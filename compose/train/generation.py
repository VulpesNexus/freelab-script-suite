"""Glyph Compose's recipe table for its Glyph generation tab: compose/glyph_generation.json.

Three inputs, none shipped:
- the research inventory (inventory.json, made for Glyph Compose on 2026-11-16 from Unicode's data, type
  tools' recipe lists, and a survey of the corpus): which characters are in the first scope, how they
  are built, how sure each recipe is, and how many of the corpus's families build them so. Its
  fontlab_alias fields (quotes of FontLab's alias.dat, which states no license) are never read here:
  nothing of FontLab's data enters FreeLab;
- GlyphsInfo's GlyphData.xml (BSD-3-Clause, notice in compose/glyph_generation_LICENSE): Glyphs' glyph
  names, as Glyph Compose's Diacritics tab names its glyphs;
- the corpus (open-licensed fonts, one per family, FreeLab's %LOCALAPPDATA%\\FreeLab\\corpus): measured
  for the layout constants the recipes need (how far apart two quotes stand, how far a turned
  exclamation mark drops, where the middle dot sits). Only medians and counts leave the fonts.

The recipes themselves are FreeLab's (RECIPES below): each character's ways, in order of preference, in
the operations freelab_glyph_generation.py knows. The inventory decides scope and confidence, and
supplies the corpus counts shown in each row; where its recipe and the corpus disagree (Unicode's
confusables map the Cyrillic I to the Latin l, but the corpus's fonts copy the capital I), the corpus
wins and the recipe here says so.

    python compose/train/generation.py INVENTORY GLYPHSINFO_XML [--corpus DIR] [--out FILE] [--limit N]
    python compose/train/generation.py --refresh TABLE [--records CALIBRATION]

--refresh rewrites what an existing table takes from Unicode's data (each turned letter's body, the
"characters" FontLab's Python 2.7 does not know: its Unicode is 5.2) and, given the calibration's records
(--calibration's file), its monoline thresholds; the rest of the table as it was, no corpus read.

Python 3 with fonttools.
"""

import argparse
import collections
import glob
import io
import json
import os
import statistics
import sys
import unicodedata
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_glyph_generation as gg  # noqa: E402  (the monoline measures, as the tab takes them)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "glyph_generation.json")
CORPUS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")
OPEN_LICENSES = (("open font license", "OFL"), ("scripts.sil.org/ofl", "OFL"), ("openfontlicense", "OFL"),
                 ("apache license", "Apache"), ("apache.org/licenses", "Apache"))
PROPRIETARY = ("microsoft supplied font", "any other use is prohibited", "end user license agreement")
SUBFOLDERS = ("kerning-fonts", "language-font-sources")  # (their work/ subsets left out)

# The first scope, by group, in the order the tab lists them (the research's recommended first scope:
# 205 characters, every one exact or accepted, every one buildable with machinery items 1 to 5)
GROUPS = (
    ("spaces", u"Spaces", "00A0 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 200A 202F 205F 200B 2060 FEFF 3000"),
    ("dashes", u"Hyphens and dashes", "00AD 2010 2011 2012 2013 2014 2015 2212 2E3A 2E3B"),
    ("duplicates", u"Duplicates", "2126 212A 212B 037E 0387 0374 1F71 1F73 1F75 1F77 1F79 1F7B 1F7D 1FBB 1FC9 1FCB "
                                  "1FD3 1FDB 1FE3 1FEB 1FEE 1FEF 1FF9 1FFB 1FFD 0340 0341 0343 00B5 2206 00D0 0110 "
                                  "0189 2219 22C5 2027 2E31 2215 2216 2223 02BC 02BB 02BD 2024"),
    ("punctuation", u"Punctuation", "2026 2025 201A 201E 2018 201B 201C 201F 00AB 00BB 203A 00A1 00BF 2E2E 204F "
                                    "2E41 2E32 00B7 2033 2034 2057 2035 2036 2037 203C 2047 2048 2049"),
    ("lookalikes", u"Greek and Cyrillic look-alikes", None),  # (the inventory's accepted look-alikes)
    ("ligatures", u"Ligature letters", "0132 0133 01C4 01C5 01C6 01C7 01C8 01C9 01CA 01CB 01CC 01F1 01F2 01F3 0149 "
                                       "013F 0140"),
    ("fractions", u"Vulgar fractions", None),  # (the inventory's twenty)
    ("arrows", u"Arrows and triangles", "2190 2191 2193 21D0 21D1 21D3 25B2 25BC 25C0 25B3 25BD 25C1 2196 2197 2198 "
                                        "2199"),
    ("turned", u"Turned and reversed letters", None),  # (the inventory's 41: starting points, unless monoline)
)
EXPECTED = {"spaces": 18, "dashes": 10, "duplicates": 44, "punctuation": 28, "lookalikes": 52, "ligatures": 17,
            "fractions": 20, "arrows": 16, "turned": 41}

