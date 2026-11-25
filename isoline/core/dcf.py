"""Discounted cash flow valuation (free cash flow to equity), with scenarios and sensitivity.

Method (see docs/valuation.md for sources):

* Cash flow discounted: free cash flow = operating cash flow - |capital expenditure|. It is
  measured after interest, so it approximates free cash flow to equity and is discounted at a
  cost of equity. The result is an equity value; net debt is NOT subtracted again.
* Base cash flow: mean of up to the last three reported years (smooths one-off swings).
* Growth: ``growth`` in year 1, fading linearly to ``terminal_growth`` in the last explicit year.
* Terminal value (Gordon growth): FCF_N x (1 + g) / (r - g), discounted N years. Requires r > g.
  Stable growth should not exceed the growth of the economy; the risk-free rate is a common cap
  (Damodaran), so a terminal growth above 4% is flagged.

Every input is an explicit assumption supplied by the user or labelled as a default. The result is an
illustrative, assumption-driven estimate, never a price target or recommendation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from isoline.core.labels import at, series, to_float

DEFAULT_DISCOUNT = 0.10
DEFAULT_TERMINAL = 0.025
DEFAULT_YEARS = 5
MAX_DEFAULT_GROWTH = 0.15


@dataclass
class Assumptions:
    discount_rate: float
    growth: float
    terminal_growth: float
    years: int
    base_fcf: float
    base_fcf_note: str
    growth_source: str


@dataclass
class Scenario:
    name: str
    discount_rate: float
    growth: float
    equity_value: float | None
    per_share: float | None


@dataclass
class DCFResult:
    ticker: str
    currency: str | None
    assumptions: Assumptions | None
    equity_value: float | None = None
    per_share: float | None = None
    price: float | None = None
    margin_of_safety: float | None = None
    terminal_share: float | None = None  # share of value that comes from the terminal value
    scenarios: list[Scenario] = field(default_factory=list)
    sensitivity: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project(base_fcf: float, growth: float, terminal: float, years: int) -> list[float]:
    """Explicit-period cash flows with growth fading linearly from ``growth`` to ``terminal``."""
    flows: list[float] = []
    fcf = base_fcf
    for t in range(1, years + 1):
        g = growth if years == 1 else growth + (terminal - growth) * (t - 1) / (years - 1)
        fcf = fcf * (1 + g)
        flows.append(fcf)
    return flows


def value(base_fcf: float, discount: float, growth: float, terminal: float, years: int) -> tuple[float, float]:
    """Return (equity value, share of that value from the terminal value)."""
    if discount <= terminal:
        raise ValueError("discount rate must be greater than terminal growth")
    flows = project(base_fcf, growth, terminal, years)
    pv = sum(cf / (1 + discount) ** t for t, cf in enumerate(flows, start=1))
    tv = flows[-1] * (1 + terminal) / (discount - terminal)
    pv_tv = tv / (1 + discount) ** years
    total = pv + pv_tv
    return total, pv_tv / total if total else 0.0


def _per_share(equity: float | None, shares: float | None) -> float | None:
    return None if equity is None or not shares else equity / shares


def _safe_value(*args: Any) -> tuple[float | None, float | None]:
    try:
        v, share = value(*args)
        return v, share
    except ValueError:
        return None, None


def base_free_cash_flow(fin: dict[str, Any]) -> tuple[float | None, str]:
    cfo = series(fin.get("cashflow"), "cfo")
    capex = series(fin.get("cashflow"), "capex")
    if not cfo or not capex:
        return None, "operating cash flow or capital expenditure not reported"
    flows = []
    for i in range(min(3, len(cfo), len(capex))):
        c, x = cfo[i], capex[i]
        if c is not None and x is not None:
            flows.append(c - abs(x))
    if not flows:
        return None, "no year has both operating cash flow and capital expenditure"
    return sum(flows) / len(flows), f"mean of the last {len(flows)} reported year(s)"


def default_growth(fin: dict[str, Any]) -> float | None:
    rev = series(fin.get("income_stmt"), "revenue")
    if not rev or len(rev) < 4 or rev[0] is None or rev[3] is None or rev[3] <= 0 or rev[0] <= 0:
        return None
    cagr = (rev[0] / rev[3]) ** (1 / 3) - 1
    return max(0.0, min(cagr, MAX_DEFAULT_GROWTH))


def run_dcf(
    fin: dict[str, Any],
    ticker: str,
    discount: float | None = None,
    growth: float | None = None,
    terminal: float | None = None,
    years: int = DEFAULT_YEARS,
) -> DCFResult:
    info = fin.get("info") or {}
    currency = info.get("financialCurrency") or info.get("currency")
    res = DCFResult(ticker=ticker, currency=currency, assumptions=None)
    if years < 1 or years > 15:
        res.notes.append("Explicit period must be between 1 and 15 years.")
        return res
    base, base_note = base_free_cash_flow(fin)
    if base is None:
        res.notes.append(f"DCF not computed: {base_note}.")
        return res
    if base <= 0:
        res.notes.append(
            "DCF not computed: average free cash flow is not positive, so a perpetuity of it "
            "has no meaningful value. Use comparables or a normalised cash flow instead."
        )
        return res
    r = DEFAULT_DISCOUNT if discount is None else discount
    tg = DEFAULT_TERMINAL if terminal is None else terminal
    if growth is not None:
        g, g_src = growth, "user input"
    else:
        dg = default_growth(fin)
        if dg is None:
            res.notes.append("DCF not computed: revenue history too short to derive growth; pass --growth.")
            return res
        g, g_src = dg, f"3-year revenue CAGR, limited to 0-{MAX_DEFAULT_GROWTH:.0%}"
    if r <= tg:
        res.notes.append("DCF not computed: the discount rate must exceed terminal growth.")
        return res
    res.assumptions = Assumptions(r, g, tg, years, base, base_note, g_src)
    if discount is None:
        res.notes.append(f"Discount rate {r:.1%} is a default assumption, not an estimate of this company's cost of equity; set --discount.")
    if tg > 0.04:
        res.notes.append("Terminal growth above 4% usually exceeds long-run nominal economic growth.")
    shares = to_float(info.get("sharesOutstanding")) or at(series(fin.get("balance_sheet"), "shares"))
    equity, term_share = _safe_value(base, r, g, tg, years)
    res.equity_value, res.terminal_share = equity, term_share
    res.per_share = _per_share(equity, shares)
    if shares is None:
        res.notes.append("Share count unavailable, so no per-share value.")
    if term_share is not None and term_share > 0.75:
        res.notes.append(f"{term_share:.0%} of the value comes from the terminal value; the estimate is sensitive to long-run assumptions.")

    price = to_float(info.get("currentPrice")) or to_float(info.get("regularMarketPrice"))
    price_ccy, fin_ccy = info.get("currency"), info.get("financialCurrency")
    if price is None:
        res.notes.append("No market price available (for example from the SEC fallback), so no margin of safety.")
    elif price_ccy and fin_ccy and price_ccy != fin_ccy:
        res.notes.append(f"Price currency ({price_ccy}) differs from reporting currency ({fin_ccy}); margin of safety not computed.")
    elif res.per_share and res.per_share > 0:
        res.price = price
        res.margin_of_safety = (res.per_share - price) / res.per_share

    for name, dg, dd in (("Bear", 0.5, 0.01), ("Base", 1.0, 0.0), ("Bull", 1.25, -0.01)):
        sg, sr = g * dg, r + dd
        eq, _ = _safe_value(base, sr, sg, tg, years)
        res.scenarios.append(Scenario(name, sr, sg, eq, _per_share(eq, shares)))
    rates = [r + d for d in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    tgs = [tg + d for d in (-0.01, 0.0, 0.01)]
    grid = []
    for t_ in tgs:
        grid.append([_per_share(_safe_value(base, rr, g, t_, years)[0], shares) if shares else _safe_value(base, rr, g, t_, years)[0] for rr in rates])
    res.sensitivity = {"discount_rates": rates, "terminal_growths": tgs, "values": grid, "unit": "per share" if shares else "equity value"}
    return res
