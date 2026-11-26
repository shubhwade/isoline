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
import math
from collections.abc import Sequence

from isoline import __version__
from isoline.branding import BRAND
from isoline.core.comparison import SECTIONS, format_value, stronger
from isoline.core.result import CompareResult, ScanResult

DISCLAIMER = (
    "Isoline produces screening statistics from public financial statements obtained from "
    "Yahoo Finance, an unofficial source that may be delayed, incomplete or wrong. "
    "Nothing in this report is investment advice, a recommendation, or an offer to buy or "
    "sell any security. Isoline is not a registered investment adviser or research analyst. "
    "Verify figures against the company's filings before relying on them."
)

CSS = """
:root{--ink:#141414;--muted:#5c5c58;--line:#dededa;--soft:#f5f5f3;--navy:#0a0a0a;
--good:#1b6b43;--warn:#8a5a00;--bad:#a42a22;--goodbg:#e8f4ed;--warnbg:#fbf2df;--badbg:#fbe9e7}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#efefec;color:var(--ink);
font:14px/1.5 Calibri,"Segoe UI",Arial,"Helvetica Neue",sans-serif;
font-variant-numeric:lining-nums tabular-nums}
.page{max-width:900px;margin:24px auto;background:#fff;padding:40px 48px;
border:1px solid var(--line);box-shadow:0 1px 3px rgba(0,0,0,.06)}
header.rep{border-bottom:3px solid var(--navy);padding-bottom:14px;margin-bottom:22px}
.kicker{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
h1{font:700 27px/1.25 "Times New Roman",Times,serif;margin:4px 0 2px;color:var(--navy);letter-spacing:.2px}
.sub{color:var(--muted);font-size:13px}
h2{font:700 16px/1.3 "Times New Roman",Times,serif;color:var(--navy);margin:28px 0 8px;
padding-bottom:4px;border-bottom:1px solid var(--line)}
.summary{background:var(--soft);border-left:4px solid var(--navy);padding:12px 16px;margin:0 0 6px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0 4px}
.card{border:1px solid var(--line);padding:12px 14px;border-radius:4px;min-width:0}
.card .lab{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.card .val{font:700 25px/1.2 Calibri,"Segoe UI",Arial,sans-serif;margin:4px 0 2px;color:var(--navy)}
.card .sub2{font-size:12px;font-weight:600}
.bar{position:relative;height:6px;background:#e6e6e2;border-radius:3px;margin-top:8px}
.fig{margin:10px 0 4px;border:1px solid var(--line);padding:10px 12px 6px}
.fig figcaption{font:700 13px "Times New Roman",Times,serif;color:var(--navy);margin-bottom:2px}
.fig .src{font-size:11px;color:var(--muted)}
.fig svg{width:100%;height:auto;display:block}
.fig text{font-family:Calibri,"Segoe UI",Arial,sans-serif;fill:#3c3c38}
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
.bad{color:var(--bad);background:var(--badbg)}.na{color:var(--muted);background:#ececea}
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
    tag = "" if status[1] == "na" else f'<span class="tag {status[1]}">{status[0]}</span>'
    return (
        f'<div class="card"><div class="lab">{label}</div><div class="val">{value}</div>'
        f'<div class="sub2">{tag or "&nbsp;"}</div>{bar}</div>'
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
<footer><span>Generated by {BRAND.command} v{__version__}</span><span>Data: Yahoo Finance (yfinance) or SEC EDGAR; see Notes</span></footer>
</div></body></html>"""


def _notes(notes: Sequence[str]) -> str:
    if not notes:
        return ""
    items = "".join(f"<li>{n}</li>" for n in notes)
    return f"<h2>Data notes</h2><p class=\"none\">Metrics shown as n/a, and why.</p><ul class=\"notes\">{items}</ul>"


# ----------------------------------------------------------------------------- charts (inline SVG)
PALETTE = ["#141414", "#8a8a86", "#c4c4bf"]
LINE_COLOR = "#d13a10"


def _scale(values: Sequence[float | None]) -> tuple[float, str]:
    nums = [abs(v) for v in values if v is not None]
    m = max(nums) if nums else 0
    if m >= 1e12:
        return 1e12, "trillions"
    if m >= 1e9:
        return 1e9, "billions"
    if m >= 1e6:
        return 1e6, "millions"
    if m >= 1e3:
        return 1e3, "thousands"
    return 1.0, ""


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
    # nice step from {1, 2, 2.5, 5, 10} x power of ten
    exp = math.floor(math.log10(raw)) if raw > 0 else 0
    base = 10.0**exp
    step = next(m * base for m in (1, 2, 2.5, 5, 10) if m * base >= raw)
    start = math.floor(lo / step) * step
    out = []
    t = start
    while True:  # include the first tick at or above hi, so no bar can exceed the axis
        out.append(round(t, 10))
        if t >= hi - step * 0.001:
            break
        t += step
    return out