E, A, S = "exact", "accepted", "starting point"


def way(op, confidence, **data):
    data.update(op=op, confidence=confidence)
    return data


# -- FreeLab's recipes: each character's ways, the first the font can take is used -------------------------
# Operations (freelab_glyph_generation.py): width (an empty glyph: em, a setting, or another glyph's
# advance), shared (the code point added to the source's own glyph), copy, move, turn (by an angle, about
# the ink's center), mirror (left to right: the contours set right), row (side by side), stretch (a dash
# drawn longer, its thickness and ends kept), minus (the hyphen on the plus), fraction.
def spaces():
    em = lambda value: [way("width", E, em=value)]
    return {
        "00A0": [way("width", E, advance_of="0020", note=u"the space's width")],
        "2000": [way("width", E, em=0.5, note=u"the en quad: half an em")],
        "2001": [way("width", E, em=1.0, note=u"the em quad: one em")],
        "2002": em(0.5), "2003": em(1.0), "2004": em(1.0 / 3), "2005": em(0.25), "2006": em(1.0 / 6),
        "2007": [way("width", E, advance_of="figure", note=u"a tabular figure's width")],
        "2008": [way("width", E, advance_of="002E", note=u"the period's width")],
        "2009": [way("width", A, setting="thin", note=u"Thin space setting")],
        "200A": [way("width", A, setting="hair", note=u"Hair space setting")],
        "202F": [way("width", E, setting="thin", note=u"the thin space's width")],
        "205F": [way("width", E, em=4.0 / 18, note=u"4/18 of an em")],
        "200B": em(0.0), "2060": em(0.0), "FEFF": em(0.0),
        "3000": [way("width", E, em=1.0, note=u"the full-width cell", only="cjk")],
    }


def dashes():
    return {
        "00AD": [way("copy", E, of="002D")],
        "2010": [way("copy", A, of="002D")],
        "2011": [way("copy", E, of="2010"), way("copy", E, of="002D")],
        "2012": [way("stretch", A, of="002D", width="figure")],
        "2013": [way("stretch", A, of="002D", width="en_dash")],
        "2014": [way("stretch", A, of="002D", width="em_dash")],
        "2015": [way("copy", A, of="2014"), way("stretch", A, of="002D", width="em_dash")],
        "2212": [way("minus", A, of="002D", on="002B")],
        "2E3A": [way("stretch", A, of="2014", width="em_dash", times=2), way("stretch", A, of="002D", width="em_dash", times=2)],
        "2E3B": [way("stretch", A, of="2014", width="em_dash", times=3), way("stretch", A, of="002D", width="em_dash", times=3)],
    }


def duplicates(inventory):
    """The inventory's recipe for each: a canonical singleton (exact) shares its source's glyph, a
    look-alike (accepted) copies it as a component, a separate glyph to adjust."""
    found = {}
    for code in GROUP_CODES["duplicates"]:
        entry = inventory[code]
        recipe = entry["recipes"][0]
        source = recipe["src"][0][0]
        ids = [m["id"] for m in recipe["machinery"]]
        if recipe["confidence"] == E and "shared_glyph" in ids:
            found[code] = [way("shared", E, of=source)]
        elif "move" in ids:
            found[code] = [way("copy", A, of=source)]
        else:
            found[code] = [way("copy", recipe["confidence"], of=source)]
    # More ways where a font lacks the first source: the corpus's next most common construction
    found["0374"].append(way("copy", A, of="2032"))  # the numeral sign as the prime (11 families) where there is no modifier prime
    found["02BC"].append(way("copy", A, of="0027", fallback=True))  # (never: only if the font lacks ’ too)
    found["02BC"].pop()  # (an apostrophe is not a turned comma: kept to the right single quote alone)
    found["02BD"].append(way("mirror", A, of="2019"))  # the reversed comma: the right single quote mirrored
    found["0189"].append(way("copy", A, of="0110"))
    found["2027"].append(way("copy", A, of="00B7"))
    return found


