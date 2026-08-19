"""Per-lot river/road orientation, derived from the strip geometry.

User confirmed: BLUE side = river (daryo), ORANGE side = road (yo'l).
For each lot the two shortest edges are the river/road frontages. Using the
band direction (increasing lot number, gap-aware), the frontage on the blue
side (higher cross product) is the river; the other is the road.

`oriented_lot(lot_no)` returns the lot ring in local metres, rotated so the
river frontage is at the TOP and the road frontage at the BOTTOM, plus the
(river_idx, road_idx) edge indices (rotation preserves vertex order).
"""
import math
import os
from shp_reader import read_shp
import geo
from master_plan import load_lot_metres

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")

_rr_cache = None
_band_cache = None


def _load_global():
    _, _, shapes = read_shp(SHP)
    lots, all_ll = [], []
    for i, g in enumerate(shapes):
        if not g["parts"]:
            continue
        ring = g["parts"][0]
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        ll = [geo.merc_to_lonlat(x, y) for (x, y) in ring]
        all_ll.extend(ll)
        lots.append((i + 1, ll))
    lon0 = sum(p[0] for p in all_ll) / len(all_ll)
    lat0 = sum(p[1] for p in all_ll) / len(all_ll)
    enu = geo.make_enu(lon0, lat0)
    return [(no, [enu(lo, la) for (lo, la) in ll]) for (no, ll) in lots]


def _centroid(r):
    return (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r))


def _adj(a, b, c):
    return math.hypot(c[a][0] - c[b][0], c[a][1] - c[b][1])


def _band_dir(i, cents, med):
    n = len(cents)
    prev = i - 1 if i - 1 >= 0 else None
    nxt = i + 1 if i + 1 < n else None
    if prev is not None and _adj(i, prev, cents) > 3 * med:
        prev = None
    if nxt is not None and _adj(i, nxt, cents) > 3 * med:
        nxt = None
    if prev is not None and nxt is not None:
        a, b = cents[prev], cents[nxt]
    elif nxt is not None:
        a, b = cents[i], cents[nxt]
    elif prev is not None:
        a, b = cents[prev], cents[i]
    else:
        return 1.0, 0.0
    vx, vy = b[0] - a[0], b[1] - a[1]
    m = math.hypot(vx, vy) or 1.0
    return vx / m, vy / m


def _compute():
    """Populate band-direction and river/road-edge caches for all lots."""
    global _rr_cache, _band_cache
    if _rr_cache is not None:
        return
    lots = _load_global()
    cents = [_centroid(r) for (_, r) in lots]
    adj = [_adj(i, i + 1, cents) for i in range(len(cents) - 1)]
    sa = sorted(adj)
    med = sa[len(sa) // 2] if sa else 1.0

    rr, band = {}, {}
    for i, (no, ring) in enumerate(lots):
        bx, by = _band_dir(i, cents, med)
        band[no] = (bx, by)
        c = cents[i]
        n = len(ring)
        # frontage edges run ALONG the strip: edge direction ~parallel to band.
        # score each edge by |edgeDir . band| (parallel) and its length.
        scored = []
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            ex, ey = b[0] - a[0], b[1] - a[1]
            el = math.hypot(ex, ey) or 1e-9
            paral = abs((ex * bx + ey * by) / el)     # 1 = along band
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            cross = bx * (my - c[1]) - by * (mx - c[0])  # >0 = blue/river side
            scored.append((paral * el, cross, k, el))
        # river = strongest along-band edge on blue side; road = on orange side
        blue = [s for s in scored if s[1] > 0]
        orange = [s for s in scored if s[1] <= 0]
        river_idx = max(blue, key=lambda s: s[0])[2] if blue else \
            max(scored, key=lambda s: s[0])[2]
        road_idx = max(orange, key=lambda s: s[0])[2] if orange else \
            min(scored, key=lambda s: s[1])[2]
        rr[no] = (river_idx, road_idx)
    _rr_cache, _band_cache = rr, band


def get_river_road():
    """Return {lot_no: (river_edge_idx, road_edge_idx)} in ring vertex order."""
    _compute()
    return _rr_cache


def band_of(lot_no):
    _compute()
    return _band_cache[lot_no]


def oriented_lot(lot_no):
    """Local-metre ring rotated so the RIVER side points up (+y).

    Uses the band-perpendicular direction (robust to extra/tiny vertices):
    river direction in ENU = left-normal of the band direction = (-by, bx).
    """
    ring = load_lot_metres(lot_no)
    bx, by = band_of(lot_no)
    river_dir = (-by, bx)
    ang = math.atan2(river_dir[1], river_dir[0])
    rot = math.pi / 2 - ang            # point river direction straight up
    cs, sn = math.cos(rot), math.sin(rot)
    c = _centroid(ring)
    out = []
    for (x, y) in ring:
        dx, dy = x - c[0], y - c[1]
        out.append((dx * cs - dy * sn, dx * sn + dy * cs))
    river_idx, road_idx = get_river_road()[lot_no]
    return out, river_idx, road_idx


if __name__ == "__main__":
    rr = get_river_road()
    for no in list(rr):
        ring, ri, ro = oriented_lot(no)
        n = len(ring)
        ys = [p[1] for p in ring]
        # topmost & bottommost edge midpoints -> should be river / road
        tops = max(range(n), key=lambda k: (ring[k][1] + ring[(k + 1) % n][1]) / 2)
        bots = min(range(n), key=lambda k: (ring[k][1] + ring[(k + 1) % n][1]) / 2)

        def elen(k):
            a, b = ring[k], ring[(k + 1) % n]
            return math.hypot(b[0] - a[0], b[1] - a[1])
        if no <= 8 or no % 15 == 0:
            print("Lot %2d: top(daryo)=%.1fm  bottom(yo'l)=%.1fm"
                  % (no, elen(tops), elen(bots)))
