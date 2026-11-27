# -*- coding: utf-8 -*-
"""Tests of FreeLab's Family Audit: the sources and their names, each audit (glyph sets, compatibility,
metrics and info, kerning, features), the reference chosen, the plan of Assemble as masters and the new
font made from it (through fake FontLab calls), and the window built on a fake Qt. Valid Python 2.7 and
Python 3."""

from __future__ import absolute_import, division, print_function

import io
import os
import shutil
import sys
import tempfile
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
for _folder in ("compare", "checks"):
    sys.path.insert(0, os.path.join(HERE, os.pardir, _folder))
import freelab_font_compare as fcmp  # noqa: E402
import freelab_family_audit as fa  # noqa: E402


def square(left=0, bottom=0, size=100, clockwise=False):
    nodes = [(left, bottom, u"on"), (left + size, bottom, u"on"), (left + size, bottom + size, u"on"),
             (left, bottom + size, u"on")]
    return nodes[::-1] if clockwise else nodes


def curve(kinds=(u"on", u"off", u"off", u"curve")):
    points = [(0, 0), (100, 0), (100, 100), (0, 100)]
    return [(x, y, kind) for (x, y), kind in zip(points, kinds)]


def shape(*contours, **kwargs):
    return fa.structure_of(list(contours), kwargs.get("components", ()), kwargs.get("anchors", ()))


def source(label, glyphs, shapes=None, key=None, info=None, kerning=None, features=None, style=None):
    """A Source: glyphs {name: [code points]} in order (a list of pairs), shapes {name: Structure}."""
    pairs = list(glyphs.items()) if isinstance(glyphs, dict) else list(glyphs)
    return fa.Source(key or (label, label), label, style if style is not None else label, label, pairs, shapes,
                     info, kerning, features)


# ---------------------------------------------------------------------------
# Words and the sources
# ---------------------------------------------------------------------------

class WordTests(unittest.TestCase):
    def test_lists_take_the_oxford_comma(self):
        self.assertEqual(fa.listed([u"Regular"]), u"Regular")
        self.assertEqual(fa.listed([u"Regular", u"Bold"]), u"Regular and Bold")
        self.assertEqual(fa.listed([u"Light", u"Regular", u"Bold"]), u"Light, Regular, and Bold")
        self.assertEqual(fa.names_text(list(u"abcdefgh")), u"a, b, c, d, e, f, and 2 more")

    def test_counts_and_tabs(self):
        self.assertEqual(fa.counted(1, u"glyph"), u"1 glyph")
        self.assertEqual(fa.counted(13956, u"glyph"), u"13,956 glyphs")
        self.assertEqual(fa.counted(2, u"entry", u"entries"), u"2 entries")
        self.assertEqual(fa.tab_text(u"Compatibility"), u"Compatibility", "no count before an audit")
        self.assertEqual(fa.tab_text(u"Compatibility", 1240), u"Compatibility (1,240)")
        # (owner's images 327 and 328: "Metrics and info (0)" over 20 fields alike read as nothing compared)
        self.assertEqual(fa.tab_text(u"Metrics and info", 0), u"Metrics and info (alike)")
        self.assertEqual(fa.sentence(u"two fields differ"), u"Two fields differ.")
        self.assertEqual(fa.sentence(u"<b>2 fields</b> differ"), u"<b>2 fields</b> differ.", "a tag left as it is")

    def test_every_format_fontlab_opens_is_named(self):
        for path, name in ((u"/f/Sans.vfc", u"VFC"), (u"Sans.VFJ", u"VFJ"), (u"Sans.vfb", u"VFB"),
                           (u"\\f\\Sans.ufo", u"UFO"), (u"\\f\\Sans.ufo\\", u"UFO"), (u"Sans.ufoz", u"UFOZ"),
                           (u"Sans.glyphs", u"Glyphs"), (u"Sans.designspace", u"Designspace"), (u"Sans.otf", u"OTF"),
                           (u"Sans.ttf", u"TTF"), (u"Sans.ttc", u"TTC"), (u"Sans.otc", u"OTC"), (u"Sans.woff", u"WOFF"),
                           (u"Sans.woff2", u"WOFF2"), (u"Sans.pfb", u"PFB"), (u"Sans.pfa", u"PFA")):
            self.assertEqual(fa.file_format(path), name, path)
        self.assertEqual(fa.file_format(u""), u"unsaved")
        self.assertEqual(fa.file_format(u"Sans.xyz"), u"XYZ")
        for pattern in (u"*.vfc", u"*.vfj", u"*.vfb", u"*.ufoz", u"*.glyphs", u"*.designspace", u"*.otf", u"*.ttf",
                        u"*.ttc", u"*.woff", u"*.woff2", u"*.pfb", u"*.pfa"):
            self.assertIn(pattern, fa.OPEN_FILTER)

    def test_a_file_inside_a_ufo_stands_for_its_folder(self):
        self.assertEqual(fa.font_path_of(u"/fonts/Sans-Bold.ufo/metainfo.plist"), os.path.normpath(u"/fonts/Sans-Bold.ufo"))
        self.assertEqual(fa.font_path_of(u"/fonts/Sans-Bold.ufo/glyphs/a.glif"), os.path.normpath(u"/fonts/Sans-Bold.ufo"))
        self.assertEqual(fa.font_path_of(u"/fonts/Sans-Bold.otf"), u"/fonts/Sans-Bold.otf")

    def test_paths_alike_whatever_their_separators(self):
        self.assertTrue(fa.same_path(u"\\fonts/corpus/Sans.ttf", u"/fonts/corpus/Sans.ttf"))
        self.assertFalse(fa.same_path(u"", u""))
        self.assertFalse(fa.same_path(u"/a.ttf", u"/b.ttf"))


class StatusHeightTests(unittest.TestCase):
    def test_the_status_line_keeps_the_tallest_tabs_height(self):
        """Owner's images 370 and 371: a tab whose status took a line more than another's moved the lists below
        as the tabs switched. The line is as tall as the tallest tab's at its width."""
        class Label(object):
            text, width, minimum = u"", 400, None

            def setText(self, text):
                self.text = text

            def heightForWidth(self, width):
                return 16 * (1 + self.text.count(u".")) if self.text else 0

            def setMinimumHeight(self, height):
                self.minimum = height

        texts = {"glyphs": u"One. Two. Three.", "compatibility": u"One.", "metrics": u"One. Two.",
                 "kerning": u"One.", "features": u"One."}
        window = fa.FamilyAuditDialog.__new__(fa.FamilyAuditDialog)
        window.status_line, window.entries, window.audit = Label(), [1], object()
        window.status_of = lambda key: texts[key]
        for key, lines in (("compatibility", 2), ("glyphs", 4), ("metrics", 3)):
            window.current_key = lambda key=key: key
            window.show_status()
            self.assertEqual(window.status_line.text, texts[key], "the shown tab's line")
            self.assertEqual(window.status_line.minimum, 16 * 4, "as tall as the glyph sets' three sentences")
        window.audit = None
        window.show_status()
        self.assertEqual(window.status_line.minimum, 0, "nothing compared: no room kept")


class SourceTests(unittest.TestCase):
    def test_labels_name_a_master_or_a_style_uniquely(self):
        entries = [(u"Sans", u"Regular", u"Regular", 1, u"Sans-Regular.otf"),
                   (u"Sans", u"Bold", u"Bold", 1, u"Sans-Bold.otf"),
                   (u"Sans VF", u"Regular", u"Light", 3, u"SansVF.vfc"),
                   (u"Sans VF", u"Regular", u"Black", 3, u"SansVF.vfc")]
        self.assertEqual(fa.source_labels(entries), [u"Regular", u"Bold", u"Light", u"Black"])
        twice = [(u"Sans", u"Regular", u"Regular", 1, u"Sans.otf"), (u"Serif", u"Regular", u"Regular", 1, u"Serif.otf")]
        self.assertEqual(fa.source_labels(twice), [u"Regular (Sans)", u"Regular (Serif)"], "the font's name first")
        same = [(u"Sans", u"Bold", u"Bold", 1, u"old.otf"), (u"Sans", u"Bold", u"Bold", 1, u"new.otf")]
        self.assertEqual(fa.source_labels(same), [u"Bold (Sans, old.otf)", u"Bold (Sans, new.otf)"], "then its file")
        unsaved = [(u"", u"", u"Regular", 1, u""), (u"", u"", u"Regular", 1, u"")]
        self.assertEqual(fa.source_labels(unsaved), [u"Regular 1", u"Regular 2"], "then a number")

    def test_weights_and_widths_from_style_names(self):
        for style, weight in ((u"Thin", 100), (u"ExtraLight", 200), (u"Light Italic", 300), (u"Regular", 400),
                              (u"Italic", 400), (u"Medium", 500), (u"SemiBold", 600), (u"Bold", 700),
                              (u"Extra Bold", 800), (u"Black", 900), (u"Bold Condensed", 700)):
            self.assertEqual(fa.style_weight(style), weight, style)
        self.assertIsNone(fa.style_weight(u"Display"), "a name that says nothing of weight")
        self.assertEqual(fa.style_width(u"Bold Condensed"), 3)
        self.assertEqual(fa.style_width(u"SemiCondensed"), 4)
        self.assertEqual(fa.style_width(u"Expanded"), 7)
        self.assertEqual(fa.style_width(u"Regular"), 5)

    def test_the_reference_is_the_upright_nearest_regular(self):
        sources = [source(u"Light", {}), source(u"Italic", {}), source(u"Bold", {}), source(u"Regular", {})]
        self.assertEqual(fa.default_reference(sources), (u"Regular", u"Regular"))
        sources = [source(u"Bold", {}), source(u"Book", {}), source(u"Light", {})]
        self.assertEqual(fa.default_reference(sources), (u"Book", u"Book"))
        # Its own weight class first: a master named "Wide" at 400 over one at 700
        sources = [source(u"Heavy", {}, info={"weight_class": 700}), source(u"Wide", {}, info={"weight_class": 400})]
        self.assertEqual(fa.default_reference(sources), (u"Wide", u"Wide"))
        sources = [source(u"Italic", {}, info={"italic_angle": -12}), source(u"Medium", {})]
        self.assertEqual(fa.default_reference(sources), (u"Medium", u"Medium"), "an italic is never first")
        self.assertIsNone(fa.default_reference([]))

    def test_the_window_font_and_its_family_ticked_first(self):
        entries = [fa.SourceEntry(1, u"Regular", family=u"Sans"), fa.SourceEntry(2, u"Bold", family=u"Sans"),
                   fa.SourceEntry(3, u"Regular", family=u"Serif"), fa.SourceEntry(4, u"Regular", family=u"Mono")]
        self.assertEqual(fa.default_ticks(entries, own_font=3), set([(3, u"Regular")]))
        self.assertEqual(fa.default_ticks(entries, own_font=1), set([(1, u"Regular"), (2, u"Bold")]))
        self.assertEqual(fa.default_ticks(entries), set([(1, u"Regular"), (2, u"Bold")]), "no font: the largest family")

    def test_fonts_that_came_in_matched_with_the_files_asked(self):
        matched, pending, left = fa.match_opened([u"/f/A.otf", u"/f/B.vfc"], [(7, u"\\f\\B.vfc"), (8, u"")])
        self.assertEqual(matched, [(u"/f/B.vfc", 7), (u"/f/A.otf", 8)], "a font without a path: the file left")
        self.assertEqual((pending, left), ([], []))
        matched, pending, left = fa.match_opened([u"/f/A.otf"], [(9, u"/other/Z.ttf")])
        self.assertEqual((matched, pending, left), ([], [u"/f/A.otf"], [9]), "another font is not taken for it")


