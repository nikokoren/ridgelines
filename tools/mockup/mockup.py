"""Ridgelines look-tuning mockups.

Renders TRMNL-sized PNG mockups from real terrain so the look can be tuned
before the production pipeline exists. Uses MapLibre's demo terrain tiles
(JAXA AW3D30, Mapbox Terrain-RGB encoding) because they are fetchable from
GitHub. They only cover 47 to 48 N and 11 to 12 E. Production data is
Copernicus DEM GLO-90; see docs/brief.md.

Usage:
    python mockup.py                      # chosen look, Karwendel, OG full view
    python mockup.py --lines 56 --ripple 5.5 --out stronger.png
    python mockup.py --mode oblique       # rejected tilted-stack look, for comparison
"""
import argparse, math, os, subprocess, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
TILES = os.path.join(CACHE, "demotiles", "terrain-tiles", "12")
FONT = os.path.join(CACHE, "Inter.ttf")
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf"
Z, TS, R = 12, 512, 6371.0

# Presets must sit inside the demo tile coverage (47-48 N, 11-12 E).
PRESETS = {
    "karwendel": dict(
        lat=47.40, lon=11.45, width_km=46, depth_km=24.5,
        hmax=2749,  # Birkkarspitze, documented high point (en.wikipedia.org/wiki/Karwendel)
        peak=("Birkkarspitze", 47.4111, 11.4378),
        caption="Karwendel · Birkkarspitze 2,749 m · Austria, Germany",
    ),
}

def fetch_tiles():
    if os.path.isdir(TILES):
        return
    os.makedirs(CACHE, exist_ok=True)
    repo = os.path.join(CACHE, "demotiles")
    run = lambda *a: subprocess.run(a, cwd=repo if os.path.isdir(repo) else CACHE, check=True)
    run("git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout",
        "https://github.com/maplibre/demotiles", "demotiles")
    run("git", "sparse-checkout", "set", "terrain-tiles/12")
    run("git", "checkout", "-q", "gh-pages")

def font(size, bold=False):
    if not os.path.exists(FONT):
        try:
            urllib.request.urlretrieve(FONT_URL, FONT)
        except Exception:
            return ImageFont.load_default()
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([14 if size < 20 else 24, 700 if bold else 450])
    except Exception:
        pass
    return f

def gpx(lat, lon):
    """Global Web Mercator pixel at zoom Z for 512 px tiles."""
    x = (lon + 180) / 360 * (2 ** Z) * TS
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * (2 ** Z) * TS
    return x, y

def tile(tx, ty, _cache={}):
    if (tx, ty) not in _cache:
        p = os.path.join(TILES, str(tx), f"{ty}.png")
        if not os.path.exists(p):
            _cache[(tx, ty)] = None
        else:
            a = np.asarray(Image.open(p).convert("RGB")).astype(np.float64)
            _cache[(tx, ty)] = -10000 + (a[..., 0] * 65536 + a[..., 1] * 256 + a[..., 2]) * 0.1
    return _cache[(tx, ty)]

