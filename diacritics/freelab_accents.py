#FLM: Accented Glyphs
# -*- coding: utf-8 -*-
"""FreeLab accented glyphs, from FontLab's Scripts menu.

Builds the accented Latin letters a font lacks, as glyphs of components (the base letter and its
marks), in every master. Shows each one before anything is made, and makes only the ones you leave
checked. It needs no groundwork in the font: no anchors, no accented glyphs to learn from, no .case
marks, not even marks.

- What can be built: every character of the chosen Unicode blocks that decomposes into a letter and
  marks (Unicode's canonical decomposition: a caron over a is U+01CE). Each mark is the font's own
  (its .case form for capitals, where there is one), else its twin above for a mark below (a dot below
  from the dot accent), else a draft made of the font's punctuation (a dot accent of the period, a
  dieresis of two, a caron of an upside-down circumflex accent ^), sized as marks are in the
  open-licensed fonts FreeLab learned from. i and j take their dotless forms under a mark above.
- Where the marks go: as the font's own accented glyphs place theirs, where it has some (their gap to
  the ink, and their offset from the center of the letter's top or bottom fifth, as a share of its
  width, pooled per case so that all marks agree); else as the open-licensed fonts place them
  (diacritics/mark_model.json, kept per letter: over b's bowl, not its stem). Marks stack the way
  those fonts stack them: an acute beside a circumflex, as Vietnamese does, a macron over a
  dieresis.
- Room above and below: a glyph must stay clear of the lines above and below at a 120% line spacing.
  A stack that would not is made compact: the gaps between its marks closed, then its marks made
  smaller (to 70% at most); a glyph that still does not fit is listed unchecked, to draw by hand.

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys
import unicodedata

# Combining marks: the root of their glyph names (acute, acutecomb, acute.case, acutecomb.case)
MARKS = {0x0300: "grave", 0x0301: "acute", 0x0302: "circumflex", 0x0303: "tilde", 0x0304: "macron",
         0x0306: "breve", 0x0307: "dotaccent", 0x0308: "dieresis", 0x0309: "hookabove", 0x030A: "ring",
         0x030B: "hungarumlaut", 0x030C: "caron", 0x030F: "dblgrave", 0x0311: "breveinverted", 0x031B: "horn",
         0x0323: "dotbelow", 0x0324: "dieresisbelow", 0x0325: "ringbelow", 0x0326: "commaaccent",
         0x0327: "cedilla", 0x0328: "ogonek", 0x032D: "circumflexbelow", 0x032E: "brevebelow",
         0x0330: "tildebelow", 0x0331: "macronbelow"}
SPACING_MARKS = {0x0300: 0x0060, 0x0301: 0x00B4, 0x0302: 0x02C6, 0x0303: 0x02DC, 0x0304: 0x00AF, 0x0306: 0x02D8,
                 0x0307: 0x02D9, 0x0308: 0x00A8, 0x030A: 0x02DA, 0x030B: 0x02DD, 0x030C: 0x02C7, 0x0327: 0x00B8,
                 0x0328: 0x02DB}  # each combining mark's spacing form, found by its code point
BORROWED = {"dotbelow": "dotaccent", "dieresisbelow": "dieresis", "ringbelow": "ring", "macronbelow": "macron",
            "tildebelow": "tilde", "brevebelow": "breve", "circumflexbelow": "circumflex",
            "commaaccent": "comma"}  # a mark below the font lacks: its twin above (or the comma), moved under
# A mark the font lacks altogether, drafted from its punctuation: (code points, how many side by side,
# flipped upside down). Marks below draft from their twins above.
DRAFTS = {"dotaccent": ((0x002E,), 1, False), "dieresis": ((0x002E,), 2, False), "macron": ((0x002D, 0x2013), 1, False),
          "ring": ((0x00B0,), 1, False), "tilde": ((0x007E,), 1, False), "circumflex": ((0x005E,), 1, False),
          "caron": ((0x005E,), 1, True), "grave": ((0x0060,), 1, False), "acute": ((0x00B4,), 1, False),
          "hungarumlaut": ((0x00B4,), 2, False), "dblgrave": ((0x0060,), 2, False), "commaaccent": ((0x002C,), 1, False),
          "cedilla": ((0x002C,), 1, False)}
DRAFT_SPACING = 0.5  # two drafted dots apart by this share of a dot's width
DOTLESS = {u"i": (u"\u0131", ("dotlessi", "idotless")), u"j": (u"\u0237", ("dotlessj", "jdotless", "uni0237"))}
SETS = (("extended", "Latin-1, Latin Extended-A and -B", ((0x00C0, 0x0250),)),
        ("additional", "Latin Extended Additional (Vietnamese, and more)", ((0x1E00, 0x1F00),)),
        ("all", "All of these", ((0x00C0, 0x0250), (0x1E00, 0x1F00))))
BAND_SHARE = 0.2  # the top or bottom share of a letter's ink whose center a mark centers on
DEFAULT_GAP_SHARE = 0.05  # a mark's gap to its letter, as a share of the em, with no model and no example
LEADING = 1.2  # the line spacing a glyph must fit, as a share of the em (applications' automatic leading)
MIN_SCALE = 0.7  # marks are made no smaller than this to fit
CLOSED_GAPS = 0.4  # a compact stack keeps this share of its gaps
OWN_EXAMPLES = 3  # a font's own placements count once it shows this many on a side, in a case
MODEL_FILE = "mark_model.json"


def side_of(code):
    """Where a combining mark goes: "above", "below", or "right" (the horn)."""
    if code == 0x031B:
        return "right"
    return "below" if unicodedata.combining(unichr_(code)) in (202, 220) else "above"


def unichr_(code):
    """A code point's character; the replacement character past U+FFFF on a narrow Python 2 (FontLab
    7's), which has none of them as one character (no letter is that far up in the blocks used here)."""
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def case_of(ch):
    return "upper" if ch.isupper() else "lower"


