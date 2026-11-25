"""Full-screen terminal interface built on Textual.

Every workflow calls the same engines as the command line; the screen only chooses what to run
and how to show it. Network work runs in a worker thread so the interface never freezes.
"""

from __future__ import annotations

import io
import threading
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, RichLog, Static

from isoline import __version__
from isoline.branding import BRAND

MODES: dict[str, tuple[str, str]] = {
    "fundamental": ("Fundamental", "Ticker, e.g. AAPL or INFY.NS. Scores, quality, growth, red flags."),
    "valuation": ("Valuation", "Ticker, then optional discount and growth, e.g. AAPL 0.09 0.07. DCF with scenarios."),
    "compare": ("Compare", "Two tickers, e.g. AAPL MSFT. Side by side."),
    "screening": ("Screening", "Sector name: IT or Banking. Piotroski and leverage screen."),
}
HELP = (
    "Type in the box and press Enter to run the current mode.\n"
    "Ctrl+K  command palette     Ctrl+N  new analysis (focus input)\n"
    "Tab     switch panels        F2-F5   choose mode\n"
    "Ctrl+L  clear output         Ctrl+Q  quit\n\n"
    "Results are screening statistics from public data, not investment advice."
)
_print_lock = threading.Lock()


def render(fn: Callable[[], Any], width: int = 110) -> Text:
    """Run a CLI printer and capture its Rich output as styled text."""
    from isoline.cli import app as cli

    buf = io.StringIO()
    with _print_lock:
        saved = cli.console
        cli.console = Console(file=buf, force_terminal=True, width=width, color_system="truecolor")
        try:
            fn()
        finally:
            cli.console = saved
    return Text.from_ansi(buf.getvalue())


def run_mode(mode: str, query: str) -> Text:
    """Execute one workflow and return what to display. Raises on bad input or provider errors."""
    parts = query.split()
    if not parts:
        raise ValueError("Enter something to analyse.")
    from isoline.cli import app as cli

    if mode == "fundamental":
        from isoline.core.scanner import IsolineScanner

        ticker = cli._validate_ticker(parts[0])
        result = IsolineScanner().scan(ticker)
        return render(lambda: cli._print_scan(result))
    if mode == "valuation":
        from isoline.core.dcf import run_dcf
        from isoline.core.loaders import load_financials

        ticker = cli._validate_ticker(parts[0])
        discount = float(parts[1]) if len(parts) > 1 else None
        growth = float(parts[2]) if len(parts) > 2 else None
        res = run_dcf(load_financials(ticker), ticker, discount, growth)
        return render(lambda: cli._print_value(res))
    if mode == "compare":
        if len(parts) != 2:
            raise ValueError("Compare needs exactly two tickers, e.g. AAPL MSFT.")
        from isoline.core.scanner import IsolineScanner

        a, b = cli._validate_ticker(parts[0]), cli._validate_ticker(parts[1])
        result = IsolineScanner().compare(a, b)
        return render(lambda: cli._print_compare(result))
    if mode == "screening":
        from isoline.core.screening import screen_sector

        outcome = screen_sector(parts[0])
        return render(lambda: cli._print_screen(outcome))
    raise ValueError(f"Unknown mode '{mode}'.")


class IsolineCommands(Provider):
    """Entries for the command palette."""

    def _entries(self) -> list[tuple[str, Callable[[], None], str]]:
        app: IsolineApp = self.app  # type: ignore[assignment]
        entries: list[tuple[str, Callable[[], None], str]] = [
            ("New analysis", app.action_new, "Focus the input box"),
            ("Clear output", app.action_clear, "Empty the results panel"),
            ("Help", app.action_help, "Show keys and usage"),
            ("Quit", app.action_quit, "Leave Isoline"),
        ]
        for key, (label, hint) in MODES.items():
            entries.append((f"Mode: {label}", lambda k=key: app.set_mode(k), hint))  # type: ignore[misc]
        return entries

    async def discover(self) -> Hits:
        for name, fn, hint in self._entries():
            yield DiscoveryHit(name, fn, help=hint)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, fn, hint in self._entries():
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), fn, help=hint)


