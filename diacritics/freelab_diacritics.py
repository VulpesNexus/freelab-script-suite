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
SCRIPT_MARKS = {("greek", "acute"): (("tonos", "oxia"), 0x0384), ("greek", "grave"): (("varia",), 0x1FEF),
                ("cyrillic", "breve"): (("brevecomb-cy", "breve-cy"), None)}
# Two marks Greek draws as one: the font's glyph for both (by name or code point), or its two marks
# set over each other (the tonos between the dialytika's dots), side by side (a breathing and its
# accent, the breathing first), or one on the other (the perispomeni over a breathing).
JOINED_MARKS = {("greek", (0x0308, 0x0301)): ("dieresistonos", 0x0385, "over"),
                ("greek", (0x0308, 0x0300)): ("dialytikavaria", 0x1FED, "over"),
                ("greek", (0x0308, 0x0342)): ("dialytikaperispomeni", 0x1FC1, "stacked"),
                ("greek", (0x0313, 0x0301)): ("psilioxia", 0x1FCE, "beside"),
                ("greek", (0x0313, 0x0300)): ("psilivaria", 0x1FCD, "beside"),
                ("greek", (0x0313, 0x0342)): ("psiliperispomeni", 0x1FCF, "stacked"),
                ("greek", (0x0314, 0x0301)): ("dasiaoxia", 0x1FDE, "beside"),
                ("greek", (0x0314, 0x0300)): ("dasiavaria", 0x1FDD, "beside"),
                ("greek", (0x0314, 0x0342)): ("dasiaperispomeni", 0x1FDF, "stacked")}
JOINED_GAP_SHARE = 0.025  # the gap between two joined marks, side by side or one on the other, as a share of the em
# A Greek capital's iota subscript is written after it (the prosgegrammeni, an adscript): its glyph,
# by code point or name, else the iota.
ADSCRIPT = ((0x1FBE,), ("prosgegrammeni", "iotaadscript"), 0x03B9)
ADSCRIPT_GAP_SHARE = 0.03  # between a capital and its adscript, as a share of the em
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
          "cedilla": ((0x002C,), 1, False), "commaabove": ((0x2019, 0x0027), 1, False),
          "commareversedabove": ((0x2018,), 1, False), "perispomeni": ((0x007E,), 1, False)}
DRAFT_SPACING = 0.5  # two drafted dots apart by this share of a dot's width
DOTLESS = {u"i": (u"\u0131", ("dotlessi", "idotless")), u"j": (u"\u0237", ("dotlessj", "jdotless", "uni0237")),
           u"\u0456": (u"\u0131", ("dotlessi", "idotless")),  # Cyrillic i and je: the Latin dotless forms
           u"\u0458": (u"\u0237", ("dotlessj", "jdotless", "uni0237"))}
SETS = (("latin", "Latin-1, Latin Extended-A and -B", ((0x00C0, 0x0250),)),
        ("additional", "Latin Extended Additional (Vietnamese, and more)", ((0x1E00, 0x1F00),)),
        ("greek", "Greek", ((0x0370, 0x0400),)),
        ("polytonic", "Greek Extended (polytonic)", ((0x1F00, 0x2000),)),
        ("cyrillic", "Cyrillic", ((0x0400, 0x0530),)),
        ("all", "All", ((0x00C0, 0x0250), (0x1E00, 0x1F00), (0x0370, 0x0400), (0x1F00, 0x2000), (0x0400, 0x0530))))
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
    if code == 0x0345:  # the iota subscript (its combining class, 240, is its own)
        return "below"
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
    """"upper" or "lower"; Greek's capitals with an iota adscript (titlecase letters) are capitals."""
    return "upper" if ch.isupper() or unicodedata.category(ch) == "Lt" else "lower"


def script_of(ch):
    """"greek", "cyrillic", or "latin", by the character's Unicode name."""
    name = unicodedata.name(ch, u"")
    if name.startswith(u"GREEK"):
        return "greek"
    if name.startswith(u"CYRILLIC"):
        return "cyrillic"
    return "latin"


# Scripts whose marks the font's mark features attach (anchors): each one's code point ranges.
ANCHOR_SCRIPTS = (("latin", ((0x0041, 0x0250), (0x0300, 0x0370), (0x1E00, 0x1F00))),
                  ("greek", ((0x0370, 0x0400), (0x1F00, 0x2000))),
                  ("cyrillic", ((0x0400, 0x0530),)),
                  ("hebrew", ((0x0590, 0x0600), (0xFB1D, 0xFB50))),
                  ("arabic", ((0x0600, 0x0700), (0x0750, 0x0780), (0x08A0, 0x0900), (0xFB50, 0xFE00), (0xFE70, 0xFF00))),
                  ("devanagari", ((0x0900, 0x0980), (0xA8E0, 0xA900))),
                  ("bengali", ((0x0980, 0x0A00),)),
                  ("gujarati", ((0x0A80, 0x0B00),)),
                  ("tamil", ((0x0B80, 0x0C00),)),
                  ("thai", ((0x0E00, 0x0E80),)),
                  ("lao", ((0x0E80, 0x0F00),)),
                  ("myanmar", ((0x1000, 0x10A0),)),
                  ("khmer", ((0x1780, 0x1800), (0x19E0, 0x1A00))))


def anchor_script(code):
    """The script of a code point, among ANCHOR_SCRIPTS, or None."""
    for script, ranges in ANCHOR_SCRIPTS:
        for low, high in ranges:
            if low <= code < high:
                return script
    return None


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
        steps, at = [], 0  # each mark's code point, or a pair of them Greek joins
        while at < len(codes):
            pair = tuple(codes[at:at + 2])
            if len(pair) == 2 and (script, pair) in JOINED_MARKS:
                steps.append(pair)
                at += 2
            else:
                steps.append(codes[at])
                at += 1
        for step in steps:
            if isinstance(step, tuple):
                mark = joined_mark(font, script, case, step)
                if mark is None:
                    lacking.append(JOINED_MARKS[(script, step)][0])
                    continue
                left = all(code in LEFT_OF_CAPITALS + (0x0313, 0x0314) for code in step)
            elif step == 0x0345 and script == "greek" and case == "upper":
                mark = adscript_mark(font)
                if mark is None:
                    lacking.append(u"prosgegrammeni")
                    continue
                left = False
            else:
                mark = make_mark(font, step, case, script)
                if mark is None:
                    lacking.append(MARKS.get(step) or u"U+%04X" % step)
                    continue
                left = step in LEFT_OF_CAPITALS
            if script == "greek" and case == "upper" and left:
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


def joined_mark(font, script, case, codes):
    """The Mark for two marks Greek joins: the font's glyph for both, else its two marks joined (over
    each other, side by side, or one on the other); None when it lacks one."""
    name, code, how = JOINED_MARKS[(script, codes)]
    names = [name, glyph_names().get(code)]
    if case == "upper":
        names = [n + u".case" for n in names if n] + names
    glyph = next((n for n in names if n and n in font.names), None) or font.by_code.get(code)
    if glyph:
        return Mark(name, "above", [(glyph, 1.0, 1.0, 0.0, 0.0)])
    parts = [make_mark(font, c, case, script) for c in codes]
    if any(part is None for part in parts):
        return None
    note = {"over": u"its marks set over each other", "beside": u"its marks side by side",
            "stacked": u"one mark on the other"}[how]
    return Mark(name, "above", [part.parts[0] for part in parts], note, joined=how)


def adscript_mark(font):
    """The Mark of a Greek capital's iota adscript, after the letter: the font's prosgegrammeni, or its
    iota; None when it has neither."""
    codes, names, iota = ADSCRIPT
    glyph = next((font.by_code[c] for c in codes if c in font.by_code), None)
    glyph = glyph or next((n for n in names if n in font.names), None) or font.by_code.get(iota)
    if glyph is None:
        return None
    return Mark("prosgegrammeni", "adscript", [(glyph, 1.0, 1.0, 0.0, 0.0)],
                None if glyph != font.by_code.get(iota) else u"the iota, as an adscript")


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
    gap = JOINED_GAP_SHARE * placement.upm
    for (glyph, sx, sy, _, _), ink in zip(mark.parts, inks):
        sx, sy = sx * scale, sy * scale
        if mark.joined == "stacked" and laid:  # on the first: centered over it
            first, (_, fsx, fsy, fx, fy) = inks[0], laid[0]
            center = fx + fsx * (first.left + first.right) / 2.0
            laid.append((glyph, sx, sy, center - sx * (ink.left + ink.right) / 2.0,
                         fy + fsy * first.top + gap - sy * ink.bottom))
            continue
        if mark.joined == "beside" and laid:  # after the first, a little apart, their bottoms level
            first, (_, fsx, fsy, fx, fy) = inks[0], laid[0]
            laid.append((glyph, sx, sy, fx + fsx * first.right + gap - sx * ink.left,
                         fy + fsy * first.bottom - sy * ink.bottom))
            continue
        if mark.joined in (True, "over"):  # over each other: centered on the first, their bottoms level
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
    adscript = 0
    for mark in recipe.marks:
        box, laid = mark_ink(mark, ink_of, placement, case)
        if box is None:
            return None, None, None, 0
        side = mark.side
        if side == "adscript":  # after a Greek capital, on the baseline
            gap = ADSCRIPT_GAP_SHARE * placement.upm
            start = base.advance + gap
            for glyph, sx, sy, x, yy in laid:
                parts.append((glyph, sx, sy, round(x - box.left + start), round(yy - box.bottom + base.bottom)))
            adscript = gap + box.width + max(base.left, 0)
            continue
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
    return parts, top, bottom, widen + int(round(adscript))


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
# Mark anchors (scripts whose marks the font's mark features attach)
# ---------------------------------------------------------------------------

ANCHOR_MODEL_FILE = "anchor_model.json"
ANCHOR_BLOCK = "anchors"
ANCHOR_BEGIN, ANCHOR_END = u"# >>> FreeLab %s (made by FreeLab Diacritics)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
MARK_FEATURES = {"mark": "Mark Positioning", "mkmk": "Mark to Mark Positioning",
                 "ccmp": "Glyph Composition/Decomposition", "pres": "Pre-base Substitutions"}
