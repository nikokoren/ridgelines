"""Build Ridgelines entries from Copernicus DEM GLO-90 and Wikidata.

Each range becomes one entry JSON in .cache/entries/ (docs/brief.md, Data
preparation): a square 8-bit heightmap, base64 encoded, quantised against the
crop's own lowest and highest point, plus a height floor, a ripple top and the
high point's position. Range facts come from a live Wikidata query. Elevation
tiles are cached in .cache/glo90/ and never committed; nor are entries.

Whole 1 degree tiles are downloaded. The brief's HTTP range requests are an
optimisation for the full list; the beta's 30 ranges need about 40 tiles.

Usage (from the repo root):
    python pipeline/entries.py                                # the look tuning corpus (FIXTURES)
    python pipeline/entries.py karwendel                      # one of them
    python pipeline/entries.py --list data/beta_de_at.json    # a curated list
pipeline/publish.py builds the published site from a list.
"""
import base64, collections, http.client, json, math, os, re, sys, threading, time, urllib.error, urllib.parse, urllib.request
import numpy as np
import tifffile
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("RIDGELINES_CACHE", os.path.join(HERE, "..", ".cache"))
TILES = os.path.join(CACHE, "glo90")
ENTRIES = os.path.join(CACHE, "entries")
R = 6371.0
GRID = 200          # samples per side, brief: about 200 x 200
FLOOR_PCT = 55      # default since 2026-10-01 (was 40, the first chosen mockup)
SNAP_KM = 3         # search radius around the listed high point
SPIKE_M = 250       # a sample this far above its 7 x 7 median is an artefact
QUIET = False
# Fingerprint of this file, stored in every entry; publish.py rebuilds entries built by another version.
BUILD = __import__("hashlib").sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()[:12]
UA = "ridgelines-build/0.2 (github.com/nikokoren/ridgelines)"

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
    "Q213": ("Czechia", "Tschechien"),                # as in Downstream
    "Q974": ("DR\u00a0Congo", "DR\u00a0Kongo"),       # no-break space keeps "DR" with its noun
}


def countries(cs, summit=()):
    """Country names per language from "Qid<TAB>en<TAB>de|..." rows, short forms where listed.
    The summit's own countries come first, then the rest, each group in the language's
    alphabetical order: "Austria, Liechtenstein, Switzerland" for the Rätikon, whose summit
    lies in Austria and Switzerland. The template shows more than two as the first plus a count."""
    rows = sorted(tuple(r.split("\t")) for r in (cs or "").split("|") if r)
    de_key = lambda n: n.replace("Ä", "A").replace("Ö", "O").replace("Ü", "U")
    out = {}
    for i, key in ((0, lambda n: n), (1, de_key)):
        names = [(q in summit, SHORT_COUNTRY.get(q, (en, de))[i]) for q, en, de in rows]
        first = sorted((n for s_, n in names if s_), key=key)
        out["en" if i == 0 else "de"] = ", ".join(first + sorted((n for s_, n in names if not s_), key=key))
    return out


def sparql(q, name):
    """Live Wikidata query, cached in .cache/wikidata/<name>.json (delete to refresh)."""
    cache = os.path.join(CACHE, "wikidata", name + ".json")
    if not os.path.exists(cache):
        url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
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
    return json.load(open(cache))["results"]["bindings"]


