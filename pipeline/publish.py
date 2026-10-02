"""Build the GitHub Pages site and the Polling URL from a curated list.

    python pipeline/publish.py                         # data/beta_de_at.json into site/
    python pipeline/publish.py --skip-build            # reuse .cache/entries (after entries.py ran)

Writes, all git-ignored except the Polling URL:
    site/beta/d/<n>.json   one payload per calendar slot, n = 0 .. count-1, in a fixed shuffled order
    site/beta/calendar.json, site/NOTICE.md, site/index.html
    recipe/polling_url.txt the Polling URL that picks today's slot (committed; a test checks it)

Rotation without a server, as in Downstream (its D18): the Polling URL computes the day number
from TRMNL's clock plus the user's UTC offset (seconds), takes it modulo the slot count and
fetches that file. Every device sees the same range on the same local day. The beta has one
folder; the Area setting will add folders beside it.
"""
import argparse, json, os, random, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import entries  # noqa: E402
import words  # noqa: E402

SITE_URL = "https://nikokoren.github.io/ridgelines"   # public GitHub Pages address of this public repo
SEED = 20261002
BUDGET = 80_000                                        # bytes per payload (CLAUDE.md: 100 KB cap, budget 80 KB)
FOLDER = "beta"


def payload(e):
    """What TRMNL polls for one range: the drawing data plus every word, keyed by language and units."""
    return {
        "v": 1,
        "id": e["id"],
        "heights": e["heights"], "grid": e["grid"],
        "side_km": e["crop"]["side_km"], "width_km": e["crop"]["width_km"],
        "floor": e["floor"], "top": e["top"],
        "peak_x": e["peak_km"][0], "peak_y": e["peak_km"][1],
        "peak": e["peak"]["en"],                       # local name, the same in every language
        "box_title": {l: words.headline(e, l) for l in words.LANGS},
        "box_peak": {l: {u: words.peak_line(e, l, u) for u in words.UNITS} for l in words.LANGS},
        "caption": {l: {u: words.captions(e, l, u) for u in words.UNITS} for l in words.LANGS},
    }


def polling_url(count):
    return ('{%- assign rl_off = trmnl.user.utc_offset | default: 0 | plus: 0 -%}'
            '{%- assign rl_day = "now" | date: "%s" | plus: rl_off | divided_by: 86400 -%}'
            '{%- assign rl_n = rl_day | modulo: ' + str(count) + ' -%}'
            + SITE_URL + "/" + FOLDER + "/d/{{ rl_n }}.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default=os.path.join(ROOT, "data", "beta_de_at.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "site"))
    ap.add_argument("--skip-build", action="store_true", help="reuse entries already in .cache/entries")
    a = ap.parse_args()

    listed = json.load(open(a.list))["entries"]
    ids = [x["id"] for x in listed]
    for x in listed:
        entries.FIXTURES[x["id"]] = dict(qid=x["wikidata"], role="beta, Germany and Austria",
                                         lat=x["lat"], lon=x["lon"], width_km=x["width_km"])
    built = {}
    for k in ids:
        path = os.path.join(entries.ENTRIES, k + ".json")
        built[k] = json.load(open(path)) if a.skip_build and os.path.exists(path) else entries.build(k)

    order = ids[:]
    random.Random(SEED).shuffle(order)
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    os.makedirs(os.path.join(a.out, FOLDER, "d"))
    sizes = []
    for n, k in enumerate(order):
        body = json.dumps(payload(built[k]), ensure_ascii=False, separators=(",", ":")).encode()
        if len(body) > BUDGET:
            raise SystemExit(f"{k}: payload {len(body)} bytes over the {BUDGET} byte budget")
        open(os.path.join(a.out, FOLDER, "d", f"{n}.json"), "wb").write(body)
        sizes.append(len(body))
    json.dump([{"slot": n, "id": k, "name": built[k]["name"]} for n, k in enumerate(order)],
              open(os.path.join(a.out, FOLDER, "calendar.json"), "w"), ensure_ascii=False, indent=1)

    att = built[order[0]]["attribution"]
    open(os.path.join(a.out, "NOTICE.md"), "w").write(
        "# Ridgelines data notice\n\n"
        f"Terrain {att['notice']}.\n\n{att['liability']['en']}\n\n{att['liability']['de']}\n\n"
        "Range names, highest points, heights and countries: Wikidata (CC0).\n")
    open(os.path.join(a.out, "index.html"), "w").write(
        "<!doctype html><meta charset=utf-8><title>Ridgelines</title>"
        "<p>Data files for the Ridgelines TRMNL recipe. See NOTICE.md.</p>\n")
    open(os.path.join(a.out, ".nojekyll"), "w").close()

    url = polling_url(len(order))
    open(os.path.join(ROOT, "recipe", "polling_url.txt"), "w").write(url + "\n")
    settings = open(os.path.join(ROOT, "recipe", "settings.yml")).read()
    if f"polling_url: '{url}'" not in settings:
        raise SystemExit("recipe/settings.yml polling_url differs from recipe/polling_url.txt; copy it over")
    print(f"{len(order)} payloads, {min(sizes)/1000:.1f} to {max(sizes)/1000:.1f} kB, into {a.out}/{FOLDER}/d/")


if __name__ == "__main__":
    main()
