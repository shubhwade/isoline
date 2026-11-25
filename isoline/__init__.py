"""isoline: financial statement analysis (Piotroski F, Altman Z'', Beneish M, quality ratios).

Public Python API (imported lazily so ``import isoline`` stays fast)::

    from isoline import scan, compare, IsolineScanner, ScanResult
    result = scan("AAPL")
"""

from __future__ import annotations

import typing

__version__ = "0.6.0"

__all__ = ["CompareResult", "ScanResult", "IsolineScanner", "__version__", "compare", "scan"]

_LAZY = {
    "scan": ("isoline.sdk", "scan"),
    "compare": ("isoline.sdk", "compare"),
    "IsolineScanner": ("isoline.sdk", "IsolineScanner"),
    "ScanResult": ("isoline.core.result", "ScanResult"),
    "CompareResult": ("isoline.core.result", "CompareResult"),
}


def __getattr__(name: str) -> typing.Any:
    if name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(f"module 'isoline' has no attribute {name!r}")
