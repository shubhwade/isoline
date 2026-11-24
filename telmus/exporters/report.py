"""Formal, print-ready HTML reports (scan, compare, screen).

Design rules:
* Self-contained: inline CSS and inline SVG only. No JavaScript, no CDN, no web
  fonts, no network access. It opens identically offline and prints to A4/Letter.
* Status is always conveyed by a word (Strong / Adequate / Weak / n/a), never by
  colour alone.
* Missing data is "n/a", never zero.
* Every string that came from a provider or the command line is HTML-escaped by
  the caller (``escape_obj``) before it reaches these functions.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Sequence

from telmus import __version__
from telmus.core.result import CompareResult, ScanResult

DISCLAIMER = (
    "Telmus produces screening statistics from public financial statements obtained from "
    "Yahoo Finance, an unofficial source that may be delayed, incomplete or wrong. "
    "Nothing in this report is investment advice, a recommendation, or an offer to buy or "
    "sell any security. Telmus is not a registered investment adviser or research analyst. "
    "Verify figures against the company's filings before relying on them."
)

CSS = """
:root{--ink:#1a1f2b;--muted:#5b6475;--line:#d9dde5;--soft:#f5f6f9;--navy:#1f3354;
--good:#1b6b43;--warn:#8a5a00;--bad:#a42a22;--goodbg:#e8f4ed;--warnbg:#fbf2df;--badbg:#fbe9e7}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#eef0f4;color:var(--ink);
font:14px/1.5 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.page{max-width:900px;margin:24px auto;background:#fff;padding:40px 48px;
border:1px solid var(--line);box-shadow:0 1px 3px rgba(0,0,0,.06)}
header.rep{border-bottom:3px solid var(--navy);padding-bottom:14px;margin-bottom:22px}
.kicker{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{font:600 26px/1.25 Georgia,"Times New Roman",serif;margin:4px 0 2px;color:var(--navy)}
.sub{color:var(--muted);font-size:13px}
h2{font:600 16px/1.3 Georgia,"Times New Roman",serif;color:var(--navy);margin:28px 0 8px;
padding-bottom:4px;border-bottom:1px solid var(--line)}
.summary{background:var(--soft);border-left:4px solid var(--navy);padding:12px 16px;margin:0 0 6px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0 4px}
.card{border:1px solid var(--line);padding:12px 14px;border-radius:4px;min-width:0}
.card .lab{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.card .val{font:600 26px/1.2 Georgia,serif;margin:4px 0 2px;font-variant-numeric:tabular-nums}
.card .sub2{font-size:12px;font-weight:600}
.bar{position:relative;height:6px;background:#e6e9ef;border-radius:3px;margin-top:8px}
.bar>i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--navy)}
table{border-collapse:collapse;width:100%;margin:4px 0;table-layout:fixed}
table.t4 th:nth-child(1){width:27%}table.t4 th:nth-child(2){width:15%}table.t4 th:nth-child(3){width:17%}table.t4 th:nth-child(4){width:41%}
td{overflow-wrap:anywhere}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--soft);font-size:11px;letter-spacing:.05em;text-transform:uppercase;
color:var(--muted);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.what{color:var(--muted);font-size:12.5px}
.tag{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11.5px;font-weight:600;
white-space:nowrap}
.good{color:var(--good);background:var(--goodbg)}.warn{color:var(--warn);background:var(--warnbg)}
.bad{color:var(--bad);background:var(--badbg)}.na{color:var(--muted);background:#eceef2}
.none{color:var(--muted)}
ul.notes{margin:6px 0 0 18px;padding:0;color:var(--muted);font-size:13px}
.disc{margin-top:28px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted);
font-size:12px}
footer{margin-top:10px;color:var(--muted);font-size:11.5px;display:flex;justify-content:space-between}
@media (max-width:700px){.page{padding:22px 16px}.cards{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:#fff}.page{margin:0;border:0;box-shadow:none;max-width:none;padding:0}
h2,table,.cards{break-inside:avoid}@page{margin:14mm}}
"""


# ----------------------------------------------------------------------------- helpers
def _num(v: float | int | None, nd: int = 2) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}"
    return f"{v:,.{nd}f}"


def _pct(v: float | None, nd: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:,.{nd}f}%"


def _days(v: float | None) -> str:
    return "n/a" if v is None else f"{v:,.0f} days"


def _tag(label: str, kind: str) -> str:
    return f'<span class="tag {kind}">{label}</span>'


def _st_f(v: int | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Strong", "good") if v >= 7 else ("Adequate", "warn") if v >= 5 else ("Weak", "bad")


def _st_z(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Safe zone", "good") if v > 2.6 else ("Grey zone", "warn") if v >= 1.1 else (
        "Distress zone",
        "bad",
    )


def _st_m(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Below -2.22", "good") if v <= -2.22 else ("Above -2.22: review", "bad")


def _st_de(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Low", "good") if v < 1 else ("Moderate", "warn") if v <= 2 else ("High", "bad")


def _st_cr(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Adequate", "good") if v >= 1 else ("Below 1.0", "bad")


def _st_ic(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Comfortable", "good") if v >= 3 else ("Thin", "warn") if v >= 1.5 else ("Weak", "bad")


def _st_growth(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Growing", "good") if v > 0 else ("Declining", "bad")


def _st_sign(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Positive", "good") if v > 0 else ("Negative", "bad")


def _row(label: str, value: str, status: tuple[str, str] | None, what: str) -> str:
    st = _tag(*status) if status else ""
    return (
        f'<tr><td>{label}</td><td class="num">{value}</td><td>{st}</td>'
        f'<td class="what">{what}</td></tr>'
    )


def _table(head: Sequence[str], rows: Sequence[str], num_cols: Sequence[int] = (1,)) -> str:
    cols = "".join(f"<th{' class=num' if i in num_cols else ''}>{h}</th>" for i, h in enumerate(head))
    cls = " class=t4" if len(head) == 4 and head[-1].startswith("What") else ""
    return f"<table{cls}><thead><tr>{cols}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _card(label: str, value: str, status: tuple[str, str], fill: float | None) -> str:
    bar = ""
    if fill is not None:
        bar = f'<div class="bar"><i style="width:{max(0.0, min(1.0, fill)) * 100:.0f}%"></i></div>'
    kind = {"good": "good", "warn": "warn", "bad": "bad", "na": "none"}[status[1]]
    return (
        f'<div class="card"><div class="lab">{label}</div><div class="val">{value}</div>'
        f'<div class="sub2"><span class="tag {kind}">{status[0]}</span></div>{bar}</div>'
    )


def _page(title: str, kicker: str, subtitle: str, body: str) -> str:
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{CSS}</style></head>
<body><div class="page">
<header class="rep"><div class="kicker">{kicker}</div><h1>{title}</h1>
<div class="sub">{subtitle} &middot; Prepared {now}</div></header>
{body}
<div class="disc">{DISCLAIMER}</div>
<footer><span>Generated by telmus v{__version__}</span><span>Data: Yahoo Finance via yfinance</span></footer>
</div></body></html>"""


def _notes(notes: Sequence[str]) -> str:
    if not notes:
        return ""
    items = "".join(f"<li>{n}</li>" for n in notes)
    return f"<h2>Data notes</h2><p class=\"none\">Metrics shown as n/a, and why.</p><ul class=\"notes\">{items}</ul>"


# ----------------------------------------------------------------------------- scan
SIGNALS = [
    ("ROA Positive", "Net income over opening assets is positive"),
    ("CFO Positive", "Operating cash flow is positive"),
    ("ROA Improving", "Return on assets is higher than last year"),
    ("Low Accruals", "Operating cash flow exceeds net income"),
    ("Leverage Falling", "Long-term debt / average assets is lower than last year"),
    ("Liquidity Rising", "Current ratio is higher than last year"),
    ("No Dilution", "Share count did not increase"),
    ("Gross Margin Rising", "Gross margin is higher than last year"),
    ("Asset Turnover Rising", "Revenue / opening assets is higher than last year"),
]


def scan_report(r: ScanResult) -> str:
    h, g, v, q = r.health, r.growth, r.valuation, r.quality
    cards = "".join(
        [
            _card(
                "Piotroski F-score",
                "n/a" if h.piotroski_f is None else f"{h.piotroski_f} / 9",
                _st_f(h.piotroski_f),
                None if h.piotroski_f is None else h.piotroski_f / 9,
            ),
            _card(
                "Altman Z&Prime;",
                _num(h.altman_z),
                _st_z(h.altman_z),
                None if h.altman_z is None else min(max(h.altman_z, 0) / 5, 1),
            ),
            _card("Beneish M-score", _num(r.beneish_m), _st_m(r.beneish_m), None),
            _card("Debt / equity", _num(h.debt_to_equity), _st_de(h.debt_to_equity), None),
        ]
    )

    valuation = _table(
        ["Metric", "Value", "Reading", "What it measures"],
        [
            _row("P/E ratio", _num(v.pe_ratio), None, "Market capitalisation relative to annual earnings"),
            _row("P/B ratio", _num(v.pb_ratio), None, "Market capitalisation relative to book equity"),
            _row("EV / EBITDA", _num(v.ev_ebitda), None, "Enterprise value relative to operating cash earnings"),
        ],
    )
    health = _table(
        ["Metric", "Value", "Reading", "What it measures"],
        [
            _row("Piotroski F-score", "n/a" if h.piotroski_f is None else f"{h.piotroski_f} / 9", _st_f(h.piotroski_f), "Nine pass/fail tests of profitability, leverage and efficiency (reported only when all nine can be computed)"),
            _row("Altman Z&Prime;", _num(h.altman_z), _st_z(h.altman_z), "Balance-sheet bankruptcy-risk model for non-financial firms"),
            _row("Debt / equity", _num(h.debt_to_equity), _st_de(h.debt_to_equity), "Total liabilities relative to shareholders' equity"),
            _row("Current ratio", _num(h.current_ratio), _st_cr(h.current_ratio), "Current assets relative to current liabilities"),
            _row("Interest coverage", _num(h.interest_coverage), _st_ic(h.interest_coverage), "Operating profit (EBIT) relative to interest expense"),
        ],
    )
    trend = g.margin_trend
    growth = _table(
        ["Metric", "Value", "Reading", "What it measures"],
        [
            _row("Revenue CAGR, 3 years", _pct(g.revenue_cagr_3y), _st_growth(g.revenue_cagr_3y), "Compound annual growth of revenue"),
            _row("Net income CAGR, 3 years", _pct(g.pat_cagr_3y), _st_growth(g.pat_cagr_3y), "Compound annual growth of net income"),
            _row("Operating margin trend", trend.capitalize() if trend else "n/a", None if trend is None else (trend.capitalize(), "good" if trend == "improving" else "warn" if trend == "stable" else "bad"), "Change in operating margin over three years"),
            _row("Free cash flow yield", _pct(g.fcf_yield), _st_sign(g.fcf_yield), "Free cash flow relative to market capitalisation"),
        ],
    )
    quality = ""
    if q is not None:
        quality = "<h2>Profitability and cash quality</h2>" + _table(
            ["Metric", "Value", "Reading", "What it measures"],
            [
                _row("Net margin", _pct(q.net_margin), _st_sign(q.net_margin), "Net income / revenue (DuPont, part 1)"),
                _row("Asset turnover", _num(q.asset_turnover), None, "Revenue / average assets (DuPont, part 2)"),
                _row("Equity multiplier", _num(q.equity_multiplier), None, "Average assets / average equity (DuPont, part 3)"),
                _row("Return on equity", _pct(q.roe), _st_sign(q.roe), "Net margin x asset turnover x equity multiplier"),
                _row("Return on invested capital", _pct(q.roic), _st_sign(q.roic), "After-tax operating profit / average invested capital"),
                _row("Free cash flow margin", _pct(q.fcf_margin), _st_sign(q.fcf_margin), "(Operating cash flow - capex) / revenue"),
                _row("Free cash flow / net income", _num(q.fcf_to_net_income), None, "Cash conversion of profit (shown when net income is positive)"),
                _row("Accruals ratio", _pct(q.accruals_ratio), None, "(Net income - operating cash flow) / average assets; lower means cash-backed earnings"),
                _row("Cash conversion cycle", _days(q.cash_conversion_cycle_days), None, "Days sales + days inventory - days payables"),
                _row("Change in share count", _pct(q.share_count_change), None, "Positive means dilution, negative means buybacks"),
            ],
        )

    signals = r.health.piotroski_signals or {}
    sig_rows = []
    for name, what in SIGNALS:
        got = signals.get(name)
        status = ("n/a", "na") if got is None else ("Pass", "good") if got else ("Fail", "bad")
        sig_rows.append(f"<tr><td>{name}</td><td>{_tag(*status)}</td><td class=\"what\">{what}</td></tr>")
    sig_table = (
        "<table><thead><tr><th>Signal</th><th>Result</th><th>Test</th></tr></thead><tbody>"
        + "".join(sig_rows)
        + "</tbody></table>"
    )

    if r.red_flags:
        flag_rows = "".join(
            f"<tr><td>{f.type.replace('_', ' ')}</td><td class=\"num\">{_num(f.value) if isinstance(f.value, (int, float)) else f.value}</td>"
            f"<td>{_tag(f.severity.capitalize(), 'bad' if f.severity == 'high' else 'warn')}</td></tr>"
            for f in r.red_flags
        )
        flags = f"<table><thead><tr><th>Flag</th><th class=num>Value</th><th>Severity</th></tr></thead><tbody>{flag_rows}</tbody></table>"
    else:
        flags = '<p class="none">No red flags were triggered by the checks that could be run.</p>'

    body = f"""
<h2>Summary</h2><div class="summary">{r.analyst_brief}</div>
<div class="cards">{cards}</div>
<h2>Valuation</h2>{valuation}
<h2>Financial health</h2>{health}
<h2>Growth</h2>{growth}
{quality}
<h2>Piotroski F-score signals</h2>{sig_table}
<h2>Red flags</h2>{flags}
{_notes(r.notes)}"""
    return _page(
        r.company,
        "Financial statement analysis",
        f"{r.ticker} &middot; {r.exchange}",
        body,
    )


# ----------------------------------------------------------------------------- compare
# metric label, getter, formatter, direction (+1 higher is better, -1 lower is better, 0 none)
_Metric = tuple[str, Callable[[ScanResult], float | None], Callable[[float | None], str], int]

_COMPARE_SECTIONS: list[tuple[str, list[_Metric]]] = [
    (
        "Valuation (no winner is implied)",
        [
            ("P/E ratio", lambda r: r.valuation.pe_ratio, _num, 0),
            ("P/B ratio", lambda r: r.valuation.pb_ratio, _num, 0),
            ("EV / EBITDA", lambda r: r.valuation.ev_ebitda, _num, 0),
        ],
    ),
    (
        "Financial health",
        [
            ("Piotroski F-score", lambda r: r.health.piotroski_f, lambda x: _num(x, 0), 1),
            ("Altman Z″", lambda r: r.health.altman_z, _num, 1),
            ("Debt / equity", lambda r: r.health.debt_to_equity, _num, -1),
            ("Current ratio", lambda r: r.health.current_ratio, _num, 1),
            ("Interest coverage", lambda r: r.health.interest_coverage, _num, 1),
            ("Beneish M-score", lambda r: r.beneish_m, _num, -1),
        ],
    ),
    (
        "Growth",
        [
            ("Revenue CAGR, 3 years", lambda r: r.growth.revenue_cagr_3y, _pct, 1),
            ("Net income CAGR, 3 years", lambda r: r.growth.pat_cagr_3y, _pct, 1),
            ("Free cash flow yield", lambda r: r.growth.fcf_yield, _pct, 1),
        ],
    ),
    (
        "Profitability and cash quality",
        [
            ("Return on equity", lambda r: r.quality.roe if r.quality else None, _pct, 1),
            ("Return on invested capital", lambda r: r.quality.roic if r.quality else None, _pct, 1),
            ("Free cash flow margin", lambda r: r.quality.fcf_margin if r.quality else None, _pct, 1),
            ("Cash conversion cycle", lambda r: r.quality.cash_conversion_cycle_days if r.quality else None, _days, -1),
        ],
    ),
]


def compare_report(c: CompareResult) -> str:
    a, b = c.result_a, c.result_b
    sections = []
    wins = {"a": 0, "b": 0}
    for title, metrics in _COMPARE_SECTIONS:
        rows = []
        for label, get, fmt, direction in metrics:
            va, vb = get(a), get(b)
            better = ""
            if direction and va is not None and vb is not None and va != vb:
                a_better = (va > vb) == (direction > 0)
                better = _tag(a.ticker if a_better else b.ticker, "good")
                wins["a" if a_better else "b"] += 1
            rows.append(
                f'<tr><td>{label}</td><td class="num">{fmt(va)}</td><td class="num">{fmt(vb)}</td>'
                f"<td>{better}</td></tr>"
            )
        sections.append(
            f"<h2>{title}</h2>"
            + _table(["Metric", a.ticker, b.ticker, "Stronger"], rows, num_cols=(1, 2))
        )
    tally = (
        f"<h2>Overview</h2><div class=\"summary\"><b>{a.ticker}</b> is stronger on {wins['a']} "
        f"metrics and <b>{b.ticker}</b> on {wins['b']}, counting only metrics where a direction "
        "is meaningful and both values exist. This is a count of screening statistics, "
        "not a recommendation.</div>"
    )
    both = (
        f"<h2>{a.ticker}: summary</h2><div class=\"summary\">{a.analyst_brief}</div>"
        f"<h2>{b.ticker}: summary</h2><div class=\"summary\">{b.analyst_brief}</div>"
    )
    notes = _notes([f"{a.ticker}: {n}" for n in a.notes] + [f"{b.ticker}: {n}" for n in b.notes])
    return _page(
        f"{a.company} vs {b.company}",
        "Comparison",
        f"{a.ticker} &middot; {b.ticker}",
        tally + "".join(sections) + both + notes,
    )


# ----------------------------------------------------------------------------- screen
def screen_report(results: Sequence[ScanResult]) -> str:
    rows = []
    for r in results:
        fl, fk = _st_f(r.health.piotroski_f)
        rows.append(
            f"<tr><td>{r.ticker}</td><td>{r.company}</td>"
            f'<td class="num">{_num(r.health.piotroski_f, 0)}</td>'
            f'<td class="num">{_num(r.health.altman_z)}</td>'
            f'<td class="num">{_num(r.health.debt_to_equity)}</td>'
            f'<td class="num">{_num(r.valuation.pe_ratio)}</td>'
            f'<td class="num">{_pct(r.growth.revenue_cagr_3y)}</td>'
            f'<td>{_tag(fl, fk)}</td></tr>'
        )
    if not rows:
        table = '<p class="none">No company passed the screen (or none had enough data).</p>'
    else:
        table = (
            "<table><thead><tr><th>Ticker</th><th>Company</th><th class=num>F-score</th>"
            "<th class=num>Altman Z&Prime;</th><th class=num>Debt/equity</th>"
            "<th class=num>P/E</th><th class=num>Revenue CAGR</th><th>Health</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    body = (
        f"<h2>Companies that passed ({len(results)})</h2>{table}"
        '<p class="none">The screen covers a small built-in example list, not the whole market.</p>'
    )
    return _page("Sector screen", "Screening results", f"{len(results)} companies", body)
