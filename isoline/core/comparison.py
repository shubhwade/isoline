"""One definition of what `compare` shows, shared by the terminal, CSV and HTML report.

``direction``: +1 higher is stronger, -1 lower is stronger, 0 no winner is implied
(valuation multiples are not "better" or "worse" on their own).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from isoline.core.result import ScanResult


@dataclass(frozen=True)
class Metric:
    label: str
    get: Callable[[ScanResult], float | None]
    kind: str  # "num" | "int" | "pct" | "days"
    direction: int


SECTIONS: list[tuple[str, list[Metric]]] = [
    (
        "Valuation (no winner is implied)",
        [
            Metric("P/E ratio", lambda r: r.valuation.pe_ratio, "num", 0),
            Metric("P/B ratio", lambda r: r.valuation.pb_ratio, "num", 0),
            Metric("EV/EBITDA", lambda r: r.valuation.ev_ebitda, "num", 0),
        ],
    ),
    (
        "Financial health",
        [
            Metric("Piotroski F-score", lambda r: r.health.piotroski_f, "int", 1),
            Metric("Altman Z″", lambda r: r.health.altman_z, "num", 1),
            Metric("Debt / equity", lambda r: r.health.debt_to_equity, "num", -1),
            Metric("Current ratio", lambda r: r.health.current_ratio, "num", 1),
            Metric("Interest coverage", lambda r: r.health.interest_coverage, "num", 1),
            Metric("Beneish M-score", lambda r: r.beneish_m, "num", -1),
        ],
    ),
    (
        "Growth",
        [
            Metric("Revenue CAGR, 3 years", lambda r: r.growth.revenue_cagr_3y, "pct", 1),
            Metric("Net income CAGR, 3 years", lambda r: r.growth.pat_cagr_3y, "pct", 1),
            Metric("Free cash flow yield", lambda r: r.growth.fcf_yield, "pct", 1),
        ],
    ),
    (
        "Profitability and cash quality",
        [
            Metric("Return on equity", lambda r: r.quality.roe if r.quality else None, "pct", 1),
            Metric("Return on invested capital", lambda r: r.quality.roic if r.quality else None, "pct", 1),
            Metric("Free cash flow margin", lambda r: r.quality.fcf_margin if r.quality else None, "pct", 1),
            Metric(
                "Cash conversion cycle",
                lambda r: r.quality.cash_conversion_cycle_days if r.quality else None,
                "days",
                -1,
            ),
        ],
    ),
]


def all_metrics() -> list[Metric]:
    return [m for _, metrics in SECTIONS for m in metrics]


def stronger(a: float | None, b: float | None, direction: int) -> str | None:
    """'a', 'b', or None (no direction, a value is missing, or a tie). Missing never wins."""
    if direction == 0 or a is None or b is None or a == b:
        return None
    return "a" if (a > b) == (direction > 0) else "b"


def format_value(value: float | None, kind: str) -> str:
    if value is None:
        return "n/a"
    if kind == "pct":
        return f"{value * 100:,.1f}%"
    if kind == "int":
        return f"{int(value)}"
    if kind == "days":
        return f"{value:,.0f} days"
    return f"{value:,.2f}"
