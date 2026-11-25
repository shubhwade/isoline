# Data sources

No free source is complete, accurate, real-time and worldwide at once. Telmus therefore
layers sources, says which one produced each result, and shows `n/a` rather than guessing.

| Source | Status | Coverage | Limits (researched Nov 2026) |
|---|---|---|---|
| Yahoo Finance via `yfinance` | **primary** | Global tickers, price and market cap, statements | Unofficial, no SLA or key; rate limits and label drift (handled in `labels.py`, retry/backoff). Check Yahoo's terms before commercial use. |
| SEC EDGAR XBRL "company facts" | **fallback, implemented (0.5.0)** | US filers only; annual 10-K figures, about five years | Free, no key. SEC asks for a declared User-Agent and at most 10 requests/second. No live price, so valuation multiples are `n/a` from this source. Set `TELMUS_CONTACT` to your email or site. |
| Financial Modeling Prep | not integrated | 250 requests/day on the free plan, end-of-day; free statements limited | Needs the user's own key; global coverage is paid. Candidate for an optional, key-based provider. |
| Alpha Vantage | not integrated | 25 requests/day on the free key | Too small for compare/screen workloads. |
| Finnhub | not integrated | 60 calls/minute free, US only | Standardised statements are not in the free tier. |
| NSE/BSE filings (India) | planned, unresearched | | Terms of use must be checked before any integration. |
| User CSV/Excel import | planned | | Lets users bring licensed data. |
| Paid APIs | not used | | Nothing is purchased by this project. |

## How the fallback works

1. Telmus asks Yahoo Finance (three attempts with backoff).
2. If Yahoo is rate-limited, unreachable or has no statements **and** the ticker looks like a
   plain US symbol (`AAPL`, `BRK-B`), it asks SEC EDGAR.
3. The result carries a note naming the source ("figures come from SEC EDGAR annual
   filings; no live price"), and it appears in every report.
4. Non-US tickers (`INFY.NS`, `VOD.L`) never fall back, because EDGAR does not cover them;
   you get the Yahoo error. Set `TELMUS_NO_FALLBACK=1` to disable the fallback.

The two sources are never blended or averaged. A line item a company did not tag stays missing.

## Not verified live

The EDGAR provider is tested offline against a fixture built from the documented company-facts
format. It could not be run against sec.gov from the development sandbox, so the first real
run (for example with Yahoo blocked) is the live check.
