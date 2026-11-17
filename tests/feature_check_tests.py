# -*- coding: utf-8 -*-
"""Tests of Feature Check's checks (its pure parts). Valid Python 2.7 and Python 3. The checks need
fontTools: run_tests gives the 2.7 run the fontTools FontLab 7 ships (3.43) where FontLab is installed;
without fontTools the tests that need it are skipped."""
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_feature_check as fc  # noqa: E402

HAS_FONTTOOLS = fc.fealib() is not None
ORDER = [".notdef", "a", "b", "c", "f", "i", "l", "f_i", "f_l", "a.sc", "b.sc", "c.sc", "one", "two", "one.osf",
         "two.osf", "acutecomb", "e", "eacute"]
DECLARED = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n"


def code(prefix=DECLARED, **features):
    return fc.FontCode(prefix, [(tag, text) for tag, text in sorted(features.items())])


def feature(tag, body):
    return "feature %s {\n%s} %s;\n" % (tag, body, tag)


def kinds(report):
    return sorted(set(f.kind for f in report.findings))


def finding(report, kind):
    found = [f for f in report.findings if f.kind == kind]
    return found[0] if found else None


class TextTests(unittest.TestCase):
    """Parts, lines, and edits need no fontTools."""

    def test_parts_go_together_in_compiling_order_and_lines_map_back(self):
        c = fc.FontCode("languagesystem DFLT dflt;", [("liga", feature("liga", "  sub f i by f_i;\n"))],
                        [("@uc", ["A", "B"])])
        text, spans = c.text()
        self.assertTrue(text.startswith("@uc = [A B];\nlanguagesystem DFLT dflt;\nfeature liga {"))
        self.assertEqual(fc.locate(spans, 1), ("classes", 1))
        self.assertEqual(fc.locate(spans, 2), ("prefix", 1))
        self.assertEqual(fc.locate(spans, 4), ("feature:liga", 2))

    def test_a_statement_span_runs_to_its_semicolon_and_a_block_to_its_end(self):
        text = "lookup L { sub a by b; } L;\nsub c by d;\n"
        self.assertEqual(text[slice(*fc.statement_span(text, 0))], "lookup L { sub a by b; } L;")
        at = text.index("sub c")
        self.assertEqual(text[slice(*fc.statement_span(text, at))], "sub c by d;")

    def test_a_removal_takes_the_whole_line_only_where_the_statement_stands_alone(self):
        text = "  sub a by b;\n  sub c by d; # kept\n"
        start, end = fc.whole_lines(text, 2, 13)
        self.assertEqual(text[:start] + text[end:], "  sub c by d; # kept\n")
        at = text.index("sub c")
        self.assertEqual(fc.whole_lines(text, at, at + 11), (at, at + 11), "a comment after it: the line stays")

    def test_edits_from_one_place_keep_the_wider(self):
        c = fc.FontCode("abcdef\n", [])
        new = fc.apply_edits(c, [fc.Edit("prefix", 0, 3, "X"), fc.Edit("prefix", 0, 6, "")])
        self.assertEqual(new.prefix, "\n", "a removal and a rewrite of the same statement: the removal")

    def test_fontlab_automatic_code_is_found_by_its_comments(self):
        text = "feature kern {\n#> feature\npos a b -10;\n#< feature\n} kern;\n"
        spans = fc.automatic_spans(text)
        self.assertEqual(len(spans), 1)
        self.assertIn("pos a b", text[spans[0][0]:spans[0][1]])


