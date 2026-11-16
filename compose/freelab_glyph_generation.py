# -*- coding: utf-8 -*-
"""FreeLab Glyph Compose's Glyph generation tab (loaded by freelab_glyph_compose.py; not a script of its own).

Lists the characters of its first scope the font lacks (spaces, hyphens and dashes, duplicates,
punctuation, Greek and Cyrillic look-alikes, ligature letters, vulgar fractions, arrows and triangles:
205 characters; then the turned and reversed letters, 41 starting points) that it can make of the
glyphs the font has, and builds the checked ones in every master, as one step of FontLab's History. A
turned or reversed letter is said "likely usable as it is" where the font's design measures monoline
(likely_usable, its thresholds from the corpus). What Font Check hands over (the window's
generation_given) is listed alone at first.

The recipes are FreeLab's own (glyph_generation.json, made by compose/train/generation.py): each
character's ways, the first the font can take used, each as sure as its confidence says:
- exact: no design in it (a space of a set width, a second code point of the same character);
- accepted: how fonts commonly build it (most of the corpus's families that have it build it so);
- starting point: a draft to draw over, never a finished glyph (none in the first scope; the row
  says so where one is used).
What the ways do, the operations below: width (an empty glyph of a set advance: a share of the em, a
setting, or another glyph's advance), shared (the code point added to the source's own glyph, no new
glyph), copy (one component), move (one component raised), turn (by any angle, about the ink's
center), mirror (left to right, the contours set right), row (side by side, at the corpus's gaps),
stretch (a dash drawn longer: the nodes right of the source's middle moved, so it keeps its thickness
and its ends), minus (the hyphen stretched on the plus: the plus's width and height, the hyphen's
thickness), and fraction (Feature Code's numerators and denominators about the fraction slash).

A recipe may use a glyph this list builds (two right single quotes make the right double quote):
the list builds that one first, and the row says so. Nothing is replaced unless the row says so:
existing glyphs are listed only with Also list existing glyphs, unchecked.

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys

DATA_FILE = "glyph_generation.json"
CONFIDENCES = ("exact", "accepted", "starting point")
DRAFT_NOTE = u"starting point: a draft to draw over"  # in the row of a recipe that is one
LIKELY = u"likely usable as it is"  # a starting point the font's monoline design makes so (likely_usable)
SETTING_KEYS = ("thin", "hair", "en_dash", "em_dash")
SETTINGS_KEY = "generation"  # its settings in Glyph Compose's settings file
SETTING_REACH = {"thin": (2, 48), "hair": (2, 48), "en_dash": (0.2, 2.5), "em_dash": (0.2, 2.5)}  # (the boxes' too)
CJK_RANGES = ((0x3040, 0x30FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF))
TABULAR = ("tf", "tosf", "tnum")  # a figure's tabular forms, in the order taken (its own glyph last)
NUMR, DNOM = ("numr", "numerator"), ("dnom", "denominator")  # (Feature Code's own, where it is read)
FRACTION_SLASH = "2044"
LACKING = u"Need a glyph the font lacks"
EXISTING = u"Existing glyphs (check to rebuild)"
JUST_BUILT = u"Just built (check to rebuild)"
FIGURE_FORMS_FIRST = u"build the numerators and denominators first (Feature Code, Forms tab)"
NO_LAYER = u"%s has no layer in this master"  # (a variable font's sparse master: the glyph gets none there either)


def main():
    """Not a script: Glyph Compose loads this module for its tab. (load_sibling keeps a module that has a
    main: one loaded again for each window would leave the earlier window's tab with a module Python 2
    has emptied.)"""
    return None


def unichr_(code):
    """The character of a code point, U+FFFD past U+FFFF in a narrow Python (FontLab's)."""
    try:
        return unichr(code)  # noqa: F821  (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"�"


def char_of(code_hex):
    return unichr_(int(code_hex, 16))


def counted(number, one, many=None):
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

_DATA = {}


def load_data(path=None):
    """The recipe table (glyph_generation.json beside this file), read once; {} when it cannot be."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), DATA_FILE)
    if path not in _DATA:
        try:
            with io.open(path, encoding="utf-8") as handle:
                _DATA[path] = json.load(handle)
        except (IOError, OSError, ValueError):
            _DATA[path] = {}
    return _DATA[path]


def settings_of(data, saved=None):
    """The settings: the table's suggestions, with those saved by the user over them (a value that
    is no number, or out of reach, is left out)."""
    found = dict((data or {}).get("settings") or {"thin": 6, "hair": 11, "en_dash": 0.528, "em_dash": 0.862})
    reach = SETTING_REACH
    for key, value in (saved or {}).items():
        low, high = reach.get(key, (None, None))
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if low is not None and low <= value <= high:
            found[key] = int(round(value)) if key in ("thin", "hair") else value
    return found


# ---------------------------------------------------------------------------
# Geometry: transforms as (m11, m12, m21, m22, dx, dy), QTransform's order (x' = m11 x + m21 y + dx)
# ---------------------------------------------------------------------------

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def compose(outer, inner):
    """outer after inner."""
    a11, a12, a21, a22, adx, ady = outer
    b11, b12, b21, b22, bdx, bdy = inner
    return (b11 * a11 + b12 * a21, b11 * a12 + b12 * a22, b21 * a11 + b22 * a21, b21 * a12 + b22 * a22,
            bdx * a11 + bdy * a21 + adx, bdx * a12 + bdy * a22 + ady)


def translation(dx, dy):
    return (1.0, 0.0, 0.0, 1.0, float(dx), float(dy))


def rotation(angle, cx, cy):
    """A turn by angle degrees, counterclockwise (y up), about (cx, cy); exact for the quarter turns."""
    turns = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
    c, s = turns.get(int(angle) % 360, (math.cos(math.radians(angle)), math.sin(math.radians(angle))))
    c, s = float(c), float(s)
    # x' = c x - s y, y' = s x + c y, about the center
    return (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)


def mirror_x(advance):
    """Left to right within an advance."""
    return (-1.0, 0.0, 0.0, 1.0, float(advance), 0.0)


def mapped(matrix, x, y):
    m11, m12, m21, m22, dx, dy = matrix
    return m11 * x + m21 * y + dx, m12 * x + m22 * y + dy


def linear(matrix):
    return tuple(round(v, 9) for v in matrix[:4])


def is_mirror(matrix):
    return matrix[0] * matrix[3] - matrix[1] * matrix[2] < 0


def box_through(box, matrix):
    """The box of a box's corners mapped (a turned box: larger than the turned ink's own box)."""
    points = [mapped(matrix, x, y) for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))]
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def union(boxes):
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def stretched_points(points, split, amount):
    """[(x, y)] with every point right of split moved by amount: a dash drawn longer keeps its ends and
    its thickness (a plain horizontal scale widens a round end and thins nothing, but distorts it)."""
    return [(x + amount if x > split else x, y) for x, y in points]


# ---------------------------------------------------------------------------
# Monoline: whether a design's turned and mirrored letters may be used as they are
# ---------------------------------------------------------------------------
# A mirror of R is a fair Я only where mirroring changes nothing a reader sees: no stroke contrast (N's
# thick diagonal would come out on И's thin side), no tilted stress (an O whose thick parts lean left
# leans right once mirrored), and serifs alike on both sides. A half turn keeps contrast and stress as they
# are, so only uneven serifs count against it. Measured on O (else o) and I (else l): the same functions
# calibrate the thresholds on the corpus (compose/train/generation.py).

MONOLINE_GLYPHS = ((0x004F, 0x006F), (0x0049, 0x006C))  # (the round letter, the straight one): first the font has


def crossings(polygons, axis, at):
    """Where a line meets the outline, sorted: x's of the horizontal line y = at (axis "y"), or y's of the
    vertical line x = at (axis "x")."""
    found = []
    for polygon in polygons:
        count = len(polygon)
        for index in range(count):
            (x0, y0), (x1, y1) = polygon[index], polygon[(index + 1) % count]
            if axis == "x":
                x0, y0, x1, y1 = y0, x0, y1, x1
            if (y0 <= at < y1) or (y1 <= at < y0):
                found.append(x0 + (at - y0) * (x1 - x0) / (y1 - y0))
    return sorted(found)


def strokes(polygons, axis, at):
    """[(start, end)] of the ink along a line (crossings in pairs: a stroke between each)."""
    cuts = crossings(polygons, axis, at)
    return [(cuts[index], cuts[index + 1]) for index in range(0, len(cuts) - 1, 2)]


def box_of(polygons):
    xs = [x for polygon in polygons for x, _ in polygon]
    ys = [y for polygon in polygons for _, y in polygon]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def round_measures(polygons):
    """(contrast, stress) of a round letter: its thicker strokes over its thinner ones, its sides' thickness at
    mid-height against its top's and bottom's at mid-width (1 for a monoline O, 4 for sides four times its top's
    thickness or for a top four times its sides': reverse contrast is no monoline either), and how much its
    left and right sides differ a quarter up and down (0 for an upright stress), as a share of their mean;
    None where it cannot be read."""
    box = box_of(polygons)
    if box is None:
        return None
    cx, cy, h = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0, box[3] - box[1]
    across = strokes(polygons, "y", cy)
    up_down = strokes(polygons, "x", cx)
    if len(across) < 2 or len(up_down) < 2:
        return None
    sides = [across[0][1] - across[0][0], across[-1][1] - across[-1][0]]
    caps = [up_down[0][1] - up_down[0][0], up_down[-1][1] - up_down[-1][0]]
    if min(caps) <= 0 or max(sides) <= 0:
        return None
    widths = []
    for at in (cy + h / 4.0, cy - h / 4.0):
        pieces = strokes(polygons, "y", at)
        if len(pieces) < 2:
            return None
        widths.append((pieces[0][1] - pieces[0][0], pieces[-1][1] - pieces[-1][0]))
    mean = sum(a + b for a, b in widths) / 4.0
    stress = sum(abs(a - b) for a, b in widths) / (2.0 * mean) if mean > 0 else 0.0
    ratio = max(sides) / min(caps)
    return max(ratio, 1.0 / ratio), stress


def serif_measure(polygons):
    """How unevenly a straight letter's foot and head reach out on either side of its stem (0 for none, or
    serifs alike both sides), as a share of the stem's width; None where it cannot be read."""
    box = box_of(polygons)
    if box is None:
        return None
    h = box[3] - box[1]
    stem = strokes(polygons, "y", box[1] + h / 2.0)
    if len(stem) != 1 or stem[0][1] <= stem[0][0]:
        return None
    s0, s1 = stem[0]
    worst = 0.0
    for at in (box[1] + h * 0.02, box[3] - h * 0.02):
        pieces = strokes(polygons, "y", at)
        if not pieces:
            continue
        left, right = s0 - pieces[0][0], pieces[-1][1] - s1
        worst = max(worst, abs(left - right) / (s1 - s0))
    return worst


def monoline_measures(polygons_of, glyph_of):
    """{"contrast", "stress", "serif"} of a font in one master (polygons_of(name): its outline as
    polygons; glyph_of(code): its glyph), or None where it has no round letter to read."""
    found = {}
    for round_codes in MONOLINE_GLYPHS[:1]:
        for code in round_codes:
            name = glyph_of(code)
            measured = round_measures(polygons_of(name)) if name else None
            if measured:
                found["contrast"], found["stress"] = measured
                break
    if "contrast" not in found:
        return None
    found["serif"] = 0.0
    for code in MONOLINE_GLYPHS[1]:
        name = glyph_of(code)
        measured = serif_measure(polygons_of(name)) if name else None
        if measured is not None:
            found["serif"] = measured
            break
    return found


