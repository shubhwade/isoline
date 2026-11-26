from __future__ import annotations

import time
from typing import Any

from isoline.core.brief import generate_brief
from isoline.core.engines.flags import FlagsEngine
from isoline.core.engines.growth import GrowthEngine
from isoline.core.engines.health import HealthEngine
from isoline.core.engines.history import HistoryEngine
from isoline.core.engines.quality import QualityEngine
from isoline.core.engines.statements import StatementsEngine
from isoline.core.engines.valuation import ValuationEngine
from isoline.core.loaders import load_financials
from isoline.core.result import CompareResult, ScanResult


def _default_dcf(financials: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    """Default-assumption DCF (its notes explain when it is not computed). Never fails a scan."""
    from isoline.core.dcf import run_dcf

    try:
        return run_dcf(financials, ticker, None, None, None, 5).to_dict()
    except Exception:  # noqa: BLE001 - a missing valuation must not break the scan
        return None


class IsolineScanner:
    def scan(self, ticker: str) -> ScanResult:
        start = time.time()
        financials = load_financials(ticker)
        valuation = ValuationEngine().run(financials)
        health = HealthEngine().run(financials)
        growth = GrowthEngine().run(financials)
        flags = FlagsEngine().run(financials)
        quality = QualityEngine().run(financials)
        duration_ms = int((time.time() - start) * 1000)

        resolved_ticker = financials.get("info", {}).get("symbol") or ticker
        company = (
            financials.get("info", {}).get("longName")
            or financials.get("info", {}).get("shortName")
            or resolved_ticker
        )
        exchange = (
            financials.get("info", {}).get("exchange")
            or financials.get("info", {}).get("exchangeTimezoneName")
            or "unknown"
        )
        brief = generate_brief(
            ScanResult(
                ticker=resolved_ticker,
                company=company,
                exchange=exchange,
                scan_duration_ms=duration_ms,
                valuation=valuation,
                health=health,
                growth=growth,
                red_flags=flags.red_flags,
                highest_concern=flags.highest_concern,
                analyst_brief="",
                beneish_m=flags.beneish_m,
            )
        )

        return ScanResult(
            ticker=resolved_ticker,
            company=company,
            exchange=exchange,
            scan_duration_ms=duration_ms,
            valuation=valuation,
            health=health,
            growth=growth,
            red_flags=flags.red_flags,
            highest_concern=flags.highest_concern,
            analyst_brief=brief,
            beneish_m=flags.beneish_m,
            notes=[*financials.get("notes", []), *health.notes, *flags.notes, *quality.notes],
            quality=quality,
            history=HistoryEngine().run(financials),
            statements=StatementsEngine().run(financials),
            dcf=_default_dcf(financials, resolved_ticker),
        )

    def compare(self, ticker_a: str, ticker_b: str) -> CompareResult:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as pool:  # the two scans are independent
            future_a = pool.submit(self.scan, ticker_a)
            future_b = pool.submit(self.scan, ticker_b)
            result_a, result_b = future_a.result(), future_b.result()
        return CompareResult(
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            result_a=result_a,
            result_b=result_b,
        )
