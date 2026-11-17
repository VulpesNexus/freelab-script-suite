#FLM: Font Compare
# -*- coding: utf-8 -*-
"""FreeLab Font Compare, from FontLab's Scripts menu.

Two open fonts, or two masters of one font, compared glyph by glyph, read-only:

- Glyphs: those only in one; names and code points; advance widths and sidebearings; outlines
  (contour and node counts, how far nodes moved, and how much the shapes differ: the area of the
  two outlines' symmetric difference, as a share of the ink); components; anchors. A list of the
  glyphs that differ, the worst first, a chip per kind of difference to filter it, and the selected
  glyph drawn from both, overlaid and side by side, its differences in one sentence.
- Kerning: the glyph pairs kerned differently (class kerning resolved to glyph pairs, as FontLab
  applies it), the largest difference first, and the pair drawn in both.
- Features: the features (and the prefix and the Classes panel's classes) only in one, and the code
  that differs, line by line.

Nothing in either font changes. Valid Python 2.7 (FontLab 7) and Python 3. The comparisons above
the Qt line need no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import difflib
import math
import os
import sys
import time

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
TABS = ("glyphs", "kerning", "features")
THRESHOLD = 1  # units: metrics, anchors, nodes, components, and kerning differing by at most this are alike
SHAPE_SHARE = 0.002  # outlines differ when their symmetric difference passes this share of the ink
SHAPE_ROWS = 160  # scan lines across a glyph's height, measuring its area
CURVE_STEPS = 8  # straight pieces per curve, measuring its area
PROGRESS_EVERY = 25  # glyphs between two moves of the progress bar (it lets events through at most every 0.1 s)
# A comparison's steps, with the share of the progress bar (the window's top row: ak.busy_start) at the end of
# each (the owner: "the comparing step could potentially get its own loading bar, since CJK fonts can take a
# bit to load")
READ_A_STEP, READ_B_STEP, GLYPHS_STEP, KERNING_STEP, FEATURES_STEP, LIST_STEP = (
    u"Reading the first font's glyphs", u"Reading the second font's glyphs", u"Comparing the glyphs",
    u"Comparing the kerning", u"Comparing the features", u"Listing the differences")
COMPARE_STEPS = ((READ_A_STEP, 0.04), (READ_B_STEP, 0.08), (GLYPHS_STEP, 0.85), (KERNING_STEP, 0.95),
                 (FEATURES_STEP, 0.98), (LIST_STEP, 1.0))
SHOW_AFTER = 0.3  # seconds: a comparison shows the bar only once it has taken this long (a small font never flickers)
OPEN_SETTLE_MS = 400  # a font just opened: FontLab activates its window as it lists it; this window comes back after
OPEN_LATE_MS = 1500  # ... and once more this long after the comparison
DIFF_CONTEXT = 3  # unchanged lines shown around each change of a feature's code
ROWS_SHOWN = 2000  # glyphs or pairs listed at most, the worst first (two weights of a family differ everywhere)


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the dialogs' shared
    helpers come from it."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "FontKerning") and getattr(held, "_freelab_stamp", None) == stamp:
        return held  # (loaded again after a reinstall)
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


def counted(number, one, many=None):
    """"1 glyph", "2 glyphs": a count with its noun in the right number."""
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


def grouped(number):
    """1234 as "1,234"."""
    return u"{:,}".format(int(number))


def round_units(value):
    return int(math.floor(value + 0.5))


def signed(value):
    """+12, -3, 0."""
    value = round_units(value)
    return u"%+d" % value if value else u"0"


def code_text(code):
    return u"U+%04X" % code


# ---------------------------------------------------------------------------
# The two sides
# ---------------------------------------------------------------------------

PLACEHOLDER = u"Choose a font\N{HORIZONTAL ELLIPSIS}"  # the second dropdown before a choice is made
OPEN_ENTRY = u"Open a font\N{HORIZONTAL ELLIPSIS}"  # its last row: a font file opened in FontLab, then chosen


def choice_text(font_name, master, masters_count, note=None):
    """A font and master as the dropdowns list them and the sentences name them: the font's name, with
    its master in parentheses when it has several ("Sans (Bold)"); note: one more thing to tell it by
    (its file's name, "first"), in the same parentheses."""
    extras = ([master] if masters_count > 1 else []) + ([note] if note else [])
    return u"%s (%s)" % (font_name, u", ".join(extras)) if extras else font_name


def side_labels(a, b, same=None):
    """The two sides' names in sentences: a and b are (font key, font name, master, masters count).
    Two masters of one font go by their masters; two fonts by their names (and their masters when
    they have several); fonts of one name by their files' names, or else as first and second. same:
    whether both are one font, when the caller knows (two unsaved fonts of one name share a key)."""
    (key_a, name_a, master_a, count_a), (key_b, name_b, master_b, count_b) = a, b
    if key_a == key_b if same is None else same:
        if master_a != master_b:
            return master_a, master_b
        return u"first", u"second"
    if name_a == name_b:
        file_a, file_b = os.path.basename(u"%s" % key_a), os.path.basename(u"%s" % key_b)
        if file_a and file_b and file_a != file_b:
            name_a, name_b = file_a, file_b
    label_a, label_b = choice_text(name_a, master_a, count_a), choice_text(name_b, master_b, count_b)
    if label_a == label_b:
        return choice_text(name_a, master_a, count_a, u"first"), choice_text(name_b, master_b, count_b, u"second")
    return label_a, label_b


def first_entries(font):
    """The first dropdown's rows, (font id, master, text): the window's own font, a row per master.
    font: (font id, name, masters, file name)."""
    font_id, name, masters, _ = font
    return [(font_id, master, choice_text(name, master, len(masters))) for master in masters]


def installed_entries(installed):
    """The second dropdown's rows of the installed fonts ([(path, name)]): set apart ("separator"), then
    one per font ("installed", its file's path for the id), A to Z; none without any."""
    if not installed:
        return []
    rows = [("separator", None, None, u"")]
    for path, name in sorted(installed, key=lambda pair: (pair[1].lower(), pair[0].lower())):
        rows.append(("installed", path, None, name))
    return rows


def second_entries(fonts, own=None, installed=(), installed_rows=None):
    """The second dropdown's rows, (kind, font id, master, text): the placeholder shown until a choice is
    made ("none", which cannot be picked); the other open fonts in FontLab's order, a row per master
    ("font"); the window's own font last, and only when it has several masters (a font is compared with
    itself master against master); then, set apart ("separator"), the row that opens a font file
    ("open"); then the installed fonts ("installed", their file's path for the id), A to Z: picked, one
    opens in FontLab and is chosen once it is in. fonts: [(font id, name, masters, file name)]; own: the
    window's font's id; installed: [(path, name)], or installed_rows: their rows made already
    (installed_entries: some 4,000 of them, made again only when they change). Fonts of one name are told
    apart by their files' names."""
    names = [name for _, name, _, _ in fonts]
    rows = [("none", None, None, PLACEHOLDER)]
    listed = [font for font in fonts if font[0] != own] + [font for font in fonts if font[0] == own and len(font[2]) > 1]
    for font_id, name, masters, file_name in listed:
        note = file_name if file_name and names.count(name) > 1 else None
        for master in masters:
            rows.append(("font", font_id, master, choice_text(name, master, len(masters), note)))
    rows.append(("separator", None, None, u""))
    rows.append(("open", None, None, OPEN_ENTRY))
    rows.extend(installed_entries(installed) if installed_rows is None else installed_rows)
    return rows


def popup_rows_hidden(rows):
    """The rows (second_entries) the open list leaves out, by index: the placeholder (the box shows it;
    listed under it, it read as a second copy), and a separator with no row above it left to set apart."""
    hidden = set(index for index, row in enumerate(rows) if row[0] == "none")
    for index, row in enumerate(rows):
        if row[0] == "separator" and all(i in hidden for i in range(index)):
            hidden.add(index)
    return hidden


FONT_FILE_TYPES = (u".otf", u".ttf", u".otc", u".ttc")  # the installed fonts listed (FontLab opens them all)
_INSTALLED = {}  # folder: (its time stamp, [(path, name)]), read once a session unless a font is added or removed;
# None: (the folders' stamps, the list installed_fonts last gave of them all)


def font_folders():
    """Windows' font folder and the user's own (fonts installed for one account only), those there are."""
    found = []
    for base, tail in ((os.environ.get("WINDIR") or os.environ.get("SystemRoot"), (u"Fonts",)),
                       (os.environ.get("LOCALAPPDATA"), (u"Microsoft", u"Windows", u"Fonts"))):
        if base:
            if not isinstance(base, type(u"")):  # (Python 2's environment is bytes: unicode paths list unicode names)
                base = base.decode(sys.getfilesystemencoding() or "mbcs", "replace")
            folder = os.path.join(base, *tail)
            if os.path.isdir(folder):
                found.append(folder)
    return found


def name_table_name(read):
    """A font's full name (name ID 4, else family and style: IDs 1 and 2), as its name table gives it for
    Windows (else for the Mac), of the first font of a collection; None when it cannot be read.
    read(offset, length) gives the file's bytes there: only the table directory and the name table are
    read (an installed font's file may be tens of megabytes)."""
    import struct
    try:
        start = 0
        if read(0, 4) == b"ttcf":
            start = struct.unpack(">I", read(12, 4))[0]
        tables = struct.unpack(">H", read(start + 4, 2))[0]
        directory = read(start + 12, 16 * tables)
        for index in range(tables):
            if directory[16 * index:16 * index + 4] == b"name":
                offset, size = struct.unpack(">II", directory[16 * index + 8:16 * index + 16])
                break
        else:
            return None
        table = read(offset, size)
        count, strings = struct.unpack(">HH", table[2:6])
        found = {}
        for index in range(count):
            at = 6 + 12 * index
            platform, encoding, language, name_id, length, where = struct.unpack(">HHHHHH", table[at:at + 12])
            if name_id not in (1, 2, 4):
                continue
            raw = table[strings + where:strings + where + length]
            if platform == 3 and encoding in (0, 1, 10):
                rank, text = (0 if language == 0x409 else 1), raw.decode("utf-16-be", "replace")
            elif platform == 1 and encoding == 0:
                rank, text = 2, raw.decode("latin-1")
            else:
                continue
            if name_id not in found or rank < found[name_id][0]:
                found[name_id] = (rank, text)
        if 4 in found:
            return found[4][1].strip() or None
        if 1 in found:
            return (u"%s %s" % (found[1][1], found[2][1] if 2 in found else u"")).strip() or None
    except Exception:
        return None
    return None


def file_font_name(path):
    """name_table_name of a font file, or None."""
    import io
    try:
        with io.open(path, "rb") as handle:
            def read(offset, length):
                handle.seek(offset)
                return handle.read(length)
            return name_table_name(read)
    except (IOError, OSError):
        return None


def installed_fonts(folders=None):
    """The fonts installed on Windows ([(path, name)]), from its font folder and the user's: each
    file's full name, or its file's name where its name table cannot be read. Read once a session (a
    folder whose time stamp changed is read again). The same list is given back while no folder changed,
    so a caller can tell a change by it (the second dropdown's rows are made again only then)."""
    found, stamps = [], []
    for folder in (font_folders() if folders is None else folders):
        try:
            stamp = os.path.getmtime(folder)
        except OSError:
            continue
        held = _INSTALLED.get(folder)
        if held is None or held[0] != stamp:
            listed = []
            try:
                files = sorted(os.listdir(folder))
            except OSError:
                files = []
            for file_name in files:
                if os.path.splitext(file_name)[1].lower() not in FONT_FILE_TYPES:
                    continue
                path = os.path.join(folder, file_name)
                listed.append((path, file_font_name(path) or os.path.splitext(file_name)[0]))
            held = _INSTALLED[folder] = (stamp, listed)
        stamps.append((folder, held[0], id(held[1])))
        found.extend(held[1])
    stamps = tuple(stamps)
    whole = _INSTALLED.get(None)  # (the folders' lists together, as last given)
    if whole is not None and whole[0] == stamps:
        return whole[1]
    _INSTALLED[None] = (stamps, found)
    return found


def missing_line(name, others, masters, chosen, same_master=False):
    """What keeps Compare grayed, as the window's top line (rich text), or u"" when both sides are
    chosen. name: the window's font, as shown (None: no font is open); others: how many other fonts are
    open; masters: how many masters the window's font has; chosen: whether the second side is chosen;
    same_master: it is the first side's own master."""
    if name is None:
        return u"No font is open. Open a font in FontLab, then choose the font to compare it with in <i>with</i>."
    if chosen and same_master:
        return (u"Both sides are the same master of %s: choose another master, or another font, in <i>with</i>."
                % name)
    if chosen:
        return u""
    if not others and masters <= 1:
        return (u"Only %s is open, with one master. Choose <i>%s</i> in <i>with</i>, or open another font in "
                u"FontLab, to have a font to compare it with." % (name, OPEN_ENTRY))
    if not others:
        return (u"Only %s is open. Choose in <i>with</i> the master to compare with, or <i>%s</i> for another "
                u"font, then click <i>Compare</i>." % (name, OPEN_ENTRY))
    return u"Choose in <i>with</i> the font to compare %s with, then click <i>Compare</i>." % name


# ---------------------------------------------------------------------------
# Glyphs matched
# ---------------------------------------------------------------------------

def match_glyphs(glyphs_a, glyphs_b):
    """The glyphs of two fonts paired: by name, then a glyph left over in each with a code point in
    common (uni00E9 and eacute) when no other glyph left over in either font has it: the pairs are the
    same whichever font comes first. glyphs_a, glyphs_b: [(name, code points)]. Returns (pairs [(name
    in a, name in b)] in a's order, names only in a, names only in b)."""
    names_b = set(name for name, _ in glyphs_b)
    names_a = set(name for name, _ in glyphs_a)
    pairs = []
    left_a = []
    for name, codes in glyphs_a:
        if name in names_b:
            pairs.append((name, name))
        else:
            left_a.append((name, codes))
    left_b = [(name, codes) for name, codes in glyphs_b if name not in names_a]
    by_code, by_code_a = {}, {}
    for name, codes in left_b:
        for code in codes:
            by_code.setdefault(code, []).append(name)
    for name, codes in left_a:
        for code in codes:
            by_code_a.setdefault(code, []).append(name)
    taken = set()
    only_a = []
    for name, codes in left_a:
        found = None
        for code in codes:
            candidates = by_code.get(code, [])
            if len(candidates) == 1 and len(by_code_a[code]) == 1 and candidates[0] not in taken:
                found = candidates[0]
                break
        if found is None:
            only_a.append(name)
        else:
            taken.add(found)
            pairs.append((name, found))
    only_b = [name for name, _ in left_b if name not in taken]
    return pairs, only_a, only_b


# ---------------------------------------------------------------------------
# Outlines: contours are lists of nodes (x, y, type), type "off" for an off-curve point
# ---------------------------------------------------------------------------

def is_on(node):
    return len(node) < 3 or u"%s" % node[2] not in (u"off", u"offcurve")


def _midpoint(p, q):
    return ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0, True)