# ---------------------------------------------------------------------------
# The audits
# ---------------------------------------------------------------------------

class GlyphSetTests(unittest.TestCase):
    def test_missing_glyphs_by_source(self):
        regular = source(u"Regular", [(u"A", [0x41]), (u"B", [0x42]), (u"C", [0x43])])
        bold = source(u"Bold", [(u"A", [0x41]), (u"C", [0x43]), (u"D", [0x44])])
        report = fa.audit_glyph_sets([regular, bold], regular.key)
        self.assertEqual(report.missing, [(u"Regular", [u"D"]), (u"Bold", [u"B"])])
        self.assertEqual(report.total, 4)
        self.assertEqual(report.lacking(), set([u"B", u"D"]))
        self.assertEqual(fa.glyph_sets_line(report, [regular, bold]),
                         u"<b>2 of 4 glyphs</b> are missing from some sources.")

    def test_code_points_that_differ_both_ways(self):
        regular = source(u"Regular", [(u"a", [0x61]), (u"eacute", [0xE9]), (u"mu", [0xB5, 0x3BC])])
        bold = source(u"Bold", [(u"a", []), (u"uni00E9", [0xE9]), (u"mu", [0x3BC, 0xB5])])
        report = fa.audit_glyph_sets([regular, bold], regular.key)
        texts = dict((d.subject, (d.kind, d.text)) for d in report.codes)
        self.assertEqual(texts[u"a"], ("glyph", u"U+0061 in Regular; none in Bold"))
        self.assertNotIn(u"mu", texts, "the same code points in another order")
        self.assertEqual(texts[u"U+00E9"], ("code", u"eacute in Regular; uni00E9 in Bold"))
        self.assertNotIn(u"U+0061", texts, "a code point one source lacks: said of its glyph, a")
        self.assertEqual([d.names for d in report.codes if d.subject == u"U+00E9"], [[u"eacute", u"uni00E9"]])

    def test_one_line_at_one(self):
        regular = source(u"Regular", [(u"A", [0x41]), (u"B", [])])
        bold = source(u"Bold", [(u"A", [0x41])])
        self.assertEqual(fa.glyph_sets_line(fa.audit_glyph_sets([regular, bold]), [regular, bold]),
                         u"<b>1 of 2 glyphs</b> is missing from some sources.")
        same = source(u"Bold", [(u"A", [0x41]), (u"B", [])])
        self.assertEqual(fa.glyph_sets_line(fa.audit_glyph_sets([regular, same]), [regular, same]),
                         u"The <b>2 sources</b> have the same <b>2 glyphs</b>, with the same code points.")


class CompatibilityTests(unittest.TestCase):
    def test_a_structure_reads_kinds_and_directions(self):
        s = shape(square(), square(20, 20, 40, clockwise=True), curve(), components=[(u"acute", None)],
                  anchors=[(u"top", 0, 0), (u"bottom", 0, 0)])
        self.assertEqual(s.contours, [(u"oooo", 1), (u"oooo", -1), (u"oxxc", 1)])
        self.assertEqual(s.components, [u"acute"])
        self.assertEqual(s.anchors, [u"bottom", u"top"], "sorted: an anchor's order is no difference")

    def test_the_first_difference_in_order(self):
        a = shape(square(), curve(), components=[u"acute"], anchors=[u"top"])
        same = shape(square(10, 10), curve(), components=[u"acute"], anchors=[u"top"])
        self.assertIsNone(fa.compare_structures(a, same, u"Regular", u"Bold"), "moved nodes are not structure")
        self.assertEqual(fa.compare_structures(a, shape(square()), u"Regular", u"Bold"),
                         ("contours", u"2 contours in Regular, 1 in Bold"))
        self.assertEqual(fa.compare_structures(a, shape(square(), curve(), components=[u"grave"], anchors=[u"top"]),
                                               u"Regular", u"Bold"),
                         ("components", u"components acute in Regular, grave in Bold"))
        b = shape(square(), curve(), components=[u"a", u"b"])
        self.assertEqual(fa.compare_structures(b, shape(square(), curve(), components=[u"b", u"a"]), u"R", u"B"),
                         ("components", u"components in another order in B"))
        five = [(0, 0, u"on"), (50, -10, u"on"), (100, 0, u"on"), (100, 100, u"on"), (0, 100, u"on")]
        self.assertEqual(fa.compare_structures(a, shape(five, curve(), components=[u"acute"], anchors=[u"top"]),
                                               u"Regular", u"Bold"),
                         ("nodes", u"contour 1: 4 nodes in Regular, 5 in Bold"))
        self.assertEqual(fa.compare_structures(a, shape(square(), curve((u"on", u"off", u"off", u"on")),
                                                        components=[u"acute"], anchors=[u"top"]), u"Regular", u"Bold"),
                         ("types", u"contour 2, node 4: curve in Regular, on in Bold"))
        self.assertEqual(fa.compare_structures(a, shape(square(clockwise=True), curve(), components=[u"acute"],
                                                        anchors=[u"top"]), u"Regular", u"Bold"),
                         ("direction", u"contour 1 runs the other way in Bold"))
        self.assertEqual(fa.compare_structures(a, shape(square(), curve(), components=[u"acute"], anchors=[u"ogonek"]),
                                               u"Regular", u"Bold"),
                         ("anchors", u"anchor top only in Regular; anchor ogonek only in Bold"))

    def test_each_source_against_the_reference(self):
        regular = source(u"Regular", [(u"A", []), (u"B", []), (u"C", [])],
                         {u"A": shape(square()), u"B": shape(square()), u"C": None})
        bold = source(u"Bold", [(u"A", []), (u"B", []), (u"C", []), (u"D", [])],
                      {u"A": shape(square()), u"B": shape(square(), square()), u"C": shape(square()), u"D": shape(square())})
        black = source(u"Black", [(u"A", []), (u"D", [])], {u"A": shape(square(clockwise=True)), u"D": shape(square())})
        report = fa.audit_compatibility([bold, regular, black], regular.key)
        found = dict((r.name, r) for r in report.results)
        self.assertEqual([r.name for r in report.results], [u"A", u"B", u"C", u"D"], "the reference's order")
        self.assertEqual((found[u"A"].kind, found[u"A"].against), ("direction", u"Black"))
        self.assertEqual(found[u"B"].text, u"1 contour in Regular, 2 in Bold")
        self.assertEqual(found[u"C"].kind, "unread")
        self.assertIsNone(found[u"D"].kind, "the reference lacks it: Bold and Black compared")
        self.assertEqual(found[u"D"].sources, [u"Bold", u"Black"])
        self.assertEqual(report.single, [])
        self.assertEqual(len(report.compatible()), 1)
        self.assertEqual(sorted(report.by_kind()), ["contours", "direction", "unread"])
        line = fa.compatibility_line(report)
        self.assertTrue(line.startswith(u"<b>1 of 4 glyphs</b> match in structure"), line)
        self.assertIn(u"does not promise it", line, "no promise of interpolation")

    def test_a_glyph_in_one_source_is_not_compared(self):
        regular = source(u"Regular", [(u"A", [])], {u"A": shape(square())})
        bold = source(u"Bold", [(u"B", [])], {u"B": shape(square())})
        report = fa.audit_compatibility([regular, bold], regular.key)
        self.assertEqual((report.results, report.single), ([], [u"A", u"B"]))
        self.assertEqual(fa.compatibility_line(report), u"No glyph is in two sources: there is nothing to compare.")


