"""Tests of FreeLab Feature Code's forms (case, locl, fractions and figures, small capitals, stylistic
sets) on synthetic glyph-name sets, and of its dialog run on fakes. Valid Python 2.7 and Python 3;
the feature parser's checks run where fontTools is installed. (features/train/forms_check.py
compiles the code into real fonts and shapes text with HarfBuzz.)"""

from __future__ import absolute_import, division, print_function

import os
import re
import sys
import unicodedata
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_feature_code as fc  # noqa: E402
import freelab_alternates as fa  # noqa: E402 (the third tab, built with the dialog in a test)

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


def refused_or(write, old, rules):
    """What a writer makes of old, or None where it refuses (FeatureCodeUnreadable, or None given)."""
    try:
        return write(old, rules)
    except fc.FeatureCodeUnreadable:
        return None


def writer_scenarios(test, write, tag, begin, end, rule):
    """Codex review 6's scenarios for a feature writer: write(old code, rules) gives the new code (None, or
    FeatureCodeUnreadable, for a refusal); tag, the feature it writes; begin and end, its block's markers;
    rule, a line its block holds once written. Shared by Feature Code's, CJK Spacing's, and CJK Vertical's
    tests: they all write through Feature Code's token functions."""
    a, b, c = u"sub a by a.alt;", u"sub b by b.alt;", u"sub c by c.alt;"
    # 1. An end marker after code on its line: the block ends there, the font's rule after it stays
    own = u"%s\n%s\n%s %s\n%s" % (a, begin, b, end, c)
    for rules in ([], [rule]):
        text = write(own, rules)
        test.assertEqual((text.count(a), text.count(c), text.count(b)), (1, 1, 0), "%r: %r" % (rules, text))
        test.assertEqual(text.count(begin), 1 if rules else 0, text)
    own = u"feature %s {\n%s\n%s\n%s %s\n%s\n} %s;\nfeature zzzz { sub z by z.alt; } zzzz;" % (tag, a, begin, b, end, c,
                                                                                             tag)
    text = write(own, [])  # (taken out: the rest of the feature, its brace, and the next feature kept)
    test.assertEqual((text.count(a), text.count(c), text.count(b)), (1, 1, 0), text)
    test.assertIn(u"} %s;" % tag, text)
    test.assertIn(u"feature zzzz { sub z by z.alt; } zzzz;", text)
    # 2. An opening marker after code on its line: the old block goes, one block is left
    own = u"feature %s { %s %s\nlookup FreeLab_old { %s } FreeLab_old;\n%s\n} %s;" % (tag, a, begin, b, end, tag)
    text = write(own, [rule])
    test.assertEqual(text.count(begin), 1, text)
    test.assertNotIn(u"FreeLab_old", text)
    test.assertEqual(text.count(a), 1)
    # 3. Written again: the same
    test.assertEqual(write(text, [rule]), text)
    # 4. Another feature's code only: this one made after it, whole, never statements at the top level
    other = u"feature kern { pos f i -10; } kern;"
    text = write(other, [rule])
    test.assertTrue(text.startswith(other), text)
    bounds = fc.feature_bounds(text, tag)
    test.assertIsInstance(bounds, tuple, text)
    test.assertTrue(bounds[0] < text.index(rule) < bounds[1], text)
    # 5. A body with no feature around it: taken where its braces balance, refused where they do not
    text = write(u"lookup Own { %s } Own;" % a, [rule])
    test.assertEqual((text.count(a), text.count(rule)), (1, 1), text)
    test.assertIsNone(refused_or(write, u"lookup Own { %s" % a, [rule]))
    # 6. Markers not in pairs: refused, to write and to take out alike
    for broken in (u"feature %s {\n%s\n%s\n} %s;" % (tag, a, begin, tag), u"feature %s {\n%s %s\n} %s;" % (tag, a, end, tag),
                   u"feature %s {\n%s\n%s\n%s\n%s\n} %s;" % (tag, begin, a, begin, end, tag)):
        for rules in ([], [rule]):
            test.assertIsNone(refused_or(write, broken, rules), broken)


class StrokeTests(unittest.TestCase):
    def test_a_square_grows_evenly(self):
        square = [(0, 0, True), (100, 0, True), (100, 100, True), (0, 100, True)]  # counterclockwise, y up
        moved = fc.offset_contour(square, 10)
        self.assertEqual([tuple(round(v, 6) for v in p) for p in moved], [(-10, -10), (110, -10), (110, 110), (-10, 110)],
                         "a corner moves 10 out both ways (the miter)")
        self.assertEqual([tuple(round(v, 6) for v in p) for p in fc.offset_contour(square, 10, right=False)],
                         [(10, 10), (90, 10), (90, 90), (10, 90)], "the other way round: inward")

    def test_handles_move_with_their_point(self):
        curve = [(0, 0, True), (50, 0, False), (100, 50, False), (100, 100, True), (0, 100, True)]
        moved = fc.offset_contour(curve, 5)
        self.assertEqual(moved[1][0] - curve[1][0], moved[0][0] - curve[0][0], "the handle leaving (0, 0) moves as it")
        self.assertEqual(moved[2][1] - curve[2][1], moved[3][1] - curve[3][1], "the handle reaching (100, 100) moves as it")

    def test_the_stem_across_the_middle(self):
        inside = lambda x, y: 20 <= x <= 40 or 80 <= x <= 100  # two strokes of 20 (a zero's sides)
        self.assertAlmostEqual(fc.stem_width(inside, (0, 0, 120, 200)), 20, delta=1)


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

    def test_a_language_the_fonts_code_sets_is_never_set_again(self):
        # Owner's report 153 (Bellefair): the font's own locl sets CAT, MOL, and ROM; checked, FreeLab's block
        # beside it set "language CAT;" again, and FontLab's compiler stopped ("language-specific behavior
        # already specified"), at every write after
        own = (u"feature locl {\n  script latn;\n  language CAT;\n  lookup locl_cat {\n    sub l periodcentered' l by ldot;\n"
               u"  } locl_cat;\n  language MOL;\n  lookup locl_mol {\n    sub Scedilla by Scommaaccent;\n  } locl_mol;\n"
               u"  language ROM exclude_dflt;\n  lookup locl_mol;\n} locl;\n")
        self.assertEqual(fc.own_languages(own), set([("latn", "CAT"), ("latn", "MOL"), ("latn", "ROM")]))
        info = make_info([u"i.loclTRK"], codes=[(u"Scedilla", 0x15E), (u"Scommaaccent", 0x218), (u"ldot", 0x140),
                                                (u"Ldot", 0x13F)])
        features, _ = fc.form_features(info, {u"locl": own})
        locl = by_tag(features)[u"locl"]
        self.assertEqual(locl.kind, "hand")
        left = [rule for rule in locl.rules if rule.data["language"] in ("CAT", "MOL", "ROM")]
        self.assertTrue(left and all(rule.warning and not rule.on for rule in left), "shown, never written")
        locl.on = True  # (checked, as the owner did)
        for rule in locl.rules:
            rule.on = True  # (even so)
        code = lines_of(locl)
        for language in (u"CAT", u"MOL", u"ROM"):
            self.assertNotIn(u"language %s;" % language, code, "the font's code sets it already")
        self.assertIn(u"language TRK;", code, "a language the font's code lacks is still FreeLab's")
        self.assertIn(u"sets CAT, MOL, and ROM already", locl.kind_note)
        text = fc.forms_texts(features, {u"locl": own})[u"locl"]
        seen, script = set(), None
        for line in text.splitlines():
            words = line.split(u"#")[0].replace(u";", u" ").split()
            if words[:1] == [u"script"]:
                script = words[1]
            elif words[:1] == [u"language"]:
                self.assertNotIn((script, words[1]), seen, "a language set twice in one feature")
                seen.add((script, words[1]))
        # FreeLab's earlier block (with CAT set again) is not taken for the font's own code
        again = fc.forms_feature_text(u"locl", own, [u"script latn;", u"language CAT;", u"lookup x {", u"} x;"])
        self.assertEqual(fc.own_languages(again), fc.own_languages(own))
        automatic = u"feature locl {\n#> feature\nscript latn;\nlanguage CAT;\n#< feature\n} locl;\n"
        self.assertEqual(fc.own_languages(automatic), set(), "FontLab's automatic code, which FreeLab's replaces")

    def test_languages_are_read_by_statements_not_lines(self):
        # Codex review 4: read line by line, a language on the script's line, a tag on the line after its
        # keyword, and a second language on one line were missed, and FreeLab set them again
        info = make_info([u"i.loclTRK"], codes=[(u"Scedilla", 0x15E), (u"Scommaaccent", 0x218), (u"ldot", 0x140),
                                                (u"Ldot", 0x13F)])
        cases = (
            (u"feature locl {\n  script latn; language CAT; sub l' periodcentered' l by ldot;\n} locl;\n",
             [("latn", "CAT")]),
            (u"feature locl {\n  script latn;\n  language\n    ROM;\n  sub Scedilla by Scommaaccent;\n} locl;\n",
             [("latn", "ROM")]),
            (u"feature locl {\n  script latn;\n  language MOL; sub Scedilla by Scommaaccent; language CAT; "
             u"sub l' periodcentered' l by ldot;\n} locl;\n", [("latn", "MOL"), ("latn", "CAT")]),
        )
        for own, pairs in cases:
            self.assertEqual(fc.own_languages(own), set(pairs), own)
            features, _ = fc.form_features(info, {u"locl": own})
            locl = by_tag(features)[u"locl"]
            locl.on = True
            for rule in locl.rules:
                rule.on = True
            text = fc.forms_texts(features, {u"locl": own})[u"locl"]
            block = text[text.index(fc.BEGIN % fc.FORMS):]
            for _, language in pairs:
                self.assertNotIn(u"language %s;" % language, block, "set by the font's code already: %r" % own)
            self.assertIn(u"language TRK;", block, "a language the font's code lacks is still FreeLab's")
            self.assertTrue(text.startswith(own[:own.index(u"} locl;")]), "the user's text intact: %r" % text)
        commented = u"feature locl {\n  # language CAT;\n  sub a by b; # script cyrl;\n  name \"language NLD;\";\n} locl;\n"
        self.assertEqual(fc.own_languages(commented), set(), "comments and strings set nothing")
        self.assertEqual(fc.own_languages(u"feature locl {\n  sub language by script;\n} locl;\n"), set(),
                         "a glyph named language is no statement")

    def test_a_compact_feature_keeps_its_code(self):
        # Codex review 5: the writer looked for the closing brace at the start of a line; a feature on one line,
        # a brace after the last rule, or delimiters on lines of their own had none, and the font's own code was
        # made again from nothing (its CAT rules lost)
        info = make_info([u"i.loclTRK"], codes=[(u"ldot", 0x140), (u"Ldot", 0x13F)])
        cases = (u"feature locl { script latn; language CAT; sub l by ldot; } locl;\n",
                 u"feature locl {\nscript latn; language CAT;\nsub l by ldot; } locl;\n",
                 u"feature\nlocl {\nscript latn; language CAT;\nsub l by ldot;\n} locl;\n")
        for own in cases:
            self.assertEqual(fc.own_languages(own), set([("latn", "CAT")]), own)
            features, _ = fc.form_features(info, {u"locl": own})
            locl = by_tag(features)[u"locl"]
            locl.on = True
            for rule in locl.rules:
                rule.on = True
            refused = []
            text = fc.forms_texts(features, {u"locl": own}, refused)[u"locl"]
            self.assertEqual(refused, [])
            start, end = text.index(fc.BEGIN % fc.FORMS), text.index(fc.END % fc.FORMS)
            block, rest = text[start:end], text[:start] + text[end + len(fc.END % fc.FORMS):]
            self.assertEqual([t for t, _, _ in fc.code_tokens(rest)], [t for t, _, _ in fc.code_tokens(own)],
                             "the user's code, statement for statement: %r" % text)
            self.assertIn(u"sub l by ldot;", text, "the designer's rule as typed")
            self.assertNotIn(u"language CAT;", block)
            self.assertIn(u"language CAT;", rest)
            self.assertIn(u"language TRK;", block)
            self.assertEqual(fc.feature_bounds(text, u"locl")[1], text.rindex(u"}"), "one feature, closed once")
        # Braces that cannot be found: nothing written there, never the feature made again
        broken = u"feature locl { script latn; language CAT; sub l by ldot;\n"
        features, _ = fc.form_features(info, {u"locl": broken})
        by_tag(features)[u"locl"].on = True
        refused = []
        self.assertNotIn(u"locl", fc.forms_texts(features, {u"locl": broken}, refused))
        self.assertEqual(refused, [u"locl"])
        self.assertIn(u"FreeLab leaves locl as it is", fc.refused_words(refused))
        # The ligatures and calt alike
        liga = u"feature liga { sub f f by f_f; } liga;"
        written = fc.feature_text(u"liga", liga, [((u"f", u"i"), u"fi")], u"ligatures", [])
        self.assertIn(u"sub f f by f_f;", written)
        self.assertIn(u"sub f i by fi;", written)
        self.assertEqual(written.count(u"} liga;"), 1)
        with self.assertRaises(fc.FeatureCodeUnreadable):
            fc.feature_text(u"liga", u"feature liga { sub f f by f_f;", [((u"f", u"i"), u"fi")], u"ligatures", [])
        calt = fc.calt_text(u"feature calt { # } calt; in a comment\n  sub a' b by a.alt; } calt;", [u"sub x by y;"])
        self.assertTrue(calt.index(u"sub x by y;") > calt.index(u"sub a' b by a.alt;"), calt)
        self.assertIn(u"# } calt; in a comment", calt)

    def test_the_writers_read_markers_and_braces_by_tokens(self):
        """Codex review 6, findings 1 and 2: markers found as comments wherever they stand, never past their
        pair; another feature's code is no body; a body's braces must balance."""
        writer_scenarios(self, lambda old, rules: fc.forms_feature_text(u"case", old, rules), u"case",
                         fc.BEGIN % fc.FORMS, fc.END % fc.FORMS, u"sub x by x.case;")
        writer_scenarios(self, lambda old, rules: fc.calt_text(old, rules), u"calt",
                         fc.BEGIN % u"alternates", fc.END % u"alternates", u"sub x' x by x.alt;")
        writer_scenarios(self, lambda old, rules: fc.feature_text(u"liga", old, [((u"x", u"y"), u"x_y")] if rules else [],
                                                                  u"ligatures", []),
                         u"liga", fc.BEGIN % u"ligatures", fc.END % u"ligatures", u"sub x y by x_y;")
        # The readers alike: an inline end marker ends the block there
        own = u"feature case {\nsub a by a.case;\n%s\nsub b by b.case; %s\nsub c by c.case;\n} case;" % (
            fc.BEGIN % fc.FORMS, fc.END % fc.FORMS)
        self.assertEqual(fc.feature_kind(own), "hand", "the font's own rules around FreeLab's block")
        self.assertIn(u"sub c by c.case;", fc.strip_block(own, fc.FORMS))
        self.assertEqual(fc.freelab_block(u"case", own, fc.FORMS), u"feature case {\nsub b by b.case; \n} case;\n")
        self.assertEqual(fc.own_languages(u"feature locl {\n%s\nscript latn; language TRK; %s\nlanguage CAT;\n} locl;" % (
            fc.BEGIN % fc.FORMS, fc.END % fc.FORMS)), set([("DFLT", "CAT")]), "CAT after FreeLab's block is the font's")

    def test_the_fonts_own_ligature_rules_are_never_moved(self):
        """Codex reviews 6 and 7: moving the font's own rules kept going wrong (a compact rule written a second
        time; a rule moved after a lookupflag took it, was read as fixed, and the next write lost it; another
        feature's rule taken for the text's tag). FreeLab never moves or takes out a rule the font wrote: it
        manages its own block, and FontLab's automatic code; a choice that would move the font's rule is said."""
        def apply(texts, found=None, stuck=None):
            found = fc.ligatures(names, texts) if found is None else found
            out = dict(texts)
            out.update(fc.ligature_texts(found, texts, [], stuck))
            return out

        names = [u"f", u"i", u"l", u"a", u"b", u"f_i", u"f_l", u"a_b"]
        # The font's compact rule: read, left where it is whatever the choice, never written again
        texts = {u"liga": u"feature liga { sub f i by f_i; } liga;"}
        for choice in ("liga", "dlig", "off"):
            found = fc.ligatures(names, texts)
            f_i = [lig for lig in found if lig.glyph == u"f_i"][0]
            self.assertEqual((f_i.now, f_i.fixed), (u"liga", True))
            f_i.choice = choice
            stuck = []
            out = apply(texts, found, stuck)
            self.assertEqual(out[u"liga"].count(u"sub f i by f_i;"), 1, (choice, out))
            self.assertIn(u"feature liga { sub f i by f_i; ", out[u"liga"], "as typed")
            self.assertEqual(out.get(u"dlig", u"").count(u"sub f i by f_i;"), 0)
            self.assertEqual(stuck, [] if choice == "liga" else [u"f_i"])
        self.assertIn(u"FreeLab does not move f_i", fc.stuck_words([u"f_i"]))
        # FontLab's automatic code is FreeLab's to take over: moved once
        texts = {u"liga": u"feature liga {\n#> feature\n  sub f i by f_i;\n#< feature\n} liga;"}
        for choice in ("liga", "dlig", "off"):
            found = fc.ligatures(names, texts)
            f_i = [lig for lig in found if lig.glyph == u"f_i"][0]
            self.assertFalse(f_i.fixed)
            f_i.choice = choice
            out = apply(texts, found)
            for tag in (u"liga", u"dlig"):
                self.assertEqual(out.get(tag, u"").count(u"sub f i by f_i;"), 1 if choice == tag else 0, (choice, out))
        # A rule before a lookupflag (or a script and language): FreeLab's block goes before it, and two writes
        # in a row keep everything
        for scope in (u"lookupflag IgnoreMarks;", u"script latn; language TRK;"):
            texts = {u"liga": u"feature liga { sub f i by f_i; %s sub a b by a_b; } liga;" % scope}
            found = fc.ligatures(names, texts)
            [lig for lig in found if lig.glyph == u"f_l"][0].choice = "liga"  # (FreeLab's own, in liga)
            first = apply(texts, found)
            second = apply(first)
            self.assertEqual(second, first, "written again: the same")
            text = first[u"liga"]
            self.assertEqual((text.count(u"sub f i by f_i;"), text.count(u"sub a b by a_b;")), (1, 1), text)
            self.assertLess(text.index(u"sub f i by f_i;"), text.index(scope))
            self.assertLess(text.index(u"sub f l by f_l;"), text.index(scope), "FreeLab's ligature in the default scope")
        # FreeLab's block left after a lookupflag by an older FreeLab: its rule written again, before it
        texts = {u"liga": u"feature liga { lookupflag IgnoreMarks;\n%s\nsub f l by f_l;\n%s\n} liga;" % (
            fc.BEGIN % u"ligatures", fc.END % u"ligatures")}
        out = apply(texts)
        self.assertEqual(out[u"liga"].count(u"sub f l by f_l;"), 1, out)
        self.assertLess(out[u"liga"].index(u"sub f l by f_l;"), out[u"liga"].index(u"lookupflag"))
        self.assertEqual(apply(out), out)
        # Another feature's code given under liga: its rule stays that feature's, byte for byte
        other = u"feature dlig { sub f i by f_i; } dlig;"
        for source in (other, u"feature liga { sub a b by a_b; } liga;\n" + other):
            for choice in ("liga", "dlig", "off"):
                texts = {u"liga": source}
                found = fc.ligatures(names, texts)
                f_i = [lig for lig in found if lig.glyph == u"f_i"][0]
                self.assertEqual(f_i.now, u"dlig", "never relabeled from the text's tag")
                f_i.choice = choice
                out = apply(texts, found)
                self.assertIn(other, out[u"liga"], (source, choice, out))
                self.assertEqual(out[u"liga"].count(u"sub f i by f_i;") + out.get(u"dlig", u"").count(u"sub f i by f_i;"), 1)
        # A feature given twice under one tag: each rule once, written again the same
        texts = {u"liga": u"feature liga { sub f i by f_i; } liga;\nfeature liga { sub f l by f_l; } liga;"}
        out = apply(texts)
        self.assertEqual((out[u"liga"].count(u"sub f i by f_i;"), out[u"liga"].count(u"sub f l by f_l;")), (1, 1), out)
        self.assertEqual(apply(out), out)

    def test_a_ligature_the_fonts_code_makes_any_way_is_the_fonts(self):
        """Codex review 8, finding 1: a rule FreeLab does not read as a plain ligature (a class in its input, a
        named class, escaped names) still makes f_i: f_i was offered as new, and FreeLab wrote "sub f i by
        f_i;" in liga again, or in dlig. That ligature is the font's: shown where it is, never written again."""
        names = [u"f", u"i", u"i.alt", u"f_i"]
        for own in (u"feature liga { sub f [i i.alt] by f_i; } liga;",
                    u"@I = [i i.alt];\nfeature liga { sub f @I by f_i; } liga;",
                    u"feature liga { sub \\f \\i by \\f_i; } liga;",
                    u"feature liga { sub f' i' by f_i; } liga;"):
            for choice in ("liga", "dlig"):
                texts = {u"liga": own}
                out = dict(texts)
                for _ in range(2):  # (two writes)
                    found = fc.ligatures(names, out)
                    f_i = [lig for lig in found if lig.glyph == u"f_i"]
                    self.assertEqual([(lig.now, lig.fixed) for lig in f_i], [(u"liga", True)], own)
                    f_i[0].choice = choice
                    stuck = []
                    out.update(fc.ligature_texts(found, out, [], stuck))
                    self.assertEqual(stuck, [] if choice == "liga" else [u"f_i"])
                self.assertEqual(out[u"liga"], own, "the font's rule as it was, nothing added: %r" % out)
                self.assertNotIn(u"f_i", out.get(u"dlig", u""))
        self.assertEqual(fc.font_outputs(u"feature dlig { sub [f f.alt] i by f_i; } dlig;", u"liga"), {u"f_i": u"dlig"},
                         "in the feature it stands in")

    def test_a_lookup_in_the_feature_ends_the_default_scope(self):
        """Codex review 8, finding 2: "lookup Own;" (or a lookup block) may carry its lookupflag on; FreeLab's
        ligatures went after it. They go before it now."""
        names = [u"f", u"l", u"f_l"]
        for own in (u"feature liga { lookup Own; } liga;",
                    u"feature liga { lookup Own { lookupflag IgnoreMarks; sub a b by a_b; } Own; } liga;"):
            texts = {u"liga": own}
            found = fc.ligatures(names, texts)
            [lig for lig in found if lig.glyph == u"f_l"][0].choice = "liga"
            out = dict(texts)
            out.update(fc.ligature_texts(found, texts, [], []))
            text = out[u"liga"]
            self.assertLess(text.index(u"sub f l by f_l;"), text.index(u"lookup Own"), text)
            again = dict(out)
            again.update(fc.ligature_texts(fc.ligatures(names, out), out, [], []))
            self.assertEqual(again, out, "written again: the same")
        self.assertEqual(fc.scope_change(u"feature liga { sub f i by f_i; lookup Own; } liga;", u"liga"),
                         len(u"feature liga { sub f i by f_i; "))

    def test_taking_a_block_out_checks_the_braces_too(self):
        """Codex review 7, finding 4: a write that only took FreeLab's block out returned an unclosed "lookup Own {"."""
        for tag, begin, end, write in (
                (u"case", fc.BEGIN % fc.FORMS, fc.END % fc.FORMS, lambda old, rules: fc.forms_feature_text(u"case", old, rules)),
                (u"calt", fc.BEGIN % u"alternates", fc.END % u"alternates", lambda old, rules: fc.calt_text(old, rules)),
                (u"liga", fc.BEGIN % u"ligatures", fc.END % u"ligatures",
                 lambda old, rules: fc.feature_text(u"liga", old, [((u"x", u"y"), u"x_y")] if rules else [], u"ligatures"))):
            for old in (u"lookup Own {\n%s\nsub a by a.alt;\n%s" % (begin, end),
                        u"feature %s {\n%s\nsub a by a.alt;\n%s\n" % (tag, begin, end)):
                for rules in ([], [u"sub x by y;"]):
                    self.assertIsNone(refused_or(write, old, rules), (tag, old, rules))

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


