"""Build the launch video: a 1080p motion-graphics piece combining the project and the website.

Every number on screen comes from the real engines run on the SYNTHETIC sample company from
make_sample_assets.py; the terminal shows the real `isoline scan` output, the report is the
real report, and the website is the real site/index.html recorded while it scrolls.

    pip install playwright pillow
    python examples/make_launch_video.py OUT.mp4 --fonts DIR [--chrome PATH] [--fps 30]

--fonts points at a folder holding the Inter Tight and IBM Plex Mono .woff2 files (for example
the @fontsource npm packages: `npm pack @fontsource/inter-tight @fontsource/ibm-plex-mono`).
Needs ffmpeg with libx264 on PATH.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from make_brand_assets import ACCENT, mark_svg  # noqa: E402
from make_demo_gif import scan_lines  # noqa: E402
from make_sample_assets import synthetic  # noqa: E402

from isoline.core.scanner import IsolineScanner  # noqa: E402
from isoline.exporters.report import scan_report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
W, H = 1920, 1080
SITE_FRAMES = 196
# [frame, scrollY]: hero, statements table, Piotroski counting to 9/9, Altman gauge settling
SITE_KEYS = [[0, 0], [22, 0], [50, 1350], [64, 1350], [88, 2350], [118, 3050], [132, 3050], [156, 3750], [196, 3750]]


def font_faces(fonts: Path, *, remote_prefix: str | None = None) -> str:
    rules = []
    for fam, slug in (("Inter Tight", "inter-tight"), ("IBM Plex Mono", "ibm-plex-mono")):
        for w in (300, 400, 500, 600, 700):
            hits = sorted(fonts.rglob(f"{slug}-latin-{w}-normal.woff2"))
            if hits:
                src = f"{remote_prefix}{hits[0].name}" if remote_prefix else hits[0].resolve().as_uri()
                rules.append(f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('{src}') format('woff2')}}")
    return "\n".join(rules)


def ease(k: float) -> float:
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def record_site(browser, fonts: Path, out: Path) -> None:
    """Scroll the real website and keep one viewport screenshot per video frame."""
    files = {p.name: p for p in fonts.rglob("*.woff2")}
    css = font_faces(fonts, remote_prefix="https://fonts.gstatic.com/x/")
    page = browser.new_page(viewport={"width": 1600, "height": 960}, device_scale_factor=1)
    page.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(content_type="text/css", body=css))
    page.route("https://fonts.gstatic.com/**", lambda r: r.fulfill(
        content_type="font/woff2", body=files[r.request.url.rsplit("/", 1)[-1]].read_bytes()))
    page.goto((ROOT / "website" / "index.html").as_uri(), wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(1800)

    def y_at(i: int) -> float:
        for (f0, y0), (f1, y1) in zip(SITE_KEYS, SITE_KEYS[1:], strict=False):
            if i <= f1:
                return y0 + (y1 - y0) * ease(1 if f1 == f0 else (i - f0) / (f1 - f0))
        return SITE_KEYS[-1][1]

    out.mkdir(parents=True, exist_ok=True)
    for i in range(SITE_FRAMES):
        page.evaluate(f"window.scrollTo(0, {round(y_at(i))})")
        page.wait_for_timeout(16)
        page.screenshot(path=str(out / f"f{i:04d}.jpg"), type="jpeg", quality=92)
    page.close()


def render_report(browser, work: Path) -> Path:
    with patch("isoline.core.scanner.load_financials", return_value=synthetic()):
        result = IsolineScanner().scan("ACME")
    html_path = work / "report.html"
    html_path.write_text(scan_report(result), encoding="utf-8")
    page = browser.new_page(viewport={"width": 1100, "height": 1000}, device_scale_factor=2)
    page.goto(html_path.as_uri())
    page.wait_for_timeout(300)
    box = page.locator(".page").bounding_box()
    png = work / "report2x.png"
    page.screenshot(path=str(png), full_page=True,
                    clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": 2300})
    page.close()
    return png


def drawable_mark(size: int, cls: str) -> str:
    """The brand mark with each contour ring made drawable (pathLength=1)."""
    svg = mark_svg(size=size).replace("<path ", '<path pathLength="1" class="ring" ')
    svg = svg.replace("<circle ", '<circle class="dot" ').replace('id="c"', f'id="c{cls}"').replace("url(#c)", f"url(#c{cls})")
    return svg.replace("<svg ", f'<svg class="{cls}" ')


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><style>
%%FONTS%%
:root{--bg:#0A0A0A;--ink:#F4F4F2;--ink2:#A3A3A0;--ink3:#6E6E6B;--line:#222;--accent:%%ACCENT%%}
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:var(--bg);color:var(--ink);
 font-family:'Inter Tight',Inter,sans-serif;-webkit-font-smoothing:antialiased}
.mono{font-family:'IBM Plex Mono','JetBrains Mono',monospace}
#ridge{position:absolute;inset:0}
.vig{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 45%,rgba(10,10,10,0) 55%,rgba(0,0,0,.55) 100%);pointer-events:none}
.scene{position:absolute;inset:0;opacity:0}
.mask{overflow:hidden;padding-bottom:.12em;margin-bottom:-.12em}
.mask>div{will-change:transform}
.label{font-size:17px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink3)}
.label b{color:var(--accent);font-weight:500}
.dotlab::before{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);margin-right:16px;vertical-align:2px}
.caret{display:inline-block;width:10px;height:19px;background:var(--accent);vertical-align:-3px}
/* scene 1 */
#s1title{position:absolute;left:150px;top:330px;font-size:178px;font-weight:600;letter-spacing:-.058em;line-height:.88}
#s1sub{position:absolute;left:156px;top:880px;font-size:26px;color:var(--ink2);letter-spacing:-.005em}
#s1lab{position:absolute;left:156px;top:268px}
#bigmark{position:absolute;left:0;top:0;transform-origin:0 0}
#nav{position:absolute;left:150px;top:96px;display:flex;align-items:center;gap:18px;font-size:40px;font-weight:600;letter-spacing:-.045em}
/* scene 2 */
.win{position:absolute;border-radius:14px;overflow:hidden;box-shadow:0 0 0 1px #2a2a2a,0 60px 120px -40px rgba(0,0,0,.95)}
.bar{height:44px;display:flex;align-items:center;gap:9px;padding:0 18px}
.bar i{width:13px;height:13px;border-radius:50%;background:#2E2E2E}
.bar span{flex:1;text-align:center;margin-right:64px;font-size:14px;color:var(--ink3)}
#term{left:250px;top:110px;width:1420px;height:820px;background:#121212}
#tpre{margin:0;padding:18px 28px;color:#E8E8E5;font-size:19px;line-height:24px;white-space:pre;height:776px;overflow:hidden}
.cap{position:absolute;left:0;right:0;top:966px;text-align:center}
.hl{background:rgba(255,74,28,.16);box-shadow:inset 3px 0 0 var(--accent)}
/* scene 3 */
#s3l{position:absolute;left:150px;top:150px;width:760px}
#s3l h2{font-size:104px;font-weight:600;letter-spacing:-.055em;line-height:.92;margin:26px 0 54px}
.call{display:flex;gap:22px;align-items:baseline;padding:20px 0;border-top:1px solid #1f1f1f;font-size:29px;letter-spacing:-.015em;color:#565654}
.call .n{font-size:16px;letter-spacing:.1em;color:#4a4a48;width:38px}
.call.on{color:var(--ink)}
.call.on .n{color:var(--accent)}
#sheet{left:1000px;top:64px;width:780px;height:952px;background:#fff}
#sheet .bar{background:#F2F2F0;border-bottom:1px solid #E2E2DF;height:44px}
#sheet .bar i{background:#D6D6D2}
#sheet .bar span{text-align:left;margin-left:10px;color:#6F6F68}
#sview{position:relative;height:908px;overflow:hidden;background:#fff}
#simg{position:absolute;left:0;top:0;width:780px;display:block}
#shl{position:absolute;border:2.5px solid var(--accent);background:rgba(255,74,28,.07);border-radius:3px}
/* scene 4 */
.col{position:absolute;top:250px;width:500px}
.col .num{font-size:236px;font-weight:600;letter-spacing:-.06em;line-height:1;margin-top:26px;font-variant-numeric:tabular-nums}
.col .num small{font-size:96px;color:var(--ink3);letter-spacing:-.04em}
.col .rule{height:2px;background:#2a2a2a;margin:24px 0 22px;position:relative}
.col .rule i{position:absolute;left:0;top:0;height:2px;background:var(--accent)}
.col .what{font-size:28px;color:var(--ink2);letter-spacing:-.01em;line-height:1.3}
#dcf{position:absolute;left:150px;top:790px;width:1620px}
#dcfbar{position:relative;height:2px;background:#2a2a2a;margin-top:118px}
#dcfbar i{position:absolute;left:0;top:0;height:2px;background:var(--ink2)}
.tick{position:absolute;top:-100px;transform:translateX(-50%);text-align:center;white-space:nowrap}
.tick .v{font-size:40px;font-weight:600;letter-spacing:-.03em}
.tick .k{font-size:15px;letter-spacing:.12em;color:var(--ink3);text-transform:uppercase;margin-top:6px}
.tick .pin{position:absolute;left:50%;top:93px;width:14px;height:14px;margin-left:-7px;border-radius:50%;background:var(--bg);box-shadow:0 0 0 2px var(--ink2)}
.tick.base .v{color:var(--accent);font-size:64px;margin-top:-26px}
.tick.base .pin{background:var(--accent);box-shadow:none}
/* scene 5 */
#s5h{position:absolute;left:150px;top:130px;font-size:104px;font-weight:600;letter-spacing:-.055em;line-height:.92}
.card{position:absolute;width:520px;height:236px;background:#111;border:1px solid #232323;border-radius:12px;padding:34px 34px}
.card .c{font-size:23px;color:#fff;white-space:nowrap}
.card .c span{color:var(--ink3)}
.card .u{height:2px;background:var(--accent);margin:26px 0 24px}
.card .t{font-size:29px;color:var(--ink2);letter-spacing:-.015em;line-height:1.25}
/* scene 6 */
#browser{left:232px;top:96px;width:1456px;height:918px;background:#0A0A0A}
#browser .bar{background:#161616;border-bottom:1px solid #262626;gap:9px}
#browser .url{flex:1;margin:0 120px 0 90px;height:28px;border-radius:7px;background:#0d0d0d;border:1px solid #262626;display:flex;align-items:center;justify-content:center;font-size:14.5px;color:var(--ink2)}
#browser .url b{color:var(--ink);font-weight:500}
#siteimg{display:block;width:1456px;height:874px;object-fit:cover;object-position:top}
/* scene 7 */
#end{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
#endrow{display:flex;align-items:center;gap:34px}
#endword{font-size:148px;font-weight:600;letter-spacing:-.055em;line-height:1}
#pill{margin-top:64px;font-size:38px;background:#141414;padding:22px 24px 22px 44px;border-radius:999px;display:flex;align-items:center;gap:30px;box-shadow:0 0 0 1px #333,0 40px 80px -30px rgba(0,0,0,.9)}
#pill i{width:56px;height:56px;border-radius:50%;background:var(--accent)}
#links{margin-top:54px;font-size:21px;letter-spacing:.06em;color:var(--ink2)}
#links b{color:var(--ink);font-weight:500}
#fine{position:absolute;left:0;right:0;bottom:56px;text-align:center;font-size:15px;letter-spacing:.1em;color:#77777A;text-transform:uppercase}
#fade{position:absolute;inset:0;background:#000;opacity:0}
</style></head><body>
<canvas id="ridge" width="1920" height="1080"></canvas><div class="vig"></div>

<div class="scene" id="s1">
 <div id="bigmark">%%MARK_BIG%%</div>
 <div id="nav"><span id="navword" style="opacity:0"><span style="color:var(--accent)">i</span>soline</span></div>
 <div id="s1lab" class="label mono dotlab">v0.9.0 · open source · MIT</div>
 <div id="s1title"><div class="mask"><div>Financial</div></div><div class="mask"><div>statements,</div></div>
  <div class="mask"><div style="color:var(--accent)">measured precisely.</div></div></div>
 <div id="s1sub">Piotroski, Altman and Beneish scores, a DCF and a print-ready report for any listed company. From your terminal.</div>
</div>

<div class="scene" id="s2">
 <div class="win" id="term"><div class="bar"><i></i><i></i><i></i><span class="mono">isoline — zsh</span></div><pre id="tpre" class="mono"></pre></div>
 <div class="cap label mono">Real output of the real engines · <b>synthetic sample company</b></div>
</div>

<div class="scene" id="s3">
 <div id="s3l"><div class="label mono dotlab">The report</div><h2>Then it writes<br>the report.</h2>
  <div class="call"><span class="n mono">01</span><span>Laid out like a published annual report</span></div>
  <div class="call"><span class="n mono">02</span><span>Every figure explained in plain English</span></div>
  <div class="call"><span class="n mono">03</span><span>Costs in (parentheses), totals double-ruled</span></div>
  <div class="call"><span class="n mono">04</span><span>Missing data says n/a. Never a zero.</span></div>
 </div>
 <div class="win" id="sheet"><div class="bar"><i></i><i></i><i></i><span class="mono">ACME_dashboard.html</span></div>
  <div id="sview"><img id="simg" src="%%REPORT%%"><div id="shl"></div></div></div>
</div>

<div class="scene" id="s4">
 <div class="label mono" style="position:absolute;left:150px;top:150px">Acme Industrial · <b>synthetic sample company</b> · real engine output</div>
 <div class="col" id="c1" style="left:150px"><div class="label mono">Piotroski F-score</div><div class="num"><span id="n1">0</span><small>/9</small></div>
  <div class="rule"><i></i></div><div class="what">Strong. All nine tests passed.</div></div>
 <div class="col" id="c2" style="left:710px"><div class="label mono">Altman Z″-score</div><div class="num" id="n2">0.00</div>
  <div class="rule"><i></i></div><div class="what">Safe zone. Low risk of financial distress.</div></div>
 <div class="col" id="c3" style="left:1270px"><div class="label mono">Beneish M-score</div><div class="num" id="n3" style="color:var(--accent)">n/a</div>
  <div class="rule"><i></i></div><div class="what">Required inputs are missing, so no score. Never a zero.</div></div>
 <div id="dcf"><div class="label mono">DCF fair value per share · bear, base and bull cases</div>
  <div id="dcfbar"><i></i>
   <div class="tick" id="tb" style="left:12%"><div class="v">$14.64</div><div class="k mono">Bear</div><div class="pin"></div></div>
   <div class="tick base" id="tm" style="left:50%"><div class="v">$19.02</div><div class="k mono">Base</div><div class="pin"></div></div>
   <div class="tick" id="tu" style="left:88%"><div class="v">$23.49</div><div class="k mono">Bull</div><div class="pin"></div></div>
  </div></div>
</div>

<div class="scene" id="s5">
 <div id="s5h">More than a scan.</div>
 %%CARDS%%
</div>

<div class="scene" id="s6">
 <div class="win" id="browser"><div class="bar"><i></i><i></i><i></i><div class="url mono"><b>isolinee.vercel.app</b></div></div>
  <img id="siteimg" src="%%SITE0%%"></div>
</div>

<div class="scene" id="s7"><div id="end">
 <div id="endrow">%%MARK_END%%<div id="endword"><span style="color:var(--accent)">i</span>soline</div></div>
 <div id="pill" class="mono"><span><span style="color:var(--ink3)">$ </span>pip install isoline</span><i></i></div>
 <div id="links" class="mono"><b>isolinee.vercel.app</b> &nbsp;·&nbsp; github.com/shubhwade/isoline &nbsp;·&nbsp; free and open source, MIT</div>
</div><div id="fine" class="mono">Screening statistics from public data · not investment advice</div></div>

<div id="fade"></div>
<script>
const W=1920,H=1080,ACC='%%ACCENT%%';
const TERM=%%TERM%%, SITE=%%SITEFRAMES%%, CARDS=%%CARDDATA%%;
const $=id=>document.getElementById(id);
const cl=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const P=(t,a,b)=>cl((t-a)/(b-a));
const eo=k=>1-Math.pow(1-k,3), eio=k=>k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2, ebk=k=>{const c=1.6;return 1+(c+1)*Math.pow(k-1,3)+c*Math.pow(k-1,2)};
const lerp=(a,b,k)=>a+(b-a)*k;
const win=(t,a,b,fi=.5,fo=.5)=>Math.min(P(t,a,a+fi),1-P(t,b-fo,b));
// scene windows
const S={s1:[0,6.2],s2:[6.2,14.6],s3:[14.6,22.6],s4:[22.6,28.8],s5:[28.8,34.0],s6:[34.0,40.9],s7:[40.9,46.0]};
const DUR=46.0;

/* ---------- ridgeline terrain (the website's motif), animated ---------- */
const cv=$('ridge'),cx=cv.getContext('2d');
const PK=[[.72,.45,.13,1],[.88,.62,.09,.7],[.5,.72,.16,.55],[.2,.55,.12,.4],[.96,.3,.1,.5]];
function hgt(u,v,t){let s=0;for(let i=0;i<PK.length;i++){const[a,b,r,k]=PK[i];
 const aa=a+.035*Math.sin(t*.32+i*1.7),bb=b+.02*Math.cos(t*.27+i);const dx=u-aa,dy=(v-bb)*1.4;
 s+=k*(1+.08*Math.sin(t*.6+i))*Math.exp(-(dx*dx+dy*dy)/(2*r*r));}
 return s+.05*Math.sin(u*22+v*6+t*.9)*Math.sin(v*15-t*.4);}
const RK=[[0,0],[1.4,.5],[5.6,.5],[6.6,.16],[14.2,.16],[15,.1],[22.2,.1],[23,.32],[28.4,.32],[29.2,.2],[33.6,.2],[34.4,.08],[40.5,.08],[41.4,.5],[46,.5]];
function keyed(K,t){for(let i=1;i<K.length;i++)if(t<=K[i][0]){const k=P(t,K[i-1][0],K[i][0]);return lerp(K[i-1][1],K[i][1],eio(k));}return K[K.length-1][1];}
function ridge(t){
 cx.fillStyle='#0A0A0A';cx.fillRect(0,0,W,H);
 const alpha=keyed(RK,t); if(alpha<=0.001)return;
 const rows=40,top=keyed([[0,.16],[6,.16],[7,.3],[40.5,.3],[41.4,.2],[46,.2]],t),y0=H*top,bot=H*1.03,amp=H*.30;
 const hotOn=(t<6.2)?P(t,1.2,3.2):(t>40.9?P(t,41.3,43.3):0), hot=17;
 for(let r=0;r<rows;r++){
  const v=r/(rows-1),base=y0+(bot-y0)*v,k=.35+v*.65;
  const reveal=t<3?eo(P(t,.15+r*.025,1.25+r*.025)):1; if(reveal<=0)continue;
  const xmax=W*reveal;
  cx.beginPath();cx.moveTo(0,base);
  for(let X=0;X<=xmax+6;X+=6)cx.lineTo(Math.min(X,xmax),base-amp*hgt(X/W,v,t)*k);
  cx.lineTo(xmax,H+2);cx.lineTo(0,H+2);cx.closePath();cx.fillStyle='#0A0A0A';cx.fill();
  cx.globalAlpha=alpha*(.22+v*.78);cx.strokeStyle='#F4F4F2';cx.lineWidth=1;cx.stroke();cx.globalAlpha=1;
  if(r===hot&&hotOn>0){cx.beginPath();const hx=W*hotOn;
   for(let X=0;X<=hx;X+=6){const y=base-amp*hgt(X/W,v,t)*k;X?cx.lineTo(X,y):cx.moveTo(X,y);}
   cx.strokeStyle=ACC;cx.lineWidth=2.2;cx.globalAlpha=Math.min(1,alpha*2.2);cx.stroke();cx.globalAlpha=1;}
 }
}

/* ---------- helpers ---------- */
function rings(svg,t0,t){svg.querySelectorAll('.ring').forEach((p,i)=>{const k=eo(P(t,t0+i*.22,t0+i*.22+.9));p.style.strokeDasharray=`${k} 1`;});
 const d=svg.querySelector('.dot');const k=ebk(P(t,t0+.75,t0+1.25));d.style.transformOrigin='70px 56px';d.style.transform=`scale(${cl(k,0,2)})`;}
function rise(el,k){el.style.transform=`translateY(${(1-k)*110}%)`;}
function show(id,o){$(id).style.opacity=o;}

/* ---------- scenes ---------- */
function s1(t){
 const o=win(t,0,6.2,.01,.45); show('s1',o); if(o<=0)return;
 const bm=$('bigmark'),svg=bm.querySelector('svg');rings(svg,.35,t);
 // mark: centre stage, then flies into the nav position
 const fly=eio(P(t,1.85,2.75)),size=lerp(300,64,fly),x=lerp(W/2-150,150,fly),y=lerp(H/2-150-30,94,fly);
 bm.style.transform=`translate(${x}px,${y}px) scale(${size/300})`;
 bm.style.opacity=cl(P(t,.2,.5));
 const nw=$('navword');nw.style.opacity=P(t,2.55,2.95);nw.style.transform=`translateX(${(1-eo(P(t,2.55,3.1)))*-16}px)`;
 $('nav').style.paddingLeft='86px';
 const lines=[...$('s1title').querySelectorAll('.mask>div')];
 lines.forEach((el,i)=>{const a=2.5+i*.14;rise(el,eo(P(t,a,a+.75))*(1-eio(P(t,5.55+i*.06,6.05+i*.06))));});
 const lab=$('s1lab');lab.style.opacity=P(t,2.9,3.4)*(1-P(t,5.5,5.9));
 const sub=$('s1sub');sub.style.opacity=P(t,3.5,4.1)*(1-P(t,5.5,5.9));sub.style.transform=`translateY(${(1-eo(P(t,3.5,4.2)))*18}px)`;
 $('nav').style.opacity=1-P(t,5.6,6.0);
}
function s2(t){
 const [a,b]=S.s2,o=win(t,a,b,.5,.5); show('s2',o); if(o<=0)return;
 const k=eo(P(t,a,a+.7)),out=eio(P(t,b-.55,b));
 $('term').style.transform=`translateY(${(1-k)*70}px) scale(${1-out*.04})`;
 const c1='pip install isoline',c2='isoline scan ACME';
 const prompt='<span style="color:#6E6E6B">~/research $</span> ';
 const caret='<span class="caret"></span>';
 const blink=(Math.floor(t*2.2)%2===0);
 const n1=Math.round(c1.length*P(t,6.9,7.9)),n2=Math.round(c2.length*P(t,8.9,9.8));
 let L=[];
 L.push(prompt+'<span style="color:#fff">'+c1.slice(0,n1)+'</span>'+(t<8.2&&(t<7.9||blink)?caret:''));
 if(t>=8.25)L.push('<span style="color:#A3A3A0">Collecting isoline</span>');
 if(t>=8.6)L.push('Successfully installed <span style="color:#fff">isoline-0.9.0</span>');
 if(t>=8.75)L.push(prompt+'<span style="color:#fff">'+c2.slice(0,n2)+'</span>'+(t<10.05&&(t<9.8||blink)?caret:''));
 const shown=Math.floor(TERM.length*P(t,10.1,13.0));
 for(let i=0;i<shown;i++)L.push(TERM[i]);
 const hl=t>13.15; const VIS=31;
 let view=L.slice(-VIS);
 if(hl){view=view.map(s=>s.indexOf('Beneish')>=0?'<span class="hl" style="color:'+ACC+'">'+s.replace(/color: ?#[0-9a-f]{6}/gi,'color:'+ACC)+'</span>':s);}
 $('tpre').innerHTML=view.join('\n');
}
const SHEET_SCALE=780/940;
const STEPS=[ // [start, offsetCss, highlight box css x,y,w,h]
 [14.9,0,[40,140,860,96]],
 [16.85,300,[40,446,440,212]],
 [18.75,850,[40,1196,860,32]],
 [20.6,1211,[40,2126,860,24]]];
function s3(t){
 const [a,b]=S.s3,o=win(t,a,b,.5,.5); show('s3',o); if(o<=0)return;
 const k=eo(P(t,a,a+.8)),out=eio(P(t,b-.55,b));
 $('sheet').style.transform=`translateX(${(1-k)*160-out*60}px)`;
 $('s3l').style.transform=`translateX(${(1-k)*-40}px)`;
 const h2=$('s3l').querySelector('h2');h2.style.opacity=P(t,a+.15,a+.7);
 let off=0,box=STEPS[0][2],step=0;
 for(let i=0;i<STEPS.length;i++)if(t>=STEPS[i][0])step=i;
 const s=STEPS[step],prev=STEPS[Math.max(0,step-1)],m=eio(P(t,s[0],s[0]+.85));
 off=lerp(prev[1],s[1],m);
 box=s[2].map((v,j)=>lerp(prev[2][j],v,m));
 $('simg').style.transform=`translateY(${-off*SHEET_SCALE}px)`;
 const hb=$('shl');hb.style.left=box[0]*SHEET_SCALE-6+'px';hb.style.top=(box[1]-off)*SHEET_SCALE-6+'px';
 hb.style.width=box[2]*SHEET_SCALE+12+'px';hb.style.height=box[3]*SHEET_SCALE+12+'px';
 hb.style.opacity=P(t,a+1.0,a+1.4)*(1-P(t,b-.7,b-.4));
 [...document.querySelectorAll('.call')].forEach((el,i)=>{el.classList.toggle('on',i===step&&t>=a+.9);
  el.style.opacity=P(t,a+.35+i*.1,a+.75+i*.1);});
}
function s4(t){
 const [a,b]=S.s4,o=win(t,a,b,.45,.5); show('s4',o); if(o<=0)return;
 const cols=['c1','c2','c3'];
 cols.forEach((id,i)=>{const st=a+.35+i*.45,k=eo(P(t,st,st+.7));const el=$(id);
  el.style.opacity=k;el.style.transform=`translateY(${(1-k)*50}px)`;
  el.querySelector('.rule i').style.width=(eio(P(t,st+.3,st+1.3))*100)+'%';});
 const c1=eio(P(t,a+.5,a+1.9));$('n1').textContent=Math.round(9*c1);
 const c2=eio(P(t,a+.95,a+2.35));$('n2').textContent=(3.94*c2).toFixed(2);
 const nn=Math.floor(3*P(t,a+1.6,a+2.0));$('n3').textContent='n/a'.slice(0,nn)||' ';
 const d=$('dcf'),dk=eo(P(t,a+2.6,a+3.2));d.style.opacity=dk;d.style.transform=`translateY(${(1-dk)*30}px)`;
 $('dcfbar').querySelector('i').style.width=(eio(P(t,a+2.8,a+3.9))*100)+'%';
 [['tb',3.1],['tm',3.45],['tu',3.8]].forEach(([id,dl])=>{const k=ebk(P(t,a+dl,a+dl+.55));const e=$(id);
  e.style.opacity=cl(P(t,a+dl,a+dl+.3));e.style.transform=`translateX(-50%) translateY(${(1-cl(k,0,1.2))*24}px)`;});
}
function s5(t){
 const [a,b]=S.s5,o=win(t,a,b,.4,.5); show('s5',o); if(o<=0)return;
 const h=$('s5h'),hk=eo(P(t,a+.1,a+.7));h.style.opacity=hk;h.style.transform=`translateY(${(1-hk)*40}px)`;
 CARDS.forEach((c,i)=>{const st=a+.45+i*.2,k=eo(P(t,st,st+.6)),el=$('card'+i);
  el.style.opacity=k;el.style.transform=`translateY(${(1-k)*60}px)`;
  const n=Math.round(c.cmd.length*P(t,st+.2,st+.2+c.cmd.length*.022));
  el.querySelector('.c').innerHTML='<span>$ </span>'+c.cmd.slice(0,n);
  el.querySelector('.u').style.width=(eio(P(t,st+.4,st+1.1))*100)+'%';
  el.querySelector('.t').style.opacity=P(t,st+.5,st+.9);});
}
let siteIdx=-1;
async function s6(t){
 const [a,b]=S.s6,o=win(t,a,b,.5,.5); show('s6',o); if(o<=0)return;
 const k=eo(P(t,a,a+.8)),out=eio(P(t,b-.6,b));
 $('browser').style.transform=`translateY(${(1-k)*80}px) scale(${lerp(.93,1,k)-out*.05})`;
 const i=Math.max(0,Math.min(SITE.length-1,Math.floor((t-(a+.2))*30)));
 if(i!==siteIdx){siteIdx=i;const img=$('siteimg');img.src=SITE[i];await img.decode();}
}
function s7(t){
 const [a,b]=S.s7,o=win(t,a,b+1,.4,.1); show('s7',o); if(o<=0)return;
 const svg=$('end').querySelector('svg');rings(svg,a+.15,t);
 const wk=eo(P(t,a+.7,a+1.4));const w=$('endword');w.style.opacity=wk;w.style.transform=`translateX(${(1-wk)*-30}px)`;
 const pk=eo(P(t,a+1.3,a+1.9));const p=$('pill');p.style.opacity=pk;p.style.transform=`translateY(${(1-pk)*26}px)`;
 $('links').style.opacity=P(t,a+1.9,a+2.5);$('fine').style.opacity=P(t,a+2.3,a+2.9);
 $('fade').style.opacity=P(t,DUR-.7,DUR);
}
window.render=async function(t){ridge(t);s1(t);s2(t);s3(t);s4(t);s5(t);await s6(t);s7(t);};
window.DUR=DUR;
</script></body></html>"""