def local_name(pqid, en, de):
    """The peak's local name, used only where Wikidata lacks the label in a language. 1. Wikidata's native label (P1705); with
    several (Mont Blanc: French and Italian), the one matching the English or German label.
    2. Otherwise the label in the official language (P37) of the peak's country; for a
    border summit with several, the one matching the German or English label.
    3. Otherwise the English label."""
    rows = sparql("""SELECT ?kind ?val ?lng WHERE {
      { wd:%s wdt:P1705 ?val . BIND("native" AS ?kind) BIND(LANG(?val) AS ?lng) }
      UNION { wd:%s wdt:P17 ?c . ?c wdt:P37 ?l . ?l wdt:P424 ?lng . BIND("official" AS ?kind)
              OPTIONAL { wd:%s rdfs:label ?val FILTER(LANG(?val) = ?lng) } }
    }""" % (pqid, pqid, pqid), pqid + ".names")
    get = lambda r, k: r[k]["value"] if k in r else None
    native = [get(r, "val") for r in rows if get(r, "kind") == "native" and get(r, "val")]
    if native:
        return next((n for n in native if n in (en, de)), native[0]), "native label"
    official = {get(r, "lng"): get(r, "val") for r in rows if get(r, "kind") == "official" and get(r, "val")}
    if len(official) == 1:
        lng, val = next(iter(official.items()))
        return val, f"official language ({lng})"
    # A border summit has several official languages: take the one whose name matches the
    # German or English label (Hochstuhl: German "Hochstuhl" over Slovene "Stol").
    for want in (de, en):
        for lng, val in official.items():
            if val == want:
                return val, f"official language ({lng}), border"
    return en or de, "English label"


class Skip(Exception):
    """A range that cannot be built (no English label, no highest point); select.py moves on."""


def wikidata(qid):
    rows = sparql("""SELECT ?p ?rl ?rde ?pl ?pde ?elev ?coord
      (GROUP_CONCAT(DISTINCT CONCAT(STRAFTER(STR(?c), "entity/"), "\t", ?cl, "\t", COALESCE(?cdl, ?cl)); separator="|") AS ?cs)
      (GROUP_CONCAT(DISTINCT STRAFTER(STR(?pc), "entity/"); separator="|") AS ?pcs)
      WHERE {
      BIND(wd:%s AS ?r)
      ?r rdfs:label ?rl FILTER(lang(?rl)="en")
      OPTIONAL { ?r rdfs:label ?rde FILTER(lang(?rde)="de") }
      ?r wdt:P610 ?p .
      OPTIONAL { ?p rdfs:label ?pl FILTER(lang(?pl)="en") }
      OPTIONAL { ?p rdfs:label ?pde FILTER(lang(?pde)="de") }
      ?p wdt:P2044 ?elev . ?p wdt:P625 ?coord .
      OPTIONAL { ?r wdt:P17 ?c . ?c rdfs:label ?cl FILTER(lang(?cl)="en")
                 OPTIONAL { ?c rdfs:label ?cdl FILTER(lang(?cdl)="de") } }
      OPTIONAL { ?p wdt:P17 ?pc }
    } GROUP BY ?p ?rl ?rde ?pl ?pde ?elev ?coord""" % qid, qid + ".v5")   # v5: peak label optional
    if not rows:
        raise Skip(f"{qid}: no Wikidata row with English range label, highest point, elevation and coordinates")
    v = lambda b, k: b[k]["value"] if k in b else None
    b = max(rows, key=lambda b: float(b["elev"]["value"]))  # some peaks carry two elevations
    lon, lat = map(float, v(b, "coord")[6:-1].split())
    pqid = v(b, "p").rsplit("/", 1)[-1]
    local, source = local_name(pqid, v(b, "pl"), v(b, "pde"))
    return dict(
        qid=qid, name={"en": v(b, "rl"), "de": v(b, "rde") or v(b, "rl")},
        # Each language shows its own Wikidata label (Niko, 2026-10-02, replacing local names the
        # same day); the local name only fills a missing label.
        peak={"en": v(b, "pl") or local, "de": v(b, "pde") or v(b, "pl") or local},
        peak_name_source=source, peak_labels={"en": v(b, "pl"), "de": v(b, "pde")},
        peak_m=round(float(v(b, "elev"))), peak_lat=lat, peak_lon=lon,
        country=countries(v(b, "cs"), (v(b, "pcs") or "").split("|")),
        elevations_listed=sorted({round(float(r["elev"]["value"])) for r in rows}),
    )


GLO90 = "https://copernicus-dem-90m.s3.amazonaws.com"


