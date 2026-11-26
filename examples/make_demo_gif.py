"""Build the demo GIF shown in the README and on PyPI.

Four scenes in the Isoline brand (black, white, one vermilion signal colour): a title
card over ridgeline terrain, the REAL `isoline scan` output on the synthetic sample
company from make_sample_assets.py, the report it writes scrolling in a browser window,
and an install card. Frames are rendered with Playwright's Chromium and encoded with a
two-pass ffmpeg palette. Also writes og.png, the 1200x630 social preview of the website.

    pip install playwright pillow && python -m playwright install chromium
    python examples/make_sample_assets.py docs/assets      # writes sample-report.png
    python examples/make_demo_gif.py docs/assets [--fonts DIR] [--chrome PATH]

--fonts may point at a folder holding Inter Tight and IBM Plex Mono .woff2 files (for
example the @fontsource npm packages); otherwise system fonts are used.
"""

from __future__ import annotations

import argparse
import html
import io
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.terminal_theme import TerminalTheme

sys.path.insert(0, str(Path(__file__).parent))
from make_brand_assets import ACCENT, mark_svg  # noqa: E402
from make_sample_assets import synthetic  # noqa: E402

from isoline.cli import app as cli  # noqa: E402
from isoline.core.scanner import IsolineScanner  # noqa: E402

W, H = 1200, 675
CMD = "isoline scan ACME"
BG = "#0A0A0A"
PANEL = "#141414"
LINE = "#262626"
DIM = "#6E6E6B"
TEXT = "#E8E8E5"

# Neutral terminal palette: greys and white, with vermilion in place of red/yellow.
THEME = TerminalTheme(
    (20, 20, 20), (210, 210, 206),
    [(20, 20, 20), (255, 90, 46), (244, 244, 242), (255, 90, 46),
     (244, 244, 242), (163, 163, 160), (200, 200, 196), (210, 210, 206)],
    [(110, 110, 107), (255, 110, 70), (255, 255, 255), (255, 110, 70),
     (255, 255, 255), (190, 190, 186), (220, 220, 216), (255, 255, 255)],
)


def font_css(fonts: Path | None) -> str:
    if not fonts:
        return ""
    rules = []
    for fam, pat, weights in (("Inter Tight", "inter-tight-latin-{w}-normal.woff2", (400, 600)),
                              ("IBM Plex Mono", "ibm-plex-mono-latin-{w}-normal.woff2", (400, 500))):
        for w in weights:
            hits = sorted(fonts.rglob(pat.format(w=w)))
            if hits:
                rules.append(f"@font-face{{font-family:'{fam}';font-weight:{w};"
                             f"src:url('{hits[0].resolve().as_uri()}')}}")
    return "".join(rules)


BASE = """<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
body{{background:{bg};font-family:'Inter Tight',Inter,'Segoe UI',system-ui,sans-serif;color:#F4F4F2;position:relative}}
.mono{{font-family:'IBM Plex Mono','DejaVu Sans Mono',Consolas,monospace}}
#ridge{{position:absolute;inset:0}}
.win{{position:absolute;border-radius:14px;overflow:hidden;box-shadow:0 0 0 1px {line},0 40px 90px -30px rgba(0,0,0,.9)}}
.bar{{height:36px;display:flex;align-items:center;gap:7px;padding:0 14px}}
.bar i{{width:11px;height:11px;border-radius:50%}}
.cap{{position:absolute;left:0;right:0;bottom:22px;text-align:center;font-size:14px;color:{dim};
 font-family:'IBM Plex Mono',monospace;letter-spacing:.04em;text-transform:uppercase;font-size:11.5px}}
.cap b{{color:{accent};font-weight:500}}
</style></head><body><canvas id="ridge" width="{W2}" height="{H2}"></canvas>{body}
<script>
// ridgeline terrain, the same motif as the website hero
const c=document.getElementById('ridge'),x=c.getContext('2d');x.scale(2,2);
const P=[[.72,.45,.13,1],[.88,.62,.09,.7],[.5,.72,.16,.55],[.2,.55,.12,.4],[.96,.3,.1,.5]];
const h=(u,v)=>P.reduce((s,[a,b,r,k])=>{{const dx=u-a,dy=(v-b)*1.4;return s+k*Math.exp(-(dx*dx+dy*dy)/(2*r*r))}},0)+.05*Math.sin(u*22+v*6)*Math.sin(v*15);
const rows=34,y0={H}*{top},bot={H}*1.02,amp={H}*.32,hot={hot};
for(let r=0;r<rows;r++){{const v=r/(rows-1),base=y0+(bot-y0)*v,k=.35+v*.65;x.beginPath();x.moveTo(0,base);
for(let X=0;X<={W}+5;X+=5)x.lineTo(X,base-amp*h(X/{W},v)*k);x.lineTo({W},{H}+2);x.lineTo(0,{H}+2);x.closePath();
x.fillStyle='{bg}';x.fill();const isHot=r===hot;x.strokeStyle=isHot?'{accent}':'#F4F4F2';
x.globalAlpha=isHot?1:{alpha}*(.25+v*.75);x.lineWidth=isHot?1.7:1;x.stroke();x.globalAlpha=1}}
</script></body></html>"""