def _chart(
    title: str,
    years: Sequence[str],
    bars: Sequence[tuple[str, Sequence[float | None]]],
    currency: str,
    line: tuple[str, Sequence[float | None]] | None = None,
) -> str:
    """Grouped bar chart (+ optional line on a right-hand % axis) as inline SVG."""
    all_vals = [v for _, vals in bars for v in vals]
    if not any(v is not None for v in all_vals):
        return ""
    div, unit_word = _scale(all_vals)
    unit = (currency + " " if currency else "") + unit_word
    unit = unit.strip()
    scaled = [(n, [None if v is None else v / div for v in vals]) for n, vals in bars]
    flat = [v for _, vals in scaled for v in vals if v is not None]
    lo, hi = min(0.0, min(flat)), max(0.0, max(flat))
    ticks = _ticks(lo, hi)
    lo, hi = ticks[0], ticks[-1]

    W, H = 720, 310
    ml, mr, mt, mb = 58, 58 if line else 18, 30, 66
    pw, ph = W - ml - mr, H - mt - mb
    n = len(years)

    def y(v: float) -> float:
        return mt + ph * (1 - (v - lo) / (hi - lo))

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{title}">']
    for t in ticks:
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e4e4e0" stroke-width="1"/>')
        out.append(f'<text x="{ml - 8}" y="{y(t) + 4:.1f}" font-size="11" text-anchor="end">{t:g}</text>')
    out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#7c7c78" stroke-width="1.2"/>')
    if unit:
        out.append(f'<text x="{ml}" y="14" font-size="11" text-anchor="start" style="fill:#5c5c58">Amounts in {unit}</text>')

    group = pw / n
    bw = group * 0.66 / len(scaled)
    for i, year in enumerate(years):
        gx = ml + group * i + group * 0.17
        for j, (_, vals) in enumerate(scaled):
            v = vals[i]
            if v is None:
                continue
            x = gx + j * bw
            top, bottom = (y(v), y(0)) if v >= 0 else (y(0), y(v))
            out.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw - 3:.1f}" height="{max(bottom - top, 0.5):.1f}" fill="{PALETTE[j % 3]}"/>')
            ly = top - 4 if v >= 0 else bottom + 11
            out.append(f'<text x="{x + (bw - 3) / 2:.1f}" y="{ly:.1f}" font-size="10.5" text-anchor="middle">{v:,.1f}</text>')
        out.append(f'<text x="{ml + group * (i + 0.5):.1f}" y="{H - mb + 18}" font-size="12" text-anchor="middle">{year}</text>')

    if line:
        lname, lvals = line
        nums = [v for v in lvals if v is not None]
        if nums:
            llo, lhi = min(nums + [0.0]), max(nums + [0.0])
            pad = (lhi - llo) * 0.15 or 0.02
            llo, lhi = llo - pad, lhi + pad

            def ly_(v: float) -> float:
                return mt + ph * (1 - (v - llo) / (lhi - llo))

            for t in _ticks(llo, lhi, 5):
                if llo <= t <= lhi:
                    out.append(f'<text x="{W - mr + 8}" y="{ly_(t) + 4:.1f}" font-size="11">{t * 100:.0f}%</text>')
            pts = [(ml + group * (i + 0.5), ly_(v), v) for i, v in enumerate(lvals) if v is not None]
            for (x1, y1, _), (x2, y2, _) in zip(pts, pts[1:], strict=False):
                out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{LINE_COLOR}" stroke-width="2"/>')
            for x, yy, v in pts:
                out.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="3.5" fill="#fff" stroke="{LINE_COLOR}" stroke-width="2"/>')
                out.append(f'<text x="{x:.1f}" y="{yy - 8:.1f}" font-size="10.5" text-anchor="middle" style="fill:{LINE_COLOR}">{v * 100:.1f}%</text>')

    # legend
    lx = ml
    ly = H - 14
    for j, (name, _) in enumerate(scaled):
        out.append(f'<rect x="{lx}" y="{ly - 9}" width="11" height="11" fill="{PALETTE[j % 3]}"/>')
        out.append(f'<text x="{lx + 16}" y="{ly}" font-size="12">{name}</text>')
        lx += 16 + 7 * len(name) + 22
    if line:
        out.append(f'<line x1="{lx}" x2="{lx + 16}" y1="{ly - 4}" y2="{ly - 4}" stroke="{LINE_COLOR}" stroke-width="2"/>')
        out.append(f'<circle cx="{lx + 8}" cy="{ly - 4}" r="3.5" fill="#fff" stroke="{LINE_COLOR}" stroke-width="2"/>')
        out.append(f'<text x="{lx + 22}" y="{ly}" font-size="12">{line[0]} (right axis)</text>')
    out.append("</svg>")
    return (
        f'<figure class="fig"><figcaption>{title}</figcaption>{"".join(out)}'
        '<div class="src">Source: company annual statements via Yahoo Finance. A missing bar means the figure was not reported.</div></figure>'
    )


def _charts(r: ScanResult) -> str:
    hst = r.history
    if hst is None:
        return ""
    c1 = _chart(
        "Revenue, net income and operating margin",
        hst.years,
        [("Revenue", hst.revenue), ("Net income", hst.net_income)],
        hst.currency,
        line=("Operating margin", hst.operating_margin),
    )
    c2 = _chart(
        "Earnings quality: net income vs cash generation",
        hst.years,
        [
            ("Net income", hst.net_income),
            ("Operating cash flow", hst.operating_cash_flow),
            ("Free cash flow", hst.free_cash_flow),
        ],
        hst.currency,
    )
    if not (c1 or c2):
        return ""
    return f"<h2>Performance charts</h2>{c1}{c2}"


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
{_charts(r)}
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

def compare_report(c: CompareResult) -> str:
    a, b = c.result_a, c.result_b
    sections = []
    wins = {"a": 0, "b": 0}
    for title, metrics in SECTIONS:
        rows = []
        for m in metrics:
            va, vb = m.get(a), m.get(b)
            win = stronger(va, vb, m.direction)
            better = ""
            if win:
                wins[win] += 1
                better = _tag(a.ticker if win == "a" else b.ticker, "good")
            rows.append(
                f'<tr><td>{m.label}</td><td class="num">{format_value(va, m.kind)}</td>'
                f'<td class="num">{format_value(vb, m.kind)}</td><td>{better}</td></tr>'
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