CODE_FEATURES = ("ccmp", "pres", "mark", "mkmk")  # the features the Mark anchors tab writes, in this order
DEFAULT_ANCHOR = {"base_gap": 0.0, "base_offset": 0.0, "mark_gap": 0.06, "mark_offset": 0.0, "mark_to_mark": 0.01}


def load_anchor_model(path=None):
    """The corpus's anchor placements (anchor_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), ANCHOR_MODEL_FILE)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class AnchorGlyph(object):
    """A base or a mark of a script, with the anchors to add ({name: (x, y)}) and those it has."""

    def __init__(self, name, code, role, ink, existing=None, parts=0):
        self.name, self.code, self.role, self.ink = name, code, role, ink  # ink: an Ink
        self.parts = parts  # a ligature's letters
        self.existing = dict(existing or {})
        self.anchors = {}  # name: (x, y), the ones to add
        self.adjust = {}  # name: [dx, dy], moved by hand
        self.side = None  # a mark's side: "top" or "bottom"
        self.checked = True

    def placed(self):
        """{name: (x, y)} of every anchor it will have: its own and those to add, as moved by hand."""
        found = {}
        for name, (x, y) in list(self.existing.items()) + list(self.anchors.items()):
            dx, dy = self.adjust.get(name, (0, 0))
            found[name] = (round(x + dx), round(y + dy))
        return found

    def moved(self):
        """The names of the anchors it has that were moved by hand (to move when written)."""
        return sorted(name for name in self.existing if name not in self.anchors and name in self.adjust)

    def pending(self):
        """Whether writing it would change the font: anchors to add, or its own moved."""
        return bool(self.anchors) or bool(self.moved())


MIN_ROW_FONTS = 3  # a script's anchor medians from fewer fonts than this give way to Latin's


def anchor_row(model, script, side):
    row = dict(DEFAULT_ANCHOR)
    anchors = model.get("anchors", {})
    found = anchors.get(u"%s %s" % (script, side))
    if not found or found.get("fonts", 0) < MIN_ROW_FONTS:
        found = anchors.get(u"latin %s" % side)
    row.update(found or {})
    return row


_ROOTS = []
COMPOSED_SCRIPTS = ("latin", "greek", "cyrillic")  # Unicode precomposes their letters with marks widely


def composing_roots():
    """The code points Unicode composes letters with marks on: the first of each canonical
    decomposition (the Basic Multilingual Plane's) whose rest are marks, all the way down (a for the
    letters with dieresis and macron, not a with dieresis), and the dotless i and j that take marks above."""
    if not _ROOTS:
        found = set([0x0131, 0x0237])
        for code in range(0x00C0, 0xFFFF):
            if 0xD800 <= code < 0xE000:
                continue
            ch = unichr_(code)
            decomposition = unicodedata.decomposition(ch)
            if not decomposition or decomposition.startswith(u"<"):
                continue
            parts = unicodedata.normalize("NFD", ch)
            if len(parts) > 1 and all(unicodedata.category(c).startswith("M") for c in parts[1:]):
                found.add(ord(parts[0]))
        _ROOTS.append(found)
    return _ROOTS[0]


def base_letters(script, model):
    """The code points of a script's letters that take marks, or None (any letter): those Unicode
    composes with marks, and those the corpus's fonts of the script attach marks to (save letters
    Unicode has precomposed: their marks are built in)."""
    roots = set(code for code in composing_roots() if anchor_script(code) == script)
    corpus = set()
    for text in model.get("bases", {}).get(script, ()):
        code = int(text, 16)
        if code <= 0xFFFF and unicodedata.normalize("NFD", unichr_(code)) == unichr_(code):
            corpus.add(code)
    if not corpus and script not in COMPOSED_SCRIPTS:
        return None  # a few compositions (Myanmar's) do not say which of its letters take marks
    found = roots | corpus
    return found or None


def mark_side_of(ink, x_height):
    """Where a mark goes, by its ink: above when its middle is at least halfway up the x-height."""
    return "top" if (ink.bottom + ink.top) / 2.0 >= 0.5 * x_height else "bottom"


# Marks that attach elsewhere than over or under the letter's middle, by code point, as most of the
# corpus's Hebrew fonts set them (27 of its 30 Hebrew families attach their points): the dagesh (and
# mapiq) inside the letter; the holam and the sin dot at its top left, the shin dot at shin's top right;
# of the cantillation marks (10 families have them), pashta and telisha qetana at the top left, yetiv
# and dehi at the bottom right.
MARK_CLASSES = {0x05BC: "center", 0x05B9: "topleft", 0x05BA: "topleft", 0x05C2: "topleft", 0x05C1: "topright",
                0x0599: "topleft", 0x05A9: "topleft", 0x059A: "bottomright", 0x05AD: "bottomright"}
SIDE_FAMILY = {"topleft": "top", "topright": "top", "bottomright": "bottom", "center": "center"}
SIDE_BASES = {"topright": (0x05E9,)}  # a side only these letters (and their forms) take: the shin dot's, shin


def anchor_side(code, ink, x_height):
    """Where a mark goes: its class (MARK_CLASSES), else above or below by its ink (top, bottom)."""
    return MARK_CLASSES.get(code) or mark_side_of(ink, x_height)


LETTER_HEIGHT_FROM_SCRIPT = ("latin",)  # per-letter placement across only: heights by the script's rule
# The marks whose landing on each letter the corpus's per-letter placements are (diacritics/train/shaped.py
# samples them), per script and side: a base's anchor is set so that this mark lands there, the others
# then sitting as their own anchors say (Thai's right-aligned)
SAMPLE_MARKS = {"latin": {"top": 0x0301, "bottom": 0x0323}, "greek": {"top": 0x0301},
                "cyrillic": {"top": 0x0301, "bottom": 0x0323},
                "hebrew": {"top": 0x05BF, "bottom": 0x05B7, "center": 0x05BC, "topleft": 0x05B9, "topright": 0x05C1},
                "arabic": {"top": 0x064E, "bottom": 0x0650}, "devanagari": {"top": 0x0902, "bottom": 0x0941},
                "bengali": {"top": 0x0981, "bottom": 0x09C1}, "gujarati": {"top": 0x0A82, "bottom": 0x0AC1},
                "tamil": {"top": 0x0BCD}, "thai": {"top": 0x0E48, "bottom": 0x0E38},
                "lao": {"top": 0x0EC8, "bottom": 0x0EB8}, "myanmar": {"top": 0x1036, "bottom": 0x102F},
                "khmer": {"top": 0x17B7, "bottom": 0x17BB}}


def letter_row(model, script, side, code):
    """(share across, gap) where the corpus's fonts land a mark on this letter (shaped.py), or None; for
    the center (a dagesh), (share across, share up) of the letter's ink."""
    if not code:
        return None
    entry = model.get("letters", {}).get(u"%s %s" % (script, side), {}).get(u"%04X" % code)
    if not entry or len(entry) < 3 or entry[2] < MIN_ROW_FONTS:
        return None
    return entry[0], entry[1]


def side_row(model, script, side):
    """The median, over the script's letters, of where the corpus's fonts land a mark of this side (for a
    letter the corpus has too little of), or None."""
    rows = [entry for entry in model.get("letters", {}).get(u"%s %s" % (script, side), {}).values()
            if len(entry) >= 3 and entry[2] >= MIN_ROW_FONTS]
    if not rows:
        return None
    return median([entry[0] for entry in rows]), median([entry[1] for entry in rows])


# Scripts whose ra and virama before a consonant make a reph over it: (ra, virama, a consonant to show it on)
REPH_SCRIPTS = {"devanagari": (0x0930, 0x094D, 0x0915), "bengali": (0x09B0, 0x09CD, 0x0995),
                "gujarati": (0x0AB0, 0x0ACD, 0x0A95)}


def reph_row(model, script):
    """{"share", "gap", "fonts"}: where the corpus's fonts of a script land the reph, or None."""
    found = model.get("reph") or {}
    if "share" in found:  # (the first models: Devanagari's only)
        return found if script == "devanagari" else None
    return found.get(script)


def ligature_point(model, script, side, ink, part, parts, upm):
    """Where a ligature's part takes a mark (part 1 is read first: the right one, in Arabic): two-part
    ligatures as the corpus's set theirs, others split evenly."""
    learned = model.get("ligature", {}).get(side)
    if parts == 2 and learned and len(learned) == 2:
        share, gap = learned[part - 1]
    else:
        share, gap = 1.0 - (part - 0.5) / parts, anchor_row(model, script, side)["base_gap"]
    x = ink.left + share * ink.width
    return (x, ink.top + gap * upm) if side == "top" else (x, ink.bottom - gap * upm)


def base_point(model, script, side, code, ink, upm, widths):
    """(x, y) of a base's anchor of a side: where the corpus's fonts land a mark on this letter (the mark's
    ink there, so the anchor sits as far off it as the mark's own anchor sits off the mark's ink), else by
    the script's rule: over (under) the center of the ink's top (bottom) fifth; a corner's at the ink's
    left or right end; the center's in the middle of the ink, as the script's letters take it."""
    family = SIDE_FAMILY.get(side, side)
    learned = letter_row(model, script, side, code)
    if family == "center":
        learned = learned or side_row(model, script, side)
        share, up = learned if learned is not None else (0.5, 0.5)
        return ink.left + share * ink.width, ink.bottom + up * (ink.top - ink.bottom)
    row = anchor_row(model, script, family)
    if side != family:  # a corner (the holam's): the mark's own anchor is under (over) its ink's center
        learned = learned or side_row(model, script, side)
        share, gap = learned if learned is not None else (1.0 if side.endswith(u"right") else 0.0, None)
        lift = (gap - row["mark_gap"]) * upm if gap is not None else row["base_gap"] * upm
        x = ink.left + share * ink.width
        return (x, ink.top + lift) if family == "top" else (x, ink.bottom - lift)
    if learned is not None:  # the mark's ink lands there: its own anchor sits mark_offset and mark_gap off it
        share, gap = learned
        x = ink.left + share * ink.width + row["mark_offset"] * widths.get(side, 0.0)
        # (Latin's heights: its script's rule, which landed marks closer, by a leave-one-font-out test)
        lift = (gap - row["mark_gap"]) * upm if script not in LETTER_HEIGHT_FROM_SCRIPT else row["base_gap"] * upm
        return (x, ink.top + lift) if side == "top" else (x, ink.bottom - lift)
    if side == "top":
        return ink.top_center + row["base_offset"] * ink.width, ink.top + row["base_gap"] * upm
    return ink.bottom_center + row["base_offset"] * ink.width, ink.bottom - row["base_gap"] * upm


