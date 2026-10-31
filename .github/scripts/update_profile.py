#!/usr/bin/env python3
"""Regenerate the marked regions of the drsamonline profile README.

Reads the catalogue (catalogue.json), reconciles it against the owner's live
repositories, and rewrites only the regions of README.md that sit between the
HTML comment markers. Everything outside the markers is human-written and is
never touched.

RECONCILIATION — why the profile keeps itself current
-----------------------------------------------------
A new repository used to appear under "Other / New" carrying its raw GitHub
description, and stayed there until somebody edited a data file by hand.

GitHub owns the description. Edit a repository's description on GitHub and both
this README and the hub follow on the next run. Two optional flags on an entry:

  "pin": true     do not take the description from GitHub for this repo.
  "auto": true    set by this script when it created the entry. It marks the
                  CATEGORY as a guess, and the run prints those names.

Category, featured, demo, release, kicker and tag have no equivalent on GitHub,
so they live in the catalogue and only there.

VISUALS
-------
GitHub strips CSS and scripts from a README, so every coloured element has to be
an image. This script therefore draws, and commits:

  assets/pills/<repo>.svg        a coloured name pill per project
  assets/pills/count-<cat>.svg   the category count pill
  assets/achievements/<slug>.svg GitHub achievement cards
  assets/stats-{light,dark}.svg  the counters strip

All of them are generated from the same numbers as the text beside them, so the
picture and the words cannot disagree.

Env overrides (used by the tests / the auto-pickup proof):
  MOCK_REPOS_JSON    path to a JSON file holding the repo list (skips the API)
  MOCK_PUBLIC_REPOS  integer public-repo count (skips the API)
  MOCK_PROFILE_HTML  path to a saved github.com/<owner> page (skips the fetch)
  GH_TOKEN / GITHUB_TOKEN  token for the API calls
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

OWNER = "drsamonline"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FILE = os.path.join(ROOT, "catalogue.json")
README = os.path.join(ROOT, "README.md")
PILLS = os.path.join(ROOT, "assets", "pills")
ACHIEVEMENTS = os.path.join(ROOT, "assets", "achievements")

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

PROJ_START, PROJ_END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"
ACH_START, ACH_END = "<!-- ACHIEVEMENTS:START -->", "<!-- ACHIEVEMENTS:END -->"

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

DEFAULT_COLOURS = {
    "desktop": "#1D4ED8", "games": "#6D28D9", "health": "#15803D",
    "mind": "#0F766E", "audio": "#C2410C", "business": "#A21CAF",
    "learning": "#A16207", "weft": "#475569", "kits": "#0369A1",
    "chce": "#B91C1C", "infra": "#334155", "other": "#52525B",
}

# GitHub's own achievement colours, echoed here so the cards read as a set.
ACHIEVEMENT_COLOURS = {
    "pull-shark": "#0369A1", "quickdraw": "#C2410C", "yolo": "#6D28D9",
    "pair-extraordinaire": "#15803D", "starstruck": "#A16207",
    "galaxy-brain": "#0F766E", "public-sponsor": "#A21CAF",
    "arctic-code-vault": "#334155",
}

# Advance widths in 1/1000 em for a bold humanist sans. Used to size a pill so
# the label cannot overflow it. Deliberately a touch generous: a pill that is
# 4px wide of the text looks fine, one that clips a letter does not.
_ADV = {
    " ": 278, "!": 333, '"': 474, "#": 556, "$": 556, "%": 889, "&": 722,
    "'": 238, "(": 333, ")": 333, "*": 389, "+": 584, ",": 278, "-": 333,
    ".": 278, "/": 278, ":": 333, ";": 333, "<": 584, "=": 584, ">": 584,
    "?": 611, "@": 975, "_": 556, "|": 280, "~": 584, "`": 333,
    "0": 556, "1": 556, "2": 556, "3": 556, "4": 556, "5": 556, "6": 556,
    "7": 556, "8": 556, "9": 556,
    "A": 722, "B": 722, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 556, "K": 722, "L": 611, "M": 833, "N": 722,
    "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722,
    "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "a": 556, "b": 611, "c": 556, "d": 611, "e": 556, "f": 333, "g": 611,
    "h": 611, "i": 278, "j": 278, "k": 556, "l": 278, "m": 889, "n": 611,
    "o": 611, "p": 611, "q": 611, "r": 389, "s": 556, "t": 333, "u": 611,
    "v": 556, "w": 778, "x": 556, "y": 556, "z": 500,
}

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


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def _get_json(url, token):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "drsamonline-profile-updater"}
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


def fetch_achievements():
    """Scrape the profile page for GitHub achievements.

    There is no API for these: they exist only as badges in the profile sidebar,
    each an <a> carrying href=...?achievement=<slug>, alt="Achievement: <name>"
    and, where it has one, a tier label and an "xN" counter.

    Any failure returns an empty list, and the section is left out. A missing
    achievements row is a small loss; a broken README is not.
    """
    mock = os.environ.get("MOCK_PROFILE_HTML")
    try:
        if mock:
            with open(mock, encoding="utf-8", errors="ignore") as fh:
                html = fh.read()
        else:
            req = urllib.request.Request(
                "https://github.com/%s" % OWNER,
                headers={"User-Agent": "Mozilla/5.0 (profile-updater)",
                         "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", "ignore")
    except Exception as exc:                                    # noqa: BLE001
        print("::warning::could not read achievements from github.com (%s)" % exc)
        return []

    out, seen = [], set()
    for m in re.finditer(r'href="[^"]*achievement=([a-z0-9\-]+)[^"]*"[^>]*>(.*?)</a>',
                         html, re.S):
        slug, block = m.group(1), m.group(2)
        alt = re.search(r'alt="Achievement: ([^"]+)"', block)
        if slug in seen or not alt:
            continue
        seen.add(slug)
        tier = re.search(r"achievement-tier-label--(\w+)", block)
        cnt = re.search(r">\s*x(\d+)\s*<", block)
        out.append({"slug": slug, "name": alt.group(1),
                    "tier": (tier.group(1).capitalize() if tier else ""),
                    "count": int(cnt.group(1)) if cnt else 1})
    return out


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #
def text_width(text, size):
    """Approximate rendered width, in px, of bold text at ``size``."""
    total = sum(_ADV.get(ch, 600) for ch in text) / 1000.0 * size
    return total + 0.2 * len(text)          # letter-spacing


def pill_svg(label, colour, size=11.5, height=24, pad=11):
    """A rounded, solid-colour pill with white bold text — the category colour."""
    w = int(round(text_width(label, size) * 1.04 + 2 * pad))
    baseline = height / 2.0 + size * 0.36
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img" aria-label="%s">'
            '<rect width="%d" height="%d" rx="%d" fill="%s"/>'
            '<text x="%d" y="%.1f" text-anchor="middle" font-family="%s" '
            'font-size="%s" font-weight="700" letter-spacing="0.2" fill="#FFFFFF">%s</text>'
            '</svg>' % (w, height, w, height, esc(label), w, height, height // 2, colour,
                        w // 2, baseline, FONT, size, esc(label)))


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def achievement_svg(name, tier, count, colour):
    """A solid-colour card: medal glyph, achievement name, tier and count."""
    meta = tier.upper() if tier else "EARNED"
    if count and count > 1:
        meta += "  \u00b7  \u00d7%d" % count
    w, h = 272, 78
    medal = ('<circle cx="38" cy="34" r="12.5" fill="none" stroke="#FFFFFF" '
             'stroke-width="1.8" stroke-opacity="0.9"/>'
             '<path d="M32 44 l-3 9 9-4 9 4-3-9" fill="none" stroke="#FFFFFF" '
             'stroke-width="1.8" stroke-linejoin="round" stroke-opacity="0.9"/>'
             '<path d="M38 27.5 l2.1 4.3 4.7.7-3.4 3.3.8 4.7-4.2-2.2-4.2 2.2.8-4.7-3.4-3.3 4.7-.7Z" '
             'fill="#FFFFFF" fill-opacity="0.95"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'role="img" aria-label="%s">'
            '<rect width="%d" height="%d" rx="12" fill="%s"/>'
            '%s'
            '<text x="62" y="34" font-family="%s" font-size="14.5" font-weight="700" '
            'fill="#FFFFFF">%s</text>'
            '<text x="62" y="53" font-family="%s" font-size="10" font-weight="600" '
            'letter-spacing="1.6" fill="#FFFFFF" fill-opacity="0.78">%s</text>'
            '</svg>' % (w, h, w, h, esc("%s, %s" % (name, meta)), w, h, colour, medal,
                        FONT, esc(name), FONT, esc(meta)))


def write_if_changed(path, text):
    """Only touch the file when the bytes differ — keeps commits honest."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            if fh.read() == text:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return True


