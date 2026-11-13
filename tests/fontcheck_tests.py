"""Tests of FreeLab's Font Check: language coverage, vertical metrics, and masters' compatibility.
Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import re
import sys
import unicodedata
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "checks"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "diacritics"))
import freelab_font_check as fc  # noqa: E402

LANGUAGES_FILE = os.path.join(HERE, os.pardir, "checks", "language_coverage.json")
ORTHOGRAPHIES_FILE = os.path.join(HERE, os.pardir, "checks", "language_orthographies.json")
CRUBADAN = u"An Cr\N{LATIN SMALL LETTER U WITH ACUTE}bad\N{LATIN SMALL LETTER A WITH ACUTE}n"
TRAIN = os.path.join(HERE, os.pardir, "checks", "train")
u = fc.char_of
LATIN_1 = list(range(0x20, 0x7F)) + list(range(0xA0, 0x180))  # ASCII, Latin-1, Latin Extended-A


def language(base, auxiliary=u"", marks=u"", script=u"Latin", name=u"Test", speakers=0, status=u"living"):
    return fc.Language(u"tst", name, u"", script, status, u"verified", speakers, base.split(), auxiliary.split(), marks)


def font(codes, anchors=None):
    """A font of the code points; anchors {code: [anchor names]} put marks on letters."""
    if anchors is None:
        return fc.FontCharacters(codes, None)

    def attaches(base, mark):
        wanted = set(name[1:] for name in anchors.get(mark, []) if name.startswith(u"_"))
        return bool(wanted & set(anchors.get(base, [])))
    return fc.FontCharacters(codes, attaches)


class TextTests(unittest.TestCase):
    def test_code_points_join_surrogates(self):
        self.assertEqual(fc.code_points(u"a" + fc.char_of(0x1F600) + u"b"), [0x61, 0x1F600, 0x62])
        self.assertEqual(fc.code_points(fc.char_of(0x1E900)), [0x1E900], "past U+FFFF, either build")

    def test_marks(self):
        self.assertTrue(fc.is_mark(0x0301))
        self.assertFalse(fc.is_mark(0x0061))

    def test_marks_newer_than_the_runtime(self):
        """FontLab's Python has Unicode 5.2: Kuvi's U+0C3C and Shina's U+08FF (encoded since) are
        unassigned there, so their letters could never count as composed. The orthographies' own marks
        (their data made with Unicode 17) make them marks whatever the runtime knows."""
        real = fc.unicodedata

        class Unicode52(object):
            """The runtime's Unicode data, as FontLab's Python 2.7 reads these two."""
            def __getattr__(self, name):
                return getattr(real, name)

            def category(self, character):
                if fc.code_points(character)[0] in (0x0C3C, 0x08FF):
                    return u"Cn"
                return real.category(character)

        held = set(fc.DATA_MARKS)
        fc.unicodedata = Unicode52()
        try:
            fc.DATA_MARKS.clear()
            self.assertFalse(fc.is_mark(0x0C3C), "what FontLab's Python said")
            anchors = {0x0C21: [u"bottom"], 0x0C3C: [u"_bottom"], 0x06D2: [u"top"], 0x08FF: [u"_top"]}
            kuvi_dda = u(0x0C21) + u(0x0C3C)
            self.assertEqual(fc.support(kuvi_dda, font([0x0C21, 0x0C3C], anchors))[0], fc.MISSING)
            fc._LANGUAGES.pop(LANGUAGES_FILE, None)  # (its orthographies made anew, as at an opening)
            fc.load_orthographies(LANGUAGES_FILE)
        finally:
            fc.unicodedata = real
        fc.DATA_MARKS.update(held)
        self.assertTrue(fc.is_mark(0x0C3C) and fc.is_mark(0x08FF), "Kuvi's and Shina's marks, in the data")
        fc.unicodedata = Unicode52()
        try:
            self.assertEqual(fc.support(kuvi_dda, font([0x0C21, 0x0C3C], anchors))[0], fc.COMPOSED)
            self.assertEqual(fc.support(u(0x06D2) + u(0x08FF), font([0x06D2, 0x08FF], anchors))[0], fc.COMPOSED)
            self.assertEqual(fc.shown_text(u(0x0C3C)), fc.DOTTED_CIRCLE + u(0x0C3C), "drawn on a dotted circle")
        finally:
            fc.unicodedata = real


class SupportTests(unittest.TestCase):
    def test_own_glyph(self):
        self.assertEqual(fc.support(u(0xE9), font([0xE9]))[0], fc.HAVE)

    def test_listed_decomposed_found_composed(self):
        self.assertEqual(fc.support(u"e" + u(0x301), font([0xE9]))[0], fc.HAVE)

    def test_composed_with_anchors(self):
        anchors = {0x65: [u"top"], 0x301: [u"_top"]}
        how, recipe = fc.support(u(0xE9), font([0x65, 0x301], anchors))
        self.assertEqual(how, fc.COMPOSED)
        self.assertEqual(recipe, (0x65, (0x301,)))

    def test_parts_without_anchors(self):
        self.assertEqual(fc.support(u(0xE9), font([0x65, 0x301], {}))[0], fc.PARTS, "no anchor joins them")
        self.assertEqual(fc.support(u(0xE9), font([0x65, 0x301]))[0], fc.PARTS, "composing not counted")
        self.assertEqual(fc.support(u(0xE9), font([0x65]))[0], fc.MISSING, "no mark")

    def test_two_marks_on_a_letter_with_one(self):
        # e with macron and acute: the font's e with macron, and the acute on it
        anchors = {0x113: [u"top"], 0x301: [u"_top"]}
        how, recipe = fc.support(u(0x1E17), font([0x113, 0x301], anchors))
        self.assertEqual((how, recipe), (fc.COMPOSED, (0x113, (0x301,))))

    def test_unencoded_cluster(self):
        n_dieresis = u"n" + u(0x308)
        anchors = {0x6E: [u"top"], 0x308: [u"_top"]}
        self.assertEqual(fc.support(n_dieresis, font([0x6E, 0x308], anchors))[0], fc.COMPOSED)
        self.assertEqual(fc.support(n_dieresis, font([0x6E]))[0], fc.MISSING)

    def test_hangul_does_not_compose_from_jamo(self):
        syllable = u(0xD55C)
        jamo = fc.code_points(unicodedata.normalize("NFD", syllable))
        self.assertEqual(fc.support(syllable, font(jamo, {}))[0], fc.MISSING, "jamo are letters, not marks")


class CoverageTests(unittest.TestCase):
    def test_levels(self):
        czech = language(u"a b c " + u(0x10D) + u" " + u(0x159), u"q " + u(0x1D7))
        result = fc.check_language(czech, font([0x61, 0x62, 0x63, 0x10D, 0x159, 0x71, 0x1D7]))
        self.assertEqual(result.level, "covered")
        result = fc.check_language(czech, font([0x61, 0x62, 0x63, 0x10D, 0x159]))
        self.assertEqual((result.level, result.auxiliary_missing), ("nearly", [u"q", u(0x1D7)]), "auxiliary only")
        result = fc.check_language(czech, font([0x61, 0x62, 0x63]))
        self.assertEqual((result.level, result.missing), ("nearly", [u(0x10D), u(0x159)]))
        result = fc.check_language(czech, font([0x61]), nearly=1)
        self.assertEqual((result.level, result.base_missing(), result.have), ("started", 4, 1),
                         "one character and more, short of within reach: started")
        result = fc.check_language(czech, font([0x71]), nearly=1)
        self.assertEqual((result.level, result.have), ("started", 1), "an auxiliary character is a start too")
        result = fc.check_language(czech, font([0x78]), nearly=1)
        self.assertEqual((result.level, result.have), ("missed", 0), "none of its characters: missed")
        result = fc.check_language(language(u"a b c d e", marks=u(0x301)), font([0x301]), nearly=1)
        self.assertEqual((result.level, result.have), ("started", 1), "a mark it needs counts as a character")
        self.assertEqual([key for key, _ in fc.LEVELS], ["nearly", "covered", "started", "missed"])
        self.assertEqual(fc.BAR_LEVELS, ("covered", "nearly", "started", "missed"))
        self.assertEqual([key for key, _ in fc.LANGUAGE_FILTERS], [None, "covered", "nearly", "started", "missed"])
        self.assertEqual(fc.STATE_LABELS["started"], u"Started")

    def test_level_counts(self):
        f = font([0x61, 0x62])
        results = [fc.check_language(one, f, 1) for one in (
            language(u"a b"), language(u"a b c"), language(u"a x y z"), language(u"x y z"), language(u"q r s"))]
        self.assertEqual([r.level for r in results], ["covered", "nearly", "started", "missed", "missed"])
        self.assertEqual(fc.level_counts(results), [1, 1, 1, 2], "covered, within reach, started, missed")
        self.assertEqual(fc.level_counts([]), [0, 0, 0, 0])
        self.assertEqual(fc.coverage_text([1, 1, 1, 2]), u"1 of 5 languages (1 within reach)")
        self.assertEqual(fc.coverage_text([1, 0, 0, 0]), u"1 of 1 language")
        self.assertEqual(fc.counts_tip(u"Latin", [1, 1, 1, 2]), u"Latin: 1 covered, 1 within reach, 1 started, 2 missed.")
        # Started languages sort after the covered ones and before the missed ones
        order = [r.language.base for r in fc.sort_languages(results[::-1], "most")]
        self.assertEqual(order[:3], [[u"a", u"b"], [u"a", u"b", u"c"], [u"a", u"x", u"y", u"z"]])
        self.assertEqual([r.level for r in fc.sort_languages(results[::-1], "reach")],
                         ["nearly", "covered", "started", "missed", "missed"])

    def test_required_marks_count_as_base(self):
        result = fc.check_language(language(u"a b", marks=u(0x301)), font([0x61, 0x62]))
        self.assertEqual((result.level, result.marks_missing), ("nearly", [u(0x301)]))

    def test_composed_listed(self):
        anchors = {0x72: [u"top"], 0x30C: [u"_top"]}
        result = fc.check_language(language(u"r " + u(0x159)), font([0x72, 0x30C], anchors))
        self.assertEqual(result.level, "covered")
        self.assertEqual([c for c, _ in result.composed], [u(0x159)])

    def test_order_and_scripts(self):
        languages = [language(u"a b", name=u"Covered", speakers=10), language(u"a b c", name=u"Nearly", speakers=5),
                     language(u"a x y z w v", name=u"Missed", speakers=100),
                     language(u"a b", name=u"Old", status=u"historical"),
                     language(u(0x3B1) + u" " + u(0x3B2), script=u"Greek", name=u"Greek")]
        found = fc.coverage(languages, font([0x61, 0x62]))
        self.assertEqual([s.script for s in found], [u"Latin", u"Greek"])
        self.assertTrue(found[0].present)
        self.assertFalse(found[1].present, "no Greek letter")
        self.assertEqual([r.language.name for r in found[0].results], [u"Nearly", u"Covered", u"Missed"])
        found = fc.coverage(languages, font([0x61, 0x62]), historical=True)
        self.assertIn(u"Old", [r.language.name for r in found[0].results])

    def test_buildable_candidates(self):
        result = fc.check_language(language(u"a " + u(0x159) + u" " + u(0x1E9B) + u" " + u(0x3A9)), font([0x61]))
        ranges = [(0xC0, 0x250), (0x370, 0x400)]
        self.assertEqual(fc.buildable_candidates([result], ranges), [u(0x159)], "in range, letter and marks only")

    def test_missing_marks_are_candidates(self):
        result = fc.check_language(language(u"a", marks=u(0x331) + u(0x5B4)), font([0x61]))
        self.assertEqual(result.marks_missing, [u(0x331), u(0x5B4)])
        ranges = [(0xC0, 0x250)]
        self.assertEqual(fc.buildable_candidates([result], ranges), [u(0x331)], "a combining mark, not a Hebrew point")
        import freelab_diacritics as dm
        self.assertEqual([r.char for r in dm.plan(dm.Font([u"o", u"macron"], [(u"o", 0x6F), (u"macron", 0xAF)]),
                                                  [u(0x331)])], [u(0x331)], "Diacritics plans the mark")

    def test_handed_to_diacritics(self):
        import freelab_diacritics as dm
        result = fc.check_language(language(u"r " + u(0x159) + u" " + u(0x13E)), font([0x72]))
        candidates = fc.buildable_candidates([result], [pair for _, _, pairs in dm.SETS for pair in pairs])
        diacritics_font = dm.Font([u"r", u"caron", u"l", u"quoteright"], [(u"r", 0x72), (u"l", 0x6C), (u"quoteright", 0x2019)])
        built = [r.char for r in dm.plan(diacritics_font, candidates) if not r.missing]
        self.assertEqual(built, [u(0x159), u(0x13E)], "r with the font's caron; l with the vertical caron drafted from its apostrophe")


class LanguageDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.languages = fc.load_languages(LANGUAGES_FILE)
        cls.by_iso = dict(((l.iso, l.script), l) for l in cls.languages)

    def test_data(self):
        self.assertGreater(len(self.languages), 700)
        czech = self.by_iso[(u"ces", u"Latin")]
        self.assertEqual(czech.name, u"Czech")
        self.assertIn(u(0x159), czech.base)
        self.assertGreater(czech.speakers, 1000000)
        self.assertIn((u"srp", u"Cyrillic"), self.by_iso)
        self.assertIn((u"srp", u"Latin"), self.by_iso)

    def test_latin_font(self):
        found = dict((s.script, s) for s in fc.coverage(self.languages, font(LATIN_1)))
        latin = dict((r.language.iso, r) for r in found[u"Latin"].results)
        for iso in (u"fra", u"deu", u"ces", u"pol", u"tur", u"hun", u"eng", u"spa"):
            self.assertNotEqual(latin[iso].level, "missed", iso)
            self.assertEqual(latin[iso].base_missing(), 0, iso)
        self.assertEqual(latin[u"vie"].level, "started", "Vietnamese needs Latin Extended Additional")
        self.assertEqual(set(r.level for r in found[u"Arabic"].results), set(["missed"]), "no Arabic letter at all")
        self.assertEqual(sorted(latin[u"ron"].missing), [u(0x218), u(0x219), u(0x21A), u(0x21B)],
                         "Romanian's letters with a comma below: Latin Extended-B")
        self.assertFalse(found[u"Arabic"].present)

    def test_vietnamese_composed(self):
        marks = [0x300, 0x301, 0x303, 0x309, 0x323, 0x302, 0x306, 0x31B]
        codes = LATIN_1 + marks
        letters = [code for code in codes if unicodedata.category(u(code)).startswith(u"L")]
        anchors = dict((code, [u"top", u"bottom"]) for code in letters)
        anchors.update(dict((code, [u"_bottom" if code == 0x323 else u"_top"]) for code in marks))
        vietnamese = [l for l in self.languages if l.iso == u"vie"][0]
        result = fc.check_language(vietnamese, font(codes, anchors))
        self.assertEqual(result.base_missing(), 0, u" ".join(result.missing))
        self.assertGreater(len(result.composed), 50)


class MetricsTests(unittest.TestCase):
    def extents(self, rows):
        return [fc.Extent(name, code, master, bottom, top) for name, code, master, bottom, top in rows]

    def test_google_fonts_example(self):
        # Google Fonts' vertical metrics guide: a new Latin family, UPM 1000, cap height 730, A grave
        # 940, g -235, the family's ink from -320 to 1116: typo 965 and -235, win 1116 and 320
        extents = self.extents([("Agrave", 0xC0, "Bold", 0, 940), ("g", 0x67, "Bold", -235, 500),
                                ("Abrevehookabove", 0x1EB2, "Bold", 0, 1116), ("ccedilla", 0xE7, "Light", -320, 500),
                                ("H", 0x48, "Bold", 0, 730)])
        m = fc.VerticalMetrics(upm=1000, cap_height=730)
        suggestions, notes = fc.suggest_metrics(m, extents)
        values = dict((s.key, s.value) for s in suggestions)
        self.assertEqual((values["typo_ascender"], values["typo_descender"], values["typo_line_gap"]), (965, -235, 0))
        self.assertEqual((values["hhea_ascender"], values["hhea_descender"], values["hhea_line_gap"]), (965, -235, 0))
        self.assertEqual((values["win_ascent"], values["win_descent"], values["use_typo"]), (1116, 320, True))

    def test_raised_for_a_grave_and_descenders(self):
        extents = self.extents([("Agrave", 0xC0, "R", 0, 1000), ("p", 0x70, "R", -300, 500)])
        values = dict((s.key, s.value) for s in fc.suggest_metrics(fc.VerticalMetrics(upm=1000, cap_height=700), extents)[0])
        self.assertEqual((values["typo_ascender"], values["typo_descender"]), (1000, -300))

    def test_updates_keep_the_line(self):
        extents = self.extents([("A", 0x41, "R", -300, 1100)])
        # I: Use Typo Metrics on: typo kept; II: off: the old win values become typo, line gaps 0
        on = fc.VerticalMetrics(upm=1000, typo_ascender=800, typo_descender=-200, typo_line_gap=200,
                                win_ascent=1000, win_descent=200, use_typo=True)
        values = dict((s.key, s.value) for s in fc.suggest_metrics(on, extents, mode="keep")[0])
        self.assertEqual((values["typo_ascender"], values["typo_line_gap"], values["win_ascent"], values["win_descent"]),
                         (800, 200, 1100, 300))
        off = fc.VerticalMetrics(upm=1000, typo_ascender=800, typo_descender=-200, typo_line_gap=200,
                                 win_ascent=1000, win_descent=200, use_typo=False)
        values = dict((s.key, s.value) for s in fc.suggest_metrics(off, extents, mode="keep")[0])
        self.assertEqual((values["typo_ascender"], values["typo_descender"], values["typo_line_gap"],
                          values["hhea_ascender"], values["use_typo"]), (1000, -200, 0, 1000, True))

    def test_clipping(self):
        extents = self.extents([("Aring", 0xC5, "Black", 0, 1050), ("Aring", 0xC5, "Light", 0, 990),
                                ("g", 0x67, "Black", -260, 520)])
        m = fc.VerticalMetrics(upm=1000, win_ascent=1000, win_descent=250, typo_ascender=950, typo_descender=-250,
                               typo_line_gap=0, hhea_ascender=950, hhea_descender=-250, hhea_line_gap=0, use_typo=True,
                               cap_height=700)
        found = fc.check_metrics(m, extents)
        clipped = [(f.kind, f.glyphs, f.value) for f in found if f.kind.startswith("clip")]
        self.assertEqual(clipped, [("clip-top", [("Black", "Aring", 50)], 50), ("clip-bottom", [("Black", "g", 10)], 10)])
        self.assertFalse([f for f in found if f.kind == "settings" and f.severity != "info"], [f.text for f in found])

    def test_settings(self):
        m = fc.VerticalMetrics(upm=1000, win_ascent=1000, win_descent=300, typo_ascender=750, typo_descender=-250,
                               typo_line_gap=200, hhea_ascender=950, hhea_descender=-250, hhea_line_gap=0,
                               use_typo=False, cap_height=700)
        texts = u" | ".join(f.text for f in fc.check_metrics(m, self.extents([("Agrave", 0xC0, "R", 0, 900)])))
        for expected in (u"Use Typo Metrics is off", u"hhea ascender (950) and typo ascender (750) differ",
                         u"hhea line gap (0) and typo line gap (200) differ", u"typo line gap is 200",
                         u(0xC0) + u" reaches 900", u"Capitals are not centered"):
            self.assertIn(expected, texts)
        self.assertNotIn(u"The line is", texts, "750 + 250 + 200: 120% of the em")
        unset = fc.check_metrics(fc.VerticalMetrics(upm=1000), [])
        self.assertTrue(any(u"winAscent and winDescent are not set" in f.text for f in unset))
        self.assertTrue(any(u"Neither typo nor hhea" in f.text for f in unset))

    def test_line_share_only_for_capitals(self):
        m = fc.VerticalMetrics(upm=1000, typo_ascender=1100, typo_descender=-500, typo_line_gap=0, hhea_ascender=1100,
                               hhea_descender=-500, hhea_line_gap=0, win_ascent=1100, win_descent=500, use_typo=True)
        self.assertTrue(any(f.text.startswith(u"The line is 160%") for f in fc.check_metrics(m, [])))
        self.assertFalse(any(f.text.startswith(u"The line is") for f in fc.check_metrics(m, [], capitals=False)))

    def test_main_script(self):
        arabic = list(range(0x627, 0x64B))
        self.assertTrue(fc.has_capitals(LATIN_1))
        self.assertTrue(fc.has_capitals(LATIN_1 + arabic), "more Latin letters than Arabic ones")
        self.assertFalse(fc.has_capitals(list(range(0x20, 0x7F)) + arabic + list(range(0xFE70, 0xFEFD))))
        self.assertFalse(fc.has_capitals(list(range(0x30, 0x3A))), "no capitals at all")

    def test_tall_script_clears_its_letters(self):
        extents = self.extents([("alef", 0x627, "R", -50, 1250), ("yeh", 0x64A, "R", -620, 400)])
        m = fc.VerticalMetrics(upm=1000, ascender=750, descender=-250)
        values = dict((s.key, s.value) for s in fc.suggest_metrics(m, extents, False, letters=set([0x627, 0x64A]))[0])
        self.assertEqual((values["typo_ascender"], values["typo_descender"], values["win_ascent"], values["win_descent"]),
                         (1250, -620, 1250, 620))


def contour(points, kind=u"on"):
    return fc.Contour([(x, y, kind) for x, y in points])


SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]  # counterclockwise (y up)
TRIANGLE = [(0, 0), (60, 0), (30, 50)]


class MastersTests(unittest.TestCase):
    def compare(self, light, bold, name=u"g"):
        return [(f.master, f.contour, f.kind) for f in fc.compare_glyph(name, [(u"Light", light), (u"Bold", bold)])]

    def test_compatible(self):
        light = fc.Outline([contour(SQUARE)], [u"acutecomb"], [u"top"])
        bold = fc.Outline([contour([(x * 1.4, y * 1.1) for x, y in SQUARE])], [u"acutecomb"], [u"top"])
        self.assertEqual(self.compare(light, bold), [])

    def test_missing_and_counts(self):
        light = fc.Outline([contour(SQUARE), contour(TRIANGLE)])
        self.assertEqual(self.compare(light, None), [], "in one master only: a glyph that does not vary")
        three = fc.compare_glyph(u"g", [(u"Light", light), (u"Regular", light), (u"Bold", None)])
        self.assertEqual([(f.master, f.kind) for f in three], [(u"Bold", "missing")], "two have it, one lacks it")
        self.assertEqual(self.compare(light, fc.Outline([contour(SQUARE)])), [(u"Bold", None, "contours")])
        self.assertEqual(self.compare(light, fc.Outline([contour(SQUARE), contour(SQUARE)])), [(u"Bold", 2, "nodes")])
        self.assertEqual(self.compare(light, fc.Outline([contour(TRIANGLE), contour(SQUARE)])), [(u"Bold", None, "order")])

    def test_types_direction_start(self):
        light = fc.Outline([contour(SQUARE)])
        curved = fc.Contour([(0, 0, u"on"), (100, 0, u"off"), (100, 100, u"on"), (0, 100, u"on")])
        self.assertEqual(self.compare(light, fc.Outline([curved])), [(u"Bold", 1, "types")])
        self.assertEqual(self.compare(light, fc.Outline([contour(SQUARE[::-1])])), [(u"Bold", 1, "direction")])
        reversed_curve = fc.Contour(curved.nodes[::-1])
        self.assertEqual(self.compare(fc.Outline([curved]), fc.Outline([reversed_curve])), [(u"Bold", 1, "direction")],
                         "reversed: its node types run the other way round")
        eight = contour([(0, 0), (100, 100), (100, 0), (0, 100)])
        self.assertEqual(self.compare(fc.Outline([eight]), fc.Outline([fc.Contour(eight.nodes[::-1])])), [],
                         "a figure eight's direction means little")
        moved = SQUARE[1:] + SQUARE[:1]
        found = fc.compare_glyph(u"o", [(u"Light", light), (u"Bold", fc.Outline([contour(moved)]))])
        self.assertEqual([(f.contour, f.kind) for f in found], [(1, "start")])
        self.assertIn(u"1 node", found[0].text)

    def test_start_point_kept_through_design_changes(self):
        # a heavier master: the same start, nodes moved a lot
        light = fc.Outline([contour([(0, 0), (100, 0), (100, 100), (50, 140), (0, 100)])])
        bold = fc.Outline([contour([(-20, -10), (140, 0), (130, 120), (60, 200), (-10, 110)])])
        self.assertEqual(self.compare(light, bold), [])

    def test_components_and_anchors(self):
        light = fc.Outline([], [u"a", u"acutecomb"], [u"top", u"bottom"])
        self.assertEqual(self.compare(light, fc.Outline([], [u"acutecomb", u"a"], [u"top", u"bottom"])),
                         [(u"Bold", None, "components")])
        found = fc.compare_glyph(u"aacute", [(u"Light", light), (u"Bold", fc.Outline([], [u"a", u"acutecomb"],
                                                                                         [u"top", u"_top"]))])
        self.assertEqual([f.kind for f in found], ["anchors"])
        self.assertEqual(found[0].text, u"Lacks anchor bottom; has anchor _top that Light lacks")

    def test_reference_is_the_first_master_with_the_glyph(self):
        found = fc.compare_glyph(u"x", [(u"Light", None), (u"Bold", fc.Outline([contour(SQUARE)])),
                                        (u"Black", fc.Outline([contour(SQUARE)]))])
        self.assertEqual([(f.master, f.kind) for f in found], [(u"Light", "missing")])


class NamesTests(unittest.TestCase):
    def test_short_names(self):
        self.assertEqual(fc.short_name(u(0x159)), u"r with caron")
        self.assertEqual(fc.short_name(u(0x158)), u"R with caron")
        self.assertEqual(fc.short_name(u(0x14A)), u"capital eng", "a capital named by a word")
        self.assertEqual(fc.short_name(u(0x67E)), u"peh", "no case: the letter's name")
        self.assertEqual(fc.short_name(u(0x301)), u"combining acute accent")
        self.assertEqual(fc.short_name(u(0x2BC)), u"modifier letter apostrophe")
        self.assertEqual(fc.short_name(u"n" + u(0x308)), u"n with diaeresis", "a letter and a mark, no one character")
        self.assertEqual(fc.short_name(u(0x113) + u(0x301)), u"e with macron and acute accent")

    def test_labels(self):
        self.assertEqual(fc.code_label(u"n" + u(0x308)), u"U+006E U+0308")
        self.assertEqual(fc.code_label(u(0x1E900)), u"U+1E900")
        self.assertEqual(fc.shown_text(u(0x301)), fc.DOTTED_CIRCLE + u(0x301), "a mark on a dotted circle")
        self.assertEqual(fc.case_partner(u(0x259)), u(0x18F))
        self.assertEqual(fc.case_partner(u(0x18F)), u(0x259))
        self.assertIsNone(fc.case_partner(u(0xDF)), "sharp s: its capital is two letters")
        self.assertIsNone(fc.case_partner(u"!"))


class AddTests(unittest.TestCase):
    """The characters to add, ranked; the languages a checked set completes."""

    def results(self):
        schwa, small_schwa, eng, small_eng = u(0x18F), u(0x259), u(0x14A), u(0x14B)
        base = u"a b c"
        languages = [language(base + u" " + schwa + u" " + small_schwa, name=u"Azeri", speakers=30),
                     language(base + u" " + schwa + u" " + small_schwa, name=u"Atayal", speakers=1),
                     language(base + u" " + small_eng + u" " + u(0x1B4), name=u"Wolof", speakers=5),
                     language(base + u" " + small_eng, name=u"Sami", speakers=2),
                     language(base, u"q", name=u"Loans", speakers=3),
                     language(base + u" x y z w", name=u"Far", speakers=100)]
        f = font([0x61, 0x62, 0x63, 0x73])
        return [fc.check_language(l, f) for l in languages], (schwa, small_schwa, eng, small_eng)

    def test_ranked_by_languages_completed(self):
        results, (schwa, small_schwa, eng, small_eng) = self.results()
        rows = fc.add_rows(results)
        self.assertEqual([row.items for row in rows][:2], [[schwa, small_schwa], [small_eng]])
        self.assertEqual([r.language.name for r in rows[0].completing], [u"Azeri", u"Atayal"], "the most spoken first")
        self.assertEqual([r.language.name for r in rows[1].completing], [u"Sami"])
        self.assertEqual([r.language.name for r in rows[1].needing], [u"Sami", u"Wolof"])
        wolof = [row for row in rows if row.items == [u(0x1B4)]][0]
        self.assertEqual(wolof.completing, [], "Wolof needs eng too")
        self.assertIn(u"Wolof (with " + small_eng + u")", fc.row_languages_text(wolof))
        self.assertNotIn(u"x", [i for row in rows for i in row.items], "a missed language's characters are not listed")
        loans = [row for row in rows if row.items == [u"q"]][0]
        self.assertTrue(loans.auxiliary(), "missing only auxiliary characters: those")

    def test_gained_as_sets(self):
        results, (schwa, small_schwa, eng, small_eng) = self.results()
        names = lambda checked: sorted(r.language.name for r in fc.languages_gained(results, checked))
        self.assertEqual(names([schwa]), [], "half of what Azeri needs")
        self.assertEqual(names([schwa, small_schwa]), [u"Atayal", u"Azeri"])
        self.assertEqual(names([small_eng]), [u"Sami"])
        self.assertEqual(names([small_eng, u(0x1B4)]), [u"Sami", u"Wolof"], "Wolof once both are checked")
        self.assertEqual(names([u"q"]), [u"Loans"])

    def test_gain_text(self):
        results, (schwa, small_schwa, _, _) = self.results()
        self.assertEqual(fc.gain_text(0, []), u"Check glyphs to see how many languages they complete.")
        self.assertEqual(fc.gain_text(1, []), u"With 1 glyph checked: no language is complete yet")
        gained = fc.languages_gained(results, [schwa, small_schwa])
        self.assertEqual(fc.gain_text(2, gained), u"With 2 glyphs checked: +2 languages (Latin)")
        self.assertEqual(fc.gain_text(2, gained[:1], lambda text: u"<b>%s</b>" % text),
                         u"With 2 glyphs checked: <b>+1 language</b> (Latin)")
        greek = fc.check_language(language(u(0x3B1), script=u"Greek", name=u"Greek"), font([]))
        self.assertEqual(fc.gain_text(3, gained + [greek]), u"With 3 glyphs checked: +3 languages (Latin 2, Greek 1)")

    def test_check_buttons(self):
        results, (schwa, small_schwa, eng, small_eng) = self.results()
        rows = fc.add_rows(results)
        listed = set(i for row in rows for i in row.items)
        targets = fc.checks_for(rows, set(), set([small_eng]))
        self.assertEqual(targets["all"], listed)
        self.assertIsNone(targets["none"], "nothing checked: grayed out")
        self.assertEqual(targets["buildable"], set([small_eng]), "the rows Diacritics can build, only")
        targets = fc.checks_for(rows, listed, set([small_eng]))
        self.assertIsNone(targets["all"], "everything checked: grayed out")
        self.assertEqual(targets["none"], set())
        self.assertEqual(targets["buildable"], set([small_eng]), "the others unchecked")
        self.assertIsNone(fc.checks_for(rows, set([small_eng]), set([small_eng]))["buildable"], "already so")
        self.assertIsNone(fc.checks_for(rows, set(), set())["buildable"], "Diacritics builds none of them")
        self.assertEqual(fc.checks_for(rows, set(), set([schwa]))["buildable"], set([schwa, small_schwa]),
                         "a row checks whole: a capital with its small letter")
        hidden = u(0x3B1)  # checked in a row another script's filter hides
        self.assertEqual(fc.checks_for(rows, set([hidden]), set())["all"], listed | set([hidden]), "kept")
        self.assertIsNone(fc.checks_for([], set(), set())["all"], "no row listed")

    def test_compact_missing(self):
        results, (schwa, small_schwa, _, _) = self.results()
        self.assertEqual(fc.compact_missing(results[0]), schwa + u" " + small_schwa)
        r = fc.check_language(language(u"a b c d"), font([0x61]))
        self.assertEqual(fc.compact_missing(r), u"b c +1")
        self.assertEqual(fc.compact_missing(results[4]), u"q", "its auxiliary ones")

    def test_script_text_and_bar(self):
        results, _ = self.results()
        s = fc.ScriptCoverage(u"Latin", results, True)
        self.assertEqual(fc.script_text(s), u"0 of 6 languages (5 within reach)", "parentheses, no middle dot")
        self.assertNotIn(u"\N{MIDDLE DOT}", fc.script_text(s))
        self.assertEqual(sum(fc.bar_widths([275, 99, 190, 5], 150)), 150, "four segments")
        self.assertEqual(fc.bar_widths([1, 0, 1000, 1], 100), [1, 0, 98, 1], "each count shows, however small")
        self.assertEqual(sum(fc.bar_widths([275, 99, 195], 150)), 150)
        self.assertEqual(fc.bar_widths([1, 0, 1000], 100), [1, 0, 99], "a count shows, however small")
        self.assertEqual(fc.bar_widths([0, 0, 0], 100), [0, 0, 0])

    def test_language_search(self):
        results, _ = self.results()
        czech = fc.check_language(fc.Language(u"ces", u"Czech", u"\N{LATIN SMALL LETTER C WITH CARON}e\N{LATIN SMALL LETTER S WITH CARON}tina",
                                              u"Latin", u"living", u"verified", 0, [u"a"], [], u""), font([0x61]))
        self.assertTrue(fc.language_matches(czech, u"cze"))
        self.assertTrue(fc.language_matches(czech, u"\N{LATIN CAPITAL LETTER C WITH CARON}E\N{LATIN SMALL LETTER S WITH CARON}"),
                        "the autonym, any case")
        self.assertTrue(fc.language_matches(czech, u"ces"))
        self.assertFalse(fc.language_matches(czech, u"slov"))
        self.assertTrue(fc.language_matches(czech, u"  cze "), "spaces around the text set aside")
        self.assertTrue(fc.language_matches(czech, u"cestina"), "diacritics set aside: the autonym typed plain")
        self.assertIsNone(fc.found_by(czech, u"cze"), "found by a name the list shows")
        self.assertEqual(fc.fold(u"\N{LATIN CAPITAL LETTER C WITH CARON}E\N{LATIN SMALL LETTER S WITH CARON}tina"), u"cestina")

    def test_found_by_another_name(self):
        """The owner: a language "may hold several names that are not even necessarily listed as is in
        our list". A search finds it by any, the list keeps its one name, and the find says which."""
        zhu = u"\N{LATIN CAPITAL LETTER Z WITH CARON}hu"
        nama = fc.Language(u"naq", u"Khoekhoe", u"Khoekhoegowab", u"Latin", u"living", u"verified", 0, [u"a"], [], u"")
        r = fc.check_language(nama, font([0x61]))
        self.assertFalse(fc.language_matches(r, u"nama"), "no other name yet")
        fc.name_languages([nama], fc.Families(aliases={u"naq": [u"Nama", u"Namaqua", u"Damara", zhu]}))
        self.assertTrue(fc.language_matches(r, u"nama"))
        self.assertEqual(fc.found_by(r, u"NAMA"), u"Nama", "any case; the first other name that holds the text")
        self.assertEqual(fc.found_by(r, u"maqua"), u"Namaqua")
        self.assertEqual(fc.found_by(r, u"zhu"), zhu, "diacritics set aside")
        self.assertIsNone(fc.found_by(r, u"khoe"), "its own name: no other name to tell")
        self.assertIsNone(fc.found_by(r, u""))
        self.assertFalse(fc.language_matches(r, u"zulu"))
        self.assertFalse(fc.language_matches(r, u"nama damara"), "one name at a time: never across two")
        self.assertEqual(nama.label(), u"Khoekhoe (Khoekhoegowab)", "the list keeps showing its one name")
        scripts = fc.coverage([nama], font([0x61]))
        sections, _ = fc.language_sections(scripts, [u"Latin"], u"dama")
        self.assertEqual([one.found_by for one in sections[0].results], [u"Damara"])
        self.assertEqual(fc.languages_line(sections, u"dama"),
                         u"1 language matches. Khoekhoe is found by its other name Damara.")
        self.assertIn(u"Found by its other name Damara.", fc.coverage_tip(sections[0].results[0]))
        self.assertEqual(fc.alias_line(sections[0].results * 2), u"2 are found by another name: their tooltips say which.")
        sections, _ = fc.language_sections(scripts, [u"Latin"], u"khoe")
        self.assertEqual([one.found_by for one in sections[0].results], [None])
        self.assertNotIn(u"other name", fc.languages_line(sections, u"khoe"))
        sections, _ = fc.language_sections(scripts, [u"Latin"])
        self.assertEqual([one.found_by for one in sections[0].results], [None], "no search: nothing to tell")
        fc.name_languages([nama], None)  # (no families file: found by its own names only)
        self.assertFalse(fc.language_matches(r, u"nama"))

    def test_selection_has_a_tab_of_its_own(self):
        """The owner: "Make the script-specific list its own tab so it doesn't get mixed in with the
        high-value list." The selection's rows are its missing characters and nothing else."""
        results, (schwa, small_schwa, eng, small_eng) = self.results()
        rows = fc.add_rows(results)
        self.assertEqual(fc.selection_rows(rows, None), ([], 0), "nothing selected: no rows")
        wolof, far = results[2], results[5]
        found, left = fc.selection_rows(rows, fc.selection_of(wolof))
        self.assertEqual(([row.items for row in found], left), ([[small_eng], [u(0x1B4)]], 0),
                         "its rows only, in the high-value list's order")
        self.assertTrue(all(row in rows for row in found), "the high-value list's own rows: +N counts every language")
        # A started language's characters are in no high-value row: they get rows of their own
        self.assertEqual(far.level, "started")
        found, left = fc.selection_rows(rows, fc.selection_of(far))
        self.assertEqual(([row.items for row in found], left), ([[u"w"], [u"x"], [u"y"], [u"z"]], 0))
        self.assertEqual([r.language.name for r in found[0].needing], [u"Far"])
        self.assertEqual(fc.row_languages_text(found[0]), u"Far (with x y z)")
        found, left = fc.selection_rows(rows, fc.selection_of(far), most=3)
        self.assertEqual((len(found), left), (3, 1), "no more rows than asked: the rest counted")
        covered = fc.check_language(language(u"a b", name=u"Whole"), font([0x61, 0x62]))
        self.assertEqual(fc.selection_rows(rows, fc.selection_of(covered)), ([], 0), "nothing missing: no rows")
        # A family: what its languages not covered miss, once each
        family = fc.Selection("family", u"Kwa", [wolof, far, covered], ("family", u"Kwa"))
        self.assertEqual(family.wanted(), [small_eng, u(0x1B4), u"x", u"y", u"z", u"w"])
        found, left = fc.selection_rows(rows, family)
        self.assertEqual([row.items for row in found[:2]], [[small_eng], [u(0x1B4)]], "the high-value rows first")
        self.assertEqual(([row.items for row in found[2:]], left), ([[u"w"], [u"x"], [u"y"], [u"z"]], 0))
        self.assertEqual(fc.selection_of(None), None)
        self.assertEqual(fc.selection_of(wolof).key, fc.language_key(wolof))
        self.assertEqual(fc.selection_of(wolof).kind, "language")

    def test_selection_text(self):
        results, _ = self.results()
        wolof, sami, far = [fc.selection_of(results[k]) for k in (2, 3, 5)]
        tail = u" Click it again, or an empty part of its list, to unselect it."
        self.assertEqual(fc.selection_text(None, 0), u"")
        self.assertEqual(fc.selection_text(wolof, 0), u"Wolof misses 2 glyphs." + tail)
        self.assertEqual(fc.selection_text(sami, 0), u"Sami misses 1 glyph." + tail)
        self.assertIn(u" 1 more is not listed (the first 3 are).", fc.selection_text(far, 1))
        self.assertIn(u" 2 more are not listed (the first 2 are).", fc.selection_text(far, 2))
        covered = fc.check_language(language(u"a b", name=u"Whole"), font([0x61, 0x62]))
        self.assertEqual(fc.selection_text(fc.selection_of(covered), 0), u"Whole misses nothing.")
        self.assertIn(u"<b>Wolof</b> misses", fc.selection_text(wolof, 0, lambda text: u"<b>%s</b>" % text))
        family = lambda members: fc.Selection("family", u"Kwa", members, ("family", u"Kwa"))
        self.assertEqual(fc.selection_text(family([results[2], results[5], covered]), 0),
                         u"Kwa: its 2 languages not covered miss 6 glyphs." + tail)
        self.assertEqual(fc.selection_text(family([results[3], covered]), 0),
                         u"Kwa: its 1 language not covered misses 1 glyph." + tail)
        self.assertEqual(fc.selection_text(family([results[2]]), 0),
                         u"Kwa: its 1 language not covered misses 2 glyphs." + tail)
        self.assertEqual(fc.selection_text(family([results[3], results[3]]), 0),
                         u"Kwa: its 2 languages not covered miss 1 glyph." + tail)
        self.assertEqual(fc.selection_text(family([covered]), 0), u"Kwa: the font covers its 1 language.")
        self.assertEqual(fc.selection_text(family([covered, covered]), 0), u"Kwa: the font covers all its 2 languages.")
        # The tabs' captions: the high-value list's with its count of rows, the selection's with its name
        self.assertEqual(fc.value_title(34), u"High-value missing glyphs (34)")
        self.assertEqual(fc.value_title(0), u"High-value missing glyphs (0)")
        self.assertEqual(fc.selection_title(None), u"Select language, character set, or family",
                         "the owner's caption: the tab works on families and character sets too")
        self.assertEqual(fc.selection_title(wolof), u"Wolof (2)")
        self.assertEqual(fc.absent_caption(48), u"Show the 48 scripts whose glyphs are fully missing from the font.")
        self.assertEqual(fc.absent_caption(1), u"Show the 1 script whose glyphs are fully missing from the font.")

    def test_missed_language_gained_once_all_checked(self):
        results, _ = self.results()
        names = lambda checked: [r.language.name for r in fc.languages_gained(results, checked)]
        self.assertEqual(names([u"x", u"y", u"z"]), [])
        self.assertEqual(names([u"x", u"y", u"z", u"w"]), [u"Far"], "its rows are listed while it is selected")

    def test_what_else_a_language_needs_is_cut_short(self):
        many = fc.check_language(language(u"a b c d e f g h i j", name=u"Many"), font([]))
        row = fc.AddRow([u"a"], [many], [])
        self.assertEqual(fc.others_text(many, row), u"b c d e f g +3")
        self.assertEqual(fc.row_languages_text(row), u"Many (with b c d e f g +3)")
        twice = fc.check_language(language(u"a b b c d e f g h"), font([]))
        self.assertEqual(fc.others_text(twice, row), u"b b c d e f +2", "a list counted as it is listed")

    def test_what_else_a_script_needs_costs_the_same_at_any_size(self):
        """A script's set selected (Han: 103,351 missing) gave each of its tab's 200 rows the text of
        every character it misses, twice (half a minute): only the first few are made into text now."""
        made = []
        shown_text = fc.shown_text

        def counting(item):
            made.append(item)
            return shown_text(item)

        han = fc.ScriptSet(u"Test ideographs", u"4E00-9FFF 20000-2A6DF", u"3001-3003")
        r = fc.check_entry(han, font(list(range(0x20, 0x7F))))
        self.assertIsInstance(fc.needs(r), fc.CodeItems)
        rows, left = fc.selection_rows([], fc.selection_of(r))
        self.assertEqual(len(rows), fc.FLOAT_MOST)
        fc.shown_text = counting
        try:
            texts = [(fc.row_languages_text(row), fc.row_tip(row)) for row in rows]
        finally:
            fc.shown_text = shown_text
        self.assertLessEqual(len(made), 2 * 7 * len(rows), "at most seven characters made into text per row and column")
        total = 0x9FFF - 0x4E00 + 1 + 0x2A6DF - 0x20000 + 1
        second = rows[1].items[0]
        expected = u" ".join(u(code) for code in range(0x4E00, 0x4E00 + 7) if u(code) != second)[:6 * 2 - 1]
        self.assertEqual(texts[1][0], u"Test ideographs (with %s +%d)" % (expected, total - 1 - 6),
                         "what the row shows: the same as before")