def figure_measures(extra=None, figure_box=(20, -10, 480, 710), width=500):
    """(widths, bounds) of lining figures (all one box), a and o, plus extra {name: (width, box)}."""
    widths, bounds = {}, {}
    for name in DIGIT_NAMES:
        widths[name], bounds[name] = width, figure_box
    widths[u"a"], bounds[u"a"] = 480, (30, -10, 450, 510)
    widths[u"o"], bounds[u"o"] = 520, (30, -10, 490, 510)
    for name, (advance, box) in (extra or {}).items():
        widths[name], bounds[name] = advance, box
    return widths, bounds


def groups_of(forms):
    found = {}
    for form in forms:
        found.setdefault(form.group, []).append(form)
    return found


class SmallFormTests(unittest.TestCase):
    """The figure forms Feature Code builds: what the font lacks, their names, settings, and placements."""

    def test_missing_forms_and_default_names(self):
        info = make_info([], base=True)
        groups = groups_of(fc.missing_small_forms(info))
        self.assertEqual(sorted(groups), ["dnom", "numr", "subs", "subscript", "superscript", "sups"],
                         "the ordinal indicators are in the base font")
        self.assertEqual([f.name for f in groups["numr"]], [d + u".numr" for d in DIGIT_NAMES])
        self.assertEqual([f.name for f in groups["subs"]][:2], [u"zero.subs", u"one.subs"])
        self.assertEqual([f.name for f in groups["superscript"]][:4], [u"uni2070", u"uni00B9", u"uni00B2", u"uni00B3"])
        self.assertEqual(groups["superscript"][2].code, 0xB2)
        self.assertEqual(groups["superscript"][2].figure, u"two")
        self.assertEqual(groups["subscript"][0].name, u"uni2080")
        self.assertTrue(all(f.code is None for f in groups["numr"]))

    def test_names_follow_the_font(self):
        info = make_info([u"one.numerator", u"one.inferior"],
                         codes=[(u"twosuperior", 0xB2), (u"onesuperior", 0xB9)])
        groups = groups_of(fc.missing_small_forms(info))
        self.assertEqual(groups["numr"][0].name, u"zero.numerator")
        self.assertNotIn(u"one.numerator", [f.name for f in groups["numr"]])
        self.assertEqual(groups["subs"][0].name, u"zero.inferior")
        self.assertEqual([f.name for f in groups["superscript"]][:2], [u"zerosuperior", u"threesuperior"])
        self.assertEqual(groups["subscript"][0].name, u"zeroinferior")
        self.assertNotIn(u"one.sups", [f.name for f in groups["sups"]], "1 has its Unicode superior: sups takes it")
        self.assertNotIn(u"two.sups", [f.name for f in groups["sups"]])
        self.assertIn(u"three.sups", [f.name for f in groups["sups"]])

    def test_taken_name_and_ordinals(self):
        info = make_info([u"uni2074"], base=False,
                         codes=[(u"a", 0x61), (u"o", 0x6F)] + [(name, 0x30 + n) for n, name in enumerate(DIGIT_NAMES)])
        groups = groups_of(fc.missing_small_forms(info))
        self.assertNotIn(u"uni2074", [f.name for f in groups["superscript"]], "a glyph by that name: not built beside it")
        self.assertEqual([(f.name, f.base, f.code) for f in groups["ordn"]],
                         [(u"ordfeminine", u"a", 0xAA), (u"ordmasculine", u"o", 0xBA)])

    def test_corpus_settings(self):
        widths, bounds = figure_measures()
        info = make_info([], widths=widths, bounds=bounds)
        settings = fc.small_settings(info, 700.0)
        self.assertEqual(settings["numr"]["scale"], 0.57)
        self.assertEqual(settings["numr"]["baseline"], int(round(710 * (1 - 0.57))), "its top at the figures' top")
        self.assertEqual(settings["dnom"]["baseline"], 0)
        self.assertEqual(settings["sups"]["baseline"], int(round(0.51 * 700)))
        self.assertEqual(settings["subs"]["baseline"], int(round(-0.17 * 700)))
        self.assertEqual(settings["ordn"]["baseline"], int(round(1.01 * 700 - 0.66 * 510)))
        self.assertEqual(settings["sups"]["width"], 1.12)
        self.assertEqual(settings["sups"]["why"], u"As most open-licensed fonts.")

    def test_settings_from_the_font(self):
        # 1, 2, 3 drawn at 0.6 of the figures, their baseline at 400: the superiors' settings; the
        # numerators take their size
        drawn = dict((name, (330, (12, 400 + 0.6 * -10, 288, 400 + 0.6 * 710))) for name in
                     (u"onesuperior", u"twosuperior", u"threesuperior"))
        widths, bounds = figure_measures(drawn)
        info = make_info([], codes=[(u"onesuperior", 0xB9), (u"twosuperior", 0xB2), (u"threesuperior", 0xB3)],
                         widths=widths, bounds=bounds)
        settings = fc.small_settings(info, 700.0)
        self.assertAlmostEqual(settings["sups"]["scale"], 0.6)
        self.assertEqual(settings["sups"]["baseline"], 400)
        self.assertEqual(settings["sups"]["width"], 1.1)
        self.assertEqual(settings["sups"]["why"], u"As the font's 3 drawn forms.")
        self.assertAlmostEqual(settings["numr"]["scale"], 0.6)
        self.assertEqual(settings["numr"]["baseline"], int(round(710 * 0.4)))
        self.assertIn(u"other small figures", settings["numr"]["why"])

    def test_scaled_placement(self):
        widths, bounds = figure_measures()
        info = make_info([], widths=widths, bounds=bounds)
        forms = fc.missing_small_forms(info)
        settings = fc.small_settings(info, 700.0)
        plans = fc.plan_small_forms(info, forms, settings)
        plan = plans[u"two.numr"]
        width = int(round(500 * 0.57 * 1.12))
        self.assertEqual(plan.how, "scaled")
        self.assertEqual(plan.width, width)
        self.assertEqual(plan.parts, [(u"two", 0.57, 0.57, int(round((width - 500 * 0.57) / 2.0)),
                                       settings["numr"]["baseline"])])
        self.assertEqual(plans[u"two.dnom"].parts[0][4], 0)
        self.assertEqual(plans[u"uni00B2"].how, "copied", "the Unicode superior is a copy of two.sups, built too")
        self.assertEqual(plans[u"uni00B2"].parts, [(u"two.sups", 1.0, 1.0, 0, 0)])
        self.assertEqual(plans[u"uni00B2"].width, plans[u"two.sups"].width)
        self.assertEqual(fc.flat_parts(plans, u"uni00B2"), plans[u"two.sups"].parts)
        self.assertIn(u"two at 57%, raised", fc.describe_placement(plan))
        [form for form in forms if form.name == u"two.sups"][0].on = False
        plans = fc.plan_small_forms(info, forms, settings)
        self.assertEqual(plans[u"uni00B2"].how, "scaled", "two.sups not built: the figure scaled")
        self.assertEqual(plans[u"uni00B2"].parts, plans[u"two.sups"].parts)

    def test_unknown_width(self):
        info = make_info([])
        plans = fc.plan_small_forms(info, fc.missing_small_forms(info), fc.small_settings(info, 700.0))
        self.assertIsNone(plans[u"two.numr"])
        self.assertIn(u"not built", fc.describe_placement(None))

    def test_moved_from_a_drawn_set(self):
        drawn = dict((name + u".dnom", (300, (10, -6, 270, 404))) for name in DIGIT_NAMES)
        widths, bounds = figure_measures(drawn)
        info = make_info([name + u".dnom" for name in DIGIT_NAMES], widths=widths, bounds=bounds)
        forms = fc.missing_small_forms(info)
        self.assertNotIn("dnom", groups_of(forms))
        settings = fc.small_settings(info, 700.0)
        plans = fc.plan_small_forms(info, forms, settings)
        plan = plans[u"two.numr"]
        self.assertEqual(plan.how, "moved")
        self.assertEqual(plan.width, 300)
        dnom_baseline = -6 - (410 / 720.0) * -10
        self.assertEqual(plan.parts, [(u"two.dnom", 1.0, 1.0, 0, int(round(settings["numr"]["baseline"] - dnom_baseline)))])
        self.assertIn(u"two.dnom (drawn), raised", fc.describe_placement(plan))

    def test_oldstyle_defaults_scale_lining_forms(self):
        widths, bounds = figure_measures({u"zero": (500, (20, -10, 480, 460))})
        extra = [name + u".lf" for name in DIGIT_NAMES]
        for name in extra:
            widths[name], bounds[name] = 520, (20, -10, 500, 710)
        info = make_info(extra, widths=widths, bounds=bounds)
        form = [f for f in fc.missing_small_forms(info) if f.name == u"two.numr"][0]
        self.assertEqual((form.base, form.figure), (u"two.lf", u"two"))

    def test_rescaled_baseline_keeps_the_top(self):
        setting = {"scale": 0.57, "baseline": 305, "width": 1.12, "top_of": 710}
        self.assertEqual(fc.rescaled_baseline(setting, 0.5), int(round(305 + 0.07 * 710)))
        self.assertEqual(fc.rescaled_baseline(dict(setting, top_of=None), 0.5), 305)

    def test_build_label(self):
        self.assertEqual(fc.build_label(0), u"Build ticked figure forms")
        self.assertEqual(fc.build_label(1), u"Build 1 ticked figure form")
        self.assertEqual(fc.build_label(12), u"Build 12 ticked figure forms")

    def test_built_forms_reach_the_features(self):
        """Once built (the font read again), the forms features take them."""
        info = make_info([])
        names = [form.name for form in fc.missing_small_forms(info)]
        codes = [(form.name, form.code) for form in fc.missing_small_forms(info) if form.code]
        built = make_info([name for name in names if not dict(codes).get(name)], codes=codes)
        features = by_tag(fc.form_features(built, {})[0])
        for tag in ("frac", "numr", "dnom", "sups", "subs", "sinf"):
            self.assertIn(tag, features)
        self.assertIn(u"sub zero by zero.sups;", lines_of(features["sups"]))
        self.assertEqual(fc.missing_small_forms(built), [], "nothing left to build")


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


class FakeSize(object):
    def __init__(self, width=0, height=0):
        self.width, self.height = width, height


class FakeItem(Anything):
    def __init__(self, texts=()):
        self.texts, self.values, self.checks, self.children, self.tree = list(texts) + [u""] * 3, {}, {}, [], None
        self.hints, self.tips = {}, {}  # its cells' size hints and tooltips, by column
        self.spanned, self.up, self.expanded, self.hidden = False, None, False, False

    def setFirstColumnSpanned(self, on):
        self.spanned = on

    def parent(self):
        return self.up

    def isExpanded(self):
        return self.expanded

    def setExpanded(self, on):
        self.expanded = on

    def isHidden(self):
        return self.hidden

    def setSizeHint(self, column, size):
        self.hints[column] = size

    def setToolTip(self, column, text):
        self.tips[column] = text

    def toolTip(self, column):
        return self.tips.get(column, u"")

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
        child.tree, child.up = self.tree, self
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


class FakeButton(Anything):
    def __init__(self, text=u""):
        self.text, self.enabled, self.slots = text, True, {}

    def setText(self, text):
        self.text = text

    def setEnabled(self, on):
        self.enabled = on

    def setWhatsThis(self, text):
        self.whats = text

    def setToolTip(self, text):
        self.tip = text

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)


class ContainedButton(FakeButton):
    """A button as Qt reports one inside a container: disabled while its container is (container_disabled,
    the window's lists while it is busy), whatever its own state (own), which setEnabled sets."""
    container_disabled = False

    def __init__(self, text=u""):
        self.text, self.own, self.slots = text, True, {}

    @property
    def enabled(self):
        return self.own and not ContainedButton.container_disabled

    def setEnabled(self, on):
        self.own = on


class BusySplitter(Anything):
    """The dialog's splitter: disabled while the dialog is busy, and its buttons with it."""

    def setEnabled(self, on):
        ContainedButton.container_disabled = not on


class Recorded(Anything):
    """A control or a label: its text, What's This, tooltip, value, and state kept; each one made is listed."""
    made = []

    def __init__(self, *args):
        self.text = args[0] if args and isinstance(args[0], (str, type(u""))) else u""
        self.whats, self.tip, self.placeholder, self.labels, self.slots = u"", u"", u"", [], {}
        self.value, self.currentIndex, self.checked, self.enabled = 0, 0, False, True
        Recorded.made.append(self)

    def setWhatsThis(self, text):
        self.whats = text

    def setToolTip(self, text):
        self.tip = text

    def setPlaceholderText(self, text):
        self.placeholder = text

    def setText(self, text):
        self.text = text

    def setValue(self, value):
        self.value = value

    def setCurrentIndex(self, index):
        self.currentIndex = index

    def setChecked(self, on):
        self.checked = on

    def setEnabled(self, on):
        self.enabled = on

    def setVisible(self, on):
        self.visible = on

    def addItem(self, label):
        self.labels.append(label)

    def clear(self):
        self.labels = []

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)


CONTROL_KINDS = ("QPushButton", "QCheckBox", "QComboBox", "QSpinBox", "QLineEdit", "QPlainTextEdit")
RECORDED = dict((kind, type(kind, (Recorded,), {})) for kind in CONTROL_KINDS + ("QLabel",))


class RecordedTree(FakeTree):
    """A list: its What's This kept, and listed among the controls made."""

    def __init__(self, *args):
        FakeTree.__init__(self, *args)
        self.whats = u""
        Recorded.made.append(self)

    def setWhatsThis(self, text):
        self.whats = text


class RecordedRow(Anything):
    """A row of a layout (QHBoxLayout): the widgets put in it, in order."""
    made = []

    def __init__(self, *args):
        self.widgets = []
        RecordedRow.made.append(self)

    def addWidget(self, widget, *args):
        self.widgets.append(widget)


class FakeQTransform(Anything):
    def __init__(self, *args):
        self.args = args


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

    def getLayerByName(self, master, create=False):
        code = self.fgGlyph.unicode
        return FakeLayer(500 + 10 * (code - 0x30) if code and 0x30 <= code <= 0x39 else 500)  # proportional figures


class FakeCodeGlyph(object):
    """A built glyph's fgGlyph: setting its code point is recorded."""

    def __init__(self, name, events):
        self.name, self.events, self.code = name, events, None

    @property
    def unicode(self):
        return self.code

    @unicode.setter
    def unicode(self, code):
        self.code = code
        self.events.append(("code", self.name))

    @property
    def unicodes(self):
        return [self.code] if self.code else []


class ArgsTransform(object):
    """A component's transform as a shape gives it back: its matrix's values (QTransform's getters)."""

    def __init__(self, args):
        self.args = tuple(args) + (0.0,) * (6 - len(args))

    def m11(self):
        return self.args[0]

    def m12(self):
        return self.args[1]

    def m21(self):
        return self.args[2]

    def m22(self):
        return self.args[3]

    def dx(self):
        return self.args[4]

    def dy(self):
        return self.args[5]

    def map(self, contour):
        return FakeTransform().map(contour)


class FakeComponentShape(FakeShape):
    """A component as a built layer holds it: the glyph it points to and its transform."""
    isComponent = True

    def __init__(self, component):
        FakeShape.__init__(self, ((0, 300, 300, 720),))
        self.shapeData = Anything()
        self.shapeData.componentGlyph = component.name
        self.transform = ArgsTransform(getattr(component.transform, "args", ()))


class FakeBuiltLayer(object):
    def __init__(self, name, events):
        self.name, self.events, self.shapes, self.advanceWidth, self.isNull = name, events, [], 0, False
        self.components = []

    def setGlyphComponents(self, components, width, package, flag):
        self.components, self.advanceWidth = list(components), width
        self.shapes = [FakeComponentShape(component) for component in components]
        self.events.append(("layer", self.name))

    def removeAllShapes(self):
        self.shapes, self.components = [], []
        self.events.append(("emptied", self.name))


class FakeBuiltGlyph(object):
    """A glyph a script adds: its layers made on it."""

    def __init__(self, name, events):
        self.name, self.isNull, self.mark, self.events = name, False, 0, events
        self.fgGlyph = FakeCodeGlyph(name, events)
        self.made = {}

    @property
    def layers(self):
        return list(self.made.values())

    def getLayerByName(self, master, create=False):
        if master not in self.made and create:
            self.made[master] = FakeBuiltLayer(self.name, self.events)
        return self.made.get(master)


class FakeNewGlyph(object):
    def __init__(self):
        self.name = None


class FakeComponent(object):
    def __init__(self, name):
        self.name, self.transform = name, None


class FakeItems(object):
    def __init__(self):
        self.steps, self.updates = [], 0

    def notifyChangesApplied(self, title, package, whole):
        self.steps.append(title)

    def notifyPackageContentUpdated(self, key):
        self.updates += 1


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
        self.fgPackage.id = id(self)  # (FontLab's number for the open font: the same at every read)
        self.isNull, self.glyphsCount, self.upm, self.tfn, self.path = False, len(self.glyphs), 1000, u"Fake", u"fake.vfc"
        self.master, self.masters, self.capsHeight_value, self.events = u"Regular", [u"Regular"], 700.0, []

    def findName(self, name):
        return self.by_name.get(name)

    def setFlag(self, flag, value):  # (marked modified, as notify_changed does)
        self.__dict__.setdefault("flags", []).append((flag, value))

    def findUnicode(self, code):
        for glyph in self.glyphs:
            if glyph.fgGlyph.unicode == code:
                return glyph
        return None

    def addGlyph(self, glyph):
        added = FakeBuiltGlyph(glyph.name, self.events)
        self.events.append(("add", glyph.name))
        self.glyphs.append(added)
        self.by_name[added.name] = added
        self.fgPackage.glyphs.append(added.fgGlyph)
        self.glyphsCount = len(self.glyphs)

    def deleteGlyph(self, glyph):
        self.glyphs.remove(glyph)
        self.fgPackage.glyphs.remove(glyph.fgGlyph)
        del self.by_name[glyph.name]

    def currentHistoryState(self):
        return 1

    def initialHistoryState(self):
        return 0  # (a step recorded since it was opened: the font itself has a state to go back to)


# A font whose figures are outlines with nodes (one upright stem each), for the strokes kept while
# scaling: what the build writes is measured on them.

STEM = (100.0, 180.0, 0.0, 700.0)  # a figure's stem: left, right, bottom, top (80 units wide)


class FakeNode(object):
    def __init__(self, x, y, kind=u"on"):
        self.x, self.y, self.type = x, y, kind


class NodeContour(object):
    """A contour whose nodes() are its own nodes: what is set on them is kept."""

    def __init__(self, points):
        self.points = [FakeNode(*point) for point in points]

    def nodes(self):
        return list(self.points)

    def update(self):
        pass

    def clone(self):
        """A copy that belongs to no shape (FontLab's flContour.clone)."""
        return type(self)([(n.x, n.y, n.type) for n in self.points])

    def path(self):
        return self

    @property
    def box(self):
        xs, ys = [n.x for n in self.points], [n.y for n in self.points]
        return (min(xs), min(ys), max(xs), max(ys))


class DroppingContour(NodeContour):
    """A contour whose nodes() are copies: what is set on them is lost, as it may be in FontLab."""

    def nodes(self):
        return [FakeNode(n.x, n.y, n.type) for n in self.points]


class OddContour(NodeContour):
    """A contour whose nodes' type does not read "on"."""

    def __init__(self, points):
        self.points = [FakeNode(point[0], point[1], u"line") for point in points]


class PlainTransform(FakeTransform):
    def m11(self):
        return 1.0

    def m22(self):
        return 1.0


