"""Analyze the plots: check attributes and compute TRUE geodesic areas.

The shapefile is in WGS84 Web Mercator (EPSG:3857), whose area is heavily
distorted away from the equator. We unproject each vertex to lon/lat and
compute the geodesic area on the WGS84 ellipsoid for correct m^2 values.
"""
import math
from shp_reader import read_shp, read_dbf, polygon_area
import os

BASE = os.path.join(os.path.dirname(__file__), "..", "shp", "migbuloq_wgs84")
R = 6378137.0  # web mercator sphere radius / WGS84 semi-major
A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)


def merc_to_lonlat(x, y):
    lon = math.degrees(x / R)
    lat = math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    return lon, lat


def geodesic_area(ring_lonlat):
    """Geodesic polygon area on WGS84 ellipsoid (m^2), abs value.
    Uses the standard authalic/ellipsoidal approximation."""
    if len(ring_lonlat) < 3:
        return 0.0
    total = 0.0
    n = len(ring_lonlat)
    for i in range(n):
        lon1, lat1 = ring_lonlat[i]
        lon2, lat2 = ring_lonlat[(i + 1) % n]
        total += math.radians(lon2 - lon1) * (
            2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2))
        )
    area = total * A * A / 2.0
    return abs(area)


fst, bbox, shapes = read_shp(BASE + ".shp")
fields, records = read_dbf(BASE + ".dbf")

# Attribute completeness
non_empty = {f: 0 for f in fields}
for r in records:
    for f in fields:
        if r.get(f) not in (None, "", "0"):
            non_empty[f] += 1

print("=== ATTRIBUTES ===")
print("Total records:", len(records))
for f in fields:
    print("  '%s': %d/%d non-empty" % (f, non_empty[f], len(records)))

print()
print("=== AREAS (Web Mercator vs TRUE geodesic) ===")
total_merc = 0.0
total_true = 0.0
rows = []
for i, g in enumerate(shapes):
    if not g["parts"]:
        continue
    merc = polygon_area(g)
    # true area: outer rings positive, holes subtract (by signed sum)
    true = 0.0
    for ring in g["parts"]:
        ll = [merc_to_lonlat(x, y) for (x, y) in ring]
        true += geodesic_area(ll)
    total_merc += merc
    total_true += true
    rows.append((i + 1, merc, true, len(g["parts"][0])))

for (idx, merc, true, npts) in rows:
    print("  lot %2d: mercator=%8.1f m^2 | TRUE=%8.1f m^2 (%.2f sotix) pts=%d"
          % (idx, merc, true, true / 100.0, npts))

print()
print("Distortion factor (true/merc): %.4f" % (total_true / total_merc))
print("TOTAL true area: %.1f m^2  =  %.2f ga  =  %.1f sotix"
      % (total_true, total_true / 10000.0, total_true / 100.0))
