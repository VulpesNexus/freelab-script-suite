# -*- coding: utf-8 -*-
"""Tests of the glyph code points FreeLab's tools read: every code point of a glyph, not FontLab's first
alone (IBM Plex Sans JP encodes 日 at the Kangxi radical U+2F47 and at U+65E5, and FontLab's unicode
gives the radical). Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
for folder in ("kerning", "compose", "features"):
    sys.path.insert(0, os.path.join(HERE, os.pardir, folder))
import freelab_auto_kerning as ak  # noqa: E402
import freelab_glyph_compose as ac  # noqa: E402
import freelab_alternates as fa  # noqa: E402


class Glyph(object):
    """A fontgate glyph as FontLab gives it: unicode is the first of unicodes."""

    def __init__(self, name, unicodes):
        self.name, self.unicodes = name, list(unicodes)
        self.unicode = self.unicodes[0] if self.unicodes else None


SUN = Glyph("uni65E5", [0x2F47, 0x65E5])  # the Kangxi radical first, as FontLab orders them
MOON = Glyph("uni6708", [0x2F49, 0x6708])
SKY = Glyph("uni5929", [0x5929])
UNENCODED = Glyph("uni65E5.vert", [])


class SharedTests(unittest.TestCase):
    def test_every_code_point_is_read(self):
        self.assertEqual(ak.glyph_codes(SUN), [0x2F47, 0x65E5])
        self.assertEqual(ak.glyph_codes(UNENCODED), [])
        old = type("Old", (), {"name": "A", "unicode": 0x41, "unicodes": None})()
        self.assertEqual(ak.glyph_codes(old), [0x41], "unicode alone where FontLab gives no list")

    def test_the_map_finds_a_glyph_by_its_ideograph(self):
        found = ak.glyph_code_map([SUN, MOON, SKY, UNENCODED])
        self.assertEqual(found[0x65E5], "uni65E5")
        self.assertEqual(found[0x2F47], "uni65E5")
        self.assertEqual(found[0x6708], "uni6708")
        twin = Glyph("sun.other", [0x65E5])
        self.assertEqual(ak.glyph_code_map([SUN, twin])[0x65E5], "uni65E5", "the first glyph at a code point wins")

    def test_the_main_code_is_not_the_radical(self):
        self.assertEqual(ak.main_code(SUN), 0x65E5)
        self.assertEqual(ak.main_code(SKY), 0x5929)
        self.assertEqual(ak.main_code(Glyph("radical", [0x2F47])), 0x2F47, "a radical alone is the radical")
        self.assertIsNone(ak.main_code(UNENCODED))


class DiacriticsTests(unittest.TestCase):
    def test_the_planning_font_finds_every_code_point(self):
        font = ac.Font([g.name for g in (SUN, SKY)], ac.font_codes(ak, [SUN, SKY]))
        self.assertEqual(font.glyph_for(u"日"), "uni65E5")
        self.assertEqual(font.glyph_for(u"⽇"), "uni65E5")
        twin = Glyph("sun.other", [0x65E5])
        font = ac.Font([SUN.name, twin.name], ac.font_codes(ak, [SUN, twin]))
        self.assertEqual(font.glyph_for(u"日"), "uni65E5", "the first glyph at a code point wins")


class AlternatesTests(unittest.TestCase):
    def test_the_cmap_reads_every_code_point(self):
        page = fa.AlternatesPage.__new__(fa.AlternatesPage)
        page.ak = ak
        package = type("P", (), {"fgPackage": type("F", (), {"glyphs": [SUN, MOON, UNENCODED]})()})()
        page.owner = type("O", (), {"package": package})()
        cmap, names = page.font_maps()
        self.assertEqual(cmap[0x65E5], "uni65E5")
        self.assertEqual(cmap[0x6708], "uni6708")
        self.assertIn("uni65E5.vert", names)


class SourceTests(unittest.TestCase):
    """The tools that map characters to glyphs read every code point (or the main one), not unicode alone."""

    def source(self, *parts):
        import io
        with io.open(os.path.join(HERE, os.pardir, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_no_character_map_from_the_first_code_point(self):
        checks = {
            ("features", "freelab_feature_code.py"): u"dict((g.name, g.unicode) for g in glyphs)",
            ("compose", "freelab_glyph_compose.py"): u"dict((fg.unicode, fg.name) for fg in package.fgPackage.glyphs",
            ("checks", "freelab_font_check.py"): u"[(u\"%s\" % g.name, g.unicode) for g in fgs]",
            ("cjk", "freelab_cjk_spacing.py"): u"dict((g.unicode, g.name)",
            ("cjk", "freelab_cjk_vertical.py"): u"dict((g.unicode, ",
        }
        for parts, old in checks.items():
            self.assertNotIn(old, self.source(*parts), parts)
        self.assertIn(u"self.ak.main_code(g)", self.source("features", "freelab_feature_code.py"))


if __name__ == "__main__":
    unittest.main()
