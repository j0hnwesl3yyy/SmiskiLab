from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "site" / "data"

for _p in (RAW, PROCESSED, SITE_DATA):
    _p.mkdir(parents=True, exist_ok=True)

# Date the study "ends". Snapshots and forecasts are relative to this.
AS_OF = "2026-10-11"
