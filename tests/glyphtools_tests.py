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
                                      "mark_to_mark": 0.01, "fonts": 7},
                         "thai bottom": {"base_gap": 0.3, "base_offset": 0.4, "mark_gap": 0.3, "mark_offset": 0.5,
                                         "fonts": 2},
                         "latin bottom": {"base_gap": 0.0, "base_offset": 0.0, "mark_gap": 0.04, "mark_offset": 0.0,
                                          "mark_to_mark": 0.01, "fonts": 119}},
             "bases": {"thai": ["0E01", "0E02"], "latin": ["00E4", "0142"]}}

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
        self.assertEqual(ko.anchors["bottom"], (300, 0), "the corpus's Latin, where Thai's row is from too few fonts")
        self.assertEqual(maiek.side, "top")
        self.assertEqual(maiek.anchors, {u"_top": (-105, 500), u"top": (-105, 710)})
        self.assertEqual(phinthu.side, "bottom")
        self.assertEqual(phinthu.anchors, {u"bottom": (-100, -210)}, "its own _bottom is kept")
        self.assertFalse(found["koold"].checked, "nothing to add")

    def test_base_letters(self):
        latin = ac.base_letters("latin", self.MODEL)
        for ch in u"aeiwAW\u0131\u00f8\u0142":
            self.assertIn(ord(ch), latin, ch)
        for ch in u"\u00aa\u0192\u1e85\u00e4":  # ordfeminine, florin, wdieresis; a with dieresis is precomposed
            self.assertNotIn(ord(ch), latin, ch)
        self.assertEqual(ac.base_letters("thai", self.MODEL), set([0xE01, 0xE02]), "the corpus's, Unicode composing none")
        self.assertIsNone(ac.base_letters("myanmar", self.MODEL), "nothing known: every letter")

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