def mosaic(lat0, lat1, lon0, lon1):
    x0, y1 = gpx(lat0, lon0); x1, y0 = gpx(lat1, lon1)
    X0, Y0, X1, Y1 = int(x0) - 2, int(y0) - 2, int(x1) + 3, int(y1) + 3
    m = np.full((Y1 - Y0, X1 - X0), np.nan)
    for ty in range(Y0 // TS, Y1 // TS + 1):
        for tx in range(X0 // TS, X1 // TS + 1):
            t = tile(tx, ty)
            if t is None:
                continue
            ys, xs = max(Y0, ty * TS), max(X0, tx * TS)
            ye, xe = min(Y1, (ty + 1) * TS), min(X1, (tx + 1) * TS)
            m[ys - Y0:ye - Y0, xs - X0:xe - X0] = t[ys - ty * TS:ye - ty * TS, xs - tx * TS:xe - tx * TS]
    return m, X0, Y0

def heightgrid(p, ncols, nrows):
    """Metric grid, rows north (0) to south, cols west to east. Clips spikes above the documented max."""
    pad = 0.05
    lat0 = p["lat"] - math.degrees(p["depth_km"] / 2 / R) - pad
    lat1 = p["lat"] + math.degrees(p["depth_km"] / 2 / R) + pad
    dl = math.degrees(p["width_km"] / 2 / (R * math.cos(math.radians(p["lat"])))) + pad
    m, X0, Y0 = mosaic(lat0, lat1, p["lon"] - dl, p["lon"] + dl)
    if np.isnan(m).any():
        raise SystemExit("crop leaves the demo tile coverage (47-48 N, 11-12 E)")
    bad = m > p["hmax"] + 20
    if bad.any():
        print(f"spike cleanup: {int(bad.sum())} pixels above documented max {p['hmax']} m, highest {m.max():.0f} m")
        lab, _ = ndimage.label(ndimage.binary_dilation(bad, iterations=8))
        for sl in ndimage.find_objects(lab):
            y0, y1 = max(sl[0].start - 40, 0), sl[0].stop + 40
            x0, x1 = max(sl[1].start - 40, 0), sl[1].stop + 40
            sub, mask = m[y0:y1, x0:x1], lab[y0:y1, x0:x1] > 0
            sub[mask] = np.median(sub[~mask])
            sm = ndimage.gaussian_filter(sub, 4)
            sub[mask] = sm[mask]
        m = np.minimum(m, p["hmax"])
    cell_px = (p["width_km"] * 1000 / (ncols - 1)) / (40075016 * math.cos(math.radians(p["lat"])) / (2 ** Z * TS))
    m = ndimage.gaussian_filter(m, sigma=max(cell_px / 2.5, 1))
    g = np.zeros((nrows, ncols)); ll = np.zeros((nrows, ncols, 2))
    for r in range(nrows):
        lat = p["lat"] + math.degrees((p["depth_km"] / 2 - r * p["depth_km"] / (nrows - 1)) / R)
        for c in range(ncols):
            de = -p["width_km"] / 2 + c * p["width_km"] / (ncols - 1)
            lon = p["lon"] + math.degrees(de / (R * math.cos(math.radians(lat))))
            x, y = gpx(lat, lon)
            g[r, c] = ndimage.map_coordinates(m, [[y - Y0], [x - X0]], order=1)[0]
            ll[r, c] = (lat, lon)
    return g, ll

def render(g, ll, p, W=800, H=480, lines=64, ripple=4.0, floor_pct=40, mode="plan", tb=40, label=True):
    """mode plan: top-down ripples (chosen). oblique: tilted stack (rejected). headon: front panorama (rejected)."""
    rows = np.linspace(0, g.shape[0] - 1, lines).round().astype(int)
    gg = np.maximum(g, np.percentile(g, floor_pct))[rows]
    lo, hi = gg.min(), gg.max()
    mx, top, bot = 12, 10, H - tb - 8
    if mode == "plan":
        # Same arithmetic as the chosen 2026-10-01 mockup, so it reproduces pixel for pixel.
        A = ripple * (bot - top - ripple * 8) / (lines - 1); sp = (bot - top - A) / (lines - 1)
    elif mode == "oblique":
        A = 0.22 * (bot - top); sp = (bot - top - A) / (lines - 1)
    else:
        A = 0.5 * (bot - top); sp = 0
    name, plat, plon = p["peak"]
    d2 = (ll[..., 0] - plat) ** 2 + ((ll[..., 1] - plon) * math.cos(math.radians(plat))) ** 2
    r0, pc = np.unravel_index(d2.argmin(), d2.shape)
    pr = int(np.abs(rows - r0).argmin())
    img = Image.new("L", (W, H), 255); d = ImageDraw.Draw(img)
    xs = np.linspace(mx, W - mx, g.shape[1]); peakpt = None
    for i in range(lines):
        base = bot if mode == "headon" else top + A + i * sp
        ys = base - (gg[i] - lo) / (hi - lo) * A
        pts = list(zip(xs, ys))
        d.polygon(pts + [(W - mx, bot + 2), (mx, bot + 2)], fill=255)
        d.line(pts, fill=0, width=1)
        if i == pr:
            peakpt = (xs[pc], ys[pc])
    # title bar mock (not a framework render)
    d.line([(0, H - tb), (W, H - tb)], fill=0, width=2)
    ix, iy, s = mx, H - tb + tb * 0.22, tb * 0.56
    d.polygon([(ix, iy + s), (ix + s * .42, iy), (ix + s * .62, iy + s * .35), (ix + s * .78, iy + s * .18), (ix + s, iy + s)], fill=0)
    d.text((ix + s + 8, H - tb / 2), "Ridgelines", font=font(int(tb * .42), True), fill=0, anchor="lm")
    d.text((W - mx, H - tb / 2), p["caption"], font=font(int(tb * .38)), fill=0, anchor="rm")
    if label and peakpt:
        px, py = peakpt; lf = font(int(tb * .34)); tw = d.textlength(name, font=lf)
        d.line([(px, py - 4), (px, py - 14)], fill=0)
        bx = min(max(px - tw / 2, mx), W - mx - tw)
        d.rectangle([bx - 3, py - 31, bx + tw + 3, py - 15], fill=255)
        d.text((bx, py - 23), name, font=lf, fill=0, anchor="lm")
    return img.point(lambda v: 255 if v > 127 else 0)  # 1-bit, like a TRMNL OG

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="karwendel", choices=PRESETS)
    ap.add_argument("--mode", default="plan", choices=["plan", "oblique", "headon"])
    ap.add_argument("--lines", type=int, default=64)
    ap.add_argument("--ripple", type=float, default=4.0, help="tallest ripple in line gaps (plan mode)")
    ap.add_argument("--floor", type=float, default=40, help="height floor as a percentile of the crop")
    ap.add_argument("--out", default="mockup.png")
    a = ap.parse_args()
    fetch_tiles()
    p = PRESETS[a.preset]
    g, ll = heightgrid(p, 260, 140)
    render(g, ll, p, lines=a.lines, ripple=a.ripple, floor_pct=a.floor, mode=a.mode).save(a.out)
    print("wrote", a.out)