@unittest.skipUnless(HAS_FONTTOOLS, "fontTools is not installed")
class CheckTests(unittest.TestCase):
    def test_clean_code_has_no_finding_and_compiles(self):
        report = fc.check(code(liga=feature("liga", "  sub f i by f_i;\n")), ORDER)
        self.assertEqual(report.findings, [])
        self.assertTrue(report.built)

    def test_a_syntax_error_is_found_in_each_feature_that_has_one(self):
        report = fc.check(code(calt=feature("calt", "  sub a' b by c\n"), liga=feature("liga", "  sub f i by\n"),
                               smcp=feature("smcp", "  sub a by a.sc;\n")), ORDER)
        found = sorted(f.key for f in report.findings if f.kind == "syntax")
        self.assertEqual(found, ["feature:calt", "feature:liga"], "smcp reads well and is still checked")
        self.assertFalse(report.built)

    def test_every_missing_glyph_is_listed_once_with_its_count(self):
        report = fc.check(code(liga=feature("liga", "  sub f f by f_f;\n  sub f f i by f_f_i;\n")), ORDER)
        missing = sorted(f.subject for f in report.findings if f.kind == "missing-glyph")
        self.assertEqual(missing, ["f_f", "f_f_i"])
        self.assertIn("missing-glyph", kinds(report))

    def test_a_missing_glyph_reads_alike_in_both_fonttools(self):
        # (fontTools 4 refuses it while parsing, 3.43 only while building: both report it, not a syntax error)
        report = fc.check(code(smcp=feature("smcp", "  sub zz by a;\n")), ORDER)
        self.assertEqual(kinds(report), ["missing-glyph"])

    def test_unused_classes_and_lookups_are_found_with_fixes(self):
        prefix = DECLARED + "@used = [a b];\n@spare = [c];\nlookup SPARE { sub c by c.sc; } SPARE;\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  sub @used by [a.sc b.sc];\n")), ORDER)
        self.assertEqual(finding(report, "unused-class").subject, "@spare")
        self.assertEqual(finding(report, "unused-lookup").subject, "SPARE")
        self.assertIsNotNone(finding(report, "unused-class").fix)

    def test_a_class_used_only_by_another_class_counts_as_used(self):
        prefix = DECLARED + "@lc = [a b];\n@all = [@lc c];\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  sub @all by [a.sc b.sc c.sc];\n")), ORDER)
        self.assertIsNone(finding(report, "unused-class"))

    def test_a_rule_written_twice_and_a_glyph_by_itself(self):
        report = fc.check(code(liga=feature("liga", "  sub f i by f_i;\n  sub f i by f_i;\n"),
                               smcp=feature("smcp", "  sub c by c;\n  sub a by a.sc;\n")), ORDER)
        self.assertEqual(finding(report, "duplicate-rule").key, "feature:liga")
        self.assertEqual(finding(report, "duplicate-rule").line, 3)
        self.assertEqual(finding(report, "identity").key, "feature:smcp")

    def test_a_language_no_languagesystem_declares(self):
        body = "  sub a by a.sc;\n  script cyrl;\n  sub b by b.sc;\n  script latn;\n  language TRK;\n  sub c by c.sc;\n"
        report = fc.check(code(smcp=feature("smcp", body)), ORDER)
        subjects = sorted(f.subject for f in report.findings if f.kind == "language")
        self.assertEqual(subjects, ["cyrl dflt", "latn TRK"])

    def test_no_default_language_system(self):
        report = fc.check(code("languagesystem latn dflt;\n", smcp=feature("smcp", "  sub a by a.sc;\n")), ORDER)
        self.assertEqual(kinds(report), ["no-default"])

    def test_no_languagesystem_at_all_is_fine(self):
        report = fc.check(code("", smcp=feature("smcp", "  sub a by a.sc;\n")), ORDER)
        self.assertEqual(report.findings, [])

    def test_empty_features_and_classes(self):
        prefix = DECLARED + "@none = [];\n"
        report = fc.check(code(prefix, ss01=feature("ss01", ""), smcp=feature("smcp", "  sub [@none] by a.sc;\n")), ORDER)
        self.assertEqual(finding(report, "empty-feature").subject, "ss01")
        self.assertEqual(finding(report, "empty-class").subject, "@none")

    def test_aalt_after_another_feature(self):
        c = fc.FontCode(DECLARED, [("smcp", feature("smcp", "  sub a by a.sc;\n")),
                                   ("aalt", feature("aalt", "  feature smcp;\n"))])
        self.assertEqual(finding(fc.check(c, ORDER), "aalt-order").subject, "aalt")

    def test_a_glyph_given_two_ways_in_one_lookup(self):
        report = fc.check(code(smcp=feature("smcp", "  sub a by a.sc;\n  sub a by b.sc;\n")), ORDER)
        self.assertIn(finding(report, "conflict").subject, ("a", '"a"'))

    def test_fontlab_classes_are_known_but_never_reported_unused(self):
        c = fc.FontCode(DECLARED, [("smcp", feature("smcp", "  sub a by a.sc;\n"))], [("figures", ["one", "two"])])
        self.assertEqual(fc.check(c, ORDER).findings, [])
        c = fc.FontCode(DECLARED, [("onum", feature("onum", "  sub @figures by [one.osf two.osf];\n"))],
                        [("figures", ["one", "two"])])
        self.assertTrue(fc.check(c, ORDER).built)

    def test_a_mark_filtering_flag_without_its_class_is_found_and_hides_nothing(self):
        # (FontLab writes "lookupflag 16;" on opening some fonts, Amiri 29 times)
        prefix = DECLARED + "@spare = [c];\nlookup MARKS { lookupflag 16; sub a by a.sc; } MARKS;\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  lookup MARKS;\n  sub zz by b;\n")), ORDER)
        flag = finding(report, "flag")
        self.assertEqual((flag.key, flag.line), ("prefix", 4))
        self.assertEqual(finding(report, "missing-glyph").subject, "zz", "the build went on past the flag")
        fc.prove_fixes(report, ORDER)
        self.assertIs(finding(report, "unused-class").fix.safe, True, "proven on the code made buildable")
        self.assertFalse(report.built)

    def test_fontlab_automatic_code_gets_no_fix(self):
        body = "#> feature\n  sub f i by f_i;\n  sub f i by f_i;\n#< feature\n"
        report = fc.check(code(liga=feature("liga", body)), ORDER)
        dup = finding(report, "duplicate-rule")
        self.assertTrue(dup.automatic)
        self.assertIsNone(dup.fix)


