"""Overlay to verify river/road assignment: river frontage = BLUE (daryo),
road frontage = ORANGE (yo'l), with a small arrow pointing to the river side.
"""
import os
import math
import orientation as O
import geo

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "output", "master_plans")


def main():
    lots = O._load_global()
    cents = [O._centroid(r) for (_, r) in lots]
    rr = O.get_river_road()
    xs = [p[0] for (_, r) in lots for p in r]
    ys = [p[1] for (_, r) in lots for p in r]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    W, margin = 1700, 90
    sc = (W - 2 * margin) / (maxx - minx)
    H = int((maxy - miny) * sc + 2 * margin)

    def f(x, y):
        return (margin + (x - minx) * sc, H - (margin + (y - miny) * sc))

    P = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
         'viewBox="0 0 %d %d" font-family="Arial">' % (W, H, W, H)]
    P.append('<rect width="%d" height="%d" fill="#f7faf4"/>' % (W, H))
    for i, (no, ring) in enumerate(lots):
        ri, ro = rr[no]
        pts = [f(x, y) for (x, y) in ring]
        poly = " ".join("%.1f,%.1f" % p for p in pts)
        P.append('<polygon points="%s" fill="#eef6e4" stroke="#ccc" '
                 'stroke-width="1"/>' % poly)
        for idx, col in ((ri, "#1f7ae0"), (ro, "#f08a24")):
            a, b = ring[idx], ring[(idx + 1) % len(ring)]
            fa, fb = f(*a), f(*b)
            P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                     'stroke-width="5" stroke-linecap="round"/>'
                     % (fa[0], fa[1], fb[0], fb[1], col))
        c = cents[i]
        rd = O.river_dir_of(no)
        cf = f(*c)
        af = f(c[0] + rd[0] * 12, c[1] + rd[1] * 12)
        P.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#1a7d1a" '
                 'stroke-width="1.5"/>' % (cf[0], cf[1], af[0], af[1]))
        P.append('<text x="%.1f" y="%.1f" font-size="12" fill="#123" '
                 'text-anchor="middle">%d</text>' % (cf[0], cf[1] + 4, no))
    # legend
    P.append('<rect x="20" y="20" width="300" height="72" rx="8" fill="#fff" '
             'stroke="#ccc"/>')
    P.append('<line x1="38" y1="46" x2="86" y2="46" stroke="#1f7ae0" '
             'stroke-width="6"/><text x="98" y="51" font-size="17">Daryo (river)</text>')
    P.append('<line x1="38" y1="74" x2="86" y2="74" stroke="#f08a24" '
             'stroke-width="6"/><text x="98" y="79" font-size="17">Yoʻl (road)</text>')
    P.append('</svg>')
    path = os.path.join(OUT, "verify_sides.svg")
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(P))
    print("Wrote", path, "%dx%d" % (W, H))


if __name__ == "__main__":
    main()
