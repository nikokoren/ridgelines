"""Render fixture entries through the real TRMNL framework (CSS, JS, fonts) in Chromium.

Markup uses framework classes only, the drawing comes from template/ridgelines.js,
so these renders are what the recipe template would produce, not a mock title
bar. Framework assets are fetched once from trmnl.com into .cache/fw/.

Usage:
    python render.py --entry karwendel --device og --view full --out k.png
    python render.py --sweep            # every entry x view x device, plus contact sheets
"""
import argparse, asyncio, json, os, sys, urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
FW = os.path.join(CACHE, "fw")
ENTRIES = os.path.join(CACHE, "entries")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
ORIGIN = "http://mock.trmnl.local"

# screen classes per device as the framework's Devices page lists them (checked 2026-10-01)
DEVICES = {
    "og":     dict(cls="screen--og screen--md screen--1bit", ratio=1, depth=1, label="TRMNL OG, 1-bit"),
    "ogv2":   dict(cls="screen--ogv2 screen--md screen--2bit", ratio=1, depth=2, label="TRMNL OG, 2-bit"),
    "v2":     dict(cls="screen--v2 screen--lg screen--density-2x screen--4bit", ratio=1.8, depth=4, label="TRMNL X, 4-bit"),
    "kindle": dict(cls="screen--amazon_kindle_2024 screen--sm screen--density-2x screen--4bit", ratio=1.75, depth=4, label="Kindle 2024, 4-bit"),
}
VIEWS = {
    "full":            (None, "view--full"),
    "half_horizontal": ("mashup--1Tx1B", "view--half_horizontal"),
    "half_vertical":   ("mashup--1Lx1R", "view--half_vertical"),
    "quadrant":        ("mashup--2x2", "view--quadrant"),
}
SEP = " · "


def fmt_m(m, lang):
    s = f"{m:,}"
    return (s.replace(",", ".") if lang == "de" else s) + " m"


def caption(e, view, lang="en", portrait=False):
    name, peak, country = e["name"][lang], e["peak"][lang], e["country"][lang]
    if view == "full":
        parts = [name, f"{peak} {fmt_m(e['peak_m'], lang)}"] + ([] if portrait else [country])
    elif view == "half_horizontal":
        parts = [name, country]
    else:
        parts = [name]
    return SEP.join(p for p in parts if p)


def view_markup(e, view, lang, portrait, idx):
    return f"""
  <div class="view {VIEWS[view][1]}">
    <div class="layout layout--col layout--stretch">
      <div id="rl-{idx}" class="w--full h--full" data-ridgelines></div>
    </div>
    <div class="title_bar">
      <img class="image image--adaptive" src="/images/plugins/trmnl--render.svg">
      <span class="title">Ridgelines</span>
      <span class="instance">{caption(e, view, lang, portrait)}</span>
    </div>
  </div>"""


def other_view(cls):
    return f"""
  <div class="view {cls}">
    <div class="layout layout--col layout--center"><span class="label label--outline">Another plugin</span></div>
  </div>"""


def page(e, device, view, lang="en", portrait=False, dark=False, look=None):
    d = DEVICES[device]
    cls = "screen " + d["cls"] + (" screen--portrait" if portrait else "") + (" screen--dark-mode" if dark else "")
    mashup, vcls = VIEWS[view]
    body = view_markup(e, view, lang, portrait, 0)
    if mashup:
        n = 4 if view == "quadrant" else 2
        body = f'<div class="mashup {mashup}">' + body + "".join(other_view(vcls) for _ in range(n - 1)) + "</div>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="/plugins.css"><script src="/plugins.js"></script>
