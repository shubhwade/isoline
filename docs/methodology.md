# Methodology

Telmus reads annual statements from Yahoo Finance and reports **screening statistics**, not
investment advice. Rules that apply everywhere:

* A missing input gives `n/a`, never `0`. A genuine zero stays zero.
* A score is shown only when every input it needs exists for the required years.
* Statement rows are looked up by canonical name, so both old and current yfinance labels work.
* Year *t* is the latest fiscal year, *t-1* the one before.

## Piotroski F-score (0-9)

Piotroski (2000), *Value Investing: The Use of Historical Financial Statement Information to
Separate Winners from Losers*, Journal of Accounting Research 38. One point per signal:

| Signal | Passes when |
|---|---|
| ROA positive | Net income(t) / total assets(t-1) > 0 |
| CFO positive | Operating cash flow(t) > 0 |
| ROA improving | ROA(t) > ROA(t-1), each over beginning-of-year assets |
| Low accruals | Operating cash flow(t) > net income(t) |
| Leverage falling | Long-term debt / average total assets lower than last year |
| Liquidity rising | Current ratio(t) > current ratio(t-1) |
| No dilution | Shares outstanding(t) <= shares outstanding(t-1) |
| Gross margin rising | Gross margin(t) > gross margin(t-1) |
| Asset turnover rising | Revenue(t) / total assets(t-1) > same for t-1 |

Needs three balance-sheet years. If any signal cannot be computed the score is withheld and the
missing signals are listed. Designed for value stocks; interpret with care elsewhere.

## Altman Z″-score

Altman (1983/1995) model for non-manufacturers and emerging markets:

`Z″ = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4`

X1 = working capital / total assets, X2 = retained earnings / total assets,
X3 = EBIT / total assets, X4 = **book** equity / total liabilities.
Zones: above 2.6 safe, 1.1-2.6 grey, below 1.1 distress. Not computed for financial firms.

## Beneish M-score

Beneish (1999), *The Detection of Earnings Manipulation*, Financial Analysts Journal 55(5).

`M = -4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI - 0.172·SGAI + 4.679·TATA - 0.327·LVGI`

| Index | Definition |
|---|---|
| DSRI | (Receivables/Sales)(t) ÷ (Receivables/Sales)(t-1) |
| GMI | Gross margin(t-1) ÷ gross margin(t) |
| AQI | [1 - (current assets + net PP&E)/total assets](t) ÷ same(t-1) |
| SGI | Sales(t) ÷ Sales(t-1) |
| DEPI | [Dep/(Dep + net PP&E)](t-1) ÷ same(t) |
| SGAI | (SG&A/Sales)(t) ÷ (SG&A/Sales)(t-1) |
| LVGI | [(current liabilities + long-term debt)/total assets](t) ÷ same(t-1) |
| TATA | (Net income - operating cash flow) / total assets(t) |

TATA uses the cash-flow form of total accruals. A score above **-2.22** raises a high-severity flag
(Beneish's paper also discusses -1.78, which flags fewer companies). Not computed for financial firms.

## Ratios and flags

* **Debt / equity** is total liabilities / shareholders' equity. Not reported when equity <= 0;
  negative equity raises its own high-severity flag.
* **Interest coverage** = EBIT / |interest expense|. EBITDA is never substituted for EBIT.
* **Negative FCF** flag: free cash flow (operating cash flow minus |capex|) negative in 2+ of the last 3 years.
* **Liabilities/equity > 2** raises a medium flag.

## Known limitations

Annual data only; no restatement tracking; no currency conversion (ratios are unit-free, absolute
values are in the reporting currency); fiscal years are not calendar-aligned across companies;
sector peer valuation is not implemented; data quality is bounded by Yahoo Finance.
