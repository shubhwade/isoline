"""Terminal UI tests: drive the real app headlessly with Textual's test pilot."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from rich.text import Text  # noqa: E402

from isoline.tui import app as tui  # noqa: E402


def _out(app) -> str:
    log = app.query_one("#out")
    return "\n".join(line.text for line in log.lines)


async def _submit(pilot, app, text: str) -> None:
    inp = app.query_one("#query")
    inp.value = text
    await pilot.press("enter")
    await app.workers.wait_for_complete()
    await pilot.pause()


def test_run_mode_validates_input(monkeypatch) -> None:
    with pytest.raises(ValueError):
        tui.run_mode("fundamental", "   ")
    with pytest.raises(ValueError):
        tui.run_mode("compare", "AAPL")


def test_modes_and_workflow_with_mocked_engine(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(tui, "run_mode", lambda mode, q: (calls.append((mode, q)), Text(f"RESULT {mode} {q}"))[1])

    async def go() -> None:
        app = tui.IsolineApp()
        async with app.run_test(size=(140, 40)) as pilot:
            assert "Help" in _out(app) or "Ctrl+K" in _out(app)
            await pilot.press("f3")
            assert app.mode == "valuation"
            await _submit(pilot, app, "AAPL 0.09 0.07")
            assert "RESULT valuation AAPL 0.09 0.07" in _out(app)
            await pilot.press("f4")
            await _submit(pilot, app, "AAPL MSFT")
            assert "RESULT compare AAPL MSFT" in _out(app)
            assert len(app.history) == 2

    asyncio.run(go())
    assert calls == [("valuation", "AAPL 0.09 0.07"), ("compare", "AAPL MSFT")]


def test_errors_are_shown_not_raised(monkeypatch) -> None:
    def boom(mode: str, q: str) -> Text:
        raise RuntimeError("provider down")

    monkeypatch.setattr(tui, "run_mode", boom)

    async def go() -> None:
        app = tui.IsolineApp()
        async with app.run_test(size=(140, 40)) as pilot:
            await _submit(pilot, app, "AAPL")
            assert "provider down" in _out(app)
            assert app.history == []

    asyncio.run(go())


def test_command_palette_lists_actions(monkeypatch) -> None:
    async def go() -> None:
        app = tui.IsolineApp()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.press("ctrl+k")
            await pilot.pause()
            from textual.command import CommandPalette

            assert isinstance(app.screen, CommandPalette)
            await pilot.press("escape")
            await pilot.pause()
            provider = tui.IsolineCommands(app.screen)
            names = [e[0] for e in provider._entries()]
            assert "New analysis" in names and "Mode: Valuation" in names and "Quit" in names

    asyncio.run(go())


def test_real_engine_renders_value_mode(monkeypatch) -> None:
    """End to end through the real DCF and printer with a synthetic company."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1] / "examples"))
    from unittest.mock import patch

    from make_sample_assets import synthetic

    with patch("isoline.core.loaders.load_financials", side_effect=lambda t: synthetic()):
        text = tui.run_mode("valuation", "ACME 0.10 0.05")
    assert "DCF assumptions" in text.plain and "Scenarios" in text.plain
