#!/usr/bin/env python3
"""Regenerate the marked regions of the drsamonline profile README.

Reads the catalogue (catalogue.json), reconciles it against the owner's live
repositories, and rewrites only the regions of README.md that sit between the
HTML comment markers. Everything outside the markers is human-written and is
never touched.

RECONCILIATION — why the profile keeps itself current
-----------------------------------------------------
A new repository used to appear under "Other / New" carrying its raw GitHub
description, and stayed there until somebody edited a data file by hand. That
is the manual step this removes.

GitHub owns the description. Edit a repository's description on GitHub and both
this README and the hub follow on the next run. Two optional flags on an entry:

  "pin": true     do not take the description from GitHub for this repo. Use it
                  for a description that must stay as written here.
  "auto": true    set by this script when it created the entry. It marks the
                  CATEGORY as a guess, and the run prints those names so a wrong
                  guess is visible rather than silent. Clearing it means a human
                  has looked at the category.

Category, featured, demo, release, kicker and tag have no equivalent on GitHub,
so they live here and only here — that is the part worth curating. Everything
else maintains itself.

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
DATA_FILE = os.path.join(ROOT, "catalogue.json")
README = os.path.join(ROOT, "README.md")

BADGES_START, BADGES_END = "<!-- BADGES:START -->", "<!-- BADGES:END -->"
PROJ_START, PROJ_END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"

DEFAULT_LABELS = {
    "desktop": "Desktop, System & Developer Tools",
    "games": "Games & Engines",
    "health": "Health & Medicine",
    "mind": "Mind, Memory & Wellbeing",
    "audio": "Audio & Media",
    "business": "Business & Productivity",
    "learning": "Learning & Reference",
    "weft": "Weft-8 & Retrocomputing",
    "kits": "Libraries & Kits",
    "chce": "CHCE Compression",
    "infra": "Meta & Infrastructure",
    "other": "Other / New",
}

# How an uncurated repository is placed. Ordered: the first rule that matches
# wins, so the specific domains come before the general ones. "other" is the
# honest answer when nothing matches, and the run prints those names rather than
# filing them somewhere plausible but wrong.
INFER_RULES = [
    ("health", ("homeopath", "materia medica", "repertor", "remed", "clinical",
                "patient", "hospital", "physician", "pediatric", "first aid")),
    ("weft", ("weft-8", "weft8", "jacquard", "loom", "assembly")),
    ("games", ("game", "engine", "shooter", "rpg", "arcade", "visual novel",
               "puzzle", "idle", "platformer")),
    ("audio", ("audio", "music", "sound", "synth", "composer")),
    ("chce", ("chce", "compression", "compressor", "zip")),
    ("learning", ("learn", "teach", "classroom", "study", "reference", "almanac",
                  "panchang", "poetry", "course", "textbook")),
    ("mind", ("journal", "wellbeing", "meditat", "habit", "focus", "mindful",
              "reading", "gratitude", "notes")),
    ("business", ("billing", "invoice", "gst", "business", "canteen", "clipboard",
                  "whiteboard", "productivity", "store", "shop")),
    ("infra", ("workflow", "tooling", "build kit", "audit", "backup", "dashboard",
               "catalogue", "infrastructure", "pipeline", "ci ")),
]


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


def infer_category(repo):
    """Best guess at where a new repo belongs, from its name, description and topics."""
    name = (repo.get("name") or "").lower()
    text = " ".join([(repo.get("description") or "").lower(),
                     " ".join(repo.get("topics") or []).lower(), name])
    if name.endswith("-kit"):
        return "kits"
    for cat, keys in INFER_RULES:
        if any(k in text for k in keys):
            return cat
    return "other"


def sync_catalogue(data, api_repos, labels):
    """Add repositories nobody has catalogued yet; refresh entries we created.

    Returns (changed, added, refreshed, uncategorised, stale) and mutates ``data``.
    """
    repos = data.setdefault("repos", {})
    index = {name.lower(): name for name in repos}
    known = {m.lower() for m in data.get("metaRepos", [])}
    live = set()

    added, refreshed, uncategorised = [], [], []
    for repo in api_repos:
        name = repo.get("name")
        if not name or repo.get("fork"):
            continue
        key = name.lower()
        if key in known:
            continue
        live.add(key)

        entry = repos.get(index.get(key, "")) if key in index else None
        if entry is None:
            cat = infer_category(repo)
            entry = {
                "description": (repo.get("description") or "").strip() or "No description yet.",
                "category": cat,
                "featured": False,
                "demo": bool(repo.get("has_pages")),
                "release": False,
                "kicker": "",
                "tag": "",
                "auto": True,
            }
            repos[name] = entry
            added.append((name, cat))
            if cat == "other":
                uncategorised.append(name)
            continue

        # GitHub is the source of the description; "pin" is the opt-out.
        if not entry.get("pin"):
            live_desc = (repo.get("description") or "").strip() or "No description yet."
            if entry.get("description") != live_desc:
                entry["description"] = live_desc
                refreshed.append(name)

    stale = [name for name in repos if name.lower() not in live]
    data["repos"] = dict(sorted(repos.items(), key=lambda kv: kv[0].lower()))
    changed = bool(added or refreshed)
    return changed, added, refreshed, uncategorised, stale


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
        else:  # only reachable if sync was skipped
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
    return pattern.sub(lambda _m: start + "\n\n" + content.strip() + "\n\n" + end, text, count=1)


def main():
    with open(DATA_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    labels = {c["key"]: c["label"] for c in data.get("categories", [])}

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    api_repos = fetch_repos(token)
    public_repos = fetch_public_repo_count(token)

    changed, added, refreshed, uncategorised, stale = sync_catalogue(data, api_repos, labels)
    if changed:
        with open(DATA_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print("catalogue updated: %d added, %d refreshed from GitHub"
              % (len(added), len(refreshed)))
        for name, cat in added:
            print("  added %-46s -> %s" % (name, cat))
        for name in refreshed:
            print("  refreshed %s" % name)
    if uncategorised:
        print("::notice::%d new repo(s) need a category: %s"
              % (len(uncategorised), ", ".join(uncategorised)))
    if stale:
        print("::warning::catalogue lists %d repo(s) that no longer exist: %s"
              % (len(stale), ", ".join(sorted(stale))))

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
