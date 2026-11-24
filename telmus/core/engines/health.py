"""Balance-sheet health: Piotroski F-score, Altman Z''-score and basic ratios.

Rules followed throughout:
* A missing input gives ``None`` ("n/a"), never ``0`` and never ``False``.
* A score is only reported when every component needed for it is available.
* These are screening statistics, not investment advice.

References
----------
Piotroski, J. (2000). Value Investing: The Use of Historical Financial
Statement Information to Separate Winners from Losers. J. Accounting Research 38.
Altman, E. (1968, 1983, 1995). Z''-score for non-manufacturers / emerging markets.
"""

from __future__ import annotations

import logging
import typing

import pandas as pd

from telmus.core.labels import at, divide, first_of, is_financial_company, series
from telmus.core.result import HealthResult

logger = logging.getLogger(__name__)

PIOTROSKI_SIGNALS = (
    "ROA Positive",
    "CFO Positive",
    "ROA Improving",
    "Low Accruals",
    "Leverage Falling",
    "Liquidity Rising",
    "No Dilution",
    "Gross Margin Rising",
    "Asset Turnover Rising",
)

# Altman Z'' zones (no constant term): > 2.60 safe, 1.10 - 2.60 grey, < 1.10 distress.
ALTMAN_SAFE = 2.6
ALTMAN_DISTRESS = 1.1


def _frame(financials: dict[str, typing.Any], key: str) -> pd.DataFrame:
    value = financials.get(key)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _gt(a: float | None, b: float | None) -> bool | None:
    return None if a is None or b is None else a > b