def prune(directory, keep):
    """Remove generated files this run did not produce. Only ever inside ``directory``."""
    if not os.path.isdir(directory):
        return []
    gone = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".svg") and name not in keep:
            os.remove(os.path.join(directory, name))
            gone.append(name)
    return gone


def write_pills(projects, colours, labels):
    """One pill per project, plus one count pill per category. Returns {name: href}."""
    written, hrefs = 0, {}
    keep = set()
    for p in projects:
        slug = p["slug"]
        path = os.path.join(PILLS, "%s.svg" % slug)
        keep.add("%s.svg" % slug)
        if write_if_changed(path, pill_svg(p["name"], colours.get(p["cat"], "#52525B"))):
            written += 1
        hrefs[p["name"]] = "assets/pills/%s.svg" % slug

    counts = {}
    for p in projects:
        counts[p["cat"]] = counts.get(p["cat"], 0) + 1
    for cat, n in counts.items():
        name = "count-%s.svg" % cat
        keep.add(name)
        if write_if_changed(os.path.join(PILLS, name),
                            pill_svg(str(n), colours.get(cat, "#52525B"), size=12.5, height=22)):
            written += 1
    gone = prune(PILLS, keep)
    if written or gone:
        print("pills: %d written, %d removed" % (written, len(gone)))
    return hrefs


