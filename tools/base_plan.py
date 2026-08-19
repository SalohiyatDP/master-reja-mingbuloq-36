"""Clean ControlNet base image generator for a single lot.

Produces two SVGs (crisp, fixed-pixel canvas so they rasterise cleanly):
  lot_XX_base.svg        light, high-contrast line/shape plan, NO text
                         -> feed to ControlNet (Canny / Lineart / Seg)
  lot_XX_base_annot.svg  same layout + dimensions + numbered legend
                         -> human reference

The boundary comes verbatim from the shapefile; only interior amenities are
stylised as clean footprints so the image model follows the composition while
the exact plot shape/size is locked.
"""
import os
import sys
import math
import random
from master_plan import load_lot_metres, point_in_polygon, snap_inside
from sheet import ANCHORS, LEGEND, get_anchors
import orientation
import geo

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "output", "master_plans", "base")

# light, high-contrast palette (good edges for Canny/Lineart)
BG = "#ffffff"
GRASS = "#cfe8bf"
WATER = "#bfe0ea"
LINE = "#14261b"
PATH = "#e8ddc2"
WOOD = "#c79a5f"
POOLC = "#5cc0dd"
BLD = "#c99a63"
COURT = "#e0a45a"
TREE = "#7cb56a"
CAR = "#dfe3de"
TXT = "#12261a"
GREEN_TXT = "#0a7d2c"


def canvas_transform(ring, target_w=1200, margin=140):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx
    h = maxy - miny
    sc = (target_w - 2 * margin) / max(w, h)
    cw = target_w
    ch = int(h * sc + 2 * margin)

    def f(x, y):
        px = margin + (x - minx) * sc
        py = ch - (margin + (y - miny) * sc)  # flip Y (up = top)
        return px, py

    return f, sc, cw, ch, (minx, miny, maxx, maxy)


