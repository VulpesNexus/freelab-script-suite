#FLM: Font Builder
# -*- coding: utf-8 -*-
"""FreeLab Font Builder, from FontLab's Scripts menu: makes template sheets to draw a font's glyphs on,
in any app or on paper, and builds the glyphs from the sheets drawn.

A template is one image per sheet (100 glyphs a sheet by default): a cell per glyph, its em box with
the font's metric lines in a pale color, the character it is for beside it, a finder pattern at each
corner, and two bands of black and white squares that hold the sheet's layout and glyph names. A
sheet read back is found by its finder patterns and told by its bands, so it needs no file beside it
and no metadata (drawing apps drop it), and it can be read on another computer than the one that made
it, scanned crooked, or photographed.

Valid Python 2.7 (FontLab 7) and Python 3. The parts above the Qt line need no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import io
import json
import math
import os
import re
import struct
import sys
import zlib

FORMAT_VERSION = 1
MAGIC = b"FLFB"
PER_SHEET = 100  # glyphs a sheet, by default
PER_SHEET_MAX = 400  # at most (a sheet stays under SHEET_PIXELS_MAX at the default em size)
EM_PIXELS = 500  # the em's size on the sheet, in pixels, by default
EM_PIXELS_RANGE = (150, 1200)
SHEET_PIXELS_MAX = 120 * 1000 * 1000  # a sheet larger than this is split into more sheets
BOX_WIDTH = 1.2  # the drawing box's width, in ems (room for wide glyphs and their sidebearings)
BOX_LEFT = 0.1  # where the glyph's origin stands in it, in ems from its left edge
BOX_ROOM = 0.15  # room above the ascender and below the descender, in ems (accents, swashes)
LABEL = 0.22  # the label strip over each box, in ems
GAP = 0.08  # between two cells, in ems
FINDER_MODULES = 7  # a finder pattern is 7 by 7 modules: ring, ring, 3 by 3 center (1:1:3:1:1)
QUIET = 2  # white modules around a finder and a band
GUIDE_GRAY = 205  # the guides' gray (and the label's), as Qt makes gray of GUIDE_RGB: above any threshold allowed
THRESHOLD_MAX = 185  # the ink threshold at most: the guides 20 grays above it, for JPEG noise and soft edges
INK_THRESHOLD = 128
EVEN_SIDE = 0.05  # each sidebearing, in ems, of a glyph placed With even sidebearings


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class Metrics(object):
    """A font's vertical metrics, in its units."""

    def __init__(self, upm=1000, ascender=750, descender=-250, x_height=500, cap_height=700):
        self.upm = int(upm)
        self.ascender, self.descender = int(ascender), int(descender)
        self.x_height, self.cap_height = int(x_height), int(cap_height)

    def as_list(self):
        return [self.upm, self.ascender, self.descender, self.x_height, self.cap_height]

    @classmethod
    def from_list(cls, values):
        return cls(*values)


class Sheet(object):
    """One sheet's layout, in the template's pixels (y down). Every place on it comes from these
    numbers, which its bands hold."""

    def __init__(self, names, labels, metrics, em=EM_PIXELS, columns=None, index=0, count=1, family=""):
        self.names = list(names)
        self.labels = list(labels)
        self.metrics = metrics
        self.em = int(em)
        n = max(1, len(self.names))
        self.columns = int(columns or max(1, int(math.ceil(math.sqrt(n)))))
        self.rows = int(math.ceil(n / float(self.columns)))
        self.index, self.count = int(index), int(count)
        self.family = family or ""
        # The sheet's unit: a finder pattern's square and a band's, in pixels. The sheet's size, its
        # margins, and its bands are whole numbers of it, so that a reader that measures it can tell them
        self.unit = max(6, int(round(self.em / 24.0)))

    # The em box and the cells

    def units(self, value):
        """Font units to template pixels."""
        return value * self.em / float(self.metrics.upm)

    def box_size(self):
        m = self.metrics
        height = m.ascender - m.descender + 2 * BOX_ROOM * m.upm
        return int(round(BOX_WIDTH * self.em)), int(round(self.units(height)))

    def cell_size(self):
        w, h = self.box_size()
        return w + int(round(GAP * self.em)), h + int(round((LABEL + GAP) * self.em))

    def margin(self):
        """The room around the cells, in pixels: a finder pattern and its quiet zones."""
        return margin_units() * self.unit

    def band_rows(self):
        return int(math.ceil(len(band_bits(self.payload())) / float(self.band_columns())))

    def band_columns(self):
        return band_columns(self.size_units()[0])

    def band_height(self):
        return (self.band_rows() + QUIET) * self.unit

    def grid_origin(self):
        """The top left of the first cell."""
        return self.margin(), self.margin() + self.band_height()

    def size_units(self):
        """The sheet's size in units (whole numbers), the bands' rows counted from the payload."""
        cw, ch = self.cell_size()
        u = self.unit
        width = 2 * margin_units() + int(math.ceil(self.columns * cw / float(u)))
        rows = 0
        for _ in range(4):  # (the band's rows depend on its columns, which depend on the width: settled at once)
            rows = int(math.ceil(len(band_bits(self.payload())) / float(band_columns(width))))
        height = 2 * margin_units() + 2 * (rows + QUIET) + int(math.ceil(self.rows * ch / float(u)))
        return width, height

    def size(self):
        w, h = self.size_units()
        return w * self.unit, h * self.unit

    def cell(self, i):
        """(left, top) of cell i's box (its drawing box; the label strip is above it)."""
        cw, ch = self.cell_size()
        x0, y0 = self.grid_origin()
        column, row = i % self.columns, i // self.columns
        return x0 + column * cw, y0 + row * ch + int(round(LABEL * self.em))

    def origin(self, i):
        """The glyph's origin (x 0, baseline) in template pixels, for cell i."""
        left, top = self.cell(i)
        m = self.metrics
        return left + BOX_LEFT * self.em, top + self.units(m.ascender + BOX_ROOM * m.upm)

    def to_units(self, i, x, y):
        """A template pixel of cell i to font units (y up)."""
        ox, oy = self.origin(i)
        scale = self.metrics.upm / float(self.em)
        return (x - ox) * scale, (oy - y) * scale

    def finders(self):
        """The four finder patterns' centers: top left, top right, bottom right, bottom left."""
        w, h = self.size_units()
        return [(x * self.unit, y * self.unit) for x, y in finder_centers(w, h)]

    def guides(self, i):
        """[(name, y)] of cell i's metric lines in template pixels."""
        _, oy = self.origin(i)
        m = self.metrics
        return [(name, oy - self.units(value)) for name, value in (
            ("ascender", m.ascender), ("cap height", m.cap_height), ("x-height", m.x_height), ("baseline", 0),
            ("descender", m.descender))]

    # What the bands hold

    def payload(self):
        """The layout as bytes: everything a reader needs, in a compact JSON, compressed."""
        data = {"v": FORMAT_VERSION, "s": [self.index, self.count], "c": self.columns, "e": self.em,
                "m": self.metrics.as_list(), "n": self.names, "f": self.family[:40]}
        labels = [label for label in self.labels]
        if labels != [label_of(name) for name in self.names]:
            data["l"] = labels
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=True, sort_keys=True)
        return zlib.compress(text.encode("ascii"), 9)

    @classmethod
    def from_payload(cls, raw):
        data = json.loads(zlib.decompress(raw).decode("ascii"))
        if data.get("v") != FORMAT_VERSION:
            raise ValueError("a template of another version (%s)" % data.get("v"))
        names = data["n"]
        labels = data.get("l") or [label_of(name) for name in names]
        sheet = cls(names, labels, Metrics.from_list(data["m"]), data["e"], data["c"], data["s"][0], data["s"][1],
                    data.get("f", ""))
        return sheet


def label_of(name):
    """A cell's label: the character a glyph name stands for (uniXXXX, uXXXXX, a one-letter name),
    else the name."""
    base = name.split(".")[0]
    match = re.match(r"^uni([0-9A-F]{4})$", base) or re.match(r"^u([0-9A-F]{4,6})$", base)
    if match:
        return unichr_(int(match.group(1), 16)) + name[len(base):]
    return name


def unichr_(code):
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:  # (a narrow build: a surrogate pair)
        code -= 0x10000
        return unichr(0xD800 + (code >> 10)) + unichr(0xDC00 + (code & 0x3FF))  # noqa: F821


def split_sheets(names, labels, metrics, per_sheet=PER_SHEET, em=EM_PIXELS, family=""):
    """The sheets for names, per_sheet glyphs each (fewer where a sheet would pass SHEET_PIXELS_MAX)."""
    per_sheet = max(1, min(int(per_sheet), PER_SHEET_MAX))
    probe = Sheet(names[:per_sheet] or ["a"], labels[:per_sheet] or ["a"], metrics, em)
    w, h = probe.size()
    while per_sheet > 1 and w * h > SHEET_PIXELS_MAX:
        per_sheet = int(per_sheet * 0.8)
        probe = Sheet(names[:per_sheet], labels[:per_sheet], metrics, em)
        w, h = probe.size()
    groups = [(names[i:i + per_sheet], labels[i:i + per_sheet]) for i in range(0, len(names), per_sheet)] or [([], [])]
    return [Sheet(n, l, metrics, em, None, index, len(groups), family) for index, (n, l) in enumerate(groups)]


# ---------------------------------------------------------------------------
# Bits
# ---------------------------------------------------------------------------


