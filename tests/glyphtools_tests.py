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
        self.assertEqual((dot.glyph, dot.side, dot.note), ("dotaccent", "below", u"for dot below"), "its twin above")
        self.assertEqual([m.glyph for m in found[O_CIRCUMFLEX_ACUTE].marks], ["circumflex", "acute"])
        self.assertTrue(found[O_HORN_DOT].missing and u"horn" in found[O_HORN_DOT].missing)

    def test_combining_marks_are_made_as_glyphs_of_their_own(self):
        bare = ac.Font(["o", "macron", "underscore", "period"],
                       [("o", 0x6F), ("macron", 0xAF), ("underscore", 0x5F), ("period", 0x2E)])
        found = dict((r.char, r) for r in ac.plan(bare, [ac.unichr_(0x0331), ac.unichr_(0x0332), ac.unichr_(0x0323),
                                                        ac.unichr_(0x0301)]))
        below = found[ac.unichr_(0x0331)]
        self.assertTrue(below.standalone)
        self.assertEqual((below.name, below.base), ("macronbelowcomb", "o"), "placed as on o")
        self.assertEqual(found[ac.unichr_(0x0332)].marks[0].glyph, "underscore", "the low line of the underscore")
        self.assertEqual(found[ac.unichr_(0x0323)].marks[0].glyph, "period", "the dot below of the period")
        self.assertTrue(found[ac.unichr_(0x0301)].missing, "no acute to draft from")
        ink = {"m": ac.Ink(100, 500, 300, 560)}.get
        parts = ac.standalone_parts([("o", 1, 1, 0, 0), ("m", 1, 1, 40, -620)], ink)
        self.assertEqual(parts, [("m", 1, 1, -200.0, -620)], "the letter taken out, the mark centered on 0")
        unencoded = ac.Font(["o", "acutecomb"], [("o", 0x6F), ("acutecomb", 0)])
        acute = ac.plan(unencoded, [ac.unichr_(0x0301)])[0]
        self.assertEqual((acute.name, acute.marks[0].glyph), (u"uni0301", "acutecomb"),
                         "the font's unencoded acutecomb is not its own name")

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


class ConventionTests(unittest.TestCase):
    """Marks fonts draw otherwise than Unicode's decomposition: Latvian's comma below and turned comma, the
    vertical caron; the names fonts give them; a and an."""

    def test_latvian_takes_a_comma_below_not_a_cedilla(self):
        f = ac.Font(["K", "k", "g", "commaaccentcomb", "commaaccentcomb.case", "cedillacomb", "S", "commaturnedabovecomb"],
                    [("K", 0x4B), ("k", 0x6B), ("g", 0x67), ("S", 0x53), ("cedillacomb", 0x327), ("commaaccentcomb", 0x326)])
        found = dict((r.code, r) for r in ac.plan(f, [ac.unichr_(c) for c in (0x136, 0x137, 0x123, 0x15E)]))
        self.assertEqual(found[0x136].marks[0].glyph, "commaaccentcomb.case", "the capital's comma below")
        self.assertEqual(found[0x137].marks[0].glyph, "commaaccentcomb")
        self.assertIn(u"comma below fonts draw for Unicode's cedilla", found[0x137].marks[0].label())
        g = found[0x123].marks[0]
        self.assertEqual((g.glyph, g.side, g.root), ("commaturnedabovecomb", "above", "commaturnedabove"),
                         "g takes a turned comma above")
        self.assertEqual(found[0x15E].marks[0].glyph, "cedillacomb", "Turkish s keeps its cedilla")
        self.assertIsNone(found[0x15E].marks[0].convention)
        production = ac.Font(["N", "uni0326", "uni0326.case"], [("N", 0x4E), ("uni0326", 0x326)])
        self.assertEqual(ac.plan(production, [ac.unichr_(0x145)])[0].marks[0].glyph, "uni0326.case",
                         "a production name's .case form")

    def test_drafts_of_the_comma_marks(self):
        f = ac.Font(["g", "k", "d", "comma", "quoteright"],
                    [("g", 0x67), ("k", 0x6B), ("d", 0x64), ("comma", 0x2C), ("quoteright", 0x2019)])
        found = dict((r.code, r) for r in ac.plan(f, [ac.unichr_(c) for c in (0x123, 0x137, 0x10F)]))
        turned = found[0x123].marks[0]
        self.assertEqual(turned.parts[0][:3], ("comma", -1.0, -1.0), "the comma turned about")
        self.assertIn(u"draft for turned comma above", turned.note)
        self.assertIn(u"turned", turned.label())
        self.assertEqual(found[0x137].marks[0].glyph, "comma", "the comma for a comma below")
        caron = found[0x10F].marks[0]
        self.assertEqual((caron.glyph, caron.side), ("quoteright", "topright"), "a vertical caron of quoteright")
        self.assertIn(u"of quoteright", caron.label())
        with_left = ac.Font(["g", "quoteleft", "comma"], [("g", 0x67), ("quoteleft", 0x2018), ("comma", 0x2C)])
        self.assertEqual(ac.plan(with_left, [ac.unichr_(0x123)])[0].marks[0].parts[0][:3], ("quoteleft", 1.0, 1.0),
                         "a left quote is a turned comma already")

    def test_the_vertical_caron_beside_the_stem(self):
        f = ac.Font(["d", "L", "caroncomb.alt", "caron"], [("d", 0x64), ("L", 0x4C), ("caron", 0x2C7)])
        found = dict((r.code, r) for r in ac.plan(f, [ac.unichr_(c) for c in (0x10F, 0x13D, 0x10E)]))
        self.assertEqual(found[0x10F].marks[0].glyph, "caroncomb.alt", "Glyphs' name for it")
        self.assertEqual(found[0x13D].marks[0].glyph, "caroncomb.alt")
        ink = {"d": ac.Ink(40, -10, 520, 760, top_right=520, advance=580), "caroncomb.alt": ac.Ink(0, 0, 60, 200)}.get
        parts, width = ac.place(found[0x10F], ink, ac.Placement(1000, MODEL))
        mark = parts[1]
        self.assertEqual((mark[3], mark[4] + 200), (520 + 48, 760), "0.048 em right of the stem, its top level with d's")
        self.assertEqual(width, 580)
        self.assertNotIn(0x10E, [code for code in ac.CONVENTIONS], "D takes a plain caron, as fonts draw it")
        bare = ac.Font(["l", "caron"], [("l", 0x6C), ("caron", 0x2C7)])
        self.assertEqual(ac.plan(bare, [ac.unichr_(0x13E)])[0].describe(),
                         u"needs a vertical caron (fonts draw it for Unicode's caron)", "not built from a v-shaped caron")

    def test_names_fonts_give_marks(self):
        for name, root in (("caroncomb.alt", "caronvertical"), ("caron.alt.case", "caronvertical"),
                           ("uni0326", "commaaccent"), ("uni0326.case", "commaaccent"), ("commaaccentrotate", "commaturnedabove"),
                           ("acutecomb.case", "acute"), ("uni0301", "acute"), ("uni3099", "dakuten")):
            self.assertEqual(ac.mark_key(name), root, name)
        self.assertTrue(ac.learnable(0x137, [("k", 0, 0), ("uni0326", 100, 0)]))
        self.assertFalse(ac.learnable(0x137, [("k", 0, 0), ("cedillacomb", 100, 0)]), "Marshallese's cedilla: not learned from")
        self.assertTrue(ac.learnable(0x10F, [("d", 0, 0), ("caroncomb.alt", 400, 0)]))

    def test_a_and_an(self):
        for word, expected in ((u"ogonek", u"an"), (u"acute", u"an"), (u"umlaut", u"an"), (u"horn", u"a"), (u"hook above", u"a"),
                               (u"ring", u"a"), (u"cedilla", u"a"), (u"unit", u"a"), (u"U+0312", u"a"), (u"hour", u"an"),
                               (u"ypogegrammeni (iota subscript)", u"an"), (u"upsilon", u"an"), (u"one", u"a"),
                               (u"uvula", u"a"), (u"F", u"an"), (u"K", u"a"), (u"dakuten", u"a")):
            self.assertEqual(ac.article(word), expected, word)
        self.assertEqual(ac.listed([u"a", u"b", u"c"]), u"a, b, and c")
        self.assertEqual(ac.listed([u"a", u"b"]), u"a and b")
        bare = ac.Font(["a", "o"], [("a", 0x61), ("o", 0x6F)])
        found = dict((r.code, r) for r in ac.plan(bare, [ac.unichr_(0x105), ac.unichr_(0x1EDB)]))
        self.assertEqual(found[0x105].describe(), u"needs an ogonek")
        self.assertEqual(found[0x1EDB].describe(), u"needs a horn and an acute")


KANA_MODEL = {"kana": {"dakuten": {"304B": [-0.05, -0.06, 0.22, 30], "hiragana": [-0.04, -0.05, 0.21, 40]},
                       "handakuten": {"hiragana": [-0.08, -0.03, 0.21, 39]}}}


class KanaTests(unittest.TestCase):
    GA, PA, KATA_VU, YORI = 0x304C, 0x3071, 0x30F4, 0x309E

    def test_voiced_kana_are_built_from_their_letter_and_mark(self):
        f = ac.Font(["uni304B", "uni306F", "uni30A6", "uni309D", "uni3099", "uni309C"],
                    [("uni304B", 0x304B), ("uni306F", 0x306F), ("uni30A6", 0x30A6), ("uni309D", 0x309D),
                     ("uni3099", 0x3099), ("uni309C", 0x309C)])
        kana = [ac.unichr_(code) for low, high in dict((k, r) for k, _, r in ac.SETS)["kana"] for code in range(low, high)]
        found = dict((r.code, r) for r in ac.plan(f, kana))
        ga = found[self.GA]
        self.assertEqual((ga.base, ga.marks[0].glyph, ga.marks[0].side, ga.name), ("uni304B", "uni3099", "kana", u"uni304C"))
        self.assertEqual(found[self.PA].marks[0].glyph, "uni309C", "the spacing handakuten, the font having no combining one")
        self.assertEqual(found[self.KATA_VU].base, "uni30A6", "katakana vu")
        self.assertEqual(found[self.YORI].base, "uni309D", "the voiced iteration mark")
        self.assertEqual(ac.scripts_present(f.by_code), set(["kana"]))
        self.assertEqual(ac.script_of(ac.unichr_(self.GA)), "kana")

    def test_placed_at_the_top_right_as_the_fonts_place_it(self):
        f = ac.Font(["ka", "dakuten"], [("ka", 0x304B), ("dakuten", 0x3099)])
        ga = ac.plan(f, [ac.unichr_(self.GA)])[0]
        ink = {"ka": ac.Ink(80, -60, 860, 800, advance=1000), "dakuten": ac.Ink(0, 0, 160, 180)}.get
        parts, width = ac.place(ga, ink, ac.Placement(1000, KANA_MODEL))
        mark = parts[1]
        self.assertEqual((mark[3] + 80, mark[4] + 90), (860 - 50, 800 - 60), "its center 0.05 em left of ka's right, "
                                                                            "0.06 em under its top: ka's own row")
        self.assertEqual(width, 1000)
        parts, _ = ac.place(ga, ink, ac.Placement(1000))
        self.assertEqual((parts[1][3] + 80, parts[1][4] + 90), (round(860 - 49.3), round(800 - 64.5)), "no model: the set's")

    def test_drafted_or_missing(self):
        f = ac.Font(["ka", "quotedblright"], [("ka", 0x304B), ("quotedblright", 0x201D)])
        ga = ac.plan(f, [ac.unichr_(self.GA)])[0]
        self.assertIn(u"draft for dakuten", ga.marks[0].note)
        none = ac.Font(["ka"], [("ka", 0x304B)])
        self.assertEqual(ac.plan(none, [ac.unichr_(self.GA)])[0].describe(), u"needs a dakuten")


class CenterTests(unittest.TestCase):
    """Snapping a dragged mark to its letter's centers, and carrying a placement to related letters."""

    def test_centers_and_snap(self):
        a = ac.Ink(40, -10, 460, 480, top_center=230)
        self.assertEqual(ac.letter_centers(a, 10, "above"), [(260.0, u"box center"), (240, u"top center")])
        o = ac.Ink(40, -10, 460, 480)
        self.assertEqual(ac.letter_centers(o, 0, "below"), [(250.0, u"center")])
        self.assertEqual(ac.letter_centers(o, 0, "kana"), [])
        targets = ac.letter_centers(a, 10, "above")
        self.assertEqual(ac.snap(243, targets, 5), (240, u"top center"), "the nearest within reach")
        self.assertEqual(ac.snap(250, targets, 5), (None, None), "none within reach")

    def recipe(self, char, base):
        return ac.Recipe(char, base=base, marks=[ac.Mark("acute", "above", [("acute", 1.0, 1.0, 0.0, 0.0)])])

    def test_centered_stays_centered_on_a_wider_letter(self):
        model = {"format": 1, "gap": {"acute lower": 0.05}, "side_offset": {"above lower": 0.03}}
        ink = {"o": ac.Ink(40, -10, 460, 480, advance=500), "ae": ac.Ink(40, -10, 840, 480, top_center=460, advance=880),
               "acute": ac.Ink(0, 500, 100, 600)}.get
        placement = ac.Placement(1000, model)
        o, ae = self.recipe(ac.unichr_(0xF3), "o"), self.recipe(ac.unichr_(0x1FD), "ae")
        parts, center = ac.mark_center(o, 0, ink, placement)
        self.assertEqual(center, 250 + round(0.03 * 420), "the font's habit: 3% of o's width right")
        o.adjust = {0: [250 - center, 20.0, 1.0, 1.0]}  # centered on o by hand, and raised
        change = ac.carried_adjust(o, 0, ae, 0, ink, placement)
        ae.adjust = {0: change}
        self.assertEqual(ac.mark_center(ae, 0, ink, placement)[1], 460, "centered on ae's top center too")
        self.assertEqual(change[1], 20.0, "raised as much")
        o.adjust = {0: [250 - center + 10, 0.0, 1.0, 1.0]}  # 10 units right of o's center
        ae.adjust = {0: ac.carried_adjust(o, 0, ae, 0, ink, placement)}
        self.assertEqual(ac.mark_center(ae, 0, ink, placement)[1], 470, "10 units right of ae's center, in units")
        o.adjust = {0: [0.0, 15.0, 1.0, 1.0]}
        self.assertEqual(ac.carried_adjust(o, 0, ae, 0, ink, placement), [0.0, 15.0, 1.0, 1.0],
                         "raised only: the change as it is")

    def test_a_letters_own_shift_is_kept(self):
        model = {"format": 1, "gap": {"acute lower": 0.05}, "side_offset": {"above lower": 0.0},
                 "offset": {"l above *": 0.5}}
        ink = {"o": ac.Ink(40, -10, 460, 480, advance=500), "l": ac.Ink(60, 0, 140, 760, advance=200),
               "acute": ac.Ink(0, 500, 100, 600)}.get
        placement = ac.Placement(1000, model)
        o, l = self.recipe(ac.unichr_(0xF3), "o"), self.recipe(ac.unichr_(0x13A), "l")
        o.adjust = {0: [6.0, 0.0, 1.0, 1.0]}  # 6 units right of o's center: not centered
        l.adjust = {0: ac.carried_adjust(o, 0, l, 0, ink, placement)}
        self.assertEqual(ac.mark_center(l, 0, ink, placement)[1], 100 + 0.5 * 80 + 6, "right of l's stem as fonts set it, "
                                                                                     "and 6 units more")


class LineUpTests(unittest.TestCase):
    def test_marks_of_a_group_line_up_and_exceptions_are_named(self):
        model = {"format": 1, "gap": {"acute lower": 0.05, "caron lower": 0.05, "circumflex lower": 0.05},
                 "side_offset": {"above lower": 0.0}}
        ink = {"o": ac.Ink(40, -10, 460, 480, advance=500), "e": ac.Ink(40, -10, 440, 470, advance=480),
               "h": ac.Ink(60, 0, 440, 760, advance=500), "c": ac.Ink(40, -10, 420, 480, advance=460),
               "acute": ac.Ink(0, 500, 100, 600), "caron": ac.Ink(0, 500, 140, 590),
               "circumflex": ac.Ink(0, 500, 140, 600), "cedilla": ac.Ink(0, -200, 80, 0)}.get
        placement = ac.Placement(1000, model)

        def recipe(code, base, *marks):
            return ac.Recipe(ac.unichr_(code), base=base,
                             marks=[ac.Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)]) for root, side, glyph in marks])
        ecaron = recipe(0x11B, "e", ("caron", "above", "caron"))
        oacute = recipe(0xF3, "o", ("acute", "above", "acute"))
        hcirc = recipe(0x125, "h", ("circumflex", "above", "circumflex"))
        ccedil = recipe(0xE7, "c", ("cedilla", "below", "cedilla"))
        stacked = recipe(0x1EA5, "e", ("circumflex", "above", "circumflex"), ("acute", "above", "acute"))
        ecaron.adjust = {0: [0.0, 25.0, 1.0, 1.0]}  # raised by hand: the reference
        line, moves, left_out = ac.line_up_plan([ecaron, oacute, hcirc, ccedil, stacked], ecaron, 0, ink, placement,
                                                None, 1000.0)
        moved = dict((other.char, rise) for other, _, rise in moves)
        self.assertIn(oacute.char, moved, "o's acute: the same group (lowercase, x-height)")
        oacute.adjust = {0: [0.0, moved[oacute.char], 1.0, 1.0]}
        self.assertAlmostEqual(ac.placed_mark_box(oacute, 0, ink, placement, None)[1], line, 3,
                               "its bottom level with the caron's")
        why = dict((other.char, reason) for other, reason in left_out)
        self.assertIn(u"taller", why[hcirc.char], "h is taller: its circumflex is left as it is")
        self.assertIn(u"stacked", why[stacked.char])
        self.assertNotIn(ccedil.char, moved, "a mark below is another side")
        self.assertIsNotNone(ac.line_up_exclusion(ccedil, 0), "a cedilla keeps its own place")


class AttachedLineUpTests(unittest.TestCase):
    def test_ogoneks_line_up_with_ogoneks_only(self):
        model = {"format": 1, "gap": {}, "side_offset": {}}
        ink = {"a": ac.Ink(40, -10, 460, 480, advance=500), "e": ac.Ink(40, -10, 440, 470, advance=480),
               "ogonek": ac.Ink(0, -200, 90, 0), "acute": ac.Ink(0, 500, 100, 600)}.get
        placement = ac.Placement(1000, model)

        def recipe(code, base, *marks):
            return ac.Recipe(ac.unichr_(code), base=base,
                             marks=[ac.Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)]) for root, side, glyph in marks])
        aogonek = recipe(0x105, "a", ("ogonek", "below", "ogonek"))
        eogonek = recipe(0x119, "e", ("ogonek", "below", "ogonek"))
        eacute = recipe(0xE9, "e", ("acute", "above", "acute"))
        aogonek.adjust = {0: [0.0, -15.0, 1.0, 1.0]}  # lowered by hand: the reference
        line, moves, left_out = ac.line_up_plan([aogonek, eogonek, eacute], aogonek, 0, ink, placement, None, 1000.0)
        self.assertEqual([other.char for other, _, _ in moves], [eogonek.char], "the other ogonek, not the acute")
        eogonek.adjust = {0: [0.0, moves[0][2], 1.0, 1.0]}
        self.assertAlmostEqual(ac.placed_mark_box(eogonek, 0, ink, placement, None)[1], line, 3, "bottoms level")
        self.assertIn(u"joined", ac.line_up_exclusion(aogonek, 0), "never lined up with the marks below at large")


class AnchorTests(unittest.TestCase):
    MODEL = {"anchors": {"thai top": {"base_gap": -0.06, "base_offset": 0.43, "mark_gap": 0.1, "mark_offset": 0.45,
                                      "mark_to_mark": 0.01, "fonts": 7},
                         "thai bottom": {"base_gap": 0.3, "base_offset": 0.4, "mark_gap": 0.3, "mark_offset": 0.5,
                                         "fonts": 2},
                         "latin bottom": {"base_gap": 0.0, "base_offset": 0.0, "mark_gap": 0.04, "mark_offset": 0.0,
                                          "mark_to_mark": 0.01, "fonts": 119}},
             "bases": {"thai": ["0E01", "0E02"], "latin": ["00E4", "0142"]}}

    def test_placements_apply_to_related_letters(self):
        def recipe(ch, base, *marks):
            return ac.Recipe(ch, base=base, marks=[ac.Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)]) for root, side, glyph in marks])
        circ = ("circumflex", "top", "circumflexcomb.case")
        c, g, j = recipe(u"\N{LATIN CAPITAL LETTER C WITH CIRCUMFLEX}", "C", circ), \
            recipe(u"\N{LATIN CAPITAL LETTER G WITH CIRCUMFLEX}", "G", circ), \
            recipe(u"\N{LATIN CAPITAL LETTER J WITH CIRCUMFLEX}", "J", circ)
        small = recipe(u"\N{LATIN SMALL LETTER C WITH CIRCUMFLEX}", "c", ("circumflex", "top", "circumflexcomb"))
        acute = recipe(u"\N{LATIN CAPITAL LETTER C WITH ACUTE}", "C", ("acute", "top", "acutecomb.case"))
        stacked = recipe(u"\N{LATIN CAPITAL LETTER A WITH CIRCUMFLEX AND ACUTE}", "A", circ, ("acute", "top", "acutecomb.case"))
        missing = recipe(u"\N{LATIN CAPITAL LETTER H WITH CIRCUMFLEX}", "H", circ)
        missing.missing = u"H"
        found = ac.related_marks([c, g, j, small, acute, stacked, missing], c, 0)
        self.assertEqual([(r.char, at) for r, at in found], [(g.char, 0), (j.char, 0), (stacked.char, 0)],
                         "the same capital circumflex, first on its side; not lowercase, not another mark, not missing")
        caron = ac.Recipe(ac.unichr_(0x010C), base="C",
                          marks=[ac.Mark("caron", "top", [("circumflexcomb.case", 1.0, -1.0, 0.0, 0.0)])])
        self.assertEqual(ac.related_marks([caron, g], c, 0), [(g, 0)], "a caron of the circumflex upside down is no circumflex")
        self.assertNotEqual(ac.mark_signature(caron.marks[0]), ac.mark_signature(c.marks[0]))

    def test_letters_get_the_anchors_their_precomposed_forms_need(self):
        sides = ac.composed_sides()
        self.assertEqual(sides[ord(u"B")][0], set([u"top", u"bottom"]), "B: dot above, dot below, macron below")
        self.assertIn(u"ogonek", sides[ord(u"a")][0])
        self.assertIn(u"horn", sides[ord(u"O")][0])
        self.assertTrue(sides[ord(u"a")][1], "a stacks marks (a with circumflex and acute)")
        self.assertNotIn(ord(u"x") + 0x1000, sides)
        g = ac.AnchorGlyph("B", 0x42, "base", None)
        g.anchors = {"top": (0, 0), "bottom": (0, 0)}
        self.assertEqual(ac.base_group(g), u"Marks above and below")
        g.stacks = True
        self.assertEqual(ac.base_group(g), u"Marks above and below", "stacking is the marks' matter: no section of bases")

    def test_own_anchors_move_by_hand(self):
        g = ac.AnchorGlyph("a", 0x61, "base", None, existing={"top": (250, 600)})
        g.anchors = {"bottom": (250, 0)}
        self.assertFalse(g.moved())
        g.adjust = {"top": [10, -5], "bottom": [3, 0]}
        self.assertEqual(g.placed(), {"top": (260, 595), "bottom": (253, 0)})
        self.assertEqual(g.moved(), ["top"], "its own anchor, moved, is written as a move; bottom is added")
        g.anchors = {}
        self.assertTrue(g.pending(), "nothing to add, one to move")
        self.assertFalse(ac.Rule("ccmp", "x.small", u"", u"").pending(), "a substitution writes no anchors")

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

    def test_a_mark_attached_already_takes_no_other_class(self):
        glyphs = [("horncomb", 0x031B, "mark", ac.Ink(0, 400, 80, 520), {"_topright": (0, 400)}),
                  ("ogonekcomb", 0x0328, "mark", ac.Ink(-100, -200, 0, 0), {"_bottom": (-50, 0)}),
                  ("tildecomb", 0x0303, "mark", ac.Ink(-100, 550, 100, 650), {})]
        found = dict((g.name, g) for g in ac.plan_anchors(glyphs, self.MODEL, "latin", 1000, 500))
        self.assertEqual(found["horncomb"].anchors, {}, "its _topright attaches it: no _horn")
        self.assertNotIn(u"_ogonek", found["ogonekcomb"].anchors, "its _bottom attaches it")
        self.assertIn(u"_top", found["tildecomb"].anchors, "a mark with no anchor of its own gets one")
        classes = [line for line in ac.mark_code(list(found.values()))["mark"] if line.startswith(u"markClass horncomb")]
        self.assertEqual(len(classes), 1, "one mark class")


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
        undrawn = ac.Recipe(u"x", u"x", "q", [ac.Mark("acute", "above", [("acute", 1.0, 1.0, 0.0, 0.0)])])
        self.assertEqual(ac.place(undrawn, inks().get, placement), (None, 0), "a letter with no outline: nothing placed")
        self.assertIsNone(ac.placed_mark_box(undrawn, 0, inks().get, placement, None))

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

    def test_a_borrowed_mark_is_learned_as_the_characters_own(self):
        marks = ac.learned_marks(0x1E07, [("b", 0, 0), ("macroncomb", 150, -600)])  # b with macron below
        self.assertEqual(marks, [("macroncomb", 150, -600, "macronbelow", "below")], "a macron below, not above")
        ink = {"b": ac.Ink(0, 0, 500, 500), "k": ac.Ink(0, 0, 500, 500), "macroncomb": ac.Ink(0, 500, 200, 560)}.get
        placement = ac.Placement(1000.0, MODEL)
        placement.learn([("b", marks), ("k", ac.learned_marks(0x1E35, [("k", 0, 0), ("macroncomb", 150, -600)]))],
                        ink, lambda name: "lower")
        self.assertEqual([g for g, _ in placement.seen[("macronbelow", "lower")]], [40, 40], "40 under the letter")
        self.assertNotIn(("macron", "lower"), placement.seen)
        self.assertNotIn(("above", "lower"), placement.sides)
        self.assertGreater(placement.gap("macron", "above", "lower"), 0, "a macron above still sits over its letter")
        left = ac.learned_marks(0x386, [("Alpha", 0, 0), ("acutecomb", 10, 0)])
        self.assertEqual(left[0][3:], ("acute", "left"), "a Greek capital's tonos at its left")
        placement.learn([("Alpha", left)] * 3, {"Alpha": ac.Ink(10, 0, 600, 700), "acutecomb": ac.Ink(0, 500, 100, 700)}.get,
                        lambda name: "upper")
        self.assertNotIn(("above", "upper"), placement.sides, "not learned as a mark above")

    def test_marks_are_measured_from_the_base_as_moved(self):
        moved = ac.learned_marks(0xF3, [("o", 100, 40), ("acute", 300, 590)])
        self.assertEqual(moved, ac.learned_marks(0xF3, [("o", 0, 0), ("acute", 200, 550)]), "the base's move taken off")
        ink = {"o": ac.Ink(0, 0, 500, 500), "acute": ac.Ink(0, 0, 100, 100)}.get
        placement = ac.Placement(1000.0, MODEL)
        placement.learn([("o", moved)] * 3, ink, lambda name: "lower")
        self.assertEqual(placement.seen[("acute", "lower")][0], (50, 0.0), "a gap of 50, centered")

        class Transform(object):
            def __init__(self, m11, m22, dx, dy):
                self.values = (m11, m22, dx, dy)

            def m11(self):
                return self.values[0]

            def m22(self):
                return self.values[1]

            def m12(self):
                return 0.0

            def m21(self):
                return 0.0

            def dx(self):
                return self.values[2]

            def dy(self):
                return self.values[3]

        class Shape(object):
            isComponent = True

            def __init__(self, name, transform):
                self.shapeData, self.transform = Stub(componentGlyph=name), transform

        moved_only = Stub(shapes=[Shape("o", Transform(1.0, 1.0, 100, 40)), Shape("acute", Transform(1.0, 1.0, 300, 590))])
        self.assertEqual(ac.component_parts(moved_only), [("o", 100, 40), ("acute", 300, 590)])
        scaled = Stub(shapes=[Shape("o", Transform(1.0, 1.0, 0, 0)), Shape("acute", Transform(1.2, 1.2, 300, 590))])
        self.assertIsNone(ac.component_parts(scaled), "a scaled mark is not measured as its glyph: not learned from")


