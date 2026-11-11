"""Tests of FreeLab Feature Code's forms (case, locl, fractions and figures, small capitals, stylistic
sets) on synthetic glyph-name sets, and of its dialog run on fakes. Valid Python 2.7 and Python 3;
the feature parser's checks run where fontTools is installed. (features/train/forms_check.py
compiles the code into real fonts and shapes text with HarfBuzz.)"""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_feature_code as fc  # noqa: E402

try:
    import fontTools.feaLib.parser  # noqa: F401
    HAVE_FONTTOOLS = True
except Exception:
    HAVE_FONTTOOLS = False

DIGIT_NAMES = [u"zero", u"one", u"two", u"three", u"four", u"five", u"six", u"seven", u"eight", u"nine"]
LETTERS = [(u"A", 0x41), (u"a", 0x61), (u"B", 0x42), (u"b", 0x62), (u"I", 0x49), (u"i", 0x69), (u"L", 0x4C),
           (u"l", 0x6C), (u"J", 0x4A), (u"j", 0x6A), (u"O", 0x4F), (u"o", 0x6F), (u"H", 0x48), (u"g", 0x67),
           (u"e", 0x65), (u"r", 0x72), (u"dotlessi", 0x131), (u"Idotaccent", 0x130), (u"ampersand", 0x26),
           (u"hyphen", 0x2D), (u"parenleft", 0x28), (u"parenright", 0x29), (u"period", 0x2E), (u"slash", 0x2F),
           (u"fraction", 0x2044), (u"periodcentered", 0xB7), (u"ordfeminine", 0xAA), (u"ordmasculine", 0xBA),
           (u"iacute", 0xED), (u"Iacute", 0xCD), (u"acutecomb", 0x301)]


def make_info(extra=(), codes=(), widths=None, bounds=None, contours=None, base=True):
    """A font of the base letters and figures (unless base is False), plus extra glyph names and codes."""
    pairs = (list(LETTERS) + [(name, 0x30 + n) for n, name in enumerate(DIGIT_NAMES)]) if base else []
    pairs += list(codes)
    names = [name for name, _ in pairs] + list(extra)
    found = {}
    for name, code in pairs:
        found.setdefault(name, []).append(code)
    return fc.FontInfo(names, found, widths, bounds, contours)


def lines_of(feature):
    return u"\n".join(feature.lines())


def by_tag(features):
    return dict((feature.tag, feature) for feature in features)


def parse(text, names):
    """fontTools' complaint about a whole feature file, or None (None too without fontTools)."""
    return fc.check_code(text, names) if HAVE_FONTTOOLS else None


class IndexTests(unittest.TestCase):
    def test_suffix_anywhere(self):
        index = fc.forms_index([u"a", u"a.sc", u"a.ss01", u"a.sc.ss01", u".notdef", u"x.case"])
        self.assertEqual(index[u"sc"], {u"a": u"a.sc", u"a.ss01": u"a.sc.ss01"})
        self.assertEqual(index[u"ss01"], {u"a": u"a.ss01", u"a.sc": u"a.sc.ss01"})
        self.assertNotIn(u"case", index, "no x in the font")

    def test_characters(self):
        info = make_info([u"a.sc", u"uni0434.loclBGR", u"f_i"])
        self.assertEqual(info.char_of(u"a.sc"), u"a")
        self.assertEqual(info.char_of(u"uni0434.loclBGR"), fc.unichr_(0x434), "from its uniXXXX name")
        self.assertIsNone(info.char_of(u"f_i"))
        self.assertEqual(info.glyph(0x2044), u"fraction")


class AaltTests(unittest.TestCase):
    def test_alternates_gathered(self):
        info = make_info([u"hyphen.case", u"a.ss01"], codes=[(u"asciitilde", 0x7E), (u"tilde", 0x2DC),
                                                          (u"asciicircum", 0x5E)])
        texts = {u"salt": u"feature salt {\n  sub a by a.ss01;\n} salt;\n", u"liga": u"feature liga {\n  sub f i by f_i;\n} liga;\n"}
        features, _ = fc.form_features(info, texts)
        aalt = by_tag(features)[u"aalt"]
        code = lines_of(aalt)
        for line in (u"feature case;", u"feature salt;", u"feature ss01;", u"sub asciitilde from [tilde];",
                     u"sub tilde from [asciitilde];"):
            self.assertIn(line, code)
        self.assertNotIn(u"feature liga;", code, "ligatures are no alternates")
        self.assertNotIn(u"asciicircum", code, "no spacing circumflex in the font: no pair")
        by_tag(features)[u"case"].on = False
        self.assertNotIn(u"feature case;", lines_of(aalt), "a feature with no code is not referred to")
        if HAVE_FONTTOOLS:
            texts_now = fc.forms_texts(features, texts)
            whole = u"languagesystem DFLT dflt;\n" + texts_now[u"aalt"] + texts[u"salt"] + texts_now[u"ss01"]
            self.assertIsNone(parse(whole, info.names + [u"f_i", u"f"]))

    def test_aalt_first(self):
        class Features(object):
            def __init__(self, tags):
                self.order = [(tag, u"feature %s {\n} %s;\n" % (tag, tag)) for tag in tags]

            def keys(self):
                return [tag for tag, _ in self.order]

            def get_feature(self, tag):
                return dict(self.order)[tag]

            def remove(self, tag):
                self.order = [item for item in self.order if item[0] != tag]

            def set_feature(self, tag, text):
                self.remove(tag)
                self.order.append((tag, text))

        features = Features([u"liga", u"case", u"aalt"])
        self.assertTrue(fc.aalt_first(features))
        self.assertEqual(features.keys(), [u"aalt", u"liga", u"case"])
        self.assertFalse(fc.aalt_first(features), "first already")


