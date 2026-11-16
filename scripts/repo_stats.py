#!/usr/bin/env python3
"""Public GitHub signals for a repo, via the REST API (no gh CLI needed).

Usage:
  python3 repo_stats.py <owner/repo | github URL> [--out stats.json]

Uses $GITHUB_TOKEN if set (higher rate limit). Read-only; sends no user data.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def get(path, accept="application/vnd.github+json"):
    req = urllib.request.Request(API + path, headers={"Accept": accept, "User-Agent": "vet-this-skill"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), r.headers
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_msg": e.read().decode(errors="ignore")[:300]}, {}


def last_page(headers):
    m = re.search(r'page=(\d+)>; rel="last"', headers.get("Link", "") if headers else "")
    return int(m.group(1)) if m else 1


def days_since(iso):
    if not iso:
        return None
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (dt.datetime.now(dt.timezone.utc) - t).days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out")
    a = ap.parse_args()
    # Accepts owner/repo or any github.com URL, including /tree/... and ?query paths.
    parts = [p for p in a.repo.split("github.com/")[-1].split("#")[0].split("?")[0].split("/") if p]
    if len(parts) < 2:
        sys.exit("Could not parse owner/repo from: " + a.repo)
    owner, name = parts[0], parts[1].removesuffix(".git")

    repo, _ = get(f"/repos/{owner}/{name}")
    if "_error" in repo:
        print(json.dumps({"error": repo}, indent=2))
        sys.exit(2)

    s = {
        "full_name": repo["full_name"],
        "description": repo.get("description"),
        "homepage": repo.get("homepage"),
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "watchers": repo.get("subscribers_count"),
        "open_issues_and_prs": repo["open_issues_count"],
        "license": (repo.get("license") or {}).get("spdx_id"),
        "language": repo.get("language"),
        "created_at": repo["created_at"],
        "age_days": days_since(repo["created_at"]),
        "pushed_at": repo["pushed_at"],
        "days_since_push": days_since(repo["pushed_at"]),
        "archived": repo.get("archived"),
        "fork_of": (repo.get("parent") or {}).get("full_name"),
        "default_branch": repo.get("default_branch"),
        "topics": repo.get("topics", []),
    }
    s["stars_per_day"] = round(s["stars"] / max(s["age_days"] or 1, 1), 1)

    _, h = get(f"/repos/{owner}/{name}/contributors?per_page=1&anon=1")
    s["contributors"] = last_page(h)
    _, h = get(f"/repos/{owner}/{name}/commits?per_page=1")
    s["commits"] = last_page(h)

    rel, _ = get(f"/repos/{owner}/{name}/releases?per_page=3")
    s["recent_releases"] = [{"tag": r["tag_name"], "date": r["published_at"],
                             "assets": [x["name"] for x in r.get("assets", [])]}
                            for r in rel] if isinstance(rel, list) else []

    iss, _ = get(f"/repos/{owner}/{name}/issues?state=all&per_page=15&sort=comments")
    s["most_discussed_issues"] = [{"n": i["number"], "title": i["title"], "state": i["state"],
                                   "comments": i["comments"], "is_pr": "pull_request" in i}
                                  for i in iss] if isinstance(iss, list) else []

    # Star velocity: dates of the most recent stargazers.
    pages = max(1, (s["stars"] + 99) // 100)
    if s["stars"]:
        sg, _ = get(f"/repos/{owner}/{name}/stargazers?per_page=100&page={min(pages, 400)}",
                    accept="application/vnd.github.star+json")
        if isinstance(sg, list) and sg:
            dates = sorted(x["starred_at"] for x in sg if "starred_at" in x)
            if dates:
                span = max((days_since(dates[0]) or 0) - (days_since(dates[-1]) or 0), 1)
                s["recent_star_sample"] = {"count": len(dates), "from": dates[0], "to": dates[-1],
                                           "approx_stars_per_day": round(len(dates) / span, 1)}

    user, _ = get(f"/users/{owner}")
    if "_error" not in user:
        s["owner"] = {"login": user["login"], "type": user["type"], "created_at": user["created_at"],
                      "account_age_days": days_since(user["created_at"]),
                      "public_repos": user["public_repos"], "followers": user["followers"],
                      "blog": user.get("blog"), "company": user.get("company")}

    txt = json.dumps(s, indent=2)
    if a.out:
        open(a.out, "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
