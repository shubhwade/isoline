# CLI reference

```text
isoline [--version] [--debug] COMMAND [ARGS]
```

`--debug` (or `ISOLINE_DEBUG=1`) shows full tracebacks. Exit codes: `0` ok, `1` no data / other error, `2` bad input (ticker, sector), `3` network or provider unavailable.

Tickers use Yahoo Finance format: `AAPL`, `INFY.NS` (NSE), `500209.BO` (BSE), `VOD.L` (London).

## scan

```bash
isoline scan AAPL
isoline scan INFY.NS --export infy.xlsx        # .xlsx, .csv or .json
isoline scan AAPL --json                        # raw JSON to the terminal
isoline scan AAPL --no-report --no-open         # terminal only, write nothing
```

Prints Valuation, Health, Growth and Quality tables, a rule-based summary and a note for every metric that is n/a. By default it also writes `<TICKER>_analysis.xlsx` and `<TICKER>_dashboard.html` to the current folder and opens the HTML in your browser; `--no-report` / `--no-open` turn that off.

## compare

```bash
isoline compare AAPL MSFT [--export out.xlsx|.csv|.json] [--no-report] [--no-open]
```

## screen

```bash
isoline screen IT --min-piotroski 6 --max-de 1.0
isoline screen Banking --export banks.csv
```

Screens a **small built-in example list** (sectors `IT` and `Banking`, five NSE tickers each), not the whole market. Tickers whose data cannot be fetched or scored are listed as skipped with the reason. Banks are usually skipped because Piotroski and debt/equity are not meaningful for them. An unknown sector exits with code 2 and lists the valid ones.

## check

```bash
isoline check AAPL
```
Prints just the Piotroski F-score and Altman Z″ (and notes), no files.

## powerbi

```bash
isoline powerbi INFY.NS TCS.NS --export portfolio.csv
isoline powerbi --tickers INFY.NS TCS.NS --export flags.csv --flags
```
Writes the CSV plus a `*_report.html` portfolio report. Radar scores for missing metrics are left blank (null), not zero.

## serve

```bash
pip install "isoline[mcp]"
isoline serve
```
Starts the MCP server over stdio. See [MCP](mcp.md).

## info

Prints version, Python version, data source and coverage.
