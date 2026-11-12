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

    def test_right_to_left_reverses_and_kerns_as_seen(self):
        font = make_font(kerning={(u"b", u"a"): -50})
        placed, width = fp.place(font, [u"a", u"b"], rtl=True)
        self.assertEqual(placed, [(u"b", 0.0), (u"a", 450.0)], "a reads first, so it sits at the right")

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
        sys.modules["PythonQt"], sys.modules["fontlab"] = qt, fontlab
        cls.ak_layer_path, cls.ak_stamp = ak.layer_path, getattr(ak, "_freelab_stamp", "unset")
        ak.layer_path = lambda layer: Anything()
        ak._freelab_stamp = None  # (load_auto_kerning finds no file beside the script: the one loaded here is kept)
        sys.modules[fp.AUTO_KERNING_MODULE] = ak
        cls.ak = ak

    @classmethod
    def tearDownClass(cls):
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


if __name__ == "__main__":
    unittest.main()
