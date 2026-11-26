from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

FLAG_LABELS = {
    "beneish_m": "Beneish M-score above -2.22",
    "negative_equity": "negative shareholders' equity",
    "de_ratio": "high debt to equity",
    "negative_fcf": "negative free cash flow in 2+ years",
}


@dataclass
class RedFlag:
    type: str
    value: Any
    severity: str

    @property
    def label(self) -> str:
        """Plain-English name for reports and summaries (``type`` stays the stable code)."""
        return FLAG_LABELS.get(self.type, self.type.replace("_", " "))


@dataclass
class ValuationResult:
    pe_ratio: float | None
    pb_ratio: float | None
    ev_ebitda: float | None
    vs_sector: str | None
    flag: str | None


@dataclass
class HealthResult:
    piotroski_f: int | None
    piotroski_signals: dict[str, int]
    altman_z: float | None
    debt_to_equity: float | None
    current_ratio: float | None
    interest_coverage: float | None
    flag: str | None
    notes: list[str] = field(default_factory=list)


@dataclass
class GrowthResult:
    revenue_cagr_3y: float | None
    pat_cagr_3y: float | None
    margin_trend: str | None
    fcf_yield: float | None
    flag: str | None


@dataclass
class QualityResult:
    """Profitability, cash-flow and working-capital quality metrics (ratios are fractions)."""

    net_margin: float | None = None
    asset_turnover: float | None = None
    equity_multiplier: float | None = None
    roe: float | None = None
    roic: float | None = None
    fcf: float | None = None
    fcf_margin: float | None = None
    fcf_to_net_income: float | None = None
    accruals_ratio: float | None = None
    dso_days: float | None = None
    dio_days: float | None = None
    dpo_days: float | None = None
    cash_conversion_cycle_days: float | None = None
    share_count_change: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class HistoryResult:
    """Up to four fiscal years, oldest first. None = not reported (never zero)."""

    years: list[str]
    revenue: list[float | None]
    net_income: list[float | None]
    operating_cash_flow: list[float | None]
    free_cash_flow: list[float | None]
    operating_margin: list[float | None]
    currency: str = ""


@dataclass
class StatementLine:
    """One line of a financial statement; ``values`` align with the periods, newest first."""

    label: str
    values: list[float | None]
    kind: str = "item"  # item | subtotal | total | memo
    key: str = ""  # stable identifier (labels are display text and may be escaped)
    group: str = ""  # heading the line sits under, e.g. "Assets" or "Operating activities"
    sign: int = 1  # display multiplier: -1 shows a reported cost in parentheses
    per_share: bool = False
    computed: bool = False  # arithmetic on reported lines, not a reported line itself


@dataclass
class StatementsResult:
    """Up to four fiscal years of the three statements, newest first."""

    periods: list[str]  # ISO period-end dates
    currency: str
    income: list[StatementLine]
    balance: list[StatementLine]
    cashflow: list[StatementLine]
    notes: list[str] = field(default_factory=list)


@dataclass
class FlagsResult:
    red_flags: list[RedFlag]
    beneish_m: float | None
    highest_concern: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    ticker: str
    company: str
    exchange: str
    scan_duration_ms: int
    valuation: ValuationResult
    health: HealthResult
    growth: GrowthResult
    red_flags: list[RedFlag]
    highest_concern: str
    analyst_brief: str
    beneish_m: float | None = None
    schema_version: int = 1
    notes: list[str] = field(default_factory=list)
    quality: QualityResult | None = None
    history: HistoryResult | None = None
    statements: StatementsResult | None = None
    dcf: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["valuation"] = asdict(self.valuation)
        result["health"] = asdict(self.health)
        result["growth"] = asdict(self.growth)
        result["quality"] = asdict(self.quality) if self.quality else None
        result["history"] = asdict(self.history) if self.history else None
        result["statements"] = asdict(self.statements) if self.statements else None
        result["red_flags"] = [asdict(flag) for flag in self.red_flags]
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=False)


@dataclass
class CompareResult:
    ticker_a: str
    ticker_b: str
    result_a: ScanResult
    result_b: ScanResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker_a": self.ticker_a,
            "ticker_b": self.ticker_b,
            "result_a": self.result_a.to_dict(),
            "result_b": self.result_b.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=False)