class CaseTests(unittest.TestCase):
    def test_case_forms(self):
        info = make_info([u"hyphen.case", u"parenleft.case", u"acutecomb.case", u"periodcentered.loclCAT",
                          u"periodcentered.loclCAT.case", u"x.case"])
        feature = fc.case_feature(info)
        self.assertEqual([(r.source, r.target) for r in feature.rules],
                         [(u"acutecomb", u"acutecomb.case"), (u"hyphen", u"hyphen.case"),
                          (u"parenleft", u"parenleft.case"), (u"periodcentered.loclCAT", u"periodcentered.loclCAT.case")])
        self.assertIn(u"lookup FreeLab_case {", lines_of(feature))
        self.assertIsNone(fc.case_feature(make_info()))


class LoclTests(unittest.TestCase):
    def rules(self, info):
        feature = fc.locl_feature(info)
        return feature, [(r.data["language"], r.line) for r in feature.rules] if feature else []

    def test_romanian_by_code_points(self):
        # Adobe's names: Tcommaaccent is U+0162, the T with a cedilla; the code points decide
        info = make_info(codes=[(u"Scedilla", 0x15E), (u"Scommaaccent", 0x218), (u"Tcommaaccent", 0x162),
                                (u"uni021A", 0x21A)])
        _, rules = self.rules(info)
        for language in fc.ROMANIAN:
            self.assertIn((language, u"sub Scedilla by Scommaaccent;"), rules)
            self.assertIn((language, u"sub Tcommaaccent by uni021A;"), rules)
        self.assertFalse([r for r in rules if r[0] == "TRK"])

    def test_one_glyph_for_both_code_points(self):
        info = make_info([u"Scedilla"], codes=[(u"Scommaaccent", 0x15E), (u"Scommaaccent", 0x218)])
        _, rules = self.rules(info)
        self.assertIn(("TRK", u"sub Scommaaccent by Scedilla;"), rules, "the cedilla languages take the cedilla")
        self.assertIn(("GAG", u"sub Scommaaccent by Scedilla;"), rules)
        self.assertFalse([r for r in rules if r[0] == "ROM"], "Romanian has its comma already")

    def test_catalan(self):
        info = make_info([u"periodcentered.loclCAT", u"periodcentered.loclCAT.case"])
        feature, rules = self.rules(info)
        self.assertEqual(rules, [("CAT", u"sub l periodcentered' l by periodcentered.loclCAT;"),
                                 ("CAT", u"sub L periodcentered' L by periodcentered.loclCAT.case;")])
        self.assertEqual(feature.rules[0].data["scripts"], ("latn",), "a middle dot: the language's script")
        older = make_info(codes=[(u"ldot", 0x140), (u"Ldot", 0x13F)])
        _, rules = self.rules(older)
        self.assertEqual(rules, [("CAT", u"sub l' periodcentered' l by ldot;"), ("CAT", u"sub L' periodcentered' L by Ldot;")])

    def test_dutch(self):
        _, rules = self.rules(make_info([u"jacute", u"Jacute"]))
        self.assertEqual(rules, [("NLD", u"sub iacute j' by jacute;"), ("NLD", u"sub Iacute J' by Jacute;")])
        _, rules = self.rules(make_info([u"Iacute_J.loclNLD"]))
        self.assertEqual(rules, [("NLD", u"sub Iacute J by Iacute_J.loclNLD;")], "a ligature named for the language")

    def test_turkic_i(self):
        _, rules = self.rules(make_info([u"i.loclTRK"]))
        self.assertEqual(sorted(language for language, _ in rules), sorted(fc.TURKIC_I))
        self.assertTrue(all(line == u"sub i by i.loclTRK;" for _, line in rules))
        _, rules = self.rules(make_info([u"idotaccent"]))
        self.assertIn(("AZE", u"sub i by idotaccent;"), rules)

    def test_the_fonts_own_form_wins(self):
        info = make_info([u"i.loclTRK", u"i.loclAZE", u"Scedilla.loclROM"],
                         codes=[(u"Scedilla", 0x15E), (u"Scommaaccent", 0x218)])
        feature, rules = self.rules(info)
        self.assertEqual([line for language, line in rules if language == "AZE"], [u"sub i by i.loclAZE;"])
        self.assertEqual([line for language, line in rules if language == "ROM"], [u"sub Scedilla by Scedilla.loclROM;"])
        self.assertIn(("MOL", u"sub Scedilla by Scommaaccent;"), rules)
        self.assertIsNone(parse(fc.prefix_text(u"", fc.language_systems(feature)) +
                                fc.forms_feature_text("locl", None, feature.lines()), info.names))

    def test_any_other_locl_glyph(self):
        info = make_info([u"uni0434.loclBGR", u"g.loclVIET", u"uni0967.loclMARNEP", u"a.loclZZZ"],
                         codes=[(u"uni0434", 0x434), (u"uni0967", 0x967)])
        feature, rules = self.rules(info)
        found = dict(((r.data["language"], r.glyphs[0]), r) for r in feature.rules)
        self.assertEqual(found[("BGR", u"uni0434")].data["scripts"], ("cyrl",))
        self.assertIn(("VIT", u"g"), found, "Glyphs' VIET read as VIT")
        self.assertEqual(found[("MAR", u"uni0967")].data["scripts"], ("dev2", "deva"))
        self.assertIn(("NEP", u"uni0967"), found, "two languages run together")
        self.assertIn(u"does not know", found[("ZZZ", u"a")].note)

    def test_code_and_language_systems(self):
        info = make_info([u"i.loclTRK", u"uni0434.loclBGR", u"periodcentered.loclCAT"], codes=[(u"uni0434", 0x434)])
        feature = fc.locl_feature(info)
        text = lines_of(feature)
        self.assertTrue(text.index(u"script cyrl;") < text.index(u"script latn;"))
        self.assertIn(u"lookup FreeLab_locl_latn_CAT_context {", text)
        systems = fc.language_systems(feature)
        self.assertIn(("latn", "TRK"), systems)
        self.assertIn(("cyrl", "dflt"), systems)
        for rule in feature.rules:
            rule.on = rule.data["language"] != "BGR"
        self.assertNotIn(u"language BGR;", lines_of(feature), "a language with no row checked: left out")
        self.assertNotIn(("cyrl", "BGR"), fc.language_systems(feature))
        for rule in feature.rules:
            rule.on = True
        prefix = fc.prefix_text(u"", systems)
        self.assertTrue(prefix.splitlines()[1].startswith(u"languagesystem DFLT dflt;"), "DFLT first, where none was")
        names = info.names
        full = prefix + fc.forms_feature_text("locl", None, feature.lines())
        self.assertIsNone(parse(full, names))

    def test_prefix(self):
        old = u"languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n@Upper = [A B];\n"
        new = fc.prefix_text(old, set([("latn", "TRK"), ("latn", "dflt")]))
        lines = new.splitlines()
        self.assertEqual(lines[2], fc.BEGIN % fc.LANGUAGES_BLOCK, "after the prefix's own languagesystems")
        self.assertEqual(lines[3], u"languagesystem latn TRK;", "only what it lacks")
        self.assertEqual(lines[-1], u"@Upper = [A B];")
        self.assertEqual(fc.prefix_text(new, set([("latn", "TRK"), ("latn", "dflt")])), new, "twice: the same")
        self.assertEqual(fc.prefix_text(new, set()), old, "nothing needed: the block out")
        self.assertEqual(fc.prefix_text(u"@x = [A];", set()), u"@x = [A];", "untouched")