@unittest.skipUnless(HAS_FONTTOOLS, "fontTools is not installed")
class ProofTests(unittest.TestCase):
    def test_fixes_that_change_nothing_are_proven_safe_and_applied_together(self):
        prefix = DECLARED + "@spare = [c];\n@used = [a b a];\nlookup SPARE { sub c by c.sc; } SPARE;\n"
        c = code(prefix, liga=feature("liga", "  sub f i by f_i;\n  sub f i by f_i;\n"),
                 smcp=feature("smcp", "  sub @used by c.sc;\n  sub c by c;\n"))
        report = fc.check(c, ORDER)
        chosen = fc.safe_fixes(report, ORDER)
        self.assertEqual(len(chosen), 5, [f.what for f in chosen])
        fixed = fc.apply_fixes(c, chosen)
        self.assertNotIn("@spare", fixed.prefix)
        self.assertNotIn("SPARE", fixed.prefix)
        self.assertIn("@used = [a b];", fixed.prefix)
        self.assertEqual(fixed.part("feature:liga").count("sub f i by f_i;"), 1)
        self.assertNotIn("sub c by c;", fixed.part("feature:smcp"))
        again = fc.check(fixed, ORDER)
        self.assertEqual(again.findings, [], [f.message for f in again.findings])
        self.assertTrue(fc.same_layout(fc.fealib(), c, fixed, ORDER))

    def test_a_single_substitution_written_twice_is_proven_in_both_fonttools(self):
        # (fontTools 3.43 refuses it, which set the whole feature aside and left its fixes unproven, live)
        c = code(ss19=feature("ss19", "  @spare = [c];\n  sub a by b;\n  sub a by b;\n  sub c by c;\n"))
        report = fc.check(c, ORDER)
        chosen = fc.safe_fixes(report, ORDER)
        self.assertEqual(sorted(f.what for f in chosen), ["Remove @spare's definition", "Remove it", "Remove the second one"])
        self.assertEqual(fc.apply_fixes(c, chosen).part("feature:ss19"), feature("ss19", "  sub a by b;\n"))
        self.assertIsNone(finding(report, "conflict"))

    def test_a_rule_again_after_a_rule_of_another_kind_is_no_duplicate(self):
        # (three lookups in fontTools 3.43: the second "sub a by b" applies to the a the ligature makes;
        # it was removed as a duplicate and proven "safe" against code that had it blanked; review 9)
        order = [".notdef", "a", "b", "c", "d", "x", "y", "z", "w"]
        c = code(calt=feature("calt", "sub a by b;\nsub x by y;\nsub c d by a;\nsub a by b;\nsub z by w;\n"))
        report = fc.check(c, order)
        self.assertIsNone(finding(report, "duplicate-rule"))
        self.assertEqual(fc.safe_fixes(report, order), [])
        again = code(calt=feature("calt", "sub a by b;\nlookupflag IgnoreMarks;\nsub a by b;\n"))
        self.assertIsNone(finding(fc.check(again, order), "duplicate-rule"), "a lookup flag begins a new lookup")

    def test_a_required_feature_is_not_the_same_as_an_optional_one(self):
        def one(required):
            return fc.FontCode("languagesystem latn dflt;\n", [("liga", "feature liga { script latn; language dflt%s; "
                                                               "sub a by b; } liga;" % (" required" if required else ""))])
        self.assertIs(fc.same_layout(fc.fealib(), one(False), one(True), ORDER), False)

    def test_a_large_class_checks_in_linear_time(self):
        import time
        names = ["g%05d" % i for i in range(20000)]
        c = fc.FontCode(DECLARED + "@big = [%s];\n" % " ".join(names),
                        [("ss01", feature("ss01", "  sub @big by a;\n"))])
        started = time.time()
        report = fc.check(c, ORDER + names)
        self.assertLess(time.time() - started, 30.0)
        self.assertIsNone(finding(report, "class-duplicates"))

    def test_fontlab_code_is_looked_for_once_a_part(self):
        # (review 10: once a finding, 10,000 duplicates scanned their feature 10,000 times)
        calls = []
        saved = fc.automatic_spans
        fc.automatic_spans = lambda text: calls.append(1) or saved(text)
        try:
            findings = [fc.Finding("duplicate-rule", "x", "feature:liga", line) for line in range(1, 400)]
            fc.mark_automatic(findings, code(liga=feature("liga", "  sub f i by f_i;\n" * 400)))
        finally:
            fc.automatic_spans = saved
        self.assertEqual(len(calls), 1)

    def test_a_fix_that_would_not_compile_is_withdrawn(self):
        # (sub [a b a] by [x y z]: each glyph takes its place's; dropping the second a breaks the rule)
        c = code(DECLARED + "@used = [a b a];\n", smcp=feature("smcp", "  sub @used by [a.sc b.sc c.sc];\n"))
        report = fc.check(c, ORDER)
        self.assertIsNotNone(finding(report, "class-duplicates").fix)
        fc.prove_fixes(report, ORDER)
        dup = finding(report, "class-duplicates")
        self.assertIsNone(dup.fix, "no fix offered")
        self.assertIn("would break the code", dup.message)
        self.assertEqual(fc.safe_fixes(report, ORDER), [])

    def test_a_fix_that_changes_the_layout_is_proven_unsafe(self):
        c = code(smcp=feature("smcp", "  sub a by a.sc;\n"))
        report = fc.check(c, ORDER)
        harmful = fc.Fix("Remove the rule", [fc.Edit("feature:smcp", c.part("feature:smcp").index("  sub"),
                                                     c.part("feature:smcp").index("} smcp"), "")])
        report.findings.append(fc.Finding("identity", "pretend", "feature:smcp", 2, fix=harmful))
        fc.prove_fixes(report, ORDER)
        self.assertIs(harmful.safe, False)
        self.assertEqual(fc.safe_fixes(report, ORDER), [])

    def test_the_layout_comparison_sees_order_and_kerning(self):
        lib = fc.fealib()
        one = code(liga=feature("liga", "  sub f i by f_i;\n"), smcp=feature("smcp", "  sub a by a.sc;\n"))
        self.assertTrue(fc.same_layout(lib, one, one.copy(), ORDER))
        kern_a = code(kern=feature("kern", "  pos [a b] [c e] -20;\n"))
        kern_b = code(kern=feature("kern", "  pos [a b] c -20;\n  pos [a b] e -20;\n"))
        kern_c = code(kern=feature("kern", "  pos [a b] [c e] -30;\n"))
        self.assertTrue(fc.same_layout(lib, kern_a, kern_b, ORDER), "the same pairs, written otherwise")
        self.assertFalse(fc.same_layout(lib, kern_a, kern_c, ORDER))

    def test_fixes_in_code_that_does_not_compile_are_not_proven(self):
        c = code(liga=feature("liga", "  sub f i by f_i;\n  sub f i by f_i;\n"), calt=feature("calt", "  sub a' b by\n"))
        report = fc.check(c, ORDER)
        fc.prove_fixes(report, ORDER)
        # (calt set aside: nothing is proven until it is mended; review 11 found classes and lookups a fix
        # changes reaching set-aside code past every finer guard)
        self.assertIsNone(finding(report, "duplicate-rule").fix.safe)
        self.assertIn("mend the errors first", fc.fix_note(finding(report, "duplicate-rule").fix))

    def test_a_fix_to_a_class_that_code_set_aside_uses_is_not_proven(self):
        # (live, 2026-11-17: a CJK font's aalt was set aside, and @aalt2's repeats, which its "sub @aalt by
        # @aalt2;" needs, were removed as "safe", breaking it)
        prefix = DECLARED + "@x = [a b a];\n"
        c = code(prefix, calt=feature("calt", "  sub @x by c;\n  sub a' b by\n"), smcp=feature("smcp", "  sub a by a.sc;\n"))
        report = fc.check(c, ORDER)
        self.assertIsNone(finding(report, "unused-class"), "@x is named by calt, set aside")
        dup = finding(report, "class-duplicates")
        self.assertIsNotNone(dup.fix)
        fc.prove_fixes(report, ORDER)
        self.assertIsNone(dup.fix.safe, "calt uses @x and was not built: nothing proven")
        self.assertEqual(fc.safe_fixes(report, ORDER), [])

    def test_through_another_class_too(self):
        prefix = DECLARED + "@x = [a b a];\n@y = [@x c];\n"
        c = code(prefix, calt=feature("calt", "  sub @y by c;\n  sub a' b by\n"), smcp=feature("smcp", "  sub @x by c;\n"))
        report = fc.check(c, ORDER)
        fc.prove_fixes(report, ORDER)
        self.assertIsNone(finding(report, "class-duplicates").fix.safe)

    def test_fontlab_aalt_with_its_lookups_inside_is_an_error_with_a_repair(self):
        # (FontLab writes its aalt so; neither its compiler, live, nor fontTools takes a lookup in aalt)
        aalt = ("feature aalt useExtension {\n  sub @lc by @sc;\n  lookup aalt_2 useExtension {\n  lookupflag 0;\n"
                "    sub a from [a.sc b.sc];\n  } aalt_2;\n} aalt;\n")
        prefix = DECLARED + "@lc = [a b c];\n@sc = [a.sc b.sc a.sc];\n"
        c = fc.FontCode(prefix, [("aalt", aalt), ("smcp", feature("smcp", "  sub @lc by @sc;\n"))])
        report = fc.check(c, ORDER)
        self.assertEqual(kinds(report), ["aalt-lookups"], [f.message for f in report.findings])
        self.assertFalse(report.built)
        repair = finding(report, "aalt-lookups").fix
        self.assertTrue(repair.repair and repair.review, "for review, never automatic")
        self.assertEqual(fc.safe_fixes(report, ORDER), [])
        mended = fc.apply_fixes(c, [repair])
        self.assertNotIn("lookup", mended.part("feature:aalt"))
        self.assertIn("sub a from [a.sc b.sc];", mended.part("feature:aalt"))
        again = fc.check(mended, ORDER)
        self.assertEqual(again.findings, [], [f.message for f in again.findings])
        self.assertTrue(again.built)
        self.assertEqual([f[2] for f in fc.aalt_lookups(aalt)], ["aalt_2"])

    def test_aalts_repair_keeps_a_rule_after_a_commented_block(self):
        # (review 12: a lookup ending with a comment, a rule after it on the same line)
        aalt = ("feature aalt {\n  lookup aalt_2 {\n    sub a from [a.sc b.sc]; # alternates\n  } aalt_2; sub b from [b.sc];\n"
                "} aalt;\n")
        c = fc.FontCode(DECLARED, [("aalt", aalt)])
        repair = finding(fc.check(c, ORDER), "aalt-lookups").fix
        mended = fc.apply_fixes(c, [repair])
        self.assertIn("\n sub b from [b.sc];", mended.part("feature:aalt"))
        self.assertTrue(fc.check(mended, ORDER).built)

    def test_two_fixes_that_only_work_together_are_not_proven_one_by_one(self):
        # (review 11: @In's and @Out's repeats pair through @Alias; either alone breaks the rule)
        prefix = DECLARED + "@In = [a b a];\n@Out = [a.sc b.sc a.sc];\n@Alias = [@Out];\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  sub @In by @Alias;\n")), ORDER)
        fc.prove_fixes(report, ORDER)
        for f in report.findings:
            if f.kind == "class-duplicates":
                self.assertTrue(f.fix is None or f.fix.safe is not True, f.message)

    def test_a_compact_definition_names_the_class_it_holds(self):
        self.assertIn("@A", fc.part_words("@B=[@A];\nsub x by [@A];\n"))
        self.assertIn("@B", fc.part_words("@B=[@A];\n"))

    def test_a_replacement_class_needs_its_repeats(self):
        prefix = DECLARED + "@lc = [a b c];\n@sc = [a.sc b.sc a.sc];\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  sub @lc by @sc;\n")), ORDER)
        self.assertIsNone(finding(report, "class-duplicates"))

    def test_a_class_defined_twice(self):
        prefix = DECLARED + "@x = [a b];\n@y = [c];\n@x = [a];\n@y = [c];\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  sub @x by a.sc;\n  sub @y by c.sc;\n")), ORDER)
        self.assertEqual(finding(report, "class-redefined").subject, "@x")
        repeated = finding(report, "class-repeated")
        self.assertEqual((repeated.subject, repeated.line), ("@y again", 6))
        self.assertIsNone(finding(report, "unused-class"), "the first one is not also removed as unused")
        fixed = fc.apply_fixes(report.code, fc.safe_fixes(report, ORDER))
        self.assertEqual(fixed.prefix.count("@y = [c];"), 1)
        self.assertEqual(fixed.prefix.count("@x ="), 2, "a class defined differently is left to review")

    def test_a_prefix_copy_unlike_fontlabs_class_can_be_made_the_same_again(self):
        # (the CJK font's @aalt2, its repeats taken out of the prefix copy: "sub @lc by @sc;" no longer read)
        prefix = DECLARED + "@lc = [a b c];\n@sc = [a.sc b.sc];\n"
        c = fc.FontCode(prefix, [("smcp", feature("smcp", "  sub @lc by @sc;\n"))],
                        [("lc", ["a", "b", "c"]), ("sc", ["a.sc", "b.sc", "a.sc"])])
        report = fc.check(c, ORDER)
        redefined = finding(report, "class-redefined")
        self.assertEqual(redefined.subject, "@sc")
        self.assertTrue(redefined.fix.review, "for review, never automatic")
        mended = fc.apply_fixes(c, [redefined.fix])
        self.assertIn("@sc = [a.sc b.sc a.sc];", mended.prefix)
        self.assertTrue(fc.check(mended, ORDER).built)

    def test_fontlab_class_and_its_copy_in_the_prefix_are_not_listed(self):
        c = fc.FontCode(DECLARED + "@figures = [one two];\n", [("onum", feature("onum", "  sub @figures by [one.osf two.osf];\n"))],
                        [("figures", ["one", "two"])])
        self.assertEqual(fc.check(c, ORDER).findings, [])

    def test_a_flag_without_its_class_has_a_fix_to_review(self):
        prefix = DECLARED + "lookup MARKS { lookupflag 16; sub a by a.sc; } MARKS;\n"
        report = fc.check(code(prefix, smcp=feature("smcp", "  lookup MARKS;\n")), ORDER)
        flag = finding(report, "flag")
        self.assertTrue(flag.fix.review)
        self.assertEqual(fc.safe_fixes(report, ORDER), [], "never applied automatically")
        self.assertIn("lookupflag 0;", fc.apply_fixes(report.code, [flag.fix]).prefix)
        self.assertIn("review it", fc.fix_note(flag.fix))
        self.assertTrue(fc.check(fc.apply_fixes(report.code, [flag.fix]), ORDER).built)

    def test_fixes_are_proven_together(self):
        # (one build a fix took a CJK font's 688 fixes 15 minutes in FontLab, live)
        spare = "".join("@s%d = [c];\n" % i for i in range(40))
        c = code(DECLARED + spare, smcp=feature("smcp", "  sub a by a.sc;\n"))
        report = fc.check(c, ORDER)
        built = []
        saved = fc.Compiled.__init__

        def counting(self, *args):
            built.append(1)
            saved(self, *args)
        fc.Compiled.__init__ = counting
        try:
            fc.prove_fixes(report, ORDER)
        finally:
            fc.Compiled.__init__ = saved
        self.assertTrue(all(f.fix.safe for f in report.findings if f.kind == "unused-class"))
        self.assertLessEqual(len(built), 3, "the base and the 40 fixes together")

    def test_a_bad_fix_among_good_ones_is_found_by_halves(self):
        prefix = DECLARED + "@in = [a b a];\n@out = [a.sc b.sc c.sc];\n@other = [c c];\n"
        c = code(prefix, smcp=feature("smcp", "  sub @in by @out;\n  sub @other by c.sc;\n"))
        report = fc.check(c, ORDER)
        fc.prove_fixes(report, ORDER)
        dups = dict((f.subject, f) for f in report.findings if f.kind == "class-duplicates")
        self.assertIsNone(dups["@in"].fix, "breaks the pairing: withdrawn")
        self.assertIs(dups["@other"].fix.safe, True)

    def test_progress_is_reported_by_steps(self):
        seen = []
        c = code(DECLARED + "@s = [c];\n", smcp=feature("smcp", "  sub a by a.sc;\n"), calt=feature("calt", "  sub a' b by\n"))
        fc.check(c, ORDER, lambda what, done, total: seen.append(what))
        clean = code(DECLARED + "@s = [c];\n", smcp=feature("smcp", "  sub a by a.sc;\n"))
        report = fc.check(clean, ORDER)
        fc.safe_fixes(report, ORDER, lambda what, done, total: seen.append(what))
        for what in ("Reading the code", "Compiling", "Proving the fixes"):
            self.assertIn(what, seen)

        def stop(what, done, total):
            raise fc.Stopped()
        self.assertRaises(fc.Stopped, fc.check, c, ORDER, stop)