def band_bits(payload):
    """The bits of a band: magic, length, payload, CRC32, MSB first (1: a black square)."""
    raw = MAGIC + struct.pack(">I", len(payload)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    bits = []
    for byte in bytearray(raw):
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def bits_payload(bits):
    """The payload read back from a band's bits, or None (no magic, a bad length, or a CRC mismatch)."""
    data = bytearray()
    for i in range(0, len(bits) - 7, 8):
        value = 0
        for bit in bits[i:i + 8]:
            value = (value << 1) | (1 if bit else 0)
        data.append(value)
    data = bytes(data)
    if len(data) < 12 or data[:4] != MAGIC:
        return None
    length = struct.unpack(">I", data[4:8])[0]
    if length <= 0 or 12 + length > len(data):
        return None
    payload = data[8:8 + length]
    crc = struct.unpack(">I", data[8 + length:12 + length])[0]
    if zlib.crc32(payload) & 0xFFFFFFFF != crc:
        return None
    return payload


def margin_units():
    return FINDER_MODULES + 2 * QUIET


def band_columns(width_units):
    """A band's squares a row, for a sheet that many units wide (between the two margins)."""
    return max(16, width_units - 2 * margin_units())


def finder_centers(width_units, height_units):
    """The four finder patterns' centers in units: top left, top right, bottom right, bottom left."""
    half = QUIET + FINDER_MODULES / 2.0
    return [(half, half), (width_units - half, half), (width_units - half, height_units - half),
            (half, height_units - half)]


def band_cell(width_units, height_units, band, i):
    """The center, in units, of a band's square for bit i: band 0 (over the cells) is read row by row
    from its top left; band 1 (under them) from its bottom left, row by row upward, so that where it
    begins does not depend on how many rows it has."""
    columns = band_columns(width_units)
    column, row = i % columns, i // columns
    x = margin_units() + column + 0.5
    if band == 0:
        return x, margin_units() + row + 0.5
    return x, height_units - margin_units() - row - 0.5


def band_squares(width_units, height_units, band, count):
    return [band_cell(width_units, height_units, band, i) for i in range(count)]


def marks(sheet):
    """[(x, y, w, h)] in units: the black rectangles of a sheet's finder patterns and bands."""
    width, height = sheet.size_units()
    out = []
    for cx, cy in finder_centers(width, height):
        x, y = cx - FINDER_MODULES / 2.0, cy - FINDER_MODULES / 2.0
        n = FINDER_MODULES
        out += [(x, y, n, 1), (x, y + n - 1, n, 1), (x, y + 1, 1, n - 2), (x + n - 1, y + 1, 1, n - 2),
                (x + 2, y + 2, n - 4, n - 4)]
    bits = band_bits(sheet.payload())
    for band in (0, 1):
        for bit, (cx, cy) in zip(bits, band_squares(width, height, band, len(bits))):
            if bit:
                out.append((cx - 0.5, cy - 0.5, 1, 1))
    return out


def _xml(text):
    return ("%s" % text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _n(value):
    return ("%.2f" % value).rstrip("0").rstrip(".")


def sheet_svg(sheet, guide_rgb=(170, 215, 250)):
    """A sheet as an SVG drawing, the same as render_sheet's image (its pixels its user units): the
    template in a locked group, "template", for a vector app to draw on a layer above it. Read back as an
    image (Qt renders it at its size), so whatever the app draws is traced as on a raster sheet."""
    width, height = sheet.size()
    guide = "rgb(%d,%d,%d)" % tuple(guide_rgb)
    thin, base = max(1.0, sheet.em / 400.0), max(2.0, sheet.em / 200.0)
    label_px, small_px = max(10, int(sheet.em * LABEL * 0.6)), max(9, int(sheet.em * LABEL * 0.35))
    bw, bh = sheet.box_size()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (
               width, height, width, height),
           '<title>%s</title>' % _xml("%s sheet %d of %d" % (sheet.family or "Font Builder", sheet.index + 1, sheet.count)),
           '<g id="template" sodipodi:insensitive="true" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/'
           'sodipodi-0.dtd">',
           '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>' % (width, height),
           '<g fill="none" stroke="%s" stroke-width="%s">' % (guide, _n(thin))]
    for i in range(len(sheet.names)):
        left, top = sheet.cell(i)
        out.append('<rect x="%s" y="%s" width="%d" height="%d"/>' % (_n(left), _n(top), bw, bh))
        for key, y in sheet.guides(i):
            extra = ' stroke-width="%s"' % _n(base) if key == "baseline" else ""
            out.append('<line x1="%s" y1="%s" x2="%s" y2="%s"%s/>' % (_n(left), _n(y), _n(left + bw), _n(y), extra))
        ox, _ = sheet.origin(i)
        out.append('<line x1="%s" y1="%s" x2="%s" y2="%s"/>' % (_n(ox), _n(top), _n(ox), _n(top + bh)))
    out.append('</g>')
    out.append('<g fill="%s" font-family="Arial, sans-serif">' % guide)
    for i, (name, label) in enumerate(zip(sheet.names, sheet.labels)):
        left, top = sheet.cell(i)
        middle = top - LABEL * sheet.em / 2.0
        if label != name:
            out.append('<text x="%s" y="%s" font-size="%d" dominant-baseline="central">%s</text>' % (
                _n(left), _n(middle + label_px * 0.35), label_px, _xml(label)))
        out.append('<text x="%s" y="%s" font-size="%d" text-anchor="end">%s</text>' % (
            _n(left + bw), _n(middle + small_px * 0.35), small_px, _xml(name)))
    which = ("%s, sheet" % sheet.family) if sheet.family else "Sheet"
    title = "%s %d of %d. Draw in dark ink inside the boxes; keep the corner squares and the bands clean." % (
        which, sheet.index + 1, sheet.count)
    out.append('<text x="%s" y="%s" font-size="%d" text-anchor="middle">%s</text>' % (
        _n(width / 2.0), _n(QUIET * sheet.unit * 1.25 + small_px * 0.35), small_px, _xml(title)))
    out.append('</g>')
    u = sheet.unit
    out.append('<path fill="#000000" d="%s"/>' % " ".join(
        "M%s %sh%sv%sh-%sz" % (_n(x * u), _n(y * u), _n(w * u), _n(h * u), _n(w * u)) for x, y, w, h in marks(sheet)))
    out.append('</g>')
    out.append('<g id="drawing"></g>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Geometry: the homography from the template to an image of it
# ---------------------------------------------------------------------------


def solve(matrix, vector):
    """x of matrix x = vector (Gaussian elimination with partial pivoting); raises ValueError when
    singular."""
    n = len(vector)
    a = [list(row) + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col:
                f = a[r][col] / a[col][col]
                if f:
                    a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return [a[i][n] / a[i][i] for i in range(n)]


def homography(src, dst):
    """The 3 by 3 projective map (row-major, 9 values, last 1) taking 4 points src to dst."""
    matrix, vector = [], []
    for (x, y), (u, v) in zip(src, dst):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        vector.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        vector.append(v)
    h = solve(matrix, vector)
    return h + [1.0]


def apply(h, x, y):
    w = h[6] * x + h[7] * y + h[8]
    return (h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w


# ---------------------------------------------------------------------------
# Finding the finder patterns in a binarized image
# ---------------------------------------------------------------------------


RUN = re.compile(b"\x00+|\xff+")


def runs(row):
    """[(value, start, length)] of a binarized row (bytes of 0 and 255)."""
    return [(row[m.start():m.start() + 1], m.start(), m.end() - m.start()) for m in RUN.finditer(row)]


def finder_ratio(lengths, slack=0.5):
    """Whether five run lengths read 1:1:3:1:1, within slack of a module."""
    total = sum(lengths)
    if total < 7:
        return False
    module = total / 7.0
    allowed = module * slack
    return (abs(lengths[0] - module) < allowed and abs(lengths[1] - module) < allowed
            and abs(lengths[2] - 3 * module) < 3 * allowed and abs(lengths[3] - module) < allowed
            and abs(lengths[4] - module) < allowed)


def column_runs(rows, x, y, limit):
    """The 1:1:3:1:1 check down a column through (x, y): the center run and the four around it, or None."""
    height = len(rows)

    def pixel(yy):
        return rows[yy][x:x + 1]

    black = b"\x00"
    if pixel(y) != black:
        return None
    lengths = [0, 0, 0, 0, 0]
    yy = y
    while yy >= 0 and pixel(yy) == black:
        lengths[2] += 1
        yy -= 1
    for slot, want in ((1, False), (0, True)):
        while yy >= 0 and (pixel(yy) == black) == want and lengths[slot] <= limit:
            lengths[slot] += 1
            yy -= 1
    yy = y + 1
    while yy < height and pixel(yy) == black:
        lengths[2] += 1
        yy += 1
    for slot, want in ((3, False), (4, True)):
        while yy < height and (pixel(yy) == black) == want and lengths[slot] <= limit:
            lengths[slot] += 1
            yy += 1
    if not finder_ratio(lengths):
        return None
    center = (yy - lengths[4] - lengths[3]) - lengths[2] / 2.0
    return center, sum(lengths) / 7.0


def find_finders(rows, step=1):
    """Centers (x, y) and module sizes of the finder patterns in a binarized image (rows of bytes, 0 ink,
    255 paper), each pattern once: [(x, y, module)]."""
    found = []
    for y in range(0, len(rows), step):
        r = runs(rows[y])
        for k in range(len(r) - 4):
            if r[k][0] != b"\x00":
                continue
            five = r[k:k + 5]
            if any(five[i][0] != (b"\x00" if i % 2 == 0 else b"\xff") for i in range(5)):
                continue
            lengths = [length for _, _, length in five]
            if not finder_ratio(lengths):
                continue
            cx = five[2][1] + five[2][2] / 2.0
            checked = column_runs(rows, int(cx), y, sum(lengths))
            if checked is None:
                continue
            cy, module_v = checked
            found.append((cx, cy, (sum(lengths) / 7.0 + module_v) / 2.0))
    return cluster(found)


def cluster(points):
    """Points close to each other (within a module) merged by their mean; the merged weight kept."""
    groups = []
    for x, y, m in points:
        for g in groups:
            if abs(g[0] / g[3] - x) < 2 * m and abs(g[1] / g[3] - y) < 2 * m:
                g[0] += x
                g[1] += y
                g[2] += m
                g[3] += 1
                break
        else:
            groups.append([x, y, m, 1])
    return [(g[0] / g[3], g[1] / g[3], g[2] / g[3], g[3]) for g in groups]


def corner_finders(found, width, height):
    """The four finders nearest the image's corners (top left, top right, bottom right, bottom left),
    among those seen on several rows; None when fewer than four stand apart."""
    strong = [f for f in found if f[3] >= 2] or found
    if len(strong) < 4:
        return None
    corners = [(0, 0), (width, 0), (width, height), (0, height)]
    chosen = []
    for cx, cy in corners:
        best = min(strong, key=lambda f: (f[0] - cx) ** 2 + (f[1] - cy) ** 2)
        if best in chosen:
            return None
        chosen.append(best)
    return chosen


def rotations(corners):
    """The four ways the finders can stand for the template's corners (a sheet scanned turned)."""
    return [corners[i:] + corners[:i] for i in range(4)]


# ---------------------------------------------------------------------------
# Reading a sheet: its layout from its bands
# ---------------------------------------------------------------------------

SIZE_GUESSES = 10  # units tried on each side of the size the finders' distances suggest


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def nearby(center, reach):
    """center, then center - 1, center + 1, center - 2, ... within reach."""
    out = [center]
    for step in range(1, reach + 1):
        out.extend([center - step, center + step])
    return [v for v in out if v > 0]


class Found(object):
    """A sheet read from an image: its layout, and the map from its units to the image's pixels."""

    def __init__(self, sheet, mapping, band):
        self.sheet = sheet
        self.mapping = mapping  # homography: sheet units to image pixels
        self.band = band  # the band it was read from (0 over the cells, 1 under them)

    def to_image(self, x, y):
        """A template pixel to the image's."""
        u = float(self.sheet.unit)
        return apply(self.mapping, x / u, y / u)


def levels(mapping, sample, width, height):
    """(ink, paper) gray levels near the top left finder: its center, and the quiet zone beside it."""
    half = QUIET + FINDER_MODULES / 2.0
    ink = sample(*apply(mapping, half, half))
    paper = sample(*apply(mapping, QUIET / 2.0, half))
    return ink, paper


def read_bits(mapping, sample, width, height, band, count, threshold):
    return [1 if sample(*apply(mapping, x, y)) < threshold else 0
            for x, y in band_squares(width, height, band, count)]


def read_layout(corners, unit, sample, reach=SIZE_GUESSES):
    """The sheet an image shows (Found), from its four finder centers in the image (any order of
    turning: each tried), the size of a unit in the image (a finder's square: one number, or one a
    finder, as find_finders measures them: a photographed sheet's far side is smaller), and
    sample(x, y): the image's gray at a point (0 ink, 255 paper). None when no band reads. The sheet's
    size in units is guessed from the finders' distances and tried a few units either way (reach, or 6%
    of the size where that is more): the magic bytes and the CRC say which size is right."""
    units = list(unit) if isinstance(unit, (list, tuple)) else [unit] * 4
    for turn in range(4):
        turned = list(corners)[turn:] + list(corners)[:turn]
        u = units[turn:] + units[:turn]
        tl, tr, br, bl = [(c[0], c[1]) for c in turned]
        half = QUIET + FINDER_MODULES / 2.0
        across = (distance(tl, tr) / ((u[0] + u[1]) / 2.0) + distance(bl, br) / ((u[3] + u[2]) / 2.0)) / 2.0 + 2 * half
        down = (distance(tl, bl) / ((u[0] + u[3]) / 2.0) + distance(tr, br) / ((u[1] + u[2]) / 2.0)) / 2.0 + 2 * half
        for width in nearby(int(round(across)), max(reach, int(0.06 * across))):
            for height in nearby(int(round(down)), max(reach, int(0.06 * down))):
                try:
                    mapping = homography(finder_centers(width, height), [tl, tr, br, bl])
                except ValueError:
                    continue
                ink, paper = levels(mapping, sample, width, height)
                if paper - ink < 40:
                    continue
                threshold = (ink + paper) / 2.0
                for band in (0, 1):
                    head = read_bits(mapping, sample, width, height, band, 64, threshold)
                    raw = bytearray()
                    for i in range(0, 64, 8):
                        value = 0
                        for bit in head[i:i + 8]:
                            value = (value << 1) | bit
                        raw.append(value)
                    if bytes(raw[:4]) != MAGIC:
                        continue
                    length = struct.unpack(">I", bytes(raw[4:8]))[0]
                    if not 0 < length < 1 << 20:
                        continue
                    bits = read_bits(mapping, sample, width, height, band, 8 * (12 + length), threshold)
                    payload = bits_payload(bits)
                    if payload is None:
                        continue
                    try:
                        sheet = Sheet.from_payload(payload)
                    except Exception:
                        continue
                    if sheet.size_units() != (width, height):
                        continue
                    return Found(sheet, mapping, band)
    return None


# ---------------------------------------------------------------------------
# Glyph lists
# ---------------------------------------------------------------------------


def characters_of(text):
    """The characters of typed text, once each, in order (spaces and line breaks left out; a pair of
    surrogates, on a narrow build, kept as one)."""
    out, seen = [], set()
    i = 0
    text = text or ""
    while i < len(text):
        ch = text[i]
        if 0xD800 <= ord(ch) < 0xDC00 and i + 1 < len(text):
            ch = text[i:i + 2]
            i += 1
        i += 1
        if ch.isspace() or ch in seen:
            continue
        seen.add(ch)
        out.append(ch)
    return out


def code_of(ch):
    if len(ch) == 2:
        return 0x10000 + ((ord(ch[0]) - 0xD800) << 10) + (ord(ch[1]) - 0xDC00)
    return ord(ch)


# The Adobe Glyph List's names of printable ASCII, which glyph_names.json (Glyph Compose's) leaves out
ASCII_NAMES = dict(zip(range(0x20, 0x7F), (
    "space exclam quotedbl numbersign dollar percent ampersand quotesingle parenleft parenright asterisk plus "
    "comma hyphen period slash zero one two three four five six seven eight nine colon semicolon less equal "
    "greater question at A B C D E F G H I J K L M N O P Q R S T U V W X Y Z bracketleft backslash bracketright "
    "asciicircum underscore grave a b c d e f g h i j k l m n o p q r s t u v w x y z braceleft bar braceright "
    "asciitilde").split()))


def name_for(code, font_names, by_code, nice):
    """The font's glyph for a code point, else its usual name (the Adobe Glyph List's for ASCII, Glyphs'
    from glyph_names.json) where the font has no glyph by that name, else uniXXXX (uXXXXX past the BMP)."""
    if code in by_code:
        return by_code[code]
    name = ASCII_NAMES.get(code) or nice.get(code)
    if name and name not in font_names:
        return name
    return ("uni%04X" % code) if code <= 0xFFFF else ("u%05X" % code)


def template_glyphs(chars, font_names=(), by_code=None, nice=None, lacking=None, alternates=0):
    """[(name, label)] of a template: a glyph per character (its name as name_for gives it), those the
    font has with ink left out when lacking holds the names that have it, and each one's alternates
    (name.alt1 to name.altN) after it."""
    by_code = by_code or {}
    nice = nice or {}
    names = set(font_names)
    out = []
    for ch in chars:
        name = name_for(code_of(ch), names, by_code, nice)
        if lacking is None or name not in lacking:
            out.append((name, ch))
        for n in range(1, alternates + 1):
            alt = "%s.alt%d" % (name, n)
            if lacking is None or alt not in lacking:
                out.append((alt, "%s.alt%d" % (ch, n)))
    return out


# ---------------------------------------------------------------------------
# A cell's ink to font units
# ---------------------------------------------------------------------------


def cell_mapping(sheet, i, scale):
    """(units a pixel, x0, y_top) taking a cell image (the drawing box at scale pixels a template
    pixel) to font units: x = x0 + px * units, y = y_top - py * units."""
    units = sheet.metrics.upm / float(sheet.em * scale)
    left, top = sheet.cell(i)
    ox, oy = sheet.origin(i)
    x0 = (left - ox) * sheet.metrics.upm / float(sheet.em)
    y_top = (oy - top) * sheet.metrics.upm / float(sheet.em)
    return units, x0, y_top


def placed(contours, how, upm, sidebearing=EVEN_SIDE):
    """(contours moved, advance) for a glyph: "drawn" keeps the ink where it was drawn against the
    origin line and gives the right side the left side's room; "even" sets both sides to sidebearing
    ems. contours: [[(x, y, kind)]]."""
    xs = [x for c in contours for x, _, _ in c]
    if not xs:
        return contours, int(round(upm * 0.5))
    left, right = min(xs), max(xs)
    if how == "even":
        room = sidebearing * upm
        dx = room - left
        return ([[(x + dx, y, k) for x, y, k in c] for c in contours]), int(round(right - left + 2 * room))
    room = max(0.0, left)
    return contours, int(round(right + room))


def signed_area(points):
    return 0.5 * sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
                     for i in range(len(points)))


def oriented(contours, clockwise_outer):
    """contours turned so that the outermost run clockwise (TrueType) or counterclockwise (PostScript),
    holes the other way, by nesting depth (a contour inside an odd number of others is a hole)."""
    def inside(point, poly):
        x, y = point
        hit = False
        for k in range(len(poly)):
            x1, y1 = poly[k][0], poly[k][1]
            x2, y2 = poly[k - 1][0], poly[k - 1][1]
            if (y1 > y) != (y2 > y) and x < x1 + (x2 - x1) * (y - y1) / float(y2 - y1):
                hit = not hit
        return hit
    out = []
    for i, c in enumerate(contours):
        ons = [p for p in c if p[2] != "off"] or c
        depth = sum(1 for j, other in enumerate(contours) if j != i and inside(ons[0][:2], other))
        hole = depth % 2 == 1
        want_clockwise = clockwise_outer != hole
        is_clockwise = signed_area(c) < 0
        out.append(reverse_contour(c) if is_clockwise != want_clockwise else c)
    return out


def reverse_contour(c):
    """A closed contour [(x, y, kind)] the other way round, its first on-curve node kept first."""
    if not c:
        return c
    rest = list(reversed(c[1:]))
    return [c[0]] + rest


# ---------------------------------------------------------------------------
# The window (FontLab, Qt)
# ---------------------------------------------------------------------------


AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
FONT_CHECK_FILE, FONT_CHECK_MODULE = "freelab_font_check.py", "freelab_font_check"
TRACER_FILE, TRACER_MODULE = "freelab_trace.py", "freelab_trace"
NAMES_FILE = "glyph_names.json"
SETTINGS_FILE = "font_builder.json"
TITLE = "FreeLab Font Builder"
FIND_SIDE = 2400  # an image is looked through for its finder patterns at this many pixels a side, at most
# The guides' color: pale blue. Qt's gray of it, (11 r + 16 g + 5 b) / 32, is GUIDE_GRAY (205); the
# first color, (150, 200, 245), came to 190, not the 205 the documentation said (review 10)
GUIDE_RGB = (170, 215, 250)
TYPED = "Characters typed below"
# The sets listed first, for quick access (each also in the full list after them), as Font Check names them
COMMON_SETS = ("GF Latin Kernel", "GF Latin Core", "GF Latin Plus", "GF Latin Vietnamese", "Adobe Latin 1",
               "Adobe Latin 2", "Adobe Latin 3", "GF Cyrillic Core", "GF Greek Core", "GF Arabic Core", "Hebrew",
               "Devanagari", "Thai", "Hiragana", "Katakana", "Jōyō kanji, 2010 (Unihan kJoyoKanji)",
               "JIS X 0208-1990 (Unihan J0)", "GB/T 2312-1980 (Unihan G0)", "Big Five (Unihan kBigFive)",
               "KS X 1001:2004 hanja (Unihan K0)", "Hangul", "General Punctuation (Unicode block)",
               "Currency Symbols (Unicode block)")


def common_sets(names):
    """The numbers (in names) of the COMMON_SETS there are, in COMMON_SETS' order."""
    where = dict((name, number) for number, name in enumerate(names))
    return [where[name] for name in COMMON_SETS if name in where]


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the shared window helpers."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "FontKerning") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(AUTO_KERNING_MODULE)
            module.__file__ = path
            sys.modules[AUTO_KERNING_MODULE] = module
            with open(path, "rb") as handle:  # open() takes a unicode path through the wide Windows API
                source = handle.read()
            exec(compile(source, AUTO_KERNING_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(AUTO_KERNING_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[AUTO_KERNING_MODULE] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(AUTO_KERNING_MODULE, None)
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def here_path(name):
    return os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), name)


def nice_names():
    """{code point: Glyphs' name} from glyph_names.json beside this script (Glyph Compose's), or {}."""
    try:
        with io.open(here_path(NAMES_FILE), encoding="utf-8") as handle:
            data = json.load(handle)
        return dict((int(code, 16), name) for code, name in data.get("names", {}).items())
    except (IOError, OSError, ValueError):
        return {}


def render_sheet(sheet, QtCore, QtGui):
    """The sheet as an image: white, its cells' boxes and metric lines and labels in pale blue, its
    finders and bands in black."""
    width, height = sheet.size()
    image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
    image.fill(QtGui.QColor(255, 255, 255))
    painter = QtGui.QPainter(image)
    try:
        guide = QtGui.QColor(*GUIDE_RGB)
        thin = QtGui.QPen(guide)
        thin.setWidthF(max(1.0, sheet.em / 400.0))
        base = QtGui.QPen(guide)
        base.setWidthF(max(2.0, sheet.em / 200.0))
        font = QtGui.QFont("Arial")
        font.setPixelSize(max(10, int(sheet.em * LABEL * 0.6)))
        small = QtGui.QFont("Arial")
        small.setPixelSize(max(9, int(sheet.em * LABEL * 0.35)))
        bw, bh = sheet.box_size()
        for i, (name, label) in enumerate(zip(sheet.names, sheet.labels)):
            left, top = sheet.cell(i)
            painter.setPen(thin)
            painter.drawRect(QtCore.QRectF(left, top, bw, bh))
            for key, y in sheet.guides(i):
                painter.setPen(base if key == "baseline" else thin)
                painter.drawLine(QtCore.QPointF(left, y), QtCore.QPointF(left + bw, y))
            ox, _ = sheet.origin(i)
            painter.setPen(thin)
            painter.drawLine(QtCore.QPointF(ox, top), QtCore.QPointF(ox, top + bh))
            painter.setFont(font)
            strip = QtCore.QRectF(left, top - LABEL * sheet.em, bw, LABEL * sheet.em)
            painter.drawText(strip, int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter), label if label != name else "")
            painter.setFont(small)
            painter.drawText(strip, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter), name)
        painter.setFont(small)
        which = ("%s, sheet" % sheet.family) if sheet.family else "Sheet"
        title = "%s %d of %d. Draw in dark ink inside the boxes; keep the corner squares and the bands clean." % (
            which, sheet.index + 1, sheet.count)
        painter.setPen(QtGui.QPen(guide))
        painter.drawText(QtCore.QRectF(sheet.margin(), 0, width - 2 * sheet.margin(), QUIET * sheet.unit * 2.5),
                         int(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter), title)
        u = sheet.unit
        black = QtGui.QColor(0, 0, 0)
        for x, y, w, h in marks(sheet):
            painter.fillRect(QtCore.QRectF(x * u, y * u, w * u, h * u), black)
    finally:
        painter.end()
    return image


def gray_bytes(image, QtGui):
    """(bytes, width, height, stride) of an image in 8-bit gray."""
    import ctypes
    gray = image.convertToFormat(QtGui.QImage.Format_Grayscale8)
    stride = gray.bytesPerLine()
    address = ctypes.addressof(ctypes.c_char.from_buffer(gray.bits()))
    return ctypes.string_at(address, stride * gray.height()), gray.width(), gray.height(), stride, gray


NOT_AN_IMAGE = "not an image FontLab can read"
SVG_NOT_DRAWN = "an SVG drawing FontLab's Qt cannot draw: save the sheet as PNG"


def on_white(image, QtGui):
    """An image with any transparency laid on white paper (a sheet drawn on a clear layer, or an SVG drawn on
    nothing: transparent pixels read as black ink once made gray)."""
    try:
        clear = bool(_value(image, "hasAlphaChannel"))
    except Exception:
        clear = False
    if not clear:
        return image
    out = QtGui.QImage(image.width(), image.height(), QtGui.QImage.Format_RGB32)
    out.fill(QtGui.QColor(255, 255, 255))
    painter = QtGui.QPainter(out)
    try:
        painter.drawImage(0, 0, image)
    finally:
        painter.end()
    return out


def svg_renderer_class(QtGui):
    """Qt's QSvgRenderer where this PythonQt wraps QtSvg (its own module, or among every class), else None."""
    holders = []
    try:
        import PythonQt
        holders += [getattr(PythonQt, "QtSvg", None), getattr(PythonQt, "Qt", None)]
    except Exception:
        pass
    holders.append(QtGui)
    for holder in holders:
        found = getattr(holder, "QSvgRenderer", None) if holder is not None else None
        if found is not None:
            return found
    return None


def read_svg_size(path):
    """svg_size of an SVG file (its root element is near its start), or None."""
    try:
        with io.open(path, "rb") as handle:
            head = handle.read(1 << 16)
    except (IOError, OSError):
        return None
    return svg_size(head.decode("utf-8", "replace"))


def render_svg(path, QtCore, QtGui):
    """(an SVG sheet drawn on white, None), or (None, why): drawn by QtSvg's renderer at the size its viewBox
    gives (a template's own pixels: the resolution it was made at, whatever units a vector app saved it in),
    else read by Qt's SVG image plugin at that size; SHEET_PIXELS_MAX pixels at the most."""
    size = read_svg_size(path)
    renderer_class = svg_renderer_class(QtGui)
    if renderer_class is not None:
        try:
            renderer = renderer_class(path)
            if _value(renderer, "isValid"):
                if size is None:
                    default = _value(renderer, "defaultSize")
                    size = (_value(default, "width"), _value(default, "height"))
                width, height = capped_size(*size)
                image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
                image.fill(QtGui.QColor(255, 255, 255))
                painter = QtGui.QPainter(image)
                try:
                    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                    renderer.render(painter, QtCore.QRectF(0, 0, width, height))
                finally:
                    painter.end()
                return image, None
        except Exception:
            pass  # (the image plugin tried next)
    try:
        reader = QtGui.QImageReader(path)
        if size is not None:
            reader.setScaledSize(QtCore.QSize(*capped_size(*size)))
        image = reader.read()
    except Exception:
        image = QtGui.QImage(path)
    if image is None or image.isNull():
        return None, SVG_NOT_DRAWN
    return on_white(image, QtGui), None


def read_sheet_image(path, QtCore, QtGui):
    """(a sheet's image on white, None), or (None, why it cannot be read): an SVG drawing rendered (render_svg),
    any other file read by Qt's image readers (PNG, JPEG, TIFF, BMP, WebP, PSD where FontLab has their plugins)."""
    if os.path.splitext(path)[1].lower() == ".svg":
        return render_svg(path, QtCore, QtGui)
    image = QtGui.QImage(path)
    if image.isNull():
        return None, NOT_AN_IMAGE
    return on_white(image, QtGui), None


def binarized_rows(data, width, height, stride, threshold=INK_THRESHOLD):
    """Rows of 0 (ink) and 255 (paper) bytes."""
    table = bytes(bytearray(0 if v < threshold else 255 for v in range(256)))
    return [data[y * stride:y * stride + width].translate(table) for y in range(height)]


def find_sheet(image, QtCore, QtGui):
    """(Found, the gray image) of a sheet image, or (None, why)."""
    width, height = image.width(), image.height()
    factor = min(1.0, FIND_SIDE / float(max(width, height)))
    small = image if factor >= 1.0 else image.scaled(int(width * factor), int(height * factor),
                                                       QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
    data, w, h, stride, _ = gray_bytes(small, QtGui)
    rows = binarized_rows(data, w, h, stride)
    corners = corner_finders(find_finders(rows), w, h)
    if corners is None:
        return None, "its four corner squares were not found"
    full, fw, fh, fstride, gray = gray_bytes(image, QtGui)
    scale = 1.0 / factor
    points = [(x * scale, y * scale) for x, y, _, _ in corners]
    units = [module * scale for _, _, module, _ in corners]

    def sample(x, y):
        xi, yi = int(x), int(y)
        if xi < 1 or yi < 1 or xi >= fw - 1 or yi >= fh - 1:
            return 255
        total = 0
        for dy in (-1, 0, 1):
            at = (yi + dy) * fstride + xi - 1
            total += sum(bytearray(full[at:at + 3]))
        return total / 9.0

    found = read_layout(points, units, sample)
    if found is None:
        return None, "its bands could not be read"
    return found, gray


def cell_image(found, i, gray, QtCore, QtGui, scale=1.0):
    """Cell i's drawing box, upright, scale image pixels a template pixel, in 8-bit gray."""
    sheet = found.sheet
    left, top = sheet.cell(i)
    bw, bh = sheet.box_size()
    corners = [(left, top), (left + bw, top), (left + bw, top + bh), (left, top + bh)]
    source = QtGui.QPolygonF([QtCore.QPointF(*found.to_image(x, y)) for x, y in corners])
    out_w, out_h = int(round(bw * scale)), int(round(bh * scale))
    target = QtGui.QPolygonF([QtCore.QPointF(0, 0), QtCore.QPointF(out_w, 0), QtCore.QPointF(out_w, out_h),
                              QtCore.QPointF(0, out_h)])
    transform = QtGui.QTransform()
    if not QtGui.QTransform.quadToQuad(source, target, transform):
        return None
    out = QtGui.QImage(out_w, out_h, QtGui.QImage.Format_Grayscale8)
    out.fill(QtGui.QColor(255, 255, 255))
    painter = QtGui.QPainter(out)
    try:
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        painter.setTransform(transform)
        painter.drawImage(0, 0, gray)
    finally:
        painter.end()
    return out


def ink_image(cell, threshold, QtGui):
    """A cell's drawing as black ink on a clear ground (ARGB): its gray read through alpha_table, so the
    guides and the paper are clear and the ink keeps its soft edges."""
    import ctypes
    data, width, height, stride, _ = gray_bytes(cell, QtGui)
    table = bytes(bytearray(alpha_table(threshold)))
    image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)  # (bytes B, G, R, A: black, its alpha)
    out_stride = image.bytesPerLine()
    address = ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))
    row = bytearray(4 * width)
    for y in range(height):
        # (PythonQt has no setColorTable, live: each row's alphas set in place, every fourth byte)
        row[3::4] = data[y * stride:y * stride + width].translate(table)
        ctypes.memmove(address + y * out_stride, bytes(row), 4 * width)
    return image


