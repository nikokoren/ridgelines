# Mockups

All rendered on 2026-10-01 from real terrain: MapLibre's demo tiles (JAXA AW3D30, attribution "AW3D30 (JAXA)" per the tileset's metadata). Mock title bars, not framework renders.

| File | What it shows | Outcome |
| --- | --- | --- |
| `chosen_topdown_64_lines.png` | Top-down map, 64 lines, tallest ripple about 4 line gaps, floor at the 40th percentile, TRMNL OG 800 × 480, 1-bit | **Chosen direction** |
| `options_front_vs_above.png` | Front-on panorama (1-bit and grey) next to two top-down variants (64 lines gentle, 56 lines stronger) | Top-down, 64 lines, gentle picked |
| `early_tilted_stack.png` | First attempt: tilted 3D stack in four views (OG, grey, portrait, quadrant) | Rejected as too erratic |

## Framework renders from Copernicus GLO-90, 2026-10-01

Real TRMNL framework 3.4 markup, CSS, fonts and title bar, drawn by tools/mockup/template/ridgelines.js from entries built with tools/mockup/fixtures.py. Bit depth is approximated after capture. See PROJECT.md Findings for what each sheet showed.

| File | What it shows |
| --- | --- |
| `compare_resolution.png` | Karwendel: chosen JAXA mockup vs GLO-90 at 200, 280 and 400 grids, and three ripple scales |
| `corpus_og.png` | All 8 fixture entries at the first chosen settings (floor 40th percentile, ripple 4 gaps, absolute height), OG 1-bit, info box on, title bar off |
| `corpus_tuned_og.png` | The same at the defaults decided 2026-10-01 (floor 55th percentile, ripple 5 gaps, local relief) |
| `compare_relief.png` | Absolute height vs local relief, floor 55th percentile, ripple 5 gaps |
| `views_karwendel.png`, `views_rwenzori.png` | Defaults: every view on OG 1-bit and 2-bit, TRMNL X 4-bit and Kindle 2024, plus portrait |
| `lang_de.png` | German captions in quadrant, half horizontal and full views |
| `beta_1.png`, `beta_2.png`, `beta_3.png` | The 30 Germany and Austria beta ranges (data/beta_de_at.json) at the defaults, OG 1-bit |
| `shade_ogv2.png`, `shade_v2.png` | Black lines only vs two shading by height variants, 2-bit OG and 4-bit TRMNL X |

Regenerate with `python tools/mockup/sweep.py <mode>` (modes listed in the script).

Reproduce the chosen one with `python tools/mockup/mockup.py` (see tools/mockup/README.md).
