"""Contact sheets for look tuning, rendered through the real framework.

    python sweep.py corpus  [out]   every entry, OG 1-bit full view, current look
    python sweep.py tune    [out]   every entry at a grid of ripple x floor settings
    python sweep.py views   [out]   every entry x 5 views x 3 bit depths and TRMNL X, with a report
    python sweep.py lang    [out]   German captions at quadrant size
    python sweep.py resolution [out]  Karwendel: JAXA mockup vs GLO-90 at 200/280/400 grids
                                      (first: fixtures.py karwendel --grid 280 --suffix _g280, same for 400)
    python sweep.py relief  [out]   absolute height vs local relief (the default)
                                      (first: fixtures.py --relief 0 0 --suffix _abs)

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


async def main():
    async with render.Renderer() as r:
        await globals()[MODE](r)
asyncio.run(main())