def tile_list(_names=set()):
    """Names of every GLO-90 tile, from the bucket's own tileList.txt (26,475 tiles, 2026-10-08).
    A tile not in the list is open ocean; a listed tile that fails to download is an error."""
    if not _names:
        path = os.path.join(TILES, "tileList.txt")
        if not os.path.exists(path):
            os.makedirs(TILES, exist_ok=True)
            urllib.request.urlretrieve(f"{GLO90}/tileList.txt", path)
        _names.update(open(path).read().split())
    return _names


# RIDGELINES_KEEP_TILES=0 deletes each tile once decoded (GitHub Actions: the full list touches
# more tiles than the runner's disk holds; the memory cache and geographic build order keep
# re-downloads rare).
KEEP_TILES = os.environ.get("RIDGELINES_KEEP_TILES", "1") != "0"
TILE_MEMORY = 40   # decoded tiles kept in memory (about 11 MB each); the full list touches thousands


def tile_name(lat_i, lon_i):
    ns, ew = ("N" if lat_i >= 0 else "S"), ("E" if lon_i >= 0 else "W")
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat_i):02d}_00_{ew}{abs(lon_i):03d}_00_DEM"


def fetch(name):
    """Download a listed tile into TILES unless it is there; returns its path (absent for ocean)."""
    path = os.path.join(TILES, name + ".tif")
    if name in tile_list() and not os.path.exists(path):
        os.makedirs(TILES, exist_ok=True)
        part = f"{path}.{os.getpid()}.{threading.get_ident()}.part"
        for attempt in range(6):
            try:
                urllib.request.urlretrieve(f"{GLO90}/{name}/{name}.tif", part)
                os.replace(part, path)
                break
            except (TimeoutError, urllib.error.URLError, ConnectionError, http.client.HTTPException):
                # S3 answers 403 now and then for tiles that exist; never take that as ocean.
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
    return path


def tiles_for(lat, lon, side_km):
    """Names of the tiles a square crop of side_km around (lat, lon) reads."""
    dlat = math.degrees(side_km / 2 / R) + 0.01
    dlon = math.degrees(side_km / 2 / (R * math.cos(math.radians(min(89, abs(lat) + dlat))))) + 0.01
    return [tile_name(a, (o + 180) % 360 - 180)
            for a in range(math.floor(lat - dlat), math.floor(lat + dlat) + 1)
            for o in range(math.floor(lon - dlon), math.floor(lon + dlon) + 1)]


def tile(lat_i, lon_i, _mem=collections.OrderedDict()):
    """1 degree GLO-90 tile whose south-west corner is (lat_i, lon_i). None where the
    dataset has no tile (tile_list), which is open ocean."""
    if (lat_i, lon_i) in _mem:
        _mem.move_to_end((lat_i, lon_i))
        return _mem[(lat_i, lon_i)]
    name = tile_name(lat_i, lon_i)
    path = fetch(name)
    if not os.path.exists(path):
        arr = None
    else:
        with tifffile.TiffFile(path) as t:
            p = t.pages[0]
            lon0, lat0 = p.tags["ModelTiepointTag"].value[3:5]
            assert (round(lon0), round(lat0)) == (lon_i, lat_i + 1), (name, lon0, lat0)
            arr = p.asarray().astype(np.float64)
        if not KEEP_TILES:
            os.remove(path)
    _mem[(lat_i, lon_i)] = arr
    while len(_mem) > TILE_MEMORY:
        _mem.popitem(last=False)
    return arr


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


def range_facts(qid):
    """Names and countries of a range without a highest point (terrain fallback)."""
    rows = sparql("""SELECT ?rl ?rde
      (GROUP_CONCAT(DISTINCT CONCAT(STRAFTER(STR(?c), "entity/"), "\t", ?cl, "\t", COALESCE(?cdl, ?cl)); separator="|") AS ?cs)
      WHERE {
      BIND(wd:%s AS ?r)
      ?r rdfs:label ?rl FILTER(lang(?rl)="en")
      OPTIONAL { ?r rdfs:label ?rde FILTER(lang(?rde)="de") }
      OPTIONAL { ?r wdt:P17 ?c . ?c rdfs:label ?cl FILTER(lang(?cl)="en")
                 OPTIONAL { ?c rdfs:label ?cdl FILTER(lang(?cdl)="de") } }
    } GROUP BY ?rl ?rde""" % qid, qid + ".range")
    if not rows:
        raise Skip(f"{qid}: no English label")
    v = lambda k: rows[0][k]["value"] if k in rows[0] else None
    return dict(qid=qid, name={"en": v("rl"), "de": v("rde") or v("rl")}, cs=v("cs"))


