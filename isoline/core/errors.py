"""Typed errors so the CLI can say what went wrong and what to do about it.

All inherit ValueError so existing ``except ValueError`` callers keep working.
"""

from __future__ import annotations


class IsolineError(ValueError):
    """Base class. ``hint`` tells the user what to try next."""

    hint = ""
    exit_code = 1


class InvalidTickerError(IsolineError):
    hint = "Use a ticker such as AAPL, MSFT or INFY.NS (Yahoo Finance format)."
    exit_code = 2


class NoDataError(IsolineError):
    hint = (
        "Check the symbol on finance.yahoo.com. Non-US stocks need an exchange "
        "suffix, e.g. INFY.NS, RELIANCE.BO, VOD.L."
    )


class ProviderUnavailableError(IsolineError):
    hint = "Check your internet connection / proxy and try again in a minute."
    exit_code = 3


class RateLimitError(ProviderUnavailableError):
    hint = "Yahoo Finance is rate-limiting requests. Wait a few minutes and retry."


class UnknownSectorError(IsolineError):
    exit_code = 2

    def __init__(self, sector: str, available: list[str]) -> None:
        super().__init__(f"Unknown sector '{sector}'.")
        self.hint = "Available sectors: " + ", ".join(available)