def other_case(case):
    return "lower" if case == "upper" else "upper"


class Font(object):
    """What the planning reads of a font: its glyph names, their code points, and which glyphs are
    empty (a character with an empty glyph is planned again, under that glyph's name)."""

    def __init__(self, names, unicodes, empty=()):
        self.names = set(names)
        self.by_code = dict((code, name) for name, code in unicodes if code)
        self.empty = set(empty)

    def glyph_for(self, ch):
        return self.by_code.get(ord(ch))


class Mark(object):
    """A mark of a recipe: its root (acute), side, and the components it is made of, [(glyph, x scale,
    y scale, x, y)] in the mark's own place (one, the mark glyph, unless drafted); with what it stands
    in for (a borrowed twin, a draft)."""

    def __init__(self, root, side, parts, note=None):
        self.root, self.side, self.parts, self.note = root, side, parts, note

    @property
    def glyph(self):
        return self.parts[0][0]

    def label(self):
        names = [part[0] for part in self.parts]
        text = names[0] if len(set(names)) == 1 and len(names) == 1 else u" ".join(names)
        if len(names) > 1 and len(set(names)) == 1:
            text = u"%s \N{MULTIPLICATION SIGN}%d" % (names[0], len(names))
        if self.parts[0][2] < 0:
            text += u" upside down"
        return text + (u" (%s)" % self.note if self.note else u"")


class Recipe(object):
    """A character to build: its base glyph and Marks, or why it cannot."""

    def __init__(self, char, name=None, base=None, marks=None, missing=None):
        self.char, self.name, self.base = char, name, base
        self.marks = marks or []
        self.missing = missing  # what the font lacks, or None
        self.checked = True
        self.refill = False  # its glyph is in the font, empty: filled under its own name
        self.notes = []  # what placing it took (marks made smaller, too tall)

    @property
    def code(self):
        return ord(self.char)

    def describe(self):
        if self.missing:
            return u"needs %s" % self.missing
        return u" + ".join([self.base] + [mark.label() for mark in self.marks])


def find_mark(font, root, case):
    """A mark glyph of the font by its root (its .case form for capitals first), or None."""
    candidates = [root + "comb", root]
    if case == "upper":
        candidates = [root + "comb.case", root + ".case"] + candidates
    for candidate in candidates:
        if candidate in font.names:
            return candidate
    for code, mark_root in MARKS.items():
        if mark_root == root:
            for found_code in (code, SPACING_MARKS.get(code)):
                found = font.by_code.get(found_code) if found_code else None
                if found:
                    return found
    return None


def make_mark(font, code, case):
    """The Mark for a combining mark: the font's own, its twin above (for a mark below), or a draft
    from the font's punctuation; or None."""
    root = MARKS.get(code)
    if root is None:
        return None
    side = side_of(code)
    glyph = find_mark(font, root, case)
    if glyph:
        return Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)])
    twin = BORROWED.get(root)
    if twin:
        glyph = find_mark(font, twin, case) or (font.by_code.get(0x002C) if twin == "comma" else None)
        if glyph:
            return Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)], u"for %s" % root)
    draft_root = root if root in DRAFTS else twin if twin in DRAFTS else None
    if draft_root:
        codes, count, flipped = DRAFTS[draft_root]
        glyph = next((font.by_code[c] for c in codes if c in font.by_code), None)
        if glyph:
            parts = [(glyph, 1.0, -1.0 if flipped else 1.0, 0.0, 0.0) for _ in range(count)]
            return Mark(root, side, parts, u"draft for %s" % root)
    return None


