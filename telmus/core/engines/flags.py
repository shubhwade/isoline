"""Earnings-quality and cash-flow red flags (Beneish M-score, leverage, FCF).

Beneish, M. (1999). The Detection of Earnings Manipulation.
Financial Analysts Journal 55(5), 24-36.

A missing input gives ``None``. It is never replaced by zero.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from telmus.core.labels import at, divide, first_of, is_financial_company, series
from telmus.core.result import FlagsResult, RedFlag

logger = logging.getLogger(__name__)

# Beneish's 8-variable model. -1.78 is the paper's balanced cut-off; -2.22 is more
# sensitive (accepts more false positives). Telmus uses the more sensitive one.
BENEISH_THRESHOLD = -2.22


def _frame(financials: dict[str, object], key: str) -> pd.DataFrame:
    value = financials.get(key)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _ratio_of_ratios(a_num, a_den, b_num, b_den) -> float | None:
    a, b = divide(a_num, a_den), divide(b_num, b_den)
    return divide(a, b)


class FlagsEngine:
    def run(self, financials: dict[str, Any]) -> FlagsResult:
        income = _frame(financials, "income_stmt")
        balance = _frame(financials, "balance_sheet")
        cashflow = _frame(financials, "cashflow")
        info = financials.get("info") or {}
        notes: list[str] = []

        beneish_m: float | None = None
        if is_financial_company(info):
            notes.append("Beneish M-score is not applicable to financial firms.")
        else:
            beneish_m = self._beneish_m_score(income, balance, cashflow)
            if beneish_m is None:
                notes.append("Beneish M-score not reported: required inputs are missing.")

        red_flags: list[RedFlag] = []
        if beneish_m is not None and beneish_m > BENEISH_THRESHOLD:
            red_flags.append(RedFlag(type="beneish_m", value=round(beneish_m, 2), severity="high"))

        equity = at(series(balance, "equity"), 0)
        if equity is not None and equity < 0:
            red_flags.append(RedFlag(type="negative_equity", value=round(equity, 2), severity="high"))

        de_ratio = self._de_ratio(balance)
        if de_ratio is not None and de_ratio > 2.0:
            red_flags.append(RedFlag(type="de_ratio", value=round(de_ratio, 2), severity="medium"))

        negative_fcf_count = self._negative_fcf_years(cashflow)
        if negative_fcf_count >= 2:
            red_flags.append(
                RedFlag(type="negative_fcf", value=negative_fcf_count, severity="medium")
            )

        severities = {f.severity for f in red_flags}
        highest = "high" if "high" in severities else "medium" if "medium" in severities else "low"
        return FlagsResult(
            red_flags=red_flags, beneish_m=beneish_m, highest_concern=highest, notes=notes
        )

    def _beneish_m_score(
        self, income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
    ) -> float | None:
        """Eight-variable Beneish M-score; None unless every input exists for t and t-1."""
        components = self.beneish_components(income, balance, cashflow)
        if components is None:
            return None
        c = components
        return (
            -4.84
            + 0.920 * c["DSRI"]
            + 0.528 * c["GMI"]
            + 0.404 * c["AQI"]
            + 0.892 * c["SGI"]
            + 0.115 * c["DEPI"]
            - 0.172 * c["SGAI"]
            + 4.679 * c["TATA"]
            - 0.327 * c["LVGI"]
        )

    def beneish_components(
        self, income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
    ) -> dict[str, float] | None:
        rev = series(income, "revenue")
        cogs = series(income, "cogs")
        gp = series(income, "gross_profit")
        ni = at(series(income, "net_income"), 0)
        sga = series(income, "sga")
        dep = first_of([income, cashflow], "depreciation")
        rec = series(balance, "receivables")
        ppe = series(balance, "ppe")
        ta = series(balance, "total_assets")
        ca = series(balance, "current_assets")
        cl = series(balance, "current_liabilities")
        ltd = series(balance, "long_term_debt")
        cfo = at(series(cashflow, "cfo"), 0)

        def gross_margin(i: int) -> float | None:
            r = at(rev, i)
            g = at(gp, i)
            if g is None and r is not None and at(cogs, i) is not None:
                g = r - at(cogs, i)  # type: ignore[operator]
            return divide(g, r)

        def aq(i: int) -> float | None:
            c, p, t = at(ca, i), at(ppe, i), at(ta, i)
            if c is None or p is None or t is None:
                return None
            return divide(t - c - p, t)

        def dep_rate(i: int) -> float | None:
            d, p = at(dep, i), at(ppe, i)
            if d is None or p is None:
                return None
            return divide(abs(d), abs(d) + p)

        def lev(i: int) -> float | None:
            l_, d, t = at(cl, i), at(ltd, i), at(ta, i)
            if l_ is None or d is None or t is None:
                return None
            return divide(l_ + d, t)

        gm0, gm1 = gross_margin(0), gross_margin(1)
        dep0, dep1 = dep_rate(0), dep_rate(1)
        aq0, aq1 = aq(0), aq(1)
        lev0, lev1 = lev(0), lev(1)
        parts = {
            "DSRI": _ratio_of_ratios(at(rec, 0), at(rev, 0), at(rec, 1), at(rev, 1)),
            "GMI": divide(gm1, gm0),
            "AQI": divide(aq0, aq1),
            "SGI": divide(at(rev, 0), at(rev, 1)),
            "DEPI": divide(dep1, dep0),
            "SGAI": _ratio_of_ratios(at(sga, 0), at(rev, 0), at(sga, 1), at(rev, 1)),
            "TATA": divide(None if ni is None or cfo is None else ni - cfo, at(ta, 0)),
            "LVGI": divide(lev0, lev1),
        }
        missing = [k for k, v in parts.items() if v is None]
        if missing:
            logger.warning("Beneish M-score missing components: %s", ", ".join(missing))
            return None
        return {k: float(v) for k, v in parts.items()}  # type: ignore[arg-type]

    def _de_ratio(self, balance: pd.DataFrame) -> float | None:
        liabilities = at(series(balance, "total_liabilities"), 0)
        equity = at(series(balance, "equity"), 0)
        if liabilities is None or equity is None or equity <= 0:
            return None
        return divide(liabilities, equity)

    def _negative_fcf_years(self, cashflow: pd.DataFrame) -> int:
        """Count of the last three years with FCF < 0 (FCF = CFO - |capex|)."""
        cfo = series(cashflow, "cfo")
        capex = series(cashflow, "capex")
        if cfo is None or capex is None:
            logger.warning("Negative-FCF check missing operating cash flow or capex")
            return 0
        count = 0
        for i in range(min(3, len(cfo), len(capex))):
            c, x = cfo[i], capex[i]
            if c is None or x is None:
                continue
            if c - abs(x) < 0:  # capex is reported negative by yfinance, positive elsewhere
                count += 1
        return count
