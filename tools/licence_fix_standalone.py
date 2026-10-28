#!/usr/bin/env python3
"""Fix the truncated licence badge across the drsamonline fleet.

Self-contained: needs only GH_TOKEN in the environment and Python 3.8+.
No pip installs, no checkout, no state directory.

Fixes two things, both in the same README line:

  1. URL.  A raw space inside the shields.io URL. GitHub truncates an image
     URL at the space, so the badge renders "license | PolyForm" in grey and
     the colour is lost.
  2. ALT TEXT.  Some READMEs carry `![License: MIT]` in front of a PolyForm
     badge. The alt text shows when the image fails and is what a screen
     reader announces, so it must agree with the licence.

It refuses three things on purpose:
  * a URL that already resolves is left exactly as written (no churn)
  * a repo whose LICENSE is not PolyForm NC is skipped (this is not a relicense)
  * a repo whose badge names a different licence is skipped (that is a legal
    question for the owner, and half-fixing it would leave badge and alt text
    disagreeing with each other)

Usage:
    GH_TOKEN=... python3 licence_fix_standalone.py            # dry run
    GH_TOKEN=... python3 licence_fix_standalone.py --apply    # commit
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
ALT = "License: PolyForm Noncommercial 1.0.0"
MESSAGE = "fix(licence): encode the licence badge URL so it renders in full"

MARKDOWN = re.compile(r"!\[([^\]]*)\]\((https://img\.shields\.io/badge/licen[^)]*)\)")
HTML = re.compile(r'<img([^>]*?)src="(https://img\.shields\.io/badge/licen[^"]*)"([^>]*?)>')

FAMILIES = [
    ("mit", ("mit",)),
    ("polyform", ("polyform",)),
    ("apache", ("apache",)),
    ("cc", ("cc by", "cc-by", "creative commons")),
    ("gpl", ("gpl", "gnu general public")),
    ("proprietary", ("all rights reserved", "proprietary")),
    ("cc0", ("cc0", "public domain")),
]


def family(text):
    t = (text or "").lower()
    for fam, needles in FAMILIES:
        if any(n in t for n in needles):
            return fam
    return None


def api(path, method="GET", payload=None):
    url = API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "drsamonline-licence-fix")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        return e.code, {"error": body}
    except Exception as e:                                    # noqa: BLE001
        return 0, {"error": str(e)[:200]}


def fetch_file(repo, path):
    code, d = api("/repos/%s/%s/contents/%s" % (OWNER, repo, path))
    if code != 200 or not isinstance(d, dict) or "content" not in d:
        return None, None
    return base64.b64decode(d["content"]).decode("utf-8", "replace"), d["sha"]


def fix_url(url):
    base = "https://img.shields.io/badge/"
    if not url.startswith(base) or " " not in url:
        return url
    rest = url[len(base):]
    query = ""
    if "?" in rest:
        rest, q = rest.split("?", 1)
        query = "?" + q
    suffix = ".svg" if rest.endswith(".svg") else ""
    if suffix:
        rest = rest[:-4]
    head, _, colour = rest.rpartition("-")
    if not head:
        head, colour = rest, "blue"
    if not re.fullmatch(r"[0-9a-fA-F]{3,8}|[a-z]+", colour or ""):
        colour = "blue"
    return "%slicense-PolyForm%%20Noncommercial%%201.0.0-%s%s%s" % (base, colour, suffix, query)


def rewrite(text):
    changes = []

    def new_alt_for(old):
        fam = family(old)
        if fam and fam != "polyform":
            return ALT
        if old.strip().lower() in ("license", "licence", ""):
            return ALT
        return old

    def md(m):
        alt, url = m.group(1), m.group(2)
        new_url, new_alt = fix_url(url), new_alt_for(alt)
        if new_url != url:
            changes.append(("url", url, new_url))
        if new_alt != alt:
            changes.append(("alt", alt, new_alt))
        return "![%s](%s)" % (new_alt, new_url)

    def html(m):
        before, url, after = m.group(1), m.group(2), m.group(3)
        new_url = fix_url(url)
        if new_url != url:
            changes.append(("url", url, new_url))

        def sub_alt(segment):
            def repl(mm):
                old = mm.group(1)
                new = new_alt_for(old)
                if new != old:
                    changes.append(("alt", old, new))
                return 'alt="%s"' % new
            return re.sub(r'alt="([^"]*)"', repl, segment)

        return '<img%ssrc="%s"%s>' % (sub_alt(before), new_url, sub_alt(after))

    text = MARKDOWN.sub(md, text)
    text = HTML.sub(html, text)
    return text, changes


def claims_in(text):
    out = []
    for rx, grp in ((MARKDOWN, 2), (HTML, 2)):
        for m in rx.finditer(text):
            body = m.group(grp).split("/badge/", 1)[-1].split("?")[0]
            parts = body.replace("%20", " ").replace("_", " ").split("-")
            out.append("-".join(parts[1:-1]) if len(parts) > 2 else "")
    return out


def main():
    apply = "--apply" in sys.argv or os.environ.get("APPLY") == "true"
    if not TOKEN:
        sys.exit("GH_TOKEN is not set")

    code, repos = api("/users/%s/repos?per_page=100&type=public" % OWNER)
    if code != 200 or not isinstance(repos, list):
        sys.exit("could not list repos (%s): %s" % (code, repos))

    fixed, skipped, failed = [], [], []
    url_fixes = alt_fixes = 0

    for repo in sorted(r["name"] for r in repos):
        readme, sha = fetch_file(repo, "README.md")
        if readme is None:
            continue
        licence, _ = fetch_file(repo, "LICENSE")
        if not licence or "polyform noncommercial" not in licence.lower():
            continue
        if any(family(c) not in (None, "polyform") for c in claims_in(readme)):
            skipped.append(repo)
            continue

        new_readme, changes = rewrite(readme)
        if not changes:
            continue

        if not apply:
            print("=== %s" % repo)
            for kind, old, new in changes:
                print("  %s  - %s" % (kind, old))
                print("       + %s" % new)
            fixed.append(repo)
            url_fixes += sum(1 for k, _, _ in changes if k == "url")
            alt_fixes += sum(1 for k, _, _ in changes if k == "alt")
            continue

        st, resp = api("/repos/%s/%s/contents/README.md" % (OWNER, repo), "PUT", {
            "message": MESSAGE,
            "content": base64.b64encode(new_readme.encode("utf-8")).decode("ascii"),
            "sha": sha,
        })
        if st in (200, 201):
            fixed.append(repo)
            url_fixes += sum(1 for k, _, _ in changes if k == "url")
            alt_fixes += sum(1 for k, _, _ in changes if k == "alt")
            print("  fixed %s" % repo)
        else:
            failed.append((repo, str(resp)[:160]))

    print("\n%s %d repo(s): %d URL fix(es), %d alt-text fix(es)"
          % ("would fix" if not apply else "fixed", len(fixed), url_fixes, alt_fixes))
    if skipped:
        print("left for a decision (badge names a different licence): %d" % len(skipped))
    for r, why in failed:
        print("  FAILED %s (%s)" % (r, why))
    if failed and apply:
        sys.exit(1)


if __name__ == "__main__":
    main()
