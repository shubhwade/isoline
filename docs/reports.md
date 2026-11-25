# Reports

`isoline scan`, `compare` and `screen` can write two files. Pass `--no-report` to write nothing.

## HTML report (`<TICKER>_dashboard.html`)

A formal, print-ready document. It is **self-contained**: inline styles and inline SVG only, no JavaScript, no web fonts, no CDN, no network requests. It looks the same offline and prints cleanly to A4 or Letter (use your browser's Print / Save as PDF).

| Section | Contents |
|---|---|
| Summary | Rule-based text summary (not a recommendation) |
| Score cards | Piotroski F, Altman Z″, Beneish M, debt/equity, each with a status word |
| Valuation, Financial health, Growth | Tables with a "what it measures" column |
| Performance charts | (1) Revenue and net income by fiscal year with operating margin on a right axis; (2) net income vs operating cash flow vs free cash flow |
| Profitability and cash quality | DuPont ROE, ROIC, FCF margin, accruals, cash conversion cycle, dilution |
| Piotroski signals | Pass / Fail / n/a for each of the nine tests |
| Red flags | Triggered checks, or a statement that none were triggered by the checks that could run |
| Data notes | One line for every metric shown as n/a, and why |

Rules the report follows: status is always a word, never colour alone; missing data is `n/a`, and a missing year has no bar (never a zero bar); all provider text is HTML-escaped; amounts are labelled with their currency and scale (for example "USD billions"). Charts cover up to four fiscal years, matched by date.

`compare` produces a side-by-side table with a "Stronger" column only for metrics where a direction is meaningful (valuation multiples never get a winner). `screen` produces a results table.

## Excel workbook (`<TICKER>_analysis.xlsx`)

Dashboard, Summary, Valuation, Health, Growth and Red Flags sheets. Missing values are `n/a`; the reasons are listed on the Summary sheet. The Excel workbook does not yet include the Quality metrics (planned).
