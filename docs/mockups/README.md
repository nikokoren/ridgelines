# Mockups

All rendered on 2026-10-01 from real terrain: MapLibre's demo tiles (JAXA AW3D30, attribution "AW3D30 (JAXA)" per the tileset's metadata). Mock title bars, not framework renders.

| File | What it shows | Outcome |
| --- | --- | --- |
| `chosen_topdown_64_lines.png` | Top-down map, 64 lines, tallest ripple about 4 line gaps, floor at the 40th percentile, TRMNL OG 800 × 480, 1-bit | **Chosen direction** |
| `options_front_vs_above.png` | Front-on panorama (1-bit and grey) next to two top-down variants (64 lines gentle, 56 lines stronger) | Top-down, 64 lines, gentle picked |
| `early_tilted_stack.png` | First attempt: tilted 3D stack in four views (OG, grey, portrait, quadrant) | Rejected as too erratic |

Reproduce the chosen one with `python tools/mockup/mockup.py` (see tools/mockup/README.md).