def draw(lot_no, annotated):
    ring, _river_idx, _road_idx = orientation.oriented_lot(lot_no)
    area = geo.shoelace_area(ring)
    perim = geo.perimeter(ring, closed=True)
    n = len(ring)
    ANCHORS = get_anchors(lot_no)   # per-lot layout variant (shadows import)
    f, sc, cw, ch, _ = canvas_transform(ring)

    xs = [f(*p)[0] for p in ring]
    ys = [f(*p)[1] for p in ring]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    bw, bh = maxx - minx, maxy - miny
    cxp = sum(xs) / n
    cyp = sum(ys) / n

    def uv(u, v):
        return (minx + bw * u, maxy - bh * v)

    # snap every anchor inside the exact polygon so no object/badge spills out
    ring_screen = list(zip(xs, ys))
    _cs = (cxp, cyp)
    _snapped = {}
    for _i, (_u, _v) in ANCHORS.items():
        _p = uv(_u, _v)
        if not point_in_polygon(_p, ring_screen):
            _p = snap_inside(_p, ring_screen, _cs)
        _snapped[_i] = ((_p[0] - minx) / bw, (maxy - _p[1]) / bh)
    ANCHORS = _snapped

    poly = " ".join("%.1f,%.1f" % (x, y) for x, y in zip(xs, ys))
    P = []
    P.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" font-family="Arial, sans-serif">'
             % (cw, ch, cw, ch))
    P.append('<rect width="%d" height="%d" fill="%s"/>' % (cw, ch, BG))

    # water band above the daryo (top) edge
    P.append('<rect x="0" y="0" width="%d" height="%.0f" fill="%s"/>'
             % (cw, miny, WATER))

    P.append('<clipPath id="lot"><polygon points="%s"/></clipPath>' % poly)
    P.append('<polygon points="%s" fill="%s"/>' % (poly, GRASS))
    P.append('<g clip-path="url(#lot)">')

    # paths from a spine
    sp = uv(*ANCHORS[6])
    for i in ANCHORS:
        px, py = uv(*ANCHORS[i])
        P.append('<path d="M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" stroke="%s" '
                 'stroke-width="14" fill="none" stroke-linecap="round"/>'
                 % (sp[0], sp[1], (sp[0] + px) / 2 + 20, (sp[1] + py) / 2,
                    px, py, PATH))

    # trees along border
    random.seed(lot_no)
    for _ in range(60):
        u, v = random.random(), random.random()
        if min(u, 1 - u, v, 1 - v) < 0.14 or random.random() < 0.15:
            px, py = uv(u, v)
            r = random.uniform(9, 16)
            P.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" '
                     'stroke="%s" stroke-width="1.5"/>' % (px, py, r, TREE, LINE))

    def rect(px, py, w, h, fill):
        P.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="4" '
                 'fill="%s" stroke="%s" stroke-width="2.5"/>'
                 % (px - w / 2, py - h / 2, w, h, fill, LINE))

    # 11 terrace along top
    P.append('<rect x="%.1f" y="%.1f" width="%.1f" height="30" fill="%s" '
             'stroke="%s" stroke-width="2.5"/>'
             % (minx + bw * 0.12, miny - 2, bw * 0.76, WOOD, LINE))
    # 1 parking + cars
    px, py = uv(*ANCHORS[1])
    rect(px, py, 120, 120, "#d9dcd7")
    for k in range(4):
        P.append('<rect x="%.1f" y="%.1f" width="34" height="58" rx="5" '
                 'fill="%s" stroke="%s" stroke-width="2"/>'
                 % (px - 52 + k * 28, py - 29, CAR, LINE))
    # 4 pool
    px, py = uv(*ANCHORS[4])
    rect(px, py, 128, 70, WOOD)
    P.append('<rect x="%.1f" y="%.1f" width="104" height="46" rx="8" fill="%s" '
             'stroke="%s" stroke-width="2"/>' % (px - 52, py - 23, POOLC, LINE))
    # 5 yurts
    px, py = uv(*ANCHORS[5])
    for dx in (-46, 46):
        P.append('<circle cx="%.1f" cy="%.1f" r="38" fill="#ececdd" '
                 'stroke="%s" stroke-width="2.5"/>' % (px + dx, py, LINE))
        for a in range(0, 360, 30):
            P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                     'stroke-width="1.2"/>'
                     % (px + dx, py, px + dx + 38 * math.cos(math.radians(a)),
                        py + 38 * math.sin(math.radians(a)), LINE))
    # 6 fire pit
    px, py = uv(*ANCHORS[6])
    P.append('<circle cx="%.1f" cy="%.1f" r="46" fill="#e7d8bf" stroke="%s" '
             'stroke-width="2.5"/>' % (px, py, LINE))
    P.append('<circle cx="%.1f" cy="%.1f" r="18" fill="#f0a04a" stroke="%s" '
             'stroke-width="2"/>' % (px, py, LINE))
    # 7,8 kitchens
    rect(*uv(*ANCHORS[7]), 78, 58, BLD)
    rect(*uv(*ANCHORS[8]), 88, 66, BLD)
    # 3 tapchan
    rect(*uv(*ANCHORS[3]), 66, 56, WOOD)
    # 9 basketball
    px, py = uv(*ANCHORS[9])
    rect(px, py, 90, 58, COURT)
    P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#fff" '
             'stroke-width="2"/>' % (px, py - 29, px, py + 29))
    P.append('<circle cx="%.1f" cy="%.1f" r="12" fill="none" stroke="#fff" '
             'stroke-width="2"/>' % (px, py))
    # 2 toilet
    rect(*uv(*ANCHORS[2]), 42, 34, "#cdbcda")
    P.append('</g>')

    # boundary (exact) -- bold dark for strong ControlNet edge
    P.append('<polygon points="%s" fill="none" stroke="%s" stroke-width="6" '
             'stroke-linejoin="round"/>' % (poly, LINE))

    # number badges (kept on both, they help seg/lineart follow zones)
    for i in ANCHORS:
        px, py = uv(*ANCHORS[i])
        P.append('<circle cx="%.1f" cy="%.1f" r="15" fill="#fff" stroke="%s" '
                 'stroke-width="2"/>' % (px, py, LINE))
        P.append('<text x="%.1f" y="%.1f" font-size="17" fill="%s" '
                 'text-anchor="middle" font-weight="700">%d</text>'
                 % (px, py + 6, TXT, i))

    if annotated:
        # corner markers + dims + labels
        for k in range(n):
            P.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>'
                     % (xs[k], ys[k], LINE))
            P.append('<text x="%.1f" y="%.1f" font-size="18" fill="%s" '
                     'font-weight="700">P%d</text>'
                     % (xs[k] + 8, ys[k] - 8, LINE, k + 1))
        sides = [math.hypot(xs[(k + 1) % n] - xs[k], ys[(k + 1) % n] - ys[k])
                 for k in range(n)]
        # real metre lengths (not pixel)
        real = []
        for k in range(n):
            a = ring[k]
            b = ring[(k + 1) % n]
            real.append(math.hypot(b[0] - a[0], b[1] - a[1]))
        for k in range(n):
            mx = (xs[k] + xs[(k + 1) % n]) / 2
            my = (ys[k] + ys[(k + 1) % n]) / 2
            P.append('<text x="%.1f" y="%.1f" font-size="20" fill="%s" '
                     'text-anchor="middle" font-weight="700">%.2f m</text>'
                     % (mx, my - 6, GREEN_TXT, real[k]))
        P.append('<text x="%.1f" y="%.1f" font-size="22" fill="#1878a0" '
                 'letter-spacing="3" text-anchor="middle">DARYO</text>'
                 % (cxp, miny - 20))
        P.append('<text x="%.1f" y="%.1f" font-size="20" fill="#555" '
                 'letter-spacing="3" text-anchor="middle">YO‘L</text>'
                 % (cxp, maxy + 40))
        P.append('<text x="20" y="34" font-size="24" fill="%s" '
                 'font-weight="800">%d-LOT — %.2f ga (%.0f sotix)</text>'
                 % (TXT, lot_no, area / 10000, area / 100))
        P.append('<text x="20" y="60" font-size="15" fill="#555">Perimetr: '
                 '%.1f m · ControlNet uchun asos plan</text>' % perim)

    P.append('</svg>')
    return "\n".join(P), cw, ch, area


def main():
    lot_no = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    os.makedirs(OUT, exist_ok=True)
    for annot, suffix in ((False, "base"), (True, "base_annot")):
        svg, cw, ch, area = draw(lot_no, annot)
        path = os.path.join(OUT, "lot_%02d_%s.svg" % (lot_no, suffix))
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(svg)
        print("Wrote %s  (%dx%d px)" % (path, cw, ch))


if __name__ == "__main__":
    main()
