"""Formal, print-ready HTML reports: company scan, comparison, sector screen, portfolio.

Design rules:
* Self-contained: inline CSS and inline SVG only. No JavaScript, no CDN, no web fonts,
  no network access. A Content-Security-Policy forbids scripts and remote loads, so even
  a bug elsewhere cannot make the page run code. It opens offline and prints to A4/Letter.
* Laid out like published financial statements: fiscal years in columns, newest first,
  amounts in one stated unit, costs in parentheses, subtotal and total rules.
* Status is always conveyed by a word (Strong / Adequate / Weak / n/a), never colour alone.
* Missing data is "n/a", never zero.
* Every string that came from a provider or the command line is HTML-escaped by the caller
  (``escape_obj``) before it reaches these functions.
"""

from __future__ import annotations

import datetime
import math
from collections.abc import Sequence
from typing import Any

from isoline import __version__
from isoline.branding import BRAND
from isoline.core.comparison import SECTIONS, format_value, stronger
from isoline.core.result import CompareResult, ScanResult, StatementLine, StatementsResult

DISCLAIMER = (
    "Isoline produces screening statistics from public financial statements obtained from "
    "Yahoo Finance or SEC EDGAR, sources that may be delayed, incomplete or wrong. "
    "Nothing in this report is investment advice, a recommendation, or an offer to buy or "
    "sell any security. Isoline is not a registered investment adviser or research analyst. "
    "Verify figures against the company's filings before relying on them."
)

CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"

CSS = """
:root{--ink:#111;--ink2:#3a3a37;--muted:#6b6b66;--line:#d9d9d4;--hair:#ecece8;--soft:#f6f6f3;
--accent:#c8361b;--good:#1b6b43;--warn:#8a5a00;--bad:#a42a22;--goodbg:#e7f3ec;--warnbg:#faf1de;--badbg:#fae8e5}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#ebebe8;color:var(--ink);
font:13.5px/1.5 "Helvetica Neue",Helvetica,Arial,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums lining-nums}
.page{max-width:980px;margin:28px auto;background:#fff;padding:48px 56px 40px;border:1px solid var(--line)}
a{color:inherit}
.mast{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;border-bottom:2px solid var(--ink);padding-bottom:16px}
.kicker{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.kicker b{color:var(--accent);font-weight:700}
h1{font:400 34px/1.1 "Times New Roman",Times,serif;margin:8px 0 0;letter-spacing:-.01em}
.mark{font:700 12px/1 "Helvetica Neue",Arial,sans-serif;letter-spacing:.02em;white-space:nowrap}
.mark i{font-style:normal;color:var(--accent)}
.meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;border-bottom:1px solid var(--line);margin-bottom:26px}
.meta div{padding:10px 12px 10px 0}
.meta dt{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.meta dd{margin:2px 0 0;font-weight:600;overflow-wrap:anywhere}
h2{font:400 21px/1.25 "Times New Roman",Times,serif;margin:34px 0 4px;padding-bottom:6px;border-bottom:1px solid var(--ink)}
h2 .n,h3 .n{color:var(--accent);font:700 12px/1 "Helvetica Neue",Arial,sans-serif;margin-right:10px;vertical-align:3px}
h3{font:700 13px/1.3 "Helvetica Neue",Arial,sans-serif;margin:22px 0 2px;letter-spacing:.01em}
.unit{font-size:11px;color:var(--muted);margin:0 0 6px}
p.lead{font-size:15px;line-height:1.55;margin:10px 0 0;color:var(--ink2)}
.figs{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:18px 0 6px}
.fig1{padding:12px 12px 12px 0;border-right:1px solid var(--hair)}
.fig1:last-child{border-right:0}
.fig1 .l{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.fig1 .v{font:600 21px/1.15 "Helvetica Neue",Helvetica,Arial,sans-serif;letter-spacing:-.01em;margin:4px 0 2px;white-space:nowrap}
.fig1 .c{font-size:11.5px;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0 4px}
.card{border:1px solid var(--line);padding:11px 13px}
.card .l{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.card .v{font:700 22px/1.2 "Helvetica Neue",Arial,sans-serif;margin:3px 0}
.meter{height:4px;background:var(--hair);margin-top:8px}.meter i{display:block;height:100%;background:var(--ink)}
.toc{columns:2;column-gap:40px;margin:12px 0 0;padding:0;list-style:none;font-size:13px}
.toc li{padding:4px 0;border-bottom:1px dotted var(--line);break-inside:avoid}
.toc a{text-decoration:none}.toc .n{color:var(--accent);font-weight:700;margin-right:8px}
table{border-collapse:collapse;width:100%;margin:4px 0}
th,td{padding:6px 8px;text-align:left;vertical-align:top}
thead th{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);font-weight:600;border-bottom:1px solid var(--ink)}
tbody td{border-bottom:1px solid var(--hair)}
td.num,th.num{text-align:right;white-space:nowrap}
td.what{color:var(--muted);font-size:12px}
table.fs{table-layout:fixed}
table.fs th:first-child,table.fs td:first-child{width:34%}
table.fs thead th{text-align:right}table.fs thead th:first-child{text-align:left}
table.fs .yr{display:block;color:var(--ink);font-size:11px;letter-spacing:.04em}
table.fs .dt{display:block;text-transform:none;letter-spacing:0;font-weight:400}
table.fs td{border-bottom:0;padding:4px 8px}
table.fs tr.sub td{border-top:1px solid var(--ink2);font-weight:600}
table.fs tr.tot td{border-top:1px solid var(--ink);border-bottom:3px double var(--ink);font-weight:700}
table.fs tr.memo td{color:var(--muted);font-style:italic}
table.fs tr.grp td{padding-top:14px;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
table.fs tbody tr.grp:first-child td{padding-top:6px}
table.fs tr.memo:first-of-type td,table.fs tr.gap td{padding-top:14px}
table.fs td.ana{color:var(--muted);font-size:12px}
table.fs th.ana,table.fs td.ana{border-left:1px solid var(--hair)}
.neg{color:inherit}
.na{color:var(--muted)}
.tag{display:inline-block;padding:1px 7px;border-radius:2px;font-size:11px;font-weight:600;white-space:nowrap}
.t-good{color:var(--good);background:var(--goodbg)}.t-warn{color:var(--warn);background:var(--warnbg)}
.t-bad{color:var(--bad);background:var(--badbg)}.t-na{color:var(--muted);background:var(--soft)}
.note{font-size:11.5px;color:var(--muted);margin:6px 0 0}
.box{border-left:3px solid var(--ink);background:var(--soft);padding:12px 16px;margin:10px 0}
.chart{margin:10px 0 4px}
.chart figcaption{font-weight:700;font-size:12.5px;margin-bottom:2px}
.chart svg{width:100%;height:auto;display:block}
.chart text{font-family:"Helvetica Neue",Arial,sans-serif;fill:#3a3a37}
.chart text.lab{paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}
.chart .src{font-size:11px;color:var(--muted)}
ul.notes{margin:6px 0 0 18px;padding:0;color:var(--ink2);font-size:12.5px}
ul.notes li{margin:3px 0}
.disc{margin-top:30px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted);font-size:11px}
footer.rep{margin-top:10px;color:var(--muted);font-size:10.5px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
.grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px}
td.base{background:var(--ink);color:#fff;font-weight:700}
@media (max-width:760px){.page{padding:24px 16px;margin:0}.meta{grid-template-columns:repeat(2,minmax(0,1fr))}
.figs{grid-template-columns:repeat(2,minmax(0,1fr))}.fig1{border-right:0;border-bottom:1px solid var(--hair)}
.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.toc{columns:1}.grid2{grid-template-columns:minmax(0,1fr)}
.scroll{overflow-x:auto}table.fs{min-width:640px}h1{font-size:27px}}
@page{size:A4;margin:16mm 14mm 18mm;
@bottom-left{content:"__FOOT__";font:8pt "Helvetica Neue",Arial,sans-serif;color:#6b6b66}
@bottom-right{content:"Page " counter(page) " of " counter(pages);font:8pt "Helvetica Neue",Arial,sans-serif;color:#6b6b66}}
@media print{body{background:#fff;font-size:10pt}.page{margin:0;border:0;max-width:none;padding:0}
.fig1 .v{font-size:17px}.card .v{font-size:18px}h1{font-size:28px}
section.major{break-before:page}h2,h3{break-after:avoid}tr,.card,.fig1,.chart{break-inside:avoid}
.toc a{text-decoration:none}.scroll{overflow:visible}}
"""