def write_achievements(achievements):
    """One card per achievement. Returns the list with its asset path attached."""
    written, keep = 0, set()
    for a in achievements:
        name = "%s.svg" % a["slug"]
        keep.add(name)
        colour = ACHIEVEMENT_COLOURS.get(a["slug"], "#334155")
        if write_if_changed(os.path.join(ACHIEVEMENTS, name),
                            achievement_svg(a["name"], a["tier"], a["count"], colour)):
            written += 1
        a["asset"] = "assets/achievements/%s" % name
    gone = prune(ACHIEVEMENTS, keep) if achievements else []
    if written or gone:
        print("achievements: %d written, %d removed" % (written, len(gone)))
    return achievements


# Tier thresholds, in order: badge, bronze, silver, gold. GitHub never publishes
# "how far am I from the next tier", so this is computed from the counters the API
# does give us, checked against the tier the profile page already shows.
THRESHOLDS = {
    "pull-shark": [2, 16, 128, 1024],
    "starstruck": [16, 128, 512, 4096],
    "pair-extraordinaire": [1, 10, 24, 48],
    "galaxy-brain": [2, 8, 16, 32],
}
TIER_LABEL = ["badge", "bronze", "silver", "gold"]
TIER_INDEX = {"": -1, "default": 0, "bronze": 1, "silver": 2, "gold": 3}


def fetch_merged_pr_count(token):
    """Merged pull requests authored by the owner — what Pull Shark counts."""
    mock = os.environ.get("MOCK_MERGED_PRS")
    if mock:
        return int(mock)
    url = ("https://api.github.com/search/issues?per_page=1&q="
           + urllib.parse.quote("is:pr author:%s is:merged" % OWNER))
    try:
        data, _ = _get_json(url, token)
        return int(data.get("total_count", 0))
    except Exception as exc:                                    # noqa: BLE001
        print("::warning::could not count merged PRs (%s)" % exc)
        return None


STATS_THEME = {
    "light": dict(paper="#F7F8FA", border="#E4E8EF", ink="#12161E", muted="#5A6473", accent="#3E6C9E"),
    "dark": dict(paper="#0F131A", border="#232A35", ink="#EDF1F7", muted="#9AA6B8", accent="#7FB0E0"),
}


