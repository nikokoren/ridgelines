"""Check how the templates read the show/hide settings, with Ruby Liquid (recipe/tools/render.rb).

    python pipeline/test_settings.py      # needs ruby and the liquid gem (5.14.0)

Peak name, info box and title bar are boolean fields (2026-10-09). TRMNL's form builder article
does not say whether Liquid receives true/false or "true"/"false", and earlier installs saved
"yes"/"no" from the select fields, so every form is rendered in every view: true, false,
"true", "false", "yes", "no", "" and missing. Defaults: peak name and info box on, title bar off.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RB = os.path.join(HERE, "..", "recipe", "tools", "render.rb")
VIEWS = ("full", "half_horizontal", "half_vertical", "quadrant")
FORMS = {"true": True, "false": False, '"true"': "true", '"false"': "false", '"yes"': "yes", '"no"': "no",
         '""': "", "missing": None}
ON = {True, "true", "yes"}
OFF = {False, "false", "no"}
PAYLOAD = {"heights": "AA==", "grid": 1, "side_km": 1, "width_km": 1, "floor": 0, "top": 1, "peak_x": 0, "peak_y": 0,
           "peak": {"en": "Birkkarspitze", "de": "Birkkarspitze"},
           "box_title": {"en": "Karwendel, Austria and Germany", "de": "Karwendel, Österreich und Deutschland"},
           "box_peak": {l: {u: "Highest peak Birkkarspitze 2,749 m" for u in ("metric", "imperial")} for l in ("en", "de")},
           "caption": {l: {u: {"full": "Karwendel", "full_portrait": "Karwendel", "half_horizontal": "Karwendel",
                                "short": "Karwendel"} for u in ("metric", "imperial")} for l in ("en", "de")}}


def render(view, values):
    ctx = dict(PAYLOAD, trmnl={"user": {"utc_offset": 0}, "plugin_settings": {"custom_fields_values": values}})
    r = subprocess.run(["ruby", RB, view], input=json.dumps(ctx).encode(), capture_output=True)
    if r.returncode:
        raise SystemExit(r.stderr.decode())
    return r.stdout.decode()


def shown(html):
    return {"peak_label": 'data-peak-name="Birkkarspitze"' in html,
            "info_box": "data-ridgelines-box>" in html,     # the markup, not the script's selector
            "title_bar": "title_bar" in html}


if __name__ == "__main__":
    n = bad = 0
    for key, default in (("peak_label", True), ("info_box", True), ("title_bar", False)):
        for form, value in FORMS.items():
            want = True if value in ON else False if value in OFF else default
            values = {} if value is None else {key: value}
            for view in VIEWS:
                got = shown(render(view, values))[key]
                n += 1
                if got != want:
                    bad += 1
                    print(f"mismatch: {key} = {form} in {view}: shown {got}, want {want}")
    print(f"{n} renders, {bad} mismatches")
    sys.exit(1 if bad else 0)
