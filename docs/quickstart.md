# Quickstart

## 1. Install

Python 3.10 or newer.

```bash
pip install telmus
telmus --version
```

Use a virtual environment (`python -m venv .venv`) and avoid creating it inside a cloud-synced folder such as OneDrive, which can corrupt installs on Windows.

## 2. Scan a stock

```bash
telmus scan AAPL          # US
telmus scan INFY.NS       # NSE (India); BSE uses .BO
```

Tickers use Yahoo Finance symbols. Non-US stocks need the exchange suffix.

The output has Valuation, Health, Growth and Quality tables, a rule-based summary, and a line for every metric that could not be computed. This is real output on a **synthetic** company with deliberately incomplete data (not a real stock):

```text
Valuation   P/E ratio 25.00 | P/B ratio 5.00 | EV/EBITDA n/a
Health      Piotroski F-score 8 | Altman Z-score 4.65 | Debt/Equity 0.83 | Current ratio 2.00
Growth      Revenue CAGR 3y n/a | Margin trend improving | FCF yield 3.0%
Quality     ROE (DuPont) 21.4% | Net margin 12.0% | ROIC n/a | Cash conversion (days) n/a

Note: ROIC not reported: effective tax rate unavailable (no rate is assumed).
```

By default a scan also writes `<TICKER>_analysis.xlsx` and `<TICKER>_dashboard.html` in the current folder and opens the HTML. Use `--no-report --no-open` for terminal-only output.

## 3. Reading the scores

| Metric | How to read it |
|---|---|
| Piotroski F (0-9) | 8-9 strong, 5-7 average, 0-4 weak. Only reported when all nine signals are computable. |
| Altman Z″ | above 2.6 safe, 1.1-2.6 grey zone, below 1.1 distress. Not applicable to banks and insurers. |
| Beneish M (8-variable) | above -2.22 suggests possible earnings manipulation. Not applicable to financial firms. |
| FCF yield | (operating cash flow minus capex) / market cap |
| ROIC | EBIT x (1 - effective tax rate) / average invested capital |
| Cash conversion cycle | DSO + DIO - DPO, in days |

Exact definitions: [Methodology](methodology.md). A flagged score is a prompt to look closer, not a verdict.

## 4. JSON and exports

```bash
telmus scan AAPL --json
telmus scan AAPL --export aapl.json      # .json, .csv or .xlsx
```

## 5. Compare two stocks

```bash
telmus compare AAPL MSFT
```

## 6. Files written

| Command | Files |
|---|---|
| `scan T` | `T_analysis.xlsx`, `T_dashboard.html` |
| `compare A B` | `AvsB_comparison.xlsx`, `AvsB_dashboard.html` |
| `screen IT` | printed table; `--export` for `.xlsx`/`.csv`/`.json` |

## Troubleshooting

- `Could not reach Yahoo Finance`: check your connection or proxy, and retry in a minute (Yahoo rate-limits).
- `No data`: check the symbol and exchange suffix on finance.yahoo.com.
- Add `--debug` to any command for the full traceback when reporting an issue.
