#!/usr/bin/env python3
"""Fetch every URL in a product's links.txt and cache the text.

    python scripts/fetch_lp.py acme-serum
    python scripts/fetch_lp.py acme-serum --force

Output goes to _derived/pages.md. Pages may be in any language — the prompts
read the source language and produce English.

Called automatically by run.py. Run it with --force after a landing page
changes.
"""

import argparse
import html
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def strip_html(html_src: str) -> str:
    """Crude but dependency-free. Good enough for landing page copy — nav,
    footer and script noise mostly falls out with the tags."""
    html_src = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html_src)
    html_src = re.sub(r"(?is)<(header|footer|nav)[^>]*>.*?</\1>", " ", html_src)
    html_src = re.sub(r"(?i)<br\s*/?>", "\n", html_src)
    html_src = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|section)>", "\n", html_src)
    text = re.sub(r"(?s)<[^>]+>", " ", html_src)
    # Full entity table — a hand-rolled list mangles Nordic and German pages
    # (&aring;, &ouml;, &szlig; …), which is most of your market.
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln.strip()) for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def read_links(product_dir: Path) -> list[str]:
    f = product_dir / "links.txt"
    if not f.exists():
        raise SystemExit(
            f"No links.txt in {product_dir}\n"
            f"Create it with the landing page URL, one per line.")
    urls = []
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "example.com" in line:
            continue                      # template placeholder
        if not line.startswith("http"):
            print(f"  ! skipping line that isn't a URL: {line[:60]}")
            continue
        urls.append(line)
    if not urls:
        raise SystemExit(
            f"links.txt in {product_dir.name} has no real URLs in it.\n"
            f"Paste the landing page URL and delete the example lines.")
    return urls


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "*"})
    with urlopen(req, timeout=30) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    return strip_html(raw.decode(charset, errors="replace"))


def run(slug: str, force: bool = False, products_root: Path | None = None):
    pdir = (products_root or ROOT / "products") / slug
    out = pdir / "_derived" / "pages.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.exists() and out.stat().st_size > 500 and not force:
        print(f"  cached: {out.name}")
        return

    chunks = []
    for url in read_links(pdir):
        try:
            text = fetch(url)
        except Exception as e:
            print(f"  ! failed to fetch {url}: {e}")
            chunks.append(f"# SOURCE: {url}\n\n(fetch failed: {e})\n")
            continue
        if len(text) < 400:
            print(f"  ! {url} returned very little text ({len(text)} chars) — "
                  f"likely JavaScript-rendered. Paste it into notes.md instead.")
        else:
            print(f"  fetched {url} ({len(text):,} chars)")
        chunks.append(f"# SOURCE: {url}\n\n{text}\n")

    out.write_text("\n\n---\n\n".join(chunks), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(a.product, a.force)
