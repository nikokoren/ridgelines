"""On-screen words for an entry, in every language and unit system.

The templates hold no words of their own (only the plugin name and the error
screen); every string they show is built here and shipped in the payload,
keyed by language and units, so a third language is one more dictionary.
"""

UI = {
    "en": {"and": "and", "more": "and {n} more", "highest": "Highest peak", "point": "Highest point", "thousands": ","},
    "de": {"and": "und", "more": "und {n} weitere", "highest": "Höchster Gipfel", "point": "Höchster Punkt", "thousands": "."},
}
LANGS = tuple(UI)
UNITS = ("metric", "imperial")
SEP = " · "


def height(m, lang, units):
    """2,749 m / 2.749 m; feet rounded to the nearest 10 ft (docs/brief.md, Text and language)."""
    v, unit = (m, "m") if units == "metric" else (int(round(m * 3.28084 / 10) * 10), "ft")
    # No-break space: a wrapped line never parts the number from its unit ("4,34…" on #81, 2026-10-08).
    return f"{v:,}".replace(",", UI[lang]["thousands"]) + "\u00a0" + unit


def countries(entry, lang):
    """One or two countries in full; more than two as the first and a count (Niko, 2026-10-02):
    "Austria and 2 more", "Österreich und 2 weitere". The build lists the summit's countries first."""
    c = [x for x in plain(entry["country"][lang]).split(", ") if x]
    if len(c) > 2:
        return c[0] + " " + UI[lang]["more"].format(n=len(c) - 1)
    return f"{c[0]} {UI[lang]['and']} {c[1]}" if len(c) == 2 else (c[0] if c else "")


def plain(text):
    """No en or em dashes on screen (CLAUDE.md): Wikidata writes "Kamnik\u2013Savinja Alps"."""
    return (text or "").replace("\u2013", "-").replace("\u2014", "-")


def peak_name(entry, lang):
    return plain(entry["peak"][lang])


def range_name(entry, lang):
    """The range name, capitalised as a headline: Wikidata keeps French lower case ("monts d'Or")."""
    n = plain(entry["name"][lang])
    return n[:1].upper() + n[1:]


def headline(entry, lang):
    """Info box headline: range and country, like Downstream's "Munich, Germany"."""
    where = countries(entry, lang)
    name = range_name(entry, lang)
    return f"{name}, {where}" if where else name


def peak_line(entry, lang, units):
    """Info box second line: "Highest peak Birkkarspitze 2,749 m" (Niko, 2026-10-01). A terrain
    summit that no Wikidata peak names reads "Highest point 1,694 m"."""
    if not entry["peak"][lang]:
        return f"{UI[lang]['point']} {height(entry['peak_m'], lang, units)}"
    return f"{UI[lang]['highest']} {peak_name(entry, lang)} {height(entry['peak_m'], lang, units)}"


def captions(entry, lang, units):
    """Title bar instance text per view (title bar setting, off by default), in the info box's
    order: range, country, then peak and height (2026-10-09; the full caption used to put the
    country last). Narrower views drop from the end: portrait drops the country, which did not
    fit beside the plugin title at 480 px (PROJECT.md, portrait caption), half horizontal the
    peak, quadrant and half vertical keep the range alone."""
    name = range_name(entry, lang)
    peak = " ".join(p for p in (peak_name(entry, lang), height(entry["peak_m"], lang, units)) if p)
    return {
        "full": SEP.join((headline(entry, lang), peak)),
        "full_portrait": SEP.join((name, peak)),
        "half_horizontal": headline(entry, lang),
        "short": name,
    }
