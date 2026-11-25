"""SEC EDGAR provider: official US filings via the free XBRL "company facts" API.

Why it exists: Yahoo Finance is an unofficial, unauthenticated source that rate-limits
and blocks without notice. For US-listed companies the SEC publishes the same numbers
filers report in their 10-K filings, free, with no key. It is used as a fallback when
Yahoo cannot supply the statements, and every result carries ``source`` so a reader
can see where the figures came from.

Limits (stated, not hidden):
  * US filers only (no foreign exchanges, no ``.NS``/``.L`` tickers).
  * Annual (10-K) data, roughly the last five fiscal years; no live price or market cap,
    so valuation multiples are ``n/a`` from this source.
  * Companies choose among equivalent XBRL tags, so a line item can be missing; it is
    left missing rather than approximated.
  * The SEC asks every client to declare itself and to stay under 10 requests/second.
    Set ``ISOLINE_CONTACT`` (an email or site) to identify yourself.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd

from isoline import __version__
from isoline.branding import env
from isoline.core.errors import NoDataError, ProviderUnavailableError

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
_MIN_INTERVAL = 0.15  # about 6 requests/second, under the SEC's 10/s ceiling

# yfinance-style row label -> us-gaap concepts, best first. First concept with data wins.
_FLOW: dict[str, list[str]] = {
    "Total Revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "Cost Of Revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "Gross Profit": ["GrossProfit"],
    "Selling General And Administration": ["SellingGeneralAndAdministrativeExpense"],
    "EBIT": ["OperatingIncomeLoss"],
    "Interest Expense": ["InterestExpense", "InterestExpenseDebt"],
    "Pretax Income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "Tax Provision": ["IncomeTaxExpenseBenefit"],
    "Net Income": ["NetIncomeLoss", "ProfitLoss"],
    "Reconciled Depreciation": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "Operating Cash Flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "Capital Expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
}
_INSTANT: dict[str, list[str]] = {
    "Total Assets": ["Assets"],
    "Current Assets": ["AssetsCurrent"],
    "Current Liabilities": ["LiabilitiesCurrent"],
    "Total Liabilities Net Minority Interest": ["Liabilities"],
    "Stockholders Equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "Retained Earnings": ["RetainedEarningsAccumulatedDeficit"],
    "Long Term Debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "Accounts Receivable": ["AccountsReceivableNetCurrent"],
    "Inventory": ["InventoryNet"],
    "Accounts Payable": ["AccountsPayableCurrent"],
    "Net PPE": ["PropertyPlantAndEquipmentNet"],
    "Cash And Cash Equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
}
_INCOME = ["Total Revenue", "Cost Of Revenue", "Gross Profit", "Selling General And Administration",
           "EBIT", "Interest Expense", "Pretax Income", "Tax Provision", "Net Income"]
_CASH = ["Reconciled Depreciation", "Operating Cash Flow", "Capital Expenditure"]

_lock = threading.Lock()
_last_call = 0.0


def user_agent() -> str:
    contact = env("CONTACT").strip() or "https://github.com/shubhwade/telmus"
    return f"isoline/{__version__} ({contact})"


def _get_json(url: str) -> Any:
    """GET a SEC URL politely: declared User-Agent and a minimum spacing between calls."""
    global _last_call
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (fixed https hosts)
            return json.load(resp)
    except Exception as exc:
        raise ProviderUnavailableError(f"Could not reach SEC EDGAR ({exc})") from exc


def is_us_symbol(symbol: str) -> bool:
    """Plain US-style tickers only (AAPL, BRK-B). Exchange-suffixed ones are not on EDGAR."""
    return bool(re.fullmatch(r"[A-Za-z]{1,5}([.\-][A-Za-z])?", symbol.strip()))


def lookup_cik(symbol: str, fetch: Callable[[str], Any] = _get_json) -> tuple[int, str]:
    want = symbol.strip().upper().replace(".", "-")
    data = fetch(TICKERS_URL)
    for row in data.values():
        if str(row.get("ticker", "")).upper() == want:
            return int(row["cik_str"]), str(row.get("title", want))
    raise NoDataError(f"'{symbol}' is not an SEC-registered ticker")


def _annual_points(units: list[dict[str, Any]], flow: bool) -> dict[str, float]:
    """One value per fiscal year end from 10-K facts; the latest filing wins (restatements)."""
    best: dict[str, tuple[str, float]] = {}
    for p in units:
        if not str(p.get("form", "")).startswith("10-K") or p.get("val") is None:
            continue
        end = p.get("end")
        if not end:
            continue
        if flow:
            start = p.get("start")
            if not start:
                continue
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if not 350 <= days <= 380:
                continue
        filed = str(p.get("filed", ""))
        if end not in best or filed >= best[end][0]:
            best[end] = (filed, float(p["val"]))
    return {end: v for end, (_, v) in best.items()}


def _frame(facts: dict[str, Any], mapping: dict[str, list[str]], rows: list[str], flow: bool,
           years: int = 5) -> pd.DataFrame:
    gaap = facts.get("us-gaap", {})
    data: dict[str, dict[str, float]] = {}
    for label in rows:
        for concept in mapping[label]:
            units = gaap.get(concept, {}).get("units", {}).get("USD")
            if units:
                pts = _annual_points(units, flow)
                if pts:
                    data[label] = pts
                    break
    if not data:
        return pd.DataFrame()
    ends = sorted({e for pts in data.values() for e in pts}, reverse=True)[:years]
    df = pd.DataFrame(
        {pd.Timestamp(e): {lbl: pts.get(e) for lbl, pts in data.items()} for e in ends}
    )
    return df


def build_bundle(symbol: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a company-facts payload into the frames the engines already consume."""
    facts = payload.get("facts", {})
    income = _frame(facts, _FLOW, _INCOME, flow=True)
    cash = _frame(facts, _FLOW, _CASH, flow=True)
    balance = _frame(facts, _INSTANT, list(_INSTANT), flow=False)
    if income.empty and balance.empty and cash.empty:
        raise NoDataError(f"SEC EDGAR has no annual XBRL statements for '{symbol}'")
    if not income.empty and "Gross Profit" not in income.index and {
        "Total Revenue", "Cost Of Revenue"
    } <= set(income.index):
        income.loc["Gross Profit"] = income.loc["Total Revenue"] - income.loc["Cost Of Revenue"]
    shares = None
    dei = facts.get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {})
    pts = [p for v in dei.values() for p in v if p.get("val") is not None]
    if pts:
        shares = float(max(pts, key=lambda p: str(p.get("end", "")))["val"])
    info: dict[str, Any] = {
        "symbol": symbol.upper(),
        "longName": payload.get("entityName") or name,
        "currency": "USD",
    }
    if shares:
        info["sharesOutstanding"] = shares
    return {
        "info": info,
        "income_stmt": income,
        "balance_sheet": balance,
        "cashflow": cash,
        "fast_info": {},
        "source": "SEC EDGAR (annual 10-K XBRL facts)",
    }


def load_edgar(symbol: str, fetch: Callable[[str], Any] = _get_json) -> dict[str, Any]:
    if not is_us_symbol(symbol):
        raise NoDataError(f"'{symbol}' is not a US ticker; SEC EDGAR covers US filers only")
    cik, name = lookup_cik(symbol, fetch)
    payload = fetch(FACTS_URL.format(cik=cik))
    return build_bundle(symbol, name, payload)
