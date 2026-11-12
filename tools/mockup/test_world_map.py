"""Browser regression for the globe locator, using all eight real terrain fixtures.

From the repo root: python pipeline/entries.py, then python tools/mockup/test_world_map.py
Uses the installed Chromium (CHROME override supported) and cached TRMNL framework assets.
Checks every device, orientation and view; full views also cover both languages and themes.
"""
import asyncio
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import render

KEYS = ('karwendel', 'glockner', 'teton', 'lyngen', 'rwenzori', 'taveuni', 'macdonnell', 'cuillin')


def overlaps(a, b):
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


async def check_device(browser, device):
    ctx = await browser.new_context()
    page = await ctx.new_page()
    html = ''
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    async def route(r):
        path = urlparse(r.request.url).path
        if path == '/':
            return await r.fulfill(body=html, content_type='text/html')
        asset = Path(render.FW) / path.lstrip('/')
        if asset.is_file():
            return await r.fulfill(path=str(asset))
        await r.fulfill(status=404)

    await page.route('**/*', route)
    count = 0
    entries = [render.load(key) for key in KEYS]
    for entry in entries:
        assert len(json.dumps(render.rl_site.payload(entry)).encode()) <= render.rl_site.BUDGET
    for portrait in (False, True):
        w, h = render.screen_size(device, portrait)
        ratio = render.DEVICES[device]['ratio']
        await page.set_viewport_size({'width': round(w * ratio), 'height': round(h * ratio)})
        cases = [(view, 'en', False, True, True, False) for view in render.VIEWS if view != 'full']
        cases += [('full', lang, dark, True, True, False) for lang in ('en', 'de') for dark in (False, True)]
        cases += [('full', 'en', False, False, True, False), ('full', 'en', False, True, False, True)]
        for view, lang, dark, enabled, info, bar in cases:
            documents = [render.page(entry, device, view, lang, portrait, dark,
                         settings={'world_map': enabled, 'info_box': info, 'title_bar': bar}) for entry in entries]
            # Batch the real fixtures on one page, sharing the framework, fonts and drawing script.
            # Each keeps its own standard screen/view/mashup markup and geographic payload.
            bodies = [document.split('<body class="environment trmnl">', 1)[1].split('</body>', 1)[0]
                      for document in documents]
            bodies[1:] = [re.sub(r'<script>.*?</script>', '', body, flags=re.S) for body in bodies[1:]]
            html = documents[0].split('<body', 1)[0] + '<body class="environment trmnl">' + ''.join(bodies) + '</body></html>'
            await page.goto(render.ORIGIN + '/')
            await page.wait_for_function("n => document.querySelectorAll('[data-ridgelines-drawn=\"1\"]').length === n", arg=len(entries))
            results = await page.evaluate('''() => Array.from(document.querySelectorAll('[data-ridgelines]'), el => {
              const marker = el.querySelector('[data-world-marker]');
              const land = el.querySelector('[data-world-land]');
              const b = el.parentNode.querySelector('[data-ridgelines-box]');
              return {report: JSON.parse(el.dataset.ridgelinesReport),
                box: b && [b.offsetLeft, b.offsetTop, b.offsetWidth, b.offsetHeight],
                land: land && land.getAttribute('d'),
                marker: marker && [+marker.getAttribute('cx'), +marker.getAttribute('cy')]};
            })''')
            assert len(results) == len(entries)
            assert not errors, errors
            for key, result in zip(KEYS, results):
                report = result['report']
                want = enabled and view == 'full'
                assert bool(report.get('world')) == want, (key, device, portrait, view, report)
                if want:
                    r = report['world']
                    assert r['x'] >= 0 and r['y'] >= 0
                    assert r['x'] + r['w'] <= report['w'] and r['y'] + r['h'] <= report['h']
                    rectangle = [r['x'], r['y'], r['w'], r['h']]
                    assert not result['box'] or not overlaps(rectangle, result['box']), (key, device, portrait, rectangle, result['box'])
                    label = report.get('label')
                    assert not label or not overlaps(rectangle, [label[k] for k in ('x', 'y', 'w', 'h')])
                    expected = [r['x'] + r['w']/2, r['y'] + r['h']/2]
                    assert all(abs(a-b) < .001 for a,b in zip(result['marker'], expected))
                    assert result['land'] and 'NaN' not in result['land']
                count += 1
            if enabled and view == 'full':
                assert len({result['land'] for result in results}) == len(entries), 'globe does not rotate'
            print(f'{device}: portrait={portrait} {view} {lang} dark={dark} globe={enabled}, {count} renders passed', flush=True)
    await ctx.close()
    print(f'{device}: {count} renders passed', flush=True)
    return count


def check_locations():
    # Include every published range, including the real crop east of 180 degrees.
    root = Path(render.ROOT)
    count = 0
    for file in [root / 'data/beta_de_at.json', *sorted((root / 'data/release').glob('*.json'))]:
        for entry in json.loads(file.read_text())['entries']:
            location = render.rl_site.range_location(entry)
            assert math.isfinite(location['lat']) and -90 <= location['lat'] <= 90
            assert math.isfinite(location['lon']) and -180 <= location['lon'] <= 180
            assert abs((location['lon'] - entry['lon'] + 180) % 360 - 180) < 1e-9
            count += 1
    assert count > 0
    print(f'{count} published range locations passed', flush=True)


async def main():
    check_locations()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.environ.get('CHROME', '/usr/bin/chromium'))
        try:
            counts = await asyncio.gather(*(check_device(browser, d) for d in render.DEVICES))
        finally:
            await browser.close()
    print(f'{sum(counts)} real-fixture browser renders passed')


if __name__ == '__main__':
    asyncio.run(main())