class NodeShape(object):
    """A shape of node contours. What it draws (its boundingBox) is kept apart from its nodes, as FontLab
    keeps a shape's outline: worked out when it is made, transformed, given contours, or updated, not
    when a node is moved (seen live: a node set from a script moved, the shape's box did not)."""
    isComponent = False

    def __init__(self, contours):
        self.contours, self.transform = contours, PlainTransform()
        self.updates = 0
        self.draw()

    def draw(self):
        boxes = [c.box for c in self.contours if c.points]
        self.drawn = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                      max(b[3] for b in boxes)) if boxes else (0, 0, 0, 0)

    @property
    def boundingBox(self):
        return NodeRect(self.drawn)

    def update(self):
        self.updates += 1
        self.draw()

    def cloneTopLevel(self):
        return type(self)([type(c)([(n.x, n.y, n.type) for n in c.points]) for c in self.contours])

    def applyTransform(self, transform):
        sx, _, _, sy, dx, dy = transform.args
        for contour in self.contours:
            for node in contour.points:
                node.x, node.y = node.x * sx + dx, node.y * sy + dy
        self.draw()


class StaleShape(NodeShape):
    """A shape that never draws its nodes anew once made and transformed (update changes nothing): what
    FontLab did when the forms built at 130% looked as scaled."""

    def update(self):
        self.updates += 1


class NewShape(NodeShape):
    """A shape made from a script (fontlab.flShape()), given its contours at once (addContours)."""

    def __init__(self):
        NodeShape.__init__(self, [])
        self.notified = []

    def addContours(self, contours, notify):
        self.contours = list(contours)
        self.notified.append(notify)
        self.draw()


def no_new_shape():
    raise TypeError("this FontLab makes no shape from a script")


class NodeLayer(object):
    def __init__(self, advance=500, contour=NodeContour, shape=NodeShape):
        left, right, bottom, top = STEM  # counterclockwise, y up
        self.shapes = [shape([contour([(left, bottom), (right, bottom), (right, top), (left, top)])])]
        self.advanceWidth, self.isNull = advance, False


class NodeBuiltLayer(FakeBuiltLayer):
    def addShape(self, shape):
        self.shapes.append(shape)
        self.events.append(("shape", self.name))

    def update(self):
        self.events.append(("measured", self.name))


class NodeBuiltGlyph(FakeBuiltGlyph):
    def getLayerByName(self, master, create=False):
        if master not in self.made and create:
            self.made[master] = NodeBuiltLayer(self.name, self.events)
        return self.made.get(master)


class NodePackage(FakePackage):
    """The fake font with its figures drawn as stems of nodes; what a build adds can hold outlines."""

    def __init__(self, features, contour=NodeContour, shape=NodeShape):
        FakePackage.__init__(self, features)
        self.drawn = dict((name, NodeLayer(500, contour, shape)) for name in DIGIT_NAMES)
        for name, layer in self.drawn.items():
            self.by_name[name].getLayerByName = lambda master, create=False, layer=layer: layer

    def addGlyph(self, glyph):
        added = NodeBuiltGlyph(glyph.name, self.events)
        self.glyphs.append(added)
        self.by_name[added.name] = added
        self.fgPackage.glyphs.append(added.fgGlyph)
        self.glyphsCount = len(self.glyphs)


class FakePoint(object):
    def __init__(self, x, y):
        self.px, self.py = x, y

    def x(self):
        return self.px

    def y(self):
        return self.py


class NodeRect(FakeRect):
    def isEmpty(self):
        return self.box[0] >= self.box[2] or self.box[1] >= self.box[3]


class NodePath(object):
    """A layer's outline: its box, and whether a point is inside one of its contours' boxes (stems)."""

    def __init__(self, layer):
        self.boxes = [c.box for shape in layer.shapes for c in shape.contours]

    def boundingRect(self):
        return NodeRect((min(b[0] for b in self.boxes), min(b[1] for b in self.boxes),
                         max(b[2] for b in self.boxes), max(b[3] for b in self.boxes)))

    def isEmpty(self):
        return not self.boxes

    def contains(self, point):
        return any(b[0] <= point.x() <= b[2] and b[1] <= point.y() <= b[3] for b in self.boxes)


def stem_of(layer):
    """The width of a built layer's stem, measured on its nodes."""
    xs = [n.x for shape in layer.shapes for c in shape.contours for n in c.points]
    return max(xs) - min(xs)


class CheckBoxTests(unittest.TestCase):
    def test_the_sheet_draws_boxes_plain_to_see(self):
        sheet = fc.check_box_sheet(13, u"C:\\temp\\check.png", u"rgb(1, 2, 3)")
        self.assertIn(u"QTreeView::indicator { width: 13px; height: 13px; border: 1px solid %s;" % fc.CHECK_FRAME, sheet)
        self.assertIn(u'image: url("C:/temp/check.png")', sheet, "forward slashes")
        self.assertIn(u"QTreeView::indicator:checked { border: 1px solid rgb(1, 2, 3); background: rgb(1, 2, 3);", sheet)
        self.assertNotIn(u"image", fc.check_box_sheet(13), "no mark: filled only")

    def test_the_list_keeps_its_own_sheet_and_dark_mode_switches_redraw(self):
        class Tree(object):
            palette, styleSheet = None, u"QTreeView::item { color: red; } " + fc.CHECK_SHEET_MARK + u" old rules"

            def __init__(self):
                self.sheets = []

            def setStyleSheet(self, sheet):
                self.sheets.append(sheet)

            def style(self):
                raise AttributeError("style")

        tree = Tree()
        fc.style_check_boxes(_FakeQtModule(), _FakeQtModule(), tree, u"QTreeView::item { color: red; }")
        self.assertEqual(tree.sheets[0], u"", "cleared first: polished again")
        self.assertTrue(tree.sheets[1].startswith(u"QTreeView::item { color: red; } " + fc.CHECK_SHEET_MARK))
        self.assertIn(u"width: 13px", tree.sheets[1], "the style's size unknown: 13 pixels")
        self.assertNotIn(u"image", tree.sheets[1], "no folder for the mark (a fake Qt): filled only")
        saved = sys.modules.get("PythonQt")
        qt = Anything()
        qt.QtCore, qt.QtGui = _FakeQtModule(), _FakeQtModule()
        sys.modules["PythonQt"] = qt
        try:
            watcher = fc.watch_check_boxes(Anything(), [tree])
        finally:
            if saved is None:
                sys.modules.pop("PythonQt", None)
            else:
                sys.modules["PythonQt"] = saved
        self.assertIsNotNone(watcher)
        self.assertEqual(tree.sheets[-1].count(fc.CHECK_SHEET_MARK), 1, "the old rules replaced, not added to")
        self.assertNotIn(u"old rules", tree.sheets[-1])


class HighlightTests(unittest.TestCase):
    """The Code box's colors (the owner, 2026-11-14: "syntax highlighting would be neat")."""

    def kinds(self, line, in_list=False):
        spans, still_open = fc.fea_spans(line, in_list)
        return [(line[start:start + length], kind) for start, length, kind in spans], still_open

    def test_each_part_of_a_line(self):
        self.assertEqual(self.kinds(u"feature liga {"), ([(u"feature", "keyword"), (u"liga", "tag")], False))
        self.assertEqual(self.kinds(u"} liga;"), ([(u"liga", "tag")], False))
        self.assertEqual(self.kinds(u"languagesystem latn TRK;")[0],
                         [(u"languagesystem", "keyword"), (u"latn", "tag"), (u"TRK", "tag")])
        self.assertEqual(self.kinds(u"  script latn; language ROM;")[0],
                         [(u"script", "keyword"), (u"latn", "tag"), (u"language", "keyword"), (u"ROM", "tag")])
        self.assertEqual(self.kinds(u"lookup FreeLab_case {")[0], [(u"lookup", "keyword"), (u"FreeLab_case", "tag")])
        self.assertEqual(self.kinds(u"  sub @FreeLab_turn_0 @FreeLab_letters_1' by @FreeLab_turn_1;")[0],
                         [(u"sub", "keyword"), (u"@FreeLab_turn_0", "class"), (u"@FreeLab_letters_1", "class"),
                          (u"by", "keyword"), (u"@FreeLab_turn_1", "class")])
        self.assertEqual(self.kinds(u"  sub uni0041 one.sups by f_i; # FreeLab begin")[0],
                         [(u"sub", "keyword"), (u"by", "keyword"), (u"# FreeLab begin", "comment")],
                         "glyph names keep the text's color, figures in a name are no number")
        self.assertEqual(self.kinds(u"@x = [a b.sc c];")[0], [(u"@x", "class"), (u"[a b.sc c]", "list")])
        self.assertEqual(self.kinds(u"  featureNames { name \"Single-story a\"; };")[0],
                         [(u"featureNames", "keyword"), (u"name", "keyword"), (u"\"Single-story a\"", "string")])
        self.assertEqual(self.kinds(u"pos a b -120; lookupflag IgnoreMarks;")[0],
                         [(u"pos", "keyword"), (u"-120", "number"), (u"lookupflag", "keyword"),
                          (u"IgnoreMarks", "keyword")])
        self.assertEqual(self.kinds(u"#> feature")[0], [(u"#> feature", "comment")], "FontLab's marker lines")
        self.assertEqual(self.kinds(u"include(features.fea);")[0], [(u"include", "keyword")])
        self.assertEqual(self.kinds(u""), ([], False))

    def test_a_list_over_several_lines(self):
        """A class of thousands of glyphs is written a few names to a line (class_lines): its lines are
        the list's color, carried from line to line."""
        lines = fc.class_lines(u"@FreeLab_letters", [u"g%d" % n for n in range(fc.CLASS_LINE_GLYPHS * 2 + 1)])
        self.assertGreater(len(lines), 3)
        still_open, kinds = False, []
        for line in lines:
            spans, still_open = fc.fea_spans(line, still_open)
            kinds.append([kind for _, _, kind in spans])
        self.assertEqual(kinds[0], ["class", "list"])
        self.assertTrue(all(k == ["list"] for k in kinds[1:]), kinds)
        self.assertFalse(still_open, "closed at the end")
        self.assertEqual(self.kinds(u"  a b c", True), ([(u"  a b c", "list")], True))
        self.assertEqual(self.kinds(u"]; sub a by b;", True)[0], [(u"]", "list"), (u"sub", "keyword"), (u"by", "keyword")])

    def test_colors_plain_to_read_on_either_palette(self):
        def lightness(rgb):
            return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0

        self.assertEqual(set(fc.FEA_COLORS), set(fc.FEA_KINDS))
        for kind in fc.FEA_KINDS:
            self.assertGreater(lightness(fc.fea_color(kind, True)), 0.55, "%s on a dark background" % kind)
            self.assertLess(lightness(fc.fea_color(kind, False)), 0.40, "%s on a light background" % kind)
        self.assertEqual(len(set(fc.fea_color(kind, True) for kind in fc.FEA_KINDS)), len(fc.FEA_KINDS))


