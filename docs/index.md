---
template: home.html
---

# telmus

Financial statement analysis from your terminal, Python, or an AI coding assistant (MCP).

## What it computes

| Engine | What it covers |
|---|---|
| Valuation | P/E, P/B, EV/EBITDA |
| Health | Piotroski F-score, Altman Z″, debt/equity, current ratio, interest coverage |
| Growth | 3-year revenue and profit CAGR, operating-margin trend, FCF yield |
| Quality | DuPont ROE, ROIC, FCF margin, accruals, cash conversion cycle, share dilution |
| Red flags | Beneish M-score, negative equity, negative free cash flow, leverage, liquidity |

Every formula is documented in [Methodology](methodology.md) and checked by hand-computed tests. **When the data needed for a metric is missing, telmus shows `n/a` and says why. It never substitutes zero.**

## Features

- **Reports:** each scan can write an Excel workbook and an HTML dashboard (`--no-report` to skip).
- **Data:** Yahoo Finance via `yfinance`. No API key needed. It is an unofficial source: coverage varies by company and exchange, and values can be delayed or wrong.
- **Python SDK** and **MCP server** (optional extra) on the same engine.
- **Local:** runs on your machine; telmus sends no telemetry.

## The summary

Each scan includes a short, rule-based text summary built from the numbers (no generative model), for example:

> Strong fundamentals (Piotroski F-score of 8). Financially safe (Altman Z-score of 4.65). Operating margins are improving. No red flags were triggered by the checks that could be run.

It describes the data; it is not a recommendation.

## Quick start

```bash
pip install telmus
telmus scan AAPL
telmus scan INFY.NS
```

See the [Quickstart](quickstart.md), [CLI](cli.md), [SDK](sdk.md) and [MCP](mcp.md) pages.

*Telmus provides screening statistics from public data. It is not investment advice and is not a SEBI-registered research analyst or investment adviser.*
