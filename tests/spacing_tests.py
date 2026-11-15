"""Tests of FreeLab's auto spacing: the suggestions and how composites follow. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "spacing"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
import freelab_auto_kerning as ak  # noqa: E402
import freelab_auto_spacing as sp  # noqa: E402


class ReferenceTests(unittest.TestCase):
    MODEL = {"references": {"H": {"by": "height", "height_of": "H", "left": 0.08, "right": 0.075},
                            "o": {"by": "width", "height_of": "x", "left": 0.2, "right": 0.2}}}

    def test_unspaced(self):
        self.assertTrue(sp.unspaced(0, 40, 1000), "a side at its ink")
        self.assertTrue(sp.unspaced(10, 50, 1000), "one side five times the other")
        self.assertFalse(sp.unspaced(50, 55, 1000))
        self.assertFalse(sp.unspaced(25, 30, 1000), "tight is not unspaced")

    def test_reference_changes_from_the_corpus(self):
        self.assertEqual(sp.reference_changes(u"H", 0, 0, 600, {"H": 700}, self.MODEL), (56, 53))
        self.assertEqual(sp.reference_changes(u"o", 10, 30, 400, {"x": 500}, self.MODEL), (70, 50), "by its ink's width")
        self.assertIsNone(sp.reference_changes(u"n", 0, 0, 400, {"x": 500}, self.MODEL), "not in the model")
        self.assertIsNone(sp.reference_changes(u"H", 0, 0, 600, {}, self.MODEL), "no cap height")


class _Box(object):
    def __init__(self, left, right):
        self.l, self.r = left, right

    def left(self):
        return self.l

    def right(self):
        return self.r


class _Shape(object):
    def __init__(self, left, right):
        self.boundingBox = _Box(left, right)


class _Layer(object):
    def __init__(self, width, *boxes):
        self.advanceWidth = width
        self.shapes = [_Shape(*box) for box in boxes]


class OverhangTests(unittest.TestCase):
    def test_a_horn_past_a_tighter_width_is_caught(self):
        horned = _Layer(600, (40, 560), (520, 640))  # O, and a horn 40 units past its width
        self.assertEqual(sp.mark_overhang(horned, -10, -30), 20.0, "sticks out 20 units further once tighter")
        self.assertEqual(sp.mark_overhang(horned, 10, 30), 0.0, "looser: no further")

    def test_each_side_is_weighed_against_itself(self):
        mark = _Layer(500, (40, 460), (-30, 480))  # out 30 units on the left already
        self.assertEqual(sp.mark_overhang(mark, 0, -45), 25.0, "grows out 25 units on the right")

    def test_an_accent_over_the_letter_never_overhangs(self):
        acute = _Layer(500, (40, 460), (200, 300))
        self.assertEqual(sp.mark_overhang(acute, -20, -40), 0.0)


class SpacingTests(unittest.TestCase):
    def test_each_side_takes_what_its_reference_pair_asks(self):
        # T's right side wants 30 units less beside H; its left side 12 more; a's sides beside n
        wants = {(u"T", u"H"): -30, (u"H", u"T"): 12, (u"a", u"n"): 4, (u"n", u"a"): None}
        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500), sp.Spacing(u"a", "a", "lower", 30, 20, 450)]
        sp.suggest_spacing(glyphs, lambda left, right: wants.get((left, right)), ak.kind_character, ak.category)
        t, a = glyphs
        self.assertEqual((t.left_change, t.right_change), (12, -30))
        self.assertEqual((a.left_change, a.right_change), (None, 4))
        self.assertEqual(t.changes(6), (12, -30))
        self.assertEqual(a.changes(6), (0, 0), "4 units is within the tolerance; an unmeasured side stays")
        self.assertTrue(t.listed(6))
        self.assertFalse(a.listed(6))

    def test_references_by_kind(self):
        self.assertEqual(sp.reference_for(ak.kind_character(u"\N{LATIN CAPITAL LETTER O WITH STROKE}"), ak.category), u"H")
        self.assertEqual(sp.reference_for(u"g", ak.category), u"n")
        self.assertEqual(sp.reference_for(u"7", ak.category), u"0")
        self.assertEqual(sp.reference_for(u"?", ak.category), u"n", "punctuation sits among lowercase most")

    def test_other_scripts_take_their_own_references(self):
        vo, small_vo = u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}"
        refs = lambda ch: sp.reference_for(ak.kind_character(ch), ak.category, ak.script_of)
        self.assertEqual(refs(u"\N{ARMENIAN CAPITAL LETTER BEN}"), vo)
        self.assertEqual(refs(u"\N{ARMENIAN SMALL LETTER BEN}"), small_vo)
        self.assertEqual(refs(ak.unichr_(0x1C91)), ak.unichr_(0x1C98), "Mtavruli against Mtavruli in")
        self.assertEqual(refs(u"\N{GEORGIAN LETTER BAN}"), u"\N{GEORGIAN LETTER IN}")
        self.assertEqual(refs(u"\N{HIRAGANA LETTER KA}"), u"\N{KATAKANA LETTER RO}")
        self.assertEqual(refs(u"\N{CYRILLIC CAPITAL LETTER ZHE}"), u"\N{CYRILLIC CAPITAL LETTER EN}")
        self.assertEqual(refs(u"\N{CYRILLIC SMALL LETTER ZHE}"), u"\N{CYRILLIC SMALL LETTER EN}")
        self.assertEqual(refs(u"\N{GREEK CAPITAL LETTER SIGMA}"), u"\N{GREEK CAPITAL LETTER ETA}")
        self.assertEqual(refs(u"\N{GREEK SMALL LETTER LAMDA}"), u"\N{GREEK SMALL LETTER ETA}")
        self.assertEqual(refs(u"\N{DEVANAGARI LETTER KA}"), u"\N{DEVANAGARI LETTER NA}")
        self.assertEqual(refs(u"\N{HEBREW LETTER BET}"), u"\N{HEBREW LETTER HE}")
        self.assertEqual(refs(u"\N{THAANA LETTER BAA}"), u"\N{THAANA LETTER NOONU}")
        for script in ("cyrillic", "greek", "devanagari", "hebrew", "thaana"):
            for straight in sp.SCRIPT_SPACING_REFERENCES[script].values():
                self.assertIn(straight, sp.ROUND_REFERENCES, "each straight reference has its round one")
        self.assertEqual(refs(u"T"), u"H", "Latin as before")
        self.assertEqual(sp.reference_for(u"T", ak.category), u"H", "without script_of: Latin's")
        self.assertEqual(sp.ROUND_REFERENCES[small_vo], u"\N{ARMENIAN SMALL LETTER OH}")
        fixed = sp.fixed_characters(ak)
        for ch in (u"H", small_vo, u"\N{GEORGIAN LETTER ON}", u"\N{HIRAGANA LETTER NO}"):
            self.assertIn(ch, fixed, "a reference is never changed")

    def test_letters_of_every_script_auto_kerning_knows(self):
        class Group(object):
            currentIndex = 0  # Letters

        class Dialog(object):
            group, package = Group(), None

        dialog = Dialog()
        dialog.ak = ak
        characters = getattr(sp.AutoSpacingDialog.characters, "__func__", sp.AutoSpacingDialog.characters)
        letters = characters(dialog)
        for ch in (u"\N{CYRILLIC CAPITAL LETTER ZHE}", u"\N{GREEK SMALL LETTER LAMDA}", u"\N{DEVANAGARI LETTER KA}",
                   u"\N{HEBREW LETTER BET}", u"\N{THAANA LETTER BAA}", u"\N{ARMENIAN SMALL LETTER BEN}", u"T"):
            self.assertIn(ch, letters, "live, Noto Sans listed no Cyrillic or Greek letter under Letters")
        self.assertEqual(len(letters), len(set(letters)), "each once")
        Group.currentIndex = 2  # Letters, figures, and punctuation
        punctuation = characters(dialog)
        self.assertIn(u"\N{HEBREW PUNCTUATION MAQAF}", punctuation)
        self.assertIn(u"\N{DEVANAGARI DANDA}", punctuation)

    def test_references_to_space_by_script(self):
        vo, small_vo, oh = u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}", u"\N{ARMENIAN SMALL LETTER OH}"
        sides = {u"H": ("H", 50, 50, 700), u"n": ("n", 40, 38, 500), u"o": ("o", 35, 35, 500),
                 vo: ("Vo", 0, 0, 600), small_vo: ("vo", 40, 40, 500), oh: ("oh", 36, 36, 500)}
        self.assertEqual(sp.references_to_space(sides, 1000), [vo, small_vo, oh], "Armenian's capital vo is unspaced")
        sides[vo] = ("Vo", 50, 50, 600)
        self.assertEqual(sp.references_to_space(sides, 1000), [])
        sides[u"n"] = ("n", 0, 2, 500)
        self.assertEqual(sp.references_to_space(sides, 1000), [u"H", u"n", u"o"], "Latin's alone")

    def test_changes_settle_in_one_analysis(self):
        # the methods want T's right side 40 units tighter and its left side 30 looser, but each measure
        # closes half of a tightening (halfkern's factor): measured once, T's right side moves 20;
        # spaced again it would ask for 10 more, then 5: the several clicks the list took
        targets = {("T", "right"): -40, ("T", "left"): 30, ("a", "right"): -9}

        def measure_at(moved):
            def measure(left, right):
                glyph, side = (right, "left") if left in u"Hn" else (left, "right")
                if (glyph, side) not in targets:
                    return None
                done = moved.get(glyph, (0, 0))[0 if side == "left" else 1]
                gap = targets[(glyph, side)] - done
                return int(gap * (0.5 if gap < 0 else 1.0))  # (truncated: the same in Python 2 and 3)
            return measure

        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500), sp.Spacing(u"a", "a", "lower", 30, 20, 450)]
        sp.suggest_spacing(glyphs, measure_at({}), ak.kind_character, ak.category)
        t, a = glyphs
        self.assertEqual((t.left_change, t.right_change), (30, -20), "one measure: half of the tightening")
        passes = sp.settle_spacing(glyphs, measure_at, ak.kind_character, ak.category, settle=2)
        self.assertEqual((t.left_change, t.right_change), (30, -38), "measured again until the step is under 2 units")
        self.assertEqual(a.right_change, -7)
        self.assertEqual(passes, 5)
        self.assertEqual(measure_at({"T": (30, -38)})(u"T", u"H"), -1, "the next analysis asks nothing worth listing")
        capped = [sp.Spacing(u"T", "T", "upper", 20, 25, 500)]
        sp.suggest_spacing(capped, measure_at({}), ak.kind_character, ak.category)
        self.assertEqual(sp.settle_spacing(capped, measure_at, ak.kind_character, ak.category, settle=2, passes=2), 2)
        self.assertEqual(capped[0].right_change, -30, "the passes are capped")

    def test_a_side_that_overshoots_takes_half_the_way_back(self):
        def measure_at(moved):
            done = moved.get("T", (0, 0))[1]
            return lambda left, right: (12 if done else -40) if left == u"T" else None  # past its target after a step
        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500)]
        sp.suggest_spacing(glyphs, measure_at({}), ak.kind_character, ak.category)
        self.assertEqual(sp.settle_spacing(glyphs, measure_at, ak.kind_character, ak.category, settle=2), 2)
        self.assertEqual(glyphs[0].right_change, -34, "-40, then half of the 12 back: it settles between")
        self.assertIsNone(glyphs[0].left_change, "an unmeasured side stays unmeasured")

    def test_apply_note_says_what_one_click_took(self):
        self.assertEqual(sp.apply_note(1, 0, 6), u"")
        self.assertEqual(sp.apply_note(2, 1, 6),
                         u"It took 2 passes: measured again after spacing, 1 glyph still had a side 6 units or more off, "
                         u"and was spaced again (the measuring's pixels round each change a little).")
        self.assertIn(u"the other 20 glyphs measured against them again", sp.apply_note(1, 0, 6, 20))

    def test_composites_follow_their_base(self):
        composites = {"eacute": ("e", ["acute"]), "ecircumflexacute": ("ecircumflex", ["acute"]),
                      "ecircumflex": ("e", ["circumflex"]), "f_e": ("f", ["e"]), "aacute": ("a", ["acute"])}
        moves = sp.composite_moves(composites, {"e": (5, -3), "f": (2, 2)})
        self.assertEqual(moves["eacute"], (5, 2), "its accent moves with the e's outline; its width follows")
        self.assertEqual(moves["ecircumflexacute"], (5, 2), "built on a composite that follows")
        self.assertIsNone(moves["f_e"], "two of its letters changed: left for a look")
        self.assertNotIn("aacute", moves)


class TableTests(unittest.TestCase):
    """The owner: "Maybe this table should be aligned in terms of layout with the other ones?" The glyph
    drawn from the font beside its character, its name, its code point, then its numbers."""

    def dialog(self):
        dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)  # (its window needs FontLab: its rows do not)
        dialog.ak = ak
        return dialog

    def test_a_rows_cells(self):
        s = sp.Spacing(u"\N{LATIN CAPITAL LETTER A WITH GRAVE}", u"Agrave", "upper", 12.4, 30, 600)
        s.left_change, s.right_change = -8, 0
        texts = self.dialog().row_texts(s, 6)
        self.assertEqual(texts, [u"\N{LATIN CAPITAL LETTER A WITH GRAVE}", u"Agrave", u"U+00C0", u"12", u"-8", u"30",
                                 u"0", u"592"])
        self.assertEqual(len(texts), len(sp.AutoSpacingDialog.COLUMNS))
        s.reference = True
        self.assertEqual(self.dialog().row_texts(s, 6)[1], u"Agrave (reference)", "said in its name's cell")

    def test_the_columns_match_the_other_tools(self):
        self.assertEqual(sp.AutoSpacingDialog.COLUMNS[:3], ("Glyph", "Name", "Unicode"))
        self.assertEqual([sp.AutoSpacingDialog.COLUMNS[c] for c in sp.AutoSpacingDialog.NUMBERS],
                         ["Left now", "Left change", "Right now", "Right change", "Width"], "the numbers, right-aligned")
        self.assertEqual(ak.glyph_icon_size(), (int(ak.GLYPH_ICON_SIZE * 1.6), int(ak.GLYPH_ICON_SIZE * 1.45)))
        self.assertEqual(ak.unicode_label(0xC0), u"U+00C0")
        self.assertEqual(ak.unicode_label(0x1F600), u"U+1F600")
        self.assertEqual(ak.unicode_label(None), u"")

    def test_a_closed_font_empties_the_window(self):
        dialog = self.dialog()
        runs = []
        dialog.run = lambda: runs.append(1)
        dialog.spaced = [u"A"]
        dialog.font_changed()
        self.assertEqual((runs, dialog.spaced), ([1], []), "measured anew (or the no-font line), nothing left to check")


class HistoryFailureTests(unittest.TestCase):
    """Review of 2026-11-15: a failed History record before the write let Auto Spacing write anyway, and a
    failed step after it was followed by "Edit > Undo takes it back"."""

    def setUp(self):
        self.saved = getattr(sys, "_freelab_history", None)
        sys._freelab_history = None
        self.addCleanup(lambda: setattr(sys, "_freelab_history", self.saved))

    def dialog(self, refuse_before, refuse_after):
        steps = []

        class Items(object):
            def notifyChangesApplied(self, title, objects, recursive):
                if (refuse_before if title.endswith(u"(before)") else refuse_after):
                    raise RuntimeError("History refused")
                steps.append(title)

            def notifyPackageContentUpdated(self, key):
                pass

        class Package(object):
            master, glyphsCount, path, id = "Regular", 1, u"a.vfc", 21
            fgPackage = type("Fg", (), {"id": 21})()

            def currentHistoryState(self):
                return 0

            def initialHistoryState(self):
                return 0

            def setFlag(self, flag, value):
                pass

        dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)
        dialog.ak, dialog.busy, dialog.package, dialog.master = ak, False, Package(), "Regular"
        dialog.fontlab = type("FontLab", (), {"flItems": Items()})()
        dialog.logged, dialog.writes = [], []
        dialog.log = type("Log", (), {"add": lambda _, text, kind="info": dialog.logged.append((kind, text))})()
        dialog.harvest = dialog.run = lambda: None
        dialog.current_font = lambda: dialog.package
        dialog.tolerance = type("Box", (), {"value": 6})()
        dialog.follow = type("Box", (), {"checked": False})()
        row = sp.Spacing(u"T", "T", "upper", 20, 25, 500)
        row.checked = True
        dialog.listed = [row]

        def write_spacings(rows, tolerance, totals):
            dialog.writes.append([s.name for s in rows])
            totals["T"] = (0, -5)
            return [], 0
        dialog.write_spacings = write_spacings
        return dialog, steps

    def test_nothing_is_written_when_the_font_cannot_be_recorded_first(self):
        dialog, steps = self.dialog(refuse_before=True, refuse_after=False)
        dialog.apply()
        self.assertEqual(dialog.writes, [], "no glyph changed")
        self.assertEqual(steps, [])
        self.assertEqual([kind for kind, _ in dialog.logged], ["error"])
        self.assertIn(u"Nothing was changed", dialog.logged[0][1])

    def test_a_step_not_recorded_promises_no_undo(self):
        dialog, steps = self.dialog(refuse_before=False, refuse_after=True)
        dialog.apply()
        self.assertEqual(dialog.writes, [["T"]])
        self.assertFalse(any(u"Undo</i> (or" in text for _, text in dialog.logged), dialog.logged)
        errors = [text for kind, text in dialog.logged if kind == "error"]
        self.assertEqual(len(errors), 1, dialog.logged)
        self.assertIn(u"cannot take it back", errors[0])

    def test_a_recorded_write_promises_undo(self):
        dialog, steps = self.dialog(refuse_before=False, refuse_after=False)
        dialog.apply()
        self.assertEqual(steps, [u"FreeLab Auto Spacing (before)", u"FreeLab Auto Spacing"])
        self.assertTrue(any(u"<i>Edit &gt; Undo</i> (or the <i>History</i> panel) takes it back." in text
                            for _, text in dialog.logged), dialog.logged)
        self.assertEqual([kind for kind, _ in dialog.logged if kind == "error"], [])


class WordingTests(unittest.TestCase):
    """The owner's rules for interface texts, read from the script (its dialog needs FontLab)."""

    def source(self):
        import io
        with io.open(sp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            return handle.read()

    def test_no_dash_or_dot_between_data(self):
        escaped = [u" \\" + code + u" " for code in (u"N{EM DASH}", u"N{MIDDLE DOT}", u"u2014", u"u00b7", u"xb7")]
        for mark in escaped + [u" \N{EM DASH} ", u" \N{MIDDLE DOT} "]:
            self.assertNotIn(mark, self.source())

    def test_a_check_box_label_takes_no_period(self):
        import re
        self.assertEqual(re.findall(u"QCheckBox\\(u?\"[^\"]*\\.\"\\)", self.source()), [])
        self.assertIn(u"QCheckBox(\"Glyphs built from components follow the glyphs they are built on\")", self.source())

    def test_the_units_box_follows_its_number(self):
        self.assertNotIn(u"setSuffix(", self.source(), "ak.counted_suffix sets it: 1 unit, 2 units")
        self.assertIn(u"counted_suffix(self.tolerance, u\"unit\")", self.source())

    def test_the_log_counts(self):
        self.assertIn(u"1 glyph still had a side 1 unit or more off, and was spaced again", sp.apply_note(2, 1, 1))
        self.assertIn(u"2 glyphs still had a side 2 units or more off, and were spaced again", sp.apply_note(3, 2, 2))
        self.assertEqual(sp.apply_note(1, 0, 2), u"")


if __name__ == "__main__":
    unittest.main()