class HealthEngine:
    def run(self, financials: dict[str, typing.Any]) -> HealthResult:
        income = _frame(financials, "income_stmt")
        balance = _frame(financials, "balance_sheet")
        cashflow = _frame(financials, "cashflow")
        info = financials.get("info") or {}
        notes: list[str] = []

        f_score, signals, missing = self._compute_piotroski(income, balance, cashflow)
        if missing:
            notes.append(
                "Piotroski F-score not reported: missing data for "
                + ", ".join(missing)
                + "."
            )

        altman_z: float | None = None
        if is_financial_company(info):
            notes.append(
                "Altman Z'' is not applicable to banks, insurers and other financial firms."
            )
        else:
            altman_z = self._compute_altman_z(income, balance)
            if altman_z is None:
                notes.append("Altman Z'' not reported: required inputs are missing.")

        health_flag = None
        if f_score is not None and f_score < 5:
            health_flag = "weak fundamentals"
        elif altman_z is not None and altman_z < ALTMAN_DISTRESS:
            health_flag = "distress risk"

        return HealthResult(
            piotroski_f=f_score,
            piotroski_signals=signals,
            altman_z=altman_z,
            debt_to_equity=self._compute_debt_to_equity(balance),
            current_ratio=self._compute_current_ratio(balance),
            interest_coverage=self._compute_interest_coverage(income),
            flag=health_flag,
            notes=notes,
        )

    # ------------------------------------------------------------------ Piotroski
    def _compute_piotroski(
        self, income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame
    ) -> tuple[int | None, dict[str, int], list[str]]:
        raw: dict[str, bool | None] = {
            "ROA Positive": self._roa_positive(income, balance),
            "CFO Positive": self._cfo_positive(cashflow),
            "ROA Improving": self._roa_increasing(income, balance),
            "Low Accruals": self._accruals(income, cashflow),
            "Leverage Falling": self._leverage_decreasing(balance),
            "Liquidity Rising": self._liquidity_increasing(balance),
            "No Dilution": self._no_dilution(balance),
            "Gross Margin Rising": self._gross_margin_increasing(income),
            "Asset Turnover Rising": self._asset_turnover_increasing(income, balance),
        }
        signals = {k: int(v) for k, v in raw.items() if v is not None}
        missing = [k for k, v in raw.items() if v is None]
        score = sum(signals.values()) if not missing else None
        return score, signals, missing

    def _roa(self, income: pd.DataFrame, balance: pd.DataFrame, i: int) -> float | None:
        """Net income of period i over total assets at the START of period i."""
        return divide(
            at(series(income, "net_income"), i), at(series(balance, "total_assets"), i + 1)
        )

    def _roa_positive(self, income: pd.DataFrame, balance: pd.DataFrame) -> bool | None:
        roa = self._roa(income, balance, 0)
        return None if roa is None else roa > 0

    def _cfo_positive(self, cashflow: pd.DataFrame) -> bool | None:
        cfo = at(series(cashflow, "cfo"), 0)
        return None if cfo is None else cfo > 0

    def _roa_increasing(self, income: pd.DataFrame, balance: pd.DataFrame) -> bool | None:
        return _gt(self._roa(income, balance, 0), self._roa(income, balance, 1))

    def _accruals(self, income: pd.DataFrame, cashflow: pd.DataFrame) -> bool | None:
        """Signal = 1 when operating cash flow exceeds net income (CFO/TA > ROA, same TA)."""
        ni = at(series(income, "net_income"), 0)
        cfo = at(series(cashflow, "cfo"), 0)
        return _gt(cfo, ni)

    def _leverage_ratio(self, balance: pd.DataFrame, i: int) -> float | None:
        """Long-term debt / average total assets for period i."""
        assets = series(balance, "total_assets")
        ltd = series(balance, "long_term_debt")
        debt_now = at(ltd, i)
        if debt_now is None and at(series(balance, "total_debt"), i) == 0:
            debt_now = 0.0  # debt-free company: an explicit zero, not a missing value
        a_now, a_prev = at(assets, i), at(assets, i + 1)
        if debt_now is None or a_now is None or a_prev is None:
            return None
        return divide(debt_now, (a_now + a_prev) / 2)

    def _leverage_decreasing(self, balance: pd.DataFrame) -> bool | None:
        now, prev = self._leverage_ratio(balance, 0), self._leverage_ratio(balance, 1)
        return None if now is None or prev is None else now < prev

    def _current_ratio_at(self, balance: pd.DataFrame, i: int) -> float | None:
        return divide(
            at(series(balance, "current_assets"), i),
            at(series(balance, "current_liabilities"), i),
        )

    def _liquidity_increasing(self, balance: pd.DataFrame) -> bool | None:
        return _gt(self._current_ratio_at(balance, 0), self._current_ratio_at(balance, 1))

    def _no_dilution(self, balance: pd.DataFrame) -> bool | None:
        """No increase in shares outstanding (a share COUNT, not the par-value amount)."""
        shares = series(balance, "shares")
        now, prev = at(shares, 0), at(shares, 1)
        return None if now is None or prev is None else now <= prev

    def _gross_margin_at(self, income: pd.DataFrame, i: int) -> float | None:
        revenue = at(series(income, "revenue"), i)
        gross = at(series(income, "gross_profit"), i)
        if gross is None:
            cogs = at(series(income, "cogs"), i)
            gross = None if revenue is None or cogs is None else revenue - cogs
        return divide(gross, revenue)

    def _gross_margin_increasing(self, income: pd.DataFrame) -> bool | None:
        return _gt(self._gross_margin_at(income, 0), self._gross_margin_at(income, 1))

    def _turnover(self, income: pd.DataFrame, balance: pd.DataFrame, i: int) -> float | None:
        return divide(
            at(series(income, "revenue"), i), at(series(balance, "total_assets"), i + 1)
        )

    def _asset_turnover_increasing(
        self, income: pd.DataFrame, balance: pd.DataFrame
    ) -> bool | None:
        return _gt(self._turnover(income, balance, 0), self._turnover(income, balance, 1))

    # --------------------------------------------------------------------- Altman
    def _compute_altman_z(self, income: pd.DataFrame, balance: pd.DataFrame) -> float | None:
        """Altman Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4.

        X1 working capital / total assets, X2 retained earnings / total assets,
        X3 EBIT / total assets, X4 BOOK equity / total liabilities.
        """
        assets = at(series(balance, "total_assets"), 0)
        ca = at(series(balance, "current_assets"), 0)
        cl = at(series(balance, "current_liabilities"), 0)
        re = at(series(balance, "retained_earnings"), 0)
        ebit = at(series(income, "ebit"), 0)
        equity = at(series(balance, "equity"), 0)
        liabilities = at(series(balance, "total_liabilities"), 0)
        if None in (assets, ca, cl, re, ebit, equity, liabilities):
            logger.warning("Altman Z'' missing required inputs")
            return None
        x1 = divide(ca - cl, assets)  # type: ignore[operator]
        x2 = divide(re, assets)
        x3 = divide(ebit, assets)
        x4 = divide(equity, liabilities)
        if None in (x1, x2, x3, x4):
            return None
        return 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4  # type: ignore[operator]

    # --------------------------------------------------------------------- Ratios
    def _compute_debt_to_equity(self, balance: pd.DataFrame) -> float | None:
        """Total liabilities / shareholders' equity. Not meaningful if equity <= 0."""
        liabilities = at(series(balance, "total_liabilities"), 0)
        equity = at(series(balance, "equity"), 0)
        if liabilities is None or equity is None or equity <= 0:
            return None
        return divide(liabilities, equity)

    def _compute_current_ratio(self, balance: pd.DataFrame) -> float | None:
        return self._current_ratio_at(balance, 0)

    def _compute_interest_coverage(self, income: pd.DataFrame) -> float | None:
        """EBIT / |interest expense|. EBITDA is deliberately NOT used as a stand-in."""
        ebit = at(series(income, "ebit"), 0)
        interest = at(series(income, "interest_expense"), 0)
        if ebit is None or interest is None:
            return None
        return divide(ebit, abs(interest))


__all__ = ["PIOTROSKI_SIGNALS", "HealthEngine", "first_of"]
