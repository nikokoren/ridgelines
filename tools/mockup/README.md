# Mockup tools

Render TRMNL mockups from real terrain, for tuning the look before the production pipeline exists. For look tuning only. Nothing in the recipe ships from these tools.

| Script | What it does |
| --- | --- |
| `fixtures.py` | Shim for `pipeline/entries.py`, where the entry build moved on 2026-10-02 (the build ships, this folder does not) |
| `render.py` | Renders one entry through the real recipe templates (`recipe/*.txt`, Ruby Liquid via `recipe/tools/render.rb`) and the real TRMNL framework (CSS, JS, fonts from trmnl.com) in Chromium |
| `sweep.py` | Contact sheets: corpus, ripple x floor tuning, every view and device, German captions, resolution and relief comparisons |
| `mockup.py` | The original PIL tool on JAXA demo tiles that produced the chosen 2026-10-01 mockup |

## Framework renders from Copernicus (fixtures.py, render.py, sweep.py)

```
pip install -r requirements.txt
python ../../pipeline/entries.py            # 8 entries into ../../.cache/entries/, about 55 kB each
python render.py --entry glockner --device v2 --view quadrant --out q.png
LOOK='{"ripple": 5, "floorPct": 55}' python sweep.py corpus out/
python sweep.py views out/                  # 8 entries x 18 view and device combinations, plus out/views_report.json
```

- **Data.** Whole 1 degree GLO-90 tiles are cached in the repo root's `.cache/glo90/` (81 MB for the eight fixtures, measured 2026-10-01). Missing tiles are open ocean and read as 0 m. Wikidata answers are cached per query in `.cache/wikidata/`; delete a file to re-query. The real build reads crop windows over HTTP range requests instead.
- **Framework.** `render.py` downloads `plugins.css`, `plugins.js`, the fonts and the placeholder title bar icon from trmnl.com into `.cache/fw/` on first run. Delete that folder to pick up a new framework release. Pages need `<body class="environment trmnl">`, or no framework rule applies.
- **Browser.** Uses the Chromium at `/opt/pw-browsers/chromium-1194`. Change `CHROME` in render.py for another install.
- **Capture.** The framework scales the screen by the device's `--pixel-ratio` itself, so screenshots are taken at the panel's physical size (TRMNL X: 1872 x 1404) with a device scale factor of 1. Bit depth is approximated afterwards: 1-bit threshold, 2-bit four greys, 4-bit sixteen greys. TRMNL's own conversion may differ.
- **Settings** (render.py `--settings`): the recipe's form fields, e.g. `{"language": "de", "title_bar": "yes"}`. Needs Ruby with the liquid gem.
- **Look overrides** (render.py `--look`, sweep.py `LOOK`, passed to the drawing as `window.RIDGELINES_LOOK`): `ripple` (gaps), `gap` (px before scaling), `floorPct` (percentile of the stored square, tuning only), `floor` (8-bit value), `norm` (`entry` default, `window`, `crop`), `label`.
- **Not framework markup:** the contact sheet frames and their captions. Everything inside each frame is.

## JAXA demo tiles (mockup.py)

```
pip install -r requirements.txt
python mockup.py                                   # chosen look: Karwendel, top-down, 64 lines
python mockup.py --lines 56 --ripple 5.5 --out stronger.png
python mockup.py --floor 50 --out median_floor.png
python mockup.py --mode oblique --out tilted.png   # rejected tilted stack, for comparison
python mockup.py --mode headon --out front.png     # rejected front-on panorama
```

- **Data.** The first run sparse-clones the zoom 12 terrain tiles from [maplibre/demotiles](https://github.com/maplibre/demotiles) (about 57 MB on disk including git objects, measured 2026-10-01) and downloads the Inter font into `.cache/`, which is gitignored. The tiles are JAXA AW3D30 in Mapbox Terrain-RGB encoding.
- **Coverage.** The demo tiles only cover 47 to 48°N and 11 to 12°E, so the only preset is the Karwendel. Tuning across the planned fixture corpus needs the tool extended to read Copernicus GLO-90.
- **Spikes.** Heights above the preset's documented high point are patched and clipped. The Karwendel crop has a spike reaching 3,011 m against a documented 2,749 m.
- **Check.** With default settings the output matched `docs/mockups/chosen_topdown_64_lines.png` exactly on 2026-10-01 (0 of 384,000 pixels differ). Re-run that diff after any change.
