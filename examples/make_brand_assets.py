"""Build the Isoline mark, wordmarks and favicon as dependency-free SVG.

The mark is a set of nested contour lines (isolines) around a single summit point,
drawn from a smooth closed curve so every ring has the same organic shape. Text in the
wordmarks is converted to outlines, so the SVGs render identically on GitHub, PyPI
and in browsers without any web font.

    pip install fonttools
    python examples/make_brand_assets.py docs/assets --font /path/to/InterDisplay-SemiBold.otf
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

INK = "#13213D"  # navy, the brand ink
PAPER = "#F4F1EA"  # warm paper
AMBER = "#C8781A"  # summit / accent
AMBER_DARK = "#E59A3C"  # accent on dark grounds


def _contour(cx: float, cy: float, r: float, wobble: float, n: int = 40) -> str:
    """One closed, smooth contour as a cubic Bezier path (Catmull-Rom through samples)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        k = 1 + wobble * (0.55 * math.sin(2 * t + 0.6) + 0.30 * math.sin(3 * t - 1.1) + 0.15 * math.cos(5 * t))
        pts.append((cx + r * k * math.cos(t) * 1.08, cy + r * k * math.sin(t) * 0.92))
    d = [f"M{pts[0][0]:.2f} {pts[0][1]:.2f}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}")
    return "".join(d) + "Z"


def mark_body(ink: str = INK, line: str = PAPER, accent: str = AMBER, rings: int = 3, width: float = 5.5) -> str:
    """Inner markup of the 128x128 mark."""
    summit = (70.0, 56.0)
    parts = [f'<rect width="128" height="128" rx="28" fill="{ink}"/>']
    parts.append('<g fill="none" stroke-linejoin="round">')
    for k in range(rings, 0, -1):
        # outer rings drift away from the summit and wobble more, like real terrain
        r = 6 + 19 * k
        cx = summit[0] - 4.0 * k
        cy = summit[1] + 5.0 * k
        op = round(1.0 - 0.28 * (k - 1), 2)
        parts.append(f'<path d="{_contour(cx, cy, r, 0.03 + 0.02 * k)}" stroke="{line}" '
                     f'stroke-width="{width}" opacity="{op}"/>')
    parts.append("</g>")
    parts.append(f'<circle cx="{summit[0]}" cy="{summit[1]}" r="9" fill="{accent}"/>')
    return "".join(parts)


def mark_svg(size: int = 128, **kw) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="{size}" height="{size}" '
            f'role="img" aria-label="Isoline"><defs><clipPath id="c"><rect width="128" height="128" rx="28"/>'
            f'</clipPath></defs><g clip-path="url(#c)">{mark_body(**kw)}</g></svg>\n')


def text_path(font_path: str, text: str, size: float, tracking: float = 0.0) -> tuple[str, float]:
    """Outline `text` at `size` px; returns (path d, advance width). Baseline at y=0."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    font = TTFont(font_path)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    x = 0.0
    pen = SVGPathPen(gs)
    for ch in text:
        name = cmap[ord(ch)]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x, 0))
        gs[name].draw(tp)
        x += gs[name].width * scale + tracking
    return pen.getCommands(), x - tracking


def _split_tittle(d: str) -> tuple[str, str]:
    """Split the outline of a lone "i" into (stem, dot): the dot is the upper subpath."""
    subs = [m for m in re.findall(r"M[^M]*", d)]
    def top(sp: str) -> float:
        return min(float(y) for y in re.findall(r"[-\d.]+ ([-\d.]+)", sp))
    subs.sort(key=top)
    return "".join(subs[1:]), subs[0]


def wordmark_svg(font_path: str, text_fill: str, ink: str, line: str, accent: str) -> str:
    d, w = text_path(font_path, "isoline", 64, tracking=-1.2)
    i_d, _ = text_path(font_path, "i", 64)
    stem, dot = _split_tittle(i_d)
    # the leading "i" is drawn first, so its outline is a prefix: recolour only its dot
    assert d.startswith(i_d)
    d = stem + d[len(i_d):]
    mark_px = 80
    gap = 22
    width = math.ceil(mark_px + gap + w + 4)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 96" width="{width}" height="96" '
            f'role="img" aria-label="Isoline"><defs><clipPath id="c"><rect width="128" height="128" rx="28"/>'
            f'</clipPath></defs>'
            f'<g transform="translate(0 8) scale({mark_px / 128})"><g clip-path="url(#c)">'
            f'{mark_body(ink=ink, line=line, accent=accent)}</g></g>'
            f'<g transform="translate({mark_px + gap} 68)"><path d="{d}" fill="{text_fill}"/>'
            f'<path d="{dot}" fill="{accent}"/></g></svg>\n')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="docs/assets")
    ap.add_argument("--font", default="/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    light = dict(ink=INK, line=PAPER, accent=AMBER)
    (out / "logo.svg").write_text(mark_svg(**light), encoding="utf-8")
    (out / "favicon.svg").write_text(mark_svg(size=32, rings=2, width=7, **light), encoding="utf-8")
    (out / "wordmark.svg").write_text(wordmark_svg(a.font, INK, **light), encoding="utf-8")
    (out / "wordmark-dark.svg").write_text(
        wordmark_svg(a.font, PAPER, ink=PAPER, line=INK, accent=AMBER), encoding="utf-8")
    print("wrote", ", ".join(p.name for p in sorted(out.glob("*.svg"))))


if __name__ == "__main__":
    main()
