"""Tests of FreeLab's CJK Spacing (palt and halt trims, and their feature code). Valid Python 2.7 and
Python 3."""

from __future__ import absolute_import, division, print_function

import io
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
        def picked(codes, family=u"", pages=()):
            return cj.SAMPLES[cj.best_sample(codes, family, pages)][0]
        self.assertEqual(picked(kana | codes_of("ja")), "ja")
        self.assertEqual(picked(hangul | kana | codes_of("ja")), "ko", "a Korean font with kana: Korean")
        self.assertEqual(picked(han | kana | codes_of("ja"), u"Noto Sans SC"), "zh-hans",
                         "a Chinese font with kana: its name says Chinese")
        self.assertEqual(picked(codes_of("zh-hant")), "zh-hant")

    def test_the_sample_in_the_fonts_own_writing(self):
        """The owner: IBM Plex Sans JP was shown the Traditional Chinese sample (it covers it as fully as the
        Iroha, and has more kanji than kana). The font's own writing wins; coverage decides only between
        the two Chinese samples, or where nothing else says."""
        def codes_of(*keys):
            return set(ord(ch) for key in keys for ch in self.sample(key))

        def picked(codes, family=u"", pages=()):
            return cj.SAMPLES[cj.best_sample(codes, family, pages)][0]
        kana = set(range(0x3041, 0x3097)) | set(range(0x30A1, 0x30FB)) | set(range(0xFF61, 0xFFA0))
        kanji = set(range(0x4E00, 0x4E00 + 6000)) | codes_of("zh-hant", "zh-hans")
        hangul = set(range(0xAC00, 0xD7A4)) | codes_of("ko")
        hanja = set(range(0x4E00, 0x4E00 + 4000)) | codes_of("zh-hant")
        simplified, traditional = codes_of("zh-hans"), codes_of("zh-hant")
        self.assertEqual(picked(kana | kanji | codes_of("ja")), "ja", "kana and kanji: Japanese")
        self.assertEqual(picked(kana | kanji | codes_of("ja"), u"IBM Plex Sans JP", (0, 2, 17, 29)), "ja",
                         "IBM Plex Sans JP, as FontLab reads it")
        self.assertEqual(picked(hangul | hanja), "ko", "Hangul and hanja: Korean")
        self.assertEqual(picked(hangul | hanja | kana | codes_of("ja")), "ko", "KS X 1001 has kana too")
        self.assertEqual(picked(simplified | set(range(0x4E00, 0x4E00 + 3000))), "zh-hans", "Simplified only")
        self.assertEqual(picked(traditional | set(range(0x4E00, 0x4E00 + 3000))), "zh-hant", "Traditional only")
        both = kana | kanji | codes_of("ja")  # (a Chinese font has kana too: GB 2312, Big5)
        self.assertEqual(picked(both, u"Noto Sans TC"), "zh-hant", "its name")
        self.assertEqual(picked(both, u"LXGW WenKai TC"), "zh-hant")
        self.assertEqual(picked(both, u"WDXL Lubrifont SC"), "zh-hans")
        self.assertEqual(picked(both, u"Some Ming", (18,)), "zh-hans", "one code page bit, no name")
        self.assertEqual(picked(both, u"Some Ming", (20,)), "zh-hant")
        self.assertEqual(picked(both, u"Zen Kaku Gothic New", (17, 20)), "ja", "two bits say nothing: its kana")
        self.assertEqual(picked(simplified | traditional), "zh-hans", "both Chinese samples covered alike: the first")
        self.assertEqual(picked(codes_of("ja") - kana | set(range(0x3000, 0x3020)), u"Amatic SC"),
                         picked(codes_of("ja") - kana | set(range(0x3000, 0x3020))),
                         "a name's word (small caps) never picks a sample the font hardly covers")
        self.assertEqual(cj.writing_hints(u"Noto Sans JP", (17, 18)), ["ja"])
        self.assertEqual(cj.writing_hints(u"", (17, 18)), [], "two writings: no hint")
        self.assertEqual(cj.writing_hints(u"Source Han Sans K", (19,)), ["ko"])

    def test_font_hints_read_from_fontlab(self):
        info = type("Info", (), {"openTypeNamePreferredFamilyName": None, "familyName": u"IBM Plex Sans JP",
                                 "openTypeOS2CodePageRanges": [0, 2, 17, 29]})()
        package = type("Package", (), {"fgPackage": type("Fg", (), {"info": info})(), "tfn": u"x"})()
        self.assertEqual(cj.font_hints(package), (u"IBM Plex Sans JP", (0, 2, 17, 29)))
        self.assertEqual(cj.font_hints(object()), (u"", ()))
        source = io.open(os.path.join(HERE, os.pardir, "cjk", "freelab_cjk_vertical.py"), encoding="utf-8").read()
        self.assertIn(u"best_sample(set(self.char_names), *self.cj.font_hints(package))", source, "CJK Vertical too")


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

    def test_ranges_are_spelled_out_and_pair_rules_are_not_single_values(self):
        text = u"""feature palt {
  @KANA = [uni3041-uni3043];
  @PUNCT = [uni3001];
  pos @KANA <-10 0 -20 0>;
  enum pos @PUNCT @KANA -40;
  pos [cid00010-cid00011] <-1 0 -2 0>;
} palt;"""
        self.assertEqual(sorted(cj.font_positioned("palt", text)),
                         [u"cid00010", u"cid00011", u"uni3041", u"uni3042", u"uni3043"], "uni3001 is only in a pair rule")