def render_stats(theme, cells):
    """The strip under the hero. Drawn from live numbers, so it never lies."""
    t = STATS_THEME[theme]
    n = len(cells)
    w = 1200 // n
    parts = []
    for i, (value, label) in enumerate(cells):
        cx = i * w + w // 2
        if i:
            parts.append('<path d="M %d 36 V 132" stroke="%s" stroke-width="1"/>'
                         % (i * w, t["border"]))
        parts.append('<text x="%d" y="86" text-anchor="middle" font-family="%s" '
                     'font-size="50" font-weight="700" fill="%s">%s</text>'
                     % (cx, FONT, t["ink"], value))
        parts.append('<text x="%d" y="116" text-anchor="middle" font-family="%s" '
                     'font-size="14.5" font-weight="600" letter-spacing="1.6" fill="%s">%s</text>'
                     % (cx, FONT, t["muted"], label))
    aria = " \u00b7 ".join("%s %s" % (v, l.title()) for v, l in cells)
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="168" viewBox="0 0 1200 168" role="img" aria-label="{aria}">
  <rect width="1200" height="168" fill="{paper}"/>
  <rect x="0.5" y="0.5" width="1199" height="167" fill="none" stroke="{border}"/>
  <path d="M 0 0 H 1200" stroke="{accent}" stroke-width="2"/>
  {parts}
</svg>
""".format(aria=aria, parts="\n  ".join(parts), **t)


def progress_rows(achievements, api_repos, merged_prs):
    """One row per tiered achievement: what we know, and what the next tier costs.

    Pull Shark and Starstruck have exact counters (merged PRs, stars on the best
    repo). Pair Extraordinaire and Galaxy Brain do not — GitHub publishes neither,
    and counting co-authored PRs from the API gives a wrong number — so those show
    the tier it reports and the threshold to beat, and no invented progress.
    """
    earned = {a["slug"]: a["tier"].lower() for a in achievements}
    meta = {"drsamonline", "drsamonline.github.io"}
    stars = max([r.get("stargazers_count") or 0 for r in api_repos
                 if r.get("name", "").lower() not in meta] or [0])

    measured = {"pull-shark": merged_prs, "starstruck": stars}
    rows = []
    for slug in ("pull-shark", "starstruck", "pair-extraordinaire", "galaxy-brain"):
        steps = THRESHOLDS[slug]
        tier = earned.get(slug, "")
        value = measured.get(slug)
        exact = value is not None
        if not exact:
            # A badge with no tier label is the base tier, not an absent one — but
            # only if the profile actually lists it. Absent from the list means 0.
            idx = max(0, TIER_INDEX.get(tier, -1)) if slug in earned else -1
            value = steps[idx] if idx >= 0 else 0      # the floor that tier guarantees

        nxt = next((i for i, t in enumerate(steps) if t > value), None)
        if nxt is None:
            ratio, target, next_label = 1.0, steps[-1], "gold \u00b7 maxed"
        else:
            ratio, target = value / float(steps[nxt]), steps[nxt]
            next_label = "next %s at %s" % (TIER_LABEL[nxt], "{:,}".format(steps[nxt]))

        rows.append({
            "slug": slug,
            "name": {"pull-shark": "Pull Shark", "starstruck": "Starstruck",
                     "pair-extraordinaire": "Pair Extraordinaire",
                     "galaxy-brain": "Galaxy Brain"}[slug],
            "unit": {"pull-shark": "merged pull requests", "starstruck": "stars on one repository",
                     "pair-extraordinaire": "co-authored merged PRs",
                     "galaxy-brain": "accepted answers"}[slug],
            "value": value, "target": target, "ratio": min(ratio, 1.0),
            "tier": tier or ("badge" if slug in earned else "not yet"),
            "next": next_label, "exact": exact,
            "colour": ACHIEVEMENT_COLOURS.get(slug, "#334155"),
        })
    return rows


def render_progress(theme, rows):
    """Four labelled bars. The number on the right is the one GitHub will not show."""
    t = STATS_THEME[theme]
    height = 20 + 58 * len(rows)
    parts = []
    for i, r in enumerate(rows):
        y = 20 + i * 58
        if i:
            parts.append('<path d="M 36 %d H 1164" stroke="%s" stroke-width="1"/>'
                         % (y - 6, t["border"]))
        parts.append('<text x="36" y="%d" font-family="%s" font-size="15" font-weight="700" '
                     'fill="%s">%s</text>' % (y + 20, FONT, t["ink"], esc(r["name"])))
        parts.append('<text x="36" y="%d" font-family="%s" font-size="11" fill="%s">%s</text>'
                     % (y + 38, FONT, t["muted"], esc(r["unit"])))

        parts.append('<rect x="300" y="%d" width="660" height="12" rx="6" fill="%s"/>'
                     % (y + 12, t["border"]))
        filled = 660 * r["ratio"]
        if filled >= 12:
            parts.append('<rect x="300" y="%d" width="%.0f" height="12" rx="6" fill="%s"/>'
                         % (y + 12, filled, r["colour"]))

        shown = "{:,}".format(r["value"]) + ("+" if not r["exact"] and r["value"] else "")
        parts.append('<text x="1164" y="%d" text-anchor="end" font-family="%s" font-size="15" '
                     'font-weight="700" fill="%s">%s / %s</text>'
                     % (y + 20, FONT, t["ink"], shown, "{:,}".format(r["target"])))
        parts.append('<text x="1164" y="%d" text-anchor="end" font-family="%s" font-size="10.5" '
                     'font-weight="600" letter-spacing="1.2" fill="%s">%s \u00b7 %s</text>'
                     % (y + 38, FONT, t["muted"], r["tier"].upper(), r["next"].upper()))

    aria = "; ".join("%s %s of %s" % (r["name"], r["value"], r["target"]) for r in rows)
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{h}" viewBox="0 0 1200 {h}" role="img" aria-label="{aria}">
  <rect width="1200" height="{h}" fill="{paper}"/>
  <rect x="0.5" y="0.5" width="1199" height="{hm}" fill="none" stroke="{border}"/>
  <path d="M 0 0 H 1200" stroke="{accent}" stroke-width="2"/>
  {parts}
</svg>
""".format(h=height, hm=height - 1, aria=esc(aria), parts="\n  ".join(parts), **t)