def likely_usable(measures, rule, kind):
    """Whether a turned (kind "turn") or mirrored ("mirror") letter of a design so measured may be used
    as it is: every measure under the corpus's threshold (rule) that counts for it."""
    if not measures or not rule:
        return False
    keys = ("contrast", "serif") if kind == "turn" else ("contrast", "stress", "serif")
    return all(measures.get(key) is not None and measures[key] <= rule[key] for key in keys)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

class Part(object):
    """A glyph placed in another: name, its transform, and for a stretched dash (split, amount): its
    nodes right of split (in its own units) moved by amount before the transform."""

    def __init__(self, name, matrix=IDENTITY, stretch=None):
        self.name, self.matrix, self.stretch = name, tuple(float(v) for v in matrix), stretch

    def moved(self, matrix):
        return Part(self.name, compose(matrix, self.matrix), self.stretch)

    def __repr__(self):
        return "Part(%r, %r, %r)" % (self.name, self.matrix, self.stretch)


class Layout(object):
    """What a glyph is made of in a master: its parts, its advance, and how it is written: "empty" (no
    shapes), "shared" (no glyph: the code point goes to shared), "components", or "mirrored" (one
    source's outlines mirrored into the glyph, its contours set right)."""

    def __init__(self, parts, advance, kind="components", shared=None, axis="x"):
        self.parts, self.advance, self.kind, self.shared = list(parts), float(advance), kind, shared
        self.axis = axis  # (a mirror's: "x" left to right, "y" upside down)


class Need(Exception):
    """A way the font cannot take: what it lacks, in words."""


class Row(object):
    """A character of the list: its glyph's name, the way taken, how sure it is, what it needs."""

    def __init__(self, entry, name):
        self.code = int(entry["code"], 16)
        self.hex = entry["code"]
        self.char = unichr_(self.code)
        self.entry, self.name, self.group = entry, name, entry["group"]
        self.way, self.way_index, self.layout, self.missing = None, None, None, None
        self.existing = False  # the font has the character already (listed to rebuild)
        self.needs = []  # the glyphs of this list it is built of: built first
        self.checked = False
        self.notes = []

    @property
    def confidence(self):
        return (self.way or {}).get("confidence") or self.entry.get("research_confidence") or u"accepted"

    @property
    def likely(self):
        """A starting point the font's design makes likely usable as it is (a monoline font's mirrored or
        turned letter: likely_usable)."""
        return getattr(self, "monoline", False) and self.confidence == "starting point"

    @property
    def sureness(self):
        """What the Confidence cell says: the recipe's confidence, or LIKELY for a likely usable draft."""
        return LIKELY if self.likely else self.confidence


def describe_code(code_hex, known=None):
    """A character for a note: a letter or a sign as itself, "‹ (U+2039)"; punctuation, a space, or a mark
    by its Unicode name, "the middle dot (U+00B7)" (a dot or a dash between words reads as a separator).
    known: the recipe table's "characters" ({hex: {"category", "name"}}, Unicode's as of the table's making):
    FontLab's Python 2.7 has Unicode 5.2, where a later character (⸲ U+2E32, Ʞ U+A7B0) is unassigned."""
    import unicodedata
    ch = char_of(code_hex)
    given = (known or {}).get(code_hex)
    if given:
        category, name = given.get("category") or u"Cn", given.get("name") or u""
    else:
        try:
            category = unicodedata.category(ch)
        except (TypeError, ValueError):
            category = u"Cn"
        try:
            name = unicodedata.name(ch)
        except (ValueError, TypeError):
            name = u""
    if category[0] in u"PZCM":
        return u"the %s (U+%s)" % (name.lower(), code_hex) if name else u"U+%s" % code_hex
    return u"%s (U+%s)" % (ch, code_hex)


def component_names(layout):
    """The glyphs a layout's parts point to, as far as a loop of components goes: every part but a stretched
    one (outlines). A mirrored part counts too: it becomes a corrected glyph of outlines only where its glyph
    is drawn; where its glyph is made of a mirrored component, the two mirrors cancel once flattened
    (flat_parts) and the part points to that component's glyph as it is (Codex's review: R made as a mirrored
    component of Я, Я rebuilt as the mirrored R became a component of itself). A second code point and an
    empty glyph point to nothing."""
    if layout is None or layout.kind != "components":
        return []
    return [part.name for part in layout.parts if part.stretch is None]


def component_loop(name, parts, components_of):
    """The part through which a glyph made of these parts would be made of itself ([part, ..., name]: the
    chain of components), else None. components_of(glyph): the glyphs its components point to."""
    for part in parts:
        trail, seen = [(part, [part])], set()
        while trail:
            glyph, path = trail.pop()
            if glyph == name:
                return path
            if glyph in seen:
                continue
            seen.add(glyph)
            for inner in components_of(glyph) or ():
                trail.append((inner, path + [inner]))
    return None


def loop_words(name, path):
    """A loop of components, for a note: "made of Dcroat, which is made of Eth"."""
    if len(path) == 1:
        return u"made of its own glyph"
    return u"made of %s, which %s made of %s" % (path[0], u"is" if len(path) == 2 else u"is in the end", name)


class Font(object):
    """What planning reads of a font in one master (FontLab's is FontLabFont, the tests' a fake):
    glyph_of(code), box(name, matrix) of a glyph's ink through a transform (y up, font units), advance(name),
    composite(name) (made of components only), names, upm, x_height, cap_height; figure (a tabular
    figure's glyph), numr(digit) and dnom(digit) (Feature Code's forms)."""

    def __init__(self, upm=1000, x_height=None, cap_height=None):
        self.upm = float(upm)
        self.x_height, self.cap_height = x_height, cap_height

    def has_layer(self, name):
        """Whether the glyph has a layer in this master (a variable font's sparse masters lack some)."""
        return True

    def polygons(self, name):
        """A glyph's outline as polygons, curves flattened ([] where it cannot be read)."""
        return []

    def components(self, name):
        """The glyphs a glyph's components point to in this master ([] for one of outlines only)."""
        return []

    def codes_of(self, name):
        """Every code point the font gives that glyph."""
        return [code for code in self.codes() if self.glyph_of(code) == name]

    def has_cjk(self):
        return any(low <= code <= high for code in self.codes() for low, high in CJK_RANGES)


