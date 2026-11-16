#FLM: CJK Vertical
# -*- coding: utf-8 -*-
"""FreeLab CJK Vertical, from FontLab's Scripts menu.

Applications lay vertical text out; a font needs three things of its own to be set in it well:

- Vertical forms (vert, and vrt2, which applications that know it use instead): the characters that turn
  or move in vertical text get glyphs of their own. Brackets, dashes, the long vowel mark, and the wave
  dash turn a quarter clockwise; the small kana, the ideographic comma and full stop, and the full-width
  comma and full stop move to the upper right of their square. Which characters, and how far each moves,
  come from the open-licensed CJK fonts (cjk/vertical_model.json, measured by cjk/train/vertical.py, with
  the characters Unicode's Vertical_Orientation property, UAX #50, marks Tu or Tr). Each form is built as
  a component of its glyph, turned or moved, so it follows the glyph's outline; a glyph the font has for
  the form already (a .vert glyph, or the vertical presentation form of the character, U+FE10 to U+FE48)
  is used as it is.
- Proportional heights (vpal): each full-width kana and punctuation mark (its vertical form where it has
  one) trimmed to its ink and the top and bottom sidebearings those fonts give theirs, as CJK Spacing's
  palt does across.
- Vertical metrics: each glyph's advance height (FontLab keeps none when it opens a font file; a glyph
  without one is set at the em), and the vhea table's ascender, descender, and line gap in the font info.

The font's own vert, vrt2, and vpal code is kept: a glyph it already substitutes or positions is listed
as the font's and left alone, and FreeLab's rules sit between its own marker lines. A glyph of the form's
name the font has is never replaced. Glyphs, code, and advance heights are one step of FontLab's History;
the vhea values are not in FontLab's History, so the window can put them back.

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import os
import re
import sys
import time

MODEL_FILE = "vertical_model.json"
SPACING_FILE, SPACING_MODULE = "freelab_cjk_spacing.py", "freelab_cjk_spacing"
BEGIN, END = u"# >>> FreeLab %s (made by FreeLab CJK Vertical)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
FEATURE_TITLES = {"vert": u"Vertical Alternates", "vrt2": u"Vertical Alternates and Rotation",
                  "vpal": u"Proportional Alternate Vertical Metrics", "vkrn": u"Vertical Kerning"}
SUFFIX = u".vert"
FULL_WIDTH_SHARE = 0.9  # a glyph narrower than this share of the em is turned by applications: no vpal
TOLERANCE_UNITS = 4  # a vpal trim smaller than this at both ends is not listed
MIN_AGREE = 0.5  # a character's form is built where at least this share of the fonts that give it one agree
MIN_FONTS = 3  # and at least this many fonts give it one
MIN_SHARE = 0.5  # and at least this share of the fonts that have the character give it a form
MIN_EXACT = 0.2  # and at least this share of them make it exactly so (the glyph's own outline turned or moved)
TURNS = ("rotated", "rotated flipped", "rotated ccw")
HOW_LABELS = {"rotated": u"Turned a quarter clockwise", "rotated flipped": u"Turned a quarter clockwise, mirrored",
              "rotated ccw": u"Turned a quarter counterclockwise", "moved": u"Moved"}
SECTION_LABELS = (("rotated", u"Turned a quarter (brackets, dashes, the long vowel mark)"),
                  ("moved", u"Moved to the upper right (small kana, comma and full stop)"),
                  ("ours", u"In FreeLab's code already (written before)"),
                  ("glyph", u"Drawn in the font already, not in its code yet"),
                  ("other", u"Others the fonts give a form (Greek, Cyrillic, symbols): left unchecked"),
                  ("font", u"In the font's own code"),
                  ("turned", u"Turned proportional glyphs (vrt2)"),
                  ("vpal", u"Proportional heights (vpal)"),
                  ("vkrn", u"Vertical kerning (vkrn)"),
                  ("metrics", u"Vertical metrics"))
# Where the forms checked at first are: the characters Unicode marks transformed in vertical text (Tu,
# Tr) and those of these blocks (dashes and ellipses, CJK punctuation, kana, vertical and full-width
# forms); the others the corpus's fonts give a form (full-width Greek and Cyrillic, symbols, box
# drawing) are listed unchecked.
CORE_RANGES = ((0x2010, 0x2027), (0x3000, 0x30FF), (0x31F0, 0x31FF), (0xFE10, 0xFE4F), (0xFF00, 0xFFEF))
# What makes a font a CJK font here: a glyph in one of these blocks (Hangul Jamo, the radicals and ideographic
# description characters, CJK punctuation, kana, bopomofo, Hangul compatibility jamo, kanbun, CJK strokes,
# enclosed and compatibility CJK, the ideographs, the Hangul syllables and their extended jamo, the vertical,
# compatibility, half-width, and full-width forms, the kana supplements). A font with none (the owner's Noto
# Sans) is not set in vertical CJK text: it is offered nothing, as CJK Spacing offers it no trim. Its em-wide
# HORIZONTAL BAR (U+2015, General Punctuation: the dash Japanese text turns) had been offered a vertical form.
CJK_RANGES = ((0x1100, 0x11FF), (0x2E80, 0x2FDF), (0x2FF0, 0x303F), (0x3040, 0x30FF), (0x3100, 0x31FF),
              (0x3200, 0x33FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xA960, 0xA97F), (0xAC00, 0xD7FF),
              (0xF900, 0xFAFF), (0xFE10, 0xFE1F), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x1B000, 0x1B16F),
              (0x20000, 0x323AF))


def has_cjk(codes):
    """Whether a font's code points include a CJK glyph (CJK_RANGES): kana, Hangul, an ideograph, bopomofo,
    or CJK punctuation and forms."""
    return any(low <= code <= high for code in codes for low, high in CJK_RANGES)
# Unicode's vertical presentation forms (UnicodeData.txt, <vertical> decompositions), each for the
# full-width or CJK character it stands for in vertical text: a font that draws one has drawn the form.
VERTICAL_PRESENTATION = {
    0xFF0C: 0xFE10, 0x3001: 0xFE11, 0x3002: 0xFE12, 0xFF1A: 0xFE13, 0xFF1B: 0xFE14, 0xFF01: 0xFE15,
    0xFF1F: 0xFE16, 0x3016: 0xFE17, 0x3017: 0xFE18, 0x2026: 0xFE19, 0x2025: 0xFE30, 0x2014: 0xFE31,
    0x2013: 0xFE32, 0xFF3F: 0xFE33, 0xFF08: 0xFE35, 0xFF09: 0xFE36, 0xFF5B: 0xFE37, 0xFF5D: 0xFE38,
    0x3014: 0xFE39, 0x3015: 0xFE3A, 0x3010: 0xFE3B, 0x3011: 0xFE3C, 0x300A: 0xFE3D, 0x300B: 0xFE3E,
    0x3008: 0xFE3F, 0x3009: 0xFE40, 0x300C: 0xFE41, 0x300D: 0xFE42, 0x300E: 0xFE43, 0x300F: 0xFE44,
    0xFF3B: 0xFE47, 0xFF3D: 0xFE48}
# The vhea values written to the font info, each a share of the em from the corpus (metrics)
VHEA_FIELDS = (("vhea_ascent", "openTypeVheaVertTypoAscender", u"vhea ascender"),
               ("vhea_descent", "openTypeVheaVertTypoDescender", u"vhea descender"),
               ("vhea_line_gap", "openTypeVheaVertTypoLineGap", u"vhea line gap"))
VHEA_DEFAULTS = {"vhea_ascent": 0.5, "vhea_descent": -0.5, "vhea_line_gap": 0.0}
OWN_DEFAULTS = ("vhea_line_gap",)  # FreeLab's own value, not the corpus's median (0.15 em): the owner's choice, 0
# A sample for vertical text, written for FreeLab (GPL-3 with the code): brackets, small kana, the long
# vowel mark, the comma and full stop, a question mark, parentheses, and a dash, each of which turns or moves.
SAMPLE_JA = (u"「ちょっとコーヒーでも飲みますか"
             u"？」――ええ、ぜひ。（午後三時）")


def unichr_(code):
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def counted(number, one, many=None):
    """u"1 glyph", u"2 glyphs", u"9,507 layers": the word follows the number, which is grouped by thousands."""
    return u"%s %s" % (format(int(number), ","), one if number == 1 else (many or one + u"s"))


def load_model(path=None, name=MODEL_FILE):
    """The corpus's vertical forms (vertical_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), name)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


def load_script(file_name, module_name):
    """A FreeLab script beside this one, loaded as a module without starting it."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, file_name)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(module_name)
    if held is not None and getattr(held, "_freelab_stamp", stamp) == stamp and hasattr(held, "kind_of"):
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(module_name)
            module.__file__ = path
            sys.modules[module_name] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, file_name, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def spacing():
    """CJK Spacing, beside this script: the kinds of glyph, the samples, line breaking, and its reading
    of a feature's own single positions."""
    return load_script(SPACING_FILE, SPACING_MODULE)


# ---------------------------------------------------------------------------
# Geometry: the em's square in vertical text, and the forms' transforms
# ---------------------------------------------------------------------------

def em_center(advance, origin, height):
    """The center of a glyph's square in vertical text: half its advance across, half its advance height
    under the vertical origin (origin: the origin's y, the typographic ascender in most CJK fonts)."""
    return advance / 2.0, origin - height / 2.0


def form_matrix(how, move, advance, origin, height):
    """The transform (m11, m12, m21, m22, dx, dy), as QTransform takes it (x' = m11 x + m21 y + dx,
    y' = m12 x + m22 y + dy), that makes a vertical form of its glyph: a quarter turn about the em's
    center then the move, or the move alone. move: (dx, dy) in font units."""
    dx, dy = move
    if how in TURNS:
        cx, cy = em_center(advance, origin, height)
        if how == "rotated":  # clockwise: (x, y) -> (cx + (y - cy), cy - (x - cx))
            return (0.0, -1.0, 1.0, 0.0, cx - cy + dx, cy + cx + dy)
        if how == "rotated flipped":  # then mirrored across: (x, y) -> (cx - (y - cy), cy - (x - cx))
            return (0.0, -1.0, -1.0, 0.0, cx + cy + dx, cy + cx + dy)
        return (0.0, 1.0, -1.0, 0.0, cx + cy + dx, cy - cx + dy)  # counterclockwise
    return (1.0, 0.0, 0.0, 1.0, float(dx), float(dy))


def mapped_point(matrix, x, y):
    m11, m12, m21, m22, dx, dy = matrix
    return m11 * x + m21 * y + dx, m12 * x + m22 * y + dy