def plan_anchors(glyphs, model, script, upm, x_height):
    """AnchorGlyphs with their anchors to add: bases get top and bottom, each mark the anchor it
    attaches by (_top or _bottom) and the one the next mark attaches to (top or bottom), a ligature
    top_1, bottom_1, top_2, and so on (one pair per letter it joins), a reph _reph and every base a
    reph anchor. Marks of other classes (MARK_CLASSES: Hebrew's dagesh, center; its holam, topleft) take
    that anchor alone, and the bases one for it (shin alone a topright, for the shin dot). glyphs: [(name,
    code, "base", "mark", "ligature" or "reph", Ink, {existing anchor: (x, y)}[, letters joined])].
    Anchors the glyph has already are kept as they are. A base's anchor sits where the corpus's fonts
    land a mark on that letter (shaped.py, all their means at once: a Thai mark beside po pla's
    ascender), else by its script's rule (base_point); a mark's under (over) its ink's center."""
    upm = float(upm)
    planned = []
    rows = [tuple(entry) + (0,) * (6 - len(entry)) for entry in glyphs]
    marks, sampled = {}, {}
    samples = SAMPLE_MARKS.get(script, {})
    for name, code, role, ink, existing, parts in rows:  # marks first: their sides and widths place the bases'
        if role == "mark" and ink is not None and ink.width > 0:
            side = anchor_side(code, ink, x_height)
            marks.setdefault(side, []).append(ink.width)
            if code == samples.get(side) and u"." not in name:  # the mark whose landing the letters' placements are
                sampled[side] = ink.width
    widths = dict((side, sampled.get(side, median(found))) for side, found in marks.items())
    special = sorted(side for side in marks if side in SIDE_FAMILY)  # the sides besides top and bottom the marks take
    has_reph = any(row[2] == "reph" for row in rows)
    reph = reph_row(model, script)
    for name, code, role, ink, existing, parts in rows:
        if ink is None or ink.width <= 0:
            continue
        g = AnchorGlyph(name, code, role, ink, existing, parts)
        if role == "base":
            for side in ["top", "bottom"] + [s for s in special if s not in SIDE_BASES or code in SIDE_BASES[s]]:
                point = base_point(model, script, side, code, ink, upm, widths)
                if side not in g.existing:
                    g.anchors[side] = (round(point[0]), round(point[1]))
            if has_reph and reph and "reph" not in g.existing:
                g.anchors[u"reph"] = (round(ink.left + reph["share"] * ink.width), round(ink.top + reph["gap"] * upm))
        elif role == "ligature":
            for part in range(1, max(parts, 2) + 1):
                for side in ("top", "bottom"):
                    anchor = u"%s_%d" % (side, part)
                    if anchor not in g.existing:
                        x, y = ligature_point(model, script, side, ink, part, max(parts, 2), upm)
                        g.anchors[anchor] = (round(x), round(y))
        elif role == "reph":
            g.side = u"reph"
            if u"_reph" not in g.existing:  # the reph's ink lands at the base's reph anchor, its bottom center there
                g.anchors[u"_reph"] = (round(ink.center), round(ink.bottom))
        else:
            side = g.side = anchor_side(code, ink, x_height)
            family = SIDE_FAMILY.get(side, side)
            points = []
            if family == "center":  # its ink's center meets the base's center anchor
                points.append((u"_" + side, (ink.center, (ink.bottom + ink.top) / 2.0)))
            elif side != family:  # at a letter's corner: centered on its ink; nothing stacks on it
                row = anchor_row(model, script, family)
                gap = row["mark_gap"] * upm
                points.append((u"_" + side, (ink.center, ink.bottom - gap if family == "top" else ink.top + gap)))
            else:
                row = anchor_row(model, script, side)
                x = ink.center + row["mark_offset"] * ink.width
                if side == "top":
                    points += [(u"_top", (x, ink.bottom - row["mark_gap"] * upm)),
                               (u"top", (x, ink.top + row["mark_to_mark"] * upm))]
                else:
                    points += [(u"_bottom", (x, ink.top + row["mark_gap"] * upm)),
                               (u"bottom", (x, ink.bottom - row["mark_to_mark"] * upm))]
            for anchor, point in points:
                if anchor not in g.existing:
                    g.anchors[anchor] = (round(point[0]), round(point[1]))
        if g.anchors:
            planned.append(g)
        else:
            g.checked = False
            planned.append(g)
    return planned


# Thai: the corpus's convention (25 of its 27 Thai families): a tone mark after a mark above takes its
# smaller form; yo ying, tho than, do chada, to patak, ru, and lu their forms without the part a vowel
# below would meet; lo chula its shorter form under a mark above. (Their narrower marks for po pla's
# ascender are left out: anchors set each mark beside it already.)
THAI_ABOVE = (0x0E31, 0x0E34, 0x0E35, 0x0E36, 0x0E37, 0x0E47, 0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C, 0x0E4D, 0x0E4E)
THAI_BELOW = (0x0E38, 0x0E39, 0x0E3A)
THAI_TONES = (0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C)
THAI_SHORTENED = ((0x0E0D, ("less", "short")), (0x0E10, ("less", "short")), (0x0E0E, ("short", "less")),
                  (0x0E0F, ("short", "less")), (0x0E24, ("short",)), (0x0E26, ("short",)))
THAI_LO_CHULA = 0x0E2C
I_MATRA = 0x093F
DEVANAGARI_CONSONANTS = tuple(range(0x0915, 0x093A))
# The pre-base i-matra and the consonants it goes before, per script: several fonts draw it in lengths
# whose hook reaches into the consonant (Devanagari's, 30 fonts; Gujarati's, 11 of the corpus's 12
# Gujarati families; Bengali's, 6 of 11, for its longer consonants)
I_MATRAS = {"devanagari": (I_MATRA, DEVANAGARI_CONSONANTS),
            "bengali": (0x09BF, tuple(range(0x0995, 0x09BA)) + (0x09DC, 0x09DD, 0x09DF)),
            "gujarati": (0x0ABF, tuple(range(0x0A95, 0x0ABA)))}
NOMINAL_SHARE = 0.5  # a consonant most of the corpus's fonts keep their nominal i-matra before gets no rule
LIGATURE_FORMS = (u"<isolated>", u"<final>", u"<initial>", u"<medial>")
# Glyphs' names for the letters whose forms the rules look for (GlyphData.xml, MIT License: see
# GlyphData_LICENSE): a form is found by its letter's font name, this one (or with another common tag
# of its script: iMatra-gujr for iMatra-gujarati), or uniXXXX, case and hyphens aside (yoYing-thai.less,
# yoYingthai.less, uni0E0D.less)
NICE_NAMES = {0x0E0D: u"yoYing-thai", 0x0E0E: u"doChada-thai", 0x0E0F: u"toPatak-thai", 0x0E10: u"thoThan-thai",
              0x0E24: u"ru-thai", 0x0E26: u"lu-thai", 0x0E2C: u"loChula-thai", 0x0E48: u"maiEk-thai",
              0x0E49: u"maiTho-thai", 0x0E4A: u"maiTri-thai", 0x0E4B: u"maiChattawa-thai", 0x0E4C: u"thanthakhat-thai",
              0x093F: u"iMatra-deva", 0x09BF: u"iMatra-beng", 0x0ABF: u"iMatra-gujarati"}
# The tags fonts name a script's glyphs with (Glyphs' first: -hb, -deva, -beng, -gujarati, -tamil)
SCRIPT_TAGS = {"hebrew": (u"hb", u"hebr", u"hebrew"), "devanagari": (u"deva", u"dv", u"dev", u"devanagari"),
               "bengali": (u"beng", u"bn", u"bng", u"bengali", u"bangla"),
               "gujarati": (u"gujarati", u"gujr", u"gj", u"guj"), "tamil": (u"tamil", u"taml", u"tml"),
               "thai": (u"thai",)}


def _plain(name):
    return name.lower().replace(u"-", u"")


def nice_names(code):
    """Glyphs' name for a code point (NICE_NAMES, else glyph_names.json), and the same with each other
    common tag of its script (iMatra-gujarati, iMatra-gujr, iMatra-gj, iMatra-guj)."""
    nice = NICE_NAMES.get(code) or glyph_names().get(code)
    if not nice:
        return []
    found = [nice]
    stem, dash, tag = nice.rpartition(u"-")
    if dash:
        for tags in SCRIPT_TAGS.values():
            if tag in tags:
                found += [u"%s-%s" % (stem, other) for other in tags if other != tag]
    return found


def forms_of(names, base, code):
    """{suffix: glyph name} of the font's forms of a letter: glyphs named after it, a period, and a suffix."""
    stems = set(_plain(stem) for stem in [base, u"uni%04X" % code] + nice_names(code) if stem)
    found = {}
    for name in sorted(names):
        stem, dot, suffix = name.partition(u".")
        if dot and suffix and _plain(stem) in stems:
            found.setdefault(suffix, name)
    return found


class Rule(object):
    """A substitution the Mark anchors tab writes: its feature, the form it puts in (name), its line of
    code, when it applies (text), and a sample to draw in the reference font."""
    role = "rule"

    def __init__(self, feature, name, line, text, sample=u""):
        self.feature, self.name, self.line, self.text, self.sample = feature, name, line, text, sample
        self.code, self.parts, self.checked, self.side, self.ink = 0, 0, True, None, None
        self.anchors, self.existing, self.adjust = {}, {}, {}

    def placed(self):
        return {}


