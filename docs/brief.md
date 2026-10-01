# Ridgelines: brief and requirements

Snapshot of the living brief in Claude Docs, exported 2026-10-01. PROJECT.md holds anything newer.

## Status and summary

Parked. Ridgelines is a back-pocket recipe and no work starts until the What to Wear overhaul ships.

Ridgelines shows one real mountain range per day as a map seen from straight above. Evenly spaced lines run west to east, and the terrain under each line lifts it gently, so the range appears as bands of ripples drawn only in black lines. A small caption names the range, its highest peak with height, and the country. The screen changes once a day and is designed to be looked at, not read.

## Why build it

Ambient art is one of the store's strongest categories, and a real-terrain take on it looks unclaimed.

- **Appeal.** On the store's [popularity list](https://trmnl.com/recipes?sort-by=popularity) (checked 2026-10-01), Art of the Day has 1,245 connections and Shan Shui Chinese Landscape, a generated mountain painting, has 1,081. Both sit in the top 12.
- **Uniqueness.** Shan Shui draws invented mountains. Ridgelines draws real ones from elevation data, which is a different type. A web search on 2026-10-01 found no TRMNL recipe for terrain, contours or ridgelines. The store's own search was not run, so that check is still owed (see Verification plan).
- **Fit.** It sits between Is the Mountain Out (Rainier visibility) and Downstream (rivers on a map), and follows Postcard's pattern of one discovery a day from public data. It reuses the line-art look of the Aurora Watch polar chart.

## What the user sees

Every view shows the same day's range, cropped to the view's shape, with a short caption in the native title bar.

- **The drawing.** A top-down map of the range. Evenly spaced lines run west to east, ordered north to south, and the terrain under each line lifts it upward. Nothing tilts, so the range keeps its real shape. Chosen on 2026-10-01 over a tilted 3D stack and a front-on panorama.
- **Gentle ripples.** The tallest ripple is about four line gaps high. Each line is filled with the background colour below it, which hides the small overlaps where ripples touch.
- **Height floor.** Terrain below a floor height draws as straight lines, so valleys stay calm and ridges carry the picture. The chosen mockup used the crop's 40th percentile height.
- **High point.** A small tick and label mark the range's highest summit inside the drawing.
- **Caption.** Range name, highest peak with its height, and country, for example "Karwendel · Birkkarspitze 2,749 m · Austria, Germany".
- **Rhythm.** One range per calendar day in the device's time zone. Every device sees the same range on the same day.

Line spacing stays the same in every view, so smaller views show a tighter crop rather than a shrunken map. All counts are starting targets to tune against a wider set of real ranges. The full landscape view matches the chosen mockup.

| View | Lines (target) | Caption |
| --- | --- | --- |
| Full, landscape | 64 | Range, peak with height, country |
| Full, portrait | about 110 | Range, peak with height, country if it fits (see open questions) |
| Half horizontal | about 30 | Range and country |
| Half vertical | about 64 | Range only |
| Quadrant | about 30 | Range only |

The large screen class (TRMNL V2, Kindle Scribe) gets more lines at the same spacing, so it shows more detail rather than a stretched OG drawing.

## Settings

Four settings, all selects, no location field. The recipe works with zero setup.

| Setting | Options | Default |
| --- | --- | --- |
| Language | English, Deutsch | English |
| Area | World, Europe, Americas, Asia and Oceania, Africa | World |
| Height units | Metres, feet | Metres |
| Caption | Show, hide (pure art mode) | Show |

Area filters the daily list rather than changing it. A user on Europe sees the next European range in the shared calendar, so two Europe users still see the same range on the same day. Line density is never a setting; the template derives it from the view and screen class.

## Data sources and licensing

Two sources, both usable with Creator Fund payouts: Copernicus DEM for the terrain and Wikidata for the list. No NC-licensed data anywhere.

