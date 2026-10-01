# Mockup tool

Renders TRMNL-sized, 1-bit PNG mockups from real terrain, for tuning the look before the production pipeline exists.

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

For look tuning only. Nothing in the recipe ships from this tool.