def plan(font, characters):
    """A Recipe for each character the font lacks that decomposes into a letter and marks."""
    recipes = []
    for ch in characters:
        existing = font.by_code.get(ord(ch))
        if (existing and existing not in font.empty) or not unicodedata.category(ch).startswith("L"):
            continue
        decomposed = unicodedata.normalize("NFD", ch)
        if len(decomposed) < 2:
            continue
        base_char, codes = decomposed[0], [ord(c) for c in decomposed[1:]]
        base = font.glyph_for(base_char)
        if base is None:
            recipes.append(Recipe(ch, missing=u"its letter %s" % base_char))
            continue
        name_base = base
        if base_char in DOTLESS and any(side_of(code) == "above" for code in codes):
            dotless_char, dotless_names = DOTLESS[base_char]
            base = font.glyph_for(dotless_char) or next((n for n in dotless_names if n in font.names), base)
        marks, lacking = [], []
        for code in codes:
            mark = make_mark(font, code, case_of(ch))
            if mark is None:
                lacking.append(MARKS.get(code) or u"U+%04X" % code)
            else:
                marks.append(mark)
        if lacking:
            recipes.append(Recipe(ch, missing=u"a %s" % u", a ".join(lacking)))
            continue
        name = existing or glyph_name(font, name_base, [mark.root for mark in marks], ord(ch))
        recipe = Recipe(ch, name, base, marks)
        recipe.refill = bool(existing)
        recipes.append(recipe)
    return recipes


def glyph_name(font, base, roots, code):
    """The base glyph's name and the marks' (adotbelow, acircumflexacute), or uniXXXX when taken."""
    name = base + u"".join(roots)
    return name if name not in font.names else u"uni%04X" % code


class Ink(object):
    """A glyph's ink, in font units: its box, and the center of its top and bottom fifths (where marks
    center), and the right end of its bottom fifth (where an ogonek hangs)."""

    def __init__(self, left, bottom, right, top, top_center=None, bottom_center=None, bottom_right=None, advance=0):
        self.left, self.bottom, self.right, self.top = left, bottom, right, top
        self.top_center = (left + right) / 2.0 if top_center is None else top_center
        self.bottom_center = (left + right) / 2.0 if bottom_center is None else bottom_center
        self.bottom_right = right if bottom_right is None else bottom_right
        self.advance = advance

    @property
    def center(self):
        return (self.left + self.right) / 2.0

    @property
    def width(self):
        return self.right - self.left


def mark_key(name):
    """The root of a mark glyph's name: acutecomb.case and acute are both acute."""
    root = name.split(".")[0]
    return root[:-4] if root.endswith("comb") else root


def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2.0


def load_model(path=None):
    """The open-licensed fonts' mark placements (mark_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), MODEL_FILE)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class Metrics(object):
    """A master's vertical metrics, in font units: the room a glyph has at a 120% line spacing reaches
    up to where the line above's descenders come down, and down to where the line below's tallest
    letters come up."""

    def __init__(self, upm, ascender, descender, caps=None):
        self.upm = float(upm)
        self.top = LEADING * self.upm + min(descender, 0)
        self.bottom = max(ascender, caps or 0) - LEADING * self.upm


class Placement(object):
    """Where marks go: learned from the font's own composites where it has them (per mark and case,
    else pooled per side and case), else from the open-licensed fonts (the model)."""

    def __init__(self, upm, model=None):
        self.upm = float(upm)
        self.model = model or {}
        self.seen = {}  # (mark root, case): [(gap, offset share)]
        self.sides = {}  # (side, case): [(gap, offset share)]

    def learn(self, composites, ink_of, case_of_glyph):
        """composites: [(base glyph, [(mark glyph, dx, dy)])]; ink_of(name) gives an Ink (or None);
        case_of_glyph(name) "upper" or "lower". Only each composite's first mark on a side counts."""
        for base, marks in composites:
            base_ink = ink_of(base)
            if base_ink is None or base_ink.width <= 0:
                continue
            case = case_of_glyph(base)
            done = set()
            for mark, dx, dy in marks:
                ink = ink_of(mark)
                side = mark_side(mark)
                if ink is None or side in done or side == "right":
                    continue
                done.add(side)
                if side == "above":
                    found = (ink.bottom + dy - base_ink.top, (ink.center + dx - base_ink.top_center) / base_ink.width)
                else:
                    root = mark_key(mark)
                    reference = base_ink.bottom_right - ink.width / 2.0 if root == "ogonek" else base_ink.bottom_center
                    found = (base_ink.bottom - (ink.top + dy), (ink.center + dx - reference) / base_ink.width)
                self.seen.setdefault((mark_key(mark), case), []).append(found)
                self.sides.setdefault((side, case), []).append(found)

    def model_value(self, table, *keys):
        found = self.model.get(table, {})
        for key in keys:
            if key in found:
                return found[key]
        return None

    def own_scale(self, side, case):
        """How far the font's own gaps run from the model's on a side (1 without examples)."""
        own = median([g for g, _ in self.sides.get((side, case), [])]) if len(self.sides.get((side, case), [])) >= OWN_EXAMPLES else None
        model = self.model_value("side_gap", u"%s %s" % (side, case))
        if own is None or not model:
            return 1.0
        return min(2.0, max(0.5, own / (model * self.upm)))

    def gap(self, root, side, case, previous=None):
        """The gap of a mark to what is under (above: its letter, or the mark it stacks on) it."""
        if previous is not None:
            pair = self.model_value("pair_gap", u"%s+%s %s" % (previous, root, case), u"%s+%s %s" % (previous, root, other_case(case)))
            if pair is None:
                pair = self.model_value("stack_gap", u"%s %s" % (side, case), u"%s lower" % side)
            return (pair if pair is not None else DEFAULT_GAP_SHARE / 2) * self.upm * self.own_scale(side, case)
        own = self.seen.get((root, case), [])
        if len(own) >= 2:
            return median([g for g, _ in own])
        model = self.model_value("gap", u"%s %s" % (root, case), u"%s %s" % (root, other_case(case)))
        if model is not None:
            return model * self.upm * self.own_scale(side, case)
        pooled = self.sides.get((side, case), [])
        if pooled:
            return median([g for g, _ in pooled])
        return DEFAULT_GAP_SHARE * self.upm

    def offset(self, letter, root, side, case, previous=None):
        """A mark's center off the center of its letter's top (bottom) fifth, as a share of the
        letter's width: the font's habit on that side and case (all marks pooled, so they agree), or
        the model's, plus how far this letter's marks sit from that habit in the model (over b's
        bowl), or the model's offset for a mark on another (an acute by a circumflex)."""
        if previous is not None:
            pair = self.model_value("pair_offset", u"%s+%s %s" % (previous, root, case),
                                    u"%s+%s %s" % (previous, root, other_case(case)))
            return pair or 0.0
        habit_model = self.model_value("side_offset", u"%s %s" % (side, case)) or 0.0
        own = self.sides.get((side, case), [])
        habit = median([o for _, o in own]) if len(own) >= OWN_EXAMPLES else habit_model
        key = root if root in ("ogonek", "horn") else u"*"
        letter_offset = self.model_value("offset", u"%s %s %s" % (letter, side, key))
        return habit + ((letter_offset - habit_model) if letter_offset is not None else 0.0)

    def height(self, root, case):
        """A mark's usual height in the model, in font units, or None."""
        value = self.model_value("height", u"%s %s" % (root, case), u"%s %s" % (root, other_case(case)))
        return value * self.upm if value else None


