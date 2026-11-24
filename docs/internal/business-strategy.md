# Business strategy (draft - hypotheses, not facts)

## Positioning
An open-source, scriptable, **explainable** fundamentals toolkit for developers and analysts: every score shows its inputs and says n/a when data is missing. It is a CLI + Python library + MCP server, which GUI-only screeners do not offer.

## Evidence so far (see [competitor research](competitor-research.md))
Retail screeners charge roughly: Screener.in Premium Rs 4,999/yr, Tickertape Pro Rs 399/mo or Rs 2,999/yr, Trendlyne PRO Rs 8,900/yr, Simply Wall St about $10-20/mo (all as found in searches during this project; re-verify before use). So paid willingness exists for polished GUIs with curated data; an open library competes on openness and automation, not on data.

## Monetisation options (none implemented)
1. Free OSS core (current).
2. Hosted web app / reports with a free tier and a paid tier - needs licensed data first; cost depends on the data vendor, which is not yet chosen.
3. Sponsorship/consulting around the library.
Unit economics cannot be stated honestly until a data source and its cost are chosen; no market-size figures are claimed here.

## Regulatory (India) - not legal advice
The SEBI (Research Analysts) Regulations, 2014 require registration to act as, or hold out as, a research analyst, and research with buy/sell/hold recommendations is covered. Telmus therefore reports data and scores, includes a disclaimer, and must not issue recommendations or target prices unless the owner obtains advice from a securities lawyer.

## Growth (hypotheses to test)
Useful README and demo GIF, PyPI keywords, Show HN / r/algotrading / r/IndiaInvestments posts, MCP directory listings, integration examples (notebooks). Measure: PyPI downloads (pepy/pypistats), GitHub stars, install-smoke pass rate, issue response time. Privacy-friendly: no telemetry in the package.
