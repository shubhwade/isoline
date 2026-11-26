"""Print-ready HTML reports: company scan, comparison, sector screen and portfolio.

The layout follows two kinds of real documents:

* Published financial statements (for example a US 10-K): one plain sans-serif face,
  black type, fiscal years in columns with the newest first, a unit caption such as
  "(In millions of USD, except per-share amounts)", group labels ending in a colon with
  indented line items, a currency sign on the first row and on totals, a single rule
  above subtotals and a double rule under totals, negatives in parentheses.
* Equity research reports (for example Morningstar's): a key-data block first, then
  short sections with plain headings, "Strengths" and "Concerns" lists, and a glossary.

Every number also gets a plain-English sentence so a first-time reader can follow it.

Safety and honesty rules:
* Self-contained: inline CSS and SVG only; no JavaScript, CDN, web fonts or network
  access, enforced by a Content-Security-Policy. Opens offline; prints to A4 with page numbers.
* Missing data is "n/a", never zero. Status is a word, never colour alone.
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
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#e9e9e9;color:#1a1a1a;font:13px/1.5 Arial,"Helvetica Neue",Helvetica,sans-serif;
font-variant-numeric:tabular-nums lining-nums}
.page{max-width:940px;margin:24px auto;background:#fff;padding:36px 48px 32px;box-shadow:0 1px 2px rgba(0,0,0,.15)}
a{color:inherit}
.top{display:flex;justify-content:space-between;align-items:baseline;border-top:4px solid #1a1a1a;padding-top:8px;font-size:11px;color:#555}
.top b{color:#1a1a1a}
h1{font-size:26px;line-height:1.2;margin:14px 0 4px;font-weight:700}
.ident{color:#444;font-size:12.5px;margin:0 0 16px}
table.kd{width:100%;border-collapse:collapse;border-top:1px solid #1a1a1a;border-bottom:1px solid #1a1a1a;margin:0 0 18px}
table.kd td{padding:8px 10px 8px 0;vertical-align:top;border-right:1px solid #ddd;width:16.66%}
table.kd td:last-child{border-right:0}
table.kd .k{display:block;font-size:11px;color:#555}
table.kd .v{display:block;font-size:17px;font-weight:700;margin-top:2px;white-space:nowrap}
table.kd .c{display:block;font-size:11px;color:#555}
.howto{background:#f3f3f3;padding:10px 14px;font-size:12px;color:#333;margin:0 0 6px}
.howto b{color:#1a1a1a}
h2{font-size:16px;font-weight:700;margin:28px 0 8px;padding-top:8px;border-top:2px solid #1a1a1a}
h3{font-size:13.5px;font-weight:700;margin:20px 0 2px}
p{margin:6px 0}
.cap{font-size:11.5px;color:#555;margin:0 0 6px}
.what{font-size:12px;color:#444;margin:2px 0 8px}
.bottom{font-size:14px;line-height:1.55;margin:8px 0 12px}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px}
.two h3{margin-top:4px}
ul{margin:4px 0 0 18px;padding:0}
li{margin:3px 0}
table{border-collapse:collapse;width:100%}
th,td{padding:5px 8px;text-align:left;vertical-align:top}
table.data thead th{font-size:11.5px;font-weight:700;border-bottom:1px solid #1a1a1a;vertical-align:bottom}
table.data tbody td{border-bottom:1px solid #e3e3e3}
.num{text-align:right;white-space:nowrap}
.na{color:#777}
.good{color:#1d6b3a;font-weight:700}.warn{color:#8a5a00;font-weight:700}.bad{color:#b42318;font-weight:700}.neutral{font-weight:700}
.mean{color:#333;font-size:12.5px}
table.fs{table-layout:fixed;margin-top:4px}
table.fs th{font-size:11.5px;font-weight:700;text-align:right;vertical-align:bottom;padding-bottom:4px;border-bottom:1px solid #1a1a1a}
table.fs th.lbl{text-align:left;font-weight:400;color:#555}
table.fs th .dt{font-weight:400;white-space:nowrap}
table.fs td{padding:3px 8px;border:0}
table.fs td.num{padding-left:2px}
table.fs tr.grp td{padding-top:10px}
table.fs tr.item td.l{padding-left:22px}
table.fs tr.sub td.num,table.fs tr.tot td.num{border-top:1px solid #1a1a1a}
table.fs tr.sub td.l{padding-left:36px}
table.fs tr.tot td.num{border-bottom:3px double #1a1a1a}
table.fs tr.flush td.l{padding-left:8px}
table.fs tr.norule td.num{border-top:0}
table.fs tr.tot td{padding-bottom:4px}
table.fs tr.memo td{color:#555;font-style:italic}
table.fs tr.memo td.l{padding-left:22px}
table.fs tr.gap td{padding-top:12px}
table.fs .an{color:#555;border-left:1px solid #e3e3e3}
table.fs td.cur{text-align:left;padding-right:0;width:16px;color:#1a1a1a}
.note{font-size:11.5px;color:#555;margin:6px 0 0}
.warnbox{border:1px solid #1a1a1a;padding:8px 12px;margin:10px 0;font-size:12.5px}
.chart{margin:12px 0 4px}
.chart figcaption{font-weight:700;font-size:12.5px;margin-bottom:2px}
.chart svg{width:100%;height:auto;display:block}
.chart text{font-family:Arial,Helvetica,sans-serif;fill:#333}
.chart text.lab{paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}
.chart .src{font-size:11px;color:#555}
dl.gloss{margin:6px 0 0;columns:2;column-gap:28px}
dl.gloss div{break-inside:avoid;margin:0 0 8px}
dl.gloss dt{font-weight:700}
dl.gloss dd{margin:0;color:#333}
ol.toc{margin:6px 0 0 18px;padding:0;columns:2;column-gap:28px}
.disc{margin-top:26px;padding-top:10px;border-top:1px solid #1a1a1a;color:#555;font-size:10.5px}
footer.rep{margin-top:8px;color:#555;font-size:10.5px;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
td.base{font-weight:700;text-decoration:underline}
@media (max-width:760px){.page{padding:20px 16px;margin:0}table.kd td{display:inline-block;width:50%;border-right:0;border-bottom:1px solid #ddd}
.two{grid-template-columns:minmax(0,1fr)}dl.gloss,ol.toc{columns:1}.scroll{overflow-x:auto}table.fs{min-width:620px}h1{font-size:22px}}
@page{size:A4;margin:15mm 14mm 17mm;
@bottom-left{content:"__FOOT__";font:7.5pt Arial,Helvetica,sans-serif;color:#555}
@bottom-right{content:"Page " counter(page) " of " counter(pages);font:7.5pt Arial,Helvetica,sans-serif;color:#555}}
@media print{body{background:#fff;font-size:9.5pt}.page{margin:0;box-shadow:none;max-width:none;padding:0}
section.major{break-before:page}h2,h3{break-after:avoid}tr,.chart,.two>div{break-inside:avoid}.scroll{overflow:visible}
table.kd .v{font-size:14px}h1{font-size:22px}
table.fs{font-size:8pt}table.fs th{font-size:7.5pt}table.fs td.cur{width:10px}}
"""