class Stub(object):
    """An object with the given attributes (FontLab's and Qt's, stubbed)."""

    def __init__(self, **values):
        self.__dict__.update(values)


class ReferenceTests(unittest.TestCase):
    def test_a_family_whose_own_font_cannot_be_read_has_nothing(self):
        raw = {"font": None}

        def from_font(font):
            if raw["font"] is None:
                raise RuntimeError("no QRawFont")
            return raw["font"]
        gui = Stub(QFont=lambda family: family, QFontInfo=lambda font: Stub(family=lambda: font),
                   QRawFont=Stub(fromFont=from_font), QFontMetrics=lambda font: Stub(inFontUcs4=lambda code: True))
        saved = ac._qt
        try:
            ac._qt = lambda: (None, gui)
            self.assertFalse(ac.has_character(u"Arial", 0x41), "not as Windows' fallback fonts have it")
            raw["font"] = Stub(isValid=True, supportsCharacter=lambda code: code == 0x41)
            self.assertTrue(ac.has_character(u"Arial", 0x41))
            self.assertFalse(ac.has_character(u"Arial", 0x42))
        finally:
            ac._qt = saved

    def test_fonts_are_told_apart_by_their_id(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.ak = Stub(font_key=lambda package: package.path or u"unsaved:%s" % package.tfn)

        def package(number):
            return Stub(path=u"", tfn=u"Untitled", fgPackage=Stub(id=number))
        self.assertNotEqual(dialog.package_key(package(1)), dialog.package_key(package(2)), "two unsaved fonts of one name")
        self.assertEqual(dialog.package_key(package(1)), dialog.package_key(package(1)), "one font, read twice")
        self.assertEqual(dialog.package_key(Stub(path=u"a.vfc", tfn=u"A")), (u"a.vfc", None))
        self.assertIsNone(dialog.package_key(None))


class AnchorPageTests(unittest.TestCase):
    """The Mark anchors tab's editor and writing, FontLab's objects stubbed."""

    def test_a_mark_kept_on_an_anchor_of_another_side(self):
        inks = {"A": ac.Ink(10, 0, 590, 700, advance=600), "ogonekcomb": ac.Ink(-100, -200, 0, 0)}
        glyphs = ac.plan_anchors([("A", 0x41, "base", inks["A"], {}),
                                  ("ogonekcomb", 0x0328, "mark", inks["ogonekcomb"], {"_bottom": (-50, 0)})],
                                 {}, "latin", 1000, 500)
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        page.glyphs, page.package = glyphs, Stub(upm=1000)
        page.ink = type("Ink", (object,), {"__call__": lambda self, name: inks.get(name),
                                           "path": lambda self, name: (None, inks[name].advance)})()
        a, ogonek = glyphs
        self.assertEqual(ogonek.side, "ogonek")
        self.assertNotIn(u"_ogonek", ogonek.placed(), "its own _bottom attaches it")
        scene = page.scene(ogonek)
        bottom = a.placed()[u"bottom"]
        self.assertEqual(scene["parts"][1][3:], (bottom[0] + 50, bottom[1]), "hung on A's bottom by its _bottom")
        self.assertEqual(page.edits, [(ogonek, u"_bottom", -1)])
        self.assertIsNotNone(page.scene(a))
        page.glyphs = [ogonek]
        self.assertIsNone(page.scene(ogonek), "no base to hang it on: nothing drawn")

    def page(self, layers):
        """An AnchorPage over a font of one glyph, a, whose layers are {master: {anchor: (x, y)}}."""
        class Anchor(object):
            def __init__(self, point):
                self.point, self.name = point, None

        def point(x, y):
            return Stub(x=lambda: x, y=lambda: y)

        class Layer(object):
            def __init__(self, anchors):
                self.anchors = []
                for name, (x, y) in anchors.items():
                    anchor = Anchor(point(x, y))
                    anchor.name = name
                    self.anchors.append(anchor)

            def findAnchor(self, name):
                return next((anchor for anchor in self.anchors if anchor.name == name), None)

            def addAnchor(self, anchor):
                self.anchors.append(anchor)

            def read(self):
                return dict((anchor.name, (anchor.point.x(), anchor.point.y())) for anchor in self.anchors)

        built = dict((master, Layer(anchors)) for master, anchors in layers.items())
        glyph = Stub(getLayerByName=lambda master: built[master])
        package = Stub(masters=sorted(layers), findName=lambda name: glyph if name == "a" else None)
        ink = ac.Ink(40, -10, 460, 480, advance=500)
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        page.package, page.master, page.texts = package, "Regular", {}
        page.plan_for = lambda master: (ac.plan_anchors([("a", 0x61, "base", ink, built[master].read())], {}, "latin",
                                                        1000, 500), None)
        page.glyphs = page.plan_for("Regular")[0]
        page.harvest = page.run = lambda keep_script=False: None
        page.code_box = Stub(checked=False)
        page.owner = Stub(current_font=lambda: package, package_key=lambda p: (u"a.vfc", 1) if p is not None else None,
                          log=Stub(add=lambda text, kind="info": None))
        page.ak = Stub(notify_changed=lambda *args: None, b=lambda text: u"%s" % text, html=lambda text: u"%s" % text)
        page.fontlab = Stub(flPinPoint=lambda point: Anchor(point))
        return page, built

    def write(self, page):
        saved = ac._qt
        try:
            ac._qt = lambda: (Stub(QPointF=lambda x, y: Stub(x=lambda: x, y=lambda: y)), None)
            page.write()
        finally:
            ac._qt = saved

    def test_a_move_written_is_not_written_again(self):
        page, built = self.page({"Regular": {"top": (250, 600), "bottom": (250, 0), "ogonek": (460, 0)}})
        g = page.glyphs[0]
        g.adjust, g.checked = {"top": [10, 0]}, True
        self.assertTrue(g.pending())
        self.write(page)
        self.assertEqual(built["Regular"].read()["top"], (260, 600))
        self.assertEqual(g.adjust, {}, "the font has the move now")
        again = page.plan_for("Regular")[0][0]
        again.adjust = g.adjust  # (as the refresh carries it)
        self.assertFalse(again.pending(), "nothing more to write")

    def test_anchors_another_master_lacks(self):
        page, built = self.page({"Regular": {"top": (250, 600), "bottom": (250, 0), "ogonek": (460, 0)}, "Bold": {}})
        g = page.glyphs[0]
        self.assertFalse(g.pending(), "Regular has them all")
        g.elsewhere = g.checked = True  # (as the list finds Bold's planned)
        self.assertTrue(g.pending())
        self.write(page)
        self.assertEqual(sorted(built["Bold"].read()), ["bottom", "ogonek", "top"], "Bold gets them")
        self.assertEqual(built["Regular"].read(), {"top": (250, 600), "bottom": (250, 0), "ogonek": (460, 0)},
                         "Regular as it was")

    # -- the bases' sections, the notes, and stacked examples (the owner's reports of 2026-11-12) --

    INKS = {"e": ac.Ink(40, -10, 440, 470, advance=480), "B": ac.Ink(60, 0, 520, 700, advance=580),
            "F": ac.Ink(60, 0, 480, 700, advance=520), "O": ac.Ink(40, -10, 660, 710, advance=700),
            "circumflexcomb": ac.Ink(-100, 550, 100, 650), "acutecomb": ac.Ink(-60, 550, 60, 660),
            "dotbelowcomb": ac.Ink(-50, -150, 50, -50), "ogonekcomb": ac.Ink(-100, -200, 0, 0)}

    def latin_page(self, rows):
        """An AnchorPage over Latin glyphs, [(name, code, role, existing anchors)]."""
        inks = self.INKS
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        page.glyphs = ac.plan_anchors([(name, code, role, inks[name], existing) for name, code, role, existing in rows],
                                      {}, "latin", 1000, 500)
        page.package, page.scripts, page.script_box = Stub(upm=1000), ["latin"], Stub(currentIndex=0)
        page.ink = type("Ink", (object,), {"__call__": lambda self, name: inks.get(name),
                                           "path": lambda self, name: (None, inks[name].advance)})()
        return page, dict((g.name, g) for g in page.glyphs)

    MARKS = [("circumflexcomb", 0x0302, "mark", {}), ("acutecomb", 0x0301, "mark", {}),
             ("dotbelowcomb", 0x0323, "mark", {}), ("ogonekcomb", 0x0328, "mark", {})]

    def test_every_letter_takes_marks_above_and_below(self):
        page, found = self.latin_page([("F", 0x46, "base", {}), ("e", 0x65, "base", {}), ("O", 0x4F, "base", {})])
        self.assertEqual(sorted(found["F"].anchors), ["bottom", "top"],
                         "F has no precomposed letter with a mark below: a combining one goes under it all the same")
        self.assertEqual(ac.base_group(found["F"]), u"Marks above and below")
        self.assertEqual(sorted(found["e"].anchors), ["bottom", "ogonek", "top"], "the side anchors only where needed")
        self.assertEqual(sorted(found["O"].anchors), ["bottom", "horn", "ogonek", "top"])
        self.assertTrue(found["O"].stacks)
        self.assertEqual(ac.base_group(found["O"]), u"With side marks too (ogonek, horn)",
                         "a letter that stacks marks is listed by its anchors: marks stack by the marks' anchors")
        self.assertFalse([label for label in ac.BASE_GROUP_ORDER if u"Stacking" in label], "no section of bases for it")

    def test_an_anchor_the_marks_do_not_use_is_not_noted(self):
        page, found = self.latin_page([("B", 0x42, "base", {"b.dotbelowcomb_2": (300, -80)}),
                                       ("F", 0x46, "base", {"above": (270, 720), "_top": (0, 0)}),
                                       ("acutecomb", 0x0301, "mark", {"_above": (0, 540), "entry": (0, 0)})])
        self.assertEqual(found["B"].existing, {}, "not an anchor marks attach to: it says nothing of them")
        self.assertEqual(sorted(found["B"].anchors), ["bottom", "top"])
        self.assertEqual(found["F"].existing, {"above": (270, 720)},
                         "the font's own side (its marks have _above) counts; an attaching anchor on a letter does not")
        self.assertEqual(found["acutecomb"].existing, {"_above": (0, 540)})
        texts = {}
        item = Stub(setText=lambda column, text: texts.__setitem__(column, text), setIcon=lambda icon: None)
        page.owner_picture = lambda g: None
        saved = ac._qt
        try:
            ac._qt = lambda: (None, None)
            page.refresh_item(item, found["B"])
            self.assertEqual(texts[3], u"", "no note of it")
            page.refresh_item(item, found["F"])
            self.assertEqual(texts[3], u"has above already", "a short note in a cell: no period")
            mark = found["acutecomb"]
            page.refresh_item(item, mark)
            self.assertFalse(texts[3].endswith(u"."), texts[3])
            self.assertIn(u"has _above already", mark.cell, "what a search looks through")
        finally:
            ac._qt = saved

    def test_the_reference_shows_only_the_sides_the_letter_has(self):
        page, found = self.latin_page([("F", 0x46, "base", {})] + self.MARKS)
        self.assertEqual(page.reference_text(found["F"]), text(0x0046, 0x0323, 0x0302), "below and above, on one letter")
        del found["F"].anchors["bottom"]  # (a letter left without that side)
        self.assertEqual(page.reference_text(found["F"]), text(0x0046, 0x0302), "no mark below a letter with no anchor for it")

    def test_stacked_examples(self):
        page, found = self.latin_page([("e", 0x65, "base", {}), ("B", 0x42, "base", {})] + self.MARKS)
        e, b, circumflex, acute = found["e"], found["B"], found["circumflexcomb"], found["acutecomb"]
        self.assertEqual(page.reference_text(e), text(0x0065, 0x0323, 0x0302, 0x0301, 0x0020, 0x0065, 0x0328),
                         "e stacks marks: a dot below, a circumflex, and an acute on it; then its ogonek")
        self.assertEqual(page.reference_text(b), text(0x0042, 0x0323, 0x0302), "B stacks none: one mark below, one above")
        self.assertEqual(page.reference_text(acute), text(0x0065, 0x0301, 0x0020, 0x0065, 0x0301, 0x0302), "the mark alone, then with a mark on it")
        self.assertEqual(page.reference_text(found["ogonekcomb"]), text(0x0065, 0x0328), "nothing stacks on an ogonek")
        scene = page.scene(e)
        names = [part[0] for part in scene["parts"]]
        self.assertEqual(names, ["e", "circumflexcomb", "acutecomb", "dotbelowcomb", "ogonekcomb"])
        under, upper = scene["parts"][1], scene["parts"][2]
        on, by = circumflex.placed()[u"top"], acute.placed()[u"_top"]
        self.assertEqual(upper[3:], (under[3] + on[0] - by[0], under[4] + on[1] - by[1]),
                         "the acute hangs on the circumflex's own anchor")
        self.assertEqual(scene["ranges"], [(1, 2), (3, 4), (4, 5)], "the second mark is shown, not moved from here")
        self.assertEqual(len(page.edits), len(scene["ranges"]))
        self.assertEqual([part[0] for part in page.scene(b)["parts"]], ["B", "circumflexcomb", "dotbelowcomb"],
                         "no stack on a letter that stacks none")
        scene = page.scene(acute)
        self.assertEqual([part[0] for part in scene["parts"]], ["e", "acutecomb", "circumflexcomb"])
        self.assertEqual(scene["ranges"], [(1, 2), (2, 3)])
        self.assertEqual(page.edits[1], (acute, u"top", 1), "dragging the mark on it moves the anchor the next attaches to")
        before = scene["parts"][2]
        acute.adjust = {u"top": [0, 10]}
        after = page.scene(acute)["parts"][2]
        self.assertEqual((after[3], after[4]), (before[3], before[4] + 10))


def text(*codes):
    """The characters of these code points (letters with their combining marks, spelled out in ASCII)."""
    return u"".join(ac.unichr_(code) for code in codes)


class Boxes(object):
    """A painter path, as the boxes of its parts (QPainterPath, stubbed)."""

    def __init__(self, boxes=()):
        self.boxes = list(boxes)

    def addPath(self, other):
        self.boxes += other.boxes

    def intersects(self, other):
        return any(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3] for a in self.boxes for b in other.boxes)


def path_gui():
    """QtGui with the paths, transforms, and stroker AccentsDialog.closeness measures with, stubbed."""
    class Transform(object):
        def __init__(self, sx, _a, _b, sy, x, y):
            self.sx, self.sy, self.x, self.y = sx, sy, x, y

        def map(self, path):
            return Boxes((l * self.sx + self.x, b * self.sy + self.y, r * self.sx + self.x, t * self.sy + self.y)
                         for l, b, r, t in path.boxes)

    class Stroker(object):
        def setWidth(self, width):
            self.half = width / 2.0

        def createStroke(self, path):
            return Boxes((l - self.half, b - self.half, r + self.half, t + self.half) for l, b, r, t in path.boxes)

    return Stub(QPainterPath=Boxes, QTransform=Transform, QPainterPathStroker=Stroker)


def one_mark(code, base, root, side, glyph):
    return ac.Recipe(ac.unichr_(code), name=u"uni%04X" % code, base=base,
                     marks=[ac.Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)])])


