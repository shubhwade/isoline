"""Write a shields.io endpoint JSON with isoline + legacy telmus downloads combined.

Source order (each package summed, never estimated):
  1. pepy.tech total downloads, if PEPY_API_KEY is set (all-time, includes legacy history).
  2. otherwise pypistats.org, last 30 days (keyless; this window is stated in the label).
If a source fails the previous badge file is left untouched.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

PACKAGES = ("isoline", "telmus")


def fetch(url: str, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "isoline-badge", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed https hosts)
        return json.load(resp)


def pepy_total(pkg: str, key: str) -> int:
    return int(fetch(f"https://api.pepy.tech/api/v2/projects/{pkg}", {"X-API-Key": key})["total_downloads"])


def pypistats_month(pkg: str) -> int:
    try:
        return int(fetch(f"https://pypistats.org/api/packages/{pkg}/recent")["data"]["last_month"])
    except Exception:
        return 0  # a package with no data yet (e.g. just created) counts as 0 only here


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def badge(total: int, label: str) -> dict:
    return {"schemaVersion": 1, "label": label, "message": human(total), "color": "B4690E"}


def build(packages=PACKAGES, key: str | None = None, pepy=pepy_total, stats=pypistats_month) -> dict:
    if key:
        return badge(sum(pepy(p, key) for p in packages), "downloads (isoline + telmus)")
    return badge(sum(stats(p) for p in packages), "downloads / month (isoline + telmus)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "downloads.json"
    data = build(key=os.environ.get("PEPY_API_KEY"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(data)
