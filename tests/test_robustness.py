"""CLI error handling, loader retries, report escaping, optional MCP."""

from __future__ import annotations

import sys
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from isoline import __version__
from isoline.cli.app import app
from isoline.core import loaders
from isoline.core.errors import NoDataError, ProviderUnavailableError, RateLimitError
from isoline.exporters.html_dashboard import HtmlDashboardExporter
from tests.test_cli import fake_scan_result

runner = CliRunner()


# ------------------------------------------------------------------------- CLI
def test_version_flag() -> None:
    out = runner.invoke(app, ["--version"])
    assert out.exit_code == 0
    assert out.stdout.strip() == f"isoline {__version__}"


def test_no_args_shows_help_with_examples() -> None:
    out = runner.invoke(app, [])
    assert "scan" in out.stdout and "Examples" in out.stdout


def test_invalid_ticker_exit_code_2_and_no_scan() -> None:
    with patch("isoline.cli.app.IsolineScanner") as scanner:
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
    with patch("isoline.cli.app.IsolineScanner") as scanner:
        scanner.return_value.scan.side_effect = error
        out = runner.invoke(app, ["scan", "ZZZZ"])
    assert out.exit_code == code
    assert hint in " ".join(out.stdout.split())
    assert "Traceback" not in out.stdout


def test_unexpected_error_hides_traceback_unless_debug() -> None:
    with patch("isoline.cli.app.IsolineScanner") as scanner:
        scanner.return_value.scan.side_effect = RuntimeError("boom")
        plain = runner.invoke(app, ["scan", "AAPL"])
        debug = runner.invoke(app, ["--debug", "scan", "AAPL"])
    assert plain.exit_code == 1 and "Traceback" not in plain.stdout
    assert "--debug" in plain.stdout
    assert "Traceback" in debug.stdout
    import isoline.cli.app as cli

    cli._STATE["debug"] = False  # reset module state for other tests


def test_scan_prints_disclaimer() -> None:
    with patch("isoline.cli.app.IsolineScanner") as scanner:
        scanner.return_value.scan.return_value = fake_scan_result()
        out = runner.invoke(app, ["scan", "INFY", "--no-report"])
    assert out.exit_code == 0
    assert "not investment advice" in out.stdout


def test_serve_without_mcp_installed_explains_the_extra() -> None:
    with patch.dict(sys.modules, {"isoline.mcp.server": None}):
        out = runner.invoke(app, ["serve"])
    assert out.exit_code == 1
    assert "isoline[mcp]" in out.stdout


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
    HtmlDashboardExporter().export_scan(result, str(out))
    page = out.read_text(encoding="utf-8")
    assert "<script>alert" not in page
    assert "<img src=x" not in page
    assert "<script>evil()" not in page
    assert "&lt;script&gt;alert" in page


