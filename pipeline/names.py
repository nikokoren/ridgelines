"""English names that look like another language, replaced from English Wikipedia (2026-10-09).

    python pipeline/names.py        # writes data/name_overrides.json, prints what it changed

Wikidata's English label is sometimes another language's name: "Sudirmanbergen" (Swedish),
"Momskiy Khrebet" (Russian), "Pegunungan Foja" (Indonesian), "Iserlohner Höhe" (German). A name
is replaced only when its English label contains another language's generic mountain word
(FOREIGN) and the English Wikipedia article on the same item has a different title, which then
becomes the English name, without any bracketed qualifier. English Wikipedia titles are not used
otherwise: many differ only in spelling, and some name something else (an article about a forest
reserve, a glacier, or a neighbouring peak). A name with no English article stays as Wikidata has
it: often the local name is also the English one (Monti Lattari, Totes Gebirge).

Bracketed qualifiers ("Hohenstein (Namibia)") and Cyrillic look-alike letters in Latin names
("Сentralny Gory") are cleaned for every name at display time, in words.py.
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import entries  # noqa: E402
import words  # noqa: E402

OUT = os.path.join(ROOT, "data", "name_overrides.json")
FOREIGN = re.compile(
    r"(^|[\s\-])(bergen|berget|berge|gebirge|bergland|gruppe|kamm|kette|alpen|höhe|fjella|fjellet|fjäll|"
    r"massivet|gebergte|chaîne|catena|gruppo|monti|khrebet|chrebet|hrebet|pohorie|vrchy|hory|góry|gory|"
    r"planina|dağları|dağı|dagi|buuraha|kabukiran|pegunungan|banjaran|silsilat|jibāl|sanchi|shanmai|"
    r"pik|vârful|varful|gora)($|[\s\-])|[a-zäöüß](bergen|gebirge|bergland|kamm|gruppe|alpen)$", re.I)
BRACKET = re.compile(r"\s*\([^)]*\)\s*$")
# Scripts TRMNL's fonts cannot draw: Greek, Cyrillic, Armenian, Hebrew, Arabic, Georgian, Thai,
# Japanese, Chinese, Korean. Cyrillic fell back to a serif system font in the render (2026-10-09).
NON_LATIN = re.compile(r"[\u0370-\u03ff\u0400-\u04ff\u0530-\u058f\u0590-\u05ff\u0600-\u06ff\u10a0-\u10ff"
                       r"\u0e00-\u0e7f\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")
LATIN_LANGS = ["en", "de", "fr", "it", "es", "pt", "nl", "pl", "cs", "sk", "sl", "hr", "bs", "sr-el", "sh", "ro",
               "hu", "tr", "az", "uz", "tk", "ku", "id", "ms", "vi", "tl", "sq", "et", "lv", "lt", "fi", "sv", "nb",
               "da", "is", "ga", "cy", "eu", "ca", "gl", "af", "sw", "so", "mul"]


# Standard romanisations for the scripts found in the lists (2026-10-09): Russian BGN/PCGN
# (simplified), Bulgarian Streamlined System (official since 2009), Georgian national system (2002).
CYR_COMMON = dict(zip("абвгдезиклмнопрстуфхцчшщ", ["a", "b", "v", "g", "d", "e", "z", "i", "k", "l", "m", "n", "o",
                                               "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch"]))
ROMAN = {
    "ru": dict(CYR_COMMON, ё="yo", ж="zh", й="y", ъ="", ы="y", ь="", э="e", ю="yu", я="ya"),
    "bg": dict(CYR_COMMON, ж="zh", й="y", х="h", щ="sht", ъ="a", ь="y", ю="yu", я="ya"),
    "ka": dict(zip("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ",
                   ["a", "b", "g", "d", "e", "v", "z", "t", "i", "k'", "l", "m", "n", "o", "p'", "zh", "r", "s",
                    "t'", "u", "p", "k", "gh", "q'", "sh", "ch", "ts", "dz", "ts'", "ch'", "kh", "j", "h"])),
}


def romanise(text, lang):
    table = ROMAN[lang]
    out = []
    for i, ch in enumerate(text):
        r = table.get(ch.lower())
        if r is None:
            out.append(ch)
            continue
        out.append(r.capitalize() if ch.isupper() or (lang == "ka" and (i == 0 or text[i - 1] == " ")) else r)
    return "".join(out)


def latin_label(qid, known):
    """A Latin-script name for an item: an English, German or multilingual label; else a standard
    romanisation of its Russian, Bulgarian or Georgian label; else the first Latin label in
    LATIN_LANGS order. None if there is none."""
    rows = entries.sparql("SELECT ?l WHERE { wd:%s rdfs:label ?l }" % qid, qid + ".labels")
    by = {r["l"]["xml:lang"]: r["l"]["value"] for r in rows if "xml:lang" in r["l"]}
    for k in list(known) + [by.get(l) for l in ("en", "de", "mul")]:
        if k and not NON_LATIN.search(k):
            return k
    for lang in ROMAN:
        if by.get(lang):
            return romanise(by[lang], lang)
    for lang in LATIN_LANGS:
        v = by.get(lang)
        if v and not NON_LATIN.search(v):
            return v
    return None


def lists():
    paths = [os.path.join(ROOT, "data", "beta_de_at.json")] + sorted(glob.glob(os.path.join(ROOT, "data", "release", "*.json")))
    for p in paths:
        for x in json.load(open(p))["entries"]:
            yield x


def peak_qid(e):
    if e.get("kind") == "terrain":
        named = e["_checks"].get("named_peak")
        return named["qid"] if named else None
    rows = entries.sparql("SELECT ?p WHERE { wd:%s wdt:P610 ?p }" % e["wikidata"], e["wikidata"] + ".p610")
    return rows[0]["p"]["value"].rsplit("/", 1)[-1] if rows else None


def enwiki(qids):
    """English Wikipedia title per item, None where there is no article."""
    out = {}
    qids = sorted(set(qids))
    for k in range(0, len(qids), 200):
        chunk = qids[k:k + 200]
        rows = entries.sparql("""SELECT ?item ?title WHERE { VALUES ?item { %s }
          ?a schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?title }"""
                              % " ".join("wd:" + q for q in chunk), "enwiki_%d_%s" % (len(chunk), chunk[0]))
        for b in rows:
            out[b["item"]["value"].rsplit("/", 1)[-1]] = b["title"]["value"]
    return out


def main():
    items, script = [], {}
    for x in lists():
        e = json.load(open(os.path.join(entries.ENTRIES, x["id"] + ".json")))
        items.append((x["id"], "name", e["wikidata"], e["name"]["en"]))
        p = peak_qid(e)
        if p and e["peak"]["en"]:
            items.append((x["id"], "peak", p, e["peak"]["en"]))
        # Names in a script the fonts cannot draw: a Latin label instead, or none (a peak then
        # reads "Highest point"; a range without one would need picking out of the list).
        for field, qid in (("name", e["wikidata"]), ("peak", p)):
            names = e[field]
            bad = [l for l in ("en", "de") if names.get(l) and NON_LATIN.search(words.plain(names[l]))]
            if bad and qid:
                lat = latin_label(qid, [names.get(l) for l in ("en", "de")])
                if lat is None and field == "name":
                    raise SystemExit(f"{x['id']}: range name {names} has no Latin form; take it out of the list")
                script.setdefault(x["id"], {})[field] = dict({l: lat or "" for l in bad}, was=names[bad[0]], wikidata=qid)
    flagged = [i for i in items if FOREIGN.search(i[3])]
    titles = enwiki(q for _, _, q, _ in flagged)
    overrides = script
    for eid, field, qid, label in flagged:
        title = BRACKET.sub("", titles.get(qid) or "").strip()
        if title and title.lower() != BRACKET.sub("", label).strip().lower():
            overrides.setdefault(eid, {}).setdefault(field, {"was": label, "wikidata": qid})["en"] = title
    json.dump({"note": "Written by pipeline/names.py: English names that were another language's, from English "
                       "Wikipedia titles. Rebuild, do not hand edit.", "overrides": dict(sorted(overrides.items()))},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"{len(items)} names, {len(flagged)} with another language's mountain word, "
          f"{len(script)} in a script the fonts cannot draw; overrides:")
    for eid, v in sorted(overrides.items()):
        for field, o in v.items():
            print(f"  {field:4s} {o['was']}  ->  " + ", ".join(f"{l}: {o[l] or '(unnamed)'}" for l in ("en", "de") if l in o))


if __name__ == "__main__":
    main()
