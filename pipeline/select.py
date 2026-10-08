"""Pick the release list for an area: build candidates in rank order, keep those that pass the checks.

    python pipeline/select.py europe                # writes data/release/europe.json
    python pipeline/select.py africa --target 40    # a trial run

Candidates come from candidates.py (ranges with a listed highest point first, then the terrain
fallback, each by sitelinks). A candidate is skipped before any terrain work when its crop centre
lies too close to one already picked, and after building when a check fails (CHECKS). Soft flags
do not skip, they mark the range for the contact sheet (sweep.py release). The list file holds
what publish.py needs to rebuild each entry; the report in .cache/release/ holds every decision.
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import candidates  # noqa: E402
import entries  # noqa: E402

TARGET = 365          # a year without repeats in every area (Niko, 2026-10-08)
CLOSE = 0.75          # crop centres closer than this share of the mean width show the same terrain
SEA = 0.7             # share of sea in the reference window (Taveuni, an island, has 0.6)
FLAT_M = 400          # height span of the reference window (Fichtelgebirge 664, MacDonnell 673)
LOW_SUMMIT = 0.65     # terrain summit below this share of the listed height: not on high ground
                      # (smoothing alone gives 0.88 to 0.97 on the corpus, MacDonnell 0.71)


def spec(c, area):
    return dict(qid=c["wikidata"], role=f"release, {candidates.NAMES[area]}", lat=c["lat"], lon=c["lon"],
                width_km=c["width_km"], kind=c["kind"])


def checks(e):
    """(hard failures, soft flags) of a built entry."""
    c = e["_checks"]
    hard, soft = [], []
    if c["ocean_ref_share"] > SEA:
        hard.append(f"mostly sea ({c['ocean_ref_share']:.0%})")
    if c["relief_m"] < FLAT_M:
        hard.append(f"too flat ({c['relief_m']} m)")
    if not c["peak_in_square"]:
        hard.append("summit outside the crop")
    if e["kind"] == "listed" and c["peak_found_m"] < LOW_SUMMIT * e["peak_m"]:
        hard.append(f"summit off high ground ({c['peak_found_m']} of {e['peak_m']} m)")
    if not e["name"]["en"]:
        hard.append("no name")
    if e["kind"] == "terrain":
        soft.append("terrain summit" + ("" if c["named_peak"] else ", unnamed"))
    if c["peak_source"] not in ("listed", "terrain") and e["kind"] == "listed":
        soft.append(c["peak_source"])
    if c["spike_pixels"] > 20:
        soft.append(f"{c['spike_pixels']} spike samples")
    if e["name"]["de"] == e["name"]["en"] and e["peak"]["de"] == e["peak"]["en"]:
        soft.append("no German labels")
    return hard, soft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("area", choices=candidates.AREAS)
    ap.add_argument("--target", type=int, default=TARGET)
    ap.add_argument("--out", help="list file, default data/release/<area>.json")
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, "data", "release", a.area + ".json")
    entries.QUIET = True

    cands = [c for c in candidates.all_candidates() if c["area"] == a.area]
    picked, report, t0 = [], [], time.time()
    for n, c in enumerate(cands):
        if len(picked) >= a.target:
            break
        near = [p for p in picked if candidates.km_between((c["lat"], c["lon"]), (p["lat"], p["lon"]))
                < CLOSE * (c["width_km"] + p["width_km"]) / 2]
        rec = dict(wikidata=c["wikidata"], kind=c["kind"], sitelinks=c["sitelinks"])
        if near:
            report.append(dict(rec, skipped=f"too close to {near[0]['wikidata']}"))
            continue
        entries.FIXTURES[c["wikidata"]] = spec(c, a.area)
        try:
            e = entries.build(c["wikidata"])
        except entries.Skip as s:
            report.append(dict(rec, skipped=str(s)))
            continue
        hard, soft = checks(e)
        rec.update(name=e["name"]["en"], peak=e["peak"]["en"], peak_m=e["peak_m"])
        if hard:
            report.append(dict(rec, skipped="; ".join(hard)))
            continue
        report.append(dict(rec, picked=len(picked), flags=soft))
        picked.append(dict(id=c["wikidata"], wikidata=c["wikidata"], kind=c["kind"], name=e["name"]["en"],
                           peak=e["peak"]["en"], peak_m=e["peak_m"], lat=c["lat"], lon=c["lon"],
                           width_km=c["width_km"], flags=soft))
        if len(picked) % 25 == 0:
            print(f"{len(picked)} picked from {n + 1} candidates, {time.time() - t0:.0f} s", flush=True)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"area": a.area, "name": candidates.NAMES[a.area], "target": a.target,
               "note": "Written by pipeline/select.py from live Wikidata and Copernicus GLO-90; rebuild, do not hand edit.",
               "entries": picked}, open(out, "w"), ensure_ascii=False, indent=1)
    rep = os.path.join(entries.CACHE, "release", a.area + "_report.json")
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    json.dump(report, open(rep, "w"), ensure_ascii=False, indent=1)
    reasons = {}
    for r in report:
        if "skipped" in r:
            k = r["skipped"].split(" (")[0].split(":")[-1].strip()
            k = "too close" if k.startswith("too close") else k
            reasons[k] = reasons.get(k, 0) + 1
    print(f"{candidates.NAMES[a.area]}: {len(picked)} of {a.target} picked from {len(report)} candidates "
          f"in {time.time() - t0:.0f} s; skipped {reasons}; flagged {sum(bool(p['flags']) for p in picked)}")
    print(f"list {out}, report {rep}")


if __name__ == "__main__":
    main()