class IsolineApp(App[None]):
    TITLE = f"{BRAND.name} {__version__}"
    SUB_TITLE = "financial statement research"
    COMMAND_PALETTE_BINDING = "ctrl+k"
    COMMANDS = {IsolineCommands}
    CSS = """
    Screen { background: #12161D; }
    #side { width: 28; border-right: solid #2A3342; padding: 0 1; }
    #side Static.title { color: #B4690E; text-style: bold; margin-top: 1; }
    ListView { background: #12161D; height: auto; }
    ListItem.-highlight, ListView:focus > ListItem.-highlight { background: #1B2A4A; }
    #main { padding: 0 1; }
    #hint { color: #9AA4B2; height: 1; margin-bottom: 1; }
    #status { color: #B4690E; height: 1; }
    Input { border: tall #2A3342; }
    Input:focus { border: tall #B4690E; }
    RichLog { border: round #2A3342; height: 1fr; padding: 0 1; }
    """
    BINDINGS = [
        Binding("ctrl+n", "new", "New"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("f1", "help", "Help"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f2", "mode('fundamental')", "Fundamental"),
        Binding("f3", "mode('valuation')", "Valuation"),
        Binding("f4", "mode('compare')", "Compare"),
        Binding("f5", "mode('screening')", "Screening"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.mode = "fundamental"
        self.history: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="side"):
                yield Static("MODE", classes="title")
                yield ListView(*[ListItem(Static(f"F{i + 1}  {label}"), id=f"mode-{key}") for i, (key, (label, _)) in enumerate(MODES.items(), 1)], id="modes")
                yield Static("SESSION", classes="title")
                yield ListView(id="history")
            with Vertical(id="main"):
                yield Static("", id="hint")
                yield Input(placeholder="ticker, then Enter", id="query")
                yield Static("", id="status")
                yield RichLog(id="out", wrap=False, markup=False, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.set_mode("fundamental")
        self.query_one("#out", RichLog).write(Text(HELP))
        self.query_one("#query", Input).focus()

    def set_mode(self, key: str) -> None:
        self.mode = key
        label, hint = MODES[key]
        self.query_one("#hint", Static).update(Text(f"{label}: {hint}"))
        self.query_one("#query", Input).placeholder = hint.split(".")[0]
        self.sub_title = label
        self.query_one("#query", Input).focus()

    def action_mode(self, key: str) -> None:
        self.set_mode(key)

    def action_new(self) -> None:
        inp = self.query_one("#query", Input)
        inp.value = ""
        inp.focus()

    def action_clear(self) -> None:
        self.query_one("#out", RichLog).clear()

    def action_help(self) -> None:
        log = self.query_one("#out", RichLog)
        log.clear()
        log.write(Text(HELP))

    @on(ListView.Selected, "#modes")
    def _mode_picked(self, event: ListView.Selected) -> None:
        if event.item.id:
            self.set_mode(event.item.id.removeprefix("mode-"))

    @on(ListView.Selected, "#history")
    def _history_picked(self, event: ListView.Selected) -> None:
        label = event.item.query_one(Static).render()
        self.query_one("#query", Input).value = str(label).split(" ", 1)[-1]
        self.query_one("#query", Input).focus()

    @on(Input.Submitted, "#query")
    def _submit(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        self.query_one("#status", Static).update(f"Running {MODES[self.mode][0].lower()} on {query} ...")
        self.run_worker(lambda: self._work(self.mode, query), thread=True, exclusive=True)

    def _work(self, mode: str, query: str) -> None:
        try:
            text: Text = run_mode(mode, query)
            ok = True
        except Exception as exc:  # shown to the user, never a traceback
            text = Text(f"Error: {exc}\n\nCheck the symbol (add .NS, .BO, .L for non-US) or try again shortly.", style="red")
            ok = False
        self.call_from_thread(self._show, mode, query, text, ok)

    def _show(self, mode: str, query: str, text: Text, ok: bool) -> None:
        log = self.query_one("#out", RichLog)
        log.clear()
        log.write(text, scroll_end=False)
        log.scroll_home(animate=False)
        self.query_one("#status", Static).update("" if ok else "Failed. See message below.")
        if ok:
            entry = f"{MODES[mode][0][:4]} {query}"
            self.history.insert(0, entry)
            hv = self.query_one("#history", ListView)
            hv.insert(0, [ListItem(Static(entry))])


def run() -> None:
    IsolineApp().run()