def learnable(code, parts):
    """Whether a composite shows where marks go: its character decomposes into a letter and the marks
    its components are (an e acute of e and acute), not a fraction, a guillemet, or a middle dot."""
    if not code:
        return False
    decomposed = unicodedata.normalize("NFD", unichr_(code))
    if len(decomposed) != len(parts) or not decomposed[0].isalpha():
        return False
    for (glyph, _, _), mark in zip(parts[1:], decomposed[1:]):
        root = MARKS.get(ord(mark))
        roots = (root, BORROWED.get(root)) + (("commaaccent",) if root == "cedilla" else ())
        if root is None or mark_key(glyph) not in roots:  # (G, K, L, N, R with a comma below decompose
            return False  # with a cedilla: Unicode's names for them predate the comma)
    return True


def mark_side(name):
    """Where a mark glyph goes, by its root's combining mark."""
    root = mark_key(name)
    for code, mark_root in MARKS.items():
        if mark_root == root:
            return side_of(code)
    if root in ("comma", "quotesinglbase", "period"):
        return "below"
    return "above"


def mark_ink(mark, ink_of, placement, case):
    """A Mark's parts laid out side by side (a drafted dieresis's two dots), drafts sized as the model's
    marks are; its box as an Ink, and its parts [(glyph, x scale, y scale, x, y)]."""
    laid, x = [], 0.0
    inks = [ink_of(part[0]) for part in mark.parts]
    if any(ink is None for ink in inks):
        return None, None
    scale = 1.0
    if mark.note and mark.note.startswith(u"draft"):
        wanted = placement.height(mark.root, case)
        ink = inks[0]
        if wanted and ink.top - ink.bottom > 0:
            scale = min(1.5, max(0.3, wanted / float(ink.top - ink.bottom)))
    for (glyph, sx, sy, _, _), ink in zip(mark.parts, inks):
        sx, sy = sx * scale, sy * scale
        left = min(sx * ink.left, sx * ink.right)
        laid.append((glyph, sx, sy, x - left, 0.0))
        x += abs(sx) * ink.width * (1 + DRAFT_SPACING)
    boxes = []
    for (glyph, sx, sy, dx, dy), ink in zip(laid, inks):
        xs = (sx * ink.left + dx, sx * ink.right + dx)
        ys = (sy * ink.bottom + dy, sy * ink.top + dy)
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    box = Ink(min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return box, laid


def layout(recipe, ink_of, placement, letter, gap_share=1.0, stack_share=1.0, scale=1.0):
    """[(glyph, x scale, y scale, x, y)] of a recipe at given shares of its gaps and mark scale, and
    its ink's (top, bottom)."""
    base = ink_of(recipe.base)
    case = case_of(recipe.char)
    parts = [(recipe.base, 1.0, 1.0, 0.0, 0.0)]
    top, bottom = base.top, base.bottom
    previous = {"above": None, "below": None}
    for mark in recipe.marks:
        box, laid = mark_ink(mark, ink_of, placement, case)
        if box is None:
            return None, None, None
        side = mark.side
        if side == "right":  # the horn: at the top right, overlapping the letter a little
            dx = base.right - placement.upm * 0.02 - box.left
            dy = base.top - (box.top - box.bottom) * 0.6 - box.bottom
            parts.extend((g, sx, sy, x + dx, y + dy) for g, sx, sy, x, y in laid)
            top = max(top, box.top + dy)
            continue
        stacked = previous[side]
        gap = placement.gap(mark.root, side, case, stacked) * (stack_share if stacked else gap_share)
        offset = placement.offset(letter, mark.root, side, case, stacked) * base.width
        # the mark made smaller about its edge nearest the letter
        height = (box.top - box.bottom) * scale
        if side == "above":
            target_x = base.top_center + offset
            y = top + gap
            dy_edge, top = y, y + height
        else:
            reference = base.bottom_right - box.width * scale / 2.0 if mark.root == "ogonek" else base.bottom_center
            target_x = reference + offset
            y = bottom - gap - height
            dy_edge, bottom = y, y
        for glyph, sx, sy, x, yy in laid:
            # the part scaled about the mark's bottom left, then moved: its center on target_x, its bottom on y
            px = (x - box.left) * scale + target_x - box.width * scale / 2.0
            py = (yy - box.bottom) * scale + dy_edge
            parts.append((glyph, sx * scale, sy * scale, round(px), round(py)))
        previous[side] = mark.root
    return parts, top, bottom


def place(recipe, ink_of, placement, metrics=None, letter=None):
    """The recipe's components [(glyph, x scale, y scale, x, y)] and width (its letter's): each mark
    placed by the Placement, and, where the glyph would reach past the room a 120% line spacing leaves
    (metrics), made compact: its stack's gaps closed, then its marks made smaller, down to MIN_SCALE.
    recipe.notes says what it took, and whether it still does not fit."""
    letter = letter or unicodedata.normalize("NFD", recipe.char)[0]
    base = ink_of(recipe.base)
    recipe.notes = []
    parts, top, bottom = layout(recipe, ink_of, placement, letter)
    if parts is None:
        return None, base.advance if base else 0
    if metrics is None or (top <= metrics.top and bottom >= metrics.bottom):
        return parts, base.advance
    parts, top, bottom = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS)
    note = u"gaps closed to fit a 120% line"
    if top > metrics.top or bottom < metrics.bottom:
        scale = 1.0
        while scale > MIN_SCALE and (top > metrics.top or bottom < metrics.bottom):
            scale = max(MIN_SCALE, scale - 0.05)
            parts, top, bottom = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS, scale)
        note = u"gaps closed and marks at %d%% to fit a 120%% line" % round(scale * 100)
    recipe.notes.append(note)
    over = max(top - metrics.top, metrics.bottom - bottom)
    if over > 0:
        recipe.notes.append(u"still %d units too tall for a 120%% line: needs a shorter letter or marks drawn "
                            u"for it" % round(over))
        recipe.checked = False
    return parts, base.advance


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 40  # pixels high, each row's picture
PREVIEW_SIZE = 150  # pixels per em, the selected glyph's picture


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: its helpers (outlines, Glyph windows, dialogs)."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "layer_path") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(AUTO_KERNING_MODULE)
            module.__file__ = path
            sys.modules[AUTO_KERNING_MODULE] = module
            with open(path, "rb") as handle:
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


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def counted(number, one, many=None):
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


