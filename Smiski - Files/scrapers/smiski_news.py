"""Scrape the official English news archive (smiski.com/e/news/) for launch announcements and store events.

Each item: headline, publish date (site shows DD/MM/YYYY), summary, link. Launch dates inside headlines
("... launches Thursday, July 9th") are extracted later in build_catalog.py.
Output: data/raw/smiski_news.jsonl
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup
from requests import HTTPError

from common import RAW, Blocked, get, write_jsonl

URL = "https://smiski.com/e/news/"
DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    links = [a["href"] for a in soup.find_all("a", href=True) if a.get_text(strip=True).lower().startswith("read more")]
    lines = [l for l in soup.get_text("\n", strip=True).split("\n")]
    items, cur = [], []
    for l in lines:
        if l.lower().startswith("read more"):
            items.append(cur); cur = []
        else:
            cur.append(l)
    out = []
    for chunk, link in zip(items, links):
        # chunk ends with: headline..., "By", author, "|", date, summary
        try:
            by = max(i for i, l in enumerate(chunk) if l == "By")
        except ValueError:
            continue
        date_line = next((l for l in chunk[by:] if DATE.match(l)), None)
        if not date_line:
            continue
        headline = " ".join(chunk[max(0, by - 1):by]).strip()
        summary = " ".join(chunk[chunk.index(date_line) + 1:]).strip()
        out.append(dict(url=link, headline=headline, published=datetime.strptime(date_line, "%d/%m/%Y").date().isoformat(), summary=summary))
    return out


def sitemap_urls() -> list[str]:
    """English news post URLs from the XML sitemaps (the listing's pagination is broken)."""
    idx = get("https://smiski.com/sitemap.xml")
    idx = idx if isinstance(idx, str) else idx.text
    posts = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "sitemap-pt-post" in u]
    out = []
    for sm in posts:
        r = get(sm)
        # the sitemap lists the Japanese site (smiski.com/news/X/); English posts live at smiski.com/e/news/X/
        out += [u.replace("smiski.com/news/", "smiski.com/e/news/") for u in re.findall(r"<loc>([^<]+)</loc>", r if isinstance(r, str) else r.text) if "smiski.com/news/" in u]
    return list(dict.fromkeys(out))


def parse_post(url: str, html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    lines = soup.get_text("\n", strip=True).split("\n")
    date_i = next((i for i, l in enumerate(lines) if DATE.match(l)), None)
    h1 = soup.find("h1") or soup.find("h2")
    title = (soup.title.string or "").split(" - ")[0].strip() if soup.title and soup.title.string else ""
    if date_i is None:
        return None
    body = " ".join(lines[date_i + 1:date_i + 12])
    return dict(url=url, headline=title, published=datetime.strptime(lines[date_i], "%d/%m/%Y").date().isoformat(), summary=body[:900])


if __name__ == "__main__":
    try:
        urls = sitemap_urls()
    except Blocked as e:
        raise SystemExit(f"BLOCKED: {e}")
    print(f"{len(urls)} English news posts in sitemaps")
    rows = []
    for u in urls:
        try:
            r = get(u)
        except HTTPError:
            continue          # no English translation for this post
        row = parse_post(u, r if isinstance(r, str) else r.text)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["published"])
    write_jsonl(RAW / "smiski_news.jsonl", rows)
    if rows:
        print(f"{len(rows)} news items, {rows[0]['published']} .. {rows[-1]['published']}")
