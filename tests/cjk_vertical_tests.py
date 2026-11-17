# -*- coding: utf-8 -*-
"""Tests of FreeLab's CJK Vertical (vertical forms, vpal, and vertical metrics). Valid Python 2.7 and
Python 3."""

from __future__ import absolute_import, division, print_function

import io
import json
import os
import re
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "cjk"))
sys.path.insert(0, HERE)
import freelab_cjk_spacing  # noqa: E402,F401  (CJK Vertical reads its kinds of glyph and samples)
import freelab_cjk_vertical as cv  # noqa: E402

MODEL = {"format": 1, "vert": {
    "U+300C": {"fonts": 100, "agree": 0.9, "how": "rotated", "move": [0.0, 0.0]},
    "U+3041": {"fonts": 90, "agree": 0.8, "how": "moved", "move": [0.1, 0.1]},
    "U+3001": {"fonts": 90, "agree": 0.8, "how": "moved", "move": [0.6, 0.6]},
    "U+FF5E": {"fonts": 70, "agree": 0.9, "how": "rotated flipped", "move": [0.0, 0.0]},
    "U+3349": {"fonts": 60, "agree": 0.9, "how": "redrawn"},
    "U+30FC": {"fonts": 2, "agree": 1.0, "how": "rotated", "move": [0.0, 0.0]},
    "U+300D": {"fonts": 100, "agree": 0.4, "how": "rotated", "move": [0.0, 0.0]}},
    "vpal": {"hiragana": [0.07, 0.07], "U+3001": [0.07, 0.17], "punctuation": [0.08, 0.07]},
    "metrics": {"advance_height": 1.0, "vhea_ascent": 0.5, "vhea_descent": -0.5, "vhea_line_gap": 0.0}}
BRACKET = (0x300C, "uni300C", 1000.0, (654.0, 110.0, 944.0, 835.0))  # IBM Plex Sans JP's, live


def rounded(values):
    return tuple(int(round(v)) for v in values)


class TopRow(object):
    """ak's top-row progress as a fake Ak's members (busy_start, busy_progress, busy_end, busy_stopping,
    Stopped, BUSY_NAME), each call recorded: ("start", what, stoppable), ("progress", what, part, stoppable),
    ("end",). on_progress(), where set, runs at each busy_start or busy_progress (as events let through);
    stop_after: busy_progress raises Stopped past that many calls, where stoppable (the user's Esc)."""

    def __init__(self, stop_after=None):
        self.calls, self.on_progress, self.stop_after = [], None, stop_after

        class Stopped(Exception):
            pass
        self.Stopped = Stopped

    def members(self):
        top = self

        def start(owner, what=u"", stoppable=True):
            top.calls.append(("start", what, stoppable))
            if top.on_progress is not None:
                top.on_progress()

        def progress(owner, what=None, part=None, force=False, stoppable=True):
            top.calls.append(("progress", what, part, stoppable))
            if top.on_progress is not None:
                top.on_progress()
            if top.stop_after is not None and stoppable and sum(1 for c in top.calls if c[0] == "progress") > top.stop_after:
                raise top.Stopped()

        return dict(busy_start=staticmethod(start), busy_progress=staticmethod(progress),
                    busy_end=staticmethod(lambda owner: top.calls.append(("end",))),
                    busy_stopping=staticmethod(lambda owner: False), Stopped=self.Stopped, BUSY_NAME="freelabBusy",
                    BUSY_RANGE=1000)

    def kinds(self):
        return [call[0] for call in self.calls]

    def last(self, kind="progress"):
        return [call for call in self.calls if call[0] == kind][-1]


class GeometryTests(unittest.TestCase):
    def test_a_quarter_turn_about_the_ems_center(self):
        """Live (IBM Plex Sans JP, 2026-11-14): this transform on a component of uni300C gave a box of
        230 to 955 across and -64 to 226 up; the source 654 to 944, 110 to 835."""
        matrix = cv.form_matrix("rotated", (0, 0), 1000.0, 880.0, 1000.0)
        self.assertEqual(rounded(matrix), (0, -1, 1, 0, 120, 880))
        self.assertEqual(rounded(cv.mapped_box(matrix, BRACKET[3])), (230, -64, 955, 226))

    def test_the_other_turns_and_a_move(self):
        flipped = cv.form_matrix("rotated flipped", (0, 0), 1000.0, 880.0, 1000.0)
        self.assertEqual(rounded(cv.mapped_point(flipped, 654, 110)), (770, 226), "turned, then mirrored across")
        ccw = cv.form_matrix("rotated ccw", (0, 0), 1000.0, 880.0, 1000.0)
        self.assertEqual(rounded(cv.mapped_point(ccw, 500, 380)), (500, 380), "the center stays")
        self.assertEqual(rounded(cv.mapped_point(ccw, 1000, 380)), (500, 880), "the right edge goes up")
        moved = cv.form_matrix("moved", (100, 105), 1000.0, 880.0, 1000.0)
        self.assertEqual(rounded(moved), (1, 0, 0, 1, 100, 105))
        turned_moved = cv.form_matrix("rotated", (10, -20), 1000.0, 880.0, 1000.0)
        self.assertEqual(rounded(turned_moved)[4:], (130, 860))

    def test_a_moved_form_goes_to_the_corpus_place(self):
        entry = {"how": "moved", "move": [0.1, 0.1], "place": [0.62, 0.48]}
        matrix = cv.placed_matrix("moved", entry, 1000.0, (200.0, -50.0, 800.0, 550.0), 880.0, 1000.0, 1000.0)
        self.assertEqual(rounded(matrix), (1, 0, 0, 1, 120, 110), "its ink's center to 620 across, 360 up")
        no_place = cv.placed_matrix("moved", {"move": [0.1, 0.1]}, 1000.0, (200.0, -50.0, 800.0, 550.0), 880.0,
                                    1000.0, 1000.0)
        self.assertEqual(rounded(no_place)[4:], (100, 100), "an older model: the median move")
        turned = cv.placed_matrix("rotated", entry, 1000.0, BRACKET[3], 880.0, 1000.0, 1000.0)
        self.assertEqual(rounded(turned)[4:], (220, 980), "a turned form keeps the move: its design's place")

    def test_a_raised_glyph_goes_up_on_screen(self):
        """Review: the previews drew vpal's positive (upward) y placement downward."""
        plain = cv.baseline_y(2.0, 880.0, 0, 0.04)
        self.assertAlmostEqual(plain, 2.0 + 880 * 0.04)
        self.assertLess(cv.baseline_y(2.0, 880.0, 100, 0.04), plain, "placed up: drawn higher (smaller y)")
        self.assertGreater(cv.baseline_y(2.0, 880.0, -100, 0.04), plain)

    def test_composed_transforms(self):
        """A glyph that is one component: the form points to its glyph, the transforms combined."""
        inner = (1.0, 0.0, 0.0, 1.0, 30.0, 0.0)
        outer = cv.form_matrix("rotated", (0, 0), 1000.0, 880.0, 1000.0)
        both = cv.compose(outer, inner)
        self.assertEqual(rounded(cv.mapped_point(both, 654, 110)),
                         rounded(cv.mapped_point(outer, *cv.mapped_point(inner, 654, 110))))


class OwnCodeTests(unittest.TestCase):
    def test_single_substitutions_and_classes(self):
        text = u"""feature vert {
  @V1 = [uni3041 uni3043];
  @V2 = [uni3041.vert uni3043.vert];
  sub @V1 by @V2;
  sub [uni300C uni300D] by [uniFE41 uniFE42];
  sub uni3001 by uniFE11; # comma
  sub @FONT by @FONTV;
  sub f i by f_i;
  sub a' b by c;
# >>> FreeLab vert (made by FreeLab CJK Vertical)
  sub uni30FC by uni30FC.vert;
# <<< FreeLab vert
} vert;"""
        found = cv.own_substitutions("vert", text, {u"@FONT": [u"uni3002"], u"@FONTV": [u"uniFE12"]})
        self.assertEqual(found, {u"uni3041": u"uni3041.vert", u"uni3043": u"uni3043.vert", u"uni300C": u"uniFE41",
                                 u"uni300D": u"uniFE42", u"uni3001": u"uniFE11", u"uni3002": u"uniFE12"},
                         "a ligature, a contextual rule, and FreeLab's block are not the font's vertical forms")

    def test_single_positions_with_the_fonts_classes(self):
        """IBM Plex Sans JP's vpal positions a class FontLab keeps among the font's classes (live)."""
        text = u"""feature vpal {
  pos uniFF65.rotat <0 250 0 -1000>;
  pos @vpal <0 0 0 -500>;
  enum pos [uniFF65 uni30FB] <0 250 0 -500>;
  pos uni3044 uniFE11 <0 0 0 -20>;
  pos a' <0 10 0 0> b;
# >>> FreeLab vpal (made by FreeLab CJK Vertical)
  pos uni3042 <0 -2 0 -13>;
# <<< FreeLab vpal
} vpal;"""
        found = cv.own_positions("vpal", text, {u"@vpal": [u"uniFF0C", u"uniFF0E"]})
        self.assertEqual(sorted(found), [u"uni30FB", u"uniFF0C", u"uniFF0E", u"uniFF65", u"uniFF65.rotat"],
                         "pairs, contextual rules, and FreeLab's block are not the font's single values")

    def test_many_glyphs_by_one_lookup_lines_and_the_prefixs_lookups(self):
        """Review: sub [a b] by c; a rule on the line of lookup X {; and a lookup the prefix defines."""
        prefix = u"""lookup VERT_PREFIX {
  sub uni3002 by uniFE12;
  pos uni3063.vert <0 5 0 -10>;
} VERT_PREFIX;
"""
        text = u"""feature vert {
  sub [uni2014 uni2015] by uni2015.vert;
  lookup INLINE { sub uni300C by uniFE41;
    sub uni300D by uniFE42;
  } INLINE;
  lookup VERT_PREFIX;
} vert;"""
        lookups = cv.code_lookups(prefix)
        self.assertEqual(sorted(lookups), [u"VERT_PREFIX"])
        found = cv.own_substitutions("vert", text, {}, lookups)
        self.assertEqual(found, {u"uni2014": u"uni2015.vert", u"uni2015": u"uni2015.vert", u"uni300C": u"uniFE41",
                                 u"uni300D": u"uniFE42", u"uni3002": u"uniFE12"})
        vpal = u"""feature vpal {
  lookup VERT_PREFIX;
  lookup V2 { pos uni3041.vert <0 3 0 -6>;
  } V2;
} vpal;"""
        self.assertEqual(sorted(cv.own_positions("vpal", vpal, {}, lookups)), [u"uni3041.vert", u"uni3063.vert"])

    def test_a_class_given_one_number_is_a_single_value(self):
        """Live pass: IBM Plex Sans JP's palt reads "pos @palt -500;" (a number alone: the advance along the
        feature's direction), its class in the prefix; CJK Spacing missed it. In vpal, the same reader:
        no vpal rule for its glyphs, and the pair reader does not take it for a pair of @vpal and "-50"."""
        prefix = u"@vpal = [uni3001 uni3002];\n"
        vpal = u"feature vpal {\n  pos @vpal -500;\n  pos uni3044 uniFE11 -20;\n} vpal;\n"
        classes = cv.code_classes(prefix)
        self.assertEqual(sorted(cv.own_positions("vpal", vpal, classes)), [u"uni3001", u"uni3002"])
        self.assertEqual(cv.own_position_values("vpal", vpal, classes), {u"uni3001": (0, -500), u"uni3002": (0, -500)})
        self.assertEqual(cv.own_pairs("vpal", vpal, classes), set([(u"uni3044", u"uniFE11")]))
        trims = [type("T", (), {"shown": name, "value": (10, -20), "checked": True})() for name in (u"uni3001", u"uni3042")]
        self.assertEqual(cv.vpal_rules(trims, cv.own_positions("vpal", vpal, classes)), [u"pos uni3042 <0 10 0 -20>;"])

    def test_ranges_in_classes(self):
        text = u"feature vert {\n  sub [cid00010-cid00011] by [cid00020-cid00021];\n} vert;"
        self.assertEqual(cv.own_substitutions("vert", text), {u"cid00010": u"cid00020", u"cid00011": u"cid00021"})


