drsamonline — status record
28 October 2026. Written from the live repositories, not from intent. Every number below was re-read from GitHub after the change landed.

1. Done, and verified
1.1 Store purchase links (Matneo + app-builder)
Was: every product's Buy button pointed at https://drsamonline.github.io/ — the hub, which is a project index, not a shop. buyLinks was empty, so the button had nowhere else to go. sourceRepo pointed at a private repo, so "View source" was a 404 for every visitor.

Now: each product's link is a pre-filled enquiry email, landingPage is that product's own page, and sourceRepo is gone. products.js says "Enquire by email" and "enquire by email · licence issued manually". Both pages that load the script now request ?v=6.

Why it will not revert: the source of truth is FOR_SALE inside app-builder/drsoam.py, and that was patched too. Tomorrow's 04:22 regeneration rebuilds products.json with the enquiry links.

Evidence: 4 commits — 2 in Matneo, 2 in app-builder; products.json re-read live and shows the mailto and the product-page URL; products.js and drsoam.py both parse.

1.2 Licence badges (the whole fleet)
The badge now says what the LICENSE file grants. The LICENSE files were not touched — the file is the legal text, the badge is the label on it.




Measure	Before	After
Badge names a licence the LICENSE does not grant	17	0
Badge URL truncated by a raw space	18	0
Dynamic badge rendering "NOASSERTION"	1	0
LICENSE present but no badge in README	20	0
Free-text claims (informational)	11	15
Repos fully correct	11	63
How: three passes. 24 truncated URLs and 28 alt texts repaired in the first; 10 badges corrected and 20 added in the second, driven by reading each LICENSE.

Bespoke licences are worded, not normalised. A standard licence name is never put on a repo that does not have one, and a custom claim is never removed:




Repo	Badge
gentle-pediatrics-companion	Free to use, non-commercial
mnemosyne-companion	Free for personal study
skin-case-tracker	Free for personal and clinical use
homoeopathic-materia-medica-repertory-json	Free to use, attribution required
boericke-repertory	Free to use, attribution required (already correct)
1.3 Tooling now in the profile repo
Three workflows, each with a script, all driven by one AUDIT_TOKEN secret:

licence-fix.yml — the original URL/alt-text repair.
apply-store-fixes.yml — the store data and the generator behind it.
apply-licence-badges.yml — reads each LICENSE and aligns the badge to it.
All three support a dry run first, are idempotent, and replace strings rather than overwriting files, so a file that has moved on reports "pattern not found" instead of being clobbered.

2. Corrections to earlier findings in this project
Recorded because a wrong audit is worse than no audit.

HMS was not a contradiction. Its LICENSE is a proprietary EULA that states "the MIT License previously applied… is expressly withdrawn and superseded." The badge saying Proprietary was right. My classifier read the whole file and matched the withdrawal notice.
open-materia-medica was not a contradiction. Its "Apache License 2.0" appears only in a third-party section about the Android SDK. The repo is all-rights-reserved; its badge was right.
The count was 56 repos with a licence defect, not 52. The first pass did not check alt text.
The first fix script rewrote every badge to PolyForm, including MIT and Apache repos, and reported success. Caught in dry run; rebuilt with an explicit "is this repo actually PolyForm" guard.
The second version missed four repos whose badge path is badge/License- with a capital L, because the pattern was case-sensitive.
The third version mislabelled two custom "free-to-use" licences as "All rights reserved" — the opposite of what those files permit. It now refuses to word a bespoke licence at all.
The checker and the aligner disagreed, so the checker was reading files differently from the tool that fixes them. They now share one classifier, windowed to the licence's own opening.
3. Remaining
3.1 Licence — soft wording, 7 repos
The badge describes permitted use in words while the LICENSE says "all rights reserved". Not urgent, but the same shape as the MIT-vs-PolyForm problem:

