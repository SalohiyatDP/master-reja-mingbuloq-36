"""Conceptual master-plan generator for a single lot.

The lot boundary (red line) is taken EXACTLY from the shapefile geometry in
true ground metres and is never modified. Amenities are laid out *inside* the
polygon relative to two reference edges the caller specifies:
  entrance_side : where the road/parking is
  river_side    : where the terrace faces the river

Output: a bright, self-contained HTML "presentation" for the lot, containing
a labelled plan (SVG), a zone-area technical table, materials, 3D-style object
icons and project advantages. Printable to A3/PDF from the browser.

Usage:
  python3 master_plan.py <lot_no> [entrance=S] [river=N]
  sides: N,S,E,W (compass on the local ENU grid; +y = north)
"""
import os
import sys
import math
from shp_reader import read_shp
import geo

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")
OUT = os.path.join(HERE, "..", "output", "master_plans")


# ------------------------------------------------------------ geometry utils

def load_lot_metres(lot_no):
    """Return the lot ring in local true metres (centred on its centroid)."""
    _, _, shapes = read_shp(SHP)
    idx = lot_no - 1
    ring = shapes[idx]["parts"][0]
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    ll = [geo.merc_to_lonlat(x, y) for (x, y) in ring]
    clon = sum(p[0] for p in ll) / len(ll)
    clat = sum(p[1] for p in ll) / len(ll)
    enu = geo.make_enu(clon, clat)
    return [enu(lon, lat) for (lon, lat) in ll]


def point_in_polygon(pt, ring):
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def snap_inside(pt, ring, centroid, steps=40):
    """Move a point toward the centroid until it lies inside the polygon."""
    if point_in_polygon(pt, ring):
        return pt
    x, y = pt
    cx, cy = centroid
    for k in range(1, steps + 1):
        t = k / steps
        p = (x + (cx - x) * t, y + (cy - y) * t)
        if point_in_polygon(p, ring):
            return p
    return centroid


def edge_point(bbox, side, u):
    """A point on a bbox edge. side in NSEW, u in [0,1] along that edge."""
    minx, miny, maxx, maxy = bbox
    if side == "N":
        return (minx + (maxx - minx) * u, maxy)
    if side == "S":
        return (minx + (maxx - minx) * u, miny)
    if side == "E":
        return (maxx, miny + (maxy - miny) * u)
    if side == "W":
        return (minx, miny + (maxy - miny) * u)
    return ((minx + maxx) / 2, (miny + maxy) / 2)


def uv_point(bbox, u, v):
    minx, miny, maxx, maxy = bbox
    return (minx + (maxx - minx) * u, miny + (maxy - miny) * v)


# ------------------------------------------------------------ layout

# Each amenity: (key, uz_label, emoji, color, footprint m (w,h) or None=icon)
ZONE_SPEC = [
    ("green",    "Yashil hudud",           "🌳", "#bfe3a6", None),
    ("parking",  "Avtoturargoh",           "🚗", "#c9ccd1", (7, 5)),
    ("toilet",   "Hojatxona",              "🚻", "#d8c7e8", (3, 2.5)),
    ("winterk",  "Qishki oshxona",         "🏠", "#e8b98a", (6, 5)),
    ("summerk",  "Yozgi oshxona",          "🍳", "#f0cf9a", (5, 4)),
    ("pool",     "Basseyn",                "🏊", "#7ec8e3", (8, 4)),
    ("yurts",    "O‘tovlar (3 ta)",        "⛺", "# efe1c0".replace(" ", ""), None),
    ("fire",     "O‘choq / dam zonasi",    "🔥", "#f4a06a", None),
    ("tapchan",  "Tapchan",                "🪵", "#d9b382", None),
    ("basket",   "Basketbol maydoni",      "⚽", "#e6a860", (15, 11)),
    ("terrace",  "Daryo bo‘yi terasasi",   "🌊", "#9fd0d6", (10, 3)),
]