class Planner(object):
    """The rows of the list for a font, and each row's layout in one of its masters. codes: the characters to
    list (Font Check's hand-over), else every one; planned against the whole table all the same, so that a
    character built of another the font lacks (‟ of two ‛) is built as the table builds it (prerequisites)."""

    def __init__(self, data, font, settings=None, include_existing=False, codes=None):
        self.data, self.font = data, font
        self.settings = settings_of(data, settings)
        self.rules = data.get("rules") or {}
        self.include_existing = include_existing
        entries = data.get("entries") or []
        self.entries = dict((e["code"], e) for e in entries)
        self.order = [e["code"] for e in entries]
        self.listed = set(codes) if codes is not None else None
        self.rows, self.by_hex, self.by_name = [], {}, {}

    def describe(self, code_hex):
        return describe_code(code_hex, self.data.get("characters"))

    # -- the list ------------------------------------------------------------------------------------------

    def plan(self, ways=None):
        """Every row: a way the font can take (the first), else what it needs. ways: {hex: way index}
        to keep (a master's plan follows the current master's choice)."""
        font = self.font
        names = font.names
        taken = set(names)
        self.ways = dict(ways or {})
        self.rows, self.by_hex, self.by_name = [], {}, {}
        for hex_ in self.order:
            entry = self.entries[hex_]
            code = int(hex_, 16)
            own = font.glyph_of(code)
            if any(way.get("only") == "cjk" for way in entry["ways"]) and not font.has_cjk():
                continue
            if own is not None and not self.include_existing:
                continue
            if own is not None and len(font.codes_of(own)) > 1:
                continue  # (its glyph stands for other characters too: rebuilt, they would change with it)
            name = own or self.free_name(entry, taken)
            taken.add(name)
            row = Row(entry, name)
            row.existing = own is not None
            self.rows.append(row)
            self.by_hex[hex_] = row
            self.by_name[name] = row
        for row in self.rows:
            self.choose(row, self.ways.get(row.hex))
        for row in self.rows:
            check = (row.way or {}).get("check")
            if check and row.confidence == "starting point":
                row.monoline = likely_usable(self.monoline(), (self.rules.get("monoline") or {}).get(check), check)
        if self.listed is not None:  # (the others stay in by_hex and by_name: prerequisites)
            drafts = self.draft_needs([row for row in self.rows if row.hex in self.listed])
            self.rows = [row for row in self.rows if row.hex in self.listed or id(row) in drafts]
        return self.rows

    def draft_needs(self, rows):
        """{id(row)} of the starting points these rows are built of, through others too: listed with them
        (unchecked, as every starting point is), so that a draft is built only once the owner checks it, as
        in the whole table (Codex's review: ǝ handed over alone built a turned e, a draft, unasked)."""
        found, seen = set(), set()

        def visit(row):
            for name in row.needs:
                need = self.by_name.get(name)
                if need is None or name in seen:
                    continue
                seen.add(name)
                if need.layout is not None and need.confidence == "starting point":
                    found.add(id(need))
                visit(need)
        for row in rows:
            visit(row)
        return found

    def prerequisites(self, chosen):
        """The rows the chosen ones are built of that the list does not show (Font Check's hand-over lists
        only the characters handed over): built with them, before them; exact or accepted recipes only (a
        starting point is listed: draft_needs). A listed one is the owner's to check, as before (unchecked,
        the row that needs it is not built, and the log says so)."""
        picked = set(row.name for row in chosen)
        listed = set(id(row) for row in self.rows)
        found = []

        def visit(row):
            for name in row.needs:
                need = self.by_name.get(name)
                if need is None or need.name in picked or need.layout is None or id(need) in listed:
                    continue
                picked.add(need.name)
                visit(need)
                found.append(need)
        for row in chosen:
            visit(row)
        return found

    def monoline(self):
        """The font's monoline measures in this master (monoline_measures), read once; None where it has
        no round letter or gives no outlines."""
        if not hasattr(self, "measured"):
            try:
                self.measured = monoline_measures(self.font.polygons, self.font.glyph_of)
            except Exception:
                self.measured = None
        return self.measured

    def free_name(self, entry, taken):
        """Glyphs' name for the character, else uniXXXX, else uniXXXX.1 and on: one no glyph has."""
        for name in (entry.get("glyph_name"), u"uni" + entry["code"]):
            if name and name not in taken:
                return name
        number = 1
        while u"uni%s.%d" % (entry["code"], number) in taken:
            number += 1
        return u"uni%s.%d" % (entry["code"], number)

    def choose(self, row, only=None, stack=()):
        if row.layout is not None or row.missing is not None:
            return row
        first_need = None
        ways = list(enumerate(row.entry["ways"]))
        if only is not None:
            ways = [(index, way) for index, way in ways if index == only]
        for index, way in ways:
            needs = []
            try:
                layout = self.lay(way, row, stack + (row.hex,), needs)
            except Need as need:
                if first_need is None:
                    first_need = u"%s" % need
                continue
            path = None
            if row.existing:  # (any part of its own glyph, then any loop through the font's components)
                try:
                    path = [row.name] if any(part.name == row.name for part in layout.parts) else \
                        component_loop(row.name, component_names(layout), self.font.components)
                except GraphUnreadable as exc:
                    first_need = first_need or u"%s" % exc
                    continue
            if path is not None:  # (a glyph is never made a component of itself, through others neither)
                first_need = first_need or loop_words(row.name, path)
                continue
            row.way, row.way_index, row.layout, row.needs = way, index, layout, needs
            return row
        row.missing = first_need or u"no way the font can take"
        return row

    # -- sources ---------------------------------------------------------------------------------------------

    def source(self, hex_, stack, needs, outlines=False):
        """(glyph name, its layout or None) of a character: the font's glyph, else one this list builds
        first (never when outlines are wanted: a mirror or a stretch reads the source's own outlines)."""
        name = self.font.glyph_of(int(hex_, 16))
        if name is not None:
            return self.drawn(name), None
        row = self.by_hex.get(hex_)
        if row is not None and not outlines and hex_ not in stack and not row.existing:
            self.choose(row, getattr(self, "ways", {}).get(hex_), stack=stack)
            if row.layout is not None and row.layout.kind in ("components", "mirrored"):
                if row.name not in needs:
                    needs.append(row.name)
                return row.name, row.layout
        raise Need(u"needs %s" % self.describe(hex_))

    def drawn(self, name):
        """A source glyph of the font, once it is known to have a layer in this master: a variable font's
        sparse master (Rubik's Bold) has none for many glyphs, and a glyph made of them gets none either."""
        if not self.font.has_layer(name):
            raise Need(NO_LAYER % name)
        return name

    def box(self, name, matrix=IDENTITY):
        """A glyph's ink through a transform: the font's own, or a planned glyph's parts'."""
        row = self.by_name.get(name)
        if row is not None and row.layout is not None and not row.existing and self.font.glyph_of(row.code) is None:
            return union([self.part_box(part.moved(matrix)) for part in row.layout.parts])
        return self.font.box(name, matrix)

    def part_box(self, part):
        if part.stretch is None:
            return self.box(part.name, part.matrix)
        own = self.box(part.name)
        if own is None:
            return None
        split, amount = part.stretch
        grown = (own[0] if own[0] <= split else own[0] + amount, own[1], own[2] + amount if own[2] > split else own[2], own[3])
        return box_through(grown, part.matrix)

    def advance(self, name):
        row = self.by_name.get(name)
        if row is not None and row.layout is not None and self.font.glyph_of(row.code) is None:
            return row.layout.advance
        return self.font.advance(name)

    def em(self, share):
        return share * self.font.upm

    # -- the operations ------------------------------------------------------------------------------------

    def lay(self, way, row, stack, needs):
        op = way["op"]
        return getattr(self, "op_" + op)(way, row, stack, needs)

    def op_width(self, way, row, stack, needs):
        if "em" in way:
            advance = self.em(way["em"])
        elif "setting" in way:
            advance = self.font.upm / float(self.settings[way["setting"]])
        elif way.get("advance_of") == "figure":
            figure = self.font.figure
            if figure is None:
                raise Need(u"needs the figures (0 to 9)")
            advance = self.font.advance(self.drawn(figure))
        else:
            name, _ = self.source(way["advance_of"], stack, needs)
            advance = self.advance(name)
        return Layout([], round(advance), kind="empty")

    def op_shared(self, way, row, stack, needs):
        name = self.font.glyph_of(int(way["of"], 16))
        if name is None:
            raise Need(u"needs %s" % self.describe(way["of"]))
        if row.existing:  # (its own glyph rebuilt as a copy: the code point cannot move to another glyph here)
            return Layout([Part(name)], self.advance(name))
        return Layout([Part(name)], self.advance(name), kind="shared", shared=name)

    def op_copy(self, way, row, stack, needs):
        name, _ = self.source(way["of"], stack, needs)
        return Layout([Part(name)], self.advance(name))

    def op_move(self, way, row, stack, needs):
        name, _ = self.source(way["of"], stack, needs)
        box = self.box(name)
        if box is None:
            raise Need(u"%s has no outline" % name)
        x_height = self.font.x_height
        if not x_height:
            raise Need(u"needs an x to measure the x-height")
        center = self.rules.get("middle_dot", 0.5) * x_height
        return Layout([Part(name, translation(0, round(center - (box[1] + box[3]) / 2.0)))], self.advance(name))

    def op_turn(self, way, row, stack, needs):
        name, _ = self.source(way["of"], stack, needs)
        box, advance = self.box(name), self.advance(name)
        if box is None:
            raise Need(u"%s has no outline" % name)
        angle = int(way["angle"]) % 360
        rule = (self.rules.get("turns") or {}).get(way.get("pair"), {})
        cy = (box[1] + box[3]) / 2.0
        if way.get("about") == "body":  # (a letter: about the middle of its x-height or cap height)
            cy = self.body_middle(way, cy)
        if angle == 180:
            # about the middle of the advance: the sidebearings change sides (as the corpus's turned quotes)
            matrix = rotation(180, advance / 2.0, cy)
            if "top_over_x_height" in rule and self.font.x_height:
                matrix = compose(translation(0, round(self.font.x_height + self.em(rule["top_over_x_height"]) - box[3])), matrix)
            elif rule.get("drop"):
                matrix = compose(translation(0, round(self.em(rule["drop"]))), matrix)
            return Layout([Part(name, matrix)], advance)
        cx = (box[0] + box[2]) / 2.0
        matrix = rotation(angle, cx, cy)
        turned = self.box(name, matrix)
        sides = max(0.0, (advance - (box[2] - box[0])) * rule.get("sides", 1.0) / 2.0)
        matrix = compose(translation(round(sides - turned[0]), 0), matrix)
        return Layout([Part(name, matrix)], round(turned[2] - turned[0] + 2 * sides))

    def body_middle(self, way, fallback):
        """The middle of a letter's body: half the cap height for a capital ("body": "cap", the table's), half
        the x-height else (a small capital's too), so that a turned letter's descender comes up as an ascender.
        The table says which, as Unicode's data had it when it was made: FontLab's Python 2.7 has Unicode 5.2,
        where Ʞ (U+A7B0) and Ʇ (U+A7B1) are unassigned, not capitals (they turned about the x-height)."""
        height = {"cap": self.font.cap_height, "x": self.font.x_height}.get(way.get("body"))
        return height / 2.0 if height else fallback

    def op_mirror(self, way, row, stack, needs):
        name = self.font.glyph_of(int(way["of"], 16))
        if name is None:
            raise Need(u"needs %s" % self.describe(way["of"]))
        advance = self.font.advance(self.drawn(name))
        kind = "components" if self.font.composite(name) or row.existing else "mirrored"
        if way.get("axis") == "y":  # upside down, about the middle of its ink (as a corrected glyph is made)
            box = self.box(name)
            if box is None:
                raise Need(u"%s has no outline" % name)
            matrix = (1.0, 0.0, 0.0, -1.0, 0.0, box[1] + box[3])
            return Layout([Part(name, matrix)], advance, kind=kind, axis="y")
        return Layout([Part(name, mirror_x(advance))], advance, kind=kind)

    def op_row(self, way, row, stack, needs):
        sources = [self.source(hex_, stack, needs) for hex_ in way["of"]]
        pair = way.get("pair")
        if pair in (self.rules.get("dots") or {}):
            return self.dotted(sources, self.rules["dots"][pair], pair)
        gap = (self.rules.get("rows") or {}).get(pair if pair in (self.rules.get("rows") or {}) else "letters")
        parts, x, last = [], 0.0, None
        for index, (name, _) in enumerate(sources):
            if index and gap is not None:
                box, previous = self.box(name), self.part_box(parts[-1])
                if box is None or previous is None:
                    raise Need(u"%s has no outline" % name)
                x = round(previous[2] + self.em(gap) - box[0])
            parts.append(Part(name, translation(x, 0)))
            last = name
            x += self.advance(name)
        if gap is None:
            return Layout(parts, x)
        box = self.box(last)
        right_side = self.advance(last) - box[2]
        return Layout(parts, round(self.part_box(parts[-1])[2] + right_side))

    def dotted(self, sources, rule, pair):
        """Catalan's L with a middle dot: the dot at the corpus's place after the letter."""
        (letter, _), (dot, _) = sources
        height = self.font.cap_height if pair == "013F" else self.font.x_height
        dot_box = self.box(dot)
        if not height or dot_box is None:
            raise Need(u"needs %s to measure the dot's height" % (u"an H" if pair == "013F" else u"an x"))
        dx = self.advance(letter) + self.em(rule["dot_left"]) - dot_box[0]
        dy = rule["dot_center"] * height - (dot_box[1] + dot_box[3]) / 2.0
        dot_part = Part(dot, translation(round(dx), round(dy)))
        right_side = self.advance(dot) - dot_box[2] + self.em(rule["right_side"])
        return Layout([Part(letter), dot_part], round(dot_box[2] + round(dx) + max(0.0, right_side)))

    def op_stretch(self, way, row, stack, needs):
        name = self.font.glyph_of(int(way["of"], 16))
        if name is None:
            raise Need(u"needs %s" % self.describe(way["of"]))
        box, advance = self.box(self.drawn(name)), self.font.advance(name)
        if box is None:
            raise Need(u"%s has no outline" % name)
        width = self.dash_width(way, name)
        lsb, rsb = box[0], advance - box[2]
        ink = width - lsb - rsb
        if ink <= 0:
            raise Need(u"%s is wider than %s" % (name, counted(int(round(width)), u"unit")))
        amount = ink - (box[2] - box[0])
        return Layout([Part(name, IDENTITY, ((box[0] + box[2]) / 2.0, round(amount)))], round(width))

    def dash_width(self, way, name):
        kind, times = way["width"], way.get("times", 1)
        if kind == "figure":
            if self.font.figure is None:
                raise Need(u"needs the figures (0 to 9)")
            return self.font.advance(self.font.figure)
        if kind == "em_dash" and times > 1:
            own = self.font.glyph_of(0x2014)
            base = self.font.advance(own) if own is not None else self.em(self.settings["em_dash"])
            return base * times
        return self.em(self.settings[kind]) * times

    def op_minus(self, way, row, stack, needs):
        hyphen, plus = self.font.glyph_of(int(way["of"], 16)), self.font.glyph_of(int(way["on"], 16))
        if hyphen is None or plus is None:
            raise Need(u"needs %s" % self.describe(way["of"] if hyphen is None else way["on"]))
        h, p = self.box(self.drawn(hyphen)), self.box(self.drawn(plus))
        if h is None or p is None:
            raise Need(u"%s has no outline" % (hyphen if h is None else plus))
        amount = round((p[2] - p[0]) - (h[2] - h[0]))
        dx, dy = round(p[0] - h[0]), round((p[1] + p[3]) / 2.0 - (h[1] + h[3]) / 2.0)
        return Layout([Part(hyphen, translation(dx, dy), ((h[0] + h[2]) / 2.0, amount))], self.font.advance(plus))

    def op_fraction(self, way, row, stack, needs):
        slash = self.font.glyph_of(int(FRACTION_SLASH, 16))
        tops = [self.font.numr(digit) for digit in way["numerator"]]
        bottoms = [self.font.dnom(digit) for digit in way["denominator"]]
        lacking = [u"%s's numerator" % d for d, n in zip(way["numerator"], tops) if n is None] + \
                  [u"%s's denominator" % d for d, n in zip(way["denominator"], bottoms) if n is None]
        if lacking:
            raise Need(u"needs %s: %s" % (u", ".join(lacking), FIGURE_FORMS_FIRST))
        if slash is None:
            raise Need(u"needs the fraction slash (U+2044)")
        parts, x = [], 0.0
        for name in tops + [slash] + bottoms:
            parts.append(Part(self.drawn(name), translation(x, 0)))
            x += self.font.advance(name)
        return Layout(parts, x)


