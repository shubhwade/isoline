from __future__ import annotations

from telmus.core.result import ScanResult
from telmus.core.scanner import TelmusScanner
from telmus.sdk.reconciler import (
    compare as compare_scanner,
)
from telmus.sdk.reconciler import (
    compare_to_dataframe,
)
from telmus.sdk.reconciler import (
    scan as scan_scanner,
)

__all__ = ["ScanResult", "TelmusScanner", "compare", "compare_to_dataframe", "scan"]


def scan(ticker: str) -> ScanResult:
    return scan_scanner(ticker)


def compare(ticker_a: str, ticker_b: str) -> object:
    return compare_scanner(ticker_a, ticker_b)
