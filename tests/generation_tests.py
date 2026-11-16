# -*- coding: utf-8 -*-
"""Tests of Glyph Compose's Glyph generation tab: its recipe table, the planning of each way on bare fonts
(outlines as polygons, so turned and stretched boxes are exact), the row texts, and the writes against
FontLab's objects stubbed. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import io
import json
import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "compose"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_glyph_generation as gg  # noqa: E402
import freelab_feature_code as fc  # noqa: E402

DATA = gg.load_data(os.path.join(HERE, os.pardir, "compose", gg.DATA_FILE))


def u(code):
    return gg.unichr_(code)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# A bare Latin font, 1,000 units to the em: no quotes but the right single one, no dashes, no arrows but
# the right one; every glyph a few rectangles (name: (code, advance, [contours], components))
BARE = {
    "space": (0x20, 260, [], None), "period": (0x2E, 250, [rect(90, 0, 160, 70)], None),
    "comma": (0x2C, 250, [rect(90, -120, 160, 70)], None), "hyphen": (0x2D, 300, [rect(50, 250, 250, 310)], None),
    "plus": (0x2B, 500, [rect(60, 320, 440, 380), rect(220, 160, 280, 540)], None),
    "exclam": (0x21, 260, [rect(100, 200, 160, 700), rect(100, 0, 160, 70)], None),
    "question": (0x3F, 450, [rect(100, 200, 350, 700), rect(180, 0, 250, 70)], None),
    "semicolon": (0x3B, 250, None, [("comma", (1, 0, 0, 1, 0, 0)), ("period", (1, 0, 0, 1, 0, 400))]),
    "quoteright": (0x2019, 230, [rect(80, 520, 150, 700)], None),
    "guilsinglleft": (0x2039, 300, [[(50, 250), (200, 100), (240, 140), (130, 250), (240, 360), (200, 400)]], None),
    "x": (0x78, 500, [rect(20, 0, 480, 500)], None), "H": (0x48, 700, [rect(80, 0, 620, 700)], None),
    "I": (0x49, 280, [rect(90, 0, 190, 700)], None), "J": (0x4A, 400, [rect(60, -50, 300, 700)], None),
    "L": (0x4C, 520, [rect(90, 0, 490, 700)], None), "l": (0x6C, 240, [rect(80, 0, 160, 740)], None),
    "i": (0x69, 240, [rect(80, 0, 160, 700)], None), "j": (0x6A, 240, [rect(20, -200, 160, 700)], None),
    "n": (0x6E, 560, [rect(80, 0, 480, 500)], None), "N": (0x4E, 700, [rect(80, 0, 620, 700)], None),
    "D": (0x44, 680, [rect(80, 0, 600, 700)], None), "Z": (0x5A, 600, [rect(40, 0, 560, 700)], None),
    "z": (0x7A, 480, [rect(40, 0, 440, 500)], None), "d": (0x64, 560, [rect(60, 0, 480, 740)], None),
    "A": (0x41, 650, [rect(10, 0, 640, 700)], None), "O": (0x4F, 720, [rect(40, -10, 680, 710)], None),
    "K": (0x4B, 640, [rect(80, 0, 620, 700)], None), "Omega": (0x3A9, 740, [rect(40, 0, 700, 710)], None),
    "zero": (0x30, 560, [rect(50, -10, 510, 710)], None), "one": (0x31, 560, [rect(150, 0, 400, 700)], None),
    "two": (0x32, 560, [rect(60, 0, 500, 710)], None), "four": (0x34, 560, [rect(40, 0, 520, 700)], None),
    "fraction": (0x2044, 120, [rect(-120, 0, 240, 700)], None),
    "arrowright": (0x2192, 800, [rect(60, 300, 700, 360), [(640, 230), (740, 330), (640, 430)]], None),
    "uni25B6": (0x25B6, 700, [[(80, 0), (620, 350), (80, 700)]], None),
    "uni25B7": (0x25B7, 700, None, [("uni25B6", (1, 0, 0, 1, 0, 0))]),
}


class FakeFont(gg.Font):
    """A font of polygons: boxes through any transform are the polygons' own (exact for any turn)."""

    def __init__(self, glyphs=None, forms=None, figure="zero"):
        gg.Font.__init__(self, 1000)
        self.glyphs = dict(glyphs or BARE)
        self.names = sorted(self.glyphs)
        self.forms = forms or {}
        self.figure = figure if figure in self.glyphs else None
        self.x_height = self.box("x")[3] if "x" in self.glyphs else None
        self.cap_height = self.box("H")[3] if "H" in self.glyphs else None

    def codes(self):
        return [g[0] for g in self.glyphs.values() if g[0]]

    def glyph_of(self, code):
        for name in self.names:
            if self.glyphs[name][0] == code:
                return name
        return None

    def polygons(self, name, matrix=gg.IDENTITY):
        code, advance, contours, components = self.glyphs[name]
        found = [[gg.mapped(matrix, x, y) for x, y in contour] for contour in contours or []]
        for inner, values in components or []:
            found.extend(self.polygons(inner, gg.compose(matrix, values)))
        return found

    def points(self, name, matrix=gg.IDENTITY):
        code, advance, contours, components = self.glyphs[name]
        found = []
        for contour in contours or []:
            found.extend(gg.mapped(matrix, x, y) for x, y in contour)
        for inner, values in components or []:
            found.extend(self.points(inner, gg.compose(matrix, values)))
        return found

    def box(self, name, matrix=gg.IDENTITY):
        if name not in self.glyphs:
            return None
        points = self.points(name, matrix)
        if not points:
            return None
        return (round(min(p[0] for p in points), 6), round(min(p[1] for p in points), 6),
                round(max(p[0] for p in points), 6), round(max(p[1] for p in points), 6))

    def advance(self, name):
        return float(self.glyphs[name][1])

    def composite(self, name):
        return not self.glyphs[name][2] and bool(self.glyphs[name][3])

    def components(self, name):
        return [inner for inner, _ in self.glyphs[name][3] or []] if name in self.glyphs else []

    def numr(self, digit):
        return self.forms.get(("numr", digit))

    def dnom(self, digit):
        return self.forms.get(("dnom", digit))


def plan(font=None, existing=False, settings=None):
    planner = gg.Planner(DATA, font or FakeFont(), settings, existing)
    planner.plan()
    return planner, dict((r.char, r) for r in planner.rows)


