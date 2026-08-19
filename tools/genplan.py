"""Whole-site GENPLAN: all 62 lots in their real positions & orientation,
with river (daryo) and road (yo'l) bands and simplified per-lot amenities.

Reuses the verified river/road orientation. Each lot keeps its EXACT boundary
(from the shapefile) in true relative position; amenities computed in the
per-lot river-up frame are rotated back into the real site orientation.
"""
import os
import math
import random
import orientation as O
from sheet import get_anchors
from master_plan import point_in_polygon, snap_inside

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "output", "master_plans")

# dusk / satellite-like palette
BG = "#0b140d"
LOT = "#24401f"
LOT_ED = "#e63030"
WATER = "#12455a"
WATER2 = "#1a5c73"
ROAD = "#5a5148"
ROAD_ED = "#d9c07a"
TREE = "#2f5a33"
WOOD = "#7a5230"
POOL = "#37b0d6"
BLD = "#8a5a30"
YURT = "#d8d2c2"
FIRE = "#ef8a34"
CAR = "#c9ccc7"
GOLD = "#e0c060"
TXT = "#eaf3e6"


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def lot_objects_global(no, ring_global):
    """Return {key: (x,y)} amenity centres in GLOBAL enu coords."""
    ringL, ri, ro = O.oriented_lot(no)             # local, river up (+y)
    xs = [p[0] for p in ringL]
    ys = [p[1] for p in ringL]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    bw, bh = (maxx - minx) or 1, (maxy - miny) or 1
    cL = (sum(xs) / len(xs), sum(ys) / len(ys))
    A = get_anchors(no)

    rd = O.river_dir_of(no)
    ang = math.atan2(rd[1], rd[0])
    rot = math.pi / 2 - ang
    # inverse rotation R(-rot) to map local river-up frame back to global
    cs, sn = math.cos(-rot), math.sin(-rot)
    Cg = (sum(p[0] for p in ring_global) / len(ring_global),
          sum(p[1] for p in ring_global) / len(ring_global))

    out = {}
    for k, (u, v) in A.items():
        p = (minx + bw * u, miny + bh * v)         # v: 0=road bottom,1=river top
        if not point_in_polygon(p, ringL):
            p = snap_inside(p, ringL, cL)
        gx = (p[0] * cs - p[1] * sn) + Cg[0]
        gy = (p[0] * sn + p[1] * cs) + Cg[1]
        out[k] = (gx, gy)
    return out


