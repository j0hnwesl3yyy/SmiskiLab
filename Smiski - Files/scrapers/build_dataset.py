"""Turn whatever exists in data/raw/ into data/processed/*.csv.

Per-table provenance is written to data/processed/DATA_SOURCE.json. Any table
without usable raw input keeps its simulated seed version and is labelled so.

Raw inputs recognised:
  catalog_series.csv / catalog_figures.csv / catalog_events.csv   (scrapers/build_catalog.py)
                                                     -> series.csv, figures.csv, events.csv  (REAL, with flagged assumptions)
  google_trends.csv      (Google export or pytrends output)  -> trends.csv
  reddit_posts.jsonl     (scrapers/reddit_api.py)            -> reddit.csv
  resale_listings.csv    (YOUR data: figure_id,snapshot_date,median_sold_usd,n_sold)
                                                             -> resale.csv
smiski_pages.jsonl / wikipedia_smiski.json are enriched text sources for the
notebooks; building series.csv/figures.csv from them needs manual review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smiskis import seed  # noqa: E402
from smiskis.paths import PROCESSED, RAW  # noqa: E402

TABLES = ["series", "figures", "resale", "trends", "events", "reddit"]


def load_trends() -> pd.DataFrame | None:
    f = RAW / "google_trends.csv"
    if not f.exists():
        return None
    skip = 1 if f.read_text().startswith("Category") else 0   # Google export has a banner line
    df = pd.read_csv(f, skiprows=skip)
    df = df.iloc[:, :2]
    df.columns = ["week", "interest"]
    df["interest"] = pd.to_numeric(df["interest"].astype(str).str.replace("<1", "0"), errors="coerce")
    df["week"] = pd.to_datetime(df["week"])
    df["keyword"] = "smiski"
    return df.dropna()


def load_catalog():
    sf, ff = RAW / "catalog_series.csv", RAW / "catalog_figures.csv"
    if not (sf.exists() and ff.exists()):
        return None
    series = pd.read_csv(sf, parse_dates=["release_date"]).dropna(subset=["release_date"])
    figs = pd.read_csv(ff, parse_dates=["release_date"])
    figs = figs[figs.series_id.isin(series.series_id)]
    return series, figs


def load_events():
    f = RAW / "catalog_events.csv"
    if not f.exists():
        return None
    ev = pd.read_csv(f, parse_dates=["date"])
    ev = ev[ev["type"] != "other"]                      # drop trivia; keep launches, stores, collabs, products
    return ev[["date", "type", "label"]].sort_values("date").reset_index(drop=True)


def load_reddit() -> pd.DataFrame | None:
    f = RAW / "reddit_posts.jsonl"
    if not f.exists():
        return None
    df = pd.read_json(f, lines=True)
    df["created"] = pd.to_datetime(df["created_utc"], unit="s").dt.normalize()
    return df[["post_id", "created", "subreddit", "title", "body", "score", "num_comments"]]


def load_resale(figures: pd.DataFrame) -> pd.DataFrame | None:
    f = RAW / "resale_listings.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, parse_dates=["snapshot_date"])
    m = df.merge(figures[["figure_id", "retail_usd", "release_date"]], on="figure_id")
    m["release_date"] = pd.to_datetime(m["release_date"])
    m["months_since_launch"] = ((m["snapshot_date"] - m["release_date"]).dt.days / 30.44).round(2)
    m["premium_pct"] = ((m["median_sold_usd"] / m["retail_usd"] - 1) * 100).round(2)
    return m[["figure_id", "snapshot_date", "months_since_launch", "median_sold_usd", "premium_pct", "n_sold"]]


def main() -> None:
    catalog, trends, events = load_catalog(), load_trends(), load_events()
    prov = {t: "simulated" for t in TABLES}
    if catalog is not None:
        prov["series"] = prov["figures"] = "scraped"
    if trends is not None and len(trends):
        prov["trends"] = "scraped"
    else:
        trends = None
    if events is not None and len(events):
        prov["events"] = "scraped"
    else:
        events = None
    # real tables are kept as-is; anything missing (always resale + reddit unless supplied) is simulated on top of them
    tables = seed.build(write=False, catalog=catalog, trends=trends, events=events)
    real = load_reddit()
    if real is not None and len(real):
        tables["reddit"], prov["reddit"] = real, "scraped"
    real = load_resale(tables["figures"])
    if real is not None and len(real):
        tables["resale"], prov["resale"] = real, "user_supplied"
    for k, v in tables.items():
        v.to_csv(PROCESSED / f"{k}.csv", index=False)
    meta = {"tables": prov}
    if catalog is not None:
        meta["assumptions"] = [
            "pull_rate: secret figure = 1/72 (collector folklore, not published by the maker); the 6 regular figures share the rest equally",
            "retail_usd: assumed constant 12.99 (the official site shows no prices)",
            "release_date: news-announced launch date when found, otherwise the first of the month the series page's images were uploaded (approximate)",
            "secret figures are not named on the official site, so each series has one unnamed 'Secret'",
            "collab: no collab series identified, so the flag is 0 everywhere",
            "Hippers excluded: attachable figures with no secret, not a standard blind-box series",
        ]
    if prov["trends"] == "scraped":
        meta["trends_note"] = "Google Trends, worldwide, weekly; two windows stitched by overlap rescaling. 2018-2020 values are tiny and noisy."
    (PROCESSED / "DATA_SOURCE.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(prov, indent=2))


if __name__ == "__main__":
    main()
