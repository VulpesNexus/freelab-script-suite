"""Tests of FreeLab's CJK Spacing (palt and halt trims, and their feature code). Valid Python 2.7 and
Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "cjk"))
import freelab_cjk_spacing as cj  # noqa: E402

MODEL = {"format": 1, "palt": {"hiragana": [0.08, 0.06], "punctuation": [0.07, 0.07], "U+3001": [0.05, 0.19]},
         "halt": {"U+3001": [0.0, -0.5], "U+300C": [-0.5, -0.5]}}


class TrimTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(cj.kind_of(0x3042), "hiragana")
        self.assertEqual(cj.kind_of(0x3041), "small hiragana")
        self.assertEqual(cj.kind_of(0x30AB), "katakana")
        self.assertEqual(cj.kind_of(0x3001), "punctuation")
        self.assertEqual(cj.kind_of(0xFF08), "punctuation")
        self.assertEqual(cj.kind_of(0xAC00), "hangul")
        self.assertIsNone(cj.kind_of(0x4E00), "kanji stay full width")

    def test_kana_trimmed_to_its_ink_and_the_corpus_sides(self):
        trim = cj.suggest(cj.Trim(0x3042, "a-hira", "hiragana", 1000, 150, 880), MODEL, 1000.0)
        self.assertEqual(trim.palt, (80 - 150, 730 + 140 - 1000), "the ink moves left to 80, the width becomes 870")
        self.assertEqual(trim.width_after(), 870)
        self.assertIsNone(trim.halt, "halt is for punctuation")

    def test_punctuation_takes_its_own_sides_and_half_width(self):
        comma = cj.suggest(cj.Trim(0x3001, "ideographiccomma", "punctuation", 1000, 100, 300), MODEL, 1000.0)
        self.assertEqual(comma.palt, (-50, 200 + 240 - 1000))
        self.assertEqual(comma.halt, (0, -500))

    def test_proportional_glyphs_and_tiny_trims_are_left_alone(self):
        narrow = cj.suggest(cj.Trim(0x3042, "a-hira", "hiragana", 600, 50, 550), MODEL, 1000.0)
        self.assertIsNone(narrow.palt, "narrower than 90% of the em: proportional already")
        tight = cj.suggest(cj.Trim(0x3042, "a-hira", "hiragana", 1000, 81, 941), MODEL, 1000.0)
        self.assertIsNone(tight.palt, "within the tolerance on both sides")

    def test_plan_lists_only_what_changes(self):
        glyphs = [(0x3042, "a-hira", 1000, 150, 880), (0x4E00, "uni4E00", 1000, 50, 950), (0xAC00, "ga-ko", 1000, 50, 950)]
        self.assertEqual([t.name for t in cj.plan(glyphs, MODEL, 1000.0)], ["a-hira"], "kanji and Hangul stay")


class HangulTests(unittest.TestCase):
    MODEL = {"fixed_width": 0.9, "proportional": {"vertical": [0.03, 0.055], "horizontal": [0.0275, 0.025]}}

    def test_shapes(self):
        self.assertEqual(cj.hangul_shape(0xAC00), "vertical", "ga: its vowel beside")
        self.assertEqual(cj.hangul_shape(0xAC01), "vertical final")
        self.assertEqual(cj.hangul_shape(0xACE0), "horizontal", "go: its vowel under")
        self.assertEqual(cj.hangul_shape(0xACFC), "mixed", "gwa: beside and under")
        self.assertEqual(cj.hangul_shape(0xD7A3), "vertical final", "the last syllable, hih")

    def test_one_width_centers_the_ink(self):
        change = cj.hangul_change(0xAC00, "ga", 1000, 100, 860, "fixed", self.MODEL, 1000.0)
        self.assertEqual((change.advance, change.shift), (900, 70 - 100), "900 wide, its 760 units of ink centered")
        same = cj.hangul_change(0xAC00, "ga", 920, 80, 840, "fixed", self.MODEL, 1000.0, width=920)
        self.assertIsNone(same, "the font's own width, centered already")

    def test_proportional_by_shape(self):
        change = cj.hangul_change(0xACE0, "go", 1000, 100, 860, "proportional", self.MODEL, 1000.0)
        self.assertEqual((change.shift, change.advance), (-72, 813), "27.5 and 812.5, rounded half up")
        self.assertIsNone(cj.hangul_change(0xACFC, "gwa", 1000, 100, 860, "proportional", self.MODEL, 1000.0),
                          "a shape the model lacks")
        self.assertIsNone(cj.hangul_change(0xAC00, "ga", 1000, 100, 860, "leave", self.MODEL, 1000.0))


class CodeTests(unittest.TestCase):
    def trims(self):
        a = cj.suggest(cj.Trim(0x3042, "a-hira", "hiragana", 1000, 150, 880), MODEL, 1000.0)
        comma = cj.suggest(cj.Trim(0x3001, "ideographiccomma", "punctuation", 1000, 100, 300), MODEL, 1000.0)
        return [a, comma]

    def test_new_features(self):
        texts = cj.texts_for(self.trims(), {})
        self.assertIn(u"feature palt {", texts["palt"])
        self.assertIn(u"  pos a-hira <-70 0 -130 0>;", texts["palt"])
        self.assertIn(u"  pos ideographiccomma <0 0 -500 0>;", texts["halt"])
        self.assertTrue(texts["palt"].rstrip().endswith(u"} palt;"))

    def test_the_rest_is_kept_and_an_old_block_replaced(self):
        old = (u"feature palt {\n#> feature\n  pos x <1 0 2 0>;\n#< feature\n" + cj.BEGIN % "palt" + u"\n  pos old <1 0 1 0>;\n"
               + cj.END % "palt" + u"\n} palt;\n")
        trims = self.trims()
        trims[1].checked = False
        text = cj.texts_for(trims, {"palt": old}, halt_on=False)["palt"]
        self.assertNotIn(u"pos old", text)
        self.assertIn(u"#/> feature", text, "FontLab's automatic block handed back")
        self.assertIn(u"pos x <1 0 2 0>;", text)
        self.assertNotIn(u"ideographiccomma", text, "unchecked")
        self.assertEqual(text.count(cj.BEGIN % "palt"), 1)
        block = cj.block_of("palt", text)
        self.assertEqual(block, u"feature palt {\n  pos a-hira <-70 0 -130 0>;\n} palt;\n")


class SampleTests(unittest.TestCase):
    def sample(self, key):
        return dict((k, text) for k, _, text in cj.SAMPLES)[key]

    def test_the_iroha_has_every_kana_once(self):
        kana = [ch for ch in self.sample("ja") if 0x3041 <= ord(ch) <= 0x3096]
        inside = self.sample("ja").split(u"\N{RIGHT CORNER BRACKET}")[0]
        poem = [ch for ch in inside if 0x3041 <= ord(ch) <= 0x3096]
        self.assertEqual(len(poem), 47)
        self.assertEqual(len(set(poem)), 47, "each kana once")
        self.assertTrue(set(kana) >= set(poem))
        for mark in u"\N{LEFT CORNER BRACKET}\N{RIGHT CORNER BRACKET}\N{IDEOGRAPHIC COMMA}\N{IDEOGRAPHIC FULL STOP}" \
                    u"\N{FULLWIDTH LEFT PARENTHESIS}\N{FULLWIDTH RIGHT PARENTHESIS}":
            self.assertIn(mark, self.sample("ja"), "palt's punctuation shows")

    def test_the_hangul_pangram_has_every_basic_jamo(self):
        import unicodedata
        found = set()
        for ch in self.sample("ko"):
            index = ord(ch) - 0xAC00
            if 0 <= index < 11172:
                found.add(unicodedata.name(cj.unichr_(0x1100 + index // 588)).split()[-1])
                found.add(unicodedata.name(cj.unichr_(0x1161 + index % 588 // 28)).split()[-1])
                if index % 28:
                    found.add(unicodedata.name(cj.unichr_(0x11A7 + index % 28)).split()[-1])
        basic = (u"KIYEOK NIEUN TIKEUT RIEUL MIEUM PIEUP SIOS IEUNG CIEUC CHIEUCH KHIEUKH THIEUTH PHIEUPH HIEUH "
                 u"A YA EO YEO O YO U YU EU I").split()
        self.assertEqual([name for name in basic if name not in found], [])

    def test_the_thousand_character_classic_repeats_no_character(self):
        for key in ("zh-hans", "zh-hant"):
            text = self.sample(key)
            han = [ch for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF]
            self.assertEqual(len(han), 27, key)  # 24 of the poem, and its title
            self.assertEqual(len(set(han)), len(han), key)
            self.assertIn(u"\N{FULLWIDTH COMMA}", text)
        simplified, traditional = self.sample("zh-hans"), self.sample("zh-hant")
        self.assertIn(u"\N{CJK UNIFIED IDEOGRAPH-9EC4}", simplified, "yellow, simplified")
        self.assertIn(u"\N{CJK UNIFIED IDEOGRAPH-9EC3}", traditional, "yellow, traditional")
        self.assertEqual(len(simplified), len(traditional))

    def test_the_sample_a_font_covers_best(self):
        def codes_of(*keys):
            return set(ord(ch) for key in keys for ch in self.sample(key))
        kana = set(range(0x3041, 0x3097)) | set(range(0x30A1, 0x30FB))
        hangul = set(range(0xAC00, 0xAC00 + 3000)) | codes_of("ko")
        han = set(range(0x4E00, 0x4E00 + 5000)) | codes_of("zh-hans")
        self.assertEqual(cj.SAMPLES[cj.best_sample(kana | codes_of("ja"))][0], "ja")
        self.assertEqual(cj.SAMPLES[cj.best_sample(hangul | kana | codes_of("ja"))][0], "ko",
                         "a Korean font with kana: Korean")
        self.assertEqual(cj.SAMPLES[cj.best_sample(han | kana | codes_of("ja"))][0], "zh-hans",
                         "a Chinese font with kana: Chinese")
        self.assertEqual(cj.SAMPLES[cj.best_sample(codes_of("zh-hant"))][0], "zh-hant")


class OwnCodeTests(unittest.TestCase):
    OLD = u"""feature palt {
  pos uni3042 <-10 0 -20 0>;
  pos [uni3044 uni3046] <-5 0 -10 0>;
  pos @kana <0 0 0 0>;
# >>> FreeLab palt (made by FreeLab CJK Spacing)
  pos uni3048 <-1 0 -2 0>;
# <<< FreeLab palt
} palt;"""

    def test_the_fonts_own_single_positions_are_found(self):
        self.assertEqual(sorted(cj.font_positioned("palt", self.OLD)), [u"uni3042", u"uni3044", u"uni3046"],
                         "not FreeLab's block, not an undefined class")

    def test_classes_defined_in_the_code_and_long_forms_are_read(self):
        text = u"""feature palt {
  @KANA = [uni304B uni304D];
  @MORE = [@KANA uni304F];
  position @MORE <-3 0 -6 0>;
  enum pos [uni3051] <-1 0 -2 0>;
} palt;"""
        self.assertEqual(sorted(cj.font_positioned("palt", text)), [u"uni304B", u"uni304D", u"uni304F", u"uni3051"])


class MissTests(unittest.TestCase):
    def test_a_sample_showing_none_of_the_fonts_cjk_characters_names_them(self):
        codes = {0x41, 0x3030, 0x303D, 0x1F600}  # an emoji font: a wavy dash and a part mark
        self.assertEqual(cj.sample_misses(codes, cj.SAMPLE), [cj.unichr_(0x3030), cj.unichr_(0x303D)])

    def test_a_sample_showing_some_says_nothing(self):
        self.assertEqual(cj.sample_misses({0x3044, 0x3030}, cj.SAMPLE), [])

    def test_no_cjk_characters_no_note(self):
        self.assertEqual(cj.sample_misses({0x41, 0x42}, cj.SAMPLE), [])


class LineTests(unittest.TestCase):
    def test_lines_fit_the_room(self):
        chars = list(u"abcdefgh")
        self.assertEqual(cj.break_lines(chars, [10] * 8, 30), [(0, 3), (3, 6), (6, 8)])
        self.assertEqual(cj.break_lines(chars, [10] * 8, 1000), [(0, 8)])
        self.assertEqual(cj.break_lines(chars[:2], [50, 50], 30), [(0, 1), (1, 2)], "too wide alone: alone")

    def test_kinsoku(self):
        text = u"\N{LEFT CORNER BRACKET}\N{HIRAGANA LETTER I}\N{HIRAGANA LETTER RO}\N{IDEOGRAPHIC COMMA}" \
               u"\N{HIRAGANA LETTER HA}\N{HIRAGANA LETTER SMALL TU}\N{HIRAGANA LETTER NI}"
        lines = cj.break_lines(list(text), [10] * len(text), 30)
        starts = [text[start] for start, _ in lines]
        ends = [text[end - 1] for _, end in lines]
        self.assertNotIn(u"\N{IDEOGRAPHIC COMMA}", starts, "no comma first on a line")
        self.assertNotIn(u"\N{HIRAGANA LETTER SMALL TU}", starts, "no small kana first")
        self.assertNotIn(u"\N{LEFT CORNER BRACKET}", ends, "no opening bracket last")
        self.assertEqual(u"".join(text[a:b] for a, b in lines), text)

    def test_korean_breaks_at_spaces(self):
        text = u"\N{HANGUL SYLLABLE GA}\N{HANGUL SYLLABLE NA} \N{HANGUL SYLLABLE DA}\N{HANGUL SYLLABLE RA}" \
               u"\N{HANGUL SYLLABLE MA}"
        lines = cj.break_lines(list(text), [10] * len(text), 40)
        self.assertEqual(lines, [(0, 2), (3, 6)], "after the space, which is dropped")


if __name__ == "__main__":
    unittest.main()