def punctuation():
    return {
        "2026": [way("row", E, of=["002E", "002E", "002E"], pair="2026")],
        "2025": [way("row", E, of=["002E", "002E"], pair="2026")],
        "201A": [way("copy", A, of="002C")],
        "201E": [way("row", A, of=["201A", "201A"], pair="201E"), way("row", A, of=["002C", "002C"], pair="201E")],
        "2018": [way("turn", A, of="2019", angle=180, pair="2018")],
        "201B": [way("mirror", A, of="2019")],
        "201C": [way("row", A, of=["2018", "2018"], pair="201C"), way("turn", A, of="201D", angle=180, pair="2018")],
        "201F": [way("row", A, of=["201B", "201B"], pair="201C"), way("mirror", A, of="201D")],
        "00AB": [way("row", A, of=["2039", "2039"], pair="00AB")],
        "00BB": [way("row", A, of=["203A", "203A"], pair="00AB"), way("mirror", A, of="00AB")],
        "203A": [way("mirror", A, of="2039")],
        "00A1": [way("turn", A, of="0021", angle=180, pair="00A1")],
        "00BF": [way("turn", A, of="003F", angle=180, pair="00BF")],
        "2E2E": [way("mirror", A, of="003F")],
        "204F": [way("mirror", A, of="003B")],
        "2E41": [way("mirror", A, of="002C")],
        "2E32": [way("turn", A, of="002C", angle=180, pair="2E32")],
        "00B7": [way("move", A, of="002E", to="x_middle")],
        "2033": [way("row", A, of=["2032", "2032"], pair="2033")],
        "2034": [way("row", A, of=["2032", "2032", "2032"], pair="2034")],
        "2057": [way("row", A, of=["2032", "2032", "2032", "2032"], pair="2034")],
        "2035": [way("mirror", A, of="2032")],
        "2036": [way("row", A, of=["2035", "2035"], pair="2033")],
        "2037": [way("row", A, of=["2035", "2035", "2035"], pair="2034")],
        "203C": [way("row", A, of=["0021", "0021"], pair="203C")],
        "2047": [way("row", A, of=["003F", "003F"], pair="2047")],
        "2048": [way("row", A, of=["003F", "0021"], pair="2048")],
        "2049": [way("row", A, of=["0021", "003F"], pair="2049")],
    }


# Look-alikes the inventory copies from a confusable whose shape the corpus's fonts do not use: their
# fonts copy another letter (Unicode's confusables map I-like letters to l; the corpus copies I)
LOOKALIKE_SOURCES = {"0399": "0049", "0406": "0049", "04C0": "0049"}


def lookalikes(inventory):
    found = {}
    for code in GROUP_CODES["lookalikes"]:
        recipe = inventory[code]["recipes"][0]
        source = LOOKALIKE_SOURCES.get(code, recipe["src"][0][0])
        found[code] = [way("copy", A, of=source)]
    found["04CF"].append(way("copy", A, of="0049"))  # (13 families copy the capital where there is no l... kept second)
    found["04CF"].pop()
    return found


def ligatures(inventory):
    found = {}
    for code in GROUP_CODES["ligatures"]:
        recipe = inventory[code]["recipes"][0]
        found[code] = [way("row", A, of=list(recipe["src"][0]), pair="letters")]
    # The middle dot of Catalan's L·L sits in the letters: L, then the dot raised to the middle of the
    # capital (Ŀ) or of the x-height (ŀ), the advance grown by the dot's
    found["013F"] = [way("row", A, of=["004C", "00B7"], pair="013F"), way("row", A, of=["004C", "002E"], pair="013F")]
    found["0140"] = [way("row", A, of=["006C", "00B7"], pair="0140"), way("row", A, of=["006C", "002E"], pair="0140")]
    found["0149"] = [way("row", A, of=["02BC", "006E"], pair="0149"), way("row", A, of=["2019", "006E"], pair="0149")]
    return found


def fractions(inventory):
    found = {}
    for code in GROUP_CODES["fractions"]:
        src = inventory[code]["recipes"][0]["src"][0]
        slash = src.index("2044")
        numerator = u"".join(unichr_hex(c) for c in src[:slash])
        denominator = u"".join(unichr_hex(c) for c in src[slash + 1:])
        found[code] = [way("fraction", A, numerator=numerator, denominator=denominator)]
    return found


def arrows():
    """Turned about the ink's center; each takes the sidebearings the corpus gives its kind of turn
    (pair: the measured character whose rule it follows)."""
    def turn(source, angle, pair):
        return [way("turn", A, of=source, angle=angle, pair=pair)]
    return {
        "2190": turn("2192", 180, "2190"), "2191": turn("2192", 90, "2191"), "2193": turn("2192", 270, "2191"),
        "21D0": turn("21D2", 180, "2190"), "21D1": turn("21D2", 90, "2191"), "21D3": turn("21D2", 270, "2191"),
        "25B2": turn("25B6", 90, "25B2"), "25BC": turn("25B6", 270, "25B2"), "25C0": turn("25B6", 180, "25C0"),
        "25B3": turn("25B7", 90, "25B2"), "25BD": turn("25B7", 270, "25B2"), "25C1": turn("25B7", 180, "25C0"),
        "2196": turn("2192", 135, "2197"), "2197": turn("2192", 45, "2197"), "2198": turn("2192", 315, "2197"),
        "2199": turn("2192", 225, "2197"),
    }