class DrawnBoxTests(unittest.TestCase):
    """What tells a thickened form FontLab draws as it was (the owner saw no difference at 130%)."""

    def test_the_drawn_box_against_the_nodes(self):
        square = [[(0.0, 0.0, True, True), (10.0, 0.0, True, True), (10.0, 10.0, True, True), (0.0, 10.0, True, True)]]
        self.assertTrue(fc.drawn_box_kept((0.0, 0.0, 10.0, 10.0), (square,)))
        self.assertTrue(fc.drawn_box_kept((0.4, -0.5, 10.0, 10.5), (square,)), "rounded to units")
        self.assertFalse(fc.drawn_box_kept((2.0, 2.0, 8.0, 8.0), (square,)), "drawn as before the offset")
        self.assertIsNone(fc.drawn_box_kept(None, (square,)), "not known")
        self.assertTrue(fc.drawn_box_kept((2.0, 2.0, 8.0, 8.0), (square, [[(2.0, 2.0, True, True),
                                                                           (8.0, 8.0, True, True)]])),
                        "in the shape's own coordinates")
        arch = [[(0.0, 0.0, True, True), (5.0, 20.0, True, False), (10.0, 0.0, True, True)]]
        self.assertTrue(fc.drawn_box_kept((0.0, 0.0, 10.0, 15.0), (arch,)), "a curve stays inside its handles")
        self.assertFalse(fc.drawn_box_kept((0.0, 0.0, 10.0, 25.0), (arch,)))

    def test_matrices(self):
        self.assertEqual(fc.compose(fc.IDENTITY, (0.5, 0.5, 10.0, 20.0)), (0.5, 0.0, 0.0, 0.5, 10.0, 20.0))
        self.assertEqual(fc.mapped(fc.compose((1.0, 0.0, 0.0, 1.0, 4.0, 0.0), (0.5, 0.5, 10.0, 20.0)), 100.0, 100.0),
                         (62.0, 70.0), "the shape's own transform first, then the plan's")
        self.assertEqual(fc.shape_matrix(object()), fc.IDENTITY)
        self.assertEqual(fc.shape_matrix(NodeShape([])), fc.IDENTITY, "what a transform does not say: the identity's")
        self.assertIsNone(fc.shape_box(object()))
        self.assertEqual(fc.shape_box(NodeShape([NodeContour([(1, 2), (5, 2), (5, 9)])])), (1.0, 2.0, 5.0, 9.0))


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

    def dialog(self, features, package=None, classes=None, core=None):
        qt = Anything()
        qt.QtCore = _FakeQtModule(dict({"Qt": FakeQt, "QSize": FakeSize}, **(core or {})))
        qt.QtGui = _FakeQtModule(dict({"QTreeWidget": FakeTree, "QTreeWidgetItem": FakeItem, "QLineEdit": FakeEdit,
                                       "QPushButton": FakeButton, "QTransform": FakeQTransform}, **(classes or {})))
        package = package or FakePackage(features)
        workspace = Anything()
        workspace.packages = lambda: [package]
        workspace.currentPackage = package
        fontlab = Anything()
        fontlab.flWorkspace = Anything()
        fontlab.flWorkspace.instance = lambda: workspace
        fontlab.flPackage = lambda item: item  # (FontLab's wrapper of an open font: its number read through it)
        fontlab.flGlyph, fontlab.GlyphComponent, fontlab.flItems = FakeNewGlyph, FakeComponent, FakeItems()
        self.fontlab = fontlab
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
        self.assertIsNotNone(dialog.check_watcher, "the lists' check boxes drawn from the palette")
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

    def small_section(self, dialog, group):
        return [item for item in dialog.small_tree.items if item.data(0, USER_ROLE) == group][0]

    def test_figure_forms_built(self):
        dialog = self.dialog(FakeFeatures({}))
        package = dialog.package
        self.assertEqual([item.data(0, USER_ROLE) for item in dialog.small_tree.items],
                         ["sups", "superscript", "subs", "subscript"], "numerators, denominators, a, and o drawn")
        self.assertEqual(dialog.build_button.text, u"Build 40 ticked figure forms")
        self.assertTrue(dialog.build_button.enabled)
        self.small_section(dialog, "subscript").setCheckState(0, UNCHECKED)
        self.assertEqual(dialog.build_button.text, u"Build 30 ticked figure forms")
        self.assertEqual(self.small_section(dialog, "subscript").child(0).checkState(0), UNCHECKED)
        sups = self.small_section(dialog, "sups")
        # Owner's report 159: a folded group showed nothing in the other columns (its first column spanned them)
        self.assertEqual(sups.text(1), u"10 of 10 glyphs ticked")
        self.assertEqual(sups.text(2), u"10 scaled from their figures", "a short note of what its rows say")
        self.assertEqual(self.small_section(dialog, "superscript").text(2),
                         u"10 copies of their set's glyphs; U+00B2 to U+2079")
        self.assertFalse(sups.spanned, "not spanned: its count and note stand in their columns")
        dialog.small_expanded(sups)  # (its pictures drawn)
        self.assertIn(u"two at 59%, raised 357 units", sups.child(2).text(1))
        self.assertIn(u"a start to draw over", sups.child(2).text(2))
        self.assertTrue(self.small_section(dialog, "superscript").child(2).text(2).startswith(u"U+00B2 "))
        dialog.small_clicked(sups.child(2), 0)
        self.assertEqual(dialog.small_set_index, fc.SMALL_SETS.index("sups"))
        dialog.small_setting("scale", 50)
        self.assertEqual(dialog.small_plans[u"two.sups"].parts[0][1], 0.5)
        self.assertIn(u"two at 50%", sups.child(2).text(1))
        dialog.restore()
        self.assertEqual(dialog.small_plans[u"two.sups"].parts[0][1], 0.59)
        self.assertEqual(dialog.build_button.text, u"Build 40 ticked figure forms", "the checks restored too")
        self.small_section(dialog, "subscript").setCheckState(0, UNCHECKED)
        self.small_section(dialog, "subs").child(0).setCheckState(0, UNCHECKED)  # zero.subs
        self.assertEqual(dialog.build_button.text, u"Build 29 ticked figure forms")
        dialog.build_small_forms()
        self.assertEqual(self.fontlab.flItems.steps, [u"FreeLab Feature Code (before)", u"FreeLab Feature Code"],
                         "the font's first write from FreeLab: the font as it was recorded first, for Undo to go back to")
        two = package.findName(u"two.sups")
        self.assertEqual(two.made[u"Regular"].advanceWidth, float(int(round(520 * 0.59 * 1.12))))
        component = two.made[u"Regular"].components[0]
        self.assertEqual(component.name, u"two")
        self.assertEqual(component.transform.args[:4], (0.59, 0.0, 0.0, 0.59))
        self.assertEqual(component.transform.args[5], 357.0)
        superior = package.findName(u"uni00B2")
        self.assertEqual(superior.fgGlyph.unicode, 0xB2)
        self.assertEqual([c.name for c in superior.made[u"Regular"].components], [u"two.sups"], "a copy of two.sups")
        self.assertLess(package.events.index(("layer", u"uni00B2")), package.events.index(("code", u"uni00B2")),
                        "the code point set once its layer is made")
        self.assertLess(package.events.index(("add", u"two.sups")), package.events.index(("add", u"uni00B2")))
        self.assertIsNone(package.findName(u"uni2080"), "unchecked: not built")
        self.assertIsNone(package.findName(u"zero.subs"))
        done = [t for level, t in self.logged if level == "done"]
        self.assertTrue(done and u"Built <b>29 glyphs</b>" in done[-1], self.logged)
        # The glyphs a log line names are links (drawn from the font's outlines, opened by a click)
        self.assertIn(u'<a href="glyphname:two.sups">two.sups</a>', done[-1])
        self.assertEqual(done[-1].count(u'<a href="glyphname:'), 29)
        self.assertEqual(dialog.log.source(), (self.fontlab, package, package.master), "the log follows the font")
        # The font read again: the forms take them, and what is left keeps its checks
        tags = [item.data(0, USER_ROLE) for item in dialog.forms_tree.items]
        self.assertIn("sups", tags)
        self.assertIn("subs", tags)
        # What was built stays listed (a build replaces it once its settings change), checked as built; the
        # button grays out, nothing checked would change (owner's report 160), and says why
        self.assertEqual([item.data(0, USER_ROLE) for item in dialog.small_tree.items],
                         ["sups", "superscript", "subs", "subscript"])
        self.assertEqual(sorted(dialog.small_ours), sorted(t.split(u'">')[0] for t in
                                                          done[-1].split(u'<a href="glyphname:')[1:]))
        self.assertEqual(dialog.build_button.text, u"Build ticked figure forms")
        self.assertFalse(dialog.build_button.enabled)
        self.assertEqual(dialog.small_counts(),
                         u"The font lacks <b>11 figure forms</b>. <b>29 figure forms</b> were built here before: a "
                         u"build replaces them once their settings change.")
        self.assertFalse([t for level, t in self.logged if level in ("error", "warning")], self.logged)

    def test_a_ligature_choice_lasts_past_the_write(self):
        """Codex review 8, finding 4: Off took f_i's rule out, the window read the font again, offered f_i as its
        name suggests (Discretionary), and the next write put it back. The choices last for the same font."""
        for choice, liga, dlig in (("off", 0, 0), ("liga", 1, 0), ("dlig", 0, 1)):
            features = FakeFeatures({u"liga": u"feature liga {\n#> feature\n  sub f i by f_i;\n#< feature\n} liga;\n"})
            dialog = self.dialog(features, self.with_glyphs(features, [u"f"]))
            lig = [lig for lig in dialog.found if lig.glyph == u"f_i"][0]
            self.assertFalse(lig.fixed, "FontLab's automatic rule: FreeLab's to move")
            dialog.choose(lig, [key for key, _ in fc.CHOICES].index(choice))
            for _ in range(2):  # (write, the font read again, write again)
                dialog.write()
                self.assertEqual([l.choice for l in dialog.found if l.glyph == u"f_i"], [choice], "the choice kept")
                texts = dict((tag, features.texts.get(tag, u"")) for tag in (u"liga", u"dlig"))
                self.assertEqual((texts[u"liga"].count(u"sub f i by f_i;"), texts[u"dlig"].count(u"sub f i by f_i;")),
                                 (liga, dlig), (choice, texts))
            self.assertFalse(dialog.write_button.enabled, "nothing left to write")

    def test_history_keeps_choices(self):
        dialog = self.dialog(FakeFeatures({}))
        self.section(dialog, "frac").setCheckState(0, UNCHECKED)
        dialog.history_moved()
        self.assertFalse(dialog.form_feature("frac").on)
        self.assertEqual(self.section(dialog, "frac").checkState(0), UNCHECKED)

    def test_no_list_cell_shows_markup(self):
        """aalt's row read "<i>Glyphs</i>" as typed: a list's cell draws no rich text, so no cell of any
        list holds a tag or an escaped character."""
        case_feature = fc.case_feature

        def marked(info):  # (a note written as for a label, one day)
            feature = case_feature(info)
            feature.note, feature.rules[0].note = u"The <i>Case</i> forms", u"Kept <b>bold</b> &amp; <i>plain</i>"
            return feature

        fc.case_feature = marked
        try:
            dialog = self.dialog(FakeFeatures({"liga": u"feature liga {\n  sub f i by f_i;\n} liga;\n"}))
        finally:
            fc.case_feature = case_feature
        cells = []
        for tree in (dialog.ligature_tree, dialog.alternate_tree, dialog.forms_tree, dialog.small_tree):
            for item in tree.items:
                for row in [item] + item.children:
                    cells.extend(u"%s" % text for text in row.texts)
        self.assertGreater(len(cells), 100)
        self.assertEqual([text for text in cells if MARKUP.search(text)], [])
        self.assertIn(u"Kept bold & plain", cells)
        self.assertIn(u"The Case forms", cells)
        aalt = [item for item in dialog.forms_tree.items if item.data(0, USER_ROLE) == "aalt"][0]
        self.assertIn(u"their Glyphs panel", aalt.text(2))

    def big_font(self, features, variants=2):
        """A font of every Latin letter to U+024F, each with built variants (X.alt1, X.alt2)."""
        package = FakePackage(features)
        letters = [(fc.unichr_(code) if code < 0x80 else u"uni%04X" % code, code) for code in range(0x41, 0x250)
                   if unicodedata.category(fc.unichr_(code)) in ("Lu", "Ll")]
        names = letters + [(u"space", 0x20)]
        names += [(u"%s.alt%d" % (name, n), None) for n in range(1, variants + 1) for name, _ in letters]
        package.glyphs = [FakeGlyph(name, code) for name, code in names]
        package.by_name = dict((g.name, g) for g in package.glyphs)
        package.fgPackage.glyphs = [g.fgGlyph for g in package.glyphs]
        package.glyphsCount = len(package.glyphs)
        return package, [name for name, _ in letters]

    def look_back(self, dialog, letters):
        """The look back set (the fake spin box holds no number), and the font read with it as if for the
        first time (no checks kept from the reading before)."""
        dialog.look_back = Anything()
        dialog.look_back.value = letters
        dialog.package = None
        dialog.run()

    def test_a_whole_alphabet_of_variants(self):
        """With variants built for every letter (1,102 in the report), the calt code was 56 MB, the list
        drew a picture per letter, and FontLab's compiler stopped at "coverage section too large". Now:
        the letters that double in text come first and start checked, taking turns by letter; all of
        them checked take turns by position, in a few rules; the checks survive the font read again."""
        features = FakeFeatures({})
        package, letters = self.big_font(features)
        drawn = []
        picture = fc.FeatureCodeDialog.picture
        fc.FeatureCodeDialog.picture = lambda self, names: drawn.append(names)
        try:
            dialog = self.dialog(features, package, {"QLabel": FakeEdit})
            del drawn[:]
            self.look_back(dialog, 2)
        finally:
            fc.FeatureCodeDialog.picture = picture
        rows = dialog.alternate_tree.items
        self.assertEqual(len(rows), len(letters))
        self.assertGreater(len(letters), 300)
        self.assertLessEqual(len([names for names in drawn if len(names) == 3]), fc.TURN_PICTURES,
                             "the first rows' cycles drawn; the rest when clicked")
        first = [row.data(0, USER_ROLE) for row in rows[:8]]
        self.assertEqual(set(first), set(u"eEtTiIaA"), "the letters doubled most in text lead (ee, tt, ii, aa)")
        self.assertEqual(rows[0].text(2), u"Often")
        self.assertEqual(rows[-1].text(2), u"Seldom")
        checked = set(dialog.cycling())
        self.assertEqual(checked, dialog.often, "more letters than rules by letter serve: the doubled ones start checked")
        self.assertTrue(set(u"lLsSeEoOtTfF") <= checked and u"x" not in checked and u"q" not in checked)
        self.assertEqual(fc.turn_mode(dialog.cycling(), 2), "letter")
        self.assertIn(u"<b>60 glyphs</b> ticked, taking turns <b>by glyph</b>", dialog.turn_label.text)
        self.assertIn(u"  ignore sub l.alt2 l';\n", dialog.new_texts()["calt"])
        states = dict((key, button.enabled) for (key, _, _), button in zip(fc.TURN_CHECKS, dialog.turn_buttons))
        self.assertEqual(states, {"often": False, "all": True, "none": True})
        dialog.check_turns("all")
        self.assertEqual(len(dialog.cycling()), len(letters))
        # Owner's report 118: these buttons left no line in the log
        self.assertEqual(self.logged[-1], ("info", u"<i>Tick all</i> ticked <b>%d glyphs</b>." % (len(letters) - 60)))
        self.assertIn(u"<b>by position</b>", dialog.turn_label.text)
        texts = dialog.new_texts()
        self.assertLess(len(texts["calt"]), 40000, "a few rules on classes, not megabytes")
        self.assertIn(u"sub @FreeLab_turn_0 @FreeLab_letters_1' by @FreeLab_turn_1;", texts["calt"])
        self.assertIn(u"sub @FreeLab_turn_1 @FreeLab_letters_1' by @FreeLab_turn_2;", texts["calt"])
        if HAVE_FONTTOOLS:
            self.assertIsNone(fc.check_code(texts["calt"], dialog.names))
        self.assertTrue(dialog.write_button.enabled)
        shown = []
        dialog.progress = lambda what, done=None, total=None, force=False, stoppable=True: shown.append(
            (what, dialog.busy and not stoppable))
        dialog.write()
        self.assertIn((u"Writing the code", True), shown, "its progress said, the dialog busy meanwhile, never stopped")
        self.assertFalse(dialog.busy)
        self.assertEqual(features.texts["calt"], texts["calt"])
        self.assertEqual(len(dialog.cycling()), len(letters), "read again after writing: the checks kept")
        self.assertFalse(dialog.write_button.enabled, "the font has this code")
        # Opened again later, the letters in the font's code are the ones checked
        again = self.dialog(features, self.big_font(features)[0], {"QLabel": FakeEdit})
        self.look_back(again, 2)
        self.assertEqual(len(again.cycling()), len(letters))
        self.assertFalse(again.write_button.enabled)
        again.check_turns("often")
        self.assertEqual(set(again.cycling()), again.often)
        again.restore()
        self.assertEqual(len(again.cycling()), len(letters), "restored as it first came: what the font's code has")
        again.check_turns("none")
        self.assertEqual(again.cycling(), {})
        self.assertEqual(self.logged[-1], ("info", u"<i>Tick none</i> unticked <b>%d glyphs</b>." % len(letters)))
        self.assertIn(u"No glyph is ticked", again.turn_label.text)
        again.check_turns("none")
        self.assertEqual(self.logged[-1], ("info", u"<i>Tick none</i> changed nothing."))

    def with_glyphs(self, features, names):
        """The fake font with more glyphs (names, no characters)."""
        package = FakePackage(features)
        for name in names:
            glyph = FakeGlyph(name, None)
            package.glyphs.append(glyph)
            package.by_name[name] = glyph
            package.fgPackage.glyphs.append(glyph.fgGlyph)
        return package

    def test_figures_and_punctuation_take_turns(self):
        """Only letters took turns: a figure's or a period's alternates were not listed, though the counts
        knew 00 and 99. They are listed, ranked, and checked by the same evidence, each kind looking back
        among its own, so the letters' turns stay what they were."""
        features = FakeFeatures({})
        package = self.with_glyphs(features, [u"zero.alt1", u"nine.alt1", u"one.alt1", u"period.alt1", u"hyphen.alt1",
                                              u"slash.alt1", u"fraction.alt1"])
        dialog = self.dialog(features, package, {"QLabel": FakeEdit})
        self.look_back(dialog, 2)
        rows = dialog.alternate_tree.items
        self.assertEqual([row.data(0, USER_ROLE) for row in rows],
                         [u"l", u"zero", u"nine", u"period", u"hyphen", u"one", u"slash"],
                         "ll, 00, 99, then the marks doubled by convention, then 11 and //; a fraction bar is a symbol")
        self.assertEqual([row.text(2) for row in rows], [u"Often"] * 5 + [u"Seldom"] * 2)
        self.assertEqual(dialog.often, set([u"l", u"zero", u"nine", u"period", u"hyphen"]))
        self.assertEqual(sorted(dialog.cycling()), sorted(row.data(0, USER_ROLE) for row in rows), "few: all checked")
        self.assertIn(u"<b>7 glyphs</b> ticked, taking turns <b>by glyph</b>", dialog.turn_label.text)
        self.assertIn(u"<b>7 glyphs</b> with alternates taking turns", dialog.status.text)
        calt = dialog.new_texts()["calt"]
        classes = classes_of(calt)
        self.assertEqual(sorted(classes), [u"FreeLab_figures", u"FreeLab_letters", u"FreeLab_punctuation"])
        figures, marks, letters = classes[u"FreeLab_figures"], classes[u"FreeLab_punctuation"], classes[u"FreeLab_letters"]
        self.assertTrue(set([u"zero", u"zero.alt1", u"one.tf", u"nine.numr"]) <= figures, "a figure's forms too")
        self.assertFalse(figures & set([u"l", u"period", u"fraction", u"f_i"]))
        self.assertTrue(set([u"period", u"period.alt1", u"hyphen", u"hyphen.case", u"parenleft", u"ampersand"]) <= marks)
        self.assertFalse(marks & set([u"fraction", u"zero", u"l", u"acutecomb"]))
        self.assertTrue(set([u"l", u"l.2", u"i.loclTRK", u"a.sc"]) <= letters)
        self.assertFalse(letters & set([u"zero", u"period", u"hyphen", u"one.tf"]), "the letters' class is the letters'")
        for rule in (u"  sub zero zero' by zero.alt1;", u"  sub zero @FreeLab_figures @FreeLab_figures zero' by zero.alt1;",
                     u"  sub period @FreeLab_punctuation period' by period.alt1;",
                     u"  sub l @FreeLab_letters l' by l.2;"):
            self.assertIn(rule, calt)
        if HAVE_FONTTOOLS:
            self.assertIsNone(fc.check_code(calt, dialog.names))
        dialog.check_turns("often")
        self.assertEqual(set(dialog.cycling()), dialog.often, "the button checks the figures and marks often doubled too")
        self.assertEqual([label for _, label, _ in fc.TURN_CHECKS], [u"Tick all", u"Tick none", u"Tick often doubled"],
                         "the suite's order (owner's images 260, 261): Tick, not Check, all and none first")
        self.assertEqual(dialog.kind(u"9"), fc.FIGURES)
        self.assertTrue(dialog.doubled(u".") and dialog.doubled(u"0") and not dialog.doubled(u"/"))

    def test_the_look_back_counts_in_words(self):
        self.assertEqual([fc.look_back_suffix(n) for n in (0, 1, 2)], [u" glyphs", u" glyph", u" glyphs"])
        dialog = self.dialog(FakeFeatures({}))
        said = []
        dialog.look_back = Anything()
        dialog.look_back.value = 1
        dialog.look_back.setSuffix = said.append
        dialog.look_back_changed(1)
        self.assertEqual(said, [u" glyph"])

        def broken(text):
            raise RuntimeError("no box")
        dialog.look_back.setSuffix = broken
        dialog.look_back_changed(2)  # (a signal's handler must not raise)

    def test_font_units_count_in_words(self):
        """The baseline box read "1 units": its word follows its number, as every text with a number of
        units does (a moved figure form's note, a tabular figure's width)."""
        self.assertEqual([fc.units_suffix(n) for n in (0, 1, 2, -1, -2)],
                         [u" units", u" unit", u" units", u" unit", u" units"])
        self.assertEqual([fc.moved_words(n) for n in (0, 1, 2, -1, -357)],
                         [u"on the baseline", u"raised 1 unit", u"raised 2 units", u"lowered 1 unit",
                          u"lowered 357 units"])
        dialog = self.dialog(FakeFeatures({}))
        said = []
        dialog.small_baseline = Anything()
        dialog.small_baseline.setSuffix = said.append
        for value in (1, 2, -1, 0):
            dialog.small_baseline.value = value
            dialog.show_baseline_suffix()
        self.assertEqual(said, [u" unit", u" units", u" unit", u" units"])

        def broken(text):
            raise RuntimeError("no box")
        dialog.small_baseline.setSuffix = broken
        dialog.show_baseline_suffix()  # (a signal's handler must not raise)
        # A tabular figure 1 unit wide among figures 2 units wide (no font has them: the words still agree)
        info = make_info([], codes=[(name, 0x30 + digit) for digit, name in enumerate(fc.DIGIT_WORDS)],
                         widths=dict((name, 1 if name == u"one" else 2) for name in fc.DIGIT_WORDS))
        sets = {("tab", "lin"): dict((name, name) for name in fc.DIGIT_WORDS)}
        rules = fc.tabular_warnings(info, sets, ("tab", "lin"))
        self.assertEqual([(rule.target, rule.note) for rule in rules],
                         [(u"1 unit wide", u"The default figures are tabular, but one is not 2 units wide like the "
                                           u"others: review it (nothing is changed here)")])

    def test_a_variant_of_an_alternate_takes_turns_with_its_glyph(self):
        """The Stylistic alternates tab builds variants from a glyph's alternates too, named after them
        (W.ss01.alt2, a changed copy of W.ss01): they are in W's turn, and W.ss01 stays the Forms tab's."""
        names = [u"W", u"W.ss01", u"W.alt1", u"W.ss01.alt2", u"W.alt3", u"a", u"a.sc", u"a.sc.alt1", u"x", u"x.ss02.alt1"]
        sets = fc.alternate_sets(names, lambda name: True)
        self.assertEqual(sets, {u"W": [u"W.alt1", u"W.ss01.alt2", u"W.alt3"]},
                         "not a small capital's alternate; not a variant whose alternate the font lacks")
        code = fc.cycle_code(sets, names, look_back=0)
        self.assertIn(u"  sub W W' by W.alt1;", code)
        self.assertIn(u"  sub W.alt1 W' by W.ss01.alt2;", code)
        self.assertIn(u"  sub W.ss01.alt2 W' by W.alt3;", code)
        self.assertIsNone(fc.check_code(u"feature calt {\n%s\n} calt;\n" % u"\n".join(code), names))
        index = fc.forms_index(names)
        self.assertEqual(index.get(u"ss01"), {u"W": u"W.ss01"}, "the set's feature takes W.ss01 alone")
        # The dialog counts the glyphs that may stand before a glyph taking turns in the font's own order
        dialog = self.dialog(FakeFeatures({}))
        self.assertIsNone(dialog.turn_trouble({}))
        self.assertTrue(dialog.cycling(), "the fake font has glyphs taking turns")
        self.assertIsNone(dialog.turn_trouble(dialog.cycling()))
        dialog.names = dialog.names[::2] + dialog.names[1::2]  # (the same glyphs: the count follows their order)
        self.assertIsNone(dialog.turn_trouble(dialog.cycling()), "a small font: room whatever the order")
    def test_busy_takes_no_clicks(self):
        """The window answers events while long work shows its progress: a click then must not start the
        tool again inside itself."""
        features = FakeFeatures({})
        dialog = self.dialog(features)
        dialog.busy = True
        dialog.write()
        self.assertEqual(features.texts, {}, "busy: nothing written")
        rows = len(dialog.forms_tree.items)
        dialog.forms_tree.clear()
        dialog.run()
        self.assertEqual(len(dialog.forms_tree.items), 0, "busy: not read again")
        dialog.busy = False
        dialog.run()
        self.assertEqual(len(dialog.forms_tree.items), rows)
        self.assertFalse(dialog.busy)

    def test_progress_in_the_top_row_reads_stop_writes_do_not(self):
        """progress() processed every event during writes and builds, so a click or a key acted on the font
        while it was being changed; it is the window's top row now (ak.busy_*: owner's image 180), which holds
        them but the tools menu, the arrows, Close, and Esc: those stop a read, and wait for a write."""
        features = FakeFeatures({})
        package, letters = self.big_font(features)
        ak = self.ak
        real = ak.busy_start, ak.busy_progress, ak.busy_end
        started, moved, ended = [], [], []

        def restore():
            ak.busy_start, ak.busy_progress, ak.busy_end = real
        self.addCleanup(restore)
        ak.busy_start = lambda owner, what=u"", stoppable=True: started.append((what, stoppable))
        ak.busy_progress = lambda owner, what=None, part=None, force=False, stoppable=True: moved.append(
            (what, part, stoppable))
        ak.busy_end = lambda owner: ended.append(owner.busy)
        dialog = self.dialog(features, package)
        self.assertEqual((started, ended), ([(u"Reading the font", True)], [False]))
        listed = [part for what, part, _ in moved if what == u"Listing the glyphs with alternates"]
        self.assertTrue(listed and listed == sorted(listed) and 0 < listed[-1] <= 1.0, listed)
        del started[:], moved[:]
        dialog.write()
        self.assertEqual(started, [(u"Writing the code", False), (u"Reading the font", True)],
                         "a write, never stopped half way; then the font read again")
        self.assertTrue(moved and not any(stoppable for _, _, stoppable in moved if _ == u"Writing the code"))
        # A read stopped by the user: nothing listed, nothing to write, and the top line's link reads it again

        def stopping(owner, what=None, part=None, force=False, stoppable=True):
            if what == u"Listing the glyphs with alternates" and stoppable:
                raise ak.Stopped()
        ak.busy_progress = stopping
        dialog.package = None  # (read anew)
        dialog.status = FakeEdit()
        dialog.run()
        self.assertIsNone(dialog.package)
        self.assertEqual((dialog.found, dialog.sets, dialog.forms, dialog.busy), ([], {}, [], False))
        self.assertEqual(len(dialog.alternate_tree.items), 0, "no list half made")
        self.assertIn(u"<a href=\"read:\">", dialog.status.text)
        self.assertEqual(self.logged[-1][0], "warning")
        count = len(started)
        dialog.write()  # (nothing to write: no font read)
        self.assertEqual(len(started), count, "no write started")
        ak.busy_progress = lambda owner, what=None, part=None, force=False, stoppable=True: None
        dialog.link_activated(u"read:")
        self.assertIs(dialog.package, package, "read again")
        self.assertTrue(dialog.sets)

    def test_set_enabled_keeps_the_no_font_gate(self):
        """Owner's images 201 to 210: a control the shared module grayed for want of a font (ak.NO_FONT_PROP)
        stays grayed whatever the tool asks; ak.no_font_states gives it back with a font."""
        button = FakeButton()
        button.property = lambda name: True if name == self.ak.NO_FONT_PROP else None
        button.enabled = False
        fc.set_enabled(button, True)
        self.assertFalse(button.enabled)
        self.assertEqual(fc.NO_FONT_PROP, self.ak.NO_FONT_PROP)
        button.property = lambda name: None
        fc.set_enabled(button, True)
        self.assertTrue(button.enabled)

    def test_empty_notes_take_no_line(self):
        """Owner's images 197 and 198: empty labels under "Figure forms to build" and "Suggested alternates"
        left blank lines: a note is hidden while it says nothing."""
        label = FakeEdit()
        shown = []
        label.setVisible = shown.append
        fc.say(label, u"")
        fc.say(label, u"Something.")
        fc.say(label, u"  ")
        self.assertEqual(shown, [False, True, False])

    def test_a_small_set_starts_checked_whole(self):
        """A font with a few drawn alternates: every letter takes turns, doubled often or not."""
        features = FakeFeatures({})
        package = FakePackage(features)
        for name in (u"H.alt1", u"e.2", u"e.3"):
            glyph = FakeGlyph(name, None)
            package.glyphs.append(glyph)
            package.by_name[name] = glyph
            package.fgPackage.glyphs.append(glyph.fgGlyph)
        dialog = self.dialog(features, package)
        self.look_back(dialog, 2)
        self.assertEqual([row.data(0, USER_ROLE) for row in dialog.alternate_tree.items], [u"e", u"l", u"H"],
                         "ee, then ll, then a letter seldom doubled")
        self.assertEqual(sorted(dialog.cycling()), [u"H", u"e", u"l"])
        dialog.alternate_tree.items[0].setCheckState(0, UNCHECKED)
        dialog.history_moved()
        self.assertEqual(sorted(dialog.cycling()), [u"H", u"l"], "an undo in FontLab: the checks kept")

    # -- the owner's round of 2026-11-13 ------------------------------------------------

    def test_every_row_of_the_forms_list_is_as_high_as_a_row_with_a_picture(self):
        """The Forms list looked crammed beside the window's other lists: a feature's row and its rows
        without a picture ("sups: its alternates (Superscript)") were one line of text high among rows
        as high as their pictures. Every row gets one height, which a picture fits in; a long note
        stays on its row's one line, and its cell's tooltip has it whole, wrapped."""
        self.assertGreaterEqual(fc.ROW_HEIGHT, fc.ICON_SIZE, "a picture fits in the row")
        self.assertLessEqual(fc.ROW_HEIGHT, fc.ICON_SIZE + 6, "and no row is stretched past a picture's")
        dialog = self.dialog(FakeFeatures({}))
        rows = [row for item in dialog.forms_tree.items for row in [item] + item.children]
        self.assertGreater(len(rows), 40)
        self.assertEqual(set(row.hints[0].height for row in rows), set([fc.ROW_HEIGHT]),
                         "feature rows and their rows, with a picture or without: one height")
        aalt = self.section(dialog, "aalt")
        self.assertTrue(aalt.children, "aalt's rows have no picture (a feature has no glyph)")
        note = aalt.text(2)
        self.assertGreater(len(note), 150, "a note longer than its column")
        self.assertNotIn(u"\n", note, "one line in the cell")
        self.assertTrue(aalt.tips[2].startswith(u'<table width="%d"' % fc.TIP_WIDTH), "wrapped at Font Check's width")
        self.assertIn(note.replace(u"&", u"&amp;"), aalt.tips[2], "the whole note in the tooltip")
        for row in rows:  # every note has its tooltip, as rich text (Qt wraps rich text only)
            if row.text(2):
                self.assertTrue(row.tips[2].startswith((u"<span>", u"<table")), row.text(2))
        # A tooltip's text: escaped, short ones as they are, long ones in a cell of the width
        self.assertEqual(fc.tip_html(u"a < b"), u"<span>a &lt; b</span>")
        self.assertEqual(fc.tip_html(u""), u"")
        long_text = u"word " * 40
        self.assertEqual(fc.tip_html(long_text), u'<table width="520" cellspacing="0" cellpadding="0"><tr><td>%s'
                                                 u'</td></tr></table>' % long_text)
        self.assertEqual(fc.tip_html(u"<i>short</i> " + u"<b></b>" * 40, True)[:6], u"<span>", "tags are not counted")
        # The first column has room for an open feature's rows: their indent, check box, and glyph name
        measure = lambda text: 8 * len(text)
        self.assertEqual(fc.form_column_width(20, [u"a", u"asciitilde"], measure), 40 + 24 + 80 + 12)
        self.assertEqual(fc.form_column_width(20, [u"x" * 100], measure), 40 + 24 + fc.FORM_SOURCE_MOST + 12,
                         "a long name does not take the list over")
        self.assertEqual(fc.form_column_width(Anything(), [u"ab"], None), 40 + 24 + 2 * fc.TIP_CHARACTER + 12,
                         "nothing to measure with: a guess")

    def recorded(self, features, package=None, classes=None):
        """A dialog whose controls, labels, lists, and rows are recorded (with its third tab)."""
        del Recorded.made[:]
        del RecordedRow.made[:]
        load = self.ak.load_sibling
        self.ak.load_sibling = lambda file_name, module_name: fa
        try:
            dialog = self.dialog(features, package, dict(RECORDED, QTreeWidget=RecordedTree, QHBoxLayout=RecordedRow,
                                                         **(classes or {})))
        finally:
            self.ak.load_sibling = load
        self.assertIsNotNone(dialog.alternates, "the Stylistic alternates tab is built")
        return dialog

    def test_every_control_answers_with_its_own_whats_this(self):
        """A right-click on Strokes showed another text, over the Suggested button: a widget with no
        What's This answers with its nearest container's, in that container's middle. Every button,
        check box, combo box, spin box, field, and list of the three tabs has its own, every label has
        its field's (or its own), and no two controls of a row share one."""
        dialog = self.recorded(FakeFeatures({"liga": u"feature liga {\n  sub f i by f_i;\n} liga;\n"}))
        controls = [w for w in Recorded.made
                    if isinstance(w, tuple(RECORDED[kind] for kind in CONTROL_KINDS) + (RecordedTree,))]
        kinds = set(type(w).__name__ for w in controls)
        self.assertEqual(kinds, set(CONTROL_KINDS + ("RecordedTree",)), "every kind of control is among them")
        self.assertGreater(len(controls), 30)
        nameless = [(type(w).__name__, getattr(w, "text", u"")) for w in controls if not (u"%s" % w.whats).strip()]
        self.assertEqual(nameless, [], "controls with no What's This of their own")
        labels = [w for w in Recorded.made if isinstance(w, RECORDED["QLabel"])]
        self.assertGreater(len(labels), 20)
        self.assertEqual([w.text for w in labels if not (u"%s" % w.whats).strip()], [], "labels with no What's This")
        is_label = lambda w: isinstance(w, RECORDED["QLabel"])
        rows = [row for row in RecordedRow.made if any(isinstance(w, Recorded) or isinstance(w, RecordedTree)
                                                       for w in row.widgets)]
        self.assertGreater(len(rows), 3)
        for row in rows:
            texts = [w.whats for w in row.widgets if not is_label(w) and hasattr(w, "whats")]
            self.assertEqual(len(texts), len(set(texts)), "two controls of a row share a What's This: %r" % (texts,))
            for at, widget in enumerate(row.widgets):
                if not is_label(widget):
                    continue
                after = row.widgets[at + 1] if at + 1 < len(row.widgets) else None
                if after is not None and not is_label(after) and widget.whats == getattr(after, "whats", None):
                    continue  # a label and its field
                self.assertNotIn(widget.whats, texts, "the label %r has another control's What's This" % widget.text)
        # Strokes: its label and its box answer with its own text, which says it is for every set
        strokes = [w for w in labels if w.text == u"Strokes:"][0]
        self.assertEqual(strokes.whats, dialog.stroke_box.whats)
        self.assertTrue(strokes.whats.startswith(u"For every set, not only the one picked: how thick"))
        self.assertNotEqual(strokes.whats, dialog.small_reset.whats)
        # The splitters hold no What's This for their labels to answer with (their handles do, in FontLab)
        self.assertNotIn(u"Drag the space", u" ".join(u"%s" % w.whats for w in Recorded.made))
        # The ligatures' boxes and the sets' name fields, made as the font is read, have theirs too
        self.assertTrue(dialog.combos and all(u"The feature this ligature goes in" in c.whats for c in dialog.combos))
        self.assertIn(u"The set's name", dialog.name_edits[u"ss01"].whats)

    def test_the_settings_of_the_figure_forms_are_one_row(self):
        """Strokes stood alone under the list, and a sentence beside Suggested said where the suggestion
        came from: Strokes is on the settings row, and the sentence in the button's tooltip and What's
        This."""
        dialog = self.recorded(FakeFeatures({}))
        row = [row for row in RecordedRow.made if dialog.small_set in row.widgets][0]
        self.assertEqual([w.text for w in row.widgets if isinstance(w, RECORDED["QLabel"])],
                         [u"Set:", u"Scale:", u"Baseline:", u"Width:", u"Strokes:"])
        for box in (dialog.small_scale, dialog.small_baseline, dialog.small_width, dialog.small_reset, dialog.stroke_box):
            self.assertIn(box, row.widgets)
        self.assertEqual(row.widgets[-1], dialog.small_reset,
                         "Suggested last, after Strokes, which it puts back too (owner's report 158)")
        self.assertNotIn(dialog.build_button, row.widgets, "the build button stays under the list")
        self.assertFalse(hasattr(dialog, "small_why"), "no sentence beside the button")
        dialog.small_set_picked(fc.SMALL_SETS.index("numr"))
        self.assertEqual(dialog.small_reset.whats,
                         u"Puts the picked set's scale, baseline, and width back as first suggested, and <i>Strokes</i> "
                         u"back at 107% (for every set). This set's suggestion: as most open-licensed fonts.")
        self.assertEqual(dialog.small_reset.tip, u"<table width=\"520\" cellspacing=\"0\" cellpadding=\"0\"><tr><td>%s"
                                                 u"</td></tr></table>" % dialog.small_reset.whats)
        dialog.small_first["sups"]["why"] = u"As the font's 5 drawn forms."  # (what the owner's font said)
        dialog.small_set_picked(fc.SMALL_SETS.index("sups"))
        self.assertTrue(dialog.small_reset.whats.endswith(u"This set's suggestion: as the font's 5 drawn forms."),
                        "the picked set's own")
        self.assertIn(u"as the font's 5 drawn forms.", dialog.small_reset.tip, "on hover too")
        first = u"Puts the picked set's scale, baseline, and width back as first suggested, and <i>Strokes</i> back at 107% " \
                u"(for every set)."
        self.assertEqual([fc.suggested_words(why) for why in (None, u"As the font's 1 drawn form.")],
                         [first, first + u" This set's suggestion: as the font's 1 drawn form."])
        self.assertIn(u"<i>Suggested</i>, after it, puts it back at 107% too.", dialog.stroke_box.whats)
        self.assertIn(u"<i>Strokes</i>, one value for every set", fc.HELP)

    def test_the_build_button_grays_out_when_nothing_is_left_to_build(self):
        """After a build that left nothing to build, Build checked glyphs stayed clickable: its state was
        set while the font was read again, the lists' part disabled meanwhile, through a helper that
        leaves a widget alone when it reports the state asked for (a widget in a disabled container
        reports disabled). The same after an undo, and for the buttons that check the turns. Since the
        owner's round of 2026-11-14 a build leaves what it built listed, and the button clickable (a
        click with nothing changed says so): it grays out only with nothing checked."""
        ContainedButton.container_disabled = False
        dialog = self.dialog(FakeFeatures({}), classes={"QPushButton": ContainedButton, "QSplitter": BusySplitter})
        package = dialog.package
        self.assertEqual(dialog.build_button.text, u"Build 40 ticked figure forms")
        self.assertTrue(dialog.build_button.enabled)
        before = list(package.glyphs)
        dialog.build_small_forms()
        self.assertFalse(ContainedButton.container_disabled, "the lists answer again")
        self.assertEqual(len(dialog.small_tree.items), 4, "what was built is listed again, to replace")
        self.assertEqual(dialog.build_button.text, u"Build ticked figure forms")
        # Owner's report 160: it stayed clickable, and a click only said "Nothing changed since the last build"
        self.assertFalse(dialog.build_button.enabled, "built with these settings: nothing a build would change")
        self.assertTrue(dialog.build_button.whats.endswith(
            u"Grayed out: the 40 figure forms ticked were built here with these very settings, so a build would "
            u"change nothing. Change a setting, or tick other figure forms, to build again."), dialog.build_button.whats)
        self.assertIn(u"Grayed out: the 40 figure forms", dialog.build_button.tip, "on hover too")
        self.assertIn(u"the figure form ticked was built", fc.build_words(0, 1))
        self.assertTrue(fc.build_words(0, 0).endswith(u"Grayed out: no figure form that can be built is ticked."))
        self.assertEqual(fc.build_words(3, 2), fc.BUILD_WHAT, "clickable: what it does only")
        for glyph in [g for g in package.glyphs if g not in before]:  # Edit > Undo in FontLab
            package.deleteGlyph(glyph)
        dialog.history_moved()
        self.assertEqual(dialog.build_button.text, u"Build 40 ticked figure forms")
        self.assertTrue(dialog.build_button.enabled, "the forms are to build again")
        for section in list(dialog.small_tree.items):
            section.setCheckState(0, UNCHECKED)
        self.assertFalse(dialog.build_button.enabled)
        dialog.history_moved()  # (read again with nothing checked: still grayed out)
        self.assertFalse(dialog.build_button.enabled)
        # The turns' buttons are set as the font is read too: None has nothing to uncheck once all are off
        dialog.check_turns("none")
        dialog.history_moved()
        states = dict((key, button.enabled) for (key, _, _), button in zip(fc.TURN_CHECKS, dialog.turn_buttons))
        self.assertFalse(states["none"], "no glyph is checked: nothing to uncheck")
        self.assertTrue(states["all"])

    def strokes_built(self, percent, contour=NodeContour, new_shape=NewShape, shape=NodeShape, prepare=None):
        """The fake font's superiors built with Strokes at percent: (the dialog, the font). new_shape: what
        fontlab.flShape() makes (no_new_shape: FontLab makes none, and the old way is taken); shape: the
        figures' shapes, whose copies the old way writes in; prepare: called with the dialog before."""
        features = FakeFeatures({})
        package = NodePackage(features, contour, shape)
        self.ak.layer_path = lambda layer, *args: NodePath(layer)
        try:
            dialog = self.dialog(features, package, core={"QPointF": FakePoint})
            self.fontlab.flShape = new_shape
            if prepare is not None:
                prepare(dialog)
            for group in ("superscript", "subs", "subscript"):
                self.small_section(dialog, group).setCheckState(0, UNCHECKED)
            self.assertEqual(dialog.build_button.text, u"Build 10 ticked figure forms")
            dialog.stroke_box = Anything()
            dialog.stroke_box.value = percent  # (read as the build starts)
            dialog.build_small_forms()
        finally:
            self.ak.layer_path = fake_path
        self.assertFalse([t for level, t in self.logged if level == "error"], self.logged)
        return dialog, package

    def test_strokes_thickens_what_is_built_by_its_share(self):
        """The owner: whatever the value of Strokes, the built glyphs' thickness did not appear to change,
        while the log said "strokes at 130% of the scaled ones". On a figure that is one stem 80 units
        wide, scaled to 59%: the stem written is 47.2 units at 100% (a component), 1.07 times that at
        107%, and 1.30 times that at 130%, measured on the nodes written."""
        scale = fc.CORPUS_SCALE["sups"]
        scaled = (STEM[1] - STEM[0]) * scale
        self.assertAlmostEqual(scaled, 47.2)
        dialog, package = self.strokes_built(100)
        layer = package.findName(u"two.sups").made[u"Regular"]
        self.assertEqual([c.name for c in layer.components], [u"two"], "100%: a component, scaled")
        self.assertEqual(layer.components[0].transform.args[:4], (scale, 0.0, 0.0, scale))
        self.assertNotIn(("shape", u"two.sups"), package.events, "no outline written")
        done = [t for level, t in self.logged if level == "done"][-1]
        self.assertIn(u"Scaling thins strokes: draw over what was scaled.", done)
        widths = {}
        for percent, moved in ((107, u"1.7"), (130, u"7.1")):
            dialog, package = self.strokes_built(percent)
            for name in (u"two.sups", u"nine.sups"):
                layer = package.findName(name).made[u"Regular"]
                self.assertEqual(layer.components, [], "outlines, not a component")
                self.assertEqual(len(layer.shapes), 1)
                widths[percent] = stem_of(layer)
                self.assertAlmostEqual(widths[percent], scaled * percent / 100.0, delta=0.5,
                                       msg="%s at %d%%: %.2f units" % (name, percent, widths[percent]))
                ys = [n.y for c in layer.shapes[0].contours for n in c.points]
                self.assertAlmostEqual((max(ys) - min(ys)) - 700 * scale, widths[percent] - scaled, delta=1e-6,
                                       msg="the same offset all around: the form grows by it in height too")
            self.assertEqual(package.findName(u"two.sups").made[u"Regular"].advanceWidth,
                             float(int(round(500 * scale * 1.12))), "the planned width")
            self.assertEqual(package.drawn[u"two"].shapes[0].contours[0].box, (100.0, 0.0, 180.0, 700.0),
                             "the figure itself is left as drawn")
            done = [t for level, t in self.logged if level == "done"][-1]
            self.assertIn(u"Made of outlines, strokes at %d%% of the scaled ones (each side moved out %s units): "
                          u'<a href="glyphname:' % (percent, moved), done)
            self.assertEqual(done.count(u'<a href="glyphname:'), 20, "the 10 built and the 10 thickened: links")
            self.assertFalse([t for level, t in self.logged if level == "warning"], self.logged)
        self.assertGreater(widths[107] - scaled, 3.0, "about 3.3 units more at 107%")
        self.assertGreater(widths[130] - widths[107], 10.0, "about 10.9 units more at 130% than at 107%")
        self.assertEqual([fc.offset_words(values) for values in ([], [1.0], [0.5, 1.0], [6.64, 7.58], [2.0, 2.04])],
                         [u"", u" (each side moved out 1 unit)", u" (each side moved out 0.5 to 1 unit)",
                          u" (each side moved out 6.6 to 7.6 units)", u" (each side moved out 2 units)"])

    def test_settings_typed_and_not_entered_are_built(self):
        """Owner's report: 100 typed in Strokes over 130, then Build without Enter, built at 130. The build
        reads every box as it starts: a scale typed (no valueChanged yet) and Strokes."""
        dialog = self.recorded(FakeFeatures({}))
        package = dialog.package
        for group in ("superscript", "subs", "subscript"):
            self.small_section(dialog, group).setCheckState(0, UNCHECKED)
        dialog.small_clicked(self.small_section(dialog, "sups").child(2), 0)
        self.assertEqual(dialog.small_scale.value, 59)
        dialog.small_scale.value = 50  # (typed: the box shows it, no signal came)
        dialog.stroke_box.value = 100  # (components: the scale read from their transform)
        dialog.build_small_forms()
        layer = package.findName(u"two.sups").made[u"Regular"]
        self.assertEqual(layer.components[0].transform.args[:4], (0.5, 0.0, 0.0, 0.5), "built at the 50% shown")
        self.assertEqual(dialog.small_setup["sups"]["scale"], 0.5, "the setting follows the box")

    def test_strokes_that_cannot_apply_are_said(self):
        """Owner's report 156: Strokes at 100% and 130% built the same glyphs, and the log said only "Scaling
        thins strokes": where the figures' stroke cannot be measured (or a figure is made of components),
        the forms are made of components, scaled, and the log says so, with why."""
        def unmeasured(dialog):
            dialog.figure_stem = lambda package, master: None
        dialog, package = self.strokes_built(130, prepare=unmeasured)
        layer = package.findName(u"two.sups").made[u"Regular"]
        self.assertEqual([c.name for c in layer.components], [u"two"], "components, scaled")
        warnings = [t for level, t in self.logged if level == "warning"]
        self.assertEqual(len(warnings), 1, self.logged)
        self.assertTrue(warnings[0].startswith(u"<i>Strokes</i> at 130% could not thicken <b>10 glyphs</b>: "
                                               u'<a href="glyphname:'), warnings[0])
        self.assertTrue(warnings[0].endswith(u"They are made of components, scaled (their strokes thinned), because "
                                             u"the figures' stroke could not be measured."), warnings[0])
        dialog, package = self.strokes_built(130)
        self.assertFalse([t for level, t in self.logged if level == "warning"], "thickened: nothing to say")

    def test_strokes_fontlab_did_not_keep_are_said_not_assumed(self):
        """Where the nodes read back after the build are not where they were put (their contour gave
        copies of its nodes: what FontLab does with a node's x and y set from a script was never looked
        at live), the log says so, and does not say the strokes are at 130%."""
        dialog, package = self.strokes_built(130, DroppingContour)
        layer = package.findName(u"two.sups").made[u"Regular"]
        self.assertAlmostEqual(stem_of(layer), (STEM[1] - STEM[0]) * fc.CORPUS_SCALE["sups"], msg="as scaled")
        done = [t for level, t in self.logged if level == "done"][-1]
        self.assertIn(u"Built <b>10 glyphs</b>", done)
        self.assertNotIn(u"strokes at 130%", done)
        warnings = [t for level, t in self.logged if level == "warning"]
        self.assertEqual(len(warnings), 1, self.logged)
        self.assertTrue(warnings[0].startswith(u"FontLab did not keep the thicker strokes of <b>10 glyphs</b>: "
                                               u'<a href="glyphname:'), warnings[0])
        # (each count bold with its noun; a number whose noun is outside, bold alone: owner's images 297, 301)
        self.assertTrue(warnings[0].endswith(u"Read back, their outlines were as scaled (<b>40 nodes</b> in <b>10 "
                                             u"contours</b>, <b>40</b> on-curve, <b>40</b> given a new place, <b>0</b> "
                                             u"found there): draw over them."), warnings[0])
        self.assertEqual(warnings[0].count(u'<a href="glyphname:'), 10)
        # The same where no node reads as an on-curve one (none is moved): the counts say where it stopped
        dialog, package = self.strokes_built(130, OddContour)
        warnings = [t for level, t in self.logged if level == "warning"]
        self.assertEqual(len(warnings), 1, self.logged)
        self.assertIn(u"(40 nodes in 10 contours, 0 on-curve, 0 given a new place, 0 found there)",
                      MARKUP.sub(u"", warnings[0]))
        self.assertNotIn(u"strokes at 130%", [t for level, t in self.logged if level == "done"][-1])

    # -- the owner's round of 2026-11-14 ------------------------------------------------

    def test_strokes_are_drawn_where_their_nodes_are(self):
        """The owner, of Strokes at 130%: "I still see no visible difference", while the log said the
        strokes were thickened and the nodes read back where they were put. FontLab keeps a node's x
        and y set from a script, but the shape it draws (its box) did not follow them (seen live). The
        fakes' shapes draw what they held when made, transformed, given contours, or updated: the
        outline is now written as contours placed before a new shape takes them, and checked on what
        the shape draws."""
        scaled = (STEM[1] - STEM[0]) * fc.CORPUS_SCALE["sups"]
        dialog, package = self.strokes_built(130)
        shape = package.findName(u"two.sups").made[u"Regular"].shapes[0]
        self.assertIsInstance(shape, NewShape, "a new shape, given its contours with their nodes in place")
        self.assertEqual(shape.notified, [True])
        self.assertGreaterEqual(shape.updates, 1, "told to draw them anew")
        self.assertAlmostEqual(shape.drawn[2] - shape.drawn[0], scaled * 1.3, delta=0.5, msg="drawn as thick")
        self.assertEqual(package.drawn[u"two"].shapes[0].contours[0].box, (100.0, 0.0, 180.0, 700.0),
                         "the figure's own contours left as drawn (clones were moved)")
        self.assertIn(u"strokes at 130% of the scaled ones", [t for level, t in self.logged if level == "done"][-1])
        self.assertFalse([t for level, t in self.logged if level == "warning"], self.logged)
        # Where FontLab makes no shape from a script: the old way, a copy whose nodes are moved, then updated
        dialog, package = self.strokes_built(130, new_shape=no_new_shape)
        shape = package.findName(u"two.sups").made[u"Regular"].shapes[0]
        self.assertNotIsInstance(shape, NewShape)
        self.assertGreaterEqual(shape.updates, 1)
        self.assertAlmostEqual(shape.drawn[2] - shape.drawn[0], scaled * 1.3, delta=0.5, msg="drawn as thick")
        self.assertIn(u"strokes at 130% of the scaled ones", [t for level, t in self.logged if level == "done"][-1])
        # A shape that draws what it drew whatever its nodes (the case the owner saw): said, not assumed
        dialog, package = self.strokes_built(130, new_shape=no_new_shape, shape=StaleShape)
        done = [t for level, t in self.logged if level == "done"][-1]
        self.assertNotIn(u"strokes at 130%", done)
        warnings = [t for level, t in self.logged if level == "warning"]
        self.assertEqual(len(warnings), 1, self.logged)
        self.assertTrue(MARKUP.sub(u"", warnings[0]).endswith(
            u"(40 nodes in 10 contours, 40 on-curve, 40 given a new place, 40 found there, 10 shapes drawn as before): "
            u"draw over them."), warnings[0])
        self.assertIn(u"<b>10 shapes</b> drawn as before", warnings[0])

    def test_a_layer_built_again_measures_itself_again(self):
        """Live (IBM Plex Sans JP): zero.sups built again at 130% and 160% had its new shape's box grow,
        while the layer's own box, what FontLab measures and draws, stayed the 100% one until the layer
        was updated."""
        dialog, package = self.strokes_built(130)
        events = [event for event in package.events if event[1] == u"two.sups"]
        self.assertIn(("measured", u"two.sups"), events)
        self.assertLess(events.index(("shape", u"two.sups")), events.index(("measured", u"two.sups")),
                        "once its shapes are written")

    def test_forms_made_from_a_form_built_again_are_built_again(self):
        """Live: uni2070, a component of zero.sups, kept zero.sups' 100% outline after zero.sups was built
        again at 130% and 160% (it was "left as it was": its own plan had not changed)."""
        features = FakeFeatures({})
        package = NodePackage(features, NodeContour, NodeShape)
        self.ak.layer_path = lambda layer, *args: NodePath(layer)
        try:
            dialog = self.dialog(features, package, core={"QPointF": FakePoint})
            self.fontlab.flShape = NewShape
            for group in ("subs", "subscript"):
                self.small_section(dialog, group).setCheckState(0, UNCHECKED)
            copies = [form.name for form in dialog.small_forms if form.group == "superscript"
                      and getattr(dialog.small_plans.get(form.name), "how", None) == "copied"]
            self.assertTrue(copies, "the superscripts copy the sups")
            dialog.stroke_box = Anything()
            dialog.stroke_box.value = 100
            dialog.build_small_forms()
            del package.events[:]
            dialog.stroke_box.value = 130
            dialog.build_small_forms()
        finally:
            self.ak.layer_path = fake_path
        emptied = set(name for kind, name in package.events if kind == "emptied")
        self.assertTrue(set(copies) <= emptied, "the copies built again with what they copy")
        self.assertNotIn(u"left as it was", [t for level, t in self.logged if level == "done"][-1])

    def test_dependent_forms(self):
        class Plan(object):
            def __init__(self, *parts):
                self.parts = [(part, 1.0, 1.0, 0, 0) for part in parts]

        class Named(object):
            def __init__(self, name):
                self.name = name

        forms = [Named(n) for n in (u"zero.sups", u"uni2070", u"uni2070.alt", u"one.sups", u"uni00B9")]
        plans = {u"zero.sups": Plan(u"zero"), u"uni2070": Plan(u"zero.sups"), u"uni2070.alt": Plan(u"uni2070"),
                 u"one.sups": Plan(u"one"), u"uni00B9": Plan(u"one.sups")}
        ours = {u"zero.sups": 1, u"uni2070": 1, u"uni2070.alt": 1, u"uni00B9": 1}
        self.assertEqual(fc.dependent_forms(forms, plans, ours, [u"zero.sups"]), [u"uni2070", u"uni2070.alt"],
                         "at any depth")
        self.assertEqual(fc.dependent_forms(forms, plans, {u"zero.sups": 1}, [u"zero.sups"]), [],
                         "only what this window built (a glyph of the font's is never replaced)")
        self.assertEqual(fc.dependent_forms(forms, plans, ours, [u"one.sups"]), [u"uni00B9"])

    def test_the_picture_of_a_form_to_build_shows_its_strokes(self):
        """The pictures of the forms to build were the scaled figure whatever Strokes said: drawn with a
        pen as wide as both sides' offset, they grow as the build does, and Strokes draws them again."""
        widths = []

        class Pen(Anything):
            def __init__(self, *args):
                self.width = None

            def setWidthF(self, width):
                self.width = width

        class Painter(Anything):
            def strokePath(self, path, pen):
                widths.append(pen.width)

        features = FakeFeatures({})
        package = NodePackage(features)
        self.ak.layer_path = lambda layer, *args: NodePath(layer)
        try:
            dialog = self.dialog(features, package, {"QPen": Pen, "QPainter": Painter}, core={"QPointF": FakePoint})
            dialog.stroke_box = Anything()
            dialog.stroke_box.value = 130
            self.assertIsNotNone(dialog.planned_picture(dialog.small_form(u"two.sups")))
            self.assertEqual(len(widths), 1)
            self.assertAlmostEqual(widths[0], 2 * 7.08, delta=0.15, msg="7.08 units a side (80 at 59%, 30% more; "
                                                                         "the stem measured to half a unit)")
            dialog.stroke_box.value = 100
            dialog.planned_picture(dialog.small_form(u"two.sups"))
            self.assertEqual(len(widths), 1, "at 100%: components, no pen")
        finally:
            self.ak.layer_path = fake_path
        replanned = []
        dialog = self.recorded(FakeFeatures({}))
        dialog.replan = lambda: replanned.append(True)
        dialog.stroke_box.slots["valueChanged(int)"][0](130)
        self.assertEqual(replanned, [True], "Strokes plans again: the pictures and the count follow")

    def test_a_build_replaces_what_it_built_and_nothing_else(self):
        """The owner: the build button "should just remain visible and simply replace the previously-created
        glyphs (if values changed or new features were ticked)". What this window built stays listed while
        nobody changes it; a build with other settings makes it again in place, as one step of the
        History; with nothing changed it says so and builds nothing; a glyph drawn over since is left."""
        dialog = self.dialog(FakeFeatures({}))
        package = dialog.package
        for group in ("superscript", "subs", "subscript"):
            self.small_section(dialog, group).setCheckState(0, UNCHECKED)
        dialog.build_small_forms()
        steps, count = len(self.fontlab.flItems.steps), len(package.glyphs)
        self.assertEqual(steps, 2, "the font as it was (its first write), then the build")
        self.assertEqual(len(dialog.small_ours), 10)
        self.assertEqual(self.small_section(dialog, "sups").childCount(), 10, "listed again")
        self.assertIn(fc.BUILT_NOTE, self.small_section(dialog, "sups").child(2).text(2))
        self.assertFalse(dialog.build_button.enabled, "grayed out: nothing that a build would change")
        self.assertEqual(dialog.build_button.text, u"Build ticked figure forms", "nothing that a build would change")
        # Nothing changed (were it clicked all the same): said, nothing built, no step
        dialog.build_small_forms()
        self.assertEqual(len(self.fontlab.flItems.steps), steps)
        self.assertTrue(self.logged[-1][1].startswith(u"Nothing changed since the last build"), self.logged[-1])
        # A setting changed: made again in place, the same glyphs, as one more step
        dialog.small_clicked(self.small_section(dialog, "sups").child(2), 0)
        dialog.small_setting("scale", 50)
        self.assertEqual(dialog.build_button.text, u"Build 10 ticked figure forms")
        two = package.findName(u"two.sups")
        dialog.build_small_forms()
        self.assertEqual(len(self.fontlab.flItems.steps), steps + 1, "one step of the History")
        self.assertEqual(len(package.glyphs), count, "no glyph added")
        self.assertIs(package.findName(u"two.sups"), two, "the same glyph, its layers made anew")
        self.assertIn(("emptied", u"two.sups"), package.events)
        self.assertEqual(two.made[u"Regular"].components[0].transform.args[:4], (0.5, 0.0, 0.0, 0.5))
        done = [t for level, t in self.logged if level == "done"][-1]
        self.assertTrue(done.startswith(u"Replaced <b>10 glyphs</b> built here before, with the settings shown: "),
                        done)
        self.assertNotIn(u"Built <b>", done)
        self.assertEqual(done.count(u'<a href="glyphname:'), 10)
        self.assertFalse([t for level, t in self.logged if level in ("error", "warning")], self.logged)
        # Drawn over since: the user's, no longer listed, never replaced
        two.made[u"Regular"].advanceWidth = 999
        dialog.history_moved()
        self.assertNotIn(u"two.sups", dialog.small_ours)
        self.assertEqual(len(dialog.small_ours), 9)
        self.assertNotIn(u"two.sups", [row.text(0) for row in self.small_section(dialog, "sups").children])
        dialog.small_setting("scale", 55)
        dialog.build_small_forms()
        self.assertEqual(two.made[u"Regular"].advanceWidth, 999, "left as the user made it")
        self.assertEqual(two.made[u"Regular"].components[0].transform.args[:4], (0.5, 0.0, 0.0, 0.5))
        self.assertIn(u"Replaced <b>9 glyphs</b>", [t for level, t in self.logged if level == "done"][-1])
        # Undone in FontLab (the glyphs gone): a build makes them anew
        for name in list(dialog.small_ours):
            package.deleteGlyph(package.findName(name))
        dialog.history_moved()
        self.assertEqual(dialog.small_ours, {})
        self.assertEqual(dialog.build_button.text, u"Build 9 ticked figure forms")
        self.assertEqual(fc.plan_signature(None, 107), None)
        self.assertEqual(fc.layer_print(two.made[u"Regular"])[0], 999)

    def test_the_code_part_is_named_code_preview_and_colored(self):
        """The owner: "it should just be 'Code'; also, syntax highlighting would be neat." Then (owner's
        image 299): "Code preview", so people understand they still have to write it. The heading reads
        Code preview, everywhere the part is named; the box is colored by a highlighter whose colors follow
        the palette, shown plain past HIGHLIGHT_LINES lines (each click makes the code again, and Qt colors
        every line again); where PythonQt cannot make the highlighter, the box stays plain."""
        dialog = self.recorded(FakeFeatures({}), classes={"QTabBar": type("QTabBar", (Recorded,), {})})
        texts = [w.text for w in Recorded.made if isinstance(w, RECORDED["QLabel"])]
        self.assertEqual(fc.CODE_HEADING, u"Code preview")
        self.assertIn(u"Code preview", texts)
        self.assertNotIn(u"Code", texts)
        self.assertNotIn(u"The code", texts)
        self.assertIn(u"<i>Code preview</i>, under them", dialog.tabs.whats)
        self.assertIn(u"in <i>Code preview</i>", fc.HELP)
        self.assertNotIn(u"<i>Code</i>", fc.HELP)

        class Highlighter(Anything):
            def __init__(self, parent):  # (as PythonQt makes it: a QObject parent, no document colored)
                self.document, self.formats, self.state, self.previous, self.colored = None, [], 0, -1, 0

            def setFormat(self, start, length, made):
                self.formats.append((start, length, made.brush.color.rgb))

            def previousBlockState(self):
                return self.previous

            def setCurrentBlockState(self, state):
                self.state = state

            def setDocument(self, document):
                self.document = document

            def rehighlight(self):
                self.colored += 1

        class CharFormat(Anything):
            def setForeground(self, brush):
                self.brush = brush

        class Color(Anything):
            def __init__(self, *rgb):
                self.rgb = rgb

        class Brush(Anything):
            def __init__(self, color):
                self.color = color

        dialog = self.dialog(FakeFeatures({}), classes={"QSyntaxHighlighter": Highlighter, "QTextCharFormat": CharFormat,
                                                        "QColor": Color, "QBrush": Brush})
        highlighter = dialog.highlighting.highlighter
        self.assertIsInstance(highlighter, Highlighter)
        self.assertIs(highlighter.document, dialog.highlighting.document,
                      "set on the document itself: PythonQt's QObject parent colored nothing, live")
        highlighter.highlightBlock(u"feature liga { # FreeLab")
        light = lambda kind: fc.fea_color(kind, False)
        self.assertEqual(highlighter.formats, [(0, 7, light("keyword")), (8, 4, light("tag")),
                                               (15, 9, light("comment"))])
        del highlighter.formats[:]
        highlighter.highlightBlock(u"@x = [a b")
        self.assertEqual(highlighter.state, 1, "a list open at the line's end")
        highlighter.previous = 1
        highlighter.highlightBlock(u"c];")
        self.assertEqual(highlighter.formats[-1], (0, 2, light("list")))
        self.assertEqual(highlighter.state, 0)
        # Dark mode switched: the colors read from the palette again, and the code colored again

        class Dark(object):
            def color(self, role):
                shade = Anything()
                shade.lightness = lambda: 40
                return shade

        dialog.code.palette = Dark()
        dialog.highlighting.refresh()
        self.assertEqual(highlighter.colored, 1)
        del highlighter.formats[:]
        highlighter.previous = 0  # (no list open on the line before)
        highlighter.highlightBlock(u"sub a by b;")
        self.assertEqual(highlighter.formats[0][2], fc.fea_color("keyword", True))
        # Long code shown plain; short code colored again
        document = highlighter.document
        dialog.show_code(u"\n".join([u"sub a by b;"] * (fc.HIGHLIGHT_LINES + 1)))
        self.assertIsNone(highlighter.document)
        self.assertFalse(dialog.highlighting.attached)
        dialog.show_code(u"sub a by b;")
        self.assertIs(highlighter.document, document)
        self.assertTrue(dialog.highlighting.attached)
        # A highlighter that cannot be made: the box stays plain, and the code is shown

        class Broken(Anything):
            def __init__(self, *args):
                raise TypeError("PythonQt cannot make it")

        dialog = self.dialog(FakeFeatures({}), classes={"QSyntaxHighlighter": Broken})
        self.assertIsNone(dialog.highlighting)
        self.assertIn(u"feature", dialog.code_text)

    def test_alternates_that_take_turns_say_where_they_are_built(self):
        """The owner: "some kind of indication in the 'Alternates that take turns' section that such
        alternates need to be built in 'Stylistic alternates' when there are none". The section says so,
        naming the tab as it is named, a link that opens it; the look back and the check buttons, which
        have nothing to act on, are grayed out."""
        features = FakeFeatures({})
        package = FakePackage(features)
        package.glyphs = [g for g in package.glyphs if g.name != u"l.2"]
        package.by_name.pop(u"l.2")
        package.fgPackage.glyphs = [g.fgGlyph for g in package.glyphs]
        tabs = type("QTabBar", (Recorded,), {})
        dialog = self.recorded(features, package, {"QTabBar": tabs, "QStackedWidget": type("Stack", (Recorded,), {})})
        self.assertEqual(dialog.sets, {})
        self.assertEqual(dialog.turn_label.text, fc.NO_TURNS)
        self.assertIn(u'on the <a href="tab:2"><i>Stylistic alternates</i></a> tab', fc.NO_TURNS)
        self.assertEqual(fc.TABS[fc.STYLISTIC_TAB], u"Stylistic alternates")
        self.assertFalse(dialog.look_back.enabled)
        self.assertEqual([button.enabled for button in dialog.turn_buttons], [False, False, False])
        dialog.turn_label.slots["linkActivated(QString)"][0](u"tab:2")
        self.assertEqual((dialog.tabs.currentIndex, dialog.pages.currentIndex), (2, 2))
        dialog.link_activated(u"elsewhere")  # (any other link: nothing, and nothing raised)
        # With alternates, the line says how they take turns, and the look back can be set
        dialog = self.recorded(FakeFeatures({}))
        self.assertNotIn(u"Stylistic alternates", dialog.turn_label.text)
        self.assertTrue(dialog.look_back.enabled)

    def test_with_no_font_nothing_acts_and_the_window_follows_the_fonts(self):
        """The owner: audit "what currently remains clickable or visible when there's nothing loaded".
        With no font, no control that acts on a font takes a click on any of the three tabs, and nothing
        of the font closed stays shown (its code, its lists); the window takes the next font opened
        (the shared module calls font_changed), read as at the window's opening."""
        dialog = self.recorded(FakeFeatures({"liga": u"feature liga {\n  sub f i by f_i;\n} liga;\n"}))
        workspace = self.fontlab.flWorkspace.instance()
        self.assertTrue(dialog.code_text)
        self.assertTrue(dialog.small_set.enabled and dialog.stroke_box.enabled, "forms to build: settings to set")
        self.assertFalse(dialog.small_reset.enabled, "the picked set as suggested: nothing to put back")
        dialog.small_setting("scale", 50)
        self.assertTrue(dialog.small_reset.enabled)
        dialog.small_suggested()
        self.assertFalse(dialog.small_reset.enabled)
        # Owner's report 158: changing Strokes left Suggested grayed out; it puts Strokes back now
        dialog.stroke_box.setValue(130)
        dialog.stroke_box.slots["valueChanged(int)"][0](130)
        self.assertTrue(dialog.small_reset.enabled, "Strokes changed: something to put back")
        dialog.small_suggested()
        self.assertEqual(dialog.stroke_box.value, fc.STROKE_WEIGHT)
        self.assertFalse(dialog.small_reset.enabled)
        empty = Anything()
        empty.packages = lambda: []
        self.fontlab.flWorkspace.instance = lambda: empty
        dialog.font_changed()
        self.assertIsNone(dialog.package)
        # (the top line says so, over the header's separator; no status line under it: convention 1)
        self.assertEqual(dialog.top_line.text, self.ak.sentences(self.ak.NO_FONT_LINE))
        self.assertEqual(dialog.status.text, u"")
        self.assertEqual(dialog.code_text, u"")
        self.assertEqual(dialog.turn_label.text, u"")
        for tree in (dialog.ligature_tree, dialog.alternate_tree, dialog.forms_tree, dialog.small_tree):
            self.assertEqual(tree.items, [])
        page = dialog.alternates
        self.assertEqual(page.tree.items, [])
        grayed = [dialog.look_back, dialog.write_button, dialog.restore_button, dialog.build_button,
                  dialog.small_set, dialog.small_scale, dialog.small_baseline, dialog.small_width,
                  dialog.small_reset, dialog.stroke_box, page.all_button, page.none_button, page.copy_button,
                  page.scope_box, page.letters_edit, page.count_box, page.strength_box, page.seed_box,
                  page.designs_box, page.build_button] + list(dialog.turn_buttons)
        self.assertEqual([getattr(w, "text", u"") for w in grayed if w.enabled], [], "clickable with no font")
        self.assertEqual(page.note.text, u"")
        # A font opened: read as when the window opens
        self.fontlab.flWorkspace.instance = lambda: workspace
        dialog.font_changed()
        self.assertIsNotNone(dialog.package)
        self.assertTrue(dialog.forms_tree.items and dialog.ligature_tree.items and page.tree.items is not None)
        self.assertTrue(dialog.code_text)
        self.assertTrue(dialog.look_back.enabled and dialog.small_set.enabled)
        # Called from a timer: nothing escapes

        def broken():
            raise RuntimeError("no font to read")
        dialog.read_font = broken
        dialog.font_changed()
        self.assertFalse(dialog.busy)
        self.assertTrue(self.logged[-1][1].startswith(u"The font could not be read"), self.logged[-1])


    # -- the owner's round of 2026-11-17 (images 212 to 282) --------------------------------

    def with_lines(self, features):
        """A recorded dialog whose separators are recorded too (each a Recorded, header and vertical kept)."""
        separator = self.ak.separator

        def line(header=False, vertical=False):
            made = Recorded()
            made.header, made.vertical = header, vertical
            return made
        self.ak.separator = line
        try:
            return self.recorded(features)
        finally:
            self.ak.separator = separator

    def test_the_header_names_the_font_over_the_status_and_its_separator(self):
        """Owner's images 217, 222, 223, 224: the window started with its tab bar (the busy bar ran into it),
        and its first line mixed the font's name with the counts. The top line names the font and its
        master (ak.font_named), the status lines under it, then the header's separator, then the tabs; a
        heading that follows a list or previews has a line over it (image 234), and the two previews a line
        between them (image 269)."""
        dialog = self.with_lines(FakeFeatures({"liga": u"feature liga {\n  sub f i by f_i;\n} liga;\n"}))
        made = Recorded.made
        is_line = lambda w: isinstance(w, Recorded) and "header" in w.__dict__
        lines = [w for w in made if is_line(w)]
        self.assertTrue(lines[0].header and not any(line.header for line in lines[1:]), "one header separator, first")
        self.assertLess(made.index(dialog.top_line), made.index(dialog.status))
        self.assertLess(made.index(dialog.status), made.index(lines[0]))
        self.assertEqual(dialog.top_line.text, self.ak.sentences(self.ak.font_named(u"Fake", u"Regular", 1)))
        self.assertNotIn(u"Fake", dialog.status.text, "the font is named once, in the top line")
        self.assertIn(u"Forms: <b>12 of 12 form features</b> ticked (", dialog.status.text)
        # (a number inside the parentheses, its noun outside them, bold alone: owner's images 297 and 301)
        self.assertIn(u"<b>1 ligature</b> (<b>1</b> standard, <b>0</b> discretionary, <b>0</b> off)", dialog.status.text)
        labels = [w for w in made if isinstance(w, RECORDED["QLabel"])]
        for heading in (u"Alternates that take turns", u"Figure forms to build", u"Code preview",
                        u"Variants that take turns"):
            label = [w for w in labels if w.text == heading][0]
            before = made[made.index(label) - 1]
            self.assertTrue(is_line(before) and not before.header, "a line over %s" % heading)
        self.assertEqual(len([line for line in lines if line.vertical]), 1, "a line between the two previews")
        self.assertNotIn(u"Variants that take turns (handwriting)", [w.text for w in labels], "owner's image 244")
        # A read stopped: the top line still names the font (image 224)
        dialog.read_stopped()
        self.assertEqual(dialog.top_line.text, self.ak.sentences(self.ak.font_named(u"Fake", u"Regular", 1)))
        self.assertIn(u"Reading the font was stopped", dialog.status.text)

    def test_the_bottom_row_holds_the_shown_tabs_buttons(self):
        """Owner's images 258, 260, 264: the turns' Check buttons stood over their list, the figure forms'
        build between the list and its splitter handle, the third tab's under its list. Every tick and build
        button is in the window's bottom row, those of the tab shown visible: Tick buttons at the left, then
        Restore suggestions; Compile after writing, the builds, Update the code, and Close at the right."""
        dialog = self.recorded(FakeFeatures({}))
        page = dialog.alternates
        row = [r for r in RecordedRow.made if dialog.close_button in r.widgets][0]
        # (owner's image 298: the write button right after Compile after writing, the tick that is about it)
        self.assertEqual(row.widgets, list(dialog.turn_buttons) + [page.all_button, page.none_button, dialog.restore_button,
                                                                   dialog.compile_box, dialog.write_button,
                                                                   dialog.build_button, page.copy_button,
                                                                   page.build_button, dialog.close_button])
        self.assertEqual([button.text for button in dialog.turn_buttons],
                         [u"Tick all", u"Tick none", u"Tick often doubled"])
        moved = list(dialog.turn_buttons) + [dialog.build_button, page.build_button, page.copy_button, page.all_button]
        self.assertEqual([r for r in RecordedRow.made if r is not row and any(w in r.widgets for w in moved)], [],
                         "no tick or build button left in a tab")
        tabs = (list(dialog.turn_buttons), [dialog.build_button], [page.all_button, page.none_button, page.copy_button,
                                                                    page.build_button])
        for index in (0, 1, 2, 0):
            dialog.switch_page(index)
            for number, buttons in enumerate(tabs):
                self.assertEqual([button.visible for button in buttons], [number == index] * len(buttons), (index, number))
        left, right = dialog.tab_buttons()
        shifted = [button for buttons in left + right for button in buttons]
        self.assertEqual([w for w in (dialog.restore_button, dialog.compile_box, dialog.write_button, dialog.close_button)
                          if w in shifted], [], "the window's own buttons stay whatever the tab")
        self.assertEqual(fc.build_label(62), u"Build 62 ticked figure forms", "named for its section (owner's image 258)")
        self.assertIsNotNone(page.parts, "the third tab's two parts share a splitter, as the other tabs' (image 259)")

    def test_the_ligatures_boxes_are_set_once_their_columns_are_sized(self):
        """Owner's image 221: while the forms were read, the Feature column's boxes stood over the Replaces
        column. Each box is placed where its cell is when it is set, and the columns were sized after: the
        rows come first, the columns are sized, then the boxes are set and the list laid out at once, its
        rows hidden meanwhile (ak.quiet_list)."""
        events = []

        class Viewport(Anything):
            def setVisible(self, on):
                events.append(("rows shown", self.tree, on))

        class OrderedTree(FakeTree):
            def resizeColumnToContents(self, column):
                events.append(("sized", id(self), column))

            def setItemWidget(self, item, column, widget):
                FakeTree.setItemWidget(self, item, column, widget)
                events.append(("box", id(self)))

            def doItemsLayout(self):
                events.append(("laid out", id(self)))

            def viewport(self):
                viewport = Viewport()
                viewport.tree = id(self)
                return viewport

        features = FakeFeatures({"liga": u"feature liga {\n  sub f i by f_i;\n} liga;\n"})
        dialog = self.dialog(features, self.with_glyphs(features, [u"f_l", u"f_f"]), {"QTreeWidget": OrderedTree})
        tree = id(dialog.ligature_tree)
        self.assertTrue(dialog.combos)
        mine = [event for event in events if event[1] == tree]
        mine = mine[mine.index(("rows shown", tree, False)):]
        boxes = [at for at, event in enumerate(mine) if event[0] == "box"]
        sized = [at for at, event in enumerate(mine) if event[0] == "sized"]
        self.assertTrue(sized and boxes and max(sized) < min(boxes), "the columns sized before any box is set")
        laid = [at for at, event in enumerate(mine) if event[0] == "laid out"]
        self.assertTrue(laid and laid[0] > max(boxes), "laid out once the boxes are in")
        shown = mine.index(("rows shown", tree, True))
        self.assertGreater(shown, laid[0], "the rows shown again once the boxes are in place")
        self.assertTrue(fc.place_cell_widgets(OrderedTree()))
        self.assertFalse(fc.place_cell_widgets(object()), "a list that cannot be laid out: said, nothing raised")


