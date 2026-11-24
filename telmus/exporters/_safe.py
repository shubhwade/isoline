"""HTML-escape every string in a result object before it is placed in a report.

Company names, exchanges and flags come from a third party (Yahoo Finance) and
the user's command line; they must never reach the page as markup.
"""

from __future__ import annotations

import dataclasses
import html
from typing import Any


def escape_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return html.escape(obj, quote=True)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.replace(
            obj, **{f.name: escape_obj(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        )
    if isinstance(obj, list):
        return [escape_obj(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(escape_obj(x) for x in obj)
    if isinstance(obj, dict):
        return {escape_obj(k) if isinstance(k, str) else k: escape_obj(v) for k, v in obj.items()}
    return obj