class TouchTests(unittest.TestCase):
    """A mark that joins its letter (ogonek, cedilla, horn) is right when it touches it: the owner's report
    of 2026-11-12 (the warning was the other way round)."""

    def test_joined_marks_are_judged_the_opposite_way(self):
        horn = one_mark(0x01A1, "o", "horn", "right", "horn")
        self.assertEqual(ac.touch_note(horn, [(True, True, False, False)], 12), u"", "a horn touching its letter: good")
        apart = ac.touch_note(horn, [(False, True, False, False)], 12)
        self.assertIn(ac.APART, apart, "close is not joined")
        self.assertIn(u"a horn joins it", apart)
        for root, side in (("ogonek", "below"), ("cedilla", "below")):
            joined = one_mark(0x0105, "a", root, side, root)
            self.assertEqual(ac.touch_note(joined, [(True, True, False, False)], 12), u"", root)
            self.assertIn(ac.APART, ac.touch_note(joined, [(False, False, False, False)], 12), root)
        acute = one_mark(0xF3, "o", "acute", "above", "acute")
        self.assertEqual(ac.touch_note(acute, [(False, False, False, False)], 12), u"")
        self.assertIn(u"overlaps", ac.touch_note(acute, [(True, True, False, False)], 12))
        self.assertIn(u"within 12 units", ac.touch_note(acute, [(False, True, False, False)], 12))
        comma = one_mark(0x0137, "k", "cedilla", "below", "commaaccent")
        comma.marks[0].convention = u"the comma below fonts draw for Unicode's cedilla"
        self.assertIn(u"overlaps", ac.touch_note(comma, [(True, True, False, False)], 12), "a comma below hangs clear")
        caron = one_mark(0x010F, "d", "caronvertical", "topright", "caron.alt")
        self.assertIn(u"overlaps", ac.touch_note(caron, [(True, True, False, False)], 12),
                      "a vertical caron stands beside its letter")

    def test_a_joined_mark_still_keeps_clear_of_the_other_marks(self):
        stacked = ac.Recipe(ac.unichr_(0x1EDF), base="o",
                            marks=[ac.Mark("horn", "right", [("horn", 1.0, 1.0, 0.0, 0.0)]),
                                   ac.Mark("hookabove", "above", [("hookabove", 1.0, 1.0, 0.0, 0.0)])])
        self.assertEqual(ac.touch_note(stacked, [(True, True, False, False), (False, False, False, False)], 12), u"")
        self.assertIn(u"within 12 units of another mark",
                      ac.touch_note(stacked, [(True, True, False, True), (False, False, False, True)], 12))
        self.assertIn(u"overlaps another mark",
                      ac.touch_note(stacked, [(True, True, True, True), (False, False, True, True)], 12))

    def dialog(self):
        inks = {"o": ac.Ink(40, -10, 460, 480, advance=500), "horn": ac.Ink(0, 400, 120, 560),
                "acute": ac.Ink(0, 500, 100, 600)}

        def box(name):
            ink = inks[name]
            return Boxes([(ink.left, ink.bottom, ink.right, ink.top)])
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.master, dialog.package = "Regular", Stub(upm=1000)
        dialog.inks = {"Regular": type("Ink", (object,), {"__call__": lambda self, name: inks.get(name),
                                                          "path": lambda self, name: (box(name), inks[name].advance)})()}
        dialog.placements = {"Regular": ac.Placement(1000, {"format": 1, "gap": {"acute lower": 0.05},
                                                            "side_offset": {"above lower": 0.0}})}
        dialog.metrics = lambda package: None
        return dialog

    def test_the_dialog_measures_a_mark_against_its_letter_alone(self):
        dialog = self.dialog()
        horn, acute = one_mark(0x01A1, "o", "horn", "right", "horn"), one_mark(0xF3, "o", "acute", "above", "acute")
        saved = ac._qt
        try:
            ac._qt = lambda: (None, path_gui())
            self.assertEqual(dialog.closeness(horn), u"", "the horn as placed overlaps its letter a little: good")
            horn.adjust = {0: [100.0, 0.0, 1.0, 1.0]}
            self.assertIn(ac.APART, dialog.closeness(horn), "moved clear of its letter: a warning")
            self.assertEqual(dialog.closeness(acute), u"")
            acute.adjust = {0: [0.0, -60.0, 1.0, 1.0]}
            self.assertIn(u"overlaps", dialog.closeness(acute))
            mark = one_mark(0x031B, "o", "horn", "right", "horn")
            mark.standalone = True
            mark.adjust = {0: [100.0, 0.0, 1.0, 1.0]}
            self.assertEqual(dialog.closeness(mark), u"", "a mark made alone has no letter to touch")
        finally:
            ac._qt = saved

    def test_the_log_names_the_two_faults_apart(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        lines = []
        dialog.log = Stub(add=lambda text, level="info": lines.append((level, text)))
        dialog.ak = Stub(b=lambda text: u"%s" % text, glyph_links=lambda chars: u" ".join(chars))
        dialog.log_touches([(u"a", u"acute overlaps its letter or another mark"),
                            (u"b", u"horn %s (a horn joins it)" % ac.APART),
                            (u"c", u"ogonek %s (an ogonek joins it)" % ac.APART)], "built")
        self.assertEqual(lines, [
            ("warning", u"1 glyph built with a mark within 12 units of its letter or another mark: a. Look at it."),
            ("warning", u"2 glyphs built with a mark that joins its letter (ogonek, cedilla, horn) and does not "
                        u"touch it: b c. Look at them.")])
        del lines[:]
        dialog.log_touches([(u"b", u"horn %s (a horn joins it)" % ac.APART)], "now")
        self.assertEqual(lines[0][1], u"1 letter now has a mark that joins its letter (ogonek, cedilla, horn) and does "
                                      u"not touch it: b. Look at it.")
        del lines[:]
        dialog.log_touches([(u"a", u"x"), (u"d", u"y")], "")
        self.assertEqual(lines[0][1], u"2 letters come within 12 units of their letter or another mark: a d. Look at them.")
        del lines[:]
        dialog.log_touches([], "built")
        self.assertEqual(lines, [], "nothing to name")


O_GRAVE, O_HORN_HOOK = ac.unichr_(0xF2), ac.unichr_(0x1EDF)


class GoToTests(unittest.TestCase):
    """A glyph named in the log, or drawn beside the edited one, clicked: its row shown, whether the list
    has it or not (the owner's reports of 2026-11-12)."""

    def dialog(self, listed=(), in_font=(), existing_on=False):
        """An AccentsDialog whose list has the listed characters; in_font: {character: glyph name}."""
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        in_font = dict(in_font)
        dialog.done = done = {"selected": [], "runs": 0, "opened": [], "log": []}
        dialog.recipes = [ac.Recipe(ch, name=u"uni%04X" % ord(ch), base="o") for ch in listed]
        dialog.select_recipe = lambda recipe: done["selected"].append(recipe.char) or True
        dialog.log = Stub(add=lambda text, level="info": done["log"].append((level, text)))
        dialog.ak = Stub(b=lambda text: u"%s" % text, i=lambda text: u"%s" % text, html=lambda text: u"%s" % text)
        dialog.tabs = Stub(currentIndex=0)
        box = dialog.existing_box = Stub(checked=existing_on, blockSignals=lambda on: None)
        box.setChecked = lambda on: setattr(box, "checked", on)
        dialog.package = Stub(findUnicode=lambda code: Stub(name=in_font[ac.unichr_(code)], isNull=False)
                              if ac.unichr_(code) in in_font else None)
        font = ac.Font(["o", "horn", "hookabove", "grave"] + list(in_font.values()),
                       [("o", 0x6F)] + [(name, ord(ch)) for ch, name in in_font.items()])
        dialog.font_read = lambda: font
        dialog.characters = lambda: [O_GRAVE, O_HORN_HOOK]

        def run():  # the list read again: the font's own glyphs listed when the box is on, or one shown
            done["runs"] += 1
            dialog.recipes = ac.plan(font, dialog.characters(), box.checked, getattr(dialog, "shown_existing", ()))
        dialog.run = run
        dialog.open_glyph = lambda name: done["opened"].append(name) and None
        return dialog, done

    def test_a_listed_glyph_is_selected(self):
        dialog, done = self.dialog(listed=[O_HORN_HOOK])
        self.assertEqual(dialog.go_to_char(O_HORN_HOOK), "selected")
        self.assertEqual(dialog.go_to_char(text(0x006F, 0x031B, 0x0309)), "selected", "named decomposed: the same letter")
        self.assertEqual(done["selected"], [O_HORN_HOOK, O_HORN_HOOK])
        self.assertEqual((done["runs"], done["opened"], done["log"]), (0, [], []))

    def test_a_built_glyph_that_left_the_list_is_listed_again(self):
        dialog, done = self.dialog(in_font={O_HORN_HOOK: "ohornhookabove"})
        self.assertEqual(dialog.go_to_char(O_HORN_HOOK), "listed")
        self.assertFalse(dialog.existing_box.checked, "Also list existing glyphs left off: only this glyph is listed")
        self.assertEqual([(r.char, r.existing, r.checked) for r in dialog.recipes if r.existing],
                         [(O_HORN_HOOK, "ohornhookabove", False)], "the font's own glyph, unchecked, and no other")
        self.assertEqual((done["runs"], done["selected"], done["opened"]), (1, [O_HORN_HOOK], []))
        self.assertIn(u"listed to show it, unchecked, and selected (Also list existing glyphs stays off)",
                      done["log"][0][1])
        self.assertEqual(done["log"][0][0], "info", "not a warning: it did what was asked")

    def test_check_all_leaves_a_glyph_listed_to_show_it(self):
        """Showing the font's own glyph switched Also list existing glyphs on quietly, and Check all then
        checked every glyph the font has to be rebuilt. Check all reaches such a row only once the box is
        on."""
        dialog, done = self.dialog(listed=[O_GRAVE], in_font={O_HORN_HOOK: "ohornhookabove"})
        dialog.go_to_char(O_HORN_HOOK)
        rows = [Row(index, False) for index in range(len(dialog.recipes))]
        mine = [index for index, r in enumerate(dialog.recipes) if r.existing]
        self.assertEqual(len(mine), 1)
        self.assertTrue(len(rows) > 1, "and a row to build")
        dialog.shown_items = lambda: [(row, row.index) for row in rows]
        dialog.tree = Stub(blockSignals=lambda on: None)
        dialog.update_buttons = lambda: None
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            dialog.check_all(True)
            self.assertEqual([row.checked for row in rows], [index not in mine for index in range(len(rows))])
            rows[mine[0]].checked = True  # checked by hand
            dialog.check_all(False)
            self.assertFalse(any(row.checked for row in rows), "Check none reaches every row shown")
            dialog.existing_box.checked = True  # ticked by the user: Check all means the font's own glyphs too
            dialog.check_all(True)
            self.assertTrue(all(row.checked for row in rows))
        finally:
            ac._qt = saved

    def test_a_glyph_the_list_cannot_have_opens_in_a_glyph_window(self):
        dialog, done = self.dialog(in_font={O_HORN_HOOK: "ohornhookabove"})
        dialog.characters = lambda: [O_GRAVE]  # another set chosen since: existing glyphs would not list it
        self.assertEqual(dialog.go_to_char(O_HORN_HOOK), "opened")
        self.assertFalse(dialog.existing_box.checked, "not switched on for nothing")
        self.assertEqual((done["runs"], done["opened"]), (0, ["ohornhookabove"]))
        dialog, done = self.dialog(in_font={O_HORN_HOOK: "ohornhookabove"}, existing_on=True)
        self.assertEqual(dialog.go_to_char(O_HORN_HOOK), "opened", "existing glyphs listed already, and it is not among them")
        self.assertEqual(done["opened"], ["ohornhookabove"])

    def test_a_glyph_neither_listed_nor_in_the_font_is_said_so(self):
        dialog, done = self.dialog()
        self.assertIsNone(dialog.go_to_char(O_HORN_HOOK))
        self.assertEqual(done["log"], [("warning", O_HORN_HOOK + u" is not in the list, and the font has no glyph for it.")])
        self.assertEqual((done["runs"], done["opened"]), (0, []))

    def test_a_log_link_reaches_its_glyph(self):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as kerning
        dialog, done = self.dialog(in_font={O_HORN_HOOK: "ohornhookabove"})
        dialog.ak.linked_char = kerning.linked_char
        link = kerning.glyph_links([O_HORN_HOOK])
        target = link.split(u'"')[1]
        dialog.log_link(target)
        self.assertEqual(done["selected"], [O_HORN_HOOK], "built since, off the list: listed again and selected")
        dialog.log_link(u"nothing")
        self.assertEqual(done["log"][-1][0], "warning")
        dialog.go_to_char = lambda ch: 1 / 0
        dialog.log_link(target)  # (a signal's handler never raises)
        self.assertEqual(done["log"][-1][0], "error")

    def test_the_letter_beside_the_edited_glyph_goes_to_its_row(self):
        dialog, done = self.dialog(listed=[O_HORN_HOOK], in_font={O_GRAVE: "ograve"})
        dialog.editor = Stub(scene={"chars": {"after": O_GRAVE}, "letters": ("o", "ograve")})
        self.assertIsNone(dialog.neighbor_char("before"), "the plain letter has no marks to place")
        self.assertEqual(dialog.neighbor_char("after"), O_GRAVE)
        shots = []
        saved = ac._qt
        try:
            ac._qt = lambda: (Stub(QTimer=Stub(singleShot=lambda ms, call: shots.append(call))), None)
            self.assertFalse(dialog.neighbor_clicked("before"))
            self.assertTrue(dialog.neighbor_clicked("after"))
        finally:
            ac._qt = saved
        self.assertEqual((len(shots), done["selected"]), (1, []), "once the click is over")
        shots[0]()
        self.assertEqual(done["selected"], [O_GRAVE], "the font's own letter: listed, its row selected")
        self.assertFalse(dialog.existing_box.checked, "the box left as it was")
        dialog.editor.scene = None
        self.assertFalse(dialog.neighbor_clicked("after"))

    def test_the_letter_beside_is_never_the_glyph_itself(self):
        dialog, done = self.dialog(in_font={O_GRAVE: "ograve", ac.unichr_(0xF3): "oacute"})
        grave = ac.Recipe(O_GRAVE, name="ograve", base="o")
        self.assertEqual(dialog.sibling(grave), ("oacute", ac.unichr_(0xF3)))
        self.assertEqual(dialog.sibling(ac.Recipe(ac.unichr_(0xF4), base="o")), ("ograve", O_GRAVE))
        self.assertEqual(dialog.sibling(ac.Recipe(ac.unichr_(0xE9), base="e")), (None, None))


class EditorClickTests(unittest.TestCase):
    """The mark editor's clicks on the letters beside the edited glyph, Qt stubbed."""

    def editor(self, owner):
        class Widget(object):
            def __init__(self):
                self.cursor = None

            def setFocusPolicy(self, policy):
                pass

            def setMouseTracking(self, on):
                pass

            def setMinimumHeight(self, height):
                pass

            def setFocus(self):
                pass

            def update(self):
                pass

            def setCursor(self, cursor):
                self.cursor = cursor
        qt = Stub(StrongFocus=1, LeftButton=1, SizeAllCursor="move", ArrowCursor="arrow", PointingHandCursor="hand",
                  SizeFDiagCursor="f", SizeBDiagCursor="b", SizeVerCursor="v", SizeHorCursor="h")
        saved = ac._qt
        try:
            ac._qt = lambda: (Stub(Qt=qt), Stub(QWidget=Widget))
            editor = ac.make_editor(owner)
        finally:
            ac._qt = saved
        part = [("o", 1.0, 1.0, 0.0, 0.0)]
        editor.scene = {"glyphs": [(part, 500.0, "before"), (part, 500.0, "new"), (part, 500.0, "after")],
                        "parts": part, "ranges": [], "ink": lambda name: None, "upm": 1000.0}
        editor.view = (1.0, 0.0, 0.0)  # one pixel a unit, the origin at the left
        return editor

    def event(self, x):
        return Stub(button=lambda: 1, pos=lambda: Stub(x=lambda: x, y=lambda: 0))

    def test_a_click_on_the_other_letter_goes_to_it_and_opens_nothing(self):
        calls = []
        owner = Stub(neighbor_clicked=lambda role: calls.append(("go", role)) or role == "after",
                     neighbor_char=lambda role: u"x" if role == "after" else None,
                     mark_selected=lambda index: None, editor_double_clicked=lambda: calls.append(("open",)))
        editor = self.editor(owner)
        editor.mousePressEvent(self.event(1200))
        self.assertEqual(calls, [("go", "after")])
        editor.mouseDoubleClickEvent(self.event(700))  # (the list moved on: the glyph itself is under the pointer now)
        self.assertEqual(calls, [("go", "after")], "the same click's second half opens no Glyph window")
        editor.mouseDoubleClickEvent(self.event(700))
        self.assertEqual(calls[-1], ("open",), "a double-click of its own does")
        del calls[:]
        editor.mousePressEvent(self.event(100))  # the plain letter: asked, and nothing to go to
        editor.mouseDoubleClickEvent(self.event(100))
        self.assertEqual(calls, [("go", "before")], "a neighbor opens nothing")
        editor.mouseMoveEvent(self.event(1200))
        self.assertEqual(editor.cursor, "hand")
        editor.mouseMoveEvent(self.event(100))
        self.assertEqual(editor.cursor, "arrow")

    def test_an_owner_without_neighbors_is_left_alone(self):
        editor = self.editor(Stub(mark_selected=lambda index: None))  # (the Mark anchors tab's editor)
        editor.mousePressEvent(self.event(1200))
        editor.mouseMoveEvent(self.event(1200))
        self.assertEqual((editor.went, editor.cursor), (False, "arrow"))


# -- Diacritics: the owner's reports of 2026-11-13 ---------------------------------------------------

def font_check():
    """Font Check, as Diacritics loads it beside itself (its bundled font, vertical metrics, high-value list)."""
    sys.path.insert(0, os.path.join(HERE, os.pardir, "checks"))
    import freelab_font_check
    return freelab_font_check


def winding(contours, x, y):
    """The winding number of closed polygons [[(x, y)]] around a point: what a renderer filling by
    nonzero winding counts (ink where it is not 0)."""
    total = 0
    for points in contours:
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
            if (y0 <= y) != (y1 <= y):
                across = x0 + (y - y0) * (x1 - x0) / float(y1 - y0)
                if across > x:
                    total += 1 if y1 > y0 else -1
    return total


SQUARE = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]  # counterclockwise


def moved(points, sx, sy, dx, dy):
    """A contour as a component scaled and moved draws it."""
    return [(sx * x + dx, sy * y + dy) for x, y in points]


class Recorder(object):
    """A Qt object that keeps what it was called with (a painter path, a painter, a pixmap, a font)."""

    def __init__(self, *args):
        self.args, self.calls = args, []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def call(*args):
            self.calls.append((name,) + args)
            return self
        return call

    def named(self, name):
        return [call[1:] for call in self.calls if call[0] == name]


class Box(object):
    """A QRectF's edges."""

    def __init__(self, left, right):
        self.edges = (left, right)

    def left(self):
        return self.edges[0]

    def right(self):
        return self.edges[1]

    def width(self):
        return self.edges[1] - self.edges[0]


class DirectionTests(unittest.TestCase):
    """A hole where a mark overlaps a letter: the reference picture's fill rule, and mirrored components."""

    BARE = ac.Font(["a", "o", "period", "asciicircum", "hyphen", "comma", "breve", "quoteleft", "quoteright",
                    "grave", "acute", "asciitilde", "degree", "quotedbl", "quotesingle", "underscore", "plus"],
                   [("a", 0x61), ("o", 0x6F), ("period", 0x2E), ("asciicircum", 0x5E), ("hyphen", 0x2D),
                    ("comma", 0x2C), ("breve", 0x2D8), ("quoteleft", 0x2018), ("quoteright", 0x2019), ("grave", 0x60),
                    ("acute", 0xB4), ("asciitilde", 0x7E), ("degree", 0xB0), ("quotedbl", 0x22),
                    ("quotesingle", 0x27), ("underscore", 0x5F), ("plus", 0x2B)])

    def test_a_mirror_reverses_a_contour_and_a_half_turn_does_not(self):
        base = SQUARE
        # the mark's square laid over the letter's top right corner, mirrored up and down, then turned
        mirrored = moved(SQUARE, 1.0, -1.0, 50.0, 150.0)
        turned = moved(SQUARE, -1.0, -1.0, 150.0, 150.0)
        plain = moved(SQUARE, 1.0, 1.0, 50.0, 50.0)
        for mark in (mirrored, turned, plain):
            self.assertEqual(sorted(set(mark)), [(50.0, 50.0), (50.0, 150.0), (150.0, 50.0), (150.0, 150.0)],
                             "the same square, over the letter's corner")
        inside, mark_only = (75.0, 75.0), (125.0, 125.0)
        self.assertEqual(winding([base, plain], *inside), 2, "two parts wound alike: ink where they overlap")
        self.assertEqual(winding([base, turned], *inside), 2, "a half turn keeps the direction: ink")
        self.assertEqual(winding([base, mirrored], *inside), 0, "a mirror reverses it: a hole, by nonzero winding")
        self.assertEqual(winding([base, mirrored], *mark_only), -1, "the mirrored part alone is still ink")
        self.assertTrue(ac.reverses_direction(1.0, -1.0))
        self.assertTrue(ac.reverses_direction(-1.0, 1.0))
        self.assertFalse(ac.reverses_direction(-1.0, -1.0), "a half turn")
        self.assertFalse(ac.reverses_direction(0.8, 1.2))
        self.assertTrue(ac.reverses_direction(0.0, 0.0, 1.0, 1.0), "sheared over: its determinant is negative")

    def test_no_mark_is_built_mirrored(self):
        for code in sorted(ac.MARKS):
            for case in ("lower", "upper"):
                mark = ac.make_mark(self.BARE, code, case)
                for part in (mark.parts if mark is not None else []):
                    self.assertFalse(ac.reverses_direction(part[1], part[2]), "U+%04X %r" % (code, part))
        caron = ac.make_mark(self.BARE, 0x030C, "lower")
        self.assertEqual(caron.parts[0][:3], ("asciicircum", -1.0, -1.0), "a caron: the circumflex turned, not mirrored")
        self.assertIn(u"turned upside down", caron.label())
        inverted = ac.make_mark(self.BARE, 0x0311, "lower")
        self.assertEqual(inverted.parts[0][:3], ("breve", -1.0, -1.0), "an inverted breve: the breve turned")
        below = ac.make_mark(self.BARE, 0x0323, "lower")
        self.assertEqual(below.parts[0][1:3], (1.0, 1.0), "a mark below borrowed from above is moved, never flipped")

    def test_a_turned_mark_is_placed_like_any_other(self):
        ink = {"o": ac.Ink(40, -10, 460, 480, advance=500), "asciicircum": ac.Ink(100, 400, 300, 700)}.get
        recipe = ac.Recipe(ac.unichr_(0x01D2), u"ocaron", "o", [ac.make_mark(self.BARE, 0x030C, "lower")])
        parts, _ = ac.place(recipe, ink, ac.Placement(1000.0, MODEL))
        left, bottom, right, top = ac.parts_box(parts[1:], ink)
        self.assertGreater(bottom, 480, "over the letter")
        self.assertLess(abs((left + right) / 2.0 - 250), 2, "centered on it")
        self.assertEqual(ac.reversal_note(parts, ink), u"")

    def test_a_mirrored_part_is_named_in_its_row_and_the_log(self):
        ink = {"o": ac.Ink(40, -10, 460, 480, advance=500), "breve": ac.Ink(100, 500, 300, 600)}.get
        clear = [("o", 1.0, 1.0, 0.0, 0.0), ("breve", 1.0, -1.0, 0.0, 1200.0)]
        note = ac.reversal_note(clear, ink)
        self.assertIn(u"breve is mirrored, its contours reversed", note)
        self.assertIn(u"correct the contour direction", note)
        over = [("o", 1.0, 1.0, 0.0, 0.0), ("breve", 1.0, -1.0, 0.0, 1000.0)]  # its ink from 400 to 500: on the o
        note = ac.reversal_note(over, ink)
        self.assertIn(u"mirrored and overlaps another part", note)
        self.assertIn(u"decompose the glyph and remove overlap", note)
        self.assertFalse(note.endswith(u"."), "a note in a cell")
        self.assertEqual(ac.mirrored_text(1), u"1 glyph built with a mirrored component")
        self.assertEqual(ac.mirrored_text(2), u"2 glyphs built with a mirrored component")
        self.assertTrue(ac.MIRRORED_ADVICE.endswith(u"."), "a sentence of the log keeps its period")

        def shape(name, m11, m22, m12=0.0, m21=0.0, component=True):
            return Stub(isComponent=component, shapeData=Stub(componentGlyph=name),
                        transform=Stub(m11=lambda: m11, m22=lambda: m22, m12=lambda: m12, m21=lambda: m21))
        layer = Stub(shapes=[shape("o", 1.0, 1.0), shape("breve", 1.0, -1.0), shape("acute", -1.0, -1.0),
                             shape("hook", 0.0, 0.0, 1.0, 1.0), shape("drawn", 1.0, -1.0, component=False)])
        self.assertEqual(ac.mirrored_components(layer), [u"breve", u"hook"], "a half turn is no mirror")

    def test_a_glyph_built_through_a_mirrored_component_is_named(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        inner = Stub(isComponent=True, shapeData=Stub(componentGlyph="caron"),
                     transform=Stub(m11=lambda: 1.0, m22=lambda: -1.0, m12=lambda: 0.0, m21=lambda: 0.0,
                                    dx=lambda: 0.0, dy=lambda: 900.0))
        glyphs = {"asciicircum": Stub(isNull=False, getLayerByName=lambda master: Stub(shapes=[inner]))}
        dialog.package, dialog.master = Stub(findName=glyphs.get), "Regular"
        dialog.inks = {"Regular": {"o": ac.Ink(40, -10, 460, 480), "caron": ac.Ink(100, 500, 300, 700)}.get}
        recipe = ac.Recipe(ac.unichr_(0x01D2), u"ocaron", "o")
        recipe.placed_parts = [("o", 1.0, 1.0, 0.0, 0.0), ("asciicircum", -0.8, -0.8, 400.0, 1300.0)]
        notes = dialog.reversal_notes(recipe)
        self.assertEqual(len(notes), 1)
        self.assertIn(u"caron is mirrored", notes[0], "the font's own ^ is a mirrored caron: the half turn of it is one")
        recipe.placed_parts = [("o", 1.0, 1.0, 0.0, 0.0), ("caron", -0.8, -0.8, 400.0, 1300.0)]
        self.assertEqual(dialog.reversal_notes(recipe), [], "a glyph of its own, turned: no mirror")

    def qt(self, paths):
        def path():
            made = Recorder()
            made.boundingRect = lambda: Stub(width=lambda: 100.0, left=lambda: 0.0)
            paths.append(made)
            return made
        gui = Stub(QFont=Recorder, QPainterPath=path, QPixmap=Recorder, QColor=Recorder, QPainter=Recorder,
                   QBrush=Recorder, QTransform=lambda *values: Stub(map=lambda path: (values, path)),
                   QPalette=Stub(WindowText=1))
        gui.QPainter.Antialiasing = 1
        return Stub(QPointF=lambda x, y: (x, y), Qt=Stub(WindingFill="winding")), gui

    def test_the_reference_is_filled_as_text_is(self):
        paths = []
        saved = ac._qt
        try:
            ac._qt = lambda: self.qt(paths)
            ac.reference_picture(u"A", u"Noto Sans", Stub(color=lambda role: "ink"))
        finally:
            ac._qt = saved
        calls = [call[0] for call in paths[0].calls]
        self.assertEqual(paths[0].named("setFillRule"), [("winding",)],
                         "not Qt's even-odd rule, which punched a hole where a mark overlapped")
        self.assertLess(calls.index("setFillRule"), calls.index("addText"))

    def test_a_glyph_of_components_is_one_outline_filled_by_winding(self):
        paths = []
        outlines = {"o": "o-outline", "breve": "breve-outline"}
        ink = Stub(path=lambda name: (outlines.get(name), 500))
        saved = ac._qt
        try:
            ac._qt = lambda: self.qt(paths)
            whole = ac.joined_path(ink, [("o", 1.0, 1.0, 0.0, 0.0), ("breve", 1.0, -1.0, 20.0, 900.0),
                                         ("nothing", 1.0, 1.0, 0.0, 0.0)])
        finally:
            ac._qt = saved
        self.assertEqual(whole.named("setFillRule"), [("winding",)])
        self.assertEqual(whole.named("addPath"), [(((1.0, 0.0, 0.0, 1.0, 0.0, 0.0), "o-outline"),),
                                                  (((1.0, 0.0, 0.0, -1.0, 20.0, 900.0), "breve-outline"),)],
                         "each outline transformed as its component is, a mirror included: its hole is drawn")


class LimitTests(unittest.TestCase):
    """The limits a built glyph can reach, drawn in the editors."""

    def test_equal_limits_share_a_line_and_a_label(self):
        check = font_check()
        values = check.VerticalMetrics(ascender=880, descender=-120, typo_ascender=880, hhea_ascender=880,
                                       typo_descender=-120, hhea_descender=-240, win_ascent=1100, win_descent=300)
        found = ac.limit_values(lambda field: getattr(values, field), ac.Metrics(1000, 880, -120, 700))
        self.assertIn((u"winDescent", -300.0, ac.WINDOWS), found, "winDescent is a depth: drawn under the baseline")
        self.assertIn((ac.LINE_NAME, 1080.0, ac.LINE_NAME), found, "the room of a 120% line: 1.2 em plus the descender")
        self.assertIn((u"font ascender", 880.0, None), found, "a reference line: nothing clips there")
        lines = ac.limit_lines(found, check.merge_names)
        self.assertEqual(lines, [(1100, u"winAscent 1100 (Windows clips above)", True),
                                 (1080, u"120% line 1080 (meets the line above)", True),
                                 (880, u"typo, hhea, and font ascender 880 (macOS clips above)", True),
                                 (-120, u"font and typo descender -120", False),
                                 (-240, u"hhea descender -240 (macOS clips below)", True),
                                 (-300, u"winDescent -300 (Windows clips below)", True),
                                 (-320, u"120% line -320 (meets the line below)", True)])
        self.assertEqual(ac.limit_lines([(u"a", 10.2), (u"b", 9.8), (u"c", None)]), [(10, u"a, b 10", False)],
                         "without Font Check's way of joining names: commas; lines given without a kind are references")
        unset = check.VerticalMetrics(ascender=880, descender=-120, typo_ascender=None, win_ascent=0)
        self.assertEqual(ac.limit_values(lambda field: getattr(unset, field)),
                         [(u"font ascender", 880.0, None), (u"font descender", -120.0, None)],
                         "a value not set draws no line")

        def broken(field):
            raise RuntimeError(field)
        self.assertEqual(ac.limit_values(broken), [])

    def test_a_limits_label_says_what_happens_past_it(self):
        self.assertEqual(ac.limit_note([ac.WINDOWS], True), u"Windows clips above")
        self.assertEqual(ac.limit_note([ac.MACOS, ac.WINDOWS], False), u"Windows and macOS clip below")
        self.assertEqual(ac.limit_note([ac.LINE_NAME], True), u"meets the line above")
        self.assertEqual(ac.limit_note([ac.WINDOWS, ac.LINE_NAME], False), u"Windows clips below; meets the line below")
        self.assertEqual(ac.limit_note([], True), u"", "a reference line says nothing")
        # the owner's font (image 48): the hhea descender and winDescent share a line, the font's and typo's another
        owners = [(u"font descender", -120.0, None), (u"typo descender", -120.0, None),
                  (u"hhea descender", -288.0, ac.MACOS), (u"winDescent", -288.0, ac.WINDOWS)]
        self.assertEqual(ac.limit_lines(owners, font_check().merge_names),
                         [(-120, u"font and typo descender -120", False),
                          (-288, u"hhea descender, winDescent -288 (Windows and macOS clip below)", True)])

    def test_only_a_limit_a_mark_crosses_is_tinted(self):
        lines = [(1160, u"winAscent, hhea ascender 1160 (Windows and macOS clip above)", True),
                 (1080, u"120% line 1080 (meets the line above)", True), (880, u"typo and font ascender 880", False),
                 (-120, u"font and typo descender -120", False),
                 (-288, u"hhea descender, winDescent -288 (Windows and macOS clip below)", True)]
        self.assertEqual(ac.crossed_limits(lines, [(0, 700, 100, 1000)]), set(),
                         "an accented capital over the ascender, within every limit: no amber (image 36)")
        self.assertEqual(ac.crossed_limits(lines, [(0, -200, 100, -100)]), set(),
                         "a mark below under the font's descender, inside winDescent: no amber (image 48)")
        self.assertEqual(ac.crossed_limits(lines, [(0, 700, 100, 1100)]), set([1]), "past the room of a 120% line")
        self.assertEqual(ac.crossed_limits(lines, [(0, 700, 100, 1200)]), set([0, 1]), "past winAscent too")
        self.assertEqual(ac.crossed_limits(lines, [(0, -300, 100, -100)]), set([4]), "Windows would clip it")
        self.assertEqual(ac.crossed_limits(lines, [(0, 0, 100, 1080)]), set(), "reaching a limit is not crossing it")
        self.assertEqual(ac.crossed_limits(lines, []), set())
        self.assertEqual(ac.crossed_limits([(1000, u""), (-400, u"")], [(0, -500, 100, 1100)]), set([0, 1]),
                         "an older scene's room, given without a kind: limits")

    def test_the_dialog_reads_them_through_font_check_once(self):
        check = font_check()
        reads = []

        def read_metrics(package):
            reads.append(package)
            return check.VerticalMetrics(ascender=800, descender=-200, win_ascent=950, win_descent=250)
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.ak = Stub(load_sibling=lambda name, module: Stub(read_metrics=read_metrics, merge_names=check.merge_names),
                         font_key=lambda package: u"a.vfc")
        package = Stub(upm=1000, ascender_value=800, descender_value=-200, capsHeight_value=700, master="Regular",
                       fgPackage=Stub(id=1))
        lines = dialog.limits(package)
        self.assertEqual([(label, limit) for _, label, limit in lines],
                         [(u"120% line 1000 (meets the line above)", True), (u"winAscent 950 (Windows clips above)", True),
                          (u"font ascender 800", False), (u"font descender -200", False),
                          (u"winDescent -250 (Windows clips below)", True), (u"120% line -400 (meets the line below)", True)])
        dialog.limits(package)
        self.assertEqual(len(reads), 1, "read once per font and master, not at every move of a dragged mark")

        def no_font_check(name, module):
            raise IOError(name)
        dialog.ak, dialog.limit_cache = Stub(load_sibling=no_font_check, font_key=lambda package: u"a.vfc"), {}
        self.assertEqual([label for _, label, _ in dialog.limits(package)],
                         [u"120% line 1000 (meets the line above)", u"font ascender 800", u"font descender -200",
                          u"120% line -400 (meets the line below)"])

    def test_both_editors_scenes_carry_them(self):
        inks = {"A": ac.Ink(10, 0, 590, 700, advance=600), "acutecomb": ac.Ink(-60, 550, 60, 660)}
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        page.glyphs = ac.plan_anchors([("A", 0x41, "base", inks["A"], {}), ("acutecomb", 0x0301, "mark", inks["acutecomb"], {})],
                                      {}, "latin", 1000, 500)
        page.package, page.scripts, page.script_box = Stub(upm=1000), ["latin"], Stub(currentIndex=0)
        page.ink = type("Ink", (object,), {"__call__": lambda self, name: inks.get(name),
                                           "path": lambda self, name: (None, inks[name].advance)})()
        page.owner = Stub(limits=lambda package: [(880, u"font ascender 880")], warning_rgb=(1, 2, 3))
        scene = page.scene(page.glyphs[0])
        self.assertEqual((scene["limits"], scene["warning"]), ([(880, u"font ascender 880")], (1, 2, 3)))
        self.assertTrue(scene["separate"], "glyphs set together by anchors are each drawn alone, as text is")


class CellTextTests(unittest.TestCase):
    """Cells take no period, and data goes in parentheses (the owner's rules)."""

    def test_built_from(self):
        self.assertEqual(ac.row_text(u"A + gravecomb"), u"A + gravecomb")
        self.assertEqual(ac.row_text(u"A + gravecomb", shift=(25, 4), existing=True),
                         u"A + gravecomb (suggested: mark 25 right, 4 up)")
        self.assertEqual(ac.row_text(u"A + gravecomb", shift=(0, 0), existing=True), u"A + gravecomb (placed as suggested)")
        self.assertEqual(ac.row_text(u"A + gravecomb", shift=None, existing=True),
                         u"A + gravecomb (drawn, not built of components: compare by eye)")
        self.assertEqual(ac.row_text(u"a + caron", refill=True, notes=[u"marks placed by hand"]),
                         u"a + caron (its glyph is in the font, empty: filled when built; marks placed by hand)")
        for text in (ac.row_text(u"A + gravecomb", shift=(25, 4), existing=True, notes=[u"gaps closed to fit a 120% line"]),
                     ac.row_text(u"a + caron", notes=[u"x"])):
            self.assertFalse(text.endswith(u"."))
            self.assertNotIn(u"\N{EM DASH}", text)
            self.assertNotIn(u"\N{MIDDLE DOT}", text)

    def test_counted_texts_follow_their_number(self):
        self.assertEqual([ac.anchors_sentence(n) for n in (0, 1, 2)], [u"0 get anchors", u"1 gets anchors", u"2 get anchors"])
        self.assertEqual([ac.corpus_sentence(n, u"Thai") for n in (0, 1, 2)],
                         [u"0 of the corpus's Thai fonts place theirs", u"the corpus's 1 Thai font places its own",
                          u"2 of the corpus's Thai fonts place theirs"])
        self.assertEqual([ac.units_up(value) for value in (0.2, 1.0, 1.4, 2.0)], [u"1 unit", u"1 unit", u"2 units", u"2 units"])
        acute = one_mark(0xF3, "o", "acute", "above", "acute")
        self.assertIn(u"within 1 unit of", ac.touch_note(acute, [(False, True, False, False)], 1.2))
        self.assertIn(u"within 2 units of", ac.touch_note(acute, [(False, True, False, False)], 2))
        self.assertEqual([ac.search_count(n, total, u"x") for n, total in ((0, 1), (1, 1), (1, 2), (2, 2))],
                         [u"0 of 1 glyph shown", u"1 of 1 glyph shown", u"1 of 2 glyphs shown", u"2 of 2 glyphs shown"])
        self.assertEqual(ac.search_count(3, 3, u"  "), u"", "no search: no count")
        self.assertEqual(ac.propagated_text(1, 0, u"C"), u"Placed the diacritics of 1 letter as on C")
        self.assertEqual(ac.propagated_text(2, 1, u"C"), u"Placed the diacritics of 2 letters as on C (1 put back as suggested)")
        self.assertEqual(ac.propagated_text(2, 2, u"C"), u"Put the diacritics of 2 letters back as suggested, as on C")
        tall = ac.Recipe(O_CIRCUMFLEX_ACUTE, u"x", "o", [ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)])])
        ac.place(tall, inks().get, ac.Placement(1000.0, MODEL), ac.Metrics(1000, 300, -700))
        over = int(tall.notes[-1].split(u" ")[1])
        self.assertTrue(tall.notes[-1].startswith(u"still %d %s too tall" % (over, u"unit" if over == 1 else u"units")),
                        tall.notes[-1])


