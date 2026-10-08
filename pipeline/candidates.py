"""Candidate mountain ranges per area, from live Wikidata queries.

    python pipeline/candidates.py            # counts per area; writes .cache/candidates.json

Two kinds of candidate (PROJECT.md, Decisions 2026-10-08):

- "listed": the range has a highest point (P610) with elevation (P2044) and coordinates (P625).
  Nested groupings repeat summits (Alps, Western Alps, Graian Alps and the Mont Blanc massif all
  name Mont Blanc), so each summit keeps one range: the one no other range of the group is part of
  (P361 or P4552), then the shortest or smallest, then the best known (most sitelinks).
- "terrain": the range has coordinates but no highest point, which covers most of Africa. The
  build finds the summit in the terrain and names it after the nearest Wikidata peak (entries.py).

Area comes from the continent (P30) of the summit's country, or of the range's country for the
terrain kind. Countries on two continents, summits without a country and ranges spanning several
continents are placed by coordinates (area_at). Antarctica has no area. 2026-10-08: the
Africa box first swallowed Turkey's Aegean coast (Besparmak Mountains).

Crop: centred on the range's own coordinates when they lie near the summit, else on the summit.
Width from the range's length (P2043) or area (P2046), else WIDTH_KM. Candidates are ranked by
sitelinks; select.py builds them in that order and keeps those that pass the checks.
"""
import collections, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from entries import CACHE, sparql  # noqa: E402

AREAS = ("europe", "americas", "asia", "africa")    # folder names and Area setting values
NAMES = {"europe": "Europe", "americas": "Americas", "asia": "Asia and Oceania", "africa": "Africa"}
CONTINENT = {
    "Q46": "europe",
    "Q49": "americas", "Q18": "americas", "Q828": "americas",          # North, South America, Americas
    "Q48": "asia", "Q55643": "asia", "Q538": "asia", "Q3960": "asia",   # Asia, Oceania, insular Oceania, Australia
    "Q15": "africa",
}
WIDTH_KM = 45                  # crop width when Wikidata gives neither length nor area
WIDTH_RANGE = (35, 80)         # beta used 40 (Alps) to 50 (low ranges); 80 keeps ridges legible
CENTRE_SHARE = 0.3             # range coordinates within this share of the width of the summit centre the crop


def area_at(lat, lon):
    """Coarse area by position, for summits whose country spans continents (Russia, Turkey,
    Kazakhstan, Georgia, Egypt, USA with Hawaii) or has none. Greater Caucasus and the Urals'
    west side count as Europe, Anatolia, Sinai and Arabia as Asia, Hawaii as Oceania."""
    if lat < -60:
        return None                                              # Antarctica
    if lon < -25 and lon > -168:
        return "asia" if (lat < 30 and lon < -150) else "americas"
    # Africa's north coast reaches 37.3 N in Tunisia but only 31.6 N in Egypt; Anatolia's
    # Aegean coast (Besparmak Mountains, 37.5 N 27.5 E) lies south of 37.5 N.
    if -20 <= lon <= 52 and lat < 37.5 and not (lon > 32.3 and lat > 12) and not (lon > 25.5 and lat > 31.7):
        return "africa"
    if lon <= 60 and lat >= 42.0 and lon > -25:
        return "europe"
    if lon <= 26.5 and lat >= 34.5 and lon > -25:                 # Greece, the Balkans, Iberia, Italy
        return "europe"
    if lon <= 29.2 and lat >= 40.6 and lon > -25:                 # Turkish Thrace (Strandzha)
        return "europe"
    return "asia"


def area_of(conts, lat, lon):
    areas = {CONTINENT[c] for c in conts if c in CONTINENT}
    return areas.pop() if len(areas) == 1 else area_at(lat, lon)


def point(wkt):
    """(lat, lon) from "Point(lon lat)"; None for an unknown value or a point on another globe."""
    if not wkt.startswith("Point("):
        return None
    lon, lat = map(float, wkt[6:-1].split())
    return lat, lon


def km_between(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1, h)))


def width_for(length_m, area_m2):
    lo, hi = WIDTH_RANGE
    if length_m:
        w = 0.8 * length_m / 1000
    elif area_m2:
        w = math.sqrt(area_m2) / 1000
    else:
        w = WIDTH_KM
    return int(round(min(hi, max(lo, w))))


Q_LISTED = """SELECT ?r ?p ?elev ?coord ?sl ?len ?area ?rcoord
 (GROUP_CONCAT(DISTINCT STRAFTER(STR(?ct), "entity/"); separator="|") AS ?conts)
 WHERE {
  ?r wdt:P31/wdt:P279* wd:Q46831 ; wdt:P610 ?p .
  ?p p:P2044 ?est ; wdt:P625 ?coord . ?est a wikibase:BestRank ; psn:P2044/wikibase:quantityAmount ?elev .
  ?r wikibase:sitelinks ?sl .
  OPTIONAL { ?r p:P2043/psn:P2043/wikibase:quantityAmount ?len }
  OPTIONAL { ?r p:P2046/psn:P2046/wikibase:quantityAmount ?area }
  OPTIONAL { ?r wdt:P625 ?rcoord }
  OPTIONAL { ?p wdt:P17 ?pc . OPTIONAL { ?pc wdt:P30 ?ct } }
 } GROUP BY ?r ?p ?elev ?coord ?sl ?len ?area ?rcoord"""

