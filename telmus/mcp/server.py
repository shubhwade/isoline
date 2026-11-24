from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from telmus import __version__
from telmus.core.scanner import TelmusScanner

server = Server(
    "telmus",
    version=__version__,
    instructions="Financial statement analysis MCP server for AI IDEs.",
)

TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="scan",
        title="Scan ticker",
        description="Run a financial scan for a single ticker symbol.",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
        outputSchema={"type": "object"},
    ),
    types.Tool(
        name="scan_ticker",
        title="Scan ticker with exchange",
        description="Scan a ticker, with an optional exchange (NSE, BSE, LSE, NYSE, NASDAQ) to pick the right listing.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "exchange": {"type": "string"},
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
        outputSchema={"type": "object"},
    ),
    types.Tool(
        name="compare",
        title="Compare two tickers",
        description="Compare financial metrics for two ticker symbols.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker_a": {"type": "string"},
                "ticker_b": {"type": "string"},
            },
            "required": ["ticker_a", "ticker_b"],
            "additionalProperties": False,
        },
        outputSchema={"type": "object"},
    ),
    types.Tool(
        name="screen",
        title="Screen sector tickers",
        description="Run a simple sector screener and return matching tickers.",
        inputSchema={
            "type": "object",
            "properties": {
                "sector": {"type": "string"},
                "min_piotroski": {"type": "number"},
                "max_de": {"type": "number"},
            },
            "required": [],
            "additionalProperties": False,
        },
        outputSchema={"type": "object"},
    ),
    types.Tool(
        name="info",
        title="Server info",
        description="Return basic server metadata and coverage information.",
        inputSchema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        outputSchema={"type": "object"},
    ),
]


EXCHANGE_SUFFIXES = {"NSE": ".NS", "BSE": ".BO", "LSE": ".L", "NYSE": "", "NASDAQ": "", "US": ""}


def _with_exchange(ticker: str, exchange: str | None) -> str:
    """Apply an exchange hint to a bare symbol (``INFY`` + ``NSE`` -> ``INFY.NS``)."""
    if not exchange:
        return ticker
    suffix = EXCHANGE_SUFFIXES.get(exchange.strip().upper())
    if suffix is None:
        raise ValueError(
            f"Unknown exchange '{exchange}'. Supported: {', '.join(sorted(EXCHANGE_SUFFIXES))}"
        )
    return ticker if "." in ticker else ticker + suffix


def _scan_and_serialize(scanner: TelmusScanner, ticker: str) -> str:
    result = scanner.scan(ticker)
    return result.to_json()


async def _serialized_tool_result(payload: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))],
        structuredContent=payload,
        isError=False,
    )


@server.list_tools()
async def list_tools(_: types.ListToolsRequest | None = None) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOL_DEFINITIONS)


@server.call_tool(validate_input=False)
async def handle_tool_call(
    name: str, arguments: dict[str, Any] | None
) -> types.CallToolResult:
    arguments = arguments or {}
    if name == "scan" or name == "scan_ticker":
        ticker = arguments.get("ticker")
        if not ticker:
            raise ValueError("Missing ticker")
        if name == "scan_ticker":
            ticker = _with_exchange(ticker, arguments.get("exchange"))
        payload = {"result": json.loads(_scan_and_serialize(TelmusScanner(), ticker))}
    elif name == "compare":
        ticker_a = arguments.get("ticker_a")
        ticker_b = arguments.get("ticker_b")
        if not ticker_a or not ticker_b:
            raise ValueError("Missing ticker_a or ticker_b")
        comparison = TelmusScanner().compare(ticker_a, ticker_b)
        payload = {"result": json.loads(comparison.to_json())}
    elif name == "screen":
        from telmus.core.screening import screen_sector

        outcome = screen_sector(
            arguments.get("sector", "IT"),
            int(arguments.get("min_piotroski", 0)),
            float(arguments.get("max_de", 10.0)),
        )
        payload = {
            "matches": [r.to_dict() for r in outcome.matches],
            "skipped": outcome.skipped,
        }
    elif name == "info":
        payload = {
            "version": __version__,
            "data_source": "yfinance",
            "coverage": ["valuation", "health", "growth", "quality", "flags"],
            "description": "Financial statement analysis MCP server for AI IDEs.",
        }
    else:
        raise ValueError(f"Unknown tool: {name}")

    return await _serialized_tool_result(payload)


def run_mcp_server() -> None:
    async def run_server() -> None:
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options(NotificationOptions())
            await server.run(read_stream, write_stream, init_options)

    asyncio.run(run_server())
