"""Public, supported Python API."""

from __future__ import annotations

from telmus.core.errors import (
    InvalidTickerError,
    NoDataError,
    ProviderUnavailableError,
    RateLimitError,
    TelmusError,
)
from telmus.core.result import CompareResult, ScanResult
from telmus.core.scanner import TelmusScanner
from telmus.sdk.reconciler import compare, compare_to_dataframe, scan

__all__ = [
    "CompareResult",
    "InvalidTickerError",
    "NoDataError",
    "ProviderUnavailableError",
    "RateLimitError",
    "ScanResult",
    "TelmusError",
    "TelmusScanner",
    "compare",
    "compare_to_dataframe",
    "scan",
]
