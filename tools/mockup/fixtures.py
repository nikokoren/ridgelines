"""Build look-tuning entries from Copernicus DEM GLO-90.

Each fixture becomes one entry JSON in .cache/entries/, shaped like the planned
pipeline output (docs/brief.md, Data preparation): a square 8-bit heightmap,
base64 encoded, quantised against the crop's own lowest and highest point,
plus a height floor and the high point's position. Range facts come from a
live Wikidata query (see FIXTURES for the ids). Elevation tiles are cached in
.cache/glo90/ and never committed.

The real build reads crop windows over HTTP range requests. This tool
downloads whole 1 degree tiles instead, because it is for look tuning only.

Usage:
    python fixtures.py                # all fixtures
    python fixtures.py karwendel      # one fixture
"""
import base64, json, math, os, sys, urllib.parse, urllib.request
import numpy as np
import tifffile
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
TILES = os.path.join(CACHE, "glo90")
ENTRIES = os.path.join(CACHE, "entries")
R = 6371.0
GRID = 200          # samples per side, brief: about 200 x 200
FLOOR_PCT = 55      # default since 2026-10-01 (was 40, the first chosen mockup)
SNAP_KM = 3         # search radius around the listed high point
SPIKE_M = 250       # a sample this far above its 7 x 7 median is an artefact
UA = "ridgelines-mockup/0.1 (look tuning; github.com/nikokoren/ridgelines)"

# Corpus from PROJECT.md "Next up" item 5. Facts (names, high point, height,
# coordinates, countries) are filled from Wikidata at build time; only the
# crop is curated here. width_km is the width the TRMNL OG full landscape view
# shows; the stored square is wider so bigger views get more terrain, not a
# stretched drawing.
FIXTURES = {
    "karwendel":   dict(qid="Q671207",  role="reference, chosen mockup", lat=47.40, lon=11.45, width_km=46),
    "glockner":    dict(qid="Q454919",  role="tall alpine", lat=47.08, lon=12.70, width_km=40),
    "teton":       dict(qid="Q586241",  role="long and narrow", lat=43.75, lon=-110.83, width_km=40),
    "lyngen":      dict(qid="Q2080571", role="high latitude", lat=69.55, lon=20.05, width_km=50),
    "rwenzori":    dict(qid="Q106540",  role="equatorial", lat=0.38, lon=29.92, width_km=50),
    "taveuni":     dict(qid="Q1138545", role="across the antimeridian", lat=-16.84, lon=179.98, width_km=50),
    "macdonnell":  dict(qid="Q1475441", role="low desert", lat=-23.35, lon=131.60, width_km=60),
    "cuillin":     dict(qid="Q1143317", role="coastal, ocean in frame", lat=57.22, lon=-6.20, width_km=20),
}
# Square side relative to width_km. TRMNL X full landscape is the widest
# drawing (about 1.33 OG widths) and TRMNL X portrait the tallest; 1.4 covers
# both with a margin. Checked by render.py, which flags any window that leaves
# the square.
SQUARE = 1.4
RELIEF = (4, 0.7)        # local relief for every range (Niko, 2026-10-01); --relief 0 0 turns it off
REF_ASPECT = 411 / 780   # TRMNL OG full landscape drawing, measured by render.py


# Shortened country names where a recognised short form exists (Niko, 2026-10-01:
# "United States -> USA"). Hand-checked like Downstream's COUNTRIES table, because
# Wikidata's short name (P1813) is uneven: Australia "AUS", the DR Congo "DRK" in
# German, the UK both "Britain" and "United Kingdom" (queried 2026-10-01).
SHORT_COUNTRY = {
    "Q30":  ("USA", "USA"),                        # as in Downstream, both languages
    "Q145": ("UK", "Vereinigtes Königreich"),      # no accurate common German short form
    "Q974": ("DR\u00a0Congo", "DR\u00a0Kongo"),       # no-break space keeps "DR" with its noun
}


def countries(cs):
    """Country names per language from "Qid<TAB>en<TAB>de|..." rows, short forms where listed,
    sorted by English name so the order is stable."""
    rows = sorted(tuple(r.split("\t")) for r in (cs or "").split("|") if r)
    rows = sorted((SHORT_COUNTRY.get(q, (en, de)) for q, en, de in rows), key=lambda r: r[0])
    return {"en": ", ".join(r[0] for r in rows), "de": ", ".join(r[1] for r in rows)}


