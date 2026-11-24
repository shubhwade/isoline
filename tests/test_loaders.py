from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from telmus.core.loaders import load_financials


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

    with patch("telmus.core.loaders._import_yfinance", return_value=fake_yf), patch(
        "telmus.core.loaders._resolve_ticker_by_name", return_value="AAPL"
    ):
        result = load_financials("APPLE")

    assert result["info"]["symbol"] == "AAPL"
    assert result["income_stmt"] == {"Total Revenue": 100}
    assert result["fast_info"] == {}  # unused by every engine; no longer fetched (saves a request)


def test_load_financials_raises_for_unknown_company_name() -> None:
    load_financials.cache_clear()
    fake_yf = Mock()
    fake_yf.Ticker.return_value = DummyTicker("UNKNOWN")

    with patch("telmus.core.loaders._import_yfinance", return_value=fake_yf), patch(
        "telmus.core.loaders._resolve_ticker_by_name", return_value=None
    ), pytest.raises(ValueError, match="No financial data available"):
        load_financials("UNKNOWN")


def test_statements_are_fetched_concurrently() -> None:
    """Four 0.3s network calls must take ~0.3s, not ~1.2s."""
    import time
    import types
    from unittest.mock import patch

    import pandas as pd

    from telmus.core import loaders

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

    from telmus.core.scanner import TelmusScanner
    from tests.test_scores import company

    def slow(ticker: str) -> dict:
        time.sleep(0.4)
        fin = company()
        fin["info"] = {"symbol": ticker, "longName": ticker, "exchange": "X"}
        return fin

    with patch("telmus.core.scanner.load_financials", side_effect=slow):
        start = time.perf_counter()
        result = TelmusScanner().compare("AAA", "BBB")
        elapsed = time.perf_counter() - start
    assert (result.result_a.ticker, result.result_b.ticker) == ("AAA", "BBB")
    assert elapsed < 0.7