class LanguageListTests(unittest.TestCase):
    """The languages list: a search looks through every language (the owner searched "lao" and found
    nothing: only the scripts the font has were searched), its order, and the choice of statuses."""

    def scripts(self, statuses=fc.STATUS_FILTERS[0][2]):
        lao = u(0xE81) + u" " + u(0xE82)
        languages = [language(u"a b", name=u"Zulu"), language(u"a b c", name=u"Azeri"),
                     language(u"a b", name=u"\N{LATIN CAPITAL LETTER O WITH DIAERESIS}mie"),
                     language(u"a x y z w v", name=u"Far"),
                     language(u"a b", name=u"Old Latin", status=u"historical"),
                     language(u"a b", name=u"Esperanto", status=u"constructed"),
                     language(lao, script=u"Lao", name=u"Lao"),
                     language(u(0x3B1) + u" " + u(0x3B2), script=u"Greek", name=u"Ancient Greek", status=u"historical")]
        f = font([0x61, 0x62])
        return fc.coverage(languages, f, 3, statuses is None, statuses), fc.left_out(languages, f, 3, statuses)

    def names(self, sections):
        return [(s.heading(), [r.language.name for r in s.results]) for s in sections]

    def test_statuses(self):
        count = lambda found: sorted(r.language.name for s in found for r in s.results)
        scripts, others = self.scripts()
        self.assertNotIn(u"Old Latin", count(scripts))
        self.assertIn(u"Esperanto", count(scripts), "constructed languages are in to start with")
        self.assertEqual(sorted(r.language.name for r in others), [u"Ancient Greek", u"Old Latin"])
        by_key = dict((key, statuses) for key, _, statuses in fc.STATUS_FILTERS)
        self.assertEqual([key for key, _, _ in fc.STATUS_FILTERS], ["current", "living", "historical", "all"])
        scripts, others = self.scripts(by_key["living"])
        self.assertNotIn(u"Esperanto", count(scripts))
        self.assertEqual(len(others), 3)
        scripts, others = self.scripts(by_key["historical"])
        self.assertEqual(count(scripts), [u"Ancient Greek", u"Old Latin"])
        self.assertEqual(len(others), 6)
        scripts, others = self.scripts(by_key["all"])
        self.assertEqual((len(count(scripts)), others), (8, []))

    def test_listed_without_a_search(self):
        scripts, others = self.scripts()
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"", None, "reach", others)
        self.assertEqual(self.names(sections), [(u"Latin (5)", [u"Azeri", u"Esperanto", u"Zulu",
                                                                u"\N{LATIN CAPITAL LETTER O WITH DIAERESIS}mie", u"Far"])])
        self.assertEqual(hidden, 0)
        self.assertEqual(fc.languages_line(sections, u"", 0, 1, 2),
                         u"1 language of the scripts not listed here is hidden: a search finds it too. "
                         u"2 languages are left out by the choice of languages above: a search finds them too.")
        self.assertEqual(fc.languages_line(sections, u"", 0, 2, 1),
                         u"2 languages of the scripts not listed here are hidden: a search finds them too. "
                         u"1 language is left out by the choice of languages above: a search finds it too.")
        self.assertEqual(fc.languages_line(sections, u"", 0, 0, 0), u"", "nothing hidden: no line")

    def test_search_finds_every_language(self):
        scripts, others = self.scripts()
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"lao", None, "reach", others)
        self.assertEqual(self.names(sections), [(u"Lao (1): a script the font has none of", [u"Lao"])])
        self.assertEqual(fc.languages_line(sections, u"lao", hidden),
                         u"1 language matches. 1 is under a heading that says why it is not listed otherwise.")
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"LAT", None, "reach", others)
        self.assertEqual(self.names(sections),
                         [(u"Historical languages (1): left out by the choice of languages above", [u"Old Latin"])])
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"a", None, "az", others)
        self.assertEqual([s.title for s in sections], [u"Latin", u"Lao", u"Historical languages"])
        self.assertEqual([s.why for s in sections], [u"", fc.ABSENT_WHY, fc.STATUS_WHY])
        self.assertEqual(fc.languages_line(sections, u"a", hidden),
                         u"6 languages match. 3 are under a heading that says why they are not listed otherwise.")
        # A script the font has, hidden by a click on another script: said so
        both = fc.coverage([language(u"a b", name=u"One"), language(u(0x3B1), script=u"Greek", name=u"Two")],
                           font([0x61, 0x62, 0x3B1]))
        sections, hidden = fc.language_sections(both, [u"Latin"], u"two")
        self.assertEqual(self.names(sections), [(u"Greek (1): not the script chosen above", [u"Two"])])
        self.assertEqual(fc.language_sections(both, [u"Latin"], u"zzz"), ([], 0))
        self.assertEqual(fc.languages_line([], u"zzz"), u"No language matches.")
        self.assertEqual(fc.languages_line([], u"zzz", nouns=fc.RIGHT_NOUNS["sets"]), u"No character set matches.")

    def test_level_holds_finds_back(self):
        scripts, others = self.scripts()
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"lao", "covered", "reach", others)
        self.assertEqual((sections, hidden), ([], 1))
        self.assertEqual(fc.languages_line(sections, u"lao", hidden, level="covered"),
                         u"1 language matches, but is not covered: choose All to see it.")
        self.assertEqual(fc.languages_line([], u"box", 2, level="started", nouns=fc.RIGHT_NOUNS["sets"]),
                         u"2 character sets match, but are not started: choose All to see them.")
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"a", "covered", "reach", others)
        self.assertEqual(self.names(sections)[0], (u"Latin (1)", [u"Esperanto"]))
        self.assertEqual(hidden, 4, "Azeri, Far, Lao, and Ancient Greek")
        self.assertEqual(fc.languages_line(sections, u"a", hidden, level="covered"),
                         u"2 languages match. 1 is under a heading that says why it is not listed otherwise. "
                         u"4 more match, but are not covered: choose All to see them.")
        self.assertEqual(fc.languages_line(sections, u"a", 1, level="nearly"),
                         u"2 languages match. 1 is under a heading that says why it is not listed otherwise. "
                         u"1 more matches, but is not within reach: choose All to see it.")
        sections, hidden = fc.language_sections(scripts, [u"Latin"], u"", "covered", "reach", others)
        self.assertEqual(hidden, 0, "without a search the level is a plain filter")

    def test_sorts(self):
        scripts, _ = self.scripts()
        latin = scripts[0].results
        order = lambda sort: [r.language.name for r in fc.sort_languages(latin, sort)]
        omie = u"\N{LATIN CAPITAL LETTER O WITH DIAERESIS}mie"
        self.assertEqual([key for key, _ in fc.SORTS], ["reach", "most", "least", "az", "za"])
        self.assertEqual(order("reach"), [u"Azeri", u"Esperanto", u"Zulu", omie, u"Far"])
        self.assertEqual(order("most"), [u"Esperanto", omie, u"Zulu", u"Azeri", u"Far"], "covered, within reach, missed")
        self.assertEqual(order("least"), [u"Far", u"Azeri", u"Esperanto", omie, u"Zulu"])
        self.assertEqual(order("az"), [u"Azeri", u"Esperanto", u"Far", omie, u"Zulu"], "a letter with a mark with its letter")
        self.assertEqual(order("za"), order("az")[::-1])
        self.assertEqual(order("unknown"), order("reach"))

    def test_lao_in_the_data(self):
        languages = fc.name_languages(fc.load_languages(LANGUAGES_FILE), None)  # (by their own names only)
        self.assertEqual(sorted(set(l.status for l in languages)), [u"constructed", u"historical", u"living"])
        statuses = fc.STATUS_FILTERS[0][2]
        f = font(LATIN_1)
        scripts, others = fc.coverage(languages, f, 3, False, statuses), fc.left_out(languages, f, 3, statuses)
        shown = [s.script for s in scripts if s.present]
        self.assertNotIn(u"Lao", shown)
        sections, _ = fc.language_sections(scripts, shown)
        self.assertNotIn(u"Lao", [r.language.name for s in sections for r in s.results])
        sections, _ = fc.language_sections(scripts, shown, u"lao", None, "reach", others)
        self.assertEqual(self.names(sections), [(u"Lao (1): a script the font has none of", [u"Lao"])])
        sections, _ = fc.language_sections(scripts, shown, u"lat", None, "reach", others)
        self.assertIn((u"Historical languages (1): left out by the choice of languages above", [u"Latin"]),
                      self.names(sections))
        every = len(languages)
        self.assertEqual(sum(len(s.results) for s in scripts) + len(others), every, "no language outside both")


class CharacterSetTests(unittest.TestCase):
    """Character sets that are no languages (IPA, mathematics, Unicode blocks, foundries' sets), checked
    and listed as the languages are."""

    def sets(self):
        return [fc.Language(u"ipa-test", u"IPA test", u"", u"Phonetics", u"set", u"", 0,
                            [u"a", u(0x259), u(0x283)], [], u"", kind="set", definition=u"A test's definition."),
                fc.Language(u"box-test", u"Box test", u"", u"Symbols and punctuation", u"set", u"", 0,
                            [u"a"], [], u"", kind="set", definition=u"Another.")]

    def test_checked_as_languages(self):
        ipa, box = [fc.check_language(one, font([0x61, 0x283])) for one in self.sets()]
        self.assertEqual((ipa.level, ipa.missing), ("nearly", [u(0x259)]))
        self.assertEqual(box.level, "covered")
        self.assertEqual(fc.language_note(ipa), u"1 of 3 missing")
        self.assertEqual(fc.language_note(box), u"")
        self.assertEqual(fc.coverage_tip(ipa), u"IPA test: within reach (the font has 2 of its 3 characters).\n"
                                               u"A test's definition.\nMissing: " + u(0x259))
        self.assertEqual(fc.coverage_tip(box), u"Box test: covered (the font has 1 of its 1 character).\nAnother.")
        self.assertTrue(fc.language_matches(ipa, u"phonet"), "a set's group")
        self.assertTrue(fc.language_matches(ipa, u"ipa"))
        self.assertFalse(fc.language_matches(box, u"ipa"))
        found, left = fc.selection_rows([], fc.selection_of(ipa))
        self.assertEqual(([row.items for row in found], left), ([[u(0x259)]], 0), "handed to the selection's tab")
        self.assertEqual(fc.selection_of(ipa).kind, "set")
        many = fc.check_language(fc.Language(u"m", u"Many", u"", u"Mathematics", u"set", u"", 0,
                                             [u(code) for code in range(0x2200, 0x2300)], [], u"", kind="set"), font([]))
        self.assertEqual(fc.language_note(many), u"256 of 256 missing")
        self.assertIn(u" and %d more" % (256 - fc.TIP_SHOWN), fc.coverage_tip(many))

    def test_listed_in_a_tab_of_their_own(self):
        """The owner: "this should get tabs instead to separately list languages from character sets"."""
        results = [fc.check_language(one, font([0x61, 0x283])) for one in self.sets()]
        scripts = fc.coverage([language(u"a b", name=u"One")], font([0x61, 0x62]))
        sections, _ = fc.language_sections(scripts, [u"Latin"])
        self.assertEqual([s.heading() for s in sections], [u"Latin (1)"], "the languages alone")
        nouns = fc.RIGHT_NOUNS["sets"]
        sections, hidden = fc.set_sections(results)
        self.assertEqual([s.heading() for s in sections], [u"Phonetics (1)", u"Symbols and punctuation (1)"])
        self.assertEqual((hidden, fc.languages_line(sections, nouns=nouns)), (0, u""))
        sections, _ = fc.set_sections(results, u"test")
        self.assertEqual(fc.languages_line(sections, u"test", nouns=nouns), u"2 character sets match.")
        sections, _ = fc.set_sections(results, u"box")
        self.assertEqual(fc.languages_line(sections, u"box", nouns=nouns), u"1 character set matches.")
        sections, hidden = fc.set_sections(results, u"", "nearly")
        self.assertEqual([s.heading() for s in sections], [u"Phonetics (1)"], "the level filters them too")
        sections, hidden = fc.set_sections(results, u"box", "nearly")
        self.assertEqual((sections, hidden), ([], 1))
        self.assertEqual(fc.languages_line(sections, u"box", hidden, level="nearly", nouns=nouns),
                         u"1 character set matches, but is not within reach: choose All to see it.")
        self.assertEqual([key for key, _ in fc.RIGHT_TABS], ["languages", "sets", "families"])
        self.assertEqual([label for _, label in fc.RIGHT_TABS], [u"Languages", u"Character sets", u"Families"])
        self.assertEqual(fc.languages_gained(results, [u(0x259)]), [results[0]])

    def test_data(self):
        path = os.path.join(HERE, os.pardir, "checks", fc.SETS_FILE)
        with open(path, "rb") as handle:
            raw = handle.read()
        self.assertTrue(all(byte < 128 for byte in bytearray(raw)), "an ASCII file")
        every = fc.load_character_sets(path)
        self.assertIs(fc.load_character_sets(path), every, "read once")
        self.assertEqual(len(set(one.iso for one in every)), len(every), "each its own id")
        self.assertEqual(len(set(one.name for one in every)), len(every), "each its own name")
        sets = [one for one in every if not isinstance(one, fc.ScriptSet)]  # (the scripts: ScriptTests)
        self.assertEqual(len(sets), 99)
        groups = []
        for one in sets:
            if one.script not in groups:
                groups.append(one.script)
        self.assertEqual(groups, [u"Phonetics", u"Mathematics", u"Symbols and punctuation", u"Notation",
                                  u"Games and pictographs", u"Foundries"])
        for one in sets:
            self.assertEqual((one.kind, one.status, one.auxiliary, one.marks), ("set", u"set", [], u""), one.name)
            self.assertTrue(one.base and one.definition.endswith(u".") and one.script, one.name)
            self.assertEqual(len(set(one.base)), len(one.base), one.name)
        by_id = dict((one.iso, one) for one in sets)
        schwa = u(0x259)
        self.assertIn(schwa, by_id[u"gf-phonetics-ipastandard"].base, "the schwa that prompted these sets")
        self.assertIn(schwa, by_id[u"block-0250"].base)
        self.assertEqual(len(by_id[u"block-0250"].base), 96, "IPA Extensions: every code point assigned")
        self.assertEqual(by_id[u"block-0250"].script, u"Phonetics")
        self.assertIn(u(0x1D400), by_id[u"block-1d400"].base, "past U+FFFF, either build")
        self.assertIn(u(0x2211), by_id[u"unicode-math"].base)
        self.assertNotIn(u(0x2061), by_id[u"unicode-math"].base, "a format character: no glyph is drawn for it")
        self.assertNotIn(u(0x200B), by_id[u"block-2000"].base)
        self.assertIn(u(0x20AC), by_id[u"unicode-sc"].base)
        self.assertIn(u"$", by_id[u"unicode-sc"].base, "any block's")
        self.assertIn(u(0x2500), by_id[u"block-2500"].base)
        # The blocks added after the survey of Unicode 17.0: notation, games, pictographs, more symbols
        for key, name, group, count in ((u"block-1d100", u"Musical Symbols (Unicode block)", u"Notation", 225),
                                        (u"block-2800", u"Braille Patterns (Unicode block)", u"Notation", 256),
                                        (u"block-1d2e0", u"Mayan Numerals (Unicode block)", u"Notation", 20),
                                        (u"block-1fa00", u"Chess Symbols (Unicode block)", u"Games and pictographs", 102),
                                        (u"block-1fb00", u"Symbols for Legacy Computing (Unicode block)",
                                         u"Symbols and punctuation", 250),
                                        (u"block-1f700", u"Alchemical Symbols (Unicode block)",
                                         u"Symbols and punctuation", 128)):
            self.assertEqual((by_id[key].name, by_id[key].script, len(by_id[key].base)), (name, group, count))
        self.assertNotIn(u(0x1D173), by_id[u"block-1d100"].base, "the musical format characters: no glyph")
        for one in sets:  # (no private-use, surrogate, or control character in any set)
            for item in one.base:
                for code in fc.code_points(item):
                    self.assertFalse(0xE000 <= code <= 0xF8FF or 0xD800 <= code <= 0xDFFF or code < 0x20
                                     or 0xF0000 <= code, (one.name, code))
        self.assertTrue(set(by_id[u"adobe-latin-1"].base) <= set(by_id[u"adobe-latin-2"].base))
        clusters = [item for item in by_id[u"adobe-latin-4"].base if len(fc.code_points(item)) > 1]
        self.assertEqual(len(clusters), 2, "letters with marks that have no single character")
        for name in (u"Unicode", u"Google Fonts", u"Adobe"):
            self.assertTrue([one for one in sets if name in one.definition], name)
        with open(os.path.join(HERE, os.pardir, "checks", "character_sets_LICENSE"), "rb") as handle:
            notice = handle.read().decode("utf-8")
        for words in (u"Unicode License V3", u"Apache License", u"MIT License", u"Adobe Systems Incorporated",
                      u"googlefonts/glyphsets"):
            self.assertIn(words, notice)

    def test_covered_by_a_font_with_every_character(self):
        sets = fc.load_character_sets(os.path.join(HERE, os.pardir, "checks", fc.SETS_FILE))
        ipa = [one for one in sets if one.iso == u"gf-phonetics-ipastandard"][0]
        codes = [code for item in ipa.base for code in fc.code_points(item)]
        self.assertEqual(fc.check_language(ipa, font(codes)).level, "covered")
        without = fc.check_language(ipa, font([code for code in codes if code != 0x259]))
        self.assertEqual((without.level, without.missing), ("nearly", [u(0x259)]))

    def test_no_file(self):
        self.assertEqual(fc.load_character_sets(os.path.join(HERE, "no_such_file.json")), [])


FAMILIES_FILE = os.path.join(HERE, os.pardir, "checks", fc.FAMILIES_FILE)


class FamilyTests(unittest.TestCase):
    """The Families tab: the languages under Glottolog's families and branches, each node counted in
    the scripts' four levels; the languages' other names; the languages Hyperglot does not describe."""

    def families(self):
        nodes = [[u"Indo-European", -1], [u"Classical Indo-European", 0], [u"Germanic", 1], [u"West Germanic", 2],
                 [u"North Germanic", 2], [u"Italic", 1], [u"Romance", 5], [u"Uralic", -1], [u"Finnic", 7],
                 [u"Language isolates", -1], [u"East Germanic", 2]]
        places = {u"eng": 3, u"deu": 3, u"dan": 4, u"got": 10, u"fra": 6, u"fin": 8, u"eus": 9}
        unlisted = [[u"ktz", u"South-Eastern Ju", [u"Ju|'hoan", u"Kung"]], [u"juu", u"Ju", [u"Sho"]],
                    [u"aaa", u"Ghotuo", []], [u"gho", u"Ghomara", []], [u"ghq", u"Ghera", []]]
        return fc.Families(nodes, places, {u"fin": [u"Suomi"]}, unlisted, u"Language isolates")

    def results(self):
        def one(iso, name, base):
            return fc.Language(iso, name, u"", u"Latin", u"living", u"verified", 0, base.split(), [], u"")
        languages = [one(u"eng", u"English", u"a b"), one(u"deu", u"German", u"a b c"), one(u"dan", u"Danish", u"a b"),
                     one(u"got", u"Gothic", u"x y z w v"), one(u"fra", u"French", u"a b"),
                     one(u"fin", u"Finnish", u"a x y z w"), one(u"eus", u"Basque", u"a b"), one(u"xxx", u"Unknown", u"a b")]
        families = self.families()
        fc.name_languages(languages, families)
        f = font([0x61, 0x62])
        return [fc.check_language(l, f, 1) for l in languages], families

    def shape(self, node):
        return (node.name, [self.shape(one) for one in node.children], [r.language.name for r in node.results])

    def test_paths(self):
        families = self.families()
        self.assertEqual(families.path(u"eng"), (u"Indo-European", u"Classical Indo-European", u"Germanic", u"West Germanic"))
        self.assertEqual(families.path(u"eus"), (u"Language isolates",))
        self.assertEqual(families.path(u"xxx"), (), "a code Glottolog does not classify")
        looped = fc.Families([[u"A", 1], [u"B", 0]], {u"aaa": 0})
        self.assertEqual(len(looped.path(u"aaa")), 64, "a file that loops is read without hanging")

    def test_tree(self):
        results, families = self.results()
        self.assertEqual([r.level for r in results],
                         ["covered", "nearly", "covered", "missed", "covered", "started", "covered", "covered"])
        root, hidden = fc.family_tree(results, families)
        self.assertEqual(hidden, 0)
        self.assertEqual(self.shape(root), (u"", [
            (u"Indo-European", [(u"Germanic", [(u"West Germanic", [], [u"German", u"English"])], [u"Danish", u"Gothic"])],
             [u"French"]),
            (u"Language isolates", [], [u"Basque"]),
            (u"Uralic", [], [u"Finnish"]),
            (fc.UNCLASSIFIED, [], [u"Unknown"])], []),
            "a branch holding one branch is skipped (Classical Indo-European, Finnic), one holding one language gives "
            "way to it (North Germanic, Romance); a family stays, even with one language; the unclassified come last")
        indo = root.children[0]
        self.assertEqual(fc.level_counts(indo.all_results()), [3, 1, 0, 1], "the same four levels as a script's bar")
        self.assertEqual(fc.coverage_text(fc.level_counts(indo.all_results())), u"3 of 5 languages (1 within reach)")
        germanic = indo.children[0]
        self.assertEqual(germanic.path, (u"Indo-European", u"Classical Indo-European", u"Germanic"),
                         "its place as Glottolog has it, whatever branches the tree skipped: it finds the node again")
        self.assertEqual(fc.family_tip(germanic), u"Germanic: 2 covered, 1 within reach, 0 started, 1 missed.\n"
                                                  u"Glottolog: Indo-European > Classical Indo-European > Germanic.")
        self.assertEqual(fc.family_tip(indo), u"Indo-European: 3 covered, 1 within reach, 0 started, 1 missed.")
        names = lambda sort: [one.name for one in fc.family_tree(results, families, u"", None, sort)[0].children]
        self.assertEqual(names("az"), [u"Indo-European", u"Language isolates", u"Uralic", fc.UNCLASSIFIED])
        self.assertEqual(names("za"), [u"Uralic", u"Language isolates", u"Indo-European", fc.UNCLASSIFIED])
        self.assertEqual(names("most"), [u"Language isolates", u"Indo-European", u"Uralic", fc.UNCLASSIFIED])
        self.assertEqual(names("least"), [u"Uralic", u"Indo-European", u"Language isolates", fc.UNCLASSIFIED])

    def test_search_and_level(self):
        results, families = self.results()
        root, hidden = fc.family_tree(results, families, u"germanic")
        self.assertEqual(sorted(r.language.name for r in root.all_results()), [u"Danish", u"English", u"German", u"Gothic"],
                         "a family named: its languages")
        self.assertEqual(fc.families_line(root, u"germanic", hidden), u"4 languages match in 1 family.")
        root, hidden = fc.family_tree(results, families, u"suomi")
        self.assertEqual([(r.language.name, r.found_by) for r in root.all_results()], [(u"Finnish", u"Suomi")])
        self.assertEqual(fc.families_line(root, u"suomi", hidden), u"1 language matches in 1 family.")
        root, hidden = fc.family_tree(results, families, u"finn")
        self.assertEqual([(r.language.name, r.found_by) for r in root.all_results()], [(u"Finnish", None)])
        root, hidden = fc.family_tree(results, families, u"germanic", "started")
        self.assertEqual(([r.language.name for r in root.all_results()], hidden), ([], 4), "its four languages, held back")
        self.assertEqual(fc.families_line(root, u"germanic", hidden, "started"),
                         u"4 languages match, but are not started: choose All to see them.")
        root, hidden = fc.family_tree(results, families, u"", "started")
        self.assertEqual(([one.name for one in root.children], hidden), ([u"Uralic"], 0))
        self.assertEqual(fc.families_line(root), u"Families and branches as Glottolog 5.4 classifies them (CC BY 4.0).")
        root, hidden = fc.family_tree(results, families, u"zzz")
        self.assertEqual(fc.families_line(root, u"zzz", hidden), u"No family or language matches.")
        root, hidden = fc.family_tree(results, families, u"eng", "nearly")
        self.assertEqual(fc.families_line(root, u"eng", hidden, "nearly"),
                         u"1 language matches, but is not within reach: choose All to see it.")
        root, hidden = fc.family_tree(results, families, u"a", "nearly")
        self.assertTrue(fc.families_line(root, u"a", hidden, "nearly").startswith(
            u"1 language matches in 1 family. %d more match, but are not within reach" % hidden))

    def test_families_counted_hold_a_match(self):
        """"N languages match in M families": Not classified is no family, and a family listed for its
        languages that cannot be checked alone holds no match."""
        results, families = self.results()
        uncovered = {u"Khoe-Kwadi": [fc.Uncovered(u"ktz", u"Kungish", (), u"Khoe-Kwadi")]}
        root, hidden = fc.family_tree(results, families, u"ish", None, "reach", uncovered)
        self.assertEqual(sorted(one.name for one in root.children), [u"Indo-European", u"Khoe-Kwadi", u"Uralic"])
        self.assertEqual(fc.families_line(root, u"ish", hidden), u"3 languages match in 2 families.")
        root, hidden = fc.family_tree(results, families, u"n", None, "reach", uncovered)
        self.assertEqual([one.name for one in root.children][-1], fc.UNCLASSIFIED)
        self.assertEqual(fc.families_line(root, u"n", hidden), u"8 languages match: 7 in 3 families, 1 not classified.")
        root, hidden = fc.family_tree(results, families, u"unknown")
        self.assertEqual(fc.families_line(root, u"unknown", hidden), u"1 language matches, not classified.")

    def test_no_file(self):
        results, _ = self.results()
        self.assertIsNone(fc.load_families(os.path.join(HERE, "no_such_file.json")))
        root, hidden = fc.family_tree(results, None)
        self.assertEqual([(one.name, len(one.results)) for one in root.children], [(fc.UNCLASSIFIED, 8)])
        self.assertIn(u"is not installed", fc.families_line(root, classified=False))

    def test_languages_hyperglot_does_not_describe(self):
        """The owner searched for Juu and !Kung varieties and found nothing: Hyperglot documents no
        orthography for them. A search now says that such a language exists and cannot be checked."""
        families = self.families()
        self.assertEqual(families.unlisted_matches(u"ktz"), [(u"ktz", u"South-Eastern Ju", None)], "by its code")
        self.assertEqual(families.unlisted_matches(u"HOAN"), [(u"ktz", u"South-Eastern Ju", u"Ju|'hoan")], "by another name")
        self.assertEqual(families.unlisted_matches(u"ju"), [(u"juu", u"Ju", None)], "a short text: a whole name only")
        self.assertEqual(families.unlisted_matches(u"juu"), [(u"juu", u"Ju", None)])
        self.assertEqual([iso for iso, _, _ in families.unlisted_matches(u"gho")], [u"gho", u"aaa"],
                         "a code first, then the names that start with the text")
        self.assertEqual(families.unlisted_matches(u""), [])
        self.assertEqual(families.unlisted_matches(u"zz"), [])
        self.assertEqual(fc.unlisted_line([]), u"")
        self.assertEqual(fc.unlisted_line(families.unlisted_matches(u"hoan")),
                         u"Glottolog also lists South-Eastern Ju (ktz, also Ju|'hoan), which none of Font Check's "
                         u"sources documents an orthography for: Font Check cannot check it.")
        self.assertEqual(fc.unlisted_line(families.unlisted_matches(u"gh"), 2), u"")
        self.assertEqual(fc.unlisted_line(families.unlisted_matches(u"gho"), 2),
                         u"Glottolog also lists 2 languages that none of Font Check's sources documents an "
                         u"orthography for, which Font Check cannot check: Ghomara (gho) and Ghotuo (aaa).")
        self.assertEqual(fc.unlisted_line(families.unlisted_matches(u"ghe") + families.unlisted_matches(u"gho"), 2),
                         u"Glottolog also lists 3 languages that none of Font Check's sources documents an "
                         u"orthography for, which Font Check cannot check: Ghera (ghq), Ghomara (gho), and 1 more.")

    def test_data(self):
        families = fc.load_families(FAMILIES_FILE)
        self.assertIs(fc.load_families(FAMILIES_FILE), families, "read once")
        languages = fc.load_languages(LANGUAGES_FILE, ORTHOGRAPHIES_FILE)  # (Hyperglot's and the other sources')
        isos = set(l.iso for l in languages)
        self.assertEqual(families.path(u"eng")[0], u"Indo-European")
        self.assertIn(u"Germanic", families.path(u"eng"))
        self.assertEqual(families.path(u"hrv")[-1], u"Serbian-Croatian-Bosnian", "a code Glottolog gives a dialect")
        self.assertEqual(families.path(u"eus"), (u"Language isolates",))
        self.assertEqual(families.path(u"que"), (u"Quechuan",), "a macrolanguage placed by hand")
        self.assertEqual(sorted(iso for iso in isos if not families.path(iso)), [u"xrg"], "all classified but one")
        self.assertTrue(set(families.aliases) <= isos)
        self.assertIn(u"Nama", families.aliases[u"naq"], "Khoekhoe's better-known name")
        own = dict((l.iso, set()) for l in languages)
        for l in languages:
            own[l.iso].update(fc.fold(name) for name in (l.name, l.autonym) if name)
        for iso, names in families.aliases.items():
            folded = [fc.fold(name) for name in names]
            self.assertEqual(len(set(folded)), len(folded), iso)
            self.assertFalse(own[iso] & set(folded), "%s: a name the list shows already" % iso)
        unlisted = dict((iso, (name, others)) for iso, name, others, _ in families.unlisted)
        self.assertFalse(set(unlisted) & isos, "only languages no source describes")
        self.assertNotIn(u"ktz", unlisted, "South-Eastern Ju is checked now (Google Fonts' language data)")
        self.assertIn(u"South-Eastern Ju", families.aliases[u"ktz"], "and still found by Glottolog's name")
        self.assertEqual(families.path(u"ktz")[0], u"Kxa")
        self.assertEqual(unlisted[u"huc"][0], u"Amkoe", "a language no source describes yet")
        self.assertIn(u"huc", [iso for iso, _, _ in families.unlisted_matches(u"hoan")])
        self.assertTrue(5000 < len(unlisted) < 5200, "6,734 with Hyperglot alone")
        with open(os.path.join(HERE, os.pardir, "checks", "language_families_LICENSE"), "rb") as handle:
            notice = handle.read().decode("utf-8")
        for words in (u"Glottolog 5.4", u"Creative Commons Attribution 4.0 International", u"Changes made",
                      u"Max Planck", u"84977fcab99ddca540550ba99984a32e908a7fcf"):
            self.assertIn(words, notice)

    def test_real_tree_and_search(self):
        families = fc.load_families(FAMILIES_FILE)
        languages = fc.name_languages(fc.load_languages(LANGUAGES_FILE), families)
        f = font(LATIN_1)
        scripts = fc.coverage(languages, f, 3, True, None)
        results = [r for s in scripts for r in s.results]
        root, _ = fc.family_tree(results, families)
        self.assertEqual(len(root.all_results()), len(results), "each orthography once")
        self.assertGreater(len(root.children), 50)
        self.assertEqual(root.children[-1].name, fc.UNCLASSIFIED)
        self.assertEqual([r.language.iso for r in root.children[-1].results], [u"xrg"])
        self.assertEqual(root.children[0].name, u"Indo-European", "the most languages covered or within reach first")

        def check(node, top):
            for one in node.children:
                self.assertFalse(len(one.children) == 1 and not one.results, "%s holds one branch only" % one.name)
                self.assertTrue(top or one.children or len(one.results) > 1, "%s holds one language only" % one.name)
                check(one, False)
        check(root, True)
        deepest = max(len(families.path(l.iso)) for l in languages)
        depth = lambda node: 1 + max([depth(one) for one in node.children] or [0])
        self.assertLess(depth(root) - 1, deepest, "shallower than Glottolog's own tree")
        sections, _ = fc.language_sections(scripts, [s.script for s in scripts], u"nama")
        found = dict((r.language.name, r.found_by) for s in sections for r in s.results)
        self.assertEqual(found.get(u"Khoekhoe"), u"Nama")
        # A search runs at each keystroke: one text per language to look through, not its names one by one
        import time
        started = time.time()
        for text in (u"n", u"na", u"nam", u"nama", u"deutsch", u"zz", u"ju", u"hoan", u"kung", u"a"):
            fc.language_sections(scripts, [s.script for s in scripts], text)
            fc.family_tree(results, families, text)
            families.unlisted_matches(text)
        self.assertLess(time.time() - started, 5.0, "ten searches over every tab's data")
        found = [r.language.iso for s in fc.language_sections(scripts, [s.script for s in scripts], u"hoan")[0]
                 for r in s.results]
        self.assertNotIn(u"ktz", found, "Hyperglot has no Ju variety")
        fc.name_languages(languages, None)  # (the languages are read once and shared: left as they were)
        self.assertIn(u"Amkoe (huc", fc.unlisted_line(families.unlisted_matches(u"hoan")))
        self.assertNotIn(u"(ktz", fc.unlisted_line(families.unlisted_matches(u"hoan")), "checked now: not named here")


