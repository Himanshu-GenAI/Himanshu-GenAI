#!/usr/bin/env python3
"""
fetch_contributions.py — refreshes data/contributions.json.

Pulls three things and writes them to one JSON file:

  * the public contribution calendar (per-day counts, scraped from
    github.com/users/<login>/contributions, which needs no token scope)
  * the public repository list + profile (REST API)
  * a timestamp

render.py reads only this file, so the cards can be rebuilt offline and the
daily GitHub Action has a single network step.

    python scripts/fetch_contributions.py
    GH_LOGIN=someone python scripts/fetch_contributions.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"

LOGIN = os.environ.get("GH_LOGIN", "Himanshu-GenAI")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
UA = "profile-cards/1.0 (+https://github.com/Himanshu-GenAI/Himanshu-GenAI)"

API = "https://api.github.com"


def get(url: str, accept: str = "application/vnd.github+json") -> str:
    headers = {"User-Agent": UA, "Accept": accept}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# contribution calendar
# --------------------------------------------------------------------------- #

CELL = re.compile(r"<td\b[^>]*>")
ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')
TOOLTIP = re.compile(
    r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>', re.S
)
COUNT = re.compile(r"([\d,]+)\s+contribution")


def fetch_days(login: str) -> list[dict]:
    """Scrape the contribution calendar into [{date, count}, ...]."""
    html = get(f"https://github.com/users/{login}/contributions", "text/html")

    # <td ... data-date="2025-11-09" id="contribution-day-component-0-0" ...>
    id_to_date: dict[str, str] = {}
    for tag in CELL.findall(html):
        attrs = dict(ATTR.findall(tag))
        cell_id, day = attrs.get("id", ""), attrs.get("data-date", "")
        if cell_id.startswith("contribution-day-component-") and day:
            id_to_date[cell_id] = day

    if not id_to_date:
        raise SystemExit("no contribution cells found — GitHub markup changed?")

    counts: dict[str, int] = {}
    for target, label in TOOLTIP.findall(html):
        day = id_to_date.get(target)
        if not day:
            continue
        match = COUNT.search(label)
        counts[day] = int(match.group(1).replace(",", "")) if match else 0

    days = [
        {"date": day, "count": counts.get(day, 0)} for day in sorted(id_to_date.values())
    ]
    return days


# --------------------------------------------------------------------------- #
# repositories + profile
# --------------------------------------------------------------------------- #


def fetch_repos(login: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while page <= 5:
        url = (
            f"{API}/users/{login}/repos"
            f"?per_page=100&page={page}&sort=pushed&direction=desc&type=owner"
        )
        try:
            batch = json.loads(get(url))
        except urllib.error.HTTPError as exc:
            print(f"  ! repo page {page}: HTTP {exc.code}", file=sys.stderr)
            break
        if not isinstance(batch, list) or not batch:
            break
        for repo in batch:
            repos.append(
                {
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "language": repo.get("language"),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "topics": repo.get("topics", []),
                    "license": (repo.get("license") or {}).get("spdx_id"),
                    "url": repo.get("html_url"),
                    "homepage": repo.get("homepage") or None,
                    "fork": repo.get("fork", False),
                    "private": repo.get("private", False),
                    "created_at": repo.get("created_at"),
                    "pushed_at": repo.get("pushed_at"),
                }
            )
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch_profile(login: str) -> dict:
    try:
        user = json.loads(get(f"{API}/users/{login}"))
    except urllib.error.HTTPError as exc:
        print(f"  ! profile: HTTP {exc.code}", file=sys.stderr)
        return {"login": login, "name": None}
    return {
        "login": user.get("login", login),
        "name": user.get("name"),
        "bio": user.get("bio"),
        "location": user.get("location"),
        "blog": user.get("blog") or None,
        "avatar_url": user.get("avatar_url"),
        "followers": user.get("followers", 0),
        "public_repos": user.get("public_repos", 0),
    }


# --------------------------------------------------------------------------- #


def main() -> None:
    print(f"→ contributions for {LOGIN}")
    days = fetch_days(LOGIN)
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"])
    print(f"  {len(days)} days · {total} contributions · {active} active")

    print("→ repositories + profile")
    repos = fetch_repos(LOGIN)
    profile = fetch_profile(LOGIN)
    print(f"  {len(repos)} repos")

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "profile": profile,
        "range": {"from": days[0]["date"], "to": days[-1]["date"]},
        "days": days,
        "repos": repos,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"✓ wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