class FractionTests(unittest.TestCase):
    def info(self, numerators=True, fraction=True, extra=()):
        names = [d + u".dnom" for d in DIGIT_NAMES] + [u"one.tf"] + list(extra)
        if numerators:
            names += [d + u".numr" for d in DIGIT_NAMES]
        info = make_info(names)
        if not fraction:
            names = [n for n in info.names if n != u"fraction"]
            info = fc.FontInfo(names, dict((n, c) for n, c in info.codes.items() if n != u"fraction"))
        return info

    def test_frac_numr_dnom(self):
        frac, numr, dnom = fc.fraction_features(self.info())
        text = lines_of(frac)
        self.assertIn(u"sub slash by fraction;", text)
        self.assertIn(u"sub [zero one one.tf two", text, "the figures' other forms take the same numerator")
        self.assertIn(u"[fraction zero.dnom", text)
        self.assertIn(u"]' by [zero.dnom", text)
        self.assertIn(u"lookup FreeLab_numr {", lines_of(numr))
        self.assertIn(u"sub [zero one one.tf", lines_of(dnom))
        frac.rules[2].on = False  # one: left out
        self.assertNotIn(u"one.numr", lines_of(frac))
        if HAVE_FONTTOOLS:
            names = self.info().names
            for feature in (frac, numr, dnom):
                self.assertIsNone(parse(fc.forms_feature_text(feature.tag, None, feature.lines()), names))

    def test_superiors_as_numerators_and_no_fraction_bar(self):
        frac, numr, _ = fc.fraction_features(self.info(numerators=False, fraction=False,
                                                       extra=[d + u".sups" for d in DIGIT_NAMES]))
        self.assertIsNone(numr, "numr only from numerators")
        self.assertIn(u"zero.sups", lines_of(frac))
        self.assertNotIn(u"fraction", lines_of(frac))
        self.assertIn(u"sub [slash zero.dnom", lines_of(frac), "the slash divides")


