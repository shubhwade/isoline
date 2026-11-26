from __future__ import annotations

import logging
import os
import re
import sys
import typing
import warnings

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from isoline import __version__
from isoline.branding import BRAND
from isoline.core.comparison import SECTIONS, all_metrics, format_value, stronger
from isoline.core.errors import IsolineError
from isoline.core.result import ScanResult
from isoline.core.scanner import IsolineScanner
from isoline.exporters._safe import safe_csv_writer

warnings.filterwarnings(
    "ignore",
    message=r".*Eventlet is deprecated.*",
    category=Warning,
)
warnings.filterwarnings(
    "ignore",
    category=Warning,
    module=r"^eventlet(\.|$)",
)
warnings.filterwarnings(
    "ignore",
    category=Warning,
    module=r"^curl_cffi(\.|$)",
)
app = typer.Typer(
    help="isoline: financial statement analysis (Piotroski F, Altman Z, Beneish M, ratios).",
    epilog="Examples:  isoline scan AAPL  |  isoline scan INFY --export report.xlsx  |  isoline compare AAPL MSFT",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"isoline {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version_flag: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show the version and exit.",
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Show full tracebacks and detailed logs (or set ISOLINE_DEBUG=1)."
    ),
) -> None:
    """isoline: financial statement analysis from your terminal."""
    if debug:
        _STATE["debug"] = True
        logging.getLogger("isoline").setLevel(logging.DEBUG)

console = Console()
logging.getLogger("isoline").setLevel(logging.ERROR)
logging.getLogger("isoline.core.engines.health").setLevel(logging.ERROR)
logging.getLogger("isoline.core.engines.valuation").setLevel(logging.ERROR)
logging.getLogger("isoline.core.engines.flags").setLevel(logging.ERROR)
logging.getLogger("isoline.core.engines.growth").setLevel(logging.ERROR)
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("curl_cffi").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


_STATE = {"debug": os.environ.get("ISOLINE_DEBUG", "") not in ("", "0", "false")}
def _validate_ticker(raw: str) -> str:
    """Accept tickers (AAPL, INFY.NS, BRK-B, ^GSPC) and short company names."""
    from isoline.core.validation import InvalidInputError, validate_ticker

    try:
        return validate_ticker(raw)
    except InvalidInputError:
        console.print(
            f"[bold red]Error:[/] '{escape(raw[:40])}' is not a valid ticker.\n"
            "Use a symbol such as AAPL, MSFT or INFY.NS."
        )
        raise typer.Exit(code=2) from None


def _open_report(path: str) -> None:
    """Open a written report in the default browser by absolute file URI; never fail the command."""
    import pathlib
    import webbrowser

    try:
        webbrowser.open(pathlib.Path(path).resolve().as_uri())
    except Exception:  # noqa: BLE001 - no browser (servers, CI) is not an error
        logging.getLogger(__name__).debug("Could not open %s in a browser", path)


def _file_stem(ticker: str) -> str:
    """A ticker as a safe file-name part (INFY.NS -> INFY, 'Tata Motors' -> Tata_Motors)."""
    stem = re.sub(r"\.(NS|BO)$", "", ticker.strip(), flags=re.I)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "report"


def _print_notes(*results: ScanResult) -> None:
    for r in results:
        for note in r.notes[:4]:
            console.print(f"[dim]{escape(r.ticker)}: {escape(note)}[/dim]")


def _fail(exc: BaseException) -> typing.NoReturn:
    """Print a friendly error (traceback only with --debug) and exit with a clear code."""
    if isinstance(exc, typer.Exit):
        raise exc
    if _STATE["debug"]:
        console.print_exception()
    console.print(f"[bold red]Error:[/] {escape(str(exc))}")
    hint = getattr(exc, "hint", "")
    if hint:
        console.print(f"[yellow]Hint:[/] {escape(hint)}")
    elif not _STATE["debug"]:
        console.print("[dim]Run again with --debug for details.[/dim]")
    raise typer.Exit(code=getattr(exc, "exit_code", 1))


class Pct(float):
    """A fraction that should be displayed as a percentage (0.123 -> 12.3%)."""


def _pct(value: float | None) -> Pct | None:
    return None if value is None else Pct(value)


