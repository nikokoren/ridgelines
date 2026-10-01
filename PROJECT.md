# Ridgelines: project state

TRMNL recipe: one real mountain range per day, drawn as a top-down map of gently rippled lines.

**Status (2026-10-01):** parked. Design phase only, no production code. Work resumes after the What to Wear overhaul ships.

Full requirements live in [docs/brief.md](docs/brief.md), a snapshot of the living brief exported on 2026-10-01. Where this file and the brief disagree, this file is newer.

## Planned architecture

1. **Build pipeline** (GitHub Actions, run on demand): Wikidata list of ranges, Copernicus GLO-90 crop windows over HTTP range requests, resample to a metric grid, spike cleanup, 8-bit base64 heightmap plus a per-entry height floor, one JSON file per entry plus a calendar index, uploaded to R2.
2. **Cloudflare Worker:** maps the user's local date (TRMNL sends the UTC offset in seconds) and Area setting to an entry and returns its file. No KV, no writes, long edge caching.
3. **TRMNL template:** plugin JS decodes the heightmap and draws SVG lines with framework paint colours and px() scaling. Caption sits in the native title bar.

## Decisions

| Date | Decision | Source |
| --- | --- | --- |
| 2026-10-01 | Layouts use TRMNL framework classes only: latest version plus anything earlier versions provide that it still supports. No own styles, no workarounds | Niko. The brief allows one exception: the SVG line art, coloured and sized only through the framework's Paint API |
| 2026-10-01 | Look: top-down map, evenly spaced west to east lines, 64 lines on the OG full view, tallest ripple about 4 line gaps, height floor at the crop's 40th percentile | Picked by Niko from [docs/mockups](docs/mockups/) over a tilted 3D stack and a front-on panorama. Fine tuning deferred until more real ranges are rendered |
| 2026-10-01 | Parked until the What to Wear overhaul is done | Niko |

Everything else in docs/brief.md (data sources, settings, delivery) is the proposed baseline and has not been reviewed line by line yet.

## Findings

Each finding is dated. Re-check before relying on it.

- **2026-10-01, framework version.** The 3.3 docs URL redirects to 3.4. *Re-check:* open https://trmnl.com/framework and stamp the current version here.
- **2026-10-01, payload cap.** Private plugins reject polled payloads over 100 KB (TRMNL help article "Parsing plugins with the Sandbox Runtime", dated Aug 28, 2026). Unknown whether the cap applies before or after compression. *Re-check:* reopen the article before sizing the payload.
- **2026-10-01, elevation spikes.** In the JAXA demo tiles, raw pixels in the Karwendel crop reach 3,011 m (2,935 m at the point sampled for the brief). The documented high point is 2,749 m (Birkkarspitze). tools/mockup clips to the documented maximum and patches around the spike. *Re-check:* run the fixture corpus through Copernicus GLO-90 and count pixels above each range's documented high point.
- **2026-10-01, busy terrain.** Without a height floor the drawing is too busy on 1-bit screens. A floor at the 40th percentile calmed the chosen mockup. *Re-check:* across the full fixture corpus.
- **2026-10-01, portrait caption.** At 480 px wide, range, peak, height and country do not fit beside the plugin title. *Open:* drop the country in portrait, or drop the title.
- **2026-10-01, uniqueness.** A web search found no TRMNL recipe for terrain, contours or ridgelines. The store's own search was not run. *Re-check:* search the store for ridgeline, terrain, elevation, topo, contour and mountain, and record the hit counts here.
- **2026-10-01, mockup reproduction.** `tools/mockup/mockup.py` with default settings reproduces the chosen mockup exactly (0 of 384,000 pixels differ). *Re-check:* after any change to the tool, diff against docs/mockups/chosen_topdown_64_lines.png.

## Next up, when unparked

1. Store search for uniqueness, recorded under Findings.
2. Re-fetch the framework docs and stamp the version.
3. Check the GLO-90 licence against the ESA annex linked from the AWS registry.
4. Live Wikidata query for ranges and their high points; confirm the property IDs.
5. Fixture corpus of seven real ranges: tall alpine, long and narrow, high latitude, equatorial, across the antimeridian, low desert, coastal with ocean in frame.
6. Tune the look across all seven. Extend tools/mockup to read Copernicus data, since the demo tiles only cover 47 to 48°N and 11 to 12°E.
7. Build pipeline, then Worker, then template.

## Open questions

- Launch with about 120 entries on a loop, or wait for the full 365?
- Copernicus notice: on screen, or a short on-screen credit plus the full notice in the listing?
- Grey screens: black lines only, or shading by height?
- Portrait caption (see Findings).
- Code licence, before the repo goes public.
