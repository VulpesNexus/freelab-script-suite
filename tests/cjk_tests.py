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


class LiveFontCodeTests(unittest.TestCase):
    """Live pass (IBM Plex Sans JP, 2026-11-15): every write failed to compile, "Duplicate single positioning
    glyph with different values in feature 'palt': uni3001". The font's palt positions its punctuation by
    "pos @palt -500;", the class defined in the prefix, and its halt by @halt and @halt2: CJK Spacing read
    the features' own text alone and added "pos uni3001 <6 0 -494 0>;". An excerpt of that font's code,
    its rules and classes as FontLab read them (the classes cut to the glyphs used here)."""

    PREFIX = u"""@palt = [angleright uni3001 uni3002 uniFF0C uniFF0E uni309B uni309C uniFF09 uni3015];
@halt = [angleleft uni300A uni300C uniFF08 uni3014];
@halt2 = [angleright uni3001 uni3002 uniFF0C uniFF09 uni3015 uni300B];
lookup HALT_EXTRA {
  pos uniFF5B <-500 0 -500 0>;
} HALT_EXTRA;
"""
    PALT = u"""feature palt {
# GPOS feature: Proportional Alternate Widths
# Lookups: 1

  pos [uni30FB uniFF1A uniFF1B uniFF1F uniFF01] <-250 0 -500 0>;
  pos @palt -500;
  pos uni30FD <-115 0 -250 0>;
  pos [uni3041] <-55 0 -115 0>;
} palt;
"""
    HALT = u"""feature halt {
# GPOS feature: Alternate Half Widths
# Lookups: 5

  script latn; # Latin
  pos @halt <-500 0 -500 0>;
  pos [uni30FB uniFF1A uniFF1B uniFF01] <-250 0 -500 0>;
  pos @halt2 -500;

  script kana; # Hiragana
  pos @halt <-500 0 -500 0>;
  pos [uni30FB uniFF1A uniFF1B uniFF01] <-250 0 -500 0>;
  pos @halt2 -500;
  lookup HALT_EXTRA;
} halt;
"""
    GLYPHS = [u"uni3001", u"uni3002", u"uni3041", u"uni3042", u"uni300C", u"uniFF5B", u"uniFF5D", u"uni30FB"]

    def trims(self):
        found = []
        for name in self.GLYPHS:
            trim = cj.Trim(0x3001, name, "punctuation", 1000, 100, 300)
            trim.palt, trim.halt, trim.checked = (6, -494), (0, -500), True
            found.append(trim)
        return found

    def texts(self, classes=None, lookups=None, kept=None):
        if classes is None:
            classes, lookups = cj.code_classes(self.PREFIX), cj.code_lookups(self.PREFIX)
        return cj.texts_for(self.trims(), {"palt": self.PALT, "halt": self.HALT}, True, True, kept, classes, lookups)

    def written(self, text, tag):
        block = cj.block_of(tag, text) or u""
        return sorted(line.split()[1] for line in block.splitlines() if line.strip().startswith(u"pos "))

    def test_the_prefixs_classes_and_lookups_keep_their_glyphs_out(self):
        kept = {}
        new = self.texts(kept=kept)
        self.assertEqual(self.written(new["palt"], "palt"), sorted([u"uni3042", u"uni300C", u"uniFF5B", u"uniFF5D"]),
                         "uni3001 and uni3002 by @palt, uni3041 by its own rule, uni30FB by a list")
        self.assertEqual(self.written(new["halt"], "halt"), [u"uni3041", u"uni3042", u"uniFF5D"],
                         "@halt, @halt2, the list, and the prefix's lookup HALT_EXTRA")
        self.assertEqual(sorted(kept["palt"]), [u"uni3001", u"uni3002", u"uni3041", u"uni30FB"])

    def test_fontlabs_class_list_counts_too(self):
        package = type("Package", (), {"getAllGroups": lambda self: [(False, u"palt", 0, 0, [u"uni3001", u"uni3002"]),
                                                                      (True, u"kern1", 0, 0, [u"uni3042"])]})()
        classes = cj.font_classes(package, None)
        self.assertEqual(sorted(classes), [u"@palt"], "a kerning class is no feature class")
        self.assertEqual(cj.font_positioned("palt", self.PALT, classes), set(
            [u"uni3001", u"uni3002", u"uni30FB", u"uniFF1A", u"uniFF1B", u"uniFF1F", u"uniFF01", u"uni30FD", u"uni3041"]))
        self.assertEqual(sorted(cj.font_classes(package, self.PREFIX)["@palt"])[:2], [u"angleright", u"uni3001"],
                         "the prefix's own definition read too")

    def test_the_written_code_compiles(self):
        """What CJK Spacing writes, compiled with the font's own code (fontTools' compiler; FontLab's refused
        the second value outright)."""
        try:
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            from fontTools.fontBuilder import FontBuilder
        except ImportError:
            return  # (the Python 2.7 run)
        new = self.texts()
        names = set(self.GLYPHS) | set(cj.code_classes(self.PREFIX)["@palt"] + cj.code_classes(self.PREFIX)["@halt"] +
                                      cj.code_classes(self.PREFIX)["@halt2"])
        names |= set([u"uni30FD", u"uniFF1A", u"uniFF1B", u"uniFF1F", u"uniFF01"])
        order = [u".notdef"] + sorted(names)
        builder = FontBuilder(1000, isTTF=True)
        builder.setupGlyphOrder(order)
        builder.setupCharacterMap({})
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        builder.setupGlyf(dict((name, TTGlyphPen(None).glyph()) for name in order))
        builder.setupHorizontalMetrics(dict((name, (1000, 0)) for name in order))
        builder.setupHorizontalHeader(ascent=880, descent=-120)
        code = u"languagesystem DFLT dflt;\nlanguagesystem latn dflt;\nlanguagesystem kana dflt;\n" + self.PREFIX + \
            new["palt"] + new["halt"]
        addOpenTypeFeaturesFromString(builder.font, code)  # (raises on a second value for one glyph)
        before = self.PALT.replace(u"} palt;", u"  pos uni3001 <6 0 -494 0>;\n} palt;")
        from fontTools.feaLib.error import FeatureLibError
        self.assertRaises(FeatureLibError, addOpenTypeFeaturesFromString, builder.font,
                          u"languagesystem DFLT dflt;\n" + self.PREFIX + before)


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
        self.assertTrue(all(w.enabled for w in (dialog.palt_box, dialog.halt_box)))
        self.assertFalse(dialog.compile_box.enabled, "given back by update_buttons, with the write button (image 195)")
        self.assertFalse(dialog.hangul_box.enabled, "the font's Hangul sets it as it is read")
        runs = []
        dialog.run = lambda: runs.append(1)
        dialog.font_changed()
        self.assertEqual(runs, [1], "a font closed or opened: read anew")