def _quadratic(points, p0, p1, p2, steps):
    for k in range(1, steps + 1):
        t = k / float(steps)
        u_ = 1.0 - t
        points.append((u_ * u_ * p0[0] + 2 * u_ * t * p1[0] + t * t * p2[0],
                       u_ * u_ * p0[1] + 2 * u_ * t * p1[1] + t * t * p2[1]))


def _cubic(points, p0, p1, p2, p3, steps):
    for k in range(1, steps + 1):
        t = k / float(steps)
        u_ = 1.0 - t
        a, b, c, d = u_ * u_ * u_, 3 * u_ * u_ * t, 3 * u_ * t * t, t * t * t
        points.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                       a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))


def flatten(nodes, steps=CURVE_STEPS, quadratic=False):
    """A closed contour as a polygon [(x, y)]: two off-curve points between on-curve ones make a cubic
    curve (PostScript), one a quadratic; more make TrueType's quadratic spline, an on-curve point
    implied midway between each two. quadratic: two off-curve points are a TrueType spline too."""
    points = [(float(n[0]), float(n[1]), is_on(n)) for n in nodes]
    if not points:
        return []
    if not any(p[2] for p in points):  # TrueType: a contour of off-curve points only
        points = [_midpoint(points[-1], points[0])] + points
    first = next(k for k, p in enumerate(points) if p[2])
    points = points[first:] + points[:first]
    polygon = [(points[0][0], points[0][1])]
    current, offs = points[0], []
    for point in points[1:] + points[:1]:
        if not point[2]:
            offs.append(point)
            continue
        if not offs:
            polygon.append((point[0], point[1]))
        elif len(offs) == 2 and not quadratic:
            _cubic(polygon, current, offs[0], offs[1], point, steps)
        else:
            start = current
            for k in range(len(offs) - 1):
                middle = _midpoint(offs[k], offs[k + 1])
                _quadratic(polygon, start, offs[k], middle, steps)
                start = middle
            _quadratic(polygon, start, offs[-1], point, steps)
        current, offs = point, []
    polygon.pop()  # (back at the first point)
    return polygon


def scan_spans(polygons, rows):
    """For each scan line's y (rows, evenly spaced, rising), the [(x0, x1)] spans inside the polygons
    (nonzero winding, as FontLab fills)."""
    crossings = [[] for _ in rows]
    if not rows:
        return []
    y0 = rows[0]
    step = (rows[1] - rows[0]) if len(rows) > 1 else 1.0
    last = len(rows) - 1
    for polygon in polygons:
        count = len(polygon)
        for k in range(count):
            x1, y1 = polygon[k]
            x2, y2 = polygon[(k + 1) % count]
            if y1 == y2:
                continue
            low, high = (y1, y2) if y1 < y2 else (y2, y1)
            first = max(0, int(math.ceil((low - y0) / step)))
            end = min(last, int(math.ceil((high - y0) / step)) - 1)
            direction = 1 if y2 > y1 else -1
            slope = (x2 - x1) / (y2 - y1)
            for row in range(first, end + 1):
                y = y0 + row * step
                if low <= y < high:
                    crossings[row].append((x1 + (y - y1) * slope, direction))
    found = []
    for row in crossings:
        row.sort()
        spans, winding, start = [], 0, None
        for x, direction in row:
            before = winding
            winding += direction
            if before == 0 and winding != 0:
                start = x
            elif before != 0 and winding == 0:
                spans.append((start, x))
        found.append(spans)
    return found


def _spans_length(spans):
    return sum(x1 - x0 for x0, x1 in spans)


def _overlap_length(one, other):
    total, i, j = 0.0, 0, 0
    while i < len(one) and j < len(other):
        low, high = max(one[i][0], other[j][0]), min(one[i][1], other[j][1])
        if high > low:
            total += high - low
        if one[i][1] < other[j][1]:
            i += 1
        else:
            j += 1
    return total


def shape_areas(contours_a, contours_b, rows=SHAPE_ROWS, quadratic=False):
    """(area of a's ink, area of b's ink, area of their symmetric difference), measured on scan lines
    across both outlines' height; overlapping contours count once."""
    polygons_a = [p for p in (flatten(c, quadratic=quadratic) for c in contours_a) if len(p) > 2]
    polygons_b = [p for p in (flatten(c, quadratic=quadratic) for c in contours_b) if len(p) > 2]
    ys = [y for polygon in polygons_a + polygons_b for _, y in polygon]
    if not ys or max(ys) <= min(ys):
        return 0.0, 0.0, 0.0
    low, high = min(ys), max(ys)
    step = (high - low) / float(rows)
    centers = [low + (k + 0.5) * step for k in range(rows)]
    spans_a, spans_b = scan_spans(polygons_a, centers), scan_spans(polygons_b, centers)
    area_a = area_b = apart = 0.0
    for one, other in zip(spans_a, spans_b):
        length_a, length_b = _spans_length(one), _spans_length(other)
        area_a += length_a
        area_b += length_b
        apart += length_a + length_b - 2 * _overlap_length(one, other)
    return area_a * step, area_b * step, apart * step


def shape_share(contours_a, contours_b, quadratic=False):
    """How much two outlines differ: their symmetric difference as a share of the larger one's ink
    (0 alike, 1 where one has no ink, up to 2 for two shapes apart)."""
    area_a, area_b, apart = shape_areas(contours_a, contours_b, quadratic=quadratic)
    largest = max(area_a, area_b)
    return apart / largest if largest > 0 else 0.0


def node_counts(contours):
    return [len(c) for c in contours]


def moved_most(contours_a, contours_b):
    """(how far the node that moved most moved, its contour's number from 1) for outlines of the same
    contour and node counts; None for others."""
    if node_counts(contours_a) != node_counts(contours_b):
        return None
    farthest, where = 0.0, 0
    for number, (one, other) in enumerate(zip(contours_a, contours_b), 1):
        for p, q in zip(one, other):
            distance = math.hypot(float(p[0]) - float(q[0]), float(p[1]) - float(q[1]))
            if distance > farthest:
                farthest, where = distance, number
    return farthest, where


def same_nodes(contours_a, contours_b, threshold):
    """Whether two outlines have the same nodes, in whatever order (start points, contour order)."""
    grid = float(max(threshold, 1))

    def points(contours):
        return sorted((round_units(float(p[0]) / grid), round_units(float(p[1]) / grid), is_on(p))
                      for c in contours for p in c)

    return points(contours_a) == points(contours_b)


# ---------------------------------------------------------------------------
# Glyphs compared
# ---------------------------------------------------------------------------

class GlyphData(object):
    """A glyph's layer as compared: its code points, advance width, the ink's left and right (its
    components' too; None: no ink), its own contours [[(x, y, type)]], components [(glyph name,
    (xx, xy, yx, yy, dx, dy))], and anchors [(name, x, y)]."""

    def __init__(self, name, codes=(), advance=0.0, ink=None, contours=(), components=(), anchors=()):
        self.name, self.codes = name, list(codes)
        self.advance, self.ink = float(advance), ink
        self.contours = [list(c) for c in contours]
        self.components = list(components)
        self.anchors = list(anchors)

    def scaled(self, factor):
        """The glyph at another em (factor: the other font's units per em over this one's)."""
        if factor == 1:
            return self
        s = float(factor)
        ink = None if self.ink is None else (self.ink[0] * s, self.ink[1] * s)
        contours = [[(p[0] * s, p[1] * s) + tuple(p[2:]) for p in c] for c in self.contours]
        components = [(name, m[:4] + (m[4] * s, m[5] * s)) for name, m in self.components]
        anchors = [(name, x * s, y * s) for name, x, y in self.anchors]
        return GlyphData(self.name, self.codes, self.advance * s, ink, contours, components, anchors)

    def renamed(self, names):
        """Its components named as the other font names their glyphs (names: this font's to the other's)."""
        if not names:
            return self
        components = [(names.get(name, name), m) for name, m in self.components]
        return GlyphData(self.name, self.codes, self.advance, self.ink, self.contours, components, self.anchors)


class Difference(object):
    """One kind of difference of a glyph: its kind (GLYPH_KINDS), the clause that says it, a short
    form for the list, and a score that ranks glyphs of the same kind."""

    def __init__(self, kind, text, short, score=0.0):
        self.kind, self.text, self.short, self.score = kind, text, short, score


GLYPH_KINDS = ("only_a", "only_b", "outline", "components", "codes", "metrics", "anchors")
KIND_LABELS = {"codes": u"Names and code points", "outline": u"Outlines", "components": u"Components",
               "metrics": u"Metrics", "anchors": u"Anchors"}
KIND_WEIGHT = {"only_a": 5, "only_b": 5, "outline": 4, "components": 3, "codes": 3, "metrics": 2, "anchors": 1}


def kind_label(kind, labels, masters=False):
    """A chip's label: "Only in Bold" (two masters: "No layer in Regular", the other side's)."""
    if kind in ("only_a", "only_b"):
        if masters:
            return u"No layer in %s" % labels[1 if kind == "only_a" else 0]
        return u"Only in %s" % labels[0 if kind == "only_a" else 1]
    return KIND_LABELS[kind]


def codes_list(codes):
    return u" ".join(code_text(c) for c in sorted(codes)) or u"none"


def compare_metrics(a, b, threshold, upm):
    clauses, shorts, largest = [], [], 0.0
    pairs = [(u"width", a.advance, b.advance)]
    if a.ink is not None and b.ink is not None:
        pairs.append((u"left side", a.ink[0], b.ink[0]))
        pairs.append((u"right side", a.advance - a.ink[1], b.advance - b.ink[1]))
    for name, one, other in pairs:
        one, other = round_units(one), round_units(other)
        if abs(other - one) > threshold:
            clauses.append(u"%s %d and %d (%s)" % (name, one, other, signed(other - one)))
            shorts.append(u"%s %s" % (name, signed(other - one)))
            largest = max(largest, abs(other - one))
    if not clauses:
        return None
    return Difference("metrics", u"; ".join(clauses), u", ".join(shorts), largest / float(upm or 1000))


def compare_outline(a, b, threshold, quadratic=False):
    contours_a, contours_b = a.contours, b.contours
    if contours_a == contours_b:
        return None
    counts_a, counts_b = node_counts(contours_a), node_counts(contours_b)
    clauses = []
    short = None
    if len(counts_a) != len(counts_b):
        clauses.append(u"%s and %d" % (counted(len(counts_a), u"contour"), len(counts_b)))
        short = u"contours %d, %d" % (len(counts_a), len(counts_b))
    elif counts_a != counts_b:
        clauses.append(u"%s and %d" % (counted(sum(counts_a), u"node"), sum(counts_b)))
        short = u"nodes %d, %d" % (sum(counts_a), sum(counts_b))
    share = shape_share(contours_a, contours_b, quadratic) if (contours_a or contours_b) else 0.0
    if share > SHAPE_SHARE:
        clauses.append(u"the shapes differ by %s of the ink" % percent(share))
        short = short or u"outline %s" % percent(share)
    moved = moved_most(contours_a, contours_b)
    if moved is not None and moved[0] > threshold:
        if share <= SHAPE_SHARE and same_nodes(contours_a, contours_b, threshold):
            clauses.append(u"the same nodes in another order (start points or contour order)")
            short = short or u"node order"
        else:
            clauses.append(u"nodes moved up to %s (contour %d)" % (counted(round_units(moved[0]), u"unit"), moved[1]))
            short = short or u"nodes moved %d" % round_units(moved[0])
    if not clauses:
        return None
    score = share + (1.0 if len(counts_a) != len(counts_b) or counts_a != counts_b else 0.0)
    return Difference("outline", u"; ".join(clauses), short, score)


def percent(share):
    """A share as a percentage: 0.4%, 4.1%, 12%."""
    value = share * 100.0
    if value >= 10:
        return u"%d%%" % round_units(value)
    return u"%.1f%%" % value


def compare_components(a, b, threshold, labels):
    names_a, names_b = [n for n, _ in a.components], [n for n, _ in b.components]
    clauses, shorts = [], []
    # counted, not only named: a second dot removed leaves the name in both
    for names, others, label, other_label in ((names_a, names_b, labels[0], labels[1]), (names_b, names_a, labels[1], labels[0])):
        for k, name in enumerate(names):
            if name in names[:k]:
                continue
            mine, theirs = names.count(name), others.count(name)
            if not theirs:
                clauses.append(u"component %s only in %s%s" % (name, label, u" (%d times)" % mine if mine > 1 else u""))
            elif mine > theirs:
                clauses.append(u"component %s %d times in %s, %d in %s" % (name, mine, label, theirs, other_label))
    if clauses:
        shorts.append(u"components")
    common = [n for n in names_a if n in names_b]
    if not clauses and names_a != names_b and sorted(names_a) == sorted(names_b):
        clauses.append(u"components in another order")
        shorts.append(u"component order")
    used = set()
    for name, matrix in a.components:
        others = [(k, m) for k, (n, m) in enumerate(b.components) if n == name and k not in used]
        if name not in common or not others:
            continue
        k, other = others[0]
        used.add(k)
        dx, dy = other[4] - matrix[4], other[5] - matrix[5]
        if abs(dx) > threshold or abs(dy) > threshold:
            clauses.append(u"component %s moved by (%s, %s)" % (name, signed(dx), signed(dy)))
            shorts.append(u"component moved")
        if any(abs(float(p) - float(q)) > 0.001 for p, q in zip(matrix[:4], other[:4])):
            clauses.append(u"component %s scaled or turned" % name)
            shorts.append(u"component scaled")
    if not clauses:
        return None
    return Difference("components", u"; ".join(clauses), shorts[0], float(len(clauses)))


def compare_anchors(a, b, threshold, labels):
    by_a = dict((name, (x, y)) for name, x, y in a.anchors)
    by_b = dict((name, (x, y)) for name, x, y in b.anchors)
    clauses = []
    for name, _, _ in a.anchors:
        if name not in by_b:
            clauses.append(u"anchor %s only in %s" % (name, labels[0]))
    for name, _, _ in b.anchors:
        if name not in by_a:
            clauses.append(u"anchor %s only in %s" % (name, labels[1]))
    for name, x, y in a.anchors:
        if name in by_b:
            dx, dy = by_b[name][0] - x, by_b[name][1] - y
            if abs(dx) > threshold or abs(dy) > threshold:
                clauses.append(u"anchor %s moved by (%s, %s)" % (name, signed(dx), signed(dy)))
    if not clauses:
        return None
    return Difference("anchors", u"; ".join(clauses), counted(len(clauses), u"anchor"), float(len(clauses)))


def compare_codes(a, b):
    clauses = []
    if a.name != b.name:
        clauses.append(u"named %s and %s" % (a.name, b.name))
    if sorted(a.codes) != sorted(b.codes):
        clauses.append(u"code points %s and %s" % (codes_list(a.codes), codes_list(b.codes)))
    if not clauses:
        return None
    return Difference("codes", u"; ".join(clauses), u"renamed" if a.name != b.name else u"code points", 1.0)


