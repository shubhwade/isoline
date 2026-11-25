# isoline

[![PyPI version](https://img.shields.io/pypi/v/isoline)](https://pypi.org/project/telmus/)
[![Downloads](https://static.pepy.tech/personalized-badge/isoline?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/isoline)
[![Python](https://img.shields.io/pypi/pyversions/isoline)](https://pypi.org/project/telmus/)
[![CI](https://github.com/shubhwade/telmus/actions/workflows/ci.yml/badge.svg)](https://github.com/shubhwade/telmus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Financial-statement analysis from your terminal.** One command gives you the Piotroski F-score,
Altman Z″-score, Beneish M-score, key ratios and red flags for a listed company, plus an Excel
workbook and a print-ready HTML report. An optional MCP server exposes the same analysis to AI coding tools.

```bash
pip install isoline
isoline scan AAPL
```

## Install

Works on Windows 10/11, macOS and Linux with **Python 3.10 or newer**.

```bash
pip install isoline            # or, keeping it isolated:  pipx install isoline
isoline --version
```

Optional MCP server for Claude Desktop, Cursor, Windsurf and similar tools:

```bash
pip install "isoline[mcp]"
```

If `pip` is not found, use `python -m pip install isoline` (Windows: `py -m pip install isoline`).
Upgrade with `pip install -U isoline`.

## Quick start

```bash
isoline scan AAPL                    # tables in the terminal + Excel and HTML reports
isoline scan INFY.NS --no-report     # terminal only: no files written, no browser opened
isoline scan MSFT --json             # machine-readable output
isoline scan AAPL --export aapl.csv  # .json, .csv or .xlsx
isoline compare AAPL MSFT            # side by side
isoline check TSLA                   # just the health scores
isoline --help
```

Tickers use Yahoo Finance symbols. Outside the US add the exchange suffix: `INFY.NS` (NSE),
`RELIANCE.BO` (BSE), `VOD.L` (London), `SAP.DE` (Xetra).

Sample output (a **synthetic** company with deliberately incomplete data, real formatting):

```text
───────────────────── Acme Corp (synthetic) — ACME — DEMO ─────────────────────
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Engine ┃ Metric            ┃ Value ┃ Status ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Health │ Piotroski F-score │ 8     │ ok     │
│ Health │ Altman Z-score    │ 4.65  │ ok     │
│ Health │ Current ratio     │ 2.00  │ ok     │
└────────┴───────────────────┴───────┴────────┘
Note: ROIC not reported: effective tax rate unavailable (no rate is assumed).
Screening statistics from public data (Yahoo Finance); not investment advice.
```

## What it computes

| Area | Metrics |
|---|---|
| Health | Piotroski F-score (9 signals), Altman Z″-score, liabilities/equity, current ratio, interest coverage |
| Earnings quality | Beneish M-score (8 variables), negative-equity and free-cash-flow flags |
| Valuation | P/E, P/B, EV/EBITDA |
| Growth | 3-year revenue and profit CAGR, operating-margin trend, FCF yield |
| Quality | DuPont ROE, ROIC, FCF margin, accruals ratio, cash conversion cycle, share dilution |

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
| `isoline: command not found` | Open a new terminal; with pip use `python -m isoline`, or install with `pipx` |
| `No financial data available` | Check the symbol on finance.yahoo.com and add the exchange suffix |
| Rate limited / unreachable | Wait a few minutes; check proxy/VPN. Isoline retries 3 times automatically |
| `isoline serve` says it needs an extra | `pip install "isoline[mcp]"` |
| Anything else | `isoline --debug scan AAPL` and open an issue with the output |

The HTML report is fully self-contained (no scripts, fonts or CDN), so it opens and prints the same offline.

## MCP server (optional)

```json
{ "mcpServers": { "isoline": { "command": "isoline", "args": ["serve"] } } }
```

## Data and limitations

Data comes from Yahoo Finance through [yfinance](https://github.com/ranaroussi/yfinance), an
unofficial interface: coverage differs by company, figures can be restated or missing, and use is
subject to Yahoo's terms. Statements are annual, in the company's reporting currency. Sector peer
comparison is not implemented. Scores are screening statistics, **not investment advice**.

## Development

```bash
git clone https://github.com/shubhwade/telmus && cd isoline
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check isoline tests && mypy && pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests never use the live internet unless marked `network`.

### Repository layout

```text
isoline/          the package (cli/, core/ engines, exporters/, mcp/, sdk/)
tests/           offline test suite
docs/            documentation site (MkDocs): guides, methodology, project docs
examples/        runnable examples (Streamlit app)
website/         the landing page
.github/         CI, release and docs workflows, issue/PR templates
```

Architecture, data sources, the release process and the roadmap are in [docs/project](docs/project/).

## License

MIT, see [LICENSE](LICENSE).