def ink_box(data, width, height, stride, threshold):
    """(left, top, right, bottom) in pixels (right and bottom past the last inked pixel) of a cell's
    pixels darker than threshold, or None."""
    table = bytes(bytearray(1 if v < threshold else 0 for v in range(256)))
    left, right, top, bottom = width, 0, None, None
    for y in range(height):
        row = data[y * stride:y * stride + width].translate(table)
        first = row.find(b"\x01")
        if first < 0:
            continue
        last = row.rfind(b"\x01")
        top = y if top is None else top
        bottom = y + 1
        left, right = min(left, first), max(right, last + 1)
    if top is None:
        return None
    return left, top, right, bottom


def has_ink(data, width, height, stride, threshold, least):
    """Whether a cell holds at least least pixels darker than threshold."""
    table = bytes(bytearray(1 if v < threshold else 0 for v in range(256)))
    count = 0
    for y in range(height):
        count += data[y * stride:y * stride + width].translate(table).count(b"\x01")
        if count >= least:
            return True
    return False


HELP = """<b>FreeLab Font Builder</b><br>
Makes template sheets to draw a font's glyphs on, then builds the glyphs from the sheets drawn.<br><br>
<b>Template</b>: pick the glyphs (a character set of Font Check's, the common ones first, which fills
the box with its characters to edit; or characters typed or pasted), and with a font open, whether to
leave out the glyphs it already has drawn; alternates add <i>name.alt1</i> and the like after each. Each
sheet holds the glyphs a sheet you set (100 by default): one image, each glyph in a box with the font's
metric lines (its baseline thicker) and an origin line, in a pale blue that the reading leaves out.
<i>Save template</i> writes one SVG drawing a sheet (the template a locked group, to draw above), or
one image a sheet (PNG or TIFF); the log's link then shows them in their folder. Open them in any app, or
print them; draw each glyph in dark ink inside its box, on the sheet or on a layer above it, and save or
export each sheet again (SVG, PNG, JPEG, TIFF, BMP, WebP, or PSD), or scan or photograph the paper.<br><br>
The corner squares and the two bands of squares tell the reading where the sheet is and what it holds,
so a sheet can be read on another computer than the one that made it, turned, skewed, or photographed;
keep them clean and wholly in the image.<br><br>
<b>Build</b>: add the sheets drawn and click <i>Read sheets</i>: each drawn box is traced into outlines
(or kept as an image, as drawn), and listed. Tick the glyphs to build and click <i>Build ticked
glyphs</i> (one step of FontLab's History). With no font open, building makes a new font, which this
window then works on: the units per em, metrics, and family name of the font that made the sheets.
Then space the glyphs (<i>Auto Spacing</i>) and build the rest (<i>Glyph Compose</i>)."""

