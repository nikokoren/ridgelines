"""Build the GitHub Pages site and the Polling URL from the curated lists.

    python pipeline/publish.py                         # every list into site/
    python pipeline/publish.py --skip-build            # reuse .cache/entries where they match the list

Lists: data/beta_de_at.json (the beta, folder beta/) and data/release/<area>.json (written by
pick.py, one folder per area: europe/, americas/, asia/, africa/). Writes, all git-ignored except
the Polling URL:
    site/<folder>/d/<n>.json   one payload per calendar slot, n = 0 .. count-1, in a fixed shuffled order
    site/<folder>/calendar.json, site/NOTICE.md, site/index.html
    recipe/polling_url.txt     the Polling URL (committed; the build fails if settings.yml differs)

Rotation without a server, as in Downstream (its D18): the Polling URL computes the day number
from TRMNL's clock plus the user's UTC offset (seconds). With release lists it reads the Area
setting (multi select; none ticked means every area) and takes turns through the ticked areas in
a fixed order, one per day: area = ticked[day mod k], slot = (day div k) mod count(area). Every
device with the same ticks sees the same range on the same local day, and a single area runs a
year without repeats at 365 ranges. The beta folder stays published for installs that still use
the beta URL (polling_url(None)).
"""
import argparse, json, os, random, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import candidates  # noqa: E402
import entries  # noqa: E402
import words  # noqa: E402

SITE_URL = "https://nikokoren.github.io/ridgelines"   # public GitHub Pages address of this public repo
SEED = 20261002
BUDGET = 80_000                                        # bytes per payload (CLAUDE.md: 100 KB cap, budget 80 KB)
BETA = os.path.join(ROOT, "data", "beta_de_at.json")
RELEASE = os.path.join(ROOT, "data", "release")


def payload(e):
    """What TRMNL polls for one range: the drawing data plus every word, keyed by language and units."""
    return {
        "v": 1,
        "id": e["id"],
        "heights": e["heights"], "grid": e["grid"],
        "side_km": e["crop"]["side_km"], "width_km": e["crop"]["width_km"],
        "floor": e["floor"], "top": e["top"],
        "peak_x": e["peak_km"][0], "peak_y": e["peak_km"][1],
        "peak": {l: words.peak_name(e, l) for l in words.LANGS},
        "box_title": {l: words.headline(e, l) for l in words.LANGS},
        "box_peak": {l: {u: words.peak_line(e, l, u) for u in words.UNITS} for l in words.LANGS},
        "caption": {l: {u: words.captions(e, l, u) for u in words.UNITS} for l in words.LANGS},
    }


def polling_url(counts=None, beta_count=30):
    """The Polling URL. counts: {area: number of ranges} for the release folders; None for the beta."""
    day = ('{%- assign rl_off = trmnl.user.utc_offset | default: 0 | plus: 0 -%}'
           '{%- assign rl_day = "now" | date: "%s" | plus: rl_off | divided_by: 86400 -%}')
    if not counts:
        return (day + '{%- assign rl_n = rl_day | modulo: ' + str(beta_count) + ' -%}'
                + SITE_URL + "/beta/d/{{ rl_n }}.json")
    areas = [a for a in candidates.AREAS if counts.get(a)]
    pick = '{%- assign rl_t = area | join: "," -%}{%- assign rl_s = "" -%}' + "".join(
        '{%- if rl_t contains "' + a + '" -%}{%- assign rl_s = rl_s | append: "' + a + ',' + '" -%}{%- endif -%}'
        for a in areas)
    pick += '{%- if rl_s == "" -%}{%- assign rl_s = "' + "".join(a + "," for a in areas) + '" -%}{%- endif -%}'
    pick += ('{%- assign rl_l = rl_s | split: "," -%}{%- assign rl_k = rl_l.size -%}'
             '{%- assign rl_j = rl_day | modulo: rl_k -%}{%- assign rl_a = rl_l[rl_j] -%}'
             '{%- case rl_a -%}' + "".join('{%- when "' + a + '" -%}{%- assign rl_c = ' + str(counts[a]) + ' -%}' for a in areas)
             + '{%- endcase -%}{%- assign rl_i = rl_day | divided_by: rl_k | modulo: rl_c -%}')
    return day + pick + SITE_URL + "/{{ rl_a }}/d/{{ rl_i }}.json"