<script src="/ridgelines.js"></script></head>
<body class="environment trmnl"><div class="{cls}">{body}
</div>
<script>
window.ENTRY = {json.dumps(e, ensure_ascii=False)};
window.LOOK = {json.dumps(look or {})};
window.rlDraw = function () {{
  return Array.prototype.map.call(document.querySelectorAll("[data-ridgelines]"), function (box) {{
    return Ridgelines.draw(box, ENTRY, Object.assign({{ peakName: ENTRY.peak["{lang}"] }}, LOOK));
  }});
}};
</script></body></html>"""


def screen_size(device, portrait):
    css = open(os.path.join(FW, "plugins.css")).read()
    import re
    key = {"kindle": "amazon_kindle_2024"}.get(device, device)
    m = re.search(r"\.screen--%s\{[^}]*--screen-w:(\d+)px;--screen-h:(\d+)px" % key, css.replace(" ", ""))
    w, h = int(m.group(1)), int(m.group(2))
    return (h, w) if portrait else (w, h)


def fetch_framework():
    if os.path.exists(os.path.join(FW, "plugins.js")):
        return
    os.makedirs(os.path.join(FW, "fonts"), exist_ok=True)
    os.makedirs(os.path.join(FW, "images", "plugins"), exist_ok=True)
    get = lambda u, p: urllib.request.urlretrieve("https://trmnl.com" + u, os.path.join(FW, p))
    get("/css/latest/plugins.css", "plugins.css")
    get("/js/latest/plugins.js", "plugins.js")
    get("/images/plugins/trmnl--render.svg", "images/plugins/trmnl--render.svg")
    import re
    for f in sorted(set(re.findall(r'url\("(/fonts/[^"]+\.(?:woff2|ttf))"\)', open(os.path.join(FW, "plugins.css")).read()))):
        if f.endswith(".ttf") and "TRMNL" in f:
            continue
        get(f, f.lstrip("/"))


class Renderer:
    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(executable_path=CHROME)
        return self

    async def __aexit__(self, *a):
        await self.browser.close()
        await self.pw.stop()

    async def shot(self, e, device, view, out, lang="en", portrait=False, dark=False, look=None):
        w, h = screen_size(device, portrait)
        # The framework scales the screen by --pixel-ratio itself, so capture the
        # panel's physical size at a device scale factor of 1.
        k = DEVICES[device]["ratio"]
        ctx = await self.browser.new_context(viewport={"width": round(w * k), "height": round(h * k)}, device_scale_factor=1)
        p = await ctx.new_page()
        html = page(e, device, view, lang, portrait, dark, look)

        async def route(r):
            path = r.request.url[len(ORIGIN):].split("?")[0]
            if path == "/":
                return await r.fulfill(body=html, content_type="text/html")
            if path == "/ridgelines.js":
                return await r.fulfill(path=os.path.join(HERE, "template", "ridgelines.js"))
            f = os.path.join(FW, path.lstrip("/"))
            if os.path.exists(f):
                return await r.fulfill(path=f)
            return await r.fulfill(status=404)
        await p.route("**/*", route)
        await p.goto(ORIGIN + "/")
        await p.wait_for_function("window.TRMNL_PLUGINS_READY === true", timeout=20000)
        await p.evaluate("document.fonts.ready")
        rep = await p.evaluate("rlDraw()")
        await p.screenshot(path=out)
        await ctx.close()
        quantise(out, DEVICES[device]["depth"])
        return rep


def quantise(path, depth):
    """Approximate the panel: 1-bit threshold, 2-bit 4 greys, 4-bit 16 greys."""
    im = Image.open(path).convert("L")
    levels = 2 ** depth
    im = im.point(lambda v: round(v / 255 * (levels - 1)) * 255 // (levels - 1))
    im.save(path)


def sheet(cells, out, cols=2, title=None, pad=24, box=800):
    """cells: list of (png path, caption). Contact sheet for look review, not a framework render."""
    from PIL import ImageDraw, ImageFont
    ims = [Image.open(p).convert("L") for p, _ in cells]
    for im in ims:                                       # hi-DPI renders shrink to fit one cell
        im.thumbnail((box, box), Image.LANCZOS)
    cw, ch = max(i.width for i in ims), max(i.height for i in ims)
    font = lambda s, b=False: ImageFont.truetype(os.path.join(FW, "fonts", "Inter.ttf"), s)
    head = 44 if title else 0
    rows = (len(ims) + cols - 1) // cols
    W, H = cols * (cw + pad) + pad, head + rows * (ch + pad + 30) + pad
    S = Image.new("L", (W, H), 232); d = ImageDraw.Draw(S)
    if title:
        d.text((pad, pad), title, font=font(22), fill=20)
    for k, (im, (_, cap)) in enumerate(zip(ims, cells)):
        x = pad + (k % cols) * (cw + pad); y = head + pad + (k // cols) * (ch + pad + 30)
        d.text((x, y), cap, font=font(17), fill=20)
        d.rectangle([x - 1, y + 29, x + im.width, y + 30 + im.height], outline=150)
        S.paste(im, (x, y + 30))
    S.save(out)
    return out


def load(key):
    return json.load(open(os.path.join(ENTRIES, key + ".json")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", default="karwendel")
    ap.add_argument("--device", default="og", choices=DEVICES)
    ap.add_argument("--view", default="full", choices=VIEWS)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--portrait", action="store_true")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--look", default="{}", help='JSON overrides, e.g. {"ripple": 5}')
    ap.add_argument("--out", default="render.png")
    a = ap.parse_args()
    fetch_framework()

    async def main():
        async with Renderer() as r:
            rep = await r.shot(load(a.entry), a.device, a.view, a.out, a.lang, a.portrait, a.dark, json.loads(a.look))
            print(json.dumps(rep))
    asyncio.run(main())
