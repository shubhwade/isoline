# Reports

`isoline scan`, `compare` and `screen` write an HTML report and an Excel workbook; `isoline powerbi` writes a CSV and a portfolio report. Pass `--no-report` to write nothing and `--no-open` to keep the browser closed.

## HTML report (`<TICKER>_dashboard.html`)

The layout follows real documents. The statements look like a company's published annual report (for example a US 10-K): one plain typeface, black type, fiscal years in columns with the newest first, a unit line such as "(In millions of USD, except per-share amounts)", group labels such as **Assets:** with indented line items, a currency sign on the first row and on totals, a single rule above subtotals, a double rule under totals and negatives in parentheses. The rest follows the structure of equity research reports: a key-data block first, then Strengths and Concerns, then the detail.

It is written for first-time readers too: a "How to read this report" box, a "What it shows" line above each statement, a "What it means" sentence next to every measure using the company's own numbers (for example "It has 1.89 of short-term assets for every 1.00 of bills due within a year"), and a glossary.

| Section | Contents |
|---|---|
| Header and key data | Company, ticker, exchange, reporting currency, fiscal years, data source; revenue, net income, free cash flow, Piotroski score, Altman Z″ and the DCF fair value estimate |
| 1 Summary | Rule-based summary (not a recommendation), Strengths and Concerns lists built only from computed figures, contents |
| 2 Financial statements | Income statement, balance sheet and cash flow statement for up to four fiscal years, with "change vs prior year" and common-size columns (% of revenue, % of assets) |
| 3 Key measures explained | Valuation, financial health, growth, profitability and cash, each with a reading and a plain-English meaning |
| 4 Health scores and red flags | The nine Piotroski tests in plain words, Altman Z″, Beneish M, red flags |
| 5 What could the business be worth? | Discounted cash flow: base case, every assumption explained, bear/base/bull cases and a sensitivity grid; or why it could not be calculated |
| 6 Trends over time | Sales, profit and operating margin; whether profit is turning into cash |
| 7 Notes and sources, 8 Glossary | Why each n/a is n/a, method, definitions |

It is self-contained: inline styles and inline SVG only, no JavaScript, web fonts, CDN or network requests, and a Content-Security-Policy that forbids them. It opens offline and prints to A4 with page numbers and repeated table headers (use your browser's Print / Save as PDF). Missing data is `n/a`, never zero; free cash flow and total liabilities and equity are marked † when calculated from reported lines; a balance-sheet check warns when the source data does not balance. Status is always a word, never colour alone. All provider text is HTML-escaped.

`compare` gives each company's strengths and concerns, key figures side by side (in each company's own currency, with a warning when they differ), a measure-by-measure table with a "Stronger" column only where higher or lower is clearly better, and both DCF values. `screen` lists the companies that passed with the rules applied. The portfolio report from `isoline powerbi` lists every company with averages and a company-by-company summary, and names the tickers that could not be analysed.

## Excel workbook (`<TICKER>_analysis.xlsx`)

Dashboard (with margin and revenue charts built from the scan's own data, so the workbook never needs a second download), Summary, Valuation, Health, Growth and Red Flags sheets, plus **Income Statement**, **Balance Sheet** and **Cash Flow** sheets at full precision (costs and outflows negative). Missing values are `n/a`. Text from the data provider can never become a live spreadsheet formula: only Isoline's own sheet references are formulas.