def thai_rules(names_by_code, names):
    """Rules for the Thai forms the font has (by its glyphs' names: uni0E48.small, maiek-thai.small)."""
    def form(code, suffixes):
        base = names_by_code.get(code)
        forms = forms_of(names, base, code) if base else {}
        for suffix in suffixes:
            if suffix in forms:
                return forms[suffix]
        return None
    found = []
    below = [names_by_code[c] for c in THAI_BELOW if c in names_by_code]
    above = [names_by_code[c] for c in THAI_ABOVE if c in names_by_code]
    if below:
        for code, suffixes in THAI_SHORTENED:
            short = form(code, suffixes)
            if short:
                found.append(Rule("ccmp", short, u"sub %s' [%s] by %s;" % (names_by_code[code], u" ".join(below), short),
                                  u"before a vowel below", unichr_(code) + unichr_(THAI_BELOW[0])))
    if above:
        for code in THAI_TONES:
            small = form(code, ("small",))
            if small:
                found.append(Rule("ccmp", small, u"sub [%s] %s' by %s;" % (u" ".join(above), names_by_code[code], small),
                                  u"after a mark above", u"\u0E01\u0E34" + unichr_(code)))
        short = form(THAI_LO_CHULA, ("short",))
        if short:
            found.append(Rule("ccmp", short, u"sub %s' [%s] by %s;" % (names_by_code[THAI_LO_CHULA], u" ".join(above), short),
                              u"under a mark above", unichr_(THAI_LO_CHULA) + u"\u0E48"))
    return found


def i_matra_variants(names, nominal, code):
    """The font's other i-matras: glyphs named after the nominal one (uni093F.01, iMatra-deva.a03, gjmI.alt02),
    or its name with other digits (MatraI3.gj for MatraI.gj, ivowelsign2gujr for ivowelsigngujr; not for a
    uniXXXX name, whose digits are its code point); none joined with another glyph (_)."""
    import re
    found = set(forms_of(names, nominal, code).values())
    if not re.match(u"^uni[0-9A-Fa-f]{4}", nominal):
        key = re.sub(u"[0-9]+", u"", nominal.lower())
        found.update(n for n in names if n != nominal and re.sub(u"[0-9]+", u"", n.lower()) == key)
    return sorted(n for n in found if u"_" not in n and n != nominal)


def i_matra_rules(names_by_code, names, reach_of, advance_of, model, script="devanagari"):
    """Rules picking, before each consonant, the i-matra whose hook reaches into it as far as the
    corpus's fonts reach into that consonant (a share of its advance), among the font's i-matras
    (i_matra_variants); none before a consonant most of those fonts keep their nominal i-matra before
    (Bengali's shorter consonants). reach_of(name): how far a glyph's ink reaches past its advance;
    advance_of(name): its advance; both None for a glyph not drawn."""
    matra, consonants = I_MATRAS.get(script, (None, ()))
    nominal = names_by_code.get(matra) if matra else None
    if not nominal:
        return []
    encoded = set(names_by_code.values())
    candidates = [nominal] + [n for n in i_matra_variants(names, nominal, matra) if n not in encoded]
    if len(candidates) < 2:
        return []
    reaches = dict((n, reach_of(n)) for n in candidates)
    reaches = dict((n, r) for n, r in reaches.items() if r is not None)
    if nominal not in reaches or len(reaches) < 2:
        return []
    groups = {}
    for code in consonants:
        consonant, learned = names_by_code.get(code), model.get("i_matra", {}).get(u"%04X" % code)
        advance = advance_of(consonant) if consonant else None
        if not consonant or not learned or not advance or (len(learned) > 2 and learned[2] > NOMINAL_SHARE):
            continue
        target = learned[0] * advance
        best = min(sorted(reaches), key=lambda n: abs(reaches[n] - target))
        if best != nominal:
            groups.setdefault(best, []).append((code, consonant))
    found = []
    for variant in sorted(groups):
        members = groups[variant]
        found.append(Rule("pres", variant, u"sub %s' [%s] by %s;" % (nominal, u" ".join(n for _, n in members), variant),
                          u"before %s" % u" ".join(unichr_(c) for c, _ in members),
                          unichr_(members[0][0]) + unichr_(matra)))
    return found


def ligature_parts(name, code, arabic_names):
    """How many letters an Arabic ligature glyph joins (0 for none): by its Unicode decomposition
    (lam with alef, U+FEFB, joins 2), its uniXXXXYYYY name, or its name's parts (lam_alef-ar: lam-ar and
    alef-ar, among the font's Arabic letters)."""
    if code:
        decomposition = unicodedata.decomposition(unichr_(code))
        if not decomposition.startswith(LIGATURE_FORMS):
            return 0
        letters = [p for p in decomposition.split()[1:]
                   if unicodedata.category(unichr_(int(p, 16))).startswith(u"L")]
        return len(letters) if len(letters) >= 2 else 0
    stem = name.split(u".")[0]
    if stem.startswith(u"uni") and len(stem) >= 11 and (len(stem) - 3) % 4 == 0:
        try:
            codes = [int(stem[i:i + 4], 16) for i in range(3, len(stem), 4)]
        except ValueError:
            codes = []
        if codes and all(anchor_script(c) == "arabic" and unicodedata.category(unichr_(c)).startswith(u"L") for c in codes):
            return len(codes)
        return 0
    if u"_" not in stem:
        return 0
    parts = stem.split(u"_")
    suffix = u""
    for mark in (u"-ar", u"-arab"):
        if parts[-1].endswith(mark):
            suffix = mark
    named = [part if (not suffix or part.endswith(suffix)) else part + suffix for part in parts]
    return len(named) if len(named) >= 2 and all(part in arabic_names for part in named) else 0


def name_script(name):
    """The reph script a glyph's name names, by its tag (Reph.bn, gjReph, rephdeva, reph-gujarati) or its
    code points (uni09B009CD), or None."""
    import re
    lowered = name.lower()
    codes = re.findall(u"(?:uni|u)([0-9a-f]{4})", lowered)
    for code in codes:
        script = anchor_script(int(code, 16))
        if script:
            return script
    words = [w for w in re.split(u"[._-]", lowered) if w]
    for script, tags in sorted(SCRIPT_TAGS.items()):
        for word in words:
            core = word.replace(u"reph", u"") if u"reph" in word else word
            if core in tags:
                return script
    return None


def is_reph(name, script=None):
    """A reph's glyph (rephdeva, Reph.dv, dvReph, uni0930094D.rphf, Reph.bn, gjReph, reph-gujarati, and ra and
    virama by their code points, uni09B009CD), not one joined with a matra, a vowel sign, or a bindu
    (bSignIiReph, ivowelsignrephgujr, gjmII_Reph), nor Marathi's eyelash ra; of the given script, when given, unless its name names another."""
    import re
    lowered = name.lower()
    named = name_script(name)
    if script is not None and named is not None and named != script:
        return False
    if lowered.endswith(u".rphf"):
        return True
    stem = lowered.split(u".")[0]
    for ra, virama, _ in REPH_SCRIPTS.values():
        if stem == u"uni%04x%04x" % (ra, virama):
            return True
    if u"reph" not in stem or any(w in lowered for w in (u"matra", u"anusvara", u"bindu", u"candra", u"eyelash", u"sign",
                                                         u"vowel", u"mark")):
        return False
    tags = set(tag for tags in SCRIPT_TAGS.values() for tag in tags)
    # joined with something else (gjmII_Reph: the ii-matra and the reph), not a script tag (bn_reph) or an alternate's
    return all(u"reph" in part or part.split(u"-")[0] in tags or re.match(u"^alt[0-9]*$", part)
               for part in stem.split(u"_"))


def mark_code(glyphs):
    """{"mark": [lines], "mkmk": [lines]} attaching the marks to the bases and to each other, from every
    anchor the glyphs will have (only checked glyphs, and glyphs with anchors of their own)."""
    marks = [g for g in glyphs if g.role in ("mark", "reph") and (g.checked or g.existing)]
    bases = [g for g in glyphs if g.role == "base" and (g.checked or g.existing)]
    ligatures = [g for g in glyphs if g.role == "ligature" and (g.checked or g.existing)]
    classes = {}
    lines = {"mark": [], "mkmk": []}
    for g in sorted(marks, key=lambda g: g.name):
        for name, (x, y) in sorted(g.placed().items()):
            if name.startswith(u"_"):
                side = name[1:]
                classes.setdefault(side, []).append(g.name)
                lines["mark"].append(u"markClass %s <anchor %d %d> @MC_%s;" % (g.name, x, y, side))
    for g in sorted(bases, key=lambda g: g.name):
        placed = g.placed()
        attach = [u"<anchor %d %d> mark @MC_%s" % (placed[side][0], placed[side][1], side)
                  for side in sorted(classes) if side in placed]
        if attach:
            lines["mark"].append(u"pos base %s %s;" % (g.name, u" ".join(attach)))
    for g in sorted(ligatures, key=lambda g: g.name):
        placed = g.placed()
        components = []
        for part in range(1, max(g.parts, 2) + 1):
            attach = [u"<anchor %d %d> mark @MC_%s" % (placed[u"%s_%d" % (side, part)][0], placed[u"%s_%d" % (side, part)][1], side)
                      for side in sorted(classes) if side != u"reph" and u"%s_%d" % (side, part) in placed]
            components.append(u" ".join(attach) if attach else u"<anchor NULL>")
        if any(c != u"<anchor NULL>" for c in components):
            lines["mark"].append(u"pos ligature %s %s;" % (g.name, u" ligComponent ".join(components)))
    for g in sorted(marks, key=lambda g: g.name):
        if g.role == "reph":
            continue  # nothing attaches to the reph
        placed = g.placed()
        attach = [u"<anchor %d %d> mark @MC_%s" % (placed[side][0], placed[side][1], side)
                  for side in sorted(classes) if side in placed]
        if attach:
            lines["mkmk"].append(u"pos mark %s %s;" % (g.name, u" ".join(attach)))
    return lines


