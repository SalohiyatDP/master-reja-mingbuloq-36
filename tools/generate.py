"""Generate per-lot master-plan deliverables from the Mingbuloq shapefile.

Outputs (all under ../output):
  dxf/lot_XX.dxf        exact geometry in TRUE ground metres (AutoCAD-ready)
  svg/lot_XX.svg        labelled drawing (side lengths, area, north, scale)
  combined_all.dxf      all 62 lots in a shared local grid (real positions)
  lots_report.csv       table: number, area, perimeter, centroid, dims
  index.html            browsable gallery of every lot

Geometry is copied vertex-for-vertex from the shapefile and only re-projected
(Web Mercator -> true metres); it is never re-drawn, so exact shapes/sizes are
preserved.
"""
import os
import math
from shp_reader import read_shp, read_dbf
import geo

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")
OUT = os.path.join(HERE, "..", "output")


def clean_ring(pts):
    """Drop the duplicate closing vertex if present."""
    if len(pts) >= 2 and pts[0] == pts[-1]:
        return pts[:-1]
    return pts


# ---------------------------------------------------------------- DXF writer

def dxf_header():
    return ["0", "SECTION", "2", "HEADER",
            "9", "$ACADVER", "1", "AC1009",
            "9", "$INSUNITS", "70", "6",  # 6 = metres
            "0", "ENDSEC",
            "0", "SECTION", "2", "ENTITIES"]


def dxf_footer():
    return ["0", "ENDSEC", "0", "EOF"]


def dxf_polyline(pts, layer="LOTS"):
    out = ["0", "POLYLINE", "8", layer, "66", "1", "70", "1"]  # 70=1 closed
    for (x, y) in pts:
        out += ["0", "VERTEX", "8", layer,
                "10", "%.4f" % x, "20", "%.4f" % y, "30", "0.0"]
    out += ["0", "SEQEND"]
    return out


def dxf_text(x, y, text, height, layer="LABELS", halign=1):
    # halign: 1 = centre (group code 72=1), needs alignment point in 11/21
    out = ["0", "TEXT", "8", layer,
           "10", "%.4f" % x, "20", "%.4f" % y, "30", "0.0",
           "40", "%.3f" % height, "1", str(text),
           "72", str(halign), "11", "%.4f" % x, "21", "%.4f" % y, "31", "0.0"]
    return out


def write_dxf(path, pts, lot_no, area_m2, side_labels):
    """side_labels: list of (mx, my, text) at edge midpoints."""
    diag = math.hypot(
        max(p[0] for p in pts) - min(p[0] for p in pts),
        max(p[1] for p in pts) - min(p[1] for p in pts),
    )
    th = max(diag * 0.03, 0.8)  # text height ~3% of diagonal
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)

    lines = dxf_header()
    lines += dxf_polyline(pts, "LOTS")
    # centre label: lot number + area
    lines += dxf_text(cx, cy + th * 0.7, "LOT %d" % lot_no, th * 1.2, "LABELS")
    lines += dxf_text(cx, cy - th * 0.9, "%.1f m2 (%.2f sotix)"
                      % (area_m2, area_m2 / 100.0), th, "LABELS")
    # side length labels
    for (mx, my, txt) in side_labels:
        lines += dxf_text(mx, my, txt, th * 0.75, "DIMS")
    lines += dxf_footer()

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------- SVG writer

