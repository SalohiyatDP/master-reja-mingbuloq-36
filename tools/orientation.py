"""Per-lot river/road orientation from the ribbon geometry (robust).

Ground truth (from the PDF/satellite): the lots form one continuous ribbon;
the RIVER (daryo, cyan reference line) runs along the north/water side, the
ROAD (yo'l, yellow reference line) along the opposite side.

Method (no fragile per-lot guessing):
  1. Order all lots into a chain along the ribbon (greedy nearest-neighbour
     starting from the leftmost lot).
  2. Tangent at each lot = direction to the next chain lot minus the previous
     -> consistently oriented along the walk (no sign flips at bends).
  3. river_dir = left-normal of the tangent, with ONE global sign chosen so the
     river points to the north/water side at the start.
  4. River frontage = the along-ribbon frontage edge on the river_dir side;
     road frontage = the one on the opposite side.

`oriented_lot(lot_no)` rotates the lot so the river side is up (DARYO),
road side down (YO'L).
"""
import math
import os
from shp_reader import read_shp
import geo
from master_plan import load_lot_metres

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")

_rr_cache = None      # {lot_no: (river_idx, road_idx)}
_dir_cache = None     # {lot_no: (rx, ry)} unit vector toward river


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


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _order_chain(cents):
    """Greedy nearest-neighbour chain starting from the leftmost lot."""
    n = len(cents)
    start = min(range(n), key=lambda i: cents[i][0])
    order = [start]
    used = {start}
    while len(order) < n:
        c = cents[order[-1]]
        nxt = min((i for i in range(n) if i not in used),
                  key=lambda i: _dist(c, cents[i]))
        order.append(nxt)
        used.add(nxt)
    return order


def _compute():
    global _rr_cache, _dir_cache
    if _rr_cache is not None:
        return
    lots = _load_global()
    cents = [_centroid(r) for (_, r) in lots]
    order = _order_chain(cents)
    pos = {idx: k for k, idx in enumerate(order)}   # lot list-index -> chain pos
    n = len(lots)

    # tangent per lot (consistent along the walk)
    tang = [None] * n
    for k, idx in enumerate(order):
        p = order[k - 1] if k > 0 else idx
        q = order[k + 1] if k < n - 1 else idx
        tx, ty = cents[q][0] - cents[p][0], cents[q][1] - cents[p][1]
        m = math.hypot(tx, ty) or 1.0
        tang[idx] = (tx / m, ty / m)

    # river_dir = left normal; global sign so it points north (+y) at the start
    river_dir = [(-t[1], t[0]) for t in tang]
    # anchor using the first 5 chain lots' average north component
    north = sum(river_dir[order[k]][1] for k in range(min(5, n)))
    sign = 1.0 if north >= 0 else -1.0
    river_dir = [(sign * d[0], sign * d[1]) for d in river_dir]

    rr, dirc = {}, {}
    for i, (no, ring) in enumerate(lots):
        rd = river_dir[i]
        c = cents[i]
        m = len(ring)
        # frontage = edge whose OUTWARD normal best aligns with river_dir
        # (river) / against it (road). Long neighbour edges have normals ~perp
        # to river_dir, so they score ~0 and are naturally excluded.
        aligns = []
        for k in range(m):
            a, b = ring[k], ring[(k + 1) % m]
            ex, ey = b[0] - a[0], b[1] - a[1]
            nl = math.hypot(ex, ey) or 1e-9
            nx, ny = ey / nl, -ex / nl               # a normal
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            if (mx - c[0]) * nx + (my - c[1]) * ny < 0:   # make it outward
                nx, ny = -nx, -ny
            aligns.append(nx * rd[0] + ny * rd[1])   # +1 = faces river
        river_idx = max(range(m), key=lambda k: aligns[k])
        road_idx = min(range(m), key=lambda k: aligns[k])
        rr[no] = (river_idx, road_idx)
        dirc[no] = rd
    _rr_cache, _dir_cache = rr, dirc


def _elen(ring, k):
    a, b = ring[k], ring[(k + 1) % len(ring)]
    return math.hypot(b[0] - a[0], b[1] - a[1])


def get_river_road():
    _compute()
    return _rr_cache


def river_dir_of(lot_no):
    _compute()
    return _dir_cache[lot_no]


def oriented_lot(lot_no):
    """Local-metre ring rotated so the RIVER side points up (+y)."""
    ring = load_lot_metres(lot_no)
    rx, ry = river_dir_of(lot_no)
    ang = math.atan2(ry, rx)
    rot = math.pi / 2 - ang
    cs, sn = math.cos(rot), math.sin(rot)
    c = _centroid(ring)
    out = [((x - c[0]) * cs - (y - c[1]) * sn,
            (x - c[0]) * sn + (y - c[1]) * cs) for (x, y) in ring]
    river_idx, road_idx = get_river_road()[lot_no]
    return out, river_idx, road_idx


if __name__ == "__main__":
    rr = get_river_road()
    for no in sorted(rr):
        ring, ri, ro = oriented_lot(no)
        n = len(ring)
        tops = max(range(n), key=lambda k: (ring[k][1] + ring[(k + 1) % n][1]) / 2)
        bots = min(range(n), key=lambda k: (ring[k][1] + ring[(k + 1) % n][1]) / 2)
        if no in (1, 17, 18, 31, 33, 49, 61):
            print("Lot %2d: river edge=%.1fm road edge=%.1fm | top=%.1f bot=%.1f"
                  % (no, _elen(ring, ri), _elen(ring, ro),
                     _elen(ring, tops), _elen(ring, bots)))
