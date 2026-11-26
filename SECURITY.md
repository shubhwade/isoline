# Security

Report vulnerabilities privately by email to shubhwade@gmail.com (or a GitHub private security
advisory). Please do not open a public issue for security problems.

## What Isoline does to stay safe

- **Network**: outbound requests go only to Yahoo Finance (via yfinance) and, as a fallback for US
  tickers, to fixed `https://www.sec.gov/` and `https://data.sec.gov/` endpoints (any other URL is
  refused). Exporters never make network requests. Isoline stores no credentials.
- **Reports**: HTML reports are self-contained (no JavaScript, CDN, fonts or remote images), all
  third-party text is HTML-escaped, and a Content-Security-Policy forbids scripts and remote loads.
- **Spreadsheets**: text that would start a formula (`=`, `+`, `-`, `@`, tab, CR) is neutralised in
  every CSV, and an .xlsx keeps only Isoline's own sheet-reference formulas (OWASP "CSV injection").
- **Input validation**: tickers, sectors and numeric options are validated with the same rules in
  the CLI, the terminal interface, the SDK and the MCP server, before anything is fetched.
- **Code and supply chain**: no `shell=True`, `eval` or `pickle`; Bandit runs in CI; a weekly
  `pip-audit` checks the installed dependency tree; Dependabot proposes dependency and GitHub
  Actions updates; workflows use least-privilege permissions; releases use PyPI Trusted Publishing.
- **Website**: a Content-Security-Policy allows only the page's own inline scripts by hash.
- `--export` writes to the path you give it; it does not restrict where you write.
