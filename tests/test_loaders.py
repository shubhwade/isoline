from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from isoline.core.loaders import load_financials


class DummyTicker:
    def __init__(self, symbol: str) -> None:
        self._symbol = symbol

    @property
    def info(self) -> dict[str, object]:
        if self._symbol == "APPLE":
            return {}
        if self._symbol == "UNKNOWN":
            return {}
        return {"symbol": self._symbol, "longName": "Apple Inc."}

    @property
    def financials(self) -> dict:
        if self._symbol == "AAPL":
            return {"Total Revenue": 100}
        return {}

    @property
    def balance_sheet(self) -> dict:
        return {}

    @property
    def cashflow(self) -> dict:
        return {}

    @property
    def fast_info(self) -> dict:
        return {"currency": "USD"} if self._symbol == "AAPL" else {}


def test_load_financials_resolves_company_name_to_ticker() -> None:
    load_financials.cache_clear()
    fake_yf = Mock()
    fake_yf.Ticker.side_effect = lambda symbol: DummyTicker(symbol)

    with patch("isoline.core.loaders._import_yfinance", return_value=fake_yf), patch(
        "isoline.core.loaders._resolve_ticker_by_name", return_value="AAPL"
    ):
        result = load_financials("APPLE")

    assert result["info"]["symbol"] == "AAPL"
    assert result["income_stmt"] == {"Total Revenue": 100}
    assert result["fast_info"] == {}  # unused by every engine; no longer fetched (saves a request)


def test_load_financials_raises_for_unknown_company_name() -> None:
    load_financials.cache_clear()
    fake_yf = Mock()
    fake_yf.Ticker.return_value = DummyTicker("UNKNOWN")

    with patch("isoline.core.loaders._import_yfinance", return_value=fake_yf), patch(
        "isoline.core.loaders._resolve_ticker_by_name", return_value=None
    ), pytest.raises(ValueError, match="No financial data available"):
        load_financials("UNKNOWN")


def test_statements_are_fetched_concurrently() -> None:
    """Four 0.3s network calls must take ~0.3s, not ~1.2s."""
    import time
    import types
    from unittest.mock import patch

    import pandas as pd

    from isoline.core import loaders

    class SlowTicker:
        def __init__(self, symbol: str) -> None:
            pass

        def _slow(self, value):
            time.sleep(0.3)
            return value

        info = property(lambda self: self._slow({"symbol": "X"}))
        financials = property(lambda self: self._slow(pd.DataFrame({"a": [1]})))
        balance_sheet = property(lambda self: self._slow(pd.DataFrame({"a": [1]})))
        cashflow = property(lambda self: self._slow(pd.DataFrame({"a": [1]})))

    fake = types.SimpleNamespace(Ticker=SlowTicker)
    with patch.object(loaders, "_import_yfinance", return_value=fake):
        start = time.perf_counter()
        info, income, balance, cash, fast = loaders._load_data("X")
        elapsed = time.perf_counter() - start
    assert info == {"symbol": "X"} and len(income) == len(balance) == len(cash) == 1
    assert elapsed < 0.9, f"fetches look sequential: {elapsed:.2f}s"


def test_compare_runs_both_scans_concurrently() -> None:
    import time
    from unittest.mock import patch

    from isoline.core.scanner import IsolineScanner
    from tests.test_scores import company

    def slow(ticker: str) -> dict:
        time.sleep(0.4)
        fin = company()
        fin["info"] = {"symbol": ticker, "longName": ticker, "exchange": "X"}
        return fin

    with patch("isoline.core.scanner.load_financials", side_effect=slow):
        start = time.perf_counter()
        result = IsolineScanner().compare("AAA", "BBB")
        elapsed = time.perf_counter() - start
    assert (result.result_a.ticker, result.result_b.ticker) == ("AAA", "BBB")
    assert elapsed < 0.7


def test_concurrent_scans_leave_stdout_intact() -> None:
    """Regression: `isoline compare` crashed with 'I/O operation on closed file'.

    Two overlapping fetches used contextlib.redirect_stdout, which is process-wide, and
    left sys.stdout pointing at a closed buffer.
    """
    import sys
    import time
    import types
    from unittest.mock import patch

    from isoline.core import loaders
    from isoline.core.scanner import IsolineScanner
    from tests.test_scores import company

    data = company()

    class Slow:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def _slow(self, value):
            time.sleep(0.15)
            print("noisy provider output")  # must be swallowed, never reach the terminal
            return value

        info = property(lambda s: s._slow({"symbol": s.symbol, "longName": s.symbol, "exchange": "X"}))
        financials = property(lambda s: s._slow(data["income_stmt"]))
        balance_sheet = property(lambda s: s._slow(data["balance_sheet"]))
        cashflow = property(lambda s: s._slow(data["cashflow"]))

    before_out, before_err = sys.stdout, sys.stderr
    loaders.load_financials.cache_clear()
    with patch.object(loaders, "_import_yfinance", return_value=types.SimpleNamespace(Ticker=Slow)):
        result = IsolineScanner().compare("AAA", "BBB")
    loaders.load_financials.cache_clear()
    assert sys.stdout is before_out and sys.stderr is before_err
    assert not sys.stdout.closed
    assert (result.result_a.ticker, result.result_b.ticker) == ("AAA", "BBB")
    assert loaders._quiet_depth == 0 and loaders._quiet_saved is None
