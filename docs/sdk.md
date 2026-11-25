# Python SDK

```bash
pip install isoline
```

```python
from isoline import scan, compare, IsolineScanner, ScanResult, CompareResult
```

`import isoline` is lightweight; the SDK loads on first use. Everything here is tested offline in `tests/test_sdk.py`. Names not listed on this page are internal and may change.

## Functions

| Call | Returns |
|---|---|
| `scan(ticker)` | `ScanResult` |
| `compare(ticker_a, ticker_b)` | `CompareResult` (`.ticker_a`, `.ticker_b`, `.result_a`, `.result_b`) |
| `isoline.sdk.compare_to_dataframe(compare_result)` | `pandas.DataFrame` indexed by metric, one column per ticker |
| `IsolineScanner().scan(t)` / `.compare(a, b)` | same as above; use when you want one reusable scanner |

Tickers use Yahoo Finance format: `AAPL`, `INFY.NS` (NSE), `500209.BO` (BSE).

## ScanResult

| Field | Type | Notes |
|---|---|---|
| `ticker`, `company`, `exchange` | str | |
| `valuation` | `ValuationResult` | `pe_ratio`, `pb_ratio`, `ev_ebitda`, `vs_sector` (always `None`: no peer data), `flag` |
| `health` | `HealthResult` | `piotroski_f` (int or `None`), `piotroski_signals` (dict of the signals that were computable), `altman_z`, `debt_to_equity`, `current_ratio`, `interest_coverage`, `flag`, `notes` |
| `growth` | `GrowthResult` | `revenue_cagr_3y`, `pat_cagr_3y` (fractions, 0.10 = 10%), `margin_trend` (`"improving"`/`"stable"`/`"declining"`), `fcf_yield`, `flag` |
| `quality` | `QualityResult` | DuPont (`net_margin`, `asset_turnover`, `equity_multiplier`, `roe`), `roic`, `fcf`, `fcf_margin`, `fcf_to_net_income`, `accruals_ratio`, `dso_days`, `dio_days`, `dpo_days`, `cash_conversion_cycle_days`, `share_count_change`, `notes` |
| `beneish_m` | float or `None` | flagged as a possible manipulator above -2.22 |
| `red_flags` | list of `RedFlag(type, value, severity)` | |
| `highest_concern` | str | `"low"`, `"medium"` or `"high"` |
| `analyst_brief` | str | rule-based text summary, not advice |
| `notes` | list[str] | one line for every metric that is `None`, saying why |
| `scan_duration_ms`, `schema_version` | int | |

**Missing data is `None`, never `0`.** Check `result.notes` to see why a value is missing (for example, banks have no meaningful Altman Z″ or Beneish M).

Methods: `result.to_dict()` and `result.to_json()` (stable shape, `schema_version` 1).

## Errors

All inherit `IsolineError` (a `ValueError`) and carry a `.hint`:
`InvalidTickerError`, `NoDataError`, `ProviderUnavailableError`, `RateLimitError`.

```python
from isoline import scan
from isoline.sdk import IsolineError

try:
    r = scan("INFY.NS")
except IsolineError as exc:
    print(exc, "->", exc.hint)
```

## Examples

```python
from isoline import scan

r = scan("AAPL")
print(r.health.piotroski_f, r.health.altman_z, r.quality.roic)
for note in r.notes:
    print("n/a because:", note)
```

```python
import pandas as pd
from isoline import scan

rows = []
for t in ["INFY.NS", "TCS.NS", "WIPRO.NS"]:
    try:
        r = scan(t)
    except Exception as exc:          # one bad ticker should not stop the loop
        print("skipped", t, exc)
        continue
    rows.append({"ticker": t, "F": r.health.piotroski_f, "Z": r.health.altman_z,
                 "ROIC": r.quality.roic, "CCC days": r.quality.cash_conversion_cycle_days})
print(pd.DataFrame(rows))
```

```python
import json
from isoline import scan
open("aapl.json", "w", encoding="utf-8").write(scan("AAPL").to_json())
```

Data comes from Yahoo Finance via `yfinance` (unofficial, may be delayed or incomplete). Output is screening statistics, not investment advice.