def build_order(rows):
    """The rows in an order that builds each glyph after the glyphs of this list it is made of."""
    by_name = dict((row.name, row) for row in rows)
    done, order = set(), []

    def visit(row, seen):
        if row.name in done or row.name in seen:
            return
        for name in row.needs:
            if name in by_name:
                visit(by_name[name], seen | set([row.name]))
        done.add(row.name)
        order.append(row)
    for row in rows:
        visit(row, set())
    return order


def unbuilt_needs(row, chosen, font_has):
    """The glyphs of this list a row is made of that will not be there: not in the font, not built."""
    names = set(r.name for r in chosen)
    return [name for name in row.needs if name not in names and not font_has(name)]


# -- the words of a row ---------------------------------------------------------------------------------------

def angle_words(angle):
    angle = int(angle) % 360
    return {180: u"turned", 90: u"turned a quarter turn left", 270: u"turned a quarter turn right"}.get(
        angle, u"turned %d°" % angle)


def width_words(way, layout, settings):
    if way.get("em") == 0:
        return u"empty, no width"
    if "setting" in way:
        return u"empty, 1/%d em (%s)" % (settings[way["setting"]], {"thin": u"Thin space", "hair": u"Hair space"}.get(
            way["setting"], way["setting"]))
    if "em" in way:
        share = way["em"]
        known = {0.5: u"1/2", 1.0: u"1", 0.25: u"1/4", 1.0 / 3: u"1/3", 1.0 / 6: u"1/6", 4.0 / 18: u"4/18"}
        for value, text in known.items():
            if abs(value - share) < 1e-6:
                return u"empty, %s em" % text
        return u"empty, %s em" % share
    return u"empty, %s" % (way.get("note") or u"%d units" % layout.advance)


def recipe_text(row, settings, rules=None):
    """The Recipe cell: what the glyph is made of, in a few words (no period: a cell)."""
    way, layout = row.way, row.layout
    if layout is None:
        return u""
    op = way["op"]
    names = [part.name for part in layout.parts]
    if op == "width":
        return width_words(way, layout, settings)
    if op == "shared" and layout.kind == "shared":
        return u"a second code point on %s" % layout.shared
    if op in ("copy", "shared"):
        return u"%s (component)" % names[0]
    if op == "move":
        return u"%s centered at %d%% of the x-height" % (names[0], round(100 * (rules or {}).get("middle_dot", 0.5)))
    if op == "turn":
        return u"%s %s" % (names[0], angle_words(way["angle"]))
    if op == "mirror":
        return u"%s mirrored" % names[0]
    if op in ("row", "fraction"):
        return u" + ".join(names)
    if op == "stretch":
        return u"%s drawn %s wide" % (names[0], counted(int(layout.advance), u"unit"))
    if op == "minus":
        return u"%s on the plus" % names[0]
    return op


def note_text(row, needs_built=()):
    """The Note cell: what to know before building (no period: a cell)."""
    notes = []
    if row.missing:
        return row.missing
    if row.confidence == "starting point" and not row.likely:
        notes.append(DRAFT_NOTE)
    if row.existing:
        notes.append(u"replaces the font's own glyph" if not row.layout or row.layout.kind != "shared"
                     else u"the font has it")
    if row.layout is not None and row.layout.kind == "shared" and not row.existing:
        notes.append(u"no new glyph")
    if row.layout is not None and row.layout.kind == "mirrored":
        notes.append(u"outlines, contours set right")
    if row.needs:
        notes.append(u"made of %s, built here first" % u", ".join(row.needs))
    return u"; ".join(notes)


def corpus_text(families, deriving):
    """How many of the corpus's families have the character, and how many of those build it of other
    glyphs (a sentence)."""
    return u"%s of the corpus %s it; %d of them %s it of other glyphs." % (
        counted(families, u"family", u"families"), u"has" if families == 1 else u"have", deriving,
        u"builds" if deriving == 1 else u"build")


def monoline_text(measured, rule, likely):
    """Why a turned or mirrored letter is, or is not, likely usable as it is (a sentence)."""
    return (u"Stroke contrast %.2f (monoline under %.2f), stress %.2f, serifs %.2f: %s. Of the corpus's families "
            u"so measured, %d%% draw it as this recipe makes it." % (
                measured["contrast"], rule["contrast"], measured.get("stress", 0.0), measured.get("serif", 0.0),
                u"likely usable as it is" if likely else u"a starting point to draw over", round(100 * rule["right"])))


def confidence_text(row):
    return row.sureness if not row.missing else u""


# ---------------------------------------------------------------------------
# FontLab: the font read for planning, and the writes (PythonQt; not used by the planning tests)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


class FontLabFont(Font):
    """A FontLab font's glyphs in one master, read as planning needs them (each outline once)."""

    def __init__(self, ak, fc, package, master, codes):
        Font.__init__(self, package.upm)
        self.ak, self.package, self.master = ak, package, master
        self.code_map = codes  # {code: glyph name}
        self.names = [u"%s" % fg.name for fg in package.fgPackage.glyphs]
        self.paths, self.boxes = {}, {}
        x, h = self.glyph_of(0x78), self.glyph_of(0x48)
        self.x_height = self.box(x)[3] if x and self.box(x) else None
        self.cap_height = self.box(h)[3] if h and self.box(h) else None
        self.figure, self.forms = figure_forms(fc, self.names, codes)

    def codes(self):
        return list(self.code_map.keys())

    def glyph_of(self, code):
        return self.code_map.get(code)

    def layer(self, name):
        glyph = self.package.findName(name)
        if glyph is None or getattr(glyph, "isNull", False):
            return None
        return glyph.getLayerByName(self.master)

    def path(self, name):
        if name not in self.paths:
            layer = self.layer(name)
            self.paths[name] = (self.ak.layer_path(layer), float(layer.advanceWidth)) if layer is not None else (None, 0.0)
        return self.paths[name]

    def box(self, name, matrix=IDENTITY):
        if name is None:
            return None
        key = (name, linear(matrix) + (round(matrix[4], 6), round(matrix[5], 6)))
        if key not in self.boxes:
            QtCore, QtGui = _qt()
            path = self.path(name)[0]
            if path is None or path.isEmpty():
                self.boxes[key] = None
            else:
                if matrix != IDENTITY:
                    path = QtGui.QTransform(*matrix).map(path)
                rect = path.boundingRect()  # (y up: top() is the ink's lowest y)
                self.boxes[key] = (rect.left(), rect.top(), rect.right(), rect.bottom())
        return self.boxes[key]

    def advance(self, name):
        return self.path(name)[1]

    def has_layer(self, name):
        return self.layer(name) is not None

    def polygons(self, name):
        """The glyph's outline flattened into polygons (QPainterPath.toSubpathPolygons), [] where it cannot be."""
        path = self.path(name)[0] if name else None
        if path is None or path.isEmpty():
            return []
        found = []
        try:
            for polygon in path.toSubpathPolygons():
                points = polygon_points(polygon)
                if len(points) > 2:
                    found.append(points)
        except Exception:
            return []
        return found

    def composite(self, name):
        layer = self.layer(name)
        try:
            shapes = list(layer.shapes) if layer is not None else []
            return bool(shapes) and all(shape.isComponent for shape in shapes)
        except Exception:
            return False

    def components(self, name):
        return glyph_components(self.package, [self.master], name)

    def numr(self, digit):
        return self.forms.get(("numr", digit))

    def dnom(self, digit):
        return self.forms.get(("dnom", digit))


def polygon_points(polygon):
    """[(x, y)] of a QPolygonF, however PythonQt hands it over (a list of points, or a vector to index)."""
    try:
        return [(point.x(), point.y()) for point in polygon]
    except TypeError:
        count = polygon.count() if callable(getattr(polygon, "count", None)) else polygon.size()
        return [(polygon.at(index).x(), polygon.at(index).y()) for index in range(count)]


def figure_forms(fc, names, codes):
    """(a tabular figure's glyph: the zero's .tf, .tosf, or .tnum form, else the zero itself; {("numr" or
    "dnom", digit): glyph}) through Feature Code's own reading of figure forms (FontInfo.form)."""
    by_name = {}
    for code, name in codes.items():
        by_name.setdefault(name, []).append(code)
    info = fc.FontInfo(names, by_name)
    zero = info.glyph(0x30)
    figure = (info.form(zero, TABULAR) or zero) if zero else None
    forms = {}
    for digit in u"0123456789":
        glyph = info.glyph(ord(digit))
        if glyph:
            for key, suffixes in (("numr", getattr(fc, "NUMR_SUFFIXES", NUMR)), ("dnom", getattr(fc, "DNOM_SUFFIXES", DNOM))):
                form = info.form(glyph, suffixes)
                if form:
                    forms[(key, digit)] = form
    return figure, forms


class WriteError(Exception):
    """Why a glyph was not built (said in the log)."""


def flat_parts(package, master, parts, depth=4):
    """The parts with every glyph made of components only replaced by its components, where a part is
    turned, mirrored, or scaled (FontLab 7 refused a whole layer whose component was scaled and flipped and
    pointed to such a glyph: Glyph Compose's unwrapped), and where a part is mirrored, so that each mirror
    lands on a glyph of outlines (its corrected glyph is made of those)."""
    out = []
    for part in parts:
        if linear(part.matrix) == linear(IDENTITY) or part.stretch is not None or depth <= 0:
            out.append(part)
            continue
        glyph = package.findName(part.name)
        layer = glyph.getLayerByName(master) if glyph is not None else None
        shapes = list(layer.shapes) if layer is not None else []
        if shapes and all(shape.isComponent for shape in shapes):
            inner = []
            for shape in shapes:
                t = shape.transform
                values = (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy())
                inner.append(Part(u"%s" % shape.shapeData.componentGlyph, compose(part.matrix, values)))
            out.extend(flat_parts(package, master, inner, depth - 1))
        else:
            out.append(part)
    return out


def outline_contours(package, master, name, matrix=IDENTITY, depth=4):
    """[(contour, matrix)] of a glyph's outlines in a master, components followed (their contours are their
    glyph's, placed by their shape's transform)."""
    glyph = package.findName(name)
    layer = glyph.getLayerByName(master) if glyph is not None else None
    found = []
    for shape in (list(layer.shapes) if layer is not None else []):
        t = shape.transform
        here = compose(matrix, (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy()))
        contours = [c for c in shape.contours if c is not None]
        if contours:
            found.extend((contour, here) for contour in contours)
        elif shape.isComponent and depth > 0:
            found.extend(outline_contours(package, master, u"%s" % shape.shapeData.componentGlyph, here, depth - 1))
    return found


def stretched_shape(fontlab, fc, package, master, part):
    """A new shape of a part's outlines, its nodes right of the split moved by the amount, then placed by its
    transform: clones of the contours given their nodes' places (Feature Code's way, live 2026-11-14)."""
    split, amount = part.stretch
    contours = outline_contours(package, master, part.name)
    if not contours:
        raise WriteError(u"%s has no outline in master %s" % (part.name, master))
    clones = []
    for contour, matrix in contours:
        clone = contour.clone()
        nodes = clone.nodes()
        for node in nodes:
            x, y = mapped(matrix, float(node.x), float(node.y))  # (in the source glyph's own units)
            x = x + amount if x > split else x
            x, y = mapped(part.matrix, x, y)
            fc.place_node(node, x, y)
        clones.append(clone)
    shape = fontlab.flShape()
    shape.addContours(clones, True)
    return shape