class InfoTests(unittest.TestCase):
    def test_fields_grouped_by_what_should_match(self):
        regular = source(u"Regular", {}, info={"family": u"Sans", "style": u"Regular", "version": u"1.002", "upm": 1000.0,
                                               "x_height": 500.0, "weight_class": 400, "italic_angle": 0.0})
        bold = source(u"Bold", {}, info={"family": u"Sans", "style": u"Bold", "version": u"1.001", "upm": 1000.0,
                                         "x_height": 512.0, "weight_class": 700, "italic_angle": 0.0})
        rows = dict((r.key, r) for r in fa.audit_info([regular, bold]))
        self.assertEqual(rows["version"].group, "mismatch")
        self.assertEqual(rows["version"].values, [(u"Regular", u"1.002"), (u"Bold", u"1.001")])
        self.assertEqual(rows["family"].group, "same")
        self.assertEqual(rows["upm"].values[0], (u"Regular", u"1000"), "a whole number without decimals")
        self.assertEqual(rows["style"].group, "style")
        self.assertEqual(rows["weight_class"].group, "style")
        self.assertEqual(rows["italic_angle"].values[0], (u"Regular", u"0"))
        self.assertNotIn("win_ascent", rows, "a field no source gives is not listed")
        self.assertEqual(fa.info_line(fa.audit_info([regular, bold])),
                         u"<b>1 field</b> that should match across a family differs (Version); <b>3 fields</b> differ "
                         u"by style.")
        self.assertEqual(fa.info_line(fa.audit_info([regular, regular])), u"<b>7 fields</b> are alike in every source.")


def kerning(classes=None, values=None):
    return fa.Kerning(classes or {}, values or {})


A_V = ((u"A", False), (u"V", False))
T_O = ((u"T", False), (u"o_lc", True))


class KerningTests(unittest.TestCase):
    def test_classes_entries_and_signs(self):
        regular = source(u"Regular", {}, kerning=kerning({u"o_lc": ("KernRight", [u"o", u"oacute"])},
                                                         {A_V: -80, T_O: 40}))
        bold = source(u"Bold", {}, kerning=kerning({u"o_lc": ("KernRight", [u"o", u"odieresis"]),
                                                    u"A_uc": ("KernLeft", [u"A"])}, {A_V: -90, T_O: -60}))
        black = source(u"Black", {}, kerning=kerning({u"o_lc": ("KernRight", [u"o", u"oacute"])}, {T_O: 20}))
        found = fa.audit_kerning([bold, regular, black], regular.key)
        rows = [(f.kind, f.subject, f.reason) for f in found]
        self.assertIn(("class", u"class A_uc", u"not in Regular and Black"), rows)
        self.assertIn(("class", u"class o_lc", u"Bold lacks oacute; Bold adds odieresis"), rows,
                      "its members against the reference's")
        self.assertIn(("missing", u"A \N{MULTIPLICATION SIGN} V", u"not kerned in Black"), rows)
        sign = [f for f in found if f.kind == "sign"]
        self.assertEqual([f.subject for f in sign], [u"T \N{MULTIPLICATION SIGN} class o_lc"])
        self.assertEqual(sign[0].values, [(u"Regular", u"40"), (u"Bold", u"-60"), (u"Black", u"20")])
        self.assertEqual(fa.kerning_line(found, [regular, bold, black]),
                         u"<b>2 classes</b> with members that differ, <b>1 entry</b> kerned in some sources only, and "
                         u"<b>1 entry</b> tightening in one source and loosening in another.")

    def test_a_source_without_kerning_said_once(self):
        regular = source(u"Regular", {}, kerning=kerning({}, {A_V: -80, T_O: 20}))
        empty = source(u"Bold", {}, kerning=kerning())
        unread = source(u"Black", {}, kerning=None)
        found = fa.audit_kerning([regular, empty, unread], regular.key)
        self.assertEqual([(f.kind, f.subject) for f in found], [("none", u"Bold")], "not every entry listed against it")
        self.assertEqual(fa.kerning_line(found, [regular, empty, unread]),
                         u"<b>1 source</b> without kerning. The kerning of <b>Black</b> could not be read.")
        self.assertEqual(fa.kerning_line([], [regular, regular]),
                         u"The <b>2 sources</b> kern the same entries, with the same signs, and their classes hold the "
                         u"same glyphs.")


def feature(tag, body):
    return u"feature %s {\n%s} %s;\n" % (tag, body, tag)


class FeatureTests(unittest.TestCase):
    def test_features_against_the_reference(self):
        regular = source(u"Regular", {}, features=[(fcmp.PREFIX, u"languagesystem DFLT dflt;\n"),
                                                   (u"liga", feature(u"liga", u"  sub f i by fi;\n")),
                                                   (u"kern", feature(u"kern", u"  pos A V -80;\n"))])
        bold = source(u"Bold", {}, features=[(u"liga", feature(u"liga", u"  sub f i by fi;\n  sub f l by fl;\n")),
                                             (u"kern", feature(u"kern", u"  pos A V -80;\n")),
                                             (fcmp.PREFIX, u"languagesystem DFLT dflt;\n"),
                                             (fcmp.CLASSES, u"@x = [a];")])
        found = fa.audit_features([bold, regular], regular.key, fcmp)
        self.assertEqual([(f.tag, f.kind) for f in found],
                         [(fcmp.PREFIX, "same"), (u"liga", "differs"), (u"kern", "same"), (fcmp.CLASSES, "missing")],
                         "the prefix first, the classes last, in the reference's order")
        liga = found[1]
        self.assertEqual(liga.base, u"Regular")
        self.assertEqual([(s.label, s.kind, s.text) for s in liga.states], [(u"Bold", "differs", u"1 line only in Bold")])
        self.assertIn((u"+", u"  sub f l by fl;"), liga.states[0].rows, "Font Compare's line diff")
        classes = found[3]
        self.assertEqual(classes.base, u"Bold", "the reference lacks it: compared with the first that has it")
        self.assertEqual([(s.label, s.kind) for s in classes.states], [(u"Regular", "only_a")])
        self.assertEqual(fa.features_line(fa.audit_features([bold, regular], regular.key, fcmp), [regular, bold]),
                         u"<b>1 feature</b> missing from some sources; <b>1 feature</b> with code that differs.")

    def test_unread_features_left_out(self):
        regular = source(u"Regular", {}, features=[(u"liga", feature(u"liga", u"  sub f i by fi;\n"))])
        self.assertEqual(fa.audit_features([regular, source(u"Bold", {}, features=None)], regular.key, fcmp), [])
        same = source(u"Bold", {}, features=[(u"liga", feature(u"liga", u"  sub f i by fi;\n"))])
        self.assertEqual(fa.features_line(fa.audit_features([regular, same], regular.key, fcmp), [regular, same]),
                         u"<b>1 feature</b> is alike in every source.")


class AuditTests(unittest.TestCase):
    def test_every_tab_counted(self):
        regular = source(u"Regular", [(u"A", [0x41]), (u"B", [0x42])], {u"A": shape(square()), u"B": shape(square())},
                         info={"version": u"1.0"}, kerning=kerning({}, {A_V: -80}),
                         features=[(u"liga", feature(u"liga", u"  sub f i by fi;\n"))])
        bold = source(u"Bold", [(u"A", [0x41])], {u"A": shape(square(), square())}, info={"version": u"1.1"},
                      kerning=kerning({}, {}), features=[(u"liga", feature(u"liga", u"  sub f l by fl;\n"))])
        audit = fa.Audit([regular, bold], regular.key, fcmp)
        self.assertEqual(audit.counts(), {"glyphs": 1, "compatibility": 1, "metrics": 1, "kerning": 1, "features": 1})
        self.assertEqual(audit.labels, [u"Regular", u"Bold"])


# ---------------------------------------------------------------------------
# Assemble as masters
# ---------------------------------------------------------------------------

class PlanTests(unittest.TestCase):
    def sources(self):
        regular = source(u"Regular", [(u"A", [0x41]), (u"B", [0x42]), (u"Aacute", [0xC1])],
                         info={"weight_class": 400, "width_class": 5, "upm": 1000.0},
                         features=[(u"liga", u"x")])
        bold = source(u"Bold", [(u"A", [0x41]), (u"Aacute", [0xC1]), (u"C", [0x43])],
                      info={"weight_class": 700, "width_class": 5, "upm": 1000.0}, features=[(u"liga", u"y")])
        light = source(u"Light", [(u"A", [0x41, 0x391]), (u"B", [0x42])],
                       info={"weight_class": 300, "width_class": 5, "upm": 1000.0}, features=[(u"liga", u"x")])
        return regular, bold, light

    def test_which_layer_goes_where_and_what_stays_empty(self):
        regular, bold, light = self.sources()
        plan = fa.plan_assembly([light, bold, regular], regular.key)
        self.assertEqual(plan.masters, [(u"Regular", regular.key), (u"Light", light.key), (u"Bold", bold.key)],
                         "the reference's master first (the default), then the others as listed")
        self.assertEqual(plan.order, [u"A", u"B", u"Aacute", u"C"], "the reference's glyph order, then the others'")
        self.assertEqual(plan.layers[u"A"], [u"Regular", u"Light", u"Bold"])
        self.assertEqual(plan.layers[u"B"], [u"Regular", u"Light"])
        self.assertEqual(plan.layers[u"C"], [u"Bold"])
        self.assertEqual(plan.empty, [(u"Regular", [u"C"]), (u"Light", [u"Aacute", u"C"]), (u"Bold", [u"B"])])
        self.assertEqual(plan.codes[u"A"], [0x41], "the reference's code points")
        self.assertEqual(plan.codes[u"C"], [0x43], "else the first source's")
        notes = u" ".join(plan.notes)
        self.assertIn(u"the glyph's of Regular kept (A)", notes)
        self.assertIn(u"Feature code, its classes, and the font info come from Regular alone: Bold has other code", notes)

    def test_an_axis_only_for_the_classes_that_differ(self):
        regular, bold, light = self.sources()
        plan = fa.plan_assembly([regular, bold, light], regular.key)
        self.assertEqual([(a.name, a.tag) for a in plan.axes], [(u"Weight", u"wght")], "no width axis: all 5")
        self.assertEqual(plan.axes[0].locations, {u"Regular": 400, u"Bold": 700, u"Light": 300})
        self.assertEqual(plan.axes[0].range, (300, 700))
        same = [source(u"Regular", [], info={"weight_class": 400}), source(u"Other", [], info={"weight_class": 400})]
        self.assertEqual(fa.plan_assembly(same, same[0].key).axes, [], "no axis where nothing differs")

    def test_styles_on_one_location_are_said(self):
        sources = [source(u"Regular", [], info={"weight_class": 400}), source(u"Italic", [], info={"weight_class": 400}),
                   source(u"Bold", [], info={"weight_class": 700})]
        plan = fa.plan_assembly(sources, sources[0].key)
        self.assertIn(u"Regular and Italic share one location on the weight axis", u" ".join(plan.notes))

    def test_other_units_per_em_said_and_the_audit_counted(self):
        sources = [source(u"Regular", [(u"A", [])], info={"upm": 1000.0}), source(u"Bold", [(u"A", [])], info={"upm": 2048.0})]
        compat = fa.Compatibility([fa.GlyphCompat(u"A"), fa.GlyphCompat(u"B", "contours")], [])
        plan = fa.plan_assembly(sources, sources[0].key, compat)
        self.assertIn(u"other units per em (1000 in Regular; 2048 in Bold)", u" ".join(plan.notes))
        self.assertEqual(plan.matched, (1, 2))

    def test_components_after_the_glyphs_they_draw(self):
        order = fa.component_order({u"Aacute": [u"A", u"acute"], u"Aacute.sc": [u"Aacute"], u"A": [], u"loop": [u"loop2"],
                                    u"loop2": [u"loop"]})
        self.assertLess(order.index(u"A"), order.index(u"Aacute"))
        self.assertLess(order.index(u"Aacute"), order.index(u"Aacute.sc"))
        self.assertEqual(sorted(order), sorted([u"Aacute", u"Aacute.sc", u"A", u"loop", u"loop2"]), "a loop ends")


class Recorder(object):
    """What the fake FontLab calls did, in order."""

    def __init__(self):
        self.events = []


class SourceLayer(object):
    def __init__(self, owner, width=500.0, parts=(), anchors=0):
        self.owner, self.width, self.parts, self.anchors = owner, width, list(parts), anchors


class SourcePackage(object):
    """A source font: {(glyph, master): SourceLayer}."""

    path, tfn = u"", u"Source"

    def __init__(self, layers):
        self.layers = layers

    def currentHistoryState(self):
        return 0


class NewLayer(object):
    def __init__(self, glyph, master):
        self.glyph, self.master, self.copied, self.width, self.parts, self.anchors = glyph, master, None, None, None, 0


class NewGlyph(object):
    def __init__(self, name):
        self.name, self.layers, self.codes = name, {}, None


class NewPackage(object):
    def __init__(self, masters=(u"Regular",)):
        self.masters, self.glyphs, self.kerning, self.features, self.info = list(masters), {}, {}, {}, {}
        self.order = []
        self.prefix, self.current, self.axes, self.locations, self.metrics = None, None, [], {}, {}


class FakeCalls(object):
    """FontLabCalls' methods, keeping what they are given."""

    fcmp = fcmp

    def __init__(self, refuse=(), masters=(u"Regular",), keep_masters=True):
        self.record = Recorder()
        self.package = NewPackage(masters)
        self.refuse, self.keep_masters = set(refuse), keep_masters

    def check(self, what):
        if what in self.refuse:
            raise RuntimeError(u"refused")

    def new_package(self):
        return self.package

    def masters(self, package):
        return list(package.masters)

    def rename_master(self, package, old, new):
        package.masters[package.masters.index(old)] = new

    def add_master(self, package, name):
        if self.keep_masters:
            package.masters.append(name)

    def set_names(self, package, family, style):
        self.check("names")
        self.record.events.append(("named", family, style, package.current))

    def show_package(self, package):
        self.record.events.append(("shown",))

    def set_upm(self, package, upm):
        package.info["upm"] = upm

    def new_glyph(self, package, name):
        glyph = package.glyphs[name] = NewGlyph(name)
        package.order.append(name)
        return glyph

    def find_glyph(self, package, name):
        self.record.found = getattr(self.record, "found", 0) + 1  # (looked up again at each use: a kept one crashed FontLab)
        return package.glyphs.get(name)

    def init_layer(self, package, layer):
        layer.ready = True  # (live: a code point set on a glyph whose layers were not set up so crashed FontLab)

    def new_layer(self, glyph, master):
        return glyph.layers.setdefault(master, NewLayer(glyph.name, master))

    def layer(self, package, name, master):
        return package.layers.get((name, master))

    def width(self, layer):
        return layer.width

    def components(self, layer):
        return list(layer.parts)

    def copy_contours(self, layer, target):
        self.check("copy_contours")
        target.copied = layer.owner
        self.record.events.append(("contours", target.glyph, target.master))
        return 1

    def set_components(self, package, target, parts, width):
        target.parts = [name for name, _ in parts]
        self.record.events.append(("components", target.glyph, target.master))

    def copy_anchors(self, layer, target):
        self.check("copy_anchors")
        target.anchors = layer.anchors
        return layer.anchors

    def set_width(self, target, width):
        target.width = width

    def set_codes(self, glyph, codes):
        if not glyph.layers or not all(getattr(layer, "ready", False) for layer in glyph.layers.values()):
            raise RuntimeError("a code point on a glyph whose layers were not set up (crashed FontLab live)")
        glyph.codes = list(codes)

    def update_glyph(self, glyph):
        pass

    def target_kerning(self, package, master):
        return package.kerning.setdefault(master, {"classes": {}, "entries": {}})

    def set_kerning_class(self, kerning, name, members, side):
        kerning["classes"][name] = (side, list(members))

    def write_kerning(self, kerning, entries):
        kerning["entries"].update(dict(entries))
        return []

    def set_prefix(self, package, text):
        package.prefix = text

    def set_feature(self, package, tag, code):
        package.features[tag] = code

    def set_info(self, package, attribute, value):
        package.info[attribute] = value

    def set_version(self, package, major, minor):
        package.info["version"] = (major, minor)

    def set_current_master(self, package, name):
        package.current = name

    def set_metric(self, package, attribute, value):
        package.metrics[(package.current, attribute)] = value

    def add_axis(self, package, name, tag, minimum, default, maximum):
        package.axes.append((name, tag, minimum, default, maximum))
        return name

    def set_location(self, package, master, location):
        package.locations[master] = location

    def rebuild_maps(self, package):
        pass

    def glyphs_shown(self, package):
        self.record.events.append(("listed",))

    def mark_modified(self, package):
        self.record.events.append(("modified",))


class BuildTests(unittest.TestCase):
    def sources(self):
        regular = source(u"Regular", [(u"A", [0x41]), (u"acute", [0x301]), (u"Aacute", [0xC1]), (u"B", [0x42])],
                         info={"weight_class": 400, "upm": 1000.0, "family": u"Sans", "version": u"1.002",
                               "typo_ascender": 800.0, "italic_angle": 0.0, "ascender": 750.0},
                         kerning=kerning({u"A_uc": ("KernLeft", [u"A", u"Aacute"])}, {((u"A_uc", True), (u"V", False)): -80}),
                         features=[(fcmp.PREFIX, u"languagesystem DFLT dflt;"), (u"liga", u"feature liga {} liga;"),
                                   (fcmp.CLASSES, u"@figures = [one two];")])
        bold = source(u"Bold", [(u"Aacute", [0xC1]), (u"A", [0x41]), (u"acute", [0x301])],
                      info={"weight_class": 700, "upm": 1000.0}, kerning=kerning(), features=[])
        regular.package = SourcePackage({
            (u"A", u"Regular"): SourceLayer(u"Regular", 600), (u"acute", u"Regular"): SourceLayer(u"Regular", 0, anchors=1),
            (u"Aacute", u"Regular"): SourceLayer(u"Regular", 600, [(u"A", None), (u"acute", None)]),
            (u"B", u"Regular"): SourceLayer(u"Regular", 580)})
        bold.package = SourcePackage({
            (u"A", u"Bold"): SourceLayer(u"Bold", 640), (u"acute", u"Bold"): SourceLayer(u"Bold", 0),
            (u"Aacute", u"Bold"): SourceLayer(u"Bold", 640, [(u"A", None), (u"acute", None)])})
        return regular, bold

    def build(self, calls=None):
        regular, bold = self.sources()
        plan = fa.plan_assembly([regular, bold], regular.key)
        calls = calls or FakeCalls()
        package, report = fa.build_font(calls, plan, dict((s.key, s) for s in (regular, bold)))
        return calls, plan, package, report

    def test_each_master_takes_its_sources_layers(self):
        calls, plan, package, report = self.build()
        self.assertEqual(package.masters, [u"Regular", u"Bold"], "the first master renamed, the other added")
        self.assertEqual(package.order, [u"A", u"acute", u"Aacute", u"B"], "the reference's glyph order")
        a = package.glyphs[u"A"]
        self.assertEqual((a.layers[u"Regular"].copied, a.layers[u"Regular"].width), (u"Regular", 600))
        self.assertEqual((a.layers[u"Bold"].copied, a.layers[u"Bold"].width), (u"Bold", 640))
        b = package.glyphs[u"B"]
        self.assertIn(u"Bold", b.layers, "a layer in every master")
        self.assertIsNone(b.layers[u"Bold"].copied, "left empty where its source lacks it")
        self.assertEqual(package.glyphs[u"acute"].layers[u"Regular"].anchors, 1)
        self.assertEqual(a.codes, [0x41])
        self.assertEqual(report, [u"The Classes panel's feature classes of Regular are written as code, first in the "
                                  u"prefix.", u"The line metrics of Bold were not read (FontLab gives a script its font's "
                                  u"current master's only): set them in Font Info."], "Bold has no features: none lost")

    def test_a_master_is_made_current_by_setmaster(self):
        # (live, 2026-11-18: "attribute 'master' of 'flPackage' objects is not writable")
        class Package(object):
            current = u"Regular"

            @property
            def master(self):
                return self.current

            def setMaster(self, name):
                self.current = name

        package = Package()
        fa.FontLabCalls.set_current_master(package, u"Bold")
        self.assertEqual(package.master, u"Bold")
        source = io.open(fa.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        self.assertNotIn(u"package.master = ", source, "flPackage.master is never assigned")

    def test_a_fonts_family_is_fontlabs_family_name(self):
        # (live, 2026-11-19: FontLab gave NotoSansJP[wght].ttf the info familyName "Noto Sans JP Thin", its name
        # ID 1, and the tfn "Noto Sans JP": its fixed copy was left unticked as another family than its instance)
        variable = FakeFont(1, u"Noto Sans JP Thin", u"Thin")
        variable.tfn = u"Noto Sans JP"
        self.assertEqual(fa.FontLabCalls.names(variable), (u"Noto Sans JP", u"Thin"))
        unnamed = FakeFont(2, u"Sans", u"Bold")
        unnamed.tfn = None
        self.assertEqual(fa.FontLabCalls.names(unnamed), (u"Sans", u"Bold"), "the info's when FontLab gives none")

    def test_a_glyph_the_new_font_has_already_is_not_added_twice(self):
        # (live, 2026-11-18: a new font comes with its .notdef, and the assembly's own made it twice)
        class Glyph(object):
            isNull = False

            def __init__(self, name):
                self.name = name

        class Package(object):
            def __init__(self):
                self.glyphs, self.added = {u".notdef": Glyph(u".notdef")}, []

            def findName(self, name):
                return self.glyphs.get(name)

            def addGlyph(self, glyph):
                self.added.append(glyph.name)
                self.glyphs[glyph.name] = Glyph(glyph.name)

        class FontLab(object):
            flGlyph = staticmethod(lambda: Glyph(u""))

        calls, package = fa.FontLabCalls(FontLab), Package()
        notdef = package.glyphs[u".notdef"]
        self.assertIs(calls.new_glyph(package, u".notdef"), notdef)
        self.assertEqual(package.added, [], "the font's own taken")
        self.assertEqual(calls.new_glyph(package, u"A").name, u"A")
        self.assertEqual(package.added, [u"A"])

    def test_no_glyph_object_is_kept_while_glyphs_are_added(self):
        # (live, 2026-11-18: setting the code points of the glyph objects kept from their adding crashed FontLab:
        # each later glyph added moved the font's storage under them)
        made = []
        real_new, real_codes = FakeCalls.__dict__["new_glyph"], FakeCalls.__dict__["set_codes"]  # (functions: Python 2 reads unbound methods off a class)

        def new_glyph(calls, package, name):
            for old in made:
                old.stale = True
            glyph = real_new(calls, package, name)
            made.append(glyph)
            return glyph

        def checked(real):
            def call(calls, glyph, *args):
                if getattr(glyph, "stale", False) and glyph.name != made[-1].name:
                    raise AssertionError("a kept glyph object used: %s" % glyph.name)
                return real(calls, glyph, *args)
            return call

        FakeCalls.new_glyph, FakeCalls.set_codes = new_glyph, checked(real_codes)
        self.addCleanup(lambda: (setattr(FakeCalls, "new_glyph", real_new), setattr(FakeCalls, "set_codes", real_codes)))
        original_find = FakeCalls.__dict__["find_glyph"]

        def find_glyph(calls, package, name):
            glyph = original_find(calls, package, name)
            if glyph is not None:
                glyph.stale = False  # (looked up now: a fresh object)
            return glyph
        FakeCalls.find_glyph = find_glyph
        self.addCleanup(setattr, FakeCalls, "find_glyph", original_find)
        calls, plan, package, report = self.build()
        self.assertEqual(package.glyphs[u"A"].codes, [0x41], "set on the glyph looked up again")
        self.assertFalse([line for line in report if u"Code points" in line])

    def test_components_once_their_glyphs_are_drawn(self):
        calls, plan, package, report = self.build()
        events = calls.record.events
        for master in (u"Regular", u"Bold"):
            made = events.index(("components", u"Aacute", master))
            self.assertGreater(made, events.index(("contours", u"A", master)))
            self.assertGreater(made, events.index(("contours", u"acute", master)))
            self.assertGreater(events.index(("contours", u"Aacute", master)), made, "its own outlines after")
        self.assertEqual(package.glyphs[u"Aacute"].layers[u"Bold"].parts, [u"A", u"acute"])
        self.assertLess(events.index(("shown",)), events.index(("contours", u"A", u"Regular")))
        # (the owner, 2026-11-24: the new font's tab read "Unnamed". Named before its window opens)
        named = [event for event in events if event[0] == "named"]
        # (live 2026-11-27: each master has its own style, full, and PostScript names; the second master kept
        # "Unnamed Regular": each is named with it current, by its source's style)
        self.assertEqual(named, [("named", u"Sans", u"Regular", u"Regular"), ("named", u"Sans", u"Bold", u"Bold")])
        self.assertLess(events.index(named[-1]), events.index(("shown",)))
        self.assertEqual(events[-2:], [("listed",), ("modified",)])
        self.assertEqual(package.current, u"Regular", "the reference's master current at the end, the axes placed")

    def test_postscript_names(self):
        self.assertEqual(fa.postscript_name(u"Noto Sans JP", u"Regular (Noto Sans JP, NotoSansJP-Regular.ttf)"),
                         u"NotoSansJP-RegularNotoSansJP,NotoSansJP-Regular.ttf")
        self.assertEqual(fa.postscript_name(u"Sans", u"Bold"), u"Sans-Bold")
        self.assertEqual(len(fa.postscript_name(u"A" * 80, u"Bold")), 63)
        self.assertEqual(fa.postscript_name(u"Café Sans", u"Light"), u"CafSans-Light", "ASCII only")

    def test_the_references_code_info_kerning_and_axes(self):
        calls, plan, package, report = self.build()
        self.assertEqual(package.prefix, u"@figures = [one two];\n\nlanguagesystem DFLT dflt;",
                         "the classes first: the prefix's code may use them")
        self.assertEqual(package.features, {u"liga": u"feature liga {} liga;"})
        self.assertEqual(package.info["familyName"], u"Sans")
        self.assertEqual(package.info["version"], (1, 2))
        self.assertEqual(package.info["openTypeOS2TypoAscender"], 800.0)
        self.assertNotIn("italicAngle", package.info, "each master's own")
        self.assertEqual(package.metrics, {(u"Regular", "ascender_value"): 750.0})
        self.assertEqual(package.current, u"Regular", "the first master current again")
        self.assertEqual(package.kerning[u"Regular"]["classes"], {u"A_uc": ("KernLeft", [u"A", u"Aacute"])})
        self.assertEqual(package.kerning[u"Regular"]["entries"], {((u"A_uc", True), (u"V", False)): -80})
        self.assertNotIn(u"Bold", package.kerning, "a source without kerning: nothing written")
        self.assertEqual(package.axes, [(u"Weight", u"wght", 400, 400, 700)])
        self.assertEqual(package.locations, {u"Regular": {u"Weight": 400}, u"Bold": {u"Weight": 700}})

    def test_coverage_and_win_values_follow_what_the_masters_bring(self):
        import freelab_font_info as fi  # (checks is on the path)
        regular = source(u"Regular", [(u"A", [0x41])],
                         info={"weight_class": 400, "unicode_ranges": [0, 9], "code_pages": [0], "win_ascent": 900.0,
                               "win_descent": 250.0})
        bold = source(u"Bold", [(u"A", [0x41]), (u"uniAC00", [0xAC00])],
                      info={"weight_class": 700, "unicode_ranges": [0, 56], "code_pages": [], "win_ascent": 950.0,
                            "win_descent": 240.0})
        regular.package = SourcePackage({(u"A", u"Regular"): SourceLayer(u"Regular", 600)})
        bold.package = SourcePackage({(u"A", u"Bold"): SourceLayer(u"Bold", 640),
                                      (u"uniAC00", u"Bold"): SourceLayer(u"Bold", 1000)})
        calls = FakeCalls()
        calls.font_info_module = lambda: fi
        plan = fa.plan_assembly([regular, bold], regular.key)
        package, report = fa.build_font(calls, plan, dict((s.key, s) for s in (regular, bold)))
        self.assertEqual(package.info["openTypeOS2UnicodeRanges"], [0, 9, 56],
                         "the reference's, its hand-set bit 9 kept, with Hangul brought by Bold")
        self.assertEqual(package.info["openTypeOS2CodePageRanges"], [0], "no code page completed")
        self.assertEqual((package.info["openTypeOS2WinAscent"], package.info["openTypeOS2WinDescent"]), (950.0, 250.0))
        self.assertIn(u"The Win ascent is 950, the largest of the sources' (Regular's is 900), so that no master's glyphs "
                      u"are clipped.", report)
        self.assertFalse([line for line in report if u"Win descent" in line], "the reference's is the largest")

    def test_without_the_shared_module_the_coverage_is_left_alone(self):
        calls, plan, package, report = self.build()
        self.assertNotIn("openTypeOS2UnicodeRanges", package.info, "not read: left as FontLab makes it")

    def test_what_fontlab_refuses_is_one_line_a_kind(self):
        calls, plan, package, report = self.build(FakeCalls(refuse=("copy_anchors",)))
        lines = [line for line in report if line.startswith(u"Anchors not copied")]
        self.assertEqual(len(lines), 1, report)
        self.assertEqual(lines[0], u"Anchors not copied (FontLab: refused): A (Regular), A (Bold), acute (Regular), "
                                   u"acute (Bold), B (Regular), Aacute (Regular), and 1 more.")

    def test_masters_fontlab_does_not_make_stop_it(self):
        with self.assertRaises(fa.AssembleError) as caught:
            self.build(FakeCalls(keep_masters=False))
        self.assertIn(u"Bold", u"%s" % caught.exception)
        self.assertIsNotNone(caught.exception.package, "the unfinished font is said, never closed")


class AssemblyLineTests(unittest.TestCase):
    def test_what_the_log_says(self):
        regular = source(u"Regular", [(u"A", []), (u"B", [])], info={"weight_class": 400})
        bold = source(u"Bold", [(u"A", [])], info={"weight_class": 700})
        compat = fa.Compatibility([fa.GlyphCompat(u"A")], [u"B"])
        plan = fa.plan_assembly([regular, bold], regular.key, compat)
        lines = fa.assembly_lines(plan, [u"Widths not set: A (Bold)."])
        self.assertEqual(lines[0], (u"Made a new font with <b>2 masters</b> (Regular and Bold) and <b>2 glyphs</b>; "
                                    u"<b>1 layer</b> is left empty where a source lacks its glyph. Nothing in the sources "
                                    u"changed; close the new font without saving to take it back.", "done"))
        # (a glyph's name in italics, as every log has it; no link: it is the new font's glyph, not this window's)
        self.assertIn((u"Left empty in <b>Bold</b>: <i>B</i>.", "info"), lines)
        plan.empty = [(u"Bold", [u"a<b"] + [u"g%d" % n for n in range(fa.NAMES_SHOWN)])]
        self.assertIn((u"Left empty in <b>Bold</b>: <i>a&lt;b</i>, %s, and 1 more." % u", ".join(
            u"<i>g%d</i>" % n for n in range(fa.NAMES_SHOWN - 1)), "info"), fa.assembly_lines(plan, []))
        self.assertIn((u"Axes: Weight (Regular 400, Bold 700).", "info"), lines)
        self.assertIn((u"At the audit, <b>1 of 1 glyph</b> matched in structure: that is needed to interpolate, not a "
                       u"promise of it.", "info"), lines)
        self.assertEqual(lines[-1], (u"Widths not set: A (Bold).", "warning"))
        self.assertEqual(fa.assembly_lines(None, [], u"FontLab made no new font", made=False),
                         [(u"No new font was made: FontLab made no new font. The sources are as they were.", "error")])
        self.assertIn(u"Close it without saving", fa.assembly_lines(plan, [], u"no masters", made=True)[0][0])


# ---------------------------------------------------------------------------
# Reading a source (fake FontLab calls)
# ---------------------------------------------------------------------------

class ReadCalls(object):
    """FontLabCalls' reading methods over plain data."""

    def __init__(self, layers):
        self.layers = layers  # {(glyph, master): Structure}

    def glyph_list(self, package):
        return [(u"A", [0x41]), (u"B", [0x42]), (u"C", [])]

    def layer(self, package, name, master):
        return (name, master) if (name, master) in self.layers else None

    def structure(self, name, layer):
        if name == u"C":
            raise ValueError(u"unreadable")
        return self.layers[layer]

    def kerning(self, package, master):
        raise RuntimeError(u"no kerning")

    def features(self, package):
        return []

    def info(self, package, master):
        return {"upm": 1000.0}


class ReadTests(unittest.TestCase):
    def test_a_master_lacks_the_glyphs_without_a_layer_there(self):
        calls = ReadCalls({(u"A", u"Bold"): shape(square()), (u"C", u"Bold"): shape(square())})
        entry = fa.SourceEntry(5, u"Bold", u"Bold", u"Sans VF", u"Bold", 3)
        read = fa.read_source(calls, entry)
        self.assertEqual(read.glyphs, [(u"A", [0x41]), (u"C", [])])
        self.assertEqual(sorted(read.shapes), [u"A", u"C"])
        self.assertIsNone(read.shapes[u"C"], "read as None where it could not be")
        self.assertIsNone(read.kerning, "None where it could not be read")
        self.assertEqual((read.features, read.info), ([], {"upm": 1000.0}))
        light = fa.read_source(calls, fa.SourceEntry(6, u"Regular", u"Regular", u"Sans", u"Regular", 1), shapes=False)
        self.assertEqual([name for name, _ in light.glyphs], [u"A", u"B", u"C"], "one master: every glyph, unread")
        self.assertIsNone(light.shapes)


# ---------------------------------------------------------------------------
# The window on a fake Qt (PythonQt's API, every call accepted) and a fake FontLab
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


Anything = _AnyMeta(str("Anything"), (object,), {
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
    "__ge__": lambda self, other: False, "__str__": lambda self: "", "__unicode__": lambda self: ""})


class _FakeQtModule(object):
    def __init__(self):
        self.classes = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self.classes:
            self.classes[name] = _AnyMeta(str(name), (Anything,), {})
        return self.classes[name]


class FakeButton(Anything):
    """A button that keeps its text, whether it is enabled, and its properties."""

    def __init__(self, text=u"", *args, **kwargs):
        self.text, self.enabled, self.slots, self.props = text, True, {}, {}

    def setEnabled(self, on):
        self.enabled = bool(on)

    def setText(self, text):
        self.text = text

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)

    def setProperty(self, name, value):
        self.props[name] = value

    def property(self, name):
        return self.props.get(name)

    def setWhatsThis(self, text):
        self.whats = text


class FakeLayout(Anything):
    """A row or column that keeps what is added to it, in order (None: a stretch)."""

    def __init__(self, *args, **kwargs):
        self.items = []

    def addWidget(self, widget, *args):
        self.items.append(widget)

    def addLayout(self, layout, *args):
        self.items.append(layout)

    def addStretch(self, *args):
        self.items.append(None)

    # (as ak.cancel_button reads and fills a row: the Cancel button put right before Close)
    def count(self):
        return len(self.items)

    def itemAt(self, k):
        held = self.items[k]
        return type("Item", (object,), {"widget": lambda item: held})()

    def insertWidget(self, k, widget):
        self.items.insert(k, widget)


class FakeLabel(Anything):
    def __init__(self, text=u"", *args, **kwargs):
        self.text = text

    def setText(self, text):
        self.text = text


class FakeCombo(FakeButton):
    def __init__(self, *args, **kwargs):
        FakeButton.__init__(self)
        self.texts, self.currentIndex = [], -1

    def clear(self):
        self.texts, self.currentIndex = [], -1

    def addItem(self, text):
        self.texts.append(text)
        if self.currentIndex < 0:
            self.currentIndex = 0

    def setCurrentIndex(self, index):
        self.currentIndex = index


class FakeTabs(Anything):
    def __init__(self, *args, **kwargs):
        self.texts, self.currentIndex = [], 0

    def addTab(self, text):
        self.texts.append(text)

    def setTabText(self, index, text):
        self.texts[index] = text


class FakeSplitter(Anything):
    def __init__(self, *args, **kwargs):
        self.widgets = []

    def addWidget(self, widget):
        self.widgets.append(widget)

    def count(self):
        return len(self.widgets)


class FakeInfo(object):
    def __init__(self, family, style, weight):
        self.familyName, self.styleName, self.openTypeOS2WeightClass = family, style, weight


class FakeFontgate(object):
    def __init__(self, number, family, style, weight):
        self.id, self.glyphs, self.info = number, [], FakeInfo(family, style, weight)