CURRENCY_SIGNS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥", "CNY": "¥", "CAD": "$", "AUD": "$"}


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
    """A status word. The colour only reinforces the word; it never replaces it."""
    if kind == "na":
        return '<span class="na">n/a</span>'
    return f'<span class="{kind}">{label}</span>'


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


def _date_label(period: str) -> str:
    """'Dec 31, 2024' without platform-specific strftime flags (``%-d`` fails on Windows)."""
    try:
        d = datetime.date.fromisoformat(period)
    except ValueError:
        return period
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def _fy(period: str) -> tuple[str, str]:
    try:
        year = datetime.date.fromisoformat(period).year
    except ValueError:
        return period, ""
    return f"FY{year}", _date_label(period)


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


# ----------------------------------------------------------------------------- plain-English meaning
def _x(v: float) -> str:
    return f"{v:,.2f}" if abs(v) < 10 else f"{v:,.1f}"


def _meanings(r: ScanResult) -> dict[str, str]:
    """One sentence per metric, using the company's own numbers."""
    h, g, v, q = r.health, r.growth, r.valuation, r.quality
    m: dict[str, str] = {}

    def put(key: str, value: float | None, text: str) -> None:
        m[key] = "Not available for this company (see Notes)." if value is None else text

    put("pe", v.pe_ratio, f"Buyers pay {_x(v.pe_ratio or 0)} times one year of profit for the shares. Higher means the market expects more growth.")
    put("pb", v.pb_ratio, f"The shares cost {_x(v.pb_ratio or 0)} times the company's accounting value (assets minus debts).")
    put("ev", v.ev_ebitda, f"The whole business (shares plus debt, minus cash) costs {_x(v.ev_ebitda or 0)} times one year of operating cash earnings.")
    put("de", h.debt_to_equity, f"For every 1.00 the owners have put in, the company owes {_x(h.debt_to_equity or 0)} to others.")
    put("cr", h.current_ratio, f"It has {_x(h.current_ratio or 0)} of short-term assets for every 1.00 of bills due within a year.")
    put("ic", h.interest_coverage, f"Operating profit covers the year's interest bill {_x(h.interest_coverage or 0)} times.")
    put("rev", g.revenue_cagr_3y, f"Sales grew by about {_pct(g.revenue_cagr_3y)} a year over the last three years.")
    put("pat", g.pat_cagr_3y, f"Profit grew by about {_pct(g.pat_cagr_3y)} a year over the last three years.")
    trend = g.margin_trend
    m["trend"] = (
        "Not available for this company (see Notes)." if trend is None
        else f"The share of each sale left after running costs is {trend} compared with three years ago."
    )
    put("fcfy", g.fcf_yield, f"The cash the business generates in a year equals {_pct(g.fcf_yield)} of what the whole company is worth on the market.")
    if q is not None:
        put("nm", q.net_margin, f"Out of every 100 of sales, {(q.net_margin or 0) * 100:,.1f} is left as profit.")
        put("at", q.asset_turnover, f"Each 1.00 of assets produced {_x(q.asset_turnover or 0)} of sales in the year.")
        put("em", q.equity_multiplier, f"Assets are {_x(q.equity_multiplier or 0)} times the owners' money; the rest is funded by borrowing and other liabilities.")
        put("roe", q.roe, f"The company earned {_pct(q.roe)} on the owners' money this year.")
        put("roic", q.roic, f"The company earned {_pct(q.roic)} after tax on all the capital invested in it (owners' and lenders').")
        put("fcfm", q.fcf_margin, f"Out of every 100 of sales, {(q.fcf_margin or 0) * 100:,.1f} turned into spare cash after investment.")
        put("fcfni", q.fcf_to_net_income, f"For every 1.00 of reported profit, the business produced {_x(q.fcf_to_net_income or 0)} of spare cash.")
        put("acc", q.accruals_ratio, "Negative is good: profits are backed by cash." if (q.accruals_ratio or 0) < 0 else "Positive means more of the profit is accounting entries than cash; worth checking.")
        put("ccc", q.cash_conversion_cycle_days, f"It takes about {_days(q.cash_conversion_cycle_days)} from paying suppliers to collecting cash from customers.")
        put("shares", q.share_count_change, "The number of shares grew, so each share owns a smaller slice." if (q.share_count_change or 0) > 0 else "The number of shares did not grow, so existing owners were not diluted.")
    put("f", h.piotroski_f, f"Passed {h.piotroski_f} of 9 basic tests of profitability, debt and efficiency. 7 or more is strong.")
    zone = _st_z(h.altman_z)[0].lower()
    put("z", h.altman_z, f"In the {zone}. Above 2.6 means a low chance of financial distress; below 1.1 means high.")
    put("m", r.beneish_m, "Below -2.22: no sign of earnings manipulation." if (r.beneish_m or 0) <= -2.22 else "Above -2.22: some warning signs of aggressive accounting; check the filings.")
    return m


