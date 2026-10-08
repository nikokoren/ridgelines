"""Contact sheets for look tuning, rendered through the real framework.

    python sweep.py corpus  [out]   every entry, OG 1-bit full view, current look
    python sweep.py tune    [out]   every entry at a grid of ripple x floor settings
    python sweep.py views   [out]   every entry x 5 views x 3 bit depths and TRMNL X, with a report
    python sweep.py lang    [out]   German captions at quadrant size
    python sweep.py resolution [out]  Karwendel: JAXA mockup vs GLO-90 at 200/280/400 grids
                                      (first: fixtures.py karwendel --grid 280 --suffix _g280, same for 400)
    python sweep.py relief  [out]   absolute height vs local relief (the default)
                                      (first: fixtures.py --relief 0 0 --suffix _abs)

    python sweep.py shade   [out]   black lines vs shading by height on 2-bit and 4-bit
    python sweep.py beta    [out]   the Germany and Austria beta list, 10 per sheet
                                      (first: python ../../pipeline/entries.py --list ../../data/beta_de_at.json)

    python sweep.py release [out]   AREA=europe: every flagged range of data/release/<area>.json plus
                                      every SAMPLE-th other one (default 6), 12 per sheet
                                      (first: python ../../pipeline/select.py <area>; LIST=path for a trial list)

LOOK='{"ripple": 5, "floorPct": 55}' overrides the look for any mode.
"""
import asyncio, json, os, sys, render
from fixtures import FIXTURES

MODE = sys.argv[1] if len(sys.argv) > 1 else "corpus"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(render.HERE, "out")
os.makedirs(OUT, exist_ok=True)
LOOK = json.loads(os.environ.get("LOOK", "{}"))


async def corpus(r):
    cells = []
    for k in FIXTURES:
        e = render.load(k); p = os.path.join(OUT, f"corpus_{k}.png")
        rep = await r.shot(e, "og", "full", p, look=LOOK)
        cells.append((p, f"{e['name']['en']} ({e['role']}), {rep[0]['lines']} lines"))
    render.sheet(cells, os.path.join(OUT, "corpus_og.png"), title=f"Fixture corpus, TRMNL OG 1-bit, full view, look {LOOK or 'default'}")


async def tune(r):
    grid = [(4, 40), (5, 40), (4, 55), (5, 55), (4, 70), (5, 70)]
    for k in FIXTURES:
        e = render.load(k); cells = []
        for ripple, fp in grid:
            look = dict(LOOK, ripple=ripple, floorPct=fp)
            p = os.path.join(OUT, f"tune_{k}_{ripple}_{fp}.png")
            await r.shot(e, "og", "full", p, look=look)
            cells.append((p, f"ripple {ripple} gaps, floor at {fp}th percentile"))
        render.sheet(cells, os.path.join(OUT, f"tune_{k}.png"), cols=2, title=f"{e['name']['en']}: ripple height x height floor, TRMNL OG 1-bit")


async def views(r):
    report = []
    combos = [("og", False), ("og", True), ("ogv2", False), ("v2", False), ("v2", True), ("kindle", False)]
    for k in FIXTURES:
        e = render.load(k); cells = []
        for dev, portrait in combos:
            for view in render.VIEWS:
                if portrait and view != "full":
                    continue
                p = os.path.join(OUT, f"views_{k}_{dev}_{'p' if portrait else 'l'}_{view}.png")
                rep = (await r.shot(e, dev, view, p, portrait=portrait, look=LOOK))[0]
                rep.update(entry=k, device=dev, portrait=portrait, view=view)
                report.append(rep)
                cells.append((p, f"{render.DEVICES[dev]['label']}{', portrait' if portrait else ''}, {view.replace('_', ' ')}, {rep.get('lines', 0)} lines"))
        render.sheet(cells, os.path.join(OUT, f"views_{k}.png"), cols=4, box=560, title=f"{e['name']['en']}: every view and device")
    json.dump(report, open(os.path.join(OUT, "views_report.json"), "w"), indent=1)


async def lang(r):
    cells = []
    for k in FIXTURES:
        e = render.load(k)
        for view in ["quadrant", "half_horizontal", "full"]:
            p = os.path.join(OUT, f"lang_{k}_{view}.png")
            await r.shot(e, "og", view, p, lang="de", look=LOOK)
            cells.append((p, f"{e['name']['de']}, {view.replace('_', ' ')}, Deutsch"))
    render.sheet(cells, os.path.join(OUT, "lang_de.png"), cols=3, title="German captions, TRMNL OG 1-bit")


