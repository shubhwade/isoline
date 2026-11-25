# Changelog

## v0.5.0
### Added
- **SEC EDGAR fallback.** When Yahoo Finance is rate-limited, unreachable or has no statements for a US ticker, Telmus now reads the official annual XBRL facts from SEC EDGAR (free, no key, polite rate limiting, declared User-Agent via `TELMUS_CONTACT`). Results are labelled with their source in the notes; there is no live price from this source, so valuation multiples are `n/a`. Non-US tickers do not fall back. `TELMUS_NO_FALLBACK=1` disables it. Tested offline against a fixture; not yet verified live.
- Data sources page rewritten with researched limits of the other free APIs (FMP, Alpha Vantage, Finnhub) and why they are not bundled.

## v0.4.4
### Fixed
- **`telmus compare` crashed** with `ValueError: I/O operation on closed file`. The two tickers are scanned concurrently and each scan silenced provider output with `contextlib.redirect_stdout`, which is process-wide; overlapping scans restored each other's streams in the wrong order and left `sys.stdout` closed. Output is now silenced by a ref-counted guard that restores the original streams exactly once. Regression test added.
- **compare**: the terminal table, CSV export and HTML report now share one definition (`telmus/core/comparison.py`). Valuation multiples are shown but never ranked; a missing value never wins; a real 0 is kept in CSV (only missing values are empty).
- The hidden `comp` alias now accepts `--export/--report/--no-report/--open/--no-open`; company names with spaces produce valid file names; `scan --json` prints raw JSON (no wrapping or markup).
- New end-to-end test file covering every command with a mocked provider.

## v0.4.3
### Changed
- **Repository layout.** The root now holds only standard files (README, LICENSE, CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, pyproject, mkdocs.yml). Project docs moved to `docs/project/` (architecture, data sources, release process, roadmap, growth plan) and internal notes to `docs/internal/` (kept out of the published site). The Streamlit app moved from `dashboard/` to `examples/`. Removed `scripts/capture.py` (a one-off screenshot helper with hard-coded personal paths) and an unused logo file. `.gitignore` reorganised and now ignores `.pypirc`.

