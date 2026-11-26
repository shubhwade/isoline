"""Write the Content-Security-Policy <meta> tag into website/index.html.

The page's two inline scripts are allowed by their SHA-256 hashes, so no other script
can run even if markup were ever injected. Re-run after editing any inline script:

    python .github/scripts/website_csp.py
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "website" / "index.html"
MARKER = re.compile(r'<meta http-equiv="Content-Security-Policy" content="[^"]*">\n?')


def policy(html: str) -> str:
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
        for s in scripts
    )
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src {hashes}",
            "style-src 'unsafe-inline' https://fonts.googleapis.com",
            "font-src https://fonts.gstatic.com",
            "img-src 'self' data:",
            "base-uri 'none'",
            "form-action 'none'",
            "object-src 'none'",
        ]
    )


def main() -> None:
    html = MARKER.sub("", PAGE.read_text(encoding="utf-8"))
    tag = f'<meta http-equiv="Content-Security-Policy" content="{policy(html)}">\n'
    anchor = '<meta name="viewport"'
    if anchor not in html:
        raise SystemExit("viewport meta not found")
    html = html.replace(anchor, tag + anchor, 1)
    PAGE.write_text(html, encoding="utf-8")
    print("CSP written with", html.count("<script>"), "script hashes")


if __name__ == "__main__":
    main()
