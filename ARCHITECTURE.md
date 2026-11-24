# Architecture

```
telmus/
  cli/app.py          Typer CLI (scan, compare, screen, serve), error mapping, exit codes
  core/
    loaders.py        provider access (yfinance today) with retry/backoff -> dict of DataFrames
    labels.py         canonical line-item aliases; all engines read data only through this
    errors.py         typed errors (+ hint, exit code)
    engines/          health (F, Z''), flags (Beneish, red flags), growth, valuation, quality
    scanner.py        orchestrates engines -> ScanResult
    result.py         dataclasses; to_dict() is the stable JSON shape
  exporters/          html_dashboard, excel, powerbi; _safe.py escapes all text
  sdk/                public Python API (scan, compare, TelmusScanner)
  mcp/server.py       optional MCP server (extra: telmus[mcp])
```

Principles: engines are pure functions of data frames (testable offline); provider quirks live only in `loaders.py` and `labels.py`; every n/a carries a note; exporters never trust text.

Planned: a `DataProvider` protocol returning the same frames so SEC EDGAR or CSV sources plug into `loaders.py` without touching engines (see DATA_SOURCES.md).
