"""Colour the two long sides of every lot consistently (left vs right of the
band direction) so the user can tell us which side is the river.

Band direction at each lot is estimated from its two nearest neighbours. For
each edge we take the sign of cross(bandDir, midpoint-centroid): one sign =
BLUE side, the other = ORANGE side. The result is globally consistent along
the strip, so a single answer ("blue = river") orients all 62 lots.
"""
import os
import math
from shp_reader import read_shp
import geo

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")
OUT = os.path.join(HERE, "..", "output", "master_plans")

BLUE = "#1f7ae0"
ORANGE = "#f08a24"


def load_all():
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


def centroid(ring):
    return (sum(p[0] for p in ring) / len(ring),
            sum(p[1] for p in ring) / len(ring))


def _adj(a, b, cents):
    return math.hypot(cents[a][0] - cents[b][0], cents[a][1] - cents[b][1])


def band_dir(idx, cents, med):
    """Forward direction = increasing lot number (list is in number order),
    ignoring neighbours across a group gap (dist > 3x median)."""
    n = len(cents)
    prev = idx - 1 if idx - 1 >= 0 else None
    nxt = idx + 1 if idx + 1 < n else None
    if prev is not None and _adj(idx, prev, cents) > 3 * med:
        prev = None
    if nxt is not None and _adj(idx, nxt, cents) > 3 * med:
        nxt = None
    if prev is not None and nxt is not None:
        a, b = cents[prev], cents[nxt]
    elif nxt is not None:
        a, b = cents[idx], cents[nxt]
    elif prev is not None:
        a, b = cents[prev], cents[idx]
    else:
        return 1.0, 0.0
    vx, vy = b[0] - a[0], b[1] - a[1]
    m = math.hypot(vx, vy) or 1.0
    return vx / m, vy / m


def render(lots):
    cents = [centroid(r) for (_, r) in lots]
    xs = [p[0] for (_, r) in lots for p in r]
    ys = [p[1] for (_, r) in lots for p in r]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    W, margin = 1700, 90
    sc = (W - 2 * margin) / (maxx - minx)
    H = int((maxy - miny) * sc + 2 * margin)

    def f(x, y):
        return (margin + (x - minx) * sc, H - (margin + (y - miny) * sc))

    P = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %d %d" font-family="Arial, sans-serif">' % (W, H, W, H)]
    P.append('<rect width="%d" height="%d" fill="#f7faf4"/>' % (W, H))

    # median adjacent (number-order) spacing, ignoring big group gaps
    adj = [_adj(i, i + 1, cents) for i in range(len(cents) - 1)]
    sa = sorted(adj)
    med = sa[len(sa) // 2] if sa else 1.0

    for i, (no, ring) in enumerate(lots):
        bx, by = band_dir(i, cents, med)
        c = cents[i]
        pts = [f(x, y) for (x, y) in ring]
        poly = " ".join("%.1f,%.1f" % p for p in pts)
        P.append('<polygon points="%s" fill="#eef6e4" stroke="#999" '
                 'stroke-width="1"/>' % poly)
        n = len(ring)
        # rank edges by length; the 2 SHORTEST = river/road frontages
        # (long edges are shared with neighbours along the strip)
        elens = [math.hypot(ring[(k + 1) % n][0] - ring[k][0],
                            ring[(k + 1) % n][1] - ring[k][1]) for k in range(n)]
        short2 = set(sorted(range(n), key=lambda k: elens[k])[:2])
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            fa, fb = f(*a), f(*b)
            if k in short2:
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                cross = bx * (my - c[1]) - by * (mx - c[0])
                col = BLUE if cross > 0 else ORANGE
                P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                         'stroke="%s" stroke-width="6" stroke-linecap="round"/>'
                         % (fa[0], fa[1], fb[0], fb[1], col))
            else:
                P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                         'stroke="#bbb" stroke-width="1.5"/>'
                         % (fa[0], fa[1], fb[0], fb[1]))
        cf = f(*c)
        P.append('<text x="%.1f" y="%.1f" font-size="14" fill="#123" '
                 'text-anchor="middle" font-weight="700">%d</text>'
                 % (cf[0], cf[1] + 4, no))

    # legend
    P.append('<rect x="20" y="20" width="330" height="86" rx="8" fill="#fff" '
             'stroke="#ccc"/>')
    P.append('<line x1="40" y1="50" x2="90" y2="50" stroke="%s" '
             'stroke-width="6"/>' % BLUE)
    P.append('<text x="102" y="55" font-size="18" fill="#123">KOʻK tomon</text>')
    P.append('<line x1="40" y1="82" x2="90" y2="82" stroke="%s" '
             'stroke-width="6"/>' % ORANGE)
    P.append('<text x="102" y="87" font-size="18" fill="#123">SARIQ tomon</text>')
    # north
    ax, ay = W - 60, 70
    P.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" '
             'stroke-width="3"/>' % (ax, ay + 40, ax, ay))
    P.append('<polygon points="%d,%d %d,%d %d,%d" fill="#333"/>'
             % (ax, ay - 8, ax - 8, ay + 8, ax + 8, ay + 8))
    P.append('<text x="%d" y="%d" font-size="16" text-anchor="middle" '
             'font-weight="700">N</text>' % (ax, ay - 14))
    P.append('</svg>')
    return "\n".join(P), W, H


def main():
    lots = load_all()
    svg, W, H = render(lots)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "site_sides.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote %s (%dx%d)" % (path, W, H))


if __name__ == "__main__":
    main()
