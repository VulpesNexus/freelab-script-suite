"""Tests of FreeLab's Diacritics (planning and placing marks) and feature code (ligatures and
alternates that take turns). Valid Python 2.7 and Python 3; the feature parser's checks run where
fontTools is installed."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "diacritics"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_diacritics as ac  # noqa: E402
import freelab_feature_code as fc  # noqa: E402

try:
    import fontTools.feaLib.parser  # noqa: F401
    HAVE_FONTTOOLS = True
except Exception:
    HAVE_FONTTOOLS = False

A_CARON, I_CARON, CAP_A_CARON = ac.unichr_(0x01CE), ac.unichr_(0x01D0), ac.unichr_(0x01CD)
A_DOT_BELOW, O_CIRCUMFLEX_ACUTE, O_HORN_DOT = ac.unichr_(0x1EA1), ac.unichr_(0x1ED1), ac.unichr_(0x1EE3)


def font():
    return ac.Font(["a", "acaron", "i", "dotlessi", "caron", "acute", "caron.case", "A", "dotaccent", "I", "o",
                    "circumflex", "e"],
                   [("a", 0x61), ("i", 0x69), ("dotlessi", 0x131), ("A", 0x41), ("I", 0x49), ("o", 0x6F), ("e", 0x65)])


class PlanTests(unittest.TestCase):
    def test_recipes(self):
        found = dict((r.char, r) for r in ac.plan(font(), [A_CARON, I_CARON, CAP_A_CARON, A_DOT_BELOW,
                                                          O_CIRCUMFLEX_ACUTE, O_HORN_DOT, u"a"]))
        self.assertNotIn(u"a", found, "a character the font has")
        self.assertEqual(found[A_CARON].name, u"uni01CE", "acaron is another glyph's name already")
        self.assertEqual(found[I_CARON].base, "dotlessi", "a mark above takes the dotless i")
        self.assertEqual(found[I_CARON].name, u"icaron", "named after the letter, not its dotless form")
        self.assertEqual(found[CAP_A_CARON].marks[0].glyph, "caron.case", "a capital takes the .case mark")
        dot = found[A_DOT_BELOW].marks[0]
        self.assertEqual((dot.glyph, dot.side, dot.note), ("dotaccent", "below", u"for dotbelow"), "its twin above")
        self.assertEqual([m.glyph for m in found[O_CIRCUMFLEX_ACUTE].marks], ["circumflex", "acute"])
        self.assertTrue(found[O_HORN_DOT].missing and u"horn" in found[O_HORN_DOT].missing)

    def test_a_bare_font_drafts_its_marks_from_punctuation(self):
        bare = ac.Font(["a", "o", "period", "asciicircum", "hyphen", "comma"],
                       [("a", 0x61), ("o", 0x6F), ("period", 0x2E), ("asciicircum", 0x5E), ("hyphen", 0x2D),
                        ("comma", 0x2C)])
        found = dict((r.char, r) for r in ac.plan(bare, [A_CARON, ac.unichr_(0xE4), A_DOT_BELOW, ac.unichr_(0x14D),
                                                        ac.unichr_(0xE1)]))
        caron = found[A_CARON].marks[0]
        self.assertEqual((caron.glyph, caron.parts[0][2] < 0, caron.note), ("asciicircum", True, u"draft for caron"),
                         "a caron of an upside-down ^")
        self.assertEqual([p[0] for p in found[ac.unichr_(0xE4)].marks[0].parts], ["period", "period"], "a dieresis of two periods")
        self.assertEqual(found[A_DOT_BELOW].marks[0].glyph, "period")
        self.assertEqual(found[ac.unichr_(0x14D)].marks[0].glyph, "hyphen", "a macron of the hyphen")
        self.assertTrue(found[ac.unichr_(0xE1)].missing, "no acute to draft from")


MODEL = {"format": 1,
         "gap": {"acute lower": 0.05, "acute upper": 0.05, "circumflex lower": 0.05, "dotaccent upper": 0.06},
         "side_gap": {"above lower": 0.05, "above upper": 0.05, "below lower": 0.04},
         "side_offset": {"above lower": 0.0, "above upper": 0.0},
         "offset": {"b above *": 0.43, "Y above *": 0.02},
         "pair_gap": {"circumflex+acute lower": -0.016}, "pair_offset": {"circumflex+acute lower": 0.44},
         "stack_gap": {"above lower": 0.025}, "height": {"dotaccent lower": 0.11, "dotaccent upper": 0.11}}


def inks():
    return {"b": ac.Ink(50, 0, 450, 700, top_center=70, advance=500),
            "o": ac.Ink(40, -10, 460, 480, advance=500),
            "Y": ac.Ink(10, 0, 590, 700, advance=600),
            "acute": ac.Ink(0, 500, 100, 600), "circumflex": ac.Ink(0, 500, 200, 600),
            "period": ac.Ink(0, 0, 100, 100), "dotaccent": ac.Ink(0, 500, 100, 600)}


class ScriptTests(unittest.TestCase):
    """Greek and Cyrillic: the script's own marks, the tonos at a capital's left, joined marks, names."""

    def setUp(self):
        self.font = ac.Font(["Alpha", "alpha", "iota", "tonos", "dieresis", "dieresistonos", "ii-cy", "brevecomb-cy",
                             "breve", "i-cy", "dotlessi", "acute"],
                            [("Alpha", 0x391), ("alpha", 0x3B1), ("iota", 0x3B9), ("tonos", 0x384),
                             ("dieresis", 0xA8), ("dieresistonos", 0x385), ("ii-cy", 0x438), ("i-cy", 0x456),
                             ("dotlessi", 0x131), ("breve", 0x2D8), ("acute", 0xB4)])
        self.names = {0x386: u"Alphatonos", 0x3AC: u"alphatonos", 0x439: u"iishort-cy", 0x390: u"iotadieresistonos"}

    def plan(self, codes):
        saved = ac._NAMES.copy()
        try:
            ac._NAMES.clear()
            ac._NAMES[os.path.join(os.path.dirname(os.path.abspath(ac.__file__)), ac.NAMES_FILE)] = self.names
            return dict((r.code, r) for r in ac.plan(self.font, [ac.unichr_(code) for code in codes]))
        finally:
            ac._NAMES.clear()
            ac._NAMES.update(saved)

    def test_greek_takes_its_tonos_at_a_capitals_left(self):
        found = self.plan([0x386, 0x3AC])
        capital, small = found[0x386], found[0x3AC]
        self.assertEqual((capital.marks[0].glyph, capital.marks[0].side), ("tonos", "left"))
        self.assertEqual((small.marks[0].glyph, small.marks[0].side), ("tonos", "above"))
        self.assertEqual((capital.name, small.name), (u"Alphatonos", u"alphatonos"), "Glyphs' names")
        ink = {"Alpha": ac.Ink(10, 0, 600, 700, advance=620), "tonos": ac.Ink(0, 520, 80, 720)}.get
        parts, width = ac.place(capital, ink, ac.Placement(1000, MODEL))
        alpha, tonos = parts
        self.assertEqual(width, 620 + alpha[3], "wider by as much as the letter moved right")
        self.assertLessEqual(tonos[3] + 80, alpha[3] + 10 - 25, "the tonos left of the letter, a gap between")
        self.assertEqual(tonos[3], 10, "the tonos keeps the letter's left sidebearing")
        self.assertEqual(tonos[4] + 720, 700, "its top level with the capital's")

    def test_greek_joins_dialytika_and_tonos(self):
        self.assertEqual([m.glyph for m in self.plan([0x390])[0x390].marks], ["dieresistonos"], "the font's glyph for both")
        self.font.names.discard("dieresistonos")
        del self.font.by_code[0x385]
        joined = self.plan([0x390])[0x390].marks[0]
        self.assertTrue(joined.joined)
        self.assertEqual([p[0] for p in joined.parts], ["dieresis", "tonos"], "else its two marks, over each other")
        box, laid = ac.mark_ink(joined, {"dieresis": ac.Ink(0, 500, 200, 560), "tonos": ac.Ink(0, 520, 60, 700)}.get,
                                ac.Placement(1000), "lower")
        self.assertEqual((laid[1][3] + 30, laid[1][4] + 520), (100, 500), "the tonos centered on the dots, bottoms level")

    def test_cyrillic_short_i_and_yi(self):
        found = self.plan([0x439, 0x457])
        self.assertEqual(found[0x439].marks[0].glyph, "brevecomb-cy", "Cyrillic's own breve first")
        self.assertEqual(found[0x439].name, u"iishort-cy")
        self.assertEqual(found[0x457].base, "dotlessi", "the Ukrainian i takes the dotless i under its dieresis")

    def test_polytonic(self):
        self.font = ac.Font(["Alpha", "alpha", "omega", "Omega", "psilicomb", "oxia", "perispomeni", "iota",
                             "ypogegrammenicomb", "prosgegrammeni"],
                            [("Alpha", 0x391), ("alpha", 0x3B1), ("omega", 0x3C9), ("Omega", 0x3A9), ("oxia", 0x1FFD),
                             ("perispomeni", 0x1FC0), ("iota", 0x3B9), ("prosgegrammeni", 0x1FBE)])
        self.font.names.add("psilicomb")
        self.font.by_code[0x1FBF] = "psilicomb"  # (found as the psili's spacing form)
        found = self.plan([0x1F04, 0x1F0C, 0x1FB3, 0x1FBC, 0x1F66])
        small = found[0x1F04]  # alpha with psili and oxia
        self.assertEqual([(m.root, m.joined, [p[0] for p in m.parts]) for m in small.marks],
                         [("psilioxia", "beside", ["psilicomb", "oxia"])], "the breathing and its accent side by side")
        self.assertEqual(found[0x1F0C].marks[0].side, "left", "at a capital's left, as one")
        self.assertEqual((found[0x1FB3].marks[0].root, found[0x1FB3].marks[0].side), ("ypogegrammeni", "below"))
        adscript = found[0x1FBC].marks[0]
        self.assertEqual((adscript.glyph, adscript.side), ("prosgegrammeni", "adscript"))
        self.assertEqual([m.joined for m in found[0x1F66].marks], ["stacked"], "omega with psili and perispomeni")
        inks = {"psilicomb": ac.Ink(0, 500, 60, 640), "oxia": ac.Ink(0, 500, 90, 700), "perispomeni": ac.Ink(0, 520, 150, 580),
                "Alpha": ac.Ink(10, 0, 600, 700, advance=620), "prosgegrammeni": ac.Ink(0, 0, 40, 500)}.get
        box, laid = ac.mark_ink(small.marks[0], inks, ac.Placement(1000), "lower")
        self.assertEqual(laid[1][3], 60 + 25, "the oxia 0.025 em after the breathing")
        stacked = found[0x1F66].marks[0]
        box, laid = ac.mark_ink(stacked, inks, ac.Placement(1000), "lower")
        self.assertEqual((laid[1][3] + 75, laid[1][4] + 520), (30, 640 + 25), "centered over the breathing, 0.025 em up")
        parts, width = ac.place(found[0x1FBC], inks, ac.Placement(1000, MODEL))
        self.assertEqual(parts[1][3:], (650, 0), "after the capital, 0.03 em past its width, on the baseline")
        self.assertEqual(width, 620 + 30 + 40 + 10)

    def test_marks_moved_by_hand(self):
        recipe = ac.Recipe(u"x", "xacute", "x", [ac.Mark("acute", "above", [("acute", 1.0, 1.0, 0.0, 0.0)])])
        ink = {"acute": ac.Ink(0, 0, 100, 100)}.get
        parts = [("x", 1.0, 1.0, 0, 0), ("acute", 1.0, 1.0, 200, 500)]
        self.assertEqual(ac.adjusted(recipe, parts, ink), parts, "nothing moved")
        recipe.adjust = {0: [10, -20, 2.0, 0.5]}
        moved = ac.adjusted(recipe, parts, ink)[1]
        self.assertEqual(moved, ("acute", 2.0, 0.5, 160, 505), "scaled about its center (250, 550), then moved")


class AnchorTests(unittest.TestCase):
    MODEL = {"anchors": {"thai top": {"base_gap": -0.06, "base_offset": 0.43, "mark_gap": 0.1, "mark_offset": 0.45,
                                      "mark_to_mark": 0.01},
                         "latin bottom": {"base_gap": 0.0, "base_offset": 0.0, "mark_gap": 0.04, "mark_offset": 0.0,
                                          "mark_to_mark": 0.01}}}

    def plan(self):
        glyphs = [("ko", 0xE01, "base", ac.Ink(50, 0, 550, 500, top_center=300, bottom_center=300), {}),
                  ("maiek", 0xE48, "mark", ac.Ink(-200, 600, -100, 700), {}),
                  ("phinthu", 0xE3A, "mark", ac.Ink(-150, -200, -50, -100), {"_bottom": (-100, 0)}),
                  ("koold", 0, "base", ac.Ink(50, 0, 550, 500), {"top": (1, 2), "bottom": (3, 4)})]
        return dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "thai", 1000, 500))

    def test_bases_and_marks(self):
        found = self.plan()
        ko, maiek, phinthu = found["ko"], found["maiek"], found["phinthu"]
        self.assertEqual(ko.anchors["top"], (515, 440), "right of its top's center, a little under its top, as Thai sets it")
        self.assertEqual(ko.anchors["bottom"], (300, 0), "the corpus's Latin, where Thai has no row")
        self.assertEqual(maiek.side, "top")
        self.assertEqual(maiek.anchors, {u"_top": (-105, 500), u"top": (-105, 710)})
        self.assertEqual(phinthu.side, "bottom")
        self.assertEqual(phinthu.anchors, {u"bottom": (-100, -210)}, "its own _bottom is kept")
        self.assertFalse(found["koold"].checked, "nothing to add")

    def test_mark_code(self):
        found = self.plan()
        found["ko"].adjust["top"] = [5, -10]
        lines = ac.mark_code(list(found.values()))
        self.assertIn(u"markClass maiek <anchor -105 500> @MC_top;", lines["mark"])
        self.assertIn(u"markClass phinthu <anchor -100 0> @MC_bottom;", lines["mark"])
        self.assertIn(u"pos base ko <anchor 300 0> mark @MC_bottom <anchor 520 430> mark @MC_top;", lines["mark"],
                      "moved by hand")
        self.assertIn(u"pos base koold <anchor 3 4> mark @MC_bottom <anchor 1 2> mark @MC_top;", lines["mark"],
                      "a base's own anchors count")
        self.assertIn(u"pos mark maiek <anchor -105 710> mark @MC_top;", lines["mkmk"])
        old = u"\n".join([u"feature mark {", u"#> feature", u"#< feature", u"} mark;", u""])
        texts = ac.mark_texts(list(found.values()), {"mark": old})
        self.assertIn(u"#/> feature", texts["mark"])
        self.assertTrue(texts["mkmk"].startswith(u"feature mkmk {"))
        if HAVE_FONTTOOLS:
            block = u"languagesystem DFLT dflt;\n" + texts["mark"] + texts["mkmk"]
            self.assertIsNone(fc.check_code(block, ["ko", "maiek", "phinthu", "koold"]))


class PlaceTests(unittest.TestCase):
    def test_a_bare_font_places_by_the_model_letter_by_letter(self):
        placement = ac.Placement(1000.0, MODEL)
        b_acute = ac.Recipe(u"x", u"x", "b", [ac.Mark("acute", "above", [("acute", 1.0, 1.0, 0.0, 0.0)])])
        parts, width = ac.place(b_acute, inks().get, placement, letter=u"b")
        self.assertEqual(width, 500)
        glyph, sx, sy, x, y = parts[1]
        self.assertEqual(y, 700 + 50 - 500, "the model's gap above b's ascender")
        self.assertEqual(x + 50, 70 + round(0.43 * 400), "over b's bowl, as the fonts put it, not its stem")

    def test_a_capital_is_centered_whatever_the_fonts_lowercase_habit(self):
        placement = ac.Placement(1000.0, MODEL)
        # the font's own lowercase marks sit far right (a slanted hand): capitals do not inherit that
        placement.learn([("o", [("acute", 300, -10)])] * 3, inks().get, lambda name: "lower")
        dot = ac.Recipe(ac.unichr_(0x1E8E), u"Ydotaccent", "Y", [ac.Mark("dotaccent", "above", [("dotaccent", 1.0, 1.0, 0.0, 0.0)])])
        parts, _ = ac.place(dot, inks().get, placement)
        center = parts[1][3] + 50
        self.assertLess(abs(center - (300 + 0.02 * 580)), 2, "centered on Y, as the fonts put it")

    def test_an_acute_sits_beside_a_circumflex(self):
        placement = ac.Placement(1000.0, MODEL)
        recipe = ac.Recipe(O_CIRCUMFLEX_ACUTE, u"x", "o", [ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)]),
                                                         ac.Mark("acute", "above", [("acute", 1.0, 1.0, 0.0, 0.0)])])
        parts, _ = ac.place(recipe, inks().get, placement)
        circumflex_top = parts[1][4] + 600  # (the circumflex's ink runs from 500 to 600 in its own glyph)
        self.assertEqual(parts[2][4] + 500, circumflex_top - 16, "its bottom a little under the circumflex's top")
        self.assertEqual(parts[2][3] + 50, 250 + round(0.44 * 420), "to the right, as Vietnamese sets it")

    def test_a_stack_too_tall_for_the_line_is_made_compact(self):
        placement = ac.Placement(1000.0, MODEL)
        recipe = ac.Recipe(O_CIRCUMFLEX_ACUTE, u"x", "o", [ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)]),
                                                         ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)])])
        roomy = ac.Metrics(1000, 800, -200)  # room up to 1000
        parts, _ = ac.place(recipe, inks().get, placement, roomy)
        self.assertEqual(recipe.notes, [], "fits as it is")
        tight = ac.Metrics(1000, 600, -500)  # room up to 700
        parts, _ = ac.place(recipe, inks().get, placement, tight)
        self.assertIn(u"gaps closed", recipe.notes[0])
        top = max(p[4] + 600 * p[2] for p in parts[1:])
        self.assertLessEqual(top, 700 + 1)
        self.assertTrue(recipe.checked)
        hopeless = ac.Metrics(1000, 300, -700)  # room up to 500: the letter alone
        ac.place(recipe, inks().get, placement, hopeless)
        self.assertIn(u"too tall", recipe.notes[-1])
        self.assertFalse(recipe.checked, "left unchecked, to draw by hand")

    def test_a_drafted_dot_is_sized_as_marks_are(self):
        placement = ac.Placement(1000.0, MODEL)
        recipe = ac.Recipe(ac.unichr_(0x1E8E), u"Ydotaccent", "Y",
                           [ac.Mark("dotaccent", "above", [("period", 1.0, 1.0, 0.0, 0.0)], u"draft for dotaccent")])
        parts, _ = ac.place(recipe, inks().get, placement)
        self.assertAlmostEqual(parts[1][1], 1.1, 2, "the period at 110%: a dot accent is 0.11 em high")
        self.assertEqual(parts[1][4], 700 + 60, "its bottom the model's gap above Y")

    def test_the_fonts_own_placements_pool_per_case(self):
        placement = ac.Placement(1000.0, MODEL)
        placement.learn([("o", [("acute", 210, -10)]), ("o", [("circumflex", 160, -10)]), ("o", [("acute", 210, -10)])],
                        inks().get, lambda name: "lower")
        self.assertEqual(placement.gap("acute", "above", "lower"), 10, "its own gap, from its own composites")
        breve, caron = (placement.offset(u"i", root, "above", "lower") for root in ("breve", "caron"))
        self.assertEqual(breve, caron, "all marks agree on a letter: the font's habit is pooled")


class RefillTests(unittest.TestCase):
    def test_an_empty_glyph_is_planned_again_under_its_name(self):
        f = ac.Font(["a", "caron", "acaron"], [("a", 0x61), ("acaron", 0x01CE)], empty=["acaron"])
        found = ac.plan(f, [A_CARON])
        self.assertEqual([(r.name, r.refill) for r in found], [("acaron", True)])
        full = ac.Font(["a", "caron", "acaron"], [("a", 0x61), ("acaron", 0x01CE)])
        self.assertEqual(ac.plan(full, [A_CARON]), [], "a drawn glyph is left alone")


class LearnableTests(unittest.TestCase):
    def test_only_composites_their_character_spells(self):
        self.assertTrue(ac.learnable(0xE9, [("e", 0, 0), ("acute", 66, -10)]))
        self.assertTrue(ac.learnable(0x122, [("G", 0, 0), ("commaaccentcomb", 113, -2)]))
        self.assertFalse(ac.learnable(0x13F, [("L", 0, 0), ("dotaccent", 168, -217)]), "a middle dot, not above")
        self.assertFalse(ac.learnable(0xBD, [("two", 0, 0), ("one", 9, 208), ("slash", 129, 143)]), "a fraction")
        self.assertFalse(ac.learnable(0x10F, [("d", 0, 0), ("quoteright", 366, 7)]), "a caron drawn as an apostrophe")
        self.assertFalse(ac.learnable(None, [("e", 0, 0), ("acute", 0, 0)]))

    def test_past_the_basic_plane(self):
        self.assertEqual(len(ac.unichr_(0x1F600)), 1)
        self.assertEqual(len(fc.unichr_(0x1F600)), 1)


class LigatureTests(unittest.TestCase):
    LIGA = u"\n".join([u"feature liga {", u"# Standard Ligatures", u"", u"#> feature",
                       u"  sub parenleft c parenright by copyright;", u"  sub f f by f_f;", u"  sub f f t by f_f_t;",
                       u"#< feature", u"} liga;", u""])
    NAMES = ["f", "t", "c", "l", "f_f", "f_f_t", "l_l.dlig", "parenleft", "parenright", "copyright"]

    def test_the_corpus_places_what_the_font_does_not(self):
        names = ["f", "i", "c", "t", "q", "f_i", "c_t", "q_q"]
        chars = {"f": u"f", "i": u"i", "c": u"c", "t": u"t", "q": u"q"}
        model = {"ligatures": {u"fi": [161, 8], u"ct": [2, 40]}}
        found = dict((l.glyph, l) for l in fc.ligatures(names, {}, chars, model))
        self.assertEqual(found["f_i"].choice, "liga")
        self.assertIn(u"161 of the 169", found["f_i"].why)
        self.assertEqual(found["c_t"].choice, "dlig")
        self.assertEqual(found["q_q"].choice, "dlig", "unknown to the corpus: discretionary")

    def test_found_and_moved(self):
        found = fc.ligatures(self.NAMES, {"liga": self.LIGA})
        self.assertEqual([(l.glyph, l.now, l.choice) for l in found],
                         [("copyright", "liga", "liga"), ("f_f", "liga", "liga"), ("f_f_t", "liga", "liga"),
                          ("l_l.dlig", None, "dlig")])
        found[2].choice = "dlig"  # f_f_t: discretionary
        texts = fc.ligature_texts(found, {"liga": self.LIGA})
        self.assertIn(u"#/> feature", texts["liga"], "FontLab's automatic block handed back")
        self.assertNotIn(u"f_f_t", texts["liga"])
        self.assertIn(u"  sub f f t by f_f_t;", texts["dlig"])
        self.assertIn(u"  sub l l by l_l.dlig;", texts["dlig"])
        self.assertTrue(texts["dlig"].startswith(u"feature dlig {"), "a new feature")
        again = fc.ligature_texts(found, texts)
        self.assertEqual(again, texts, "writing twice changes nothing")
        if HAVE_FONTTOOLS:
            for tag in ("liga", "dlig"):
                self.assertIsNone(fc.check_code(texts[tag], self.NAMES))

    def test_longest_first(self):
        self.assertEqual(fc.rule_lines([(("f", "f"), "f_f"), (("f", "f", "t"), "f_f_t")]),
                         [u"sub f f t by f_f_t;", u"sub f f by f_f;"])


class AlternateTests(unittest.TestCase):
    def test_sets_by_suffix(self):
        names = ["l", "l.2", "i", "i.alt1", "i.alt2", "a.ss01", "a", "x.case", "x", "period", "period.2"]
        sets = fc.alternate_sets(names, lambda name: name in ("l", "i", "a", "x"))
        self.assertEqual(sets, {"l": ["l.2"], "i": ["i.alt1", "i.alt2"]}, "stylistic sets and other letters' forms left out")

    def test_alternates_with_a_job_are_found(self):
        texts = {"liga": u"feature liga {\n  sub I' space [a - z] by I.2;\n  # l.2 in a comment\n} liga;\n"}
        texts["aalt"] = u"feature aalt {\n  sub l from [l l.2];\n} aalt;\n"
        self.assertEqual(fc.used_in(["I.2", "l.2", "i.2"], texts), {"I.2": ["liga"]}, "aalt lists every alternate")

    def test_take_turns(self):
        letters = ["i", "i.2", "i.3", "n", "l"]
        code = fc.cycle_code({"i": ["i.2", "i.3"]}, letters, 1)
        self.assertIn(u"@FreeLab_gap_i = [l n];", code)
        self.assertIn(u"  sub i i' by i.2;", code)
        self.assertIn(u"  sub i.2 @FreeLab_gap_i i' by i.3;", code)
        self.assertFalse(any(u"i.3 i' by" in line for line in code), "after the last alternate, the letter itself")
        text = fc.calt_text(u"feature calt {\n  sub x' y by x.alt;\n} calt;\n", code)
        self.assertIn(u"  sub x' y by x.alt;", text, "the feature's own code kept")
        self.assertEqual(fc.calt_text(text, code), text, "writing twice changes nothing")
        if HAVE_FONTTOOLS:
            self.assertIsNone(fc.check_code(text, letters + ["x", "x.alt", "y"]))


if __name__ == "__main__":
    unittest.main()
