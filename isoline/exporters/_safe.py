"""Output hardening for everything Isoline writes.

* ``escape_obj``: HTML-escape every string in a result object before it reaches a
  report. Company names, exchanges and flags come from a third party (Yahoo Finance,
  SEC EDGAR) and the command line; they must never reach the page as markup.
* ``cell_safe`` / ``safe_csv_writer``: neutralise spreadsheet formula injection in
  CSV files. A third-party string such as ``=HYPERLINK(...)`` would otherwise run as a
  formula when the CSV is opened in Excel, Sheets or LibreOffice (OWASP "CSV
  injection"). Such strings get a leading apostrophe; plain numbers are untouched.
* ``harden_workbook``: the same protection for .xlsx files. openpyxl stores any string
  that starts with "=" as a formula, so before saving, every formula that is not one
  of Isoline's own sheet references is turned back into literal text.
"""

from __future__ import annotations

import csv
import dataclasses
import html
import re
from typing import IO, Any

# Characters that make a spreadsheet treat a cell as a formula or command.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")
# Plain numbers, optionally signed, with thousands separators, decimals, a percent
# sign or an exponent. These start with "+" or "-" legitimately and stay as they are.
_NUMBER = re.compile(r"[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?([eE][+-]?\d+)?%?")
# The only formulas Isoline itself writes: a reference to a cell on a named sheet,
# optionally scaled by 100 (for example "=Summary!B3" or "=Growth!B2*100").
_OWN_FORMULA = re.compile(r"=[A-Za-z][A-Za-z ]{0,30}![A-Z]{1,3}[1-9][0-9]{0,6}(\*100)?")


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


def cell_safe(value: Any) -> Any:
    """Return ``value`` safe to place in a spreadsheet cell (strings only are changed)."""
    if not isinstance(value, str) or not value:
        return value
    if value.startswith(_FORMULA_START) and not _NUMBER.fullmatch(value.strip()):
        return "'" + value
    return value


class _SafeWriter:
    """A ``csv.writer`` whose rows pass through :func:`cell_safe`."""

    def __init__(self, handle: IO[str], **kwargs: Any) -> None:
        self._writer = csv.writer(handle, **kwargs)

    def writerow(self, row: Any) -> Any:
        return self._writer.writerow([cell_safe(v) for v in row])

    def writerows(self, rows: Any) -> None:
        for row in rows:
            self.writerow(row)


def safe_csv_writer(handle: IO[str], **kwargs: Any) -> _SafeWriter:
    return _SafeWriter(handle, **kwargs)


def harden_workbook(workbook: Any) -> int:
    """Turn every formula that Isoline did not write into literal text. Returns the count."""
    neutralised = 0
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value
                if cell.data_type == "f" and isinstance(value, str) and not _OWN_FORMULA.fullmatch(value):
                    cell.value = "'" + value
                    cell.data_type = "s"
                    neutralised += 1
    return neutralised
