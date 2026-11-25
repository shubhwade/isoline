"""Build the landscape demo GIF used in the README.

Frames are rendered from the REAL command output (isoline scan on the synthetic sample
company defined in make_sample_assets.py). Requires Pillow and Google Chrome.

    python examples/make_demo_gif.py docs/assets
"""

from __future__ import annotations

import html
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from rich.console import Console
from rich.terminal_theme import MONOKAI

sys.path.insert(0, str(Path(__file__).parent))
from make_sample_assets import synthetic  # noqa: E402

from isoline.cli import app as cli  # noqa: E402
from isoline.core.scanner import IsolineScanner  # noqa: E402

W, H = 1280, 720
CMD = "isoline scan ACME --no-open"
PAGE = """<html><body style="margin:0;background:#E9E6DF;font-family:Segoe UI,Calibri,Arial,sans-serif">
<div style="position:absolute;left:60px;top:40px;width:1160px;height:640px;background:#12161D;border-radius:8px;
 box-shadow:0 10px 40px rgba(0,0,0,.35);overflow:hidden">
 <div style="height:36px;background:#1E242E;display:flex;align-items:center;padding-left:14px;gap:8px">
  <i style="width:12px;height:12px;border-radius:6px;background:#E5605A"></i><i style="width:12px;height:12px;border-radius:6px;background:#E6B450"></i><i style="width:12px;height:12px;border-radius:6px;background:#5FBF77"></i>
  <span style="color:#9AA4B2;font-size:13px;margin-left:14px">PowerShell</span></div>
 <pre style="margin:0;padding:14px 20px;color:#D8DEE9;font:15px/20px Consolas,'DejaVu Sans Mono',monospace;white-space:pre;overflow:hidden;height:570px">{body}</pre></div>
<div style="position:absolute;left:60px;top:690px;color:#5B6472;font-size:13px">Real output of the real engines on a synthetic sample company.</div>
</body></html>"""
REPORT = """<html><body style="margin:0;background:#E9E6DF;font-family:Segoe UI,Calibri,Arial,sans-serif">
<div style="position:absolute;left:150px;top:30px;width:980px;height:640px;background:#fff;border-radius:8px;
 box-shadow:0 10px 40px rgba(0,0,0,.35);overflow:hidden">
 <div style="height:40px;background:#DEE1E6;display:flex;align-items:center;padding-left:14px;gap:10px">
  <span style="background:#fff;border-radius:14px;padding:5px 16px;font-size:13px;color:#333;width:620px">file:///reports/ACME_scan.html</span></div>
 <img src="file://{img}" style="width:980px;display:block"></div>
<div style="position:absolute;left:150px;top:690px;color:#5B6472;font-size:13px">The same scan opens as a formal, print-ready report (synthetic sample company).</div>
</body></html>"""


def shot(html_text: str, out: Path, tmp: Path) -> None:
    src = tmp / (out.stem + ".html")
    src.write_text(html_text, encoding="utf-8")
    subprocess.run(["google-chrome", "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={W},{H}", f"--screenshot={out}", f"file://{src}"],
                   check=True, capture_output=True)


def main(outdir: Path) -> None:
    with patch("isoline.core.scanner.load_financials", return_value=synthetic()):
        result = IsolineScanner().scan("ACME")
    rec = Console(record=True, width=120, force_terminal=True, color_system="truecolor")
    cli.console = rec
    cli._print_scan(result)
    body = rec.export_html(theme=MONOKAI, inline_styles=True, code_format="{code}").replace("<pre", "<span").replace("</pre>", "</span>")
    lines = body.split("\n")
    prompt = '<span style="color:#7FB3E0">PS C:\\isoline&gt;</span> '
    visible = 28
    frames: list[tuple[str, int]] = []
    for n in range(0, len(CMD) + 1, 3):
        frames.append((prompt + html.escape(CMD[:n]) + "▌", 120))
    frames.append((prompt + html.escape(CMD), 400))
    for k in range(4, len(lines) + 1, 4):
        chunk = lines[max(0, k - visible):k]
        frames.append((prompt + html.escape(CMD) + "\n" + "\n".join(chunk), 160))
    frames.append((prompt + html.escape(CMD) + "\n" + "\n".join(lines[-visible:]), 2200))
    tmp = Path(tempfile.mkdtemp())
    imgs, durs = [], []
    for i, (text, d) in enumerate(frames):
        p = tmp / f"f{i:03d}.png"
        shot(PAGE.replace("{body}", text), p, tmp)
        imgs.append(Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=128))
        durs.append(d)
    rep = tmp / "report.png"
    full = (outdir / "sample-report.png").resolve()
    shot(REPORT.replace("{img}", str(full)), rep, tmp)
    imgs.append(Image.open(rep).convert("P", palette=Image.ADAPTIVE, colors=128))
    durs.append(3500)
    out = outdir / "demo.gif"
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=durs, loop=0, optimize=True)
    print("wrote", out, f"{out.stat().st_size // 1024} KB, {len(imgs)} frames")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets"))