def main():
    lots = O._load_global()                        # [(no, ring_global)]
    cents = [O._centroid(r) for (_, r) in lots]
    order = O._order_chain(cents)
    rr = O.get_river_road()
    by_no = {no: r for (no, r) in lots}
    idx_of = {no: i for i, (no, _) in enumerate(lots)}

    xs = [p[0] for (_, r) in lots for p in r]
    ys = [p[1] for (_, r) in lots for p in r]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 120
    W = 2400
    sc = (W - 2 * pad) / (maxx - minx)
    H = int((maxy - miny) * sc + 2 * pad)

    def f(x, y):
        return (pad + (x - minx) * sc, H - (pad + (y - miny) * sc))

    P = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %d %d" font-family="Segoe UI, Arial, sans-serif">'
         % (W, H, W, H)]
    P.append('<rect width="%d" height="%d" fill="%s"/>' % (W, H, BG))

    # ---- river & road bands from chain-ordered frontage midpoints
    riverpts, roadpts, rdirs = [], [], []
    for i in order:
        no, ring = lots[i]
        ri, ro = rr[no]
        n = len(ring)
        riverpts.append(_mid(ring[ri], ring[(ri + 1) % n]))
        roadpts.append(_mid(ring[ro], ring[(ro + 1) % n]))
        rdirs.append(O.river_dir_of(no))

    # water polygon: river line + outward offset (toward river)
    OFF = 70.0
    outer = [(p[0] + d[0] * OFF, p[1] + d[1] * OFF)
             for p, d in zip(riverpts, rdirs)]
    water = riverpts + outer[::-1]
    wpoly = " ".join("%.1f,%.1f" % f(x, y) for (x, y) in water)
    P.append('<polygon points="%s" fill="%s"/>' % (wpoly, WATER))
    # a lighter inner water edge
    rline = " ".join("%.1f,%.1f" % f(x, y) for (x, y) in riverpts)
    P.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3" '
             'opacity=".6"/>' % (rline, WATER2))

    # road band: road line offset outward (away from river = -rd)
    road_outer = [(p[0] - d[0] * 55, p[1] - d[1] * 55)
                  for p, d in zip(roadpts, rdirs)]
    rpoly = " ".join("%.1f,%.1f" % f(x, y) for (x, y) in
                     (roadpts + road_outer[::-1]))
    P.append('<polygon points="%s" fill="%s"/>' % (rpoly, ROAD))
    rdline = " ".join("%.1f,%.1f" % f(x, y) for (x, y) in roadpts)
    P.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5" '
             'stroke-dasharray="10 8" opacity=".7"/>' % (rdline, ROAD_ED))

    # ---- each lot
    for (no, ring) in lots:
        pts = [f(*p) for p in ring]
        poly = " ".join("%.1f,%.1f" % p for p in pts)
        P.append('<polygon points="%s" fill="%s"/>' % (poly, LOT))
        # clip amenities to the lot
        cid = "c%d" % no
        P.append('<clipPath id="%s"><polygon points="%s"/></clipPath>'
                 % (cid, poly))
        P.append('<g clip-path="url(#%s)">' % cid)

        obj = lot_objects_global(no, ring)
        # trees scattered
        random.seed(no)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        for _ in range(10):
            tx = cx + random.uniform(-1, 1) * (max(p[0] for p in pts) - cx)
            ty = cy + random.uniform(-1, 1) * (max(p[1] for p in pts) - cy)
            P.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                     % (tx, ty, random.uniform(2.5, 4.5), TREE))

        def g(k):
            return f(*obj[k])

        # terrace (11) small wood strip
        x, y = g(11)
        P.append('<rect x="%.1f" y="%.1f" width="26" height="7" rx="2" '
                 'fill="%s"/>' % (x - 13, y - 3, WOOD))
        # pool (4)
        x, y = g(4)
        P.append('<rect x="%.1f" y="%.1f" width="18" height="10" rx="3" '
                 'fill="%s"/>' % (x - 9, y - 5, POOL))
        # yurts (5)
        x, y = g(5)
        for dx in (-7, 7):
            P.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>'
                     % (x + dx, y, YURT))
        # fire (6)
        x, y = g(6)
        P.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="#2a2018"/>' % (x, y))
        P.append('<circle cx="%.1f" cy="%.1f" r="2.2" fill="%s"/>' % (x, y, FIRE))
        # kitchens 7,8
        for k in (7, 8):
            x, y = g(k)
            P.append('<rect x="%.1f" y="%.1f" width="12" height="9" rx="1.5" '
                     'fill="%s"/>' % (x - 6, y - 4.5, BLD))
        # tapchan 3
        x, y = g(3)
        P.append('<rect x="%.1f" y="%.1f" width="9" height="8" rx="1.5" '
                 'fill="%s"/>' % (x - 4.5, y - 4, WOOD))
        # basketball 9
        x, y = g(9)
        P.append('<rect x="%.1f" y="%.1f" width="12" height="8" fill="#b5652a"/>'
                 % (x - 6, y - 4))
        # parking 1 + cars
        x, y = g(1)
        P.append('<rect x="%.1f" y="%.1f" width="16" height="14" rx="2" '
                 'fill="#3a3f3c"/>' % (x - 8, y - 7))
        for j in range(3):
            P.append('<rect x="%.1f" y="%.1f" width="4" height="7" fill="%s"/>'
                     % (x - 7 + j * 5, y - 3, CAR))
        # toilet 2
        x, y = g(2)
        P.append('<rect x="%.1f" y="%.1f" width="6" height="5" fill="#7d6b8e"/>'
                 % (x - 3, y - 2.5))
        P.append('</g>')
        # red boundary + number
        P.append('<polygon points="%s" fill="none" stroke="%s" '
                 'stroke-width="2"/>' % (poly, LOT_ED))
        P.append('<text x="%.1f" y="%.1f" font-size="13" fill="%s" '
                 'text-anchor="middle" font-weight="700">%d</text>'
                 % (cx, cy + 4, "#fff", no))

    # ---- labels: DARYO / YO'L along the bands
    def bandlabel(ptsrc, text, col):
        mid = ptsrc[len(ptsrc) // 2]
        fx, fy = f(*mid)
        P.append('<text x="%.1f" y="%.1f" font-size="30" fill="%s" '
                 'letter-spacing="6" text-anchor="middle" font-weight="700" '
                 'opacity=".85">%s</text>' % (fx, fy, col, text))
    bandlabel(outer, "DARYO", "#9fd8e6")
    bandlabel(road_outer, "YOʻL", ROAD_ED)

    # north arrow
    ax, ay = W - 90, 110
    P.append('<g transform="translate(%d,%d)">'
             '<polygon points="0,-40 11,0 0,10 -11,0" fill="#eaf3e6"/>'
             '<polygon points="0,40 11,0 0,-10 -11,0" fill="#5c7565"/>'
             '<text x="0" y="-48" font-size="22" fill="%s" text-anchor="middle" '
             'font-weight="700">N</text></g>' % (ax, ay, TXT))

    # scale bar (500 m)
    bar = 500 * sc
    bx, by = 120, H - 60
    P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
             'stroke-width="4"/>' % (bx, by, bx + bar, by, TXT))
    P.append('<text x="%.1f" y="%.1f" font-size="18" fill="%s">500 m</text>'
             % (bx, by - 10, TXT))

    # title block
    P.append('<rect x="%d" y="%d" width="560" height="150" rx="12" '
             'fill="#0f1c14" stroke="#2b4a30"/>' % (60, 60))
    P.append('<text x="%d" y="%d" font-size="30" fill="%s" font-weight="800">'
             'MINGBULOQ c-36 — BOSH REJA (GENPLAN)</text>' % (86, 108, TXT))
    P.append('<text x="%d" y="%d" font-size="18" fill="%s">62 ta lot · dam olish '
             'zonasi · umumiy maydon ~17.4 ga</text>' % (86, 140, "#a9c3ad"))
    P.append('<text x="%d" y="%d" font-size="15" fill="%s">Daryo bo‘yi terasa, '
             'basseyn, o‘tovlar, oshxonalar, avtoturargoh (yo‘l tomonda)</text>'
             % (86, 170, "#8fb595"))
    P.append('<text x="%d" y="%d" font-size="13" fill="%s">Lot chegaralari '
             'shapefile‘dan aynan olingan (1:1)</text>' % (86, 194, "#6f8f74"))

    P.append('</svg>')

    path = os.path.join(OUT, "genplan.svg")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(P))
    print("Wrote %s (%dx%d)" % (path, W, H))


if __name__ == "__main__":
    main()
