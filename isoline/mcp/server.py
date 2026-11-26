from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from isoline import __version__
from isoline.core.scanner import IsolineScanner
from isoline.core.validation import bounded_number, validate_sector, validate_ticker

INSTRUCTIONS = "Financial statement analysis MCP server for AI IDEs."

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
        name="statements",
        title="Financial statements",
        description="Income statement, balance sheet and cash flow (up to four fiscal years, newest first, as reported; costs have sign -1).",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
            "additionalProperties": False,
        },
        outputSchema={"type": "object"},
    ),
    types.Tool(
        name="value",
        title="Discounted cash flow",
        description="DCF estimate with bear/base/bull scenarios and a sensitivity grid. Every assumption is returned; illustrative, not a price target.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "discount": {"type": "number", "description": "Discount rate, e.g. 0.10"},
                "growth": {"type": "number", "description": "Year-1 free cash flow growth, e.g. 0.06"},
                "terminal": {"type": "number", "description": "Terminal growth, e.g. 0.025"},
                "years": {"type": "integer", "description": "Explicit forecast years, 1-15"},
            },
            "required": ["ticker"],
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
    if not isinstance(exchange, str):
        raise ValueError("Exchange must be text, for example NSE or NASDAQ.")
    suffix = EXCHANGE_SUFFIXES.get(exchange.strip().upper())
    if suffix is None:
        raise ValueError(
            f"Unknown exchange '{exchange}'. Supported: {', '.join(sorted(EXCHANGE_SUFFIXES))}"
        )
    return ticker if "." in ticker else ticker + suffix


def _scan_and_serialize(scanner: IsolineScanner, ticker: str) -> str:
    result = scanner.scan(ticker)
    return result.to_json()


async def _serialized_tool_result(payload: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, indent=2))],
        structuredContent=payload,
        isError=False,
    )


async def list_tools(_: Any = None) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOL_DEFINITIONS)


async def handle_tool_call(
    name: str, arguments: dict[str, Any] | None
) -> types.CallToolResult:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object.")
    if name == "scan" or name == "scan_ticker":
        if not arguments.get("ticker"):
            raise ValueError("Missing ticker")
        ticker = validate_ticker(arguments["ticker"])
        if name == "scan_ticker":
            ticker = validate_ticker(_with_exchange(ticker, arguments.get("exchange")))
        payload = {"result": json.loads(_scan_and_serialize(IsolineScanner(), ticker))}
    elif name == "compare":
        if not arguments.get("ticker_a") or not arguments.get("ticker_b"):
            raise ValueError("Missing ticker_a or ticker_b")
        ticker_a = validate_ticker(arguments["ticker_a"])
        ticker_b = validate_ticker(arguments["ticker_b"])
        comparison = IsolineScanner().compare(ticker_a, ticker_b)
        payload = {"result": json.loads(comparison.to_json())}
    elif name == "screen":
        from isoline.core.screening import screen_sector

        outcome = screen_sector(
            validate_sector(arguments.get("sector")),
            int(bounded_number(arguments.get("min_piotroski"), "min_piotroski", 0, 9, 0)),
            bounded_number(arguments.get("max_de"), "max_de", 0, 1000, 10.0),
        )
        payload = {
            "matches": [r.to_dict() for r in outcome.matches],
            "skipped": outcome.skipped,
        }
    elif name == "statements":
        import dataclasses

        from isoline.core.engines.statements import StatementsEngine
        from isoline.core.loaders import load_financials

        if not arguments.get("ticker"):
            raise ValueError("Missing ticker")
        ticker = validate_ticker(arguments["ticker"])
        st = StatementsEngine().run(load_financials(ticker))
        payload = {"ticker": ticker, "statements": dataclasses.asdict(st) if st else None}
    elif name == "value":
        from isoline.core.dcf import run_dcf
        from isoline.core.loaders import load_financials

        if not arguments.get("ticker"):
            raise ValueError("Missing ticker")
        ticker = validate_ticker(arguments["ticker"])

        def opt(key: str, lo: float, hi: float) -> float | None:
            raw = arguments.get(key)
            return None if raw is None else bounded_number(raw, key, lo, hi, 0.0)

        res = run_dcf(
            load_financials(ticker),
            ticker,
            opt("discount", 0.0, 1.0),
            opt("growth", -0.5, 1.0),
            opt("terminal", -0.05, 0.2),
            int(bounded_number(arguments.get("years"), "years", 1, 15, 5)),
        )
        payload = {"result": res.to_dict()}
    elif name == "info":
        payload = {
            "version": __version__,
            "data_source": "Yahoo Finance (yfinance); SEC EDGAR fallback for US tickers",
            "coverage": ["valuation", "health", "growth", "quality", "flags", "statements", "dcf"],
            "description": "Financial statement analysis MCP server for AI IDEs.",
        }
    else:
        raise ValueError(f"Unknown tool: {name}")

    return await _serialized_tool_result(payload)


def _error_result(exc: BaseException) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=str(exc))], isError=True)


def _build_server() -> Server:
    """Register the same two handlers with whichever MCP Python SDK API is installed.

    SDK 1.x registers handlers with decorators (``@server.list_tools()``) and turns an
    exception into an error result itself. SDK 2.x takes ``on_list_tools`` /
    ``on_call_tool`` in the constructor; there the wrapper converts exceptions into the
    same error result, so clients see identical behaviour on both.
    """
    if hasattr(Server, "list_tools"):  # SDK 1.x
        srv = Server("isoline", version=__version__, instructions=INSTRUCTIONS)
        srv.list_tools()(list_tools)
        srv.call_tool(validate_input=False)(handle_tool_call)
        return srv

    async def on_list_tools(_ctx: Any, _params: Any) -> types.ListToolsResult:
        return await list_tools()

    async def on_call_tool(_ctx: Any, params: Any) -> types.CallToolResult:
        try:
            return await handle_tool_call(params.name, params.arguments)
        except Exception as exc:  # noqa: BLE001 - reported to the client as a tool error
            return _error_result(exc)

    return Server(  # type: ignore[call-arg,unused-ignore]
        "isoline",
        version=__version__,
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


server = _build_server()


def run_mcp_server() -> None:
    async def run_server() -> None:
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options(NotificationOptions())
            await server.run(read_stream, write_stream, init_options)

    asyncio.run(run_server())
