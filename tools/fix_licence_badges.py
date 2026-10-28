#!/usr/bin/env python3
"""Make every licence badge say what the LICENSE file actually grants.

The LICENSE file is authoritative and is never touched. This script reads it,
works out the licence, and then:

  * rewrites an existing badge that names a different licence
  * adds a badge where there is none
  * leaves a correct badge exactly as it is

It also replaces a dynamic `github/license` badge, because GitHub answers
"NOASSERTION" for anything that is not on its recognised list - which includes
every PolyForm and every custom licence here.

Custom and proprietary licences are kept as they are, worded from their own
LICENSE text. Nothing is normalised to a standard licence it does not have.

    GH_TOKEN=... python3 fix_licence_badges.py            # dry run
    GH_TOKEN=... python3 fix_licence_badges.py --apply    # commit
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get("OWNER", "drsamonline")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
API = "https://api.github.com"
MESSAGE = "docs(licence): make the badge match the LICENSE file"

MARKDOWN = re.compile(r"!\[([^\]]*)\]\((https://img\.shields\.io/badge/[^)\s]*?licen[^)]*)\)", re.I)
HTML = re.compile(r'<img([^>]*?)src="(https://img\.shields\.io/badge/[^"\s]*?licen[^"]*)"([^>]*?)>', re.I)
DYNAMIC = re.compile(r"https://img\.shields\.io/github/license/[^)\"'<>\s]+", re.I)
BADGE_ANY = re.compile(r"(?:!\[[^\]]*\]\(https://img\.shields\.io/badge/[^)\s]*?licen[^)]*\)"
                       r'|<img[^>]*src="https://img\.shields\.io/badge/[^"\s]*?licen[^"]*"[^>]*>)', re.I)

# licence text in the file -> (badge message, colour)
# The licence identity lives in the opening of the file. Reading further picks up
# third-party credits ("built on the Android SDK (Apache License 2.0)") and
# withdrawal notices ("the MIT License previously applied is withdrawn"), both of
# which describe someone else's licence, not this repository's.
WINDOW = 600

STANDARD = [
    ("polyform noncommercial", "PolyForm Noncommercial 1.0.0", "2e7d32"),
    ("polyform small business", "PolyForm Small Business 1.0.0", "2e7d32"),
    ("attribution-noncommercial-sharealike", "CC BY-NC-SA 4.0", "orange"),
    ("apache license", "Apache 2.0", "blue"),
    ("gnu general public", "GPL-3.0", "blue"),
    ("mit license", "MIT", "green"),
    ("permission is hereby granted, free of charge", "MIT", "green"),
    ("creative commons zero", "CC0 1.0", "lightgrey"),
]

# Words that mean "this is bespoke; do not put a standard licence name on it".
CUSTOM = ("proprietary", "all rights reserved", "free-to-use", "free to use",
          "not an open-source", "source-available", "eula", "permission from the author")


# Bespoke licences, worded by the owner. A standard licence name would be a lie
# here, so each one is named from what its own file permits. Keep the wording
# short: the badge is a label, the LICENSE is the contract.
OVERRIDES = {
    # permits copy, share and redistribute for non-commercial purposes
    "gentle-pediatrics-companion": ("Free to use, non-commercial", "yellowgreen"),
    # single personal copy for personal/educational study - no redistribution
    "mnemosyne-companion": ("Free for personal study", "lightgrey"),
    # free of charge for personal and clinical use - no redistribution
    "skin-case-tracker": ("Free for personal and clinical use", "lightgrey"),
    # the compiled dataset is free to use and share; the source books are public
    # domain, so credit is owed to their authors and to the compiler
    "homoeopathic-materia-medica-repertory-json": ("Free to use, attribution required", "yellowgreen"),
    # already worded this way in its own README - listed so the wording is pinned
    "boericke-repertory": ("Free to use, attribution required", "yellowgreen"),
}


def licence_of(text):
    """Return (message, colour, note).

    A standard licence gets a badge message. A bespoke one returns
    (None, None, 'custom') so it is reported and left for the owner to word -
    the script must never invent a licence name, in either direction.
    """
    head = text[:WINDOW].lower()
    full = text.lower()
    if "two different licences" in full or ("cc0 1.0" in full and "gnu general public" in full):
        return None, None, "split"
    for needle, msg, colour in STANDARD:
        if needle in head:
            return msg, colour, ""
    if any(w in head for w in CUSTOM):
        return None, None, "custom"
    return None, None, "unclear"


def badge_url(msg, colour, query=""):
    slug = msg.replace(" ", "%20").replace("-", "--")
    return "https://img.shields.io/badge/license-%s-%s%s" % (slug, colour, query)


def query_of(url):
    return "?" + url.split("?", 1)[1] if "?" in url else ""


def alt_of(msg):
    return "License: " + msg


FAMILY = [
    ("mit", ("mit",)),
    ("polyform", ("polyform",)),
    ("apache", ("apache",)),
    ("cc", ("cc by", "cc-by", "creative commons")),
    ("gpl", ("gpl", "gnu general public")),
    ("proprietary", ("all rights reserved", "proprietary")),
    ("cc0", ("cc0",)),
]


def family(text):
    t = (text or "").lower()
    for fam, needles in FAMILY:
        if any(n in t for n in needles):
            return fam
    return None


def claimed_of(url):
    body = url.split("/badge/", 1)[-1].split("?")[0]
    parts = body.replace("%20", " ").replace("_", " ").split("-")
    return "-".join(parts[1:-1]) if len(parts) > 2 else (parts[-1] if parts else "")


def rewrite(text, msg, colour):
    """Correct only the badges that name the wrong licence, or the wrong alt text.

    A badge that already names this licence is left byte-for-byte alone: its
    colour is the author's choice, not a defect.
    """
    changes = []
    act_fam = family(msg)

    def md(m):
        old_alt, url = m.group(1), m.group(2)
        new_url, new_alt = url, old_alt
        if family(claimed_of(url)) not in (None, act_fam):
            new_url = badge_url(msg, colour, query_of(url))
        if family(old_alt) not in (None, act_fam):
            new_alt = alt_of(msg)
        if new_url != url:
            changes.append(("url", url, new_url))
        if new_alt != old_alt:
            changes.append(("alt", old_alt, new_alt))
        return "![%s](%s)" % (new_alt, new_url)

    def html(m):
        before, url, after = m.group(1), m.group(2), m.group(3)
        new_url = url
        if family(claimed_of(url)) not in (None, act_fam):
            new_url = badge_url(msg, colour, query_of(url))
        if new_url != url:
            changes.append(("url", url, new_url))

        def sub_alt(seg):
            def repl(mm):
                old = mm.group(1)
                if family(old) not in (None, act_fam):
                    new = alt_of(msg)
                    if new != old:
                        changes.append(("alt", old, new))
                    return 'alt="%s"' % new
                return mm.group(0)
            return re.sub(r'alt="([^"]*)"', repl, seg)

        return '<img%ssrc="%s"%s>' % (sub_alt(before), new_url, sub_alt(after))

    text = MARKDOWN.sub(md, text)
    text = HTML.sub(html, text)

    def dyn(m):
        url = m.group(0)
        new = badge_url(msg, colour, query_of(url))
        changes.append(("dynamic", url, new))
        return new

    text = DYNAMIC.sub(dyn, text)
    return text, changes


def insert_badge(text, msg, colour):
    """Add a badge line after the first H1, or at the top if there is none."""
    line = "[![%s](%s)](LICENSE)" % (alt_of(msg), badge_url(msg, colour))
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if re.match(r"^#\s+\S", l):
            lines[i + 1:i + 1] = ["", line]
            return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), [("add", "", line)]
    return line + "\n\n" + text, [("add", "", line)]


def api(path, method="GET", payload=None):
    req = urllib.request.Request(API + path,
                                 data=json.dumps(payload).encode() if payload else None,
                                 method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "drsamonline-licence-badge")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}
    except Exception as e:                                    # noqa: BLE001
        return 0, {"error": str(e)[:200]}


def get_file(repo, path):
    code, d = api("/repos/%s/%s/contents/%s" % (OWNER, repo, path))
    if code != 200 or not isinstance(d, dict) or "content" not in d:
        return None, None
    return base64.b64decode(d["content"]).decode("utf-8", "replace"), d["sha"]


def main():
    apply = "--apply" in sys.argv or os.environ.get("APPLY") == "true"
    only = os.environ.get("ONLY", "")
    if not TOKEN:
        sys.exit("GH_TOKEN is not set")

    code, repos = api("/users/%s/repos?per_page=100&type=public" % OWNER)
    if code != 200 or not isinstance(repos, list):
        sys.exit("could not list repos (%s): %s" % (code, repos))

    names = sorted(r["name"] for r in repos)
    if only:
        wanted = {x.strip() for x in only.split(",")}
        names = [n for n in names if n in wanted]

    changed = added = rewired = skipped = 0
    custom = []
    for repo in names:
        readme, sha = get_file(repo, "README.md")
        if readme is None:
            continue
        licence, _ = get_file(repo, "LICENSE")
        if licence is None:
            licence, _ = get_file(repo, "LICENSE.md")
        if not licence:
            print("skip     %-40s no LICENSE" % repo)
            continue

        if repo in OVERRIDES:
            msg, colour, note = OVERRIDES[repo][0], OVERRIDES[repo][1], ""
        else:
            msg, colour, note = licence_of(licence)
        if msg is None:
            reason = {"custom": "bespoke licence - word the badge yourself",
                      "split": "two licences in one repo - needs two badges",
                      "unclear": "licence not recognised - check by hand"}[note]
            print("skip     %-40s %s" % (repo, reason))
            custom.append(repo) if note == "custom" else None
            skipped += 1
            continue

        if BADGE_ANY.search(readme) or DYNAMIC.search(readme):
            new, changes = rewrite(readme, msg, colour)
            kind = "rewire"
        else:
            new, changes = insert_badge(readme, msg, colour)
            kind = "add"

        if new == readme:
            continue

        print("%-8s %-40s -> %s" % (kind, repo, msg))
        for k, old, nw in changes[:3]:
            print("           %s  %s" % (k, nw[:100]))
        if kind == "add":
            added += 1
        else:
            rewired += 1
        changed += 1

        if apply:
            st, resp = api("/repos/%s/%s/contents/README.md" % (OWNER, repo), "PUT", {
                "message": MESSAGE,
                "content": base64.b64encode(new.encode("utf-8")).decode("ascii"),
                "sha": sha,
            })
            print("         -> %s" % ("written" if st in (200, 201) else "FAILED %s" % resp))

    print("\n%s %d README(s): %d badge(s) added, %d badge(s) corrected, %d skipped"
          % ("would change" if not apply else "changed", changed, added, rewired, skipped))
    if custom:
        print("\nbespoke licences left alone (yours to word): %d" % len(custom))
        for r in custom:
            print("  %s" % r)


if __name__ == "__main__":
    main()
