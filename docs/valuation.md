# Valuation (DCF)

```bash
isoline value AAPL --discount 0.09 --growth 0.07 --terminal 0.025 --years 5
isoline value MSFT --json
```

`isoline value` estimates the equity value of a company from its own reported cash flow and
shows every assumption, three scenarios and a sensitivity grid. It is an illustration of what
your assumptions imply. It is **not a price target, a recommendation or investment advice.**

## Method

| Step | What is done |
|---|---|
| Cash flow | Free cash flow = operating cash flow minus the absolute capital expenditure. It is measured after interest, so it approximates free cash flow to equity. |
| Base | Mean of up to the last three reported years, to smooth one-off swings. If this is not positive the DCF is not computed (a perpetuity of a negative cash flow has no meaningful value). |
| Growth | Year-1 growth (`--growth`, default: 3-year revenue CAGR limited to 0-15%) fades linearly to terminal growth by the last explicit year. |
| Terminal value | Gordon growth: FCF in the last year x (1 + g) / (r - g), discounted back. Requires r > g. |
| Equity value | Present value of the explicit cash flows plus the present value of the terminal value. Because the cash flow is already after interest, **net debt is not subtracted again**. |
| Per share | Equity value divided by shares outstanding. |
| Margin of safety | (value per share - price) / value per share, only when price and the estimate are in the same currency. |

Scenarios: **Bear** halves growth and adds 1 point to the discount rate; **Bull** multiplies growth
by 1.25 and subtracts 1 point; **Base** uses your inputs. The grid varies the discount rate by +/-2
points and terminal growth by +/-1 point.

## Assumptions you must own

- **Discount rate.** The default of 10% is a placeholder, not an estimate of any company's cost
  of equity. Set `--discount`.
- **Terminal growth.** Stable growth should not exceed the growth of the economy; the risk-free
  rate is a common cap (Damodaran). Isoline flags terminal growth above 4%.
- **Terminal weight.** When more than 75% of the value comes from the terminal value the output says so.

## When it returns "not computed"

Missing cash-flow items, a non-positive average free cash flow, too little revenue history to
derive growth (pass `--growth`), or a discount rate at or below terminal growth. Data fetched
from the SEC fallback has no market price, so the margin of safety is `n/a`.

## Sources

- Damodaran, *Getting Closure in Valuation* (terminal value, stable growth cannot exceed the economy's growth): <https://pages.stern.nyu.edu/~adamodar/pdfiles/valonlineslides/session9.pdf>
- Damodaran, *Terminal value* notes (risk-free rate as a cap on stable growth): <https://pages.stern.nyu.edu/~adamodar/pdfiles/country/TerminalValue.pdf>
