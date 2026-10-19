PY := .venv/bin/python
NB := notebooks/01_resale_premium.ipynb notebooks/02_demand_forecast.ipynb notebooks/03_reddit_nlp.ipynb

.PHONY: help setup seed scrape data notebooks site-data test serve all clean
help:
	@echo "make setup      create .venv and install requirements (macOS: also patch libomp)"
	@echo "make scrape     fetch real data (smiski.com catalog + news, Google Trends, Reddit if credentials set)"
	@echo "make data       merge whatever is in data/raw/ into data/processed/ (real where available, simulated otherwise)"
	@echo "make seed       write a FULLY simulated dataset into data/processed/ (offline fallback)"
	@echo "make notebooks  execute the three notebooks in-process and refresh site/data/*.json"
	@echo "make site-data  bundle JSON into site/data/data.js"
	@echo "make test       run tests"
	@echo "make serve      serve site/ at http://localhost:8000"
	@echo "make all        data -> notebooks -> site-data -> test"

setup:
	uv venv .venv --python 3.14 || python3 -m venv .venv
	uv pip install --python $(PY) -r requirements.txt || $(PY) -m pip install -r requirements.txt
	@if [ "$$(uname)" = "Darwin" ]; then tools/fix_macos_libomp.sh .venv; fi

seed:
	PYTHONPATH=src $(PY) -m smiskis.seed

scrape:
	-$(PY) scrapers/smiski_catalog.py
	-$(PY) scrapers/smiski_news.py
	-$(PY) scrapers/google_trends.py
	-$(PY) scrapers/wikipedia.py
	-$(PY) scrapers/reddit_api.py
	$(PY) scrapers/build_catalog.py
	$(PY) scrapers/build_dataset.py

data:
	$(PY) scrapers/build_catalog.py
	$(PY) scrapers/build_dataset.py

notebooks:
	$(PY) tools/execute_notebooks.py $(NB)

site-data:
	$(PY) tools/export_site_data.py

test:
	PYTHONPATH=src $(PY) -m pytest -q tests

serve:
	$(PY) -m http.server 8000 -d site

all: data notebooks site-data test

clean:
	rm -rf data/raw/_cache reports/*.png site/data/*.json site/data/data.js
