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
    attaches = None
    if anchors is not None:
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
        diacritics_font = dm.Font([u"r", u"caron", u"l"], [(u"r", 0x72), (u"l", 0x6C)])
        built = [r.char for r in dm.plan(diacritics_font, candidates) if not r.missing]
        self.assertEqual(built, [u(0x159), u(0x13E)], "r and l with a caron, from the font's caron")


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
                         u"A grave reaches 900", u"Capitals are not centered"):
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
    def __init__(self, points):
        self.points, self.closed = points, True

    def nodes(self):
        return [FakeNode(x, y) for x, y in self.points]

    def path(self):
        return self.points


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


class FakeAnchor(object):
    def __init__(self, name):
        self.name = name


class FakeLayer(object):
    def __init__(self, shapes, anchors=(), advance=500):
        self.shapes, self.anchors, self.advanceWidth = shapes, [FakeAnchor(a) for a in anchors], advance
        self.isNull = False


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
                                                                     FakeShape(component=u"acutecomb")])})]
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


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        cls.saved = dict((name, sys.modules.get(name)) for name in ("PythonQt", "fontlab", fc.AUTO_KERNING_MODULE))
        qt = Anything()
        qt.QtCore, qt.QtGui = _FakeQtModule(), _FakeQtModule()
        package = FakePackage()
        workspace = Anything()
        workspace.packages = lambda: [package]
        workspace.currentPackage = package
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

    def test_metrics(self):
        dialog = self.dialog()
        dialog.mode.currentIndex, dialog.share.value = 0, 120
        dialog.check_vertical()
        clipped = [f for f in dialog.metrics.findings if isinstance(f, fc.MetricFinding) and f.kind == "clip-top"]
        self.assertEqual([(f.glyphs[0][1], f.value) for f in clipped], [(u"Agrave", 100), (u"Agrave", 100)])
        self.assertTrue(dialog.suggestions)
        dialog.metrics_picture(u"Agrave", u"Bold")

    def test_masters(self):
        dialog = self.dialog()
        dialog.reference.currentText, dialog.reference.currentIndex = u"Regular", 0
        dialog.check_masters()
        found = sorted((f.glyph, f.master, f.kind) for f in dialog.masters.findings)
        self.assertEqual(found, [(u"o", u"Bold", "direction")], "eacute, in Regular only, does not vary")
        dialog.outline_picture(u"o", u"Bold", 1)


if __name__ == "__main__":
    unittest.main()