def turned(inventory):
    """Turned letters about the middle of their body (a lowercase's x-height, a capital's cap height: ʎ's
    descender comes up as y's tail), reversed ones mirrored, ʁ flipped upside down; every one a starting
    point (the tab says "likely usable as it is" where the font measures monoline). Where most of the
    corpus copies a look-alike instead (Ʌ of Λ, ǝ of ə), that copy first."""
    found = {}
    for code in GROUP_CODES["turned"]:
        recipe = inventory[code]["recipes"][0]
        source = recipe["src"][0][0]
        ids = [m["id"] for m in recipe["machinery"]]
        if "rotate180" in ids:
            found[code] = [way("turn", S, of=source, angle=180, about="body", body=body_of(code), check="turn")]
        elif u"upside down" in recipe["text"]:
            found[code] = [way("mirror", S, of=source, axis="y", check="turn")]
        else:
            found[code] = [way("mirror", S, of=source, check="mirror")]
    found["0245"].insert(0, way("copy", A, of="039B"))  # (34 of 49 families: Λ)
    found["01DD"].insert(0, way("copy", A, of="0259"))  # (the corpus's first construction: ə)
    return found


def body_of(code):
    """Which height a turned letter turns about the middle of: "cap" for a capital (or a titlecase letter),
    "x" else (a small capital's too). Stored in the table: FontLab's Python 2.7 has Unicode 5.2, where Ʞ and
    Ʇ (U+A7B0, U+A7B1: Unicode 7.0) are unassigned, and they turned about the x-height."""
    return "cap" if unicodedata.category(chr(int(code, 16))) in ("Lu", "Lt") else "x"


def characters(entries):
    """{hex: {"category", "name"}} of every character the table names (its characters, their sources):
    the notes describe them so (freelab_glyph_generation.describe_code), whatever Unicode the runtime has."""
    codes = set()
    for e in entries:
        codes.add(e["code"])
        for w in e["ways"]:
            for key in ("of", "on"):
                value = w.get(key)
                codes.update(value if isinstance(value, list) else [value] if value else [])
    return dict((code, {"category": unicodedata.category(chr(int(code, 16))), "name": unicode_name(code)})
                for code in sorted(codes))


def refresh(path, records_path=None):
    """The table at path, its Unicode-derived fields made again (body_of, characters) and, given the
    calibration's records, its monoline thresholds (monoline_rules, the measures as the tab takes them now:
    a record's contrast made two-sided, as round_measures gives it since reverse contrast counts)."""
    with io.open(path, encoding="utf-8") as handle:
        table = json.load(handle)
    for e in table["entries"]:
        for w in e["ways"]:
            if w.get("about") == "body":
                w["body"] = body_of(e["code"])
    table["characters"] = characters(table["entries"])
    if records_path:
        with io.open(records_path, encoding="utf-8") as handle:
            records = json.load(handle)
        two_sided = [(target, found, dict(measures, contrast=max(measures["contrast"], 1.0 / measures["contrast"])))
                     for target, found, measures in records]
        table["rules"]["monoline"] = monoline_rules(two_sided)
    write_table(table, path)
    return table


def write_table(table, path):
    text = json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True)
    assert "fontlab" not in text.lower(), "nothing of FontLab's alias data may enter the table"
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + u"\n")


def unichr_hex(code):
    return chr(int(code, 16))


GROUP_CODES = {}


# -- the corpus's layout constants ---------------------------------------------------------------------------

def license_of(font):
    text = " ".join(str(r) for r in font["name"].names if r.nameID in (13, 14)).lower()
    if any(marker in text for marker in PROPRIETARY):
        return None
    for marker, name in OPEN_LICENSES:
        if marker in text:
            return name
    return None


def font_files(corpus):
    found = sorted(glob.glob(os.path.join(corpus, "*.[to]t[fc]")))
    for name in SUBFOLDERS:
        for root, folders, files in os.walk(os.path.join(corpus, name)):
            folders[:] = sorted(f for f in folders if f != "work")
            found.extend(os.path.join(root, f) for f in sorted(files) if f.lower().endswith((".ttf", ".otf")))
    return found


class Measured(object):
    """A font's ink boxes and advances, by character, in ems."""

    def __init__(self, font):
        from fontTools.pens.boundsPen import BoundsPen
        self.font, self.cmap = font, font.getBestCmap() or {}
        self.glyphs = font.getGlyphSet()
        self.em = float(font["head"].unitsPerEm)
        self.metrics = font["hmtx"].metrics
        self.pen_class = BoundsPen
        self.boxes = {}

    def name(self, code):
        return self.cmap.get(code)

    def box(self, code):
        """(left, bottom, right, top) of a character's ink, in ems, or None."""
        name = self.name(code)
        if name is None:
            return None
        if name not in self.boxes:
            pen = self.pen_class(self.glyphs)
            try:
                self.glyphs[name].draw(pen)
            except Exception:
                pen.bounds = None
            self.boxes[name] = tuple(v / self.em for v in pen.bounds) if pen.bounds else None
        return self.boxes[name]

    def advance(self, code):
        name = self.name(code)
        return self.metrics[name][0] / self.em if name in self.metrics else None