# The top line while no font is open, on one line (ak.one_line: owner's images 274 and 280): the window
# hooks to a font it builds too
NO_FONT_TEXT = (u"No font is open. This window hooks to the next font you open (or build here). A template can still "
                u"be made, with default metrics.")
FLOW_SPACING = 16  # pixels between two options of a row that wraps (FlowRow)


def flow_rows(widths, room, spacing=FLOW_SPACING):
    """How many items each line of a row that wraps holds ([5], or [3, 2]): the items in their order, as
    many on a line as room allows (each width, spacing between two), at least one a line. room 0 or less
    (not laid out yet): all on one line. The owner's images 241, 266, and 267: the options and their run
    button on one line where the window is wide enough, wrapped where it is not, nothing lost."""
    widths = [max(0, int(w)) for w in widths]
    if not widths:
        return []
    if room <= 0:
        return [len(widths)]
    counts, used = [], None
    for width in widths:
        if used is not None and used + spacing + width <= room:
            used += spacing + width
            counts[-1] += 1
        else:
            counts.append(1)
            used = width
    return counts


def settings_path(ak):
    return os.path.join(ak.state_dir(), SETTINGS_FILE)


def read_settings(ak):
    try:
        with io.open(settings_path(ak), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def write_settings(ak, data):
    try:
        folder = os.path.dirname(settings_path(ak))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(settings_path(ak), "w", encoding="utf-8") as handle:
            handle.write("%s" % json.dumps(data, indent=1, sort_keys=True))
    except (IOError, OSError):
        pass


def counted(number, one, many=None):
    """"1 glyph", "1,412 glyphs": the count, thousands grouped, with its noun in the right number."""
    return "%s %s" % (grouped(number), one if number == 1 else (many or one + "s"))


def grouped(number):
    return "{:,}".format(int(number))


# The template's file types, the first the save dialog's own (owner's image 374: SVG, which every vector app and
# most drawing apps open, and which Read sheets reads back)
TEMPLATE_FORMATS = ((".svg", "SVG drawings, for vector apps (*.svg)"), (".png", "PNG images (*.png)"),
                    (".tif", "TIFF images (*.tif *.tiff)"))


def template_filter():
    """The save dialog's file types, SVG first."""
    return ";;".join(label for _, label in TEMPLATE_FORMATS)


def template_ext(path):
    """(the path without its extension, the extension the sheets are written with): the one typed where it is
    a template's (.tiff kept), else SVG's."""
    stem, ext = os.path.splitext(path)
    if ext.lower() in (".svg", ".png", ".tif", ".tiff"):
        return stem, ext.lower()
    return (stem if not ext else path), TEMPLATE_FORMATS[0][0]


_TEXT_TYPES = (type(u""), type(b""))


def picked_paths(chosen):
    """The files a file dialog of several gave (getOpenFileNames), as a list of paths: PythonQt gives them as a
    tuple of strings, PyQt and PySide as (the list, the filter chosen), and a dialog of one file a string. The
    tuple of one string had been taken for the PyQt form, and its path read character by character, each a
    sheet "not an image FontLab can read" (owner's image 376)."""
    if not chosen:
        return []
    if isinstance(chosen, _TEXT_TYPES):
        return ["%s" % chosen]
    items = list(chosen)
    if items and not isinstance(items[0], _TEXT_TYPES):
        try:
            items = list(items[0])  # (PyQt's and PySide's form: the files first, then the filter)
        except TypeError:
            return []
    out = []
    for item in items:
        path = "%s" % (item or "")
        if path and path not in out:
            out.append(path)
    return out


def picked_path(chosen):
    """The file a dialog of one file gave (getSaveFileName, getOpenFileName): a string in PythonQt, (the path,
    the filter chosen) in PyQt and PySide; "" when none."""
    if not chosen:
        return ""
    if isinstance(chosen, _TEXT_TYPES):
        return "%s" % chosen
    items = list(chosen)
    return picked_path(items[0]) if items else ""


SVG_UNITS = {"": 1.0, "px": 1.0, "pt": 96 / 72.0, "pc": 16.0, "in": 96.0, "mm": 96 / 25.4, "cm": 96 / 2.54}


def svg_size(text):
    """(width, height) of an SVG drawing in its own units, as read from its root element: its viewBox's (a
    template's are its pixels, kept by the vector apps that draw on it), else its width and height (pixels;
    points, picas, inches, and millimeters at 96 pixels an inch). None when it says neither, or a percentage."""
    root = re.search(r"<svg\b([^>]*)>", text or "", re.S)
    if root is None:
        return None
    attributes = root.group(1)

    def attribute(name):
        found = re.search(r"(?:^|\s)%s\s*=\s*(?:\"([^\"]*)\"|'([^']*)')" % name, attributes)
        return (found.group(1) if found.group(1) is not None else found.group(2)).strip() if found else None

    box = attribute("viewBox")
    if box:
        parts = [p for p in re.split(r"[\s,]+", box) if p]
        try:
            width, height = float(parts[2]), float(parts[3])
            if width > 0 and height > 0:
                return width, height
        except (IndexError, ValueError):
            pass
    sizes = []
    for name in ("width", "height"):
        value = re.match(r"^([0-9.]+(?:[eE][-+]?\d+)?)\s*([a-z]*)$", attribute(name) or "")
        if value is None or value.group(2) not in SVG_UNITS:
            return None
        sizes.append(float(value.group(1)) * SVG_UNITS[value.group(2)])
    return tuple(sizes) if min(sizes) > 0 else None


def capped_size(width, height, most=SHEET_PIXELS_MAX):
    """(width, height) in whole pixels, scaled down (in proportion) to most pixels at the most."""
    scale = min(1.0, math.sqrt(most / float(max(1.0, width * height))))
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def saved_line(ak, paths, one="sheet"):
    """The log's line once files are saved: how many in bold, the folder they are in as a link that shows the
    first selected in a new window of the system's file manager (ak.reveal_link: owner's image 375), then their
    names."""
    folder = os.path.normpath(os.path.dirname(paths[0]))
    link = getattr(ak, "reveal_link", None)
    place = link(paths[0], folder) if link is not None else ak.html(folder)
    return "Saved %s in %s: %s." % (ak.b(counted(len(paths), one)), place,
                                    ak.html(", ".join(os.path.basename(p) for p in paths)))


class Drawn(object):
    """A glyph read from a sheet: its name, label, the file and sheet it came from, and its contours in
    font units (or its image, for images)."""

    def __init__(self, name, label, source, contours=None, image=None, note="", upm=1000, code=None):
        self.name, self.label, self.source = name, label, source
        self.contours = contours or []
        self.image = image  # (QImage, units a pixel, x0, y_top) for images
        self.note = note
        self.upm = upm  # the units of the sheet it was drawn on (the font that made the template)
        # the code point its cell asked for (from its label when not given), or None
        self.code = code if code is not None else cell_code(name, label)


class DrawnNames(object):
    """"name in drawn": whether the font's glyph of that name has something drawn (outlines, components,
    an image) in the current master, asked of each name when first needed and remembered (a CJK font's
    20,000 glyphs are not all read for a template of 100)."""

    def __init__(self, package):
        self.package, self.known = package, {}

    def __contains__(self, name):
        if name not in self.known:
            drawn = False
            try:
                glyph = self.package.findName(name)
                layer = glyph.getLayerByName(self.package.master, False) if glyph is not None else None
                drawn = layer is not None and len(layer.shapes) > 0
            except Exception:
                drawn = False
            self.known[name] = drawn
        return self.known[name]


def _value(widget, name):
    """A Qt property's value: an attribute in PythonQt (a method in some builds)."""
    value = getattr(widget, name)
    return value() if callable(value) else value


class FlowRow(object):
    """A row of options (each a group: a caption and its control, a check box, the run button last) that
    stands on one line where the window is wide enough and wraps onto more lines where it is not
    (flow_rows), in its order, nothing lost or overlapping: the owner's images 241, 266, and 267 ("both
    lines of options could sit on the same line"; on a tiny screen, "wrapping/reflowing" must break
    nothing but the looks). Each line is a box of its own, its groups at the left (a stretch after
    them); a line with no group takes no room. Its width never holds the window wide (Ignored): the
    groups move to the next line instead, once it is resized (on the next turn of the event loop,
    never inside Qt's layout)."""

    def __init__(self, groups, spacing=FLOW_SPACING):
        QtCore, QtGui = _qt()
        self.spacing = spacing
        self.widget = QtGui.QWidget()
        try:
            self.widget.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Preferred)
        except Exception:
            pass
        box = QtGui.QVBoxLayout(self.widget)
        box.setContentsMargins(0, 0, 0, 0)
        self.groups, self.lines, self.counts = [], [], None
        for parts in groups:
            group = QtGui.QWidget()
            inner = QtGui.QHBoxLayout(group)
            inner.setContentsMargins(0, 0, 0, 0)
            for part in parts:
                inner.addWidget(part)
            self.groups.append(group)
            line = QtGui.QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(spacing)
            line.addStretch(1)
            box.addLayout(line)
            self.lines.append(line)
        self.place([len(self.groups)])
        owner = self

        class Resized(QtCore.QTimer):  # (PythonQt has no QObject to subclass; a timer will do)
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize: fitted on the next turn
                        self.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.watch = Resized(self.widget)  # (its parent the row: Qt deletes it with it)
        try:
            self.watch.setSingleShot(True)
            self.watch.setInterval(0)
            self.watch.connect("timeout()", self.fit)
            self.widget.installEventFilter(self.watch)
        except Exception:
            pass

    def place(self, counts):
        """The groups put on the lines counts says (flow_rows), in their order."""
        if counts == self.counts:
            return
        at = 0
        for number, line in enumerate(self.lines):
            for index in range(counts[number] if number < len(counts) else 0):
                group = self.groups[at]
                for other in self.lines:
                    other.removeWidget(group)
                line.insertWidget(index, group)
                at += 1
        self.counts = list(counts)

    def fit(self):
        """The groups on as few lines as the row's width allows. Never raises."""
        try:
            widths = [int(_value(_value(group, "sizeHint"), "width")) for group in self.groups]
            self.place(flow_rows(widths, int(_value(self.widget, "width")), self.spacing))
        except Exception:
            pass