class ScriptedTests(unittest.TestCase):
    def test_superiors_and_inferiors(self):
        info = make_info([u"one.sups", u"one.subs", u"two.inferior"], codes=[(u"twosuperior", 0xB2)])
        sups = fc.scripted_feature(info, "sups", fc.SUPS_SUFFIXES, "<super>", u"")
        self.assertEqual([(r.source, r.target) for r in sups.rules], [(u"one", u"one.sups"), (u"two", u"twosuperior")])
        self.assertNotIn(u"ordfeminine", lines_of(sups), "the ordinal indicators are ordn's")
        sinf = fc.scripted_feature(info, "sinf", fc.SINF_SUFFIXES, "<sub>", u"")
        self.assertEqual([(r.source, r.target) for r in sinf.rules], [(u"two", u"two.inferior"), (u"one", u"one.subs")])

    def test_ordinals(self):
        feature = fc.ordinal_feature(make_info([u"e.ordn", u"r.ordn", u"one.tf"]))
        text = lines_of(feature)
        self.assertIn(u"sub [zero one one.tf two", text)
        self.assertIn(u"[a A o O e r]' by [ordfeminine ordfeminine ordmasculine ordmasculine e.ordn r.ordn];", text)
        self.assertIn(u"nine] period [a A o O e r]'", text, "1.\N{MASCULINE ORDINAL INDICATOR}")
        self.assertIn(u"sub [e.ordn r.ordn] [e r]' by [e.ordn r.ordn];", text, "1ere: one after another")
        own = fc.ordinal_feature(make_info([u"a.ordn"]))
        self.assertIn(u"by [a.ordn a.ordn ordmasculine ordmasculine]", lines_of(own), "a's own .ordn form first")
        if HAVE_FONTTOOLS:
            info = make_info([u"e.ordn", u"r.ordn", u"one.tf"])
            self.assertIsNone(parse(fc.forms_feature_text("ordn", None, feature.lines()), info.names))


class SmallCapTests(unittest.TestCase):
    def pairs(self, info):
        smcp, c2sc = fc.small_cap_features(info)
        return (dict((r.source, r.target) for r in smcp.rules) if smcp else {},
                dict((r.source, r.target) for r in c2sc.rules) if c2sc else {})

    def test_lowercase_named(self):
        smcp, c2sc = self.pairs(make_info([u"a.sc", u"b.sc", u"i.sc", u"ampersand.sc", u"a.ss01", u"a.sc.ss01",
                                           u"i.loclTRK", u"i.sc.loclTRK"]))
        self.assertEqual(smcp[u"a"], u"a.sc")
        self.assertEqual(c2sc[u"A"], u"a.sc", "the capital takes its lowercase letter's")
        self.assertEqual(smcp[u"dotlessi"], u"i.sc", "dotless i: its capital's small capital")
        self.assertEqual(smcp[u"a.ss01"], u"a.sc.ss01", "an alternate's small capital, wherever its suffix stands")
        self.assertEqual(smcp[u"i.loclTRK"], u"i.sc.loclTRK", "Turkish i: the dotted small capital")
        self.assertEqual(c2sc[u"Idotaccent"], u"i.sc.loclTRK")
        self.assertEqual((smcp[u"ampersand"], c2sc[u"ampersand"]), (u"ampersand.sc", u"ampersand.sc"), "caseless: both")
        self.assertNotIn(u"a.sc", smcp, "a small capital is no source")

    def test_capital_named_and_own_forms(self):
        smcp, c2sc = self.pairs(make_info([u"A.sc", u"b.smcp", u"B.c2sc"]))
        self.assertEqual(smcp[u"a"], u"A.sc")
        self.assertEqual(c2sc[u"A"], u"A.sc")
        self.assertEqual((smcp[u"b"], c2sc[u"B"]), (u"b.smcp", u"B.c2sc"))
        self.assertEqual(self.pairs(make_info()), ({}, {}))


