"""Bundle model outputs into site/data/*.json plus site/data/data.js.

data.js assigns everything to ``window.SMISKI`` so the site also works when
opened straight from disk (fetch() of local JSON is blocked by browsers).
Run after the notebooks:  python tools/export_site_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smiskis.data import load, provenance  # noqa: E402
from smiskis.paths import SITE_DATA  # noqa: E402

IMG_DIR = SITE_DATA.parent / "img" / "figures"


def main() -> None:
    series, figs = load("series"), load("figures")
    premium = json.loads((SITE_DATA / "premium.json").read_text())
    pred = {p["figure_id"]: p for p in premium["figures"]}
    out = []
    for s in series.itertuples():
        fl = []
        for f in figs[figs.series_id == s.series_id].itertuples():
            p = pred.get(f.figure_id, {})
            desc = getattr(f, "description", "")
            fl.append(dict(id=f.figure_id, name=f.figure_name, tier=f.rarity_tier, pull_rate=float(f.pull_rate),
                           description=desc if isinstance(desc, str) else "",
                           img=f"img/figures/{f.figure_id}.png" if (IMG_DIR / f"{f.figure_id}.png").exists() else None,
                           glow=bool(f.glow), pred_pct=p.get("pred_pct"), lo_pct=p.get("lo_pct"), hi_pct=p.get("hi_pct"),
                           pred_usd=p.get("pred_usd"), lo_usd=p.get("lo_usd"), hi_usd=p.get("hi_usd")))
        out.append(dict(id=s.series_id, name=s.series_name, theme=s.theme, release=s.release_date.strftime("%Y-%m-%d"),
                        collab=bool(s.collab), retail_usd=float(s.retail_usd), figures=fl,
                        date_src=str(getattr(s, "release_date_source", "")), url=str(getattr(s, "page_url", ""))))
    prov = provenance()
    catalog = dict(provenance=prov["tables"], assumptions=prov.get("assumptions", []), trends_note=prov.get("trends_note", ""), series=out)
    (SITE_DATA / "catalog.json").write_text(json.dumps(catalog))
    bundle = dict(catalog=catalog, premium=premium,
                  forecast=json.loads((SITE_DATA / "forecast.json").read_text()),
                  reddit=json.loads((SITE_DATA / "reddit.json").read_text()))
    (SITE_DATA / "data.js").write_text("window.SMISKI = " + json.dumps(bundle, separators=(",", ":")) + ";\n")
    print(f"catalog: {len(out)} series, {sum(len(s['figures']) for s in out)} figures | data.js {(SITE_DATA / 'data.js').stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
