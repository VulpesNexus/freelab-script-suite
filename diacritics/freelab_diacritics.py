#FLM: Diacritics
# -*- coding: utf-8 -*-
"""FreeLab Diacritics, from FontLab's Scripts menu.

Builds the letters with diacritics a font lacks (Latin, Greek, and Cyrillic), as glyphs of components
(the base letter and its marks), in every master. Shows each one before anything is made, lets each
mark be moved and scaled by hand, and makes only the ones you leave checked. It needs no groundwork in
the font: no anchors, no accented glyphs to learn from, no .case marks, not even marks.

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
- Greek capitals take their tonos at their left, as Greek sets them, the glyph made wider for it.
- Names: Glyphs' names for the characters (glyph_names.json, from glyphsLib's GlyphData.xml, MIT
  License), else the letter's name and the marks' (adotbelow).

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
         0x0330: "tildebelow", 0x0331: "macronbelow", 0x0313: "commaabove", 0x0314: "commareversedabove",
         0x0342: "perispomeni", 0x0345: "ypogegrammeni"}
SPACING_MARKS = {0x0300: 0x0060, 0x0301: 0x00B4, 0x0302: 0x02C6, 0x0303: 0x02DC, 0x0304: 0x00AF, 0x0306: 0x02D8,
                 0x0307: 0x02D9, 0x0308: 0x00A8, 0x030A: 0x02DA, 0x030B: 0x02DD, 0x030C: 0x02C7, 0x0327: 0x00B8,
                 0x0328: 0x02DB, 0x0313: 0x1FBF, 0x0314: 0x1FFE, 0x0342: 0x1FC0,
                 0x0345: 0x037A}  # each combining mark's spacing form, found by its code point
# A script's own forms of a mark, looked for first: (names, spacing code point). Greek's acute is its
# tonos, steeper; Cyrillic's short i takes a breve of its own in many fonts.
SCRIPT_MARKS = {("greek", "acute"): (("tonos",), 0x0384), ("cyrillic", "breve"): (("brevecomb-cy", "breve-cy"), None)}
# Two marks Greek draws as one (the tonos between the dialytika's dots): the font's glyph for both, or
# its two marks set over each other.
JOINED_MARKS = {("greek", (0x0308, 0x0301)): ("dieresistonos", 0x0385)}
# Greek capitals carry these at their left, not above (Ά, Ἀ): the glyph made wider for them.
LEFT_OF_CAPITALS = (0x0301, 0x0300, 0x0313, 0x0314, 0x0342)
LEFT_GAP_SHARE = 0.03  # the gap between a mark at a capital's left and the capital, as a share of the em
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
DOTLESS = {u"i": (u"\u0131", ("dotlessi", "idotless")), u"j": (u"\u0237", ("dotlessj", "jdotless", "uni0237")),
           u"\u0456": (u"\u0131", ("dotlessi", "idotless")),  # Cyrillic i and je: the Latin dotless forms
           u"\u0458": (u"\u0237", ("dotlessj", "jdotless", "uni0237"))}
SETS = (("latin", "Latin-1, Latin Extended-A and -B", ((0x00C0, 0x0250),)),
        ("additional", "Latin Extended Additional (Vietnamese, and more)", ((0x1E00, 0x1F00),)),
        ("greek", "Greek", ((0x0370, 0x0400),)),
        ("cyrillic", "Cyrillic", ((0x0400, 0x0530),)),
        ("all", "All", ((0x00C0, 0x0250), (0x1E00, 0x1F00), (0x0370, 0x0400), (0x0400, 0x0530))))
NAMES_FILE = "glyph_names.json"
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


def script_of(ch):
    """"greek", "cyrillic", or "latin", by the character's Unicode name."""
    name = unicodedata.name(ch, u"")
    if name.startswith(u"GREEK"):
        return "greek"
    if name.startswith(u"CYRILLIC"):
        return "cyrillic"
    return "latin"


_NAMES = {}


