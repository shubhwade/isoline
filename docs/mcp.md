# MCP Server Guide

telmus can run as an MCP server so AI assistants and agents can call financial analytics tools directly. This makes valuation, health, growth, and red-flag metrics available to Claude, Cursor, Windsurf, and other MCP-compatible clients.

## Why use telmus as an MCP server

- Get deterministic, documented financial metrics instead of model-generated numbers.
- Let AI agents fetch company analysis automatically during conversations.
- Keep your local environment in control while giving assistants structured access to tools.
- Same engine as the CLI and the Python SDK.

## Install and start

```bash
pip install "telmus[mcp]"
telmus serve
```

`telmus serve` speaks MCP over **stdio**: it opens no network port and prints nothing on its own. You normally don't run it by hand; your MCP client launches it (see the client examples below). Without the extra installed, the command exits with a message telling you to install it.

## Available MCP tools

| Tool | Inputs | Returns |
|---|---|---|
| `scan` | `ticker` | `{"result": ScanResult}` (same JSON as `scan(...).to_dict()`) |
| `scan_ticker` | `ticker`, optional `exchange` (`NSE`, `BSE`, `LSE`, `NYSE`, `NASDAQ`, `US`) | same; `INFY` + `NSE` scans `INFY.NS`; a ticker that already has a suffix is left alone; unknown exchange is an error |
| `compare` | `ticker_a`, `ticker_b` | `{"result": CompareResult}` |
| `screen` | optional `sector` (`IT` or `Banking`, default `IT`), `min_piotroski` (default 0), `max_de` (default 10) | `{"matches": [ScanResult...], "skipped": {ticker: reason}}`; unknown sector is an error |
| `info` | none | `{version, data_source, coverage, description}` |

Missing metrics are `null` with an explanation in each result's `notes`. `screen` only covers the small built-in example lists described in the [CLI](cli.md#screen) page.

## Client setup examples

### Claude Desktop

```json
{
  "mcpServers": {
    "telmus": {
      "command": "telmus",
      "args": ["serve"],
      "description": "Financial statement analysis - real ratios for any ticker"
    }
  }
}
```

### Cursor

```json
{
  "mcpServers": {
    "telmus": {
      "command": "telmus",
      "args": ["serve"],
      "description": "Financial statement analysis - real ratios for any ticker"
    }
  }
}
```

### Windsurf

```json
{
  "mcpServers": {
    "telmus": {
      "command": "telmus",
      "args": ["serve"],
      "description": "Financial statement analysis - real ratios for any ticker"
    }
  }
}
```

## Using the tools

### Example: scan a company

Ask the assistant to:

- `Analyze INFY financials`
- `Run a scan for AAPL`
- `Get Piotroski and Altman Z for TCS`

### Example: compare two names

Ask the assistant to:

- `Compare INFY and TCS`
- `Show me valuation and health differences between Apple and Microsoft`

### Example: screen for quality companies

Ask the assistant to:

- `Find IT stocks with Piotroski above 6 and debt-to-equity below 1.5`
- `Give me a shortlist of low-leverage, high-quality companies in the technology sector`

## Troubleshooting

- `telmus serve` prints "needs the optional mcp extra": run `pip install "telmus[mcp]"`.
- The client cannot start the server: make sure `telmus` is on the PATH of the app that launches it (on Windows/macOS GUI apps this can differ from your terminal; use the full path to `telmus` in `command`).
- A ticker is not found: add the exchange suffix (`INFY.NS`) or pass `exchange` to `scan_ticker`.
- Data is from Yahoo Finance (unofficial). Output is screening statistics, not investment advice.