@unittest.skipUnless(HAS_FONTTOOLS, "fontTools is not installed")
class ChangeTests(unittest.TestCase):
    def test_only_new_errors_count(self):
        before = code(smcp=feature("smcp", "  sub zz by a;\n"))
        after = code(smcp=feature("smcp", "  sub zz by a;\n"), liga=feature("liga", "  sub f l by f_l;\n"))
        self.assertEqual(fc.check_change(before, after, ORDER), ([], []), "the font's own missing glyph is not new")
        worse = code(smcp=feature("smcp", "  sub zz by a;\n"), liga=feature("liga", "  sub f l by f_f_l;\n"))
        errors, _ = fc.check_change(before, worse, ORDER)
        self.assertEqual([f.subject for f in errors], ["f_f_l"])

    def test_a_moved_rule_is_not_new(self):
        before = code(liga=feature("liga", "  sub f i by zz;\n"))
        after = code(liga=feature("liga", "  # moved\n\n  sub f i by zz;\n"))
        self.assertEqual(fc.check_change(before, after, ORDER), ([], []))

    def test_new_warnings_are_told_apart(self):
        before = code(smcp=feature("smcp", "  sub a by a.sc;\n"))
        after = code(smcp=feature("smcp", "  sub a by a.sc;\n  script cyrl;\n  sub b by b.sc;\n"))
        errors, warnings = fc.check_change(before, after, ORDER)
        self.assertEqual(errors, [])
        self.assertEqual([f.kind for f in warnings], ["language"])


