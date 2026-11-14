# -*- coding: utf-8 -*-
"""Tests of FreeLab's Proof: glyph lines with their kerning, line breaking, pages with headers and
footers, the strings of each section, and the choice of sample text. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "proof"))
import freelab_proof as fp  # noqa: E402

LANGUAGES_FILE = os.path.join(HERE, os.pardir, "checks", fp.LANGUAGES_FILE)
u = fp.char_of

# A small font: Latin letters and figures (their glyph names are their characters, except a few),
# 500 units wide, and a space of 250.
LETTERS = u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:;!?'-"
NAMED = {u" ": u"space", u".": u"period", u",": u"comma", u"\N{LATIN CAPITAL LETTER A WITH ACUTE}": u"Aacute",
         u"\N{LATIN SMALL LETTER L WITH STROKE}": u"lslash", u"\N{COMBINING ACUTE ACCENT}": u"acutecomb",
         u"\N{LATIN SMALL LETTER E WITH ACUTE}": u"eacute"}


def make_font(chars=LETTERS + u" ", widths=None, kerning=None, extra=(), master=u"Regular", upm=1000,
              missing=()):
    """A ProofFont of chars (each a glyph named after it, or as NAMED says), plus extra unencoded names."""
    names, codes = [], {}
    for ch in chars:
        name = NAMED.get(ch, ch)
        names.append(name)
        codes[name] = [ord(ch)]
    names += list(extra)
    widths = dict(widths or {})

    def advance(name):
        if name in missing:
            return None
        if name in widths:
            return widths[name]
        if name == u"space":
            return 250
        if name == u"acutecomb":
            return 0
        return 500

    return fp.ProofFont(u"Test Sans", master, upm, names, codes, advance, kerning or {}, 800, -200,
                        lambda name: (-300.0, -100.0) if name == u"acutecomb" else (50.0, 450.0))


HEBREW_GLYPHS = ((u"H", ord(u"H")), (u"O", ord(u"O")), (u"T", ord(u"T")), (u"n", ord(u"n")), (u"o", ord(u"o")),
                 (u"period", ord(u".")), (u"he", 0x05D4), (u"samekh", 0x05E1), (u"yod", 0x05D9), (u"bet", 0x05D1),
                 (u"haa", 0x0780))  # (haa: Thaana)


def hebrew_font(kerning=None):
    """A ProofFont with Hebrew letters (and their controls, he and samekh), a Thaana letter, a few Latin
    ones, a period, and an unencoded yod.alt; every glyph 500 units wide. kerning: FontLab's keys."""
    names = [name for name, _ in HEBREW_GLYPHS] + [u"yod.alt"]
    codes = dict((name, [code]) for name, code in HEBREW_GLYPHS)
    return fp.ProofFont(u"Test Hebrew", u"Regular", 1000, names, codes, lambda name: 500, kerning or {}, 800, -200,
                        lambda name: (50.0, 450.0))


class PlaceTests(unittest.TestCase):
    def test_kerning_moves_the_glyphs_after_the_pair(self):
        font = make_font(kerning={(u"T", u"o"): -80})
        placed, width = fp.place(font, [u"T", u"o", u"n"])
        self.assertEqual(placed, [(u"T", 0.0), (u"o", 420.0), (u"n", 920.0)])
        self.assertEqual(width, 1420.0)

    def test_without_kerning_and_with_spaces(self):
        font = make_font(kerning={(u"T", u"o"): -80, (u"o", u"T"): -30})
        placed, width = fp.place(font, [u"T", u"o", None, u"T"], kerning=False)
        self.assertEqual([x for _, x in placed], [0.0, 500.0, 1250.0])
        placed, _ = fp.place(font, [u"o", None, u"T"])
        self.assertEqual(placed[1][1], 750.0, "no kerning across a space")

    def test_right_to_left_reverses_and_kerns_in_text_order(self):
        # The font's key of a right-to-left pair is in text order, its right glyph first (FontLab 7
        # keeps typed yod then bet as (yod, bet)): a then b typed is kerned by (a, b), b at the left
        font = make_font(kerning={(u"a", u"b"): -50})
        placed, width = fp.place(font, [u"a", u"b"], rtl=True)
        self.assertEqual(placed, [(u"b", 0.0), (u"a", 450.0)], "a reads first, so it sits at the right")
        self.assertEqual(width, 950.0)
        font = make_font(kerning={(u"b", u"a"): -50})
        placed, _ = fp.place(font, [u"a", u"b"], rtl=True)
        self.assertEqual(placed, [(u"b", 0.0), (u"a", 500.0)], "the pair as seen, left glyph first, is no key")

    def test_wrap_measures_right_to_left_kerning_in_text_order(self):
        font = make_font(kerning={(u"a", u"b"): 100})
        self.assertEqual(fp.wrap(font, [([u"a", u"b"], False)], 1050, rtl=True), [[u"a"], [u"b"]])
        font = make_font(kerning={(u"b", u"a"): 100})
        self.assertEqual(fp.wrap(font, [([u"a", u"b"], False)], 1050, rtl=True), [[u"a", u"b"]])

    def test_clip_keeps_what_fits(self):
        font = make_font()
        placed, width = fp.clip(font, [u"a", u"b", u"c", u"d"], 1600)
        self.assertEqual([name for name, _ in placed], [u"a", u"b", u"c"])
        self.assertEqual(width, 1500.0)
        placed, width = fp.clip(font, [u"a", u"b", u"c", u"d"], 1600, rtl=True)
        self.assertEqual([name for name, _ in placed], [u"c", u"b", u"a"], "right to left: its start, at the right")
        self.assertEqual(placed[0][1], 100.0)


class WrapTests(unittest.TestCase):
    def test_words_break_at_spaces(self):
        font = make_font()
        tokens = fp.tokens_of(font.sequence(u"ab cd ef"))
        self.assertEqual(tokens, [([u"a", u"b"], False), ([u"c", u"d"], True), ([u"e", u"f"], True)])
        lines = fp.wrap(font, tokens, 2300)  # two words and a space: 2250
        self.assertEqual(lines, [[u"a", u"b", None, u"c", u"d"], [u"e", u"f"]])

    def test_a_word_too_wide_is_broken_between_its_glyphs(self):
        font = make_font()
        lines = fp.wrap(font, [([u"a", u"b", u"c", u"d", u"e"], False)], 1200)
        self.assertEqual(lines, [[u"a", u"b"], [u"c", u"d"], [u"e"]])

    def test_unspaced_text_breaks_anywhere_and_keeps_its_kerning(self):
        font = make_font(kerning={(u"a", u"b"): -100})
        tokens = fp.tokens_of([u"a", u"b", u"c", None, u"d"], unspaced=True)
        self.assertEqual(tokens, [([u"a"], False), ([u"b"], False), ([u"c"], False), ([u"d"], True)])
        lines = fp.wrap(font, tokens, 1400)
        self.assertEqual(lines, [[u"a", u"b", u"c"], [u"d"]], "a and b kerned: 1400 fits")

    def test_wrap_is_measured_with_the_kerning(self):
        font = make_font(kerning={(u"a", u"b"): 100})
        self.assertEqual(fp.wrap(font, [([u"a", u"b"], False)], 1050), [[u"a"], [u"b"]])


