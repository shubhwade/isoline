"""Power BI exports: a tidy portfolio CSV (or red-flag CSV) plus a portfolio HTML report.

One ticker that cannot be loaded no longer aborts the whole export: it is skipped,
listed in ``self.failures`` and in the report, and the export fails only if no ticker
could be analysed at all. Every text cell goes through the formula-injection guard.
"""

from __future__ import annotations

import datetime
import logging
import typing

from isoline.core.errors import IsolineError
from isoline.core.result import ScanResult
from isoline.core.scanner import IsolineScanner
from isoline.exporters._safe import escape_obj, safe_csv_writer
from isoline.exporters.report import portfolio_report

logger = logging.getLogger(__name__)

HEADERS = [
    "Date",
    "Ticker",
    "Company",
    "Exchange",
    "PE_Ratio",
    "PB_Ratio",
    "EV_EBITDA",
    "Sector_Comparison",
    "Piotroski_F",
    "Altman_Z",
    "Debt_Equity",
    "Current_Ratio",
    "Interest_Coverage",
    "Revenue_CAGR_3Y",
    "PAT_CAGR_3Y",
    "Margin_Trend",
    "FCF_Yield",
    "Beneish_M",
    "Red_Flag_Count",
    "Highest_Concern",
    "Analyst_Brief",
]


def report_path(csv_path: str) -> str:
    """Where the HTML report for a CSV export is written."""
    return (csv_path[:-4] if csv_path.lower().endswith(".csv") else csv_path) + "_report.html"


class PowerBIExporter:
    def __init__(self) -> None:
        self.failures: dict[str, str] = {}

    def _scan_all(self, tickers: list[str]) -> list[ScanResult]:
        scanner = IsolineScanner()
        results: list[ScanResult] = []
        self.failures = {}
        for ticker in tickers:
            try:
                results.append(scanner.scan(ticker))
            except IsolineError as exc:
                logger.warning("Skipping %s: %s", ticker, exc)
                self.failures[ticker] = str(exc)
        if not results:
            detail = "; ".join(f"{t}: {why}" for t, why in self.failures.items())
            raise IsolineError(f"None of the tickers could be analysed ({detail})")
        return results

    def export_portfolio(self, tickers: list[str], path: str) -> None:
        results = self._scan_all(tickers)
        today = datetime.date.today().isoformat()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = safe_csv_writer(f)
            writer.writerow(HEADERS)
            for res in results:
                writer.writerow(
                    [
                        today,
                        res.ticker,
                        res.company,
                        res.exchange,
                        self._csv_val(res.valuation.pe_ratio),
                        self._csv_val(res.valuation.pb_ratio),
                        self._csv_val(res.valuation.ev_ebitda),
                        self._csv_val(res.valuation.vs_sector),
                        self._csv_val(res.health.piotroski_f),
                        self._csv_val(res.health.altman_z),
                        self._csv_val(res.health.debt_to_equity),
                        self._csv_val(res.health.current_ratio),
                        self._csv_val(res.health.interest_coverage),
                        self._csv_val(res.growth.revenue_cagr_3y),
                        self._csv_val(res.growth.pat_cagr_3y),
                        self._csv_val(res.growth.margin_trend),
                        self._csv_val(res.growth.fcf_yield),
                        self._csv_val(res.beneish_m),
                        len(res.red_flags),
                        res.highest_concern,
                        res.analyst_brief,
                    ]
                )
        self._generate_html_report(results, report_path(path), tickers)

    def export_flags(self, tickers: list[str], path: str) -> None:
        results = self._scan_all(tickers)
        today = datetime.date.today().isoformat()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = safe_csv_writer(f)
            writer.writerow(["Date", "Ticker", "Flag_Type", "Flag_Value", "Flag_Severity"])
            for res in results:
                if not res.red_flags:
                    writer.writerow([today, res.ticker, "none", "", ""])
                    continue
                for flag in res.red_flags:
                    writer.writerow([today, res.ticker, flag.type, self._csv_val(flag.value), flag.severity])

    def _csv_val(self, val: typing.Any) -> typing.Any:
        return "" if val is None else val

    def _generate_html_report(self, results: list[ScanResult], html_path: str, requested: list[str] | None = None) -> None:
        html = portfolio_report(escape_obj(results), escape_obj(list(requested or [])))
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