def glyph_names(path=None):
    """{code point: Glyphs' name} (glyph_names.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), NAMES_FILE)
    if path not in _NAMES:
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            _NAMES[path] = dict((int(code, 16), name) for code, name in data.get("names", {}).items())
        except (IOError, OSError, ValueError):
            _NAMES[path] = {}
    return _NAMES[path]


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

    def __init__(self, root, side, parts, note=None, joined=False):
        self.root, self.side, self.parts, self.note = root, side, parts, note
        self.joined = joined  # its parts set over each other, centered (a dialytika with tonos), not side by side

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
        self.adjust = {}  # mark index: [dx, dy, x scale, y scale], set by hand (about the mark's center)

    @property
    def code(self):
        return ord(self.char)

    def describe(self):
        if self.missing:
            return u"needs %s" % self.missing
        return u" + ".join([self.base] + [mark.label() for mark in self.marks])


def find_mark(font, root, case, script="latin"):
    """A mark glyph of the font by its root (its .case form for capitals first; the script's own form
    first, Greek's tonos for an acute), or None."""
    candidates = [root + "comb", root]
    if case == "upper":
        candidates = [root + "comb.case", root + ".case"] + candidates
    own, own_code = SCRIPT_MARKS.get((script, root), ((), None))
    first = []
    for name in own:
        first += ([name + ".case"] if case == "upper" else []) + [name]
    for candidate in first + candidates:
        if candidate in font.names:
            return candidate
    if own_code and font.by_code.get(own_code):
        return font.by_code[own_code]
    for code, mark_root in MARKS.items():
        if mark_root == root:
            for found_code in (code, SPACING_MARKS.get(code)):
                found = font.by_code.get(found_code) if found_code else None
                if found:
                    return found
    return None


def make_mark(font, code, case, script="latin"):
    """The Mark for a combining mark: the font's own, its twin above (for a mark below), or a draft
    from the font's punctuation; or None."""
    root = MARKS.get(code)
    if root is None:
        return None
    side = side_of(code)
    glyph = find_mark(font, root, case, script)
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
        script, case = script_of(ch), case_of(ch)
        joined = JOINED_MARKS.get((script, tuple(codes)))
        if joined is not None:
            glyph = joined[0] if joined[0] in font.names else font.by_code.get(joined[1])
            if glyph:
                marks.append(Mark(joined[0], "above", [(glyph, 1.0, 1.0, 0.0, 0.0)]))
            else:
                parts = [make_mark(font, code, case, script) for code in codes]
                if any(part is None for part in parts):
                    lacking.append(joined[0])
                else:
                    marks.append(Mark(joined[0], "above", [part.parts[0] for part in parts],
                                      u"its marks set over each other", joined=True))
            codes = []
        for code in codes:
            mark = make_mark(font, code, case, script)
            if mark is None:
                lacking.append(MARKS.get(code) or u"U+%04X" % code)
            else:
                if script == "greek" and case == "upper" and code in LEFT_OF_CAPITALS:
                    mark.side = "left"
                marks.append(mark)
        if lacking:
            recipes.append(Recipe(ch, missing=u"a %s" % u", a ".join(lacking)))
            continue
        name = existing or glyph_name(font, name_base, [mark.root for mark in marks], ord(ch))
        recipe = Recipe(ch, name, base, marks)
        recipe.refill = bool(existing)
        recipes.append(recipe)
    return recipes


def glyph_name(font, base, roots, code, names=None):
    """Glyphs' name for the character (iishort-cy, Alphatonos), else the base glyph's name and the
    marks' (adotbelow, acircumflexacute); uniXXXX when taken."""
    for name in ((names if names is not None else glyph_names()).get(code), base + u"".join(roots)):
        if name and name not in font.names:
            return name
    return u"uni%04X" % code


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
        if mark.joined:  # over each other: centered on the first, their bottoms level
            first = inks[0]
            center = laid[0][3] + laid[0][1] * (first.left + first.right) / 2.0 if laid else sx * (first.left + first.right) / 2.0
            laid.append((glyph, sx, sy, center - sx * (ink.left + ink.right) / 2.0, sy * (first.bottom - ink.bottom)))
            continue
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
    """[(glyph, x scale, y scale, x, y)] of a recipe at given shares of its gaps and mark scale, its
    ink's (top, bottom), and how much wider it is than its letter (a mark at a Greek capital's left)."""
    base = ink_of(recipe.base)
    case = case_of(recipe.char)
    parts = [(recipe.base, 1.0, 1.0, 0.0, 0.0)]
    top, bottom = base.top, base.bottom
    previous = {"above": None, "below": None}
    left_edge = base.left
    for mark in recipe.marks:
        box, laid = mark_ink(mark, ink_of, placement, case)
        if box is None:
            return None, None, None, 0
        side = mark.side
        if side == "left":  # at a capital's left, its top level with the capital's (Greek)
            gap = LEFT_GAP_SHARE * placement.upm * gap_share
            height = (box.top - box.bottom) * scale
            right = left_edge - gap
            for glyph, sx, sy, x, yy in laid:
                px = (x - box.left) * scale + right - box.width * scale
                py = (yy - box.bottom) * scale + base.top - height
                parts.append((glyph, sx * scale, sy * scale, round(px), round(py)))
            left_edge = right - box.width * scale
            continue
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
    widen = max(0, int(round(base.left - left_edge)))
    if widen:  # everything moves right, so the mark keeps the letter's left sidebearing
        parts = [(glyph, sx, sy, x + widen, y) for glyph, sx, sy, x, y in parts]
    return parts, top, bottom, widen


def mark_ranges(recipe):
    """(first, last + 1) of each mark's parts among a placed recipe's parts (the letter is the first)."""
    ranges, start = [], 1
    for mark in recipe.marks:
        ranges.append((start, start + len(mark.parts)))
        start += len(mark.parts)
    return ranges


def parts_box(parts, ink_of):
    """(left, bottom, right, top) of placed parts' ink, or None."""
    boxes = []
    for glyph, sx, sy, x, y in parts:
        ink = ink_of(glyph)
        if ink is None:
            continue
        xs, ys = (sx * ink.left + x, sx * ink.right + x), (sy * ink.bottom + y, sy * ink.top + y)
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def adjusted(recipe, parts, ink_of):
    """The placed parts with the recipe's marks moved and scaled by hand (recipe.adjust): each mark
    scaled about its own center, then moved."""
    if not recipe.adjust or parts is None:
        return parts
    parts = list(parts)
    for index, (first, last) in enumerate(mark_ranges(recipe)):
        change = recipe.adjust.get(index)
        if not change or last > len(parts):
            continue
        dx, dy, kx, ky = change
        box = parts_box(parts[first:last], ink_of)
        if box is None:
            continue
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        for at in range(first, last):
            glyph, sx, sy, x, y = parts[at]
            parts[at] = (glyph, sx * kx, sy * ky, cx + (x - cx) * kx + dx, cy + (y - cy) * ky + dy)
    return parts


def place(recipe, ink_of, placement, metrics=None, letter=None):
    """The recipe's components [(glyph, x scale, y scale, x, y)] and width (its letter's): each mark
    placed by the Placement, and, where the glyph would reach past the room a 120% line spacing leaves
    (metrics), made compact: its stack's gaps closed, then its marks made smaller, down to MIN_SCALE.
    recipe.notes says what it took, and whether it still does not fit."""
    letter = letter or unicodedata.normalize("NFD", recipe.char)[0]
    base = ink_of(recipe.base)
    recipe.notes = []
    parts, top, bottom, widen = layout(recipe, ink_of, placement, letter)
    if parts is None:
        return None, base.advance if base else 0
    if metrics is None or (top <= metrics.top and bottom >= metrics.bottom):
        return finished(recipe, parts, ink_of), base.advance + widen
    parts, top, bottom, widen = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS)
    note = u"gaps closed to fit a 120% line"
    if top > metrics.top or bottom < metrics.bottom:
        scale = 1.0
        while scale > MIN_SCALE and (top > metrics.top or bottom < metrics.bottom):
            scale = max(MIN_SCALE, scale - 0.05)
            parts, top, bottom, widen = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS, scale)
        note = u"gaps closed and marks at %d%% to fit a 120%% line" % round(scale * 100)
    recipe.notes.append(note)
    over = max(top - metrics.top, metrics.bottom - bottom)
    if over > 0:
        recipe.notes.append(u"still %d units too tall for a 120%% line: needs a shorter letter or marks drawn "
                            u"for it" % round(over))
        recipe.checked = False
    return finished(recipe, parts, ink_of), base.advance + widen


def finished(recipe, parts, ink_of):
    """The placed parts with the hand's changes, and a note of them."""
    if recipe.adjust:
        recipe.notes.append(u"marks placed by hand")
    return adjusted(recipe, parts, ink_of)


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