def entry_for(x, role, skip_build):
    """The built entry for a list item, rebuilt unless a cached one matches crop, kind and build."""
    spec = dict(qid=x["wikidata"], role=role, lat=x["lat"], lon=x["lon"], width_km=x["width_km"],
                kind=x.get("kind", "listed"))
    entries.FIXTURES[x["id"]] = spec
    path = os.path.join(entries.ENTRIES, x["id"] + ".json")
    if skip_build and os.path.exists(path):
        e = json.load(open(path))
        if (e.get("build") == entries.BUILD and e.get("kind", "listed") == spec["kind"] and e["wikidata"] == spec["qid"]
                and (e["crop"]["lat"], e["crop"]["lon"], e["crop"]["width_km"]) == (x["lat"], x["lon"], x["width_km"])):
            return e
    return entries.build(x["id"])


def write_folder(out, folder, listed, role, skip_build):
    """One folder of calendar slots. Returns (slot count, payload sizes)."""
    built = {}
    # Neighbours share elevation tiles, so build in geographic order.
    for x in sorted(listed, key=lambda x: (round(x["lat"]), x["lon"])):
        built[x["id"]] = entry_for(x, role, skip_build)
    order = [x["id"] for x in listed]
    random.Random(SEED).shuffle(order)
    os.makedirs(os.path.join(out, folder, "d"))
    sizes = []
    for n, k in enumerate(order):
        body = json.dumps(payload(built[k]), ensure_ascii=False, separators=(",", ":")).encode()
        if len(body) > BUDGET:
            raise SystemExit(f"{k}: payload {len(body)} bytes over the {BUDGET} byte budget")
        open(os.path.join(out, folder, "d", f"{n}.json"), "wb").write(body)
        sizes.append(len(body))
    json.dump([{"slot": n, "id": k, "name": built[k]["name"]} for n, k in enumerate(order)],
              open(os.path.join(out, folder, "calendar.json"), "w"), ensure_ascii=False, indent=1)
    return len(order), sizes, built[order[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "site"))
    ap.add_argument("--skip-build", action="store_true", help="reuse entries in .cache/entries that match the list and the build")
    a = ap.parse_args()

    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    beta = json.load(open(BETA))["entries"]
    beta_n, sizes, first = write_folder(a.out, "beta", beta, "beta, Germany and Austria", a.skip_build)
    print(f"beta: {beta_n} payloads, {min(sizes)/1000:.1f} to {max(sizes)/1000:.1f} kB")
    counts = {}
    for area in candidates.AREAS:
        path = os.path.join(RELEASE, area + ".json")
        if not os.path.exists(path):
            continue
        listed = json.load(open(path))["entries"]
        counts[area], sizes, _ = write_folder(a.out, area, listed, f"release, {candidates.NAMES[area]}", a.skip_build)
        print(f"{area}: {counts[area]} payloads, {min(sizes)/1000:.1f} to {max(sizes)/1000:.1f} kB")

    att = first["attribution"]
    open(os.path.join(a.out, "NOTICE.md"), "w").write(
        "# Ridgelines data notice\n\n"
        f"Terrain {att['notice']}.\n\n{att['liability']['en']}\n\n{att['liability']['de']}\n\n"
        "Range names, highest points, heights and countries: Wikidata (CC0).\n")
    open(os.path.join(a.out, "index.html"), "w").write(
        "<!doctype html><meta charset=utf-8><title>Ridgelines</title>"
        "<p>Data files for the Ridgelines TRMNL recipe. See NOTICE.md.</p>\n")
    open(os.path.join(a.out, ".nojekyll"), "w").close()

    url = polling_url(counts or None, beta_n)
    open(os.path.join(ROOT, "recipe", "polling_url.txt"), "w").write(url + "\n")
    settings = open(os.path.join(ROOT, "recipe", "settings.yml")).read()
    if f"polling_url: '{url}'" not in settings:
        raise SystemExit("recipe/settings.yml polling_url differs from recipe/polling_url.txt; copy it over")
    print(f"Polling URL for {', '.join(counts) or 'the beta'} written to recipe/polling_url.txt")


if __name__ == "__main__":
    main()