def freelab_feature(tag, old, lines, block=ANCHOR_BLOCK, titles=MARK_FEATURES):
    """A feature's code with FreeLab's block (lines) before its closing line: an older FreeLab block
    taken out, the rest kept, FontLab's automatic block handed back ("#/> feature")."""
    import re
    begin, end = ANCHOR_BEGIN % block, ANCHOR_END % block
    kept, inside = [], False
    for line in (old or u"").splitlines():
        stripped = line.strip()
        if stripped == begin:
            inside = True
            continue
        if stripped == end:
            inside = False
            continue
        if inside:
            continue
        if stripped.startswith(FONTLAB_AUTO):
            line = line.replace(FONTLAB_AUTO, FONTLAB_HANDED, 1)
        kept.append(line)
    closing = None
    for index in range(len(kept) - 1, -1, -1):
        if re.match(r"^\s*}\s*%s\s*;" % re.escape(tag), kept[index]):
            closing = index
            break
    if closing is None:
        kept = [u"feature %s {" % tag, u"# %s" % titles.get(tag, tag), u""]
        closing = len(kept)
        kept.append(u"} %s;" % tag)
    body = [begin] + [u"  %s" % line for line in lines] + [end] if lines else []
    return u"\n".join(kept[:closing] + body + kept[closing:]) + u"\n"


def mark_texts(glyphs, old_texts):
    """{tag: new code} for mark and mkmk, and the substitutions' features (ccmp, pres) (a feature with
    nothing of FreeLab's and nothing to add is left out)."""
    lines = mark_code(glyphs)
    for rule in glyphs:
        if rule.role == "rule":
            lines.setdefault(rule.feature, [])
            if rule.checked:
                lines[rule.feature].append(rule.line)
    new = {}
    for tag in CODE_FEATURES:
        old = old_texts.get(tag)
        if lines.get(tag) or (ANCHOR_BEGIN % ANCHOR_BLOCK) in (old or u""):
            new[tag] = freelab_feature(tag, old, lines.get(tag, []))
    return new


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


def has_character(family, code):
    """Whether an installed font family itself has a character: QRawFont reads the family's own font
    (QFontMetrics.inFontUcs4 answers for Windows' fallback fonts too, and drew another font's glyph
    as the chosen one's)."""
    QtCore, QtGui = _qt()
    font = QtGui.QFont(family)
    try:
        if u"%s" % QtGui.QFontInfo(font).family() != u"%s" % family:
            return False  # not installed: Qt picked another
    except Exception:
        pass
    try:
        raw = QtGui.QRawFont.fromFont(font)
        valid = raw.isValid
        if valid() if callable(valid) else valid:
            return bool(raw.supportsCharacter(code))
    except Exception:
        pass
    try:
        return bool(QtGui.QFontMetrics(font).inFontUcs4(code))
    except Exception:
        return False


# Families with other scripts' letters and marks (Windows' own, then Google's Noto): a reference for them
SCRIPT_FAMILIES = {"arabic": ("Noto Naskh Arabic", "Noto Sans Arabic", "Segoe UI", "Arial", "Tahoma"),
                   "hebrew": ("Noto Serif Hebrew", "Noto Sans Hebrew", "Frank Ruhl Libre", "David", "Segoe UI", "Arial",
                              "Tahoma"),
                   "bengali": ("Noto Sans Bengali", "Noto Serif Bengali", "Hind Siliguri", "Nirmala UI", "Vrinda"),
                   "gujarati": ("Noto Sans Gujarati", "Noto Serif Gujarati", "Hind Vadodara", "Nirmala UI", "Shruti"),
                   "tamil": ("Noto Sans Tamil", "Noto Serif Tamil", "Hind Madurai", "Nirmala UI", "Latha"),
                   "devanagari": ("Noto Sans Devanagari", "Noto Serif Devanagari", "Nirmala UI", "Mangal"),
                   "thai": ("Noto Sans Thai", "Noto Serif Thai", "Leelawadee UI", "Tahoma"),
                   "lao": ("Noto Sans Lao", "Leelawadee UI"),
                   "khmer": ("Noto Sans Khmer", "Noto Serif Khmer", "Khmer UI", "Leelawadee UI"),
                   "myanmar": ("Noto Sans Myanmar", "Myanmar Text")}
DOTTED_CIRCLE = 0x25CC  # what a mark is drawn on without a letter


def script_families(script):
    return SCRIPT_FAMILIES.get(script, ())


def reference_picture(text, family, palette):
    """text drawn in a font family, centered in the reference column (made smaller to fit across), in
    the dialog's text color."""
    QtCore, QtGui = _qt()
    font = QtGui.QFont(family)
    size = int(REFERENCE_WIDTH * 0.62)
    font.setPixelSize(size)
    path = QtGui.QPainterPath()
    path.addText(QtCore.QPointF(0, 0), font, text)
    box = path.boundingRect()
    scale = min(1.0, REFERENCE_WIDTH * 0.92 / box.width()) if box.width() > 0 else 1.0
    pixmap = QtGui.QPixmap(REFERENCE_WIDTH, int(size * 1.6))
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    try:  # ended before anything else can fail
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.translate(REFERENCE_WIDTH / 2.0, size * 1.15)
        painter.scale(scale, scale)
        painter.translate(-box.left() - box.width() / 2.0, 0)
        painter.fillPath(path, QtGui.QBrush(palette.color(QtGui.QPalette.WindowText)))
    finally:
        painter.end()
    return pixmap


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
            if self.selected in boxes and not self.scene.get("move_only"):
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
                for hx, hy in ([] if scene.get("move_only") else self.handles(boxes[self.selected]).values()):
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


ANCHOR_HELP_NOTE = (u"Moving the sample mark moves the selected glyph's anchor: a base's anchor where the mark should "
                    u"sit, a mark's own so it sits as shown.")