MARKUP = re.compile(u"</?[A-Za-z]+>|&[a-z]+;")


def classes_of(code):
    """{class name: the set of its glyphs} of feature code's class definitions, on one line or wrapped."""
    return dict((name, set(glyphs.split())) for name, glyphs in re.findall(r"@(\w+) = \[([^\]]*)\];", code))


def turn_font(letters, variants, extra=()):
    """A font (fontTools) of the letters (glyph names; a letter's own, or uniXXXX), each with its variants
    (X.alt1...), a space, and a period; then the extra glyphs (names, no characters)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    cmap = dict((int(name[3:], 16) if name.startswith("uni") else ord(name), name) for name in letters)
    cmap.update({0x20: "space", 0x2E: "period"})
    order = [".notdef", "space", "period"] + list(letters)
    order += ["%s.alt%d" % (ch, n) for ch in letters for n in range(1, variants.get(ch, 0) + 1)]
    have = set(order)
    order += [name for name in extra if name not in have]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(dict((name, TTGlyphPen(None).glyph()) for name in order))
    builder.setupHorizontalMetrics(dict((name, (500, 0)) for name in order))
    builder.setupHorizontalHeader()
    builder.setupNameTable({"familyName": "Turns", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font, order


def apply_lookup(gsub, index, glyphs, at=None):
    """GSUB applied as a shaper does, for the tables these rules compile to: single substitutions and
    chaining contexts (format 3, coverages; format 1, glyphs)."""
    lookup = gsub.LookupList.Lookup[index]
    subtables = [sub.ExtSubTable if lookup.LookupType == 7 else sub for sub in lookup.SubTable]
    for i in (range(len(glyphs)) if at is None else [at]):
        for sub in subtables:
            kind = type(sub).__name__
            if kind == "SingleSubst":
                if glyphs[i] in sub.mapping:
                    glyphs[i] = sub.mapping[glyphs[i]]
                    break
                continue
            if kind != "ChainContextSubst" or sub.Format not in (1, 3):
                raise ValueError("a table this test does not read: %s %s" % (kind, getattr(sub, "Format", None)))
            if sub.Format == 3:
                rules = [([c.glyphs for c in sub.BacktrackCoverage], [c.glyphs for c in sub.InputCoverage],
                          [c.glyphs for c in sub.LookAheadCoverage], sub.SubstLookupRecord)]
            elif glyphs[i] in sub.Coverage.glyphs:
                rules = [([[g] for g in rule.Backtrack], [[glyphs[i]]] + [[g] for g in rule.Input],
                          [[g] for g in rule.LookAhead], rule.SubstLookupRecord)
                         for rule in sub.ChainSubRuleSet[sub.Coverage.glyphs.index(glyphs[i])].ChainSubRule]
            else:
                rules = []
            matched = False
            for back, inputs, ahead, records in rules:
                if i - len(back) < 0 or i + len(inputs) + len(ahead) > len(glyphs):
                    continue
                if all(glyphs[i - 1 - k] in c for k, c in enumerate(back)) and \
                        all(glyphs[i + k] in c for k, c in enumerate(inputs)) and \
                        all(glyphs[i + len(inputs) + k] in c for k, c in enumerate(ahead)):
                    for record in records:
                        apply_lookup(gsub, record.LookupListIndex, glyphs, i + record.SequenceIndex)
                    matched = True
                    break
            if matched:
                break
    return glyphs


class TurnTests(unittest.TestCase):
    """Alternates that take turns: the code by letter and by position, compiled and applied."""

    def test_by_letter_one_class_and_the_nearest_form_first(self):
        letters = [u"i", u"i.2", u"i.3", u"n", u"l"]
        code = fc.cycle_code({u"i": [u"i.2", u"i.3"]}, letters, 1)
        self.assertEqual(code, [u"@FreeLab_letters = [i i.2 i.3 l n];",
                                u"lookup FreeLab_take_turns {",
                                u"  sub i i' by i.2;",
                                u"  sub i.2 i' by i.3;",
                                u"  ignore sub i.3 i';",
                                u"  sub i @FreeLab_letters i' by i.2;",
                                u"  sub i.2 @FreeLab_letters i' by i.3;",
                                u"} FreeLab_take_turns;"])
        self.assertEqual(fc.turn_rules({u"i": [u"i.2", u"i.3"]}, 1), 5)
        self.assertEqual(fc.cycle_code({}, letters), [])

    def test_the_code_grows_with_the_alternates_not_with_their_square(self):
        """One class of the letters per letter (4,400 names, 1,100 times) made 56 MB of code."""
        bases = [u"g%04d" % n for n in range(1100)]
        sets = dict((base, [base + u".alt1", base + u".alt2", base + u".alt3"]) for base in bases)
        letters = bases + [form for forms in sets.values() for form in forms]
        self.assertEqual(fc.turn_mode(sets, 2), "position")
        self.assertEqual(fc.turn_rules(sets, 2), 12100)
        self.assertEqual(fc.turn_bytes(sets), 26400)
        self.assertIsNone(fc.turn_problem(sets, 2))
        code = fc.cycle_code(sets, letters, 2)
        self.assertLess(sum(len(line) for line in code), 120000)
        self.assertEqual(len([line for line in code if line.startswith(u"  sub ")]), 3, "a rule per step of the turn")
        self.assertLess(max(len(line) for line in code), 400, "long classes wrapped")
        forced = fc.cycle_code(sets, letters, 2, mode="letter")
        self.assertLess(sum(len(line) for line in forced), 800000)
        self.assertEqual([line for line in forced if line.startswith(u"@")], [u"@FreeLab_letters = ["],
                         "one class of the letters, wrapped; none per letter")
        few = dict((base, sets[base]) for base in bases[:60])
        self.assertEqual(fc.turn_mode(few, 2), "letter")
        self.assertEqual(fc.turn_mode(few, 6), "position", "a long look back takes more rules")
        self.assertEqual(fc.turn_mode({}, 2), "none")
        huge = dict((u"h%05d" % n, [u"h%05d.alt%d" % (n, k) for k in (1, 2, 3, 4)]) for n in range(1600))
        self.assertIn(u"1,600 glyphs taking turns need more room", fc.turn_problem(huge, 2),
                      "past what GSUB's offsets reach: said, not written")
        self.assertIn(u"untick some glyphs", fc.turn_problem(huge, 2))
        self.assertIn(u"(about 51,200 of 48,000 bytes)", fc.turn_problem(huge, 2), "numbers grouped by thousands")

    def test_a_cjk_fonts_letters_are_counted_before_a_glyph_taking_turns(self):
        """A font of ideographs: every one is a letter, so the class of the glyphs that may stand before a
        glyph taking turns holds tens of thousands. In the font's order they are a few runs; in an order
        without runs they pass what a table's offsets reach (fontTools could not compile the turns of
        6,000 glyphs among 48,000 letters in a shuffled font of 65,000 glyphs): said, not written."""
        order = dict((u"g%d" % n, n) for n in range(100))
        self.assertEqual(fc.coverage_bytes([u"g%d" % n for n in range(40)], order), 6, "one run of glyphs")
        self.assertEqual(fc.coverage_bytes([u"g1", u"g3", u"g5", u"g6", u"g7"], order), 10, "five glyphs: 2 bytes each")
        self.assertEqual(fc.coverage_bytes([u"g%d" % n for n in range(0, 40)] + [u"g50", u"g60"], order), 18)
        self.assertEqual(fc.coverage_bytes([], order), 0)
        letters = [u"u%05d" % n for n in range(30000)]
        sets = dict((base, [base + u".alt1"]) for base in letters[:50])
        forms = [form for base in sorted(sets) for form in sets[base]]
        in_order = dict((name, number) for number, name in enumerate(letters + forms))
        self.assertEqual(fc.turn_mode(sets, 2), "letter")
        context = fc.context_bytes(sets, letters + forms, {}, in_order, "letter")
        self.assertEqual(context, 6, "by glyph: the letters and the alternates, one run")
        self.assertIsNone(fc.turn_problem(sets, 2, context))
        self.assertEqual(fc.context_bytes(sets, letters + forms, {}, in_order, "position"), 6, "the letters alone")
        apart = dict((name, 2 * number) for name, number in in_order.items())  # (no two glyphs follow one another)
        context = fc.context_bytes(sets, letters + forms, {}, apart, "letter")
        self.assertEqual(context, 2 * 30050)
        problem = fc.turn_problem(sets, 2, context)
        self.assertIn(u"the glyphs that may stand before a glyph taking turns need more room", problem)
        self.assertIn(u"(about 60,100 of 48,000 bytes with the turns, in this font's glyph order)", problem)
        # By position, the turns' own room is added; figures are counted with figures
        many = dict((base, [base + u".alt1"]) for base in letters[:5000])
        self.assertEqual(fc.turn_mode(many, 2), "position")
        self.assertIsNone(fc.turn_problem(many, 2, 6))
        self.assertIn(u"(about 50,000 of 48,000 bytes with the turns", fc.turn_problem(many, 2, 10000))
        figures = {fc.FIGURES: [u"one", u"one.alt1", u"two"], fc.PUNCTUATION: [u"period"]}
        mixed = {u"one": [u"one.alt1"], u"u00000": [u"u00000.alt1"]}
        spread = dict((name, 2 * number) for number, name in enumerate([u"one", u"one.alt1", u"two", u"period",
                                                                        u"u00000", u"u00001", u"u00000.alt1"]))
        self.assertEqual(fc.context_bytes(mixed, [u"u00000", u"u00001", u"u00000.alt1"], figures, spread, "position"),
                         2 * 2 + 2 * 2, "two letters before a letter, two figures before a figure; no alternate")
        self.assertEqual(fc.context_bytes({}, letters, {}, in_order, "none"), 0)

    def compiled(self, sets, look_back, mode=None):
        try:
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            letters = sorted(set(base for base in sets) | set(u"abcdefgh"))
            font, order = turn_font(letters, dict((base, len(forms)) for base, forms in sets.items()))
        except Exception as exc:
            self.skipTest("fontTools cannot build the test font here: %s" % exc)
        every = [name for name in order if name not in (".notdef", "space", "period")]
        text = fc.calt_text(None, fc.cycle_code(sets, every, look_back, mode=mode))
        self.assertIsNone(fc.check_code(text, order))
        addOpenTypeFeaturesFromString(font, u"languagesystem DFLT dflt;\n" + text)
        return font, every

    def shape(self, font, text):
        gsub = font["GSUB"].table
        glyphs = [{u" ": "space", u".": "period"}.get(ch, ch) for ch in text]  # (characters, or glyph names)
        for record in gsub.FeatureList.FeatureRecord:
            if record.FeatureTag == "calt":
                for index in record.Feature.LookupListIndex:
                    apply_lookup(gsub, index, glyphs)
                break
        return u" ".join(glyphs)

    def sizes(self, font):
        """The compiled GSUB's size, which every 16-bit offset in it stays under."""
        import io
        buffer = io.BytesIO()
        font.save(buffer)
        from fontTools.ttLib import TTFont
        again = TTFont(io.BytesIO(buffer.getvalue()))
        return len(again.getTableData("GSUB")), [lookup.LookupType for lookup in again["GSUB"].table.LookupList.Lookup]

    def test_by_letter_compiled(self):
        sets = {u"a": [u"a.alt1", u"a.alt2"], u"b": [u"b.alt1"]}
        font, every = self.compiled(sets, 2)
        self.assertEqual(self.shape(font, u"aaaa"), u"a a.alt1 a.alt2 a", "back to the letter after its last alternate")
        self.assertEqual(self.shape(font, u"aaaaaaa"), u"a a.alt1 a.alt2 a a.alt1 a.alt2 a")
        self.assertEqual(self.shape(font, u"acdac"), u"a c d a.alt1 c", "two letters between")
        self.assertEqual(self.shape(font, u"acdea"), u"a c d e a", "three: too far")
        self.assertEqual(self.shape(font, u"a a.a"), u"a space a period a", "a space or punctuation ends the look back")
        self.assertEqual(self.shape(font, u"abab"), u"a b a.alt1 b.alt1")
        self.assertEqual(self.shape(font, u"aacaca"), u"a a.alt1 c a.alt2 c a",
                         "the nearest earlier form decides, and its last alternate's stops the look back")
        self.assertEqual(self.shape(font, u"bbbb"), u"b b.alt1 b b.alt1")
        size, kinds = self.sizes(font)
        self.assertLess(size, 2000)
        self.assertNotIn(7, kinds, "no extension lookup needed")
        none, _ = self.compiled(sets, 0)
        self.assertEqual(self.shape(none, u"aaca"), u"a a.alt1 c a", "look back 0: only side by side")

    def test_by_position_compiled(self):
        sets = {u"a": [u"a.alt1", u"a.alt2"], u"b": [u"b.alt1"], u"c": [u"c.alt1", u"c.alt2"]}
        font, every = self.compiled(sets, 2, "position")
        self.assertEqual(self.shape(font, u"aaaa"), u"a a.alt1 a.alt2 a")
        self.assertEqual(self.shape(font, u"acac"), u"a c.alt1 a.alt2 c", "the form after the letter's before it")
        self.assertEqual(self.shape(font, u"abc"), u"a b.alt1 c.alt2")
        self.assertEqual(self.shape(font, u"cab"), u"c a.alt1 b", "b has no second alternate: the letter itself")
        self.assertEqual(self.shape(font, u"da a"), u"d a.alt1 space a", "after a plain letter the first alternate; "
                                                                        u"a space starts afresh")
        size, kinds = self.sizes(font)
        self.assertLess(size, 600)
        self.assertEqual(sorted(kinds), [1, 1, 6], "two steps: two substitutions, one lookup of two rules")

    FIGURES = [u"zero", u"one", u"nine"]
    MARKS = [u"period", u"exclam", u"question", u"hyphen", u"quotedbl"]

    def test_each_kind_has_its_own_class(self):
        sets = {u"i": [u"i.2"], u"one": [u"one.alt1"], u"period": [u"period.alt1", u"period.alt2"]}
        letters = [u"i", u"i.2", u"n"]
        others = {fc.FIGURES: [u"one", u"one.alt1", u"zero", u"zero.tf"], fc.PUNCTUATION: [u"period", u"exclam"]}
        code = fc.cycle_code(sets, letters, 1, others=others)
        self.assertEqual(code, [u"@FreeLab_letters = [i i.2 n];",
                                u"@FreeLab_figures = [one one.alt1 zero zero.tf];",
                                u"@FreeLab_punctuation = [exclam period period.alt1 period.alt2];",
                                u"lookup FreeLab_take_turns {",
                                u"  sub i i' by i.2;",
                                u"  ignore sub i.2 i';",
                                u"  sub i @FreeLab_letters i' by i.2;",
                                u"  sub one one' by one.alt1;",
                                u"  ignore sub one.alt1 one';",
                                u"  sub one @FreeLab_figures one' by one.alt1;",
                                u"  sub period period' by period.alt1;",
                                u"  sub period.alt1 period' by period.alt2;",
                                u"  ignore sub period.alt2 period';",
                                u"  sub period @FreeLab_punctuation period' by period.alt1;",
                                u"  sub period.alt1 @FreeLab_punctuation period' by period.alt2;",
                                u"} FreeLab_take_turns;"])
        only = {u"i": [u"i.2"]}
        for mode in ("letter", "position"):
            self.assertEqual(fc.cycle_code(only, letters, 2, mode=mode, others=others),
                             fc.cycle_code(only, letters, 2, mode=mode),
                             "letters alone: the code written before figures and punctuation took turns")
            both = fc.cycle_code(sets, letters, 2, mode=mode, others=others)
            self.assertTrue(set(fc.cycle_code(only, letters, 2, mode=mode)) <= set(both), "and the same beside them")
        self.assertEqual(fc.cycle_code({u"one": [u"one.alt1"]}, letters, 0, others=others),
                         [u"@FreeLab_figures = [one one.alt1 zero zero.tf];", u"lookup FreeLab_take_turns {",
                          u"  sub one one' by one.alt1;", u"} FreeLab_take_turns;"], "no letter: no class of letters")
        by_position = fc.cycle_code(sets, letters, 1, mode="position", others=others)
        self.assertEqual([line for line in by_position if line.startswith(u"  sub ")],
                         [u"  sub @FreeLab_turn_0 @FreeLab_letters_1' by @FreeLab_turn_1;",
                          u"  sub @FreeLab_figures_turn_0 @FreeLab_figures_1' by @FreeLab_figures_turn_1;",
                          u"  sub @FreeLab_punctuation_turn_0 @FreeLab_punctuation_1' by @FreeLab_punctuation_turn_1;",
                          u"  sub @FreeLab_punctuation_turn_1 @FreeLab_punctuation_1' by @FreeLab_punctuation_turn_2;"],
                         "a rule per kind and step (the marks with a second step are those with a first: one class)")
        self.assertEqual(classes_of(u"\n".join(by_position))[u"FreeLab_figures_turn_0"], set([u"one", u"zero", u"zero.tf"]))

    def mixed(self, look_back, mode=None, forms=2):
        """A font of letters, figures, and punctuation marks, each with alternates, and its compiled turns."""
        try:
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            letters = list(u"abcd")
            bases = self.FIGURES + self.MARKS
            extra = bases + [u"%s.alt%d" % (base, n) for base in bases for n in range(1, forms + 1)] + [u"plus"]
            font, order = turn_font(letters, dict((ch, forms) for ch in letters), extra)
        except Exception as exc:
            self.skipTest("fontTools cannot build the test font here: %s" % exc)
        sets = dict((base, [u"%s.alt%d" % (base, n) for n in range(1, forms + 1)]) for base in letters + bases)
        others = {fc.FIGURES: [name for name in order if name.split(u".")[0] in self.FIGURES],
                  fc.PUNCTUATION: [name for name in order if name.split(u".")[0] in self.MARKS]}
        every = [name for name in order if name.split(u".")[0] in letters]
        text = fc.calt_text(None, fc.cycle_code(sets, every, look_back, mode=mode, others=others))
        self.assertIsNone(fc.check_code(text, order))
        addOpenTypeFeaturesFromString(font, u"languagesystem DFLT dflt;\n" + text)
        return font

    NAMES = {u"0": u"zero", u"1": u"one", u"9": u"nine", u".": u"period", u"!": u"exclam", u"?": u"question",
             u"-": u"hyphen", u'"': u"quotedbl", u" ": u"space", u"+": u"plus"}

    def set_text(self, font, text):
        return self.shape(font, [self.NAMES.get(ch, ch) for ch in text])

    def test_figures_and_punctuation_by_character_compiled(self):
        font = self.mixed(2)
        for text, shaped, why in (
                (u"1001", u"one zero zero.alt1 one.alt1", "two figures between: the second 1 takes its turn"),
                (u"99", u"nine nine.alt1", None),
                (u"...", u"period period.alt1 period.alt2", None),
                (u"....", u"period period.alt1 period.alt2 period", None),
                (u"!!", u"exclam exclam.alt1", None),
                (u"--", u"hyphen hyphen.alt1", None),
                (u"?!?", u"question exclam question.alt1", "a mark looks back over marks"),
                (u"aa.", u"a a.alt1 period", None),
                (u"a.a", u"a period a", "a letter does not look back over punctuation, as before"),
                (u"a-a", u"a hyphen a", None),
                (u"a1a", u"a one a", "nor over a figure"),
                (u"1a1", u"one a one", "nor a figure over a letter"),
                (u"1.1", u"one period one", "nor a figure over a mark"),
                (u".a.", u"period a period", None),
                (u"1 1", u"one space one", "a space ends every look back"),
                (u"1+1", u"one plus one", "and a symbol"),
                (u"abab 1010 .!.!", u"a b a.alt1 b.alt1 space one zero one.alt1 zero.alt1 space period exclam "
                                    u"period.alt1 exclam.alt1", None)):
            self.assertEqual(self.set_text(font, text), shaped, why or text)
        size, kinds = self.sizes(font)
        self.assertLess(size, 4000)
        self.assertNotIn(7, kinds, "no extension lookup needed")

    def test_figures_and_punctuation_by_position_compiled(self):
        font = self.mixed(2, "position")
        for text, shaped, why in (
                (u"1001", u"one zero.alt1 zero.alt2 one", "the form after the figure's before it"),
                (u"99", u"nine nine.alt1", None),
                (u"...", u"period period.alt1 period.alt2", None),
                (u"!!", u"exclam exclam.alt1", None),
                (u"--", u"hyphen hyphen.alt1", None),
                (u'"ab"', u"quotedbl a b.alt1 quotedbl", "a word after a quotation mark starts on its plain letter, as "
                                                         "after a space; the closing mark is plain: a letter stands before it"),
                (u"a1", u"a one", "a figure after a letter is plain"),
                (u"ab.!", u"a b.alt1 period exclam.alt1", "each kind takes its own turns"),
                (u"1 1", u"one space one", None)):
            self.assertEqual(self.set_text(font, text), shaped, why or text)
        size, kinds = self.sizes(font)
        self.assertLess(size, 1200)
        self.assertEqual(sorted(kinds), [1, 1, 6], "one lookup of six rules (two steps of three kinds); the kinds' "
                                                    "substitutions share a lookup per step, as fontTools compiles them")

    def test_a_whole_font_compiled(self):
        """1,100 letters, 40 figures and figure forms, and 60 punctuation marks, each with 3 variants, all
        checked: by position, in nine rules, and under the room the window counts."""
        try:
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            letters = [u"uni%04X" % code for code in range(0x100, 0x2000)
                       if unicodedata.category(fc.unichr_(code)) in ("Lu", "Ll")][:1100]
            figures = [u"fig%02d" % n for n in range(40)]
            marks = [u"mark%02d" % n for n in range(60)]
            extra = figures + marks + [u"%s.alt%d" % (base, n) for base in figures + marks for n in (1, 2, 3)]
            font, order = turn_font(letters, dict((ch, 3) for ch in letters), extra)
        except Exception as exc:
            self.skipTest("fontTools cannot build the test font here: %s" % exc)
        sets = dict((base, [u"%s.alt%d" % (base, n) for n in (1, 2, 3)]) for base in letters + figures + marks)
        others = {fc.FIGURES: [name for name in order if name.startswith(u"fig")],
                  fc.PUNCTUATION: [name for name in order if name.startswith(u"mark")]}
        every = [name for name in order[3:] if name.startswith(u"uni")]
        self.assertEqual(fc.turn_mode(sets, 2), "position")
        self.assertEqual(fc.turn_rules(sets, 2), 13200)
        self.assertEqual(fc.turn_bytes(sets), 28800)
        self.assertIsNone(fc.turn_problem(sets, 2))
        code = fc.cycle_code(sets, every, 2, others=others)
        self.assertEqual(len([line for line in code if line.startswith(u"  sub ")]), 9, "a rule per kind and step")
        addOpenTypeFeaturesFromString(font, u"languagesystem DFLT dflt;\n" + fc.calt_text(None, code))
        size, kinds = self.sizes(font)
        self.assertLess(size, fc.turn_bytes(sets))
        self.assertEqual(sorted(kinds), [1, 1, 1, 6])
        a, f, m = letters[0], figures[0], marks[0]
        self.assertEqual(self.shape(font, [a, a, f, f, f, m, m, a]),
                         u"%s %s.alt1 %s %s.alt1 %s.alt2 %s %s.alt1 %s" % (a, a, f, f, f, m, m, a))

    def test_a_whole_alphabet_compiled(self):
        """1,100 letters with 3 variants each: FontLab's compiler stopped at "coverage section too large";
        the code by position compiles to a few kilobytes, every offset far under 65,535."""
        try:
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            letters = [u"uni%04X" % code for code in range(0x100, 0x2000)
                       if unicodedata.category(fc.unichr_(code)) in ("Lu", "Ll")][:1100]
            font, order = turn_font(letters, dict((ch, 3) for ch in letters))
        except Exception as exc:
            self.skipTest("fontTools cannot build the test font here: %s" % exc)
        self.assertEqual(len(letters), 1100)
        sets = dict((ch, [u"%s.alt%d" % (ch, n) for n in (1, 2, 3)]) for ch in letters)
        every = order[3:]
        text = fc.calt_text(None, fc.cycle_code(sets, every, 2))
        addOpenTypeFeaturesFromString(font, u"languagesystem DFLT dflt;\n" + text)
        size, kinds = self.sizes(font)
        self.assertLess(size, fc.turn_bytes(sets))
        self.assertLess(fc.turn_bytes(sets), 65535)
        self.assertEqual(sorted(kinds), [1, 1, 1, 6])
        a, b = letters[0], letters[700]
        self.assertEqual(self.shape(font, [a, a, b, b, a]), u"%s %s.alt1 %s.alt2 %s.alt3 %s" % (a, a, b, b, a))


