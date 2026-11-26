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

## value

```bash
isoline value AAPL --discount 0.09 --growth 0.07
isoline value MSFT --json
```

DCF estimate with scenarios and a sensitivity grid. See [Valuation](valuation.md) for the method and assumptions.

## statements

```bash
isoline statements AAPL
isoline statements INFY.NS --export infy_statements.csv
isoline statements MSFT --json
```

The income statement, balance sheet and cash flow statement for up to four fiscal years, newest first, as reported. Amounts are shown in one unit (for example USD millions) with costs and outflows in parentheses. Lines a company did not report show `n/a`; free cash flow and total liabilities and equity are marked `*` when they are computed from reported lines. If the balance sheet does not balance in some year, a warning says so. `--export` writes `.csv` or `.json`.

## screen

```bash
isoline screen IT --min-piotroski 6 --max-de 1.0
isoline screen Banking --export banks.csv
```

Options: `--export FILE`, `--no-report` (write no Excel/HTML), `--no-open` (do not open the report). `--min-piotroski` must be 0 to 9 and `--max-de` 0 to 1000.

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
Writes the CSV plus a `*_report.html` portfolio report (one row per company, averages of reported values, and a summary per company). A ticker that cannot be loaded is skipped and listed, instead of aborting the export; the command fails only if no ticker could be analysed.

## serve

```bash
pip install "isoline[mcp]"
isoline serve
```
Starts the MCP server over stdio. See [MCP](mcp.md).

## info

Prints version, Python version, data source and coverage.