def mapped_box(matrix, box):
    """A box (x min, y min, x max, y max) as the transform puts it."""
    corners = [mapped_point(matrix, x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    return (min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners),
            max(c[1] for c in corners))


def compose(outer, inner):
    """outer after inner, both as form_matrix gives them."""
    a1, b1, c1, d1, e1, f1 = inner
    a2, b2, c2, d2, e2, f2 = outer
    return (a2 * a1 + c2 * b1, b2 * a1 + d2 * b1, a2 * c1 + c2 * d1, b2 * c1 + d2 * d1,
            a2 * e1 + c2 * f1 + e2, b2 * e1 + d2 * f1 + f2)


# ---------------------------------------------------------------------------
# The font's own code: classes and single substitutions
# ---------------------------------------------------------------------------

# (CJK Spacing's reader of the font's own code, shared: its classes, lookups, and single positions)

def code_classes(text):
    """{@name: [members]} of the classes a feature code defines (ranges spelled out)."""
    return spacing().code_classes(text)


def members(token, classes, depth=0):
    """The glyphs a token names: a glyph, a [list], or a @class (classes: {@name: [members]})."""
    return spacing().class_members(token, classes, depth)


SUBSTITUTION = re.compile(u"^\\s*sub(?:stitute)?\\s+(\\[[^\\]]*\\]|@[A-Za-z0-9_.\\-]+|[A-Za-z0-9_.\\-]+)\\s+by\\s+"
                          u"(\\[[^\\]]*\\]|@[A-Za-z0-9_.\\-]+|[A-Za-z0-9_.\\-]+)\\s*;")


def code_lookups(text):
    """{name: body} of the named lookups a feature code (or the prefix) defines."""
    return spacing().code_lookups(text)


def statements(tag, text, lookups=None):
    """The statements of a feature's own code, outside this tool's block (spacing's feature_statements)."""
    return spacing().feature_statements(tag, text, lookups, BEGIN, END)


def own_positions(tag, text, classes=None, lookups=None):
    """The glyphs a feature's own code (outside FreeLab's block) gives a single value (CJK Spacing's
    font_positioned: pos a <0 -2 0 -13>; pos [a b] <...>; pos @class -500;), the font's classes read too
    (classes: {@name: [members]}), and the lookups it names (lookups: the prefix's, {name: body}): a
    second value for one of them would not compile. A pair or a contextual rule is not a single value."""
    return spacing().font_positioned(tag, text, classes, lookups, BEGIN, END)


def own_substitutions(tag, text, classes=None, lookups=None):
    """{glyph: its vertical form} of the single substitutions in a feature's own code (outside FreeLab's
    block): sub a by b; sub [a b] by [c d]; sub [a b] by c; sub @one by @two; (classes: the font's,
    {@name: [members]}; those the code defines are added), the lookups it names included (lookups: the
    prefix's, {name: body}). A substitution of one glyph by several, or with context, is not a vertical
    form and is not read."""
    known = dict(classes or {})
    known.update(code_classes(text))
    for body in (lookups or {}).values():
        known.update(code_classes(body))
    found = {}
    for statement in statements(tag, text, lookups):
        match = SUBSTITUTION.match(statement + u";")
        if not match:
            continue
        sources, targets = members(match.group(1), known), members(match.group(2), known)
        if len(targets) == 1:
            for source in sources:
                found.setdefault(source, targets[0])
        elif len(sources) == len(targets):
            for source, target in zip(sources, targets):
                found.setdefault(source, target)
    return found


def freelab_substitutions(tag, text):
    """{glyph: form} of FreeLab's own block in a feature (written by this tool before), its markers found
    as comments wherever they stand (Feature Code's block_text)."""
    found = {}
    try:
        inner = reader().block_text(text, BEGIN % tag, END % tag)
    except Exception:
        inner = None  # (no reader: nothing read; the window says why and writes nothing)
    for line in (inner or u"").splitlines():
        match = SUBSTITUTION.match(line.strip())
        if match:
            found[match.group(1)] = match.group(2)
    return found


# ---------------------------------------------------------------------------
# The plan: vertical forms, vpal, metrics
# ---------------------------------------------------------------------------

class Form(object):
    """A character's vertical form. state: "build" (a glyph made from its glyph, and a rule), "glyph" (a
    glyph of the font is the form: a rule only), or "font" (the font's own code makes it: left alone)."""

    def __init__(self, code, name, how, target, state, matrix=None, note=u"", core=True, ours=False):
        self.code, self.name, self.how, self.target, self.state = code, name, how, target, state
        self.matrix, self.note, self.core, self.ours = matrix, note, core, ours
        self.checked = state != "font" and (core or ours)

    @property
    def char(self):
        return unichr_(self.code)

    def section(self):
        if getattr(self, "vrt2_only", False):
            return "turned"
        if self.ours:
            return "ours"
        if self.state != "font" and not self.core:
            return "other"
        if self.state == "build":
            return "rotated" if self.how in TURNS else "moved"
        return self.state


def is_core(code, orientation=None):
    """Whether a character's form is checked at first: transformed in vertical text, as Unicode has it
    (orientation "Tu" or "Tr"), or in CORE_RANGES."""
    return orientation in ("Tu", "Tr") or any(low <= code <= high for low, high in CORE_RANGES)


def form_name(name):
    """The name of a glyph's vertical form: its name with .vert."""
    return name + SUFFIX


def plan_forms(glyphs, names, model, upm, origin, height=None, own=None, ours=None):
    """The vertical forms for the font's glyphs: glyphs [(code, name, advance, (x min, y min, x max,
    y max) or None)], names: every glyph name of the font, model: vertical_model.json, origin: the
    vertical origin's y, height: the advance height (the em by default), own: {glyph: form} the font's
    own vert and vrt2 make (outside FreeLab's block), ours: {glyph: form} of FreeLab's block. A form
    FreeLab wrote before is listed as such, checked: its rule is written again (unchecked, taken out),
    and its glyph is never replaced.

    A character is given a form where at least MIN_FONTS of the corpus's fonts give it one and
    MIN_AGREE of those make it the same way (turned or moved); its move is their median. The vertical
    presentation form of a character (U+FE11 for U+3001), when the font has it, is its form as drawn."""
    height = float(height or upm)
    own, ours = own or {}, ours or {}
    names = set(names)
    by_code = dict((code, name) for code, name, _, _ in glyphs)
    forms, seen = [], set()
    for code, name, advance, box in sorted(glyphs, key=lambda g: g[0]):
        entry = (model.get("vert") or {}).get(u"U+%04X" % code)
        if name in seen or entry is None:
            continue
        seen.add(name)
        core = is_core(code, (model.get("orientation") or {}).get(u"U+%04X" % code))
        if name in own:
            forms.append(Form(code, name, entry.get("how"), own[name], "font",
                              note=u"the font's own vert makes it %s" % own[name]))
            continue
        if ours.get(name) in names:
            forms.append(Form(code, name, entry.get("how"), ours[name], "glyph", note=u"FreeLab's code makes it %s"
                              % ours[name], core=core, ours=True))
            continue
        presentation = by_code.get(VERTICAL_PRESENTATION.get(code))
        target = form_name(name)
        if target in names:
            forms.append(Form(code, name, entry.get("how"), target, "glyph", note=u"drawn as %s" % target, core=core))
            continue
        if presentation is not None and presentation in names:
            forms.append(Form(code, name, entry.get("how"), presentation, "glyph",
                              note=u"its vertical presentation form, %s" % presentation, core=core))
            continue
        how = entry.get("how")
        if how not in TURNS + ("moved",) or entry.get("fonts", 0) < MIN_FONTS or entry.get("agree", 0) < MIN_AGREE:
            continue  # (redrawn in the corpus: a form to draw by hand, not to build)
        if entry.get("share", 1.0) < MIN_SHARE:
            continue  # (most fonts with the character set it as it is: a full-width ! stands centered already)
        if entry.get("exact", 1.0) < MIN_EXACT:
            continue  # (laid out anew by nearly every font, as the squared words ㌔ are: a copy would not do)
        if (model.get("orientation") or {}).get(u"U+%04X" % code) == "U":
            continue  # (upright in vertical text, as Unicode has it: a font may adjust it, FreeLab does not)
        if box is None or advance < FULL_WIDTH_SHARE * upm:
            continue  # (nothing drawn; or proportional: applications turn the glyph itself)
        matrix = placed_matrix(how, entry, advance, box, origin, height, upm)
        forms.append(Form(code, name, how, target, "build", matrix, core=core))
    return forms


def placed_matrix(how, entry, advance, box, origin, height, upm):
    """A form's transform, rounded as FontLab keeps it (whole units): a turn about the em's center and
    the corpus's median move after it (a turned form keeps where the glyph's design puts it); a moved
    form is put where the corpus's forms have their ink's center in the square (entry "place": shares
    of the advance across and of the advance height up), wherever the glyph's own ink sits, else moved
    by the median move."""
    move = entry.get("move") or (0.0, 0.0)
    place = entry.get("place")
    if how == "moved" and place and box is not None:
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        shift = (place[0] * advance - cx, (origin - height) + place[1] * height - cy)
    else:
        shift = (move[0] * upm, move[1] * upm)
    matrix = form_matrix(how, shift, advance, origin, height)
    return tuple(round(value, 4) if index < 4 else float(int(round(value))) for index, value in enumerate(matrix))


def form_rules(forms):
    """The substitutions FreeLab writes in vert (and vrt2), one per checked form it makes or names; vrt2's
    turned proportional glyphs (vrt2_only) are not vert's."""
    return [u"sub %s by %s;" % (f.name, f.target) for f in forms
            if f.checked and f.state in ("build", "glyph") and not getattr(f, "vrt2_only", False)]


class VTrim(object):
    """A glyph's vpal adjustment in vertical text: y placement and y advance, in font units. shown: the
    glyph vertical text sets (its vertical form where it has one)."""

    def __init__(self, code, name, shown, kind, value, top, bottom):
        self.code, self.name, self.shown, self.kind = code, name, shown, kind
        self.value, self.top, self.bottom = value, top, bottom  # its ink's top and bottom sidebearings now
        self.checked = True

    @property
    def char(self):
        return unichr_(self.code)


def vpal_value(box, sides, origin, height, upm):
    """(y placement, y advance) that give an ink box (x min, y min, x max, y max) the sidebearings sides
    (top, bottom; shares of the em) under the vertical origin, in an advance height."""
    top, bottom = sides[0] * upm, sides[1] * upm
    placement = origin - box[3] - top
    advance = bottom - height + (origin - box[1]) - placement
    return int(round(placement)), int(round(advance))


def plan_vpal(shown, model, upm, origin, height=None, kind_of=None, tolerance=TOLERANCE_UNITS):
    """vpal trims: shown [(code, name, glyph set, advance, ink box)], each a full-width kana or punctuation
    mark as vertical text sets it (its vertical form, or itself); the sides are the character's own in
    the corpus where it has them, else its kind's."""
    height = float(height or upm)
    kind_of = kind_of or spacing().kind_of
    table = model.get("vpal") or {}
    trims, done = [], set()
    for code, name, glyph, advance, box in sorted(shown, key=lambda s: s[0]):
        kind = kind_of(code)
        if glyph in done:
            continue  # (one value per glyph: a glyph encoded twice, as IBM Plex Sans KR's wave dash, got two)
        if kind is None or kind == "hangul" or box is None or advance < FULL_WIDTH_SHARE * upm:
            continue
        sides = table.get(u"U+%04X" % code) or table.get(kind)
        if not sides:
            continue
        value = vpal_value(box, sides, origin, height, upm)
        done.add(glyph)
        if abs(value[0]) < tolerance and abs(value[1] + value[0]) < tolerance:
            continue
        trims.append(VTrim(code, name, glyph, kind, value, int(round(origin - box[3])),
                           int(round(height - (origin - box[1])))))
    return trims


def vpal_rules(trims, own=(), unbuilt=()):
    """pos rules for the checked trims whose glyph the font's own vpal does not position, and that is
    in the font or built now (unbuilt: the planned forms that are not)."""
    return [u"pos %s <0 %d 0 %d>;" % (t.shown, t.value[0], t.value[1]) for t in trims
            if t.checked and t.shown not in own and t.shown not in unbuilt]


class Metric(object):
    """A vertical metric to set: key, its label, the value now (None: unset), the value suggested."""

    def __init__(self, key, label, now, value, count=None):
        self.key, self.label, self.now, self.value, self.count = key, label, now, value, count
        self.checked = now is None and value is not None and (count is None or count > 0)


def plan_metrics(upm, info, without_height, model=None):
    """The vertical metrics to set: the advance heights of the glyphs that have none (without_height:
    how many), and vhea's values (info: {field: value now or None}), each from the corpus's medians
    (shares of the em) where the font has none; a value the font has is listed, unchecked. The line gap
    is 0, as the owner chose (the corpus's median is 0.15 em; IBM Plex Sans JP and Source Han Sans have
    none)."""
    metrics = (model or {}).get("metrics") or {}
    found = [Metric("advance_height", u"Advance heights", None, int(round(upm * (metrics.get("advance_height") or 1.0))),
                    without_height)]
    for key, field, label in VHEA_FIELDS:
        share = VHEA_DEFAULTS[key] if key in OWN_DEFAULTS else metrics.get(key, VHEA_DEFAULTS[key])
        now = info.get(field)
        found.append(Metric(key, label, now, int(round(share * upm))))
    return found


def lookup_name(tag):
    """The name of FreeLab's lookup in a feature (FreeLab_vkrn)."""
    return u"FreeLab_%s" % tag


def reader():
    """Feature Code's reader, through CJK Spacing, or None where either cannot be loaded."""
    try:
        return spacing().feature_code_or_none()
    except Exception:
        return None


def feature_text(tag, old, rules):
    """A feature's code with FreeLab's block of rules before its closing brace: an older FreeLab block
    taken out, the rest kept, FontLab's automatic block handed back ("#/> feature"); or None where FreeLab
    cannot read the code safely (its own markers not in pairs, or the feature's braces not found): nothing
    is written then. Read by tokens through Feature Code, as CJK Spacing reads (spacing().feature_code:
    Codex reviews 5 and 6)."""
    fc = reader()
    if fc is None:  # (no reader: nothing written; the window says why: reader_problem)
        return None
    begin, end = BEGIN % tag, END % tag
    # FreeLab's rules in a lookup of their own: appended to the font's lookup, after its class pairs, a pair
    # was shadowed by them (live, IBM Plex Sans JP: "Single kern pair occurring after class kern pair in
    # feature 'vkrn'"). A later lookup's values add to an earlier one's: the font's own pairs, glyphs, and
    # forms are left out of FreeLab's rules, so nothing is doubled.
    name = lookup_name(tag)
    block = ([begin, u"  lookup %s {" % name] + [u"    %s" % rule for rule in rules] + [u"  } %s;" % name, end]
             if rules else [])
    try:
        fc.readable(old, tag)  # (taking a block out too: Codex review 7)
        text = fc.handed_back(fc.without_blocks(old, begin, end, tag)).rstrip(u"\r\n")
        if not block and fc.code_tokens(text):
            fc.readable(text, tag)
            return text + u"\n"
        return fc.insert_block(text, tag, block, title=FEATURE_TITLES.get(tag, tag), blank=True) + u"\n"
    except fc.FeatureCodeUnreadable:
        return None


CODE_TAGS = ("vert", "vrt2", "vpal", "vkrn")  # (the features written, each read for the font's own code too)


def read_prefix(features):
    """The font's feature prefix (its classes and lookups, which the features name), or None unread."""
    try:
        return features.get_prefix()
    except Exception:
        return None


UNCOMPARED = object()


def changed_features(features, texts, tags, prefix=UNCOMPARED):
    """What differs in the font from the code read with the list (texts: {tag: code}, a feature the font
    lacked then left out; prefix, when given: read_prefix's then): the tags, and "prefix". A write composed
    from that code would undo an edit made since (Feature Code's check before it writes). A feature that
    cannot be read counts as changed."""
    try:
        present = set(features.keys())
    except Exception:
        return list(tags)
    changed = []
    for tag in tags:
        try:
            now = features.get_feature(tag) if tag in present else None
        except Exception:
            changed.append(tag)
            continue
        if now != texts.get(tag):
            changed.append(tag)
    if prefix is not UNCOMPARED and read_prefix(features) != prefix:
        changed.append(u"prefix")
    return changed


def block_of(tag, text):
    """FreeLab's block of a feature, alone in a feature of its own (for the parser's check), or None."""
    fc = reader()
    inner = fc.block_text(text, BEGIN % tag, END % tag) if fc is not None else None  # (its markers as comments)
    if inner is None:
        return None
    return u"feature %s {\n%s} %s;\n" % (tag, inner, tag)


def vrt2_rules(forms, vrt2_extra=None, turned=()):
    """vrt2's rules: FreeLab's forms, its turned proportional glyphs (turned: Forms, vrt2_only, the
    checked ones), and, where FreeLab writes any, each substitution of the font's own vert that its own
    vrt2 does not make (vrt2_extra: {glyph: form}): applications that know vrt2 use it alone, and a vrt2
    FreeLab made would otherwise lose the font's own forms."""
    pairs = [(f.name, f.target) for f in list(forms) + list(turned)
             if f.checked and f.state in ("build", "glyph") and (f in turned or not getattr(f, "vrt2_only", False))]
    if not pairs:
        return []
    pairs += sorted((vrt2_extra or {}).items())
    rules, ruled = [], set()
    for source, target in pairs:  # (one rule per glyph, the first: a second would never apply)
        if source not in ruled:
            ruled.add(source)
            rules.append(u"sub %s by %s;" % (source, target))
    return rules


def texts_for(forms, trims, old_texts, forms_on=True, vpal_on=True, own_vpal=(), vrt2_extra=None, turned=(),
              kerns=(), vkrn_on=True, refused=None):
    """{tag: new code} for vert, vrt2, vpal, and vkrn: vert and vrt2 take the same substitutions (vrt2 is a
    superset of vert, and applications that know it use it alone), vrt2 the turned proportional glyphs
    too (turned: those of the option, when it is on), vpal the checked trims and vkrn the checked pairs
    (not those of a form left unbuilt: its glyph would be missing); only where the code changes. An old
    FreeLab block is taken out when nothing is left to write in it. vrt2_extra: the font's own vert
    substitutions its own vrt2 lacks (vrt2_rules). refused, when given: the tags of the features whose
    braces FreeLab cannot find (left as they are)."""
    new = {}
    unbuilt = set(f.target for f in list(forms) + list(turned) if f.state == "build" and not (f.checked and forms_on))
    kern_rules = vkrn_rules([k for k in kerns if k.first not in unbuilt and k.second not in unbuilt])
    for tag, on, rules in (("vert", forms_on, form_rules(forms)),
                           ("vrt2", forms_on, vrt2_rules(forms, vrt2_extra, turned)),
                           ("vpal", vpal_on, vpal_rules(trims, own_vpal, unbuilt)),
                           ("vkrn", vkrn_on, kern_rules)):
        rules = rules if on else []
        old = old_texts.get(tag)
        if rules or (BEGIN % tag) in (old or u""):
            text = feature_text(tag, old, rules)
            if text is None:  # (its braces not found: left as it is, and said)
                if refused is not None:
                    refused.append(tag)
                continue
            if text != old:
                new[tag] = text
    return new


# ---------------------------------------------------------------------------
# Vertical metrics for an exported font: FontLab 7's export writes none, so they are added to the font it
# exported, by tools/add_vertical_metrics.py (installed beside this script as add_vertical_metrics.module),
# from the FontLab font's own values
# ---------------------------------------------------------------------------

METRICS_SCRIPT = "add_vertical_metrics.module", os.path.join(os.pardir, "tools", "add_vertical_metrics.py")


def export_values(upm, origin, vhea, heights, codes, family=u"", master=u""):
    """The values add_vertical_metrics reads ("<exported font>.vertical.json"): the em, the vertical origin
    (the typographic ascender, as this tool takes it), vhea's ascender, descender, and line gap, and each
    glyph's advance height where it is not the em (heights: {glyph: height}), with each glyph's code
    points (codes: {glyph: [code points]}) to find a glyph the export renamed."""
    default = int(round(upm))
    return {"format": 1, "upm": default, "origin": int(round(origin)), "family": family, "master": master,
            "vhea": {"ascent": int(round(vhea[0])), "descent": int(round(vhea[1])), "lineGap": int(round(vhea[2]))},
            "default_height": default,
            "heights": dict((name, int(round(h))) for name, h in heights.items() if int(round(h)) != default),
            "codes": dict((name, list(found)) for name, found in codes.items() if found)}


def free_name(path, exists=os.path.exists):
    """path, or path with -2, -3 ... before its extension, the first that does not exist."""
    if not exists(path):
        return path
    stem, ext = os.path.splitext(path)
    number = 2
    while exists(u"%s-%d%s" % (stem, number, ext)):
        number += 1
    return u"%s-%d%s" % (stem, number, ext)


def values_file(script, path, values, exists=os.path.exists):
    """Where this font's values go beside the exported font at path, as (file, the file kept or None): the
    values file add_vertical_metrics reads by default (script.values_path), replaced only when it holds the
    values of this same font and master; one holding another's, or that cannot be read, is kept, and the
    values go to the next name (<font>.vertical-2.json ...) that is free or holds this font's and master's
    values, for --values."""
    first = script.values_path(path)
    stem, ext = os.path.splitext(first)
    candidate, number = first, 1
    while exists(candidate):
        try:
            old = script.load_values(candidate)
            if (old.get("family"), old.get("master")) == (values.get("family"), values.get("master")):
                break
        except Exception:
            pass
        number += 1
        candidate = u"%s-%d%s" % (stem, number, ext)
    return candidate, (first if candidate != first else None)


def load_metrics_script():
    """add_vertical_metrics, beside this script once installed (or in the repository's tools folder)."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    for name in METRICS_SCRIPT:
        path = os.path.normpath(os.path.join(here, name))
        if os.path.isfile(path):
            import types
            module = types.ModuleType("freelab_add_vertical_metrics")
            module.__file__ = path
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, os.path.basename(path), "exec", 0, True), module.__dict__)
            sys.modules["freelab_add_vertical_metrics"] = module  # (held: its functions keep their globals)
            return module
    raise IOError("add_vertical_metrics is not beside this script: reinstall FreeLab")


def baseline_y(top, origin, placement, scale):
    """Where a glyph's y = 0 goes in a picture (y down) whose square starts at top, its vertical origin at
    the square's top: origin units under it, less the glyph's y placement (vpal's, upward in the font:
    up on screen too)."""
    return top + (origin - placement) * scale


# ---------------------------------------------------------------------------
# vrt2's turned proportional glyphs (an option, off unless asked: two thirds of the corpus's fonts leave
# them to applications)
# ---------------------------------------------------------------------------

TURNED_SUFFIX = u".vrt2"


def turned_matrix(upm, origin, move=(0.0, 0.0), how="rotated"):
    """A proportional glyph turned a quarter clockwise for vertical text, about the center of the em's
    square (not its own: its baseline goes to the same place across every turned glyph, as the
    descender's depth from the square's left), then moved (shares of the em)."""
    return tuple(round(value, 4) if index < 4 else float(int(round(value)))
                 for index, value in enumerate(form_matrix(how, (move[0] * upm, move[1] * upm), upm, origin, upm)))


def plan_turned(glyphs, names, model, upm, origin, own=None, ours=None):
    """vrt2's turned copies of the font's proportional glyphs: glyphs [(code, name, advance, ink box)],
    the characters the corpus's fonts that turn proportional glyphs mostly turn (model "turned"), each a
    glyph narrower than FULL_WIDTH_SHARE of the em; own: {glyph: form} the font's own vrt2 makes
    (left alone), ours: {glyph: form} of FreeLab's vrt2 block. Forms, each vrt2_only."""
    turned = (model or {}).get("turned") or {}
    codes, how, move = turned.get("codes") or {}, turned.get("how") or "rotated", turned.get("move") or (0.0, 0.0)
    names, own, ours = set(names), own or {}, ours or {}
    found, done = [], set()
    for code, name, advance, box in sorted(glyphs, key=lambda g: g[0]):
        share = codes.get(u"U+%04X" % code)
        if (share is None or share < MIN_SHARE or advance >= FULL_WIDTH_SHARE * upm or box is None or name in own
                or name in done):
            continue  # (a glyph encoded twice is turned once)
        done.add(name)
        target = ours.get(name) or name + TURNED_SUFFIX
        state = "glyph" if target in names else "build"
        form = Form(code, name, how, target, state, turned_matrix(upm, origin, move, how), core=False,
                    ours=name in ours)
        form.vrt2_only, form.checked = True, True
        found.append(form)
    return found


# ---------------------------------------------------------------------------
# vkrn: vertical kerning, the vertical counterpart of kern for proportional vertical text (vpal on)
# ---------------------------------------------------------------------------

VKRN_BANDS = 16  # the column's width cut into this many bands, each glyph's ink read in each


def placed_profile(bands, origin, height, value=(0, 0)):
    """A glyph as proportional vertical text sets it: per band of its column, (the ink's depth under the
    square's top, its height over the square's bottom) or None where it has no ink, and its square's
    height; bands: (y min, y max) of its ink per band, or None; value: its vpal (y placement, y
    advance)."""
    placement, advance = value
    cell = float(height + advance)
    profile = []
    for band in bands:
        if band is None:
            profile.append(None)
        else:
            profile.append((origin - band[1] - placement, cell - (origin - band[0] - placement)))
    return profile, cell


def pair_gap(upper, lower, cap):
    """The white between a glyph and the next one under it, as an eye reads it: the mean, over the bands
    where either has ink, of the white down from the upper glyph's ink to the lower one's (the whole
    square where one has none), each band's white counted up to cap. upper, lower: placed_profile's."""
    (top_profile, top_cell), (bottom_profile, bottom_cell) = upper, lower
    gaps = []
    for above, below in zip(top_profile, bottom_profile):
        if above is None and below is None:
            continue
        gaps.append(min(cap, (above[1] if above else top_cell) + (below[0] if below else bottom_cell)))
    return sum(gaps) / float(len(gaps)) if gaps else None


def gap_scores(gaps):
    """{pair: score} of a font's pairs' whites (gaps: {pair: white}): how much less white a pair has than
    the font's usual (their median), in the font's own spread (their interquartile range over 1.349, as
    a standard deviation; a unit at least). A pair whiter than usual scores below 0, and is drawn
    together. The trainer and the tool score alike, so the corpus's factor carries over to any font."""
    values = sorted(gaps.values())
    if not values:
        return {}
    usual = values[len(values) // 2]
    spread = max(1.0, (values[(3 * len(values)) // 4] - values[len(values) // 4]) / 1.349)
    return dict((pair, (usual - gap) / spread) for pair, gap in gaps.items())


class VKern(object):
    """A vertical pair's kerning: the upper glyph's y advance changed by value (font units); fonts: how many
    of the corpus's fonts kern the pair."""

    def __init__(self, first_code, first, second_code, second, value, fonts):
        self.first_code, self.first, self.second_code, self.second = first_code, first, second_code, second
        self.value, self.fonts = value, fonts
        self.checked = True

    @property
    def name(self):
        return self.first

    @property
    def chars(self):
        return unichr_(self.first_code) + unichr_(self.second_code)


VKRN_LEAST = 0.01  # a pair kerned by less than this share of the em is left alone (the corpus's lower quartile)


def plan_vkrn(pairs, settings, upm, own=()):
    """vkrn for the pairs the corpus's fonts kern (pairs: [(first code, first glyph, second code, second
    glyph)], each glyph as vertical text sets it, both full width): each the median of those fonts' values
    for it (settings, model "vkrn": "values", {"XXXX YYYY": [share of the em, fonts]}), scaled to the em.
    Measured on the font's own glyphs, the white between a pair predicted the fonts' values too weakly to
    use (docs/VERTICAL.md): the corpus's practice is taken as it is. own: the pairs the font's own vkrn
    sets (left alone)."""
    table = settings.get("values") or {}
    found, seen = [], set()
    for first_code, first, second_code, second in pairs:
        entry = table.get(u"%04X %04X" % (first_code, second_code))
        if entry is None or (first, second) in own or (first, second) in seen:
            continue
        seen.add((first, second))
        value = int(round(entry[0] * upm))
        if abs(value) >= max(1, VKRN_LEAST * upm):
            found.append(VKern(first_code, first, second_code, second, value, entry[1]))
    return found


def vkrn_rules(kerns):
    return [u"pos %s %s <0 0 0 %d>;" % (k.first, k.second, k.value) for k in kerns if k.checked]


# (a glyph name starts with no digit or hyphen: the single position "pos @vpal -500" is no pair of @vpal and "-50")
PAIR_POSITION = re.compile(u"^\\s*(?:enum\\s+)?pos(?:ition)?\\s+(\\[[^\\]]*\\]|@[A-Za-z0-9_.\\-]+|[A-Za-z_.][A-Za-z0-9_.\\-]*)\\s+"
                           u"(\\[[^\\]]*\\]|@[A-Za-z0-9_.\\-]+|[A-Za-z_.][A-Za-z0-9_.\\-]*)\\s*(?:<|-?[0-9])")


def own_pairs(tag, text, classes=None, lookups=None):
    """The glyph pairs a feature's own code (outside FreeLab's block) kerns: pos a b -20; pos a b <0 0 0
    -20>; pos @one @two ...; (classes and lookups as own_positions reads them)."""
    known = dict(classes or {})
    known.update(code_classes(text))
    for body in (lookups or {}).values():
        known.update(code_classes(body))
    found = set()
    for statement in statements(tag, text, lookups):
        match = PAIR_POSITION.match(statement)
        if match:
            for first in members(match.group(1), known):
                for second in members(match.group(2), known):
                    found.add((first, second))
    return found


def own_position_values(tag, text, classes=None, lookups=None):
    """{glyph: (y placement, y advance)} of the single values a feature's own code gives (pos a <0 -2 0
    -13>;, or pos a -500;: a number alone is the advance along the feature's direction, the y advance in a
    vertical feature), for measuring glyphs as the font's own vpal sets them."""
    found = {}
    for glyph, value in spacing().single_positions(tag, text, classes, lookups, BEGIN, END):
        record = re.match(u"^<\\s*(-?[0-9]+)\\s+(-?[0-9]+)\\s+(-?[0-9]+)\\s+(-?[0-9]+)\\s*>$", value)
        if record:
            found.setdefault(glyph, (int(record.group(2)), int(record.group(4))))
        elif not value.startswith(u"<"):
            found.setdefault(glyph, (0, int(value)))
    return found


def codes_of(glyph):
    """Every code point a glyph is encoded at (fgGlyph.unicodes; its first, unicode, where FontLab gives
    no list): a CJK font encodes 日 at the Kangxi radical U+2F47 too, and FontLab's unicode gives that
    one first (IBM Plex Sans JP: 日 月 玄 黄 辰), so the ideographs went missing from the previews."""
    try:
        codes = [int(code) for code in (glyph.unicodes or [])]
    except Exception:
        codes = []
    if not codes and getattr(glyph, "unicode", None):
        codes = [int(glyph.unicode)]
    return codes


def code_map(glyphs):
    """{code point: glyph name} of the font's glyphs, every code point of each (the first glyph at a code
    point wins, as in a cmap)."""
    found = {}
    for glyph in glyphs:
        for code in codes_of(glyph):
            found.setdefault(code, u"%s" % glyph.name)
    return found


def code_points(text):
    """[(code point, its characters in the text)] of a text, a pair of UTF-16 surrogates read as one: FontLab's
    narrow Python 2 splits a character past U+FFFF (𠮷) in two."""
    found, at = [], 0
    while at < len(text):
        code = ord(text[at])
        if 0xD800 <= code < 0xDC00 and at + 1 < len(text) and 0xDC00 <= ord(text[at + 1]) < 0xE000:
            found.append((0x10000 + ((code - 0xD800) << 10) + ord(text[at + 1]) - 0xDC00, text[at:at + 2]))
            at += 2
        else:
            found.append((code, text[at]))
            at += 1
    return found


def preview_column(text, names, own, chosen, trims, kerns, height, upm):
    """A sample as vertical text sets it: ([(glyph or None, transform or None, y placement, y advance
    change)], its characters, each one's height in ems). names: {code point: glyph}; own: {glyph: its
    form} of the font's code; chosen: {glyph: Form} checked; trims: {glyph shown: (y placement, y
    advance)} of vpal; kerns: {(upper glyph shown, lower glyph shown): y advance change} of vkrn, which
    the upper glyph takes in its height. A character the font lacks is left out, as CJK Spacing's previews
    leave it (the owner, of Noto Sans's: rows of empty boxes, where CJK Spacing "only shows the glyphs it
    can display")."""
    placed, chars, heights, previous = [], [], [], None
    for code, ch in code_points(text):
        if ch.isspace():
            continue
        name = names.get(code)
        if name is None:  # (a character the font lacks)
            previous = None
            continue
        if name in own:
            item = (own[name], None, 0, 0)
        elif name in chosen:
            form = chosen[name]
            item = (name, form.matrix, 0, 0) if form.state == "build" else (form.target, None, 0, 0)
        else:
            item = (name, None, 0, 0)
        shown = chosen[name].target if name in chosen else item[0]
        value = trims.get(shown)
        if value is not None:
            item = (item[0], item[1], value[0], value[1])
        kern = kerns.get((previous, shown)) if placed else None
        if kern:  # (vkrn: the glyph above takes it, in its height; in ems, as every height here)
            last = placed[-1]
            placed[-1] = (last[0], last[1], last[2], last[3] + kern)
            heights[-1] += kern / float(upm)
        previous = shown
        placed.append(item)
        chars.append(ch)
        heights.append((height + item[3]) / float(upm))
    return placed, chars, heights


# What a sample's characters the font lacks are, for the previews' note: (name for one, for many, ranges)
SAMPLE_KINDS = ((u"Hangul syllable", u"Hangul syllables", ((0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F))),
                (u"kana", u"kana", ((0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F))),
                (u"ideograph", u"ideographs", ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
                                               (0x20000, 0x3FFFF))),
                (u"CJK punctuation mark", u"CJK punctuation marks", ((0x3000, 0x303F), (0xFE10, 0xFE1F),
                                                                     (0xFE30, 0xFE4F), (0xFF00, 0xFF65))))
SAMPLE_SHOWN_MOST = 6  # characters named in the note's parentheses at most


def character_words(chars, most=SAMPLE_SHOWN_MOST):
    """A few characters named in words, the distinct ones in their order: a punctuation mark or a symbol
    by its name ("the comma", "the period", "the left corner bracket"), anything else between quotation
    marks; "and others" past most. A bare mark in parentheses, "(, .)", read oddly (live pass)."""
    import unicodedata
    distinct = []
    for ch in chars:
        if ch not in distinct:
            distinct.append(ch)
    words = []
    for ch in distinct[:most]:
        try:
            kind, name = unicodedata.category(ch), unicodedata.name(ch, u"")
        except (TypeError, ValueError):
            kind, name = u"", u""
        if kind[:1] in (u"P", u"S") and name:
            words.append(u"the " + name.lower().replace(u"full stop", u"period"))
        else:
            words.append(u"\N{LEFT DOUBLE QUOTATION MARK}%s\N{RIGHT DOUBLE QUOTATION MARK}" % ch)
    if len(distinct) > most:
        words.append(u"others")
    if len(words) <= 2:
        return u" and ".join(words)
    return u"%s, and %s" % (u", ".join(words[:-1]), words[-1])


def preview_note(text, names):
    """What the previews show of a sample, where the font lacks some of its characters (owner's report
    148: on Bellefair, the Korean sample's previews held a comma and a period only, and nothing said
    why): the characters the font has, and what it lacks, by kind (its Hangul, its CJK punctuation
    marks, named). Empty where the font has every character. names: {code point: glyph}."""
    shown, lacking = [], []
    for code, ch in code_points(text):
        if ch.isspace():
            continue
        (shown if code in names else lacking).append((code, ch))
    if not lacking:
        return u""
    listed = character_words  # (the live pass: "(, .)" read oddly; named now, "(the comma and the period)")

    kinds, sorted_out = [], 0
    for one, many, ranges in SAMPLE_KINDS:
        found = [ch for code, ch in lacking if any(low <= code <= high for low, high in ranges)]
        if found:
            sorted_out += len(found)
            words = counted(len(found), one, many)
            if one.startswith(u"CJK punctuation"):  # (named: the marks a vertical font turns or moves)
                words += u" (%s)" % listed(found)
            kinds.append(words)
    if len(lacking) > sorted_out:
        kinds.append(counted(len(lacking) - sorted_out, u"other character"))
    lacks = kinds[0] if len(kinds) == 1 else (u"%s and %s" % tuple(kinds) if len(kinds) == 2 else
                                              u"%s, and %s" % (u", ".join(kinds[:-1]), kinds[-1]))
    if not shown:
        return u"The font has none of the sample's characters, so the previews are empty: it lacks %s." % lacks
    return u"The previews show only the %s of the sample the font has (%s): it lacks %s." % (
        counted(len(shown), u"character"), listed([ch for _, ch in shown]), lacks)


def fitting_em(chars, heights_at, width, height, largest, smallest=12):
    """The largest em (pixels, from largest down to smallest) at which a sample's columns fit a pane of
    width by height: its columns as vertical_lines breaks them, each step = em * COLUMN_STEP wide.
    heights_at(em): each character's height at that em. The smallest when none fits."""
    em = largest
    while em > smallest:
        room = height - 8
        if room > em:
            columns = len(vertical_lines(chars, heights_at(em), room)) if chars else 0
            if columns * em * COLUMN_STEP + 4 <= width - 8:
                return em
        em -= 2
    return smallest


COLUMN_STEP = 1.15  # a column's width, in ems


def vertical_lines(chars, heights, room):
    """The columns of a vertical sample: [(start, end)], as CJK Spacing breaks lines (kinsoku kept)."""
    return spacing().break_lines(chars, heights, room)


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 32
PREVIEW_EM = 40  # pixels per em, the previews
TITLE = u"FreeLab CJK Vertical"


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: the dialogs' shared helpers."""
    held = sys.modules.get(AUTO_KERNING_MODULE)
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    try:
        stamp = os.path.getmtime(os.path.join(here, AUTO_KERNING_FILE))
    except OSError:
        stamp = None
    if held is not None and hasattr(held, "load_sibling") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    module = load_script(AUTO_KERNING_FILE, AUTO_KERNING_MODULE) if held is None or not hasattr(held, "load_sibling") \
        else spacing().load_auto_kerning()
    return module


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


# Said after writing vertical metrics: tried live (2026-11-14, IBM Plex Sans KR), FontLab 7.2's export as
# OpenType TT and OpenType PS wrote no vhea, vmtx, or VORG table, with every layer's advance height and vhea's
# values in the font info set, and with a table vhea block in the feature prefix (compiled, then left out);
# a table vmtx block stopped the features compiling ("VertOriginY redefined").
EXPORT_NOTE = (u"FontLab 7's export writes no vhea, vmtx, or VORG table (tried as OpenType TT and PS): the advance "
               u"heights and vhea values stay in the font. After exporting it, <i>Add vertical metrics to an "
               u"exported font</i> adds them to a copy of the font FontLab exported.")

# Long work under a progress bar, as Font Check's: its steps, each with the share of the bar at which it
# ends, from live timings on IBM Plex Sans JP (9,505 glyphs, 2026-11-15, with the bar): the list read in
# 1.0 s (the font read 0.6 s), a write in 3.8 s (FontLab's update 0.5 s, vhea 1.3 s, the list read again
# 1.7 s; the undo step took 0.1 s, once 1.6 s), and vertical metrics added to its TrueType font in 7.4 s (the
# glyphs measured 3.5 to 6.1 s, saving 0.1 s) and to its CFF export in 7.8 s (measured 3.3 s, saving 3.1 s;
# 13 s before save_with_tables, which copies the other tables as they are).
READ_STEP, LIST_STEP, PREVIEW_STEP = u"Reading the font", u"Listing", u"Drawing the previews"
LIST_STEPS = ((READ_STEP, 0.6), (LIST_STEP, 0.95), (PREVIEW_STEP, 1.0))
SHOW_STEPS = ((LIST_STEP, 0.95), (PREVIEW_STEP, 1.0))
UNDO_STEP, BUILD_STEP, CODE_STEP = u"Opening an undo step", u"Building the vertical forms", u"Writing the code"
HEIGHTS_STEP, UPDATE_STEP, VHEA_STEP = u"Setting advance heights", u"Updating the font", u"Writing vhea"
WRITE_STEPS = ((UNDO_STEP, 0.05), (BUILD_STEP, 0.1), (CODE_STEP, 0.12), (HEIGHTS_STEP, 0.15), (UPDATE_STEP, 0.25),
               (VHEA_STEP, 0.5), (READ_STEP, 0.84), (LIST_STEP, 0.97), (PREVIEW_STEP, 1.0))
VALUES_STEP, OPEN_STEP, SAVE_STEP, CHECK_STEP = (u"Reading this font's values", u"Reading the exported font",
                                                 u"Saving", u"Checking")
# (add_vertical_metrics.add_tables reports its own steps by key)
SCRIPT_STEPS = {"match": u"Matching glyphs", "measure": u"Measuring the glyphs", "build": u"Building the tables"}
EXPORT_STEPS = ((VALUES_STEP, 0.12), (OPEN_STEP, 0.13), (SCRIPT_STEPS["match"], 0.14), (SCRIPT_STEPS["measure"], 0.95),
                (SCRIPT_STEPS["build"], 0.96), (SAVE_STEP, 0.98), (CHECK_STEP, 1.0))
CFF_EXPORT_STEPS = ((VALUES_STEP, 0.12), (OPEN_STEP, 0.13), (SCRIPT_STEPS["match"], 0.14), (SCRIPT_STEPS["measure"], 0.56),
                    (SCRIPT_STEPS["build"], 0.57), (SAVE_STEP, 0.96), (CHECK_STEP, 1.0))
SHOW_AFTER = 0.3  # seconds: the list read again (an undo, a check box) shows the bar only when it takes longer
PUMP_SECONDS = 0.05  # the window redrawn at most this often during a step
ROWS_PER_STEP = 100  # rows listed between two moves of the bar
BAR_RANGE = 1000
BAR_GREEN = ((120, 200, 120), (30, 120, 40))  # ak.LOG_COLORS["done"], should the shared module not have it
# On the bar itself, never on the dialog: a thin bar, its chunk in the suite's "done" green (Font Check's)
BAR_SHEET = (u"QProgressBar { border: 1px solid rgba(128, 128, 128, 140); border-radius: 3px; "
             u"background: transparent; min-height: 10px; max-height: 10px; } "
             u"QProgressBar::chunk { background-color: rgb(%d, %d, %d); border-radius: 2px; }")


def bar_value(steps, label, part=0.0):
    """How far the bar is, 0 to 1, at this part (0 to 1) of the step of that label; None for a step that is
    not one of these steps."""
    start = 0.0
    for name, end in steps:
        if name == label:
            return start + (end - start) * min(max(float(part), 0.0), 1.0)
        start = end
    return None


def pump_events(QtCore, QtGui):
    """The window redrawn during long work, the user's clicks and keys left waiting until it is over (Feature
    Code's pump_events): nothing may act on the font halfway."""
    flag = getattr(getattr(QtCore, "QEventLoop", None), "ExcludeUserInputEvents", None)
    if flag is None:
        QtGui.QApplication.processEvents()
    else:
        QtGui.QApplication.processEvents(flag)


HELP = u"""<b>FreeLab CJK Vertical</b><br>
Gives the font what vertical text needs of it: vertical forms (vert and vrt2), proportional heights
(vpal), vertical kerning (vkrn), and vertical metrics. Nothing is written until you click
<i>Write</i>.<br><br>
<b>The list</b>: the characters that turn in vertical text (brackets, dashes, the long vowel mark) and
those that move to the upper right of their square (small kana, the comma and full stop), as the
open-licensed CJK fonts make them; each form is built as a component of its glyph, turned or moved.
A form the font has drawn (a .vert glyph, or the character's vertical presentation form) is used as
it is; one the font's own code makes is listed and left alone. Then each full-width kana and
punctuation mark's vpal trim (its top and bottom sidebearings, as those fonts set them), the vkrn
pairs (the pairs those fonts kern, a kana before the comma or full stop above all, each by their
median value), and the vertical metrics: advance heights for the glyphs
without one, and vhea's ascender, descender, and line gap (0; the corpus's median is 0.15 em).
FontLab 7's export writes no vhea, vmtx, or VORG table: these stay in the font (its .vfc), and
<i>Add vertical metrics to an exported font</i> adds them to a copy of the font FontLab exported
(.vert before its extension; the exported font is not changed).
<i>Turned proportional glyphs (vrt2)</i>, off unless checked, adds turned copies of the font's
proportional glyphs to vrt2, as a third of those fonts do. Checked rows are written.<br>
<b>The previews</b>: the sample set in vertical columns, right to left, as the font's own code sets
it, and with what is checked.<br>
<i>Restore suggestions</i> puts every check back as the list first came; <i>Put back vhea</i> puts
the font info back as it was before the last write (FontLab's History does not hold it).<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""


def mark_modified(package):
    """The font marked modified (ofChanged): a script's write leaves it unmarked, and FontLab would close it
    without asking to save. The font info alone needs no step of FontLab's History (it is not in it)."""
    try:
        package.setFlag(2, True)
    except Exception:
        pass


class CJKVerticalDialog(object):
    COLUMNS = ("Glyph", "Name", "Vertical form", "How", "Now", "After")
    # (long work's state, also for a dialog object made without its window: tests)
    busy, busy_shown, run_due, busy_steps, busy_now, busy_since, pumped = False, False, False, (), None, 0.0, 0.0

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        self.cj = spacing()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle(TITLE)
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(ak.separator())
        self.log = ak.Log()
        row = QtGui.QHBoxLayout()
        self.forms_box = QtGui.QCheckBox(u"Vertical forms (vert, vrt2)")
        self.forms_box.setChecked(True)
        self.forms_box.setWhatsThis(u"Builds the checked vertical forms and writes vert and vrt2 for them.")
        self.vpal_box = QtGui.QCheckBox(u"Proportional heights (vpal)")
        self.vpal_box.setChecked(True)
        self.vpal_box.setWhatsThis(u"Writes vpal: kana and punctuation trimmed to their ink and the corpus's top and "
                                   u"bottom sidebearings in vertical text.")
        self.vkrn_box = QtGui.QCheckBox(u"Vertical kerning (vkrn)")
        self.vkrn_box.setChecked(True)
        self.vkrn_box.setWhatsThis(u"Writes vkrn for the pairs the corpus's fonts kern in vertical text (kana before the "
                                   u"comma and full stop, and kana pairs), each by their median value, scaled to the "
                                   u"em: a starting point, not measured on the font's glyphs.")
        self.turned_box = QtGui.QCheckBox(u"Turned proportional glyphs (vrt2)")
        self.turned_box.setChecked(False)
        self.turned_box.setWhatsThis(u"Builds turned copies of the font's proportional glyphs (Latin, figures, half-width "
                                     u"forms) for vrt2, as a third of the corpus's fonts do; the others leave them to "
                                     u"applications, which turn them themselves. Off unless checked.")
        self.metrics_box = QtGui.QCheckBox(u"Vertical metrics")
        self.metrics_box.setChecked(True)
        self.metrics_box.setWhatsThis(u"Sets the checked vertical metrics: advance heights for the glyphs without one, and "
                                      u"vhea's values in the font info (its line gap 0; the corpus's median is 0.15 em).")
        for box in (self.forms_box, self.vpal_box, self.vkrn_box, self.turned_box, self.metrics_box):
            row.addWidget(box)
        row.addStretch(1)
        layout.addLayout(row)
        # A progress bar over the list while long work runs (Font Check's): the step's name beside it, its
        # chunk in the log's "done" green, left alone by dark mode; hidden otherwise
        self.busy_row = QtGui.QWidget()
        busy_layout = QtGui.QHBoxLayout(self.busy_row)
        busy_layout.setContentsMargins(0, 2, 0, 2)
        self.busy_step = QtGui.QLabel(u"")
        self.busy_bar = QtGui.QProgressBar()
        try:
            self.busy_bar.setRange(0, BAR_RANGE)
            self.busy_bar.setValue(0)
            self.busy_bar.setTextVisible(False)  # (the step's name stands beside it)
            self.busy_bar.setProperty(ak.LEAVE_ALONE_PROP, True)
        except Exception:
            pass
        try:  # (room for the longest step's name: the bar's left edge stays put from one step to the next)
            longest = max([label for steps in (LIST_STEPS, WRITE_STEPS, EXPORT_STEPS) for label, _ in steps], key=len)
            self.busy_step.setMinimumWidth(int(QtGui.QFontMetrics(self.busy_step.font).width(
                u"%s\N{HORIZONTAL ELLIPSIS}" % longest)) + 8)
        except Exception:
            pass
        busy_help = (u"How far the work is: reading the font and listing it, writing, or adding vertical metrics to "
                     u"an exported font. The window waits for it; it goes away when the work is over.")
        self.busy_bar.setWhatsThis(busy_help)
        self.busy_step.setWhatsThis(busy_help)
        busy_layout.addWidget(self.busy_step)
        busy_layout.addWidget(self.busy_bar, 1)
        self.busy_row.setVisible(False)
        layout.addWidget(self.busy_row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.table_layout(self.tree)
        self.tree.setWhatsThis(u"The vertical forms (the picture shows the form), the vpal trims (y placement and y "
                               u"advance), and the vertical metrics, each with its value now and after. Checked rows "
                               u"are written. Double-click a glyph to see it in a <i>Glyph</i> window.")
        layout.addWidget(self.tree, 1)
        sample_row = QtGui.QHBoxLayout()
        self.sample_label = QtGui.QLabel(u"Sample:")
        sample_row.addWidget(self.sample_label)
        # One sample per writing system, each set vertically: FreeLab's Japanese sentence (brackets, small
        # kana, the long vowel mark, a dash, the comma and full stop: each turns or moves) in place of the
        # Iroha, which has none of the small kana or the long vowel mark; no horizontal view (vertical forms
        # do nothing across, and CJK Spacing shows text across)
        self.samples = [(u"ja", u"Japanese", SAMPLE_JA)] + [s for s in self.cj.SAMPLES if s[0] != "ja"]
        self.sample_box = QtGui.QComboBox()
        for _, label, _ in self.samples:
            self.sample_box.addItem(label)
        self.sample_box.setWhatsThis(u"A sample per writing system; the field beside it takes text of your own.")
        sample_row.addWidget(self.sample_box)
        self.sample = QtGui.QLineEdit(SAMPLE_JA)
        self.sample.setWhatsThis(u"The text the previews set in vertical columns, right to left.")
        sample_row.addWidget(self.sample, 1)
        layout.addLayout(sample_row)
        previews = QtGui.QHBoxLayout()
        self.previews, self.preview_captions = [], []
        for caption in (u"Now (the font's own code)", u"With what is checked"):
            column = QtGui.QVBoxLayout()
            title = QtGui.QLabel(caption)
            title.setEnabled(False)  # (drawn in the quiet text color)
            column.addWidget(title)
            self.preview_captions.append(title)
            label = QtGui.QLabel()
            label.setProperty(ak.LEAVE_ALONE_PROP, True)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumHeight(int(PREVIEW_EM * 6))
            try:
                label.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
            except Exception:
                pass
            label.setToolTip(caption)
            column.addWidget(label, 1)
            previews.addLayout(column, 1)
            self.previews.append(label)
        layout.addLayout(previews)
        # What the previews show of the sample where the font lacks some of it (preview_note), else hidden
        self.preview_note = QtGui.QLabel(u"")
        self.preview_note.setWordWrap(True)
        self.preview_note.setEnabled(False)  # (drawn in the quiet text color, as the captions)
        self.preview_note.setWhatsThis(u"The previews leave out the sample's characters the font lacks: this line "
                                       u"says which they show, and which are missing.")
        self.preview_note.setVisible(False)
        layout.addWidget(self.preview_note)
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every check back as the list first came.")
        self.put_back_button = QtGui.QPushButton("Put back vhea")
        self.put_back_button.setWhatsThis(u"Puts vhea's values in the font info back as they were before the last write "
                                          u"(FontLab's <i>Edit &gt; Undo</i> does not take the font info back).")
        self.export_button = QtGui.QPushButton(u"Add vertical metrics to an exported font\N{HORIZONTAL ELLIPSIS}")
        self.export_button.setWhatsThis(u"FontLab 7's export writes no vhea, vmtx, or VORG table. Pick the font FontLab "
                                        u"exported (.otf or .ttf): a copy of it, named .vert, gets them from this "
                                        u"font's values (each glyph's advance height, vhea's values, the vertical "
                                        u"origin at the typographic ascender; VORG for a CFF font). The exported "
                                        u"font is not changed.")
        self.write_button = QtGui.QPushButton("Write")
        self.write_button.setWhatsThis(u"Builds the checked vertical forms, writes vert, vrt2, and vpal between FreeLab's "
                                       u"marker lines (the rest of each feature kept), and sets the checked vertical "
                                       u"metrics. <i>Edit &gt; Undo</i> takes the glyphs, the code, and the advance "
                                       u"heights back; <i>Put back vhea</i> the font info.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button, self.put_back_button, self.export_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.compile_box = ak.compile_box()
        buttons.addWidget(self.compile_box)
        buttons.addWidget(self.write_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.put_back_button.connect("clicked()", self.put_back_values)
        self.export_button.connect("clicked()", lambda: self.add_metrics_to_export())
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        for box in (self.forms_box, self.vpal_box, self.vkrn_box, self.turned_box, self.metrics_box):
            box.connect("toggled(bool)", lambda on: self.toggled())
        self.sample.connect("textChanged(QString)", lambda text: self.draw_previews())
        self.sample_box.connect("activated(int)", lambda index: self.sample.setText(self.samples[index][2]))
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window(item))
        self.package = None
        self.forms, self.trims, self.metrics, self.first_checks = [], [], [], []
        self.turned, self.kerns, self.own_vkrn = [], [], set()
        self.texts, self.names, self.own_vpal, self.boxes, self.own_vert = {}, [], set(), {}, {}
        self.char_names, self.prefix, self.classes, self.holding = {}, None, {}, False
        self.font_vert, self.vrt2_extra = {}, {}
        self.origin, self.height = 880.0, 1000.0
        self.seen_history, self.busy, self.buttons_due, self.put_back = None, False, False, None
        self.model = load_model()
        ak.add_tools_button(dialog, "CJK Vertical", self.log)  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.history_timer = ak.watch_history(self)
        self.flagging = ak.flag_menu(self.tree, self, self.flag_names, self.row_names)
        self.watchers = []
        try:  # the check boxes drawn plain to see in either palette (the list's pictures stay unmapped)
            fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            self.watchers.append(fc.watch_check_boxes(self.dialog, [self.tree]))
        except Exception:
            pass
        self.preview_room = None
        self.watch_previews()

    def watch_previews(self):
        """The previews set again when their height changes (their columns break to fit it)."""
        QtCore, QtGui = _qt()
        owner = self

        class Watcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize
                        owner.redraw_timer.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        try:
            # (parents given: Qt deletes them with the window, never PythonQt at a random moment)
            self.redraw_timer = QtCore.QTimer(self.dialog)
            self.redraw_timer.setSingleShot(True)
            self.redraw_timer.setInterval(80)
            self.redraw_timer.connect("timeout()", self.previews_resized)
            watcher = Watcher(self.previews[0])
            self.previews[0].installEventFilter(watcher)
            self.watchers.append(watcher)
        except Exception:
            pass

    def previews_resized(self):
        if self.busy:
            return  # (drawn again once the work is over: set_busy)
        if (self.room(), self.pane_width(self.previews[0])) != self.preview_room:  # (a pane taller or wider)
            self.draw_previews()

    def pane_width(self, label):
        """A preview's width in pixels (None where Qt does not say): its columns are fitted to it, and never
        drawn past it into the other preview."""
        try:
            return int(self.ak._property(label, "width"))
        except Exception:
            return None

    def room(self):
        """The previews' height in pixels, for their columns (None where Qt does not say)."""
        try:
            height = int(self.ak._property(self.previews[0], "height"))
            return height - 8 if height > 32 else None  # (a shorter pane: the em shrinks to fit it, fitting_em)
        except Exception:
            return None

    # -- long work ------------------------------------------------------------------

    def busy_widgets(self):
        """What is grayed while long work runs (Close is not: a click waits for the work, then closes)."""
        return [getattr(self, name, None) for name in (
            "tree", "forms_box", "vpal_box", "vkrn_box", "turned_box", "metrics_box", "compile_box", "sample_box",
            "sample", "all_button", "none_button", "restore_button", "put_back_button", "export_button",
            "write_button")]

    def set_busy(self, on, steps=(), at_once=False):
        """Long work begun (its steps: (label, share of the bar at its end)) or over. While busy, the History
        watcher, dark mode, and the window's release wait, and so does another read of the list (run once the
        work is over). The bar and the grayed controls show at once (at_once: a write, an export), or once
        the work has taken SHOW_AFTER (a list read again for a small font never flickers). Never raises."""
        self.busy, self.holding = bool(on), False
        self.busy_steps, self.busy_now = (tuple(steps) if on else ()), None
        self.busy_since, self.pumped = time.time(), 0.0
        if on:
            if at_once:
                self.show_busy()
            return
        if self.busy_shown:
            self.busy_shown = False
            try:
                self.busy_row.setVisible(False)
                for widget in self.busy_widgets():
                    if widget is not None:
                        self.ak.enable(widget, True)
            except Exception:
                pass
            for restore in (lambda: self.show_font_parts(self.package is not None), self.update_buttons,
                            self.update_put_back):
                try:  # (each control as the font and the checks want it)
                    restore()
                except Exception:
                    pass
        elif getattr(self, "buttons_waiting", False):  # (a quick list, no bar: the buttons it held off set now)
            try:
                self.update_buttons()
            except Exception:
                pass
        if self.run_due:
            self.run_due = False
            try:
                QtCore, QtGui = _qt()
                QtCore.QTimer.singleShot(0, self.run)
            except Exception:
                pass

    def show_busy(self):
        """The bar shown and the controls grayed, painted at once."""
        if self.busy_shown:
            return
        self.busy_shown = True
        try:
            for widget in self.busy_widgets():
                if widget is not None:
                    self.ak.enable(widget, False)
            self.busy_bar.setStyleSheet(self.bar_sheet())  # (the palette may have changed since)
            self.busy_bar.setValue(0)
            self.busy_row.setVisible(True)
        except Exception:
            pass
        self.pump(force=True)

    def bar_sheet(self):
        """The bar's own stylesheet: its chunk in the log's "done" green, the one that reads on the window."""
        rgb = BAR_GREEN[1]
        try:
            QtCore, QtGui = _qt()
            pair = self.ak.LOG_COLORS["done"]
            dark = self.dialog.palette.color(QtGui.QPalette.Window).lightness() < 128
            rgb = tuple(int(value) for value in (pair[0] if dark else pair[1]))
        except Exception:
            pass
        return BAR_SHEET % rgb

    def progress(self, label, part=0.0, events=True):
        """The work at this part (0 to 1) of the step of that label: the bar moved and the window redrawn (at
        most every PUMP_SECONDS within a step), or, without events, only the bar painted (as the list is
        filled: live, letting events through laid out the list made so far each time, and doubled its 0.8 s;
        the window is redrawn when the step changes). A step the work does not list is passed over. While
        holding (a write, from its check of the font's code to the code written), no events go through at
        all: the bar and its step are painted alone, and nothing can change the code meanwhile. Never
        raises."""
        value = bar_value(self.busy_steps, label, part)
        if value is None or not self.busy:
            return
        now = time.time()
        if not self.busy_shown and now - self.busy_since >= SHOW_AFTER:
            self.show_busy()
        if not self.busy_shown:
            return
        moved = label != self.busy_now
        holding = getattr(self, "holding", False)
        try:
            if moved:
                self.busy_now = label
                self.busy_step.setText(u"%s\N{HORIZONTAL ELLIPSIS}" % label)
                if holding:
                    self.busy_step.repaint()
            self.busy_bar.setValue(int(round(value * BAR_RANGE)))
            if holding or not (moved or events):
                self.busy_bar.repaint()
        except Exception:
            pass
        if moved or events:
            self.pump(force=moved)

    def pump(self, force=False):
        if getattr(self, "holding", False):
            return  # (a write between its check and its code: progress paints the bar alone)
        now = time.time()
        if not force and now - self.pumped < PUMP_SECONDS:
            return
        self.pumped = now
        try:
            QtCore, QtGui = _qt()
            pump_events(QtCore, QtGui)
        except Exception:
            pass

    # -- reading the font --------------------------------------------------------------

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

    def layer_of(self, name, master=None):
        glyph = self.package.findName(name) if self.package is not None else None
        if glyph is None or glyph.isNull:
            return None
        return glyph.getLayerByName(master or self.package.master)

    def measure(self, name):
        """(advance, ink box or None) of a glyph in the current master, kept for the list's life."""
        if name not in self.boxes:
            layer = self.layer_of(name)
            if layer is None:
                self.boxes[name] = None
            else:
                box = layer.boundingBox  # (FontLab's QRectF: y() is the ink's bottom, its height upward)
                ink = (box.x(), box.y(), box.x() + box.width(), box.y() + box.height()) if box.width() > 0 else None
                self.boxes[name] = (float(layer.advanceWidth), ink)
        return self.boxes[name]

    def font_classes(self, package, features):
        """{@name: [members]} of the font's classes: its prefix's and FontLab's own feature classes (CJK
        Spacing's font_classes)."""
        return spacing().font_classes(package, read_prefix(features))

    def vertical_origin(self, package):
        """The vertical origin's y: the typographic ascender (the font's ascender where it has none),
        moved as the corpus has it (its median, in a share of the em)."""
        upm = float(package.upm)
        ascender = None
        try:
            ascender = package.fgPackage.info.openTypeOS2TypoAscender
        except Exception:
            pass
        if ascender is None:
            try:
                ascender = package.ascender_value
            except Exception:
                ascender = None
        ascender = float(ascender) if ascender is not None else 0.88 * upm
        return ascender + ((self.model.get("metrics") or {}).get("origin_over_ascender") or 0.0) * upm

    def run(self):
        """The list read again for the font that is current, under the progress bar; while other work runs,
        once it is over."""
        if self.busy:
            self.run_due = True
            return
        self.set_busy(True, LIST_STEPS)
        try:
            self.read_font()
        finally:
            self.set_busy(False)

    def read_font(self):
        QtCore, QtGui = _qt()
        ak = self.ak
        self.progress(READ_STEP)
        kept = self.current_checks()
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.forms, self.trims, self.metrics, self.boxes = [], [], [], {}
        self.turned, self.kerns = [], []
        package = self.package = self.current_font()
        self.show_font_parts(package is not None)
        if package is None:
            self.status.setText(ak.no_font_line())
            self.update_buttons()
            return
        if not self.model:
            self.status.setText(u"")
            self.log.add(u"The corpus's vertical forms (vertical_model.json) are missing beside this script: reinstall "
                         u"FreeLab.", "error")
            return
        upm = float(package.upm)
        master = package.master
        self.origin, self.height = self.vertical_origin(package), upm
        fg_glyphs = list(package.fgPackage.glyphs)
        self.names = [u"%s" % g.name for g in fg_glyphs]
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        self.prefix = read_prefix(features)  # (with the code and the classes: checked again before a write)
        classes = self.classes = self.font_classes(package, features)
        try:  # (lookups the prefix defines, which features name)
            lookups = code_lookups(self.prefix) if self.prefix is not None else {}
        except Exception:
            lookups = {}
        own_vert = own_substitutions("vert", self.texts.get("vert"), classes, lookups)
        own_vrt2 = own_substitutions("vrt2", self.texts.get("vrt2"), classes, lookups)
        own = dict(own_vrt2)
        own.update(own_vert)
        # (the font's own vert forms its own vrt2 lacks: a vrt2 FreeLab writes carries them too)
        self.vrt2_extra = dict((source, target) for source, target in own_vert.items() if source not in own_vrt2)
        wanted = set()
        for key in (self.model.get("vert") or {}):
            wanted.add(int(key[2:], 16))
        wanted.update(VERTICAL_PRESENTATION.values())
        turnable = set(int(key[2:], 16) for key in ((self.model.get("turned") or {}).get("codes") or {}))
        wanted.update(turnable)
        glyphs, shown_codes = [], []
        self.char_names = code_map(fg_glyphs)
        self.cjk = has_cjk(self.char_names)  # (none: not a CJK font, nothing listed but what says so)
        codes = sorted(self.char_names.items()) if self.cjk else []
        for number, (code, name) in enumerate(codes):
            if number % ROWS_PER_STEP == 0:
                self.progress(READ_STEP, 0.2 + 0.6 * number / float(len(codes)))
            kind = self.cj.kind_of(code)
            if code in wanted or (kind is not None and kind != "hangul"):
                measured = self.measure(name)
                if measured is None:
                    continue
                if code in wanted:
                    glyphs.append((code, name, measured[0], measured[1]))
                if kind is not None and kind != "hangul":
                    shown_codes.append((code, name))
        ours = freelab_substitutions("vert", self.texts.get("vert"))
        self.font_vert = own  # (the font's own code: in both previews)
        self.own_vert = dict(ours)  # (the font's code as it stands, FreeLab's block in it: the previews' "Now")
        self.own_vert.update(own)
        self.forms = plan_forms(glyphs, self.names, self.model, upm, self.origin, self.height, own, ours)
        self.own_vpal = own_positions("vpal", self.texts.get("vpal"), classes, lookups)
        self.trims = [t for t in self.plan_trims(shown_codes, own) if t.shown not in self.own_vpal]
        # (a glyph with a vertical form, the font's own or one listed here, takes that form in vrt2: no
        # turned copy is planned for it. Live, IBM Plex Sans KR: en dash had both its presentation form
        # uniFE32 and endash.vrt2, FontLab kept the first rule, and the turned copy was built unused)
        formed = dict(own_vrt2)
        formed.update(self.vrt2_extra)
        formed.update((f.name, f.target) for f in self.forms)
        self.turned = plan_turned([g for g in glyphs if g[0] in turnable], self.names, self.model, upm, self.origin,
                                  formed, freelab_substitutions("vrt2", self.texts.get("vrt2")))
        self.own_vkrn = own_pairs("vkrn", self.texts.get("vkrn"), classes, lookups)
        own_values = own_position_values("vpal", self.texts.get("vpal"), classes, lookups)
        self.kerns = self.plan_kerns(self.char_names, own, own_values) if self.cjk else []
        self.metrics = self.plan_metrics(package) if self.cjk else []
        for item, on in zip(self.all_rows(), [kept.get(self.row_key(row), row.checked) for row in self.all_rows()]):
            item.checked = on
        if u"%s" % self.sample.text in [text for _, _, text in self.samples]:  # (text of one's own is kept)
            key = self.cj.SAMPLES[self.cj.best_sample(set(self.char_names), *self.cj.font_hints(package))][0]
            keys = [k for k, _, _ in self.samples]
            index = keys.index(key) if key in keys else 0
            self.sample_box.setCurrentIndex(index)
            self.sample.setText(self.samples[index][2])
        self.progress(LIST_STEP)
        self.fill(lambda part: self.progress(LIST_STEP, part, False))
        self.first_checks = [row.checked for row in self.all_rows()]
        self.update_buttons()
        self.status.setText(self.status_text(package, master))
        self.seen_history = ak.history_mark(package)
        self.update_put_back()
        self.progress(PREVIEW_STEP)
        self.draw_previews()

    def shown_glyph(self, name, own):
        """(the glyph vertical text sets for a glyph, the transform it is drawn with or None): the font's own
        form, a form listed (built with its transform when it is to be built), or the glyph itself."""
        if name in own:
            return own[name], None
        for form in self.forms:
            if form.name == name and form.state != "font":
                return (name, form.matrix) if form.state == "build" else (form.target, None)
        return name, None

    def plan_kerns(self, by_code, own, own_values):
        """vkrn for the corpus's pairs the font has both glyphs of, both full width, each glyph as vertical
        text sets it (its vertical form: the font's own, or the one to build)."""
        settings = self.model.get("vkrn") or {}
        if not settings.get("values"):
            return []
        pairs = []
        for key in sorted(settings["values"]):
            first_code, second_code = [int(part, 16) for part in key.split()]
            names = [by_code.get(first_code), by_code.get(second_code)]
            if None in names or any((self.measure(name) or (0, None))[0] < FULL_WIDTH_SHARE * self.height
                                    for name in names):
                continue  # (a proportional glyph is turned by applications, and kerned across by kern)
            shown = []
            for name in names:
                glyph, matrix = self.shown_glyph(name, own)
                shown.append(glyph if matrix is None else name + SUFFIX)
            pairs.append((first_code, shown[0], second_code, shown[1]))
        return plan_vkrn(pairs, settings, float(self.package.upm), self.own_vkrn)

    def plan_trims(self, shown_codes, own):
        """vpal trims for the glyphs vertical text sets: each one's vertical form where the font has one
        (or one is planned), else itself."""
        upm = float(self.package.upm)
        by_name = dict((f.name, f) for f in self.forms)
        shown = []
        for code, name in shown_codes:
            measured = self.measure(name)
            if measured is None:
                continue
            advance, box = measured
            form = by_name.get(name)
            glyph = own.get(name) or name
            if form is not None and form.state == "build":
                glyph, box = form.target, (mapped_box(form.matrix, box) if box is not None else None)
            elif form is not None:
                glyph = form.target
                other = self.measure(glyph)
                box = other[1] if other is not None else box
            elif glyph != name:
                other = self.measure(glyph)
                box = other[1] if other is not None else box
            shown.append((code, name, glyph, advance, box))
        return plan_vpal(shown, self.model, upm, self.origin, self.height, self.cj.kind_of)

    def plan_metrics(self, package):
        info = {}
        try:
            data = package.fgPackage.info
            for _, field, _ in VHEA_FIELDS:
                info[field] = getattr(data, field)
        except Exception:
            pass
        without = 0
        for master in self.masters(package):
            for name in self.names:
                layer = self.layer_of(name, master)
                try:
                    if layer is not None and not layer.hasAdvanceHeight:
                        without += 1
                except Exception:
                    pass
        return plan_metrics(float(package.upm), info, without, self.model)

    def masters(self, package):
        try:
            masters = list(package.masters)
        except Exception:
            masters = []
        return masters or [package.master]

    def status_text(self, package, master):
        b = self.ak.b
        builds = sum(1 for f in self.forms if f.state == "build")
        drawn = sum(1 for f in self.forms if f.state == "glyph")
        own = sum(1 for f in self.forms if f.state == "font")
        if not getattr(self, "cjk", True):
            return u"%s, master %s, has no kana, Hangul, ideographs, or CJK punctuation: not a CJK font, nothing to " \
                   u"add for vertical text." % (b(package.tfn), b(master))
        if not self.forms and not self.trims:
            return u"%s, master %s, has none of the characters that turn or move in vertical text, and no full-width " \
                   u"kana or punctuation." % (b(package.tfn), b(master))
        parts = [u"%s to build" % b(counted(builds, u"vertical form")), u"%s drawn already" % b(drawn),
                 u"%s the font's own code makes" % b(own), u"%s" % b(counted(len(self.trims), u"vpal trim")),
                 u"%s" % b(counted(len(self.kerns), u"vkrn pair"))]
        if self.own_vkrn:
            parts.append(u"%s the font's own vkrn kerns (kept)" % b(counted(len(self.own_vkrn), u"pair")))
        if self.own_vpal:
            parts.append(u"%s the font's own vpal positions (kept)" % b(counted(len(self.own_vpal), u"glyph")))
        return u"%s, master %s: %s. Nothing is written until you click %s." % (
            b(package.tfn), b(master), self.ak.joined(parts), self.ak.i(u"Write"))

    # -- the list ------------------------------------------------------------------------

    def all_rows(self):
        """Every row, in a fixed order (a row's index in it is its item's data; the turned glyphs are among
        them while their option is off, unlisted)."""
        return list(self.forms) + list(self.turned) + list(self.trims) + list(self.kerns) + list(self.metrics)

    def row_key(self, row):
        if isinstance(row, Form):
            return ("form", row.name)
        if isinstance(row, VTrim):
            return ("vpal", row.name)
        if isinstance(row, VKern):
            return ("vkrn", row.first, row.second)
        return ("metric", row.key)

    def current_checks(self):
        try:
            self.harvest()
        except Exception:
            pass
        return dict((self.row_key(row), row.checked) for row in self.all_rows())

    def fill(self, progress=None):
        """The list made from the rows; progress(part), where given, every ROWS_PER_STEP rows, the list not
        painted meanwhile."""
        if progress is None:
            self.fill_rows(None)
            return
        try:
            self.tree.setUpdatesEnabled(False)
        except Exception:
            pass
        try:
            self.fill_rows(progress)
        finally:
            try:
                self.tree.setUpdatesEnabled(True)
            except Exception:
                pass

    def fill_rows(self, progress):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        rows = self.all_rows()
        try:
            dimmed = QtGui.QBrush(self.dialog.palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text))
        except Exception:
            dimmed = None
        on = {"forms": self.forms_box.checked, "vpal": self.vpal_box.checked, "metrics": self.metrics_box.checked,
              "vkrn": self.vkrn_box.checked, "turned": self.turned_box.checked and self.forms_box.checked}
        listed = 0
        for section, label in SECTION_LABELS:
            if section == "vpal":
                members = [(i, r) for i, r in enumerate(rows) if isinstance(r, VTrim)]
            elif section == "vkrn":
                members = [(i, r) for i, r in enumerate(rows) if isinstance(r, VKern)]
            elif section == "metrics":
                members = [(i, r) for i, r in enumerate(rows) if isinstance(r, Metric)]
            else:
                members = [(i, r) for i, r in enumerate(rows) if isinstance(r, Form) and r.section() == section]
            if not members or (section == "turned" and not self.turned_box.checked):
                continue  # (the turned glyphs listed only while their option is on)
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (label, len(members))])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            part = section if section in ("vpal", "metrics", "vkrn", "turned") else "forms"
            for index, row in members:
                item = QtGui.QTreeWidgetItem(self.row_texts(row))
                item.setData(0, QtCore.Qt.UserRole, index)
                flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                if not (isinstance(row, Form) and row.state == "font"):
                    flags |= QtCore.Qt.ItemIsUserCheckable
                    item.setCheckState(0, QtCore.Qt.Checked if row.checked else QtCore.Qt.Unchecked)
                item.setFlags(flags)
                if not isinstance(row, Metric):
                    item.setFont(0, bold)
                    icon = self.row_picture(row)
                    if icon is not None:
                        item.setIcon(0, self.ak.icon_of(icon))
                for column in (4, 5):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                if dimmed is not None and (not on[part] or (isinstance(row, Form) and row.state == "font")):
                    for column in range(len(self.COLUMNS)):
                        item.setForeground(column, dimmed)
                item.setToolTip(3, self.row_tip(row))
                top.addChild(item)
                listed += 1
                if progress is not None and listed % ROWS_PER_STEP == 0:
                    progress(listed / float(len(rows) or 1))
            top.setExpanded(True)
        # every row measured (the shared fit_rows): Qt measures only some of a long list's rows, and the
        # metrics' labels at its end were cut ("Advanc...", "none o...", live)
        self.ak.fit_rows(self.tree, range(len(self.COLUMNS) - 1))
        self.tree.blockSignals(False)
        self.update_buttons()

    def row_texts(self, row):
        dash = u"\N{EN DASH}"
        if isinstance(row, Form):
            how = HOW_LABELS.get(row.how, u"") if row.state == "build" else row.note
            if row.state == "build" and row.how == "moved":
                how = u"Moved %+d, %+d" % (row.matrix[4], row.matrix[5])
            return [row.char, row.name, row.target, how, dash, u"new" if row.state == "build" else dash]
        if isinstance(row, VTrim):
            return [row.char, row.name, row.shown if row.shown != row.name else dash, u"y placement, y advance",
                    u"%d, %d" % (row.top, row.bottom), u"%+d, %+d" % row.value]
        if isinstance(row, VKern):
            return [row.chars, u"%s %s" % (row.first, row.second), dash, counted(row.fonts, u"font"), dash,
                    u"%+d" % row.value]
        now = (u"none on %s" % counted(row.count, u"layer") if row.key == "advance_height"
               else (dash if row.now is None else u"%d" % int(round(float(row.now)))))
        return [row.label, u"", u"", u"the font's own kept" if not row.checked and row.now is not None else u"",
                now, u"%d" % row.value]

    def row_tip(self, row):
        if isinstance(row, Form) and getattr(row, "vrt2_only", False):
            return (u"Turned a quarter clockwise about the em's square, for vrt2 only: its width the em, its height "
                    u"its width now.")
        if isinstance(row, Form):
            if row.state == "font":
                return u"The font's own vert or vrt2 makes this form: left alone."
            if row.state == "glyph":
                return u"The font draws this form already: only its rule is written."
            return u"Built as a component of %s, then written in vert and vrt2." % row.name
        if isinstance(row, VTrim):
            return (u"Now: the ink's top and bottom sidebearings in vertical text. After: vpal's y placement and y "
                    u"advance (the ink moves by the first, the height changes by the second).")
        if isinstance(row, VKern):
            return (u"How many of the corpus's fonts kern this pair in vertical text; After: their median value, "
                    u"scaled to the em (the upper glyph's height changes by this much: vkrn).")
        if row.key == "advance_height":
            return u"Each layer without an advance height gets the em (FontLab keeps none from a font file it opens)."
        return u"The font info's %s (not in FontLab's History: Put back vhea undoes it)." % row.label

    def items(self):
        found = []
        for index in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(index)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def harvest(self):
        QtCore, QtGui = _qt()
        rows = self.all_rows()
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(rows) and not (isinstance(rows[index], Form) and rows[index].state == "font"):
                rows[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        """Check all, Check none: every checkable row, the log told how many it checked or unchecked, and
        how many of them were in closed groups (owner's report 118)."""
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        try:
            self.ak.check_rows([item for item in self.items() if item.flags() & QtCore.Qt.ItemIsUserCheckable], on,
                               log=self.log, command=u"Check all" if on else u"Check none",
                               hidden_text=(u"in a closed group", u"in closed groups"))
        finally:
            self.tree.blockSignals(False)
        self.changed()

    def changed(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def checkable(self):
        return [row for row in self.all_rows() if not (isinstance(row, Form) and row.state == "font")]

    def texts_now(self):
        """The feature code a write would make now, from the checks and the parts switched on."""
        if self.package is None:
            return {}
        self.refused = []  # (features whose braces FreeLab cannot find: left as they are, said as a write starts)
        return texts_for(self.forms, self.trims, self.texts, self.forms_box.checked, self.vpal_box.checked,
                         self.own_vpal, self.vrt2_extra, list(self.turned) if self.turned_box.checked else [],
                         self.kerns, self.vkrn_box.checked, self.refused)

    @staticmethod
    def cj_refused_words(tags):
        """The log's sentence for features left as they are (feature_text found no braces)."""
        one = len(tags) == 1
        return (u"FreeLab leaves %s as %s: it cannot find where %s code begins and ends (the feature's braces), "
                u"so nothing of FreeLab's goes in. Check %s code in FontLab's Features panel." % (
                    u", ".join(sorted(set(tags))), u"it is" if one else u"they are",
                    u"that feature's" if one else u"each one's", u"its" if one else u"their"))

    def pending(self):
        """What a write would do now: (new feature code, forms to build, metrics to set)."""
        new = self.texts_now()
        turned = list(self.turned) if self.turned_box.checked else []
        on = self.forms_box.checked
        builds = [f for f in list(self.forms) + turned if f.checked and f.state == "build"] if on else []
        metrics = [m for m in self.metrics if m.checked] if self.metrics_box.checked else []
        return new, builds, metrics

    def update_buttons(self):
        """Each button clickable only when it would do something. While long work runs, once it is over
        (set_busy): the live pass found Write and Restore suggestions clickable over Noto Sans's empty list,
        left as the font before had them, since a list read quickly (no bar shown) never set them again. A
        font with no CJK glyph is offered nothing: every button that acts on the list is grayed, and so is
        Add vertical metrics to an exported font, whose values would be the ones the list offers (none)."""
        self.buttons_due = False
        if self.busy:
            self.buttons_waiting = True  # (set once the work is over: set_busy)
            return
        self.buttons_waiting = False
        ak = self.ak
        self.harvest()
        cjk = getattr(self, "cjk", True)
        checks = [row.checked for row in self.checkable()]
        ak.enable(self.all_button, cjk and (not all(checks) if checks else False))
        ak.enable(self.none_button, cjk and any(checks))
        ak.enable(self.restore_button, cjk and [row.checked for row in self.all_rows()] != self.first_checks)
        new, builds, metrics = self.pending()
        problem = self.reader_problem()
        ak.enable(self.write_button, cjk and bool(new or builds or metrics) and not problem)
        if problem and problem != getattr(self, "problem_said", None):
            self.log.add(self.ak.html(problem), "error")  # (once, while it lasts)
        self.problem_said = problem
        if not cjk:
            ak.enable(self.export_button, False)
        self.draw_previews()

    def toggled(self):
        if self.busy:
            return
        self.set_busy(True, SHOW_STEPS)
        try:
            self.harvest()
            self.fill(lambda part: self.progress(LIST_STEP, part, False))
            self.progress(PREVIEW_STEP)
            self.draw_previews()
        except Exception as exc:
            self.log.add(u"Could not show the change: %s" % self.ak.html(exc), "error")
        finally:
            self.set_busy(False)
        self.update_buttons()

    def restore(self):
        if self.busy:
            return
        for row, on in zip(self.all_rows(), self.first_checks):
            row.checked = on
        self.set_busy(True, SHOW_STEPS)
        try:
            self.fill(lambda part: self.progress(LIST_STEP, part, False))
        finally:
            self.set_busy(False)
        self.log.add(u"Checks restored as suggested.")

    def history_moved(self):
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()

    def font_changed(self):
        self.run()

    def show_font_parts(self, on):
        """With no font open, the sample and its previews are hidden and the settings grayed out."""
        for widget in [self.sample_label, self.sample_box, self.sample] + list(self.preview_captions) + list(self.previews):
            widget.setVisible(on)
        note = getattr(self, "preview_note", None)
        if note is not None and not on:  # (shown again by draw_previews, where it has something to say)
            note.setVisible(False)
        for widget in (self.forms_box, self.vpal_box, self.vkrn_box, self.turned_box, self.metrics_box, self.compile_box,
                       self.export_button):
            self.ak.enable(widget, on)

    def flag_names(self):
        items = self.tree.selectedItems()
        return self.row_names(items[0]) if items else []

    def row_names(self, item):
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        rows = self.all_rows()
        if not 0 <= index < len(rows) or isinstance(rows[index], Metric):
            return []
        row = rows[index]
        names = [row.name]
        target = getattr(row, "target", None) or getattr(row, "shown", None)
        if target and target != row.name and target in self.names:
            names.append(target)
        return names

    def show_in_glyph_window(self, item):
        names = self.row_names(item)
        if not names:
            return
        name = names[-1]
        error = self.ak.show_in_glyph_window(self.fontlab, u"/%s/%s/%s" % (name, name, name))
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % self.ak.html(error), "error")

    # -- pictures ------------------------------------------------------------------

    def form_path(self, name, matrix=None):
        """A glyph's outline as a QPainterPath, mapped by a form's transform when given."""
        QtCore, QtGui = _qt()
        layer = self.layer_of(name)
        if layer is None:
            return None
        path = self.ak.layer_path(layer)
        if matrix is not None:
            path = QtGui.QTransform(*matrix).map(path)
        return path

    def row_picture(self, row):
        if isinstance(row, Form):
            if row.state == "build":
                return self.picture([[(row.name, row.matrix, 0, 0)]], ICON_SIZE, columns=False)
            return self.picture([[(row.target, None, 0, 0)]], ICON_SIZE, columns=False)
        if isinstance(row, VKern):  # (the pair one under the other, a form to build drawn from its glyph)
            column = [self.drawable(row.first) + (0, row.value), self.drawable(row.second) + (0, 0)]
            return self.picture([column], ICON_SIZE // 2, columns=False)
        return self.picture([[(row.shown if row.shown in self.names else row.name,
                               self.form_matrix_of(row.name) if row.shown not in self.names else None, 0, 0)]],
                            ICON_SIZE, columns=False)

    def drawable(self, glyph):
        """(name, transform) to draw a glyph by: a form still to build is drawn from its glyph, turned or moved."""
        if glyph not in self.names:
            for f in list(self.forms) + list(self.turned):
                if f.target == glyph and f.state == "build":
                    return f.name, f.matrix
        return glyph, None

    def form_matrix_of(self, name):
        for f in self.forms:
            if f.name == name and f.state == "build":
                return f.matrix
        return None

    def picture(self, columns_of, size, columns=True):
        """Glyphs [(name, transform or None, y placement, y advance change)] set top to bottom in columns
        right to left (columns_of: a list of columns), each square an em, in the dialog's text color."""
        QtCore, QtGui = _qt()
        if self.package is None:
            return None
        upm = float(self.package.upm)
        scale = size / upm
        tall = max([sum(self.height + item[3] for item in column) for column in columns_of] + [self.height])
        step = size * COLUMN_STEP
        width = int(step * len(columns_of)) + 4 if columns else int(size) + 4
        pixmap = QtGui.QPixmap(max(width, 4), max(int(tall * scale) + 4, 4))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            for number, column in enumerate(columns_of):
                x = (width - step * (number + 1)) if columns else 2.0
                y = 2.0
                for name, matrix, placement, advance in column:
                    path = self.form_path(name, matrix) if name is not None else None
                    if name is None:  # (missing from the font: an empty box, as a font's .notdef)
                        painter.save()
                        painter.setPen(QtGui.QPen(color, 1.0))
                        painter.drawRect(QtCore.QRectF(x + size * 0.15, y + size * 0.1, size * 0.7, size * 0.8))
                        painter.restore()
                    elif path is not None:
                        painter.save()
                        painter.translate(x, baseline_y(y, self.origin, placement, scale))
                        painter.scale(scale, -scale)
                        painter.fillPath(path, QtGui.QBrush(color))
                        painter.restore()
                    y += (self.height + advance) * scale
        finally:
            painter.end()
        # (in one color: redrawn in the new one when dark mode switches)
        return self.ak.inked(pixmap, color)

    def draw_previews(self):
        if self.package is None:
            return
        names = self.char_names
        text = u"%s" % self.sample.text
        chosen = dict((f.name, f) for f in self.forms if f.checked and f.state != "font") if self.forms_box.checked else {}
        trims = dict((t.shown, t.value) for t in self.trims if t.checked) if self.vpal_box.checked else {}
        kerns = dict(((k.first, k.second), k.value) for k in self.kerns if k.checked) if self.vkrn_box.checked else {}
        room = self.room()
        self.preview_room = (room, self.pane_width(self.previews[0]))
        upm = float(self.package.upm) or 1000.0
        for index, label in enumerate(self.previews):
            own = self.own_vert if index == 0 else self.font_vert  # (now: the code as it stands; after: the font's own and what is checked)
            placed, chars, heights = preview_column(text, names, own, chosen if index else {}, trims if index else {},
                                                    kerns if index else {}, self.height, upm)
            width = self.pane_width(label)
            em = fitting_em(chars, lambda size: [h * size for h in heights], width, room + 8, PREVIEW_EM) \
                if room and width else PREVIEW_EM
            spans = vertical_lines(chars, [h * em for h in heights], room) if room and room > em else [(0, len(placed))]
            pixmap = self.picture([placed[a:b] for a, b in spans], em) if placed else None
            if pixmap is None:
                label.clear()
            else:
                label.setPixmap(pixmap)
        note = getattr(self, "preview_note", None)
        if note is not None:
            words = preview_note(text, names)
            note.setText(words)
            note.setVisible(bool(words))

    # -- writing --------------------------------------------------------------------

    def reader_problem(self):
        """Why nothing can be written (Feature Code's reader, which CJK Spacing loads, cannot be loaded), or
        empty (Codex review 7: a missing script raised out of the button updates and the write)."""
        try:
            return spacing().feature_code_problem(u"CJK Vertical")
        except Exception as exc:
            return (u"CJK Vertical cannot read the font's feature code: FreeLab's CJK Spacing script, which it "
                    u"reads code through, is missing or broken (%s). Reinstall FreeLab; nothing is written until "
                    u"then." % exc)

    def write(self):
        if self.package is None or self.busy:
            return
        problem = self.reader_problem()
        if problem:  # (nothing written: no reader)
            self.log.add(self.ak.html(problem), "error")
            return
        self.harvest()
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed: here is this one's list. Nothing was written.", "warning")
            return
        new, builds, metrics = self.pending()
        if getattr(self, "refused", None):
            self.log.add(self.ak.html(self.cj_refused_words(self.refused)), "warning")
        fc = None
        try:
            fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
        except Exception:
            pass
        names = self.names + [f.target for f in builds]
        problems = []
        for tag, text in sorted(new.items()):
            block = block_of(tag, text)
            problem = fc.check_code(block, names) if (fc is not None and block) else None
            if problem:
                problems.append(u"%s: %s" % (tag, problem))
        if problems:
            self.log.add(u"The code has problems, so nothing was written: %s" % self.ak.html(u"; ".join(problems)), "error")
            return
        heights = [m for m in metrics if m.key == "advance_height"]
        vhea = [m for m in metrics if m.key != "advance_height"]
        self.set_busy(True, WRITE_STEPS, at_once=True)
        try:  # (busy always ends: while it holds, the History watcher is silent and the window is kept)
            self.write_parts(package, new, builds, heights, vhea)
        finally:
            self.set_busy(False)

    def write_parts(self, package, new, builds, heights, vhea):
        """The write itself, under the progress bar (write), then its log and the list read again."""
        built, failed, written, set_heights, error, touched = [], [], [], 0, None, []
        vhea_done = []
        # The code written is composed from the code read with the list: an edit made since (before the History
        # watcher saw it, or one that leaves the History where it was) would be replaced. Checked after the last
        # event let through (the bar's); from here until the code is written, the bar is painted alone
        self.holding = True
        try:
            changed = self.changed_code(package)
        except Exception:
            changed = list(CODE_TAGS)  # (code that cannot be read counts as changed)
        if changed:
            self.holding = False
            self.read_font()  # (under the same bar)
            self.log.add(u"The feature code (%s) changed since the list was read: here is the list again, to check "
                         u"before writing. Nothing was written." % self.ak.html(self.ak.joined(changed)), "warning")
            return
        status = None  # (notify_changed's: Undo promised only when FontLab's History recorded the write)
        try:
            in_history = bool(builds or new or heights)  # (the font info is not in FontLab's History: no step for it alone)
            if in_history:
                self.progress(UNDO_STEP)
                try:
                    self.ak.before_changes(self.fontlab, package, TITLE)
                except getattr(self.ak, "HistoryError", ()) as exc:  # (nothing written: Undo could not take it back)
                    self.holding = False
                    self.log.add(u"%s" % (exc,), "error")
                    return
            try:
                self.progress(BUILD_STEP)
                for number, form in enumerate(builds):
                    self.progress(BUILD_STEP, number / float(len(builds)))
                    glyph, why = self.build_form_safely(package, form)
                    if glyph is None:
                        failed.append((form.target, why))
                        continue
                    touched.append(glyph)
                    built.append(form.target)
                if failed:  # (a rule for a form that was not built would name a missing glyph)
                    gone = set(target for target, _ in failed)
                    for form in builds:
                        if form.target in gone:
                            form.checked = False
                    new = self.texts_now()
                self.progress(CODE_STEP)
                features = package.fgPackage.features
                for tag in CODE_TAGS:
                    if tag in new:
                        features.set_feature(tag, new[tag])
                        written.append(tag)
                self.holding = False
                if heights:
                    self.progress(HEIGHTS_STEP)
                    set_heights = self.set_advance_heights(package, heights[0].value)
            except Exception as exc:
                error = exc
            self.holding = False
            if in_history:
                self.progress(UPDATE_STEP)
                status = self.ak.notify_changed(self.fontlab, package, TITLE, touched, added=bool(built) or None)
            if vhea:
                self.progress(VHEA_STEP)
            vhea_done = self.write_vhea(package, vhea) if vhea else []
        except Exception as exc:
            error = error or exc
        self.holding = False
        b = self.ak.b
        undo = getattr(status, "recorded", True)
        if built:
            self.log.add(u"Built %s: %s. %s at the end of the font%s." % (
                b(counted(len(built), u"vertical form")), self.ak.glyph_name_links(built),
                u"It is" if len(built) == 1 else u"They are",
                u"; <i>Edit &gt; Undo</i> takes %s back" % (u"it" if len(built) == 1 else u"them") if undo else u""), "done")
        for target, why in failed:
            self.log.add(u"%s was not built: %s." % (b(target), self.ak.html(why)), "warning")
        if written:
            self.log.add(u"Wrote %s%s.%s" % (
                b(self.ak.joined(written)),
                u"; <i>Edit &gt; Undo</i> takes %s back" % (u"it" if len(written) == 1 else u"them") if undo else u"",
                self.ak.compiled_note(self.compile_box, self.log)), "done")
        if set_heights:
            self.log.add(u"Set the advance height of %s to %s." % (b(counted(set_heights, u"layer")), b(heights[0].value)),
                         "done")
        if vhea_done:
            self.log.add(u"Wrote %s into the font info: %s. FontLab's <i>Edit &gt; Undo</i> does not take the font info "
                         u"back: <i>Put back vhea</i> does." % (
                             b(counted(len(vhea_done), u"vhea value")),
                             self.ak.html(u"; ".join(u"%s %d" % (m.label, m.value) for m in vhea_done))), "done")
        if set_heights or vhea_done:
            self.log.add(EXPORT_NOTE, "warning")
        if not (built or written or set_heights or vhea_done):
            self.log.add(u"Wrote nothing.")
        if not getattr(status, "ok", True):
            self.log.add(status.message(), "error")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        self.read_font()  # (under the same bar)

    def changed_code(self, package):
        """What differs in the font's code from the code read with the list (changed_features: the features
        written, the prefix), its feature classes too: the list rests on all of them."""
        features = package.fgPackage.features
        changed = changed_features(features, self.texts, CODE_TAGS, self.prefix)
        if u"prefix" not in changed and self.font_classes(package, features) != self.classes:
            changed.append(u"classes")
        return changed

    def build_form_safely(self, package, form):
        """build_form, its glyph taken out again when anything fails after FontLab added it (an empty glyph
        left behind, and the rest of the write skipped): (glyph, None), or (None, why)."""
        try:
            return self.build_form(package, form)
        except Exception as exc:
            try:
                glyph = package.findName(form.target)
                if glyph is not None:
                    package.deleteGlyph(glyph)
            except Exception:
                pass
            return None, u"%s" % exc

    def source_parts(self, package, master, name, matrix):
        """The component to make for a form: the glyph and the transform; a glyph that is one component
        alone is replaced by the glyph it points to, the transforms combined (FontLab 7 refused a scaled
        component of such a glyph: Feature Code's and Diacritics' finding)."""
        for _ in range(4):
            layer = self.layer_of(name, master)
            shapes = list(layer.shapes) if layer is not None else []
            if len(shapes) != 1 or not shapes[0].isComponent:
                break
            inner = shapes[0].transform
            inner_name = u"%s" % shapes[0].shapeData.componentGlyph
            if not inner_name:
                break
            matrix = compose(matrix, (inner.m11(), inner.m12(), inner.m21(), inner.m22(), inner.dx(), inner.dy()))
            name = inner_name
        return name, matrix

    def build_form(self, package, form):
        """A vertical form added to the font: a component of its glyph, turned or moved, in every master
        (each master's own advance: the turn is about its em's center), with the glyph's width and the em
        as its advance height. (glyph, None), or (None, why) with nothing left in the font."""
        QtCore, QtGui = _qt()
        fontlab = self.fontlab
        if package.findName(form.target) is not None:
            return None, u"the font has a glyph of that name now"
        source = package.findName(form.name)
        if source is None:
            return None, u"%s is gone" % form.name
        new = fontlab.flGlyph()
        new.name = form.target
        package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
        glyph = package.findName(form.target)
        if glyph is None:
            return None, u"FontLab did not add it"
        made = 0
        upm = float(package.upm)
        entry = (self.model.get("vert") or {}).get(u"U+%04X" % form.code) or {}
        for master in self.masters(package):
            layer_from = source.getLayerByName(master)
            if layer_from is None:
                continue
            advance = float(layer_from.advanceWidth)
            box = layer_from.boundingBox  # (each master's own ink: a moved form takes the same place in each)
            ink = (box.x(), box.y(), box.x() + box.width(), box.y() + box.height()) if box.width() > 0 else None
            turned = getattr(form, "vrt2_only", False)
            if turned:  # (vrt2's turned proportional glyph: about the em's square, the em wide, as tall as it is wide)
                settings = self.model.get("turned") or {}
                matrix, width = form.matrix, upm * (settings.get("advance") or 1.0)
                height = advance * (settings.get("height") or 1.0)
            else:
                matrix = placed_matrix(form.how, entry, advance, ink, self.origin, self.height, upm) if entry \
                    else form.matrix
                width = advance
                height = layer_from.advanceHeight if layer_from.hasAdvanceHeight else self.height
            name, matrix = self.source_parts(package, master, form.name, matrix)
            component = fontlab.GlyphComponent(name)
            component.transform = QtGui.QTransform(*[float(value) for value in matrix])
            layer = glyph.getLayerByName(master, True)
            layer.setGlyphComponents([component], width, package, False)
            try:
                layer.advanceHeight = height
                layer.update()
            except Exception:
                pass
            if len(layer.shapes):
                made += 1
        if not made:
            package.deleteGlyph(glyph)
            return None, u"FontLab did not keep its component"
        return glyph, None

    def set_advance_heights(self, package, value):
        """The advance height of every layer that has none set to value (the em); how many. Each glyph changed
        is told so (its update()): live (2026-11-14, Zen Old Mincho and IBM Plex Sans JP opened afresh), a
        layer's advance height set without it was gone once the write was over in all but a few glyphs
        (256 of 7,866 layers kept it), while with it every one of 7,792 kept it."""
        done = 0
        masters = self.masters(package)
        for name in self.names:
            glyph = package.findName(name)
            if glyph is None:
                continue
            changed = False
            for master in masters:
                try:
                    layer = glyph.getLayerByName(master)
                    if layer is not None and not layer.hasAdvanceHeight:
                        layer.advanceHeight = value
                        done += 1
                        changed = True
                except Exception:
                    pass
            if changed:
                try:
                    glyph.update()
                except Exception:
                    pass
        return done

    def write_vhea(self, package, metrics):
        """vhea's checked values into the font info (outside FontLab's History): the old ones kept for Put
        back vhea (an unset value goes back to unset). The metrics written."""
        info = package.fgPackage.info
        fields = dict((key, field) for key, field, _ in VHEA_FIELDS)
        old, done = {}, []
        for metric in metrics:
            field = fields[metric.key]
            try:
                old[field] = getattr(info, field)
                setattr(info, field, float(metric.value))
                now = getattr(package.fgPackage.info, field)
                if now is not None and int(round(float(now))) == metric.value:
                    done.append(metric)
            except Exception as exc:
                self.log.add(u"FontLab did not take %s: %s" % (metric.label, self.ak.html(exc)), "warning")
        if old:
            self.put_back = (self.ak.font_key(package), old)
            mark_modified(package)
        self.update_put_back()
        return done

    def metrics_values(self, package):
        """This font's vertical values for an exported font (export_values): the current master's advance
        heights, vhea's values from the font info (the suggested ones where it has none)."""
        master = package.master
        heights, codes = {}, {}
        for fg in package.fgPackage.glyphs:
            name = u"%s" % fg.name
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            try:
                if layer is not None and layer.hasAdvanceHeight and layer.advanceHeight > 0:
                    heights[name] = float(layer.advanceHeight)
            except Exception:
                pass
            codes[name] = codes_of(fg)
        suggested = dict((m.key, m.value) for m in self.metrics)
        info = package.fgPackage.info
        vhea = []
        for key, field, _ in VHEA_FIELDS:
            value = getattr(info, field, None)
            vhea.append(float(value) if value is not None else suggested.get(key, VHEA_DEFAULTS[key] * package.upm))
        return export_values(package.upm, self.origin, vhea, heights, codes, u"%s" % package.tfn, u"%s" % master)

    def add_metrics_to_export(self, path=None):
        """Vertical metrics added to a copy of a font FontLab exported (picked, or path), from this font's
        values, by add_vertical_metrics run here (FontLab 7's Python ships fontTools); the values written
        beside the exported font too, for add_vertical_metrics run on its own. The result in the log."""
        QtCore, QtGui = _qt()
        if self.package is None or self.busy:
            return
        if path is None:
            path = QtGui.QFileDialog.getOpenFileName(self.dialog, u"The font FontLab exported", u"",
                                                     u"Fonts (*.otf *.ttf)")
            if not path:
                return
        path = u"%s" % path
        self.set_busy(True, EXPORT_STEPS, at_once=True)
        try:
            self.add_metrics_to(path)
        finally:
            self.set_busy(False)

    def add_metrics_to(self, path):
        """add_metrics_to_export's work, under the progress bar, and its log. Nothing is written until the
        exported font is read and its em checked; the copy and the values file are written to files of their
        own first (add_vertical_metrics' staged_path), and take their names together, once the copy's tables
        read back right: a refusal or a failure leaves the folder as it was."""
        import io
        import json
        b = self.ak.b
        started = time.time()
        staged, script = None, None
        try:
            self.progress(VALUES_STEP)
            values = self.metrics_values(self.package)
            script = load_metrics_script()
            self.progress(OPEN_STEP)
            from fontTools.ttLib import TTFont
            font = TTFont(path)
            try:
                if font["head"].unitsPerEm != values["upm"]:
                    self.log.add(u"%s has an em of %s, this font %s: export it from this font again." % (
                        b(os.path.basename(path)), counted(font["head"].unitsPerEm, u"unit"),
                        counted(values["upm"], u"unit")), "error")
                    return
                if "CFF " in font or "CFF2" in font:
                    self.busy_steps = CFF_EXPORT_STEPS  # (its glyphs measured faster, its copy saved slower)
                metrics = script.add_tables(font, values,
                                            lambda key, part=0.0: self.progress(SCRIPT_STEPS.get(key, key), part))
                self.progress(SAVE_STEP)
                values_out, kept = values_file(script, path, values)
                staged = script.staged_path(values_out)
                with io.open(staged, "w", encoding="utf-8") as handle:
                    handle.write(u"%s" % json.dumps(values, indent=1, sort_keys=True, ensure_ascii=False))
                out = free_name(script.output_path(path))
                problems = script.write_copy(font, path, out, values,
                                             lambda key: self.progress(CHECK_STEP) if key == "check" else None)
                cff = "VORG" in font
            finally:
                font.close()  # (the exported font let go: Windows keeps an open file from being moved or deleted)
            if problems:
                for problem in problems:
                    self.log.add(u"Read back: %s." % self.ak.html(problem), "error")
                self.log.add(u"Nothing was written: the copy's tables read back wrong.", "error")
                return
            script.publish(staged, values_out)
            staged = None
        except Exception as exc:
            self.log.add(u"Could not add the vertical metrics: %s" % self.ak.html(exc), "error")
            return
        finally:
            if staged is not None and script is not None:
                script.discard(staged)
        self.log.add(u"Wrote %s: %s for %s, from this font's values (master %s; vertical origin %d), in %s. The "
                     u"exported font is unchanged; its values are in %s, for <i>add_vertical_metrics</i> run again%s." % (
                         b(os.path.basename(out)), u"vhea, vmtx, and VORG" if cff else u"vhea and vmtx",
                         b(counted(len(metrics), u"glyph")), self.ak.html(values["master"]), values["origin"],
                         counted(int(round(time.time() - started)) or 1, u"second"),
                         b(os.path.basename(values_out)), u" (with <i>--values</i>)" if kept else u""), "done")
        if kept:
            self.log.add(u"%s is kept as it was: it holds another font's or master's values, or could not be read." % (
                b(os.path.basename(kept))), "warning")

    def update_put_back(self):
        held = self.put_back
        self.ak.enable(self.put_back_button, bool(held) and self.package is not None
                       and self.ak.font_key(self.package) == held[0])

    def put_back_values(self):
        held = self.put_back
        current = self.current_font()
        if not held or current is None or self.ak.font_key(current) != held[0]:
            self.log.add(u"The font written to is not this window's font now: nothing was put back.", "warning")
            self.update_put_back()
            return
        info = current.fgPackage.info
        restored = 0
        for field, value in held[1].items():
            try:
                setattr(info, field, None if value is None else float(value))  # (None unsets it: live, 2026-11-14)
                restored += 1
            except Exception as exc:
                self.log.add(u"FontLab did not take %s back: %s" % (field, self.ak.html(exc)), "warning")
        self.put_back = None
        mark_modified(current)
        self.log.add(u"Put back %s as %s." % (self.ak.b(counted(restored, u"vhea value")),
                                               u"it was" if restored == 1 else u"they were"), "done")
        self.run()

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("CJK Vertical"):
            return
    except Exception:
        pass
    try:
        dialog = CJKVerticalDialog()
    except Exception as exc:
        print("FreeLab CJK Vertical: %s" % exc)
        return
    sys._freelab_cjk_vertical = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("CJK Vertical", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_cjk_vertical":
    main()
