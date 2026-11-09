#!/usr/bin/env python3
"""Peri & Calm media generator: carousel slides, story image, and reel (MP4) in the brand style.

Usage: python3 tools/make_media.py spec.json
spec.json:
{
  "date": "2026-11-10",
  "carousel": {"slug": "post-a-...", "kicker": "AFTER A BROKEN NIGHT",
               "slides": [{"title": "...", "body": "..."}, ...]},
  "story":    {"slug": "...", "kicker": "THIS MORNING", "title": "...", "body": "..."},
  "reel":     {"slug": "reel-a-...", "frames": [{"kicker": "...", "title": "...", "body": "..."}, ...]}
}
Outputs go to posts/<date>-<carousel.slug>/slide-N.jpg, stories/<date>-story-<slug>.jpg,
reels/<date>-<reel.slug>.mp4 (+ -cover.png).

Brand (taken from the October assets):
- Feed: warm cream gradient (#F7F1E6 to #EFE4D0), navy headline #14204A (Inter Bold),
  slate body #44506B, amber kicker/accent #B8740A, amber moon #F2A516, 1080x1350.
- Story/Reel: navy gradient (#1A2550 to #22306B), white headline, amber kicker and moon, 1080x1920.
- Footer handle "@periandcalm"; feed slides show "n/N" and "Swipe →" on slide 1.
"""
import json, os, subprocess, sys, tempfile, html
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOON = ('<svg width="{s}" height="{s}" viewBox="0 0 100 100"><path d="M62 8a44 44 0 1 0 30 70 '
        '38 38 0 1 1-30-70z" fill="#F2A516"/></svg>')

CSS = """
*{margin:0;padding:0;box-sizing:border-box} body{font-family:Inter,sans-serif}
.feed{width:1080px;height:1350px;padding:110px 96px;position:relative;
 background:linear-gradient(180deg,#F7F1E6,#EFE4D0)}
.feed .k{color:#B8740A;font-weight:700;font-size:38px;letter-spacing:1px;text-transform:uppercase}
.feed .n{position:absolute;top:118px;right:96px;color:#44506B;font-size:32px}
.feed h1{color:#14204A;font-weight:800;font-size:{TS}px;line-height:1.12;margin-top:44px}
.feed .bar{width:120px;height:8px;background:#B8740A;margin:48px 0 44px}
.feed p{color:#44506B;font-size:44px;line-height:1.45;white-space:pre-line}
.feed .sw{position:absolute;bottom:100px;left:96px;color:#B8740A;font-size:34px;font-weight:600}
.feed .h{position:absolute;bottom:100px;right:96px;color:#44506B;font-size:34px}
.feed .m{position:absolute;bottom:170px;right:96px}
.tall{width:1080px;height:1920px;padding:0 110px;display:flex;flex-direction:column;
 align-items:center;justify-content:center;text-align:center;position:relative;
 background:linear-gradient(180deg,#1A2550,#22306B)}
.tall .k{color:#F2A516;font-weight:700;font-size:44px;letter-spacing:1px;margin-top:70px;text-transform:uppercase}
.tall h1{color:#fff;font-weight:800;font-size:{TT}px;line-height:1.15;margin-top:36px}
.tall p{color:#C9D0E6;font-size:46px;line-height:1.45;margin-top:40px;white-space:pre-line}
.tall .h{position:absolute;bottom:230px;color:#C9D0E6;font-size:38px}
"""

def esc(s): return html.escape(s or "")

def feed_html(kicker, title, body, i, n):
    ts = 96 if len(title) < 40 else 80 if len(title) < 70 else 66
    return (f'<style>{CSS.replace("{TS}", str(ts)).replace("{TT}", "96")}</style><div class="feed">'
            f'<div class="k">{esc(kicker)}</div><div class="n">{i}/{n}</div><h1>{esc(title)}</h1>'
            f'<div class="bar"></div><p>{esc(body)}</p>'
            + ('<div class="sw">Swipe →</div>' if i == 1 else '')
            + f'<div class="m">{MOON.format(s=110)}</div><div class="h">@periandcalm</div></div>')