ROW_TARGETS = {  # (target, its parts): two or more glyphs side by side
    "2026": ("002E", "002E", "002E"), "201E": ("002C", "002C"), "201C": ("2018", "2018"), "201D": ("2019", "2019"),
    "00AB": ("2039", "2039"), "00BB": ("203A", "203A"), "203C": ("0021", "0021"), "2047": ("003F", "003F"),
    "2048": ("003F", "0021"), "2049": ("0021", "003F"), "2033": ("2032", "2032"), "2034": ("2032", "2032", "2032"),
    "0132": ("0049", "004A"), "0133": ("0069", "006A"), "01C6": ("0064", "017E"), "01C9": ("006C", "006A"),
    "0149": ("2019", "006E"), "013F": ("004C", "00B7"), "0140": ("006C", "00B7"),
}
TURN_TARGETS = {"00A1": "0021", "00BF": "003F", "2018": "2019", "2E32": "002C"}
ARROW_TARGETS = {"2190": ("2192", 180), "2191": ("2192", 90), "2193": ("2192", 270), "2197": ("2192", 45),
                 "25B2": ("25B6", 90), "25C0": ("25B6", 180)}


def rotated_box(box, angle):
    """The box of a box's corners turned by angle about its center (exact for the quarter turns)."""
    import math
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    xs, ys = [], []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
        dx, dy = x - cx, y - cy
        xs.append(cx + c * dx - s * dy)
        ys.append(cy + s * dx + c * dy)
    return min(xs), min(ys), max(xs), max(ys)


# -- the monoline check's calibration: a drawn Я against R mirrored, И against N, ə against e turned ----------

CALIBRATION = []  # (pair, overlap, measures) per family, filled by survey()
CALIBRATION_PAIRS = (("042F", "0052", "mirror"), ("0418", "004E", "mirror"), ("0259", "0065", "turn"))
GRID = 100  # cells per em, for the overlap


def polygons(m, name):
    """A glyph's outline as polygons (curves flattened), in ems."""
    from fontTools.pens.basePen import BasePen

    class Flat(BasePen):
        def __init__(self, glyphs):
            BasePen.__init__(self, glyphs)
            self.found, self.now = [], []

        def _moveTo(self, p):
            self.now = [p]

        def _lineTo(self, p):
            self.now.append(p)

        def _curveToOne(self, p1, p2, p3):
            p0 = self.now[-1]
            for step in range(1, 9):
                t = step / 8.0
                u = 1 - t
                self.now.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                                 u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))

        def _closePath(self):
            if len(self.now) > 2:
                self.found.append(self.now)
            self.now = []

        _endPath = _closePath
    pen = Flat(m.glyphs)
    try:
        m.glyphs[name].draw(pen)
    except Exception:
        return []
    return [[(x / m.em, y / m.em) for x, y in polygon] for polygon in pen.found]


def raster(polys):
    """The cells (row, column) an outline fills, even-odd, on a GRID-per-em grid."""
    cells = set()
    box = gg.box_of(polys)
    if box is None:
        return cells
    for row in range(int(box[1] * GRID) - 1, int(box[3] * GRID) + 2):
        for start, end in gg.strokes(polys, "y", (row + 0.5) / GRID):
            for column in range(int(round(start * GRID)), int(round(end * GRID))):
                cells.add((row, column))
    return cells


def overlap(drawn, made):
    """How much two outlines cover alike (intersection over union), their inks centered on each other."""
    a, b = gg.box_of(drawn), gg.box_of(made)
    if a is None or b is None:
        return None
    dx, dy = (a[0] + a[2] - b[0] - b[2]) / 2.0, (a[1] + a[3] - b[1] - b[3]) / 2.0
    moved = [[(x + dx, y + dy) for x, y in polygon] for polygon in made]
    one, two = raster(drawn), raster(moved)
    return len(one & two) / float(len(one | two)) if one | two else None


def calibrate(m):
    measures = gg.monoline_measures(lambda name: polygons(m, name), lambda code: m.name(code))
    if measures is None:
        return
    for target, source, kind in CALIBRATION_PAIRS:
        drawn, base = m.name(int(target, 16)), m.name(int(source, 16))
        if not drawn or not base:
            continue
        made = polygons(m, base)
        box = gg.box_of(made)
        if box is None:
            continue
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        if kind == "mirror":
            made = [[(2 * cx - x, y) for x, y in polygon] for polygon in made]
        else:
            made = [[(2 * cx - x, 2 * cy - y) for x, y in polygon] for polygon in made]
        found = overlap(polygons(m, drawn), made)
        if found is not None:
            CALIBRATION.append((target, found, measures))