class PlanTests(unittest.TestCase):
    GLYPHS = [BRACKET, (0x300D, "uni300D", 1000.0, (56.0, -75.0, 346.0, 650.0)),
              (0x3041, "uni3041", 1000.0, (172.0, -51.0, 833.0, 643.0)),
              (0x3001, "uni3001", 1000.0, (49.0, -71.0, 312.0, 206.0)),
              (0xFE11, "uniFE11", 1000.0, (650.0, 600.0, 900.0, 860.0)),
              (0xFF5E, "uniFF5E", 1000.0, (46.0, 264.0, 954.0, 496.0)),
              (0x3349, "uni3349", 1000.0, (10.0, -100.0, 990.0, 850.0)),
              (0x30FC, "uni30FC", 1000.0, (100.0, 342.0, 900.0, 418.0))]

    def plan(self, names=(), own=None):
        all_names = [g[1] for g in self.GLYPHS] + list(names)
        return dict((f.name, f) for f in cv.plan_forms(self.GLYPHS, all_names, MODEL, 1000.0, 880.0, 1000.0, own))

    def test_a_bare_font_gets_its_forms_built(self):
        forms = self.plan()
        self.assertEqual(forms["uni300C"].state, "build")
        self.assertEqual(forms["uni300C"].target, "uni300C.vert")
        self.assertEqual(rounded(forms["uni300C"].matrix), (0, -1, 1, 0, 120, 880))
        self.assertEqual(forms["uni3041"].state, "build")
        self.assertEqual(rounded(forms["uni3041"].matrix), (1, 0, 0, 1, 100, 100), "moved by the corpus's median")
        self.assertEqual(forms["uni3041"].section(), "moved")
        self.assertEqual(forms["uniFF5E"].how, "rotated flipped")
        self.assertNotIn("uni3349", forms, "redrawn in the corpus: drawn by hand, not built")
        self.assertNotIn("uni30FC", forms, "too few fonts give it a form")
        self.assertNotIn("uni300D", forms, "the fonts do not agree on how")

    def test_the_fonts_presentation_form_and_vert_glyph_are_used(self):
        forms = self.plan(names=["uni3041.vert"])
        self.assertEqual((forms["uni3001"].state, forms["uni3001"].target), ("glyph", "uniFE11"),
                         "U+FE11, the vertical ideographic comma, is drawn")
        self.assertEqual((forms["uni3041"].state, forms["uni3041"].target), ("glyph", "uni3041.vert"))
        self.assertTrue(forms["uni3041"].checked)
        self.assertEqual(cv.form_rules([forms["uni3041"]]), [u"sub uni3041 by uni3041.vert;"])

    def test_the_fonts_own_code_is_left_alone(self):
        forms = self.plan(own={"uni300C": "uniFE41"})
        self.assertEqual(forms["uni300C"].state, "font")
        self.assertFalse(forms["uni300C"].checked)
        self.assertEqual(forms["uni300C"].target, "uniFE41")
        rules = cv.form_rules(forms.values())
        self.assertFalse(any("uni300C " in rule for rule in rules), "no second rule for a glyph the font substitutes")
        self.assertIn(u"sub uni3041 by uni3041.vert;", rules)

    def test_forms_freelab_wrote_before_are_listed_as_its_own(self):
        """Live, IBM Plex Sans JP: after a write, the forms built were listed as drawn but not in the code."""
        text = (u"feature vert {\n" + cv.BEGIN % "vert" + u"\n  sub uni300C by uni300C.vert;\n" + cv.END % "vert" +
                u"\n} vert;\n")
        ours = cv.freelab_substitutions("vert", text)
        self.assertEqual(ours, {u"uni300C": u"uni300C.vert"})
        self.assertEqual(cv.own_substitutions("vert", text), {}, "not the font's own")
        forms = self.plan(names=["uni300C.vert"])
        self.assertEqual(forms["uni300C"].section(), "glyph")
        glyphs = self.GLYPHS + [(0x253C, "uni253C", 1000.0, (0.0, 0.0, 1000.0, 800.0))]
        model = dict(MODEL, vert=dict(MODEL["vert"], **{"U+253C": {"fonts": 60, "agree": 0.9, "how": "rotated",
                                                                  "move": [0.0, 0.0]}}))
        planned = dict((f.name, f) for f in cv.plan_forms(
            glyphs, [g[1] for g in glyphs] + ["uni300C.vert", "uni253C.vert"], model, 1000.0, 880.0, 1000.0, {},
            {u"uni300C": u"uni300C.vert", u"uni253C": u"uni253C.vert"}))
        self.assertEqual((planned["uni300C"].section(), planned["uni300C"].checked), ("ours", True))
        self.assertEqual((planned["uni253C"].section(), planned["uni253C"].checked), ("ours", True),
                         "written before: checked, even outside the forms checked at first")
        self.assertIn(u"sub uni300C by uni300C.vert;", cv.form_rules(planned.values()), "written again")

    def test_an_empty_glyph_gets_no_form(self):
        glyphs = [(0x300C, "uni300C", 1000.0, None)]
        self.assertEqual(cv.plan_forms(glyphs, ["uni300C"], MODEL, 1000.0, 880.0), [])

    def test_a_form_most_fonts_with_the_character_do_without_is_not_built(self):
        """Live, IBM Plex Sans JP: its centered full-width ! was to be moved right, as the 23 fonts that give
        it a form do; most of those that have it give it none."""
        model = dict(MODEL, vert=dict(MODEL["vert"], **{"U+FF01": {"fonts": 23, "agree": 0.83, "exact": 0.65,
                                                                  "share": 0.22, "how": "moved", "move": [0.2, 0.0]}}))
        glyphs = [(0xFF01, "uniFF01", 1000.0, (439.0, -10.0, 561.0, 735.0))]
        self.assertEqual(cv.plan_forms(glyphs, ["uniFF01"], model, 1000.0, 880.0), [])

    def test_forms_the_fonts_lay_out_anew_are_not_built(self):
        """The squared words (U+3314 ㌔): every font's vertical form is its own layout, of the glyph's size."""
        model = dict(MODEL, vert=dict(MODEL["vert"], **{"U+3314": {"fonts": 66, "agree": 1.0, "exact": 0.0,
                                                                  "how": "moved", "move": [0.03, 0.0]}}))
        glyphs = [(0x3314, "uni3314", 1000.0, (40.0, -80.0, 960.0, 840.0))]
        self.assertEqual(cv.plan_forms(glyphs, ["uni3314"], model, 1000.0, 880.0), [])

    def test_forms_outside_cjk_punctuation_and_kana_start_unchecked(self):
        """Live, IBM Plex Sans JP: the corpus's fonts give full-width box drawing and Greek forms too;
        they are listed, unchecked, under their own heading."""
        model = dict(MODEL, vert=dict(MODEL["vert"], **{"U+253C": {"fonts": 60, "agree": 0.8, "how": "rotated",
                                                                  "move": [0.0, 0.0]}}),
                     orientation={"U+253C": "R", "U+300C": "Tr"})
        glyphs = [(0x253C, "uni253C", 1000.0, (0.0, -120.0, 1000.0, 880.0)), BRACKET]
        forms = dict((f.name, f) for f in cv.plan_forms(glyphs, [g[1] for g in glyphs], model, 1000.0, 880.0))
        self.assertEqual((forms["uni253C"].checked, forms["uni253C"].section()), (False, "other"))
        self.assertEqual((forms["uni300C"].checked, forms["uni300C"].section()), (True, "rotated"))
        self.assertTrue(cv.is_core(0x3041) and cv.is_core(0x2015) and cv.is_core(0xFF5E))
        self.assertTrue(cv.is_core(0xFE59, "Tr"), "transformed, as Unicode has it")
        self.assertFalse(cv.is_core(0x0392, "R"))

    def test_upright_characters_and_proportional_glyphs_are_not_built(self):
        """Unicode sets the section sign and full-width Greek upright (U), and an application turns a
        proportional glyph itself: live, IBM Plex Sans JP's proportional Greek were listed to build."""
        model = dict(MODEL, vert=dict(MODEL["vert"], **{"U+00A7": {"fonts": 60, "agree": 0.8, "how": "moved",
                                                                  "move": [0.0, 0.05]},
                                                       "U+0392": {"fonts": 60, "agree": 0.8, "how": "moved",
                                                                  "move": [0.0, 0.05]}}),
                     orientation={"U+00A7": "U", "U+0392": "R", "U+300C": "Tr"})
        glyphs = [(0xA7, "section.full", 1000.0, (100.0, 0.0, 900.0, 800.0)),
                  (0x392, "Beta", 600.0, (80.0, 0.0, 540.0, 700.0)), BRACKET]
        forms = cv.plan_forms(glyphs, [g[1] for g in glyphs], model, 1000.0, 880.0)
        self.assertEqual([f.name for f in forms], ["uni300C"])


class VpalTests(unittest.TestCase):
    def test_the_value_gives_the_corpus_sides(self):
        # a: ink 812 down to -35 under an origin at 880, in an em: now 68 above, 85 below
        value = cv.vpal_value((99, -35, 905, 812), (0.07, 0.07), 880.0, 1000.0, 1000.0)
        self.assertEqual(value, (-2, -13))
        placement, advance = value
        top = 880 - 812 - placement
        bottom = 1000 + advance - (880 - (-35)) + placement
        self.assertEqual((top, bottom), (70, 70))

    def test_plan_reads_the_shown_glyph_and_skips_what_it_should(self):
        shown = [(0x3042, "uni3042", "uni3042", 1000.0, (99, -35, 905, 812)),
                 (0x3001, "uni3001", "uni3001.vert", 1000.0, (650, 589, 913, 866)),
                 (0x3044, "uni3044", "uni3044", 600.0, (50, 0, 550, 700)),
                 (0xAC00, "ga", "ga", 1000.0, (50, -50, 950, 800)),
                 (0x3046, "uni3046", "uni3046", 1000.0, (100, -50, 900, 810))]
        trims = dict((t.name, t) for t in cv.plan_vpal(shown, MODEL, 1000.0, 880.0))
        self.assertIn("uni3042", trims)
        self.assertEqual(trims["uni3001"].shown, "uni3001.vert", "positioned as vertical text sets it")
        self.assertEqual(trims["uni3001"].value, cv.vpal_value((650, 589, 913, 866), (0.07, 0.17), 880.0, 1000.0, 1000.0),
                         "the mark's own sides")
        self.assertNotIn("uni3044", trims, "proportional: turned by applications")
        self.assertNotIn("ga", trims, "Hangul is not trimmed")
        self.assertNotIn("uni3046", trims, "within the tolerance")
        rules = cv.vpal_rules(list(trims.values()), own={"uni3001.vert"})
        self.assertEqual(rules, [u"pos uni3042 <0 -2 0 -13>;"], "the font's own vpal value is kept")


class MetricTests(unittest.TestCase):
    def test_unset_values_are_suggested_set_ones_kept(self):
        metrics = dict((m.key, m) for m in cv.plan_metrics(1000.0, {"openTypeVheaVertTypoAscender": None,
                                                                    "openTypeVheaVertTypoDescender": -440.0},
                                                           12, MODEL))
        self.assertEqual(metrics["advance_height"].value, 1000)
        self.assertTrue(metrics["advance_height"].checked, "12 layers have none")
        self.assertEqual((metrics["vhea_ascent"].value, metrics["vhea_ascent"].checked), (500, True))
        self.assertEqual((metrics["vhea_descent"].value, metrics["vhea_descent"].checked), (-500, False),
                         "the font's own value is kept unless checked")
        self.assertTrue(metrics["vhea_line_gap"].checked, "unset (missing from the info: unset)")
        gap = dict((m.key, m) for m in cv.plan_metrics(1000.0, {}, 0, {"metrics": {"vhea_line_gap": 0.1484}}))
        self.assertEqual(gap["vhea_line_gap"].value, 0, "the owner's choice, 0, not the corpus's median (0.15 em)")
        none = dict((m.key, m) for m in cv.plan_metrics(2048.0, {}, 0, {}))
        self.assertFalse(none["advance_height"].checked, "every layer has one")
        self.assertEqual(none["vhea_ascent"].value, 1024, "half the em without a model")


