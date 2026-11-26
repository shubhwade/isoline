"""Public, supported Python API."""

from __future__ import annotations

from isoline.core.dcf import DCFResult
from isoline.core.errors import (
    InvalidTickerError,
    IsolineError,
    NoDataError,
    ProviderUnavailableError,
    RateLimitError,
)
from isoline.core.result import CompareResult, ScanResult, StatementLine, StatementsResult
from isoline.core.scanner import IsolineScanner
from isoline.sdk.reconciler import compare, compare_to_dataframe, scan, statements, value

__all__ = [
    "CompareResult",
    "DCFResult",
    "StatementLine",
    "StatementsResult",
    "InvalidTickerError",
    "NoDataError",
    "ProviderUnavailableError",
    "RateLimitError",
    "ScanResult",
    "IsolineError",
    "IsolineScanner",
    "compare",
    "compare_to_dataframe",
    "scan",
    "statements",
    "value",
]