class ReferenceClusterTests(unittest.TestCase):
    """A reference never shows a mark standing beside its letter (the owner's report of 2026-11-13)."""

    A_GRAVE_ACUTE = text(0x0041, 0x0300, 0x0301)

    def test_a_cluster_unicode_has_one_character_for_is_that_character(self):
        kept, reduced, dropped = ac.settled_clusters([text(0x0041, 0x0302, 0x0301)], lambda cluster: False)
        self.assertEqual((kept, reduced, dropped), ([text(0x1EA4)], 0, 0), "A with circumflex and acute: U+1EA4")
        kept, reduced, dropped = ac.settled_clusters([text(0x0065, 0x0323, 0x0302, 0x0301)], lambda cluster: True)
        self.assertEqual(kept, [text(0x1EC7, 0x0301)], "composed as far as Unicode goes, the rest left to the font")

    def test_a_second_mark_the_font_does_not_stack_is_left_off(self):
        asked = []

        def holds(cluster):
            asked.append(cluster)
            return False
        kept, reduced, dropped = ac.settled_clusters([text(0x0041, 0x0300), self.A_GRAVE_ACUTE], holds)
        self.assertEqual((kept, reduced, dropped), ([text(0x00C0)], 1, 0), "one mark, once: no acute beside the letter")
        self.assertEqual(asked, [text(0x00C0, 0x0301)])
        kept, reduced, dropped = ac.settled_clusters([text(0x0041, 0x0300), self.A_GRAVE_ACUTE], lambda cluster: True)
        self.assertEqual((kept, reduced, dropped), ([text(0x00C0), text(0x00C0, 0x0301)], 0, 0), "a font that stacks it")

    def test_an_example_the_font_cannot_set_at_all_is_absent(self):
        kept, reduced, dropped = ac.settled_clusters([text(0x0E01, 0x0E48), text(0x0E01)], lambda cluster: False)
        self.assertEqual((kept, reduced, dropped), ([text(0x0E01)], 0, 1), "no precomposed Thai: left out; a bare letter stays")
        kept, reduced, dropped = ac.settled_clusters([text(0x0041, 0x0300)], lambda cluster: True, lambda cluster: len(cluster) > 1)
        self.assertEqual(kept, [text(0x0041, 0x0300)], "a font without the one character, which sets the mark itself")
        kept, reduced, dropped = ac.settled_clusters([text(0x0041, 0x0300)], lambda cluster: False, lambda cluster: len(cluster) > 1)
        self.assertEqual((kept, dropped), ([], 1))

    def test_marks_on_their_letter_or_beside_it(self):
        self.assertTrue(ac.ink_holds((5, 65), (5, 65), 100.0), "a mark over its letter")
        self.assertTrue(ac.ink_holds((5, 65), (5, 80), 100.0), "a horn reaches a little past it")
        self.assertFalse(ac.ink_holds((5, 65), (5, 100), 100.0), "an acute standing beside the letter")
        self.assertFalse(ac.ink_holds((5, 65), (-30, 65), 100.0))
        self.assertFalse(ac.ink_holds((5, 65), (5, 80), 100.0, 70.0, 95.0), "the mark took room of its own")
        self.assertTrue(ac.ink_holds((5, 65), (5, 80), 100.0, 70.0, 70.0))

    def test_qt_is_asked_what_it_would_draw(self):
        boxes = {u"A": (5.0, 65.0), self.A_GRAVE_ACUTE: (5.0, 100.0), text(0x0041, 0x0300): (5.0, 65.0)}
        widths = {u"A": 70.0, self.A_GRAVE_ACUTE: 70.0, text(0x0041, 0x0300): 70.0}

        def path():
            made = Recorder()
            made.boundingRect = lambda: Box(*boxes[made.named("addText")[0][2]])
            return made
        gui = Stub(QFont=Recorder, QPainterPath=path, QFontMetricsF=lambda font: Stub(width=lambda drawn: widths[drawn]))
        saved = ac._qt
        try:
            ac._qt = lambda: (Stub(QPointF=lambda x, y: (x, y)), gui)
            self.assertTrue(ac.cluster_holds(u"Noto Sans", text(0x0041, 0x0300)))
            self.assertFalse(ac.cluster_holds(u"Noto Sans JP", self.A_GRAVE_ACUTE), "its ink reaches past the letter")
            boxes[self.A_GRAVE_ACUTE], widths[self.A_GRAVE_ACUTE] = (5.0, 70.0), 110.0
            self.assertFalse(ac.cluster_holds(u"Noto Sans JP", self.A_GRAVE_ACUTE), "the cluster is wider than its letter")
            gui.QFontMetricsF = lambda font: 1 / 0
            self.assertTrue(ac.cluster_holds(u"Noto Sans JP", self.A_GRAVE_ACUTE), "no advances: by the ink alone")
        finally:
            ac._qt = saved

    def test_the_note_says_what_was_left_off(self):
        a = text(0x00C0)
        self.assertEqual(ac.reference_note(a, u"Noto Sans", u"Noto Sans"), a + u" in Noto Sans.")
        self.assertEqual(ac.reference_note(a, u"Noto Sans", u"Bundled Sans"),
                         u"Bundled Sans lacks " + a + u": shown in Noto Sans.")
        self.assertEqual(ac.reference_note(a, u"N", u"N", 1, 0), a + u" in N. N does not stack these marks: 1 example is "
                                                                    u"shown with a mark fewer.")
        self.assertEqual(ac.reference_note(a, u"N", u"N", 2, 1), a + u" in N. N does not stack these marks: 2 examples are "
                                                                    u"shown with a mark fewer. 1 example is left out: N "
                                                                    u"would set its mark beside the letter.")
        self.assertTrue(ac.reference_note(a, u"N", u"N", 0, 2).endswith(u"2 examples are left out: N would set its mark "
                                                                        u"beside the letter."))

    def test_the_anchors_tab_draws_only_what_the_font_sets(self):
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        shown = {}
        page.reference = Stub(clear=lambda: shown.__setitem__("picture", None),
                              setPixmap=lambda picture: shown.__setitem__("picture", picture))
        page.reference_note = Stub(setText=lambda note: shown.__setitem__("note", note))
        page.reference_text = lambda g: text(0x0041, 0x0300) + u" " + self.A_GRAVE_ACUTE
        page.script = lambda: "latin"
        page.owner = Stub(reference_family=lambda codes, more: (u"Noto Sans JP", u"Noto Sans JP"),
                          dialog=Stub(palette=None))
        saved = ac.cluster_holds, ac.reference_picture, ac.has_character
        try:
            ac.cluster_holds = lambda family, cluster: False
            ac.reference_picture = lambda drawn, family, palette: drawn
            ac.has_character = lambda family, code: True
            page.draw_reference(Stub(role="mark"))
            self.assertEqual(shown["picture"], text(0x00C0), "the letter with its one mark, once")
            self.assertIn(u"1 example is shown with a mark fewer", shown["note"])
            ac.has_character = lambda family, code: code < 0x80 or 0x300 <= code < 0x370  # no precomposed letters
            page.draw_reference(Stub(role="mark"))
            self.assertIsNone(shown["picture"], "nothing it can set: no picture, rather than marks beside the letter")
            self.assertEqual(shown["note"], u"Noto Sans JP does not set these marks on their letter: no reference.")

            def broken(family, cluster):
                raise RuntimeError("no Qt")
            ac.cluster_holds = broken
            page.draw_reference(Stub(role="mark"))
            self.assertEqual(shown["picture"], text(0x0041, 0x0300) + u" " + self.A_GRAVE_ACUTE, "not measurable: as written")
        finally:
            ac.cluster_holds, ac.reference_picture, ac.has_character = saved


class ReferenceFallbackTests(unittest.TestCase):
    """A character the chosen reference font lacks is drawn in FreeLab's own fonts (FreeLang) before any
    installed one: Noto is no longer the catch-all."""

    def test_freelang_comes_right_after_the_chosen_font(self):
        has = {u"Chosen": set([0x41]), u"Bundled CJK": set([0xAC00]), u"Noto Sans": set([0x41, 0xAC00, 0x10D40]),
               u"Bundled Extra": set([0x10D40])}
        old = ac.has_character
        ac.has_character = lambda family, code: code in has.get(family, ())
        self.addCleanup(lambda: setattr(ac, "has_character", old))
        owner = ac.AccentsDialog.__new__(ac.AccentsDialog)
        owner.reference_chosen, owner.reference_history = u"Chosen", [u"Noto Sans"]
        owner.freelang = [u"Bundled Essential", u"Bundled CJK", u"Bundled Extra"]
        self.assertEqual(owner.reference_family([0x41]), (u"Chosen", u"Chosen"))
        self.assertEqual(owner.reference_family([0xAC00]), (u"Bundled CJK", u"Chosen"), "not the font picked before")
        self.assertEqual(owner.reference_family([0x10D40]), (u"Bundled Extra", u"Chosen"))
        self.assertEqual(owner.reference_family([0x1E6C0]), (None, u"Chosen"))

    def test_the_note_names_freelab_s_fonts_as_one(self):
        names = {u"Bundled Essential": u"Bundled", u"Bundled CJK": u"Bundled"}
        a = text(0xAC00)
        self.assertEqual(ac.reference_note(a, u"Bundled CJK", u"Bundled Essential", names=names), a + u" in Bundled.")
        self.assertEqual(ac.reference_note(a, u"Bundled CJK", u"Chosen", names=names),
                         u"Chosen lacks " + a + u": shown in Bundled.")


class ReferenceFontTests(unittest.TestCase):
    """The reference font: FreeLab's own by default, one choice for both tabs."""

    def test_the_bundled_font_comes_first_set_apart(self):
        rows = ac.reference_rows(u"Bundled Sans", [u"Arial", u"Bundled Sans", u"Noto Sans"])
        self.assertEqual(rows, [(u"Bundled Sans (default)", u"Bundled Sans"), (None, None),
                                (u"Arial", u"Arial"), (u"Noto Sans", u"Noto Sans")], "once, above a separator")
        self.assertEqual(ac.reference_rows(None, [u"Arial"]), [(u"Arial", u"Arial")], "no bundled font: as before")
        self.assertEqual(ac.reference_rows(u"Bundled Sans", [u"Arial"], u"Gone Sans")[-1], (u"Gone Sans", u"Gone Sans"),
                         "a pick saved before is still listed")

    def dialog(self, settings, default=u"Bundled Sans"):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.settings, dialog.reference_history = dict(settings), []
        dialog.choosing_reference, dialog.anchors_read = False, True
        dialog.done = done = {"written": [], "drawn": 0, "registered": 0}

        def register(core, gui):
            done["registered"] += 1
            return default
        dialog.ak = Stub(load_sibling=lambda name, module: Stub(register_list_font=register), state_dir=lambda: u"")
        dialog.reference_boxes = [self.box(), self.box()]
        dialog.draw_reference = lambda r: done.__setitem__("drawn", done["drawn"] + 1)
        dialog.selected = lambda: None
        dialog.anchors = Stub(draw_reference=lambda g: done.__setitem__("drawn", done["drawn"] + 1), selected=lambda: None)
        dialog.log = Stub(add=lambda text, level="info": None)
        return dialog, done

    def box(self):
        box = Stub(rows=[], currentIndex=-1, slots=[])
        box.blockSignals = lambda on: None
        box.addItem = lambda label: box.rows.append(label)
        box.insertSeparator = lambda at: box.rows.insert(at, None)
        box.setCurrentIndex = lambda index: setattr(box, "currentIndex", index)
        box.connect = lambda signal, slot: box.slots.append(slot)
        return box

    def setup(self, dialog):
        saved = ac._qt, ac.write_settings
        try:
            families = Stub(families=lambda: [u"Arial", u"Bundled Sans", u"Noto Sans JP"])
            ac._qt = lambda: (None, Stub(QFontDatabase=lambda: families))
            ac.write_settings = lambda ak, data: dialog.done["written"].append(dict(data))
            dialog.setup_reference()
        finally:
            ac._qt = saved[0]
        return saved[1]

    def test_a_fresh_setting_starts_on_the_bundled_font(self):
        dialog, done = self.dialog({})
        restore = self.setup(dialog)
        try:
            first, second = dialog.reference_boxes
            self.assertEqual(first.rows, [u"Bundled Sans (default)", None, u"Arial", u"Noto Sans JP"])
            self.assertEqual(second.rows, first.rows, "the Mark anchors tab has the same chooser")
            self.assertEqual((done["registered"], dialog.reference_chosen), (1, u"Bundled Sans"))
            self.assertEqual((first.currentIndex, second.currentIndex), (0, 0))
            self.assertEqual(done["written"], [], "the default is not saved: it stays the default")
            second.currentIndex = 3  # Noto Sans JP picked on the Mark anchors tab
            second.slots[0](3)
            self.assertEqual(dialog.reference_chosen, u"Noto Sans JP")
            self.assertEqual(first.currentIndex, 3, "kept in step")
            self.assertEqual(done["written"][-1], {"reference": u"Noto Sans JP"})
            self.assertEqual(done["drawn"], 2, "both references drawn again")
            first.currentIndex = 0  # the bundled font's own entry: the pick taken back
            first.slots[0](0)
            self.assertEqual((dialog.reference_chosen, second.currentIndex), (u"Bundled Sans", 0))
            self.assertEqual(done["written"][-1], {}, "no pick saved any more")
            self.assertEqual(dialog.reference_history, [u"Noto Sans JP"], "the earlier pick still stands in when it lacks a character")
            first.currentIndex = 1  # the separator
            first.slots[0](1)
            self.assertEqual(dialog.reference_chosen, u"Bundled Sans")
        finally:
            ac.write_settings = restore

    def test_a_saved_pick_is_kept(self):
        dialog, done = self.dialog({"reference": u"Noto Sans JP"})
        ac.write_settings = self.setup(dialog)
        self.assertEqual(dialog.reference_chosen, u"Noto Sans JP")
        self.assertEqual(dialog.reference_boxes[0].currentIndex, 3)
        self.assertEqual(dialog.reference_boxes[0].rows[0], u"Bundled Sans (default)", "a click away")

    def test_without_the_bundled_font_the_installed_ones_alone(self):
        dialog, done = self.dialog({}, default=None)
        ac.write_settings = self.setup(dialog)
        self.assertEqual(dialog.reference_boxes[0].rows, [u"Arial", u"Bundled Sans", u"Noto Sans JP"])
        self.assertEqual((dialog.reference_chosen, dialog.reference_boxes[0].currentIndex), (u"", -1),
                         "chosen when the list is read: the installed font with the most of its characters")

    def test_the_line_under_the_reference_names_the_font_drawn(self):
        dialog, done = self.dialog({})
        dialog.reference_chosen, dialog.reference_history = u"Bundled Sans", [u"Noto Sans JP"]
        saved = ac.has_character
        try:
            ac.has_character = lambda family, code: family == u"Noto Sans"
            self.assertEqual(dialog.reference_family([0x01CE]), (u"Noto Sans", u"Bundled Sans"))
            ac.has_character = lambda family, code: family == u"Bundled Sans"
            self.assertEqual(dialog.reference_family([0x01CE]), (u"Bundled Sans", u"Bundled Sans"))
            ac.has_character = lambda family, code: False
            self.assertEqual(dialog.reference_family([0x01CE]), (None, u"Bundled Sans"))
        finally:
            ac.has_character = saved

    def test_font_check_registers_the_family(self):
        check = font_check()
        self.assertTrue(check.LIST_FAMILY and check.LIST_FAMILY == check.LIST_FAMILY.strip(), "a family name")
        self.assertTrue(callable(check.register_list_font), "what Diacritics calls, without Font Check's window")

    def test_the_family_is_named_from_font_checks_constant_only(self):
        ak = Stub(load_sibling=lambda name, module: Stub(LIST_FAMILY=u"Renamed Sans"))
        self.assertEqual(ac.bundled_family_text(ak), u"FreeLab's own <i>Renamed Sans</i>")

        def missing(name, module):
            raise IOError(name)
        self.assertEqual(ac.bundled_family_text(Stub(load_sibling=missing)), u"FreeLab's own font")
        self.assertIn(u"{reference}", ac.HELP, "the help takes the name when the dialog is made")
        with open(ac.__file__.replace(".pyc", ".py"), "rb") as handle:
            source = handle.read().decode("utf-8")
        family = font_check().LIST_FAMILY
        self.assertNotIn(family, source, "the family's name is never written in Diacritics: a rename reaches it")


class HandedOverTests(unittest.TestCase):
    """Every glyph Font Check hands over is a row or is named in the top line (the owner's report: "one
    glyph mentioned, none shown")."""

    MACRON_BELOW = ac.unichr_(0x0331)

    def test_a_glyph_built_since_is_said_to_be_in_the_font(self):
        built = ac.Font(["o", "macron", "macronbelowcomb"], [("o", 0x6F), ("macron", 0xAF), ("macronbelowcomb", 0x0331)])
        recipes = ac.plan(built, [self.MACRON_BELOW])
        self.assertEqual(recipes, [], "the font has it now: no row")
        left_out = ac.left_out_given([self.MACRON_BELOW], recipes, built)
        self.assertEqual(left_out, [("have", [self.MACRON_BELOW])])
        self.assertEqual(ac.left_out_sentence(1, left_out),
                         u"The glyph Font Check handed over is not listed: the font has it already (%s)." % self.MACRON_BELOW)
        before = ac.Font(["o", "macron"], [("o", 0x6F), ("macron", 0xAF)])
        recipes = ac.plan(before, [self.MACRON_BELOW])
        self.assertEqual(ac.left_out_given([self.MACRON_BELOW], recipes, before), [], "listed: nothing to say")
        self.assertEqual(ac.left_out_sentence(1, []), u"")

    def test_each_reason_is_named_with_its_glyphs(self):
        f = ac.Font(["a", "o", "caron", "acaron", "germandbls"], [("a", 0x61), ("o", 0x6F), ("acaron", 0x01CE)])
        given = [A_CARON, ac.unichr_(0x01D2), ac.unichr_(0xDF), ac.unichr_(0x03AC), u"ch", ac.unichr_(0x0142)]
        recipes = ac.plan(f, [c for c in given if len(c) == 1 and ac.script_of(c) != "greek"])
        self.assertEqual([r.char for r in recipes], [ac.unichr_(0x01D2)])
        left_out = ac.left_out_given(given, recipes, f, ["greek"])
        self.assertEqual(left_out, [("have", [A_CARON]), ("script", [ac.unichr_(0x03AC)]),
                                    ("unbuildable", [ac.unichr_(0xDF), ac.unichr_(0x0142)]), ("several", [u"ch"])])
        sentence = ac.left_out_sentence(len(given), left_out, lambda chars: u"+".join(chars))
        self.assertEqual(sentence, u"Of the 6 glyphs Font Check handed over, 5 are not listed: the font has 1 already "
                                   u"(%s), 1 is of a script the font has no letters of (%s), 2 are not built from a "
                                   u"letter and marks (%s+%s), and 1 is not one character (ch)." % (
                                       A_CARON, ac.unichr_(0x03AC), ac.unichr_(0xDF), ac.unichr_(0x0142)))
        self.assertEqual(ac.left_out_sentence(2, [("have", [u"x", u"y"])]),
                         u"None of the 2 glyphs Font Check handed over is listed: the font has 2 already (x y).")
        self.assertEqual(ac.left_out_sentence(2, [("unbuildable", [u"x"])]),
                         u"Of the 2 glyphs Font Check handed over, 1 is not listed: it is not built from a letter and "
                         u"marks (x).")

    def test_a_character_past_the_basic_plane_is_one_character(self):
        """On FontLab's narrow Python 2 a character past U+FFFF is two code units, and was said to be "not
        one character": it is one, on either Python, written either way."""
        pair = text(0xD835, 0xDC00)  # U+1D400 as FontLab's Python holds it
        self.assertEqual(ac.single_code(pair), 0x1D400)
        self.assertEqual(ac.single_code(u"a"), 0x61)
        for several in (u"ch", text(0xD835), text(0xDC00, 0xD835), text(0xD835, 0xDC00, 0x61)):
            self.assertIsNone(ac.single_code(several), repr(several))
        f = ac.Font(["a"], [("a", 0x61)])
        self.assertEqual(ac.left_out_given([pair], [], f, ["greek"]), [("unbuildable", [pair])])
        has = ac.Font(["a", "u1D400"], [("a", 0x61), ("u1D400", 0x1D400)])
        self.assertEqual(ac.left_out_given([pair, u"ch"], [], has), [("have", [pair]), ("several", [u"ch"])])
        if sys.maxunicode > 0xFFFF:  # (a wide Python: the same character as one code unit)
            self.assertEqual(ac.left_out_given([ac.unichr_(0x1D400)], [], has), [("have", [ac.unichr_(0x1D400)])])

    def test_the_top_line_and_the_log_say_it(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        lines = []
        dialog.given, dialog.left_out = [self.MACRON_BELOW], [("have", [self.MACRON_BELOW])]
        dialog.ak = Stub(b=lambda value: u"<b>%s</b>" % value, html=lambda value: u"%s" % value,
                         glyph_links=lambda chars: u"[%s]" % u" ".join(chars))
        dialog.log = Stub(add=lambda line, level="info": lines.append((level, line)))
        self.assertEqual(dialog.left_out_text(), u" The glyph Font Check handed over is not listed: the font has it "
                                                 u"already (<b>%s</b>)." % self.MACRON_BELOW)
        dialog.say_left_out()
        dialog.say_left_out()
        self.assertEqual(lines, [("warning", u"The glyph Font Check handed over is not listed: the font has it already "
                                             u"([%s])." % self.MACRON_BELOW)], "once, its glyph a link")
        dialog.left_out = []
        self.assertEqual(dialog.left_out_text(), u"")
        dialog.say_left_out()
        self.assertEqual(len(lines), 1)

    def test_only_single_characters_are_planned(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.given, dialog.set_box = [u"ch", A_CARON], Stub(currentIndex=0)
        self.assertEqual(dialog.characters(), [A_CARON], "two characters handed over as one are named, not planned")


class Row(object):
    """A list row (QTreeWidgetItem, stubbed): its data, its check, whether it is hidden, its rows."""

    def __init__(self, index, checked=None, rows=()):
        self.index, self.checked, self.rows, self.hidden = index, checked, list(rows), False

    def data(self, column, role):
        return self.index

    def flags(self):
        return 1 if self.checked is not None else 0

    def checkState(self, column):
        return 2 if self.checked else 0

    def setCheckState(self, column, state):
        self.checked = state == 2

    def setHidden(self, on):
        self.hidden = on

    def childCount(self):
        return len(self.rows)

    def child(self, at):
        return self.rows[at]


LIST_QT = Stub(Qt=Stub(UserRole=32, ItemIsUserCheckable=1, Checked=2, Unchecked=0))


class SearchTests(unittest.TestCase):
    """The search fields over the lists (the owner's request of 2026-11-13)."""

    def test_what_finds_a_row(self):
        a_ogonek = ac.unichr_(0x0105)
        row = (u"aogonek", a_ogonek, 0x0105, u"a + ogonekcomb (suggested: mark 25 right)")
        for query in (u"", u"  ", u"aog", u"AOGONEK", a_ogonek, text(0x0061, 0x0328), u"U+0105", u"u+105", u"0105", u"105",
                      u"ogonekcomb", u"25 right"):
            self.assertTrue(ac.row_matches(query, *row), repr(query))
        for query in (u"U+0104", u"0104", u"macron", ac.unichr_(0x0104), u"U+", u"1050"):
            self.assertFalse(ac.row_matches(query, *row), repr(query))
        self.assertTrue(ac.row_matches(u"0105", u"uni0105", a_ogonek, 0x0105), "the name holds it too")
        self.assertTrue(ac.row_matches(u"dead", u"x", u"", 0, u"a deadline"), "hexadecimal digits are text too")
        self.assertFalse(ac.row_matches(u"dead", u"x", u"", 0, u""), "a glyph of no character has no Unicode value")
        self.assertEqual(ac.ascii_lower(u"AbZ" + ac.unichr_(0x0104)), u"abz" + ac.unichr_(0x0104),
                         "A to Z only: the same on FontLab's Python and on Python 3")

    def dialog(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.recipes = [ac.Recipe(ac.unichr_(0x0101), u"amacron", "a"), ac.Recipe(ac.unichr_(0x0105), u"aogonek", "a"),
                          ac.Recipe(ac.unichr_(0x1E0D), u"ddotbelow", "d", missing=u"a dot below")]
        dialog.recipes[1].cell = u"a + ogonekcomb"
        dialog.recipes[1].checked = False
        build, lack = Row(-1, rows=[Row(0, True), Row(1, False)]), Row(-1, rows=[Row(2)])
        dialog.tops = [build, lack]
        dialog.tree = Stub(topLevelItemCount=2, topLevelItem=lambda row: dialog.tops[row], blockSignals=lambda on: None)
        dialog.search, dialog.search_label = Stub(text=u""), Stub(setText=lambda value: setattr(dialog, "count", value))
        dialog.update_buttons = lambda: None
        dialog.log = Stub(add=lambda line, level="info": None)
        return dialog, build, lack

    def test_rows_are_hidden_and_keep_their_checks(self):
        dialog, build, lack = self.dialog()
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            dialog.search.text = u"ogonek"
            dialog.apply_search()
            self.assertEqual([row.hidden for row in build.rows], [True, False])
            self.assertEqual((build.hidden, lack.hidden), (False, True), "a section with no row left is hidden with them")
            self.assertEqual((dialog.hidden, dialog.count), (set([0, 2]), u"1 of 3 glyphs shown"))
            self.assertEqual([row.checked for row in build.rows], [True, False], "a hidden row keeps its check")
            dialog.check_all(True)
            self.assertEqual([row.checked for row in build.rows], [True, True], "the rows shown")
            dialog.check_all(False)
            self.assertEqual([row.checked for row in build.rows], [True, False], "the hidden row as it was")
            dialog.search.text = u"U+1E0D"
            dialog.apply_search()
            self.assertEqual((build.hidden, lack.hidden, dialog.count), (True, False, u"1 of 3 glyphs shown"))
            dialog.search.text = u""
            dialog.apply_search()
            self.assertEqual((dialog.hidden, dialog.count), (set(), u""))
            self.assertFalse(any(row.hidden for row in build.rows + lack.rows + [build, lack]))
            self.assertEqual([row.checked for row in build.rows], [True, False])
        finally:
            ac._qt = saved

    def test_a_list_whose_rows_cannot_be_hidden_still_fills(self):
        dialog, build, lack = self.dialog()
        lines = []
        dialog.log = Stub(add=lambda line, level="info": lines.append(level))
        dialog.ak = Stub(html=lambda value: u"%s" % value)
        build.rows[0].setHidden = lambda on: 1 / 0
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            dialog.search.text = u"ogonek"
            dialog.apply_search()
            dialog.searched()
        finally:
            ac._qt = saved
        self.assertEqual((dialog.hidden, lines), (set(), ["error"]), "every row counts as shown; said once")

    def test_the_anchors_list_is_searched_through_its_sections(self):
        inks = AnchorPageTests.INKS
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        page.glyphs = ac.plan_anchors([("e", 0x65, "base", inks["e"], {}), ("B", 0x42, "base", inks["B"], {}),
                                       ("acutecomb", 0x0301, "mark", inks["acutecomb"], {})], {}, "latin", 1000, 500)
        names = [g.name for g in page.glyphs]
        section = Row(-1, rows=[Row(names.index("e"), True), Row(names.index("B"), True)])
        bases, marks = Row(-1, rows=[section]), Row(-1, rows=[Row(names.index("acutecomb"), True)])
        tops = [bases, marks]
        page.tree = Stub(topLevelItemCount=2, topLevelItem=lambda row: tops[row], blockSignals=lambda on: None)
        page.search, page.search_label = Stub(text=u"U+0042"), Stub(setText=lambda value: setattr(page, "count", value))
        page.update_buttons = lambda: None
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            page.apply_search()
            self.assertEqual([row.hidden for row in section.rows], [True, False])
            self.assertEqual((section.hidden, bases.hidden, marks.hidden), (False, False, True))
            self.assertEqual(page.count, u"1 of 3 glyphs shown")
            page.check_all(False)
            self.assertEqual([row.checked for row in section.rows + marks.rows], [True, False, True], "the row shown only")
            page.search.text = u"acute"
            page.apply_search()
            self.assertEqual((bases.hidden, marks.hidden), (True, False))
        finally:
            ac._qt = saved

    def test_the_anchors_button_counts_the_checked_glyphs_a_search_hides(self):
        """Add checked anchors wrote every checked row, those a search hid too, and did not say so: it
        counts them as Build does."""
        self.assertEqual(ac.anchors_button_text(3, 0), u"Add checked anchors")
        self.assertEqual(ac.anchors_button_text(0, 0), u"Add checked anchors")
        self.assertEqual(ac.anchors_button_text(1, 1), u"Add anchors to 1 checked glyph (1 not shown)")
        self.assertEqual(ac.anchors_button_text(12, 5), u"Add anchors to 12 checked glyphs (5 not shown)")
        inks = AnchorPageTests.INKS
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        page.glyphs = ac.plan_anchors([("e", 0x65, "base", inks["e"], {}), ("B", 0x42, "base", inks["B"], {}),
                                       ("acutecomb", 0x0301, "mark", inks["acutecomb"], {})], {}, "latin", 1000, 500)
        for g in page.glyphs:
            g.checked = True
        names = [g.name for g in page.glyphs]
        texts = []
        page.harvest, page.selected, page.first_checks, page.buttons_due = (lambda: None), (lambda: None), {}, False
        page.ak = Stub(enable=lambda button, on: None)
        page.all_button = page.none_button = page.restore_button = page.reset_button = Stub()
        page.write_button = Stub(setText=texts.append)
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            page.hidden = set([names.index("e"), names.index("acutecomb")])
            page.update_buttons()
            self.assertEqual(texts[-1], u"Add anchors to 3 checked glyphs (2 not shown)")
            page.glyphs[names.index("e")].checked = False
            page.update_buttons()
            self.assertEqual(texts[-1], u"Add anchors to 2 checked glyphs (1 not shown)", "an unchecked row is not written")
            page.hidden = set()
            page.update_buttons()
            self.assertEqual(texts[-1], u"Add checked anchors")
        finally:
            ac._qt = saved


class HighValueTests(unittest.TestCase):
    """Check only high-value glyphs: Font Check's own list, for this font."""

    def test_font_checks_own_functions_give_the_set(self):
        check = font_check()
        codes = set(range(0x20, 0x7F)) | set(range(0xC0, 0x100))
        found = ac.high_value_characters(check, codes)
        languages, _ = check.chosen_languages(check.load_languages(), True)
        scripts = check.coverage(languages, check.FontCharacters(codes, None), check.NEARLY_MISSING, True, None)
        rows = check.add_rows([r for s in scripts if s.present for r in s.results])
        self.assertEqual(found, set(item for row in rows for item in row.items), "what its High-value tab lists")
        self.assertTrue(found, "a Latin-1 font is within reach of languages it does not cover")
        self.assertFalse(any(len(item) == 1 and ord(item) in codes for item in found), "missing glyphs only")
        fewer = ac.high_value_characters(check, codes, nearly=0)
        self.assertEqual(fewer, set(item for row in check.add_rows(
            [r for s in check.coverage(languages, check.FontCharacters(codes, None), 0, True, None) if s.present
             for r in s.results]) for item in row.items), "Font Check's settings are followed")

    def dialog(self, high_value):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.recipes = [ac.Recipe(ac.unichr_(0x0101), u"amacron", "a"), ac.Recipe(ac.unichr_(0x0105), u"aogonek", "a"),
                          ac.Recipe(ac.unichr_(0x01CE), u"acaron", "a")]
        rows = [Row(0, True), Row(1, True), Row(2, False)]
        top = Row(-1, rows=rows)
        dialog.tree = Stub(topLevelItemCount=1, topLevelItem=lambda row: top, blockSignals=lambda on: None)
        dialog.high_value, dialog.hidden = high_value, set()
        dialog.update_buttons = lambda: None
        dialog.lines = lines = []
        dialog.log = Stub(add=lambda line, level="info": lines.append(line))
        dialog.ak = Stub(b=lambda value: u"%s" % value, html=lambda value: u"%s" % value)
        return dialog, rows

    def test_only_the_high_value_rows_stay_checked(self):
        dialog, rows = self.dialog(set([ac.unichr_(0x0105), ac.unichr_(0x01CE), u"x"]))
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            self.assertEqual(dialog.high_value_checks(), {0: False, 1: True, 2: True})
            dialog.check_high_value()
            self.assertEqual([row.checked for row in rows], [False, True, True])
            self.assertEqual(dialog.lines, [u"Checked 2 glyphs <i>Font Check</i> lists as high-value (they help complete "
                                            u"languages already within reach), and no other shown."])
            dialog.hidden = set([1])  # a search hides aogonek: its check stays
            rows[1].checked = False
            dialog.check_high_value()
            self.assertEqual([row.checked for row in rows], [False, False, True])
            self.assertIn(u"Checked 1 glyph <i>Font Check</i> lists as high-value (it helps", dialog.lines[-1])
        finally:
            ac._qt = saved

    def test_nothing_to_check_grays_the_button(self):
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            for unknown in (None, set(), set([u"x"])):
                dialog, rows = self.dialog(unknown)
                self.assertEqual(dialog.high_value_checks(), {}, "not read, nothing listed, or none of them shown")
                dialog.check_high_value()
                self.assertEqual(([row.checked for row in rows], dialog.lines), ([True, True, False], []))
        finally:
            ac._qt = saved

    def test_font_check_is_asked_with_its_own_settings(self):
        check = font_check()
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        saved = getattr(sys, "_freelab_font_check", None)
        try:
            sys._freelab_font_check = None
            self.assertEqual(dialog.font_check_settings(check), (check.NEARLY_MISSING, None, True, True), "as it starts")
            sys._freelab_font_check = Stub(dialog=Stub(visible=True), nearly=Stub(value=5), status_filter="box",
                                           choice=lambda box, choices: choices[1], inferred_box=Stub(checked=False),
                                           composing=Stub(checked=False))
            self.assertEqual(dialog.font_check_settings(check), (5, check.STATUS_FILTERS[1][2], False, False),
                             "its window is open: as set there")
            sys._freelab_font_check = Stub(dialog=Stub(visible=False), nearly=Stub(value=5))
            self.assertEqual(dialog.font_check_settings(check)[0], check.NEARLY_MISSING, "a closed window's are not")
        finally:
            sys._freelab_font_check = saved

    def test_a_font_check_that_cannot_be_read_is_said_once(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        lines = []

        def broken(name, module):
            raise IOError("no file")
        dialog.package, dialog.master = Stub(), "Regular"
        dialog.ak = Stub(load_sibling=broken, html=lambda value: u"%s" % value)
        dialog.log = Stub(add=lambda line, level="info": lines.append(level))
        self.assertIsNone(dialog.read_high_value())
        self.assertIsNone(dialog.read_high_value())
        self.assertEqual(lines, ["warning"])


class ApplyResetTests(unittest.TestCase):
    """A reset can be applied to the related letters (the owner's report of 2026-11-13: after Reset
    diacritic, Apply to related letters was grayed, so a bad placement applied to all could not be taken
    back from them)."""

    def dialog(self):
        def letter(code, base):
            return ac.Recipe(ac.unichr_(code), name=u"uni%04X" % code, base=base,
                             marks=[ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)])])
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        c, g, s = letter(0x0108, "C"), letter(0x011C, "G"), letter(0x015C, "S")
        dialog.recipes = [c, g, s, letter(0x0109, "c")]  # (the small letter is not related to the capitals)
        dialog.master, dialog.package = "Regular", None
        dialog.inks, dialog.placements = {}, {}
        dialog.metrics = lambda package: None
        dialog.selected = lambda: c
        dialog.closeness = lambda recipe: u""
        dialog.item_of = lambda recipe: None
        dialog.fill_strip = dialog.log_touches = lambda *args: None
        dialog.update_buttons = lambda: None
        dialog.lines = lines = []
        dialog.log = Stub(add=lambda line, level="info": lines.append(line))
        dialog.ak = Stub(b=lambda value: u"%s" % value, glyph_links=lambda chars: u" ".join(chars))
        return dialog, c, g, s

    def test_a_reset_is_applied_to_the_related_letters(self):
        dialog, c, g, s = self.dialog()
        self.assertEqual(dialog.propagation_targets(c), [], "nothing moved anywhere")
        self.assertFalse(dialog.can_propagate(c, []))
        c.adjust = {0: [0.0, 80.0, 1.0, 1.0]}
        targets = dialog.propagation_targets(c)
        self.assertEqual(targets, [(g, 0, 0), (s, 0, 0)])
        self.assertTrue(dialog.can_propagate(c, targets))
        dialog.propagate()
        self.assertEqual((g.adjust, s.adjust), ({0: [0.0, 80.0, 1.0, 1.0]}, {0: [0.0, 80.0, 1.0, 1.0]}))
        self.assertFalse(dialog.can_propagate(c, dialog.propagation_targets(c)), "applied: grayed until moved again")
        c.adjust, c.applied = {}, None  # Reset diacritic on C
        targets = dialog.propagation_targets(c)
        self.assertEqual(targets, [(g, 0, None), (s, 0, None)], "the related letters still hold the bad placement")
        self.assertTrue(dialog.can_propagate(c, targets), "so the reset can be applied to them")
        dialog.propagate()
        self.assertEqual((g.adjust, s.adjust), ({}, {}), "back as suggested too")
        self.assertEqual(dialog.lines[-1], u"Put the diacritics of 2 letters back as suggested, as on %s: %s %s." % (
            c.char, g.char, s.char))
        self.assertEqual(dialog.propagation_targets(c), [], "nothing left to apply: grayed")
        self.assertEqual(dialog.recipes[3].adjust, {}, "letters of the other case are not touched")

    def test_a_placement_applied_already_stays_clickable_while_a_letter_differs_by_a_reset(self):
        dialog, c, g, s = self.dialog()
        acute = ac.Mark("acute", "above", [("acute", 1.0, 1.0, 0.0, 0.0)])
        for recipe in (c, g):
            recipe.marks.append(acute)
        c.adjust = {0: [0.0, 80.0, 1.0, 1.0]}
        c.applied = dict(c.adjust)
        g.adjust = {0: [0.0, 80.0, 1.0, 1.0], 1: [5.0, 0.0, 1.0, 1.0]}
        targets = dialog.propagation_targets(c)
        self.assertIn((g, 1, None), targets, "G's acute holds a placement C's, at the suggestion, does not")
        self.assertTrue(dialog.can_propagate(c, targets))
        dialog.propagate()
        self.assertEqual(g.adjust, {0: [0.0, 80.0, 1.0, 1.0]}, "its acute put back, its circumflex as on C")
        self.assertIn(u"Placed the diacritics of 2 letters as on", dialog.lines[-1])


# -- Diacritics: the owner's second round of 2026-11-13 ------------------------------------------------

try:
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

HOLE_BASE = [(100, 0), (100, 500), (600, 500), (600, 0)]  # clockwise, TrueType's outer direction
HOLE_MARK = [(0, 0), (0, 200), (300, 200), (300, 0)]  # clockwise, at the origin
# (x scale, y scale, dx, dy, the mark's contour reversed): each lands the mark on 250..550 by 400..600
HOLE_CASES = {"plain": (1, 1, 250, 400, False), "mirrored_y": (1, -1, 250, 600, False),
              "mirrored_x": (-1, 1, 550, 400, False), "half_turn": (-1, -1, 550, 600, False),
              "mirrored_y_reversed": (1, -1, 250, 600, True), "mirrored_x_reversed": (-1, 1, 550, 400, True)}
HOLE_SPOTS = {"overlap": (400, 450), "mark": (400, 550), "base": (350, 200), "outside": (650, 650)}


@unittest.skipUnless(HAVE_FONTTOOLS and HAVE_PIL and sys.version_info[0] >= 3,
                     "needs fontTools and PIL, under Python 3 (FontLab's Python renders nothing)")
class HoleRenderingTests(unittest.TestCase):
    """When a mirrored part leaves a hole: small fonts built here, rendered by FreeType (PIL's). The mark
    overlaps the base; where the two run opposite ways, the overlap is a hole. FreeType does not set a
    mirrored component's direction right, so a composite and a glyph of outlines show the same."""

    def font(self, cff):
        import io
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.t2CharStringPen import T2CharStringPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        order = [".notdef", "base", "mark", "mark.rev"]
        contours = {".notdef": [], "base": [HOLE_BASE], "mark": [HOLE_MARK], "mark.rev": [HOLE_MARK[::-1]]}
        composites = {}
        for name in sorted(HOLE_CASES):
            sx, sy, dx, dy, reverse = HOLE_CASES[name]
            mark = HOLE_MARK[::-1] if reverse else HOLE_MARK
            contours["simple_" + name] = [HOLE_BASE, moved(mark, sx, sy, dx, dy)]  # copied in, overlaps kept
            order.append("simple_" + name)
            if not cff:
                composites["composite_" + name] = ("mark.rev" if reverse else "mark", sx, sy, dx, dy)
                order.append("composite_" + name)
        cmap = dict((0x41 + at, name) for at, name in enumerate(order[1:]))
        builder = FontBuilder(1000, isTTF=not cff)
        builder.setupGlyphOrder(order)
        builder.setupCharacterMap(cmap)

        def draw(pen, name):
            for points in contours[name]:
                # (CFF's outer direction is the other one: the same shapes, drawn as that format draws them)
                points = points[::-1] if cff else points
                pen.moveTo(points[0])
                for point in points[1:]:
                    pen.lineTo(point)
                pen.closePath()
        if cff:
            strings = {}
            for name in order:
                pen = T2CharStringPen(700, None)
                draw(pen, name)
                strings[name] = pen.getCharString()
            builder.setupCFF("HoleTest", {"FullName": "HoleTest"}, strings, {})
        else:
            glyphs = {}
            for name in order:
                pen = TTGlyphPen(dict.fromkeys(order))
                if name in composites:
                    mark, sx, sy, dx, dy = composites[name]
                    pen.addComponent("base", (1, 0, 0, 1, 0, 0))
                    pen.addComponent(mark, (sx, 0, 0, sy, dx, dy))
                else:
                    draw(pen, name)
                glyphs[name] = pen.glyph()
            builder.setupGlyf(glyphs)
        builder.setupHorizontalMetrics(dict((name, (700, 0)) for name in order))
        builder.setupHorizontalHeader(ascent=900, descent=-200)
        builder.setupNameTable({"familyName": "HoleTest", "styleName": "Regular"})
        builder.setupOS2(sTypoAscender=900, sTypoDescender=-200, usWinAscent=900, usWinDescent=200)
        builder.setupPost()
        data = io.BytesIO()
        builder.save(data)
        return data.getvalue(), dict((name, code) for code, name in cmap.items())

    def inked(self, data, code):
        """{spot: whether FreeType inks it} for one glyph, drawn 200 pixels to the em."""
        import io
        size, origin = 200, (20, 200)
        image = Image.new("L", (200, 220), 0)
        ImageDraw.Draw(image).text(origin, chr(code), font=ImageFont.truetype(io.BytesIO(data), size), fill=255,
                                   anchor="ls")
        return dict((spot, image.getpixel((int(origin[0] + x * size / 1000.0), int(origin[1] - y * size / 1000.0))) > 127)
                    for spot, (x, y) in HOLE_SPOTS.items())

    def check(self, cff):
        data, codes = self.font(cff)
        for name in sorted(codes):
            kind, _, case = name.partition("_")
            if kind not in ("simple", "composite"):
                continue
            found = self.inked(data, codes[name])
            self.assertEqual((found["mark"], found["base"], found["outside"]), (True, True, False), name)
            hole = case in ("mirrored_x", "mirrored_y")  # the two parts run opposite ways there, and only there
            self.assertEqual(found["overlap"], not hole, "%s (%s): a hole exactly where a part mirrored one way "
                                                         "overlaps another" % (name, "CFF" if cff else "TrueType"))

    def test_truetype_composites_and_outlines(self):
        self.check(False)

    def test_cff_outlines(self):
        self.check(True)


class HandReachTests(unittest.TestCase):
    """A mark moved by hand: how far, how it is written, where it shows (the owner's report: a drag sent a
    mark to coordinates of three hundred digits, and Reset diacritic stayed grayed)."""

    def test_moves_are_kept_to_what_a_font_holds(self):
        self.assertEqual(ac.clamped_adjust([12.5, -340.0, 1.2, 0.9]), [12.5, -340.0, 1.2, 0.9], "within reach: as set")
        self.assertEqual(ac.clamped_adjust([1e305, -1e305, 1e9, 0.0]), [ac.HAND_REACH, -ac.HAND_REACH, 10.0, 0.1])
        self.assertEqual(ac.clamped_adjust([float("inf"), float("nan"), float("nan"), float("-inf")]),
                         [0.0, 0.0, 1.0, 1.0], "no numbers: no move, no scaling")
        self.assertLessEqual(ac.HAND_REACH + 16384, 32767, "moved that far from anywhere in the largest em, a mark "
                                                           "still fits TrueType's 16-bit coordinates")
        self.assertEqual(ac.finite(u"x", 7.0), 7.0)

    def test_numbers_are_whole_units_grouped_by_thousands(self):
        self.assertEqual([ac.grouped(value) for value in (0, 7, 950, 1000, 12345.4, -1200, 1234567, 999.5, -0.4)],
                         [u"0", u"7", u"950", u"1,000", u"12,345", u"-1,200", u"1,234,567", u"1,000", u"0"])
        self.assertEqual([ac.whole_units(value) for value in (0.5, 1.5, 2.5, -0.5, -2.5)], [1, 2, 3, -1, -3],
                         "halves away from zero, on either Python")
        self.assertEqual(ac.moved_words(12, 1250), u"12 right, 1,250 up")
        self.assertEqual(ac.moved_words(-16000, -3), u"16,000 left, 3 down")
        self.assertEqual(ac.moved_words(0, 0.2), u"")
        line = ac.mark_line(u"period (draft for dot above)", [1e305, 6e305, 1.0, 1.0], True)
        self.assertTrue(line.startswith(u"period (draft for dot above), moved 16,000 right, 16,000 up (outside the "
                                        u"view: the arrow at the edge points to it). Arrows move it"), line)
        self.assertLess(len(line), 220)
        self.assertEqual(ac.mark_line(u"acute", [0.0, 0.0, 1.0, 1.0]).split(u".")[0], u"acute")
        self.assertIn(u", at 120% \N{MULTIPLICATION SIGN} 90%", ac.mark_line(u"acute", [0.0, 0.0, 1.2, 0.9]))

    def test_a_mark_none_of_which_shows_gets_an_arrow_at_the_edge(self):
        self.assertIsNone(ac.outside_view((10, 10, 50, 50), 600, 300))
        self.assertIsNone(ac.outside_view((-20, 280, 5, 400), 600, 300), "part of it shows")
        self.assertEqual(ac.outside_view((100, -900, 140, -850), 600, 300), (120.0, 9, 0, -1), "above: at the top edge")
        self.assertEqual(ac.outside_view((700, 100, 760, 140), 600, 300), (591, 120.0, 1, 0))
        self.assertEqual(ac.outside_view((-90, 400, -40, 450), 600, 300), (9, 291, -1, 1), "a corner")
        self.assertEqual(ac.outside_view((1e300, -1e300, float("inf"), -1e299), 600, 300)[2:], (1, -1))

    def test_the_view_opens_for_a_moved_mark_only_so_far(self):
        self.assertEqual(ac.view_bounds(1130, -370, 900, -200, 1000, 50), (1130, -370), "the glyph within its lines")
        self.assertEqual(ac.view_bounds(1130, -370, 1500, -200, 1000, 50), (1550, -370), "opened to hold a raised mark")
        self.assertEqual(ac.view_bounds(1130, -370, 17000, -9000, 1000, 50), (2130, -1370),
                         "no farther than an em past them: the glyph keeps its size")
        self.assertEqual(ac.view_bounds(1130, -370, float("inf"), float("nan"), 1000, 50), (1130, -370))


class InkOf(object):
    """A master's ink, as the dialog keeps it (FontLabInk, stubbed): an Ink by name, and (path, advance)."""

    def __init__(self, found):
        self.found = found

    def __call__(self, name):
        return self.found.get(name)

    def path(self, name):
        return None, (self.found[name].advance if name in self.found else 0)


class DragTests(unittest.TestCase):
    """The mark editor's drags, its widget and Qt stubbed, the dialog's own methods behind it."""

    WIDTH, HEIGHT = 600.0, 300.0

    def setUp(self):
        test = self

        class Widget(object):
            def __init__(self):
                self.cursor, self.updates = None, 0

            rect = property(lambda self: Stub(width=lambda: test.WIDTH, height=lambda: test.HEIGHT))

            def setFocusPolicy(self, policy):
                pass

            def setMouseTracking(self, on):
                pass

            def setMinimumHeight(self, height):
                pass

            def setFocus(self):
                pass

            def update(self):
                self.updates += 1

            def setCursor(self, cursor):
                self.cursor = cursor
        qt = Stub(StrongFocus=1, LeftButton=1, ShiftModifier=2, AltModifier=4, SizeAllCursor="move",
                  ArrowCursor="arrow", PointingHandCursor="hand", SizeFDiagCursor="f", SizeBDiagCursor="b",
                  SizeVerCursor="v", SizeHorCursor="h")
        self.saved = ac._qt
        ac._qt = lambda: (Stub(Qt=qt), Stub(QWidget=Widget))
        self.recipe = ac.Recipe(ac.unichr_(0x010B), u"cdotaccent", "c", [ac.Mark(
            "dotaccent", "above", [("period", 1.0, 1.0, 0.0, 0.0)], u"draft for dot above")])
        dialog = self.dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.master, dialog.package, dialog.held_font, dialog.compact = "Regular", Stub(upm=1000), None, True
        dialog.inks = {"Regular": InkOf({"c": ac.Ink(40, -10, 460, 480, advance=500), "period": ac.Ink(0, 0, 100, 100)})}
        dialog.placements = {"Regular": ac.Placement(1000.0, MODEL)}
        dialog.metrics = lambda package: ac.Metrics(1000, 880, -120, 700)
        dialog.limits = lambda package: [(1080, u"120% line 1080 (meets the line above)", True),
                                         (880, u"font ascender 880", False)]
        dialog.font = lambda package: ac.Font(["c", "period"], [("c", 0x63), ("period", 0x2E)])
        dialog.recipes = [self.recipe]
        dialog.selected = lambda: self.recipe
        dialog.item_of = lambda recipe: None
        self.lines, self.calls = [], []
        dialog.hint = Stub(setText=self.lines.append)
        dialog.ak = Stub(html=lambda value: u"%s" % value)
        dialog.update_buttons = lambda: self.calls.append("buttons")
        self.editor = dialog.editor = ac.make_editor(dialog)
        self.editor.scene = dialog.scene(self.recipe)
        self.editor.geometry()

    def tearDown(self):
        ac._qt = self.saved

    def event(self, x, y, held=True):
        return Stub(button=lambda: 1, buttons=lambda: 1 if held else 0, modifiers=lambda: 4,  # (Alt: no snapping)
                    pos=lambda: Stub(x=lambda: x, y=lambda: y))

    def mark_at(self):
        left, top, right, bottom = self.editor.screen_box(dict(self.editor.mark_boxes())[0])
        return (left + right) / 2.0, (top + bottom) / 2.0

    def repaint(self):
        self.editor.geometry()  # what a paint does first: the view, for the scene as it is now

    def test_a_drag_far_outside_the_editor_stays_finite_and_ends_at_the_release(self):
        editor, recipe = self.editor, self.recipe
        x, y = self.mark_at()
        scale = editor.view[0]
        editor.mousePressEvent(self.event(x, y))
        self.assertEqual(editor.selected, 0)
        # The pointer 2,000 pixels over the press, far over the editor's top (the mouse is the editor's
        # until the button is let go). The view was fitted again at every move, to a scene whose top
        # followed the mark: each move divided the same pixels by a smaller scale, and the mark ran off
        # without end. Now the same pixels are the same units, however many moves come.
        for _ in range(300):
            editor.mouseMoveEvent(self.event(x + 40, y - 2000))
            self.repaint()
        self.assertEqual(recipe.adjust[0][:2], [round(40 / scale, 2), round(2000 / scale, 2)])
        self.assertEqual(editor.view[0], scale, "the view of the press, for the whole drag")
        for _ in range(50):  # (and to the very edge of a very large screen)
            editor.mouseMoveEvent(self.event(x - 10 ** 7, y - 10 ** 9))
            self.repaint()
        self.assertEqual(recipe.adjust[0][:2], [-ac.HAND_REACH, ac.HAND_REACH], "kept to what a font can hold")
        self.assertEqual(self.calls, [], "the buttons follow once the drag is over")
        editor.mouseReleaseEvent(self.event(x - 10 ** 7, y - 10 ** 9, held=False))  # let go out there
        self.assertIsNone(editor.drag)
        self.assertIsNone(editor.held, "the view is fitted again")
        self.assertEqual(self.calls, ["buttons"], "the release, wherever it comes, reaches the buttons")
        self.assertTrue(recipe.adjust, "a placement by hand: Reset diacritic is clickable (it is while adjust holds one)")
        self.assertIn(u"moved 16,000 left, 16,000 up (outside the view", self.lines[-1])
        self.assertLess(len(self.lines[-1]), 220, "no number of three hundred digits")
        self.repaint()
        self.assertLessEqual(editor.scene["top"], 1130 + 1000, "the view opens an em past its lines, no farther")
        arrow = editor.outside()
        self.assertEqual(list(arrow), [0], "the mark is outside the view: an arrow at the edge")
        self.assertEqual(arrow[0][2:], (-1, -1), "pointing up and left, where the mark went")
        self.assertEqual(editor.hit(arrow[0][0], arrow[0][1]), ("mark", 0), "a click on the arrow selects the mark")

    def test_a_move_within_reach_stays_as_set_and_shows(self):
        editor, recipe = self.editor, self.recipe
        x, y = self.mark_at()
        scale = editor.view[0]
        editor.mousePressEvent(self.event(x, y))
        editor.mouseMoveEvent(self.event(x + 20, y - 30))
        editor.mouseReleaseEvent(self.event(x + 20, y - 30, held=False))
        self.assertEqual(recipe.adjust, {0: [round(20 / scale, 2), round(30 / scale, 2), 1.0, 1.0]})
        self.assertEqual(editor.outside(), {})
        self.assertNotIn(u"outside the view", self.lines[-1])
        self.assertEqual(self.calls, ["buttons"])

    def test_a_lost_release_ends_the_drag_at_the_next_move(self):
        editor, recipe = self.editor, self.recipe
        x, y = self.mark_at()
        editor.mousePressEvent(self.event(x, y))
        editor.mouseMoveEvent(self.event(x, y - 40))
        moved_to = list(recipe.adjust[0])
        editor.mouseMoveEvent(self.event(x + 300, y + 100, held=False))  # back over the editor, no button held
        self.assertIsNone(editor.drag, "the drag is over: the mark does not follow a pointer with no button down")
        self.assertEqual(recipe.adjust[0], moved_to)
        self.assertEqual(self.calls, ["buttons"])

    def test_a_move_that_is_no_number_still_reaches_the_buttons(self):
        self.dialog.set_adjust(0, [float("inf"), float("nan"), float("nan"), 1e300], final=True)
        self.assertEqual(self.recipe.adjust, {0: [0.0, 0.0, 1.0, 10.0]}, "nothing infinite is kept")
        self.assertEqual(self.calls, ["buttons"])

        def broken(index):
            raise OverflowError("cannot convert float infinity to integer")
        self.dialog.mark_selected = broken
        with self.assertRaises(OverflowError):
            self.dialog.set_adjust(0, [5.0, 5.0, 1.0, 1.0], final=True)
        self.assertEqual(self.calls, ["buttons", "buttons"], "whatever the line under the picture did (the owner's "
                                                             "Reset diacritic stayed grayed: they never came)")

    def test_scaling_uses_the_view_of_the_press_too(self):
        editor, recipe = self.editor, self.recipe
        box = dict(editor.mark_boxes())[0]
        left, top, right, bottom = editor.screen_box(box)
        editor.selected = 0
        editor.mousePressEvent(self.event(right, top))  # its top right handle
        self.assertEqual(editor.drag[0], "scale")
        for _ in range(100):
            editor.mouseMoveEvent(self.event(right + 10 ** 6, top - 10 ** 6))
            self.repaint()
        self.assertEqual(recipe.adjust[0][2:], [10.0, 10.0], "no larger than ten times")
        editor.mouseReleaseEvent(self.event(0, 0, held=False))
        self.assertTrue(all(abs(value) <= ac.HAND_REACH for value in recipe.adjust[0][:2]))

    def test_the_anchors_tab_keeps_an_anchor_within_reach(self):
        page = ac.AnchorPage.__new__(ac.AnchorPage)
        inks = {"A": ac.Ink(10, 0, 590, 700, advance=600), "acutecomb": ac.Ink(-60, 550, 60, 660)}
        page.glyphs = ac.plan_anchors([("A", 0x41, "base", inks["A"], {}), ("acutecomb", 0x0301, "mark", inks["acutecomb"], {})],
                                      {}, "latin", 1000, 500)
        base = page.glyphs[0]
        page.edits = [(base, "top", 1)]
        page.selected = lambda: base
        page.scene = lambda g: None
        page.editor = Stub(selected=0, scene=None, update=lambda: None, outside=lambda: {0: (9, 9, -1, -1)})
        lines = []
        page.hint, page.ak = Stub(setText=lines.append), Stub(html=lambda value: u"%s" % value)
        page.items = lambda: []
        page.update_buttons = lambda: self.calls.append("anchors")
        page.set_adjust(0, [1e305, float("inf"), 1.0, 1.0], final=True)
        self.assertEqual(base.adjust["top"], [ac.HAND_REACH, 0.0])
        self.assertEqual(self.calls, ["anchors"])
        self.assertIn(u"(the mark is outside the view: the arrow at the edge points to it)", lines[-1])
        import re
        self.assertTrue(re.search(u"anchor: x 16,[0-9]{3}, y [0-9]+", lines[-1]), lines[-1])


class CompactTests(unittest.TestCase):
    """Compact glyphs to fit the line: one check box, and the rows placed by hand keep what was set."""

    TIGHT = ac.Metrics(1000, 600, -500)  # room up to 700
    HOPELESS = ac.Metrics(1000, 300, -700)  # room up to 500: the letter alone

    def stack(self, code=0x1ED1):
        return ac.Recipe(ac.unichr_(code), u"x%04X" % code, "o", [
            ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)]),
            ac.Mark("circumflex", "above", [("circumflex", 1.0, 1.0, 0.0, 0.0)])])

    def test_switched_off_a_glyph_is_left_as_placed_and_says_it_is_too_tall(self):
        placement = ac.Placement(1000.0, MODEL)
        roomy = self.stack()
        natural, _ = ac.place(roomy, inks().get, placement)  # no line to fit: every mark at its own gap and size
        recipe = self.stack()
        compact, _ = ac.place(recipe, inks().get, placement, self.TIGHT)
        self.assertTrue(recipe.notes[0].startswith(ac.COMPACT_NOTE))
        self.assertNotEqual(compact, natural)
        recipe.compact = False
        parts, _ = ac.place(recipe, inks().get, placement, self.TIGHT)
        self.assertEqual(parts, natural, "the uncompacted placement: natural gaps, full size")
        over = max(p[4] + 600 * p[2] for p in parts[1:]) - 700
        self.assertEqual(recipe.notes, [u"%s too tall for a 120%% line" % ac.units_up(over)])
        self.assertTrue(recipe.checked, "left checked: whoever switched compacting off sees to it by hand")
        ac.place(recipe, inks().get, placement, ac.Metrics(1000, 800, -200))
        self.assertEqual(recipe.notes, [], "one that fits says nothing either way")

    def test_the_top_line_counts_follow(self):
        placement = ac.Placement(1000.0, MODEL)
        recipes = [self.stack(), self.stack(), self.stack()]
        ac.place(recipes[0], inks().get, placement, self.TIGHT)
        ac.place(recipes[1], inks().get, placement, self.HOPELESS)
        recipes[2].compact = False
        ac.place(recipes[2], inks().get, placement, self.TIGHT)
        self.assertEqual(ac.room_counts(recipes), (2, 1, 1), "made compact (one of them too tall even so), and "
                                                             "one too tall as placed")
        self.assertEqual(ac.room_details(2, 1, 0), [u"2 made compact to fit a 120% line", u"1 too tall even so, left unchecked"])
        self.assertEqual(ac.room_details(0, 0, 42), [u"42 too tall for a 120% line as placed"])
        self.assertEqual(ac.room_details(0, 0, 0), [])
        self.assertEqual(ac.compact_text(False, 0), u"Glyphs are no longer made compact: their marks keep their own gaps "
                                                    u"and size, and the rows say which are too tall for a 120% line.")
        self.assertEqual(ac.compact_text(True, 1), u"Glyphs too tall for a 120% line are made compact again. 1 glyph "
                                                   u"placed by hand keeps what you set.")
        self.assertTrue(ac.compact_text(True, 2).endswith(u"2 glyphs placed by hand keep what you set."))

    def dialog(self, metrics):
        placement = ac.Placement(1000.0, MODEL)
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.recipes = [self.stack(0x1ED1), self.stack(0x1ED3), self.stack(0x1ED5)]
        dialog.compact, dialog.settings, dialog.shift_cache = True, {}, {"stale": 1}
        dialog.compact_box = Stub(checked=True)
        dialog.harvest = dialog.select = lambda: None
        dialog.selected = lambda: None
        dialog.item_of = lambda recipe: None
        dialog.lines, dialog.written = [], []
        dialog.log = Stub(add=lambda line, level="info": dialog.lines.append(line))
        dialog.ak = Stub(html=lambda value: u"%s" % value)

        def fill():  # as the list's rows are first drawn: each placed (which unchecks one too tall even compact)
            for r in dialog.recipes:
                ac.place(r, inks().get, placement, metrics)
        dialog.fill = fill
        fill()
        dialog.first_checks = dict((r.char, r.checked) for r in dialog.recipes)
        return dialog, placement

    def switch(self, dialog, on):
        saved = ac._qt, ac.write_settings
        try:
            ac._qt = lambda: (LIST_QT, None)
            ac.write_settings = lambda ak, data: dialog.written.append(dict(data))
            dialog.compact_box.checked = on
            dialog.compact_toggled()
        finally:
            ac._qt, ac.write_settings = saved

    def test_switching_changes_only_rows_still_placed_as_suggested(self):
        dialog, placement = self.dialog(self.TIGHT)
        plain, by_hand, _ = dialog.recipes
        by_hand.adjust = {1: [0.0, 30.0, 1.0, 1.0]}  # its upper mark raised by hand, under the compact suggestion
        before, _ = ac.place(by_hand, inks().get, placement, self.TIGHT)
        compact, _ = ac.place(plain, inks().get, placement, self.TIGHT)
        self.switch(dialog, False)
        self.assertEqual((plain.compact, by_hand.compact), (False, True))
        self.assertEqual(dialog.written, [{"compact": False}], "remembered")
        self.assertEqual(dialog.shift_cache, {})
        self.assertTrue(plain.notes[0].endswith(ac.TOO_TALL_NOTE), "its row says it is too tall, not that it was compacted")
        self.assertEqual(ac.place(by_hand, inks().get, placement, self.TIGHT)[0], before, "what the hand set, kept")
        self.assertIn(u"1 glyph placed by hand keeps what you set", dialog.lines[-1])
        self.switch(dialog, True)
        self.assertEqual(ac.place(plain, inks().get, placement, self.TIGHT)[0], compact, "the compact suggestion again")
        self.assertEqual(ac.place(by_hand, inks().get, placement, self.TIGHT)[0], before)
        # put back as suggested while compacting is off, it follows the dialog again
        self.switch(dialog, False)
        by_hand.adjust = {}
        dialog.sync_compact([by_hand])
        self.assertFalse(by_hand.compact)

    def test_checks_follow_the_suggestion_unless_changed_by_hand(self):
        dialog, placement = self.dialog(self.HOPELESS)
        first, second, third = dialog.recipes
        self.assertEqual([r.checked for r in dialog.recipes], [False, False, False], "too tall even compact: unchecked")
        second.checked = True  # checked by hand all the same
        self.switch(dialog, False)
        self.assertEqual([r.checked for r in dialog.recipes], [True, True, True], "as placed, they are left checked")
        self.assertEqual(dialog.first_checks[first.char], True, "the suggestion now")
        third.checked = False  # unchecked by hand
        self.switch(dialog, True)
        self.assertEqual([r.checked for r in dialog.recipes], [False, True, False],
                         "unchecked again where too tall even compact; the checks set by hand stay")
        self.assertEqual(dialog.settings, {"compact": True})

    def test_a_reread_keeps_what_a_row_placed_by_hand_was_placed_under(self):
        dialog, placement = self.dialog(self.TIGHT)
        dialog.recipes[0].adjust, dialog.recipes[0].compact = {0: [5.0, 0.0, 1.0, 1.0]}, False
        dialog.sync_compact()
        self.assertEqual([r.compact for r in dialog.recipes], [False, True, True], "the dialog's choice for the others")


