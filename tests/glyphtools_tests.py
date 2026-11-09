"""Tests of FreeLab's accented glyphs (planning and placing marks) and feature code (ligatures and
alternates that take turns). Valid Python 2.7 and Python 3; the feature parser's checks run where
fontTools is installed."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "diacritics"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_accents as ac  # noqa: E402
import freelab_feature_code as fc  # noqa: E402

try:
    import fontTools.feaLib.parser  # noqa: F401
    HAVE_FONTTOOLS = True
except Exception:
    HAVE_FONTTOOLS = False

A_CARON, I_CARON, CAP_A_CARON = ac.unichr_(0x01CE), ac.unichr_(0x01D0), ac.unichr_(0x01CD)
A_DOT_BELOW, O_CIRCUMFLEX_ACUTE, O_HORN_DOT = ac.unichr_(0x1EA1), ac.unichr_(0x1ED1), ac.unichr_(0x1EE3)


def font():
    return ac.Font(["a", "acaron", "i", "dotlessi", "caron", "acute", "caron.case", "A", "dotaccent", "I", "o",
                    "circumflex", "e"],
                   [("a", 0x61), ("i", 0x69), ("dotlessi", 0x131), ("A", 0x41), ("I", 0x49), ("o", 0x6F), ("e", 0x65)])


class PlanTests(unittest.TestCase):
    def test_recipes(self):
        found = dict((r.char, r) for r in ac.plan(font(), [A_CARON, I_CARON, CAP_A_CARON, A_DOT_BELOW,
                                                          O_CIRCUMFLEX_ACUTE, O_HORN_DOT, u"a"]))
        self.assertNotIn(u"a", found, "a character the font has")
        self.assertEqual(found[A_CARON].name, u"uni01CE", "acaron is another glyph's name already")
        self.assertEqual(found[I_CARON].base, "dotlessi", "a mark above takes the dotless i")
        self.assertEqual(found[I_CARON].name, u"icaron", "named after the letter, not its dotless form")
        self.assertEqual(found[CAP_A_CARON].marks[0][0], "caron.case", "a capital takes the .case mark")
        self.assertEqual(found[A_DOT_BELOW].marks[0][:2], ("dotaccent", "below"))
        self.assertEqual(found[A_DOT_BELOW].marks[0][3], "dotbelow", "borrowed from its twin above")
        self.assertEqual([m[0] for m in found[O_CIRCUMFLEX_ACUTE].marks], ["circumflex", "acute"])
        self.assertTrue(found[O_HORN_DOT].missing and u"horn" in found[O_HORN_DOT].missing)


class RefillTests(unittest.TestCase):
    def test_an_empty_glyph_is_planned_again_under_its_name(self):
        f = ac.Font(["a", "caron", "acaron"], [("a", 0x61), ("acaron", 0x01CE)], empty=["acaron"])
        found = ac.plan(f, [A_CARON])
        self.assertEqual([(r.name, r.refill) for r in found], [("acaron", True)])
        full = ac.Font(["a", "caron", "acaron"], [("a", 0x61), ("acaron", 0x01CE)])
        self.assertEqual(ac.plan(full, [A_CARON]), [], "a drawn glyph is left alone")


class PlaceTests(unittest.TestCase):
    def test_marks_sit_as_the_fonts_own(self):
        inks = {"a": ac.Ink(10, 0, 350, 480, top_center=200, advance=367),
                "acute": ac.Ink(20, 510, 230, 590), "caron": ac.Ink(0, 500, 200, 580),
                "circumflex": ac.Ink(0, 500, 220, 580), "e": ac.Ink(4, 0, 314, 478, top_center=170, advance=312)}
        placement = ac.Placement(1000.0)
        # the font's aacute: the acute 20 units above a's ink, its center 18 units right of a's top center
        placement.learn([("a", [("acute", 93, -10)])], inks.get, lambda name: "lower")
        self.assertEqual(placement.where("acute", "above", "lower"), (20, 18))
        self.assertEqual(placement.where("caron", "above", "lower"), (20, 18), "unseen: the side's median")
        recipe = ac.Recipe(ac.unichr_(0x011B), u"ecaron", "e", [("caron", "above", "caron", None)])
        parts, width = ac.place(recipe, inks.get, placement)
        self.assertEqual(width, 312)
        self.assertEqual(parts[1], ("caron", 170 + 18 - 100, 478 + 20 - 500))
        stacked = ac.Recipe(O_CIRCUMFLEX_ACUTE, u"x", "e", [("circumflex", "above", "circumflex", None),
                                                           ("acute", "above", "acute", None)])
        parts, _ = ac.place(stacked, inks.get, placement)
        circumflex_top = 580 + parts[1][2]
        self.assertEqual(510 + parts[2][2] - circumflex_top, 20, "the acute stacked on the circumflex, the same gap")


class LearnableTests(unittest.TestCase):
    def test_only_composites_their_character_spells(self):
        self.assertTrue(ac.learnable(0xE9, [("e", 0, 0), ("acute", 66, -10)]))
        self.assertTrue(ac.learnable(0x122, [("G", 0, 0), ("commaaccentcomb", 113, -2)]))
        self.assertFalse(ac.learnable(0x13F, [("L", 0, 0), ("dotaccent", 168, -217)]), "a middle dot, not above")
        self.assertFalse(ac.learnable(0xBD, [("two", 0, 0), ("one", 9, 208), ("slash", 129, 143)]), "a fraction")
        self.assertFalse(ac.learnable(0x10F, [("d", 0, 0), ("quoteright", 366, 7)]), "a caron drawn as an apostrophe")
        self.assertFalse(ac.learnable(None, [("e", 0, 0), ("acute", 0, 0)]))

    def test_past_the_basic_plane(self):
        self.assertEqual(len(ac.unichr_(0x1F600)), 1)
        self.assertEqual(len(fc.unichr_(0x1F600)), 1)


class LigatureTests(unittest.TestCase):
    LIGA = u"\n".join([u"feature liga {", u"# Standard Ligatures", u"", u"#> feature",
                       u"  sub parenleft c parenright by copyright;", u"  sub f f by f_f;", u"  sub f f t by f_f_t;",
                       u"#< feature", u"} liga;", u""])
    NAMES = ["f", "t", "c", "l", "f_f", "f_f_t", "l_l.dlig", "parenleft", "parenright", "copyright"]

    def test_found_and_moved(self):
        found = fc.ligatures(self.NAMES, {"liga": self.LIGA})
        self.assertEqual([(l.glyph, l.now, l.choice) for l in found],
                         [("copyright", "liga", "liga"), ("f_f", "liga", "liga"), ("f_f_t", "liga", "liga"),
                          ("l_l.dlig", None, "dlig")])
        found[2].choice = "dlig"  # f_f_t: discretionary
        texts = fc.ligature_texts(found, {"liga": self.LIGA})
        self.assertIn(u"#/> feature", texts["liga"], "FontLab's automatic block handed back")
        self.assertNotIn(u"f_f_t", texts["liga"])
        self.assertIn(u"  sub f f t by f_f_t;", texts["dlig"])
        self.assertIn(u"  sub l l by l_l.dlig;", texts["dlig"])
        self.assertTrue(texts["dlig"].startswith(u"feature dlig {"), "a new feature")
        again = fc.ligature_texts(found, texts)
        self.assertEqual(again, texts, "writing twice changes nothing")
        if HAVE_FONTTOOLS:
            for tag in ("liga", "dlig"):
                self.assertIsNone(fc.check_code(texts[tag], self.NAMES))

    def test_longest_first(self):
        self.assertEqual(fc.rule_lines([(("f", "f"), "f_f"), (("f", "f", "t"), "f_f_t")]),
                         [u"sub f f t by f_f_t;", u"sub f f by f_f;"])


class AlternateTests(unittest.TestCase):
    def test_sets_by_suffix(self):
        names = ["l", "l.2", "i", "i.alt1", "i.alt2", "a.ss01", "a", "x.case", "x", "period", "period.2"]
        sets = fc.alternate_sets(names, lambda name: name in ("l", "i", "a", "x"))
        self.assertEqual(sets, {"l": ["l.2"], "i": ["i.alt1", "i.alt2"]}, "stylistic sets and other letters' forms left out")

    def test_alternates_with_a_job_are_found(self):
        texts = {"liga": u"feature liga {\n  sub I' space [a - z] by I.2;\n  # l.2 in a comment\n} liga;\n"}
        texts["aalt"] = u"feature aalt {\n  sub l from [l l.2];\n} aalt;\n"
        self.assertEqual(fc.used_in(["I.2", "l.2", "i.2"], texts), {"I.2": ["liga"]}, "aalt lists every alternate")

    def test_take_turns(self):
        letters = ["i", "i.2", "i.3", "n", "l"]
        code = fc.cycle_code({"i": ["i.2", "i.3"]}, letters, 1)
        self.assertIn(u"@FreeLab_gap_i = [l n];", code)
        self.assertIn(u"  sub i i' by i.2;", code)
        self.assertIn(u"  sub i.2 @FreeLab_gap_i i' by i.3;", code)
        self.assertFalse(any(u"i.3 i' by" in line for line in code), "after the last alternate, the letter itself")
        text = fc.calt_text(u"feature calt {\n  sub x' y by x.alt;\n} calt;\n", code)
        self.assertIn(u"  sub x' y by x.alt;", text, "the feature's own code kept")
        self.assertEqual(fc.calt_text(text, code), text, "writing twice changes nothing")
        if HAVE_FONTTOOLS:
            self.assertIsNone(fc.check_code(text, letters + ["x", "x.alt", "y"]))


if __name__ == "__main__":
    unittest.main()