HELP = u"""<b>FreeLab Diacritics</b><br>
Builds the letters with diacritics this font lacks (Latin, Greek, Cyrillic) from its letters and
marks, as glyphs of components, placing each mark as the font's own accented glyphs place theirs (no
anchors needed). Nothing is made until you click <i>Build checked glyphs</i>.<br><br>
<b>The list</b>: each character that can be built, drawn as it would be, with the glyphs it is
built from. Capitals take a mark's .case form where the font has one; i and j take their dotless
forms under a mark above. A mark the font lacks is borrowed (a dot below from the dot accent) or
drafted from its punctuation, and the list says so. Characters that cannot be built say what the
font lacks. Double-click a glyph the font has to open it in a Glyph window.<br>
<b>The editor</b> (under the list): the selected glyph between its letter and a letter the font has
with the same base. Click a mark to select it; drag it, or press the arrow keys (Shift: 10 units),
to move it; drag a corner or a side of its frame to scale it (Shift on a corner: in proportion);
Tab selects the next mark, Backspace puts the selected one back. Your changes stay with the glyph as
you go down the list, and are built. The dashed lines are the room a 120% line spacing leaves.
Click the letter beside it to open the pair in Auto Kerning (once the glyph is built).<br>
<b>Reference</b>: the character in another font (the installed font with the most of the listed
characters, or one you pick), to compare.<br>
<b>Restore suggestions</b> puts every check and every mark back as the list first came.<br>
<b>Masters</b>: each glyph is built in every master, each measured on its own; marks moved by hand
move by as much in every master.<br><br>
Click this help's ? button, then any control, for what it does."""

EDITOR_HEIGHT = 300  # pixels, the editor's least height
REFERENCE_WIDTH = 170  # pixels, the reference's column
HANDLE = 4  # half the side of a frame's handle, in pixels
SETTINGS_FILE = "diacritics.json"  # in FreeLab's state folder: the reference font chosen
NEIGHBOR_ALPHA = 110  # the letters beside the edited glyph, dimmed
# Families known for many Latin, Greek, and Cyrillic letters: the reference is the installed one with
# the most of the listed characters (all installed families would take minutes to look through).
REFERENCE_FAMILIES = ("Noto Sans", "Noto Serif", "Gentium Plus", "Gentium Book Plus", "Charis SIL", "Andika",
                      "DejaVu Sans", "Segoe UI", "Arial", "Times New Roman", "Calibri", "Cambria", "Tahoma",
                      "Verdana", "Open Sans", "Roboto", "Source Sans 3", "Source Serif 4", "IBM Plex Sans")


def settings_path(ak):
    return os.path.join(ak.state_dir(), SETTINGS_FILE)


