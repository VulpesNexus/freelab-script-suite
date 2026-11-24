"""Tests of FreeLab's Font Compare: glyphs matched, outlines, metrics, components, anchors, kerning,
and features compared. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import io
import math
import os
import shutil
import sys
import tempfile
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
        pairs, only_a, only_b = fcmp.match_glyphs(b, a)
        self.assertEqual(pairs, [], "the fonts swapped: no guess either")
        self.assertEqual((only_a, only_b), ([u"A.one", u"A.two"], [u"uni0041"]))


class LabelTests(unittest.TestCase):
    def test_masters_of_one_font(self):
        self.assertEqual(fcmp.side_labels((u"f.vfc", u"Sans", u"Regular", 2), (u"f.vfc", u"Sans", u"Bold", 2)),
                         (u"Regular", u"Bold"))

    def test_two_fonts(self):
        self.assertEqual(fcmp.side_labels((u"a.vfc", u"Sans", u"Regular", 1), (u"b.vfc", u"Serif", u"Regular", 1)),
                         (u"Sans", u"Serif"))
        self.assertEqual(fcmp.side_labels((u"a.vfc", u"Sans", u"Bold", 2), (u"b.vfc", u"Serif", u"Regular", 1)),
                         (u"Sans (Bold)", u"Serif"), "a master in parentheses, not after a dot")

    def test_two_versions_of_one_font(self):
        self.assertEqual(fcmp.side_labels((u"old/Sans.vfc", u"Sans", u"R", 1), (u"new/Sans-2.vfc", u"Sans", u"R", 1)),
                         (u"Sans.vfc", u"Sans-2.vfc"))
        self.assertEqual(fcmp.side_labels((u"old/Sans.vfc", u"Sans", u"R", 1), (u"new/Sans.vfc", u"Sans", u"R", 1)),
                         (u"Sans (first)", u"Sans (second)"))
        self.assertEqual(fcmp.side_labels((u"old/Sans.vfc", u"Sans", u"Bold", 2), (u"new/Sans.vfc", u"Sans", u"Bold", 2)),
                         (u"Sans (Bold, first)", u"Sans (Bold, second)"), "one pair of parentheses")

    def test_two_unsaved_fonts_of_one_name(self):
        # Both go by "unsaved:Sans": the caller, which knows them by FontLab's numbers, says they are two
        a, b = (u"unsaved:Sans", u"Sans", u"Regular", 1), (u"unsaved:Sans", u"Sans", u"Regular", 1)
        self.assertEqual(fcmp.side_labels(a, b), (u"first", u"second"))
        self.assertEqual(fcmp.side_labels(a, b, False), (u"Sans (first)", u"Sans (second)"))
        self.assertEqual(fcmp.side_labels((u"a.vfc", u"Sans", u"Regular", 2), (u"a.vfc", u"Sans", u"Bold", 2), True),
                         (u"Regular", u"Bold"))


class ChoiceTests(unittest.TestCase):
    """The two dropdowns' rows, and the line saying what is missing."""

    ELLIPSIS = u"\N{HORIZONTAL ELLIPSIS}"

    def rows(self, fonts, own):
        return [(kind, font, master, text) for kind, font, master, text in fcmp.second_entries(fonts, own)]

    def test_first_lists_the_window_font_masters(self):
        self.assertEqual(fcmp.first_entries((7, u"Sans", [u"Regular"], u"Sans.vfc")), [(7, u"Regular", u"Sans")])
        self.assertEqual(fcmp.first_entries((7, u"Sans", [u"Regular", u"Bold"], u"")),
                         [(7, u"Regular", u"Sans (Regular)"), (7, u"Bold", u"Sans (Bold)")])

    def test_one_font_one_master_offers_only_a_file(self):
        rows = self.rows([(7, u"Sans", [u"Regular"], u"Sans.vfc")], 7)
        self.assertEqual(rows, [("none", None, None, u"Choose a font" + self.ELLIPSIS), ("separator", None, None, u""),
                                ("open", None, None, u"Open a font" + self.ELLIPSIS)],
                         "a font is not compared with itself")

    def test_installed_fonts_come_after_the_file_row(self):
        rows = fcmp.second_entries([(7, u"Sans", [u"Regular"], u"Sans.vfc")], 7, [(u"b.ttf", u"Beta"), (u"a.otf", u"alpha")])
        self.assertEqual(rows[1:], [("separator", None, None, u""), ("open", None, None, u"Open a font" + self.ELLIPSIS),
                                    ("separator", None, None, u""), ("installed", u"a.otf", None, u"alpha"),
                                    ("installed", u"b.ttf", None, u"Beta")], "A to Z, its file's path for an id")

    def test_installed_fonts_of_one_name_show_their_files(self):
        # (Noto Sans JP listed twice: Windows' variable .ttf and the user's static .otf)
        system = os.path.join(u"C:", os.sep, u"Windows", u"Fonts")
        mine = os.path.join(u"C:", os.sep, u"Users", u"me", u"AppData", u"Local", u"Microsoft", u"Windows", u"Fonts")
        found = [(os.path.join(system, u"NotoSansJP-VF.ttf"), u"Noto Sans JP"),
                 (os.path.join(mine, u"NotoSansJP-Regular.otf"), u"Noto Sans JP"),
                 (os.path.join(system, u"Cardo.ttf"), u"Cardo"),
                 (os.path.join(system, u"Twin.ttf"), u"Twin"), (os.path.join(mine, u"Twin.ttf"), u"Twin")]
        real = fcmp.user_font_folder
        fcmp.user_font_folder = lambda: mine
        self.addCleanup(setattr, fcmp, "user_font_folder", real)
        texts = [row[3] for row in fcmp.installed_entries(found)[1:]]
        self.assertEqual(sorted(texts), sorted([u"Cardo", u"Noto Sans JP (NotoSansJP-Regular.otf)",
                                                u"Noto Sans JP (NotoSansJP-VF.ttf)", u"Twin (Twin.ttf)",
                                                u"Twin (Twin.ttf, yours)"]),
                         "a lone name stays bare; the user's copy of a shared file is marked")

    def test_the_open_list_leaves_out_the_placeholder(self):
        # (the owner's screenshot 98: "Choose a font..." in the box and again as the list's first row)
        alone = fcmp.second_entries([(7, u"Sans", [u"Regular"], u"Sans.vfc")], 7, [(u"a.otf", u"alpha")])
        self.assertEqual(fcmp.popup_rows_hidden(alone), set([0, 1]), "and the separator with nothing above it")
        others = fcmp.second_entries([(7, u"Sans", [u"Regular"], u""), (8, u"Serif", [u"Regular"], u"")], 7)
        self.assertEqual(fcmp.popup_rows_hidden(others), set([0]), "a separator under another font stays")

        class View(object):
            hidden = {}

            def setRowHidden(self, row, on):
                View.hidden[row] = on

        class Box(object):
            def setItemData(self, *args):
                pass

            def view(self):
                return View()

        class Window(object):
            placeholder_unpickable = fcmp.CompareDialog.__dict__["placeholder_unpickable"]  # (a function in 2.7 too)

        window = Window()
        window.second_rows, window.choice_b = alone, Box()
        saved = fcmp._qt
        fcmp._qt = lambda: (type("Core", (object,), {"Qt": type("Qt", (object,), {"UserRole": 32})}), None)
        try:
            window.placeholder_unpickable()
        finally:
            fcmp._qt = saved
        self.assertEqual(View.hidden, {0: True, 1: True, 2: False, 3: False, 4: False})

    def test_an_installed_fonts_name_comes_from_its_name_table(self):
        import struct

        def font(records, collection=False):
            strings, entries = b"", []
            for platform, encoding, language, name_id, text in records:
                data = text.encode("utf-16-be" if platform == 3 else "latin-1")
                entries.append(struct.pack(">HHHHHH", platform, encoding, language, name_id, len(data), len(strings)))
                strings += data
            table = struct.pack(">HHH", 0, len(records), 6 + 12 * len(records)) + b"".join(entries) + strings
            start = 16 if collection else 0  # (a collection's header: its tag, version, count, and first offset)
            head = struct.pack(">4sHHHH", b"\x00\x01\x00\x00", 1, 0, 0, 0) + struct.pack(">4sIII", b"name", 0,
                                                                                         start + 28, len(table))
            whole = (struct.pack(">4sIII", b"ttcf", 0x10000, 1, start) if collection else b"") + head + table
            return lambda offset, length: whole[offset:offset + length]

        self.assertEqual(fcmp.name_table_name(font([(1, 0, 0, 4, u"Mac Name"), (3, 1, 0x40C, 4, u"Nom"),
                                                    (3, 1, 0x409, 4, u"Fake Sans Bold")])), u"Fake Sans Bold")
        self.assertEqual(fcmp.name_table_name(font([(3, 1, 0x409, 1, u"Fake"), (3, 1, 0x409, 2, u"Italic")])),
                         u"Fake Italic", "family and style without a full name")
        self.assertEqual(fcmp.name_table_name(font([(3, 1, 0x409, 4, u"First")], collection=True)), u"First")
        self.assertIsNone(fcmp.name_table_name(lambda offset, length: b"\x00" * length), "no name table: the file's name")
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        with open(os.path.join(folder, u"x.ttf"), "wb") as handle:
            handle.write(b"not a font")
        with open(os.path.join(folder, u"notes.txt"), "wb") as handle:
            handle.write(b"")
        self.assertEqual(fcmp.installed_fonts([folder]), [(os.path.join(folder, u"x.ttf"), u"x")])

    def test_installed_fonts_give_the_same_list_until_a_folder_changes(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        with open(os.path.join(folder, u"x.ttf"), "wb") as handle:
            handle.write(b"not a font")
        found = fcmp.installed_fonts([folder])
        self.assertIs(fcmp.installed_fonts([folder]), found, "read once: the same list, so a change shows")
        with open(os.path.join(folder, u"y.ttf"), "wb") as handle:
            handle.write(b"not a font")
        os.utime(folder, (os.path.getmtime(folder) + 5,) * 2)  # (a file added: the folder's stamp moves)
        again = fcmp.installed_fonts([folder])
        self.assertIsNot(again, found)
        self.assertEqual([name for _, name in again], [u"x", u"y"])

    def test_one_font_with_masters_offers_its_masters(self):
        rows = self.rows([(7, u"Sans", [u"Regular", u"Bold"], u"Sans.vfc")], 7)
        self.assertEqual([row[1:] for row in rows if row[0] == "font"],
                         [(7, u"Regular", u"Sans (Regular)"), (7, u"Bold", u"Sans (Bold)")])

    def test_other_fonts_first_then_the_own_masters(self):
        fonts = [(7, u"Sans", [u"Regular", u"Bold"], u"Sans.vfc"), (9, u"Serif", [u"Regular"], u"Serif.vfc"),
                 (12, u"Mono", [u"Light", u"Black"], u"")]
        rows = self.rows(fonts, 7)
        self.assertEqual([row[0] for row in rows], ["none", "font", "font", "font", "font", "font", "separator", "open"])
        self.assertEqual([row[3] for row in rows[1:6]],
                         [u"Serif", u"Mono (Light)", u"Mono (Black)", u"Sans (Regular)", u"Sans (Bold)"])
        self.assertEqual(rows[1][1:3], (9, u"Regular"), "the other open font is the first to choose")

    def test_fonts_of_one_name_told_apart_by_file(self):
        fonts = [(7, u"Sans", [u"Regular"], u"Sans.vfc"), (9, u"Sans", [u"Regular"], u"Sans-2.vfc"),
                 (12, u"Sans", [u"Regular", u"Bold"], u"")]
        texts = [row[3] for row in self.rows(fonts, 7) if row[0] == "font"]
        self.assertEqual(texts, [u"Sans (Sans-2.vfc)", u"Sans (Regular)", u"Sans (Bold)"])
        self.assertEqual([row[1] for row in self.rows(fonts, 7) if row[0] == "font"], [9, 12, 12], "by number, not by name")

    def test_no_dash_or_dot_between_data(self):
        # The owner's rule: data beside data goes in parentheses, not after an interpunct or an em dash
        import io
        with io.open(fcmp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read()
        escaped = [u" \\" + code + u" " for code in (u"N{EM DASH}", u"N{MIDDLE DOT}", u"u2014", u"u00b7", u"xb7")]
        for mark in escaped + [u" \N{EM DASH} ", u" \N{MIDDLE DOT} "]:
            self.assertNotIn(mark, source)
        self.assertEqual(fcmp.choice_text(u"Sans", u"Bold", 1), u"Sans")
        self.assertEqual(fcmp.choice_text(u"Sans", u"Bold", 2, u"Sans-2.vfc"), u"Sans (Bold, Sans-2.vfc)")

    def test_what_is_missing(self):
        line = fcmp.missing_line
        self.assertIn(u"No font is open", line(None, 0, 0, False))
        self.assertIn(u"hooks to the next font you open", line(None, 0, 0, False), "as the shared no-font line")
        one = line(u"<b>Sans</b>", 0, 1, False)
        self.assertIn(u"Only <b>Sans</b> is open, with one master.", one)
        self.assertIn(u"<i>Open a font" + self.ELLIPSIS + u"</i>", one)
        self.assertIn(u"the master to compare with", line(u"<b>Sans</b>", 0, 2, False))
        # Owner's image 257: a font picked in "with" is compared at once (no click on Compare to ask for)
        self.assertEqual(line(u"<b>Sans</b>", 1, 1, False),
                         u"Choose in <i>with</i> the font to compare <b>Sans</b> with: it is compared at once.")
        self.assertEqual(line(u"<b>Sans</b>", 3, 2, False), line(u"<b>Sans</b>", 1, 1, False))
        self.assertEqual(line(u"<b>Sans</b>", 1, 1, True), u"", "both sides chosen: nothing is missing")
        self.assertIn(u"the same master", line(u"<b>Sans</b>", 0, 2, True, True))


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
        two = glyph(u"colon", components=[(u"dot", IDENTITY), (u"dot", (1, 0, 0, 1, 0, 400))])
        one = glyph(u"colon", components=[(u"dot", IDENTITY)])
        self.assertEqual(fcmp.compare_glyph(two, one, 1, self.labels)[0].text, u"component dot 2 times in Regular, 1 in Bold")
        self.assertEqual(fcmp.compare_glyph(glyph(u"colon"), two, 1, self.labels)[0].text,
                         u"component dot only in Bold (2 times)")
        one = glyph(u"eacute", components=[(u"e", IDENTITY), (u"acutecomb", (1, 0, 0, 1, 100, 0))])
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
        self.assertEqual(both.short(), u"outline 4.1%; width +20", "no interpunct between a list cell's parts")
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

    def test_the_table_s_numbers_align_right_and_the_pairs_take_the_room(self):
        # (live, 2026-11-16: its values sat at the left, unlike every other list's numbers)
        with io.open(fcmp.__file__, encoding="utf-8") as handle:
            source = handle.read()
        fill = source.split(u'tree.setHeaderLabels([u"Pair", labels[0], labels[1], u"Difference"])')[1].split(u"\n    def ")[0]
        self.assertIn(u"self.ak.align_numbers(tree, (1, 2, 3))", fill)
        self.assertIn(u"self.ak.set_stretch(tree, 0)", fill)
        sizing = source.split(u"    def fit_columns(self, tree, widths):")[1].split(u"\n    def ")[0]
        self.assertIn(u"self.ak.fit_rows(tree, range(len(widths)), most=list(widths))", sizing)
        self.assertNotIn(u"resizeColumnToContents", sizing, "measured alike in either theme")

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


class FakeCombo(Anything):
    """A dropdown that keeps its rows and its current one as Qt's does: a separator is a row too (None
    here), the first row added becomes the current one, and a change of the current row is signaled.
    pick() is the user choosing a row (activated, which the code's own changes do not send)."""

    def __init__(self, *args, **kwargs):
        self.rows, self.currentIndex, self.slots, self.watchers, self.cleared = [], -1, {}, [], 0

    @property
    def count(self):
        return len(self.rows)

    def addItem(self, text):
        self.rows.append(text)
        if self.currentIndex < 0:
            self.setCurrentIndex(0)

    def insertSeparator(self, index):
        self.rows.insert(index, None)

    def clear(self):
        self.rows, self.cleared = [], self.cleared + 1
        self.setCurrentIndex(-1)

    def setCurrentIndex(self, index):
        if index != self.currentIndex:
            self.currentIndex = index
            for slot in self.slots.get("currentIndexChanged(int)", []):
                slot(index)

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)

    def installEventFilter(self, watcher):
        self.watchers.append(watcher)

    def pick(self, index):
        self.setCurrentIndex(index)
        for slot in self.slots.get("activated(int)", []):
            slot(index)

    def setProperty(self, name, value):
        self.__dict__.setdefault("properties", {})[name] = value

    def property(self, name):
        return self.__dict__.get("properties", {}).get(name)


class FakeSpin(Anything):
    """A spin box that keeps its value and its suffix, and signals a change of value."""

    def __init__(self, *args, **kwargs):
        self.value, self.suffix, self.slots = 0, u"", {}

    def inherits(self, name):
        return name == "QSpinBox"

    def setValue(self, value):
        self.value = value
        for slot in self.slots.get("valueChanged(int)", []):
            slot(value)

    def setSuffix(self, text):
        self.suffix = text

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)


