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
