"""SEC EDGAR provider, tested offline against a hand-built company-facts fixture."""

from __future__ import annotations

import pytest

from telmus.core import edgar, loaders
from telmus.core.errors import NoDataError, ProviderUnavailableError, RateLimitError


def _pt(end, val, start=None, form="10-K", filed="2024-02-01"):
    p = {"end": end, "val": val, "form": form, "filed": filed}
    if start:
        p["start"] = start
    return p


def _facts():
    def flow(a, b):
        return {"units": {"USD": [
            _pt("2022-12-31", a, "2022-01-01"),
            _pt("2023-12-31", b, "2023-01-01"),
            _pt("2023-09-30", 1, "2023-07-01", form="10-Q"),  # quarter: ignored
        ]}}

    def inst(a, b):
        return {"units": {"USD": [_pt("2022-12-31", a), _pt("2023-12-31", b)]}}

    return {
        "entityName": "Acme Corp",
        "facts": {
            "us-gaap": {
                "Revenues": flow(1000, 1200),
                "CostOfRevenue": flow(600, 700),
                "NetIncomeLoss": flow(100, 150),
                "NetCashProvidedByUsedInOperatingActivities": flow(130, 180),
                "PaymentsToAcquirePropertyPlantAndEquipment": flow(40, 50),
                "Assets": inst(2000, 2400),
                "StockholdersEquity": inst(900, 1000),
            },
            "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
                {"end": "2024-01-20", "val": 500, "form": "10-K"}]}}},
        },
    }


TICKERS = {"0": {"cik_str": 1234, "ticker": "ACME", "title": "Acme Corp"}}


def _fetch(url):
    return TICKERS if url == edgar.TICKERS_URL else _facts()


def test_bundle_has_engine_shaped_frames():
    b = edgar.load_edgar("acme", _fetch)
    inc = b["income_stmt"]
    assert inc.loc["Total Revenue"].tolist() == [1200, 1000]  # newest first, quarters skipped
    assert inc.loc["Gross Profit"].tolist() == [500, 400]  # derived, revenue - cost
    assert b["cashflow"].loc["Capital Expenditure"].iloc[0] == 50
    assert b["balance_sheet"].loc["Total Assets"].iloc[0] == 2400
    assert b["info"]["symbol"] == "ACME" and b["info"]["sharesOutstanding"] == 500
    assert "SEC EDGAR" in b["source"]


def test_missing_items_stay_missing_not_zero():
    b = edgar.load_edgar("ACME", _fetch)
    assert "Inventory" not in b["balance_sheet"].index
    assert "Interest Expense" not in b["income_stmt"].index


def test_restatement_latest_filing_wins():
    pts = [_pt("2023-12-31", 1, "2023-01-01", filed="2024-02-01"),
           _pt("2023-12-31", 2, "2023-01-01", filed="2025-02-01")]
    assert edgar._annual_points(pts, flow=True) == {"2023-12-31": 2.0}


def test_non_us_and_unknown_tickers_rejected():
    with pytest.raises(NoDataError):
        edgar.load_edgar("INFY.NS", _fetch)
    with pytest.raises(NoDataError):
        edgar.load_edgar("ZZZZ", _fetch)


def test_user_agent_declares_contact(monkeypatch):
    monkeypatch.setenv("TELMUS_CONTACT", "me@example.com")
    assert "me@example.com" in edgar.user_agent() and edgar.user_agent().startswith("telmus/")


def test_scan_falls_back_to_edgar_when_yahoo_fails(monkeypatch):
    loaders.load_financials.cache_clear()
    monkeypatch.setattr(loaders, "_load_data_with_retry",
                        lambda s: (_ for _ in ()).throw(RateLimitError("429")))
    real = edgar.load_edgar
    monkeypatch.setattr(edgar, "load_edgar", lambda s: real(s, _fetch))
    from telmus import scan
    r = scan("ACME")
    assert r.company == "Acme Corp"
    assert any("SEC EDGAR" in n for n in r.notes)
    loaders.load_financials.cache_clear()


def test_non_us_ticker_keeps_yahoo_error(monkeypatch):
    loaders.load_financials.cache_clear()
    monkeypatch.setattr(loaders, "_load_data_with_retry",
                        lambda s: (_ for _ in ()).throw(ProviderUnavailableError("down")))
    with pytest.raises(ProviderUnavailableError):
        loaders.load_financials("INFY.NS")
    loaders.load_financials.cache_clear()