class ScriptFeatureTests(unittest.TestCase):
    """Per-letter anchors, Arabic ligatures, the Devanagari reph and i-matras, Thai forms."""
    MODEL = {"anchors": {"thai top": {"base_gap": -0.06, "base_offset": 0.43, "mark_gap": 0.1, "mark_offset": 0.4,
                                      "mark_to_mark": 0.01, "fonts": 28},
                         "arabic top": {"base_gap": 0.07, "base_offset": 0.0, "mark_gap": 0.02, "mark_offset": 0.0,
                                        "fonts": 7},
                         "arabic bottom": {"base_gap": 0.07, "base_offset": 0.0, "mark_gap": 0.02, "mark_offset": 0.0,
                                           "fonts": 7}},
             "letters": {"thai top": {"0E1B": [0.55, -0.12, 28], "0E01": [0.9, 0.08, 2]}},
             "reph": {"share": 0.77, "gap": -0.01, "fonts": 30},
             "ligature": {"top": [[0.72, 0.0], [0.22, -0.08]], "bottom": [[0.74, -0.06], [0.27, 0.03]], "fonts": 19},
             "i_matra": {"0915": [0.56, 30], "0916": [0.88, 30]}}

    def test_letter_placement(self):
        glyphs = [("popla", 0xE1B, "base", ac.Ink(0, 0, 500, 700, top_center=450, bottom_center=250), {}),
                  ("koKai", 0xE01, "base", ac.Ink(0, 0, 500, 500, top_center=250, bottom_center=250), {}),
                  ("maiek", 0xE48, "mark", ac.Ink(-150, 600, -50, 700), {})]
        found = dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "thai", 1000, 500))
        # the mark's ink lands at 55% across, 0.12 em below the ascender's top; its own anchor sits
        # 0.4 of its width right of its center and 0.1 em under it
        self.assertEqual(found["popla"].anchors["top"], (315, 480))
        self.assertEqual(found["koKai"].anchors["top"], (round(250 + 0.43 * 500), 440),
                         "from 2 fonts only: the script's own rule")

    def test_ligature(self):
        self.assertEqual(ac.ligature_parts(u"uniFEFB", 0xFEFB, set()), 2)
        self.assertEqual(ac.ligature_parts(u"lam_alef-ar", 0, set([u"lam-ar", u"alef-ar"])), 2)
        self.assertEqual(ac.ligature_parts(u"lam_alef-ar.fina", 0, set([u"lam-ar", u"alef-ar"])), 2)
        self.assertEqual(ac.ligature_parts(u"uni06440627", 0, set()), 2)
        self.assertEqual(ac.ligature_parts(u"f_f", 0, set()), 0)
        self.assertEqual(ac.ligature_parts(u"beh-ar", 0x0628, set()), 0)
        glyphs = [("lam_alef-ar", 0, "ligature", ac.Ink(0, 0, 400, 800), {}, 2),
                  ("fatha-ar", 0x064E, "mark", ac.Ink(100, 900, 200, 950), {}),
                  ("kasra-ar", 0x0650, "mark", ac.Ink(100, -150, 200, -100), {})]
        found = dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "arabic", 1000, 500))
        lig = found["lam_alef-ar"]
        self.assertEqual(lig.anchors["top_1"], (288, 800), "the first letter, lam, on the right")
        self.assertEqual(lig.anchors["top_2"], (88, 720))
        self.assertEqual(lig.anchors["bottom_1"], (296, 60))
        lines = ac.mark_code(list(found.values()))["mark"]
        self.assertIn(u"pos ligature lam_alef-ar <anchor 296 60> mark @MC_bottom <anchor 288 800> mark @MC_top "
                      u"ligComponent <anchor 108 -30> mark @MC_bottom <anchor 88 720> mark @MC_top;", lines)

    def test_reph(self):
        for name in (u"rephdeva", u"Reph.dv", u"dvReph", u"uni0930094D.rphf"):
            self.assertTrue(ac.is_reph(name), name)
        for name in (u"iMatra_reph-deva", u"RephBindu.dv", u"ka-deva", u"eyelashRephdeva"):
            self.assertFalse(ac.is_reph(name), name)
        glyphs = [("ka-deva", 0x0915, "base", ac.Ink(0, 0, 600, 700, top_center=300, bottom_center=300), {}),
                  ("reph-deva", 0, "reph", ac.Ink(-200, 750, -50, 950), {})]
        found = dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "devanagari", 1000, 500))
        self.assertEqual(found["ka-deva"].anchors["reph"], (462, 690))
        self.assertEqual(found["reph-deva"].anchors, {u"_reph": (-125, 750)})
        lines = ac.mark_code(list(found.values()))["mark"]
        self.assertIn(u"markClass reph-deva <anchor -125 750> @MC_reph;", lines)
        self.assertTrue(any(line.startswith(u"pos base ka-deva") and u"mark @MC_reph" in line for line in lines))

    def test_i_matra(self):
        names_by_code = {0x093F: u"iMatra-deva", 0x0915: u"ka-deva", 0x0916: u"kha-deva"}
        names = set([u"iMatra-deva", u"iMatra-deva.01", u"iMatra-deva.02", u"ka-deva", u"kha-deva"])
        reaches = {u"iMatra-deva": 200, u"iMatra-deva.01": 330, u"iMatra-deva.02": 520}
        advances = {u"ka-deva": 600, u"kha-deva": 600}
        rules = ac.i_matra_rules(names_by_code, names, reaches.get, advances.get, self.MODEL)
        self.assertEqual([r.line for r in rules], [u"sub iMatra-deva' [ka-deva] by iMatra-deva.01;",
                                                   u"sub iMatra-deva' [kha-deva] by iMatra-deva.02;"])
        self.assertEqual(ac.i_matra_rules(names_by_code, set([u"iMatra-deva"]), reaches.get, advances.get, self.MODEL), [],
                         "one i-matra: nothing to pick")

    def test_thai_rules(self):
        names_by_code = {0x0E0D: u"uni0E0D", 0x0E38: u"uni0E38", 0x0E34: u"uni0E34", 0x0E48: u"uni0E48", 0x0E49: u"uni0E49"}
        names = set(names_by_code.values()) | set([u"uni0E0D.less", u"uni0E48.small"])
        lines = [r.line for r in ac.thai_rules(names_by_code, names)]
        self.assertEqual(lines, [u"sub uni0E0D' [uni0E38] by uni0E0D.less;",
                                 u"sub [uni0E34 uni0E48 uni0E49] uni0E48' by uni0E48.small;"])
        self.assertEqual([r.line for r in ac.thai_rules({0x0E0D: u"uni0E0D", 0x0E38: u"uni0E38"},
                                                        set([u"uni0E0D", u"uni0E38", u"yoYingthai.less"]))],
                         [u"sub uni0E0D' [uni0E38] by yoYingthai.less;"], "named after Glyphs' name for the letter")
        rules = ac.thai_rules(names_by_code, names)
        rules[1].checked = False
        texts = ac.mark_texts(rules, {})
        self.assertIn(u"sub uni0E0D' [uni0E38] by uni0E0D.less;", texts["ccmp"])
        self.assertNotIn(u"uni0E48.small", texts["ccmp"], "unchecked: left out")
        if HAVE_FONTTOOLS:
            self.assertIsNone(fc.check_code(u"languagesystem DFLT dflt;\n" + texts["ccmp"], sorted(names)))


