# Smiski Lab

An unofficial fan data-science project on Smiski blind boxes: **what drives a figure's resale premium**, **where demand is heading**, and **what collectors talk about**, plus a static website with a virtual blind box that prices every pull with the model.

> ## What is real and what is not
> | Table | Status | Source |
> |---|---|---|
> | Series (18) and figures (108 named + 18 secrets) | **real** | smiski.com/e/products (official names and descriptions) |
> | Search interest, weekly 2018-2026 | **real** | Google Trends via `pytrends` (two windows stitched) |
> | Product events (launches, stores, products) | **real** | smiski.com/e/news (36 English posts) + series launches |
> | Resale prices / premiums | **simulated** | no accessible source: marketplaces need their own API access |
> | Reddit posts | **simulated** | needs Reddit API credentials (see below) |
>
> Anything that depends on resale prices or Reddit text (notebooks 01 and 03, the blind-box "predicted value")
> demonstrates the method on a simulation laid over the **real** catalog; it says nothing about real prices or
> real fans. Notebook 02 (forecast + changepoints) runs entirely on real data.
>
> **Assumptions inside the real tables** (also in `data/processed/DATA_SOURCE.json` and on the site):
> * Pull rates: the secret is 1/72 (a figure collectors quote; the maker does not publish odds), the 6 regular figures share the rest.
> * Retail price: 12.99 assumed for every series (the site shows no prices).
> * Release dates: a news-announced date where one exists (Museum onward), otherwise the first of the month the series page's
>   images were uploaded (Series 1 - Cheer; approximate and flagged `page_image_upload_month`).
> * Secret figures are never named on the site, so each series has one unnamed "Secret".
> * HIPPERS is excluded (attachable figures, no secret); accessories, plush and other products are not blind-box series.
> * No collab series were identified, so the `collab` feature is constant.

## What's inside

| Part | Where | What it does |
|---|---|---|
| 1. Resale premium (supervised) | `notebooks/01_resale_premium.ipynb` | Ridge baseline → LightGBM / XGBoost; validated by **leave-one-series-out** and a **time hold-out**; two baselines (mean, rarity-tier mean); series-level bootstrap of the improvement; **SHAP** with stability across refits; empirical prediction intervals checked on the newest series |
| 2. Demand forecast (time series) | `notebooks/02_demand_forecast.ipynb` | Naive, seasonal-naive, SARIMAX (Fourier seasonality), Prophet, Prophet + launch calendar, LightGBM on lags; rolling-origin backtests pick the model, a final 52-week hold-out reports it; **ruptures** changepoints aligned to product events; calibrated intervals |
| 3. Fan conversation (NLP) | `notebooks/03_reddit_nlp.ipynb` | **BERTopic** topics, VADER sentiment, lead/lag with block-bootstrap intervals and Granger tests; exports aggregates only |
| Website | `site/` | Static, no build step, GitHub-Pages ready: blind box simulator, model section, forecast chart with interval, changepoints, topics |
| Scrapers | `scrapers/` | Polite (robots.txt, 2 s throttle, cache) fetchers: `smiski_catalog.py`, `smiski_news.py`, `google_trends.py`, `reddit_api.py`; `build_catalog.py` and `build_dataset.py` assemble the tables |

Optional extras from the brief (clustering, Bayesian pull rates, CLIP, causal impact) were left out on purpose: the brief suggested three models, and the data is too small to carry more.

## Quickstart

```bash
make setup        # venv + dependencies (macOS: also patches libomp for LightGBM/XGBoost)
make all          # seed data -> run all notebooks -> bundle site data -> tests
make serve        # http://localhost:8000   (or just open site/index.html)
```

Notebooks open normally in Jupyter (`jupyter lab`, kernel "Python (smiskis)"). `make notebooks` executes them
in-process via `tools/execute_notebooks.py`, which works where a Jupyter kernel cannot start.

## Getting the data (what was done, and what is still missing)

```bash
make scrape      # smiski.com catalog + news, Google Trends, (Reddit if credentials are set), then build data/processed/
make data        # re-merge data/raw/ into data/processed/ without fetching
```

