"""Render the sample report and terminal output used in the README.

Everything is computed by the real engines from a SYNTHETIC company ("Acme Industrial"),
so the screenshots show true formatting without implying any real company's numbers.

    python examples/make_sample_assets.py docs/assets [--chrome PATH]

Writes sample-report.html and sample-terminal.svg, plus sample-report.png (the top
2300 px of the report at 1100 px wide) when Playwright's Chromium is installed.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from rich.console import Console

from isoline.cli import app as cli
from isoline.core.scanner import IsolineScanner
from isoline.exporters.report import scan_report

DATES = [pd.Timestamp(f"{y}-12-31") for y in (2024, 2023, 2022, 2021)]


def frame(rows: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=DATES).T


def synthetic() -> dict:
    income = frame({
        "Total Revenue": [1480e6, 1320e6, 1190e6, 1040e6],
        "Cost Of Revenue": [880e6, 800e6, 735e6, 650e6],
        "Gross Profit": [600e6, 520e6, 455e6, 390e6],
        "Selling General And Administration": [260e6, 240e6, 220e6, 200e6],
        "EBIT": [250e6, 205e6, 165e6, 130e6],
        "Interest Expense": [18e6, 20e6, 21e6, 22e6],
        "Pretax Income": [232e6, 185e6, 144e6, 108e6],
        "Tax Provision": [52e6, 42e6, 33e6, 25e6],
        "Net Income": [180e6, 143e6, 111e6, 83e6],
        "Reconciled Depreciation": [70e6, 66e6, 62e6, 58e6],
    })
    balance = frame({
        "Total Assets": [1900e6, 1760e6, 1650e6, 1540e6],
        "Current Assets": [720e6, 650e6, 600e6, 540e6],
        "Current Liabilities": [380e6, 360e6, 350e6, 340e6],
        "Total Liabilities Net Minority Interest": [980e6, 960e6, 950e6, 940e6],
        "Stockholders Equity": [920e6, 800e6, 700e6, 600e6],
        "Retained Earnings": [520e6, 420e6, 340e6, 270e6],
        "Long Term Debt": [400e6, 430e6, 460e6, 490e6],
        "Accounts Receivable": [210e6, 195e6, 180e6, 165e6],
        "Inventory": [190e6, 180e6, 170e6, 160e6],
        "Accounts Payable": [150e6, 140e6, 135e6, 130e6],
        "Cash And Cash Equivalents": [210e6, 170e6, 140e6, 110e6],
        "Ordinary Shares Number": [100e6, 100e6, 100e6, 100e6],
    })
    cash = frame({
        "Operating Cash Flow": [240e6, 190e6, 150e6, 118e6],
        "Capital Expenditure": [-90e6, -80e6, -75e6, -70e6],
    })
    info = {"symbol": "ACME", "longName": "Acme Industrial (synthetic sample)", "currency": "USD",
            "trailingPE": 18.4, "priceToBook": 2.6, "enterpriseToEbitda": 10.2,
            "marketCap": 2.4e9, "enterpriseValue": 2.6e9}
    return {"info": info, "income_stmt": income, "balance_sheet": balance,
            "cashflow": cash, "fast_info": {}, "source": "synthetic sample"}


def main(out: Path, chrome: str | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with patch("isoline.core.scanner.load_financials", return_value=synthetic()):
        result = IsolineScanner().scan("ACME")
    (out / "sample-report.html").write_text(scan_report(result), encoding="utf-8")
    rec = Console(record=True, width=100, force_terminal=True, file=io.StringIO())
    cli.console = rec
    cli._print_scan(result)
    rec.save_svg(str(out / "sample-terminal.svg"), title="isoline scan ACME  (synthetic sample)")
    render_png(out / "sample-report.html", out / "sample-report.png", chrome=chrome)
    print("wrote", out)


def render_png(html_file: Path, png: Path, width: int = 1100, height: int = 2300,
               chrome: str | None = None) -> None:
    """Screenshot the report; skipped with a message if Playwright is unavailable."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed: skipped", png.name)
        return
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chrome) if chrome else pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=1)
        page.goto(html_file.resolve().as_uri())
        full = page.evaluate("document.documentElement.scrollHeight")
        page.screenshot(path=str(png), full_page=True,
                        clip={"x": 0, "y": 0, "width": width, "height": min(full, height)})
        browser.close()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="docs/assets")
    ap.add_argument("--chrome", default=None, help="Path to a Chrome/Chromium binary (optional).")
    args = ap.parse_args()
    main(Path(args.out), args.chrome)
