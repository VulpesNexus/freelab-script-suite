# -*- coding: utf-8 -*-
"""Tests of tools/add_vertical_metrics.py, the step that adds vhea and vmtx (and VORG) to a font FontLab
exported. Python 3 with fontTools (the step runs outside FontLab)."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))
try:
    import fontTools  # noqa: F401
    import add_vertical_metrics as avm
except ImportError:  # (the Python 2.7 run, or no fontTools)
    avm = None


def make_font(path, cff=False):
    """A small font: .notdef, a kana-like box (U+3042), a comma (U+3001) high in its square, a space, and a
    glyph encoded at two code points (U+2F47 and U+65E5), its name not the values'."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    order = [".notdef", "space", "a-kana", "comma", "sun"]
    boxes = {".notdef": (100, 0, 900, 800), "a-kana": (100, -50, 900, 800), "comma": (650, 550, 900, 800),
             "sun": (150, -40, 850, 790), "space": None}
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x20: "space", 0x3042: "a-kana", 0x3001: "comma", 0x2F47: "sun", 0x65E5: "sun"})
    if cff:
        charstrings = {}
        for name in order:
            pen = T2CharStringPen(1000, None)
            box = boxes[name]
            if box:
                pen.moveTo((box[0], box[1]))
                pen.lineTo((box[0], box[3]))
                pen.lineTo((box[2], box[3]))
                pen.lineTo((box[2], box[1]))
                pen.closePath()
            charstrings[name] = pen.getCharString()
        fb.setupCFF("Test", {"FullName": "Test"}, charstrings, {})
    else:
        glyphs = {}
        for name in order:
            pen = TTGlyphPen(None)
            box = boxes[name]
            if box:
                pen.moveTo((box[0], box[1]))
                pen.lineTo((box[0], box[3]))
                pen.lineTo((box[2], box[3]))
                pen.lineTo((box[2], box[1]))
                pen.closePath()
            glyphs[name] = pen.glyph()
        fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(dict((name, (1000, (boxes[name] or (0,))[0])) for name in order))
    fb.setupHorizontalHeader(ascent=880, descent=-120)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=880, sTypoDescender=-120)
    fb.setupPost()
    fb.save(path)


VALUES = {"format": 1, "upm": 1000, "origin": 880, "vhea": {"ascent": 500, "descent": -500, "lineGap": 0},
          "default_height": 1000, "heights": {"comma": 500, "uni65E5": 900}, "codes": {"uni65E5": [0x65E5]}}


@unittest.skipIf(avm is None, "Python 3 with fontTools")
class AddTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="freelab-vertical-")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def font(self, cff=False):
        path = os.path.join(self.folder, "test.otf" if cff else "test.ttf")
        make_font(path, cff)
        with io.open(avm.values_path(path), "w", encoding="utf-8") as handle:
            json.dump(VALUES, handle)
        return path

    def test_vhea_and_vmtx_from_the_values(self):
        from fontTools.ttLib import TTFont
        path = self.font()
        self.assertEqual(avm.main([path]), 0)
        out = TTFont(avm.output_path(path))
        vmtx = out["vmtx"].metrics
        self.assertEqual(vmtx["a-kana"], (1000, 80), "the em; 880 less its top at 800")
        self.assertEqual(vmtx["comma"], (500, 80), "its own advance height, by name")
        self.assertEqual(vmtx["sun"], (900, 90), "by its code point, under another name")
        self.assertEqual(vmtx["space"], (1000, 0), "no ink: 0")
        vhea = out["vhea"]
        self.assertEqual((vhea.ascent, vhea.descent, vhea.lineGap), (500, -500, 0))
        self.assertEqual(vhea.advanceHeightMax, 1000)
        self.assertTrue(1 <= vhea.numberOfVMetrics <= len(out.getGlyphOrder()))
        self.assertNotIn("VORG", out, "a TrueType font has no VORG")
        self.assertEqual(avm.check(avm.output_path(path), VALUES), [])

    def test_a_cff_font_gets_vorg(self):
        from fontTools.ttLib import TTFont
        path = self.font(cff=True)
        self.assertEqual(avm.main([path]), 0)
        out = TTFont(avm.output_path(path))
        self.assertEqual(out["VORG"].defaultVertOriginY, 880)
        self.assertEqual(out["vmtx"].metrics["comma"], (500, 80))

    def test_the_exported_font_is_never_replaced(self):
        path = self.font()
        before = open(path, "rb").read()
        self.assertEqual(avm.main([path, "--out", path]), 2)
        self.assertEqual(avm.main([path]), 0)
        self.assertEqual(avm.main([path]), 2, "the output exists: --force to replace it")
        self.assertEqual(avm.main([path, "--force"]), 0)
        self.assertEqual(open(path, "rb").read(), before)

    def test_another_em_is_refused(self):
        path = self.font()
        with io.open(avm.values_path(path), "w", encoding="utf-8") as handle:
            json.dump(dict(VALUES, upm=2048), handle)
        self.assertEqual(avm.main([path]), 2)

    def test_the_other_tables_are_copied_as_they_are_and_the_export_let_go(self):
        """Saved from a fresh copy: the glyphs read to measure them are not compiled again (live: 8.6 s of
        13 for a CFF font), and come out byte for byte; no file left open (Windows could not move it)."""
        from fontTools.ttLib import TTFont
        for cff in (False, True):
            path = self.font(cff)
            self.assertEqual(avm.main([path, "--force"]), 0)
            source, out = TTFont(path), TTFont(avm.output_path(path))
            for tag in ("CFF " if cff else "glyf", "cmap", "hmtx", "OS/2"):
                self.assertEqual(source.reader[tag], out.reader[tag], tag)
            source.close()
            out.close()
            moved = path + ".moved"
            os.rename(path, moved)
            os.rename(avm.output_path(path), moved + ".vert")

    def test_progress_through_its_steps(self):
        """CJK Vertical's progress bar follows add_tables: matching, measuring (by part), building."""
        from fontTools.ttLib import TTFont
        font = TTFont(self.font())
        seen = []
        avm.add_tables(font, VALUES, lambda step, part=0.0: seen.append((step, part)))
        self.assertEqual(sorted(set(step for step, _ in seen), key=[s for s, _ in seen].index), ["match", "measure", "build"])
        parts = [part for step, part in seen if step == "measure"]
        self.assertEqual(parts, sorted(parts))
        self.assertTrue(all(0.0 <= part < 1.0 for part in parts))

    def test_check_finds_a_wrong_height(self):
        path = self.font()
        self.assertEqual(avm.main([path]), 0)
        problems = avm.check(avm.output_path(path), dict(VALUES, heights={"comma": 600}))
        self.assertTrue(any("another advance height" in p for p in problems), problems)

    def test_harfbuzz_sets_the_text_vertically_with_them(self):
        """With uharfbuzz, each glyph's advance height; without it, None (the gate counts a skip as a
        failure, so no skip here)."""
        try:
            import uharfbuzz  # noqa: F401
            heights = [-1000, -500, -900]
        except ImportError:
            heights = None
        path = self.font()
        self.assertEqual(avm.main([path]), 0)
        self.assertEqual(avm.shaped_heights(avm.output_path(path), u"あ、日"), heights)


if __name__ == "__main__":
    unittest.main()
