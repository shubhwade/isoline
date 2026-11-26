"""Income statement, balance sheet and cash-flow statement, laid out for presentation.

Every value comes straight from the provider's statements, matched to its fiscal
period by date. Nothing is estimated or back-filled: a line the company did not
report is ``None`` (shown as n/a), and a line with no values at all is left out.
Two lines are arithmetic on reported figures and are marked ``computed``: free cash
flow (when the provider has no such row) and total liabilities and equity.

Sign convention (as in published statements): costs and expenses are shown in
parentheses; cash-flow lines keep the provider's sign (outflows negative).
"""

from __future__ import annotations

import typing

import pandas as pd

from isoline.core.labels import ALIASES, to_float
from isoline.core.result import StatementLine, StatementsResult

# (key, label, row names to try, kind, display sign, per-share, group)
# kind: item | subtotal | total | memo.  A name starting with "@" expands to labels.ALIASES.
Spec = tuple[str, str, list[str], str, int, bool, str]

INCOME: list[Spec] = [
    ("revenue", "Revenue", ["@revenue"], "subtotal", 1, False, ""),
    ("cogs", "Cost of revenue", ["@cogs"], "item", -1, False, ""),
    ("gross_profit", "Gross profit", ["@gross_profit"], "subtotal", 1, False, ""),
    ("rnd", "Research and development", ["Research And Development", "Research Development"], "item", -1, False, ""),
    ("sga", "Selling, general and administrative", ["@sga"], "item", -1, False, ""),
    ("operating_income", "Operating income", ["Operating Income", "OperatingIncome", "EBIT", "Ebit"], "subtotal", 1, False, ""),
    ("interest_expense", "Interest expense", ["@interest_expense"], "item", -1, False, ""),
    ("pretax", "Income before tax", ["@pretax"], "subtotal", 1, False, ""),
    ("tax", "Income tax expense", ["@tax"], "item", -1, False, ""),
    ("net_income", "Net income", ["@net_income"], "total", 1, False, ""),
    ("ebitda", "EBITDA", ["@ebitda"], "memo", 1, False, "Memo"),
    ("depreciation", "Depreciation and amortisation", ["@depreciation"], "memo", 1, False, "Memo"),
    ("eps_diluted", "Diluted EPS", ["Diluted EPS", "DilutedEPS"], "memo", 1, True, "Memo"),
    ("eps_basic", "Basic EPS", ["Basic EPS", "BasicEPS"], "memo", 1, True, "Memo"),
]

BALANCE: list[Spec] = [
    ("cash", "Cash and cash equivalents", ["Cash And Cash Equivalents", "Cash"], "item", 1, False, "Assets"),
    ("short_investments", "Short-term investments", ["Other Short Term Investments", "Short Term Investments"], "item", 1, False, "Assets"),
    ("receivables", "Accounts receivable", ["@receivables"], "item", 1, False, "Assets"),
    ("inventory", "Inventory", ["@inventory"], "item", 1, False, "Assets"),
    ("current_assets", "Total current assets", ["@current_assets"], "subtotal", 1, False, "Assets"),
    ("ppe", "Property, plant and equipment, net", ["@ppe"], "item", 1, False, "Assets"),
    ("goodwill", "Goodwill and intangible assets", ["Goodwill And Other Intangible Assets", "Goodwill"], "item", 1, False, "Assets"),
    ("total_assets", "Total assets", ["@total_assets"], "total", 1, False, "Assets"),
    ("payables", "Accounts payable", ["@payables"], "item", 1, False, "Liabilities"),
    ("current_liabilities", "Total current liabilities", ["@current_liabilities"], "subtotal", 1, False, "Liabilities"),
    ("long_term_debt", "Long-term debt", ["@long_term_debt"], "item", 1, False, "Liabilities"),
    ("total_liabilities", "Total liabilities", ["@total_liabilities"], "subtotal", 1, False, "Liabilities"),
    ("retained_earnings", "Retained earnings", ["@retained_earnings"], "item", 1, False, "Equity"),
    ("equity", "Total shareholders' equity", ["@equity"], "subtotal", 1, False, "Equity"),
    ("equity_incl_minority", "Total equity incl. minority interest", ["Total Equity Gross Minority Interest"], "item", 1, False, "Equity"),
    ("total_debt", "Total debt", ["@total_debt"], "memo", 1, False, "Memo"),
]

