"""Sanity tests: schema, leakage guards, and exported artefacts. Run: make test"""
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import LeaveOneGroupOut

from smiskis.data import load, provenance
from smiskis.paths import PROCESSED, SITE_DATA


def test_provenance_file_labels_every_table():
    prov = provenance()["tables"]
    assert set(prov) == {"series", "figures", "resale", "trends", "events", "reddit"}
    assert set(prov.values()) <= {"simulated", "scraped", "user_supplied"}


def test_pull_rates_sum_to_one_per_series():
    figs = load("figures")
    sums = figs.groupby("series_id")["pull_rate"].sum()
    assert np.allclose(sums, 1.0, atol=0.01)


def test_every_series_has_one_secret():
    figs = load("figures")
    assert (figs[figs.rarity_tier == "secret"].groupby("series_id").size() == 1).all()


def test_resale_references_known_figures_and_positive_prices():
    resale, figs = load("resale"), load("figures")
    assert resale.figure_id.isin(figs.figure_id).all()
    assert (resale.median_sold_usd > 0).all()


def test_group_split_never_shares_a_series():
    """The validation scheme in notebook 01 must hold out whole series."""
    resale, figs = load("resale"), load("figures")
    g = resale.merge(figs[["figure_id", "series_id"]], on="figure_id")["series_id"].values
    for tr, te in LeaveOneGroupOut().split(np.zeros(len(g)), groups=g):
        assert set(g[tr]).isdisjoint(set(g[te]))


def test_trends_are_weekly_and_in_range():
    t = load("trends").sort_values("week")
    assert t.week.diff().dropna().dt.days.eq(7).all()
    assert t.interest.between(0, 100).all()


@pytest.mark.skipif(not (SITE_DATA / "premium.json").exists(), reason="run notebooks first")
def test_exported_intervals_are_ordered():
    p = json.loads((SITE_DATA / "premium.json").read_text())
    for f in p["figures"]:
        assert f["lo_usd"] <= f["pred_usd"] <= f["hi_usd"]
        assert f["lo_pct"] <= f["pred_pct"] <= f["hi_pct"]


@pytest.mark.skipif(not (SITE_DATA / "forecast.json").exists(), reason="run notebooks first")
def test_forecast_export_shapes():
    f = json.loads((SITE_DATA / "forecast.json").read_text())
    n = len(f["future"]["dates"])
    assert len(f["future"]["mean"]) == len(f["future"]["lo"]) == len(f["future"]["hi"]) == n
    assert all(lo <= m <= hi for lo, m, hi in zip(f["future"]["lo"], f["future"]["mean"], f["future"]["hi"]))
    assert len(f["holdout"]["dates"]) == f["holdout_weeks"]


@pytest.mark.skipif(not (SITE_DATA / "reddit.json").exists(), reason="run notebooks first")
def test_reddit_export_has_no_post_text():
    blob = (SITE_DATA / "reddit.json").read_text()
    posts = load("reddit")
    sample = posts["title"].dropna().sample(20, random_state=0)
    assert not any(t in blob for t in sample), "raw post titles must not be exported"


def test_real_catalog_is_sane_when_scraped():
    prov = provenance()["tables"]
    if prov["figures"] != "scraped":
        pytest.skip("catalog is simulated")
    figs, series = load("figures"), load("series")
    assert (figs.figure_name.str.strip() != "").all()
    named = figs[figs.rarity_tier == "common"]
    assert not named.duplicated(["series_id", "figure_name"]).any(), "duplicate figure names inside a series"
    assert named.groupby("series_id").size().between(5, 12).all()
    assert series.release_date.is_monotonic_increasing, "series ids must be in release order"
    assert series.release_date_source.notna().all()
