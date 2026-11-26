# Reports

`isoline scan`, `compare` and `screen` write an HTML report and an Excel workbook; `isoline powerbi` writes a CSV and a portfolio report. Pass `--no-report` to write nothing and `--no-open` to keep the browser closed.

## HTML report (`<TICKER>_dashboard.html`)

Laid out like a published set of financial statements, with numbered sections and a table of contents. It is **self-contained**: inline styles and inline SVG only, no JavaScript, no web fonts, no CDN, no network requests, and a Content-Security-Policy that forbids all of them. It looks the same offline and prints to A4 with page numbers (use your browser's Print / Save as PDF).

| Section | Contents |
|---|---|
| Cover | Company, ticker, exchange, reporting currency, fiscal years covered, data source, preparation time |
| 1 Summary | Rule-based summary (not a recommendation), key figures for the latest year with year-on-year change, score cards |
| 2 Financial statements | Income statement, balance sheet (assets, liabilities, equity) and cash flow statement for up to four fiscal years, with YoY change and common-size columns (% of revenue, % of total assets) |
| 3 Ratio analysis | Valuation multiples, financial health, growth, profitability and cash quality, each with a "what it measures" column |
| 4 Scoring models and red flags | Piotroski F (all nine signals), Altman Z″, Beneish M, red flags |
| 5 Valuation: discounted cash flow | Base case, every assumption, bear/base/bull scenarios and a discount-rate by terminal-growth grid; or the reason it could not be computed |
| 6 Multi-year trends | Revenue and net income with operating margin; net income against operating and free cash flow |
| 7 Notes and data sources | Why each n/a is n/a, method, disclaimer |

Presentation rules: fiscal years in columns, newest first; one unit per report (for example "USD millions", chosen so the largest figure shows 100 to 99,999); costs and outflows in parentheses; subtotal rules and a double rule under totals; per-share figures unscaled. Missing data is `n/a`, never zero, and a missing year has no chart bar. Free cash flow and total liabilities and equity are marked † when computed from reported lines, and a balance-sheet check warns when assets and liabilities plus equity disagree in the source data. Status is always a word, never colour alone. All provider text is HTML-escaped.

`compare` adds a key-financials table (latest year, in each company's own currency, with a warning when currencies differ), a metric comparison with a "Stronger" column only where a direction is meaningful, and both default DCF values. `screen` lists the companies that passed and the criteria used. The portfolio report lists each company with averages of the reported values and the tickers that could not be analysed.

## Excel workbook (`<TICKER>_analysis.xlsx`)

Dashboard (with margin and revenue charts built from the scan's own data, so the workbook never needs a second download), Summary, Valuation, Health, Growth and Red Flags sheets, plus **Income Statement**, **Balance Sheet** and **Cash Flow** sheets at full precision (costs and outflows negative). Missing values are `n/a`. Text from the data provider can never become a live spreadsheet formula: only Isoline's own sheet references are formulas.