class CodeTests(unittest.TestCase):
    def forms_and_trims(self):
        forms = [cv.Form(0x300C, "uni300C", "rotated", "uni300C.vert", "build", (0, -1, 1, 0, 120, 880)),
                 cv.Form(0x3001, "uni3001", "moved", "uniFE11", "glyph"),
                 cv.Form(0x3002, "uni3002", "moved", "uniFE12", "font")]
        trims = [cv.VTrim(0x3042, "uni3042", "uni3042", "hiragana", (-2, -15), 68, 85)]
        return forms, trims

    def test_new_features(self):
        forms, trims = self.forms_and_trims()
        texts = cv.texts_for(forms, trims, {})
        for tag in ("vert", "vrt2"):
            self.assertIn(u"feature %s {" % tag, texts[tag])
            self.assertIn(u"  sub uni300C by uni300C.vert;", texts[tag])
            self.assertIn(u"  sub uni3001 by uniFE11;", texts[tag])
            self.assertNotIn(u"uni3002", texts[tag], "the font's own")
        self.assertIn(u"  pos uni3042 <0 -2 0 -15>;", texts["vpal"])
        self.assertEqual(cv.block_of("vpal", texts["vpal"]), u"feature vpal {\n  lookup FreeLab_vpal {\n"
                                                             u"    pos uni3042 <0 -2 0 -15>;\n  } FreeLab_vpal;\n} vpal;\n")

    def test_freelabs_rules_sit_in_a_lookup_of_their_own(self):
        """Live, IBM Plex Sans JP: FreeLab's single pairs after the font's class pairs in one lookup drew
        "Single kern pair occurring after class kern pair in feature 'vkrn'" (shadowed)."""
        old = u"feature vkrn {\n  pos @K @COMMA -40;\n} vkrn;\n"
        kern = cv.VKern(0x3042, "uni3042", 0xFE10, "uniFE10", -20, 7)
        text = cv.texts_for([], [], {"vkrn": old}, kerns=[kern])["vkrn"]
        self.assertLess(text.index(u"pos @K @COMMA -40;"), text.index(u"lookup FreeLab_vkrn {"))
        self.assertIn(u"lookup FreeLab_vkrn {\n    pos uni3042 uniFE10 <0 0 0 -20>;\n  } FreeLab_vkrn;", text)
        try:
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            from fontTools.fontBuilder import FontBuilder
            from fontTools.pens.ttGlyphPen import TTGlyphPen
        except ImportError:
            return
        import warnings
        fb = FontBuilder(1000, isTTF=True)
        names = [".notdef", "uni3042", "uni3044", "uniFE10"]
        fb.setupGlyphOrder(names)
        fb.setupCharacterMap({0x3042: "uni3042", 0x3044: "uni3044", 0xFE10: "uniFE10"})
        fb.setupGlyf(dict((n, TTGlyphPen(None).glyph()) for n in names))
        fb.setupHorizontalMetrics(dict((n, (1000, 0)) for n in names))
        fb.setupHorizontalHeader()
        code = u"@K = [uni3042 uni3044];\n@COMMA = [uniFE10];\n" + text
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            addOpenTypeFeaturesFromString(fb.font, code)
        self.assertEqual([str(w.message) for w in caught if "kern pair" in str(w.message)], [])
        self.assertEqual(len(fb.font["GPOS"].table.LookupList.Lookup), 2, "the font's lookup, then FreeLab's")

    def test_the_fonts_code_is_kept_and_an_old_block_replaced(self):
        forms, trims = self.forms_and_trims()
        old = (u"feature vert {\n#> feature\n  sub uni3002 by uniFE12;\n#< feature\n" + cv.BEGIN % "vert" +
               u"\n  sub old by old.vert;\n" + cv.END % "vert" + u"\n} vert;\n")
        text = cv.texts_for(forms, trims, {"vert": old}, vpal_on=False)["vert"]
        self.assertIn(u"sub uni3002 by uniFE12;", text)
        self.assertIn(u"#/> feature", text, "FontLab's automatic block handed back")
        self.assertNotIn(u"old.vert", text)
        self.assertEqual(text.count(cv.BEGIN % "vert"), 1)
        self.assertLess(text.index(u"uniFE12"), text.index(cv.BEGIN % "vert"), "FreeLab's block before the closing line")

    def test_vrt2_made_by_freelab_carries_the_fonts_own_vert(self):
        """Review: a font with its own vert and no vrt2 got a vrt2 of FreeLab's rules alone, and applications
        that use vrt2 instead of vert lost the font's own forms."""
        forms, trims = self.forms_and_trims()
        extra = {u"uni3002": u"uniFE12", u"uni3001": u"uni3001.own"}
        vrt2 = cv.texts_for(forms, trims, {}, vrt2_extra=extra)["vrt2"]
        self.assertIn(u"sub uni3002 by uniFE12;", vrt2, "the font's own vert rule")
        self.assertIn(u"sub uni300C by uni300C.vert;", vrt2)
        self.assertNotIn(u"uni3001.own", vrt2, "a glyph FreeLab's own rule substitutes is not given two")
        self.assertNotIn(u"uniFE12", cv.texts_for(forms, trims, {}, vrt2_extra=extra)["vert"], "vert has it already")
        for form in forms:
            form.checked = False
        self.assertNotIn("vrt2", cv.texts_for(forms, [], {}, vrt2_extra=extra), "no vrt2 made for the font's rules alone")

    def test_code_without_a_closing_line_is_kept(self):
        """Review: an old text with code but no "} vert;" line was replaced by a new feature."""
        text = cv.feature_text("vert", u"  sub uni3001 by uniFE11;", [u"sub uni300C by uni300C.vert;"])
        self.assertIn(u"sub uni3001 by uniFE11;", text)
        self.assertLess(text.index(u"uniFE11"), text.index(cv.BEGIN % "vert"))
        self.assertTrue(cv.feature_text("vert", u"  \n", [u"sub a by b;"]).startswith(u"feature vert {"),
                        "no code: a feature of its own")

    def test_a_compact_feature_keeps_its_code(self):
        """Codex review 5 (Feature Code's writer, the same as this one): a feature on one line, or its brace after
        the last rule, had no "} vert;" line, and FreeLab's block went after the feature, outside it."""
        rule = u"sub uni300C by uni300C.vert;"
        for own in (u"feature vert { sub uni3001 by uniFE11; } vert;", u"feature vert {\nsub uni3001 by uniFE11; } vert;",
                    u"feature\nvert\n{ sub uni3001 by uniFE11;\n}\nvert;"):
            text = cv.feature_text("vert", own, [rule])
            self.assertIn(u"sub uni3001 by uniFE11;", text)
            self.assertLess(text.index(rule), cv.spacing().feature_code().feature_bounds(text, "vert")[1], "inside the feature: %r" % text)
            self.assertEqual(cv.spacing().feature_code().feature_bounds(text, "vert")[1], text.rindex(u"}"))
        self.assertIsNone(cv.feature_text("vert", u"feature vert { sub uni3001 by uniFE11;", [rule]),
                          "braces not found: nothing written")
        refused = []
        forms, trims = self.forms_and_trims()
        new = cv.texts_for(forms, trims, {"vert": u"feature vert { sub a by b;", "vrt2": u""}, refused=refused)
        self.assertNotIn("vert", new)
        self.assertEqual(refused, ["vert"])
        self.assertIn(u"FreeLab leaves vert as it is", cv.CJKVerticalDialog.cj_refused_words(refused))

    def test_no_vpal_for_a_form_left_unbuilt(self):
        forms, trims = self.forms_and_trims()
        trims.append(cv.VTrim(0x300C, "uni300C", "uni300C.vert", "punctuation", (400, -500), 650, 100))
        self.assertIn(u"pos uni300C.vert", cv.texts_for(forms, trims, {})["vpal"])
        forms[0].checked = False
        self.assertNotIn(u"uni300C.vert", cv.texts_for(forms, trims, {})["vpal"], "its glyph would be missing")
        forms[0].checked = True
        self.assertNotIn(u"uni300C.vert", cv.texts_for(forms, trims, {}, forms_on=False)["vpal"])

    def test_off_takes_the_block_out_and_unchanged_code_is_not_written(self):
        forms, trims = self.forms_and_trims()
        written = cv.texts_for(forms, trims, {})
        self.assertEqual(cv.texts_for(forms, trims, written), {}, "as written: nothing to write")
        off = cv.texts_for(forms, trims, written, forms_on=False, vpal_on=False)
        self.assertEqual(sorted(off), ["vert", "vpal", "vrt2"])
        self.assertNotIn(cv.BEGIN % "vert", off["vert"])
        for form in forms:
            form.checked = False
        self.assertNotIn("vert", cv.texts_for(forms, [], {}), "no feature made empty")

    def test_the_parser_takes_the_blocks(self):
        try:
            from fontTools.feaLib.parser import Parser
        except Exception:
            self.skipTest("fontTools is not installed")
        import io as _io
        forms, trims = self.forms_and_trims()
        names = set(["uni300C", "uni300C.vert", "uni3001", "uniFE11", "uni3042"])
        for tag, text in cv.texts_for(forms, trims, {}).items():
            Parser(_io.StringIO(cv.block_of(tag, text)), glyphNames=names).parse()


class TurnedTests(unittest.TestCase):
    def model(self):
        return {"turned": {"codes": {"U+0041": 1.0, "U+0061": 0.9, "U+007E": 0.3, "U+FF21": 1.0}, "how": "rotated",
                           "move": [0.0, 0.0], "advance": 1.0, "height": 1.0}}

    def test_proportional_glyphs_are_turned_about_the_ems_square(self):
        glyphs = [(0x41, "A", 640.0, (10.0, 0.0, 630.0, 700.0)), (0x61, "a", 520.0, (40.0, -10.0, 480.0, 520.0)),
                  (0x7E, "asciitilde", 600.0, (50.0, 250.0, 550.0, 350.0)),
                  (0xFF21, "uniFF21", 1000.0, (100.0, 0.0, 900.0, 700.0))]
        forms = dict((f.name, f) for f in cv.plan_turned(glyphs, [g[1] for g in glyphs] + ["a.vrt2"], self.model(),
                                                         1000.0, 880.0, own={}, ours={}))
        self.assertEqual(sorted(forms), ["A", "a"], "few turning fonts turn the tilde; a full-width glyph is not turned")
        self.assertEqual((forms["A"].target, forms["A"].state, forms["A"].section()), ("A.vrt2", "build", "turned"))
        self.assertEqual(forms["a"].state, "glyph", "the font's own a.vrt2 is used")
        self.assertEqual(rounded(forms["A"].matrix), (0, -1, 1, 0, 120, 880),
                         "about the em's square (its baseline 120 from the left), whatever its width")
        own = cv.plan_turned(glyphs, [g[1] for g in glyphs], self.model(), 1000.0, 880.0, own={"A": "A.rotat"})
        self.assertNotIn("A", [f.name for f in own], "the font's own vrt2 turns it")

    def test_one_vrt2_rule_per_glyph_its_vertical_form_first(self):
        """Live, IBM Plex Sans KR: en dash had both uniFE32 (its presentation form) and endash.vrt2."""
        form = cv.Form(0x2013, "endash", "rotated", "uniFE32", "glyph")
        turned = cv.Form(0x2013, "endash", "rotated", "endash.vrt2", "build", (0, -1, 1, 0, 120, 880))
        turned.vrt2_only = True
        rules = cv.vrt2_rules([form], {u"endash": u"endash.own"}, [turned])
        self.assertEqual(rules, [u"sub endash by uniFE32;"])
        glyphs = [(0x2013, "endash", 500.0, (0.0, 200.0, 500.0, 260.0))]
        self.assertEqual(cv.plan_turned(glyphs, ["endash", "uniFE32"], self.model(), 1000.0, 880.0,
                                        own={"endash": "uniFE32"}), [], "not planned: nothing unused is built")

    def test_turned_glyphs_go_in_vrt2_only(self):
        glyphs = [(0x41, "A", 640.0, (10.0, 0.0, 630.0, 700.0))]
        turned = cv.plan_turned(glyphs, ["A"], self.model(), 1000.0, 880.0)
        forms = [cv.Form(0x300C, "uni300C", "rotated", "uni300C.vert", "build", (0, -1, 1, 0, 120, 880))]
        texts = cv.texts_for(forms, [], {}, turned=turned)
        self.assertIn(u"sub A by A.vrt2;", texts["vrt2"])
        self.assertNotIn(u"A.vrt2", texts["vert"])
        self.assertNotIn(u"A.vrt2", cv.texts_for(forms, [], {}).get("vrt2", u""), "the option off: none")
        self.assertIn(u"sub uni3002 by uniFE12;", cv.texts_for([], [], {}, turned=turned,
                                                                 vrt2_extra={u"uni3002": u"uniFE12"})["vrt2"],
                      "a vrt2 made for the turned glyphs keeps the font's own vert forms")


class VkrnTests(unittest.TestCase):
    SETTINGS = {"cap": 0.4, "factor": 0.25, "threshold": 0.01, "most": 0.1}

    def column(self, bands):
        """A placed glyph from bands given as (y min, y max) in an em of 1000, origin 880, no vpal."""
        return cv.placed_profile(bands, 880.0, 1000.0)

    def test_profiles_and_the_white_between(self):
        upper = self.column([(0.0, 700.0)] * 16)  # ink 180 under the top, 120 over the bottom
        self.assertEqual(upper[0][0], (180.0, 120.0))
        lower = self.column([(0.0, 700.0)] * 16)
        self.assertEqual(cv.pair_gap(upper, lower, 400.0), 300.0, "120 under the upper, 180 over the lower")
        comma = self.column([None] * 12 + [(500.0, 800.0)] * 4)  # a vertical comma: ink at the right, high
        self.assertGreater(cv.pair_gap(upper, comma, 400.0), 300.0, "the comma's empty bands count as open white")
        raised = cv.placed_profile([(0.0, 700.0)] * 16, 880.0, 1000.0, (20, -40))
        self.assertEqual(raised[0][0], (160.0, 100.0), "vpal: placed up 20, 40 shorter")
        self.assertEqual(raised[1], 960.0)

    def test_scores_are_in_the_fonts_own_spread(self):
        """Live, Zen Kaku Gothic New: whites of 285 to 400 against the usual times a factor fitted on raw
        units gave at most 22 units: no pair passed the threshold. Scores make fonts comparable."""
        gaps = {"a": 300.0, "b": 320.0, "c": 340.0, "d": 360.0, "e": 400.0}
        scores = cv.gap_scores(gaps)
        self.assertEqual(scores["c"], 0.0, "the median: usual")
        self.assertLess(scores["e"], 0)
        self.assertGreater(scores["a"], 0)
        wide = cv.gap_scores(dict((k, v * 2) for k, v in gaps.items()))
        self.assertAlmostEqual(wide["e"], scores["e"], 6, msg="the same shape at twice the size scores the same")
        self.assertEqual(cv.gap_scores({}), {})

    def test_a_glyph_encoded_twice_gets_one_value_and_one_turned_copy(self):
        """Live, IBM Plex Sans KR: the wave dash's glyph is encoded at U+301C and U+FF5E, and got two vpal
        values ("Duplicate single positioning glyph with different values"); a turned copy would be built
        twice."""
        model = {"vpal": {"U+301C": [0.07, 0.07], "U+FF5E": [0.1, 0.1]}}
        box = (400.0, 24.0, 600.0, 736.0)
        shown = [(0x301C, "uni301C", "uni301C.vert", 1000.0, box), (0xFF5E, "uni301C", "uni301C.vert", 1000.0, box)]
        trims = cv.plan_vpal(shown, model, 1000.0, 880.0, kind_of=lambda code: "punctuation")
        self.assertEqual([(t.code, t.shown) for t in trims], [(0x301C, "uni301C.vert")])
        turned = {"turned": {"codes": {"U+0060": 1.0, "U+02CB": 1.0}, "how": "rotated", "move": [0, 0]}}
        glyphs = [(0x60, "grave", 300.0, (50.0, 500.0, 250.0, 700.0)), (0x2CB, "grave", 300.0, (50.0, 500.0, 250.0, 700.0))]
        self.assertEqual(len(cv.plan_turned(glyphs, ["grave"], turned, 1000.0, 880.0)), 1)

    def test_a_pairs_picture_draws_both_glyphs_a_form_to_build_from_its_glyph(self):
        """Live, Zen Kaku Gothic New: the list's pair rows had no picture to draw (an error read the font)."""
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        dialog.names = ["ka", "uni3001"]
        dialog.forms = [cv.Form(0x3001, "uni3001", "moved", "uni3001.vert", "build", (1, 0, 0, 1, 600, 600))]
        dialog.turned = []
        drawn = []
        dialog.picture = lambda grid, size, columns=True: drawn.append(grid) or "picture"
        kern = cv.VKern(0x304B, "ka", 0x3001, "uni3001.vert", -80, 22)
        self.assertEqual(dialog.row_picture(kern), "picture")
        self.assertEqual(drawn[0], [[("ka", None, 0, -80), ("uni3001", (1, 0, 0, 1, 600, 600), 0, 0)]])

    def test_the_corpus_values_are_written_scaled_to_the_em(self):
        """Live, Zen Kaku Gothic New and IBM Plex Sans KR: measured from the white between a pair, no value
        passed the threshold. The corpus's median per pair is written, scaled to the em."""
        settings = {"values": {"3059 FE11": [-0.1, 23], "304B 3055": [-0.004, 6], "30A2 30E1": [-0.04, 23]}}
        pairs = [(0x3059, "su", 0xFE11, "comma.vert"), (0x304B, "ka", 0x3055, "sa"), (0x30A2, "a-kata", 0x30E1, "me-kata"),
                 (0x3042, "a", 0x3044, "i")]
        kerns = dict(((k.first, k.second), k) for k in cv.plan_vkrn(pairs, settings, 2048.0))
        self.assertEqual(sorted(kerns), [("a-kata", "me-kata"), ("su", "comma.vert")],
                         "a value under 0.01 em, and a pair no font kerns, are left out")
        self.assertEqual(kerns[("su", "comma.vert")].value, -205)
        self.assertEqual(kerns[("su", "comma.vert")].fonts, 23)
        self.assertEqual(cv.vkrn_rules([kerns[("su", "comma.vert")]]), [u"pos su comma.vert <0 0 0 -205>;"])
        self.assertEqual([(k.first, k.second) for k in cv.plan_vkrn(pairs, settings, 2048.0, own={("su", "comma.vert")})],
                         [("a-kata", "me-kata")], "the font's own vkrn pair is left alone")

    def test_the_fonts_own_vkrn_and_vpal_are_read(self):
        text = u"""feature vkrn {
  pos uni3044 uniFE11 <0 0 0 -20>;
  pos @K [uni3078 uni3079] 10;
  pos uni3046 <0 5 0 -10>;
} vkrn;"""
        self.assertEqual(sorted(cv.own_pairs("vkrn", text, {u"@K": [u"uni3048"]})),
                         [(u"uni3044", u"uniFE11"), (u"uni3048", u"uni3078"), (u"uni3048", u"uni3079")],
                         "a single value is not a pair")
        vpal = u"""feature vpal {
  pos [uni3042 uni3044] <0 -2 0 -13>;
} vpal;"""
        self.assertEqual(cv.own_position_values("vpal", vpal), {u"uni3042": (-2, -13), u"uni3044": (-2, -13)})

    def test_vkrn_is_written_and_left_out_with_its_option_or_an_unbuilt_form(self):
        forms = [cv.Form(0x3001, "uni3001", "moved", "uni3001.vert", "build", (1, 0, 0, 1, 600, 600))]
        kern = cv.VKern(0x304B, "ka", 0x3001, "uni3001.vert", -40, 22)
        self.assertIn(u"pos ka uni3001.vert <0 0 0 -40>;", cv.texts_for(forms, [], {}, kerns=[kern])["vkrn"])
        self.assertNotIn("vkrn", cv.texts_for(forms, [], {}, kerns=[kern], vkrn_on=False))
        forms[0].checked = False
        self.assertNotIn("vkrn", cv.texts_for(forms, [], {}, kerns=[kern]), "its form unbuilt: its glyph would be missing")

    def test_the_dialog_kerns_full_width_pairs_as_vertical_text_sets_them(self):
        """Each glyph as vertical text sets it (the font's own form, or the form to build); a pair with a
        proportional glyph is left to applications and kern."""
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        dialog.package = type("P", (), {"upm": 1000.0})()
        dialog.origin, dialog.height = 880.0, 1000.0
        dialog.model = {"vkrn": {"values": {"304B 3001": [-0.08, 22], "0041 3001": [-0.05, 9], "304B 3002": [-0.1, 20]}}}
        dialog.forms = [cv.Form(0x3001, "uni3001", "moved", "uni3001.vert", "build", (1, 0, 0, 1, 600, 600))]
        dialog.own_vkrn = set()
        widths = {"ka": 1000.0, "uni3001": 1000.0, "uni3002": 1000.0, "A": 600.0}
        dialog.measure = lambda name: (widths[name], (0, 0, 1, 1))
        by_code = {0x304B: "ka", 0x3001: "uni3001", 0x3002: "uni3002", 0x41: "A"}
        kerns = dialog.plan_kerns(by_code, {"uni3002": "uniFE12"}, {})
        self.assertEqual(sorted((k.first, k.second, k.value) for k in kerns),
                         [("ka", "uni3001.vert", -80), ("ka", "uniFE12", -100)],
                         "the form to build, the font's own form; no pair with a proportional glyph")

    def test_the_shipped_model_has_vkrn_and_turned_glyphs(self):
        model = cv.load_model(os.path.join(HERE, os.pardir, "cjk", cv.MODEL_FILE))
        vkrn, turned = model["vkrn"], model["turned"]
        self.assertGreater(len(vkrn["values"]), 100)
        self.assertLess(vkrn["values"]["3059 FE11"][0], -0.05, "su before the vertical comma, drawn together")
        self.assertEqual((turned["how"], turned["advance"], turned["height"]), ("rotated", 1.0, 1.0))
        self.assertEqual(turned["codes"].get("U+0041"), 1.0)


