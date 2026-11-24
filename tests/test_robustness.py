"""CLI error handling, loader retries, report escaping, optional MCP."""

from __future__ import annotations

import sys
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from telmus import __version__
from telmus.cli.app import app
from telmus.core import loaders
from telmus.core.errors import NoDataError, ProviderUnavailableError, RateLimitError
from telmus.exporters.html_dashboard import HtmlDashboardExporter
from tests.test_cli import fake_scan_result

runner = CliRunner()


# ------------------------------------------------------------------------- CLI
def test_version_flag() -> None:
    out = runner.invoke(app, ["--version"])
    assert out.exit_code == 0
    assert out.stdout.strip() == f"telmus {__version__}"


def test_no_args_shows_help_with_examples() -> None:
    out = runner.invoke(app, [])
    assert "scan" in out.stdout and "Examples" in out.stdout


def test_invalid_ticker_exit_code_2_and_no_scan() -> None:
    with patch("telmus.cli.app.TelmusScanner") as scanner:
        out = runner.invoke(app, ["scan", "AAPL; rm -rf /"])
    assert out.exit_code == 2
    assert "not a valid ticker" in out.stdout
    scanner.assert_not_called()


@pytest.mark.parametrize(
    ("error", "code", "hint"),
    [
        (NoDataError("No financial data available for ticker 'ZZZZ'"), 1, "exchange suffix"),
        (ProviderUnavailableError("down"), 3, "internet connection"),
        (RateLimitError("429"), 3, "rate-limiting"),
    ],
)
def test_data_errors_are_friendly_with_hint_and_no_traceback(error, code, hint) -> None:
    with patch("telmus.cli.app.TelmusScanner") as scanner:
        scanner.return_value.scan.side_effect = error
        out = runner.invoke(app, ["scan", "ZZZZ"])
    assert out.exit_code == code
    assert hint in " ".join(out.stdout.split())
    assert "Traceback" not in out.stdout


def test_unexpected_error_hides_traceback_unless_debug() -> None:
    with patch("telmus.cli.app.TelmusScanner") as scanner:
        scanner.return_value.scan.side_effect = RuntimeError("boom")
        plain = runner.invoke(app, ["scan", "AAPL"])
        debug = runner.invoke(app, ["--debug", "scan", "AAPL"])
    assert plain.exit_code == 1 and "Traceback" not in plain.stdout
    assert "--debug" in plain.stdout
    assert "Traceback" in debug.stdout
    import telmus.cli.app as cli

    cli._STATE["debug"] = False  # reset module state for other tests


def test_scan_prints_disclaimer() -> None:
    with patch("telmus.cli.app.TelmusScanner") as scanner:
        scanner.return_value.scan.return_value = fake_scan_result()
        out = runner.invoke(app, ["scan", "INFY", "--no-report"])
    assert out.exit_code == 0
    assert "not investment advice" in out.stdout


def test_serve_without_mcp_installed_explains_the_extra() -> None:
    with patch.dict(sys.modules, {"telmus.mcp.server": None}):
        out = runner.invoke(app, ["serve"])
    assert out.exit_code == 1
    assert "telmus[mcp]" in out.stdout


# ---------------------------------------------------------------------- loader
@pytest.fixture(autouse=True)
def _no_sleep_and_clear_cache(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(loaders, "_sleep", lambda s: None)
    loaders.load_financials.cache_clear()
    yield
    loaders.load_financials.cache_clear()


GOOD = ({"symbol": "AAPL"}, {"Total Revenue": 1}, {}, {}, {})


def test_transient_network_error_is_retried_then_succeeds() -> None:
    calls = Mock(side_effect=[OSError("connection reset"), TimeoutError("timed out"), GOOD])
    with patch.object(loaders, "_load_data", calls):
        assert loaders.load_financials("AAPL")["info"]["symbol"] == "AAPL"
    assert calls.call_count == 3


def test_persistent_network_error_becomes_provider_unavailable() -> None:
    calls = Mock(side_effect=OSError("curl: (7) CONNECT tunnel failed, response 403"))
    with patch.object(loaders, "_load_data", calls), pytest.raises(ProviderUnavailableError):
        loaders.load_financials("AAPL")
    assert calls.call_count == 3


def test_rate_limit_is_typed() -> None:
    err = Exception("Too Many Requests. Rate limited.")
    with patch.object(loaders, "_load_data", Mock(side_effect=err)), pytest.raises(RateLimitError):
        loaders.load_financials("AAPL")


def test_unknown_ticker_is_not_retried() -> None:
    calls = Mock(return_value=({}, {}, {}, {}, {}))
    with (
        patch.object(loaders, "_load_data", calls),
        patch.object(loaders, "_resolve_ticker_by_name", return_value=None),
        pytest.raises(NoDataError),
    ):
        loaders.load_financials("ZZZZ")
    assert calls.call_count == 1


# --------------------------------------------------------------------- reports
def test_html_report_escapes_untrusted_company_name(tmp_path) -> None:
    result = fake_scan_result()
    result.company = '<script>alert("x")</script>'
    result.exchange = "<img src=x onerror=alert(1)>"
    result.analyst_brief = "</div><script>evil()</script>"
    out = tmp_path / "r.html"
    with patch("telmus.exporters.html_dashboard.get_company_logo_url", return_value=""):
        HtmlDashboardExporter().export_scan(result, str(out))
    page = out.read_text(encoding="utf-8")
    assert "<script>alert" not in page
    assert "<img src=x" not in page
    assert "<script>evil()" not in page
    assert "&lt;script&gt;alert" in page


def test_no_report_writes_no_files_and_opens_no_browser(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with (
        patch("telmus.cli.app.TelmusScanner") as scanner,
        patch("webbrowser.open") as opener,
    ):
        scanner.return_value.scan.return_value = fake_scan_result()
        out = runner.invoke(app, ["scan", "INFY", "--no-report"])
    assert out.exit_code == 0
    assert list(tmp_path.iterdir()) == []
    opener.assert_not_called()


def test_default_scan_writes_reports_and_can_skip_browser(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with (
        patch("telmus.cli.app.TelmusScanner") as scanner,
        patch("webbrowser.open") as opener,
        patch("telmus.exporters.html_dashboard.get_company_logo_url", return_value=""),
    ):
        scanner.return_value.scan.return_value = fake_scan_result()
        out = runner.invoke(app, ["scan", "INFY", "--no-open"])
    assert out.exit_code == 0
    assert {p.name for p in tmp_path.iterdir()} == {"INFY_analysis.xlsx", "INFY_dashboard.html"}
    opener.assert_not_called()
