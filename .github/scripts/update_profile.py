#!/usr/bin/env python3
"""Regenerate the marked regions of the drsamonline profile README.

Reads the curated map (profile-data.json), fetches the owner's public repos
from the GitHub API using the runner's authenticated token, merges the two,
and rewrites only the regions of README.md that sit between the HTML comment
markers.  Everything outside the markers is human-written and is never touched.

Env overrides (used by the tests / the auto-pickup proof):
  MOCK_REPOS_JSON    path to a JSON file holding the repo list (skips the API)
  MOCK_PUBLIC_REPOS  integer public-repo count (skips the API)
  GH_TOKEN / GITHUB_TOKEN  token for the API calls
"""
import json
import os
import re
import sys
import urllib.request

OWNER = "drsamonline"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FILE = os.path.join(ROOT, "profile-data.json")
README = os.path.join(ROOT, "README.md")

BADGES_START, BADGES_END = "<!-- BADGES:START -->", "<!-- BADGES:END -->"
PROJ_START, PROJ_END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"

DEFAULT_LABELS = {
    "desktop": "Desktop & System Tools",
    "games": "Games & Engines",
    "health": "Health & Medicine",
    "mind": "Mind & Wellbeing",
    "audio": "Audio & Media",
    "business": "Business & Productivity",
    "meta": "Meta & Infrastructure",
    "other": "Other / New",
}


def _get_json(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "drsamonline-profile-updater",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp), resp.headers


def fetch_repos(token):
    mock = os.environ.get("MOCK_REPOS_JSON")
    if mock:
        with open(mock, encoding="utf-8") as fh:
            data = json.load(fh)
        return data["repositories"] if isinstance(data, dict) else data

    repos, url = [], "https://api.github.com/users/%s/repos?per_page=100&sort=full_name" % OWNER
    while url:
        page, headers = _get_json(url, token)
        repos.extend(page)
        link = headers.get("Link", "")
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = nxt.group(1) if nxt else None
    return repos


def fetch_public_repo_count(token):
    mock = os.environ.get("MOCK_PUBLIC_REPOS")
    if mock:
        return int(mock)
    user, _ = _get_json("https://api.github.com/users/%s" % OWNER, token)
    return int(user["public_repos"])


def build_projects(api_repos, data):
    curated = {k.lower(): v for k, v in data.get("repos", {}).items()}
    meta = {m.lower() for m in data.get("metaRepos", [])}
    out = []
    for repo in api_repos:
        name = repo["name"]
        if repo.get("fork"):
            continue
        if name.lower() in meta:
            continue
        entry = curated.get(name.lower())
        if entry:
            desc, cat = entry["description"], entry["category"]
            feat = bool(entry.get("featured"))
        else:  # a brand-new repo nobody has curated yet
            desc = (repo.get("description") or "").strip() or "No description yet."
            cat, feat = "other", False
        landing = ("https://%s.github.io/%s/" % (OWNER, name)
                   if repo.get("has_pages") else repo["html_url"])
        out.append({"name": name, "desc": desc, "cat": cat,
                    "featured": feat, "landing": landing, "source": repo["html_url"]})
    return out


def render_badges(public_repos, project_count):
    return (
        '<div align="center">\n\n'
        '<img src="https://img.shields.io/github/followers/%s?style=flat-square&label=Followers"'
        ' alt="GitHub followers" onerror="this.style.display=\'none\'" />\n'
        '<img src="https://img.shields.io/badge/Public%%20repos-%d-blue?style=flat-square"'
        ' alt="%d public repositories" onerror="this.style.display=\'none\'" />\n'
        '<img src="https://img.shields.io/badge/Projects-%d-blueviolet?style=flat-square"'
        ' alt="%d projects" onerror="this.style.display=\'none\'" />\n\n'
        '</div>' % (OWNER, public_repos, public_repos, project_count, project_count)
    )


def render_projects(projects, labels):
    def key(p):
        return p["name"].lower()

    lines = ["## Featured", ""]
    for p in sorted([p for p in projects if p["featured"]], key=key):
        lines.append('- **[%s](%s)** \u2014 %s &nbsp;\u00b7&nbsp; [source](%s)'
                     % (p["name"], p["landing"], p["desc"], p["source"]))
    lines += ["", "## Projects by category", ""]
    order = list(labels.keys())
    if "other" not in order:
        order.append("other")
    for cat in order:
        group = sorted([p for p in projects if p["cat"] == cat], key=key)
        if not group:
            continue
        lines.append("### " + labels.get(cat, DEFAULT_LABELS.get(cat, cat.title())))
        for p in group:
            lines.append('- [%s](%s) \u2014 %s' % (p["name"], p["landing"], p["desc"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def replace_region(text, start, end, content):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        sys.exit("ERROR: markers %s / %s not found in README.md" % (start, end))
    return pattern.sub(lambda _m: start + "\n" + content.rstrip() + "\n" + end, text, count=1)


def main():
    with open(DATA_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    labels = {c["key"]: c["label"] for c in data.get("categories", [])}

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    api_repos = fetch_repos(token)
    public_repos = fetch_public_repo_count(token)
    projects = build_projects(api_repos, data)

    with open(README, encoding="utf-8") as fh:
        readme = fh.read()

    readme = replace_region(readme, BADGES_START, BADGES_END,
                            render_badges(public_repos, len(projects)))
    readme = replace_region(readme, PROJ_START, PROJ_END,
                            render_projects(projects, labels))
    if not readme.endswith("\n"):
        readme += "\n"

    with open(README, "w", encoding="utf-8") as fh:
        fh.write(readme)

    print("OK public_repos=%d projects=%d (featured=%d)"
          % (public_repos, len(projects), sum(1 for p in projects if p["featured"])))


if __name__ == "__main__":
    main()