# ----------------------------------------------------------------------------- formatting
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
    return f'<span class="tag t-{kind}">{label}</span>'


def _scale(values: Sequence[float | None]) -> tuple[float, str]:
    """Unit for a set of amounts, chosen so the largest shows 100 to 99,999 (as filings do)."""
    nums = [abs(v) for v in values if v is not None]
    m = max(nums) if nums else 0
    for div, word in ((1e9, "billions"), (1e6, "millions"), (1e3, "thousands")):
        if m >= div * 100:
            return div, word
    return 1.0, ""


def _acct(v: float | None, div: float, nd: int) -> str:
    """Accounting format: thousands separators, negatives in parentheses."""
    if v is None:
        return '<span class="na">n/a</span>'
    x = v / div
    if round(x, nd) == 0:
        x = 0.0
    s = f"{abs(x):,.{nd}f}"
    return f"({s})" if x < 0 else s


def _sig3(x: float) -> str:
    """Three significant figures: 1.48, 18.0, 180."""
    return f"{x:,.2f}" if x < 10 else f"{x:,.1f}" if x < 100 else f"{x:,.0f}"


def _money(v: float | None, currency: str = "") -> str:
    """Compact amount for headline figures: 1.48B, 180M (negatives in parentheses)."""
    if v is None:
        return "n/a"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            s = _sig3(abs(v) / div) + suf
            break
    else:
        s = f"{abs(v):,.2f}"
    s = f"{currency} {s}".strip()
    return f"({s})" if v < 0 else s


OUTFLOW_KEYS = {"capex", "dividends", "buybacks", "cfi"}


def _change(new: float | None, old: float | None, outflow: bool = False) -> str:
    """Year-on-year change; "n.m." (not meaningful) when a base year is negative.

    For lines that are normally outflows (capex, dividends, buybacks, investing cash flow)
    two negative years give the change in size, so higher spending reads as an increase.
    """
    if new is None or old is None or old == 0:
        return "n/a"
    if outflow and new <= 0 and old < 0:
        return f"{(abs(new) - abs(old)) / abs(old) * 100:+.1f}%"
    if old < 0 or (new < 0 and old > 0 and outflow):
        return "n.m."
    return f"{(new - old) / old * 100:+.1f}%"


def _fy(period: str) -> tuple[str, str]:
    try:
        d = datetime.date.fromisoformat(period)
    except ValueError:
        return period, ""
    return f"FY{d.year}", d.strftime("%d %b %Y")