class FakeFont(object):
    """An open font as the window lists it."""

    isNull = False

    def __init__(self, number, family, style, masters=None, weight=400, path=u""):
        self.fgPackage = FakeFontgate(number, family, style, weight)
        self.masters = list(masters or [style])
        self.master = self.masters[0]
        self.tfn, self.tsn, self.path = family, style, path
        self.glyphsCount, self.versionMajor, self.versionMinor, self.upm = 3, 1, 2, 1000

    def currentHistoryState(self):
        return 0


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        cls.saved = dict((name, sys.modules.get(name)) for name in ("PythonQt", "fontlab", fa.AUTO_KERNING_MODULE))
        qt = Anything()
        qt.QtCore, qt.QtGui = _FakeQtModule(), _FakeQtModule()
        qt.QtGui.classes.update({"QPushButton": FakeButton, "QHBoxLayout": FakeLayout, "QVBoxLayout": FakeLayout,
                                 "QLabel": FakeLabel, "QComboBox": FakeCombo, "QTabBar": FakeTabs,
                                 "QSplitter": FakeSplitter})
        cls.workspace = workspace = Anything()
        fontlab = Anything()
        fontlab.flWorkspace = Anything()
        fontlab.flWorkspace.instance = lambda: workspace
        fontlab.flPackage = lambda item: item
        sys.modules["PythonQt"], sys.modules["fontlab"] = qt, fontlab
        cls.ak_stamp = getattr(ak, "_freelab_stamp", "unset")
        ak._freelab_stamp = None  # (load_auto_kerning finds no file beside the script: the one loaded here is kept)
        sys.modules[fa.AUTO_KERNING_MODULE] = ak
        cls.ak = ak
        cls.real = dict((name, getattr(ak, name)) for name in ("window_layout", "status_label", "header_separator",
                                                                "busy_start", "busy_progress", "busy_end"))
        cls.fakes()

    @classmethod
    def fakes(cls):
        ak = cls.ak
        ak.window_layout = lambda dialog, scroll=None: FakeLayout()
        ak.status_label = lambda text=u"", plain=False: FakeLabel()
        ak.header_separator = lambda: "header line"
        ak.busy_start = lambda owner, what=u"", stoppable=True: None
        ak.busy_progress = lambda owner, what=None, part=None, force=False, stoppable=True: None
        ak.busy_end = lambda owner: None

    @classmethod
    def tearDownClass(cls):
        for name, value in cls.real.items():
            setattr(cls.ak, name, value)
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
        sys._freelab_family_audit_last = None  # (a window shows the session's last audit again: none here)

    def tearDown(self):
        for name, value in self.real.items():
            setattr(self.ak, name, value)
        self.fakes()
        sys._freelab_family_audit_last = None

    def dialog(self, fonts, own=None):
        self.workspace.packages = lambda: list(fonts)
        self.workspace.currentPackage = own
        real = self.ak.window_font
        self.ak.window_font = lambda owner, workspace=None: own
        self.addCleanup(setattr, self.ak, "window_font", real)
        made = []
        init = FakeLayout.__init__

        def keep(layout, *args, **kwargs):
            init(layout)
            made.append(layout)
        FakeLayout.__init__ = keep
        self.addCleanup(setattr, FakeLayout, "__init__", init)
        self.ak.window_layout = lambda dialog, scroll=None: FakeLayout()
        dialog = fa.FamilyAuditDialog()
        if dialog.failed is not None:
            raise dialog.failed
        self.said = []
        dialog.log.add = lambda text, level="info": self.said.append((level, text))
        dialog.window = made[0]
        return dialog

    def test_the_rows_in_order(self):
        dialog = self.dialog([])
        window = dialog.window
        self.assertIs(window.items[0], dialog.font_label, "the top line first (the tools' buttons join its row)")
        self.assertIs(window.items[1], dialog.status_line, "the shown tab's status under it")
        self.assertEqual(window.items[2], "header line")
        options = window.items[3]
        self.assertEqual(options.items, [dialog.add_button, options.items[1], dialog.reference_box,
                                         dialog.compare_button, None], "Compare at the end of the options it reads")
        self.assertEqual(options.items[1].text, u"Reference:", "label form: a noun and a colon")
        self.assertIs(window.items[4], dialog.splitter)
        self.assertIs(window.items[-2], dialog.log.widget)
        bottom = window.items[-1]
        self.assertEqual(bottom.items, [dialog.tick_all, dialog.tick_none, dialog.glyph_window_button, None,
                                        dialog.assemble_button, dialog.cancel_button, dialog.close_button])
        self.assertEqual(dialog.add_button.text, u"Add files\N{HORIZONTAL ELLIPSIS}")

    def test_the_lower_part_starts_with_its_line_under_the_handle(self):
        made = []
        real = self.ak.separator
        self.ak.separator = lambda header=False, vertical=False: made.append("line") or "line"
        self.addCleanup(setattr, self.ak, "separator", real)
        dialog = self.dialog([])
        self.assertEqual(len(dialog.splitter.widgets), 2, "the sources over the results")
        self.assertEqual(made, ["line"])
        self.assertEqual(dialog.tabs.texts, list(fa.TAB_TITLES))

    def test_no_font_says_so_and_add_files_stays_usable(self):
        dialog = self.dialog([])
        self.assertEqual(dialog.font_label.text, fa.NO_FONT_LINE)
        self.assertTrue(dialog.add_button.props.get(self.ak.WITHOUT_FONT_PROP), "usable without a font")
        self.assertFalse(dialog.compare_button.enabled)
        self.assertFalse(dialog.assemble_button.enabled)
        self.assertEqual(dialog.reference_box.texts, [u"n/a"], "a dropdown empty with no font says n/a")
        self.assertFalse(dialog.has_font())

    def test_the_family_ticked_the_reference_nearest_regular(self):
        bold = FakeFont(2, u"Sans", u"Bold", weight=700, path=u"/f/Sans-Bold.otf")
        regular = FakeFont(1, u"Sans", u"Regular", path=u"/f/Sans-Regular.vfc")
        other = FakeFont(3, u"Serif", u"Regular")
        dialog = self.dialog([bold, regular, other], own=bold)
        self.assertEqual([e.label for e in dialog.entries], [u"Bold", u"Regular (Sans)", u"Regular (Serif)"])
        self.assertEqual(dialog.ticked, set([(2, u"Bold"), (1, u"Regular")]))
        self.assertEqual(dialog.reference, (1, u"Regular"))
        self.assertEqual(dialog.reference_box.texts, [u"Bold", u"Regular (Sans)"])
        self.assertEqual(dialog.reference_box.currentIndex, 1)
        self.assertEqual(dialog.font_label.text,
                         u"<b>Sans</b>: <b>2 of 3 sources</b> ticked (reference <b>Regular (Sans)</b>).")
        self.assertEqual(dialog.status_line.text, u"Click <i>Compare</i> to compare the ticked sources.")
        self.assertTrue(dialog.compare_button.enabled)
        self.assertFalse(dialog.assemble_button.enabled, "nothing audited yet")
        self.assertEqual([e.format for e in dialog.entries], [u"OTF", u"VFC", u"unsaved"])

    def test_a_font_of_several_masters_gives_a_source_each(self):
        font = FakeFont(4, u"Sans VF", u"Regular", masters=[u"Light", u"Regular", u"Black"])
        dialog = self.dialog([font], own=font)
        self.assertEqual([e.label for e in dialog.entries], [u"Light", u"Regular", u"Black"])
        self.assertEqual(len(dialog.ticked), 3)
        self.assertEqual(dialog.reference, (4, u"Regular"))

    def test_a_tick_changes_the_reference_and_the_line(self):
        bold = FakeFont(2, u"Sans", u"Bold", weight=700)
        regular = FakeFont(1, u"Sans", u"Regular")
        dialog = self.dialog([bold, regular], own=bold)
        dialog.set_tick((1, u"Regular"), False)
        self.assertEqual(dialog.reference, (2, u"Bold"), "the reference unticked: the next nearest")
        self.assertFalse(dialog.compare_button.enabled, "one source: nothing to compare")
        self.assertEqual(dialog.status_line.text, u"Tick at least two sources, then click <i>Compare</i>.")
        dialog.tick_every(True)
        self.assertEqual(len(dialog.ticked), 2)
        self.assertEqual(dialog.reference, (2, u"Bold"), "kept while ticked")
        dialog.tick_every(False)
        self.assertEqual(dialog.reference_box.texts, [u"n/a"])

    def test_compare_fills_the_tabs_and_assemble_waits_for_it(self):
        bold = FakeFont(2, u"Sans", u"Bold", weight=700)
        regular = FakeFont(1, u"Sans", u"Regular")
        dialog = self.dialog([bold, regular], own=bold)
        read = {(1, u"Regular"): source(u"Regular", [(u"A", [0x41]), (u"B", [0x42])],
                                        {u"A": shape(square()), u"B": shape(square())}, key=(1, u"Regular"),
                                        kerning=kerning(), features=[]),
                (2, u"Bold"): source(u"Bold", [(u"A", [0x41])], {u"A": shape(square(), square())}, key=(2, u"Bold"),
                                     kerning=kerning(), features=[])}
        real = fa.read_source
        fa.read_source = lambda calls, entry, shapes=True, progress=None: read[entry.key]
        self.addCleanup(setattr, fa, "read_source", real)
        dialog.compare()
        self.assertIsNotNone(dialog.audit)
        self.assertEqual(dialog.tabs.texts[:2], [u"Glyph sets (1)", u"Compatibility (1)"])
        self.assertTrue(dialog.assemble_button.enabled)
        self.assertEqual(dialog.assemble_button.text, u"Assemble 2 sources as masters")
        self.assertEqual(dialog.status_line.text, u"<b>1 of 2 glyphs</b> is missing from some sources.")
        self.assertEqual(self.said[-1][0], "done")
        dialog.set_tick((2, u"Bold"), False)
        self.assertFalse(dialog.assemble_button.enabled, "the ticks changed: compare again first")
        self.assertIn(u"click <i>Compare</i> to compare again", dialog.status_line.text)

    def compared(self):
        bold = FakeFont(2, u"Sans", u"Bold", weight=700)
        regular = FakeFont(1, u"Sans", u"Regular")
        dialog = self.dialog([bold, regular], own=bold)
        read = {(1, u"Regular"): source(u"Regular", [(u"A", [0x41])], {u"A": shape(square())}, key=(1, u"Regular"),
                                        info={"weight_class": 400}, kerning=kerning(), features=[]),
                (2, u"Bold"): source(u"Bold", [(u"A", [0x41])], {u"A": shape(square())}, key=(2, u"Bold"),
                                     info={"weight_class": 700}, kerning=kerning(), features=[])}
        read[(1, u"Regular")].package = SourcePackage({(u"A", u"Regular"): SourceLayer(u"Regular", 600)})
        read[(2, u"Bold")].package = SourcePackage({(u"A", u"Bold"): SourceLayer(u"Bold", 640)})
        real = fa.read_source
        fa.read_source = lambda calls, entry, shapes=True, progress=None: read[entry.key]
        self.addCleanup(setattr, fa, "read_source", real)
        dialog.compare()
        return dialog

    def test_a_window_opened_again_shows_the_last_audit_while_no_source_changed(self):
        # (owner's image 330: Family Audit opened again showed nothing of the comparison made before)
        first = self.compared()
        fonts = list(self.workspace.packages())
        own = self.workspace.currentPackage
        again = self.dialog(fonts, own=own)
        self.assertIs(again.audit, first.audit, "the last audit, not read again")
        self.assertEqual(again.ticked, set([(1, u"Regular"), (2, u"Bold")]))
        self.assertFalse(again.stale())
        self.assertEqual(again.tabs.texts[:3], [u"Glyph sets (alike)", u"Compatibility (alike)", u"Metrics and info (1)"])
        # a source edited since (its History moved): nothing shown
        real = self.ak.history_mark
        self.ak.history_mark = lambda package: ("moved", id(package))
        self.addCleanup(setattr, self.ak, "history_mark", real)
        moved = self.dialog(fonts, own=own)
        self.assertIsNone(moved.audit)
        self.assertEqual(moved.tabs.texts, list(fa.TAB_TITLES))

    def test_an_edit_in_a_source_puts_the_audit_out_of_date(self):
        dialog = self.compared()
        self.assertEqual(len(dialog.watches), 2, "each audited font's History watched")
        dialog.source_moved(dialog.watches[0])
        dialog.source_moved(dialog.watches[1])
        warnings = [text for level, text in self.said if level == "warning"]
        self.assertEqual(len(warnings), 1, "said once")
        self.assertIn(u"A source changed since: click <i>Compare</i> to compare again.", dialog.status_line.text)
        self.assertTrue(dialog.assemble_button.enabled, "Assemble reads the sources afresh")
        dialog.compare()
        self.assertFalse(dialog.moved)

    def test_assemble_makes_a_new_font_and_says_what_it_holds(self):
        dialog = self.compared()
        calls = dialog.calls = FakeCalls()
        busy = []
        self.ak.busy_start = lambda owner, what=u"", stoppable=True: busy.append(stoppable)
        dialog.assemble()
        self.assertEqual(busy, [False], "never stopped half way")
        self.assertFalse(dialog.busy)
        self.assertEqual(calls.package.masters, [u"Regular", u"Bold"])
        self.assertEqual(calls.package.glyphs[u"A"].layers[u"Bold"].width, 640)
        self.assertIs(dialog.made_fonts[-1], calls.package, "held for the session")
        done = [text for level, text in self.said if level == "done"]
        self.assertTrue(done[-1].startswith(u"Made a new font with <b>2 masters</b> (Regular and Bold)"), done)
        self.assertIn(("info", u"Axes: Weight (Regular 400, Bold 700)."), self.said)

    def test_cancel_is_usable_while_it_compares_not_while_it_assembles(self):
        """The owner, 2026-11-24: a Cancel left of Close (test_the_rows_in_order), grayed but while work that can
        stop runs (ak.cancel_button), as Esc stops it; its help says what a stop leaves."""
        import qtfakes
        dialog = self.compared()
        self.assertFalse(dialog.cancel_button.enabled, "grayed while nothing runs")
        self.assertEqual(dialog.cancel_button.whats, self.ak.CANCEL_HELP + u" A comparison stopped changes no font: the "
                                                                           u"tabs show the one before it.")
        seen = qtfakes.follow_cancel(self, self.ak)
        audit = dialog.audit

        def stopping(owner, what=None, part=None, force=False, stoppable=True):
            if stoppable:
                raise self.ak.Stopped()  # (as a click on Cancel makes it)
        self.ak.busy_progress = stopping
        dialog.compare()
        self.assertEqual(seen, [(fa.READ_STEP, True, True), (None, None, False)], "usable while it compares")
        self.assertEqual(self.said[-1], ("warning", u"The comparison was stopped: the tabs show the one before it."))
        self.assertIs(dialog.audit, audit)
        del seen[:]
        dialog.calls = FakeCalls()
        dialog.assemble()
        self.assertEqual(seen, [(fa.READ_STEP, False, False), (None, None, False)], "grayed while it assembles")
        self.assertIs(dialog.made_fonts[-1], dialog.calls.package, "made whole, whatever was clicked")

    def test_an_unfinished_font_is_said_never_closed(self):
        dialog = self.compared()
        dialog.calls = FakeCalls(keep_masters=False)
        dialog.assemble()
        level, text = self.said[-1]
        self.assertEqual(level, "error")
        self.assertIn(u"The new font was left unfinished", text)
        self.assertIn(u"Close it without saving", text)
        self.assertIs(dialog.made_fonts[-1], dialog.calls.package)

    def test_files_added_are_ticked_once_fontlab_has_them(self):
        regular = FakeFont(1, u"Sans", u"Regular", path=u"/f/Sans-Regular.vfc")
        fonts = [regular]
        dialog = self.dialog(fonts, own=regular)
        asked = []
        dialog.calls.request_font = asked.append
        dialog.start_open_timer = lambda: None
        dialog.open_paths([u"/f/Sans-Regular.vfc", u"/f/Serif-Bold.otf"])
        self.assertEqual(asked, [u"/f/Serif-Bold.otf"], "a file open already is not opened again")
        self.assertIn(("info", u"<i>Sans-Regular.vfc</i> is open already: ticked."), self.said)
        self.assertEqual(dialog.pending, [u"/f/Serif-Bold.otf"])
        fonts.append(FakeFont(9, u"Serif", u"Bold", weight=700, path=u"\\f\\Serif-Bold.otf"))
        dialog.open_tick()
        self.assertEqual(dialog.pending, [])
        # (owner's image 344: a font of another family was ticked with the window's family's)
        self.assertNotIn((9, u"Bold"), dialog.ticked, "another family: left unticked, and said")
        self.assertEqual(self.said[-1][0], "warning")
        self.assertIn(u"of another family (Serif): left unticked", self.said[-1][1])
        asked[:] = []
        dialog.open_paths([u"/f/Sans-Bold.otf"])
        fonts.append(FakeFont(10, u"Sans", u"Bold", weight=700, path=u"/f/Sans-Bold.otf"))
        dialog.open_tick()
        self.assertIn((10, u"Bold"), dialog.ticked, "the window's family: ticked")
        self.assertEqual(self.said[-1], ("done", u"Opened <i>Sans-Bold.otf</i> in FontLab: ticked as <b>Bold (Sans)</b>."))

    def test_a_file_fontlab_crashes_on_is_asked_about_first(self):
        """FontLab 7.2 crashes on a font whose GPOS holds a single adjustment of format 2 with no values (Noto Sans
        JP): such a file is opened as a fixed copy, or skipped, as the one question asked first is answered."""
        import fontbytes
        folder = tempfile.mkdtemp(prefix="freelab-audit-crash-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, u"Sans-Black.ttf")
        with open(path, "wb") as handle:
            handle.write(fontbytes.sfnt({b"head": fontbytes.head(), b"GPOS": fontbytes.gpos(
                [fontbytes.lookup(1, [fontbytes.single(2, 0, 0)])])}))
        for name in ("ask_open_fixed", "safe_copies_folder"):
            self.addCleanup(setattr, self.ak, name, getattr(self.ak, name))
        self.ak.safe_copies_folder = lambda: os.path.join(folder, "copies")
        regular = FakeFont(1, u"Sans", u"Regular", path=u"/f/Sans-Regular.vfc")
        fonts = [regular]
        dialog = self.dialog(fonts, own=regular)
        asked, questions = [], []
        dialog.calls.request_font = asked.append
        dialog.start_open_timer = lambda: None
        self.ak.ask_open_fixed = lambda parent, crashers: questions.append([p for p, s in crashers]) and False
        dialog.open_paths([path, u"/f/Sans-Bold.otf"])
        self.assertEqual((questions, asked), ([[path]], [u"/f/Sans-Bold.otf"]), "skipped: not opened")
        self.assertIn(u"<i>Sans-Black.ttf</i> skipped: FontLab 7.2 crashes on it", self.said[0][1])
        self.ak.ask_open_fixed = lambda parent, crashers: True
        del self.said[:]
        dialog.open_paths([path])
        copy = asked[-1]
        self.assertEqual((os.path.basename(copy), os.path.dirname(os.path.dirname(copy))),
                         (u"Sans-Black.ttf", os.path.join(folder, "copies")), "its fixed copy opened")
        self.assertEqual(dialog.pending, [u"/f/Sans-Bold.otf", copy])
        self.assertIn(u"a fixed copy is opened instead", self.said[0][1])
        self.assertEqual(self.said[-1], ("info", u"Opening <i>Sans-Black.ttf</i> in FontLab\N{HORIZONTAL ELLIPSIS}"))
        # (Codex, 2026-11-19: picked again before it came in, it was asked about, written, and opened again)
        self.ak.ask_open_fixed = lambda parent, crashers: self.fail("its copy is on its way: not asked about")
        os.utime(copy, (1, 1))
        dialog.open_paths([path, u"/f/Sans-Bold.otf"])
        self.assertEqual((asked[-1], dialog.pending), (copy, [u"/f/Sans-Bold.otf", copy]), "asked for once")
        self.assertEqual(os.path.getmtime(copy), 1, "the copy not written again")
        self.assertEqual([text for level, text in self.said[-2:]],
                         [u"<i>Sans-Bold.otf</i> is being opened already: ticked once it is in.",
                          u"<i>Sans-Black.ttf</i> is being opened already: ticked once it is in."])
        fonts.append(FakeFont(11, u"Sans", u"Black", weight=900, path=copy))
        dialog.open_tick()
        self.assertIn((11, u"Black"), dialog.ticked, "the copy's font ticked once it is in")
        del asked[:]
        dialog.open_paths([path])
        self.assertEqual(asked, [], "its copy open already: ticked, not opened again")
        self.assertIn(u"is open already: ticked", self.said[-1][1])


class TextReviewTests(unittest.TestCase):
    """The interface-text review of November 24: Assemble's help says each thing once, plainly."""

    def test_assembles_help_and_the_window_help(self):
        with io.open(os.path.join(os.path.dirname(os.path.abspath(fa.__file__)), "freelab_family_audit.py"),
                     encoding="utf-8") as handle:
            source = handle.read()
        assemble = source.split(u"self.assemble_button.setWhatsThis(")[1].split(u")\n")[0]
        self.assertIn(u"Makes a new font", assemble)
        self.assertNotIn(u"NEW", assemble)
        self.assertNotIn(u"promise", assemble, "said by the Compatibility list and the log")
        self.assertEqual(assemble.count(u"without saving"), 1)
        self.assertNotIn(u"not saved", assemble)
        self.assertIn(u"each master's kerning and line metrics", fa.HELP, "as Assemble copies them (MASTER_METRICS)")
        self.assertTrue(fa.MASTER_METRICS)
        # (the review of 2026-11-24: a font of another family is opened unticked, and both helps say so)
        self.assertIn(u"another family is left unticked", u" ".join(fa.HELP.split()))
        add = source.split(u"self.add_button.setWhatsThis(")[1].split(u")\n")[0]
        self.assertIn(u"a font of another family is left unticked", add)
        self.assertIn(u"of another family (%s): left unticked", source)


if __name__ == "__main__":
    unittest.main()
