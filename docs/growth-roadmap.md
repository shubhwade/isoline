# Growth roadmap: toward 100,000 cumulative downloads

Targets, not promises. PyPI download counts include CI runs, mirrors and re-installs, so they are
**not unique users**. No bots, purchased traffic or misleading claims. Record the current number
at pepy.tech/projects/telmus (and pypistats.org) before starting: that is month 0.

| Milestone | Target month | What has to be true |
|---|---|---|
| 15K | 3 | v0.4.x is the stable, easy install; first tutorials and a launch post are out |
| 25K | 5 | Telmus is used in public notebooks / blog posts by people other than the author |
| 50K | 8 | Listed in awesome-lists and an MCP directory; some downstream tool depends on it |
| 75K | 11 | Regular contributors; second wave of features (peer valuation, DCF) shipped |
| 100K | 12 | Compounding: search traffic, recommendations, CI/dependency installs |

## Why people will install it (and recommend it)
1. **It works first time.** `pip install telmus && telmus scan AAPL`, on every OS. This release fixes the crash that hit fresh installs.
2. **It is correct and says so.** Published formulas with citations and hand-computed tests (docs/methodology.md). "Shows n/a rather than guessing" is a differentiator versus scraped-ratio tools.
3. **It produces something shareable:** an Excel workbook and a print-ready HTML report from one command, plus an MCP server for AI coding tools.

## Months 1-3: foundation (to 15K)
- Release the current version; GitHub release notes; pin the README badges; add topics: `finance`, `piotroski`, `altman-z-score`, `beneish`, `stock-analysis`, `yfinance`, `mcp`, `cli`.
- Record a 60-second terminal GIF from a **real** run; add it to the README and the PyPI page.
- Write three tutorials: "Screen for weak balance sheets with the Piotroski F-score", "Spot earnings manipulation with the Beneish M-score in Python", "Give Claude/Cursor real financial ratios with MCP". Publish on the project docs, dev.to and Medium; cross-link to the repo.
- Post once, honestly, to r/Python, r/algotrading, r/SecurityAnalysis, r/mcp and "Show HN": what it is, what it does not do, how it is validated. Answer every comment.
- Open "good first issue" tickets (new ratios, other data providers, tests).

## Months 4-6: distribution (to 25-50K)
- Submit to awesome-python, awesome-quant, awesome-mcp-servers and MCP registries/directories; Python Weekly, PyCoder's Weekly, Console.dev newsletters.
- YouTube demo (5 min) and a short for each tutorial; ask finance-Python creators for honest feedback, not endorsements.
- Add a Jupyter/Colab notebook so people can try it without installing.
- Add a `telmus.sdk` quick example to the README (library use drives installs in other projects' requirements).

## Months 7-12: depth (to 100K)
- Features that earn recommendations: peer/sector valuation from a documented data source, DCF template workbook, watchlist/portfolio reports, a second data provider (reduces Yahoo dependence).
- Conference/meetup talks (PyCon India, local Python meetups); a "How we validate financial formulas" blog post.
- Monthly releases with changelogs; respond to issues within 48 hours.
- Integrations: GitHub Action that posts a scan on a watchlist; pre-built MCP config snippets for each AI IDE.

## Track monthly
Downloads (total and last 30 days, excluding mirrors where pypistats allows), GitHub stars, forks,
unique contributors, open/closed issues and median response time, PRs merged, releases, docs
visits (enable a privacy-friendly analytics tool if wanted), newsletter/community mentions.
Review each milestone honestly; if a channel does not move numbers after two tries, drop it.

## Risks
Yahoo Finance changes or blocks scraping (mitigation: second provider, clear errors); a wrong number
damaging trust (mitigation: tests, citations, "not investment advice"); download counts inflated by
CI (mitigation: report stars/contributors alongside downloads).