class FontLabInk(object):
    """The ink of a master's glyphs (components drawn), measured once each."""

    def __init__(self, ak, package, master):
        self.ak, self.package, self.master = ak, package, master
        self.found, self.paths = {}, {}

    def path(self, name):
        if name not in self.paths:
            glyph = self.package.findName(name)
            layer = glyph.getLayerByName(self.master) if glyph is not None and not glyph.isNull else None
            self.paths[name] = (self.ak.layer_path(layer), layer.advanceWidth) if layer is not None else (None, 0)
        return self.paths[name]

    def __call__(self, name):
        if name not in self.found:
            QtCore, QtGui = _qt()
            path, advance = self.path(name)
            if path is None or path.isEmpty():
                self.found[name] = None
            else:
                box = path.boundingRect()  # font units, y up: top() is the ink's lowest y
                left, bottom, right, top = box.left(), box.top(), box.right(), box.bottom()
                band = (top - bottom) * BAND_SHARE

                def part(y0, y1):
                    piece = path.intersected(_rect(QtCore, left - 1, y0, right - left + 2, y1 - y0)).boundingRect()
                    return piece if piece.width() > 0 else None

                upper, lower = part(top - band, top + 1), part(bottom - 1, bottom + band)
                self.found[name] = Ink(left, bottom, right, top,
                                       upper.center().x() if upper else None, lower.center().x() if lower else None,
                                       lower.right() if lower else None, advance)
        return self.found[name]


