"""telmus: financial statement analysis (Piotroski F, Altman Z'', Beneish M, quality ratios).

Public Python API (imported lazily so ``import telmus`` stays fast)::

    from telmus import scan, compare, TelmusScanner, ScanResult
    result = scan("AAPL")
"""

from __future__ import annotations

import typing

__version__ = "0.4.0"

__all__ = ["CompareResult", "ScanResult", "TelmusScanner", "__version__", "compare", "scan"]

_LAZY = {
    "scan": ("telmus.sdk", "scan"),
    "compare": ("telmus.sdk", "compare"),
    "TelmusScanner": ("telmus.sdk", "TelmusScanner"),
    "ScanResult": ("telmus.core.result", "ScanResult"),
    "CompareResult": ("telmus.core.result", "CompareResult"),
}


def __getattr__(name: str) -> typing.Any:
    if name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(f"module 'telmus' has no attribute {name!r}")
