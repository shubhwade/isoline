"""Input validation shared by the command line, the SDK-facing MCP server and the TUI.

Everything that reaches a data provider or a file name passes through here first, so
the same rules apply whether a person typed the value or an AI client sent it.
"""

from __future__ import annotations

import math
import re
from typing import Any

# Tickers (AAPL, INFY.NS, BRK-B, ^GSPC, EURUSD=X) and short company names.
TICKER_RE = re.compile(r"[A-Za-z0-9^][A-Za-z0-9.\-^=& ]{0,39}")
SECTOR_RE = re.compile(r"[A-Za-z][A-Za-z &\-]{0,39}")


class InvalidInputError(ValueError):
    """A value supplied by a user or client failed validation."""


def validate_ticker(raw: Any) -> str:
    if not isinstance(raw, str):
        raise InvalidInputError("Ticker must be text, for example AAPL or INFY.NS.")
    ticker = raw.strip()
    if not TICKER_RE.fullmatch(ticker):
        shown = raw[:40].replace("\n", " ")
        raise InvalidInputError(f"'{shown}' is not a valid ticker. Use a symbol such as AAPL or INFY.NS.")
    return ticker


def validate_sector(raw: Any, default: str = "IT") -> str:
    if raw is None or raw == "":
        return default
    if not isinstance(raw, str) or not SECTOR_RE.fullmatch(raw.strip()):
        raise InvalidInputError("Sector must be a short name such as IT or Banking.")
    return raw.strip()


def bounded_number(raw: Any, name: str, lo: float, hi: float, default: float) -> float:
    """A finite number within [lo, hi]; ``default`` when the value is absent."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        raise InvalidInputError(f"{name} must be a number.")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise InvalidInputError(f"{name} must be a number.") from None
    if not math.isfinite(value) or not lo <= value <= hi:
        raise InvalidInputError(f"{name} must be between {lo:g} and {hi:g}.")
    return value