def measure(font, found):
    m = Measured(font)
    try:
        calibrate(m)
    except Exception:
        pass
    x_box, h_box = m.box(0x78), m.box(0x48)
    x_height = x_box[3] if x_box else None
    cap = h_box[3] if h_box else None
    # Rows: the gap between neighboring parts' ink, against the em and against the parts' own
    # sidebearings, and the target's outer sidebearings against the parts'
    for target, parts in ROW_TARGETS.items():
        tbox, tadv = m.box(int(target, 16)), m.advance(int(target, 16))
        boxes = [m.box(int(p, 16)) for p in parts]
        advances = [m.advance(int(p, 16)) for p in parts]
        if tbox is None or tadv is None or any(b is None for b in boxes) or any(a is None for a in advances):
            continue
        inks = [b[2] - b[0] for b in boxes]
        gaps = len(parts) - 1
        gap = ((tbox[2] - tbox[0]) - sum(inks)) / gaps
        sides = [(advances[i] - inks[i]) for i in range(len(parts))]  # each part's lsb + rsb
        inner = sum((advances[i] - boxes[i][2]) + boxes[i + 1][0] for i in range(gaps)) / gaps  # rsb + next lsb
        found[target + " gap/em"].append(gap)
        if inner > 1e-3:
            found[target + " gap/inner sidebearings"].append(gap / inner)
        found[target + " left - first left"].append(tbox[0] - boxes[0][0])
        found[target + " right side - last right side"].append((tadv - tbox[2]) - (advances[-1] - boxes[-1][2]))
        found[target + " advance - parts"].append(tadv - sum(advances))
        del sides
        if target in ("013F", "0140"):
            # the dot's place: L's advance to the dot's ink left, and its height (from a composite's component)
            name = m.name(int(target, 16))
            glyph = font["glyf"][name] if "glyf" in font and name in font["glyf"].glyphs else None
            dot_name = m.name(0xB7)
            if glyph is not None and glyph.isComposite() and dot_name:
                for comp in glyph.components:
                    if comp.glyphName in (dot_name, m.name(0x2E)):
                        dbox = m.box(0xB7) if comp.glyphName == dot_name else m.box(0x2E)
                        dy = comp.y / m.em
                        center = (dbox[1] + dbox[3]) / 2 + dy
                        ref = cap if target == "013F" else x_height
                        if ref:
                            found[target + " dot center/height"].append(center / ref)
                        found[target + " dot left - letter advance"].append(dbox[0] + comp.x / m.em - advances[0])
    # Turned glyphs: how far the turned ink stands from the source's place (turned about its center)
    for target, source in TURN_TARGETS.items():
        tbox, sbox = m.box(int(target, 16)), m.box(int(source, 16))
        tadv, sadv = m.advance(int(target, 16)), m.advance(int(source, 16))
        if tbox is None or sbox is None:
            continue
        found[target + " drop/em"].append(tbox[1] - sbox[1])
        if x_height:
            found[target + " top - x-height"].append(tbox[3] - x_height)
        found[target + " left - source right side"].append(tbox[0] - (sadv - sbox[2]))
        found[target + " advance - source"].append(tadv - sadv)
    # The middle dot: its center against the x-height
    dot, period = m.box(0xB7), m.box(0x2E)
    if dot and x_height:
        found["00B7 center/x-height"].append((dot[1] + dot[3]) / 2 / x_height)
    if dot and period:
        found["00B7 advance - period"].append(m.advance(0xB7) - m.advance(0x2E))
    # Arrows and triangles turned: the sidebearings and the height of the turned ink's center
    for target, (source, angle) in ARROW_TARGETS.items():
        tbox, sbox = m.box(int(target, 16)), m.box(int(source, 16))
        if tbox is None or sbox is None:
            continue
        tadv, sadv = m.advance(int(target, 16)), m.advance(int(source, 16))
        turned = rotated_box(sbox, angle)
        found[target + " center y - turned center y"].append((tbox[1] + tbox[3]) / 2 - (turned[1] + turned[3]) / 2)
        sides = sadv - (sbox[2] - sbox[0])
        if sides > 1e-3:
            found[target + " sidebearings/source's"].append((tadv - (tbox[2] - tbox[0])) / sides)
        found[target + " ink width/turned width"].append((tbox[2] - tbox[0]) / max(turned[2] - turned[0], 1e-6))


LETTER_ROWS = ("0132", "0133", "01C6", "01C9")  # the digraphs measured: what "letters" rows follow
ADVANCES = (0.9, 1.1)  # a row whose gap is this share of its parts' inner sidebearings is set at their advances


def median_of(layout, key, default=None):
    found = layout.get(key)
    return found["median"] if found else default