MATERIA-MEDICA-BUILDER (badge "free with attribution", file MIT) · smartbill-app ("custom dual", MIT) · unstoppable-mind-companion ("free to use", MIT) · ambient-sound-studio ("personal use only") · the-symphony-companion ("Personal use only") · whispering-body-first-aid ("free to use") · boericke-repertory ("free use · attribution required", file MIT).

Decision needed: is the badge right and the file wrong, or the reverse?

3.2 Licence — two files that forbid what you described
You said all three companions are free to use and share. gentle-pediatrics-companion is — its file permits copying and redistribution. But mnemosyne-companion grants only "a single personal copy", and skin-case-tracker states you may NOT "redistribute, sublicense, publish, mirror". If sharing is the intent, those two LICENSE files need rewriting before the badge can say so.

3.3 Matneo blog — one more run
posts.json is stale (generated 27 Oct) and still points at the hub root. The generator now prefers landingPage, so the next blog.yml run (04:12 daily) fixes it. To fix it now, re-run apply-store-fixes with apply ticked.

3.4 Requirements still open



#	Requirement	State
1	Dashboard design, missing functions, errors	Not started. refresh.yml failed 2 of its last 6 runs; logs not yet read. SPEC-GAP.json and plan.json already list what is missing.
2	Hub: kits subpage + own blog subpage	Not started. No kits/ or blog/ directory exists; the kits link is a GitHub search URL; the blog link points at Matneo.
3	Matneo blog on product add	Working, one stale-data run outstanding (§3.3).
4	Control panel too complicated	Not started. Zero buttons in the static HTML; five JSON files behind it.
5	Repo hygiene	Partly done. Descriptions 78/78, LICENSE 78/78, README 78/78, licence badges 78/78. Still: topics 73/78, homepage 70/78, Pages off for 6, 25 of 54 landing pages link no download, today-card serves its app from the landing slot, 9 landing pages share one palette.
6a	App icons in releases	Not started. today-card.apk has no res/, no mipmap, no ic_launcher; app-builder/build.yml has zero icon references. One shared fix.
6b	Scheduled runs minimised	Not started. 11 cron entries; Matneo runs three dailies; update-profile and refresh-hub both fire at 03:17.
7	Enhancement list	Delivered as a document (§7 of the plan), not implemented.
8	One repo holding the audit record	Not created. This file is the first record; it needs a home.
9	—	Unknown. Item 9 was cut off in the original paste.
4. Next three actions
Re-run apply-store-fixes with apply ticked — clears the blog URLs.
Answer §3.1 and §3.2 — closes the licence work completely.
Phase 2: icons in app-builder. One fix, forty repos, and the most visible defect left.

---

31 October 2026 — the profile and the hub now read one catalogue
Written from the live repositories after the change landed.

1. What was wrong
Three numbers described the same fleet and none of them agreed: the profile README said 92 projects, the hub's repos.json said 71, and the hub's grid actually rendered 53 cards. Behind the numbers, 52 of 92 repos had never been curated, so they fell into "Other / New" carrying their raw GitHub text — 35 of the hub's 71 records sat there, including kent-repertory-explorer (a repertory tool filed under "Other"), Scrap-and-Gun (a game filed under "Other") and all 18 *-kit libraries.

Two independent causes:

* The hub had not refreshed since 27 October. Its refresh workflow committed, then failed to push, because `git rebase origin/main` refuses while the regenerated thumbnails sit unstaged in the tree. That is a permanent condition, not a race: the retry loop ran six times, aborted six times, and the run ended red with the new data still local.
* Curation lived in two hand-maintained places — profile-data.json (40 entries) and the CURATED map inside the hub's index.html (41 entries) — and neither was required to learn about a new repo. A repo added to the fleet appeared as "Other / New" on both surfaces, by design.

Measure	Before	After
Places the descriptions are written	2	1
Repos in "Other / New"	35 hub + 52 profile	0
Categories	7	11
Profile projects / hub apps / hub kits	92 / 71 / hidden	92 / 68 / 19
Hub hero count vs cards rendered	71 vs 53	68 vs 68