PEAK_CLASSES = "wd:Q8502 wd:Q54050 wd:Q207326 wd:Q8072"   # mountain, hill, summit, volcano
NAME_KM = 3            # a Wikidata peak this close to the terrain summit names it, if its listed
NAME_TOLERANCE = 0.1   # elevation is within 10 % (at least 100 m) of the terrain height,
NAME_KM_UNLISTED = 1.5 # or, if it lists no elevation, if it is this close
# Labels that only state a height are not names ("Höhe 781" in the Adrar Plateau, 2026-10-08).
PLACEHOLDER = re.compile(r"^(höhe|hill|point|peak|cote|kote|pt\.?|elevation)\s*\d", re.I)


def nearest_peak(lat, lon, height):
    """The Wikidata peak that names a terrain summit: the nearest one within NAME_KM whose listed
    elevation matches the terrain, or within NAME_KM_UNLISTED if it lists none (many African
    peaks carry no elevation). None if there is none."""
    rows = sparql("""SELECT ?p ?pl ?pde ?elev ?coord
      (GROUP_CONCAT(DISTINCT STRAFTER(STR(?pc), "entity/"); separator="|") AS ?pcs) WHERE {
      SERVICE wikibase:around { ?p wdt:P625 ?coord .
        bd:serviceParam wikibase:center "Point(%.5f %.5f)"^^geo:wktLiteral ; wikibase:radius "%g" . }
      VALUES ?cls { %s }
      ?p wdt:P31/wdt:P279* ?cls .
      FILTER NOT EXISTS { ?p wdt:P31/wdt:P279* wd:Q46831 }     # a range is not its own summit (Aheggar)
      OPTIONAL { ?p p:P2044/psn:P2044/wikibase:quantityAmount ?elev . }
      OPTIONAL { ?p rdfs:label ?pl FILTER(lang(?pl)="en") }
      OPTIONAL { ?p rdfs:label ?pde FILTER(lang(?pde)="de") }
      OPTIONAL { ?p wdt:P17 ?pc }
    } GROUP BY ?p ?pl ?pde ?elev ?coord""" % (lon, lat, NAME_KM, PEAK_CLASSES), "around3_%.4f_%.4f" % (lat, lon))
    best = None
    for b in rows:
        if not b["coord"]["value"].startswith("Point("):
            continue
        plon, plat = map(float, b["coord"]["value"][6:-1].split())
        elev = float(b["elev"]["value"]) if "elev" in b else None
        dist = R * math.hypot(math.radians(plat - lat), math.radians(plon - lon) * math.cos(math.radians(lat)))
        if elev is None and dist > NAME_KM_UNLISTED:
            continue
        if elev is not None and abs(elev - height) > max(100, NAME_TOLERANCE * height):
            continue
        pqid = b["p"]["value"].rsplit("/", 1)[-1]
        en = b["pl"]["value"] if "pl" in b else None
        de = b["pde"]["value"] if "pde" in b else None
        if not (en or de):
            local, _ = local_name(pqid, None, None)
            en = de = local
        en, de = (None if PLACEHOLDER.match(x or "") else x for x in (en, de))
        if not (en or de):
            continue
        if best is None or dist < best["km"]:
            best = dict(qid=pqid, en=en or de, de=de or en, m=round(elev if elev is not None else height),
                        elevation_listed=elev is not None, km=round(dist, 2),
                        countries=(b["pcs"]["value"] if "pcs" in b else "").split("|"))
    return best


