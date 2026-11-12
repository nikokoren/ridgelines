// Projection regression using every real published location, no terrain build required.
// Run from any directory: node recipe/tools/test_globe.mjs
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const shared = fs.readFileSync(path.join(root, 'recipe/shared.txt'), 'utf8');
const land = JSON.parse(shared.match(/var WORLD_LAND = (.*);/)[1]);
const bundle = shared.split('// BEGIN bundled globe projection')[1].split('// END bundled globe projection.')[0];
// Drop the version label on the marker line, leaving the licence and JavaScript intact.
const context = {};
vm.runInNewContext(bundle.slice(bundle.indexOf('\n')), context);
const files = ['data/beta_de_at.json', ...fs.readdirSync(path.join(root, 'data/release')).filter(f => f.endsWith('.json')).map(f => 'data/release/' + f)];
const silhouettes = new Set();
let count = 0;
const locations = [];
for (const file of files) {
  for (const entry of JSON.parse(fs.readFileSync(path.join(root, file), 'utf8')).entries) {
    const lon = ((entry.lon + 180) % 360 + 360) % 360 - 180;
    locations.push([lon, entry.lat]);
    const result = context.RidgelinesGlobe.project(land, lon, entry.lat, 37);
    assert.ok(result.path && !/NaN|Infinity/.test(result.path), entry.id);
    assert.ok(Math.hypot(...result.marker) < 1e-9, entry.id + ': location is not centred');
    // Every SVG coordinate must remain within the visible hemisphere's bounding square.
    const coordinates = result.path.match(/-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi).map(Number);
    assert.ok(coordinates.every(n => Number.isFinite(n) && Math.abs(n) <= 37.01), entry.id + ': invalid hemisphere clipping');
    silhouettes.add(result.path);
    count++;
  }
}
assert.ok(count > 0 && silhouettes.size > count / 2, 'globe does not rotate with location');
console.log(`${count} locations centred and clipped correctly; ${silhouettes.size} distinct globe silhouettes`);

// Use real neighbouring ranges to check that the centre is magnified, while all
// real front-hemisphere locations keep their direction and stay inside the rim.
const [lon0, lat0] = locations[0];
const normal = context.RidgelinesGlobe.createProjection(lon0, lat0, 37, 1);
const focused = context.RidgelinesGlobe.createProjection(lon0, lat0, 37);
const radians = Math.PI / 180;
let nearby = 0, visible = 0;
for (const location of locations) {
  const [lon, lat] = location;
  const facing = Math.sin(lat0*radians)*Math.sin(lat*radians) + Math.cos(lat0*radians)*Math.cos(lat*radians)*Math.cos((lon-lon0)*radians);
  if (facing <= 0) continue;
  const a = normal(location), b = focused(location);
  const ra = Math.hypot(...a), rb = Math.hypot(...b);
  assert.ok(rb >= ra - 1e-9 && rb <= 37 + 1e-9, 'focus escapes or shrinks the globe');
  assert.ok(Math.abs(a[0]*b[1] - a[1]*b[0]) < 1e-9, 'focus folds the geography');
  if (ra > .01 && ra < 1) {
    assert.ok(rb / ra > 2.8, 'nearby geography was not magnified');
    nearby++;
  }
  visible++;
}
assert.ok(nearby > 0 && visible > 0);
console.log(`${visible} real visible locations preserve direction and bounds; ${nearby} nearby locations magnified by over 2.8x`);
