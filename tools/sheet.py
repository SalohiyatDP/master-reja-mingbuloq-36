"""Dark-theme presentation master-plan SHEET for a single lot (vector SVG).

Reproduces the composition of a professional concept sheet:
  - big plan panel (dark, stylised amenities, exact red boundary + dims)
  - corner markers P1..Pn, DARYO / YO'L edge labels, north compass
  - EKSPLIKATSIYA (numbered legend), O'LCHAMLAR, YO'LAKLAR panels
  - 3D KO'RINISHLAR placeholder tiles (to be filled by an image AI)

The lot boundary is taken EXACTLY from the shapefile; only the interior
illustration is stylised. Not photorealistic (no image engine here) — but the
geometry, dimensions and layout are precise and print-ready.
"""
import os
import sys
import math
from shp_reader import read_shp
import geo
from master_plan import load_lot_metres, point_in_polygon, snap_inside
import orientation

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "output", "master_plans")

# palette
BG = "#10201a"
PANEL = "#16241d"
PANEL2 = "#1d2f26"
LINE = "#2c4034"
GRASS = "#243d2a"
GRASS2 = "#2c4a32"
TEXT = "#e7f0e6"
MUTE = "#9fb3a3"
GOLD = "#d9b25f"
RED = "#e63030"
WATER = "#123a44"

LEGEND = [
    (1, "Avtoturargoh (kirish qismi)"),
    (2, "Hojatxona"),
    (3, "Tapchan"),
    (4, "Basseyn"),
    (5, "O‘tovlar (2–3 ta)"),
    (6, "O‘choq / dam olish zonasi"),
    (7, "Yozgi oshxona"),
    (8, "Qishki oshxona"),
    (9, "Basketbol maydonchasi"),
    (10, "Katta yashil hudud"),
    (11, "Daryo bo‘yida terasa"),
]

# normalized anchors: u across daryo-width (0..1), v from yo'l(0) -> daryo(1)
ANCHORS = {
    1: (0.16, 0.12),   # parking near road
    2: (0.07, 0.88),   # toilet, edge
    3: (0.22, 0.80),   # tapchan
    4: (0.34, 0.62),   # pool
    5: (0.64, 0.70),   # yurts
    6: (0.50, 0.50),   # fire pit
    7: (0.74, 0.44),   # summer kitchen
    8: (0.62, 0.26),   # winter kitchen
    9: (0.80, 0.18),   # basketball
    10: (0.42, 0.30),  # green (large)
    11: (0.50, 0.93),  # river terrace
}


# ------------------------------------------------------------ orientation

def orient_daryo_up(ring):
    """Rotate so the shortest 'river' edge sits horizontally on top.

    We pick the edge whose midpoint is farthest in one direction as 'daryo'.
    For lot 1 this yields the 44 m edge on top (matches the reference sheet).
    Returns (oriented_ring, corner_order) with P1..Pn starting top-left, CW.
    """
    n = len(ring)
    # choose river edge = the edge most aligned 'up' after we try each as top.
    # Simpler: pick the edge that, when placed on top, puts the whole polygon
    # below it AND is among the two shorter edges (rivers here are short sides).
    best = None
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        rot = -ang
        c, s = math.cos(rot), math.sin(rot)
        R = [(c * (x - a[0]) - s * (y - a[1]),
              s * (x - a[0]) + c * (y - a[1])) for (x, y) in ring]
        cy = sum(p[1] for p in R) / n
        # want polygon below the top edge -> centroid y < 0
        score = (length, cy)
        if cy < -1:  # polygon lies below this horizontal edge
            if best is None or length < best[0][0]:
                best = (score, i, R)
    if best is None:
        return ring, list(range(n))
    _, i0, R = best
    # normalise so top edge is at y=0 and plot below (positive downward later)
    # reorder starting at i0 (top-left)
    order = [(i0 + k) % n for k in range(n)]
    oriented = [R[k] for k in order]
    return oriented, order


# ------------------------------------------------------------ svg helpers