def compare_glyph(a, b, threshold=THRESHOLD, labels=(u"A", u"B"), upm=1000.0, masters=False, quadratic=False):
    """[Difference] between a glyph's two GlyphData (None: not in that font, or no layer in that master),
    b at a's em already."""
    if a is None and b is None:
        return []
    if a is None or b is None:
        kind = "only_b" if a is None else "only_a"
        if masters:
            text = u"no layer in %s" % labels[0 if a is None else 1]
        else:
            text = u"only in %s" % labels[1 if a is None else 0]
        return [Difference(kind, text, text, 0.0)]
    found = []
    for difference in (compare_codes(a, b), compare_outline(a, b, threshold, quadratic),
                       compare_components(a, b, threshold, labels), compare_metrics(a, b, threshold, upm),
                       compare_anchors(a, b, threshold, labels)):
        if difference is not None:
            found.append(difference)
    return found


class GlyphResult(object):
    """A glyph's differences: its name in each font (None: not there, or no layer)."""

    def __init__(self, a, b, differences):
        self.a, self.b, self.differences = a, b, list(differences)

    @property
    def name(self):
        return self.a if self.a is not None else self.b

    def kinds(self):
        return set(d.kind for d in self.differences)

    def caption(self):
        """Its name, and the other font's when they differ: "uni00E9 / eacute"."""
        if self.a is not None and self.b is not None and self.a != self.b:
            return u"%s / %s" % (self.a, self.b)
        return self.name

    def shown(self, kinds=None):
        """Its differences of the given kinds (None: all of them)."""
        return [d for d in self.differences if kinds is None or d.kind in kinds]

    def short(self, kinds=None):
        """Its differences of the given kinds (None: all) in short, for the list: one after another, as
        its sentence gives them (a kind's own parts are joined by commas)."""
        return u"; ".join(d.short for d in self.shown(kinds))

    def sentence(self, labels):
        """Its differences in one sentence: "a, Regular and Bold: width 520 and 540 (+20); ...". """
        if any(d.kind in ("only_a", "only_b") for d in self.differences):
            return u"%s: %s." % (self.caption(), self.differences[0].text)
        return u"%s, %s and %s: %s." % (self.caption(), labels[0], labels[1], u"; ".join(d.text for d in self.differences))


def glyph_counts(results):
    """{kind: glyphs with it}."""
    found = {}
    for result in results:
        for kind in result.kinds():
            found[kind] = found.get(kind, 0) + 1
    return found


def glyph_rows(results, kinds=None):
    """The results with a difference of the given kinds (None: any), the worst first by those kinds
    alone: the gravest kind, then the largest score (how much the shapes differ, how far the
    metrics), then by name. A kind left out is left out of every row, not only of the glyphs that
    have nothing else: an outline change moves the sidebearings too, so nearly every glyph whose
    metrics differ differs otherwise as well, and hiding only those glyphs hid nothing."""
    kinds = None if kinds is None else set(kinds)
    shown = [r for r in results if r.shown(kinds)]

    def key(r):
        differences = r.shown(kinds)
        weight = max(KIND_WEIGHT.get(d.kind, 1) for d in differences)
        return (-weight, -sum(d.score for d in differences if KIND_WEIGHT.get(d.kind, 1) == weight),
                -len(differences), r.name)

    return sorted(shown, key=key)


# ---------------------------------------------------------------------------
# Kerning compared
# ---------------------------------------------------------------------------

def resolve_entries(values, members):
    """Glyph pairs and the value each gets from a master's entries ({((left, is class), (right, is
    class)): value}, as FontKerning reads them), the most specific entry winning as FontLab applies
    them: glyph and glyph, glyph and class, class and glyph, then class and class."""
    rank = {(False, False): 0, (False, True): 1, (True, False): 2, (True, True): 3}
    best = {}
    for ((left, left_class), (right, right_class)), value in values.items():
        level = rank[(bool(left_class), bool(right_class))]
        lefts = members.get(left, []) if left_class else [left]
        rights = members.get(right, []) if right_class else [right]
        for one in lefts:
            for other in rights:
                held = best.get((one, other))
                if held is None or level < held[0]:
                    best[(one, other)] = (level, value)
    return dict((pair, value) for pair, (_, value) in best.items())


class KernDifference(object):
    """A glyph pair kerned differently: its names (the first font's), its value in each (0: not kerned),
    and its kind: only_a, only_b, value, or absent (a glyph of it is missing in a font)."""

    def __init__(self, left, right, a, b, kind):
        self.left, self.right, self.a, self.b, self.kind = left, right, a, b, kind

    @property
    def delta(self):
        return self.b - self.a


KERN_KINDS = ("only_a", "only_b", "value", "absent")
# The kinds of difference each list shows to start with: what both fonts have, compared (the owner: the
# glyphs only in one font "should probably be unchecked by default so it truly focuses on comparing what is
# available in both fonts", and the kerning "should default to 'Differing values' ... only different to
# ticking everything else if there's nothing falling under that category")
GLYPH_KINDS_FIRST = ("outline", "components", "codes", "metrics", "anchors")
KERN_KINDS_FIRST = ("value",)


def kern_label(kind, labels):
    return {"only_a": u"Only in %s" % labels[0], "only_b": u"Only in %s" % labels[1],
            "value": u"Differing values", "absent": u"Glyphs one font lacks"}[kind]


def bar_value(steps, label, part=0.0):
    """How far the progress bar is, 0 to 1, at this part (0 to 1) of the step of that label (steps: (label,
    share at its end)); None for a label that is not one of them."""
    start = 0.0
    for name, end in steps:
        if name == label:
            return start + (end - start) * min(max(float(part), 0.0), 1.0)
        start = end
    return None


def kinds_first_on(counts, first):
    """The kinds whose chips are checked after a comparison: those of first that have something; every
    kind that has something when none of them has (else the list would start empty)."""
    found = set(kind for kind in first if counts.get(kind))
    return found or set(kind for kind, count in counts.items() if count)


def kerning_diff(a, b, threshold=0, rename=None, glyphs_a=None, glyphs_b=None):
    """[KernDifference] between two masters' kerning ({(left, right): value}, classes resolved), b
    in the first font's units already, the largest difference first. rename: b's glyph names to a's;
    glyphs_a, glyphs_b: each font's glyphs (a's names), to tell pairs a font cannot have."""
    rename = rename or {}
    b = dict(((rename.get(left, left), rename.get(right, right)), value) for (left, right), value in b.items())
    found = []
    for pair in set(a) | set(b):
        one, other = round_units(a.get(pair) or 0), round_units(b.get(pair) or 0)
        if abs(other - one) <= threshold:
            continue
        left, right = pair
        if (glyphs_a is not None and (left not in glyphs_a or right not in glyphs_a)) or \
                (glyphs_b is not None and (left not in glyphs_b or right not in glyphs_b)):
            kind = "absent"
        elif not other:
            kind = "only_a"
        elif not one:
            kind = "only_b"
        else:
            kind = "value"
        found.append(KernDifference(left, right, one, other, kind))
    found.sort(key=lambda d: (-abs(d.delta), d.left, d.right))
    return found


def kern_counts(found):
    counts_ = {}
    for d in found:
        counts_[d.kind] = counts_.get(d.kind, 0) + 1
    return counts_


# ---------------------------------------------------------------------------
# Features compared
# ---------------------------------------------------------------------------

PREFIX, CLASSES = u"Prefix", u"Classes"  # the code before the features, and the Classes panel's classes


def code_lines(text):
    """A feature's code as lines: line ends made one, trailing spaces and the blank lines at either end
    dropped (they change nothing)."""
    lines = [line.rstrip() for line in (text or u"").replace(u"\r\n", u"\n").replace(u"\r", u"\n").split(u"\n")]
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return lines


def line_diff(a, b, context=DIFF_CONTEXT):
    """[(sign, line)] of what differs between two texts: " " a line in both, "-" only in a, "+" only
    in b, "@" lines left out (unchanged); [] when they are alike."""
    lines_a, lines_b = code_lines(a), code_lines(b)
    if lines_a == lines_b:
        return []
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b, False)
    rows = []
    for group in matcher.get_grouped_opcodes(context):
        if rows or group[0][1] > 0 or group[0][3] > 0:
            rows.append((u"@", u""))
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                rows.extend((u" ", line) for line in lines_a[i1:i2])
                continue
            if tag in ("replace", "delete"):
                rows.extend((u"-", line) for line in lines_a[i1:i2])
            if tag in ("replace", "insert"):
                rows.extend((u"+", line) for line in lines_b[j1:j2])
        if group[-1][2] < len(lines_a) or group[-1][4] < len(lines_b):
            rows.append((u"@", u""))
    while len(rows) > 1 and rows[-1][0] == u"@" and rows[-2][0] == u"@":
        rows.pop()
    return rows


class FeatureDifference(object):
    """A feature (or the prefix, or the classes): its tag, its kind (only_a, only_b, differs, same),
    its code in each, and the lines that differ."""

    def __init__(self, tag, kind, a, b, rows):
        self.tag, self.kind, self.a, self.b, self.rows = tag, kind, a, b, rows

    @property
    def added(self):
        return sum(1 for sign, _ in self.rows if sign == u"+")

    @property
    def removed(self):
        return sum(1 for sign, _ in self.rows if sign == u"-")


def feature_diff(a, b):
    """[FeatureDifference] of two fonts' features, each [(tag, code)] in its font's order: a's order,
    then b's own (the prefix first, the classes last)."""
    by_a, by_b = dict(a), dict(b)
    found = []
    tags = [t for t, _ in a] + [t for t, _ in b if t not in by_a]
    tags.sort(key=lambda t: {PREFIX: 0, CLASSES: 2}.get(t, 1))  # (a stable sort: the fonts' order kept)
    for tag in tags:
        if tag not in by_b:
            found.append(FeatureDifference(tag, "only_a", by_a[tag], None, [(u"-", line) for line in code_lines(by_a[tag])]))
        elif tag not in by_a:
            found.append(FeatureDifference(tag, "only_b", None, by_b[tag], [(u"+", line) for line in code_lines(by_b[tag])]))
        else:
            rows = line_diff(by_a[tag], by_b[tag])
            found.append(FeatureDifference(tag, "differs" if rows else "same", by_a[tag], by_b[tag], rows))
    return found


def classes_text(groups):
    """The Classes panel's feature classes as code, a line each, by name: [(name, glyph names)]."""
    return u"\n".join(u"@%s = [%s];" % (name, u" ".join(members)) for name, members in sorted(groups))


def feature_state(f, labels):
    """The Difference column of a feature's row."""
    if f.kind == "only_a":
        return u"only in %s" % labels[0]
    if f.kind == "only_b":
        return u"only in %s" % labels[1]
    if f.kind == "same":
        return u"alike"
    parts = []
    if f.removed:
        parts.append(u"%s only in %s" % (counted(f.removed, u"line"), labels[0]))
    if f.added:
        parts.append(u"%s only in %s" % (counted(f.added, u"line"), labels[1]))
    return u", ".join(parts) or u"differs"


def html_escape(text):
    return (u"%s" % text).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


def blend(base, tint, share):
    """"#rrggbb" of tint laid over base at a share (both (r, g, b))."""
    return u"#%02x%02x%02x" % tuple(int(round(b_ * (1 - share) + t * share)) for b_, t in zip(base, tint))


def diff_html(rows, labels, base, text, removed=(222, 64, 52), added=(64, 168, 92)):
    """A feature's lines that differ as rich text: lines only in the first font on a red tint, a minus
    before them; lines only in the second on a green tint, a plus; lines left out as an ellipsis.
    base and text: the view's colors (r, g, b)."""
    color = u"#%02x%02x%02x" % tuple(text)
    tints = {u"-": blend(base, removed, 0.28), u"+": blend(base, added, 0.28)}
    quiet = blend(base, text, 0.55)
    signs = {u"-": u"\N{MINUS SIGN}", u"+": u"+", u" ": u" "}
    parts = [u'<table cellspacing="0" cellpadding="1" width="100%%" style="color:%s">' % color,
             u'<tr><td colspan="2" style="color:%s">%s %s &nbsp; + %s</td></tr>' % (
                 quiet, u"\N{MINUS SIGN}", html_escape(labels[0]), html_escape(labels[1]))]
    for sign, line in rows:
        if sign == u"@":
            parts.append(u'<tr><td></td><td style="color:%s">\N{HORIZONTAL ELLIPSIS}</td></tr>' % quiet)
            continue
        style = u' style="background-color:%s"' % tints[sign] if sign in tints else u""
        parts.append(u'<tr%s><td width="14"><pre style="margin:0">%s</pre></td><td><pre style="margin:0">%s</pre></td></tr>'
                     % (style, signs[sign], html_escape(line) or u" "))
    parts.append(u"</table>")
    return u"".join(parts)


# ---------------------------------------------------------------------------
# FontLab: reading a glyph (every call guarded: only those noted in docs/FONT-COMPARE.md are proven)
# ---------------------------------------------------------------------------

def glyph_codes(fg):
    """A fontgate glyph's code points (its unicodes, else its unicode)."""
    try:
        codes = [int(code) for code in (fg.unicodes or []) if code]
    except Exception:
        codes = []
    if not codes:
        try:
            codes = [int(fg.unicode)] if fg.unicode else []
        except Exception:
            codes = []
    return codes


def shape_matrix(shape):
    try:
        t = shape.transform
        return (float(t.m11()), float(t.m12()), float(t.m21()), float(t.m22()), float(t.dx()), float(t.dy()))
    except Exception:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def anchor_points(layer):
    """[(name, x, y)] of a layer's anchors (flPinPoint.point, as Diacritics reads it)."""
    found = []
    try:
        for anchor in layer.anchors:
            try:
                point = anchor.point
                found.append((u"%s" % anchor.name, float(point.x()), float(point.y())))
            except Exception:
                pass
    except Exception:
        pass
    return found


def read_layer(name, codes, layer):
    """A layer's GlyphData (its ink not yet measured), or None when it cannot be read."""
    contours, components = [], []
    try:
        shapes = list(layer.shapes)
    except Exception:
        return None
    for shape in shapes:
        try:
            component = bool(shape.isComponent)
        except Exception:
            component = False
        matrix = shape_matrix(shape)
        if component:
            try:
                base = u"%s" % shape.shapeData.componentGlyph
            except Exception:
                base = u"?"
            components.append((base, matrix))
            continue
        a, b, c, d, dx, dy = matrix
        for contour in shape.contours:
            if contour is None:  # FontLab lists an empty contour as None in some glyphs
                continue
            nodes = []
            for node in contour.nodes():
                x, y = float(node.x), float(node.y)
                nodes.append((a * x + c * y + dx, b * x + d * y + dy, u"%s" % node.type))
            contours.append(nodes)
    try:
        advance = float(layer.advanceWidth)
    except Exception:
        advance = 0.0
    return GlyphData(name, codes, advance, None, contours, components, anchor_points(layer))