def read_settings(ak):
    import io
    import json
    try:
        with io.open(settings_path(ak), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def write_settings(ak, data):
    import io
    import json
    try:
        folder = os.path.dirname(settings_path(ak))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(settings_path(ak), "w", encoding="utf-8") as handle:
            handle.write(u"%s" % json.dumps(data, indent=1, sort_keys=True))
    except (IOError, OSError):
        pass


def make_editor(owner):
    """The mark editor: a widget drawing the selected glyph between its neighbors, its marks clickable,
    movable, and scalable (PythonQt subclasses Qt widgets in Python; the class is made once Qt is in)."""
    QtCore, QtGui = _qt()

    class MarkEditor(QtGui.QWidget):
        def __init__(self):
            QtGui.QWidget.__init__(self)
            self.setFocusPolicy(QtCore.Qt.StrongFocus)
            self.setMouseTracking(True)
            self.setMinimumHeight(EDITOR_HEIGHT)
            self.scene = None  # set by the dialog: see AccentsDialog.scene
            self.selected = None  # the index of the selected mark
            self.drag = None
            self.view = None  # (scale, x of the origin, y of the baseline)

        # -- geometry --------------------------------------------------------

        def geometry(self):
            scene = self.scene
            rect = _property(self, "rect")
            width, height = rect.width(), rect.height()
            total = sum(advance for _, advance, _ in scene["glyphs"]) or scene["upm"]
            top, bottom = scene["top"], scene["bottom"]
            scale = min((width - 24.0) / total, (height - 24.0) / float(top - bottom))
            x0 = (width - total * scale) / 2.0
            y0 = 12.0 + top * scale + ((height - 24.0) - (top - bottom) * scale) / 2.0
            self.view = (scale, x0, y0)
            return scale, x0, y0

        def origin_of(self, role):
            x = 0.0
            for _, advance, glyph_role in self.scene["glyphs"]:
                if glyph_role == role:
                    return x
                x += advance
            return None

        def to_screen(self, x, y):
            scale, x0, y0 = self.view
            return x0 + x * scale, y0 - y * scale

        def to_units(self, sx, sy):
            scale, x0, y0 = self.view
            return (sx - x0) / scale, (y0 - sy) / scale

        def mark_boxes(self):
            """[(index, (left, bottom, right, top))] of the edited glyph's marks, in the editor's units."""
            scene = self.scene
            origin = self.origin_of("new") or 0.0
            found = []
            for index, (first, last) in enumerate(scene["ranges"]):
                box = parts_box(scene["parts"][first:last], scene["ink"])
                if box is not None:
                    found.append((index, (box[0] + origin, box[1], box[2] + origin, box[3])))
            return found

        def screen_box(self, box):
            left, top = self.to_screen(box[0], box[3])
            right, bottom = self.to_screen(box[2], box[1])
            return left, top, right, bottom

        def handles(self, box):
            """{handle: (x, y)} on screen: corners tl, tr, br, bl and sides t, r, b, l."""
            left, top, right, bottom = self.screen_box(box)
            middle_x, middle_y = (left + right) / 2.0, (top + bottom) / 2.0
            return {"tl": (left, top), "tr": (right, top), "br": (right, bottom), "bl": (left, bottom),
                    "t": (middle_x, top), "r": (right, middle_y), "b": (middle_x, bottom), "l": (left, middle_y)}

        def hit(self, x, y):
            """("handle", name) of the selected mark, ("mark", index), ("glyph", role), or None."""
            if self.scene is None or self.view is None:
                return None
            boxes = dict(self.mark_boxes())
            if self.selected in boxes:
                for name, (hx, hy) in self.handles(boxes[self.selected]).items():
                    if abs(x - hx) <= HANDLE + 2 and abs(y - hy) <= HANDLE + 2:
                        return ("handle", name)
            for index, box in sorted(boxes.items(), key=lambda item: item[0] != self.selected):
                left, top, right, bottom = self.screen_box(box)
                if left - 3 <= x <= right + 3 and top - 3 <= y <= bottom + 3:
                    return ("mark", index)
            ux, _ = self.to_units(x, y)
            start = 0.0
            for _, advance, role in self.scene["glyphs"]:
                if start <= ux < start + advance and role != "new":
                    return ("glyph", role)
                start += advance
            return None

        # -- drawing ---------------------------------------------------------

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            try:  # a paint handler must not raise, and its painter must end
                if self.scene is not None:
                    self.paint(painter)
            except Exception:
                pass
            finally:
                painter.end()

        def paint(self, painter):
            scene = self.scene
            scale, x0, y0 = self.geometry()
            palette = _property(self, "palette")
            text = palette.color(QtGui.QPalette.WindowText)
            highlight = palette.color(QtGui.QPalette.Highlight)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            faint = QtGui.QColor(text)
            faint.setAlpha(60)
            width = _property(self, "rect").width()
            painter.setPen(QtGui.QPen(faint, 1))
            painter.drawLine(QtCore.QPointF(0, y0), QtCore.QPointF(width, y0))
            dashed = QtGui.QPen(faint, 1, QtCore.Qt.DashLine)
            painter.setPen(dashed)
            for value in scene["room"]:
                y = y0 - value * scale
                painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(width, y))
            x = 0.0
            for parts, advance, role in scene["glyphs"]:
                ink = QtGui.QColor(text)
                if role != "new":
                    ink.setAlpha(NEIGHBOR_ALPHA)
                for at, (glyph, sx, sy, dx, dy) in enumerate(parts):
                    path = scene["ink"].path(glyph)[0]
                    if path is None:
                        continue
                    color = ink
                    if role == "new" and self.selected is not None and self.selected < len(scene["ranges"]):
                        first, last = scene["ranges"][self.selected]
                        if first <= at < last:
                            color = highlight
                    painter.save()
                    painter.translate(x0 + (x + dx) * scale, y0 - dy * scale)
                    painter.scale(scale * sx, -scale * sy)
                    painter.fillPath(path, QtGui.QBrush(color))
                    painter.restore()
                x += advance
            boxes = dict(self.mark_boxes())
            if self.selected in boxes:
                left, top, right, bottom = self.screen_box(boxes[self.selected])
                painter.setPen(QtGui.QPen(highlight, 1, QtCore.Qt.DashLine))
                painter.setBrush(QtGui.QBrush())
                painter.drawRect(QtCore.QRectF(left, top, right - left, bottom - top))
                painter.setPen(QtGui.QPen(highlight, 1))
                painter.setBrush(QtGui.QBrush(palette.color(QtGui.QPalette.Base)))
                for hx, hy in self.handles(boxes[self.selected]).values():
                    painter.drawRect(QtCore.QRectF(hx - HANDLE, hy - HANDLE, 2 * HANDLE, 2 * HANDLE))

        # -- the mouse and the keys ---------------------------------------------

        def mousePressEvent(self, event):
            try:
                if event.button() != QtCore.Qt.LeftButton:
                    return
                self.setFocus()
                pos = event.pos()
                found = self.hit(pos.x(), pos.y())
                if found is None:
                    self.select(None)
                    return
                kind, what = found
                if kind == "glyph":
                    owner.neighbor_clicked(what)
                    return
                if kind == "mark":
                    self.select(what)
                    self.drag = ("move", pos.x(), pos.y(), list(owner.adjust_of(what)), None)
                else:
                    box = dict(self.mark_boxes())[self.selected]
                    self.drag = ("scale", pos.x(), pos.y(), list(owner.adjust_of(self.selected)), (what, box))
            except Exception:
                pass

        def mouseMoveEvent(self, event):
            try:
                pos = event.pos()
                if self.drag is None:
                    found = self.hit(pos.x(), pos.y())
                    shapes = {"tl": QtCore.Qt.SizeFDiagCursor, "br": QtCore.Qt.SizeFDiagCursor,
                              "tr": QtCore.Qt.SizeBDiagCursor, "bl": QtCore.Qt.SizeBDiagCursor,
                              "t": QtCore.Qt.SizeVerCursor, "b": QtCore.Qt.SizeVerCursor,
                              "l": QtCore.Qt.SizeHorCursor, "r": QtCore.Qt.SizeHorCursor}
                    if found is None:
                        self.setCursor(QtCore.Qt.ArrowCursor)
                    elif found[0] == "handle":
                        self.setCursor(shapes[found[1]])
                    elif found[0] == "mark":
                        self.setCursor(QtCore.Qt.SizeAllCursor)
                    else:
                        self.setCursor(QtCore.Qt.PointingHandCursor)
                    return
                kind, x, y, start, extra = self.drag
                scale = self.view[0]
                shift = bool(int(event.modifiers()) & int(QtCore.Qt.ShiftModifier))
                if kind == "move":
                    dx, dy = (pos.x() - x) / scale, -(pos.y() - y) / scale
                    if shift:  # along one axis
                        if abs(dx) > abs(dy):
                            dy = 0.0
                        else:
                            dx = 0.0
                    owner.set_adjust(self.selected, [start[0] + dx, start[1] + dy, start[2], start[3]], final=False)
                else:
                    handle, box = extra
                    owner.set_adjust(self.selected, self.scaled(handle, box, start, pos, shift), final=False)
            except Exception:
                pass

        def scaled(self, handle, box, start, pos, shift):
            """The adjustment for a frame's handle dragged to pos: the opposite corner or side stays."""
            left, bottom, right, top = box
            ux, uy = self.to_units(pos.x(), pos.y())
            kx = ky = 1.0
            fixed_x = right if "l" in handle else left
            fixed_y = bottom if "t" in handle else top
            if "l" in handle or "r" in handle:
                moving = left if "l" in handle else right
                kx = (ux - fixed_x) / (moving - fixed_x) if moving != fixed_x else 1.0
            if "t" in handle or "b" in handle:
                moving = top if "t" in handle else bottom
                ky = (uy - fixed_y) / (moving - fixed_y) if moving != fixed_y else 1.0
            if shift and len(handle) == 2:
                kx = ky = max(kx, ky)
            kx, ky = max(0.1, kx), max(0.1, ky)
            # the box's center now, and after: the fixed side stays where it is
            cx, cy = (left + right) / 2.0, (bottom + top) / 2.0
            new_cx = fixed_x + (cx - fixed_x) * kx if ("l" in handle or "r" in handle) else cx
            new_cy = fixed_y + (cy - fixed_y) * ky if ("t" in handle or "b" in handle) else cy
            return [start[0] + new_cx - cx, start[1] + new_cy - cy, start[2] * kx, start[3] * ky]

        def mouseReleaseEvent(self, event):
            try:
                if self.drag is not None and self.selected is not None:
                    owner.set_adjust(self.selected, owner.adjust_of(self.selected), final=True)
            except Exception:
                pass
            self.drag = None

        def keyPressEvent(self, event):
            try:
                key = event.key()
                shift = bool(int(event.modifiers()) & int(QtCore.Qt.ShiftModifier))
                step = 10.0 if shift else 1.0
                moves = {QtCore.Qt.Key_Left: (-step, 0), QtCore.Qt.Key_Right: (step, 0),
                         QtCore.Qt.Key_Up: (0, step), QtCore.Qt.Key_Down: (0, -step)}
                count = len(self.scene["ranges"]) if self.scene else 0
                if key in moves and self.selected is not None:
                    dx, dy = moves[key]
                    change = list(owner.adjust_of(self.selected))
                    owner.set_adjust(self.selected, [change[0] + dx, change[1] + dy, change[2], change[3]], final=True)
                elif key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab) and count:
                    current = -1 if self.selected is None else self.selected
                    self.select((current + (1 if key == QtCore.Qt.Key_Tab else -1)) % count)
                elif key in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete) and self.selected is not None:
                    owner.set_adjust(self.selected, [0.0, 0.0, 1.0, 1.0], final=True)
                elif key == QtCore.Qt.Key_Escape:
                    self.select(None)
                else:
                    event.ignore()
                    return
                event.accept()
            except Exception:
                pass

        def focusNextPrevChild(self, forward):
            return False  # Tab selects the next mark instead of the next control

        def select(self, index):
            self.selected = index
            owner.mark_selected(index)
            self.update()

    return MarkEditor()