class FigureTests(unittest.TestCase):
    def info(self, extra, widths=None, bounds=None):
        return make_info(extra, widths=widths, bounds=bounds)

    def test_style_from_suffixes(self):
        info = self.info([d + u".tf" for d in DIGIT_NAMES] + [d + u".osf" for d in DIGIT_NAMES])
        self.assertEqual(fc.figure_style(info)[:2], ("prop", "lin"))
        info = self.info([d + u".tf" for d in DIGIT_NAMES] + [d + u".lf" for d in DIGIT_NAMES])
        self.assertEqual(fc.figure_style(info)[:2], ("prop", "old"), "Alegreya's: the one the font lacks")

    def test_style_from_measures(self):
        widths = dict((d, 600) for d in DIGIT_NAMES)
        bounds = {u"zero": (0, 0, 500, 480), u"eight": (0, 0, 500, 700)}
        spacing, style, why = fc.figure_style(self.info([], widths, bounds))
        self.assertEqual((spacing, style), ("tab", "old"))
        self.assertIn(u"widths", why)

    def test_features_and_tabular_warning(self):
        tf = [d + u".tf" for d in DIGIT_NAMES]
        widths = dict((d, 500 + 20 * n) for n, d in enumerate(DIGIT_NAMES))
        widths.update(dict((d, 600) for d in tf))
        widths[u"four.tf"] = 640
        info = self.info(tf + [d + u".osf" for d in DIGIT_NAMES] + [d + u".tosf" for d in DIGIT_NAMES], widths)
        found, default = fc.figure_features(info)
        self.assertEqual(default[:2], ("prop", "lin"))
        tnum = dict((r.source, r.target) for r in found["tnum"].rules if not r.warning)
        self.assertEqual((tnum[u"one"], tnum[u"one.osf"]), (u"one.tf", u"one.tosf"))
        onum = dict((r.source, r.target) for r in found["onum"].rules)
        self.assertEqual((onum[u"one"], onum[u"one.tf"]), (u"one.osf", u"one.tosf"))
        warnings = [r for r in found["tnum"].rules if r.warning]
        self.assertEqual([r.source for r in warnings], [u"four.tf"])
        self.assertIn(u"600", warnings[0].note)
        self.assertFalse(warnings[0].on, "a warning is never written")
        self.assertNotIn(u"640", lines_of(found["tnum"]))
        self.assertEqual([r.source for r in found["tnum"].checked()].count(u"four.tf"), 0)

    def test_oldstyle_only_proportional(self):
        widths = dict((d, 600) for d in DIGIT_NAMES)
        widths.update(dict((d + u".onum", 450 + 15 * n) for n, d in enumerate(DIGIT_NAMES)))
        info = self.info([d + u".onum" for d in DIGIT_NAMES], widths)
        found, default = fc.figure_features(info)
        self.assertEqual(default[:2], ("tab", "lin"))
        self.assertEqual(dict((r.source, r.target) for r in found["onum"].rules)[u"one"], u"one.onum",
                         "tabular defaults to the proportional oldstyle ones")
        self.assertIsNone(found["tnum"], "the .onum figures are proportional: no tabular warning")


class SetTests(unittest.TestCase):
    def test_sets_and_names(self):
        info = make_info([u"a.ss01", u"g.ss02", u"A.ss03", u"B.ss03", u"one.ss04", u"two.ss04", u"three.ss04",
                          u"four.ss04", u"a.cv01", u"ampersand.ss05"])
        found = by_tag(fc.set_features(info, {}))
        self.assertEqual(found["ss01"].name, u"Alternate a")
        self.assertEqual(found["ss03"].name, u"Alternate A and B")
        self.assertEqual(found["ss04"].name, u"Alternate figures")
        self.assertEqual(found["ss05"].name, u"Alternate ampersand")
        self.assertTrue(lines_of(found["ss01"]).startswith(u'featureNames { name "Alternate a"; };'))
        self.assertIn(u'FeatUILabelNameID { name "Alternate a"; };', lines_of(found["cv01"]))

    def test_story_from_contours(self):
        double = [(0, -10, 500, 510), (100, 40, 380, 250)]  # its bowl's counter low
        single = [(0, -10, 500, 510), (100, 40, 380, 450)]  # its counter near the top
        info = make_info([u"a.ss01", u"g.ss01"], contours={u"a": double, u"a.ss01": single,
                                                            u"g": [(0, 0, 1, 1)] * 3, u"g.ss01": [(0, 0, 1, 1)] * 2})
        self.assertEqual(fc.story(u"a", double), "double")
        self.assertEqual(fc.story(u"a", single), "single")
        self.assertEqual(fc.set_features(info, {})[0].name, u"Single-story a and g")

    def test_hand_name_and_escapes(self):
        text = u'feature ss01 {\n  featureNames { name "Round a"; };\n  sub a by a.ss01;\n} ss01;\n'
        feature = fc.set_features(make_info([u"a.ss01"]), {"ss01": text})[0]
        self.assertEqual((feature.name, feature.hand_name), (u"Round a", u"Round a"))
        self.assertNotIn(u"featureNames", lines_of(feature), "the font names it already")
        self.assertEqual(fc.fea_string(u'Caf\N{LATIN SMALL LETTER E WITH ACUTE} "a"'), u"Caf\\00E9 \\0022a\\0022")


class FeatureTextTests(unittest.TestCase):
    AUTO = u"feature case {\n# Case\n#> feature\n  sub hyphen by hyphen.case;\n#< feature\n} case;\n"

    def test_kinds(self):
        self.assertEqual(fc.feature_kind(None), "none")
        self.assertEqual(fc.feature_kind(self.AUTO), "fontlab")
        mine = fc.forms_feature_text("case", self.AUTO, [u"sub hyphen by hyphen.case;"])
        self.assertEqual(fc.feature_kind(mine), "freelab")
        self.assertEqual(fc.feature_kind(mine.replace(u"} case;", u"  sub x by x.case;\n} case;")), "hand")
        handed = u"feature case {\n#/> feature\n  sub hyphen by hyphen.case;\n#< feature\n} case;\n"
        self.assertEqual(fc.feature_kind(handed), "hand", "a block handed back is the designer's")

    def test_automatic_code_replaced(self):
        text = fc.forms_feature_text("case", self.AUTO, [u"lookup FreeLab_case {", u"  sub x by x.case;",
                                                         u"} FreeLab_case;"])
        self.assertIn(u"#/> feature", text)
        self.assertNotIn(u"sub hyphen by hyphen.case;", text, "FontLab's code replaced")
        self.assertIn(u"  sub x by x.case;", text)
        again = fc.forms_feature_text("case", text, [u"lookup FreeLab_case {", u"  sub x by x.case;",
                                                     u"} FreeLab_case;"])
        self.assertEqual(again, text, "writing twice changes nothing")
        self.assertNotIn(fc.BEGIN % fc.FORMS, fc.forms_feature_text("case", text, []), "unchecked: the block out")

    def test_names_lead_the_feature(self):
        old = u"feature ss01 {\n# Stylistic Set 1\n  sub b by b.ss01;\n} ss01;\n"
        text = fc.forms_feature_text("ss01", old, [u'featureNames { name "x"; };', u"sub a by a.ss01;"])
        lines = text.splitlines()
        self.assertEqual(lines[1], u"# Stylistic Set 1")
        self.assertEqual(lines[2], fc.BEGIN % fc.FORMS)
        self.assertIn(u"  sub b by b.ss01;", lines, "the feature's own code kept")

    def test_first_checks(self):
        info = make_info([u"hyphen.case", u"a.sc", u"a.ss01"])
        texts = {"case": self.AUTO,  # FontLab's own code does the same: left to it
                 "smcp": u"feature smcp {\n  sub a by a.sc;\n} smcp;\n",  # by hand: left alone
                 "ss01": u"feature ss01 {\n#> feature\n  sub a by a.ss01;\n#< feature\n} ss01;\n",  # no name yet
                 "sups": u"feature sups {\n" + fc.BEGIN % fc.FORMS + u"\n  sub x by y;\n" + fc.END % fc.FORMS +
                         u"\n} sups;\n"}  # FreeLab's, its glyphs gone
        found = by_tag(fc.form_features(info, texts)[0])
        self.assertEqual((found["case"].kind, found["case"].on), ("fontlab", False))
        self.assertEqual((found["smcp"].kind, found["smcp"].on), ("hand", False))
        self.assertIn(u"by hand", found["smcp"].kind_note.replace(u"has its own", u"by hand"))
        self.assertEqual((found["c2sc"].kind, found["c2sc"].on), ("none", True))
        self.assertEqual((found["ss01"].kind, found["ss01"].on), ("fontlab", True), "FreeLab's adds a name")
        self.assertEqual(found["sups"].rules, [])
        new = fc.forms_texts(found.values(), texts)
        self.assertNotIn("case", new)
        self.assertNotIn("smcp", new)
        self.assertNotIn(fc.BEGIN % fc.FORMS, new["sups"], "the old block taken out")
        self.assertIn(u"sub A by a.sc;", new["c2sc"])
        languages = {"case": u"feature case {\n  script latn;\n  language TRK;\n  sub x by x.case;\n} case;\n"}
        case = by_tag(fc.form_features(info, languages)[0])["case"]
        self.assertIn(u"apply to the last one only", case.kind_note)

    def test_whole_font_parses(self):
        extra = [u"hyphen.case", u"a.sc", u"b.sc", u"a.ss01", u"i.loclTRK", u"periodcentered.loclCAT", u"jacute",
                 u"one.sups", u"one.subs", u"e.ordn", u"a.cv01"]
        extra += [d + s for d in DIGIT_NAMES for s in (u".numr", u".dnom", u".tf", u".osf")]
        info = make_info(extra, codes=[(u"Scedilla", 0x15E), (u"Scommaaccent", 0x218)])
        features, _ = fc.form_features(info, {})
        tags = [feature.tag for feature in features]
        self.assertEqual(tags, ["aalt", "locl", "case", "frac", "numr", "dnom", "sups", "subs", "sinf", "ordn", "smcp", "c2sc",
                                "lnum", "onum", "pnum", "tnum", "ss01", "cv01"])
        texts = fc.forms_texts(features, {})
        systems = fc.language_systems(by_tag(features)["locl"])
        self.assertEqual(fc.forms_check(features, texts, systems, info.names), {})
        if HAVE_FONTTOOLS:
            whole = fc.prefix_text(u"", systems) + u"".join(texts[tag] for tag in tags)
            self.assertIsNone(parse(whole, info.names))


# ---------------------------------------------------------------------------
# The dialog, run on fakes: Qt's classes accept any call (the trees keep their rows, data, and
# checks); the font is a small fake of FontLab's. This catches mistakes in the dialog's own code
# paths, not in how Qt or FontLab answer.
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