class FakeFeatures(object):
    def __init__(self, prefix, features):
        self.prefix, self.features = prefix, list(features)

    def get_prefix(self):
        return self.prefix

    def keys(self):
        return [tag for tag, _ in self.features]

    def get_feature(self, tag):
        return dict(self.features)[tag]


class FakePackage(object):
    def __init__(self, prefix, features, names, groups=()):
        class Glyph(object):
            def __init__(self, name):
                self.name = name

        class Fg(object):
            pass
        self.fgPackage = Fg()
        self.fgPackage.features = FakeFeatures(prefix, features)
        self.fgPackage.glyphs = [Glyph(n) for n in names]
        self.groups = list(groups)

    def getAllGroups(self):
        return self.groups


class FontTests(unittest.TestCase):
    def test_a_font_is_read_with_its_feature_classes_only(self):
        package = FakePackage(DECLARED, [("liga", "feature liga { } liga;")], ORDER,
                              [(False, "figures", 1, 0, ["one", "two"]), (True, "_kern_A", 2, 0, ["a"])])
        c = fc.font_code(package)
        self.assertEqual(c.classes, [("figures", ["one", "two"])], "kerning classes are not feature code")
        self.assertEqual(c.keys(), ["classes", "prefix", "feature:liga"])

    @unittest.skipUnless(HAS_FONTTOOLS, "fontTools is not installed")
    def test_a_writer_is_refused_code_that_brings_an_error(self):
        package = FakePackage(DECLARED, [("liga", feature("liga", "  sub f i by f_i;\n"))], ORDER)
        self.assertIsNone(fc.change_refusal(package, {"smcp": feature("smcp", "  sub a by a.sc;\n")}))
        refusal = fc.change_refusal(package, {"smcp": feature("smcp", "  sub a by a.smcp;\n")})
        self.assertIn("a.smcp is not in the font", refusal)
        self.assertIsNone(fc.change_refusal(package, {"smcp": feature("smcp", "  sub a by a.smcp;\n")},
                                            glyph_order=ORDER + ["a.smcp"]), "a glyph the same write adds")


if __name__ == "__main__":
    unittest.main()
