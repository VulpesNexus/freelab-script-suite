"""Tests of FreeLab's Font Check: language coverage, vertical metrics, and masters' compatibility.
Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unicodedata
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "checks"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "diacritics"))
import freelab_font_check as fc  # noqa: E402

LANGUAGES_FILE = os.path.join(HERE, os.pardir, "checks", "language_coverage.json")
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
        self.assertEqual((result.level, result.base_missing()), ("missed", 4))

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
        self.assertEqual(latin[u"vie"].level, "missed", "Vietnamese needs Latin Extended Additional")
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
        self.assertEqual(fc.gain_text(0, []), u"Check characters to see how many languages they complete.")
        self.assertEqual(fc.gain_text(1, []), u"With 1 character checked: no language is complete yet")
        gained = fc.languages_gained(results, [schwa, small_schwa])
        self.assertEqual(fc.gain_text(2, gained), u"With 2 characters checked: +2 languages (Latin)")
        self.assertEqual(fc.gain_text(2, gained[:1], lambda text: u"<b>%s</b>" % text),
                         u"With 2 characters checked: <b>+1 language</b> (Latin)")
        greek = fc.check_language(language(u(0x3B1), script=u"Greek", name=u"Greek"), font([]))
        self.assertEqual(fc.gain_text(3, gained + [greek]), u"With 3 characters checked: +3 languages (Latin 2, Greek 1)")

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
        self.assertEqual(fc.script_text(s), u"0 of 6 languages \N{MIDDLE DOT} 5 within reach")
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

    def dialog(self):
        self.workspace.currentPackage = FakePackage()  # (a font of its own: the fixes and writes change it)
        dialog = fc.FontCheckDialog()
        self.assertIsNone(dialog.failed, dialog.failed)
        dialog.log.add = lambda text, level="info": self.fail(text) if level == "error" else None
        return dialog

    def test_coverage(self):
        dialog = self.dialog()
        dialog.composing.checked = True
        dialog.nearly.value, dialog.historical.checked = 3, False
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
        dialog.mark_needed(dialog.rows[0].needing[0])
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


if __name__ == "__main__":
    unittest.main()