def _rect(QtCore, x, y, w, h):
    QtGui = _qt()[1]
    path = QtGui.QPainterPath()
    path.addRect(QtCore.QRectF(x, y, w, h))
    return path


def is_empty(glyph):
    """True for a glyph with no layer, or none with shapes (an earlier FreeLab build left 257 such)."""
    try:
        return not any(layer.shapes for layer in glyph.layers)
    except Exception:
        return False


def component_parts(layer):
    """[(glyph, dx, dy)] of a layer made only of components, or None."""
    parts = []
    for shape in layer.shapes:
        try:
            if not shape.isComponent:
                return None
            parts.append((shape.shapeData.componentGlyph, shape.transform.dx(), shape.transform.dy()))
        except Exception:
            return None
    return parts or None


HELP = u"""<b>FreeLab Accented Glyphs</b><br>
Builds the accented letters this font lacks from its letters and marks, as glyphs of components,
placing each mark as the font's own accented glyphs place theirs (no anchors needed). Nothing is
made until you click Build checked glyphs.<br><br>
<b>The list</b>: each character that can be built, drawn as it would be, with the glyphs it is
built from. Capitals take a mark's .case form where the font has one; i and j take their dotless
forms under a mark above. A mark below the font lacks borrows its twin above (a dot below from the
dot accent), and says so. Characters that cannot be built say what the font lacks.<br>
<b>Where marks go</b>: learned from the font's composites, per mark and per case: how far a mark sits
from its letter's ink, and how far off the center of the letter's top (or bottom) fifth. Marks stacked
above (Vietnamese) sit one above the other with the same gap.<br>
<b>Masters</b>: each glyph is built in every master, each measured on its own.<br><br>
Click this help's ? button, then any control, for what it does."""


