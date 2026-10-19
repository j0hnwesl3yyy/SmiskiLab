"""Build the REAL series/figure catalog from what the scrapers saved in data/raw/.

Inputs : data/raw/smiski_series_pages.jsonl  (scrapers/smiski_catalog.py)
         data/raw/smiski_news.jsonl          (scrapers/smiski_news.py, optional)
Outputs: data/raw/catalog_series.csv, catalog_figures.csv, catalog_events.csv

What is real vs assumed (also recorded in the CSV columns):
  * series names, figure names, figure descriptions .......... scraped (smiski.com/e/products/*)
  * release order .......................................... the site's product menu is newest-first
  * release_date ........................................... announced launch date in a news post when one
                                                             exists, else the first-of-month of the page's
                                                             earliest image upload (APPROXIMATE, flagged)
  * secret figure .......................................... the site says every series has 6 + 1 secret,
                                                             but never names the secret; we add an unnamed one
  * pull_rate .............................................. ASSUMED: secret = 1/72 (commonly quoted by
                                                             collectors, not published by the maker), the 6
                                                             regular figures share the rest equally
  * retail_usd ............................................. ASSUMED constant 12.99; the site shows no prices
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# Standard blind-box series, in the site's menu order (newest first). Hippers is excluded: it is an
# attachable-figure product with no secret figure, so the "6 + 1 secret" box logic does not apply.
SLUGS_NEWEST_FIRST = ["construction-series", "birthday-series", "sunday-series", "moving-series", "exercising-series",
                      "dressing-series", "work-series", "museumseries", "cheerseries", "yoga-series", "bed-series",
                      "living", "bath-series", "toilet-series", "series-4", "series-3", "series-2", "series-1"]
THEME_OVERRIDE = {"series-1": "Original", "series-2": "Original", "series-3": "Original", "series-4": "Original"}
SECRET_RATE, RETAIL_ASSUMED = 1 / 72, 12.99
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
END_PUNCT = (".", "?", "!", "…", "。")
NAME = re.compile(r"\bsmiski\b", re.I)
META = re.compile(r"^(body type|pose|found)\s*:", re.I)


def clean_theme(title: str, slug: str) -> str:
    if slug in THEME_OVERRIDE:
        return THEME_OVERRIDE[slug]
    t = re.sub(r"\bseries\b", "", title, flags=re.I).strip()
    t = re.sub(r"^@", "", t)
    return t.title() if t.isupper() else t


def parse_figures(text: str) -> list[dict]:
    lines = [l.strip() for l in text.split("\n")]
    start = next((i for i, l in enumerate(lines) if l.startswith("/ SMISKI")), None)
    if start is None:
        return []
    out, cur = [], None
    for l in lines[start + 1:]:
        if l.startswith(("Each series has", "Smiski come packaged", "*The secret", "©", "What is")):
            break
        if not l or l == "無題ドキュメント":
            continue
        is_name = bool(NAME.search(l)) and not l.endswith(END_PUNCT) and len(l.split()) <= 6 and not META.match(l)
        if is_name:
            nm = re.sub(r"\s+", " ", NAME.sub("", l)).strip()          # "Little SMISKI Teamwork" -> "Little Teamwork"
            cur = dict(name=nm[:1].upper() + nm[1:], description="")
            out.append(cur)
        elif cur is not None and not META.match(l) and not cur["description"]:
            cur["description"] = l
    return out


NOT_A_SERIES = re.compile(r"strap|capsule|embroidery|plush|zipper|hippers|stamp|bath ball|touch light|key ?chain|pouch|rainbomb|bobbing|store|shop|anniversary", re.I)
RELEASE = re.compile(r"releas|releac|launch|available|arriv|will be", re.I)
EXPLICIT = re.compile(r"(?:launch(?:es|ing|ed)?|releas(?:e|es|ed|ing)|available)[^.]{0,60}?([A-Z][a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?")


def launch_date_from_news(theme: str, news: list[dict], approx: pd.Timestamp | None) -> tuple[pd.Timestamp | None, str | None, str]:
    """Earliest release-type news item whose HEADLINE names the series (accessories/stores excluded).

    The date is the explicit 'Month Day' in the text when present, else the publish date. A match is only
    accepted if it agrees (within ~5 months) with the independent image-upload month, which guards against
    headlines that merely mention a series in passing."""
    if theme == "Original":
        return None, None, ""
    name = re.compile(rf"smiski\s*[\"'「『“]?\s*@?\s*{re.escape(theme)}\b", re.I)
    for n in sorted(news, key=lambda r: r["published"]):
        h = n["headline"]
        if not name.search(h) or NOT_A_SERIES.search(h) or not RELEASE.search(h + " " + n["summary"][:200]):
            continue
        pub = pd.Timestamp(n["published"]); date, how = pub, "news_publish_date"
        m = EXPLICIT.search(h + " " + n["summary"])
        if m and MONTHS.get(m.group(1).lower()):
            mon = MONTHS[m.group(1).lower()]
            try:
                d = pd.Timestamp(year=int(m.group(3)) if m.group(3) else pub.year + (1 if mon < pub.month - 1 else 0), month=mon, day=int(m.group(2)))
                if abs((d - pub).days) <= 120:
                    date, how = d, "news_announced_launch"
            except ValueError:
                pass
        if approx is not None and abs((date - approx).days) > 150:
            continue
        return date, n["url"], how
    return None, None, ""


def main() -> None:
    pages = {json.loads(l)["slug"]: json.loads(l) for l in (RAW / "smiski_series_pages.jsonl").read_text().splitlines()}
    news_f = RAW / "smiski_news.jsonl"
    news = [json.loads(l) for l in news_f.read_text().splitlines()] if news_f.exists() else []
    print(f"{len(pages)} product pages, {len(news)} news items")

    rows = []
    for slug in SLUGS_NEWEST_FIRST:
        p = pages[slug]
        theme = clean_theme(p["title"], slug)
        figs = parse_figures(p["text"])
        months = [m for m in p["upload_months"]]
        d_img = pd.Timestamp(months[0] + "-01") if months else None
        d_news, url, how = launch_date_from_news(theme, news, d_img)
        if d_news is not None:
            date, src = d_news, how
        elif d_img is not None:
            date, src = d_img, "page_image_upload_month (approx.)"
        else:
            date, src = None, "unknown"
        rows.append(dict(slug=slug, theme=theme, title=p["title"], release_date=date, release_date_source=src, news_url=url,
                         figures=figs, page_url=p["url"]))

    # chronological ids: menu is newest-first, so reverse; stable sort by date keeps menu order for ties
    rows = list(reversed(rows))
    rows.sort(key=lambda r: (r["release_date"] is None, r["release_date"]))
    series, figures = [], []
    for i, r in enumerate(rows, 1):
        sid = f"S{i:02d}"
        name = f"{r['theme']} Series" if r["theme"] != "Original" else r["title"]
        series.append(dict(series_id=sid, series_name=name, theme=r["theme"], slug=r["slug"], release_date=r["release_date"],
                           release_date_source=r["release_date_source"], collab=0, retail_usd=RETAIL_ASSUMED,
                           retail_source="assumed", n_figures=len(r["figures"]) + 1, source="smiski.com/e", page_url=r["page_url"]))
        n_reg = len(r["figures"])
        for j, f in enumerate(r["figures"], 1):
            figures.append(dict(figure_id=f"{sid}-{j:02d}", series_id=sid, series_name=name, theme=r["theme"], figure_name=f["name"],
                                description=f["description"], rarity_tier="common", pull_rate=round((1 - SECRET_RATE) / n_reg, 4),
                                glow=0, collab=0, retail_usd=RETAIL_ASSUMED, release_date=r["release_date"], source="smiski.com/e"))
        figures.append(dict(figure_id=f"{sid}-{n_reg + 1:02d}", series_id=sid, series_name=name, theme=r["theme"], figure_name="Secret",
                            description="Unnamed on the official site; 'rare to find' in the box.", rarity_tier="secret",
                            pull_rate=round(SECRET_RATE, 4), glow=0, collab=0, retail_usd=RETAIL_ASSUMED,
                            release_date=r["release_date"], source="smiski.com/e (secret figure not named)"))
    s, f = pd.DataFrame(series), pd.DataFrame(figures)

    # events: store openings, collabs, launches pulled from real news headlines
    ev = []
    for n in news:
        h = n["headline"]
        typ = ("store_launch" if re.search(r"\b(store|shop|pop-?up|opening|opens?)\b", h, re.I)
               else "collab" if re.search(r"collab|x\s|×", h, re.I) else "product" if re.search(r"launch|release|series|vol", h, re.I) else "other")
        ev.append(dict(date=n["published"], type=typ, label=h[:140], url=n["url"]))
    for r in series:
        if pd.notna(r["release_date"]):
            ev.append(dict(date=r["release_date"].strftime("%Y-%m-%d"), type="series_launch", label="Launch: " + r["series_name"], url=r["page_url"]))
    e = pd.DataFrame(ev).sort_values("date") if ev else pd.DataFrame(columns=["date", "type", "label", "url"])

    s.to_csv(RAW / "catalog_series.csv", index=False)
    f.to_csv(RAW / "catalog_figures.csv", index=False)
    e.to_csv(RAW / "catalog_events.csv", index=False)
    pd.set_option("display.width", 200); pd.set_option("display.max_colwidth", 40)
    print(s[["series_id", "series_name", "release_date", "release_date_source", "n_figures"]].to_string(index=False))
    print(Counter(f.groupby("series_id").size()))
    print(f"events: {len(e)}  types: {dict(Counter(e['type']))}")


if __name__ == "__main__":
    main()
