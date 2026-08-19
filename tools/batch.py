"""Batch-generate all deliverables for every lot in the shapefile.

For each lot i (1..N):
  base/lot_XX_base.svg        clean ControlNet control image
  base/lot_XX_base_annot.svg  dimensioned human reference
  sheets/lot_XX_sheet.svg     dark presentation sheet

Also writes gallery.html indexing everything.
Boundaries come verbatim from the shapefile — exact shapes preserved.
"""
import os
from shp_reader import read_shp
import base_plan
import sheet
import geo

HERE = os.path.dirname(__file__)
SHP = os.path.join(HERE, "..", "shp", "migbuloq_wgs84.shp")
MP = os.path.join(HERE, "..", "output", "master_plans")
BASE = os.path.join(MP, "base")
SHEETS = os.path.join(MP, "sheets")


def lot_count():
    _, _, shapes = read_shp(SHP)
    return sum(1 for g in shapes if g["parts"])


def main():
    os.makedirs(BASE, exist_ok=True)
    os.makedirs(SHEETS, exist_ok=True)
    n = lot_count()
    rows = []
    for lot in range(1, n + 1):
        # base + annotated
        for annot, suffix in ((False, "base"), (True, "base_annot")):
            svg, cw, ch, area = base_plan.draw(lot, annot)
            with open(os.path.join(BASE, "lot_%02d_%s.svg" % (lot, suffix)),
                      "w", encoding="utf-8") as f:
                f.write(svg)
        # presentation sheet
        ssvg, sarea, perim, sides = sheet.build_sheet(lot)
        with open(os.path.join(SHEETS, "lot_%02d_sheet.svg" % lot),
                  "w", encoding="utf-8") as f:
            f.write(ssvg)
        rows.append((lot, sarea, perim))
        if lot % 10 == 0 or lot == n:
            print("  ... %d/%d" % (lot, n))

    _gallery(rows)
    print("Done: %d lots -> base, annot, sheet SVGs + gallery.html" % n)


def _gallery(rows):
    cards = []
    for (lot, area, perim) in rows:
        cards.append(
            '<div class="card">'
            '<a href="sheets/lot_%02d_sheet.svg" target="_blank">'
            '<img src="base/lot_%02d_base_annot.svg" loading="lazy"/></a>'
            '<div class="m"><b>%d-LOT</b> · %.2f ga (%.0f sotix)<br>'
            'Perimetr %.0f m<br>'
            '<a href="base/lot_%02d_base.svg" target="_blank">base</a> · '
            '<a href="base/lot_%02d_base_annot.svg" target="_blank">annot</a> · '
            '<a href="sheets/lot_%02d_sheet.svg" target="_blank">sheet</a>'
            '</div></div>'
            % (lot, lot, lot, area / 10000, area / 100, perim, lot, lot, lot))
    html = """<!DOCTYPE html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mingbuloq — 62 lot master-plan</title>
<style>
 body{margin:0;font-family:'Segoe UI',Arial,sans-serif;background:#0f1b15;color:#e7f0e6}
 header{background:linear-gradient(90deg,#1b6e1b,#2f8f3a);padding:20px 26px}
 header h1{margin:0;font-size:21px} header p{margin:5px 0 0;opacity:.9;font-size:13px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
  gap:14px;padding:18px}
 .card{background:#16241d;border:1px solid #24382c;border-radius:10px;overflow:hidden}
 .card img{width:100%;height:210px;object-fit:contain;background:#fff}
 .m{padding:9px 11px;font-size:12.5px;line-height:1.55}
 .m a{color:#7fd08a;text-decoration:none} .m a:hover{text-decoration:underline}
</style></head><body>
<header><h1>🏞️ Mingbuloq c-36 — 62 lot konseptual master-plan</h1>
<p>Har bir lot chegarasi shapefile'dan aynan olingan · base = ControlNet asos, sheet = prezentatsiya varag'i</p></header>
<div class="grid">__CARDS__</div></body></html>""".replace("__CARDS__", "\n".join(cards))
    with open(os.path.join(MP, "gallery.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
