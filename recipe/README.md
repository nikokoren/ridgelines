# Ridgelines recipe

TRMNL private plugin, Polling strategy. Framework classes only (Framework 3.4); the SVG line art takes every colour and size from TRMNLPaint.

## Files

| File | TRMNL tab or field |
| --- | --- |
| `settings.yml` | Plugin settings: name, Polling strategy, Polling URL, refresh every 60 minutes, and the form fields (About in English and German, `description` and `description-de`, each with the Copernicus and Wikidata notices; Area; Language; Units; Peak name; Info box; Title bar; Globe view) |
| `polling_url.txt` | The Polling URL, also inside `settings.yml`. Written by `pipeline/publish.py`; the build fails if the two differ |
| `shared.txt` | **Shared** tab: reads the settings (an empty value counts as the default) and holds the drawing script |
| `full.txt`, `half_horizontal.txt`, `half_vertical.txt`, `quadrant.txt` | One tab per view |
| `tools/render.rb` | Renders a view with Ruby Liquid, the engine TRMNL runs. Used by `tools/mockup/render.py` |
| `tools/polling_url.rb` | Renders the Polling URL with Ruby Liquid at a given time. Used by `pipeline/test_polling_url.py` |

## How a day's range is picked

The Polling URL adds the user's UTC offset (TRMNL sends seconds) to the current time and divides by a day. It then reads the Area setting (a multi select; none ticked means every area) and takes turns through the ticked areas in a fixed order (Europe, Americas, Asia and Oceania, Africa), one per day: the area is `ticked[day mod k]`, the slot within it `(day div k) mod count`. It fetches `https://nikokoren.github.io/ridgelines/<area>/d/<slot>.json`. Devices with the same ticks see the same range on the same local date, it changes at local midnight, and with one area ticked 365 ranges last a year without repeats. Each area folder holds its list (`data/release/<area>.json`) in a fixed shuffled order (seed 20261002). Only areas with a published list appear in the URL; a ticked area without one is ignored.

With Expedition mode on (`expedition`, off by default) the ticked areas take turns by the week instead, starting Monday at local midnight: the week is `(day + 3) div 7` (1970-01-01, day 0, was a Thursday), the area `ticked[week mod k]`, and the slot `((week div k) * 7 + weekday - 3) mod count`, with weekday 0 for Monday. That counter grows by one on every day an area is shown, as `day div k` does in daily mode, so each area still runs a year without repeats, switching the mode moves an area's list by at most 7 ranges, and with one area ticked both modes give the same range. `pipeline/test_polling_url.py` checks both modes in Ruby Liquid and proves these properties on the rule.

`pipeline/test_polling_url.py` renders the URL with Ruby Liquid 5.14.0 for every combination of ticks, the Area value as a list, as text and missing, UTC offsets from minus 12 to plus 14 hours as numbers and as text, over nine days, and compares each with the rule above. The site workflow runs it on every build. Not yet confirmed on a device, in particular whether TRMNL hands the multi select to the Polling URL as a list or as text (both work).

The beta folder (`beta/d/<n>.json`, 30 ranges in Germany and Austria, slot `day mod 30`) stays published for installs that still use the beta URL.

Each file is one payload of about 55 kB: the heightmap and every word on screen, keyed by language and units. The templates hold no words except the plugin name and the error screen.

## Installing

1. In TRMNL, create a private plugin with the **Polling** strategy.
2. Paste the Polling URL from `polling_url.txt`, set the refresh interval to 60 minutes.
3. Add the form fields from `settings.yml` (keynames `area` (multiple), `expedition`, `language`, `units`, `peak_label`, `info_box`, `title_bar`, `world_map`, with the options and defaults listed there), and paste the About text in both languages.
4. Paste `shared.txt` into the Shared tab and each view file into its tab.

Alternatively zip `settings.yml` and the `.txt` files (renamed to `.liquid`) for TRMNL's plugin import; that path has not been tried.

## Globe view

Globe view is off by default (`world_map`). It adds a round globe rotated to centre the range crop location
in the bottom-right corner of full views, landscape and portrait. In portrait the info box
narrows to leave room. The continents are outlined, with a solid dot at the centre marking the location. Half views and quadrants never show it. There are no extra network requests
during rendering. The globe uses public-domain Natural Earth 1:110m land, simplified for this size
(see tools/world_map.py); very small islands are omitted, but their locations still get a dot.
A fisheye projection magnifies geography near the dot by up to 3x, compressing the outer
hemisphere into the same circular rim. This is a deliberately stylised locator. Projection
and hemisphere clipping use bundled d3-geo, with its licence notices
in Shared and tools/globe-LICENSE.txt. tools/globe.js documents how to regenerate the bundle.

After updating the templates and adding the boolean field, rebuild and deploy the Pages payloads
with pipeline/publish.py so they include location.lat and location.lon. Existing payloads without
coordinates still render normally, with the locator hidden until the data is updated.