def _format_metric(value: typing.Any | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, Pct):
        return f"{value * 100:.1f}%"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _severity_color(flag: str | None) -> str:
    if flag is None:
        return "green"
    text = flag.lower() if isinstance(flag, str) else ""
    if (
        flag == "expensive relative to sector"
        or "negative" in text
        or "weak" in text
        or "distress" in text
    ):
        return "red"
    return "yellow"


def _render_section(
    name: str, metrics: typing.Sequence[tuple[str, object | None, str | None]]
) -> Table:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Engine")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_column("Status")
    for metric, value, flag in metrics:
        text = _format_metric(value)
        if value is None:
            table.add_row(name, metric, text, "[dim]n/a[/dim]")
            continue
        color = _severity_color(flag)
        table.add_row(name, metric, text, f"[{color}]{flag or 'ok'}[/{color}]")
    return table


def _get_bar_char() -> str:
    import sys

    try:
        if (
            sys.stdout
            and sys.stdout.encoding
            and "utf-8" in sys.stdout.encoding.lower()
        ):
            return "█"
    except Exception:
        pass
    return "X"


def _render_bar_chart(
    title: str,
    metrics: typing.Sequence[tuple[str, object | None, str | None]],
    color: str = "cyan",
) -> Table:
    table = Table(title=title, show_header=False, box=None)
    table.add_column("Label", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Bar")

    valid_data = [
        abs(v) for _, v, _ in metrics if v is not None and isinstance(v, (int, float))
    ]
    max_val = max(valid_data + [0.001])

    for metric, value, _flag in metrics:
        if value is None or not isinstance(value, (int, float)):
            table.add_row(metric, "n/a", "")
            continue

        bar_len = int((abs(value) / max_val) * 20)
        bar_str = _get_bar_char() * max(1, bar_len)
        if value < 0:
            bar_str = f"[red]{bar_str}[/red]"
        else:
            bar_str = f"[{color}]{bar_str}[/{color}]"

        table.add_row(metric, _format_metric(value), bar_str)

    return table


def _render_compare_chart(
    title: str,
    ticker_a: str,
    ticker_b: str,
    metrics: list[tuple[str, object | None, object | None]],
) -> Table:
    table = Table(title=title, show_header=True, header_style="bold magenta", box=None)
    table.add_column("Metric", style="bold")
    table.add_column(f"{ticker_a} (cyan)", justify="right")
    table.add_column(f"{ticker_b} (magenta)", justify="right")

    all_vals = []
    for _, a, b in metrics:
        if a is not None and isinstance(a, (int, float)):
            all_vals.append(abs(a))
        if b is not None and isinstance(b, (int, float)):
            all_vals.append(abs(b))
    max_val = max(all_vals + [0.001])

    for metric, val_a, val_b in metrics:

        def make_bar(v, c):
            if v is None or not isinstance(v, (int, float)):
                return "n/a"
            bar_len = int((abs(v) / max_val) * 15)
            bar_str = _get_bar_char() * max(1, bar_len)
            col = "red" if v < 0 else c
            return f"{v:,.2f} [{col}]{bar_str}[/{col}]"

        table.add_row(metric, make_bar(val_a, "cyan"), make_bar(val_b, "magenta"))

    return table


def _print_scan(result: ScanResult) -> None:
    console.rule(
        f"[bold blue]{escape(result.company)}[/] — [green]{escape(result.ticker)}[/] — [cyan]{escape(result.exchange)}[/]"
    )
    console.print(f"Scan duration: {result.scan_duration_ms} ms")

    valuation_metrics = [
        ("P/E ratio", result.valuation.pe_ratio, result.valuation.flag),
        ("P/B ratio", result.valuation.pb_ratio, result.valuation.flag),
        ("EV/EBITDA", result.valuation.ev_ebitda, result.valuation.flag),
    ]
    health_metrics = [
        ("Piotroski F-score", result.health.piotroski_f, result.health.flag),
        ("Altman Z-score", result.health.altman_z, result.health.flag),
        ("Debt / Equity", result.health.debt_to_equity, result.health.flag),
        ("Current ratio", result.health.current_ratio, result.health.flag),
        ("Interest coverage", result.health.interest_coverage, result.health.flag),
    ]
    growth_metrics = [
        ("Revenue CAGR 3y", _pct(result.growth.revenue_cagr_3y), result.growth.flag),
        ("PAT CAGR 3y", _pct(result.growth.pat_cagr_3y), result.growth.flag),
        ("Margin trend", result.growth.margin_trend, result.growth.flag),
        ("FCF yield", _pct(result.growth.fcf_yield), result.growth.flag),
    ]

    console.print(_render_section("Valuation", valuation_metrics))
    console.print(_render_bar_chart("Valuation Chart", valuation_metrics, "cyan"))
    console.print(_render_section("Health", health_metrics))
    console.print(_render_bar_chart("Health Chart", health_metrics, "cyan"))
    console.print(_render_section("Growth", growth_metrics))
    console.print(_render_bar_chart("Growth Chart", growth_metrics, "cyan"))
    if result.quality is not None:
        q = result.quality
        quality_metrics = [
            ("ROE (DuPont)", _pct(q.roe), None),
            ("Net margin", _pct(q.net_margin), None),
            ("Asset turnover", q.asset_turnover, None),
            ("Equity multiplier", q.equity_multiplier, None),
            ("ROIC", _pct(q.roic), None),
            ("FCF margin", _pct(q.fcf_margin), None),
            ("Accruals ratio", _pct(q.accruals_ratio), None),
            ("Cash conversion (days)", q.cash_conversion_cycle_days, None),
        ]
        console.print(_render_section("Quality", quality_metrics))
    console.print(Panel(escape(result.analyst_brief), title="Summary (rule-based)", expand=False))
    for note in result.notes:
        console.print(f"[dim]Note: {escape(note)}[/dim]")
    console.print(
        "[dim]Screening statistics from public data (Yahoo Finance); not investment advice.[/dim]"
    )


@app.command()
def scan(
    ticker: str,
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON output."),
    export: str | None = typer.Option(
        None, "--export", help="Save result to file (.xlsx, .csv, or .json)."
    ),
    report: bool = typer.Option(
        True, "--report/--no-report", help="Write the Excel + HTML reports (default: yes)."
    ),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the HTML report in your browser (default: yes)."
    ),
) -> None:
    """Run a financial scan for a ticker.

    Example: isoline scan AAPL --export aapl.xlsx
    """
    ticker = _validate_ticker(ticker)
    try:
        scanner = IsolineScanner()
        result = scanner.scan(ticker)
        if json_output:
            typer.echo(result.to_json())  # raw: Rich would wrap lines and eat [brackets]
        else:
            _print_scan(result)
        if export:
            if export.endswith(".xlsx"):
                from isoline.exporters.excel import ExcelExporter

                ExcelExporter().export(result, export)
            elif export.endswith(".csv"):

                with open(export, "w", newline="", encoding="utf-8") as f:
                    writer = safe_csv_writer(f)
                    writer.writerow(["Category", "Metric", "Value", "Status"])
                    writer.writerow(["Summary", "Company Name", result.company, ""])
                    writer.writerow(["Summary", "Ticker", result.ticker, ""])
                    writer.writerow(["Summary", "Exchange", result.exchange, ""])
                    writer.writerow(
                        ["Summary", "Scan Duration (ms)", result.scan_duration_ms, ""]
                    )
                    writer.writerow(
                        ["Summary", "Highest Concern", result.highest_concern, ""]
                    )
                    writer.writerow(
                        ["Summary", "Analyst Brief", result.analyst_brief, ""]
                    )

                    writer.writerow(
                        [
                            "Valuation",
                            "P/E ratio",
                            result.valuation.pe_ratio or "n/a",
                            result.valuation.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Valuation",
                            "P/B ratio",
                            result.valuation.pb_ratio or "n/a",
                            result.valuation.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Valuation",
                            "EV/EBITDA",
                            result.valuation.ev_ebitda or "n/a",
                            result.valuation.flag or "ok",
                        ]
                    )

                    writer.writerow(
                        [
                            "Health",
                            "Piotroski F-score",
                            result.health.piotroski_f or "n/a",
                            result.health.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Health",
                            "Altman Z-score",
                            result.health.altman_z or "n/a",
                            result.health.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Health",
                            "Debt / Equity",
                            result.health.debt_to_equity or "n/a",
                            result.health.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Health",
                            "Current ratio",
                            result.health.current_ratio or "n/a",
                            result.health.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Health",
                            "Interest coverage",
                            result.health.interest_coverage or "n/a",
                            result.health.flag or "ok",
                        ]
                    )

                    writer.writerow(
                        [
                            "Growth",
                            "Revenue CAGR 3y",
                            result.growth.revenue_cagr_3y or "n/a",
                            result.growth.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Growth",
                            "PAT CAGR 3y",
                            result.growth.pat_cagr_3y or "n/a",
                            result.growth.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Growth",
                            "Margin trend",
                            result.growth.margin_trend or "n/a",
                            result.growth.flag or "ok",
                        ]
                    )
                    writer.writerow(
                        [
                            "Growth",
                            "FCF yield",
                            result.growth.fcf_yield or "n/a",
                            result.growth.flag or "ok",
                        ]
                    )

                    for flag in result.red_flags:
                        writer.writerow(
                            ["Red Flags", flag.type, flag.value, flag.severity]
                        )
            else:
                with open(export, "w", encoding="utf-8") as handle:
                    handle.write(result.to_json())
            console.print(f"Saved to {export}")

        # Auto-generate dashboards
        if not json_output and report:
            ticker_clean = ticker.replace(".NS", "").replace(".BO", "")
            excel_path = f"{ticker_clean}_analysis.xlsx"
            html_path = f"{ticker_clean}_dashboard.html"

            from isoline.exporters.excel import ExcelExporter
            from isoline.exporters.html_dashboard import HtmlDashboardExporter

            ExcelExporter().export(result, excel_path)
            HtmlDashboardExporter().export_scan(result, html_path)
            print(f"Saved: {excel_path} and {html_path}")

            if open_browser:
                _open_report(html_path)

    except Exception as exc:
        _fail(exc)


