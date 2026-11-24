"""Multi-year history used by the report charts (oldest -> newest, up to four fiscal years).

Values are matched to fiscal periods by date, not by position, so a cash-flow
statement with a different number of years than the income statement cannot
shift a bar onto the wrong year. A missing value stays None (no bar), never 0.
"""

from __future__ import annotations

import typing

import pandas as pd

from telmus.core.labels import ALIASES, to_float
from telmus.core.result import HistoryResult


def _by_period(df: typing.Any, key: str) -> dict[pd.Timestamp, float | None]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    for name in ALIASES.get(key, [key]):
        if name in df.index:
            s = df.loc[name]
        elif name in df.columns:
            s = df[name]
        else:
            continue
        if isinstance(s, pd.DataFrame):
            s = s.iloc[0]
        out: dict[pd.Timestamp, float | None] = {}
        for period, value in s.items():
            try:
                out[pd.Timestamp(typing.cast(typing.Any, period))] = to_float(value)
            except (ValueError, TypeError):
                return {}
        return out
    return {}


def _frame(financials: dict[str, typing.Any], key: str) -> typing.Any:
    return financials.get(key)


class HistoryEngine:
    MAX_YEARS = 4

    def run(self, financials: dict[str, typing.Any]) -> HistoryResult | None:
        income = _frame(financials, "income_stmt")
        balance = _frame(financials, "balance_sheet")
        cashflow = _frame(financials, "cashflow")
        revenue = _by_period(income, "revenue")
        net_income = _by_period(income, "net_income")
        ebit = _by_period(income, "ebit")
        cfo = _by_period(cashflow, "cfo")
        capex = _by_period(cashflow, "capex")
        _ = balance  # reserved for future balance-sheet series

        periods = sorted({*revenue, *net_income, *cfo})[-self.MAX_YEARS :]
        if len(periods) < 2:
            return None

        def pick(d: dict[pd.Timestamp, float | None]) -> list[float | None]:
            return [d.get(p) for p in periods]

        fcf: list[float | None] = []
        for p in periods:
            c, x = cfo.get(p), capex.get(p)
            fcf.append(None if c is None or x is None else c - abs(x))
        margin: list[float | None] = []
        for p in periods:
            e, r = ebit.get(p), revenue.get(p)
            margin.append(None if e is None or not r else e / r)

        info = financials.get("info") or {}
        currency = info.get("financialCurrency") or info.get("currency") or ""
        return HistoryResult(
            years=[f"FY{p.year}" for p in periods],
            revenue=pick(revenue),
            net_income=pick(net_income),
            operating_cash_flow=pick(cfo),
            free_cash_flow=fcf,
            operating_margin=margin,
            currency=str(currency),
        )
