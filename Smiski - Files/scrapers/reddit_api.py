"""Fetch posts from r/smiski through the official Reddit API (OAuth, app-only).

Setup: create a "script" app at https://www.reddit.com/prefs/apps and export
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET   (and optionally REDDIT_USER_AGENT)
Reddit listings cap at ~1000 items each, so several sort orders are combined
and de-duplicated. Respect Reddit's Data API terms: keep raw posts private.
"""
from __future__ import annotations

import os
import time

import requests

from common import RAW, USER_AGENT, write_jsonl

SUBREDDITS = ["smiski"]
LISTINGS = [("new", {}), ("top", {"t": "all"}), ("top", {"t": "year"}), ("controversial", {"t": "all"})]


def token() -> str:
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        raise SystemExit("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (see docstring).")
    r = requests.post("https://www.reddit.com/api/v1/access_token", auth=(cid, secret),
                      data={"grant_type": "client_credentials"},
                      headers={"User-Agent": os.environ.get("REDDIT_USER_AGENT", USER_AGENT)}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def listing(tok: str, sub: str, sort: str, extra: dict, limit_pages: int = 10) -> list[dict]:
    headers = {"Authorization": f"bearer {tok}", "User-Agent": os.environ.get("REDDIT_USER_AGENT", USER_AGENT)}
    out, after = [], None
    for _ in range(limit_pages):
        r = requests.get(f"https://oauth.reddit.com/r/{sub}/{sort}", headers=headers, timeout=30,
                         params={"limit": 100, "after": after, "raw_json": 1, **extra})
        r.raise_for_status()
        data = r.json()["data"]
        out += [c["data"] for c in data["children"]]
        after = data.get("after")
        if not after:
            break
        time.sleep(1.1)
    return out


if __name__ == "__main__":
    tok = token()
    posts: dict[str, dict] = {}
    for sub in SUBREDDITS:
        for sort, extra in LISTINGS:
            for p in listing(tok, sub, sort, extra):
                posts[p["id"]] = dict(post_id=p["id"], created_utc=p["created_utc"], subreddit=sub,
                                      title=p.get("title", ""), body=p.get("selftext", ""),
                                      score=p.get("score"), num_comments=p.get("num_comments"))
    write_jsonl(RAW / "reddit_posts.jsonl", list(posts.values()))
