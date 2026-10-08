"""Check the Polling URL with Ruby Liquid, the engine TRMNL runs (recipe/tools/polling_url.rb).

    python pipeline/test_polling_url.py      # needs ruby and the liquid gem (5.14.0)

Renders the committed recipe/polling_url.txt and an all-areas variant for every combination of
ticked areas, the Area value as a list, as text and missing, UTC offsets from minus 12 to plus 14
hours (as numbers and as text), over nine days, and compares each URL with the rule in publish.py.
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


def expected(counts, ticks, t, off):
    day = (t + off) // 86400
    if not counts:
        return f"beta/d/{day % 30}.json"
    built = [a for a in candidates.AREAS if counts.get(a)]
    s = [a for a in built if a in ticks] or built
    a = s[day % len(s)]
    return f"{a}/d/{(day // len(s)) % counts[a]}.json"


def check(url_file, counts):
    cases, wants = [], []
    combos = [list(c) for k in range(5) for c in itertools.combinations(candidates.AREAS, k)]
    for ticks in combos:
        for form in ("list", "text", "missing"):
            if form == "missing" and ticks:
                continue
            for off in OFFSETS:
                for d in range(9):
                    t = T0 + d * 86400 + (d * 7919) % 86400      # a different time of day each day
                    ctx = {"trmnl": {"user": {"utc_offset": off if d % 2 else str(off)}}}
                    if form != "missing":
                        ctx["area"] = ticks if form == "list" else ",".join(ticks)
                    cases.append((t, ctx))
                    wants.append(expected(counts, ticks, t, off))
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
    sys.exit(1 if any(bad for _, _, bad in results) else 0)
