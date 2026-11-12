"""Tests of FreeLab's Font Compare: glyphs matched, outlines, metrics, components, anchors, kerning,
and features compared. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import math
import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "compare"))
import freelab_font_compare as fcmp  # noqa: E402


def square(left=0, bottom=0, size=100, clockwise=False):
    nodes = [(left, bottom, u"on"), (left + size, bottom, u"on"), (left + size, bottom + size, u"on"),
             (left, bottom + size, u"on")]
    return nodes[::-1] if clockwise else nodes


def circle(radius=100.0):
    """A circle of four cubic curves (the usual 0.5523 handles), counterclockwise."""
    k = 0.5523 * radius
    r = radius
    return [(r, 0, u"on"), (r, k, u"off"), (k, r, u"off"), (0, r, u"on"), (-k, r, u"off"), (-r, k, u"off"),
            (-r, 0, u"on"), (-r, -k, u"off"), (-k, -r, u"off"), (0, -r, u"on"), (k, -r, u"off"), (r, -k, u"off")]


def glyph(name=u"o", codes=(0x6F,), advance=500, ink=(50, 450), contours=(), components=(), anchors=()):
    return fcmp.GlyphData(name, codes, advance, ink, contours, components, anchors)


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


class MatchTests(unittest.TestCase):
    def test_by_name_then_code_point(self):
        a = [(u"A", [0x41]), (u"uni00E9", [0xE9]), (u"x.alt", []), (u"ae", [0xE6])]
        b = [(u"A", [0x41]), (u"eacute", [0xE9]), (u"y.alt", []), (u"ae", [0xE6])]
        pairs, only_a, only_b = fcmp.match_glyphs(a, b)
        self.assertEqual(pairs, [(u"A", u"A"), (u"ae", u"ae"), (u"uni00E9", u"eacute")])
        self.assertEqual((only_a, only_b), ([u"x.alt"], [u"y.alt"]))

    def test_code_point_shared_by_two_left_alone(self):
        a = [(u"uni0041", [0x41])]
        b = [(u"A.one", [0x41]), (u"A.two", [0x41])]
        pairs, only_a, only_b = fcmp.match_glyphs(a, b)
        self.assertEqual(pairs, [], "two candidates: no guess")
        self.assertEqual((only_a, only_b), ([u"uni0041"], [u"A.one", u"A.two"]))


class LabelTests(unittest.TestCase):
    def test_masters_of_one_font(self):
        self.assertEqual(fcmp.side_labels((u"f.vfc", u"Sans", u"Regular", 2), (u"f.vfc", u"Sans", u"Bold", 2)),
                         (u"Regular", u"Bold"))

    def test_two_fonts(self):
        self.assertEqual(fcmp.side_labels((u"a.vfc", u"Sans", u"Regular", 1), (u"b.vfc", u"Serif", u"Regular", 1)),
                         (u"Sans", u"Serif"))
        self.assertEqual(fcmp.side_labels((u"a.vfc", u"Sans", u"Bold", 2), (u"b.vfc", u"Serif", u"Regular", 1)),
                         (u"Sans \N{MIDDLE DOT} Bold", u"Serif"))

    def test_two_versions_of_one_font(self):
        self.assertEqual(fcmp.side_labels((u"old/Sans.vfc", u"Sans", u"R", 1), (u"new/Sans-2.vfc", u"Sans", u"R", 1)),
                         (u"Sans.vfc", u"Sans-2.vfc"))
        self.assertEqual(fcmp.side_labels((u"old/Sans.vfc", u"Sans", u"R", 1), (u"new/Sans.vfc", u"Sans", u"R", 1)),
                         (u"Sans (first)", u"Sans (second)"))


class OutlineTests(unittest.TestCase):
    def test_flatten_lines_and_curves(self):
        self.assertEqual(fcmp.flatten(square()), [(0, 0), (100, 0), (100, 100), (0, 100)])
        polygon = fcmp.flatten(circle())
        self.assertEqual(len(polygon), 4 * fcmp.CURVE_STEPS)
        self.assertTrue(all(abs(math.hypot(x, y) - 100) < 0.5 for x, y in polygon))

    def test_flatten_starts_at_an_on_curve_point(self):
        nodes = circle()
        rotated = nodes[1:] + nodes[:1]  # an off-curve point first
        self.assertEqual(sorted(fcmp.flatten(rotated)), sorted(fcmp.flatten(nodes)))

    def test_truetype_contour_of_off_curve_points(self):
        nodes = [(0, 0, u"off"), (100, 0, u"off"), (100, 100, u"off"), (0, 100, u"off")]
        polygon = fcmp.flatten(nodes)
        self.assertIn((50.0, 0.0), polygon, "an on-curve point implied midway")
        area = fcmp.shape_areas([nodes], [])[0]
        self.assertTrue(7000 < area < 10000, area)

    def test_quadratic_spline(self):
        nodes = [(0, 0, u"on"), (50, 100, u"off"), (100, 100, u"off"), (150, 0, u"on")]
        cubic = fcmp.flatten(nodes)
        spline = fcmp.flatten(nodes, quadratic=True)
        self.assertIn((75.0, 100.0), spline, "the implied point between two off-curve points")
        self.assertNotIn((75.0, 100.0), cubic)

    def test_areas_exact_for_straight_edges(self):
        moved = [(0, 0, u"on"), (100, 0, u"on"), (110, 100, u"on"), (0, 100, u"on")]
        area_a, area_b, apart = fcmp.shape_areas([square()], [moved])
        self.assertAlmostEqual(area_a, 10000.0, 6)
        self.assertAlmostEqual(area_b, 10500.0, 6)
        self.assertAlmostEqual(apart, 500.0, 6)
        self.assertAlmostEqual(fcmp.shape_share([square()], [moved]), 500.0 / 10500.0, 6)

    def test_counter_and_overlap(self):
        holed = [square(), square(25, 25, 50, clockwise=True)]
        self.assertAlmostEqual(fcmp.shape_areas(holed, [])[0], 7500.0, 6)
        overlapping = [square(), square(50, 0)]
        self.assertAlmostEqual(fcmp.shape_areas(overlapping, [])[0], 15000.0, 6, "nonzero: overlaps count once")

    def test_circle_area(self):
        area = fcmp.shape_areas([circle()], [])[0]
        self.assertLess(abs(area - math.pi * 10000) / (math.pi * 10000), 0.01)

    def test_reordered_contours_and_start_points_same_shape(self):
        one = [square(), square(200, 0)]
        other = [square(200, 0)[1:] + square(200, 0)[:1], square()]
        self.assertAlmostEqual(fcmp.shape_share(one, other), 0.0, 9)
        self.assertTrue(fcmp.same_nodes(one, other, 1))
        found = fcmp.compare_outline(glyph(contours=one), glyph(contours=other), 1)
        self.assertEqual(found.text, u"the same nodes in another order (start points or contour order)")

    def test_moved_node(self):
        moved = [(0, 0, u"on"), (100, 0, u"on"), (100, 112, u"on"), (0, 100, u"on")]
        found = fcmp.compare_outline(glyph(contours=[square()]), glyph(contours=[moved]), 1)
        self.assertIn(u"the shapes differ by", found.text)
        self.assertIn(u"nodes moved up to 12 units (contour 1)", found.text)
        self.assertEqual(fcmp.moved_most([square()], [moved]), (12.0, 1))

    def test_small_move_within_threshold(self):
        moved = [(0, 0, u"on"), (100, 0, u"on"), (100, 101, u"on"), (0, 100, u"on")]
        found = fcmp.compare_outline(glyph(contours=[square(0, 0, 1000)]), glyph(contours=[[(x * 10, y * 10, t) for x, y, t in moved]]), 0)
        self.assertIsNotNone(found, "10 units moved")
        tiny = [(0, 0, u"on"), (1000, 0, u"on"), (1000, 1001, u"on"), (0, 1000, u"on")]
        self.assertIsNone(fcmp.compare_outline(glyph(contours=[square(0, 0, 1000)]), glyph(contours=[tiny]), 1),
                          "1 unit: within the threshold, and a sliver of the ink")

    def test_counts(self):
        found = fcmp.compare_outline(glyph(contours=[square()]), glyph(contours=[square(), square(200, 0)]), 1)
        self.assertTrue(found.text.startswith(u"1 contour and 2"), found.text)
        self.assertEqual(found.short, u"contours 1, 2")
        extra = square()[:2] + [(100, 50, u"on")] + square()[2:]
        found = fcmp.compare_outline(glyph(contours=[square()]), glyph(contours=[extra]), 1)
        self.assertEqual(found.text, u"4 nodes and 5", "a node added on a straight edge: the same shape")

    def test_percent(self):
        self.assertEqual(fcmp.percent(0.0041), u"0.4%")
        self.assertEqual(fcmp.percent(0.123), u"12%")


class GlyphTests(unittest.TestCase):
    labels = (u"Regular", u"Bold")

    def test_alike(self):
        one = glyph(contours=[square()], anchors=[(u"top", 250, 500)])
        self.assertEqual(fcmp.compare_glyph(one, glyph(contours=[square()], anchors=[(u"top", 250, 500)])), [])

    def test_metrics(self):
        found = fcmp.compare_glyph(glyph(ink=(50, 450)), glyph(advance=520, ink=(60, 450)), 1, self.labels)
        self.assertEqual([d.kind for d in found], ["metrics"])
        self.assertEqual(found[0].text, u"width 500 and 520 (+20); left side 50 and 60 (+10); right side 50 and 70 (+20)")
        self.assertEqual(found[0].short, u"width +20, left side +10, right side +20")
        self.assertEqual(fcmp.compare_glyph(glyph(), glyph(advance=501), 1), [], "within the threshold")

    def test_no_ink(self):
        found = fcmp.compare_glyph(glyph(u"space", ink=None, advance=250), glyph(u"space", ink=None, advance=200))
        self.assertEqual(found[0].text, u"width 250 and 200 (-50)")

    def test_anchors(self):
        found = fcmp.compare_glyph(glyph(anchors=[(u"top", 250, 500), (u"bottom", 250, 0)]),
                                   glyph(anchors=[(u"top", 250, 512), (u"ogonek", 400, 0)]), 1, self.labels)
        self.assertEqual(found[0].text, u"anchor bottom only in Regular; anchor ogonek only in Bold; "
                                        u"anchor top moved by (0, +12)")

    def test_components(self):
        one = glyph(u"eacute", components=[(u"e", IDENTITY), (u"acutecomb", (1, 0, 0, 1, 100, 0))])
        other = glyph(u"eacute", components=[(u"e", IDENTITY), (u"acutecomb", (1, 0, 0, 1, 120, -5))])
        found = fcmp.compare_glyph(one, other, 1, self.labels)
        self.assertEqual(found[0].text, u"component acutecomb moved by (+20, -5)")
        swapped = glyph(u"eacute", components=[(u"acutecomb", (1, 0, 0, 1, 100, 0)), (u"e", IDENTITY)])
        self.assertEqual(fcmp.compare_glyph(one, swapped, 1)[0].text, u"components in another order")
        other = glyph(u"eacute", components=[(u"e", IDENTITY), (u"gravecomb", IDENTITY)])
        self.assertEqual(fcmp.compare_glyph(one, other, 1, self.labels)[0].text,
                         u"component acutecomb only in Regular; component gravecomb only in Bold")
        scaled = glyph(u"eacute", components=[(u"e", IDENTITY), (u"acutecomb", (0.9, 0, 0, 0.9, 100, 0))])
        self.assertEqual(fcmp.compare_glyph(one, scaled, 1)[0].text, u"component acutecomb scaled or turned")

    def test_names_and_codes(self):
        found = fcmp.compare_glyph(glyph(u"uni00E9", [0xE9]), glyph(u"eacute", [0xE9, 0x65]))
        self.assertEqual(found[0].text, u"named uni00E9 and eacute; code points U+00E9 and U+0065 U+00E9")

    def test_only_in_one(self):
        self.assertEqual(fcmp.compare_glyph(glyph(), None, labels=self.labels)[0].text, u"only in Regular")
        self.assertEqual(fcmp.compare_glyph(None, glyph(), labels=self.labels)[0].kind, "only_b")
        self.assertEqual(fcmp.compare_glyph(None, glyph(), labels=self.labels, masters=True)[0].text, u"no layer in Regular")
        self.assertEqual(fcmp.kind_label("only_b", self.labels, masters=True), u"No layer in Regular")
        self.assertEqual(fcmp.kind_label("only_b", self.labels), u"Only in Bold")

    def test_sentence(self):
        result = fcmp.GlyphResult(u"o", u"o", fcmp.compare_glyph(glyph(), glyph(advance=520), 1, self.labels))
        self.assertEqual(result.sentence(self.labels), u"o, Regular and Bold: width 500 and 520 (+20); right side 50 and 70 (+20).")
        renamed = fcmp.GlyphResult(u"uni00E9", u"eacute", [])
        self.assertEqual(renamed.caption(), u"uni00E9 / eacute")

    def test_scaled_to_the_other_em(self):
        scaled = glyph(advance=1024, ink=(100, 900), contours=[square(0, 0, 2048)], anchors=[(u"top", 512, 2048)],
                       components=[(u"a", (1, 0, 0, 1, 2048, 0))]).scaled(1000.0 / 2048)
        self.assertEqual((scaled.advance, scaled.ink[1]), (500.0, 900 * 1000.0 / 2048))
        self.assertEqual(scaled.contours[0][2], (1000.0, 1000.0, u"on"))
        self.assertEqual(scaled.anchors, [(u"top", 250.0, 1000.0)])
        self.assertEqual(scaled.components[0][1][4], 1000.0)
        self.assertEqual(glyph(components=[(u"a.alt", IDENTITY)]).renamed({u"a.alt": u"a.ss01"}).components[0][0], u"a.ss01")

    def test_rows_worst_first(self):
        results = [fcmp.GlyphResult(u"n", u"n", [fcmp.Difference("anchors", u"", u"", 1.0)]),
                   fcmp.GlyphResult(u"o", u"o", [fcmp.Difference("outline", u"", u"", 0.01)]),
                   fcmp.GlyphResult(u"p", u"p", [fcmp.Difference("outline", u"", u"", 0.2)]),
                   fcmp.GlyphResult(u"q", None, [fcmp.Difference("only_a", u"", u"")]),
                   fcmp.GlyphResult(u"m", u"m", [fcmp.Difference("metrics", u"", u"", 0.01)])]
        self.assertEqual([r.name for r in fcmp.glyph_rows(results)], [u"q", u"p", u"o", u"m", u"n"])
        self.assertEqual([r.name for r in fcmp.glyph_rows(results, ["anchors", "metrics"])], [u"m", u"n"])
        self.assertEqual(fcmp.glyph_counts(results), {"anchors": 1, "outline": 2, "only_a": 1, "metrics": 1})

    def test_rows_by_the_kinds_shown(self):
        # A kind hidden leaves every row (an outline change moves the sidebearings too: hiding only the
        # glyphs with metrics alone hid nothing), and the rows are ranked by the kinds shown
        both = fcmp.GlyphResult(u"o", u"o", [fcmp.Difference("outline", u"", u"outline 4.1%", 0.04),
                                             fcmp.Difference("metrics", u"", u"width +20", 0.02)])
        metrics = fcmp.GlyphResult(u"m", u"m", [fcmp.Difference("metrics", u"", u"width +40", 0.04)])
        outline = fcmp.GlyphResult(u"p", u"p", [fcmp.Difference("outline", u"", u"outline 1%", 0.01)])
        results = [outline, metrics, both]
        self.assertEqual(both.short(), u"outline 4.1% \N{MIDDLE DOT} width +20")
        shown = set(["outline"])
        self.assertEqual([r.name for r in fcmp.glyph_rows(results, shown)], [u"o", u"p"])
        self.assertEqual([r.short(shown) for r in fcmp.glyph_rows(results, shown)], [u"outline 4.1%", u"outline 1%"])
        self.assertEqual([r.name for r in fcmp.glyph_rows(results, ["metrics"])], [u"m", u"o"], "by the metrics alone")
        self.assertEqual(fcmp.glyph_rows(results, []), [])
        self.assertEqual([r.name for r in fcmp.glyph_rows(results)], [u"o", u"p", u"m"])


class KerningTests(unittest.TestCase):
    def test_resolve_most_specific_first(self):
        members = {u"A": [u"A", u"Aacute"], u"O": [u"O", u"Q"]}
        values = {((u"A", True), (u"O", True)): -40, ((u"Aacute", False), (u"O", True)): -30,
                  ((u"A", True), (u"Q", False)): -20, ((u"A", False), (u"Q", False)): -10}
        self.assertEqual(fcmp.resolve_entries(values, members),
                         {(u"A", u"O"): -40, (u"A", u"Q"): -10, (u"Aacute", u"O"): -30, (u"Aacute", u"Q"): -30})

    def test_diff(self):
        a = {(u"A", u"V"): -80, (u"T", u"o"): -60, (u"L", u"T"): -50, (u"x", u"y"): -10, (u"g", u"j"): 5}
        b = {(u"A", u"V"): -70, (u"T", u"o"): -61, (u"P", u"A"): -40, (u"x", u"y"): -10, (u"uni0237", u"g"): 8}
        found = fcmp.kerning_diff(a, b, 1, {u"uni0237": u"jdotless"}, set(u"AVToLTxyPgj") | {u"jdotless"},
                                  set(u"AVToTxyPg") | {u"jdotless"})
        self.assertEqual([(d.left, d.right, d.a, d.b, d.kind) for d in found],
                         [(u"L", u"T", -50, 0, "absent"), (u"P", u"A", 0, -40, "only_b"),
                          (u"A", u"V", -80, -70, "value"), (u"jdotless", u"g", 0, 8, "only_b"),
                          (u"g", u"j", 5, 0, "absent")])
        self.assertEqual(found[2].delta, 10)
        self.assertEqual(fcmp.kern_counts(found), {"absent": 2, "only_b": 2, "value": 1})

    def test_only_in_first(self):
        found = fcmp.kerning_diff({(u"A", u"V"): -80}, {})
        self.assertEqual([(d.kind, d.delta) for d in found], [("only_a", 80)])

    def test_labels(self):
        self.assertEqual(fcmp.kern_label("only_a", (u"Regular", u"Bold")), u"Only in Regular")
        self.assertEqual(fcmp.kern_label("absent", (u"Regular", u"Bold")), u"Glyphs one font lacks")


class FeatureTests(unittest.TestCase):
    def test_code_lines(self):
        self.assertEqual(fcmp.code_lines(u"\r\n  sub a by b;  \r\n\n"), [u"  sub a by b;"])

    def test_line_diff(self):
        a = u"\n".join(u"line %d" % k for k in range(12))
        b = a.replace(u"line 6", u"line six") + u"\nline 12"
        rows = fcmp.line_diff(a, b)
        self.assertEqual(rows[0], (u"@", u""), "lines 0 to 2 left out")
        self.assertIn((u"-", u"line 6"), rows)
        self.assertIn((u"+", u"line six"), rows)
        self.assertEqual(rows[-1], (u"+", u"line 12"))
        self.assertEqual(sum(1 for sign, _ in rows if sign == u"@"), 1, "one change near the end: one gap, at the start")
        self.assertEqual(fcmp.line_diff(a, a + u"\n\n"), [], "blank lines at the end change nothing")

    def test_feature_diff(self):
        a = [(fcmp.PREFIX, u"languagesystem DFLT dflt;"), (u"liga", u"sub f i by fi;"), (u"kern", u"pos A V -80;")]
        b = [(u"liga", u"sub f i by f_i;"), (u"kern", u"pos A V -80;\n"), (u"ss01", u"sub a by a.ss01;")]
        found = fcmp.feature_diff(a, b)
        self.assertEqual([(f.tag, f.kind) for f in found],
                         [(fcmp.PREFIX, "only_a"), (u"liga", "differs"), (u"kern", "same"), (u"ss01", "only_b")])
        liga = found[1]
        self.assertEqual((liga.removed, liga.added), (1, 1))
        labels = (u"Regular", u"Bold")
        self.assertEqual(fcmp.feature_state(liga, labels), u"1 line only in Regular, 1 line only in Bold")
        self.assertEqual(fcmp.feature_state(found[3], labels), u"only in Bold")
        self.assertEqual(fcmp.feature_state(found[2], labels), u"alike")

    def test_classes_text(self):
        self.assertEqual(fcmp.classes_text([(u"lc", [u"a", u"b"]), (u"UC", [u"A"])]), u"@UC = [A];\n@lc = [a b];")

    def test_diff_html(self):
        html = fcmp.diff_html([(u"@", u""), (u"-", u"sub a by <b>;"), (u"+", u"sub a by c;"), (u" ", u"}")],
                              (u"A & B", u"C"), (255, 255, 255), (0, 0, 0))
        self.assertIn(u"sub a by &lt;b&gt;;", html)
        self.assertIn(u"A &amp; B", html)
        self.assertIn(fcmp.blend((255, 255, 255), (222, 64, 52), 0.28), html)
        self.assertIn(fcmp.blend((255, 255, 255), (64, 168, 92), 0.28), html)
        self.assertEqual(fcmp.blend((0, 0, 0), (200, 100, 50), 0.5), u"#643219")


# ---------------------------------------------------------------------------
# The dialog, run on fakes: any Qt call is accepted and does nothing; the fonts are small fakes of
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


class FakeTransform(object):
    def __init__(self, dx=0.0, dy=0.0):
        self._dx, self._dy = dx, dy

    def m11(self):
        return 1.0

    m22 = m11

    def m12(self):
        return 0.0

    m21 = m12

    def dx(self):
        return self._dx

    def dy(self):
        return self._dy


class FakeShape(object):
    def __init__(self, contours=(), component=None, dx=0.0):
        self.contours = [FakeContour(c) for c in contours]
        self.isComponent = component is not None
        self.shapeData = Anything()
        self.shapeData.componentGlyph = component
        self.transform = FakeTransform(dx)


class FakePoint(object):
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class FakeAnchor(object):
    def __init__(self, name, x, y):
        self.name, self.point = name, FakePoint(x, y)


class FakeLayer(object):
    def __init__(self, shapes, anchors=(), advance=500):
        self.shapes, self.anchors, self.advanceWidth = shapes, [FakeAnchor(*a) for a in anchors], advance
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


class FakeKerning(object):
    def __init__(self, pairs):
        self.pairs = pairs
        self.groups = {}

    def getPlainPairsDict(self):
        return dict(self.pairs)

    def items(self):
        return []


class FakeFeatures(object):
    def __init__(self, features, prefix=u""):
        self.features, self.prefix = features, prefix

    def keys(self):
        return [tag for tag, _ in self.features]

    def get_feature(self, tag):
        return dict(self.features)[tag]

    def get_prefix(self):
        return self.prefix


def box(top, right=400):
    return [(0, 0), (right, 0), (right, top), (0, top)]


class FakePackage(object):
    def __init__(self, name, glyphs, kerning, features, masters=(u"Regular",), upm=1000):
        self.by_name = dict((g.name, g) for g in glyphs)
        self.fgPackage = Anything()
        self.fgPackage.glyphs = [g.fgGlyph for g in glyphs]
        self.fgPackage.features = FakeFeatures(features)
        self.kernings = kerning
        self.isNull, self.glyphsCount, self.upm, self.tfn, self.path = False, len(glyphs), upm, name, name + u".vfc"
        self.master, self.masters = masters[0], list(masters)

    def findName(self, name):
        return self.by_name.get(name)

    def findUnicode(self, code):
        return next((g for g in self.by_name.values() if g.fgGlyph.unicode == code), None)

    def kerning(self, master):
        return FakeKerning(self.kernings.get(master, {}))

    def getAllGroups(self):
        return [(False, u"lc", 1, 0, [u"n", u"o"])]

    def currentHistoryState(self):
        return 1


def one_master(layer):
    return {u"Regular": layer}


def first_font():
    glyphs = [FakeGlyph(u"H", 0x48, one_master(FakeLayer([FakeShape([box(700)])]))),
              FakeGlyph(u"o", 0x6F, one_master(FakeLayer([FakeShape([box(500)])]))),
              FakeGlyph(u"n", 0x6E, one_master(FakeLayer([FakeShape([box(500)])], [(u"top", 200, 500)]))),
              FakeGlyph(u"a", 0x61, one_master(FakeLayer([FakeShape([box(500)])]))),
              FakeGlyph(u"uni0101", 0x101, one_master(FakeLayer([FakeShape([box(600)])]))),
              FakeGlyph(u"eacute", 0xE9, one_master(FakeLayer([FakeShape(component=u"e"),
                                                                 FakeShape(component=u"acutecomb", dx=100)])))]
    return FakePackage(u"Fake A", glyphs, {u"Regular": {(u"H", u"o"): -20, (u"o", u"n"): -10, (u"a", u"H"): -5}},
                       [(u"liga", u"sub f i by fi;"), (u"kern", u"pos H o -20;")])


def second_font():
    moved = [(0, 0), (400, 0), (400, 510), (0, 500)]
    glyphs = [FakeGlyph(u"H", 0x48, one_master(FakeLayer([FakeShape([box(700)])]))),
              FakeGlyph(u"o", 0x6F, one_master(FakeLayer([FakeShape([moved])]))),
              FakeGlyph(u"n", 0x6E, one_master(FakeLayer([FakeShape([box(500)])], [(u"top", 200, 520)], advance=520))),
              FakeGlyph(u"b", 0x62, one_master(FakeLayer([FakeShape([box(700)])]))),
              FakeGlyph(u"amacron", 0x101, one_master(FakeLayer([FakeShape([box(600)])]))),
              FakeGlyph(u"eacute", 0xE9, one_master(FakeLayer([FakeShape(component=u"e"),
                                                                 FakeShape(component=u"acutecomb", dx=120)])))]
    return FakePackage(u"Fake B", glyphs, {u"Regular": {(u"H", u"o"): -30, (u"n", u"o"): 15}},
                       [(u"liga", u"sub f i by f_i;"), (u"ss01", u"sub a by a.ss01;")])


def two_master_font():
    glyphs = [FakeGlyph(u"H", 0x48, {u"Regular": FakeLayer([FakeShape([box(700)])]),
                                     u"Bold": FakeLayer([FakeShape([box(700, 500)])], advance=600)}),
              FakeGlyph(u"o", 0x6F, {u"Regular": FakeLayer([FakeShape([box(500)])])})]
    return FakePackage(u"Fake", glyphs, {u"Regular": {(u"H", u"o"): -20}, u"Bold": {(u"H", u"o"): -20}},
                       [(u"liga", u"sub f i by fi;")], masters=(u"Regular", u"Bold"))


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        cls.saved = dict((name, sys.modules.get(name)) for name in ("PythonQt", "fontlab", fcmp.AUTO_KERNING_MODULE))
        qt = Anything()
        qt.QtCore, qt.QtGui = _FakeQtModule(), _FakeQtModule()
        cls.workspace = workspace = Anything()
        fontlab = Anything()
        fontlab.flWorkspace = Anything()
        fontlab.flWorkspace.instance = lambda: workspace
        fontlab.flPackage = lambda item: item
        sys.modules["PythonQt"], sys.modules["fontlab"] = qt, fontlab
        cls.ak_layer_path, cls.ak_stamp = ak.layer_path, getattr(ak, "_freelab_stamp", "unset")
        ak.layer_path = FakePath
        ak._freelab_stamp = None  # (load_auto_kerning finds no file beside the script: the one loaded here is kept)
        sys.modules[fcmp.AUTO_KERNING_MODULE] = ak
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

    def dialog(self, packages):
        self.workspace.packages = lambda: list(packages)
        self.workspace.currentPackage = packages[0]
        dialog = fcmp.CompareDialog()
        self.assertIsNone(dialog.failed, dialog.failed)
        dialog.log.add = lambda text, level="info": self.fail(text) if level == "error" else None
        dialog.threshold.value = 1
        for _, chip in dialog.glyph_chips + dialog.kern_chips:
            chip.checked = True
        return dialog

    def test_two_fonts(self):
        dialog = self.dialog([first_font(), second_font()])
        self.assertEqual(len(dialog.choices), 2)
        dialog.choice_a.currentIndex, dialog.choice_b.currentIndex = 0, 1
        dialog.compare()
        found = dict((r.name, sorted(r.kinds())) for r in dialog.results)
        self.assertEqual(found, {u"o": ["outline"], u"n": ["anchors", "metrics"], u"a": ["only_a"], u"b": ["only_b"],
                                 u"uni0101": ["codes"], u"eacute": ["components"]})
        self.assertEqual([r.name for r in dialog.glyph_names][:2], [u"a", u"b"], "glyphs only in one font first")
        self.assertEqual(dialog.labels(), (u"Fake A", u"Fake B"))
        kerning = sorted((d.left, d.right, d.a, d.b, d.kind) for d in dialog.kern_rows)
        self.assertEqual(kerning, [(u"H", u"o", -20, -30, "value"), (u"a", u"H", -5, 0, "absent"),
                                   (u"n", u"o", 0, 15, "only_b"), (u"o", u"n", -10, 0, "only_a")])
        self.assertEqual([(f.tag, f.kind) for f in dialog.feature_rows],
                         [(u"liga", "differs"), (u"kern", "only_a"), (u"ss01", "only_b"), (fcmp.CLASSES, "same")])
        dialog.draw_comparison()
        dialog.draw_pair()
        dialog.feature_selected()
        self.assertEqual(dialog.row_glyph(None), [])
        chips = dict(dialog.glyph_chips)
        chips["metrics"].checked = False
        dialog.fill_glyphs()
        self.assertIn(u"n", [r.name for r in dialog.glyph_names], "its anchors still shown")
        chips["anchors"].checked = False
        dialog.fill_glyphs()
        self.assertNotIn(u"n", [r.name for r in dialog.glyph_names], "nothing of it shown")
        self.assertFalse(hasattr(dialog, "glyph_window_button") or hasattr(dialog, "show_in_glyph_window"),
                         "no Glyph window: FontLab opens it on its current font only")
        self.assertEqual(dialog.selected_glyphs(), [])
        dialog.history_moved()

    def test_two_masters(self):
        dialog = self.dialog([two_master_font()])
        self.assertEqual(len(dialog.choices), 2)
        dialog.choice_a.currentIndex, dialog.choice_b.currentIndex = 0, 1
        dialog.compare()
        self.assertTrue(dialog.masters_mode)
        found = dict((r.name, [d.text for d in r.differences]) for r in dialog.results)
        self.assertEqual(found, {u"H": [u"the shapes differ by 20% of the ink; nodes moved up to 100 units (contour 1)",
                                        u"width 500 and 600 (+100)"],
                                 u"o": [u"no layer in Bold"]})
        self.assertEqual(dialog.kern_rows, [])
        self.assertEqual(dialog.feature_rows, [], "one font: its features are shared")
        self.assertEqual(dialog.first_name(dialog.results[-1]), u"o")

    def test_rows_listed_at_most(self):
        saved = fcmp.ROWS_SHOWN
        fcmp.ROWS_SHOWN = 2
        try:
            dialog = self.dialog([first_font(), second_font()])
            dialog.choice_a.currentIndex, dialog.choice_b.currentIndex = 0, 1
            dialog.compare()
        finally:
            fcmp.ROWS_SHOWN = saved
        self.assertEqual(len(dialog.results), 6)
        self.assertEqual([r.name for r in dialog.glyph_names], [u"a", u"b"], "the worst listed")
        self.assertEqual(len(dialog.kern_shown), 2)

    def test_open_a_font(self):
        first, second, third = first_font(), second_font(), two_master_font()
        packages = [first, second]
        dialog = self.dialog(packages)
        self.workspace.packages = lambda: list(packages)  # (a font opened later is listed)
        said, chosen, requested, picked = [], [], [], []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        dialog.choice_b.setCurrentIndex = chosen.append
        gui = sys.modules["PythonQt"].QtGui
        gui.classes["QFileDialog"] = type("QFileDialog", (), {"getOpenFileName": staticmethod(lambda *args: picked[-1])})
        fontlab = sys.modules["fontlab"]
        fontlab.flItems = type("Items", (), {"requestLoadingFont": staticmethod(requested.append)})
        try:
            picked.append(second.path)
            dialog.open_font()
            self.assertEqual(requested, [], "open already: not opened again")
            self.assertEqual(chosen[-1], 1)
            self.assertIn(u"open already", said[-1][1])
            done = lambda: len([text for level, text in said if level == "done"])
            picked.append(u"other.vfc")
            dialog.open_font()
            picked.append(third.path)
            dialog.open_font()
            self.assertEqual(requested, [u"other.vfc", third.path])
            dialog.look_for_opened()
            self.assertEqual((dialog.open_tries, done()), (1, 1), "not in yet: looked for again")
            packages.append(third)
            dialog.look_for_opened()
            self.assertEqual(said[-1][0], "done")
            self.assertIn(u"Opened", said[-1][1])
            self.assertEqual(done(), 2)
            self.assertIs(dialog.fonts[dialog.choices[chosen[-1]][0]], third, "the font just opened")
            dialog.look_for_opened()
            self.assertEqual(done(), 2, "chosen once: the earlier request's poll is gone")
        finally:
            del gui.classes["QFileDialog"]
            del fontlab.flItems

    def test_a_color_glyph_at_its_font_scale(self):
        a, b = first_font(), second_font()
        b.upm = 2000
        dialog = self.dialog([a, b])
        dialog.log.add = lambda text, level="info": None
        dialog.choice_a.currentIndex, dialog.choice_b.currentIndex = 0, 1
        dialog.compare()
        dialog.selected_result = lambda: next(r for r in dialog.results if r.a == u"o" and r.b == u"o")

        class Transform(object):
            def scale(self, x, y):
                self.factor = x

            def map(self, path):
                return (self.factor, path)

        gui, drawn = sys.modules["PythonQt"].QtGui, []
        saved = fcmp.comparison_pixmap, self.ak.layer_parts
        gui.classes["QTransform"] = Transform
        fcmp.comparison_pixmap = lambda width, height, first, second, *rest: drawn.append((first, second))
        self.ak.layer_parts = lambda layer: [(u"part", u"red")]
        try:
            dialog.draw_comparison()
        finally:
            del gui.classes["QTransform"]
            fcmp.comparison_pixmap, self.ak.layer_parts = saved
        self.assertEqual(drawn[0][0][3], [(u"part", u"red")])
        self.assertEqual(drawn[0][1][3], [((0.5, u"part"), u"red")], "scaled as the second font's path")

    def test_one_font_one_master(self):
        dialog = self.dialog([first_font()])
        self.assertEqual(len(dialog.choices), 1)
        dialog.compare()
        self.assertIsNone(dialog.sides)


if __name__ == "__main__":
    unittest.main()