def unused_helpers(package, masters, helpers, touched):
    """The corrected glyphs made in a build that no glyph built points to."""
    used = set()
    for glyph in touched:
        for master in masters:
            layer = glyph.getLayerByName(master) if hasattr(glyph, "getLayerByName") else None
            for shape in (list(layer.shapes) if layer is not None else []):
                if getattr(shape, "isComponent", False):
                    used.add(u"%s" % shape.shapeData.componentGlyph)
    return [name for name in helpers if name not in used]


class GraphUnreadable(Exception):
    """A glyph's components could not be read: no loop of components can be ruled out (Codex's review,
    round 3: read as none, a loop went through)."""

    def __init__(self, name, master=None):
        Exception.__init__(self, u"the components of %s could not be read%s" % (
            name, u" in master %s" % master if master is not None else u""))
        self.name, self.master = name, master


def glyph_components(package, masters, name):
    """The glyphs a glyph's components point to, in any of these masters (a set; empty for a glyph of
    outlines, or no such glyph). GraphUnreadable where they cannot be read: never taken for none."""
    found, at = set(), None
    try:
        glyph = package.findName(name)
        for master in masters:
            at = master
            layer = glyph.getLayerByName(master) if glyph is not None else None
            for shape in (list(layer.shapes) if layer is not None else []):
                if shape.isComponent:
                    found.add(u"%s" % shape.shapeData.componentGlyph)
    except Exception:
        raise GraphUnreadable(name, at)
    return found


def component_loops(order, layouts_of, components_of):
    """{row: the chain of components} for the rows whose glyph would end up made of itself (FontLab is
    handed a loop of components it can only recurse through), taken in build order: each row's new
    components replace its glyph's own once it is let through, so of Ð and Đ checked together (each a copy
    of the other) the first is built and the second refused. layouts_of(row): its layouts in every master;
    components_of(glyph): the font's own (glyph_components)."""
    planned, loops = {}, {}

    def edges(glyph):
        return planned[glyph] if glyph in planned else components_of(glyph)
    for row in order:
        layouts = [layout for layout in layouts_of(row) if layout is not None]
        if all(layout.kind == "shared" for layout in layouts):
            continue  # (a second code point: no glyph's shapes change)
        new = []
        for layout in layouts:
            new.extend(name for name in component_names(layout) if name not in new)
        try:
            path = component_loop(row.name, new, edges)
        except GraphUnreadable as exc:  # (no loop ruled out: refused as one)
            loops[row] = u"%s, so it cannot be told whether it would be made of itself" % exc
            continue
        if path is not None:
            loops[row] = u"it would be %s, a loop of components" % loop_words(row.name, path)
        else:
            planned[row.name] = set(new)
    return loops


def glyph_layers(cm, glyph, masters):
    """{master: (its shapes copied, its advance, what they read as now: shapes_read), or None where the glyph
    has no layer}: a glyph as it was, to put back whole (put_glyph_back) and to read back against (the
    reading is taken before anything is written: the copies themselves go back into the layer)."""
    saved = {}
    for master in masters:
        layer = glyph.getLayerByName(master)
        if layer is None:
            saved[master] = None
            continue
        shapes = list(layer.shapes)
        try:
            reading = shapes_read(shapes)
        except Exception:
            reading = None  # (nothing to read back against: a put-back is then never said to hold)
        saved[master] = ([cm.shape_copy(shape) for shape in shapes], float(layer.advanceWidth or 0), reading)
    return saved


def put_glyph_back(glyph, saved, masters):
    """The glyph put back as it was (glyph_layers) in these masters, each then read back against what was
    saved; the masters it could not be put back in, or that do not read as they were."""
    left = []
    for master in masters:
        try:
            layer = glyph.getLayerByName(master)
            if saved.get(master) is None:
                if layer is not None:
                    glyph.removeLayer(layer)
            else:
                put_back(layer if layer is not None else glyph.getLayerByName(master, True), saved[master][0],
                         saved[master][1])
        except Exception:
            pass  # (read back below, as every master is)
        if not layer_as_saved(glyph, master, saved.get(master)):
            left.append(master)
    return left


def shapes_read(shapes):
    """What a layer's shapes are, to compare whole: each shape's transform, and a component's glyph or an
    outline's contours, each its nodes' places and kinds in order (a count alone took another drawing of as
    many nodes for the saved one: Codex's review, round 3)."""
    found = []
    for shape in shapes:
        t = shape.transform
        matrix = tuple(round(float(v), 3) for v in (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy()))
        if shape.isComponent:
            found.append(("component", u"%s" % shape.shapeData.componentGlyph, matrix))
        else:
            contours = [None if contour is None else tuple((round(float(node.x), 3), round(float(node.y), 3),
                                                            u"%s" % node.type) for node in list(contour.nodes()))
                        for contour in list(shape.contours)]
            found.append(("outline", matrix, tuple(contours)))
    return found


def layer_as_saved(glyph, master, saved):
    """Whether a master's layer reads as glyph_layers saved it (None: no layer)."""
    try:
        layer = glyph.getLayerByName(master)
        if saved is None:
            return layer is None
        if layer is None or abs(float(layer.advanceWidth or 0) - saved[1]) > 0.5:
            return False
        return saved[2] is not None and shapes_read(list(layer.shapes)) == saved[2]
    except Exception:
        return False


def held_glyph(cm, fontlab, package, name):
    """A new glyph added to the font (held for the session: Glyph Compose's new_glyph), or WriteError."""
    new = cm.new_glyph(fontlab, package, name)
    package.addGlyph(new)
    glyph = package.findName(name)
    if glyph is None:
        raise WriteError(u"FontLab did not add %s" % name)
    return glyph


def write_layer(fontlab, ak, fc, cm, package, master, masters, glyph, layout, corrected):
    """A master's layer of glyph made as layout says (its shapes replaced): components, the mirrored ones
    pointing to their corrected glyphs (corrected(source): its name, made once), stretched outlines, or
    nothing (an empty glyph). True when FontLab kept what was asked. An error is raised after the layer is
    put back; where putting it back fails too, the error says both (the build puts it back again, whole)."""
    QtCore, QtGui = _qt()
    existed = glyph.getLayerByName(master) is not None
    layer = glyph.getLayerByName(master, True)
    own = [cm.shape_copy(shape) for shape in list(layer.shapes)]
    own_width = float(layer.advanceWidth or 0)
    try:
        if write_parts(fontlab, ak, fc, cm, package, master, layer, layout, corrected, u"%s" % glyph.name):
            return True
    except Exception as exc:
        try:
            put_back(layer, own, own_width) if existed else drop_layer(glyph, layer)
        except Exception as again:
            raise WriteError(u"%s; putting master %s back failed at first (%s)" % (exc, master, again))
        raise
    put_back(layer, own, own_width) if existed else drop_layer(glyph, layer)
    return False


def drop_layer(glyph, layer):
    """A layer made for a write FontLab did not keep, taken out (the glyph had none in that master)."""
    try:
        glyph.removeLayer(layer)
    except Exception:
        pass


def put_back(layer, shapes, width):
    """A layer's own shapes and advance put back after a write FontLab did not keep."""
    layer.removeAllShapes()
    for shape in shapes:
        layer.addShape(shape)
    layer.advanceWidth = width


def write_parts(fontlab, ak, fc, cm, package, master, layer, layout, corrected, own=None):
    """The layer's shapes replaced by layout's: own, the glyph's name, is never among the components handed
    to FontLab, through other glyphs neither (checked on the parts as they are written, flattened and their
    mirrors pointed to corrected glyphs, before the layer is cleared: WriteError, the layer as it was)."""
    QtCore, QtGui = _qt()
    components, names, shapes = [], [], []  # (names: the components' glyphs; FontLab's GlyphComponent has no name)
    for part in flat_parts(package, master, layout.parts):
        if part.stretch is not None:
            shapes.append(stretched_shape(fontlab, fc, package, master, part))
            continue
        name, values = part.name, part.matrix
        if is_mirror(values):
            axis = cm.mirror_axis(*values[:4])
            mirror = cm.source_mirror(ak, package, master, name, axis)
            if mirror is None:
                raise WriteError(u"%s has no outline in master %s" % (name, master))
            name, values = corrected(name, axis), cm.without_mirror(values, mirror)
        component = fontlab.GlyphComponent(name)
        component.transform = QtGui.QTransform(*[float(round(v, 6)) for v in values])
        components.append(component)
        names.append(name)
    if own is not None:
        try:
            path = component_loop(own, names,
                                  lambda name: glyph_components(package, list(package.masters) or [master], name))
        except GraphUnreadable as exc:  # (an unreadable graph rules no loop out: the layer is left as it is)
            raise WriteError(u"%s, so it cannot be told whether it would be made of itself" % exc)
        if path is not None:
            raise WriteError(u"it would be %s, a loop of components" % loop_words(own, path))
    layer.removeAllShapes()  # (only once every part is ready: a part that cannot be made leaves it as it was)
    # Always through setGlyphComponents, with no component too (an empty glyph, a stretched dash's outlines
    # added after): a new glyph whose layer was only made by getLayerByName(master, True) crashed FontLab
    # when its fgGlyph was first read (live 2026-11-16, Varela Round: an empty layer and one with an outline
    # alike, 0xC0000005 in FontLab 7.exe+0x72b370); made so first, both kept their code point
    layer.setGlyphComponents(components, float(layout.advance), package, False)
    for shape in shapes:
        layer.addShape(shape)
    layer.advanceWidth = float(layout.advance)
    try:
        layer.update()
    except Exception:
        pass
    wanted = len(components) + len(shapes)
    return len(list(layer.shapes)) >= wanted


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

COLUMNS = (u"Glyph", u"Name", u"Recipe", u"Confidence", u"Note")
ICON_SIZE = 40
PREVIEW_SIZE = 150  # pixels per em
HELP_LIST = (u"The characters the font lacks that it can make of the glyphs it has, by group: each with its "
             u"recipe, a picture of the glyph it makes, and how sure the recipe is (<i>exact</i>: no design in "
             u"it; <i>accepted</i>: how most fonts build it; <i>starting point</i>: a draft to draw over; <i>likely "
             u"usable as it is</i>: a turned or reversed letter the font's monoline design makes so). Checked "
             u"rows are built. A row that needs a glyph the font lacks says which, at the end. Double-click a row "
             u"to open its glyph (built already) in a <i>Glyph</i> window.")