class TableTests(unittest.TestCase):
    def test_first_scope(self):
        entries = DATA["entries"]
        self.assertEqual(len(entries), 246)
        counts = dict((g["id"], g["count"]) for g in DATA["groups"])
        self.assertEqual(counts, {"spaces": 18, "dashes": 10, "duplicates": 44, "punctuation": 28, "lookalikes": 52,
                                  "ligatures": 17, "fractions": 20, "arrows": 16, "turned": 41})
        self.assertEqual(len(set(e["code"] for e in entries)), 246, "each character once")
        turned = [e for e in entries if e["group"] == "turned"]
        self.assertTrue(all(any(w["confidence"] == "starting point" for w in e["ways"]) for e in turned),
                        "the turned and reversed letters are starting points")
        ops = set(name[3:] for name in dir(gg.Planner) if name.startswith("op_"))
        for e in entries:
            self.assertTrue(e["ways"], e["code"])
            self.assertTrue(e["glyph_name"], e["code"])
            for way in e["ways"]:
                self.assertIn(way["op"], ops, e["code"])
                self.assertIn(way["confidence"], gg.CONFIDENCES, e["code"])

    def test_nothing_of_fontlabs_alias_data(self):
        with io.open(os.path.join(HERE, os.pardir, "compose", gg.DATA_FILE), encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(u"fontlab", text.lower(), "alias.dat states no license: nothing derived from it ships")
        with io.open(os.path.join(HERE, os.pardir, "compose", "glyph_generation_LICENSE"), encoding="utf-8") as handle:
            notice = handle.read()
        for words in (u"Unicode License V3", u"BSD 3-Clause", u"Apache License"):
            self.assertIn(words, notice)

    def test_rules_from_the_corpus(self):
        rules = DATA["rules"]
        self.assertIsNone(rules["rows"]["2026"], "the ellipsis's periods at their own advances")
        self.assertIsNone(rules["rows"]["letters"], "IJ and the digraphs at their advances")
        self.assertTrue(0.02 < rules["rows"]["201C"] < 0.05, "quotes a little apart")
        self.assertLess(rules["rows"]["00AB"], 0, "guillemets overlap")
        self.assertTrue(0.5 < rules["middle_dot"] < 0.7)
        self.assertTrue(-0.01 < rules["turns"]["00A1"]["top_over_x_height"] < 0.05)

    def test_the_look_alike_i_copies_the_capital(self):
        found = dict((e["code"], e) for e in DATA["entries"])
        for code in ("0399", "0406", "04C0"):
            self.assertEqual(found[code]["ways"][0]["of"], "0049", "the corpus copies I, not Unicode's confusable l")

    def test_settings_saved_over_the_suggestions(self):
        settings = gg.settings_of(DATA, {"thin": 5, "hair": "x", "en_dash": 9.0, "em_dash": 1.0})
        self.assertEqual((settings["thin"], settings["hair"], settings["en_dash"], settings["em_dash"]), (5, 11, 0.528, 1.0))
        self.assertEqual(gg.settings_of(DATA, {"thin": 30, "hair": 2})["thin"], 30, "what the boxes allow is kept")
        self.assertEqual(gg.settings_of(DATA, {"en_dash": 2.4})["en_dash"], 2.4)


class SpaceTests(unittest.TestCase):
    def test_widths_by_rule(self):
        planner, rows = plan()
        width = dict((r.hex, r.layout.advance) for r in planner.rows if r.group == "spaces")
        self.assertEqual(width["00A0"], 260, "the no-break space: the space's width")
        self.assertEqual(width["2002"], 500)
        self.assertEqual(width["2003"], 1000)
        self.assertEqual(width["2009"], round(1000 / 6.0), "thin: 1/6 em")
        self.assertEqual(width["200A"], round(1000 / 11.0), "hair: 1/11 em")
        self.assertEqual(width["202F"], width["2009"], "the narrow no-break space is a thin space")
        self.assertEqual(width["2007"], 560, "a tabular figure's width")
        self.assertEqual(width["2008"], 250, "the period's")
        self.assertEqual(width["200B"], 0)
        self.assertNotIn("3000", width, "the ideographic space only in a CJK font")
        self.assertTrue(all(r.layout.kind == "empty" for r in planner.rows if r.group == "spaces"))

    def test_a_tabular_figure_first(self):
        glyphs = dict(BARE, **{"zero.tf": (None, 600, [rect(50, -10, 550, 710)], None)})
        figure, forms = gg.figure_forms(fc, sorted(glyphs), dict((g[0], n) for n, g in glyphs.items() if g[0]))
        self.assertEqual(figure, "zero.tf")
        planner, rows = plan(FakeFont(glyphs, figure=figure))
        self.assertEqual(planner.by_hex["2007"].layout.advance, 600)
        self.assertEqual(planner.by_hex["2012"].layout.advance, 600, "the figure dash too")

    def test_settings_change_widths(self):
        planner, rows = plan(settings={"thin": 5, "en_dash": 0.5})
        self.assertEqual(planner.by_hex["2009"].layout.advance, 200)
        self.assertEqual(planner.by_hex["2013"].layout.advance, 500)

    def test_the_ideographic_space_in_a_cjk_font(self):
        glyphs = dict(BARE, **{"a-hira": (0x3042, 1000, [rect(100, 0, 900, 800)], None)})
        planner, rows = plan(FakeFont(glyphs))
        self.assertEqual(planner.by_hex["3000"].layout.advance, 1000)


class DashTests(unittest.TestCase):
    def test_dashes_keep_the_hyphens_thickness_and_sidebearings(self):
        planner, rows = plan()
        en = planner.by_hex["2013"]
        self.assertEqual(en.layout.advance, 528)
        self.assertEqual(planner.part_box(en.layout.parts[0]), (50, 250, 478, 310), "lsb and rsb 50, thickness 60")
        em = planner.by_hex["2014"]
        self.assertEqual(em.layout.advance, 862)
        self.assertEqual(planner.part_box(em.layout.parts[0])[2], 812)
        self.assertEqual(planner.by_hex["2015"].layout.parts[0].name, "emdash", "the horizontal bar: the em dash")
        self.assertEqual(planner.by_hex["2015"].needs, ["emdash"], "built here first")
        two = planner.by_hex["2E3A"]
        self.assertEqual(two.layout.parts[0].name, "hyphen", "no em dash in the font: from the hyphen")
        self.assertEqual(two.layout.advance, 1724)

    def test_the_two_em_dash_from_the_fonts_em_dash(self):
        glyphs = dict(BARE, emdash=(0x2014, 900, [rect(40, 250, 860, 310)], None))
        planner, rows = plan(FakeFont(glyphs))
        two = planner.by_hex["2E3A"]
        self.assertEqual((two.layout.parts[0].name, two.layout.advance), ("emdash", 1800))
        self.assertEqual(planner.part_box(two.layout.parts[0]), (40, 250, 1760, 310), "its ends kept: 40 each side")

    def test_the_minus_sits_on_the_plus(self):
        planner, rows = plan()
        minus = planner.by_hex["2212"]
        self.assertEqual(minus.layout.advance, 500, "the plus's advance")
        self.assertEqual(planner.part_box(minus.layout.parts[0]), (60, 320, 440, 380),
                         "the plus's width and height, the hyphen's thickness")

    def test_a_stretch_moves_the_nodes_right_of_the_middle(self):
        self.assertEqual(gg.stretched_points([(0, 0), (10, 0), (10, 5), (0, 5)], 5, 100),
                         [(0, 0), (110, 0), (110, 5), (0, 5)])


class PunctuationTests(unittest.TestCase):
    def test_turned_and_dropped_to_the_x_height(self):
        planner, rows = plan()
        box = planner.part_box(rows[u(0xA1)].layout.parts[0])
        self.assertEqual(box[3], 510, "its top at the x-height (and 0.01 em above it)")
        self.assertEqual(box[3] - box[1], 700, "the whole mark, turned")
        self.assertEqual(rows[u(0xA1)].layout.advance, 260)
        self.assertEqual(box[0], 260 - 160, "its sidebearings changed sides")

    def test_quotes_are_turned_not_mirrored_and_built_before_their_doubles(self):
        planner, rows = plan()
        left = rows[u(0x2018)]
        self.assertEqual(left.way["op"], "turn")
        self.assertFalse(gg.is_mirror(left.layout.parts[0].matrix))
        self.assertEqual(planner.part_box(left.layout.parts[0]), (80, 520, 150, 700), "in the same band, sides swapped")
        double = rows[u(0x201C)]
        self.assertEqual([p.name for p in double.layout.parts], ["quoteleft", "quoteleft"])
        self.assertEqual(double.needs, ["quoteleft"])
        order = [r.char for r in gg.build_order([double, left])]
        self.assertEqual(order, [u(0x2018), u(0x201C)], "the single quote first")
        gap = DATA["rules"]["rows"]["201C"] * 1000
        first, second = [planner.part_box(p) for p in double.layout.parts]
        self.assertAlmostEqual(second[0] - first[2], round(gap), delta=0.6)
        self.assertEqual(double.layout.advance, second[2] + 80, "the last quote's right sidebearing")

    def test_the_low_double_quote_of_two_commas_through_the_single(self):
        planner, rows = plan()
        low = rows[u(0x201E)]
        self.assertEqual([p.name for p in low.layout.parts], ["quotesinglbase", "quotesinglbase"])
        self.assertEqual(rows[u(0x201A)].layout.parts[0].name, "comma")

    def test_the_ellipsis_at_the_periods_advances(self):
        planner, rows = plan()
        dots = rows[u(0x2026)].layout
        self.assertEqual([p.matrix[4] for p in dots.parts], [0, 250, 500])
        self.assertEqual(dots.advance, 750)

    def test_mirrors(self):
        planner, rows = plan()
        single = rows[u(0x203A)]
        self.assertEqual((single.way["op"], single.layout.kind), ("mirror", "mirrored"),
                         "an outline glyph: its outlines mirrored, contours set right")
        reversed_semicolon = rows[u(0x204F)]
        self.assertEqual(reversed_semicolon.layout.kind, "components", "a glyph of components: corrected glyphs")
        double = rows[u(0xBB)]
        self.assertEqual([p.name for p in double.layout.parts], ["guilsinglright", "guilsinglright"])

    def test_the_middle_dot(self):
        planner, rows = plan()
        box = planner.part_box(rows[u(0xB7)].layout.parts[0])
        self.assertAlmostEqual((box[1] + box[3]) / 2.0, DATA["rules"]["middle_dot"] * 500, delta=0.6)

    def test_what_a_font_lacks_is_said(self):
        planner, rows = plan()
        self.assertEqual(rows[u(0x2033)].missing, u"needs the prime (U+2032)")
        self.assertEqual(rows[u(0x2190)].missing, None)
        self.assertEqual(rows[u(0x21D0)].missing, u"needs ⇒ (U+21D2)", "a sign as itself")
        self.assertIsNone(rows[u(0x2033)].layout)


class LetterTests(unittest.TestCase):
    def test_duplicates_share_or_copy(self):
        planner, rows = plan()
        ohm = rows[u(0x2126)]
        self.assertEqual((ohm.layout.kind, ohm.layout.shared), ("shared", "Omega"), "a second code point")
        self.assertEqual(rows[u(0x212A)].layout.shared, "K")
        self.assertIn(u"needs", rows[u(0xB5)].missing, "no mu to copy")
        self.assertEqual(rows[u(0x0410)].layout.parts[0].name, "A", "the Cyrillic A copies the Latin A")
        self.assertEqual(rows[u(0x0406)].layout.parts[0].name, "I")

    def test_existing_glyphs_rebuilt_as_copies(self):
        glyphs = dict(BARE, Ohm=(0x2126, 740, [rect(40, 0, 700, 710)], None))
        planner, rows = plan(FakeFont(glyphs), existing=True)
        ohm = rows[u(0x2126)]
        self.assertTrue(ohm.existing)
        self.assertEqual(ohm.layout.kind, "components", "its own glyph cannot hand its code point on")
        self.assertIn(u"replaces the font's own glyph", gg.note_text(ohm))
        planner, rows = plan(FakeFont(glyphs))
        self.assertNotIn(u(0x2126), rows, "listed only when asked")

    def test_a_glyph_that_stands_for_two_characters_is_never_rebuilt(self):
        """Omega encoded for U+2126 too: rebuilding the Ohm row would make Omega a component of itself."""
        glyphs = dict(BARE, Omega=(0x3A9, 740, [rect(40, 0, 700, 710)], None))
        font = FakeFont(glyphs)
        font.glyph_of = lambda code, of=font.glyph_of: "Omega" if code == 0x2126 else of(code)
        font.codes = lambda: [g[0] for g in glyphs.values() if g[0]] + [0x2126]
        planner, rows = plan(font, existing=True)
        self.assertNotIn(u(0x2126), rows)
        self.assertEqual(sorted(font.codes_of("Omega")), [0x3A9, 0x2126])

    def test_a_name_no_glyph_has(self):
        glyphs = dict(BARE, endash=(None, 500, [], None), uni2013=(None, 500, [], None))
        planner, rows = plan(FakeFont(glyphs))
        self.assertEqual(rows[u(0x2013)].name, u"uni2013.1")

    def test_ligature_letters_side_by_side(self):
        planner, rows = plan()
        ij = rows[u(0x0133)].layout
        self.assertEqual([(p.name, p.matrix[4]) for p in ij.parts], [("i", 0), ("j", 240)])
        self.assertEqual(ij.advance, 480)
        self.assertIn(u"needs", rows[u(0x01C6)].missing, u"d with z caron: Diacritics' z caron first")

    def test_the_catalan_dot(self):
        planner, rows = plan()
        ldot = rows[u(0x0140)]
        rule = DATA["rules"]["dots"]["0140"]
        dot = planner.part_box(ldot.layout.parts[1])
        self.assertAlmostEqual(dot[0], 240 + rule["dot_left"] * 1000, delta=1)
        self.assertAlmostEqual((dot[1] + dot[3]) / 2.0, rule["dot_center"] * 500, delta=1)
        self.assertEqual(ldot.layout.parts[1].name, "periodcentered", "the middle dot, built here first")


class FractionTests(unittest.TestCase):
    def test_needs_the_figure_forms_first(self):
        planner, rows = plan()
        self.assertIn(u"Feature Code, Forms tab", rows[u(0xBD)].missing)

    def test_numerator_fraction_slash_denominator(self):
        forms = {("numr", u"1"): "one.numr", ("dnom", u"2"): "two.dnom", ("dnom", u"4"): "four.dnom"}
        glyphs = dict(BARE, **{"one.numr": (None, 330, [rect(80, 400, 230, 700)], None),
                               "two.dnom": (None, 330, [rect(40, 0, 290, 300)], None),
                               "four.dnom": (None, 330, [rect(30, 0, 300, 300)], None)})
        planner, rows = plan(FakeFont(glyphs, forms))
        half = rows[u(0xBD)].layout
        self.assertEqual([(p.name, p.matrix[4]) for p in half.parts], [("one.numr", 0), ("fraction", 330), ("two.dnom", 450)])
        self.assertEqual(half.advance, 780)
        self.assertIn(u"3's numerator", rows[u(0xBE)].missing, "three quarters: no three.numr")

    def test_feature_codes_forms_are_read(self):
        names = ["zero", "one", "one.numr", "one.dnom", "two.denominator"]
        figure, forms = gg.figure_forms(fc, names, {0x30: "zero", 0x31: "one", 0x32: "two"})
        self.assertEqual(forms[("numr", u"1")], "one.numr")
        self.assertEqual(forms[("dnom", u"1")], "one.dnom")


class ArrowTests(unittest.TestCase):
    def test_turned_by_quarter_turns_and_diagonals(self):
        planner, rows = plan()
        right = FakeFont().box("arrowright")
        up = rows[u(0x2191)].layout
        box = planner.part_box(up.parts[0])
        self.assertEqual(box[2] - box[0], right[3] - right[1], "a quarter turn: its width the arrow's height")
        self.assertEqual(box[3] - box[1], right[2] - right[0])
        self.assertAlmostEqual((box[1] + box[3]) / 2.0, (right[1] + right[3]) / 2.0, delta=0.01)
        sides = (800 - (right[2] - right[0])) * DATA["rules"]["turns"]["2191"]["sides"] / 2.0
        self.assertAlmostEqual(box[0], sides, delta=0.6)
        self.assertAlmostEqual(up.advance, box[2] + sides, delta=1)
        left = rows[u(0x2190)].layout
        self.assertEqual(left.advance, 800, "a half turn keeps the advance")
        diagonal = planner.part_box(rows[u(0x2197)].layout.parts[0])
        self.assertLess(diagonal[2] - diagonal[0], right[2] - right[0], "45 degrees: narrower than the arrow")
        self.assertEqual(rows[u(0x25C0)].layout.advance, 700)
        self.assertEqual(rows[u(0x25B3)].layout.parts[0].name, "uni25B7")


def frame(x0, y0, x1, y1, side, cap):
    """An O of four strokes: sides side thick, top and bottom cap thick (its counter a hole)."""
    return [rect(x0, y0, x1, y1), rect(x0 + side, y0 + cap, x1 - side, y1 - cap)]


TURNABLE = dict(BARE, **{
    "h": (0x68, 560, [rect(80, 0, 160, 740), rect(80, 420, 480, 500), rect(400, 0, 480, 500)], None),
    "R": (0x52, 640, [rect(90, 0, 590, 700)], None), "N": (0x4E, 700, [rect(80, 0, 620, 700)], None),
    "Rsmall": (0x0280, 520, [rect(60, 0, 460, 500)], None)})


class TurnedTests(unittest.TestCase):
    def font(self, side, cap, serif=0):
        glyphs = dict(TURNABLE, O=(0x4F, 720, frame(40, -10, 680, 710, side, cap), None))
        if serif:  # (a foot reaching out on one side only)
            glyphs["I"] = (0x49, 280, [rect(90, 0, 190, 700), rect(90 - serif, 0, 190, 20)], None)
        return FakeFont(glyphs)

    def test_a_turned_letter_turns_about_its_body(self):
        planner, rows = plan(self.font(80, 80))
        box = planner.part_box(rows[u(0x0265)].layout.parts[0])
        self.assertEqual((box[1], box[3]), (-240, 500), "h's ascender comes down as a descender, about x-height/2")
        self.assertEqual(rows[u(0x0265)].layout.advance, 560)
        cap = planner.part_box(rows[u(0x2C6F)].layout.parts[0])
        self.assertEqual((cap[1], cap[3]), (0, 700), "a capital about half its cap height")
        flipped = rows[u(0x0281)].layout
        self.assertEqual((flipped.axis, planner.part_box(flipped.parts[0])), ("y", (60, 0, 460, 500)), "upside down")
        self.assertEqual(rows[u(0x042F)].way["op"], "mirror")

    def test_monoline_measures(self):
        self.assertAlmostEqual(gg.round_measures(frame(40, -10, 680, 710, 80, 80))[0], 1.0)
        self.assertAlmostEqual(gg.round_measures(frame(40, -10, 680, 710, 120, 30))[0], 4.0)
        self.assertEqual(gg.round_measures(frame(40, -10, 680, 710, 80, 80))[1], 0.0, "upright stress")
        self.assertEqual(gg.serif_measure([rect(90, 0, 190, 700)]), 0.0)
        self.assertAlmostEqual(gg.serif_measure([rect(90, 0, 190, 700), rect(40, 0, 190, 20)]), 0.5)
        self.assertIsNone(gg.round_measures([rect(0, 0, 10, 10)]), "no counter: nothing to read")

    def test_a_monoline_design_is_likely_usable_as_it_is(self):
        mono = plan(self.font(80, 80))[1]
        self.assertEqual(gg.confidence_text(mono[u(0x042F)]), gg.LIKELY)
        self.assertNotIn(gg.DRAFT_NOTE, gg.note_text(mono[u(0x042F)]))
        contrast = plan(self.font(90, 50))[1]  # (contrast 1.8: past a mirror's threshold, within a half turn's)
        self.assertEqual(gg.confidence_text(contrast[u(0x042F)]), u"starting point", "a mirror in a contrast design")
        self.assertIn(gg.DRAFT_NOTE, gg.note_text(contrast[u(0x042F)]))
        self.assertEqual(gg.confidence_text(contrast[u(0x0265)]), gg.LIKELY, "a half turn keeps contrast as it is")
        serifs = plan(self.font(80, 80, serif=60))[1]
        self.assertEqual(gg.confidence_text(serifs[u(0x0265)]), u"starting point", "a foot on one side only")
        self.assertEqual(gg.confidence_text(serifs[u(0x042F)]), u"starting point")

    def test_reverse_contrast_is_no_monoline(self):
        # Codex's review: sides 30 thick, top and bottom 120 (contrast 0.25) passed as monoline
        self.assertAlmostEqual(gg.round_measures(frame(40, -10, 680, 710, 30, 120))[0], 4.0, msg="two-sided")
        reverse = plan(self.font(30, 120))[1]
        self.assertEqual(gg.confidence_text(reverse[u(0x042F)]), u"starting point")
        self.assertIn(gg.DRAFT_NOTE, gg.note_text(reverse[u(0x042F)]))
        self.assertEqual(gg.confidence_text(reverse[u(0x0265)]), u"starting point", "past a half turn's 2.0 too")
        self.assertEqual(gg.confidence_text(plan(self.font(80, 80))[1][u(0x042F)]), gg.LIKELY, "a monoline O still is")
        slight = plan(self.font(80, 84))[1]  # (top and bottom a little heavier: 1.05, either way round)
        self.assertEqual(gg.confidence_text(slight[u(0x042F)]), gg.LIKELY)

    def test_a_turned_capital_turns_about_its_cap_height_whatever_unicode_the_runtime_has(self):
        # FontLab's Python 2.7 has Unicode 5.2: Ʞ and Ʇ (U+A7B0, U+A7B1: Unicode 7.0) are unassigned there
        import unicodedata
        glyphs = dict(TURNABLE, T=(0x54, 600, [rect(40, 0, 560, 700)], None))
        original = unicodedata.category
        unicodedata.category = lambda ch: u"Cn" if ord(ch) in (0xA7B0, 0xA7B1) else original(ch)
        try:
            planner, rows = plan(FakeFont(glyphs))
            for code in (0xA7B0, 0xA7B1):
                box = planner.part_box(rows[u(code)].layout.parts[0])
                self.assertEqual((box[1], box[3]), (0, 700), "U+%04X at the cap height, not 200 units down" % code)
            self.assertEqual(gg.describe_code("2E32", DATA["characters"]), u"the turned comma (U+2E32)")
            self.assertEqual(gg.describe_code("A7B0", DATA["characters"]), u"%s (U+A7B0)" % u(0xA7B0))
        finally:
            unicodedata.category = original
        small = planner.part_box(rows[u(0x0265)].layout.parts[0])
        self.assertEqual((small[1], small[3]), (-240, 500), "a lowercase about its x-height, as before")

    def test_the_table_says_each_turned_letters_body(self):
        turned = [(e["code"], w) for e in DATA["entries"] for w in e["ways"] if w.get("about") == "body"]
        self.assertTrue(turned)
        self.assertTrue(all(w.get("body") in ("cap", "x") for _, w in turned))
        caps = sorted(code for code, w in turned if w["body"] == "cap")
        self.assertEqual(caps, ["019C", "0245", "2C6F", "2C70", "A7B0", "A7B1"])
        named = DATA["characters"]
        for e in DATA["entries"]:  # (every character a note may name, as the table's Unicode has it)
            for w in e["ways"]:
                for key in ("of", "on"):
                    for code in (w[key] if isinstance(w.get(key), list) else [w[key]] if w.get(key) else []):
                        self.assertIn(code, named)
            self.assertIn(e["code"], named)

    def test_the_corpus_thresholds(self):
        rules = DATA["rules"]["monoline"]
        self.assertLessEqual(rules["mirror"]["contrast"], 1.2, "a mirror wants a monoline design")
        for kind in ("mirror", "turn"):
            self.assertGreaterEqual(rules[kind]["right"], 0.7)
            self.assertGreater(rules[kind]["right"], rules[kind]["base"], "better than saying it of every family")


class HandOverTests(unittest.TestCase):
    """Font Check's hand-over: letters with diacritics to the Diacritics tab, the rest of the table to Glyph
    generation, which lists them alone at first."""

    def test_split_between_the_tabs(self):
        sys.modules.pop("freelab_glyph_compose", None)
        import freelab_glyph_compose as cm
        table = set(gg.unichr_(int(e["code"], 16)) for e in DATA["entries"])
        letters, others = cm.handed_over([u(0x1EBD), u(0x02BC), u(0x2013), u(0x1F71), u(0x0101), u(0x00A0)], table)
        self.assertEqual(others, [u(0x02BC), u(0x2013), u(0x00A0)])
        self.assertEqual(letters, [u(0x1EBD), u(0x1F71), u(0x0101)], "a letter with an oxia is the Diacritics tab's")

    def test_the_log_says_what_each_tab_holds(self):
        sys.modules.pop("freelab_glyph_compose", None)
        import freelab_glyph_compose as cm
        lines = []
        dialog = cm.AccentsDialog.__new__(cm.AccentsDialog)
        dialog.ak = Stub(b=lambda text: u"%s" % text)
        dialog.log = Stub(add=lambda text, kind="info": lines.append(text))
        for letters, others in ((2, 2), (3, 1), (1, 2), (0, 1)):
            dialog.given, dialog.generation_given = [u"a"] * letters, [u"-"] * others
            dialog.say_handed_over()
        self.assertEqual(lines, [
            u"From Font Check: 2 letters with diacritics on the <i>Diacritics</i> tab and 2 other glyphs on <i>Glyph "
            u"generation</i> (shown first: <i>Glyph generation</i>, as many on each).",
            u"From Font Check: 3 letters with diacritics on the <i>Diacritics</i> tab and 1 other glyph on <i>Glyph "
            u"generation</i> (shown first: <i>Diacritics</i>, the tab with more).",
            u"From Font Check: 1 letter with diacritics on the <i>Diacritics</i> tab and 2 other glyphs on <i>Glyph "
            u"generation</i> (shown first: <i>Glyph generation</i>, the tab with more).",
            u"From Font Check: 1 other glyph, on <i>Glyph generation</i>."])

    def test_the_list_holds_what_was_handed_over(self):
        page = gg.GenerationPage.__new__(gg.GenerationPage)
        page.given, page.list_box = [u(0x02BC), u(0x2013)], Stub(currentIndex=0)
        self.assertEqual(page.listed_codes(), set(["02BC", "2013"]))
        planner = gg.Planner(DATA, FakeFont(), None, False, page.listed_codes())
        self.assertEqual(sorted(r.hex for r in planner.plan()), ["02BC", "2013"])
        page.list_box = Stub(currentIndex=1)
        self.assertIsNone(page.listed_codes(), "Every group")
        page.given = []
        self.assertIsNone(page.listed_codes())

    def test_a_character_handed_over_alone_keeps_what_it_is_built_of(self):
        # Codex's review: ‟ (U+201F) is two ‛ (U+201B), which the font lacks too; Font Check (the whole table)
        # offered it, the list of ‟ alone could not build it
        whole = gg.Planner(DATA, FakeFont())
        whole.plan()
        self.assertIsNotNone(whole.by_hex["201F"].layout)
        alone = gg.Planner(DATA, FakeFont(), codes=set(["201F"]))
        self.assertEqual([r.hex for r in alone.plan()], ["201F"], "only what was handed over is listed")
        row = alone.by_hex["201F"]
        self.assertIsNotNone(row.layout, row.missing)
        self.assertEqual([p.name for p in row.layout.parts], [p.name for p in whole.by_hex["201F"].layout.parts])
        self.assertEqual([r.hex for r in alone.prerequisites([row])], ["201B"], "‛ built with it")


class TextTests(unittest.TestCase):
    BANNED = (u"—", u" · ", u" -- ")  # (as separators: a character a note names may be one)

    def test_cells_are_short_notes(self):
        glyphs = dict(BARE, **{"one.numr": (None, 330, [rect(80, 400, 230, 700)], None),
                               "two.dnom": (None, 330, [rect(40, 0, 290, 300)], None)})
        planner, rows = plan(FakeFont(glyphs, {("numr", u"1"): "one.numr", ("dnom", u"2"): "two.dnom"}), existing=True)
        for r in planner.rows:
            for text in (gg.recipe_text(r, planner.settings, DATA["rules"]), gg.note_text(r), gg.confidence_text(r)):
                self.assertFalse(text.endswith(u"."), (r.hex, text))
                for banned in self.BANNED:
                    self.assertNotIn(banned, text, (r.hex, text))
        self.assertEqual(gg.recipe_text(rows[u(0x2013)], planner.settings), u"hyphen drawn 528 units wide")
        self.assertEqual(gg.recipe_text(rows[u(0x2026)], planner.settings), u"period + period + period")
        self.assertEqual(gg.recipe_text(rows[u(0x2126)], planner.settings), u"a second code point on Omega")
        self.assertEqual(gg.recipe_text(rows[u(0x2009)], planner.settings), u"empty, 1/6 em (Thin space)")

    def test_counts_follow_their_number(self):
        self.assertEqual(gg.corpus_text(1, 1), u"1 family of the corpus has it; 1 of them builds it of other glyphs.")
        self.assertEqual(gg.corpus_text(509, 0), u"509 families of the corpus have it; 0 of them build it of other glyphs.")

    def test_a_starting_point_says_so(self):
        planner, rows = plan()
        row = rows[u(0x2013)]
        row.way = dict(row.way, confidence="starting point")
        self.assertIn(gg.DRAFT_NOTE, gg.note_text(row))


# -- the writes, FontLab's objects stubbed -------------------------------------------------------------------

class Transform(object):
    def __init__(self, *values):
        self.values = tuple(values) if values else gg.IDENTITY

    def m11(self):
        return self.values[0]

    def m12(self):
        return self.values[1]

    def m21(self):
        return self.values[2]

    def m22(self):
        return self.values[3]

    def dx(self):
        return self.values[4]

    def dy(self):
        return self.values[5]


class Node(object):
    def __init__(self, x, y):
        self.x, self.y, self.type = x, y, u"on"


class Contour(object):
    def __init__(self, points):
        self._nodes = [Node(x, y) for x, y in points]

    def nodes(self):
        return self._nodes

    def clone(self):
        return Contour([(n.x, n.y) for n in self._nodes])


class Shape(object):
    def __init__(self, contours=(), component=None, transform=None):
        self.contours = list(contours)
        self.isComponent = component is not None
        self.shapeData = type("Data", (object,), {"componentGlyph": component})()
        self.transform = transform or Transform()

    def addContours(self, contours, keep):
        self.contours.extend(contours)


class Layer(object):
    def __init__(self, shapes=(), advance=0):
        self.shapes, self.advanceWidth = list(shapes), advance

    def removeAllShapes(self):
        self.shapes = []

    def setGlyphComponents(self, components, width, package, flag):
        self.through_components = True
        for component in components:
            self.shapes.append(Shape(component=component._glyph, transform=component.transform))
        self.advanceWidth = width

    def addShape(self, shape):
        self.shapes.append(shape)

    def update(self):
        pass


class FgGlyph(object):
    def __init__(self, codes):
        self.unicodes = list(codes)

    @property
    def unicode(self):
        return self.unicodes[0] if self.unicodes else None

    @unicode.setter
    def unicode(self, code):
        self.unicodes = [code]


class Glyph(object):
    def __init__(self, name, layers=None, codes=()):
        self.name, self.layers_by, self.fgGlyph = name, layers or {}, FgGlyph(codes)
        self.isNull = False

    def getLayerByName(self, master, create=False):
        if master not in self.layers_by and create:
            self.layers_by[master] = Layer()
        return self.layers_by.get(master)

    def removeLayer(self, layer):
        for master, own in list(self.layers_by.items()):
            if own is layer:
                del self.layers_by[master]


class Package(object):
    def __init__(self, glyphs, masters=("Regular",)):
        self.glyphs, self.masters, self.master = dict((g.name, g) for g in glyphs), list(masters), masters[0]
        self.deleted, self.rebuilt = [], 0
        package = self
        self.fgPackage = type("Fg", (object,), {"id": 7, "rebuildMaps": lambda this: package.rebuild(),
                                                "glyphs": property(lambda this: [g.fgGlyph for g in package.glyphs.values()])})()
        self.tfn, self.upm = u"Bare", 1000

    def rebuild(self):
        self.rebuilt += 1

    def findName(self, name):
        return self.glyphs.get(name)

    def findUnicode(self, code):
        return next((g for g in self.glyphs.values() if code in g.fgGlyph.unicodes), None)

    def addGlyph(self, new):
        self.glyphs[new.name] = Glyph(new.name)

    def deleteGlyph(self, glyph):
        self.deleted.append(glyph.name)
        self.glyphs.pop(glyph.name, None)


def package_of(font, masters=("Regular",)):
    glyphs = []
    for name, (code, advance, contours, components) in font.glyphs.items():
        layers = {}
        for master in masters:
            shapes = [Shape([Contour(c) for c in contours])] if contours else []
            for inner, values in components or []:
                shapes.append(Shape(component=inner, transform=Transform(*values)))
            layers[master] = Layer(shapes, advance)
        glyphs.append(Glyph(name, layers, [code] if code else []))
    return Package(glyphs, masters)


class Stub(object):
    def __init__(self, **values):
        self.__dict__.update(values)


class Component(object):
    """FontLab's GlyphComponent: no name to read back (live 2026-11-16: 'GlyphComponent' object has no
    attribute 'name'); the tests read the glyph through _glyph."""

    def __init__(self, name):
        self._glyph, self.transform = name, None


class Cm(object):
    """Glyph Compose's module, as the tab uses it."""
    MirrorError = type("MirrorError", (Exception,), {})

    def __init__(self):
        self.mirrored = []

    def new_glyph(self, fontlab, package, name):
        return Stub(name=name)

    def mirror_axis(self, m11, m12, m21, m22):
        return "x"

    def source_mirror(self, ak, package, master, name, axis):
        return (-1.0, 1.0, package.findName(name).getLayerByName(master).advanceWidth, 0.0)

    def without_mirror(self, values, mirror):
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def make_corrected(self, fontlab, ak, package, masters, source, axis, name):
        package.addGlyph(Stub(name=name))
        glyph = package.findName(name)
        for master in masters:
            glyph.getLayerByName(master, True).addShape(Shape([Contour([(0, 0)])]))
        self.mirrored.append((source, name))
        return glyph

    def undo_words(self, status, text):
        return text

    def shape_copy(self, shape):
        return Shape(list(shape.contours), shape.shapeData.componentGlyph if shape.isComponent else None, shape.transform)

    def report_write(self, status, log):
        pass

    def build_text(self, checked, hidden):
        return u"Build checked glyphs"


class WriteTests(unittest.TestCase):
    def page(self, font=None, masters=("Regular",)):
        font = font or FakeFont()
        package = package_of(font, masters)
        page = gg.GenerationPage.__new__(gg.GenerationPage)
        page.data, page.settings, page.fc = DATA, gg.settings_of(DATA), Stub(place_node=self.place)
        page.cm = Cm()
        page.font, page.package, page.master = font, package, masters[0]
        page.planner_now = gg.Planner(DATA, font, None, False)
        page.rows = page.planner_now.plan()
        page.just_built = set()
        page.font_in = lambda package_, master: font
        page.harvest = page.update_buttons = lambda: None
        page.existing_box = Stub(checked=False)
        page.run = lambda same_font=True: None
        page.fontlab = Stub(GlyphComponent=Component, flShape=lambda: Shape())
        steps, logged = [], []
        page.ak = Stub(notify_changed=lambda fontlab, package_, title, touched: steps.append((title, list(touched))),
                       b=lambda text: u"%s" % text, html=lambda text: u"%s" % text)
        page.owner = Stub(package_key=lambda p: (u"bare", 7) if p is not None else None, current_font=lambda: package,
                          log=Stub(add=lambda text, kind="info": logged.append((kind, text))),
                          begin_write=lambda p, glyphs=(): steps.append(("begin", [g.name for g in glyphs])) or True,
                          end_write=lambda p, wrote=True: steps.append(("end", wrote)),
                          corrector=lambda package_, masters_, made, touched: self.corrector(package_, made))
        return page, package, steps, logged

    def place(self, node, x, y):
        node.x, node.y = x, y

    def corrector(self, package, made):
        def corrected(source, axis):
            name = source + ".mirrored"
            if package.findName(name) is None:
                package.addGlyph(Stub(name=name))
                made.append(name)
            return name
        return corrected

    def build(self, page, codes):
        saved = gg._qt
        try:
            gg._qt = lambda: (None, Stub(QTransform=Transform))
            for r in page.rows:
                r.checked = r.code in codes
            page.build()
        finally:
            gg._qt = saved

    def test_one_history_step_with_the_shared_glyphs_recorded_first(self):
        page, package, steps, logged = self.page()
        self.build(page, [0x2126, 0x2013, 0x2009])
        self.assertEqual(steps[0], ("begin", ["Omega"]), "the glyph that takes a code point recorded before")
        self.assertEqual(package.findName("Omega").fgGlyph.unicodes, [0x3A9, 0x2126], "no new glyph: a second code point")
        self.assertIsNone(package.findName("Ohm"))
        self.assertEqual([s[0] for s in steps], ["begin", u"FreeLab Glyph Compose", "end"], "one step")
        self.assertTrue(package.rebuilt, "FontLab's lookups rebuilt")
        thin = package.findName("thinspace").getLayerByName("Regular")
        en_layer = package.findName("endash").getLayerByName("Regular")
        self.assertTrue(getattr(thin, "through_components", False) and getattr(en_layer, "through_components", False),
                        "every new layer made through setGlyphComponents, none given too: a layer made otherwise "
                        "crashed FontLab when the glyph's fgGlyph was read (live 2026-11-16)")
        self.assertEqual((thin.shapes, thin.advanceWidth, package.findName("thinspace").fgGlyph.unicodes),
                         ([], 167.0, [0x2009]))
        en = package.findName("endash").getLayerByName("Regular")
        self.assertEqual(en.advanceWidth, 528.0)
        nodes = [(n.x, n.y) for c in en.shapes[0].contours for n in c.nodes()]
        self.assertEqual(sorted(nodes), sorted([(50, 250), (478, 250), (478, 310), (50, 310)]), "stretched outlines")
        self.assertIn(("done", u"Built 2 glyphs:   –. <i>Edit &gt; Undo</i> takes it back."), logged)
        self.assertTrue(any(u"Added 1 code point to a glyph the font has already, no new glyph: Ω on Omega" in text
                            for _, text in logged), logged)

    def test_a_glyph_of_the_list_is_built_first_and_never_without_it(self):
        page, package, steps, logged = self.page()
        self.build(page, [0x201C, 0x2018])
        double = package.findName("quotedblleft").getLayerByName("Regular")
        self.assertEqual([s.shapeData.componentGlyph for s in double.shapes], ["quoteleft", "quoteleft"],
                         "the single quotes built just before")
        single = package.findName("quoteleft").getLayerByName("Regular").shapes
        self.assertEqual([(s.shapeData.componentGlyph, s.transform.values[:4]) for s in single],
                         [("quoteright", (-1.0, 0.0, -0.0, -1.0))], "a turned component, no mirror")
        page, package, steps, logged = self.page()
        self.build(page, [0x201C])
        self.assertIsNone(package.findName("quotedblleft"))
        self.assertTrue(any(u"it needs quoteleft, which was not built: check it too" in text for _, text in logged))

    def test_mirrors_are_set_right(self):
        page, package, steps, logged = self.page()
        self.build(page, [0x203A, 0x204F])
        self.assertEqual(page.cm.mirrored, [("guilsinglleft", "guilsinglright")], "outlines mirrored into the glyph")
        self.assertEqual(package.findName("guilsinglright").fgGlyph.unicodes, [0x203A])
        reversed_semicolon = package.findName("uni204F") or package.findName("reversedsemicolon")
        names = [s.shapeData.componentGlyph for s in reversed_semicolon.getLayerByName("Regular").shapes]
        self.assertEqual(sorted(names), ["comma.mirrored", "period.mirrored"], "each part's corrected glyph")

    def test_a_glyph_that_fails_leaves_the_others_and_nothing_behind(self):
        page, package, steps, logged = self.page()
        page.cm.source_mirror = lambda ak, package_, master, name, axis: None if name == "period" else (-1.0, 1.0, 250.0, 0.0)
        self.build(page, [0x204F, 0x2013])
        self.assertIsNotNone(package.findName("endash"), "the other glyph built")
        self.assertIsNone(package.findName("reversedsemicolon") or package.findName("uni204F"), "the failed one taken out")
        self.assertIsNone(package.findName("comma.mirrored"), "the corrected glyph made for it taken out too")
        self.assertTrue(any(u"was not built: period has no outline in master Regular" in text for _, text in logged), logged)

    def test_an_error_after_the_glyphs_still_records_the_step(self):
        page, package, steps, logged = self.page()
        saved = gg.unused_helpers
        try:
            gg.unused_helpers = lambda *args: 1 / 0
            self.build(page, [0x2013])
        finally:
            gg.unused_helpers = saved
        self.assertEqual([s[0] for s in steps], ["begin", u"FreeLab Glyph Compose", "end"], "recorded, the write ended")
        self.assertTrue(any(kind == "error" for kind, _ in logged))

    def test_a_layer_fontlab_did_not_keep_is_put_back(self):
        glyph = Glyph("minus", {"Regular": Layer([Shape([Contour(rect(0, 0, 10, 10))])], 400)})
        refuse, saved = Layer.setGlyphComponents, gg._qt
        try:
            gg._qt = lambda: (None, Stub(QTransform=Transform))
            Layer.setGlyphComponents = lambda self, *args: None  # (FontLab keeping nothing)
            kept = gg.write_layer(Stub(GlyphComponent=Component), None, None, Cm(), package_of(FakeFont()), "Regular",
                                  ["Regular"], glyph, gg.Layout([gg.Part("hyphen")], 500), None)
        finally:
            Layer.setGlyphComponents, gg._qt = refuse, saved
        layer = glyph.getLayerByName("Regular")
        self.assertFalse(kept)
        self.assertEqual((len(layer.shapes), layer.advanceWidth), (1, 400), "its own outline and advance back")
        fresh = Glyph("minus")
        try:
            gg._qt = lambda: (None, Stub(QTransform=Transform))
            Layer.setGlyphComponents = lambda self, *args: None
            gg.write_layer(Stub(GlyphComponent=Component), None, None, Cm(), package_of(FakeFont()), "Regular",
                           ["Regular"], fresh, gg.Layout([gg.Part("hyphen")], 500), None)
        finally:
            Layer.setGlyphComponents, gg._qt = refuse, saved
        self.assertIsNone(fresh.getLayerByName("Regular"), "a layer made for a write that did not hold is taken out")

    def test_a_sparse_master_gets_no_layer(self):
        """Rubik's Bold has no layer for many glyphs (live 2026-11-16): a glyph made of them gets none there
        either, never an empty one, and the log says so once per master."""
        bold = FakeFont()
        bold.has_layer = lambda name: name not in ("hyphen", "period")
        page, package, steps, logged = self.page(masters=("Light", "Bold"))
        page.font_in = lambda package_, master: bold if master == "Bold" else page.font
        for name in ("hyphen", "period"):
            del package.findName(name).layers_by["Bold"]
        self.build(page, [0x2010, 0x2025, 0x2002])
        for name in ("hyphentwo", "twodotenleader"):
            glyph = package.findName(name)
            self.assertIsNotNone(glyph.getLayerByName("Light"), name)
            self.assertIsNone(glyph.getLayerByName("Bold"), "%s: no layer made where its source has none" % name)
        self.assertIsNotNone(package.findName("enspace").getLayerByName("Bold"), "a width by rule: every master")
        self.assertIn(("info", u"In master Bold, 2 glyphs have no layer, as their sources have none there (a variable "
                               u"font's sparse master): ‐ ‥."), logged)

    def test_every_master(self):
        page, package, steps, logged = self.page(masters=("Light", "Bold"))
        self.build(page, [0x2212])
        minus = package.findName("minus")
        for master in ("Light", "Bold"):
            layer = minus.getLayerByName(master)
            self.assertEqual(layer.advanceWidth, 500.0)
            xs = sorted(set(n.x for c in layer.shapes[0].contours for n in c.nodes()))
            self.assertEqual(xs, [60, 440], master)

    def rebuilding(self, glyphs, masters=("Regular",)):
        """A page that lists the font's own glyphs too (Also list existing glyphs checked)."""
        font = FakeFont(glyphs)
        page, package, steps, logged = self.page(font, masters)
        page.existing_box = Stub(checked=True)
        page.planner_now = gg.Planner(DATA, font, None, True)
        page.rows = page.planner_now.plan()
        calls = []
        refuse = Layer.setGlyphComponents

        def spy(layer, components, width, package_, flag):
            calls.append([c._glyph for c in components])
            refuse(layer, components, width, package_, flag)
        Layer.setGlyphComponents = spy
        self.addCleanup(setattr, Layer, "setGlyphComponents", refuse)
        return page, package, steps, logged, calls

    def graph_loops(self, package, masters=("Regular",)):
        return [name for name in package.glyphs
                if gg.component_loop(name, sorted(gg.glyph_components(package, masters, name)),
                                     lambda g: gg.glyph_components(package, masters, g))]

    def test_eth_and_dcroat_never_make_a_loop_of_components(self):
        # Codex's review: Ð and Đ are each a copy of the other; rebuilt together, Ð of Đ then Đ of Ð
        eth = dict(BARE, Eth=(0x00D0, 680, [rect(80, 0, 600, 700)], None),
                   Dcroat=(0x0110, 680, [rect(80, 0, 600, 700)], None))
        page, package, steps, logged, calls = self.rebuilding(eth)
        rows = dict((r.hex, r) for r in page.rows)
        self.assertEqual(([p.name for p in rows["00D0"].layout.parts], [p.name for p in rows["0110"].layout.parts]),
                         (["Dcroat"], ["Eth"]), "each alone is a copy of the other")
        self.build(page, [0x00D0, 0x0110])
        self.assertEqual(calls, [["Dcroat"]], "the first rebuilt; setGlyphComponents never handed the loop")
        self.assertEqual(self.graph_loops(package), [], "no glyph made of itself")
        dcroat = package.findName("Dcroat").getLayerByName("Regular").shapes
        self.assertEqual([s.isComponent for s in dcroat], [False], "Đ left as it was: its own outline")
        self.assertIn(("warning", u"Đ was not built: it would be made of Eth, which is made of Dcroat, a loop of "
                                  u"components: left as it was."), logged)
        # Đ already a copy of Ð: Ð's row says why it cannot be rebuilt
        made_of = dict(BARE, Eth=(0x00D0, 680, [rect(80, 0, 600, 700)], None),
                       Dcroat=(0x0110, 680, None, [("Eth", (1, 0, 0, 1, 0, 0))]))
        page, package, steps, logged, calls = self.rebuilding(made_of)
        rows = dict((r.hex, r) for r in page.rows)
        self.assertIsNone(rows["00D0"].layout)
        self.assertEqual(gg.note_text(rows["00D0"]), u"made of Dcroat, which is made of Eth")

    def test_a_loop_through_another_master_is_refused_before_any_write(self):
        # The current master plans Ð of Đ, but in Bold Đ is made of Ð already: nothing is written
        eth = dict(BARE, Eth=(0x00D0, 680, [rect(80, 0, 600, 700)], None),
                   Dcroat=(0x0110, 680, [rect(80, 0, 600, 700)], None))
        page, package, steps, logged, calls = self.rebuilding(eth, ("Regular", "Bold"))
        package.findName("Dcroat").layers_by["Bold"] = Layer([Shape(component="Eth")], 680)
        self.build(page, [0x00D0])
        self.assertEqual(calls, [], "never called on a loop")
        self.assertEqual([s.isComponent for s in package.findName("Eth").getLayerByName("Bold").shapes], [False])
        self.assertEqual(self.graph_loops(package, ("Regular", "Bold")), [])
        self.assertTrue(any(u"Ð was not built: it would be made of Dcroat, which is made of Eth" in text
                            for _, text in logged), logged)

    def test_a_rebuild_that_fails_in_one_master_is_put_back_in_every_master(self):
        # Codex's review: Regular rebuilt, Bold's write raised; Regular stayed rebuilt while the log said
        # "Built none"
        ohm = dict(BARE, Ohm=(0x2126, 740, [rect(40, 0, 700, 710)], None))
        page, package, steps, logged, calls = self.rebuilding(ohm, ("Regular", "Bold"))
        saved = gg.write_parts

        def failing(fontlab, ak, fc, cm, package_, master, layer, layout, corrected, own=None):
            if master == "Bold":
                raise gg.WriteError(u"Bold refused")
            return saved(fontlab, ak, fc, cm, package_, master, layer, layout, corrected, own)
        gg.write_parts = failing
        self.addCleanup(setattr, gg, "write_parts", saved)
        self.build(page, [0x2126])
        for master in ("Regular", "Bold"):
            layer = package.findName("Ohm").getLayerByName(master)
            self.assertEqual(([s.isComponent for s in layer.shapes], layer.advanceWidth), ([False], 740.0), master)
        self.assertIn(("warning", u"%s was not built: Bold refused; every master left as it was." % u(0x2126)), logged)
        self.assertIn(("info", u"Built none."), logged)
        # put back where it can be; where it cannot, the log names the master that changed
        page, package, steps, logged, calls = self.rebuilding(ohm, ("Regular", "Bold"))
        regular = package.findName("Ohm").getLayerByName("Regular")
        put_back = gg.put_back

        def stuck(layer, shapes, width):
            if layer is regular:
                raise RuntimeError("FontLab refused")
            put_back(layer, shapes, width)
        gg.put_back = stuck
        self.addCleanup(setattr, gg, "put_back", put_back)
        self.build(page, [0x2126])
        self.assertIn(("warning", u(0x2126) + u" was not built: Bold refused; it was changed all the same in master Regular, which "
                                  u"could not be put back (the other masters are as they were): Edit > Undo takes it "
                                  u"back."), logged)
        self.assertIn(package.findName("Ohm"), steps[1][1], "recorded: Undo takes it back")

    def test_a_character_handed_over_is_built_with_what_it_is_made_of(self):
        # Codex's review: ‟ handed over alone, the font lacking ‛ too
        page, package, steps, logged = self.page()
        page.planner_now = gg.Planner(DATA, page.font, None, False, set(["201F"]))
        page.rows = page.planner_now.plan()
        self.build(page, [0x201F])
        double = package.findName("quotedblrightreversed")
        self.assertIsNotNone(double, logged)
        self.assertEqual([s.shapeData.componentGlyph for s in double.getLayerByName("Regular").shapes],
                         ["quotereversed", "quotereversed"])
        self.assertEqual(package.findName("quotereversed").fgGlyph.unicodes, [0x201B])
        self.assertIn(("done", u"‛ was built too, though not listed: ‟ is made of it."), logged)

    YA = {"Ya-cy": (0x042F, 700, [rect(40, 0, 660, 700)], None)}
    MIRROR = (-1, 0, 0, 1, 700, 0)

    def test_two_mirrors_never_cancel_into_a_glyph_made_of_itself(self):
        # Codex's review, round 2: R made as a mirrored component of Я, Я rebuilt as the mirrored R; flattened,
        # the two mirrors cancel, and Я became a component of itself
        glyphs = dict(BARE, R=(0x0052, 700, None, [("Ya-cy", self.MIRROR)]), **self.YA)
        page, package, steps, logged, calls = self.rebuilding(glyphs)
        row = dict((r.hex, r) for r in page.rows)["042F"]
        self.assertIsNone(row.layout)
        self.assertEqual(gg.note_text(row), u"made of R, which is made of Ya-cy")
        self.build(page, [0x042F])
        self.assertFalse(any("Ya-cy" in names for names in calls), calls)
        self.assertEqual(self.graph_loops(package), [])
        # through a glyph between them: R of Rmid mirrored, Rmid of Я mirrored
        chain = dict(BARE, R=(0x0052, 700, None, [("Rmid", self.MIRROR)]), Rmid=(None, 700, None, [("Ya-cy", self.MIRROR)]),
                     **self.YA)
        page, package, steps, logged, calls = self.rebuilding(chain)
        row = dict((r.hex, r) for r in page.rows)["042F"]
        self.assertEqual(gg.note_text(row), u"made of R, which is in the end made of Ya-cy")
        self.build(page, [0x042F])
        self.assertEqual(calls, [])

    def test_the_parts_as_written_are_checked_before_the_layer_is_cleared(self):
        # (the plan read another master, or the font changed since: the write itself refuses)
        glyphs = dict(BARE, R=(0x0052, 700, None, [("Ya-cy", self.MIRROR)]), **self.YA)
        package = package_of(FakeFont(glyphs))
        ya = package.findName("Ya-cy")
        calls, refuse, saved = [], Layer.setGlyphComponents, gg._qt
        try:
            gg._qt = lambda: (None, Stub(QTransform=Transform))
            Layer.setGlyphComponents = lambda layer, components, *args: calls.append([c._glyph for c in components])
            with self.assertRaises(gg.WriteError) as caught:
                gg.write_layer(Stub(GlyphComponent=Component), None, None, Cm(), package, "Regular", ["Regular"], ya,
                               gg.Layout([gg.Part("R", gg.mirror_x(700))], 700), None)
        finally:
            Layer.setGlyphComponents, gg._qt = refuse, saved
        self.assertEqual(calls, [], "FontLab never handed the loop")
        self.assertIn(u"made of its own glyph", u"%s" % caught.exception, "R's mirror and Я's cancel: Я itself")
        self.assertEqual([s.isComponent for s in ya.getLayerByName("Regular").shapes], [False], "its outline kept")

    def test_a_normal_mirror_still_builds(self):
        glyphs = dict(BARE, R=(0x0052, 640, [rect(90, 0, 590, 700)], None))
        page, package, steps, logged = self.page(FakeFont(glyphs))
        self.build(page, [0x042F])
        ya = package.findUnicode(0x042F)
        self.assertIsNotNone(ya, logged)
        self.assertEqual(page.cm.mirrored, [("R", ya.name)], "R's outlines mirrored into it, contours set right")

    def failing_after_writing(self, master, restores_failing):
        """write_parts that writes, then changes the width and raises in master; put_back that fails its first
        restores_failing tries in that master's layer."""
        real_write, real_restore, tries = gg.write_parts, gg.put_back, []

        def write(fontlab, ak, fc, cm, package_, master_, layer, layout, corrected, own=None):
            result = real_write(fontlab, ak, fc, cm, package_, master_, layer, layout, corrected, own)
            if master_ == master:
                layer.advanceWidth = 999
                raise gg.WriteError(u"%s failed after its write" % master)
            return result

        def restore(layer, shapes, width):
            if getattr(layer, "master", None) == master:
                tries.append(master)
                if len(tries) <= restores_failing:
                    layer.removeAllShapes()
                    raise RuntimeError(u"no put-back")
            return real_restore(layer, shapes, width)
        gg.write_parts, gg.put_back = write, restore
        self.addCleanup(setattr, gg, "write_parts", real_write)
        self.addCleanup(setattr, gg, "put_back", real_restore)
        return tries

    def test_a_master_whose_own_put_back_failed_is_put_back_from_what_was_saved(self):
        # Codex's review, round 2: Bold changed, raised, and its own put-back failed: Bold was never put back
        # and the log said every master was; failing first, nothing was put back at all
        ohm = dict(BARE, Ohm=(0x2126, 740, [rect(40, 0, 700, 710)], None))
        for failing in ("Bold", "Regular"):
            page, package, steps, logged, calls = self.rebuilding(ohm, ("Regular", "Bold"))
            for master in ("Regular", "Bold"):
                package.findName("Ohm").getLayerByName(master).master = master
            tries = self.failing_after_writing(failing, 1)
            self.build(page, [0x2126])
            self.assertEqual(tries, [failing, failing], "its own put-back, then the build's from what was saved")
            for master in ("Regular", "Bold"):
                layer = package.findName("Ohm").getLayerByName(master)
                self.assertEqual(([s.isComponent for s in layer.shapes], layer.advanceWidth), ([False], 740.0),
                                 (failing, master))
            self.assertIn(("warning", u"%s was not built: %s failed after its write; putting master %s back failed at "
                                      u"first (no put-back); every master left as it was." % (u(0x2126), failing, failing)),
                          logged)

    def test_a_master_that_cannot_be_put_back_is_named(self):
        ohm = dict(BARE, Ohm=(0x2126, 740, [rect(40, 0, 700, 710)], None))
        page, package, steps, logged, calls = self.rebuilding(ohm, ("Regular", "Bold"))
        for master in ("Regular", "Bold"):
            package.findName("Ohm").getLayerByName(master).master = master
        self.failing_after_writing("Bold", 2)
        self.build(page, [0x2126])
        self.assertIn(("warning", u"%s was not built: Bold failed after its write; putting master Bold back failed at "
                                  u"first (no put-back); it was changed all the same in master Bold, which could not be "
                                  u"put back (the other masters are as they were): Edit > Undo takes it back." % u(0x2126)),
                      logged)
        regular = package.findName("Ohm").getLayerByName("Regular")
        self.assertEqual([s.isComponent for s in regular.shapes], [False], "Regular put back, read back")
        self.assertIn(package.findName("Ohm"), steps[1][1], "recorded: Undo takes it back")

    def test_a_draft_a_glyph_is_made_of_is_built_only_once_checked(self):
        # Codex's review, round 2: ǝ (U+01DD) copies ə (U+0259), a turned e: a draft. The whole table lists ə
        # unchecked and builds ǝ only with it checked; handed over alone, ǝ built the draft unasked
        font = FakeFont(dict(BARE, e=(0x65, 500, [rect(40, 0, 460, 500)], None)))
        for codes in (None, set(["01DD"])):
            page, package, steps, logged = self.page(font)
            page.planner_now = gg.Planner(DATA, font, None, False, codes)
            page.rows = page.planner_now.plan()
            rows = dict((r.hex, r) for r in page.rows)
            self.assertIn("0259", rows, "ə listed: the owner sees the draft")
            self.assertEqual(rows["0259"].confidence, u"starting point")
            self.assertEqual(page.planner_now.prerequisites([rows["01DD"]]), [], "never a hidden draft")
            self.build(page, [0x01DD])
            self.assertIsNone(package.findUnicode(0x0259), codes)
            self.assertIsNone(package.findUnicode(0x01DD), codes)
            self.assertIn(("warning", u"%s was not built: it needs schwa, which was not built: check it too." % u(0x01DD)),
                          logged)
            page, package, steps, logged = self.page(font)
            page.planner_now = gg.Planner(DATA, font, None, False, codes)
            page.rows = page.planner_now.plan()
            self.build(page, [0x01DD, 0x0259])
            self.assertIsNotNone(package.findUnicode(0x01DD), "checked both: both built")
            self.assertIsNotNone(package.findUnicode(0x0259))
        handed = gg.Planner(DATA, font, None, False, set(["01DD"]))
        self.assertEqual(sorted(r.hex for r in handed.plan()), ["01DD", "0259"], "nothing else listed")

    def test_a_prerequisite_whose_glyphs_were_not_built_is_taken_out(self):
        # Codex's review, round 2: ‛ built, ‟ failed: the log said "the glyphs listed are made of it"
        real = gg.write_parts
        self.addCleanup(setattr, gg, "write_parts", real)

        def handed(write_fails, delete_fails=False):
            page, package, steps, logged = self.page()
            page.planner_now = gg.Planner(DATA, page.font, None, False, set(["201F"]))
            page.rows = page.planner_now.plan()

            def write(fontlab, ak, fc, cm, package_, master, layer, layout, corrected, own=None):
                if write_fails and any(part.name == "quotereversed" for part in layout.parts):
                    raise gg.WriteError(u"refused")
                return real(fontlab, ak, fc, cm, package_, master, layer, layout, corrected, own)
            gg.write_parts = write
            if delete_fails:
                package.deleteGlyph = lambda glyph: None
            self.build(page, [0x201F])
            return package, logged
        package, logged = handed(True)
        self.assertIsNone(package.findUnicode(0x201F))
        self.assertIsNone(package.findName("quotereversed"), "‛ taken out with the glyph it was built for")
        self.assertIn(("info", u"‛ was built for ‟, which was not built: it was taken out again."), logged)
        self.assertFalse(any(u"made of it" in text or u"Built" in text and u"‛" in text for _, text in logged), logged)
        package, logged = handed(True, delete_fails=True)
        self.assertIsNotNone(package.findName("quotereversed"))
        self.assertIn(("warning", u"‛ was built for ‟, which was not built: FontLab did not take it out again, so it stays "
                                  u"in the font (Edit > Undo takes it back)."), logged)
        package, logged = handed(False)
        self.assertIn(("done", u"‛ was built too, though not listed: ‟ is made of it."), logged)

    # -- Codex's review, round 3 ---------------------------------------------------------------------------

    def geometry(self, layer):
        return (layer.advanceWidth, [(s.isComponent, s.shapeData.componentGlyph, s.transform.values,
                                      [[(n.x, n.y, n.type) for n in c.nodes()] for c in s.contours]) for s in layer.shapes])

    def test_an_unreadable_component_graph_is_never_taken_for_none(self):
        def unreadable(*args):
            raise RuntimeError(u"component graph unreadable")
        # the write itself: Đ made of Ð, but Đ cannot be read; Ð would be made of Đ
        glyphs = dict(BARE, Eth=(0x00D0, 680, [rect(80, 0, 600, 700)], None), Dcroat=(0x0110, 680, None, [("Eth", gg.IDENTITY)]))
        package = package_of(FakeFont(glyphs))
        eth = package.findName("Eth")
        before = self.geometry(eth.getLayerByName("Regular"))
        package.findName("Dcroat").getLayerByName = unreadable
        calls, refuse, saved = [], Layer.setGlyphComponents, gg._qt
        try:
            gg._qt = lambda: (None, Stub(QTransform=Transform))
            Layer.setGlyphComponents = lambda layer, components, *args: calls.append([c._glyph for c in components])
            with self.assertRaises(gg.WriteError) as caught:
                gg.write_layer(Stub(GlyphComponent=Component), None, None, Cm(), package, "Regular", ["Regular"], eth,
                               gg.Layout([gg.Part("Dcroat")], 680), None)
        finally:
            Layer.setGlyphComponents, gg._qt = refuse, saved
        self.assertEqual(calls, [], "an unreadable graph is not an empty one")
        self.assertEqual(self.geometry(eth.getLayerByName("Regular")), before)
        self.assertEqual(u"%s" % caught.exception, u"the components of Dcroat could not be read in master Regular, so it "
                                                      u"cannot be told whether it would be made of itself")
        # the check before any write: planned while Đ read as outlines, built once it cannot be read
        eth_dcroat = dict(BARE, Eth=(0x00D0, 680, [rect(80, 0, 600, 700)], None),
                          Dcroat=(0x0110, 680, [rect(80, 0, 600, 700)], None))
        page, package, steps, logged, calls = self.rebuilding(eth_dcroat)
        package.findName("Dcroat").getLayerByName = unreadable
        self.build(page, [0x00D0])
        self.assertEqual(calls, [])
        self.assertIn(("warning", u"Ð was not built: the components of Dcroat could not be read in master Regular, so it "
                                  u"cannot be told whether it would be made of itself: left as it was."), logged)
        # planning: the row says so
        font = FakeFont(eth_dcroat)
        own = font.components

        def components(name):
            if name == "Dcroat":
                raise gg.GraphUnreadable(name, "Regular")
            return own(name)
        font.components = components
        rows = dict((r.hex, r) for r in gg.Planner(DATA, font, None, True).plan())
        self.assertIsNone(rows["00D0"].layout)
        self.assertEqual(gg.note_text(rows["00D0"]), u"the components of Dcroat could not be read in master Regular")

    def test_a_master_fontlab_did_not_keep_puts_the_glyph_back_whole(self):
        # Codex's review, round 3: Bold kept none of its parts (no error): Regular stayed rebuilt, Bold not
        ohm = dict(BARE, Ohm=(0x2126, 740, [rect(30, 0, 690, 700)], None))
        original = Layer.setGlyphComponents
        for rejecting in ("Bold", "Regular"):
            Layer.setGlyphComponents = original  # (each round its own spy, not the last round's)
            page, package, steps, logged, calls = self.rebuilding(ohm, ("Regular", "Bold"))
            glyph = package.findName("Ohm")
            before = dict((m, self.geometry(glyph.getLayerByName(m))) for m in package.masters)
            target, spy = glyph.getLayerByName(rejecting), Layer.setGlyphComponents

            def keep_none(layer, components, width, package_, flag):
                if layer is target:
                    layer.advanceWidth = width
                    return  # (FontLab keeps none of the components asked)
                return spy(layer, components, width, package_, flag)
            Layer.setGlyphComponents = keep_none
            self.build(page, [0x2126])
            self.assertEqual(dict((m, self.geometry(glyph.getLayerByName(m))) for m in package.masters), before, rejecting)
            self.assertFalse(any(u"Rebuilt" in text for _, text in logged), logged)
            self.assertIn(("warning", u"%s was not built: FontLab did not keep its parts in master %s; every master left as "
                                      u"it was." % (u(0x2126), rejecting)), logged)

    def test_a_put_back_is_read_back_whole(self):
        # Codex's review, round 3: only node counts were compared: another drawing of as many nodes read as restored
        layer = Layer([Shape([Contour(rect(0, 0, 100, 100))])], 500)
        glyph = Glyph("emdash", {"Regular": layer})
        saved = gg.glyph_layers(Cm(), glyph, ["Regular"])
        self.assertTrue(gg.layer_as_saved(glyph, "Regular", saved["Regular"]))
        layer.shapes = [Shape([Contour(rect(80, 50, 180, 150))])]
        self.assertFalse(gg.layer_as_saved(glyph, "Regular", saved["Regular"]), "moved: not as it was")
        layer.shapes = [Shape([Contour(rect(0, 0, 100, 100))], transform=Transform(1, 0, 0, 1, 5, 0))]
        self.assertFalse(gg.layer_as_saved(glyph, "Regular", saved["Regular"]), "its shape moved")
        turned = Contour(rect(0, 0, 100, 100))
        turned._nodes[1].type = u"off"
        layer.shapes = [Shape([turned])]
        self.assertFalse(gg.layer_as_saved(glyph, "Regular", saved["Regular"]), "a node of another kind")
        layer.shapes = [Shape([Contour(rect(0, 0, 100, 100)[:2]), Contour(rect(0, 0, 100, 100)[2:])])]
        self.assertFalse(gg.layer_as_saved(glyph, "Regular", saved["Regular"]), "the same nodes in two contours")
        # a rebuild that leaves another outline of as many nodes behind names its master
        ohm = dict(BARE, Ohm=(0x2126, 740, [rect(40, 0, 700, 710)], None))
        page, package, steps, logged, calls = self.rebuilding(ohm, ("Regular", "Bold"))
        bold = package.findName("Ohm").getLayerByName("Bold")
        real_write, real_restore = gg.write_parts, gg.put_back

        def write(fontlab, ak, fc, cm, package_, master, layer_, layout, corrected, own=None):
            result = real_write(fontlab, ak, fc, cm, package_, master, layer_, layout, corrected, own)
            if layer_ is bold:
                layer_.shapes = [Shape([Contour(rect(90, 10, 600, 690))])]  # (4 nodes, its own advance)
                layer_.advanceWidth = 740
                raise gg.WriteError(u"Bold failed after its write")
            return result

        def restore(layer_, shapes, width):
            if layer_ is bold:
                raise RuntimeError(u"no put-back")
            return real_restore(layer_, shapes, width)
        gg.write_parts, gg.put_back = write, restore
        self.addCleanup(setattr, gg, "write_parts", real_write)
        self.addCleanup(setattr, gg, "put_back", real_restore)
        self.build(page, [0x2126])
        self.assertFalse(any(u"every master left as it was" in text for _, text in logged), logged)
        self.assertTrue(any(u"it was changed all the same in master Bold, which could not be put back" in text
                            for _, text in logged), logged)

    def test_a_prerequisite_a_glyph_left_in_the_font_is_made_of_stays(self):
        # Codex's review, round 3: ‟ written, its code point refused: ‟ stayed, made of ‛, and ‛ was taken out
        page, package, steps, logged = self.page()
        page.planner_now = gg.Planner(DATA, page.font, None, False, set(["201F"]))
        page.rows = page.planner_now.plan()
        add = package.addGlyph

        class Refusing(FgGlyph):
            @property
            def unicode(self):
                return self.unicodes[0] if self.unicodes else None

            @unicode.setter
            def unicode(self, code):
                raise RuntimeError(u"code point refused")

        def adding(new):
            add(new)
            if new.name == "quotedblrightreversed":
                package.findName(new.name).fgGlyph = Refusing([])
        package.addGlyph = adding
        self.build(page, [0x201F])
        target = package.findName("quotedblrightreversed")
        self.assertEqual(sorted(gg.glyph_components(package, ["Regular"], target.name)), ["quotereversed"])
        self.assertIsNotNone(package.findName("quotereversed"), "what ‟ is made of stays")
        self.assertIn(("warning", u"‛ was built for ‟, which was not built: a glyph left in the font is made of it, so "
                                  u"it stays (Edit > Undo takes it back)."), logged)
        self.assertFalse(any(u"built too" in text for _, text in logged), logged)

    def test_a_prerequisite_left_in_the_font_keeps_what_it_is_made_of(self):
        # (one FontLab did not take out: the glyph it is made of stays too, never deleted under it)
        glyphs = dict(BARE, inner=(None, 300, [rect(0, 0, 10, 10)], None), outer=(None, 300, None, [("inner", gg.IDENTITY)]))
        package = package_of(FakeFont(glyphs))
        page = gg.GenerationPage.__new__(gg.GenerationPage)
        inner, outer = Stub(name="inner", char=u"i", needs=[]), Stub(name="outer", char=u"o", needs=["inner"])
        target = Stub(name="target", char=u"t", needs=["outer"])
        page.planner_now = Stub(by_name={"inner": inner, "outer": outer})
        deleted = []
        package.deleteGlyph = lambda glyph: deleted.append(glyph.name)  # (FontLab takes nothing out)
        made, built, touched = [u"i", u"o"], set(["inner", "outer"]), []
        orphans, left = page.drop_orphans(package, ["Regular"], [outer, inner], [target], made, built, touched)
        self.assertEqual(orphans, [])
        self.assertEqual(sorted((r.name, why) for r, why in left), [("inner", "used"), ("outer", "stuck")])
        self.assertEqual(deleted, ["outer"], "inner never asked out: outer, still in the font, is made of it")

    def test_a_prerequisite_left_in_the_font_is_never_said_to_be_used(self):
        # Codex's review, round 3: FontLab did not take ‛ out: the log still said "are made of it", of no glyph
        real = gg.write_parts
        self.addCleanup(setattr, gg, "write_parts", real)

        def handed(codes, failing, delete_fails=False):
            page, package, steps, logged = self.page()
            page.planner_now = gg.Planner(DATA, page.font, None, False, set(codes))
            page.rows = page.planner_now.plan()

            def write(fontlab, ak, fc, cm, package_, master, layer, layout, corrected, own=None):
                if failing and any(part.name == "quotereversed" for part in layout.parts):
                    raise gg.WriteError(u"refused")
                return real(fontlab, ak, fc, cm, package_, master, layer, layout, corrected, own)
            gg.write_parts = write
            if delete_fails:
                package.deleteGlyph = lambda glyph: None
            self.build(page, [int(code, 16) for code in codes])
            return logged
        logged = handed(["201F"], True, delete_fails=True)  # 0 glyphs built of it
        self.assertFalse(any(u"made of it" in text for _, text in logged), logged)
        self.assertIn(("warning", u"‛ was built for ‟, which was not built: FontLab did not take it out again, so it stays "
                                  u"in the font (Edit > Undo takes it back)."), logged)
        logged = handed(["201F"], False)  # 1
        self.assertIn(("done", u"‛ was built too, though not listed: ‟ is made of it."), logged)
        logged = handed(["201F", "02BD"], False)  # 2
        self.assertIn(("done", u"‛ was built too, though not listed: ʽ ‟ are made of it."), logged)
        logged = handed(["201F", "02BD"], True, delete_fails=True)  # 0 of 2
        self.assertFalse(any(u"made of it" in text for _, text in logged), logged)
        self.assertIn(("warning", u"‛ was built for ʽ ‟, which were not built: FontLab did not take it out again, so it "
                                  u"stays in the font (Edit > Undo takes it back)."), logged)

    def test_python_made_glyphs_are_held(self):
        sys.modules.pop("freelab_glyph_compose", None)
        import freelab_glyph_compose as cm
        made = Stub(name=None)
        fontlab = Stub(flGlyph=lambda: made)
        package = Stub(fgPackage=Stub(id=99))
        try:
            self.assertIs(cm.new_glyph(fontlab, package, u"endash"), made)
            self.assertEqual(made.name, u"endash")
            self.assertIn(made, getattr(sys, cm.HELD_GLYPHS)[99], "held for the session")
        finally:
            getattr(sys, cm.HELD_GLYPHS, {}).pop(99, None)


if __name__ == "__main__":
    unittest.main()
