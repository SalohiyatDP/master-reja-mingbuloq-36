"""Extract coloured polylines from the CAD PDF content stream (pure Python).

The exported PDF draws the reference lines by colour:
  yellow (1 1 0)  = road  (yo'l)   -> bottom of the ribbon
  cyan   (0 1 1)  = river (daryo)  -> top of the ribbon
  red    (1 0 0)  = lot boundaries
We parse the (flate-decoded) content stream, track the current stroke colour
(RG), and collect sub-paths (m/l sequences) grouped by colour.
"""
import re
import zlib
import os
import math

HERE = os.path.dirname(__file__)
PDF = os.path.join(HERE, "..", "lotlarga_ExportCAD-Model.pdf")


def _decoded():
    data = open(PDF, "rb").read()
    streams = re.findall(rb'stream\r?\n(.*?)\r?\nendstream', data, re.DOTALL)
    out = b""
    for s in streams:
        try:
            out += zlib.decompress(s)
        except Exception:
            out += s
    return out.decode("latin-1")


def extract():
    txt = _decoded()
    toks = txt.split()
    color = None
    cur = []
    polys = []  # (color, [(x,y),...])
    i = 0
    stack = []

    def flush():
        if len(cur) >= 2:
            polys.append((color, list(cur)))

    while i < len(toks):
        t = toks[i]
        # numbers push to stack
        try:
            float(t)
            stack.append(float(t))
            i += 1
            continue
        except ValueError:
            pass
        if t == "RG" and len(stack) >= 3:
            color = tuple(round(v, 2) for v in stack[-3:])
            stack = []
        elif t == "rg" and len(stack) >= 3:
            stack = []
        elif t == "m" and len(stack) >= 2:
            flush()
            cur = [(stack[-2], stack[-1])]
            stack = []
        elif t == "l" and len(stack) >= 2:
            cur.append((stack[-2], stack[-1]))
            stack = []
        elif t in ("S", "s", "f", "F", "B", "b", "n"):
            flush()
            cur = []
            stack = []
        elif t == "re" and len(stack) >= 4:
            stack = []
        else:
            stack = []
        i += 1
    flush()
    return polys


def summarize():
    polys = extract()
    from collections import defaultdict
    byc = defaultdict(list)
    for c, pts in polys:
        byc[c].append(pts)
    for c in sorted(byc, key=lambda k: -sum(len(p) for p in byc[k])):
        segs = byc[c]
        npts = sum(len(p) for p in segs)
        allp = [q for p in segs for q in p]
        xs = [q[0] for q in allp]
        ys = [q[1] for q in allp]
        print("color %s : %d subpaths, %d pts, bbox x[%.0f..%.0f] y[%.0f..%.0f]"
              % (c, len(segs), npts, min(xs), max(xs), min(ys), max(ys)))


if __name__ == "__main__":
    summarize()