* **Reddit** (still simulated): create a "script" app at <https://www.reddit.com/prefs/apps>, then
  `export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...` and `make scrape`. Anonymous `.json` requests get a 403, so the official
  OAuth API is the only route. Keep raw posts private (Reddit's Data API terms). In notebook 03 set `USE_SBERT = True` for sentence
  embeddings if `huggingface.co` is reachable.
* **Resale prices** (still simulated): there is no scraper, because marketplaces restrict it. Supply your own
  `data/raw/resale_listings.csv` with columns `figure_id, snapshot_date, median_sold_usd, n_sold` (figure ids are in
  `data/processed/figures.csv`), then `make data notebooks site-data`.
* The site's REST API (`/wp-json`) returns 403, so it is not used. Release dates come from the news archive and image-upload
  months instead. Selectors are tied to the site's current markup and may need updating if it changes.
* `make seed` writes a fully simulated dataset (offline fallback).

## Design choices worth knowing

* **Validation by series.** Figures in one series look alike; a random split leaks. Notebook 01 shows the
  random-vs-grouped gap explicitly. On the simulated data the gap is small (R² 0.90 vs 0.87) because the
  simulator's noise is figure-level; real data likely leaks more.
* **Two baselines.** "Mean" is easy to beat. "Mean per rarity tier" is the one a collector would guess, and the
  claim "the model beats the baseline" is made against that one, with a 90% bootstrap interval over series.
* **Small data.** The effective sample size is the number of series (18), not the few hundred price snapshots.
* **Intervals are checked, not just drawn.** The price interval covered 80% of the newest series. The forecast
  interval did **not**: the built-in SARIMAX interval covered 98%, the recalibrated one 44%, because the
  hold-out contains a structural break the backtests never saw. The site and notebook report this.
* **SHAP explains the model, not the market.** `retail_usd` partly stands in for release era.
* **Topic discovery excludes tone words** (VADER lexicon) so topics describe subject matter while sentiment is
  analysed separately. Series and pose names are removed from keyword ranking.
* **Official images are local-only.** `python scrapers/smiski_images.py` downloads each figure's product photo from
  smiski.com (108 figures; the 18 secrets have none, because the site only shows a "?" graphic for them) and resizes
  it into `site/img/figures/`. That folder is **git-ignored**: the photos are Dreams Inc.'s artwork, so they are not
  committed or deployed unless you choose to remove the ignore rule and accept that. Without the files the site falls
  back to original placeholder sprites, so the GitHub Pages build still works.

## Layout

```
smiskis/
├── notebooks/        01 premium · 02 forecast · 03 Reddit NLP (executed, outputs included)
├── src/smiskis/      seed.py (simulator) · data.py (loader + provenance banner) · viz.py (chart style)
├── scrapers/         common.py · smiski_official.py · wikipedia.py · reddit_api.py · google_trends.py · build_dataset.py
├── tools/            execute_notebooks.py · export_site_data.py · fix_macos_libomp.sh
├── data/processed/   CSVs + DATA_SOURCE.json            (data/raw/ is git-ignored)
├── reports/          PNGs saved by the notebooks
├── site/             index.html · css/ · js/ · data/*.json + data.js
├── tests/            schema, leakage and export checks (make test)
└── .github/workflows/pages.yml   publishes site/ to GitHub Pages
```

## Deploying the site

Push to GitHub, then Settings → Pages → Source: *GitHub Actions*. The included workflow publishes `site/`.
`site/data/data.js` bundles all model outputs, so no server-side code or `fetch()` is needed.

## Not done / known limits

* The catalog scraper was tested against the live site; the Reddit scraper was **not** run (no credentials). Google Trends goes through the
  unofficial `pytrends` package, which needs `retries=0` on urllib3 2.x and may be rate-limited.
* The website was verified by running its JavaScript in jsdom (no errors; the full pick-series → pick-box → open
  flow works) and by rendering the chart SVGs to images. It has **not** been viewed in a real browser: check
  layout on a phone-width window before publishing.
* Forecast changepoint matching uses ±8 weeks, and the penalty (a plateau rule) is a judgement call; the notebook
  prints the sensitivity table.
* Unofficial and non-commercial. Smiski is a brand of Dreams Inc.; this project is not affiliated with them.
