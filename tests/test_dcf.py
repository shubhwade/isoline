import math

import pandas as pd
import pytest

from isoline.core import dcf


def test_zero_growth_perpetuity_hand_check():
    # FCF 100, g=0, terminal=0, r=10%, 1 year: PV(100)=90.909..., TV=100/0.10=1000 -> PV 909.09; total 1000.
    total, tshare = dcf.value(100, 0.10, 0.0, 0.0, 1)
    assert total == pytest.approx(1000.0)
    assert tshare == pytest.approx(909.0909 / 1000, rel=1e-4)


def test_growth_fades_linearly_to_terminal():
    flows = dcf.project(100, 0.10, 0.02, 5)
    rates = [flows[0] / 100 - 1] + [flows[i] / flows[i - 1] - 1 for i in range(1, 5)]
    assert rates[0] == pytest.approx(0.10) and rates[-1] == pytest.approx(0.02)
    assert rates == sorted(rates, reverse=True)


def test_discount_must_exceed_terminal_growth():
    with pytest.raises(ValueError):
        dcf.value(100, 0.03, 0.05, 0.03, 5)


def _fin(cfo, capex, revenue=None, price=None, shares=100.0):
    d = [pd.Timestamp(f"{y}-12-31") for y in (2024, 2023, 2022, 2021)]
    cash = pd.DataFrame({"Operating Cash Flow": cfo, "Capital Expenditure": capex}, index=d[: len(cfo)]).T
    inc = pd.DataFrame({"Total Revenue": revenue or [100, 95, 90, 85]}, index=d).T
    info = {"sharesOutstanding": shares, "currency": "USD", "financialCurrency": "USD"}
    if price:
        info["currentPrice"] = price
    return {"info": info, "cashflow": cash, "income_stmt": inc, "balance_sheet": pd.DataFrame()}


def test_full_dcf_with_margin_of_safety_and_scenarios():
    r = dcf.run_dcf(_fin([150, 140, 130], [-50, -50, -50], price=8.0), "X", discount=0.10, growth=0.05, terminal=0.02)
    assert r.assumptions and r.assumptions.base_fcf == pytest.approx(90.0)  # mean(100, 90, 80)
    equity, _ = dcf.value(90, 0.10, 0.05, 0.02, 5)
    assert r.equity_value == pytest.approx(equity) and r.per_share == pytest.approx(equity / 100)
    assert r.margin_of_safety == pytest.approx((r.per_share - 8.0) / r.per_share)
    bear, base, bull = (s.per_share for s in r.scenarios)
    assert bear < base < bull
    grid = r.sensitivity["values"]
    assert len(grid) == 3 and len(grid[0]) == 5
    assert grid[1][2] == pytest.approx(r.per_share)  # centre cell equals the base case


def test_no_value_for_negative_fcf_or_missing_data():
    r = dcf.run_dcf(_fin([10, 10, 10], [-50, -50, -50]), "X", discount=0.10, growth=0.05)
    assert r.per_share is None and any("not positive" in n for n in r.notes)
    r2 = dcf.run_dcf({"info": {}, "cashflow": pd.DataFrame(), "income_stmt": pd.DataFrame()}, "X")
    assert r2.assumptions is None and r2.notes


def test_default_discount_is_labelled_as_assumption_and_no_price_noted():
    r = dcf.run_dcf(_fin([150, 140, 130], [-50, -50, -50]), "X", growth=0.04)
    assert any("default assumption" in n for n in r.notes)
    assert r.margin_of_safety is None and any("No market price" in n for n in r.notes)


def test_currency_mismatch_blocks_margin_of_safety():
    f = _fin([150, 140, 130], [-50, -50, -50], price=8.0)
    f["info"]["currency"] = "GBP"
    r = dcf.run_dcf(f, "X", discount=0.10, growth=0.05)
    assert r.margin_of_safety is None and any("currency" in n.lower() for n in r.notes)


def test_default_growth_is_capped():
    f = _fin([150, 140, 130], [-50] * 3, revenue=[1000, 500, 200, 100])
    assert dcf.default_growth(f) == pytest.approx(dcf.MAX_DEFAULT_GROWTH)
    assert not math.isnan(dcf.default_growth(f))
