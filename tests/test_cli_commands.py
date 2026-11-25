"""Every CLI command, run end to end (real exporters, mocked provider, temp directory)."""

from __future__ import annotations

import csv
import json
import os
from unittest.mock import patch

import openpyxl
import pandas as pd
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from isoline.cli.app import app
from tests.test_scores import company, quality_company


def _fin(ticker: str) -> dict:
    a, b = company(), quality_company()
    for k in ("income_stmt", "balance_sheet", "cashflow"):
        extra = b[k].loc[[i for i in b[k].index if i not in a[k].index]]
        a[k] = pd.concat([a[k], extra])
    a["info"] = {"symbol": ticker, "longName": f"{ticker} Ltd", "exchange": "NSE", "marketCap": 3000.0}
    return a


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _run(*args: str):
        with (
            patch("isoline.core.scanner.load_financials", side_effect=_fin),
            patch("isoline.core.loaders.load_financials", side_effect=_fin),
            patch("webbrowser.open") as opened,
        ):
            result = CliRunner().invoke(app, list(args))
        result.opened = opened  # type: ignore[attr-defined]
        return result

    return _run


def test_every_command_has_working_help(run) -> None:
    for name in get_command(app).commands:  # type: ignore[attr-defined]
        res = run(name, "--help")
        assert res.exit_code == 0, (name, res.output)


def test_scan_default_writes_both_reports_and_opens_browser(run, tmp_path) -> None:
    res = run("scan", "AAA.NS")
    assert res.exit_code == 0, res.output
    assert (tmp_path / "AAA_analysis.xlsx").exists() and (tmp_path / "AAA_dashboard.html").exists()
    res.opened.assert_called_once()  # type: ignore[attr-defined]
    assert "Quality" in res.output


@pytest.mark.parametrize("ext", ["xlsx", "csv", "json"])
def test_scan_exports(run, tmp_path, ext) -> None:
    out = tmp_path / f"o.{ext}"
    res = run("scan", "AAA", "--export", str(out), "--no-report", "--no-open")
    assert res.exit_code == 0, res.output
    assert out.exists() and out.stat().st_size > 0
    if ext == "json":
        assert json.loads(out.read_text())["ticker"] == "AAA"


def test_scan_json_flag(run) -> None:
    res = run("scan", "AAA", "--json", "--no-report")
    assert res.exit_code == 0 and json.loads(res.output)["ticker"] == "AAA"


def test_compare_terminal_files_and_exports(run, tmp_path) -> None:
    res = run("compare", "AAA.NS", "BBB.BO")
    assert res.exit_code == 0, res.output
    assert (tmp_path / "AAAvsBBB_comparison.xlsx").exists()
    assert (tmp_path / "AAAvsBBB_dashboard.html").exists()
    out = " ".join(res.output.split())
    assert "Piotroski F-score" in out and "Return on equity" in out
    assert "not ranked" in out  # valuation multiples are never marked "better"
    res.opened.assert_called_once()  # type: ignore[attr-defined]

    for ext in ("xlsx", "csv", "json"):
        r = run("compare", "AAA", "BBB", "--export", f"c.{ext}", "--no-report", "--no-open")
        assert r.exit_code == 0 and (tmp_path / f"c.{ext}").exists(), (ext, r.output)


def test_compare_csv_keeps_real_zeros_and_ranks_nothing_for_valuation(run, tmp_path) -> None:
    res = run("compare", "AAA", "BBB", "--export", "c.csv", "--no-report", "--no-open")
    assert res.exit_code == 0
    rows = list(csv.reader((tmp_path / "c.csv").open(encoding="utf-8")))
    assert rows[0] == ["Metric", "AAA", "BBB", "Stronger"]
    by = {r[0]: r for r in rows[1:]}
    assert by["P/E ratio"][3] == "" and by["EV/EBITDA"][3] == ""  # no winner for multiples
    assert by["Piotroski F-score"][1] == "8"
    # identical companies tie everywhere
    assert all(r[3] == "" for r in rows[1:])


def test_compare_alias_and_bad_input(run, tmp_path) -> None:
    assert run("comp", "AAA", "BBB", "--no-report", "--no-open").exit_code == 0
    assert run("compare", "AAA").exit_code == 2  # missing argument
    res = run("compare", "AAA", "bad/ticker", "--no-report")
    assert res.exit_code == 2 and "not a valid ticker" in res.output
    # a company name with a space still yields a safe file name
    res = run("compare", "AAA", "Tata Motors", "--no-open")
    assert res.exit_code == 0 and (tmp_path / "AAAvsTata_Motors_dashboard.html").exists()


def test_screen_all_formats(run, tmp_path) -> None:
    res = run("screen", "IT", "--min-piotroski", "0", "--max-de", "100", "--export", "s.json")
    assert res.exit_code == 0, res.output
    assert len(json.loads((tmp_path / "s.json").read_text())) == 5
    for ext in ("csv", "xlsx"):
        r = run("screen", "it", "--min-piotroski", "0", "--max-de", "100", "--export", f"s.{ext}")
        assert r.exit_code == 0 and (tmp_path / f"s.{ext}").exists(), (ext, r.output)
    assert run("screen", "Pharma").exit_code == 2


def test_check_info_and_serve_message(run) -> None:
    res = run("check", "AAA")
    assert res.exit_code == 0 and "Piotroski F-score: 8" in res.output
    assert run("info").exit_code == 0
    assert run("--version").exit_code == 0


def test_powerbi_portfolio_and_flags(run, tmp_path) -> None:
    res = run("powerbi", "AAA", "BBB", "--export", "p.csv")
    assert res.exit_code == 0, res.output
    assert (tmp_path / "p.csv").exists() and (tmp_path / "p_report.html").exists()
    assert len(list(csv.reader((tmp_path / "p.csv").open(encoding="utf-8")))) == 3
    res = run("powerbi", "--tickers", "AAA", "--tickers", "BBB", "--export", "f.csv", "--flags")
    assert res.exit_code == 0 and (tmp_path / "f.csv").exists(), res.output
    assert run("powerbi", "--export", "x.csv").exit_code == 1  # no tickers


def test_excel_compare_workbook_is_readable(run, tmp_path) -> None:
    run("compare", "AAA", "BBB", "--no-open")
    wb = openpyxl.load_workbook(tmp_path / "AAAvsBBB_comparison.xlsx")
    assert wb.sheetnames
    assert os.path.getsize(tmp_path / "AAAvsBBB_comparison.xlsx") > 1000


def test_value_command_prints_assumptions_and_scenarios(run) -> None:
    result = run("value", "ACME", "--discount", "0.10", "--growth", "0.05", "--terminal", "0.02")
    assert result.exit_code == 0, result.output
    for text in ("DCF assumptions", "Scenarios", "Sensitivity", "not a price target"):
        assert text in result.output


def test_value_json_is_valid_and_rejects_bad_rates(run) -> None:
    import json

    ok = run("value", "ACME", "--json", "--discount", "0.10", "--growth", "0.05")
    assert ok.exit_code == 0 and json.loads(ok.output)["assumptions"]["discount_rate"] == 0.10
    bad = run("value", "ACME", "--discount", "0.02", "--terminal", "0.03", "--growth", "0.05")
    assert bad.exit_code == 0 and "not computed" in bad.output