class PreviewTests(unittest.TestCase):
    """The owner's screenshots (IBM Plex Sans JP): ideographs left out of the Chinese sample, columns past
    their pane, two Japanese samples, one marked "(vertical)" in a tool where every sample is vertical."""

    class Glyph(object):
        def __init__(self, name, unicodes):
            self.name, self.unicodes = name, unicodes
            self.unicode = unicodes[0] if unicodes else None

    def test_every_code_point_of_a_glyph_is_read(self):
        """Live: FontLab's unicode gives the Kangxi radical (U+2F47) of 日, not U+65E5."""
        glyphs = [self.Glyph("uni65E5", [0x2F47, 0x65E5]), self.Glyph("uni6708", [0x2F49, 0x6708]),
                  self.Glyph("uni5929", [0x5929]), self.Glyph("a", [])]
        names = cv.code_map(glyphs)
        self.assertEqual(names[0x65E5], "uni65E5")
        self.assertEqual(names[0x2F47], "uni65E5")
        self.assertEqual(names[0x6708], "uni6708")
        self.assertNotIn(None, names)
        old = type("Old", (), {"name": "x", "unicode": 0x41, "unicodes": None})()
        self.assertEqual(cv.code_map([old]), {0x41: "x"}, "unicode alone where FontLab gives no list")
        self.assertEqual(freelab_cjk_spacing.all_codes(glyphs)[0x65E5], "uni65E5", "CJK Spacing reads them too")

    def test_vkrn_shortens_the_upper_glyph_in_ems(self):
        """Review: vkrn was added to the heights in pixels while the heights are ems, and the columns broke
        and fitted wrong with vkrn on."""
        names = {0x304B: "ka", 0x3001: "uni3001"}
        placed, chars, heights = cv.preview_column(u"\u304b\u3001", names, {"uni3001": "uniFE11"}, {}, {},
                                                   {("ka", "uniFE11"): -100}, 1000.0, 1000.0)
        self.assertEqual(placed, [("ka", None, 0, -100), ("uniFE11", None, 0, 0)])
        self.assertEqual(heights, [0.9, 1.0], "in ems: 1000 less 100 units")
        plain = cv.preview_column(u"\u304b\u3001", names, {}, {}, {}, {}, 1000.0, 1000.0)
        self.assertEqual(plain[2], [1.0, 1.0])

    def test_a_character_past_the_bmp_is_one_character(self):
        """Review: FontLab's narrow Python splits U+20BB7 in two surrogates, each looked up and missed."""
        text = u"\U00020bb7\u304b"
        self.assertEqual([code for code, _ in cv.code_points(text)], [0x20BB7, 0x304B])
        placed, chars, _ = cv.preview_column(text, {0x20BB7: "u20BB7", 0x304B: "ka"}, {}, {}, {}, {}, 1000.0, 1000.0)
        self.assertEqual([item[0] for item in placed], ["u20BB7", "ka"])
        self.assertEqual(len(chars), 2)
        surrogates = u"\ud842\udfb7"  # (as a narrow Python holds it)
        self.assertEqual(cv.code_points(surrogates), [(0x20BB7, surrogates)])
        missing = cv.preview_column(u"\U00020bb7か", {0x304B: "ka"}, {}, {}, {}, {}, 1000.0, 1000.0)
        self.assertEqual((missing[0], missing[1]), ([("ka", None, 0, 0)], [u"か"]),
                         "left out whole, as CJK Spacing leaves it: no half of it drawn")

    def test_the_columns_fit_their_pane(self):
        chars = list(u"\u3044\u308d\u306f") * 16  # 48 kana: 48 ems of column
        heights_at = lambda em: [em] * len(chars)
        em = cv.fitting_em(chars, heights_at, 300, 248, 40)
        self.assertLess(em, 40, "at 40 px the columns are wider than the pane")
        columns = len(cv.vertical_lines(chars, heights_at(em), 240))
        self.assertLessEqual(columns * em * cv.COLUMN_STEP + 4, 300 - 8)
        self.assertEqual(cv.fitting_em(chars[:4], heights_at, 300, 248, 40), 40, "a short sample keeps the em")
        self.assertEqual(cv.fitting_em(chars * 10, lambda em: [em] * 480, 100, 60, 40), 12, "the smallest when none fits")

    def test_one_sample_per_writing_system(self):
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        source = io.open(os.path.join(HERE, os.pardir, "cjk", "freelab_cjk_vertical.py"), encoding="utf-8").read()
        self.assertNotIn(u"(vertical)", source.split("class CJKVerticalDialog")[1].split("def watch_previews")[0])
        samples = [(u"ja", u"Japanese", cv.SAMPLE_JA)] + [s for s in freelab_cjk_spacing.SAMPLES if s[0] != "ja"]
        self.assertEqual([label for _, label, _ in samples],
                         [u"Japanese", u"Korean", u"Chinese (Simplified)", u"Chinese (Traditional)"])
        self.assertTrue(dialog is not None)


class TrainerTests(unittest.TestCase):
    def test_a_double_encoded_glyph_is_read_as_its_ideograph(self):
        """Review: the trainer keyed a glyph encoded at a Kangxi radical and its ideograph by the radical."""
        if sys.version_info[0] < 3:
            self.skipTest("the trainer runs under Python 3")
        try:
            sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning", "train"))
            sys.path.insert(0, os.path.join(HERE, os.pardir, "cjk", "train"))
            import vertical as trainer
        except Exception as exc:
            self.skipTest("the trainer's needs are missing: %s" % exc)
        self.assertTrue(trainer.is_duplicate(0x2F47))
        self.assertFalse(trainer.is_duplicate(0x65E5))
        kept = trainer.pair_values
        trainer.pair_values = lambda font, tag: {("uni65E5", "uniFE11"): -50}
        try:
            found = trainer.pair_codes(None, {0x2F47: "uni65E5", 0x65E5: "uni65E5", 0x3001: "uni3001"},
                                       {"uni3001": "uniFE11"})
        finally:
            trainer.pair_values = kept
        self.assertEqual(found, {(0x65E5, 0x3001): -50})


class ModelTests(unittest.TestCase):
    def test_the_shipped_model(self):
        model = cv.load_model(os.path.join(HERE, os.pardir, "cjk", cv.MODEL_FILE))
        self.assertEqual(model.get("format"), 1)
        self.assertGreaterEqual(model["fonts"], 20)
        vert = model["vert"]
        self.assertIn(vert["U+3008"]["how"], cv.TURNS, "an angle bracket turns")
        self.assertEqual(vert["U+30C3"]["how"], "moved", "a small tu moves")
        dx, dy = vert["U+30C3"]["move"]
        self.assertTrue(0.03 < dx < 0.2 and 0.03 < dy < 0.2, "to the upper right")
        dx, dy = vert["U+3001"]["move"]
        self.assertTrue(dx > 0.4 and dy > 0.4, "the comma to the upper right")
        self.assertEqual(model["orientation"]["U+3001"], "Tu")
        self.assertEqual(model["orientation"]["U+300C"], "Tr")
        self.assertEqual(model["metrics"]["advance_height"], 1.0)
        for kind in ("hiragana", "katakana", "punctuation"):
            self.assertIn(kind, model["vpal"])

    def test_a_bare_font_of_the_kana_gets_forms_from_the_shipped_model(self):
        model = cv.load_model(os.path.join(HERE, os.pardir, "cjk", cv.MODEL_FILE))
        glyphs = [(0x30C3, "uni30C3", 1000.0, (180.0, -40.0, 820.0, 600.0)),
                  (0x3008, "uni3008", 1000.0, (600.0, -80.0, 900.0, 840.0))]
        forms = cv.plan_forms(glyphs, [g[1] for g in glyphs], model, 1000.0, 880.0)
        self.assertEqual(sorted((f.name, f.state) for f in forms), [("uni3008", "build"), ("uni30C3", "build")])


