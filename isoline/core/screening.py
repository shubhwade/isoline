"""Sector screening shared by the CLI and the MCP server.

The universes are small, hand-picked example lists (NSE tickers), not an
exhaustive or authoritative index membership. Banks report Piotroski/Altman/D-E
differently, so they are usually skipped with a reason rather than scored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from isoline.core.errors import IsolineError, UnknownSectorError
from isoline.core.result import ScanResult
from isoline.core.scanner import IsolineScanner

UNIVERSES: dict[str, list[str]] = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "SBIN.NS", "AXISBANK.NS"],
}


@dataclass
class ScreenOutcome:
    matches: list[ScanResult] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # ticker -> reason


def resolve_sector(sector: str) -> str:
    for name in UNIVERSES:
        if name.lower() == sector.strip().lower():
            return name
    raise UnknownSectorError(sector, list(UNIVERSES))


def screen_sector(
    sector: str, min_piotroski: int, max_de: float, scanner: IsolineScanner | None = None
) -> ScreenOutcome:
    scanner = scanner or IsolineScanner()
    outcome = ScreenOutcome()
    for ticker in UNIVERSES[resolve_sector(sector)]:
        try:
            result = scanner.scan(ticker)
        except IsolineError as exc:
            outcome.skipped[ticker] = str(exc)
            continue
        f, de = result.health.piotroski_f, result.health.debt_to_equity
        if f is None or de is None:
            outcome.skipped[ticker] = "Piotroski F or debt/equity not computable from the data"
        elif f >= min_piotroski and de <= max_de:
            outcome.matches.append(result)
    return outcome
