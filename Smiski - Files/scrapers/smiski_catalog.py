"""Scrape the real series / figure catalog from the official English site (smiski.com/e/).

robots.txt (checked by common.get) only disallows /wp-admin/. We fetch each product page once, cached,
2s apart. Image URLs are recorded for reference only; images are never downloaded or republished.
Output: data/raw/smiski_series_pages.jsonl  (one row per product page)
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from common import RAW, Blocked, get, write_jsonl

BASE = "https://smiski.com/e/"
SKIP_ALT = re.compile(r"(_top|_bottom|bottom_|icon|logo|banner)", re.I)


def text_of(url: str) -> str:
    r = get(url)
    return r if isinstance(r, str) else r.text


def product_links() -> list[str]:
    soup = BeautifulSoup(text_of(BASE + "products/"), "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        h = a["href"].split("#")[0]
        if h.startswith(BASE + "products/") and h.rstrip("/") != (BASE + "products").rstrip("/") and h not in out:
            out.append(h)
    return out


def parse_page(url: str) -> dict:
    soup = BeautifulSoup(text_of(url), "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    title = (soup.title.string or "").split(" - ")[0].strip() if soup.title else ""
    full = soup.get_text("\n", strip=True)
    figs = []
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        src = img.get("src") or img.get("data-src") or ""
        if not alt or SKIP_ALT.search(alt) or SKIP_ALT.search(src.rsplit("/", 1)[-1]) or "uploads" not in src:
            continue
        # description = the text node that follows the figure name in the page text
        desc = ""
        m = re.search(re.escape(alt) + r"\n([^\n]+)", full)
        if m and not m.group(1).upper().startswith("SMISKI") or (m and "SMISKI" in m.group(1) and len(m.group(1)) > 40):
            desc = m.group(1)
        figs.append(dict(name=alt, description=desc, image_url=src))
    # WordPress stores media under /uploads/YYYY/MM/: product-image months approximate when the page first went live
    months = sorted({"-".join(m) for img in soup.find_all("img")
                     for m in re.findall(r"/uploads/(\d{4})/(\d{2})/", img.get("src") or "")
                     if not re.search(r"(logo|icon|bottom|banner)", (img.get("src") or "").rsplit("/", 1)[-1], re.I)})
    return dict(url=url, slug=url.rstrip("/").rsplit("/", 1)[-1], title=title, text=full, upload_months=months,
                says_blind_box="blind box" in full.lower(), says_secret="secret" in full.lower(),
                variations_text=next((l for l in full.split("\n") if "variations" in l.lower()), ""),
                figures=figs, text_excerpt=full[:1500])


if __name__ == "__main__":
    try:
        links = product_links()
    except Blocked as e:
        raise SystemExit(f"BLOCKED: {e}")
    print(f"{len(links)} product pages")
    rows = []
    for u in links:
        try:
            rows.append(parse_page(u))
        except Blocked as e:
            print("BLOCKED", e); break
    write_jsonl(RAW / "smiski_series_pages.jsonl", rows)