class FakeQtTests(unittest.TestCase):
    """Building a form, advance heights, and vhea, on fakes of FontLab's objects."""

    class Transform(object):
        def __init__(self, *values):
            self.values = values

        def m11(self):
            return self.values[0]

        def m12(self):
            return self.values[1]

        def m21(self):
            return self.values[2]

        def m22(self):
            return self.values[3]

        def dx(self):
            return self.values[4]

        def dy(self):
            return self.values[5]

    class Component(object):
        def __init__(self, name):
            self.name, self.transform = name, None

    class Shape(object):
        def __init__(self, component=None, transform=None):
            self.isComponent = component is not None
            self.transform = transform
            self.shapeData = type("Data", (), {"componentGlyph": component})()

    class Box(object):  # (FontLab's QRectF: y() the ink's bottom, its height upward)
        def __init__(self, ink):
            self.ink = ink

        def x(self):
            return self.ink[0]

        def y(self):
            return self.ink[1]

        def width(self):
            return self.ink[2] - self.ink[0]

        def height(self):
            return self.ink[3] - self.ink[1]

    class Layer(object):
        def __init__(self, advance=1000.0, shapes=None, ink=(654.0, 110.0, 944.0, 835.0)):
            self.advanceWidth, self.shapes = advance, list(shapes or [])
            self.advanceHeight, self.hasAdvanceHeight = 0.0, False
            self.boundingBox = FakeQtTests.Box(ink)

        def setGlyphComponents(self, components, width, package, flag):
            self.shapes = [FakeQtTests.Shape(c.name, c.transform) for c in components]
            self.advanceWidth = width

        def update(self):
            pass

    class Glyph(object):
        def __init__(self, name, layers=None):
            self.name, self.layers, self.isNull = name, dict(layers or {}), False
            self.updates = 0

        def update(self):
            self.updates += 1

        def getLayerByName(self, master, create=False):
            if create and master not in self.layers:
                self.layers[master] = FakeQtTests.Layer()
            return self.layers.get(master)

    class Package(object):
        def __init__(self, glyphs, masters=("Regular", "Bold")):
            self.glyphs = dict((g.name, g) for g in glyphs)
            self.masters, self.master, self.upm = list(masters), masters[0], 1000.0
            self.deleted = []
            self.fgPackage = type("Fg", (), {"info": type("Info", (), {})()})()

        def findName(self, name):
            return self.glyphs.get(name)

        def addGlyph(self, glyph):
            self.glyphs[glyph.name] = FakeQtTests.Glyph(glyph.name)

        def deleteGlyph(self, glyph):
            self.deleted.append(glyph.name)
            self.glyphs.pop(glyph.name, None)

    def setUp(self):
        import qtfakes
        qtfakes.install()
        sys.modules["PythonQt.QtGui"].QTransform = self.Transform
        self.qtfakes = qtfakes

    def tearDown(self):
        self.qtfakes.uninstall()

    def dialog(self, package):
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)  # (its window needs FontLab)
        test = self
        dialog.fontlab = type("FL", (), {"flGlyph": staticmethod(lambda: type("G", (), {"name": None})()),
                                         "GlyphComponent": test.Component})
        dialog.package, dialog.model = package, MODEL
        dialog.origin, dialog.height = 880.0, 1000.0
        dialog.names = list(package.glyphs)
        return dialog

    def test_a_form_is_a_turned_component_in_every_master(self):
        source = self.Glyph("uni300C", {"Regular": self.Layer(1000.0), "Bold": self.Layer(1000.0)})
        package = self.Package([source])
        dialog = self.dialog(package)
        form = cv.Form(0x300C, "uni300C", "rotated", "uni300C.vert", "build", (0, -1, 1, 0, 120, 880))
        glyph, why = dialog.build_form(package, form)
        self.assertIsNone(why)
        for master in ("Regular", "Bold"):
            layer = glyph.getLayerByName(master)
            self.assertEqual(len(layer.shapes), 1)
            self.assertEqual(layer.shapes[0].shapeData.componentGlyph, "uni300C")
            self.assertEqual(rounded(layer.shapes[0].transform.values), (0, -1, 1, 0, 120, 880))
            self.assertEqual(layer.advanceHeight, 1000.0, "the em, as its glyph has none")
        again, why = dialog.build_form(package, form)
        self.assertIsNone(again)
        self.assertEqual(why, u"the font has a glyph of that name now", "a glyph of the name is never replaced")

    def test_a_moved_form_takes_the_same_place_in_every_master(self):
        """Each master's small tu, wherever its ink sits, goes to where the corpus puts the form's ink."""
        source = self.Glyph("uni3063", {"Regular": self.Layer(1000.0, ink=(200.0, -50.0, 800.0, 550.0)),
                                        "Bold": self.Layer(1000.0, ink=(180.0, -70.0, 820.0, 570.0))})
        package = self.Package([source])
        dialog = self.dialog(package)
        dialog.model = dict(MODEL, vert={"U+3063": {"fonts": 98, "agree": 0.98, "exact": 0.65, "how": "moved",
                                                    "move": [0.12, 0.116], "place": [0.62, 0.48]}})
        form = cv.Form(0x3063, "uni3063", "moved", "uni3063.vert", "build", (1, 0, 0, 1, 120, 116))
        glyph, _ = dialog.build_form(package, form)
        for master in ("Regular", "Bold"):
            values = glyph.getLayerByName(master).shapes[0].transform.values
            self.assertEqual(rounded(values[4:]), (120, 110), master)  # (center 500, 250 to 620, 360)

    def test_busy_ends_when_the_write_raises(self):
        """Review: an error in notify_changed or the vhea write left busy set (the History watcher silent,
        the window never let go)."""
        package = self.Package([self.Glyph("uni300C", {"Regular": self.Layer(1000.0)})], masters=("Regular",))
        package.fgPackage.features = StaleCodeTests.Features({})
        dialog = self.dialog(package)
        dialog.texts, dialog.prefix, dialog.classes = {}, u"", {}
        logged = []
        raising = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("FontLab said no"))
        top = TopRow()
        dialog.ak = type("Ak", (), dict(
            font_key=staticmethod(lambda p: 1), load_sibling=staticmethod(raising),
            before_changes=staticmethod(lambda *args: []),
            notify_changed=staticmethod(raising), b=staticmethod(lambda t: t), html=staticmethod(lambda t: u"%s" % t),
            joined=staticmethod(lambda items: u", ".join(items)), enable=staticmethod(lambda w, on: None),
            **top.members()))
        dialog.log = type("Log", (), {"add": lambda self, text, kind=None: logged.append((kind, text))})()
        dialog.harvest = dialog.run = dialog.read_font = lambda: None
        dialog.current_font = lambda: package
        heights = cv.Metric("advance_height", u"Advance heights", None, 1000, 1)
        dialog.pending = lambda: ({}, [], [heights])
        dialog.set_advance_heights = lambda package, value: 1
        dialog.write()
        self.assertFalse(dialog.busy)
        self.assertTrue(any(kind == "error" and u"FontLab said no" in text for kind, text in logged), logged)
        # (owner's image 183: under the top row's progress at once, never stoppable while it writes, and ended)
        self.assertEqual((top.kinds()[0], top.kinds()[-1]), ("start", "end"))
        self.assertFalse(top.calls[0][2], "the write is not stoppable")

    def test_a_glyph_of_one_component_is_followed(self):
        inner = self.Glyph("uniFF08", {"Regular": self.Layer(1000.0)})
        outer = self.Glyph("uniFF08.alt", {"Regular": self.Layer(1000.0, [self.Shape("uniFF08", self.Transform(1, 0, 0, 1, 30, 0))])})
        package = self.Package([inner, outer], masters=("Regular",))
        dialog = self.dialog(package)
        form = cv.Form(0xFF08, "uniFF08.alt", "rotated", "uniFF08.alt.vert", "build", (0, -1, 1, 0, 120, 880))
        glyph, _ = dialog.build_form(package, form)
        shape = glyph.getLayerByName("Regular").shapes[0]
        self.assertEqual(shape.shapeData.componentGlyph, "uniFF08", "the glyph it points to")
        self.assertEqual(rounded(shape.transform.values), (0, -1, 1, 0, 120, 850), "the inner move, turned (30 across becomes 30 down)")

    def test_a_form_fontlab_leaves_empty_is_taken_out(self):
        source = self.Glyph("uni300C", {"Regular": self.Layer(1000.0)})
        package = self.Package([source], masters=("Regular",))
        dialog = self.dialog(package)
        self.Layer.setGlyphComponents, kept = (lambda *args: None), self.Layer.setGlyphComponents
        try:
            glyph, why = dialog.build_form(package, cv.Form(0x300C, "uni300C", "rotated", "uni300C.vert", "build",
                                                            (0, -1, 1, 0, 120, 880)))
        finally:
            self.Layer.setGlyphComponents = kept
        self.assertIsNone(glyph)
        self.assertEqual(package.deleted, ["uni300C.vert"])
        self.assertIn(u"did not keep", why)

    def test_a_form_that_fails_midway_is_taken_out_and_the_rest_written(self):
        """Review: an error after the glyph was added left it empty in the font and skipped the rest."""
        source = self.Glyph("uni300C", {"Regular": self.Layer(1000.0)})
        package = self.Package([source], masters=("Regular",))
        dialog = self.dialog(package)

        def broken(*args):
            raise RuntimeError("FontLab said no")
        self.Layer.setGlyphComponents, kept = broken, self.Layer.setGlyphComponents
        try:
            glyph, why = dialog.build_form_safely(package, cv.Form(0x300C, "uni300C", "rotated", "uni300C.vert", "build",
                                                                   (0, -1, 1, 0, 120, 880)))
        finally:
            self.Layer.setGlyphComponents = kept
        self.assertIsNone(glyph)
        self.assertEqual(why, u"FontLab said no")
        self.assertEqual(package.deleted, ["uni300C.vert"], "the empty glyph taken out again")
        self.assertIsNone(package.findName("uni300C.vert"))
        source = io.open(os.path.join(HERE, os.pardir, "cjk", "freelab_cjk_vertical.py"), encoding="utf-8").read()
        self.assertIn(u"glyph, why = self.build_form_safely(package, form)", source,
                      "the write builds each form through it, and goes on to the next")

    def test_a_font_without_cjk_glyphs_is_offered_nothing(self):
        """The owner, of Noto Sans: "The CJK spacing section is aware that the font contains no such glyphs,
        but the CJK vertical section disagrees because of some punctuation marks". Its em-wide HORIZONTAL
        BAR (U+2015, General Punctuation: the dash Japanese text turns, so the corpus turns it) passed every
        test of a form, and the vertical metrics were offered too: a font with no CJK glyph is offered
        nothing, and the line over the list says why."""
        self.assertFalse(cv.has_cjk([0x41, 0x2015, 0x2014, 0x201C, 0x0416, 0x03BC]))
        for code in (0x3001, 0x304B, 0x30AB, 0x3105, 0x4E00, 0xAC00, 0xFE41, 0xFF08, 0x20BB7):
            self.assertTrue(cv.has_cjk([0x41, code]), hex(code))
        model = dict(MODEL, vert=dict(MODEL["vert"], **{"U+2015": {"fonts": 90, "agree": 0.9, "how": "rotated",
                                                                    "move": [0.0, 0.0]}}))

        def listed(codes):
            glyphs = [self.Glyph(u"uni%04X" % code, {"Regular": self.Layer(1000.0)}) for code in codes]
            package = self.Package(glyphs, masters=("Regular",))
            package.fgPackage.glyphs = [type("Fg", (), {"name": glyph.name, "unicodes": [code]})()
                                        for glyph, code in zip(glyphs, codes)]
            package.fgPackage.features = StaleCodeTests.Features({})
            package.tfn = u"Fake Sans"
            dialog = self.dialog(package)
            dialog.model, dialog.cj = model, cv.spacing()
            dialog.boxes, dialog.busy, dialog.holding = {}, False, False
            widget = ProgressTests.Widget
            dialog.status, dialog.sample, dialog.sample_box = widget(), widget(), widget()
            dialog.tree = type("Tree", (), {"blockSignals": lambda self, on: None, "clear": lambda self: None})()
            dialog.samples = [(u"ja", u"Japanese", cv.SAMPLE_JA)]
            dialog.ak = type("Ak", (), dict(b=staticmethod(lambda t: u"%s" % t), i=staticmethod(lambda t: u"%s" % t),
                                            joined=staticmethod(lambda items: u", ".join(items)),
                                            history_mark=staticmethod(lambda p: None),
                                            font_named=staticmethod(lambda name, master=None, masters=1:
                                                                    u"%s, master %s" % (name, master))))
            for name in ("show_font_parts", "fill", "update_buttons", "update_put_back", "draw_previews", "progress"):
                setattr(dialog, name, lambda *args, **kwargs: None)
            dialog.current_checks = lambda: {}
            dialog.current_font = lambda: package
            dialog.font_classes = lambda package, features: {}
            dialog.read_font()
            return dialog

        latin = listed([0x41, 0x2015])
        self.assertEqual((latin.forms, latin.trims, latin.turned, latin.kerns, latin.metrics), ([], [], [], [], []))
        # (the font line first, as every window's: ak.font_named, owner's images 223 and 238)
        self.assertEqual(latin.status.text, u"Fake Sans, master Regular. No kana, Hangul, ideographs, or CJK "
                                            u"punctuation: not a CJK font, nothing to add for vertical text.")
        cjk = listed([0x41, 0x2015, 0x300C])
        self.assertEqual(sorted(f.name for f in cjk.forms), [u"uni2015", u"uni300C"], "a CJK font's dash turns")
        self.assertTrue(cjk.metrics)
        self.assertNotIn(u"not a CJK font", cjk.status.text)

    def test_advance_heights_only_where_none(self):
        set_one = self.Layer()
        set_one.advanceHeight, set_one.hasAdvanceHeight = 1100.0, True
        package = self.Package([self.Glyph("a", {"Regular": self.Layer()}), self.Glyph("b", {"Regular": set_one})],
                               masters=("Regular",))
        dialog = self.dialog(package)
        self.assertEqual(dialog.set_advance_heights(package, 1000), 1)
        self.assertEqual(package.findName("a").getLayerByName("Regular").advanceHeight, 1000)
        self.assertEqual(set_one.advanceHeight, 1100.0, "the font's own kept")
        self.assertEqual((package.findName("a").updates, package.findName("b").updates), (1, 0),
                         "live: without the glyph's update() the height was gone after the write in most glyphs")