def wikidata(qid):
    q = """SELECT ?rl ?rde ?pl ?pde ?elev ?coord
      (GROUP_CONCAT(DISTINCT CONCAT(STRAFTER(STR(?c), "entity/"), "\t", ?cl, "\t", COALESCE(?cdl, ?cl)); separator="|") AS ?cs)
      WHERE {
      BIND(wd:%s AS ?r)
      ?r rdfs:label ?rl FILTER(lang(?rl)="en")
      OPTIONAL { ?r rdfs:label ?rde FILTER(lang(?rde)="de") }
      ?r wdt:P610 ?p . ?p rdfs:label ?pl FILTER(lang(?pl)="en")
      OPTIONAL { ?p rdfs:label ?pde FILTER(lang(?pde)="de") }
      ?p wdt:P2044 ?elev . ?p wdt:P625 ?coord .
      OPTIONAL { ?r wdt:P17 ?c . ?c rdfs:label ?cl FILTER(lang(?cl)="en")
                 OPTIONAL { ?c rdfs:label ?cdl FILTER(lang(?cdl)="de") } }
    } GROUP BY ?rl ?rde ?pl ?pde ?elev ?coord""" % qid
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
    cache = os.path.join(CACHE, "wikidata", qid + ".v2.json")   # live on first run; delete to refresh
    if not os.path.exists(cache):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                body = urllib.request.urlopen(req, timeout=90).read()
                break
            except (TimeoutError, urllib.error.URLError):
                if attempt == 3:
                    raise
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        open(cache, "wb").write(body)
    rows = json.load(open(cache))["results"]["bindings"]
    if not rows:
        raise SystemExit(f"{qid}: no Wikidata row with highest point, elevation and coordinates")
    v = lambda b, k: b[k]["value"] if k in b else None
    b = max(rows, key=lambda b: float(b["elev"]["value"]))  # some peaks carry two elevations
    lon, lat = map(float, v(b, "coord")[6:-1].split())
    return dict(
        qid=qid, name={"en": v(b, "rl"), "de": v(b, "rde") or v(b, "rl")},
        peak={"en": v(b, "pl"), "de": v(b, "pde") or v(b, "pl")},
        peak_m=round(float(v(b, "elev"))), peak_lat=lat, peak_lon=lon,
        country=countries(v(b, "cs")),
        elevations_listed=sorted({round(float(r["elev"]["value"])) for r in rows}),
    )


def tile(lat_i, lon_i, _mem={}):
    """1 degree GLO-90 tile whose south-west corner is (lat_i, lon_i). None where the
    dataset has no tile, which is open ocean."""
    if (lat_i, lon_i) in _mem:
        return _mem[(lat_i, lon_i)]
    ns, ew = ("N" if lat_i >= 0 else "S"), ("E" if lon_i >= 0 else "W")
    name = f"Copernicus_DSM_COG_30_{ns}{abs(lat_i):02d}_00_{ew}{abs(lon_i):03d}_00_DEM"
    path = os.path.join(TILES, name + ".tif")
    if not os.path.exists(path) and not os.path.exists(path + ".missing"):
        os.makedirs(TILES, exist_ok=True)
        try:
            urllib.request.urlretrieve(f"https://copernicus-dem-90m.s3.amazonaws.com/{name}/{name}.tif", path)
        except urllib.error.HTTPError as e:
            if e.code not in (403, 404):
                raise
            open(path + ".missing", "w").close()
    if not os.path.exists(path):
        _mem[(lat_i, lon_i)] = None
        return None
    with tifffile.TiffFile(path) as t:
        p = t.pages[0]
        lon0, lat0 = p.tags["ModelTiepointTag"].value[3:5]
        assert (round(lon0), round(lat0)) == (lon_i, lat_i + 1), (name, lon0, lat0)
        _mem[(lat_i, lon_i)] = p.asarray().astype(np.float64)
    return _mem[(lat_i, lon_i)]


def sample(lat, lon):
    """Bilinear GLO-90 height at arrays of lat/lon. Ocean (no tile) reads 0 m."""
    lon = (lon + 180) % 360 - 180
    out = np.zeros_like(lat)
    li, oi = np.floor(lat).astype(int), np.floor(lon).astype(int)
    for a, o in sorted(set(zip(li.ravel(), oi.ravel()))):
        m = (li == a) & (oi == o)
        t = tile(a, o)
        if t is None:
            continue
        h, w = t.shape
        y = (a + 1 - lat[m]) * h - 0.5
        x = (lon[m] - o) * w - 0.5
        out[m] = ndimage.map_coordinates(t, [y, x], order=1, mode="nearest")
    return out