def other_language(base, name=u"Other", evidence=fc.DECLARED, source=u"SIL's Locale Data Repository (SLDR)",
                   status=fc.NOT_GIVEN, validity=u"unconfirmed", iso=u"oth"):
    """A language of the second data file: its source, its evidence, and no status given."""
    one = fc.Language(iso, name, u"", u"Latin", status, validity, 0, base.split(), [], u"")
    one.source, one.evidence = source, evidence
    return one


class NotCoveredTests(unittest.TestCase):
    """The owner: "we should keep track of languages/scripts/families we are aware of but can't offer
    support for yet, inviting users to open an issue to enrich the dataset." The languages Glottolog
    lists that no source describes are counted family by family and listed under each family's last
    node; the scripts Unicode has that no orthography is written in close the Languages tab."""

    def test_data(self):
        families = fc.load_families(FAMILIES_FILE)
        by_family = families.uncovered()
        self.assertIs(families.uncovered(), by_family, "made once")
        self.assertEqual(sum(len(found) for found in by_family.values()), len(families.unlisted))
        self.assertEqual((len(by_family), len(by_family[u"Austronesian"])), (226, 880),
                         "Rade and Eastern Cham are checked now, from their keyboard layouts; Inland-Buhi-Daraga "
                         "Bikol, Eastern-Southern Bontok, and Tangga are described through their dialects")
        self.assertIn(families.isolates, by_family)
        counts = families.counts
        self.assertEqual((counts["described"], counts["not_described"], counts["glottolog_languages_with_iso"],
                          counts["families"], counts["families_without_a_described_language"]),
                         (2511, 5036, 7861, 240, 77))
        amkoe = [one for one in by_family[u"Kxa"] if one.iso == u"huc"][0]
        self.assertEqual((amkoe.name, amkoe.family), (u"Amkoe", u"Kxa"))
        names = [fc.fold(one.name) for one in by_family[u"Austronesian"]]
        self.assertEqual(names, sorted(names), "A to Z")
        old = fc.Families(unlisted=[[u"aaa", u"Ghotuo", []]])
        self.assertEqual(old.uncovered(), {}, "a file made before: the search still names them, nothing is listed")
        self.assertEqual(old.unlisted_matches(u"aaa"), [(u"aaa", u"Ghotuo", None)])
        scripts = fc.load_known_scripts(ORTHOGRAPHIES_FILE)
        self.assertIs(fc.load_known_scripts(ORTHOGRAPHIES_FILE), scripts, "read once")
        self.assertEqual((scripts.known, len(scripts.not_covered)), (172, 61))
        self.assertEqual(fc.scripts_section(scripts.not_covered, u"MONGOL"), [u"Mongolian"])
        self.assertEqual(fc.scripts_section(scripts.not_covered), scripts.not_covered)
        self.assertEqual(fc.scripts_section(scripts.not_covered, u"latin"), [])
        unlisted = set(row[0] for row in families.unlisted)
        recorded = set(iso for iso in scripts.of_languages if iso in unlisted)
        self.assertEqual(len(recorded), 4501, "of the 5,036: a script recorded by CLDR or Google's data")
        self.assertEqual(len([iso for iso in recorded if scripts.of_languages[iso] == [u"Latin"]]), 3957)
        empty = fc.load_known_scripts(os.path.join(HERE, "no_such_file.json"))
        self.assertEqual((empty.known, empty.not_covered, empty.of_languages), (0, [], {}))

    def test_tree(self):
        entry = lambda iso, name, family, others=(): fc.Uncovered(iso, name, others, family)
        uncovered = {u"Kxa": [entry(u"huc", u"Amkoe", u"Kxa", [u"Hoan"])],
                     u"Zeta": [entry(u"zza", u"Alpha", u"Zeta"), entry(u"zzb", u"Beta", u"Zeta")]}
        root, _ = fc.family_tree([], None, u"", None, "reach", uncovered)
        self.assertEqual([one.name for one in root.children], [u"Kxa", u"Zeta"], "families listed for them alone")
        last = root.children[1].children[-1]
        self.assertIsInstance(last, fc.UncoveredNode)
        self.assertEqual((last.name, last.path, [one.iso for one in last.entries]),
                         (fc.NOT_COVERED, (u"Zeta", fc.NOT_COVERED), [u"zza", u"zzb"]))
        self.assertEqual(root.children[1].uncovered, last.entries)
        self.assertEqual(root.all_results(), [])
        found, _ = fc.family_tree([], None, u"hoan", None, "reach", uncovered)
        self.assertEqual([(one.name, len(one.uncovered)) for one in found.children], [(u"Kxa", 1)], "by another name")
        found, _ = fc.family_tree([], None, u"zet", None, "reach", uncovered)
        self.assertEqual([(one.name, len(one.uncovered)) for one in found.children], [(u"Zeta", 2)], "a family named: all of it")
        found, _ = fc.family_tree([], None, u"zzb", None, "reach", uncovered)
        self.assertEqual([[e.iso for e in one.uncovered] for one in found.children], [[u"zzb"]], "by its code")
        self.assertEqual(fc.family_tree([], None, u"", "covered", "reach", uncovered)[0].children, [],
                         "a level kept alone: they have none")
        self.assertEqual(fc.families_line(found, u"zzb"), u"No language that can be checked matches.")
        self.assertEqual(fc.families_line(fc.family_tree([], None, u"qqq", None, "reach", uncovered)[0], u"qqq"),
                         u"No family or language matches.")
        # Under a family that has languages: after them, and the languages no one classifies stay last
        zulu = fc.check_language(language(u"a b", name=u"Zulu"), font([0x61]))
        mixed = dict(uncovered)
        mixed[fc.UNCLASSIFIED] = [entry(u"xxa", u"Lost", fc.UNCLASSIFIED)]
        root, _ = fc.family_tree([zulu], None, u"", None, "az", mixed)
        self.assertEqual([one.name for one in root.children], [u"Kxa", u"Zeta", fc.UNCLASSIFIED])
        loose = root.children[-1]
        self.assertEqual((loose.results, [type(one) for one in loose.children]), ([zulu], [fc.UncoveredNode]))
        self.assertEqual([one.name for one in fc.family_tree([zulu], None, u"", None, "za", mixed)[0].children],
                         [u"Zeta", u"Kxa", fc.UNCLASSIFIED])

    def test_texts(self):
        entry = lambda number: fc.Uncovered(u"x%02d" % number, u"Name %d" % number, (), u"Kxa")
        self.assertEqual([fc.uncovered_count_text(count) for count in (0, 1, 2)],
                         [u"", u"1 not yet covered", u"2 not yet covered"])
        self.assertEqual(fc.uncovered_sentence([]), u"")
        self.assertEqual(fc.uncovered_sentence([entry(1)]),
                         u"1 more language of it is known and cannot be checked yet (no source says how it is "
                         u"written): Name 1.")
        self.assertEqual(fc.uncovered_sentence([entry(1), entry(2)]),
                         u"2 more languages of it are known and cannot be checked yet (no source says how they are "
                         u"written): Name 1 and Name 2.")
        self.assertTrue(fc.uncovered_sentence([entry(n) for n in range(6)]).endswith(
            u"Name 0, Name 1, Name 2, Name 3, and 2 more."))
        node = fc.FamilyNode(u"Kxa", (u"Kxa",))
        node.uncovered = [entry(1)]
        self.assertTrue(fc.family_tip(node).endswith(u"\n" + fc.uncovered_sentence([entry(1)])))
        tip = fc.family_tip(fc.UncoveredNode((u"Kxa",), [entry(1), entry(2)]))
        self.assertTrue(tip.startswith(u"2 languages of it are known and cannot be checked yet"), tip)
        self.assertIn(fc.CONTRIBUTE, tip)
        self.assertEqual(fc.ISSUES_ADDRESS, fc.REPOSITORY + u"/issues")
        self.assertTrue(fc.REPOSITORY.startswith(u"https://github.com/"))
        for text in (fc.CONTRIBUTE, fc.CONTRIBUTE_SCRIPTS):
            self.assertIn(u"open an issue on FreeLab's repository (%s) with the characters" % fc.ISSUES_ADDRESS, text,
                          "the address is written out: it reads without a link")
        amkoe = fc.Uncovered(u"huc", u"Amkoe", (u"Hoan", u"Eastern Hoan"), u"Kxa")
        lines = fc.uncovered_tip(amkoe, [u"Latin"]).split(u"\n")
        self.assertEqual(lines[0], u"Amkoe (huc), Kxa: known, not yet covered. None of Font Check's sources says which "
                                   u"characters it is written with, so no font can be checked for it.")
        self.assertEqual(lines[1], u"Recorded as written in Latin: the character sets Adobe Latin 5, GF Latin African, "
                                   u"and GF Latin Beyond (in Character sets) are the nearest measure.")
        self.assertEqual(lines[2], u"Also called: Hoan and Eastern Hoan")
        self.assertIn(fc.ISSUES_ADDRESS, lines[3])
        self.assertEqual(fc.proxy_sentence([u"Arabic"]), u"Recorded as written in Arabic: the character set GF Arabic "
                                                         u"Plus (in Character sets) is the nearest measure.")
        self.assertEqual(fc.proxy_sentence([u"Thai"]), u"Recorded as written in Thai: the languages listed under that "
                                                       u"script are the nearest measure.")
        self.assertIn(u"No source here records a script for it", fc.uncovered_tip(amkoe))
        sets = set(one.name for one in fc.load_character_sets())
        self.assertTrue(set(name for names in fc.PROXY_SETS.values() for name in names) <= sets, "sets Font Check lists")
        self.assertEqual(fc.coverage_counts_text(2510, 7861, 103, 172),
                         u"Font Check can check 2,510 of the 7,861 languages Glottolog lists with an ISO 639-3 code, "
                         u"written in 103 of Unicode's 172 scripts.")
        self.assertEqual(fc.coverage_counts_text(0, 0, 0, 0), u"")
        self.assertTrue(fc.uncovered_matches(amkoe, u"huc") and fc.uncovered_matches(amkoe, u"eastern"))
        self.assertFalse(fc.uncovered_matches(amkoe, u"am"), "a short text: a code or a whole name only")


class CustomSetTests(unittest.TestCase):
    """A set of the user's own: text or characters pasted are checked as a character set, and saved
    in FreeLab's settings folder. It is how a language no source describes is checked all the same."""

    def test_pasted_characters(self):
        dieresis, acute = u(0x308), u(0x301)
        self.assertEqual(fc.pasted_characters(u"ab a\t" + u"n" + dieresis + u" e" + acute + u(0x200D) + u"b\n"),
                         [u"a", u"b", u"n" + dieresis, u(0xE9)],
                         "each once, in NFC, spaces, controls, and format characters left out")
        self.assertEqual(fc.pasted_characters(acute + u" a"), [acute, u"a"], "a lone mark stays one")
        self.assertEqual(fc.pasted_characters(u(0x1E900) + u"a" + u(0x1E900)), [u(0x1E900), u"a"], "past U+FFFF: one item")
        self.assertEqual(fc.pasted_characters(u"1, 2!"), [u"1", u",", u"2", u"!"], "digits and punctuation are characters")
        self.assertEqual((fc.pasted_characters(u""), fc.pasted_characters(None), fc.pasted_characters(u" \n")), ([], [], []))

    def test_set(self):
        one = fc.custom_set(fc.PASTED_KEY, fc.PASTED_NAME, u"ab b" + u(0x14B))
        self.assertEqual((one.kind, one.script, one.name, one.base), (u"set", fc.CUSTOM_GROUP, u"Pasted characters",
                                                                      [u"a", u"b", u(0x14B)]))
        self.assertEqual(one.definition, u"A set of your own: the 3 characters of the text you gave (spaces left out).")
        self.assertIn(u"the 1 character of", fc.custom_set(u"k", u"One", u"a").definition)
        result = fc.check_language(one, font([0x61, 0x62]))
        self.assertEqual((result.level, result.missing), ("nearly", [u(0x14B)]))
        sections, _ = fc.set_sections([result])
        self.assertEqual([(s.title, len(s.results)) for s in sections], [(fc.CUSTOM_GROUP, 1)])
        self.assertEqual(fc.custom_key(u"Mine"), u"custom:Mine")

    def test_saved(self):
        import shutil
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-sets-")
        self.addCleanup(lambda: shutil.rmtree(folder, True))
        path = os.path.join(folder, "deeper", fc.CUSTOM_SETS_FILE)
        self.assertEqual(fc.load_custom_sets(path), [], "no file yet")
        sets = fc.with_custom_set([], u" Mine ", u"ab" + u(0x14B))
        sets = fc.with_custom_set(sets, u"Other", u"xyz")
        fc.save_custom_sets(path, sets)
        self.assertEqual(fc.load_custom_sets(path), [(u"Mine", u"ab" + u(0x14B)), (u"Other", u"xyz")])
        with open(path, "rb") as handle:
            raw = handle.read()
        self.assertEqual(raw, raw.decode("ascii").encode("ascii"), "plain ASCII on disk")
        again = fc.with_custom_set(sets, u"Mine", u"q")
        self.assertEqual(again, [(u"Mine", u"q"), (u"Other", u"xyz")], "saved again under its name: in its place")
        with open(path, "wb") as handle:
            handle.write(b"not json")
        self.assertEqual(fc.load_custom_sets(path), [], "an unreadable file: no set, no error")


class OrthographyTests(unittest.TestCase):
    """The languages Hyperglot does not describe (the owner: "Find ways to cover the languages that
    cannot be checked"): a second data file from other sources, each language saying where its
    characters come from and whether they were declared or inferred from counting a text."""

    @classmethod
    def setUpClass(cls):
        cls.hyperglot = fc.load_languages(LANGUAGES_FILE)
        cls.languages = fc.load_languages(LANGUAGES_FILE, ORTHOGRAPHIES_FILE)
        cls.others = cls.languages[len(cls.hyperglot):]

    def test_loaded_beside_hyperglot(self):
        self.assertEqual(self.languages[:len(self.hyperglot)], self.hyperglot, "Hyperglot's first, as they were")
        self.assertIs(fc.load_languages(LANGUAGES_FILE, ORTHOGRAPHIES_FILE), self.languages, "put together once")
        self.assertEqual(len(fc.load_languages()), len(self.languages), "the file beside the script, by itself")
        self.assertIs(fc.load_languages(LANGUAGES_FILE, False), self.hyperglot)
        self.assertIs(fc.load_languages(LANGUAGES_FILE, os.path.join(HERE, "no_such_file.json")), self.hyperglot,
                      "without the second file: Hyperglot's languages alone")
        self.assertGreater(len(set(l.iso for l in self.others)), 1600)
        both = set(l.iso for l in self.others) & set(l.iso for l in self.hyperglot)
        self.assertEqual(len(both), 66, "a second source only fills what Hyperglot lacks: a language, or a script")
        written = set((l.iso, l.script) for l in self.hyperglot)
        self.assertTrue(all(l.evidence != fc.INFERRED and (l.iso, l.script) not in written
                            for l in self.others if l.iso in both), "a declared source's or a layout's, never a count")
        seconds = dict(((l.iso, l.script), l.evidence) for l in self.others if l.iso in both)
        for key in ((u"jav", u"Javanese"), (u"ban", u"Balinese"), (u"sun", u"Sundanese"), (u"kaz", u"Arabic"),
                    (u"mni", u"Meetei Mayek"), (u"lzz", u"Latin")):
            self.assertEqual(seconds.get(key), fc.DECLARED, key)
        for key in ((u"kmr", u"Yezidi"), (u"fuf", u"Adlam"), (u"bts", u"Batak"), (u"xmf", u"Latin")):
            self.assertEqual(seconds.get(key), fc.KEYBOARD, key)
        self.assertNotIn((u"uzn", u"Arabic"), seconds, "a macrolanguage's subtag (uz) names none of its members")
        self.assertNotIn(u"aka", set(l.iso for l in self.others), "Akan: Hyperglot describes Twi and Fante")
        names = dict(((l.iso, l.script), l.name) for l in self.others)
        self.assertEqual(names[(u"jav", u"Javanese")], [l.name for l in self.hyperglot if l.iso == u"jav"][0],
                         "Hyperglot's name for its language")
        self.assertTrue(all(l.source == fc.HYPERGLOT and l.evidence == fc.DECLARED for l in self.hyperglot))
        self.assertTrue(all(l.source != fc.HYPERGLOT and l.base for l in self.others))
        self.assertEqual(set(l.evidence for l in self.others), set([fc.DECLARED, fc.INFERRED, fc.KEYBOARD]))
        declared = set(l.iso for l in self.others if l.evidence == fc.DECLARED)
        inferred = set(l.iso for l in self.others if l.evidence == fc.INFERRED)
        self.assertFalse(declared & inferred, "one source per language")
        self.assertTrue(len(declared) > 900 and len(inferred) > 600, (len(declared), len(inferred)))
        self.assertEqual(set(l.status for l in self.others), set([fc.NOT_GIVEN, u"historical", u"constructed"]))
        self.assertTrue(all((u"generated" in l.source or u"Unilex" in l.source or u"sample text" in l.source
                             or CRUBADAN in l.source or u"Universal Declaration" in l.source)
                            == (l.evidence == fc.INFERRED) for l in self.others),
                        "inferred: SIL's generated exemplars, Unilex's counts, An Crubadan's, the declaration's "
                        "whole text, Google's sample texts")

    def test_an_crubadan(self):
        """A sixth source (the owner: "Evaluate one more data source"): Kevin Scannell's web corpora,
        from the seven archives the Wayback Machine kept (word frequencies) and from the 2010 trigram
        counts NLTK distributes; each language it gives is one no other source had, or one whose
        only other evidence was a short sample text."""
        found = dict((l.iso, l) for l in self.others if CRUBADAN in l.source)
        self.assertEqual(len(found), 37, "Plains Cree's now rests on a keyboard layout, and Akan's is Hyperglot's "
                                         "through Twi and Fante")
        self.assertTrue(all(l.evidence == fc.INFERRED and not l.auxiliary for l in found.values()),
                        "counted text: inferred, base characters only")
        words = sorted(iso for iso, l in found.items() if u"word frequencies" in l.source)
        self.assertEqual(words, [u"act", u"bcl", u"urh"], "the archives: Achterhoeks, Bikol, Urhobo")
        self.assertTrue(all(found[iso].license == u"CC BY 4.0" for iso in words))
        trigrams = [l for l in found.values() if u"character trigrams of 2010" in l.source]
        self.assertEqual(len(trigrams), 34, "four fewer: three files were another language's text, one a text held "
                                            "twice; and Plains Cree's and Akan's")
        self.assertTrue(all(l.license == u"GNU General Public License, version 3 or later" for l in trigrams))
        cree = [l for l in self.others if l.iso == u"crk"]
        self.assertEqual([(l.script, l.evidence) for l in cree], [(u"Canadian Syllabics", fc.KEYBOARD)],
                         "the layout ranks before the counted text, and takes its place")
        self.assertIn(u(0x1403), cree[0].base)
        urhobo = found[u"urh"]
        for letter in (u"a", u"A", u"v", u"w", u(0x1EB9), u(0x1ECD)):  # (e and o with a dot below)
            self.assertIn(letter, urhobo.base)
        self.assertTrue(fc.source_text(urhobo).startswith(
            u"An Cr\N{LATIN SMALL LETTER U WITH ACUTE}bad\N{LATIN SMALL LETTER A WITH ACUTE}n's word "
            u"frequencies (Kevin Scannell) (a word list of "), fc.source_text(urhobo))
        self.assertIn(u" letters): inferred from text", fc.source_text(urhobo))
        gothic = [l for l in self.others if l.iso == u"got"]
        self.assertEqual([(l.script, u"sample text" in l.source) for l in gothic], [(u"Gothic", True), (u"Runic", True)],
                         "crawled in Latin letters, while Google's data states other scripts: left to its texts")
        self.assertEqual(len(set(l.iso for l in self.languages)), 2511)
        self.assertEqual(len(set(l.iso for l in self.others if l.evidence == fc.INFERRED)), 748,
                         "Lisu in Lisu and Mandaic in Mandaic counted (their scripts by Unicode's own codes); Akan not")
        self.assertEqual(len(fc.load_families(FAMILIES_FILE).unlisted), 5036,
                         "nor a language described through its dialects or members (Latvian, Serbian-Croatian-Bosnian)")

    def test_misfiled_and_reinforced(self):
        """The owner: "For the 73 weakest samples, look into UDHR-derived alternates/reinforcements
        before dropping anything", and, of two doubtful entries, "double-check those before deciding".
        Three of An Crubadan's trigram files were another language's text (the declaration in Aja of
        Benin, Gen, and Waama, which Hyperglot describes): no row stands under their labels. An
        inferred row names every source it rests on, with the letters each counted; the short sample
        texts say how short they are."""
        isos = set(l.iso for l in self.languages)
        self.assertFalse(isos & set([u"aja", u"hna", u"ako"]), "Aja (South Sudan), Mina (Cameroon), Akurio: not theirs")
        self.assertTrue(set([u"ajg", u"gej", u"wwa"]) <= set(l.iso for l in self.hyperglot))
        inferred = [l for l in self.others if l.evidence == fc.INFERRED]
        self.assertTrue(all(l.rests for l in inferred), "every inferred row says what it rests on")
        self.assertFalse([l.iso for l in self.others if l.evidence == fc.DECLARED and l.rests],
                         "a declared orthography stands alone")
        several = [l for l in inferred if len(l.rests) > 1]
        self.assertEqual(len(several), 211, "Sylheti's in Syloti Nagri among them: its two layouts lack kho, cho, "
                                            "and the anusvara, and are not read")
        sylheti = [l for l in several if l.iso == u"syl" and l.script == u"Syloti Nagri"]
        self.assertEqual(len(sylheti), 1)
        for code in (0xA808, 0xA80D):
            self.assertIn(u(code), sylheti[0].base)
        self.assertIn(u(0xA80B), sylheti[0].marks)
        self.assertTrue(all(l.rests[0][0] == l.source for l in inferred), "the first source is the one named before")
        whole = dict((l.iso, l) for l in inferred if u"Universal Declaration" in l.source)
        self.assertEqual(sorted(whole), [u"eml", u"hlt", u"mxi", u"qud", u"qxa", u"qxu", u"ztu"],
                         "five that rested on an excerpt, one new language, and one whose trigram file is the same text")
        self.assertEqual(whole[u"hlt"].rests, ((whole[u"hlt"].source, 9996, u"text"),))
        self.assertEqual(fc.source_text(whole[u"hlt"]),
                         u"The Universal Declaration of Human Rights, whole (NLTK's udhr2 package) (a text of 9,996 "
                         u"letters): inferred from text, status not given")
        self.assertFalse(fc.short_text(whole[u"hlt"]))
        short = [l for l in inferred if fc.short_text(l)]
        self.assertEqual(len(short), 77, "the rows that still rest on one sample text (four now rest on a layout, and "
                                         "Mandaic's, its script found by Unicode's code, is one more)")
        self.assertTrue(all(u"sample text" in l.source and 1000 <= l.rests[0][1] < fc.SHORT_TEXT for l in short))
        tip = fc.coverage_tip(fc.check_language(short[0], font(LATIN_1)))
        self.assertIn(u"(a text of ", tip)
        self.assertIn(fc.SHORT_TIP, tip.split(u"\n"))
        both = fc.coverage_tip(fc.check_language(several[0], font(LATIN_1)))
        self.assertIn(u" and ", both.split(u"\n")[0])
        self.assertIn(u"another source has too", both)
        self.assertNotIn(fc.SHORT_TIP, both)
        # The words themselves, at one, two, and three sources, and for a source that gives no count
        one = other_language(u"a", evidence=fc.INFERRED, validity=u"", source=u"A")
        one.rests = ((u"A", 1412, u"text"),)
        self.assertEqual(fc.rests_text(one), u"A (a text of 1,412 letters)")
        one.rests = ((u"A", 0, u""), (u"B", 23512, u"words"))
        self.assertEqual(fc.rests_text(one), u"A and B (a word list of 23,512 letters)")
        one.rests = ((u"A", 0, u""), (u"B", 23512, u"words"), (u"C", 1, u"text"))
        self.assertEqual(fc.rests_text(one), u"A, B (a word list of 23,512 letters), and C (a text of 1 letter)")
        one.rests = ()
        self.assertEqual(fc.rests_text(one), u"A", "a row that says no more: its one source")

    def test_south_eastern_ju(self):
        """The language the owner looked for: checked now, from a source that declares its characters."""
        ju = [l for l in self.others if l.iso == u"ktz"]
        self.assertEqual(len(ju), 1)
        ju = ju[0]
        self.assertEqual((ju.script, ju.evidence, ju.status), (u"Latin", fc.DECLARED, fc.NOT_GIVEN))
        self.assertIn(u"Google Fonts' language data", ju.source)
        for code in (0x1C0, 0x1C1, 0x1C2, 0x1C3, 0x2BC, 0x61, 0x41):  # the four clicks, the apostrophe
            self.assertIn(u(code), ju.base)
        result = fc.check_language(ju, font(LATIN_1))
        self.assertEqual(sorted(result.missing), [u(0x1C0), u(0x1C1), u(0x1C2), u(0x1C3), u(0x2BC)])
        tip = fc.coverage_tip(result, (u"Kxa", u"Ju"))
        self.assertIn(u"(Google Fonts' language data (gflanguages 0.7.9): declared, status not given).", tip)
        self.assertNotIn(u"Inferred", tip)
        self.assertEqual(fc.language_note(result), u"")

    def test_capitals_and_marks(self):
        """CLDR's and SLDR's exemplars list small letters: the data has their capitals too, as
        Hyperglot's does, and the marks an Indic exemplar set lists are marks."""
        aai = [l for l in self.others if l.iso == u"aai"][0]
        self.assertIn(u"a", aai.base)
        self.assertIn(u"A", aai.base)
        self.assertIn(u"q", aai.auxiliary)
        self.assertIn(u"Q", aai.auxiliary)
        self.assertEqual(aai.validity, u"unconfirmed", "SLDR's draft level")
        kuvi = [l for l in self.others if l.iso == u"kxv" and l.script == u"Devanagari"][0]
        self.assertIn(u(0x93E), kuvi.marks)
        self.assertFalse([item for item in kuvi.base if all(fc.is_mark(code) for code in fc.code_points(item))])
        self.assertEqual(len([l for l in self.others if l.iso == u"kxv"]), 4, "every script its one source gives")
        self.assertFalse([l.iso for l in self.others if any(not item for item in l.base + l.auxiliary)])

    def test_tooltip_names_the_source(self):
        f = font([0x61, 0x62])
        hyperglot = fc.check_language(language(u"a b", name=u"Zulu"), f)
        self.assertTrue(fc.coverage_tip(hyperglot).startswith(u"Zulu, Latin script: covered (Hyperglot: living, verified)."))
        declared = fc.check_language(other_language(u"a b"), f)
        self.assertEqual(fc.coverage_tip(declared),
                         u"Other, Latin script: covered (SIL's Locale Data Repository (SLDR): declared, draft level "
                         u"unconfirmed, status not given).")
        counted = fc.check_language(other_language(u"a b c", evidence=fc.INFERRED, validity=u"",
                                                   source=u"Unilex word frequencies"), f)
        lines = fc.coverage_tip(counted).split(u"\n")
        self.assertEqual(lines[0], u"Other, Latin script: within reach (Unilex word frequencies: inferred from text, "
                                   u"status not given).")
        self.assertEqual(lines[1], fc.INFERRED_TIP)
        self.assertIn(u"not an orthography someone declared", fc.INFERRED_TIP)
        generated = other_language(u"a", evidence=fc.INFERRED, validity=u"generated", source=u"SLDR, generated by SIL's tools")
        self.assertEqual(fc.source_text(generated), u"SLDR, generated by SIL's tools: inferred from text, status not given")
        # The list itself says which languages are inferred, where it shows no missing characters
        self.assertEqual(fc.language_note(counted), fc.compact_missing(counted), "within reach: what it misses")
        covered = fc.check_language(other_language(u"a b", evidence=fc.INFERRED), f)
        self.assertEqual(fc.language_note(covered), u"inferred")
        self.assertEqual(fc.language_note(declared), u"")
        anchors = {0x65: [u"top"], 0x301: [u"_top"]}
        composed = fc.check_language(other_language(u(0xE9), evidence=fc.INFERRED), font([0x65, 0x301], anchors))
        self.assertEqual(fc.language_note(composed), u"composed, inferred")
        # A keyboard layout's row says so, in its tooltip and in the list
        typed = fc.check_language(other_language(u"a b c", evidence=fc.KEYBOARD, validity=u"",
                                                 source=u"Language Tools (sven-oly/LanguageTools, commit a9386e00)"), f)
        lines = fc.coverage_tip(typed).split(u"\n")
        self.assertEqual(lines[0], u"Other, Latin script: within reach (Language Tools (sven-oly/LanguageTools, commit "
                                   u"a9386e00): from a keyboard layout, status not given).")
        self.assertEqual(lines[1], fc.KEYBOARD_TIP)
        self.assertTrue(fc.KEYBOARD_TIP.startswith(u"From a keyboard layout (Language Tools, Apache License 2.0): the "
                                                   u"characters its keys and rules produce"))
        self.assertNotIn(fc.INFERRED_TIP, lines)
        self.assertEqual(fc.language_note(fc.check_language(other_language(u"a b", evidence=fc.KEYBOARD), f)),
                         u"keyboard")
        self.assertEqual(fc.language_note(fc.check_language(other_language(u(0xE9), evidence=fc.KEYBOARD),
                                                            font([0x65, 0x301], anchors))), u"composed, keyboard")
        self.assertFalse(fc.short_text(typed.language), "a layout is no short text")

    def test_keyboard_rows(self):
        """The rows a keyboard layout gives: languages no source describes, and second scripts of
        languages a source gives in another; each in one script, its source named, alone."""
        import json
        rows = [l for l in self.others if l.evidence == fc.KEYBOARD]
        self.assertEqual((len(rows), len(set(l.iso for l in rows))), (37, 37),
                         "Manipuri's in Meetei Mayek and Laz's in Latin are a declared source's now")
        self.assertFalse([l for l in rows if l.iso == u"syl"], "Sylheti's layouts, worse than its counted row, are not read")
        gondi = dict((l.script, l) for l in self.others if l.iso == u"wsg")
        self.assertEqual(gondi[u"Gunjala Gondi"].evidence, fc.KEYBOARD)
        self.assertEqual(gondi[u"Telugu"].evidence, fc.INFERRED,
                         "its Telugu layout, a prototype whose shift layer types Tibetan, is refused")
        for code in (0xC06, 0xC08, 0xC09, 0xC0A, 0xC0E):  # (the independent vowels the layout lacked)
            self.assertIn(u(code), gondi[u"Telugu"].base)
        self.assertIn(u(0xC3E), gondi[u"Telugu"].marks, "and the vowel signs: aa")
        self.assertTrue(all(l.source.startswith(u"Language Tools (sven-oly/LanguageTools, commit a9386e00)")
                            and l.license == u"Apache License 2.0" and not l.rests and not l.auxiliary
                            for l in rows), "the source named, no rests, no auxiliary set made up")
        by = dict(((l.iso, l.script), l) for l in rows)
        for key in ((u"aho", u"Ahom"), (u"com", u"Latin"), (u"tyj", u"Tai Yo"), (u"kmr", u"Yezidi"),
                    (u"fuf", u"Adlam"), (u"wsg", u"Gunjala Gondi"), (u"hoc", u"Varang Kshiti")):
            self.assertIn(key, by)
        self.assertNotIn((u"mni", u"Meetei Mayek"), by, "SLDR declares it: the layouts are set aside")
        self.assertEqual(by[(u"kmr", u"Yezidi")].name, [l.name for l in self.hyperglot if l.iso == u"kmr"][0],
                         "a Hyperglot language keeps its name")
        self.assertEqual(by[(u"bsq", u"Bassa Vah")].name, u"Bassa", "without the script Google's name adds")
        self.assertEqual(by[(u"hoc", u"Varang Kshiti")].name, u"Ho",
                         "Google's \"Ho, Warang Citi\" without the script, by Unicode's name for it")
        self.assertEqual(by[(u"mro", u"Mro")].status, u"historical", "what the counted row's source said is kept")
        com = by[(u"com", u"Latin")]
        for letter in (u"a", u"Z", u(0x289), u(0x244), u(0x294)):  # (barred u, its capital, the glottal stop)
            self.assertIn(letter, com.base)
        self.assertIn(u(0x331), com.marks, "the macron below, typed alone")
        self.assertFalse([l for l in rows if l.iso == u"mww"], "the English layout under another name: refused")
        # One script per row, by the pinned scripts' ranges (character_sets.json): no Latin fallback leaks
        with open(os.path.join(HERE, os.pardir, "checks", "character_sets.json"), "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        ranges = []
        for row in data["scripts"]["rows"]:
            for part in row[1].split():
                low, _, high = part.partition("-")
                ranges.append((int(low, 16), int(high or low, 16), row[0]))
        for l in rows:
            scripts = set()
            for item in l.base:
                code = fc.code_points(item)[0]
                found = [name for low, high, name in ranges if low <= code <= high]
                if found:
                    scripts.add(found[0])
            self.assertEqual(len(scripts), 1, (l.iso, l.script, sorted(scripts)))

    def test_status_not_given_counts_as_living(self):
        languages = [language(u"a b", name=u"Zulu"), other_language(u"a b", name=u"Unstated"),
                     other_language(u"a b", name=u"Old", status=u"historical", iso=u"old")]
        f = font([0x61, 0x62])
        by_key = dict((key, statuses) for key, _, statuses in fc.STATUS_FILTERS)
        names = lambda statuses: sorted(r.language.name for s in fc.coverage(languages, f, 3, statuses is None, statuses)
                                        for r in s.results)
        self.assertEqual(names(by_key["current"]), [u"Unstated", u"Zulu"])
        self.assertEqual(names(by_key["living"]), [u"Unstated", u"Zulu"])
        self.assertEqual(names(by_key["historical"]), [u"Old"])
        self.assertEqual(names(by_key["all"]), [u"Old", u"Unstated", u"Zulu"])
        self.assertEqual(fc.left_title(languages[1]), u"Languages of no given status")

    def test_inferred_left_out_by_their_check_box(self):
        languages = [language(u"a b", name=u"Zulu"), other_language(u"a b", name=u"Declared"),
                     other_language(u"a b", name=u"Counted", evidence=fc.INFERRED, iso=u"cnt"),
                     other_language(u"a b", name=u"Typed", evidence=fc.KEYBOARD, iso=u"typ"),
                     language(u"a b", name=u"Old Latin", status=u"historical")]
        self.assertEqual(fc.chosen_languages(languages), (languages, []))
        kept, aside = fc.chosen_languages(languages, False)
        self.assertEqual(([l.name for l in kept], [l.name for l in aside]),
                         ([u"Zulu", u"Declared", u"Old Latin"], [u"Counted", u"Typed"]),
                         "one check box for both: the languages no source declares")
        f = font([0x61, 0x62])
        statuses = fc.STATUS_FILTERS[0][2]
        scripts = fc.coverage(kept, f, 3, False, statuses)
        others = fc.left_out(kept, f, 3, statuses, aside)
        self.assertEqual([r.language.name for r in others], [u"Old Latin", u"Counted", u"Typed"])
        self.assertEqual([r.language.name for r in fc.left_out(kept, f, 3, None, aside)], [u"Counted", u"Typed"],
                         "every status kept: the inferred ones are still set aside")
        sections, _ = fc.language_sections(scripts, [u"Latin"], u"", None, "reach", others)
        self.assertEqual([(s.title, len(s.results)) for s in sections], [(u"Latin", 2)], "not listed without a search")
        sections, _ = fc.language_sections(scripts, [u"Latin"], u"e", None, "reach", others)
        self.assertEqual([s.heading() for s in sections if s.why],
                         [u"Languages from texts and keyboards (2): left out by the choice of languages above"],
                         "a search finds them, under a heading that says why they are not listed")
        self.assertEqual(fc.left_title(languages[3]), fc.INFERRED_TITLE)

    def test_top_line(self):
        self.assertEqual(fc.inferred_sentence(0, 0), u"")
        self.assertEqual(fc.inferred_sentence(1), u" Of those covered or within reach, 1 is inferred from text or read "
                                                  u"from a keyboard layout, not declared by a source (its row says so).")
        self.assertEqual(fc.inferred_sentence(12, 3, lambda text: u"<b>%s</b>" % text),
                         u" Of those covered or within reach, <b>12</b> are inferred from text or read from a keyboard "
                         u"layout, not declared by a source (their rows say so).")
        self.assertEqual(fc.inferred_sentence(0, 1), u" 1 language from texts and keyboards is left out.")
        self.assertEqual(fc.inferred_sentence(0, 805), u" 805 languages from texts and keyboards are left out.")

    def test_every_added_language_has_a_family(self):
        families = fc.load_families(FAMILIES_FILE)
        self.assertEqual([l.iso for l in self.others if not families.path(l.iso)], [],
                         "Glottolog classifies each one (two placed by hand: Middle Newar, Manichaean Middle Persian)")
        self.assertTrue(families.path(u"nwx") and families.path(u"xmn"))
        named = set(families.aliases)
        self.assertGreater(len([l for l in self.others if l.iso in named]), 1500, "and keeps their other names")

    def test_license_and_data_file(self):
        import json
        with open(ORTHOGRAPHIES_FILE, "rb") as handle:
            raw = handle.read()
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["columns"][:10], ["iso", "name", "autonym", "script", "status", "validity", "speakers",
                                                "base", "auxiliary", "marks"], "the shape of Hyperglot's file")
        self.assertEqual(data["columns"][10:], ["source", "evidence", "rests"])
        self.assertEqual([row[0] for row in data["sources"]],
                         ["gflanguages", "cldr", "sldr", "keyboard", "sldr-generated", "unilex", "crubadan",
                          "crubadan-trigrams", "udhr2", "gflanguages-text"])
        self.assertEqual([row[3] for row in data["sources"]],
                         ["", "", "", "", "", "words", "words", "text", "text", "text"], "what each source's count counts")
        self.assertEqual(data["evidence"], {"d": "declared", "i": "inferred", "k": "keyboard"})
        self.assertIn("one layout per language and script, alone", data["keyboard_rule"])
        self.assertIn("2 or fewer letters of another script", data["keyboard_rule"])
        self.assertLess(len(raw), 400000)
        for row in data["orthographies"]:
            self.assertEqual(len(row), 13 if row[11] == "i" else 12, row[0])
            self.assertEqual(row[11] == "i", row[10] >= 4, "%s: the last six sources are the inferred ones" % row[0])
            self.assertEqual(row[11] == "k", row[10] == 3, "%s: a keyboard layout's row rests on it alone" % row[0])
            if row[11] == "i":
                self.assertEqual(row[12][0][0], row[10], "%s: the source named is the first it rests on" % row[0])
                self.assertTrue(all(index >= 4 for index, _ in row[12]), "%s: inferred sources only" % row[0])
        scripts = data["scripts"]
        self.assertEqual((scripts["known"], len(scripts["not_covered"])), (172, 61))
        for script in ("Javanese", "Balinese", "Sundanese", "Lisu", "Mandaic"):
            self.assertNotIn(script, scripts["not_covered"], "a declared second script, or a text Unicode's code finds")
        for script in ("Ahom", "Tai Yo", "Warang Citi", "Meetei Mayek", "Gurung Khema"):
            self.assertNotIn(script, scripts["not_covered"], "a layout's language is written in it")
        self.assertIn("Mongolian", scripts["not_covered"])
        self.assertNotIn("Latin", scripts["not_covered"])
        self.assertNotIn("Miao", scripts["not_covered"], "the Pollard script, which the data has")
        known = set(row[0] for row in data["orthographies"])
        for script, codes in scripts["of_other_languages"].items():
            self.assertFalse(set(codes.split()) & known, script)
        with open(os.path.join(HERE, os.pardir, "checks", "language_orthographies_LICENSE"), "rb") as handle:
            notice = handle.read().decode("utf-8")
        for words in (u"Apache License", u"UNICODE LICENSE V3", u"The MIT License (MIT)", u"SIL International",
                      u"Changes made", u"googlefonts/lang", u"silnrsi/sldr", u"unicode-org/unilex", u"marked as inferred",
                      CRUBADAN + u" (http://crubadan.org/), edited by Kevin Scannell",
                      u"language dataset is licensed under a\nCreative Commons Attribution 4.0 International License",
                      u"web.archive.org/web/20210607115712id_/http://crubadan.org/files/urh.zip",
                      u"Corpus building for under-resourced languages", u"Attribution 4.0 International\n",
                      u"Copyright 2010\n      Kevin P. Scannell, licensed under the GNU General Public License, version 3",
                      u"nltk/nltk_data, commit fa7aae1c5c5e26b3cc3217dae15005c471184819",
                      u"nltk/nltk_data, commit\n   5d8fe95aee5ac9014f7b3924b32715ead288441c",
                      u'license="public domain" copyright="public domain"',
                      u"The archive holds the texts alone, with no readme or license file of its own",
                      u"a declared orthography (sources 1 to 3) is never mixed with another",
                      u"7. Language Tools (https://languagetools-153419.appspot.com/)",
                      u"https://github.com/sven-oly/LanguageTools, branch p3_version, commit\n"
                      u"   a9386e0031b086418f402338a7428449b08166a1",
                      u'      Licensed under the Apache License, Version 2.0 (the "License");\n',
                      u"carry no license line of their own, and the repository's LICENSE covers them",
                      u"no layout, key map, or\n   rule is kept",
                      u"Apache License, Version 2.0 (Language Tools: its LICENSE file)",
                      u"8. Glottolog 5.4 (https://glottolog.org)", u"Cite as:", u"Glottolog does not endorse this file",
                      u"Creative Commons Attribution 4.0 International (%s's archives and Glottolog" % CRUBADAN):
            self.assertIn(words, notice)
        section = notice[notice.index(u"7. Language Tools"):notice.index(u"Where two or more of the inferred")]
        self.assertFalse([line for line in section.split(u"\n") if line != line.rstrip()], "the header quoted, no trailing spaces")

    def test_a_search_folds_each_text_once(self):
        """With some 2,500 languages a keystroke folded 25,000 texts (the text typed and each family's
        name, at every row): a short text is folded once and kept."""
        fc._FOLDS.clear()
        self.assertEqual(fc.fold(u"Fran\N{LATIN SMALL LETTER C WITH CEDILLA}ais"), u"francais")
        self.assertEqual(fc._FOLDS, {u"Fran\N{LATIN SMALL LETTER C WITH CEDILLA}ais": u"francais"})
        self.assertEqual(fc.fold(u"Fran\N{LATIN SMALL LETTER C WITH CEDILLA}ais"), u"francais")
        long_text = u"\N{LATIN CAPITAL LETTER E WITH ACUTE}" * (fc.FOLD_LENGTH + 1)
        self.assertEqual(fc.fold(long_text), u"e" * (fc.FOLD_LENGTH + 1))
        self.assertNotIn(long_text, fc._FOLDS, "a language's joined names are kept on the language, not here")
        self.assertEqual((fc.fold(None), fc.fold(u"")), (u"", u""))
        for number in range(fc.FOLDS_KEPT + 5):
            fc.fold(u"x%d" % number)
        self.assertLessEqual(len(fc._FOLDS), fc.FOLDS_KEPT, "never more than so many kept")
        families = fc.load_families(FAMILIES_FILE)
        languages = fc.name_languages(self.languages, families)
        f = font(LATIN_1)
        scripts = fc.coverage(languages, f, 3, True, None)
        results = [r for s in scripts for r in s.results]
        shown = [s.script for s in scripts]
        fc.language_sections(scripts, shown, u"x")  # (each language's names folded once, the first time)
        import time
        started = time.time()
        for text in (u"k", u"ku", u"kun", u"kung", u"", u"german", u"hoan", u"zz", u"a", u"nama"):
            fc.language_sections(scripts, shown, text)
            fc.family_tree(results, families, text)
            families.unlisted_matches(text)
        self.assertLess(time.time() - started, 2.0, "ten keystrokes over every language (about 0.2 s under Python 2.7)")
        found = [r.language.iso for s in fc.language_sections(scripts, shown, u"hoan")[0] for r in s.results]
        self.assertIn(u"ktz", found, "found by its name now that it has an orthography")
        fc.name_languages(languages, None)