class LargeFontTests(unittest.TestCase):
    """The other features Feature Code writes, on a font of 1,100 letters: none grows as the letters
    taking turns did (a table per rule, each with its own lists of glyphs), so none nears the 65,535
    bytes an offset reaches."""

    def letters(self):
        return [(u"uni%04X" % code, code) for code in range(0x100, 0x2000)
                if unicodedata.category(fc.unichr_(code)) in ("Lu", "Ll")][:1100]

    def compiled(self, text, names):
        """(the compiled GSUB's size, its lookups' types), by fontTools; skipped without it."""
        try:
            import io
            from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
            from fontTools.ttLib import TTFont
            font, order = turn_font([], {}, names)
        except Exception as exc:
            self.skipTest("fontTools cannot build the test font here: %s" % exc)
        self.assertIsNone(fc.check_code(text, order))
        addOpenTypeFeaturesFromString(font, text)
        buffer = io.BytesIO()
        font.save(buffer)
        again = TTFont(io.BytesIO(buffer.getvalue()))
        return len(again.getTableData("GSUB")), [lookup.LookupType for lookup in again["GSUB"].table.LookupList.Lookup]

    def test_the_forms_of_a_whole_alphabet(self):
        letters = self.letters()
        extra = [name + suffix for name, _ in letters for suffix in (u".sc", u".ss01", u".case")]
        extra += [d + s for d in DIGIT_NAMES for s in (u".numr", u".dnom", u".tf", u".osf")]
        info = make_info(extra, codes=letters)
        features, _ = fc.form_features(info, {})
        found = by_tag(features)
        self.assertEqual(len(found["ss01"].rules), 1100)
        self.assertEqual(len(found["case"].rules), 1100)
        self.assertGreater(len(found["smcp"].rules) + len(found["c2sc"].rules), 1100)
        texts = fc.forms_texts(features, {})
        tags = [feature.tag for feature in features]
        self.assertEqual(tags[0], "aalt")
        whole = fc.prefix_text(u"", fc.language_systems(found["locl"])) + u"".join(texts[tag] for tag in tags)
        self.assertLess(len(whole), 200000, "a line per substitution: the code grows with the glyphs, no faster")
        size, kinds = self.compiled(whole, info.names)
        self.assertLess(size, 40000, "aalt, case, the small capitals, the figures, and the set together")
        self.assertNotIn(7, kinds, "no lookup past its offsets (fontTools would have made it an extension)")

    def test_a_thousand_ligatures(self):
        letters = [name for name, _ in self.letters()]
        rules = [([letters[n], letters[n + 1]], u"%s_%s" % (letters[n], letters[n + 1])) for n in range(1000)]
        text = fc.feature_text("liga", None, rules, "ligatures")
        size, kinds = self.compiled(u"languagesystem DFLT dflt;\n" + text, letters + [glyph for _, glyph in rules])
        self.assertLess(size, 20000)
        self.assertEqual(kinds, [4], "one lookup of ligatures")