def build(key, suffix=""):
    f = FIXTURES[key]
    wd = wikidata(f["qid"])
    side = f["width_km"] * SQUARE
    # Oversample 3x, then smooth and decimate, so the 200 grid averages terrain
    # instead of aliasing single 90 m pixels.
    n = GRID * 3
    d = np.linspace(-side / 2, side / 2, n)
    ys, xs = d[::-1], d                                    # rows north to south
    lat = f["lat"] + np.degrees(ys / R)[:, None] + 0 * xs
    lon = f["lon"] + np.degrees(xs[None, :] / (R * np.cos(np.radians(lat))))
    z = sample(lat, lon)
    # Spikes are local outliers, not heights above the range's high point: the
    # square reaches into neighbouring ranges that are genuinely higher (the
    # Karwendel square holds Stubai and Tux summits up to 3,146 m).
    med = ndimage.median_filter(z, size=7)
    bad = (z - med) > SPIKE_M
    spikes = int(bad.sum())
    zmax_raw = float(z.max())
    above_peak = int((z > wd["peak_m"] + 20).sum())
    z[bad] = med[bad]
    z = ndimage.gaussian_filter(z, 1.2)
    z = z.reshape(GRID, 3, GRID, 3).mean(axis=(1, 3))
    z_abs = z.copy()                                       # true heights, for locating the summit
    if RELIEF:
        # Local relief: take away part of the broad shape so ridges,
        # not the massif's dome, carry the ripples. sigma in km, share 0..1.
        sigma_km, share = RELIEF
        z = z - share * ndimage.gaussian_filter(z, sigma_km / (side / GRID), mode="nearest")
    lo, hi = float(z.min()), float(z.max())
    q = np.round((z - lo) / (hi - lo) * 255).astype(np.uint8)
    floor_m = float(np.percentile(z, FLOOR_PCT))
    # Ripple top: the highest sample in the reference window (what the OG full
    # landscape view shows), so higher neighbours at the edge of the stored
    # square do not flatten the range itself. Views use this one scale.
    c = (np.abs(xs) <= f["width_km"] / 2)[None, :] & (np.abs(ys) <= f["width_km"] * REF_ASPECT / 2)[:, None]
    c = c.reshape(GRID, 3, GRID, 3).any(axis=(1, 3))
    top_m = float(z[c].max())
    ocean = float((z_abs <= 0.5).mean())
    # High point position in km from the crop centre (east, north), snapped to
    # the highest terrain within SNAP_KM of the listed point, so the label sits
    # on the summit even when Wikidata's coordinates are rounded. If the listed
    # point is not on high ground, the sign-flipped longitude and latitude are
    # tried too, and the candidate whose summit best matches the listed height
    # wins: Taveuni's Uluigalau is listed at 179.967 E, in the sea; it is at W.
    gx = xs.reshape(GRID, 3).mean(axis=1)
    gy = ys.reshape(GRID, 3).mean(axis=1)

    def km(plat, plon):
        pe = math.radians(plon - f["lon"] + 540) % (2 * math.pi) - math.pi
        return R * pe * math.cos(math.radians(plat)), R * math.radians(plat - f["lat"])

    def summit(plat, plon):
        px, py = km(plat, plon)
        near = (gx[None, :] - px) ** 2 + (gy[:, None] - py) ** 2 <= SNAP_KM ** 2
        if not near.any():
            return None
        r, c = np.unravel_index(np.where(near, z_abs, -np.inf).argmax(), z_abs.shape)
        return float(z_abs[r, c]), (float(gx[c]), float(gy[r])), math.hypot(gx[c] - px, gy[r] - py)

    plat, plon = wd["peak_lat"], wd["peak_lon"]
    at_peak = float(sample(np.array([plat]), np.array([plon]))[0])
    peak_ok = at_peak >= 0.75 * wd["peak_m"]
    cands = [("listed", plat, plon)]
    if not peak_ok:
        cands += [("longitude sign flipped", plat, -plon), ("latitude sign flipped", -plat, plon)]
    found = [(n, summit(a, o)) for n, a, o in cands]
    found = [(n, s_) for n, s_ in found if s_ and s_[0] > 0]
    if found:
        source, (peak_found_m, peak_xy, snap) = min(found, key=lambda t: abs(t[1][0] - wd["peak_m"]))
    else:
        source, peak_found_m, peak_xy, snap = "listed, no terrain nearby", at_peak, km(plat, plon), 0.0
    entry = dict(
        id=key, role=f["role"], wikidata=wd["qid"],
        name=wd["name"], peak=wd["peak"], peak_m=wd["peak_m"], country=wd["country"],
        crop=dict(lat=f["lat"], lon=f["lon"], width_km=f["width_km"], side_km=round(side, 3)),
        grid=GRID, min_m=round(lo, 1), max_m=round(hi, 1),
        floor=int(round((floor_m - lo) / (hi - lo) * 255)), floor_pct=FLOOR_PCT,
        top=int(round((top_m - lo) / (hi - lo) * 255)),
        peak_km=[round(v, 3) for v in peak_xy],
        heights=base64.b64encode(q.tobytes()).decode(),
        # GLO-90 licence, Article 6 (b) and (c), checked 2026-10-02. The notice stays in
        # English; the liability sentence may be translated. Shown on the About page.
        attribution={
            "notice": "produced using Copernicus WorldDEM\u2122-90 \u00a9 DLR e.V. 2010-2014 and \u00a9 Airbus Defence "
                      "and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved",
            "liability": {
                "en": "The organisations in charge of the Copernicus programme by law or by delegation do not incur "
                      "any liability for any use of the Copernicus WorldDEM\u2122-90.",
                "de": "Die Organisationen, die kraft Gesetzes oder im Auftrag f\u00fcr das Copernicus-Programm "
                      "zust\u00e4ndig sind, haften nicht f\u00fcr die Nutzung des Copernicus WorldDEM\u2122-90.",
            },
            "wikidata": {"en": "Range facts: Wikidata (CC0).", "de": "Gebirgsdaten: Wikidata (CC0)."},
        },
        _checks=dict(peak_point_m=round(at_peak), peak_point_ok=peak_ok, peak_source=source,
                     peak_snap_km=round(snap, 2), peak_found_m=round(peak_found_m), spike_pixels=spikes, above_peak_pixels=above_peak, raw_max_m=round(zmax_raw, 1), ocean_share=round(ocean, 3),
                     peak_in_square=bool(abs(peak_xy[0]) < side / 2 and abs(peak_xy[1]) < side / 2),
                     wikidata_elevations=wd["elevations_listed"]),
    )
    os.makedirs(ENTRIES, exist_ok=True)
    path = os.path.join(ENTRIES, key + suffix + ".json")
    with open(path, "w") as fh:
        json.dump(entry, fh, ensure_ascii=False, separators=(",", ":"))
    c = entry["_checks"]
    print(f"{key + suffix:11s} {os.path.getsize(path)/1000:5.1f} kB  {wd['name']['en']}: {wd['peak']['en']} {wd['peak_m']} m"
          f"  crop {lo:.0f} to {hi:.0f} m, raw max {c['raw_max_m']:.0f} m, spikes {spikes}, above high point {above_peak}, ocean {ocean:.0%},"
          f" peak in square {c['peak_in_square']}, Wikidata elevations {c['wikidata_elevations']},"
          f" terrain at listed point {c['peak_point_m']} m, summit {c['peak_found_m']} m {c['peak_snap_km']} km away ({source})")
    return entry


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--list", help="build the entries of a list file instead, e.g. ../../data/beta_de_at.json")
    ap.add_argument("--grid", type=int, default=GRID, help="samples per side (payload grows with the square)")
    ap.add_argument("--suffix", default="", help="written as <key><suffix>.json, for side by side tests")
    ap.add_argument("--relief", nargs=2, type=float, metavar=("SIGMA_KM", "SHARE"), help="local relief, default 4 0.7; 0 0 for absolute height")
    a = ap.parse_args()
    GRID = a.grid
    RELIEF = (tuple(a.relief) if a.relief[1] > 0 else None) if a.relief else RELIEF
    if a.list:
        for e in json.load(open(a.list))["entries"]:
            FIXTURES[e["id"]] = dict(qid=e["wikidata"], role="beta, Germany and Austria",
                                     lat=e["lat"], lon=e["lon"], width_km=e["width_km"])
        keys = a.keys or [e["id"] for e in json.load(open(a.list))["entries"]]
    else:
        keys = a.keys or list(FIXTURES)
    for k in keys:
        build(k, a.suffix)
