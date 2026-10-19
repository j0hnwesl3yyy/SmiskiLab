"""Download the official product images for each figure and resize them for the site.

PERSONAL / LOCAL USE. The images are Dreams Inc.'s artwork. They are saved under site/img/figures/ which is
git-ignored by default, so they are not committed or published unless you decide to. The site falls back to
original placeholder sprites for any figure without a file.

Mapping (verified against filenames such as carrying-ladder.png, awadateski.png = Bath "Shampooing"):
  the first six content images on a series page, in page order, are its six figures in the order the
  page lists them. Secret figures get no image (the site only shows a "?" graphic for them).
Run after build_catalog.py:   python scrapers/smiski_images.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, RAW, ROOT, Blocked, get, get_bytes  # noqa: E402

OUT = ROOT / "site" / "img" / "figures"
MAX_H = 360
SKIP = re.compile(r"logo|icon|bottom|banner|top|blindbox|_img|chibi_eng|image\.png", re.I)


def page_images(url: str) -> list[tuple[str, str]]:
    html = get(url)
    soup = BeautifulSoup(html if isinstance(html, str) else html.text, "lxml")
    out = []
    for i in soup.find_all("img"):
        src = i.get("src") or i.get("data-src") or ""
        fn = src.rsplit("/", 1)[-1]
        if "uploads" in src and not SKIP.search(fn) or "secret" in fn.lower() and "uploads" in src:
            full = urljoin(url, src)
            if not urlparse(full).netloc.endswith("smiski.com"):   # old staging host in some pages; same upload path lives on smiski.com
                full = "https://smiski.com/e" + urlparse(full).path
            out.append((full, fn))
    return out


def shrink(path: Path, dest: Path) -> None:
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.getbbox() or (0, 0, *im.size))            # trim transparent margins
    if im.height > MAX_H:
        im = im.resize((round(im.width * MAX_H / im.height), MAX_H), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, optimize=True)


def main() -> None:
    series = pd.read_csv(RAW / "catalog_series.csv")
    figs = pd.read_csv(RAW / "catalog_figures.csv")
    index = {}
    for s in series.itertuples():
        imgs = page_images(s.page_url)
        regular = [i for i in imgs if "secret" not in i[1].lower()][:6]
        # The site's "*_secret.png" files are a "? 6 KINDS + SECRET" promo graphic, not the secret figure
        # (the maker keeps it hidden), so secrets deliberately get no official image.
        secret = None
        rows = figs[figs.series_id == s.series_id].sort_values("figure_id")
        reg_rows, sec_rows = rows[rows.rarity_tier == "common"], rows[rows.rarity_tier == "secret"]
        pairs = list(zip(reg_rows.figure_id, regular)) + ([(sec_rows.figure_id.iloc[0], secret)] if secret and len(sec_rows) else [])
        if len(regular) != len(reg_rows):
            print(f"  WARNING {s.slug}: {len(regular)} images for {len(reg_rows)} figures")
        for fid, (src, fn) in pairs:
            try:
                raw = get_bytes(src, RAW / "images" / s.slug / fn)
                shrink(raw, OUT / f"{fid}.png")
                index[fid] = f"img/figures/{fid}.png"
            except Blocked as e:
                raise SystemExit(f"BLOCKED: {e}")
            except Exception as e:                         # a single bad file should not stop the run
                print(f"  skipped {fid} ({fn}): {e}")
        print(f"{s.series_id} {s.series_name}: {sum(1 for f, _ in pairs if f in index)}/{len(pairs)} images")
    (RAW / "images" / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} images -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