class FakeButton(Anything):
    """A button that keeps whether it is enabled, and whether it is checked (a chip)."""

    def __init__(self, *args, **kwargs):
        self.enabled = True

    def setEnabled(self, on):
        self.enabled = on

    def setChecked(self, on):
        self.checked = on

    def setWhatsThis(self, text):
        self.whats = text


class FakeEvent(object):
    def __init__(self, kind):
        self.kind = kind

    def type(self):
        return self.kind


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
    numbers = [100]  # FontLab's number of each open font (fgPackage.id): what tells two fonts of one name apart

    def __init__(self, name, glyphs, kerning, features, masters=(u"Regular",), upm=1000):
        self.by_name = dict((g.name, g) for g in glyphs)
        self.fgPackage = Anything()
        FakePackage.numbers[0] += 1
        self.fgPackage.id = FakePackage.numbers[0]
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
        qt.QtGui.classes.update({"QComboBox": FakeCombo, "QSpinBox": FakeSpin, "QPushButton": FakeButton,
                                 "QToolButton": FakeButton})
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
        cls.installed_fonts, cls.installed = fcmp.installed_fonts, []
        fcmp.installed_fonts = lambda folders=None: list(cls.installed)  # (never this machine's fonts)

    @classmethod
    def tearDownClass(cls):
        fcmp.installed_fonts = cls.installed_fonts
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

    def setUp(self):
        # The font kept for "with" for the session (on sys): each test starts without one, and leaves none
        held = getattr(sys, fcmp.REMEMBERED, None)
        if hasattr(sys, fcmp.REMEMBERED):
            delattr(sys, fcmp.REMEMBERED)

        def restore():
            if hasattr(sys, fcmp.REMEMBERED):
                delattr(sys, fcmp.REMEMBERED)
            if held is not None:
                setattr(sys, fcmp.REMEMBERED, held)
        self.addCleanup(restore)

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

    ELLIPSIS = u"\N{HORIZONTAL ELLIPSIS}"

    def said(self, dialog):
        """The top line's texts from now on."""
        texts = []
        dialog.font_label.setText = texts.append
        return texts

    def test_second_side_starts_empty(self):
        first, second = first_font(), second_font()
        dialog = self.dialog([first, second])
        self.assertEqual(dialog.choice_a.rows, [u"Fake A"], "the first side: this window's font")
        self.assertEqual(dialog.choice_b.rows, [u"Choose a font" + self.ELLIPSIS, u"Fake B", None,
                                                u"Open a font" + self.ELLIPSIS])
        self.assertEqual(dialog.choice_b.currentIndex, 0, "two fonts open: still the user's to choose")
        self.assertIsNone(dialog.second_key)
        self.assertFalse(dialog.compare_button.enabled, "grayed until both sides are chosen")
        self.assertIn(u"Choose in <i>with</i> the font to compare <b>Fake A</b> with", dialog.missing())
        dialog.compare()
        self.assertIsNone(dialog.sides, "nothing compared")
        texts = self.said(dialog)
        dialog.choice_b.pick(1)
        self.assertEqual(dialog.second_key, (second.fgPackage.id, u"Regular"))
        self.assertTrue(dialog.compare_button.enabled)
        self.assertEqual(dialog.missing(), u"")
        # Owner's image 257: a font picked in "with" is compared at once, no click on Compare
        self.assertIsNotNone(dialog.sides, "compared on the pick")
        self.assertTrue(texts[-1].startswith(u"Compared <b>Fake A</b> with <b>Fake B</b>"), texts[-1])
        self.assertFalse(dialog.swap_button.enabled, "two fonts: the first stays this window's")
        dialog.choice_b.pick(0)
        self.assertEqual(dialog.second_key, (second.fgPackage.id, u"Regular"),
                         "the placeholder is no choice (its row is grayed out): the font chosen stays")
        self.assertEqual(dialog.choice_b.currentIndex, 1)
        self.assertTrue(dialog.compare_button.enabled)

    def test_a_glyph_not_read_is_named_as_a_link_to_it(self):
        # (the owner's request of 2026-11-24: a glyph's name in a log line in italics, a link that opens it)
        dialog = self.dialog([first_font(), second_font()])
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        real = dialog.read_glyph

        def read_glyph(side, name, *rest):
            if name == u"o":
                raise RuntimeError("unreadable")
            return real(side, name, *rest)
        dialog.read_glyph = read_glyph
        dialog.choice_b.pick(1)
        self.assertIn((u"warning", u"Could not read <b>1 glyph</b>: %s." % self.ak.glyph_name_link(u"o")), logged)

    def test_a_right_to_left_pair_is_drawn_as_on_screen(self):
        # FontLab keeps typed yod then bet as the key (yod, bet): bet stands at the left. The Latin key
        # of the same font stays as it is: each pair by its own glyphs
        def hebrew_font(name, value):
            glyphs = [FakeGlyph(u"yod", 0x05D9, one_master(FakeLayer([FakeShape([box(500)])]))),
                      FakeGlyph(u"bet", 0x05D1, one_master(FakeLayer([FakeShape([box(500)])]))),
                      FakeGlyph(u"H", 0x48, one_master(FakeLayer([FakeShape([box(700)])]))),
                      FakeGlyph(u"o", 0x6F, one_master(FakeLayer([FakeShape([box(500)])])))]
            return FakePackage(name, glyphs, {u"Regular": {(u"yod", u"bet"): value, (u"H", u"o"): value}}, [])

        dialog = self.dialog([hebrew_font(u"Fake A", -64), hebrew_font(u"Fake B", -40)])
        dialog.choice_b.pick(1)
        dialog.compare()
        drawn = []
        saved = self.ak.pair_pixmap
        self.ak.pair_pixmap = lambda package, master, left, right, *rest: drawn.append((left, right)) or Anything()
        try:
            for d in list(dialog.kern_shown):
                dialog.selected_pair = lambda d=d: d
                del drawn[:]
                dialog.draw_pair()
                expected = (u"bet", u"yod") if d.left == u"yod" else (u"H", u"o")
                self.assertEqual(drawn, [expected, expected], u"%s %s" % (d.left, d.right))
        finally:
            self.ak.pair_pixmap = saved
        self.assertEqual(sorted((d.left, d.right) for d in dialog.kern_shown), [(u"H", u"o"), (u"yod", u"bet")],
                         "listed by FontLab's keys")

    def test_two_fonts(self):
        dialog = self.dialog([first_font(), second_font()])
        dialog.choice_b.pick(1)
        dialog.compare()
        found = dict((r.name, sorted(r.kinds())) for r in dialog.results)
        self.assertEqual(found, {u"o": ["outline"], u"n": ["anchors", "metrics"], u"a": ["only_a"], u"b": ["only_b"],
                                 u"uni0101": ["codes"], u"eacute": ["components"]})
        # The owner: the glyphs only in one font "should probably be unchecked by default so it truly focuses
        # on comparing what is available in both fonts"
        chips = dict(dialog.glyph_chips)
        self.assertEqual(sorted(kind for kind, chip in dialog.glyph_chips if chip.checked),
                         ["anchors", "codes", "components", "metrics", "outline"])
        self.assertNotIn(u"a", [r.name for r in dialog.glyph_names])
        self.assertEqual([r.name for r in dialog.glyph_names][0], u"o", "the worst of what both have first")
        self.assertNotIn(u"b", dialog.sides[1].paths, "a glyph only in one font is read once listed, not before")
        chips["only_a"].checked = chips["only_b"].checked = True
        dialog.fill_glyphs()
        self.assertEqual([r.name for r in dialog.glyph_names][:2], [u"a", u"b"], "glyphs only in one font first")
        self.assertIsNotNone(dialog.sides[1].paths.get(u"b"))
        self.assertEqual(dialog.labels(), (u"Fake A", u"Fake B"))
        kerning = sorted((d.left, d.right, d.a, d.b, d.kind) for d in dialog.kern_rows)
        self.assertEqual(kerning, [(u"H", u"o", -20, -30, "value"), (u"a", u"H", -5, 0, "absent"),
                                   (u"n", u"o", 0, 15, "only_b"), (u"o", u"n", -10, 0, "only_a")])
        # And the kerning "should default to 'Differing values' (instead of 'Other values')"
        self.assertEqual([kind for kind, chip in dialog.kern_chips if chip.checked], ["value"])
        self.assertEqual([(d.left, d.right) for d in dialog.kern_shown], [(u"H", u"o")])
        self.assertEqual(fcmp.kern_label("value", dialog.labels()), u"Differing values")
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
        font = two_master_font()
        dialog = self.dialog([font])
        self.assertEqual(dialog.choice_a.rows, [u"Fake (Regular)", u"Fake (Bold)"])
        self.assertEqual(dialog.choice_b.rows, [u"Choose a font" + self.ELLIPSIS, u"Fake (Regular)", u"Fake (Bold)", None,
                                                u"Open a font" + self.ELLIPSIS])
        self.assertIn(u"the master to compare with", dialog.missing())
        dialog.choice_b.pick(1)
        self.assertIn(u"the same master", dialog.missing())
        self.assertFalse(dialog.compare_button.enabled, "a master is not compared with itself")
        dialog.compare()
        self.assertIsNone(dialog.sides)
        dialog.choice_b.pick(2)
        self.assertTrue(dialog.compare_button.enabled and dialog.swap_button.enabled)
        dialog.compare()
        self.assertTrue(dialog.masters_mode)
        found = dict((r.name, [d.text for d in r.differences]) for r in dialog.results)
        self.assertEqual(found, {u"H": [u"the shapes differ by 20% of the ink; nodes moved up to 100 units (contour 1)",
                                        u"width 500 and 600 (+100)"],
                                 u"o": [u"no layer in Bold"]})
        self.assertEqual(dialog.kern_rows, [])
        self.assertEqual(dialog.feature_rows, [], "one font: its features are shared")
        self.assertEqual(dialog.first_name(dialog.results[-1]), u"o")
        dialog.swap()
        number = font.fgPackage.id
        self.assertEqual((dialog.first_key(), dialog.second_key), ((number, u"Bold"), (number, u"Regular")))
        self.assertEqual(dialog.labels(), (u"Bold", u"Regular"), "compared again, the other way")

    def test_lists_follow_the_open_fonts(self):
        first, second, namesake = first_font(), second_font(), second_font()
        namesake.path = u"Fake B 2.vfc"
        packages = [first]
        dialog = self.dialog(packages)
        self.workspace.packages = lambda: list(packages)
        said = []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        watch = dialog.choice_b.watchers[-1]
        self.assertIn(watch, dialog.filters, "kept: PythonQt drops a filter no Python object holds")
        self.assertEqual(len(dialog.choice_b.rows), 3, "one font, one master: only a file to open")
        self.assertIn(u"Only <b>Fake A</b> is open, with one master.", dialog.missing())
        cleared = dialog.choice_b.cleared
        self.assertFalse(watch.eventFilter(dialog.choice_b, FakeEvent(2)), "the press goes on to the dropdown")
        self.assertEqual(dialog.choice_b.cleared, cleared, "nothing changed: the list is left as it is")
        packages.extend([second, namesake])  # opened in FontLab meanwhile
        watch.eventFilter(dialog.choice_b, FakeEvent(5))
        self.assertEqual(len(dialog.choice_b.rows), 3, "a mouse move reads nothing")
        watch.eventFilter(dialog.choice_b, FakeEvent(2))  # the dropdown pressed: read before its list opens
        self.assertEqual(dialog.choice_b.rows[1:3], [u"Fake B (Fake B.vfc)", u"Fake B (Fake B 2.vfc)"])
        self.assertEqual(dialog.choice_b.currentIndex, 0, "still nothing chosen")
        dialog.choice_b.pick(2)
        self.assertEqual(dialog.second_key, (namesake.fgPackage.id, u"Regular"))
        packages.remove(second)  # the other font of that name closed: the choice stays the font it was
        watch.eventFilter(dialog.dialog, FakeEvent(24))  # the window active again
        self.assertEqual(dialog.choice_b.rows[1:2], [u"Fake B"], "one of that name left: its file's name not needed")
        self.assertEqual((dialog.choice_b.currentIndex, dialog.second_key), (1, (namesake.fgPackage.id, u"Regular")))
        self.assertIs(dialog.chosen(dialog.choice_b)[0], namesake)
        packages[:] = [first, second]  # the font chosen closed, and its namesake opened again
        watch.eventFilter(dialog.dialog, FakeEvent(24))
        self.assertEqual(dialog.choice_b.rows[1:2], [u"Fake B"])
        self.assertEqual((dialog.choice_b.currentIndex, dialog.second_key), (0, None), "matched by number, not by name")
        self.assertFalse(dialog.compare_button.enabled)
        self.assertEqual(said[-1][0], "warning")
        self.assertIn(u"no longer open", said[-1][1])
        dialog.busy = True
        packages.append(namesake)
        watch.eventFilter(dialog.dialog, FakeEvent(24))
        self.assertEqual(len(dialog.choice_b.rows), 4, "not read while comparing")

    def test_units_follow_the_number(self):
        dialog = self.dialog([first_font()])
        spin = dialog.threshold
        spin.setValue(fcmp.THRESHOLD)
        self.assertEqual((fcmp.THRESHOLD, spin.suffix), (1, u" unit"), "as the window opens")
        self.assertEqual([(spin.setValue(n), spin.suffix)[1] for n in (0, 1, 2)], [u" units", u" unit", u" units"])

    def test_rows_listed_at_most(self):
        saved = fcmp.ROWS_SHOWN
        fcmp.ROWS_SHOWN = 2
        try:
            dialog = self.dialog([first_font(), second_font()])
            dialog.choice_b.pick(1)
            dialog.compare()
            for _, chip in dialog.glyph_chips + dialog.kern_chips:
                chip.checked = True
            dialog.fill_glyphs()
            dialog.fill_kerning()
        finally:
            fcmp.ROWS_SHOWN = saved
        self.assertEqual(len(dialog.results), 6)
        self.assertEqual([r.name for r in dialog.glyph_names], [u"a", u"b"], "the worst listed")
        self.assertEqual(len(dialog.kern_shown), 2)

    def test_a_font_closed_since_the_comparison_is_asked_nothing(self):
        # Review: the glyphs only in one font are read as they are listed; the lists keep the last comparison
        # once a font is closed, and ticking "Only in" then called FontLab through the closed font
        first, second = first_font(), second_font()
        packages = [first, second]
        dialog = self.dialog(packages)
        self.workspace.packages = lambda: list(packages)
        dialog.choice_b.pick(1)
        dialog.compare()
        packages.remove(second)  # closed in FontLab
        closed = lambda *args: self.fail("FontLab asked about a closed font")
        second.findName = second.kerning = closed
        # The live pass: its History watcher then logged "A font's History moved ... compared again", and
        # nothing was compared
        said, texts = [], []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        dialog.font_label.setText = texts.append
        dialog.history_moved()
        self.assertEqual(said, [("warning", u"<b>Fake B</b> was closed: the comparison is out of date.")])
        self.assertIn(u"out of date", texts[-1])
        self.assertEqual((dialog.second.package, dialog.second.seen_history), (None, None), "its watcher let go")
        self.assertIs(dialog.package, first, "the font still open still watched")
        chips = dict(dialog.glyph_chips)
        chips["only_a"].checked = chips["only_b"].checked = True
        dialog.fill_glyphs()
        self.assertIn(u"b", [r.name for r in dialog.glyph_names], "still listed, as the last comparison has it")
        self.assertNotIn(u"b", dialog.sides[1].paths, "not read, and not kept as unreadable")
        self.assertIsNotNone(dialog.sides[0].paths.get(u"a"), "the font still open is read")
        for r in (r for r in dialog.glyph_names if r.name in (u"b", u"o")):
            dialog.selected_result = lambda r=r: r
            dialog.draw_comparison()
        dialog.selected_pair = lambda: dialog.kern_rows[0]
        dialog.draw_pair()
        del second.findName, second.kerning
        packages.append(second)  # open again: read now
        dialog.fill_glyphs()
        self.assertIsNotNone(dialog.sides[1].paths.get(u"b"))

    def test_every_kind_shown_when_what_both_have_is_alike(self):
        self.assertEqual(fcmp.kinds_first_on({"value": 3, "only_a": 2, "absent": 1}, fcmp.KERN_KINDS_FIRST),
                         set(["value"]))
        self.assertEqual(fcmp.kinds_first_on({"only_a": 2, "absent": 1}, fcmp.KERN_KINDS_FIRST),
                         set(["only_a"]), "no differing value: every other kind but the glyphs one font lacks")
        self.assertEqual(fcmp.kinds_first_on({"absent": 4}, fcmp.KERN_KINDS_FIRST), set(["absent"]),
                         "those too when they are all there is (owner's image 369)")
        self.assertEqual(fcmp.kinds_first_on({}, fcmp.KERN_KINDS_FIRST), set())
        first, second = first_font(), second_font()
        second.by_name.pop(u"o")  # (the only glyph whose outline differs: the Glyphs list keeps something)
        for name in (u"n", u"uni0101", u"eacute"):
            first.by_name.pop(name)
        first.fgPackage.glyphs = [g.fgGlyph for g in first.by_name.values()]
        second.fgPackage.glyphs = [g.fgGlyph for g in second.by_name.values()]
        second.kernings = {u"Regular": {(u"n", u"o"): 15}}
        first.kernings = {u"Regular": {(u"H", u"o"): -20}}
        dialog = self.dialog([first, second])
        dialog.choice_b.pick(1)
        dialog.compare()
        self.assertTrue(dialog.glyph_names and all(r.a is None or r.b is None for r in dialog.glyph_names),
                        "only glyphs one font lacks differ: shown")
        self.assertTrue(all(chip.checked for kind, chip in dialog.glyph_chips if kind in ("only_a", "only_b")))
        self.assertNotIn("value", [d.kind for d in dialog.kern_rows])
        self.assertTrue(dialog.kern_shown, "no differing value: the other pairs shown")

    def test_installed_fonts_are_listed_and_open_in_fontlab_when_picked(self):
        # The owner: "'Choose a font' does nothing, only 'Open a font' is usable, which doesn't help much,
        # especially if it does not open in the default system font folder"
        first = first_font()
        type(self).installed = [(u"C:\\Fonts\\zeta.ttf", u"Zeta Sans"), (u"C:\\Fonts\\alpha.otf", u"Alpha Serif"),
                                (first.path, u"Fake A, installed")]
        self.addCleanup(lambda: setattr(type(self), "installed", []))
        dialog = self.dialog([first])
        box = dialog.choice_b
        self.assertEqual(box.rows, [u"Choose a font" + self.ELLIPSIS, None, u"Open a font" + self.ELLIPSIS, None,
                                    u"Alpha Serif", u"Zeta Sans"], "A to Z, the font open already left out")
        requested, opened = [], []
        dialog.open_font = lambda path=None: opened.append(path)
        box.pick(4)
        self.assertEqual(opened, [u"C:\\Fonts\\alpha.otf"], "opened in FontLab, then chosen once it is in")
        self.assertEqual((box.currentIndex, dialog.second_key), (0, None), "the choice is what it was meanwhile")
        with io.open(fcmp.__file__, encoding="utf-8") as handle:
            self.assertIn(u"picking one opens it \"\n                                   u\"in FontLab", handle.read(),
                          "its help says so")

    def test_installed_rows_made_again_only_when_they_change(self):
        """read_fonts runs at each press, focus, and activation: it made and sorted some 4,000 installed
        rows each time, comparing each file with each open font's (0.1 s a click with five fonts open)."""
        first = first_font()
        installed = [(u"C:\\Fonts\\zeta.ttf", u"Zeta Sans"), (u"C:\\Fonts\\alpha.otf", u"Alpha Serif")]
        held, made = fcmp.installed_fonts, []
        fcmp.installed_fonts = lambda folders=None: installed  # (the same list while nothing changed, as there)
        self.addCleanup(setattr, fcmp, "installed_fonts", held)
        real = fcmp.installed_entries
        fcmp.installed_entries = lambda found: made.append(list(found)) or real(found)
        self.addCleanup(setattr, fcmp, "installed_entries", real)
        dialog = self.dialog([first])
        count = len(made)
        self.assertGreaterEqual(count, 1)
        rows = list(dialog.choice_b.rows)
        dialog.read_fonts()
        dialog.read_fonts()
        self.assertEqual(len(made), count, "nothing changed: not made again")
        self.assertEqual(dialog.choice_b.rows, rows)
        installed = installed + [(first.path, u"Fake A, installed")]  # (a font installed: a new list)
        dialog.read_fonts()
        self.assertEqual(len(made), count + 1)
        self.assertEqual(dialog.choice_b.rows[4:], [u"Alpha Serif", u"Zeta Sans"], "the font open already left out")
        dialog.read_fonts()
        self.assertEqual(len(made), count + 1)
        first.path = u"C:\\Elsewhere\\a.vfc"  # (the open font saved elsewhere: its installed file listed now)
        dialog.read_fonts()
        self.assertEqual((len(made), dialog.choice_b.rows[4:]), (count + 2, [u"Alpha Serif", u"Fake A, installed",
                                                                             u"Zeta Sans"]))

    def test_the_placeholder_is_not_a_choice_and_the_file_dialog_starts_in_a_font_folder(self):
        first, second = first_font(), second_font()
        dialog = self.dialog([first, second])
        flags = []
        qt = sys.modules["PythonQt"].QtCore.Qt
        qt.UserRole = 256
        self.addCleanup(lambda: delattr(qt, "UserRole"))
        dialog.choice_b.setItemData = lambda index, value, role: flags.append((index, value, role))
        dialog.second_rows = []
        dialog.read_fonts()
        self.assertIn((0, 0, 255), flags, "its row grayed out (its flags, Qt.UserRole - 1, cleared)")
        dialog.choice_b.pick(1)
        self.assertEqual(dialog.second_key, (second.fgPackage.id, u"Regular"))
        dialog.choice_b.pick(0)
        self.assertEqual(dialog.second_key, (second.fgPackage.id, u"Regular"), "picking it changes nothing")
        folders = fcmp.font_folders()
        self.assertEqual(dialog.open_folder(), folders[0] if folders else u"")
        dialog.last_folder = HERE
        self.assertEqual(dialog.open_folder(), HERE, "then where the last font came from")

    def test_open_a_font(self):
        first, second, third = first_font(), second_font(), two_master_font()
        packages = [first, second]
        dialog = self.dialog(packages)
        self.workspace.packages = lambda: list(packages)  # (a font opened later is listed)
        said, requested, picked = [], [], []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        box = dialog.choice_b
        gui = sys.modules["PythonQt"].QtGui
        gui.classes["QFileDialog"] = type("QFileDialog", (), {"getOpenFileName": staticmethod(lambda *args: picked[-1])})
        fontlab = sys.modules["fontlab"]
        fontlab.flItems = type("Items", (), {"requestLoadingFont": staticmethod(requested.append)})
        open_row = lambda: len(box.rows) - 1  # the dropdown's last row, after the separator
        try:
            self.assertEqual(box.rows[-2:], [None, u"Open a font\N{HORIZONTAL ELLIPSIS}"])
            self.assertFalse(hasattr(dialog, "open_button"), "the dropdown's row, not a button beside it")
            picked.append(u"")  # the file dialog closed without a file
            box.pick(open_row())
            self.assertEqual((box.currentIndex, dialog.second_key, said), (0, None, []), "the choice is what it was")
            picked.append(first.path)
            box.pick(open_row())
            self.assertEqual((box.currentIndex, said[-1][0]), (0, "warning"), "this window's own font, with one master")
            picked.append(second.path)
            box.pick(open_row())
            self.assertEqual(requested, [], "open already: not opened again")
            self.assertEqual((box.currentIndex, dialog.second_key), (1, (second.fgPackage.id, u"Regular")))
            self.assertIn(u"open already", said[-1][1])
            self.assertTrue(dialog.compare_button.enabled)
            done = lambda: len([text for level, text in said if level == "done"])
            picked.append(u"other.vfc")
            box.pick(open_row())
            self.assertEqual(box.currentIndex, 1, "the font chosen stays chosen until the file is in")
            picked.append(third.path)
            box.pick(open_row())
            self.assertEqual(requested, [u"other.vfc", third.path])
            dialog.look_for_opened()
            self.assertEqual((dialog.open_tries, done()), (1, 1), "not in yet: looked for again")
            earlier = first_font()
            earlier.path = u"other.vfc"
            packages.append(earlier)  # the file picked first comes in first
            dialog.look_for_opened()
            self.assertEqual((dialog.open_tries, done()), (2, 1), "not the file looked for: looked for again")
            self.assertIsNotNone(dialog.opening)
            packages.append(third)
            dialog.look_for_opened()
            self.assertEqual(said[-1][0], "done")
            self.assertIn(u"Opened", said[-1][1])
            self.assertEqual(done(), 2)
            self.assertIs(dialog.chosen(box)[0], third, "the font just opened")
            self.assertEqual(box.rows[box.currentIndex], u"Fake (Regular)", "its current master, shown in the dropdown")
            dialog.look_for_opened()
            self.assertEqual(done(), 2, "chosen once: the earlier request's poll is gone")
        finally:
            del gui.classes["QFileDialog"]
            del fontlab.flItems

    def test_a_font_fontlab_crashes_on_is_asked_about_first(self):
        """FontLab 7.2 crashes on a font whose GPOS holds a single adjustment of format 2 with no values (Noto Sans
        JP): Open a font... opens a fixed copy of it, or nothing, as the one question asked first is answered."""
        import fontbytes
        folder = tempfile.mkdtemp(prefix="freelab-compare-crash-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, u"NotoSansJP[wght].ttf")
        with open(path, "wb") as handle:
            handle.write(fontbytes.sfnt({b"head": fontbytes.head(), b"GPOS": fontbytes.gpos(
                [fontbytes.lookup(9, [fontbytes.extension(fontbytes.single(2, 0, 0))])])}))
        for name in ("ask_open_fixed", "safe_copies_folder"):
            self.addCleanup(setattr, self.ak, name, getattr(self.ak, name))
        self.ak.safe_copies_folder = lambda: os.path.join(folder, "copies")
        first = first_font()
        packages = [first]
        dialog = self.dialog(packages)
        self.workspace.packages = lambda: list(packages)
        said, requested = [], []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        fontlab = sys.modules["fontlab"]
        fontlab.flItems = type("Items", (), {"requestLoadingFont": staticmethod(requested.append)})
        self.addCleanup(lambda: delattr(fontlab, "flItems"))
        self.ak.ask_open_fixed = lambda parent, crashers: False
        dialog.open_font(path)
        self.assertEqual((requested, getattr(dialog, "opening", None)), ([], None), "skipped: nothing opened")
        self.assertEqual(said[-1][0], "warning")
        self.assertIn(u"skipped: FontLab 7.2 crashes on it", said[-1][1])
        self.ak.ask_open_fixed = lambda parent, crashers: True
        dialog.open_font(path)
        copy = requested[-1]
        self.assertEqual((os.path.basename(copy), os.path.dirname(os.path.dirname(copy))),
                         (u"NotoSansJP[wght].ttf", os.path.join(folder, "copies")), "its fixed copy opened")
        self.assertEqual(dialog.opening[0], copy, "the copy looked for")
        # (Codex, 2026-11-19: picked again before it came in, it was asked about, written, and opened again)
        self.ak.ask_open_fixed = lambda parent, crashers: self.fail("its copy is on its way: not asked about")
        os.utime(copy, (1, 1))
        dialog.open_font(path)
        self.assertEqual((requested, os.path.getmtime(copy)), ([copy], 1), "asked for once, the copy not rewritten")
        self.assertEqual(said[-1], ("info", u"<i>NotoSansJP[wght].ttf</i> is being opened already: chosen once it "
                                            u"is in."))
        self.ak.ask_open_fixed = lambda parent, crashers: True
        second = second_font()
        second.path = copy
        packages.append(second)
        dialog.look_for_opened()
        self.assertEqual(dialog.second_key, (second.fgPackage.id, u"Regular"), "chosen once it is in")
        del requested[:]
        mark = len(said)
        dialog.open_font(path)
        self.assertEqual(requested, [], "its copy open already: chosen, not opened again")
        self.assertTrue(any(u"open already" in text for level, text in said[mark:]), said[mark:])

    def test_a_font_opened_is_compared_and_the_window_comes_back(self):
        # The owner: choosing a font "sends the script window in the background and doesn't bring it back to
        # the front after opening (...) Could opening a font also automatically run the first
        # comparison without requiring to click 'Compare'?"
        first, second = first_font(), second_font()
        packages = [first]
        dialog = self.dialog(packages)
        self.workspace.packages = lambda: list(packages)
        said, requested, raised = [], [], []
        dialog.log.add = lambda text, level="info": said.append((level, text))
        fontlab = sys.modules["fontlab"]
        fontlab.flItems = type("Items", (), {"requestLoadingFont": staticmethod(requested.append)})
        self.addCleanup(lambda: delattr(fontlab, "flItems"))
        window = dialog.dialog
        window.visible, window.minimized = True, False
        window.raise_ = lambda: raised.append(window)
        window.showNormal = lambda: self.fail("a window minimized is never restored")
        dialog.open_font(second.path)
        dialog.look_for_opened()
        self.assertIsNone(dialog.sides, "not in yet")
        packages.append(second)  # FontLab lists it, and makes its window the active one
        dialog.look_for_opened()
        self.assertEqual(dialog.second_key, (second.fgPackage.id, u"Regular"))
        self.assertEqual(raised, [dialog.dialog], "brought back at once")
        self.assertNotIn(u"Click", said[-1][1], "nothing to click")
        dialog.busy = True
        dialog.settled()  # (the settling timer, while a comparison runs: waits for it)
        self.assertIsNone(dialog.sides)
        dialog.busy = False
        dialog.settled()  # (the settling timer: FontLab has activated its font's window by now)
        self.assertIsNotNone(dialog.sides, "compared without a click on Compare")
        self.assertEqual(dialog.labels(), (u"Fake A", u"Fake B"))
        self.assertEqual(len(raised), 3, "brought back again before and after the comparison")
        self.assertIsNotNone(getattr(dialog, "late_timer", None), "and once more a while later")
        self.assertEqual(said[-1], ("done", u"Compared <b>Fake A</b> with <b>Fake B</b>."))
        del raised[:]
        dialog.open_font(second.path)  # (open already: chosen and compared all the same)
        self.assertEqual((requested, raised), ([second.path], [dialog.dialog]))
        compared = []
        real_compare = dialog.compare
        dialog.compare = lambda: compared.append(1) or real_compare()
        dialog.choice_b.pick(1)
        self.assertEqual(raised, [dialog.dialog], "a font picked among those open: the window is in front already")
        self.assertEqual(compared, [1], "and compared at once (owner's image 257)")
        dialog.compare = real_compare
        # Review: the timers once the window is minimized or closed, and a click on Compare meanwhile
        stopped = []
        dialog.settle_timer = type("Timer", (), {"stop": lambda timer: stopped.append(1),
                                                 "start": lambda timer: None})()
        compared, real = [], dialog.compare
        dialog.compare = lambda: compared.append(1) or real()
        window.minimized = True
        dialog.bring_forward()  # (the late raise)
        dialog.settled()
        self.assertEqual((raised[1:], compared), ([], []), "minimized: left as it is, nothing compared")
        window.minimized, window.visible = False, False
        dialog.settled()
        self.assertEqual(compared, [], "closed: no comparison for a window no one sees")
        window.visible = True
        real()  # (Compare clicked during the settling)
        self.assertEqual(stopped, [1], "the settling's comparison called off: compared once")

    def test_a_comparison_shows_its_progress(self):
        # The owner: "the comparing step could potentially get its own loading bar, since CJK fonts can take a
        # bit to load". It is the window's own now, in its top row (ak.busy_*: owner's image 200)
        dialog = self.dialog([first_font(), second_font()])
        dialog.choice_b.pick(1)
        ak = self.ak
        started, moved, ended, enabled = [], [], [], {}
        real = ak.busy_start, ak.busy_progress, ak.busy_end, ak.enable, fcmp.SHOW_AFTER

        def restore():
            ak.busy_start, ak.busy_progress, ak.busy_end, ak.enable, fcmp.SHOW_AFTER = real
        self.addCleanup(restore)
        ak.busy_start = lambda owner, what=u"", stoppable=True: started.append(what)
        ak.busy_progress = lambda owner, what=None, part=None, force=False, stoppable=True: moved.append(
            (what, part, stoppable))
        ak.busy_end = lambda owner: ended.append(owner.busy)
        ak.enable = lambda widget, on: enabled.setdefault(id(widget), []).append(bool(on))
        dialog.compare()
        self.assertEqual((started, moved, ended), ([], [], []), "a small font compared at once: no bar to flicker")
        fcmp.SHOW_AFTER = 0
        dialog.compare()
        self.assertEqual(started, [fcmp.READ_A_STEP], "the top row from the first step")
        self.assertEqual([what for what, _, _ in moved if what is not None][::1],
                         [what for what, _, _ in moved], "each move names its step")
        steps = []
        for what, _, _ in moved:
            if not steps or steps[-1] != what:
                steps.append(what)
        self.assertEqual(steps, [label for label, _ in fcmp.COMPARE_STEPS], "each step said in turn")
        values = [part for _, part, _ in moved]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[-1], 1.0)
        self.assertEqual(moved[-1][2], False, "the lists filled: too late to stop")
        self.assertEqual(ended, [False], "gone with the comparison (not busy then)")
        self.assertFalse(dialog.busy)
        for widget in (dialog.choice_a, dialog.choice_b, dialog.threshold, dialog.compare_button, dialog.tabs,
                       dialog.pages):
            states = enabled.get(id(widget), [])
            self.assertTrue(False in states and states[-1], "grayed meanwhile, then clickable again")
        self.assertAlmostEqual(fcmp.bar_value(fcmp.COMPARE_STEPS, fcmp.GLYPHS_STEP, 0.5), (0.08 + 0.85) / 2)
        self.assertIsNone(fcmp.bar_value(fcmp.COMPARE_STEPS, u"elsewhere"))
        # Stopped (the tools menu, an arrow, Close, Esc): the comparison shown before stays, as it was
        compared = dialog.sides, dialog.results, dialog.kern_rows, dialog.package
        lines = []
        dialog.font_label = type("Line", (object,), {"text": u"Compared A with B.",
                                                     "setText": lambda label, text: lines.append(text)})()

        def stopping(owner, what=None, part=None, force=False, stoppable=True):
            if what == fcmp.KERNING_STEP and stoppable:
                raise ak.Stopped()
        ak.busy_progress = stopping
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.compare()
        self.assertEqual((dialog.sides, dialog.results, dialog.kern_rows, dialog.package), compared)
        self.assertEqual(lines[-1], u"Compared A with B.", "its top line too")
        self.assertEqual((logged[-1][0], dialog.busy, ended[-1]), ("warning", False, False))

    def test_cancel_sits_before_close_usable_while_it_compares(self):
        """The owner, 2026-11-24: a Cancel left of Close, grayed but while work that can stop runs (ak.cancel_button),
        as Esc stops it; its help says what a stop leaves. Font Compare never writes: it is grayed but then."""
        import qtfakes
        rows = []

        class Row(Anything):
            def __init__(self, *args):
                self.items = []
                rows.append(self)

            def addWidget(self, widget, *args):
                self.items.append(widget)

            def addStretch(self, *args):
                self.items.append(None)

            def count(self):
                return len(self.items)

            def itemAt(self, k):
                held = self.items[k]
                return type("Item", (object,), {"widget": lambda item: held})()

            def insertWidget(self, k, widget):
                self.items.insert(k, widget)

        classes = sys.modules["PythonQt"].QtGui.classes
        before = classes.get("QHBoxLayout")
        classes["QHBoxLayout"] = Row
        self.addCleanup(lambda: classes.pop("QHBoxLayout") if before is None else classes.update(QHBoxLayout=before))
        dialog = self.dialog([first_font(), second_font()])
        bottom = [row for row in rows if dialog.close_button in row.items][0]
        self.assertEqual(bottom.items, [None, dialog.cancel_button, dialog.close_button], "right before Close")
        self.assertFalse(dialog.cancel_button.enabled, "grayed while nothing runs")
        self.assertEqual(dialog.cancel_button.whats, self.ak.CANCEL_HELP + u" A comparison stopped changes neither "
                                                                           u"font: the lists show the one before it.")
        dialog.choice_b.pick(1)
        ak = self.ak
        real = ak.busy_start, ak.busy_progress, ak.busy_end, fcmp.SHOW_AFTER

        def restore():
            ak.busy_start, ak.busy_progress, ak.busy_end, fcmp.SHOW_AFTER = real
        self.addCleanup(restore)
        ak.busy_start = lambda owner, what=u"", stoppable=True: None  # (the real ones need a window)
        ak.busy_end = lambda owner: None
        moved = []

        def stopping(owner, what=None, part=None, force=False, stoppable=True):
            moved.append((what, owner.cancel_button.enabled))
            if what == fcmp.KERNING_STEP and stoppable:
                raise ak.Stopped()  # (as a click on Cancel makes it)
        ak.busy_progress = stopping
        seen = qtfakes.follow_cancel(self, ak)
        fcmp.SHOW_AFTER = 0
        logged = []
        dialog.log.add = lambda text, level="info": logged.append((level, text))
        dialog.compare()
        self.assertEqual(seen, [(fcmp.READ_A_STEP, True, True), (None, None, False)], "usable while it compares")
        self.assertTrue(moved and all(on for _, on in moved))
        self.assertEqual(logged[-1], ("warning", u"The comparison was stopped: the lists show the one before it."))

    def test_has_font_and_the_choices_kept_usable(self):
        """Owner's image 209: with no comparison to make, the controls are grayed (ak.no_font_states, which
        asks has_font) but the two dropdowns that choose the fonts."""
        dialog = self.dialog([first_font(), second_font()])
        prop = getattr(self.ak, "WITHOUT_FONT_PROP", "freelabWithoutFont")
        self.assertTrue(dialog.choice_a.property(prop) and dialog.choice_b.property(prop))
        self.assertFalse(dialog.threshold.property(prop))
        self.assertFalse(dialog.has_font(), "no second side chosen yet")
        dialog.choice_b.pick(1)
        self.assertTrue(dialog.has_font())
        self.assertTrue(self.ak.window_has_font(dialog))
        dialog.missing = lambda: u"No font is open."
        self.assertFalse(dialog.has_font(), "something missing: no comparison to make")

    def test_a_color_glyph_at_its_font_scale(self):
        a, b = first_font(), second_font()
        b.upm = 2000
        dialog = self.dialog([a, b])
        dialog.log.add = lambda text, level="info": None
        dialog.choice_b.pick(1)
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

    def test_close_and_the_help_read_as_every_tools(self):
        """The review of 2026-11-24: Close has a help, as Proof's and Glyph Compose's; the help's last line stands
        apart, as every tool's; Esc is a key, in italics."""
        dialog = self.dialog([first_font()])
        self.assertIn(u"Closes the window", getattr(dialog.close_button, "whats", u""))
        self.assertIn(u".<br><br>\nClick this help's button", fcmp.HELP)
        self.assertIn(u"<i>Esc</i>", fcmp.HELP)
        # (kinds_first_on: what starts hidden is shown when nothing else differs, as the chips' helps said)
        help_text = u" ".join(fcmp.HELP.split())
        self.assertIn(u"hidden to start with, unless nothing else differs", help_text)
        self.assertIn(u"(the other kinds when there are none)", help_text)

    def test_one_font_one_master(self):
        dialog = self.dialog([first_font()])
        self.assertEqual(dialog.choice_a.rows, [u"Fake A"])
        self.assertEqual(dialog.choice_b.rows, [u"Choose a font\N{HORIZONTAL ELLIPSIS}", None, u"Open a font\N{HORIZONTAL ELLIPSIS}"],
                         "a font is not offered against itself")
        self.assertFalse(dialog.compare_button.enabled)
        dialog.compare()
        self.assertIsNone(dialog.sides)

    def test_no_font(self):
        self.workspace.packages = lambda: []
        self.workspace.currentPackage = None
        enabled = {}
        FakeCombo.setEnabled = lambda box, on: enabled.__setitem__(id(box), on)
        self.addCleanup(delattr, FakeCombo, "setEnabled")
        dialog = fcmp.CompareDialog()
        self.assertIsNone(dialog.failed, dialog.failed)
        # (owner's image 290: "Compare [ ]" then the swap button, an empty box; a grayed "n/a" instead)
        self.assertEqual((dialog.choice_a.rows, dialog.first_key(), dialog.second_key), ([fcmp.NOT_AVAILABLE], None, None))
        self.assertEqual(fcmp.NOT_AVAILABLE, u"n/a")
        self.assertIs(enabled.get(id(dialog.choice_a)), False, "grayed")
        self.assertIn(u"No font is open", dialog.missing())
        self.assertIn(fcmp.NO_FONT_LINE, self.ak.ONE_LINE, "a no-font line: on one line")
        self.assertFalse(dialog.compare_button.enabled)
        dialog.compare()
        self.assertIsNone(dialog.sides)
        # A font opened for the window: its masters instead, the box usable again
        self.workspace.packages = lambda: [first_font()]
        self.workspace.currentPackage = self.workspace.packages()[0]
        dialog.font_changed()
        self.assertEqual(dialog.choice_a.rows, [u"Fake A"])
        self.assertIs(enabled.get(id(dialog.choice_a)), True)

    def test_the_tick_of_the_features_alike_says_how_many(self):
        # Owner's image 293: "I don't seem to be able to see a difference when ticking this option". It works:
        # it lists the features whose code is the same in both fonts too; two fonts with none alike (every
        # feature differs or is only in one) leave it nothing to show. It says how many, and grays with none.
        self.assertEqual(fcmp.same_caption(None), u"Show the features that are alike.")
        self.assertEqual(fcmp.same_caption(0), u"Show the features that are alike.")
        self.assertEqual(fcmp.same_caption(1), u"Show the feature that is alike.")
        self.assertEqual(fcmp.same_caption(1200), u"Show the 1,200 features that are alike.")
        dialog = self.dialog([first_font(), second_font()])
        told = {}
        dialog.show_same = type("Tick", (), {
            "checked": False, "setText": lambda tick, text: told.__setitem__("text", text),
            "setEnabled": lambda tick, on: told.__setitem__("enabled", on),
            "setToolTip": lambda tick, text: told.__setitem__("tip", text),
            "property": lambda tick, name: None})()
        dialog.update_buttons()
        self.assertEqual((told["text"], told["enabled"], told["tip"]),
                         (u"Show the features that are alike.", False, u"Compare two fonts first."))
        dialog.choice_b.pick(1)  # (compared at once: the Classes panel's classes are alike in both)
        self.assertEqual((told["text"], told["enabled"], told["tip"]), (u"Show the feature that is alike.", True, u""))
        self.assertEqual([f.tag for f in dialog.feature_shown], [u"liga", u"kern", u"ss01"], "unticked: alike left out")
        dialog.show_same.checked = True
        dialog.fill_features()
        self.assertEqual([f.tag for f in dialog.feature_shown], [u"liga", u"kern", u"ss01", fcmp.CLASSES],
                         "ticked: the one alike listed too")
        dialog.feature_rows = [f for f in dialog.feature_rows if f.kind != "same"]  # (two fonts with none alike)
        dialog.update_buttons()
        self.assertEqual(told["enabled"], False)
        self.assertIn(u"No feature is alike", told["tip"])

    def test_the_options_rows_are_as_tall_as_one_another(self):
        # (owner's images 285 and 286, in Kerning Check: a tab's row of options shorter than another's moved the
        # list under it as the tab was shown; here the chips' rows and the Features tab's tick)
        dialog = self.dialog([first_font(), second_font()])
        self.assertEqual(len(dialog.option_rows), 3, "the chips' two rows and the tick's")

        class Hint(object):
            def __init__(self, height):
                self.value = height

            def height(self):
                return self.value

        def box(*heights):
            items = [type("Item", (), {"widget": (lambda item, h=h: type("W", (), {"sizeHint": Hint(h)})())})()
                     for h in heights]
            found = type("Box", (), {"least": None})()
            found.layout = lambda: type("Layout", (), {"count": lambda layout: len(items),
                                                       "itemAt": lambda layout, index: items[index]})()
            found.setMinimumHeight = lambda height: setattr(found, "least", height)
            return found

        dialog.option_rows = [box(24, 24), box(24), box(18)]
        dialog.switch_page(2)
        self.assertEqual([row.least for row in dialog.option_rows], [24, 24, 24], "the tick's row as tall as the chips'")
        with io.open(fcmp.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(u"self.level_options()\n        self.may_recall = True", source, "levelled as the window is made")

    def test_one_feature_alike(self):
        dialog = self.dialog([first_font(), second_font()])
        dialog.choice_b.pick(1)
        dialog.compare()
        texts = []
        dialog.feature_status.setText = texts.append
        same = lambda tag: fcmp.FeatureDifference(tag, "same", u"", u"", [])
        for rows in ([same(u"liga")], [same(u"liga"), same(u"kern")]):
            dialog.feature_rows = rows
            dialog.fill_features()
        self.assertEqual(texts, [u"The one feature is alike in both.", u"The <b>2 features</b> are alike."])

    def test_the_tabs_count_in_parentheses(self):
        # Owner's image 235: "Glyphs 13,956" read as a name; every header puts its count in parentheses
        dialog = self.dialog([first_font(), second_font()])
        texts = {}
        dialog.tabs.setTabText = lambda index, text: texts.__setitem__(index, text)
        dialog.update_buttons()
        self.assertEqual(texts, {0: u"Glyphs", 1: u"Kerning", 2: u"Features"}, "nothing compared: no count")
        dialog.choice_b.pick(1)
        dialog.update_buttons()
        self.assertEqual(texts, {0: u"Glyphs (6)", 1: u"Kerning (3)", 2: u"Features (3)"})
        self.assertEqual(fcmp.tab_text(u"Glyphs", 13956), u"Glyphs (13,956)")
        # (owner's images 327 and 328: "(0)" over features alike read as nothing compared)
        self.assertEqual(fcmp.tab_text(u"Features", 0), u"Features (alike)")
        self.assertEqual(fcmp.counted(13956, u"glyph"), u"13,956 glyphs")

    def test_the_tab_lines(self):
        # Owner's image 256: "632 glyphs differ." and "231 shown." on one line; names and counts in bold,
        # the chips' names in italics
        line = fcmp.glyphs_line
        self.assertEqual(line(632, 231, 231, [u"Only in A"]),
                         u"<b>632 glyphs</b> differ (<b>231</b> shown; hidden: <i>Only in A</i>).")
        self.assertEqual(line(5000, 2000, 2400), u"<b>5,000 glyphs</b> differ (the <b>2,000</b> worst shown).")
        self.assertEqual(line(1, 1, 1), u"<b>1 glyph</b> differs.")
        self.assertIn(u"alike", line(0, 0, 0))
        counts = {"only_a": 3, "only_b": 2, "value": 442, "absent": 1}
        self.assertEqual(fcmp.kerning_line(counts, (u"A", u"B")),
                         u"<b>447 glyph pairs</b> kerned differently: <b>3</b> only in <b>A</b>, <b>2</b> only in "
                         u"<b>B</b>, <b>442</b> with differing values. <b>1 pair</b> of a glyph one font lacks.")
        self.assertIn(u"(the <b>2,000</b> largest differences shown).", fcmp.kerning_line(counts, (u"A", u"B"), 2000))
        rows = [fcmp.FeatureDifference(u"liga", "only_a", u"", u"", []),
                fcmp.FeatureDifference(u"kern", "same", u"", u"", [])]
        self.assertEqual(fcmp.features_line(rows, (u"A", u"B")),
                         u"<b>1 feature</b> differs: <b>1</b> only in <b>A</b>, <b>0</b> only in <b>B</b>, <b>0</b> "
                         u"with code that differs.")

    def test_the_code_is_written_in_the_views_enabled_colors(self):
        # Owner's image 233: a font compared from the Features tab showed its code dimmed until another feature
        # was selected. The pages are grayed while comparing, and Qt's palette() then gives the disabled
        # colors, which the code's HTML kept: the colors are read for the enabled view, whatever it is now
        dialog = self.dialog([first_font(), second_font()])
        gui = sys.modules["PythonQt"].QtGui
        asked = []

        class Color(object):
            def __init__(self, value):
                self.value = value

            def red(self):
                return self.value

            green = blue = red

        class Palette(object):
            def color(self, *args):
                asked.append(args)
                return Color(200 if len(args) == 2 and args[0] == "active" else 90)

        gui.classes["QPalette"] = type("QPalette", (), {"Active": "active", "Base": "base", "Text": "text"})
        self.addCleanup(lambda: gui.classes.pop("QPalette", None))
        dialog.diff_view = type("View", (), {"palette": Palette()})()
        self.assertEqual(dialog.code_colors(), ((200, 200, 200), (200, 200, 200)))
        self.assertEqual(asked, [("active", "base"), ("active", "text")])

    def test_the_first_font_is_as_wide_as_its_name_and_bold(self):
        # Owner's images 236 and 237: a tab's width between the name and the swap button, the name not bold
        made = []
        real = FakeCombo.__init__

        def init(box, *args, **kwargs):
            real(box)
            made.append(box)
            box.calls = []
            box.setSizeAdjustPolicy = lambda policy: box.calls.append(("policy", policy))
            box.setMinimumContentsLength = lambda length: box.calls.append(("length", length))
            box.setFont = lambda font: box.calls.append(("font", font))
        FakeCombo.__init__ = init
        self.addCleanup(setattr, FakeCombo, "__init__", real)
        FakeCombo.AdjustToContents = "to contents"
        self.addCleanup(delattr, FakeCombo, "AdjustToContents")
        gui = sys.modules["PythonQt"].QtGui
        bolded = []
        gui.classes["QFont"] = type("QFont", (), {"__init__": lambda font, *args: None,
                                                  "setBold": lambda font, on: bolded.append(on)})
        self.addCleanup(lambda: gui.classes.pop("QFont", None))
        dialog = self.dialog([first_font(), second_font()])
        calls = dict((kind, value) for kind, value in dialog.choice_a.calls)
        self.assertEqual(calls["policy"], "to contents")
        self.assertEqual(calls["length"], 0)
        self.assertIn("font", calls)
        self.assertEqual(bolded, [True])
        self.assertNotIn("font", dict(dialog.choice_b.calls), "the second lists other fonts: plain")

    def test_the_font_picked_is_kept_for_the_session(self):
        # Owner's image 257: "the last loaded font should stay loaded and keep being compared with for the rest
        # of the session (or until a new font is selected for comparison)"
        first, second, third = first_font(), second_font(), two_master_font()
        packages = [first, second, third]
        dialog = self.dialog(packages)
        dialog.choice_b.pick(1)  # Fake B
        self.assertEqual(getattr(sys, fcmp.REMEMBERED)["number"], second.fgPackage.id)
        # A new window on the same font: Fake B chosen, and compared once it is shown
        other = self.dialog(packages)
        self.assertEqual(other.second_key, (second.fgPackage.id, u"Regular"))
        self.assertIsNone(other.sides, "not compared before it is shown")
        other.shown = lambda: True
        other.compare_recalled()
        self.assertIsNotNone(other.sides)
        self.assertEqual(other.labels(), (u"Fake A", u"Fake B"))
        other.sides = None
        other.compare_recalled()
        self.assertIsNone(other.sides, "once")
        # Another font picked: kept instead
        index = next(k for k, row in enumerate(dialog.second_rows) if row[0] == "font" and row[1] == third.fgPackage.id)
        dialog.choice_b.pick(index)
        self.assertEqual(getattr(sys, fcmp.REMEMBERED)["number"], third.fgPackage.id)
        # The font closed and its file opened again (another number): still the one
        reopened = second_font()
        reopened.path = second.path
        packages[:] = [first, reopened]
        setattr(sys, fcmp.REMEMBERED, {"number": second.fgPackage.id, "path": second.path, "master": u"Regular"})
        again = self.dialog(packages)
        self.assertEqual(again.second_key, (reopened.fgPackage.id, u"Regular"))
        # Not open at all: nothing chosen
        packages[:] = [first, third]
        none = self.dialog(packages)
        self.assertIsNone(none.second_key)
        # The window's own font (one master) kept elsewhere: nothing to compare it with here
        setattr(sys, fcmp.REMEMBERED, {"number": first.fgPackage.id, "path": first.path, "master": u"Regular"})
        own = self.dialog([first, third])
        self.assertIsNone(own.second_key)
        # Read again later (a press on the dropdown): never chosen then, under the user's pick
        setattr(sys, fcmp.REMEMBERED, {"number": third.fgPackage.id, "path": third.path, "master": u"Bold"})
        own.read_fonts()
        self.assertIsNone(own.second_key)
        own.font_changed()  # (as the window takes a font: chosen then)
        self.assertEqual(own.second_key, (third.fgPackage.id, u"Bold"))


class ThemeChangedTests(unittest.TestCase):
    def test_a_dark_mode_switch_redraws_without_reading_the_fonts(self):
        # (the glyphs' pictures are in two colors: the shared module cannot redraw them in one)
        dialog = fcmp.CompareDialog.__new__(fcmp.CompareDialog)
        calls, current = [], []

        class Item(object):
            def __init__(self, index):
                self.index = index

        items = [Item(0), Item(1), Item(2)]
        dialog.glyph_tree = type("Tree", (object,), {"setCurrentItem": lambda tree, item: current.append(item.index)})()
        dialog.selected_item = lambda view: items[1]
        dialog.index_of = lambda item: item.index if item is not None else -1
        dialog.top_items = lambda tree: items
        dialog.fill_glyphs = lambda: calls.append("glyphs")
        dialog.draw_comparison = lambda: calls.append("comparison")
        dialog.draw_pair = lambda: calls.append("pair")
        dialog.feature_selected = lambda: calls.append("differences")
        dialog.compare = dialog.run = lambda: self.fail("the fonts are not read again")
        dialog.redraws = {}
        dialog.theme_changed()
        self.assertEqual(sorted(calls), ["comparison", "differences", "glyphs", "pair"])
        self.assertEqual(current, [1], "the selected glyph stays selected")


if __name__ == "__main__":
    unittest.main()