USABLE_OVERLAP = 0.9  # a drawn letter this close to the recipe's (intersection over union) is the recipe's
PRECISION_FLOOR = 0.7  # "likely usable": right for at least this share of the corpus's families so measured,
LIFT = 0.1  # and this much more often than for any family (a half turn is the recipe's in 75% of them already)
CONTRASTS = (1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0)
ASYMMETRIES = (0.03, 0.05, 0.1, 0.2)


def monoline_rules(records):
    """Per kind (mirror: Я and И; turn: ə), the thresholds under which "likely usable as it is" is right for
    at least PRECISION_FLOOR of the corpus's families, finding the most of those that draw the letter as
    the recipe makes it; with how right it is and how many it finds."""
    found = {}
    for kind, pairs in (("mirror", ("042F", "0418")), ("turn", ("0259",))):
        rows = [r for r in records if r[0] in pairs]
        usable = sum(1 for r in rows if r[1] >= USABLE_OVERLAP)
        floor = max(PRECISION_FLOOR, usable / float(max(len(rows), 1)) + LIFT)
        best = None
        for contrast in CONTRASTS:
            for asymmetry in ASYMMETRIES:
                rule = {"contrast": contrast, "stress": asymmetry, "serif": asymmetry}
                said = [r for r in rows if gg.likely_usable(r[2], rule, kind)]
                right = sum(1 for r in said if r[1] >= USABLE_OVERLAP)
                if not said or right / float(len(said)) < floor:
                    continue
                key = (right, -contrast, -asymmetry)
                if best is None or key > best[0]:
                    best = (key, dict(rule, right=round(right / float(len(said)), 3),
                                      finds=round(right / float(max(usable, 1)), 3), families=len(rows),
                                      base=round(usable / float(max(len(rows), 1)), 3)))
        found[kind] = best[1] if best else None
    return found


def rules(layout, records=()):
    """The runtime's constants, from the survey's statistics: a row's gap (None: the parts at their own
    advances, as the corpus sets IJ and the ellipsis), a turn's place and sidebearings, the middle dot's
    height, and the Catalan dot's place."""
    rows = {}
    for key in ("2026", "201E", "201C", "00AB", "2033", "2034", "203C", "2047", "2048", "2049", "0149"):
        inner = median_of(layout, key + " gap/inner sidebearings")
        rows[key] = None if inner is not None and ADVANCES[0] <= inner <= ADVANCES[1] else median_of(layout, key + " gap/em", 0.0)
    inner = [median_of(layout, key + " gap/inner sidebearings") for key in LETTER_ROWS]
    rows["letters"] = None if all(v is not None and ADVANCES[0] <= v <= ADVANCES[1] for v in inner) else 0.0
    turns = {}
    for key in ("00A1", "00BF"):  # turned, its top at the x-height (and this much of the em above it)
        turns[key] = {"top_over_x_height": median_of(layout, key + " top - x-height", 0.0)}
    for key in ("2018", "2E32"):
        turns[key] = {"drop": median_of(layout, key + " drop/em", 0.0)}
    for key in ("2190", "2191", "2197", "25B2", "25C0"):
        turns[key] = {"sides": median_of(layout, key + " sidebearings/source's", 1.0)}
    dots = {}
    for key in ("013F", "0140"):
        dots[key] = {"dot_left": median_of(layout, key + " dot left - letter advance", 0.0),
                     "dot_center": median_of(layout, key + " dot center/height", 0.5),
                     "right_side": median_of(layout, key + " right side - last right side", 0.0)}
    return {"rows": rows, "turns": turns, "dots": dots,
            "middle_dot": median_of(layout, "00B7 center/x-height", 0.5),
            "monoline": monoline_rules(records)}


def stats(values):
    values = sorted(values)
    if not values:
        return None
    q = statistics.quantiles(values, n=4) if len(values) >= 4 else [values[0], statistics.median(values), values[-1]]
    return {"n": len(values), "median": round(statistics.median(values), 4), "q1": round(q[0], 4), "q3": round(q[2], 4)}


def survey(corpus, limit=None):
    from fontTools.ttLib import TTFont
    found = collections.defaultdict(list)
    families = set()
    for path in font_files(corpus):
        if limit and len(families) >= limit:
            break
        try:
            font = TTFont(path, lazy=True)
            if license_of(font) is None:
                continue
            name = font["name"]
            family = str(name.getDebugName(16) or name.getDebugName(1) or "")
            if not family or family in families:
                continue
            families.add(family)
            measure(font, found)
        except Exception:
            continue
    return dict((key, stats(values)) for key, values in sorted(found.items())), len(families)


# -- the table -------------------------------------------------------------------------------------------------