class WidthTests(unittest.TestCase):
    """The owner: "Default width for the font check panel appears to be too narrow for two lists"."""

    def test_sizes(self):
        self.assertEqual(fc.WIDE, 1400)
        self.assertEqual(fc.wide_width(1920), 1400)
        self.assertEqual(fc.wide_width(1366), 1326, "never more than the screen allows: 40 pixels less, as the shared size")
        self.assertEqual(fc.wide_width(None), 1400, "a screen that cannot be read: as the shared size, unbounded")
        self.assertEqual(fc.wide_width(0), 1400)
        left, right = fc.split_sizes(1400)
        self.assertEqual(left + right, 1400)
        self.assertTrue(500 < left < right, "the languages' lists a little wider than the characters'")

    def test_the_bar_gives_up_width_first(self):
        whole = fc.BAR_COLUMN
        self.assertEqual(fc.bar_width(900, 300, 250), whole, "room for all three: the bar whole")
        self.assertEqual(fc.bar_width(600, 300, 250), 50, "a narrower list: the bar gives up what is missing")
        self.assertEqual(fc.bar_width(500, 300, 250), 0, "narrower still: no bar, and only then are the names cut")
        self.assertEqual(fc.bar_width(0, 300, 250), 0)


@unittest.skipUnless(sys.version_info[0] >= 3 and os.path.isfile(os.path.join(TRAIN, "orthographies.py")),
                     "the train script is Python 3, and is not in the Python 2.7 copy")
class TrainTests(unittest.TestCase):
    """checks/train/orthographies.py: how it reads its sources and what it counts as a language's
    characters (no source is downloaded here)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, TRAIN)
        try:
            import orthographies
        finally:
            sys.path.remove(TRAIN)
        cls.o = orthographies

    def counter(self):
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-train-")
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, True))
        path = os.path.join(folder, "Scripts.txt")
        with open(path, "wb") as handle:
            handle.write(b"0041..005A ; Latin # L\n0061..007A ; Latin # L\n00C0..024F ; Latin # L\n1E00..1EFF ; Latin # L\n"
                         b"0370..03FF ; Greek # L\n0900..097F ; Devanagari # L\n02BC ; Common # Lm\n"
                         b"0300..036F ; Inherited # Mn\n")
        return self.o.Counter(path, {"Latn": "Latin", "Grek": "Greek", "Deva": "Devanagari"})

    def test_pins(self):
        o = self.o
        self.assertEqual(len(o.SOURCES), 9, "and three of Unicode's files for the keyboard layouts")
        for name, (url, digest) in o.SOURCES.items():
            self.assertTrue(url.startswith("https://"), name)
            self.assertEqual(len(digest), 64, name)
            self.assertNotIn("/main", url)
            self.assertNotIn("master", url)
        self.assertEqual([key for key, _, _ in o.SOURCE_ROWS[-6:]], list(o.INFERRED), "the inferred sources last")
        self.assertEqual([key for key, _, _ in o.SOURCE_ROWS[:4]], ["gflanguages", "cldr", "sldr", o.KEYBOARD],
                         "a keyboard layout after the declared sources, before the inferred ones")
        self.assertNotIn("compatible; fetch", "".join(url for url, _ in o.SOURCES.values()))
        # An Crubadan's files: seven captures of the Wayback Machine (the bytes as captured) and NLTK's package;
        # the declaration's texts: NLTK's package, at the commit that last changed it
        self.assertEqual(len(o.TEXT_SOURCES), 9)
        self.assertEqual(o.TEXT_SOURCES[o.UDHR2],
                         ("https://raw.githubusercontent.com/nltk/nltk_data/5d8fe95aee5ac9014f7b3924b32715ead288441c/"
                          "packages/corpora/udhr2.zip", "0796c314b09a930c989c6f9d93d226af9af13feccd88496e196c743dd266c7f3"))
        self.assertIn('license="public domain"', o.UDHR2_INDEX)
        self.assertFalse(set(o.TEXT_SOURCES) & set(o.SOURCES))
        for name, (url, digest) in o.TEXT_SOURCES.items():
            self.assertTrue(url.startswith("https://"), name)
            self.assertEqual(len(digest), 64, name)
            self.assertNotIn("gh-pages", url)
        captures = [url for url, _ in o.TEXT_SOURCES.values() if "web.archive.org" in url]
        self.assertEqual(len(captures), 7)
        self.assertTrue(all(re.match(r"https://web\.archive\.org/web/\d{14}id_/http://crubadan\.org/(files|dist)/"
                                     r"[a-z]{2,3}\.zip$", url) for url in captures), captures)
        self.assertEqual(o.TEXT_SOURCES[o.CRUBADAN_TRIGRAMS][0],
                         "https://raw.githubusercontent.com/nltk/nltk_data/fa7aae1c5c5e26b3cc3217dae15005c471184819/"
                         "packages/corpora/crubadan.zip")
        self.assertGreaterEqual(o.TEXT_PAUSE, 1, "one request at a time, a pause before each")
        self.assertGreaterEqual(o.KEYBOARD_PAUSE, 1)

    def test_keyboard_pins(self):
        """Language Tools' layouts: one commit of its live branch, each file by its SHA-256, from the
        raw files (never the repository's archive, 187 MB of fonts), with its LICENSE."""
        o = self.o
        self.assertTrue(re.match(r"^[0-9a-f]{40}$", o.LANGUAGE_TOOLS_COMMIT))
        self.assertEqual(len(o.KEYBOARD_SOURCES), len(o.KEYBOARDS) + 1)
        for name, (url, digest) in o.KEYBOARD_SOURCES.items():
            self.assertTrue(url.startswith("https://raw.githubusercontent.com/sven-oly/LanguageTools/%s/"
                                           % o.LANGUAGE_TOOLS_COMMIT), url)
            self.assertTrue(re.match(r"^[0-9a-f]{64}$", digest), name)
        self.assertTrue(o.KEYBOARD_SOURCES[o.LANGUAGE_TOOLS_LICENSE[0]][0].endswith("/LICENSE"))
        self.assertFalse(set(o.KEYBOARD_SOURCES) & (set(o.SOURCES) | set(o.TEXT_SOURCES)))
        self.assertEqual(len(set(name for name, _, _, _ in o.KEYBOARDS)), len(o.KEYBOARDS), "each file once")
        self.assertEqual(len(set(digest for _, _, _, digest in o.KEYBOARDS)), len(o.KEYBOARDS),
                         "no file twice under two names (gvr's is also grv, Tibetan Wylie's bo_wylie)")

    def test_keyboard_mapping(self):
        """Each layout is mapped by hand to an ISO 639-3 code Glottolog has (or Hyperglot describes)
        and an ISO 15924 code Unicode encodes; a language and script's layouts agree with each other."""
        o = self.o
        import collections
        import json
        with open(FAMILIES_FILE, "rb") as handle:
            families = json.loads(handle.read().decode("utf-8"))
        with open(LANGUAGES_FILE, "rb") as handle:
            hyperglot = set(row[0] for row in json.loads(handle.read().decode("utf-8"))["orthographies"])
        known = set(families["languages"]) | set(row[0] for row in families["unlisted"]) | hyperglot
        scripts = collections.defaultdict(set)
        for name, iso, script, _ in o.KEYBOARDS:
            self.assertTrue(re.match(r"^[a-z]{3}$", iso), name)
            self.assertTrue(re.match(r"^[A-Z][a-z]{3}$", script), name)
            self.assertNotIn(script, ("Zyyy", "Zinh", "Zzzz", "Qaaa"), name)
            self.assertIn(iso, known, "%s: %s is a code of Glottolog's or Hyperglot's" % (name, iso))
            scripts[name.split("_")[0].rstrip("0123456789")].add(script)
        self.assertEqual(scripts["gon"], set(["Deva", "Gong", "Gonm", "Telu"]), "Gondi's four, each its own")
        by_file = dict((name, (iso, script)) for name, iso, script, _ in o.KEYBOARDS)
        # The mappings a file name does not give: checked against what the layouts type.
        self.assertEqual(by_file["cja"], ("cjm", "Cham"), "the Cham script is Eastern Cham's")
        self.assertEqual(by_file["gon_gunjala"], ("wsg", "Gong"), "und_Gong: Adilabad Gondi")
        self.assertEqual(by_file["gon_deva"], ("gno", "Deva"), "the macrolanguage's member Glottolog has")
        self.assertEqual(by_file["del"], ("unm", "Latn"))
        self.assertEqual(by_file["ff_adlam"], ("fuf", "Adlm"))
        self.assertEqual(by_file["tmh"], ("ttq", "Tfng"))
        self.assertNotIn("ojs", by_file, "titled Fort Severn Cree: which Cree is not said")
        self.assertNotIn("yo1983", by_file)
        self.assertFalse(set(["syl", "syl2"]) & set(by_file), "no key for kho, cho, or the anusvara: not read")

    def keyboard_scripts(self):
        """A Scripts of a few lines, as Unicode's files write them."""
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-train-")
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, True))
        paths = {}
        for name, text in (("Scripts.txt", b"0041..005A ; Latin # L\n0061..007A ; Latin # L\n00C0..024F ; Latin # L\n"
                                           b"02BC ; Common # Lm\n00B5 ; Common # L&\n0300..036F ; Inherited # Mn\n"
                                           b"0964 ; Common # Po\n0900..0963 ; Devanagari # Lo\n"
                                           b"1E6C0..1E6DE ; Tai_Yo # Lo\n0370..03FF ; Greek # L\n0F00..0FFF ; Tibetan # Lo\n"),
                           ("ScriptExtensions.txt", b"0964 ; Beng Deva # Po\n"),
                           ("PropertyValueAliases.txt", b"sc ; Latn ; Latin\nsc ; Deva ; Devanagari\nsc ; Zyyy ; Common\n"
                                                        b"sc ; Zinh ; Inherited\nsc ; Tayo ; Tai_Yo\nsc ; Grek ; Greek\n"
                                                        b"sc ; Tibt ; Tibetan\n"),
                           ("UnicodeData.txt", b"1E6C0;TAI YO LETTER LOW KO;Lo;0;L;;;;;N;;;;;\n"
                                               b"1E6DE;TAI YO LETTER HIGH NA;Lo;0;L;;;;;N;;;;;\n")):
            paths[name] = os.path.join(folder, name)
            with open(paths[name], "wb") as handle:
                handle.write(text)
        o = self.o
        counter = o.Counter(paths["Scripts.txt"], {})
        held = dict(o.CATEGORIES)
        self.addCleanup(lambda: (o.CATEGORIES.clear(), o.CATEGORIES.update(held)))
        o.pinned_categories(paths["UnicodeData.txt"])
        return o.Scripts(counter, paths["ScriptExtensions.txt"], paths["PropertyValueAliases.txt"])

    def test_keyboard_reading(self):
        """A layout's keys and rules, read: \\u escapes decoded (a surrogate pair is one character),
        {{ }} groups and their labels, the layers of a Latin fallback left out, letters and marks of
        the script kept, private-use and unassigned code points dropped."""
        o = self.o
        scripts = self.keyboard_scripts()
        layout = (u"// Licensed under the Apache License, Version 2.0 (the \"License\");\n"
                  u"var X_LAYOUT = {\n  'id': 'x', 'title': \"X\",\n  'mappings': {\n"
                  u"    '': { '': '\\u0915\\u093f{{\\u0916\\u094d}}12' + 'q\\ue000' },\n"
                  u"    's': { '': '{{S||label||\\u0917}}\\u0964' },\n"
                  u"    'c,l,cl': { '': 'qwerty' }\n  },\n"
                  u"  'transform': { '\\u0915\\u0915': '\\u0918$1', 'x': '\\ud839\\udec0' }\n};\n")
        layers, rules = o.layout_outputs(layout)
        self.assertEqual([name for name, _ in layers], [u"", u"s", u"c,l,cl"])
        self.assertEqual(layers[0][1], [u(0x915), u(0x93F), u(0x916) + u(0x94D), u"1", u"2", u"q", u(0xE000)])
        self.assertEqual(layers[1][1], [u(0x917), u(0x964)], "the label set apart")
        self.assertEqual(rules, [u(0x918) + u"$1", u(0x1E6C0)], "a surrogate pair is one character")
        self.assertEqual(o.js_string(u"'\\ud83a'"), u(0xFFFD), "a lone surrogate: no character a row keeps")
        units, fallback = o.keyboard_reading(layout, "Deva", scripts)
        self.assertEqual(units, [u(0x915), u(0x93F), u(0x916), u(0x94D), u(0x917), u(0x918)],
                         "letters and marks one by one; no digit, danda, Latin letter, or private use")
        self.assertEqual(fallback, [u"c,l,cl"], "a layer all Latin is the keyboard's Latin fallback")
        units, _ = o.keyboard_reading(layout, "Tayo", scripts)
        self.assertEqual(units, [u(0x1E6C0)], "Unicode 17's letters by the pinned UnicodeData.txt")
        latin = (u"var L = { 'mappings': { '': { '': 'a\\u0331{{e\\u0301}}\\u02bc\\u00b5\\u0915' } },"
                 u" 'transform': { 'aa': '\\u00e1' } };")
        units, fallback = o.keyboard_reading(latin, "Latn", scripts)
        self.assertEqual(units[:26], [chr(code) for code in range(0x61, 0x7B)], "a to z first")
        self.assertEqual(units[26:], [u(0x331), u(0xE9), u(0x2BC), u(0xE1)],
                         "a lone mark, a letter with its mark (in NFC), the modifier apostrophe; not a micro sign")
        self.assertEqual(fallback, [])
        self.assertEqual(o.own_units(units, "Latn"), units[26:])
        self.assertEqual(o.own_units([u"a", u(0x915)], "Deva"), [u"a", u(0x915)])

    def test_keyboard_floor(self):
        """A layout under the floor is refused: too few letters and marks of its script, or none an
        English keyboard lacks; of a language and script's layouts, the one that types the most."""
        o = self.o
        scripts = self.keyboard_scripts()
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-train-")
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, True))

        def layout(name, text):
            path = os.path.join(folder, name + ".js")
            with open(path, "wb") as handle:
                handle.write((u"var X = { 'mappings': { '': { '': '%s' } } };" % text).encode("utf-8"))
            return path

        many = u"".join(u"\\u%04x" % code for code in range(0x915, 0x915 + 25))
        paths = {"big.js": layout("big", many), "small.js": layout("small", many[:6 * 21]),
                 "english.js": layout("english", u"qwerty"), "few.js": layout("few", many[:6 * 5]),
                 "latin.js": layout("latin", u"\\u0101\\u0331")}
        table = (("small", "aaa", "Deva", ""), ("big", "aaa", "Deva", ""), ("few", "bbb", "Deva", ""),
                 ("english", "ccc", "Latn", ""), ("latin", "ddd", "Latn", ""))
        held = o.KEYBOARDS
        o.KEYBOARDS = table
        try:
            chosen, refused = o.read_keyboards(paths, scripts)
        finally:
            o.KEYBOARDS = held
        self.assertEqual((o.KEYBOARD_FLOOR, o.KEYBOARD_OWN), (20, 2))
        self.assertEqual(list(chosen), [("aaa", "Deva"), ("ddd", "Latn")])
        self.assertEqual(chosen[("aaa", "Deva")][0], "big", "the one that types the most")
        self.assertEqual(sorted((r[0], r[3], r[4], r[5]) for r in refused), [("english", 26, 0, []), ("few", 5, 5, [])])

    def test_keyboard_unfinished(self):
        """The owner, of Adilabad Gondi in Telugu, which lost 5 independent vowels to its layout: that
        layout was a prototype whose shift layer types Tibetan. A layout that types more than
        KEYBOARD_FOREIGN letters of another script is refused as unfinished, in its layers or its
        rules; a stray one or two pass (a capital with its small letter is one), and marks of another
        script do not count."""
        o = self.o
        scripts = self.keyboard_scripts()
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-train-")
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, True))
        escaped = lambda codes: u"".join(u"\\u%04x" % code for code in codes)
        own = escaped(range(0x915, 0x915 + 25))
        tibetan = escaped([0xF40, 0xF41, 0xF42, 0xF71])  # (three letters and a vowel sign)
        stray = escaped([0x3B8, 0x398, 0x3C7, 0xF71, 0xF72])  # (theta, its capital, chi; two Tibetan vowel signs)
        texts = {
            "copied": u"'mappings': { '': { '': '%s' }, 's': { '': '%s' }, 'l': { '': 'qwerty' } }" % (own, tibetan),
            "ruled": u"'mappings': { '': { '': '%s' } }, 'transform': { 'x': '%s' }" % (own, tibetan),
            "stray": u"'mappings': { '': { '': '%s' }, 's': { '': '%s' } }" % (own, stray),
        }
        paths = {}
        for name, text in texts.items():
            paths[name + ".js"] = os.path.join(folder, name + ".js")
            with open(paths[name + ".js"], "wb") as handle:
                handle.write((u"var X = { %s };" % text).encode("utf-8"))
        with open(paths["copied.js"], "rb") as handle:
            copied = handle.read().decode("utf-8")
        _, fallback = o.keyboard_reading(copied, "Deva", scripts)
        self.assertEqual(o.foreign_letters(copied, "Deva", scripts, fallback), [u(0xF40), u(0xF41), u(0xF42)])
        with open(paths["stray.js"], "rb") as handle:
            self.assertEqual(o.foreign_letters(handle.read().decode("utf-8"), "Deva", scripts), [u(0x3B8), u(0x3C7)])
        table = (("copied", "aaa", "Deva", ""), ("ruled", "bbb", "Deva", ""), ("stray", "ccc", "Deva", ""))
        held = o.KEYBOARDS
        o.KEYBOARDS = table
        try:
            chosen, refused = o.read_keyboards(paths, scripts)
        finally:
            o.KEYBOARDS = held
        self.assertEqual(o.KEYBOARD_FOREIGN, 2)
        self.assertEqual(list(chosen), [("ccc", "Deva")], "a stray theta and chi pass")
        self.assertEqual(chosen[("ccc", "Deva")][1], [u(code) for code in range(0x915, 0x915 + 25)],
                         "and only the script's letters and marks are kept")
        self.assertEqual(sorted((r[0], r[3], len(r[5])) for r in refused), [("copied", 25, 3), ("ruled", 25, 3)],
                         "above the floor, refused all the same")

    def test_second_scripts(self):
        """A review: declared second scripts of Hyperglot's languages were thrown away. A declared
        orthography of a Hyperglot language in a script Hyperglot does not give it in is kept, each
        script from the first source that has it; a macrolanguage's subtag names none of its members."""
        o = self.o
        scripts = self.keyboard_scripts()
        codes = o.Codes.__new__(o.Codes)
        codes.overlong, codes.members = {"aa": "aaa"}, {"zz": ["aaa"]}
        deva = lambda source: o.shaped("aa", "Deva", source, u"", [u(0x915), u(0x916)], [], [], source, True)
        latin = o.shaped("aaa", "Latn", u"Latin", u"", [u"a", u"b"], [], [], "sldr", True)
        greek = o.shaped("zz", "Grek", u"Greek", u"", [u(0x3B1), u(0x3B2)], [], [], "gflanguages", True)
        declared = (("gflanguages", {"aa": [deva("gflanguages")], "zz": [greek]}),
                    ("cldr", {"aa": [deva("cldr")]}), ("sldr", {"aaa": [latin]}))
        found = o.second_scripts(declared, codes, {"aaa": [(u"Aaa", "Latn")]}, scripts)
        self.assertEqual(list(found), ["aaa"])
        self.assertEqual([one.source for one in found["aaa"]], ["gflanguages"],
                         "Devanagari from the first source; not Latin, Hyperglot's; not Greek, the macrolanguage's")
        self.assertEqual((codes.own("aa"), codes.own("aaa"), codes.own("zz")), ("aaa", "aaa", None))
        self.assertEqual(o.plain_name(u"Ho, Warang Citi", u"Varang Kshiti", u"Warang Citi"), u"Ho")
        self.assertEqual(o.plain_name(u"Bassa (Latin)", u"Latin"), u"Bassa")

    def test_described_through_members(self):
        """A review: An Crubadan's aka (Akan) file made a row though Hyperglot describes Akan's dialects
        Twi and Fante. Glottolog's classification says what is below a languoid: a dialect (by its
        Language_ID or the tree) or, for a family standing for a macrolanguage, its languages."""
        sys.path.insert(0, TRAIN)
        try:
            import families
        finally:
            sys.path.remove(TRAIN)
        row = lambda code, iso, level, language=u"", family=u"atla1278": {
            "ID": code, "ISO639P3code": iso, "Level": level, "Language_ID": language, "Family_ID": family}
        languoids = [row("akan1250", "aka", "language"), row("twii1234", "twi", "dialect", "akan1250"),
                     row("fant1241", "fat", "dialect", "akan1250"), row("uzbe1247", "uzb", "family", family=u"turk1311"),
                     row("nort2690", "uzn", "language", family=u"turk1311"), row("ewee1241", "ewe", "language"),
                     row("spur1234", "xxx", "language", family=families.BOOKKEEPING)]
        parent = {"nort2690": "uzbe1247", "uzbe1247": "turk1311", "akan1250": "atla1278", "ewee1241": "atla1278"}
        self.assertEqual(families.described_through(languoids, parent, set(["twi", "uzn"])), set(["aka", "uzb"]),
                         "Akan through Twi (Language_ID), Uzbek through Northern Uzbek (the tree); not Ewe, a sibling")
        self.assertEqual(families.described_through(languoids, parent, set(["ewe"])), set())

    def test_scripts_by_unicode_code(self):
        """A review: a counted text's script was known only by UNICODE_SCRIPTS or Google's name for it,
        so a text in Warang Citi (Google: Varang Kshiti) counted for nothing; PropertyValueAliases.txt
        gives every script's code."""
        counter = self.counter()
        self.assertIsNone(counter.code_of_script("Warang_Citi"))
        counter.unicode_codes["Warang_Citi"] = "Wara"
        self.assertEqual(counter.code_of_script("Warang_Citi"), "Wara")
        self.assertEqual(counter.code_of_script("Han"), "Hani", "UNICODE_SCRIPTS still")
        scripts = self.keyboard_scripts()
        self.assertEqual(scripts.counter.code_of_script("Tai_Yo"), "Tayo", "Scripts fills the counter's table")

    def test_trigrams(self):
        """An Crubadan's 2010 files count character trigrams, not words: each character is the middle
        one of one trigram, the word's two markers never count, and three different trigrams stand
        for the three word forms."""
        o = self.o
        counter = self.counter()
        lines = [u"600 <ab", u"600 aba", u"400 bab", u"600 ba>", u"3 <A>", u"2 a<b", u"5 <1>", u"7 xyz",
                 u"4 e" + u(0x301) + u">", u"4 <e" + u(0x301), u"9 " + u(0x301) + u(0x301) + u"a", u"no count", u"12 ab"]
        counts, size = o.trigram_counts(lines, counter)
        self.assertEqual(counts[u"a"], (1603, 4), "the middle of <ab, bab, ba>, and <A>: counted small, in four trigrams")
        self.assertEqual(counts[u"b"], (600, 1))
        self.assertEqual(counts[u(0xE9)], (4, 1), "a letter with the mark after it")
        self.assertEqual(counts[u"y"], (7, 1))
        self.assertEqual(counts[u(0x301)], (9, 1), "a mark after another mark, alone")
        self.assertEqual(set(counts), set([u"a", u"b", u"y", u(0xE9), u(0x301)]),
                         "no marker, digit, or mark after its letter (counted with it) is a unit")
        self.assertEqual(size, 1603 + 600 + 4 + 7, "the letters counted")
        one = counter.orthography(counts, size, "xx", "X", "", "crubadan-trigrams")
        self.assertEqual((one.script, one.base, one.marks), ("Latn", [u"a", u"A"], u""),
                         "b is frequent enough, but the middle of one trigram only: under three, left out")
        counts[u"b"] = (600, 3)
        self.assertEqual(counter.orthography(counts, size, "xx", "X", "", "crubadan-trigrams").base,
                         [u"a", u"A", u"b", u"B"])
        self.assertIsNone(counter.orthography(counts, 999, "xx", "X", "", "crubadan-trigrams"),
                          "under 1,000 letters counted: nothing")

    def test_reinforcement(self):
        """Two or more inferred sources of one language in one script are put together: a letter is
        kept when one source's rule keeps it and another has it too, or when it alone makes 1 letter
        in 500; one text counted twice is one source."""
        o = self.o
        make = lambda source, kept, seen: o.Evidence(source, "xx", "Latn", kept, seen, 5000, name="X")
        first = make("unilex", [u"a", u"b", u"q", u"w"], {u"a": 0.5, u"b": 0.4, u"q": 0.0006, u"w": 0.004})
        second = make("crubadan-trigrams", [u"a", u"b", u"z"], {u"a": 0.5, u"b": 0.4, u"z": 0.001, u"q": 0.0001})
        self.assertEqual(o.reinforced([first]), [u"a", u"b", u"q", u"w"], "one source alone: what its rule keeps")
        self.assertEqual(o.reinforced([first, second]), [u"a", u"b", u"q", u"w"],
                         "q: the second saw it too, under its floor; w: 1 in 250 alone; z: one source's, too rare")
        self.assertEqual(o.REINFORCED_ALONE * o.INFERRED_SHARE, 1 / 500.0)
        one = o.orthography_of([first, second])
        self.assertEqual(one.base, [u"a", u"A", u"b", u"B", u"q", u"Q", u"w", u"W"])
        self.assertEqual(one.rests, [("unilex", 5000), ("crubadan-trigrams", 5000)], "every source it rests on")
        # SLDR's generated exemplars give no counts: a letter of theirs needs a counted source to have it
        given = o.shaped("xx", "Latn", "X", "", [u"a", u"b", u"x"], [u"k"], [], "sldr-generated", True, validity="generated")
        generated = o.generated_evidence(given)
        self.assertEqual((generated.kept, generated.seen), ([u"a", u"b", u"x"], None))
        self.assertIs(o.orthography_of([generated]), given, "alone: as SLDR gives it")
        self.assertEqual(given.rests, [("sldr-generated", 0)])
        mixed = o.orthography_of([generated, second])
        self.assertEqual((mixed.base, mixed.auxiliary, mixed.validity),
                         ([u"a", u"A", u"b", u"B"], [u"k", u"K"], "generated"), "x and z: one source each")
        short = make("gflanguages-text", [u"a", u"b"], {u"a": 0.5, u"b": 0.5})
        short.size = o.SILENCE_LETTERS - 1
        self.assertEqual(o.reinforced([generated, short]), [u"a", u"b", u"x"],
                         "a short text's silence takes nothing from SLDR's set (it took 13 of Syloti Nagri's letters)")
        # One text counted twice is one source
        text = u"Aba baba abab " * 30
        whole = make("udhr2", [u"a", u"b"], {u"a": 0.5, u"b": 0.5})
        whole.profile = o.text_profile(text)
        self.assertEqual(whole.profile[u"<ab"], 60)
        same, other = make("crubadan-trigrams", [u"a"], {u"a": 1.0}), make("crubadan-trigrams", [u"a"], {u"a": 1.0})
        same.profile, other.profile = o.text_profile(text + u"aba "), o.text_profile(u"zzz yyy xxx " * 30)
        self.assertGreater(o.cosine(same.profile, whole.profile), o.SAME_TEXT)
        self.assertEqual(o.cosine(other.profile, whole.profile), 0.0)
        self.assertEqual(o.cosine({}, whole.profile), 0.0)
        excerpt = make("gflanguages-text", [u"a"], {u"a": 1.0})
        self.assertEqual(o.independent([same, whole, excerpt]), [whole],
                         "the trigram file of the same text and the excerpt give way to the whole text")
        self.assertEqual(o.independent([other, whole]), [other, whole])
        self.assertEqual(o.independent([same, excerpt]), [same, excerpt], "without the whole text: as they are")

    def test_misfiled_and_the_declaration(self):
        """The owner: "double-check those before deciding what's the best approach." Files a source
        filed under another language's code are read as that language, and any other trigram file
        whose nearest text of the declaration is another code's is reported."""
        import io
        import zipfile
        o = self.o
        self.assertEqual(o.MISFILED, {"aja": "ajg", "hna": "gej", "ako": "wwa", "tos": "top"})
        counter = self.counter()
        held = io.BytesIO()
        with zipfile.ZipFile(held, "w") as archive:
            archive.writestr("common/supplemental/supplementalMetadata.xml", "<supplementalData/>")
            archive.writestr("common/supplemental/likelySubtags.xml", "<supplementalData/>")
            archive.writestr("common/main/en.xml", "<ldml/>")
        codes = o.Codes(zipfile.ZipFile(held))
        texts = io.BytesIO()
        body = (u"Aba baba abab " * 100).encode("utf-8")
        with zipfile.ZipFile(texts, "w") as archive:
            archive.writestr("udhr2/hna.txt", body)
            archive.writestr("udhr2/abc.txt", (u"Qaq waw qawa " * 100).encode("utf-8"))
            archive.writestr("udhr2/abc_latn.txt", body)
            archive.writestr("udhr2/abc_1.txt", body)
            archive.writestr("udhr2/007.txt", body)
            archive.writestr("udhr2/README", b"no text")
        texts.seek(0)
        found, profiles = o.read_udhr2(texts, counter, codes, lambda tag: True, [])
        self.assertEqual(sorted(found), ["abc", "gej"], "hna is read as Gen; the variant and the numbered file are not read")
        self.assertEqual([(one.source, one.script, one.size) for one in found["gej"]], [("udhr2", "Latn", 1100)])
        self.assertEqual(len(found["abc"]), 2, "a language's own file and the one named by a script")
        self.assertEqual(sorted(profiles), ["abc", "gej"])
        trigram = o.Evidence("crubadan-trigrams", "xyz", "Latn", [u"a"], {u"a": 1.0}, 5000)
        trigram.iso, trigram.profile = "xyz", profiles["gej"]
        self.assertEqual(o.misfiled({"xyz": [trigram]}, profiles),
                         ["An Crubadan's trigram file for xyz is the declaration's text for gej (cosine 1.00): see MISFILED"])
        trigram.iso = "gej"
        self.assertEqual(o.misfiled({"gej": [trigram]}, profiles), [], "its own text: nothing to report")

    def test_iso_codes_as_subtags(self):
        """An Crubadan's 2010 table gives ISO 639-3 codes: each is read as the subtag CLDR writes it
        with, so Plateau Malagasy is Malagasy, which Hyperglot has."""
        import io
        import zipfile
        o = self.o
        held = io.BytesIO()
        with zipfile.ZipFile(held, "w") as archive:
            archive.writestr("common/supplemental/supplementalMetadata.xml",
                             '<supplementalData><metadata><alias>'
                             '<languageAlias type="mlg" replacement="mg" reason="overlong"/>'
                             '<languageAlias type="plt" replacement="mg" reason="macrolanguage"/>'
                             '<languageAlias type="deu" replacement="de" reason="overlong"/>'
                             '</alias></metadata></supplementalData>')
            archive.writestr("common/supplemental/likelySubtags.xml", "<supplementalData/>")
            archive.writestr("common/main/en.xml", "<ldml/>")
        codes = o.Codes(zipfile.ZipFile(held))
        self.assertEqual([codes.subtag(iso) for iso in ("plt", "mlg", "deu", "urh")], ["mg", "mg", "de", "urh"])
        self.assertEqual(codes.isos("mg"), ["mlg", "plt"])

    def test_unicode_set(self):
        o = self.o
        self.assertEqual(o.parse_set(u"[a b {ch} d-f]"), [u"a", u"b", u"ch", u"d", u"e", u"f"])
        self.assertEqual(o.parse_set(u"[a" + u(0xE1) + u(0xE2) + u" b]"), [u"a", u(0xE1), u(0xE2), u"b"],
                         "characters side by side are apart")
        self.assertEqual(o.parse_set(u"[a \\u0301 \\- \\U0001E900 \\x41 \\: {a\\u0301}]"),
                         [u"a", u(0x301), u"-", u(0x1E900), u"A", u":", u"a" + u(0x301)])
        self.assertEqual(o.parse_set(u"[\\N{LATIN SMALL LETTER A}-c]"), [u"a", u"b", u"c"])
        for refused in (u"[[:Latn:]]", u"[\\p{L}]", u"[a-z&[aeiou]]", u"a b", u"[z-a]"):
            self.assertRaises(o.UnsupportedSet, o.parse_set, refused)

    def test_characters(self):
        o = self.o
        dot_acute = unicodedata.normalize("NFC", u"e" + u(0x323) + u(0x301))
        self.assertEqual(o.items_of([u"a", u"ch", u"e" + u(0x323) + u(0x301), u"a", o.MARK_BASE + u(0x301)]),
                         [u"a", u"c", u"h", dot_acute, u(0x301)], "NFC clusters, digraphs split, each once")
        self.assertEqual(o.items_of([u"a" + u(0x200D) + u"b c"]), [u"a", u"b", u"c"], "format characters and spaces dropped")
        self.assertEqual(o.capital_of(u"a"), u"A")
        self.assertEqual(o.capital_of(dot_acute), unicodedata.normalize("NFC", u"E" + u(0x323) + u(0x301)))
        self.assertIsNone(o.capital_of(u"A"))
        self.assertIsNone(o.capital_of(u(0xDF)), "a sharp s has no single capital here")
        self.assertIsNone(o.capital_of(u(0x10D0)), "Georgian: no Mtavruli asked for")
        self.assertIsNone(o.capital_of(u(0x915)))
        self.assertEqual(o.with_capitals([u"a", u(0xDF), u"b"]), [u"a", u"A", u(0xDF), u"b", u"B"])
        self.assertEqual(o.required_marks([u(0x301), u(0x304)], [u(0xE1), u"n" + u(0x308)], []), u(0x304) + u(0x308),
                         "listed marks no character decomposes into, and those of unencoded clusters")
        one = o.shaped("xx", "Deva", "X", "", [u(0x915), u(0x93E), u"a"], [u(0x916), u(0x940), u(0x915)], [], "cldr", True)
        self.assertEqual((one.base, one.auxiliary, one.marks), ([u(0x915), u"a", u"A"], [u(0x916)], u(0x93E)),
                         "lone marks of the main set are marks; of the auxiliary set, left out")
        self.assertIsNone(o.shaped("xx", "Latn", "X", "", [u(0x301)], [], [], "cldr", True), "no base character")

    def test_textproto(self):
        o = self.o
        text = (u'# a comment\nid: "yo_Latn"\nlanguage: "yo"\npopulation: 28685568\nhistorical: true\n'
                u'exemplar_chars {\n  base: "a A {gb} \\303\\251"\n  marks: "x"\n}\n'
                u'source: "one"\nsource: "two \\"quoted\\""\nnote: "first "\n      "second"\n')
        fields = o.parse_textproto(text)
        self.assertEqual(fields["id"], [u"yo_Latn"])
        self.assertEqual(fields["population"], [u"28685568"])
        self.assertEqual(fields["historical"], [u"true"])
        self.assertEqual(fields["exemplar_chars"][0]["base"], [u"a A {gb} " + u(0xE9)], "escapes are bytes of UTF-8")
        self.assertEqual(fields["source"], [u"one", u'two "quoted"'])
        self.assertEqual(fields["note"], [u"first second"], "adjacent strings are one")
        self.assertEqual(o.exemplar_elements(u"a {gb} " + o.MARK_BASE + u(0x301)), [u"a", u"gb", o.MARK_BASE + u(0x301)])

    def test_locales(self):
        o = self.o
        self.assertEqual(o.split_locale("ktz"), ("ktz", None))
        self.assertEqual(o.split_locale("sr_Latn"), ("sr", "Latn"))
        self.assertEqual(o.split_locale("kab-Arab"), ("kab", "Arab"))
        for other in ("pt_PT", "en_Latn_US", "be-tarask", "gsw-u-sd-chag", "root", "test"):
            self.assertIsNone(o.split_locale(other), other)

    def test_counted_text(self):
        """The stated rule of an inferred orthography: letters only, of the text's main script, a
        floor of 1 letter in 2,000 and of 3 places, from 1,000 letters on, capitals with their small
        letters, a letter with its marks in the alphabets."""
        o = self.o
        counter = self.counter()
        dot_acute = unicodedata.normalize("NFC", u"e" + u(0x323) + u(0x301))
        text = (u"Aba " * 400) + (dot_acute + u" ") * 5 + u"q q z 12 34, (x)! " + (u(0x3B1) + u" ") * 9 + (u(0x2BC) + u"a ") * 4
        counts = dict((unit, (times, times)) for unit, times in counter.count(text).items())
        self.assertEqual(counts[u"a"], (804, 804), "capitals counted with their small letters")
        self.assertNotIn(u"1", counts)
        self.assertNotIn(u",", counts)
        size = sum(times for times, _ in counts.values())
        one = counter.orthography(counts, size, "xx", "X", "", "unilex")
        self.assertEqual(one.script, "Latn")
        self.assertEqual(set(one.base), set([u"a", u"A", u"b", u"B", dot_acute, o.capital_of(dot_acute), u(0x2BC)]),
                         "q (twice), z and x (once) are under the floor; the Greek letter is of another script; the "
                         "modifier apostrophe has no script of its own and stays")
        self.assertEqual((one.auxiliary, one.marks), ([], u(0x301)), "base characters only; the cluster's mark is needed")
        self.assertIsNone(counter.orthography(counts, 999, "xx", "X", "", "unilex"), "under 1,000 letters: nothing")
        self.assertIsNone(counter.orthography(counts, size, "xx", "X", "", "unilex", wanted="Grek"),
                          "not the script the source states")
        self.assertIsNotNone(counter.orthography(counts, size, "xx", "X", "", "unilex", wanted="Latn"))
        rare = dict(counts)
        rare[u"w"] = (1, 50)  # (in 50 places, but under 1 letter in 2,000)
        rare[u"a"] = (3000, 804)
        self.assertNotIn(u"w", counter.orthography(rare, size, "xx", "X", "", "unilex").base)
        # Outside the alphabets, letters and marks are counted one by one
        ka, aa = u(0x915), u(0x93E)
        text = (ka + aa + u" ") * 600 + (ka + u" ") * 500
        counts = dict((unit, (times, times)) for unit, times in counter.count(text).items())
        one = counter.orthography(counts, sum(times for times, _ in counts.values()), "xx", "X", "", "gflanguages-text")
        self.assertEqual((one.script, one.base, one.marks), ("Deva", [ka], aa))

    def test_font_characters(self):
        o = self.o
        self.assertEqual(o.ranges_of([0x41, 0x42, 0x43, 0x61, 0x1F600]), "0041-0043 0061 1F600")
        found = o.font_characters()
        import json
        with open(os.path.join(HERE, os.pardir, "checks", "font_characters.json"), "rb") as handle:
            written = json.loads(handle.read().decode("utf-8"))
        self.assertEqual(json.loads(json.dumps(found)), written, "the file is what the data files give now")
        codes = set()
        for key in ("names", "other_names", "orthographies", "sets"):
            for part in written[key].split():
                low, _, high = part.partition("-")
                codes.update(range(int(low, 16), int(high or low, 16) + 1))
        self.assertEqual(len(codes), written["counts"]["all"])
        every = set()
        for one in fc.load_languages(LANGUAGES_FILE, ORTHOGRAPHIES_FILE):
            for text in [one.name, one.autonym, one.script, one.marks] + one.base + one.auxiliary:
                every.update(ord(ch) for ch in text)
        self.assertFalse(every - codes, "every character of every name and orthography is in it")
        self.assertTrue(set([0x1C0, 0x2BC]) <= codes)

    def test_font_characters_bounded(self):
        """The bundled font cannot hold all of Unicode (65,535 glyphs at most): a script's set is drawn
        whole up to 300 characters of its own, a Unicode block's set up to 256, and the list says what
        it leaves out."""
        o = self.o
        self.assertEqual((o.SCRIPT_FONT_LIMIT, o.BLOCK_FONT_LIMIT), (300, 256))
        self.assertEqual((fc.NAMED_SCRIPT_MOST, fc.NAMED_BLOCK_MOST), (o.SCRIPT_FONT_LIMIT, o.BLOCK_FONT_LIMIT),
                         "a tooltip names the characters of the sets the font draws whole, and no others")
        # Every character a set's tooltip names is in the list (a font with nothing: each names its first missing)
        drawn = set()
        for key in ("names", "other_names", "orthographies", "sets"):
            for part in o.font_characters()[key].split():
                low, _, high = part.partition("-")
                drawn.update(range(int(low, 16), int(high or low, 16) + 1))
        nothing = fc.FontCharacters([])
        for one in fc.load_character_sets():
            tip = fc.coverage_tip(fc.check_entry(one, nothing))
            self.assertFalse(sorted(set(fc.code_points(tip)) - drawn - set([0x0A])), one.name)
        found = o.font_characters()
        codes = set()
        for part in found["sets"].split():
            low, _, high = part.partition("-")
            codes.update(range(int(low, 16), int(high or low, 16) + 1))
        self.assertEqual(len(codes), found["counts"]["sets"])
        self.assertLess(found["counts"]["all"], 45000, "room left under 65,535 glyphs")
        self.assertEqual(found["left_out"]["scripts"],
                         ["Anatolian Hieroglyphs", "Arabic", "Bamum", "Canadian Aboriginal", "Cuneiform", "Cyrillic",
                          "Egyptian Hieroglyphs", "Ethiopic", "Greek", "Han", "Hangul", "Hiragana", "Katakana",
                          "Khitan Small Script", "Latin", "Linear A", "Nushu", "SignWriting", "Tangut", "Yi"])
        self.assertEqual(found["left_out"]["blocks"],
                         ["Mathematical Alphanumeric Symbols (Unicode block)",
                          "Symbols for Legacy Computing Supplement (Unicode block)",
                          "Sutton SignWriting (Unicode block)",
                          "Miscellaneous Symbols and Pictographs (Unicode block)"])
        self.assertTrue(set(range(0x1E5D0, 0x1E5FB)) <= codes, "Ol Onal: a script no language here is written in, whole")
        self.assertTrue(set([0x10940, 0x10959]) <= codes, "Sidetic")
        self.assertIn(0x1D400, codes, "a block left out whole keeps what another set brings (the Math property's)")
        self.assertNotIn(0x2A700, codes, "not Han's 103,351 ideographs")
        self.assertNotIn(0x1D800, codes, "nor SignWriting's 672 signs")
        self.assertIn(0x1D100, codes, "Musical Symbols: a block of 225")