def page(body: str, fonts: str, alpha: float = .45, top: float = .12, hot: int = 15) -> str:
    return BASE.format(fonts=fonts, W=W, H=H, W2=W * 2, H2=H * 2, bg=BG, line=LINE, dim=DIM,
                       accent=ACCENT, body=body, alpha=alpha, top=top, hot=hot)


def dark_mark(size: int) -> str:
    return mark_svg(size=size).replace("<svg ", f'<svg style="display:block;border-radius:{size * 28 // 128}px;'
                                               f'box-shadow:0 0 0 1px #333" ')


def title_card(t: float) -> str:
    """t in [0, 1]: words slide up out of a mask, then the tagline fades in."""
    def line(text: str, delay: float, color: str = "#F4F4F2") -> str:
        k = max(0.0, min(1.0, (t - delay) / 0.5))
        k = 1 - (1 - k) ** 3
        return (f'<div style="overflow:hidden;padding-bottom:16px;margin-bottom:-10px"><div style="transform:translateY({(1 - k) * 105:.1f}%);'
                f'color:{color}">{text}</div></div>')
    fade = max(0.0, min(1.0, (t - 0.55) / 0.45))
    return f"""<div style="position:absolute;inset:0;background:linear-gradient(90deg,{BG} 0%,rgba(10,10,10,.85) 40%,rgba(10,10,10,0) 70%)"></div>
<div style="position:absolute;left:72px;top:96px;opacity:{min(1, t * 3):.2f}">{dark_mark(56)}</div>
<div style="position:absolute;left:72px;top:180px;font-size:92px;font-weight:600;letter-spacing:-.06em;line-height:.9">
 {line("Financial", 0)}{line("statements,", .1)}{line("measured precisely.", .2, ACCENT)}</div>
<div class="mono" style="position:absolute;left:76px;top:520px;font-size:15px;color:#A3A3A0;opacity:{fade:.2f};letter-spacing:.02em">
 isoline · open-source financial statement analysis</div>"""


def terminal(body_html: str, cmd_typed: str, caret: bool) -> str:
    caret_html = f'<span style="display:inline-block;width:9px;height:17px;background:{ACCENT};vertical-align:-3px"></span>' if caret else ""
    prompt = f'<span style="color:{DIM}">~/research $</span> '
    return f"""<div style="position:absolute;inset:0;background:rgba(10,10,10,.6)"></div>
<div class="win" style="left:80px;top:34px;width:1040px;height:560px;background:{PANEL}">
 <div class="bar" style="border-bottom:1px solid {LINE}"><i style="background:#2E2E2E"></i><i style="background:#2E2E2E"></i><i style="background:#2E2E2E"></i>
 <span class="mono" style="flex:1;text-align:center;margin-right:50px;font-size:12px;color:{DIM}">isoline — zsh</span></div>
 <pre class="mono" style="margin:0;padding:14px 22px;color:{TEXT};font-size:13.2px;line-height:17.4px;white-space:pre;height:524px;overflow:hidden">{prompt}<span style="color:#fff">{html.escape(cmd_typed)}</span>{caret_html}{body_html}</pre>
</div><div class="cap">Real output of the real engines · <b>synthetic sample company</b></div>"""


def report(img: Path, offset: int) -> str:
    return f"""<div style="position:absolute;inset:0;background:rgba(10,10,10,.6)"></div>
<div class="win" style="left:150px;top:28px;width:900px;height:570px;background:#fff">
 <div class="bar" style="background:#F2F2F0;border-bottom:1px solid #E2E2DF"><i style="background:#D6D6D2"></i><i style="background:#D6D6D2"></i><i style="background:#D6D6D2"></i>
 <span class="mono" style="margin-left:14px;font-size:11.5px;color:#6F6F68">ACME_dashboard.html</span></div>
 <div style="height:534px;overflow:hidden;background:#F3F4F6"><img src="{img.as_uri()}" style="display:block;width:900px;transform:translateY(-{offset}px)"></div>
</div><div class="cap">The same scan as a formal, print-ready report</div>"""


def end_card() -> str:
    return f"""<div style="position:absolute;inset:0;background:linear-gradient(0deg,{BG} 10%,rgba(10,10,10,.7) 60%,rgba(10,10,10,.4))"></div>
<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px">
 <div style="display:flex;align-items:center;gap:14px">{dark_mark(52)}<span style="font-size:44px;font-weight:600;letter-spacing:-.045em"><span style="color:{ACCENT}">i</span>soline</span></div>
 <div class="mono" style="font-size:28px;background:#141414;color:#fff;padding:18px 18px 18px 32px;border-radius:999px;display:flex;align-items:center;gap:22px;
  box-shadow:0 0 0 1px #333,0 30px 60px -24px rgba(0,0,0,.9)"><span><span style="color:{DIM}">$ </span>pip install isoline</span>
  <span style="width:44px;height:44px;border-radius:50%;background:{ACCENT}"></span></div>
 <div class="mono" style="font-size:13px;color:#A3A3A0;letter-spacing:.06em;text-transform:uppercase">Open source · No API key · isolinee.vercel.app</div>
</div>"""


