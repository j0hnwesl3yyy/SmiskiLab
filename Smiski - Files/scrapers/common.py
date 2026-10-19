"""Polite HTTP helper shared by all scrapers: robots.txt, throttling, on-disk cache."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = RAW / "_cache"
RAW.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

USER_AGENT = "smiski-student-research/0.1 (non-commercial data science project)"
MIN_DELAY_S = 2.0

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}


class Blocked(RuntimeError):
    """Raised when the network sandbox / robots.txt prevents a fetch."""


def allowed_by_robots(url: str) -> bool:
    host = urlparse(url)
    base = f"{host.scheme}://{host.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _session.get(f"{base}/robots.txt", timeout=15)
            rp.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(USER_AGENT, url)


def get(url: str, *, params: dict | None = None, headers: dict | None = None,
        use_cache: bool = True, check_robots: bool = True) -> requests.Response | str:
    """GET with cache + throttle. Returns text (from cache) or a Response."""
    key = hashlib.sha256((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()[:24]
    cached = CACHE / f"{key}.txt"
    if use_cache and cached.exists():
        return cached.read_text()
    if check_robots and not allowed_by_robots(url):
        raise Blocked(f"robots.txt disallows {url}")
    host = urlparse(url).netloc
    wait = MIN_DELAY_S - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    try:
        r = _session.get(url, params=params, headers=headers, timeout=30)
    except requests.exceptions.ProxyError as e:
        raise Blocked(f"network blocked for {host}: {e}") from e
    _last_hit[host] = time.time()
    if r.status_code == 403 and "sandbox" in r.text.lower():
        raise Blocked(f"sandbox blocked {host}")
    r.raise_for_status()
    cached.write_text(r.text)
    return r.text


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    print(f"wrote {len(rows):>6} rows -> {path.relative_to(ROOT)}")


def get_bytes(url: str, dest: Path, *, check_robots: bool = True) -> Path:
    """Download a binary file once (skipped if it already exists), throttled and robots-aware."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    if check_robots and not allowed_by_robots(url):
        raise Blocked(f"robots.txt disallows {url}")
    host = urlparse(url).netloc
    wait = MIN_DELAY_S - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    try:
        r = _session.get(url, timeout=60)
    except requests.exceptions.ProxyError as e:
        raise Blocked(f"network blocked for {host}: {e}") from e
    _last_hit[host] = time.time()
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest
