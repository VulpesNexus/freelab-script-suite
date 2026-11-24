# -*- coding: utf-8 -*-
"""Tests of Font Builder's sheets (their pure parts: layout, bands, finders, reading). Valid Python 2.7
and Python 3."""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "builder"))
import freelab_font_builder as fb  # noqa: E402

METRICS = fb.Metrics(1000, 800, -200, 500, 700)
LATIN = ["A", "B", "C", "a", "b", "c", "uni00E9", "g.alt1", "f_f_i", "u1F600"]


def sheet_of(names=LATIN, em=150, **options):
    return fb.Sheet(names, [fb.label_of(n) for n in names], METRICS, em, **options)


def raster(sheet, px):
    """The sheet's marks as rows of bytes (0 ink, 255 paper), px pixels a unit."""
    width, height = sheet.size_units()
    rows = [bytearray(b"\xff" * (width * px)) for _ in range(height * px)]
    for x, y, w, h in fb.marks(sheet):
        for yy in range(int(round(y * px)), int(round((y + h) * px))):
            rows[yy][int(round(x * px)):int(round((x + w) * px))] = b"\x00" * (int(round((x + w) * px)) - int(round(x * px)))
    return [bytes(r) for r in rows]


def warped_sampler(sheet, mapping):
    """sample(x, y) of the sheet seen through mapping (sheet units to image pixels): each image point
    taken back to the sheet, black where a mark is."""
    inverse = fb.homography([fb.apply(mapping, *p) for p in ((0, 0), (1, 0), (1, 1), (0, 1))],
                            [(0, 0), (1, 0), (1, 1), (0, 1)])
    black = set()  # (every mark covers whole units)
    for rx, ry, rw, rh in fb.marks(sheet):
        for ux in range(int(round(rx)), int(round(rx + rw))):
            for uy in range(int(round(ry)), int(round(ry + rh))):
                black.add((ux, uy))

    def sample(x, y):
        u, v = fb.apply(inverse, x, y)
        return 10 if (int(u // 1), int(v // 1)) in black else 245
    return sample


class LayoutTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(fb.label_of("uni00E9"), "é")
        self.assertEqual(fb.label_of("uni00E9.alt1"), "é.alt1")
        self.assertEqual(fb.label_of("A"), "A")
        self.assertEqual(fb.label_of("f_f_i"), "f_f_i")
        self.assertEqual(len(fb.label_of("u1F600")) in (1, 2), True, "an astral character (a pair on a narrow build)")

    def test_cells_fill_rows_and_the_sheet_is_whole_units(self):
        sheet = sheet_of()
        self.assertEqual((sheet.columns, sheet.rows), (4, 3))
        w, h = sheet.size()
        self.assertEqual((w % sheet.unit, h % sheet.unit), (0, 0))
        cw, ch = sheet.cell_size()
        left0, top0 = sheet.cell(0)
        left5, top5 = sheet.cell(5)
        self.assertEqual((left5 - left0, top5 - top0), (cw, ch))
        last = sheet.cell(len(LATIN) - 1)
        self.assertLess(last[1] + sheet.box_size()[1], h - sheet.margin() - sheet.band_height() + 1, "the last row clears the bottom band")

    def test_units_map_back(self):
        sheet = sheet_of()
        ox, oy = sheet.origin(3)
        self.assertEqual(sheet.to_units(3, ox, oy), (0.0, 0.0))
        x, y = sheet.to_units(3, ox + sheet.em, oy - sheet.em / 2.0)
        self.assertAlmostEqual(x, 1000)
        self.assertAlmostEqual(y, 500)
        guides = dict(sheet.guides(3))
        self.assertAlmostEqual(guides["baseline"], oy)
        self.assertAlmostEqual(oy - guides["x-height"], sheet.em / 2.0)

    def test_sheets_split_by_count_and_by_size(self):
        names = ["g%03d" % i for i in range(250)]
        sheets = fb.split_sheets(names, names, METRICS, per_sheet=100, em=300)
        self.assertEqual([len(s.names) for s in sheets], [100, 100, 50])
        self.assertEqual([(s.index, s.count) for s in sheets], [(0, 3), (1, 3), (2, 3)])
        big = fb.split_sheets(names, names, METRICS, per_sheet=400, em=1200)
        for s in big:
            w, h = s.size()
            self.assertLessEqual(w * h, fb.SHEET_PIXELS_MAX)
        self.assertEqual(sum(len(s.names) for s in big), 250)


class BandTests(unittest.TestCase):
    def test_the_payload_comes_back(self):
        sheet = sheet_of(index=1, count=3, family="Test")
        again = fb.Sheet.from_payload(fb.bits_payload(fb.band_bits(sheet.payload())))
        self.assertEqual((again.names, again.labels, again.em, again.columns, again.index, again.count, again.family),
                         (sheet.names, sheet.labels, sheet.em, sheet.columns, 1, 3, "Test"))
        self.assertEqual(again.metrics.as_list(), METRICS.as_list())
        self.assertEqual(again.size_units(), sheet.size_units())

    def test_a_flipped_bit_is_caught(self):
        bits = fb.band_bits(sheet_of().payload())
        bits[100] ^= 1
        self.assertIsNone(fb.bits_payload(bits))

    def test_the_bands_stay_clear_of_the_cells_and_finders(self):
        sheet = sheet_of()
        w, h = sheet.size_units()
        bits = len(fb.band_bits(sheet.payload()))
        top = fb.band_squares(w, h, 0, bits)
        bottom = fb.band_squares(w, h, 1, bits)
        grid_top = sheet.grid_origin()[1] / float(sheet.unit)
        grid_bottom = grid_top + sheet.rows * sheet.cell_size()[1] / float(sheet.unit)
        self.assertLess(max(y for _, y in top), grid_top)
        self.assertGreater(min(y for _, y in bottom), grid_bottom)
        self.assertGreaterEqual(min(x for x, _ in top), fb.margin_units())
        self.assertLessEqual(max(x for x, _ in top), w - fb.margin_units())


class GeometryTests(unittest.TestCase):
    def test_a_homography_maps_its_four_points(self):
        src = [(0, 0), (10, 0), (10, 5), (0, 5)]
        dst = [(3, 4), (100, 10), (95, 60), (0, 50)]
        h = fb.homography(src, dst)
        for (x, y), (u, v) in zip(src, dst):
            a, b = fb.apply(h, x, y)
            self.assertAlmostEqual(a, u, 6)
            self.assertAlmostEqual(b, v, 6)


class ReadTests(unittest.TestCase):
    def test_finders_are_found_in_an_upright_sheet(self):
        sheet = sheet_of(LATIN[:4])
        rows = raster(sheet, 3)
        found = fb.find_finders(rows)
        corners = fb.corner_finders(found, len(rows[0]), len(rows))
        self.assertIsNotNone(corners)
        expected = [(x * 3, y * 3) for x, y in fb.finder_centers(*sheet.size_units())]
        for (x, y, module, _), (ex, ey) in zip(corners, expected):
            self.assertLess(abs(x - ex), 2)
            self.assertLess(abs(y - ey), 2)
            self.assertAlmostEqual(module, 3, delta=0.6)

    def check_read(self, mapping, turn=0):
        sheet = sheet_of()
        w, h = sheet.size_units()
        centers = [fb.apply(mapping, x, y) for x, y in fb.finder_centers(w, h)]
        corners = centers[turn:] + centers[:turn]
        # (each finder's square as find_finders measures it, a little off)
        units = [1.02 * (fb.distance(fb.apply(mapping, x, y), fb.apply(mapping, x + 1, y)) +
                         fb.distance(fb.apply(mapping, x, y), fb.apply(mapping, x, y + 1))) / 2.0
                 for x, y in fb.finder_centers(w, h)]
        units = units[turn:] + units[:turn]
        found = fb.read_layout(corners, units, warped_sampler(sheet, mapping))
        self.assertIsNotNone(found)
        self.assertEqual(found.sheet.names, sheet.names)
        return found

    def test_a_sheet_reads_straight(self):
        found = self.check_read(fb.homography([(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (4, 0), (4, 4), (0, 4)]))
        x, y = found.to_image(*found.sheet.origin(0))
        ox, oy = found.sheet.origin(0)
        self.assertAlmostEqual(x, ox * 4.0 / found.sheet.unit, 3)

    def test_a_sheet_reads_turned_skewed_and_in_perspective(self):
        sheet = sheet_of()
        w, h = sheet.size_units()
        # (turned about 92 degrees, its far side shrunk by 6 %: a phone photo of a printed sheet)
        corners_image = [(900, 40), (930, 40 + 3.1 * w), (930 - 3.0 * h, 30 + 3.05 * w), (900 - 3.15 * h, 60)]
        mapping = fb.homography([(0, 0), (w, 0), (w, h), (0, h)], corners_image)
        self.check_read(mapping, turn=1)

    def test_the_bottom_band_reads_when_the_top_one_is_spoiled(self):
        sheet = sheet_of()
        w, h = sheet.size_units()
        mapping = fb.homography([(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (3, 0), (3, 3), (0, 3)])
        base = warped_sampler(sheet, mapping)
        spoiled_bottom = (fb.margin_units() + 6) * 3  # (a smear across the top band's first rows)

        def sample(x, y):
            if y < spoiled_bottom and fb.margin_units() * 3 < x < (w - fb.margin_units()) * 3:
                return 10
            return base(x, y)
        found = fb.read_layout([fb.apply(mapping, *c) for c in fb.finder_centers(w, h)], 3.0, sample)
        self.assertIsNotNone(found)
        self.assertEqual(found.band, 1)

    def test_nothing_reads_from_a_blank_image(self):
        self.assertIsNone(fb.read_layout([(10, 10), (500, 10), (500, 700), (10, 700)], 4.0, lambda x, y: 245, reach=2))


class GlyphListTests(unittest.TestCase):
    def test_characters_once_without_spaces(self):
        self.assertEqual(fb.characters_of("ab a\nc\U0001F600"), ["a", "b", "c", "\U0001F600"])

    def test_names_come_from_the_font_then_glyphs_names_then_uni(self):
        nice = {0xE9: "eacute", 0x0434: "de-cy"}
        glyphs = fb.template_glyphs(["a", "é", "д", "☃"], font_names=["a", "de-cy"],
                                    by_code={0x61: "a"}, nice=nice)
        self.assertEqual([n for n, _ in glyphs], ["a", "eacute", "uni0434", "uni2603"],
                         "de-cy is taken by another glyph of the font: uni0434")

    def test_glyphs_drawn_are_left_out_and_alternates_follow(self):
        glyphs = fb.template_glyphs(["a", "b"], font_names=["a"], by_code={0x61: "a"}, lacking={"a"}, alternates=1)
        self.assertEqual(glyphs, [("a.alt1", "a.alt1"), ("b", "b"), ("b.alt1", "b.alt1")])

    def test_code_points_of_names(self):
        nice = {0xE9: "eacute"}
        self.assertEqual(fb.code_for("uni00E9", nice), 0xE9)
        self.assertEqual(fb.code_for("u1F600", nice), 0x1F600)
        self.assertEqual(fb.code_for("eacute", nice), 0xE9)
        self.assertEqual(fb.code_for("a", nice), 0x61)
        self.assertEqual(fb.code_for("zero", nice), 0x30)
        self.assertEqual(fb.code_for("ampersand", nice), 0x26)
        self.assertEqual(fb.template_glyphs(["0", "&"]), [("zero", "0"), ("ampersand", "&")])
        self.assertIsNone(fb.code_for("a.alt1", nice))
        self.assertIsNone(fb.code_for("f_i", nice))

    def test_common_sets_come_first_in_their_own_order(self):
        names = ["Thai", "Arrows (Unicode block)", "GF Latin Core", "Hangul", "Adobe Latin 1"]
        self.assertEqual(fb.common_sets(names), [2, 4, 0, 3], "Latin first, then Thai, then Hangul")
        self.assertEqual(fb.common_sets(["Arrows (Unicode block)"]), [])


class SvgTests(unittest.TestCase):
    def test_an_svg_sheet_holds_the_raster_sheets_marks_and_boxes(self):
        import xml.etree.ElementTree as ET
        sheet = fb.split_sheets(["A", "uni00E9", "a.alt1"], ["A", "é", "a.alt1"], fb.Metrics(), em=200,
                                family="Test & <Sans>")[0]
        text = fb.sheet_svg(sheet)
        root = ET.fromstring(text.encode("utf-8"))
        width, height = sheet.size()
        self.assertEqual((root.get("width"), root.get("height")), (str(width), str(height)))
        ns = "{http://www.w3.org/2000/svg}"
        paths = root.findall(".//%spath" % ns)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].get("d").count("M"), len(fb.marks(sheet)), "every black square, finders and bands")
        boxes = [r for r in root.findall(".//%srect" % ns) if r.get("fill") != "#ffffff"]
        self.assertEqual(len(boxes), 3)
        self.assertIn("é", text)
        self.assertIsNotNone(root.find(".//%sg[@id='drawing']" % ns), "a layer to draw on")


class PlacementTests(unittest.TestCase):
    def square(self, x0, y0, side, clockwise=False):
        pts = [(x0, y0, "on"), (x0 + side, y0, "on"), (x0 + side, y0 + side, "on"), (x0, y0 + side, "on")]
        return list(reversed(pts)) if clockwise else pts

    def test_drawn_keeps_the_ink_and_mirrors_its_left_room(self):
        contours, advance = fb.placed([self.square(100, 0, 300)], "drawn", 1000)
        self.assertEqual(contours[0][0][:2], (100, 0))
        self.assertEqual(advance, 500)

    def test_even_sets_both_sides(self):
        contours, advance = fb.placed([self.square(100, 0, 300)], "even", 1000)
        self.assertEqual(min(x for x, _, _ in contours[0]), 50)
        self.assertEqual(advance, 400)

    def test_outer_contours_and_holes_turn_the_way_asked(self):
        outer = self.square(0, 0, 400)
        hole = self.square(100, 100, 200)  # (drawn the same way as the outer one: wrong for a hole)
        for clockwise_outer in (True, False):
            out = fb.oriented([outer, hole], clockwise_outer)
            self.assertEqual(fb.signed_area(out[0]) < 0, clockwise_outer)
            self.assertEqual(fb.signed_area(out[1]) < 0, not clockwise_outer)

    def test_the_ink_box_skips_guides_and_padding(self):
        width, stride, height = 10, 12, 6
        rows = [bytearray(b"\xff" * stride) for _ in range(height)]
        rows[1][2:9] = b"\xcd" * 7  # (a guide, gray 205: not ink)
        rows[2][3] = 0
        rows[4][6] = 40
        rows[3][11] = 0  # (past the width, in the row's padding: not the image's)
        data = b"".join(bytes(r) for r in rows)
        self.assertEqual(fb.ink_box(data, width, height, stride, 128), (3, 2, 7, 5))
        self.assertIsNone(fb.ink_box(b"\xff" * (stride * height), width, height, stride, 128))

    def test_a_cell_maps_to_units_through_its_origin(self):
        sheet = sheet_of()
        units, x0, y_top = fb.cell_mapping(sheet, 2, 2.0)
        left, top = sheet.cell(2)
        ox, oy = sheet.origin(2)
        # the origin's place in the cell image (scale 2) maps to (0, 0)
        px, py = (ox - left) * 2.0, (oy - top) * 2.0
        self.assertAlmostEqual(x0 + px * units, 0.0, 6)
        self.assertAlmostEqual(y_top - py * units, 0.0, 6)
        self.assertAlmostEqual(units * sheet.em * 2.0, sheet.metrics.upm)


class Box(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeLayer(object):
    def __init__(self, shapes=()):
        self.shapes, self.removals, self.advanceWidth = list(shapes), 0, 0

    def removeAllShapes(self):
        self.removals += 1
        self.shapes = []

    def addShape(self, shape):
        self.shapes.append(shape)

    def setGlyphComponents(self, *args):
        pass


class FakeGlyph(object):
    """An flGlyph (layers by master, fgGlyph.unicode) whose fontgate glyph (fg) is what the font's list
    holds (name, unicodes), as in FontLab."""

    def __init__(self, name, code=None):
        self.name = name
        self.layers = {}
        self.fgGlyph = self
        self.unicodes = [code] if code is not None else []

    @property
    def unicode(self):
        return self.unicodes[0] if self.unicodes else None

    @unicode.setter
    def unicode(self, code):
        self.unicodes = [code]

    def getLayerByName(self, master, create=False):
        if master not in self.layers and create:
            self.layers[master] = FakeLayer()
        return self.layers.get(master)


class FakePackage(object):
    def __init__(self, upm=1000):
        self.master, self.upm = "Regular", upm
        self.found = {}
        self.fgPackage = Box(id="fake", glyphs=[])

    def findName(self, name):
        return self.found.get(name)

    def addGlyph(self, glyph):
        glyph = FakeGlyph(glyph.name)  # (FontLab adds a copy)
        self.found[glyph.name] = glyph
        self.fgPackage.glyphs.append(glyph)


class FakeShape(object):
    def addContours(self, contours, *args):
        self.contours = contours


SQUARE = [(50, 0, "on"), (450, 0, "on"), (450, 700, "on"), (50, 700, "on")]


class BuildTests(unittest.TestCase):
    """build_glyphs on a fake font (review 9: stale checks, code points, units per em)."""

    def setUp(self):
        self.saved = (fb._qt, fb.nice_names, fb.made_contour, fb.is_postscript)
        fb._qt = lambda: (None, None)
        fb.nice_names = lambda: {}
        fb.made_contour = lambda host, nodes, core: nodes
        fb.is_postscript = lambda package: False
        self.logged = []

    def tearDown(self):
        fb._qt, fb.nice_names, fb.made_contour, fb.is_postscript = self.saved

    def dialog(self, package, drawn, replace=False):
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.busy, d.package = False, package
        d.current_font = lambda: package
        d.checked_drawn = lambda: drawn
        d.placement = Box(currentIndex=0)
        d.replace = Box(checked=replace)
        d.show_drawn = lambda: None
        d.log = Box(add=lambda text, level="info": self.logged.append(text))
        d.fontlab = Box(flGlyph=lambda: Box(name=None), flShape=FakeShape)
        status = Box(undo=lambda text: "", report=lambda log: None)
        self.progress = []
        d.ak = Box(begin_write=lambda *a, **k: True, notify_changed=lambda *a, **k: status, html=lambda s: s,
                   b=lambda s: "<b>%s</b>" % s, glyph_names_linked=shared_module().glyph_names_linked,
                   LOG_NAMES_LINKED=shared_module().LOG_NAMES_LINKED, font_key=lambda p: id(p), busy_start=lambda o, what="", stoppable=True: self.progress.append(
                       ("start", stoppable)),
                   busy_progress=lambda o, what=None, part=None, stoppable=True: self.progress.append(
                       ("step", stoppable)),
                   busy_end=lambda o: self.progress.append(("end", None)))
        d.read_for = d.target_key(package)
        return d

    def add(self, package, name, code=None, drawn=False):
        glyph = FakeGlyph(name, code)
        glyph.layers["Regular"] = FakeLayer(["ink"] if drawn else [])
        package.found[name] = glyph
        package.fgPackage.glyphs.append(glyph)
        return glyph

    def test_a_glyph_drawn_since_the_reading_is_kept_without_replace(self):
        p = FakePackage()
        glyph = self.add(p, "A", 0x41)
        d = self.dialog(p, [fb.Drawn("A", "A", "sheet", contours=[SQUARE])])
        glyph.layers["Regular"].shapes.append("drawn after the reading")
        d.build_glyphs()
        self.assertEqual(glyph.layers["Regular"].removals, 0)
        self.assertTrue(any("Left as drawn" in line for line in self.logged))
        # The glyph's name in italics, a link that opens it (owner's request of 2026-11-24)
        self.assertIn(u'redraw them): <a href="glyphname:A"><i>A</i></a>.', [line for line in self.logged
                                                                             if "Left as drawn" in line][0])

    def test_a_long_list_of_glyphs_left_is_cut_in_the_log(self):
        p = FakePackage()
        names = ["g%d" % n for n in range(shared_module().LOG_NAMES_LINKED + 2)]
        for name in names:
            self.add(p, name, drawn=True)
        d = self.dialog(p, [fb.Drawn(name, name, "sheet", contours=[SQUARE]) for name in names])
        d.build_glyphs()
        line = [line for line in self.logged if "Left as drawn" in line][0]
        self.assertEqual(line.count("<a href="), shared_module().LOG_NAMES_LINKED)
        self.assertTrue(line.endswith(", and 2 more."), line)

    def test_a_build_shows_its_progress_and_is_never_stopped_half_way(self):
        p = FakePackage()
        self.add(p, "A", 0x41)
        d = self.dialog(p, [fb.Drawn("A", "A", "sheet", contours=[SQUARE])])
        d.build_glyphs()
        self.assertEqual(self.progress[0], ("start", False), "one History step: not stoppable")
        self.assertTrue(all(s is False for kind, s in self.progress if kind == "step"))
        self.assertEqual(self.progress[-1], ("end", None))
        self.assertFalse(d.busy)

    def test_another_master_since_the_reading_builds_nothing(self):
        p = FakePackage()
        glyph = self.add(p, "A", 0x41)
        d = self.dialog(p, [fb.Drawn("A", "A", "sheet", contours=[SQUARE])])
        p.master = "Bold"
        d.build_glyphs()
        self.assertEqual(glyph.layers, {"Regular": glyph.layers["Regular"]})
        self.assertTrue(any("Read sheets" in line for line in self.logged))

    def test_a_drawing_goes_into_the_glyph_that_has_its_code_point(self):
        p = FakePackage()
        owner = self.add(p, "uni0041", 0x41)
        self.dialog(p, [fb.Drawn("A", "A", "sheet", contours=[SQUARE])]).build_glyphs()
        self.assertIsNone(p.findName("A"), "no second glyph for U+0041")
        self.assertEqual(len(owner.layers["Regular"].shapes), 1)

    def test_a_custom_name_keeps_its_cells_code_point(self):
        p = FakePackage()
        self.dialog(p, [fb.Drawn("customA", "A", "sheet", contours=[SQUARE])]).build_glyphs()
        self.assertEqual(p.findName("customA").unicode, 0x41)

    def test_a_character_drawn_twice_is_built_once(self):
        # (review 10: the second drawing replaced the first, Replace off; two names for one character too)
        p = FakePackage()
        other = [(60, 0, "on"), (300, 0, "on"), (300, 300, "on")]
        drawn = [fb.Drawn("A", "A", "sheet 1", contours=[SQUARE]), fb.Drawn("customA", "A", "sheet 2", contours=[other]),
                 fb.Drawn("A", "A", "sheet 3", contours=[other])]
        self.dialog(p, drawn).build_glyphs()
        self.assertEqual(p.findName("A").unicode, 0x41)
        self.assertIsNone(p.findName("customA"))
        layer = p.findName("A").layers["Regular"]
        self.assertEqual(layer.removals, 1)
        self.assertEqual(len(layer.shapes[0].contours[0]), 4, "the first drawing")
        self.assertTrue(any("more than once" in line for line in self.logged))

    def test_a_name_held_by_another_character_is_not_drawn_into(self):
        # (review 10: a source font's B for A, here B at U+0042)
        p = FakePackage()
        b = self.add(p, "B", 0x42)
        self.dialog(p, [fb.Drawn("B", "A", "sheet", contours=[SQUARE])]).build_glyphs()
        self.assertEqual(b.layers["Regular"].removals, 0)
        self.assertEqual(b.unicode, 0x42)
        self.assertEqual(p.findName("uni0041").unicode, 0x41, "into the character's own uni name")

    def test_an_unencoded_glyph_of_the_name_takes_the_character(self):
        p = FakePackage()
        glyph = self.add(p, "A")
        self.dialog(p, [fb.Drawn("A", "A", "sheet", contours=[SQUARE])]).build_glyphs()
        self.assertEqual(glyph.unicode, 0x41)

    def test_a_dotted_name_keeps_its_labels_character(self):
        self.assertEqual(fb.cell_code("A.display", "A"), 0x41)
        self.assertIsNone(fb.cell_code("A.display.alt1", "A.alt1"))

    def test_ink_scales_to_the_fonts_units(self):
        p = FakePackage(2048)
        self.dialog(p, [fb.Drawn("A", "A", "sheet", contours=[SQUARE], upm=1000)]).build_glyphs()
        made = p.findName("A").layers["Regular"].shapes[0].contours
        self.assertAlmostEqual(max(y for c in made for _, y, _ in c), 700 * 2.048)

    def test_cell_codes_and_targets(self):
        self.assertEqual(fb.cell_code("customA", "A"), 0x41)
        self.assertIsNone(fb.cell_code("a.alt1", "a.alt1"))
        self.assertEqual(fb.target_name("A", 0x41, {0x41: "uni0041"}), "uni0041")
        self.assertEqual(fb.target_name("A", 0x41, {}), "A")

    def test_image_ink_leaves_guides_and_paper_clear(self):
        table = fb.alpha_table(128)
        self.assertEqual(table[0], 255)
        self.assertEqual(table[205], 0, "a guide")
        self.assertEqual(table[240], 0, "scanned paper")
        self.assertTrue(0 < table[128] < 255, "an antialiased edge")
        for threshold in (160, 180, fb.THRESHOLD_MAX):  # (review 10: at 180 a guide came back as faint ink)
            self.assertEqual(fb.alpha_table(threshold)[fb.GUIDE_GRAY], 0)
            self.assertEqual(fb.alpha_table(threshold)[0], 255)

    def test_the_guides_gray_is_what_qt_makes_of_their_color(self):
        r, g, b = fb.GUIDE_RGB
        self.assertEqual((11 * r + 16 * g + 5 * b) // 32, fb.GUIDE_GRAY)
        self.assertLessEqual(fb.THRESHOLD_MAX, fb.GUIDE_GRAY - 15)


class FakeLine(object):
    """A QHBoxLayout as FlowRow uses it: its widgets in order (its trailing stretch left out)."""

    def __init__(self, parent=None):
        self.items = []

    def setContentsMargins(self, *args):
        pass

    def setSpacing(self, spacing):
        self.spacing = spacing

    def addStretch(self, factor=0):
        pass

    def addWidget(self, widget, *args):
        self.items.append(widget)

    def addLayout(self, layout, *args):
        self.items.append(layout)

    def removeWidget(self, widget):
        if widget in self.items:
            self.items.remove(widget)

    def insertWidget(self, index, widget):
        self.items.insert(index, widget)


class FakeWidget(object):
    def __init__(self, *args):
        self.width = 0
        self.hint = 0

    def setSizePolicy(self, *args):
        pass

    def installEventFilter(self, watcher):
        pass

    @property
    def sizeHint(self):
        return Box(width=self.hint)


class FakeTimer(object):
    def __init__(self, parent=None):
        pass

    def setSingleShot(self, on):
        pass

    def setInterval(self, ms):
        pass

    def connect(self, signal, slot):
        self.slot = slot


class FontLabCallTests(unittest.TestCase):
    def test_a_new_fonts_master_calls_are_those_fontlab_takes(self):
        # (live, 2026-11-18: addMaster refused None as its source font, and flPackage.master is read-only)
        import io
        with io.open(os.path.join(HERE, os.pardir, "builder", "freelab_font_builder.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("addMaster(\"Regular\", False, None", source)
        self.assertIn("package.addMaster(\"Regular\", False, package,", source)
        self.assertNotIn("package.master = ", source)


class UiRoundTests(unittest.TestCase):
    """The owner's UI round of 2026-11-17 (images 216, 239 to 241, 266 to 268, 274, 280) on Font Builder."""

    def setUp(self):
        self.saved = fb._qt
        gui = Box(QWidget=FakeWidget, QVBoxLayout=FakeLine, QHBoxLayout=FakeLine,
                  QSizePolicy=Box(Ignored=0, Preferred=1))
        fb._qt = lambda: (Box(QTimer=FakeTimer), gui)

    def tearDown(self):
        fb._qt = self.saved

    def test_a_row_of_options_flows_onto_as_few_lines_as_its_width_allows(self):
        """Images 241, 266, 267: the options and their run button on one line where the window is wide
        enough; on a narrow window (a tiny screen), wrapped onto more lines, in their order, nothing lost."""
        self.assertEqual(fb.flow_rows([200, 100, 150, 120, 110], 2000, 16), [5])
        self.assertEqual(fb.flow_rows([200, 100, 150, 120, 110], 500, 16), [3, 2], "200+16+100+16+150 = 482")
        self.assertEqual(fb.flow_rows([200, 100, 150, 120, 110], 482, 16), [3, 2], "exactly the room: it fits")
        self.assertEqual(fb.flow_rows([200, 100, 150], 150, 16), [1, 1, 1], "one a line at least, wider or not")
        self.assertEqual(fb.flow_rows([200, 100], 0, 16), [2], "not laid out yet: one line")
        self.assertEqual(fb.flow_rows([], 500), [])
        groups = [["a"], ["b", "B"], ["c"], ["d"]]
        row = fb.FlowRow(groups, spacing=10)
        made = row.groups
        self.assertEqual([len(line.items) for line in row.lines], [4, 0, 0, 0], "one line to start with")
        for group, hint in zip(made, (300, 200, 100, 120)):
            group.hint = hint
        row.widget.width = 400  # (300 alone; 200, 100; 120)
        row.fit()
        self.assertEqual([line.items for line in row.lines], [[made[0]], [made[1], made[2]], [made[3]], []])
        row.widget.width = 2000
        row.fit()
        self.assertEqual([line.items for line in row.lines], [made, [], [], []], "wide again: one line, in order")
        self.assertEqual(sum(len(line.items) for line in row.lines), 4, "no group lost or twice")
        self.assertEqual(row.lines[0].spacing, 10)

    def test_the_header_and_bottom_row_parts_follow_the_tab(self):
        """Image 240: the template's status sits under the top line (the Template tab's only); the Build
        tab's committing button in the bottom row, shown with its tab."""
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        calls = []

        class Recorder(object):
            text = "No glyph to draw."

            def __getattr__(self, name):
                return lambda *args: calls.append((name, args))

        d.pages, d.summary, d.build_button = Recorder(), Recorder(), Recorder()
        d.ak = Box(BUSY_LINE_PROP="freelabBusyLine")
        d.tab_changed(1)
        self.assertIn(("setHidden", (True,)), calls)
        self.assertIn(("setProperty", ("freelabBusyLine", True)), calls, "kept hidden as it is written meanwhile")
        self.assertIn(("setVisible", (True,)), calls, "Build ticked glyphs shown")
        del calls[:]
        d.tab_changed(0)
        self.assertIn(("setHidden", (False,)), calls)
        self.assertIn(("setProperty", ("freelabBusyLine", None)), calls)
        self.assertIn(("setVisible", (False,)), calls)

    def test_a_tab_switch_hides_the_other_tabs_buttons_first(self):
        """Round 3's convention 24 (owner's image 284): the bottom row's buttons swapped through the shared
        show_only, which hides the other tab's before it shows this one's (shown first, the row held both a
        moment and Qt widened the window for good)."""
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        swaps = []

        class Quiet(object):
            text = ""

            def __getattr__(self, name):
                return lambda *args: None

        d.pages, d.summary, d.build_button = Quiet(), Quiet(), Quiet()
        d.ak = Box(BUSY_LINE_PROP="freelabBusyLine", show_only=lambda groups, shown: swaps.append((groups, shown)))
        d.tab_changed(1)
        d.tab_changed(0)
        self.assertEqual([shown for _, shown in swaps], [1, 0])
        self.assertEqual(swaps[0][0], {0: [], 1: [d.build_button]}, "Build ticked glyphs is the Build tab's")

    def test_the_rows_above_the_tabs_frames_are_as_tall(self):
        """Round 3's convention 23 (owner's images 285 and 286): the Template tab's row (a dropdown) and the
        Build tab's (two buttons) made as tall as the taller, so the frame under them never shifts as the tabs
        switch; again at each switch and as the window shows."""

        class Bar(object):
            def __init__(self, height):
                self.hint, self.minimumHeight, self.set = height, 0, []

            def sizeHint(self):
                return Box(height=lambda: self.hint)

            def setMinimumHeight(self, height):
                self.minimumHeight = height
                self.set.append(height)

        dropdown, buttons = Bar(24), Bar(21)
        self.assertEqual(fb.even_height([dropdown, None, buttons]), 24)
        self.assertEqual((dropdown.minimumHeight, buttons.minimumHeight), (24, 24))
        fb.even_height([dropdown, buttons])
        self.assertEqual((dropdown.set, buttons.set), ([24], [24]), "set once, not at every switch")
        self.assertIsNone(fb.even_height([None]))
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.template_bar, d.build_bar = Bar(20), Bar(26)
        d.even_rows()
        self.assertEqual((d.template_bar.minimumHeight, d.build_bar.minimumHeight), (26, 26))
        import io
        with io.open(os.path.join(HERE, os.pardir, "builder", "freelab_font_builder.py"), encoding="utf-8") as handle:
            source = handle.read()
        for bar in ("self.template_bar = QtGui.QWidget()", "self.build_bar = QtGui.QWidget()"):
            self.assertIn(bar, source)
        self.assertIn("self.even_rows()  # (again in the window's own style", source)

    def test_the_new_fonts_units_are_bold_with_their_noun(self):
        """Round 3's convention 18: a count bold with its noun ("1,000 units per em": the number was plain)."""
        ak = Box(b=lambda text: "<b>%s</b>" % text)
        self.assertEqual(fb.new_font_line(ak, "Hand", 1000.0),
                         "Made a new font, <b>Hand</b>: <b>1,000 units</b> per em, the sheets' metrics.")

    def test_the_no_font_line_is_one_line_and_says_a_built_font_is_hooked(self):
        """Images 274 and 280: "This window hooks to the next font you open (or build here)", one line."""
        self.assertEqual(fb.NO_FONT_TEXT, "No font is open. This window hooks to the next font you open (or build "
                                          "here). A template can still be made, with default metrics.")
        asked = []
        ak = Box(no_font_line=lambda own=None: asked.append(own) or own)
        self.assertEqual(fb.no_font_text(ak), fb.NO_FONT_TEXT)
        self.assertEqual(asked, [fb.NO_FONT_TEXT], "the tool's own line, which ak.one_line keeps on one line")
        waiting = Box(no_font_line=lambda own=None: "This window has no font: the font open has a window of its own.")
        self.assertTrue(fb.no_font_text(waiting).endswith("A template can still be made, with default metrics."))
        named = Box(font_named=lambda name, master, masters: "%s/%s/%d" % (name, master, masters), b=lambda s: s)
        package = Box(tfn="Cardo", master="Bold", masters=["Regular", "Bold"])
        self.assertEqual(fb.font_text(named, package), "Cardo/Bold/2: its metrics shape the template's boxes.")

    def test_a_font_built_with_no_font_open_is_this_windows(self):
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        built = Box(fgPackage=Box(id=7))
        shown = Box(currentPackage=built)
        d.fontlab = Box(flWorkspace=Box(instance=lambda: shown))
        d.current_font = lambda: built
        d.summary_soon = lambda: None
        d.package = None
        self.assertTrue(d.hook_built_font(built))
        self.assertIs(d.package, built)
        d.package = None
        shown.currentPackage = Box(fgPackage=Box(id=8))
        self.assertFalse(d.hook_built_font(built), "FontLab shows another font: never that one")
        self.assertIsNone(d.package)
        d.font_id = 3
        shown.currentPackage = built
        self.assertFalse(d.hook_built_font(built), "a window with a font keeps it")

    def test_no_space_before_a_percent_sign_and_thousands_grouped(self):
        """Image 216: "5 % of the em" in the Glyphs placed dropdown's help."""
        import io
        with io.open(os.path.join(HERE, os.pardir, "builder", "freelab_font_builder.py"), encoding="utf-8") as handle:
            source = handle.read()
        import re
        # (a number then a space and a percent sign that is no format's: "5 % of", "6 %)")
        self.assertEqual(re.findall(r"\d %(?![sdr0-9.(])", source), [], "a number and its percent sign kept together")
        self.assertIn('Even: both sides %d%% of the em', source, "the dropdown's help: 5% of the em")
        self.assertEqual(fb.EVEN_SIDE, 0.05)
        self.assertEqual(fb.counted(13932, "glyph"), "13,932 glyphs")
        self.assertEqual(fb.counted(1, "sheet"), "1 sheet")


def shared_module():
    """FreeLab's shared module (Auto Kerning's), as the tools load it: its dialog not opened."""
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    folder = os.path.join(HERE, os.pardir, "kerning")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import freelab_auto_kerning
    return freelab_auto_kerning


class FakeImage(object):
    """A QImage: made at a size (width, height, format), or read from a path FILES knows ((width, height, has
    alpha); any other path reads as a null image)."""
    Format_RGB32 = 4
    FILES = {}

    def __init__(self, *args):
        self.args, self.filled, self.drawn = args, None, []
        if len(args) == 3:
            self.w, self.h, self.alpha, self.null = args[0], args[1], False, False
        else:
            spec = self.FILES.get(args[0]) if args else None
            self.null = spec is None
            self.w, self.h, self.alpha = spec or (0, 0, False)

    def isNull(self):
        return self.null

    def width(self):
        return self.w

    def height(self):
        return self.h

    def hasAlphaChannel(self):
        return self.alpha

    def fill(self, color):
        self.filled = color


class FakePainter(object):
    Antialiasing = 1

    def __init__(self, image):
        self.image, self.ended = image, False

    def setRenderHint(self, *args):
        pass

    def drawImage(self, x, y, image):
        self.image.drawn.append(image)

    def end(self):
        self.ended = True


class FakeRenderer(object):
    VALID = set()
    rendered = []

    def __init__(self, path):
        self.path = path

    def isValid(self):
        return self.path in self.VALID

    def defaultSize(self):
        return Box(width=lambda: 120, height=lambda: 90)

    def render(self, painter, rect):
        FakeRenderer.rendered.append((self.path, rect, painter.image))


class FakeReader(object):
    scaled = []

    def __init__(self, path):
        self.path = path

    def setScaledSize(self, size):
        FakeReader.scaled.append(size)

    def read(self):
        return FakeImage(self.path)


class SheetFileTests(unittest.TestCase):
    """The sheets' files: the save dialog's type (owner's image 374), the sheets picked (image 376: one file read
    as 20 sheets, a character each), SVG sheets read back, and the log's link to the folder (image 375)."""

    def setUp(self):
        self.saved = (fb._qt, fb.write_settings, sys.modules.get("PythonQt", "absent"))
        sys.modules["PythonQt"] = None  # (no PythonQt here: QtSvg is looked for in the Qt module given)
        fb.write_settings = lambda ak, data: None  # (never this machine's settings file)
        import tempfile
        import shutil
        self.folder = tempfile.mkdtemp(prefix="freelab-sheets-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        FakeImage.FILES, FakeRenderer.VALID = {}, set()
        del FakeRenderer.rendered[:], FakeReader.scaled[:]

    def tearDown(self):
        fb._qt, fb.write_settings = self.saved[:2]
        if self.saved[2] == "absent":
            sys.modules.pop("PythonQt", None)
        else:
            sys.modules["PythonQt"] = self.saved[2]

    def write(self, name, text):
        import io
        path = os.path.join(self.folder, name)
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_the_files_picked_are_paths_whatever_form_the_dialog_gives(self):
        path = "C:/Temp/Sheets/Your-Highschool-Crush.svg"
        self.assertEqual(fb.picked_paths((path,)), [path], "PythonQt's tuple of one: one path, not its characters")
        self.assertEqual(fb.picked_paths((path, "C:/Temp/Sheets/b.png")), [path, "C:/Temp/Sheets/b.png"], "two files")
        self.assertEqual(fb.picked_paths(path), [path], "a string")
        self.assertEqual(fb.picked_paths([path]), [path])
        self.assertEqual(fb.picked_paths(([path], "Images (*.png *.svg)")), [path], "PyQt's (files, filter)")
        self.assertEqual(fb.picked_paths(([], "Images (*.png)")), [])
        for nothing in (None, "", (), []):
            self.assertEqual(fb.picked_paths(nothing), [])
        self.assertEqual(fb.picked_path(path), path)
        self.assertEqual(fb.picked_path((path, "SVG drawings (*.svg)")), path, "PyQt's (path, filter)")
        self.assertEqual(fb.picked_path(""), "")

    def test_one_sheet_picked_is_one_row(self):
        picked = ("C:/Temp/Sheets/Your-Highschool-Crush.svg",)  # (what PythonQt gives for one file)
        rows = []
        gui = Box(QFileDialog=Box(getOpenFileNames=lambda *args: picked), QTreeWidgetItem=lambda texts: texts)
        fb._qt = lambda: (None, gui)
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.settings, d.files, d.dialog, d.ak = {}, [], None, None
        d.sheet_list = Box(addTopLevelItem=rows.append)
        d.update_buttons = lambda: None
        d.add_sheets()
        self.assertEqual(d.files, list(picked))
        self.assertEqual(rows, [["Your-Highschool-Crush.svg", "", "", "not yet"]])
        self.assertEqual(d.settings["read_folder"], "C:/Temp/Sheets")

    def test_the_template_saves_as_svg_unless_another_type_is_picked(self):
        asked = []
        gui = Box(QFileDialog=Box(getSaveFileName=lambda *args: asked.append(args) or ""))
        fb._qt = lambda: (None, gui)
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.settings, d.dialog, d.ak = {"folder": self.folder}, None, shared_module()
        d.sheets = lambda: [fb.Sheet(["A"], ["A"], METRICS, 150, family="Your Highschool Crush")]
        d.save_template()  # (the dialog canceled: nothing written)
        name, filters = asked[0][2], asked[0][3]
        self.assertEqual(os.path.basename(name), "Your-Highschool-Crush.svg")
        self.assertTrue(filters.startswith("SVG drawings (vector) (*.svg);;"), filters)
        self.assertEqual(filters.split(";;"), ["SVG drawings (vector) (*.svg)", "PNG images (*.png)",
                                               "TIFF images (*.tif *.tiff)", "Photoshop documents (layered) (*.psd)"])
        self.assertEqual(asked[0][4:], (None, 4), "asked not to confirm a replace (QFileDialog::DontConfirmOverwrite)")
        self.assertEqual(fb.template_ext("C:/Temp/a/sheet.PNG"), ("C:/Temp/a/sheet", ".png"))
        self.assertEqual(fb.template_ext("C:/Temp/a/sheet.tiff"), ("C:/Temp/a/sheet", ".tiff"))
        self.assertEqual(fb.template_ext("C:/Temp/a/sheet.PSD"), ("C:/Temp/a/sheet", ".psd"))
        sheets = [fb.Sheet(["A"], ["A"], METRICS, 150, index=i, count=2) for i in range(2)]
        self.assertEqual(fb.sheet_names(sheets, "C:/Temp/a/Hand", ".psd"),
                         ["C:/Temp/a/Hand-1-of-2.psd", "C:/Temp/a/Hand-2-of-2.psd"])
        self.assertEqual(fb.template_ext("C:/Temp/a/sheet"), ("C:/Temp/a/sheet", ".svg"), "no type typed: SVG")
        self.assertEqual(fb.template_ext("C:/Temp/a/Hand.v2"), ("C:/Temp/a/Hand.v2", ".svg"), "a dot in the name kept")

    def test_each_file_types_label_still_gives_its_extension(self):
        """The owner's labels of 2026-11-24 hold two groups in parentheses ("SVG drawings (vector) (*.svg)"): Qt's
        own regular expression takes the last as the patterns (greedy on the name), as Windows' dialog helper takes
        the text after the last "(", so each label's type still gives its extension, and a name typed with it is
        written in its format."""
        import re
        for ext, label in fb.TEMPLATE_FORMATS:
            patterns = fb.filter_patterns(label)
            self.assertEqual(patterns.split()[0], "*" + ext, label)
            name = fb.QT_FILTER.match(label).group(1)
            self.assertNotIn("*", name, "the name keeps no pattern")
            windows = label[label.rindex("(") + 1:label.index(")", label.rindex("("))]
            self.assertEqual(windows, patterns, "Windows' helper reads the same patterns")
            for pattern in patterns.split():
                self.assertEqual(fb.template_ext("C:/Temp/a/Hand" + pattern[1:])[1], pattern[1:], label)
        self.assertEqual([fb.QT_FILTER.match(label).group(1).strip() for _, label in fb.TEMPLATE_FORMATS],
                         ["SVG drawings (vector)", "PNG images", "TIFF images", "Photoshop documents (layered)"])
        # (the expression as Qt 5.14 writes it, qplatformdialoghelper.cpp)
        self.assertEqual(fb.QT_FILTER.pattern, r"^(.*)\(([a-zA-Z0-9_.,*? +;#\-\[\]@\{\}/!<>\$%&=^~:\|]*)\)$")
        self.assertIsNone(re.search(r"layers|for vector apps", fb.template_filter()))

    def saving_dialog(self, answer, sheets=2, ext=".svg", options=True, gui=None):
        """A dialog that saves sheets of "A" as Hand.svg (or ext), its question answered with answer ("Replace", or
        None for Cancel); options False: a PythonQt whose save dialog takes no options (ak.save_file_name falls
        back to the plain call, and Windows' own box asks of the name typed). (the dialog, what was asked, what was
        logged)."""
        asked, logged = [], []

        class Box_(object):
            AcceptRole, RejectRole, Cancel, Warning = "accept", "reject", "cancel", "warning"

            def __init__(self, parent):
                self.buttons, self.clicked = {}, None

            def setText(self, text):
                asked.append(text)

            def addButton(self, label, role=None):
                button = object()
                self.buttons[button] = "reject" if label == "cancel" else role
                if label == answer:
                    self.clicked = button
                return button

            def exec_(self):
                if self.clicked is None:
                    self.clicked = [b for b, role in self.buttons.items() if role == "reject"][0]

            def clickedButton(self):
                return self.clicked

            def buttonRole(self, button):
                return self.buttons[button]

            def __getattr__(self, name):
                return lambda *args: None
        stem = os.path.join(self.folder, "Hand")

        def dialog(*args):
            if len(args) > 4 and not options:
                raise ValueError("Could not find matching overload for given arguments")
            return stem + ext
        qt = Box(QFileDialog=Box(getSaveFileName=dialog), QMessageBox=Box_)
        qt.__dict__.update(gui or {})
        fb._qt = lambda: (None, qt)
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.settings, d.dialog, d.typed = {"folder": self.folder}, None, Box(toPlainText=lambda: "A")
        d.alternates = d.per_sheet = d.em = Box(value=1)
        d.guide_box = Box(checked=False)  # (the sheets as before guides: no FreeLang to register here)
        self.marked = []  # (FreeLab MCP's conventions: the question FreeLab's own, its Replace risky)
        self.progress = []
        d.ak = Box(busy_start=lambda *a: None, busy_end=lambda *a: None,
                   busy_progress=lambda o, what=None, part=None: self.progress.append(part),
                   Stopped=KeyboardInterrupt, html=lambda s: s, b=lambda s: s,
                   mcp_script_window=lambda w: self.marked.append(("script", w)) or w,
                   mark_risky=lambda w: self.marked.append(("risky", w)) or w,
                   save_file_name=shared_module().save_file_name, file_size_text=shared_module().file_size_text)
        d.log = Box(add=lambda text, level="info": logged.append((level, text)))
        d.sheets = lambda: [fb.Sheet(["A"], ["A"], METRICS, 150, index=i, count=sheets) for i in range(sheets)]
        return d, asked, logged

    def read(self, name):
        import io
        with io.open(os.path.join(self.folder, name), encoding="utf-8") as handle:
            return handle.read()

    def test_numbered_sheets_already_there_are_asked_of_before_any_is_replaced(self):
        """Saving the template again as Hand.svg replaced Hand-2-of-2.svg, drawn in place, with an empty sheet
        without a word: the dialog asked of Hand.svg, which was never written (adversarial review 2). Every file
        the save would replace is named in one question; Cancel leaves them all as they were."""
        self.write("Hand-2-of-2.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog(None)
        d.save_template()
        self.assertEqual(asked, ["Hand-2-of-2.svg already exists. Replace it with a new sheet?"])
        self.assertEqual([kind for kind, _w in self.marked], ["script", "risky"],
                         "FreeLab's own question for FreeLab MCP, its Replace needing risky mode")
        self.assertEqual(self.read("Hand-2-of-2.svg"), "OWNER DRAWING", "canceled: left as it was")
        self.assertFalse(os.path.exists(os.path.join(self.folder, "Hand-1-of-2.svg")), "and nothing else written")
        self.assertEqual(logged, [("warning", "The operation was interrupted. Nothing was saved or overwritten.")])
        self.write("Hand-1-of-2.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog("Replace")
        d.save_template()
        self.assertEqual(asked, ["Hand-1-of-2.svg and Hand-2-of-2.svg already exist. Replace them with new sheets?"],
                         "one question for both")
        for name in ("Hand-1-of-2.svg", "Hand-2-of-2.svg"):
            self.assertIn("<svg", self.read(name))
        self.assertEqual(sorted(os.listdir(self.folder)), ["Hand-1-of-2.svg", "Hand-2-of-2.svg"], "nothing left beside")
        self.assertEqual(logged[-1][0], "done")

    def test_the_name_typed_is_asked_of_by_freelab_unless_windows_asked(self):
        """Windows' own "Confirm Save As" box is light in dark mode (owner's report, 2026-11-24): the dialog is told
        not to ask, and FreeLab's own question names the file typed too, once. Where this PythonQt takes no options,
        Windows' box asked of it, as before, and FreeLab asks of the others only."""
        self.write("Hand.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog(None, sheets=1)
        d.save_template()
        self.assertEqual(asked, ["Hand.svg already exists. Replace it with a new sheet?"])
        self.assertEqual([kind for kind, _w in self.marked], ["script", "risky"])
        self.assertEqual(self.read("Hand.svg"), "OWNER DRAWING", "canceled: left as it was")
        self.assertEqual(logged, [("warning", "The operation was interrupted. Nothing was saved or overwritten.")])
        d, asked, logged = self.saving_dialog("Replace", sheets=1)
        d.save_template()
        self.assertEqual(len(asked), 1, "asked once")
        self.assertIn("<svg", self.read("Hand.svg"))
        # Options refused: the plain call, Windows' box asked of Hand.svg, FreeLab asks nothing more
        self.write("Hand.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog(None, sheets=1, options=False)
        d.save_template()
        self.assertEqual(asked, [])
        self.assertIn("<svg", self.read("Hand.svg"))
        # (and of the numbered sheets, which Windows never asked of, as before)
        self.write("Hand-2-of-2.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog(None, options=False)
        d.save_template()
        self.assertEqual(asked, ["Hand-2-of-2.svg already exists. Replace it with a new sheet?"])
        # Every sheet's file there, with options taken: one question for all (Hand.svg, not written, not named)
        self.write("Hand-1-of-2.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog(None)
        d.save_template()
        self.assertEqual(len(asked), 1)
        self.assertIn("Hand-1-of-2.svg and Hand-2-of-2.svg already exist", asked[0])
        self.assertEqual(fb.files_to_replace([os.path.join(self.folder, "Hand.svg")], None),
                         [os.path.join(self.folder, "Hand.svg")], "None: none was asked of")
        self.assertEqual(fb.files_to_replace([os.path.join(self.folder, "Hand.svg")],
                                             os.path.join(self.folder, "Hand.svg")), [])

    def test_tiff_sheets_are_written_with_lzw_and_png_as_before(self):
        """QImage.save wrote TIFF uncompressed: a sheet of 7,518 by 9,996 pixels took 220 MB, 1.6 MB with LZW
        (measured live in FontLab's Qt 5.14). The format named, as the staged file's name ends in .part.tif."""
        writers, saved = [], []

        class Writer(object):
            def __init__(self, path, kind):
                self.calls = [("made", os.path.basename(path).endswith(".part.tif"), kind)]
                self.path = path
                writers.append(self)

            def setCompression(self, value):
                self.calls.append(("compression", value))

            def write(self, image):
                self.calls.append(("write", image))
                with open(self.path, "w") as handle:
                    handle.write("TIFF")
                return True

        class Image(object):
            def save(self, path):
                saved.append(path)
                with open(path, "w") as handle:
                    handle.write("PNG")
                return True
        image = Image()
        real = fb.render_sheet
        fb.render_sheet = lambda sheet, core, gui, guides=None: image
        try:
            d, asked, logged = self.saving_dialog(None, sheets=1, ext=".tif", gui={"QImageWriter": Writer})
            d.save_template()
            self.assertEqual([w.calls for w in writers], [[("made", True, "tiff"), ("compression", 1), ("write", image)]])
            self.assertEqual(saved, [], "never QImage.save")
            self.assertEqual(self.read("Hand.tif"), "TIFF")
            d, asked, logged = self.saving_dialog(None, sheets=1, ext=".png", gui={"QImageWriter": Writer})
            d.save_template()
            self.assertEqual(len(writers), 1)
            self.assertEqual(len(saved), 1, "PNG as before")
            self.assertEqual(self.read("Hand.png"), "PNG")
        finally:
            fb.render_sheet = real
        self.assertEqual(sorted(os.listdir(self.folder)), ["Hand.png", "Hand.tif"], "nothing staged left")

    def test_a_psd_template_is_written_in_layers_from_the_painted_sheet(self):
        """Save template as PSD: render_sheet's picture read row by row through ctypes (its Format_RGB32 bytes, B,
        G, R, 255, rows bytesPerLine apart, here a bytearray standing for QImage.bits()), written whole beside
        the file first, with the bar's progress per band of rows."""
        class Picture(object):
            def __init__(self, rows, pad=8):
                self.w, self.h = len(rows[0]) // 4, len(rows)
                self.stride = 4 * self.w + pad  # (rows further apart than their pixels: bytesPerLine is the step)
                self.data = bytearray(b"".join(row + b"\x77" * pad for row in rows))

            def width(self):
                return self.w

            def height(self):
                return self.h

            def bytesPerLine(self):
                return self.stride

            def bits(self):
                return self.data
        pictures = []

        def render(sheet, core, gui, guides=None):
            pictures.append(sheet_picture(sheet))
            return Picture(pictures[-1])
        real = fb.render_sheet
        fb.render_sheet = render
        try:
            self.write("Hand-1-of-2.psd", "OWNER DRAWING")
            d, asked, logged = self.saving_dialog("Replace", ext=".psd")
            d.save_template()
        finally:
            fb.render_sheet = real
        self.assertEqual(len(asked), 1, "the sheet there asked of")
        self.assertEqual(sorted(os.listdir(self.folder)), ["Hand-1-of-2.psd", "Hand-2-of-2.psd"], "nothing staged left")
        self.assertEqual(logged[-1][0], "done")
        import io
        for k, name in enumerate(("Hand-1-of-2.psd", "Hand-2-of-2.psd")):
            with io.open(os.path.join(self.folder, name), "rb") as handle:
                psd = parse_psd(handle.read(), self)
            self.assertEqual(psd["picture"], planes_of(pictures[k]), name)
            self.assertEqual([layer["name"] for layer in psd["layers"]],
                             [b"Marks (keep visible)", b"Template (can be hidden)", b"Draw here"])
        self.assertTrue(logged[-1][1].startswith("Saved 2 sheets (%s) in " % shared_module().file_size_text(
            sum(os.path.getsize(os.path.join(self.folder, name)) for name in ("Hand-1-of-2.psd", "Hand-2-of-2.psd")))),
                        logged[-1][1])
        parts = [part for part in self.progress if part is not None]
        self.assertEqual(parts, sorted(parts), "the bar moves forward")
        self.assertTrue(any(0.25 <= part < 0.5 for part in parts), "the first sheet's encoding: its second half")
        self.assertLessEqual(max(parts), 1.0)

    def test_a_psd_qt_cannot_read_says_so(self):
        core = Box(QRectF=lambda *rect: rect, QSize=lambda *size: size)
        self.assertEqual(fb.read_sheet_image("drawn.psd", core, self.gui()), (None, fb.PSD_NO_PICTURE))
        self.assertEqual(fb.read_sheet_image("drawn.PSD", core, self.gui()), (None, fb.PSD_NO_PICTURE))
        self.assertEqual(fb.read_sheet_image("drawn.png", core, self.gui()), (None, fb.NOT_AN_IMAGE))
        FakeImage.FILES["drawn.psd"] = (800, 600, False)
        image, why = fb.read_sheet_image("drawn.psd", core, self.gui())
        self.assertEqual((image.args, why), (("drawn.psd",), None), "its flattened picture, as Qt reads it")

    def test_a_sheet_that_cannot_be_written_leaves_the_file_there_as_it_was(self):
        self.write("Hand-1-of-2.svg", "OWNER DRAWING")
        d, asked, logged = self.saving_dialog("Replace")
        saved = fb.sheet_svg

        def broken(*args):
            raise IOError("disk full")
        fb.sheet_svg = broken
        try:
            d.save_template()
        finally:
            fb.sheet_svg = saved
        self.assertEqual(self.read("Hand-1-of-2.svg"), "OWNER DRAWING", "the write failed before it took the file's place")
        self.assertEqual(os.listdir(self.folder), ["Hand-1-of-2.svg"], "the staged file removed")
        self.assertEqual(logged[-1], ("error", "%s could not be written. Nothing was saved or overwritten." %
                                      os.path.join(self.folder, "Hand-1-of-2.svg")))
        # Python 2.7's way, without os.replace: the old file set aside, then removed
        staged = fb.staged_beside(os.path.join(self.folder, "Hand-1-of-2.svg"))
        self.assertTrue(os.path.basename(staged).startswith("Hand-1-of-2.") and staged.endswith(".part.svg"))
        with open(staged, "w") as handle:
            handle.write("NEW")
        real = getattr(os, "replace", None)
        if real is not None:
            del os.replace
        try:
            fb.put_in_place(staged, os.path.join(self.folder, "Hand-1-of-2.svg"))
        finally:
            if real is not None:
                os.replace = real
        self.assertEqual(self.read("Hand-1-of-2.svg"), "NEW")
        self.assertEqual(os.listdir(self.folder), ["Hand-1-of-2.svg"])

    def three_sheets_there(self):
        """Hand-1-of-3.svg and Hand-3-of-3.svg drawn already (Hand-2-of-3.svg not there): {name: bytes}."""
        for name in ("Hand-1-of-3.svg", "Hand-3-of-3.svg"):
            self.write(name, "OWNER DRAWING %s" % name)
        return self.contents()

    def contents(self):
        import io
        out = {}
        for name in os.listdir(self.folder):
            with io.open(os.path.join(self.folder, name), "rb") as handle:
                out[name] = handle.read()
        return out

    def test_a_save_stopped_after_two_sheets_of_three_leaves_nothing_behind(self):
        """The owner, 2026-11-24: "Cancelling should probably delete what was already exported; I managed to cancel
        by hitting Close, and that left partial exports behind." Every sheet is staged beside its file until all are
        written: stopped at the third (Cancel, Esc, Close, the tools menu, or an arrow: one path), the files there
        are byte for byte as they were, no staged file is left, and the log says so in the owner's words."""
        before = self.three_sheets_there()
        d, asked, logged = self.saving_dialog("Replace", sheets=3)
        staged_seen = []

        def progress(owner, what=None, part=None):
            staged_seen.append(sorted(os.listdir(self.folder)))
            if what == "Saving sheet 3 of 3":
                raise KeyboardInterrupt()  # (Stopped, as busy_progress raises it)
        d.ak.busy_progress = progress
        d.save_template()
        self.assertEqual(asked, ["Hand-1-of-3.svg and Hand-3-of-3.svg already exist. Replace them with new sheets?"],
                         "asked once, of every file, before anything is written")
        self.assertEqual(len([name for name in staged_seen[-1] if ".part" in name]), 2, "two sheets staged when stopped")
        self.assertEqual(self.contents(), before, "the files there untouched, nothing new, no staged file left")
        self.assertEqual(logged[-1], ("warning", "The operation was interrupted. Nothing was saved or overwritten."))
        self.assertEqual(fb.STOPPED_LINE, logged[-1][1])

    def test_an_error_on_the_third_sheet_saves_nothing(self):
        before = self.three_sheets_there()
        d, asked, logged = self.saving_dialog("Replace", sheets=3)
        real, calls = fb.sheet_svg, []

        def third_fails(sheet, *args):
            calls.append(sheet.index)
            if sheet.index == 2:
                raise IOError("disk full")
            return real(sheet, *args)
        fb.sheet_svg = third_fails
        try:
            d.save_template()
        finally:
            fb.sheet_svg = real
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(self.contents(), before, "the first two sheets written, then removed: nothing in place")
        self.assertEqual(logged[-1], ("error", "%s could not be written. Nothing was saved or overwritten." %
                                      os.path.join(self.folder, "Hand-3-of-3.svg")))

    def test_a_sheet_that_cannot_take_its_place_says_which_are_saved(self):
        """Rare: a file locked by another app as the staged sheets move into place. The moves stop there; the log
        names the sheets in place and those not, and no staged file is left."""
        before = self.three_sheets_there()
        real = fb.put_in_place

        def locked(staged, name, at="Hand-2-of-3.svg"):
            if os.path.basename(name) == at:
                raise OSError(13, "Permission denied")
            return real(staged, name)
        fb.put_in_place = locked
        try:
            d, asked, logged = self.saving_dialog("Replace", sheets=3)
            d.save_template()
            after = self.contents()
            self.assertIn(b"<svg", after["Hand-1-of-3.svg"], "the first sheet in place")
            self.assertEqual(after["Hand-3-of-3.svg"], before["Hand-3-of-3.svg"], "the third never moved")
            self.assertEqual(sorted(after), ["Hand-1-of-3.svg", "Hand-3-of-3.svg"], "no staged file left")
            self.assertEqual(logged[-1], ("error", "Hand-2-of-3.svg could not take its place (Permission denied). Saved: "
                                                   "Hand-1-of-3.svg. Not saved, any file there left as it was: "
                                                   "Hand-2-of-3.svg and Hand-3-of-3.svg."))
            # The first move failing: nothing saved at all
            self.write("Hand-1-of-3.svg", "OWNER DRAWING Hand-1-of-3.svg")
            fb.put_in_place = lambda staged, name: locked(staged, name, "Hand-1-of-3.svg")
            d, asked, logged = self.saving_dialog("Replace", sheets=3)
            d.save_template()
            self.assertEqual(self.contents(), before)
            self.assertEqual(logged[-1], ("error", "Hand-1-of-3.svg could not take its place (Permission denied). "
                                                   "Nothing was saved or overwritten."))
        finally:
            fb.put_in_place = real

    def test_staged_files_an_earlier_save_left_are_cleared_and_only_those(self):
        leftovers = {"Hand-1-of-2.ab12_xyz.part.svg": True, "Hand-2-of-2.q9w8e7.part.svg": True,  # (Python 3's, 2.7's)
                     "Hand-1-of-2.ab12_xyz.part.svg.old": False,  # (put_in_place's aside: maybe the only drawing)
                     "Hand-1-of-2.ab12.part.svg": False, "Other.ab12_xyz.part.svg": False,
                     "Hand-1-of-2.ab12_xyz.part.png": False, "Hand-1-of-3.ab12_xyz.part.svg": False}
        for name in leftovers:
            self.write(name, "LEFT")
        d, asked, logged = self.saving_dialog(None, sheets=2)
        d.save_template()
        names = sorted(os.listdir(self.folder))
        self.assertEqual(sorted(name for name, gone in leftovers.items() if not gone),
                         [name for name in names if not name.startswith("Hand-") or ".part" in name])
        self.assertIn("Hand-1-of-2.svg", names, "then saved")
        self.assertTrue(fb.staged_pattern("a/Hand.svg").match(os.path.basename(fb.staged_beside(
            os.path.join(self.folder, "Hand.svg")))), "the pattern is staged_beside's own")

    def test_the_question_names_a_long_list_in_part(self):
        names = ["a/Big-%d-of-131.png" % (k + 1) for k in range(131)]
        self.assertEqual(fb.replace_question(names), "Big-1-of-131.png, Big-2-of-131.png, Big-3-of-131.png, "
                                                     "Big-4-of-131.png, Big-5-of-131.png, and 126 more already exist. "
                                                     "Replace them with new sheets?")
        self.assertEqual(fb.replace_question(names[:3]), "Big-1-of-131.png, Big-2-of-131.png, and Big-3-of-131.png "
                                                         "already exist. Replace them with new sheets?")
        self.assertEqual(fb.files_named(names[:6]), ", ".join("Big-%d-of-131.png" % (k + 1) for k in range(5)) +
                         ", and Big-6-of-131.png", "never \"and 1 more\": the sixth is named")
        self.assertTrue(fb.files_named(names[:7]).endswith(", and 2 more"))
        self.assertEqual(fb.replace_question(["a/DotTest.tif"]), "DotTest.tif already exists. Replace it with a new "
                                                                    "sheet?")

    def test_the_window_has_cancel_left_of_close(self):
        source = builder_source()
        self.assertIn("buttons.addWidget(self.close_button)\n        ak.cancel_button(self, buttons, self.close_button, "
                      "CANCEL_NOTE)", source)
        self.assertIn("nothing behind", fb.CANCEL_NOTE)
        self.assertIn("all or nothing", fb.SAVE_HELP)

    def test_an_svgs_size_is_its_viewbox_else_its_width_and_height(self):
        self.assertEqual(fb.svg_size('<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100mm" '
                                     'height="80mm" viewBox="0 0 640 480">'), (640.0, 480.0))
        self.assertEqual(fb.svg_size("<svg\n viewBox='0,0,640.5,480'\n>"), (640.5, 480.0), "commas, single quotes")
        self.assertEqual(fb.svg_size('<svg width="300" height="200px">'), (300.0, 200.0))
        self.assertEqual(fb.svg_size('<svg width="72pt" height="1in">'), (96.0, 96.0))
        self.assertIsNone(fb.svg_size('<svg width="100%" height="100%">'))
        self.assertIsNone(fb.svg_size('<svg data-width="3" data-height="4">'), "another attribute's name")
        self.assertIsNone(fb.svg_size("<html></html>"))
        sheet = sheet_of()
        self.assertEqual(fb.svg_size(fb.sheet_svg(sheet)), tuple(float(v) for v in sheet.size()), "a template's own")
        self.assertEqual(fb.capped_size(640.4, 480.0), (640, 480))
        w, h = fb.capped_size(20000, 20000)
        self.assertLessEqual(w * h, fb.SHEET_PIXELS_MAX)
        self.assertEqual(w, h)

    def gui(self, renderer=True):
        return Box(QImage=FakeImage, QPainter=FakePainter, QColor=lambda *rgb: rgb, QImageReader=FakeReader,
                   **({"QSvgRenderer": FakeRenderer} if renderer else {}))

    def test_an_svg_sheet_is_drawn_at_its_viewboxs_size_on_white(self):
        core = Box(QRectF=lambda *rect: rect, QSize=lambda *size: size)
        path = self.write("Your-Highschool-Crush.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="169.33mm" '
                                                       'height="127mm" viewBox="0 0 640 480"></svg>')
        FakeRenderer.VALID.add(path)
        image, why = fb.read_sheet_image(path, core, self.gui())
        self.assertIsNone(why)
        self.assertEqual((image.width(), image.height(), image.filled), (640, 480, (255, 255, 255)))
        self.assertEqual(FakeRenderer.rendered, [(path, (0, 0, 640, 480), image)], "the whole drawing, on white")
        # Without QtSvg in this PythonQt: Qt's SVG image plugin, asked for that size, its clear ground made white
        FakeImage.FILES[path] = (640, 480, True)
        image, why = fb.read_sheet_image(path, core, self.gui(renderer=False))
        self.assertEqual(FakeReader.scaled, [(640, 480)])
        self.assertEqual((image.w, image.h, image.filled), (640, 480, (255, 255, 255)))
        self.assertEqual(len(image.drawn), 1, "the drawing laid on white paper")
        # Neither: said, not read as a blank sheet
        del FakeImage.FILES[path]
        self.assertEqual(fb.read_sheet_image(path, core, self.gui(renderer=False)), (None, fb.SVG_NOT_DRAWN))
        self.assertIn("PNG", fb.SVG_NOT_DRAWN)

    def test_other_sheets_are_read_as_images_their_clear_parts_white(self):
        core = Box(QRectF=lambda *rect: rect, QSize=lambda *size: size)
        FakeImage.FILES.update({"scan.jpg": (800, 600, False), "layer.png": (800, 600, True)})
        image, why = fb.read_sheet_image("scan.jpg", core, self.gui())
        self.assertEqual((image.args, why), (("scan.jpg",), None), "as read")
        image, why = fb.read_sheet_image("layer.png", core, self.gui())
        self.assertEqual((image.filled, len(image.drawn)), ((255, 255, 255), 1), "drawn on a clear layer: on white")
        self.assertEqual(fb.read_sheet_image("sheet.pdf", core, self.gui()), (None, fb.NOT_AN_IMAGE))
        self.assertEqual(FakeRenderer.rendered, [], "an image is never handed to the SVG renderer")

    def test_the_saved_line_links_to_the_folder_and_the_link_shows_the_file(self):
        ak = shared_module()
        first = os.path.join(self.folder, "Hand-1-of-2.svg")
        line = fb.saved_line(ak, [first, os.path.join(self.folder, "Hand-2-of-2.svg")])
        link = ak.reveal_link(first, os.path.normpath(self.folder))
        self.assertEqual(line, "Saved <b>2 sheets</b> in %s: Hand-1-of-2.svg and Hand-2-of-2.svg." % link)
        # Their size together, in the suite's words (the owner, 2026-11-24); a long list named in part
        line = fb.saved_line(ak, [first, os.path.join(self.folder, "Hand-2-of-2.svg")], size=1717986918)
        self.assertEqual(line, "Saved <b>2 sheets</b> (1.6 GB) in %s: Hand-1-of-2.svg and Hand-2-of-2.svg." % link)
        many = [os.path.join(self.folder, "Big-%d-of-131.png" % (k + 1)) for k in range(131)]
        self.assertTrue(fb.saved_line(ak, many, size=860000).endswith(
            ": Big-1-of-131.png, Big-2-of-131.png, Big-3-of-131.png, Big-4-of-131.png, Big-5-of-131.png, and 126 more."))
        self.assertIn("<b>131 sheets</b> (840 KB)", fb.saved_line(ak, many, size=860000))
        target = link.split('"')[1]
        self.assertEqual(ak.revealed_path(target), first)
        self.assertIn(">%s</a>" % ak.html(os.path.normpath(self.folder)), link, "the folder's path the link's words")
        plain = fb.saved_line(Box(b=lambda s: "<b>%s</b>" % s, html=lambda s: s), ["C:/Temp/a/Hand.svg"])
        self.assertEqual(plain, "Saved <b>1 sheet</b> in %s: Hand.svg." % os.path.normpath("C:/Temp/a"),
                         "a shared module without links: the folder named")
        # A click on it: handed to the shared module, which shows the file; other links left to the log
        shown = []
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.log = Box(add=lambda text, level="info": shown.append((level, text)))
        d.ak = Box(reveal_clicked=lambda target, log: shown.append((target, log)) or True)
        self.assertTrue(d.log_link(target))
        self.assertEqual(shown, [(target, d.log)])
        d.ak = Box()
        self.assertFalse(d.log_link(target), "a shared module without it: the log's own")


class RevealTests(unittest.TestCase):
    """The shared module's link to a file saved (owner's image 375): Explorer on Windows (explorer /select,
    no shell, no console window), the Finder on macOS (open -R), the folder elsewhere."""

    def setUp(self):
        import subprocess
        self.ak = shared_module()
        self.calls = []
        real = subprocess.Popen
        subprocess.Popen = lambda *args, **kwargs: self.calls.append((args, kwargs))
        self.addCleanup(setattr, subprocess, "Popen", real)
        self.here = os.path.abspath(__file__)
        if not isinstance(self.here, type("")):  # (Python 2: bytes; the copied tree's path is ASCII)
            self.here = self.here.decode("ascii")

    def test_the_commands(self):
        ak = self.ak
        old = os.environ.get("SystemRoot")
        os.environ["SystemRoot"] = str("C:\\Windows")
        self.addCleanup(lambda: os.environ.__setitem__("SystemRoot", old) if old else os.environ.pop("SystemRoot", None))
        self.assertEqual(ak.reveal_command("C:/Temp/My Hand/Hand-1-of-2.svg", "win32"),
                         '"C:\\Windows\\explorer.exe" /select,"C:\\Temp\\My Hand\\Hand-1-of-2.svg"',
                         "Explorer by its full path, the file's slashes made backslashes, quoted")
        self.assertEqual(ak.reveal_command("/Volumes/Fonts/Hand.svg", "darwin"),
                         ["/usr/bin/open", "-R", "/Volumes/Fonts/Hand.svg"])
        self.assertIsNone(ak.reveal_command("/srv/fonts/Hand.svg", "linux"))
        path = "C:\\Temp\\\u10d0 \"x\".svg"
        self.assertEqual(ak.revealed_path(ak.reveal_link(path).split('"')[1]), path, "any character comes back")
        self.assertIsNone(ak.revealed_path("glyph:0041"))
        self.assertIsNone(ak.revealed_path(ak.REVEAL_LINK + "zz"), "broken: no path")

    # (Python 2 encodes the command line in the ANSI code page, "mbcs", which only Windows has: adversarial review 12)
    @unittest.skipIf(sys.version_info[0] < 3 and os.name != "nt", "Python 2's ANSI command line exists on Windows only")
    def test_windows_starts_explorer_without_a_console_window(self):
        ak = self.ak
        self.assertIsNone(ak.reveal_file(self.here, "win32"))
        (args, kwargs), = self.calls
        command = ak.reveal_command(self.here, "win32")
        self.assertEqual(args[0], command if sys.version_info[0] >= 3 else command.encode("mbcs"))
        self.assertEqual(kwargs.get("creationflags"), 0x08000000, "CREATE_NO_WINDOW")
        self.assertNotIn("shell", kwargs)

    # (defined under Python 2 only: the gate fails on any test Python 3 skips, which this one always was)
    if sys.version_info[0] < 3:
        @unittest.skipIf(os.name != "nt", "Python 2's ANSI command line, on Windows")
        def test_a_path_the_ansi_code_page_cannot_spell_goes_through_shell_execute(self):
            self.ansi_path_goes_through_shell_execute()

    def ansi_path_goes_through_shell_execute(self):
        import io
        import shutil
        import tempfile
        ak = self.ak
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder.decode("mbcs"), "\u10d0\u10d1 sheet.svg")
        io.open(path, "w").close()
        shell = []
        real = ak._shell_execute
        ak._shell_execute = lambda program, parameters: shell.append((program, parameters)) or True
        self.addCleanup(setattr, ak, "_shell_execute", real)
        self.assertIsNone(ak.reveal_file(path, "win32"))
        command = ak.reveal_command(path, "win32")
        if command.encode("mbcs", "replace").decode("mbcs") == command:
            self.skipTest("this code page spells it")
        self.assertEqual(self.calls, [])
        self.assertEqual(shell, [(command[1:].split('" ')[0], '/select,"%s"' % path)])

    def test_macos_asks_the_finder_and_elsewhere_the_folder_opens(self):
        ak = self.ak
        self.assertIsNone(ak.reveal_file(self.here, "darwin"))
        (args, kwargs), = self.calls
        self.assertEqual(list(args[0])[:2], ["/usr/bin/open", "-R"])
        opened = []
        real = ak._qt
        ak._qt = lambda: (Box(QUrl=Box(fromLocalFile=lambda folder: folder)),
                          Box(QDesktopServices=Box(openUrl=lambda url: opened.append(url) or True)))
        self.addCleanup(setattr, ak, "_qt", real)
        self.assertIsNone(ak.reveal_file(self.here, "linux"))
        self.assertEqual(opened, [os.path.dirname(self.here)])

    def test_a_file_gone_is_said_and_other_links_are_the_logs(self):
        ak = self.ak
        logged = []
        log = Box(add=lambda text, level="info": logged.append((level, text)))
        gone = os.path.join(os.path.dirname(self.here), "no such sheet.svg")
        self.assertTrue(ak.reveal_clicked(ak.reveal_link(gone).split('"')[1], log))
        self.assertEqual(self.calls, [], "nothing started")
        self.assertEqual(logged[0][0], "warning")
        self.assertIn("not there anymore", logged[0][1])
        self.assertFalse(ak.reveal_clicked("glyph:0041", log))


class ModuleNameTests(unittest.TestCase):
    """This file's literals are unicode in Python 2 (unicode_literals): a module loaded under such a name put a
    unicode key in sys.modules, found on 2026-11-23 beside a FontLab session whose Scripts menu ran no script."""

    def test_the_modules_it_loads_are_named_with_plain_strings(self):
        for name in ('AUTO_KERNING_MODULE', 'FONT_CHECK_MODULE', 'TRACER_MODULE'):
            self.assertIs(type(getattr(fb, name)), str, name)


class TextTests(unittest.TestCase):
    """The review of 2026-11-24: the window's texts say what the code does, plainly."""

    def source(self):
        import io
        with io.open(fb.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_em_size_help_is_worked_out_from_the_default(self):
        self.assertEqual(fb.EM_PIXELS, 500)
        # (the owner asked whether the font's metrics affect the em size: they do not, and the help says what they do)
        self.assertEqual(fb.EM_HELP, u"The em's size on the sheet, in pixels (500 at first, which draws well on a screen), "
                                     u"whatever the font's units per em: the font's metrics set where its lines fall "
                                     u"within the em, and how tall a box is. Printed at 300 dpi, 118 pixels make a "
                                     u"centimeter, so an em of 500 pixels is about 4.2 cm.")
        small, large = fb.Metrics(1000, 800, -200, 500, 700), fb.Metrics(2048, 1638, -410, 1024, 1434)
        for metrics in (small, large):
            sheet = fb.Sheet(["A"], ["A"], metrics, 500)
            self.assertAlmostEqual(sheet.units(metrics.upm), 500, msg="an em is the Em size, whatever the units")
            self.assertEqual(sheet.box_size()[0], 600, "a box 1.2 em wide")
        self.assertEqual(fb.Sheet(["A"], ["A"], small, 500).box_size()[1], 650, "1.3 em: ascender to descender, room")
        self.assertEqual(fb.Sheet(["A"], ["A"], fb.Metrics(1000, 900, -300, 500, 700), 500).box_size()[1], 750,
                         "a font of taller extremes: taller boxes at the same em")

    def test_the_replace_box_says_when_it_counts(self):
        """Unticked, a drawn glyph is kept even ticked (build); the list's ticks follow the box only at a read."""
        self.assertIn(u"Unticked, it is kept, even ticked in the list.", fb.REPLACE_HELP)
        self.assertNotIn(u"unless you tick it", fb.REPLACE_HELP)
        self.assertIn(u"(tick <i>Replace glyphs the font has drawn</i> to redraw them)", self.source())
        self.assertNotIn(u"turn on <i>Replace", self.source())

    def test_buttons_that_open_a_file_dialog_end_with_an_ellipsis(self):
        for text in (fb.SAVE_TEMPLATE, fb.ADD_SHEETS):
            self.assertTrue(text.endswith(u"\N{HORIZONTAL ELLIPSIS}") and not text.endswith(u"..."), text)
        self.assertNotIn(u'QPushButton("Save template...")', self.source())

    def test_an_error_sentence_ends_with_its_period(self):
        # (the log adds no period: ak.error_sentence ends the sentence once)
        self.assertIn(u'self.ak.error_sentence(u"Stopped by an error", error)', self.source())
        self.assertNotIn(u"Stopped by an error: %s", self.source())

    def test_the_help_and_the_sheet_size_read_plainly(self):
        self.assertEqual(fb.PER_SHEET, 100)
        self.assertIn(u"holds as many glyphs as you set (100 at first)", fb.HELP)
        self.assertIn(u'QLabel("Glyphs per sheet:")', self.source())
        self.assertTrue(fb.HELP.endswith(u"<br><br>\nClick this help's button, then anything in the window, for what it "
                                         u"does (or right-click it: <i>What's This?</i>)."))
        self.assertIn(u'self.close_button.setWhatsThis("Closes the window.', self.source())

    def test_the_ink_threshold_says_where_the_risk_begins_from_the_grays_themselves(self):
        """The owner, 2026-11-24: the lines read at about 205 and the guide characters at about 235, and the setting
        stops at 185; the numbers come from the constants, never typed in the text."""
        for text in (fb.THRESHOLD_TIP, fb.THRESHOLD_HELP):
            for value in (fb.GUIDE_GRAY, fb.GUIDE_INK_GRAY, fb.THRESHOLD_MAX):
                self.assertIn(u"%d" % value, text)
            self.assertTrue(text.endswith(u"."), text)
        self.assertEqual((fb.GUIDE_GRAY, fb.GUIDE_INK_GRAY, fb.THRESHOLD_MAX), (205, 235, 185))
        self.assertIn(u"lines read at about 205 and the guide characters at about 235", fb.THRESHOLD_TIP)
        self.assertIn(u"the sooner the lines, then the guide characters, show in the glyphs", fb.THRESHOLD_HELP)
        self.assertIn(u"lower it if lines appear", fb.THRESHOLD_HELP)
        source = self.source()
        texts = source[source.index(u"THRESHOLD_TIP = ("):source.index(u"# Save template...: the formats")]
        for typed in (u"205", u"235", u"185"):
            self.assertNotIn(typed, texts, "worked out from the constants")
        self.assertIn(u"self.threshold.setToolTip(THRESHOLD_TIP)", source)
        self.assertIn(u"self.threshold.setWhatsThis(THRESHOLD_HELP)", source)
        self.assertIn(u'QtGui.QLabel("Ink darker than:"), self.threshold', source)

    def test_the_save_help_names_the_formats_and_what_may_be_hidden(self):
        self.assertIn(u"SVG and PSD keep the template on locked layers of their own, with an empty layer above it to "
                      u"draw on; PNG and TIFF are flat images.", fb.SAVE_HELP)
        self.assertIn(u"the marks (the corner squares and the bands) must stay visible", fb.SAVE_HELP)
        self.assertIn(u"self.save_button.setWhatsThis(SAVE_HELP)", self.source())
        self.assertIn(u"an SVG drawing or a PSD image", fb.HELP)
        self.assertIn(u"The boxes, lines, and guide characters may be hidden", fb.HELP)


def builder_source():
    import io
    with io.open(os.path.join(HERE, os.pardir, "builder", "freelab_font_builder.py"), encoding="utf-8") as handle:
        return handle.read()


def font_check():
    """Font Check's module, as Font Builder loads it (its window not opened)."""
    folder = os.path.join(HERE, os.pardir, "checks")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import freelab_font_check
    return freelab_font_check


class FakeFont(object):
    """A QFont: made from another (the box's), its family and point size set."""

    def __init__(self, other=None):
        self.family = getattr(other, "family", "MS Shell Dlg 2")
        self.points = getattr(other, "points", 9.0)

    def setFamily(self, family):
        self.family = family

    def setPointSizeF(self, points):
        self.points = points


class FakeBox(object):
    """The template's box (a QPlainTextEdit): its font a property, as in PythonQt."""

    def __init__(self, text="", events=None):
        self.text, self.font, self.events = text, FakeFont(), events if events is not None else []

    def toPlainText(self):
        return self.text

    def setPlainText(self, text):
        self.text = text
        self.events.append(("text", len(text)))

    def setFont(self, font):
        self.font = font
        self.events.append(("font", font.family, font.points))


class FakeNote(object):
    """The line under the box (ak.status_label): its text a property."""

    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class FakeCheck(object):
    """Font Check's module as the template's box uses it: registering FreeLang gives Qt the fallback files
    there are (drawn), once a session as the real one does."""
    LIST_FONT_FALLBACKS = (("FreeLang-CJK.ttf", "FreeLang CJK"), ("FreeLangPlus-General.ttf", "FreeLang+ General"),
                           ("FreeLangPlus-Mongolian-Tibetan.ttf", "FreeLang+ Mongolian\N{EN DASH}Tibetan"),
                           ("FreeLangPlus-Duployan.ttf", "FreeLang+ Duployan"))

    def __init__(self, drawn=(), family="FreeLang Essential"):
        self.drawn, self.family, self.registered = frozenset(drawn), family, 0
        self.LIST_FALLBACKS_DRAWN = None

    def register_list_font(self, QtCore, QtGui):
        self.registered += 1
        self.LIST_FALLBACKS_DRAWN = self.drawn
        return self.family

    def names_characters(self, s):
        return s.size() <= 300

    def fallbacks_needed(self, s):
        return ("FreeLang CJK", "FreeLang+ General")


def preview_dialog(fc, text="ABC", points=12):
    """A Font Builder window's Template tab, as far as its box, its size, and its line go."""
    d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
    d.events = []
    d.typed = FakeBox(text, d.events)
    d.preview_size = Box(value=points)
    d.preview_note = FakeNote()
    d.preview_family = None
    d.source = Box(currentIndex=0)
    d.ak = Box(load_sibling=lambda file_name, module: fc, i=lambda text: "<i>%s</i>" % text)
    d.summary_soon = lambda: None
    return d


class TemplatePreviewTests(unittest.TestCase):
    """The owner's review of the Template tab (2026-11-24): the box under Glyphs drew Yi's 1,220 characters as
    boxes (the window's font has no Yi), its dropdown's line sat tight between the rows, and its text size
    could not be changed."""

    def setUp(self):
        self.saved = fb._qt
        fb._qt = lambda: (Box(), Box(QFont=FakeFont))
        self.addCleanup(setattr, fb, "_qt", self.saved)

    def dialog(self, fc, text="ABC", points=12):
        return preview_dialog(fc, text, points)

    def test_freelang_is_registered_once_the_box_holds_a_character_past_ascii(self):
        """Font Check's own font chain (register_list_font), not at the window's opening: ASCII draws in the
        window's font, at the size picked."""
        fc = FakeCheck()
        d = self.dialog(fc)
        d.preview_font("ABC")
        self.assertEqual(fc.registered, 0, "ASCII alone: nothing registered")
        self.assertIsNone(d.preview_family)
        self.assertEqual((d.typed.font.family, d.typed.font.points), ("MS Shell Dlg 2", 12.0), "the size picked")
        yi = "\N{YI SYLLABLE IT}\N{YI SYLLABLE IX}"
        d.preview_font(yi)
        self.assertEqual(fc.registered, 1)
        self.assertEqual((d.typed.font.family, d.typed.font.points), ("FreeLang Essential", 12.0))
        d.preview_font(yi)
        self.assertEqual(fc.registered, 1, "once a window (register_list_font itself is once a session)")
        refused = FakeCheck(family=None)
        d = self.dialog(refused)
        d.preview_font(yi)
        d.preview_font(yi)
        self.assertEqual((refused.registered, d.preview_family), (1, False), "tried once, without FreeLang")
        self.assertEqual(d.typed.font.family, "MS Shell Dlg 2", "the window's font, at the size picked")
        broken = self.dialog(Box())
        broken.preview_font(yi)  # (no register_list_font: never raises)
        self.assertFalse(broken.preview_family)

    def test_past_ascii_and_astral_characters(self):
        self.assertFalse(fb.past_ascii(""))
        self.assertFalse(fb.past_ascii("ABC xyz 0123 ~"))
        self.assertTrue(fb.past_ascii("A\N{LATIN SMALL LETTER E WITH ACUTE}"))
        # (a character past U+FFFF: two code units in a narrow build, one in a wide one)
        self.assertTrue(fb.past_ascii("\N{LINEAR B SYLLABLE B008 A}"))

    def test_a_set_picked_registers_freelang_before_the_box_is_filled(self):
        fc = FakeCheck(drawn=["FreeLang CJK", "FreeLang+ General"])
        d = self.dialog(fc)
        d.sets = [Box(base=["\N{YI SYLLABLE IT}", "\N{YI SYLLABLE IX}", "A"], size=lambda: 1220)]
        d.set_number = lambda index: 0
        d.filling = False
        d.set_chosen(1)
        self.assertEqual([event[0] for event in d.events], ["font", "text"], "the font first, then the 1,220 characters")
        self.assertEqual(d.events[0][1], "FreeLang Essential")
        self.assertEqual(d.preview_note.text, "", "every file there: no line")

    def test_a_set_whose_fonts_are_not_installed_says_so_in_one_line(self):
        fc = FakeCheck(drawn=[])
        d = self.dialog(fc)
        d.sets = [Box(base=["\N{YI SYLLABLE IT}"], size=lambda: 1220),
                  Box(base=["\N{HEBREW LETTER ALEF}"], size=lambda: 134)]
        d.set_number = lambda index: index - 1
        d.filling = False
        d.set_chosen(1)
        self.assertEqual(d.preview_note.text, "Some of these characters may show as boxes: <i>FreeLang CJK</i> and "
                                              "<i>FreeLang+ General</i>, the fonts that draw them, are not installed; "
                                              "install FreeLab again to get them.")
        d.set_chosen(2)
        self.assertEqual(d.preview_note.text, "", "a set the first file draws: no line")
        d.set_chosen(1)
        d.typed.text = "\N{YI SYLLABLE IT} edited"
        d.typed_changed()
        self.assertNotEqual(d.preview_note.text, "", "still past ASCII: still said")
        d.typed.text = "plain"
        d.typed_changed()
        self.assertEqual(d.preview_note.text, "", "the last character past ASCII gone: the line with it")
        nothing = self.dialog(FakeCheck(family=None))
        nothing.sets, nothing.set_number, nothing.filling = d.sets, d.set_number, False
        nothing.set_chosen(1)
        self.assertEqual(nothing.preview_note.text, "", "no FreeLang at all: no line that names the optional files")

    def test_the_line_follows_the_number_of_fonts(self):
        ak = Box(i=lambda text: "<i>%s</i>" % text)
        self.assertEqual(fb.missing_fonts_line(ak, []), "")
        one = fb.missing_fonts_line(ak, ["FreeLang+ Duployan"])
        self.assertEqual(one, "Some of these characters may show as boxes: <i>FreeLang+ Duployan</i>, the font that "
                              "draws them, is not installed; install FreeLab again to get it.")
        three = fb.missing_fonts_line(ak, ["A", "B", "C"])
        self.assertIn("<i>A</i>, <i>B</i>, and <i>C</i>, the fonts that draw them, are not installed; install", three)
        for line in (one, three):
            self.assertEqual(line.count(". "), 0, "one sentence: one line (a status label starts a line per sentence)")
            self.assertTrue(line.endswith("."))

    def test_the_fonts_a_set_needs_are_font_checks_judgment(self):
        """Font Check's real sets and functions: Yi and Big Five need the optional files, Hebrew and General
        Punctuation the first file alone, and Duployan its own file (which Font Check's tooltip bounds miss)."""
        fc = font_check()
        self.addCleanup(setattr, fc, "LIST_FALLBACKS_DRAWN", fc.LIST_FALLBACKS_DRAWN)
        sets = dict((s.name, s) for s in fc.load_character_sets())

        def needs(name, drawn):
            fc.LIST_FALLBACKS_DRAWN = drawn
            s = sets[name]
            chars = [item for item in s.base if len(item) == 1 or (len(item) == 2 and 0xD800 <= ord(item[0]) < 0xDC00)]
            return fb.missing_fonts(fc, s, chars)

        cjk, general, duployan = fc.LIST_FONT_FALLBACKS[0][1], fc.LIST_FONT_FALLBACKS[1][1], fc.LIST_FONT_FALLBACKS[3][1]
        none, every = frozenset(), frozenset(family for _, family in fc.LIST_FONT_FALLBACKS)
        self.assertEqual(needs("Yi", none), [cjk, general])
        self.assertEqual(needs("Yi", frozenset([cjk])), [general])
        self.assertEqual(needs("Big Five (Unihan kBigFive)", none), [cjk])
        for name in ("Hebrew", "General Punctuation (Unicode block)", "GF Latin Kernel"):
            self.assertEqual(needs(name, none), [], name)
        for name in ("Duployan", "Duployan (Unicode block)"):
            self.assertEqual(needs(name, none), [duployan], name)
        for name in ("Yi", "Big Five (Unihan kBigFive)", "Duployan"):
            self.assertEqual(needs(name, every), [], "every file there: " + name)
            self.assertEqual(needs(name, None), [], "FreeLang not registered yet: nothing said")
        self.assertEqual(fb.missing_fonts(Box(), sets["Yi"]), [], "where Font Check cannot tell")
        self.assertEqual(fb.DUPLOYAN_CODES, (0x1BC00, 0x1BCA3))

    def test_the_text_size_is_kept_within_its_range_from_one_session_to_the_next(self):
        import shutil
        import tempfile
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        ak = Box(state_dir=lambda: folder)
        self.assertEqual(fb.saved_points(fb.read_settings(ak)), fb.PREVIEW_POINTS, "nothing kept: 12 points")
        fc = FakeCheck()
        d = self.dialog(fc, points=20)
        d.ak.state_dir = ak.state_dir
        d.settings = {"em": 500}
        d.preview_size_changed(20)
        self.assertEqual(d.typed.font.points, 20.0, "the box's text at the size picked")
        self.assertEqual(fb.read_settings(ak), {"em": 500, "preview_points": 20}, "in font_builder.json")
        self.assertEqual(fb.saved_points(fb.read_settings(ak)), 20)
        self.assertEqual(fb.PREVIEW_POINTS_RANGE, (6, 72))
        self.assertEqual(fb.saved_points({"preview_points": 2}), 6)
        self.assertEqual(fb.saved_points({"preview_points": 500}), 72)
        self.assertEqual(fb.saved_points({"preview_points": "large"}), 12)
        self.assertEqual(fb.saved_points({"preview_points": None}), 12)
        self.assertEqual(fc.registered, 0, "a size alone registers nothing")

    def test_the_text_size_stands_right_of_the_sets_dropdown_with_its_help(self):
        """The owner, 2026-11-24: "Character set: [dropdown]   Text size: [14 pt]", the row's spacing between the
        dropdown and the next caption, the dropdown as wide as its widest choice as before."""
        source = builder_source()
        page = source[source.index("    def template_page(self, QtCore, QtGui):"):source.index("    def preview_font(")]
        order = ['row.addWidget(QtGui.QLabel("Character set:"))', "row.addWidget(self.source)",
                 "row.addSpacing(FLOW_SPACING)", 'row.addWidget(QtGui.QLabel("Text size:"))',
                 "row.addWidget(self.preview_size)", "row.addStretch(1)"]
        places = [page.index(line) for line in order]
        self.assertEqual(places, sorted(places), "right of the sets' dropdown, then the row's stretch")
        self.assertEqual(page.count("row.addSpacing(FLOW_SPACING)"), 1)
        self.assertIn("self.source.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)", page)
        self.assertNotIn("row.addWidget(self.source, ", page, "no stretch of its own")
        self.assertIn('self.preview_size.setToolTip("The size of the characters in the box below.")', source)
        self.assertIn('"The size the box below shows its characters at, kept for the next time. It "\n'
                      '                                       "changes only what the box shows: the sheets keep their '
                      '<i>Em size</i>.")', source)
        self.assertIn('self.preview_size.setSuffix(" pt")', source)
        self.assertIn('self.preview_size.connect("valueChanged(int)", self.preview_size_changed)', source)


class FakeSource(object):
    """The Character set dropdown: each row's data (a set's number; None for Characters typed below and the
    line), its count a property as in PythonQt."""

    def __init__(self, rows):
        self.rows, self.count, self.currentIndex, self.blocked = list(rows), len(rows), 0, []

    def itemData(self, row):
        return self.rows[row]

    def setCurrentIndex(self, row):
        self.currentIndex = row

    def blockSignals(self, on):
        self.blocked.append(on)


YI = "\N{YI SYLLABLE IT}\N{YI SYLLABLE IX}"


class SavedSetTests(unittest.TestCase):
    """The owner's review of 2026-11-24: the characters of the template were kept, the set picked was not,
    and the window reopened on Characters typed below as if they had been typed."""

    def setUp(self):
        self.saved = fb._qt
        fb._qt = lambda: (Box(), Box(QFont=FakeFont))
        self.addCleanup(setattr, fb, "_qt", self.saved)
        self.sets = [Box(iso="script:Hebrew", base=["\N{HEBREW LETTER ALEF}"], size=lambda: 1),
                     Box(iso="script:Yi", base=list(YI), size=lambda: 2)]

    def dialog(self, settings, typed):
        d = preview_dialog(FakeCheck(drawn=["FreeLang CJK", "FreeLang+ General"]), typed)
        # (Characters typed below, Yi among the common sets, the line, then every set)
        d.source = FakeSource([None, 1, None, 0, 1])
        d.sets, d.settings, d.picked_set, d.filling = self.sets, settings, None, False
        return d

    def test_the_set_saved_is_chosen_again(self):
        d = self.dialog({"set": "script:Yi", "typed": YI}, YI)
        d.restore_set()
        self.assertEqual(d.source.currentIndex, 1, "its first row (among the common sets)")
        self.assertEqual(d.source.blocked, [True, False])
        self.assertEqual((d.typed.text, d.picked_set), (YI, 1))
        d = self.dialog({"set": "script:Yi"}, "ABC")
        d.restore_set()
        self.assertEqual((d.source.currentIndex, d.typed.text), (1, YI), "no characters saved: the set's")
        self.assertEqual(fb.restored_choice(self.sets, "script:Yi", YI[0] + " \n" + YI[1]), 1,
                         "spaces and line breaks do not count, as in the box")

    def test_a_set_picked_is_kept_at_once(self):
        """A set picked and used without saving a template came back as Characters typed below: the choice is
        kept as it is made, with the set's characters."""
        written = []
        saved = fb.write_settings
        fb.write_settings = lambda ak, data: written.append(dict(data))
        self.addCleanup(setattr, fb, "write_settings", saved)
        d = self.dialog({"typed": "ABC"}, "ABC")
        d.picked_set = 1
        d.remember_choice(YI)
        self.assertEqual(written[-1], {"set": "script:Yi", "typed": YI})
        d.picked_set = None  # (Characters typed below picked)
        d.remember_choice()
        self.assertEqual(written[-1], {"typed": YI}, "no set kept; the characters as they were")

    def test_a_new_font_is_named_before_its_window_opens(self):
        """The owner, 2026-11-24: a font FreeLab made came up in a tab titled Unnamed. Read live: a new font's own
        names (tfn, tsn, ffn, psn) stay Unnamed whatever its font info says, and the tab is titled by them."""
        import inspect
        source = inspect.getsource(fb.FontBuilderDialog.new_font)
        for name in ('"tfn"', '"tsn"', '"ffn"', '"psn"'):
            self.assertIn(name, source)
        self.assertLess(source.index('"ffn"'), source.index("notifyPackageAdded"))

    def test_characters_typed_by_hand_come_back_as_typed(self):
        for typed in (YI + "A", YI[1] + YI[0], YI[0]):
            d = self.dialog({"set": "script:Yi", "typed": typed}, typed)
            d.restore_set()
            self.assertEqual((d.source.currentIndex, d.typed.text, d.picked_set), (0, typed, None), repr(typed))

    def test_a_set_no_longer_there_falls_back_to_the_characters(self):
        for settings in ({"set": "script:Gone", "typed": YI}, {"typed": YI}, {"set": None, "typed": YI}):
            d = self.dialog(settings, YI)
            d.restore_set()
            self.assertEqual((d.source.currentIndex, d.typed.text), (0, YI), repr(settings))
        self.assertIsNone(fb.restored_choice([], "script:Yi", YI))

    def test_the_set_is_kept_by_its_key_with_the_template(self):
        d = self.dialog({"typed": YI, "set": "script:Hebrew"}, YI)
        d.set_chosen(4)
        d.keep_set()
        self.assertEqual(d.settings["set"], "script:Yi", "Font Check's code for it, not a row or a label")
        self.assertEqual(fb.set_key(self.sets[1]), "script:Yi")
        d.set_chosen(0)
        d.keep_set()
        self.assertNotIn("set", d.settings, "Characters typed below picked: no set")
        source = builder_source()
        save = source[source.index("    def save_template(self):"):source.index("    def log_link(self, target):")]
        self.assertLess(save.index("self.keep_set()"), save.index("write_settings(self.ak, self.settings)"))
        self.assertLess(source.index("self.fill_sets()\n        self.restore_set()"), source.index("def tab_changed"),
                        "chosen again as the window opens, once the sets are listed")

    def test_the_dropdown_is_captioned_as_glyph_composes(self):
        import io
        with io.open(os.path.join(HERE, os.pardir, "compose", "freelab_glyph_compose.py"), encoding="utf-8") as handle:
            compose = handle.read()
        self.assertIn('QtGui.QLabel("Character set:")', compose)
        self.assertIn('row.addWidget(QtGui.QLabel("Character set:"))', builder_source())
        self.assertNotIn('QLabel("Glyphs:")', builder_source())


class FakeDelegate(object):
    """QStyledItemDelegate, as PythonQt lets a class of Python's derive from it."""
    calls = []

    def __init__(self, parent=None):
        self.parent = parent

    def sizeHint(self, option, index):
        FakeDelegate.calls.append("base sizeHint")
        return Box(width=lambda: 100, height=lambda: 20)

    def paint(self, painter, option, index):
        FakeDelegate.calls.append("base paint")


class QtsOwnDelegate(object):
    """Qt's QComboBoxDelegate: a separator's row as tall as a frame's width."""

    def __init__(self, broken=False):
        self.broken, self.painted = broken, []

    def sizeHint(self, option, index):
        if self.broken:
            raise RuntimeError("deleted")
        return Box(width=lambda: 2, height=lambda: 2) if index.data(99) == "separator" else \
            Box(width=lambda: 140, height=lambda: 18)

    def paint(self, painter, option, index):
        if self.broken:
            raise RuntimeError("deleted")
        self.painted.append(index.data(99))


class SeparatorRoomTests(unittest.TestCase):
    def setUp(self):
        self.saved = fb._qt
        FakeDelegate.calls = []
        core = Box(Qt=Box(AccessibleDescriptionRole=99), QSize=lambda w, h: ("QSize", w, h))
        fb._qt = lambda: (core, Box(QStyledItemDelegate=FakeDelegate))
        self.addCleanup(setattr, fb, "_qt", self.saved)

    def combo(self, own, order):
        view = Box(itemDelegate=lambda: order.append("read Qt's delegate") or own,
                   setItemDelegate=lambda delegate: order.append(("set on the list", delegate)))
        return Box(view=lambda: view)  # (no setItemDelegate on the box: QComboBox's deletes the one it replaces)

    def test_a_separators_row_gets_room_above_and_below_its_line(self):
        order, own = [], QtsOwnDelegate()
        ak = Box(long_choice=lambda combo: order.append("long_choice"))
        delegate = fb.separator_room(self.combo(own, order), ak)
        self.assertEqual(order[:2], ["long_choice", "read Qt's delegate"], "Qt's list delegate, not a menu's")
        self.assertEqual(order[2], ("set on the list", delegate))
        self.assertIsInstance(delegate, FakeDelegate)
        separator, choice = Box(data=lambda role: "separator" if role == 99 else None), Box(data=lambda role: None)
        self.assertEqual(delegate.sizeHint(None, separator), ("QSize", 2, 2 + 2 * fb.SEPARATOR_ROOM))
        self.assertEqual(fb.SEPARATOR_ROOM, 4, "a few pixels above and below")
        hint = delegate.sizeHint(None, choice)
        self.assertEqual((hint.width(), hint.height()), (140, 18), "every other row as Qt makes it")
        delegate.paint(None, None, separator)
        delegate.paint(None, None, choice)
        self.assertEqual(own.painted, ["separator", None], "Qt's own painting: the style's line, in either palette")
        self.assertEqual(FakeDelegate.calls, [])

    def test_a_delegate_that_fails_falls_back_and_never_raises(self):
        order = []
        delegate = fb.separator_room(self.combo(QtsOwnDelegate(broken=True), order), Box())
        index = Box(data=lambda role: "separator")
        hint = delegate.sizeHint(None, index)
        self.assertEqual(hint.height(), 20, "the base class's size")
        delegate.paint(None, None, index)
        self.assertEqual(FakeDelegate.calls, ["base sizeHint", "base paint"])
        self.assertIsNone(fb.separator_room(Box(), Box()), "no list to read: nothing, no error")
        self.assertIsNone(fb.separator_room(Box(view=lambda: Box(itemDelegate=lambda: None)), Box()))

    def test_the_template_dropdown_gets_it(self):
        source = builder_source()
        self.assertIn("self.separator_delegate = separator_room(self.source, self.ak)", source)
        self.assertNotIn("combo.setItemDelegate(", source)


def painting_qt(calls):
    """(QtCore, QtGui) fakes under which render_sheet's painting is recorded into calls, in order, as plain values
    (lists, numbers, and strings: the same in Python 2.7 and 3, so a whole painting can be compared by its hash)."""
    record = calls.append

    class Image(object):
        Format_RGB32 = 4

        def __init__(self, width, height, kind):
            record(["image", width, height, kind])

        def fill(self, color):
            record(["fill", color])

    class Pen(object):
        def __init__(self, color):
            self.color, self.width = color, None

        def setWidthF(self, width):
            self.width = width

    class Font(object):
        def __init__(self, family):
            self.family, self.pixels = family, None

        def setPixelSize(self, pixels):
            self.pixels = pixels

    class Painter(object):
        Antialiasing = 1

        def __init__(self, image):
            record(["painter"])

        def setPen(self, pen):
            record(["setPen", pen.color, pen.width])

        def drawRect(self, rect):
            record(["drawRect", rect])

        def drawLine(self, start, end):
            record(["drawLine", start, end])

        def setFont(self, font):
            record(["setFont", font.family, font.pixels])

        def drawText(self, rect, flags, text):
            record(["drawText", rect, flags, text])

        def fillRect(self, rect, color):
            record(["fillRect", rect, color])

        def setRenderHint(self, hint, on):
            record(["setRenderHint", hint, on])

        def fillPath(self, path, brush):
            record(["fillPath", path, brush])

        def end(self):
            record(["end"])

    core = Box(QRectF=lambda *rect: ["rect"] + list(rect), QPointF=lambda *point: ["point"] + list(point),
               Qt=Box(AlignLeft=1, AlignRight=2, AlignHCenter=4, AlignVCenter=0x80))
    gui = Box(QImage=Image, QPainter=Painter, QColor=lambda *rgb: ["color"] + list(rgb), QPen=Pen, QFont=Font,
              QBrush=lambda color: ["brush", color])
    return core, gui


def painting_hash(calls):
    import hashlib
    import json
    return hashlib.sha1(json.dumps(calls, sort_keys=True).encode("ascii")).hexdigest()


def baseline_sheet():
    """The sheet whose SVG text and painting were hashed before the guides came (2026-11-24): a letter, a letter
    with a mark, an alternate, and a character past U+FFFF."""
    names = ["A", "uni00E9", "a.alt1", "u1F600"]
    return fb.split_sheets(names, [fb.label_of(n) for n in names], fb.Metrics(), em=200, family="Test")[0]


BASELINE_SVG = "0c722a4a6a1f950738e6a1ea944d02060e126bc9"  # (sheet_svg(baseline_sheet()), before the guides)
SODIPODI = 'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"'


def svg_before_marks_group(text):
    """An SVG sheet as sheet_svg wrote it before its marks had a group of their own (the owner, 2026-11-24): the
    marks' path back as the template group's last element, the sodipodi namespace on that group. Nothing else
    moved, so this gives the text as it was, byte for byte."""
    lines = text.split("\n")
    at = lines.index('<g id="marks" sodipodi:insensitive="true">')
    assert lines[at + 2] == "</g>" and lines[at - 1] == "</g>"
    lines = lines[:at - 1] + [lines[at + 1], lines[at - 1]] + lines[at + 3:]
    text = "\n".join(lines).replace(' %s width=' % SODIPODI, ' width=', 1)
    return text.replace('<g id="template" sodipodi:insensitive="true">',
                        '<g id="template" sodipodi:insensitive="true" %s>' % SODIPODI, 1)
BASELINE_PAINTING = "280c6ddb303f50742d4011c7ca7556d8975ad4bb"  # (render_sheet's painting of it, before them)

# ---------------------------------------------------------------------------
# Guide characters, read back: cells rasterized here as render_sheet paints them (a box's frame, its metric
# lines, and its origin line in GUIDE_GRAY over a guide character in GUIDE_INK_GRAY, smoothed), the guide a
# synthetic letter (FreeLang itself needs a real Qt), placed by the builder's own guide_left; dark strokes
# drawn over it; then scanned or photographed (blur, light, contrast, gamma, noise, 1 bit); then read as
# read_sheets reads a box (paper_level and paper_table, then the ink threshold).
# ---------------------------------------------------------------------------

GUIDE_EM = 100  # the em of the sheets read here, in pixels (small: the cells are rasterized in pure Python)


def em_polygon(points, x0, baseline, em):
    """A polygon given in ems (y up from the baseline, x from the origin) in cell pixels (y down)."""
    return [(x0 + x * em, baseline - y * em) for x, y in points]


def circle(cx, cy, r, steps=48):
    import math
    return [(cx + r * math.cos(2 * math.pi * k / steps), cy + r * math.sin(2 * math.pi * k / steps)) for k in range(steps)]


# A letter of FreeLang's size: a bowl at the x-height and a stem to the ascender (a "d", y up, in ems from its
# origin), its ink from 0.06 to 0.62 em across
GUIDE_LETTER = [circle(0.32, 0.26, 0.26), circle(0.32, 0.26, 0.17),
                [(0.52, 0.0), (0.62, 0.0), (0.62, 0.74), (0.52, 0.74)]]
GUIDE_LETTER_INK = (0.06, 0.62)


def coverage(width, height, polygons, ss=4):
    """Each pixel's share (0 to 1) inside polygons (even-odd, as a letter's bowl and counter), by ss x ss
    samples a pixel, scanline by scanline."""
    cover = [0.0] * (width * height)
    unit = 1.0 / (ss * ss)
    edges = []
    for poly in polygons:
        for k in range(len(poly)):
            edges.append((poly[k - 1], poly[k]))
    for sy in range(height * ss):
        y = (sy + 0.5) / ss
        xs = []
        for (x1, y1), (x2, y2) in edges:
            if (y1 > y) != (y2 > y):
                xs.append(x1 + (x2 - x1) * (y - y1) / (y2 - y1))
        xs.sort()
        row = (sy // ss) * width
        for a, b in zip(xs[0::2], xs[1::2]):
            first, last = max(0, int(a * ss + 0.5)), min(width * ss, int(b * ss + 0.5))
            for sx in range(first, last):
                cover[row + sx // ss] += unit
    return cover


def guide_cell(sheet, i, guide=True, strokes=(), smooth=True, lines=True):
    """Cell i's box (width, height, gray bytearray), as render_sheet paints it with its guide character (or
    without) and its lines (or, to measure the guide alone, without), then strokes (shapes, each a list of
    polygons in cell pixels) drawn over in black, one after the other, smoothed or hard-edged."""
    left, top = sheet.cell(i)
    bw, bh = sheet.box_size()
    gray = bytearray(b"\xff" * (bw * bh))
    _, baseline = sheet.origin(i)
    baseline -= top
    if guide:
        x = fb.guide_left(sheet, i, GUIDE_LETTER_INK[0] * sheet.em, GUIDE_LETTER_INK[1] * sheet.em) - left
        shape = [em_polygon(poly, x, baseline, sheet.em) for poly in GUIDE_LETTER]
        for k, share in enumerate(coverage(bw, bh, shape)):
            if share:
                gray[k] = int(round(255 - share * (255 - fb.GUIDE_INK_GRAY)))
    thin, base = int(max(1.0, sheet.em / 400.0)), int(round(max(2.0, sheet.em / 200.0)))
    # (the lines over it, unsmoothed, as render_sheet draws them: the frame's inner half, the metric lines, the origin)
    for name, y in (sheet.guides(i) if lines else ()):
        width_ = base if name == "baseline" else thin
        for yy in range(int(round(y - top - width_ / 2.0)), int(round(y - top - width_ / 2.0)) + width_):
            if 0 <= yy < bh:
                gray[yy * bw:(yy + 1) * bw] = bytearray([fb.GUIDE_GRAY]) * bw
    if lines:
        ox = int(round(sheet.origin(i)[0] - left))
        for yy in range(bh):
            gray[yy * bw + ox] = fb.GUIDE_GRAY
            gray[yy * bw] = gray[yy * bw + bw - 1] = fb.GUIDE_GRAY
        gray[0:bw] = gray[(bh - 1) * bw:bh * bw] = bytearray([fb.GUIDE_GRAY]) * bw
    for shape in strokes:
        for k, share in enumerate(coverage(bw, bh, shape, 4 if smooth else 1)):
            if share:
                gray[k] = int(round(gray[k] * (1.0 - share)))
    return bw, bh, gray


def scanned(gray, width, height, light=1.0, black=0, gamma=1.0, darker=0, slope=0.0, noise=0, blur=False,
            one_bit=False, seed=7):
    """A cell as a scan or a photograph gives it back: the guide's tint printed darker (darker: grays taken off
    its light grays, a printer's dot gain), smoothed by the optics (blur: 3 x 3), the paper's light (light, times
    white) falling off across the box (slope, a share of it), the scanner's black (black) and its tone curve
    (gamma), then its noise (noise grays either way, seeded); one_bit: the scanner's own black and white at
    128."""
    import random
    out = bytearray(gray)
    if darker:
        for k, v in enumerate(out):
            if fb.GUIDE_GRAY < v < 255:  # (the guide character's tint and its soft edges)
                out[k] = v - int(round(darker * (255 - v) / float(255 - fb.GUIDE_INK_GRAY)))
    if blur:
        src = bytearray(out)
        for y in range(height):
            for x in range(width):
                total = n = 0
                for yy in range(max(0, y - 1), min(height, y + 2)):
                    for xx in range(max(0, x - 1), min(width, x + 2)):
                        total += src[yy * width + xx]
                        n += 1
                out[y * width + x] = int(round(total / float(n)))
    rng = random.Random(seed)
    for y in range(height):
        for x in range(width):
            k = y * width + x
            value = 255.0 * (out[k] / 255.0) ** gamma
            value = black + (light * (1.0 - slope * x / float(width)) * 255.0 - black) * value / 255.0
            if noise:
                value += int(rng.random() * (2 * noise + 1)) - noise
            value = max(0, min(255, int(round(value))))
            out[k] = (0 if value < 128 else 255) if one_bit else value
    return out


def read_box(gray, width, height, threshold=fb.INK_THRESHOLD):
    """A box as read_sheets reads it: (its gray with its paper made white, its ink as 1s, whether it holds
    ink)."""
    data = bytes(gray)
    table = fb.paper_table(fb.paper_level(data, width, height, width), threshold)
    if table is not None:
        data = data.translate(table)
    ink = bytearray(1 if v < threshold else 0 for v in bytearray(data))
    return data, ink, fb.has_ink(data, width, height, width, threshold, max(20, int(width * height * 0.0005)))


def guide_sheet():
    names = ["d", "a", "o", "n"]
    return fb.Sheet(names, names, fb.Metrics(), GUIDE_EM)


def strokes_of(sheet, i):
    """Dark strokes a user draws over cell i's guide: a slanted bar across its bowl and a ring over its
    counter, in cell pixels."""
    left, top = sheet.cell(i)
    ox, baseline = sheet.origin(i)
    x, y = ox - left, baseline - top
    em = sheet.em
    bar = [(x + 0.05 * em, y - 0.05 * em), (x + 0.15 * em, y - 0.05 * em), (x + 0.65 * em, y - 0.65 * em),
           (x + 0.55 * em, y - 0.65 * em)]
    return [[bar], [circle(x + 0.32 * em, y - 0.26 * em, 0.2 * em), circle(x + 0.32 * em, y - 0.26 * em, 0.13 * em)]]


SCANS = {  # (realistic sheets back from paper: a flatbed scan, a phone photo, a scanner's 1 bit)
    "screen": {},
    "scan": dict(light=0.93, black=24, gamma=1.2, darker=15, slope=0.03, noise=6, blur=True),
    "photo": dict(light=0.8, black=40, gamma=1.1, darker=10, slope=0.05, noise=8, blur=True),
    "one bit": dict(light=0.9, black=20, gamma=1.3, darker=20, slope=0.04, noise=6, blur=True, one_bit=True),
}


class GuideReadingTests(unittest.TestCase):
    """The guide characters never become part of a glyph read back (the owner's request, 2026-11-24): on a
    screen's sheet, a scanned one, a photographed one, and a scanner's 1 bit, at the default and the highest
    ink threshold, in outlines and images alike."""

    def test_the_guide_is_lighter_than_every_ink_threshold_and_than_the_lines(self):
        r, g, b = fb.GUIDE_INK_RGB
        self.assertEqual((11 * r + 16 * g + 5 * b) // 32, fb.GUIDE_INK_GRAY, "Qt's gray of its color")
        self.assertEqual(fb.GUIDE_INK_GRAY, 235)
        self.assertGreaterEqual(fb.GUIDE_INK_GRAY - fb.THRESHOLD_MAX, 50)
        self.assertGreater(fb.GUIDE_INK_GRAY, fb.GUIDE_GRAY, "lighter than the lines the reading already leaves out")
        self.assertTrue(r < g < b, "the guides' own hue (pale blue)")
        gr, gg, gb = fb.GUIDE_RGB
        self.assertTrue(all(ink > line for ink, line in zip(fb.GUIDE_INK_RGB, (gr, gg, gb))))

    def test_an_untouched_sheet_with_guides_reads_as_no_ink_in_any_box(self):
        sheet = guide_sheet()
        for kind, scan in sorted(SCANS.items()):
            for threshold in (fb.INK_THRESHOLD, fb.THRESHOLD_MAX):
                if scan.get("one_bit") and threshold != fb.INK_THRESHOLD:
                    continue
                for i in range(len(sheet.names)):
                    w, h, gray = guide_cell(sheet, i)
                    data, ink, drawn = read_box(scanned(gray, w, h, seed=i, **scan), w, h, threshold)
                    self.assertFalse(drawn, "%s at %d, box %d" % (kind, threshold, i))
                    self.assertIsNone(fb.ink_box(data, w, h, w, threshold), "%s at %d" % (kind, threshold))
                    if scan.get("one_bit"):
                        continue
                    # (images: what is kept of the box is clear, the guide's soft edges too)
                    raw = scanned(gray, w, h, seed=i, **scan)
                    alphas = fb.alpha_table(threshold, fb.paper_level(bytes(raw), w, h, w))
                    self.assertEqual(max(alphas[v] for v in raw), 0, "%s at %d: an image kept no guide" % (kind, threshold))

    def ink_difference(self, scan, threshold=fb.INK_THRESHOLD, smooth=True):
        """(pixels read differently with the guide under the strokes than without it, of them those not at an
        edge of the ink read without it (a pixel whose 3 x 3 holds no paper, or no ink), the edge pixels of that
        ink), summed over the sheet's boxes."""
        sheet = guide_sheet()
        differ = inside = edge = 0
        for i in range(len(sheet.names)):
            strokes = strokes_of(sheet, i)
            reads = []
            for guide in (True, False):
                w, h, gray = guide_cell(sheet, i, guide, strokes, smooth)
                reads.append(read_box(scanned(gray, w, h, seed=i, **scan), w, h, threshold)[1])
            plain = reads[1]
            for y in range(h):
                for x in range(w):
                    near = set(plain[yy * w + xx] for yy in range(max(0, y - 1), min(h, y + 2))
                               for xx in range(max(0, x - 1), min(w, x + 2)))
                    k = y * w + x
                    if plain[k] and len(near) == 2:
                        edge += 1
                    if reads[0][k] != plain[k]:
                        differ += 1
                        inside += 1 if len(near) == 1 else 0
        return differ, inside, edge

    def test_strokes_over_a_guide_read_as_the_same_strokes_without_it(self):
        differ, inside, edge = self.ink_difference({}, smooth=False)
        self.assertEqual(differ, 0, "hard-edged strokes on a screen's sheet: the same pixels")
        self.assertGreater(edge, 500)
        for threshold in (fb.INK_THRESHOLD, fb.THRESHOLD_MAX):
            # (smoothed edges: a pixel partly inked over the guide is a little darker than over white paper, so
            # an edge moves by a pixel where its coverage was within a few hundredths of the threshold's)
            differ, inside, edge = self.ink_difference({}, threshold)
            self.assertEqual(inside, 0, "only at the strokes' edges")
            self.assertLessEqual(differ, edge * 0.1, "smoothed strokes at %d: %d of %d" % (threshold, differ, edge))

    def test_strokes_over_a_guide_read_the_same_after_a_scan_or_a_photograph(self):
        for kind in ("scan", "photo", "one bit"):
            for threshold in (fb.INK_THRESHOLD, fb.THRESHOLD_MAX):
                differ, inside, edge = self.ink_difference(SCANS[kind], threshold)
                self.assertEqual(inside, 0, "%s at %d: only at the strokes' edges" % (kind, threshold))
                self.assertLessEqual(differ, edge * 0.25, "%s at %d: %d of %d" % (kind, threshold, differ, edge))

    def test_the_traced_outlines_match(self):
        import freelab_trace as ft
        sheet = guide_sheet()
        strokes = strokes_of(sheet, 1)
        traced = []
        for guide in (True, False):
            w, h, gray = guide_cell(sheet, 1, guide, strokes)
            data = read_box(scanned(gray, w, h, seed=3, **SCANS["scan"]), w, h)[0]
            units, x0, y_top = fb.cell_mapping(sheet, 1, 1.0)
            traced.append(ft.trace_glyph(data, w, h, units, x0, y_top, stride=w, em_px=sheet.em,
                                         threshold=fb.INK_THRESHOLD))
        self.assertEqual(len(traced[0]), len(traced[1]), "as many contours")
        self.assertEqual(len(traced[0]), 3, "the bar and the ring's two")

        def box(contours):
            xs = [x for c in contours for x, _, _ in c]
            ys = [y for c in contours for _, y, _ in c]
            return min(xs), min(ys), max(xs), max(ys)
        for a, b in zip(box(traced[0]), box(traced[1])):
            self.assertLessEqual(abs(a - b), 10, "within a hundredth of the em (10 units)")

    def test_a_dim_box_is_read_with_its_paper_made_white(self):
        """Without it, a photograph whose paper reads 150 took the guides' lines (205 of white: 120) and, under
        a dimmer one, the guide characters for ink at the default threshold; read against its own paper, a box
        reads as printed."""
        sheet = guide_sheet()
        w, h, gray = guide_cell(sheet, 0)
        dim = scanned(gray, w, h, light=150 / 255.0)
        plain = bytearray(1 if v < fb.INK_THRESHOLD else 0 for v in dim)
        self.assertGreater(sum(plain), 200, "the lines read as ink, as the reading did before")
        self.assertFalse(read_box(dim, w, h)[2])
        self.assertEqual(fb.paper_level(bytes(dim), w, h, w), 150)

    def test_how_much_darkening_the_guide_survives(self):
        """The margins the documentation gives: read against its box's paper, the guide character is ink only
        once its gray falls under the threshold: a tone curve (gamma) of 8.4 on it at the default threshold,
        3.9 at the highest (185), or the light falling off by 46% or 21% between the box's brightest paper and
        the guide; the guides' lines fail first, at 3.2 and 1.5, and 38% and 10%."""
        import math
        for gray, threshold, gamma, slope in ((fb.GUIDE_INK_GRAY, 128, 8.4, 0.46), (fb.GUIDE_INK_GRAY, 185, 3.9, 0.21),
                                              (fb.GUIDE_GRAY, 128, 3.2, 0.38), (fb.GUIDE_GRAY, 185, 1.5, 0.10)):
            self.assertAlmostEqual(math.log(threshold / 255.0) / math.log(gray / 255.0), gamma, delta=0.05)
            self.assertAlmostEqual(1 - threshold / float(gray), slope, delta=0.005)
        sheet = guide_sheet()
        w, h, gray = guide_cell(sheet, 0, lines=False)
        self.assertFalse(read_box(scanned(gray, w, h, gamma=8.0), w, h)[2])
        self.assertTrue(read_box(scanned(gray, w, h, gamma=9.0), w, h)[2], "past it: the guide is ink")
        self.assertFalse(read_box(scanned(gray, w, h, gamma=3.7), w, h, fb.THRESHOLD_MAX)[2])
        self.assertTrue(read_box(scanned(gray, w, h, gamma=4.2), w, h, fb.THRESHOLD_MAX)[2])
        w, h, gray = guide_cell(sheet, 0)
        self.assertTrue(read_box(scanned(gray, w, h, gamma=3.4), w, h)[2], "the lines fail first")
        # (a dim photograph at the highest threshold: its guide 183 of a paper of 199, ink as read before)
        dim = scanned(gray, w, h, light=0.78)
        self.assertTrue(any(v < fb.THRESHOLD_MAX for v in dim if v > 150), "guide and lines under 185 as they come")
        self.assertFalse(read_box(dim, w, h, fb.THRESHOLD_MAX)[2], "read against its paper: no ink")

    def test_the_paper_of_a_box(self):
        self.assertEqual(fb.paper_level(b"\xff" * 400, 20, 20, 20), 255)
        self.assertIsNone(fb.paper_table(255, 128), "a white box: read as before, byte for byte")
        self.assertIsNone(fb.paper_table(120, 128), "no lighter than the threshold: read as before")
        table = bytearray(fb.paper_table(200, 128))
        self.assertEqual((table[200], table[0], table[255]), (255, 0, 255))
        self.assertEqual(table[int(round(fb.GUIDE_INK_GRAY * 200 / 255.0))], fb.GUIDE_INK_GRAY)
        # (a box two thirds inked: its paper still read; a stride past the width skipped)
        rows = (b"\x00" * 14 + b"\xf0" * 6 + b"\x11\x11") * 20
        self.assertEqual(fb.paper_level(rows, 20, 20, 22), 0xF0)
        self.assertEqual(fb.paper_level(b"", 0, 0, 0), 255)

    def test_an_image_glyph_is_made_from_its_box_as_read(self):
        self.assertEqual(fb.alpha_table(128, 255), fb.alpha_table(128))
        dim = fb.alpha_table(128, 200)
        self.assertEqual(dim[int(fb.GUIDE_INK_GRAY * 200 / 255.0)], 0, "a dim box's guide character: clear")
        self.assertEqual(dim[0], 255)
        self.assertEqual(fb.alpha_table(128, 100), fb.alpha_table(128), "too dark to tell: as before")
        drawn = fb.Drawn("a", "a", "sheet", image=(None, 1, 0, 0), paper=180)
        self.assertEqual(drawn.paper, 180)
        self.assertEqual(fb.Drawn("a", "a", "sheet").paper, 255)
        source = builder_source()
        self.assertEqual(source.count('ink_image(cell, self.threshold.value, QtGui, getattr(d, "paper", 255))'), 2,
                         "the list's picture and the glyph built")
        read = source[source.index("    def read_sheets(self):"):source.index("    def show_drawn(self):")]
        self.assertLess(read.index("data = data.translate(whiter)"), read.index("if not has_ink("))


class FakeGuidePath(object):
    """A QPainterPath as Guides uses it: text added at a size (its ink a box in ems), moved, cut to a box."""

    def __init__(self, ink=None, offset=(0.0, 0.0), clipped=False):
        self.ink, self.offset, self.clipped, self.rule, self.text, self.rect = ink, offset, clipped, None, None, None

    def setFillRule(self, rule):
        self.rule = rule

    def addText(self, point, font, text):
        self.text, self.font = text, font
        self.ink = FakeGuidePath.INKS.get(text)
        if self.ink is not None:
            self.ink = tuple(v * font.pixels for v in self.ink)

    def addRect(self, rect):
        self.rect = rect

    def isEmpty(self):
        return self.ink is None and self.rect is None

    def boundingRect(self):
        left, top, right, bottom = self.ink
        return Box(left=lambda: left, top=lambda: top, right=lambda: right, bottom=lambda: bottom)

    def intersected(self, other):
        return FakeGuidePath(self.ink, self.offset, clipped=True)


FakeGuidePath.INKS = {  # (left, top, right, bottom) in ems, y down from the baseline
    "d": (0.06, -0.74, 0.62, 0.01), "\N{COMBINING ACUTE ACCENT}": (-0.33, -0.74, -0.12, -0.56),
    fb.unichr_(0x2E3B): (0.0, -0.3, 3.0, -0.25), "\N{LATIN CAPITAL LETTER A WITH RING ABOVE AND ACUTE}": (0.0, -1.1, 0.7, 0.0)}


class FakeTransform(object):
    def __init__(self, *matrix):
        self.matrix = matrix

    def map(self, path):
        moved = FakeGuidePath(path.ink, (self.matrix[4], self.matrix[5]), path.clipped)
        moved.rule, moved.text, moved.font = path.rule, path.text, getattr(path, "font", None)
        return moved


def guide_qt(fonts, made):
    """(QtCore, QtGui) fakes for Guides: fonts {family: its characters}; made: the QRawFonts read."""

    class Font(object):
        def __init__(self, family):
            self.family, self.pixels = family, None

        def setPixelSize(self, pixels):
            self.pixels = pixels

    def from_font(font):
        made.append(font.family)
        chars = fonts.get(font.family)
        return Box(isValid=chars is not None, supportsCharacter=lambda code: chars is not None and code in chars)

    core = Box(QPointF=lambda *point: point, QRectF=lambda *rect: rect, Qt=Box(WindingFill=1))
    gui = Box(QFont=Font, QRawFont=Box(fromFont=from_font), QPainterPath=FakeGuidePath, QTransform=FakeTransform)
    return core, gui


class GuideCharacterTests(unittest.TestCase):
    """Which boxes get a guide character, drawn by which of FreeLang's families, and where it stands."""

    def setUp(self):
        self.saved = fb._qt
        self.addCleanup(setattr, fb, "_qt", self.saved)
        self.made = []
        fonts = {"FreeLang Essential": set([0x64, 0x301, 0x2E3B, 0x1FA]), "FreeLang CJK": set([0x64, 0x4E00])}
        fb._qt = lambda: guide_qt(fonts, self.made)

    def sheet(self, names, labels=None, metrics=None):
        return fb.Sheet(names, labels or [fb.label_of(n) for n in names], metrics or fb.Metrics(), 200)

    def test_each_character_by_the_first_family_that_has_it_and_none_else(self):
        guides = fb.Guides(["FreeLang Essential", None, "FreeLang CJK"])
        self.assertEqual(guides.family_for(0x64), "FreeLang Essential")
        self.assertEqual(guides.family_for(0x4E00), "FreeLang CJK", "the optional file, read directly")
        self.assertIsNone(guides.family_for(0xA000), "no file draws Yi here: no guide, never a box")
        self.assertEqual(self.made, ["FreeLang Essential", "FreeLang CJK"], "each family's font read once")
        sheet = self.sheet(["d", "d.alt1", "f_f_i", "uniA000"])
        self.assertIsNotNone(guides.path(sheet, 0))
        for i in (1, 2, 3):
            self.assertIsNone(guides.path(sheet, i), sheet.labels[i])
        self.assertIsNone(fb.Guides([]).path(sheet, 0), "without FreeLang")
        broken = fb.Guides(["Gone"])
        self.assertIsNone(broken.family_for(0x64), "a family Qt has no valid font for")

    def test_on_the_baseline_at_the_em_its_own_sidebearings_kept(self):
        sheet = self.sheet(["d", "n"])
        path, clipped = fb.Guides(["FreeLang Essential"]).path(sheet, 0)
        self.assertFalse(clipped)
        self.assertEqual(path.offset, sheet.origin(0), "its origin on the origin line, on the baseline")
        self.assertEqual(path.font.pixels, sheet.em, "the guide's em is the sheet's em")
        self.assertEqual(path.rule, 1, "filled as text is (nonzero)")

    def test_a_mark_or_a_wide_character_is_centered_or_left_out(self):
        sheet = self.sheet(["acutecomb", "uni2E3B"], ["\N{COMBINING ACUTE ACCENT}", fb.unichr_(0x2E3B)])  # (a three-em dash: no name in 2.7)
        guides = fb.Guides(["FreeLang Essential"])
        path, _ = guides.path(sheet, 0)
        left, _ = sheet.cell(0)
        bw, _ = sheet.box_size()
        ink_left, ink_right = path.ink[0] + path.offset[0], path.ink[2] + path.offset[0]
        self.assertAlmostEqual((ink_left + ink_right) / 2.0, left + bw / 2.0, 6, "a mark left of its origin: centered")
        self.assertEqual(path.offset[1], sheet.origin(0)[1], "at its own height")
        self.assertIsNone(guides.path(sheet, 1), "wider than its box: none")

    def test_placement_across(self):
        sheet = self.sheet(["d"])
        ox, _ = sheet.origin(0)
        left, _ = sheet.cell(0)
        bw, _ = sheet.box_size()
        em = sheet.em
        self.assertEqual(fb.guide_left(sheet, 0, 0.06 * em, 0.62 * em), ox)
        self.assertEqual(fb.guide_left(sheet, 0, 0.0, 1.0 * em), ox, "a CJK em fits right of the origin line")
        self.assertAlmostEqual(fb.guide_left(sheet, 0, 0.0, 1.15 * em), left + bw / 2.0 - 0.575 * em)
        self.assertIsNone(fb.guide_left(sheet, 0, 0.0, bw - 2 * fb.GUIDE_PAD * em + 1))
        self.assertEqual(fb.guide_code("d"), 0x64)
        self.assertEqual(fb.guide_code(fb.label_of("u1F600")), 0x1F600, "past U+FFFF, either build")
        for label in ("d.alt1", "f_f_i", ""):
            self.assertIsNone(fb.guide_code(label))

    def test_a_character_taller_than_its_box_is_cut_to_it(self):
        short = fb.Metrics(1000, 600, -200, 450, 550)  # (a box 1.1 em tall: the guide's 1.1 em capital passes it)
        sheet = self.sheet(["Aringacute"], ["\N{LATIN CAPITAL LETTER A WITH RING ABOVE AND ACUTE}"], short)
        path, clipped = fb.Guides(["FreeLang Essential"]).path(sheet, 0)
        self.assertTrue(clipped)
        self.assertIn('fill-rule="evenodd"', fb.guide_svg(FakeElements([(0, 1, 1), (1, 2, 2)]), clipped))


class FakeElements(object):
    """A QPainterPath's elements, as PythonQt gives them: (type, x, y), type 0 a move, 1 a line, 2 and 3 a
    curve's points."""

    def __init__(self, elements):
        self.elements = [Box(type=t, x=x, y=y) for t, x, y in elements]

    def elementCount(self):
        return len(self.elements)

    def elementAt(self, k):
        return self.elements[k]


class GuideFileTests(unittest.TestCase):
    """The guide characters in each template format, and the option."""

    def test_svg_path_data_is_short_and_exact(self):
        square = FakeElements([(0, 10.04, 20.0), (1, 30.0, 20.0), (2, 35.0, 25.0), (3, 35.0, 35.0), (3, 30.0, 40.0),
                               (1, 10.0, 40.0), (1, 10.04, 20.0), (0, 1.0, 2.0), (1, -1.25, 2.0)])
        self.assertEqual(fb.path_data(square), "M10 20l20 0c5 5 5 15 0 20l-20 0l0 -20zM1 2l-2.2 0z")
        # (many small steps: each relative to the point before as rounded, so the contour ends where it should)
        steps = [(0, 0.0, 0.0)] + [(1, 0.04 * k, 0.0) for k in range(1, 101)]
        data = fb.path_data(FakeElements(steps))
        self.assertAlmostEqual(sum(float(part.split(" ")[0]) for part in data[4:-1].split("l") if part), 4.0, 6)
        self.assertEqual(fb.path_data(FakeElements([])), "")
        self.assertIsNone(fb.guide_svg(FakeElements([])))
        self.assertEqual(fb.guide_svg(FakeElements([(0, 1, 1), (1, 2, 2)])), '<path d="M1 1l1 1z"/>')

    def test_an_svg_sheet_without_guides_is_byte_for_byte_as_before(self):
        """As before the guides, but for the marks' own group (svg_before_marks_group undoes that alone)."""
        import hashlib
        sheet = baseline_sheet()
        for guides in (None, [], [None] * len(sheet.names)):
            text = svg_before_marks_group(fb.sheet_svg(sheet, fb.GUIDE_RGB, guides))
            self.assertEqual(hashlib.sha1(text.encode("utf-8")).hexdigest(), BASELINE_SVG, repr(guides))
        text = svg_before_marks_group(fb.sheet_svg(sheet))
        self.assertEqual(hashlib.sha1(text.encode("utf-8")).hexdigest(), BASELINE_SVG)

    def test_an_svg_sheets_marks_are_a_locked_group_of_their_own_over_the_template(self):
        """The owner, 2026-11-24: the boxes and guides may be hidden before a sheet is saved, the marks kept. The
        marks' group holds the corner squares and the bands alone, drawn last as they always were (a title wider
        than a small sheet runs under them), and the template's holds no black."""
        import xml.etree.ElementTree as ET
        sheet = baseline_sheet()
        text = fb.sheet_svg(sheet, fb.GUIDE_RGB, [fb.guide_svg(FakeElements([(0, 1, 1), (1, 2, 2)]))] * 4)
        ns = "{http://www.w3.org/2000/svg}"
        root = ET.fromstring(text.encode("utf-8"))
        groups = [g.get("id") for g in root.findall("%sg" % ns)]
        self.assertEqual(groups, ["template", "marks", "drawing"], "bottom to top")
        locked = "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}insensitive"
        marks = root.find("%sg[@id='marks']" % ns)
        template = root.find("%sg[@id='template']" % ns)
        self.assertEqual((marks.get(locked), template.get(locked)), ("true", "true"))
        self.assertEqual([child.tag for child in marks], ["%spath" % ns])
        self.assertEqual(marks[0].get("d").count("M"), len(fb.marks(sheet)))
        self.assertNotIn("#000000", ET.tostring(template).decode("utf-8"), "no black in the template")
        self.assertEqual(template[0].get("fill"), "#ffffff", "the paper, under everything")

    def test_an_svg_sheets_guides_are_outlines_under_the_lines_in_the_template(self):
        import xml.etree.ElementTree as ET
        sheet = baseline_sheet()
        element = fb.guide_svg(FakeElements([(0, 1, 1), (1, 2, 2)]))
        text = fb.sheet_svg(sheet, fb.GUIDE_RGB, [element, None, None, element])
        self.assertLess(text.index('<g id="guides" fill="rgb(221,239,253)">'), text.index('<g fill="none" stroke='))
        ns = "{http://www.w3.org/2000/svg}"
        root = ET.fromstring(text.encode("utf-8"))
        template = root.find("%sg[@id='template']" % ns)
        guides = template.find("%sg[@id='guides']" % ns)
        self.assertEqual(len(guides.findall("%spath" % ns)), 2)
        self.assertEqual(template.findall("%sg" % ns)[0].get("id"), "guides", "first, under everything")
        self.assertNotIn("FreeLang", text, "paths, not text a viewer would need the font for")
        self.assertIsNotNone(root.find("%sg[@id='drawing']" % ns))
        self.assertEqual(text.replace("\n".join(['<g id="guides" fill="rgb(221,239,253)">', element, element, "</g>"]) +
                                      "\n", ""), fb.sheet_svg(sheet), "nothing else changes")

    def test_a_raster_sheet_without_guides_is_painted_as_before(self):
        sheet = baseline_sheet()
        for guides in (None, [None] * len(sheet.names)):
            calls = []
            core, gui = painting_qt(calls)
            fb.render_sheet(sheet, core, gui, guides)
            self.assertEqual(painting_hash(calls), BASELINE_PAINTING, repr(guides))

    def test_a_raster_sheets_guides_are_filled_first_smoothed_then_the_lines_as_before(self):
        sheet = baseline_sheet()
        calls = []
        core, gui = painting_qt(calls)

        def save():
            calls.append(["save"])

        def restore():
            calls.append(["restore"])
        painter = gui.QPainter

        class Painter(painter):
            def save(self):
                save()

            def restore(self):
                restore()
        gui.QPainter = Painter
        fb.render_sheet(sheet, core, gui, ["path 0", None, None, "path 3"])
        guide_calls = [["save"], ["setRenderHint", 1, True], ["fillPath", "path 0", ["brush", ["color", 221, 239, 253]]],
                       ["fillPath", "path 3", ["brush", ["color", 221, 239, 253]]], ["restore"]]
        self.assertEqual(calls[3:8], guide_calls, "after the image and its painter, before any line")
        self.assertEqual(painting_hash(calls[:3] + calls[8:]), BASELINE_PAINTING, "the rest as before")

    def saving(self, ext, guides_ticked=True, families=("FreeLang Essential",)):
        import shutil
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-guides-")
        self.addCleanup(shutil.rmtree, folder, True)
        saved = (fb._qt, fb.write_settings, fb.render_sheet, fb.Guides)
        self.addCleanup(lambda: setattr(fb, "_qt", saved[0]) or setattr(fb, "write_settings", saved[1]) or
                        setattr(fb, "render_sheet", saved[2]) or setattr(fb, "Guides", saved[3]))
        path = os.path.join(folder, "Hand" + ext)
        fb._qt = lambda: (None, Box(QFileDialog=Box(getSaveFileName=lambda *args: path)))
        fb.write_settings = lambda ak, data: None
        rendered, logged, progress = [], [], []

        class Image(object):
            def save(self, staged):
                with open(staged, "w") as handle:
                    handle.write("image")
                return True
        fb.render_sheet = lambda sheet, core, gui, guides=None: rendered.append(guides) or Image()

        class Made(object):
            def __init__(self, families):
                self.families = families

            def path(self, sheet, i):
                if sheet.names[i] == "broken":
                    raise RuntimeError("Qt could not draw it")
                return (FakeElements([(0, i, i), (1, i + 1, i)]), False) if sheet.names[i] != "a.alt1" else None
        fb.Guides = Made
        d = fb.FontBuilderDialog.__new__(fb.FontBuilderDialog)
        d.settings, d.dialog, d.typed = {"folder": folder}, None, Box(toPlainText=lambda: "A")
        d.alternates = d.per_sheet = d.em = Box(value=1)
        d.guide_box = Box(checked=guides_ticked)
        d.guide_families = lambda: list(families)
        d.ak = Box(busy_start=lambda *a: None, busy_end=lambda *a: None,
                   busy_progress=lambda o, what=None, part=None: progress.append((what, part)),
                   Stopped=KeyboardInterrupt, html=lambda s: s, b=lambda s: s,
                   save_file_name=shared_module().save_file_name)
        d.log = Box(add=lambda text, level="info": logged.append((level, text)))
        names = ["A", "broken", "a.alt1"] + ["g%d" % n for n in range(9)]
        d.sheets = lambda: [fb.Sheet(names, [fb.label_of(n) for n in names], METRICS, 150)]
        d.save_template()
        return d, folder, rendered, logged, progress

    def test_saving_an_svg_template_with_guides(self):
        d, folder, rendered, logged, progress = self.saving(".svg")
        import io
        with io.open(os.path.join(folder, "Hand.svg"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count("<path d="), 10, "every box but the one Qt failed and the alternate")
        self.assertIn('<path d="M0 0l1 0z"/>', text)
        self.assertEqual(d.settings["guides"], True, "kept in font_builder.json")
        self.assertEqual(logged[-1][0], "done")
        self.assertEqual(sum(1 for what, part in progress if what is None), 2, "the bar moves box by box (every 8)")

    def test_saving_a_raster_template_with_guides_and_without(self):
        d, folder, rendered, logged, progress = self.saving(".png")
        self.assertEqual([p is None for p in rendered[0]], [False, True, True] + [False] * 9)
        d, folder, rendered, logged, progress = self.saving(".png", guides_ticked=False)
        self.assertEqual(rendered, [None], "unticked: painted as before")
        self.assertEqual(d.settings["guides"], False)
        self.assertEqual([level for level, _ in logged], ["done"])

    def test_no_freelang_prints_no_guide_and_says_so(self):
        d, folder, rendered, logged, progress = self.saving(".png", families=())
        self.assertEqual(rendered, [None])
        self.assertEqual(logged[-1], ("warning", fb.NO_GUIDES_LINE))
        self.assertTrue(fb.NO_GUIDES_LINE.endswith(".") and "FreeLang" in fb.NO_GUIDES_LINE)

    def test_freelang_is_registered_for_the_guides_once_its_files_in_font_checks_order(self):
        fc = FakeCheck(drawn=["FreeLang+ Duployan", "FreeLang CJK"])
        d = preview_dialog(fc)
        saved = fb._qt
        fb._qt = lambda: (Box(), Box())
        self.addCleanup(setattr, fb, "_qt", saved)
        self.assertEqual(d.guide_families(), ["FreeLang Essential", "FreeLang CJK", "FreeLang+ Duployan"])
        self.assertEqual(d.guide_families(), ["FreeLang Essential", "FreeLang CJK", "FreeLang+ Duployan"])
        self.assertEqual(fc.registered, 1, "once")
        self.assertIsNone(d.preview_family, "the box keeps its font until it holds a character past ASCII")
        d = preview_dialog(fc)
        d.preview_family = "FreeLang Essential"  # (registered by the box already)
        d.guide_families()
        self.assertEqual(fc.registered, 1)
        none = preview_dialog(FakeCheck(family=None))
        self.assertEqual((none.guide_families(), none.guide_families()), ([], []))
        self.assertEqual(none.ak.load_sibling(None, None).registered, 1, "tried once")
        self.assertEqual(preview_dialog(Box()).guide_families(), [], "never raises")

    def test_the_option_and_its_texts(self):
        self.assertEqual(fb.GUIDE_CAPTION, "Print each character faintly as a guide.")
        self.assertEqual(fb.GUIDE_TIP, "Each box shows its character very faintly, in FreeLang, to draw over.")
        self.assertIn("FreeLang", fb.GUIDE_HELP)
        self.assertIn("never takes it for ink", fb.GUIDE_HELP)
        self.assertIn("<i>Em size</i>", fb.GUIDE_HELP)
        self.assertIn("a character FreeLang does not draw", fb.GUIDE_HELP)
        for text in (fb.GUIDE_CAPTION, fb.GUIDE_TIP, fb.GUIDE_HELP):
            self.assertTrue(text.endswith("."), text)
        source = builder_source()
        self.assertIn('self.guide_box.setChecked(bool(self.settings.get("guides", True)))', source, "ticked at first")
        self.assertIn("[self.lacking], [self.guide_box], [QtGui.QLabel(\"Alternates of each:\")", source)
        self.assertIn("its character printed very faintly in FreeLang as a guide", fb.HELP)


# ---------------------------------------------------------------------------
# PSD sheets (the owner, 2026-11-24), read back by a parser of this file's own after Adobe's Photoshop File
# Format (version 1), every length checked against the bytes after it; then by Pillow and psd-tools where
# this Python has them
# ---------------------------------------------------------------------------


def unpackbits(data, size):
    """PackBits (PSD's RLE) decoded, size bytes expected; the no-op header 128, which Photoshop never writes, is
    an error here."""
    data = bytearray(data)
    out = bytearray()
    at = 0
    while at < len(data):
        n = data[at]
        at += 1
        if n < 128:
            if at + n + 1 > len(data):
                raise ValueError("a literal past the row's end")
            out += data[at:at + n + 1]
            at += n + 1
        elif n > 128:
            out += data[at:at + 1] * (257 - n)
            at += 1
        else:
            raise ValueError("the no-op header 128")
    if len(out) != size:
        raise ValueError("a row of %d bytes, not %d" % (len(out), size))
    return bytes(out)


class PsdParser(object):
    def __init__(self, data, test):
        self.data, self.at, self.test = bytes(data), 0, test

    def take(self, n):
        part = self.data[self.at:self.at + n]
        self.test.assertEqual(len(part), n, "the file ends early")
        self.at += n
        return part

    def unpack(self, fmt):
        import struct
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))


def parse_psd(data, test):
    """{width, height, resources, layers (bottom to top), picture (its red, green, and blue planes)} of a PSD,
    test asserting every length and padding rule on the way."""
    p = PsdParser(data, test)
    sig, version, channels, height, width, depth, mode = p.unpack(">4sH6xHIIHH")
    test.assertEqual((sig, version, channels, depth, mode), (b"8BPS", 1, 3, 8, 3), "version 1, RGB, 8 bits, no alpha")
    test.assertEqual(p.unpack(">I")[0], 0, "no color mode data")
    resources = p.take(p.unpack(">I")[0])
    section = p.unpack(">I")[0]
    section_end = p.at + section
    info = p.unpack(">I")[0]
    test.assertEqual(info % 2, 0, "the layer info's length rounded up to even")
    info_end = p.at + info
    count = p.unpack(">h")[0]
    layers = []
    for _ in range(abs(count)):
        top, left, bottom, right, n = p.unpack(">iiiiH")
        channel_list = [p.unpack(">hI") for _ in range(n)]
        key, blend, opacity, clipping, flags, filler = p.unpack(">4s4sBBBB")
        extra_end = p.unpack(">I")[0]
        extra_end += p.at
        p.take(p.unpack(">I")[0])  # (the layer mask)
        ranges = p.take(p.unpack(">I")[0])
        length = bytearray(p.take(1))[0]
        name = p.take(length)
        padding = p.take((-(1 + length)) % 4)
        test.assertEqual(padding, b"\x00" * len(padding), "the Pascal name padded to 4 with zeros")
        blocks = {}
        while p.at < extra_end:
            sig, tag, size = p.unpack(">4s4sI")
            test.assertEqual(sig, b"8BIM")
            test.assertEqual(size % 2, 0, "each block's data even")
            blocks[tag] = p.take(size)
        test.assertEqual(p.at, extra_end, "the extra data's length is its bytes'")
        layers.append({"bounds": (top, left, bottom, right), "channels": channel_list, "key": key, "blend": blend,
                       "opacity": opacity, "clipping": clipping, "flags": flags, "filler": filler, "ranges": ranges,
                       "name": name, "blocks": blocks, "pixels": {}})
    for layer in layers:
        top, left, bottom, right = layer["bounds"]
        w, h = right - left, bottom - top
        for channel, length in layer["channels"]:
            start = p.at
            compression = p.unpack(">H")[0]
            if compression == 0:
                plane = p.take(w * h)
            else:
                test.assertEqual(compression, 1)
                counts = p.unpack(">%dH" % h)
                plane = b"".join(unpackbits(p.take(c), w) for c in counts)
            test.assertEqual(p.at - start, length, "each channel's length is its bytes'")
            layer["pixels"][channel] = plane
    test.assertIn(p.take(info_end - p.at), (b"", b"\x00"), "the layer info's padding")
    test.assertEqual(p.unpack(">I")[0], 0, "no global layer mask")
    test.assertEqual(p.at, section_end, "the section's length is its bytes'")
    test.assertEqual(p.unpack(">H")[0], 1, "the flattened picture in PackBits")
    counts = p.unpack(">%dH" % (3 * height))
    planes = [b"".join(unpackbits(p.take(counts[c * height + y]), width) for y in range(height)) for c in range(3)]
    test.assertEqual(p.at, len(p.data), "nothing after the picture")
    return {"width": width, "height": height, "resources": resources, "layers": layers, "picture": planes}


def psd_sheet():
    names = ["A", "B", "C", "D"]
    return fb.Sheet(names, names, METRICS, 60, family="Test")


def sheet_picture(sheet):
    """The sheet as render_sheet paints it, in pure Python, as rows of Format_RGB32 bytes (B, G, R, 255 a
    pixel): white; each box's frame, metric lines, origin line, and label in the guides' blue (a gray of 205)
    over a guide character's tint (235) with soft edges (lighter tints); then the marks in black."""
    width, height = sheet.size()
    rows = [bytearray(b"\xff" * (4 * width)) for _ in range(height)]

    def fill(x0, y0, x1, y1, rgb):
        pixel = bytearray([rgb[2], rgb[1], rgb[0], 255])
        for y in range(max(0, int(y0)), min(height, int(y1))):
            x_from, x_to = max(0, int(x0)), min(width, int(x1))
            rows[y][4 * x_from:4 * x_to] = pixel * (x_to - x_from)
    bw, bh = sheet.box_size()
    for i in range(len(sheet.names)):
        left, top = [int(v) for v in sheet.cell(i)]
        fill(left + bw // 3, top + bh // 4, left + bw // 2, top + bh // 2, fb.GUIDE_INK_RGB)
        for k, tint in enumerate(((240, 247, 254), (247, 251, 255), (252, 254, 255))):  # (its soft edge)
            fill(left + bw // 2 + k, top + bh // 4, left + bw // 2 + k + 1, top + bh // 2, tint)
        blue = fb.GUIDE_RGB
        for x0, y0, x1, y1 in ((left, top, left + bw, top + 1), (left, top + bh - 1, left + bw, top + bh),
                               (left, top, left + 1, top + bh), (left + bw - 1, top, left + bw, top + bh)):
            fill(x0, y0, x1, y1, blue)
        for _name, y in sheet.guides(i):
            fill(left, int(round(y)), left + bw, int(round(y)) + 1, blue)
        ox = int(round(sheet.origin(i)[0]))
        fill(ox, top, ox + 1, top + bh, blue)
        fill(left + 2, top - 8, left + 9, top - 3, blue)  # (a label over the box)
    u = sheet.unit
    for x, y, w, h in fb.marks(sheet):
        fill(x * u, y * u, (x + w) * u, (y + h) * u, (0, 0, 0))
    return [bytes(row) for row in rows]


def written_psd(sheet, rows, progress=None):
    import io
    width, height = sheet.size()
    spans = fb.mark_spans(sheet)
    handle = io.BytesIO()
    fb.write_psd(handle, width, height, lambda y: rows[y], lambda y: spans.get(y // sheet.unit, ()), progress)
    return handle.getvalue()


def planes_of(rows):
    """(red, green, blue) planes of rows of Format_RGB32 bytes."""
    return [b"".join(row[k::4] for row in rows) for k in (2, 1, 0)]


def marks_raster(sheet):
    """One byte a pixel: 0 on the marks' black, 255 elsewhere."""
    width, height = sheet.size()
    plane = bytearray(b"\xff" * (width * height))
    u = sheet.unit
    for x, y, w, h in fb.marks(sheet):
        for yy in range(int(round(y * u)), int(round((y + h) * u))):
            plane[yy * width + int(round(x * u)):yy * width + int(round((x + w) * u))] = b"\x00" * int(round(w * u))
    return bytes(plane)


def with_strokes(planes, sheet, boxes):
    """The red, green, and blue planes with dark strokes drawn in the boxes given (a bar and a block, hard-edged,
    in black): what a user draws on the Draw here layer, flattened. (the planes, the strokes' own pixels)"""
    width, _ = sheet.size()
    out = [bytearray(plane) for plane in planes]
    bw, bh = sheet.box_size()
    inked = set()
    for i in boxes:
        left, top = [int(v) for v in sheet.cell(i)]
        for x0, y0, x1, y1 in ((0.2, 0.15, 0.3, 0.8), (0.35, 0.5, 0.75, 0.62), (0.2, 0.0, 0.3, 0.05)):
            for y in range(top + int(y0 * bh), top + int(y1 * bh)):
                for x in range(left + int(x0 * bw), left + int(x1 * bw)):
                    for plane in out:
                        plane[y * width + x] = 0
                    inked.add((x - left, y - top))
    return [bytes(plane) for plane in out], inked


def read_planes(planes, width, height, threshold):
    """A picture read as read_sheets reads one: made gray as Qt makes it (11, 16, 5 of 32), its corner squares
    found on its binarized rows, its layout read from a band (sampled 3 x 3, as find_sheet samples), then each
    box taken at the place the layout gives (upright at scale 1 here, where read_sheets warps it with Qt) and read
    with its paper made white (read_box). (Found, [(the box's ink, whether it holds ink)])."""
    red, green, blue = [bytearray(plane) for plane in planes]
    gray = bytes(bytearray((red[k] * 11 + green[k] * 16 + blue[k] * 5) // 32 for k in range(width * height)))
    rows = fb.binarized_rows(gray, width, height, width)
    corners = fb.corner_finders(fb.find_finders(rows), width, height)
    if corners is None:
        return None, []

    def sample(x, y):
        xi, yi = int(x), int(y)
        if xi < 1 or yi < 1 or xi >= width - 1 or yi >= height - 1:
            return 255
        total = 0
        for dy in (-1, 0, 1):
            at = (yi + dy) * width + xi - 1
            total += sum(bytearray(gray[at:at + 3]))
        return total / 9.0
    found = fb.read_layout([(x, y) for x, y, _, _ in corners], [m for _, _, m, _ in corners], sample)
    if found is None:
        return None, []
    boxes = []
    bw, bh = found.sheet.box_size()
    for i in range(len(found.sheet.names)):
        left, top = [int(round(v)) for v in found.to_image(*found.sheet.cell(i))]
        crop = bytearray()
        for y in range(top, top + bh):
            crop += bytearray(gray[y * width + left:y * width + left + bw])
        _data, ink, drawn = read_box(crop, bw, bh, threshold)
        boxes.append((bytes(ink), drawn))
    return found, boxes


class PsdTests(unittest.TestCase):
    """A template saved as PSD (the owner, 2026-11-24): the flattened picture, then three layers, bottom to top,
    Marks (keep visible), Template, and Draw here, every channel in PackBits, written in pure Python."""

    def test_packbits_comes_back_and_a_white_row_is_short(self):
        import random
        rng = random.Random(5)
        noise = bytes(bytearray(rng.randrange(256) for _ in range(700)))
        samples = [b"", b"\x01", b"ab", b"aab", b"aaab", b"\xff" * 128, b"\xff" * 129, b"\xff" * 130, b"\xff" * 300,
                   b"ab" * 200, noise, b"\x00" * 3 + noise[:129] + b"\x07" * 257 + b"xy"]
        for data in samples:
            self.assertEqual(unpackbits(fb.packbits(data), len(data)), data, repr(data[:12]))
        self.assertLessEqual(len(fb.packbits(b"\xff" * 7518)), 2 * 59, "a white row of a sheet: 59 runs of 128 at most")
        self.assertLessEqual(len(fb.packbits(noise)), len(noise) + (len(noise) + 127) // 128)

    def test_the_marks_spans_are_the_marks_row_by_row(self):
        sheet = psd_sheet()
        width, height = sheet.size()
        spans = fb.mark_spans(sheet)
        raster = marks_raster(sheet)
        for y in range(height):
            row = fb.marks_plane(width, spans.get(y // sheet.unit, ()))
            self.assertEqual(row, raster[y * width:(y + 1) * width], "row %d" % y)
        self.assertTrue(all(isinstance(value, tuple) for value in spans.values()), "one tuple a row of units")

    def test_the_template_layer_is_clear_where_white_and_over_the_marks_black(self):
        white, black, gray = b"\xff\xff\xff\xff", b"\x00\x00\x00\xff", b"\x80\x80\x80\xff"
        blue = b"\xfa\xd7\xaa\xff"  # (the guides' blue: 170, 215, 250 as B, G, R)
        self.assertEqual(fb.template_alpha(white + blue + white + black), b"\x00\xff\x00\xff", "no marks: black is ink")
        self.assertEqual(fb.template_alpha(white + black + black + white, ((1, 3),)), b"\x00\x00\x00\x00")
        # (a mark Qt painted otherwise than its black: the template keeps the picture's own pixels there)
        self.assertEqual(fb.template_alpha(white + black + gray + white, ((1, 3),)), b"\x00\xff\xff\x00")
        self.assertEqual(fb.template_alpha(white * 3 + b"\xff\xfe\xff\xff", ()), b"\x00\x00\x00\xff", "near white is not white")

    def test_a_psd_sheet_comes_back_whole(self):
        import struct
        sheet = psd_sheet()
        rows = sheet_picture(sheet)
        width, height = sheet.size()
        progress = []
        psd = parse_psd(written_psd(sheet, rows, progress.append), self)
        self.assertEqual((psd["width"], psd["height"]), (width, height))
        self.assertEqual(psd["resources"], b"", "no image resources")
        picture = planes_of(rows)
        self.assertEqual(psd["picture"], picture, "the flattened picture is the sheet")
        layers = psd["layers"]
        self.assertEqual([layer["name"] for layer in layers],
                         [b"Marks (keep visible)", b"Template (can be hidden)", b"Draw here"],
                         "bottom to top: Draw here on top")
        self.assertEqual([layer["opacity"] for layer in layers], [255, 85, 255], "the Template at a third")
        for layer in layers:
            units = layer["blocks"][b"luni"]
            self.assertEqual(len(units) % 4, 0)
            count = struct.unpack(">I", units[:4])[0]
            self.assertEqual(units[4:4 + 2 * count].decode("utf-16-be").encode("ascii"), layer["name"])
            self.assertEqual((layer["key"], layer["blend"], layer["clipping"], layer["filler"]),
                             (b"8BIM", b"norm", 0, 0))
            self.assertEqual([channel for channel, _ in layer["channels"]], [-1, 0, 1, 2])
            self.assertEqual(layer["ranges"], b"\x00\x00\xff\xff" * 10)
        self.assertEqual([layer["flags"] for layer in layers], [0x09, 0x09, 0x08], "locked, locked, open; all shown")
        self.assertEqual([layer["blocks"].get(b"lspf") for layer in layers],
                         [struct.pack(">I", 7), struct.pack(">I", 7), None], "transparency, pixels, and position locked")
        self.assertEqual([layer["bounds"] for layer in layers], [(0, 0, height, width)] * 2 + [(0, 0, 0, 0)])
        self.assertEqual(layers[2]["pixels"], {-1: b"", 0: b"", 1: b"", 2: b""}, "Draw here: empty")
        marks = layers[0]["pixels"]
        self.assertEqual(marks[-1], b"\xff" * (width * height), "Marks: opaque")
        self.assertEqual([marks[0], marks[1], marks[2]], [marks_raster(sheet)] * 3, "the marks' black on white")
        template = layers[1]["pixels"]
        strong = [bytearray(template[0]), bytearray(template[1]), bytearray(template[2])]
        alpha = bytearray(template[-1])
        red, green, blue = [bytearray(plane) for plane in picture]
        black = bytearray(marks_raster(sheet))
        opacity = layers[1]["opacity"] / 255.0
        below = [bytearray(marks[c]) for c in range(3)]
        for k in range(width * height):
            white = red[k] == green[k] == blue[k] == 255
            self.assertEqual(alpha[k], 0 if white or black[k] == 0 else 255, "pixel %d" % k)
            if alpha[k]:
                self.assertFalse(red[k] == green[k] == blue[k] == 0, "no black of the marks in the Template")
            for c, plane in enumerate((red, green, blue)):
                # (Marks, then the Template at its opacity over it, as an app composites them: the picture)
                under = below[c][k]
                shown = strong[c][k] * opacity + under * (1 - opacity) if alpha[k] else under
                self.assertLessEqual(abs(shown - plane[k]), 1, "pixel %d, channel %d" % (k, c))
        # Raised to full opacity, the Template's colors are the strong ones (the owner, 2026-11-24): the lines and
        # labels at full strength, the guide characters as much lighter than them as they were
        pixels = set(zip(red, green, blue))
        self.assertIn(fb.GUIDE_RGB, pixels)
        self.assertIn(fb.GUIDE_INK_RGB, pixels)
        stored = dict(((red[k], green[k], blue[k]), (strong[0][k], strong[1][k], strong[2][k]))
                      for k in range(width * height) if alpha[k])
        self.assertEqual(stored[fb.GUIDE_RGB], (0, 135, 240))
        self.assertEqual(stored[fb.GUIDE_INK_RGB], (153, 207, 249))
        self.assertEqual([fb.template_strong(value) for value in (255, 170, 85, 0)], [255, 0, 0, 0], "kept within 0 to 255")
        self.assertEqual(fb.PSD_TEMPLATE_OPACITY, 85)
        self.assertGreater(alpha.count(b"\xff"), 1000, "the boxes and guides are on it")
        self.assertEqual(progress, [256.0 * k / height for k in range((height + 255) // 256)], "a call a band of rows")

    def test_with_the_template_hidden_the_sheet_reads_as_with_it_shown(self):
        """The owner, 2026-11-24: a sheet saved with the Template layer hidden (the marks on white, and the strokes
        drawn) is found, its layout read from a band, and its boxes read exactly as with the template shown: the
        reading uses the corner squares, the bands, and the boxes' ink, never the lines or the labels."""
        sheet = psd_sheet()
        width, height = sheet.size()
        psd = parse_psd(written_psd(sheet, sheet_picture(sheet)), self)
        marks = psd["layers"][0]["pixels"]
        stroked = (0, 2)
        shown, inked = with_strokes(psd["picture"], sheet, stroked)
        hidden, _ = with_strokes([marks[0], marks[1], marks[2]], sheet, stroked)
        for threshold in (fb.INK_THRESHOLD, fb.THRESHOLD_MAX):
            found_shown, boxes_shown = read_planes(shown, width, height, threshold)
            found_hidden, boxes_hidden = read_planes(hidden, width, height, threshold)
            self.assertIsNotNone(found_hidden, "the marks alone are found and read")
            self.assertEqual(found_hidden.sheet.names, sheet.names)
            self.assertEqual(found_hidden.sheet.payload(), found_shown.sheet.payload())
            for (x, y) in ((0, 0), (width, height)):
                for a, b in zip(fb.apply(found_shown.mapping, x, y), fb.apply(found_hidden.mapping, x, y)):
                    self.assertAlmostEqual(a, b, 6)
            self.assertEqual(boxes_hidden, boxes_shown, "every box read alike at %d" % threshold)
            self.assertEqual([drawn for _, drawn in boxes_hidden], [i in stroked for i in range(len(sheet.names))])
            bw, _ = sheet.box_size()
            ink = bytearray(boxes_hidden[0][0])
            self.assertEqual(set((k % bw, k // bw) for k in range(len(ink)) if ink[k]), inked,
                             "the strokes, and nothing else")

    def test_a_psd_past_its_size_or_stopped_is_not_written(self):
        import io
        for width, height in ((30001, 10), (10, 30001), (0, 10)):
            self.assertRaises(IOError, fb.write_psd, io.BytesIO(), width, height, lambda y: b"", None, None)
        self.assertEqual(fb.PSD_SIDE_MAX, 30000)

        def stop(part):
            if part > 0:
                raise KeyboardInterrupt()
        sheet = psd_sheet()
        rows = sheet_picture(sheet)
        self.assertRaises(KeyboardInterrupt, written_psd, sheet, rows, stop)

    def test_pillow_reads_the_picture_and_lists_the_layers(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("no Pillow in this Python (FontLab's has none)")
        import io
        sheet = psd_sheet()
        rows = sheet_picture(sheet)
        width, height = sheet.size()
        image = Image.open(io.BytesIO(written_psd(sheet, rows)))
        self.assertEqual((image.format, image.mode, image.size), ("PSD", "RGB", (width, height)))
        red, green, blue = planes_of(rows)
        rgb = bytearray(3 * width * height)
        rgb[0::3], rgb[1::3], rgb[2::3] = red, green, blue
        self.assertEqual(image.tobytes(), bytes(rgb), "the flattened picture")
        self.assertEqual([(name, bbox) for name, _mode, bbox, _tile in image.layers],
                         [("Marks (keep visible)", (0, 0, width, height)),
                          ("Template (can be hidden)", (0, 0, width, height)), ("Draw here", (0, 0, 0, 0))])
        # (Pillow opens a PSD as frame 1, the flattened picture, so seek(1) alone stays there: frame 2, the
        # Template, first; an empty layer, Draw here, is no frame it can load. Pillow fills a layer's bands R, G,
        # B, A in the order the channels come in the file, whatever their ids: the transparency comes first, as
        # Photoshop writes it, so Pillow's R is the alpha, its G the red, and so on)
        template = parse_psd(written_psd(sheet, rows), self)["layers"][1]["pixels"]
        image.seek(2)
        rgba = bytearray(4 * width * height)
        rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = template[-1], template[0], template[1], template[2]
        self.assertEqual(image.mode, "RGBA")
        self.assertTrue(image.tobytes() == bytes(rgba), "the Template layer, as Pillow decodes it")
        image.seek(1)
        raster = marks_raster(sheet)
        rgba[1::4] = rgba[2::4] = rgba[3::4] = raster
        rgba[0::4] = b"\xff" * (width * height)
        self.assertEqual(image.mode, "RGBA")
        self.assertTrue(image.tobytes() == bytes(rgba), "the Marks layer, as Pillow decodes it")

    def test_psd_tools_reads_the_layers_and_their_locks(self):
        try:
            from psd_tools import PSDImage
            from psd_tools.constants import Tag
        except ImportError:
            self.skipTest("no psd-tools in this Python")
        import io
        sheet = psd_sheet()
        width, height = sheet.size()
        psd = PSDImage.open(io.BytesIO(written_psd(sheet, sheet_picture(sheet))))
        self.assertEqual((psd.width, psd.height), (width, height))
        layers = list(psd)
        self.assertEqual([layer.name for layer in layers], list(fb.PSD_LAYERS), "bottom to top")
        self.assertEqual([layer.visible for layer in layers], [True, True, True])
        self.assertEqual([layer.opacity for layer in layers], [255, fb.PSD_TEMPLATE_OPACITY, 255], "the Template at a third")
        self.assertEqual([tuple(layer.bbox) for layer in layers], [(0, 0, width, height)] * 2 + [(0, 0, 0, 0)])
        self.assertEqual([layer.tagged_blocks.get_data(Tag.PROTECTED_SETTING) for layer in layers], [7, 7, None])
        marks = layers[0].topil()
        self.assertEqual((marks.mode, marks.size), ("RGBA", (width, height)))
        self.assertEqual(marks.tobytes()[0::4], marks_raster(sheet), "the Marks layer, as psd-tools decodes it")
        self.assertIsNone(layers[2].topil(), "Draw here: no pixels")

    def test_a_psd_without_a_real_flattened_picture_is_told(self):
        """Photoshop with Maximize Compatibility off saves a blank stand-in for the flattened picture, and says so
        in its Version Info resource (0x0421, hasRealMergedData 0): the row says it plainly."""
        import io
        import shutil
        import struct
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-psd-")
        self.addCleanup(shutil.rmtree, folder, True)

        def psd_with(real):
            other = b"8BIM" + struct.pack(">H", 0x03ED) + b"\x03abc" + struct.pack(">I", 3) + b"xyz\x00"
            info = struct.pack(">I", 1) + bytearray([real]) + b"\x00" * 8
            version = b"8BIM" + struct.pack(">H", 0x0421) + b"\x00\x00" + struct.pack(">I", len(info)) + bytes(info)
            resources = other + version + (b"\x00" if len(info) % 2 else b"")
            return (b"8BPS" + struct.pack(">H6xHIIHH", 1, 3, 4, 4, 8, 3) + struct.pack(">I", 0) +
                    struct.pack(">I", len(resources)) + resources + b"\x00" * 64)
        cases = {"blank.psd": psd_with(0), "real.psd": psd_with(1), "ours.psd": written_psd(psd_sheet(), sheet_picture(psd_sheet())),
                 "sheet.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "short.psd": b"8BPS\x00\x01"}
        for name, data in cases.items():
            with io.open(os.path.join(folder, name), "wb") as handle:
                handle.write(data)
        said = dict((name, fb.psd_without_picture(os.path.join(folder, name))) for name in cases)
        self.assertEqual(said, {"blank.psd": True, "real.psd": False, "ours.psd": False, "sheet.png": False,
                                "short.psd": False})
        self.assertFalse(fb.psd_without_picture(os.path.join(folder, "gone.psd")))
        self.assertTrue(fb.PSD_NO_PICTURE.startswith("not read: a PSD"))
        self.assertIn("Maximize Compatibility", fb.PSD_NO_PICTURE)
        self.assertFalse(fb.PSD_NO_PICTURE.endswith("."), "a list cell's note: no period")
        source = builder_source()
        self.assertIn("item.setText(3, PSD_NO_PICTURE if psd_without_picture(path) else \"not read: %s\" % gray)", source)


def estimate_picture(sheet, guides=True):
    """A sheet painted closer to Qt's than sheet_picture, to weigh a PSD by: each box's frame, metric lines (the
    baseline thicker, as render_sheet's pens), and origin line in the guides' blue; its label as a few short
    strokes with soft edges; with guides, FreeLang's "d" (GUIDE_LETTER: a bowl and a stem) smoothed in the guide
    characters' tint, on the box's baseline at the sheet's em; then the marks in black. Rows of Format_RGB32
    bytes (B, G, R, 255 a pixel)."""
    width, height = sheet.size()
    rows = [bytearray(b"\xff" * (4 * width)) for _ in range(height)]
    bw, bh = sheet.box_size()
    white = bytearray(b"\xff\xff\xff\xff")

    def tint(rgb, share):
        return bytearray([int(round(255 - share * (255 - c))) for c in (rgb[2], rgb[1], rgb[0])] + [255])
    cell = None
    if guides:  # (the same letter in every box: its pixels worked out once)
        left, top = sheet.cell(0)
        _, baseline = sheet.origin(0)
        x = fb.guide_left(sheet, 0, GUIDE_LETTER_INK[0] * sheet.em, GUIDE_LETTER_INK[1] * sheet.em) - left
        cover = coverage(bw, bh, [em_polygon(poly, x, baseline - top, sheet.em) for poly in GUIDE_LETTER])
        cell = [b"".join(bytes(tint(fb.GUIDE_INK_RGB, share) if share else white) for share in cover[y * bw:(y + 1) * bw])
                for y in range(bh)]
    blue = tint(fb.GUIDE_RGB, 1.0)
    thin, base = int(max(1.0, sheet.em / 400.0)), int(round(max(2.0, sheet.em / 200.0)))
    for i in range(len(sheet.names)):
        left, top = [int(v) for v in sheet.cell(i)]
        if cell is not None:
            for y in range(bh):
                rows[top + y][4 * left:4 * (left + bw)] = cell[y]

        def fill(x0, y0, x1, y1, pixel):
            for y in range(max(0, y0), min(height, y1)):
                rows[y][4 * x0:4 * x1] = pixel * (x1 - x0)
        for x0, y0, x1, y1 in ((left, top, left + bw, top + thin), (left, top + bh - thin, left + bw, top + bh),
                               (left, top, left + thin, top + bh), (left + bw - thin, top, left + bw, top + bh)):
            fill(x0, y0, x1, y1, blue)
        for name, y in sheet.guides(i):
            width_ = base if name == "baseline" else thin
            y0 = int(round(y - width_ / 2.0))
            fill(left, y0, left + bw, y0 + width_, blue)
        ox = int(round(sheet.origin(i)[0]))
        fill(ox, top, ox + thin, top + bh, blue)
        strip = int(round(fb.LABEL * sheet.em))
        for k in range(4):  # (the label: letter-like strokes, a soft pixel at each side)
            x0, y0, y1 = left + 2 + 4 * k, top - strip + strip // 4, top - strip // 4
            fill(x0, y0, x0 + 1, y1, tint(fb.GUIDE_RGB, 0.4))
            fill(x0 + 1, y0, x0 + 2, y1, blue)
            fill(x0 + 2, y0, x0 + 3, y1, tint(fb.GUIDE_RGB, 0.6))
    u = sheet.unit
    for x, y, w, h in fb.marks(sheet):
        for yy in range(int(round(y * u)), int(round((y + h) * u))):
            rows[yy][4 * int(round(x * u)):4 * int(round((x + w) * u))] = b"\x00\x00\x00\xff" * int(round(w * u))
    return [bytes(row) for row in rows]


ESTIMATE_SHEETS = ((60, 4), (120, 9), (200, 6), (150, 12))  # (em, boxes): small, so the test stays quick


def estimate_sheet(em, boxes):
    names = [chr(ord("A") + k) for k in range(boxes)]
    return fb.Sheet(names, names, METRICS, em, family="Estimate")


class EstimateTests(unittest.TestCase):
    """The size a save will take, said in the log as it starts (the owner, 2026-11-24: "for PSD size risks, is it
    doable to estimate required size before writing?"): PSD by PackBits' own costs, calibrated here on the
    writer's output; PNG, TIFF, and SVG roughly; nothing said under ESTIMATE_QUIET, a warning past ESTIMATE_WARN
    that names a lighter format."""

    def test_a_psds_estimate_is_within_30_percent_of_the_writers_output(self):
        for em, boxes in ESTIMATE_SHEETS:
            sheet = estimate_sheet(em, boxes)
            for guides in (False, True):
                written = len(written_psd(sheet, estimate_picture(sheet, guides)))
                estimate = fb.estimated_size([sheet], ".psd", guides)
                self.assertLess(abs(estimate / float(written) - 1.0), 0.3,
                                "em %d, %d boxes, guides %s: %d estimated, %d written" % (em, boxes, guides, estimate,
                                                                                          written))

    def test_an_svgs_estimate_is_near_its_text_and_adds_the_guides(self):
        for em, boxes in ((60, 4), (150, 12), (300, 30), (500, 100), (500, 400)):
            names = ["uni%04X" % (0x4E00 + k) for k in range(boxes)]
            sheet = fb.Sheet(names, [fb.label_of(n) for n in names], METRICS, em)
            text = len(fb.sheet_svg(sheet, fb.GUIDE_RGB).encode("utf-8"))
            self.assertLess(abs(fb.estimated_size([sheet], ".svg") / float(text) - 1.0), 0.2, "em %d, %d boxes" % (em, boxes))
        sheet = estimate_sheet(120, 9)
        self.assertEqual(fb.estimated_size([sheet], ".svg", True) - fb.estimated_size([sheet], ".svg"), 9 * fb.SVG_GUIDE)
        alternates = fb.Sheet(["A", "A.alt1"], ["A", "A.alt1"], METRICS, 120)
        self.assertEqual(fb.guided_boxes(alternates), 1, "an alternate gets no guide")

    def test_png_and_tiff_follow_the_live_measures(self):
        """A sheet of 100 boxes at the default em, 60.7 megapixels (measured live in FontLab's Qt 5.14 with Big Five:
        PNG 0.2 MB without guides, 0.8 MB with; TIFF about twice)."""
        names = [fb.unichr_(0x4E00 + k) for k in range(100)]
        sheet = fb.Sheet(names, names, fb.Metrics(1000, 880, -120, 500, 700), fb.EM_PIXELS)
        width, height = sheet.size()
        self.assertAlmostEqual(width * height / 1e6, 60.7, delta=8)
        png = fb.estimated_size([sheet], ".png")
        self.assertAlmostEqual(png / 1e6, 0.2, delta=0.06)
        self.assertAlmostEqual(fb.estimated_size([sheet], ".png", True) / 1e6, 0.8, delta=0.24)
        self.assertAlmostEqual(fb.estimated_size([sheet], ".tif"), 2 * png, delta=2)

    def test_the_line_is_quiet_under_50_mb_and_warns_past_1_gb(self):
        ak = shared_module()
        small = [estimate_sheet(120, 9)]
        self.assertEqual(fb.estimate_line(ak, small, ".psd", True), (None, None), "an ordinary save: nothing said")
        names = ["uni%04X" % (0x4E00 + k) for k in range(100)]
        sheet = fb.Sheet(names, [fb.label_of(n) for n in names], METRICS, fb.EM_PIXELS)
        many = [sheet] * 81
        line, level = fb.estimate_line(ak, many, ".psd", True)
        size = fb.estimated_size(many, ".psd", True)
        self.assertGreater(size, fb.ESTIMATE_WARN)
        png, tiff = fb.estimated_size(many, ".png", True), fb.estimated_size(many, ".tif", True)
        self.assertEqual(level, "warning")
        self.assertEqual(line, "Writing <b>81 sheets</b> as PSD: about <b>%s</b>. PNG and TIFF sheets of this template "
                               "would take about %s and %s." % (ak.file_size_text(size), ak.file_size_text(png),
                                                                ak.file_size_text(tiff)))
        self.assertTrue(ak.file_size_text(size).endswith(" GB"))
        line, level = fb.estimate_line(ak, [sheet] * 4, ".psd", True)
        self.assertEqual(level, "info")
        self.assertTrue(line.startswith("Writing <b>4 sheets</b> as PSD: about <b>"), line)
        self.assertTrue(line.endswith(" MB</b>."), line)
        self.assertEqual(fb.estimate_line(ak, [sheet], ".png", True), (None, None))

    def test_file_sizes_read_as_explorers(self):
        ak = shared_module()
        self.assertEqual([ak.file_size_text(size) for size in (0, 1, 512, 1024, 2560, 860000, 1048000, 1048064,
                                                               1048576, 12897485, 1073689000, 1073700000, 1717986918,
                                                               1099511627776)],
                         ["0 KB", "1 KB", "1 KB", "1 KB", "3 KB", "840 KB", "1,023 KB", "1.0 MB", "1.0 MB", "12.3 MB",
                          "1,023.9 MB", "1.0 GB", "1.6 GB", "1,024.0 GB"], "halves up in Python 2.7 and 3 alike")


if __name__ == "__main__":
    unittest.main()