class StaleCodeTests(unittest.TestCase):
    """Review: a write composed its code from the code read with the list, so an edit of vert, vrt2, vpal, or
    vkrn made since (before the History watcher's next look, or one that leaves the History where it was)
    was replaced. The write now compares the font's code with what was read, after the last event it lets
    through, and writes nothing when it differs."""

    USER_VERT = u"feature vert {\n  sub uni3001 by uni3001.vert;\n} vert;\n"

    class Features(object):
        def __init__(self, texts, prefix=u""):
            self.texts, self.prefix, self.written = dict(texts), prefix, []

        def keys(self):
            return list(self.texts)

        def get_feature(self, tag):
            return self.texts[tag]

        def get_prefix(self):
            return self.prefix

        def set_feature(self, tag, text):
            self.written.append(tag)
            self.texts[tag] = text

    def setUp(self):
        import qtfakes
        qtfakes.install()
        self.addCleanup(qtfakes.uninstall)
        gui = sys.modules["PythonQt.QtGui"]
        gui.QLabel, gui.QProgressBar = "QLabel", "QProgressBar"  # (the top row's parts, found by name: paint_bar)
        self.pumps, self.on_pump = [], None
        self.top = TopRow()

        def pumped():  # (ak's busy_start and busy_progress let events through)
            self.pumps.append(self.dialog.holding)
            if self.on_pump is not None:
                self.on_pump()
        self.top.on_progress = pumped

    def make(self, texts, prefix=u""):
        features = self.Features(texts, prefix)
        package = FakeQtTests.Package([FakeQtTests.Glyph("uni300C", {"Regular": FakeQtTests.Layer(1000.0)})],
                                      masters=("Regular",))
        package.fgPackage.features = features
        dialog = self.dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)  # (its window needs FontLab)
        dialog.package, dialog.names, dialog.fontlab = package, ["uni300C"], None
        dialog.texts, dialog.prefix, dialog.classes = dict(texts), features.get_prefix(), {}
        dialog.holding, dialog.busy, dialog.busy_shown, dialog.run_due = False, False, False, False
        widget = ProgressTests.Widget
        dialog.busy_step, dialog.busy_bar = widget(), widget()  # (the top row's, as ak's busy_row makes them)
        parts = {"freelabBusyStep": dialog.busy_step, "freelabBusyBar": dialog.busy_bar}
        dialog.dialog = type("Dialog", (), {"findChild": lambda _, kind, name: parts.get(name)})()
        dialog.tree, dialog.write_button, dialog.export_button, dialog.compile_box = widget(), widget(), widget(), None
        self.logged, self.steps, self.reads, self.history = [], [], [], []
        dialog.log = type("Log", (), {"add": lambda _, text, kind=None: self.logged.append((kind, text))})()
        raising = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no Feature Code here"))
        dialog.ak = type("Ak", (), dict(
            font_key=staticmethod(lambda p: 1), load_sibling=staticmethod(raising), LOG_COLORS={},
            enable=staticmethod(lambda w, on: w.setEnabled(bool(on)) if w is not None else None),
            before_changes=staticmethod(lambda *args: self.history.append("before")),
            notify_changed=staticmethod(lambda *args, **kwargs: self.history.append("notify")),
            compiled_note=staticmethod(lambda box, log: u""), glyph_name_links=staticmethod(lambda names: u" ".join(names)),
            b=staticmethod(lambda t: u"%s" % t), html=staticmethod(lambda t: u"%s" % t),
            joined=staticmethod(lambda items: u" and ".join(items)), **self.top.members()))
        dialog.harvest = dialog.show_font_parts = lambda *args: None
        dialog.update_buttons = dialog.update_put_back = lambda: None
        dialog.read_font = lambda: self.reads.append(dialog.busy)
        dialog.current_font = lambda: package
        kept = dialog.progress
        dialog.progress = lambda label, part=0.0, events=True: (self.steps.append((label, dialog.holding)),
                                                               kept(label, part, events))
        form = cv.Form(0x300C, "uni300C", "rotated", "uni300C.vert", "build", (0, -1, 1, 0, 120, 880))
        self.built = []
        dialog.build_form_safely = lambda package, form: (self.built.append(form.target), (object(), None))[1]
        new = {"vert": cv.feature_text("vert", texts.get("vert"), [u"sub uni300C by uni300C.vert;"])}
        dialog.pending = lambda: (new, [form], [])
        return dialog, features

    def refused(self, features):
        self.assertEqual(features.written, [], "no feature replaced")
        self.assertEqual(self.built, [], "no form built")
        self.assertEqual(self.history, [], "no History step")
        self.assertEqual(self.reads, [True], "the list read again (under the bar)")
        self.assertEqual([kind for kind, _ in self.logged], ["warning"], self.logged)
        self.assertIn(u"Nothing was written", self.logged[0][1])
        self.assertFalse(self.dialog.busy)
        self.assertFalse(self.dialog.holding)

    def test_an_edit_made_since_the_list_was_read_is_kept(self):
        dialog, features = self.make({"vert": self.USER_VERT})
        features.texts["vert"] = self.USER_VERT.replace(u"} vert;", u"  sub uni3002 by uni3002.vert;\n} vert;")
        edited = features.texts["vert"]
        dialog.write()
        self.refused(features)
        self.assertEqual(features.texts["vert"], edited, "the user's rule is still there")
        self.assertIn(u"(vert)", self.logged[0][1])

    def test_a_feature_added_since_or_a_new_prefix_is_seen_too(self):
        dialog, features = self.make({"vert": self.USER_VERT})
        features.texts["vkrn"] = u"feature vkrn {\n  pos uni3042 uni3001 -80;\n} vkrn;\n"
        dialog.write()
        self.refused(features)
        self.assertIn(u"(vkrn)", self.logged[0][1])
        dialog, features = self.make({"vert": self.USER_VERT}, prefix=u"@kana = [uni3042];")
        features.prefix = u"@kana = [uni3042 uni3044];"
        dialog.write()
        self.refused(features)
        self.assertIn(u"(prefix)", self.logged[0][1])

    def test_an_edit_let_through_by_the_bar_is_seen(self):
        """The bar lets events through as it shows; an edit made then is after any check made before it."""
        dialog, features = self.make({"vert": self.USER_VERT})

        def edit():
            features.texts["vert"] = self.USER_VERT + u"# mine\n"
            self.on_pump = None
        self.on_pump = edit
        dialog.write()
        self.assertTrue(self.pumps, "the bar shown at once let events through")
        self.refused(features)

    def test_no_event_goes_through_between_the_check_and_the_code(self):
        dialog, features = self.make({"vert": self.USER_VERT})
        dialog.write()
        self.assertEqual(features.written, ["vert"], self.logged)
        self.assertEqual(self.built, ["uni300C.vert"])
        self.assertIn(u"sub uni3001 by uni3001.vert;", features.texts["vert"], "the font's own rule kept")
        self.assertEqual(self.history, ["before", "notify"])
        self.assertNotIn(True, self.pumps, "no event let through while holding")
        held = [label for label, holding in self.steps if holding]
        self.assertEqual(held, [cv.UNDO_STEP, cv.BUILD_STEP, cv.BUILD_STEP, cv.CODE_STEP], "the bar still moves meanwhile")
        self.assertEqual(dialog.busy_step.repaints, 2, "each new step painted without events (the first by busy_start)")
        self.assertEqual(dialog.busy_bar.value, int(round(1000 * cv.bar_value(cv.WRITE_STEPS, cv.CODE_STEP))),
                         "the top row's bar moved meanwhile")
        self.assertFalse(dialog.holding)
        self.assertIn(False, self.pumps[1:], "events go through again once the code is written")
        self.assertFalse(any(call[-1] for call in self.top.calls if call[0] != "end"), "never stoppable while it writes")
        self.assertEqual(self.top.kinds()[-1], "end")


class ExportTests(unittest.TestCase):
    """Vertical metrics added to a font FontLab exported (its export writes none)."""

    class Layer(object):
        def __init__(self, height=None):
            self.advanceHeight, self.hasAdvanceHeight = (height or 0.0), height is not None

    class Glyph(object):
        def __init__(self, name, height=None, codes=()):
            self.name, self.unicodes = name, list(codes)
            self.unicode = codes[0] if codes else None
            self.layer = ExportTests.Layer(height)

        def getLayerByName(self, master):
            return self.layer

    class Package(object):
        def __init__(self, glyphs, upm=1000.0):
            self.upm, self.master, self.tfn = upm, u"Regular", u"Test"
            self.found = dict((g.name, g) for g in glyphs)
            info = type("Info", (), {"openTypeVheaVertTypoAscender": 500, "openTypeVheaVertTypoDescender": -500,
                                     "openTypeVheaVertTypoLineGap": None})()
            self.fgPackage = type("Fg", (), {"glyphs": list(glyphs), "info": info})()

        def findName(self, name):
            return self.found.get(name)

    def package(self, upm=1000.0):
        return self.Package([self.Glyph("a-kana", 1000.0, [0x3042]), self.Glyph("comma", 500.0, [0x3001]),
                             self.Glyph("uni65E5", 900.0, [0x2F47, 0x65E5]), self.Glyph("space", None, [0x20])], upm)

    def dialog(self, package):
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        dialog.package, dialog.origin = package, 880.0
        dialog.metrics = [cv.Metric("vhea_line_gap", u"vhea line gap", None, 0, None)]
        self.logged = []
        dialog.log = type("Log", (), {"add": lambda _, text, kind=None: self.logged.append((kind, text))})()
        self.top = TopRow()
        dialog.ak = type("Ak", (), dict(b=staticmethod(lambda t: t), html=staticmethod(lambda t: u"%s" % t),
                                        **self.top.members()))
        return dialog

    def test_a_stopped_export_writes_nothing(self):
        """Stoppable (the top row's Esc, Close, a tool, an arrow): stopped before the copy takes its name, the
        folder is left as it was."""
        path = self.exported()
        folder = os.path.dirname(path)
        listed = sorted(os.listdir(folder))
        dialog = self.dialog(self.package())
        self.top.stop_after = 3
        dialog.add_metrics_to_export(path)
        self.assertEqual([kind for kind, _ in self.logged], ["warning"], self.logged)
        self.assertIn(u"was stopped: nothing was written", self.logged[0][1])
        self.assertEqual(sorted(os.listdir(folder)), listed, "no copy, no values file, no staged file")
        self.assertEqual(self.top.kinds()[-1], "end")
        self.assertFalse(dialog.busy)

    def test_the_values_hold_the_heights_that_are_not_the_em(self):
        values = cv.export_values(1000.0, 880.4, (500.0, -500.0, 0.0), {"a": 1000.0, "b": 500.2}, {"a": [0x3042], "c": []},
                                  u"Test", u"Regular")
        self.assertEqual(values["format"], 1)
        self.assertEqual((values["upm"], values["origin"], values["default_height"]), (1000, 880, 1000))
        self.assertEqual(values["vhea"], {"ascent": 500, "descent": -500, "lineGap": 0})
        self.assertEqual(values["heights"], {"b": 500})
        self.assertEqual(values["codes"], {"a": [0x3042]})

    def test_the_font_values_heights_and_vhea_line_gap_suggested(self):
        values = self.dialog(self.package()).metrics_values(self.package())
        self.assertEqual(values["heights"], {"comma": 500, "uni65E5": 900})
        self.assertEqual(values["codes"]["uni65E5"], [0x2F47, 0x65E5], "every code point, not FontLab's first")
        self.assertEqual(values["vhea"], {"ascent": 500, "descent": -500, "lineGap": 0}, "the line gap unset: suggested")
        self.assertEqual(values["origin"], 880)

    def test_a_free_name_never_replaces_a_file(self):
        taken = set([u"a.vert.ttf", u"a.vert-2.ttf"])
        self.assertEqual(cv.free_name(u"b.vert.ttf", taken.__contains__), u"b.vert.ttf")
        self.assertEqual(cv.free_name(u"a.vert.ttf", taken.__contains__), u"a.vert-3.ttf")

    def test_the_script_loads_in_this_python(self):
        """It runs inside FontLab 7's Python 2.7, as well as on its own under Python 3."""
        script = cv.load_metrics_script()
        self.assertEqual(script.output_path(os.path.join(u"x", u"Font.otf")), os.path.join(u"x", u"Font.vert.otf"))
        self.assertEqual(script.values_path(u"Font.otf"), u"Font.otf.vertical.json")
        for name in ("add_tables", "check", "heights_by_glyph", "main", "same_file", "staged_path", "publish",
                     "discard", "write_copy", "load_values"):
            self.assertTrue(callable(getattr(script, name)), name)

    def exported(self):
        try:
            import fontTools.ttLib  # noqa: F401
            import vertical_metrics_tests
        except ImportError:
            self.skipTest("fontTools")
        import shutil
        import tempfile
        import qtfakes
        qtfakes.install()
        self.addCleanup(qtfakes.uninstall)
        folder = tempfile.mkdtemp(prefix="freelab-vertical-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, u"test.ttf")
        vertical_metrics_tests.make_font(path)
        return path

    def test_the_button_writes_a_copy_with_the_tables_and_keeps_the_export(self):
        path = self.exported()
        from fontTools.ttLib import TTFont
        before = open(path, "rb").read()
        dialog = self.dialog(self.package())
        steps, kept = [], dialog.progress
        dialog.progress = lambda label, part=0.0: (steps.append(label), kept(label, part))
        dialog.add_metrics_to_export(path)
        self.assertEqual([kind for kind, _ in self.logged], ["done"], self.logged)
        self.assertEqual(sorted(set(steps), key=steps.index), [label for label, _ in cv.EXPORT_STEPS],
                         "every step on the bar, in order")
        self.assertFalse(dialog.busy)
        out = os.path.join(os.path.dirname(path), u"test.vert.ttf")
        vmtx = TTFont(out)["vmtx"].metrics
        self.assertEqual(vmtx["comma"], (500, 80))
        self.assertEqual(vmtx["sun"], (900, 90), "found by its code point under the export's name")
        self.assertEqual(vmtx["a-kana"], (1000, 80))
        self.assertEqual(open(path, "rb").read(), before, "the exported font is unchanged")
        self.assertTrue(os.path.isfile(path + u".vertical.json"))
        dialog.add_metrics_to_export(path)
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(path), u"test.vert-2.ttf")), "the first kept")

    def test_a_cff_export_gets_vorg_and_its_own_shares_of_the_bar(self):
        path = self.exported()
        import vertical_metrics_tests
        otf = os.path.join(os.path.dirname(path), u"test.otf")
        vertical_metrics_tests.make_font(otf, cff=True)
        dialog = self.dialog(self.package())
        shares, kept = [], dialog.progress
        dialog.progress = lambda label, part=0.0: (shares.append((label, dialog.busy_steps)), kept(label, part))
        dialog.add_metrics_to_export(otf)
        self.assertEqual([kind for kind, _ in self.logged], ["done"], self.logged)
        self.assertIn(u"vhea, vmtx, and VORG", self.logged[0][1])
        self.assertEqual(dict(shares)[cv.SAVE_STEP], cv.CFF_EXPORT_STEPS, "saving a CFF copy takes longer")
        from fontTools.ttLib import TTFont
        out = TTFont(os.path.join(os.path.dirname(path), u"test.vert.otf"))
        self.assertEqual(out["VORG"].defaultVertOriginY, 880)
        out.close()

    def test_a_font_of_another_em_is_refused(self):
        path = self.exported()
        dialog = self.dialog(self.package(2048.0))
        dialog.add_metrics_to_export(path)
        self.assertEqual([kind for kind, _ in self.logged], ["error"])
        self.assertIn(u"1,000 units", self.logged[0][1])
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(path), u"test.vert.ttf")))

    SENTINEL = {"format": 1, "upm": 2048, "origin": 1800, "family": u"Other", "master": u"Bold",
                "vhea": {"ascent": 1024, "descent": -1024, "lineGap": 0}, "default_height": 2048, "heights": {},
                "codes": {}}

    def sentinel(self, path, values=None):
        """A values file beside the export already, as an earlier use (or the user) left it."""
        sidecar = path + u".vertical.json"
        with io.open(sidecar, "w", encoding="utf-8") as handle:
            handle.write(u"%s" % json.dumps(values or self.SENTINEL))
        return sidecar, open(sidecar, "rb").read()

    def test_a_refusal_leaves_the_values_file_as_it_was(self):
        """Review: the values file was written before the font was read and its em checked, so a refusal
        (another em, a file that is not a font) replaced the values an earlier use had left there."""
        path = self.exported()
        folder = os.path.dirname(path)
        sidecar, before = self.sentinel(path)
        listed = sorted(os.listdir(folder))
        self.dialog(self.package(2048.0)).add_metrics_to_export(path)
        self.assertEqual([kind for kind, _ in self.logged], ["error"], self.logged)
        self.assertEqual(open(sidecar, "rb").read(), before)
        not_a_font = os.path.join(folder, u"notes.ttf")
        with open(not_a_font, "wb") as handle:
            handle.write(b"not a font")
        other, other_before = self.sentinel(not_a_font)
        self.dialog(self.package()).add_metrics_to_export(not_a_font)
        self.assertEqual([kind for kind, _ in self.logged], ["error"], self.logged)
        self.assertEqual(open(other, "rb").read(), other_before)
        self.assertEqual(sorted(os.listdir(folder)), sorted(listed + [u"notes.ttf", u"notes.ttf.vertical.json"]),
                         "nothing else written")

    def test_a_failed_copy_writes_neither_file(self):
        path = self.exported()
        folder = os.path.dirname(path)
        sidecar, before = self.sentinel(path, dict(self.SENTINEL, family=u"Test", master=u"Regular", upm=1000))
        listed = sorted(os.listdir(folder))
        real = cv.load_metrics_script

        def broken():
            script = real()

            def save_with_tables(font, source, out):
                with open(out, "wb") as handle:
                    handle.write(b"half a font")
                raise IOError("the disk is full")
            script.save_with_tables = save_with_tables
            return script
        cv.load_metrics_script = broken
        try:
            self.dialog(self.package()).add_metrics_to_export(path)
        finally:
            cv.load_metrics_script = real
        self.assertEqual([kind for kind, _ in self.logged], ["error"], self.logged)
        self.assertIn(u"the disk is full", self.logged[0][1])
        self.assertEqual(open(sidecar, "rb").read(), before, "this master's values as they were")
        self.assertEqual(sorted(os.listdir(folder)), listed, "no copy, no staged file left")

    def test_another_masters_values_are_kept(self):
        """A values file of another font or master is never replaced: this one's go to the next free name."""
        path = self.exported()
        sidecar, before = self.sentinel(path)
        self.dialog(self.package()).add_metrics_to_export(path)
        self.assertEqual([kind for kind, _ in self.logged], ["done", "warning"], self.logged)
        self.assertEqual(open(sidecar, "rb").read(), before)
        second = path + u".vertical-2.json"
        self.assertEqual(json.load(io.open(second, encoding="utf-8"))["master"], u"Regular")
        self.assertIn(u"test.ttf.vertical-2.json", self.logged[0][1])
        self.assertIn(u"--values", self.logged[0][1])
        self.assertIn(u"test.ttf.vertical.json", self.logged[1][1])
        self.dialog(self.package()).add_metrics_to_export(path)  # (the same master again: its own file replaced)
        self.assertEqual([kind for kind, _ in self.logged], ["done", "warning"], self.logged)
        self.assertIn(u"test.ttf.vertical-2.json", self.logged[0][1])
        self.assertFalse(os.path.exists(path + u".vertical-3.json"))
        self.assertEqual(open(sidecar, "rb").read(), before)