class TipTests(unittest.TestCase):
    """Tooltips wrap: the owner's screen showed one a few thousand pixels wide (a tree row's plain
    text is laid out on one line). Each goes out as rich text, in a width when it needs one."""

    def test_width(self):
        self.assertIsNone(fc.tip_width(u"Short.", 520), "a short text needs no width")
        self.assertIsNone(fc.tip_width(u"Short.\nAnother short line.", 520))
        long_line = u"Needed, with other glyphs, by: " + u", ".join([u"Language (with x)"] * 60)
        self.assertEqual(fc.tip_width(u"U+0190: capital open e.\n" + long_line, 520), 520, "its longest line decides")
        self.assertEqual(fc.tip_width(long_line, 300), 300, "no wider than the limit, a narrower window's too")
        self.assertEqual(fc.tip_width(u"abc", 520, lambda line: 9000), 520, "the font's own measure when it gives one")
        self.assertIsNone(fc.tip_width(u"x" * 500, 520, lambda line: 100))
        self.assertEqual(fc.tip_width(u"x" * 500, 520, lambda line: 1 / 0), 520, "a measure that fails: by characters")
        self.assertIsNone(fc.tip_width(u"<i>Diacritics</i> " + u"<b></b>" * 200, 520, None, True), "tags are not text")
        asked = []
        measure = lambda line: asked.append(line) or len(line) * 9
        self.assertEqual(fc.tip_width(u"short\n" + u"x" * 90 + u"\nmid " * 3, 520, measure), 520)
        self.assertEqual(asked, [u"x" * 90], "the longest line first, and no other once one is too wide (thousands "
                                             "of rows have a tooltip each: every line of each was measured)")
        del asked[:]
        self.assertIsNone(fc.tip_width(u"one\nthree", 520, measure))
        self.assertEqual(asked, [u"three", u"one"], "a tooltip that fits: every line asked about")

    def test_html(self):
        self.assertEqual(fc.tip_html(u""), u"")
        self.assertEqual(fc.tip_html(u"a < b & c\nd"), u"<span>a &lt; b &amp; c<br>d</span>", "escaped, a line per line")
        self.assertEqual(fc.tip_html(u"<i>Diacritics</i> cannot.", rich=True), u"<span><i>Diacritics</i> cannot.</span>")
        self.assertEqual(fc.tip_html(u"a", 520),
                         u"<table width=\"520\" cellspacing=\"0\" cellpadding=\"0\"><tr><td>a</td></tr></table>")
        self.assertEqual(fc.tip_html(u"a", None, u"FreeLang"),
                         u"<span style=\"font-family:'FreeLang'\">a</span>")
        self.assertIn(u"<td style=\"font-family:'FreeLang'\">a</td>", fc.tip_html(u"a", 300, u"FreeLang"))
        every = fc.tip_html(u"x" * 9000, fc.tip_width(u"x" * 9000))
        self.assertTrue(every.startswith(u"<table width=\"%d\"" % fc.TIP_WIDTH), "the widest tooltip has a width")


class SingleMasterTests(unittest.TestCase):
    """The owner, of a font with one master: "Should be 'measured in the single master'"."""

    def test_sentences(self):
        self.assertEqual(fc.measured_text(1), u"Every glyph measured in the single master.")
        self.assertEqual(fc.measured_text(2), u"Every glyph measured in every master.")
        self.assertEqual(fc.measured_text(6), u"Every glyph measured in every master.")
        one = [fc.Extent(u"H", 0x48, u"Regular", 0, 700), fc.Extent(u"p", 0x70, u"Regular", -200, 500)]
        two = one + [fc.Extent(u"H", 0x48, u"Bold", 0, 700)]
        self.assertEqual(fc.in_masters(one), u"in the single master")
        self.assertEqual(fc.in_masters(two), u"in every master")
        m = fc.VerticalMetrics(upm=1000.0, ascender=750, descender=-250, cap_height=700, x_height=500, line_gap=0,
                               typo_ascender=800, typo_descender=-200, typo_line_gap=0, hhea_ascender=800,
                               hhea_descender=-200, hhea_line_gap=0, win_ascent=1000, win_descent=250, use_typo=True)
        for extents, words in ((one, u"in the single master."), (two, u"in every master.")):
            notes = fc.suggest_metrics(m, extents)[1]
            self.assertTrue([note for note in notes if note.endswith(u"of every glyph " + words)], notes)
            lines = fc.check_lines(m, extents, fc.check_metrics(m, extents))
            self.assertTrue([line for line in lines if line.tip.endswith(u"of every glyph " + words)],
                            [line.tip for line in lines])


class DiagramTests(unittest.TestCase):
    def test_lines_merged_when_equal(self):
        m = fc.VerticalMetrics(upm=1000, typo_ascender=900, hhea_ascender=900, win_ascent=1000, cap_height=700,
                               x_height=500, typo_descender=-250, hhea_descender=-250, win_descent=250)
        lines = fc.diagram_lines(m)
        self.assertEqual([(l.value, l.label()) for l in lines],
                         [(1000, u"winAscent 1000"), (900, u"typo and hhea ascender 900"), (700, u"cap height 700"),
                          (500, u"x-height 500"), (0, u"baseline 0"),
                          (-250, u"typo and hhea descender, winDescent -250")])
        self.assertEqual(lines[-1].kind, "win", "the win kind wins")

    def test_suggested_lines(self):
        m = fc.VerticalMetrics(upm=1000, typo_ascender=900, hhea_ascender=900, typo_descender=-250,
                               hhea_descender=-250, win_ascent=900, win_descent=250)
        extents = [fc.Extent("A", 0x41, "R", -300, 1100)]
        suggestions, _ = fc.suggest_metrics(m, extents, mode="keep")
        dashed = [(l.value, l.label()) for l in fc.diagram_lines(m, suggestions) if l.kind == "suggested"]
        self.assertEqual(dashed, [(1100, u"winAscent 1100"), (-300, u"winDescent -300")], "the values that change only")

    def test_merge_names(self):
        self.assertEqual(fc.merge_names([u"winAscent", u"typo ascender", u"hhea ascender"]),
                         u"winAscent, typo and hhea ascender")
        self.assertEqual(fc.merge_names([u"cap height"]), u"cap height")

    def test_spread_labels(self):
        placed = fc.spread_labels([10, 12, 13, 50], 10)
        self.assertEqual(placed[3], 50, "alone: where it is wanted")
        self.assertTrue(all(b - a >= 10 - 1e-9 for a, b in zip(placed, placed[1:])), placed)
        self.assertAlmostEqual(sum(placed[:3]) / 3.0, (10 + 12 + 13) / 3.0, msg="a crowd centered on its lines")
        placed = fc.spread_labels([5, 0], 10, low=0)
        self.assertEqual(placed, [10, 0], "the order kept, within bounds, any order given")
        self.assertEqual(fc.spread_labels([100, 99], 10, high=100), [100, 90])

    def test_extremes(self):
        extents = [fc.Extent(n, None, m, b, t) for n, m, b, t in
                   [("A", "L", 0, 700), ("Aring", "L", 0, 900), ("Aring", "B", 0, 950), ("p", "B", -250, 500),
                    ("g", "L", -230, 500), ("bracket", "B", -260, 920), ("dot", "L", -50, 40)]]
        tallest, deepest = fc.extreme_glyphs(extents, 2)
        self.assertEqual([(e.name, e.master) for e in tallest], [("Aring", "B"), ("bracket", "B")])
        self.assertEqual([e.name for e in deepest], ["p", "g"], "a glyph in one list only")

    def test_clipped(self):
        m = fc.VerticalMetrics(upm=1000, win_ascent=1000, win_descent=250)
        extents = [fc.Extent(n, None, ma, b, t) for n, ma, b, t in
                   [("Aring", "L", 0, 1010), ("Aring", "B", 0, 1080), ("g", "B", -300, 500), ("H", "B", 0, 700)]]
        found = fc.clipped_glyphs(m, extents)
        self.assertEqual([(c.extent.name, c.extent.master, c.above, c.below) for c in found],
                         [("Aring", "B", 80, 0), ("g", "B", 0, 50)], "each glyph once, in its worst master")
        self.assertEqual([c.extent.master for c in fc.clipped_glyphs(m, extents, "L")], ["L"])
        self.assertEqual(fc.clipped_glyphs(fc.VerticalMetrics(upm=1000), extents), [], "no win values: nothing known")

    def test_check_lines(self):
        m = fc.VerticalMetrics(upm=1000, win_ascent=1000, win_descent=250, typo_ascender=950, typo_descender=-250,
                               typo_line_gap=0, hhea_ascender=950, hhea_descender=-250, hhea_line_gap=0, use_typo=True,
                               cap_height=700)
        extents = [fc.Extent("Aring", 0xC5, "B", 0, 1082), fc.Extent("Agrave", 0xC0, "B", 0, 900),
                   fc.Extent("g", 0x67, "B", -300, 500)]
        lines = fc.check_lines(m, extents, fc.check_metrics(m, extents))
        texts = [(line.state, line.text) for line in lines]
        self.assertEqual(texts[:2], [("warn", u"Windows clips 1 glyph at the top, up to 82 units (Aring)"),
                                     ("warn", u"Windows clips 1 glyph at the bottom, up to 50 units (g)")])
        self.assertEqual(lines[0].glyphs, [u"Aring"])
        for passed in (u"Use Typo Metrics is on", u"hhea and typo values match", u"Line gaps are 0",
                       u"The line is 120% of the em", u(0xC0) + u" stays under the line's ascender",
                       u"Capitals are centered in the line"):
            self.assertIn(("ok", passed), texts)
        self.assertEqual([line.state for line in lines], sorted((line.state for line in lines),
                                                               key=["warn", "info", "ok"].index), "problems first")
        gaps = fc.VerticalMetrics(upm=1000, typo_ascender=750, typo_descender=-250, typo_line_gap=200,
                                  hhea_ascender=750, hhea_descender=-250, hhea_line_gap=100)
        texts = [line.text for line in fc.check_lines(gaps, [], fc.check_metrics(gaps, []))]
        self.assertIn(u"Line gaps 100 and 200: set them to 0 and add them to the ascender and descender", texts)
        self.assertIn(u"winAscent and winDescent are not set", texts)
        self.assertIn(u"FontLab did not say whether Use Typo Metrics is on", texts)
        unset = fc.VerticalMetrics(upm=1000, typo_ascender=750, typo_descender=-250, typo_line_gap=0)
        self.assertIn(u"The hhea values are not set in Font Info",
                      [line.text for line in fc.check_lines(unset, [], fc.check_metrics(unset, []))])


class MasterRowsTests(unittest.TestCase):
    def found(self):
        I = fc.Incompatibility
        return [I(u"o", u"Bold", 1, "start", u"Start point 1 node on from where Light's would match"),
                I(u"a", u"Bold", 2, "nodes", u"12 nodes, 14 in Light"), I(u"a", u"Black", None, "missing", u"No layer"),
                I(u"e", u"Bold", None, "anchors", u"Lacks anchor top"), I(u"e", u"Black", None, "anchors", u"Lacks anchor top"),
                I(u"n", u"Bold", 1, "direction", u"Runs clockwise, counterclockwise in Light")]

    def test_counts_and_order(self):
        found = self.found()
        self.assertEqual(fc.problem_counts(found), [("missing", u"No layer", 1), ("nodes", u"Node counts", 1),
                                                    ("direction", u"Directions", 1), ("start", u"Start points", 1),
                                                    ("anchors", u"Anchors", 1)])
        self.assertEqual([g for g, _ in fc.glyph_problems(found)], [u"a", u"n", u"o", u"e"], "the worst first")
        self.assertEqual([g for g, _ in fc.glyph_problems(found, set(["anchors", "start"]))], [u"o", u"e"])

    def test_master_marks(self):
        problems = [f for f in self.found() if f.glyph == u"a"]
        self.assertEqual(fc.master_states(problems, [u"Light", u"Regular", u"Bold", u"Black"], u"Light"),
                         ["reference", "ok", "grave", "missing"])
        anchors = [f for f in self.found() if f.glyph == u"e"]
        self.assertEqual(fc.master_states(anchors, [u"Light", u"Bold"], u"Light"), ["reference", "minor"])

    def test_problem_sentence(self):
        problems = [f for f in self.found() if f.glyph == u"a" and f.master == u"Bold"]
        self.assertEqual(fc.problem_sentence(problems), u"Contour 2: 12 nodes, 14 in Light.")


def curve(points_and_types):
    return fc.Contour([(x, y, t) for x, y, t in points_and_types])


# An o: its outer contour counterclockwise, on-curve extremes and off-curve handles between them; its
# counter clockwise. A bowl with a straight side (types not symmetric: only one start matches).
O_OUTER = [(250, 0, u"on"), (400, 0, u"off"), (500, 100, u"off"), (500, 250, u"on"), (500, 400, u"off"),
           (400, 500, u"off"), (250, 500, u"on"), (100, 500, u"off"), (0, 400, u"off"), (0, 250, u"on"),
           (0, 100, u"off"), (100, 0, u"off")]
O_INNER = [(250, 100, u"on"), (150, 100, u"off"), (100, 150, u"off"), (100, 250, u"on"), (100, 350, u"off"),
           (150, 400, u"off"), (250, 400, u"on"), (350, 400, u"off"), (400, 350, u"off"), (400, 250, u"on"),
           (400, 150, u"off"), (350, 100, u"off")]
D_BOWL = [(0, 0, u"on"), (300, 0, u"on"), (450, 0, u"off"), (550, 150, u"off"), (550, 350, u"on"),
          (550, 550, u"off"), (450, 700, u"off"), (300, 700, u"on"), (0, 700, u"on")]
DOT = [(200, 600, u"on"), (300, 600, u"on"), (300, 700, u"on")]


def bolder(nodes, dx=30, dy=10):
    """A heavier master: the same structure, points moved apart from the middle."""
    return [(x + (dx if x > 250 else -dx), y + (dy if y > 300 else -dy), t) for x, y, t in nodes]


class FixPlanTests(unittest.TestCase):
    """Masters: what Fix sets right, planned without FontLab, then the plan's result compared again."""

    def problems(self, reference, outline):
        return fc.compare_glyph(u"g", [(u"Regular", reference), (u"Bold", outline)])

    def fixed(self, reference, outline):
        plan = fc.plan_fixes(reference, outline)
        return plan, fc.apply_plan(outline, plan)

    def test_fontlab_like_edits(self):
        nodes = [(0, 0, u"on"), (1, 0, u"off"), (2, 0, u"on"), (3, 0, u"on")]
        self.assertEqual(fc.reversed_contour(fc.Contour(nodes)).nodes, [nodes[0], nodes[3], nodes[2], nodes[1]],
                         "the first node kept first, as flContour.reverse()")
        self.assertEqual(fc.rotated_contour(fc.Contour(nodes), 2).nodes, nodes[2:] + nodes[:2], "setStartPoint(2)")

    def test_direction_and_start_fixed(self):
        reference = fc.Outline([curve(O_OUTER), curve(O_INNER)])
        bold = [bolder(O_OUTER), bolder(O_INNER)]
        planted = fc.Outline([curve(bold[0][::-1]), curve(bold[1][3:] + bold[1][:3])])
        found = self.problems(reference, planted)
        self.assertEqual([(f.contour, f.kind, f.fixable) for f in found], [(1, "direction", True), (2, "start", True)])
        plan, result = self.fixed(reference, planted)
        self.assertEqual([(at, reverse) for at, reverse, _, _ in plan.contours], [(0, True), (1, False)])
        self.assertEqual(self.problems(reference, result), [], "compatible once fixed")
        self.assertEqual(result.contours[0].nodes, curve(bold[0]).nodes, "back to the heavier master's own drawing")
        self.assertEqual(fc.plan_steps(plan, u"Regular"), [u"contour 1 reversed, its start point moved 1 node on",
                                                           u"contour 2's start point moved 3 nodes back"])

    def test_start_by_node_types(self):
        reference = fc.Outline([curve(D_BOWL)])
        moved = bolder(D_BOWL)
        moved = moved[4:] + moved[:4]  # onto another on-curve node: the node types no longer line up
        found = self.problems(reference, fc.Outline([curve(moved)]))
        self.assertEqual([(f.kind, f.fixable) for f in found], [("start", True)])
        self.assertIn(u"node types match from there", found[0].text)
        plan, result = self.fixed(reference, fc.Outline([curve(moved)]))
        self.assertEqual(self.problems(reference, result), [])

    def test_off_curve_start_left_to_the_designer(self):
        reference = fc.Outline([curve([(0, 0, u"off"), (100, 0, u"on"), (100, 100, u"off"), (0, 100, u"on"),
                                       (-50, 50, u"on")])])
        moved = reference.contours[0].nodes[1:] + reference.contours[0].nodes[:1]
        found = self.problems(reference, fc.Outline([fc.Contour(moved)]))
        self.assertEqual([(f.kind, f.fixable) for f in found], [("start", False)], "the start would be off-curve")
        self.assertTrue(fc.plan_fixes(reference, fc.Outline([fc.Contour(moved)])).empty())
        self.assertIn(u"needs the designer", fc.fix_sentence(found).lower())

    def test_contour_order(self):
        reference = fc.Outline([curve(D_BOWL), curve(DOT), contour(SQUARE)])
        bold = fc.Outline([contour([(x, y + 5) for x, y in SQUARE]), curve(bolder(D_BOWL)), curve(DOT)])
        found = self.problems(reference, bold)
        self.assertEqual([(f.kind, f.fixable) for f in found], [("order", True)])
        plan, result = self.fixed(reference, bold)
        self.assertEqual(plan.order, [1, 2, 0])
        self.assertEqual(self.problems(reference, result), [])
        self.assertEqual(fc.plan_steps(plan, u"Regular"), [u"contours put in Regular's order"])
        split = fc.Outline(bold.contours, blocks=[1, 2])  # its contours in two shapes: none may cross
        self.assertEqual([(f.kind, f.fixable) for f in self.problems(reference, split)], [("order", False)])
        self.assertTrue(fc.plan_fixes(reference, split).empty())

    def test_order_matched_by_place(self):
        # two dots of one node count: told apart by where they sit once the order is wrong anyway
        left_dot, right_dot = [(0, 0), (50, 0), (25, 40)], [(400, 0), (450, 0), (425, 40)]
        reference = fc.Outline([contour(left_dot), contour(SQUARE), contour(right_dot)])
        bold = fc.Outline([contour(right_dot), contour(left_dot), contour(SQUARE)])
        self.assertEqual(fc.match_contours(reference.contours, bold.contours), [1, 2, 0])
        plan, result = self.fixed(reference, bold)
        self.assertTrue(fc.same_outline(result, reference))

    def test_order_then_direction(self):
        reference = fc.Outline([curve(D_BOWL), curve(DOT)])
        bold = fc.Outline([curve(DOT[::-1]), curve(D_BOWL)])
        plan, result = self.fixed(reference, bold)
        self.assertEqual(plan.order, [1, 0])
        self.assertEqual([(at, reverse) for at, reverse, _, _ in plan.contours], [(1, True)])
        self.assertEqual(self.problems(reference, result), [])

    def test_designer_problems_untouched(self):
        reference = fc.Outline([contour(SQUARE), contour(TRIANGLE)], [u"a"], [u"top"])
        bold = fc.Outline([contour(SQUARE[::-1]), contour(SQUARE)], [u"b"], [])
        found = self.problems(reference, bold)
        self.assertEqual(sorted((f.kind, f.fixable) for f in found),
                         [("anchors", False), ("components", False), ("direction", True), ("nodes", False)])
        self.assertEqual(fc.fix_state(found), "some")
        plan = fc.plan_fixes(reference, bold)
        self.assertEqual(([at for at, _, _, _ in plan.contours], plan.order, plan.components), ([0], None, None))
        self.assertEqual(fc.fix_sentence(found), u"Fix sets the direction right; the node count (add or remove nodes), "
                                                 u"the components (add or remove them), and the anchors (add or remove "
                                                 u"them) need the designer.")
        types = fc.Outline([fc.Contour([(0, 0, u"on"), (100, 0, u"off"), (100, 100, u"on"), (0, 100, u"on")])])
        self.assertTrue(fc.plan_fixes(fc.Outline([contour(SQUARE)]), types).empty(), "node types: left alone")
        self.assertEqual(fc.fix_state(self.problems(fc.Outline([contour(SQUARE)]), types)), "none")

    def test_open_contour_start_not_moved(self):
        line = [(0, 0), (100, 0), (100, 100), (0, 100)]
        reference = fc.Outline([fc.Contour([(x, y, u"on") for x, y in line], closed=False)])
        moved = fc.Outline([fc.Contour([(x, y, u"on") for x, y in line[1:] + line[:1]], closed=False)])
        self.assertTrue(fc.plan_fixes(reference, moved).empty(), "an open contour's start is its end")

    def test_components(self):
        self.assertEqual(fc.component_order([u"a", u"acutecomb"], [u"acutecomb", u"a"]), [1, 0])
        self.assertEqual(fc.component_order([u"a", u"dot", u"dot"], [u"dot", u"a", u"dot"]), [1, 0, 2],
                         "the same names taken in turn")
        self.assertIsNone(fc.component_order([u"a"], [u"a"]))
        self.assertIsNone(fc.component_order([u"a"], [u"b"]))
        reference = fc.Outline([], [u"a", u"acutecomb"])
        plan, result = self.fixed(reference, fc.Outline([], [u"acutecomb", u"a"]))
        self.assertEqual((result.components, plan.names), ([u"a", u"acutecomb"], [u"a", u"acutecomb"]))

    def test_reference_left_alone(self):
        reference = fc.Outline([curve(O_OUTER)])
        kept = [n for n in reference.contours[0].nodes]
        self.fixed(reference, fc.Outline([curve(O_OUTER[::-1])]))
        self.assertEqual(reference.contours[0].nodes, kept)

    def test_assignment(self):
        import itertools
        import random
        rng = random.Random(7)
        for n in range(1, 7):
            for _ in range(20):
                cost = [[rng.randint(0, 30) for _ in range(n)] for _ in range(n)]
                found = fc.assignment(cost)
                best = min(sum(cost[i][p[i]] for i in range(n)) for p in itertools.permutations(range(n)))
                self.assertEqual(sorted(found), list(range(n)))
                self.assertEqual(sum(cost[i][found[i]] for i in range(n)), best)

    def test_blocks(self):
        self.assertTrue(fc.within_blocks([1, 0, 2], [2, 1]))
        self.assertFalse(fc.within_blocks([2, 1, 0], [2, 1]))
        self.assertTrue(fc.within_blocks([2, 1, 0], None))

    def test_fix_texts(self):
        I = fc.Incompatibility
        fixable = [I(u"o", u"Bold", 1, "direction", u"", True), I(u"o", u"Bold", 2, "start", u"", True)]
        self.assertEqual(fc.fix_state(fixable), "all")
        self.assertEqual(fc.fix_sentence(fixable), u"Fix sets the direction and the start point right.")
        designer = [I(u"a", u"Bold", None, "missing", u"")]
        self.assertEqual(fc.fix_sentence(designer), u"Needs the designer: the missing layer (add it).")
        self.assertEqual(fc.FIX_LABELS[fc.fix_state(designer)], u"Needs the designer")


