# Changelog

## v0.3.1
First release containing everything below (a v0.3.0 tag was created but never published).

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