def even_height(bars):
    """The bars (widgets holding a row each; None skipped) given one least height, the tallest's size hint:
    each tab's row above its frame as tall as the others', so switching tabs never shifts the frames
    (round 3's convention 23). The height set, or None where none could be read. Never raises."""
    bars = [bar for bar in bars or () if bar is not None]
    heights = []
    for bar in bars:
        try:
            heights.append(int(_value(_value(bar, "sizeHint"), "height")))
        except Exception:
            continue
    if not heights:
        return None
    tallest = max(heights)
    for bar in bars:
        try:
            if int(_value(bar, "minimumHeight") or 0) != tallest:
                bar.setMinimumHeight(tallest)
        except Exception:
            continue
    return tallest


class FontBuilderDialog(object):
    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle(TITLE)
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = ak.window_layout(dialog)
        self.settings = read_settings(ak)
        try:  # (its no-font line on one line, the only lines allowed to be: owner's images 274 and 280)
            ak.one_line(NO_FONT_TEXT)
        except Exception:
            pass
        # The header, as every window's (owner's images 222, 223, 240): the top line, the template's status
        # under it (the Template tab's: what it holds, or why there is nothing to draw), the header's line
        # (shown even with no font), then the tabs
        self.font_label = ak.status_label()
        self.font_label.setWordWrap(True)
        layout.addWidget(self.font_label)
        self.summary = ak.status_label()
        layout.addWidget(self.summary)
        layout.addWidget(ak.header_separator())
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.addTab("Template")
        self.tabs.addTab("Build")
        # (a right-click on a tab tells of it: owner's image 329)
        self.tabs.setTabWhatsThis(0, u"Makes template sheets to draw the glyphs on, in any app or on paper: a box for "
                                     u"each glyph picked here, shaped by the font's metrics.")
        self.tabs.setTabWhatsThis(1, u"Reads the sheets drawn and builds their glyphs in the font: traced into "
                                     u"outlines, or kept as images.")
        layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.pages.addWidget(self.template_page(QtCore, QtGui))
        self.pages.addWidget(self.build_page(QtCore, QtGui))
        self.log = ak.Log()
        self.log.link_handler = self.log_link  # (a template saved: its folder, the file selected, on a click)
        layout.addWidget(self.log.widget)
        # The bottom row, as every window's (owner's images 258 to 265): the Build tab's committing button at
        # the right, shown with its tab, then Close
        buttons = QtGui.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.build_button)
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.tabs.connect("currentChanged(int)", self.tab_changed)
        self.close_button.connect("clicked()", ak.close_slot(self))
        self.package = None
        self.busy = False
        self.works_without_font = True  # (a template needs no font; building without one makes one)
        self.seen_history = None
        self.drawn = []
        self.read_for = None  # (the font and master the sheets were read for; None: none open)
        self.read_metrics, self.read_family = None, ""  # (the first sheet's: a new font takes them)
        self.filling = False
        self.sets = None  # Font Check's character sets, read when first listed
        ak.add_tools_button(dialog, "Font Builder", self.log)
        ak.plain_buttons(dialog)
        self.read_font()
        self.fill_sets()
        self.update_summary()
        self.tab_changed(0)

    def tab_changed(self, index):
        """A tab shown: its page, its status in the header (the template's on the Template tab only, kept
        hidden as it is written meanwhile by the property that keeps a top line hidden while the busy bar
        stands in for it: ak.status_label), and its button in the bottom row (Build ticked glyphs on the
        Build tab only)."""
        try:
            self.pages.setCurrentIndex(index)
        except Exception:
            pass
        template = index == 0
        try:
            self.summary.setProperty(getattr(self.ak, "BUSY_LINE_PROP", "freelabBusyLine"), None if template else True)
            self.summary.setHidden(not template or not (u"%s" % (_value(self.summary, "text") or u"")).strip())
        except Exception:
            pass
        # (the other tab's buttons hidden before this one's are shown, ak.show_only: shown first, the row held
        # both a moment and Qt widened the window for good, owner's image 284)
        groups = {0: [], 1: [self.build_button]}
        show_only = getattr(self.ak, "show_only", None)
        try:
            if show_only is not None:
                show_only(groups, index)
            else:
                self.build_button.setVisible(not template)
        except Exception:
            pass
        self.even_rows()

    def even_rows(self):
        """The rows above the two tabs' frames (the Template tab's Glyphs dropdown, the Build tab's Add
        sheets... and Clear) made as tall as the taller (even_height): a row of buttons was lower than one
        with a dropdown, so the frame under it moved as the tabs switched (owner's images 285 and 286). At
        each switch, as the window's style may have changed their sizes since. Never raises."""
        even_height([getattr(self, "template_bar", None), getattr(self, "build_bar", None)])

    # -- the template ------------------------------------------------------------

    def template_page(self, QtCore, QtGui):
        page = QtGui.QWidget()
        box = QtGui.QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)  # (its frames in line with the log's: owner's image 268)
        # The row above the tab's frame, in a bar of its own: as tall as the Build tab's (even_rows), so the
        # frames under them never shift as the tabs switch (owner's images 285 and 286)
        bar = self.template_bar = QtGui.QWidget()
        row = QtGui.QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QtGui.QLabel("Glyphs:"))
        self.source = QtGui.QComboBox()
        self.source.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)  # (as wide as its widest item: image 239)
        self.source.setWhatsThis("Where the glyphs come from: the characters typed below, or one of Font Check's "
                                 "character sets (its scripts, Unicode blocks, and foundries' sets; the common ones "
                                 "first, then every set). A set picked fills the box below with its characters; "
                                 "edit them there, and the choice becomes the characters typed.")
        row.addWidget(self.source)
        row.addStretch(1)
        box.addWidget(bar)
        self.typed = QtGui.QPlainTextEdit()
        self.typed.setPlaceholderText(u"Type or paste the characters to draw (each once; spaces do not count)…")
        self.typed.setPlainText(self.settings.get("typed") or "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        self.typed.setWhatsThis("The characters to draw, when the glyphs come from them.")
        box.addWidget(self.typed, 1)
        self.lacking = QtGui.QCheckBox("Leave out the glyphs the font has drawn.")
        self.lacking.setChecked(True)
        self.lacking.setWhatsThis("With a font open: no box for a glyph that has outlines, components, or an image in "
                                  "its current master.")
        self.alternates = QtGui.QSpinBox()
        self.alternates.setRange(0, 9)
        self.alternates.setValue(int(self.settings.get("alternates", 0)))
        self.alternates.setWhatsThis("Boxes for alternates of each glyph (name.alt1, name.alt2, ...), after it: for a "
                                     "handwriting font, Feature Code makes them take turns.")
        self.per_sheet = QtGui.QSpinBox()
        self.per_sheet.setRange(1, PER_SHEET_MAX)
        self.per_sheet.setValue(int(self.settings.get("per_sheet", PER_SHEET)))
        self.per_sheet.setWhatsThis("How many glyphs each sheet holds; there are as many sheets as the glyphs need. "
                                    "A sheet larger than %s megapixels gets fewer." % grouped(SHEET_PIXELS_MAX // 1000000))
        self.em = QtGui.QSpinBox()
        self.em.setRange(EM_PIXELS_RANGE[0], EM_PIXELS_RANGE[1])
        self.em.setSuffix(" px")
        self.em.setValue(int(self.settings.get("em", EM_PIXELS)))
        self.em.setWhatsThis("The em's size on the sheet, in pixels: 500 draws well on a screen; for print, 300 "
                             "pixels a centimeter of em at 300 dpi is about 118, so raise it for small paper sizes.")
        self.save_button = QtGui.QPushButton("Save template...")
        self.save_button.setWhatsThis("Writes the sheets as SVG drawings (the template a locked group, to draw above, "
                                      "in a vector app or any app that opens SVG), or as images (PNG or TIFF), one a "
                                      "sheet, numbered. The log then links to the folder.")
        # The options on one line with the run button at their end (owner's images 241 and 266), wrapping
        # onto the next line where the window is too narrow (FlowRow); the template's status is in the header
        self.template_options = FlowRow([
            [self.lacking], [QtGui.QLabel("Alternates of each:"), self.alternates],
            [QtGui.QLabel("Glyphs a sheet:"), self.per_sheet], [QtGui.QLabel("Em size:"), self.em],
            [self.save_button]])
        box.addWidget(self.template_options.widget)
        self.summary_timer = QtCore.QTimer(page)  # (its parent the page: Qt deletes it with the window)
        self.summary_timer.setSingleShot(True)
        self.summary_timer.setInterval(250)
        self.summary_timer.connect("timeout()", self.update_summary)
        self.source.connect("currentIndexChanged(int)", self.set_chosen)
        self.typed.connect("textChanged()", self.typed_changed)
        self.lacking.connect("toggled(bool)", lambda on: self.update_summary())
        for spin in (self.alternates, self.per_sheet, self.em):
            spin.connect("valueChanged(int)", lambda v: self.update_summary())
        self.save_button.connect("clicked()", self.save_template)
        return page

    def fill_sets(self):
        """The dropdown: the characters typed, the common sets (COMMON_SETS, a quick way to them), a
        separator, then every set of Font Check's, the common ones again among them."""
        QtCore, QtGui = _qt()
        self.source.blockSignals(True)
        self.source.clear()
        self.source.addItem(TYPED)
        try:
            fc = self.ak.load_sibling(FONT_CHECK_FILE, FONT_CHECK_MODULE)
            # (a set's characters are its base ones, made from ranges only when asked for: Han's are
            # 100,000, so a set is counted by its size and listed whole only once picked)
            self.sets = [s for s in fc.load_character_sets() if s.size()]
        except Exception:
            self.sets = []
        common = common_sets([s.name for s in self.sets])
        for number in common:
            self.add_set(number)
        if common:
            self.source.insertSeparator(self.source.count)
        for number in range(len(self.sets)):
            self.add_set(number)
        self.source.blockSignals(False)

    def add_set(self, number):
        s = self.sets[number]
        self.source.addItem("%s (%s)" % (s.name, counted(s.size(), "character")), number)

    def set_number(self, index):
        """The set (its number in self.sets) a dropdown row stands for, or None (the characters typed)."""
        if index <= 0:
            return None
        try:
            value = self.source.itemData(index)
            return int(value) if value is not None and "%s" % value != "" else None
        except (TypeError, ValueError):
            return None

    def set_chosen(self, index):
        """A set picked: its characters fill the box below (each once), where they can be edited; typing
        there makes the choice the characters typed again."""
        number = self.set_number(index)
        if number is None or not self.sets:
            self.summary_soon()
            return
        # (single characters: a letter with marks that has no character of its own is left to Glyph Compose)
        chars = [item for item in self.sets[number].base if len(item) == 1 or
                 (len(item) == 2 and 0xD800 <= ord(item[0]) < 0xDC00)]
        self.filling = True
        try:
            self.typed.setPlainText("".join(chars))
        finally:
            self.filling = False
        self.summary_soon()

    def typed_changed(self):
        if not getattr(self, "filling", False) and self.source.currentIndex != 0:
            self.source.blockSignals(True)
            self.source.setCurrentIndex(0)  # (the set edited: the characters typed now)
            self.source.blockSignals(False)
        self.summary_soon()

    def summary_soon(self):
        """update_summary once typing pauses (a set of 20,000 characters is not counted at each key)."""
        try:
            self.summary_timer.start()
        except Exception:
            self.update_summary()

    def chosen_characters(self):
        return characters_of("%s" % self.typed.toPlainText())

    def font_glyphs(self):
        """({name: its code points}, {code: name}, DrawnNames) of the font, or empty ones."""
        if self.package is None:
            return {}, {}, set()
        codes_of, by_code = {}, {}
        for fg in self.package.fgPackage.glyphs:
            name = "%s" % fg.name
            try:
                codes = list(fg.unicodes or [])
            except Exception:
                codes = []
            codes_of[name] = codes
            for code in codes:
                by_code.setdefault(code, name)
        return codes_of, by_code, DrawnNames(self.package)

    def planned(self):
        names, by_code, drawn = self.font_glyphs()
        return template_glyphs(self.chosen_characters(), names, by_code, nice_names(),
                               drawn if (self.lacking.checked and self.package is not None) else None,
                               self.alternates.value)

    def metrics(self):
        p = self.package
        if p is None:
            return Metrics()
        try:
            return Metrics(p.upm, p.ascender_value, p.descender_value, p.xHeight_value, p.capsHeight_value)
        except Exception:
            return Metrics(p.upm, 0.8 * p.upm, -0.2 * p.upm, 0.5 * p.upm, 0.7 * p.upm)

    def sheets(self):
        glyphs = self.planned()
        family = ""
        try:
            family = self.package.info.familyName if self.package is not None else ""
        except Exception:
            pass
        return split_sheets([n for n, _ in glyphs], [l for _, l in glyphs], self.metrics(), self.per_sheet.value,
                            self.em.value, family)

    def update_summary(self):
        try:
            glyphs = self.planned()
            if not glyphs:
                self.summary.setText("No glyph to draw: pick a set or type characters%s." % (
                    ", or let the template hold the glyphs the font has" if self.lacking.checked and self.package else ""))
                self.ak.enable(self.save_button, False)
                return
            sheets = self.sheets()
            w, h = sheets[0].size()
            b = self.ak.b  # (counts with their nouns in bold: owner's convention 8)
            self.summary.setText("%s on %s of %s by %s pixels (%s megapixels)." % (
                b(counted(len(glyphs), "glyph")), b(counted(len(sheets), "sheet")), grouped(w), grouped(h),
                "%.1f" % (w * h / 1e6)))
            self.ak.enable(self.save_button, True)
        except Exception as exc:
            self.summary.setText("The template cannot be made: %s" % self.ak.html("%s" % exc))
            self.ak.enable(self.save_button, False)

    def save_template(self):
        QtCore, QtGui = _qt()
        sheets = self.sheets()
        folder = self.settings.get("folder") or os.path.expanduser("~")
        base = (sheets[0].family or "template").replace(" ", "-")
        # (SVG first, the name ending in it: the dialog's type is SVG unless another is picked, owner's image 374)
        chosen = QtGui.QFileDialog.getSaveFileName(self.dialog, "Save the template",
                                                   os.path.join(folder, base + TEMPLATE_FORMATS[0][0]), template_filter())
        path = picked_path(chosen)
        if not path:
            return
        stem, ext = template_ext(path)
        self.settings.update({"folder": os.path.dirname(path), "typed": "%s" % self.typed.toPlainText(),
                              "alternates": self.alternates.value, "per_sheet": self.per_sheet.value, "em": self.em.value})
        write_settings(self.ak, self.settings)
        written = []
        self.busy = True
        self.ak.busy_start(self, "Saving the template")
        try:
            self.write_sheets(sheets, stem, ext, written)
        except self.ak.Stopped:
            self.log.add("Saving was stopped after %s." % self.ak.b(counted(len(written), "sheet")), "warning")
            return
        finally:
            self.busy = False
            self.ak.busy_end(self)
        if written:
            self.log.add(saved_line(self.ak, written), "done")

    def log_link(self, target):
        """A link of the log clicked: a file saved (ak.reveal_link) shown selected in its folder; any other
        left to the log (False)."""
        reveal = getattr(self.ak, "reveal_clicked", None)
        return reveal(target, self.log) if reveal is not None else False

    def write_sheets(self, sheets, stem, ext, written):
        """Each sheet written (its path added to written); stops at the first that cannot be."""
        QtCore, QtGui = _qt()
        for sheet in sheets:
            self.ak.busy_progress(self, "Saving sheet %d of %d" % (sheet.index + 1, len(sheets)),
                                  sheet.index / float(len(sheets)))
            name = stem + ("-%d-of-%d" % (sheet.index + 1, sheet.count) if sheet.count > 1 else "") + ext
            if ext == ".svg":
                try:
                    with io.open(name, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(sheet_svg(sheet, GUIDE_RGB))
                except (IOError, OSError):
                    self.log.add("%s could not be written." % self.ak.html(name), "error")
                    return
                written.append(name)
                continue
            image = render_sheet(sheet, QtCore, QtGui)
            if not image.save(name):
                self.log.add("%s could not be written." % self.ak.html(name), "error")
                return
            written.append(name)

    # -- building ------------------------------------------------------------------

    def build_page(self, QtCore, QtGui):
        page = QtGui.QWidget()
        box = QtGui.QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)  # (its lists' frames in line with the log's: owner's image 268)
        bar = self.build_bar = QtGui.QWidget()  # (as tall as the Template tab's row: even_rows)
        row = QtGui.QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        self.add_button = QtGui.QPushButton("Add sheets...")
        self.add_button.setWhatsThis("Adds sheets drawn to read: images (PNG, JPEG, TIFF, BMP, WebP, PSD) or SVG "
                                     "drawings.")
        self.clear_button = QtGui.QPushButton("Clear")
        self.clear_button.setWhatsThis("Takes every sheet and glyph off the lists.")
        row.addWidget(self.add_button)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        box.addWidget(bar)
        self.sheet_list = QtGui.QTreeWidget()
        self.sheet_list.setHeaderLabels(["File", "Sheet", "Glyphs", "Read"])
        self.sheet_list.setRootIsDecorated(False)
        self.sheet_list.setWhatsThis("The sheets added: which sheet each is, how many glyphs it holds, and whether it "
                                     "was read.")
        self.ak.table_layout(self.sheet_list, stretch=3)  # (FreeLab's one list layout: headers centered, no light lines)
        box.addWidget(self.sheet_list, 1)
        self.mode = QtGui.QComboBox()
        self.mode.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.mode.addItem("Outlines (traced)")
        self.mode.addItem("Images (as drawn)")
        self.mode.setWhatsThis("Outlines: each drawing traced into contours, nodes at extremes. Images: each kept as "
                               "drawn, an image in the glyph (a bitmap or color font, or to trace by hand).")
        self.threshold = QtGui.QSpinBox()
        self.threshold.setRange(1, THRESHOLD_MAX)  # (higher, the guides would count as ink)
        self.threshold.setValue(min(THRESHOLD_MAX, int(self.settings.get("threshold", INK_THRESHOLD))))
        self.threshold.setWhatsThis("What counts as ink: pixels darker than this gray (0 black, 255 white). Raise it for "
                                    "pencil or light ink, lower it for a gray paper; up to %d, so the guides (gray "
                                    "%d) always stay out." % (THRESHOLD_MAX, GUIDE_GRAY))
        self.placement = QtGui.QComboBox()
        self.placement.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.placement.addItem("Where drawn")
        self.placement.addItem("With even sidebearings")
        # (no space before the percent sign: owner's image 216)
        self.placement.setWhatsThis("Where drawn: the ink stays where it was drawn against the box's origin line, the "
                                    "right side given the left side's room. Even: both sides %d%% of the em. Either "
                                    "way, <i>Auto Spacing</i> spaces them better after." % int(round(EVEN_SIDE * 100)))
        self.replace = QtGui.QCheckBox("Replace glyphs the font has drawn.")
        self.replace.setWhatsThis("Off: a glyph that has outlines, components, or an image in the current master is "
                                  "listed unticked and left as it is unless you tick it.")
        self.read_button = QtGui.QPushButton("Read sheets")
        self.read_button.setWhatsThis("Reads every sheet added: finds it in its image, and traces each drawn box.")
        # The options on one line with Read sheets at their end (owner's image 267), wrapping where the window
        # is too narrow (FlowRow)
        self.build_options = FlowRow([
            [QtGui.QLabel("Make:"), self.mode], [QtGui.QLabel("Ink darker than:"), self.threshold],
            [QtGui.QLabel("Glyphs placed:"), self.placement], [self.replace], [self.read_button]])
        box.addWidget(self.build_options.widget)
        self.glyph_list = QtGui.QTreeWidget()
        self.glyph_list.setHeaderLabels(["Glyph", "From", "Read"])
        self.glyph_list.setRootIsDecorated(False)
        self.glyph_list.setIconSize(QtCore.QSize(*self.ak.glyph_icon_size(1)))
        self.glyph_list.setWhatsThis("The glyphs read: as traced, the sheet each came from, and what was read. Ticked "
                                     "ones are built.")
        # (left alone by dark mode, its pictures drawn in the window's text color: mapped as one of FontLab's
        # lists, each picture came out twice, the second cut off and outlined; owner's image 168)
        self.ak.table_layout(self.glyph_list, stretch=2)
        box.addWidget(self.glyph_list, 2)
        # (in the window's bottom row, at its right, shown with this tab: owner's images 258 to 265)
        self.build_button = QtGui.QPushButton("Build ticked glyphs")
        self.build_button.setWhatsThis("Writes the ticked glyphs into the current master (new glyphs added with their "
                                       "code points), as one step of FontLab's History. With no font open, makes a new "
                                       "font first, which this window then works on: the units per em, metrics, and "
                                       "family name of the font that made the sheets.")
        self.files = []
        self.add_button.connect("clicked()", self.add_sheets)
        self.clear_button.connect("clicked()", self.clear_sheets)
        self.read_button.connect("clicked()", self.read_sheets)
        self.build_button.connect("clicked()", self.build_glyphs)
        self.glyph_list.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons())
        return page

    def add_sheets(self):
        QtCore, QtGui = _qt()
        folder = self.settings.get("read_folder") or self.settings.get("folder") or os.path.expanduser("~")
        chosen = QtGui.QFileDialog.getOpenFileNames(self.dialog, "Add sheets drawn", folder,
                                                    "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp *.psd *.svg)")
        paths = picked_paths(chosen)
        if not paths:
            return
        self.settings["read_folder"] = os.path.dirname(paths[0])
        write_settings(self.ak, self.settings)
        for path in paths:
            if path not in self.files:
                self.files.append(path)
                self.sheet_list.addTopLevelItem(QtGui.QTreeWidgetItem([os.path.basename(path), "", "", "not yet"]))
        self.update_buttons()

    def clear_sheets(self):
        self.files, self.drawn = [], []
        self.sheet_list.clear()
        self.glyph_list.clear()
        self.update_buttons()

    def tracer(self):
        return self.ak.load_sibling(TRACER_FILE, TRACER_MODULE)

    def read_sheets(self):
        QtCore, QtGui = _qt()
        if self.busy or not self.files:
            return
        self.settings["threshold"] = self.threshold.value
        write_settings(self.ak, self.settings)
        self.busy = True
        self.update_buttons()
        images = self.mode.currentIndex == 1
        threshold = self.threshold.value
        tracer = None
        if not images:
            try:
                tracer = self.tracer()
            except Exception as exc:
                self.log.add("The tracer did not load: %s" % self.ak.html("%s" % exc), "error")
                self.busy = False
                self.update_buttons()
                return
        self.drawn = []
        self.read_metrics, self.read_family = None, ""
        self.read_for = self.target_key()  # (the lists stand for this font and master: build_glyphs checks)
        nice = nice_names()
        seen = {}
        self.ak.busy_start(self, "Reading the sheets")
        try:
            for row, path in enumerate(self.files):
                item = self.sheet_list.topLevelItem(row)
                item.setText(3, "reading")
                self.ak.busy_progress(self, "Reading sheet %d of %d" % (row + 1, len(self.files)),
                                      row / float(len(self.files)))
                image, why = read_sheet_image(path, QtCore, QtGui)
                if image is None:
                    item.setText(3, why)
                    continue
                found, gray = find_sheet(image, QtCore, QtGui)
                if found is None:
                    item.setText(3, "not read: %s" % gray)
                    continue
                sheet = found.sheet
                if self.read_metrics is None:  # (a new font, built with no font open, takes the first sheet's)
                    self.read_metrics, self.read_family = sheet.metrics, sheet.family
                item.setText(1, "%d of %d" % (sheet.index + 1, sheet.count))
                item.setText(2, "%d" % len(sheet.names))
                # (each box at the image's own resolution: its em in pixels as the image shows it)
                tl = found.to_image(*sheet.cell(0))
                tr = found.to_image(sheet.cell(0)[0] + sheet.em, sheet.cell(0)[1])
                scale = max(0.5, min(3.0, math.hypot(tr[0] - tl[0], tr[1] - tl[1]) / float(sheet.em)))
                drawn_here = 0
                for i, (name, label) in enumerate(zip(sheet.names, sheet.labels)):
                    if i % 4 == 0:
                        item.setText(3, "%d of %d boxes" % (i, len(sheet.names)))
                        self.ak.busy_progress(self, None, (row + i / float(max(1, len(sheet.names)))) / len(self.files))
                    cell = cell_image(found, i, gray, QtCore, QtGui, scale)
                    if cell is None:
                        continue
                    data, w, h, stride, cell = gray_bytes(cell, QtGui)
                    if not has_ink(data, w, h, stride, threshold, max(20, int(w * h * 0.0005))):
                        continue
                    units, x0, y_top = cell_mapping(sheet, i, scale)
                    source = "%s (%d of %d)" % (os.path.basename(path), sheet.index + 1, sheet.count)
                    if images:
                        # (cropped to its ink, two pixels around: the glyph's width is its ink's)
                        box = ink_box(data, w, h, stride, threshold)
                        left, top = max(0, box[0] - 2), max(0, box[1] - 2)
                        right, bottom = min(w, box[2] + 2), min(h, box[3] + 2)
                        cropped = cell.copy(QtCore.QRect(left, top, right - left, bottom - top))
                        self.drawn.append(Drawn(name, label, source,
                                                image=(cropped, units, x0 + left * units, y_top - top * units),
                                                upm=sheet.metrics.upm, code=cell_code(name, label, nice)))
                    else:
                        contours = trace_cell(tracer, data, w, h, stride, threshold, units, x0, y_top, sheet.em * scale)
                        self.drawn.append(Drawn(name, label, source, contours=contours,
                                                note=counted(len(contours), "contour"), upm=sheet.metrics.upm,
                                                code=cell_code(name, label, nice)))
                    if name in seen:
                        self.drawn[-1].note += "; also on %s" % seen[name]
                    seen[name] = source
                    drawn_here += 1
                item.setText(3, "%s drawn" % counted(drawn_here, "box", "boxes"))
        except self.ak.Stopped:
            self.log.add("Reading was stopped: the glyphs read so far are listed.", "warning")
        except Exception as exc:
            self.log.add("Reading stopped on an error: %s" % self.ak.html("%s" % exc), "error")
        finally:
            self.busy = False
            self.ak.busy_end(self)
        self.show_drawn()
        self.log.add("Read %s from %s." % (self.ak.b(counted(len(self.drawn), "drawn glyph")),
                                           self.ak.b(counted(len(self.files), "sheet"))))
        self.update_buttons()

    def show_drawn(self):
        QtCore, QtGui = _qt()
        self.glyph_list.blockSignals(True)
        self.glyph_list.clear()
        codes_of, by_code, drawn_in_font = self.font_glyphs()
        targets = {}  # {target: how many rows go into it}
        for d in self.drawn:
            target = target_name(d.name, d.code, by_code, codes_of)
            targets[target] = targets.get(target, 0) + 1
        for index, d in enumerate(self.drawn):
            note = d.note
            target = target_name(d.name, d.code, by_code, codes_of)
            if target is None:
                note = (note + "; " if note else "") + "no glyph to go into: %s is another character's" % d.name
                target = d.name
            elif target != d.name:
                note = (note + "; " if note else "") + "into %s" % target
            if targets.get(target, 0) > 1:
                note = (note + "; " if note else "") + "drawn more than once: the first ticked is built"
            exists = target in drawn_in_font
            if exists:
                note = (note + "; " if note else "") + "the font has it drawn"
            item = QtGui.QTreeWidgetItem(["%s  %s" % (d.label, target) if d.label != target else target, d.source, note])
            item.setData(0, QtCore.Qt.UserRole, index)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if (not exists or self.replace.checked) else QtCore.Qt.Unchecked)
            icon = self.drawn_icon(d)
            if icon is not None:
                item.setIcon(0, icon)
            self.glyph_list.addTopLevelItem(item)
        self.glyph_list.blockSignals(False)

    def drawn_icon(self, d):
        """A row's picture of a drawing: on its baseline, at the size every FreeLab list draws glyphs
        (Glyph Compose's), in the window's text color on nothing (inked: redrawn in the new color when dark
        mode switches), as the glyph will stand in the font."""
        QtCore, QtGui = _qt()
        width, height = self.ak.glyph_icon_size(1)
        size = int(round(height / 1.45))
        scale = float(size) / float(d.upm or 1000)
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        pix = QtGui.QPixmap(width, height)
        pix.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pix)
        try:  # (ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            if d.image is not None:
                cell, units, x0, y_top = d.image
                ink = ink_image(cell, self.threshold.value, QtGui)
                tinted = QtGui.QImage(ink.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
                tinted.fill(QtGui.QColor(0, 0, 0, 0))
                inner = QtGui.QPainter(tinted)
                try:
                    inner.drawImage(0, 0, ink)
                    inner.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
                    inner.fillRect(tinted.rect(), color)
                finally:
                    inner.end()
                left = min(0.0, x0)
                box = QtCore.QRectF(4 + (x0 - left) * scale, size * 1.1 - y_top * scale,
                                    cell.width() * units * scale, cell.height() * units * scale)
                painter.drawImage(box, tinted)
            elif d.contours:
                path = contours_path(d.contours, QtGui, QtCore)
                left = min(0.0, path.boundingRect().left())
                painter.translate(4 - left * scale, size * 1.1)
                painter.scale(scale, -scale)
                painter.fillPath(path, QtGui.QBrush(color))
        finally:
            painter.end()
        return self.ak.icon_of(self.ak.inked(pix, color))

    def checked_drawn(self):
        QtCore, QtGui = _qt()
        out = []
        for row in range(self.glyph_list.topLevelItemCount):
            item = self.glyph_list.topLevelItem(row)
            if item.checkState(0) == QtCore.Qt.Checked:
                out.append(self.drawn[int(item.data(0, QtCore.Qt.UserRole))])
        return out

    def build_glyphs(self):
        QtCore, QtGui = _qt()
        if self.busy:
            return
        chosen = self.checked_drawn()
        package = self.current_font()
        if not chosen:
            return
        if package is None and getattr(self, "read_for", None) is None:
            # No font open, nor when the sheets were read: a new font, its units, metrics, and name the
            # sheets' (the font that made the template), the glyphs laid out in it as drawn
            package = self.new_font()
            if package is None:
                return
            self.read_for = self.target_key(package)
        if package is None:
            self.log.add("The font the sheets were read for was closed: open a font, or click <i>Read sheets</i> "
                         "again to build a new one. Nothing was built.", "warning")
            return
        if self.target_key(package) != getattr(self, "read_for", None):
            # (the checks were made for another font or master: its glyphs drawn then are not these;
            # review 9)
            self.log.add("The font or master changed since the sheets were read: click <i>Read sheets</i> again. "
                         "Nothing was built.", "warning")
            return
        self.package = package
        master = package.master
        codes_of, by_code, drawn_now = self.font_glyphs()  # (read again: the font may have changed since)
        if not self.ak.begin_write(self.fontlab, package, TITLE, self.log, coverage=True):  # (the font info follows)
            return
        added, rebuilt, touched, kept, unencoded, twice, nowhere, error = [], [], [], [], [], [], [], None
        clockwise_outer = not is_postscript(package)
        how = "even" if self.placement.currentIndex == 1 else "drawn"
        given = set()  # (code points given in this build: one glyph each)
        written = set()  # (each glyph written once a build: a second drawing of it is left out; review 10)
        self.busy = True
        self.ak.busy_start(self, "Building the glyphs", stoppable=False)  # (one History step: never half)
        try:
            for number, d in enumerate(chosen):
                if number % 8 == 0:
                    self.ak.busy_progress(self, None, number / float(len(chosen)), stoppable=False)
                target = target_name(d.name, d.code, by_code, codes_of)
                if target is None:
                    nowhere.append(d.name)  # (its name is another character's glyph, and so is uniXXXX)
                    continue
                if target in written:
                    twice.append(target)
                    continue
                if target in drawn_now and not self.replace.checked:
                    kept.append(target)  # (drawn in the font: replaced only with Replace on)
                    continue
                factor = float(package.upm) / float(d.upm or package.upm)  # (the sheet's units to the font's)
                # (the drawing made first, the glyph touched after: an image that failed had left its glyph
                # emptied, live)
                if d.image is not None:
                    shape, advance = self.image_shape(d, factor, how)
                else:
                    scaled = [[(x * factor, y * factor, k) for x, y, k in c] for c in d.contours]
                    contours, advance = placed(oriented(scaled, clockwise_outer), how, package.upm)
                    shape = self.fontlab.flShape()
                    shape.addContours([made_contour(self.fontlab, c, QtCore) for c in contours], True)
                glyph = package.findName(target)
                new = glyph is None
                if new:
                    made = self.fontlab.flGlyph()
                    made.name = target
                    held = getattr(sys, "_freelab_made_glyphs", None)
                    if held is None:
                        held = sys._freelab_made_glyphs = {}
                    held.setdefault(getattr(package.fgPackage, "id", None), []).append(made)
                    package.addGlyph(made)
                    glyph = package.findName(target)
                    if glyph is None:
                        raise RuntimeError("FontLab did not add %s" % target)
                layer = glyph.getLayerByName(master, True)
                if new:
                    layer.setGlyphComponents([], float(package.upm) / 2, package, False)
                layer.removeAllShapes()
                layer.addShape(shape)
                layer.advanceWidth = float(advance)
                if d.code is not None and not codes_of.get(target):
                    # (a new glyph, or one of the font with no code point, takes its cell's character, unless
                    # another glyph has it: never two)
                    if d.code in by_code or d.code in given:
                        unencoded.append(target)
                    else:
                        glyph.fgGlyph.unicode = d.code
                        given.add(d.code)
                        by_code[d.code], codes_of[target] = target, [d.code]  # (a later drawing of it goes here)
                (added if new else rebuilt).append(target)
                codes_of.setdefault(target, [])
                written.add(target)
                touched.append(glyph)
        except Exception as exc:
            error = exc
        status = self.ak.notify_changed(self.fontlab, package, TITLE, touched, added=bool(added), coverage=True)
        self.busy = False
        self.ak.busy_end(self)
        if added or rebuilt:
            parts = []
            if added:
                parts.append("built %s" % self.ak.b(counted(len(added), "new glyph")))
            if rebuilt:
                parts.append("redrew %s" % self.ak.b(counted(len(rebuilt), "glyph")))
            done = " and ".join(parts)
            self.log.add("%s%s.%s" % (done[0].upper(), done[1:], status.undo(" <i>Edit &gt; Undo</i> takes it back.")),
                         "done")
        status.report(self.log)
        if kept:
            self.log.add("Left as drawn in the font (turn on <i>Replace glyphs the font has drawn</i> to redraw them): "
                         "%s." % self.ak.html(", ".join(kept)), "warning")
        if unencoded:
            self.log.add("Left without a code point, since another glyph of the font has it: %s." %
                         self.ak.html(", ".join(unencoded)), "warning")
        if twice:
            self.log.add("Drawn more than once among the ticked: built from the first, the others left out: %s." %
                         self.ak.html(", ".join(sorted(set(twice)))), "warning")
        if nowhere:
            self.log.add("Not built, since the font's glyphs of these names are other characters' (and so are their "
                         "uniXXXX names): %s." % self.ak.html(", ".join(nowhere)), "warning")
        if error is not None:
            self.log.add("Stopped by an error: %s" % self.ak.html("%s" % error), "error")
        self.show_drawn()

    def new_font(self):
        """A new font in FontLab, open in its own window: the units per em, ascender, descender, x-height,
        cap height, and family name of the sheets read (the font that made them), its one master Regular.
        None, logged, where FontLab refused."""
        metrics = getattr(self, "read_metrics", None) or Metrics()
        family = (getattr(self, "read_family", "") or "").strip() or "Untitled"
        fl = self.fontlab
        try:
            package = fl.flPackage()  # (FontLab adds it to its workspace, current)
            try:
                if int(round(package.upm)) != int(metrics.upm):
                    package.setUpm(int(metrics.upm), False)
            except Exception:
                pass
            if not list(package.masters or []):
                package.addMaster("Regular", False, package, "", False, False)  # (a font as its source: None was refused live)
            if not package.master:
                package.setMaster(list(package.masters)[0])  # (flPackage.master is read-only: live, 2026-11-18)
            for attr, value in (("ascender_value", metrics.ascender), ("descender_value", metrics.descender),
                                ("xHeight_value", metrics.x_height), ("capsHeight_value", metrics.cap_height)):
                try:
                    setattr(package, attr, float(value))
                except Exception:
                    pass
            try:
                package.info.familyName = family
            except Exception:
                pass
            try:
                package.updateFontMetrics()
            except Exception:
                pass
            try:
                fl.flItems.notifyPackageAdded(package)  # (its font window opens)
            except Exception:
                pass
        except Exception as exc:
            self.log.add("FontLab did not make a new font: %s. Open a font (<i>File &gt; New</i>), then build "
                         "again." % self.ak.html("%s" % exc), "error")
            return None
        self.package = package
        self.log.add(new_font_line(self.ak, family, metrics.upm), "done")
        self.hook_built_font(package)
        try:
            self.font_label.setText(font_text(self.ak, package, family))
        except Exception:
            pass
        return package

    def hook_built_font(self, package):
        """The new font this window built is its font from now on (owner's images 274 and 280: "This window
        hooks to the next font you open (or build here)"): taken as a window without a font takes the font
        opened (ak.window_font: its registry, its title), at once rather than at the next look at the fonts,
        and only while FontLab shows that font (it adds a new font as the current one): never another.
        True when it took it. Never raises."""
        try:
            if getattr(self, "font_id", None) is not None:
                return False  # (a window that has a font keeps it)
            workspace = self.fontlab.flWorkspace.instance()
            if workspace.currentPackage.fgPackage.id != package.fgPackage.id:
                return False  # (left to the shared module's watch of the fonts)
            taken = self.current_font()
            if taken is None or taken.fgPackage.id != package.fgPackage.id:
                return False
            self.package = taken
        except Exception:
            return False
        try:
            self.summary_soon()  # (the template now takes its metrics, and leaves out what it has drawn)
        except Exception:
            pass
        return True

    def image_shape(self, d, factor, how):
        """(an image glyph's shape, its advance): the drawing's ink in black on clear (alpha_table at the
        threshold set), placed as outlines are, in the font's units."""
        QtCore, QtGui = _qt()
        cell, units, x0, y_top = d.image
        units, x0, y_top = units * factor, x0 * factor, y_top * factor
        ink = ink_image(cell, self.threshold.value, QtGui).mirrored(False, True)  # (FontLab keeps rows bottom-up)
        shape = self.fontlab.flShape(ink)
        # (placed as outlines are: its box's corners stand for its ink)
        corners = [[(x0, y_top - cell.height() * units, "on"), (x0 + cell.width() * units, y_top, "on")]]
        moved, advance = placed(corners, how, self.package.upm)
        left = moved[0][0][0]
        shape.transform = QtGui.QTransform(units, 0, 0, units, left, y_top - cell.height() * units)
        return shape, advance

    def target_key(self, package=None):
        """(the font, its master) the lists are for, or None."""
        package = package if package is not None else self.package
        if package is None:
            return None
        try:
            return self.ak.font_key(package), package.master
        except Exception:
            return None

    # -- the font, the buttons ---------------------------------------------------------

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = self.ak.window_font(self, workspace)
        if package is None or package.isNull:
            return None
        return package

    def read_font(self):
        self.package = self.current_font()
        if self.package is None:
            self.font_label.setText(no_font_text(self.ak))
        else:
            self.font_label.setText(font_text(self.ak, self.package))
        self.update_buttons()

    def font_changed(self):
        self.read_font()
        self.update_summary()

    def history_moved(self):
        pass

    def update_buttons(self):
        busy = self.busy
        self.ak.enable(self.lacking, self.package is not None)  # (no font: nothing drawn to leave out)
        self.ak.enable(self.read_button, bool(self.files) and not busy)
        self.ak.enable(self.clear_button, bool(self.files) and not busy)
        # (no font open, nor when the sheets were read: building makes a new font)
        can_build = self.package is not None or getattr(self, "read_for", None) is None
        self.ak.enable(self.build_button, bool(self.checked_drawn()) and can_build and not busy)

    def show(self):
        self.dialog.show()
        self.dialog.raise_()
        self.even_rows()  # (again in the window's own style, now that it shows)


def new_font_line(ak, family, upm):
    """The log's line once a new font is made: its name in bold, its units per em counted in bold with
    their noun ("**1,000 units** per em", round 3's rule: the number alone was plain)."""
    return "Made a new font, %s: %s per em, the sheets' metrics." % (ak.b(family), ak.b(counted(int(upm), "unit")))


def no_font_text(ak):
    """The top line with no font open: NO_FONT_TEXT, on one line; while fonts are open that each have a
    window (the shared no_font_line says why this one has none), that line, then what a template still
    takes."""
    try:
        line = ak.no_font_line(NO_FONT_TEXT)
    except TypeError:  # (a shared module from before own lines)
        line = ak.no_font_line()
    if line == NO_FONT_TEXT:
        return line
    return line + " A template can still be made, with default metrics."


def font_text(ak, package, family=""):
    """The top line with a font: its name and master, as every window's (ak.font_named), and what the
    font is for here."""
    name = package.tfn or family
    try:
        masters = len(list(package.masters or []))
    except Exception:
        masters = 1
    try:
        start = ak.font_named(name, package.master, masters)
    except Exception:
        start = "%s, master %s" % (ak.b(name), ak.b(package.master))
    return "%s: its metrics shape the template's boxes." % start  # (after "(of 3 masters)": no second parentheses)


def is_postscript(package):
    """Whether the font's outlines run the PostScript way (outer contours counterclockwise): read from its
    first drawn glyph, else assumed TrueType's (FontLab's default for a new font: cubic, clockwise)."""
    for number, fg in enumerate(package.fgPackage.glyphs):
        if number >= 300:
            break  # (no drawn glyph among the first 300: taken for TrueType's)
        try:
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(package.master, False)
            polygons = [[(n.x, n.y) for n in c.nodes()] for shape in layer.shapes for c in shape.contours
                        if c is not None and c.nodesCount > 2]
        except Exception:
            continue
        if polygons:  # (its largest contour: an outer one)
            return signed_area(max(polygons, key=lambda p: abs(signed_area(p)))) > 0
    return False


def cell_code(name, label, nice=None):
    """The code point a cell's glyph is for: its label's character (a template names the character it
    asks for, whatever the glyph's name: a font's customA, or A.display, for A keeps U+0041; reviews 9
    and 10), none for an alternate (its label is "a.alt1", no single character), else what the name says
    (code_for)."""
    if len(label) == 1 or (len(label) == 2 and 0xD800 <= ord(label[0]) < 0xDC00):
        return code_of(label)
    return code_for(name, nice or {})


def target_name(name, code, by_code, codes_of=None):
    """The destination glyph a cell is drawn into, or None where there is none it may go into: the one
    that has its code point, where one does (a sheet made from another font names its A "A"; this
    font's may be "uni0041"); else a glyph of its own name, unless that glyph is for another character
    (a source font's B for A, here B at U+0042; review 10), then its uniXXXX name, if that is free too.
    codes_of: {name: [its code points]} of the font."""
    if code is not None and code in by_code:
        return by_code[code]
    codes_of = codes_of or {}
    held = codes_of.get(name)
    if code is None or not held or code in held:
        return name
    fallback = ("uni%04X" % code) if code <= 0xFFFF else ("u%05X" % code)
    other = codes_of.get(fallback)
    return fallback if not other or code in other else None


def alpha_table(threshold):
    """[256 alphas] of an image glyph's ink by gray: opaque up to half the threshold, clear from halfway
    between it and white (the guides, about 205, and scanned paper fall there at the default 128), and
    fading between, so the ink keeps its soft edges (review 9: every gray pixel was made ink)."""
    low = threshold / 2.0
    # (clear 15 grays under the guides at the most: at 180, halfway to white was 217, and a guide's 205
    # came back as faint ink; review 10)
    high = max(threshold + 1.0, min(threshold + (255 - threshold) / 2.0, GUIDE_GRAY - 15.0))
    out = []
    for g in range(256):
        if g <= low:
            out.append(255)
        elif g >= high:
            out.append(0)
        else:
            out.append(int(round(255 * (high - g) / (high - low))))
    return out


def code_for(name, nice):
    """The code point of a glyph name: uniXXXX, uXXXXX, Glyphs' name, or a single character's own; None
    for an alternate or a ligature."""
    if "." in name or "_" in name:
        return None
    match = re.match(r"^uni([0-9A-F]{4})$", name) or re.match(r"^u([0-9A-F]{4,6})$", name)
    if match:
        return int(match.group(1), 16)
    for code, ascii_name in ASCII_NAMES.items():
        if ascii_name == name:
            return code
    for code, nice_name in nice.items():
        if nice_name == name:
            return code
    return ord(name) if len(name) == 1 else None


def contours_path(contours, QtGui, QtCore):
    path = QtGui.QPainterPath()
    for c in contours:
        if not c:
            continue
        start = [i for i, n in enumerate(c) if n[2] != "off"]
        if not start:
            continue
        c = c[start[0]:] + c[:start[0]]
        path.moveTo(c[0][0], c[0][1])
        i = 1
        n = len(c)
        while i <= n:
            node = c[i % n]
            if node[2] == "off":
                a, b, end = c[i % n], c[(i + 1) % n], c[(i + 2) % n]
                path.cubicTo(a[0], a[1], b[0], b[1], end[0], end[1])
                i += 3
            else:
                path.lineTo(node[0], node[1])
                i += 1
        path.closeSubpath()
    return path


def made_contour(fontlab, nodes, QtCore):
    """An flContour of nodes [(x, y, kind)] (kind "on", "smooth", or "off": a cubic handle): built from
    its points, then each node's type and smoothness set (FontLab takes no list of flNode, live)."""
    contour = fontlab.flContour([QtCore.QPointF(float(x), float(y)) for x, y, _ in nodes])
    contour.closed = True
    for node, (_, _, kind) in zip(contour.nodes(), nodes):
        if kind == "off":
            node.type = "curve"
        elif kind == "smooth":
            node.smooth = True
    return contour


def trace_cell(tracer, data, width, height, stride, threshold, units, x0, y_top, em_pixels):
    """A cell's drawing as contours in font units [[(x, y, kind)]], by the tracer (freelab_trace): specks
    and pinholes smaller than a square of 2% of the em dropped, nodes at extremes, coordinates whole
    units (smooth nodes kept smooth)."""
    return tracer.trace_glyph(data, width, height, units, x0, y_top, stride=stride, em_px=em_pixels,
                              threshold=threshold)


def main():
    """Font Builder on the current font (or none)."""
    try:
        if load_auto_kerning().raise_open("Font Builder"):
            return
    except Exception:
        pass
    try:
        dialog = FontBuilderDialog()
    except Exception as exc:
        print("FreeLab Font Builder: %s" % exc)
        return
    sys._freelab_font_builder = dialog
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("Font Builder", dialog)
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_font_builder":
    main()