def scan_lines() -> list[str]:
    with patch("isoline.core.scanner.load_financials", return_value=synthetic()):
        result = IsolineScanner().scan("ACME")
    rec = Console(record=True, width=108, force_terminal=True, color_system="truecolor", file=io.StringIO())
    cli.console = rec
    cli._print_scan(result)
    out = rec.export_html(theme=THEME, inline_styles=True, code_format="{code}")
    out = re.sub(r"</?pre[^>]*>", "", out)
    return out.rstrip("\n").split("\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="docs/assets")
    ap.add_argument("--fonts", type=Path, default=None)
    ap.add_argument("--chrome", default=None, help="Path to a Chrome/Chromium binary (optional).")
    a = ap.parse_args()
    outdir = Path(a.out)
    fonts = font_css(a.fonts)
    img = (outdir / "sample-report.png").resolve()

    frames: list[tuple[str, float]] = []  # (html, seconds)
    # 1. title: words rise out of a mask over the terrain; the hot ridgeline climbs
    for k in range(0, 15):
        frames.append((page(title_card(k / 14), fonts, hot=8 + k // 2), 0.05))
    frames.append((page(title_card(1), fonts, hot=15), 1.7))

    # 2. terminal: type the command, then stream the real output
    lines = scan_lines()
    for n in range(0, len(CMD) + 1):
        frames.append((page(terminal("", CMD[:n], True), fonts, .16, hot=-1), 0.06 if n else 0.45))
    frames.append((page(terminal("", CMD, True), fonts, .16, hot=-1), 0.35))
    visible = 28
    shown = 1
    while shown <= len(lines):
        chunk = lines[max(0, shown - visible + 1):shown]
        frames.append((page(terminal("\n" + "\n".join(chunk), CMD, False), fonts, .16, hot=-1), 0.07))
        shown += 2
    frames.append((page(terminal("\n" + "\n".join(lines[-(visible - 1):]), CMD, False), fonts, .16, hot=-1), 2.4))

    # 3. the report, scrolling with ease-in-out
    frames.append((page(report(img, 0), fonts, .16, hot=-1), 1.2))
    from PIL import Image as _Image

    iw, ih = _Image.open(img).size
    max_off = int(ih * 900 / iw) - 534
    steps = 34
    for k in range(1, steps + 1):
        t = k / steps
        e = t * t * (3 - 2 * t)
        frames.append((page(report(img, int(e * max_off * 0.62)), fonts, .16, hot=-1), 0.06))
    frames.append((page(report(img, int(max_off * 0.62)), fonts, .16, hot=-1), 1.6))

    # 4. install card
    frames.append((page(end_card(), fonts, .5, top=.3, hot=20), 3.0))

    from playwright.sync_api import sync_playwright

    tmp = Path(tempfile.mkdtemp())
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=a.chrome) if a.chrome else pw.chromium.launch()
        pg = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for i, (doc, _) in enumerate(frames):
            src = tmp / "frame.html"
            src.write_text(doc, encoding="utf-8")
            pg.goto(src.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=str(tmp / f"f{i:04d}.png"))
        browser.close()

    # social preview (1200x630) from the settled title frame
    from PIL import Image

    title_idx = 15
    Image.open(tmp / f"f{title_idx:04d}.png").convert("RGB").crop((0, 0, W, 630)).save(outdir / "og.png", optimize=True)
    site = Path(__file__).resolve().parents[1] / "website"
    if site.is_dir() and outdir.resolve() == (site.parent / "docs" / "assets").resolve():
        shutil.copyfile(outdir / "og.png", site / "og.png")  # served at https://isolinee.vercel.app/og.png

    concat = tmp / "list.txt"
    with concat.open("w") as fh:
        for i, (_, d) in enumerate(frames):
            fh.write(f"file 'f{i:04d}.png'\nduration {d:.3f}\n")
        fh.write(f"file 'f{len(frames) - 1:04d}.png'\n")
    out = outdir / "demo.gif"
    ff = shutil.which("ffmpeg") or "ffmpeg"
    common = [ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat)]
    subprocess.run(common + ["-vf", "palettegen=max_colors=160:stats_mode=full", str(tmp / "pal.png")], check=True)
    subprocess.run(common + ["-i", str(tmp / "pal.png"), "-lavfi",
                             "[0:v][1:v]paletteuse=dither=sierra2_4a:diff_mode=rectangle",
                             "-fps_mode", "vfr", "-loop", "0", str(out)], check=True)
    print("wrote", out, f"{out.stat().st_size // 1024} KB, {len(frames)} frames")


if __name__ == "__main__":
    main()