class MoreScriptTests(unittest.TestCase):
    """Hebrew's dagesh, holam, and shin dot; the reph and i-matras of Bengali and Gujarati; Tamil."""
    MODEL = {"anchors": {"hebrew top": {"base_gap": 0.05, "base_offset": 0.0, "mark_gap": 0.04, "mark_offset": 0.0,
                                        "mark_to_mark": 0.02, "fonts": 25},
                         "hebrew bottom": {"base_gap": 0.03, "base_offset": 0.0, "mark_gap": 0.05, "mark_offset": 0.0,
                                           "mark_to_mark": 0.02, "fonts": 25}},
             "letters": {"hebrew center": {"05D1": [0.4, 0.5, 20], "05D3": [0.3, 0.6, 20]},
                         "hebrew topleft": {"05D1": [0.0, 0.1, 20]},
                         "hebrew topright": {"05E9": [0.9, 0.1, 20]}},
             "reph": {"devanagari": {"share": 0.77, "gap": -0.01, "fonts": 30},
                      "bengali": {"share": 0.8, "gap": 0.02, "fonts": 9}},
             "i_matra": {"0A95": [0.3, 10], "0A96": [0.7, 10]}}

    def test_scripts(self):
        for code, script in ((0x05D0, "hebrew"), (0x0995, "bengali"), (0x0A95, "gujarati"), (0x0B95, "tamil"),
                             (0x0915, "devanagari")):
            self.assertEqual(ac.anchor_script(code), script)

    def hebrew(self):
        glyphs = [("bet-hb", 0x05D1, "base", ac.Ink(0, 0, 500, 500), {}),
                  ("he-hb", 0x05D4, "base", ac.Ink(0, 0, 600, 500), {}),
                  ("shin-hb", 0x05E9, "base", ac.Ink(0, 0, 700, 500), {}),
                  ("patah-hb", 0x05B7, "mark", ac.Ink(-300, -120, -100, -80), {}),
                  ("dagesh-hb", 0x05BC, "mark", ac.Ink(-260, 230, -220, 270), {}),
                  ("holam-hb", 0x05B9, "mark", ac.Ink(-260, 560, -220, 600), {}),
                  ("shindot-hb", 0x05C1, "mark", ac.Ink(-160, 560, -120, 600), {})]
        return dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "hebrew", 1000, 500))

    def test_hebrew_marks_of_other_classes(self):
        found = self.hebrew()
        self.assertEqual(found["dagesh-hb"].anchors, {u"_center": (-240, 250)}, "the center of its ink, nothing onward")
        self.assertEqual(found["holam-hb"].anchors, {u"_topleft": (-240, 520)}, "under its ink's center by the gap")
        self.assertEqual(found["shindot-hb"].side, u"topright")
        self.assertEqual(found["patah-hb"].side, u"bottom")
        bet, he, shin = found["bet-hb"], found["he-hb"], found["shin-hb"]
        self.assertEqual(bet.anchors["center"], (200, 250), "where the corpus lands the dagesh in bet")
        self.assertEqual(he.anchors["center"], (210, 275), "a letter the corpus has too little of: its letters' median")
        self.assertEqual(bet.anchors["topleft"], (0, 560), "the holam's ink 0.1 em over bet's, at its left")
        self.assertEqual(he.anchors["topleft"], (0, 560))
        self.assertNotIn("topright", bet.anchors, "the shin dot's anchor: shin's only")
        self.assertEqual(shin.anchors["topright"], (630, 560))
        lines = ac.mark_code(list(found.values()))
        self.assertIn(u"markClass dagesh-hb <anchor -240 250> @MC_center;", lines["mark"])
        self.assertIn(u"pos base bet-hb <anchor 250 -30> mark @MC_bottom <anchor 200 250> mark @MC_center "
                      u"<anchor 0 560> mark @MC_topleft;", lines["mark"])
        self.assertTrue(any(line.startswith(u"pos base shin-hb") and u"mark @MC_topright" in line for line in lines["mark"]))
        self.assertFalse(any(u"dagesh-hb" in line for line in lines["mkmk"]), "nothing stacks on a dagesh")
        if HAVE_FONTTOOLS:
            texts = ac.mark_texts(list(found.values()), {})
            self.assertIsNone(fc.check_code(u"languagesystem DFLT dflt;\n" + texts["mark"] + texts["mkmk"],
                                            sorted(found)))

    def test_hebrew_without_a_model(self):
        glyphs = [("bet-hb", 0x05D1, "base", ac.Ink(0, 0, 500, 500), {}),
                  ("dagesh-hb", 0x05BC, "mark", ac.Ink(-260, 230, -220, 270), {}),
                  ("holam-hb", 0x05B9, "mark", ac.Ink(-260, 560, -220, 600), {})]
        bet = dict((g.name, g) for g in ac.plan_anchors(glyphs, {}, "hebrew", 1000, 500))["bet-hb"]
        self.assertEqual(bet.anchors["center"], (250, 250), "the middle of its ink")
        self.assertEqual(bet.anchors["topleft"][0], 0, "its ink's left end")

    def test_reph(self):
        self.assertEqual(ac.reph_row(self.MODEL, "bengali")["share"], 0.8)
        self.assertIsNone(ac.reph_row(self.MODEL, "gujarati"))
        self.assertEqual(ac.reph_row({"reph": {"share": 0.77, "gap": 0.0}}, "devanagari")["share"], 0.77, "the first models")
        self.assertIsNone(ac.reph_row({"reph": {"share": 0.77, "gap": 0.0}}, "bengali"))
        for name in (u"Reph.bn", u"bn_reph", u"bnReph", u"uni09B009CD", u"reph-beng", u"bReph"):
            self.assertTrue(ac.is_reph(name, "bengali"), name)
        for name in (u"Reph.gj", u"gjReph", u"rephgujr", u"uni0AB00ACD", u"reph-gujarati"):
            self.assertTrue(ac.is_reph(name, "gujarati"), name)
            self.assertFalse(ac.is_reph(name, "bengali"), name)
        self.assertFalse(ac.is_reph(u"rephdeva", "bengali"), "another script's reph")
        self.assertTrue(ac.is_reph(u"Reph_alt2.bn", "bengali"), "an alternate")
        for name in (u"gjmII_Reph", u"bSignIiReph", u"ivowelsignrephgujr", u"bAuMarkReph"):
            self.assertFalse(ac.is_reph(name), name + u": joined with a vowel sign")
        self.assertTrue(ac.is_reph(u"rephleftgujr", "gujarati"))
        glyphs = [("ka-beng", 0x0995, "base", ac.Ink(0, 0, 600, 700), {}),
                  ("reph-beng", 0, "reph", ac.Ink(-200, 750, -50, 950), {})]
        found = dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "bengali", 1000, 500))
        self.assertEqual(found["ka-beng"].anchors["reph"], (480, 720))

    def test_i_matra(self):
        names_by_code = {0x0ABF: u"MatraI.gj", 0x0A95: u"Ka.gj", 0x0A96: u"Kha.gj"}
        names = set([u"MatraI.gj", u"MatraI1.gj", u"MatraI2.gj", u"MatraII.gj", u"MatraI_Reph.gj", u"Ka.gj", u"Kha.gj"])
        self.assertEqual(ac.i_matra_variants(names, u"MatraI.gj", 0x0ABF), [u"MatraI1.gj", u"MatraI2.gj"],
                         "its name with other digits, not the ii-matra nor a ligature")
        self.assertEqual(ac.i_matra_variants(set([u"uni0ABF", u"uni0ABF.alt01", u"uni0AB1"]), u"uni0ABF", 0x0ABF),
                         [u"uni0ABF.alt01"], "a uniXXXX name's digits are its code point")
        self.assertEqual(ac.i_matra_variants(set([u"ivowelsigngujr", u"ivowelsign3gujr"]), u"ivowelsigngujr", 0x0ABF),
                         [u"ivowelsign3gujr"])
        self.assertEqual(ac.i_matra_variants(set([u"uni0ABF", u"iMatra-gujr.long"]), u"uni0ABF", 0x0ABF),
                         [u"iMatra-gujr.long"], "Glyphs' name with another common tag of the script")
        reaches = {u"MatraI.gj": 100, u"MatraI1.gj": 180, u"MatraI2.gj": 420}
        advances = {u"Ka.gj": 600, u"Kha.gj": 600}
        rules = ac.i_matra_rules(names_by_code, names, reaches.get, advances.get, self.MODEL, "gujarati")
        self.assertEqual([r.line for r in rules], [u"sub MatraI.gj' [Ka.gj] by MatraI1.gj;",
                                                   u"sub MatraI.gj' [Kha.gj] by MatraI2.gj;"])
        self.assertEqual(ac.i_matra_rules(names_by_code, names, reaches.get, advances.get, self.MODEL), [],
                         "Devanagari's i-matra: the font has none")
        kept = dict(self.MODEL, i_matra={"0A95": [0.3, 10, 0.2], "0A96": [0.7, 10, 0.8]})
        self.assertEqual([r.line for r in ac.i_matra_rules(names_by_code, names, reaches.get, advances.get, kept, "gujarati")],
                         [u"sub MatraI.gj' [Ka.gj] by MatraI1.gj;"], "most fonts keep their nominal i-matra before kha")

    def test_tamil(self):
        glyphs = [("ka-tamil", 0x0B95, "base", ac.Ink(0, 0, 600, 500), {}),
                  ("pulli-tamil", 0x0BCD, "mark", ac.Ink(-200, 560, -100, 660), {})]
        found = dict((g.name, g) for g in ac.plan_anchors(glyphs, {}, "tamil", 1000, 500))
        self.assertEqual(found["pulli-tamil"].side, "top")
        self.assertIn("top", found["ka-tamil"].anchors)


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
