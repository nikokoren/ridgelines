"""Check the Polling URL with Ruby Liquid, the engine TRMNL runs (recipe/tools/polling_url.rb).

    python pipeline/test_polling_url.py      # needs ruby and the liquid gem (5.14.0)

Renders the committed recipe/polling_url.txt and an all-areas variant for every combination of
ticked areas, the Area value as a list, as text and missing, UTC offsets from minus 12 to plus 14
hours (as numbers and as text), over nine days, and compares each URL with the rule in publish.py.
Expedition mode (the expedition setting as true, false, their text forms, or missing) is checked
the same way over three weeks, and properties() proves on the rule itself that every area runs a
year without repeats, that switching the mode moves an area's counter by only a few ranges, and that
with one area ticked both modes agree.
"""
import itertools, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidates  # noqa: E402
import publish  # noqa: E402

RB = os.path.join(HERE, "..", "recipe", "tools", "polling_url.rb")
T0 = 1791417600           # 2026-10-08 00:00 UTC
OFFSETS = (-43200, -18000, 0, 3600, 19800, 34200, 50400)


def render(url_file, cases):
    """URLs for a list of (unix time, context) pairs, all in one Ruby process."""
    r = subprocess.run(["ruby", RB], input=json.dumps(cases).encode(), capture_output=True,
                       env=dict(os.environ, URL_FILE=url_file))
    if r.returncode:
        raise SystemExit(r.stderr.decode())
    return [u.split(publish.SITE_URL + "/", 1)[1] for u in json.loads(r.stdout)]


EXPEDITION = {"missing": False, True: True, False: False, "true": True, "false": False}


def rotation(day, k, expedition):
    """(index of the area in the ticked list, that area's counter) for a local day number."""
    if expedition:
        week, weekday = (day + 3) // 7, (day + 3) % 7      # weeks start on Monday; day 0 was a Thursday
        return week % k, (week // k) * 7 + weekday - 3
    return day % k, day // k


def expected(counts, ticks, t, off, expedition=False):
    day = (t + off) // 86400
    if not counts:
        return f"beta/d/{day % 30}.json"
    built = [a for a in candidates.AREAS if counts.get(a)]
    s = [a for a in built if a in ticks] or built
    j, n = rotation(day, len(s), expedition)
    return f"{s[j]}/d/{n % counts[s[j]]}.json"


def properties(count=365, days=range(20000, 20000 + 4 * 365 * 4)):
    """Facts about the rule itself, for 1 to 4 ticked areas over sixteen years."""
    worst = 0
    for k in range(1, 5):
        for exp in (False, True):
            seen = {}
            for d in days:
                j, n = rotation(d, k, exp)
                seen.setdefault(j, []).append(n)
            for j, ns in seen.items():
                # each area's counter goes up by one every day it is shown: a year of different ranges
                assert all(b == a + 1 for a, b in zip(ns, ns[1:])), (k, exp, j)
        for d in days:
            (j0, n0), (j1, n1) = rotation(d, k, False), rotation(d, k, True)
            if k == 1:
                assert (j0, n0) == (j1, n1), d
            # after switching on day d, the area shown has moved this far from where daily mode had it
            worst = max(worst, abs(n1 - rotation(d + (j1 - j0) % k, k, False)[1]))
    assert worst <= 7, worst
    return worst


def check(url_file, counts):
    cases, wants = [], []
    combos = [list(c) for k in range(5) for c in itertools.combinations(candidates.AREAS, k)]
    for ticks in combos:
        for form in ("list", "text", "missing"):
            if form == "missing" and ticks:
                continue
            for exp in EXPEDITION:
                for off in OFFSETS:
                    for d in range(9 if exp == "missing" else 21):
                        t = T0 + d * 86400 + (d * 7919) % 86400      # a different time of day each day
                        ctx = {"trmnl": {"user": {"utc_offset": off if d % 2 else str(off)}}}
                        if form != "missing":
                            ctx["area"] = ticks if form == "list" else ",".join(ticks)
                        if exp != "missing":
                            ctx["expedition"] = exp
                        cases.append((t, ctx))
                        wants.append(expected(counts, ticks, t, off, EXPEDITION[exp]))
    got = render(url_file, cases)
    bad = [(c, g, w) for c, g, w in zip(cases, got, wants) if g != w]
    for c, g, w in bad[:10]:
        print("mismatch", c, g, w)
    return len(cases), len(bad)


if __name__ == "__main__":
    committed = os.path.join(HERE, "..", "recipe", "polling_url.txt")
    counts = {}
    for a in candidates.AREAS:
        p = os.path.join(publish.RELEASE, a + ".json")
        if os.path.exists(p):
            counts[a] = len(json.load(open(p))["entries"])
    assert open(committed).read().strip() == publish.polling_url(counts or None), "polling_url.txt is stale"
    results = [("committed", *check(committed, counts))]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        full = {"europe": 365, "americas": 364, "asia": 300, "africa": 7}
        f.write(publish.polling_url(full))
    results.append(("all four areas, uneven counts", *check(f.name, full)))
    os.remove(f.name)
    for name, n, bad in results:
        print(f"{name}: {n} renders, {bad} mismatches")
    print(f"rule: a year without repeats per area in both modes; switching moves at most {properties()} ranges")
    sys.exit(1 if any(bad for _, _, bad in results) else 0)
