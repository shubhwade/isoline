"""MCP tool handlers, tested offline with a mocked provider."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

pytest.importorskip("mcp")
from telmus.mcp.server import _with_exchange, handle_tool_call  # noqa: E402
from tests.test_scores import company  # noqa: E402


def _call(name: str, args: dict) -> dict:
    result = asyncio.run(handle_tool_call(name, args))
    return json.loads(result.content[0].text)


def _fin(ticker: str) -> dict:
    fin = company()
    fin["info"] = {"symbol": ticker, "longName": ticker, "exchange": "X", "marketCap": 3000.0}
    return fin


def test_info_lists_quality_and_version() -> None:
    import telmus

    out = _call("info", {})
    assert out["version"] == telmus.__version__ and "quality" in out["coverage"]


def test_scan_and_scan_ticker_apply_exchange_hint() -> None:
    seen: list[str] = []

    def fake(t: str) -> dict:
        seen.append(t)
        return _fin(t)

    with patch("telmus.core.scanner.load_financials", side_effect=fake):
        assert _call("scan", {"ticker": "INFY"})["result"]["ticker"] == "INFY"
        _call("scan_ticker", {"ticker": "INFY", "exchange": "nse"})
        _call("scan_ticker", {"ticker": "INFY.BO", "exchange": "NSE"})  # explicit suffix wins
    assert seen == ["INFY", "INFY.NS", "INFY.BO"]


def test_bad_inputs_are_errors() -> None:
    with pytest.raises(ValueError, match="Unknown exchange"):
        _with_exchange("X", "MARS")
    with pytest.raises(ValueError, match="Missing ticker"):
        _call("scan", {})
    with pytest.raises(ValueError, match="Unknown tool"):
        _call("nope", {})


def test_screen_reports_skipped_tickers() -> None:
    with patch("telmus.core.scanner.load_financials", side_effect=lambda t: _fin(t)):
        out = _call("screen", {"sector": "IT", "min_piotroski": 0, "max_de": 100})
    assert "matches" in out and "skipped" in out
    with pytest.raises(ValueError, match="Unknown sector"):
        _call("screen", {"sector": "Pharma"})
