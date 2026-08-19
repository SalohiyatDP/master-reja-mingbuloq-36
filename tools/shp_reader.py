"""Pure-Python ESRI Shapefile + DBF reader (no external deps).

Supports the subset of the shapefile spec we need for polygon land-plot data:
- .shp geometry parsing for shape types Polygon(5) / PolyLine(3) / Point(1)
  and their Z/M variants (13/15, 23/25, 11/21, etc. handled by base type).
- .dbf attribute table parsing (dBASE III/IV).

Coordinates are read exactly as stored (no re-projection, no rounding),
so plot geometry is preserved bit-for-bit.
"""
import struct
import os


# --- .dbf attribute table -------------------------------------------------

def read_dbf(path):
    with open(path, "rb") as f:
        data = f.read()

    num_records = struct.unpack("<I", data[4:8])[0]
    header_size = struct.unpack("<H", data[8:10])[0]
    record_size = struct.unpack("<H", data[10:12])[0]

    # Field descriptors: start at byte 32, terminated by 0x0D.
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        raw = data[pos:pos + 32]
        name = raw[0:11].split(b"\x00")[0].decode("latin-1").strip()
        ftype = chr(raw[11])
        flen = raw[16]
        fdec = raw[17]
        fields.append((name, ftype, flen, fdec))
        pos += 32

    records = []
    rec_start = header_size
    for i in range(num_records):
        base = rec_start + i * record_size
        rec = data[base:base + record_size]
        if not rec:
            break
        deleted = rec[0:1] == b"*"
        offset = 1
        row = {}
        for (name, ftype, flen, fdec) in fields:
            raw_val = rec[offset:offset + flen]
            offset += flen
            val = raw_val.decode("utf-8", errors="replace").strip()
            if ftype in ("N", "F"):
                if val == "":
                    val = None
                else:
                    try:
                        val = int(val) if fdec == 0 else float(val)
                    except ValueError:
                        pass
            row[name] = val
        if not deleted:
            records.append(row)

    return [f[0] for f in fields], records


# --- .shp geometry ---------------------------------------------------------

SHAPE_TYPE_NAMES = {
    0: "Null", 1: "Point", 3: "PolyLine", 5: "Polygon", 8: "MultiPoint",
    11: "PointZ", 13: "PolyLineZ", 15: "PolygonZ", 18: "MultiPointZ",
    21: "PointM", 23: "PolyLineM", 25: "PolygonM", 28: "MultiPointM",
}


def read_shp(path):
    with open(path, "rb") as f:
        data = f.read()

    file_shape_type = struct.unpack("<i", data[32:36])[0]
    bbox = struct.unpack("<4d", data[36:68])  # Xmin, Ymin, Xmax, Ymax

    shapes = []
    pos = 100  # skip 100-byte header
    n = len(data)
    while pos < n:
        rec_num = struct.unpack(">i", data[pos:pos + 4])[0]
        content_len = struct.unpack(">i", data[pos + 4:pos + 8])[0]  # in 16-bit words
        pos += 8
        content = data[pos:pos + content_len * 2]
        pos += content_len * 2

        st = struct.unpack("<i", content[0:4])[0]
        base_type = st % 10 if st in (13, 15, 23, 25) else st

        geom = {"rec": rec_num, "type": st, "parts": []}

        if st == 0:
            shapes.append(geom)
            continue

        if base_type in (3, 5) or st in (3, 5, 13, 15, 23, 25):
            # box(32) numParts(4) numPoints(4)
            num_parts = struct.unpack("<i", content[36:40])[0]
            num_points = struct.unpack("<i", content[40:44])[0]
            p = 44
            parts = list(struct.unpack("<%di" % num_parts, content[p:p + 4 * num_parts]))
            p += 4 * num_parts
            coords = struct.unpack("<%dd" % (2 * num_points), content[p:p + 16 * num_points])
            pts = [(coords[2 * i], coords[2 * i + 1]) for i in range(num_points)]
            # split into rings/parts
            bounds = parts + [num_points]
            for i in range(num_parts):
                geom["parts"].append(pts[bounds[i]:bounds[i + 1]])
        elif base_type == 1 or st in (1, 11, 21):
            x, y = struct.unpack("<2d", content[4:20])
            geom["parts"].append([(x, y)])

        shapes.append(geom)

    return file_shape_type, bbox, shapes


# --- helpers ---------------------------------------------------------------

def ring_area(pts):
    """Signed area (shoelace). Positive = clockwise in shapefile convention."""
    a = 0.0
    m = len(pts)
    for i in range(m):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % m]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def polygon_area(geom):
    """Net area of a polygon record (outer rings minus holes), abs value."""
    total = 0.0
    for ring in geom["parts"]:
        total += ring_area(ring)
    return abs(total)


if __name__ == "__main__":
    import sys, json
    shp = sys.argv[1]
    base = os.path.splitext(shp)[0]
    fst, bbox, shapes = read_shp(shp)
    field_names, records = read_dbf(base + ".dbf")

    print("Shape type      :", fst, SHAPE_TYPE_NAMES.get(fst, "?"))
    print("Bounding box    : Xmin=%.3f Ymin=%.3f Xmax=%.3f Ymax=%.3f" % bbox)
    print("Feature count   :", len(shapes))
    print("Attribute fields:", field_names)
    print()
    print("First 5 records (attributes):")
    for r in records[:5]:
        print("  ", r)
    print()
    print("Geometry summary (first 10):")
    for g in shapes[:10]:
        npts = sum(len(p) for p in g["parts"])
        area = polygon_area(g) if g["parts"] and len(g["parts"][0]) > 2 else 0.0
        print("  rec %-3d type=%-2d parts=%d points=%d area(m^2)=%.1f"
              % (g["rec"], g["type"], len(g["parts"]), npts, area))
