"""Quality metrics: DuPont ROE decomposition, ROIC, free cash flow, accruals,
cash conversion cycle and share dilution.

Conventions (see FINANCIAL_METHODOLOGY.md):
* Flow items (net income, revenue, EBIT, CFO) are for the latest fiscal year (t).
* Balance-sheet denominators for returns use the AVERAGE of year t and t-1.
* Working-capital days use year-end balances and a 365-day year.
* Anything that cannot be computed from reported data is None, with a note.
  A missing line item is never assumed to be zero, and no tax rate is assumed.
"""

from __future__ import annotations

import typing

import pandas as pd

from isoline.core.labels import at, divide, is_financial_company, series
from isoline.core.result import QualityResult

DAYS = 365.0


def _frame(financials: dict[str, typing.Any], key: str) -> pd.DataFrame:
    value = financials.get(key)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _avg(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else (a + b) / 2


class QualityEngine:
    def run(self, financials: dict[str, typing.Any]) -> QualityResult:
        income = _frame(financials, "income_stmt")
        balance = _frame(financials, "balance_sheet")
        cashflow = _frame(financials, "cashflow")
        info = financials.get("info") or {}
        notes: list[str] = []

        revenue = at(series(income, "revenue"), 0)
        net_income = at(series(income, "net_income"), 0)
        avg_assets = _avg(*(at(series(balance, "total_assets"), i) for i in (0, 1)))
        avg_equity = _avg(*(at(series(balance, "equity"), i) for i in (0, 1)))
        if avg_equity is not None and avg_equity <= 0:
            notes.append("DuPont/ROE not meaningful: average shareholders' equity is not positive.")
            avg_equity = None

        net_margin = divide(net_income, revenue)
        asset_turnover = divide(revenue, avg_assets)
        equity_multiplier = divide(avg_assets, avg_equity)
        roe = divide(net_income, avg_equity)

        cfo = at(series(cashflow, "cfo"), 0)
        capex = at(series(cashflow, "capex"), 0)
        fcf = None if cfo is None or capex is None else cfo - abs(capex)
        fcf_to_ni = divide(fcf, net_income) if net_income is not None and net_income > 0 else None
        if net_income is not None and net_income <= 0:
            notes.append("FCF / net income not meaningful: net income is not positive.")
        accruals = divide(
            None if net_income is None or cfo is None else net_income - cfo, avg_assets
        )

        financial = is_financial_company(info)
        roic = None if financial else self._roic(income, balance, notes)
        dso = dio = dpo = ccc = None
        if financial:
            notes.append("ROIC and cash conversion cycle are not applicable to financial firms.")
        else:
            dso, dio, dpo, ccc = self._working_capital(income, balance, notes)

        shares = series(balance, "shares")
        now, prev = at(shares, 0), at(shares, 1)
        share_change = divide(None if now is None or prev is None else now - prev, prev)

        return QualityResult(
            net_margin=net_margin,
            asset_turnover=asset_turnover,
            equity_multiplier=equity_multiplier,
            roe=roe,
            roic=roic,
            fcf=fcf,
            fcf_margin=divide(fcf, revenue),
            fcf_to_net_income=fcf_to_ni,
            accruals_ratio=accruals,
            dso_days=dso,
            dio_days=dio,
            dpo_days=dpo,
            cash_conversion_cycle_days=ccc,
            share_count_change=share_change,
            notes=notes,
        )

    def _invested_capital(self, balance: pd.DataFrame, i: int) -> float | None:
        """Shareholders' equity + total debt - cash, at the end of period i."""
        equity = at(series(balance, "equity"), i)
        debt = at(series(balance, "total_debt"), i)
        cash = at(series(balance, "cash"), i)
        if equity is None or debt is None or cash is None:
            return None
        return equity + debt - cash

    def _roic(self, income: pd.DataFrame, balance: pd.DataFrame, notes: list[str]) -> float | None:
        ebit = at(series(income, "ebit"), 0)
        tax = at(series(income, "tax"), 0)
        pretax = at(series(income, "pretax"), 0)
        tax_rate = divide(tax, pretax) if pretax is not None and pretax > 0 else None
        if tax_rate is None or not 0 <= tax_rate <= 1:
            notes.append("ROIC not reported: effective tax rate unavailable (no rate is assumed).")
            return None
        capital = _avg(self._invested_capital(balance, 0), self._invested_capital(balance, 1))
        if ebit is None or capital is None or capital <= 0:
            notes.append("ROIC not reported: EBIT or invested capital unavailable or not positive.")
            return None
        return divide(ebit * (1 - tax_rate), capital)

    def _working_capital(
        self, income: pd.DataFrame, balance: pd.DataFrame, notes: list[str]
    ) -> tuple[float | None, float | None, float | None, float | None]:
        revenue = at(series(income, "revenue"), 0)
        cogs = at(series(income, "cogs"), 0)
        receivables = at(series(balance, "receivables"), 0)
        inventory = at(series(balance, "inventory"), 0)
        payables = at(series(balance, "payables"), 0)
        dso = divide(None if receivables is None else receivables * DAYS, revenue)
        dio = divide(None if inventory is None else inventory * DAYS, cogs)
        dpo = divide(None if payables is None else payables * DAYS, cogs)
        if None in (dso, dio, dpo):
            notes.append(
                "Cash conversion cycle not reported: receivables, inventory, payables, revenue "
                "or cost of revenue is missing (a missing inventory line is not assumed to be zero)."
            )
            return dso, dio, dpo, None
        return dso, dio, dpo, dso + dio - dpo  # type: ignore[operator]