class ProgressTests(unittest.TestCase):
    """Long work under a progress bar (the owner: about 13 s without one adding vertical metrics), in the
    window's top row since owner's images 176 and 180 (ak.busy_*: its own bar under the settings before)."""

    class Widget(object):
        def __init__(self):
            self.visible, self.enabled, self.value, self.text, self.repaints = False, True, 0, u"", 0

        def repaint(self):
            self.repaints += 1

        def setVisible(self, on):
            self.visible = on

        def setEnabled(self, on):
            self.enabled = on

        def setValue(self, value):
            self.value = value

        def setText(self, text):
            self.text = text

        def setStyleSheet(self, sheet):
            pass

        def blockSignals(self, on):
            pass

        def clear(self):
            pass

    def dialog(self, stop_after=None):
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        widget = self.Widget
        self.top = TopRow(stop_after)
        dialog.ak = type("Ak", (), dict(enable=staticmethod(lambda w, on: w.setEnabled(bool(on))), LOG_COLORS={},
                                        history_mark=staticmethod(lambda package: "mark"), **self.top.members()))
        dialog.tree, dialog.write_button, dialog.export_button = widget(), widget(), widget()
        dialog.package = None
        self.restored = []
        dialog.show_font_parts = lambda on: self.restored.append("parts")
        dialog.update_buttons = lambda: self.restored.append("buttons")
        dialog.update_put_back = lambda: self.restored.append("put back")
        return dialog

    def test_each_step_has_its_share_and_the_bar_ends_full(self):
        for steps in (cv.LIST_STEPS, cv.SHOW_STEPS, cv.WRITE_STEPS, cv.EXPORT_STEPS, cv.CFF_EXPORT_STEPS):
            ends = [end for _, end in steps]
            self.assertEqual(ends, sorted(ends))
            self.assertEqual(ends[-1], 1.0)
            self.assertEqual(len(set(label for label, _ in steps)), len(steps))
        self.assertEqual(cv.bar_value(cv.EXPORT_STEPS, cv.VALUES_STEP), 0.0)
        self.assertAlmostEqual(cv.bar_value(cv.EXPORT_STEPS, u"Measuring the glyphs", 0.5), (0.14 + 0.95) / 2)
        self.assertAlmostEqual(cv.bar_value(cv.EXPORT_STEPS, cv.CHECK_STEP, 2.0), 1.0, msg="a part past its end")
        self.assertIsNone(cv.bar_value(cv.LIST_STEPS, cv.SAVE_STEP))
        for label in cv.SCRIPT_STEPS.values():
            self.assertIsNotNone(cv.bar_value(cv.EXPORT_STEPS, label), "add_tables' own steps on the bar")
        for label, _ in cv.LIST_STEPS:
            self.assertIsNotNone(cv.bar_value(cv.WRITE_STEPS, label), "the list read again at a write's end")
        self.assertIsNotNone(cv.bar_value(cv.WRITE_STEPS, cv.COMPILE_STEP), "the compile on the bar too")

    def test_a_write_shows_the_bar_at_once_and_moves_it(self):
        dialog = self.dialog()
        dialog.set_busy(True, cv.EXPORT_STEPS, at_once=True)
        self.assertTrue(dialog.busy)
        self.assertEqual(self.top.calls[0], ("start", cv.VALUES_STEP, True), "in the top row at once")
        self.assertFalse(any(w.enabled for w in (dialog.tree, dialog.write_button, dialog.export_button)))
        dialog.progress(u"Measuring the glyphs", 0.5)
        self.assertEqual(self.top.last(), ("progress", u"Measuring the glyphs",
                                           cv.bar_value(cv.EXPORT_STEPS, u"Measuring the glyphs", 0.5), True))
        dialog.progress(cv.SAVE_STEP)
        self.assertAlmostEqual(self.top.last()[2], 0.96, msg="where building the tables ends")
        dialog.set_busy(False)
        self.assertFalse(dialog.busy)
        self.assertEqual(self.top.kinds()[-1], "end")
        self.assertTrue(dialog.tree.enabled)
        self.assertEqual(self.restored, ["parts", "buttons", "put back"], "each control as the font wants it")
        dialog.set_busy(True, cv.WRITE_STEPS, at_once=True, stoppable=False)
        self.assertEqual(self.top.last("start"), ("start", cv.UNDO_STEP, False), "a write never stops half way")
        dialog.progress(cv.BUILD_STEP)
        self.assertFalse(self.top.last()[3])
        dialog.set_busy(False)

    def test_a_quick_list_sets_the_buttons_and_a_font_without_cjk_grays_them(self):
        """The live pass, on Noto Sans: Write and Restore suggestions stayed clickable over an empty list, left as
        the font before had them (a list read quickly shows no bar, and the buttons it held off were never set
        again). A font with no CJK glyph has every button that acts on the list grayed, and the export's."""
        dialog = self.dialog()
        del dialog.update_buttons  # (the real one)
        for name in ("all_button", "none_button", "restore_button", "export_button", "compile_box"):
            setattr(dialog, name, self.Widget())
        dialog.harvest = dialog.draw_previews = lambda: None
        dialog.forms, dialog.turned, dialog.trims, dialog.kerns, dialog.metrics, dialog.first_checks = [], [], [], [], [], []
        dialog.pending = lambda: ({"vert": u"code"}, [], [])  # (what a write would change)
        dialog.cjk = False
        dialog.set_busy(True, cv.LIST_STEPS)
        dialog.update_buttons()  # (held off while the list is read)
        self.assertTrue(dialog.write_button.enabled, "as the font before left it")
        dialog.set_busy(False)
        self.assertEqual(self.top.calls, [], "a quick list: no bar")
        self.assertEqual([getattr(dialog, name).enabled for name in ("all_button", "none_button", "restore_button",
                                                                     "write_button", "export_button", "compile_box")],
                         [False] * 6, "set once the list is read: nothing to act on")
        dialog.cjk = True
        dialog.update_buttons()
        self.assertTrue(dialog.write_button.enabled, "a CJK font's change: Write")
        self.assertTrue(dialog.compile_box.enabled, "and its compile, with it (owner's image 195)")
        dialog.pending = lambda: ({}, [], [])  # (nothing to write)
        dialog.update_buttons()
        self.assertEqual((dialog.write_button.enabled, dialog.compile_box.enabled), (False, False),
                         "Compile after writing grayed with the write button")

    def test_a_quick_list_never_shows_the_bar(self):
        dialog = self.dialog()
        dialog.set_busy(True, cv.LIST_STEPS)
        dialog.progress(cv.LIST_STEP, 0.5)
        self.assertEqual(self.top.calls, [])
        self.assertTrue(dialog.tree.enabled)
        dialog.busy_since -= cv.SHOW_AFTER + 0.01  # (as if it had taken that long)
        dialog.progress(cv.LIST_STEP, 0.6)
        self.assertEqual(self.top.kinds(), ["start", "progress"])
        self.assertTrue(self.top.calls[0][2], "a listing is stoppable")
        self.assertAlmostEqual(self.top.last()[2], 0.6 + 0.35 * 0.6)
        self.assertFalse(dialog.tree.enabled)
        dialog.set_busy(False)
        self.assertEqual(self.top.kinds()[-1], "end")

    def test_a_stopped_listing_leaves_the_list_empty_with_a_link(self):
        dialog = self.dialog(stop_after=0)
        dialog.cj = cv.spacing()
        dialog.status = self.Widget()
        dialog.forms = [object()]

        def read_font():
            dialog.busy_since -= cv.SHOW_AFTER + 0.01
            dialog.progress(cv.READ_STEP, 0.5)
            self.fail("stopped at its first step")
        dialog.read_font = read_font
        dialog.run()
        self.assertEqual(self.top.kinds(), ["start", "progress", "end"])
        self.assertEqual(dialog.forms, [])
        self.assertIn(u"Listing was stopped", dialog.status.text)
        self.assertIn(dialog.cj.LIST_AGAIN, dialog.status.text)
        self.assertEqual(dialog.seen_history, "mark", "not read again for the History seen before")
        self.assertFalse(dialog.busy)
        runs = []
        dialog.run = lambda: runs.append(1)
        dialog.status_link(dialog.cj.LIST_AGAIN)
        self.assertEqual(runs, [1], "the link lists it again")

    def test_the_list_read_during_work_waits_for_it(self):
        dialog = self.dialog()
        reads = []
        dialog.read_font = lambda: reads.append(dialog.busy)
        dialog.run()
        self.assertEqual(reads, [True], "read under the bar")
        self.assertFalse(dialog.busy)
        dialog.set_busy(True, cv.EXPORT_STEPS, at_once=True)
        dialog.run()
        self.assertEqual(reads, [True], "not in the middle of the work")
        self.assertTrue(dialog.run_due)
        import qtfakes
        qtfakes.install()
        self.addCleanup(qtfakes.uninstall)
        shots = []
        sys.modules["PythonQt.QtCore"].QTimer = type("T", (), {"singleShot": staticmethod(lambda ms, f: shots.append(f))})
        dialog.set_busy(False)
        self.assertFalse(dialog.run_due)
        self.assertEqual(len(shots), 1, "once the work is over")
        dialog.write()
        dialog.add_metrics_to_export(u"x.otf")
        self.assertEqual(reads, [True], "no font: nothing")

    def test_the_export_step_goes_through_its_steps(self):
        import qtfakes
        qtfakes.install()
        self.addCleanup(qtfakes.uninstall)
        dialog = self.dialog()
        seen = []
        dialog.progress = lambda label, part=0.0: seen.append(label)
        dialog.package = object()
        dialog.add_metrics_to = lambda path: [dialog.progress(label) for label, _ in cv.EXPORT_STEPS]
        dialog.busy = True
        dialog.add_metrics_to_export(u"x.otf")
        self.assertEqual(seen, [], "busy: a second click does nothing")
        dialog.busy = False
        dialog.add_metrics_to_export(u"x.otf")
        self.assertEqual(seen, [label for label, _ in cv.EXPORT_STEPS])
        self.assertFalse(dialog.busy)

    def test_no_bar_of_its_own(self):
        """Owner's image 180: its own bar under the settings ("Listing..."); the top row's now."""
        with io.open(os.path.join(HERE, os.pardir, "cjk", "freelab_cjk_vertical.py"), encoding="utf-8") as handle:
            source = handle.read()
        for gone in (u"QProgressBar()", u"processEvents", u"ExcludeUserInputEvents", u"self.busy_row"):
            self.assertNotIn(gone, source)


