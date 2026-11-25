from __future__ import annotations

import logging
import typing

import numpy as np
import pandas as pd

from isoline.core.labels import at, divide, series, to_float
from isoline.core.result import GrowthResult

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


def _cagr(start: typing.Any, end: typing.Any, years: float) -> float | None:
    if start is None or end is None:
        return None
    try:
        start = float(start)
        end = float(end)
    except Exception:
        return None

    if start <= 0 or years <= 0:
        return None
    try:
        return float((end / start) ** (1.0 / years) - 1.0)
    except Exception:
        return None


def _get_series(df: pd.DataFrame, label: str) -> pd.Series | None:
    if label in df.index:
        return df.loc[label]
    if label in df.columns:
        return df[label]
    return None


class GrowthEngine:
    def run(self, financials: dict[str, typing.Any]) -> GrowthResult:
        income_stmt = financials.get("income_stmt")
        if income_stmt is None:
            income_stmt = pd.DataFrame()
        cashflow = financials.get("cashflow")
        if cashflow is None:
            cashflow = pd.DataFrame()
        info = financials.get("info") or {}

        revenue_cagr = self._revenue_cagr(income_stmt)
        pat_cagr = self._pat_cagr(income_stmt)
        margin_trend = self._margin_trend(income_stmt)
        fcf_yield = self._fcf_yield(cashflow, info)

        flag = None
        if revenue_cagr is not None and revenue_cagr < 0:
            flag = "negative revenue growth"
        elif fcf_yield is not None and fcf_yield < 0:
            flag = "negative free cash flow"

        return GrowthResult(
            revenue_cagr_3y=revenue_cagr,
            pat_cagr_3y=pat_cagr,
            margin_trend=margin_trend,
            fcf_yield=fcf_yield,
            flag=flag,
        )

    def _revenue_cagr(self, income_stmt: pd.DataFrame) -> float | None:
        """3-year CAGR: needs four annual revenue figures (t-3 .. t)."""
        revenue = series(income_stmt, "revenue")
        if revenue is None or len(revenue) < 4:
            logger.warning("Insufficient revenue history for CAGR")
            return None
        return _cagr(at(revenue, 3), at(revenue, 0), 3.0)

    def _pat_cagr(self, income_stmt: pd.DataFrame) -> float | None:
        net_income = series(income_stmt, "net_income")
        if net_income is None or len(net_income) < 4:
            logger.warning("Insufficient net income history for CAGR")
            return None
        return _cagr(at(net_income, 3), at(net_income, 0), 3.0)

    def _margin_trend(self, income_stmt: pd.DataFrame) -> str | None:
        """Operating-margin change over three years; None if any year is missing."""
        revenue = series(income_stmt, "revenue")
        operating_income = series(income_stmt, "ebit")
        if revenue is None or operating_income is None:
            logger.warning("Insufficient data for margin trend")
            return None
        margins = [divide(at(operating_income, i), at(revenue, i)) for i in range(3)]
        first, last = margins[2], margins[0]
        if first is None or last is None:
            logger.warning("Margin trend: operating margin unavailable for a required year")
            return None
        diff = last - first
        if diff > 0.02:
            return "improving"
        if diff < -0.02:
            return "declining"
        return "stable"

    def _fcf_yield(
        self, cashflow: pd.DataFrame, info: dict[str, typing.Any]
    ) -> float | None:
        """(Operating cash flow - |capex|) / market cap. yfinance reports capex as negative."""
        cfo = at(series(cashflow, "cfo"), 0)
        capex = at(series(cashflow, "capex"), 0)
        market_cap = to_float(info.get("marketCap"))
        if cfo is None or capex is None or market_cap is None or market_cap <= 0:
            logger.warning("Insufficient values for FCF yield")
            return None
        return divide(cfo - abs(capex), market_cap)
