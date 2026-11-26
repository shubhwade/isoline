"""Financial statements: engine, report presentation, CLI, MCP, SDK, Excel and Power BI."""

from __future__ import annotations

import copy
import csv
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pandas as pd
import pytest

from isoline.core.engines.statements import StatementsEngine
from isoline.core.result import CompareResult
from isoline.core.scanner import IsolineScanner
from isoline.exporters.report import (
    _acct,
    _change,
    _scale,
    compare_report,
    portfolio_report,
    scan_report,
)

sys.path.insert(0, str(Path(__file__).parents[1] / "examples"))
from make_sample_assets import synthetic  # noqa: E402

from tests.fixtures.infy_mock import infy_financials  # noqa: E402


def _scan(fin: dict, ticker: str = "ACME"):
    with patch("isoline.core.scanner.load_financials", return_value=fin):
        return IsolineScanner().scan(ticker)


def _line(lines, key):
    return next(ln for ln in lines if ln.key == key)


# ----------------------------------------------------------------- engine
def test_engine_lays_out_three_statements_newest_first() -> None:
    st = StatementsEngine().run(synthetic())
    assert st is not None and st.currency == "USD"
    assert st.periods == ["2024-12-31", "2023-12-31", "2022-12-31", "2021-12-31"]
    assert _line(st.income, "revenue").values[0] == 1480e6
    assert _line(st.income, "cogs").sign == -1  # a cost, shown in parentheses
    assert _line(st.balance, "total_assets").kind == "total"
    assert [ln.group for ln in st.balance][:1] == ["Assets"]


def test_computed_lines_only_from_reported_components() -> None:
    st = StatementsEngine().run(synthetic())
    fcf = _line(st.cashflow, "fcf")
    assert fcf.computed and fcf.values == [150e6, 110e6, 75e6, 48e6]
    tle = _line(st.balance, "total_liabilities_equity")
    assert tle.computed and tle.values == _line(st.balance, "total_assets").values
    assert st.notes == []  # the sample balances in every year


def test_unbalanced_data_is_flagged_not_hidden() -> None:
    fin = copy.deepcopy(synthetic())
    fin["balance_sheet"].loc["Stockholders Equity"] = [500e6, 800e6, 700e6, 600e6]
    st = StatementsEngine().run(fin)
    assert len(st.notes) == 1 and "FY2024" in st.notes[0] and "FY2023" not in st.notes[0]


def test_transposed_frames_and_outflow_sign_normalisation() -> None:
    st = StatementsEngine().run(infy_financials())  # dates as rows; capex reported positive
    assert st is not None and st.periods[0] == "2024-03-31"
    assert all(v is None or v < 0 for v in _line(st.cashflow, "capex").values)
    assert _line(st.cashflow, "fcf").values[0] == pytest.approx(320e9 - 45e9)


def test_missing_values_stay_none_and_empty_lines_are_dropped() -> None:
    st = StatementsEngine().run(infy_financials())
    total_assets = _line(st.balance, "total_assets").values
    assert total_assets[2] is None and total_assets[3] is None  # not reported, never zero
    assert all(any(v is not None for v in ln.values) for lines in (st.income, st.balance, st.cashflow) for ln in lines)


def test_engine_returns_none_without_data() -> None:
    assert StatementsEngine().run({}) is None
    assert StatementsEngine().run({"income_stmt": pd.DataFrame()}) is None


# ----------------------------------------------------------------- formatting
def test_accounting_format_and_scale() -> None:
    assert _acct(-880e6, 1e6, 0) == "(880)" and _acct(1480e6, 1e6, 0) == "1,480"
    assert "n/a" in _acct(None, 1e6, 0) and _acct(-0.0001, 1, 0) == "0"
    assert _scale([1.48e9]) == (1e6, "millions")  # filings show 1,480, not 1.48
    assert _scale([1.54e12]) == (1e9, "billions") and _scale([5e4]) == (1.0, "")


def test_year_on_year_rules() -> None:
    assert _change(110, 100) == "+10.0%"
    assert _change(-110, -30) == "n.m."  # a deeper loss is not "growth"
    assert _change(-90, -80, outflow=True) == "+12.5%"  # capex rose 12.5%
    assert _change(1, 0) == "n/a" and _change(None, 1) == "n/a"


# ----------------------------------------------------------------- reports
def test_scan_report_reads_like_a_statement() -> None:
    html = scan_report(_scan(synthetic()))
    for text in ("Income statement", "Balance sheet", "Cash flow statement", "In millions of USD", "1,480", "(880)",
                 "Total liabilities and equity", "&dagger;", "discounted cash flow", "$19.02",
                 # beginner aids: plain-English meanings, strengths/concerns, glossary, reading guide
                 "What it means", "Strengths", "Concerns", "Glossary", "How to read this report",
                 "of short-term assets for every 1.00 of bills due within a year"):
        assert text in html, text
    assert html.count('class="tot"') >= 3  # net income, total assets, free cash flow
    # published-statement conventions: currency sign on the first row, flush result lines
    assert '<td class="cur">$</td>' in html and 'class="sub flush"' in html
    for slop in ("Georgia", "letter-spacing", "border-radius"):
        assert slop not in html, slop
    assert "Page \" counter(page)" in html  # numbered pages when printed