## v0.4.2
### Changed
- **Report fonts and charts.** Headings use Times New Roman and numbers use a lining, tabular sans-serif (Georgia's old-style digits made figures look uneven). Scan reports now include two inline-SVG charts built from up to four fiscal years of real statement data, matched by date: revenue and net income with operating margin, and net income vs operating cash flow vs free cash flow. A year that was not reported has no bar (never a zero bar). New `history` field in the JSON output.
- **Docs site.** New Reports page; Architecture, Data sources, Release process, Roadmap and Changelog are now published in the docs navigation (a test keeps the root files and their docs copies identical and checks that every page is in the nav). The docs workflow builds with `--strict` before deploying.
- Website and README text updated to describe the report accurately (no more "interactive dashboard with gauges, radar charts"; no CDN claim).

## v0.4.1
### Changed
- **Reports rebuilt.** The HTML scan, compare and screen reports are now formal, print-ready documents: light layout, serif headings, tables with "what it measures" columns, status words (Strong / Adequate / Weak / n/a) instead of colour alone, a Piotroski signal table, notes explaining every n/a, and a disclaimer. They are fully self-contained (no JavaScript, no Chart.js CDN, no web fonts, no logo lookups), so they look the same offline and print cleanly. This also fixes the misaligned, differently sized gauges.
- **Speed.** Statements are fetched concurrently (about the slowest request instead of the sum of four); `compare` scans both tickers at the same time; the unused `fast_info` request and the per-report logo lookup (an extra network call) are gone.

## v0.4.0
### Fixed (reports, docs, screening: found in a second, deeper audit)
- **HTML report** showed missing data as `0` (P/E 0.0, "HEALTH: WEAK", "GROWTH: DECLINING", "VALUATION: FAIR", "Beneish 0.00 = low manipulation risk") and unavailable Piotroski signals as failures. It now shows `n/a`, "N/A" badges and neutral signal markers. The header said v0.2.6 and the footer printed a literal `{telmus_version}`; both now show the real version.
- **Excel report** header said v0.1.0, used the old Altman thresholds (2.99/1.81) and showed "ok" for n/a rows; now correct, with the n/a reasons listed on the Summary sheet.
- **Power BI** radar scored a missing leverage as a perfect 10 and other gaps as 0; gaps are now blank.
- **screen**: an unknown sector silently screened IT; now exit code 2 with the valid sectors. Tickers that fail are reported as skipped with the reason instead of vanishing. The MCP `screen` tool scanned bare symbols (US listings) instead of NSE tickers; it now shares the CLI's universe.
- **MCP** `scan_ticker` ignored its `exchange` argument; it now applies it (`INFY` + `NSE` = `INFY.NS`).
- **CLI**: `telmus check` printed "n/a" for a legitimate score of 0; percentages now display as percentages; n/a rows show an n/a status, not "ok".
- Summary text no longer says "Suitable for DCF or comparable company analysis" (that read as a recommendation) and has correct capitalisation; "AI Analyst Brief" renamed "Summary (rule-based)" because it is not AI.
- Website showed real companies (INFY, AAPL, RELIANCE, MSFT) with numbers from the pre-fix formulas; replaced with clearly labelled synthetic samples. Removed the unverifiable "50,000+ tickers" claim and the wrong "Python 3.9+".

### Changed
- `from telmus import scan, compare, TelmusScanner, ScanResult` now works as documented (lazy import). `telmus.sdk` exports the error classes.
- Docs rewritten from the actual behaviour: SDK, CLI, MCP (stdio, not a port), Quickstart, homepage. They previously described methods and options that did not exist and showed invented example numbers.

## v0.3.3
### Added
- **Quality metrics** (`ScanResult.quality`, CLI "Quality" table, HTML report section): DuPont ROE decomposition, ROIC, free-cash-flow margin and FCF/net income, accruals ratio, DSO/DIO/DPO, cash conversion cycle, share-count change. Formulas in `docs/methodology.md`; missing inputs give n/a with a note.
- Release safeguards: `RELEASES_DISABLED` kill switch, PyPI version-conflict check, post-release smoke test (see Release process).
- Project docs: ROADMAP, ARCHITECTURE, DATA_SOURCES, RELEASE_PROCESS, BUSINESS_STRATEGY, COMPETITOR_RESEARCH, PROJECT_STATUS.

## v0.3.2
First published release containing everything below (tags v0.3.0 and v0.3.1 were created but never published; the release workflow now supports PyPI Trusted Publishing).

### Fixed
- **Install:** `pip install telmus` produced a CLI that crashed on every command when pip picked `mcp` 2.x. `mcp` is now an optional extra (`pip install "telmus[mcp]"`, pinned `<2`); the CLI no longer imports it unless you run `telmus serve`.
- **Beneish M-score** was not Beneish's model (DSRI was a gross-margin ratio, LVGI used interest expense, TATA had the wrong sign and denominator) and returned nothing on current yfinance data. Rewritten per the paper, with hand-computed tests. **Reported M-scores change.**
- **Altman Z″** now uses book equity / total liabilities as in the paper (was market cap), and no longer falls back to total equity or zero when retained earnings are missing. **Reported Z-scores change.**
- **Piotroski F-score** follows the paper (beginning-of-year assets, long-term debt / average assets, share count instead of par value). A missing signal now withholds the score instead of counting as a fail. **Reported F-scores change.**
- yfinance row names: both legacy and current labels are supported (previously Beneish and D/E silently returned nothing).
- Free-cash-flow flag mis-added capex when yfinance reports it as a negative number.
- Valuation: `Series or Series` crash when a "Cash" row existed; invented peer comparison removed (`vs_sector` is now `n/a`).
- HTML reports escape company names and other third-party text.
- Interest coverage no longer substitutes EBITDA for EBIT; negative equity no longer yields a negative debt/equity.

### Added
- `telmus --version`, `--debug`; `scan`/`compare` accept `--no-report` and `--no-open`.
- Friendly errors with hints and exit codes (0 ok, 1 no data/error, 2 usage, 3 network); no tracebacks unless `--debug`.
- Ticker validation; automatic retry with backoff for network and rate-limit errors.
- `notes` in scan results explaining every `n/a`; disclaimer in CLI output.
- 40+ new tests (hand-computed formulas, errors, retries, escaping); tests run offline.
- CI on Windows, macOS and Linux for Python 3.10-3.13, with clean-wheel install checks; release workflow checks tag == version.
- docs/methodology.md, CONTRIBUTING, CODE_OF_CONDUCT, issue and PR templates.

### Changed
- Minimum Python is 3.10 (the previous 3.9 claim was untrue: `mcp` needs 3.10).
- Version has a single source: `telmus/__init__.py`.
- Removed one-off scripts from `scripts/` and a scratch network script from `tests/`.

## v0.2.6
- Metadata audit.

## v0.2.3
- MCP server stability improvements, sector screener, HTML dashboard print support.

## v0.2.0
- Beneish M-score engine, Excel report generation, HTML dashboard.

## v0.1.0
- Initial release: Piotroski F-score, Altman Z-score; CLI scan, compare, check, serve.