def T(pts, box, pad):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx
    h = maxy - miny
    bx, by, bw, bh = box
    sc = min((bw - 2 * pad) / w, (bh - 2 * pad) / h)
    ox = bx + (bw - w * sc) / 2 - minx * sc
    oy = by + (bh - h * sc) / 2 - miny * sc

    def f(x, y):
        # flip Y so 'up' (daryo) renders at the top of the panel
        return (ox + x * sc, by + bh - (oy + y * sc - by))
    return f, sc


def tree(cx, cy, r):
    return ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#1f3a26"/>'
            '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#2f5636"/>'
            '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#3f7048" opacity=".7"/>'
            % (cx, cy, r, cx - r * .15, cy - r * .15, r * .7,
               cx - r * .3, cy - r * .3, r * .35))


# ------------------------------------------------------------ main render

def build_sheet(lot_no):
    ring, river_idx, road_idx = orientation.oriented_lot(lot_no)
    area = geo.shoelace_area(ring)
    perim = geo.perimeter(ring, closed=True)
    n = len(ring)

    # side lengths (oriented order): edge0 = top(daryo), last = bottom-ish
    sides = []
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        sides.append(math.hypot(b[0] - a[0], b[1] - a[1]))

    W, Hh = 1440, 1000
    plan_box = (24, 24, 860, 700)
    pad = 74
    f, sc = T(ring, plan_box, pad)

    xs = [f(*p)[0] for p in ring]
    ys = [f(*p)[1] for p in ring]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    bw, bh = maxx - minx, maxy - miny
    cx = sum(xs) / n
    cy = sum(ys) / n

    def uv(u, v):
        return (minx + bw * u, maxy - bh * v)  # v up

    P = []
    P.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
             'font-family="Segoe UI, Arial, sans-serif">' % (W, Hh))
    P.append('<rect width="%d" height="%d" fill="%s"/>' % (W, Hh, BG))

    poly = " ".join("%.1f,%.1f" % (x, y) for (x, y) in zip(xs, ys))
    # plan backdrop
    P.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" rx="10"/>'
             % (plan_box[0], plan_box[1], plan_box[2], plan_box[3], "#0c1712"))
    # water strip above daryo edge
    P.append('<rect x="%d" y="%d" width="%d" height="%.0f" fill="%s"/>'
             % (plan_box[0], plan_box[1], plan_box[2], miny - plan_box[1] + 6, WATER))
    P.append('<clipPath id="lot"><polygon points="%s"/></clipPath>' % poly)
    # grass fill inside lot
    P.append('<polygon points="%s" fill="%s"/>' % (poly, GRASS))
    P.append('<g clip-path="url(#lot)">')

    # scatter trees along the inside border & green zone
    import random
    random.seed(lot_no)
    for _ in range(70):
        u, v = random.random(), random.random()
        px, py = uv(u, v)
        edge = min(u, 1 - u, v, 1 - v)
        if edge < 0.16 or random.random() < 0.25:
            P.append(tree(px, py, random.uniform(4, 9)))

    def anchor(i):
        u, v = ANCHORS[i]
        p = uv(u, v)
        # keep inside
        mp = ((minx + maxx) / 2, (miny + maxy) / 2)
        # rough inside check in screen space vs polygon
        return p

    # paths: smooth beige links from a central spine
    spine = anchor(6)
    for i in ANCHORS:
        px, py = anchor(i)
        P.append('<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" stroke="#b9a06a" '
                 'stroke-width="4.5" fill="none" opacity=".55" '
                 'stroke-linecap="round"/>'
                 % (spine[0], spine[1], (spine[0] + px) / 2 + 12,
                    (spine[1] + py) / 2, px, py))

    # ---- objects
    # 11 terrace along daryo (top)
    tx, ty = anchor(11)
    P.append('<rect x="%.1f" y="%.1f" width="%.1f" height="18" fill="#5b4028" '
             'rx="3"/>' % (minx + bw * 0.12, miny - 4, bw * 0.76))
    for k in range(14):
        xx = minx + bw * 0.12 + k * (bw * 0.76 / 14)
        P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3c2a19" '
                 'stroke-width="1.5"/>' % (xx, miny - 4, xx, miny + 14))

    # 1 parking + cars
    px, py = anchor(1)
    P.append('<rect x="%.1f" y="%.1f" width="70" height="70" fill="#3a3f3c" '
             'rx="4"/>' % (px - 35, py - 35))
    for k in range(4):
        P.append('<rect x="%.1f" y="%.1f" width="20" height="34" rx="3" '
                 'fill="#c9ccc7"/>' % (px - 30 + k * 16, py - 17))

    # 4 pool
    px, py = anchor(4)
    P.append('<rect x="%.1f" y="%.1f" width="74" height="40" rx="8" '
             'fill="#5b4028"/>' % (px - 37, py - 20))
    P.append('<rect x="%.1f" y="%.1f" width="62" height="28" rx="6" '
             'fill="#2aa7c8"/>' % (px - 31, py - 14))
    P.append('<rect x="%.1f" y="%.1f" width="62" height="28" rx="6" '
             'fill="#57c7e0" opacity=".5"/>' % (px - 31, py - 14))

    # 5 yurts (2)
    px, py = anchor(5)
    for dx in (-26, 26):
        P.append('<circle cx="%.1f" cy="%.1f" r="22" fill="#d7d2c4" '
                 'stroke="#8a8574" stroke-width="2"/>' % (px + dx, py))
        for a in range(0, 360, 30):
            ex = px + dx + 22 * math.cos(math.radians(a))
            ey = py + 22 * math.sin(math.radians(a))
            P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                     'stroke="#a49e8c" stroke-width="1"/>'
                     % (px + dx, py, ex, ey))

    # 6 fire pit
    px, py = anchor(6)
    P.append('<circle cx="%.1f" cy="%.1f" r="30" fill="#2a2118"/>' % (px, py))
    P.append('<circle cx="%.1f" cy="%.1f" r="12" fill="#e8721c"/>' % (px, py))
    P.append('<circle cx="%.1f" cy="%.1f" r="6" fill="#ffd24a"/>' % (px, py))

    # 7 summer kitchen, 8 winter kitchen (buildings)
    for i, (ww, hh, col) in ((7, (46, 34, "#6a4a2c")), (8, (52, 40, "#5a3f26"))):
        px, py = anchor(i)
        P.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="3" '
                 'fill="%s" stroke="#2c1e12" stroke-width="1.5"/>'
                 % (px - ww / 2, py - hh / 2, ww, hh, col))
        P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#3c2a19" '
                 'stroke-width="1.5"/>' % (px - ww / 2, py, px + ww / 2, py))

    # 3 tapchan
    px, py = anchor(3)
    P.append('<rect x="%.1f" y="%.1f" width="40" height="34" rx="3" '
             'fill="#6a4a2c" stroke="#2c1e12"/>' % (px - 20, py - 17))

    # 9 basketball
    px, py = anchor(9)
    P.append('<rect x="%.1f" y="%.1f" width="52" height="34" rx="2" '
             'fill="#b5652a"/>' % (px - 26, py - 17))
    P.append('<rect x="%.1f" y="%.1f" width="52" height="34" fill="none" '
             'stroke="#f0e9d8" stroke-width="1.4"/>' % (px - 26, py - 17))
    P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#f0e9d8" '
             'stroke-width="1.4"/>' % (px, py - 17, px, py + 17))
    P.append('<circle cx="%.1f" cy="%.1f" r="7" fill="none" stroke="#f0e9d8" '
             'stroke-width="1.4"/>' % (px, py))

    # 2 toilet
    px, py = anchor(2)
    P.append('<rect x="%.1f" y="%.1f" width="24" height="20" rx="2" '
             'fill="#7d6b8e"/>' % (px - 12, py - 10))
    P.append('</g>')  # end clip

    # number badges
    for i in ANCHORS:
        px, py = anchor(i)
        P.append('<circle cx="%.1f" cy="%.1f" r="11" fill="#14241c" '
                 'stroke="%s" stroke-width="1.5"/>' % (px, py, GOLD))
        P.append('<text x="%.1f" y="%.1f" font-size="12" fill="%s" '
                 'text-anchor="middle" font-weight="700">%d</text>'
                 % (px, py + 4, GOLD, i))

    # THE RED LINE (exact, on top)
    P.append('<polygon points="%s" fill="none" stroke="%s" stroke-width="3.2" '
             'stroke-linejoin="round"/>' % (poly, RED))
    labels = ["P%d" % (k + 1) for k in range(n)]
    for k in range(n):
        x, y = xs[k], ys[k]
        P.append('<circle cx="%.1f" cy="%.1f" r="4" fill="#fff"/>' % (x, y))
        P.append('<text x="%.1f" y="%.1f" font-size="13" fill="#fff" '
                 'font-weight="700">%s</text>' % (x + 6, y - 6, labels[k]))

    # dimension labels at edge midpoints
    for k in range(n):
        x1, y1 = xs[k], ys[k]
        x2, y2 = xs[(k + 1) % n], ys[(k + 1) % n]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        P.append('<text x="%.1f" y="%.1f" font-size="15" fill="#7CFC7A" '
                 'text-anchor="middle" font-weight="700">%.2f m</text>'
                 % (mx, my - 5, sides[k]))

    # DARYO / YO'L labels
    P.append('<text x="%.1f" y="%.1f" font-size="20" fill="#8fd0dc" '
             'letter-spacing="3" text-anchor="middle">DARYO</text>'
             % (cx, miny - 22))
    P.append('<text x="%.1f" y="%.1f" font-size="18" fill="%s" '
             'letter-spacing="3" text-anchor="middle">YO‘L</text>'
             % (cx, maxy + 34, MUTE))

    # north compass
    ncx, ncy = plan_box[0] + 40, plan_box[1] + 44
    P.append('<g transform="translate(%d,%d)">'
             '<polygon points="0,-22 6,0 0,6 -6,0" fill="#e7f0e6"/>'
             '<polygon points="0,22 6,0 0,-6 -6,0" fill="#5c7565"/>'
             '<text x="0" y="-26" font-size="12" fill="%s" '
             'text-anchor="middle">N</text></g>' % (ncx, ncy, TEXT))

    # ---- title block (top-left overlay)
    P.append('<g transform="translate(%d,%d)">' % (plan_box[0] + 70, plan_box[1] + 20))
    P.append('<text x="0" y="0" font-size="26" fill="%s" font-weight="800">'
             '%d-LOT (%.2f ga)</text>' % (TEXT, lot_no, area / 10000))
    P.append('<text x="0" y="22" font-size="13" fill="%s">Maydoni: %.2f ga '
             '(%.0f sotix)</text>' % (MUTE, area / 10000, area / 100))
    P.append('<text x="0" y="40" font-size="13" fill="%s">Vazifasi: Dam olish '
             'va oilaviy hordiq</text>' % MUTE)
    P.append('</g>')

    # ---- right: EKSPLIKATSIYA
    rx = 908
    P.append('<rect x="%d" y="24" width="300" height="700" rx="10" fill="%s"/>'
             % (rx, PANEL))
    yy = 60
    P.append('<text x="%d" y="%d" font-size="16" fill="%s" font-weight="800" '
             'letter-spacing="1">EKSPLIKATSIYA</text>' % (rx + 20, yy, GOLD))
    yy += 26
    for (num, label) in LEGEND:
        P.append('<circle cx="%d" cy="%d" r="10" fill="#14241c" stroke="%s"/>'
                 % (rx + 28, yy - 4, GOLD))
        P.append('<text x="%d" y="%d" font-size="11" fill="%s" '
                 'text-anchor="middle" font-weight="700">%d</text>'
                 % (rx + 28, yy, GOLD, num))
        P.append('<text x="%d" y="%d" font-size="13" fill="%s">%s</text>'
                 % (rx + 48, yy, TEXT, label))
        yy += 27
    # O'LCHAMLAR
    yy += 8
    P.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
             % (rx + 20, yy - 14, rx + 280, yy - 14, LINE))
    P.append('<text x="%d" y="%d" font-size="15" fill="%s" font-weight="800">'
             'O‘LCHAMLAR (m)</text>' % (rx + 20, yy + 6, GOLD))
    yy += 30
    dim_rows = [("🌊 Daryo bo‘yi", sides[river_idx]),
                ("🚗 Yo‘l bo‘yi", sides[road_idx]),
                ("Maydoni (ga)", area / 10000)]
    for (nm, val) in dim_rows:
        P.append('<text x="%d" y="%d" font-size="13" fill="%s">%s</text>'
                 '<text x="%d" y="%d" font-size="13" fill="%s" '
                 'text-anchor="end" font-weight="700">%.2f</text>'
                 % (rx + 20, yy, MUTE, nm, rx + 280, yy, TEXT, val))
        yy += 22
    P.append('<text x="%d" y="%d" font-size="13" fill="%s">Perimetr</text>'
             '<text x="%d" y="%d" font-size="13" fill="%s" text-anchor="end" '
             'font-weight="700">%.1f</text>'
             % (rx + 20, yy, MUTE, rx + 280, yy, TEXT, perim))

    # ---- far right: 3D KO'RINISHLAR placeholders
    tx0 = 1224
    P.append('<text x="%d" y="46" font-size="14" fill="%s" font-weight="800">'
             '3D KO‘RINISHLAR</text>' % (tx0, GOLD))
    tiles = ["Daryo bo‘yi terasa", "Basseyn zonasi", "O‘choq / dam zonasi"]
    ty = 58
    for cap in tiles:
        P.append('<rect x="%d" y="%d" width="190" height="130" rx="8" '
                 'fill="%s" stroke="%s"/>' % (tx0, ty, PANEL2, LINE))
        P.append('<text x="%d" y="%d" font-size="26" fill="%s" '
                 'text-anchor="middle">▦</text>' % (tx0 + 95, ty + 68, "#3c5647"))
        P.append('<text x="%d" y="%d" font-size="12" fill="%s" '
                 'text-anchor="middle">%s</text>' % (tx0 + 95, ty + 148, MUTE, cap))
        ty += 172

    # ---- bottom 3D strip
    by = 748
    P.append('<text x="24" y="%d" font-size="14" fill="%s" font-weight="800">'
             '3D KO‘RINISHLAR (AI render bilan to‘ldiriladi)</text>'
             % (by - 6, GOLD))
    bcaps = ["Kirish, avtoturargoh", "Tapchan", "O‘tovlar", "Yozgi oshxona",
             "Qishki oshxona"]
    bw2 = 272
    for k, cap in enumerate(bcaps):
        x0 = 24 + k * (bw2 + 12)
        P.append('<rect x="%d" y="%d" width="%d" height="196" rx="8" fill="%s" '
                 'stroke="%s"/>' % (x0, by, bw2, PANEL2, LINE))
        P.append('<text x="%d" y="%d" font-size="30" fill="%s" '
                 'text-anchor="middle">▦</text>' % (x0 + bw2 / 2, by + 96, "#3c5647"))
        P.append('<text x="%d" y="%d" font-size="12" fill="%s" '
                 'text-anchor="middle">%s</text>'
                 % (x0 + bw2 / 2, by + 176, MUTE, cap))

    P.append('</svg>')
    return "\n".join(P), area, perim, sides


def main():
    lot_no = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    os.makedirs(OUT, exist_ok=True)
    svg, area, perim, sides = build_sheet(lot_no)
    path = os.path.join(OUT, "lot_%02d_sheet.svg" % lot_no)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("Lot %d sheet: %.0f m2 (%.1f sotix), sides=%s"
          % (lot_no, area, area / 100, [round(s, 2) for s in sides]))
    print("Wrote", path)


if __name__ == "__main__":
    main()