CHECKED, UNCHECKED, USER_ROLE = 2, 0, 32
FakeQt = _AnyMeta("Qt", (Anything,), {"Checked": CHECKED, "Unchecked": UNCHECKED, "UserRole": USER_ROLE,
                                      "ItemIsEnabled": 32, "ItemIsSelectable": 1, "ItemIsUserCheckable": 16,
                                      "Vertical": 2})


class FakeItem(Anything):
    def __init__(self, texts=()):
        self.texts, self.values, self.checks, self.children, self.tree = list(texts) + [u""] * 3, {}, {}, [], None

    def text(self, column):
        return self.texts[column]

    def setText(self, column, text):
        self.texts[column] = text

    def data(self, column, role):
        return self.values.get((column, role))

    def setData(self, column, role, value):
        self.values[(column, role)] = value

    def checkState(self, column):
        return self.checks.get(column, UNCHECKED)

    def setCheckState(self, column, state):
        changed = self.checks.get(column) != state
        self.checks[column] = state
        tree = self.treeWidget()
        if changed and tree is not None and not tree.blocked:
            for slot in tree.slots.get("itemChanged(QTreeWidgetItem*,int)", []):
                slot(self, column)

    def addChild(self, child):
        child.tree = self.tree
        self.children.append(child)

    def child(self, index):
        return self.children[index]

    def childCount(self):
        return len(self.children)

    def treeWidget(self):
        return self.tree


class FakeTree(Anything):
    def __init__(self, *args):
        self.items, self.blocked, self.slots, self.widgets = [], False, {}, {}

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)

    def addTopLevelItem(self, item):
        item.tree = self
        for child in item.children:
            child.tree = self
        self.items.append(item)

    def topLevelItem(self, row):
        return self.items[row]

    @property
    def topLevelItemCount(self):
        return len(self.items)

    def clear(self):
        self.items, self.widgets = [], {}

    def blockSignals(self, on):
        self.blocked = on

    def setItemWidget(self, item, column, widget):
        self.widgets[(id(item), column)] = widget

    def selectedItems(self):
        return []

    def columnWidth(self, column):
        return 100


class FakeEdit(Anything):
    def __init__(self, text=u""):
        self.text, self.slots = text, {}

    def setText(self, text):
        self.text = text

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)


class _FakeQtModule(object):
    def __init__(self, classes=None):
        self.classes = dict(classes or {})

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self.classes:
            self.classes[name] = _AnyMeta(name, (Anything,), {})
        return self.classes[name]


class FakeRect(object):
    def __init__(self, box):
        self.box = box

    def left(self):
        return self.box[0]

    def top(self):
        return self.box[1]  # (font units up: top() is the lowest)

    def right(self):
        return self.box[2]

    def bottom(self):
        return self.box[3]


class FakeContour(object):
    def __init__(self, box):
        self.box = box

    def path(self):
        return self


class FakeTransform(object):
    def map(self, contour):
        rect = FakeRect(contour.box)
        holder = Anything()
        holder.boundingRect = lambda: rect
        return holder


class FakeShape(object):
    def __init__(self, boxes):
        self.contours = [FakeContour(box) for box in boxes]
        self.transform = FakeTransform()


class FakeLayer(object):
    def __init__(self, advance=500, boxes=((0, 0, 400, 700),)):
        self.advanceWidth, self.shapes, self.isNull = advance, [FakeShape(boxes)], False


def fake_path(layer):
    boxes = [c.box for shape in layer.shapes for c in shape.contours]
    rect = FakeRect((min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                     max(b[3] for b in boxes)))
    path = Anything()
    path.boundingRect = lambda: rect
    path.isEmpty = lambda: False
    return path


class FakeFgGlyph(object):
    def __init__(self, name, code):
        self.name, self.unicode, self.unicodes = name, code, [code] if code else []


class FakeGlyph(object):
    def __init__(self, name, code):
        self.name, self.isNull, self.mark, self.fgGlyph = name, False, 0, FakeFgGlyph(name, code)

    def getLayerByName(self, master):
        code = self.fgGlyph.unicode
        return FakeLayer(500 + 10 * (code - 0x30) if code and 0x30 <= code <= 0x39 else 500)  # proportional figures


class FakeFeatures(object):
    def __init__(self, texts, prefix=u"", can_prefix=True):
        self.texts, self.prefix = dict(texts), prefix
        if can_prefix:
            self.set_prefix = self._set_prefix

    def keys(self):
        return list(self.texts)

    def get_feature(self, tag):
        return self.texts[tag]

    def set_feature(self, tag, text):
        self.texts[tag] = text

    def get_prefix(self):
        return self.prefix

    def _set_prefix(self, text):
        self.prefix = text


