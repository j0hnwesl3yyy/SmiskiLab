"""Crawl the official Smiski English site for product / series pages.

Image *URLs* are recorded for reference only; images are never downloaded or
republished (the website uses original placeholder art).

NOTE: CSS selectors / URL patterns are generic and UNVERIFIED against the live
site (it could not be reached when this was written). Inspect
data/raw/smiski_pages.jsonl after the first run and adjust KEYWORDS if needed.
"""
from __future__ import annotations

import re
from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from common import RAW, Blocked, get, write_jsonl

START = "https://www.smiski.com/e/"
KEYWORDS = ("series", "product", "lineup", "item", "news", "store", "shop")
MAX_PAGES = 120
PRICE = re.compile(r"(?:US\$|\$|¥|JPY|USD)\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)")


def parse(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    meta = lambda p: (soup.find("meta", property=p) or {}).get("content")
    text = soup.get_text(" ", strip=True)
    return dict(
        url=url,
        title=(soup.title.string.strip() if soup.title and soup.title.string else None),
        og_title=meta("og:title"),
        og_description=meta("og:description"),
        og_image_url=meta("og:image"),
        headings=[h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])][:30],
        prices=PRICE.findall(text)[:10],
        text_excerpt=text[:3000],
    )


def crawl() -> list[dict]:
    seen, out, queue = set(), [], deque([START])
    while queue and len(out) < MAX_PAGES:
        url = queue.popleft().split("#")[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            html = get(url)
        except Blocked as e:
            print(f"BLOCKED: {e}")
            break
        html = html if isinstance(html, str) else html.text
        out.append(parse(url, html))
        for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
            nxt = urljoin(url, a["href"])
            p = urlparse(nxt)
            if p.netloc.endswith("smiski.com") and p.path.startswith("/e/") \
                    and any(k in p.path.lower() for k in KEYWORDS) and nxt not in seen:
                queue.append(nxt)
    return out


if __name__ == "__main__":
    pages = crawl()
    if pages:
        write_jsonl(RAW / "smiski_pages.jsonl", pages)
    else:
        print("no pages fetched (network blocked?)")