class PreviewLayoutTests(unittest.TestCase):
    """Owner's image 181 (07LightNovelPOP): the previews cut some glyphs at the bottom of a column. The font's
    own values are sane (VORG and typographic ascender 860, the ideographs' ink -110 to 833 in a 1000 em, every
    advance height 1000); the pictures were as tall as their squares alone, and the glyphs sat lower in them
    than the font has them, from an origin read higher than its own."""

    def test_the_ink_past_the_squares_is_measured(self):
        boxes = [((50.0, -110.0, 950.0, 833.0), 0, 0)]
        self.assertEqual(cv.ink_overflow(boxes, 860.0, 1000.0), (0.0, 0.0), "the font's own origin: inside")
        above, below = cv.ink_overflow(boxes, 1060.0, 1000.0)
        self.assertEqual((above, below), (0.0, 170.0), "an origin 200 too high: 170 units under the last square")
        above, below = cv.ink_overflow([((50.0, -110.0, 950.0, 900.0), -100, 0)], 860.0, 1000.0)
        self.assertEqual(above, 0.0)
        self.assertEqual(below, 70.0, "placed lower by vpal (y placement -100)")
        self.assertEqual(cv.ink_overflow([((0.0, 0.0, 10.0, 950.0), 0, 0), (None, 0, 0)], 860.0, 1000.0), (90.0, 0.0))

    def test_a_column_leaves_room_for_its_ink(self):
        chars = list(u"天地玄黄宇宙洪荒日月")
        heights_at = lambda em: [em] * len(chars)
        tight = cv.fitting_em(chars, heights_at, 1000, 248, 40)
        roomy = cv.fitting_em(chars, heights_at, 1000, 248, 40, extra=0.5)
        self.assertEqual(tight, 40)
        self.assertEqual(roomy, 40, "wide enough: the same em, the columns shorter")
        narrow = cv.fitting_em(chars, heights_at, 150, 248, 40)
        self.assertLessEqual(cv.fitting_em(chars, heights_at, 150, 248, 40, extra=0.5), narrow)

    def test_an_origin_off_the_glyphs_ink_is_taken_from_the_fonts_ascender(self):
        boxes = [(53, -83, 947, 773), (40, -79, 973, 809), (52, -83, 965, 833), (128, -78, 872, 784),
                 (104, -78, 907, 808)]  # (07LightNovelPOP's, from the font file)
        self.assertEqual(cv.origin_from_ink(860.0, boxes, 1000.0, 1000.0), (860.0, False), "its own: kept")
        self.assertEqual(cv.origin_from_ink(880.0, boxes, 1000.0, 1000.0), (880.0, False), "within the slack: kept")
        # (FontLab's typographic ascender 1048, the font's ascender 860)
        self.assertEqual(cv.origin_from_ink(1048.0, boxes, 1000.0, 1000.0, others=(860.0,)), (860.0, True))
        # (review 12: never a value of its own: with no other value of the font's that centers them, kept)
        self.assertEqual(cv.origin_from_ink(1048.0, boxes, 1000.0, 1000.0), (1048.0, False))
        self.assertEqual(cv.origin_from_ink(1048.0, boxes, 1000.0, 1000.0, others=(1040.0,)), (1048.0, False))
        self.assertEqual(cv.origin_from_ink(1048.0, boxes[:2], 1000.0, 1000.0, others=(860.0,)), (1048.0, False),
                         "too few to tell")



class SourceTests(unittest.TestCase):
    def source(self, *parts):
        with io.open(os.path.join(HERE, os.pardir, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_one_history_step_begun_by_before_changes(self):
        text = self.source("cjk", "freelab_cjk_vertical.py")
        self.assertEqual(len(re.findall(r"(?<!def )before_changes\(self\.fontlab", text)), 1)
        self.assertEqual(len(re.findall(r"notify_changed\(self\.fontlab, package, TITLE", text)), 1)

    def test_in_the_menu_and_the_installer_and_the_gate(self):
        self.assertIn(u"\"CJK Spacing\", \"CJK Vertical\"", self.source("kerning", "freelab_auto_kerning.py"))
        if sys.version_info[0] < 3:
            return  # the 2.7 run copies only the files it runs; Python 3 checks the installer and the gate
        installer = self.source("tools", "install-fontlab.ps1")
        self.assertIn(u"cjk\\freelab_cjk_vertical.py", installer)
        self.assertIn(u"cjk\\vertical_model.json", installer)
        self.assertIn(u"tools\\add_vertical_metrics.py'; Name = 'add_vertical_metrics.module'", installer)
        gate = self.source("tests", "run_tests.py")
        self.assertIn(u'"cjk/freelab_cjk_vertical.py"', gate)
        self.assertIn(u'"tests/cjk_vertical_tests.py"', gate)

    def test_the_tool_says_fontlab_exports_no_vertical_tables(self):
        """Live: FontLab 7's export wrote no vhea, vmtx, or VORG, whatever was set; the tool says so."""
        text = self.source("cjk", "freelab_cjk_vertical.py")
        self.assertIn(u"export writes no vhea, vmtx, or VORG", cv.EXPORT_NOTE)
        self.assertIn(u"self.log.add(EXPORT_NOTE", text)
        self.assertIn(u"FontLab 7's export writes no vhea, vmtx, or VORG table", u" ".join(cv.HELP.split()))

    def test_wording(self):
        """Counts follow their number; parentheses, not dashes or dots, between data; FreeLab says glyph."""
        self.assertEqual([cv.counted(n, u"vertical form") for n in (0, 1, 2)],
                         [u"0 vertical forms", u"1 vertical form", u"2 vertical forms"])
        self.assertEqual(cv.counted(9507, u"layer"), u"9,507 layers")
        text = self.source("cjk", "freelab_cjk_vertical.py")
        for mark in (u" \\N{EM DASH} ", u" \\N{MIDDLE DOT} ", u" \N{EM DASH} ", u" \N{MIDDLE DOT} "):
            self.assertNotIn(mark, text)
        self.assertNotIn(u"%d units", text)
        interface = text.split(u"# FontLab\n")[-1]
        self.assertNotIn(u" letter", interface.lower(), "the interface says glyph")

    def test_previews_have_a_line_between_and_quiet_captions(self):
        # (owner's image 219: CJK Spacing's previews have a line between them, these did not; brief: the shared
        # preview_caption for every preview's caption; image 261: Tick, not Check)
        text = self.source("cjk", "freelab_cjk_vertical.py")
        init = text.split(u"class CJKVerticalDialog")[1].split(u"\n    def watch_previews")[0]
        previews = init.split(u"previews = QtGui.QHBoxLayout()")[1].split(u"layout.addLayout(previews)")[0]
        self.assertIn(u"previews.addWidget(ak.separator(vertical=True))", previews)
        self.assertIn(u"ak.preview_caption(caption)", previews)
        self.assertIn(u"layout.addWidget(ak.header_separator())", init)
        self.assertEqual(cv.PREVIEW_CAPTIONS, (u"Now (the font's own code)", u"With what is ticked"))
        for old in (u'"Check all"', u'"Check none"', u"Checks restored", u"what is checked", u"Checked rows",
                    u"left unchecked"):
            self.assertNotIn(old, text)
        # (a tool named in the log is a link that opens it: owner's image 220)
        self.assertIn(u'self.ak.tool_link(u"Feature Check")', text)
        self.assertNotIn(u"<i>Feature Check</i> lists", text)

    def test_the_top_line_names_the_font_then_counts_what_is_there(self):
        # (owner's images 223 and 238: one font line for every window; brief: no "0 drawn already")
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        dialog.ak = type("Ak", (), dict(b=staticmethod(lambda t: u"<b>%s</b>" % t), i=staticmethod(lambda t: u"<i>%s</i>" % t),
                                        joined=staticmethod(lambda items: u", ".join(items)),
                                        font_named=staticmethod(lambda name, master=None, masters=1:
                                                                u"<b>%s</b>, master <b>%s</b>" % (name, master))))
        dialog.cj = cv.spacing()
        form = lambda state: type("Form", (), {"state": state})()
        dialog.forms, dialog.trims, dialog.kerns = [form("build"), form("build"), form("font")], [1], []
        dialog.own_vkrn, dialog.own_vpal, dialog.cjk = set(), set(), True
        package = type("Package", (), {"tfn": u"Fake Sans", "master": u"Regular", "mastersCount": 1})()
        self.assertEqual(dialog.status_text(package, u"Regular"),
                         u"<b>Fake Sans</b>, master <b>Regular</b>. <b>2 vertical forms</b> to build, <b>1</b> the font's "
                         u"own code makes, <b>1 vpal trim</b>. Nothing is written until you click <i>Write</i>.")
        dialog.forms = [form("glyph")]
        self.assertIn(u"master <b>Regular</b>. <b>1 vertical form</b> drawn already, <b>1 vpal trim</b>.",
                      dialog.status_text(package, u"Regular"), "the noun on the first count said")


class NoFontTests(unittest.TestCase):
    class Widget(object):
        def __init__(self):
            self.visible = self.enabled = True

        def setVisible(self, on):
            self.visible = on

        def setEnabled(self, on):
            self.enabled = on

    def test_with_no_font_the_sample_and_previews_are_hidden_and_the_settings_grayed(self):
        dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)
        dialog.ak = type("Ak", (), {"enable": staticmethod(lambda widget, on: widget.setEnabled(bool(on)))})
        widget = self.Widget
        dialog.sample_label, dialog.sample_box, dialog.sample = widget(), widget(), widget()
        dialog.preview_captions, dialog.previews = [widget(), widget()], [widget(), widget()]
        dialog.forms_box, dialog.vpal_box, dialog.metrics_box, dialog.compile_box = widget(), widget(), widget(), widget()
        dialog.vkrn_box, dialog.turned_box, dialog.export_button = widget(), widget(), widget()
        dialog.show_font_parts(False)
        shown = [dialog.sample_label, dialog.sample_box, dialog.sample] + dialog.preview_captions + dialog.previews
        self.assertFalse(any(w.visible for w in shown))
        self.assertFalse(any(w.enabled for w in (dialog.forms_box, dialog.vpal_box, dialog.metrics_box, dialog.compile_box,
                                                 dialog.vkrn_box, dialog.turned_box)))
        dialog.show_font_parts(True)
        self.assertTrue(all(w.visible for w in shown))
        runs = []
        dialog.run = lambda: runs.append(1)
        dialog.font_changed()
        self.assertEqual(runs, [1])


class PreviewNoteTests(unittest.TestCase):
    def test_the_note_says_what_the_previews_show(self):
        """Owner's report 148: on Bellefair (no CJK glyph), the Korean sample's previews showed a comma and a
        period only, and nothing said why: a line under the previews says what they show, and what the font
        lacks (its Hangul, its CJK punctuation, named)."""
        import freelab_cjk_spacing
        korean = [s for s in freelab_cjk_spacing.SAMPLES if s[0] == "ko"][0][2]  # (the sample the owner saw)
        names = {0x2C: u"comma", 0x2E: u"period"}
        syllables = sum(1 for ch in korean if 0xAC00 <= ord(ch) <= 0xD7A3)
        self.assertEqual(cv.preview_note(korean, names),
                         u"The previews show only the 2 characters of the sample the font has (the comma and the period): it lacks %d Hangul "
                         u"syllables and 2 CJK punctuation marks (the left corner bracket and the right corner bracket)." % syllables)
        self.assertEqual(cv.preview_note(u"あ, x", {0x2C: u"comma"}),
                         u"The previews show only the 1 character of the sample the font has (the comma): it lacks 1 kana and "
                         u"1 other character.")
        self.assertEqual(cv.preview_note(u"一、", {}),
                         u"The font has none of the sample's characters, so the previews are empty: it lacks 1 ideograph "
                         u"and 1 CJK punctuation mark (the ideographic comma).")
        self.assertEqual(cv.preview_note(u"あ い", {0x3042: u"a", 0x3044: u"i"}), u"", "all there: nothing to say")
        # Live pass: "(, .)" read oddly; marks by their names, anything else quoted
        self.assertEqual(cv.character_words(u"a,.a"), u"“a”, the comma, and the period")
        self.assertEqual(cv.character_words(u"abcdefgh", 2), u"“a”, “b”, and others")


class ReaderAndRemovalTests(unittest.TestCase):
    def test_no_reader_writes_nothing_and_says_why(self):
        """Codex review 7, finding 3: without Feature Code's reader, the writer raised; now it writes nothing,
        and the window's write refuses and says to reinstall FreeLab."""
        cj = cv.spacing()
        saved = cj.feature_code_or_none
        cj.feature_code_or_none = lambda: None
        cj.FEATURE_CODE_ERROR[:] = [u"no such file"]
        try:
            self.assertIsNone(cv.feature_text("vert", u"feature vert { sub a by b; } vert;", [u"sub x by x.vert;"]))
            self.assertIsNone(cv.block_of("vert", u""))
            dialog = cv.CJKVerticalDialog.__new__(cv.CJKVerticalDialog)  # (its window needs FontLab)
            logged = []
            dialog.package, dialog.busy = object(), False
            dialog.ak = type("Ak", (), {"html": staticmethod(lambda text: text)})()
            dialog.log = type("Log", (), {"add": lambda _, text, kind=None: logged.append((kind, text))})()
            dialog.harvest = lambda: self.fail("nothing read before the refusal")
            dialog.write()
            self.assertEqual([kind for kind, _ in logged], ["error"])
            self.assertIn(u"Reinstall FreeLab", logged[0][1])
        finally:
            cj.feature_code_or_none = saved
            del cj.FEATURE_CODE_ERROR[:]

    def test_taking_a_block_out_checks_the_braces_too(self):
        """Codex review 7, finding 4: a write that only took FreeLab's block out returned an unclosed "lookup
        Own {"; refused now, as a write that adds one is."""
        cj = cv.spacing()
        for write, tag, begin, end in ((cv.feature_text, "vert", cv.BEGIN % "vert", cv.END % "vert"),
                                       (cj.feature_text, "palt", cj.BEGIN % "palt", cj.END % "palt")):
            for old in (u"lookup Own {\n%s\nsub a by a.alt;\n%s" % (begin, end),
                        u"feature %s {\n%s\nsub a by a.alt;\n%s\n" % (tag, begin, end)):
                for rules in ([], [u"sub x by y;"]):
                    self.assertIsNone(write(tag, old, rules), (tag, old, rules))


class TokenReadingTests(unittest.TestCase):
    def test_codex_review_6_scenarios(self):
        """Markers found as comments wherever they stand, never past their pair; another feature's code is no
        body; a body's braces must balance (Feature Code's writer_scenarios, through its token functions)."""
        sys.path.insert(0, HERE)
        import features_tests
        features_tests.writer_scenarios(self, lambda old, rules: cv.feature_text("vert", old, rules), u"vert",
                                        cv.BEGIN % "vert", cv.END % "vert", u"sub x by x.vert;")
        own = u"feature vert {\n%s\nsub b by b.vert; %s\nsub c by c.vert;\n} vert;" % (cv.BEGIN % "vert", cv.END % "vert")
        self.assertEqual(cv.freelab_substitutions("vert", own), {u"b": u"b.vert"}, "FreeLab's own, up to its end marker")


class CheckAllTests(unittest.TestCase):
    def test_check_all_and_none_say_how_many(self):
        """Owner's report 118: Check all and Check none left no line in the log."""
        sys.path.insert(0, HERE)
        import cjk_tests
        cjk_tests.check_all_logged(self, cv, cv.CJKVerticalDialog, u"row")


if __name__ == "__main__":
    unittest.main()