class KindTests(unittest.TestCase):
    """Which characters take turns: letters, figures, and punctuation marks, told by the model's table
    so that FontLab's Python 2.7 (Unicode 5.2) and Python 3 list the same characters."""

    def test_kinds(self):
        for ch, kind in ((u"a", fc.LETTERS), (u"\u00df", fc.LETTERS), (u"\u3044", fc.LETTERS), (u"9", fc.FIGURES),
                         (u"\u00b2", fc.FIGURES), (u"\u00bd", fc.FIGURES), (u".", fc.PUNCTUATION), (u"-", fc.PUNCTUATION),
                         (u"&", fc.PUNCTUATION), (u"\u2026", fc.PUNCTUATION), (u"_", fc.PUNCTUATION),
                         (u" ", None), (u"+", None), (u"$", None), (u"~", None), (u"\u2044", None), (u"\u0301", None),
                         (u"\u00a9", None)):
            self.assertEqual(fc.char_kind(ch), kind, repr(ch))
        for value in (None, u"", u"ab"):
            self.assertIsNone(fc.char_kind(value))

    def test_the_same_in_python_2_and_3(self):
        # Python 2.7's Unicode 5.2 calls the section sign and the pilcrow symbols, and knows none of the rest
        for code, kind in ((0xA7, fc.PUNCTUATION), (0xB6, fc.PUNCTUATION), (0x2E3A, fc.PUNCTUATION),
                           (0xA7AE, fc.LETTERS), (0x1C90, fc.LETTERS), (0x20BD, None)):
            self.assertEqual(fc.char_kind(fc.unichr_(code)), kind, "U+%04X" % code)
        self.assertIsNone(fc.char_kind(fc.unichr_(0x1D400)), "past U+FFFF: no character in FontLab's Python")
        self.assertIsNone(fc.char_kind(u"\U0001D400"))

    def test_the_table_is_unicodes(self):
        table = fc.load_kinds()
        self.assertIsNotNone(table)
        self.assertIsNone(fc.load_kinds(os.path.join(HERE, "no-such-file.json")))
        self.assertEqual(fc.char_kind(u"a", ()), fc.LETTERS, "without the table, this Python's unicodedata")
        self.assertEqual(fc.char_kind(u"+", ()), None)
        import io
        import json
        with io.open(os.path.join(HERE, os.pardir, "features", fc.DOUBLES_FILE), encoding="utf-8") as handle:
            source = json.load(handle)["kinds_source"]
        if (u"Unicode %s:" % unicodedata.unidata_version) not in source:
            self.skipTest("this Python's Unicode (%s) is not the table's" % unicodedata.unidata_version)
        for code in range(0x10000):
            ch = fc.unichr_(code)
            self.assertEqual(fc.char_kind(ch, table), fc.CATEGORY_KINDS.get(unicodedata.category(ch)[:1]), "U+%04X" % code)

    def test_glyphs_by_kind(self):
        codes = {u"a": 0x61, u"f": 0x66, u"t": 0x74, u"one": 0x31, u"nine": 0x39, u"period": 0x2E, u"hyphen": 0x2D,
                 u"space": 0x20, u"plus": 0x2B, u"acutecomb": 0x301, u"big": 0x1D400, u"quote_single": 0x27}
        names = [u"a", u"a.sc", u"f", u"t", u"f_f_t", u"f_t.liga", u"one", u"one.tf", u"nine", u"nine.alt1", u"period",
                 u"hyphen", u"hyphen.case", u"period_period_period", u"f_period", u"one_period", u"space", u"plus",
                 u"plus.alt1", u"acutecomb", u".notdef", u"big", u"x.alt1", u"quote_single", u"quote_single.alt1"]
        kinds = fc.glyph_kinds(names, codes)
        self.assertEqual(kinds[fc.LETTERS], [u"a", u"a.sc", u"f", u"t", u"f_f_t", u"f_t.liga"])
        self.assertEqual(kinds[fc.FIGURES], [u"one", u"one.tf", u"nine", u"nine.alt1"])
        self.assertEqual(kinds[fc.PUNCTUATION], [u"period", u"hyphen", u"hyphen.case", u"period_period_period",
                                                 u"quote_single", u"quote_single.alt1"],
                         "a glyph joining two kinds (f_period) is of none; a character is of its kind whatever its name")
        sets = fc.alternate_sets(names + [u"a.alt1", u"period.2"], lambda name: fc.char_kind(fc.unichr_(codes.get(name, 0x20))))
        self.assertEqual(sets, {u"a": [u"a.alt1"], u"nine": [u"nine.alt1"], u"period": [u"period.2"],
                                u"quote_single": [u"quote_single.alt1"]},
                         "a plus sign's alternates take no turns")