class GenerationPage(object):
    """The Glyph generation tab of Glyph Compose's window: owner, the window (its log, its font, its writes);
    cm, Glyph Compose's module (its mirrored-component machinery, its settings, its helpers)."""

    def __init__(self, owner, cm):
        QtCore, QtGui = _qt()
        self.owner, self.cm, self.ak, self.fontlab = owner, cm, owner.ak, owner.fontlab
        ak = self.ak
        self.data = load_data()
        saved = (getattr(owner, "settings", None) or {}).get(SETTINGS_KEY) or {}
        self.settings = settings_of(self.data, saved)
        self.rows, self.first_checks, self.hidden = [], {}, set()
        self.package = self.master = None
        self.font = None
        self.just_built = set()
        self.buttons_due = False
        self.fc = None
        self.widget = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        self.status.setWhatsThis(u"What the list holds for this font and master: how many glyphs can be built, how "
                                 u"sure their recipes are, and how many need a glyph the font lacks.")
        layout.addWidget(self.status)
        layout.addWidget(ak.separator())
        row = QtGui.QHBoxLayout()
        # What Font Check handed over (the window's generation_given): listed alone at first, as the
        # Diacritics tab lists its own (its Character set's From Font Check)
        self.given = [ch for ch in (getattr(owner, "generation_given", None) or []) if len(ch) == 1]
        self.list_box = None
        if self.given:
            list_help = (u"Which characters are listed: those Font Check handed over (checked), or every group "
                         u"of the table.")
            row.addWidget(cm.helped(QtGui.QLabel(u"List:"), list_help))
            self.list_box = QtGui.QComboBox()
            self.list_box.addItem(u"From Font Check (%s)" % counted(len(self.given), u"glyph"))
            self.list_box.addItem(u"Every group")
            self.list_box.setWhatsThis(list_help)
            row.addWidget(self.list_box)
            row.addSpacing(12)
        self.existing_box = QtGui.QCheckBox(u"Also list existing glyphs")
        self.existing_box.setWhatsThis(u"Also lists the characters of these groups the font has already, in a section "
                                       u"of their own, unchecked: those you check are built again from their recipe, "
                                       u"their outlines in each master replaced (<i>Edit &gt; Undo</i> takes it back). "
                                       u"A glyph that shares its code point is rebuilt as a component of its source.")
        row.addWidget(self.existing_box)
        # The four widths in a row of their own: beside the List chooser and the search field, the search
        # field was squeezed to two letters (live, 2026-11-16)
        settings_row = QtGui.QHBoxLayout()
        self.spins = {}
        for key, label, help_text in (
                ("thin", u"Thin space 1/", u"The thin space's width, and the narrow no-break space's: this share of the "
                                           u"em (1/6 at first; Unicode says 1/5 or 1/6, the corpus's median is 0.158 em)."),
                ("hair", u"Hair space 1/", u"The hair space's width: this share of the em (1/11 at first, the corpus's "
                                           u"median 0.090 em).")):
            settings_row.addWidget(cm.helped(QtGui.QLabel(label), help_text))
            spin = QtGui.QSpinBox()
            spin.setRange(*SETTING_REACH[key])
            spin.setValue(int(self.settings[key]))
            spin.setSuffix(u" em")
            spin.setWhatsThis(help_text)
            settings_row.addWidget(spin)
            settings_row.addSpacing(12)
            self.spins[key] = spin
        for key, label, help_text in (
                ("en_dash", u"En dash", u"The en dash's advance, as a share of the em (52.8% at first: the corpus's median, "
                                        u"507 families). Built from the hyphen, its thickness and ends kept."),
                ("em_dash", u"Em dash", u"The em dash's advance, as a share of the em (86.2% at first: the corpus's median, "
                                        u"507 families); the two- and three-em dashes are two and three times the font's "
                                        u"em dash.")):
            settings_row.addWidget(cm.helped(QtGui.QLabel(label), help_text))
            spin = QtGui.QDoubleSpinBox()
            spin.setRange(SETTING_REACH[key][0] * 100, SETTING_REACH[key][1] * 100)
            spin.setDecimals(1)
            spin.setSingleStep(0.5)
            spin.setValue(round(float(self.settings[key]) * 100, 1))
            spin.setSuffix(u"% of the em")
            spin.setWhatsThis(help_text)
            settings_row.addWidget(spin)
            settings_row.addSpacing(12)
            self.spins[key] = spin
        row.addStretch(1)
        self.search, self.search_label = owner.search_field(
            u"Find a glyph", u"Shows only the rows whose glyph name, or the name of a glyph they are built from, holds "
                             u"this text, whose character it is, whose Unicode value it is (<i>U+2013</i>, <i>2013</i>), "
                             u"or whose Unicode name holds it (<i>dash</i>). Rows not shown keep their checks; <i>Check "
                             u"all</i> and <i>Check none</i> act on the rows shown.")
        row.addWidget(self.search)
        row.addWidget(self.search_label)
        layout.addLayout(row)
        settings_row.addStretch(1)
        layout.addLayout(settings_row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(COLUMNS))
        self.tree.setHeaderLabels(list(COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.table_layout(self.tree, stretch=len(COLUMNS) - 1)
        self.tree.setWhatsThis(HELP_LIST)
        layout.addWidget(self.tree, 3)
        lower = QtGui.QHBoxLayout()
        self.preview = QtGui.QLabel()
        self.preview.setProperty(ak.LEAVE_ALONE_PROP, True)
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setMinimumHeight(int(PREVIEW_SIZE * 1.5))
        self.preview.setWhatsThis(u"The selected row's glyph as it would be built in this master, between dashed lines "
                                  u"at its advance's ends and on the baseline; an empty glyph shows its advance alone.")
        lower.addWidget(self.preview, 1)
        self.details = QtGui.QLabel(u"")
        self.details.setWordWrap(True)
        self.details.setWhatsThis(u"The selected row's character, its Unicode name, the way it is built, and how many of "
                                  u"the corpus's families have it and build it so.")
        lower.addWidget(self.details, 1)
        layout.addLayout(lower, 2)
        buttons = QtGui.QHBoxLayout()
        self.all_button = cm.helped(QtGui.QPushButton(u"Check all"), u"Checks every row shown that can be built (rows "
                                    u"a search hides keep their checks).")
        self.none_button = cm.helped(QtGui.QPushButton(u"Check none"), u"Unchecks every row shown (rows a search hides "
                                     u"keep their checks).")
        self.restore_button = cm.helped(QtGui.QPushButton(u"Restore suggestions"), u"Puts every check, and the four "
                                        u"settings, back as the list first came.")
        self.build_button = QtGui.QPushButton(u"Build checked glyphs")
        self.build_button.setWhatsThis(u"Adds each checked glyph to the font with its Unicode value, in every master, as "
                                       u"its recipe says; a glyph made of others of this list is built after them. A "
                                       u"duplicate's code point goes to its source glyph (no new glyph). Every checked "
                                       u"row is built, those a search hides too: the button then says how many are not "
                                       u"shown. <i>Edit &gt; Undo</i> takes it back, in one step.")
        for button in (self.all_button, self.none_button, self.restore_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.build_button)
        layout.addLayout(buttons)
        self.existing_box.connect("toggled(bool)", lambda on: self.run())
        if self.list_box is not None:
            self.list_box.connect("currentIndexChanged(int)", lambda index: self.run())
        for key, spin in self.spins.items():
            spin.connect("valueChanged(double)" if key in ("en_dash", "em_dash") else "valueChanged(int)",
                         (lambda key: lambda value: self.setting_changed(key, value))(key))
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.build_button.connect("clicked()", self.build)
        self.search.connect("textChanged(QString)", lambda text: self.searched())
        self.tree.connect("itemSelectionChanged()", self.select)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.open_selected())
        try:  # the check boxes drawn plain to see in either palette
            self.check_watcher = self.feature_code().watch_check_boxes(owner.dialog, [self.tree])
        except Exception:
            self.check_watcher = None
        try:  # a right-click flags a row's glyph, as on the suite's other lists
            self.flagging = ak.flag_menu(self.tree, owner, self.flag_names, self.row_names)
        except Exception:
            self.flagging = None
        self.update_buttons()

    # -- the font ----------------------------------------------------------------------------------------

    def feature_code(self):
        if self.fc is None:
            self.fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
        return self.fc

    def font_in(self, package, master):
        codes = self.ak.glyph_code_map(package.fgPackage.glyphs)
        return FontLabFont(self.ak, self.feature_code(), package, master, codes)

    def listed_codes(self):
        """The table's codes to list: Font Check's alone (List: From Font Check), else None (every one)."""
        box = getattr(self, "list_box", None)
        if not getattr(self, "given", None) or box is None or box.currentIndex != 0:
            return None
        return set(u"%04X" % ord(ch) for ch in self.given)

    def planner(self, font, ways=None):
        planner = Planner(self.data, font, self.settings, bool(self.existing_box.checked), self.listed_codes())
        planner.plan(ways)
        return planner

    def run(self, same_font=True):
        """The list read again: checks kept for the same font (by character), the rows first suggested
        otherwise (every buildable row checked but the rebuilds)."""
        if not self.data.get("entries"):
            self.status.setText(u"The recipe table (%s) could not be read: reinstall FreeLab." % DATA_FILE)
            return
        kept = dict((row.hex, row.checked) for row in self.rows) if same_font else {}
        old_key = self.owner.package_key(self.package) if self.package is not None else None
        package = self.package = self.owner.current_font()
        self.rows = []
        if package is None:
            self.status.setText(self.cm.no_font_line(self.ak))
            self.fill()
            return
        if not same_font or self.owner.package_key(package) != old_key:
            kept, self.just_built = {}, set()
        self.master = package.master
        try:
            self.font = self.font_in(package, self.master)
            self.planner_now = self.planner(self.font)
        except Exception as exc:
            self.status.setText(u"Could not read the font: %s" % self.ak.html(exc))
            self.fill()
            return
        self.rows = self.planner_now.rows
        for row in self.rows:
            suggested = row.layout is not None and not row.existing and row.confidence != "starting point"
            row.checked = kept.get(row.hex, suggested) and row.layout is not None
            self.first_checks[row.hex] = suggested
        self.fill()
        self.say_status()

    def say_status(self):
        b = self.ak.b
        buildable = [r for r in self.rows if r.layout is not None and not r.existing]
        lacking = [r for r in self.rows if r.layout is None]
        words = CONFIDENCES[:2] + (LIKELY, CONFIDENCES[2])
        sure = dict((c, sum(1 for r in buildable if r.sureness == c)) for c in words)
        parts = [u"%s %s" % (b(sure[c]), c) for c in words if sure[c]]
        self.status.setText(u"%s, master %s: %s can be built (%s)%s. Nothing changes until you click %s." % (
            b(self.package.tfn), b(self.master), b(counted(len(buildable), u"glyph")), u", ".join(parts) or u"none",
            u"; %s %s a glyph the font lacks" % (b(counted(len(lacking), u"glyph")), u"needs" if len(lacking) == 1 else u"need")
            if lacking else u"", self.ak.i(u"Build checked glyphs")))

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        groups = [(g["id"], g["title"]) for g in self.data.get("groups") or []]
        sections = [(title, [i for i, r in enumerate(self.rows) if r.group == key and r.layout is not None
                             and not r.existing and r.char not in self.just_built]) for key, title in groups]
        sections.append((JUST_BUILT, [i for i, r in enumerate(self.rows) if r.char in self.just_built]))
        sections.append((EXISTING, [i for i, r in enumerate(self.rows) if r.existing and r.char not in self.just_built
                                    and r.layout is not None]))
        sections.append((LACKING, [i for i, r in enumerate(self.rows) if r.layout is None]))
        for title, members in sections:
            if not members:
                continue
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (title, len(members))])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for index in members:
                r = self.rows[index]
                item = QtGui.QTreeWidgetItem([r.char if r.layout is None or r.layout.kind != "empty" else u"",
                                              r.name, recipe_text(r, self.settings, self.data.get("rules")),
                                              confidence_text(r), note_text(r)])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                if r.layout is not None:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(0, QtCore.Qt.Checked if r.checked else QtCore.Qt.Unchecked)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                item.setToolTip(4, u"U+%s %s" % (r.hex, r.entry.get("unicode_name", u"")))
                try:
                    icon = self.picture(r, ICON_SIZE)
                    if icon is not None:
                        item.setIcon(0, self.ak.icon_of(icon))
                except Exception:
                    pass
                top.addChild(item)
            top.setExpanded(title not in (EXISTING, LACKING))
        self.cm.fit_tree_columns(self.tree, len(COLUMNS) - 1)
        self.tree.blockSignals(False)
        self.apply_search()

    # -- the list's controls --------------------------------------------------------------------------------

    def items(self):
        found = []
        for top in range(self.tree.topLevelItemCount):
            item = self.tree.topLevelItem(top)
            found.extend(item.child(child) for child in range(item.childCount()))
        return found

    def harvest(self):
        QtCore = _qt()[0]
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.rows) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                self.rows[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        QtCore = _qt()[0]
        self.tree.blockSignals(True)
        for item in self.items():
            if item.flags() & QtCore.Qt.ItemIsUserCheckable and int(item.data(0, QtCore.Qt.UserRole)) not in self.hidden:
                item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.update_buttons()

    def changed(self):
        QtCore = _qt()[0]
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        self.buttons_due = False
        ak = self.ak
        try:
            self.harvest()
        except Exception:
            pass
        shown = [r for i, r in enumerate(self.rows) if r.layout is not None and i not in self.hidden]
        ak.enable(self.all_button, any(not r.checked for r in shown))
        ak.enable(self.none_button, any(r.checked for r in shown))
        checked = [i for i, r in enumerate(self.rows) if r.checked and r.layout is not None]
        ak.enable(self.build_button, bool(checked))
        self.build_button.setText(self.cm.build_text(len(checked), sum(1 for i in checked if i in self.hidden)))
        defaults = settings_of(self.data)
        ak.enable(self.restore_button, any(r.checked != self.first_checks.get(r.hex, r.checked) for r in self.rows)
                  or any(abs(float(self.settings[k]) - float(defaults[k])) > 1e-9 for k in SETTING_KEYS))

    def searched(self):
        try:
            self.apply_search()
        except Exception as exc:
            self.owner.log.add(u"Could not search the list: %s" % self.ak.html(exc), "error")

    def apply_search(self):
        QtCore = _qt()[0]
        self.hidden = set()
        query = u"%s" % (self.cm._property(self.search, "text") or u"")
        shown = total = 0
        for top in range(self.tree.topLevelItemCount):
            section = self.tree.topLevelItem(top)
            any_shown = False
            for child in range(section.childCount()):
                item = section.child(child)
                index = int(item.data(0, QtCore.Qt.UserRole))
                r = self.rows[index]
                parts = [p.name for p in r.layout.parts] if r.layout is not None else []
                found = self.cm.row_matches(query, r.name, r.char, r.code, parts) or (
                    query and query.lower() in (r.entry.get("unicode_name") or u"").lower())
                total += 1
                shown += 1 if found else 0
                if not found:
                    self.hidden.add(index)
                item.setHidden(not found)
                any_shown = any_shown or found
            section.setHidden(not any_shown)
        self.search_label.setText(self.cm.search_count(shown, total, query))
        self.update_buttons()

    def setting_changed(self, key, value):
        """A setting changed: kept in Glyph Compose's settings file, and the list planned again."""
        value = int(value) if key in ("thin", "hair") else round(float(value) / 100.0, 4)
        if self.settings.get(key) == value:
            return
        self.settings[key] = value
        try:
            settings = self.owner.settings
            settings.setdefault(SETTINGS_KEY, {})[key] = value
            self.cm.write_settings(self.ak, settings)
        except Exception:
            pass
        self.run()

    def restore(self):
        defaults = settings_of(self.data)
        for key, spin in self.spins.items():
            spin.blockSignals(True)
            spin.setValue(int(defaults[key]) if key in ("thin", "hair") else round(defaults[key] * 100, 1))
            spin.blockSignals(False)
        self.settings = defaults
        try:
            self.owner.settings.pop(SETTINGS_KEY, None)
            self.cm.write_settings(self.ak, self.owner.settings)
        except Exception:
            pass
        self.run(same_font=False)
        self.owner.log.add(u"Glyph generation's checks and settings restored as suggested.")

    def selected(self):
        QtCore = _qt()[0]
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def select(self):
        r = self.selected()
        self.preview.clear()
        if r is None:
            self.details.setText(u"")
            return
        try:
            picture = self.picture(r, PREVIEW_SIZE, frame=True)
            if picture is not None:
                self.preview.setPixmap(picture)
        except Exception:
            pass
        lines = [u"<b>%s</b> U+%s %s" % (self.ak.html(r.char) if r.layout is None or r.layout.kind != "empty" else u"",
                                           r.hex, self.ak.html(r.entry.get("unicode_name", u"")))]
        if r.layout is not None:
            lines.append(u"%s (%s)" % (self.ak.html(recipe_text(r, self.settings, self.data.get("rules"))), r.sureness))
            rule = (self.data.get("rules") or {}).get("monoline", {}).get((r.way or {}).get("check"))
            measured = self.planner_now.monoline() if (r.way or {}).get("check") else None
            if rule and measured:
                lines.append(monoline_text(measured, rule, r.likely))
        else:
            lines.append(self.ak.html(r.missing))
        families, deriving = r.entry.get("families", 0), r.entry.get("deriving", 0)
        if families:
            lines.append(corpus_text(families, deriving))
        self.details.setText(u"<br>".join(lines))

    def glyph_in_font(self, r):
        """The font's glyph a row stands for: its own once built, a duplicate's source; None before."""
        if r is None or self.package is None:
            return None
        name = r.layout.shared if r.layout is not None and r.layout.kind == "shared" and not r.existing else r.name
        return name if self.package.findName(name) is not None else None

    def flag_names(self):
        name = self.glyph_in_font(self.selected())
        return [name] if name else []

    def row_names(self, item):
        QtCore = _qt()[0]
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        name = self.glyph_in_font(self.rows[index]) if 0 <= index < len(self.rows) else None
        return [name] if name else []

    def open_selected(self):
        r = self.selected()
        if r is None or self.package is None:
            return
        name = self.glyph_in_font(r)
        if name is None:
            self.owner.log.add(u"%s is not in the font yet: build it first." % self.ak.b(r.name), "warning")
            return
        self.owner.open_glyph(name)

    # -- pictures --------------------------------------------------------------------------------------------

    def part_path(self, part, depth=4):
        """A part's outline as drawn (a QPainterPath, font units, y up): stretched where it is, a planned
        glyph's own parts where it is one."""
        QtCore, QtGui = _qt()
        planner = self.planner_now
        row = planner.by_name.get(part.name)
        if row is not None and row.layout is not None and self.font.glyph_of(row.code) is None and depth:
            path = QtGui.QPainterPath()
            for inner in row.layout.parts:
                found = self.part_path(inner.moved(part.matrix), depth - 1)
                if found is not None:
                    path.addPath(found)
            return path
        path = self.font.path(part.name)[0]
        if path is None:
            return None
        if part.stretch is not None:
            split, amount = part.stretch
            try:  # each element right of the split moved, as the build moves the nodes
                moved = QtGui.QPainterPath(path)
                for index in range(moved.elementCount()):
                    element = moved.elementAt(index)
                    if element.x > split:
                        moved.setElementPositionAt(index, element.x + amount, element.y)
                path = moved
            except Exception:  # (else the ink scaled across to the same length: a picture only)
                box = path.boundingRect()
                width = max(box.width(), 1e-6)
                scale = (width + amount) / width
                path = QtGui.QTransform(scale, 0, 0, 1, box.left() * (1 - scale), 0).map(path)
        return QtGui.QTransform(*part.matrix).map(path)

    def picture(self, r, size, frame=False):
        """The row's glyph in the window's text color, size pixels per em; None where there is nothing."""
        QtCore, QtGui = _qt()
        if r.layout is None or self.font is None:
            return None
        upm = float(self.font.upm)
        scale = float(size) / upm
        path = QtGui.QPainterPath()
        path.setFillRule(QtCore.Qt.WindingFill)
        for part in r.layout.parts:
            found = self.part_path(part)
            if found is not None:
                path.addPath(found)
        box = path.boundingRect() if not path.isEmpty() else None
        left = min(0.0, box.left()) if box else 0.0
        right = max(r.layout.advance, box.right() if box else 0.0)
        width = max(int((right - left) * scale) + 8, 8)
        height = int(size * 1.45)
        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.owner.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(4 - left * scale, size * 1.1)
            painter.scale(scale, -scale)
            if frame or r.layout.kind == "empty":
                pen = QtGui.QPen(color)
                pen.setStyle(QtCore.Qt.DashLine)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(QtCore.QPointF(0, -0.25 * upm), QtCore.QPointF(0, 0.85 * upm))
                painter.drawLine(QtCore.QPointF(r.layout.advance, -0.25 * upm), QtCore.QPointF(r.layout.advance, 0.85 * upm))
                if frame:
                    painter.drawLine(QtCore.QPointF(left, 0), QtCore.QPointF(right, 0))
            if not path.isEmpty():
                painter.fillPath(path, QtGui.QBrush(color))
        finally:
            painter.end()
        return self.ak.inked(pixmap, color)

    # -- the build -------------------------------------------------------------------------------------------

    def made_of(self, row):
        """The names of the glyphs of the list a row is built of, through others too."""
        found, todo = set(), list(row.needs)
        while todo:
            name = todo.pop()
            if name in found:
                continue
            found.add(name)
            need = self.planner_now.by_name.get(name)
            todo.extend(need.needs if need is not None else [])
        return found

    def drop_orphans(self, package, masters, unlisted, chosen, made, built_names, touched):
        """The unlisted prerequisites this build made (prerequisites) that no glyph in the font is made of
        any more (the glyphs that needed them were not built and are gone, or were put back): taken out of
        the font again, and out of made, built_names, and touched. Whether one is used is read from the
        components of the glyphs this build wrote that are still in the font, in every master (a glyph that
        failed may stay, made of it: Codex's review, round 3), never from what was built. (taken out, left:
        [(row, "used" where a glyph left in the font is made of it, "stuck" where FontLab did not take it
        out, "unread" where the components could not be read)])."""
        orphans, left = [], []
        candidates = [r for r in unlisted if r.char in made]
        while True:
            gone = set(r.name for r in orphans)
            used, unread = set(), False
            for r in chosen + unlisted:
                if r.name in gone or package.findName(r.name) is None:
                    continue
                try:
                    used.update(name for name in glyph_components(package, masters, r.name) if name != r.name)
                except GraphUnreadable:
                    unread = True
            if unread:  # (no use ruled out: every one left that is not taken out yet stays, said so)
                left.extend((r, "unread") for r in candidates if r not in orphans and all(r is not k for k, _ in left))
                return orphans, left
            found = [r for r in candidates if r.name not in used and r not in orphans and all(r is not k for k, _ in left)]
            if not found:
                left.extend((r, "used") for r in candidates if r not in orphans and all(r is not k for k, _ in left))
                return orphans, left
            for r in found:
                glyph = package.findName(r.name)
                try:
                    if glyph is not None:
                        package.deleteGlyph(glyph)
                    taken = package.findName(r.name) is None
                except Exception:
                    taken = False
                if not taken:
                    left.append((r, "stuck"))  # (still in the font: what it is made of stays too, read next round)
                    continue
                orphans.append(r)
                made.remove(r.char)
                built_names.discard(r.name)
                touched[:] = [g for g in touched if u"%s" % getattr(g, "name", u"") != r.name]

    def build(self):
        """The checked rows built in every master, as one step of the History (the owner's write: its
        begin_write and end_write)."""
        self.harvest()
        chosen = [r for r in self.rows if r.checked and r.layout is not None]
        if not chosen or self.package is None:
            return
        package = self.package
        if self.owner.package_key(self.owner.current_font()) != self.owner.package_key(package):
            self.run(same_font=False)
            self.owner.log.add(u"The font changed since the list was made: here is this one's. Nothing was built.",
                               "warning")
            return
        log, b, html = self.owner.log, self.ak.b, self.ak.html
        masters = list(package.masters) or [self.master]
        plans = {}  # master: Planner, the current master's way kept for each row
        unlisted = self.planner_now.prerequisites(chosen)  # (what the rows handed over are made of: built too)
        ways = dict((r.hex, r.way_index) for r in list(self.rows) + unlisted if r.way_index is not None)
        for master in masters:
            plans[master] = self.planner_now if master == self.master else self.planner(self.font_in(package, master), ways)
        order = build_order(chosen + unlisted)
        failed = []
        # Before any write: no glyph may end up a component of itself, through others too (Ð and Đ are each
        # a copy of the other: rebuilt together, or one while the other is made of it, they would loop)
        loops = component_loops(order, lambda r: [(plans[m].by_hex.get(r.hex) or Row(r.entry, r.name)).layout
                                                  for m in masters],
                                lambda name: glyph_components(package, masters, name))
        for r in order:
            if r in loops:
                failed.append((r.char, u"%s: left as it was" % loops[r]))
        order = [r for r in order if r not in loops]
        sharing = [package.findName(r.layout.shared) for r in order if r.layout.kind == "shared"]
        if not self.owner.begin_write(package, [g for g in sharing if g is not None]):
            return
        made, rebuilt, shared, touched, error = [], [], [], [], None
        sparse = {}  # master: the glyphs left without a layer there, as their sources have none
        built_names = set()
        helpers = []  # the corrected glyphs made for mirrored parts
        corrected = self.owner.corrector(package, masters, helpers, touched)
        changing = None
        try:
            for r in order:
                lacking = unbuilt_needs(r, [c for c in order if c.name in built_names],
                                        lambda name: package.findName(name) is not None)
                if lacking:
                    failed.append((r.char, u"it needs %s, which %s not built: check %s too" % (
                        u", ".join(lacking), u"was" if len(lacking) == 1 else u"were",
                        u"it" if len(lacking) == 1 else u"them")))
                    continue
                if not r.existing and package.findUnicode(r.code) is not None:
                    failed.append((r.char, u"the font has it now"))
                    continue
                if r.layout.kind == "shared":
                    glyph = package.findName(r.layout.shared)
                    before = list(glyph.fgGlyph.unicodes)
                    glyph.fgGlyph.unicodes = before + [r.code]
                    package.fgPackage.rebuildMaps()
                    if r.code in list(package.findName(r.layout.shared).fgGlyph.unicodes):
                        touched.append(glyph)
                        shared.append((r.char, r.layout.shared))
                        built_names.add(r.name)
                        continue
                    glyph.fgGlyph.unicodes = before
                    package.fgPackage.rebuildMaps()
                    failed.append((r.char, u"FontLab did not keep the second code point on %s" % r.layout.shared))
                    continue
                if r.layout.kind == "mirrored" and not r.existing:
                    try:
                        glyph = self.cm.make_corrected(self.fontlab, self.ak, package, masters, r.layout.parts[0].name,
                                                       r.layout.axis, r.name)
                    except self.cm.MirrorError as exc:
                        failed.append((r.char, u"%s" % exc))
                        continue
                    glyph.fgGlyph.unicode = r.code
                    touched.append(glyph)
                    made.append(r.char)
                    built_names.add(r.name)
                    continue
                glyph = package.findName(r.name)
                added = glyph is None
                if added:
                    glyph = held_glyph(self.cm, self.fontlab, package, r.name)
                changing = glyph
                kept, empty_in, tried, why = [], [], [], None
                saved = glyph_layers(self.cm, glyph, masters) if not added else None  # (put back whole on an error)
                try:
                    for master in masters:
                        row = plans[master].by_hex.get(r.hex)
                        layout = row.layout if row is not None else None
                        if layout is None:  # (a source with no layer there: a sparse master, said once below)
                            sparse.setdefault(master, []).append(r.char)
                            continue
                        tried.append(master)
                        if write_layer(self.fontlab, self.ak, self.feature_code(), self.cm, package, master, masters,
                                       glyph, layout if layout.kind != "mirrored" else Layout(layout.parts, layout.advance),
                                       corrected):
                            kept.append(master)
                        else:
                            empty_in.append(master)
                except Exception as exc:  # (this glyph only: the others are built all the same)
                    why = u"%s" % exc
                if why is None and empty_in:  # (a master FontLab did not keep: the glyph is rebuilt whole or not at all)
                    why = u"FontLab did not keep its parts in %s %s" % (
                        u"master" if len(empty_in) == 1 else u"masters", u", ".join(empty_in))
                if why is not None or not kept:
                    if added:
                        package.deleteGlyph(package.findName(r.name))
                    elif tried and why is not None:
                        # Every master written or tried put back from what was saved, the failing one too (its own
                        # put-back may have failed), each read back: a glyph half rebuilt (Regular new, Bold old)
                        # may no longer interpolate, while the log said it was not built
                        left = put_glyph_back(glyph, saved, tried)
                        if left:
                            why = u"%s; it was changed all the same in %s %s, which could not be put back (the other " \
                                  u"masters are as they were): Edit > Undo takes it back" % (
                                      why, u"master" if len(left) == 1 else u"masters", u", ".join(left))
                        else:
                            why = u"%s; every master left as it was" % why
                    if not added and (tried or why is not None):
                        touched.append(glyph)  # (recorded all the same: one History step, whatever it holds)
                    failed.append((r.char, why or u"FontLab kept none of its parts"))
                    changing = None
                    continue
                if added:
                    package.findName(r.name).fgGlyph.unicode = r.code
                touched.append(glyph)
                changing = None
                (rebuilt if r.existing else made).append(r.char)
                built_names.add(r.name)
        except Exception as exc:
            error = exc
            if changing is not None:
                touched.append(changing)
        orphans, left = [], []  # (prerequisites built for glyphs not built: taken out, or left, and why)
        try:
            orphans, left = self.drop_orphans(package, masters, unlisted, chosen, made, built_names, touched)
        except Exception as exc:
            error = error or exc
        try:  # (whatever happens here, the step below is recorded and the window's write ends)
            unused = unused_helpers(package, masters, helpers, touched)
            for name in unused:  # (made for a glyph that was then not built: taken out, as Diacritics does)
                try:
                    package.deleteGlyph(package.findName(name))
                except Exception:
                    pass
            helpers[:] = [name for name in helpers if name not in unused]
            touched = [glyph for glyph in touched if u"%s" % getattr(glyph, "name", u"") not in unused]
        except Exception as exc:
            error = error or exc
        try:
            package.fgPackage.rebuildMaps()  # (FontLab's lookups by code point see the new ones: live 2026-11-16)
        except Exception:
            pass
        status = None
        try:
            status = self.ak.notify_changed(self.fontlab, package, u"FreeLab Glyph Compose", touched)
        finally:
            self.owner.end_write(package, bool(touched))
        undo = self.cm.undo_words(status, u" <i>Edit &gt; Undo</i> takes it back.")
        if made:
            log.add(u"Built %s: %s.%s" % (b(counted(len(made), u"glyph")), html(u" ".join(made)), undo), "done")
        if shared:
            glyphs = len(set(name for _, name in shared))
            log.add(u"Added %s to %s the font has already, no new glyph: %s.%s" % (
                b(counted(len(shared), u"code point")), u"a glyph" if glyphs == 1 else u"glyphs",
                html(u", ".join(u"%s on %s" % pair for pair in shared)), undo), "done")
        if rebuilt:
            log.add(u"Rebuilt %s from %s recipe, in place: %s.%s" % (
                b(counted(len(rebuilt), u"glyph")), u"its" if len(rebuilt) == 1 else u"their", html(u" ".join(rebuilt)),
                undo), "done")
        done = set(r.char for r in chosen if r.char in made or r.char in rebuilt)
        extra = [r for r in unlisted if r.char in made and any(
            r.name in self.made_of(c) for c in chosen if c.char in done)]  # (only those a glyph built is made of)
        if extra:
            names = set(r.name for r in extra)
            users = [r.char for r in chosen if r.char in done and names & self.made_of(r)]
            log.add(u"%s %s built too, though not listed: %s %s made of %s." % (
                b(html(u" ".join(r.char for r in extra))), u"was" if len(extra) == 1 else u"were",
                html(u" ".join(users)), u"is" if len(users) == 1 else u"are", u"it" if len(extra) == 1 else u"them"),
                "done")
        outcomes = [(orphans, None)] + [([r for r, why in left if why == key and all(r is not e for e in extra)], key)
                                        for key in ("used", "stuck", "unread")]
        for gone, key in outcomes:
            if not gone:
                continue
            names = set(g.name for g in gone)
            users = [r.char for r in chosen if r.char not in done and names & self.made_of(r)]
            one = len(gone) == 1
            it, they = (u"it", u"it stays") if one else (u"them", u"they stay")
            then = {None: u"%s taken out again" % (u"it was" if one else u"they were"),
                    "used": u"a glyph left in the font is made of %s, so %s (Edit > Undo takes %s back)" % (it, they, it),
                    "stuck": u"FontLab did not take %s out again, so %s in the font (Edit > Undo takes %s back)" % (
                        it, they, it),
                    "unread": u"the components of the glyphs it was built for could not be read, so %s in the font "
                              u"(Edit > Undo takes %s back)" % (they, it) if one else
                              u"the components of the glyphs they were built for could not be read, so %s in the font "
                              u"(Edit > Undo takes %s back)" % (they, it)}[key]
            log.add(u"%s %s built for %s, which %s not built: %s." % (
                b(html(u" ".join(r.char for r in gone))), u"was" if one else u"were",
                html(u" ".join(users)) or u"the glyphs listed", u"was" if len(users) == 1 else u"were", then),
                "info" if key is None else "warning")
        if not (made or shared or rebuilt):
            log.add(u"Built none.")
        for master in masters:
            chars = [char for char in sparse.get(master, []) if char in made or char in rebuilt]
            if chars:
                log.add(u"In master %s, %s %s no layer, as %s sources have none there (a variable font's sparse "
                        u"master): %s." % (
                    b(master), counted(len(chars), u"glyph"), u"has" if len(chars) == 1 else u"have",
                    u"its" if len(chars) == 1 else u"their", html(u" ".join(chars))))
        if helpers:
            log.add(u"Added %s for mirrored parts, mirrored with %s contours reversed: %s." % (
                counted(len(helpers), u"glyph"), u"its" if len(helpers) == 1 else u"their", html(u", ".join(helpers))),
                "done")
        for char, why in failed:
            log.add(u"%s was not built: %s." % (b(char), html(why)), "warning")
        self.cm.report_write(status, log)
        if error is not None:
            log.add(u"Stopped by an error: %s" % html(error), "error")
        self.just_built |= set(made) | set(rebuilt)
        self.run()
        try:  # the Diacritics tab's list reads the font again too (a letter built here may be one it listed)
            self.owner.run()
        except Exception:
            pass