def _strengths_concerns(r: ScanResult) -> tuple[list[str], list[str]]:
    """Rule-based lists from the computed metrics only; nothing is asserted without data."""
    h, g, q = r.health, r.growth, r.quality
    good: list[str] = []
    bad: list[str] = []
    f = h.piotroski_f
    if f is not None:
        (good if f >= 7 else bad if f <= 4 else []).append(f"Piotroski score of {f} out of 9 ({'strong' if f >= 7 else 'weak'} financial health).")
    z = h.altman_z
    if z is not None:
        if z > 2.6:
            good.append(f"Altman Z″ of {z:.2f}: low risk of financial distress.")
        else:
            bad.append(f"Altman Z″ of {z:.2f}: {'elevated' if z >= 1.1 else 'high'} risk of financial distress.")
    if g.revenue_cagr_3y is not None:
        if g.revenue_cagr_3y >= 0.05:
            good.append(f"Sales grew about {_pct(g.revenue_cagr_3y)} a year over three years.")
        elif g.revenue_cagr_3y < 0:
            bad.append(f"Sales shrank about {_pct(-g.revenue_cagr_3y)} a year over three years.")
    if g.margin_trend == "improving":
        good.append("Operating margins are improving.")
    elif g.margin_trend == "declining":
        bad.append("Operating margins are declining.")
    if q is not None:
        if q.net_margin is not None:
            if q.net_margin >= 0.10:
                good.append(f"Keeps {_pct(q.net_margin)} of sales as profit.")
            elif q.net_margin < 0:
                bad.append("The company made a loss in the latest year.")
        if q.roe is not None and q.roe >= 0.15:
            good.append(f"Earns {_pct(q.roe)} a year on the owners' money.")
        if q.fcf_margin is not None:
            if q.fcf_margin >= 0.05:
                good.append(f"Turns {_pct(q.fcf_margin)} of sales into spare cash.")
            elif q.fcf_margin < 0:
                bad.append("Spends more cash than it brings in (negative free cash flow).")
    if h.debt_to_equity is not None:
        if h.debt_to_equity < 1:
            good.append(f"Modest debt: liabilities are {h.debt_to_equity:.2f} times equity.")
        elif h.debt_to_equity > 2:
            bad.append(f"Heavy debt: liabilities are {h.debt_to_equity:.2f} times equity.")
    if h.current_ratio is not None and h.current_ratio < 1:
        bad.append(f"Short-term bills exceed short-term assets (current ratio {h.current_ratio:.2f}).")
    if h.interest_coverage is not None:
        if h.interest_coverage >= 8:
            good.append(f"Operating profit covers interest {h.interest_coverage:.1f} times.")
        elif h.interest_coverage < 3:
            bad.append(f"Operating profit covers interest only {h.interest_coverage:.1f} times.")
    if r.beneish_m is not None and r.beneish_m > -2.22:
        bad.append(f"Beneish M-score of {r.beneish_m:.2f} suggests checking the quality of reported earnings.")
    if r.valuation.pe_ratio is not None and r.valuation.pe_ratio > 40:
        bad.append(f"Expensive on earnings: the share price is {r.valuation.pe_ratio:.1f} times profit.")
    for flag in r.red_flags:
        text = f"Red flag: {flag.label}."
        if text not in bad:
            bad.append(text)
    return good, bad


# ----------------------------------------------------------------------------- building blocks
def _metric_table(rows: Sequence[tuple[str, str, tuple[str, str] | None, str]], reading: bool = True) -> str:
    if not reading:
        body = "".join(
            f'<tr><td>{label}</td><td class="num"><b>{value}</b></td><td class="mean">{meaning}</td></tr>'
            for label, value, _status, meaning in rows
        )
        return (
            '<div class="scroll"><table class="data"><colgroup><col style="width:24%"><col style="width:13%"><col></colgroup>'
            f'<thead><tr><th>Item</th><th class="num">Value</th><th>&nbsp;&nbsp;What it means</th></tr></thead><tbody>{body}</tbody></table></div>'
        )
    body = "".join(
        f'<tr><td>{label}</td><td class="num"><b>{value}</b></td><td>{_tag(*status) if status else ""}</td>'
        f'<td class="mean">{meaning}</td></tr>'
        for label, value, status, meaning in rows
    )
    return (
        '<div class="scroll"><table class="data"><colgroup><col style="width:24%"><col style="width:11%">'
        '<col style="width:13%"><col></colgroup><thead><tr><th>Measure</th><th class="num">Value</th>'
        f"<th>Reading</th><th>What it means</th></tr></thead><tbody>{body}</tbody></table></div>"
    )


def _section(num: str, anchor: str, title: str, body: str, major: bool = False) -> str:
    cls = ' class="major"' if major else ""
    return f'<section id="{anchor}"{cls}><h2>{num}. {title}</h2>{body}</section>'


def _sub(title: str) -> str:
    return f"<h3>{title}</h3>"


def _page(title: str, kind: str, ident: str, body: str, source: str) -> str:
    now = datetime.datetime.now()
    stamp = f"{now.strftime('%b')} {now.day}, {now.year}"
    foot = f"{title} · {kind}".replace('"', "'")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="{BRAND.name} {__version__}">