class AnchorPage(object):
    """The Mark anchors tab: anchors for a script's bases and marks, and the mark and mkmk code that
    attaches them, for scripts whose marks the font's features place (Khmer, Thai, Arabic, Hebrew,
    Devanagari, Bengali, Gujarati, Tamil, and the combining marks of any script)."""
    COLUMNS = ("Glyph", "Name", "Anchors to add", "Note")

    def __init__(self, owner):
        QtCore, QtGui = _qt()
        self.owner, self.ak, self.fontlab = owner, owner.ak, owner.fontlab
        ak = self.ak
        self.widget = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(ak.separator())
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(u"Script:"))
        self.script_box = QtGui.QComboBox()
        self.script_box.setWhatsThis(u"The script whose bases and marks get anchors: those the font has marks of.")
        row.addWidget(self.script_box)
        self.script_name = QtGui.QLabel(u"")  # in its place when the font has marks of one script only
        bold = QtGui.QFont(self.script_name.font)
        bold.setBold(True)
        self.script_name.setFont(bold)
        self.script_name.setWhatsThis(u"The script whose bases and marks get anchors: the only one the font has marks of.")
        self.script_name.hide()
        row.addWidget(self.script_name)
        row.addSpacing(12)
        self.code_box = QtGui.QCheckBox(u"Write the feature code")
        self.code_box.setChecked(True)
        self.code_box.setWhatsThis(u"Also writes the mark and mkmk features that attach the marks by these anchors "
                                   u"(and the checked substitutions: ccmp, pres), between FreeLab's marker lines (a "
                                   u"font with one master: anchors are the same in every master only then).")
        row.addWidget(self.code_box)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)
        ak.grid_lines(self.tree)
        self.tree.setWhatsThis(u"The script's bases (top and bottom anchors) and marks (the anchor each attaches by, "
                               u"and the one the next mark attaches to). Anchors a glyph has already are kept. "
                               u"Checked glyphs get theirs.")
        layout.addWidget(self.tree, 3)
        lower = QtGui.QHBoxLayout()
        reference = QtGui.QVBoxLayout()
        title = QtGui.QLabel(u"Reference")
        bold = QtGui.QFont(title.font)
        bold.setBold(True)
        title.setFont(bold)
        reference.addWidget(title)
        self.reference = QtGui.QLabel()
        self.reference.setProperty(ak.LEAVE_ALONE_PROP, True)
        self.reference.setAlignment(QtCore.Qt.AlignCenter)
        self.reference.setFixedWidth(REFERENCE_WIDTH)
        self.reference.setMinimumHeight(EDITOR_HEIGHT - 60)
        self.reference.setWhatsThis(u"The selected glyph's letter with the sample marks, in the reference font picked "
                                    u"on the first tab (its own marks placed by its own features), to compare.")
        reference.addWidget(self.reference, 1)
        self.reference_note = QtGui.QLabel(u"")
        self.reference_note.setWordWrap(True)
        self.reference_note.setFixedWidth(REFERENCE_WIDTH)
        reference.addWidget(self.reference_note)
        lower.addLayout(reference)
        editing = QtGui.QVBoxLayout()
        self.editor = make_editor(self)
        self.editor.setProperty(ak.LEAVE_ALONE_PROP, True)
        self.editor.setWhatsThis(u"The selected glyph with a mark attached by its anchors. " + ANCHOR_HELP_NOTE +
                                 u" Drag the mark or press the arrow keys (Shift: 10 units).")
        editing.addWidget(self.editor, 1)
        lower.addLayout(editing, 1)
        hint_row = QtGui.QHBoxLayout()
        self.hint = QtGui.QLabel(ANCHOR_HELP_NOTE)
        self.hint.setWordWrap(True)
        hint_row.addWidget(self.hint, 1)
        self.reset_button = QtGui.QPushButton(u"Reset anchors")
        self.reset_button.setWhatsThis(u"Puts the selected glyph's anchors back where they were suggested.")
        hint_row.addWidget(self.reset_button)
        editing.addLayout(hint_row)
        layout.addLayout(lower, 2)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton(u"Check all")
        self.none_button = QtGui.QPushButton(u"Check none")
        self.restore_button = QtGui.QPushButton(u"Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every check and every anchor moved by hand back as the list first came.")
        self.write_button = QtGui.QPushButton(u"Add checked anchors")
        self.write_button.setWhatsThis(u"Adds the checked glyphs' anchors in every master, each measured on its own, and "
                                       u"writes the mark and mkmk code when asked. Edit > Undo takes it back.")
        for button in (self.all_button, self.none_button, self.restore_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.write_button)
        layout.addLayout(buttons)
        self.script_box.connect("currentIndexChanged(int)", lambda index: self.run(keep_script=True))
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.reset_button.connect("clicked()", self.reset_anchors)
        self.write_button.connect("clicked()", self.write)
        self.code_box.connect("toggled(bool)", lambda on: self.update_buttons())
        self.tree.connect("itemSelectionChanged()", self.select)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        self.glyphs, self.first_checks, self.texts, self.names = [], {}, {}, []
        self.package = self.master = None
        self.model = load_anchor_model()
        self.ink = None
        self.buttons_due = False
        self.loading = False

    # -- the font --------------------------------------------------------------------

    def scripts_present(self, package):
        """The scripts the font has marks of, in ANCHOR_SCRIPTS' order."""
        found = set()
        for fg in package.fgPackage.glyphs:
            code = fg.unicode
            if code and unicodedata.category(unichr_(code)) in ("Mn", "Me"):
                script = anchor_script(code)
                if script:
                    found.add(script)
        return [script for script, _ in ANCHOR_SCRIPTS if script in found]

    def collect(self, package, master, script, ink):
        """[(name, code, role, Ink, existing anchors)] of the script's bases and marks: encoded letters that
        take marks (base_letters) and marks, and their unencoded forms (beh-ar.init, ka-khmer.sub, i.2) by
        the name before the period."""
        roles = {}
        takes_marks = base_letters(script, self.model)
        self.left_out = 0
        arabic_names = set(fg.name for fg in package.fgPackage.glyphs if fg.unicode and anchor_script(fg.unicode) == "arabic")
        for fg in package.fgPackage.glyphs:
            code = fg.unicode
            if code and anchor_script(code) == script:
                category = unicodedata.category(unichr_(code))
                if category in ("Mn", "Me"):
                    roles[fg.name] = ("mark", code, 0)
                elif category.startswith("L"):
                    parts = ligature_parts(fg.name, code, arabic_names) if script == "arabic" else 0
                    if parts:
                        roles[fg.name] = ("ligature", code, parts)
                        continue
                    if takes_marks is not None and code not in takes_marks:
                        self.left_out += 1
                        continue
                    roles[fg.name] = ("base", code, 0)
        found = []
        for fg in package.fgPackage.glyphs:
            role = roles.get(fg.name) or (roles.get(fg.name.split(u".")[0]) if not fg.unicode else None)
            if role is None and not fg.unicode:
                if script == "arabic":
                    parts = ligature_parts(fg.name, 0, arabic_names)
                    role = ("ligature", 0, parts) if parts else None
                elif script in REPH_SCRIPTS and is_reph(fg.name, script):
                    role = ("reph", 0, 0)
            if role is None:
                continue
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            existing = {}
            try:
                for anchor in layer.anchors:
                    existing[u"%s" % anchor.name] = (anchor.point.x(), anchor.point.y())
            except Exception:
                pass
            found.append((fg.name, fg.unicode or role[1], role[0], ink(fg.name), existing, role[2]))
        return found

    def rules_for(self, script, ink):
        """The substitutions the font's own forms allow (Thai's smaller and shortened forms, the i-matras
        of Devanagari, Bengali, and Gujarati), as Rules."""
        package = self.package
        names_by_code = dict((fg.unicode, fg.name) for fg in package.fgPackage.glyphs if fg.unicode)
        names = set(fg.name for fg in package.fgPackage.glyphs)
        if script == "thai":
            return thai_rules(names_by_code, names)
        if script in I_MATRAS:
            def reach_of(name):
                found = ink(name)
                advance = ink.path(name)[1]
                return found.right - advance if found is not None else None

            def advance_of(name):
                return ink.path(name)[1] or None
            return i_matra_rules(names_by_code, names, reach_of, advance_of, self.model, script)
        return []

    def plan_for(self, master):
        package = self.package
        ink = FontLabInk(self.ak, package, master)
        x_height = getattr(package, "xHeight_value", 0) or 0.5 * package.upm
        script = self.script()
        return plan_anchors(self.collect(package, master, script, ink), self.model, script, package.upm, x_height), ink

    def script(self):
        return self.scripts[self.script_box.currentIndex] if self.scripts and self.script_box.currentIndex >= 0 else "latin"

    def run(self, keep_script=False):
        QtCore, QtGui = _qt()
        if self.loading:
            return
        ak = self.ak
        kept = dict((g.name, (g.checked, dict(g.adjust))) for g in self.glyphs)
        package = self.package = self.owner.current_font()
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.glyphs = []
        if package is None:
            self.status.setText(u"No font is open.")
            self.update_buttons()
            return
        self.master = package.master
        if not keep_script:
            self.loading = True
            self.scripts = self.scripts_present(package)
            self.script_box.clear()
            for script in self.scripts:
                self.script_box.addItem(script.capitalize())
            one = len(self.scripts) == 1
            self.script_box.setVisible(not one)
            self.script_name.setVisible(one)
            self.script_name.setText(self.scripts[0].capitalize() if one else u"")
            self.loading = False
        if not self.scripts:
            self.status.setText(u"%s has no combining marks (Unicode's nonspacing marks): nothing to attach." % ak.b(package.tfn))
            self.update_buttons()
            return
        self.glyphs, self.ink = self.plan_for(self.master)
        self.glyphs = self.glyphs + self.rules_for(self.script(), self.ink)
        for g in self.glyphs:
            if g.name in kept:
                g.checked, g.adjust = kept[g.name][0], kept[g.name][1]
        self.first_checks = dict((g.name, g.checked) for g in self.glyphs)
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        self.names = [g.name for g in package.fgPackage.glyphs]
        self.code_box.setChecked(package.mastersCount == 1 and self.code_box.checked)
        self.code_box.setEnabled(package.mastersCount == 1)
        self.fill()
        bases = [g for g in self.glyphs if g.role == "base"]
        marks = [g for g in self.glyphs if g.role in ("mark", "reph")]
        others = [counted(n, one, many) for n, one, many in (
            (sum(1 for g in self.glyphs if g.role == "ligature"), u"ligature", None),
            (sum(1 for g in self.glyphs if g.role == "rule"), u"substitution", None)) if n]
        b = ak.b
        rows = self.model.get("anchors", {}).get(u"%s top" % self.script(), {})
        left_out = getattr(self, "left_out", 0)
        self.status.setText(u"%s, master %s, %s: %s and %s%s; %s get anchors, placed as %s of the corpus's %s fonts place "
                            u"theirs.%s%s Nothing changes until you click %s." % (
                                b(package.tfn), b(self.master), b(self.script().capitalize()),
                                b(counted(len(bases), u"base")), b(counted(len(marks), u"mark")),
                                u"".join(u", %s" % b(text) for text in others),
                                b(sum(1 for g in self.glyphs if g.anchors)), b(rows.get("fonts", 0)),
                                self.script().capitalize(),
                                u" %s that take no marks (in Unicode's letters and the corpus's fonts) %s left out." % (
                                    b(counted(left_out, u"letter")), u"is" if left_out == 1 else u"are")
                                if left_out else u"",
                                u" With several masters, the mark and mkmk code is left to FontLab's automatic features "
                                u"(they read the anchors of each master)." if package.mastersCount > 1 else u"",
                                ak.i(u"Add checked anchors")))

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        for roles, title in ((("base",), u"Bases"), (("ligature",), u"Ligatures"), (("mark", "reph"), u"Marks"),
                             (("rule",), u"Substitutions")):
            members = [(index, g) for index, g in enumerate(self.glyphs) if g.role in roles]
            if not members:
                continue
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (title, len(members))])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for index, g in members:
                item = QtGui.QTreeWidgetItem([unichr_(g.code) if g.code else u"", g.name, u"", u""])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                if g.anchors or g.existing or g.role == "rule":  # (its own anchors can be moved and written)
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(0, QtCore.Qt.Checked if g.checked else QtCore.Qt.Unchecked)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.refresh_item(item, g)
                top.addChild(item)
            top.setExpanded(True)
        for column in range(len(self.COLUMNS) - 1):
            self.tree.resizeColumnToContents(column)
        self.tree.blockSignals(False)
        self.update_buttons()

    def refresh_item(self, item, g):
        QtCore, QtGui = _qt()
        placed = g.placed()
        if g.role == "rule":
            item.setText(2, g.line)
            item.setText(3, u"%s (%s)." % (g.text[:1].upper() + g.text[1:], g.feature))
            icon = self.owner_picture(g)
            if icon is not None:
                item.setIcon(0, QtGui.QIcon(icon))
            return
        item.setText(2, u", ".join([u"%s %d %d" % (name, placed[name][0], placed[name][1]) for name in sorted(g.anchors)] +
                                   [u"%s moved to %d %d" % (name, placed[name][0], placed[name][1]) for name in g.moved()]))
        notes = []
        if g.role == "ligature":
            notes.append(u"joins %d letters" % max(g.parts, 2))
        if g.role == "reph":
            notes.append(u"the reph: every base gets its anchor")
        if g.existing:
            notes.append(u"has %s already" % u", ".join(sorted(g.existing)))
        if g.adjust:
            notes.append(u"moved by hand")
        if g.role == "mark" and g.side:
            notes.insert(0, u"above" if g.side == "top" else u"below")
        item.setText(3, (u"; ".join(notes) + u".") if notes else u"")
        icon = self.owner_picture(g)
        if icon is not None:
            item.setIcon(0, QtGui.QIcon(icon))

    def owner_picture(self, g):
        """The glyph alone, in the dialog's text color."""
        QtCore, QtGui = _qt()
        path, advance = self.ink.path(g.name)
        if path is None:
            return None
        size = ICON_SIZE
        scale = float(size) / float(self.package.upm)
        box = path.boundingRect()
        pixmap = QtGui.QPixmap(max(int(max(advance, box.right()) * scale - min(0, box.left()) * scale) + 8, 8), int(size * 1.45))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(4 - min(0, box.left()) * scale, size * 1.1)
            painter.scale(scale, -scale)
            painter.fillPath(path, QtGui.QBrush(self.owner.dialog.palette.color(QtGui.QPalette.WindowText)))
        finally:
            painter.end()
        return pixmap

    def items(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.glyphs) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                self.glyphs[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        for item in self.items():
            if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.update_buttons()

    def changed(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        QtCore, QtGui = _qt()
        self.buttons_due = False
        ak = self.ak
        self.harvest()
        checkable = [g for g in self.glyphs if g.anchors]
        ak.enable(self.all_button, any(not g.checked for g in checkable))
        ak.enable(self.none_button, any(g.checked for g in checkable))
        ak.enable(self.write_button, any(g.checked and g.pending() for g in self.glyphs))
        ak.enable(self.restore_button, any(g.adjust or self.first_checks.get(g.name, g.checked) != g.checked
                                           for g in self.glyphs))
        g = self.selected()
        ak.enable(self.reset_button, g is not None and bool(g.adjust))

    def restore(self):
        for g in self.glyphs:
            g.adjust = {}
            g.checked = self.first_checks.get(g.name, g.checked)
        self.fill()
        self.select()
        self.owner.log.add(u"Anchor checks and positions restored as suggested.")

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.glyphs[index] if 0 <= index < len(self.glyphs) else None

    def row_names(self, item):
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return [self.glyphs[index].name] if 0 <= index < len(self.glyphs) else []

    # -- the editor: a sample mark attached ---------------------------------------------

    def samples(self, g):
        """The glyphs drawn with g: for a base, a mark above and one below (and the reph); for a
        ligature, a mark above and one below on each of its letters (anchor top_1, bottom_1, ...); for
        a mark (the reph), a base."""
        if g.role in ("base", "ligature"):
            found = []
            sides = ["top", "bottom"]
            if g.role == "base":  # and the other sides its marks take (Hebrew's dagesh, holam), and the reph
                sides += sorted(set(m.side for m in self.glyphs if m.role == "mark" and m.side in SIDE_FAMILY
                                    and m.side in g.placed())) + ["reph"]
            for side in sides:
                mark = next((m for m in self.glyphs if m.role in ("mark", "reph") and m.side == side
                             and (u"_" + side) in m.placed()), None)
                if g.role == "ligature":
                    found.extend((u"%s_%d" % (side, part), mark) for part in range(1, max(g.parts, 2) + 1))
                else:
                    found.append((side, mark))
            return found
        if g.role == "rule":
            return []
        base = next((b for b in self.glyphs if b.role == "base" and b.code and g.side in b.placed()), None)
        return [(g.side, base)]

    def select(self):
        g = self.selected()
        self.editor.selected = None
        self.editor.scene = self.scene(g) if g is not None else None
        self.editor.update()
        self.hint.setText(ANCHOR_HELP_NOTE)
        self.draw_reference(g)
        self.update_buttons()

    def reference_text(self, g):
        """The characters the reference draws for g: its letter with each sample mark (a base), or the
        sample letter with it (a mark); none for a glyph of no character."""
        if g is None:
            return u""
        if g.role == "rule":
            return g.sample
        if g.role == "reph":
            ra, virama, consonant = REPH_SCRIPTS.get(self.script(), REPH_SCRIPTS["devanagari"])
            return unichr_(ra) + unichr_(virama) + unichr_(consonant)
        if not g.code:
            return u""
        if g.role == "ligature":
            return unichr_(g.code)
        if g.role == "base":
            marks = [m for _, m in self.samples(g) if m is not None and m.code]
            if not marks:
                return unichr_(g.code)
            return u" ".join(unichr_(g.code) + unichr_(m.code) for m in marks)
        side, base = self.samples(g)[0]
        return unichr_(base.code) + unichr_(g.code) if base is not None and base.code else unichr_(DOTTED_CIRCLE) + unichr_(g.code)

    def draw_reference(self, g):
        text = self.reference_text(g)
        if not text:
            self.reference.clear()
            self.reference_note.setText(u"" if g is None else u"%s is no character's glyph: no reference." % g.name)
            return
        codes = [ord(c) for c in text if c != u" "]
        family, chosen = self.owner.reference_family(codes, script_families(self.script()))
        if family is None:
            self.reference.clear()
            self.reference_note.setText(u"No reference font has %s." % text)
            return
        self.reference.setPixmap(reference_picture(text, family, self.owner.dialog.palette))
        if family == chosen:
            self.reference_note.setText(u"%s in %s." % (text, family))
        else:
            self.reference_note.setText(u"%s lacks %s: shown in %s." % (chosen, text, family))

    def scene(self, g):
        placed = g.placed()
        parts, ranges, self.edits = [], [], []
        if g.role == "rule":
            parts.append((g.name, 1.0, 1.0, 0.0, 0.0))
            advance = self.ink.path(g.name)[1]
        elif g.role in ("base", "ligature"):
            parts.append((g.name, 1.0, 1.0, 0.0, 0.0))
            for side, mark in self.samples(g):
                if mark is None or side not in placed:
                    continue
                own = mark.placed()[u"_" + side.split(u"_")[0]]
                parts.append((mark.name, 1.0, 1.0, placed[side][0] - own[0], placed[side][1] - own[1]))
                ranges.append((len(parts) - 1, len(parts)))
                self.edits.append((g, side, 1))
            advance = self.ink.path(g.name)[1]
        else:
            side, base = self.samples(g)[0]
            if base is None:
                return None
            target = base.placed()[side]
            own = placed[u"_" + side]
            parts = [(base.name, 1.0, 1.0, 0.0, 0.0), (g.name, 1.0, 1.0, target[0] - own[0], target[1] - own[1])]
            ranges = [(1, 2)]
            self.edits.append((g, u"_" + side, -1))
            advance = self.ink.path(base.name)[1]
        box = parts_box(parts, self.ink)
        if box is None:
            return None
        upm = float(self.package.upm)
        return {"glyphs": [(parts, max(advance, box[2] - min(0, box[0])), "new")], "parts": parts, "ranges": ranges,
                "ink": self.ink, "upm": upm, "top": max(box[3], upm * 0.8) + upm * 0.05,
                "bottom": min(box[1], -upm * 0.25) - upm * 0.05, "room": (), "letters": (None, None), "move_only": True}

    def adjust_of(self, index):
        if index is None or index >= len(getattr(self, "edits", [])):
            return [0.0, 0.0, 1.0, 1.0]
        g, name, sign = self.edits[index]
        dx, dy = g.adjust.get(name, (0, 0))
        return [sign * dx, sign * dy, 1.0, 1.0]

    def set_adjust(self, index, change, final):
        """The sample mark moved: the selected glyph's anchor moved with it (a mark's own the other way)."""
        if index is None or index >= len(getattr(self, "edits", [])):
            return
        g, name, sign = self.edits[index]
        dx, dy = round(change[0] * sign, 1), round(change[1] * sign, 1)
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            g.adjust.pop(name, None)
        else:
            g.adjust[name] = [dx, dy]
        selected = self.editor.selected
        self.editor.scene = self.scene(self.selected())
        self.editor.selected = selected
        self.editor.update()
        self.mark_selected(index)
        if final:
            Qt = _qt()[0].Qt
            for item in self.items():
                index_ = int(item.data(0, Qt.UserRole))
                if 0 <= index_ < len(self.glyphs) and self.glyphs[index_] is g:
                    self.tree.blockSignals(True)
                    self.refresh_item(item, g)
                    if g.pending() and item.flags() & Qt.ItemIsUserCheckable:
                        item.setCheckState(0, Qt.Checked)  # moved by hand: to be written
                    self.tree.blockSignals(False)
            self.update_buttons()

    def mark_selected(self, index):
        if index is None or index >= len(getattr(self, "edits", [])):
            self.hint.setText(ANCHOR_HELP_NOTE)
            return
        g, name, sign = self.edits[index]
        x, y = g.placed().get(name, (0, 0))
        self.hint.setText(u"%s's %s anchor: %d, %d. Drag the mark or press the arrow keys (Shift: 10 units); Backspace "
                          u"puts it back." % (g.name, name, x, y))

    def neighbor_clicked(self, role):
        pass

    def reset_anchors(self):
        """The selected glyph's anchors back where they were placed (or are), its row and the editor too."""
        QtCore, QtGui = _qt()
        g = self.selected()
        if g is None:
            return
        g.adjust = {}
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.glyphs) and self.glyphs[index] is g:
                self.tree.blockSignals(True)
                self.refresh_item(item, g)
                self.tree.blockSignals(False)
        self.select()  # the editor drawn again (the list's refill alone left the mark where it was dragged)
        self.update_buttons()

    def show_in_glyph_window(self):
        g = self.selected()
        if g is None or self.package is None:
            return
        error = self.ak.show_in_glyph_window(self.fontlab, u"/%s" % g.name)
        if error:
            self.owner.log.add(u"FontLab did not open the glyph: %s" % self.ak.html(error), "error")

    # -- writing -----------------------------------------------------------------------

    def write(self):
        QtCore, QtGui = _qt()
        self.harvest()
        package = self.package
        if package is None:
            return
        current = self.owner.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.owner.log.add(u"The font changed: here is this one's list. Nothing was added.", "warning")
            return
        chosen = dict((g.name, g) for g in self.glyphs if g.checked and g.pending())
        if not chosen and not any(g.checked for g in self.glyphs if g.role == "rule"):
            return
        new_texts = mark_texts(self.glyphs, self.texts) if self.code_box.checked else {}
        if new_texts:
            fc = None
            try:
                fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            except Exception:
                pass
            if fc is not None:
                problem = fc.check_code(u"languagesystem DFLT dflt;\n" + u"".join(new_texts.get(t, u"") for t in CODE_FEATURES),
                                        self.names)
                if problem:
                    self.owner.log.add(u"The mark code has problems, so nothing was written: %s" % self.ak.html(problem), "error")
                    return
        added, moved, touched, error = 0, 0, [], None
        try:
            for master in list(package.masters) or [self.master]:
                planned = dict((g.name, g) for g in self.plan_for(master)[0])
                for name, g in chosen.items():
                    here = planned.get(name)
                    if here is None:
                        continue
                    here.adjust = g.adjust
                    glyph = package.findName(name)
                    layer = glyph.getLayerByName(master) if glyph is not None else None
                    if layer is None:
                        continue
                    for anchor_name in sorted(here.anchors):
                        if layer.findAnchor(anchor_name) is not None:
                            continue
                        x, y = here.placed()[anchor_name]
                        pin = self.fontlab.flPinPoint(QtCore.QPointF(float(x), float(y)))
                        pin.name = anchor_name
                        layer.addAnchor(pin)
                        added += 1
                    for anchor_name in here.moved():  # its own anchors moved by hand (flPinPoint.point, proven)
                        anchor = layer.findAnchor(anchor_name)
                        if anchor is None:
                            continue
                        x, y = here.placed()[anchor_name]
                        anchor.point = QtCore.QPointF(float(x), float(y))
                        moved += 1
                    if glyph not in touched:
                        touched.append(glyph)
            features = package.fgPackage.features
            for tag in CODE_FEATURES:
                if tag in new_texts and new_texts[tag] != self.texts.get(tag):
                    features.set_feature(tag, new_texts[tag])
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.fontlab, package, u"FreeLab Diacritics anchors", touched)
        self.owner.log.add(u"Added %s%s to %s%s. Edit &gt; Undo takes it back." % (
            self.ak.b(counted(added, u"anchor")), (u" and moved %s" % self.ak.b(moved)) if moved else u"",
            self.ak.b(counted(len(touched), u"glyph")),
            u", and wrote the %s code" % u", ".join(t for t in CODE_FEATURES if t in new_texts) if new_texts else u""),
            "done" if added or moved or new_texts else "info")
        if error is not None:
            self.owner.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        self.run(keep_script=True)