class AccentsDialog(object):
    COLUMNS = ("Glyph", "Name", "Built from")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Diacritics")
        dialog.setWhatsThis(HELP)
        dialog.resize(900, 1000)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = ak.rich(QtGui.QLabel(u""))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = ak.Log()
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Character set:"))
        self.set_box = QtGui.QComboBox()
        for _, label, _ in SETS:
            self.set_box.addItem(label)
        self.set_box.setCurrentIndex(len(SETS) - 1)
        self.set_box.setWhatsThis(u"The Unicode blocks whose missing letters with diacritics are listed.")
        row.addWidget(self.set_box)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.grid_lines(self.tree)
        self.tree.setWhatsThis(u"The letters with diacritics this font lacks: those that can be built (checked ones "
                               u"are built), and, at the end, those that need a mark the font does not have. "
                               u"Double-click a glyph the font has to open it in a Glyph window.")
        layout.addWidget(self.tree, 3)

        lower = QtGui.QHBoxLayout()
        reference = QtGui.QVBoxLayout()
        title = QtGui.QLabel(u"Reference")
        bold = QtGui.QFont(title.font)
        bold.setBold(True)
        title.setFont(bold)
        reference.addWidget(title)
        self.reference_font = QtGui.QFontComboBox()
        self.reference_font.setMaximumWidth(REFERENCE_WIDTH)
        self.reference_font.setWhatsThis(u"The font the reference is drawn in: at first, the installed font with the "
                                         u"most of the listed characters.")
        reference.addWidget(self.reference_font)
        self.reference = QtGui.QLabel()
        self.reference.setProperty(ak.LEAVE_ALONE_PROP, True)
        self.reference.setAlignment(QtCore.Qt.AlignCenter)
        self.reference.setFixedWidth(REFERENCE_WIDTH)
        self.reference.setMinimumHeight(EDITOR_HEIGHT - 60)
        self.reference.setWhatsThis(u"The selected character in the reference font, to compare.")
        reference.addWidget(self.reference, 1)
        self.reference_note = QtGui.QLabel(u"")
        self.reference_note.setWordWrap(True)
        self.reference_note.setFixedWidth(REFERENCE_WIDTH)
        reference.addWidget(self.reference_note)
        lower.addLayout(reference)
        editing = QtGui.QVBoxLayout()
        self.editor = make_editor(self)
        self.editor.setProperty(ak.LEAVE_ALONE_PROP, True)  # dark mode leaves what it draws alone
        self.editor.setWhatsThis(u"The selected glyph as it would be built, between its letter and a letter the font "
                                 u"has with the same base. Click a mark to select it, drag it or press the arrow keys "
                                 u"to move it, drag its frame to scale it; Tab selects the next mark, Backspace puts "
                                 u"it back. Click the letter beside it to open the pair in Auto Kerning.")
        editing.addWidget(self.editor, 1)
        hint_row = QtGui.QHBoxLayout()
        self.hint = QtGui.QLabel(u"Click a mark to move or scale it.")
        self.hint.setWordWrap(True)
        hint_row.addWidget(self.hint, 1)
        self.reset_marks_button = QtGui.QPushButton(u"Reset marks")
        self.reset_marks_button.setWhatsThis(u"Puts this glyph's marks back where they were suggested.")
        hint_row.addWidget(self.reset_marks_button)
        editing.addLayout(hint_row)
        lower.addLayout(editing, 1)
        layout.addLayout(lower, 2)
        layout.addWidget(self.log.view)

        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every check, and every mark moved by hand, back as the list first came.")
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected glyph in a Glyph window, between H's, n's, and o's "
                                              u"(only a glyph the font has: build it first).")
        self.build_button = QtGui.QPushButton("Build checked glyphs")
        self.build_button.setWhatsThis(u"Adds each checked glyph to the font, with its Unicode value, built from its "
                                       u"letter and marks as components, in every master. Edit > Undo takes it back.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button, self.glyph_window_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.build_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.set_box.connect("currentIndexChanged(int)", lambda index: self.run())
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.reset_marks_button.connect("clicked()", self.reset_marks)
        self.build_button.connect("clicked()", self.build)
        self.close_button.connect("clicked()", dialog.close)
        self.tree.connect("itemSelectionChanged()", self.select)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons_soon())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        self.reference_font.connect("currentFontChanged(QFont)", lambda font: self.reference_changed())
        self.package = self.master = None
        self.recipes, self.inks, self.placements = [], {}, {}
        self.first_checks, self.seen_history, self.buttons_due, self.busy = {}, None, False, False
        self.settings = read_settings(ak)
        self.choosing_reference = False
        self.model = load_model()
        ak.plain_buttons(dialog)
        self.history_timer = ak.watch_history(self)
        self.update_buttons()

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
            if g.unicode and 0xC0 <= g.unicode < 0x1F00:  # (only letters with diacritics are looked at)
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

    # -- the list ----------------------------------------------------------------

    def run(self):
        QtCore, QtGui = _qt()
        kept = dict((r.char, (r.checked, dict(r.adjust))) for r in self.recipes)
        same_font = self.package is not None
        self.tree.clear()
        self.recipes = []
        self.build_button.setEnabled(False)
        package = self.package = self.current_font()
        self.master = package.master if package is not None else None
        if package is None:
            self.status.setText(u"No font is open. Open one, then run Diacritics again.")
            self.update_buttons()
            return
        self.status.setText(u"Reading the font\N{HORIZONTAL ELLIPSIS}")
        QtGui.QApplication.processEvents()
        try:
            font = self.font(package)
            present = set(script_of(unichr_(code)) for code in font.by_code
                          if 0x0370 <= code < 0x0530 and unicodedata.category(unichr_(code)).startswith(u"L"))
            wanted = [ch for ch in self.characters() if script_of(ch) == "latin" or script_of(ch) in present]
            self.absent = sorted(set(script_of(ch).capitalize() for ch in self.characters()
                                     if script_of(ch) != "latin" and script_of(ch) not in present))
            self.recipes = plan(font, wanted)
            self.inks, self.placements = {}, {}
            self.inks[self.master], self.placements[self.master] = self.learn(package, self.master)
        except Exception as exc:
            self.status.setText(u"")
            self.log.add(self.ak.html(exc), "error")
            return
        self.fill()
        self.first_checks = dict((r.char, r.checked) for r in self.recipes)
        if same_font:  # the hand's changes and checks carry over (an undo, another set)
            for r in self.recipes:
                if r.char in kept:
                    r.checked, r.adjust = kept[r.char][0], kept[r.char][1]
            self.fill()
        self.seen_history = self.ak.history_mark(package)
        self.choose_reference()

    def fill(self):
        QtCore, QtGui = _qt()
        ak = self.ak
        self.tree.blockSignals(True)
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
                item = QtGui.QTreeWidgetItem([r.char, r.name or u"", u""])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                item.setToolTip(0, u"U+%04X %s" % (r.code, unicodedata.name(r.char, u"")))
                if r.missing:
                    item.setText(2, r.describe() + u".")
                    item.setFlags(QtCore.Qt.ItemIsSelectable)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    self.refresh_item(item, r, first=True)
                    item.setCheckState(0, QtCore.Qt.Checked if r.checked else QtCore.Qt.Unchecked)
                top.addChild(item)
            top.setExpanded(title == groups[0][0])
        for column in range(len(self.COLUMNS) - 1):
            self.tree.resizeColumnToContents(column)
        self.tree.blockSignals(False)
        notes = lambda index, start: any((m.note or u"").startswith(start) for m in self.recipes[index].marks)
        borrowed = sum(1 for index in buildable if notes(index, u"for "))
        drafted = sum(1 for index in buildable if notes(index, u"draft"))
        compact = sum(1 for index in buildable if any(n.startswith(u"gaps") for n in self.recipes[index].notes))
        too_tall = sum(1 for index in buildable if any(n.startswith(u"still") for n in self.recipes[index].notes))
        b = ak.b
        details = [text % b(count) for count, text in ((borrowed, u"%s with a mark below borrowed from above"),
                                                      (drafted, u"%s with a mark drafted from punctuation"),
                                                      (compact, u"%s made compact to fit a 120%% line"),
                                                      (too_tall, u"%s too tall even so, left unchecked")) if count]
        self.status.setText(u"%s, master %s: %s can be built%s; %s %s a mark or letter the font lacks. Nothing is "
                            u"made until you click %s." % (
                                b(self.package.tfn), b(self.master), b(counted(len(buildable), u"glyph")),
                                (u" (%s)" % u", ".join(details)) if details else u"",
                                b(counted(len(lacking), u"other")), u"needs" if len(lacking) == 1 else u"need",
                                ak.i(u"Build checked glyphs")) + (
                                u" The font has no %s letters: theirs are not listed." % u" or ".join(self.absent)
                                if getattr(self, "absent", None) else u""))
        self.update_buttons()

    def refresh_item(self, item, r, first=False):
        """A row's picture and what it is built from, as the recipe is now."""
        QtCore, QtGui = _qt()
        checked = r.checked
        icon = self.picture(r, ICON_SIZE)  # (placing it notes what it took)
        if not first:
            r.checked = checked  # a mark moved by hand does not uncheck the glyph
        if icon is not None:
            item.setIcon(0, QtGui.QIcon(icon))
        text = r.describe() + (u" (its glyph is in the font, empty: filled when built)" if r.refill else u"")
        if r.notes:
            text += u" \N{EM DASH} " + u"; ".join(r.notes)
        item.setText(2, text + u".")
        item.setToolTip(2, (u"; ".join(r.notes) + u".") if r.notes else u"")

    def recipe_items(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def item_of(self, recipe):
        QtCore, QtGui = _qt()
        for item in self.recipe_items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.recipes) and self.recipes[index] is recipe:
                return item
        return None

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.recipe_items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.recipes) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                self.recipes[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        for item in self.recipe_items():
            if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.update_buttons()

    def update_buttons_soon(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        QtCore, QtGui = _qt()
        self.buttons_due = False
        ak = self.ak
        items = [item for item in self.recipe_items() if item.flags() & QtCore.Qt.ItemIsUserCheckable]
        some_on, some_off = ak.checks_of(items, lambda item: item.checkState(0) == QtCore.Qt.Checked)
        ak.enable(self.all_button, some_off)
        ak.enable(self.none_button, some_on)
        ak.enable(self.build_button, some_on and self.package is not None)
        self.harvest()
        ak.enable(self.restore_button, any(r.adjust or self.first_checks.get(r.char, r.checked) != r.checked
                                           for r in self.recipes))
        r = self.selected()
        ak.enable(self.glyph_window_button, r is not None and self.in_font(r))
        ak.enable(self.reset_marks_button, r is not None and bool(r.adjust))

    def restore(self):
        """Every check and every mark as the list first came."""
        for r in self.recipes:
            r.adjust = {}
            r.checked = self.first_checks.get(r.char, r.checked)
        self.fill()
        self.select()
        self.log.add(u"Checks and marks restored as suggested.")

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.recipes[index] if 0 <= index < len(self.recipes) else None

    def in_font(self, r):
        glyph = self.package.findName(r.name) if self.package is not None and r.name else None
        return glyph is not None and not is_empty(glyph)

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again (checks and marks moved by hand
        kept)."""
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()

    # -- the editor ----------------------------------------------------------------

    def select(self):
        r = self.selected()
        self.editor.selected = None
        if r is None or r.missing:
            self.editor.scene = None
            self.editor.update()
            self.hint.setText(u"Select a glyph that can be built to place its marks." if r is None else
                              u"%s %s." % (r.char, r.describe()))
            self.draw_reference(r)
            self.update_buttons()
            return
        self.editor.scene = self.scene(r)
        self.editor.update()
        self.hint.setText(u"Click a mark to move or scale it.")
        self.draw_reference(r)
        self.update_buttons()

    def scene(self, recipe):
        """What the editor draws: the recipe placed, between its letter and a sibling; its marks' ranges;
        the room of a 120% line."""
        ink = self.inks.get(self.master)
        placement = self.placements.get(self.master)
        if ink is None or ink(recipe.base) is None:
            return None
        checked = recipe.checked
        parts, width = place(recipe, ink, placement, self.metrics(self.package))
        recipe.checked = checked
        if parts is None:
            return None
        glyphs = []
        base_char = unicodedata.normalize("NFD", recipe.char)[0]
        letter = self.font(self.package).glyph_for(base_char)
        if letter:
            glyphs.append(([(letter, 1.0, 1.0, 0.0, 0.0)], ink.path(letter)[1], "before"))
        glyphs.append((parts, width, "new"))
        sibling = self.sibling(recipe)
        if sibling:
            glyphs.append(([(sibling, 1.0, 1.0, 0.0, 0.0)], ink.path(sibling)[1], "after"))
        metrics = self.metrics(self.package)
        upm = float(self.package.upm)
        top = max(metrics.top if metrics else upm, max(parts_box(parts, ink)[3], 0)) + upm * 0.05
        bottom = min(metrics.bottom if metrics else -0.3 * upm, parts_box(parts, ink)[1]) - upm * 0.05
        return {"glyphs": glyphs, "parts": parts, "ranges": mark_ranges(recipe), "ink": ink, "upm": upm,
                "top": top, "bottom": bottom, "room": (metrics.top, metrics.bottom) if metrics else (),
                "letters": (letter, sibling)}

    def adjust_of(self, index):
        r = self.selected()
        return list(r.adjust.get(index, [0.0, 0.0, 1.0, 1.0])) if r is not None else [0.0, 0.0, 1.0, 1.0]

    def set_adjust(self, index, change, final):
        """A mark moved or scaled by hand: drawn at once; its row's picture redrawn when done."""
        r = self.selected()
        if r is None or index is None:
            return
        dx, dy, kx, ky = change
        if abs(dx) < 0.01 and abs(dy) < 0.01 and abs(kx - 1) < 1e-4 and abs(ky - 1) < 1e-4:
            r.adjust.pop(index, None)
        else:
            r.adjust[index] = [round(dx, 2), round(dy, 2), round(kx, 4), round(ky, 4)]
        self.editor.scene = self.scene(r)
        self.editor.update()
        self.mark_selected(index)
        if final:
            item = self.item_of(r)
            if item is not None:
                self.tree.blockSignals(True)
                self.refresh_item(item, r)
                self.tree.blockSignals(False)
            self.update_buttons()

    def mark_selected(self, index):
        r = self.selected()
        if r is None or index is None or index >= len(r.marks):
            self.hint.setText(u"Click a mark to move or scale it.")
            return
        dx, dy, kx, ky = self.adjust_of(index)
        mark = r.marks[index]
        moved = u", moved %d, %d" % (round(dx), round(dy)) if (dx or dy) else u""
        sized = u", at %d%% \N{MULTIPLICATION SIGN} %d%%" % (round(kx * 100), round(ky * 100)) if (kx != 1 or ky != 1) else u""
        self.hint.setText(u"%s%s%s. Arrows move it (Shift: 10 units); its frame scales it; Backspace puts it back."
                          % (mark.label(), moved, sized))

    def reset_marks(self):
        r = self.selected()
        if r is None:
            return
        r.adjust = {}
        self.select()
        item = self.item_of(r)
        if item is not None:
            self.tree.blockSignals(True)
            self.refresh_item(item, r)
            self.tree.blockSignals(False)
        self.update_buttons()

    def neighbor_clicked(self, role):
        """The letter beside the edited glyph clicked: their pair in Auto Kerning, once the glyph is built."""
        r = self.selected()
        scene = self.editor.scene
        if r is None or scene is None:
            return
        letter, sibling = scene["letters"]
        if not self.in_font(r):
            self.log.add(u"%s is not built yet: Auto Kerning measures the font's glyphs. Build it first." % self.ak.b(r.char),
                         "warning")
            return
        pair = (letter, r.name) if role == "before" else (r.name, sibling)
        error = self.ak.open_auto_kerning_at(*pair)
        if error:
            self.log.add(u"Auto Kerning did not open: %s" % self.ak.html(error), "error")

    def picture(self, recipe, size):
        """The recipe drawn as it would be built, in the dialog's text color."""
        QtCore, QtGui = _qt()
        ink = self.inks.get(self.master)
        placement = self.placements.get(self.master)
        if ink is None or ink(recipe.base) is None:
            return None
        parts, width = place(recipe, ink, placement, self.metrics(self.package))
        if parts is None:
            return None
        scale = float(size) / float(self.package.upm)
        pixmap = QtGui.QPixmap(max(int(width * scale) + size // 3, 4), int(size * 1.45))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            for name, sx, sy, dx, dy in parts:
                path = ink.path(name)[0]
                if path is None:
                    continue
                painter.save()
                painter.translate(size / 6.0 + dx * scale, size * 1.1 - dy * scale)
                painter.scale(scale * sx, -scale * sy)
                painter.fillPath(path, QtGui.QBrush(color))
                painter.restore()
        finally:
            painter.end()
        return pixmap

    def sibling(self, recipe):
        """A letter the font has with the same base and a diacritic, to compare (á beside a new ǎ)."""
        base_char = unicodedata.normalize("NFD", recipe.char)[0]
        font = self.font(self.package)
        for code in sorted(font.by_code):
            ch = unichr_(code)
            decomposed = unicodedata.normalize("NFD", ch)
            if len(decomposed) > 1 and decomposed[0] == base_char:
                return font.by_code[code]
        return None

    # -- the reference -------------------------------------------------------------

    def choose_reference(self):
        """The reference font: the one chosen before, else the installed font with the most of the listed
        characters (found once, and remembered)."""
        QtCore, QtGui = _qt()
        family = self.settings.get("reference")
        if not family:
            chars = [r.code for r in self.recipes][:400]
            if not chars:
                return
            self.status.setText(self.status.text + u" Finding the installed font with the most of these "
                                                  u"characters\N{HORIZONTAL ELLIPSIS}")
            QtGui.QApplication.processEvents()
            best, best_count = None, -1
            try:
                installed = set(u"%s" % name for name in QtGui.QFontDatabase().families())
                for name in [f for f in REFERENCE_FAMILIES if f in installed]:
                    metrics = QtGui.QFontMetrics(QtGui.QFont(name))
                    count = sum(1 for code in chars if metrics.inFontUcs4(code))
                    if count > best_count:
                        best, best_count = name, count
            except Exception:
                best = None
            self.fill()  # the status again
            family = best
            if family:
                self.settings["reference"] = family
                write_settings(self.ak, self.settings)
        if family:
            self.choosing_reference = True
            self.reference_font.setCurrentFont(QtGui.QFont(family))
            self.choosing_reference = False
        self.draw_reference(self.selected())

    def reference_changed(self):
        if self.choosing_reference:
            return
        self.settings["reference"] = _property(self.reference_font, "currentFont").family()
        write_settings(self.ak, self.settings)
        self.draw_reference(self.selected())

    def draw_reference(self, r):
        QtCore, QtGui = _qt()
        if r is None or self.package is None:
            self.reference.clear()
            self.reference_note.setText(u"")
            return
        font = QtGui.QFont(_property(self.reference_font, "currentFont"))
        family = font.family()
        if not QtGui.QFontMetrics(font).inFontUcs4(r.code):
            self.reference.clear()
            self.reference_note.setText(u"%s does not have %s." % (family, r.char))
            return
        size = int(REFERENCE_WIDTH * 0.62)
        font.setPixelSize(size)
        path = QtGui.QPainterPath()
        path.addText(QtCore.QPointF(0, 0), font, r.char)
        box = path.boundingRect()
        pixmap = QtGui.QPixmap(REFERENCE_WIDTH, int(size * 1.6))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate((REFERENCE_WIDTH - box.width()) / 2.0 - box.left(), size * 1.15)
            painter.fillPath(path, QtGui.QBrush(self.dialog.palette.color(QtGui.QPalette.WindowText)))
        finally:
            painter.end()
        self.reference.setPixmap(pixmap)
        self.reference_note.setText(u"%s in %s." % (r.char, family))

    # -- the Glyph window ----------------------------------------------------------

    def show_in_glyph_window(self):
        r = self.selected()
        if r is None or self.package is None:
            return
        if not self.in_font(r):
            self.log.add(u"%s is not in the font yet: build it first." % self.ak.b(r.char), "warning")
            return
        contexts = self.ak.proof_contexts(self.package, [r.name])
        text = u"/space".join(u"/%s/%s/%s/%s/%s" % (c, c, r.name, c, c) for c in contexts)
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % self.ak.html(error), "error")

    # -- building -----------------------------------------------------------------

    def build(self):
        QtCore, QtGui = _qt()
        if self.package is None:
            return
        self.harvest()
        chosen = [r for r in self.recipes if not r.missing and r.checked]
        if not chosen:
            return
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed since the list was made: here is this one's. Nothing was built.", "warning")
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
                    checked = r.checked
                    parts, width = place(r, ink, placement, metrics)
                    r.checked = checked
                    if parts is None:
                        continue
                    components = []
                    for name, sx, sy, dx, dy in parts:
                        component = fontlab.GlyphComponent(name)
                        component.transform = QtGui.QTransform(sx, 0.0, 0.0, sy, float(round(dx)), float(round(dy)))
                        components.append(component)
                    layer = glyph.getLayerByName(master, True)
                    layer.setGlyphComponents(components, float(width), package, False)
                touched.append(glyph)
                if is_empty(package.findName(r.name)):
                    raise RuntimeError(u"FontLab left %s empty" % r.name)
                made.append(r.char)
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
        self.ak.notify_changed(fontlab, package, u"FreeLab Diacritics", touched)
        b = self.ak.b
        if made:
            self.log.add(u"Built %s: %s. They are at the end of the font; Edit &gt; Undo takes them back." % (
                b(counted(len(made), u"glyph")), self.ak.html(u"".join(made))), "done")
        else:
            self.log.add(u"Built none.")
        if skipped:
            self.log.add(u"%s had been made meanwhile and %s left as %s." % (
                b(u"".join(skipped)), u"was" if len(skipped) == 1 else u"were",
                u"it was" if len(skipped) == 1 else u"they were"), "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        self.run()

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def _property(widget, name):
    """A Qt property's value (PythonQt gives properties as attributes, some builds as methods)."""
    value = getattr(widget, name)
    return value() if callable(value) else value


def main():
    held = getattr(sys, "_freelab_diacritics", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = AccentsDialog()
    except Exception as exc:
        print("FreeLab Diacritics: %s" % exc)
        return
    sys._freelab_diacritics = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_diacritics":
    main()
