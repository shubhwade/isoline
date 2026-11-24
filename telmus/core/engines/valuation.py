from __future__ import annotations

import logging
import typing

import numpy as np
import pandas as pd

from telmus.core.labels import at, series
from telmus.core.result import ValuationResult

logger = logging.getLogger(__name__)


def _safe_value(value: typing.Any) -> float | None:
    if value is None:
        return None
    try:
        value_float = float(value)
    except (TypeError, ValueError, Exception):
        return None
    if np.isnan(value_float):
        return None
    return value_float


def _safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _get_series(df: pd.DataFrame, label: str) -> pd.Series | None:
    if label in df.index:
        return df.loc[label]
    if label in df.columns:
        return df[label]
    return None


class ValuationEngine:
    def run(self, financials: dict[str, typing.Any]) -> ValuationResult:
        info = financials.get("info") or {}
        balance_sheet = financials.get("balance_sheet")
        if balance_sheet is None:
            balance_sheet = pd.DataFrame()
        income_stmt = financials.get("income_stmt")
        if income_stmt is None:
            income_stmt = pd.DataFrame()
        market_cap = _safe_value(info.get("marketCap"))

        net_income = self._net_income_ttm(income_stmt)
        book_value = self._book_value(balance_sheet)
        ebitda = self._ebitda(income_stmt)
        total_debt = self._total_debt(balance_sheet)
        cash = self._cash(balance_sheet)

        pe_ratio = _safe_value(info.get("trailingPE"))
        if pe_ratio is None:
            pe_ratio = _safe_divide(market_cap, net_income)

        pb_ratio = _safe_value(info.get("priceToBook"))
        if pb_ratio is None:
            pb_ratio = _safe_divide(market_cap, book_value)

        ev_ebitda = _safe_value(info.get("enterpriseToEbitda"))
        if ev_ebitda is None:
            if (
                market_cap is not None
                and total_debt is not None
                and cash is not None
                and ebitda is not None
            ):
                ev = float(market_cap) + float(total_debt) - float(cash)
                ev_ebitda = _safe_divide(ev, ebitda)

        # Peer comparison is not implemented: yfinance exposes no peer list, so the
        # previous "fair" default was a fabricated answer. Report "n/a" instead.
        vs_sector = None
        flag = None

        if pe_ratio is not None and pe_ratio < 0:
            flag = "negative earnings"
        if ev_ebitda is not None and ev_ebitda < 0 and flag is None:
            flag = "negative ebitda"
        return ValuationResult(
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            ev_ebitda=ev_ebitda,
            vs_sector=vs_sector,
            flag=flag,
        )

    def _net_income_ttm(self, income_stmt: pd.DataFrame) -> float | None:
        return at(series(income_stmt, "net_income"), 0)

    def _book_value(self, balance_sheet: pd.DataFrame) -> float | None:
        return at(series(balance_sheet, "equity"), 0)

    def _ebitda(self, income_stmt: pd.DataFrame) -> float | None:
        return at(series(income_stmt, "ebitda"), 0)

    def _total_debt(self, balance_sheet: pd.DataFrame) -> float | None:
        total = at(series(balance_sheet, "total_debt"), 0)
        if total is not None:
            return total
        return at(series(balance_sheet, "long_term_debt"), 0)

    def _cash(self, balance_sheet: pd.DataFrame) -> float | None:
        return at(series(balance_sheet, "cash"), 0)