def build_layout(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    centroid = (cx, cy)

    # normalized anchor positions (u across width, v bottom->top).
    # entrance assumed at S (bottom), river at N (top) -- rotated later.
    anchors = {
        "parking":  (0.5, 0.08),
        "toilet":   (0.9, 0.15),
        "winterk":  (0.22, 0.28),
        "summerk":  (0.38, 0.30),
        "fire":     (0.62, 0.32),
        "tapchan":  (0.80, 0.40),
        "basket":   (0.25, 0.55),
        "pool":     (0.60, 0.60),
        "yurts":    (0.45, 0.72),
        "terrace":  (0.5, 0.93),
        "green":    (0.75, 0.78),
    }

    placed = {}
    for key, (u, v) in anchors.items():
        p = uv_point(bbox, u, v)
        placed[key] = snap_inside(p, ring, centroid)
    return bbox, centroid, placed


def estimate_zone_areas(ring, placed, total_area):
    """Grid-sample the polygon; assign each cell to nearest anchor."""
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    step = max((maxx - minx), (maxy - miny)) / 90.0
    if step <= 0:
        step = 0.5
    keys = list(placed.keys())
    counts = {k: 0 for k in keys}
    total = 0
    y = miny
    while y <= maxy:
        x = minx
        while x <= maxx:
            if point_in_polygon((x, y), ring):
                total += 1
                best = None
                bestd = 1e18
                for k in keys:
                    px, py = placed[k]
                    d = (px - x) ** 2 + (py - y) ** 2
                    if d < bestd:
                        bestd = d
                        best = k
                counts[best] += 1
            x += step
        y += step
    if total == 0:
        return {k: 0 for k in keys}
    return {k: counts[k] / total * total_area for k in keys}


# ------------------------------------------------------------ SVG rendering

ICON_EMOJI = {k: e for (k, _, e, _, _) in ZONE_SPEC}
ZONE_LABEL = {k: lbl for (k, lbl, _, _, _) in ZONE_SPEC}
ZONE_COLOR = {k: c for (k, _, _, c, _) in ZONE_SPEC}
ZONE_FOOT = {k: f for (k, _, _, _, f) in ZONE_SPEC}


def render_plan_svg(ring, bbox, centroid, placed, zone_area):
    minx, miny, maxx, maxy = bbox
    w = maxx - minx
    h = maxy - miny
    pad = max(w, h) * 0.16 + 6
    vb_w = w + 2 * pad
    vb_h = h + 2 * pad

    def sx(x):
        return x - minx + pad

    def sy(y):
        return maxy - y + pad  # flip Y

    stroke = max(vb_w, vb_h) * 0.0035
    fs = max(vb_w, vb_h) * 0.026

    P = []
    P.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.2f %.2f" '
             'font-family="Segoe UI, Arial, sans-serif">' % (vb_w, vb_h))
    P.append('<rect width="%.2f" height="%.2f" fill="#f4fbef"/>' % (vb_w, vb_h))

    poly = " ".join("%.2f,%.2f" % (sx(x), sy(y)) for (x, y) in ring)
    # base green fill of the whole plot
    P.append('<polygon points="%s" fill="#d8efc4"/>' % poly)

    # soft zone blobs (approximate footprints as circles sized by area)
    for k in placed:
        px, py = placed[k]
        a = zone_area.get(k, 0)
        r = max(math.sqrt(max(a, 1) / math.pi), fs * 0.6)
        col = ZONE_COLOR.get(k, "#cccccc")
        P.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" '
                 'fill-opacity="0.55"/>' % (sx(px), sy(py), r, col))

    # rectangular footprints for hard objects (pool, court, buildings)
    for k, foot in ZONE_FOOT.items():
        if foot is None or k not in placed:
            continue
        fw, fh = foot
        px, py = placed[k]
        col = ZONE_COLOR.get(k, "#ccc")
        P.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" '
                 'fill="%s" stroke="#555" stroke-width="%.3f"/>'
                 % (sx(px - fw / 2), sy(py + fh / 2), fw, fh, min(fw, fh) * 0.15,
                    col, stroke * 0.7))

    # walkways: centroid -> each anchor
    ccx, ccy = centroid
    for k in placed:
        px, py = placed[k]
        P.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#caa16a" '
                 'stroke-width="%.3f" stroke-dasharray="%.2f %.2f" '
                 'stroke-linecap="round"/>'
                 % (sx(ccx), sy(ccy), sx(px), sy(py), stroke * 1.2,
                    stroke * 2, stroke * 2))

    # THE RED LINE (exact boundary) -- drawn last, on top, unmodified
    P.append('<polygon points="%s" fill="none" stroke="#e11d1d" '
             'stroke-width="%.3f" stroke-linejoin="round"/>' % (poly, stroke * 3))
    for (x, y) in ring:
        P.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#e11d1d"/>'
                 % (sx(x), sy(y), stroke * 2))

    # labels + emoji markers
    for k in placed:
        px, py = placed[k]
        P.append('<text x="%.2f" y="%.2f" font-size="%.2f" text-anchor="middle">'
                 '%s</text>' % (sx(px), sy(py) + fs * 0.35, fs * 1.3,
                                ICON_EMOJI.get(k, "")))
        P.append('<text x="%.2f" y="%.2f" font-size="%.2f" text-anchor="middle" '
                 'fill="#123" font-weight="600">%s</text>'
                 % (sx(px), sy(py) - fs * 0.9, fs * 0.62, ZONE_LABEL.get(k, k)))

    # side length labels on the red line
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        L = math.hypot(x2 - x1, y2 - y1)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        P.append('<text x="%.2f" y="%.2f" font-size="%.2f" fill="#b00020" '
                 'text-anchor="middle">%.1f m</text>'
                 % (sx(mx), sy(my), fs * 0.6, L))

    # north arrow
    ax, ay = vb_w - pad * 0.5, pad * 0.85
    al = pad * 0.5
    P.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#333" '
             'stroke-width="%.3f"/>' % (ax, ay + al, ax, ay, stroke))
    P.append('<polygon points="%.2f,%.2f %.2f,%.2f %.2f,%.2f" fill="#333"/>'
             % (ax, ay - al * 0.2, ax - al * 0.2, ay + al * 0.15,
                ax + al * 0.2, ay + al * 0.15))
    P.append('<text x="%.2f" y="%.2f" font-size="%.2f" text-anchor="middle">N</text>'
             % (ax, ay - al * 0.4, fs * 0.7))
    P.append('</svg>')
    return "\n".join(P)


