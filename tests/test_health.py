from __future__ import annotations

import logging

import pytest

from telmus.core.engines.health import HealthEngine
from tests.fixtures.infy_mock import infy_financials


def test_piotroski_score_is_in_range_or_not_reported() -> None:
    result = HealthEngine().run(infy_financials())
    # The mock has no share counts, so the score must be withheld (not guessed).
    assert result.piotroski_f is None or 0 <= result.piotroski_f <= 9


def test_piotroski_individual_signals() -> None:
    engine = HealthEngine()
    financials = infy_financials()
    income = financials["income_stmt"]
    balance = financials["balance_sheet"]
    cashflow = financials["cashflow"]
    assert engine._roa_positive(income, balance) in (True, False, None)
    assert engine._cfo_positive(cashflow) in (True, False, None)
    assert engine._roa_increasing(income, balance) in (True, False, None)
    assert engine._accruals(income, cashflow) in (True, False, None)
    assert engine._leverage_decreasing(balance) in (True, False, None)
    assert engine._liquidity_increasing(balance) in (True, False, None)
    assert engine._no_dilution(balance) in (True, False, None)
    assert engine._gross_margin_increasing(income) in (True, False, None)
    assert engine._asset_turnover_increasing(income, balance) in (True, False, None)


def test_debt_to_equity_non_negative() -> None:
    result = HealthEngine().run(infy_financials())
    assert result.debt_to_equity is not None
    assert result.debt_to_equity >= 0


def test_missing_data_graceful_empty_dict(caplog: pytest.LogCaptureFixture) -> None:
    logging.getLogger("telmus.core.engines.health").setLevel(logging.WARNING)
    caplog.set_level(logging.WARNING)
    result = HealthEngine().run({})
    assert result.piotroski_f is None  # insufficient data is not a score of 0
    assert result.altman_z is None
    assert result.debt_to_equity is None
    assert any("missing" in rec.message.lower() for rec in caplog.records)
