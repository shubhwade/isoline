# Data sources

| Source | Status | Notes |
|---|---|---|
| Yahoo Finance via `yfinance` | implemented | Unofficial, no SLA, label names drift (handled in `labels.py`), rate limits (retry/backoff). Check Yahoo terms before commercial use. |
| SEC EDGAR (XBRL "company facts") | planned | Free, official, US filers only; requires a descriptive User-Agent; best primary source for US fundamentals. |
| NSE/BSE filings (India) | planned, unresearched | Terms of use and data availability must be checked before any integration. |
| User CSV/Excel import | planned | Removes provider risk; lets users bring licensed data. |
| Paid APIs | not used | Nothing is purchased by this project; add only with the owner's approval. |

Reliability stance: never silently fall back to made-up values; report n/a with the reason; reconcile two providers only when both are available.
