"""Simulated seed dataset for the Smiski project.

WHY THIS EXISTS
    The scrapers in ``scrapers/`` need network access to smiski.com, Wikipedia,
    Reddit and Google Trends. When that access is unavailable, this module
    generates a *simulated* dataset with exactly the same schema so every
    notebook and the website still run end to end.

WHAT IT IS NOT
    Nothing here is real market data. Series names/dates are illustrative
    approximations, and every price, search-interest value and Reddit post is
    drawn from a data-generating process written below. Any "finding" computed
    on this data describes that process, not Smiski fans or the real resale
    market. The generator keeps a small ground truth (injected changepoints,
    a built-in sentiment lead) so the methods can be sanity-checked.

Run:  python -m smiskis.seed
Writes CSVs into data/processed/ and a ``DATA_SOURCE`` marker file.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .paths import AS_OF, PROCESSED

SEED = 1218

# --- Catalog ------------------------------------------------------------------
# (series_id, theme, release_date, collab)
SERIES = [
    ("S01", "Work",     "2018-12-01", 0),
    ("S02", "Bed",      "2019-09-01", 0),
    ("S03", "Exercise", "2020-06-01", 0),
    ("S04", "Living",   "2021-03-01", 0),
    ("S05", "Museum",   "2021-11-01", 0),
    ("S06", "Dressing", "2022-06-01", 0),
    ("S07", "Cheer",    "2022-12-01", 0),
    ("S08", "Moving",   "2023-06-01", 0),
    ("S09", "Yoga",     "2023-11-01", 0),
    ("S10", "Bath",     "2024-04-01", 0),
    ("S11", "Sitting",  "2024-09-01", 1),
    ("S12", "Hippers",  "2025-02-01", 0),
    ("S13", "Travel",   "2025-07-01", 1),
    ("S14", "Garden",   "2026-03-01", 0),
    ("S15", "Night Out", "2026-07-01", 1),
]

# Six regular poses + one secret per series. Pose names are illustrative.
POSES = {
    "Work":      ["Typing", "Coffee Break", "Stapling", "Dozing Off", "Presenting", "On The Phone", "Late Night"],
    "Bed":       ["Stretching", "Pillow Hug", "Peeking", "Snoozing", "Rolling Over", "Yawning", "Dream Walk"],
    "Exercise":  ["Stretch", "Jump Rope", "Sit-Ups", "Jogging", "Squats", "Cool Down", "Champion"],
    "Living":    ["Sofa Slump", "Remote Hunt", "Snack Raid", "Window Gazing", "Reading", "Tidy Up", "Midnight Fridge"],
    "Museum":    ["Admiring", "Reading Plaque", "Sketching", "Pointing", "Tiptoe", "Audio Guide", "After Hours"],
    "Dressing":  ["Buttoning", "Sock Hop", "Tie Trouble", "Hat Try-On", "Mirror Check", "Zip Up", "Runway"],
    "Cheer":     ["Pom-Poms", "Megaphone", "Banner", "Jump Cheer", "High Five", "Team Huddle", "Mascot"],
    "Moving":    ["Box Carry", "Tape Gun", "Peeking Out", "Box Sit", "Wrapping", "Stack Wobble", "Keys"],
    "Yoga":      ["Tree Pose", "Downward Dog", "Lotus", "Warrior", "Child's Pose", "Bridge", "Zen"],
    "Bath":      ["Bubble Bath", "Rubber Duck", "Towel Wrap", "Scrubbing", "Shower Cap", "Steamy Mirror", "Soak"],
    "Sitting":   ["Cross-Legged", "Bench Sit", "Chin Rest", "Knees Up", "Swing Legs", "Leaning", "Moonlit Perch"],
    "Hippers":   ["Peek-A-Boo", "Hip Sway", "Wiggle", "Spin", "Bounce", "Shuffle", "Glow Dance"],
    "Travel":    ["Backpack", "Map Reading", "Window Seat", "Camera", "Souvenir", "Hitchhike", "Stowaway"],
    "Garden":    ["Watering", "Planting", "Sniffing Flower", "Weeding", "Wheelbarrow", "Sunhat", "Fireflies"],
    "Night Out": ["Karaoke", "Lantern Walk", "Street Food", "Dance Floor", "Photo Booth", "Rooftop", "Last Train"],
}

# Latent "how collectible does this theme feel" effect used by the generator.
THEME_EFFECT = {
    "Work": 0.10, "Bed": 0.18, "Exercise": -0.02, "Living": 0.02, "Museum": 0.14,
    "Dressing": -0.04, "Cheer": 0.00, "Moving": 0.06, "Yoga": 0.03, "Bath": 0.12,
    "Sitting": 0.05, "Hippers": 0.08, "Travel": 0.02, "Garden": 0.04, "Night Out": 0.06,
}

def theme_effect(theme: str) -> float:
    """Latent theme appeal used by the simulator. Unknown themes get a stable pseudo-random value."""
    if theme in THEME_EFFECT:
        return THEME_EFFECT[theme]
    h = sum(ord(c) * (i + 7) for i, c in enumerate(theme)) % 1000
    return round((h / 1000 - 0.5) * 0.24, 3)


# Rarity tier -> (count per series, pull probability per figure)
RARITY = {"common": (4, 0.20), "uncommon": (2, 0.0928), "secret": (1, 0.0139)}

EVENTS = [
    # date, type, label  -- illustrative placeholders, replace with scraped news
    ("2018-12-01", "series_launch", "Series 1 launch (Japan)"),
    ("2021-08-15", "store_launch",  "First dedicated shop opens (illustrative)"),
    ("2023-03-12", "viral",         "Social-media wave goes viral (illustrative)"),
    ("2024-03-03", "store_launch",  "North America retail expansion (illustrative)"),
    ("2025-04-13", "store_launch",  "Flagship store opens (illustrative)"),
    ("2026-03-08", "market",        "Market saturation / restock glut (illustrative)"),
]
# (date, log-level step) -- ground-truth structural breaks in the trends series
LEVEL_STEPS = [
    ("2018-12-01", 0.20), ("2021-08-15", 0.35), ("2023-03-12", 0.95),
    ("2024-03-03", 0.50), ("2025-04-13", 0.30), ("2026-03-08", -0.18),
]


def _weeks() -> pd.DatetimeIndex:
    return pd.date_range("2018-01-07", AS_OF, freq="W-SUN")


def make_events(series_df: pd.DataFrame) -> pd.DataFrame:
    ev = pd.DataFrame(EVENTS, columns=["date", "type", "label"])
    launches = pd.DataFrame({
        "date": series_df["release_date"],
        "type": "series_launch",
        "label": "Launch: " + series_df["series_name"],
    })
    ev = pd.concat([ev[ev["type"] != "series_launch"], launches], ignore_index=True)
    ev["date"] = pd.to_datetime(ev["date"])
    return ev.sort_values("date").reset_index(drop=True)


def make_trends(series_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    wk = _weeks()
    n = len(wk)
    t = np.arange(n)
    log_level = np.full(n, np.log(4.0))
    for d, step in LEVEL_STEPS:
        log_level += np.where(wk >= pd.Timestamp(d), step, 0.0)
    log_level += 0.0006 * t  # slow organic drift

    doy = wk.dayofyear.values
    season = 0.17 * np.cos(2 * np.pi * (doy - 355) / 365.25) + 0.05 * np.cos(4 * np.pi * (doy - 190) / 365.25)

    bump = np.zeros(n)
    for rd, amp in zip(series_df["release_date"], np.where(series_df["collab"] == 1, 0.40, 0.28)):
        lag = (wk - pd.Timestamp(rd)).days.values / 7.0
        bump += np.where(lag >= 0, amp * np.exp(-lag / 3.0), 0.0)

    ar = np.zeros(n)
    eps = rng.normal(0, 0.065, n)
    for i in range(1, n):
        ar[i] = 0.55 * ar[i - 1] + eps[i]

    raw = np.exp(log_level + season + bump + ar)
    interest = np.clip(np.round(100 * raw / raw.max()), 1, 100).astype(int)
    return pd.DataFrame({"week": wk, "interest": interest, "keyword": "smiski"})


def make_catalog(rng: np.random.Generator, trends: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    srows, frows = [], []
    t = trends.set_index("week")["interest"]
    for sid, theme, rel, collab in SERIES:
        rel_ts = pd.Timestamp(rel)
        retail = 12.99 if rel_ts < pd.Timestamp("2023-01-01") else 13.99 if rel_ts < pd.Timestamp("2025-01-01") else 14.99
        retail += 3.0 * collab
        # search interest in the 4 weeks starting at launch
        launch_interest = float(t[(t.index >= rel_ts) & (t.index < rel_ts + pd.Timedelta(weeks=4))].mean())
        name = f"Series {int(sid[1:])} · {theme}"
        srows.append(dict(series_id=sid, series_name=name, theme=theme, release_date=rel_ts,
                          collab=collab, retail_usd=round(retail, 2), launch_interest=round(launch_interest, 1),
                          n_figures=7, source="seed"))
        poses = iter(POSES[theme])
        fnum = 0
        for tier, (cnt, p) in RARITY.items():
            for _ in range(cnt):
                fnum += 1
                pose = next(poses)
                frows.append(dict(figure_id=f"{sid}-{fnum:02d}", series_id=sid, series_name=name,
                                  theme=theme, figure_name=pose, rarity_tier=tier,
                                  pull_rate=round(p * rng.uniform(0.93, 1.07), 4),
                                  glow=int(tier == "secret"), collab=collab,
                                  retail_usd=round(retail, 2), release_date=rel_ts))
    series_df = pd.DataFrame(srows)
    fig_df = pd.DataFrame(frows)
    # renormalise pull rates inside each series so they sum to 1
    fig_df["pull_rate"] = fig_df.groupby("series_id")["pull_rate"].transform(lambda s: (s / s.sum()).round(4))
    return series_df, fig_df


def add_launch_interest(series_df: pd.DataFrame, trends: pd.DataFrame) -> pd.DataFrame:
    """Mean search interest in the 4 weeks starting at each release (works for real or simulated trends)."""
    t = trends.set_index("week")["interest"]
    out = series_df.copy()
    out["launch_interest"] = [round(float(t[(t.index >= d) & (t.index < d + pd.Timedelta(weeks=4))].mean()), 1)
                              for d in out["release_date"]]
    first = round(float(t.iloc[:4].mean()), 1)                 # releases before the trends window: use the earliest level
    out["launch_interest"] = out["launch_interest"].fillna(first)
    return out


def make_resale(rng: np.random.Generator, fig_df: pd.DataFrame, series_df: pd.DataFrame) -> pd.DataFrame:
    """Quarterly median sold-price premium per figure (simulated)."""
    snaps = pd.to_datetime(["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"])
    li = series_df.set_index("series_id")["launch_interest"]
    li_norm = (li - li.min()) / (li.max() - li.min())
    series_shock = pd.Series(rng.normal(0, 0.12, len(series_df)), index=series_df["series_id"])
    fig_eps = pd.Series(rng.normal(0, 0.10, len(fig_df)), index=fig_df["figure_id"])
    rarity_eff = {"common": 0.0, "uncommon": 0.15, "secret": 1.10}

    rows = []
    for f in fig_df.itertuples():
        s_eff = (0.35 * li_norm[f.series_id] + theme_effect(f.theme) + 0.30 * f.collab
                 + series_shock[f.series_id])
        for snap in snaps:
            m = (snap - f.release_date).days / 30.44
            if m < 0.5:
                continue
            age = 0.25 * np.exp(-m / 4.0) + 0.12 * (1 - np.exp(-m / 18.0))
            pct = (0.08 + rarity_eff[f.rarity_tier] * (0.6 + s_eff) + 0.5 * s_eff + age
                   + fig_eps[f.figure_id] + rng.normal(0, 0.04))
            pct = max(pct, -0.30)
            n_sold = int(rng.poisson(6 if f.rarity_tier == "common" else 3 if f.rarity_tier == "uncommon" else 2) + 1)
            rows.append(dict(figure_id=f.figure_id, snapshot_date=snap,
                             months_since_launch=round(m, 2),
                             median_sold_usd=round(f.retail_usd * (1 + pct), 2),
                             premium_pct=round(pct * 100, 2), n_sold=n_sold))
    return pd.DataFrame(rows)


# --- Reddit -------------------------------------------------------------------
TOPIC_TEMPLATES = {
    "figure_chatter": [
        "Finally pulled {fig} from the {theme} series!",
        "{fig} is my favorite pose so far, the details are great",
        "Anyone else think {fig} looks better in person?",
        "Which {theme} smiski do you think is the cutest, I keep going back to {fig}",
        "Got {fig} in my first box, can't believe it",
    ],
    "scarcity": [
        "Can't find the {theme} series anywhere, every store is sold out",
        "Sold out again. How are people finding {theme} boxes?",
        "Restock alert? Checked three stores for {theme} and nothing",
        "Is {theme} getting a restock? Shelves have been empty for weeks",
        "Tired of the queue and the limit per customer for {theme}",
    ],
    "display": [
        "My shelf display with the {theme} set and a little lamp, they glow so nicely",
        "Built a little glow-in-the-dark display for {fig}, photos inside",
        "Where do you keep your smiskis? Looking for display shelf ideas for {theme}",
        "Desk setup update: {fig} sits next to my monitor now",
        "Dark room glow test with {theme} figures, look at that green",
    ],
    "resale": [
        "Someone on ebay wants {price} for the {theme} secret, that's insane",
        "Resale prices for {fig} are out of control, scalpers everywhere",
        "Is it worth paying a premium for the secret from {theme}?",
        "Sold my duplicate {fig} for double retail, is that bad?",
        "Price check: what is {fig} going for on mercari lately?",
    ],
    "pull_rates": [
        "Opened {n} boxes of {theme} and got duplicates every time, what are the odds?",
        "Pull rate thread: how many boxes did it take to get the secret in {theme}?",
        "Case break of {theme}: {n} boxes, one secret. Results inside",
        "Does shaking the box actually help find {fig}? Asking for science",
        "Got the secret on my {n}th box of {theme}!",
    ],
    "new_release": [
        "New {theme} series announced, those poses look so good",
        "{theme} collab reveal, who else is hyped for launch day?",
        "Preorders for {theme} are open, which pose are you hoping for?",
        "Leak or real? Possible new {theme} lineup",
        "Release date confirmed for {theme}, counting down",
    ],
}
# base valence of each topic (VADER-ish scale) and base share
TOPIC_PRIOR = {
    "figure_chatter": 0.26, "scarcity": 0.17, "display": 0.20,
    "resale": 0.12, "pull_rates": 0.15, "new_release": 0.10,
}
TOPIC_BODY = {
    "figure_chatter": ["The sculpt and paint on this pose are great.", "Honestly my favorite pose of the whole lineup.", "The face detail is so cute in person."],
    "scarcity": ["Every store I checked has empty shelves and a queue.", "Sold out online within minutes of the restock.", "There is a limit per customer and nothing in stock."],
    "display": ["Photos of my shelf and lamp setup inside.", "They glow in the dark so well on the display shelf.", "Placed on my desk next to the monitor, the glow is lovely."],
    "resale": ["Ebay and mercari prices are above retail again.", "Scalpers are listing at double the retail price.", "Resale premium feels too high for a blind box."],
    "pull_rates": ["Opened a whole case of boxes and the odds felt rough.", "Duplicates everywhere, the secret pull rate seems tiny.", "Tracking how many boxes it takes to pull the secret."],
    "new_release": ["The announced lineup and release date look promising.", "Preorders and the collab reveal have everyone hyped.", "Another leak of the upcoming release surfaced today."],
}
POS = ["so happy about it", "love it", "obsessed", "this made my week", "absolutely adorable", "worth it"]
NEG = ["so frustrated", "really disappointed", "ugh, this is awful", "kind of annoying", "not happy at all", "this is ridiculous"]
NEUT = ["any thoughts?", "curious what you all think", "thanks in advance"]


def make_reddit(rng: np.random.Generator, trends: pd.DataFrame, series_df: pd.DataFrame,
                fig_df: pd.DataFrame, total_posts: int = 3600, lead_weeks: int = 2) -> pd.DataFrame:
    """Posts whose volume follows demand and whose mood *leads* demand by ``lead_weeks``."""
    wk = trends["week"].values
    demand = trends["interest"].values.astype(float)
    # Reddit community only exists once there is a bit of buzz
    vol_w = demand ** 0.9
    vol_w = vol_w / vol_w.sum()
    log_d = np.log(np.maximum(demand, 0.5))
    # high-pass the demand so mood reflects *momentum*, not the long-run level
    mom = log_d - pd.Series(log_d).rolling(26, min_periods=1).mean().values
    mood_raw = pd.Series(mom).shift(-lead_weeks).bfill().ffill().values   # t+lead
    mood = 1 / (1 + np.exp(-3.0 * (mood_raw / (mood_raw.std() + 1e-9)) * 0.6))

    counts = rng.multinomial(total_posts, vol_w)
    topics = list(TOPIC_PRIOR)
    base = np.array([TOPIC_PRIOR[k] for k in topics])
    rows, pid = [], 0
    rel = series_df.set_index("series_id")["release_date"]
    for i, c in enumerate(counts):
        if c == 0:
            continue
        w_date = pd.Timestamp(wk[i])
        # scarcity & new_release spike right after launches
        since = (w_date - rel).dt.days.values / 7.0
        near = float(np.any((since >= 0) & (since < 6)))
        mix = base * np.array([1, 1 + 1.3 * near, 1, 1 + 0.4 * (w_date > pd.Timestamp("2023-03-12")), 1, 1 + 1.0 * near])
        mix = mix / mix.sum()
        for _ in range(c):
            topic = rng.choice(topics, p=mix)
            # pick a series that is "current" or any, weighted to recent
            live = series_df[series_df["release_date"] <= w_date]
            if live.empty:
                live = series_df.iloc[[0]]
            pick = live.iloc[-1] if rng.random() < 0.5 else live.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
            figs = fig_df[fig_df["series_id"] == pick["series_id"]]
            fig = figs.sample(1, random_state=int(rng.integers(1e9))).iloc[0]["figure_name"]
            tmpl = TOPIC_TEMPLATES[topic][rng.integers(len(TOPIC_TEMPLATES[topic]))]
            title = tmpl.format(fig=fig, theme=pick["theme"], price=f"${int(rng.integers(40, 400))}", n=int(rng.integers(3, 25)))
            # mood suffix: topic prior pulls negative for scarcity/resale
            p_pos = mood[i] * (0.35 if topic in ("scarcity", "resale") else 0.9)
            r = rng.random()
            tail = POS if r < p_pos else NEG if r < p_pos + (1 - p_pos) * 0.75 else NEUT
            subject = rng.choice(TOPIC_BODY[topic])
            body = f"{subject} {rng.choice(NEUT)}" if tail is NEUT else f"{subject} {rng.choice(tail)}."
            created = w_date - pd.Timedelta(days=int(rng.integers(0, 7)))
            pid += 1
            rows.append(dict(post_id=f"sim{pid:05d}", created=created, subreddit="smiski",
                             title=title, body=body, score=int(rng.gamma(1.4, 14)),
                             num_comments=int(rng.gamma(1.2, 6)), true_topic=topic))
    return pd.DataFrame(rows)


def build(write: bool = True, catalog: tuple[pd.DataFrame, pd.DataFrame] | None = None,
          trends: pd.DataFrame | None = None, events: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Build every table. Pass real ``catalog`` (series_df, fig_df), ``trends`` and/or ``events`` to keep them;
    whatever is not supplied (and always resale + reddit) is simulated on top of them."""
    rng = np.random.default_rng(SEED)
    if trends is None:
        base_series = pd.DataFrame(SERIES, columns=["series_id", "theme", "release_date", "collab"])
        base_series["release_date"] = pd.to_datetime(base_series["release_date"])
        base_series["series_name"] = [f"Series {int(s[1:])} · {t}" for s, t in zip(base_series.series_id, base_series.theme)]
        trends = make_trends(base_series, rng)
    if catalog is None:
        series_df, fig_df = make_catalog(rng, trends)
    else:
        series_df, fig_df = add_launch_interest(catalog[0], trends), catalog[1]
    resale = make_resale(rng, fig_df, series_df)
    events = make_events(series_df) if events is None else events
    reddit = make_reddit(rng, trends, series_df, fig_df)
    out = dict(series=series_df, figures=fig_df, resale=resale, trends=trends, events=events, reddit=reddit)
    if write:
        for k, v in out.items():
            v.to_csv(PROCESSED / f"{k}.csv", index=False)
        (PROCESSED / "DATA_SOURCE.json").write_text(json.dumps({
            "tables": {k: "simulated" for k in out},
            "note": "Generated by smiskis.seed. Not real market data.",
            "level_steps_ground_truth": LEVEL_STEPS,
            "reddit_mood_lead_weeks": 2,
        }, indent=2))
    return out


if __name__ == "__main__":
    d = build()
    for k, v in d.items():
        print(f"{k:8s} {v.shape}")