def build(key, suffix=""):
    f = FIXTURES[key]
    kind = f.get("kind", "listed")
    if kind == "listed":
        wd = wikidata(f["qid"])
    else:
        wd = range_facts(f["qid"])
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
    z[bad] = med[bad]
    z_fine = z.copy()                                      # 3x grid, spikes removed, unsmoothed
    z = ndimage.gaussian_filter(z, 1.2)
    z = z.reshape(GRID, 3, GRID, 3).mean(axis=(1, 3))
    z_abs = z.copy()                                       # true heights, for locating the summit
    if RELIEF:
        # Local relief: take away part of the broad shape so ridges,
        # not the massif's dome, carry the ripples. sigma in km, share 0..1.
        sigma_km, share = RELIEF
        z = z - share * ndimage.gaussian_filter(z, sigma_km / (side / GRID), mode="nearest")
    lo, hi = float(z.min()), float(z.max())
    if hi - lo < 1:
        raise Skip(f"{f['qid']}: no terrain in the crop (all {lo:.0f} m)")
    q = np.round((z - lo) / (hi - lo) * 255).astype(np.uint8)
    floor_m = float(np.percentile(z, FLOOR_PCT))
    # Ripple top: the highest sample in the reference window (what the OG full
    # landscape view shows), so higher neighbours at the edge of the stored
    # square do not flatten the range itself. Views use this one scale.
    c = (np.abs(xs) <= f["width_km"] / 2)[None, :] & (np.abs(ys) <= f["width_km"] * REF_ASPECT / 2)[:, None]
    c = c.reshape(GRID, 3, GRID, 3).any(axis=(1, 3))
    top_m = float(z[c].max())
    ocean = float((z_abs <= 0.5).mean())
    ref = z_abs[c]
    relief_ref = float(ref.max() - np.percentile(ref, 5))  # height span the reference window shows
    gx = xs.reshape(GRID, 3).mean(axis=1)
    gy = ys.reshape(GRID, 3).mean(axis=1)

    def km(plat, plon):
        pe = math.radians(plon - f["lon"] + 540) % (2 * math.pi) - math.pi
        return R * pe * math.cos(math.radians(plat)), R * math.radians(plat - f["lat"])

    if kind == "listed":
        # High point position in km from the crop centre (east, north), snapped to
        # the highest terrain within SNAP_KM of the listed point, so the label sits
        # on the summit even when Wikidata's coordinates are rounded. If the listed
        # point is not on high ground, the sign-flipped longitude and latitude are
        # tried too, and the candidate whose summit best matches the listed height
        # wins: Taveuni's Uluigalau is listed at 179.967 E, in the sea; it is at W.
        def summit(plat, plon):
            px, py = km(plat, plon)
            near = (gx[None, :] - px) ** 2 + (gy[:, None] - py) ** 2 <= SNAP_KM ** 2
            if not near.any():
                return None
            r, c_ = np.unravel_index(np.where(near, z_abs, -np.inf).argmax(), z_abs.shape)
            return float(z_abs[r, c_]), (float(gx[c_]), float(gy[r])), math.hypot(gx[c_] - px, gy[r] - py)

        plat, plon = wd["peak_lat"], wd["peak_lon"]
        at_peak = float(sample(np.array([plat]), np.array([plon]))[0])
        peak_ok = at_peak >= 0.75 * wd["peak_m"]
        cands = [("listed", plat, plon)]
        if not peak_ok:
            cands += [("longitude sign flipped", plat, -plon), ("latitude sign flipped", -plat, plon)]
        found = [(n_, summit(a_, o_)) for n_, a_, o_ in cands]
        found = [(n_, s_) for n_, s_ in found if s_ and s_[0] > 0]
        if found:
            source, (peak_found_m, peak_xy, snap) = min(found, key=lambda t: abs(t[1][0] - wd["peak_m"]))
        else:
            source, peak_found_m, peak_xy, snap = "listed, no terrain nearby", at_peak, km(plat, plon), 0.0
        peak, peak_m, country = wd["peak"], wd["peak_m"], wd["country"]
        checks = dict(peak_name_source=wd["peak_name_source"], peak_labels=wd["peak_labels"],
                      peak_point_m=round(at_peak), peak_point_ok=peak_ok)
        elevations = wd["elevations_listed"]
    else:
        # Terrain fallback (Niko, 2026-10-08): the range has no highest point in Wikidata, so
        # the summit is the highest terrain in the reference window (inset by a tenth, so the
        # summit is not cut at the frame), named after the nearest Wikidata peak whose listed
        # elevation matches. Without one the box says "Highest point" and the label is left out.
        inset = (np.abs(gx) <= 0.45 * f["width_km"])[None, :] & (np.abs(gy) <= 0.45 * f["width_km"] * REF_ASPECT)[:, None]
        r, c_ = np.unravel_index(np.where(inset, z_abs, -np.inf).argmax(), z_abs.shape)
        peak_xy, snap, source = (float(gx[c_]), float(gy[r])), 0.0, "terrain"
        peak_found_m = float(z_abs[r, c_])
        fine_r, fine_c = slice(3 * r, 3 * r + 3), slice(3 * c_, 3 * c_ + 3)
        terrain_m = float(z_fine[max(0, 3 * r - 6):3 * r + 9, max(0, 3 * c_ - 6):3 * c_ + 9].max())
        slat = f["lat"] + math.degrees(peak_xy[1] / R)
        slon = f["lon"] + math.degrees(peak_xy[0] / (R * math.cos(math.radians(slat))))
        named = nearest_peak(slat, slon, terrain_m)
        if named:
            peak, peak_m = {"en": named["en"], "de": named["de"]}, named["m"]
            source = f"terrain, named after {named['qid']} {named['km']} km away"
        else:
            peak, peak_m = {"en": "", "de": ""}, int(round(terrain_m))
        country = countries(wd["cs"], named["countries"] if named else ())
        checks = dict(peak_name_source="nearest Wikidata peak" if named else "none", peak_labels=peak,
                      terrain_summit_m=round(terrain_m), named_peak=named)
        elevations = []
        del fine_r, fine_c
    above_peak = int((z_fine > peak_m + 20).sum())
    entry = dict(
        id=key, role=f["role"], wikidata=wd["qid"], kind=kind, build=BUILD,
        name=wd["name"], peak=peak, peak_m=peak_m, country=country,
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
        _checks=dict(checks, peak_source=source,
                     peak_snap_km=round(snap, 2), peak_found_m=round(peak_found_m), spike_pixels=spikes, above_peak_pixels=above_peak, raw_max_m=round(zmax_raw, 1), ocean_share=round(ocean, 3),
                     relief_m=round(relief_ref), window_max_m=round(float(ref.max())), ocean_ref_share=round(float((ref <= 0.5).mean()), 3),
                     peak_in_square=bool(abs(peak_xy[0]) < side / 2 and abs(peak_xy[1]) < side / 2),
                     wikidata_elevations=elevations),
    )
    os.makedirs(ENTRIES, exist_ok=True)
    path = os.path.join(ENTRIES, key + suffix + ".json")
    with open(path, "w") as fh:
        json.dump(entry, fh, ensure_ascii=False, separators=(",", ":"))
    c = entry["_checks"]
    if not QUIET:
        print(f"{key + suffix:11s} {os.path.getsize(path)/1000:5.1f} kB  {wd['name']['en']}: {peak['en']} {peak_m} m"
              f"  crop {lo:.0f} to {hi:.0f} m, raw max {c['raw_max_m']:.0f} m, spikes {spikes}, above high point {above_peak}, ocean {ocean:.0%},"
              f" peak in square {c['peak_in_square']}, relief {c['relief_m']} m, Wikidata elevations {elevations},"
              f" summit {c['peak_found_m']} m {c['peak_snap_km']} km away ({source})")
    return entry


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--list", help="build the entries of a list file instead, e.g. data/beta_de_at.json")
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