class LayoutTests(unittest.TestCase):
    def test_lines_fill_pages_then_go_on(self):
        font = make_font()
        layout = fp.Layout()
        layout.begin("text", u"Regular")
        height = fp.line_height(font, 20)
        room = layout.bottom - layout.top
        count = int(room // height) + 3
        for _ in range(count):
            layout.glyphs(font, [(u"a", 0.0)], 500, 20)
        self.assertEqual(len(layout.pages), 2)
        self.assertEqual(sum(1 for item in layout.pages[1].items if item.kind == "glyphs"), 3)
        for page in layout.pages:
            for item in page.items:
                self.assertLessEqual(item.baseline, layout.bottom)

    def test_a_section_continues_the_page_when_room_is_left_and_a_new_master_turns_it(self):
        layout = fp.Layout()
        layout.begin("charset", u"Regular")
        layout.begin("waterfall", u"Regular")
        self.assertEqual(len(layout.pages), 1)
        self.assertEqual(layout.pages[0].sections, ["charset", "waterfall"])
        layout.begin("charset", u"Bold")
        self.assertEqual(len(layout.pages), 2)
        self.assertEqual(layout.pages[1].master, u"Bold")

    def test_headers_and_footers(self):
        layout = fp.Layout()
        layout.begin("charset", u"Regular")
        layout.new_page()
        layout.finish(u"Test Sans", u"2026-11-11")
        texts = [[item.text for item in page.items if item.kind == "text"] for page in layout.pages]
        self.assertEqual(texts[0][:3], [u"Test Sans", u"Master Regular", u"2026-11-11"])
        self.assertIn(u"Page 1 of 2", texts[0])
        self.assertIn(u"Page 2 of 2", texts[1])
        self.assertIn(u"Character set", texts[1])
        self.assertIn(fp.NOTE, texts[1])

    def test_right_to_left_lines_are_set_flush_right(self):
        font = make_font()
        layout = fp.Layout()
        layout.begin("text", u"Regular")
        layout.glyphs(font, [(u"a", 0.0)], 500, 10, align="right")
        run = [item for item in layout.page.items if item.kind == "glyphs"][0]
        self.assertAlmostEqual(run.x, layout.right - 5.0)

    def test_sizes(self):
        self.assertEqual(fp.parse_sizes(u"8, 9 10,5 9 2 500", (12,)), (8.0, 9.0, 10.5))
        self.assertEqual(fp.parse_sizes(u"none", (12,)), (12,))
        self.assertEqual(fp.format_size(10.5), u"10.5")
        self.assertEqual(fp.format_size(12.0), u"12")

    def test_long_text_is_broken_into_lines(self):
        lines = fp.text_lines(u"one two three four five six", 40, 8)  # at least 10 characters a line
        self.assertEqual(lines, [u"one two", u"three four", u"five six"])
        layout = fp.Layout()
        layout.begin("about", u"Regular")
        layout.text(u"word " * 200)
        texts = [item for item in layout.page.items if item.kind == "text"]
        self.assertGreater(len(texts), 5)
        self.assertTrue(all(len(item.text) * 8 * fp.CHAR_SHARE <= layout.width() for item in texts))

    def test_file_name(self):
        self.assertEqual(fp.pdf_name(u"My: Font", u"Bold/Italic", u"2026-11-11"), u"My Font Bold Italic proof 2026-11-11.pdf")
        self.assertEqual(fp.pdf_name(u"Sans", u"", u"2026-11-11"), u"Sans proof 2026-11-11.pdf")


class StringTests(unittest.TestCase):
    def test_kinds_and_controls(self):
        font = make_font(extra=[u"a.sc", u"f_i"])
        self.assertEqual(font.kind_of(u"T"), ("LATIN", "upper"))
        self.assertEqual(font.kind_of(u"a.sc"), ("LATIN", "lower"), "an unencoded glyph goes by its base's")
        self.assertEqual(font.kind_of(u"f_i"), ("LATIN", "lower"))
        self.assertEqual(font.kind_of(u"7"), ("FIGURE", None))
        self.assertIsNone(font.kind_of(u"period"))
        self.assertEqual(font.controls(("LATIN", "upper")), (u"H", u"O"))
        self.assertEqual(font.controls(("GREEK", "lower")), (u"n", u"o"), "Greek controls missing: Latin's")
        self.assertEqual(font.controls(("FIGURE", None)), (u"H", u"0"))

    def test_kerning_strings_group_by_left_glyph_between_controls(self):
        font = make_font(kerning={(u"T", u"o"): -80, (u"T", u"A"): -40, (u"period", u"T"): -20, (u"V", u"a"): 0,
                                  (u"x", u"gone"): -10})
        groups = fp.kerning_strings(font)
        self.assertEqual([left for left, _ in groups], [u"T", u"period"], "in the font's order; zero and missing out")
        strings = dict((right, names) for right, _, names in groups[0][1])
        self.assertEqual(strings[u"A"], [u"H", u"H", u"T", u"A", u"H", u"O", u"H", u"O"])
        self.assertEqual(strings[u"o"], [u"H", u"H", u"T", u"o", u"n", u"o", u"n", u"o"], "HH?nono: each side's kind")
        self.assertEqual(groups[1][1][0][2][:4], [u"H", u"H", u"period", u"T"], "punctuation takes its partner's kind")

    def test_kerning_strings_keep_filter(self):
        font = make_font(kerning={(u"T", u"o"): -80, (u"T", u"A"): -40})
        keep = fp.common_filter({u"To": 0}, font.codes)
        groups = fp.kerning_strings(font, keep)
        self.assertEqual([right for right, _, _ in groups[0][1]], [u"o"])

    def test_common_filter_reads_a_hebrew_key_in_text_order(self):
        # FontLab keeps yod-then-bet (bet at the left on screen) as the key (yod, bet), as the common
        # pairs are counted: typed order; a ")" glyph first is an opening parenthesis typed "("
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        yod, bet = u"\N{HEBREW LETTER YOD}", u"\N{HEBREW LETTER BET}"
        codes = {u"yod": [ord(yod)], u"bet": [ord(bet)], u"parenright": [ord(u")")]}
        keep = fp.common_filter({yod + bet: 0, u"(" + yod: 1}, codes, ak)
        self.assertTrue(keep(u"yod", u"bet"))
        self.assertFalse(keep(u"bet", u"yod"), "the screen order is not a key")
        self.assertTrue(keep(u"parenright", u"yod"), "the mirrored parenthesis, typed (")
        self.assertTrue(fp.common_filter({yod + bet: 0}, codes)(u"yod", u"bet"), "without Auto Kerning: the key as typed")

    def test_directions_of_glyphs_and_pairs(self):
        font = hebrew_font()
        self.assertEqual(font.direction(u"yod"), "rtl")
        self.assertEqual(font.direction(u"yod.alt"), "rtl", "an unencoded glyph goes by its base's")
        self.assertEqual(font.direction(u"haa"), "rtl", "Thaana too")
        self.assertIsNone(font.direction(u"T"))
        self.assertIsNone(font.direction(u"period"))
        self.assertTrue(font.rtl_pair(u"yod", u"bet"))
        self.assertTrue(font.rtl_pair(u"period", u"yod"), "punctuation takes its partner's direction")
        self.assertFalse(font.rtl_pair(u"period", u"T"))
        self.assertFalse(font.rtl_pair(u"T", u"o"))

    def test_right_to_left_code_points_by_table_on_any_interpreter(self):
        # A table, not unicodedata: FontLab's Python 2.7 knows Unicode 5.2 and cannot read a character
        # past U+FFFF, so Adlam or Old Hungarian would have read as left to right there
        rtl = (0x05D0, 0x0627, 0x0710, 0x0780, 0x07CA, 0xFB2A, 0xFEFB, 0x10A60, 0x10C80, 0x10D00, 0x1E900, 0x1E922)
        for code in rtl:
            self.assertTrue(fp.is_rtl_code(code), u"U+%04X" % code)
        ltr = (0x41, 0x2E, 0x0661, 0x06F1, 0x10E60, 0xFEFF, 0x1820, 0xA840, 0x1681, 0x1720, 0x4E00, 0x3042)
        for code in ltr:  # (Latin, a period, Arabic-Indic and Rumi numbers, the BOM, Mongolian, Phags-pa,
            self.assertFalse(fp.is_rtl_code(code), u"U+%04X" % code)  # Ogham, Hanunoo, Han, kana)
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        self.assertEqual((fp.RTL_RANGES, fp.RTL_NUMBER_RANGES), (ak.RTL_RANGES, ak.RTL_NUMBER_RANGES),
                         "Proof reads directions as Kerning Check and Font Compare do")
        font = fp.ProofFont(u"Adlam", u"Regular", 1000, [u"alif", u"daali", u"one"],
                            {u"alif": [0x1E900], u"daali": [0x1E901], u"one": [0x1E951]}, lambda name: 500)
        self.assertTrue(font.rtl_pair(u"alif", u"daali"), "Adlam, past U+FFFF")

    def test_scripts_written_top_to_bottom_are_set_horizontally_and_said_so(self):
        chars = {u"a": 0x61, u"mongolian_a": 0x1820, u"phagspa_ka": 0xA840, u"mongolian_comma": 0x1802,
                 u"ogham_beith": 0x1681, u"hanunoo_a": 0x1720}
        names = sorted(chars)
        codes = dict((name, [code]) for name, code in chars.items())
        font = fp.ProofFont(u"Test Vertical", u"Regular", 1000, names, codes, lambda name: 500)
        self.assertEqual(fp.vertical_scripts(font), [u"Mongolian", u"Phags-pa"], "Ogham and Hanunoo run left to right")
        latin = fp.ProofFont(u"Test", u"Regular", 1000, [u"a", u"mongolian_comma"],
                             {u"a": [0x61], u"mongolian_comma": [0x1802]}, lambda name: 500)
        self.assertEqual(fp.vertical_scripts(latin), [], "a Mongolian punctuation mark alone is no Mongolian")
        placed, _ = fp.place(font, [u"mongolian_a", u"phagspa_ka"])
        self.assertEqual([name for name, _ in placed], [u"mongolian_a", u"phagspa_ka"], "left to right, as encoded")
        proof = fp.build_proof([font], fp.Options([]), [], u"2026-11-11", summary=fp.Summary(u"Test Vertical"))
        texts = [item.text for item in proof.pages[0].items if item.kind == "text"]
        self.assertIn(u"Set horizontally", texts)
        self.assertTrue(any(text.startswith(u"Mongolian, Phags-pa (written top to bottom") for text in texts))
        proof = fp.build_proof([font], fp.Options([]), [], u"2026-11-11")
        texts = u" ".join(item.text for item in proof.pages[0].items if item.kind == "text")
        self.assertIn(u"Set horizontally: Mongolian, Phags-pa (written top to bottom", texts)
        proof = fp.build_proof([latin], fp.Options([]), [], u"2026-11-11", summary=fp.Summary(u"Test"))
        self.assertNotIn(u"Set horizontally", [item.text for item in proof.pages[0].items if item.kind == "text"])

    def test_hebrew_kerning_strings_read_right_to_left_kerned_by_the_key(self):
        # Typed yod then bet: the key (yod, bet), bet at the left on screen. The string is the key's
        # glyphs between Hebrew controls in text order (he he yod bet he samekh he samekh), set from
        # the right, the kerning between bet and yod
        font = hebrew_font({(u"yod", u"bet"): -64})
        groups = fp.kerning_strings(font)
        strings = dict(groups)
        self.assertEqual(strings[u"yod"][0][2], [u"he", u"he", u"yod", u"bet", u"he", u"samekh", u"he", u"samekh"])
        layout = fp.Layout()
        layout.begin("kerning", u"Regular")
        fp.section_kerning(layout, font)
        runs = [item for item in layout.page.items if item.kind == "glyphs"]
        hebrew = [item for item in runs if u"yod" in [name for name, _ in item.placed]
                  and [name for name, _ in item.placed][-2:] == [u"he", u"he"]][0]
        self.assertTrue(hebrew.rtl)
        x = dict((name, at) for name, at in hebrew.placed[4:6])
        self.assertEqual([name for name, _ in hebrew.placed][4:6], [u"bet", u"yod"], "bet at the left of yod")
        self.assertEqual(x[u"yod"] - x[u"bet"], 500 - 64, "kerned by (yod, bet), not by the pair as seen")
        self.assertAlmostEqual(hebrew.x + hebrew.placed[-1][1] * hebrew.size / font.upm + 500 * hebrew.size / font.upm,
                               layout.right, msg="flush right: the string starts at the right")
        self.assertIn([u"he", u"he", u"yod", u"bet", u"he", u"samekh", u"he", u"samekh"], layout.page.runs(),
                      "the Glyph window gets the string in text order (FontLab kerns it by the same key)")

    def test_a_group_of_both_directions_is_set_in_runs(self):
        font = hebrew_font({(u"period", u"T"): -20, (u"period", u"yod"): -30})
        groups = dict(fp.kerning_strings(font))
        runs = fp.direction_runs(font, u"period", groups[u"period"])
        self.assertEqual([rtl for rtl, _ in runs], [False, True], "T (Latin) first in the font's order, then yod")
        layout = fp.Layout()
        layout.begin("kerning", u"Regular")
        fp.section_kerning(layout, font)
        flags = [item.rtl for item in layout.page.items if item.kind == "glyphs"]
        self.assertEqual(flags, [False, True])

    def test_hebrew_spacing_strings_read_right_to_left(self):
        font = hebrew_font()
        layout = fp.Layout()
        layout.begin("spacing", u"Regular")
        fp.section_spacing(layout, font)
        flags = dict((item.placed[-1][0], item.rtl) for item in layout.page.items if item.kind == "glyphs")
        self.assertTrue(any(flags.values()), "the Hebrew letters' line")
        self.assertFalse(all(flags.values()), "the Latin letters' lines")

    def test_spacing_strings(self):
        font = make_font()
        groups = dict(fp.spacing_strings(font))
        self.assertEqual(sorted(groups), [u"Figures", u"Latin capitals", u"Latin lowercase"])
        self.assertEqual(dict(groups[u"Latin capitals"])[u"B"], [u"H", u"H", u"B", u"H", u"O", u"B", u"O", u"O"])
        self.assertEqual(dict(groups[u"Latin lowercase"])[u"b"], [u"n", u"n", u"b", u"n", u"o", u"b", u"o", u"o"])
        self.assertEqual(dict(groups[u"Figures"])[u"5"], [u"H", u"H", u"5", u"H", u"0", u"5", u"0", u"0"])

    def test_spacing_strings_leave_modifier_letters_out(self):
        font = make_font(u"Hnox" + u"ʰ" + u"ₒ")
        names = [name for _, strings in fp.spacing_strings(font) for name, _ in strings]
        self.assertEqual(names, [u"H", u"n", u"o", u"x"])

    def test_spacing_strings_on_a_bare_font(self):
        font = make_font(u"xyz")
        self.assertEqual(fp.spacing_strings(font), [(u"Latin lowercase", [(u"x", [u"x"]), (u"y", [u"y"]), (u"z", [u"z"])])],
                         "no control letters: each letter alone")

    def test_diacritics_group_under_their_base(self):
        chars = LETTERS + u"\N{LATIN CAPITAL LETTER A WITH ACUTE}\N{LATIN SMALL LETTER L WITH STROKE}" \
                          u"\N{COMBINING ACUTE ACCENT}\N{LATIN SMALL LETTER E WITH ACUTE}"
        font = make_font(chars)
        groups = fp.diacritic_groups(font)
        self.assertEqual(groups, [(u"A", [u"Aacute"]), (u"e", [u"eacute"]), (u"l", [u"lslash"])])
        combining, spacing = fp.marks_of(font)
        self.assertEqual(combining, [u"acutecomb"])

    def test_figure_rows(self):
        font = make_font(extra=[u"0.osf", u"1.osf"])
        rows = dict(fp.figure_rows(font))
        self.assertEqual([names[0] for names, _ in rows[u"Figures"]][:3], [u"0", u"1", u"2"])
        self.assertEqual([names[0] for names, _ in rows[u"Figures .osf"]], [u"0.osf", u"1.osf"])
        between = [names[0] for names, _ in rows[u"Figures between capitals"]]
        self.assertEqual(between[:5], [u"H", u"0", u"H", u"1", u"H"])
        self.assertTrue(all(not spaced for _, spaced in rows[u"Figures between capitals"]), "one run")
        self.assertTrue(all(spaced for _, spaced in rows[u"Punctuation"]), "each mark apart")


class ScopeTests(unittest.TestCase):
    def test_a_script_keeps_its_letters_and_the_common_glyphs(self):
        greek = u"".join(u(code) for code in range(0x3B1, 0x3BA))
        font = make_font(u"abcxyz019.," + greek, extra=[u"a.ss01"], kerning={(u"a", u"b"): -10, (u"a", greek[0]): -5})
        kept = fp.scope_names(font, ("script", u"LATIN"))
        self.assertIn(u"a", kept)
        self.assertIn(u"a.ss01", kept, "an alternate of a Latin letter")
        self.assertIn(u"0", kept, "figures stay")
        self.assertNotIn(greek[0], kept)
        small = fp.restricted(font, kept)
        self.assertEqual(small.kerning, {(u"a", u"b"): -10}, "pairs within the scope only")

    def test_a_language_keeps_its_letters(self):
        font = make_font(u"abcdefghijklmnopqrstuvwxyzñé .,")
        spanish = type("L", (), {"base": [u"a", u"b", u"ñ"], "auxiliary": [u"é"]})()
        kept = fp.scope_names(font, ("language", spanish))
        letters = sorted(font.code_of(n) for n in kept if fp.glyph_script(font, n))
        self.assertEqual(letters, sorted(ord(c) for c in u"abñé"))

    def test_letters_whose_name_names_no_script_stay_in_every_scope(self):
        odd = u"\N{FEMININE ORDINAL INDICATOR}\N{MICRO SIGN}\N{MODIFIER LETTER CIRCUMFLEX ACCENT}\N{CARON}"
        font = make_font(u"abc" + odd + u"\N{GREEK SMALL LETTER ALPHA}")
        self.assertEqual([fp.glyph_script(font, ch) for ch in odd], [None] * 4)
        self.assertEqual(fp.glyph_script(font, u"a"), u"LATIN")
        kept = fp.scope_names(font, ("script", u"GREEK"))
        self.assertTrue(all(ch in kept for ch in odd))
        self.assertNotIn(u"a", kept)

    def test_languages_carry_their_auxiliary_letters(self):
        languages = fp.load_languages(LANGUAGES_FILE)
        icelandic = [language for language in languages if language.iso == u"isl" and language.script == u"Latin"]
        self.assertEqual(len(icelandic), 1)
        self.assertIn(u"\N{LATIN CAPITAL LIGATURE OE}", icelandic[0].auxiliary)
        self.assertNotIn(u"\N{LATIN CAPITAL LIGATURE OE}", icelandic[0].base)


class SampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.languages = fp.load_languages(LANGUAGES_FILE)

    def test_samples_need_every_character(self):
        english = make_font(u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,")
        groups, left_out = fp.choose_samples(english, self.languages)
        self.assertEqual(groups[0].script, u"Latin")
        self.assertEqual(groups[0].entries, [(u"English", u"The quick brown fox jumps over the lazy dog.")])
        self.assertEqual(left_out, [])

    def test_the_most_spoken_first_and_at_most_a_few(self):
        latin = u"".join(u(code) for code in list(range(0x20, 0x7F)) + list(range(0xA0, 0x250)))
        font = make_font(latin)
        groups, _ = fp.choose_samples(font, self.languages)
        names = [name for name, _ in groups[0].entries]
        self.assertEqual(len(names), fp.MAX_SAMPLES)
        self.assertEqual(names[:2], [u"Spanish", u"English"], "by Hyperglot's speakers")

    def test_letters_stand_in_when_no_sample_fits(self):
        greek = u"".join(u(code) for code in range(0x391, 0x3CA) if code != 0x3A2)  # no final sigma's capital
        font = make_font(greek + u" ")
        groups, _ = fp.choose_samples(font, self.languages)
        self.assertEqual(groups[0].script, u"Greek")
        self.assertTrue(groups[0].alphabet, "no tonos: Modern Greek's sample does not fit")
        self.assertTrue(groups[0].unspaced)
        self.assertIn(u"\N{GREEK SMALL LETTER ALPHA}", groups[0].text())

    def test_ideographs_stand_in_once(self):
        font = make_font(u"".join(u(code) for code in range(0x4E00, 0x5000)))
        groups, _ = fp.choose_samples(font, self.languages)
        han = [g for g in groups if g.script in fp.HAN_SCRIPTS]
        self.assertEqual(len(han), 1, "Kanji, Chinese, and Hanja share the ideographs: shown once")
        self.assertTrue(han[0].alphabet and han[0].unspaced)
        self.assertLessEqual(len(han[0].text()), fp.ALPHABET_MAX)

    def test_hebrew_reads_right_to_left_and_shaped_scripts_are_left_out(self):
        hebrew = u"".join(u(code) for code in range(0x5D0, 0x5EB)) + u"".join(u(code) for code in range(0x5B0, 0x5C8))
        arabic = u"".join(u(code) for code in range(0x621, 0x64B)) + u"".join(u(code) for code in range(0x64B, 0x656))
        font = make_font(hebrew + arabic + u" " + u"".join(u(c) for c in (0xFB2A, 0xFB2B, 0xFB31, 0xFB4A, 0xFB3B,
                                                                            0xFB3A, 0xFB44, 0xFB43)))
        groups, left_out = fp.choose_samples(font, self.languages)
        hebrew_groups = [g for g in groups if g.script == u"Hebrew"]
        self.assertTrue(hebrew_groups and hebrew_groups[0].rtl)
        self.assertIn(u"Arabic", left_out)

    def test_scripts_too_thin_for_any_sample_are_named(self):
        font = make_font(u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .," + u(0x3042) + u(0x3044))
        groups, _ = fp.choose_samples(font, self.languages)
        thin = dict(fp.thin_scripts(font, self.languages, groups))
        self.assertNotIn(u"Latin", thin, "shown")
        self.assertEqual(thin.get(u"Hiragana"), u(0x3042) + u(0x3044), "two kana: no sample, too few to stand in")

    def test_waterfall_line(self):
        font = make_font()
        groups, _ = fp.choose_samples(font, self.languages)
        line, rtl = fp.waterfall_line(font, groups)
        self.assertFalse(rtl)
        self.assertGreaterEqual(len(line), fp.WATERFALL_MIN)
        bare = make_font(u"xyz")
        self.assertEqual(fp.waterfall_line(bare, [])[0], [u"x", u"y", u"z"])


def fold(char):
    """A character's lowercase (Turkish dotted capital I as i), the character itself where its
    lowercase is longer."""
    if char == u"\N{LATIN CAPITAL LETTER I WITH DOT ABOVE}":
        return u"i"
    low = char.lower()
    return low if len(low) == len(char) else char


# Hyperglot letters a pangram leaves out, and why
PANGRAM_EXEMPT = {
    ("ukr", u"\N{CYRILLIC SMALL LETTER E}"): u"Hyperglot 0.8.2 lists Russian's e for Ukrainian, which never writes it",
}
KEPT_SAMPLES = (("eng", "Latin"), ("vie", "Latin"), ("jpn", "Hiragana"), ("jpn", "Katakana"))  # public domain, not ours
HANGUL_BASIC = (u"KIYEOK NIEUN TIKEUT RIEUL MIEUM PIEUP SIOS IEUNG CIEUC CHIEUCH KHIEUKH THIEUTH PHIEUPH HIEUH".split(),
                u"A YA EO YEO O YO U YU EU I".split())


def missing_letters(text, base, iso, script):
    """The letters of base (Hyperglot's, each case) the text lacks: a letter counts in either case, a
    compatibility character (Dutch ij) as its letters, a Hebrew letter with a dot as its letter."""
    import unicodedata
    have = unicodedata.normalize("NFC", u"".join(fold(ch) for ch in text))
    missing = []
    for entry in base:
        letter = unicodedata.normalize("NFC", u"".join(fold(ch) for ch in entry))
        if (iso, letter) in PANGRAM_EXEMPT or letter in have or letter in missing:
            continue
        if unicodedata.normalize("NFKC", letter) in have:
            continue
        if script == "Hebrew" and unicodedata.normalize("NFD", letter)[0] in have:
            continue  # (a pointed letter: the proof does not position marks; its letter stands)
        missing.append(letter)
    return missing


def missing_jamo(text):
    """The basic consonants (as initials or finals) and basic vowels of Hangul a text lacks."""
    import unicodedata
    found = set()
    for ch in text:
        index = ord(ch) - 0xAC00
        if 0 <= index < 11172:
            found.add(unicodedata.name(u(0x1100 + index // 588)).split()[-1])
            found.add(unicodedata.name(u(0x1161 + index % 588 // 28)).split()[-1])
            if index % 28:
                found.add(unicodedata.name(u(0x11A7 + index % 28)).split()[-1])
    return [name for names in HANGUL_BASIC for name in names if name not in found]


class PangramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bases = dict(((language.iso, language.script), language.base)
                         for language in fp.load_languages(LANGUAGES_FILE))

    def test_each_pangram_has_every_letter_of_its_language(self):
        checked = []
        for iso, script, text in fp.SAMPLES:
            if (iso, script) in KEPT_SAMPLES:
                continue
            if script == "Hangul":
                self.assertEqual(missing_jamo(text), [], "%s lacks these jamo" % iso)
            else:
                self.assertIn((iso, script), self.bases, iso)
                self.assertEqual(missing_letters(text, self.bases[(iso, script)], iso, script), [],
                                 "%s lacks these letters" % iso)
            checked.append(iso)
        for iso in ("dan", "hrv", "cat", "lit", "kor", "spa", "fra", "deu", "rus", "ell", "hye", "heb"):
            self.assertIn(iso, checked)

    def test_the_check_finds_a_missing_letter(self):
        base = self.bases[("deu", "Latin")]
        self.assertEqual(missing_letters(u"The quick brown fox jumps over the lazy dog.", base, "deu", "Latin"),
                         [u"\N{LATIN SMALL LETTER A WITH DIAERESIS}", u"\N{LATIN SMALL LETTER O WITH DIAERESIS}",
                          u"\N{LATIN SMALL LETTER U WITH DIAERESIS}", u"\N{LATIN SMALL LETTER SHARP S}"])
        self.assertEqual(missing_jamo(u"\N{HANGUL SYLLABLE GA}"), HANGUL_BASIC[0][1:] + HANGUL_BASIC[1][1:])

    def test_samples_use_only_the_language_and_plain_punctuation(self):
        import unicodedata
        for iso, script, text in fp.SAMPLES:
            if (iso, script) in KEPT_SAMPLES or script == "Hangul":
                continue
            base = set(unicodedata.normalize("NFC", ch) for ch in self.bases[(iso, script)])
            for ch in text:
                if unicodedata.category(ch).startswith(u"L"):
                    self.assertIn(ch, base, u"%s: %s is not among its letters" % (iso, ch))


class InfoTests(unittest.TestCase):
    class Info(object):
        familyName, styleName = u"Test Sans", u"Bold"
        versionMajor, versionMinor = 2, 5
        openTypeNameDesigner = u"  A   Designer "
        designer = u"not this one"
        copyright = u"Copyright line one\r\nline two"
        trademark = u""
        openTypeNameLicense = u"x" * (fp.INFO_TEXT_MAX + 30)
        openTypeNameLicenseURL = None
        openTypeHeadCreated = fp.MAC_EPOCH + 1700000000.0  # counted from 1904

        def openTypeNameDescription(self):  # a method: never called
            raise AssertionError("called")

    def test_rows_in_order_without_the_empty_ones(self):
        rows = fp.info_rows(self.Info(), u"Test Sans Bold", 1000.0, [u"Regular", u"Bold"])
        labels = [label for label, _ in rows]
        self.assertEqual(labels, [u"Family", u"Style", u"Font name", u"Version", u"Designer", u"Copyright", u"License",
                                  u"Created", u"Units per em", u"Masters"])
        values = dict(rows)
        self.assertEqual(values[u"Version"], u"2.005")
        self.assertEqual(values[u"Designer"], u"A Designer", "the first name with a value, its spaces made single")
        self.assertEqual(values[u"Copyright"], u"Copyright line one\nline two")
        self.assertTrue(values[u"License"].startswith(u"x" * fp.INFO_TEXT_MAX + u"\N{HORIZONTAL ELLIPSIS} (30 characters more)"))
        self.assertEqual(values[u"Created"], u"2023-11-14")
        self.assertEqual(values[u"Units per em"], u"1000")
        self.assertEqual(values[u"Masters"], u"Regular, Bold (2)")

    def test_nothing_known(self):
        self.assertEqual(fp.info_rows(None), [])
        self.assertEqual(fp.info_rows(object(), upm=1000), [(u"Units per em", u"1000")])
        self.assertEqual(fp.info_date(1700000000), u"2023-11-14", "from 1970")
        self.assertEqual(fp.info_date(u"2020/01/31 12:00:00"), u"2020/01/31 12:00:00")

    def test_the_info_follows_the_about_block(self):
        font = make_font()
        rows = [(u"Family", u"Test Sans"), (u"License", u"word " * 300)]
        proof = fp.build_proof([font], fp.Options(["charset"]), [], u"2026-11-11", info=rows)
        self.assertEqual(proof.pages[0].sections[:2], ["about", "info"])
        texts = [item for page in proof.pages for item in page.items if item.kind == "text"]
        labels = [item for item in texts if item.text == u"License"]
        self.assertEqual(len(labels), 1, "a field's name once, on its first line")
        lines = [item for item in texts if item.text.startswith(u"word")]
        self.assertGreater(len(lines), 3)
        self.assertTrue(all(item.x == labels[0].x + fp.INFO_LABEL_WIDTH for item in lines))
        bare = fp.build_proof([font], fp.Options(["charset"]), [], u"2026-11-11", info=[])
        self.assertIn(u"FontLab gave none of the font's info.",
                      [item.text for item in bare.pages[0].items if item.kind == "text"])

    def test_colors(self):
        self.assertEqual(fp.page_colors("print", (200, 200, 200), (30, 30, 30)), ((0, 0, 0), (255, 255, 255)))
        self.assertEqual(fp.page_colors("window", (200, 200, 200), (30, 30, 30)), ((200, 200, 200), (30, 30, 30)))
        self.assertEqual(fp.page_colors("window"), fp.PRINT_COLORS, "no palette: black on white")
        self.assertEqual(fp.colors_label("window", (230, 230, 230), (40, 40, 40)), u"the window's: light on dark")
        self.assertEqual(fp.colors_label("print", (0, 0, 0), (255, 255, 255)), u"black on white")
        self.assertAlmostEqual(fp.fit_scale((300, 300), (600, 800)), 0.375, msg="the page's height decides")


class ProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.languages = fp.load_languages(LANGUAGES_FILE)

    def test_every_section_on_a_small_font(self):
        font = make_font(kerning={(u"T", u"o"): -80})
        proof = fp.build_proof([font], fp.Options(), self.languages, u"2026-11-11")
        counts = proof.section_pages()
        for key, _ in fp.SECTIONS:
            self.assertIn(key, counts, key)
        self.assertEqual(proof.kerned, [1])
        for number, page in enumerate(proof.pages, 1):
            texts = [item.text for item in page.items if item.kind == "text"]
            self.assertIn(u"Page %d of %d" % (number, len(proof.pages)), texts)
            for item in page.items:
                if item.kind == "glyphs":
                    for name, _ in item.placed:
                        self.assertTrue(font.has(name), name)

    def test_a_bare_font_says_what_it_lacks(self):
        font = make_font(u"xyz")
        proof = fp.build_proof([font], fp.Options(), self.languages, u"2026-11-11")
        texts = [item.text for page in proof.pages for item in page.items if item.kind == "text"]
        self.assertIn(u"No kerned pairs in this master.", texts)
        self.assertIn(u"The font has no letters with marks.", texts)

    def test_masters_each_on_their_own_pages(self):
        regular = make_font(kerning={(u"T", u"o"): -80})
        bold = make_font(kerning={(u"T", u"o"): -60}, master=u"Bold", widths={u"o": 560}, missing=(u"z",))
        proof = fp.build_proof([regular, bold], fp.Options(["charset", "kerning"]), self.languages, u"2026-11-11")
        self.assertEqual(proof.masters, [u"Regular", u"Bold"])
        self.assertEqual(proof.pages[0].master, fp.ALL_MASTERS)
        self.assertIn("masters", proof.pages[0].sections)
        masters = [page.master for page in proof.pages]
        self.assertIn(u"Regular", masters)
        self.assertIn(u"Bold", masters)
        self.assertEqual(masters.index(u"Bold"), max(i for i, m in enumerate(masters) if m != u"Bold") + 1,
                         "Bold's pages after Regular's")
        bold_texts = [item.text for page in proof.pages if page.master == u"Bold" for item in page.items
                      if item.kind == "text"]
        self.assertIn(u"no layer", bold_texts, "z has no layer in Bold")
        runs = [item for page in proof.pages if page.master == u"Bold" for item in page.items if item.kind == "glyphs"]
        self.assertTrue(all(item.master == u"Bold" for item in runs))

    def test_only_the_sections_picked(self):
        font = make_font()
        proof = fp.build_proof([font], fp.Options(["waterfall"]), self.languages, u"2026-11-11")
        self.assertEqual(sorted(proof.section_pages()), ["about", "waterfall"])
        runs = [item for page in proof.pages for item in page.items if item.kind == "glyphs"]
        self.assertEqual(sorted(set(item.size for item in runs)), sorted(fp.WATERFALL_SIZES))


def font_check():
    """Font Check, as a module (its window not opened): the summary's coverage is its own computation."""
    folder = os.path.join(HERE, os.pardir, "checks")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import freelab_font_check
    return freelab_font_check


LATIN_1_A = [code for code in list(range(0x20, 0x7F)) + list(range(0xA0, 0x180))]  # Latin-1 and Latin Extended-A


class Metrics(object):
    upm, ascender, descender, line_gap, x_height, cap_height = 1000.0, 750.0, -250.0, None, 499.5, 700.0
    typo_ascender, typo_descender, typo_line_gap = 950.0, -250.0, 0.0
    hhea_ascender = hhea_descender = hhea_line_gap = None
    win_ascent, win_descent, use_typo = 1024.4, 300.0, True


def summary_texts(proof, key="summary"):
    return [item.text for page in proof.pages if key in page.sections for item in page.items if item.kind == "text"]


def entries(prefix, count, inferred=0):
    """count names, the first few inferred from text."""
    return [(u"%s%04d" % (prefix, index), index < inferred, u"") for index in range(count)]


class SummaryTests(unittest.TestCase):
    def test_features_in_one_text_in_their_number(self):
        self.assertEqual(fp.features_text([]), u"none in the font's code")
        self.assertEqual(fp.features_text([(u"liga", u"")]), u"1 feature: liga (Standard Ligatures)")
        self.assertEqual(fp.features_text([(u"kern", None), (u"ss03", u"Round a"), (u"zzzz", u""), (u"cv12", u"")]),
                         u"4 features: kern (Kerning), ss03 (Stylistic Set 3: Round a), zzzz, cv12 (Character Variant 12)")
        self.assertEqual(fp.feature_title(u"ss21"), u"", "OpenType has twenty stylistic sets")
        self.assertEqual(fp.feature_title(u"ss00"), u"")

    def test_kerning_in_one_line_in_its_numbers(self):
        self.assertEqual(fp.kerning_text(0, u"Regular"), u"0 kerned pairs in master Regular, classes resolved")
        self.assertEqual(fp.kerning_text(1, u"Regular", 1, 1),
                         u"1 kerned pair in master Regular, classes resolved (1 entry, 1 class)")
        self.assertEqual(fp.kerning_text(1204, u"Bold", 86, 2),
                         u"1,204 kerned pairs in master Bold, classes resolved (86 entries, 2 classes)")

    def test_vertical_metrics_as_a_small_table(self):
        rows = fp.metric_rows(Metrics(), u"Regular")
        self.assertEqual(rows, [(u"Master Regular", [u"750", u"-250", fp.NOT_SET]), (u"Typo", [u"950", u"-250", u"0"]),
                                (u"hhea", [fp.NOT_SET] * 3), (u"Windows", [u"1024", u"300", u""])])
        self.assertEqual(fp.metric_notes(Metrics()), [(u"Heights", u"x-height 500, cap height 700"),
                                                      (u"Use Typo Metrics", u"on")], "halves round up, on any Python")
        self.assertEqual(fp.metric_notes(object()), [])

    def test_the_font_and_its_masters(self):
        info = [(u"Family", u"Test Sans"), (u"Style", u"Bold"), (u"Version", u"2.005"), (u"Created", u"2023-11-14"),
                (u"Modified", u"2026-11-01"), (u"Units per em", u"1000")]
        rows = fp.summary_rows(info, u"TestSans-Bold", u"Bold", [u"Regular", u"Bold", u"Black"], [u"Bold"], 1234, 1100)
        self.assertEqual(rows, [(u"Font", u"Test Sans Bold"), (u"Master", u"Bold (the font's other masters: Regular, Black)"),
                                (u"Version", u"2.005 (created 2023-11-14, modified 2026-11-01)"),
                                (u"Units per em", u"1000"), (u"Glyphs", u"1,234 glyphs (1,100 encoded characters)")])
        rows = dict(fp.summary_rows(None, u"Bare", u"Regular", [u"Regular"], [u"Regular"], 1, 1, u"Latin only"))
        self.assertEqual(rows, {u"Font": u"Bare", u"Master": u"Regular (the font's only master)",
                                u"Glyphs": u"1 glyph (1 encoded character)", u"Proof of": u"Latin only"})
        rows = dict(fp.summary_rows([(u"Modified", u"2026-11-01")], u"Two", u"Regular", [u"Regular", u"Bold"],
                                    [u"Regular"], 2, 0))
        self.assertEqual(rows[u"Master"], u"Regular (the font's other master: Bold)")
        self.assertEqual(rows[u"Dates"], u"modified 2026-11-01", "no version recorded: its dates alone")
        self.assertEqual(rows[u"Glyphs"], u"2 glyphs (0 encoded characters)")
        rows = dict(fp.summary_rows(None, u"Two", u"Regular", [u"Regular", u"Bold"], [u"Regular", u"Bold"], 2, 2))
        self.assertEqual(rows[u"Masters"], u"Regular, Bold (all 2 proofed)")
        self.assertNotIn(u"Master", rows)

    def test_coverage_is_font_checks_own(self):
        fc = font_check()
        found = fp.coverage_summary(fc, set(LATIN_1_A))
        languages, _ = fc.chosen_languages(fc.load_languages(), True)
        scripts = [s for s in fc.coverage(languages, fc.FontCharacters(set(LATIN_1_A), None), fc.NEARLY_MISSING, True, None)
                   if s.present]
        self.assertEqual([s.script for s in found.scripts], [u"%s" % s.script for s in scripts])
        latin, checked = found.scripts[0], scripts[0]
        self.assertEqual(latin.script, u"Latin")
        self.assertEqual(latin.text, fc.script_text(checked), "the count in Font Check's own words")
        self.assertEqual(len(latin.covered), checked.count("covered"))
        self.assertEqual(len(latin.reach), checked.count("nearly"))
        names = [name for name, _, _ in latin.covered]
        self.assertIn(u"English", names)
        self.assertIn(u"Spanish", names)
        self.assertEqual(names, [u"%s" % r.language.name for r in sorted(checked.results, key=fc.name_key)
                                 if r.level == "covered"], "A to Z, as Font Check orders names")
        # Marked as Font Check marks its rows: the languages no source declares, keyboard layouts' too
        marks = dict((name, mark) for name, mark, _ in latin.covered + latin.reach if mark)
        self.assertEqual(set(marks), set(u"%s" % r.language.name for r in checked.results
                                         if r.level in ("covered", "nearly") and r.language.evidence in fc.UNDECLARED))
        for r in checked.results:
            if u"%s" % r.language.name in marks:
                self.assertEqual(marks[u"%s" % r.language.name], u"keyboard" if r.language.evidence == fc.KEYBOARD
                                 else u"inferred")
        lacks = dict((u"%s" % r.language.name, r) for r in checked.results if r.level == "nearly")
        for name, _, text in latin.reach:  # base characters and marks, at most Font Check's few; or auxiliary ones alone
            r = lacks[name]
            if r.missing or r.marks_missing:
                self.assertEqual(text, u"%d missing" % (len(r.missing) + len(r.marks_missing)))
                self.assertLessEqual(len(r.missing) + len(r.marks_missing), fc.NEARLY_MISSING)
            else:
                self.assertEqual(text, u"%d auxiliary missing" % len(r.auxiliary_missing))
        self.assertTrue(any(text.endswith(u"auxiliary missing") for _, _, text in latin.reach))
        self.assertTrue(all(text == u"" for _, _, text in latin.covered))
        self.assertEqual(found.covered(), sum(len(s.covered) for s in found.scripts))
        self.assertEqual(sum(count for _, count in found.sources), found.covered(), "each covered language has a source")
        self.assertEqual(found.sources[0][0], u"Hyperglot")
        self.assertIsNone(found.composed, "no anchors asked: no letter is composed")
        sets = [fc.check_language(one, fc.FontCharacters(set(LATIN_1_A), None), fc.NEARLY_MISSING)
                for one in fc.load_character_sets()]
        legacy = [r for r in sets if r.language.script == fc.LEGACY_GROUP]
        self.assertEqual((len(legacy), set(r.level for r in legacy)), (5, set([u"covered"])), "covered by a Latin font")
        sets = [r for r in sets if r not in legacy]
        self.assertEqual(found.set_count, len(sets), "the Legacy sets do not count toward the stats")
        self.assertEqual(found.sets, [u"%s" % r.language.name for r in sets if r.level == "covered"])
        self.assertNotIn(u"CJK Compatibility Ideographs (Unicode block)", found.sets)
        import re
        self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2}$", found.dated), found.dated)
        composing = fp.coverage_summary(fc, set(LATIN_1_A), lambda base, mark: True)
        self.assertIsNotNone(composing.composed)
        self.assertGreaterEqual(composing.covered(), found.covered())

    def test_a_font_with_no_script_says_so(self):
        found = fp.coverage_summary(font_check(), set([0x20]))
        self.assertEqual(found.scripts, [])
        self.assertEqual(found.sentence(), u"The font has none of the scripts whose languages Font Check checks.")

    def test_the_counts_sentence_and_the_small_print_follow_their_numbers(self):
        def coverage(covered, reach, inferred=0, composed=None, scripts=1):
            found = [fp.ScriptSummary(u"S%d" % at, u"x", [], []) for at in range(scripts)]
            found[0].covered, found[0].reach = entries(u"c", covered, inferred), entries(u"r", reach)
            return fp.CoverageSummary(found, [], 0, 3, composed, [(u"Hyperglot", covered)] if covered else [], u"2026-11-13")

        self.assertEqual(coverage(0, 0).sentence(), u"0 languages covered and 0 within reach, of the languages of 1 "
                                                    u"script the font has.")
        self.assertEqual(coverage(1, 1, scripts=2).sentence(),
                         u"1 language covered and 1 within reach, of the languages of 2 scripts the font has.")
        self.assertEqual(coverage(1234, 2).sentence()[:25], u"1,234 languages covered a")
        notes = coverage(2, 0, inferred=1, composed=1).notes()
        self.assertIn(u"at most 3 base characters or marks (or auxiliary characters alone).", notes[0])
        self.assertTrue(notes[0].endswith(u"counts as there (1 language covered relies on such letters)."))
        self.assertEqual(notes[1], u"Of the languages covered, 1 is inferred from text or read from a keyboard layout, "
                                   u"not declared by a source.")
        self.assertEqual(notes[2], u"Language data, as Font Check holds it: 2 languages from Hyperglot. Data files last "
                                   u"changed 2026-11-13.")
        notes = coverage(3, 0, inferred=2, composed=2).notes()
        self.assertTrue(notes[0].endswith(u"(2 languages covered rely on such letters)."))
        self.assertEqual(notes[1], u"Of the languages covered, 2 are inferred from text or read from a keyboard layout, "
                                   u"not declared by a source.")
        self.assertEqual(len(coverage(1, 0).notes()), 2, "none inferred: nothing said of it; no anchors: no clause")
        self.assertNotIn(u"anchors", coverage(1, 0).notes()[0])
        one = fp.CoverageSummary([], [], 0, 1)
        self.assertIn(u"at most 1 base character or mark (or", one.notes()[0])

    def page_of(self, summary, font=None, left_out=()):
        font = font or make_font()
        return fp.build_proof([font], fp.Options([]), [], u"2026-11-11", summary=summary)

    def test_the_page_top_to_bottom(self):
        font = make_font()
        coverage = fp.CoverageSummary([fp.ScriptSummary(u"Latin", u"3 of 9 languages (1 within reach)",
                                                        entries(u"Lang", 3, 1), [(u"Near", False, u"2 missing")])],
                                      [u"Adobe Latin 1"], 61, 3, 0, [(u"Hyperglot", 3)], u"2026-11-13")
        summary = fp.Summary(u"Test Sans", [(u"Font", u"Test Sans Regular")], fp.metric_rows(Metrics(), u"Regular"),
                             fp.metric_notes(Metrics()), fp.features_text([(u"liga", u"")]),
                             fp.kerning_text(1, u"Regular"), coverage, "covered")
        proof = self.page_of(summary)
        page = proof.pages[0]
        self.assertEqual(page.sections, ["summary", "coverage"], "no about block beside it")
        self.assertEqual(len(proof.pages), 1)
        body = page.items[8:]  # (after the header and footer)
        title = body[0]
        self.assertEqual((title.kind, title.size), ("glyphs", fp.SUMMARY_TITLE_SIZE), "the family, in the font itself")
        self.assertEqual([name for name, _ in title.placed], [u"T", u"e", u"s", u"t", u"S", u"a", u"n", u"s"])
        texts = [item.text for item in body if item.kind == "text"]
        order = [u"Font", u"Proofed", u"2026-11-11, with FreeLab Proof, from the font's own outlines in FontLab",
                 u"Applied", u"Vertical metrics", u"Ascender", u"Master Regular", u"Windows", u"Heights",
                 u"Use Typo Metrics", u"OpenType", u"Features", u"1 feature: liga (Standard Ligatures)", u"Kerning",
                 u"Language coverage", u"3 languages covered and 1 within reach, of the languages of 1 script the "
                 u"font has.", u"Latin", u"3 of 9 languages (1 within reach)", u"Character sets",
                 u"1 of 61 covered: Adobe Latin 1", fp.INFERRED_KEY, u"Latin, covered (3)", u"Lang0000 (inferred)",
                 u"Lang0001", u"Lang0002"]
        places = [texts.index(text) for text in order]
        self.assertEqual(places, sorted(places), "each block under the one before")
        self.assertNotIn(u"Near (2 missing)", texts, "within reach: counted, listed only when asked")
        sizes = dict((item.text, item.size) for item in body if item.kind == "text")
        self.assertEqual(sizes[u"Lang0001"], fp.SUMMARY_NAME_SIZE)
        self.assertEqual(sizes[u"Vertical metrics"], 9)
        numbers = [item for item in body if item.kind == "text" and item.text == u"950"]
        self.assertEqual(numbers[0].align, "right", "a table's numbers flush right")
        for item in body:
            y = item.baseline if item.kind == "glyphs" else item.y
            self.assertTrue(fp.MARGIN + fp.HEADER_ROOM <= y <= 841.89 - fp.MARGIN - fp.HEADER_ROOM)

    def test_the_language_coverage_closes_the_proof(self):
        # The owner: "maybe language/script coverage should be moved at the very end, leaving only technical data
        # and font info at the beginning before letters"
        coverage = fp.CoverageSummary([fp.ScriptSummary(u"Latin", u"x", entries(u"Lang", 3), [])], [], 0)
        proof = fp.build_proof([make_font()], fp.Options(["charset", "figures"]), [], u"2026-11-11",
                               info=[(u"Font name", u"Test Sans")], summary=fp.Summary(u"Test Sans", coverage=coverage))
        sections = [key for page in proof.pages for key in page.sections]
        self.assertEqual(sections[0], "summary")
        self.assertEqual(sections[-1], "coverage", "after every glyph")
        self.assertLess(sections.index("info"), sections.index("charset"), "the font's info before the letters")
        texts = [item.text for page in proof.pages for item in page.items if item.kind == "text"]
        self.assertLess(texts.index(u"U+0048"), texts.index(u"Language coverage"), "after the letters")
        self.assertIn(u"Lang0001", summary_texts(proof, "coverage"))
        self.assertEqual(fp.TITLES["coverage"], u"Language coverage", "the pages list names it")

    def test_what_the_list_holds_is_a_setting(self):
        coverage = fp.CoverageSummary([fp.ScriptSummary(u"Latin", u"x", entries(u"Lang", 2), [(u"Near", True, u"1 missing")]),
                                       fp.ScriptSummary(u"Greek", u"y", [], [(u"Far", False, u"3 auxiliary missing")])],
                                      [], 0)
        texts = summary_texts(self.page_of(fp.Summary(u"Test Sans", coverage=coverage, languages="reach")))
        for text in (u"Latin, covered (2)", u"Latin, within reach (1)", u"Near (inferred, 1 missing)",
                     u"Greek, within reach (1)", u"Far (3 auxiliary missing)", fp.INFERRED_KEY):
            self.assertIn(text, texts)
        self.assertNotIn(u"Greek, covered (0)", texts, "no heading over nothing")
        texts = summary_texts(self.page_of(fp.Summary(u"Test Sans", coverage=coverage, languages="covered")))
        self.assertNotIn(fp.INFERRED_KEY, texts, "no key without a language it marks")
        self.assertNotIn(u"Latin, within reach (1)", texts)
        texts = summary_texts(self.page_of(fp.Summary(u"Test Sans", coverage=coverage, languages="none")))
        self.assertIn(u"Latin", texts)
        self.assertIn(u"x", texts, "the counts stay")
        self.assertNotIn(u"Lang0000", texts)
        self.assertNotIn(u"Latin, covered (2)", texts)

    def test_keyboard_layout_languages_are_marked_as_font_check_marks_them(self):
        # The summary marked only the inferred languages; Font Check's UNDECLARED holds keyboard layouts' too
        class Check(object):
            INFERRED, KEYBOARD, UNDECLARED = "inferred", "keyboard", ("inferred", "keyboard")

        class Older(object):  # (a Font Check from before keyboard layouts)
            INFERRED = "inferred"

        self.assertEqual([fp.evidence_mark(Check, e) for e in ("declared", "inferred", "keyboard")],
                         [u"", u"inferred", u"keyboard"])
        self.assertEqual([fp.evidence_mark(Older, e) for e in ("declared", "inferred", "keyboard")],
                         [u"", u"inferred", u""])
        self.assertEqual(fp.language_names([(u"Ainu", u"keyboard", u""), (u"Near", u"keyboard", u"1 missing"),
                                            (u"Old", True, u"")]),
                         [u"Ainu (keyboard)", u"Near (keyboard, 1 missing)", u"Old (inferred)"])
        coverage = fp.CoverageSummary([fp.ScriptSummary(u"Latin", u"x", [(u"Ainu", u"keyboard", u"")], [])], [], 0)
        self.assertEqual(coverage.inferred(), 1, "counted with the undeclared")
        texts = summary_texts(self.page_of(fp.Summary(u"Test Sans", coverage=coverage, languages="covered")))
        self.assertIn(u"Ainu (keyboard)", texts)
        self.assertIn(fp.KEYBOARD_KEY, texts)
        self.assertNotIn(fp.INFERRED_KEY, texts, "a key only for a mark the lists show")
        self.assertIn(u"inferred from text or read from a keyboard layout", coverage.notes()[1])

    def test_names_read_down_each_column(self):
        layout = fp.Layout()
        layout.begin("summary", u"Regular")
        names = [u"n%02d" % index for index in range(23)]
        fp.summary_names(layout, names)
        items = [item for item in layout.page.items if item.kind == "text"]
        width = layout.width() / fp.SUMMARY_COLUMNS
        columns = [int(round((item.x - layout.left) / width)) for item in items]
        self.assertEqual(columns, [0] * 5 + [1] * 5 + [2] * 5 + [3] * 5 + [4] * 3, "five rows: down, then across")
        self.assertEqual([item.y for item in items[:5]], [layout.top + row * fp.SUMMARY_NAME_LEADING for row in range(5)])
        self.assertAlmostEqual(layout.y, layout.top + 5 * fp.SUMMARY_NAME_LEADING)

    def test_a_long_list_goes_on_over_the_following_pages_whole(self):
        coverage = fp.CoverageSummary([fp.ScriptSummary(u"Latin", u"x", entries(u"Tongue", 1900, 500), [])], [], 0)
        proof = self.page_of(fp.Summary(u"Test Sans", coverage=coverage))
        pages = [page for page in proof.pages if "coverage" in page.sections]
        self.assertGreater(len(pages), 4)
        self.assertEqual(pages, proof.pages[-len(pages):], "the proof's last pages")
        found = []
        for page in pages:
            names = [item for item in page.items if item.kind == "text" and item.text.startswith(u"Tongue")]
            for item in names:
                self.assertLessEqual(item.y + item.height, 841.89 - fp.MARGIN - fp.HEADER_ROOM + 0.01)
            found += [item.text for item in sorted(names, key=lambda item: (round(item.x), item.y))]
        wanted = fp.language_names(entries(u"Tongue", 1900, 500))
        self.assertEqual(found, wanted, "every name once, in order down the columns of each page: none cut")
        full = [item for item in pages[1].items if item.kind == "text" and item.text.startswith(u"Tongue")]
        self.assertEqual(len(full), 87 * fp.SUMMARY_COLUMNS, "a full page of names (the window's help says some 435)")

    def test_the_pages_a_real_font_takes(self):
        # What the Summary lists dropdown's help says: about four pages for Latin-1 and Latin Extended-A
        fc = font_check()
        coverage = fp.coverage_summary(fc, set(LATIN_1_A))
        proof = self.page_of(fp.Summary(u"Test Sans", coverage=coverage))
        pages = sum(1 for page in proof.pages if "coverage" in page.sections)
        self.assertTrue(3 <= pages <= 5, "%d pages for %d languages" % (pages, coverage.covered()))
        self.assertTrue(800 <= coverage.covered() <= 1200, coverage.covered())
        texts = summary_texts(proof, "coverage")
        self.assertIn(u"English", texts)
        listed = sum(len(script.covered) for script in coverage.scripts)
        self.assertEqual(sum(1 for item in proof.pages for item in item.items
                             if item.kind == "text" and item.size == fp.SUMMARY_NAME_SIZE and item.style == "plain"),
                         listed)

    def test_a_name_the_font_cannot_set_is_set_in_the_labels_typeface(self):
        font = make_font(u"xyz")
        proof = self.page_of(fp.Summary(u"Test Sans"), font)
        body = proof.pages[0].items[8:]
        self.assertEqual((body[0].kind, body[0].text, body[0].style), ("text", u"Test Sans", "bold"))
        self.assertNotIn(u"Language coverage", summary_texts(proof), "no coverage read: left out, not failed")
        self.assertNotIn(u"Vertical metrics", summary_texts(proof))
        long_name = fp.Summary(u"T" * 60)
        title = self.page_of(long_name).pages[0].items[8]
        self.assertEqual(title.kind, "glyphs")
        self.assertLess(title.size, fp.SUMMARY_TITLE_SIZE)
        self.assertLessEqual(len(title.placed) * 500 * title.size / 1000.0, fp.Layout().width() + 0.01)

    def test_the_title_is_set_in_the_whole_font_whatever_the_scope(self):
        whole = make_font()
        scoped = fp.restricted(whole, set([u"x", u"y"]))
        proof = fp.build_proof([scoped], fp.Options([]), [], u"2026-11-11", summary=fp.Summary(u"Test Sans", font=whole))
        self.assertEqual(proof.pages[0].items[8].kind, "glyphs")

    def test_scripts_left_out_are_named(self):
        font = make_font()
        layout = fp.Layout()
        layout.begin("summary", u"Regular")
        fp.section_summary(layout, font, fp.Summary(u"Test Sans"), u"2026-11-11", [u"Arabic", u"Thai"])
        texts = [item.text for item in layout.page.items if item.kind == "text"]
        self.assertIn(u"Arabic, Thai (shaping is not done)", texts)


class ScopeListTests(unittest.TestCase):
    @staticmethod
    def languages(count):
        names = [u"Zulu", u"Albanian", u"Welsh", u"Basque", u"Maori", u"Dutch"]
        return [fp.Language(u"l%02d" % index, names[index] if index < len(names) else u"Lang %02d" % index, u"Latin",
                            1000 - index, [u"a"]) for index in range(count)]

    def test_the_most_spoken_then_every_other_one(self):
        # The owner, of More languages...: "Works, but why not have them reachable by default?"
        covered = self.languages(60)
        rows = fp.scope_rows([u"LATIN", u"GREEK"], covered)
        texts = [text for text, _ in rows]
        self.assertEqual(texts[:4], [u"Every script", u"Latin only", u"Greek only", None], "the scripts, then a line")
        self.assertEqual(texts[4:7], [u"Zulu (Latin)", u"Albanian (Latin)", u"Welsh (Latin)"], "by speakers, as before")
        self.assertEqual(len(rows), 3 + 1 + fp.SCOPE_LANGUAGES_TOP + 1 + 40, "every language, without asking")
        self.assertNotIn(fp.MORE, [scope for _, scope in rows])
        self.assertEqual(rows[0][1], None)
        self.assertEqual(rows[1][1], ("script", u"LATIN"))

    def test_the_others_follow_a_to_z(self):
        covered = self.languages(60)
        rows = fp.scope_rows([u"LATIN"], covered)
        texts = [text for text, _ in rows]
        self.assertNotIn(fp.MORE_LANGUAGES, texts)
        at = 2 + 1 + fp.SCOPE_LANGUAGES_TOP
        self.assertIsNone(texts[at], "a second line before the others")
        rest = texts[at + 1:]
        self.assertEqual(len(rest), 40)
        self.assertEqual(rest, sorted(rest))
        self.assertEqual(len(set(texts) - set([None])), 2 + 60, "every covered language once")

    def test_few_others_are_listed_at_once_and_a_kept_one_is_never_hidden(self):
        few = self.languages(fp.SCOPE_LANGUAGES_TOP + fp.SCOPE_LANGUAGES_SLACK)
        rows = fp.scope_rows([], few)
        self.assertEqual(len(rows), 1 + 1 + len(few))
        self.assertNotIn(fp.MORE, [scope for _, scope in rows])
        self.assertEqual(fp.scope_rows([], []), [(u"Every script", None)], "no language covered: no line either")
        many = self.languages(60)
        kept = ("language", many[45])
        rows = fp.scope_rows([], many, False, kept)
        self.assertTrue(any(fp.same_scope(scope, kept) for _, scope in rows), "the choice kept stays in the list")
        self.assertFalse(fp.same_scope(fp.MORE, fp.MORE))
        self.assertEqual(fp.scope_label(kept), u"Lang 45 (Latin)")
        self.assertEqual(fp.scope_label(None), u"")

    def test_the_help_gives_the_counts_in_their_numbers(self):
        self.assertIn(u"No language is listed", fp.scope_help(0, 0, True))
        self.assertIn(u"every base character of 1 language Hyperglot describes: it is listed. ", fp.scope_help(1, 0, True))
        self.assertIn(u"of 2 languages Hyperglot describes: all are listed, the most spoken first. ",
                      fp.scope_help(2, 0, True))
        self.assertIn(u"of 25 languages Hyperglot describes: the 20 most spoken are listed, and <i>More languages"
                      u"\N{HORIZONTAL ELLIPSIS}</i> lists the other 5 after them, A to Z. ", fp.scope_help(25, 5, False))
        self.assertIn(u"lists the other one after them", fp.scope_help(21, 1, False))
        self.assertIn(u"of 1,412 languages Hyperglot describes: the 20 most spoken come first, then the other 1,392, "
                      u"A to Z. ", fp.scope_help(1412, 1392, True))
        self.assertIn(u"then the other one, A to Z", fp.scope_help(21, 1, True))
        for text in (fp.scope_help(0, 0, True), fp.scope_help(30, 10, False)):
            self.assertIn(u"Languages within reach are not offered", text)

    def test_covered_means_every_base_character(self):
        font = make_font(u"abc ")
        languages = [fp.Language(u"one", u"One", u"Latin", 5, [u"a", u"b"]),
                     fp.Language(u"two", u"Two", u"Latin", 9, [u"a", u"c"]),
                     fp.Language(u"not", u"Not", u"Latin", 99, [u"a", u"z"]),
                     fp.Language(u"nil", u"Nil", u"Latin", 99, [])]
        self.assertEqual([language.name for language in fp.covered_languages(font, languages)], [u"Two", u"One"])


# ---------------------------------------------------------------------------
# The dialog, run on fakes: any Qt call is accepted and does nothing, and the font is a small fake of
# FontLab's. This catches mistakes in the dialog's own code paths, not in how Qt or FontLab answer.
# ---------------------------------------------------------------------------

class _AnyMeta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Anything()


def _no_dunder(self, name):
    if name.startswith("__"):
        raise AttributeError(name)
    return Anything()


def _zero(*args):
    return 0


Anything = _AnyMeta("Anything", (object,), {
    "__init__": lambda self, *args, **kwargs: None,
    "__getattr__": _no_dunder,
    "__call__": lambda self, *args, **kwargs: Anything(),
    "__iter__": lambda self: iter([]),
    "__len__": _zero, "__int__": _zero, "__index__": _zero, "__float__": lambda self: 0.0,
    "__bool__": lambda self: False, "__nonzero__": lambda self: False,
    "__or__": lambda self, other: Anything(), "__ror__": lambda self, other: Anything(),
    "__add__": _zero, "__radd__": _zero, "__sub__": _zero, "__rsub__": _zero, "__mul__": _zero, "__rmul__": _zero,
    "__truediv__": _zero, "__div__": _zero, "__neg__": _zero,
    "__lt__": lambda self, other: False, "__gt__": lambda self, other: False, "__le__": lambda self, other: False,
    "__ge__": lambda self, other: False, "__str__": lambda self: "", "__unicode__": lambda self: u""})


class _FakeQtModule(object):
    def __init__(self):
        self.classes = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self.classes:
            self.classes[name] = _AnyMeta(name, (Anything,), {})
        return self.classes[name]


# A Qt module whose widgets remember what the dialog tells them: their What's This, their text, a
# check box's state, a dropdown's rows and choice. Anything else is accepted as above.
CONTROLS = ("QPushButton", "QCheckBox", "QComboBox", "QSpinBox", "QDoubleSpinBox", "QLineEdit", "QListWidget",
            "QTreeWidget", "QRadioButton", "QPlainTextEdit")


def _remembering(name, made):
    def init(self, *args, **kwargs):
        self.whats, self.rows, self.kind = u"", [], name
        self.captioned = bool(args) and isinstance(args[0], (type(u""), str))  # made with its text
        if self.captioned:
            self.text = args[0]
        made.append(self)

    def set_whats(self, text):
        self.whats = text

    def set_text(self, text):
        self.text = text

    members = {"__init__": init, "setWhatsThis": set_whats, "setText": set_text}
    if name == "QCheckBox":
        members["setChecked"] = lambda self, on: setattr(self, "on", bool(on))
        members["isChecked"] = lambda self: getattr(self, "on", False)
    if name in ("QComboBox", "QListWidget"):
        members["addItem"] = lambda self, text: self.rows.append(text)
        members["insertSeparator"] = lambda self, at: self.rows.insert(at, None)
        members["clear"] = lambda self: self.rows.__delitem__(slice(None))
        members["count"] = property(lambda self: len(self.rows))
        members["setCurrentIndex"] = lambda self, index: setattr(self, "currentIndex", index)
        members["setCurrentRow"] = lambda self, row: setattr(self, "currentRow", row)
    return _AnyMeta(name, (Anything,), members)


class _RememberingQtModule(_FakeQtModule):
    def __init__(self):
        _FakeQtModule.__init__(self)
        self.made = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self.classes:
            self.classes[name] = _remembering(name, self.made)
        return self.classes[name]


class FakeFeatures(object):
    def __init__(self, features):
        self.features = features

    def keys(self):
        return [tag for tag, _ in self.features]

    def get_feature(self, tag):
        return dict(self.features)[tag]


class FakeLayer(object):
    def __init__(self, advance):
        self.advanceWidth = advance


class FakeFontgateGlyph(object):
    def __init__(self, name, code):
        self.name, self.unicode, self.unicodes = name, code, [code] if code else []


class FakeGlyph(object):
    isNull = False

    def __init__(self, name, code, layers):
        self.name, self.layers_by_master = name, layers
        self.fgGlyph = FakeFontgateGlyph(name, code)

    def getLayerByName(self, master):
        return self.layers_by_master.get(master)


class FakeKerning(object):
    def __init__(self, pairs):
        self.pairs, self.groups = pairs, {}

    def getPlainPairsDict(self):
        return dict(self.pairs)

    def items(self):
        return []


class FakePackage(object):
    isNull = False
    upm = 1000
    tfn, path = u"Fake Sans", u"fake.vfc"
    ascender_value, descender_value = 750.0, -250.0

    def __init__(self, glyphs, kerning, masters):
        self.glyphs, self.kernings, self.masters = glyphs, kerning, list(masters)
        self.master, self.mastersCount, self.glyphsCount = masters[0], len(masters), len(glyphs)
        self.fgPackage = Anything()
        self.fgPackage.glyphs = [glyph.fgGlyph for glyph in glyphs]
        self.fgPackage.id = 1

    def findName(self, name):
        return next((glyph for glyph in self.glyphs if glyph.name == name), None)

    def kerning(self, master):
        return FakeKerning(self.kernings.get(master, {}))

    def currentHistoryState(self):
        return 0


def fake_font():
    masters = (u"Regular", u"Bold")
    glyphs = [FakeGlyph(ch, ord(ch), dict((m, FakeLayer(500 + 50 * i)) for i, m in enumerate(masters)))
              for ch in u"HOTnoaehrt .,"]
    glyphs.append(FakeGlyph(u"a.ss01", 0, {u"Regular": FakeLayer(500)}))  # no Bold layer
    return FakePackage(glyphs, {u"Regular": {(u"T", u"o"): -80}, u"Bold": {(u"T", u"o"): -60}}, masters)


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        cls.saved = dict((name, sys.modules.get(name)) for name in ("PythonQt", "fontlab", fp.AUTO_KERNING_MODULE))
        qt = Anything()
        qt.QtCore, qt.QtGui = _FakeQtModule(), _FakeQtModule()
        cls.workspace = workspace = Anything()
        fontlab = Anything()
        fontlab.flWorkspace = Anything()
        fontlab.flWorkspace.instance = lambda: workspace
        fontlab.flPackage = lambda item: item  # (FontLab's wrapper of an open font: its number read through it)
        sys.modules["PythonQt"], sys.modules["fontlab"] = qt, fontlab
        cls.ak_layer_path, cls.ak_stamp = ak.layer_path, getattr(ak, "_freelab_stamp", "unset")
        ak.layer_path = lambda layer: Anything()
        ak._freelab_stamp = None  # (load_auto_kerning finds no file beside the script: the one loaded here is kept)
        sys.modules[fp.AUTO_KERNING_MODULE] = ak
        cls.ak = ak
        # The settings kept between sessions: never this machine's own file (read, or written, by a test)
        cls.settings, cls.written = {}, []
        cls.settings_functions = fp.read_settings, fp.write_settings
        fp.read_settings = lambda ak: dict(cls.settings)
        fp.write_settings = lambda ak, data: cls.written.append(dict(data))

    @classmethod
    def tearDownClass(cls):
        fp.read_settings, fp.write_settings = cls.settings_functions
        cls.ak.layer_path = cls.ak_layer_path
        if cls.ak_stamp == "unset":
            del cls.ak._freelab_stamp
        else:
            cls.ak._freelab_stamp = cls.ak_stamp
        for name, module in cls.saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def dialog(self, package):
        self.workspace.packages = lambda: [package] if package is not None else []
        self.workspace.currentPackage = package
        dialog = fp.ProofDialog()
        self.assertIsNone(dialog.failed, dialog.failed)
        dialog.log.add = lambda text, level="info": self.fail(text) if level == "error" else None
        return dialog

    def test_a_proof_of_each_master(self):
        dialog = self.dialog(fake_font())
        dialog.languages = []  # (no language data: the font's letters stand in)
        dialog.rebuild()
        self.assertIsNotNone(dialog.proof)
        self.assertEqual(dialog.proof.masters, [u"Regular"])
        self.assertEqual(dialog.proof.kerned, [1])
        dialog.masters_box.currentIndex = 1
        dialog.rebuild()
        self.assertEqual(dialog.proof.masters, [u"Regular", u"Bold"])
        self.assertEqual(dialog.proof.kerned, [1, 1])
        self.assertFalse(dialog.fonts[u"Bold"].has(u"a.ss01"), "no Bold layer")
        self.assertEqual(dialog.fonts[u"Bold"].width(u"H"), 550)
        dialog.page_list.currentRow = 0
        dialog.show_page()
        dialog.history_moved()
        self.assertEqual(dialog.proof.masters, [u"Regular", u"Bold"])

    def test_a_page_of_one_master_names_it_in_parentheses(self):
        dialog = self.dialog(fake_font())
        dialog.languages = []
        dialog.masters_box.currentIndex = 1
        dialog.rebuild()

        class Page(object):
            def __init__(self, sections, master):
                self.sections, self.master = sections, master

        dialog.proof.pages = [Page(["about"], fp.ALL_MASTERS), Page(["text", "kerning"], u"Regular"), Page(["text"], u"Bold")]
        listed = []
        dialog.page_list.addItem = listed.append
        dialog.fill_pages()
        text, kerning = fp.TITLES["text"], fp.TITLES["kerning"]
        self.assertEqual(listed, [u"1   %s" % fp.TITLES["about"], u"2   %s, %s (Regular)" % (text, kerning),
                                  u"3   %s (Bold)" % text], "data beside data: parentheses, no dash, no period")

    def test_no_dash_or_dot_between_data(self):
        # The owner's rule: data beside data goes in parentheses, not after an interpunct or an em dash
        import io
        with io.open(fp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read()
        escaped = [u" \\" + code + u" " for code in (u"N{EM DASH}", u"N{MIDDLE DOT}", u"u2014", u"u00b7", u"xb7")]
        for mark in escaped + [u" \N{EM DASH} ", u" \N{MIDDLE DOT} "]:
            self.assertNotIn(mark, source)

    def test_common_pairs_and_defaults(self):
        dialog = self.dialog(fake_font())
        dialog.languages = []
        dialog.pairs_box.currentIndex = 1
        dialog.common = {u"To": 0}
        dialog.rebuild()
        self.assertEqual(dialog.proof.kerned, [1])
        dialog.common = {u"Ta": 0}
        dialog.rebuild()
        self.assertEqual(dialog.proof.kerned, [0])
        self.assertTrue(dialog.defaults_changed())

    def test_no_font_open(self):
        dialog = self.dialog(None)
        dialog.rebuild()
        self.assertIsNone(dialog.proof)
        dialog.save_pdf()
        dialog.show_in_glyph_window()

    def test_a_setting_saved_changes_only_its_own_key(self):
        # Two Proof windows (two fonts) each read proof.json once: the second to save wrote back the first's
        # other setting as it had read it
        type(self).settings = {}
        try:
            dialog = self.dialog(fake_font())
            type(self).settings = {"summary": True, "summary_languages": "reach", "later": 1}  # another window's since
            dialog.summary_box.setChecked(False)
            del self.written[:]
            dialog.summary_changed("summary")
            self.assertEqual(self.written[-1], {"summary": False, "summary_languages": "reach", "later": 1})
            type(self).settings = {"summary": True, "summary_languages": "reach"}
            dialog.summary_changed("summary_languages")
            self.assertEqual(self.written[-1], {"summary": True, "summary_languages": fp.SUMMARY_LANGUAGES[0][0]})
            self.assertEqual(dialog.settings, self.written[-1], "the window holds what it wrote")
        finally:
            type(self).settings = {}

    def test_the_font_info_page_and_the_colors(self):
        dialog = self.dialog(fake_font())
        dialog.languages = []
        dialog.rebuild()
        self.assertEqual(dialog.proof.pages[0].sections[:2], ["about", "info"])
        self.assertIn((u"Font name", u"Fake Sans"), dialog.info, "(FontLab's info a fake here: the package's own)")
        self.assertIn((u"Masters", u"Regular, Bold (2)"), dialog.info)
        self.assertEqual(dialog.color_mode(), "window")
        self.assertEqual([len(rgb) for rgb in dialog.colors()], [3, 3], "the fake palette's colors")
        dialog.colors_box.currentIndex = 1
        self.assertEqual(dialog.color_mode(), "print")
        self.assertEqual(dialog.colors(), fp.PRINT_COLORS)
        self.assertTrue(dialog.defaults_changed())
        dialog.show_page()

    def test_a_pdf_moved_away_is_said_once_and_its_button_grays_out(self):
        dialog = self.dialog(fake_font())
        said = []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        states, enable = [], dialog.ak.enable
        dialog.ak.enable = lambda button, on: states.append((button, on))
        try:
            dialog.saved = os.path.join(HERE, u"no such proof.pdf")
            dialog.open_pdf()
        finally:
            dialog.ak.enable = enable
        self.assertEqual(len(said), 1)
        self.assertEqual(said[0][0], "warning")
        self.assertIn(u"not there anymore", said[0][1])
        self.assertIn((dialog.open_button, False), states)
        dialog.update_buttons()
        self.assertEqual(len(said), 1, "said once")
        dialog.saved = os.path.abspath(__file__)
        self.assertTrue(dialog.saved_there())

    # -- on widgets that remember what they are told ----------------------------------------------

    def remembering(self, package, settings=None, font_check_module=True):
        """A dialog whose widgets remember their texts, rows, and states; (dialog, the Qt module's widgets).
        Font Check is the repository's own (the scripts are not installed side by side here)."""
        qt = sys.modules["PythonQt"]
        plain, made = qt.QtGui, _RememberingQtModule()
        type(self).settings = dict(settings or {})
        del self.written[:]
        qt.QtGui = made
        try:
            dialog = self.dialog(package)
        finally:
            qt.QtGui = plain
            type(self).settings = {}
        self.said = []
        dialog.log.add = lambda text, level="info": self.fail(text) if level == "error" else self.said.append((level, text))
        if font_check_module:
            dialog.font_check = font_check
        dialog.languages = fp.load_languages(LANGUAGES_FILE)
        return dialog, made.made

    def test_every_control_has_a_help_text_of_its_own(self):
        # The owner found, in another tool, a control whose right-click help was its neighbor's
        dialog, made = self.remembering(fake_font())
        dialog.rebuild()
        controls = [widget for widget in made if widget.kind in CONTROLS]
        kinds = set(widget.kind for widget in controls)
        for kind in ("QPushButton", "QCheckBox", "QComboBox", "QLineEdit", "QListWidget"):
            self.assertIn(kind, kinds)
        self.assertGreaterEqual(len(controls), 5 + 1 + 8 + 6 + 2)
        for widget in controls:
            self.assertTrue((u"%s" % widget.whats).strip(), "%s %r has no What's This" % (widget.kind, getattr(widget, "text", u"")))
        texts = [u"%s" % widget.whats for widget in controls]
        self.assertEqual(len(set(texts)), len(texts), "two controls with one help text: %r" % sorted(
            text for text in set(texts) if texts.count(text) > 1))
        named = {"masters": dialog.masters_box, "page": dialog.page_box, "pairs": dialog.pairs_box,
                 "scope": dialog.scope_box, "colors": dialog.colors_box, "languages": dialog.languages_box,
                 "waterfall": dialog.waterfall_edit, "text": dialog.text_edit}
        self.assertEqual(sorted(dialog.captions), sorted(named))
        for name, control in named.items():
            self.assertEqual(dialog.captions[name].whats, control.whats, "%s: its caption answers for it" % name)
            self.assertEqual(dialog.captions[name].kind, "QLabel")
        labels = [widget for widget in made if widget.kind == "QLabel" and widget.captioned and widget.text]
        self.assertEqual(sorted(label.text for label in labels), sorted(label.text for label in dialog.captions.values()),
                         "no caption without its control's help")
        for box in [dialog.summary_box, dialog.close_button, dialog.page_list] + list(dialog.section_boxes.values()):
            self.assertIn(box, controls)

    def test_the_summary_is_the_first_page_and_is_listed_as_summary(self):
        package = fake_font()
        package.fgPackage.features = FakeFeatures([(u"liga", u"sub f i by f_i;"), (u"kern", u"pos T o -80;"),
                                                   (u"ss01", u'featureNames { name "Round a"; };\nsub a by a.ss01;')])
        dialog, made = self.remembering(package)
        self.assertTrue(dialog.summary_box.isChecked(), "on to start with")
        reads = []
        read = dialog.read_coverage
        dialog.read_coverage = lambda fc: reads.append(1) or read(fc)
        dialog.rebuild()
        self.assertEqual(dialog.proof.pages[0].sections[0], "summary")
        self.assertNotIn("about", dialog.proof.section_pages())
        self.assertIn("info", dialog.proof.section_pages(), "the font's info follows")
        self.assertTrue(dialog.page_list.rows[0].startswith(u"1   Summary"), dialog.page_list.rows[0])
        texts = summary_texts(dialog.proof)
        self.assertIn(u"Fake Sans", texts)
        self.assertIn(u"Regular (the font's other master: Bold)", texts)
        self.assertIn(u"14 glyphs (13 encoded characters)", texts)
        self.assertIn(u"1 kerned pair in master Regular, classes resolved (0 entries, 0 classes)", texts)
        self.assertIn(u"Vertical metrics", texts)
        self.assertIn(u"Master Regular", texts)
        self.assertIn(u"Language coverage", summary_texts(dialog.proof, "coverage"))
        features = [text for text in texts if text.startswith(u"3 features: liga (Standard Ligatures), kern (Kerning), ss01")]
        self.assertEqual(len(features), 1)
        # a stylistic set's own name, as Feature Code reads it from the set's code (the scripts are not
        # side by side here: Feature Code is handed over as the installed copy would be found)
        folder = os.path.join(HERE, os.pardir, "features")
        if folder not in sys.path:
            sys.path.insert(0, folder)
        import freelab_feature_code
        load = dialog.ak.load_sibling
        dialog.ak.load_sibling = lambda file_name, module_name: (
            freelab_feature_code if module_name == fp.FEATURE_CODE_MODULE else load(file_name, module_name))
        try:
            self.assertEqual(dialog.read_features(), [(u"liga", u""), (u"kern", u""), (u"ss01", u"Round a")])
        finally:
            dialog.ak.load_sibling = load
        self.assertEqual(fp.features_text([(u"ss01", u"Round a")]), u"1 feature: ss01 (Stylistic Set 1: Round a)")
        self.assertIn(u"summary 1", dialog.font_label.text)
        self.assertEqual(self.said, [], "nothing left out")
        # once per font read: not per layout, not as a page is drawn
        dialog.rebuild()
        dialog.show_page()
        dialog.languages_box.setCurrentIndex(2)
        dialog.rebuild()
        self.assertEqual(len(reads), 1)
        self.assertNotIn(u"Latin, covered", u" ".join(summary_texts(dialog.proof)), "counts only")
        dialog.history_moved()
        self.assertEqual(len(reads), 2, "read again once the font changed")
        # a scope limits the proof, not what the summary says of the font
        dialog.scopes = [None, ("script", u"LATIN")]
        dialog.scope_box.setCurrentIndex(1)
        dialog.scopes_font = dialog.ak.font_key(dialog.package)
        dialog.rebuild()
        texts = summary_texts(dialog.proof)
        self.assertIn(u"Latin only", texts)
        self.assertIn(u"14 glyphs (13 encoded characters)", texts)
        # off: the about block, as before
        dialog.summary_box.setChecked(False)
        dialog.rebuild()
        self.assertEqual(dialog.proof.pages[0].sections[:2], ["about", "info"])
        self.assertEqual(len(reads), 2, "nothing read for a page not made")

    def test_without_font_check_the_summary_leaves_coverage_out_and_says_why_once(self):
        dialog, made = self.remembering(fake_font(), font_check_module=False)

        def missing():
            raise IOError("no freelab_font_check.py")

        dialog.font_check = missing
        dialog.rebuild()
        self.assertIsNotNone(dialog.proof, "the proof is made all the same")
        self.assertEqual(dialog.proof.pages[0].sections[0], "summary")
        texts = summary_texts(dialog.proof)
        self.assertNotIn(u"Language coverage", texts)
        self.assertNotIn(u"Vertical metrics", texts)
        self.assertIn(u"OpenType", texts, "what Proof reads itself stays")
        warnings = [text for level, text in self.said if level == "warning" and u"Font Check" in text]
        self.assertEqual(len(warnings), 1)
        self.assertIn(u"leaves the languages the font covers and its vertical metrics out", warnings[0])
        dialog.history_moved()
        self.assertEqual(len([text for level, text in self.said if u"Font Check" in text]), 1, "said once")
        # its data unreadable: the same, for the languages alone
        dialog, made = self.remembering(fake_font())
        broken = font_check()

        class Broken(object):
            def __getattr__(self, name):
                if name == "load_languages":
                    return lambda *args: (_ for _ in ()).throw(IOError("language_coverage.json"))
                return getattr(broken, name)

        dialog.font_check = lambda: Broken()
        dialog.rebuild()
        texts = summary_texts(dialog.proof)
        self.assertNotIn(u"Language coverage", texts)
        self.assertIn(u"Vertical metrics", texts)
        self.assertEqual(len([text for level, text in self.said if u"language data could not be read" in text]), 1)

    def test_the_summary_settings_are_remembered(self):
        dialog, made = self.remembering(fake_font())
        self.assertTrue(dialog.summary_box.isChecked())
        dialog.summary_box.setChecked(False)
        dialog.languages_box.setCurrentIndex(1)
        dialog.summary_changed()
        self.assertEqual(self.written[-1], {"summary": False, "summary_languages": "reach"})
        self.assertTrue(dialog.defaults_changed())
        dialog, made = self.remembering(fake_font(), {"summary": False, "summary_languages": "none"})
        self.assertFalse(dialog.summary_box.isChecked(), "as it was left")
        self.assertEqual(dialog.languages_box.currentIndex, 2)
        self.assertEqual(dialog.languages_box.rows, [label for _, label in fp.SUMMARY_LANGUAGES])
        dialog, made = self.remembering(fake_font(), {"summary_languages": "no such choice"})
        self.assertTrue(dialog.summary_box.isChecked())
        dialog.restore_defaults()
        self.assertTrue(dialog.summary_box.isChecked())
        self.assertEqual(dialog.languages_box.currentIndex, 0)

    def test_the_proof_dropdown_lists_every_language_the_most_spoken_first(self):
        # The owner, of More languages...: "Works, but why not have them reachable by default?" Every
        # dropdown now opens as a list of 24 rows, scrolled, and typing a name's first letters finds it.
        glyphs = [FakeGlyph(fp.char_of(code), code, {u"Regular": FakeLayer(500)}) for code in LATIN_1_A]
        dialog, made = self.remembering(FakePackage(glyphs, {}, (u"Regular",)))
        dialog.rebuild()
        rows, scopes = dialog.scope_box.rows, dialog.scopes
        self.assertEqual(len(rows), len(scopes))
        self.assertEqual(rows[:3], [u"Every script", u"Latin only", None])
        self.assertEqual(rows[3:5], [u"Spanish (Latin)", u"English (Latin)"], "by Hyperglot's speakers, as before")
        self.assertNotIn(fp.MORE_LANGUAGES, rows, "nothing held back")
        covered = len(dialog.scope_languages)
        self.assertGreater(covered, 100)
        self.assertEqual(len([row for row in rows if row is not None]), 2 + covered, "every covered language")
        self.assertEqual(rows.count(None), 2)
        rest = rows[3 + fp.SCOPE_LANGUAGES_TOP + 1:]
        self.assertEqual(rest, sorted(rest, key=lambda text: text.lower()), "the others A to Z")
        self.assertIn(u"come first, then the other %d, A to Z" % (covered - fp.SCOPE_LANGUAGES_TOP),
                      dialog.scope_box.whats)
        self.assertEqual(dialog.captions["scope"].whats, dialog.scope_box.whats)
        dialog.scope_box.setCurrentIndex(len(rows) - 1)  # one of the others, picked at once
        dialog.scope_chosen(len(rows) - 1)
        self.assertEqual(fp.scope_label(dialog.scope_kept), rows[-1])
        dialog.rebuild()
        self.assertIn(rows[-1], summary_texts(dialog.proof), "the summary names the scope")
        self.assertTrue(dialog.defaults_changed())
        dialog.restore_defaults()
        dialog.rebuild()
        self.assertEqual(dialog.scope_box.currentIndex, 0)
        self.assertNotIn(fp.MORE_LANGUAGES, dialog.scope_box.rows)
        self.assertFalse(dialog.defaults_changed())


if __name__ == "__main__":
    unittest.main()
