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
    size in units is guessed from the finders' distances and tried a few units either way (reach, or 6 %
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


def placed(contours, how, upm, sidebearing=0.05):
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
<b>Template</b>: pick the glyphs (a character set of Font Check's, or characters typed or pasted), and with
a font open, whether to leave out the glyphs it already has drawn; alternates add <i>name.alt1</i> and the
like after each. Each sheet holds the glyphs a sheet you set (100 by default): one image, each glyph in a
box with the font's metric lines (its baseline thicker) and an origin line, in a pale blue that the
reading leaves out. <i>Save template</i> writes one image a sheet. Open them in any app, or print them;
draw each glyph in dark ink inside its box, on the image or on a layer above it, and export each sheet as
an image again (PNG, JPEG, TIFF, BMP, WebP, or PSD), or scan or photograph the paper.<br><br>
The corner squares and the two bands of squares tell the reading where the sheet is and what it holds,
so a sheet can be read on another computer than the one that made it, turned, skewed, or photographed;
keep them clean and wholly in the image.<br><br>
<b>Build</b>: add the sheets drawn and click <i>Read sheets</i>: each drawn box is traced into outlines
(or kept as an image, as drawn), and listed. Check the glyphs to build and click <i>Build checked
glyphs</i> (one step of FontLab's History). Then space them (<i>Auto Spacing</i>) and build the rest
(<i>Glyph Compose</i>)."""


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
    return "%d %s" % (number, one if number == 1 else (many or one + "s"))


def grouped(number):
    return "{:,}".format(int(number))


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
        self.font_label = ak.status_label()
        self.font_label.setWordWrap(True)
        layout.addWidget(self.font_label)
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.addTab("Template")
        self.tabs.addTab("Build")
        layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.pages.addWidget(self.template_page(QtCore, QtGui))
        self.pages.addWidget(self.build_page(QtCore, QtGui))
        self.log = ak.Log()
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        buttons.addStretch(1)
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.tabs.connect("currentChanged(int)", self.pages.setCurrentIndex)
        self.close_button.connect("clicked()", ak.close_slot(self))
        self.package = None
        self.busy = False
        self.seen_history = None
        self.drawn = []
        self.sets = None  # Font Check's character sets, read when first listed
        ak.add_tools_button(dialog, "Font Builder", self.log)
        ak.plain_buttons(dialog)
        self.read_font()
        self.fill_sets()
        self.update_summary()

    # -- the template ------------------------------------------------------------

    def template_page(self, QtCore, QtGui):
        page = QtGui.QWidget()
        box = QtGui.QVBoxLayout(page)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Glyphs:"))
        self.source = QtGui.QComboBox()
        self.source.setWhatsThis("Where the glyphs come from: the characters typed below, or one of Font Check's "
                                 "character sets (its scripts, Unicode blocks, and foundries' sets).")
        row.addWidget(self.source, 1)
        box.addLayout(row)
        self.typed = QtGui.QPlainTextEdit()
        self.typed.setPlaceholderText("Type or paste the characters to draw (each once; spaces do not count).")
        self.typed.setPlainText(self.settings.get("typed") or "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        self.typed.setWhatsThis("The characters to draw, when the glyphs come from them.")
        box.addWidget(self.typed, 1)
        row = QtGui.QHBoxLayout()
        self.lacking = QtGui.QCheckBox("Leave out the glyphs the font has drawn")
        self.lacking.setChecked(True)
        self.lacking.setWhatsThis("With a font open: no box for a glyph that has outlines, components, or an image in "
                                  "its current master.")
        row.addWidget(self.lacking)
        row.addSpacing(16)
        row.addWidget(QtGui.QLabel("Alternates of each:"))
        self.alternates = QtGui.QSpinBox()
        self.alternates.setRange(0, 9)
        self.alternates.setValue(int(self.settings.get("alternates", 0)))
        self.alternates.setWhatsThis("Boxes for alternates of each glyph (name.alt1, name.alt2, ...), after it: for a "
                                     "handwriting font, Feature Code makes them take turns.")
        row.addWidget(self.alternates)
        row.addStretch(1)
        box.addLayout(row)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Glyphs a sheet:"))
        self.per_sheet = QtGui.QSpinBox()
        self.per_sheet.setRange(1, PER_SHEET_MAX)
        self.per_sheet.setValue(int(self.settings.get("per_sheet", PER_SHEET)))
        self.per_sheet.setWhatsThis("How many glyphs each sheet holds; there are as many sheets as the glyphs need. "
                                    "A sheet larger than %s megapixels gets fewer." % grouped(SHEET_PIXELS_MAX // 1000000))
        row.addWidget(self.per_sheet)
        row.addSpacing(16)
        row.addWidget(QtGui.QLabel("Em size:"))
        self.em = QtGui.QSpinBox()
        self.em.setRange(EM_PIXELS_RANGE[0], EM_PIXELS_RANGE[1])
        self.em.setSuffix(" px")
        self.em.setValue(int(self.settings.get("em", EM_PIXELS)))
        self.em.setWhatsThis("The em's size on the sheet, in pixels: 500 draws well on a screen; for print, 300 "
                             "pixels a centimeter of em at 300 dpi is about 118, so raise it for small paper sizes.")
        row.addWidget(self.em)
        row.addStretch(1)
        box.addLayout(row)
        self.summary = self.ak.status_label()
        self.summary.setWordWrap(True)
        box.addWidget(self.summary)
        row = QtGui.QHBoxLayout()
        row.addStretch(1)
        self.save_button = QtGui.QPushButton("Save template...")
        self.save_button.setWhatsThis("Writes the sheets as images (PNG, or TIFF), one a sheet, numbered.")
        row.addWidget(self.save_button)
        box.addLayout(row)
        self.source.connect("currentIndexChanged(int)", lambda i: self.update_summary())
        self.typed.connect("textChanged()", self.update_summary)
        self.lacking.connect("toggled(bool)", lambda on: self.update_summary())
        for spin in (self.alternates, self.per_sheet, self.em):
            spin.connect("valueChanged(int)", lambda v: self.update_summary())
        self.save_button.connect("clicked()", self.save_template)
        return page

    def fill_sets(self):
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
        for s in self.sets:
            self.source.addItem("%s (%s)" % (s.name, counted(s.size(), "character")))
        self.source.blockSignals(False)

    def chosen_characters(self):
        index = self.source.currentIndex
        if index <= 0 or not self.sets:
            return characters_of("%s" % self.typed.toPlainText())
        # (single characters: a letter with marks that has no character of its own is left to Glyph Compose)
        return [item for item in self.sets[index - 1].base if len(item) == 1 or
                (len(item) == 2 and 0xD800 <= ord(item[0]) < 0xDC00)]

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
            self.summary.setText("%s on %s of %s by %s pixels (%s megapixels)." % (
                counted(len(glyphs), "glyph"), counted(len(sheets), "sheet"), grouped(w), grouped(h),
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
        chosen = QtGui.QFileDialog.getSaveFileName(self.dialog, "Save the template", os.path.join(folder, base + ".png"),
                                                   "PNG images (*.png);;TIFF images (*.tif *.tiff)")
        if isinstance(chosen, (tuple, list)):
            chosen = chosen[0] if chosen else ""
        path = "%s" % (chosen or "")
        if not path:
            return
        stem, ext = os.path.splitext(path)
        ext = ext.lower() if ext.lower() in (".png", ".tif", ".tiff") else ".png"
        self.settings.update({"folder": os.path.dirname(path), "typed": "%s" % self.typed.toPlainText(),
                              "alternates": self.alternates.value, "per_sheet": self.per_sheet.value, "em": self.em.value})
        write_settings(self.ak, self.settings)
        written = []
        for sheet in sheets:
            QtGui.QApplication.processEvents()
            image = render_sheet(sheet, QtCore, QtGui)
            name = stem + ("-%d-of-%d" % (sheet.index + 1, sheet.count) if sheet.count > 1 else "") + ext
            if not image.save(name):
                self.log.add("%s could not be written." % self.ak.html(name), "error")
                return
            written.append(os.path.basename(name))
        self.log.add("Saved %s: %s." % (counted(len(written), "sheet"), self.ak.html(", ".join(written))), "done")

    # -- building ------------------------------------------------------------------

    def build_page(self, QtCore, QtGui):
        page = QtGui.QWidget()
        box = QtGui.QVBoxLayout(page)
        row = QtGui.QHBoxLayout()
        self.add_button = QtGui.QPushButton("Add sheets...")
        self.add_button.setWhatsThis("Adds sheets drawn (images: PNG, JPEG, TIFF, BMP, WebP, PSD) to read.")
        self.clear_button = QtGui.QPushButton("Clear")
        self.clear_button.setWhatsThis("Takes every sheet and glyph off the lists.")
        row.addWidget(self.add_button)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        box.addLayout(row)
        self.sheet_list = QtGui.QTreeWidget()
        self.sheet_list.setHeaderLabels(["File", "Sheet", "Glyphs", "Read"])
        self.sheet_list.setRootIsDecorated(False)
        self.sheet_list.setWhatsThis("The sheets added: which sheet each is, how many glyphs it holds, and whether it "
                                     "was read.")
        box.addWidget(self.sheet_list, 1)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Make:"))
        self.mode = QtGui.QComboBox()
        self.mode.addItem("Outlines (traced)")
        self.mode.addItem("Images (as drawn)")
        self.mode.setWhatsThis("Outlines: each drawing traced into contours, nodes at extremes. Images: each kept as "
                               "drawn, an image in the glyph (a bitmap or color font, or to trace by hand).")
        row.addWidget(self.mode)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Ink darker than:"))
        self.threshold = QtGui.QSpinBox()
        self.threshold.setRange(1, THRESHOLD_MAX)  # (higher, the guides would count as ink)
        self.threshold.setValue(min(THRESHOLD_MAX, int(self.settings.get("threshold", INK_THRESHOLD))))
        self.threshold.setWhatsThis("What counts as ink: pixels darker than this gray (0 black, 255 white). Raise it for "
                                    "pencil or light ink, lower it for a gray paper; up to %d, so the guides (gray "
                                    "%d) always stay out." % (THRESHOLD_MAX, GUIDE_GRAY))
        row.addWidget(self.threshold)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Glyphs placed:"))
        self.placement = QtGui.QComboBox()
        self.placement.addItem("Where drawn")
        self.placement.addItem("With even sidebearings")
        self.placement.setWhatsThis("Where drawn: the ink stays where it was drawn against the box's origin line, the "
                                    "right side given the left side's room. Even: both sides 5 % of the em. Either way, "
                                    "Auto Spacing spaces them better after.")
        row.addWidget(self.placement)
        row.addStretch(1)
        box.addLayout(row)
        row = QtGui.QHBoxLayout()
        self.replace = QtGui.QCheckBox("Replace glyphs the font has drawn")
        self.replace.setWhatsThis("Off: a glyph that has outlines, components, or an image in the current master is "
                                  "listed unchecked and left as it is unless you check it.")
        row.addWidget(self.replace)
        row.addStretch(1)
        self.read_button = QtGui.QPushButton("Read sheets")
        self.read_button.setWhatsThis("Reads every sheet added: finds it in its image, and traces each drawn box.")
        row.addWidget(self.read_button)
        box.addLayout(row)
        self.glyph_list = QtGui.QTreeWidget()
        self.glyph_list.setHeaderLabels(["Glyph", "From", "Read"])
        self.glyph_list.setRootIsDecorated(False)
        self.glyph_list.setIconSize(QtCore.QSize(48, 48))
        self.glyph_list.setWhatsThis("The glyphs read: as traced, the sheet each came from, and what was read. Checked "
                                     "ones are built.")
        box.addWidget(self.glyph_list, 2)
        row = QtGui.QHBoxLayout()
        row.addStretch(1)
        self.build_button = QtGui.QPushButton("Build checked glyphs")
        self.build_button.setWhatsThis("Writes the checked glyphs into the current master (new glyphs added with their "
                                       "code points), as one step of FontLab's History.")
        row.addWidget(self.build_button)
        box.addLayout(row)
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
                                                    "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp *.psd)")
        if isinstance(chosen, tuple):
            chosen = chosen[0]
        paths = ["%s" % p for p in (chosen or [])]
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
        self.read_for = self.target_key()  # (the lists stand for this font and master: build_glyphs checks)
        nice = nice_names()
        seen = {}
        try:
            for row, path in enumerate(self.files):
                item = self.sheet_list.topLevelItem(row)
                item.setText(3, "reading")
                QtGui.QApplication.processEvents()
                image = QtGui.QImage(path)
                if image.isNull():
                    item.setText(3, "not an image FontLab can read")
                    continue
                found, gray = find_sheet(image, QtCore, QtGui)
                if found is None:
                    item.setText(3, "not read: %s" % gray)
                    continue
                sheet = found.sheet
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
                        QtGui.QApplication.processEvents()
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
        except Exception as exc:
            self.log.add("Reading stopped on an error: %s" % self.ak.html("%s" % exc), "error")
        finally:
            self.busy = False
        self.show_drawn()
        self.log.add("Read %s from %s." % (counted(len(self.drawn), "drawn glyph"), counted(len(self.files), "sheet")))
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
                note = (note + "; " if note else "") + "drawn more than once: the first checked is built"
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
        QtCore, QtGui = _qt()
        size = 48
        pix = QtGui.QPixmap(size, size)
        pix.fill(QtGui.QColor(255, 255, 255))
        painter = QtGui.QPainter(pix)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            if d.image is not None:
                painter.drawImage(QtCore.QRectF(0, 0, size, size), d.image[0])
            elif d.contours:
                path = contours_path(d.contours, QtGui, QtCore)
                box = path.boundingRect()
                side = max(box.width(), box.height(), 1.0)
                t = QtGui.QTransform()
                t.translate(size / 2.0, size / 2.0)
                t.scale(0.85 * size / side, -0.85 * size / side)
                t.translate(-box.center().x(), -box.center().y())
                painter.fillPath(t.map(path), QtGui.QBrush(QtGui.QColor(0, 0, 0)))
        finally:
            painter.end()
        return QtGui.QIcon(pix)

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
        if package is None or not chosen:
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
        if not self.ak.begin_write(self.fontlab, package, TITLE, self.log):
            return
        added, rebuilt, touched, kept, unencoded, twice, nowhere, error = [], [], [], [], [], [], [], None
        clockwise_outer = not is_postscript(package)
        how = "even" if self.placement.currentIndex == 1 else "drawn"
        given = set()  # (code points given in this build: one glyph each)
        written = set()  # (each glyph written once a build: a second drawing of it is left out; review 10)
        try:
            for d in chosen:
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
        status = self.ak.notify_changed(self.fontlab, package, TITLE, touched, added=bool(added))
        if added or rebuilt:
            parts = []
            if added:
                parts.append("built %s" % counted(len(added), "new glyph"))
            if rebuilt:
                parts.append("redrew %s" % counted(len(rebuilt), "glyph"))
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
            self.log.add("Drawn more than once among the checked: built from the first, the others left out: %s." %
                         self.ak.html(", ".join(sorted(set(twice)))), "warning")
        if nowhere:
            self.log.add("Not built, since the font's glyphs of these names are other characters' (and so are their "
                         "uniXXXX names): %s." % self.ak.html(", ".join(nowhere)), "warning")
        if error is not None:
            self.log.add("Stopped by an error: %s" % self.ak.html("%s" % error), "error")
        self.show_drawn()

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
            self.font_label.setText(self.ak.no_font_line() + " A template can still be made, with default metrics.")
        else:
            self.font_label.setText("%s, master %s (its metrics shape the template's boxes)." % (
                self.ak.b(self.package.tfn), self.ak.b(self.package.master)))
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
        self.ak.enable(self.build_button, bool(self.checked_drawn()) and self.package is not None and not busy)

    def show(self):
        self.dialog.show()
        self.dialog.raise_()


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
    and pinholes smaller than a square of 2 % of the em dropped, nodes at extremes, coordinates whole
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