class MetricWritesTests(unittest.TestCase):
    def test_writes(self):
        m = fc.VerticalMetrics(upm=1000, cap_height=700, typo_ascender=950, typo_descender=-250, typo_line_gap=0,
                               hhea_ascender=None, hhea_descender=-250, hhea_line_gap=0, win_ascent=1000,
                               win_descent=300, use_typo=False)
        extents = [fc.Extent("A", 0x41, "R", -300, 1000)]
        suggestions, _ = fc.suggest_metrics(m, extents)
        writes = fc.metric_writes(suggestions)
        self.assertEqual([s.key for s in writes], ["hhea_ascender", "use_typo"], "those that differ only")
        self.assertEqual(fc.write_text(writes[0]), u"hhea ascender not set \N{RIGHTWARDS ARROW} 950")
        self.assertEqual(fc.write_text(writes[-1]), u"Use Typo Metrics off \N{RIGHTWARDS ARROW} on")
        self.assertEqual(fc.selection_with([0, 6], True), [0, 6, 7])
        self.assertEqual(fc.selection_with([7, 0], True), [0, 7])
        self.assertEqual(fc.selection_with([7], False), [])
        self.assertEqual(fc.selection_with(None, True), [7])
        same = fc.VerticalMetrics(**dict((s.key, s.value) for s in suggestions))
        same.upm, same.cap_height = 1000, 700
        self.assertEqual(fc.metric_writes(fc.suggest_metrics(same, extents)[0]), [], "as suggested: nothing to write")


# ---------------------------------------------------------------------------
# The dialog, run on fakes: any Qt call is accepted and does nothing; the font is a small fake of
# FontLab's (two masters, a glyph that does not interpolate, an anchored letter and mark). This
# catches mistakes in the dialog's own code paths, not in how Qt or FontLab answer.
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