2. What changed
One file, catalogue.json in this repository, holds every description, category and feature flag for all 92 projects. The profile generator reads it directly; the hub fetches it at build time and merges it over its own map, so the in-page CURATED, CAT_LABEL, CAT_ORDER and FEATURED literals are now regenerated rather than hand-edited.

Taxonomy: Learning & Reference, Weft-8 & Retrocomputing, Libraries & Kits, CHCE Compression and Meta & Infrastructure are new; "Desktop & System Tools" became "Desktop, System & Developer Tools" so NOVA, Aetheris, LEXORA and CLDR are not filed under a label that does not describe them.

Counts: the hub states what it renders. repos.json still carries every record, because the kits page reads it; the hero, the JSON-LD, the sitemap and the grid count apps only, so 68 means 68 cards.

3. The push bug (F-97, second instance)
tools/commit-and-verify.sh rebased without --autostash, so any file the build regenerates but the script was not asked to commit made the rebase impossible. It now rebases with --autostash, and the refresh workflow stages assets/shots before calling it. The thumbnail step also carries continue-on-error: a screenshot is decoration, the data is the product, and a Chromium hiccup used to discard a perfectly good repos.json.

4. Descriptions that were simply wrong
* All4ONE said 551 tools on both surfaces. The repository says 403; 551 was the 3.x count, retired with the plugin packs. Corrected everywhere.
* TTB said 590 utilities and named one browser. Its README says 591, and it ships for Chrome, Edge, Firefox and Safari.
* ai-bridge read "VScode Extension to use webchat ais in vscoding environment". Written properly.
* BLINKTRANSFER and ULTIMATE-WINDOWS-OPTIMIZER were set in capitals. CLDR, HCS and MATERIA-MEDICA-BUILDER were a phrase or a bare name.

5. Repo metadata (§3.4 item 5)
topics 76/94 -> 94/94. homepage 74/94 -> 83/94, and every Pages-enabled repo now links its site (81 of 81); the other 11 have no site to link. drsamonline.github.io pointed its Website at https://drsamonline.github.io/drsamonline.github.io/ — a sub-path of itself, which 404s — and now points at the root.

6. Found, and not fixed
app-lantern reports size 0 KB to the API while holding a README, server.js, a test file and examples. The hub's "empty repo" rule trusted that field and silently dropped it from the showcase; the rule now also requires that nothing has been pushed. Anything else in the estate that trusts `size` will make the same mistake.

Evidence: catalogue.json in this repo; tools/build_hub.py, tools/commit-and-verify.sh and the refresh workflow in drsamonline.github.io; both workflows green, then re-read live.

7. Since then: it maintains itself
Aligning the descriptions exposed the real question — who owns them? Answer, now written into the script: GitHub does. Every repository's description was pushed to GitHub from the catalogue (83 changed, 0 disagreements left), and from here the arrow runs the other way. The daily run reconciles the catalogue against the live repositories before it renders:

* a repository that is not in the catalogue is added, with its GitHub description and a category guessed from its name, description and topics; anything the rules cannot place is reported in the run log rather than filed somewhere plausible but wrong;
* a description edited on GitHub replaces the catalogue's on the next run, so the profile and the hub follow an edit made in the one place a person would naturally make it;
* an entry carrying "pin": true keeps its own wording, for a description that must not move;
* category, featured, demo, release, kicker and tag have no equivalent on GitHub, so they stay here. That is the part worth curating, and the only part.

Two cadences were wrong for this. update-profile ran weekly and refresh-hub ran on the 1st and 16th, so a repository added on a Tuesday reached the profile the following Monday and the hub up to a fortnight later. Both are daily now, and the hub's thumbnails are freshness-checked per repo, so a daily run re-captures only what changed. A new repository now reaches both surfaces within a day, described and categorised, with nobody editing a file.

Proved, not assumed: a mock fleet with two invented repositories and an edited description was run through the script — both were added (one to "mind" from its wording, one to "other" with a notice), the edited description propagated, and a repository whose text was already correct was left alone. The real fleet then ran as a no-op: 0 added, 0 refreshed, README byte-identical.
