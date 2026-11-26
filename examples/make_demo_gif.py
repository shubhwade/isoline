"""Build the demo GIF shown in the README and on PyPI.

Four scenes, all in the Isoline brand: a title card, the REAL `isoline scan` output on
the synthetic sample company from make_sample_assets.py, the report it writes scrolling
past in a browser window, and an install card. Frames are rendered with Playwright's
Chromium and encoded with an ffmpeg two-pass palette, so colours stay clean.

    pip install playwright pillow && python -m playwright install chromium
    python examples/make_sample_assets.py docs/assets      # writes sample-report.png
    python examples/make_demo_gif.py docs/assets [--fonts DIR]

--fonts may point at a folder holding JetBrains Mono and Newsreader .woff2 files
(for example from the @fontsource npm packages); otherwise system fonts are used.
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
from make_brand_assets import AMBER, INK, PAPER, mark_svg  # noqa: E402
from make_sample_assets import synthetic  # noqa: E402

from isoline.cli import app as cli  # noqa: E402
from isoline.core.scanner import IsolineScanner  # noqa: E402

W, H = 1200, 675
CMD = "isoline scan ACME"

# Terminal palette tuned to the brand: deep navy ground, paper text, amber/blue accents.
THEME = TerminalTheme(
    (15, 24, 40), (217, 222, 231),
    [(15, 24, 40), (231, 123, 110), (116, 198, 154), (232, 160, 74),
     (127, 167, 217), (196, 160, 230), (125, 196, 214), (217, 222, 231)],
    [(111, 123, 144), (240, 140, 128), (140, 214, 172), (240, 180, 100),
     (150, 186, 232), (210, 180, 240), (150, 210, 226), (243, 241, 236)],
)


def font_css(fonts: Path | None) -> str:
    if not fonts:
        return ""
    rules = []
    for fam, pat in (("JetBrains Mono", "jetbrains-mono-latin-{w}-normal.woff2"),
                     ("Newsreader", "newsreader-latin-{w}-normal.woff2"),
                     ("Newsreader", "newsreader-latin-{w}-italic.woff2")):
        for w in (400, 500, 700):
            hits = list(fonts.rglob(pat.format(w=w)))
            if hits:
                style = "italic" if "italic" in pat else "normal"
                rules.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:{style};"
                             f"src:url('{hits[0].resolve().as_uri()}')}}")
    return "".join(rules)


BASE = """<!doctype html><html><head><meta charset="utf-8"><style>{fonts}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
body{{background:{paper};font-family:Inter,'Segoe UI',system-ui,sans-serif;color:{ink};position:relative}}
.serif{{font-family:Newsreader,Georgia,serif}}.mono{{font-family:'JetBrains Mono','DejaVu Sans Mono',Consolas,monospace}}
#topo{{position:absolute;inset:0}}
.win{{position:absolute;border-radius:12px;overflow:hidden;
 box-shadow:0 0 0 1px rgba(19,33,61,.14),0 40px 80px -30px rgba(15,24,40,.55),0 14px 28px -14px rgba(15,24,40,.35)}}
