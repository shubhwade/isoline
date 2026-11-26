# Changelog

## Unreleased
### Fixed
- The README download badge showed only the last 30 days (979) because no pepy.tech API key is set. It now shows all-time downloads of `isoline` and the legacy `telmus` combined as one number (16.7k at the time of writing), read from pepy.tech's public badge when no key is set. If a count cannot be read, the previous badge stays instead of a partial or estimated figure.
- Each nightly badge update also triggered a failed Vercel preview, because the `badges` branch holds only the badge data and has no `website/` folder. The branch now carries a Vercel config that skips deployment.

## v0.9.0
### Added
- **Financial statements** in every scan: income statement, balance sheet and cash flow for up to four fiscal years, newest first, as reported (`isoline statements TICKER`, with `--json` and `--export .csv/.json`; SDK `isoline.sdk.statements()`; MCP tool `statements`). Values are matched to fiscal periods by date and never estimated; free cash flow and total liabilities and equity are marked when computed; a balance check warns when the source data does not balance. Capex, dividends and buybacks are always shown as outflows whatever sign the provider uses.
- **HTML report redesigned after real documents.** The statements follow published annual reports (for example a US 10-K): one plain typeface, black type, a unit line such as "(In millions of USD, except per-share amounts)", group labels with indented items, a currency sign on the first row and totals, single rules above subtotals and double rules under totals, negatives in parentheses, plus change-vs-prior-year and common-size columns. The rest follows equity research reports: a key-data block (revenue, profit, free cash flow, scores, DCF fair value), Strengths and Concerns, then the detail. Written for beginners too: a "How to read this report" box, a "What it shows" line for each statement, a plain-English "What it means" sentence for every measure using the company's own numbers, and a glossary. Includes a discounted-cash-flow section (assumptions explained, three cases, sensitivity grid, or why it could not be calculated); prints to A4 with page numbers.
- Comparison report gains key financials side by side (with a warning when currencies differ) and both default DCF values; the screen report states its criteria.
- **Portfolio report** (from `isoline powerbi`) rebuilt as a self-contained report; it replaces the old dashboard that loaded an unpinned Chart.js from a CDN.
- Excel workbooks gain **Income Statement**, **Balance Sheet** and **Cash Flow** sheets.
- MCP tool `value` (DCF with validated, bounded inputs) and SDK `isoline.sdk.value()`.
- `isoline screen --no-report/--no-open`.

### Security
- Spreadsheet formula injection is neutralised in every CSV and .xlsx written (OWASP "CSV injection"): text from data providers can no longer become a live formula.
- One validator for tickers, sectors and numeric options across the CLI, terminal interface, SDK and MCP server; MCP arguments are type- and range-checked before anything is fetched. Index symbols such as `^GSPC` are now accepted, as documented.
- HTML reports carry a Content-Security-Policy that forbids scripts and remote loads; the website carries one that allows only its own inline scripts by hash (checked by a test).
- The Excel exporter no longer downloads data during export (it re-fetched financials and price history); exporters make no network requests.
- SEC EDGAR requests are restricted to fixed `https://` SEC endpoints.
- CI runs Bandit; a weekly workflow runs `pip-audit` on the installed dependency tree; Dependabot added; workflows use least-privilege permissions and do not persist the checkout token where nothing is pushed.
- Unit tests can no longer reach SEC EDGAR by accident (they now make zero network connections).

### Fixed
- Website browser-tab icon showed a blank globe: the inline icon contained unescaped quotes that cut the attribute short. The site now ships real `favicon.ico`, `favicon.svg`, `icon-192.png` and an Apple touch icon, generated from the logo.
- The website's report preview looked doubled (a page inside a page): the sample image included the report's grey screen background, and the frame drew a second sheet. The image is now the report sheet alone, edge to edge, in a single square-cornered frame.
- Reports show the Isoline mark in their header and as their browser-tab icon (base64-embedded, kept identical to the brand files by a test).
- `isoline serve` printed a configuration snippet to standard output before starting, corrupting the MCP stdio channel (clients logged "Failed to parse JSONRPC message"). Standard output now carries only protocol messages; the hint goes to standard error, and only in a terminal.
- The MCP server works with both MCP Python SDK 1.x and 2.x (2.x replaced the decorator API with constructor handlers); the `mcp` extra now allows `<3`, and CI tests the 1.x path in a separate job. Verified with real stdio sessions on both SDKs.
- A test that timed two concurrent scans with a stopwatch failed on slow CI runners; it now proves concurrency with a barrier.
- A ticker that fails in `isoline powerbi` is skipped and reported instead of aborting the whole export.
- Reports open in the browser by absolute file URI, and a missing browser never fails the command.
- Red flags read in plain English in summaries and reports ("negative free cash flow in 2+ years").

