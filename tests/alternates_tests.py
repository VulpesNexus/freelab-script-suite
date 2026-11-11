# -*- coding: utf-8 -*-
"""Tests of Feature Code's Stylistic alternates tab (its pure parts). Valid Python 2.7 and Python 3."""
from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_alternates as fa  # noqa: E402


class SuggestionTests(unittest.TestCase):
    def test_the_model_reads(self):
        model = fa.load_model()
        self.assertIsNotNone(model)
        rows, families, varied = model
        self.assertEqual(rows[0][0], u"a", "the most varied character in the corpus")
        self.assertGreater(families, varied)

    def test_suggestions_list_what_the_font_has_and_its_alternates(self):
        rows = [(u"a", 49), (u"g", 46), (u"Q", 35)]
        cmap = {ord(u"a"): u"a", ord(u"Q"): u"Q"}
        names = set([u"a", u"a.ss01", u"a.sc", u"Q", u"Q.cv01"])
        found = fa.suggestions(rows, cmap, names)
        self.assertEqual([(ch, alternates) for ch, _, _, alternates in found],
                         [(u"a", [u"a.ss01"]), (u"Q", [u"Q.cv01"])], "g is not in the font; a.sc is no stylistic alternate")

    def test_the_next_free_set(self):
        self.assertEqual(fa.free_set_name(u"a", set([u"a", u"a.ss01"])), u"a.ss02")

    def test_scopes(self):
        self.assertTrue(fa.in_scope(u"a", "lower"))
        self.assertFalse(fa.in_scope(u"A", "lower"))
        self.assertTrue(fa.in_scope(u"A", "both"))
        self.assertFalse(fa.in_scope(u"1", "both"))


class VariantTests(unittest.TestCase):
    def test_the_same_seed_makes_the_same_variants(self):
        self.assertEqual(fa.variant_params(u"a", 1, "subtle", 7), fa.variant_params(u"a", 1, "subtle", 7))
        self.assertNotEqual(fa.variant_params(u"a", 1, "subtle", 7), fa.variant_params(u"a", 2, "subtle", 7))

    def test_each_change_stays_within_the_strengths_reach(self):
        for key, _, rotation, scale, slant, rise in fa.STRENGTHS:
            for number in range(1, 5):
                r, sx, sy, k, up = fa.variant_params(u"g", number, key, 3)
                self.assertLessEqual(abs(r), rotation)
                self.assertLessEqual(abs(sx - 1), scale + 1e-9)
                self.assertLessEqual(abs(sy - 1), scale + 1e-9)
                self.assertLessEqual(abs(k), slant)
                self.assertLessEqual(abs(up), rise)

    def test_the_matrix_keeps_the_center(self):
        a, b, c, d, e, f = fa.variant_matrix((1.2, 1.03, 0.98, 2.0, 0.0), 250.0, 300.0, 1000.0)
        self.assertAlmostEqual(a * 250 + c * 300 + e, 250.0, 6)
        self.assertAlmostEqual(b * 250 + d * 300 + f, 300.0, 6)
        a, b, c, d, e, f = fa.variant_matrix((0.0, 1.0, 1.0, 0.0, 0.01), 250.0, 300.0, 1000.0)
        self.assertEqual((round(a, 9), round(b, 9), round(c, 9), round(d, 9), round(e, 9), round(f, 9)),
                         (1.0, 0.0, 0.0, 1.0, 0.0, 10.0), "a baseline shift alone: raised by 1% of the em")


if __name__ == "__main__":
    unittest.main()