class StaleCodeTests(unittest.TestCase):
    """Review: a write composed palt and halt from the code read with the list, so an edit made since (before
    the History watcher's next look, or one that leaves the History where it was) was replaced. The write
    now compares the font's code with what was read, last, and writes nothing when it differs."""

    USER_PALT = u"feature palt {\n  pos uni3042 <-10 0 -20 0>;\n} palt;\n"

    class Features(object):
        def __init__(self, texts):
            self.texts, self.written = dict(texts), []

        def keys(self):
            return list(self.texts)

        def get_feature(self, tag):
            return self.texts[tag]

        def set_feature(self, tag, text):
            self.written.append(tag)
            self.texts[tag] = text

    def make(self, texts):
        features = self.Features(texts)
        package = type("Package", (), {"fgPackage": type("Fg", (), {"features": features})()})()
        dialog = cj.CJKSpacingDialog.__new__(cj.CJKSpacingDialog)  # (its window needs FontLab)
        dialog.package, dialog.names, dialog.texts = package, ["a-hira", "uni3042"], dict(texts)
        dialog.prefix, dialog.classes, dialog.lookups = None, {}, {}
        dialog.trims = [cj.suggest(cj.Trim(0x3042, "a-hira", "hiragana", 1000, 150, 880), MODEL, 1000.0),
                        cj.suggest(cj.Trim(0x3001, "ideographiccomma", "punctuation", 1000, 100, 300), MODEL, 1000.0)]
        dialog.palt_box = dialog.halt_box = type("Box", (), {"checked": True})()
        dialog.compile_box = dialog.fontlab = None
        self.logged, self.runs, self.history = [], [], []
        dialog.log = type("Log", (), {"add": lambda _, text, kind=None: self.logged.append((kind, text))})()
        raising = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no Feature Code here"))
        dialog.ak = type("Ak", (), dict(
            font_key=staticmethod(lambda p: 1), load_sibling=staticmethod(raising),
            before_changes=staticmethod(lambda *args: self.history.append("before")),
            notify_changed=staticmethod(lambda *args: self.history.append("notify")),
            compiled_note=staticmethod(lambda box, log: u""), b=staticmethod(lambda t: u"%s" % t),
            html=staticmethod(lambda t: u"%s" % t), joined=staticmethod(lambda items: u" and ".join(items)),
            busy_start=staticmethod(lambda owner, what=u"", stoppable=True: self.busy.append(("start", stoppable))),
            busy_progress=staticmethod(lambda owner, what=None, part=None, force=False, stoppable=True:
                                       self.busy.append(("progress", stoppable))),
            busy_end=staticmethod(lambda owner: self.busy.append(("end", None))),
            busy_stopping=staticmethod(lambda owner: False), Stopped=Exception))
        self.busy = []
        dialog.harvest = lambda: None
        dialog.hangul_chosen = lambda: []
        dialog.current_font = lambda: package
        dialog.run = lambda: self.runs.append(1)
        return dialog, features

    def test_an_edit_made_since_the_list_was_read_is_kept(self):
        dialog, features = self.make({"palt": self.USER_PALT})
        edited = features.texts["palt"] = self.USER_PALT.replace(u"} palt;", u"  pos uni3044 <-5 0 -10 0>;\n} palt;")
        dialog.write()
        self.assertEqual(features.written, [], "no feature replaced")
        self.assertEqual(features.texts["palt"], edited, "the user's rule is still there")
        self.assertEqual(self.history, [], "no History step")
        self.assertEqual(self.runs, [1], "the list read again")
        self.assertEqual([kind for kind, _ in self.logged], ["warning"], self.logged)
        self.assertIn(u"(palt)", self.logged[0][1])
        self.assertIn(u"Nothing was written", self.logged[0][1])

    def test_a_feature_added_since_is_seen_and_an_unchanged_font_is_written(self):
        dialog, features = self.make({})
        features.texts["halt"] = u"feature halt {\n  pos uni3001 <0 0 -500 0>;\n} halt;\n"
        dialog.write()
        self.assertEqual(features.written, [])
        self.assertIn(u"(halt)", self.logged[0][1])
        dialog, features = self.make({"palt": self.USER_PALT})
        dialog.write()
        self.assertEqual(sorted(features.written), ["halt", "palt"])
        self.assertIn(u"pos uni3042 <-10 0 -20 0>;", features.texts["palt"], "the font's own rule kept")
        self.assertEqual(self.history, ["before", "notify"])
        # (owner's image 183: under the top row's progress, never stoppable, always ended)
        self.assertEqual((self.busy[0][0], self.busy[-1][0]), ("start", "end"))
        self.assertFalse(any(stoppable for kind, stoppable in self.busy if kind != "end"), self.busy)
        self.assertFalse(dialog.busy)

    def test_compile_after_writing_is_grayed_with_the_write_button(self):
        # (owner's image 195: checked and clickable beside a grayed Write the code)
        self.assertFalse(cj.compile_on(False, True))
        self.assertFalse(cj.compile_on(True, False), "Hangul widths alone: no code to compile")
        self.assertTrue(cj.compile_on(True, True))
        self.assertIn(u'<a href="%s">List again</a>' % cj.LIST_AGAIN, cj.stopped_line())
        self.assertEqual(cj.bar_share(cj.LIST_STEPS, cj.READ_STEP, 1.0), cj.LIST_STEPS[0][1])
        self.assertEqual(cj.bar_share(cj.LIST_STEPS, cj.PREVIEW_STEP, 1.0), 1.0)
        self.assertIsNone(cj.bar_share(cj.LIST_STEPS, u"Something else"))

    def test_a_stopped_listing_leaves_the_list_empty_with_a_link(self):
        dialog, features = self.make({})
        dialog.busy, dialog.trims = False, list(dialog.trims)
        dialog.tree = type("Tree", (), {"blockSignals": lambda t, on: None, "clear": lambda t: None})()
        dialog.status = type("Status", (), {"setText": lambda s, text: setattr(s, "text", text)})()
        dialog.ak.history_mark = staticmethod(lambda package: "mark")
        dialog.update_buttons = lambda: None

        def read_font():
            raise dialog.ak.Stopped()
        dialog.read_font = read_font
        del dialog.run
        dialog.run()
        self.assertEqual([kind for kind, _ in self.busy], ["start", "end"])
        self.assertEqual(dialog.trims, [])
        self.assertIn(u"Listing was stopped", dialog.status.text)
        self.assertEqual(dialog.seen_history, "mark", "not read again for the History seen before")
        self.assertFalse(dialog.busy)

    def test_a_new_prefix_is_seen_too(self):
        """The font's own positions are read through the prefix's classes: one changed since is a change."""
        dialog, features = self.make({"palt": self.USER_PALT})
        features.get_prefix = lambda: u"@palt = [a-hira];"
        dialog.write()
        self.assertEqual(features.written, [])
        self.assertIn(u"(prefix)", self.logged[0][1])

    def test_the_log_says_who_keeps_what(self):
        """Live: "they keep palt it, not FreeLab's trim" (the feature's tag given once too often)."""
        dialog, features = self.make({"palt": u"feature palt {\n  pos [a-hira ideographiccomma] <0 0 -1 0>;\n} palt;\n"})
        dialog.write()
        palt = [text for kind, text in self.logged if kind == "warning" and u"own palt" in text]
        self.assertEqual(len(palt), 1, self.logged)
        self.assertIn(u"are positioned by the font's own palt code already: they keep theirs, not FreeLab's trim", palt[0])
        self.assertNotIn(u"keep palt", palt[0])
        self.assertEqual(features.written, ["halt"], "palt has nothing left to write")