Anything = _AnyMeta("Anything", (object,), {
    "__init__": lambda self, *args, **kwargs: None,
    "__getattr__": _no_dunder,
    "__call__": lambda self, *args, **kwargs: Anything(),
    "__iter__": lambda self: iter([]),
    "__len__": lambda self: 0,
    "__int__": lambda self: 0, "__index__": lambda self: 0, "__float__": lambda self: 0.0,
    "__bool__": lambda self: False, "__nonzero__": lambda self: False,
    "__or__": lambda self, other: Anything(), "__ror__": lambda self, other: Anything(),
    "__add__": lambda self, other: 0, "__radd__": lambda self, other: 0, "__sub__": lambda self, other: 0,
    "__rsub__": lambda self, other: 0, "__mul__": lambda self, other: 0, "__rmul__": lambda self, other: 0,
    "__truediv__": lambda self, other: 0, "__div__": lambda self, other: 0, "__neg__": lambda self: 0,
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


class Recorded(Anything):
    """A fake widget that remembers what it was told: made (its constructor's arguments), told(name)
    (the arguments of each call of that setter or adder), and, as a Qt property reads under PythonQt,
    the value last set (after setChecked(True), checked is True)."""

    def __init__(self, *args, **kwargs):
        self.__dict__["made"] = args
        self.__dict__["calls"] = []

    def told(self, name):
        return [args for called, args in self.calls if called == name]

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if not (name.startswith("set") or name.startswith("add")):
            return Anything()

        def call(*args, **kwargs):
            self.calls.append((name, args))
            if name.startswith("set") and len(args) == 1:
                self.__dict__[name[3].lower() + name[4:]] = args[0]
            return Anything()
        return call


class FakeNode(object):
    def __init__(self, x, y, kind=u"on"):
        self.x, self.y, self.type = x, y, kind


class FakeContour(object):
    """A contour as FontLab edits it: reverse() keeps the first node first; setStartPoint takes an
    on-curve node only (an off-curve one did nothing live)."""

    def __init__(self, points):
        self.items = [p if len(p) == 3 else (p[0], p[1], u"on") for p in points]
        self.closed = True

    @property
    def points(self):
        return [(x, y) for x, y, _ in self.items]

    def nodes(self):
        return [FakeNode(x, y, t) for x, y, t in self.items]

    def path(self):
        return self.points

    def reverse(self):
        self.items = self.items[:1] + self.items[:0:-1]

    def setStartPoint(self, index):
        if self.items[index][2] != u"on":
            return False
        self.items = self.items[index:] + self.items[:index]
        return True

    def clone(self):
        found = FakeContour(self.items)
        found.closed = self.closed
        return found


class FakeTransform(object):
    def m11(self):
        return 1.0

    m22 = m11

    def m12(self):
        return 0.0

    m21 = dx = dy = m12

    def map(self, points):
        return points


class FakeShape(object):
    def __init__(self, contours=(), component=None):
        self.contours = [FakeContour(c) for c in contours]
        self.isComponent = component is not None
        self.shapeData = Anything()
        self.shapeData.componentGlyph = component
        self.transform = FakeTransform()

    def clearContours(self):
        self.contours = []

    def addContours(self, contours, notify):
        self.contours.extend(contours)


class FakeAnchor(object):
    def __init__(self, name):
        self.name = name


class FakeLayer(object):
    def __init__(self, shapes, anchors=(), advance=500):
        self.shapes, self.anchors, self.advanceWidth = shapes, [FakeAnchor(a) for a in anchors], advance
        self.isNull = False

    def reorderShapes(self, order):
        """The new order: the index of the shape each place takes (one reading of the unproven call)."""
        self.shapes = [self.shapes[k] for k in order]


class FakePath(object):
    def __init__(self, layer):
        self.points = [p for shape in layer.shapes for c in shape.contours for p in c.points]

    def isEmpty(self):
        return not self.points

    def boundingRect(self):
        xs, ys = [p[0] for p in self.points], [p[1] for p in self.points]
        rect = Anything()
        rect.left, rect.right = (lambda: min(xs)), (lambda: max(xs))
        rect.top, rect.bottom = (lambda: min(ys)), (lambda: max(ys))  # (font units up: top() is the lowest)
        return rect


class FakeFontgateGlyph(object):
    def __init__(self, name, code):
        self.name, self.unicode, self.unicodes = name, code, [code] if code else []


class FakeGlyph(object):
    def __init__(self, name, code, layers):
        self.name, self.isNull, self.mark = name, False, 0
        self.layers_by_master = layers
        self.fgGlyph = FakeFontgateGlyph(name, code)

    def getLayerByName(self, master):
        return self.layers_by_master.get(master)

    @property
    def layers(self):
        return list(self.layers_by_master.values())


def square(top):
    return [(0, 0), (400, 0), (400, top), (0, top)]


def both_masters(make):
    return dict((master, make()) for master in (u"Regular", u"Bold"))


class FakePackage(object):
    made = 0

    def __init__(self):
        glyphs = [FakeGlyph(u"H", 0x48, both_masters(lambda: FakeLayer([FakeShape([square(700)])]))),
                  FakeGlyph(u"e", 0x65, both_masters(lambda: FakeLayer([FakeShape([square(500)])], [u"top"]))),
                  FakeGlyph(u"acutecomb", 0x301, both_masters(lambda: FakeLayer([FakeShape([square(100)])], [u"_top"]))),
                  FakeGlyph(u"Agrave", 0xC0, both_masters(lambda: FakeLayer([FakeShape([square(1100)])]))),
                  FakeGlyph(u"o", 0x6F, {u"Regular": FakeLayer([FakeShape([square(500)])]),
                                         u"Bold": FakeLayer([FakeShape([square(500)[::-1]])])}),
                  FakeGlyph(u"eacute", None, {u"Regular": FakeLayer([FakeShape(component=u"e"),
                                                                     FakeShape(component=u"acutecomb")])}),
                  FakeGlyph(u"Hacute", None, {u"Regular": FakeLayer([FakeShape(component=u"H"),
                                                                     FakeShape(component=u"acutecomb")]),
                                              u"Bold": FakeLayer([FakeShape(component=u"acutecomb"),
                                                                  FakeShape(component=u"H")])}),
                  FakeGlyph(u"i", 0x69, {u"Regular": FakeLayer([FakeShape([square(500), [(0, 600), (100, 600), (50, 700)]])]),
                                         u"Bold": FakeLayer([FakeShape([[(0, 600), (120, 600), (60, 710)], square(520)])])}),
                  FakeGlyph(u"x", 0x78, {u"Regular": FakeLayer([FakeShape([square(500)])]),
                                         u"Bold": FakeLayer([FakeShape([[(0, 0), (400, 0), (200, 500)]])])})]
        self.by_name = dict((g.name, g) for g in glyphs)
        self.fgPackage = Anything()
        self.fgPackage.glyphs = [g.fgGlyph for g in glyphs]
        FakePackage.made += 1
        self.fgPackage.id = FakePackage.made  # (FontLab's: one per open font)
        self.fgPackage.info = Anything()
        for field, value in (("openTypeOS2WinAscent", 1000), ("openTypeOS2WinDescent", 250),
                             ("openTypeOS2TypoAscender", 800), ("openTypeOS2TypoDescender", -200),
                             ("openTypeOS2TypoLineGap", 0), ("openTypeHheaAscender", 900),
                             ("openTypeHheaDescender", -200), ("openTypeHheaLineGap", 0), ("openTypeOS2Selection", [7])):
            setattr(self.fgPackage.info, field, value)
        self.isNull, self.glyphsCount, self.upm, self.tfn, self.path = False, len(glyphs), 1000, u"Fake", u"fake.vfc"
        self.master, self.masters, self.mastersCount, self.defaultMaster = u"Regular", [u"Regular", u"Bold"], 2, u"Regular"
        self.ascender_value, self.descender_value, self.capsHeight_value, self.xHeight_value = 750, -250, 700, 500
        self.lineGap_value = 0

    def findName(self, name):
        return self.by_name.get(name)

    def findUnicode(self, code):
        return next((g for g in self.by_name.values() if g.fgGlyph.unicode == code), None)

    def currentHistoryState(self):
        return 1


class ReorderShapesTests(unittest.TestCase):
    """flLayer.reorderShapes is unproven: whichever way it reads its list, the components end in the
    reference's order and the other shapes stay where they are."""

    def layer(self, reorder):
        layer = FakeLayer([FakeShape(component=u"c"), FakeShape([square(100)]), FakeShape(component=u"a"),
                           FakeShape(component=u"b")])
        layer.reorderShapes = lambda order: reorder(layer, order)
        return layer

    def names(self, layer):
        return [s.shapeData.componentGlyph if s.isComponent else u"(contours)" for s in layer.shapes]

    def test_any_reading(self):
        def take(layer, order):
            layer.shapes = [layer.shapes[k] for k in order]

        def put(layer, order):
            shapes = list(layer.shapes)
            for k, at in enumerate(order):
                layer.shapes[at] = shapes[k]

        def shapes_only(layer, order):
            if any(isinstance(item, int) for item in order):
                raise TypeError("expected flShape")
            layer.shapes = list(order)

        for reorder in (take, put, shapes_only):
            layer = self.layer(reorder)
            fc.reorder_components(layer, [u"a", u"b", u"c"])  # (a cycle of three: taking and putting differ)
            self.assertEqual(self.names(layer), [u"a", u"(contours)", u"b", u"c"], reorder.__name__)

    def test_refused(self):
        layer = self.layer(lambda layer, order: None)
        self.assertRaises(fc.FixError, fc.reorder_components, layer, [u"a", u"b", u"c"])

    def test_contours_reordered_within_their_shape(self):
        layer = FakeLayer([FakeShape([square(100), [(0, 0), (10, 0), (5, 10)]]), FakeShape([square(300)])])
        fc.apply_fix(layer, fc.FixPlan(order=[1, 0, 2]))
        self.assertEqual([[len(c.points) for c in s.contours] for s in layer.shapes], [[3, 4], [4]])
        self.assertRaises(fc.FixError, fc.apply_fix, layer, fc.FixPlan(order=[2, 1, 0]))


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        cls.saved = dict((name, sys.modules.get(name)) for name in ("PythonQt", "fontlab", fc.AUTO_KERNING_MODULE))
        qt = Anything()
        qt.QtCore, qt.QtGui = _FakeQtModule(), _FakeQtModule()
        workspace = cls.workspace = Anything()
        workspace.packages = lambda: [workspace.currentPackage]
        fontlab = Anything()
        fontlab.flWorkspace = Anything()
        fontlab.flWorkspace.instance = lambda: workspace
        sys.modules["PythonQt"], sys.modules["fontlab"] = qt, fontlab
        cls.ak_layer_path, cls.ak_stamp = ak.layer_path, getattr(ak, "_freelab_stamp", "unset")
        ak.layer_path = FakePath
        ak._freelab_stamp = None  # (load_auto_kerning finds no file beside the script: the one loaded here is kept)
        sys.modules[fc.AUTO_KERNING_MODULE] = ak
        cls.ak = ak
        # (the sets a user saved on this computer are not the tests': a file no one has)
        cls.sets_file, fc.CUSTOM_SETS_FILE = fc.CUSTOM_SETS_FILE, u"font_check_sets_of_the_tests.json"

    @classmethod
    def tearDownClass(cls):
        fc.CUSTOM_SETS_FILE = cls.sets_file
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

    def dialog(self):
        self.workspace.currentPackage = FakePackage()  # (a font of its own: the fixes and writes change it)
        dialog = fc.FontCheckDialog()
        self.assertIsNone(dialog.failed, dialog.failed)
        dialog.log.add = lambda text, level="info": self.fail(text) if level == "error" else None
        return dialog

    def test_coverage(self):
        dialog = self.dialog()
        dialog.composing.checked = True
        dialog.nearly.value = 3
        dialog.check_coverage()
        found = [f for f in dialog.coverage.findings if f.composed]
        self.assertTrue(found, "e with acute, composed by the anchors")
        self.assertIn((u"e" + u(0x301), (0x65, (0x301,))),
                      [(unicodedata.normalize("NFD", c), r) for c, r in found[0].composed])
        dialog.nearly.value, dialog.show_absent.checked = 30, True  # (the fake font has five letters)
        dialog.check_coverage()
        self.assertTrue(dialog.rows, "characters to add, the scripts the font lacks shown too")
        dialog.checked = set(dialog.rows[0].items)
        dialog.update_gain()
        one = dialog.rows[0].needing[0]
        dialog.select(fc.selection_of(one))
        self.assertEqual((dialog.left_tab, dialog.selection.results), ("own", [one]))
        self.assertTrue(dialog.own_rows and all(set(fc.needs(one)) & set(row.items) for row in dialog.own_rows))
        dialog.select(None)
        self.assertEqual((dialog.left_tab, dialog.selection, dialog.own_rows), ("value", None, []))
        dialog.update_buttons()
        dialog.set_checks("all")
        self.assertEqual(dialog.checked, set(i for row in dialog.rows for i in row.items))
        dialog.set_checks("none")
        self.assertEqual(dialog.checked, set())
        dialog.buildable = set([dialog.rows[-1].items[0]])
        dialog.set_checks("buildable")
        self.assertEqual(dialog.checked, set(dialog.rows[-1].items))
        dialog.set_checks("buildable")  # (grayed out: nothing changes)
        self.assertEqual(dialog.checked, set(dialog.rows[-1].items))

    def test_checks_shared_by_the_two_tabs(self):
        """The owner: the buttons "work on whichever tab is shown, and a character checked in one tab is
        checked in the other"."""
        dialog = self.dialog()
        dialog.nearly.value, dialog.show_absent.checked = 30, True
        dialog.check_coverage()
        dialog.set_checks("none")
        within = [r for r in dialog.results if r.level == "nearly" and len(fc.needs(r)) < len(dialog.rows)]
        one = min(within, key=lambda r: len(fc.needs(r)))
        dialog.select(fc.selection_of(one))
        own = set(item for row in dialog.own_rows for item in row.items)
        self.assertEqual(dialog.shown_rows(), dialog.own_rows)
        dialog.set_checks("all")
        self.assertEqual(dialog.checked, own, "Check all: the rows of the tab shown")
        self.assertEqual(set(dialog.chosen_characters()), own)
        dialog.show_left("value")
        self.assertEqual(dialog.shown_rows(), dialog.rows)
        listed = set(item for row in dialog.rows for item in row.items)
        self.assertEqual(set(dialog.chosen_characters()), own & listed, "checked in the other tab: checked here")
        self.assertTrue(own & listed, "a language within reach: its characters are high-value rows too")
        dialog.set_checks("all")
        self.assertEqual(dialog.checked, own | listed, "the checks of rows not listed are kept")
        dialog.left_tab_changed(1)
        self.assertEqual((dialog.left_tab, set(dialog.chosen_characters())), ("own", own),
                         "Copy and Build act on the tab shown")
        dialog.set_checks("none")
        self.assertEqual(dialog.checked, set())
        # A row unchecked by hand in one tab: its characters unchecked for both
        dialog.checked = set(own)
        row = dialog.own_rows[0]
        dialog.row_checked(row, False)
        self.assertEqual(dialog.checked, own - set(row.items))
        dialog.row_checked(row, True)
        self.assertEqual(dialog.checked, own)
        dialog.select(None)
        dialog.left_tab_changed(1)
        self.assertEqual(dialog.left_tab, "value", "nothing selected: the second tab is grayed, never shown")
        dialog.left_tab_changed(Anything())  # (a signal's handler: it must not raise)

    def test_double_click_opens_that_character(self):
        """The owner: "Clicking on a given character when there are ticked characters opens the list of
        ticked characters instead of the individual, targeted glyph."""
        dialog, state, click, Row = self.linked_lists()
        opened = []
        dialog.open_glyph_text = opened.append
        dialog.checked = set(item for row in dialog.rows[:2] for item in row.items)
        target = dialog.rows[-1]
        dialog.character_double_clicked("value", Row(len(dialog.rows) - 1))
        self.assertEqual(opened, [u"".join(target.items)], "that row's character, whatever is checked")
        self.assertEqual(dialog.glyph_window_text(), u"".join(sorted(dialog.checked, key=fc.code_points)),
                         "the button: the checked ones")
        self.assertIn(u"checked glyphs of this tab", dialog.glyph_window_tip())
        self.assertIn(u"A double-click on a row opens that row's glyph alone", dialog.glyph_window_tip())
        dialog.checked = set(dialog.rows[0].items[:1])
        if len(dialog.rows[0].items) == 1:
            self.assertIn(u"Opens the 1 checked glyph of this tab", dialog.glyph_window_tip())
        dialog.checked = set()
        dialog.selected_row = lambda: target
        self.assertEqual(dialog.glyph_window_text(), u"".join(sorted(target.items, key=fc.code_points)),
                         "none checked: the selected row")
        self.assertIn(u"selected row's", dialog.glyph_window_tip())
        dialog.selected_row = lambda: None
        self.assertEqual(dialog.glyph_window_text(), u"")
        self.assertTrue(dialog.glyph_window_tip().startswith(u"Check glyphs or select a row first."))
        dialog.select(fc.selection_of(target.needing[0]))
        dialog.character_double_clicked("own", Row(0))
        self.assertEqual(opened[-1], u"".join(dialog.own_rows[0].items), "in the selection's tab too")
        dialog.character_double_clicked("own", Row(9999))
        dialog.character_double_clicked("value", None)  # (a row of an earlier filling, or none: nothing, no error)
        self.assertEqual(len(opened), 2)

    def linked_lists(self):
        """A dialog checked, its lists at the right stood in for: the selection is the test's to set,
        as Qt would after a press, and the calls that clear it are counted. Row: a list's row (what its
        item's data gives, and what the dialog tells it)."""
        dialog = self.dialog()
        dialog.nearly.value, dialog.show_absent.checked = 30, True
        dialog.check_coverage()
        state = {"selected": None, "cleared": 0, "add cleared": 0}

        class Row(object):
            def __init__(self, data):
                self.value, self.expanded, self.icons, self.children = data, None, 0, []

            def data(self, column, role):
                return self.value

            def addChild(self, child):  # (a closed row's rows are made as it is opened)
                self.children.append(child)

            def setExpanded(self, on):
                self.expanded = on

            def setIcon(self, column, icon):
                self.icons += 1

        def cleared(key):
            def clear():
                state[key] += 1
                if key == "cleared" and state["selected"] is not None:
                    state["selected"] = None
                    dialog.right_selected(dialog.right_tab)  # (Qt's itemSelectionChanged)
            return clear

        for tree in dialog.right_trees.values():
            tree.clearSelection = cleared("cleared")
        dialog.add_tree.clearSelection = cleared("add cleared")
        dialog.selected_entry = lambda tab: state["selected"]

        def click(what, pos=None, double=False):
            """A mouse press and its click on the list shown at the right: on the row of that index, on a
            heading ("#" and its title), or on its empty part (None). pos: where in the row (None: on
            its text); double: a double-click's second press. The row stood in is handed back."""
            tab = dialog.right_tab
            row = None if what is None else Row(what)
            used = dialog.list_pressed(dialog.right_trees[tab], row, pos, double)
            entry = dialog.right_entry(tab, row)
            if not used and entry is not None and entry[0] != "heading" and state["selected"] != entry:
                state["selected"] = entry  # (Qt selects the row pressed)
                dialog.right_selected(tab)
            if row is not None and not used:
                dialog.right_clicked(tab)
            return row
        return dialog, state, click, Row

    def test_linked_lists(self):
        dialog, state, click, Row = self.linked_lists()
        rows = [row.key() for row in dialog.rows]
        self.assertEqual((dialog.selection, dialog.left_tab, dialog.own_rows), (None, "value", []),
                         "nothing selected: the second tab of characters is empty and not shown")
        listed = dialog.right_rows["languages"]
        self.assertTrue(listed and all(r.language.kind == "language" for r in listed), "no character set here")
        within = [k for k, r in enumerate(listed) if r.level == "nearly"]
        first, second = within[0], within[-1]
        click(first)
        one = listed[first]
        self.assertEqual((dialog.selection.results, dialog.selection.kind), ([one], "language"))
        self.assertEqual(dialog.left_tab, "own", "selecting switches to the selection's own tab")
        needed = set(fc.needs(one))
        self.assertTrue(dialog.own_rows and all(needed & set(row.items) for row in dialog.own_rows),
                        "its missing characters, and nothing else")
        self.assertEqual([row.key() for row in dialog.rows], rows, "the high-value list is left as it was")
        self.assertEqual(state["cleared"], 0, "a first click selects")
        click(second)
        other = listed[second]
        self.assertEqual(dialog.selection.results, [other], "another language: in place of the first")
        self.assertTrue(all(set(fc.needs(other)) & set(row.items) for row in dialog.own_rows))
        self.assertEqual(state["cleared"], 0)
        click(second)
        self.assertEqual(state["cleared"], 1, "a second click on the selected language unselects it")
        self.assertEqual((dialog.selection, dialog.left_tab, dialog.own_rows), (None, "value", []),
                         "unselecting grays the second tab again and returns to the first")
        click(second)
        self.assertEqual(dialog.selection.results, [other], "and a third selects it again")
        click(None)
        self.assertEqual((state["cleared"], dialog.selection, dialog.left_tab), (2, None, "value"),
                         "a click on the empty part clears the selection")
        self.assertEqual([row.key() for row in dialog.rows], rows)
        dialog.list_pressed(dialog.add_tree, None)
        self.assertEqual(state["add cleared"], 1, "in the list of characters too")
        dialog.list_pressed(dialog.add_tree, object())
        self.assertEqual(state["add cleared"], 1, "a press on a row leaves the selection to Qt")
        dialog.selected_entry = lambda tab: 1 / 0
        dialog.right_clicked("languages")  # (a signal's handler: it must not raise)
        dialog.right_double_clicked("languages", Row(first))

    def recorded_items(self, dialog):
        """The rows the dialog makes from now on, each remembering what it was told."""
        made = []

        class Item(object):
            def __init__(self, texts, data):
                self.texts, self.value, self.calls, self.children = list(texts), data, [], []

            def data(self, column, role):
                return self.value

            def addChild(self, child):
                self.children.append(child)

            def last(self, name):
                found = [args for called, args in self.calls if called == name]
                return found[-1] if found else None

            def __getattr__(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return lambda *args: self.calls.append((name, args))

        def item(texts, data, tip=u"", names=False):
            made.append(Item(texts, data))
            # (a row of a right tab hands its tooltip over as something to call: made when Qt asks for it)
            made[-1].lazy = callable(tip)
            made[-1].tip = dialog.tip(tip() if callable(tip) else tip, names)
            return made[-1]

        dialog.item = item
        return made

    def test_headings_collapse(self):
        """The owner: "Family headers should be collapsible to easily reach another family." A click or
        a double-click on a heading closes or opens it; the state is kept by the heading's script."""
        dialog, state, click, Row = self.linked_lists()
        click(0)
        selected, name = dialog.selection.key, dialog.selection.name
        script = dialog.selection.results[0].language.script
        title = u"#%s" % script
        heading = click(title)
        self.assertEqual((heading.expanded, dialog.closed["languages"]), (False, set([script])), "a click closes it")
        self.assertEqual(heading.icons, 1, "its arrow drawn again")
        self.assertEqual((state["cleared"], dialog.selection.key), (0, selected), "and changes no selection")
        heading = click(title, None, True)
        self.assertEqual((heading.expanded, dialog.closed["languages"]), (None, set([script])),
                         "a double-click's second press does nothing more: closed once")
        made = self.recorded_items(dialog)
        for change in (lambda: dialog.fill_right(), lambda: setattr(dialog.sort_box, "currentIndex", 3),
                       lambda: setattr(dialog.search, "text", name[:3])):
            change()
            del made[:]
            dialog.languages_changed()
            headings = dict((one.value, one) for one in made if (u"%s" % one.value).startswith(u"#"))
            self.assertIn(title, headings)
            self.assertEqual(headings[title].last("setExpanded"), (False,), "kept through refills, orders, and searches")
            self.assertEqual(headings[title].children, [], "closed: its languages' rows are not made")
            self.assertTrue(dialog.unfilled["languages"][script], "they wait for it to be opened")
            self.assertTrue(headings[title].last("setChildIndicatorPolicy"), "and Qt may still open it by a key")
            self.assertEqual(dialog.selection.key, selected, "the language selected under it stays selected, without a row")
            for other, one in headings.items():
                if other == u"#" + fc.SCRIPTS_NOT_COVERED:
                    continue  # (the closing section: closed until asked for, or opened by a search that names a script)
                if other != title:
                    self.assertEqual(one.last("setExpanded"), (True,), other)
                    self.assertTrue(one.children, "%s is open: its rows are made" % other)
                self.assertTrue(one.last("setIcon"), "an arrow on %s" % other)
        dialog.search.text = u""
        dialog.languages_changed()
        waiting = len(dialog.unfilled["languages"][script])
        listed = len(dialog.right_rows["languages"])
        del made[:]
        heading = click(title)
        self.assertEqual((heading.expanded, dialog.closed["languages"]), (True, set()), "another click opens it")
        self.assertEqual((len(heading.children), len(made)), (waiting, waiting), "its rows made as it opens, under it")
        self.assertEqual(len(dialog.right_rows["languages"]), listed + waiting)
        self.assertEqual(list(dialog.unfilled["languages"]), [fc.SCRIPTS_NOT_COVERED],
                         "once (the closing section alone still waits, closed)")
        self.assertEqual(dialog.selection.key, selected, "the language under it is still selected")
        chosen = [one for one in made if one.last("setSelected") == (True,)]
        self.assertEqual([fc.language_key(dialog.right_rows["languages"][one.value]) for one in chosen], [selected],
                         "its new row marked selected (not made current: that would scroll to it)")
        self.assertFalse(dialog.filling, "the handlers held off only meanwhile")
        click(title)
        click(title)
        self.assertEqual(len(dialog.right_rows["languages"]), listed + waiting, "opened again: no row made twice")
        # What is selected under a closed heading has no row: a click on the empty part still unselects it
        click(title)
        dialog.fill_right()
        self.assertEqual(dialog.selection.key, selected)
        click(None)
        self.assertEqual((dialog.selection, dialog.left_tab), (None, "value"))
        click(title)
        # Qt closing or opening a heading itself (a key): what is held follows, once
        row = Row(title)
        dialog.right_expanded("languages", row, False)
        self.assertEqual((dialog.closed["languages"], row.icons), (set([script]), 1))
        dialog.right_expanded("languages", row, False)
        self.assertEqual(row.icons, 1, "already so: nothing more")
        dialog.right_expanded("languages", row, True)
        self.assertEqual(dialog.closed["languages"], set())
        dialog.right_expanded("languages", None, True)
        dialog.right_expanded("languages", Row(0), True)  # (a language's row: nothing, no error)

    def test_character_sets_tab(self):
        dialog, state, click, Row = self.linked_lists()
        dialog.show_absent.checked = False  # (the scripts the font has only: Lao is not listed)
        dialog.refill_coverage()
        rows = [row.key() for row in dialog.rows]
        self.assertNotIn(u"Lao", [r.language.name for r in dialog.right_rows["languages"]])
        self.assertTrue(dialog.set_results, "the character sets are read and checked with the languages")
        dialog.right_tab_changed(1)
        self.assertEqual(dialog.right_tab, "sets")
        listed = dialog.right_rows["sets"]
        self.assertEqual(len(listed), len(dialog.set_results))
        self.assertTrue(all(r.language.kind == "set" for r in listed), "the character sets alone")
        click([k for k, r in enumerate(listed) if r.language.iso == u"unicode-math"][0])
        math = dialog.selection
        self.assertEqual((math.kind, dialog.left_tab), ("set", "own"))
        own = [item for row in dialog.own_rows for item in row.items]
        self.assertTrue(0 < len(own) <= fc.FLOAT_MOST, "the first of the thousands it misses")
        self.assertTrue(set(own) <= set(math.results[0].missing))
        self.assertEqual([row.key() for row in dialog.rows], rows)
        self.assertLessEqual(len(fc.code_points(dialog.glyph_window_text())), fc.FLOAT_MOST)
        dialog.checked = set(own[:2])
        dialog.update_gain()  # (a set is no language gained: nothing raises)
        dialog.update_buttons()
        # Listed again (a search that keeps it): still selected, found again by what it is
        dialog.search.text = u"math"
        dialog.fill_right()
        self.assertTrue(dialog.right_rows["sets"] and len(dialog.right_rows["sets"]) < len(listed))
        self.assertEqual((dialog.selection.key, dialog.left_tab), (math.key, "own"))
        # Another tab does not list it: unselected, the first tab of characters shown again
        dialog.search.text = u"lao"
        dialog.right_tab_changed(0)
        found = [r.language.name for r in dialog.right_rows["languages"]]
        self.assertIn(u"Lao", found, "a search finds a language of a script not listed")
        self.assertEqual((dialog.selection, dialog.left_tab, dialog.own_rows), (None, "value", []))
        self.assertEqual([row.key() for row in dialog.rows], rows)
        click(found.index(u"Lao"))
        self.assertEqual(dialog.selection.name, u"Lao")
        self.assertTrue(dialog.own_rows, "a language of a script the font lacks: its characters listed")
        dialog.right_tab_changed(7)  # (no such tab: nothing, no error)
        self.assertEqual(dialog.right_tab, "languages")

    def test_families_tab(self):
        """The owner: "A nice third tab ... would be 'Families' with a tree that uses the same colors to
        display support per linguistic families"."""
        dialog, state, click, Row = self.linked_lists()
        self.assertIsNotNone(dialog.families, "Glottolog's file is read with the languages")
        listed = dialog.right_rows["languages"]
        english = [k for k, r in enumerate(listed) if r.language.iso == u"eng"][0]
        click(english)
        key = dialog.selection.key
        made = self.recorded_items(dialog)
        dialog.right_tab_changed(2)
        self.assertEqual(dialog.right_tab, "families")
        rows = dialog.right_rows["families"]
        nodes = [one for one in rows if isinstance(one, fc.FamilyNode)]
        languages = [one for one in rows if not isinstance(one, fc.FamilyNode)]
        tops = [node for node in nodes if len(node.path) == 1]
        self.assertEqual(sum(len(node.all_results()) for node in tops), len(listed),
                         "every language once, under its family")
        self.assertTrue(0 < len(languages) < len(listed) // 4,
                        "rows only for the languages of the families opened: the closed ones' are made later")
        self.assertEqual(len(made), len(rows))
        self.assertEqual((dialog.selection.key, dialog.left_tab), (key, "own"), "the selected language goes with the tab")
        above = [node.path for node in nodes if any(r.language.iso == u"eng" for r in node.all_results())]
        self.assertTrue(above and set(above) <= dialog.opened, "its family and branches opened to show it")
        indo = [node for node in nodes if node.path == (u"Indo-European",)][0]
        item = [one for one in made if one.value == rows.index(indo)][0]
        self.assertEqual(item.texts[0], u"Indo-European (%d)" % len(indo.all_results()))
        self.assertEqual(item.texts[2], fc.coverage_text(fc.level_counts(indo.all_results())), "counted as a script is")
        self.assertEqual(item.last("setExpanded"), (True,))
        self.assertEqual(len([args for name, args in item.calls if name == "setIcon"]), 2, "its arrow and its bar")
        self.assertTrue(item.children, "its branches and languages are rows under it")
        closed = [node for node in nodes if len(node.path) == 1 and node.path not in dialog.opened][0]
        item = [one for one in made if one.value == rows.index(closed)][0]
        self.assertEqual(item.last("setExpanded"), (False,), "the other families closed to start with")
        self.assertEqual((item.children, dialog.unfilled["families"][closed.path]), ([], closed),
                         "and without rows under them until they are opened")

        class At(object):  # (where the mouse is in the row)
            def __init__(self, x):
                self.at = x

            def x(self):
                return self.at

        # A press on a family's arrow opens it and selects nothing; kept by its place through a refill
        before = len(rows)
        row = click(rows.index(closed), At(5))
        self.assertEqual((row.expanded, closed.path in dialog.opened, dialog.selection.key), (True, True, key))
        self.assertEqual(len(row.children), len(closed.children) + len(closed.results), "its rows made as it opens")
        self.assertGreater(len(rows), before)
        self.assertNotIn(closed.path, dialog.unfilled["families"])
        dialog.fill_right()
        rows = dialog.right_rows["families"]
        again = [one for one in rows if isinstance(one, fc.FamilyNode) and one.path == closed.path][0]
        self.assertIsNot(again, closed, "the tree is made anew")
        self.assertTrue(dialog.family_open(again), "found again by its place, never by a kept row")
        row = click(rows.index(again), At(5))
        self.assertEqual((row.expanded, again.path in dialog.opened), (False, False), "another press closes it")
        # A click on its name selects the family: what its languages miss, in the selection's tab
        row = click(rows.index(again), At(200))
        self.assertEqual((dialog.selection.kind, dialog.selection.name, dialog.left_tab), ("family", again.name, "own"))
        self.assertEqual(row.expanded, None, "a click on its name leaves it closed")
        wanted = dialog.selection.wanted()
        self.assertEqual(set(item for row_ in dialog.own_rows for item in row_.items) <= set(wanted), True)
        self.assertEqual(bool(dialog.own_rows), bool(wanted))
        row = click(rows.index(again), At(200), True)
        self.assertEqual((row.expanded, dialog.selection.kind), (True, "family"), "a double-click on its name opens it")
        dialog.fill_right()
        self.assertEqual(dialog.selection.kind, "family", "still selected after a refill, found by its place")
        # A search opens every family it lists, and finds a family by its name
        dialog.search.text = u"germanic"
        del made[:]
        dialog.fill_right()
        rows = dialog.right_rows["families"]
        found = [one for one in rows if not isinstance(one, fc.FamilyNode)]
        self.assertTrue([r for r in found if r.language.iso == u"deu"], "German, by its family's name")
        self.assertTrue(all(u"Germanic" in dialog.families.path(r.language.iso) or fc.language_matches(r, u"germanic")
                            for r in found))
        self.assertTrue(all(one.last("setExpanded") == (True,) for one in made if isinstance(rows[one.value], fc.FamilyNode)))
        top = [one for one in rows if isinstance(one, fc.FamilyNode)][0]
        row = click(rows.index(top), At(5))
        self.assertEqual((row.expanded, top.path in dialog.closed["families"]), (False, True), "closed by hand meanwhile")
        dialog.search.text = u""
        dialog.right_tab_changed(1)
        self.assertEqual((dialog.selection, dialog.left_tab), (None, "value"), "a family is no character set")

    def test_defaults_and_captions(self):
        """The owner: one check box whose caption is the sentence with the count, ticked by default;
        the Languages choice starts with Every language; the high-value tab is named with its count."""
        gui = sys.modules["PythonQt"].QtGui
        saved = dict(gui.classes)
        for name in ("QCheckBox", "QComboBox", "QTabBar"):
            gui.classes[name] = Recorded
        try:
            dialog = self.dialog()
        finally:
            gui.classes.clear()
            gui.classes.update(saved)
        self.assertEqual(dialog.show_absent.checked, True, "ticked to start with")
        self.assertEqual(dialog.show_absent.made, (u"Show the scripts whose glyphs are fully missing from the font.",),
                         "no count shown as a zero before the first check")
        self.assertEqual(fc.STATUS_FILTERS[dialog.status_filter.currentIndex][1], u"Every language")
        self.assertEqual(fc.STATUS_START, "all")
        self.assertEqual(dialog.left_tabs.told("addTab"),
                         [(u"High-value missing glyphs",), (u"Select language, character set, or family",)])
        for words in (u"language", u"character set", u"script", u"family"):  # (its help and tooltip say the same)
            self.assertIn(words, dialog.left_tabs.told("setWhatsThis")[0][0])
            self.assertIn(words, dialog.left_tabs.told("setTabToolTip")[1][1])
        self.assertIn(u"<i>Select language, character set, or family</i>", dialog.left_tabs.told("setWhatsThis")[0][0])
        self.assertIn(u"<i>Select language, character set, or family</i>", fc.HELP)
        self.assertEqual(dialog.left_tabs.told("setTabEnabled"), [(1, False)], "grayed until something is selected")
        self.assertEqual(dialog.right_tabs.told("addTab"), [(u"Languages",), (u"Character sets",), (u"Families",)])
        dialog.nearly.value = 30
        dialog.check_coverage()
        every = len(fc.load_languages())  # (Hyperglot's, and those of the other sources beside it)
        self.assertGreater(every, len(fc.load_languages(LANGUAGES_FILE)))
        self.assertEqual(sum(len(s.results) for s in dialog.scripts), every, "every language, historical ones too")
        self.assertEqual(dialog.inferred_box.checked, True, "the languages from texts and keyboards counted to start with")
        self.assertEqual(dialog.inferred_box.made, (u"Languages from texts and keyboards",))
        said = dialog.inferred_box.told("setWhatsThis")[-1][0]
        for words in (u"<i>inferred</i>", u"<i>keyboard</i>", u"keyboard layout of Language Tools", u"a second script"):
            self.assertIn(words, said)
        absent = len([s for s in dialog.scripts if not s.present])
        self.assertGreater(absent, 1)
        self.assertEqual(dialog.show_absent.text, u"Show the %d scripts whose glyphs are fully missing from the font." % absent)
        self.assertEqual(len(dialog.shown_scripts()), len(dialog.scripts), "and they are listed")
        self.assertEqual(dialog.left_tabs.told("setTabText")[-2:],
                         [(0, u"High-value missing glyphs (%d)" % len(dialog.rows)),
                          (1, u"Select language, character set, or family")])
        captions = dict(dialog.right_tabs.told("setTabText")[-3:])
        self.assertEqual(captions[0], u"Languages (%d)" % every)
        self.assertEqual(captions[1], u"Character sets (%d)" % len(dialog.set_results))
        self.assertTrue(captions[2].startswith(u"Families ("))
        one = [r for r in dialog.results if r.level == "nearly"][0]
        dialog.select(fc.selection_of(one))
        self.assertEqual(dialog.left_tabs.told("setTabText")[-1], (1, u"%s (%d)" % (one.language.name, len(fc.needs(one)))))
        self.assertEqual(dialog.left_tabs.told("setTabEnabled")[-1], (1, True))
        self.assertEqual(dialog.left_tabs.told("setCurrentIndex")[-1], (1,))
        dialog.select(None)
        self.assertEqual(dialog.left_tabs.told("setTabEnabled")[-1], (1, False))
        self.assertEqual(dialog.left_tabs.told("setCurrentIndex")[-1], (0,))

    def test_says_glyph(self):
        """The owner: "use the more technical terminology, which would be 'glyph' wherever relevant": what
        the font has or would get is a glyph; a character set and an orthography's base characters stay."""
        gui = sys.modules["PythonQt"].QtGui
        saved = dict(gui.classes)
        for name in ("QPushButton", "QSpinBox", "QTreeWidget"):
            gui.classes[name] = Recorded
        try:
            dialog = self.dialog()
        finally:
            gui.classes.clear()
            gui.classes.update(saved)
        self.assertEqual(dialog.copy_chars_button.made, (u"Copy glyphs",))
        self.assertEqual(dialog.nearly.told("setSuffix"), [(" glyphs",)])
        for tree in (dialog.add_tree, dialog.own_tree):
            self.assertEqual(tree.told("setHeaderLabels"), [(["", "Glyph", "", "Languages"],)])
        self.assertEqual(dialog.set_tree.told("setHeaderLabels"), [(["Character set", "Missing"],)])
        self.assertEqual(fc.RIGHT_TABS[1][1], u"Character sets")
        self.assertEqual(fc.value_title(3), u"High-value missing glyphs (3)")
        self.assertEqual(fc.gain_text(1, []), u"With 1 glyph checked: no language is complete yet")
        f = font([0x61])
        tip = fc.coverage_tip(fc.check_language(language(u"a b", u"c"), f))
        self.assertIn(u"Base characters missing: b", tip, "the orthography's own terms are kept")
        self.assertIn(u"Auxiliary characters missing (loan words, names): c", tip)
        for text in (fc.HELP, dialog.glyph_window_tip()):
            self.assertNotIn(u"checked character", text)
            self.assertNotIn(u"characters to add", text)

    def test_opens_wider(self):
        """The owner: "Default width for the font check panel appears to be too narrow for two lists":
        it opens 1,400 pixels wide, or what the screen allows, at the height the shared size gave it."""
        gui = sys.modules["PythonQt"].QtGui
        saved = dict(gui.classes)
        gui.classes["QSplitter"] = Recorded
        try:
            dialog = self.dialog()
        finally:
            gui.classes.clear()
            gui.classes.update(saved)

        class Window(object):
            def __init__(self, width, height):
                self.width, self.height, self.sizes = width, height, []

            def resize(self, width, height):
                self.sizes.append((width, height))

        for screen, size, wanted in ((1920, (1000, 1000), [(1400, 1000)]), (1280, (1000, 900), [(1240, 900)]),
                                     (None, (1000, 1000), [(1400, 1000)]), (1040, (1000, 1000), []),
                                     (1920, (1600, 1000), []), (1920, (1000, 0), [])):
            dialog.screen_width = lambda window, screen=screen: screen
            window = Window(*size)
            dialog.widen(window)
            self.assertEqual(window.sizes, wanted, "screen %s, opened at %s" % (screen, size))
        dialog.screen_width = lambda window: 1 / 0
        window = Window(1000, 1000)
        dialog.widen(window)  # (never raises, and leaves the shared size)
        self.assertEqual(window.sizes, [])
        del dialog.screen_width
        self.assertIsNone(dialog.screen_width(dialog.dialog), "a screen that cannot be read")
        self.assertEqual(dialog.coverage_halves.told("setSizes"), [(list(fc.split_sizes(fc.WIDE)),)],
                         "the two lists' widths to start with")

    def test_columns_degrade(self):
        """At 1000 pixels the families' counts were cut ("95 of 177 la..."): the last column of each list
        at the right is as wide as its contents, the names take the rest, and the bar gives way first."""
        calls, original = [], fc.FontCheckDialog.size_columns
        fc.FontCheckDialog.size_columns = lambda self, tree, modes: calls.append((tree, modes))
        try:
            dialog = self.dialog()
        finally:
            fc.FontCheckDialog.size_columns = original
        self.assertEqual([modes for _, modes in calls],
                         [("stretch", "contents"), ("stretch", "contents"), ("stretch", "fixed", "contents", "contents")])
        self.assertTrue(all(tree is wanted for (tree, _), wanted in
                            zip(calls, (dialog.language_tree, dialog.set_tree, dialog.family_tree))))

        class Modes(object):
            Stretch, ResizeToContents, Fixed = "Stretch", "ResizeToContents", "Fixed"

        class Tree(object):
            def __init__(self, room=600, names=300, counts=250):
                self.head, self.room, self.names, self.counts, self.widths = Recorded(), room, names, counts, []

            def header(self):
                return self.head

            def viewport(self):
                view = Anything()
                view.width = self.room
                return view

            def sizeHintForColumn(self, column):
                return self.names

            def columnWidth(self, column):
                return self.counts

            def setColumnWidth(self, column, width):
                self.widths.append((column, width))

        gui = sys.modules["PythonQt"].QtGui
        saved = dict(gui.classes)
        gui.classes["QHeaderView"] = Modes
        try:
            tree = Tree()
            dialog.size_columns(tree, ("stretch", "fixed", "contents"))
        finally:
            gui.classes.clear()
            gui.classes.update(saved)
        self.assertEqual(tree.head.told("setStretchLastSection"), [(False,)], "Qt's own stretch gave the last column the rest")
        self.assertEqual(tree.head.told("setSectionResizeMode"), [(0, "Stretch"), (1, "Fixed"), (2, "ResizeToContents")])
        dialog.size_columns(object(), ("stretch",))  # (a list without a header: nothing, no error)
        dialog.fit_bar(tree, fc.FAMILY_NAMES_MOST)
        self.assertEqual(tree.widths, [(1, 50)], "a narrow list: the bar's column gets what the names and counts leave")
        wide = Tree(room=1000, names=900)
        dialog.fit_bar(wide, 400)
        self.assertEqual(wide.widths, [(1, fc.BAR_COLUMN)], "the bar whole once the names (400 of them at most) fit")
        dialog.fit_bar(object(), 400)  # (never raises)
        dialog.redraws = {"bars": True}
        dialog.redraw_now()  # (the list resized: its bars fitted again)
        self.assertEqual(dialog.redraws, {})

    def test_inferred_languages(self):
        """The languages whose characters are inferred from a text, or read from a keyboard layout, are
        counted to start with, and left out by their one check box; a search still finds them, under a
        heading that says why; the top line counts them."""
        dialog = self.dialog()
        dialog.nearly.value, dialog.show_absent.checked, dialog.inferred_box.checked = 30, True, True
        dialog.status_filter.currentIndex = [key for key, _, _ in fc.STATUS_FILTERS].index("all")
        dialog.check_coverage()
        every = sum(len(s.results) for s in dialog.scripts)
        inferred = [r for r in dialog.results if r.language.evidence == fc.INFERRED]
        typed = [r for r in dialog.results if r.language.evidence == fc.KEYBOARD]
        self.assertGreater(len(inferred), 600)
        self.assertEqual(len(typed), 37, "Gondi in Telugu's layout refused as unfinished, Sylheti's not read, "
                                         "Manipuri's and Laz's set aside for a declared source's")
        self.assertEqual((every, dialog.other_results), (len(fc.load_languages()), []))
        self.assertTrue([r for r in typed if r.language.iso == u"kmr" and r.language.script == u"Yezidi"],
                        "a second script beside Hyperglot's row")
        self.assertTrue([r for r in dialog.results if r.language.iso == u"jav" and r.language.script == u"Javanese"
                         and r.language.evidence == fc.DECLARED], "and a declared source's second script")
        dialog.inferred_box.checked = False
        dialog.coverage.status = Recorded()
        dialog.status_changed()  # (its toggled signal)
        self.assertEqual(sum(len(s.results) for s in dialog.scripts), every - len(inferred) - len(typed))
        self.assertTrue(all(r.language.evidence == fc.DECLARED for r in dialog.results))
        self.assertEqual(len(dialog.other_results), len(inferred) + len(typed), "set aside for a search")
        line = re.sub(u"<[^>]*>", u"", dialog.coverage.status.text)
        self.assertIn(u"%d languages from texts and keyboards are left out." % (len(inferred) + len(typed)), line)
        name = dialog.other_results[0].language.name
        dialog.search.text = name
        dialog.fill_right()
        found = [r for r in dialog.right_rows["languages"] if r.language.name == name]
        self.assertTrue(found and found[0].language.evidence == fc.INFERRED, "a search finds it all the same")
        shown = [s.script for s in dialog.filtered_scripts()]
        sections, _ = fc.language_sections(dialog.scripts, shown, name, None, "reach", dialog.other_results)
        self.assertIn(u"Languages from texts and keyboards", [s.title for s in sections if s.why])
        sections, _ = fc.language_sections(dialog.scripts, shown, u"comanche", None, "reach", dialog.other_results)
        self.assertEqual([(s.title, [r.language.iso for r in s.results]) for s in sections if s.why],
                         [(u"Languages from texts and keyboards", [u"com"])], "and a layout's language too")

    def test_rows_made_only_where_they_show(self):
        """Some 2,500 languages: a closed family or script has no rows until it is opened, so filling
        the Families tab makes a row per family, not one per language."""
        dialog, state, click, Row = self.linked_lists()
        dialog.inferred_box.checked = True
        dialog.check_coverage()
        every = sum(len(s.results) for s in dialog.scripts)
        self.assertGreater(every, 2400)
        made = self.recorded_items(dialog)
        dialog.right_tab_changed(2)
        rows = dialog.right_rows["families"]
        self.assertTrue(all(isinstance(one, fc.FamilyNode) and len(one.path) == 1 for one in rows), "the families alone")
        self.assertEqual(len(made), len(rows))
        self.assertLess(len(made), 300, "against a row for each of the %d languages and each branch" % every)
        self.assertEqual(sum(len(one.all_results()) for one in rows), every, "which wait under their families")
        self.assertEqual(len(dialog.unfilled["families"]), len(rows))
        del made[:]
        dialog.right_tab_changed(0)
        headings = [one for one in made if (u"%s" % one.value).startswith(u"#")]
        self.assertEqual(len(made), every + len(headings), "the scripts are open to start with: a row per language")
        latin = len([r for r in dialog.results if r.language.script == u"Latin"])
        click(u"#Latin")
        del made[:]
        dialog.fill_right()
        self.assertEqual(len(made), every - latin + len(headings), "a closed script's rows are not made")
        click(u"#Latin")

    def test_tooltips_wrap_and_name_the_font(self):
        dialog = self.dialog()
        self.assertEqual(dialog.tip(u""), u"")
        self.assertEqual(dialog.tip(u"Short"), u"<span>Short.</span>", "a sentence, as rich text")
        long_text = u"Needed, with other glyphs, by: " + u", ".join([u"Language (with x)"] * 80)
        self.assertTrue(dialog.tip(long_text).startswith(u"<table width=\"%d\"" % fc.TIP_WIDTH), "a width for a long one")
        dialog.dialog.width = 400
        self.assertTrue(dialog.tip(long_text).startswith(u"<table width=\"%d\"" % (400 - fc.TIP_MARGIN)),
                        "no wider than a narrower window")
        dialog.list_family = u"FreeLang"
        self.assertIn(u"font-family:'FreeLang'", dialog.tip(u"Name", True), "names and characters in the bundled font")
        self.assertNotIn(u"font-family", dialog.tip(u"Name"))
        self.assertEqual(dialog.tip(u"<i>Diacritics</i> cannot build it.", rich=True),
                         u"<span><i>Diacritics</i> cannot build it.</span>")
        made = self.recorded_items(dialog)
        dialog.nearly.value, dialog.show_absent.checked = 30, True
        dialog.check_coverage()
        tips = [one.tip for one in made if one.tip]
        self.assertTrue(tips)
        self.assertTrue(all(tip.startswith(u"<table ") or tip.startswith(u"<span") for tip in tips), "every row's is rich text")
        self.assertTrue([tip for tip in tips if u"font-family:'FreeLang'" in tip])

    def test_loading_state(self):
        """The owner: "This stays empty for several seconds before it all loads, it should indicate
        loading in some way so the user understands it's not broken." In a window that is shown, the
        check goes in steps from a timer: the lists' area says which one runs, the controls are grayed,
        a second check does not start inside the first, and no count shows as a zero meanwhile."""
        dialog = self.dialog()
        dialog.busy_label, dialog.coverage_stack, dialog.coverage.status = Recorded(), Recorded(), Recorded()
        dialog.coverage_button, dialog.tabs = Recorded(), Recorded()
        dots = u(0x2026)
        dialog.show()
        self.assertTrue(dialog.stepwise, "a window shown: step by step from now on")
        self.assertEqual((dialog.busy, dialog.busy_label.text, dialog.coverage_stack.currentIndex),
                         (False, u"Reading the language data" + dots, 0), "it opens on that line, not on empty lists")
        waiting = []
        dialog.defer = waiting.append
        dialog.nearly.value, dialog.inferred_box.checked = 30, True
        dialog.check_coverage()
        self.assertEqual((dialog.busy, dialog.busy_label.text, dialog.coverage.status.text),
                         (True, u"Reading the language data" + dots, u"Reading the language data" + dots))
        self.assertEqual((dialog.coverage_stack.currentIndex, dialog.coverage_button.enabled, dialog.tabs.enabled),
                         (0, False, False), "the line in the lists' place, the controls grayed")
        self.assertEqual((len(waiting), dialog.scripts), (1, []), "nothing is done before the window is painted")
        dialog.check_coverage()
        dialog.status_changed()
        self.assertEqual(len(waiting), 1, "a check asked for meanwhile does not start inside the first")
        said = []
        while waiting:
            self.assertEqual(len(waiting), 1, "one step at a time")
            waiting.pop(0)()
            said.append(dialog.busy_label.text)
        self.assertEqual(said, [u"Reading the font" + dots, u"Checking 2,511 languages" + dots, u"Listing" + dots, u""])
        self.assertEqual((dialog.busy, dialog.coverage_stack.currentIndex, dialog.coverage_button.enabled,
                          dialog.tabs.enabled), (False, 1, True, True))
        self.assertTrue(dialog.scripts and dialog.rows)
        self.assertIn(u"covered and", dialog.coverage.status.text)
        self.assertEqual(fc.checking_text(1), u"Checking 1 language")
        self.assertEqual((fc.value_title(None), fc.value_title(0)), (u"High-value missing glyphs", u"High-value missing glyphs (0)"))
        self.assertEqual(fc.absent_caption(None), u"Show the scripts whose glyphs are fully missing from the font.")
        # A step that fails ends the work: the lists come back, and the log says why
        errors = []
        dialog.log.add = lambda text, level="info": errors.append((text, level))

        def refuse():
            raise RuntimeError("no glyphs")

        dialog.font_characters = refuse
        dialog.check_coverage()
        while waiting:
            waiting.pop(0)()
        self.assertEqual((dialog.busy, dialog.coverage_stack.currentIndex, errors), (False, 1, [(u"no glyphs", "error")]))
        # Without a font the lists are shown, empty, and nothing is said to be read
        dialog.read_font = lambda: False
        dialog.coverage_stack.setCurrentIndex(0)
        dialog.check_coverage()
        self.assertEqual((dialog.busy, dialog.coverage_stack.currentIndex, waiting), (False, 1, []))

    def test_data_kept_for_the_session(self):
        """FontLab runs the script anew at each opening: the files parsed are held on sys, as plain
        data, so the second window parses nothing; within one opening, the objects are made once."""
        self.assertIs(fc.session_cache(), fc._FILES)
        self.assertIs(sys._freelab_font_check_files, fc._FILES)
        first = fc.load_languages()
        self.assertIs(fc.load_languages(), first)
        self.assertIs(fc.load_families(), fc.load_families())
        fc.load_character_sets()
        self.assertTrue(fc._FILES)
        for path, (stamp, data) in fc._FILES.items():
            self.assertIsInstance(data, dict, "plain data only, never an object of the script's classes: %s" % path)

    def test_second_opening(self):
        """The script run a second time, as FontLab runs it at each opening (a fresh namespace, its
        classes defined anew): what the first opening read must not hand the second objects of the
        first one's classes. They failed every isinstance: Han was checked as a list of 103,351
        characters, the scripts' lines were gone, and a language that cannot be checked raised as it was
        selected."""
        import io
        path = os.path.join(os.path.dirname(os.path.abspath(fc.__file__)), "freelab_font_check.py")
        with io.open(path, "rb") as handle:
            source = handle.read()

        def opening():
            space = {"__file__": path, "__name__": "__main__"}
            exec(compile(source, path, "exec"), space)
            return space

        first = opening()
        first["load_character_sets"]()
        first["load_families"]().uncovered()
        first["load_languages"]()
        second = opening()
        self.assertIs(second["_FILES"], first["_FILES"], "the files are parsed once a session")
        sets = second["load_character_sets"]()
        scripts = [one for one in sets if type(one).__name__ == "ScriptSet"]
        self.assertTrue(scripts)
        self.assertTrue(all(isinstance(one, second["ScriptSet"]) for one in scripts), "the second opening's own class")
        han = [one for one in scripts if one.name == u"Han"][0]
        r = second["check_entry"](han, second["FontCharacters"](list(range(0x20, 0x7F)), None))
        self.assertIsInstance(r.missing, second["CodeItems"], "Han checked by its ranges, not as a list")
        self.assertTrue(second["language_note"](r).endswith(u"missing"))
        selection = second["selection_of"](r)
        self.assertEqual((selection.kind, selection.results), ("set", [r]))
        uncovered = second["load_families"]().uncovered()
        entry = next(iter(uncovered.values()))[0]
        self.assertIsInstance(entry, second["Uncovered"], "a language that cannot be checked: nothing to select")
        languages = second["load_languages"]()
        self.assertTrue(all(isinstance(one, second["Language"]) for one in languages))
        kept = second["load_known_scripts"]()
        self.assertIsInstance(kept, second["KnownScripts"])

    def test_not_yet_covered_rows(self):
        """The Families tab counts, beside each family's bar, the languages of it that cannot be
        checked, and lists them under a last node whose rows are made when it is opened; the Languages
        tab closes on the scripts not yet covered; the line under the list says how to add one."""
        dialog, state, click, Row = self.linked_lists()
        dialog.languages_note = Recorded()
        made = self.recorded_items(dialog)
        dialog.right_tab_changed(2)
        rows = dialog.right_rows["families"]
        family = [one for one in made if one.texts[0].startswith(u"Austronesian (")][0]
        self.assertEqual(family.texts[3], u"880 not yet covered")
        self.assertIn(u"880 more languages of it are known and cannot be checked yet", family.tip)
        self.assertGreater(len(rows), 230, "the families that have nothing but languages not yet covered are listed too")
        note = dialog.languages_note.text
        self.assertIn(u"Font Check can check 2,511 of the 7,861 languages Glottolog lists with an ISO 639-3 code, written "
                      u"in 111 of Unicode's 172 scripts.", note)
        self.assertIn(u"of the 5,036 languages not covered, 4,501 have a script on record", note)
        self.assertIn(u'<a href="%s">%s</a>' % (fc.ISSUES_ADDRESS, fc.ISSUES_ADDRESS), note, "a link, and the address as text")
        node = rows[family.value]
        dialog.toggle_family(node, Row(family.value))
        last = rows[-1]
        self.assertIsInstance(last, fc.UncoveredNode)
        self.assertEqual((made[-1].texts[0], len(last.entries)), (u"Not yet covered (880)", 880))
        self.assertFalse([one for one in rows if isinstance(one, fc.Uncovered)], "its rows wait until it is opened")
        self.assertIsNone(dialog.entry_selection(("node", last)), "nothing to check: nothing to select")
        self.assertIs(dialog.list_pressed(dialog.right_trees["families"], Row(len(rows) - 1)), True,
                      "a press anywhere on it opens it")
        entries = [one for one in rows if isinstance(one, fc.Uncovered)]
        self.assertEqual(len(entries), 880)
        self.assertIsNone(dialog.right_entry("families", Row(rows.index(entries[0]))), "a row to read")
        self.assertIn(u"known, not yet covered", made[-1].tip)
        dialog.search.text = u"amkoe"
        dialog.fill_right()
        found = [one for one in dialog.right_rows["families"] if isinstance(one, fc.Uncovered)]
        self.assertEqual([(one.iso, one.family) for one in found], [(u"huc", u"Kxa")], "a search finds it, under its family")
        self.assertIn(u"Glottolog also lists Amkoe (huc)", dialog.languages_note.text)
        self.assertIn(u"<a href=", dialog.languages_note.text)
        dialog.search.text = u""
        del made[:]
        dialog.right_tab_changed(0)
        heading = made[-1]
        self.assertEqual((heading.value, heading.texts[0]), (u"#Scripts not yet covered", u"Scripts not yet covered (61)"))
        self.assertIn(u"each is checked as a script", heading.tip)
        self.assertIn(u"As of November 2026, a script Unicode has not encoded", heading.tip)
        rows = dialog.right_rows["languages"]
        self.assertFalse([r for r in rows if isinstance(r.language, fc.ScriptSet)], "closed to start with")
        before = len(made)
        row = click(u"#Scripts not yet covered")
        # The owner: "see how these can be supported going forward": each is a live row, checked as a script
        scripts = [r for r in rows if isinstance(r.language, fc.ScriptSet)]
        self.assertEqual((len(scripts), len(made) - before), (61, 61))
        names = [r.language.name for r in scripts]
        for name in (u"Mongolian", u"Ol Onal", u"Sidetic", u"Tolong Siki", u"Tulu Tigalari", u"Garay", u"Beria Erfe"):
            self.assertIn(name, names)
        for name in (u"Kirat Rai", u"Tai Yo", u"Gurung Khema", u"Warang Citi"):
            self.assertNotIn(name, names, "a script a language here is written in is listed under its languages")
        mongolian = made[before + sorted(names).index(u"Mongolian")] if names == sorted(names) else \
            [one for one in made[before:] if one.texts[0] == u"Mongolian"][0]
        self.assertEqual(mongolian.texts, [u"Mongolian", u"167 of 167 missing"], "its coverage, as any set's")
        self.assertTrue(mongolian.lazy, "its tooltip is made when asked for")
        self.assertIn(u"Mongolian: missed (the font has 0 of its 167 characters", mongolian.tip)
        self.assertIn(u"No language data exists for it yet", mongolian.tip)
        self.assertIn(u"the script's whole repertoire is the measure", mongolian.tip)
        entry = dialog.right_entry("languages", Row(mongolian.value))
        self.assertEqual(entry[0], "row", "a row that selects like any other")
        dialog.select(dialog.entry_selection(entry))
        self.assertEqual((dialog.selection.kind, dialog.selection.name, dialog.left_tab), ("set", u"Mongolian", "own"))
        self.assertEqual(sum(len(one.items) for one in dialog.own_rows), 167, "its missing glyphs, handed to the left")
        dialog.right_tab_changed(1)  # (the same script under Scripts (Unicode), in the Character sets tab)
        self.assertEqual(dialog.selection.name, u"Mongolian", "the selection goes with the tab that lists it too")
        dialog.select(None)
        dialog.right_tab_changed(0)
        dialog.search.text = u"mongol"
        del made[:]
        dialog.fill_right()
        self.assertEqual([one.texts[0] for one in made if one.texts[0] == u"Mongolian"], [u"Mongolian"],
                         "a search finds a script not yet covered, and opens its section")
        self.assertEqual([r.language.name for r in dialog.right_rows["languages"] if isinstance(r.language, fc.ScriptSet)],
                         [u"Mongolian"])
        dialog.search.text = u""
        dialog.level_filter.currentIndex = [key for key, _ in fc.LANGUAGE_FILTERS].index("covered")
        dialog.fill_right()
        self.assertFalse([r for r in dialog.right_rows["languages"] if isinstance(r.language, fc.ScriptSet)],
                         "the level kept holds for the scripts too: the fake font covers none")
        dialog.level_filter.currentIndex = 0
        # Without the scripts' sets (a data file made before), the scripts are rows to read, as before
        dialog.set_results = [r for r in dialog.set_results if not isinstance(r.language, fc.ScriptSet)]
        dialog.scripts_open = True
        del made[:]
        dialog.fill_right()
        plain = [one for one in made if (u"%s" % one.value).startswith(u"script:")]
        self.assertEqual(len(plain), 61)
        self.assertIsNone(dialog.right_entry("languages", Row(u"script:Mongolian")))

    def test_a_set_of_your_own(self):
        """Characters pasted in the Character sets tab are checked as a set, selected (its missing
        glyphs at the left), saved under a name in the settings folder, and removed again."""
        import shutil
        import tempfile
        dialog = self.dialog()
        dialog.nearly.value = 30
        dialog.check_coverage()
        listed = len(dialog.set_results)
        dialog.custom_row = Recorded()
        dialog.right_tab_changed(1)
        self.assertEqual(dialog.custom_row.visible, True, "the field is shown with the Character sets tab")
        dialog.paste_field.text = u"ab " + u(0x14B) + u(0x14B)
        dialog.pasted_changed()
        first = dialog.set_results[0]
        self.assertEqual((first.language.name, first.language.script, first.language.base),
                         (u"Pasted characters", fc.CUSTOM_GROUP, [u"a", u"b", u(0x14B)]))
        self.assertEqual(len(dialog.set_results), listed + 1)
        self.assertEqual(dialog.selection.key, fc.language_key(first), "selected: what it misses is listed at the left")
        self.assertIn(u(0x14B), [item for row in dialog.own_rows for item in row.items])
        folder = tempfile.mkdtemp(prefix="freelab-sets-")
        self.addCleanup(lambda: shutil.rmtree(folder, True))
        dialog.custom_path = lambda: os.path.join(folder, "sets.json")
        dialog.save_set()
        self.assertEqual(fc.load_custom_sets(dialog.custom_path()), [], "no name: nothing saved")
        dialog.name_field.text = u"Mine"
        dialog.save_set()
        self.assertEqual(fc.load_custom_sets(dialog.custom_path()), [(u"Mine", u"ab " + u(0x14B) + u(0x14B))])
        self.assertEqual([r.language.name for r in dialog.set_results[:2]], [u"Pasted characters", u"Mine"])
        self.assertEqual((dialog.selected_custom(), len(dialog.set_results)), (u"Mine", listed + 2))
        dialog.remove_set()
        self.assertEqual((fc.load_custom_sets(dialog.custom_path()), len(dialog.set_results)), ([], listed + 1))
        dialog.paste_field.text = u""
        dialog.pasted_changed()
        self.assertEqual(len(dialog.set_results), listed, "the field emptied: no set of its own")
        dialog.remove_set()  # (none selected: nothing, no error)

    def test_own_tab_follows_edits(self):
        """The pasted set edited, or a selected saved set saved again, keeps its key while what it
        misses changes: the selection's own tab follows (it stayed as it was)."""
        import shutil
        import tempfile
        dialog = self.dialog()
        dialog.nearly.value = 30
        dialog.check_coverage()
        dialog.custom_row = Recorded()
        dialog.right_tab_changed(1)
        own = lambda: set(item.lower() for row in dialog.own_rows for item in row.items)  # (a capital comes along)
        dialog.paste_field.text = u(0x14B)
        dialog.pasted_changed()
        self.assertEqual(own(), set([u(0x14B)]))
        dialog.paste_field.text = u(0x272)
        dialog.pasted_changed()
        self.assertEqual((own(), dialog.left_tab), (set([u(0x272)]), "own"), "the text edited: its tab lists the new one")
        folder = tempfile.mkdtemp(prefix="freelab-sets-")
        self.addCleanup(lambda: shutil.rmtree(folder, True))
        dialog.custom_path = lambda: os.path.join(folder, "sets.json")
        dialog.name_field.text = u"Mine"
        dialog.save_set()
        self.assertEqual((dialog.selected_custom(), own()), (u"Mine", set([u(0x272)])))
        dialog.paste_field.text = u(0x14B)
        dialog.pasted_changed()
        mine = [r for r in dialog.set_results if r.language.name == u"Mine"][0]
        dialog.select(fc.selection_of(mine))
        self.assertEqual(own(), set([u(0x272)]))
        dialog.save_set()  # (the field's text saved under the selected set's name)
        self.assertEqual((dialog.selected_custom(), own()), (u"Mine", set([u(0x14B)])), "saved again: its tab follows")
        listed = dialog.own_rows
        dialog.select(fc.selection_of([r for r in dialog.set_results if r.language.name == u"Mine"][0]))
        self.assertIs(dialog.own_rows, listed, "the same selection again: nothing made anew")

    def test_two_orthographies_of_one_name(self):
        """Hyperglot gives Bassari two orthographies of one name and script (oniyan and oneyan): each
        is selected, and found again as the list is filled anew, as itself."""
        dialog, state, click, Row = self.linked_lists()
        listed = dialog.right_rows["languages"]
        bassari = [k for k, r in enumerate(listed) if r.language.iso == u"bsc"]
        self.assertEqual(sorted(listed[k].language.autonym for k in bassari), [u"oneyan", u"oniyan"])
        self.assertNotEqual(fc.language_key(listed[bassari[0]]), fc.language_key(listed[bassari[1]]))
        for k in reversed(bassari):
            click(k)
            autonym = listed[k].language.autonym
            self.assertEqual(dialog.selection.results[0].language.autonym, autonym)
            dialog.fill_right()
            self.assertEqual(dialog.selection.results[0].language.autonym, autonym, "found again as itself")
            self.assertEqual(dialog.selection.results[0].missing, listed[k].missing)
            listed = dialog.right_rows["languages"]
            bassari = [one for one in range(len(listed)) if listed[one].language.iso == u"bsc"]

    def test_buildable_asked_again_after_a_check(self):
        """A new check (an undo's) forgets what Diacritics was asked; the selection kept through it is
        asked about again, so its rows still say Diacritics can build them."""
        dialog, state, click, Row = self.linked_lists()
        asked = []

        def plan(results):
            asked.append([fc.language_key(r) for r in results])
            return set(item for r in results for item in fc.needs(r)[:1])

        dialog.diacritics_plan = plan
        listed = dialog.right_rows["languages"]
        started = [k for k, r in enumerate(listed) if r.level in ("started", "missed") and fc.needs(r)][0]
        click(started)
        key, first = dialog.selection.key, fc.needs(listed[started])[0]
        self.assertIn(first, dialog.buildable)
        del asked[:]
        dialog.check_coverage()
        self.assertEqual(dialog.selection.key, key, "kept through the check")
        self.assertIn([key], asked, "asked again about the selection")
        self.assertIn(first, dialog.buildable)
        self.assertIn(key, dialog.asked)
        dialog.fill_right()
        self.assertEqual(sum(1 for one in asked if one == [key]), 1, "once per check")

    def test_diacritics_font_made_once_per_check(self):
        """Diacritics' Font of every glyph is made once per check, not at each selection."""
        dialog = self.dialog()
        dialog.check_coverage()
        made = []

        class Recipe(object):
            def __init__(self, char):
                self.char, self.missing = char, None

        class Diacritics(object):
            SETS = [(u"Every", u"", [(0, 0x110000)])]

            class Font(object):
                def __init__(self, names, unicodes):
                    made.append(list(names))

            @staticmethod
            def plan(font, characters):
                return [Recipe(c) for c in characters]

        dialog.diacritics = Diacritics()
        results = [fc.check_language(language(u(0xE9) + u" " + u(0x1E17)), fc.FontCharacters([], None))]
        self.assertEqual(dialog.diacritics_plan(results), set([u(0xE9), u(0x1E17)]))
        dialog.diacritics_plan(results)
        self.assertEqual(len(made), 1, "once")
        self.assertIn(u"acutecomb", made[0], "of every glyph of the font")
        dialog.check_coverage()
        dialog.diacritics_plan(results)
        dialog.diacritics_plan(results)
        self.assertEqual(len(made), 2, "made anew by a check (the glyphs may have changed), once")

    def test_scripts_not_covered_toggles_as_shown(self):
        """During a search the closing section, Scripts not yet covered, is shown open: a first click
        closes it (it acted on the state held apart, closed, and seemed to do nothing)."""
        dialog, state, click, Row = self.linked_lists()
        made = self.recorded_items(dialog)
        title = u"#" + fc.SCRIPTS_NOT_COVERED

        def heading():
            return [one for one in made if one.value == title][-1]

        dialog.search.text = u"glagolitic"
        dialog.languages_changed()
        self.assertEqual(heading().last("setExpanded"), (True,), "a search opens it")
        row = click(title)
        self.assertEqual(row.expanded, False, "a first click closes it")
        del made[:]
        dialog.languages_changed()
        self.assertEqual(heading().last("setExpanded"), (False,), "closed by hand: kept while the search runs")
        row = click(title)
        self.assertEqual(row.expanded, True)
        click(title)
        dialog.search.text = u""
        del made[:]
        dialog.languages_changed()
        self.assertEqual(heading().last("setExpanded"), (False,), "no search: closed until asked for")
        row = click(title)
        self.assertEqual(row.expanded, True, "and opened by a click")
        dialog.search.text = u"glagolitic"
        del made[:]
        dialog.languages_changed()
        self.assertEqual(heading().last("setExpanded"), (True,), "a new search opens it again")

    def test_single_master_label(self):
        dialog = self.dialog()
        dialog.measured_label = Recorded()
        dialog.read_font()
        self.assertEqual(dialog.measured_label.text, u"Every glyph measured in every master.")
        dialog.package.masters = [u"Regular"]
        dialog.read_font()
        self.assertEqual(dialog.measured_label.text, u"Every glyph measured in the single master.")

    def test_metrics(self):
        dialog = self.dialog()
        dialog.mode_share.checked, dialog.share.value = True, 120
        self.assertEqual(dialog.mode(), "share")
        dialog.check_vertical()
        clipped = [f for f in dialog.metrics.findings if isinstance(f, fc.MetricFinding) and f.kind == "clip-top"]
        self.assertEqual([(f.glyphs[0][1], f.value) for f in clipped], [(u"Agrave", 100), (u"Agrave", 100)])
        self.assertTrue(dialog.suggestions)
        self.assertEqual([(c.extent.name, c.above) for c in dialog.clipped], [(u"Agrave", 100)], "once, its worst master")
        self.assertTrue(any(line.state == "ok" for line in dialog.check_rows), "passed checks listed too")
        dialog.draw_diagram()
        dialog.mode_share.checked = False
        dialog.mode_changed()
        self.assertEqual(dialog.mode(), "keep")

    def test_masters(self):
        dialog = self.dialog()
        dialog.reference.currentText, dialog.reference.currentIndex = u"Regular", 0
        for _, _, chip in dialog.chips:
            chip.checked = True
        dialog.check_masters()
        found = sorted((f.glyph, f.master, f.kind, f.fixable) for f in dialog.masters.findings)
        self.assertEqual(found, [(u"Hacute", u"Bold", "components", True), (u"i", u"Bold", "order", True),
                                 (u"o", u"Bold", "direction", True), (u"x", u"Bold", "nodes", False)],
                         "eacute, in Regular only, does not vary")
        self.assertEqual(dialog.glyph_names, [u"i", u"x", u"Hacute", u"o"])
        self.assertEqual(dialog.fixable_names, set([u"i", u"Hacute", u"o"]))
        dialog.draw_comparison()
        dialog.update_buttons()

    def test_fix(self):
        dialog = self.dialog()
        dialog.reference.currentText, dialog.reference.currentIndex = u"Regular", 0
        for _, _, chip in dialog.chips:
            chip.checked = True
        dialog.check_masters()
        package = dialog.package
        regular = [(c.items, c.closed) for g in package.by_name.values() for layer in [g.getLayerByName(u"Regular")]
                   if layer is not None for s in layer.shapes for c in s.contours]
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.fix_glyphs([u"o", u"i", u"Hacute", u"x"])
        self.assertEqual([level for level, _ in logged if level in ("error", "warning")], [], logged)
        found = sorted((f.glyph, f.master, f.kind) for f in dialog.masters.findings)
        self.assertEqual(found, [(u"x", u"Bold", "nodes")], "what needs the designer only")
        self.assertEqual([c.points for c in package.findName(u"o").getLayerByName(u"Bold").shapes[0].contours],
                         [square(500)], "reversed, its start where Regular's is")
        bold_i = package.findName(u"i").getLayerByName(u"Bold").shapes[0].contours
        self.assertEqual([len(c.points) for c in bold_i], [4, 3], "the stem first, as in Regular")
        self.assertEqual([s.shapeData.componentGlyph for s in package.findName(u"Hacute").getLayerByName(u"Bold").shapes],
                         [u"H", u"acutecomb"])
        self.assertEqual([(c.items, c.closed) for g in package.by_name.values() for layer in [g.getLayerByName(u"Regular")]
                          if layer is not None for s in layer.shapes for c in s.contours], regular,
                         "the master compared with never changes")
        done = [text for level, text in logged if level == "done"]
        self.assertTrue(done and u"3 glyph layers" in done[0], logged)
        self.assertIn(u"contour 1 reversed", done[0])
        self.assertTrue(any(u"need the designer" in text and u"x" in text for _, text in logged), logged)

    def test_write_metrics(self):
        dialog = self.dialog()
        dialog.mode_share.checked, dialog.share.value = True, 120
        dialog.check_vertical()
        writes = fc.metric_writes(dialog.suggestions)
        self.assertTrue(writes)
        info = dialog.package.fgPackage.info
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.write_suggestions()
        self.assertEqual([level for level, _ in logged if level == "error"], [], logged)
        values = dict((s.key, s.value) for s in dialog.suggestions)
        self.assertEqual((info.openTypeOS2TypoAscender, info.openTypeHheaAscender, info.openTypeOS2WinAscent),
                         (values["typo_ascender"], values["hhea_ascender"], 1100))
        self.assertEqual(info.openTypeOS2Selection, [7])
        self.assertEqual(fc.metric_writes(dialog.suggestions), [], "checked again: as suggested")
        self.assertEqual(dialog.package.ascender_value, 750, "the master's own metrics left alone")
        self.assertTrue(any(level == "done" and u"Wrote" in text for level, text in logged), logged)

    def written(self, unsaved=False, unset=()):
        """A dialog that wrote its suggestions into its font (unsaved: no path; unset: info fields None)."""
        dialog = self.dialog()
        package = dialog.package
        if unsaved:
            package.path = None
        for field in unset:
            setattr(package.fgPackage.info, field, None)
        dialog.mode_share.checked, dialog.share.value = True, 120
        dialog.check_vertical()
        dialog.log.add = lambda text, level="info": None
        dialog.write_suggestions()
        self.assertTrue(dialog.put_back)
        return dialog, package

    def test_put_back(self):
        dialog, package = self.written()
        info = package.fgPackage.info
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.put_back_values()
        self.assertEqual((info.openTypeOS2TypoAscender, info.openTypeHheaAscender, info.openTypeOS2WinAscent),
                         (800, 900, 1000), logged)
        self.assertIsNone(dialog.put_back)
        self.assertEqual([level for level, _ in logged if level in ("error", "warning")], [], logged)

    def test_put_back_only_into_the_font_written_to(self):
        """Two unsaved fonts of one family name share a font key: the old values of one never go into the other."""
        dialog, written = self.written(unsaved=True)
        other = FakePackage()
        other.path = None
        other.fgPackage.info.openTypeHheaAscender = 1100
        self.assertEqual(self.ak.font_key(other), self.ak.font_key(written))
        self.workspace.currentPackage = other
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.put_back_values()
        self.assertEqual(other.fgPackage.info.openTypeHheaAscender, 1100, "the other font left alone")
        self.assertTrue(any(level == "warning" and u"nothing was put back" in text for level, text in logged), logged)
        self.assertTrue(dialog.put_back, "kept for the font written to")
        self.workspace.currentPackage = written
        dialog.put_back_values()
        self.assertEqual(written.fgPackage.info.openTypeHheaAscender, 900)
        self.assertIsNone(dialog.put_back)

    def test_put_back_unset_and_refused(self):
        """A value that was not set stays as written and is named; one FontLab refuses stays held."""
        dialog, package = self.written(unset=("openTypeHheaAscender",))
        self.assertIn("hhea_ascender", dialog.put_back[3])
        info = package.fgPackage.info
        written = info.openTypeHheaAscender
        self.assertIsNotNone(written)

        class Refusing(object):
            def __setattr__(self, name, value):
                if name == "openTypeOS2TypoAscender":
                    raise ValueError("refused")
                setattr(info, name, value)

            def __getattr__(self, name):
                return getattr(info, name)

        package.fgPackage.info = Refusing()
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.put_back_values()
        self.assertEqual(info.openTypeHheaAscender, written, "an unset value cannot be unset again")
        self.assertEqual(info.openTypeOS2WinAscent, 1000)
        self.assertNotEqual(info.openTypeOS2TypoAscender, 800)
        self.assertTrue(any(u"hhea ascender was not set before; set to %d now" % written in text
                            for level, text in logged if level == "warning"), logged)
        self.assertEqual(dialog.put_back[2], ["typo_ascender"], "the refused value kept, the others done")
        package.fgPackage.info = info
        dialog.put_back_values()
        self.assertEqual(info.openTypeOS2TypoAscender, 800)
        self.assertIsNone(dialog.put_back)


class ScriptTests(unittest.TestCase):
    """Every script of Unicode is checkable as a script, where no language's orthography is known: its
    own characters are the measure, those it shares with other scripts are auxiliary, and a script of
    100,000 characters makes no list of them."""

    def scripts(self):
        every = fc.load_character_sets(os.path.join(HERE, os.pardir, "checks", fc.SETS_FILE))
        return dict((one.name, one) for one in every if isinstance(one, fc.ScriptSet))

    def test_data(self):
        scripts = self.scripts()
        self.assertEqual(len(scripts), 172, "Unicode 17.0's scripts, without Common and Inherited")
        self.assertEqual(set(scripts) & set([u"Common", u"Inherited"]), set())
        known = fc.load_known_scripts(ORTHOGRAPHIES_FILE)
        self.assertEqual(set(known.not_covered) - set(scripts), set(), "each script not yet covered has its set")
        for name, own, shared, since in ((u"Latin", 1492, 67, u"1.1"), (u"Han", 103351, 308, u"1.1"),
                                         (u"Ol Onal", 44, 2, u"16.0"), (u"Sidetic", 26, 0, u"17.0"),
                                         (u"Kirat Rai", 58, 0, u"16.0"), (u"Braille", 256, 0, u"3.0")):
            one = scripts[name]
            self.assertEqual((one.own_count, one.shared_count, one.since), (own, shared, since), name)
            self.assertEqual((one.kind, one.script, one.iso, one.size()), ("set", u"Scripts (Unicode)", u"script:" + name, own))
            self.assertIn(u"A script of Unicode 17.0.0", one.definition)
            self.assertIn(u"Encoded since Unicode %s." % since, one.definition)
        self.assertEqual(sum(one.own_count for one in scripts.values()), 150031)
        # Nothing is made into characters by loading or by counting
        self.assertEqual(scripts[u"Han"].lists, {})
        latin, deva = scripts[u"Latin"], scripts[u"Devanagari"]
        self.assertEqual(len(latin.base), 1492)
        self.assertIn(u"a", latin.base)
        self.assertNotIn(u"1", latin.base, "a digit is Common, with no script of its own: no script's")
        self.assertIn(u(0x0964), deva.auxiliary, "the danda: Common, and Devanagari's by Script_Extensions")
        self.assertIn(u(0x0964), scripts[u"Bengali"].auxiliary)
        self.assertNotIn(u(0x0964), deva.base)
        self.assertNotIn(u(0x180E), scripts[u"Mongolian"].base, "a format character: no glyph")

    def test_checked_by_ranges(self):
        script = fc.ScriptSet(u"Test", u"41-43 61-63", u"B7 2E31", u"1.1", u"Scripts (Unicode)", u"17.0.0")
        self.assertEqual((script.own_count, script.shared_count, script.lists), (6, 2, {}))
        r = fc.check_entry(script, font([0x41, 0x42, 0x43, 0x61, 0x62, 0x63, 0xB7, 0x2E31]))
        self.assertEqual((r.level, len(r.missing), len(r.auxiliary_missing), r.have), ("covered", 0, 0, 8))
        r = fc.check_entry(script, font([0x41, 0x42, 0x43, 0x61, 0x62, 0x63, 0xB7]))
        self.assertEqual((r.level, list(r.auxiliary_missing)), ("nearly", [u(0x2E31)]),
                         "its own characters all there: within reach, a shared one missing")
        self.assertEqual(fc.language_note(r), u"1 shared missing")
        self.assertEqual(fc.needs(r), [u(0x2E31)])
        r = fc.check_entry(script, font([0x41, 0x42, 0x61]), nearly=3)
        self.assertEqual((r.level, list(r.missing), fc.language_note(r)), ("nearly", [u"C", u"b", u"c"], u"3 of 6 missing"))
        r = fc.check_entry(script, font([0x41]), nearly=3)
        self.assertEqual((r.level, r.have), ("started", 1))
        r = fc.check_entry(script, font([0x3B1]))
        self.assertEqual((r.level, r.have, len(r.missing)), ("missed", 0, 6))
        # A character it shares with other scripts is not a start of it (U+00B7: a Latin font has it, and
        # Han and Carian were "started" in such a font); it still counts as had, and as shared
        shared = fc.check_entry(script, font([0xB7, 0x2E31]), nearly=3)
        self.assertEqual((shared.level, shared.have, len(shared.missing), len(shared.auxiliary_missing)), ("missed", 2, 6, 0))
        shared = fc.check_entry(script, font([0xB7, 0x41]), nearly=3)
        self.assertEqual((shared.level, shared.have), ("started", 2), "one of its own: started")
        self.assertEqual(script.lists, {}, "checked on its ranges: no list of its characters was made")
        self.assertIsInstance(fc.check_entry(language(u"a b"), font([0x61])).missing, list)
        tip = fc.coverage_tip(r)
        self.assertTrue(tip.startswith(u"Test: missed (the font has 0 of its 6 characters, and 0 of the 2 it shares "
                                       u"with other scripts).\nA script of Unicode 17.0.0: its own characters"), tip)
        self.assertIn(u"\nMissing: A B C a b c\nShared characters missing: ", tip)
        self.assertNotIn(u"No language data", tip)
        self.assertIn(u"\n%s\n" % fc.NO_LANGUAGE_DATA, fc.coverage_tip(r, (), True))
        one = fc.ScriptSet(u"One", u"41", u"")
        self.assertIn(u"the font has 0 of its 1 character)", fc.coverage_tip(fc.check_entry(one, font([]))))
        # A letter the anchors compose counts, as in a language
        composing = fc.ScriptSet(u"Composing", u"65 E9", u"")
        r = fc.check_entry(composing, font([0x65, 0x301], {0x65: [u"top"], 0x301: [u"_top"]}))
        self.assertEqual((r.level, [c for c, _ in r.composed]), ("covered", [u(0xE9)]))

    def test_a_large_script_makes_no_list(self):
        """Han: about 100,000 characters. Its row shows counts; selecting it lists the first 200 missing
        and counts the rest; nothing looks at all of them."""
        han = self.scripts()[u"Han"]
        han.lists.clear()
        r = fc.check_entry(han, font([0x4E00, 0x61]))
        self.assertEqual((r.level, len(r.missing), fc.language_note(r)), ("started", 103350, u"103,350 of 103,351 missing"))
        self.assertIsInstance(r.missing, fc.CodeItems)
        self.assertEqual(fc.check_entry(han, font(list(range(0x20, 0x7F)) + [0xB7])).level, "missed",
                         "a Latin font with U+00B7 (Han's by Script_Extensions) has none of Han")
        tip = fc.coverage_tip(r, (), False)
        self.assertIn(u"Han: started (the font has 1 of its 103,351 characters, and 0 of the 308 it shares", tip)
        # The list's font, which tooltips are set in, does not draw a script this large: code points, not boxes
        self.assertIn(u"\nMissing, by code point (a set this large is not drawn by the list's font): U+2E80 to U+2E99, "
                      u"U+2E9B to U+2EF3, U+2F00 to U+2FD5, U+3005, U+3007, U+3021 to U+3029, and 103,010 more\n", tip)
        self.assertTrue(all(code < 128 for code in fc.code_points(tip)), "no character of the script in it")
        self.assertFalse(fc.names_characters(han))
        self.assertTrue(fc.names_characters(self.scripts()[u"Braille"]))
        self.assertTrue(fc.names_characters(language(u"a b")))
        big = fc.Language(u"block-1f300", u"Big (Unicode block)", u"", u"Games and pictographs", u"set", u"", 0,
                          [u(code) for code in range(0x1F300, 0x1F600)], [], u"", kind="set", definition=u"A block.")
        self.assertFalse(fc.names_characters(big))
        self.assertIn(u"\nMissing, by code point (a set this large is not drawn by the list's font): U+1F300 to U+1F5FF",
                      fc.coverage_tip(fc.check_language(big, font([]))))
        self.assertEqual(fc.few_codes([u"a", u"b", u"d"]), u"U+0061 to U+0062, U+0064")
        self.assertEqual(fc.few_codes([u"a", u"c", u"e"], 2), u"U+0061, U+0063, and 1 more")
        self.assertEqual(fc.few_codes([]), u"")
        selection = fc.selection_of(r)
        self.assertEqual((selection.count(), len(selection.wanted())), (103350, fc.WANTED_MOST))
        self.assertEqual(fc.selection_title(selection), u"Han (103350)")
        rows, left = fc.selection_rows([], selection)
        listed = sum(len(row.items) for row in rows)
        self.assertEqual((listed, left), (fc.FLOAT_MOST, 103350 - fc.FLOAT_MOST), "the first 200, the rest counted")
        self.assertEqual(rows[0].items, [u(0x2E80)], "by code point")
        self.assertEqual([len(row.completing) for row in rows[:3]], [0, 0, 0])
        self.assertIn(u"Han misses 103350 glyphs. 103150 more are not listed (the first 200 are).",
                      fc.selection_text(selection, left))
        self.assertEqual(fc.languages_gained([r], [u(0x2E80)]), [])
        self.assertEqual(fc.buildable_candidates([r], [(0xC0, 0x250)]), [])
        self.assertEqual(han.lists, {}, "and still no list of its 103,351 characters")

    def test_code_items(self):
        items = fc.CodeItems([0x61, 0x1F600, 0x62])
        self.assertEqual((len(items), list(items), items[1], items[-1]), (3, [u"a", u(0x1F600), u"b"], u(0x1F600), u"b"))
        self.assertEqual((items[:2], items[5:]), ([u"a", u(0x1F600)], []))
        self.assertTrue(u(0x1F600) in items and u"z" not in items and u"ab" not in items)
        self.assertIs(items + [], items)
        self.assertIs([] + items, items)
        self.assertEqual(items + [u"z"], [u"a", u(0x1F600), u"b", u"z"])
        self.assertEqual([u"z"] + items, [u"z", u"a", u(0x1F600), u"b"])
        joined = items + fc.CodeItems([0x63])
        self.assertIsInstance(joined, fc.CodeItems)
        self.assertEqual(len(joined), 4)
        self.assertTrue(items == [u"a", u(0x1F600), u"b"] and items != [u"a"])
        self.assertFalse(fc.CodeItems([]))
        self.assertEqual(fc.ranges_of(u"20-7E A0 1F600"), [(0x20, 0x7E), (0xA0, 0xA0), (0x1F600, 0x1F600)])

    def test_stated_limits(self):
        """What cannot be supported is said plainly, with its date and the data's own counts."""
        self.assertEqual(fc.AS_OF, u"November 2026")
        for name in (u"Loma", u"Naxi Dongba", u"Balti-A and Balti-B", u"Chola", u"Landa", u"Maya hieroglyphs",
                     u"Numidian", u"Book Pahlavi", u"Pyu", u"Ranjana", u"Satavahana"):
            self.assertIn(name, fc.NOT_ENCODED)
        self.assertTrue(fc.NOT_ENCODED.startswith(u"As of November 2026, a script Unicode has not encoded can be "
                                                  u"neither checked nor built, except through private-use code points"))
        self.assertEqual(fc.limits_text(0, 0), u"")
        self.assertEqual(fc.limits_text(5055, 4509),
                         u"As of November 2026, of the 5,055 languages not covered, 4,509 have a script on record but "
                         u"no source that gives their characters, and 546 have no script on record (many have no "
                         u"written form, or no open description that can be cited). The limit is the record itself, "
                         u"not the tool.")
        self.assertIn(u"1 has a script on record but no source that gives its characters, and 1 has no script",
                      fc.limits_text(2, 1))
        self.assertIn(u"1 language is not covered: a script is on record for it", fc.limits_text(1, 1))
        self.assertIn(u"1 language is not covered: no script is on record for it", fc.limits_text(1, 0))
        families, known = fc.load_families(FAMILIES_FILE), fc.load_known_scripts(ORTHOGRAPHIES_FILE)
        self.assertEqual((len(families.unlisted), sum(1 for row in families.unlisted if row[0] in known.of_languages)),
                         (5036, 4501), "the counts the docs state")

    def test_progress_and_log_texts(self):
        self.assertEqual(len(fc.BUSY_SHARES), len(fc.BUSY_STEPS))
        self.assertEqual(list(fc.BUSY_SHARES), sorted(fc.BUSY_SHARES))
        self.assertEqual((fc.busy_share(0), fc.busy_share(4), fc.busy_share(9)), (0.0, 1.0, 1.0))
        self.assertAlmostEqual(fc.busy_share(1), 0.10)
        self.assertAlmostEqual(fc.busy_share(3, 0.5), 0.70)
        self.assertAlmostEqual(fc.busy_share(3, 7), 1.0)
        self.assertEqual(fc.checked_sentence(2510, 99, 172, 0.44),
                         u"Checked 2,510 languages, 99 character sets, and 172 scripts in 0.4 s.")
        self.assertEqual(fc.checked_sentence(1, 1, 1, 2), u"Checked 1 language, 1 character set, and 1 script in 2.0 s.")
        self.assertEqual(fc.checked_sentence(0, 0, 0, 0), u"Checked 0 languages in 0.0 s.")
        self.assertEqual(fc.checked_sentence(2, 2, 0, 1.25), u"Checked 2 languages and 2 character sets in 1.2 s.")
        self.assertIn(u"QProgressBar::chunk { background-color: rgb(30, 120, 40)", fc.BAR_SHEET % fc.BAR_GREEN[1])


@unittest.skipUnless(sys.version_info[0] >= 3 and os.path.isfile(os.path.join(TRAIN, "character_sets.py")),
                     "the train scripts are Python 3's, and are not installed")
class SurveyTests(unittest.TestCase):
    """checks/train/character_sets.py: the scripts' sets and the survey of Unicode, from small files of
    the Unicode Character Database's shapes (no source is downloaded here)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, TRAIN)
        try:
            import character_sets
        finally:
            sys.path.remove(TRAIN)
        cls.c = character_sets

    def files(self):
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-survey-")
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, True))
        texts = {
            "UnicodeData": "0041;LATIN CAPITAL LETTER A;Lu;0;L;;;;;N;;;;0061;\n0061;LATIN SMALL LETTER A;Ll;0;L;;;;;N;;;0041;;0041\n"
                           "0031;DIGIT ONE;Nd;0;EN;;1;1;1;N;;;;;\n0964;DEVANAGARI DANDA;Po;0;L;;;;;N;;;;;\n"
                           "0905;DEVANAGARI LETTER A;Lo;0;L;;;;;N;;;;;\n0985;BENGALI LETTER A;Lo;0;L;;;;;N;;;;;\n"
                           "200D;ZERO WIDTH JOINER;Cf;0;BN;;;;;N;;;;;\n0009;<control>;Cc;0;S;;;;;N;;;;;\n"
                           "E000;<Private Use, First>;Co;0;L;;;;;N;;;;;\nE002;<Private Use, Last>;Co;0;L;;;;;N;;;;;\n"
                           "2669;QUARTER NOTE;So;0;ON;;;;;N;;;;;\n",
            "Scripts": "0041 ; Latin # Lu\n0061 ; Latin # Ll\n0031 ; Common # Nd\n0964 ; Common # Po\n0905 ; Devanagari # Lo\n"
                       "0985 ; Bengali # Lo\n200D ; Inherited # Cf\n0009 ; Common # Cc\n2669 ; Common # So\n",
            "ScriptExtensions": "0964 ; Beng Deva # Po\n",
            "PropertyValueAliases": "sc ; Beng ; Bengali\nsc ; Deva ; Devanagari\nsc ; Latn ; Latin\nsc ; Zyyy ; Common\n",
            "DerivedAge": "0041 ; 1.1 #\n0061 ; 1.1 #\n0905 ; 1.1 #\n0985 ; 16.0 #\n0964 ; 1.1 #\n",
            "Blocks": "0000..007F; Basic Latin\n0900..097F; Devanagari\n0980..09FF; Bengali\n2000..206F; General Punctuation\n"
                      "2600..26FF; Miscellaneous Symbols\nE000..F8FF; Private Use Area\n",
        }
        found = {}
        for name, text in texts.items():
            key = "unicode-%s-%s.txt" % (self.c.UNICODE_VERSION, name)
            found[key] = os.path.join(folder, key)
            with open(found[key], "w", encoding="utf-8") as handle:
                handle.write(text)
        return found

    def test_pins(self):
        c = self.c
        for name in ("Scripts", "ScriptExtensions", "PropertyValueAliases", "DerivedAge", "Blocks", "UnicodeData"):
            url, digest = c.SOURCES["unicode-17.0.0-%s.txt" % name]
            self.assertEqual(url, "https://www.unicode.org/Public/17.0.0/ucd/%s.txt" % name)
            self.assertEqual(len(digest), 64)
        sys.path.insert(0, TRAIN)
        try:
            import orthographies
        finally:
            sys.path.remove(TRAIN)
        self.assertEqual(c.SOURCES["unicode-17.0.0-Scripts.txt"], orthographies.SOURCES["unicode-17.0.0-Scripts.txt"],
                         "one pin for the file the two scripts read")
        self.assertEqual(len(c.GROUPS), 6)
        names = [name for _, name in c.BLOCKS]
        self.assertEqual((len(names), len(set(names))), (62, 62))
        for name in names:  # (no private-use, surrogate, or control range is a set)
            self.assertFalse("Private Use" in name or "Surrogate" in name or "Control" == name or "Tags" == name, name)

    def test_scripts_from_the_database(self):
        rows = self.c.build_scripts(self.files())
        self.assertEqual(rows, [["Bengali", "985", "964", "16.0"], ["Devanagari", "905", "964", "1.1"],
                                ["Latin", "41 61", "", "1.1"]],
                         "its own characters; the danda Unicode says it shares; no digit, control, or format character")

    def test_survey(self):
        c = self.c
        files = self.files()
        sets = [["block-2600", "Miscellaneous Symbols (Unicode block)", 2, "", "2669", ""]]
        lines, rest, untouched, totals = c.survey(files, sets, c.build_scripts(files), [])
        self.assertEqual(totals["assigned"], 9, "private-use code points are no characters")
        self.assertEqual((totals["scripts"], totals["sets"]), (5, 1))
        self.assertTrue(totals["none_before_scripts"] >= totals["none_before_blocks"] >= totals["none"] >= 1,
                        "each kind of set answers for more; a control character stays in none")
        self.assertTrue(lines[0].startswith("| General category | Assigned | In an orthography |"))
        self.assertEqual(lines[-1].split("|")[1].strip(), "All")
        self.assertIn("Basic Latin", [name for _, _, name in rest], "its control character: in no orthography, set, or script")
        self.assertNotIn("Miscellaneous Symbols", [name for _, _, name in rest])
        self.assertNotIn("Private Use Area", [name for _, _, name in rest] + [row[1] for row in untouched])
        self.assertIn("Bengali", [row[1] for row in untouched], "a block no character set touches: its script's set does")


class LoadingTests(unittest.TestCase):
    """The loading state: a progress bar over the lists' area, the steps in the log when done, and
    tooltips made when they are asked for. It stands on DialogTests' fakes (its own class, so that
    DialogTests' tests are not run twice)."""

    setUpClass = classmethod(DialogTests.__dict__["setUpClass"].__func__)
    tearDownClass = classmethod(DialogTests.__dict__["tearDownClass"].__func__)
    dialog = DialogTests.__dict__["dialog"]
    linked_lists = DialogTests.__dict__["linked_lists"]

    def recorded_dialog(self, names):
        gui = sys.modules["PythonQt"].QtGui
        saved = dict(gui.classes)
        made = []

        def recorded(kind):
            class Widget(Recorded):
                def __init__(self, *args, **kwargs):
                    Recorded.__init__(self, *args, **kwargs)
                    self.__dict__["kind"] = kind
                    made.append(self)
            return Widget

        for name in names:
            gui.classes[name] = recorded(name)
        try:
            dialog = self.dialog()
        finally:
            gui.classes.clear()
            gui.classes.update(saved)
        return dialog, made

    def test_progress_bar(self):
        """The owner: "The loading of Font Check is not visible enough; a green progression bar or status
        in the log could help better visualize it." """
        dialog, made = self.recorded_dialog(("QProgressBar",))
        bar = dialog.busy_bar
        self.assertEqual(bar.told("setRange"), [(0, fc.BAR_RANGE)])
        self.assertEqual(bar.told("setTextVisible"), [(False,)])
        self.assertEqual(bar.told("setProperty"), [(self.ak.LEAVE_ALONE_PROP, True)], "dark mode leaves its green alone")
        sheet = bar.told("setStyleSheet")[-1][0]
        light = self.ak.LOG_COLORS["done"][1]
        self.assertIn(u"QProgressBar::chunk { background-color: rgb(%d, %d, %d)" % light, sheet, "the log's done green")
        self.assertTrue(sheet.startswith(u"QProgressBar {"), "on the bar itself")
        self.assertTrue(bar.told("setWhatsThis")[0][0])
        dialog.busy_row, dialog.busy_step, dialog.busy_label = Recorded(), Recorded(), Recorded()
        dialog.coverage_stack, dialog.coverage.status = Recorded(), Recorded()
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((text, level))
        dialog.show()
        self.assertEqual((dialog.busy_row.visible, dialog.busy_step.text), (True, u"Reading the language data" + u(0x2026)),
                         "the bar from the first paint, the step's name beside it")
        waiting = []
        dialog.defer = waiting.append
        dialog.nearly.value, dialog.show_absent.checked, dialog.inferred_box.checked = 30, True, True
        del bar.calls[:]
        dialog.check_coverage()
        self.assertEqual((dialog.busy_row.visible, bar.value), (True, 0))
        values, pages = [], []
        while waiting:
            waiting.pop(0)()
            values.append(bar.value)
            pages.append(dialog.coverage_stack.currentIndex)
        self.assertEqual(values[:3], [100, 200, 400], "determinate over the known steps")
        self.assertEqual(values[-1], fc.BAR_RANGE)
        moved = [args[0] for args in bar.told("setValue")]
        self.assertEqual(moved, sorted(moved), "it only moves forward")
        listing = [value for value in moved if 400 < value < fc.BAR_RANGE]
        self.assertGreater(len(set(listing)), 4, "and within the listing, by the rows made")
        self.assertGreaterEqual(len(bar.told("repaint")) + len([1 for name, _ in bar.calls if name == "setValue"]), len(moved))
        self.assertEqual((dialog.busy, dialog.busy_row.visible, pages[-1]), (False, False, 1), "gone with the lists shown")
        done = [text for text, level in logged if level == "done"]
        self.assertEqual(len(done), 1, "one line when done, not one per step")
        self.assertTrue(re.match(u"^Checked 2,511 languages, 99 character sets, and 172 scripts in [0-9]+\\.[0-9] s\\.$",
                                 done[0]), done[0])
        self.assertIn(u"of Unicode's 172 are covered whole.", dialog.coverage.status.text)
        self.assertIn(u"character sets</b> of 99 are covered.", dialog.coverage.status.text)

    def test_tooltips_made_when_asked_for(self):
        """Some 2,600 rows each had a rich tooltip made, measured, and set as the list was filled: a
        row's is now made when Qt asks for it."""
        dialog, state, click, Row = self.linked_lists()
        told = []
        real = dialog.item

        class Item(Recorded):
            def data(self, column, role):
                return self.__dict__.get("value")

        def item(texts, data, tip=u"", names=False):
            found = real(texts, data, tip, names)
            told.append((data, callable(tip), tip))
            return found

        dialog.item = item
        measured = []
        tip = dialog.tip
        dialog.tip = lambda text, names=False, rich=False: measured.append(text) or tip(text, names, rich)
        dialog.fill_right()
        rows = dialog.right_rows["languages"]
        lazy = [one for one in told if one[1]]
        self.assertEqual(len(lazy), len(rows), "every language's row")
        self.assertGreater(len(rows), 1700)
        self.assertLess(len(measured), 200, "no tooltip is made or measured for them as the list is filled")
        # Qt asks for the tooltip of the row under the mouse: made now, shown over that row
        gui = sys.modules["PythonQt"].QtGui
        shown = []

        class ToolTip(object):
            @staticmethod
            def showText(*args):
                shown.append(args)

        saved = dict(gui.classes)
        gui.classes["QToolTip"] = ToolTip

        class Event(object):
            def __init__(self, kind, row):
                self.kind, self.row = kind, row

            def type(self):
                return self.kind

            def pos(self):
                return self.row

            def globalPos(self):
                return "there"

        tree = dialog.right_trees["languages"]
        tree.itemAt = lambda pos: pos
        tree.visualItemRect = lambda item: "its row"
        tree.viewport = lambda: "viewport"
        try:
            index = [i for i, r in enumerate(rows) if r.language.iso == u"deu"][0]
            self.assertIs(dialog.show_tip(tree, Event(110, Row(index))), True)
            self.assertEqual(len(shown), 1)
            where, text, widget, rect = shown[0]
            self.assertEqual((where, widget, rect), ("there", "viewport", "its row"))
            self.assertIn(u"German", text)
            self.assertIn(u"Latin script", text)
            self.assertTrue(text.startswith(u"<table ") or text.startswith(u"<span"), "rich text, as every tooltip")
            self.assertEqual(text, dialog.right_tip("languages", Row(index)))
            self.assertIs(dialog.show_tip(tree, Event(110, Row(u"#Latin"))), False, "a heading keeps what is set on it")
            self.assertIs(dialog.show_tip(tree, Event(110, None)), False)
            self.assertIs(dialog.show_tip(tree, Event(110, Row(10 ** 6))), False, "a row of an earlier filling")
            self.assertIs(dialog.show_tip(dialog.add_tree, Event(110, Row(0))), False, "the glyphs' lists keep theirs")
            self.assertEqual(len(shown), 1)

            class Bare(object):  # (an event handed over without its positions: the cursor's are taken)
                def type(self):
                    return 110

            class Cursor(object):
                @staticmethod
                def pos():
                    return "cursor"

            gui.classes["QCursor"] = Cursor

            class Viewport(object):
                def mapFromGlobal(self, where):
                    return Row(index)

            tree.viewport = lambda: Viewport()
            self.assertIs(dialog.show_tip(tree, Bare()), True)
            self.assertEqual(shown[-1][0], "cursor")
        finally:
            gui.classes.clear()
            gui.classes.update(saved)
        self.assertEqual(dialog.entry_tip("languages", object()), u"")
        dialog.right_tab_changed(2)
        family = dialog.right_rows["families"][0]
        self.assertIn(family.name, dialog.right_tip("families", Row(0)))

    def test_every_control_has_its_own_help(self):
        """The owner found, in another tool, that right-clicking a control showed a neighboring
        control's help: each button, check box, combo box, spin box, field, list, and tab bar built by
        the dialog has a What's This of its own, and a label has its control's."""
        kinds = ("QPushButton", "QCheckBox", "QComboBox", "QSpinBox", "QDoubleSpinBox", "QLineEdit", "QTreeWidget",
                 "QListWidget", "QRadioButton", "QToolButton", "QTabBar", "QProgressBar", "QLabel")
        dialog, made = self.recorded_dialog(kinds)
        controls = [one for one in made if one.kind != "QLabel"]
        self.assertGreater(len(controls), 45)
        texts = {}
        for one in controls:
            said = one.told("setWhatsThis")
            name = u"%s %r" % (one.kind, one.made)
            self.assertTrue(said and (u"%s" % said[-1][0]).strip(), u"%s has no What's This" % name)
            texts.setdefault(u"%s" % said[-1][0], []).append(name)
        shared = dict((text, names) for text, names in texts.items() if len(names) > 1)
        self.assertEqual(shared, {}, "no two controls answer with the same text")
        labels = dict((one.made[0], one) for one in made if one.kind == "QLabel" and one.made and one.told("setBuddy"))
        self.assertEqual(sorted(labels), [u"Beside it", u"Compare every master with", u"Languages", u"Master",
                                          u"Within reach: missing at most"])
        for text, control in ((u"Within reach: missing at most", dialog.nearly), (u"Languages", dialog.status_filter),
                              (u"Master", dialog.clip_master), (u"Compare every master with", dialog.reference),
                              (u"Beside it", dialog.compare_master)):
            self.assertEqual(labels[text].told("setWhatsThis")[-1], control.told("setWhatsThis")[-1], text)
            self.assertIs(labels[text].told("setBuddy")[-1][0], control)

    def test_spin_box_says_its_number(self):
        """The shared plural helper keeps the box's word in step: "1 glyph", "2 glyphs"."""
        dialog, made = self.recorded_dialog(("QSpinBox",))
        spin = dialog.nearly
        self.assertEqual(spin.told("setSuffix"), [(u" glyphs",)])
        signals = [args for name, args in spin.calls if name == "connect"]
        self.assertEqual(signals, [], "(a recorded widget keeps setters and adders only)")
        for value, suffix in ((1, u" glyph"), (0, u" glyphs"), (2, u" glyphs")):
            box = Recorded()
            box.setValue(value)
            self.ak.counted_suffix(box, u"glyph")
            self.assertEqual(box.told("setSuffix"), [(suffix,)])


if __name__ == "__main__":
    unittest.main()
