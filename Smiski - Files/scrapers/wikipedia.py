"""Pull Smiski background from the MediaWiki API (an official, documented API)."""
from __future__ import annotations

import json

from common import RAW, Blocked, get

API = "https://en.wikipedia.org/w/api.php"


def fetch(title: str = "Smiski") -> dict:
    txt = get(API, params=dict(action="query", format="json", prop="extracts|pageprops|info",
                               explaintext=1, redirects=1, titles=title, inprop="url"))
    pages = json.loads(txt)["query"]["pages"]
    page = next(iter(pages.values()))
    return dict(title=page.get("title"), url=page.get("fullurl"), extract=page.get("extract", ""))


if __name__ == "__main__":
    try:
        data = fetch()
    except Blocked as e:
        raise SystemExit(f"BLOCKED: {e}")
    (RAW / "wikipedia_smiski.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"wrote {len(data['extract'])} chars -> data/raw/wikipedia_smiski.json")