def write_progress(rows):
    if not rows:
        return False
    for theme in ("light", "dark"):
        write_if_changed(os.path.join(ROOT, "assets", "progress-%s.svg" % theme),
                         render_progress(theme, rows))
    print("progress: " + ", ".join("%s %s/%s" % (r["slug"], r["value"], r["target"]) for r in rows))
    return True


def write_stats(projects, api_repos, public_repos):
    cats = {p["cat"] for p in projects}
    meta = {"drsamonline", "drsamonline.github.io"}
    live = [r for r in api_repos
            if r.get("name") and not r.get("fork") and r["name"].lower() not in meta]
    web = sum(1 for r in live if r.get("has_pages"))
    langs = {r.get("language") for r in live if r.get("language")}
    cells = [(len(projects), "PROJECTS"), (len(cats), "PURPOSES"),
             (web, "WEB EDITIONS"), (len(langs), "LANGUAGES"),
             (public_repos, "REPOSITORIES")]
    for theme in ("light", "dark"):
        write_if_changed(os.path.join(ROOT, "assets", "stats-%s.svg" % theme),
                         render_stats(theme, cells))
    print("stats: " + " \u00b7 ".join("%s %s" % (v, l.lower()) for v, l in cells))


# --------------------------------------------------------------------------- #
# catalogue
# --------------------------------------------------------------------------- #
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


def sync_catalogue(data, api_repos):
    """Add repositories nobody has catalogued yet; refresh descriptions from GitHub."""
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
            repos[name] = {
                "description": (repo.get("description") or "").strip() or "No description yet.",
                "category": cat,
                "featured": False,
                "demo": bool(repo.get("has_pages")),
                "release": False,
                "kicker": "",
                "tag": "",
                "auto": True,
            }
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
    return bool(added or refreshed), added, refreshed, uncategorised, stale


def build_projects(api_repos, data):
    curated = {k.lower(): v for k, v in data.get("repos", {}).items()}
    meta = {m.lower() for m in data.get("metaRepos", [])}
    out = []
    for repo in api_repos:
        name = repo["name"]
        if repo.get("fork") or name.lower() in meta:
            continue
        entry = curated.get(name.lower())
        if entry:
            desc, cat = entry["description"], entry["category"]
            feat = bool(entry.get("featured"))
        else:
            desc = (repo.get("description") or "").strip() or "No description yet."
            cat, feat = "other", False
        landing = ("https://%s.github.io/%s/" % (OWNER, name)
                   if repo.get("has_pages") else repo["html_url"])
        out.append({"name": name, "slug": name.lower(), "desc": desc, "cat": cat,
                    "featured": feat, "landing": landing, "source": repo["html_url"]})
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def heading(cat, label, count):
    """A category heading with its coloured count pill, keeping a real anchor slug."""
    return ('### <img src="assets/icons/%s.svg" width="20" height="20" alt=""> %s '
            '<img src="assets/pills/count-%s.svg" height="22" alt="%d projects">'
            % (cat, label, cat, count))


