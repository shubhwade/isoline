# telmus

[![PyPI version](https://img.shields.io/pypi/v/telmus)](https://pypi.org/project/telmus/)
[![Downloads](https://img.shields.io/pypi/dm/telmus?label=downloads%2Fmonth)](https://pypistats.org/packages/telmus)
[![Python](https://img.shields.io/pypi/pyversions/telmus)](https://pypi.org/project/telmus/)
[![CI](https://github.com/shubhwade/telmus/actions/workflows/ci.yml/badge.svg)](https://github.com/shubhwade/telmus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Financial-statement analysis from your terminal.** One command gives you the Piotroski F-score,
Altman Z″-score, Beneish M-score, key ratios and red flags for a listed company, plus an Excel
workbook and an HTML dashboard. An optional MCP server exposes the same analysis to AI coding tools.

```bash
pip install telmus
telmus scan AAPL
```

## Install

Works on Windows 10/11, macOS and Linux with **Python 3.10 or newer**.

```bash
pip install telmus            # or, keeping it isolated:  pipx install telmus
telmus --version
```

Optional MCP server for Claude Desktop, Cursor, Windsurf and similar tools:

```bash
pip install "telmus[mcp]"
```

If `pip` is not found, use `python -m pip install telmus` (Windows: `py -m pip install telmus`).
Upgrade with `pip install -U telmus`.

## Quick start

```bash
telmus scan AAPL                    # tables in the terminal + Excel and HTML reports
telmus scan INFY.NS --no-report     # terminal only: no files written, no browser opened
telmus scan MSFT --json             # machine-readable output
telmus scan AAPL --export aapl.csv  # .json, .csv or .xlsx
telmus compare AAPL MSFT            # side by side
telmus check TSLA                   # just the health scores
telmus --help
```

Tickers use Yahoo Finance symbols. Outside the US add the exchange suffix: `INFY.NS` (NSE),
`RELIANCE.BO` (BSE), `VOD.L` (London), `SAP.DE` (Xetra).

Sample output (illustrative figures, real formatting):

```text
─────────────────────────── Infosys Limited — INFY — NSE ───────────────────────────
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Engine ┃ Metric            ┃ Value ┃ Status ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Health │ Piotroski F-score │ 7     │ ok     │
│ Health │ Altman Z-score    │ 4.00  │ ok     │
│ Health │ Current ratio     │ 2.00  │ ok     │
└────────┴───────────────────┴───────┴────────┘
Screening statistics from public data (Yahoo Finance); not investment advice.
```

## What it computes

| Area | Metrics |
|---|---|
| Health | Piotroski F-score (9 signals), Altman Z″-score, liabilities/equity, current ratio, interest coverage |
| Earnings quality | Beneish M-score (8 variables), negative-equity and free-cash-flow flags |
| Valuation | P/E, P/B, EV/EBITDA |
| Growth | 3-year revenue and profit CAGR, margin trend, FCF yield |

Formulas, sources and limits are in [docs/methodology.md](docs/methodology.md).

**Missing data is never turned into a zero.** If an input is not available the metric shows `n/a`
and a note says why. A score is only shown when everything it needs is present. Banks and insurers
get `n/a` for Altman and Beneish because those models do not apply to them.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | No data for that ticker, or an unexpected error (re-run with `--debug`) |
| 2 | Bad usage, e.g. an invalid ticker |
| 3 | Yahoo Finance unreachable or rate-limiting |

## Troubleshooting

| Problem | Fix |
|---|---|
| `telmus: command not found` | Open a new terminal; with pip use `python -m telmus`, or install with `pipx` |
| `No financial data available` | Check the symbol on finance.yahoo.com and add the exchange suffix |
| Rate limited / unreachable | Wait a few minutes; check proxy/VPN. Telmus retries 3 times automatically |
| `telmus serve` says it needs an extra | `pip install "telmus[mcp]"` |
| Anything else | `telmus --debug scan AAPL` and open an issue with the output |

Charts in the HTML report load Chart.js from a CDN, so they need an internet connection to render.

## MCP server (optional)

```json
{ "mcpServers": { "telmus": { "command": "telmus", "args": ["serve"] } } }
```

## Data and limitations

Data comes from Yahoo Finance through [yfinance](https://github.com/ranaroussi/yfinance), an
unofficial interface: coverage differs by company, figures can be restated or missing, and use is
subject to Yahoo's terms. Statements are annual, in the company's reporting currency. Sector peer
comparison is not implemented. Scores are screening statistics, **not investment advice**.

## Development

```bash
git clone https://github.com/shubhwade/telmus && cd telmus
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check telmus tests && mypy && pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests never use the live internet unless marked `network`.

## License

MIT, see [LICENSE](LICENSE).