Q_PARENTS = """SELECT ?r ?parent WHERE {
  ?r wdt:P31/wdt:P279* wd:Q46831 ; wdt:P610 ?p .
  ?r wdt:P361|wdt:P4552 ?parent .
}"""

Q_TERRAIN = """SELECT ?r ?coord ?sl ?len ?area
 (GROUP_CONCAT(DISTINCT STRAFTER(STR(?ct), "entity/"); separator="|") AS ?conts)
 WHERE {
  ?r wdt:P31/wdt:P279* wd:Q46831 ; wdt:P625 ?coord .
  FILTER NOT EXISTS { ?r wdt:P610 ?p }
  ?r wikibase:sitelinks ?sl .
  OPTIONAL { ?r p:P2043/psn:P2043/wikibase:quantityAmount ?len }
  OPTIONAL { ?r p:P2046/psn:P2046/wikibase:quantityAmount ?area }
  OPTIONAL { ?r wdt:P17 ?c . OPTIONAL { ?c wdt:P30 ?ct } }
 } GROUP BY ?r ?coord ?sl ?len ?area"""


def qid(b, k):
    return b[k]["value"].rsplit("/", 1)[-1] if k in b else None


def num(b, k):
    return float(b[k]["value"]) if k in b else None


def listed():
    rows = sparql(Q_LISTED, "candidates.listed2")   # 2: preferred elevation statements only
    parents = collections.defaultdict(set)
    for b in sparql(Q_PARENTS, "candidates.parents"):
        parents[qid(b, "r")].add(qid(b, "parent"))
    ranges = {}
    for b in rows:
        r = qid(b, "r")
        x = ranges.get(r)
        # A range with two highest points or two elevations: keep the highest reading.
        if x and x["peak"]["m"] >= num(b, "elev"):
            continue
        if point(b["coord"]["value"]) is None:
            continue
        plat, plon = point(b["coord"]["value"])
        ranges[r] = dict(
            wikidata=r, kind="listed", sitelinks=int(b["sl"]["value"]),
            length_m=num(b, "len"), area_m2=num(b, "area"),
            range_point=point(b["rcoord"]["value"]) if "rcoord" in b else None,  # None if unknown
            peak=dict(wikidata=qid(b, "p"), m=num(b, "elev"), lat=plat, lon=plon),
            area=area_of(b.get("conts", {}).get("value", "").split("|"), plat, plon),
        )
    by_summit = collections.defaultdict(list)
    for r in ranges.values():
        by_summit[r["peak"]["wikidata"]].append(r)
    out = []
    for group in by_summit.values():
        ids = {r["wikidata"] for r in group}
        leaves = [r for r in group if not any(r["wikidata"] in parents[o] for o in ids - {r["wikidata"]})] or group
        size = lambda r: r["length_m"] or (math.sqrt(r["area_m2"]) if r["area_m2"] else math.inf)
        pick = min(leaves, key=lambda r: (size(r), -r["sitelinks"], r["wikidata"]))
        pick["same_summit"] = sorted(ids - {pick["wikidata"]})
        out.append(pick)
    return out


def terrain():
    """One row per range: a range with two coordinates, lengths or areas comes back several
    times; the first by coordinate text is kept, so the choice is stable."""
    out, seen = [], set()
    rows = sparql(Q_TERRAIN, "candidates.terrain")
    for b in sorted(rows, key=lambda b: (b["r"]["value"], b["coord"]["value"], b.get("len", {}).get("value", ""))):
        if b["r"]["value"] in seen:
            continue
        seen.add(b["r"]["value"])
        if point(b["coord"]["value"]) is None:
            continue
        lat, lon = point(b["coord"]["value"])
        out.append(dict(
            wikidata=qid(b, "r"), kind="terrain", sitelinks=int(b["sl"]["value"]),
            length_m=num(b, "len"), area_m2=num(b, "area"), range_point=(lat, lon), peak=None,
            area=area_of(b.get("conts", {}).get("value", "").split("|"), lat, lon),
        ))
    return out


def crop(c):
    """Crop centre and width for a candidate."""
    w = width_for(c["length_m"], c["area_m2"])
    if c["peak"] is None:
        lat, lon = c["range_point"]
    else:
        summit = (c["peak"]["lat"], c["peak"]["lon"])
        near = c["range_point"] and km_between(c["range_point"], summit) <= CENTRE_SHARE * w
        lat, lon = c["range_point"] if near else summit
    return round(lat, 4), round(lon, 4), w


def all_candidates():
    """Every candidate with an area, listed kind first, each kind ranked by sitelinks."""
    cands = sorted(listed(), key=lambda c: (-c["sitelinks"], c["wikidata"])) \
        + sorted(terrain(), key=lambda c: (-c["sitelinks"], c["wikidata"]))
    out = []
    for c in cands:
        if c["area"] is None:
            continue
        lat, lon, w = crop(c)
        out.append(dict(c, lat=lat, lon=lon, width_km=w))
    return out


if __name__ == "__main__":
    cands = all_candidates()
    json.dump(cands, open(os.path.join(CACHE, "candidates.json"), "w"), ensure_ascii=False)
    n = collections.Counter((c["area"], c["kind"]) for c in cands)
    for a in AREAS:
        print(f"{NAMES[a]:17s} listed {n[(a, 'listed')]:5d}   terrain {n[(a, 'terrain')]:6d}")
