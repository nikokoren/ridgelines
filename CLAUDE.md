# CLAUDE.md

Rules for any agent working in this repo.

## Start here

1. [PROJECT.md](PROJECT.md): current status, decisions, dated findings, next steps.
2. [docs/brief.md](docs/brief.md): the full brief and requirements. Everything the recipe must do is specified there.
3. This file: how to work.

## Working method

1. Never verify against invented input. Use live API responses or the captured fixture corpus.
2. Sweep the full state space (every entry, view, bit depth and size class) instead of spot checking.
3. Re-fetch docs from unversioned URLs before relying on them, and stamp what was verified and when. When the web and this repo disagree, the web wins.
4. Prove absence claims: name what was checked and the hit counts.
5. Prove fixes with before and after evidence, never by assertion.
6. Run real data through new copy before shipping it.
7. State corrections in one line and move on.
8. Write findings into PROJECT.md, dated, each with a re-check instruction.
9. Assume concurrent agents. Re-read a file right before editing it.

## TRMNL

- **Layouts use TRMNL framework classes only, no exceptions.** The latest framework version, plus anything from earlier versions that the latest still supports. No custom CSS, no `<style>` blocks, no inline style attributes, no self-made style classes, no hard-coded colours or pixel sizes, no workarounds. The SVG line art inside the drawing container is the only thing drawn outside framework classes, and it takes every colour and size from TRMNLPaint. If something cannot be built from framework classes, stop and flag it instead of working around it.
- Start from https://trmnl.com/framework and check what the latest version supports before writing markup (the 3.3 URL redirected to 3.4 on 2026-10-01).
- Layouts scale across sizes and orientations through framework classes and responsive prefixes. No hard-coded pixel sizes.
- Colours come from TRMNLPaint, sizes go through TRMNLPaint.px().
- If the drawing container measures zero, draw nothing and show the caption alone (the Aurora Watch layout once collapsed and drew at a fallback size over the text).
- Deliver Liquid templates as .txt files.
- TRMNL sends the UTC offset in seconds, not minutes.
- Polled payloads have a 100 KB hard cap. Budget 80 KB and measure every entry.
- The Worker never writes to KV.

## Data

- Terrain from Copernicus DEM GLO-90, list and names from Wikidata. No non-commercial (NC) licensed data, ever: the recipe may earn Creator Fund payouts.
- Put the Copernicus GLO-90 notice and liability sentence on the About page, with all other licensing (decided 2026-10-02, exact wording in PROJECT.md Findings).
- Never commit elevation tiles, caches or generated entry files.
- tools/mockup reads JAXA demo tiles for look tuning only. Nothing ships from it.

## Copy

- English and German from the first release, every string keyed by language code.
- Write German copy from scratch, as a native speaker would, never as a translation of the English. Translated copy sounds robotic (Niko, 2026-10-10).
- No en or em dashes in user-facing text, docs or commit messages. Use commas, periods, or rephrase.
- The listing, icon and store image must not reference or imitate the album cover associated with ridgeline plots.

## Repo hygiene

- The repo is meant to go public at launch. Never commit Worker URLs, account or namespace ids, tokens or email addresses. Use placeholders and document what a user must supply. Secrets go through `wrangler secret`.
