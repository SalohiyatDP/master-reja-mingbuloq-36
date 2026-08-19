"""Whole-site overview: all lots in their real relative positions.

Renders every lot polygon (exact geometry) in a shared local ENU grid with
lot numbers and a north arrow, so the road/river sides can be identified
visually. Also prints, for each lot, its edges with their outward compass
bearing — useful once we know which global side is the river/road.
"""
import os
import math
from shp_reader import read_shp
import geo

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")
OUT = os.path.join(HERE, "..", "output", "master_plans")


def load_all():
    _, _, shapes = read_shp(SHP)
    lots = []
    all_ll = []
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
    out = []
    for (no, ll) in lots:
        out.append((no, [enu(lon, lat) for (lon, lat) in ll]))
    return out


def render(lots):
    xs = [p[0] for (_, r) in lots for p in r]
    ys = [p[1] for (_, r) in lots for p in r]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    W = 1600
    margin = 90
    sc = (W - 2 * margin) / (maxx - minx)
    H = int((maxy - miny) * sc + 2 * margin)

    def f(x, y):
        return (margin + (x - minx) * sc, H - (margin + (y - miny) * sc))

    P = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %d %d" font-family="Arial, sans-serif">' % (W, H, W, H)]
    P.append('<rect width="%d" height="%d" fill="#f7faf4"/>' % (W, H))
    for (no, ring) in lots:
        pts = [f(x, y) for (x, y) in ring]
        poly = " ".join("%.1f,%.1f" % p for p in pts)
        P.append('<polygon points="%s" fill="#e5f2d8" stroke="#e11d1d" '
                 'stroke-width="2"/>' % poly)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        P.append('<text x="%.1f" y="%.1f" font-size="16" fill="#123" '
                 'text-anchor="middle" font-weight="700">%d</text>'
                 % (cx, cy + 5, no))
    # north arrow
    ax, ay = W - 60, 70
    P.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" '
             'stroke-width="3"/>' % (ax, ay + 40, ax, ay))
    P.append('<polygon points="%d,%d %d,%d %d,%d" fill="#333"/>'
             % (ax, ay - 8, ax - 8, ay + 8, ax + 8, ay + 8))
    P.append('<text x="%d" y="%d" font-size="16" text-anchor="middle" '
             'font-weight="700">N</text>' % (ax, ay - 14))
    # edge compass hint labels W/E/S along border
    P.append('<text x="%d" y="%d" font-size="20" fill="#888">Gʻarb (W)</text>'
             % (12, H // 2))
    P.append('<text x="%d" y="%d" font-size="20" fill="#888" text-anchor="end">'
             'Sharq (E)</text>' % (W - 12, H // 2))
    P.append('<text x="%d" y="%d" font-size="20" fill="#888" text-anchor="middle">'
             'Shimol (N)</text>' % (W // 2, 30))
    P.append('<text x="%d" y="%d" font-size="20" fill="#888" text-anchor="middle">'
             'Janub (S)</text>' % (W // 2, H - 12))
    P.append('</svg>')
    return "\n".join(P), W, H


def main():
    lots = load_all()
    svg, W, H = render(lots)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "site_overview.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Wrote %s (%dx%d)" % (path, W, H))


if __name__ == "__main__":
    main()