# ----------------------------------------------------------------------------- status labels
def _st_f(v: int | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Strong", "good") if v >= 7 else ("Adequate", "warn") if v >= 5 else ("Weak", "bad")


def _st_z(v: float | None) -> tuple[str, str]:
    if v is None:
        return "n/a", "na"
    return ("Safe zone", "good") if v > 2.6 else ("Grey zone", "warn") if v >= 1.1 else ("Distress zone", "bad")


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


# ----------------------------------------------------------------------------- building blocks
def _row(label: str, value: str, status: tuple[str, str] | None, what: str) -> str:
    st = _tag(*status) if status else ""
    return f'<tr><td>{label}</td><td class="num">{value}</td><td>{st}</td><td class="what">{what}</td></tr>'


def _ratio_table(rows: Sequence[str]) -> str:
    return (
        '<div class="scroll"><table><colgroup><col style="width:28%"><col style="width:14%">'
        '<col style="width:17%"><col></colgroup><thead><tr><th>Metric</th><th class="num">Value</th>'
        f"<th>Reading</th><th>What it measures</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _card(label: str, value: str, status: tuple[str, str], fill: float | None) -> str:
    meter = ""
    if fill is not None:
        meter = f'<div class="meter"><i style="width:{max(0.0, min(1.0, fill)) * 100:.0f}%"></i></div>'
    tag = _tag(*status) if status[1] != "na" else '<span class="na">not computed</span>'
    return f'<div class="card"><div class="l">{label}</div><div class="v">{value}</div>{tag}{meter}</div>'


def _section(num: str, anchor: str, title: str, body: str, major: bool = False) -> str:
    cls = ' class="major"' if major else ""
    return f'<section id="{anchor}"{cls}><h2><span class="n">{num}</span>{title}</h2>{body}</section>'


def _sub(num: str, title: str) -> str:
    return f'<h3><span class="n">{num}</span>{title}</h3>'


def _page(title: str, kicker: str, meta: Sequence[tuple[str, str]], body: str, source: str) -> str:
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    meta_html = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in [*meta, ("Prepared", now)])
    foot = f"{BRAND.name} v{__version__} · {kicker}".replace('"', "'")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="{BRAND.name} {__version__}">
<title>{title} · {kicker}</title><style>{CSS.replace("__FOOT__", foot)}</style></head>
<body><div class="page">
<header class="mast"><div><div class="kicker"><b>&#9679;</b>&nbsp; {kicker}</div><h1>{title}</h1></div>
<div class="mark"><i>i</i>soline</div></header>
<dl class="meta">{meta_html}</dl>
{body}
<div class="disc">{DISCLAIMER}</div>
<footer class="rep"><span>Generated by {BRAND.command} v{__version__} · {BRAND.site_url}</span><span>Data: {source}</span></footer>
</div></body></html>"""


def _notes_list(notes: Sequence[str]) -> str:
    if not notes:
        return '<p class="note">Every metric in this report could be computed from the data available.</p>'
    return '<ul class="notes">' + "".join(f"<li>{n}</li>" for n in notes) + "</ul>"


def _source(r: ScanResult) -> str:
    notes = " ".join(r.notes).lower()
    return "SEC EDGAR (XBRL company facts)" if "sec edgar" in notes else "Yahoo Finance (yfinance)"


# ----------------------------------------------------------------------------- statements
def _statement_scale(st: StatementsResult) -> tuple[float, str, int]:
    values = [v for lines in (st.income, st.balance, st.cashflow) for ln in lines if not ln.per_share for v in ln.values]
    div, word = _scale(values)
    biggest = max((abs(v) / div for v in values if v is not None), default=0)
    nd = 0 if biggest >= 100 else 2
    return div, word, nd


def _statement_table(
    lines: list[StatementLine],
    periods: list[str],
    div: float,
    nd: int,
    base_key: str | None,
    base_name: str,
) -> str:
    if not lines:
        return '<p class="note">This statement was not available from the data source.</p>'
    base = next((ln for ln in lines if ln.key == base_key), None)
    ncols = len(periods) + 3
    head = "".join(
        f'<th class="num"><span class="yr">{fy}</span><span class="dt">{dt}</span></th>' for fy, dt in map(_fy, periods)
    )
    rows = []
    prev_kind = ""
    prev_group = ""
    for ln in lines:
        if ln.group and ln.group != prev_group and ln.group not in ("Memo", "Free cash flow"):
            rows.append(f'<tr class="grp"><td colspan="{ncols}">{ln.group}</td></tr>')
        prev_group = ln.group
        shown = [None if v is None else v * ln.sign for v in ln.values]
        if ln.per_share:
            cells = "".join(f'<td class="num">{_acct(v, 1, 2)}</td>' for v in shown)
        else:
            cells = "".join(f'<td class="num">{_acct(v, div, nd)}</td>' for v in shown)
        yoy = _change(ln.values[0], ln.values[1], ln.key in OUTFLOW_KEYS) if len(ln.values) > 1 else "n/a"
        if base and not ln.per_share and ln.values[0] is not None and base.values[0]:
            share = f"{ln.values[0] / base.values[0] * 100:,.1f}%"
        else:
            share = ""
        mark = " &dagger;" if ln.computed else ""
        cls = {"subtotal": "sub", "total": "tot", "memo": "memo"}.get(ln.kind, "")
        if ln.kind == "memo" and prev_kind != "memo":
            cls += " gap"
        prev_kind = ln.kind
        rows.append(
            f'<tr class="{cls.strip()}"><td>{ln.label}{mark}</td>{cells}'
            f'<td class="num ana">{yoy}</td><td class="num ana">{share}</td></tr>'
        )
    return (
        '<div class="scroll"><table class="fs"><thead><tr><th>Fiscal year ended</th>'
        f'{head}<th class="num ana">YoY</th><th class="num ana">{base_name}</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _statements_section(r: ScanResult, num: str) -> str:
    st = r.statements
    if st is None:
        return _section(num, "statements", "Financial statements", '<p class="note">No statement data was available.</p>', True)
    div, word, nd = _statement_scale(st)
    unit = f"{st.currency} {word}".strip() or "Reported units"
    unit_line = f'<p class="unit">{unit}, except per-share amounts. Costs and outflows in parentheses. YoY compares the latest two years.</p>'
    computed = any(ln.computed for lines in (st.income, st.balance, st.cashflow) for ln in lines)
    body = (
        _sub(f"{num}.1", "Income statement") + unit_line
        + _statement_table(st.income, st.periods, div, nd, "revenue", "% rev.")
        + _sub(f"{num}.2", "Balance sheet") + unit_line
        + _statement_table(st.balance, st.periods, div, nd, "total_assets", "% assets")
        + _sub(f"{num}.3", "Cash flow statement") + unit_line
        + _statement_table(st.cashflow, st.periods, div, nd, None, "")
    )
    if st.notes:
        body += '<div class="box">' + "<br>".join(st.notes) + "</div>"
    if computed:
        body += '<p class="note">&dagger; Computed from reported lines: free cash flow = cash from operations &minus; capital expenditure; total liabilities and equity = total liabilities + total equity.</p>'
    body += '<p class="note">n/a: not reported by the company or the data source for that year. Values are never estimated or set to zero.</p>'
    return _section(num, "statements", "Financial statements", body, True)


def _key_figures(r: ScanResult) -> str:
    st = r.statements
    if st is None:
        return ""

    def line(lines: list[StatementLine], key: str) -> StatementLine | None:
        return next((ln for ln in lines if ln.key == key), None)

    rev, ni = line(st.income, "revenue"), line(st.income, "net_income")
    op = line(st.income, "operating_income")
    fcf, ta, eq = line(st.cashflow, "fcf"), line(st.balance, "total_assets"), line(st.balance, "equity")

    def latest(ln: StatementLine | None, i: int = 0) -> float | None:
        return ln.values[i] if ln and len(ln.values) > i else None

    margin = None
    if latest(op) is not None and latest(rev):
        margin = latest(op) / latest(rev)  # type: ignore[operator]
    prev_margin = None
    if latest(op, 1) is not None and latest(rev, 1):
        prev_margin = latest(op, 1) / latest(rev, 1)  # type: ignore[operator]
    margin_change = "n/a" if margin is None or prev_margin is None else f"{(margin - prev_margin) * 10000:+.0f} bp"
    fy = _fy(st.periods[0])[0] if st.periods else ""
    items = [
        ("Revenue", _money(latest(rev)), _change(latest(rev), latest(rev, 1))),
        ("Net income", _money(latest(ni)), _change(latest(ni), latest(ni, 1))),
        ("Op. margin", _pct(margin), margin_change),
        ("Free cash flow", _money(latest(fcf)), _change(latest(fcf), latest(fcf, 1))),
        ("Total assets", _money(latest(ta)), _change(latest(ta), latest(ta, 1))),
        ("Equity", _money(latest(eq)), _change(latest(eq), latest(eq, 1))),
    ]
    cells = "".join(f'<div class="fig1"><div class="l">{k}</div><div class="v">{v}</div><div class="c">{c} YoY</div></div>' for k, v, c in items)
    unit = f" &middot; amounts in {st.currency}" if st.currency else ""
    return f'<p class="unit" style="margin-top:6px">Key figures, {fy}{unit}</p><div class="figs">{cells}</div>'


# ----------------------------------------------------------------------------- charts (inline SVG)
PALETTE = ["#111111", "#8a8a86", "#c4c4bf"]
LINE_COLOR = "#c8361b"


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
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
    if not any(v is not None for v in all_vals) or not years:
        return ""
    div, unit_word = _scale(all_vals)
    unit = ((currency + " ") if currency else "") + unit_word
    unit = unit.strip()
    scaled = [(n, [None if v is None else v / div for v in vals]) for n, vals in bars]
    flat = [v for _, vals in scaled for v in vals if v is not None]
    nd = 0 if max(abs(v) for v in flat) >= 100 else 1
    lo, hi = min(0.0, min(flat)), max(0.0, max(flat))
    ticks = _ticks(lo, hi)
    lo, hi = ticks[0], ticks[-1]

    W, H = 760, 300
    ml, mr, mt, mb = 58, 58 if line else 18, 30, 60
    pw, ph = W - ml - mr, H - mt - mb
    n = len(years)

    def y(v: float) -> float:
        return mt + ph * (1 - (v - lo) / (hi - lo))

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{title}">']
    for t in ticks:
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#ecece8" stroke-width="1"/>')
        out.append(f'<text x="{ml - 8}" y="{y(t) + 4:.1f}" font-size="11" text-anchor="end">{t:,g}</text>')
    out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#3a3a37" stroke-width="1"/>')
    if unit:
        out.append(f'<text x="{ml}" y="14" font-size="11" text-anchor="start" style="fill:#6b6b66">{unit}</text>')

    group = pw / n
    bw = group * 0.66 / len(scaled)
    for i, year in enumerate(years):
        gx = ml + group * i + group * 0.17
        for j, (_, vals) in enumerate(scaled):
            v = vals[i] if i < len(vals) else None
            if v is None:
                continue
            x = gx + j * bw
            top, bottom = (y(v), y(0)) if v >= 0 else (y(0), y(v))
            out.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{max(bw - 3, 1):.1f}" height="{max(bottom - top, 0.5):.1f}" fill="{PALETTE[j % 3]}"/>')
            ly = top - 4 if v >= 0 else bottom + 11
            out.append(f'<text class="lab" x="{x + (bw - 3) / 2:.1f}" y="{ly:.1f}" font-size="10" text-anchor="middle">{v:,.{nd}f}</text>')
        out.append(f'<text x="{ml + group * (i + 0.5):.1f}" y="{H - mb + 18}" font-size="11.5" text-anchor="middle">{year}</text>')

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
                out.append(f'<text class="lab" x="{x + 6:.1f}" y="{yy - 9:.1f}" font-size="10" text-anchor="start" style="fill:{LINE_COLOR}">{v * 100:.1f}%</text>')

    lx, ly = ml, H - 12
    for j, (name, _) in enumerate(scaled):
        out.append(f'<rect x="{lx}" y="{ly - 9}" width="10" height="10" fill="{PALETTE[j % 3]}"/>')
        out.append(f'<text x="{lx + 15}" y="{ly}" font-size="11.5">{name}</text>')
        lx += 15 + 7 * len(name) + 22
    if line:
        out.append(f'<line x1="{lx}" x2="{lx + 16}" y1="{ly - 4}" y2="{ly - 4}" stroke="{LINE_COLOR}" stroke-width="2"/>')
        out.append(f'<text x="{lx + 22}" y="{ly}" font-size="11.5">{line[0]} (right axis)</text>')
    out.append("</svg>")
    return (
        f'<figure class="chart"><figcaption>{title}</figcaption>{"".join(out)}'
        '<div class="src">A missing bar means the figure was not reported for that year.</div></figure>'
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
        "Earnings quality: net income against cash generation",
        hst.years,
        [("Net income", hst.net_income), ("Operating cash flow", hst.operating_cash_flow), ("Free cash flow", hst.free_cash_flow)],
        hst.currency,
    )
    return c1 + c2


# ----------------------------------------------------------------------------- scan
SIGNALS = [
    ("ROA Positive", "Profitability", "Net income over opening assets is positive"),
    ("CFO Positive", "Profitability", "Operating cash flow is positive"),
    ("ROA Improving", "Profitability", "Return on assets is higher than last year"),
    ("Low Accruals", "Profitability", "Operating cash flow exceeds net income"),
    ("Leverage Falling", "Leverage and liquidity", "Long-term debt / average assets is lower than last year"),
    ("Liquidity Rising", "Leverage and liquidity", "Current ratio is higher than last year"),
    ("No Dilution", "Leverage and liquidity", "Share count did not increase"),
    ("Gross Margin Rising", "Operating efficiency", "Gross margin is higher than last year"),
    ("Asset Turnover Rising", "Operating efficiency", "Revenue / opening assets is higher than last year"),
]


def _dcf_section(r: ScanResult, num: str) -> str:
    d = r.dcf
    if not d:
        return _section(num, "dcf", "Valuation: discounted cash flow", '<p class="note">The DCF could not be run for this company.</p>', True)
    a = d.get("assumptions")
    notes = d.get("notes") or []
    if not a:
        why = " ".join(notes) or "Inputs were missing."
        body = f'<div class="box">Not computed. {why}</div><p class="note">Run <code>isoline value {r.ticker} --growth 0.05</code> to supply a growth assumption where history is too short.</p>'
        return _section(num, "dcf", "Valuation: discounted cash flow", body, True)
    cur = d.get("currency") or ""
    unit = (d.get("sensitivity") or {}).get("unit", "per share")
    per_share = unit == "per share"

    def val(eq: float | None, ps: float | None) -> str:
        if per_share:
            return "n/a" if ps is None else f"{cur} {ps:,.2f}".strip()
        return _money(eq, cur)

    assumptions = _ratio_table(
        [
            _row("Base free cash flow", _money(a.get("base_fcf"), cur), None, a.get("base_fcf_note", "")),
            _row("Year-1 growth", _pct(a.get("growth")), None, a.get("growth_source", "")),
            _row("Discount rate", _pct(a.get("discount_rate")), None, "Default assumption, not a cost-of-equity estimate"),
            _row("Terminal growth", _pct(a.get("terminal_growth")), None, "Growth after the explicit period, in perpetuity"),
            _row("Explicit period", f"{a.get('years', 'n/a')} years", None, "Growth fades linearly to terminal growth"),
            _row("Terminal value share", _pct(d.get("terminal_share")), None, "Share of the value that comes after the explicit period"),
        ]
    )
    scen_rows = "".join(
        f'<tr><td>{s.get("name")}</td><td class="num">{_pct(s.get("discount_rate"))}</td><td class="num">{_pct(s.get("growth"))}</td>'
        f'<td class="num">{val(s.get("equity_value"), s.get("per_share"))}</td></tr>'
        for s in d.get("scenarios") or []
    )
    scenarios = (
        '<table><thead><tr><th>Scenario</th><th class="num">Discount rate</th><th class="num">Growth</th>'
        f'<th class="num">Value {"per share" if per_share else ""}</th></tr></thead><tbody>{scen_rows}</tbody></table>'
    )
    sens = d.get("sensitivity") or {}
    rates, tgs, grid = sens.get("discount_rates") or [], sens.get("terminal_growths") or [], sens.get("values") or []
    sens_html = ""
    if rates and tgs and grid:
        head = "".join(f'<th class="num">{_pct(x)}</th>' for x in rates)
        body_rows = []
        for gi, (t, row) in enumerate(zip(tgs, grid, strict=False)):
            cells = []
            for ri, v in enumerate(row):
                txt = "n/a" if v is None else (f"{v:,.2f}" if per_share else _money(v, ""))
                cls = "num base" if gi == len(tgs) // 2 and ri == len(rates) // 2 else "num"
                cells.append(f'<td class="{cls}">{txt}</td>')
            body_rows.append(f'<tr><td>{_pct(t)}</td>{"".join(cells)}</tr>')
        sens_html = (
            f'{_sub(num + ".3", "Sensitivity")}<p class="unit">Value {unit} ({cur}); rows: terminal growth, columns: discount rate. Base case highlighted.</p>'
            f'<div class="scroll"><table><thead><tr><th>Terminal growth</th>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
        )
    headline = val(d.get("equity_value"), d.get("per_share"))
    mos = d.get("margin_of_safety")
    price_line = ""
    if d.get("price") is not None:
        price_line = f" against a market price of {cur} {d['price']:,.2f} (margin of safety {_pct(mos)})"
    body = (
        f'<div class="box">Base-case value: <b>{headline}</b>{" per share" if per_share and headline != "n/a" else ""}{price_line}. '
        "Illustrative: the result depends entirely on the assumptions below. It is not a price target.</div>"
        + _sub(num + ".1", "Assumptions") + assumptions
        + _sub(num + ".2", "Scenarios") + scenarios
        + sens_html
        + (_notes_list(notes) if notes else "")
    )
    return _section(num, "dcf", "Valuation: discounted cash flow", body, True)


def scan_report(r: ScanResult) -> str:
    h, g, v, q = r.health, r.growth, r.valuation, r.quality
    cards = "".join(
        [
            _card("Piotroski F-score", "n/a" if h.piotroski_f is None else f"{h.piotroski_f} / 9", _st_f(h.piotroski_f), None if h.piotroski_f is None else h.piotroski_f / 9),
            _card("Altman Z&Prime;", _num(h.altman_z), _st_z(h.altman_z), None if h.altman_z is None else min(max(h.altman_z, 0) / 5, 1)),
            _card("Beneish M-score", _num(r.beneish_m), _st_m(r.beneish_m), None),
            _card("Debt / equity", _num(h.debt_to_equity), _st_de(h.debt_to_equity), None),
        ]
    )
    trend = g.margin_trend
    ratio_body = (
        _sub("3.1", "Valuation multiples")
        + _ratio_table(
            [
                _row("P/E ratio", _num(v.pe_ratio), None, "Market capitalisation relative to annual earnings"),
                _row("P/B ratio", _num(v.pb_ratio), None, "Market capitalisation relative to book equity"),
                _row("EV / EBITDA", _num(v.ev_ebitda), None, "Enterprise value relative to operating cash earnings"),
            ]
        )
        + _sub("3.2", "Financial health")
        + _ratio_table(
            [
                _row("Debt / equity", _num(h.debt_to_equity), _st_de(h.debt_to_equity), "Total liabilities relative to shareholders' equity"),
                _row("Current ratio", _num(h.current_ratio), _st_cr(h.current_ratio), "Current assets relative to current liabilities"),
                _row("Interest coverage", _num(h.interest_coverage), _st_ic(h.interest_coverage), "Operating profit (EBIT) relative to interest expense"),
            ]
        )
        + _sub("3.3", "Growth")
        + _ratio_table(
            [
                _row("Revenue CAGR, 3 years", _pct(g.revenue_cagr_3y), _st_growth(g.revenue_cagr_3y), "Compound annual growth of revenue"),
                _row("Net income CAGR, 3 years", _pct(g.pat_cagr_3y), _st_growth(g.pat_cagr_3y), "Compound annual growth of net income"),
                _row(
                    "Operating margin trend",
                    trend.capitalize() if trend else "n/a",
                    None if trend is None else (trend.capitalize(), "good" if trend == "improving" else "warn" if trend == "stable" else "bad"),
                    "Change in operating margin over three years",
                ),
                _row("Free cash flow yield", _pct(g.fcf_yield), _st_sign(g.fcf_yield), "Free cash flow relative to market capitalisation"),
            ]
        )
    )
    if q is not None:
        ratio_body += _sub("3.4", "Profitability and cash quality") + _ratio_table(
            [
                _row("Net margin", _pct(q.net_margin), _st_sign(q.net_margin), "Net income / revenue (DuPont, part 1)"),
                _row("Asset turnover", _num(q.asset_turnover), None, "Revenue / average assets (DuPont, part 2)"),
                _row("Equity multiplier", _num(q.equity_multiplier), None, "Average assets / average equity (DuPont, part 3)"),
                _row("Return on equity", _pct(q.roe), _st_sign(q.roe), "Net margin &times; asset turnover &times; equity multiplier"),
                _row("Return on invested capital", _pct(q.roic), _st_sign(q.roic), "After-tax operating profit / average invested capital"),
                _row("Free cash flow margin", _pct(q.fcf_margin), _st_sign(q.fcf_margin), "(Operating cash flow &minus; capex) / revenue"),
                _row("Free cash flow / net income", _num(q.fcf_to_net_income), None, "Cash conversion of profit (shown when net income is positive)"),
                _row("Accruals ratio", _pct(q.accruals_ratio), None, "(Net income &minus; operating cash flow) / average assets; lower is better"),
                _row("Cash conversion cycle", _days(q.cash_conversion_cycle_days), None, "Days sales + days inventory &minus; days payables"),
                _row("Change in share count", _pct(q.share_count_change), None, "Positive means dilution, negative means buybacks"),
            ]
        )

    signals = h.piotroski_signals or {}
    sig_rows = []
    for name, group, what in SIGNALS:
        got = signals.get(name)
        status = ("n/a", "na") if got is None else ("Pass", "good") if got else ("Fail", "bad")
        sig_rows.append(f'<tr><td>{name}</td><td class="what">{group}</td><td>{_tag(*status)}</td><td class="what">{what}</td></tr>')
    tested = sum(1 for n, _, _ in SIGNALS if signals.get(n) is not None)
    score_line = (
        f"withheld: {tested} of 9 signals could be tested" if h.piotroski_f is None else f"{h.piotroski_f} of 9"
    )
    models = (
        _sub("4.1", "Piotroski F-score")
        + f'<p class="unit">Score {score_line}. One point per signal passed. Piotroski (2000).</p>'
        + '<div class="scroll"><table><thead><tr><th>Signal</th><th>Group</th><th>Result</th><th>Test</th></tr></thead><tbody>'
        + "".join(sig_rows) + "</tbody></table></div>"
        + _sub("4.2", "Altman Z&Prime;-score")
        + _ratio_table([_row("Z&Prime;", _num(h.altman_z), _st_z(h.altman_z), "6.56&middot;X1 + 3.26&middot;X2 + 6.72&middot;X3 + 1.05&middot;X4. Safe above 2.6, distress below 1.1. Altman (1983/1995)")])
        + _sub("4.3", "Beneish M-score")
        + _ratio_table([_row("M", _num(r.beneish_m), _st_m(r.beneish_m), "Eight-variable earnings-manipulation screen; above &minus;2.22 warrants review. Beneish (1999)")])
        + _sub("4.4", "Red flags")
    )
    if r.red_flags:
        flag_rows = "".join(
            f"<tr><td>{f.label[:1].upper() + f.label[1:]}</td><td class=\"num\">{_num(f.value) if isinstance(f.value, (int, float)) else f.value}</td>"
            f"<td>{_tag(f.severity.capitalize(), 'bad' if f.severity == 'high' else 'warn')}</td></tr>"
            for f in r.red_flags
        )
        models += f'<table><thead><tr><th>Flag</th><th class="num">Value</th><th>Severity</th></tr></thead><tbody>{flag_rows}</tbody></table>'
    else:
        models += '<p class="note">No red flags were triggered by the checks that could be run.</p>'

    charts = _charts(r)
    toc_items = [("1", "summary", "Summary"), ("2", "statements", "Financial statements"), ("3", "ratios", "Ratio analysis"),
                 ("4", "models", "Scoring models and red flags"), ("5", "dcf", "Valuation: discounted cash flow")]
    if charts:
        toc_items.append(("6", "trends", "Multi-year trends"))
    toc_items.append(("6" if not charts else "7", "notes", "Notes and data sources"))
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{a}"><span class="n">{n}</span>{t}</a></li>' for n, a, t in toc_items) + "</ul>"

    summary = f'<p class="lead">{r.analyst_brief}</p>{_key_figures(r)}<div class="cards">{cards}</div>{toc}'
    notes_num = "7" if charts else "6"
    body = (
        _section("1", "summary", "Summary", summary)
        + _statements_section(r, "2")
        + _section("3", "ratios", "Ratio analysis", ratio_body, True)
        + _section("4", "models", "Scoring models and red flags", models, True)
        + _dcf_section(r, "5")
        + (_section("6", "trends", "Multi-year trends", charts) if charts else "")
        + _section(
            notes_num,
            "notes",
            "Notes and data sources",
            _sub(f"{notes_num}.1", "Data notes") + _notes_list(r.notes)
            + _sub(f"{notes_num}.2", "Method")
            + '<p class="note">Ratios use the latest fiscal year unless stated; averages use the latest two balance sheets. '
            "Scores follow their published definitions and are withheld when any input is missing. "
            f"Full formulas: {BRAND.docs_url}methodology/</p>",
        )
    )
    st = r.statements
    periods = f"{_fy(st.periods[-1])[0]}&ndash;{_fy(st.periods[0])[0]}" if st and st.periods else "n/a"
    currency = (st.currency if st else "") or (r.history.currency if r.history else "") or "n/a"
    meta = [("Ticker", r.ticker), ("Exchange", r.exchange), ("Reporting currency", currency), ("Fiscal years", periods),
            ("Data source", _source(r)), ("Scan time", f"{r.scan_duration_ms:,} ms"), ("Report version", f"v{__version__}")]
    return _page(r.company, "Financial statement analysis", meta, body, _source(r))


# ----------------------------------------------------------------------------- compare
def _latest(r: ScanResult, statement: str, key: str) -> float | None:
    st = r.statements
    if st is None:
        return None
    ln = next((x for x in getattr(st, statement) if x.key == key), None)
    return ln.values[0] if ln and ln.values else None


def compare_report(c: CompareResult) -> str:
    a, b = c.result_a, c.result_b
    cur_a = (a.statements.currency if a.statements else "") or ""
    cur_b = (b.statements.currency if b.statements else "") or ""
    key_rows = []
    for label, stmt, item in (
        ("Revenue", "income", "revenue"),
        ("Operating income", "income", "operating_income"),
        ("Net income", "income", "net_income"),
        ("Total assets", "balance", "total_assets"),
        ("Shareholders' equity", "balance", "equity"),
        ("Cash from operations", "cashflow", "cfo"),
        ("Free cash flow", "cashflow", "fcf"),
    ):
        key_rows.append(
            f'<tr><td>{label}</td><td class="num">{_money(_latest(a, stmt, item), cur_a)}</td>'
            f'<td class="num">{_money(_latest(b, stmt, item), cur_b)}</td><td></td></tr>'
        )
    fy_a = _fy(a.statements.periods[0])[0] if a.statements and a.statements.periods else "n/a"
    fy_b = _fy(b.statements.periods[0])[0] if b.statements and b.statements.periods else "n/a"
    ccy_note = ""
    if cur_a and cur_b and cur_a != cur_b:
        ccy_note = f'<p class="note">The two companies report in different currencies ({cur_a} and {cur_b}); amounts are not converted, so compare ratios rather than sizes.</p>'
    key = (
        f'<p class="unit">Latest fiscal year: {a.ticker} {fy_a}, {b.ticker} {fy_b}.</p>'
        f'<table><colgroup><col style="width:40%"><col style="width:20%"><col style="width:20%"><col></colgroup><thead><tr><th>Line item</th><th class="num">{a.ticker}</th><th class="num">{b.ticker}</th><th></th></tr></thead>'
        f"<tbody>{''.join(key_rows)}</tbody></table>{ccy_note}"
    )
    sections = []
    wins = {"a": 0, "b": 0}
    for i, (title, metrics) in enumerate(SECTIONS, start=1):
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
                f'<td class="num">{format_value(vb, m.kind)}</td><td>&nbsp;&nbsp;{better}</td></tr>'
            )
        sections.append(
            _sub(f"3.{i}", title)
            + f'<table><colgroup><col style="width:40%"><col style="width:20%"><col style="width:20%"><col></colgroup><thead><tr><th>Metric</th><th class="num">{a.ticker}</th><th class="num">{b.ticker}</th><th>&nbsp;&nbsp;Stronger</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    da, db = a.dcf or {}, b.dcf or {}

    def dcf_cell(d: dict[str, Any]) -> str:
        if not d.get("assumptions"):
            return "not computed"
        ps = d.get("per_share")
        return "n/a" if ps is None else f"{d.get('currency') or ''} {ps:,.2f}".strip()

    overview = (
        f'<p class="lead"><b>{a.ticker}</b> is stronger on {wins["a"]} metrics and <b>{b.ticker}</b> on {wins["b"]}, '
        "counting only metrics where a direction is meaningful and both values exist. "
        "This is a count of screening statistics, not a recommendation.</p>"
        f'<div class="grid2"><div>{_sub("1.1", a.ticker)}<p class="note" style="color:var(--ink2)">{a.analyst_brief}</p></div>'
        f'<div>{_sub("1.2", b.ticker)}<p class="note" style="color:var(--ink2)">{b.analyst_brief}</p></div></div>'
    )
    valuation = (
        f'<table><colgroup><col style="width:40%"><col style="width:20%"><col style="width:20%"><col></colgroup><thead><tr><th>Default DCF, base case</th><th class="num">{a.ticker}</th><th class="num">{b.ticker}</th><th></th></tr></thead>'
        f'<tbody><tr><td>Value per share</td><td class="num">{dcf_cell(da)}</td><td class="num">{dcf_cell(db)}</td><td></td></tr></tbody></table>'
        '<p class="note">Same default assumptions for both (10% discount rate, growth from revenue history). Illustrative only.</p>'
    )
    notes = [f"{a.ticker}: {n}" for n in a.notes] + [f"{b.ticker}: {n}" for n in b.notes]
    body = (
        _section("1", "overview", "Overview", overview)
        + _section("2", "key", "Key financials", key)
        + _section("3", "metrics", "Metric comparison", "".join(sections), True)
        + _section("4", "dcf", "Valuation", valuation)
        + _section("5", "notes", "Notes and data sources", _notes_list(notes))
    )
    meta = [(a.ticker, a.company), (b.ticker, b.company), ("Currencies", " / ".join(x for x in (cur_a or "n/a", cur_b or "n/a")))]
    source = _source(a) if _source(a) == _source(b) else f"{_source(a)}; {_source(b)}"
    return _page(f"{a.company} vs {b.company}", "Comparison", meta, body, source)


# ----------------------------------------------------------------------------- screen
def screen_report(results: Sequence[ScanResult], criteria: str = "") -> str:
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
            f"<td>{_tag(fl, fk)}</td></tr>"
        )
    if not rows:
        table = '<p class="note">No company passed the screen, or none had enough data to be scored.</p>'
    else:
        table = (
            '<div class="scroll"><table><thead><tr><th>Ticker</th><th>Company</th><th class="num">F-score</th>'
            '<th class="num">Altman Z&Prime;</th><th class="num">Debt / equity</th>'
            '<th class="num">P/E</th><th class="num">Revenue CAGR</th><th>Health</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
    body = _section(
        "1",
        "results",
        f"Companies that passed ({len(results)})",
        table + '<p class="note">The screen covers a small built-in example universe, not the whole market.</p>',
    )
    meta = [("Companies passed", str(len(results)))] + ([("Criteria", criteria)] if criteria else [])
    return _page("Sector screen", "Screening results", meta, body, "Yahoo Finance (yfinance)")


# ----------------------------------------------------------------------------- portfolio
def portfolio_report(results: Sequence[ScanResult], requested: Sequence[str] = ()) -> str:
    """Portfolio overview for the Power BI export: one row per company, plus averages."""

    def avg(values: Sequence[float | None]) -> float | None:
        nums = [x for x in values if x is not None]
        return sum(nums) / len(nums) if nums else None

    rows = []
    for r in results:
        fl, fk = _st_f(r.health.piotroski_f)
        concern_kind = {"high": "bad", "medium": "warn", "low": "good"}.get(r.highest_concern or "", "")
        rows.append(
            f"<tr><td>{r.ticker}</td><td>{r.company}</td>"
            f'<td class="num">{_num(r.health.piotroski_f, 0)}</td><td class="num">{_num(r.health.altman_z)}</td>'
            f'<td class="num">{_num(r.health.debt_to_equity)}</td><td class="num">{_num(r.valuation.pe_ratio)}</td>'
            f'<td class="num">{_pct(r.growth.revenue_cagr_3y)}</td><td class="num">{_pct(r.quality.roe if r.quality else None)}</td>'
            f"<td>{_tag(fl, fk)}</td><td>{_tag(r.highest_concern.capitalize(), concern_kind) if concern_kind else ''}</td></tr>"
        )
    f_scores = [r.health.piotroski_f for r in results]
    averages = (
        '<tr class="avg"><td colspan="2"><b>Average of reported values</b></td>'
        f'<td class="num"><b>{_num(avg([float(x) if x is not None else None for x in f_scores]), 1)}</b></td>'
        f'<td class="num"><b>{_num(avg([r.health.altman_z for r in results]))}</b></td>'
        f'<td class="num"><b>{_num(avg([r.health.debt_to_equity for r in results]))}</b></td>'
        f'<td class="num"><b>{_num(avg([r.valuation.pe_ratio for r in results]))}</b></td>'
        f'<td class="num"><b>{_pct(avg([r.growth.revenue_cagr_3y for r in results]))}</b></td>'
        f'<td class="num"><b>{_pct(avg([r.quality.roe if r.quality else None for r in results]))}</b></td><td></td><td></td></tr>'
    )
    table = (
        '<div class="scroll"><table><thead><tr><th>Ticker</th><th>Company</th><th class="num">F-score</th>'
        '<th class="num">Altman Z&Prime;</th><th class="num">D / E</th><th class="num">P/E</th>'
        '<th class="num">Revenue CAGR</th><th class="num">ROE</th><th>Health</th><th>Concern</th></tr></thead>'
        f"<tbody>{''.join(rows)}{averages if rows else ''}</tbody></table></div>"
    )
    analysed = {r.ticker.upper() for r in results}
    missing = [t for t in requested if t.upper() not in analysed and t.upper().split(".")[0] not in analysed]
    flagged = sum(1 for r in results if r.red_flags)
    strong = sum(1 for r in results if (r.health.piotroski_f or 0) >= 7)
    summary = (
        f'<p class="lead">{len(results)} {"company" if len(results) == 1 else "companies"} analysed. '
        f'{strong} {"has" if strong == 1 else "have"} a strong Piotroski score (7 or more); '
        f"{flagged} triggered at least one red flag.</p>"
    )
    if missing:
        summary += f'<p class="note">Could not be analysed: {", ".join(missing)}.</p>'
    briefs = "".join(f"{_sub(str(i), r.ticker)}<p class=\"note\" style=\"color:var(--ink2)\">{r.analyst_brief}</p>" for i, r in enumerate(results, start=1))
    body = (
        _section("1", "summary", "Summary", summary)
        + _section("2", "holdings", "Companies", table if rows else '<p class="note">No company could be analysed.</p>')
        + (_section("3", "briefs", "Company summaries", briefs, True) if results else "")
    )
    return _page("Portfolio overview", "Portfolio report", [("Companies", str(len(results)))], body, "Yahoo Finance (yfinance)")