def render_projects(projects, labels, pills):
    def key(p):
        return p["name"].lower()

    # The pill IS the name and the link: one coloured object per row, then the
    # description in plain text. Repeating the name as bold text as well made every
    # line say everything twice.
    lines = ["## Start here", ""]
    for p in sorted([p for p in projects if p["featured"]], key=key):
        lines.append('- <a href="%s"><img src="%s" height="24" alt="%s"></a> \u2014 %s &nbsp;\u00b7&nbsp; [source](%s)'
                     % (p["landing"], pills[p["name"]], p["name"], p["desc"], p["source"]))
    lines += ["", "## Everything, by purpose", ""]
    order = list(labels.keys())
    if "other" not in order:
        order.append("other")
    for cat in order:
        group = sorted([p for p in projects if p["cat"] == cat], key=key)
        if not group:
            continue
        lines.append(heading(cat, labels.get(cat, DEFAULT_LABELS.get(cat, cat.title())),
                             len(group)))
        for p in group:
            lines.append('- <a href="%s"><img src="%s" height="24" alt="%s"></a> \u2014 %s'
                         % (p["landing"], pills[p["name"]], p["name"], p["desc"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_achievements(achievements, progress=None):
    """The row of achievement cards. Empty string when nothing could be read, so
    the heading disappears with the cards rather than hanging over nothing."""
    if not achievements:
        return ""
    parts = ["## Achievements", "",
             '<p align="center">']
    for a in achievements:
        label = "%s%s%s" % (a["name"], ", " + a["tier"] if a["tier"] else "",
                            ", earned %d times" % a["count"] if a["count"] > 1 else "")
        parts.append('  <a href="https://github.com/%s?tab=achievements">'
                     '<img src="%s" height="78" alt="%s"></a>&nbsp;'
                     % (OWNER, a["asset"], esc(label)))
    parts.append("</p>")
    if progress:
        parts += ["",
                  '<p align="center">',
                  "  <picture>",
                  '    <source media="(prefers-color-scheme: dark)" srcset="assets/progress-dark.svg">',
                  '    <source media="(prefers-color-scheme: light)" srcset="assets/progress-light.svg">',
                  '    <img src="assets/progress-light.svg" width="100%" '
                  'alt="Distance to the next tier of each tiered achievement">',
                  "  </picture>",
                  "</p>",
                  "",
                  '<p align="center"><sub>Counted from the API on every build. A number marked + is a floor, '
                  "not a count \u2014 GitHub publishes no counter for those two.</sub></p>"]
    return "\n".join(parts) + "\n"


def replace_region(text, start, end, content):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        sys.exit("ERROR: markers %s / %s not found in README.md" % (start, end))
    return pattern.sub(lambda _m: start + "\n\n" + content.strip() + "\n\n" + end, text, count=1)


def main():
    with open(DATA_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    labels = {c["key"]: c["label"] for c in data.get("categories", [])}
    colours = {c["key"]: c.get("colour", DEFAULT_COLOURS.get(c["key"], "#52525B"))
               for c in data.get("categories", [])}
    if not colours:
        colours = dict(DEFAULT_COLOURS)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    api_repos = fetch_repos(token)
    public_repos = fetch_public_repo_count(token)

    changed, added, refreshed, uncategorised, stale = sync_catalogue(data, api_repos)
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
    pills = write_pills(projects, colours, labels)
    achievements = write_achievements(fetch_achievements())
    rows = progress_rows(achievements, api_repos, fetch_merged_pr_count(token))
    progress = write_progress(rows)
    write_stats(projects, api_repos, public_repos)

    with open(README, encoding="utf-8") as fh:
        readme = fh.read()
    readme = replace_region(readme, PROJ_START, PROJ_END,
                            render_projects(projects, labels, pills))
    if ACH_START in readme and ACH_END in readme:
        readme = replace_region(readme, ACH_START, ACH_END,
                                render_achievements(achievements, rows if progress else None))
    if not readme.endswith("\n"):
        readme += "\n"
    with open(README, "w", encoding="utf-8") as fh:
        fh.write(readme)

    print("OK public_repos=%d projects=%d (featured=%d, achievements=%d)"
          % (public_repos, len(projects), sum(1 for p in projects if p["featured"]),
             len(achievements)))


if __name__ == "__main__":
    main()