def glyphs_names(xml_path, codes):
    """{code: Glyphs' name} from GlyphData.xml. A downloaded file: read with defusedxml where it is
    installed, else refused if it declares a document type or entities (what expat would expand)."""
    with io.open(xml_path, "rb") as handle:
        raw = handle.read()
    try:
        import defusedxml.ElementTree as safe
        root = safe.fromstring(raw)
    except ImportError:
        if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
            raise SystemExit("%s declares a document type: install defusedxml to read it" % xml_path)
        root = ET.fromstring(raw)
    names = {}
    for glyph in root.iter("glyph"):
        code = glyph.get("unicode")
        if code and code.upper() in codes and glyph.get("name"):
            names.setdefault(code.upper(), glyph.get("name"))
    return names


def unicode_name(code):
    try:
        return unicodedata.name(chr(int(code, 16)))
    except ValueError:
        return u""


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    if "--refresh" in sys.argv:
        parser.add_argument("--refresh", required=True, help="an existing table to make again from Unicode's data")
        parser.add_argument("--records", help="the calibration's records (--calibration's file): its thresholds again")
        args = parser.parse_args()
        table = refresh(args.refresh, args.records)
        print("%d characters refreshed; monoline %s" % (len(table["entries"]), table["rules"]["monoline"]))
        return
    parser.add_argument("inventory")
    parser.add_argument("glyphs_info", help="GlyphsInfo's GlyphData.xml")
    parser.add_argument("--corpus", default=CORPUS)
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--calibration", help="also write the monoline calibration's records here (not shipped)")
    args = parser.parse_args()
    with io.open(args.inventory, encoding="utf-8") as handle:
        data = json.load(handle)
    inventory = dict((e["code_points"][0], e) for e in data["entries"] if len(e["code_points"]) == 1)
    for key, _, codes in GROUPS:
        if codes:
            GROUP_CODES[key] = codes.split()
    GROUP_CODES["lookalikes"] = [code for code, e in sorted(inventory.items())
                                 if e["group"] == "lookalikes" and e["confidence"] == A]
    GROUP_CODES["fractions"] = [code for code, e in sorted(inventory.items()) if e["group"] == "fractions"]
    GROUP_CODES["turned"] = [code for code, e in sorted(inventory.items()) if e["group"] == "turned"]
    for key, count in EXPECTED.items():
        assert len(GROUP_CODES[key]) == count, (key, len(GROUP_CODES[key]))
    recipes = {}
    for made in (spaces(), dashes(), duplicates(inventory), punctuation(), lookalikes(inventory), ligatures(inventory),
                 fractions(inventory), arrows(), turned(inventory)):
        recipes.update(made)
    every = [code for key, _, _ in GROUPS for code in GROUP_CODES[key]]
    assert sorted(recipes) == sorted(every), set(recipes) ^ set(every)
    names = glyphs_names(args.glyphs_info, set(every))
    layout, families = survey(args.corpus, args.limit)
    if args.calibration:
        with io.open(args.calibration, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(CALIBRATION))
    groups, entries = [], []
    for key, title, _ in GROUPS:
        groups.append({"id": key, "title": title, "count": len(GROUP_CODES[key])})
        for code in GROUP_CODES[key]:
            e = inventory[code]
            corpus = e.get("corpus") or {}
            top = (corpus.get("constructions") or [{}])[0]
            entries.append({
                "code": code, "group": key, "unicode_name": unicode_name(code) or e.get("unicode_name", u""),
                "glyph_name": names.get(code) or e.get("glyph_name") or u"uni" + code,
                "ways": recipes[code],
                "research_confidence": e["confidence"],
                "families": corpus.get("families_with_char", 0), "deriving": corpus.get("families_deriving", 0),
                "most": [top.get("how", u""), top.get("families", 0)] if top else None,
            })
    out = {
        "format": 1,
        "about": u"Glyph Compose's Glyph generation recipes (FreeLab's own), made by compose/train/generation.py "
                 u"from the research inventory of 2026-11-16, Unicode's data, GlyphsInfo's glyph names, and "
                 u"measurements of the open-licensed corpus. Sources and licenses: glyph_generation_LICENSE.",
        "corpus_families": families,
        "settings": {"thin": 6, "hair": 11, "en_dash": 0.528, "em_dash": 0.862},
        "settings_why": {"thin": u"1/6 em (Unicode: 1/5 or 1/6; the corpus's median 0.158 em)",
                         "hair": u"1/11 em (the corpus's median 0.090 em)",
                         "en_dash": u"the corpus's median en dash, 0.528 em (507 families)",
                         "em_dash": u"the corpus's median em dash, 0.862 em (507 families)"},
        "rules": rules(layout, CALIBRATION),
        "layout": layout,
        "groups": groups,
        "entries": entries,
        "characters": characters(entries),
    }
    write_table(out, args.out)
    print("%d characters in %d groups; layout from %d families" % (len(entries), len(groups), families))


if __name__ == "__main__":
    main()
