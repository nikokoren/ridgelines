# Ridgelines recipe (beta)

TRMNL private plugin, Polling strategy. Framework classes only (Framework 3.4); the SVG line art takes every colour and size from TRMNLPaint.

## Files

| File | TRMNL tab or field |
| --- | --- |
| `settings.yml` | Plugin settings: name, Polling strategy, Polling URL, refresh every 60 minutes, and the form fields (About with the Copernicus and Wikidata notices; Language; Units; Peak name; Info box; Title bar) |
| `polling_url.txt` | The Polling URL, also inside `settings.yml`. Written by `pipeline/publish.py`; the build fails if the two differ |
| `shared.txt` | **Shared** tab: reads the settings (an empty value counts as the default) and holds the drawing script |
| `full.txt`, `half_horizontal.txt`, `half_vertical.txt`, `quadrant.txt` | One tab per view |
| `tools/render.rb` | Renders a view with Ruby Liquid, the engine TRMNL runs. Used by `tools/mockup/render.py` |

## How a day's range is picked

The Polling URL adds the user's UTC offset (TRMNL sends seconds) to the current time, divides by a day, takes the result modulo 30, and fetches `https://nikokoren.github.io/ridgelines/beta/d/<n>.json`. Every device sees the same range on the same local date, and it changes at local midnight. The 30 files hold the beta list (`data/beta_de_at.json`) in a fixed shuffled order (seed 20261002). Checked with Ruby Liquid 5.14.0 for UTC offsets from minus 12 to plus 14 hours, given as a number, a string, or missing; not yet confirmed on a device.

Each file is one payload of about 55 kB: the heightmap and every word on screen, keyed by language and units. The templates hold no words except the plugin name and the error screen.

## Installing

1. In TRMNL, create a private plugin with the **Polling** strategy.
2. Paste the Polling URL from `polling_url.txt`, set the refresh interval to 60 minutes.
3. Add the form fields from `settings.yml` (keynames `language`, `units`, `peak_label`, `info_box`, `title_bar`, with the options and defaults listed there), and paste the About text.
4. Paste `shared.txt` into the Shared tab and each view file into its tab.

Alternatively zip `settings.yml` and the `.txt` files (renamed to `.liquid`) for TRMNL's plugin import; that path has not been tried.

The Area setting is left out of the beta: with only Germany and Austria every choice would show the same 30 ranges.