# ---------------------------------------------------------------------------
# The dialog (Qt)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def _prop(obj, name):
    """A Qt property's value: an attribute in PythonQt (a method in some builds)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


HELP = u"""<b>FreeLab Font Compare</b><br>
Two open fonts, or two masters of one font, compared glyph by glyph. Nothing in either font
changes.<br><br>
The first is this window's font (<i>Compare</i> lists its masters). Choose the second in <i>with</i>:
another open font, another master of the first, or <i>Open a font\N{HORIZONTAL ELLIPSIS}</i> for a font
file; then click <i>Compare</i>. A font opened from there, or from the fonts installed on Windows listed
under it, is compared at once. A long comparison shows how far it is in the window's top row; the tools
menu, the arrows, <i>Close</i>, and Esc stop it (the lists keep the comparison before it).
Differences of at most the units set are left out (metrics, anchors, nodes, components, kerning).
A font of another em is scaled to the first one's.<br><br>
<b>Glyphs</b>: a chip per kind of difference, each showing or hiding that kind in the list (a glyph
with none of the kinds shown is left out; the glyphs only in one font are hidden to start with); the
glyphs that differ, the worst first by the kinds
shown, both drawn small; the selected glyph from both fonts, the first in the text
color and the second in the highlight color, overlaid in the middle, its differences in one sentence
under it. How much two outlines differ is the area where one has ink and the other not, as a share of
the ink: a node moved shows.<br>
<b>Kerning</b>: the glyph pairs kerned differently, classes resolved as FontLab applies them, the
largest difference first, and the selected pair drawn in both. The pairs both fonts kern, with
differing values, are shown to start with; a chip shows the others.<br>
<b>Features</b>: the features only in one font, and the lines of code that differ, removed in red and
added in green.<br><br>
Right-click a glyph or a pair to flag it in the first font. Compared again after an undo or an edit
in either font. Click this help's <i>?</i> button, then any control, for what it does."""

CHIP_SHEET = (u"QToolButton { background: transparent; color: rgba(128, 128, 128, 255); "
              u"border: 1px solid rgba(128, 128, 128, 110); border-radius: 10px; padding: 2px 10px; } "
              u"QToolButton:hover { color: palette(window-text); border: 1px solid rgba(128, 128, 128, 200); } "
              u"QToolButton:checked { color: palette(highlighted-text); background: palette(highlight); "
              u"border: 1px solid palette(highlight); } "
              u"QToolButton:checked:hover { border: 1px solid palette(window-text); } "
              u"QToolButton:disabled { color: rgba(128, 128, 128, 110); }")
# FreeLab's chips: flat, a kind shown filled in the highlight color, a kind hidden as a gray outline,
# over either palette, set on each chip (never on the dialog, whose fields dark mode then maps) and
# left alone by dark mode, as Auto Kerning's TAB_SHEET is. Windows' own style drew a checked tool
# button light whatever the palette: mapped, it came out garbled, white in dark mode.

GRAY = (128, 128, 128)
LINE_ALPHA = 128  # the lists' lines: a mid gray at half strength
QUIET_ALPHA = 150
FIRST_ALPHA = 120  # the first font's ink, overlaid
SECOND_ALPHA = 150  # the second's, in the highlight color
THUMB_SIZE = 32
COLUMN_MAX = 260  # pixels: a list's first column at most
KERN_PREVIEW_GAP = 6  # pixels between the two pair pictures


def qcolor(rgb, alpha=255):
    QtCore, QtGui = _qt()
    return QtGui.QColor(rgb[0], rgb[1], rgb[2], alpha)


def faded(color, alpha):
    QtCore, QtGui = _qt()
    found = QtGui.QColor(color)
    found.setAlpha(alpha)
    return found


def new_pixmap(width, height):
    QtCore, QtGui = _qt()
    pixmap = QtGui.QPixmap(max(1, int(width)), max(1, int(height)))
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    return pixmap


def text_width(font, text):
    QtCore, QtGui = _qt()
    return QtGui.QFontMetrics(font).width(text)


def elided(font, text, width):
    """text cut to fit width pixels, an ellipsis at its end."""
    if text_width(font, text) <= width:
        return text
    while text and text_width(font, text + u"\N{HORIZONTAL ELLIPSIS}") > width:
        text = text[:-1]
    return text + u"\N{HORIZONTAL ELLIPSIS}" if text else u""


def ink_box(path):
    """(left, bottom, right, top) of a glyph's ink in font units, or None (no ink)."""
    if path is None or path.isEmpty():
        return None
    rect = path.boundingRect()  # font units grow upward: the rect's top() is the ink's bottom
    return rect.left(), rect.top(), rect.right(), rect.bottom()


def both_thumb(path_a, path_b, colors, size=THUMB_SIZE):
    """A glyph from both fonts, small: the first in the text color, the second in the highlight color,
    see-through, at one scale."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(size, size)
    boxes = [box for box in (ink_box(path_a), ink_box(path_b)) if box is not None]
    if not boxes:
        return pixmap
    left, bottom = min(b_[0] for b_ in boxes), min(b_[1] for b_ in boxes)
    right, top = max(b_[2] for b_ in boxes), max(b_[3] for b_ in boxes)
    scale = min((size - 6) / float(max(right - left, 1.0)), (size - 6) / float(max(top - bottom, 1.0)))
    painter = QtGui.QPainter(pixmap)
    try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.translate(size / 2.0 - (left + right) / 2.0 * scale, size / 2.0 + (bottom + top) / 2.0 * scale)
        painter.scale(scale, -scale)
        two = path_a is not None and path_b is not None
        if path_a is not None:
            painter.fillPath(path_a, QtGui.QBrush(faded(colors["text"], FIRST_ALPHA + 40 if two else 220)))
        if path_b is not None:
            painter.fillPath(path_b, QtGui.QBrush(faded(colors["highlight"], SECOND_ALPHA if two else 220)))
    finally:
        painter.end()
    return pixmap


def comparison_pixmap(width, height, a, b, colors, font):
    """The selected glyph from both fonts at one scale, in three panels: the first font's (text
    color), both overlaid, the second's (highlight color); the baseline and each advance width drawn
    thin; a font without the glyph as a dashed empty frame. a, b: (caption, path or None, advance), and
    optionally a color glyph's parts [(path, QColor)]: its own panel draws it in its colors (the overlay
    keeps the two comparison colors)."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(width, height)
    text, highlight = colors["text"], colors["highlight"]
    line_height = QtGui.QFontMetrics(font).height()
    xs, ys = [], [0.0]
    for side in (a, b):
        path, advance = side[1], side[2]
        box = ink_box(path)
        if box is not None:
            xs += [box[0], box[2]]
            ys += [box[1], box[3]]
        if path is not None:
            xs += [0.0, float(advance)]
    if len(xs) < 2:
        xs, ys = [0.0, 500.0], [0.0, 700.0]
    left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)
    third = width / 3.0
    room_y = height - line_height - 28
    scale = min((third - 28) / float(max(1.0, right - left)), room_y / float(max(1.0, top - bottom)))
    if scale <= 0:
        return pixmap
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        panels = ((a[0], [(a, faded(text, 210))], text), (u"Both", [(a, faded(text, FIRST_ALPHA)), (b, faded(highlight, SECOND_ALPHA))], text),
                  (b[0], [(b, faded(highlight, 210))], highlight))
        for index, (caption, drawn, caption_color) in enumerate(panels):
            x0 = index * third + third / 2.0 - (left + right) / 2.0 * scale
            y0 = 12 + room_y / 2.0 + (bottom + top) / 2.0 * scale
            painter.setPen(QtGui.QPen(qcolor(GRAY, LINE_ALPHA)))
            painter.drawLine(QtCore.QPointF(index * third + 8, y0), QtCore.QPointF((index + 1) * third - 8, y0))
            for side, color in drawn:
                path, advance = side[1], side[2]
                parts = side[3] if len(side) > 3 and len(drawn) == 1 else None
                if path is None:
                    if len(drawn) == 1:
                        pen = QtGui.QPen(qcolor(GRAY, 200), 1.2, QtCore.Qt.DashLine)
                        painter.setPen(pen)
                        painter.setBrush(QtGui.QBrush())
                        frame = QtCore.QRectF(x0 + left * scale, y0 - top * scale, (right - left) * scale,
                                              (top - bottom) * scale)
                        painter.drawRect(frame)
                        painter.setPen(faded(text, QUIET_ALPHA))
                        painter.drawText(frame, int(QtCore.Qt.AlignCenter), u"Not there")
                    continue
                pen = QtGui.QPen(faded(color, 150), 1.0, QtCore.Qt.DashLine)
                painter.setPen(pen)
                for x in (0.0, float(advance)):
                    painter.drawLine(QtCore.QPointF(x0 + x * scale, y0 - top * scale - 4),
                                     QtCore.QPointF(x0 + x * scale, y0 - bottom * scale + 4))
                painter.save()
                painter.translate(x0, y0)
                painter.scale(scale, -scale)
                if parts:  # a color glyph alone in its panel: its own colors
                    for part, part_color in parts:
                        painter.fillPath(part, QtGui.QBrush(part_color))
                else:
                    painter.fillPath(path, QtGui.QBrush(color))
                painter.restore()
            painter.setFont(font)
            painter.setPen(caption_color)
            painter.drawText(QtCore.QRectF(index * third, height - line_height - 6, third, line_height),
                             int(QtCore.Qt.AlignCenter), elided(font, caption, int(third) - 8))
        painter.setPen(QtGui.QPen(qcolor(GRAY, LINE_ALPHA)))
        for index in (1, 2):
            painter.drawLine(QtCore.QPointF(index * third, 8), QtCore.QPointF(index * third, height - 8))
    finally:
        painter.end()
    return pixmap


def stacked_pixmap(pixmaps, gap=KERN_PREVIEW_GAP):
    """Pictures one under the other, centered."""
    QtCore, QtGui = _qt()
    shown = [p for p in pixmaps if p is not None and not p.isNull()]
    if not shown:
        return QtGui.QPixmap()
    width = max(p.width() for p in shown)
    height = sum(p.height() for p in shown) + gap * (len(shown) - 1)
    pixmap = new_pixmap(width, height)
    painter = QtGui.QPainter(pixmap)
    try:
        y = 0
        for p in shown:
            painter.drawPixmap(int((width - p.width()) / 2), int(y), p)
            y += p.height() + gap
    finally:
        painter.end()
    return pixmap


class Side(object):
    """A font and master chosen: its package, master, label in sentences, and glyph names."""

    def __init__(self, package, master, label):
        self.package, self.master, self.label = package, master, label
        self.paths = {}  # glyph name: (its QPainterPath, its advance), for the glyphs listed (path_of)
        self.factor = 1.0  # the scale of its glyphs to the first font's em
        self.number = None  # FontLab's number of its font at the comparison (font_number): read only while it is open


class SecondWatch(object):
    """The second font's History watched too (watch_history takes one font per owner)."""

    def __init__(self, owner):
        self.owner = owner
        self.package = self.seen_history = None

    @property
    def dialog(self):
        return self.owner.dialog

    @property
    def busy(self):
        return self.owner.busy

    def history_moved(self):
        self.owner.history_moved()