class AccentsDialog(object):
    COLUMNS = ("Glyph", "Name", "Built from")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = load_auto_kerning()
        main = self.ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Accented Glyphs")
        dialog.setWhatsThis(HELP)
        dialog.resize(760, 760)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = QtGui.QLabel(u"")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Characters of"))
        self.set_box = QtGui.QComboBox()
        for _, label, _ in SETS:
            self.set_box.addItem(label)
        self.set_box.setCurrentIndex(len(SETS) - 1)
        self.set_box.setWhatsThis(u"The Unicode blocks whose missing accented letters are listed.")
        row.addWidget(self.set_box)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setWhatsThis(u"The accented letters this font lacks: those that can be built (checked ones are "
                               u"built), and, at the end, those that need a mark the font does not have.")
        layout.addWidget(self.tree, 1)
        self.preview = QtGui.QLabel()
        self.preview.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn picture alone
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setMinimumHeight(int(PREVIEW_SIZE * 1.5))
        self.preview.setWhatsThis(u"The selected glyph as it would be built, between its letter and an accented "
                                  u"letter the font has, to compare.")
        layout.addWidget(self.preview)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.build_button = QtGui.QPushButton("Build checked glyphs")
        self.build_button.setWhatsThis(u"Adds each checked glyph to the font, with its Unicode value, built from its "
                                       u"letter and marks as components, in every master.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.build_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.set_box.connect("currentIndexChanged(int)", lambda index: self.run())
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.build_button.connect("clicked()", self.build)
        self.close_button.connect("clicked()", dialog.close)
        self.tree.connect("itemSelectionChanged()", self.select)
        self.package = self.master = None
        self.recipes, self.inks, self.placements = [], {}, {}
        self.model = load_model()
        self.ak.plain_buttons(dialog)

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = workspace.currentPackage
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def font(self, package):
        glyphs = list(package.fgPackage.glyphs)
        empty = []
        for g in glyphs:
            if g.unicode and 0xC0 <= g.unicode < 0x1F00:  # (only accented letters' glyphs are looked at)
                glyph = package.findName(g.name)
                if glyph is not None and is_empty(glyph):
                    empty.append(g.name)
        return Font([g.name for g in glyphs], [(g.name, g.unicode) for g in glyphs], empty)

    def characters(self):
        ranges = SETS[self.set_box.currentIndex][2]
        return [unichr_(code) for low, high in ranges for code in range(low, high)]

    def learn(self, package, master):
        """The master's ink and where its composites put their marks."""
        ink = FontLabInk(self.ak, package, master)
        placement = Placement(float(package.upm), self.model)
        composites = []
        for fg in package.fgPackage.glyphs:
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            parts = component_parts(layer) if layer is not None else None
            if parts and len(parts) > 1 and learnable(fg.unicode, parts):
                composites.append((parts[0][0], parts[1:]))
        by_name = dict((g.name, g.unicode) for g in package.fgPackage.glyphs)

        def glyph_case(name):
            code = by_name.get(name)
            return case_of(unichr_(code)) if code else ("upper" if name[:1].isupper() else "lower")

        placement.learn(composites, ink, glyph_case)
        return ink, placement

    def metrics(self, package):
        try:
            return Metrics(package.upm, package.ascender_value, package.descender_value, package.capsHeight_value)
        except Exception:
            return None

    def run(self):
        QtCore, QtGui = _qt()
        self.tree.clear()
        self.recipes = []
        self.build_button.setEnabled(False)
        package = self.package = self.current_font()
        self.master = package.master if package is not None else None
        if package is None:
            self.status.setText(u"No font is open. Open one, then run Accented Glyphs again.")
            return
        self.status.setText(u"Reading the font\N{HORIZONTAL ELLIPSIS}")
        QtGui.QApplication.processEvents()
        try:
            self.recipes = plan(self.font(package), self.characters())
            self.inks, self.placements = {}, {}
            self.inks[self.master], self.placements[self.master] = self.learn(package, self.master)
        except Exception as exc:
            self.status.setText(u"%s" % exc)
            return
        self.fill()

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        buildable = [index for index, r in enumerate(self.recipes) if not r.missing]
        lacking = [index for index, r in enumerate(self.recipes) if r.missing]
        groups = ((u"Can be built", buildable), (u"Need a mark or letter the font lacks", lacking))
        for title, indexes in groups:
            if not indexes:
                continue
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (title, len(indexes))])
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            top.setData(0, QtCore.Qt.UserRole, -1)
            for index in indexes:
                r = self.recipes[index]
                item = QtGui.QTreeWidgetItem([r.char, r.name or u"", r.describe() + (
                    u" (its glyph is in the font, empty: filled when built)" if getattr(r, "refill", False) else u"")])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                item.setToolTip(2, u"U+%04X %s" % (r.code, unicodedata.name(r.char, u"")))
                if r.missing:
                    item.setFlags(QtCore.Qt.ItemIsSelectable)
                else:
                    icon = self.picture(r, ICON_SIZE, with_neighbors=False)  # (placing it notes what it took)
                    if icon is not None:
                        item.setIcon(0, QtGui.QIcon(icon))
                    if r.notes:
                        item.setText(2, r.describe() + u" \N{EM DASH} " + u"; ".join(r.notes))
                        item.setToolTip(2, u"; ".join(r.notes))
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(0, QtCore.Qt.Checked if r.checked else QtCore.Qt.Unchecked)
                top.addChild(item)
            top.setExpanded(title == groups[0][0])
        for column in range(len(self.COLUMNS) - 1):
            self.tree.resizeColumnToContents(column)
        self.build_button.setEnabled(bool(buildable))
        notes = lambda index, start: any((m.note or u"").startswith(start) for m in self.recipes[index].marks)
        borrowed = sum(1 for index in buildable if notes(index, u"for "))
        drafted = sum(1 for index in buildable if notes(index, u"draft"))
        compact = sum(1 for index in buildable if self.recipes[index].notes and self.recipes[index].checked)
        too_tall = sum(1 for index in buildable if not self.recipes[index].checked)
        details = [text for count, text in ((borrowed, u"%d with a mark below borrowed from above"),
                                            (drafted, u"%d with a mark drafted from punctuation"),
                                            (compact, u"%d made compact to fit a 120%% line"),
                                            (too_tall, u"%d too tall even so, left unchecked")) if count]
        self.status.setText(u"%s, master %s: %s can be built%s; %s %s a mark or letter the font lacks. Nothing is "
                            u"made until you click Build checked glyphs." % (
                                self.package.tfn, self.master, counted(len(buildable), u"glyph"),
                                (u" (%s)" % u", ".join(t % c for t, c in zip(details, [n for n in (borrowed, drafted, compact, too_tall) if n])))
                                if details else u"",
                                counted(len(lacking), u"other"), u"needs" if len(lacking) == 1 else u"need"))

    def recipe_items(self):
        QtCore, QtGui = _qt()
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def check_all(self, on):
        QtCore, QtGui = _qt()
        for item in self.recipe_items():
            if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.recipes[index] if 0 <= index < len(self.recipes) else None

    def select(self):
        r = self.selected()
        if r is None or r.missing:
            self.preview.clear()
            return
        picture = self.picture(r, PREVIEW_SIZE, with_neighbors=True)
        if picture is not None:
            self.preview.setPixmap(picture)

    def picture(self, recipe, size, with_neighbors):
        """The recipe drawn as it would be built (between its letter and an accented letter the font has,
        with_neighbors), in the dialog's text color."""
        QtCore, QtGui = _qt()
        ink = self.inks.get(self.master)
        placement = self.placements.get(self.master)
        if ink is None or ink(recipe.base) is None:
            return None
        parts, width = place(recipe, ink, placement, self.metrics(self.package))
        if parts is None:
            return None
        drawn = [(parts, width, True)]
        if with_neighbors:
            neighbors = []
            base_char = unicodedata.normalize("NFD", recipe.char)[0]
            letter = self.font(self.package).glyph_for(base_char)
            if letter:
                neighbors.append(([(letter, 1.0, 1.0, 0.0, 0.0)], ink.path(letter)[1], False))
            sibling = self.sibling(recipe)
            if sibling:
                neighbors.append(([(sibling, 1.0, 1.0, 0.0, 0.0)], ink.path(sibling)[1], False))
            drawn = neighbors[:1] + drawn + neighbors[1:]
        scale = float(size) / float(self.package.upm)
        total = sum(w for _, w, _ in drawn)
        pixmap = QtGui.QPixmap(max(int(total * scale) + size // 3, 4), int(size * 1.45))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            x = size / 6.0
            for glyph_parts, w, is_new in drawn:
                tint = QtGui.QColor(color)
                if not is_new:
                    tint.setAlpha(110)
                for name, sx, sy, dx, dy in glyph_parts:
                    path = ink.path(name)[0]
                    if path is None:
                        continue
                    painter.save()
                    painter.translate(x + dx * scale, size * 1.1 - dy * scale)
                    painter.scale(scale * sx, -scale * sy)
                    painter.fillPath(path, QtGui.QBrush(tint))
                    painter.restore()
                x += w * scale
        finally:
            painter.end()
        return pixmap

    def sibling(self, recipe):
        """An accented letter the font has with the same base, to compare (\u00e1 beside a new \u01ce)."""
        base_char = unicodedata.normalize("NFD", recipe.char)[0]
        font = self.font(self.package)
        for code in sorted(font.by_code):
            ch = unichr_(code)
            decomposed = unicodedata.normalize("NFD", ch)
            if len(decomposed) > 1 and decomposed[0] == base_char:
                return font.by_code[code]
        return None

    # -- building -----------------------------------------------------------

    def build(self):
        QtCore, QtGui = _qt()
        if self.package is None:
            return
        for item in self.recipe_items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.recipes) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                self.recipes[index].checked = item.checkState(0) == QtCore.Qt.Checked
        chosen = [r for r in self.recipes if not r.missing and r.checked]
        if not chosen:
            return
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.status.setText(u"The font changed since the list was made: here is this one's. " + self.status.text)
            return
        masters = list(package.masters) or [self.master]
        metrics = self.metrics(package)
        for master in masters:
            if master not in self.inks:
                self.inks[master], self.placements[master] = self.learn(package, master)
        fontlab = self.fontlab
        made, skipped, error, touched = [], [], None, []
        try:
            for r in chosen:
                glyph = package.findName(r.name)
                if glyph is not None and not is_empty(glyph):
                    skipped.append(r.char)  # made meanwhile
                    continue
                if glyph is None:
                    if package.findUnicode(r.code) is not None:
                        skipped.append(r.char)
                        continue
                    new = fontlab.flGlyph()
                    new.name = r.name
                    new.fgGlyph.unicode = r.code
                    package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
                    glyph = package.findName(r.name)
                    if glyph is None:
                        raise RuntimeError(u"FontLab did not add %s" % r.name)
                for master in masters:
                    ink, placement = self.inks[master], self.placements[master]
                    if ink(r.base) is None:
                        continue  # not drawn in this master
                    parts, width = place(r, ink, placement, metrics)
                    if parts is None:
                        continue
                    components = []
                    for name, sx, sy, dx, dy in parts:
                        component = fontlab.GlyphComponent(name)
                        component.transform = QtGui.QTransform(sx, 0.0, 0.0, sy, float(dx), float(dy))
                        components.append(component)
                    layer = glyph.getLayerByName(master, True)
                    layer.setGlyphComponents(components, float(width), package, False)
                touched.append(glyph)
                if is_empty(package.findName(r.name)):
                    raise RuntimeError(u"FontLab left %s empty" % r.name)
                made.append(r.char)
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
        self.ak.notify_changed(fontlab, package, u"FreeLab Accented Glyphs", touched)
        notes = [u"Built %s: %s." % (counted(len(made), u"glyph"), u"".join(made)) if made else u"Built none."]
        if skipped:
            notes.append(u"%s had been made meanwhile and %s left as %s." % (
                u"".join(skipped), u"was" if len(skipped) == 1 else u"were", u"it was" if len(skipped) == 1 else u"they were"))
        if error is not None:
            notes.append(u"Stopped by an error: %s" % error)
        notes.append(u"New glyphs are added at the end of the font; close it without saving to take them back.")
        self.run()
        self.status.setText(u" ".join(notes) + u" " + self.status.text)

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    held = getattr(sys, "_freelab_accents", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = AccentsDialog()
    except Exception as exc:
        print("FreeLab Accented Glyphs: %s" % exc)
        return
    sys._freelab_accents = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_accents":
    main()