class BuildTextTests(unittest.TestCase):
    """Build builds every checked glyph, shown or not, and says how many a search hides."""

    def test_the_button_says_how_many_are_not_shown(self):
        self.assertEqual(ac.build_text(12, 0), u"Build checked glyphs")
        self.assertEqual(ac.build_text(12, 5), u"Build 12 checked glyphs (5 not shown)")
        self.assertEqual(ac.build_text(1, 1), u"Build 1 checked glyph (1 not shown)")
        self.assertEqual(ac.build_text(2, 1), u"Build 2 checked glyphs (1 not shown)")
        self.assertEqual(ac.build_text(0, 0), u"Build checked glyphs")
        self.assertEqual([ac.correct_button_text(n) for n in (0, 1, 2)],
                         [u"Correct mirrored components", u"Correct mirrored components of 1 glyph",
                          u"Correct mirrored components of 2 glyphs"])

    def test_the_dialog_counts_the_checked_rows_a_search_hides(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.recipes = [ac.Recipe(ac.unichr_(0x0101), u"amacron", "a"), ac.Recipe(ac.unichr_(0x0105), u"aogonek", "a"),
                          ac.Recipe(ac.unichr_(0x01CE), u"acaron", "a"),
                          ac.Recipe(ac.unichr_(0x1E0D), u"ddotbelow", "d", missing=u"a dot below")]
        rows = [Row(0, True), Row(1, True), Row(2, False), Row(3)]
        top = Row(-1, rows=rows)
        dialog.tree = Stub(topLevelItemCount=1, topLevelItem=lambda row: top, selectedItems=lambda: [])
        dialog.hidden, dialog.package, dialog.high_value, dialog.first_checks = set([1, 2]), Stub(), None, {}
        dialog.built_names, dialog.editor = [], Stub(selected=None)
        texts = {}

        def button(name):
            return Stub(enabled=True, setEnabled=lambda on: None, setText=lambda value: texts.__setitem__(name, value))
        for name in ("all", "none", "build", "value", "restore", "glyph_window", "reset_marks", "propagate", "kerning",
                     "line_up", "correct"):
            setattr(dialog, name + "_button", button(name))
        dialog.ak = Stub(enable=lambda widget, on: None,
                         checks_of=lambda items, checked: (any(checked(i) for i in items), any(not checked(i) for i in items)))
        saved = ac._qt
        try:
            ac._qt = lambda: (LIST_QT, None)
            dialog.update_buttons()
            self.assertEqual(texts["build"], u"Build 2 checked glyphs (1 not shown)")
            dialog.hidden = set()
            dialog.update_buttons()
            self.assertEqual(texts["build"], u"Build checked glyphs")
        finally:
            ac._qt = saved
        self.assertEqual(texts["correct"], u"Correct mirrored components")


class ReferencePreviewTests(unittest.TestCase):
    """The reference font's chooser: the default first, and each font's name in its own font."""

    def test_each_entry_is_given_its_own_font_a_slice_at_a_time(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        families = [u"Family %03d" % at for at in range(95)] + [u"Symbols"]
        dialog.reference_list = ac.reference_rows(u"Bundled Sans", families)
        dialog.reference_fonts_at = 0
        boxes = [Stub(font="box font", set=[]), Stub(font="box font", set=[])]
        for box in boxes:
            box.setItemData = (lambda target: lambda at, value, role: target.set.append((at, value.family, role)))(box)
        dialog.reference_boxes = boxes
        timers = []

        class Font(object):
            def __init__(self, other):
                self.other, self.family = other, None

            def setFamily(self, family):
                self.family = family
        database = type("Database", (object,), {
            "Latin": 1, "writingSystems": lambda self, family: [] if family == u"Symbols" else [1, 2]})
        gui = Stub(QFont=Font, QFontDatabase=database)
        core = Stub(Qt=Stub(FontRole=6), QTimer=Stub(singleShot=lambda wait, slot: timers.append(slot)))
        saved = ac._qt
        try:
            ac._qt = lambda: (core, gui)
            dialog.set_reference_fonts()
            self.assertEqual(len(boxes[0].set), ac.REFERENCE_SLICE - 1, "the first slice (its separator has no font)")
            self.assertEqual(boxes[0].set[0], (0, u"Bundled Sans", 6), "the default's entry in its own font too")
            self.assertEqual(len(timers), 1, "the rest at the next turn of the event loop: the dialog is not held up")
            while timers:
                timers.pop(0)()
        finally:
            ac._qt = saved
        self.assertEqual(boxes[0].set, boxes[1].set, "both tabs' choosers")
        rows = dialog.reference_list
        self.assertEqual(sorted(at for at, _, _ in boxes[0].set),
                         [at for at, (label, family) in enumerate(rows) if family is not None and family != u"Symbols"],
                         "every family but the separator and a font with no Latin letters (its name would not read)")
        self.assertTrue(all(family == rows[at][1] for at, family, _ in boxes[0].set), "each row its own family")
        self.assertEqual(dialog.reference_fonts_at, len(rows))

    def test_a_qt_that_does_not_take_fonts_leaves_plain_names(self):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.reference_list, dialog.reference_fonts_at = ac.reference_rows(u"Bundled Sans", [u"Arial"]), 0

        def refuse(at, value, role):
            raise TypeError("no such overload")
        dialog.reference_boxes = [Stub(font="f", setItemData=refuse)]
        saved = ac._qt
        try:
            ac._qt = lambda: (Stub(Qt=Stub(FontRole=6), QTimer=Stub(singleShot=lambda wait, slot: 1 / 0)),
                              Stub(QFont=lambda other: Stub(setFamily=lambda family: None),
                                   QFontDatabase=lambda: Stub(writingSystems=lambda family: [1])))
            dialog.set_reference_fonts()  # (a timer's slot: nothing escapes)
        finally:
            ac._qt = saved
        self.assertEqual(dialog.reference_fonts_at, 3, "stopped: the names stay in the dialog's font")


def recording_qt():
    """(QtCore, QtGui, made): a Qt that takes any call, each widget made kept with what it was made with
    and its What's This text, to build the real dialog on."""
    made = []

    def class_missing(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return 0  # (an enumeration's value: QFrame.NoFrame, Qt.AlignCenter)
    meta = type("Meta", (type,), {"__getattr__": class_missing})

    def init(self, *args, **kwargs):
        self.__dict__["args"], self.__dict__["whats"] = args, None
        made.append(self)

    def missing(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args, **kwargs: None

    def whats(self, value):
        self.__dict__["whats"] = value
    base = meta("Base", (object,), {"__init__": init, "__getattr__": missing, "setWhatsThis": whats})
    classes = {}

    class Namespace(object):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            if name not in classes:
                classes[name] = meta(name, (base,), {})
            return classes[name]
    space = Namespace()
    return space, space, made


class WhatsThisTests(unittest.TestCase):
    """Every control the dialog builds has a What's This of its own, and a label beside a control carries
    the control's (the owner found, in another tool, a control showing its neighbor's help)."""

    CONTROLS = ("QPushButton", "QCheckBox", "QComboBox", "QFontComboBox", "QSpinBox", "QDoubleSpinBox", "QLineEdit",
                "QTreeWidget", "QListWidget", "QTabBar", "QToolButton", "QRadioButton", "QSlider", "MarkEditor")

    def build(self):
        core, gui, made = recording_qt()

        class Ak(object):
            LEAVE_ALONE_PROP = "leave"
            AutoKerningDialog = type("Window", (object,), {"main_window": staticmethod(lambda: None)})

            def __getattr__(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return lambda *args, **kwargs: None

            def status_label(self, *args):
                return gui.QLabel()

            def separator(self):
                return gui.QFrame()

            def Log(self):
                return Stub(widget=gui.QTextBrowser(), link_handler=None, follow=lambda source: None,
                            add=lambda *args: None)

            def counted(self, number, one, many=None):
                return ac.counted(number, one, many)

            def load_sibling(self, file_name, module_name):
                raise IOError(file_name)

            def state_dir(self):
                return os.path.join(HERE, "no-such-folder")

        class Built(ac.AccentsDialog):
            def update_buttons(self):  # (it reads the list, which the stand-in Qt does not fill)
                pass
        saved = ac._qt, ac.load_auto_kerning, sys.modules.get("fontlab")
        try:
            ac._qt = lambda: (core, gui)
            ac.load_auto_kerning = lambda: Ak()
            sys.modules["fontlab"] = Stub()
            dialog = Built([u"x"])
        finally:
            ac._qt, ac.load_auto_kerning = saved[:2]
            if saved[2] is None:
                sys.modules.pop("fontlab", None)
            else:
                sys.modules["fontlab"] = saved[2]
        return dialog, made

    def test_every_control_and_label_has_its_own(self):
        dialog, made = self.build()
        kinds = dict((kind, [w for w in made if type(w).__name__ == kind]) for kind in self.CONTROLS + ("QLabel",))
        self.assertGreaterEqual(len(kinds["QPushButton"]), 16, "both tabs' buttons were made")
        self.assertEqual(len(kinds["MarkEditor"]), 2)
        self.assertEqual(len(kinds["QComboBox"]), 4, "the character set, the script, and a reference chooser per tab")
        for kind in self.CONTROLS + ("QLabel",):
            for widget in kinds[kind]:
                self.assertTrue(widget.whats and widget.whats.strip(),
                                "%s %r has no What's This of its own" % (kind, widget.args[:1]))
        buttons = [w.whats for w in kinds["QPushButton"]]
        self.assertEqual(len(set(buttons)), len(buttons), "no button shows another button's help")
        self.assertEqual(len(set(w.whats for w in kinds["QCheckBox"])), len(kinds["QCheckBox"]))

    def test_a_label_carries_its_controls_text(self):
        dialog, made = self.build()
        labels = dict((w.args[0], w) for w in made if type(w).__name__ == "QLabel" and w.args)
        self.assertEqual(labels[u"Character set:"].whats, dialog.set_box.whats)
        self.assertEqual(labels[u"Script:"].whats, dialog.anchors.script_box.whats)
        self.assertEqual(labels[u"Same diacritic:"].whats, dialog.strip_area.whats)
        self.assertEqual(dialog.search_label.whats, dialog.search.whats)
        self.assertEqual(dialog.anchors.search_label.whats, dialog.anchors.search.whats)
        self.assertNotEqual(dialog.search.whats, dialog.anchors.search.whats, "each tab's field says what it searches")
        self.assertEqual(dialog.reference_title.whats, dialog.reference.whats)
        self.assertEqual(dialog.anchors.reference_title.whats, dialog.anchors.reference.whats)
        self.assertEqual(dialog.reference_font.whats, dialog.anchors.reference_font.whats, "one chooser, on both tabs")
        self.assertIn(u"FreeLab's own font", dialog.reference_font.whats, "named plainly where Font Check is not read")
        self.assertTrue(dialog.compact_box.whats.startswith(u"Makes a glyph too tall for a 120% line compact"))
        self.assertIn(u"Every checked glyph is built, those a search hides too", dialog.build_button.whats)
        self.assertNotEqual(dialog.dialog.whats, dialog.tabs.whats, "the tab bar's own, not the whole dialog's")


class CellWalkTests(unittest.TestCase):
    """Every row a realistic font produces, in both lists: no cell ends with a period, none holds an em
    dash, an en dash, or an interpunct (the owner's rules; rows still read "... + macron -- gaps closed to
    fit a 120% line." with an em dash in an installed copy)."""

    NAMES = dict([(chr(code) if sys.version_info[0] >= 3 else unichr(code), code)  # noqa: F821
                  for code in list(range(0x41, 0x5B)) + list(range(0x61, 0x7B))],
                 dotlessi=0x131, period=0x2E, comma=0x2C, hyphen=0x2D, asciicircum=0x5E, asciitilde=0x7E, grave=0x60,
                 acute=0xB4, degree=0xB0, quotedbl=0x22, quoteright=0x2019, quoteleft=0x2018, quotesingle=0x27,
                 underscore=0x5F, plus=0x2B, breve=0x2D8, macron=0xAF, dieresis=0xA8, cedilla=0xB8, ogonek=0x2DB,
                 Alpha=0x391, alpha=0x3B1, tonos=0x384, iota=0x3B9, Omega=0x3A9, omega=0x3C9, aacute=0xE1,
                 Agrave=0xC0, amacron=0x101, odieresis=0xF6, Ccedilla=0xC7, eacute=0xE9)
    NAMES.update({"ii-cy": 0x438, "Ii-cy": 0x418, "ka-hira": 0x304B, "ha-hira": 0x306F})
    BANNED = (u"\N{EM DASH}", u"\N{EN DASH}", u"\N{MIDDLE DOT}", u"\N{HORIZONTAL BAR}", u" -- ")

    def ink(self):
        tall = set(u"bdfhklt")

        def of(name):
            if name in ("period", "comma"):
                return ac.Ink(0, 0, 100, 100, advance=200)
            code = self.NAMES.get(name, 0)
            if len(name) == 1 or name in ("Alpha", "Omega", "Ii-cy", "Agrave", "Ccedilla"):
                if name[:1].isupper() or name in tall:
                    return ac.Ink(20, 0, 580, 700, advance=600)
                return ac.Ink(30, -10, 470, 480, advance=500)
            if code and (0x370 <= code < 0x530 or code > 0x3000
                         or name in ("dotlessi", "aacute", "amacron", "odieresis", "eacute")):
                return ac.Ink(30, -10, 470, 480, advance=500)
            return ac.Ink(0, 520, 200, 620, advance=200)  # a mark, or punctuation at a mark's height
        return InkOf(dict((name, of(name)) for name in self.NAMES))

    def clean(self, cell, where):
        self.assertFalse(cell.rstrip().endswith(u"."), "%s ends with a period: %r" % (where, cell))
        for sign in self.BANNED:
            self.assertNotIn(sign, cell, "%s: %r" % (where, cell))
        self.assertEqual(cell, cell.strip(), where)

    def rows(self, compact):
        """[(recipe, its Built from cell, its tooltip)] of every row the dialog would list."""
        font = ac.Font(list(self.NAMES), [(name, code) for name, code in self.NAMES.items()], empty=["amacron"])
        characters = [ac.unichr_(code) for _, _, ranges in ac.SETS[:-1] for low, high in ranges for code in range(low, high)]
        characters += [ac.unichr_(code) for code in sorted(ac.MARKS) if code < 0x3000]  # what Font Check hands over
        recipes = ac.plan(font, characters, True)
        ink, placement = self.ink(), ac.Placement(1000.0, MODEL)
        metrics = ac.Metrics(1000, 700, -350, 700)  # room up to 850: stacks on capitals do not fit
        mirrored = Stub(isComponent=True, shapeData=Stub(componentGlyph="breve"),
                        transform=Stub(m11=lambda: 1.0, m22=lambda: -1.0, m12=lambda: 0.0, m21=lambda: 0.0,
                                       dx=lambda: 0.0, dy=lambda: 900.0))
        plain = Stub(isComponent=True, shapeData=Stub(componentGlyph="o"),
                     transform=Stub(m11=lambda: 1.0, m22=lambda: 1.0, m12=lambda: 0.0, m21=lambda: 0.0,
                                    dx=lambda: 0.0, dy=lambda: 0.0))
        glyph = Stub(isNull=False, getLayerByName=lambda master: Stub(shapes=[plain, mirrored]))
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.master, dialog.package = "Regular", Stub(upm=1000, findName=lambda name: glyph)
        dialog.inks = {"Regular": ink}

        def picture(recipe, size):
            recipe.placed_parts = ac.place(recipe, ink, placement, metrics)[0]
        dialog.picture = picture
        shifts = ((0, 0), (25, -4), None)
        dialog.existing_shift = lambda recipe: shifts[recipe.code % 3]
        acute = one_mark(0xF3, "o", "acute", "above", "acute")
        ogonek = one_mark(0x105, "a", "ogonek", "below", "ogonek")
        touches = [u""] + [ac.touch_note(recipe, [measure], 12.0) for recipe in (acute, ogonek)
                           for measure in ((True, True, False, False), (False, True, False, False),
                                           (False, False, True, True), (False, False, False, True),
                                           (False, False, False, False))]
        found = []
        saved = ac._qt
        try:
            ac._qt = lambda: (None, None)
            for at, recipe in enumerate(recipes):
                recipe.compact = compact
                if recipe.missing:  # as the list writes a row that cannot be built
                    found.append((recipe, recipe.describe(), u""))
                    continue
                recipe.touches = touches[at % len(touches)]
                if at % 7 == 0:
                    recipe.adjust = {0: [3.0, -2.0, 1.0, 1.0]}
                kept = {}
                item = Stub(setIcon=lambda icon: None, setText=lambda column, value: kept.__setitem__("cell", value),
                            setToolTip=lambda column, value: kept.__setitem__("tip", value))
                dialog.refresh_item(item, recipe, first=True)
                self.assertEqual(kept["cell"], recipe.cell)
                found.append((recipe, recipe.cell, kept["tip"]))
        finally:
            ac._qt = saved
        return found

    def test_no_built_from_cell_ends_with_a_period_or_holds_a_dash(self):
        seen = set()
        for compact in (True, False):
            rows = self.rows(compact)
            self.assertGreater(len(rows), 500, "the whole of the sets, and the font's own letters with diacritics")
            for recipe, cell, tip in rows:
                self.clean(cell, u"U+%04X" % recipe.code)
                self.assertTrue(tip == u"" or tip.endswith(u"."), "a tooltip is a sentence: %r" % tip)
                for sign in self.BANNED:
                    self.assertNotIn(sign, tip)
                for word in (u"gaps closed", u"marks at", u"still", u"too tall for a 120% line", u"placed by hand",
                             u"suggested: mark", u"placed as suggested", u"drawn, not built", u"filled when built",
                             u"draft for", u"needs ", u"a combining mark", u"mirrored", u"comes within", u"overlaps",
                             u"does not touch", u"fonts draw for"):
                    if word in cell:
                        seen.add(word)
            if compact:
                self.assertTrue(any(u"(gaps closed to fit a 120% line" in cell or u"; gaps closed" in cell
                                    for _, cell, _ in rows), "the compacting note, in parentheses")
            else:
                self.assertFalse(any(u"gaps closed" in cell for _, cell, _ in rows))
        self.assertEqual(len(seen), 17, "every kind of note was written by some row: %s" % sorted(seen))

    def test_the_exact_rows_of_the_owners_report(self):
        rows = dict((recipe.char, cell) for recipe, cell, _ in self.rows(True) if not recipe.missing)
        a_dieresis_macron, a_dot_macron = ac.unichr_(0x01DE), ac.unichr_(0x01E0)
        self.assertTrue(rows[a_dieresis_macron].startswith(u"A + dieresis + macron ("), rows[a_dieresis_macron])
        self.assertIn(u"gaps closed", rows[a_dieresis_macron])
        self.assertTrue(rows[a_dieresis_macron].endswith(u")"))
        self.assertTrue(rows[a_dot_macron].startswith(u"A + period (draft for dot above) + macron ("), rows[a_dot_macron])

    def test_no_cell_of_the_anchors_list_either(self):
        inks = {"A": ac.Ink(10, 0, 590, 700, advance=600), "e": ac.Ink(30, -10, 470, 480, advance=500),
                "acutecomb": ac.Ink(-60, 550, 60, 660), "dotbelowcomb": ac.Ink(-40, -180, 40, -100),
                "ogonekcomb": ac.Ink(-100, -200, 0, 0), "f_i": ac.Ink(20, 0, 500, 700, advance=520)}
        glyphs = ac.plan_anchors([("A", 0x41, "base", inks["A"], {}), ("e", 0x65, "base", inks["e"], {"top": (250, 500)}),
                                  ("acutecomb", 0x0301, "mark", inks["acutecomb"], {}),
                                  ("dotbelowcomb", 0x0323, "mark", inks["dotbelowcomb"], {"_bottom": (0, -90)}),
                                  ("ogonekcomb", 0x0328, "mark", inks["ogonekcomb"], {"_bottom": (-50, 0)}),
                                  ("f_i", 0, "ligature", inks["f_i"], {}, 2)], {}, "latin", 1000, 500)
        glyphs[0].adjust = {"top": [12.0, -3.0]}
        glyphs[1].adjust = {"top": [5.0, 5.0]}  # an anchor of its own, moved
        glyphs[2].elsewhere = True
        names = dict((code, u"uni%04X" % code) for code in list(range(0x0E01, 0x0E2F)) + list(range(0x0E31, 0x0E4F)))
        every = set(names.values())
        every.update(name + suffix for name in list(names.values()) for suffix in (u".small", u".short", u".less"))
        rules = ac.thai_rules(names, every)
        self.assertTrue(rules, "the substitutions' rows")
        seen = 0
        for g in list(glyphs) + rules:
            anchors, note = ac.anchor_cells(g)
            for cell in (anchors, note):
                if cell:
                    self.clean(cell, g.name)
                    seen += 1
        self.assertGreater(seen, 12)
        self.assertEqual(ac.anchor_cells(glyphs[0])[1], u"moved by hand")
        self.assertIn(u"moved to", ac.anchor_cells(glyphs[1])[0])
        self.assertTrue(ac.anchor_cells(rules[0])[1].endswith(u"(ccmp)"), "data in parentheses")


# -- mirrored components set right: FontLab's glyphs, layers, shapes, and contours, stood in for ----------

class FlTransform(object):
    """A QTransform's six numbers, in Qt's order."""

    def __init__(self, m11=1.0, m12=0.0, m21=0.0, m22=1.0, dx=0.0, dy=0.0):
        self.values = tuple(float(value) for value in (m11, m12, m21, m22, dx, dy))

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

    def point(self, x, y):
        m11, m12, m21, m22, dx, dy = self.values
        return (m11 * x + m21 * y + dx, m12 * x + m22 * y + dy)


def signed_area(points):
    """Twice a polygon's area: negative when it runs clockwise (y up)."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))


class FlContour(object):
    """A contour: its nodes can be read; written through nodes() only where the font's FontLab lets them."""

    def __init__(self, points, font=None):
        self.points, self.font = [(float(x), float(y)) for x, y in points], font

    clockwise = property(lambda self: signed_area(self.points) < 0)

    def reverse(self):
        self.points = [self.points[0]] + self.points[:0:-1]  # (its first node kept first, as FontLab does)

    def clone(self):
        return FlContour(self.points, self.font)

    def nodes(self):
        contour = self

        class Node(object):
            def __init__(self, at):
                self.__dict__["at"] = at

            x = property(lambda self: contour.points[self.at][0], lambda self, value: self.put(0, value))
            y = property(lambda self: contour.points[self.at][1], lambda self, value: self.put(1, value))

            def put(self, axis, value):
                if contour.font is None or contour.font.how != "nodes":
                    return  # (a copy of the node: writing it changes nothing, as PythonQt may hand them)
                point = list(contour.points[self.at])
                point[axis] = float(value)
                contour.points[self.at] = tuple(point)
        return [Node(at) for at in range(len(self.points))]


class FlShape(object):
    """A layer's shape: contours of its own, or a component, whose contours are its glyph's (as FontLab
    hands them: Auto Kerning's layer_path draws a component by them and the component's transform)."""

    def __init__(self, contours=(), component=None, transform=None, font=None):
        self.own = [FlContour(c.points if isinstance(c, FlContour) else c, font) for c in contours]
        self.component, self.transform, self.font, self.layer = component, transform or FlTransform(), font, None

    isComponent = property(lambda self: self.component is not None)
    shapeData = property(lambda self: Stub(componentGlyph=self.component))

    @property
    def contours(self):
        if self.component is None:
            return self.own
        glyph = self.layer.font.glyphs.get(self.component)
        layer = glyph.by_master.get(self.layer.master) if glyph is not None else None
        return [contour for shape in (layer.shapes if layer is not None else []) for contour in shape.contours]

    def clone(self):
        return FlShape(self.own, self.component, self.transform, self.font)


class FlLayer(object):
    def __init__(self, font, master, advance=0.0, shapes=()):
        self.font, self.master, self.advanceWidth, self.shapes = font, master, float(advance), []
        for shape in shapes:
            self.addShape(shape)

    def addShape(self, shape):
        shape.layer, shape.font = self, self.font
        for contour in shape.own:
            contour.font = self.font
        self.shapes.append(shape)

    def removeAllShapes(self):
        self.shapes = []

    def setGlyphComponents(self, components, width, package, flag):
        self.advanceWidth = float(width)
        self.shapes = []
        refused = self.font.refuses is True or self.font.refuses == self.master  # (every master, or that one)
        for component in ([] if refused else components):
            self.addShape(FlShape(component=component.name, transform=component.transform))

    def applyTransform(self, transform):
        """As the font's stand-in FontLab takes it: its outlines moved ("bake"), moved and set to run the
        right way by itself ("bake+reverse"), or not there at all."""
        if self.font.how not in ("bake", "bake+reverse"):
            raise AttributeError("applyTransform")
        for shape in self.shapes:
            for contour in shape.own:
                contour.points = [transform.point(x, y) for x, y in contour.points]
                if self.font.how == "bake+reverse":
                    contour.reverse()


class FlGlyph(object):
    isNull = False

    def __init__(self, name, font):
        self.name, self.font, self.by_master, self.fgGlyph = name, font, {}, Stub(unicode=None)

    layers = property(lambda self: list(self.by_master.values()))

    def getLayerByName(self, master, create=False):
        if master not in self.by_master and create:
            self.by_master[master] = FlLayer(self.font, master)
        return self.by_master.get(master)

    def update(self):
        pass


class FlFont(object):
    """A font (flPackage, stood in for): how says what its FontLab does to mirror outlines."""

    def __init__(self, how="bake", masters=("Regular", "Bold")):
        self.how, self.masters, self.glyphs, self.refuses = how, list(masters), {}, False
        self.fgPackage, self.upm = Stub(id=1), 1000

    def findName(self, name):
        return self.glyphs.get(name)

    def findUnicode(self, code):
        return None

    def addGlyph(self, new):
        self.glyphs[new.name] = FlGlyph(new.name, self)  # (a copy, without layers)

    def deleteGlyph(self, glyph):
        del self.glyphs[glyph.name]

    def draw(self, name, advance, contours, bold=1.0):
        glyph = self.glyphs[name] = FlGlyph(name, self)
        for master in self.masters:
            k = bold if master == "Bold" else 1.0
            glyph.by_master[master] = FlLayer(self, master, advance * k, [
                FlShape([[(x * k, y * k) for x, y in points] for points in contours])])
        return glyph

    def compose(self, name, advance, components, bold=1.0):
        glyph = self.glyphs[name] = FlGlyph(name, self)
        for master in self.masters:
            k = bold if master == "Bold" else 1.0
            glyph.by_master[master] = FlLayer(self, master, advance * k, [
                FlShape(component=part, transform=FlTransform(m11, m12, m21, m22, dx * k, dy * k))
                for part, (m11, m12, m21, m22, dx, dy) in components])
        return glyph

    def outline(self, name, master):
        """A glyph's contours as drawn in a master: its own, and its components' through their transforms."""
        found = []
        for shape in self.glyphs[name].by_master[master].shapes:
            inner = self.outline(shape.component, master) if shape.isComponent else [c.points for c in shape.own]
            found += [[shape.transform.point(x, y) for x, y in points] for points in inner]
        return found


def fl_path(layer):
    """Auto Kerning's layer_path, stood in for: a path that tells its box and whether it is empty."""
    found = []
    for shape in layer.shapes:
        if shape.isComponent:
            inner = [contour for contour in layer.font.outline(shape.component, layer.master)]
        else:
            inner = [c.points for c in shape.own]
        found += [[shape.transform.point(x, y) for x, y in points] for points in inner]
    xs = [x for points in found for x, _ in points]
    ys = [y for points in found for _, y in points]
    box = Stub(left=lambda: min(xs), right=lambda: max(xs), top=lambda: min(ys), bottom=lambda: max(ys))
    return Stub(isEmpty=lambda: not xs, boundingRect=lambda: box)


class FlComponent(object):
    def __init__(self, name):
        self.name, self.transform = name, FlTransform()


FL = Stub(flGlyph=lambda: Stub(name=None), GlyphComponent=FlComponent)
# A bar with a slanted end, clockwise: no mirror of it is itself (a mirror of a rectangle would be, and no
# measure could tell whether it had been mirrored)
FL_MARK = [(0, 0), (0, 200), (200, 200), (300, 0)]
FLIP_Y, MIRROR_X = (1, 0, 0, -1, 250, 600), (-1, 0, 0, 1, 550, 400)  # each lands the mark on 250..550 by 400..600


def fl_font(how="bake"):
    """o (a square), mark (a bar), and letters whose mark is a mirrored component over the o's top edge."""
    font = FlFont(how)
    font.draw("o", 700, [HOLE_BASE], bold=1.1)
    font.draw("mark", 300, [FL_MARK], bold=1.1)
    font.compose("oflip", 700, [("o", (1, 0, 0, 1, 0, 0)), ("mark", FLIP_Y)], bold=1.1)
    font.compose("oflip.alt", 700, [("o", (1, 0, 0, 1, 0, 0)), ("mark", (1, 0, 0, -1, 200, 620))], bold=1.1)
    font.compose("omirror", 700, [("o", (1, 0, 0, 1, 0, 0)), ("mark", MIRROR_X)], bold=1.1)
    font.compose("oplain", 700, [("o", (1, 0, 0, 1, 0, 0)), ("mark", (1, 0, 0, 1, 250, 400))], bold=1.1)
    return font


class MirrorFixTests(unittest.TestCase):
    """A mirrored component found in the font, set right on a click: the mark mirrored into a glyph of
    its own with its contours reversed, the letters' components pointed to it."""

    LETTERS = ("oflip", "oflip.alt", "omirror", "oplain")

    def setUp(self):
        self.saved = ac._qt
        ac._qt = lambda: (Stub(), Stub(QTransform=FlTransform))

    def tearDown(self):
        ac._qt = self.saved

    def dialog(self, font, letters=None):
        dialog = ac.AccentsDialog.__new__(ac.AccentsDialog)
        dialog.package, dialog.master, dialog.fontlab, dialog.hidden = font, "Regular", FL, set()
        dialog.steps, dialog.lines, dialog.reads = [], [], []
        dialog.ak = Stub(layer_path=fl_path, b=lambda value: u"%s" % value, html=lambda value: u"%s" % value,
                         glyph_links=lambda chars: u" ".join(chars),
                         notify_changed=lambda fontlab, package, title, glyphs=(): dialog.steps.append(
                             (title, sorted(set(g.name for g in glyphs)))))
        dialog.current_font = lambda: font
        dialog.package_key = lambda package: None if package is None else id(package)
        dialog.run = lambda: dialog.reads.append(1)
        dialog.log = Stub(add=lambda line, level="info": dialog.lines.append((level, line)))
        dialog.recipes = []
        for at, name in enumerate(self.LETTERS if letters is None else letters):
            recipe = ac.Recipe(ac.unichr_(0x1E00 + at), name, "o")
            recipe.existing = name
            layer = font.glyphs[name].by_master["Regular"]
            recipe.mirrored = ac.mirrored_components(layer)
            dialog.recipes.append(recipe)
        return dialog

    def overlap(self, font, name, master="Regular"):
        k = 1.1 if master == "Bold" else 1.0
        return winding(font.outline(name, master), 400 * k, 450 * k)

    def test_the_arithmetic_of_a_mirror_taken_out_of_a_transform(self):
        self.assertEqual(ac.mirror_axis(1, 0, 0, -1), "y")
        self.assertEqual(ac.mirror_axis(-1, 0, 0, 1), "x")
        self.assertEqual(ac.mirror_axis(0, 1, 1, 0), "x", "turned and mirrored: either mirror does")
        self.assertEqual(ac.mirror_of("x", 300.4, 0, 200), (-1.0, 1.0, 300.0, 0.0), "about the middle of its advance")
        self.assertEqual(ac.mirror_of("y", 300, 520, 621), (1.0, -1.0, 0.0, 1141.0), "about the middle of its ink")
        points = [(0.0, 0.0), (300.0, 0.0), (120.0, 200.0), (-40.0, 75.5)]
        for values in ((1, 0, 0, -1, 250, 600), (-1, 0, 0, 1, 550, 400), (-0.8, 0, 0, 0.8, 30, 700),
                       (0.9, 0.2, 0.3, -1.1, 12, -40), (0, 1, 1, 0, 5, 6), (-1.2, 0.5, 0.1, 0.7, 0, 0)):
            self.assertTrue(ac.is_mirror(values), values)
            axis = ac.mirror_axis(*values[:4])
            mirror = ac.mirror_of(axis, 300, 0, 200)
            proper = ac.without_mirror(values, mirror)
            self.assertFalse(ac.is_mirror(proper), "what is left of it mirrors nothing: %r" % (proper,))
            for x, y in points:
                mirrored_x, mirrored_y = mirror[0] * x + mirror[2], mirror[1] * y + mirror[3]
                drawn = FlTransform(*proper).point(mirrored_x, mirrored_y)
                wanted = FlTransform(*values).point(x, y)
                self.assertAlmostEqual(drawn[0], wanted[0], 6)
                self.assertAlmostEqual(drawn[1], wanted[1], 6, "the corrected glyph through it draws what the mirrored "
                                                               "component drew")
        self.assertEqual(ac.corrected_name(u"caron", "y", lambda name: False), u"caron.flipped")
        self.assertEqual(ac.corrected_name(u"comma", "x", lambda name: False), u"comma.mirrored")
        self.assertEqual(ac.corrected_name(u"caron.case", "y", lambda name: name in (u"caron.case.flipped", u"caron.case.flipped2")),
                         u"caron.case.flipped3")
        self.assertEqual(ac.corrected_text(1, 1), u"Corrected the mirrored components of 1 glyph (1 glyph added, "
                                                  u"mirrored with its contours reversed)")
        self.assertEqual(ac.corrected_text(3, 2), u"Corrected the mirrored components of 3 glyphs (2 glyphs added, "
                                                  u"mirrored with their contours reversed)")
        self.assertEqual(ac.corrected_text(2, 0), u"Corrected the mirrored components of 2 glyphs")

    def check_corrected(self, how):
        font = fl_font(how)
        before = dict(((name, master), fl_path(font.glyphs[name].by_master[master]).boundingRect())
                      for name in self.LETTERS for master in font.masters)
        boxes = dict((key, (box.left(), box.top(), box.right(), box.bottom())) for key, box in before.items())
        for name in ("oflip", "oflip.alt", "omirror"):
            self.assertEqual(self.overlap(font, name), 0, "%s: a hole where the mirrored mark overlaps the o" % name)
        self.assertEqual(abs(self.overlap(font, "oplain")), 2)
        dialog = self.dialog(font)
        self.assertEqual([r.existing for r in dialog.correctable()], ["oflip", "oflip.alt", "omirror"])
        dialog.correct_mirrored()
        self.assertEqual(sorted(font.glyphs), sorted(["o", "mark", "mark.flipped", "mark.mirrored"] + list(self.LETTERS)),
                         "one corrected glyph for each way the mark was mirrored, used by every letter that needs it")
        for master in font.masters:
            for name in ("oflip", "oflip.alt", "omirror"):
                layer = font.glyphs[name].by_master[master]
                self.assertEqual(ac.mirrored_components(layer), [], "%s %s (%s)" % (name, master, how))
                self.assertTrue(all(shape.isComponent for shape in layer.shapes), "still a glyph of components")
                box = fl_path(layer).boundingRect()
                for found, wanted in zip((box.left(), box.top(), box.right(), box.bottom()), boxes[(name, master)]):
                    self.assertAlmostEqual(found, wanted, 6, "it looks as it did")
                self.assertEqual(abs(self.overlap(font, name, master)), 2, "%s %s (%s): the hole is filled: both parts "
                                                                           "run the same way" % (name, master, how))
            self.assertEqual([s.component for s in font.glyphs["oflip"].by_master[master].shapes], ["o", "mark.flipped"])
            self.assertEqual([s.component for s in font.glyphs["omirror"].by_master[master].shapes], ["o", "mark.mirrored"])
            for helper in ("mark.flipped", "mark.mirrored"):
                drawn = font.outline(helper, master)
                source = font.outline("mark", master)
                self.assertEqual([signed_area(points) < 0 for points in drawn],
                                 [signed_area(points) < 0 for points in source], "wound as the mark is, not reversed")
        self.assertEqual(font.glyphs["oplain"].by_master["Regular"].shapes[1].transform.values, (1.0, 0.0, 0.0, 1.0, 250.0, 400.0),
                         "a glyph with nothing mirrored is not touched")
        self.assertEqual(len(dialog.steps), 1, "one step of the History")
        self.assertEqual(dialog.steps[0][0], u"FreeLab Diacritics mirrored components")
        self.assertEqual(dialog.steps[0][1], ["mark.flipped", "mark.mirrored", "oflip", "oflip.alt", "omirror"])
        self.assertEqual(dialog.lines[0][0], "done")
        self.assertIn(u"Corrected the mirrored components of 3 glyphs (2 glyphs added, mirrored with their contours "
                      u"reversed)", dialog.lines[0][1])
        self.assertIn(u"added: mark.flipped, mark.mirrored", dialog.lines[0][1])
        self.assertEqual((len(dialog.lines), dialog.reads), (1, [1]), "and the list read again")
        return font

    def test_outlines_fontlab_mirrors_in_place(self):
        font = self.check_corrected("bake")
        shape = font.glyphs["mark.flipped"].by_master["Regular"].shapes[0]
        self.assertEqual(shape.transform.values, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), "its outlines themselves were mirrored")
        self.assertEqual(sorted(shape.own[0].points), [(0.0, 0.0), (0.0, 200.0), (200.0, 0.0), (300.0, 200.0)],
                         "upside down about the middle of its ink: it stands where the mark does")
        across = font.glyphs["mark.mirrored"].by_master["Regular"].shapes[0]
        self.assertEqual(sorted(across.own[0].points), [(0.0, 0.0), (100.0, 200.0), (300.0, 0.0), (300.0, 200.0)],
                         "left to right about the middle of its advance width")

    def test_a_fontlab_that_sets_the_direction_right_by_itself_is_not_reversed_twice(self):
        self.check_corrected("bake+reverse")

    def test_outlines_mirrored_node_by_node(self):
        font = self.check_corrected("nodes")  # no applyTransform: each node is moved, and read back
        shape = font.glyphs["mark.flipped"].by_master["Regular"].shapes[0]
        self.assertEqual(sorted(shape.own[0].points), [(0.0, 0.0), (0.0, 200.0), (200.0, 0.0), (300.0, 200.0)])

    def test_a_fontlab_that_mirrors_nothing_changes_nothing_and_says_so(self):
        font = fl_font("neither")
        dialog = self.dialog(font)
        dialog.correct_mirrored()
        self.assertEqual(sorted(font.glyphs), sorted(["o", "mark"] + list(self.LETTERS)), "no glyph left behind")
        self.assertEqual(font.glyphs["oflip"].by_master["Regular"].shapes[1].transform.values, (1.0, 0.0, 0.0, -1.0, 250.0, 600.0))
        self.assertEqual([level for level, _ in dialog.lines], ["warning"] * 3, "each glyph left as it is, named")
        self.assertIn(u"keeps a mirrored component: FontLab did not mirror its outlines.", dialog.lines[0][1])
        self.assertEqual(dialog.steps, [], "nothing was written: no step of the History")

    def test_components_fontlab_does_not_keep_are_put_back(self):
        font = fl_font("bake")
        font.refuses = True
        dialog = self.dialog(font, ["oflip"])
        dialog.correct_mirrored()
        layer = font.glyphs["oflip"].by_master["Regular"]
        self.assertEqual([(s.component, s.transform.values) for s in layer.shapes],
                         [("o", (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)), ("mark", (1.0, 0.0, 0.0, -1.0, 250.0, 600.0))], "as it was")
        self.assertNotIn("mark.flipped", font.glyphs, "the corrected glyph no letter uses is taken out again")
        self.assertIn(u"FontLab did not keep the new components in master", dialog.lines[-1][1])
        self.assertEqual(len(dialog.steps), 1, "its shapes were taken out and put back: recorded, to be undone whole")

    def test_a_mark_made_of_components_is_left_and_named(self):
        font = fl_font("bake")
        font.compose("mark", 300, [("o", (0.5, 0, 0, 0.4, 0, 0))])
        dialog = self.dialog(font, ["oflip"])
        dialog.correct_mirrored()
        self.assertIn(u"mark is itself made of components in master Regular: decompose it first", dialog.lines[-1][1])
        self.assertNotIn("mark.flipped", font.glyphs)

    def test_a_corrected_glyph_of_the_font_is_used_again_and_another_name_is_not_taken(self):
        font = fl_font("bake")
        self.dialog(font, ["oflip"]).correct_mirrored()
        self.assertIn("mark.flipped", font.glyphs)
        dialog = self.dialog(font, ["oflip.alt"])
        dialog.correct_mirrored()
        self.assertIn(u"Corrected the mirrored components of 1 glyph:", dialog.lines[0][1], "none added: the font's own")
        self.assertEqual(sorted(name for name in font.glyphs if name.startswith("mark.")), ["mark.flipped"])
        other = fl_font("bake")
        other.draw("mark.flipped", 300, [HOLE_BASE])  # a glyph of that name that is something else
        self.dialog(other, ["oflip"]).correct_mirrored()
        self.assertEqual([s.component for s in other.glyphs["oflip"].by_master["Regular"].shapes], ["o", "mark.flipped2"])
        # the numbered one is found again too: a second run makes no mark.flipped3 (one more at every run before)
        dialog = self.dialog(other, ["oflip.alt"])
        dialog.correct_mirrored()
        self.assertEqual([s.component for s in other.glyphs["oflip.alt"].by_master["Bold"].shapes], ["o", "mark.flipped2"])
        self.assertEqual(sorted(name for name in other.glyphs if name.startswith("mark.")), ["mark.flipped", "mark.flipped2"])
        self.assertIn(u"Corrected the mirrored components of 1 glyph:", dialog.lines[0][1], "none added")

    def as_drawn(self, font, name):
        return dict((master, [(s.component, s.transform.values) for s in font.glyphs[name].by_master[master].shapes])
                    for master in font.masters)

    def test_a_master_that_cannot_be_set_right_leaves_every_master_as_it_was(self):
        """Masters set right one by one: one that failed kept its mirrored component while those before it
        pointed to the corrected glyph, and the glyph no longer interpolated."""
        font = fl_font("bake")
        before = self.as_drawn(font, "oflip")
        font.refuses = "Bold"  # Regular is written first, then FontLab keeps nothing in Bold
        dialog = self.dialog(font, ["oflip"])
        dialog.correct_mirrored()
        self.assertEqual(self.as_drawn(font, "oflip"), before, "Regular put back too")
        self.assertNotIn("mark.flipped", font.glyphs, "the corrected glyph no letter uses is taken out again")
        self.assertIn(u"in master Bold: left as it was in every master", dialog.lines[-1][1])
        self.assertEqual(dialog.lines[-1][0], "warning")
        # a mark with no outline in one master: planned first, so nothing is written at all
        font = fl_font("bake")
        font.glyphs["mark"].by_master["Bold"].shapes = []
        before = self.as_drawn(font, "oflip")
        dialog = self.dialog(font, ["oflip"])
        dialog.correct_mirrored()
        self.assertEqual(self.as_drawn(font, "oflip"), before)
        self.assertNotIn("mark.flipped", font.glyphs)
        self.assertIn(u"keeps a mirrored component: mark has no outline in master Bold.", dialog.lines[-1][1])
        self.assertEqual(dialog.steps, [], "nothing was written: no step of the History")

    def test_a_search_or_a_changed_font_limits_it(self):
        font = fl_font("bake")
        dialog = self.dialog(font)
        dialog.hidden = set([0, 1])  # a search hides oflip and oflip.alt
        self.assertEqual([r.existing for r in dialog.correctable()], ["omirror"])
        dialog.current_font = lambda: fl_font("bake")
        dialog.correct_mirrored()
        self.assertEqual(dialog.lines[-1][0], "warning")
        self.assertIn(u"Nothing was corrected", dialog.lines[-1][1])
        self.assertNotIn("mark.mirrored", font.glyphs)

    def test_build_never_writes_a_mirror_a_draft_would_bring(self):
        font = fl_font("bake")
        # the font's own ^ is one component, its caron mirrored upside down: the caron drafted from ^ turned by
        # a half turn would be the caron mirrored left to right
        font.draw("caron", 300, [[(0, 500), (150, 700), (300, 500), (150, 560)]])
        font.compose("asciicircum", 300, [("caron", (1, 0, 0, -1, 0, 1200))])
        bare = ac.Font(["o", "asciicircum", "caron.unlisted"], [("o", 0x6F), ("asciicircum", 0x5E)])
        recipe = ac.plan(bare, [ac.unichr_(0x01D2)])[0]
        self.assertEqual(recipe.marks[0].parts[0][:3], ("asciicircum", -1.0, -1.0))
        dialog = self.dialog(font, [])
        dialog.recipes = [recipe]
        ink = InkOf({"o": ac.Ink(100, 0, 600, 500, advance=700), "asciicircum": ac.Ink(0, 500, 300, 700, advance=300)})
        dialog.inks = dict((master, ink) for master in font.masters)
        dialog.placements = dict((master, ac.Placement(1000.0, MODEL)) for master in font.masters)
        dialog.metrics = lambda package: None
        dialog.harvest = lambda: None
        dialog.closeness = lambda r: u""
        dialog.log_touches = lambda noted, how: None
        dialog.built_names, dialog.built_font = [], None
        dialog.build()
        built = font.glyphs[recipe.name]
        for master in font.masters:
            layer = built.by_master[master]
            self.assertEqual([s.component for s in layer.shapes], ["o", "caron.mirrored"], "no ^, and no mirror of it")
            self.assertEqual(ac.mirrored_components(layer), [])
        placed, _ = ac.place(recipe, ink, dialog.placements["Regular"])
        name, sx, sy, dx, dy = ac.unwrapped(font, "Regular", *placed[1])
        self.assertTrue(ac.reverses_direction(sx, sy), "what the draft alone would have written")
        wanted = [FlTransform(sx, 0, 0, sy, round(dx), round(dy)).point(x, y) for x, y in font.outline("caron", "Regular")[0]]
        drawn = font.outline(recipe.name, "Regular")[1]
        self.assertEqual(sorted(drawn), sorted(wanted), "the same picture")
        self.assertEqual(signed_area(drawn) < 0, signed_area(font.outline("o", "Regular")[0]) < 0,
                         "wound as the letter is: no hole where they would overlap")
        self.assertNotEqual(signed_area(wanted) < 0, signed_area(drawn) < 0, "which the mirrored component was not")
        self.assertEqual(built.fgGlyph.unicode, 0x01D2)
        lines = [line for level, line in dialog.lines if u"corrected glyph" in line]
        self.assertEqual(len(lines), 1)
        self.assertIn(u"1 glyph built with a corrected glyph in the place of a mirrored one", lines[0])
        self.assertIn(u"(1 glyph added, mirrored with its contours reversed, so that no hole shows where it overlaps: "
                      u"caron.mirrored)", lines[0])
        self.assertFalse(any(u"built with a mirrored component" in line for _, line in dialog.lines))
        self.assertIn("caron.mirrored", dialog.steps[0][1], "in the build's one step of the History")

    def build_caron(self, font, bold_caron=True):
        """A build of o with caron, drafted from ^ (one component: the caron mirrored upside down)."""
        font.draw("caron", 300, [[(0, 500), (150, 700), (300, 500), (150, 560)]])
        if not bold_caron:
            font.glyphs["caron"].by_master["Bold"].shapes = []
        font.compose("asciicircum", 300, [("caron", (1, 0, 0, -1, 0, 1200))])
        bare = ac.Font(["o", "asciicircum", "caron.unlisted"], [("o", 0x6F), ("asciicircum", 0x5E)])
        recipe = ac.plan(bare, [ac.unichr_(0x01D2)])[0]
        dialog = self.dialog(font, [])
        dialog.recipes = [recipe]
        ink = InkOf({"o": ac.Ink(100, 0, 600, 500, advance=700), "asciicircum": ac.Ink(0, 500, 300, 700, advance=300)})
        dialog.inks = dict((master, ink) for master in font.masters)
        dialog.placements = dict((master, ac.Placement(1000.0, MODEL)) for master in font.masters)
        dialog.metrics = lambda package: None
        dialog.harvest = lambda: None
        dialog.closeness = lambda r: u""
        dialog.log_touches = lambda noted, how: None
        dialog.built_names, dialog.built_font = [], None
        dialog.build()
        return dialog, recipe

    def test_a_build_sets_a_mirror_right_in_every_master_or_in_none(self):
        """A mirror set right in Regular and left in Bold (the caron has no outline there): the built glyph's
        masters no longer matched. Both keep the mirrored component, and the corrected glyph made for it,
        used by nothing, is taken out again."""
        font = fl_font("bake")
        dialog, recipe = self.build_caron(font, bold_caron=False)
        built = font.glyphs[recipe.name]
        self.assertEqual([[s.component for s in built.by_master[master].shapes] for master in font.masters],
                         [["o", "caron"], ["o", "caron"]], "the same components in both masters")
        self.assertNotIn("caron.mirrored", font.glyphs, "a corrected glyph used by nothing is not left in the font")
        self.assertNotIn("caron.mirrored", dialog.steps[0][1])
        self.assertTrue(any(u"built with a mirrored component" in line for _, line in dialog.lines), dialog.lines)
        self.assertFalse(any(u"corrected glyph" in line for _, line in dialog.lines))

    def test_a_helper_made_for_a_glyph_then_not_built_is_taken_out(self):
        font = fl_font("bake")
        font.refuses = True  # FontLab keeps none of the components: the glyph is not built
        dialog, recipe = self.build_caron(font)
        self.assertNotIn(recipe.name, font.glyphs)
        self.assertNotIn("caron.mirrored", font.glyphs, "made at the first need, used by nothing: taken out again")
        self.assertTrue(any(level == "warning" and u"was not built" in line for level, line in dialog.lines))
        self.assertFalse(any(u"corrected glyph" in line for _, line in dialog.lines), "no glyph added to name")


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

    def test_forms_and_mark_stacks_are_no_ligatures(self):
        names = ["f", "i", "I", "J", "tildecomb", "acutecomb", "f_i", "f_i.sc", "f_i.ss01", "I_J.loclNLD",
                 "tildecomb_acutecomb"]
        chars = {"f": u"f", "i": u"i", "I": u"I", "J": u"J", "tildecomb": u"\N{COMBINING TILDE}",
                 "acutecomb": u"\N{COMBINING ACUTE ACCENT}"}
        found = [l.glyph for l in fc.ligatures(names, {}, chars, {})]
        self.assertEqual(found, ["f_i"], "a ligature's small cap or set form, a locl form, and stacked marks: "
                                         "their own features'")

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
        self.assertIn(u"@FreeLab_letters = [i i.2 i.3 l n];", code, "one class of the letters, shared by every rule")
        self.assertIn(u"  sub i i' by i.2;", code)
        self.assertIn(u"  sub i.2 @FreeLab_letters i' by i.3;", code)
        self.assertFalse(any(u"i.3 i' by" in line for line in code), "after the last alternate, the letter itself")
        text = fc.calt_text(u"feature calt {\n  sub x' y by x.alt;\n} calt;\n", code)
        self.assertIn(u"  sub x' y by x.alt;", text, "the feature's own code kept")
        self.assertEqual(fc.calt_text(text, code), text, "writing twice changes nothing")
        if HAVE_FONTTOOLS:
            self.assertIsNone(fc.check_code(text, letters + ["x", "x.alt", "y"]))


if __name__ == "__main__":
    unittest.main()