<title>{title} · {kind}</title><style>{CSS.replace("__FOOT__", foot)}</style></head>
<body><div class="page">
<div class="top"><span><b>{BRAND.name}</b> &nbsp;|&nbsp; {kind}</span><span>Report date {stamp}</span></div>
<h1>{title}</h1>
<p class="ident">{ident}</p>
{body}
<div class="disc">{DISCLAIMER}</div>
<footer class="rep"><span>Prepared with {BRAND.command} v{__version__} ({BRAND.site_url})</span><span>Data: {source}</span></footer>
</div></body></html>"""


def _notes_list(notes: Sequence[str]) -> str:
    if not notes:
        return '<p class="note">Every measure in this report could be calculated from the data available.</p>'
    return "<ul>" + "".join(f"<li>{n}</li>" for n in notes) + "</ul>"


def _source(r: ScanResult) -> str:
    notes = " ".join(r.notes).lower()
    return "SEC EDGAR (XBRL company facts)" if "sec edgar" in notes else "Yahoo Finance (yfinance)"


# ----------------------------------------------------------------------------- statements
STATEMENT_HELP = {
    "income": "What it shows: how much the company sold during each year, what it spent, and how much was left as profit.",
    "balance": "What it shows: what the company owns (assets) and owes (liabilities) at the end of each year. The difference belongs to the shareholders (equity).",
    "cashflow": "What it shows: actual cash coming in and going out. Profit can be positive while cash is negative, so this is where problems often show first.",
}


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
    sign: str,
    flush_subtotals: bool = False,
    base_line: StatementLine | None = None,
) -> str:
    if not lines:
        return '<p class="note">This statement was not available from the data source.</p>'
    base = base_line or next((ln for ln in lines if ln.key == base_key), None)
    n = len(periods)
    widths = f'<col style="width:{34 if base_name else 40}%">' + "".join(
        '<col style="width:16px"><col>' for _ in range(n)
    ) + ('<col style="width:9%"><col style="width:9%">' if base_name else '<col style="width:9%">')
    head = "".join(f'<th colspan="2">{_fy(p)[0]}<br><span class="dt">{_date_label(p)}</span></th>' for p in periods)
    head += '<th class="an">Change<br>vs prior</th>' + (f'<th class="an">{base_name}</th>' if base_name else "")
    rows = []
    prev_group = ""
    first_amount = True
    prev_kind = ""
    for ln in lines:
        if ln.group and ln.group != prev_group and ln.group not in ("Memo", "Free cash flow"):
            rows.append(f'<tr class="grp"><td class="l" colspan="{2 * n + 3}"><b>{ln.group}:</b></td></tr>')
            prev_kind = "grp"
        prev_group = ln.group
        shown = [None if v is None else v * ln.sign for v in ln.values]
        show_sign = (first_amount or ln.kind == "total") and not ln.per_share and ln.kind != "memo"
        cells = []
        for v in shown:
            amount = _acct(v, 1, 2) if ln.per_share else _acct(v, div, nd)
            cur = sign if show_sign and v is not None else ""
            cells.append(f'<td class="cur">{cur}</td><td class="num">{amount}</td>')
        if ln.kind != "memo" and not ln.per_share:
            first_amount = False
        yoy = _change(ln.values[0], ln.values[1], ln.key in OUTFLOW_KEYS) if len(ln.values) > 1 else "n/a"
        share = ""
        if base and not ln.per_share and ln.values[0] is not None and base.values[0]:
            share = f"{ln.values[0] / base.values[0] * 100:,.1f}%"
        cls = {"subtotal": "sub", "total": "tot", "memo": "memo"}.get(ln.kind, "item")
        if ln.kind == "subtotal" and (flush_subtotals or prev_kind in ("", "grp")):
            cls += " flush"
        if ln.kind == "subtotal" and prev_kind in ("", "grp"):
            cls += " norule"
        if ln.kind == "memo" and prev_kind != "memo":
            cls += " gap"
        prev_kind = ln.kind
        label = ln.label + (" &dagger;" if ln.computed else "")
        if ln.kind == "total":
            label = f"<b>{label}</b>"
        analysis = f'<td class="num an">{yoy}</td>' + (f'<td class="num an">{share}</td>' if base_name else "")
        rows.append(f'<tr class="{cls}"><td class="l">{label}</td>{"".join(cells)}{analysis}</tr>')
    return (
        f'<div class="scroll"><table class="fs"><colgroup>{widths}</colgroup><thead><tr><th class="lbl">Fiscal year ended</th>'
        f"{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _statements_section(r: ScanResult, num: str) -> str:
    st = r.statements
    if st is None:
        return _section(num, "statements", "Financial statements", '<p class="note">No statement data was available.</p>', True)
    div, word, nd = _statement_scale(st)
    sign = CURRENCY_SIGNS.get(st.currency, "")
    unit = f"In {word} of {st.currency}" if word and st.currency else (f"In {st.currency}" if st.currency else "In reported units")
    cap = f'<p class="cap">({unit}, except per-share amounts. Figures in parentheses are costs, outflows or losses.)</p>'
    computed = any(ln.computed for lines in (st.income, st.balance, st.cashflow) for ln in lines)
    revenue = next((ln for ln in st.income if ln.key == "revenue"), None)
    body = (
        _sub("Income statement") + cap + f'<p class="what">{STATEMENT_HELP["income"]}</p>'
        + _statement_table(st.income, st.periods, div, nd, "revenue", "% of rev.", sign, flush_subtotals=True)
        + _sub("Balance sheet") + cap + f'<p class="what">{STATEMENT_HELP["balance"]}</p>'
        + _statement_table(st.balance, st.periods, div, nd, "total_assets", "% of assets", sign)
        + _sub("Cash flow statement") + cap + f'<p class="what">{STATEMENT_HELP["cashflow"]}</p>'
        + _statement_table(
            st.cashflow, st.periods, div, nd, None, "% of rev." if revenue else "", sign,
            base_line=revenue,
        )
    )
    if st.notes:
        body += '<div class="warnbox">' + "<br>".join(st.notes) + "</div>"
    if computed:
        body += '<p class="note">&dagger; Calculated from reported lines: free cash flow = cash from operations minus capital expenditure; total liabilities and equity = total liabilities plus total equity.</p>'
    body += '<p class="note">n/a: not reported by the company or the data source for that year. Values are never estimated or set to zero.</p>'
    return _section(num, "statements", "Financial statements", body, True)


def _key_data(r: ScanResult) -> str:
    st = r.statements

    def line(lines: list[StatementLine], key: str) -> StatementLine | None:
        return next((ln for ln in lines if ln.key == key), None)

    def latest(ln: StatementLine | None, i: int = 0) -> float | None:
        return ln.values[i] if ln and len(ln.values) > i else None

    rev = ni = fcf = None
    if st is not None:
        rev, ni, fcf = line(st.income, "revenue"), line(st.income, "net_income"), line(st.cashflow, "fcf")
    cur = st.currency if st else ""
    d = r.dcf or {}
    if d.get("assumptions") and d.get("per_share") is not None:
        fair = f"{CURRENCY_SIGNS.get(d.get('currency') or '', '')}{d['per_share']:,.2f}"
        fair_c = "per share, base-case DCF"
    else:
        fair, fair_c = "n/a", "DCF not computed"
    f = r.health.piotroski_f
    z = r.health.altman_z
    cells = [
        ("Revenue", _money(latest(rev), CURRENCY_SIGNS.get(cur, "")).replace(" ", ""), f"{_change(latest(rev), latest(rev, 1))} vs prior year"),
        ("Net income", _money(latest(ni), CURRENCY_SIGNS.get(cur, "")).replace(" ", ""), f"{_change(latest(ni), latest(ni, 1))} vs prior year"),
        ("Free cash flow", _money(latest(fcf), CURRENCY_SIGNS.get(cur, "")).replace(" ", ""), f"{_change(latest(fcf), latest(fcf, 1))} vs prior year"),
        ("Financial health", "n/a" if f is None else f"{f} / 9", "Piotroski F-score" + ("" if f is None else f": {_st_f(f)[0].lower()}")),
        ("Distress risk", _num(z), "Altman Z″" + ("" if z is None else f": {_st_z(z)[0].lower()}")),
        ("Fair value estimate", fair, fair_c),
    ]
    tds = "".join(f'<td><span class="k">{k}</span><span class="v">{v}</span><span class="c">{c}</span></td>' for k, v, c in cells)
    return f'<table class="kd"><tr>{tds}</tr></table>'


HOW_TO_READ = (
    "<b>How to read this report.</b> Figures come from the company's annual reports. "
    "<b>n/a</b> means the figure was not reported, so it is never shown as zero. "
    "Amounts in <b>(parentheses)</b> are costs, outflows or losses. "
    "Each measure has a plain-English line under <b>What it means</b>, and a glossary is at the end. "
    "Nothing here is investment advice."
)

GLOSSARY = [
    ("Revenue", "Money from selling goods and services, before any costs."),
    ("Operating income (EBIT)", "Profit from the main business, before interest and tax."),
    ("Net income", "Profit left for shareholders after every cost, interest and tax."),
    ("Free cash flow", "Cash from running the business minus spending on equipment and buildings; money the company could pay out or save."),
    ("Assets, liabilities, equity", "What the company owns, what it owes, and the difference, which belongs to shareholders."),
    ("Fiscal year (FY)", "The company's 12-month accounting year; it does not always end in December."),
    ("Piotroski F-score", "Nine yes/no tests of profitability, debt and efficiency (Piotroski, 2000). 7 to 9 is strong, 0 to 4 weak."),
    ("Altman Z″-score", "A formula that estimates the risk of financial distress from the balance sheet (Altman, 1983/1995)."),
    ("Beneish M-score", "A screen for signs of earnings manipulation (Beneish, 1999). Above -2.22 deserves a closer look."),
    ("Return on equity (ROE)", "Profit as a percentage of the shareholders' money in the business."),
    ("P/E ratio", "Share price divided by profit per share: how many years of current profit the price represents."),
    ("Discounted cash flow (DCF)", "An estimate of what a business is worth today, from the cash it is expected to produce in future years."),
]


def _glossary() -> str:
    items = "".join(f"<div><dt>{t}</dt><dd>{d}</dd></div>" for t, d in GLOSSARY)
    return f'<dl class="gloss">{items}</dl>'


# ----------------------------------------------------------------------------- charts (inline SVG)
PALETTE = ["#1a1a1a", "#8c8c8c", "#c8c8c8"]
LINE_COLOR = "#1a1a1a"


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
    """Grouped bar chart (+ optional dashed line on a right-hand % axis) as inline SVG."""
    all_vals = [v for _, vals in bars for v in vals]
    if not any(v is not None for v in all_vals) or not years:
        return ""
    div, unit_word = _scale(all_vals)
    unit = (f"{currency} {unit_word}" if currency else unit_word).strip()
    scaled = [(n, [None if v is None else v / div for v in vals]) for n, vals in bars]
    flat = [v for _, vals in scaled for v in vals if v is not None]
    nd = 0 if max(abs(v) for v in flat) >= 100 else 1
    lo, hi = min(0.0, min(flat)), max(0.0, max(flat))
    ticks = _ticks(lo, hi)
    lo, hi = ticks[0], ticks[-1]

    W, H = 760, 290
    ml, mr, mt, mb = 58, 58 if line else 18, 26, 56
    pw, ph = W - ml - mr, H - mt - mb
    n = len(years)

    def y(v: float) -> float:
        return mt + ph * (1 - (v - lo) / (hi - lo))

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{title}">']
    for t in ticks:
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e3e3e3" stroke-width="1"/>')
        out.append(f'<text x="{ml - 8}" y="{y(t) + 4:.1f}" font-size="11" text-anchor="end">{t:,g}</text>')
    out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#1a1a1a" stroke-width="1"/>')
    if unit:
        out.append(f'<text x="{ml}" y="12" font-size="11" text-anchor="start" style="fill:#555">{unit}</text>')
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
        out.append(f'<text x="{ml + group * (i + 0.5):.1f}" y="{H - mb + 17}" font-size="11.5" text-anchor="middle">{year}</text>')
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
                out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{LINE_COLOR}" stroke-width="1.6" stroke-dasharray="5 3"/>')
            for x, yy, v in pts:
                out.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="3.2" fill="#fff" stroke="{LINE_COLOR}" stroke-width="1.6"/>')
                out.append(f'<text class="lab" x="{x + 6:.1f}" y="{yy - 8:.1f}" font-size="10" text-anchor="start">{v * 100:.1f}%</text>')
    lx, lyy = ml, H - 12
    for j, (name, _) in enumerate(scaled):
        out.append(f'<rect x="{lx}" y="{lyy - 9}" width="10" height="10" fill="{PALETTE[j % 3]}"/>')
        out.append(f'<text x="{lx + 15}" y="{lyy}" font-size="11.5">{name}</text>')
        lx += 15 + 7 * len(name) + 22
    if line:
        out.append(f'<line x1="{lx}" x2="{lx + 18}" y1="{lyy - 4}" y2="{lyy - 4}" stroke="{LINE_COLOR}" stroke-width="1.6" stroke-dasharray="5 3"/>')
        out.append(f'<text x="{lx + 24}" y="{lyy}" font-size="11.5">{line[0]} (right axis)</text>')
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
        "Sales, profit and operating margin",
        hst.years,
        [("Revenue", hst.revenue), ("Net income", hst.net_income)],
        hst.currency,
        line=("Operating margin", hst.operating_margin),
    )
    c2 = _chart(
        "Is profit turning into cash?",
        hst.years,
        [("Net income", hst.net_income), ("Operating cash flow", hst.operating_cash_flow), ("Free cash flow", hst.free_cash_flow)],
        hst.currency,
    )
    return c1 + c2


# ----------------------------------------------------------------------------- scan
SIGNALS = [
    ("ROA Positive", "Profitability", "The company made a profit relative to its assets"),
    ("CFO Positive", "Profitability", "Day-to-day operations brought in cash"),
    ("ROA Improving", "Profitability", "Profit relative to assets is higher than last year"),
    ("Low Accruals", "Profitability", "Cash from operations is larger than reported profit"),
    ("Leverage Falling", "Debt and liquidity", "Long-term debt is lower relative to assets than last year"),
    ("Liquidity Rising", "Debt and liquidity", "Short-term assets cover short-term bills better than last year"),
    ("No Dilution", "Debt and liquidity", "No new shares were issued"),
    ("Gross Margin Rising", "Efficiency", "Profit on each sale, before overheads, is higher than last year"),
    ("Asset Turnover Rising", "Efficiency", "Each unit of assets produced more sales than last year"),
]


def _dcf_section(r: ScanResult, num: str) -> str:
    title = "What could the business be worth? (discounted cash flow)"
    intro = ('<p class="what">A discounted cash flow (DCF) estimates the value of a business today from the cash it might '
             "produce in future years. It depends entirely on the assumptions, so it is a range of possibilities, not a price target.</p>")
    d = r.dcf
    if not d:
        return _section(num, "dcf", title, intro + '<p class="note">The DCF could not be run for this company.</p>', True)
    a = d.get("assumptions")
    notes = d.get("notes") or []
    if not a:
        why = " ".join(notes) or "Inputs were missing."
        body = intro + f'<div class="warnbox">Not calculated. {why}</div><p class="note">You can supply your own assumption, for example <code>isoline value {r.ticker} --growth 0.05</code>.</p>'
        return _section(num, "dcf", title, body, True)
    cur = d.get("currency") or ""
    sign = CURRENCY_SIGNS.get(cur, "")
    unit = (d.get("sensitivity") or {}).get("unit", "per share")
    per_share = unit == "per share"

    def val(eq: float | None, ps: float | None) -> str:
        if per_share:
            return "n/a" if ps is None else f"{sign}{ps:,.2f}" if sign else f"{cur} {ps:,.2f}"
        return _money(eq, cur)

    assumptions = _metric_table(
        [
            ("Starting free cash flow", _money(a.get("base_fcf"), cur), None, f"Average of recent years ({a.get('base_fcf_note', '')})."),
            ("Growth in year 1", _pct(a.get("growth")), None, f"Based on {a.get('growth_source', 'history')}; it slows each year to the long-run rate."),
            ("Discount rate", _pct(a.get("discount_rate")), None, "The yearly return an investor demands. A standard assumption, not specific to this company."),
            ("Long-run growth", _pct(a.get("terminal_growth")), None, "Growth assumed forever after the forecast years."),
            ("Forecast years", f"{a.get('years', 'n/a')}", None, "Years forecast one by one before the long-run assumption takes over."),
            ("Share from long run", _pct(d.get("terminal_share")), None, "How much of the value comes from the years after the forecast; higher means more uncertainty."),
        ],
        reading=False,
    )
    scen_rows = "".join(
        f'<tr><td>{s.get("name")}</td><td class="num">{_pct(s.get("discount_rate"))}</td><td class="num">{_pct(s.get("growth"))}</td>'
        f'<td class="num"><b>{val(s.get("equity_value"), s.get("per_share"))}</b></td></tr>'
        for s in d.get("scenarios") or []
    )
    scenarios = (
        '<table class="data"><thead><tr><th>Case</th><th class="num">Discount rate</th><th class="num">Growth</th>'
        f'<th class="num">Value {"per share" if per_share else ""}</th></tr></thead><tbody>{scen_rows}</tbody></table>'
        '<p class="note">Bear: slower growth and a higher discount rate. Bull: faster growth and a lower discount rate.</p>'
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
            _sub("How the value changes with the assumptions")
            + f'<p class="cap">Value {unit} ({cur}). Rows: long-run growth. Columns: discount rate. The base case is underlined.</p>'
            + f'<div class="scroll"><table class="data"><thead><tr><th>Long-run growth</th>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
        )
    headline = val(d.get("equity_value"), d.get("per_share"))
    price_line = ""
    if d.get("price") is not None:
        price_line = f" The share price was {sign or cur + ' '}{d['price']:,.2f}, a margin of safety of {_pct(d.get('margin_of_safety'))}."
    body = (
        intro
        + f'<p class="bottom">Base-case value: <b>{headline}</b>{" per share" if per_share and headline != "n/a" else ""}.{price_line}</p>'
        + _sub("Assumptions") + assumptions
        + _sub("Three cases") + scenarios
        + sens_html
        + (_notes_list(notes) if notes else "")
    )
    return _section(num, "dcf", title, body, True)


def scan_report(r: ScanResult) -> str:
    h, g, v, q = r.health, r.growth, r.valuation, r.quality
    mean = _meanings(r)
    good, bad = _strengths_concerns(r)
    trend = g.margin_trend

    def lst(items: list[str], empty: str) -> str:
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else f'<p class="note">{empty}</p>'

    summary = (
        f'<p class="bottom">{r.analyst_brief}</p>'
        '<div class="two">'
        f'<div><h3>Strengths</h3>{lst(good, "No clear strengths could be established from the available data.")}</div>'
        f'<div><h3>Concerns</h3>{lst(bad, "No concerns were triggered by the checks that could be run.")}</div>'
        "</div>"
    )
    ratios = (
        _sub("Valuation: what the market is paying")
        + _metric_table(
            [
                ("P/E ratio", _num(v.pe_ratio), None, mean["pe"]),
                ("P/B ratio", _num(v.pb_ratio), None, mean["pb"]),
                ("EV / EBITDA", _num(v.ev_ebitda), None, mean["ev"]),
            ]
        )
        + _sub("Financial health: can it pay its bills?")
        + _metric_table(
            [
                ("Debt to equity", _num(h.debt_to_equity), _st_de(h.debt_to_equity), mean["de"]),
                ("Current ratio", _num(h.current_ratio), _st_cr(h.current_ratio), mean["cr"]),
                ("Interest coverage", _num(h.interest_coverage), _st_ic(h.interest_coverage), mean["ic"]),
            ]
        )
        + _sub("Growth: is it getting bigger?")
        + _metric_table(
            [
                ("Revenue growth, 3-year average", _pct(g.revenue_cagr_3y), _st_growth(g.revenue_cagr_3y), mean["rev"]),
                ("Profit growth, 3-year average", _pct(g.pat_cagr_3y), _st_growth(g.pat_cagr_3y), mean["pat"]),
                ("Operating margin trend", trend.capitalize() if trend else "n/a",
                 None if trend is None else (trend.capitalize(), "good" if trend == "improving" else "warn" if trend == "stable" else "bad"), mean["trend"]),
                ("Free cash flow yield", _pct(g.fcf_yield), _st_sign(g.fcf_yield), mean["fcfy"]),
            ]
        )
    )
    if q is not None:
        ratios += _sub("Profitability and cash: how good is the business?") + _metric_table(
            [
                ("Net profit margin", _pct(q.net_margin), _st_sign(q.net_margin), mean["nm"]),
                ("Return on equity", _pct(q.roe), _st_sign(q.roe), mean["roe"]),
                ("Return on invested capital", _pct(q.roic), _st_sign(q.roic), mean["roic"]),
                ("Asset turnover", _num(q.asset_turnover), None, mean["at"]),
                ("Equity multiplier", _num(q.equity_multiplier), None, mean["em"]),
                ("Free cash flow margin", _pct(q.fcf_margin), _st_sign(q.fcf_margin), mean["fcfm"]),
                ("Free cash flow to profit", _num(q.fcf_to_net_income), None, mean["fcfni"]),
                ("Accruals ratio", _pct(q.accruals_ratio), None, mean["acc"]),
                ("Cash conversion cycle", _days(q.cash_conversion_cycle_days), None, mean["ccc"]),
                ("Change in share count", _pct(q.share_count_change), None, mean["shares"]),
            ]
        )

    signals = h.piotroski_signals or {}
    sig_rows = []
    for name, group, what in SIGNALS:
        got = signals.get(name)
        status = ("n/a", "na") if got is None else ("Pass", "good") if got else ("Fail", "bad")
        sig_rows.append(f'<tr><td>{what}</td><td>{group}</td><td>{_tag(*status)}</td></tr>')
    tested = sum(1 for n, _, _ in SIGNALS if signals.get(n) is not None)
    score_line = f"Score withheld: only {tested} of 9 tests could be run." if h.piotroski_f is None else f"Score: {h.piotroski_f} of 9. One point for each test passed; 7 or more is strong."
    models = (
        _sub("Piotroski F-score: nine health tests")
        + f'<p class="what">{score_line}</p>'
        + '<div class="scroll"><table class="data"><thead><tr><th>Test</th><th>Area</th><th>Result</th></tr></thead><tbody>'
        + "".join(sig_rows) + "</tbody></table></div>"
        + _sub("Distress and accounting checks")
        + _metric_table(
            [
                ("Altman Z″-score", _num(h.altman_z), _st_z(h.altman_z), mean["z"]),
                ("Beneish M-score", _num(r.beneish_m), _st_m(r.beneish_m), mean["m"]),
            ]
        )
        + _sub("Red flags")
    )
    if r.red_flags:
        flag_rows = "".join(
            f"<tr><td>{f.label[:1].upper() + f.label[1:]}</td><td class=\"num\">{_num(f.value) if isinstance(f.value, (int, float)) else f.value}</td>"
            f"<td>{_tag(f.severity.capitalize(), 'bad' if f.severity == 'high' else 'warn')}</td></tr>"
            for f in r.red_flags
        )
        models += f'<table class="data"><thead><tr><th>Flag</th><th class="num">Value</th><th>Severity</th></tr></thead><tbody>{flag_rows}</tbody></table>'
    else:
        models += '<p class="note">No red flags were triggered by the checks that could be run.</p>'

    charts = _charts(r)
    sections = [("summary", "Summary"), ("statements", "Financial statements"), ("ratios", "Key measures explained"),
                ("models", "Health scores and red flags"), ("dcf", "What could the business be worth?")]
    if charts:
        sections.append(("trends", "Trends over time"))
    sections += [("notes", "Notes and sources"), ("glossary", "Glossary")]
    toc = '<ol class="toc">' + "".join(f'<li><a href="#{a}">{t}</a></li>' for a, t in sections) + "</ol>"
    nums = {a: str(i) for i, (a, _) in enumerate(sections, start=1)}

    body = (
        _key_data(r)
        + f'<div class="howto">{HOW_TO_READ}</div>'
        + _section(nums["summary"], "summary", "Summary", summary + _sub("Contents") + toc)
        + _statements_section(r, nums["statements"])
        + _section(nums["ratios"], "ratios", "Key measures explained", ratios, True)
        + _section(nums["models"], "models", "Health scores and red flags", models, True)
        + _dcf_section(r, nums["dcf"])
        + (_section(nums["trends"], "trends", "Trends over time", charts) if charts else "")
        + _section(
            nums["notes"], "notes", "Notes and sources",
            _sub("Why some figures are n/a") + _notes_list(r.notes)
            + _sub("Method")
            + '<p class="note">Measures use the latest fiscal year unless stated; averages use the latest two balance sheets. '
            "Scores follow their published definitions and are withheld when any input is missing. "
            f"Full formulas: {BRAND.docs_url}methodology/</p>",
        )
        + _section(nums["glossary"], "glossary", "Glossary", _glossary())
    )
    st = r.statements
    periods = f"{_fy(st.periods[-1])[0]} to {_fy(st.periods[0])[0]}" if st and st.periods else "n/a"
    currency = (st.currency if st else "") or (r.history.currency if r.history else "") or "n/a"
    ident = (f"<b>{r.ticker}</b> &nbsp;·&nbsp; Exchange: {r.exchange} &nbsp;·&nbsp; Reporting currency: {currency} "
             f"&nbsp;·&nbsp; Fiscal years: {periods} &nbsp;·&nbsp; Source: {_source(r)}")
    return _page(r.company, "Financial statement analysis", ident, body, _source(r))


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
    cols = '<colgroup><col style="width:40%"><col style="width:20%"><col style="width:20%"><col></colgroup>'
    key_rows = "".join(
        f'<tr><td>{label}</td><td class="num">{_money(_latest(a, stmt, item), cur_a)}</td>'
        f'<td class="num">{_money(_latest(b, stmt, item), cur_b)}</td><td></td></tr>'
        for label, stmt, item in (
            ("Revenue", "income", "revenue"),
            ("Operating income", "income", "operating_income"),
            ("Net income", "income", "net_income"),
            ("Total assets", "balance", "total_assets"),
            ("Shareholders' equity", "balance", "equity"),
            ("Cash from operations", "cashflow", "cfo"),
            ("Free cash flow", "cashflow", "fcf"),
        )
    )
    fy_a = _fy(a.statements.periods[0])[0] if a.statements and a.statements.periods else "n/a"
    fy_b = _fy(b.statements.periods[0])[0] if b.statements and b.statements.periods else "n/a"
    ccy_note = ""
    if cur_a and cur_b and cur_a != cur_b:
        ccy_note = f'<p class="note">The companies report in different currencies ({cur_a} and {cur_b}). Amounts are not converted, so compare the ratios below rather than the sizes.</p>'
    key = (
        f'<p class="cap">Latest fiscal year: {a.ticker} {fy_a}, {b.ticker} {fy_b}.</p>'
        f'<table class="data">{cols}<thead><tr><th>Line item</th><th class="num">{a.ticker}</th><th class="num">{b.ticker}</th><th></th></tr></thead>'
        f"<tbody>{key_rows}</tbody></table>{ccy_note}"
    )
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
                better = f'<span class="good">{a.ticker if win == "a" else b.ticker}</span>'
            rows.append(
                f'<tr><td>{m.label}</td><td class="num">{format_value(va, m.kind)}</td>'
                f'<td class="num">{format_value(vb, m.kind)}</td><td>&nbsp;&nbsp;{better}</td></tr>'
            )
        sections.append(
            _sub(title)
            + f'<table class="data">{cols}<thead><tr><th>Measure</th><th class="num">{a.ticker}</th><th class="num">{b.ticker}</th><th>&nbsp;&nbsp;Stronger</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    da, db = a.dcf or {}, b.dcf or {}

    def dcf_cell(d: dict[str, Any]) -> str:
        if not d.get("assumptions"):
            return "not calculated"
        ps = d.get("per_share")
        return "n/a" if ps is None else f"{d.get('currency') or ''} {ps:,.2f}".strip()

    ga, ba = _strengths_concerns(a)
    gb, bb = _strengths_concerns(b)

    def lst(items: list[str]) -> str:
        return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else '<p class="note">None from the available data.</p>'

    overview = (
        f'<p class="bottom"><b>{a.ticker}</b> is stronger on {wins["a"]} measures and <b>{b.ticker}</b> on {wins["b"]}, '
        "counting only measures where higher or lower is clearly better and both values exist. "
        "This is a count of statistics, not a recommendation.</p>"
        f'<div class="two"><div><h3>{a.ticker}: strengths</h3>{lst(ga)}<h3>{a.ticker}: concerns</h3>{lst(ba)}</div>'
        f'<div><h3>{b.ticker}: strengths</h3>{lst(gb)}<h3>{b.ticker}: concerns</h3>{lst(bb)}</div></div>'
    )
    valuation = (
        f'<table class="data">{cols}<thead><tr><th>Discounted cash flow, base case</th><th class="num">{a.ticker}</th><th class="num">{b.ticker}</th><th></th></tr></thead>'
        f'<tbody><tr><td>Value per share</td><td class="num">{dcf_cell(da)}</td><td class="num">{dcf_cell(db)}</td><td></td></tr></tbody></table>'
        '<p class="note">The same standard assumptions are used for both (10% discount rate, growth from sales history). Illustrative only.</p>'
    )
    notes = [f"{a.ticker}: {n}" for n in a.notes] + [f"{b.ticker}: {n}" for n in b.notes]
    body = (
        f'<div class="howto">{HOW_TO_READ}</div>'
        + _section("1", "overview", "Summary", overview)
        + _section("2", "key", "Size and cash: latest year", key)
        + _section("3", "metrics", "Measure by measure", "".join(sections), True)
        + _section("4", "dcf", "What could each business be worth?", valuation)
        + _section("5", "notes", "Notes and sources", _notes_list(notes))
        + _section("6", "glossary", "Glossary", _glossary())
    )
    ident = f"<b>{a.ticker}</b>: {a.company} &nbsp;·&nbsp; <b>{b.ticker}</b>: {b.company} &nbsp;·&nbsp; Currencies: {cur_a or 'n/a'} / {cur_b or 'n/a'}"
    source = _source(a) if _source(a) == _source(b) else f"{_source(a)}; {_source(b)}"
    return _page(f"{a.company} vs {b.company}", "Comparison", ident, body, source)


# ----------------------------------------------------------------------------- screen
def _list_table(results: Sequence[ScanResult], extra: bool = False) -> str:
    rows = []
    for r in results:
        fl, fk = _st_f(r.health.piotroski_f)
        roe = f'<td class="num">{_pct(r.quality.roe if r.quality else None)}</td>' if extra else ""
        concern = ""
        if extra:
            kind = {"high": "bad", "medium": "warn", "low": "good"}.get(r.highest_concern or "", "")
            concern = f"<td>{_tag(r.highest_concern.capitalize(), kind) if kind else ''}</td>"
        rows.append(
            f"<tr><td><b>{r.ticker}</b></td><td>{r.company}</td>"
            f'<td class="num">{_num(r.health.piotroski_f, 0)}</td><td class="num">{_num(r.health.altman_z)}</td>'
            f'<td class="num">{_num(r.health.debt_to_equity)}</td><td class="num">{_num(r.valuation.pe_ratio)}</td>'
            f'<td class="num">{_pct(r.growth.revenue_cagr_3y)}</td>{roe}<td>{_tag(fl, fk)}</td>{concern}</tr>'
        )
    return "".join(rows)


def screen_report(results: Sequence[ScanResult], criteria: str = "") -> str:
    head = ('<thead><tr><th>Ticker</th><th>Company</th><th class="num">F-score</th><th class="num">Altman Z″</th>'
            '<th class="num">Debt / equity</th><th class="num">P/E</th><th class="num">Revenue growth</th><th>Health</th></tr></thead>')
    if results:
        table = f'<div class="scroll"><table class="data">{head}<tbody>{_list_table(results)}</tbody></table></div>'
    else:
        table = '<p class="note">No company passed the screen, or none had enough data to be scored.</p>'
    explain = ('<p class="what">A screen keeps only the companies that meet every rule below. '
               "F-score: nine health tests (7 or more is strong). Debt / equity: what the company owes for every 1.00 the owners put in.</p>")
    body = (
        _section("1", "results", f"Companies that passed ({len(results)})",
                 explain + (f'<p class="cap">Rules: {criteria}.</p>' if criteria else "") + table
                 + '<p class="note">The screen covers a small built-in example list of companies, not the whole market.</p>')
        + _section("2", "glossary", "Glossary", _glossary())
    )
    return _page("Sector screen", "Screening results", f"{len(results)} companies passed" + (f" &nbsp;·&nbsp; {criteria}" if criteria else ""), body, "Yahoo Finance (yfinance)")


# ----------------------------------------------------------------------------- portfolio
def portfolio_report(results: Sequence[ScanResult], requested: Sequence[str] = ()) -> str:
    """Portfolio overview for the Power BI export: one row per company, plus averages."""

    def avg(values: Sequence[float | None]) -> float | None:
        nums = [x for x in values if x is not None]
        return sum(nums) / len(nums) if nums else None

    averages = (
        '<tr><td colspan="2"><b>Average of reported values</b></td>'
        f'<td class="num"><b>{_num(avg([float(r.health.piotroski_f) if r.health.piotroski_f is not None else None for r in results]), 1)}</b></td>'
        f'<td class="num"><b>{_num(avg([r.health.altman_z for r in results]))}</b></td>'
        f'<td class="num"><b>{_num(avg([r.health.debt_to_equity for r in results]))}</b></td>'
        f'<td class="num"><b>{_num(avg([r.valuation.pe_ratio for r in results]))}</b></td>'
        f'<td class="num"><b>{_pct(avg([r.growth.revenue_cagr_3y for r in results]))}</b></td>'
        f'<td class="num"><b>{_pct(avg([r.quality.roe if r.quality else None for r in results]))}</b></td><td></td><td></td></tr>'
    )
    head = ('<thead><tr><th>Ticker</th><th>Company</th><th class="num">F-score</th><th class="num">Altman Z″</th>'
            '<th class="num">D / E</th><th class="num">P/E</th><th class="num">Revenue growth</th><th class="num">ROE</th>'
            "<th>Health</th><th>Concern</th></tr></thead>")
    table = f'<div class="scroll"><table class="data">{head}<tbody>{_list_table(results, extra=True)}{averages if results else ""}</tbody></table></div>'
    analysed = {r.ticker.upper() for r in results}
    missing = [t for t in requested if t.upper() not in analysed and t.upper().split(".")[0] not in analysed]
    flagged = sum(1 for r in results if r.red_flags)
    strong = sum(1 for r in results if (r.health.piotroski_f or 0) >= 7)
    summary = (
        f'<p class="bottom">{len(results)} {"company" if len(results) == 1 else "companies"} analysed. '
        f'{strong} {"has" if strong == 1 else "have"} a strong Piotroski score (7 or more out of 9); '
        f"{flagged} triggered at least one red flag.</p>"
    )
    if missing:
        summary += f'<p class="note">Could not be analysed: {", ".join(missing)}.</p>'
    cards = ""
    for r in results:
        good, bad = _strengths_concerns(r)
        cards += (
            f"<h3>{r.ticker}: {r.company}</h3><p>{r.analyst_brief}</p>"
            f'<div class="two"><div><b>Strengths</b><ul>{"".join(f"<li>{g}</li>" for g in good) or "<li>None from the available data.</li>"}</ul></div>'
            f'<div><b>Concerns</b><ul>{"".join(f"<li>{b}</li>" for b in bad) or "<li>None triggered.</li>"}</ul></div></div>'
        )
    body = (
        f'<div class="howto">{HOW_TO_READ}</div>'
        + _section("1", "summary", "Summary", summary)
        + _section("2", "holdings", "Companies", table if results else '<p class="note">No company could be analysed.</p>')
        + (_section("3", "briefs", "Company by company", cards, True) if results else "")
        + _section("4", "glossary", "Glossary", _glossary())
    )
    return _page("Portfolio overview", "Portfolio report", f"{len(results)} companies", body, "Yahoo Finance (yfinance)")