### Changed
- **Brand**: black, white and one vermilion signal colour, replacing navy and amber. The mark is nested contour lines (isolines) around a summit point; the "isoline" wordmark has a vermilion dot on the "i". Light and dark wordmarks and an SVG favicon are generated by `examples/make_brand_assets.py`, with text converted to outlines so they render the same on GitHub, PyPI and the docs.
- **Website** (now at https://isolinee.vercel.app) rebuilt with scroll-driven scenes that use the real engine output for the synthetic sample company: statements loading, the nine Piotroski signals ticking, the Altman Z″ gauge, withheld metrics, a DCF that projects, discounts and stress-tests, and the report scrolling in a browser frame. Interactive ridgeline terrain in the hero, light and dark themes, no third-party scripts. With reduced motion or without JavaScript the page shows every final state as ordinary sections.
- **HTML report and terminal interface** use the same neutral palette. Status colours (good, warning, bad) keep their meaning.
- **Demo GIF and social preview** redone in the new brand (`examples/make_demo_gif.py` also writes `docs/assets/og.png`). `examples/make_sample_assets.py` now renders `sample-report.png` itself.
- Project homepage in the package metadata, the README and the docs header now point to https://isolinee.vercel.app.
### Fixed
- `docs/changelog.md` is in sync with this file again (CI failed on the previous merge because it wasn't).
- Type checking no longer breaks with numpy 2.5 or newer, whose stubs use Python 3.12 syntax that mypy rejects when targeting 3.10.

## v0.8.0
### Added
- **`isoline tui`**: full-screen terminal interface (optional extra: `pip install "isoline[tui]"`, built on Textual). Four distinct workflows (Fundamental, Valuation, Compare, Screening), a command palette (Ctrl+K), session history, keyboard shortcuts, loading and error states. Work runs in a background thread. Tested headlessly with Textual's pilot.
### Changed
- The compare and screen table printers are now shared functions used by both the command line and the terminal interface.

## v0.7.0
### Added
- **`isoline value TICKER`**: discounted-cash-flow estimate (free cash flow to equity, Gordon-growth terminal value, growth fading to terminal) with bear/base/bull scenarios, a discount-rate x terminal-growth sensitivity grid, margin of safety and a `--json` mode. All assumptions are printed; defaults are labelled; nothing is computed from a non-positive cash flow. Documented on the new Valuation page with sources; the arithmetic is covered by hand-checked tests.

## v0.6.2
### Changed
- **Logo redrawn** as a plain geometric mark: a lowercase "i" whose dot sits on a level line (an isoline). The earlier wave motif looked generic.
- **README** now shows a wide animated demo (terminal scan, then the report) instead of two tall screenshots. `examples/make_demo_gif.py` regenerates it from the real engines and a labelled synthetic company.

## v0.6.1
### Changed
- **PyPI and GitHub page.** New README with logo, real terminal and report images (rendered from a labelled synthetic company by `examples/make_sample_assets.py`), and a "formerly Telmus" notice.
### Fixed
- **Report charts:** the value axis stopped at the last tick below the data, so the tallest bars could extend past the top of the chart. The axis now always covers the largest value. Test added.

## v0.6.0 (Isoline)
### Changed
- **Renamed from Telmus to Isoline.** New PyPI project `isoline`, command `isoline`, `import isoline`. Behaviour and formulas are unchanged. Environment variables are now `ISOLINE_*`; the old `TELMUS_*` names still work. The earlier `telmus` releases stay on PyPI; a final `telmus` release (see `legacy/telmus-shim`) installs `isoline` and keeps the old command and import working with a deprecation notice. Download counts of `telmus` do not transfer to `isoline`.

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
