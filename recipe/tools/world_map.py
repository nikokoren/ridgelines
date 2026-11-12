"""Regenerate WORLD_LAND in recipe/shared.txt from Natural Earth public-domain 1:110m land.

Download https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson
then: python recipe/tools/world_map.py /path/to/ne_110m_land.geojson
Paste stdout into WORLD_LAND. Small islands are omitted for legibility.
Rings are clockwise, as required by d3-geo for polygons smaller than a hemisphere.
Source SHA256 checked 2026-11-12: 9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9
Licence: https://github.com/nvkelso/natural-earth-vector/blob/master/LICENSE.md
"""
import json
import math
import sys


def simplify(points, tolerance=0.35):
    """Douglas-Peucker simplification in geographic degrees."""
    if len(points) <= 2:
        return points
    a, b = points[0], points[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_squared = dx * dx + dy * dy

    def distance(point):
        t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_squared if length_squared else 0
        t = max(0, min(1, t))
        return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)

    i = max(range(1, len(points) - 1), key=lambda i: distance(points[i]))
    if distance(points[i]) > tolerance:
        return simplify(points[:i + 1], tolerance)[:-1] + simplify(points[i:], tolerance)
    return [a, b]


def world_land(features):
    rings = []
    for feature in features:
        # Only outer land rings, no political boundaries or inland water detail.
        for ring in feature['geometry']['coordinates'][:1]:
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))) / 2
            if area < 0.25:
                continue
            points = simplify(ring)
            if len(points) >= 4:
                signed = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
                if signed > 0:
                    points.reverse()
                rings.append([[[round(x, 1), round(y, 1)] for x, y in points]])
    return rings


if __name__ == '__main__':
    with open(sys.argv[1]) as source:
        print(json.dumps(world_land(json.load(source)['features']), separators=(',', ':')))
