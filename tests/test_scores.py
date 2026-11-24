"""Financial-score tests using hand-computed expected values (no network)."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from telmus.core.engines.flags import FlagsEngine
from telmus.core.engines.health import HealthEngine
from telmus.core.engines.valuation import ValuationEngine
from telmus.core.labels import at, series, to_float

DATES = ["2024-12-31", "2023-12-31", "2022-12-31"]


def frame(rows: dict[str, list[float | None]]) -> pd.DataFrame:
    """yfinance orientation: items as rows, newest period first."""
    return pd.DataFrame({k: dict(zip(DATES, v, strict=False)) for k, v in rows.items()}).T


def company() -> dict[str, object]:
    income = frame(
        {
            "Total Revenue": [1000, 900, 800],
            "Gross Profit": [400, 340, 300],
            "Net Income": [120, 80, 60],
            "Operating Income": [150, 120, 100],
            "Interest Expense": [10, 12, 12],
            "Selling General And Administration": [100, 81, 70],
        }
    )
    balance = frame(
        {
            "Total Assets": [1100, 1000, 900],
            "Current Assets": [500, 450, 400],
            "Current Liabilities": [250, 250, 240],
            "Total Liabilities Net Minority Interest": [500, 480, 460],
            "Stockholders Equity": [600, 520, 440],
            "Retained Earnings": [330, 250, 190],
            "Long Term Debt": [100, 150, 160],
            "Accounts Receivable": [120, 90, 80],
            "Net PPE": [400, 380, 360],
            "Ordinary Shares Number": [100, 100, 100],
        }
    )
    cashflow = frame(
        {
            "Operating Cash Flow": [150, 100, 90],
            "Capital Expenditure": [-60, -50, -40],
            "Depreciation And Amortization": [40, 36, 33],
        }
    )
    return {"income_stmt": income, "balance_sheet": balance, "cashflow": cashflow, "info": {}}


# --------------------------------------------------------------------- Piotroski
def test_piotroski_hand_computed_score_is_8() -> None:
    result = HealthEngine().run(company())
    # Every signal passes except asset turnover: 1000/1000 == 900/900 (not greater).
    assert result.piotroski_f == 8
    assert result.piotroski_signals["Asset Turnover Rising"] == 0
    assert sum(result.piotroski_signals.values()) == 8


def test_piotroski_not_reported_when_a_signal_cannot_be_computed() -> None:
    fin = company()
    fin["balance_sheet"] = fin["balance_sheet"].drop("Ordinary Shares Number")  # type: ignore[union-attr]
    result = HealthEngine().run(fin)
    assert result.piotroski_f is None
    assert "No Dilution" not in result.piotroski_signals
    assert any("No Dilution" in n for n in result.notes)


def test_piotroski_needs_history_not_zero() -> None:
    fin = company()
    fin["balance_sheet"] = fin["balance_sheet"].iloc[:, :1]  # only one year
    result = HealthEngine().run(fin)
    assert result.piotroski_f is None  # insufficient data is not a score of 0


def test_debt_free_company_leverage_is_zero_not_missing() -> None:
    fin = company()
    bs = fin["balance_sheet"].drop("Long Term Debt")  # type: ignore[union-attr]
    bs.loc["Total Debt"] = [0, 0, 0]
    fin["balance_sheet"] = bs
    assert HealthEngine()._leverage_decreasing(bs) is False  # 0 -> 0 is not "falling"


# ------------------------------------------------------------------------ Altman
def test_altman_z_double_prime_hand_computed() -> None:
    # X1=250/1100 X2=330/1100 X3=150/1100 X4=600/500 (BOOK equity / liabilities)
    assert HealthEngine().run(company()).altman_z == pytest.approx(4.645273, abs=1e-5)


def test_altman_not_applicable_to_financials() -> None:
    fin = company()
    fin["info"] = {"sector": "Financial Services"}
    result = HealthEngine().run(fin)
    assert result.altman_z is None
    assert any("not applicable" in n for n in result.notes)


def test_altman_missing_retained_earnings_is_none_not_equity_fallback() -> None:
    fin = company()
    fin["balance_sheet"] = fin["balance_sheet"].drop("Retained Earnings")  # type: ignore[union-attr]
    assert HealthEngine().run(fin).altman_z is None


# ----------------------------------------------------------------------- Beneish
def test_beneish_components_and_score_hand_computed() -> None:
    f = company()
    c = FlagsEngine().beneish_components(f["income_stmt"], f["balance_sheet"], f["cashflow"])  # type: ignore[arg-type]
    assert c is not None
    expected = {
        "DSRI": 1.2, "GMI": 0.944444, "AQI": 1.069519, "SGI": 1.111111,
        "DEPI": 0.951923, "SGAI": 1.111111, "TATA": -0.027273, "LVGI": 0.795455,
    }
    for key, value in expected.items():
        assert c[key] == pytest.approx(value, abs=1e-5), key
    result = FlagsEngine().run(f)
    assert result.beneish_m == pytest.approx(-2.2835, abs=1e-3)
    assert not any(fl.type == "beneish_m" for fl in result.red_flags)  # below -2.22


def test_beneish_flags_aggressive_accruals() -> None:
    f = company()
    cf = f["cashflow"].copy()  # type: ignore[union-attr]
    cf.loc["Operating Cash Flow"] = [-100, 100, 90]  # profit with large cash shortfall
    f["cashflow"] = cf
    result = FlagsEngine().run(f)
    assert result.beneish_m is not None and result.beneish_m > -2.22
    assert any(fl.type == "beneish_m" and fl.severity == "high" for fl in result.red_flags)


def test_beneish_missing_input_is_none_and_explained() -> None:
    f = company()
    f["balance_sheet"] = f["balance_sheet"].drop("Accounts Receivable")  # type: ignore[union-attr]
    result = FlagsEngine().run(f)
    assert result.beneish_m is None
    assert any("Beneish" in n for n in result.notes)


def test_beneish_not_applicable_to_financials() -> None:
    f = company()
    f["info"] = {"sector": "Financial Services"}
    assert FlagsEngine().run(f).beneish_m is None


# ------------------------------------------------------------------- Ratios etc.
def test_ratios_hand_computed() -> None:
    r = HealthEngine().run(company())
    assert r.current_ratio == pytest.approx(2.0)
    assert r.debt_to_equity == pytest.approx(500 / 600)
    assert r.interest_coverage == pytest.approx(15.0)


def test_negative_equity_gives_no_de_ratio_but_a_high_flag() -> None:
    f = company()
    bs = f["balance_sheet"].copy()  # type: ignore[union-attr]
    bs.loc["Stockholders Equity"] = [-50, 10, 20]
    f["balance_sheet"] = bs
    assert HealthEngine().run(f).debt_to_equity is None
    flags = FlagsEngine().run(f)
    assert any(x.type == "negative_equity" and x.severity == "high" for x in flags.red_flags)


def test_zero_denominators_do_not_crash() -> None:
    f = company()
    cf = f["cashflow"]
    inc = f["income_stmt"].copy()  # type: ignore[union-attr]
    inc.loc["Interest Expense"] = [0, 0, 0]
    bs = f["balance_sheet"].copy()  # type: ignore[union-attr]
    bs.loc["Current Liabilities"] = [0, 0, 0]
    out = HealthEngine().run({**f, "income_stmt": inc, "balance_sheet": bs, "cashflow": cf})
    assert out.interest_coverage is None and out.current_ratio is None


def test_interest_coverage_never_falls_back_to_ebitda() -> None:
    inc = frame({"EBITDA": [500, 400, 300], "Interest Expense": [10, 10, 10]})
    assert HealthEngine()._compute_interest_coverage(inc) is None


def test_empty_input_gives_nones_not_zeros() -> None:
    r = HealthEngine().run({})
    assert r.piotroski_f is None and r.altman_z is None
    assert r.debt_to_equity is None and r.current_ratio is None
    assert FlagsEngine().run({}).beneish_m is None


# -------------------------------------------------------------- FCF sign regression
@pytest.mark.parametrize("capex", [-60, 60])
def test_fcf_counts_capex_regardless_of_sign(capex: float) -> None:
    # CFO 50, capex 60 => FCF -10 in each of three years, whichever sign capex has.
    cf = frame({"Operating Cash Flow": [50, 50, 50], "Capital Expenditure": [capex] * 3})
    assert FlagsEngine()._negative_fcf_years(cf) == 3


# ------------------------------------------------------------------------ Labels
def test_legacy_and_modern_labels_give_same_answer() -> None:
    legacy = frame({"Total Liab": [500, 480, 460], "Total Stockholder Equity": [600, 520, 440]})
    modern = frame(
        {"Total Liabilities Net Minority Interest": [500, 480, 460], "Stockholders Equity": [600, 520, 440]}
    )
    e = HealthEngine()
    assert e._compute_debt_to_equity(legacy) == e._compute_debt_to_equity(modern)


def test_series_sorts_oldest_first_input_newest_first() -> None:
    df = pd.DataFrame({"Total Assets": {"2022-12-31": 1, "2024-12-31": 3, "2023-12-31": 2}}).T
    assert series(df, "total_assets") == [3.0, 2.0, 1.0]


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "x", True])
def test_to_float_rejects_non_finite_and_junk(bad: object) -> None:
    assert to_float(bad) is None
    assert to_float(0) == 0.0  # a genuine zero stays zero
    assert at([1.0], 5) is None


# --------------------------------------------------------------------- Valuation
def test_valuation_cash_lookup_does_not_raise_on_series_truthiness() -> None:
    """Regression: `Series or Series` raised ValueError whenever a 'Cash' row existed."""
    bs = frame({"Cash": [10, 9, 8], "Total Debt": [5, 5, 5], "Stockholders Equity": [100, 90, 80]})
    inc = frame({"EBITDA": [20, 18, 16], "Net Income": [10, 9, 8]})
    out = ValuationEngine().run(
        {"info": {"marketCap": 200.0}, "balance_sheet": bs, "income_stmt": inc}
    )
    assert out.pb_ratio == pytest.approx(2.0)
    assert out.ev_ebitda == pytest.approx((200 + 5 - 10) / 20)
    assert out.vs_sector is None  # peer comparison is not implemented; no invented answer
    assert math.isfinite(out.pe_ratio)  # type: ignore[arg-type]


# ------------------------------------------------------------------------ Growth
def test_growth_fcf_yield_and_cagr_hand_computed() -> None:
    from telmus.core.engines.growth import GrowthEngine

    inc = pd.DataFrame(
        {
            "Total Revenue": {"2024": 1331.0, "2023": 1210.0, "2022": 1100.0, "2021": 1000.0},
            "Net Income": {"2024": 266.2, "2023": 200.0, "2022": 150.0, "2021": 100.0},
            "Operating Income": {"2024": 266.2, "2023": 200.0, "2022": 180.0, "2021": 150.0},
        }
    ).T
    cf = frame({"Operating Cash Flow": [300, 0, 0], "Capital Expenditure": [-100, 0, 0]})
    out = GrowthEngine().run({"income_stmt": inc, "cashflow": cf, "info": {"marketCap": 4000}})
    assert out.revenue_cagr_3y == pytest.approx(0.10, abs=1e-9)  # (1331/1000)^(1/3)-1
    assert out.pat_cagr_3y == pytest.approx(0.385913, abs=1e-5)  # (266.2/100)^(1/3)-1
    # FCF = 300 - |-100| = 200 ; 200 / 4000 = 5%. (The old code gave (300+100)/4000 = 10%.)
    assert out.fcf_yield == pytest.approx(0.05)
    assert out.margin_trend == "improving"  # 20% vs 15% operating margin


def test_margin_trend_unknown_when_a_year_is_missing_not_zero() -> None:
    from telmus.core.engines.growth import GrowthEngine

    inc = frame({"Total Revenue": [100, 100, 100], "Operating Income": [20, 20, None]})
    assert GrowthEngine()._margin_trend(inc) is None


# ------------------------------------------------------------ end-to-end (offline)
def test_scanner_end_to_end_with_mocked_provider() -> None:
    from unittest.mock import patch

    from telmus.core.scanner import TelmusScanner

    fin = company()
    fin["info"] = {"symbol": "ACME", "longName": "Acme Corp", "exchange": "NYQ", "marketCap": 3000.0}
    with patch("telmus.core.scanner.load_financials", return_value=fin):
        result = TelmusScanner().scan("ACME")
    assert (result.ticker, result.company) == ("ACME", "Acme Corp")
    assert result.health.piotroski_f == 8
    assert result.health.altman_z == pytest.approx(4.645273, abs=1e-5)
    assert result.beneish_m == pytest.approx(-2.2835, abs=1e-3)
    assert result.valuation.pb_ratio == pytest.approx(3000 / 600)
    assert result.valuation.vs_sector is None
    assert result.highest_concern == "low"
    payload = result.to_dict()  # serialisable, with explanatory notes list
    assert payload["notes"] == []
    with patch("telmus.core.scanner.load_financials", return_value=fin):
        cmp = TelmusScanner().compare("ACME", "ACME")
    assert cmp.result_a.ticker == cmp.result_b.ticker == "ACME"


def test_scan_result_carries_notes_for_every_na() -> None:
    from unittest.mock import patch

    from telmus.core.scanner import TelmusScanner

    sparse = {"info": {"symbol": "X"}, "income_stmt": frame({"Total Revenue": [1, 1, 1]})}
    with patch("telmus.core.scanner.load_financials", return_value=sparse):
        result = TelmusScanner().scan("X")
    assert result.health.piotroski_f is None and result.beneish_m is None
    assert any("Piotroski" in n for n in result.notes)
    assert any("Beneish" in n for n in result.notes)