class CodePointTests(unittest.TestCase):
    def test_a_glyph_encoded_twice_is_found_at_both(self):
        """IBM Plex Sans JP encodes the ideograph sun at U+2F47 (its Kangxi radical) and U+65E5; FontLab's
        unicode gives the first, so the Chinese sample left it out."""
        glyph = type("G", (), {"name": "uni65E5", "unicode": 0x2F47, "unicodes": [0x2F47, 0x65E5]})()
        self.assertEqual(cj.all_codes([glyph]), {0x2F47: u"uni65E5", 0x65E5: u"uni65E5"})


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


class NoFontTests(unittest.TestCase):
    """The owner: audit "what currently remains clickable or visible when there's nothing loaded"."""

    class Widget(object):
        def __init__(self):
            self.visible = self.enabled = True

        def setVisible(self, on):
            self.visible = on

        def setEnabled(self, on):
            self.enabled = on

    def test_with_no_font_the_sample_and_previews_are_hidden_and_the_settings_grayed(self):
        dialog = cj.CJKSpacingDialog.__new__(cj.CJKSpacingDialog)  # (its window needs FontLab)
        dialog.ak = type("Ak", (), {"enable": staticmethod(lambda widget, on: widget.setEnabled(bool(on)))})  # (ak.enable)
        widget = self.Widget
        dialog.sample_label, dialog.sample_box, dialog.sample = widget(), widget(), widget()
        dialog.preview_captions = [widget(), widget()]
        dialog.previews = [(widget(), u"Now"), (widget(), u"With palt")]
        dialog.palt_box, dialog.halt_box, dialog.compile_box, dialog.hangul_box = widget(), widget(), widget(), widget()
        dialog.show_font_parts(False)
        shown = [dialog.sample_label, dialog.sample_box, dialog.sample] + dialog.preview_captions + [p for p, _ in dialog.previews]
        self.assertFalse(any(w.visible for w in shown), "nothing to set a sample in")
        self.assertFalse(any(w.enabled for w in (dialog.palt_box, dialog.halt_box, dialog.compile_box, dialog.hangul_box)))
        dialog.show_font_parts(True)
        self.assertTrue(all(w.visible for w in shown))
        self.assertTrue(all(w.enabled for w in (dialog.palt_box, dialog.halt_box, dialog.compile_box)))
        self.assertFalse(dialog.hangul_box.enabled, "the font's Hangul sets it as it is read")
        runs = []
        dialog.run = lambda: runs.append(1)
        dialog.font_changed()
        self.assertEqual(runs, [1], "a font closed or opened: read anew")


class WordingTests(unittest.TestCase):
    """The owner's rules for interface texts: a text with a number follows it, and data beside data
    goes in parentheses."""

    def test_the_hangul_sentence_follows_its_count(self):
        self.assertEqual(cj.hangul_note(0, u"Hangul:"), u"")
        one, two = cj.hangul_note(1, u"Hangul:"), cj.hangul_note(2, u"Hangul:", lambda text: u"<b>%s</b>" % text)
        self.assertTrue(one.startswith(u" Its 1 Hangul syllable: "), one)
        self.assertTrue(one.endswith(u"choose how to set its width under Hangul:."), one)
        self.assertTrue(two.startswith(u" Its <b>2 Hangul syllables</b>: "), two)
        self.assertTrue(two.endswith(u"choose how to set their widths under Hangul:."), two)

    def test_counted(self):
        self.assertEqual([cj.counted(n, u"unit") for n in (0, 1, 2)], [u"0 units", u"1 unit", u"2 units"])
        self.assertEqual([cj.counted_chars(n) for n in (0, 1, 2)],
                         [u"0 CJK characters", u"1 CJK character", u"2 CJK characters"])

    def test_no_dash_or_dot_between_data(self):
        import io
        with io.open(cj.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read()
        escaped = [u" \\" + code + u" " for code in (u"N{EM DASH}", u"N{MIDDLE DOT}", u"u2014", u"u00b7", u"xb7")]
        for mark in escaped + [u" \N{EM DASH} ", u" \N{MIDDLE DOT} "]:
            self.assertNotIn(mark, source)
        self.assertNotIn(u"%d units", source, "a number's word through counted: 1 unit")


if __name__ == "__main__":
    unittest.main()
