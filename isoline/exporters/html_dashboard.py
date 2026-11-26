"""HTML report exporter (thin wrapper around :mod:`isoline.exporters.report`).

The earlier dark Chart.js dashboards (CDN scripts, web fonts, a logo lookup that made
extra network calls, and several places that rendered missing data as 0) were replaced
by self-contained, print-ready reports with no JavaScript and no network access.
"""

from __future__ import annotations

from collections.abc import Sequence

from isoline.core.result import CompareResult, ScanResult
from isoline.exporters._safe import escape_obj
from isoline.exporters.report import compare_report, scan_report, screen_report


def _write(path: str, html: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


class HtmlDashboardExporter:
    def export_scan(self, result: ScanResult, path: str) -> None:
        _write(path, scan_report(escape_obj(result)))

    def export_compare(self, result: CompareResult, path: str) -> None:
        _write(path, compare_report(escape_obj(result)))

    def export_screen(self, results: Sequence[ScanResult], path: str, criteria: str = "") -> None:
        _write(path, screen_report(escape_obj(list(results)), escape_obj(criteria)))