@app.command(hidden=True)
def comp(
    ticker_a: str,
    ticker_b: str,
    export: str | None = typer.Option(None, "--export"),
    report: bool = typer.Option(True, "--report/--no-report"),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Alias for `compare`."""
    compare(ticker_a, ticker_b, export, report, open_browser)


def _print_compare(comparison: typing.Any) -> None:
    res_a, res_b = comparison.result_a, comparison.result_b
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column(res_a.ticker, justify="right")
    table.add_column(res_b.ticker, justify="right")
    for title, metrics in SECTIONS:
        table.add_section()
        table.add_row(f"[bold]{title}[/bold]", "", "")
        for m in metrics:
            va, vb = m.get(res_a), m.get(res_b)
            ta, tb = format_value(va, m.kind), format_value(vb, m.kind)
            win = stronger(va, vb, m.direction)
            if win == "a":
                ta = f"[green]{ta}[/green]"
            elif win == "b":
                tb = f"[green]{tb}[/green]"
            table.add_row(m.label, ta, tb)
    console.print(table)
    console.print("[dim]Green marks the stronger value where a direction is meaningful; "
                  "valuation multiples are not ranked.[/dim]")
    _print_notes(res_a, res_b)



@app.command()
def compare(
    ticker_a: str,
    ticker_b: str,
    export: str | None = typer.Option(
        None, "--export", help="Save comparison to file (.xlsx, .csv, or .json)."
    ),
    report: bool = typer.Option(
        True, "--report/--no-report", help="Write the Excel + HTML reports (default: yes)."
    ),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the HTML report in your browser (default: yes)."
    ),
) -> None:
    """Compare two tickers side by side.

    Example: isoline compare AAPL MSFT
    """
    ticker_a = _validate_ticker(ticker_a)
    ticker_b = _validate_ticker(ticker_b)
    try:
        scanner = IsolineScanner()
        comparison = scanner.compare(ticker_a, ticker_b)
        res_a, res_b = comparison.result_a, comparison.result_b
        _print_compare(comparison)

        if export:
            if export.endswith(".xlsx"):
                from isoline.exporters.excel import ExcelExporter

                ExcelExporter().export_compare(comparison, export)
            elif export.endswith(".csv"):

                with open(export, "w", newline="", encoding="utf-8") as f:
                    writer = safe_csv_writer(f)
                    writer.writerow(["Metric", res_a.ticker, res_b.ticker, "Stronger"])
                    for m in all_metrics():
                        va, vb = m.get(res_a), m.get(res_b)
                        win = stronger(va, vb, m.direction)
                        writer.writerow(
                            [
                                m.label,
                                "" if va is None else va,  # empty cell = n/a; a real 0 stays 0
                                "" if vb is None else vb,
                                {"a": res_a.ticker, "b": res_b.ticker}.get(win or "", ""),
                            ]
                        )
            else:
                with open(export, "w", encoding="utf-8") as handle:
                    handle.write(comparison.to_json())
            console.print(f"Saved to {export}")

        if not report:
            return
        # Auto-generate dashboards
        name = f"{_file_stem(ticker_a)}vs{_file_stem(ticker_b)}"

        from isoline.exporters.excel import ExcelExporter
        from isoline.exporters.html_dashboard import HtmlDashboardExporter

        ExcelExporter().export_compare(comparison, f"{name}_comparison.xlsx")
        HtmlDashboardExporter().export_compare(comparison, f"{name}_dashboard.html")
        console.print(f"Saved: {name}_comparison.xlsx and {name}_dashboard.html")

        if open_browser:
            _open_report(f"{name}_dashboard.html")

    except Exception as exc:
        _fail(exc)


@app.command()
def value(
    ticker: str,
    discount: float | None = typer.Option(None, "--discount", help="Discount rate (cost of equity), e.g. 0.11. Default 0.10 is an assumption."),
    growth: float | None = typer.Option(None, "--growth", help="Year-1 growth of free cash flow, e.g. 0.08. Default: 3-year revenue CAGR, capped at 15%."),
    terminal: float | None = typer.Option(None, "--terminal", help="Terminal growth, e.g. 0.025 (default 0.025)."),
    years: int = typer.Option(5, "--years", help="Explicit forecast years (1-15)."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON output."),
) -> None:
    """Discounted-cash-flow estimate with bear/base/bull scenarios and a sensitivity grid.

    Every assumption is shown. The output is illustrative, not a price target or advice.

    Example: isoline value AAPL --discount 0.09 --growth 0.07
    """
    import json as _json

    from isoline.core.dcf import run_dcf
    from isoline.core.loaders import load_financials

    ticker = _validate_ticker(ticker)
    try:
        fin = load_financials(ticker)
        res = run_dcf(fin, ticker, discount, growth, terminal, years)
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    if json_output:
        typer.echo(_json.dumps(res.to_dict(), indent=2, default=str))
        return
    _print_value(res)


@app.command()
def statements(
    ticker: str,
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON output."),
    export: str | None = typer.Option(None, "--export", help="Save the statements to a .csv or .json file."),
) -> None:
    """Income statement, balance sheet and cash flow, up to four fiscal years.

    Example: isoline statements AAPL --export aapl_statements.csv
    """
    import dataclasses
    import json as _json

    from isoline.core.engines.statements import StatementsEngine
    from isoline.core.loaders import load_financials

    ticker = _validate_ticker(ticker)
    try:
        st = StatementsEngine().run(load_financials(ticker))
    except Exception as exc:  # noqa: BLE001
        _fail(exc)
    if st is None:
        console.print(f"[bold red]Error:[/] No financial statements are available for {escape(ticker)}.")
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(_json.dumps(dataclasses.asdict(st), indent=2))
        return
    if export:
        _export_statements(st, export)
        console.print(f"Saved to {export}")
        return
    _print_statements(st, ticker)


def _export_statements(st: typing.Any, path: str) -> None:
    import dataclasses
    import json as _json

    if path.lower().endswith(".json"):
        with open(path, "w", encoding="utf-8") as handle:
            _json.dump(dataclasses.asdict(st), handle, indent=2)
        return
    if not path.lower().endswith(".csv"):
        raise typer.BadParameter("--export must end in .csv or .json")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = safe_csv_writer(handle)
        writer.writerow(["Statement", "Line item", *(f"FY{p[:4]}" for p in st.periods), "Computed"])
        for name, lines in (("Income statement", st.income), ("Balance sheet", st.balance), ("Cash flow", st.cashflow)):
            for ln in lines:
                writer.writerow([name, ln.label, *("" if v is None else v * ln.sign for v in ln.values), "yes" if ln.computed else ""])


def _print_statements(st: typing.Any, ticker: str) -> None:
    from isoline.exporters.report import _acct, _scale

    values = [v for lines in (st.income, st.balance, st.cashflow) for ln in lines if not ln.per_share for v in ln.values]
    div, word = _scale(values)
    biggest = max((abs(v) / div for v in values if v is not None), default=0)
    nd = 0 if biggest >= 100 else 2
    unit = f"{st.currency} {word}".strip() or "reported units"
    console.rule(f"[bold]{escape(ticker)}[/] statements, {escape(unit)} (costs and outflows in parentheses)")
    for title, lines in (("Income statement", st.income), ("Balance sheet", st.balance), ("Cash flow statement", st.cashflow)):
        if not lines:
            continue
        table = Table(title=title, title_justify="left", show_lines=False)
        table.add_column("Line item")
        for p in st.periods:
            table.add_column(f"FY{p[:4]}", justify="right")
        for ln in lines:
            cells = [_acct(None if v is None else v * ln.sign, 1 if ln.per_share else div, 2 if ln.per_share else nd) for v in ln.values]
            cells = [c.replace('<span class="na">n/a</span>', "n/a") for c in cells]
            style = "bold" if ln.kind in ("subtotal", "total") else "dim" if ln.kind == "memo" else None
            table.add_row(ln.label + (" *" if ln.computed else ""), *cells, style=style)
        console.print(table)
    if any(ln.computed for lines in (st.income, st.balance, st.cashflow) for ln in lines):
        console.print("[dim]* Computed from reported lines (free cash flow; total liabilities and equity).[/dim]")
    for note in st.notes:
        console.print(f"[yellow]{escape(note)}[/yellow]")


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "n/a"
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(v) >= div:
            return f"{v / div:,.2f}{suffix}"
    return f"{v:,.2f}"


def _print_value(res: typing.Any) -> None:
    ccy = res.currency or ""
    a = res.assumptions
    if a is None:
        console.print(f"[bold]{escape(res.ticker)}[/]  DCF not computed")
    else:
        t = Table(title=f"DCF assumptions: {res.ticker}", show_header=True, header_style="bold")
        t.add_column("Assumption")
        t.add_column("Value", justify="right")
        t.add_column("Basis")
        t.add_row("Base free cash flow", f"{ccy} {_fmt_money(a.base_fcf)}", a.base_fcf_note)
        t.add_row("Year-1 growth", f"{a.growth:.1%}", a.growth_source)
        t.add_row("Terminal growth", f"{a.terminal_growth:.1%}", "assumption")
        t.add_row("Discount rate", f"{a.discount_rate:.1%}", "assumption")
        t.add_row("Explicit years", str(a.years), "growth fades linearly to terminal")
        console.print(t)
        r = Table(title="Estimate (illustrative)", show_header=True, header_style="bold")
        r.add_column("Item")
        r.add_column("Value", justify="right")
        r.add_row("Equity value", f"{ccy} {_fmt_money(res.equity_value)}")
        r.add_row("Per share", "n/a" if res.per_share is None else f"{res.per_share:,.2f}")
        r.add_row("Market price", "n/a" if res.price is None else f"{res.price:,.2f}")
        r.add_row("Margin of safety", "n/a" if res.margin_of_safety is None else f"{res.margin_of_safety:.1%}")
        r.add_row("Value from terminal", "n/a" if res.terminal_share is None else f"{res.terminal_share:.0%}")
        console.print(r)
        sc = Table(title="Scenarios", show_header=True, header_style="bold")
        for col in ("Scenario", "Growth", "Discount", "Per share"):
            sc.add_column(col, justify="right" if col != "Scenario" else "left")
        for s_ in res.scenarios:
            sc.add_row(s_.name, f"{s_.growth:.1%}", f"{s_.discount_rate:.1%}", "n/a" if s_.per_share is None else f"{s_.per_share:,.2f}")
        console.print(sc)
        sens = res.sensitivity
        if sens:
            g = Table(title=f"Sensitivity ({sens['unit']}): terminal growth (rows) vs discount rate (columns)", header_style="bold")
            g.add_column("")
            for rate in sens["discount_rates"]:
                g.add_column(f"{rate:.1%}", justify="right")
            for tgv, row in zip(sens["terminal_growths"], sens["values"], strict=True):
                g.add_row(f"{tgv:.1%}", *["n/a" if v is None else (f"{v:,.2f}" if v < 1e6 else _fmt_money(v)) for v in row])
            console.print(g)
    for note in res.notes:
        console.print(f"[dim]Note: {escape(note)}[/dim]")
    console.print("[dim]Illustrative estimate from stated assumptions; not a price target or investment advice.[/dim]")


def _print_screen(outcome: typing.Any, _sector: str = "") -> None:
    results = outcome.matches
    for tkr, reason in outcome.skipped.items():
        console.print(f"[dim]Skipped {escape(tkr)}: {escape(reason)}[/dim]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Ticker")
    table.add_column("Piotroski F")
    table.add_column("D/E")
    table.add_column("Concern")
    for r in results:
        table.add_row(
            r.ticker,
            str(r.health.piotroski_f),
            f"{r.health.debt_to_equity:.2f}",
            r.highest_concern,
        )
    console.print(table)


@app.command()
def screen(
    sector: str = typer.Argument("IT", help="Sector to screen."),
    min_piotroski: int = typer.Option(6, help="Minimum Piotroski score."),
    max_de: float = typer.Option(1.0, help="Maximum debt-to-equity ratio."),
    export: str | None = typer.Option(
        None, "--export", help="Save screening results to file (.xlsx, .csv, or .json)."
    ),
    report: bool = typer.Option(True, "--report/--no-report", help="Write the Excel + HTML reports (default: yes)."),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the HTML report in your browser (default: yes)."),
) -> None:
    """Screen a small example sector universe (IT, Banking) by Piotroski F and debt/equity."""
    from isoline.core.screening import screen_sector
    from isoline.core.validation import InvalidInputError, bounded_number, validate_sector

    try:
        sector = validate_sector(sector)
        min_piotroski = int(bounded_number(min_piotroski, "--min-piotroski", 0, 9, 6))
        max_de = bounded_number(max_de, "--max-de", 0, 1000, 1.0)
    except InvalidInputError as exc:
        console.print(f"[bold red]Error:[/] {escape(str(exc))}")
        raise typer.Exit(code=2) from None

    try:
        outcome = screen_sector(sector, min_piotroski, max_de)
    except IsolineError as exc:
        _fail(exc)
    results = outcome.matches
    _print_screen(outcome)

    if export:
        if export.endswith(".xlsx"):
            from isoline.exporters.excel import ExcelExporter

            ExcelExporter().export_screen(results, export)
        elif export.endswith(".csv"):

            with open(export, "w", newline="", encoding="utf-8") as f:
                writer = safe_csv_writer(f)
                writer.writerow(
                    [
                        "Ticker",
                        "Company",
                        "P/E",
                        "P/B",
                        "EV/EBITDA",
                        "Piotroski F",
                        "Altman Z",
                        "Revenue CAGR",
                        "Margin Trend",
                        "Highest Concern",
                    ]
                )
                pe_vals, pb_vals, ev_vals, pio_vals, alt_vals, rev_vals = (
                    [],
                    [],
                    [],
                    [],
                    [],
                    [],
                )
                for r in results:
                    writer.writerow(
                        [
                            r.ticker,
                            r.company,
                            r.valuation.pe_ratio or "n/a",
                            r.valuation.pb_ratio or "n/a",
                            r.valuation.ev_ebitda or "n/a",
                            r.health.piotroski_f or "n/a",
                            r.health.altman_z or "n/a",
                            r.growth.revenue_cagr_3y or "n/a",
                            r.growth.margin_trend or "n/a",
                            r.highest_concern,
                        ]
                    )
                    if r.valuation.pe_ratio is not None:
                        pe_vals.append(r.valuation.pe_ratio)
                    if r.valuation.pb_ratio is not None:
                        pb_vals.append(r.valuation.pb_ratio)
                    if r.valuation.ev_ebitda is not None:
                        ev_vals.append(r.valuation.ev_ebitda)
                    if r.health.piotroski_f is not None:
                        pio_vals.append(r.health.piotroski_f)
                    if r.health.altman_z is not None:
                        alt_vals.append(r.health.altman_z)
                    if r.growth.revenue_cagr_3y is not None:
                        rev_vals.append(r.growth.revenue_cagr_3y)

                def avg(vals):
                    return round(sum(vals) / len(vals), 2) if vals else "n/a"

                writer.writerow(
                    [
                        "Average",
                        "",
                        avg(pe_vals),
                        avg(pb_vals),
                        avg(ev_vals),
                        avg(pio_vals),
                        avg(alt_vals),
                        avg(rev_vals),
                        "",
                        "",
                    ]
                )
        else:
            with open(export, "w", encoding="utf-8") as handle:
                import json

                json.dump([r.to_dict() for r in results], handle, indent=2)
            console.print(f"Saved to {export}")

    if not report:
        return
    from isoline.exporters.excel import ExcelExporter
    from isoline.exporters.html_dashboard import HtmlDashboardExporter

    criteria = f"{sector}: Piotroski F at least {min_piotroski}, debt/equity at most {max_de:g}"
    ExcelExporter().export_screen(results, "screen_results.xlsx")
    HtmlDashboardExporter().export_screen(results, "screen_dashboard.html", criteria)
    print("Saved: screen_results.xlsx and screen_dashboard.html")
    if open_browser:
        _open_report("screen_dashboard.html")


@app.command()
def tui() -> None:
    """Open the full-screen terminal interface (needs the optional tui extra)."""
    try:
        from isoline.tui.app import run
    except ImportError:
        console.print('[bold red]The terminal interface needs an extra package.[/] Run: pip install "isoline[tui]"')
        raise typer.Exit(code=1) from None
    run()


@app.command()
def serve() -> None:
    """Start the isoline MCP server (needs the optional mcp extra)."""
    try:
        from isoline.mcp.server import run_mcp_server
    except ImportError:
        console.print(
            "[bold red]Error:[/] the MCP server needs an extra package.\n"
            'Install it with:  pip install "isoline\\[mcp]"'
        )
        raise typer.Exit(code=1) from None
    # stdout is the MCP protocol channel: anything printed there corrupts the session.
    # The setup hint goes to stderr, and only when a person runs this in a terminal.
    if sys.stdin.isatty():
        config = {"mcpServers": {"isoline": {"command": "isoline", "args": ["serve"]}}}
        hint = Console(stderr=True)
        hint.print("Isoline MCP server is running on stdio. Add this to your MCP client config:")
        hint.print_json(data=config)
    run_mcp_server()


@app.command()
def info() -> None:
    """Print package info."""
    package_version = __version__
    console.print(f"Version: [green]{package_version}[/green]")
    console.print(f"Python: [green]{sys.version.split()[0]}[/green]")
    console.print("Data source: [green]Yahoo Finance (yfinance); SEC EDGAR fallback for US tickers[/green]")
    console.print(
        "Coverage: [green]financial statements, valuation, health, growth, quality, red flags, DCF[/green]"
    )
    console.print(f"Docs: {BRAND.docs_url}  Website: {BRAND.site_url}")


@app.command()
def check(ticker: str) -> None:
    """Run a quick health check for a ticker."""
    ticker = _validate_ticker(ticker)
    try:
        scanner = IsolineScanner()
        result = scanner.scan(ticker)
        console.print(f"Piotroski F-score: [bold]{_format_metric(result.health.piotroski_f)}[/bold]")
        console.print(f"Altman Z-score: [bold]{_format_metric(result.health.altman_z)}[/bold]")
        for note in result.notes:
            console.print(f"[dim]Note: {escape(note)}[/dim]")
    except Exception as exc:
        _fail(exc)


@app.command()
def powerbi(
    extra_tickers: list[str] = typer.Argument(None, help="Additional tickers to scan."),
    tickers: list[str] = typer.Option(
        None, "--tickers", help="List of tickers to scan."
    ),
    export: str = typer.Option(..., "--export", help="Save results to a CSV file."),
    flags: bool = typer.Option(
        False,
        "--flags",
        help="Export red flags details instead of standard portfolio metrics.",
    ),
) -> None:
    """Export portfolio metrics formatted for Power BI."""
    try:
        all_tickers = []
        if tickers:
            all_tickers.extend(tickers)
        if extra_tickers:
            all_tickers.extend(extra_tickers)

        if not all_tickers:
            console.print("[bold red]Error:[/] No tickers provided.")
            raise typer.Exit(code=1)

        # Validate, then deduplicate while preserving order
        seen = set()
        clean_tickers = []
        for t in (_validate_ticker(x) for x in all_tickers):
            if t.upper() not in seen:
                seen.add(t.upper())
                clean_tickers.append(t)

        from isoline.exporters.powerbi import PowerBIExporter, report_path

        exporter = PowerBIExporter()
        if flags:
            exporter.export_flags(clean_tickers, export)
            console.print(f"Saved to {export}")
        else:
            exporter.export_portfolio(clean_tickers, export)
            console.print(f"Saved to {export}")
            console.print(f"Saved to {report_path(export)}")
        for ticker, why in exporter.failures.items():
            console.print(f"[yellow]Skipped {escape(ticker)}:[/] {escape(why)}")
    except Exception as exc:
        _fail(exc)