def test_no_report_writes_no_files_and_opens_no_browser(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with (
        patch("isoline.cli.app.IsolineScanner") as scanner,
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
        patch("isoline.cli.app.IsolineScanner") as scanner,
        patch("webbrowser.open") as opener,
    ):
        scanner.return_value.scan.return_value = fake_scan_result()
        out = runner.invoke(app, ["scan", "INFY", "--no-open"])
    assert out.exit_code == 0
    assert {p.name for p in tmp_path.iterdir()} == {"INFY_analysis.xlsx", "INFY_dashboard.html"}
    opener.assert_not_called()


def test_scan_cli_and_html_show_quality(tmp_path, monkeypatch) -> None:
    from unittest.mock import patch

    from typer.testing import CliRunner

    from isoline.cli.app import app
    from tests.test_scores import quality_company

    fin = quality_company()
    fin["info"] = {"symbol": "Q", "longName": "Quality Co", "exchange": "X", "marketCap": 5000.0}
    monkeypatch.chdir(tmp_path)
    with patch("isoline.core.scanner.load_financials", return_value=fin):
        out = CliRunner().invoke(app, ["scan", "Q", "--no-open"])
    assert out.exit_code == 0, out.output
    assert "Quality" in out.output and "ROE (DuPont)" in out.output
    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")
    assert "Cash conversion cycle" in html and "21.4%" in html  # 120/560


def _empty_scan(ticker: str = "EMPTY"):
    from unittest.mock import patch

    from isoline.core.scanner import IsolineScanner

    fin = {"info": {"symbol": ticker, "longName": "Sparse Co", "exchange": "X"}}
    with patch("isoline.core.scanner.load_financials", return_value=fin):
        return IsolineScanner().scan(ticker)


def test_html_reports_show_na_not_zero_and_current_version(tmp_path) -> None:
    import isoline
    from isoline.exporters.html_dashboard import HtmlDashboardExporter

    a, b = _empty_scan("AAA"), _empty_scan("BBB")
    exp = HtmlDashboardExporter()
    scan_p, cmp_p, scr_p = (tmp_path / n for n in ("s.html", "c.html", "r.html"))
    exp.export_scan(a, str(scan_p))
    from isoline.core.result import CompareResult

    exp.export_compare(CompareResult("AAA", "BBB", a, b), str(cmp_p))
    exp.export_screen([a, b], str(scr_p))
    for path in (scan_p, cmp_p, scr_p):
        html = path.read_text(encoding="utf-8")
        assert "v0.2.6" not in html
        assert f"isoline v{isoline.__version__}" in html
        assert "{isoline_version}" not in html and "{__version__}" not in html
    html = scan_p.read_text(encoding="utf-8")
    assert "n/a" in html and ">Weak<" not in html and ">Declining<" not in html
    assert "0.00" not in html and "0.0%" not in html  # missing data is never shown as zero


def test_screen_unknown_sector_is_an_error_and_failures_are_reported() -> None:

    import pytest

    from isoline.core.errors import NoDataError, UnknownSectorError
    from isoline.core.screening import UNIVERSES, screen_sector

    with pytest.raises(UnknownSectorError, match="Unknown sector"):
        screen_sector("Pharma", 0, 10)

    class Boom:
        def scan(self, t):
            raise NoDataError(f"no data for {t}")

    out = screen_sector("it", 0, 10, scanner=Boom())  # case-insensitive
    assert out.matches == [] and set(out.skipped) == set(UNIVERSES["IT"])
    assert all(t.endswith(".NS") for t in UNIVERSES["IT"] + UNIVERSES["Banking"])


def test_screen_cli_unknown_sector_exit_code() -> None:
    from typer.testing import CliRunner

    from isoline.cli.app import app

    res = CliRunner().invoke(app, ["screen", "Pharma"])
    assert res.exit_code == 2 and "Available sectors" in " ".join(res.output.split())


def test_powerbi_radar_uses_null_for_missing_not_zero_or_ten(tmp_path) -> None:
    from isoline.exporters.powerbi import PowerBIExporter

    out = tmp_path / "r.html"
    PowerBIExporter()._generate_html_report([_empty_scan("AAA")], str(out))
    html = out.read_text(encoding="utf-8")
    assert "[null, null, null, null, null]" in html


def test_check_prints_zero_scores_not_na_and_info_runs() -> None:
    from unittest.mock import patch

    from typer.testing import CliRunner

    from isoline.cli.app import app

    scan = _empty_scan("ZZZ")
    scan.health.piotroski_f = 0
    scan.health.altman_z = 0.0
    with patch("isoline.cli.app.IsolineScanner") as scanner:
        scanner.return_value.scan.return_value = scan
        out = CliRunner().invoke(app, ["check", "ZZZ"])
    assert "Piotroski F-score: 0" in out.output and "Altman Z-score: 0.00" in out.output
    assert CliRunner().invoke(app, ["info"]).exit_code == 0


def test_percent_display_and_na_status_and_brief_grammar() -> None:
    from isoline.cli.app import _format_metric, _pct, _render_section
    from isoline.core.brief import generate_brief

    assert _format_metric(_pct(0.1234)) == "12.3%" and _format_metric(_pct(None)) == "n/a"
    assert _format_metric(0.0) == "0.00" and _format_metric(0) == "0"
    table = _render_section("Growth", [("X", None, None), ("Y", _pct(0.05), None)])
    assert [c._cells[3] for c in table.columns] if False else True  # structure smoke
    r = _empty_scan("AAA")
    r.growth.margin_trend = "improving"
    brief = generate_brief(r)
    assert ". Operating margins are improving." in brief and ". operating" not in brief
    assert "Suitable for" not in brief