class CheckRow(object):
    """A list's row as check_rows sees it: its check, its group (up), whether that group is open."""

    def __init__(self, on, up=None, expanded=True):
        self.on, self.up, self.expanded = on, up, expanded

    def checkState(self, column):
        return 2 if self.on else 0

    def setCheckState(self, column, state):
        self.on = state == 2

    def parent(self):
        return self.up

    def isHidden(self):
        return False

    def isExpanded(self):
        return self.expanded


def check_all_logged(test, module, dialog_class, noun):
    """Check all and Check none of a CJK tool (module's dialog_class) over two groups, one closed: what
    the log says (owner's report 118: these buttons left no line)."""
    sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
    import freelab_auto_kerning as ak
    saved = sys.modules.get("PythonQt")
    qt = type("PythonQt", (), {})()
    qt.QtCore = type("QtCore", (), {"Qt": type("Qt", (), {"Checked": 2, "Unchecked": 0, "ItemIsUserCheckable": 16})})
    qt.QtGui = type("QtGui", (), {})
    sys.modules["PythonQt"] = qt
    try:
        open_group, closed_group = CheckRow(False), CheckRow(False, expanded=False)
        rows = [CheckRow(True, open_group), CheckRow(False, open_group), CheckRow(False, closed_group),
                CheckRow(False, closed_group)]
        for row in rows:
            row.flags = lambda: 16
        dialog = dialog_class.__new__(dialog_class)  # (its window needs FontLab)
        logged = []
        dialog.ak, dialog.items, dialog.changed = ak, lambda: rows, lambda: None
        dialog.tree = type("Tree", (), {"blockSignals": lambda self, on: None})()
        dialog.log = type("Log", (), {"add": lambda _, text, kind=None: logged.append(text)})()
        dialog.check_all(True)
        test.assertTrue(all(row.on for row in rows))
        test.assertEqual(logged[-1], u"<i>Check all</i> checked <b>3 %ss</b> (2 of them in closed groups)." % noun)
        rows[2].on = False
        dialog.check_all(False)
        test.assertEqual(logged[-1], u"<i>Check none</i> unchecked <b>3 %ss</b> (1 of them in a closed group)." % noun)
        dialog.check_all(False)
        test.assertEqual(logged[-1], u"<i>Check none</i> changed nothing.")
    finally:
        if saved is None:
            sys.modules.pop("PythonQt", None)
        else:
            sys.modules["PythonQt"] = saved