def write_svg(path, pts, lot_no, area_m2, perim, sides):
    """sides: list of (mx, my, length) for edge midpoints (in true metres)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = maxx - minx
    h = maxy - miny
    pad = max(w, h) * 0.18 + 4
    vb_w = w + 2 * pad
    vb_h = h + 2 * pad

    # SVG y grows downward -> flip: sy = maxy - y
    def sx(x):
        return x - minx + pad

    def sy(y):
        return maxy - y + pad

    stroke = max(vb_w, vb_h) * 0.004
    fs = max(vb_w, vb_h) * 0.032
    fs_small = fs * 0.72

    poly = " ".join("%.2f,%.2f" % (sx(x), sy(y)) for (x, y) in pts)

    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.2f %.2f" '
        'font-family="Arial, sans-serif">' % (vb_w, vb_h))
    parts.append('<rect x="0" y="0" width="%.2f" height="%.2f" fill="#ffffff"/>'
                 % (vb_w, vb_h))
    # plot polygon
    parts.append('<polygon points="%s" fill="#eaf4ea" stroke="#1b6e1b" '
                 'stroke-width="%.3f" stroke-linejoin="round"/>' % (poly, stroke))
    # vertices
    for (x, y) in pts:
        parts.append('<circle cx="%.2f" cy="%.2f" r="%.3f" fill="#1b6e1b"/>'
                     % (sx(x), sy(y), stroke * 1.6))
    # side length labels
    for (mx, my, length) in sides:
        parts.append('<text x="%.2f" y="%.2f" font-size="%.2f" fill="#b00020" '
                     'text-anchor="middle" dominant-baseline="middle">%.2f m</text>'
                     % (sx(mx), sy(my), fs_small, length))
    # centre label
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    parts.append('<text x="%.2f" y="%.2f" font-size="%.2f" fill="#0d3b0d" '
                 'text-anchor="middle" font-weight="bold">LOT %d</text>'
                 % (sx(cx), sy(cy) - fs * 0.3, fs, lot_no))
    parts.append('<text x="%.2f" y="%.2f" font-size="%.2f" fill="#333" '
                 'text-anchor="middle">%.1f m\u00b2 (%.2f sotix)</text>'
                 % (sx(cx), sy(cy) + fs * 0.9, fs_small, area_m2, area_m2 / 100.0))
    # north arrow (top-right)
    ax = vb_w - pad * 0.5
    ay = pad * 0.9
    al = pad * 0.55
    parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#333" '
                 'stroke-width="%.3f"/>' % (ax, ay + al, ax, ay, stroke))
    parts.append('<polygon points="%.2f,%.2f %.2f,%.2f %.2f,%.2f" fill="#333"/>'
                 % (ax, ay - al * 0.15, ax - al * 0.18, ay + al * 0.12,
                    ax + al * 0.18, ay + al * 0.12))
    parts.append('<text x="%.2f" y="%.2f" font-size="%.2f" fill="#333" '
                 'text-anchor="middle">N</text>' % (ax, ay - al * 0.35, fs_small))
    # scale bar (bottom-left): nice round metres
    bar_m = _nice_len(w * 0.4)
    bx = pad * 0.6
    by = vb_h - pad * 0.5
    parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#333" '
                 'stroke-width="%.3f"/>' % (bx, by, bx + bar_m, by, stroke * 1.4))
    for t in (bx, bx + bar_m):
        parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="#333" '
                     'stroke-width="%.3f"/>' % (t, by - fs_small * 0.4, t,
                                                by + fs_small * 0.4, stroke * 1.4))
    parts.append('<text x="%.2f" y="%.2f" font-size="%.2f" fill="#333">%d m</text>'
                 % (bx, by - fs_small * 0.6, fs_small, int(round(bar_m))))
    parts.append('</svg>')

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def _nice_len(x):
    """Round a length down to a 'nice' 1/2/5 * 10^k value."""
    if x <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(x))
    for m in (5, 2, 1):
        if m * p <= x:
            return m * p
    return p


# ---------------------------------------------------------------- main

def main():
    for sub in ("dxf", "svg"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    _, _, shapes = read_shp(SHP)
    _, records = read_dbf(SHP.replace(".shp", ".dbf"))

    # global origin for the combined drawing = mean of all vertices (lon/lat)
    all_ll = []
    lot_data = []
    for i, g in enumerate(shapes):
        if not g["parts"]:
            continue
        ring_merc = clean_ring(g["parts"][0])
        ring_ll = [geo.merc_to_lonlat(x, y) for (x, y) in ring_merc]
        all_ll.extend(ring_ll)
        lot_data.append((i + 1, ring_ll))

    lon0 = sum(p[0] for p in all_ll) / len(all_ll)
    lat0 = sum(p[1] for p in all_ll) / len(all_ll)
    enu_global = geo.make_enu(lon0, lat0)

    combined = dxf_header()
    csv_rows = ["lot,area_m2,area_sotix,perimeter_m,vertices,width_m,height_m,"
                "centroid_lon,centroid_lat"]
    gallery = []

    for (lot_no, ring_ll) in lot_data:
        # local ENU centred on this lot's own centroid for a clean sheet
        clon = sum(p[0] for p in ring_ll) / len(ring_ll)
        clat = sum(p[1] for p in ring_ll) / len(ring_ll)
        enu = geo.make_enu(clon, clat)
        pts = [enu(lon, lat) for (lon, lat) in ring_ll]

        area = geo.shoelace_area(pts)
        perim = geo.perimeter(pts, closed=True)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        # edge midpoints + lengths
        sides = []
        n = len(pts)
        for k in range(n):
            x1, y1 = pts[k]
            x2, y2 = pts[(k + 1) % n]
            length = math.hypot(x2 - x1, y2 - y1)
            sides.append(((x1 + x2) / 2, (y1 + y2) / 2, length))
        side_txt = [(mx, my, "%.2f" % L) for (mx, my, L) in sides]

        write_dxf(os.path.join(OUT, "dxf", "lot_%02d.dxf" % lot_no),
                  pts, lot_no, area, side_txt)
        write_svg(os.path.join(OUT, "svg", "lot_%02d.svg" % lot_no),
                  pts, lot_no, area, perim, sides)

        csv_rows.append("%d,%.2f,%.2f,%.2f,%d,%.2f,%.2f,%.6f,%.6f"
                        % (lot_no, area, area / 100.0, perim, n,
                           width, height, clon, clat))
        gallery.append((lot_no, area, perim, n))

        # add to combined drawing (real relative positions)
        gpts = [enu_global(lon, lat) for (lon, lat) in ring_ll]
        combined += dxf_polyline(gpts, "LOTS")
        gcx = sum(p[0] for p in gpts) / len(gpts)
        gcy = sum(p[1] for p in gpts) / len(gpts)
        combined += dxf_text(gcx, gcy, str(lot_no), 3.0, "LABELS")

    combined += dxf_footer()
    with open(os.path.join(OUT, "combined_all.dxf"), "w", encoding="utf-8") as f:
        f.write("\n".join(combined) + "\n")

    with open(os.path.join(OUT, "lots_report.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(csv_rows) + "\n")

    _write_index(gallery)

    total_area = sum(g[1] for g in gallery)
    print("Generated %d lots." % len(gallery))
    print("Total true area: %.1f m2 = %.3f ga = %.1f sotix"
          % (total_area, total_area / 10000, total_area / 100))
    print("Output dir:", os.path.abspath(OUT))


def _write_index(gallery):
    rows = []
    for (lot_no, area, perim, n) in gallery:
        rows.append(
            '<div class="card">'
            '<img src="svg/lot_%02d.svg" alt="Lot %d"/>'
            '<div class="meta"><b>Lot %d</b><br>%.1f m\u00b2 (%.2f sotix)<br>'
            'Perimetr: %.1f m &middot; %d burchak<br>'
            '<a href="dxf/lot_%02d.dxf" download>DXF yuklab olish</a></div>'
            '</div>' % (lot_no, lot_no, lot_no, area, area / 100.0,
                        perim, n, lot_no))

    html = """<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mingbuloq \u2014 lotlar master rejasi</title>
<style>
 body{font-family:Arial,sans-serif;margin:0;background:#f5f6f5;color:#222}
 header{background:#1b6e1b;color:#fff;padding:18px 24px}
 header h1{margin:0;font-size:20px}
 header p{margin:4px 0 0;opacity:.9;font-size:13px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
       gap:16px;padding:20px}
 .card{background:#fff;border:1px solid #ddd;border-radius:8px;overflow:hidden;
       box-shadow:0 1px 3px rgba(0,0,0,.08)}
 .card img{width:100%%;height:220px;object-fit:contain;background:#fff;
           border-bottom:1px solid #eee}
 .meta{padding:10px 12px;font-size:13px;line-height:1.5}
 .meta a{color:#1b6e1b;text-decoration:none;font-weight:bold}
 .meta a:hover{text-decoration:underline}
</style></head><body>
<header><h1>Mingbuloq c-36 \u2014 lotlar master rejasi</h1>
<p>%d ta lot &middot; aniq geometriya shapefile'dan olingan (o'lchamlar buzilmagan)</p></header>
<div class="grid">
%s
</div></body></html>""" % (len(gallery), "\n".join(rows))

    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