def tall_html(kicker, title, body):
    tt = 104 if len(title) < 40 else 88 if len(title) < 70 else 72
    return (f'<style>{CSS.replace("{TS}", "96").replace("{TT}", str(tt))}</style><div class="tall">'
            f'{MOON.format(s=230)}<div class="k">{esc(kicker)}</div><h1>{esc(title)}</h1>'
            f'<p>{esc(body)}</p><div class="h">@periandcalm</div></div>')

def shoot(page, markup, path, w, h, fmt="jpeg"):
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(f"<html><body>{markup}</body></html>")
    page.wait_for_timeout(150)
    kw = {"quality": 92} if fmt == "jpeg" else {}
    page.screenshot(path=path, type=fmt, clip={"x": 0, "y": 0, "width": w, "height": h}, **kw)

def make_reel(frames_png, out_mp4, secs=3.6):
    """Slideshow with gentle crossfades and a soft original ambient pad (generated, royalty-free)."""
    n = len(frames_png); total = secs * n
    inputs = []
    for f in frames_png: inputs += ["-loop", "1", "-t", str(secs + 0.6), "-i", f]
    fc, last = [], "0:v"
    for i in range(1, n):
        off = secs * i - 0.3 * i
        fc.append(f"[{last}][{i}:v]xfade=transition=fade:duration=0.6:offset={off:.2f}[v{i}]")
        last = f"v{i}"
    dur = secs * n - 0.3 * (n - 1)
    pad = ("aevalsrc='0.06*sin(2*PI*220*t)+0.05*sin(2*PI*277.18*t)+0.04*sin(2*PI*329.63*t)"
           "+0.03*sin(2*PI*440*t)*(0.5+0.5*sin(2*PI*0.2*t))':s=44100:d=" + f"{dur:.2f}")
    vf = ";".join(fc) + (";" if fc else "") + f"[{last}]format=yuv420p,scale=1080:1920[vout]"
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + inputs + ["-f", "lavfi", "-i", pad,
           "-filter_complex", vf + f";[{n}:a]afade=t=in:d=1,afade=t=out:st={dur-1.2:.2f}:d=1.2[aout]",
           "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-r", "30", "-c:a", "aac",
           "-t", f"{dur:.2f}", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)

def main(spec_path):
    s = json.load(open(spec_path)); d = s["date"]; out = []
    with sync_playwright() as p:
        b = p.chromium.launch(); page = b.new_page()
        if c := s.get("carousel"):
            folder = os.path.join(ROOT, "posts", f"{d}-{c['slug']}"); os.makedirs(folder, exist_ok=True)
            n = len(c["slides"])
            for i, sl in enumerate(c["slides"], 1):
                fp = os.path.join(folder, f"slide-{i}.jpg")
                shoot(page, feed_html(sl.get("kicker", c["kicker"]), sl["title"], sl.get("body", ""), i, n), fp, 1080, 1350)
                out.append(fp)
        if st := s.get("story"):
            fp = os.path.join(ROOT, "stories", f"{d}-story-{st['slug']}.jpg"); os.makedirs(os.path.dirname(fp), exist_ok=True)
            shoot(page, tall_html(st["kicker"], st["title"], st.get("body", "")), fp, 1080, 1920); out.append(fp)
        if r := s.get("reel"):
            tmp = tempfile.mkdtemp(); pngs = []
            for i, fr in enumerate(r["frames"]):
                fp = os.path.join(tmp, f"f{i}.png"); shoot(page, tall_html(fr["kicker"], fr["title"], fr.get("body", "")), fp, 1080, 1920, "png"); pngs.append(fp)
            os.makedirs(os.path.join(ROOT, "reels"), exist_ok=True)
            mp4 = os.path.join(ROOT, "reels", f"{d}-{r['slug']}.mp4"); make_reel(pngs, mp4)
            cover = mp4.replace(".mp4", "-cover.png"); os.replace(pngs[0], cover); out += [mp4, cover]
        b.close()
    print("\n".join(os.path.relpath(x, ROOT) for x in out))

if __name__ == "__main__":
    main(sys.argv[1])
