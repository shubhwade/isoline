from __future__ import annotations

import contextlib
import functools
import importlib
import io
import logging
import sys
import threading
import time
from typing import Any

from isoline.core.errors import (
    IsolineError,
    NoDataError,
    ProviderUnavailableError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


def _import_yfinance():
    return importlib.import_module("yfinance")


def _resolve_ticker_by_name(query: str) -> str | None:
    try:
        from yfinance.search import Search

        search = Search(query)
        search.search()
        quotes = getattr(search, "_quotes", None) or []
        for quote in quotes:
            if quote.get("quoteType") == "EQUITY" and quote.get("symbol"):
                return quote["symbol"]
        if quotes:
            return quotes[0].get("symbol")
    except Exception as exc:
        logger.debug(
            "Unable to resolve company name %s: %s",
            query,
            exc,
            exc_info=True,
        )
    return None


def _is_valid_financial_data(
    info: dict[str, object],
    income_stmt: object,
    balance_sheet: object,
    cashflow: object,
) -> bool:
    if info.get("symbol"):
        return True
    has_income = income_stmt is not None and (
        hasattr(income_stmt, "__len__")
        and len(income_stmt) > 0
        or isinstance(income_stmt, dict)
        and bool(income_stmt)
    )
    has_balance = balance_sheet is not None and (
        hasattr(balance_sheet, "__len__")
        and len(balance_sheet) > 0
        or isinstance(balance_sheet, dict)
        and bool(balance_sheet)
    )
    has_cashflow = cashflow is not None and (
        hasattr(cashflow, "__len__")
        and len(cashflow) > 0
        or isinstance(cashflow, dict)
        and bool(cashflow)
    )
    return has_income or has_balance or has_cashflow


_quiet_lock = threading.Lock()
_quiet_depth = 0
_quiet_saved: tuple[Any, Any, io.StringIO] | None = None


@contextlib.contextmanager
def _quiet():
    """Silence provider chatter on stdout/stderr, safely under concurrency.

    ``contextlib.redirect_stdout`` is process-wide and not re-entrant across threads:
    two overlapping scans each saved "the current stdout" (the other's buffer) and
    restored it in the wrong order, leaving sys.stdout pointing at a closed buffer
    ("I/O operation on closed file" in `isoline compare`). Here the first thread in
    swaps the streams and the last thread out restores the originals.
    """
    global _quiet_depth, _quiet_saved
    with _quiet_lock:
        if _quiet_depth == 0:
            sink = io.StringIO()
            _quiet_saved = (sys.stdout, sys.stderr, sink)
            sys.stdout = sys.stderr = sink
        _quiet_depth += 1
    try:
        yield
    finally:
        with _quiet_lock:
            _quiet_depth -= 1
            if _quiet_depth == 0 and _quiet_saved is not None:
                sys.stdout, sys.stderr, sink = _quiet_saved
                sink.close()
                _quiet_saved = None


def _load_data(symbol: str) -> tuple[dict[str, object], object, object, object, object]:
    """Fetch info and the three statements concurrently (they are independent HTTP calls).

    Sequential fetching costs roughly the sum of four round trips; running them in
    parallel costs roughly the slowest one.
    """
    from concurrent.futures import ThreadPoolExecutor

    yf = _import_yfinance()
    with _quiet():
        ticker_obj = yf.Ticker(symbol)

        def fetch(attr: str) -> object:
            value = getattr(ticker_obj, attr)
            return value if value is not None else {}

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                name: pool.submit(fetch, attr)
                for name, attr in (
                    ("info", "info"),
                    ("income", "financials"),
                    ("balance", "balance_sheet"),
                    ("cashflow", "cashflow"),
                )
            }
            results = {name: fut.result() for name, fut in futures.items()}
    info: dict[str, object] = results["info"] or {}  # type: ignore[assignment]
    # fast_info was fetched but never used by any engine; it is kept as an empty
    # placeholder so the returned dict keeps its shape.
    return info, results["income"], results["balance"], results["cashflow"], {}


_ATTEMPTS = 3
_sleep = time.sleep  # replaced in tests


def _classify(exc: Exception) -> IsolineError | None:
    """Map a provider exception to a typed error, or None if it is not transient."""
    text = f"{type(exc).__name__} {exc}".lower()
    if "ratelimit" in text or "too many requests" in text or "429" in text:
        return RateLimitError(f"Yahoo Finance rate limit reached ({exc})")
    transient = (
        "timeout", "timed out", "connection", "curl", "ssl", "proxy",
        "name or service", "temporary failure", "network", "403", "502", "503", "504",
    )
    if isinstance(exc, (OSError, TimeoutError)) or any(t in text for t in transient):
        return ProviderUnavailableError(f"Could not reach Yahoo Finance ({exc})")
    return None


def _load_data_with_retry(symbol: str):
    """Call _load_data, retrying transient failures with exponential backoff."""
    last: IsolineError | None = None
    for attempt in range(_ATTEMPTS):
        try:
            return _load_data(symbol)
        except Exception as exc:
            typed = _classify(exc)
            if typed is None:
                raise
            last = typed
            logger.debug("Attempt %d/%d for %s failed: %s", attempt + 1, _ATTEMPTS, symbol, exc)
            if attempt < _ATTEMPTS - 1:
                _sleep(2**attempt)  # 1s, 2s
    assert last is not None
    raise last


def _fallback(ticker: str, primary: IsolineError) -> dict[str, Any]:
    """Try the SEC when Yahoo fails for a US ticker; otherwise re-raise the Yahoo error."""
    from isoline.branding import env
    from isoline.core import edgar

    if env("NO_FALLBACK") or not edgar.is_us_symbol(ticker):
        raise primary
    try:
        bundle = edgar.load_edgar(ticker)
    except IsolineError as exc:
        logger.debug("EDGAR fallback failed for %s: %s", ticker, exc)
        raise primary from exc
    bundle["notes"] = [
        f"Yahoo Finance was unavailable ({primary}); figures come from SEC EDGAR annual "
        "filings. No live price, so valuation multiples are n/a."
    ]
    return bundle


@functools.lru_cache(maxsize=128)
def load_financials(ticker: str) -> dict[str, Any]:
    """Load financial data for a ticker from yfinance.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        A dictionary containing info, income_stmt, balance_sheet, cashflow, fast_info.

    Raises:
        ValueError: If data cannot be loaded for the ticker.
    """
    try:
        ticker_symbol = ticker

        info, income_stmt, balance_sheet, cashflow, fast_info = _load_data_with_retry(
            ticker_symbol
        )
        if not info.get("symbol"):
            resolved = _resolve_ticker_by_name(ticker)
            if resolved and resolved != ticker_symbol:
                ticker_symbol = resolved
                info, income_stmt, balance_sheet, cashflow, fast_info = _load_data_with_retry(
                    ticker_symbol
                )

        if not _is_valid_financial_data(info, income_stmt, balance_sheet, cashflow):
            raise NoDataError(f"No financial data available for ticker '{ticker}'")

        return {
            "info": info,
            "income_stmt": income_stmt,
            "balance_sheet": balance_sheet,
            "cashflow": cashflow,
            "fast_info": fast_info,
            "source": "Yahoo Finance (via yfinance)",
        }
    except IsolineError as primary:
        return _fallback(ticker, primary)
    except Exception as exc:
        logger.debug("Failed to load financials for %s: %s", ticker, exc, exc_info=True)
        raise ValueError(
            f"Unable to load financials for ticker '{ticker}': {exc}"
        ) from exc