.bar{{height:36px;display:flex;align-items:center;gap:7px;padding:0 14px}}
.bar i{{width:11px;height:11px;border-radius:50%}}
.cap{{position:absolute;left:0;right:0;bottom:22px;text-align:center;font-size:14px;color:#7A8091;letter-spacing:.01em}}
.cap b{{color:{ink};font-weight:600}}
</style></head><body><canvas id="topo" width="{W2}" height="{H2}"></canvas>{body}
<script>
// static topographic texture (same marching-squares idea as the website)
const c=document.getElementById('topo'),x=c.getContext('2d');x.scale(2,2);
const P=[[.82,.22,.28],[.12,.85,.3],[.55,1.1,.22],[.02,.1,.2]];
const f=(u,v)=>P.reduce((s,[a,b,r],k)=>{{const dx=(u-a)*{asp},dy=v-b;return s+Math.exp(-(dx*dx+dy*dy)/(2*r*r))*(1-k*.1)}},0)+.05*Math.sin(u*9)*Math.cos(v*7);
const st=12,cols=Math.ceil({W}/st)+1,rows=Math.ceil({H}/st)+1,g=[];
for(let j=0;j<rows;j++)for(let i=0;i<cols;i++)g.push(f(i*st/{W},j*st/{H}));
x.strokeStyle='rgba(19,33,61,{alpha})';x.lineWidth=1;
const S={{1:[[3,0]],2:[[0,1]],3:[[3,1]],4:[[1,2]],5:[[3,0],[1,2]],6:[[0,2]],7:[[3,2]],8:[[2,3]],9:[[0,2]],10:[[0,1],[2,3]],11:[[1,2]],12:[[1,3]],13:[[0,1]],14:[[0,3]]}};
for(let L=.1;L<1.3;L+=.09){{x.beginPath();for(let j=0;j<rows-1;j++)for(let i=0;i<cols-1;i++){{
const a=g[j*cols+i],b=g[j*cols+i+1],cc=g[(j+1)*cols+i+1],d=g[(j+1)*cols+i];
const n=(a>L)|(b>L)<<1|(cc>L)<<2|(d>L)<<3;if(!n||n==15)continue;const X=i*st,Y=j*st;
const e=[[X+st*(L-a)/(b-a),Y],[X+st,Y+st*(L-b)/(cc-b)],[X+st*(L-d)/(cc-d),Y+st],[X,Y+st*(L-a)/(d-a)]];
for(const[p,q]of S[n]){{x.moveTo(...e[p]);x.lineTo(...e[q])}}}}x.stroke()}}
</script></body></html>"""


def page(body: str, fonts: str, alpha: float = 0.07) -> str:
    return BASE.format(fonts=fonts, W=W, H=H, W2=W * 2, H2=H * 2, paper=PAPER, ink=INK,
                       body=body, asp=W / H, alpha=alpha)


def title_card(opacity: float, rise: float) -> str:
    mark = mark_svg(size=96).replace("<svg ", '<svg style="display:block;border-radius:22px" ')
    return f"""<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
 justify-content:center;gap:26px;opacity:{opacity};transform:translateY({rise}px)">
 <div style="box-shadow:0 24px 48px -20px rgba(19,33,61,.5);border-radius:22px">{mark}</div>
 <div style="font-size:64px;font-weight:600;letter-spacing:-.035em;line-height:1"><span style="color:{AMBER}">i</span>soline</div>
 <div class="serif" style="font-size:30px;color:#4B5468;font-style:italic;letter-spacing:-.01em">Financial statements, measured precisely.</div>
</div>"""


def terminal(body_html: str, cmd_typed: str, caret: bool, cap: str) -> str:
    caret_html = f'<span style="display:inline-block;width:9px;height:17px;background:#D9DEE7;vertical-align:-3px"></span>' if caret else ""
    prompt = '<span style="color:#7FA7D9">~/research</span> <span style="color:#6F7B90">$</span> '
    return f"""<div class="win" style="left:80px;top:34px;width:1040px;height:560px;background:#0F1828">
 <div class="bar" style="border-bottom:1px solid #22304A"><i style="background:#2C3851"></i><i style="background:#2C3851"></i><i style="background:#2C3851"></i>
 <span style="flex:1;text-align:center;margin-right:50px;font-size:12.5px;color:#6F7B90">isoline — zsh</span></div>
 <pre class="mono" style="margin:0;padding:14px 22px;color:#D9DEE7;font-size:13.4px;line-height:17.6px;white-space:pre;height:524px;overflow:hidden">{prompt}<span style="color:#F3F1EC">{html.escape(cmd_typed)}</span>{caret_html}{body_html}</pre>
</div><div class="cap">{cap}</div>"""


def report(img: Path, offset: int, cap: str) -> str:
    return f"""<div class="win" style="left:150px;top:28px;width:900px;height:570px;background:#fff">
 <div class="bar" style="background:#EEEBE4;border-bottom:1px solid #DED8CB"><i style="background:#D3CCBD"></i><i style="background:#D3CCBD"></i><i style="background:#D3CCBD"></i>
 <span style="margin-left:14px;width:420px;height:22px;border-radius:6px;background:#fff;font-size:12px;line-height:22px;color:#6A6F7A;padding:0 10px">ACME_dashboard.html</span></div>
 <div style="height:534px;overflow:hidden;background:#F3F4F6"><img src="{img.as_uri()}" style="display:block;width:900px;transform:translateY(-{offset}px)"></div>
</div><div class="cap">{cap}</div>"""


def end_card() -> str:
    mark = mark_svg(size=56).replace("<svg ", '<svg style="display:block;border-radius:13px" ')
    return f"""<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px">
 <div style="display:flex;align-items:center;gap:14px">{mark}<span style="font-size:40px;font-weight:600;letter-spacing:-.03em"><span style="color:{AMBER}">i</span>soline</span></div>
 <div class="mono" style="font-size:30px;background:#0F1828;color:#F3F1EC;padding:20px 34px;border-radius:12px;
  box-shadow:0 30px 60px -24px rgba(15,24,40,.55)"><span style="color:#6F7B90">$ </span>pip install isoline</div>
 <div style="font-size:16px;color:#4B5468">Open source · No API key · <b style="color:{INK}">github.com/shubhwade/isoline</b></div>
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
    # 1. title card: fade up, hold
    for k in range(1, 7):
        t = k / 6
        frames.append((page(title_card(t, 14 * (1 - t) ** 2), fonts), 0.05))
    frames.append((page(title_card(1, 0), fonts), 1.6))

    # 2. terminal: type the command, then stream the real output
    lines = scan_lines()
    cap = "Real output of the real engines on a <b>synthetic sample company</b>"
    for n in range(0, len(CMD) + 1):
        frames.append((page(terminal("", CMD[:n], True, cap), fonts, .05), 0.06 if n else 0.5))
    frames.append((page(terminal("", CMD, True, cap), fonts, .05), 0.35))
    visible = 28
    shown = 1
    while shown <= len(lines):
        chunk = lines[max(0, shown - visible + 1):shown]
        frames.append((page(terminal("\n" + "\n".join(chunk), CMD, False, cap), fonts, .05), 0.07))
        shown += 2
    frames.append((page(terminal("\n" + "\n".join(lines[-(visible - 1):]), CMD, False, cap), fonts, .05), 2.4))

    # 3. the report, scrolling with ease-in-out
    rcap = "The same scan as a formal, print-ready report"
    frames.append((page(report(img, 0, rcap), fonts), 1.2))
    max_off = int(2300 * 900 / 1100) - 534
    steps = 34
    for k in range(1, steps + 1):
        t = k / steps
        e = t * t * (3 - 2 * t)
        frames.append((page(report(img, int(e * max_off * 0.62), rcap), fonts), 0.06))
    frames.append((page(report(img, int(max_off * 0.62), rcap), fonts), 1.6))

    # 4. install card
    frames.append((page(end_card(), fonts), 3.0))

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

    concat = tmp / "list.txt"
    with concat.open("w") as fh:
        for i, (_, d) in enumerate(frames):
            fh.write(f"file 'f{i:04d}.png'\nduration {d:.3f}\n")
        fh.write(f"file 'f{len(frames) - 1:04d}.png'\n")
    out = outdir / "demo.gif"
    ff = shutil.which("ffmpeg") or "ffmpeg"
    common = [ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat)]
    subprocess.run(common + ["-vf", "palettegen=max_colors=192:stats_mode=full", str(tmp / "pal.png")], check=True)
    subprocess.run(common + ["-i", str(tmp / "pal.png"), "-lavfi",
                             "[0:v][1:v]paletteuse=dither=sierra2_4a:diff_mode=rectangle",
                             "-fps_mode", "vfr", "-loop", "0", str(out)], check=True)
    print("wrote", out, f"{out.stat().st_size // 1024} KB, {len(frames)} frames")


if __name__ == "__main__":
    main()