class ReaderLoadingTests(unittest.TestCase):
    """Codex review 7, finding 3: without Feature Code's script (or with a broken one), its loader raised out of
    the windows' button updates and writes. Now nothing is written, the write is grayed out, and the log says
    to reinstall FreeLab."""

    class Ak(object):
        def __init__(self):
            self.enabled = {}

        def enable(self, widget, on):
            self.enabled[widget] = bool(on)

        @staticmethod
        def html(text):
            return text

    def window(self, logged):
        dialog = cj.CJKSpacingDialog.__new__(cj.CJKSpacingDialog)  # (its window needs FontLab)
        dialog.ak = self.Ak()
        dialog.trims, dialog.first_checks, dialog.texts, dialog.classes, dialog.lookups = [], [], {}, {}, {}
        dialog.package = object()
        for name in ("all_button", "none_button", "restore_button", "compile_box"):
            setattr(dialog, name, name)
        dialog.write_button = type("Button", (), {"setText": lambda self, text: None})()
        dialog.palt_box = dialog.halt_box = type("Box", (), {"checked": True})()
        dialog.harvest = dialog.draw_previews = lambda: None
        dialog.hangul_chosen = lambda: [u"ga"]  # (Hangul widths to set: clickable but for the reader)
        dialog.log = type("Log", (), {"add": lambda _, text, kind=None: logged.append((kind, text))})()
        return dialog

    def test_a_missing_or_broken_reader_writes_nothing_and_says_why(self):
        import shutil
        import tempfile
        saved_file, saved = cj.__file__, sys.modules.pop(cj.FEATURE_CODE_MODULE, None)
        saved_qt = sys.modules.get("PythonQt")
        qt = type("PythonQt", (), {"QtCore": None, "QtGui": None})()  # (the window's update asks for Qt's modules)
        sys.modules["PythonQt"] = qt
        self.addCleanup(lambda: sys.modules.__setitem__("PythonQt", saved_qt) if saved_qt is not None
                        else sys.modules.pop("PythonQt", None))
        env = os.environ.get("FREELAB_NO_AUTOSTART")
        folder = tempfile.mkdtemp(prefix="freelab-reader-")
        old = u"feature palt { pos a <0 0 -5 0>; } palt;"
        try:
            os.makedirs(os.path.join(folder, "cjk"))
            cj.__file__ = os.path.join(folder, "cjk", "freelab_cjk_spacing.py")
            # Codex review 8, finding 3: an older script that loads but lacks what is called now (readable),
            # made here from today's by taking it out (the real round-6 script was checked the same way)
            with io.open(os.path.join(HERE, os.pardir, "features", cj.FEATURE_CODE_FILE), encoding="utf-8") as handle:
                older = handle.read().replace(u"\ndef readable(", u"\ndef readable_not_yet(")
            for broken in (None, u"def broken(:\n", older, older):  # (empty folder; no compile; older; older, cached)
                if broken is not None:
                    with io.open(os.path.join(folder, "cjk", cj.FEATURE_CODE_FILE), "w", encoding="utf-8") as handle:
                        handle.write(broken)
                self.assertIsNone(cj.feature_text("palt", old, [u"pos x <0 0 -10 0>;"]), "nothing written")
                self.assertIsNone(cj.block_of("palt", old))
                self.assertIn(u"Reinstall FreeLab", cj.feature_code_problem(u"CJK Spacing"))
                if broken is older:
                    self.assertIn(u"without readable", cj.feature_code_problem(u"CJK Spacing"))
                    self.assertIn(cj.FEATURE_CODE_MODULE, sys.modules, "loaded (and kept), but not used")
                else:
                    self.assertNotIn(cj.FEATURE_CODE_MODULE, sys.modules, "no half-loaded module kept")
                self.assertEqual(os.environ.get("FREELAB_NO_AUTOSTART"), env)
                logged = []
                dialog = self.window(logged)
                dialog.update_buttons()
                self.assertFalse(dialog.ak.enabled[dialog.write_button], "the write grayed out")
                self.assertFalse(dialog.ak.enabled["compile_box"], "and its compile with it (owner's image 195)")
                dialog.update_buttons()
                self.assertEqual([kind for kind, _ in logged], ["error"], "said once")
                self.assertIn(u"freelab_feature_code.py", logged[0][1])
                dialog.write()  # (refused before anything is read or written)
                self.assertEqual([kind for kind, _ in logged], ["error", "error"])
        finally:
            cj.__file__ = saved_file
            sys.modules.pop(cj.FEATURE_CODE_MODULE, None)
            if saved is not None:
                sys.modules[cj.FEATURE_CODE_MODULE] = saved
            shutil.rmtree(folder, ignore_errors=True)
        # The script there (the control): loaded once, then the same module; nothing to say
        self.assertIs(cj.feature_code(), cj.feature_code())
        self.assertEqual(cj.feature_code_problem(u"CJK Spacing"), u"")
        logged = []
        self.window(logged).update_buttons()
        self.assertEqual(logged, [])