class FakePackage(object):
    def __init__(self, features):
        names = [(name, code) for name, code in LETTERS] + [(d, 0x30 + n) for n, d in enumerate(DIGIT_NAMES)]
        names += [(u"f_i", None), (u"hyphen.case", None), (u"a.sc", None), (u"a.ss01", None), (u"i.loclTRK", None),
                  (u"l.2", None)]
        names += [(d + s, None) for d in DIGIT_NAMES for s in (u".numr", u".dnom", u".tf")]
        self.glyphs = [FakeGlyph(name, code) for name, code in names]
        self.by_name = dict((g.name, g) for g in self.glyphs)
        self.fgPackage = Anything()
        self.fgPackage.glyphs = [g.fgGlyph for g in self.glyphs]
        self.fgPackage.features = features
        self.isNull, self.glyphsCount, self.upm, self.tfn, self.path = False, len(self.glyphs), 1000, u"Fake", u"fake.vfc"
        self.master = u"Regular"

    def findName(self, name):
        return self.by_name.get(name)

    def currentHistoryState(self):
        return 1


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        import freelab_auto_kerning as ak
        cls.saved = dict((name, sys.modules.get(name)) for name in ("PythonQt", "fontlab", fc.AUTO_KERNING_MODULE))
        cls.ak_layer_path, cls.ak_stamp = ak.layer_path, getattr(ak, "_freelab_stamp", "unset")
        ak.layer_path = fake_path
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

    def dialog(self, features):
        qt = Anything()
        qt.QtCore = _FakeQtModule({"Qt": FakeQt})
        qt.QtGui = _FakeQtModule({"QTreeWidget": FakeTree, "QTreeWidgetItem": FakeItem, "QLineEdit": FakeEdit})
        package = FakePackage(features)
        workspace = Anything()
        workspace.packages = lambda: [package]
        workspace.currentPackage = package
        fontlab = Anything()
        fontlab.flWorkspace = Anything()
        fontlab.flWorkspace.instance = lambda: workspace
        sys.modules["PythonQt"], sys.modules["fontlab"] = qt, fontlab
        dialog = fc.FeatureCodeDialog()
        self.logged = []
        dialog.log.add = lambda text, level="info": self.logged.append((level, text))
        dialog.run()
        self.assertFalse([t for level, t in self.logged if level == "error"], self.logged)
        return dialog

    def section(self, dialog, tag):
        return [item for item in dialog.forms_tree.items if item.data(0, USER_ROLE) == tag][0]

    def test_forms_listed_and_written(self):
        features = FakeFeatures({"liga": u"feature liga {\n#> feature\n  sub f i by f_i;\n#< feature\n} liga;\n"},
                                u"@x = [a];\n")
        dialog = self.dialog(features)
        tags = [item.data(0, USER_ROLE) for item in dialog.forms_tree.items]
        self.assertEqual(tags, ["aalt", "locl", "case", "frac", "numr", "dnom", "ordn", "smcp", "c2sc", "pnum", "tnum",
                                "ss01"])
        self.assertIn(u"ss01", dialog.name_edits)
        self.assertEqual(dialog.name_edits["ss01"].text, u"Alternate a")
        case = self.section(dialog, "case")
        case.setCheckState(0, UNCHECKED)
        self.assertFalse(dialog.form_feature("case").on)
        smcp = self.section(dialog, "smcp")
        smcp.child(0).setCheckState(0, UNCHECKED)
        self.assertFalse(dialog.form_feature("smcp").rules[0].on)
        dialog.rename(dialog.form_feature("ss01"), u"Single-story a")
        self.assertTrue(dialog.forms_changed())
        dialog.restore()
        self.assertTrue(dialog.form_feature("case").on and dialog.form_feature("smcp").rules[0].on)
        self.assertEqual(case.checkState(0), CHECKED, "the tree shows it again")
        self.assertEqual(dialog.form_feature("ss01").name, u"Alternate a")
        case.setCheckState(0, UNCHECKED)
        dialog.rename(dialog.form_feature("ss01"), u"Single-story a")
        dialog.write()
        self.assertNotIn("case", features.texts, "unchecked: not written")
        self.assertIn(u'featureNames { name "Single-story a"; };', features.texts["ss01"])
        self.assertIn(u"sub i by i.loclTRK;", features.texts["locl"])
        self.assertIn(u"languagesystem latn TRK;", features.prefix)
        self.assertTrue(features.prefix.endswith(u"@x = [a];\n"), "the prefix's own code kept")
        self.assertIn(u"#/> feature", features.texts["liga"], "the ligatures written as before")
        self.assertFalse(dialog.form_feature("case").on, "the choices kept after writing")
        self.assertEqual(dialog.form_feature("ss01").name, u"Single-story a")
        self.assertEqual(dialog.form_feature("tnum").kind, "freelab")

    def test_locl_waits_for_the_prefix(self):
        features = FakeFeatures({}, u"", can_prefix=False)
        dialog = self.dialog(features)
        dialog.write()
        self.assertNotIn("locl", features.texts)
        self.assertIn("smcp", features.texts, "the rest written")
        self.assertTrue([t for level, t in self.logged if level == "warning" and u"locl was not written" in t])

    def test_history_keeps_choices(self):
        dialog = self.dialog(FakeFeatures({}))
        self.section(dialog, "frac").setCheckState(0, UNCHECKED)
        dialog.history_moved()
        self.assertFalse(dialog.form_feature("frac").on)
        self.assertEqual(self.section(dialog, "frac").checkState(0), UNCHECKED)


if __name__ == "__main__":
    unittest.main()