CASHFLOW: list[Spec] = [
    ("cf_net_income", "Net income", ["Net Income From Continuing Operations", "@net_income"], "item", 1, False, "Operating activities"),
    ("cf_depreciation", "Depreciation and amortisation", ["Depreciation And Amortization", "Depreciation Amortization Depletion", "@depreciation"], "item", 1, False, "Operating activities"),
    ("working_capital", "Change in working capital", ["Change In Working Capital"], "item", 1, False, "Operating activities"),
    ("cfo", "Cash from operating activities", ["@cfo"], "subtotal", 1, False, "Operating activities"),
    ("capex", "Capital expenditure", ["@capex"], "item", 1, False, "Investing activities"),
    ("cfi", "Cash from investing activities", ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"], "subtotal", 1, False, "Investing activities"),
    ("dividends", "Dividends paid", ["Cash Dividends Paid", "Common Stock Dividend Paid"], "item", 1, False, "Financing activities"),
    ("buybacks", "Share repurchases", ["Repurchase Of Capital Stock", "Common Stock Payments"], "item", 1, False, "Financing activities"),
    ("cff", "Cash from financing activities", ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"], "subtotal", 1, False, "Financing activities"),
    ("fcf", "Free cash flow", ["Free Cash Flow"], "total", 1, False, "Free cash flow"),
]

MAX_YEARS = 4
# Always cash outflows. Providers disagree on their sign (older yfinance reports capex as a
# positive number), so they are normalised to negative, as published cash-flow statements show them.
OUTFLOWS = {"capex", "dividends", "buybacks"}


def _names(spec_names: list[str]) -> list[str]:
    out: list[str] = []
    for n in spec_names:
        out.extend(ALIASES.get(n[1:], []) if n.startswith("@") else [n])
    return out


def _row(df: typing.Any, names: list[str]) -> dict[pd.Timestamp, float | None]:
    """First matching row with at least one value, keyed by period end date."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    for name in names:
        if name in df.index:
            s = df.loc[name]
        elif name in df.columns:
            s = df[name]
        else:
            continue
        if isinstance(s, pd.DataFrame):
            s = s.iloc[0]
        out: dict[pd.Timestamp, float | None] = {}
        try:
            for period, value in s.items():
                out[pd.Timestamp(typing.cast(typing.Any, period)).normalize()] = to_float(value)
        except (ValueError, TypeError):
            continue
        if any(v is not None for v in out.values()):
            return out
    return {}


def _dates(labels: typing.Iterable[typing.Any]) -> list[pd.Timestamp]:
    """Labels as period-end dates (newest first), or [] if they are not all dates."""
    try:
        return sorted({pd.Timestamp(c).normalize() for c in labels}, reverse=True)
    except (ValueError, TypeError):
        return []


def _periods(*frames: typing.Any) -> list[pd.Timestamp]:
    """Fiscal periods, income statement first. Accepts dates as columns (yfinance) or as rows."""
    for df in frames:
        if isinstance(df, pd.DataFrame) and not df.empty:
            dates = _dates(df.columns) or _dates(df.index)
            if dates:
                return dates
    return []


def _build(df: typing.Any, specs: list[Spec], periods: list[pd.Timestamp]) -> list[StatementLine]:
    lines = []
    for key, label, names, kind, sign, per_share, group in specs:
        row = _row(df, _names(names))
        values = [row.get(p) for p in periods]
        if key in OUTFLOWS:
            values = [None if v is None else -abs(v) for v in values]
        if any(v is not None for v in values):
            lines.append(StatementLine(label, values, kind, key, group, sign, per_share))
    return lines


def _find(lines: list[StatementLine], key: str) -> StatementLine | None:
    return next((ln for ln in lines if ln.key == key), None)


class StatementsEngine:
    def run(self, financials: dict[str, typing.Any]) -> StatementsResult | None:
        income = financials.get("income_stmt")
        balance = financials.get("balance_sheet")
        cashflow = financials.get("cashflow")
        candidates = _periods(income, balance, cashflow)
        if not candidates:
            return None

        # Keep the newest periods that actually carry data in at least one statement.
        def has_data(p: pd.Timestamp) -> bool:
            for df, specs in ((income, INCOME), (balance, BALANCE), (cashflow, CASHFLOW)):
                for _, _, names, _, _, _, _ in specs:
                    if _row(df, _names(names)).get(p) is not None:
                        return True
            return False

        periods = [p for p in candidates if has_data(p)][:MAX_YEARS]
        if not periods:
            return None

        inc = _build(income, INCOME, periods)
        bal = _build(balance, BALANCE, periods)
        cfs = _build(cashflow, CASHFLOW, periods)

        # Free cash flow = operating cash flow - |capex|, only where both are reported.
        if _find(cfs, "fcf") is None:
            cfo, capex = _find(cfs, "cfo"), _find(cfs, "capex")
            if cfo and capex:
                fcf = [None if c is None or x is None else c - abs(x) for c, x in zip(cfo.values, capex.values, strict=True)]
                if any(v is not None for v in fcf):
                    cfs.append(StatementLine("Free cash flow", fcf, "total", "fcf", "Free cash flow", computed=True))

        # Total liabilities and equity, only where both components are reported.
        liab = _find(bal, "total_liabilities")
        eq = _find(bal, "equity_incl_minority") or _find(bal, "equity")
        if liab and eq:
            tle = [None if a is None or b is None else a + b for a, b in zip(liab.values, eq.values, strict=True)]
            if any(v is not None for v in tle):
                line = StatementLine("Total liabilities and equity", tle, "total", "total_liabilities_equity", "Equity", computed=True)
                memo = next((i for i, ln in enumerate(bal) if ln.kind == "memo"), len(bal))
                bal.insert(memo, line)

        # Balance check: assets should equal liabilities plus equity in every year.
        notes: list[str] = []
        assets, tle_line = _find(bal, "total_assets"), _find(bal, "total_liabilities_equity")
        if assets and tle_line:
            gaps = [
                f"FY{period.year} ({abs(a - b) / abs(a):.1%})"
                for period, a, b in zip(periods, assets.values, tle_line.values, strict=True)
                if a and b is not None and abs(a - b) > 0.005 * abs(a)
            ]
            if gaps:
                notes.append(
                    "Balance check: total assets differ from total liabilities and equity in "
                    f"{', '.join(gaps)}. The source data is incomplete or inconsistent for those years; "
                    "verify against the filing."
                )

        info = financials.get("info") or {}
        currency = str(info.get("financialCurrency") or info.get("currency") or "")
        return StatementsResult(
            periods=[p.strftime("%Y-%m-%d") for p in periods],
            currency=currency,
            income=inc,
            balance=bal,
            cashflow=cfs,
            notes=notes,
        )
