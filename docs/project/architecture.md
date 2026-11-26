# Architecture

```
isoline/
  cli/app.py          Typer CLI (scan, compare, value, statements, screen, check, powerbi, tui, serve), error mapping, exit codes
  core/
    loaders.py        provider access (yfinance today) with retry/backoff -> dict of DataFrames
    labels.py         canonical line-item aliases; all engines read data only through this
    errors.py         typed errors (+ hint, exit code)
    validation.py     one set of input rules (tickers, sectors, bounded numbers) for CLI, TUI, SDK and MCP
    dcf.py            discounted cash flow, scenarios and sensitivity grid
    engines/          health (F, Z''), flags (Beneish, red flags), growth, valuation, quality, history (chart series),
                      statements (income statement, balance sheet, cash flow laid out for presentation)
    scanner.py        orchestrates engines -> ScanResult (compare scans both tickers concurrently)
    screening.py      sector screening shared by the CLI and the MCP server
    result.py         dataclasses; to_dict() is the stable JSON shape
  exporters/          report.py (self-contained HTML with a CSP), html_dashboard.py (thin wrapper), excel, powerbi;
                      _safe.py escapes HTML and neutralises spreadsheet formula injection; exporters never use the network
  sdk/                public Python API (scan, compare, statements, value, IsolineScanner)
  mcp/server.py       optional MCP server (extra: isoline[mcp])
```

Principles: engines are pure functions of data frames (testable offline); provider quirks live only in `loaders.py` and `labels.py`; every n/a carries a note; exporters never trust text.

Planned: a `DataProvider` protocol returning the same frames so SEC EDGAR or CSV sources plug into `loaders.py` without touching engines (see Data sources).