class DoubleTests(unittest.TestCase):
    """The characters that double in text, which lead the characters taking turns."""

    def test_a_capital_counts_as_its_own_small_letter_only(self):
        # Python 2 (FontLab's) lowers the dotted capital I to a plain i: it led the list as "ii" does
        dotted = fc.unichr_(0x130) if hasattr(fc, "unichr_") else u"\N{LATIN CAPITAL LETTER I WITH DOT ABOVE}"
        self.assertEqual(fc.small(u"E"), u"e")
        self.assertEqual(fc.small(dotted), dotted)
        self.assertEqual(fc.double_count(u"I", {u"i": 9}), 9)
        self.assertEqual(fc.double_count(dotted, {u"i": 9}), 0)

    def test_the_counts_ship_with_the_model(self):
        doubles = fc.load_doubles()
        self.assertGreater(len(doubles), 60)
        self.assertGreater(doubles[u"e"], doubles[u"l"])
        self.assertGreater(doubles[u"l"], doubles[u"f"])
        self.assertGreaterEqual(doubles[u"f"], fc.DOUBLE_OFTEN)
        self.assertEqual(fc.load_doubles(os.path.join(HERE, "no-such-file.json")), {})

    def test_often_and_seldom(self):
        doubles = {u"l": 2779, u"f": 300, u"w": 20, u"9": 112}
        pairs = {u"\u3044\u3044": 162, u"TT": 21}
        self.assertTrue(fc.doubles_often(u"l", doubles))
        self.assertTrue(fc.doubles_often(u"L", doubles), "text in capitals doubles the same letters")
        self.assertTrue(fc.doubles_often(u"9", doubles))
        self.assertFalse(fc.doubles_often(u"w", doubles))
        self.assertFalse(fc.doubles_often(u"q", doubles))
        self.assertTrue(fc.doubles_often(u"\u3044", doubles, pairs), "kana, among Auto Kerning's common pairs")
        self.assertTrue(fc.doubles_often(u"T", doubles, pairs))
        self.assertFalse(fc.doubles_often(None, doubles, pairs))
        self.assertEqual(fc.double_words(u"l", doubles)[0], u"Often")
        self.assertIn(u"ll: about 2779 of every 300,000 pairs of characters in text", fc.double_words(u"l", doubles)[1])
        self.assertEqual(fc.double_words(u"w", doubles),
                         (u"Seldom", u"ww: about 20 of every 300,000 pairs of characters in text, in the language that "
                                     u"doubles it most."))
        self.assertIn(u"[[: about 1 of every 300,000 pairs", fc.double_words(u"[", {u"[": 1})[1], "the same words for one")
        self.assertEqual(fc.double_words(u"q", doubles), (u"Seldom", u"qq was not found among the pairs counted in text."))
        self.assertEqual(fc.double_words(u"\u3044", doubles, pairs)[0], u"Often")
        self.assertEqual(fc.grouped(1102), u"1,102")
        self.assertEqual(fc.grouped(300000), u"300,000")
        self.assertEqual(fc.grouped(12), u"12")

    def test_figures_and_punctuation_by_the_same_counts(self):
        """What the counts hold for figures and punctuation, and why the marks are taken from conventions:
        the text counted is an encyclopedia's with its markup, so no mark is counted as often as the
        letters that double, and the common pairs' doubled marks are markup."""
        doubles, typed = fc.load_doubles(), fc.load_typed_doubles()
        self.assertEqual([doubles[ch] for ch in u"0918"], [419, 112, 72, 45])
        self.assertEqual([doubles[ch] for ch in u"}.-,/!?"], [85, 72, 47, 32, 24, 1, 1])
        marks = [ch for ch in doubles if fc.char_kind(ch) == fc.PUNCTUATION]
        self.assertEqual(len(marks), 19)
        self.assertEqual([ch for ch in marks if doubles[ch] >= fc.DOUBLE_OFTEN], [],
                         "no mark reaches what makes a letter one that doubles: the conventions decide")
        self.assertEqual(typed, set([u".", u"!", u"?", u"-", u"'", u"\u2032", u"\u2035"]),
                         "Unicode's ellipsis, !!, ??, and primes; TeX's -- and ''")
        self.assertEqual(fc.load_typed_doubles(os.path.join(HERE, "no-such-file.json")), set())
        pairs = {u"}}": 3, u"//": 9, u"))": 12, u"{{": 30, u"TT": 21}
        often = [ch for ch in u"09185.!?-'},/)({\"" if fc.doubles_often(ch, doubles, pairs, typed)]
        self.assertEqual(often, list(u"09.!?-'"), "00 and 99 by their counts, the marks by convention; not the "
                                                  "markup the common pairs hold (}}, //, )), {{)")
        self.assertTrue(fc.doubles_often(u"T", doubles, pairs, typed), "a letter's common pair still counts")
        self.assertTrue(fc.doubles_often(u";", {u";": 100}), "a mark counted as often as a letter would be one too")
        self.assertEqual(fc.double_words(u".", doubles, pairs, typed),
                         (u"Often", u".. is a mark doubled by convention (as ..., !!, ??, --, and '' are)."))
        self.assertEqual(fc.double_words(u",", doubles, pairs, typed),
                         (u"Seldom", u",,: about 32 of every 300,000 pairs of characters in text, in the language that "
                                     u"doubles it most."))
        self.assertEqual(fc.double_words(u"}", doubles, pairs, typed)[0], u"Seldom")
        self.assertEqual(fc.double_words(u"0", doubles, pairs, typed)[0], u"Often")
        chars = {u"zero": u"0", u"one": u"1", u"period": u".", u"comma": u",", u"exclam": u"!", u"w": u"w", u"l": u"l",
                 u"braceright": u"}"}
        self.assertEqual(fc.turn_order(list(chars), chars, doubles, pairs, typed),
                         [u"l", u"zero", u"period", u"exclam", u"braceright", u"one", u"comma", u"w"],
                         "those often doubled by their counts, then the rest by theirs")

    def test_order_and_first_checks(self):
        doubles = {u"l": 2779, u"e": 3329, u"w": 20}
        chars = {u"l": u"l", u"e": u"e", u"w": u"w", u"x": u"x", u"L": u"L", u"ka": u"\u304b"}
        pairs = {u"\u304b\u304b": 280}
        order = fc.turn_order(list(chars), chars, doubles, pairs)
        self.assertEqual(order, [u"e", u"L", u"l", u"ka", u"w", u"x"])
        sets = dict((base, [base + u".alt1"]) for base in order)
        often = set([u"e", u"L", u"l", u"ka"])
        self.assertEqual(fc.first_turns(sets, order, often, set([u"l"])), set(order) - set([u"l"]),
                         "few letters: all but the one whose alternate has a job")
        many = dict((u"g%d" % n, [u"g%d.alt1" % n, u"g%d.alt2" % n]) for n in range(400))
        many.update(sets)
        self.assertEqual(fc.first_turns(many, sorted(many), often, set()), often, "many: those doubled in text")
        self.assertEqual(fc.first_turns(many, sorted(many), set(), set()), set(many), "none known to double: all")
        calt = fc.calt_text(None, fc.cycle_code({u"x": [u"x.alt1"]}, [u"x", u"x.alt1", u"w"]))
        self.assertEqual(fc.turns_written(sets, calt), set([u"x"]), "what the font's code cycles already")
        self.assertEqual(fc.turns_written(sets, u"feature calt {\n  sub x' w by x.alt1;\n} calt;\n"), set())

    def test_notes_made_plain(self):
        self.assertEqual(fc.plain(u"their <i>Glyphs</i> panel: a &lt; b &amp; c<br/>"), u"their Glyphs panel: a < b & c")
        self.assertEqual(fc.plain(u"sub a' <b> by c"), u"sub a'  by c")
        self.assertEqual(fc.plain(None), u"")
        info = make_info([u"hyphen.case", u"a.sc", u"a.ss01", u"i.loclTRK", u"one.numr", u"one.dnom", u"one.tf"])
        for feature in fc.form_features(info, {})[0]:
            for note in [feature.note, feature.kind_note] + [rule.note for rule in feature.rules]:
                self.assertIsNone(MARKUP.search(note or u""), note)


class PlaceNodeTests(unittest.TestCase):
    """Thicker strokes are written by moving nodes. FontLab keeps a node's x and y set from a script, but
    its shape's outline follows only a node moved through its position (seen live): forms built with
    Strokes at 130% looked as scaled."""

    class Node(object):
        """As FontLab's: x and y can be set, and the shape sees only what position was given."""

        def __init__(self, x, y):
            self.x, self.y, self.shape_sees = x, y, (x, y)

        @property
        def position(self):
            return (self.x, self.y)

        @position.setter
        def position(self, point):
            self.x, self.y = point.x(), point.y()
            self.shape_sees = (self.x, self.y)

    class Point(object):
        def __init__(self, x, y):
            self.px, self.py = x, y

        def x(self):
            return self.px

        def y(self):
            return self.py

    def test_a_node_is_moved_through_its_position(self):
        class Core(object):
            QPointF = PlaceNodeTests.Point

        class Qt(object):
            QtCore = Core

        old = sys.modules.get("PythonQt")
        sys.modules["PythonQt"] = Qt
        self.addCleanup(lambda: sys.modules.__setitem__("PythonQt", old) if old is not None else sys.modules.pop("PythonQt"))
        node = self.Node(10.0, 20.0)
        fc.place_node(node, 13.5, 18.0)
        self.assertEqual(node.shape_sees, (13.5, 18.0), "the shape's outline follows")

    def test_a_node_without_a_position_takes_x_and_y(self):
        node = FakeNode(10.0, 20.0)
        fc.place_node(node, 13.5, 18.0)
        self.assertEqual((node.x, node.y), (13.5, 18.0))


if __name__ == "__main__":
    unittest.main()