| Need | Source | Licence | Obligations |
| --- | --- | --- | --- |
| Terrain heights | [Copernicus DEM GLO-90](https://registry.opendata.aws/copernicus-dem/), 90 m, global, Cloud Optimized GeoTIFFs on AWS Open Data, no account needed | Free; reproduction, distribution and adaptation granted; no non-commercial clause ([licence text](https://docs.sentinel-hub.com/api/latest/static/files/data/dem/resources/license/License-COPDEM-30.pdf)) | Show the "produced using Copernicus WorldDEM" notice for modified data, add the liability sentence, never imply endorsement |
| Ranges, highest peaks, heights, coordinates, EN and DE names | [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) | CC0 | None; credit as a courtesy |

- **Why GLO-90, not GLO-30.** GLO-90 covers the whole globe, while the public GLO-30 set still lacks some countries' tiles. 90 m sampling also exceeds what any TRMNL screen can show for a range-sized crop.
- **Surface, not bare earth.** Copernicus DEM includes buildings and forest. At mountain-range scale that is invisible.
- **Wikidata fields.** Mountain ranges with a highest point, that peak's elevation and coordinates, and English and German labels. Confirm the property IDs against a live query before writing the build script.
- **Excluded on purpose.** Open-Meteo's elevation API (free tier is non-commercial only) and OpenStreetMap peaks (share-alike on derived databases, and not needed).

## Data preparation

All heavy work happens once, offline, in a build script. The elevation data never changes, so nothing is computed daily.

1. **Curate the list.** Query Wikidata for mountain ranges with a highest point and an elevation. Hand-pick up to 365 entries (about 120 at launch, see Risks) with a good spread across continents, cutting duplicates and sub-ranges. Each entry stores: id, EN and DE names, peak name and height, country, crop centre, and crop width in km.
2. **Fetch only what's needed.** Read just the crop window from the Copernicus COGs over HTTP range requests, never whole tiles.
3. **Resample in metres, not degrees.** Project each crop to a local metric projection before sampling, so slices are true distances. Degree grids stretch badly at high latitudes. Then clip spikes: cap heights at the documented high point and patch the area around any spike. The JAXA data used for the mockups showed 2,935 m on a Karwendel ridge, while the range tops out at 2,749 m.
4. **Store a compact heightmap.** A square grid of about 200 × 200 samples, quantised to 8 bits against the crop's own lowest and highest point, base64 encoded. 256 levels is finer than any screen's line amplitude in pixels, so quantising costs nothing visible. Store each entry's height floor with it, starting at the crop's 40th percentile height (the chosen mockup's value), so the template can flatten valleys and the value can be tuned per entry.
5. **Review every crop.** The build renders a contact sheet of all entries for a human pass, and flags crops that are mostly flat, mostly ocean, or have the high point outside the frame.
6. **Assign days.** A fixed-seed shuffle maps day of year to entry, so the calendar is deterministic. The Area setting picks the next entry in that area at or after today's slot.

Runs in GitHub Actions on demand, not on a schedule. Output is one JSON file per entry plus a calendar index.

## Backend and delivery

A small Cloudflare Worker picks today's entry and returns its file. It does no terrain work and writes nothing.

- **Storage.** The prepared entry files live in R2 (roughly 365 files of well under 100 KB each). No KV at all, so the write quota that took Nearby Nextbike down cannot recur.
- **Request.** TRMNL polls the Worker with the user's UTC offset and Area. The offset arrives in seconds, not minutes (the Nearby Nextbike day-label bug).
- **Response.** Entry metadata, both EN and DE names, the base64 heightmap and the attribution strings. Language and units are applied in the template, so one cached response serves every user on the same entry.
- **Size cap.** Private plugins reject polled payloads over 100 KB ([TRMNL help](https://help.trmnl.com/en/articles/12996946-parsing-plugins-with-the-sandbox-runtime)). Budget 80 KB per response and measure every entry in the build, not a sample.
- **Caching.** Entry files are immutable, so cache them at the edge for a long time, keyed by entry id. Only the date-to-entry lookup runs per request.
- **Refresh.** Content changes once a day, so a long TRMNL refresh interval is fine. A refresh shortly after local midnight is enough.

## Template requirements

Native TRMNL framework only, latest version at build time. On 2026-10-01 the 3.3 docs URL already redirects to [3.4](https://trmnl.com/framework/docs/3.4/responsive), so re-fetch the docs before writing any markup.

- **Framework only, no exceptions.** Every layout, spacing, typography and colour decision uses TRMNL framework classes: the latest version, plus anything from earlier versions that the latest still supports. No custom CSS, no `<style>` blocks, no inline style attributes, no self-made style classes, no hard-coded colours or pixel sizes, no workarounds. The SVG line art inside the drawing container is the only thing drawn outside framework classes, and it takes every colour and size from the framework's own Paint API. If something cannot be built from framework classes, stop and flag it instead of working around it.
- **Structure.** Standard screen, view, layout and title bar, with the title bar at the bottom where the framework places it. Full, half horizontal, half vertical and quadrant views, all working inside mashups.
- **Drawing.** Plugin JS decodes the heightmap and draws the lines as inline SVG sized to the drawing container. Lines are drawn north to south, each filled with the background colour and then stroked, which hides the small overlaps where ripples touch.
- **Container height.** The Aurora Watch layout collapsed once and the drawing fell back to a fixed size over the text. Reuse the proven Aurora layout pattern, and refuse to draw (show the caption alone) if the container measures zero.
- **Framework paint.** Take line and fill colours from the [Paint API](https://trmnl.com/framework/docs/3.4/paint_api) and scale stroke widths and spacing with its px() helper. That keeps 1-bit, 2-bit, 4-bit, dark theme and device density correct without per-device code.
- **Responsive rules.** Line count follows the view and the sm, md and lg size classes; portrait follows the screen's portrait class. Caption text uses responsive title and label sizes. No hard-coded pixel sizes anywhere.
- **Grey screens.** A top-down map has no depth to shade, so every screen starts with black lines. Whether grey adds anything, such as shading by height, is an open question.
- **Delivery.** Liquid templates as .txt files.
- **Store image.** Built from a real entry's data, not mock lines.

## Text and language

English and German from the first release, with every string keyed by language code so a third language is one more dictionary.

- **Names.** Range, peak and country names come from Wikidata labels per language, falling back to English when a German label is missing.
- **Numbers.** Heights follow the language's number format (3,798 m in English, 3.798 m in German). Feet are converted and rounded to the nearest 10 ft.
- **Store listing.** English and German descriptions, using the description-de field as What to Wear does.
- **Attribution.** The Copernicus licence allows the liability sentence in translation, so the German listing can carry it in German.

## Verification plan

Everything is tested against real prepared entries, never invented grids, and swept across the full state space.

- [ ] Search the store for ridgeline, terrain, elevation, topo, contour and mountain before any build work. Record the terms and hit counts.
- [ ] Re-fetch the framework docs from the unversioned URL and stamp the version and date in PROJECT.md.
- [ ] Re-check the GLO-90 licence against the newer ESA annex the AWS registry links, which differs from the GLO-30 text checked here.
- [ ] Confirm the Wikidata property IDs with a live query.
- [ ] Build a fixture corpus of real entries covering a tall alpine range, a long narrow range, a high-latitude range, an equatorial range, one crossing the antimeridian, a low desert range and a coastal range with ocean in frame.
- [ ] Sweep every entry across all five views, three bit depths and three size classes. Measure the payload of every entry, not a sample.
- [ ] Sweep UTC offsets from minus 12 h to plus 14 h around local midnight to prove the day flip.
- [ ] Render every caption in both languages at quadrant size to catch truncation.
- [ ] Prove each fix with before and after screenshots.
- [ ] Write findings into the repo, dated, each with a re-check instruction.

## Risks and open questions

The biggest risk is curation effort, not code: 365 hand-checked crops is Postcard-sized work.

**Risks**

- **Curation load.** Mitigation: launch with about 120 entries looping, and grow the list in later releases.
- **1-bit legibility.** Dense lines can turn to noise at 800 × 480. Mitigation: the first milestone is three real entries rendered on a real OG before any pipeline polish.
- **Dull crops.** Plateaus and long thin ranges can look flat in a fixed crop. Mitigation: the contact sheet review, plus per-entry crop width and height floor.
- **Borders and names.** Cross-border and disputed ranges make a single country label political. Mitigation: list all countries for cross-border ranges and avoid disputed areas in v1.
- **Style association.** Stacked ridgelines are widely linked to a famous album cover. The listing, icon and store image must not reference or imitate it.

**Open questions**

- Does the 100 KB cap apply before or after compression? The design assumes before.
- Does the Copernicus notice have to appear on screen, or is a short on-screen credit plus the full notice in the listing enough? Ask the Copernicus helpdesk before launch.
- Portrait caption: range, peak with height and country did not fit next to the plugin title at 480 px wide in the mockups. Drop the country in portrait, or drop the title?

## Out of scope for v1

- Ranges near the user's location, and any location field.
- Pinning a favourite range.
- Other drawing styles, such as contour lines.
- Labels for summits other than the highest.
- Live data on the range, such as snow or weather.
- Colour-specific palettes beyond what the framework's paint gives automatically.

## Sources

All checked on 2026-10-01. Re-check each before relying on it at build time.

| Source | What it confirmed | How checked |
| --- | --- | --- |
| [TRMNL recipes, most popular](https://trmnl.com/recipes?sort-by=popularity) | Art of the Day and Shan Shui connection counts | Page opened |
| [TRMNL framework, Responsive](https://trmnl.com/framework/docs/3.4/responsive) | Current version 3.4, size classes, bit depths, portrait variants | Page opened |
| [TRMNL framework, Paint API](https://trmnl.com/framework/docs/3.4/paint_api) | JS paint colours and px() scaling for custom drawing | Page opened |
| [TRMNL help, Sandbox Runtime](https://help.trmnl.com/en/articles/12996946-parsing-plugins-with-the-sandbox-runtime) | 100 KB cap on polled payloads | Page opened |
| [Copernicus WorldDEM-30 licence](https://docs.sentinel-hub.com/api/latest/static/files/data/dem/resources/license/License-COPDEM-30.pdf) | Free use incl. adaptation, notice and liability sentence required | PDF opened |
| [Copernicus DEM on AWS Open Data](https://registry.opendata.aws/copernicus-dem/) | GLO-90 global coverage, COG format, no account needed | Search result only; open it |
| [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing) | Structured data is CC0 | Page opened |
| [Open-Meteo terms](https://open-meteo.com/en/terms) | Free API is non-commercial only | Search result only; open it |

The 2026-10-01 mockups used [MapLibre's demo terrain tiles](https://github.com/maplibre/demotiles) (JAXA AW3D30, covering 47 to 48°N and 11 to 12°E), not Copernicus. That is why they show the Karwendel instead of the Großglockner. Karwendel high point: [Birkkarspitze, 2,749 m](https://en.wikipedia.org/wiki/Karwendel).
