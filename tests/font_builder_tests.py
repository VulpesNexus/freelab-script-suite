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
                   b=lambda s: "<b>%s</b>" % s,
                   font_key=lambda p: id(p), busy_start=lambda o, what="", stoppable=True: self.progress.append(
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


if __name__ == "__main__":
    unittest.main()
