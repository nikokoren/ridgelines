// Bundled into recipe/shared.txt between the globe projection markers.
// Regenerate with pinned build tools installed outside the checkout:
// npm install --prefix /tmp/ridgelines-globe --no-package-lock d3-geo@3.1.1 d3-array@3.2.5 esbuild@0.25.12
// NODE_PATH=/tmp/ridgelines-globe/node_modules /tmp/ridgelines-globe/node_modules/.bin/esbuild recipe/tools/globe.js --bundle --minify --format=iife --global-name=RidgelinesGlobe
// Keep the license notice from globe-LICENSE.txt with the bundled code.
import {geoProjection, geoPath} from 'd3-geo';

// Radial fisheye: enlarge the centre while keeping the hemisphere's circular rim fixed.
// At magnification 1 this is orthographic. The mapping is continuous and monotonic,
// so coastlines keep their order rather than folding or crossing over themselves.
export function createProjection(longitude, latitude, radius, magnification = 3) {
  return geoProjection((lambda, phi) => {
    const x = Math.cos(phi) * Math.sin(lambda), y = Math.sin(phi);
    const r = Math.hypot(x, y);
    const scale = magnification / (1 + (magnification - 1) * r);
    return [x * scale, y * scale];
  })
    .rotate([-longitude, -latitude])
    .translate([0, 0])
    .scale(radius)
    .clipAngle(90)
    .precision(0.25);
}

export function project(land, longitude, latitude, radius, magnification = 3) {
  const projection = createProjection(longitude, latitude, radius, magnification);
  return {path: geoPath(projection)({type: 'MultiPolygon', coordinates: land}),
    marker: projection([longitude, latitude])};
}
