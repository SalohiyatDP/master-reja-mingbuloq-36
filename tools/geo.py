"""Geodesy helpers (pure Python, no deps).

Pipeline: Web Mercator (EPSG:3857) -> WGS84 lon/lat -> local tangent-plane
metres (ENU) centred at a chosen origin. The ENU projection gives TRUE
ground distances/areas for small areas (a few hundred metres), which is what
we need for individual land-plot master plans.
"""
import math

R_MERC = 6378137.0            # Web Mercator sphere radius
A_WGS = 6378137.0             # WGS84 semi-major axis (m)
F_WGS = 1 / 298.257223563     # WGS84 flattening
E2 = F_WGS * (2 - F_WGS)      # first eccentricity squared


def merc_to_lonlat(x, y):
    """EPSG:3857 metres -> (lon, lat) degrees."""
    lon = math.degrees(x / R_MERC)
    lat = math.degrees(2 * math.atan(math.exp(y / R_MERC)) - math.pi / 2)
    return lon, lat


def _radii(lat_deg):
    """Meridional (M) and prime-vertical (N) radii of curvature at latitude."""
    lat = math.radians(lat_deg)
    s = math.sin(lat)
    denom = 1 - E2 * s * s
    M = A_WGS * (1 - E2) / (denom ** 1.5)
    N = A_WGS / math.sqrt(denom)
    return M, N


def make_enu(lon0, lat0):
    """Return a function (lon,lat)->(east,north) metres centred at origin.

    Equirectangular tangent-plane using WGS84 curvature radii at the origin.
    Accurate to well under 1 cm for plots of this size.
    """
    M, N = _radii(lat0)
    cos_lat0 = math.cos(math.radians(lat0))

    def project(lon, lat):
        east = math.radians(lon - lon0) * N * cos_lat0
        north = math.radians(lat - lat0) * M
        return east, north

    return project


def polygon_centroid_merc(ring):
    """Area-weighted centroid of a ring given in projected (planar) coords."""
    a = 0.0
    cx = 0.0
    cy = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    a *= 0.5
    if abs(a) < 1e-12:
        # degenerate -> plain average
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / n, sum(ys) / n
    return cx / (6 * a), cy / (6 * a)


def shoelace_area(ring):
    """Absolute planar polygon area (m^2) via the shoelace formula."""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def perimeter(ring, closed=True):
    """Total edge length (m) of a ring in planar coords."""
    total = 0.0
    n = len(ring)
    m = n if closed else n - 1
    for i in range(m):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total