class CompareDialog(object):
    def __init__(self):
        self.failed = None
        self.dialog = None
        try:
            self.build()
        except Exception as exc:  # a half-built dialog crashed FontLab: never raised from here
            self.failed = exc

    # -- building ------------------------------------------------------------

    def build(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        self.package = None  # the first font: flags, and its History watched
        self.seen_history = None
        self.second = SecondWatch(self)
        self.busy = self.filling = False
        self.fonts, self.by_id = [], {}  # the open fonts (this window's first), and each by FontLab's number of it
        self.own_listed = False  # whether fonts starts with this window's font
        self.first_rows, self.second_rows = [], []  # the dropdowns' rows (first_entries, second_entries)
        self.second_key = None  # the second side chosen: (font number, master), or None
        self.sides = None  # (Side, Side) compared
        self.masters_mode = False
        self.results, self.glyph_names = [], []
        self.kern_rows, self.kern_shown = [], []
        self.feature_rows, self.feature_shown = [], []
        self.rename = {}  # the second font's glyph names to the first's (matched by code point)
        self.filters, self.redraws = [], {}
        self.drawing_failed = False
        main = ak.AutoKerningDialog.main_window()
        dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        self.dialog = dialog
        dialog.setWindowTitle("FreeLab Font Compare")
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.font_label = ak.status_label()
        layout.addWidget(self.font_label)
        layout.addWidget(ak.separator())
        settings = QtGui.QHBoxLayout()
        settings.addWidget(QtGui.QLabel("Compare"))
        self.choice_a = self.combo(u"The first font: this window's, with a row for each of its masters. Its glyph "
                                   u"names are the ones listed, and its glyphs are flagged by a right-click.")
        settings.addWidget(self.choice_a)
        self.swap_button = QtGui.QToolButton()
        self.swap_button.setText(u"\N{LEFTWARDS ARROW OVER RIGHTWARDS ARROW}")
        self.swap_button.setAutoRaise(True)
        self.swap_button.setToolTip(u"Swaps the two masters of this font, and compares again if they were compared. "
                                    u"With another font chosen there is nothing to swap: the first is this window's font.")
        settings.addWidget(self.swap_button)
        settings.addWidget(QtGui.QLabel("with"))
        self.choice_b = self.combo(u"The second font: another font open in FontLab (a row for each master), or "
                                   u"another master of the first. <i>%s</i> opens a font file in FontLab (as "
                                   u"<i>File &gt; Open</i> does, starting in Windows' font folder) and chooses it. "
                                   u"Under it, the fonts installed on Windows (yours too), A to Z: picking one opens it "
                                   u"in FontLab and chooses it. A font opened either way is compared at once, without a "
                                   u"click on <i>Compare</i>. The list follows the fonts FontLab has open." % OPEN_ENTRY)
        settings.addWidget(self.choice_b)
        settings.addSpacing(12)
        settings.addWidget(QtGui.QLabel("Ignore differences up to"))
        self.threshold = QtGui.QSpinBox()
        self.threshold.setRange(0, 100)
        self.threshold.setValue(THRESHOLD)
        self.suffix_slot = ak.counted_suffix(self.threshold, u"unit")  # ("1 unit", "2 units")
        self.threshold.setWhatsThis(u"Widths, sidebearings, anchors, nodes, components, and kerning values that differ "
                                    u"by at most this many units count as alike.")
        settings.addWidget(self.threshold)
        self.compare_button = QtGui.QPushButton("Compare")
        settings.addWidget(self.compare_button)
        settings.addStretch(1)
        layout.addLayout(settings)
        # (a comparison's progress shows in the window's top row, ak.busy_start: owner's image 200, the bar that
        # stood under the choices took a line of its own)
        self.log = ak.Log()
        # A tab bar over plain pages, as in Font Check: a QTabWidget's page drew light frames in dark mode
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.redraw_timer = QtCore.QTimer(dialog)  # (its parent the window: Qt deletes it with it)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(80)
        self.redraw_timer.connect("timeout()", self.redraw_now)
        for build, label in ((self.build_glyphs, u"Glyphs"), (self.build_kerning, u"Kerning"),
                             (self.build_features, u"Features")):
            page = build(QtCore, QtGui)
            self.tabs.addTab(label)
            self.pages.addWidget(page)
        layout.addWidget(self.log.widget)
        # No "Show in Glyph window": FontLab opens a Glyph window on its current font only, so a glyph
        # of the other font (or of a font not current) would show in the wrong one
        buttons = QtGui.QHBoxLayout()
        self.close_button = QtGui.QPushButton("Close")
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        # What chooses the fonts stays usable with no comparison to make (ak.no_font_states grays the rest
        # while has_font says no: owner's image 209); update_buttons still grays the second without a first
        for box in (self.choice_a, self.choice_b):
            box.setProperty(getattr(ak, "WITHOUT_FONT_PROP", "freelabWithoutFont"), True)
        self.compare_button.connect("clicked()", self.compare)
        self.swap_button.connect("clicked()", self.swap)
        self.choice_slots = [lambda index: self.choice_changed(), lambda index: self.second_activated(index)]
        self.choice_a.connect("currentIndexChanged(int)", self.choice_slots[0])
        self.choice_b.connect("currentIndexChanged(int)", self.choice_slots[0])
        self.choice_b.connect("activated(int)", self.choice_slots[1])  # (a row picked by the user, not by the code)
        self.watch_fonts()
        self.tabs.connect("currentChanged(int)", self.switch_page)
        ak.add_tools_button(dialog, "Font Compare", getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.read_fonts()
        self.history_timer = ak.watch_history(self)
        self.second_timer = ak.watch_history(self.second)
        self.flagging = [ak.flag_menu(self.glyph_tree, self, self.selected_glyphs, self.row_glyph),
                         ak.flag_menu(self.kern_tree, self, self.selected_glyphs, self.row_pair)]
        self.update_buttons()

    def combo(self, tip):
        QtCore, QtGui = _qt()
        box = QtGui.QComboBox()
        try:
            box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(22)  # (a long name elided, not pushing the row past the window)
        except Exception:
            pass
        box.setWhatsThis(tip)
        return box

    def tree(self, columns, icon=None):
        """A list: no root decoration, no horizontal scrolling (long texts elided, whole in tooltips),
        grid lines, pictures of the given size (its pictures drawn in the dialog's colors)."""
        QtCore, QtGui = _qt()
        tree = QtGui.QTreeWidget()
        tree.setColumnCount(len(columns))
        tree.setHeaderLabels(list(columns))
        tree.setRootIsDecorated(False)
        try:
            tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        except Exception:
            pass
        if icon is not None:
            tree.setIconSize(QtCore.QSize(icon, icon))
            tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # (as Font Check's: its scroll bars are FreeLab's flat ones)
        self.ak.table_layout(tree)  # (left alone by dark mode: mapped, its header and grid came out light)
        return tree

    def picture_label(self, minimum):
        """A label showing a picture drawn to its size (redrawn as it is resized)."""
        QtCore, QtGui = _qt()
        label = QtGui.QLabel()
        label.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
        label.setAlignment(QtCore.Qt.AlignCenter)
        try:
            label.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)  # (its picture never sizes it)
        except Exception:
            pass
        label.setMinimumSize(minimum[0], minimum[1])
        return label

    def watch_resize(self, widget, key):
        """The picture of widget drawn again (redraw_now's key) a moment after it is resized."""
        QtCore, QtGui = _qt()
        owner = self

        class Resized(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize
                        owner.redraws[key] = True
                        owner.redraw_timer.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        found = Resized(widget)  # (its parent the widget it watches: Qt deletes it with it)
        widget.installEventFilter(found)
        self.filters.append(found)

    REFRESH_EVENTS = (2, 8, 24)  # MouseButtonPress, FocusIn, WindowActivate

    def watch_fonts(self):
        """The dropdowns follow the fonts FontLab has open: read again as a dropdown is pressed or takes
        the focus (before its list opens), and as the window becomes the active one (a font opened or
        closed in FontLab meanwhile)."""
        QtCore, QtGui = _qt()
        owner = self

        class Watch(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() in owner.REFRESH_EVENTS and not owner.busy and not owner.filling:
                        owner.read_fonts()
                except Exception:
                    pass  # an event filter must never raise
                return False

        found = Watch(self.dialog)  # (its parent the window: Qt deletes it with it)
        for widget in (self.dialog, self.choice_a, self.choice_b):
            widget.installEventFilter(found)
        self.filters.append(found)

    def theme_changed(self):
        """Dark mode switched, either way (the shared module's theme_switched): what is drawn here in the
        palette's colors drawn again from the new one, the fonts not read again: the glyphs' pictures
        (each font in its own color), the comparison, the pair, and the feature's differences. The
        selected glyph stays selected."""
        try:
            index = self.index_of(self.selected_item(self.glyph_tree))
        except Exception:
            index = -1
        try:
            self.fill_glyphs()
            if index >= 0:
                for item in self.top_items(self.glyph_tree) if hasattr(self, "top_items") else []:
                    if self.index_of(item) == index:
                        self.glyph_tree.setCurrentItem(item)
                        break
        except Exception:
            pass
        self.redraws = dict((key, True) for key in ("comparison", "pair"))
        self.redraw_now()
        try:
            self.feature_selected()
        except Exception:
            pass

    def redraw_now(self):
        keys, self.redraws = list(self.redraws), {}
        for key in keys:
            try:
                if key == "comparison":
                    self.draw_comparison()
                elif key == "pair":
                    self.draw_pair()
            except Exception:
                pass  # a timer's handler must not raise

    def page(self, QtGui):
        widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        status = self.ak.status_label()
        box.addWidget(status)
        return widget, box, status

    def chip_row(self, kinds, on_toggle, tip, first=()):
        QtCore, QtGui = _qt()
        row = QtGui.QHBoxLayout()
        chips = []
        for kind in kinds:
            chip = QtGui.QToolButton()
            chip.setCheckable(True)
            chip.setChecked(kind in first)  # (each comparison sets them again: fill_chips)
            chip.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # (drawn by CHIP_SHEET in the palette's colors)
            chip.setStyleSheet(CHIP_SHEET)
            chip.setWhatsThis(tip)
            chip.setVisible(False)
            chip.connect("toggled(bool)", lambda on: on_toggle())
            row.addWidget(chip)
            chips.append((kind, chip))
        row.addStretch(1)
        return row, chips

    def build_glyphs(self, QtCore, QtGui):
        ak = self.ak
        widget, box, self.glyph_status = self.page(QtGui)
        row, self.glyph_chips = self.chip_row(GLYPH_KINDS, self.fill_glyphs,
                                              u"Shows or hides this kind of difference in the list (the count: glyphs "
                                              u"with it). A glyph left with no kind shown is hidden; the others are "
                                              u"ranked by the kinds shown. The glyphs only in one font are hidden to "
                                              u"start with, so the list compares what both fonts have (shown when "
                                              u"nothing else differs).", GLYPH_KINDS_FIRST)
        box.addLayout(row)
        halves = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.glyph_tree = self.tree(("Glyph", "Differences"), icon=THUMB_SIZE)
        self.glyph_tree.setWhatsThis(u"The glyphs that differ, the worst first (only in one font, then outlines, "
                                     u"components, names and code points, metrics, anchors), each drawn from both "
                                     u"fonts: the first in the text color, the second in the highlight color. "
                                     u"Right-click to flag a glyph in the first font.")
        halves.addWidget(self.glyph_tree)
        right = QtGui.QWidget()
        side = QtGui.QVBoxLayout(right)
        side.setContentsMargins(4, 0, 0, 0)
        self.comparison = self.picture_label((360, 260))
        self.comparison.setWhatsThis(u"The selected glyph from the first font (left, in the text color), both overlaid "
                                     u"(middle), and from the second (right, in the highlight color), at one scale; "
                                     u"the dashed lines are the advance widths. A font without the glyph shows a "
                                     u"dashed empty frame.")
        side.addWidget(self.comparison, 1)
        self.difference_label = ak.status_label()
        side.addWidget(self.difference_label)
        halves.addWidget(right)
        halves.setStretchFactor(0, 2)
        halves.setStretchFactor(1, 3)
        box.addWidget(halves, 1)
        self.glyph_tree.connect("itemSelectionChanged()", self.glyph_selected)
        self.watch_resize(self.comparison, "comparison")
        return widget

    def build_kerning(self, QtCore, QtGui):
        widget, box, self.kern_status = self.page(QtGui)
        row, self.kern_chips = self.chip_row(KERN_KINDS, self.fill_kerning,
                                             u"Shows or hides these pairs (the count: pairs). Only the pairs kerned in "
                                             u"both fonts with differing values are shown to start with (every other kind "
                                             u"when there are none): the pairs only one font kerns, and those of a glyph "
                                             u"one font lacks (the Glyphs tab lists those glyphs), are a click away.",
                                             KERN_KINDS_FIRST)
        box.addLayout(row)
        halves = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.kern_tree = self.tree(("Pair", "First", "Second", "Difference"))
        self.kern_tree.setWhatsThis(u"The glyph pairs kerned differently, the largest difference first: the value in "
                                    u"each font (0: not kerned) and the second's minus the first's. Class kerning is "
                                    u"resolved to its glyph pairs, as FontLab applies it. Right-click to flag a pair's "
                                    u"glyphs in the first font.")
        halves.addWidget(self.kern_tree)
        self.pair_picture = self.picture_label((280, 200))
        self.pair_picture.setWhatsThis(u"The selected pair in the first font (text color) and in the second (highlight "
                                       u"color), each at its own value.")
        halves.addWidget(self.pair_picture)
        halves.setStretchFactor(0, 3)
        halves.setStretchFactor(1, 2)
        box.addWidget(halves, 1)
        self.kern_tree.connect("itemSelectionChanged()", self.draw_pair)
        self.watch_resize(self.pair_picture, "pair")
        return widget

    def build_features(self, QtCore, QtGui):
        ak = self.ak
        widget, box, self.feature_status = self.page(QtGui)
        row = QtGui.QHBoxLayout()
        self.show_same = QtGui.QCheckBox("Show the features that are alike")
        self.show_same.setWhatsThis(u"Lists the features whose code is the same in both fonts too.")
        row.addWidget(self.show_same)
        row.addStretch(1)
        box.addLayout(row)
        halves = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.feature_tree = self.tree(("Feature", "Difference"))
        self.feature_tree.setWhatsThis(u"The features only in one font or whose code differs, in the first font's order; "
                                       u"<i>Prefix</i> is the code before the features, <i>Classes</i> the classes of the "
                                       u"Classes panel.")
        halves.addWidget(self.feature_tree)
        self.diff_view = QtGui.QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setProperty(ak.LEAVE_ALONE_PROP, True)  # (as the log: its colors are the palette's, its tints drawn)
        self.diff_view.setWhatsThis(u"The selected feature's code: lines only in the first font on red, after a minus; "
                                    u"lines only in the second on green, after a plus; three lines around each change, "
                                    u"the rest left out.")
        halves.addWidget(self.diff_view)
        halves.setStretchFactor(0, 1)
        halves.setStretchFactor(1, 3)
        box.addWidget(halves, 1)
        self.show_same.connect("toggled(bool)", lambda on: self.fill_features())
        self.feature_tree.connect("itemSelectionChanged()", self.feature_selected)
        return widget

    # -- the fonts -----------------------------------------------------------

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = self.ak.window_font(self, workspace)  # this window's font
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def font_number(self, package):
        """What tells an open font from every other: FontLab's number of it (fgPackage.id, the same through
        every Python wrapper of the font), since two open fonts can share a name; its file, or its name,
        where the number cannot be read. (Not named font_id: the window model keeps this window's font's
        number in an attribute of that name.)"""
        try:
            found = package.fgPackage.id
        except Exception:
            found = None
        return found if found is not None else self.ak.font_key(package)

    def open_fonts(self):
        """The open fonts, this window's first (own_listed: whether it is there), each once."""
        current = self.current_font()
        self.own_listed = current is not None
        found = [current] if current is not None else []
        keys = set(self.font_number(p) for p in found)
        try:
            listed = list(self.fontlab.flWorkspace.instance().packages())
        except Exception:
            listed = []
        for item in listed:
            try:
                package = self.fontlab.flPackage(item)
                if package is None or package.isNull or not package.glyphsCount:
                    continue
                key = self.font_number(package)
            except Exception:
                continue
            if key not in keys:
                keys.add(key)
                found.append(package)
        return found

    @staticmethod
    def masters_of(package):
        try:
            found = [u"%s" % name for name in package.masters]
        except Exception:
            found = []
        if not found:
            try:
                found = [u"%s" % package.master]
            except Exception:
                found = []
        return found

    OPEN_FILTER = u"Fonts (*.vfc *.vfj *.vfb *.otf *.ttf *.otc *.ttc *.woff *.woff2 *.ufo *.glyphs *.designspace);;All files (*)"
    OPEN_WAIT_MS, OPEN_TRIES = 500, 120  # FontLab opens a font in the background: looked for twice a second, a minute

    @staticmethod
    def same_file(a, b):
        try:
            return os.path.normcase(os.path.abspath(u"%s" % a)) == os.path.normcase(os.path.abspath(u"%s" % b))
        except Exception:
            return False

    def installed(self):
        """The fonts installed on Windows (installed_fonts), [] when they cannot be listed."""
        try:
            return installed_fonts()
        except Exception:
            return []

    @staticmethod
    def normal_path(path):
        """A file's path as same_file compares it (absolute, in Windows' case), or None."""
        try:
            return os.path.normcase(os.path.abspath(u"%s" % path))
        except Exception:
            return None

    def installed_rows(self, fonts):
        """The second dropdown's rows of the installed fonts not open already (installed_entries). They
        are made again only when the installed fonts or the open fonts' files change: read_fonts runs at
        each press, focus, and activation of the window, and made and sorted some 4,000 rows each time,
        comparing each file with each open font's (0.1 s a click with five fonts open)."""
        found = self.installed()
        opened = frozenset(self.normal_path(p.path) for p in fonts if getattr(p, "path", None))
        held = getattr(self, "installed_held", None)
        if held is not None and held[0] is found and held[1] == opened:
            return held[2]
        normal = self.normal_path
        rows = installed_entries([(path, name) for path, name in found if normal(path) not in opened])
        self.installed_held = (found, opened, rows)
        return rows

    def placeholder_unpickable(self):
        """The second dropdown's placeholder shown, not picked: its row grayed out in the list (its flags
        cleared, as Qt's own model reads them), so that it does nothing when clicked; and left out of the
        open list (popup_rows_hidden), where it read as the box's text twice (the owner's screenshot 98)."""
        QtCore = _qt()[0]
        try:
            for index, row in enumerate(self.second_rows):
                if row[0] == "none":
                    self.choice_b.setItemData(index, 0, int(QtCore.Qt.UserRole) - 1)
        except Exception:
            pass  # (a Qt whose model will not: picking it still changes nothing, second_activated)
        try:
            view = self.choice_b.view()
            hidden = popup_rows_hidden(self.second_rows)
            for index in range(len(self.second_rows)):
                view.setRowHidden(index, index in hidden)
        except Exception:
            pass  # (shown, grayed out, as before)

    def open_folder(self):
        """Where Open a font... starts: the folder of the last font opened from it, else Windows' font
        folder (or the user's own)."""
        last = getattr(self, "last_folder", None)
        if last and os.path.isdir(last):
            return last
        folders = font_folders()
        return folders[0] if folders else u""

    def open_font(self, path=None):
        """The second dropdown's Open a font... row (a font file picked, the dialog starting in a font
        folder), or an installed font's row (path): the font opened in FontLab; once it is in, chosen as
        the second font (at once when it is open already)."""
        QtCore, QtGui = _qt()
        if path is None:
            path = QtGui.QFileDialog.getOpenFileName(self.dialog, u"Open a font to compare", self.open_folder(),
                                                     self.OPEN_FILTER)
            path = u"%s" % (path[0] if isinstance(path, (tuple, list)) else path or u"")
            if path:
                self.last_folder = os.path.dirname(path)
        if not path:
            return
        fonts = self.open_fonts()
        there = [p for p in fonts if getattr(p, "path", None) and self.same_file(p.path, path)]
        if there:
            self.opening = None  # (a font still being looked for is not chosen over this one)
            try:
                self.choose_second(there[0], u"%s is open already", True)
            except Exception as exc:
                self.log.add(u"Could not choose that font: %s" % self.ak.html(exc), "error")
            return
        before = set(self.font_number(p) for p in fonts)
        try:
            self.fontlab.flItems.requestLoadingFont(path)
        except Exception as exc:
            self.log.add(u"FontLab did not open %s: %s" % (self.ak.i(os.path.basename(path)), self.ak.html(exc)), "error")
            return
        self.log.add(u"Opening %s in FontLab\N{HORIZONTAL ELLIPSIS}" % self.ak.i(os.path.basename(path)))
        # One poll pending at a time: a second font opened before the first came in is the one looked for,
        # and the files picked before it (superseded) may still come in first
        earlier = getattr(self, "opening", None)
        superseded = (earlier[2] | set([earlier[0]])) if earlier is not None else set()
        self.opening, self.open_tries = (path, before, superseded), 0
        timer = getattr(self, "open_timer", None)
        if timer is None:
            timer = self.open_timer = QtCore.QTimer(self.dialog)  # (its parent the window: Qt deletes it with it)
            timer.setSingleShot(True)
            timer.setInterval(self.OPEN_WAIT_MS)
            timer.connect("timeout()", self.look_for_opened)
        timer.start()

    def look_for_opened(self):
        """The font being opened (open_font), chosen once it is in; looked for again until OPEN_TRIES.
        The font with the file's path is taken; another font that came in is taken only while no file
        picked before is on its way (a font opened from a binary file may not give its path), since it
        may be that earlier file's."""
        opening = getattr(self, "opening", None)
        if opening is None:
            return
        path, before, superseded = opening
        try:
            new = [p for p in self.open_fonts() if self.font_number(p) not in before]
            named = [p for p in new if getattr(p, "path", None) and self.same_file(p.path, path)]
            found = named or ([] if superseded else new)
            if not found:
                self.open_tries += 1
                if self.open_tries < self.OPEN_TRIES:
                    self.open_timer.start()
                else:
                    self.opening = None
                    self.log.add((u"%s was not among the fonts that came in: choose it in <i>with</i>." if new else
                                  u"%s did not open (or FontLab is waiting for an answer in a dialog).")
                                 % self.ak.i(os.path.basename(path)), "warning")
                return
            self.opening = None
            self.choose_second(found[0], u"Opened %s", True)  # (the file's own, when another font came in too)
        except Exception as exc:
            self.opening = None
            self.log.add(u"Could not choose the font just opened: %s" % self.ak.html(exc), "error")

    def choose_second(self, package, said, then_compare=False):
        """An open font chosen as the second font, and said so (said: how the log's line starts, %s standing
        for the font's name); then_compare: compared too, with this window brought back to the front
        (compare_opened). True when chosen."""
        self.read_fonts()
        key = self.font_number(package)
        first = self.first_key()
        masters = [row[2] for row in self.second_rows if row[0] == "font" and row[1] == key]
        if first is not None and first[0] == key:  # a master of the first font: another than the first side's
            masters = [master for master in masters if master != first[1]]
        if not masters:  # this window's own font, with one master: not in the list
            self.log.add(u"%s is the first font, and has one master: there is nothing to compare it with. "
                         u"Choose another font in <i>with</i>." % self.ak.b(package.tfn), "warning")
            return False
        try:
            current = u"%s" % package.master
        except Exception:
            current = None
        self.set_second((key, current if current in masters else masters[0]))
        self.say_state(True)
        self.update_buttons()
        if then_compare:
            self.log.add((said + u": chosen as the second font.") % self.ak.b(package.tfn), "done")  # (the comparison says its own)
            self.compare_opened()
        else:
            self.log.add((said + u": chosen as the second font. Click %s.") % (
                self.ak.b(package.tfn), self.ak.i(u"Compare")), "done")
        return True

    def compare_opened(self):
        """A font opened from the second dropdown (a file, or an installed font), now chosen: compared without
        a click on Compare, and this window brought back to the front. FontLab makes the new font's window
        the active one as it lists the font, which sent this window behind it: it is brought forward now,
        again once FontLab has settled (OPEN_SETTLE_MS), and after the comparison."""
        QtCore, QtGui = _qt()
        self.bring_forward()
        timer = getattr(self, "settle_timer", None)
        if timer is None:
            timer = self.settle_timer = QtCore.QTimer(self.dialog)  # (its parent the window: Qt deletes it with it)
            timer.setSingleShot(True)
            timer.setInterval(OPEN_SETTLE_MS)
            timer.connect("timeout()", self.settled)
        timer.start()

    def settled(self):
        """compare_opened's comparison, once FontLab has settled (again later while one runs); nothing once
        the window is closed (a comparison would hold the user's clicks for a window no one sees)."""
        try:
            if not self.shown():
                return
            if self.busy:
                self.settle_timer.start()
                return
            self.bring_forward()
            if self.missing():
                return  # (the choice changed meanwhile: the top line says what is missing)
            self.compare()
            self.bring_forward()
            QtCore, QtGui = _qt()
            late = getattr(self, "late_timer", None)
            if late is None:  # (once more a while later: FreeLab's tab docking merges the new window, and
                # activates FontLab's, once a second)
                late = self.late_timer = QtCore.QTimer(self.dialog)  # (its parent the window: Qt deletes it with it)
                late.setSingleShot(True)
                late.setInterval(OPEN_LATE_MS)
                late.connect("timeout()", self.bring_forward)
            late.start()
        except Exception:
            pass  # a timer's handler must not raise

    def shown(self):
        """Whether the window is on screen: visible, and not closed (the tool let go) or minimized."""
        try:
            return _prop(self.dialog, "visible") is True and _prop(self.dialog, "minimized") is not True
        except Exception:
            return False

    def bring_forward(self):
        """This window raised and made the active one, while it is shown (shown): a window the user
        minimized or closed meanwhile is left as it is, never restored. Never raises."""
        try:
            if self.shown():
                self.dialog.raise_()
                self.dialog.activateWindow()
        except Exception:
            pass

    def swap(self):
        """The two masters of this window's font exchanged; compared again when they had been. Two
        fonts are not exchanged: the first side is the window's font."""
        a, b = self.first_key(), self.second_key
        if not self.can_swap():
            return
        compared = self.sides is not None
        self.filling = True
        try:
            self.choice_a.setCurrentIndex([row[:2] for row in self.first_rows].index(b))
        finally:
            self.filling = False
        self.set_second(a)
        self.update_buttons()
        if compared:
            self.compare()

    def can_swap(self):
        a, b = self.first_key(), self.second_key
        return a is not None and b is not None and a[0] == b[0] and a[1] != b[1] and b in [row[:2] for row in self.first_rows]

    @staticmethod
    def file_name(package):
        """A font's file's name, to tell two fonts of one name apart; u"" for a font never saved."""
        try:
            return os.path.basename(u"%s" % (package.path or u""))
        except Exception:
            return u""

    @staticmethod
    def fill_box(box, texts):
        """A dropdown's rows set (None: a separator, which takes a row of its own in Qt's count too)."""
        box.clear()
        for index, text in enumerate(texts):
            if text is None:
                try:
                    box.insertSeparator(index)
                except Exception:
                    box.addItem(u"")  # (a Qt that will not: an empty row keeps the rows' numbers)
            else:
                box.addItem(text)

    def read_fonts(self):
        """The dropdowns filled from the fonts FontLab has open now, each choice kept while its font (by
        FontLab's number of it, not its name) and master are still there: the first lists this window's
        font's masters, the second the other fonts (second_entries), empty until a choice is made. A
        list that did not change is left as it is (it may be open). False when the window has no font."""
        wanted = self.first_key()
        fonts = self.open_fonts()
        listed = [(self.font_number(p), u"%s" % p.tfn, self.masters_of(p), self.file_name(p)) for p in fonts]
        self.fonts = fonts
        self.by_id = dict((entry[0], package) for entry, package in zip(listed, fonts))
        own = listed[0] if self.own_listed and listed else None
        first = first_entries(own) if own is not None else []
        installed_rows = []
        if own is not None:  # (the fonts installed on Windows, those not open already, to compare with directly)
            installed_rows = self.installed_rows(fonts)
        second = second_entries(listed, own[0] if own is not None else None, installed_rows=installed_rows)
        lost = False
        self.filling = True
        try:
            if first != self.first_rows:
                self.first_rows = first
                self.fill_box(self.choice_a, [row[2] for row in first])
                keys = [row[:2] for row in first]
                if wanted not in keys and own is not None:
                    try:  # the master FontLab shows, to start with
                        wanted = (own[0], u"%s" % fonts[0].master)
                    except Exception:
                        wanted = None
                if keys:
                    self.choice_a.setCurrentIndex(keys.index(wanted) if wanted in keys else 0)
            if second != self.second_rows:
                self.second_rows = second
                self.fill_box(self.choice_b, [None if row[0] == "separator" else row[3] for row in second])
                self.placeholder_unpickable()
            held = self.second_key
            lost = not self.set_second(held) and held is not None  # (its font closed, or its master gone)
        finally:
            self.filling = False
        if lost:
            self.log.add(u"The second font chosen is no longer open (or no longer has that master): choose again in "
                         u"<i>with</i>.", "warning")
        self.say_state()
        self.update_buttons()
        return own is not None

    def set_second(self, key):
        """The second side set to (font number, master), or to nothing (None, or a font or master that
        is not listed): the placeholder shows. True when it is chosen."""
        index = next((k for k, row in enumerate(self.second_rows) if row[0] == "font" and row[1:3] == tuple(key or ())), 0)
        self.second_key = tuple(key) if index else None
        filling, self.filling = self.filling, True
        try:
            if _prop(self.choice_b, "currentIndex") != index:
                self.choice_b.setCurrentIndex(index)
        finally:
            self.filling = filling
        return bool(index)

    def first_key(self):
        """(font number, master) of the first side, or None while the window has no font."""
        index = _prop(self.choice_a, "currentIndex")
        if not isinstance(index, int) or not 0 <= index < len(self.first_rows):
            return None
        return self.first_rows[index][:2]

    def chosen(self, box):
        """(package, master) chosen in a dropdown, or None."""
        key = self.first_key() if box is self.choice_a else self.second_key
        package = self.by_id.get(key[0]) if key is not None else None
        return (package, key[1]) if package is not None else None

    def missing(self):
        """What keeps Compare grayed (missing_line), or u"" when both sides are chosen."""
        own = self.fonts[0] if self.own_listed and self.fonts else None
        first, second = self.first_key(), self.second_key
        line = missing_line(self.ak.b(own.tfn) if own is not None else None, len(self.fonts) - (1 if own is not None else 0),
                            len(self.first_rows), second is not None, second is not None and second == first)
        if own is None and hasattr(self.ak, "no_font_line"):
            line = self.ak.no_font_line(line)  # (while other fonts are open, why this window has none)
        return line

    def say_state(self, changed=False):
        """The top line: what is missing, while something is; that Compare can be clicked, before the
        first comparison and after a choice changed (the lists below then show the last comparison)."""
        text = self.missing()
        if not text and (changed or self.sides is None):
            text = u"Click %s to compare the fonts chosen." % self.ak.i("Compare")
        if text:
            self.font_label.setText(text)

    def second_activated(self, index):
        """A row of the second dropdown picked by the user: its last row opens a font file, the choice
        staying what it was (the font opened is chosen once FontLab has it)."""
        try:
            row = self.second_rows[index] if isinstance(index, int) and 0 <= index < len(self.second_rows) else None
            kind = row[0] if row is not None else None
            if kind in ("open", "separator", "installed", "none"):  # (no open font: the dropdown shows the choice again)
                self.set_second(self.second_key)
            if kind == "open":
                self.open_font()
            elif kind == "installed":
                self.open_font(row[1])  # (opened in FontLab, then chosen once it is in)
        except Exception as exc:  # a signal's handler must not raise
            self.log.add(u"Could not open a font: %s" % self.ak.html(exc), "error")

    def choice_changed(self):
        """A dropdown's row changed (by the user: the code's own changes are made while filling)."""
        if self.filling or self.busy:
            return
        try:
            index = _prop(self.choice_b, "currentIndex")
            row = self.second_rows[index] if isinstance(index, int) and 0 <= index < len(self.second_rows) else None
            if row is not None and row[0] == "font":
                self.second_key = row[1:3]
            elif row is not None and row[0] == "none" and self.second_key is None:
                pass  # (the placeholder, shown while nothing is chosen)
            elif row is not None:
                return  # a row that opens a file, or the placeholder: second_activated puts the choice back
            self.say_state(True)
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def colors(self):
        QtCore, QtGui = _qt()
        palette = _prop(self.dialog, "palette")
        return {"text": palette.color(QtGui.QPalette.WindowText), "base": palette.color(QtGui.QPalette.Window),
                "highlight": palette.color(QtGui.QPalette.Highlight)}

    def icon(self, draw, *args):
        """A QIcon of a picture drawn (an empty one, and a warning once per window, when drawing failed)."""
        QtCore, QtGui = _qt()
        try:
            return QtGui.QIcon(draw(*args))
        except Exception as exc:
            if not self.drawing_failed:
                self.drawing_failed = True
                self.log.add(u"A picture could not be drawn: %s" % self.ak.html(exc), "warning")
            return QtGui.QIcon()

    # -- long work -----------------------------------------------------------

    busy_shown, busy_since = False, 0.0

    def has_font(self):
        """Whether a comparison can be made (ak.window_has_font): this window's font and a second side
        chosen, nothing missing. Without one, the shared module grays the controls but those that choose
        the fonts (owner's image 209). Never raises."""
        try:
            return self.first_key() is not None and self.second_key is not None and not self.missing()
        except Exception:
            return True

    def busy_widgets(self):
        """What is grayed while a comparison runs (Close is not: a click stops it, then closes)."""
        return [getattr(self, name, None) for name in ("choice_a", "choice_b", "swap_button", "threshold",
                                                       "compare_button", "tabs", "pages")]

    def set_busy(self, on):
        """A comparison begun or over. While busy, the History watchers, dark mode, the dropdowns' reading,
        and the window's release wait. The top row's bar and the grayed controls show once the comparison
        has taken SHOW_AFTER (progress). Never raises."""
        self.busy = bool(on)
        self.busy_since = time.time()
        if on or not self.busy_shown:
            return
        self.busy_shown = False
        self.ak.busy_end(self)  # (and what was clicked meanwhile done: a tool, an arrow, Close)
        try:
            for widget in (self.choice_a, self.tabs, self.pages):  # (the others as the choices want them: update_buttons)
                self.ak.enable(widget, True)
        except Exception:
            pass

    def show_busy(self, label):
        """The top row's bar shown (its step, label) and the controls grayed."""
        if self.busy_shown:
            return
        self.busy_shown = True
        try:
            for widget in self.busy_widgets():
                if widget is not None:
                    self.ak.enable(widget, False)
        except Exception:
            pass
        self.ak.busy_start(self, label)

    def progress(self, label, part=0.0, stoppable=True):
        """The comparison at this part (0 to 1) of the step of that label (COMPARE_STEPS), in the window's top
        row once it has taken SHOW_AFTER (ak.busy_progress: the window redrawn, the user's clicks and keys
        held but the tools menu's, the arrows', Close's, and Esc, which stop it). Raises ak.Stopped when the
        user asked it to stop, unless stoppable is False."""
        value = bar_value(COMPARE_STEPS, label, part)
        if value is None or not self.busy:
            return
        if not self.busy_shown and time.time() - self.busy_since >= SHOW_AFTER:
            self.show_busy(label)
        if self.busy_shown:
            self.ak.busy_progress(self, label, value, stoppable=stoppable)

    # -- comparing -----------------------------------------------------------

    def glyph_list(self, package):
        return [(u"%s" % fg.name, glyph_codes(fg)) for fg in package.fgPackage.glyphs]

    def layer_of(self, package, name, master):
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            return None
        layer = glyph.getLayerByName(master)
        if layer is None or getattr(layer, "isNull", False):
            return None
        return layer

    def read_glyph(self, side, name, codes, factor=1.0):
        """(GlyphData, (its path, its advance width) scaled by factor) of a glyph in a side's master,
        (None, None) without a layer there."""
        QtCore, QtGui = _qt()
        layer = self.layer_of(side.package, name, side.master)
        if layer is None:
            return None, None
        data = read_layer(name, codes, layer)
        if data is None:
            raise ValueError(u"%s could not be read in %s" % (name, side.label))
        path = self.ak.layer_path(layer)
        box = ink_box(path)
        data.ink = None if box is None else (box[0], box[2])
        if factor != 1:
            transform = QtGui.QTransform()
            transform.scale(factor, factor)
            path = transform.map(path)
        return data, (path, data.advance * factor)

    def path_of(self, side, name, opened=None):
        """A glyph's (path, advance width) in a side's master, scaled to the first font's em, read when first
        asked for and kept: the glyphs only in one font are read as they are listed, not all at a comparison.
        None without the glyph, a layer, or a read, and for a font closed since the comparison (opened: the
        numbers of the fonts open now, open_numbers; the lists keep the last comparison, and FontLab is never
        asked about a closed font: nothing is drawn, and nothing kept, so it is read once the font is back)."""
        if name is None:
            return None
        if name not in side.paths:
            if side.number not in (opened if opened is not None else self.open_numbers()):
                return None
            try:
                side.paths[name] = self.read_glyph(side, name, [], side.factor)[1]
            except Exception:
                side.paths[name] = None
        return side.paths[name]

    def open_numbers(self):
        """FontLab's numbers of the fonts open now (font_number), read afresh: a font compared may have been
        closed since the dropdowns were last read. Those of the last reading where FontLab cannot be asked."""
        try:
            return set(self.font_number(package) for package in self.open_fonts())
        except Exception:
            return set(self.by_id)

    def kerning_of(self, side):
        """A master's kerning, {(left, right): value}, classes resolved as FontLab applies them."""
        kerning = self.ak.FontKerning(side.package.kerning(side.master))
        if kerning.plain is not None:
            return dict((pair, value) for pair, value in kerning.plain.items() if value)
        return resolve_entries(kerning.values, kerning.members)

    @staticmethod
    def features_of(package):
        """[(tag, code)] of a font's features, its prefix first and the Classes panel's classes last."""
        found = []
        features = package.fgPackage.features
        try:
            prefix = features.get_prefix() or u""
        except Exception:
            prefix = u""
        if code_lines(prefix):
            found.append((PREFIX, u"%s" % prefix))
        for tag in features.keys():
            found.append((u"%s" % tag, u"%s" % (features.get_feature(tag) or u"")))
        try:
            groups = [(u"%s" % g[1], [u"%s" % n for n in g[4]]) for g in package.getAllGroups() if not g[0]]
        except Exception:
            groups = []
        if groups:
            found.append((CLASSES, classes_text(groups)))
        return found

    def compare(self):
        """Both choices compared: glyphs, kerning, and features."""
        if self.busy:
            return
        try:  # (a click on Compare while a font just opened waits to be compared: compared once, now)
            settle = getattr(self, "settle_timer", None)
            if settle is not None:
                settle.stop()
        except Exception:
            pass
        self.read_fonts()  # (and what is missing said, the button grayed)
        a, b = self.chosen(self.choice_a), self.chosen(self.choice_b)
        ak = self.ak
        if a is None or b is None or self.missing():
            return
        self.set_busy(True)
        ak.enable(self.compare_button, False)
        before = self.compared_state()
        try:
            self.run(a, b)
        except ak.Stopped:  # (by the user: the comparison shown before stays, as it was)
            self.put_back_state(before)
            self.log.add(u"The comparison was stopped: the lists show the one before it.", "warning")
        except Exception as exc:
            self.font_label.setText(u"The comparison stopped: see the log.")
            self.log.add(ak.html(exc), "error")
        finally:
            self.set_busy(False)
        self.update_buttons()

    STATE_NAMES = ("sides", "masters_mode", "results", "kern_rows", "feature_rows", "rename", "package", "seen_history")

    def compared_state(self):
        """What a comparison changes before it lists anything (put_back_state)."""
        state = dict((name, getattr(self, name, None)) for name in self.STATE_NAMES)
        state["second"] = (self.second.package, self.second.seen_history)
        try:
            state["line"] = u"%s" % (_prop(self.font_label, "text") or u"")
        except Exception:
            state["line"] = None
        return state

    def put_back_state(self, state):
        """A comparison stopped before its lists were filled: what it changed put back, so the lists, the
        top line, and the History's watchers stay with the comparison they show. Never raises."""
        try:
            for name in self.STATE_NAMES:
                setattr(self, name, state[name])
            self.second.package, self.second.seen_history = state["second"]
            if state["line"] is not None:
                self.font_label.setText(state["line"])
            else:
                self.say_state()
        except Exception:
            pass

    def run(self, a, b):
        ak, b_ = self.ak, self.ak.b
        (package_a, master_a), (package_b, master_b) = a, b
        same = self.font_number(package_a) == self.font_number(package_b)
        labels = side_labels((ak.font_key(package_a), u"%s" % package_a.tfn, master_a, len(self.masters_of(package_a))),
                             (ak.font_key(package_b), u"%s" % package_b.tfn, master_b, len(self.masters_of(package_b))),
                             same)
        first, second = Side(package_a, master_a, labels[0]), Side(package_b, master_b, labels[1])
        upm_a, upm_b = float(package_a.upm or 1000), float(package_b.upm or 1000)
        factor = upm_a / upm_b if upm_b else 1.0
        second.factor = factor  # (its glyphs drawn at the first one's em, as they are read: path_of)
        first.number, second.number = self.font_number(package_a), self.font_number(package_b)
        threshold = int(_prop(self.threshold, "value") or 0)
        self.font_label.setText(u"Comparing %s with %s\N{HORIZONTAL ELLIPSIS}" % (b_(labels[0]), b_(labels[1])))
        self.progress(READ_A_STEP)
        glyphs_a = self.glyph_list(package_a)
        self.progress(READ_B_STEP)
        glyphs_b = self.glyph_list(package_b)
        codes_a, codes_b = dict(glyphs_a), dict(glyphs_b)
        pairs, only_a, only_b = match_glyphs(glyphs_a, glyphs_b)
        self.rename = rename = dict((name_b, name_a) for name_a, name_b in pairs if name_a != name_b)
        results, unread = [], []
        total = float(len(pairs) or 1)
        for done, (name_a, name_b) in enumerate(pairs):
            if done % PROGRESS_EVERY == 0:
                self.progress(GLYPHS_STEP, done / total)
            try:
                data_a, picture_a = self.read_glyph(first, name_a, codes_a.get(name_a, []))
                data_b, picture_b = self.read_glyph(second, name_b, codes_b.get(name_b, []), factor)
            except Exception:
                unread.append(name_a)
                continue
            if data_b is not None:
                data_b = data_b.scaled(factor).renamed(rename)
            found = compare_glyph(data_a, data_b, threshold, labels, upm_a, same)
            if found:
                results.append(GlyphResult(name_a if data_a is not None else None,
                                           name_b if data_b is not None else None, found))
                first.paths[name_a], second.paths[name_b] = picture_a, picture_b
        for side, names, kind in ((first, only_a, "only_a"), (second, only_b, "only_b")):
            # (their pictures read as they are listed, path_of: a CJK font has thousands no other font has,
            # each read whole here before, and their kind is hidden to start with)
            text = u"only in %s" % side.label
            for name in names:
                results.append(GlyphResult(name if kind == "only_a" else None, name if kind == "only_b" else None,
                                           [Difference(kind, text, text)]))
        self.sides, self.masters_mode, self.results = (first, second), same, results
        if unread:
            self.log.add(u"Could not read %s: %s." % (counted(len(unread), u"glyph"), ak.html(u", ".join(unread[:20]))
                                                     + (u"\N{HORIZONTAL ELLIPSIS}" if len(unread) > 20 else u"")), "warning")
            unread = []

        self.progress(KERNING_STEP)
        try:
            kern_a = self.kerning_of(first)
            self.progress(KERNING_STEP, 0.4)
            kern_b = dict((pair, value * factor) for pair, value in self.kerning_of(second).items())
            self.progress(KERNING_STEP, 0.8)
            known_a = set(name for name, _ in glyphs_a)
            known_b = set(rename.get(name, name) for name, _ in glyphs_b)
            self.kern_rows = kerning_diff(kern_a, kern_b, threshold, rename, known_a, known_b)
        except Exception as exc:
            self.kern_rows = []
            unread.append(u"kerning (%s)" % ak.html(exc))
        self.progress(FEATURES_STEP)
        if same:
            self.feature_rows = []
        else:
            try:
                self.feature_rows = feature_diff(self.features_of(package_a), self.features_of(package_b))
            except Exception as exc:
                self.feature_rows = []
                unread.append(u"features (%s)" % ak.html(exc))
        for what in unread:
            self.log.add(u"Could not read the %s." % what, "warning")

        self.package = package_a
        self.seen_history = ak.history_mark(package_a)
        self.second.package = None if same else package_b
        self.second.seen_history = None if same else ak.history_mark(package_b)
        both = len(pairs)
        text = u"Compared %s with %s: %s in both" % (b_(labels[0]), b_(labels[1]), b_(counted(both, u"glyph")))
        if not same:
            text += u", %s only in %s, %s only in %s" % (b_(grouped(len(only_a))), html_escape(labels[0]),
                                                         b_(grouped(len(only_b))), html_escape(labels[1]))
        text += u"."
        if factor != 1:
            text += u" %s has %s units per em, %s has %s: its values are scaled to %s." % (
                html_escape(labels[1]), b_(round_units(upm_b)), html_escape(labels[0]), b_(round_units(upm_a)), b_(round_units(upm_a)))
        self.font_label.setText(text)
        self.log.add(u"Compared %s with %s." % (b_(labels[0]), b_(labels[1])), "done")
        noted = set()
        for side in self.sides:
            note = self.ak.color_note(side.package) if side.package.tfn not in noted else u""
            noted.add(side.package.tfn)
            if note:
                self.log.add(note)
        self.progress(LIST_STEP)  # (the last chance to stop: the lists are filled from here on)
        self.fill_chips()
        self.fill_glyphs()
        self.fill_kerning()
        self.fill_features()
        self.progress(LIST_STEP, 1.0, stoppable=False)

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick): the
        dropdowns read again (the first lists the new font's masters, or nothing), the top line says
        what is missing; a comparison shown is the old font's, and the log says so."""
        if self.busy:
            return
        compared = self.sides is not None
        self.read_fonts()
        if compared:
            self.log.add(u"This window's font changed: the lists show the last comparison until you click %s."
                         % self.ak.i(u"Compare"), "warning")

    def history_moved(self):
        """An undo, a redo, or an edit in either font: compared again. A font compared that was closed moves
        its History too (the live pass: "A font's History moved ... compared again", with the old results
        still listed and nothing compared): that is said instead, and the comparison marked out of date."""
        QtCore, QtGui = _qt()
        if self.sides is None:
            return
        opened = self.open_numbers()
        closed = []
        for side in self.sides:
            if side.number not in opened and side.label not in closed:
                closed.append(side.label)
        if closed:  # (FontLab asked nothing of the closed font: its watcher let go of it, by its side's number)
            first, second = self.sides
            if first.number not in opened:
                self.package, self.seen_history = None, None
            if second.number not in opened or first.number not in opened and self.masters_mode:
                self.second.package, self.second.seen_history = None, None
            self.out_of_date(closed)
            return
        self.log.add(u"A font's History moved (an undo, a redo, or an edit): compared again.")
        QtCore.QTimer.singleShot(0, self.compare)

    def out_of_date(self, closed):
        """A font compared was closed (closed: the labels of its sides): the lists keep the last comparison (a
        closed font's glyphs not read yet drawn empty: path_of), and the top line and the log say it is out
        of date, once (history_moved lets the closed font's History watcher go)."""
        names = html_escape(u" and ".join(closed))
        verb = u"was" if len(closed) == 1 else u"were"
        self.font_label.setText(u"%s %s closed: the comparison shown is out of date. Choose a font in %s and "
                                u"click %s." % (self.ak.b(names), verb, self.ak.i(u"with"), self.ak.i(u"Compare")))
        self.log.add(u"%s %s closed: the comparison is out of date." % (self.ak.b(names), verb), "warning")

    # -- the tabs and buttons ------------------------------------------------

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        self.update_buttons()
        self.redraws.update({"comparison": True, "pair": True})  # (its size may have changed while hidden)
        self.redraw_timer.start()

    def current_key(self):
        index = _prop(self.tabs, "currentIndex")
        return TABS[index] if 0 <= index < len(TABS) else TABS[0]

    def update_buttons(self):
        ak = self.ak
        ready = self.first_key() is not None and self.second_key is not None and not self.missing()
        ak.enable(self.compare_button, not self.busy and ready)  # grayed until both sides are chosen
        ak.enable(self.swap_button, not self.busy and self.can_swap())
        # No font of its own: no second font to choose for it, no differences to ignore yet
        own = self.first_key() is not None
        ak.enable(self.choice_b, own and not self.busy)
        ak.enable(self.threshold, own)
        tab_texts = (u"Glyphs", u"Kerning", u"Features")
        if self.sides is not None:
            tab_texts = (u"Glyphs %s" % grouped(len(self.results)), u"Kerning %s" % grouped(
                sum(1 for d in self.kern_rows if d.kind != "absent")),
                u"Features %s" % grouped(sum(1 for f in self.feature_rows if f.kind != "same")))
        for index, text in enumerate(tab_texts):
            try:
                self.tabs.setTabText(index, text)
            except Exception:
                pass

    def labels(self):
        return (self.sides[0].label, self.sides[1].label) if self.sides is not None else (u"first", u"second")

    @staticmethod
    def item(texts, data, tip=u""):
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        item.setData(0, QtCore.Qt.UserRole, data)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if tip:
            for column in range(len(texts)):
                item.setToolTip(column, tip)
        return item

    @staticmethod
    def index_of(item):
        QtCore, QtGui = _qt()
        if item is None:
            return -1
        try:
            data = item.data(0, QtCore.Qt.UserRole)
            return int(data) if data is not None else -1
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def selected_item(view):
        try:
            items = view.selectedItems()
        except Exception:
            return None
        return items[0] if items else None

    @staticmethod
    def top_items(tree):
        return [tree.topLevelItem(i) for i in range(_prop(tree, "topLevelItemCount"))]

    def fit_columns(self, tree, widths):
        """The columns as wide as every row needs, at most the widths given (None: as is), the same in
        either theme (the shared fit_rows), the list's stretch column given the rest."""
        self.ak.fit_rows(tree, range(len(widths)), most=list(widths))
        self.ak.stretch_column(tree, measure=True)

    def select_first(self, tree, otherwise):
        items = self.top_items(tree)
        if items:
            tree.setCurrentItem(items[0])
        else:
            otherwise()

    # -- Glyphs --------------------------------------------------------------

    def fill_chips(self):
        labels = self.labels()
        counts_ = glyph_counts(self.results)
        on = kinds_first_on(counts_, GLYPH_KINDS_FIRST)
        for kind, chip in self.glyph_chips:
            count = counts_.get(kind, 0)
            chip.setText(u"%s %s" % (kind_label(kind, labels, self.masters_mode), grouped(count)))
            chip.setChecked(kind in on)
            chip.setVisible(bool(count))
        counts_ = kern_counts(self.kern_rows)
        on = kinds_first_on(counts_, KERN_KINDS_FIRST)
        for kind, chip in self.kern_chips:
            count = counts_.get(kind, 0)
            chip.setText(u"%s %s" % (kern_label(kind, labels), grouped(count)))
            chip.setChecked(kind in on)
            chip.setVisible(bool(count))

    @staticmethod
    def kinds_on(chips):
        return set(kind for kind, chip in chips if _prop(chip, "checked"))

    def fill_glyphs(self):
        QtCore, QtGui = _qt()
        if self.sides is None:
            return
        tree, colors = self.glyph_tree, self.colors()
        first, second = self.sides
        labels = self.labels()
        kinds = self.kinds_on(self.glyph_chips)
        found = glyph_rows(self.results, kinds)
        rows = self.glyph_names = found[:ROWS_SHOWN]
        opened = self.open_numbers()  # (once per filling: path_of reads a font only while it is open)
        self.filling = True
        self.ak.quiet_list(tree, True)
        try:
            tree.clear()
            for index, r in enumerate(rows):
                item = self.item((r.caption(), r.short(kinds)), index, r.sentence(labels))
                picture_a, picture_b = self.path_of(first, r.a, opened), self.path_of(second, r.b, opened)
                item.setIcon(0, self.icon(both_thumb, picture_a[0] if picture_a else None,
                                          picture_b[0] if picture_b else None, colors))
                tree.addTopLevelItem(item)
            self.fit_columns(tree, (COLUMN_MAX,))
        finally:
            self.ak.quiet_list(tree, False)
            self.filling = False
        changed = len(self.results)
        if self.results:
            text = u"%s %s." % (self.ak.b(counted(changed, u"glyph")), u"differs" if changed == 1 else u"differ")
            if len(rows) < len(found):
                text += u" The %s worst shown." % self.ak.b(grouped(len(rows)))
            elif len(rows) != changed:
                text += u" %s shown." % self.ak.b(grouped(len(rows)))
            counts_ = glyph_counts(self.results)
            hidden = [kind_label(kind, labels, self.masters_mode) for kind, _ in self.glyph_chips
                      if counts_.get(kind) and kind not in kinds]
            if hidden:
                text += u" Hidden: %s." % html_escape(u", ".join(hidden))
        else:
            text = u"The glyphs are alike: names, code points, metrics, outlines, components, and anchors."
        self.glyph_status.setText(text)
        self.select_first(tree, self.glyph_selected)

    def selected_result(self):
        index = self.index_of(self.selected_item(self.glyph_tree))
        rows = self.glyph_names
        return rows[index] if 0 <= index < len(rows) else None

    def first_name(self, r):
        """A row's glyph in the first font (two masters of one font: the glyph, whatever master lacks it)."""
        if r is None:
            return None
        return r.a if r.a is not None else (r.b if self.masters_mode else None)

    def row_glyph(self, item):
        index = self.index_of(item)
        rows = self.glyph_names
        name = self.first_name(rows[index] if 0 <= index < len(rows) else None)
        return [name] if name is not None else []

    def glyph_selected(self):
        if self.filling:
            return
        self.draw_comparison()
        self.update_buttons()

    def draw_comparison(self):
        if self.filling:
            return
        r = self.selected_result()
        if r is None or self.sides is None:
            self.comparison.clear()
            self.difference_label.setText(u"")
            return
        first, second = self.sides
        try:
            factor = second.factor  # the second font's paths are scaled to the first's em (run)
            opened = self.open_numbers()  # (a font closed since the comparison is asked nothing: its glyph drawn as kept)
            sides = []
            for side, name in ((first, r.a), (second, r.b)):
                picture = self.path_of(side, name, opened)
                path, advance = picture if picture else (None, 0.0)
                parts = None
                if path is not None and side.number in opened:
                    try:
                        layer = self.layer_of(side.package, name, side.master)
                        parts = self.ak.layer_parts(layer) if layer is not None else None
                        if parts and side is second and factor != 1:
                            transform = _qt()[1].QTransform()
                            transform.scale(factor, factor)
                            parts = [(transform.map(part), color) for part, color in parts]
                    except Exception:
                        parts = None
                sides.append((side.label, path, advance, parts))
            width = int(_prop(self.comparison, "width") or 0) or 600
            height = int(_prop(self.comparison, "height") or 0) or 400
            self.comparison.setPixmap(comparison_pixmap(width, height, sides[0], sides[1], self.colors(),
                                                        _prop(self.dialog, "font")))
        except Exception as exc:
            self.comparison.clear()
            self.log.add(u"The comparison could not be drawn: %s" % self.ak.html(exc), "warning")
        self.difference_label.setText(self.ak.html(r.sentence(self.labels())))

    # -- Kerning -------------------------------------------------------------

    def fill_kerning(self):
        if self.sides is None:
            return
        tree, labels = self.kern_tree, self.labels()
        on = self.kinds_on(self.kern_chips)
        found = [d for d in self.kern_rows if d.kind in on]
        rows = self.kern_shown = found[:ROWS_SHOWN]
        try:
            tree.setHeaderLabels([u"Pair", labels[0], labels[1], u"Difference"])
        except Exception:
            pass
        self.filling = True
        self.ak.quiet_list(tree, True)
        try:
            tree.clear()
            for index, d in enumerate(rows):
                tip = u"%s %s: %d in %s, %d in %s." % (d.left, d.right, d.a, labels[0], d.b, labels[1])
                if d.kind == "absent":
                    tip += u" A glyph of the pair is missing in one font."
                item = self.item((u"%s %s" % (d.left, d.right), u"%d" % d.a, u"%d" % d.b, signed(d.delta)), index, tip)
                tree.addTopLevelItem(item)
            if self.ak.table_stretch(tree) is None:  # (the pairs take the room; the values keep to the right of them)
                self.ak.set_stretch(tree, 0)
            self.ak.align_numbers(tree, (1, 2, 3))
            self.fit_columns(tree, (COLUMN_MAX, None, None, None))
        finally:
            self.ak.quiet_list(tree, False)
            self.filling = False
        counts_ = kern_counts(self.kern_rows)
        listed = sum(n for kind, n in counts_.items() if kind != "absent")
        b = self.ak.b
        if listed:
            text = u"%s kerned differently: %s only in %s, %s only in %s, %s with differing values." % (
                b(counted(listed, u"glyph pair")), b(grouped(counts_.get("only_a", 0))), html_escape(labels[0]),
                b(grouped(counts_.get("only_b", 0))), html_escape(labels[1]), b(grouped(counts_.get("value", 0))))
        else:
            text = u"The pairs of glyphs both fonts have are kerned alike."
        if counts_.get("absent"):
            text += u" %s of a glyph one font lacks." % b(counted(counts_["absent"], u"pair"))
        if len(rows) < len(found):
            text += u" The %s largest differences shown." % b(grouped(len(rows)))
        self.kern_status.setText(text)
        self.select_first(tree, self.draw_pair)

    def selected_pair(self):
        index = self.index_of(self.selected_item(self.kern_tree))
        return self.kern_shown[index] if 0 <= index < len(self.kern_shown) else None

    def row_pair(self, item):
        index = self.index_of(item)
        d = self.kern_shown[index] if 0 <= index < len(self.kern_shown) else None
        return [d.left, d.right] if d is not None else []

    def screen_pair(self, package, first, second):
        """A kerning key's glyphs as they stand on screen, (left, right): a right-to-left key (Hebrew,
        Arabic...) is in text order, its right glyph first, and is drawn the other way round. Each pair
        by its own glyphs (Auto Kerning's direction_char), whatever scripts the font has."""
        try:
            ak = self.ak
            return ak.screen_of_key(ak.direction_char(package, first), ak.direction_char(package, second),
                                    first, second)
        except Exception:
            return first, second

    def draw_pair(self):
        if self.filling:
            return
        d = self.selected_pair()
        if d is None or self.sides is None:
            self.pair_picture.clear()
            self.update_buttons()
            return
        first, second = self.sides
        opened = self.open_numbers()
        if first.number not in opened or second.number not in opened:  # (closed since: FontLab is asked nothing)
            self.pair_picture.clear()
            self.update_buttons()
            return
        back = dict((one, other) for other, one in self.rename.items())  # the first font's names to the second's
        font = _prop(self.dialog, "font")
        colors = self.colors()
        try:
            factor = float(first.package.upm) / float(second.package.upm)
        except Exception:
            factor = 1.0
        try:
            left, right = self.screen_pair(first.package, d.left, d.right)
            pictures = [self.ak.pair_pixmap(first.package, first.master, left, right, d.a,
                                            u"%s: %d" % (first.label, d.a), colors["text"], font),
                        self.ak.pair_pixmap(second.package, second.master, back.get(left, left),
                                            back.get(right, right), int(round(d.b / factor)) if factor else d.b,
                                            u"%s: %d" % (second.label, d.b), colors["highlight"], font)]
            self.pair_picture.setPixmap(stacked_pixmap(pictures))
        except Exception as exc:
            self.pair_picture.clear()
            self.log.add(u"The pair could not be drawn: %s" % self.ak.html(exc), "warning")
        self.update_buttons()

    # -- Features ------------------------------------------------------------

    def fill_features(self):
        if self.sides is None:
            return
        tree, labels = self.feature_tree, self.labels()
        same_shown = bool(_prop(self.show_same, "checked"))
        rows = [f for f in self.feature_rows if same_shown or f.kind != "same"]
        self.feature_shown = rows
        self.filling = True
        try:
            tree.clear()
            for index, f in enumerate(rows):
                state = feature_state(f, labels)
                tree.addTopLevelItem(self.item((f.tag, state), index, u"%s: %s." % (f.tag, state)))
            self.fit_columns(tree, (COLUMN_MAX,))
        finally:
            self.filling = False
        b = self.ak.b
        if self.masters_mode:
            text = u"Two masters of one font share their features and classes."
        elif not self.feature_rows:
            text = u"Neither font has features."
        else:
            differing = [f for f in self.feature_rows if f.kind != "same"]
            if differing:
                text = u"%s differ: %s only in %s, %s only in %s, %s with code that differs." % (
                    b(counted(len(differing), u"feature")),
                    b(grouped(sum(1 for f in differing if f.kind == "only_a"))), html_escape(labels[0]),
                    b(grouped(sum(1 for f in differing if f.kind == "only_b"))), html_escape(labels[1]),
                    b(grouped(sum(1 for f in differing if f.kind == "differs"))))
                if len(differing) == 1:
                    text = text.replace(u" differ:", u" differs:")
            else:
                text = (u"The one feature is alike in both." if len(self.feature_rows) == 1
                    else u"The %s are alike." % b(counted(len(self.feature_rows), u"feature")))
        self.feature_status.setText(text)
        self.select_first(tree, self.feature_selected)

    def feature_selected(self):
        if self.filling:
            return
        index = self.index_of(self.selected_item(self.feature_tree))
        f = self.feature_shown[index] if 0 <= index < len(self.feature_shown) else None
        if f is None:
            self.diff_view.clear()
            return
        QtCore, QtGui = _qt()
        palette = _prop(self.diff_view, "palette")
        base, text = palette.color(QtGui.QPalette.Base), palette.color(QtGui.QPalette.Text)
        rgb = lambda c: (c.red(), c.green(), c.blue())
        rows = f.rows if f.kind != "same" else [(u" ", line) for line in code_lines(f.a)]
        self.diff_view.setHtml(diff_html(rows, self.labels(), rgb(base), rgb(text)))

    # -- flags ---------------------------------------------------------------

    def selected_glyphs(self):
        """The first font's glyphs selected in the view shown, as it names them (flags). (No Glyph
        window: FontLab opens one on its current font only, which may be neither of the two.)"""
        key = self.current_key()
        if key == "glyphs":
            name = self.first_name(self.selected_result())
            return [name] if name is not None else []
        if key == "kerning":
            d = self.selected_pair()
            return [d.left, d.right] if d is not None else []
        return []

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()  # (nothing compared as it opens: the second font is the user's to choose)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("Font Compare"):
            return
    except Exception:
        pass
    dialog = CompareDialog()
    sys._freelab_font_compare = dialog  # kept, even half-built: PythonQt deletes a dialog with no Python reference
    if dialog.failed is not None:
        print("FreeLab Font Compare: %s" % dialog.failed)
        try:
            dialog.dialog.close()
        except Exception:
            pass
        return
    try:
        dialog.ak.hook_menu_order()
    except Exception:
        pass
    try:
        dialog.ak.take_window("Font Compare", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_font_compare":
    main()
