"""Load the processed tables and their provenance."""
from __future__ import annotations

import json

import pandas as pd

from .paths import PROCESSED

DATES = {"series": ["release_date"], "figures": ["release_date"], "resale": ["snapshot_date"],
         "trends": ["week"], "events": ["date"], "reddit": ["created"]}


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / f"{name}.csv", parse_dates=DATES.get(name, []))


def provenance() -> dict:
    return json.loads((PROCESSED / "DATA_SOURCE.json").read_text())


def banner(*tables: str) -> str:
    prov = provenance()["tables"]
    labels = {t: prov.get(t, "unknown") for t in tables}
    sim = [t for t, v in labels.items() if v == "simulated"]
    line = " | ".join(f"{t}: {v}" for t, v in labels.items())
    if sim:
        return (f"DATA PROVENANCE  [{line}]\n"
                f"  !! {', '.join(sim)} is SIMULATED (see src/smiskis/seed.py). Results below describe the "
                f"simulation, not the real Smiski market. Run `make scrape` with network access to replace it.")
    return f"DATA PROVENANCE  [{line}]"