# ------------------------------------------------------------ HTML wrapper

MATERIALS = [
    ("Piyoda yo‘laklar", "Tabiiy tosh plitka / dekorativ shag‘al, kenglik 1.2–1.5 m"),
    ("Tapchan & terasa", "Termo-yog‘och (lиственница) taxta, antiseptik qoplama"),
    ("O‘tovlar", "An’anaviy kigiz o‘tov, yog‘och karkas, diametri 5–6 m"),
    ("Basseyn", "Beton chasha + mozaika, filtrlash tizimi bilan"),
    ("Oshxonalar", "G‘isht/gazoblok devor, yog‘och bezak, cherepitsa tom"),
    ("O‘choq zonasi", "Tabiiy tosh mangal, o‘tga chidamli maydoncha"),
    ("Basketbol", "Rezina qoplama, standart halqa, yoritish"),
    ("Yashil hudud", "Gazon, mahalliy daraxtlar, dekorativ butalar"),
]

ADVANTAGES = [
    "Lotning aniq shakli va o‘lchamlari 1:1 saqlangan — qizil chiziq o‘zgarmagan.",
    "Kirish qismida avtoturargoh — mehmonlar oqimi qulay tashkil etilgan.",
    "Hojatxona chekka qismda — dam olish zonalaridan uzoq, gigienik.",
    "Daryo bo‘yida terasa — eng nazarali va sokin dam olish nuqtasi.",
    "Faol (basketbol, basseyn) va sokin (o‘tov, tapchan) zonalar ajratilgan.",
    "Ichki piyoda yo‘laklar barcha obyektlarni bog‘laydi — qulay harakat.",
    "Katta yashil hudud — mikroiqlim va tabiiy soya.",
]


def kpi_rows(zone_area, total_area):
    rows = []
    for k in sorted(zone_area, key=lambda z: -zone_area[z]):
        a = zone_area[k]
        rows.append("<tr><td>%s %s</td><td>%.0f</td><td>%.2f</td><td>%.1f%%</td></tr>"
                    % (ICON_EMOJI.get(k, ""), ZONE_LABEL.get(k, k), a, a / 100.0,
                       a / total_area * 100))
    return "\n".join(rows)


