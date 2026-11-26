from __future__ import annotations

import pandas as pd

from isoline.core.dcf import DCFResult, run_dcf
from isoline.core.result import CompareResult, ScanResult, StatementsResult
from isoline.core.scanner import IsolineScanner


def scan(ticker: str) -> ScanResult:
    return IsolineScanner().scan(ticker)


def compare(ticker_a: str, ticker_b: str) -> CompareResult:
    return IsolineScanner().compare(ticker_a, ticker_b)


def statements(ticker: str) -> StatementsResult | None:
    """Income statement, balance sheet and cash flow (newest first), or None if unavailable."""
    from isoline.core.engines.statements import StatementsEngine
    from isoline.core.loaders import load_financials
    from isoline.core.validation import validate_ticker

    return StatementsEngine().run(load_financials(validate_ticker(ticker)))


def value(
    ticker: str,
    discount: float | None = None,
    growth: float | None = None,
    terminal: float | None = None,
    years: int = 5,
) -> DCFResult:
    """Discounted-cash-flow estimate; defaults match ``isoline value``."""
    from isoline.core.loaders import load_financials
    from isoline.core.validation import validate_ticker

    t = validate_ticker(ticker)
    return run_dcf(load_financials(t), t, discount, growth, terminal, years)


def compare_to_dataframe(compare_result: CompareResult) -> pd.DataFrame:
    rows = [
        (
            "P/E ratio",
            compare_result.result_a.valuation.pe_ratio,
            compare_result.result_b.valuation.pe_ratio,
        ),
        (
            "P/B ratio",
            compare_result.result_a.valuation.pb_ratio,
            compare_result.result_b.valuation.pb_ratio,
        ),
        (
            "EV/EBITDA",
            compare_result.result_a.valuation.ev_ebitda,
            compare_result.result_b.valuation.ev_ebitda,
        ),
        (
            "Piotroski F-score",
            compare_result.result_a.health.piotroski_f,
            compare_result.result_b.health.piotroski_f,
        ),
        (
            "Altman Z-score",
            compare_result.result_a.health.altman_z,
            compare_result.result_b.health.altman_z,
        ),
        (
            "Revenue CAGR 3y",
            compare_result.result_a.growth.revenue_cagr_3y,
            compare_result.result_b.growth.revenue_cagr_3y,
        ),
        (
            "FCF yield",
            compare_result.result_a.growth.fcf_yield,
            compare_result.result_b.growth.fcf_yield,
        ),
    ]
    return pd.DataFrame(
        rows, columns=["metric", compare_result.ticker_a, compare_result.ticker_b]
    ).set_index("metric")
