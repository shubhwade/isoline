# Security

Report vulnerabilities privately by email to shubhwade@gmail.com (or a GitHub private security
advisory). Please do not open a public issue for security problems.

Notes
- Telmus makes outbound requests only to Yahoo Finance (via yfinance) and, for HTML reports, to
  public CDNs for Chart.js and company logos. It stores no credentials.
- Report pages HTML-escape all third-party text (company names, exchanges, flags).
- `--export` writes to the path you give it; it does not validate or restrict it.
- No `shell=True` or `eval` is used (the earlier `shell=True` issue was fixed in v0.2.0).
