from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RedFlag:
    type: str
    value: Any
    severity: str


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

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["valuation"] = asdict(self.valuation)
        result["health"] = asdict(self.health)
        result["growth"] = asdict(self.growth)
        result["quality"] = asdict(self.quality) if self.quality else None
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