class AccentsDialog(object):
    COLUMNS = ("Glyph", "Name", "Built from")

    def __init__(self, characters=None):
        """characters: letters handed over (Font Check's missing ones), listed first as their own set."""
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.given = [c for c in (characters or []) if c]
        ak = self.ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Diacritics")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        outer = QtGui.QVBoxLayout(dialog)
        # A tab bar over plain pages (a QTabWidget's themed page frames its buttons in light colors in dark mode)
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        outer.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        outer.addWidget(self.pages, 1)
        letters_page = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(letters_page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.pages.addWidget(letters_page)
        self.tabs.addTab(u"Letters with diacritics")
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(ak.separator())
        self.log = ak.Log()
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Character set:"))
        self.set_box = QtGui.QComboBox()
        if self.given:
            self.set_box.addItem(u"From Font Check (%s)" % ak.counted(len(self.given), u"letter"))
        for _, label, _ in SETS:
            self.set_box.addItem(label)
        self.set_box.setCurrentIndex(0 if self.given else len(SETS) - 1)
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
        self.hint = QtGui.QLabel(u"Click a diacritic to move or scale it.")
        self.hint.setWordWrap(True)
        hint_row.addWidget(self.hint, 1)
        self.reset_marks_button = QtGui.QPushButton(u"Reset diacritics")
        self.reset_marks_button.setWhatsThis(u"Puts this glyph's diacritics back where they were suggested.")
        hint_row.addWidget(self.reset_marks_button)
        editing.addLayout(hint_row)
        lower.addLayout(editing, 1)
        layout.addLayout(lower, 2)

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
        layout.addLayout(buttons)
        self.anchors = AnchorPage(self)
        self.pages.addWidget(self.anchors.widget)
        self.tabs.addTab(u"Mark anchors")
        self.tabs.setTabToolTip(1, u"Anchors and mark features for scripts whose marks are attached, not built "
                                   u"(Khmer, Thai, Arabic, Hebrew, Devanagari, Bengali, Gujarati, Tamil, and the combining "
                                   u"marks of any script)")
        outer.addWidget(self.log.widget)
        closing = QtGui.QHBoxLayout()
        closing.addStretch(1)
        closing.addWidget(self.close_button)
        outer.addLayout(closing)
        self.anchors_read = False
        self.tabs.connect("currentChanged(int)", self.switch_page)
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
        self.reference_history = []
        family = self.settings.get("reference")
        if family:
            self.reference_history.append(family)
        self.model = load_model()
        ak.plain_buttons(dialog)
        self.history_timer = ak.watch_history(self)
        self.flagging = [ak.flag_menu(self.tree, self, self.flag_names, self.row_names),
                         ak.flag_menu(self.anchors.tree, self, lambda: [self.anchors.selected().name]
                                      if self.anchors.selected() is not None else [], self.anchors.row_names)]
        self.update_buttons()

    def flag_names(self):
        """The selected glyph, or its letter while it is not built."""
        r = self.selected()
        if r is None:
            return []
        return [r.name] if self.in_font(r) else [r.base] if r.base else []

    def row_names(self, item):
        """A row's glyph, if the font has it (its flag shown); none for a section's heading."""
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        if not 0 <= index < len(self.recipes):
            return []
        r = self.recipes[index]
        return [r.name] if self.package is not None and r.name and self.package.findName(r.name) is not None else []

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
        index = self.set_box.currentIndex
        if self.given:
            if index == 0:
                return list(self.given)
            index -= 1
        ranges = SETS[index][2]
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
            self.ak.section_row(top, self.tree)
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
        self.reset_marks_button.setText(u"Reset diacritic" if r is not None and len(r.marks) == 1 else u"Reset diacritics")

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

    def switch_page(self, index):
        QtCore, QtGui = _qt()
        self.pages.setCurrentIndex(index)
        if index == 1 and not self.anchors_read:
            self.anchors_read = True
            QtCore.QTimer.singleShot(0, self.anchors.run)  # read as the tab is first shown

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again (checks and marks moved by hand
        kept)."""
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()
        if self.anchors_read:
            self.anchors.run(keep_script=True)

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
        self.hint.setText(u"Click a diacritic to move or scale it.")
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
            self.hint.setText(u"Click a diacritic to move or scale it.")
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

    def reference_family(self, codes, more=()):
        """(family, chosen): the first of the chosen reference font, those picked before, and the known
        families (more: a script's) that has every one of the code points, or None; and the chosen one."""
        chosen = u"%s" % _property(self.reference_font, "currentFont").family()
        for candidate in [chosen] + self.reference_history + list(REFERENCE_FAMILIES) + list(more):
            if all(has_character(candidate, code) for code in codes):
                return candidate, chosen
        return None, chosen

    def reference_changed(self):
        if self.choosing_reference:
            return
        family = u"%s" % _property(self.reference_font, "currentFont").family()
        if family in self.reference_history:
            self.reference_history.remove(family)
        self.reference_history.insert(0, family)  # the fonts picked before: the fallbacks, latest first
        self.settings["reference"] = family
        write_settings(self.ak, self.settings)
        self.draw_reference(self.selected())
        if self.anchors_read:
            self.anchors.draw_reference(self.anchors.selected())

    def draw_reference(self, r):
        QtCore, QtGui = _qt()
        if r is None or self.package is None:
            self.reference.clear()
            self.reference_note.setText(u"")
            return
        family, chosen = self.reference_family([r.code], script_families(script_of(r.char)))
        if family is None:
            self.reference.clear()
            self.reference_note.setText(u"No reference font has %s." % r.char)
            return
        self.reference.setPixmap(reference_picture(r.char, family, self.dialog.palette))
        if family == chosen:
            self.reference_note.setText(u"%s in %s." % (r.char, family))
        else:
            self.reference_note.setText(u"%s lacks %s: shown in %s." % (chosen, r.char, family))

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
        made, skipped, failed, error, touched = [], [], [], None, []
        try:
            for r in chosen:
                glyph = package.findName(r.name)
                if glyph is not None and not is_empty(glyph):
                    skipped.append(r.char)  # made meanwhile
                    continue
                added = glyph is None
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
                placed = False
                for master in masters:
                    ink, placement = self.inks[master], self.placements[master]
                    if ink(r.base) is None:
                        continue  # not drawn in this master
                    checked = r.checked
                    parts, width = place(r, ink, placement, metrics)
                    r.checked = checked
                    if parts is None:
                        continue
                    placed = True
                    components = []
                    for name, sx, sy, dx, dy in parts:
                        component = fontlab.GlyphComponent(name)
                        component.transform = QtGui.QTransform(sx, 0.0, 0.0, sy, float(round(dx)), float(round(dy)))
                        components.append(component)
                    layer = glyph.getLayerByName(master, True)
                    layer.setGlyphComponents(components, float(width), package, False)
                if not placed or is_empty(package.findName(r.name)):
                    # Nothing of it drawn: said why, and a glyph added for it taken out again
                    failed.append((r.char, self.why_empty(r, masters, placed)))
                    if added:
                        package.deleteGlyph(package.findName(r.name))
                    continue
                touched.append(glyph)
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
        for char, why in failed:
            self.log.add(u"%s was not built: %s." % (b(char), self.ak.html(why)), "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        self.run()

    def why_empty(self, r, masters, placed):
        """Why a recipe came out with nothing drawn: the first of its glyphs with no outline, master by
        master, else FontLab not keeping its components."""
        if placed:
            return u"FontLab did not keep its components (%s)" % u" + ".join(
                [r.base] + [part[0] for mark in r.marks for part in mark.parts])
        for master in masters:
            ink = self.inks[master]
            for name in [r.base] + [part[0] for mark in r.marks for part in mark.parts]:
                if ink(name) is None:
                    return u"%s has no outline in master %s" % (name, master)
        return u"its marks could not be placed"

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def _property(widget, name):
    """A Qt property's value (PythonQt gives properties as attributes, some builds as methods)."""
    value = getattr(widget, name)
    return value() if callable(value) else value


def main(characters=None):
    """Opens Diacritics; characters (Font Check's missing letters) are listed as a set of their own."""
    held = getattr(sys, "_freelab_diacritics", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = AccentsDialog(characters)
    except Exception as exc:
        print("FreeLab Diacritics: %s" % exc)
        return
    sys._freelab_diacritics = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_diacritics":
    main()