def test_reports_escape_provider_text_everywhere() -> None:
    from isoline.exporters._safe import escape_obj

    fin = copy.deepcopy(synthetic())
    fin["info"] = {**fin["info"], "symbol": "EV", "longName": "<img src=x onerror=alert(1)>"}
    r = escape_obj(_scan(fin, "EV"))
    for html in (scan_report(r), compare_report(CompareResult("EV", "EV", r, r)), portfolio_report([r])):
        assert "<img" not in html and "&lt;img" in html


def test_reports_never_touch_the_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from isoline.exporters.excel import ExcelExporter
    from isoline.exporters.html_dashboard import HtmlDashboardExporter

    r = _scan(synthetic())

    def no_network(*_a, **_k):
        raise AssertionError("an exporter opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    HtmlDashboardExporter().export_scan(r, str(tmp_path / "r.html"))
    ExcelExporter().export(r, str(tmp_path / "r.xlsx"))


def test_excel_has_statement_sheets_at_full_precision(tmp_path: Path) -> None:
    from isoline.exporters.excel import ExcelExporter

    out = tmp_path / "r.xlsx"
    ExcelExporter().export(_scan(synthetic()), str(out))
    wb = openpyxl.load_workbook(out)
    assert {"Income Statement", "Balance Sheet", "Cash Flow"} <= set(wb.sheetnames)
    rows = {r[0]: r[1:] for r in wb["Income Statement"].iter_rows(min_row=3, values_only=True)}
    assert rows["Revenue"][0] == 1480e6 and rows["Cost of revenue"][0] == -880e6


def test_portfolio_export_skips_failed_tickers(tmp_path: Path) -> None:
    from isoline.core.errors import NoDataError
    from isoline.exporters.powerbi import PowerBIExporter, report_path

    def fake(t: str) -> dict:
        if t == "BAD":
            raise NoDataError("no data for BAD")
        fin = copy.deepcopy(synthetic())
        fin["info"] = {**fin["info"], "symbol": t}
        return fin

    exp = PowerBIExporter()
    out = tmp_path / "p.csv"
    with patch("isoline.core.scanner.load_financials", side_effect=fake):
        exp.export_portfolio(["ACME", "BAD"], str(out))
    assert list(exp.failures) == ["BAD"]
    assert len(list(csv.reader(open(out, encoding="utf-8")))) == 2
    assert "Could not be analysed: BAD" in Path(report_path(str(out))).read_text(encoding="utf-8")
    with patch("isoline.core.scanner.load_financials", side_effect=fake), pytest.raises(Exception, match="None of the tickers"):
        exp.export_portfolio(["BAD"], str(out))


# ----------------------------------------------------------------- CLI, MCP, SDK
def test_cli_statements_table_json_and_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from isoline.cli.app import app

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    with patch("isoline.core.loaders.load_financials", return_value=synthetic()):
        res = runner.invoke(app, ["statements", "ACME"], terminal_width=120)
        assert res.exit_code == 0 and "Income statement" in res.output and "1,480" in res.output
        res = runner.invoke(app, ["statements", "ACME", "--json"])
        assert json.loads(res.output)["periods"][0] == "2024-12-31"
        res = runner.invoke(app, ["statements", "ACME", "--export", "s.csv"])
        assert res.exit_code == 0
        rows = list(csv.reader(open(tmp_path / "s.csv", encoding="utf-8")))
        assert rows[0][:3] == ["Statement", "Line item", "FY2024"] and ["Income statement", "Revenue"] == rows[1][:2]
        res = runner.invoke(app, ["statements", "ACME", "--export", "s.exe"])
        assert res.exit_code != 0
    assert runner.invoke(app, ["statements", "../x"]).exit_code == 2


def test_mcp_statements_and_value_tools() -> None:
    pytest.importorskip("mcp")
    import asyncio

    from isoline.mcp.server import handle_tool_call

    def call(name: str, args: dict) -> dict:
        return json.loads(asyncio.run(handle_tool_call(name, args)).content[0].text)

    with patch("isoline.core.loaders.load_financials", return_value=synthetic()):
        st = call("statements", {"ticker": "ACME"})["statements"]
        assert st["income"][0]["key"] == "revenue"
        val = call("value", {"ticker": "ACME", "discount": 0.09, "years": 7})["result"]
        assert val["assumptions"]["discount_rate"] == 0.09 and val["assumptions"]["years"] == 7
        with pytest.raises(ValueError):
            call("value", {"ticker": "ACME", "discount": 5})
        with pytest.raises(ValueError):
            call("value", {"ticker": "ACME", "years": 100})


def test_sdk_statements_and_value() -> None:
    import isoline.sdk as sdk

    with patch("isoline.core.loaders.load_financials", return_value=synthetic()):
        st = sdk.statements("ACME")
        assert st is not None and _line(st.income, "net_income").values[0] == 180e6
        assert sdk.value("ACME").per_share == pytest.approx(19.017, abs=0.01)
    with pytest.raises(ValueError):
        sdk.statements("../etc")
