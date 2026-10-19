"""Google Trends interest-over-time for "smiski" via the unofficial `pytrends` package.

Google returns WEEKLY data only for windows <= ~5 years, so two overlapping weekly windows are fetched and
the earlier one is rescaled onto the later one using the overlap (the usual stitching trick). The result is
renormalised to a 0-100 peak. Early values (2018-2020) are tiny integers, so they are very noisy.

Fallback with no unofficial API: export the CSV by hand from trends.google.com and save it as
data/raw/google_trends.csv (columns: week, interest).
"""
from __future__ import annotations

import time

import pandas as pd

from common import RAW

WINDOWS = [("2018-01-01", "2022-12-31"), ("2021-10-10", None)]   # None -> today


def fetch(start: str, end: str | None) -> pd.Series:
    from pytrends.request import TrendReq
    # retries=0: pytrends' own Retry() call breaks on urllib3 2.x; we retry manually below
    py = TrendReq(hl="en-US", tz=0, timeout=(10, 40), retries=0, backoff_factor=0)
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    for attempt in range(4):
        try:
            py.build_payload(["smiski"], timeframe=f"{start} {end}")
            df = py.interest_over_time()
            return df["smiski"].astype(float).rename("interest")
        except Exception as e:                       # 429s etc.
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(15 * (attempt + 1))
    raise SystemExit("Google Trends kept failing (rate limit?). Try later or export the CSV by hand.")


if __name__ == "__main__":
    a = fetch(*WINDOWS[0]); time.sleep(5); b = fetch(*WINDOWS[1])
    gap = a.index.to_series().diff().dt.days.median()
    assert gap == 7, f"expected weekly data, got median gap {gap} days"
    both = a.index.intersection(b.index)
    scale = b[both].mean() / a[both].mean() if a[both].mean() > 0 else 1.0
    print(f"overlap {len(both)} weeks, rescale factor for the early window = {scale:.2f}")
    s = pd.concat([(a * scale)[a.index < b.index.min()], b]).sort_index()
    s = (100 * s / s.max()).round(1)
    out = s.reset_index(); out.columns = ["week", "interest"]
    out.to_csv(RAW / "google_trends.csv", index=False)
    print(f"wrote {len(out)} weeks {out.week.min().date()} .. {out.week.max().date()} -> data/raw/google_trends.csv")
