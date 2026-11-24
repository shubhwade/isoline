"""Canonical financial-statement line items and tolerant lookup.

yfinance has renamed statement rows across releases (``Total Liab`` became
``Total Liabilities Net Minority Interest``, ``Capital Expenditures`` became
``Capital Expenditure`` ...). Every engine looks values up through this module
so a rename is fixed in one place.

A value that cannot be found is ``None``. It is never replaced by zero.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ALIASES: dict[str, list[str]] = {
    "revenue": ["Total Revenue", "Operating Revenue", "TotalRevenue", "Revenue"],
    "gross_profit": ["Gross Profit", "GrossProfit"],
    "cogs": ["Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Revenue"],
    "net_income": [
        "Net Income",
        "Net Income Common Stockholders",
        "NetIncome",
        "Net Income From Continuing Operation Net Minority Interest",
    ],
    "sga": [
        "Selling General And Administration",
        "Selling General Administrative",
        "Selling General and Administrative",
    ],
    "depreciation": [
        "Reconciled Depreciation",
        "Depreciation And Amortization",
        "Depreciation Amortization Depletion",
        "Depreciation",
    ],
    "ebit": ["EBIT", "Ebit", "Operating Income", "OperatingIncome"],
    "ebitda": ["EBITDA", "Ebitda"],
    "interest_expense": [
        "Interest Expense",
        "Interest Expense Non Operating",
        "InterestExpense",
    ],
    "total_assets": ["Total Assets", "TotalAssets"],
    "current_assets": [
        "Current Assets",
        "Total Current Assets",
        "TotalCurrentAssets",
        "CurrentAssets",
    ],
    "current_liabilities": [
        "Current Liabilities",
        "Total Current Liabilities",
        "TotalCurrentLiabilities",
        "CurrentLiabilities",
    ],
    "total_liabilities": [
        "Total Liabilities Net Minority Interest",
        "Total Liab",
        "Total Liabilities",
        "TotalLiabilities",
    ],
    "equity": [
        "Stockholders Equity",
        "Total Stockholder Equity",
        "Common Stock Equity",
        "Total Equity Gross Minority Interest",
        "Total Equity",
        "StockholdersEquity",
    ],
    "retained_earnings": ["Retained Earnings", "RetainedEarnings"],
    "long_term_debt": [
        "Long Term Debt",
        "Long Term Debt And Capital Lease Obligation",
        "LongTermDebt",
    ],
    "total_debt": ["Total Debt"],
    "receivables": ["Accounts Receivable", "Receivables", "Net Receivables"],
    "ppe": ["Net PPE", "Property Plant Equipment Net", "Property Plant And Equipment Net"],
    "cash": ["Cash And Cash Equivalents", "Cash", "Cash Cash Equivalents And Short Term Investments"],
    "shares": ["Ordinary Shares Number", "Share Issued"],
    "cfo": [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
        "Total Cash From Operating Activities",
        "Cash Flow From Operating Activities",
        "CashFlowFromOperatingActivities",
    ],
    "capex": ["Capital Expenditure", "Capital Expenditures"],
}


def to_float(value: Any) -> float | None:
    """Convert to a finite float, or None for missing / NaN / inf / non-numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _periods_newest_first(s: pd.Series) -> list[float | None]:
    try:
        order = pd.to_datetime(s.index).argsort()[::-1]
        s = s.iloc[list(order)]
    except (ValueError, TypeError):
        logger.debug("Statement periods are not dates; keeping the given order")
    return [to_float(v) for v in s.tolist()]


def series(df: Any, key: str) -> list[float | None] | None:
    """Values for canonical item ``key``, newest period first.

    Accepts yfinance orientation (items as rows) and the transposed one
    (items as columns). Returns None if no alias exists or all values are missing.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for name in ALIASES.get(key, [key]):
        if name in df.index:
            s = df.loc[name]
        elif name in df.columns:
            s = df[name]
        else:
            continue
        if isinstance(s, pd.DataFrame):
            s = s.iloc[0]
        values = _periods_newest_first(s)
        if any(v is not None for v in values):
            return values
    return None


def at(values: list[float | None] | None, i: int = 0) -> float | None:
    if values is None or i >= len(values):
        return None
    return values[i]


def first_of(dfs: list[Any], key: str) -> list[float | None] | None:
    """Look ``key`` up in several statements and return the first hit."""
    for df in dfs:
        found = series(df, key)
        if found is not None:
            return found
    return None


def divide(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    out = num / den
    return out if math.isfinite(out) else None


def is_financial_company(info: dict[str, Any] | None) -> bool:
    """Banks / insurers: working capital, EBIT and receivables models do not apply."""
    sector = str((info or {}).get("sector") or "").lower()
    return "financial" in sector


def get_series_fallback(df: Any, labels: list[str]) -> pd.Series | None:
    """First raw row/column of ``df`` matching any of ``labels`` (for exporters)."""
    if df is None or not isinstance(df, pd.DataFrame):
        return None
    for label in labels:
        if label in df.index:
            return df.loc[label]
        if label in df.columns:
            return df[label]
    return None
