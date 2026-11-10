"""Tests of FreeLab's auto spacing: the suggestions and how composites follow. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "spacing"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
import freelab_auto_kerning as ak  # noqa: E402
import freelab_auto_spacing as sp  # noqa: E402


class ReferenceTests(unittest.TestCase):
    MODEL = {"references": {"H": {"by": "height", "height_of": "H", "left": 0.08, "right": 0.075},
                            "o": {"by": "width", "height_of": "x", "left": 0.2, "right": 0.2}}}

    def test_unspaced(self):
        self.assertTrue(sp.unspaced(0, 40, 1000), "a side at its ink")
        self.assertTrue(sp.unspaced(10, 50, 1000), "one side five times the other")
        self.assertFalse(sp.unspaced(50, 55, 1000))
        self.assertFalse(sp.unspaced(25, 30, 1000), "tight is not unspaced")

    def test_reference_changes_from_the_corpus(self):
        self.assertEqual(sp.reference_changes(u"H", 0, 0, 600, {"H": 700}, self.MODEL), (56, 53))
        self.assertEqual(sp.reference_changes(u"o", 10, 30, 400, {"x": 500}, self.MODEL), (70, 50), "by its ink's width")
        self.assertIsNone(sp.reference_changes(u"n", 0, 0, 400, {"x": 500}, self.MODEL), "not in the model")
        self.assertIsNone(sp.reference_changes(u"H", 0, 0, 600, {}, self.MODEL), "no cap height")


class SpacingTests(unittest.TestCase):
    def test_each_side_takes_what_its_reference_pair_asks(self):
        # T's right side wants 30 units less beside H; its left side 12 more; a's sides beside n
        wants = {(u"T", u"H"): -30, (u"H", u"T"): 12, (u"a", u"n"): 4, (u"n", u"a"): None}
        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500), sp.Spacing(u"a", "a", "lower", 30, 20, 450)]
        sp.suggest_spacing(glyphs, lambda left, right: wants.get((left, right)), ak.kind_character, ak.category)
        t, a = glyphs
        self.assertEqual((t.left_change, t.right_change), (12, -30))
        self.assertEqual((a.left_change, a.right_change), (None, 4))
        self.assertEqual(t.changes(6), (12, -30))
        self.assertEqual(a.changes(6), (0, 0), "4 units is within the tolerance; an unmeasured side stays")
        self.assertTrue(t.listed(6))
        self.assertFalse(a.listed(6))

    def test_references_by_kind(self):
        self.assertEqual(sp.reference_for(ak.kind_character(u"\N{LATIN CAPITAL LETTER O WITH STROKE}"), ak.category), u"H")
        self.assertEqual(sp.reference_for(u"g", ak.category), u"n")
        self.assertEqual(sp.reference_for(u"7", ak.category), u"0")
        self.assertEqual(sp.reference_for(u"?", ak.category), u"n", "punctuation sits among lowercase most")

    def test_other_scripts_take_their_own_references(self):
        vo, small_vo = u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}"
        refs = lambda ch: sp.reference_for(ak.kind_character(ch), ak.category, ak.script_of)
        self.assertEqual(refs(u"\N{ARMENIAN CAPITAL LETTER BEN}"), vo)
        self.assertEqual(refs(u"\N{ARMENIAN SMALL LETTER BEN}"), small_vo)
        self.assertEqual(refs(ak.unichr_(0x1C91)), ak.unichr_(0x1C98), "Mtavruli against Mtavruli in")
        self.assertEqual(refs(u"\N{GEORGIAN LETTER BAN}"), u"\N{GEORGIAN LETTER IN}")
        self.assertEqual(refs(u"\N{HIRAGANA LETTER KA}"), u"\N{KATAKANA LETTER RO}")
        self.assertEqual(refs(u"T"), u"H", "Latin as before")
        self.assertEqual(sp.reference_for(u"T", ak.category), u"H", "without script_of: Latin's")
        self.assertEqual(sp.ROUND_REFERENCES[small_vo], u"\N{ARMENIAN SMALL LETTER OH}")
        fixed = sp.fixed_characters(ak)
        for ch in (u"H", small_vo, u"\N{GEORGIAN LETTER ON}", u"\N{HIRAGANA LETTER NO}"):
            self.assertIn(ch, fixed, "a reference is never changed")

    def test_references_to_space_by_script(self):
        vo, small_vo, oh = u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}", u"\N{ARMENIAN SMALL LETTER OH}"
        sides = {u"H": ("H", 50, 50, 700), u"n": ("n", 40, 38, 500), u"o": ("o", 35, 35, 500),
                 vo: ("Vo", 0, 0, 600), small_vo: ("vo", 40, 40, 500), oh: ("oh", 36, 36, 500)}
        self.assertEqual(sp.references_to_space(sides, 1000), [vo, small_vo, oh], "Armenian's capital vo is unspaced")
        sides[vo] = ("Vo", 50, 50, 600)
        self.assertEqual(sp.references_to_space(sides, 1000), [])
        sides[u"n"] = ("n", 0, 2, 500)
        self.assertEqual(sp.references_to_space(sides, 1000), [u"H", u"n", u"o"], "Latin's alone")

    def test_composites_follow_their_base(self):
        composites = {"eacute": ("e", ["acute"]), "ecircumflexacute": ("ecircumflex", ["acute"]),
                      "ecircumflex": ("e", ["circumflex"]), "f_e": ("f", ["e"]), "aacute": ("a", ["acute"])}
        moves = sp.composite_moves(composites, {"e": (5, -3), "f": (2, 2)})
        self.assertEqual(moves["eacute"], (5, 2), "its accent moves with the e's outline; its width follows")
        self.assertEqual(moves["ecircumflexacute"], (5, 2), "built on a composite that follows")
        self.assertIsNone(moves["f_e"], "two of its letters changed: left for a look")
        self.assertNotIn("aacute", moves)


if __name__ == "__main__":
    unittest.main()