async def resolution(r):
    cells = [(os.path.join(render.HERE, "..", "..", "docs", "mockups", "chosen_topdown_64_lines.png"), "A. Chosen 2026-10-01 mockup, JAXA demo tiles, PIL")]
    for key, look, cap in [
        ("karwendel", {"norm": "crop"}, "B. GLO-90, 200 grid (54 kB), ripple scaled to the stored square's top"),
        ("karwendel", {"norm": "window"}, "C. GLO-90, 200 grid, ripple scaled to the visible top"),
        ("karwendel_g280", {"norm": "window"}, "D. GLO-90, 280 grid (105 kB), visible top"),
        ("karwendel_g400", {"norm": "window"}, "E. GLO-90, 400 grid (214 kB), visible top"),
        ("karwendel", {}, "F. GLO-90, 200 grid, entry top (the fix)"),
    ]:
        p = os.path.join(OUT, f"res_{key}_{len(cells)}.png")
        await r.shot(render.load(key), "og", "full", p, look=dict(LOOK, **look))
        cells.append((p, cap))
    render.sheet(cells, os.path.join(OUT, "compare_resolution.png"), title="Karwendel on TRMNL OG 1-bit: data source, heightmap size, ripple scale")


async def relief(r):
    cells = []
    for k in FIXTURES:
        for suf, cap in [("_abs", "absolute height"), ("", "local relief (4 km, 70 %), default")]:
            p = os.path.join(OUT, f"relief_{k}{suf}.png")
            await r.shot(render.load(k + suf), "og", "full", p, look=LOOK)
            cells.append((p, f"{render.load(k)['name']['en']}: {cap}"))
    render.sheet(cells, os.path.join(OUT, "compare_relief.png"), title=f"Absolute height vs local relief, TRMNL OG 1-bit, look {LOOK or 'default'}")


SHADES = [
    ("black lines only", None),
    ("light: gray-75 above half height", [[0.5, "gray-75"]]),
    ("two steps: gray-75 above 30 %, gray-55 above 65 %", [[0.3, "gray-75"], [0.65, "gray-55"]]),
]


async def shade(r):
    for dev in ["ogv2", "v2"]:
        cells = []
        for k in ["karwendel", "glockner", "rwenzori", "cuillin"]:
            e = render.load(k)
            for cap, sh in SHADES:
                p = os.path.join(OUT, f"shade_{dev}_{k}_{len(cells)}.png")
                rep = await r.shot(e, dev, "full", p, look=dict(LOOK, shade=sh) if sh else LOOK)
                cells.append((p, f"{e['name']['en']}: {cap}"))
        render.sheet(cells, os.path.join(OUT, f"shade_{dev}.png"), cols=3, box=640,
                     title=f"Shading by height, {render.DEVICES[dev]['label']}, full view")


async def beta(r):
    """Contact sheets of the Germany and Austria beta list, 10 entries per sheet."""
    ids = [e["id"] for e in json.load(open(os.path.join(render.HERE, "..", "..", "data", "beta_de_at.json")))["entries"]]
    report = []
    for part in range(0, len(ids), 10):
        cells = []
        for k in ids[part:part + 10]:
            e = render.load(k); p = os.path.join(OUT, f"beta_{k}.png")
            rep = (await r.shot(e, "og", "full", p, look=LOOK))[0]
            rep.update(entry=k, checks=e["_checks"]); report.append(rep)
            cells.append((p, f"{e['name']['de']}, {e['peak']['de']} {e['peak_m']} m"))
        render.sheet(cells, os.path.join(OUT, f"beta_{part // 10 + 1}.png"), cols=2,
                     title=f"Beta list {part + 1} to {part + len(cells)}, TRMNL OG 1-bit, full view, defaults")
    json.dump(report, open(os.path.join(OUT, "beta_report.json"), "w"), indent=1)


async def release(r):
    """Review sheets for a release list: all flagged ranges plus a regular sample of the rest."""
    area = os.environ.get("AREA", "europe")
    path = os.environ.get("LIST") or os.path.join(render.ROOT, "data", "release", area + ".json")
    listed = json.load(open(path))["entries"]
    every = int(os.environ.get("SAMPLE", "6"))
    pick = [x for i, x in enumerate(listed) if x["flags"] or i % every == 0]
    report = []
    for part in range(0, len(pick), 12):
        cells = []
        for x in pick[part:part + 12]:
            e = render.load(x["id"]); p = os.path.join(OUT, f"release_{x['id']}.png")
            rep = (await r.shot(e, "og", "full", p, look=LOOK))[0]
            rep.update(entry=x["id"], flags=x["flags"]); report.append(rep)
            n = listed.index(x) + 1
            cells.append((p, f"{n}. {e['name']['en']}, {e['peak']['en'] or 'unnamed'} {e['peak_m']} m"
                             + (f"  [{'; '.join(x['flags'])}]" if x["flags"] else "")))
        render.sheet(cells, os.path.join(OUT, f"release_{area}_{part // 12 + 1}.png"), cols=3,
                     title=f"{area}: flagged plus every {every}th, {part + 1} to {part + len(cells)} of {len(pick)}, TRMNL OG 1-bit, defaults")
    json.dump(report, open(os.path.join(OUT, f"release_{area}_report.json"), "w"), indent=1)
    print(f"{len(pick)} of {len(listed)} rendered, drawn {sum(bool(x.get('drawn')) for x in report)}")


async def main():
    async with render.Renderer() as r:
        await globals()[MODE](r)
asyncio.run(main())
