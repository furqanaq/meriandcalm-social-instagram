#!/usr/bin/env python3
"""Carousel that mixes brand text slides with real page previews from a guide PDF.

Usage: python3 tools/make_page_carousel.py spec.json key=/path/to/guide.pdf [key2=/path/other.pdf]
The PDFs themselves are never stored in this repo; only the rendered preview slides are.

spec.json:
{"date": "2026-11-12", "slug": "post-c-...", "kicker": "INSIDE THE GUIDE",
 "slides": [{"title": "...", "body": "..."},                                  # brand text slide
            {"pdf": "key", "page": 4, "kicker": "CHAPTER 1", "caption": "..."}]} # page preview slide
Output: posts/<date>-<slug>/slide-N.jpg (1080x1350).
"""
import base64, json, os, subprocess, sys, tempfile, html
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_media import feed_html, shoot, MOON, ROOT  # noqa: E402

PAGE_CSS = """
*{margin:0;padding:0;box-sizing:border-box} body{font-family:Inter,sans-serif}
.pg{width:1080px;height:1350px;position:relative;background:linear-gradient(180deg,#F7F1E6,#EFE4D0)}
.pg .k{position:absolute;top:70px;left:96px;color:#B8740A;font-weight:700;font-size:34px;letter-spacing:1px;text-transform:uppercase}
.pg .n{position:absolute;top:74px;right:96px;color:#44506B;font-size:30px}
.pg img{position:absolute;top:140px;left:50%;transform:translateX(-50%) rotate(-1deg);height:1000px;
 border-radius:6px;box-shadow:0 18px 50px rgba(20,32,74,.22),0 2px 8px rgba(20,32,74,.12)}
.pg .c{position:absolute;bottom:84px;left:96px;right:290px;color:#14204A;font-weight:700;font-size:34px;line-height:1.25}
.pg .h{position:absolute;bottom:92px;right:96px;color:#44506B;font-size:28px}
"""

def render_page(pdf, page, tmp):
    base = os.path.join(tmp, f"{os.path.basename(pdf)}-{page}")
    subprocess.run(["pdftoppm", "-q", "-r", "130", "-jpeg", "-jpegopt", "quality=92", "-singlefile",
                    "-f", str(page), "-l", str(page), pdf, base], check=True)
    return base + ".jpg"

def page_html(img, kicker, caption, i, n):
    b64 = base64.b64encode(open(img, "rb").read()).decode()
    return (f'<style>{PAGE_CSS}</style><div class="pg"><div class="k">{html.escape(kicker)}</div>'
            f'<div class="n">{i}/{n}</div><img src="data:image/jpeg;base64,{b64}">'
            f'<div class="c">{html.escape(caption or "")}</div><div class="h">@periandcalm</div></div>')

def main(spec_path, pdf_args):
    pdfs = dict(a.split("=", 1) for a in pdf_args)
    s = json.load(open(spec_path))
    folder = os.path.join(ROOT, "posts", f"{s['date']}-{s['slug']}"); os.makedirs(folder, exist_ok=True)
    n = len(s["slides"]); tmp = tempfile.mkdtemp(); out = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        for i, sl in enumerate(s["slides"], 1):
            fp = os.path.join(folder, f"slide-{i}.jpg")
            if "pdf" in sl:
                img = render_page(pdfs[sl["pdf"]], sl["page"], tmp)
                shoot(pg, page_html(img, sl.get("kicker", s["kicker"]), sl.get("caption"), i, n), fp, 1080, 1350)
            else:
                shoot(pg, feed_html(sl.get("kicker", s["kicker"]), sl["title"], sl.get("body", ""), i, n), fp, 1080, 1350)
            out.append(fp)
        b.close()
    print("\n".join(os.path.relpath(x, ROOT) for x in out))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
