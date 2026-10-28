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