CARD_DATA = [
    ("isoline statements ACME", "Four years of statements, as reported"),
    ("isoline compare AAPL MSFT", "Two companies, side by side"),
    ("isoline screen IT", "Screen a sector, with a reason for every skip"),
    ("isoline value ACME", "DCF with every assumption shown"),
    ("isoline scan ACME --export a.xlsx", "Excel, CSV, JSON and Power BI"),
    ("isoline serve", "MCP server for AI coding tools"),
]


def build_page(fonts: Path, report_png: Path, site_dir: Path) -> str:
    cards = []
    for i, (_cmd, text) in enumerate(CARD_DATA):
        x, y = 150 + (i % 3) * 560, 360 + (i // 3) * 276
        cards.append(f'<div class="card" id="card{i}" style="left:{x}px;top:{y}px"><div class="c mono"></div>'
                     f'<div class="u" style="width:0"></div><div class="t">{text}</div></div>')
    term = [re.sub(r"text-decoration-color: ?#[0-9a-f]{6};?", "", line) for line in scan_lines()]
    site = [p.resolve().as_uri() for p in sorted(site_dir.glob("f*.jpg"))]
    return (PAGE.replace("%%FONTS%%", font_faces(fonts))
            .replace("%%ACCENT%%", ACCENT)
            .replace("%%MARK_BIG%%", drawable_mark(300, "mbig"))
            .replace("%%MARK_END%%", drawable_mark(150, "mend"))
            .replace("%%REPORT%%", report_png.resolve().as_uri())
            .replace("%%SITE0%%", site[0])
            .replace("%%CARDS%%", "\n".join(cards))
            .replace("%%TERM%%", json.dumps(term))
            .replace("%%SITEFRAMES%%", json.dumps(site))
            .replace("%%CARDDATA%%", json.dumps([{"cmd": c} for c, _ in CARD_DATA])))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--fonts", type=Path, required=True)
    ap.add_argument("--chrome", default=None, help="Path to a Chrome/Chromium binary (optional).")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--work", type=Path, default=None, help="Keep intermediate files here.")
    ap.add_argument("--preview", type=str, default="", help="Comma-separated seconds: write PNG stills only.")
    a = ap.parse_args()
    if not shutil.which("ffmpeg") and not a.preview:
        sys.exit("ffmpeg is required")

    from playwright.sync_api import sync_playwright

    work = a.work or Path(tempfile.mkdtemp(prefix="isoline-video-"))
    work.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        launch = {"executable_path": a.chrome, "args": ["--headless=new"]} if a.chrome else {}
        browser = p.chromium.launch(**launch)
        site_dir = work / "site"
        if not (site_dir.exists() and len(list(site_dir.glob("f*.jpg"))) == SITE_FRAMES):
            record_site(browser, a.fonts, site_dir)
        report_png = render_report(browser, work)
        page_file = work / "video.html"
        page_file.write_text(build_page(a.fonts, report_png, site_dir), encoding="utf-8")

        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto(page_file.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        duration = page.evaluate("window.DUR")

        if a.preview:
            for s in a.preview.split(","):
                page.evaluate(f"window.render({float(s)})")
                page.screenshot(path=str(a.out.with_name(f"{a.out.stem}_{float(s):05.1f}s.png")))
            browser.close()
            return

        a.out.parent.mkdir(parents=True, exist_ok=True)
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-i", "-",
             "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(a.out)],
            stdin=subprocess.PIPE)
        frames = round(duration * a.fps)
        for f in range(frames):
            page.evaluate(f"window.render({f / a.fps})")
            ff.stdin.write(page.screenshot(type="png"))
            if f % 150 == 0:
                print(f"frame {f}/{frames}", flush=True)
        ff.stdin.close()
        ff.wait()
        browser.close()
    print(f"wrote {a.out} ({frames} frames, {duration:.1f}s)")


if __name__ == "__main__":
    main()