def render_html(lot_no, ring, svg, zone_area, total_area, perim):
    mat = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (a, b) for a, b in MATERIALS)
    adv = "\n".join("<li>%s</li>" % a for a in ADVANTAGES)
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return """<!DOCTYPE html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lot %d — konseptual master-plan</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:'Segoe UI',Arial,sans-serif;
   background:#eef3ea;color:#1a2b17}
 .sheet{max-width:1180px;margin:18px auto;background:#fff;border-radius:14px;
   box-shadow:0 4px 24px rgba(0,0,0,.12);overflow:hidden}
 header{background:linear-gradient(90deg,#1b6e1b,#3aa03a);color:#fff;padding:22px 28px}
 header h1{margin:0;font-size:24px} header p{margin:6px 0 0;opacity:.92}
 .body{display:grid;grid-template-columns:1.35fr 1fr;gap:0}
 .plan{padding:18px;border-right:1px solid #eee}
 .plan svg{width:100%%;height:auto;border:1px solid #e3ecdd;border-radius:10px;background:#f4fbef}
 .side{padding:18px 22px}
 h2{font-size:16px;color:#1b6e1b;border-bottom:2px solid #d8efc4;padding-bottom:6px;
    margin:18px 0 10px} h2:first-child{margin-top:0}
 table{width:100%%;border-collapse:collapse;font-size:13px}
 th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #eef}
 th{background:#f3f8ef;color:#2a5} tfoot td{font-weight:700;background:#f7fbf4}
 ul{margin:0;padding-left:18px;font-size:13.5px;line-height:1.65}
 .kpi{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px}
 .chip{background:#eaf6e2;border:1px solid #cfe8bf;border-radius:20px;
   padding:6px 12px;font-size:13px;font-weight:600;color:#1b6e1b}
 .note{font-size:12px;color:#777;padding:10px 22px 20px}
 @media print{body{background:#fff}.sheet{box-shadow:none;margin:0}}
</style></head><body>
<div class="sheet">
<header>
  <h1>🏞️ Lot %d — Konseptual master-plan</h1>
  <p>Mingbuloq c-36 · dam olish / glamping zonasi · qizil chiziq 1:1 aniq saqlangan</p>
</header>
<div class="body">
  <div class="plan">%s</div>
  <div class="side">
    <div class="kpi">
      <span class="chip">📐 %.0f m² (%.1f sotix)</span>
      <span class="chip">📏 Perimetr %.1f m</span>
      <span class="chip">↔️ %.0f×%.0f m</span>
    </div>
    <h2>Texnik ko‘rsatkichlar (zonalar bo‘yicha)</h2>
    <table>
      <thead><tr><th>Zona</th><th>m²</th><th>sotix</th><th>ulush</th></tr></thead>
      <tbody>%s</tbody>
      <tfoot><tr><td>JAMI</td><td>%.0f</td><td>%.1f</td><td>100%%</td></tr></tfoot>
    </table>
    <h2>Materiallar va elementlar</h2>
    <table><tbody>%s</tbody></table>
    <h2>Loyiha afzalliklari</h2>
    <ul>%s</ul>
  </div>
</div>
<div class="note">⚠️ Konseptual variant. Obyektlar joylashuvi taxminiy — kirish/daryo
 tomonini aniqlagach optimallashtiriladi. Lot chegarasi (qizil chiziq) shapefile'dan
 aynan olingan va o‘zgartirilmagan.</div>
</div></body></html>""" % (
        lot_no, lot_no, svg,
        total_area, total_area / 100.0, perim, width, height,
        kpi_rows(zone_area, total_area), total_area, total_area / 100.0,
        mat, adv)


def main():
    lot_no = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    os.makedirs(OUT, exist_ok=True)
    ring = load_lot_metres(lot_no)
    total_area = geo.shoelace_area(ring)
    perim = geo.perimeter(ring, closed=True)
    bbox, centroid, placed = build_layout(ring)
    zone_area = estimate_zone_areas(ring, placed, total_area)
    svg = render_plan_svg(ring, bbox, centroid, placed, zone_area)
    html = render_html(lot_no, ring, svg, zone_area, total_area, perim)

    svg_path = os.path.join(OUT, "lot_%02d_plan.svg" % lot_no)
    html_path = os.path.join(OUT, "lot_%02d.html" % lot_no)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("Lot %d: area=%.0f m2 (%.1f sotix), perim=%.1f m"
          % (lot_no, total_area, total_area / 100, perim))
    print("Zone areas:", {k: round(v) for k, v in zone_area.items()})
    print("Wrote:", html_path)


if __name__ == "__main__":
    main()