class TokenReadingTests(unittest.TestCase):
    def test_codex_review_6_scenarios(self):
        """Markers found as comments wherever they stand, never past their pair; another feature's code is no
        body; a body's braces must balance (Feature Code's writer_scenarios, through its token functions)."""
        sys.path.insert(0, HERE)
        import features_tests
        features_tests.writer_scenarios(self, lambda old, rules: cj.feature_text("palt", old, rules), u"palt",
                                        cj.BEGIN % "palt", cj.END % "palt", u"pos x <0 0 -10 0>;")
        own = u"feature palt {\npos a <0 0 -5 0>;\n%s\npos b <0 0 -5 0>; %s\npos c <0 0 -7 0>;\n} palt;" % (
            cj.BEGIN % "palt", cj.END % "palt")
        self.assertEqual(cj.font_positioned("palt", own), set(["a", "c"]), "the font's own, around FreeLab's block")
        self.assertEqual(cj.block_of("palt", own), u"feature palt {\npos b <0 0 -5 0>; \n} palt;\n")


class CompactFeatureTests(unittest.TestCase):
    def test_a_compact_feature_keeps_its_code(self):
        """Codex review 5 (Feature Code's writer, the same as this one): a feature on one line, or its brace after
        the last rule, had no "} palt;" line, and the font's own code was made again from nothing."""
        rule = u"pos uni3042 <-10 0 -20 0>;"
        for own in (u"feature palt { pos uni3044 <-5 0 -10 0>; } palt;",
                    u"feature palt {\npos uni3044 <-5 0 -10 0>; } palt;",
                    u"feature\npalt\n{\npos uni3044 <-5 0 -10 0>;\n}\npalt;"):
            text = cj.feature_text("palt", own, [rule])
            self.assertIn(u"pos uni3044 <-5 0 -10 0>;", text, "the font's own rule kept: %r" % text)
            self.assertLess(text.index(rule), cj.feature_code().feature_bounds(text, "palt")[1], "inside the feature")
            self.assertEqual(text.count(u"feature"), 1)
        broken = u"feature palt { pos uni3044 <-5 0 -10 0>;"
        self.assertIsNone(cj.feature_text("palt", broken, [rule]))
        refused = []
        trims = [cj.suggest(cj.Trim(0x3042, "a-hira", "hiragana", 1000, 150, 880), MODEL, 1000.0)]
        self.assertNotIn("palt", cj.texts_for(trims, {"palt": broken}, halt_on=False, refused=refused))
        self.assertEqual(refused, ["palt"])
        self.assertIn(u"FreeLab leaves palt as it is", cj.refused_words(refused))
        self.assertEqual(cj.feature_text("palt", None, [rule]).splitlines()[0], u"feature palt {", "no code: a new feature")


class CheckAllTests(unittest.TestCase):
    def test_check_all_and_none_say_how_many(self):
        check_all_logged(self, cj, cj.CJKSpacingDialog, u"glyph")


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
