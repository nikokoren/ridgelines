"""On-screen words for an entry, in every language and unit system.

The templates hold no words of their own (only the plugin name and the error
screen); every string they show is built here and shipped in the payload,
keyed by language and units, so a third language is one more dictionary.
"""

UI = {
    "en": {"and": "and", "more": "and {n} more", "highest": "Highest peak", "thousands": ","},
    "de": {"and": "und", "more": "und {n} weitere", "highest": "Höchster Gipfel", "thousands": "."},
}
LANGS = tuple(UI)
UNITS = ("metric", "imperial")
SEP = " · "


def height(m, lang, units):
    """2,749 m / 2.749 m; feet rounded to the nearest 10 ft (docs/brief.md, Text and language)."""
    v, unit = (m, "m") if units == "metric" else (int(round(m * 3.28084 / 10) * 10), "ft")
    return f"{v:,}".replace(",", UI[lang]["thousands"]) + " " + unit


def countries(entry, lang):
    """One or two countries in full; more than two as the first and a count (Niko, 2026-10-02):
    "Austria and 2 more", "Österreich und 2 weitere". The build lists the summit's countries first."""
    c = [x for x in entry["country"][lang].split(", ") if x]
    if len(c) > 2:
        return c[0] + " " + UI[lang]["more"].format(n=len(c) - 1)
    return f"{c[0]} {UI[lang]['and']} {c[1]}" if len(c) == 2 else (c[0] if c else "")


def headline(entry, lang):
    """Info box headline: range and country, like Downstream's "Munich, Germany"."""
    where = countries(entry, lang)
    return f"{entry['name'][lang]}, {where}" if where else entry["name"][lang]


def peak_line(entry, lang, units):
    """Info box second line: "Highest peak Birkkarspitze 2,749 m" (Niko, 2026-10-01)."""
    return f"{UI[lang]['highest']} {entry['peak'][lang]} {height(entry['peak_m'], lang, units)}"


def captions(entry, lang, units):
    """Title bar instance text per view (title bar setting, off by default). Portrait drops the
    country, which did not fit beside the plugin title at 480 px (PROJECT.md, portrait caption)."""
    name, peak = entry["name"][lang], f"{entry['peak'][lang]} {height(entry['peak_m'], lang, units)}"
    where = countries(entry, lang)
    return {
        "full": SEP.join(p for p in (name, peak, where) if p),
        "full_portrait": SEP.join((name, peak)),
        "half_horizontal": SEP.join(p for p in (name, where) if p),
        "short": name,
    }
