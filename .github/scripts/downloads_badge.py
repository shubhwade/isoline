"""Write a shields.io endpoint JSON: all-time downloads of isoline + legacy telmus, as one number.

Both counts come from pepy.tech, which keeps each project's full history (the downloads
`telmus` gathered before the rename stay counted under `telmus`, so the two are summed):
  1. the pepy.tech API, if PEPY_API_KEY is set;
  2. otherwise pepy.tech's public badge for the project with `units=none`, which carries the
     exact all-time total and needs no key.
Numbers are never estimated and there is no partial-period fallback: if any package's total
cannot be read, the script exits non-zero without writing, so the previous badge stays up.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

PACKAGES = ("isoline", "telmus")
LABEL = "downloads"
BADGE_URL = "https://static.pepy.tech/personalized-badge/{pkg}?period=total&units=none&left_text=downloads"
_TEXT = re.compile(r"<text\b[^>]*>([^<]*)</text>")


def _get(url: str, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "isoline-badge", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed https hosts)
        return resp.read()


def pepy_api_total(pkg: str, key: str) -> int:
    return int(json.loads(_get(f"https://api.pepy.tech/api/v2/projects/{pkg}", {"X-API-Key": key}))["total_downloads"])


def total_from_badge_svg(svg: str) -> int:
    """The badge's value is its last <text> element; with units=none it is the exact integer."""
    texts = [t.strip() for t in _TEXT.findall(svg)]
    if not texts:
        raise ValueError("no <text> in pepy badge")
    value = texts[-1].replace(",", "").replace(" ", "")
    if not value.isdigit():  # e.g. "1k" would mean pepy ignored units=none: refuse, never guess
        raise ValueError(f"pepy badge value is not an exact count: {texts[-1]!r}")
    return int(value)


def pepy_badge_total(pkg: str) -> int:
    return total_from_badge_svg(_get(BADGE_URL.format(pkg=pkg)).decode("utf-8"))


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def badge(total: int) -> dict:
    return {"schemaVersion": 1, "label": LABEL, "message": human(total), "color": "B4690E"}


def build(packages=PACKAGES, key: str | None = None, api=pepy_api_total, public=pepy_badge_total) -> dict:
    if key:
        return badge(sum(api(p, key) for p in packages))
    return badge(sum(public(p) for p in packages))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "downloads.json"
    data = build(key=os.environ.get("PEPY_API_KEY") or None)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(data)
