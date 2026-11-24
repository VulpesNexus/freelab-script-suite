"""Tests of FreeLab's auto kerning: the native core on synthetic glyphs, and the arithmetic around it.

The core's tests need its DLL (tools/build-native.ps1 -Kern, or the installer). Without it they are
skipped, and run_tests.py reports the skip. Valid Python 2.7 and Python 3.
"""

from __future__ import absolute_import, division, print_function

import ctypes
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
import freelab_auto_kerning as ak  # noqa: E402
import qtfakes  # noqa: E402  (beside this file: the Cancel button's fakes, shared by every tool's tests)

try:
    CORE = ak.Core()
except Exception:
    CORE = None

HEIGHT = 60  # the ink's height, in pixels
PAD = 30  # room around the ink


def stems(name, widths, gaps, left_bearing, right_bearing, rows=(0, HEIGHT)):
    """A glyph of solid vertical stems (widths, separated by gaps), with its sidebearings in pixels;
    rows: the ink's top and bottom rows, counted down from the ink's top (all of it by default)."""
    ink = sum(widths) + sum(gaps)
    width = PAD + left_bearing + ink + right_bearing + PAD
    height = HEIGHT + 2 * PAD
    data = (ctypes.c_uint8 * (width * height))()
    x = PAD + left_bearing
    for index, stem in enumerate(widths):
        for column in range(x, x + stem):
            for row in range(PAD + rows[0], PAD + rows[1]):
                data[row * width + column] = 255
        x += stem + (gaps[index] if index < len(gaps) else 0)
    advance = left_bearing + ink + right_bearing
    return ak.Glyph(name, data, width, height, width, PAD, advance)


def stem(name, left_bearing=10, right_bearing=10, width=10):
    return stems(name, [width], [], left_bearing, right_bearing)


class MissingReferenceTests(unittest.TestCase):
    def test_all_missing_names_none(self):
        text = ak.missing_references(object(), ak.TUNING, list(ak.TUNING), u"Auto Kerning", u"their spacing sets the kerning")
        self.assertEqual(text, u"Auto Kerning needs l, n, and o: their spacing sets the kerning.")

    def test_some_missing_are_named(self):
        text = ak.missing_references(object(), ak.TUNING, [u"l", u"o"], u"Auto Kerning", u"their spacing sets the kerning")
        self.assertTrue(text.startswith(u"This font has no \N{LEFT DOUBLE QUOTATION MARK}l\N{RIGHT DOUBLE QUOTATION MARK} or "), text)
        self.assertIn(u"Auto Kerning needs l, n, and o", text)


class ArithmeticTests(unittest.TestCase):
    def test_units_halve_tightenings_as_halfkern_does(self):
        self.assertEqual(ak.to_units(-10.0, 200, 1000), -25)  # -50 units, halved
        self.assertEqual(ak.to_units(4.0, 200, 1000), 20)  # loosenings in full

    def test_factors_follow_the_fonts_kerning(self):
        samples = [(-100, -80), (-50, -40), (-20, -16), (30, 30)]
        tighten, loosen = ak.fit_factors(samples)
        self.assertAlmostEqual(tighten, 0.8)
        self.assertEqual(loosen, ak.LOOSEN, "one loosening is too few: halfkern's factor")

    def test_factors_stay_in_range(self):
        tighten, _ = ak.fit_factors([(-10, -500), (-20, -900), (-5, -300)])
        self.assertEqual(tighten, ak.FACTOR_RANGE[1])

    def test_spread_and_average_of_the_methods(self):
        self.assertEqual(ak.spread([-40, -60, None]), 20)
        self.assertEqual(ak.spread([-40]), 0)
        self.assertEqual(ak.average([-40, -61]), -50)  # -50.5, halves up in both Pythons
        self.assertIsNone(ak.average([None, None]))

    def test_contour_distance_has_its_own_default_strength(self):
        self.assertEqual(ak.fit_factors([], ak.DEFAULT_FACTORS["contour"]), (1.0, 1.0))
        self.assertEqual(ak.fit_factors([]), (ak.TIGHTEN, ak.LOOSEN))

    def test_common_pairs_are_ranked_without_the_notice(self):
        ranks = ak.common_pairs(os.path.join(HERE, os.pardir, "kerning", ak.COMMON_PAIRS_FILE))
        self.assertGreater(len(ranks), 3000)
        self.assertTrue(all(len(pair) == 2 and not pair.startswith(u"#") for pair in ranks))
        self.assertLess(ranks[u"To"], ranks[u"fj"], "To is more relevant")
        self.assertEqual(ak.common_pairs(os.path.join(HERE, "no such file")), {})

    def test_a_pair_can_use_another_method(self):
        s = ak.Suggestion(u"T", u"o", "T", "o", 0)
        s.values = {"halfkern": -80, "contour": -120, "fontlab": -56}
        self.assertEqual(s.to_write("average"), -100)
        s.override = "fontlab"
        self.assertEqual(s.to_write("average"), -56, "the pair's own choice wins")
        s.override = "current"
        self.assertEqual(s.to_write("halfkern"), 0)

    def test_no_qt_name_fontlabs_pythonqt_lacks(self):
        # QPalette.PlaceholderText (Qt 5.12) is missing from FontLab 7's PythonQt: asking for it
        # mid-painting left a painter open on a freed pixmap, and FontLab aborted.
        source = io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        self.assertNotIn("QPalette.PlaceholderText)", source)

    def test_the_cache_is_named_by_a_hash_and_survives_a_round_trip(self):
        import shutil
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-kern-cache-")
        try:
            old = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = folder
            try:
                path = ak.cache_path(u"fonts/Secret Name.vfc", u"Regular")
            finally:
                if old is None:
                    del os.environ["LOCALAPPDATA"]
                else:
                    os.environ["LOCALAPPDATA"] = old
            self.assertNotIn("Secret", path, "no font name or path in the cache's name")
            self.assertEqual(path, ak.cache_path(u"fonts/Secret Name.vfc", u"Regular").replace(
                ak.state_dir(), os.path.join(folder, u"FreeLab")))
            data = {"method": ak.method_fingerprint(), "pairs": {u"T o": [-80.5, -120.0, None]}}
            ak.save_cache(path, data)
            self.assertEqual(ak.load_cache(path), data)
            self.assertIsNone(ak.load_cache(path + u".missing"))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def test_a_glyph_signature_follows_its_outline_and_width(self):
        class Element(object):
            def __init__(self, kind, x, y):
                self.type, self.x, self.y = kind, x, y

        class Path(object):
            def __init__(self, points):
                self.points = points

            def elementCount(self):
                return len(self.points)

            def elementAt(self, index):
                return Element(*self.points[index])

        square = [(0, 0, 0), (1, 100, 0), (1, 100, 100), (1, 0, 100)]
        moved = [(0, 0, 0), (1, 101, 0), (1, 100, 100), (1, 0, 100)]
        self.assertEqual(ak.path_signature(Path(square), 500), ak.path_signature(Path(list(square)), 500))
        self.assertNotEqual(ak.path_signature(Path(square), 500), ak.path_signature(Path(moved), 500))
        self.assertNotEqual(ak.path_signature(Path(square), 500), ak.path_signature(Path(square), 510))

    def test_learned_trees_are_walked_as_scikit_learn_does(self):
        # one tree: feature 0 at most -0.05 goes left (-0.04), above it right (0.0); missing goes right
        stage = {"baseline": -0.01, "trees": [[[0, -0.05, 0, 1, 2, 0, 0.0], [0, 0, 0, 0, 0, 1, -0.04], [0, 0, 0, 0, 0, 1, 0.0]]]}
        self.assertAlmostEqual(ak.tree_sum(stage, [-0.1]), -0.05)
        self.assertAlmostEqual(ak.tree_sum(stage, [-0.05]), -0.05, msg="at the threshold: left")
        self.assertAlmostEqual(ak.tree_sum(stage, [0.2]), -0.01)
        self.assertAlmostEqual(ak.tree_sum(stage, [None]), -0.01, msg="a missing feature follows the node's side")
        # two stages: kerned when the classifier's probability reaches the cut (feature 0 below 0 here)
        classifier = {"baseline": 0.0, "trees": [[[0, 0.0, 0, 1, 2, 0, 0.0], [0, 0, 0, 0, 0, 1, 2.0], [0, 0, 0, 0, 0, 1, -2.0]]]}
        model = {"cut": 0.4, "classifier": classifier, "regressor": stage}
        self.assertAlmostEqual(ak.predict(model, [-0.1]), -0.05)
        self.assertEqual(ak.predict(model, [0.2]), 0.0, "not kerned: 0")
        self.assertIsNone(ak.learned_model(os.path.join(HERE, "no such model.json")))

    def test_first_halo_is_halfkerns(self):
        self.assertEqual(ak.first_bias(100), 10)  # halfkern: kernel 21 pixels at 100 pixels per em
        self.assertEqual(ak.first_bias(200), 20)


class FakeKerningObject(object):
    def __init__(self, name, is_class):
        self.id, self.mode = name, "groupMode" if is_class else "glyphMode"


class FakeKerningPair(object):
    def __init__(self, entry):
        self.left, self.right = FakeKerningObject(*entry[0]), FakeKerningObject(*entry[1])


class FakeKerning(object):
    """fgKerning as FontLab 7 behaves (found live): a name written means a class when a class has
    that name, and getPlainPairsDict() resolves classes, the most specific entry winning."""

    def __init__(self, groups, entries):
        self.groups = FakeGroups(groups)
        self.stored = dict(entries)  # ((left, is class), (right, is class)): value

    def keys(self):
        return [FakeKerningPair(entry) for entry in self.stored]

    def items(self):
        return [(FakeKerningPair(entry), value) for entry, value in self.stored.items()]

    def entry(self, key):
        return tuple((name, name in self.groups.data) for name in key)

    def __setitem__(self, key, value):
        self.stored[self.entry(key)] = value

    def remove(self, key):
        del self.stored[self.entry(key)]

    renames = None

    def renameGroup(self, old, new):
        self.renames = (self.renames or []) + [(old, new)]
        self.groups.data[new] = self.groups.data.pop(old)
        self.stored = dict((tuple((new if (name, is_class) == (old, True) else name, is_class) for name, is_class in entry), value)
                           for entry, value in self.stored.items())

    def getPlainPairsDict(self):
        kerning = ak.FontKerning.__new__(ak.FontKerning)  # the same class lookup, on these groups
        kerning.left_class, kerning.right_class = {}, {}
        for name, (members, side) in self.groups.data.items():
            for member in members:
                if side in ak.CLASS_SIDES["left"]:
                    kerning.left_class.setdefault(member, name)
                if side in ak.CLASS_SIDES["right"]:
                    kerning.right_class.setdefault(member, name)
        glyphs = set(m for members, _ in self.groups.data.values() for m in members) | set(
            name for entry in self.stored for name, is_class in entry if not is_class)
        plain = {}
        for left in glyphs:
            for right in glyphs:
                for entry in kerning.candidates(left, right):
                    if entry in self.stored:
                        plain[(left, right)] = self.stored[entry]
                        break
        return plain


class FakeGroups(object):
    def __init__(self, data):
        self.data = data

    def items(self):
        return list(self.data.items())

    def __setitem__(self, name, value):
        self.data[name] = (list(value[0]), value[1])


class FlagCellTests(unittest.TestCase):
    def test_segments(self):
        self.assertEqual(ak.flag_segments(u"#eb3c3c", 10, 100), [(10, 100, u"#eb3c3c")], "one glyph: the whole cell")
        self.assertEqual(ak.flag_segments(u"#eb3c3c,#3c3ceb", 10, 100), [(10, 50, u"#eb3c3c"), (60, 50, u"#3c3ceb")],
                         "a pair: each glyph's flag on its half")
        self.assertEqual(ak.flag_segments(u",#3c3ceb", 0, 101), [(50, 51, u"#3c3ceb")], "only the right one flagged")
        self.assertEqual(ak.flag_segments(None, 0, 100), [])

    def test_colors_text(self):
        saved = ak.flag_color
        try:
            ak.flag_color = lambda mark, alpha=255: type("C", (), {"name": lambda self: u"#%06d" % mark})()
            self.assertEqual(ak.flag_colors_text([1, 241]), u"#000001,#000241")
            self.assertEqual(ak.flag_colors_text([0, 241]), u",#000241")
            self.assertIsNone(ak.flag_colors_text([0, 0]))
        finally:
            ak.flag_color = saved


class KerningClassTests(unittest.TestCase):
    GROUPS = {"T": (["T", "Tcaron"], "KernBothSide"), "o": (["o", "oacute"], "KernLeft"),
              "o1": (["o", "oacute"], "KernRight"), "A": (["A", "Aacute"], "KernLeft")}

    def kerning(self, entries):
        return ak.FontKerning(FakeKerning(dict(self.GROUPS), entries))

    def test_current_values_include_class_kerning(self):
        k = self.kerning({(("T", True), ("o1", True)): -172, (("T", False), ("oacute", False)): -150})
        self.assertEqual(k.current("T", "o"), -172, "from the classes' pair")
        self.assertEqual(k.current("T", "oacute"), -150, "a glyph pair wins over its classes'")
        self.assertEqual(k.current("o", "T"), 0)

    def test_a_pair_is_written_where_its_value_comes_from(self):
        k = self.kerning({(("T", True), ("o1", True)): -172})
        self.assertEqual(k.target("T", "o"), ((("T", True), ("o1", True)), True), "its classes' pair")
        self.assertEqual(k.reach(k.target("T", "o")[0]), 4)
        self.assertEqual(k.target("V", "o"), ((("V", False), ("o1", True)), True), "no class on the left: the glyph")

    def test_a_glyph_named_like_a_class_is_written_with_the_class_out_of_the_way(self):
        # kerning[("A", "V")] would write class A: the class is renamed while the glyph pair is written
        k = self.kerning({(("A", False), ("V", False)): -50})
        entry, remove = k.target("A", "V")
        self.assertEqual(entry, (("A", False), ("V", False)))
        self.assertEqual(k.hidden(entry), ["A"])
        k.write(entry, -70, remove)
        self.assertEqual(k.kerning.stored[entry], -70)
        self.assertNotIn((("A", True), ("V", False)), k.kerning.stored, "class A untouched")
        self.assertIn("A", k.kerning.groups.data, "and named A again")
        self.assertEqual(k.kerning.renames, [("A", "A__freelab"), ("A__freelab", "A")])

    def test_an_entry_lists_the_glyph_pairs_it_kerns(self):
        k = self.kerning({})
        self.assertEqual(k.pairs((("T", True), ("o1", True))),
                         [("T", "o"), ("T", "oacute"), ("Tcaron", "o"), ("Tcaron", "oacute")])
        self.assertEqual(k.reach((("V", False), ("o1", True))), 2)

    def test_a_zero_removes_an_entry_unless_a_class_pair_lies_below(self):
        k = self.kerning({(("Tcaron", False), ("o1", True)): -20, (("T", True), ("o1", True)): -172})
        entry, remove = k.target("Tcaron", "o")
        self.assertEqual(entry, (("Tcaron", False), ("o1", True)))
        self.assertFalse(remove, "removing it would leave the class value: 0 is written")
        k.write(entry, 0, remove)
        self.assertEqual(ak.FontKerning(k.kerning).current("Tcaron", "o"), 0)
        entry, remove = k.target("T", "o")
        k.write(entry, 0, remove)
        self.assertNotIn(entry, k.kerning.stored, "the last entry for the pair: removed")

    def test_a_zero_keeps_an_entry_whose_other_pairs_would_take_another_value(self):
        # glyph A against class R (V, W) -50, class L (A) against glyph W -80: a 0 written through A/V
        # also sets A/W, which removing the entry would hand to L against W
        groups = {"L": (["A"], "KernLeft"), "R": (["V", "W"], "KernRight")}
        k = ak.FontKerning(FakeKerning(groups, {(("A", False), ("R", True)): -50, (("L", True), ("W", False)): -80}))
        entry, remove = k.target("A", "V")
        self.assertEqual(entry, (("A", False), ("R", True)))
        self.assertFalse(remove, "A/W would become -80")
        k.write(entry, 0, remove)
        after = ak.FontKerning(k.kerning)
        self.assertEqual((after.current("A", "V"), after.current("A", "W")), (0, 0))
        k = ak.FontKerning(FakeKerning(groups, {(("A", False), ("R", True)): -50, (("A", False), ("W", False)): -10,
                                                (("L", True), ("W", False)): -80}))
        self.assertEqual(k.target("A", "V"), ((("A", False), ("R", True)), True), "A/W has its own entry: removed")

    def test_a_spare_class_name_is_never_a_name_of_the_entry(self):
        # class A renamed to A__freelab would turn the glyph A__freelab of the pair into that class
        groups = {"A": (["A", "Aacute"], "KernLeft")}
        k = ak.FontKerning(FakeKerning(groups, {}))
        entry = (("A", False), ("A__freelab", False))
        self.assertEqual(k.hidden(entry), ["A"])
        k.write(entry, -30, False)
        self.assertEqual(k.kerning.stored, {entry: -30}, "two glyphs, not glyph A against class A")
        self.assertEqual(k.kerning.renames, [("A", "A__freelab_"), ("A__freelab_", "A")])
        self.assertIn("A", k.kerning.groups.data)


@unittest.skipIf(CORE is None, "auto kerning core not built: run tools/build-native.ps1 -Kern (%s)" % ak.kern_library_path())
class CoreTests(unittest.TestCase):
    def test_envelope_is_ink_then_a_fading_halo(self):
        glyph = stem("l")
        env = glyph.envelope(CORE, 10)
        row = PAD + HEIGHT // 2
        ink_left = PAD + 10
        self.assertEqual(env[row * glyph.width + ink_left + 2], 255, "full ink")
        self.assertEqual(env[row * glyph.width + ink_left - 5], 63, "half way out: 127, halved")
        self.assertEqual(env[row * glyph.width + ink_left - 10], 0, "the halo's end")
        self.assertEqual(env[row * glyph.width + ink_left - 20], 0)

    def test_no_solid_ink_has_no_envelope(self):
        glyph = stem("blank")
        for i in range(glyph.width * glyph.height):
            glyph.coverage[i] = min(glyph.coverage[i], 200)
        self.assertIsNone(CORE.envelope(glyph, 10))

    def band(self):
        return ak.calibrate(CORE, [stem("l"), stem("n"), stem("o")], 100)

    def test_a_pair_spaced_like_the_tuning_glyphs_needs_no_kerning(self):
        band = self.band()
        self.assertEqual(ak.suggest_pixels(CORE, stem("l"), stem("l"), band), 0.0)

    def test_a_wide_gap_tightens_and_a_tight_one_loosens(self):
        band = self.band()
        wide = ak.suggest_pixels(CORE, stem("wide", right_bearing=25), stem("l"), band)
        wider = ak.suggest_pixels(CORE, stem("wider", right_bearing=30), stem("l"), band)
        tight = ak.suggest_pixels(CORE, stem("tight", right_bearing=0), stem("r", left_bearing=0), band)
        self.assertLess(wide, 0)
        self.assertLess(wider, wide, "a wider gap tightens more")
        self.assertGreater(tight, 0)

    def test_values_are_refined_between_whole_steps(self):
        band = self.band()
        # stems on whole pixels meet a band taken from the same stems exactly: move it off them
        band = ak.Band(band.bias, band.low * 1.07, band.high * 1.07)
        values = set()
        for bearing in range(14, 30):
            value = ak.suggest_pixels(CORE, stem("g%d" % bearing, right_bearing=bearing), stem("l"), band)
            values.add(round(value - int(value), 3))
        self.assertTrue(any(0 < abs(v) < 1 for v in values), "some suggestions fall between whole pixels")

    def test_the_halo_grows_until_the_tuning_glyphs_agree(self):
        narrow = stem("l", left_bearing=4, right_bearing=4)
        wide = stems("n", [10, 10], [12], 6, 6)
        band = ak.calibrate(CORE, [narrow, wide, stem("o")], 100)
        self.assertGreaterEqual(band.bias, ak.first_bias(100))
        self.assertGreater(band.low, band.high / 2)


@unittest.skipIf(CORE is None, "auto kerning core not built: run tools/build-native.ps1 -Kern (%s)" % ak.kern_library_path())
class ContourTests(unittest.TestCase):
    def band(self):
        refs = [stem("l"), stem("n"), stem("o")]
        return ak.contour_band(CORE, refs, refs)

    def suggest(self, left, right, min_gap=0.0):
        return ak.suggest_contour_pixels(CORE, left, right, self.band(), float(PAD), min_gap)

    def test_profiles_find_the_ink_edges(self):
        left, right, limited_left, limited_right = CORE.contours(stem("l"), ak.CONTOUR_SLOPE)
        row = PAD + HEIGHT // 2
        self.assertAlmostEqual(left[row], PAD + 10, places=2)  # where the coverage crosses half (128 of 255)
        self.assertAlmostEqual(right[row], PAD + 20, places=2)
        self.assertGreater(left[0], 1e8, "no ink in the top row")
        self.assertLess(limited_left[0], 1e8, "the limited contour reaches every row")

    def test_a_pair_spaced_like_the_references_needs_no_kerning(self):
        self.assertEqual(self.suggest(stem("l"), stem("l")), 0.0)

    def test_a_wide_gap_tightens_and_a_tight_one_loosens(self):
        wide = self.suggest(stem("wide", right_bearing=25), stem("l"))
        tight = self.suggest(stem("tight", right_bearing=0), stem("r", left_bearing=0))
        self.assertLess(wide, 0)
        self.assertGreater(tight, 0)

    def test_a_tightening_keeps_the_minimum_ink_gap(self):
        far = stem("far", right_bearing=40)
        free = self.suggest(far, stem("l"))
        kept = self.suggest(far, stem("l"), min_gap=25.0)
        self.assertLess(free, kept, "the gap rule stops the tightening early")
        _, raw_right, _, _ = far.contours(CORE)
        raw_left, _, _, _ = stem("l").contours(CORE)
        gap = CORE.closest(raw_right, raw_left, far.height, ak.base_offset(far, stem("l")) - kept)
        self.assertAlmostEqual(gap, 25.0, places=3)

    def test_the_angle_limit_reaches_into_rows_without_ink(self):
        period = stems("period", [8], [], 10, 10, rows=(HEIGHT - 8, HEIGHT))
        _, raw_right, _, limited_right = period.contours(CORE)
        bottom, above = PAD + HEIGHT - 4, PAD + HEIGHT - 4 - 20
        self.assertLess(raw_right[above], -1e8, "no ink 20 rows above the period")
        self.assertAlmostEqual(limited_right[above], raw_right[bottom] - 16 * ak.CONTOUR_SLOPE, places=3)



class ClassSuggestionTests(unittest.TestCase):
    def test_the_classes_window_records_the_font_before_it_writes(self):
        """Kerning Classes said "close it without saving to take it back". Tried live, 2026-11-24: one Edit >
        Undo takes a created class back. Both of its writes begin with the History step Auto Kerning's own
        write begins with, and say Undo takes them back when FontLab recorded the step."""
        import inspect
        window = [value for value in vars(ak).values()
                  if inspect.isclass(value) and hasattr(value, "begin_classes_write")][0]
        for method in (window.apply, window.write_exceptions):
            source = inspect.getsource(method)
            self.assertLess(source.index("self.begin_classes_write(package)"), source.index("FontKerning("))
            self.assertIn("if status.recorded:", source)
            self.assertNotIn("without saving", source)
        self.assertIn(u"Edit &gt; Undo", ak.TAKE_BACK_NOTE)
        calls = []
        saved = ak.begin_write
        ak.begin_write = lambda fontlab, package, title, log: calls.append(title) or False
        self.addCleanup(setattr, ak, "begin_write", saved)
        texts = []
        status = type("S", (), {"text": u"old", "setText": lambda self, text: texts.append(text)})()
        fake = type("W", (), {"owner": type("O", (), {"fontlab": None})(), "status": status})()
        self.assertFalse(window.__dict__["begin_classes_write"](fake, "font"))
        self.assertEqual(calls, [u"FreeLab Auto Kerning"])
        self.assertTrue(texts[0].startswith(u"Nothing was changed"), texts)

    def test_signatures_match_within_the_tolerance(self):
        one = [0.0, -0.05, 0.02, None]
        self.assertTrue(ak.signatures_match(one, [0.01, -0.05, 0.03, 0.2]))
        self.assertFalse(ak.signatures_match(one, [0.0, -0.1, 0.02, None]), "one partner kerned 5% apart")
        self.assertFalse(ak.signatures_match([0.0, None, None, None], [0.0, None, None, None]), "too few partners")
        self.assertAlmostEqual(ak.signature_gap(one, [0.0, -0.08, 0.02, None]), 0.03)

    def test_base_letter(self):
        self.assertEqual(ak.base_letter(u"\u00c1"), u"A")
        self.assertEqual(ak.base_letter(u"\u013f"), u"L", "L with middle dot, a compatibility decomposition")
        self.assertEqual(ak.base_letter(u"\u0141"), u"\u0141", "L with stroke has none")
        self.assertEqual(ak.base_letter(u"."), u".")

    def test_classes_from_the_corpus_and_the_fonts_kerning(self):
        names = {u"o": "o", u"\u00f6": "odieresis", u"\u0151": "ohungarumlaut", u"c": "c", u"e": "e", u"b": "b",
                 u"\u014f": "obreve"}
        alike, apart = [0.0, -0.02, 0.01], [0.0, -0.09, 0.01]
        signatures = {"second": {u"o": alike, u"\u00f6": alike, u"\u0151": alike, u"\u014f": apart, u"c": alike,
                                 u"e": alike, u"b": apart},
                      "first": {u"o": alike, u"\u00f6": apart, u"\u0151": alike, u"\u014f": alike, u"c": apart,
                                u"e": apart, u"b": alike}}
        model = {"second": {(u"c", u"o"): 0.8, (u"o", u"c"): 0.8, (u"e", u"o"): 0.74, (u"o", u"e"): 0.74,
                            (u"c", u"e"): 0.78, (u"e", u"c"): 0.78, (u"b", u"o"): 0.1, (u"o", u"b"): 0.1,
                            (u"o", u"\u00f6"): 0.99, (u"o", u"\u0151"): 0.1},
                 "first": {(u"b", u"o"): 0.75, (u"o", u"b"): 0.75, (u"o", u"\u00f6"): 0.98}}
        classes = ak.suggest_classes(names, lambda ch, side: signatures[side][ch], model)
        # second: o with c and e (the corpus, and they kern alike); \u00f6 with o by the corpus; \u0151 rarely
        # classed with o by the corpus, so apart; \u014f unseen by the corpus and kerning unlike o, apart
        self.assertEqual(classes["second"], [[u"c", u"e", u"o", u"\u00f6"]])
        # first: \u00f6 joins by the corpus though it kerns unlike o; \u0151 and \u014f, unseen, kern alike
        self.assertEqual(classes["first"], [[u"b", u"o", u"\u00f6", u"\u014f", u"\u0151"]])

    def test_plans_keep_the_fonts_classes_and_name_odd_members(self):
        k = ak.FontKerning(FakeKerning({"o1": (["o", "oacute"], "KernRight"), "T": (["T"], "KernBothSide")},
                                       {(("b", False), ("o1", True)): -20, (("b", False), ("x", False)): -10}))
        names = {u"o": "o", u"\u00f3": "oacute", u"\u00f6": "odieresis", u"b": "b", u"\u00fe": "thorn", u"T": "T",
                 u"\u0162": "Tcedilla"}
        signatures = {u"b": [0.0, 0.0, 0.0], u"\u00fe": [0.0, 0.05, -0.06]}
        signature_of = lambda ch, side: signatures.get(ch, [0.0, 0.0, 0.0])
        plans = ak.plan_classes({"second": [[u"o", u"\u00f3", u"\u00f6"]], "first": [[u"b", u"\u00fe"]]}, names, k,
                                signature_of, 1000.0)
        plans += ak.plan_classes({"first": [[u"T", u"\u0162"]]}, names, k)
        self.assertEqual([p.action for p in plans], ["new", "add", "overlap"])
        new, add, both = plans
        self.assertEqual((new.name, new.glyphs), ("kern1_b", ["b", "thorn"]))
        self.assertEqual(new.differs, [(u"\u00fe", 50, u"O")], "thorn kerns 50 units looser than b beside O (tighter is not noted)")
        self.assertIn(u"\u00feO 50 units looser than bO", new.describe())
        self.assertEqual(new.columns(), (u"kern1_b", u"b \u00fe", u"New class"), "a cell's note: no period")
        self.assertEqual(add.columns(), (u"o1", u"\u00f6", u"Added to the class (with o \u00f3)"))
        self.assertTrue(new.describe().endswith(u" than bO)"), "what a member may need, in parentheses: no dash")
        self.assertNotIn(u"\N{EM DASH}", new.describe())
        self.assertEqual((both.columns()[2], both.columns()[2][-1:] != u"."), (u"Left as it is: class T kerns both sides", True))
        self.assertEqual((add.existing, add.adding), ("o1", ["odieresis"]))
        made, extended, moved, kept = ak.apply_class_plans(k, [new, add])
        self.assertEqual((made, extended, moved, kept), (1, 1, 2, 0))
        stored = k.kerning.stored
        self.assertEqual(stored[(("kern1_b", True), ("o1", True))], -20, "b's pairs moved to its new class")
        self.assertEqual(stored[(("kern1_b", True), ("x", False))], -10)
        self.assertNotIn((("b", False), ("o1", True)), stored)
        self.assertEqual(k.kerning.groups.data["o1"], (["o", "oacute", "odieresis"], "KernRight"))
        self.assertEqual(k.kerning.groups.data["kern1_b"], (["b", "thorn"], "KernLeft"))


class ClassDialogFixTests(unittest.TestCase):
    def test_every_plan_has_a_hashable_key(self):
        # an overlap's existing is a list of classes: comparing plans before creating them hashed it
        k = ak.FontKerning(FakeKerning({"h": (["h"], "KernLeft"), "n": (["n"], "KernLeft")}, {}))
        names = {u"h": "h", u"n": "n", u"m": "m"}
        plans = ak.plan_classes({"first": [[u"h", u"m", u"n"]]}, names, k)
        self.assertEqual([p.action for p in plans], ["overlap"])
        self.assertEqual(len(set(p.key() for p in plans)), 1)
        self.assertEqual(plans[0].columns()[0], u"h, n")

    def test_a_looser_member_at_its_widest_partner(self):
        # second side: partners H O o n v T L r f; the member kerns 40 units looser beside T (index 5)
        first, member = [0.0, 0.0, 0.0, 0.0, 0.0, -0.08], [0.0, 0.01, 0.0, 0.0, 0.0, -0.04]
        self.assertEqual(ak.loosest_difference(first, member)[1], 5)
        k = ak.FontKerning(FakeKerning({}, {}))
        names = {u"a": "a", u"\u00e1": "aacute"}
        plans = ak.plan_classes({"second": [[u"a", u"\u00e1"]]}, names, k,
                                lambda ch, side: first if ch == u"a" else member, 1000.0)
        self.assertEqual(plans[0].differs, [(u"\u00e1", 40, u"T")])
        self.assertEqual(plans[0].describe_differs(), u"T\u00e1 40 units looser than Ta")


class ReviewFixTests(unittest.TestCase):
    def test_a_glyph_against_the_class_that_bears_its_name(self):
        # glyph o has no first-position class; class o (second position) holds c, e, and o
        k = ak.FontKerning(FakeKerning({"o": (["c", "e", "o"], "KernRight")}, {}))
        entry, remove = k.target("o", "e")
        self.assertEqual(entry, (("o", False), ("o", True)))
        k.write(entry, -30, remove)
        self.assertEqual(k.kerning.stored, {(("o", False), ("o", True)): -30}, "glyph o against class o, not the pair oo")
        self.assertEqual(ak.FontKerning(k.kerning).current("o", "e"), -30)

    def test_a_member_keeps_its_own_value_when_a_class_takes_it_in(self):
        # T o is -80 (glyph pair); class TT against odieresis is -60 (the member's own entry)
        k = ak.FontKerning(FakeKerning({"TT": (["T", "Tcaron"], "KernLeft")},
                                       {(("T", False), ("o", False)): -80, (("TT", True), ("odieresis", False)): -60}))
        names = {u"o": "o", u"\u00f6": "odieresis", u"T": "T", u"\u0164": "Tcaron"}
        plans = ak.plan_classes({"second": [[u"o", u"\u00f6"]]}, names, k)
        self.assertEqual([p.action for p in plans], ["new"])
        made, extended, moved, kept = ak.apply_class_plans(k, plans)
        after = ak.FontKerning(k.kerning)
        self.assertEqual(after.current("T", "o"), -80, "moved into the class")
        self.assertEqual(after.current("T", "odieresis"), -60, "the member's own value kept")
        self.assertEqual(after.current("Tcaron", "odieresis"), -60)
        self.assertEqual((made, moved, kept), (1, 1, 1))

    def test_letters_of_their_own_take_their_case_references(self):
        self.assertEqual(ak.kind_character(u"\u00f8"), u"n", "o with stroke: lowercase")
        self.assertEqual(ak.kind_character(u"\u00d8"), u"H")
        self.assertEqual(ak.kind_character(u"\u00e9"), u"e")
        self.assertEqual(ak.kind_character(u"."), u".")

    def test_band_edges_round_as_in_python_3(self):
        self.assertEqual([ak.round_half_even(v) for v in (12.5, 13.5, -0.5, 2.4, 2.6)], [12, 14, 0, 2, 3])

    def test_a_model_for_other_features_is_not_used(self):
        import json
        import tempfile
        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        try:
            with io.open(path, "wb") as out:
                out.write(json.dumps({"format": 2, "features": ["one", "two"], "cut": 0.4,
                                      "classifier": {"baseline": 0, "trees": []}, "regressor": {"baseline": 0, "trees": []}}).encode("utf-8"))
            self.assertIsNone(ak.learned_model(path))
        finally:
            os.remove(path)


import freelab_kerning_check as kc  # noqa: E402


def fake_font(groups, entries):
    return ak.FontKerning(FakeKerning(groups, entries))


class KerningUpgradeTests(unittest.TestCase):
    def test_a_noted_pair_gets_a_value_of_its_own(self):
        # class e (first side) holds e and eacute; class e against T is -80; eacute measures 52 units looser by T
        k = fake_font({"e": (["e", "eacute"], "KernLeft")}, {(("e", True), ("T", False)): -80})
        names = {u"e": "e", u"E": "eacute", u"T": "T"}  # (E stands for e acute: the test stays ASCII)
        base, member = [0.0] * 9, [0.0] * 9
        member[5] = 0.052  # SIGNATURE_PARTNERS["first"][5] is T
        plans = ak.plan_classes({"first": [[u"e", u"E"]]}, names, k, lambda ch, side: base if ch == u"e" else member, 1000.0)
        self.assertEqual(plans[0].action, "same")
        found = ak.noted_exceptions(k, plans, names)
        self.assertEqual([(e.pair, e.current, e.value) for e in found], [(("eacute", "T"), -80, -28)])
        self.assertEqual(ak.write_exceptions(k, found), 1)
        after = ak.FontKerning(k.kerning)
        self.assertEqual((after.current("eacute", "T"), after.current("e", "T")), (-28, -80))

    def test_no_exception_where_the_member_has_its_own_value_or_none_is_tightened(self):
        k = fake_font({"e": (["e", "eacute"], "KernLeft")},
                      {(("e", True), ("T", False)): -80, (("eacute", False), ("T", False)): -40,
                       (("e", True), ("V", False)): 10})
        plan = ak.ClassPlan("first", [u"e", u"E"], {u"e": "e", u"E": "eacute"}, k, [(u"E", 52, u"T"), (u"E", 40, u"V")])
        self.assertEqual(ak.noted_exceptions(k, [plan], {u"e": "e", u"E": "eacute", u"T": "T", u"V": "V"}), [])

    def test_kerning_check_shows_a_right_to_left_pair_as_read(self):
        class Glyph(object):
            def __init__(self, code):
                self.fgGlyph = type("FgGlyph", (object,), {"unicode": code})()

        class Package(object):
            def findName(self, name):
                return Glyph({"bet": 0x05D1, "yod": 0x05D9, "T": 0x54, "o": 0x6F}.get(name, 0))

        self.assertEqual(kc.pair_text(Package(), "yod", "bet", ak), HEBREW_YOD + HEBREW_BET,
                         "the key (yod, bet) is typed yod then bet: shown so, yod at the right")
        self.assertEqual(kc.screen_pair(ak, Package(), "yod", "bet"), ("bet", "yod"), "measured and drawn as on screen")
        self.assertEqual(kc.screen_pair(ak, Package(), "T", "o"), ("T", "o"))
        self.assertEqual(kc.pair_text(Package(), "T", "o", ak), u"To")
        self.assertEqual(kc.pair_text(Package(), "T", "bet.alt", ak), u"T bet.alt", "a glyph without a character: its name")

    def test_collisions_closest_first_with_their_fix(self):
        k = fake_font({"T": (["T", "Tcaron"], "KernLeft")},
                      {(("T", True), ("o", False)): -90, (("T", False), ("a", False)): -60, (("V", False), ("o", False)): 5})
        gaps = {("T", "o"): 30.0, ("Tcaron", "o"): -12.0, ("T", "a"): 8.0}
        found = kc.find_collisions(k, lambda left, right, value: gaps.get((left, right)), 20, relative=False)
        self.assertEqual([(c.pair(), c.value, c.fix) for c in found],
                         [(("Tcaron", "o"), -90, -58), (("T", "a"), -60, -48)])
        self.assertEqual(found[0].entry, (("T", True), ("o", False)), "Tcaron o takes its class's value")

    def test_cleanup_kinds(self):
        k = fake_font({"C": (["c", "ccedilla"], "KernLeft"), "gone": ([], "KernLeft")},
                      {(("C", True), ("T", False)): -50,
                       (("c", False), ("T", False)): -50,  # the class gives the same: changes nothing
                       (("ccedilla", False), ("T", False)): 0,  # an exception of 0 against -50: kept
                       (("x", False), ("T", False)): -30,  # no glyph x
                       (("gone", True), ("T", False)): -20,  # a class with no members
                       (("C", True), ("V", False)): -3,  # tiny
                       (("c", False), ("V", False)): -40, (("ccedilla", False), ("V", False)): -40})
        found = kc.find_cleanup(k, lambda name: name != "x", 5)
        kinds = dict((c.entry, c.kind) for c in found)
        self.assertEqual(kinds, {(("x", False), ("T", False)): "missing", (("gone", True), ("T", False)): "missing",
                                 (("C", True), ("V", False)): "overridden", (("c", False), ("T", False)): "redundant"})
        self.assertTrue(all(c.checked for c in found))
        tiny = kc.find_cleanup(fake_font({}, {(("a", False), ("b", False)): -3}), lambda name: True, 5)
        self.assertEqual([(c.kind, c.checked) for c in tiny], [("tiny", False)])
        self.assertEqual(tiny[0].reason, u"smaller than 5 units")
        self.assertFalse([c.reason for c in found + tiny if c.reason.endswith(u".")], "a cell's note: no period")
        # (owner's images 338 and 339: -4 for A and lacute, an exception to the class pair's -32, was listed as
        # tiny; removed, the pair collided again, and its fix was a tiny value again)
        exception = kc.find_cleanup(fake_font({"L": (["l", "lacute"], "KernRight")},
                                              {(("A", False), ("L", True)): -32, (("A", False), ("lacute", False)): -4,
                                               (("A", False), ("x", False)): -3}), lambda name: True, 5)
        self.assertEqual([(c.entry, c.kind) for c in exception], [((("A", False), ("x", False)), "tiny")],
                         "A lacute's pair would move 28 units without it: not tiny")

    def test_cleanup_judged_again_before_removing(self):
        # A V equals its class's -50 at the check; the class pair is then edited to -100: A V now sets A V
        groups = {"A": (["A", "Aacute"], "KernLeft")}
        entries = {(("A", True), ("V", False)): -50, (("A", False), ("V", False)): -50, (("x", False), ("V", False)): -20}
        found = kc.find_cleanup(fake_font(groups, dict(entries)), lambda name: name != "x", 5)
        self.assertEqual(sorted(c.entry for c in found), [(("A", False), ("V", False)), (("x", False), ("V", False))])
        entries[(("A", True), ("V", False))] = -100
        chosen, stale = kc.still_removable(fake_font(groups, entries), found, lambda name: name != "x", 5)
        self.assertEqual(([c.entry for c in chosen], stale), ([(("x", False), ("V", False))], 1), "the exception kept")
        entries[(("A", True), ("V", False))] = -50
        chosen, stale = kc.still_removable(fake_font(groups, entries), found, lambda name: name != "x", 5)
        self.assertEqual((len(chosen), stale), (2, 0), "nothing changed: both go")
        chosen, stale = kc.still_removable(fake_font(groups, entries), found, lambda name: True, 5)
        self.assertEqual(([c.entry for c in chosen], stale), ([(("A", False), ("V", False))], 1), "glyph x added since: left")
        k = fake_font(groups, entries)
        k.values[(("A", False), ("V", False))] = -60
        chosen, stale = kc.still_removable(k, found, lambda name: name != "x", 5)
        self.assertEqual(([c.entry for c in chosen], stale), ([(("x", False), ("V", False))], 1), "a value changed: left")

    def test_collisions_against_the_class_pair(self):
        # T T overlaps by design (joined crossbars); Tcaron T overlaps 40 units more; T a is a pair of its own;
        # class signs holds unlike shapes (plus, approxequal): C plus is not compared with C approxequal
        k = fake_font({"T": (["T", "Tcaron"], "KernBothSide"), "signs": (["approxequal", "plus"], "KernRight"),
                       "C": (["C", "Ccaron"], "KernLeft")},
                      {(("T", True), ("T", True)): -268, (("T", False), ("a", False)): -60,
                       (("C", True), ("signs", True)): -15})
        gaps = {("T", "T"): -266.0, ("Tcaron", "T"): -306.0, ("T", "Tcaron"): -270.0, ("Tcaron", "Tcaron"): -300.0,
                ("T", "a"): -50.0, ("C", "approxequal"): 378.0, ("C", "plus"): 6.0, ("Ccaron", "plus"): -1.0,
                ("Ccaron", "approxequal"): 370.0}
        found = kc.find_collisions(k, lambda left, right, value: gaps.get((left, right)), 20)
        self.assertEqual([(c.pair(), c.fix, c.reference) for c in found],
                         [(("Tcaron", "T"), -228, ("T", "T")), (("Tcaron", "Tcaron"), -238, ("T", "Tcaron"))])

    def test_variants_of_a_key_glyph(self):
        chars = {"w": u"w", "won": u"\N{WON SIGN}", "T": u"T", "Tcaron": u"\N{LATIN CAPITAL LETTER T WITH CARON}",
                 "Tbar": u"\N{LATIN CAPITAL LETTER T WITH STROKE}", "f": u"f", "f_f_t": None, "j": u"j", "j.2": None}
        char_of = chars.get
        self.assertTrue(kc.is_variant("Tcaron", "T", char_of))
        self.assertTrue(kc.is_variant("Tbar", "T", char_of), "a barred letter has no decomposition")
        self.assertTrue(kc.is_variant("j.2", "j", char_of), "an alternate")
        self.assertFalse(kc.is_variant("won", "w", char_of), "a currency sign named after w")
        self.assertFalse(kc.is_variant("f_f_t", "f", char_of), "a ligature")

    def test_masters_compared(self):
        regular = fake_font({"o": (["o"], "KernRight")}, {(("T", False), ("o", True)): -60, (("V", False), ("a", False)): -20})
        bold = fake_font({"o": (["o", "oacute"], "KernRight")}, {(("T", False), ("o", True)): 30})
        found = kc.compare_masters([("Regular", regular), ("Bold", bold)])
        self.assertEqual([(d.kind, d.subject) for d in found],
                         [("sign", u"T \N{MULTIPLICATION SIGN} class o"), ("missing", u"V \N{MULTIPLICATION SIGN} a"),
                          ("class", u"class o")])
        self.assertEqual(kc.compare_masters([("Regular", regular)]), [])

    def test_lists_limited_to_some_glyphs(self):
        # after Glyph Compose built Tcaron (or moved its caron): only the pairs and entries with it
        k = fake_font({"T": (["T", "Tcaron"], "KernLeft")},
                      {(("T", True), ("o", False)): -90, (("V", False), ("a", False)): -60,
                       (("V", False), ("o", False)): -3, (("Tcaron", False), ("a", False)): -60,
                       (("T", True), ("a", False)): -60})
        gaps = {("T", "o"): 30.0, ("Tcaron", "o"): -12.0, ("V", "a"): 8.0, ("Tcaron", "a"): 9.0, ("T", "a"): 9.0}
        closest = lambda left, right, value: gaps.get((left, right))
        found = kc.find_collisions(k, closest, 20, relative=False, only=set(["Tcaron"]))
        self.assertEqual([c.pair() for c in found], [("Tcaron", "o"), ("Tcaron", "a")], "V a left out")
        self.assertEqual(len(kc.find_collisions(k, closest, 20, relative=False)), 4, "every pair without a limit")
        measured = []
        kc.find_collisions(k, lambda left, right, value: measured.append((left, right)), 20, relative=False,
                           only=set(["Tcaron"]))
        self.assertTrue(all("Tcaron" in pair for pair in measured), "the other pairs are not even measured")
        self.assertEqual([pair for pair, _ in kc.tight_pairs(k, set(["Tcaron"]))], [("Tcaron", "a"), ("Tcaron", "o")])

        cleanup = kc.find_cleanup(k, lambda name: True, 5)
        self.assertEqual(sorted(c.entry for c in cleanup),
                         [(("Tcaron", False), ("a", False)), (("V", False), ("o", False))])
        limited = kc.limited_cleanup(k, cleanup, set(["Tcaron"]))
        self.assertEqual([c.entry for c in limited], [(("Tcaron", False), ("a", False))], "the exception equal to its class's")
        self.assertEqual([c.entry for c in kc.limited_cleanup(k, cleanup, set(["T"]))], [], "neither names T nor a class holding it")
        self.assertEqual(len(kc.limited_cleanup(k, cleanup, None)), 2)
        self.assertTrue(kc.involves(k, (("T", True), ("o", False)), ["Tcaron"]), "a class side: its members")
        self.assertFalse(kc.involves(k, (("V", False), ("a", False)), ["Tcaron"]))
        self.assertEqual(kc.entry_glyphs(k, (("T", True), ("o", False))), set(["T", "Tcaron", "o"]))

    def test_masters_limited_to_some_glyphs(self):
        regular = fake_font({"o": (["o"], "KernRight"), "A": (["A"], "KernLeft")},
                            {(("T", False), ("o", True)): -60, (("V", False), ("a", False)): -20})
        bold = fake_font({"o": (["o", "oacute"], "KernRight"), "A": (["A", "Aacute"], "KernLeft")},
                         {(("T", False), ("o", True)): 30})
        found = kc.compare_masters([("Regular", regular), ("Bold", bold)], only=set(["oacute"]))
        self.assertEqual([(d.kind, d.subject) for d in found],
                         [("sign", u"T \N{MULTIPLICATION SIGN} class o"), ("class", u"class o")],
                         "class o holds oacute in Bold: its entry and the class; V a and class A left out")
        self.assertEqual(found[0].entry, (("T", False), ("o", True)))
        self.assertEqual(len(kc.compare_masters([("Regular", regular), ("Bold", bold)])), 4)

    def test_the_line_over_limited_lists(self):
        self.assertEqual(kc.limit_line([u"L", u"l"], u"Glyph Compose built"), u"Pairs with the 2 glyphs Glyph Compose built: L l")
        self.assertEqual(kc.limit_line([u"L"], u"Glyph Compose built"), u"Pairs with the glyph Glyph Compose built: L")
        self.assertEqual(kc.limit_line([u"a", u"b", u"c"], None, shown=2), u"Pairs with these 3 glyphs: a b \N{HORIZONTAL ELLIPSIS}")
        self.assertEqual(kc.limit_line([u"a"]), u"Pairs with this glyph: a")

    def test_glyphs_handed_over_by_name_or_as_glyphs(self):
        glyph = type("Glyph", (), {"name": u"Ldot"})()
        self.assertEqual(kc.glyph_names([glyph, "ldot", u"Ldot", None]), [u"Ldot", u"ldot"])
        self.assertEqual(kc.glyph_names(None), [])

    def test_buttons_count_their_checked_rows(self):
        # (Tick, not Check, for check boxes: owner's image 261)
        self.assertEqual(kc.action_text("cleanup", 0), u"Clean up ticked entries")
        self.assertEqual(kc.action_text("cleanup", 1), u"Clean up 1 ticked entry")
        self.assertEqual(kc.action_text("cleanup", 3), u"Clean up 3 ticked entries")
        self.assertEqual(kc.action_text("collisions", 1), u"Write 1 ticked fix")
        self.assertEqual(kc.action_text("collisions", 2), u"Write 2 ticked fixes")
        self.assertEqual(ak.checks_of([True, False], bool), (True, True))
        self.assertEqual(ak.checks_of([], bool), (False, False), "an empty list: neither Check all nor Check none")

    def test_main_takes_the_glyphs_without_qt(self):
        import contextlib
        try:
            from io import StringIO
        except ImportError:  # pragma: no cover
            from StringIO import StringIO
        out = StringIO() if sys.version_info[0] >= 3 else io.BytesIO()
        redirect = getattr(contextlib, "redirect_stdout", None)
        if redirect is None:
            saved, sys.stdout = sys.stdout, out
            try:
                kc.main(glyphs=["Ldot"], reason=u"Glyph Compose built")
                kc.main(["Ldot"], why=u"Glyph Compose moved marks of")
            finally:
                sys.stdout = saved
        else:
            with redirect(out):
                kc.main(glyphs=["Ldot"], reason=u"Glyph Compose built")
                kc.main(["Ldot"], why=u"Glyph Compose moved marks of")
        self.assertIn("FreeLab Kerning Check", out.getvalue(), "no Qt here: said so, nothing raised")

    def test_proof_text_names_each_glyph(self):
        self.assertEqual(ak.proof_text("T", "eacute", ["H", "n"]), u"/H/H/T/eacute/H/H/space/n/n/T/eacute/n/n")


class ProofTests(unittest.TestCase):
    class Glyph(object):
        def __init__(self, name, code):
            self.name, self.isNull = name, False
            self.fgGlyph = type("Fg", (), {"unicode": code})()

    class Package(object):
        def __init__(self, glyphs):
            self.by_name = dict((name, ProofTests.Glyph(name, code)) for name, code in glyphs)
            self.by_code = dict((code, self.by_name[name]) for name, code in glyphs if code)

        def findName(self, name):
            return self.by_name.get(name)

        def findUnicode(self, code):
            return self.by_code.get(code)

    def test_contexts_follow_the_script(self):
        package = self.Package([("H", 0x48), ("n", 0x6E), ("o", 0x6F), ("Eta", 0x397), ("nu", 0x3BD), ("omicron", 0x3BF),
                                ("Ka", 0x41A), ("zero", 0x30), ("T", 0x54), ("kappa", 0x3BA), ("x.alt", 0)])
        self.assertEqual(ak.proof_contexts(package, ["T", "o"]), ["H", "n", "o"])
        self.assertEqual(ak.proof_contexts(package, ["kappa", "nu"]), ["Eta", "nu", "omicron"], "Greek's own")
        self.assertEqual(ak.proof_contexts(package, ["Ka", "o"]), ["H", "n", "o"], "no Cyrillic controls: Latin's")
        self.assertEqual(ak.proof_contexts(package, ["zero", "T"]), ["zero", "H", "n"], "figures between zeros")
        self.assertEqual(ak.proof_contexts(package, ["x.alt", "T"]), ["H", "n", "o"], "an unencoded glyph: the next one's")


class HistoryObject(object):
    """A FontLab object with History states: at its first one until a step records it (FontLab's
    History moves every object's current state with it; here, only what a step records moves)."""
    def __init__(self, name):
        self.name, self.state, self.mark = name, 0, 0

    def currentHistoryState(self):
        return self.state

    def initialHistoryState(self):
        return 0

    def update(self):
        pass


class HistoryItems(object):
    def __init__(self):
        self.steps, self.updates, self.index = [], [], 0

    def notifyChangesApplied(self, title, objects, recursive):
        self.index += 1
        recorded = objects if isinstance(objects, list) else [objects]
        for obj in recorded:
            obj.state = self.index
        self.steps.append((title, [obj.name for obj in recorded], recursive))

    def notifyPackageContentUpdated(self, key):
        self.updates.append(key)


class HistoryPackage(HistoryObject):
    def __init__(self, key):
        HistoryObject.__init__(self, "font")
        self.fgPackage = HistoryObject("fgPackage")
        self.fgPackage.id = key
        self.glyphsCount, self.flags = 3, []

    def setFlag(self, flag, value):
        self.flags.append((flag, value))


class BeforeChangesTests(unittest.TestCase):
    """A FreeLab write to a font opened afresh could not be undone (live: History 1 to 0, H's width
    kept): a step records objects as they are after it, and those with no earlier state stayed."""

    def setUp(self):
        self.saved = getattr(sys, "_freelab_history", None)
        sys._freelab_history = None
        self.fontlab = HistoryObject("fontlab")
        self.items = self.fontlab.flItems = HistoryItems()

    def tearDown(self):
        sys._freelab_history = self.saved

    def test_the_first_write_records_the_font_as_it_was(self):
        package = HistoryPackage(7)
        self.assertEqual(ak.before_changes(self.fontlab, package, u"FreeLab Auto Spacing"), [package])
        ak.notify_changed(self.fontlab, package, u"FreeLab Auto Spacing")
        self.assertEqual(self.items.steps, [(u"FreeLab Auto Spacing (before)", ["font"], True),
                                            (u"FreeLab Auto Spacing", ["font"], True)], "the whole font, each time")
        self.assertEqual(self.items.updates, [], "no glyph added: the Font window's list not rebuilt")
        self.assertEqual(package.flags, [(2, True)], "marked modified")
        self.assertEqual(ak.before_changes(self.fontlab, package, u"FreeLab Auto Spacing"), [],
                         "a later write: the font recorded already")
        self.assertEqual(len(self.items.steps), 2)

    def test_an_undo_past_the_first_record_records_it_again(self):
        package = HistoryPackage(8)
        ak.before_changes(self.fontlab, package, u"FreeLab Glyph Compose")
        ak.notify_changed(self.fontlab, package, u"FreeLab Glyph Compose")
        package.state = 0  # (undone twice: back where the font was opened)
        self.assertEqual(ak.before_changes(self.fontlab, package, u"FreeLab Glyph Compose"), [package])

    def test_glyphs_without_a_state_are_recorded_with_the_font(self):
        package, glyphs = HistoryPackage(9), [HistoryObject("A"), HistoryObject("B")]
        glyphs[1].state = 4  # (recorded by an earlier step)
        self.assertEqual(ak.before_changes(self.fontlab, package, u"FreeLab flag", glyphs), [package, glyphs[0]],
                         "a flag is the glyph's own state, which the whole font's record leaves out")
        ak.notify_changed(self.fontlab, package, u"FreeLab flag", glyphs)
        self.assertEqual(self.items.steps[-1], (u"FreeLab flag", ["font", "A", "B"], True), "the glyphs recorded too")
        self.assertEqual(ak.before_changes(self.fontlab, package, u"FreeLab flag", glyphs), [])

    def test_the_font_window_is_told_only_of_glyphs_added_or_removed(self):
        package = HistoryPackage(10)
        ak.before_changes(self.fontlab, package, u"FreeLab Feature Code")
        package.glyphsCount += 2
        ak.notify_changed(self.fontlab, package, u"FreeLab Feature Code")
        self.assertEqual(self.items.updates, [10], "glyphs added: the Font window shows them")
        ak.notify_changed(self.fontlab, package, u"FreeLab Feature Code")
        self.assertEqual(self.items.updates, [10, 10], "no count noted before: told, to be safe")
        ak.notify_changed(self.fontlab, package, u"FreeLab Auto Kerning", added=False)
        self.assertEqual(self.items.updates, [10, 10], "kerning only: not told")

    # Failures of FontLab's History or modified mark were swallowed, and the tools then wrote and promised
    # Undo (review of 2026-11-15): each of the three calls fails here on its own

    def test_a_failed_first_record_writes_nothing(self):
        package = HistoryPackage(11)

        def refuse(title, objects, recursive):
            raise RuntimeError("History refused")
        self.items.notifyChangesApplied = refuse
        with self.assertRaises(ak.HistoryError):
            ak.before_changes(self.fontlab, package, u"FreeLab Auto Spacing")
        logged = []
        log = type("Log", (), {"add": lambda _, text, kind="info": logged.append((kind, text))})()
        self.assertFalse(ak.begin_write(self.fontlab, package, u"FreeLab Auto Spacing", log))
        self.assertEqual([kind for kind, _ in logged], ["error"])
        self.assertIn(u"Nothing was changed", logged[0][1])
        self.assertIn(u"History refused", logged[0][1])
        self.assertNotIn(11, sys._freelab_history["whole"], "not taken as recorded: the next write tries again")

    def test_a_failed_step_is_reported_without_the_undo_promise(self):
        package = HistoryPackage(12)
        self.assertTrue(ak.begin_write(self.fontlab, package, u"FreeLab Auto Spacing", None))

        def refuse(title, objects, recursive):
            raise RuntimeError("History refused")
        self.items.notifyChangesApplied = refuse
        status = ak.notify_changed(self.fontlab, package, u"FreeLab Auto Spacing")
        self.assertFalse(status.recorded)
        self.assertTrue(status.marked, "the font marked modified all the same")
        self.assertEqual(status.undo(u"Undo takes it back."), u"")
        logged = []
        log = type("Log", (), {"add": lambda _, text, kind="info": logged.append((kind, text))})()
        self.assertFalse(status.report(log))
        self.assertEqual([kind for kind, _ in logged], ["error"])
        self.assertIn(u"cannot take it back", logged[0][1])
        self.assertIn(u"close the font without saving", logged[0][1])
        self.assertNotIn(12, sys._freelab_history["whole"], "the next write records the font first again")

    def test_a_font_left_unmarked_is_reported(self):
        package = HistoryPackage(13)

        def refuse(flag, value):
            raise RuntimeError("no flag")
        package.setFlag = refuse
        ak.before_changes(self.fontlab, package, u"FreeLab flag")
        status = ak.notify_changed(self.fontlab, package, u"FreeLab flag")
        self.assertTrue(status.recorded)
        self.assertFalse(status.marked)
        self.assertFalse(status.ok)
        self.assertEqual(status.undo(u"Undo takes it back."), u"Undo takes it back.", "the History has the step")
        self.assertIn(u"save the font before closing it", status.message())

    def test_a_failed_redraw_is_not_a_failed_write(self):
        package = HistoryPackage(14)
        glyph = HistoryObject("A")

        def broken():
            raise RuntimeError("no redraw")
        glyph.update = broken
        self.items.notifyPackageContentUpdated = lambda key: broken()
        ak.before_changes(self.fontlab, package, u"FreeLab Glyph Compose", [glyph])
        package.glyphsCount += 1
        status = ak.notify_changed(self.fontlab, package, u"FreeLab Glyph Compose", [glyph])
        self.assertTrue(status.ok)
        self.assertEqual(status.message(), u"")

    def test_every_write_begins_with_before_changes_where_undo_needs_it(self):
        """Each tool that writes records the font first. Kerning, feature code, and font info are the font's
        own state (recorded when FontLab opens a font: live, they went on Undo), but the step records the
        whole font, its glyphs too, which have none in a font opened afresh: undone, FontLab printed "We have
        a problem with the component 'P' in glyph 'Rho:Regular'" (owner's image 336, Kerning Check's)."""
        root = os.path.join(HERE, os.pardir)
        expected = {"spacing/freelab_auto_spacing.py": 1, "cjk/freelab_cjk_spacing.py": 1,
                    "compose/freelab_glyph_compose.py": 1,
                    "features/freelab_feature_code.py": 2,  # (the figure forms' build, the code's write)
                    "features/freelab_alternates.py": 2,  # (Make copies to redraw, Build variants)
                    "checks/freelab_font_check.py": 2,  # (the masters' fixes, begin_info_write)
                    "features/freelab_feature_check.py": 1, "builder/freelab_font_builder.py": 1,
                    "kerning/freelab_kerning_check.py": 1,  # (begin_writing)
                    # (flag_glyphs's, begin_write's own before_changes, begin_kerning_write)
                    "kerning/freelab_auto_kerning.py": 3}
        for path, count in expected.items():
            with io.open(os.path.join(root, path), encoding="utf-8") as handle:
                source = handle.read()
            self.assertEqual(len(re.findall(r"(?<!def )(?:before_changes|begin_write)\((?:self\.(?:ak\.)?|owner\.|ak\.)?fontlab",
                                            source)), count, path)


class MenuOrderTests(unittest.TestCase):
    def test_working_order_then_dark_mode_then_mcp(self):
        texts = ["Glyph Compose", "Auto Kerning", "Auto Spacing", "CJK Spacing", "Toggle Dark Mode", "Dark Mode Settings",
                 "Feature Code", "Kerning Check", "Start Listener", "Something New"]
        self.assertEqual(ak.menu_order(texts),
                         ["Glyph Compose", "Auto Spacing", "CJK Spacing", "Auto Kerning", "Kerning Check", "Feature Code", None,
                          "Toggle Dark Mode", "Dark Mode Settings", None, "Start Listener", None, "Something New"])
        self.assertEqual(ak.menu_order(["Auto Kerning"]), ["Auto Kerning"], "no separator around a lone group")

    def test_font_check_follows_feature_code(self):
        texts = ["Proof", "Font Check", "Kerning Check", "Feature Code"]
        self.assertEqual(ak.menu_order(texts), ["Kerning Check", "Feature Code", "Font Check", "Proof"])


class WindowTests(unittest.TestCase):
    """One FreeLab window for each open font: a tool opened for a font takes the place of the tool its
    window showed, and a window keeps the font it was opened for."""

    class Font(object):
        isNull, glyphsCount = False, 10

        def __init__(self, number, name):
            self.fgPackage, self.tfn = self, name
            self.id = number

    class Workspace(object):
        def __init__(self, fonts):
            self.fonts, self.currentPackage = list(fonts), fonts[0]

        def packages(self):
            return list(self.fonts)

    class Window(object):
        def __init__(self, title):
            self.windowTitle, self.props, self.calls = title, {}, []
            self.visible, self.minimized, self.maximized = False, False, False
            self.pos, self.width, self.height, self.parent, self.slots = (0, 0), 400, 300, "main", {}

        def property(self, name):
            return self.props.get(name)

        def setProperty(self, name, value):
            self.props[name] = value

        def parentWidget(self):
            return None

        def isVisible(self):
            return self.visible

        def setWindowTitle(self, title):
            self.windowTitle = title

        def setParent(self, parent, flags=None):
            self.parent = parent
            self.flags = flags

        def windowFlags(self):
            return "window flags"

        def metaObject(self):
            return "QDialog"

        def deleteLater(self):
            self.calls.append("deleteLater")

        def setAttribute(self, attribute, on=True):
            self.props[("attribute", attribute)] = on

        def resize(self, width, height):
            self.width, self.height = width, height

        def move(self, *pos):
            self.pos = pos if len(pos) == 2 else pos[0]

        def connect(self, signal, slot):
            self.slots[signal] = slot

        def close(self):
            self.visible = False
            self.calls.append("close")
            if "finished(int)" in self.slots:
                self.slots["finished(int)"](0)

        def show(self, laid_out=None):
            """As Qt shows a window: grown to its layout's least size (laid_out) first."""
            if laid_out is not None:
                self.width, self.height = max(self.width, laid_out[0]), max(self.height, laid_out[1])
            self.visible = True

        def showNormal(self):
            self.calls.append("showNormal")

        def raise_(self):
            self.calls.append("raise")

        def activateWindow(self):
            self.calls.append("activate")

    class Tool(object):
        def __init__(self, workspace, title):
            self.workspace, self.dialog = workspace, WindowTests.Window(title)
            self.busy, self.lines = False, []

            class Log(object):
                def add(log, text, level="info"):
                    self.lines.append((level, text))

            self.log = Log()

        def current_font(self):
            return ak.window_font(self, self.workspace)

    def setUp(self):
        case = self
        self.one, self.two = self.Font(1068, u"One"), self.Font(8869, u"Two")
        self.workspace = self.Workspace([self.one, self.two])
        self.active, self.timers, self.app_slots, self.triggered = None, [], {}, []

        class FontLab(object):  # (the module a tool imports inside FontLab)
            class flWorkspace(object):
                @staticmethod
                def instance():
                    return case.workspace

            @staticmethod
            def flPackage(item):
                return item

            @staticmethod
            def fgSymbolList(text, flag):
                return [text]

        class App(object):
            def connect(self, signal, slot):
                case.app_slots.setdefault(signal, []).append(slot)

        class Action(object):
            def __init__(self, name):
                self.objectName = name

            def isEnabled(self):
                return True

            def trigger(self):
                case.triggered.append(self.objectName)

        class Main(object):
            objectName = "MainWindow"

            def findChildren(self, kind):
                return [Action(name) for name in ("actionUndo", "actionRedo", ak.GLYPH_TAB_ACTION)]

        class Application(object):
            @staticmethod
            def activeWindow():
                return case.active

            @staticmethod
            def instance():
                return App()

            @staticmethod
            def focusWidget():
                return None

            @staticmethod
            def topLevelWidgets():
                return [Main()]

        class Shortcut(object):
            def __init__(self, keys, parent):
                self.keys = keys

            def connect(self, signal, slot):
                case.shortcuts[self.keys] = slot

        class Gui(object):
            QApplication = Application
            QShortcut = Shortcut
            QAction = Action
            QMenu = "QMenu"

            @staticmethod
            def QKeySequence(keys):
                return keys

        class Core(object):
            class Qt(object):
                Window = WindowTitleHint = WindowSystemMenuHint = WindowMinMaxButtonsHint = WindowCloseButtonHint = 0
                WA_QuitOnClose = 98

            class QTimer(object):
                @staticmethod
                def singleShot(ms, slot):
                    case.timers.append(slot)

        self.saved, self.shortcuts = [], {}
        old_qt, old_fontlab, old_windows = ak._qt, sys.modules.get("fontlab"), getattr(sys, "_freelab_windows", None)
        old_hook, old_watch = getattr(sys, "_freelab_quit_hook", None), getattr(sys, "_freelab_font_watch", None)
        old_state = ak.state_dir
        self.state = tempfile.mkdtemp()
        ak._qt, sys.modules["fontlab"], sys._freelab_windows = (lambda: (Core, Gui)), FontLab, None
        ak.state_dir = lambda: self.state  # (a windows.json written there would be found: none must be)
        sys._freelab_quit_hook = None
        sys._freelab_font_watch = "held"  # (the fonts' watch is ticked by hand here: fonts_tick)

        def restore():
            ak._qt, sys._freelab_windows = old_qt, old_windows
            ak.state_dir = old_state
            sys._freelab_quit_hook, sys._freelab_font_watch = old_hook, old_watch
            shutil.rmtree(self.state, ignore_errors=True)
            if old_fontlab is None:
                del sys.modules["fontlab"]
            else:
                sys.modules["fontlab"] = old_fontlab

        self.addCleanup(restore)

    def run_timers(self):
        while self.timers:
            self.timers.pop(0)()

    def open(self, tool, title=None, laid_out=None):
        """As a tool's main() does (laid_out: the least size its layout grows the window to as it shows)."""
        if ak.raise_open(tool):
            return None
        owner = self.Tool(self.workspace, title or u"FreeLab %s" % tool)
        ak.take_window(tool, owner)
        owner.dialog.show(laid_out)
        self.run_timers()  # (Qt's event loop, once main() has returned)
        return owner

    def test_a_window_keeps_the_font_it_was_opened_for(self):
        proof = self.open("Proof")
        self.assertEqual(proof.dialog.windowTitle, u"FreeLab Proof (One)")
        self.workspace.currentPackage = self.two  # the owner looks at the other font in FontLab
        self.assertIs(proof.current_font(), self.one)
        self.assertEqual(proof.dialog.windowTitle, u"FreeLab Proof (One)")

    def test_each_open_font_has_a_window_of_its_own(self):
        first = self.open("Proof")
        self.workspace.currentPackage = self.two
        second = self.open("Proof")
        self.assertIsNotNone(second, "the other font's Proof is no reason to reuse a window")
        self.assertTrue(first.dialog.visible and second.dialog.visible)
        self.assertEqual(second.dialog.windowTitle, u"FreeLab Proof (Two)")
        self.assertIs(second.current_font(), self.two)

    def test_the_next_tool_takes_the_windows_place_at_its_own_size(self):
        first = self.open("Proof")
        first.dialog.pos = (40, 50)
        self.workspace.currentPackage = self.two
        other = self.open("Font Check")
        self.workspace.currentPackage = self.one
        second = self.Tool(self.workspace, u"FreeLab Font Check")
        second.dialog.width = 1400  # (Font Check asks for more width than the others)
        ak.take_window("Font Check", second)
        self.assertFalse(first.dialog.visible, "the tool the window showed is closed")
        self.assertEqual(second.dialog.pos, (40 - 500, 50), "where it stood, around the same center")
        self.assertEqual((second.dialog.width, second.dialog.height), (1400, 300), "at its own size")
        second.dialog.visible = True
        third = self.open("Glyph Compose")
        self.assertEqual((third.dialog.width, third.dialog.height), (400, 300), "back to the others' size after Font Check")
        self.assertEqual(third.dialog.pos, (40, 50), "shrunk around its center again")
        self.assertTrue(other.dialog.visible, "the other font's window stays")
        self.assertEqual(other.dialog.pos, (0, 0))
        self.assertIsNone(sys._freelab_windows.get("size"), "nothing resized by hand: nothing kept")

    def test_a_wider_tool_grows_on_both_sides_and_stays_on_screen(self):
        # The owner: "it always enlarges from the left side of the window instead of keeping it centered"
        self.assertEqual(ak.centered_place((300, 100), (1000, 800), (1400, 800)), (100, 100), "200 pixels each side")
        self.assertEqual(ak.centered_place((100, 100), (1400, 800), (1000, 800)), (300, 100), "and back")
        area = (0, 0, 1920, 1040)
        self.assertEqual(ak.centered_place((50, 100), (1000, 800), (1400, 800), area, (16, 39)), (0, 100),
                         "kept on screen on the left")
        self.assertEqual(ak.centered_place((900, 100), (1000, 800), (1400, 800), area, (16, 39)), (1920 - 1400 - 16, 100),
                         "and on the right")
        self.assertEqual(ak.centered_place((300, 600), (1000, 800), (1000, 900), area, (16, 39)), (300, 1040 - 900 - 39),
                         "a taller one, above the taskbar")

    def test_a_size_given_by_hand_is_every_windows_size_for_this_session_only(self):
        # The owner: "it should survive within a single session across fonts and such, but maybe not between
        # sessions, else there's no way to ever go back to default size"
        with open(os.path.join(self.state, "windows.json"), "w") as handle:
            handle.write('{"size": [900, 700]}')  # an earlier version's
        first = self.open("Proof")
        self.assertEqual((first.dialog.width, first.dialog.height), (400, 300), "an earlier session's size is not read")
        first.dialog.resize(1200, 900)  # the owner drags its corner
        second = self.open("Glyph Compose")
        self.assertEqual((second.dialog.width, second.dialog.height), (1200, 900))
        self.workspace.currentPackage = self.two
        other = self.open("Font Check")
        self.assertEqual((other.dialog.width, other.dialog.height), (1200, 900), "for the other font too")
        other.dialog.resize(1000, 800)
        other.dialog.close()  # closed, not taken over: its size counts all the same
        self.assertEqual(sys._freelab_windows["size"], (1000, 800))
        with open(os.path.join(self.state, "windows.json")) as handle:
            self.assertEqual(handle.read(), '{"size": [900, 700]}', "nothing written for later sessions")
        self.assertEqual(os.listdir(self.state), ["windows.json"])

    def test_a_minimized_or_maximized_window_gives_no_place_and_no_size(self):
        first = self.open("Proof")
        first.dialog.pos, first.dialog.minimized = (-32000, -32000), True
        first.dialog.resize(160, 28)
        second = self.open("Glyph Compose")
        self.assertEqual(second.dialog.pos, (0, 0))
        self.assertEqual((second.dialog.width, second.dialog.height), (400, 300))
        self.assertIsNone(sys._freelab_windows.get("size"))

    def test_a_tools_window_is_a_window_of_its_own(self):
        proof = self.open("Proof")
        self.assertIsNone(proof.dialog.parent, "no owner: a button of its own on the taskbar")
        self.assertIn(proof, sys._freelab_windows["kept"], "held while shown: nothing else keeps it alive")

    def test_a_window_closed_or_replaced_is_let_go(self):
        # sys._freelab_windows["kept"] held 18 hidden windows after a session, live
        filters = sys._freelab_window_filters = {}
        self.addCleanup(lambda: setattr(sys, "_freelab_window_filters", None))
        proof = self.open("Proof")
        filters[5] = "Proof's filter"
        proof.dialog.setProperty(ak.WINDOW_FILTER_PROP, 5)
        diacritics = self.Tool(self.workspace, u"FreeLab Glyph Compose")  # (from FontLab's menu: in Proof's place)
        ak.take_window("Glyph Compose", diacritics)
        diacritics.dialog.show()
        self.assertFalse(proof.dialog.visible)
        self.assertEqual(sys._freelab_windows["kept"], [proof, diacritics], "not while its own events run")
        self.run_timers()
        self.assertEqual(sys._freelab_windows["kept"], [diacritics], "let go once they have")
        self.assertEqual(filters, {}, "its filter too: its handler holds the window")
        diacritics.dialog.close()  # (by hand)
        diacritics.dialog.visible = True  # shown again before the wait is over: still needed
        self.run_timers()
        self.assertEqual(sys._freelab_windows["kept"], [diacritics])
        diacritics.dialog.close()
        self.run_timers()
        self.assertEqual(sys._freelab_windows["kept"], [])
        self.assertEqual(sys._freelab_windows["releasing"], [], "nothing waiting")

    def test_a_tool_opened_from_a_window_works_on_that_windows_font(self):
        self.workspace.currentPackage = self.two
        check = self.open("Font Check")
        window = check.dialog  # (the tool's object is emptied once its window is let go: let_go)
        self.workspace.currentPackage = self.one  # FontLab shows the other font; the click is in Two's window
        self.active = check.dialog
        with ak.opening_from(check.dialog):  # (its tools button, its arrows, a button handing glyphs over)
            diacritics = self.open("Glyph Compose")
        self.assertIs(diacritics.current_font(), self.two)
        self.assertFalse(window.visible, "its window's tool gave way")
        self.assertIsNone(sys._freelab_windows["hint"], "let go once it opened")
        self.active = None
        kerning = self.open("Auto Kerning")
        self.assertIs(kerning.current_font(), self.one, "from FontLab's menu: the font FontLab shows")

    def test_a_menu_launch_while_another_fonts_window_is_active_opens_on_the_font_fontlab_shows(self):
        # Live 2026-11-16: Glyph Compose open on Varela Round, still the active window; Bellefair brought
        # forward in FontLab; Font Check from FontLab's menu opened on Varela Round, in Glyph Compose's place
        compose = self.open("Glyph Compose")
        window = compose.dialog
        self.workspace.currentPackage = self.two
        self.active = compose.dialog  # (FontLab's menu leaves the active window as it was)
        check = self.open("Font Check")
        self.assertIsNotNone(check)
        self.assertIs(check.current_font(), self.two, "the font FontLab shows")
        self.assertEqual(check.dialog.windowTitle, u"FreeLab Font Check (Two)")
        self.assertTrue(window.visible, "the other font's window is left alone")
        self.assertIs(sys._freelab_windows["fonts"][self.one.id], compose)
        self.assertIs(sys._freelab_windows["fonts"][self.two.id], check)

    def test_a_menu_launch_never_brings_forward_another_fonts_window(self):
        check = self.open("Font Check")
        self.workspace.currentPackage = self.two
        self.active = check.dialog
        other = self.open("Font Check")
        self.assertIsNotNone(other, "Two has no Font Check: one is opened for it")
        self.assertEqual(check.dialog.calls, [], "One's is not brought forward")
        self.assertIs(other.current_font(), self.two)
        self.assertIsNone(self.open("Font Check"), "Two's own, brought forward")
        self.assertEqual(other.dialog.calls, ["raise", "activate"])

    def test_a_menu_launch_with_a_window_without_a_font_around(self):
        compose = self.open("Glyph Compose", u"FreeLab Glyph Compose")
        self.workspace.currentPackage = self.two
        compose_two = self.open("Glyph Compose")  # Two's window
        fonts, current = self.workspace.fonts, self.workspace.currentPackage
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")  # (FontLab's placeholder)
        fontless = self.open("Proof")  # (opened while no font was open, not yet given one)
        self.workspace.fonts, self.workspace.currentPackage = fonts, current
        self.assertIs(sys._freelab_windows["fonts"].get(None), fontless)
        self.active = fontless.dialog  # clicked last, then FontLab's menu
        self.assertIsNone(self.open("Glyph Compose"), "Two's own window comes forward")
        self.assertEqual(compose_two.dialog.calls, ["raise", "activate"])
        self.assertEqual(fontless.dialog.calls, [], "not the window without a font")
        check = self.open("Font Check")
        self.assertIs(check.current_font(), self.two)
        self.assertFalse(compose_two.dialog.visible, "Two's window gives way: still one window for Two")
        self.assertTrue(fontless.dialog.visible, "the window without a font stays, for the next font")
        self.assertTrue(compose.dialog.visible)
        self.assertEqual(sorted(sys._freelab_windows["fonts"], key=str), sorted([self.one.id, self.two.id, None], key=str))

    def test_a_window_without_a_font_never_makes_a_second_window_on_a_font(self):
        # The owner: no FreeLab window may land on a font that has a window of its own. A window opened with no
        # font, still waiting while FontLab shows a font with its own window: its tools button and arrows
        # open the tool on that font in that font's window (brought forward), and it goes on waiting
        self.workspace.currentPackage = self.two
        compose_two = self.open("Glyph Compose")  # Two's window
        fonts, current = self.workspace.fonts, self.workspace.currentPackage
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")
        fontless = self.open("Proof")
        self.workspace.fonts, self.workspace.currentPackage = fonts, current
        self.assertEqual(ak.fonts_tick(self.workspace), [], "Two has its window: this one waits")
        with ak.opening_from(fontless.dialog):  # its tools button: the tool Two's window shows
            self.assertIsNone(self.open("Glyph Compose"), "Two's window brought forward")
        self.assertEqual(compose_two.dialog.calls, ["raise", "activate"])
        with ak.opening_from(fontless.dialog):  # its arrow to the next tool
            spacing = self.open("Auto Spacing")
        self.assertIs(spacing.current_font(), self.two)
        self.assertFalse(compose_two.dialog.visible, "Two's window gives way to it")
        self.assertTrue(fontless.dialog.visible, "the window without a font goes on waiting")
        shown = [o for o in sys._freelab_windows["kept"] if o.dialog.visible and o.font_id == self.two.id]
        self.assertEqual(shown, [spacing], "one window on Two")
        self.assertIs(sys._freelab_windows["fonts"][self.two.id], spacing)
        self.assertIs(sys._freelab_windows["fonts"].get(None), fontless)
        self.assertIsNone(fontless.current_font(), "read again, it takes no font that has a window of its own")
        self.assertIsNone(fontless.font_id)
        self.assertEqual(fontless.dialog.windowTitle, u"FreeLab Proof")
        # Its top line: never "No font is open" while fonts are (One has no window: FontLab shows Two)
        self.assertEqual(ak.no_font_line(u"No font is open. Open one.", self.workspace),
                         u"This window has no font: <b>Two</b>, the font FontLab shows, has a window of its own. It "
                         u"hooks to the next font you open, or to a font without a window once FontLab shows it.")
        self.workspace.fonts = [self.two]
        self.assertEqual(ak.no_font_line(None, self.workspace), u"This window has no font: the font open has a window "
                                                                u"of its own. It hooks to the next font you open.")
        self.workspace.fonts = [self.one, self.two]
        one = self.Tool(self.workspace, u"FreeLab Font Check")  # One's window (shown, as a race may leave it)
        one.font_id, one.dialog.visible = self.one.id, True
        sys._freelab_windows["fonts"][self.one.id] = one
        self.assertEqual(ak.no_font_line(None, self.workspace), u"This window has no font: the 2 fonts open each have "
                                                                u"a window of their own. It hooks to the next font you open.")
        for line in (ak.no_font_line(None, self.workspace), ak.no_font_line(u"x", self.workspace)):
            self.assertNotIn(u"No font is open", line)
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")
        self.assertEqual(ak.no_font_line(None, self.workspace), ak.NO_FONT_LINE, "none open: as before")
        self.assertEqual(ak.no_font_line(u"No font is open. Open one.", self.workspace), u"No font is open. Open one.")
        self.workspace.fonts, self.workspace.currentPackage = [self.one, self.two], self.two
        del sys._freelab_windows["fonts"][self.one.id]
        three = self.Font(4242, u"Three")
        self.workspace.fonts, self.workspace.currentPackage = fonts + [three], three  # a font opened
        self.assertEqual(ak.fonts_tick(self.workspace), [fontless], "it takes the next font")
        self.assertIs(fontless.current_font(), three)

    def test_a_tool_opened_from_a_window_keeps_it_however_long_it_takes_to_open(self):
        # Codex's review, round 2: a tool slower than HINT_SECONDS to load lost its caller inside opening_from
        # and opened on the font FontLab shows, in that font's window
        class Clock(object):
            now = 1000.0

            def time(self):
                return self.now

            def __getattr__(self, name):
                return getattr(real_time, name)
        real_time, clock = ak.time, Clock()
        ak.time = clock
        self.addCleanup(setattr, ak, "time", real_time)
        one = self.open("Proof")  # One's window
        self.workspace.currentPackage = self.two
        two = self.open("Glyph Compose")  # Two's, FontLab showing Two
        window = one.dialog
        with ak.opening_from(one.dialog):  # One's tools button
            clock.now += ak.HINT_SECONDS + 1  # (the tool's script loads slowly)
            self.assertEqual(ak.calling_font(), self.one.id)
            check = self.open("Font Check")
        self.assertIs(check.current_font(), self.one, "One's window's font")
        self.assertFalse(window.visible, "in its place")
        self.assertTrue(two.dialog.visible, "Two's window left alone")
        self.assertIsNone(sys._freelab_windows["hint"], "let go once the block ended")
        with self.assertRaises(ZeroDivisionError):
            with ak.opening_from(check.dialog):
                1 / 0
        self.assertIsNone(sys._freelab_windows["hint"], "an error lets it go too")
        with ak.opening_from(check.dialog):
            with ak.opening_from(two.dialog):
                self.assertEqual(ak.calling_font(), self.two.id)
            clock.now += 60
            self.assertEqual(ak.calling_font(), self.one.id, "the outer block's caller, back")
        self.assertIsNone(sys._freelab_windows["hint"])
        ak.note_caller(check.dialog)  # (a hint noted alone, outside a block: it still lasts HINT_SECONDS)
        self.assertEqual(ak.calling_font(), self.one.id)
        clock.now += ak.HINT_SECONDS + 1
        self.assertIsNone(ak.calling_font())

    def test_freelabs_own_controls_open_a_tool_on_their_windows_font(self):
        # A window's tools button and arrows (open_tool), and the buttons that hand glyphs over
        # (open_kerning_check, open_auto_kerning_at, open_sibling_script, opening_from): the window's font,
        # in its place, whatever FontLab shows and whichever window is the active one
        case = self
        opened = []

        class Entry(object):
            def __init__(self, text):
                self.text = text

            def isSeparator(self):
                return False

            def trigger(self):  # (FontLab runs the entry's script before trigger returns, live)
                opened.append(case.open(self.text))

        class Menu(object):
            objectName = ak.SCRIPTS_MENU

            def __init__(self, entries):
                self.entries = entries

            def actions(self):
                return self.entries

            def menu(self):
                return self

            text = ak.MENU_TITLE

        class Main(object):
            def findChildren(self, kind):
                return [Menu([Menu([Entry(tool) for tool in ak.FONT_TOOLS])])]

        old_main = ak.AutoKerningDialog.__dict__["main_window"]  # (the staticmethod: read from the class, Python 2.7
        ak.AutoKerningDialog.main_window = staticmethod(lambda: Main())  # gives a function that goes back unbound)
        self.addCleanup(setattr, ak.AutoKerningDialog, "main_window", old_main)
        one = self.open("Proof")
        self.workspace.currentPackage = self.two
        two = self.open("Glyph Compose")
        for tool in ("Font Check", "Auto Spacing", "Proof"):  # the tools button, then its arrows
            window = one.dialog
            self.active = two.dialog  # (the other font's window was clicked last)
            self.assertTrue(ak.open_tool(tool, window))
            one = opened[-1]
            self.assertIs(one.current_font(), self.one, tool)
            self.assertFalse(window.visible, "the window clicked gives way")
            self.assertTrue(two.dialog.visible, "the other is left alone")
            self.assertIsNone(sys._freelab_windows["hint"], "let go once it opened")
        self.active = None
        loaded = []

        class Sibling(object):
            def main(module, **given):
                loaded.append(given)
                opened.append(case.open("Kerning Check"))

        old_load = ak.load_sibling
        ak.load_sibling = lambda file_name, module_name: Sibling()
        self.addCleanup(setattr, ak, "load_sibling", old_load)
        window = one.dialog
        self.assertIsNone(ak.open_kerning_check([u"A"], u"Auto Spacing spaced", caller=window))
        self.assertEqual(loaded, [{"glyphs": [u"A"], "reason": u"Auto Spacing spaced"}])
        one = opened[-1]
        self.assertIs(one.current_font(), self.one, "Auto Spacing's Check kerning")
        self.assertFalse(window.visible)
        window = one.dialog
        self.workspace.currentPackage = self.one
        compose = self.open("Glyph Compose")  # (FontLab's menu: One's window, now Glyph Compose)
        self.assertFalse(window.visible)
        self.workspace.currentPackage = self.two
        self.assertIsNone(ak.open_sibling_script(ak.KERNING_CHECK_FILE, ak.KERNING_CHECK_MODULE, caller=compose.dialog))
        one = opened[-1]
        self.assertIs(one.current_font(), self.one, "Auto Kerning's Kerning Check button")
        self.assertFalse(compose.dialog.visible)
        self.assertIsNone(sys._freelab_windows["hint"])
        self.assertIsNone(ak.open_sibling_script(ak.KERNING_CHECK_FILE, ak.KERNING_CHECK_MODULE, caller=one.dialog))
        self.assertIsNone(opened[-1], "its own window shows it already: brought forward")
        self.assertEqual(one.dialog.calls[-2:], ["raise", "activate"])
        window = one.dialog
        old_main_ak = ak.main
        ak.main = lambda focus=None: opened.append(case.open("Auto Kerning"))
        self.addCleanup(setattr, ak, "main", old_main_ak)
        self.assertIsNone(ak.open_auto_kerning_at(u"A", u"V", caller=window))
        self.assertIs(opened[-1].current_font(), self.one, "Auto Spacing's kern-this-pair")
        self.assertFalse(window.visible)
        self.assertTrue(two.dialog.visible)
        self.assertIsNone(sys._freelab_windows["hint"])
        kerning = self.open("Font Check")  # then FontLab's menu: the font FontLab shows, again
        self.assertIs(kerning.current_font(), self.two)

    def test_every_control_that_opens_a_tool_names_its_window(self):
        # A tool opened without its window named opens as from FontLab's menu: on the font FontLab shows
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        calls = {
            os.path.join("spacing", "freelab_auto_spacing.py"): ("open_kerning_check(", "open_auto_kerning_at("),
            os.path.join("kerning", "freelab_auto_kerning.py"): ("open_sibling_script(KERNING",),
            os.path.join("compose", "freelab_glyph_compose.py"): ("module.main(glyphs=names",),
            os.path.join("checks", "freelab_font_check.py"): ("dm.main(characters=chars)",),
        }
        for name, texts in sorted(calls.items()):
            with io.open(os.path.join(root, name), encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            for text in texts:
                found = [n for n, line in enumerate(lines) if text in line and "def " not in line]
                self.assertTrue(found, (name, text))
                for n in found:
                    near = u"\n".join(lines[max(0, n - 3):n + 2])
                    self.assertTrue("caller=self.dialog" in near or "opening_from(self.dialog)" in near, (name, text))
        with io.open(os.path.join(root, "kerning", "freelab_auto_kerning.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("open_tool(title, _window_of(button))", source, "the tools button and its arrows")
        self.assertNotIn("activeWindow()", source.split("def calling_font():")[1].split("def note_caller(")[0],
                         "never the window that has the focus")

    def test_a_windows_button_names_its_font_for_the_tool_it_opens(self):
        # (FontLab may run the menu entry once the click is over, the window no longer the active one)
        self.workspace.currentPackage = self.two
        check = self.open("Font Check")
        font_id = check.font_id
        self.workspace.currentPackage = self.one
        sys._freelab_windows["hint"] = (font_id, ak.time.time())
        self.assertIs(self.open("Glyph Compose").current_font(), self.two)
        self.assertIsNone(sys._freelab_windows["hint"], "used once")
        sys._freelab_windows["hint"] = (font_id, ak.time.time() - 60)
        self.assertIs(self.open("Proof").current_font(), self.one, "an old one counts no more")

    def test_the_tool_a_window_shows_comes_forward(self):
        proof = self.open("Proof")
        self.assertIsNone(self.open("Proof"), "opened anew, it would lose its checks and its log")
        self.assertEqual(proof.dialog.calls, ["raise", "activate"])
        proof.dialog.minimized = True
        self.open("Proof")
        self.assertEqual(proof.dialog.calls[2:], ["showNormal", "raise", "activate"])
        proof.dialog.visible = False
        self.assertIsNotNone(self.open("Proof"), "closed: opened anew")

    def test_a_window_closes_with_its_font_while_others_stay_open(self):
        # The owner: "In such a case, I'd suggest closing the script window along with the font it belongs to"
        # (it moved to the font FontLab showed, which could leave two windows on one font)
        proof = self.open("Proof")
        self.workspace.currentPackage = self.two
        other = self.open("Glyph Compose")
        window, other_window = proof.dialog, other.dialog
        self.workspace.fonts = [self.two]  # One closed
        self.assertIsNone(proof.current_font(), "never another font in its place, even before it closes")
        self.assertEqual(window.windowTitle, u"FreeLab Proof (One)")
        self.assertEqual(ak.fonts_tick(self.workspace), [proof])
        self.assertFalse(window.visible, "closed with its font")
        self.assertEqual(window.calls, ["close"], "as its close button does")
        self.assertTrue(other_window.visible, "the other font's window stays")
        self.run_timers()
        self.assertTrue(getattr(proof, ak.RELEASED, False), "let go once closed")
        self.assertEqual(sys._freelab_windows["fonts"], {self.two.id: other})
        self.assertEqual(ak.fonts_tick(self.workspace), [], "nothing more to do")
        self.assertIsNone(self.open("Glyph Compose"), "Two's window is still its only one")

    def test_a_tools_window_does_not_keep_fontlab_running(self):
        # A window of its own counted as one of FontLab's main windows: left open, FontLab kept running
        proof = self.open("Proof")
        self.workspace.currentPackage = self.two
        check = self.open("Font Check")
        for owner in (proof, check):
            self.assertIs(owner.dialog.props.get(("attribute", 98)), False, "WA_QuitOnClose off")
        self.assertEqual(sorted(self.app_slots), ["aboutToQuit()", "lastWindowClosed()"])
        self.assertEqual([len(slots) for slots in self.app_slots.values()], [1, 1], "connected once a session")
        self.app_slots["lastWindowClosed()"][0]()  # FontLab's main window closed
        self.assertFalse(proof.dialog.visible or check.dialog.visible)
        self.assertEqual(proof.dialog.calls, ["close"], "closed, as its close button does (nothing deleted)")

    def test_a_window_opened_with_no_font_is_its_fonts_once_it_reads_one(self):
        self.workspace.fonts, self.workspace.currentPackage = [], None
        proof = self.open("Proof")
        self.assertIsNone(proof.font_id)
        self.workspace.fonts, self.workspace.currentPackage = [self.one, self.two], self.one
        self.assertIs(proof.current_font(), self.one)
        self.assertIs(sys._freelab_windows["fonts"].get(self.one.id), proof)
        self.assertNotIn(None, sys._freelab_windows["fonts"], "no longer listed under no font")
        self.assertIsNone(self.open("Proof"), "it is that font's window: brought forward, not opened twice")
        window = proof.dialog
        diacritics = self.open("Glyph Compose")
        self.assertFalse(window.visible, "the next tool takes its place")
        self.assertTrue(diacritics.dialog.visible)

    def test_the_window_clicked_is_the_one_replaced(self):
        # Two fonts, a window each: a tool opened from one window (its tools button, or its hint once the
        # window is no longer the active one) replaces that window, never the other
        one = self.open("Proof")
        self.workspace.currentPackage = self.two
        other = self.open("Glyph Compose")
        one_window, other_window = one.dialog, other.dialog
        with ak.opening_from(one.dialog):  # its tools button clicked, while FontLab shows Two
            check = self.open("Font Check")
        self.assertFalse(one_window.visible, "the window clicked gives way")
        self.assertTrue(other_window.visible, "the other is left alone")
        self.assertIs(check.current_font(), self.one, "on the clicked window's font")
        self.assertIs(sys._freelab_windows["fonts"][self.one.id], check)
        sys._freelab_windows["hint"] = (other.font_id, ak.time.time(), other.window_key)
        spacing = self.open("Auto Spacing")
        self.assertFalse(other_window.visible)
        self.assertTrue(check.dialog.visible)
        self.assertTrue(spacing.dialog.visible)
        self.assertIs(spacing.current_font(), self.two)

    def test_a_size_qt_or_the_logs_grip_gives_is_not_a_size_given_by_hand(self):
        first = self.open("Proof", laid_out=(520, 360))  # Qt grew it to its layout as it showed it
        window = first.dialog
        second = self.open("Glyph Compose")
        self.assertFalse(window.visible)
        self.assertIsNone(sys._freelab_windows.get("size"), "measured once shown: nothing given by hand")
        self.assertEqual((second.dialog.width, second.dialog.height), (400, 300))
        before = second.dialog.height
        second.dialog.resize(400, before + 120)  # the log's grip drags the window's bottom edge
        ak.grip_resized(second.dialog, before)
        second.dialog.close()
        self.assertIsNone(sys._freelab_windows.get("size"), "the grip's doing")
        third = self.open("Proof")
        third.dialog.resize(700, 300)  # the owner drags its edge
        third.dialog.close()
        self.assertEqual(sys._freelab_windows.get("size"), (700, 300))

    def press(self, owner, key, held=0x04000000):
        """A key pressed in a tool's window, as Qt sends it to the window's filter: its ShortcutOverride, then
        (once taken) its key press."""
        override = self.KeyEvent(ak.SHORTCUT_OVERRIDE, key, held)
        if ak.filter_event(owner.dialog, owner.dialog, override, []) and override.accepted:
            ak.filter_event(owner.dialog, owner.dialog, self.KeyEvent(ak.KEY_PRESS, key, held), [])

    def test_undo_and_redo_reach_fontlab_for_this_windows_font_only(self):
        proof = self.open("Proof")
        self.assertEqual(self.shortcuts, {}, "no Ctrl+Z of the window's own: with FontLab's application-wide one, "
                                             "Qt's ambiguous case ran neither (live, 2026-11-17)")
        self.press(proof, ak.KEY_Z)
        self.press(proof, ak.KEY_Y)
        self.assertEqual(self.triggered, ["actionUndo", "actionRedo"])
        proof.busy = True  # inside its own loop
        self.press(proof, ak.KEY_Z)
        self.assertEqual(len(self.triggered), 2, "nothing while the tool is busy")
        proof.busy = False
        self.workspace.currentPackage = self.two  # FontLab shows the other font: its History, not this one's
        self.press(proof, ak.KEY_Z)
        self.assertEqual(len(self.triggered), 2)
        self.assertEqual(len(proof.lines), 1)
        level, text = proof.lines[0]
        self.assertEqual(level, "warning")
        self.assertIn(u"<b>One</b>'s Font window", text, "names the font to click")

    class KeyEvent(object):
        def __init__(self, kind, key, held):
            self.kind, self.code, self.held, self.accepted = kind, key, held, False

        def type(self):
            return self.kind

        def key(self):
            return self.code

        def modifiers(self):
            return self.held

        def accept(self):
            self.accepted = True

    def test_undo_keys_are_taken_before_any_shortcut_and_run_fontlabs_command(self):
        # The owner (2026-11-16): undo and redo pressed while a FreeLab window is in front never reach
        # FontLab. Taken at Qt's ShortcutOverride, before any shortcut is looked up, no shortcut of the
        # window or of FontLab (whatever its context) can make the key ambiguous or take it.
        proof = self.open("Proof")
        window, key = proof.dialog, self.KeyEvent
        override = key(ak.SHORTCUT_OVERRIDE, ak.KEY_Z, ak.CONTROL)
        self.assertTrue(ak.filter_event(window, window, override, []))
        self.assertTrue(override.accepted, "overridden: Qt then sends it as a plain key press")
        self.assertEqual(self.triggered, [], "nothing run at the override")
        self.assertTrue(ak.filter_event(window, window, key(ak.KEY_PRESS, ak.KEY_Z, ak.CONTROL), []))
        self.assertEqual(self.triggered, ["actionUndo"], "FontLab's Edit > Undo")
        keypad = 0x20000000
        ak.filter_event(window, window, key(ak.KEY_PRESS, ak.KEY_Z, ak.CONTROL | ak.SHIFT | keypad), [])
        ak.filter_event(window, window, key(ak.KEY_PRESS, ak.KEY_Y, ak.CONTROL), [])
        self.assertEqual(self.triggered, ["actionUndo", "actionRedo", "actionRedo"], "Ctrl+Shift+Z and Ctrl+Y redo")
        for held, code in ((ak.CONTROL | ak.ALT, ak.KEY_Z), (ak.CONTROL, 0x41), (0, ak.KEY_Z)):
            self.assertFalse(ak.filter_event(window, window, key(ak.SHORTCUT_OVERRIDE, code, held), []), "not ours")
        other = self.Window(u"FontLab")  # (a window no FreeLab tool shows: FontLab's own keys never touched)
        foreign = key(ak.SHORTCUT_OVERRIDE, ak.KEY_Z, ak.CONTROL)
        self.assertFalse(ak.filter_event(other, other, foreign, []))
        self.assertFalse(foreign.accepted)
        self.assertEqual(len(self.triggered), 3)

        class Field(object):
            readOnly, undoAvailable, redoAvailable = False, True, False

            @staticmethod
            def inherits(kind):
                return kind == "QLineEdit"

        field = Field()
        ak._qt()[1].QApplication.focusWidget = staticmethod(lambda: field)
        typed = key(ak.SHORTCUT_OVERRIDE, ak.KEY_Z, ak.CONTROL)
        self.assertFalse(ak.filter_event(window, field, typed, []), "a field typed in keeps the key")
        self.assertFalse(typed.accepted)
        field.undoAvailable = False
        for code, held in ((ak.KEY_Z, ak.CONTROL), (ak.KEY_Y, ak.CONTROL)):
            self.assertFalse(ak.filter_event(window, field, key(ak.SHORTCUT_OVERRIDE, code, held), []),
                             "nothing of its own to undo or redo: still its own, never FontLab's")
            self.assertFalse(ak.filter_event(window, field, key(ak.KEY_PRESS, code, held), []))
        self.assertEqual(len(self.triggered), 3)
        field.readOnly = True  # (read-only text, as the log: nothing to type, FontLab's)
        self.assertTrue(ak.filter_event(window, field, key(ak.KEY_PRESS, ak.KEY_Z, ak.CONTROL), []))
        self.assertEqual(self.triggered[-1], "actionUndo")

    def test_a_spin_box_typed_in_keeps_its_own_undo(self):
        # (Codex, round 4, finding 1: Qt makes a spin box its line edit's focus proxy, so the focus widget is
        # the box; Ctrl+Z while typing digits ran FontLab's Undo instead of the field's)
        proof = self.open("Proof")
        window, key = proof.dialog, self.KeyEvent

        class Edit(object):
            undoAvailable, redoAvailable = True, True

        edit = Edit()

        class Spin(object):
            readOnly = False

            @staticmethod
            def inherits(kind):
                return kind in ("QAbstractSpinBox", "QWidget")

            @staticmethod
            def findChildren(kind):
                return [edit] if kind == "QLineEdit" else []

        spin = Spin()
        gui = ak._qt()[1]
        gui.QLineEdit = "QLineEdit"
        gui.QApplication.focusWidget = staticmethod(lambda: spin)
        for code, held in ((ak.KEY_Z, ak.CONTROL), (ak.KEY_Z, ak.CONTROL | ak.SHIFT), (ak.KEY_Y, ak.CONTROL)):
            override = key(ak.SHORTCUT_OVERRIDE, code, held)
            self.assertFalse(ak.filter_event(window, spin, override, []), "left to the box")
            self.assertFalse(override.accepted, "the box takes it as its own")
            self.assertFalse(ak.filter_event(window, spin, key(ak.KEY_PRESS, code, held), []))
        self.assertEqual(self.triggered, [], "FontLab's Undo and Redo untouched")
        # (live, 2026-11-17: after typing 9, the value applied as typed, its line edit said nothing to undo,
        # and Ctrl+Z went to FontLab and undid a glyph build, the field still at 9)
        edit.undoAvailable = edit.redoAvailable = False
        for code, held in ((ak.KEY_Z, ak.CONTROL), (ak.KEY_Y, ak.CONTROL)):
            override = key(ak.SHORTCUT_OVERRIDE, code, held)
            self.assertFalse(ak.filter_event(window, spin, override, []))
            self.assertFalse(override.accepted)
            self.assertFalse(ak.filter_event(window, spin, key(ak.KEY_PRESS, code, held), []))
        self.assertEqual(self.triggered, [], "the box keeps it all the same")
        gui.QApplication.focusWidget = staticmethod(lambda: None)  # (the focus on the list, or nowhere)
        self.assertTrue(ak.filter_event(window, window, key(ak.KEY_PRESS, ak.KEY_Z, ak.CONTROL), []))
        self.assertEqual(self.triggered, ["actionUndo"], "elsewhere in the window: FontLab's")

    def test_an_undo_fontlab_cannot_do_is_said(self):
        proof = self.open("Proof")

        class Off(object):
            objectName = "actionUndo"

            @staticmethod
            def isEnabled():
                return False

        class Main(object):
            objectName = "MainWindow"

            @staticmethod
            def findChildren(kind):
                return [Off()]

        gui = ak._qt()[1]
        gui.QApplication.topLevelWidgets = staticmethod(lambda: [Main()])
        self.assertFalse(ak.fontlab_undo(proof, "actionUndo"))
        self.assertEqual(proof.lines[-1], ("info", u"FontLab has nothing to undo (its <i>Edit &gt; Undo</i> is grayed out)."))
        self.assertFalse(ak.fontlab_undo(proof, "actionRedo"))
        self.assertEqual(proof.lines[-1], ("warning", u"Nothing was redone: FontLab's <i>Edit &gt; Redo</i> was not found."))
        self.assertEqual(self.triggered, [])

    def test_an_undo_from_a_window_redraws_fontlabs_views(self):
        # The owner: "The log does mention the history changed, but it doesn't appear to actually reach FontLab"
        proof = self.open("Proof")
        told = []

        class Items(object):
            def __getattr__(self, name):
                return lambda *args: told.append((name,) + args)

        fontlab = sys.modules["fontlab"]
        fontlab.flItems = Items()
        self.addCleanup(lambda: delattr(fontlab, "flItems"))
        self.press(proof, ak.KEY_Z)
        self.assertEqual(self.triggered, ["actionUndo"])
        self.assertEqual(told, [], "told once FontLab's command has run")
        self.run_timers()
        self.assertEqual([call[0] for call in told], ["notifyPackageUpdated", "notifyHistoryChanged"],
                         "not notifyPackageContentUpdated: 8.8 s a Ctrl+Z on a 3,700-glyph font, live")
        self.assertEqual(told[0][1:], (self.one.id,), "this window's font")
        self.assertNotIn("notifyChangesApplied", [call[0] for call in told], "no step of the History of its own")

    def test_a_window_closes_with_the_last_font_too(self):
        # (a window is its font's for good: one left open without a font, waiting for the next, was the font's
        # window no more, and "navigating again opens a new window", the owner)
        spacing = self.open("Auto Spacing")
        window, changes = spacing.dialog, []
        spacing.font_changed = lambda: changes.append(("spacing", spacing.font_id))
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")  # (FontLab's placeholder)
        self.assertEqual(ak.fonts_tick(self.workspace), [spacing])
        self.assertFalse(window.visible)
        self.assertEqual(changes, [], "closed, not shown without a font")
        self.run_timers()
        self.assertEqual(sys._freelab_windows["fonts"], {})
        self.assertIsNotNone(self.open("Auto Spacing"), "opened anew, without a font")

    def test_a_window_opened_with_no_font_is_reused_then_takes_the_next_font(self):
        # The owner: "can't it also detect when a font then gets open after its launch to hook into that one?"
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")  # (FontLab's placeholder)
        spacing = self.open("Auto Spacing")
        window, changes = spacing.dialog, []
        self.assertIsNone(spacing.font_id)
        self.assertEqual(spacing.dialog.windowTitle, u"FreeLab Auto Spacing", "its title without a font")
        self.assertIs(sys._freelab_windows["fonts"].get(None), spacing)
        self.assertEqual(ak.fonts_tick(self.workspace), [], "nothing to do")
        self.assertIsNone(self.open("Auto Spacing"), "FontLab's menu brings it forward: no second window")
        with ak.opening_from(spacing.dialog):  # its arrow to the next tool
            kerning = self.open("Auto Kerning")
        self.assertFalse(window.visible, "the window clicked gives way, as one with a font does")
        self.assertIs(sys._freelab_windows["fonts"].get(None), kerning)
        self.assertIsNone(self.open("Auto Kerning"), "and the menu finds it again")
        three = self.Font(4242, u"Three")
        self.workspace.fonts, self.workspace.currentPackage = [three], three  # a font opened
        kerning.font_changed = lambda: changes.append(("kerning", kerning.font_id))
        self.assertEqual(ak.fonts_tick(self.workspace), [kerning])
        self.assertEqual(changes[-1], ("kerning", 4242), "the tool reads it")
        self.assertEqual(kerning.dialog.windowTitle, u"FreeLab Auto Kerning (Three)")
        self.assertIs(sys._freelab_windows["fonts"][4242], kerning)
        self.assertNotIn(None, sys._freelab_windows["fonts"])
        self.assertIsNone(self.open("Auto Kerning"), "the font's window now")

    def test_a_window_without_a_font_takes_the_one_fontlab_shows(self):
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")
        proof = self.open("Proof")
        self.assertIsNone(getattr(proof, "font_id", None))
        self.workspace.fonts, self.workspace.currentPackage = [self.one, self.two], self.two  # two opened at once
        self.assertEqual(ak.fonts_tick(self.workspace), [proof])
        self.assertEqual(proof.font_id, self.two.id, "the one FontLab shows")
        busy = self.open("Glyph Compose")  # (on Two too: it takes the window's place)
        window = busy.dialog
        self.workspace.fonts, self.workspace.currentPackage = [self.one], self.one  # Two closed
        busy.busy = True
        self.assertEqual(ak.fonts_tick(self.workspace), [], "a busy window is looked at next time")
        self.assertTrue(window.visible)
        busy.busy = False
        self.assertEqual(ak.fonts_tick(self.workspace), [busy])
        self.assertFalse(window.visible, "closed with its font once its work is done")

    def test_a_window_is_let_go_only_once_its_work_is_done(self):
        proof = self.open("Proof")
        proof.busy = True  # (closed while inside its own loop, which lets events through)
        proof.dialog.close()
        self.timers.pop(0)()  # (RELEASE_MS later)
        self.assertFalse(getattr(proof, ak.RELEASED, False), "its loop still works on it")
        self.assertEqual(len(sys._freelab_windows["releasing"]), 1, "looked at again later")
        self.assertEqual(len(self.timers), 1)
        proof.busy = False
        self.run_timers()
        self.assertTrue(getattr(proof, ak.RELEASED, False))
        self.assertEqual(sys._freelab_windows["releasing"], [])

    def test_a_window_let_go_is_held_by_nothing_freelab_keeps(self):
        # Hidden windows were never freed: closures Qt held still reached them (PythonQt frees a window made
        # from Python once nothing refers to it; deleteLater crashed FontLab)
        case = self
        proof = self.open("Proof")
        window = proof.dialog
        window.window = lambda: window
        filters = sys._freelab_window_filters = {7: "Proof's filter"}
        window.setProperty(ak.WINDOW_FILTER_PROP, 7)
        disconnected, forgotten, told = [], [], []

        class Timer(object):
            def __init__(self):
                self.running, self.owner = True, None

            def inherits(self, name):
                return name == "QTimer"

            def metaObject(self):
                return "QTimer"

            def parent(self):
                return self.owner

            def setParent(self, parent):
                self.owner = parent

            def stop(self):
                self.running = False

            def disconnect(self, signal, slot):
                disconnected.append((self, signal, slot))

        class Sender(object):
            def __init__(self, parent):
                self.parent = parent

            def window(self):
                return self.parent

            def disconnect(self, signal, slot):
                disconnected.append((self, signal, slot))

        states_timer = Timer()
        tick = lambda: None
        tick.dialog, tick.timer = window, states_timer
        old_watchers = getattr(sys, "_freelab_state_watchers", None)
        sys._freelab_state_watchers = [tick, "another window's tick"]
        button, other_button = Sender(window), Sender(object())
        slot = lambda: None
        saved_buttons = list(ak._TOOL_BUTTONS)
        ak._TOOL_BUTTONS[:] = [(button, "menu", [slot], [(button, "clicked()", slot)]),
                               (other_button, "menu", [], [])]

        class DarkMode(object):
            @staticmethod
            def forget(widget):
                forgotten.append(widget)
                return True

        old_dark = getattr(sys, "_freelab_dark_mode", None)
        sys._freelab_dark_mode = {"module": DarkMode}

        def restore():
            sys._freelab_window_filters = None
            sys._freelab_state_watchers = old_watchers
            sys._freelab_dark_mode = old_dark
            ak._TOOL_BUTTONS[:] = saved_buttons
        self.addCleanup(restore)
        own_timer = proof.history_timer = Timer()
        proof.timers = [Timer()]
        part = type("Page", (object,), {})()  # (a part the tool holds: Glyph Compose's anchors page)
        part.redraw_timer, part.owner = Timer(), proof
        proof.anchors = part
        shared = type(sys)("shared")  # (the shared module a tool holds: its timers serve every window)
        shared.watch = Timer()
        proof.ak = shared
        proof.let_go = lambda: told.append("tool")
        window.close()
        self.run_timers()
        self.assertTrue(getattr(proof, ak.RELEASED, False))
        self.assertEqual(sorted(proof.__dict__), [ak.RELEASED], "the tool's object holds nothing more")
        self.assertEqual(sys._freelab_windows["kept"], [])
        self.assertNotIn(proof, sys._freelab_windows["fonts"].values())
        self.assertEqual(filters, {})
        self.assertEqual(sys._freelab_state_watchers, ["another window's tick"])
        self.assertFalse(states_timer.running)
        self.assertEqual([entry[0] for entry in ak._TOOL_BUTTONS], [other_button], "the other window's button stays")
        self.assertIn((button, "clicked()", slot), disconnected)
        self.assertIn((states_timer, "timeout()", tick), disconnected)
        self.assertEqual(forgotten, [window], "dark mode's records of its widgets")
        self.assertEqual(told, ["tool"], "what the tool connected outside its window")
        self.assertFalse(own_timer.running, "its timers stopped")
        self.assertFalse(part.redraw_timer.running, "and its parts' (one level down)")
        self.assertTrue(shared.watch.running, "never a module's")
        # Freed by Qt alone, once: given FontLab's main window as its parent (PythonQt leaves a parented
        # object to Qt), its parentless timers given the window, then deleteLater from a plain timer
        self.assertIs(own_timer.owner, window, "a timer made from Python dies with the window, through Qt")
        self.assertIs(part.redraw_timer.owner, window)
        self.assertIsNone(shared.watch.owner)
        self.assertEqual(type(window.parent).__name__, "Main", "FontLab's main window")
        self.assertEqual(window.flags, "window flags", "a window still, hidden")
        self.assertEqual(window.calls.count("deleteLater"), 1, "deleted once")
        self.assertEqual(sys._freelab_windows[ak.DELETING], [], "held until deleteLater was asked, then let go")
        self.assertFalse(case.timers, "nothing left waiting")

    def test_without_fontlabs_main_window_a_window_is_kept_rather_than_freed_by_pythonqt(self):
        proof = self.open("Proof")
        window = proof.dialog
        saved = ak.AutoKerningDialog.main_window
        ak.AutoKerningDialog.main_window = staticmethod(lambda: None)
        # (put back as a static method: Python 2 makes a plain function set on a class an unbound method)
        self.addCleanup(lambda: setattr(ak.AutoKerningDialog, "main_window", staticmethod(saved)))
        window.close()
        self.run_timers()
        self.assertNotIn("deleteLater", window.calls)
        self.assertIn(window, sys._freelab_windows["unfreed"], "held, hidden: never freed at a random moment")
        sys._freelab_windows["unfreed"] = []

    def test_work_still_pending_on_a_tool_let_go_does_nothing(self):
        # Live: a refresh asked for by a list as it was deleted ran on it afterwards; a write through a
        # deleted list's item corrupts FontLab's heap without a word
        import types
        proof = self.open("Proof")
        written = []

        class Item(object):
            def setText(self, column, text):
                written.append(text)

        class Tree(object):
            def topLevelItem(self, index):
                return Item()

        proof.tree = Tree()
        touch = types.MethodType(lambda self: self.tree.topLevelItem(0).setText(0, u"x"), proof)
        touch()
        self.assertEqual(written, [u"x"])
        proof.dialog.close()
        self.run_timers()
        self.assertTrue(getattr(proof, ak.RELEASED, False))
        touch()  # (a slot Qt still held, bound to the tool's object)
        self.assertEqual(written, [u"x"], "nothing reached the list")
        self.assertIsNotNone(proof.update_buttons(), "any method: nothing done, nothing raised")
        self.assertFalse(getattr(proof, "busy", False))
        self.assertEqual(list(proof.anything), [])
        # written to, it stays nothing (one object stands for every attribute of every tool let go)
        proof.tree.rows = [u"a row"]
        proof.tree[0] = u"a row"
        self.assertEqual(list(proof.tree.rows), [])
        self.assertFalse(proof.log)
        ak.flag_glyphs(proof, [u"A"], u"Red", 1)  # (picked in a menu that stayed open while the window closed)
        self.assertEqual(written, [u"x"])

    def test_a_flag_refresh_never_runs_on_a_list_gone(self):
        case, scheduled, touched = self, [], []

        class View(object):
            deleted = False

            def metaObject(self):
                if self.deleted:
                    raise ValueError("Trying to call 'metaObject' on a destroyed QTreeWidget object")
                return "QTreeWidget"

            def signalsBlocked(self):
                touched.append("signalsBlocked")
                return False

            def blockSignals(self, on):
                touched.append("blockSignals")

            topLevelItemCount = 0

            def viewport(self):
                return type("Viewport", (object,), {"update": lambda viewport: touched.append("update")})()

        class Owner(object):
            pass

        menu = ak.FlagMenu.__new__(ak.FlagMenu)
        menu.view, menu.owner, menu.names_of_row = View(), Owner(), lambda handle: []
        menu.refreshing, menu.due, menu.cache, menu.table = False, False, {}, False
        saved = ak._qt

        class Core(object):
            class QTimer(object):
                @staticmethod
                def singleShot(ms, slot):
                    scheduled.append(slot)
        ak._qt = lambda: (Core, None)
        self.addCleanup(lambda: setattr(ak, "_qt", saved))
        menu.soon(True)
        self.assertEqual(len(scheduled), 1)
        menu.view.deleted = True  # (deleted with its window before the timer fired)
        scheduled.pop()()
        self.assertEqual(touched, [], "nothing asked of the deleted list")
        menu.soon(True)
        self.assertEqual(scheduled, [], "and nothing more asked for")
        menu.view.deleted = False
        menu.owner.released = True  # (its tool let go)
        menu.refresh()
        menu.go(1)
        self.assertEqual(touched, [])

    def test_a_close_button_closes_through_the_tools_object(self):
        proof = self.open("Proof")
        window = proof.dialog
        close = ak.close_slot(proof)
        self.assertIs(proof.close_slot, close, "held with the tool")
        self.assertNotIn(window, [cell.cell_contents for cell in (close.__closure__ or ())],
                         "the slot never refers to the window itself")
        close()
        self.assertFalse(window.visible)
        self.run_timers()
        close()  # (clicked again after the window was let go: nothing happens)

    def test_a_glyph_tab_opens_for_this_windows_font_only(self):
        proof = self.open("Proof")
        self.active = proof.dialog
        self.workspace.currentPackage = self.two
        error = ak.show_in_glyph_window(sys.modules["fontlab"], u"/A")
        self.assertIn(u"click One's Font window", error)
        self.assertEqual(self.triggered, [])
        self.workspace.currentPackage = self.one
        self.assertIsNone(ak.show_in_glyph_window(sys.modules["fontlab"], u"/A"))
        self.assertEqual(self.triggered, [ak.GLYPH_TAB_ACTION])
        self.active = None  # from no tool window: FontLab's current font, as before
        self.workspace.currentPackage = self.two
        self.assertIsNone(ak.show_in_glyph_window(sys.modules["fontlab"], u"/A"))

    def test_a_window_whose_font_is_gone_never_acts_on_the_font_in_front(self):
        """Undo from the window of a font just closed (before fonts_tick closes the window) undid the font FontLab
        showed: foreign_font said nothing of a font it could not find (adversarial review 4). Undo, Redo, and a new
        Glyph tab refuse unless FontLab's current font is positively the window's."""
        proof = self.open("Proof")
        self.active = proof.dialog
        self.workspace.fonts.remove(self.one)  # (One closed; Two in front)
        self.workspace.currentPackage = self.two
        for name, done in (("actionUndo", u"undone"), ("actionRedo", u"redone")):
            self.assertFalse(ak.fontlab_undo(proof, name))
            self.assertEqual(proof.lines[-1], ("warning", u"Nothing was %s: FontLab's <i>%s</i> works on the font it "
                                                          u"shows, and this window's font is no longer open (or FontLab "
                                                          u"could not say which font it shows)." % (
                                                              done, u"Undo" if done == u"undone" else u"Redo")))
        self.assertIn(u"no longer open", ak.show_in_glyph_window(sys.modules["fontlab"], u"/A"))
        self.assertEqual(self.triggered, [], "nothing run on Two")
        # FontLab's current font unreadable: refused too, the window's font open or not
        self.workspace.fonts.insert(0, self.one)
        self.workspace.currentPackage = object()
        self.assertFalse(ak.fontlab_undo(proof, "actionUndo"))
        self.assertIsNotNone(ak.show_in_glyph_window(sys.modules["fontlab"], u"/A"))
        self.assertEqual(self.triggered, [])
        self.assertFalse(ak.font_shown(proof))
        # Its own font in front: run
        self.workspace.currentPackage = self.one
        self.assertTrue(ak.font_shown(proof))
        self.assertTrue(ak.fontlab_undo(proof, "actionUndo"))
        self.assertIsNone(ak.show_in_glyph_window(sys.modules["fontlab"], u"/A"))
        self.assertEqual(self.triggered, ["actionUndo", ak.GLYPH_TAB_ACTION])
        fills = ak.pending_slots() & set(self.timers)
        self.assertEqual(len(fills), 1, "the Glyph tab's fill held until it runs")
        self.run_timers()
        self.assertFalse(fills & ak.pending_slots(), "and let go once it ran")

    def test_the_tools_follow_the_order_of_the_work(self):
        self.assertEqual(ak.FONT_TOOLS[0], "Font Builder", "drawn first, then the rest built from it")
        self.assertEqual(ak.FONT_TOOLS[-2:], ("Font Check", "Proof"), "checked before it is proofed")
        self.assertEqual(ak.tool_neighbors("Glyph Compose"), ("Font Builder", "Auto Spacing"))
        self.assertEqual(ak.tool_neighbors("Feature Check"), ("Feature Code", "Font Compare"), "code checked once written")
        self.assertEqual(ak.tool_neighbors("Kerning Check"), ("Auto Kerning", "Feature Code"))
        self.assertEqual(ak.tool_neighbors("Proof"), ("Font Check", None))
        self.assertEqual(ak.tool_neighbors("No Such Tool"), (None, None))


class ThemeFakes(object):
    """Just enough of PythonQt for the windows following dark mode (pictures, items, palettes)."""

    LIGHT = {"Window": (240, 240, 240), "WindowText": (0, 0, 0), "Text": (0, 0, 0), "Base": (255, 255, 255),
             "Highlight": (0, 120, 215), "HighlightedText": (255, 255, 255), "disabled Text": (120, 120, 120)}
    DARK = {"Window": (53, 53, 53), "WindowText": (219, 219, 219), "Text": (219, 219, 219), "Base": (31, 31, 31),
            "Highlight": (61, 111, 184), "HighlightedText": (255, 255, 255), "disabled Text": (110, 110, 110)}

    class Color(object):
        def __init__(self, r, g, b, a=255):
            self.rgba = [r, g, b, a]

        def red(self):
            return self.rgba[0]

        def green(self):
            return self.rgba[1]

        def blue(self):
            return self.rgba[2]

        def alpha(self):
            return self.rgba[3]

        def setAlpha(self, alpha):
            self.rgba[3] = alpha

        def lightness(self):
            return (max(self.rgba[:3]) + min(self.rgba[:3])) // 2

    class Palette(object):
        Active, Disabled = 0, 2

        def __init__(self, colors=None):
            self.colors = colors or {}  # (none: as QPalette() is, the application's, nothing set)

        def color(self, *args):
            group, role = (0, args[0]) if len(args) == 1 else args
            key = ("disabled " if group == 2 else "") + role
            rgb = self.colors.get(key, self.colors.get(role, (1, 2, 3)))
            return ThemeFakes.Color(*rgb)

    class Brush(object):
        def __init__(self, color=None, style=1):
            self._color, self._style = color, style if color is not None else 0

        def color(self):
            return self._color or ThemeFakes.Color(0, 0, 0)

        def style(self):
            return self._style

    class Icon(object):
        keys = [100]

        def __init__(self, pixmap=None):
            ThemeFakes.Icon.keys[0] += 1
            self.key = ThemeFakes.Icon.keys[0]

        def cacheKey(self):
            return self.key

        def isNull(self):
            return False

    class Item(object):
        def __init__(self, icon=None, brush=None):
            self.icons, self.brushes, self.children = {0: icon}, {0: brush}, []

        def icon(self, column):
            return self.icons.get(column)

        def setIcon(self, column, icon):
            self.icons[column] = icon

        def foreground(self, column):
            return self.brushes.get(column) or ThemeFakes.Brush()

        def setForeground(self, column, brush):
            self.brushes[column] = brush

        def background(self, column):
            return ThemeFakes.Brush()

        def childCount(self):
            return len(self.children)

        def child(self, index):
            return self.children[index]

    class Tree(object):
        columnCount = 2

        def __init__(self, items):
            self.items = items

        def blockSignals(self, on):
            return False

        def inherits(self, name):
            return name == "QTreeWidget"

        @property
        def topLevelItemCount(self):
            return len(self.items)

        def topLevelItem(self, index):
            return self.items[index]


class ThemeTests(unittest.TestCase):
    """FreeLab's windows follow a dark mode switch at once, both ways, repeatedly (owner's screenshots 76
    and 77: stale cells, labels, pictures, and buttons until the window was opened again)."""

    def setUp(self):
        fakes = ThemeFakes
        case = self
        self.palette = fakes.Palette(dict(fakes.LIGHT))
        self.widgets = []

        class App(object):
            @staticmethod
            def palette():
                return case.palette

            @staticmethod
            def allWidgets():
                return list(case.widgets)

        class Gui(object):
            QPalette = fakes.Palette
            QColor = fakes.Color
            QBrush = fakes.Brush
            QIcon = fakes.Icon
            QDialog = "QDialog"

            class QApplication(object):
                @staticmethod
                def instance():
                    return App()

        class Core(object):
            class Qt(object):
                WA_SetPalette = 13

        for role in ak.THEME_ROLES:
            setattr(fakes.Palette, role, role)
        old = (ak._qt, ak.retinted, getattr(sys, "_freelab_windows", None), getattr(sys, "_freelab_theme_hook", None))
        ak._qt = lambda: (Core, Gui)
        self.retints = []

        def retinted(picture, rgb):
            self.retints.append((picture, rgb))
            return ak.inked(fakes.Icon(), rgb)
        ak.retinted = retinted
        sys._freelab_windows, sys._freelab_theme_hook = None, None

        def restore():
            ak._qt, ak.retinted, sys._freelab_windows, sys._freelab_theme_hook = old
        self.addCleanup(restore)

    def test_colors_map_role_by_role_and_the_logs_swap(self):
        old, new = ak.theme_colors(ThemeFakes.Palette(ThemeFakes.LIGHT)), ak.theme_colors(ThemeFakes.Palette(ThemeFakes.DARK))
        self.assertFalse(ak.theme_dark(old))
        self.assertTrue(ak.theme_dark(new))
        mapping = ak.theme_map(old, new)
        self.assertEqual(mapping[(0, 0, 0)], (219, 219, 219), "text")
        self.assertNotIn((255, 255, 255), mapping, "a color both palettes give the same role is not listed")
        self.assertEqual(mapping[(120, 120, 120)], (110, 110, 110), "grayed-out text")
        warning = ak.LOG_COLORS["warning"]
        self.assertEqual(mapping[warning[1]], warning[0], "a log's amber for a light background, for a dark one")
        back = ak.theme_map(new, old)
        self.assertEqual(back[(219, 219, 219)], (0, 0, 0))
        self.assertEqual(back[warning[0]], warning[1])

    def test_a_picture_in_one_color_is_noted_and_its_icon_too(self):
        pixmap = ThemeFakes.Icon()
        self.assertIs(ak.inked(pixmap, ThemeFakes.Color(0, 0, 0)), pixmap)
        self.assertEqual(ak.ink_of(pixmap), (0, 0, 0))
        icon = ak.icon_of(pixmap)
        self.assertEqual(ak.ink_of(icon), (0, 0, 0), "the icon made of it is another picture to Qt")
        self.assertIsNone(ak.ink_of(ak.icon_of(ThemeFakes.Icon())), "a picture never noted: left as drawn")
        self.assertIsNone(ak.ink_of(None))

    def test_a_lists_pictures_and_grayed_rows_take_the_new_colors(self):
        fakes = ThemeFakes
        black = ak.inked(fakes.Icon(), (0, 0, 0))
        red = ak.inked(fakes.Icon(), (200, 0, 0))  # (a fixed color: no role's)
        quiet = fakes.Brush(fakes.Color(0, 0, 0, 120))  # (the text color, faded)
        grayed = fakes.Brush(fakes.Color(120, 120, 120))
        child = fakes.Item(black, grayed)
        top = fakes.Item(red, quiet)
        top.children.append(child)
        plain = fakes.Item(None, None)
        tree = fakes.Tree([top, plain])
        mapping = ak.theme_map(ak.theme_colors(fakes.Palette(fakes.LIGHT)), ak.theme_colors(fakes.Palette(fakes.DARK)))
        self.assertEqual(ak.retheme_items(tree, mapping), 3)
        self.assertEqual(self.retints, [(black, (219, 219, 219))], "the red one keeps its color")
        self.assertEqual(ak.ink_of(child.icons[0]), (219, 219, 219), "and can follow the next switch")
        self.assertEqual(top.brushes[0].color().rgba, [219, 219, 219, 120], "faded as it was")
        self.assertEqual(child.brushes[0].color().rgba, [110, 110, 110, 255])
        self.assertIsNone(plain.brushes[0], "an item's own palette colors are left to Qt")

    def test_a_lists_items_redrawn_are_no_edit(self):
        # Glyph Compose dropped its revealed rows, and Feature Code wrote its code again row by row, on the
        # itemChanged each redrawn item sent (review)
        fakes, edits = ThemeFakes, []

        class Item(fakes.Item):
            def setIcon(self, column, icon):
                fakes.Item.setIcon(self, column, icon)
                tree.changed(self)

            def setForeground(self, column, brush):
                fakes.Item.setForeground(self, column, brush)
                tree.changed(self)

        class Tree(fakes.Tree):
            blocked, calls = False, []

            def blockSignals(self, on):
                was, self.blocked = self.blocked, on
                self.calls.append(on)
                return was

            def changed(self, item):
                if not self.blocked:
                    edits.append(item)  # (itemChanged reaching the tool's handler)

        item = Item(ak.inked(fakes.Icon(), (0, 0, 0)), fakes.Brush(fakes.Color(0, 0, 0)))
        tree = Tree([item])
        mapping = ak.theme_map(ak.theme_colors(fakes.Palette(fakes.LIGHT)), ak.theme_colors(fakes.Palette(fakes.DARK)))
        self.assertEqual(ak.retheme_items(tree, mapping), 2)
        self.assertEqual(edits, [], "no handler ran")
        self.assertEqual(tree.calls, [True, False], "held, then let go as it was")
        tree.blocked, tree.calls = True, []
        ak.retheme_items(tree, mapping)
        self.assertEqual(tree.calls, [True, True], "a list held already stays held")

    def test_a_busy_window_catches_up_once_its_work_is_done(self):
        ak.hook_theme()
        owner, label, _ = self.window()
        other, other_label, _ = self.window()
        owner.busy = True  # (an analysis under way, which lets events through)
        self.palette = ThemeFakes.Palette(dict(ThemeFakes.DARK))
        self.assertEqual(sys._freelab_theme_hook(True), [other], "not redrawn mid-loop")
        self.assertEqual(ak.ink_of(label.pixmap), (0, 0, 0))
        self.assertEqual(owner.calls, [])
        self.assertEqual(ak.theme_tick(), [], "still busy")
        owner.busy = False
        self.assertEqual(ak.theme_tick(), [owner], "the next tick catches it up")
        self.assertEqual(ak.ink_of(label.pixmap), (219, 219, 219))
        self.assertEqual(owner.calls, ["log", "tool"])
        self.assertEqual(other.calls, ["log", "tool"], "the other one is not redrawn twice")
        self.assertEqual(ak.theme_tick(), [])
        ak.note_theme(owner)
        self.assertEqual(getattr(owner, ak.THEME_ATTR), ak.theme_colors(self.palette), "a window built now: drawn in now's")

    def window(self, theme_changed=True, shown=True):
        """A tool's window: a label with a picture, and a list; its dialog object."""
        fakes, case = ThemeFakes, self
        polished = []

        class Style(object):
            def unpolish(self, widget):
                polished.append(("unpolish", widget.name))

            def polish(self, widget):
                polished.append(("polish", widget.name))

        class Palette(object):
            def __init__(self, mask):
                self.mask = mask

            def resolve(self):
                return self.mask

        class Widget(object):
            def __init__(self, name, parent=None, kinds=()):
                self.name, self.parent, self.kinds, self.set_palette = name, parent, kinds, False
                self.pixmap = None

            @property
            def palette(self):
                return Palette(1 if self.set_palette else 0)

            def setPalette(self, palette):
                polished.append(("palette", self.name))

            def inherits(self, kind):
                return kind in self.kinds

            def parentWidget(self):
                return self.parent

            def isAncestorOf(self, other):
                while other is not None:
                    if other is self:
                        return True
                    other = other.parent
                return False

            def findChildren(self, kind):
                return []

            def testAttribute(self, attribute):
                return self.set_palette

            def style(self):
                return Style()

            def update(self):
                pass

            def isVisible(self):
                return shown

            def setPixmap(self, pixmap):
                self.pixmap = pixmap

        dialog = Widget("dialog")
        label = Widget("label", dialog, ("QLabel",))
        label.pixmap = ak.inked(fakes.Icon(), (0, 0, 0))
        island = Widget("island", dialog)
        island.set_palette = True  # (dark mode's island: its palette is dark mode's)
        sheeted = Widget("sheeted", dialog)
        sheeted.set_palette = True  # (a stylesheet with colors: Qt marks its palette as set too)
        islands = self.islands = getattr(self, "islands", [])
        islands.append(island)
        dark = type(sys)("dark")
        dark.owns_palette = lambda widget: any(widget is one for one in islands)
        saved = getattr(sys, "_freelab_dark_mode", None)
        sys._freelab_dark_mode = {"module": dark}
        self.addCleanup(lambda: setattr(sys, "_freelab_dark_mode", saved))
        self.widgets.extend([label, island, sheeted, dialog])

        class Owner(object):
            pass
        owner = Owner()
        owner.dialog, owner.window_key, owner.calls = dialog, len(self.widgets), []

        class FakeLog(ak.Log):
            def __init__(self):
                self.entries, self.view = [], None

            def restyle(self):
                owner.calls.append("log")
        owner.log = FakeLog()
        if theme_changed:
            owner.theme_changed = lambda: owner.calls.append("tool")
        registry = ak._windows()
        registry.setdefault("kept", []).append(owner)
        return owner, label, polished

    def test_a_switch_redraws_every_shown_window_once(self):
        ak.hook_theme()
        owner, label, polished = self.window()
        hidden, _, hidden_polish = self.window(shown=False)
        self.palette = ThemeFakes.Palette(dict(ThemeFakes.DARK))  # dark mode switched on
        followed = sys._freelab_theme_hook(True)
        self.assertEqual(followed, [owner], "a closed window is let go, not redrawn")
        self.assertEqual(polished[:3], [("unpolish", "dialog"), ("palette", "dialog"), ("polish", "dialog")],
                         "the window first, then its children: unpolished, its palette inherited again, polished")
        self.assertIn(("palette", "label"), polished, "a widget with no palette of its own takes its parent's again")
        self.assertNotIn(("palette", "sheeted"), polished, "one its stylesheet colors is polished from them again")
        self.assertIn(("polish", "label"), polished)
        self.assertNotIn(("polish", "island"), polished, "a palette dark mode set is kept")
        self.assertIn(("polish", "sheeted"), polished,
                      "a palette its stylesheet set is read again (Font Check's scripts list stayed light, live)")
        self.assertEqual(ak.ink_of(label.pixmap), (219, 219, 219), "its picture in the new text color")
        self.assertEqual(owner.calls, ["log", "tool"], "its logs, then the tool's own")
        self.assertEqual(sys._freelab_theme_hook(True), [], "told twice: done once")
        self.assertEqual(ak.theme_tick(), [], "and the windows' tick has nothing more to do")
        self.palette = ThemeFakes.Palette(dict(ThemeFakes.LIGHT))  # and off again: no one said so
        self.assertEqual(ak.theme_tick(), [owner], "the tick notices it")
        self.assertEqual(ak.ink_of(label.pixmap), (0, 0, 0), "back in black")
        self.assertEqual(owner.calls, ["log", "tool", "log", "tool"])

    def test_the_hook_reaches_the_module_loaded_last(self):
        ak.hook_theme()
        hook = sys._freelab_theme_hook
        ak.hook_theme()
        self.assertIs(sys._freelab_theme_hook, hook, "once a session")
        calls = []
        stand_in = type(sys)("stand_in")
        stand_in.theme_switched = lambda dark=None: calls.append(dark) or ["followed"]
        saved = sys.modules[ak.__name__]
        sys.modules[ak.__name__] = stand_in  # (a reinstall replaced it)
        try:
            self.assertEqual(hook(False), ["followed"])
        finally:
            sys.modules[ak.__name__] = saved
        self.assertEqual(calls, [False])

    def test_a_log_is_written_again_in_the_new_colors(self):
        fakes = ThemeFakes

        class View(object):
            def __init__(self):
                self.palette = fakes.Palette(dict(fakes.LIGHT))
                self.html = None

            def setHtml(self, html):
                self.html = html

            def verticalScrollBar(self):
                raise AttributeError("no bar")

        log = ak.Log.__new__(ak.Log)
        log.view, log.entries, log.lines, log.source, log.line = View(), [], [], None, 12
        log.add(u"Done.", "done")
        log.add(u"Read.")
        light = ak.LOG_COLORS["done"][1]
        self.assertIn(u"#%02x%02x%02x" % light, log.view.html)
        log.view.palette = fakes.Palette(dict(fakes.DARK))
        log.restyle()
        dark = ak.LOG_COLORS["done"][0]
        self.assertIn(u"#%02x%02x%02x" % dark, log.view.html)
        self.assertNotIn(u"#%02x%02x%02x" % light, log.view.html)
        self.assertEqual(len(log.entries), 2, "every line, newest first")
        self.assertTrue(log.entries[0].endswith(u"Read."))


class TableLayoutTests(unittest.TestCase):
    """FreeLab's one table layout (owner, 2026-11-15: Auto Spacing's list left half its window empty, with
    gray ticks; Kerning Classes' and Font Compare's headers had stray separators, their rows no room;
    the grids were to be faint, at 50 % opacity)."""

    class Header(object):
        def __init__(self):
            self.calls, self.default, self.slots = [], None, {}

        def setStretchLastSection(self, on):
            self.calls.append(("last", on))

        def setSectionResizeMode(self, column, mode):
            self.calls.append(("mode", column, mode))

        def setDefaultAlignment(self, alignment):
            self.default = alignment

        def connect(self, signal, slot):
            self.slots.setdefault(signal, []).append(slot)

    class HeaderItem(object):
        def __init__(self):
            self.aligned = {}

        def setTextAlignment(self, column, alignment):
            self.aligned[column] = alignment

    class View(object):
        columnCount = 4

        def __init__(self, palette, kind="QTreeView", sheet=u""):
            self.props, self.sheets, self.kind = {}, [], kind
            self.palette, self.styleSheet = palette, sheet
            self.head, self.head_item, self.resized = TableLayoutTests.Header(), TableLayoutTests.HeaderItem(), []
            self.contents = [40, 120, 50, 60]  # (each column's width for its contents)
            self.widths = [100, 100, 100, 100]
            self.port = type("Port", (object,), {"width": 600, "filters": []})()
            self.port.installEventFilter = self.port.filters.append

        def setProperty(self, name, value):
            self.props[name] = value

        def property(self, name):
            return self.props.get(name)

        def setStyleSheet(self, sheet):
            self.sheets.append(sheet)
            self.styleSheet = sheet

        def inherits(self, kind):
            return kind == self.kind or (kind == "QTreeWidget" and self.kind == "QTreeView")

        def header(self):
            if self.kind != "QTreeView":
                raise AttributeError("header")
            return self.head

        def horizontalHeader(self):
            return self.head

        def headerItem(self):
            return self.head_item

        def resizeColumnToContents(self, column):
            self.resized.append(column)
            self.widths[column] = self.contents[column]

        def columnWidth(self, column):
            return self.widths[column]

        def setColumnWidth(self, column, width):
            self.widths[column] = width

        def isColumnHidden(self, column):
            return False

        def viewport(self):
            return self.port

        def parentWidget(self):
            return None

        def style(self):
            class Style(object):
                @staticmethod
                def pixelMetric(metric):
                    return 14  # (Fusion's box)
            return Style()

    def setUp(self):
        fakes = ThemeFakes

        class Gui(object):
            QPalette = fakes.Palette

            class QStyle(object):
                PM_IndicatorWidth = 1

            class QHeaderView(object):
                Stretch = "Stretch"

        class Core(object):
            class Qt(object):
                AlignRight, AlignVCenter = 2, 128

            class QDir(object):
                @staticmethod
                def tempPath():
                    return u""  # (no folder: the check mark is left out, the box filled)

        for role in ("Text", "Base", "Highlight", "HighlightedText"):
            setattr(fakes.Palette, role, role)
        old = ak._qt
        ak._qt = lambda: (Core, Gui)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        self.light = fakes.Palette(dict(fakes.LIGHT))
        self.dark = fakes.Palette(dict(fakes.DARK))

    def test_a_list_takes_the_layout_in_its_palettes_colors(self):
        view = self.View(self.light)
        self.assertIs(ak.table_layout(view), view)
        self.assertTrue(view.props[ak.LEAVE_ALONE_PROP], "dark mode leaves it alone: mapped, its header and grid came out light")
        self.assertTrue(ak.is_table(view))
        sheet = view.styleSheet
        self.assertEqual(view.sheets[0], u"", "cleared first: polished again in the palette of now")
        self.assertIn(u"border-right: 1px solid rgba(127, 127, 127, 128)", sheet,
                      "grid lines halfway between the text and the ground, at half strength")
        self.assertIn(u"QTreeView::item { padding: %dpx %dpx;" % ak.TABLE_PADDING, sheet, "room around each cell's text")
        self.assertIn(u"QTreeView::item:selected { background: rgb(0, 120, 215); color: rgb(255, 255, 255); }", sheet)
        self.assertIn(u"QTreeView::indicator { width: 12px; height: 12px;", sheet,
                      "the style's 14-pixel box, its frame inside it (a wider one cut the cell's text)")
        self.assertIn(u"QTreeView::indicator:checked { border: 1px solid rgb(0, 120, 215); background: rgb(0, 120, 215);",
                      sheet, "checked: filled with the selection's color")
        self.assertEqual(view.head.calls, [("last", False)],
                         "no stretch column named: the columns share the width (share_columns), not Qt's last one")

    def test_no_focus_rectangle_in_a_clicked_cell(self):
        # (owner's report 114: a faint rectangle in the cell clicked, in every list: the style's focus frame
        # around the current column's cell, which serves nothing where whole rows are selected)
        for kind in ("QTreeView", "QTableView", "QListView"):
            view = self.View(self.light, kind=kind)
            ak.table_layout(view)
            self.assertIn(u"%s { outline: 0; }" % kind, view.styleSheet, kind)
            ak.style_table(view)  # (a dark mode switch writes it again)
            self.assertEqual(view.styleSheet.count(u"outline: 0;"), 1)

    def test_headers_are_centered(self):
        # (owner's report 141: the numbers' headers sat at the right, the names' at the left)
        centered = 0x4 | 0x80
        view = self.View(self.light)
        ak.table_layout(view, stretch=1, numbers=(2, 3))
        self.assertEqual(view.head.default, centered, "the header's own default")
        self.assertEqual(view.head_item.aligned, dict((column, centered) for column in range(4)), "every column's")
        view.head_item.aligned.clear()
        ak.fit_columns(view, (2, 3))
        self.assertEqual(view.head_item.aligned, dict((column, centered) for column in range(4)), "after a fit too")
        child = self.Row([u"A V", u"-60", u"-80"])
        rows = [self.Row([u"group"], children=[child])]
        listed = self.rows_view(rows)
        heads = {}
        listed.headerItem = lambda: type("Head", (), {"setTextAlignment": lambda h, c, a: heads.update({c: a}),
                                                      "text": lambda h, c: u""})()
        ak.align_numbers(listed, (1, 2))
        self.assertEqual(child.aligned, {1: 130, 2: 130}, "the numbers' cells right-aligned")
        self.assertEqual(heads, {1: centered, 2: centered}, "their headers centered")
        import freelab_kerning_check as kc
        with io.open(kc.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            self.assertNotIn(u"header.setTextAlignment", handle.read(), "Kerning Check's own right-aligned headers gone")

    def test_a_switch_writes_it_again_and_keeps_what_a_tool_added(self):
        view = self.View(self.light)
        ak.table_layout(view)
        view.styleSheet += u" QTreeView::branch { image: none; }"  # (Font Check's branch arrows, added after)
        view.palette = self.dark
        ak.style_table(view)
        sheet = view.styleSheet
        self.assertEqual(sheet.count(ak.TABLE_SHEET_MARK), 1, "the old rules replaced, not added to")
        self.assertIn(u"rgba(125, 125, 125, 128)", sheet, "the grid in the dark palette's half")
        self.assertIn(u"background: rgb(61, 111, 184)", sheet)
        self.assertNotIn(u"rgb(0, 120, 215)", sheet, "nothing of the light palette left")
        self.assertTrue(sheet.endswith(u"QTreeView::branch { image: none; }"), "the tool's own rules kept, after")
        older = self.View(self.light, sheet=u"QTreeView::item { color: gray; }")
        ak.table_layout(older)
        ak.style_table(older)
        self.assertEqual(older.styleSheet.split(ak.TABLE_SHEET_END)[1].strip(), u"QTreeView::item { color: gray; }",
                         "a sheet the tool set before stays its own, once")

    def test_the_stretch_column_takes_the_rest_never_less_than_its_contents(self):
        # (Qt's Stretch mode shrank Auto Kerning's pair pictures in a narrow window, and the column could
        # not be dragged: the reviewer, 2026-11-15)
        view = self.View(self.light)
        ak.table_layout(view, stretch=1, numbers=(2, 3))
        self.assertEqual(view.head.calls, [("last", False)], "no column in Qt's Stretch mode: all can be dragged")
        ak.fit_columns(view, (2, 3))
        self.assertEqual(view.resized, [0, 1, 2, 3], "every column sized to its contents")
        self.assertEqual(view.widths, [40, 450, 50, 60], "the names given the rest (Auto Spacing's list now fills)")
        self.assertNotIn("mode", [call[0] for call in view.head.calls])
        view.port.width = 200  # a narrow window
        ak.stretch_column(view)
        self.assertEqual(view.widths[1], 120, "its spare room taken first, then never narrower than its contents")
        self.assertEqual(sum(view.widths), 200, "the others give way (owner, 2026-11-16): no sideways scrolling")
        view.port.width = 800
        ak.stretch_column(view)
        self.assertEqual(view.widths, [40, 650, 50, 60], "the others whole again first, then the rest to it")
        plain = self.View(self.light)
        ak.table_layout(plain)
        ak.fit_columns(plain)
        self.assertEqual(sum(plain.widths), 600, "none named: every column takes its share, no gap at the right")
        self.assertEqual(plain.widths, [89, 267, 111, 133], "in proportion to its width")

    class Timer(object):
        """A QTimer as the watches use it: its slots run by fire(), its starts counted."""
        made = []

        def __init__(self, parent=None):
            self.parent, self.slots, self.started, self.single = parent, [], 0, None
            TableLayoutTests.Timer.made.append(self)

        def setSingleShot(self, on):
            self.single = on

        def setInterval(self, ms):
            self.interval = ms

        def connect(self, signal, slot):
            self.slots.append(slot)

        def start(self):
            self.started += 1

        def fire(self):
            for slot in self.slots:
                slot()

    def timers(self):
        TableLayoutTests.Timer.made = []
        ak._qt()[0].QTimer = TableLayoutTests.Timer
        saved = getattr(sys, "_freelab_table_fills", None)
        self.addCleanup(lambda: setattr(sys, "_freelab_table_fills", saved))
        return TableLayoutTests.Timer.made

    def test_a_resize_of_the_list_gives_the_room_again_on_the_next_turn(self):
        made = self.timers()
        view = self.View(self.light)
        ak.table_layout(view, stretch=1)
        ak.fit_columns(view)
        self.assertEqual(len(made), 1)
        self.assertIs(made[0].parent, view, "parented to the list: Qt deletes it with it")
        self.assertEqual(view.port.filters, made, "on the viewport")
        self.assertIs(sys._freelab_table_fills[-1], made[0], "held: PythonQt drops an override no one holds")
        view.port.width = 700

        class Event(object):
            @staticmethod
            def type():
                return ak.RESIZE_EVENT
        self.assertFalse(made[0].eventFilter(view.port, Event()), "the event goes on")
        self.assertEqual(view.widths[1], 450, "nothing changed inside Qt's resizing (it re-enters the layout)")
        self.assertEqual((made[0].started, made[0].single, made[0].interval), (1, True, 0), "a turn of the loop later")
        made[0].fire()
        self.assertEqual(view.widths[1], 550)
        ak.watch_stretch(view)
        self.assertEqual(len(made), 1, "watched once")

    def test_a_window_following_a_switch_writes_its_tables_again(self):
        view = self.View(self.light)
        ak.table_layout(view)

        class Dialog(object):
            def findChildren(self, kind):
                return []

            def isAncestorOf(self, widget):
                return True

        class App(object):
            @staticmethod
            def allWidgets():
                return [view]

        gui = ak._qt()[1]
        gui.QDialog = "QDialog"
        gui.QApplication = type("QApplication", (object,), {"instance": staticmethod(lambda: App())})

        class Owner(object):
            dialog = Dialog()
        view.palette = self.dark
        done = ak.retheme_window(Owner(), {})
        self.assertEqual(done["tables"], 1)
        self.assertIn(u"background: rgb(61, 111, 184)", view.styleSheet, "in the new palette's selection color")

    def test_colors_are_read_from_the_active_group(self):
        # (live, 2026-11-16: a window behind another at a switch got gray ticks and a gray selection, its
        # Inactive group's, which stayed once it was activated)
        class Palette(ThemeFakes.Palette):
            def color(self, *args):
                if len(args) == 1 or args[0] != ThemeFakes.Palette.Active:
                    return ThemeFakes.Color(240, 240, 240)  # (the Inactive selection of the Windows style)
                return ThemeFakes.Palette.color(self, *args)
        view = self.View(Palette(dict(ThemeFakes.LIGHT)))
        ak.table_layout(view)
        self.assertIn(u"QTreeView::item:selected { background: rgb(0, 120, 215);", view.styleSheet)
        self.assertNotIn(u"240", view.styleSheet)

    class Font(object):
        def __init__(self, bold=False):
            self.bold = bold

        def key(self):
            return "bold" if self.bold else "plain"

    class Icon(object):
        def __init__(self, null):
            self.null = null

        def isNull(self):
            return self.null

    class Row(object):
        def __init__(self, texts, children=(), checked=False, icon=False, bold=False, spanned=False):
            self.texts, self.children, self.checked = list(texts), list(children), checked
            self.icon_on, self.bold, self.spanned = icon, bold, spanned
            self.aligned = {}

        def text(self, column):
            return self.texts[column] if column < len(self.texts) else u""

        def font(self, column):
            return TableLayoutTests.Font(self.bold)

        def icon(self, column):
            return TableLayoutTests.Icon(not (self.icon_on and column == 0))

        def data(self, column, role):
            return 2 if self.checked and column == 0 and role == "check" else None

        def isFirstColumnSpanned(self):
            return self.spanned

        def childCount(self):
            return len(self.children)

        def child(self, index):
            return self.children[index]

        def setTextAlignment(self, column, alignment):
            self.aligned[column] = alignment

    def rows_view(self, rows):
        case = self

        class Metrics(object):
            def __init__(self, font):
                self.font = font

            def width(self, text):
                return len(text) * (8 if self.font.bold else 7)

        gui, core = ak._qt()[1], ak._qt()[0]
        gui.QFontMetrics = Metrics
        core.Qt.CheckStateRole = "check"

        class Header(object):
            font = TableLayoutTests.Font()

        class View(case.View):
            columnCount, indentation, rootIsDecorated = 3, 20, True
            iconSize = type("Size", (object,), {"width": lambda self: 32})()

            def topLevelItemCount(self):
                return len(rows)

            def topLevelItem(self, index):
                return rows[index]

            def header(self):
                return Header()

            def headerItem(self):
                return TableLayoutTests.Row([u"Pair", u"Glyphs", u"Set by"])

        view = View(self.light)
        view.widths = [0, 0, 0]
        return view

    def test_columns_fit_every_row_closed_groups_too(self):
        # (live, 2026-11-16: Kerning Check's names cut to "Lc..." once a group was opened; CJK Vertical's
        # metrics' labels cut at the end of a long list; Font Check's "+N" 6 pixels wider after a round trip)
        long_child = self.Row([u"", u"Lcaron quotedbl", u"class LT"], checked=True, icon=True)
        group = self.Row([u"L (23 pairs)"], children=[long_child], spanned=True, bold=True)
        rows = [group, self.Row([u"Advance height", u"", u"none on 3,884 layers"], checked=True)]
        view = self.rows_view(rows)
        widths = ak.fit_rows(view)
        pad = 2 * ak.TABLE_PADDING[1] + 2 * ak.TEXT_MARGIN + 1
        check = ak.CHECK_SIZE + 2 + ak.ICON_GAP
        self.assertEqual(widths[1], len(u"Lcaron quotedbl") * 7 + pad, "a closed group's row measured")
        self.assertEqual(widths[0], max(len(u"Advance height") * 7 + check + 20,  # (indented once: root decorated)
                                        0 + 32 + ak.ICON_GAP + check + 40) + pad,
                         "a child's picture, check box, and indentation; the spanned heading counts for none")
        self.assertEqual(widths[2], len(u"none on 3,884 layers") * 7 + pad)
        view.port.width = sum(widths.values())  # (a list as wide as its columns: nothing shared out)
        ak.fit_rows(view)
        self.assertEqual(view.widths, [widths[0], widths[1], widths[2]])
        self.assertEqual(ak.fit_rows(view), widths, "the same every time: fonts and fixed margins alone")
        capped = ak.fit_rows(view, (1,), most=60)
        self.assertEqual(capped[1], 60, "a long glyph list capped (Kerning Classes ran 1,664 pixels wide)")
        ak.fit_rows(view, (0, 1, 2), most=[None, 50, None])
        kept = json.loads(view.props[ak.TABLE_WANTS_PROP])
        self.assertEqual(kept["fits"], [widths[0], 50, widths[2]], "None: as measured")
        self.assertEqual(kept["wants"], [widths[0], widths[1], widths[2]], "what each wants: its whole content")
        self.assertEqual(view.widths[1], widths[1], "the room the cap left given back to the list it cut")

    def test_a_bold_count_fitted_stays_whole_once_the_list_is_shared_out(self):
        # (live, 2026-11-17: Font Check's high-value list showed "+..." for its bold "+N" counts, its third
        # column with no header text, beside a long list of glyphs, in a narrow list)
        row = self.Row([u"Latin", u"a" * 60, u"+12"])
        row.font = lambda column: TableLayoutTests.Font(column == 2)  # (the count in bold)
        view = self.rows_view([row])
        view.headerItem = lambda: TableLayoutTests.Row([u"Pair", u"Glyphs", u""])
        view.port.width = 200
        widths = ak.fit_rows(view, (0, 1, 2))
        pad = 2 * ak.TABLE_PADDING[1] + 2 * ak.TEXT_MARGIN + 1
        self.assertEqual(widths[2], 3 * 8 + pad, "measured in bold")
        self.assertEqual(view.widths[2], widths[2], "whole after sharing: the long glyph list gave the room")
        self.assertEqual(sum(view.widths), 200)

    def test_a_row_is_measured_in_the_font_qt_draws_it_in(self):
        # (live, 2026-11-16: Font Check's "+N" column 35 pixels on opening, 39 after a dark mode round
        # trip: its bold font was copied from the list before the window was shown, at the size of then)
        class SizedFont(object):
            def __init__(self, size, bold=False, sized=True):
                self.size, self.bold_on, self.sized = size, bold, sized

            def key(self):
                return "%s-%s" % (self.size, self.bold_on)

            def resolve(self, other):  # (never called: its overloads are not called from PythonQt)
                raise AssertionError("QFont.resolve called")

            def bold(self):
                return self.bold_on

            def italic(self):
                return False

        class QFont(SizedFont):  # (the list's font copied, given the row's weight)
            def __init__(self, other):
                SizedFont.__init__(self, other.size)

            def setBold(self, on):
                self.bold_on = on

            def setItalic(self, on):
                pass
        ak._qt()[1].QFont = QFont
        rows = [self.Row([u"", u"", u"+1"])]
        rows[0].font = lambda column: SizedFont(8, bold=True, sized=False)  # (only its weight set)
        view = self.rows_view(rows)

        class Metrics(object):
            def __init__(self, font):
                self.font = font

            def width(self, text):
                return len(text) * getattr(self.font, "size", 7)
        ak._qt()[1].QFontMetrics = Metrics
        view.headerItem = lambda: TableLayoutTests.Row([u"", u"", u""])  # (as Font Check's "+N" column: no header text)
        view.font = SizedFont(10)  # (the list's font once its window is shown)
        pad = 2 * ak.TABLE_PADDING[1] + 2 * ak.TEXT_MARGIN + 1
        self.assertEqual(ak.fit_rows(view, (2,))[2], 2 * 10 + pad, "the list's size, as Qt draws the row")
        view.font = SizedFont(12)
        self.assertEqual(ak.fit_rows(view, (2,))[2], 2 * 12 + pad, "and the list's size of now, every time")

    def test_a_list_is_fitted_again_once_shown_without_an_event_filter(self):
        # (2026-11-16: a filter on the list's font and style changes, run while Qt polished the window being
        # shown, came with two crashes of FontLab on opening Kerning Check)
        made = self.timers()
        filters = []
        rows = [self.Row([u"Advance height", u"x", u"none on 3,884 layers"])]
        view = self.rows_view(rows)
        view.installEventFilter = filters.append
        view.visible = False  # (filled before its window is shown)
        first = ak.fit_rows(view, (0, 2), most=[None, None, 100])
        self.assertEqual(json.loads(view.props[ak.TABLE_FIT_PROP]), {"columns": [0, 2], "most": [None, None, 100]})
        self.assertEqual(filters, [], "no event filter on the list")
        self.assertEqual(len(made), 1, "a plain timer")
        timer = made[0]
        self.assertIs(timer.parent, view, "parented to the list")
        self.assertIn(timer, sys._freelab_table_fills, "held")
        self.assertEqual((timer.started, timer.single, timer.interval), (1, True, ak.FIT_SETTLE_MS))
        view.widths = [5, 5, 5]
        rows[0].texts[0] = u"Advance height (font units)"  # (its window's font: the same rows measure wider)
        timer.fire()
        self.assertEqual(view.widths, [5, 5, 5], "not shown yet: looked at again later")
        self.assertEqual(timer.started, 2)
        view.visible = True
        timer.fire()
        self.assertGreater(view.widths[0], first[0], "shown: fitted again")
        fits = json.loads(view.props[ak.TABLE_WANTS_PROP])["fits"]
        self.assertEqual(fits[2], 100, "with the same widths at most")
        self.assertEqual(fits[1], None, "and the same columns only")
        self.assertEqual(sum(view.widths), view.port.width, "then the width shared out")
        self.assertEqual(len(made), 1, "a refit sets no timer of its own")
        self.assertNotIn(timer, sys._freelab_table_fills, "done: let go")
        hidden = self.rows_view([self.Row([u"a"])])
        hidden.visible = False
        ak.fit_rows(hidden, (0,))
        for _ in range(ak.FIT_SETTLE_TRIES + 5):
            made[-1].fire()
        self.assertEqual(made[-1].started, ak.FIT_SETTLE_TRIES, "never shown: given up")
        self.assertFalse(ak.refit(self.rows_view([])), "a list never fitted: nothing to do")

    def test_numbers_align_right_in_every_row(self):
        child = self.Row([u"A V", u"-60", u"-80"])
        rows = [self.Row([u"group"], children=[child])]
        view = self.rows_view(rows)
        ak.align_numbers(view, (1, 2))
        self.assertEqual(child.aligned, {1: 130, 2: 130}, "a closed group's rows too")
        self.assertEqual(rows[0].aligned, {1: 130, 2: 130})

    def test_a_list_widens_to_its_longest_row(self):
        class List(object):
            frameWidth, minimum = 1, None

            def sizeHintForColumn(self, column):
                return 97

            def verticalScrollBar(self):
                return type("Bar", (object,), {"sizeHint": lambda self: type("S", (object,), {"width": lambda s: 12})()})()

            def setMinimumWidth(self, width):
                self.minimum = width
        pages = List()
        self.assertEqual(ak.fit_list_width(pages), 97 + 2 + 12 + 2, "Proof's pages: no sideways scrolling for 2 pixels")
        self.assertEqual(pages.minimum, 113)
        self.assertEqual(ak.fit_list_width(pages, most=80), 80)

    def test_tables_and_lists_without_grid(self):
        table = self.View(self.light, kind="QTableView")
        ak.table_layout(table)
        self.assertIn(u"QTableView { gridline-color: rgba(127, 127, 127, 128); }", table.styleSheet)
        self.assertIn(u"QTableView::indicator", table.styleSheet)
        names = self.View(self.light, kind="QListView")
        ak.table_layout(names, grid=False)
        self.assertIn(u"QListView::item { padding: %dpx %dpx; }" % ak.TABLE_PADDING, names.styleSheet, "no lines")
        self.assertNotIn(u"border-right", names.styleSheet)
        ak.style_table(names)
        self.assertNotIn(u"border-right", names.styleSheet, "still none after a switch")

    def test_every_tools_list_takes_the_layout(self):
        made = re.compile(u"QtGui\\.Q(?:TreeWidget|ListWidget|TableWidget)\\(\\)")
        exempt = {u"freelab_font_check.py": 1}  # (its clipped glyphs: a strip of tiles, not rows)
        root = os.path.join(HERE, os.pardir)
        checked = 0
        for folder in ("kerning", "spacing", "compose", "features", "cjk", "compare", "checks", "proof"):
            for name in os.listdir(os.path.join(root, folder)):
                if not name.endswith(u".py"):
                    continue
                with io.open(os.path.join(root, folder, name), encoding="utf-8") as handle:
                    source = handle.read()
                lists = len(made.findall(source)) - exempt.get(name, 0)
                laid = source.count(u"table_layout(") - (source.count(u"def table_layout(") * 2)
                checked += lists
                self.assertGreaterEqual(laid, lists, "%s: a list made without FreeLab's table layout" % name)
                self.assertNotIn(u"grid_lines(", source.replace(u"def grid_lines(", u""), name)
        self.assertGreater(checked, 15)


class ColumnShareTests(unittest.TestCase):
    """How a list's columns share its width (owner, 2026-11-16, report 142: a column dragged narrower left
    a gap in the list's frame; shrinking takes from the columns with spare room first, growing gives to
    the columns cut short first, then in proportion)."""

    LEASTS = [24, 24, 24, 24]

    def share(self, widths, wants, room, held=None, stretch=None, leasts=None):
        return ak.share_widths(list(widths), list(wants), list(leasts or self.LEASTS), room, held, stretch)

    def test_a_column_dragged_narrower_leaves_no_gap(self):
        new = self.share([100, 60, 100, 100], [100, 100, 100, 100], 400, held=1)
        self.assertEqual(sum(new), 400, "the frame filled")
        self.assertEqual(new[1], 60, "the column dragged keeps the width given it")
        self.assertEqual(new, [114, 60, 113, 113], "the others share the room in proportion")

    def test_a_column_dragged_wider_takes_from_the_roomiest_first(self):
        new = self.share([150, 180, 100, 200], [100, 100, 100, 120], 550, held=1)
        self.assertEqual(new, [125, 180, 100, 145], "the roomiest (80 spare) down to the next (50), then both")
        self.assertEqual(sum(new), 550)

    def test_then_its_neighbor_then_every_column(self):
        self.assertEqual(self.share([100, 160, 100, 100], [100] * 4, 400, held=1), [100, 160, 40, 100],
                         "no spare room anywhere: its neighbor gives way, as Qt's own")
        self.assertEqual(self.share([100, 100, 100, 160], [100] * 4, 400, held=3), [100, 100, 40, 160],
                         "the last column's neighbor is the one before it")
        self.assertEqual(self.share([100, 250, 100, 100], [100] * 4, 400, held=1), [63, 250, 24, 63],
                         "the neighbor at its least: the others in proportion")
        squeezed = self.share([100, 390, 100, 100], [100] * 4, 400, held=1)
        self.assertEqual(squeezed, [24, 390, 24, 24], "nothing left above the least: the list scrolls")

    def test_a_narrower_list_takes_spare_room_first(self):
        self.assertEqual(self.share([300, 100, 100, 100], [100, 100, 60, 100], 520), [220, 100, 100, 100],
                         "the roomiest alone, while it has more spare room than the next")
        self.assertEqual(self.share([300, 100, 100, 100], [100, 100, 60, 100], 400), [120, 100, 80, 100],
                         "then both together; the columns without spare room left whole")
        self.assertEqual(self.share([100, 100, 60, 100], [100, 100, 60, 100], 300), [80, 80, 60, 80],
                         "no spare room left: the widest above its least first, levelled down together")

    def test_a_short_count_beside_a_long_list_stays_whole(self):
        # (live, 2026-11-17: Font Check's bold "+N" counts cut to "+..." in its narrow list of high-value
        # glyphs, taken in proportion beside a long list of languages)
        self.assertEqual(self.share([200, 40, 300], [200, 40, 300], 400, leasts=[24, 24, 24]), [180, 40, 180],
                         "the long ones give first; the count, much narrower, keeps its 40 pixels")
        self.assertEqual(self.share([180, 30, 180], [200, 40, 300], 450, leasts=[24, 24, 24]), [200, 40, 210],
                         "and, cut, it is shown whole first once there is room")

    def test_a_wider_list_shows_its_cut_columns_whole_first(self):
        self.assertEqual(self.share([100, 60, 80], [100, 70, 300], 260, leasts=[24] * 3), [100, 70, 90],
                         "the one lacking least made whole first, the rest to the one still cut")
        # (the owner's "under 5 % still clipped" worry: a column nearly whole is never left short for a long note)
        self.assertEqual(self.share([190, 300], [200, 1000], 520, leasts=[24, 24]), [200, 320])
        self.assertEqual(self.share([100, 100, 100], [100, 100, 100], 360, leasts=[24] * 3, stretch=1), [100, 160, 100],
                         "nothing cut: the rest to the stretch column (the pair pictures, the names)")
        self.assertEqual(self.share([100, 50, 150], [100, 50, 150], 600, leasts=[24] * 3), [200, 100, 300],
                         "none named: every column in proportion")

    def test_a_hidden_column_is_left_alone(self):
        self.assertEqual(self.share([100, None, 100], [100, 100, 100], 300, leasts=[24] * 3), [150, None, 150])

    def view(self, widths, wants, room):
        case = self

        class Port(object):
            def __init__(self):
                self.width, self.filters = room, []

            def installEventFilter(self, watch):
                self.filters.append(watch)

        class View(TableLayoutTests.View):
            columnCount = len(widths)

            def setColumnWidth(self, column, width):
                old, self.widths[column] = self.widths[column], width
                for slot in self.head.slots.get("sectionResized(int,int,int)", []):
                    slot(column, old, width)  # (Qt says so for any width set, the tool's own too)

        view = View(ThemeFakes.Palette(dict(ThemeFakes.LIGHT)))
        view.widths, view.port = list(widths), Port()
        case.made = []

        class Timer(object):
            def __init__(self, parent=None):
                self.slots, self.started = [], 0
                case.made.append(self)

            def setSingleShot(self, on):
                pass

            def setInterval(self, ms):
                pass

            def connect(self, signal, slot):
                self.slots.append(slot)

            def start(self):
                self.started += 1

            def fire(self):
                for slot in self.slots:
                    slot()

        class Core(object):
            QTimer = Timer

            class Qt(object):
                AlignRight, AlignVCenter = 2, 128

            class QDir(object):
                @staticmethod
                def tempPath():
                    return u""

        class Gui(object):
            QPalette = ThemeFakes.Palette

            class QStyle(object):
                PM_IndicatorWidth = 1

        old, saved = ak._qt, getattr(sys, "_freelab_table_fills", None)
        ak._qt = lambda: (Core, Gui)

        def restore():
            ak._qt = old
            sys._freelab_table_fills = saved
        self.addCleanup(restore)
        ak.table_layout(view)
        ak.note_wants(view, dict(enumerate(wants)))
        return view

    def test_a_drag_is_shared_out_on_the_next_turn_and_kept(self):
        view = self.view([100, 100, 100, 100], [100, 100, 100, 100], 400)
        self.assertEqual(len(view.head.slots["sectionResized(int,int,int)"]), 1, "the header's drags heard")
        watch = self.made[0]
        view.setColumnWidth(1, 60)  # the owner drags the second column narrower
        self.assertEqual(view.widths, [100, 60, 100, 100], "nothing changed inside Qt's resizing")
        self.assertEqual(watch.started, 1)
        watch.fire()
        self.assertEqual(view.widths, [114, 60, 113, 113], "the gap shared out, the dragged column as dragged")
        self.assertEqual(watch.started, 1, "its own widths are no drag")
        self.assertEqual(json.loads(view.props[ak.TABLE_WANTS_PROP])["wants"][1], 60, "what it wants from now on")
        view.port.width = 370  # the window made narrower
        ak.share_columns(view)
        self.assertEqual(view.widths, [103, 60, 103, 104], "the others' spare room taken, not the column dragged narrower")

    def test_tool_modes_and_qts_own_stretch_are_left_alone(self):
        view = self.view([100, 100], [100, 100], 400)
        view.head.sectionResizeMode = lambda column: 1  # (Font Check's Stretch columns)
        self.assertIsNone(ak.share_columns(view))
        self.assertEqual(view.widths, [100, 100])
        own = self.view([100, 100], [100, 100], 400)
        own.setProperty(ak.OWN_COLUMNS_PROP, True)  # (Font Check's right-hand lists size their own columns)
        self.assertIsNone(ak.share_columns(own))
        own.setColumnWidth(0, 60)  # a drag
        self.made[-1].fire()
        self.assertEqual(own.widths, [60, 100], "left to the tool, drags too")

    def test_a_check_button_is_judged_by_the_shown_list_of_those_equally_near(self):
        # (the Font Check agent, 2026-11-16: a QStackedWidget's hidden page, as near as the shown one,
        # grayed out Check all; and Kerning Check's bottom row lies as near to its three tabs' lists)
        class Widget(object):
            def __init__(self, parent=None, visible=True, kinds=()):
                self.parent, self.visible, self.kinds = parent, visible, kinds

            def parentWidget(self):
                return self.parent

            def window(self):
                return dialog

            def inherits(self, kind):
                return kind in self.kinds

        class Item(object):
            def flags(self):
                return 16

            def data(self, column, role):
                return 0

            def childCount(self):
                return 0

        class Tree(Widget):
            def __init__(self, parent, visible, rows):
                Widget.__init__(self, parent, visible, ("QTreeWidget",))
                self.rows = rows
                self.topLevelItemCount = len(rows)

            def topLevelItem(self, index):
                return self.rows[index]

        class Button(Widget):
            text, enabled = u"Check all", True

            def isEnabled(self):
                return self.enabled

            def setEnabled(self, on):
                self.enabled = on

        class Dialog(Widget):
            def findChildren(self, kind):
                return {"QPushButton": [button], "QAbstractItemView": [hidden, shown]}.get(kind, [])

        dialog = Dialog()
        stack = Widget(dialog)
        hidden = Tree(Widget(stack, False), False, [])  # (an empty page, not shown)
        shown = Tree(Widget(stack), True, [Item()])
        button = Button(dialog)

        class Core(object):
            class Qt(object):
                ItemIsUserCheckable, CheckStateRole = 16, 10

        old = ak._qt
        ak._qt = lambda: (Core, type("Gui", (), {"QPushButton": "QPushButton", "QAbstractItemView": "QAbstractItemView",
                                                 "QComboBox": "QComboBox"}))
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        ak.update_states(dialog)
        self.assertTrue(button.enabled, "judged by the list shown, which has rows to check")
        shown.rows, shown.topLevelItemCount = [], 0
        ak.update_states(dialog)
        self.assertFalse(button.enabled, "nothing listed in it: grayed out")

    def test_a_list_too_narrow_widens_its_window(self):
        view = self.view([100, 100], [100, 100], 150)

        class Window(object):
            visible, maximized, minimized, pos, width, height = True, False, False, (300, 100), 500, 400

            def resize(self, width, height):
                self.width, self.height = width, height

            def move(self, x, y):
                self.pos = (x, y)

        window = Window()
        owner = type("Owner", (), {"dialog": window, "opened_size": (500, 400)})()
        view.window, view.visible = lambda: window, True
        saved = ak.window_owner, ak._windows, ak.screen_area, ak._free_area
        ak.window_owner = lambda widget: owner
        ak._windows = lambda: {"size": None}
        ak.screen_area = lambda widget=None: (0, 0, 1000, 800)
        ak._free_area = lambda widget: ((0, 0, 1000, 800), (16, 39))

        def restore():
            ak.window_owner, ak._windows, ak.screen_area, ak._free_area = saved
        self.addCleanup(restore)
        self.assertEqual(ak.widen_window(view), 50, "by what its columns lack")
        self.assertEqual((window.width, window.pos), (550, (275, 100)), "around its center")
        self.assertEqual(owner.opened_size, (550, 400), "FreeLab's doing, not a size given by hand")
        view.port.width = 150
        ak.note_wants(view, {0: 900})
        self.assertEqual(ak.widen_window(view), 1000 - 40 - 16 - 550, "at most to the screen's free area")
        window.width = 700  # the owner drags its edge
        self.assertEqual(ak.widen_window(view), 0, "a size given by hand stays")
        owner.opened_size = (700, 400)
        ak._windows = lambda: {"size": (700, 400)}
        self.assertEqual(ak.widen_window(view), 0, "and so does every window's this session")

    def test_a_window_scrolls_on_a_small_screen(self):
        made = []

        class Widget(object):
            def __init__(self, *parent):
                self.props, self.parent = {}, parent[0] if parent else None
                made.append(self)

            def setProperty(self, name, value):
                self.props[name] = value

            def property(self, name):
                return self.props.get(name)

        class Layout(Widget):
            def setContentsMargins(self, *margins):
                self.margins = margins

            def addWidget(self, widget):
                self.added = widget

        class Area(Widget):
            def setWidgetResizable(self, on):
                self.resizable = on

            def setFrameShape(self, shape):
                pass

            def setWidget(self, widget):
                self.body = widget

        class Gui(object):
            QVBoxLayout, QWidget, QScrollArea = Layout, Widget, Area
            QFrame = type("QFrame", (), {"NoFrame": 0})

        old = ak._qt
        ak._qt = lambda: (None, Gui)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        dialog = Widget()
        plain = ak.window_layout(dialog, scroll=False)
        self.assertIs(plain.parent, dialog, "a screen of a usual size: laid out as before")
        layout = ak.window_layout(dialog, scroll=True)
        area = [w for w in made if isinstance(w, Area)][0]
        self.assertTrue(area.resizable)
        self.assertIs(layout.parent, area.body, "the tool's content in the scroll area")
        self.assertIs(area.body.parent, area, "parented from the start")
        self.assertTrue(area.props[ak.WINDOW_BODY_PROP] and area.body.props[ak.WINDOW_BODY_PROP])
        self.assertTrue(ak.small_screen((0, 0, 854, 440)), "480p (its taskbar taken)")
        self.assertTrue(ak.small_screen((0, 0, 1280, 680)), "720p")
        self.assertFalse(ak.small_screen((0, 0, 1920, 1040)))
        self.assertFalse(ak.small_screen(None), "no screen known: as before")
        import freelab_kerning_check as kc
        with io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(source.count(u"layout = window_layout(dialog)"), 2, "Auto Kerning's and Kerning Classes' windows")
        with io.open(kc.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            self.assertIn(u"layout = self.ak.window_layout(dialog)", handle.read(), "Kerning Check's")

    def test_the_tools_buttons_go_into_the_scrolling_content(self):
        # (live, 2026-11-17: on a small screen the tools button went beside the scroll area, into the dialog's
        # own layout, and left an empty strip 116 pixels wide at the window's right)
        class Item(object):
            def __init__(self, widget):
                self.held = widget

            def widget(self):
                return self.held

        class Layout(object):
            def __init__(self, *widgets):
                self.widgets = list(widgets)

            def count(self):
                return len(self.widgets)

            def itemAt(self, index):
                return Item(self.widgets[index])

        inner = Layout("status")
        body = type("Body", (), {"layout": lambda b: inner})()
        area = type("Area", (), {"property": lambda a, name: name == ak.WINDOW_BODY_PROP, "widget": lambda a: body})()
        scrolling = type("Dialog", (), {"layout": lambda d: Layout(area)})()
        self.assertIs(ak.content_layout(scrolling), inner, "the body's layout, inside the scroll area")
        plain_layout = Layout("status", "row")
        plain = type("Dialog", (), {"layout": lambda d: plain_layout})()
        self.assertIs(ak.content_layout(plain), plain_layout, "a usual window: its own layout")
        with io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read().split(u"def add_tools_button(")[1].split(u"\ndef ")[0]
        self.assertIn(u"layout = content_layout(dialog)", source)

    def test_a_click_on_a_scrolling_windows_background_is_beside_the_lists(self):
        class Widget(object):
            def __init__(self, parent, kinds=(), body=False):
                self.parent, self.kinds, self.body, self.mouseTracking = parent, kinds, body, False

            def parentWidget(self):
                return self.parent

            def inherits(self, kind):
                return kind in self.kinds

            def property(self, name):
                return True if name == ak.WINDOW_BODY_PROP and self.body else None

        window = Widget(None)
        area = Widget(window, ("QAbstractScrollArea",), body=True)
        port = Widget(area)
        body = Widget(port, body=True)
        label = Widget(body, ("QLabel",))
        self.assertTrue(ak.blank_press(window, label), "its scroll area is the window's own")
        self.assertFalse(ak.blank_press(window, Widget(body, ("QAbstractScrollArea",))), "a list is still no blank")

    def test_size_dialog_keeps_to_fontlabs_screen(self):
        sized = []
        dialog = type("Dialog", (), {"resize": lambda d, w, h: sized.append((w, h))})()
        saved = ak.screen_area
        self.addCleanup(lambda: setattr(ak, "screen_area", saved))
        ak.screen_area = lambda widget=None: (0, 0, 854, 440)
        ak.size_dialog(dialog)
        self.assertEqual(sized[-1], (854 - 40, 440 - 60))
        ak.screen_area = lambda widget=None: None
        ak.size_dialog(dialog)
        self.assertEqual(sized[-1], (ak.DIALOG_SIZE, ak.DIALOG_SIZE), "where Qt cannot tell: 1000 by 1000")


class CheckRowsTests(unittest.TestCase):
    """Check all, Check none, and the like say what they did, rows out of sight included (owner, report 118)."""

    class Item(object):
        def __init__(self, checked=False, parent=None, open_=True, hidden=False, tree=True):
            self.state, self.parent_item, self.open, self.hidden, self.tree = 2 if checked else 0, parent, open_, hidden, tree

        def checkState(self, *column):
            if bool(column) != self.tree:
                raise TypeError("wrong number of arguments")
            return self.state

        def setCheckState(self, *args):
            self.state = args[-1]

        def isHidden(self):
            return self.hidden

        def isExpanded(self):
            return self.open

        def parent(self):
            return self.parent_item

    def setUp(self):
        class Core(object):
            class Qt(object):
                Checked, Unchecked = 2, 0
        old = ak._qt
        ak._qt = lambda: (Core, None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        self.lines = []
        self.log = type("Log", (), {"add": lambda log, text, level="info": self.lines.append(text)})()

    def test_counts_said_with_the_rows_out_of_sight(self):
        closed = self.Item(parent=None, open_=False)
        items = [self.Item(), self.Item(checked=True), self.Item(parent=closed), self.Item(hidden=True)]
        self.assertEqual(ak.check_rows(items, True, self.log, u"Check all", u"pair"), (3, 0, 2))
        self.assertEqual(self.lines[-1], u"<i>Check all</i> ticked <b>3 pairs</b> (<b>2</b> of them hidden).")
        self.assertEqual([item.state for item in items], [2, 2, 2, 2])
        ak.check_rows(items[:1], False, self.log, u"Check none", u"glyph")
        self.assertEqual(self.lines[-1], u"<i>Check none</i> unticked <b>1 glyph</b>.")
        ak.check_rows(items[2:3], False, self.log, u"Check none", u"entry", u"entries", (u"in a closed group", u"in closed groups"))
        self.assertEqual(self.lines[-1], u"<i>Check none</i> unticked <b>1 entry</b> (in a closed group).")
        ak.check_rows(items[2:], False, self.log, u"Check none", u"pair")
        self.assertEqual(self.lines[-1], u"<i>Check none</i> unticked <b>1 pair</b> (hidden).")
        ak.check_rows(items, False, self.log, u"Check none", u"pair")
        self.assertEqual(self.lines[-1], u"<i>Check none</i> unticked <b>1 pair</b>.", "only those it changed")
        ak.check_rows(items, False, self.log, u"Check none", u"pair")
        self.assertEqual(self.lines[-1], u"<i>Check none</i> changed nothing.")

    def test_both_ways_at_once_and_list_rows(self):
        items = [self.Item(checked=True, tree=False), self.Item(tree=False), self.Item(tree=False, hidden=True)]
        wanted = [False, True, True]
        counts = ak.check_rows(items, lambda item: wanted[items.index(item)], self.log, u"Check new pairs", u"pair")
        self.assertEqual(counts, (2, 1, 1))
        self.assertEqual(self.lines[-1], u"<i>Check new pairs</i> ticked <b>2 pairs</b> and unticked <b>1</b> (<b>1</b> of them hidden).")
        hidden = [self.Item(hidden=True), self.Item(hidden=True)]
        ak.check_rows(hidden, True, self.log, u"Check all", u"glyph")
        self.assertEqual(self.lines[-1], u"<i>Check all</i> ticked <b>2 glyphs</b> (all of them hidden).")
        self.assertEqual(ak.check_rows([self.Item()], None, None), (0, 0, 0), "None: left alone, nothing said")


class HeldFilterTests(unittest.TestCase):
    """Event filters made from Python are timers here: made without a parent, one held only in a
    dictionary of parts became garbage once its tool was let go, and PythonQt deleted it at whatever
    moment Python's collector picked (the crashes of November 14 were PythonQt freeing such a wrapper)."""

    def setUp(self):
        made = self.made = []

        class Timer(object):
            def __init__(self, parent=None):
                self.owner, self.running = parent, True
                made.append(self)

            def inherits(self, name):
                return name == "QTimer"

            def metaObject(self):
                return "QTimer"

            def parent(self):
                return self.owner

            def setParent(self, parent):
                self.owner = parent

            def stop(self):
                self.running = False

        class Core(object):
            QTimer = Timer

            class Qt(object):
                ClickFocus = SizeHorCursor = ArrowCursor = PointingHandCursor = 0

        class Widget(object):
            def __init__(self):
                self.filters = []

            def installEventFilter(self, watcher):
                self.filters.append(watcher)

            def setMouseTracking(self, on):
                pass

            def setFocusPolicy(self, policy):
                pass

            def setToolTip(self, text):
                pass

            def setProperty(self, name, value):
                pass

            toolTip = u""

        self.Widget = Widget
        saved = ak._qt
        ak._qt = lambda: (Core, None)
        self.addCleanup(lambda: setattr(ak, "_qt", saved))

    def test_filters_are_made_with_the_widget_they_watch_as_parent(self):
        button, label = self.Widget(), self.Widget()
        regions = ak.ClickRegions(button, lambda key: None)
        drag = ak.PairDrag(label, lambda: 0, lambda value: None, lambda step: None, lambda: 1.0)
        self.assertIs(regions.filter.owner, button, "Qt deletes it with its widget, never PythonQt at random")
        self.assertIs(drag.filter.owner, label)

    def test_a_double_clicks_call_and_the_history_tick_are_held(self):
        """A neighbor's double-click handed QTimer.singleShot a lambda nothing held, and watch_history's tick was
        held by nothing but its connection (adversarial review 9): PythonQt drops a slot no Python object holds."""
        import gc
        import weakref
        Timer, queue, clicked = ak._qt()[0].QTimer, [], []
        Timer.singleShot = staticmethod(lambda ms, slot: queue.append(weakref.ref(slot)))

        class Event(object):
            def __init__(self, kind):
                self.kind = kind

            def type(self):
                return self.kind

        widget = self.Widget()
        regions = ak.ClickRegions(widget, clicked.append)
        regions.hit = lambda event: "neighbor"
        for kind in (2, 3):  # (a single click: taken, nothing called)
            self.assertTrue(regions.filter.eventFilter(widget, Event(kind)))
        self.assertEqual(queue, [])
        self.assertTrue(regions.filter.eventFilter(widget, Event(4)))
        gc.collect()
        (slot,) = queue
        self.assertIsNotNone(slot(), "held until it runs")
        slot()()
        self.assertEqual(clicked, ["neighbor"])
        self.assertEqual(regions.pending, [], "and let go once it ran")
        # The History's watch
        connected = []
        Timer.setInterval = Timer.start = lambda self, *args: None
        Timer.connect = lambda self, signal, slot: connected.append(weakref.ref(slot))

        class Tool(object):
            dialog = None

        tool = Tool()
        timer = ak.watch_history(tool)
        gc.collect()
        self.assertIsNotNone(connected[0](), "its tick held with the tool")
        self.assertIs(connected[0](), tool.history_tick)
        del timer

    def test_timers_anywhere_a_tool_holds_them_are_found(self):
        class Tool(object):
            pass

        class Page(object):
            pass

        tool, made = Tool(), self.made
        tool.neighbors = dict((key, ak.ClickRegions(self.Widget(), lambda k: None)) for key in ("before", "after"))
        tool.spacing_neighbors = [ak.ClickRegions(self.Widget(), lambda k: None)]
        tool.class_dialog = Page()  # (Auto Kerning's classes dialog, holding its drag, and its owner back)
        tool.class_dialog.adjusting = ak.PairDrag(self.Widget(), lambda: 0, lambda v: None, lambda s: None, lambda: 1.0)
        tool.class_dialog.owner = tool
        tool.shared = type(sys)("shared")  # (a module: its timers serve every window)
        tool.shared.watch = made[0].__class__()
        tool.text, tool.numbers = u"a" * 10, list(range(1000))
        found = ak._held_timers(tool)
        self.assertEqual(len(found), 4, "two in a dictionary, one in a list, one in a part of a part")
        self.assertNotIn(tool.shared.watch, found)


class MainCodeTests(unittest.TestCase):
    def test_a_glyph_fontlab_gives_a_radical_first_is_read_as_its_ideograph(self):
        # FontLab's unicode gives the Kangxi radical U+2F47 first for a glyph also encoded at U+65E5 (IBM Plex
        # Sans JP): read as the radical, it was a symbol (category So), not Han
        class Fg(object):
            unicodes, unicode = [0x2F47, 0x65E5], 0x2F47

        class Glyph(object):
            fgGlyph = Fg()

        class Package(object):
            def findName(self, name):
                return Glyph() if name == u"uni65E5" else None

        self.assertEqual(ak.main_code(Fg()), 0x65E5)
        self.assertEqual(ak.direction_char(Package(), u"uni65E5"), u"\u65e5")
        import freelab_kerning_check as check
        self.assertEqual(check.glyph_text(Package(), u"uni65E5"), u"\u65e5")


class FontLabWidgetTests(unittest.TestCase):
    def test_fontlabs_widgets_are_looked_for_once_not_at_every_read(self):
        # Every widget wrapped at each compile and each of its Output reads (the walk November 14's crashes
        # came at the end of, in tab docking): the widget found is kept while it is there
        case, walks = self, []

        class Output(object):
            objectName, deleted, shown, text = "textOutput", False, True, u"compiled"

            def inherits(self, name):
                return name == "QTextEdit"

            def metaObject(self):
                if self.deleted:
                    raise ValueError("destroyed")
                return "QTextEdit"

            def isVisible(self):
                return self.shown

            def toPlainText(self):
                return self.text

        case.output = Output()
        hidden = Output()  # (FontLab has two of that name: the first hidden and empty, live)
        hidden.shown, hidden.text = False, u""

        class App(object):
            def allWidgets(self):
                walks.append(1)
                return [hidden, case.output]

        class Gui(object):
            class QApplication(object):
                @staticmethod
                def instance():
                    return App()

        saved, held = ak._qt, getattr(sys, "_freelab_found", None)
        ak._qt, sys._freelab_found = (lambda: (None, Gui)), None

        def restore():
            ak._qt, sys._freelab_found = saved, held
        self.addCleanup(restore)
        self.assertEqual([ak.output_text() for _ in range(3)], [u"compiled"] * 3)
        self.assertEqual(len(walks), 1, "walked once")
        case.output.deleted = True  # (FontLab rebuilt its panel)
        case.output = Output()
        self.assertEqual(ak.output_text(), u"compiled")
        self.assertEqual(len(walks), 2, "walked again once the one found is gone")
        case.output.shown = False  # (the panel closed: both hidden)
        self.assertEqual(ak.output_text(), u"compiled", "the one that holds text, not the empty first")
        case.output.text = u""
        self.assertEqual(ak.output_text(), u"", "with none holding text, the first")

    def test_a_compiles_output_is_read_before_and_after_from_the_same_text_box(self):
        reads, timers, logged = [], [], []

        class View(object):
            def __init__(self, texts):
                self.texts = texts

            def toPlainText(self):
                reads.append(self)
                return self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]

        view = View([u"old", u"old\n[E] bad rule", u"old\n[E] bad rule"])

        class Core(object):
            class QTimer(object):
                @staticmethod
                def singleShot(ms, slot):
                    timers.append(slot)

        class Box(object):
            checked = True

        class Log(object):
            def add(self, text, level="info"):
                logged.append((level, text))

        saved = (ak._qt, ak.output_view, ak.compile_features)
        ak._qt, ak.output_view, ak.compile_features = (lambda: (Core, None)), (lambda: view), (lambda: True)
        self.addCleanup(lambda: setattr(ak, "_qt", saved[0]) or setattr(ak, "output_view", saved[1])
                        or setattr(ak, "compile_features", saved[2]))
        ak.compiled_note(Box(), Log())
        while timers:
            timers.pop(0)()
        self.assertTrue(all(read is view for read in reads), "one text box, before and after")
        self.assertEqual(logged[-1][0], "error")
        self.assertIn(u"bad rule", logged[-1][1])

    def test_a_clean_compile_says_fontlab_reported_no_errors(self):
        # The log said "FontLab's Output panel showed nothing from the compiler: see the Features panel for any
        # error" after a write with vrt2. FontLab clears the panel at each compile (the owner), so an empty
        # panel after one means no message at all
        timers, logged = [], []

        class View(object):
            def __init__(self, texts):
                self.texts = texts

            def toPlainText(self):
                return self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]

        class Core(object):
            class QTimer(object):
                @staticmethod
                def singleShot(ms, slot):
                    timers.append(slot)

        class Box(object):
            checked = True

        class Log(object):
            def add(self, text, level="info"):
                logged.append((level, text))

        saved = (ak._qt, ak.output_view, ak.compile_features)
        self.addCleanup(lambda: setattr(ak, "_qt", saved[0]) or setattr(ak, "output_view", saved[1])
                        or setattr(ak, "compile_features", saved[2]))
        ak._qt, ak.compile_features = (lambda: (Core, None)), (lambda: True)
        cases = (([u"", u""], ("info", u"Compiled: FontLab reported no errors.")),
                 ([u"[E] an old error", u""], ("info", u"Compiled: FontLab reported no errors."), "cleared"),
                 ([u"", u"[W] unused class @a"],
                  ("info", u"Compiled: FontLab reported no errors, and a warning: [W] unused class @a")),
                 # Review: a panel that never changed is not this compile's: neither its old error, nor "no
                 # errors" before the compiler has had its say
                 ([u"[W] unused class @a", u"[W] unused class @a"], ("info", ak.COMPILE_UNCHANGED),
                  "the old text, never changed"),
                 ([u"[E] bad rule", u"[E] bad rule"], ("info", ak.COMPILE_UNCHANGED), "not the old error again"),
                 ([u"[E] old", u"[E] old", u"[E] old", u"[E] old", u""],
                  ("info", u"Compiled: FontLab reported no errors."), "read on while it has not changed"),
                 ([u"[N] notes", u"[N] notes\n[E] bad rule"], ("error", u"The features did not compile: [E] bad rule"),
                  "kept and added to"),
                 ([u"", u"", u"[F] stopped", u"[F] stopped"], ("error", u"The features did not compile: [F] stopped"),
                  "read until it stops changing"))
        for case in cases:
            texts, wanted = case[0], case[1]
            view = View(list(texts))
            ak.output_view = lambda: view
            del logged[:]
            note = ak.compiled_note(Box(), Log())
            while timers:
                timers.pop(0)()
            self.assertEqual(logged, [wanted], case[2:] or texts)
        self.assertEqual(note, u" Compiled: what FontLab's compiler reports follows in this log.")
        counted, view = [], View([u"[E] old"])
        plain = view.toPlainText
        view.toPlainText = lambda: counted.append(1) or plain()
        ak.output_view = lambda: view
        ak.compiled_note(Box(), Log())
        while timers:
            timers.pop(0)()
        self.assertEqual(len(counted), 1 + ak.COMPILE_READS_MAX, "read before, then to the most while unchanged")
        self.assertEqual(ak.compile_report(u"[W] a\n[W] b\n")[0], u"Compiled: FontLab reported no errors, and 2 warnings: [W] a [W] b")
        for text in (logged[-1][1], ak.compile_report(u"")[0]):
            self.assertNotIn(u"showed nothing", text)


class HelperModuleTests(unittest.TestCase):
    """A helper module is installed under another extension, so FontLab's Scripts menu does not list it."""

    def test_a_helper_is_found_under_its_installed_extension(self):
        import shutil
        import tempfile
        folder = tempfile.mkdtemp(prefix="freelab-helper-")
        self.addCleanup(lambda: shutil.rmtree(folder, True))
        self.assertEqual(ak.sibling_path("freelab_helper.py", folder), os.path.join(folder, "freelab_helper.py"),
                         "neither is there: the name as given (the error then names it)")
        with open(os.path.join(folder, "freelab_helper" + ak.HELPER_SUFFIX), "w") as handle:
            handle.write("VALUE = 7\n")
        self.assertEqual(ak.sibling_path("freelab_helper.py", folder), os.path.join(folder, "freelab_helper.module"))
        with open(os.path.join(folder, "freelab_helper.py"), "w") as handle:
            handle.write("VALUE = 8\n")
        self.assertEqual(ak.sibling_path("freelab_helper.py", folder), os.path.join(folder, "freelab_helper.py"),
                         "the .py first (the repository's layout, and the tests')")


class Stub(object):
    """An object with the attributes given (a tool, a widget, a glyph: what the code reads of it)."""

    def __init__(self, **values):
        self.__dict__.update(values)


class LogGlyphTests(unittest.TestCase):
    """A log's glyphs: drawn as the font draws them, and opened in a Glyph window when clicked."""

    class Found(object):
        isNull = False

        def __init__(self, name):
            self.name = name

    class Font(object):
        def __init__(self, names, codes):
            self.names, self.codes = names, codes

        def findName(self, name):
            return LogGlyphTests.Found(name) if name in self.names else None

        def findUnicode(self, code):
            return LogGlyphTests.Found(self.codes[code]) if code in self.codes else None

    def log(self, font):
        log = ak.Log.__new__(ak.Log)  # (no Qt here: the parts that need none)
        log.view = None
        log.link_handler, log.line, log.lines = None, 16, []
        log.source = lambda: ("fontlab", font, "Regular")
        log.add = lambda text, level="info": log.lines.append((level, text))
        return log

    def patch(self, name, value):
        old = getattr(ak, name)
        setattr(ak, name, value)
        self.addCleanup(lambda: setattr(ak, name, old))

    def test_links_name_glyphs_by_name_or_by_character(self):
        font = self.Font({"uniE000", "A"}, {0x41: "A", 0x1F600: "smile"})
        self.assertEqual(ak.glyph_name_links([u"uniE000", u""]), u'<a href="glyphname:uniE000">uniE000</a>')
        self.assertEqual(ak.glyph_of_link(font, u"glyphname:uniE000"), "uniE000")
        self.assertEqual(ak.glyph_of_link(font, u"glyph:0041"), "A")
        self.assertIsNone(ak.glyph_of_link(font, u"glyphname:gone"))
        self.assertIsNone(ak.glyph_of_link(font, u"glyph:0042"))
        self.assertIsNone(ak.glyph_of_link(None, u"glyph:0041"), "no font open")
        self.assertIsNone(ak.glyph_of_link(font, u"https://example.org"))

    def test_a_character_past_the_basic_plane_keeps_its_code_point(self):
        # FontLab's Python 2 holds it as two halves: the link named the first half alone
        halves = ak.unichr_(0xD83D) + ak.unichr_(0xDE00)
        self.assertEqual(ak.code_point(halves), 0x1F600)
        self.assertEqual(ak.code_point(u"A"), 0x41)
        self.assertEqual(ak.linked_code(ak.glyph_links([halves]).split(u'"')[1]), 0x1F600)

    def test_linked_glyphs_the_font_has_are_drawn_from_it(self):
        # Auto Spacing's log named glyphs by their characters: Cardo's private-use ones came out as boxes
        font = self.Font({"uniE000"}, {0x41: "A"})
        drawn = []
        self.patch("glyph_picture", lambda package, master, name, color, line:
                   drawn.append((name, master, color, line)) or (u"UE5H", 12, 24))
        log = self.log(font)
        text = log.pictured(u"Check %s and %s." % (ak.glyph_name_links([u"uniE000", u"gone"]), ak.glyph_links([u"A"])),
                            (1, 2, 3))
        self.assertEqual(drawn, [("uniE000", "Regular", (1, 2, 3), 16), ("A", "Regular", (1, 2, 3), 16)])
        self.assertIn(u'<a href="glyphname:uniE000"><img src="data:image/png;base64,UE5H" width="12" height="24"', text)
        self.assertIn(u'<a href="glyphname:gone">gone</a>', text, "not in the font: its name stays")
        self.assertIn(u'<a href="glyph:0041"><img ', text)
        log.source = None
        self.assertEqual(log.pictured(ak.glyph_links([u"A"]), (1, 2, 3)), ak.glyph_links([u"A"]), "no font followed")

    def test_a_glyph_without_outlines_keeps_its_text(self):
        self.patch("glyph_picture", lambda *args: None)
        log = self.log(self.Font({"space"}, {}))
        self.assertEqual(log.pictured(ak.glyph_name_links([u"space"]), (0, 0, 0)), ak.glyph_name_links([u"space"]))

    def test_a_link_no_dialog_takes_opens_the_glyph(self):
        opened = []
        self.patch("show_in_glyph_window", lambda fontlab, text: opened.append((fontlab, text)) and None)
        log = self.log(self.Font({"uniE000"}, {0x41: "A"}))
        log.link_clicked(u"glyphname:uniE000")
        log.link_clicked(u"glyph:0041")
        self.assertEqual(opened, [("fontlab", u"/uniE000"), ("fontlab", u"/A")])
        log.link_clicked(u"glyphname:gone")
        self.assertEqual(len(opened), 2)
        self.assertEqual(log.lines, [("warning", u"The font does not have that glyph now.")])

    def test_a_dialog_handler_comes_first(self):
        opened, taken = [], []
        self.patch("show_in_glyph_window", lambda fontlab, text: opened.append(text) and None)
        log = self.log(self.Font({"A", "B"}, {}))
        log.link_handler = lambda target: taken.append(target) or (False if target.endswith(u"B") else None)
        log.link_clicked(u"glyphname:A")
        log.link_clicked(u"glyphname:B")
        self.assertEqual(taken, [u"glyphname:A", u"glyphname:B"])
        self.assertEqual(opened, [u"/B"], "False: left to the log")

    ODD_NAMES = [u"a.alt1", u"f_f_i", u"uni0E01", u"caroncomb.alt", u"a-b~2", u'q"uote', u"a&b", u"x<y>", u"sp ace",
                 u"frag#1", u"what?", u"pct%41", u"e\N{COMBINING ACUTE ACCENT}.ss01", u"\N{HIRAGANA LETTER A}", u"a/b:c"]

    def test_a_glyph_named_in_a_line_is_an_italic_link_to_it(self):
        # The owner's request of 2026-11-24, on Glyph Compose's "Made dotlessi from i without its dot"
        self.assertEqual(ak.glyph_name_link(u"dotlessi"), u'<a href="glyphname:dotlessi"><i>dotlessi</i></a>')
        self.assertEqual(ak.glyph_name_link(u"f_f_i.alt1-2"), u'<a href="glyphname:f_f_i.alt1-2"><i>f_f_i.alt1-2</i></a>',
                         "a name's usual characters kept readable in the target")
        self.assertEqual(ak.glyph_name_link(u"x<y>&z"), u'<a href="glyphname:x%3Cy%3E%26z"><i>x&lt;y&gt;&amp;z</i></a>')
        for name in self.ODD_NAMES:
            link = ak.glyph_name_link(name)
            target = re.match(u'<a href="([^"]*)"><i>(.*)</i></a>$', link)
            self.assertIsNotNone(target, link)
            self.assertFalse(re.search(u"[\\s\"<>&#?]", target.group(1)), link)
            self.assertTrue(all(ord(ch) < 0x80 for ch in target.group(1)), "a target of ASCII alone: %s" % link)
            self.assertEqual(ak.linked_glyph_name(target.group(1)), name, "read back whole")
            self.assertNotIn(u"<", target.group(2))
        # QUrl may hand some characters back decoded: they read the same
        self.assertEqual(ak.linked_glyph_name(u"glyphname:sp ace"), u"sp ace")
        self.assertEqual(ak.linked_glyph_name(u"glyphname:e\N{COMBINING ACUTE ACCENT}.ss01"), u"e\N{COMBINING ACUTE ACCENT}.ss01")
        self.assertEqual(ak.linked_glyph_name(u"glyphname:pct%2541"), u"pct%41", "decoded once, not twice")
        self.assertEqual(ak.linked_glyph_name(u"glyphname:50%"), u"50%", "a stray % stays")

    def test_a_named_glyph_is_opened_on_a_click_and_never_drawn(self):
        opened = []
        self.patch("show_in_glyph_window", lambda fontlab, text: opened.append(text) and None)
        self.patch("glyph_picture", lambda *args: (u"UE5H", 12, 24))
        log = self.log(self.Font(set(self.ODD_NAMES), {}))
        for name in self.ODD_NAMES:
            log.link_clicked(re.search(u'href="([^"]*)"', ak.glyph_name_link(name)).group(1))
        self.assertEqual(opened, [u"/%s" % name for name in self.ODD_NAMES], "each by its own name")
        line = u"Made %s from %s." % (ak.glyph_name_link(u"a.alt1"), ak.glyph_name_link(u"f_f_i"))
        self.assertEqual(log.pictured(line, (0, 0, 0)), line, "a name stays a name: only glyph_name_links are drawn")
        self.assertIn(u"<img ", log.pictured(ak.glyph_name_links([u"a.alt1"]), (0, 0, 0)))

    def test_a_named_glyph_gone_does_nothing_but_say_so(self):
        opened = []
        self.patch("show_in_glyph_window", lambda fontlab, text: opened.append(text) and None)
        log = self.log(self.Font({"i"}, {}))
        log.link_clicked(re.search(u'href="([^"]*)"', ak.glyph_name_link(u"dotlessi")).group(1))
        self.assertEqual(opened, [])
        self.assertEqual(log.lines, [("warning", u"The font does not have that glyph now.")])

    def test_a_log_that_follows_no_font_opens_its_window_tools_font(self):
        # Font Check, Kerning Check, and the other windows whose lines are never drawn: the tool's own font
        opened = []
        self.patch("show_in_glyph_window", lambda fontlab, text: opened.append((fontlab, text)) and None)
        log = self.log(self.Font({"a.alt1"}, {}))
        log.source = None
        log.view = Stub(window=lambda: "the window")
        tool = Stub(fontlab="fontlab", package=self.Font({"a.alt1"}, {}))
        self.patch("window_owner", lambda widget: tool if widget == "the window" else None)
        log.link_clicked(u"glyphname:a.alt1")
        self.assertEqual(opened, [("fontlab", u"/a.alt1")])
        log.link_clicked(u"glyphname:gone")
        self.assertEqual((len(opened), log.lines), (1, [("warning", u"The font does not have that glyph now.")]))
        self.patch("window_owner", lambda widget: None)
        log.link_clicked(u"glyphname:a.alt1")  # (a window no tool holds: nothing)
        log.link_clicked(u"https://example.org")
        self.assertEqual((len(opened), len(log.lines)), (1, 1))

    def test_a_list_of_names_takes_the_serial_comma_and_its_cut(self):
        link = ak.glyph_name_link
        self.assertEqual(ak.glyph_names_linked([u"a"]), link(u"a"))
        self.assertEqual(ak.glyph_names_linked([u"a", u"b"]), u"%s and %s" % (link(u"a"), link(u"b")))
        self.assertEqual(ak.glyph_names_linked([u"a", u"", u"b", u"c"]), u"%s, %s, and %s" % (link(u"a"), link(u"b"), link(u"c")))
        self.assertEqual(ak.glyph_names_linked([u"a", u"b"], word=None), u"%s, %s" % (link(u"a"), link(u"b")))
        self.assertEqual(ak.glyph_names_linked([u"a", u"b", u"c"], word=u"or"), u"%s, %s, or %s" % (link(u"a"), link(u"b"), link(u"c")))
        many = [u"g%d" % index for index in range(1203)]
        cut = ak.glyph_names_linked(many, 3)
        self.assertEqual(cut, u"%s, %s, %s, and 1,200 more" % (link(u"g0"), link(u"g1"), link(u"g2")))
        self.assertEqual(ak.glyph_names_linked(many, 3, word=None), cut, "a cut list ends with and")
        self.assertEqual(ak.glyph_names_linked(many[:3], 3), u"%s, %s, and %s" % (link(u"g0"), link(u"g1"), link(u"g2")))

    def test_flagging_names_its_glyphs_as_links(self):
        logged = []
        self.patch("begin_write", lambda *args, **kwargs: True)
        self.patch("notify_changed", lambda *args, **kwargs: Stub(report=lambda log: True))
        self.patch("history_mark", lambda package: None)
        glyphs = dict((name, Stub(name=name, isNull=False, mark=0)) for name in [u"a.alt1"] + [u"g%d" % n for n in range(50)])
        owner = Stub(package=Stub(findName=glyphs.get), fontlab="fontlab", flagging=None,
                     log=Stub(add=lambda text, level="info": logged.append((level, text))))
        ak.flag_glyphs(owner, [u"a.alt1", u"g0"], u"Red", 1)
        self.assertEqual(logged[-1], ("done", u"Flagged %s, %s red in FontLab (<i>Select &gt; Same Flag</i> gathers them "
                                              u"again; <i>F3</i> goes to the next flagged row here)." % (
                                                  ak.glyph_name_link(u"a.alt1"), ak.glyph_name_link(u"g0"))))
        ak.flag_glyphs(owner, [u"g%d" % n for n in range(50)], u"Red", 0)
        self.assertEqual(logged[-1][1].count(u"<a href="), ak.LOG_NAMES_LINKED, "a row of a group: the rest counted")
        self.assertTrue(logged[-1][1].endswith(u", and 10 more."), logged[-1][1])


class SingleChoiceTests(unittest.TestCase):
    """A dropdown with one choice is drawn as its text, and asks dark mode to leave it as drawn."""

    class Combo(object):
        def __init__(self, count):
            self.count, self.editable, self.styleSheet, self.props = count, False, u"", {}

        def property(self, name):
            return self.props.get(name)

        def setProperty(self, name, value):
            self.props[name] = value

        def setStyleSheet(self, sheet):
            self.styleSheet = sheet

        def setAttribute(self, attribute, on):
            pass

        def setFocusPolicy(self, policy):
            pass

    def test_one_choice_then_two(self):
        class Qt(object):
            WA_TransparentForMouseEvents = NoFocus = StrongFocus = 0

        class QtCore(object):
            pass

        QtCore.Qt = Qt
        old = ak._qt
        ak._qt = lambda: (QtCore, None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        combo = self.Combo(1)
        ak.single_choice(combo)
        self.assertEqual(combo.styleSheet, ak.SINGLE_SHEET)
        self.assertTrue(combo.property(ak.LEAVE_ALONE_PROP), "dark mode's ink effect garbled its text")
        combo.count = 2
        ak.single_choice(combo)
        self.assertEqual(combo.styleSheet, u"")
        self.assertIsNone(combo.property(ak.LEAVE_ALONE_PROP), "a real dropdown again: dark mode's to look at")

    def test_long_then_one_then_a_few_keeps_the_sheet_and_its_flag_together(self):
        # A dropdown long, then one row, then 2 to 24 kept the long list's sheet without the flag: dark mode
        # took it for a styled input and garbled it
        class Qt(object):
            WA_TransparentForMouseEvents = NoFocus = StrongFocus = 0

        class QtCore(object):
            pass

        QtCore.Qt = Qt
        old = ak._qt
        ak._qt = lambda: (QtCore, None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        combo = self.Combo(ak.LONG_CHOICES + 10)
        combo.setMaxVisibleItems = lambda count: None

        def tick():  # (as update_states does)
            ak.single_choice(combo)
            ak.long_choice(combo)

        def consistent():
            return bool(combo.property(ak.LEAVE_ALONE_PROP)) == (combo.styleSheet in (ak.LONG_SHEET, ak.SINGLE_SHEET))

        tick()
        self.assertEqual(combo.styleSheet, ak.LONG_SHEET)
        self.assertTrue(combo.property(ak.LEAVE_ALONE_PROP))
        for count in (1, 5, ak.LONG_CHOICES + 3, 1, ak.LONG_CHOICES + 3, 5):
            combo.count = count
            tick()
            self.assertTrue(consistent(), "%d rows: sheet %r, flag %r" % (count, combo.styleSheet,
                                                                            combo.property(ak.LEAVE_ALONE_PROP)))
        self.assertEqual(combo.styleSheet, ak.LONG_SHEET, "a few rows: opens below its box too")
        self.assertTrue(combo.property(ak.LEAVE_ALONE_PROP))

    def test_every_dropdown_opens_below_its_box(self):
        # The owner: "Some open upwards still even when there's room below" (Glyph Compose's Character set on
        # All, its last row, opened upward over the box)
        class Qt(object):
            WA_TransparentForMouseEvents = NoFocus = StrongFocus = 0

        class QtCore(object):
            pass

        QtCore.Qt = Qt
        old = ak._qt
        ak._qt = lambda: (QtCore, None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        for count in (2, 7, ak.LONG_CHOICES, ak.LONG_CHOICES + 1, 400):
            combo = self.Combo(count)
            shown = []
            combo.setMaxVisibleItems = shown.append
            ak.single_choice(combo)
            ak.long_choice(combo)
            self.assertEqual(combo.styleSheet, ak.LONG_SHEET, "%d rows" % count)
            self.assertIn(u"combobox-popup: 0", combo.styleSheet)
            self.assertTrue(combo.property(ak.LEAVE_ALONE_PROP), "drawn by the palette, not by dark mode's effect")
            self.assertEqual(shown, [ak.LONG_CHOICES], "scrolled past 24 rows")
        own = self.Combo(7)
        own.styleSheet = u"QComboBox { color: red; }"
        ak.long_choice(own)
        self.assertEqual(own.styleSheet, u"QComboBox { color: red; }", "a sheet of its own is left as it is")

    def test_a_long_dropdown_has_a_flat_scroll_bar(self):
        # (owner's image 163: Font Builder's 300 sets scrolled with no bar; Qt had turned the list's bar off
        # for Fusion's menu-like dropdowns when the list was made, before the sheet)
        class Qt(object):
            WA_TransparentForMouseEvents = NoFocus = StrongFocus = 0
            ScrollBarAlwaysOff, ScrollBarAsNeeded = 1, 0

        class QtCore(object):
            pass

        QtCore.Qt = Qt
        old = ak._qt
        ak._qt = lambda: (QtCore, None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))

        class Bar(object):
            styleSheet = u""

            def setStyleSheet(self, sheet):
                self.styleSheet = sheet

        class View(object):
            policy = Qt.ScrollBarAlwaysOff
            bar = Bar()

            def property(self, name):
                return None

            def setProperty(self, name, value):
                pass

            def parentWidget(self):
                return None

            def verticalScrollBarPolicy(self):
                return self.policy

            def setVerticalScrollBarPolicy(self, policy):
                self.policy = policy

            def verticalScrollBar(self):
                return self.bar

        view = View()
        for sheet in (u"", u"QComboBox { color: red; }"):
            combo = self.Combo(300)
            combo.styleSheet = sheet
            combo.setMaxVisibleItems = lambda count: None
            combo.view = lambda: view
            view.policy, view.bar.styleSheet = Qt.ScrollBarAlwaysOff, u""
            ak.long_choice(combo)
            self.assertEqual(view.policy, Qt.ScrollBarAsNeeded, "sheet %r" % sheet)
            self.assertEqual(view.bar.styleSheet, ak.SCROLL_SHEET, "the bar every FreeLab list has")

    def test_the_no_font_sentences_share_a_line_and_no_others(self):
        # (owner's image 191: "the only two sentences that I'll allow on a single line across the suite")
        text = ak.sentences(ak.NO_FONT_LINE + u" A template can still be made.")
        self.assertEqual(text, ak.NO_FONT_LINE + u"<br>A template can still be made.")
        self.assertEqual(ak.sentences(u"Done. Next one."), u"Done.<br>Next one.")

    def test_a_tools_own_no_font_line_shares_a_line_once_registered(self):
        # (owner's images 278 and 280: Proof's and Font Builder's no-font lines on one line too)
        line = u"No font is open. Open one: its proof is laid out at once."
        self.assertEqual(ak.sentences(line), u"No font is open.<br>Open one: its proof is laid out at once.")
        try:
            self.assertEqual(ak.one_line(line), line)
            self.assertEqual(ak.sentences(line + u" Then wait."), line + u"<br>Then wait.")
        finally:
            ak.ONE_LINE.remove(line)

    def test_counts_group_their_thousands(self):
        # (owner's image 231: "13932 glyphs")
        self.assertEqual(ak.counted(13932, u"glyph"), u"13,932 glyphs")
        self.assertEqual(ak.counted(1, u"glyph"), u"1 glyph")
        self.assertEqual(ak.counted(0, u"pair"), u"0 pairs")
        self.assertEqual(ak.grouped(1234567), u"1,234,567")

    def test_the_font_line_names_the_masters_only_when_there_are_several(self):
        # (owner's images 223 and 238: "(1 master)" here, nothing there)
        self.assertEqual(ak.font_named(u"Cardo", u"Regular"), u"<b>Cardo</b>, master <b>Regular</b>")
        self.assertEqual(ak.font_named(u"Cardo", u"Bold", 3),
                         u"<b>Cardo</b>, master <b>Bold</b> (of <b>3 masters</b>)")
        self.assertEqual(ak.font_named(u"A & B"), u"<b>A &amp; B</b>")

    def test_a_tool_named_in_a_log_line_becomes_its_link(self):
        # (owner's image 220: "Write palt with CJK Spacing first")
        line = ak.with_tool_links(ak.html(u"Write palt with CJK Spacing first, then analyze the kana again."))
        self.assertIn(u'<a href="freelab-tool:CJK%20Spacing"><i>CJK Spacing</i></a> first', line)
        linked = u'<a href="x"><i>Font Check</i></a> and Kerning Check'
        self.assertEqual(ak.with_tool_links(linked),
                         u'<a href="x"><i>Font Check</i></a> and ' + ak.tool_link(u"Kerning Check"),
                         "a name inside a link already is left alone")

    def test_a_column_dragged_stops_where_the_others_keep_their_least(self):
        # (owner's image 214: dragged past the frame, every other column went out of sight)
        widths, leasts = [100, 100, 100, 100], [40, 40, 40, 40]
        self.assertEqual(ak.drag_limit(widths, leasts, 1, 400), 400 - 100 - 40 - 40,
                         "the columns before as they are, those after at their least")
        self.assertEqual(ak.drag_limit([100, None, 100, 100], leasts, 0, 400), 400 - 40 - 40, "a hidden column takes nothing")
        self.assertEqual(ak.drag_limit(widths, leasts, 3, 120), ak.MIN_SECTION, "never under the least a column is dragged to")
        self.assertEqual(ak.drag_limit([100, 10, 100], [40, 40, 40], 0, 400), 400 - 24 - 40,
                         "a column narrower than its least counts at MIN_SECTION at least")

    def test_the_header_line_stays_and_the_others_go_without_a_font(self):
        # (owner's images 275, 276: the line under the top text vanished in every window)
        self.assertNotEqual(ak.HEADER_SEPARATOR_PROP, ak.SEPARATOR_PROP)
        source = io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        body = source[source.index(u"def no_font_states("):source.index(u"def checks_of(")]
        self.assertIn(u"line.property(SEPARATOR_PROP)", body)
        self.assertNotIn(u"HEADER_SEPARATOR_PROP", body, "the header's line is never hidden")
        # (owner's image 283: "Now" and "Suggested" over previews of nothing; hidden, and only those it hid
        # shown again with a font)
        self.assertIn(u"label.property(PREVIEW_CAPTION_PROP)", body)
        self.assertIn(u"label.setProperty(NO_FONT_HIDDEN_PROP, True)", body)
        self.assertIn(u"has_font and label.property(NO_FONT_HIDDEN_PROP)", body)

    def test_the_label_before_a_control_in_its_row_captions_it(self):
        class Item(object):
            def __init__(self, widget=None, layout=None):
                self._widget, self._layout = widget, layout

            def widget(self):
                return self._widget

            def layout(self):
                return self._layout

        class Layout(object):
            def __init__(self, *items):
                self.items = list(items)

            def count(self):
                return len(self.items)

            def itemAt(self, k):
                return self.items[k]

        label, combo, other, spin = object(), object(), object(), object()
        row = Layout(Item(other), Item(label), Item(), Item(combo))
        outer = Layout(Item(layout=Layout(Item(spin))), Item(layout=row))
        self.assertIs(ak._next_widget(outer, label), combo, "a stretch between them is skipped")
        self.assertIsNone(ak._next_widget(outer, combo), "the row's last widget captions nothing")
        self.assertIs(ak._next_widget(Layout(Item(spin)), label), ak._NOT_FOUND)

    def test_a_caption_grays_and_explains_with_its_control(self):
        # (owner's images 216 and 281: a right-click on a caption showed the window's help; captions of
        # grayed dropdowns stayed bright)
        class Widget(object):
            def __init__(self, enabled=True, tip=u"", what=u""):
                self.enabled, self.toolTip, self.whatsThis, self.props, self._buddy = enabled, tip, what, {}, None

            def setEnabled(self, on):
                self.enabled = on

            def setToolTip(self, text):
                self.toolTip = text

            def setWhatsThis(self, text):
                self.whatsThis = text

            def setBuddy(self, other):
                self._buddy = other

            def buddy(self):
                return self._buddy

            def setProperty(self, name, value):
                self.props[name] = value

            def property(self, name):
                return self.props.get(name)

        combo, label = Widget(False, u"Where the glyphs go.", u"How sheets place glyphs."), Widget()
        ak.caption(label, combo)
        ak.caption_states([label])
        self.assertFalse(label.enabled)
        self.assertEqual((label.toolTip, label.whatsThis), (u"Where the glyphs go.", u"How sheets place glyphs."))
        combo.enabled = True
        ak.caption_states([label])
        self.assertTrue(label.enabled)
        own = Widget(tip=u"Its own.")
        ak.caption(own, combo)
        ak.caption_states([own])
        self.assertEqual(own.toolTip, u"Its own.", "a caption's own help is kept")

    def test_a_sentences_period_grays_with_the_control_before_it(self):
        # (owner's images 319 to 323: "List changes of at least [6 units] ." with its period bright, no font open)
        class Item(object):
            def __init__(self, widget=None, layout=None):
                self._widget, self._layout = widget, layout

            def widget(self):
                return self._widget

            def layout(self):
                return self._layout

        class Label(object):
            def __init__(self, text=u""):
                self.text, self.props, self._buddy = text, {}, None

            def setBuddy(self, other):
                self._buddy = other

            def buddy(self):
                return self._buddy

            def setProperty(self, name, value):
                self.props[name] = value

            def property(self, name):
                return self.props.get(name)

        class Row(object):
            spacing = 6

            def __init__(self, *items):
                self.items = list(items)

            def count(self):
                return len(self.items)

            def itemAt(self, k):
                return self.items[k]

            def addSpacing(self, value):
                self.items.append(Item())

            def addWidget(self, widget):
                self.items.append(Item(widget))

        old = ak._qt
        ak._qt = lambda: (None, type("QtGui", (), {"QLabel": Label}))
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        spin = object()
        row = Row(Item(Label(u"List changes of at least")), Item(layout=Row(Item(spin))))
        period = ak.sentence_end(row)
        self.assertEqual(period.text, u".")
        self.assertIs(period.buddy(), spin, "the last control in the row, a nested row searched")
        self.assertTrue(period.property(ak.CAPTION_PROP), "grayed and explained with it (caption_states)")

    def test_a_blank_line_under_the_font_line(self):
        # (owner's image 346: Font Check's results stood a blank line under the font's line; every window now)
        class Widget(object):
            def __init__(self, label=True):
                self.label, self.props, self.margins = label, {}, None

            def inherits(self, kind):
                return self.label and kind == "QLabel"

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

            def setContentsMargins(self, *margins):
                self.margins = margins

        class Item(object):
            def __init__(self, widget):
                self._widget = widget

            def widget(self):
                return self._widget

        class Layout(object):
            def __init__(self, parent=None, items=()):
                self.items, self.added = [Item(w) for w in items], []

            def count(self):
                return len(self.items)

            def itemAt(self, k):
                return self.items[k]

            def removeWidget(self, widget):
                self.items = [i for i in self.items if i.widget() is not widget]

            def setContentsMargins(self, *margins):
                pass

            def setSpacing(self, value):
                pass

            def addWidget(self, widget):
                self.added.append(widget)

        old_qt, old_gap = ak._qt, ak.head_gap
        # (staticmethod: a function in a class is a method in Python 2.7)
        ak._qt = lambda: (None, type("QtGui", (), {"QWidget": staticmethod(lambda: Widget(False)), "QVBoxLayout": Layout}))
        ak.head_gap = lambda label: 15
        self.addCleanup(lambda: (setattr(ak, "_qt", old_qt), setattr(ak, "head_gap", old_gap)))
        first, status, line = Widget(), Widget(), Widget(False)
        head = ak.window_head(Layout(items=[status, line]), first)
        self.assertEqual(status.margins, (0, 15, 0, 0), "a line of text above what the tool found")
        self.assertIsNone(first.margins)

    def test_an_empty_output_panel_is_read_longer(self):
        # (owner's image 342: "FontLab reported no errors" while the code named a class the font lacks; FontLab
        # clears the panel as it compiles, so an empty panel may be a compile still under way)
        self.assertTrue(ak.read_again(8, u"", u"", u""), "empty: still read")
        self.assertFalse(ak.read_again(ak.COMPILE_EMPTY_READS_MAX, u"", u"", u""), "then a clean compile")
        self.assertTrue(ak.read_again(2, u"", u"", u"[F] glyph class not defined"), "text that came: read once more")
        self.assertFalse(ak.read_again(3, u"", u"[F] x", u"[F] x"), "stopped growing: read")

    def test_the_log_yields_room_first(self):
        # (owner's image 340: the log kept its dragged height while the lists above it showed a row each)
        self.assertEqual(ak.log_height(180, 180, 40, 100, 0), 80, "the lists lack 100 pixels: the log gives them")
        self.assertEqual(ak.log_height(180, 180, 40, 500, 0), 40, "never under two lines")
        self.assertEqual(ak.log_height(40, 180, 40, 30, 0), 40)
        self.assertEqual(ak.log_height(80, 180, 40, 0, 60), 140, "the window grown: the log takes it back first")
        self.assertEqual(ak.log_height(160, 180, 40, 0, 60), 180, "up to its height")
        self.assertEqual(ak.log_height(180, 180, 40, 0, -50), 180, "shorter, the lists still with room: as it is")

    def test_a_tabs_help_is_its_own(self):
        # (owner's image 329: a right-click on a tab showed the window's whole help, in its middle)
        help_text = (u"<b>Audit</b><br><br><i>Glyph sets</i>: the glyphs each source lacks. <i>Compatibility</i>: each\n"
                     u"glyph's contours across the sources. <i>Features</i>: features some sources lack.<br><br>More.")
        self.assertEqual(ak.help_section(help_text, u"Compatibility"), u"Each glyph's contours across the sources.")
        self.assertEqual(ak.help_section(help_text, u"Features"), u"Features some sources lack.")
        self.assertEqual(ak.help_section(help_text, u"Kerning"), u"")
        self.assertEqual(ak.tab_title(u"Compatibility (52)"), u"Compatibility")
        self.assertEqual(ak.tab_title(u"&Metrics and info (alike)"), u"Metrics and info")

        class Bar(object):
            def __init__(self, texts, whats=(), tips=()):
                self.texts, self.whats, self.tips = texts, list(whats), list(tips)
                self.whatsThis = u""

            def tabText(self, index):
                return self.texts[index]

            def tabWhatsThis(self, index):
                return self.whats[index] if index < len(self.whats) else u""

            def tabToolTip(self, index):
                return self.tips[index] if index < len(self.tips) else u""

            def parentWidget(self):
                return None

            def window(self):
                return Window()

            def property(self, name):
                return None

        class Window(object):
            whatsThis = help_text

            def property(self, name):
                return None

            def parentWidget(self):
                return None

        bar = Bar([u"Glyph sets (3)", u"Compatibility (alike)", u"Kerning"], whats=[u"", u""], tips=[u"", u"", u""])
        self.assertEqual(ak.tab_help(bar, 0), u"The glyphs each source lacks.", "from the window's help")
        bar.whats[0] = u"Its own."
        self.assertEqual(ak.tab_help(bar, 0), u"Its own.")
        self.assertEqual(ak.tab_help(bar, 2), u"", "nothing to say: left to Qt")

    def test_an_empty_list_shows_no_scroll_bars(self):
        class Qt(object):
            ScrollBarAlwaysOff, ScrollBarAsNeeded = 1, 0

        class QtCore(object):
            pass

        QtCore.Qt = Qt
        old = ak._qt
        ak._qt = lambda: (QtCore, None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))

        class View(object):
            topLevelItemCount = 0
            horizontalScrollBarPolicy = verticalScrollBarPolicy = Qt.ScrollBarAsNeeded

            def setHorizontalScrollBarPolicy(self, value):
                self.horizontalScrollBarPolicy = value

            def setVerticalScrollBarPolicy(self, value):
                self.verticalScrollBarPolicy = value

        view = View()
        ak.empty_bars(view)
        self.assertEqual((view.horizontalScrollBarPolicy, view.verticalScrollBarPolicy), (1, 1))
        view.topLevelItemCount = 3
        ak.empty_bars(view)
        self.assertEqual(view.verticalScrollBarPolicy, 0, "back with rows")
        self.assertEqual(view.horizontalScrollBarPolicy, 1, "the horizontal one as the columns are shared (fitted_bar)")
        # (owner's image 295: the horizontal bar flashed as the window was resized, the columns shared on the
        # next turn of the event loop passing the new width meanwhile)
        ak.fitted_bar(view, [100, None, 199], 300)
        self.assertEqual(view.horizontalScrollBarPolicy, 1, "off while the columns fit")
        ak.fitted_bar(view, [100, None, 250], 300)
        self.assertEqual(view.horizontalScrollBarPolicy, 0, "as needed once they pass the width")
        ak.fitted_bar(view, [100, 200], 300)
        self.assertEqual(view.horizontalScrollBarPolicy, 1, "off again")
        view.topLevelItemCount = 0
        view.horizontalScrollBarPolicy = 0
        ak.fitted_bar(view, [500], 300)
        self.assertEqual(view.horizontalScrollBarPolicy, 0, "an empty list is empty_bars' alone")

    def test_a_line_over_a_sections_heading_stays_without_a_font(self):
        # (owner's image 318: "missing on all windows where it should be present", Feature Code with no font)
        class Widget(object):
            def __init__(self, kind, props=None):
                self.kind, self.props = kind, props or {}

            def inherits(self, name):
                return name == self.kind

            def property(self, name):
                return self.props.get(name)

        class Item(object):
            def __init__(self, widget):
                self._widget = widget

            def widget(self):
                return self._widget

            def layout(self):
                return None

        class Layout(object):
            def __init__(self, *widgets):
                self.items = [Item(w) for w in widgets]

            def count(self):
                return len(self.items)

            def itemAt(self, k):
                return self.items[k]

        line, heading, caption, table = (Widget("QFrame"), Widget("QLabel"),
                                         Widget("QLabel", {ak.PREVIEW_CAPTION_PROP: True}), Widget("QTreeWidget"))
        for after, kept in ((heading, True), (caption, False), (table, False), (None, False)):
            parent = type("Parent", (object,), {"layout": lambda self, l=Layout(*[w for w in (line, after) if w]): l})()
            line.parentWidget = lambda parent=parent: parent
            self.assertEqual(ak.heads_section(line), kept, after and after.kind)

    def test_a_splitters_panes_get_their_shares_at_first(self):
        # (live: CJK Spacing's previews of large text took the window, its list showing one row)
        self.assertEqual(ak.shares_of(600, [3, 2, 1]), [300, 200, 100])
        self.assertEqual(sum(ak.shares_of(601, [3, 3, 2])), 601, "every pixel given")
        self.assertEqual(ak.shares_of(500, [2, 0, 3]), [200, 0, 300], "a pane without a share takes none")
        self.assertEqual(ak.shares_of(10, []), [])

    def test_a_tab_switch_hides_the_others_before_showing_its_own(self):
        # (owner's image 284, live: the bottom row held both tabs' buttons a moment and the window grew)
        calls = []

        class Widget(object):
            def __init__(self, name, visible):
                self.name, self.visible = name, visible

            def setVisible(self, on):
                calls.append((self.name, on))
                self.visible = on

        a1, a2, b1 = Widget("a1", True), Widget("a2", True), Widget("b1", False)
        ak.show_only({"a": [a1, a2], "b": [b1]}, "b")
        self.assertEqual(calls, [("a1", False), ("a2", False), ("b1", True)])
        del calls[:]
        ak.show_only([[b1], [a1, a2]], 1)
        self.assertEqual(calls[0], ("b1", False), "a list of groups too, the others hidden first")
        self.assertEqual(sorted(calls[1:]), [("a1", True), ("a2", True)])
        del calls[:]
        ak.show_only([[b1], [a1, a2]], 1)
        self.assertEqual(calls, [("b1", False)], "nothing shown again that is shown")
        ak.show_only([[b1], []], 5)  # (no such group: all hidden, no error)

    def test_a_window_taking_anothers_place_is_centered_at_the_size_it_shows_at(self):
        # (owner's image 311: Qt grew each new window to its least width to the right; the arrows walked the
        # windows off to the right of the screen)
        moved = []

        class Dialog(object):
            width, height, pos = 1400, 800, None

            def move(self, x, y):
                moved.append((x, y))

        class Owner(object):
            dialog = Dialog()

        owner = Owner()
        old_area, old_xy = ak._free_area, ak._xy
        ak._free_area = lambda dialog: ((0, 0, 1920, 1040), (16, 39))
        ak._xy = lambda pos: (300, 100)
        self.addCleanup(lambda: (setattr(ak, "_free_area", old_area), setattr(ak, "_xy", old_xy)))
        owner.placed_from = ((300, 100), (1000, 800))  # (the old window's place and size)
        ak.keep_center(owner)
        self.assertEqual(moved, [(100, 100)], "200 pixels each side of the old center")
        self.assertIsNone(owner.placed_from, "once")
        ak.keep_center(owner)
        self.assertEqual(moved, [(100, 100)])
        ak.keep_center(object())  # (a window that took no place: nothing, no error)

    def test_a_tools_font_is_shown_before_fontlabs_commands_act(self):
        # (owner's image 314: a Glyph window asked for while FontLab showed another font was refused)
        class Package(object):
            def __init__(self, name):
                self.tfn = name

        one, two = Package(u"One"), Package(u"Two")

        class Workspace(object):
            currentPackage = two

        workspace = Workspace()

        class FontLab(object):
            class flWorkspace(object):
                @staticmethod
                def instance():
                    return workspace

        class Window(object):
            def __init__(self, package):
                self.package = package

            def inherits(self, name):
                return name == ak.FONT_WINDOW_CLASS and self.package is not None

        tried = []

        class Tabs(object):
            pages = [(u"Sketchboard", Window(None)), (u" Two ", Window(two)), (u" One Regular ", Window(one))]
            currentIndex = 1
            count = 3

            def widget(self, k):
                return self.pages[k][1]

            def tabText(self, k):
                return self.pages[k][0]

            def setCurrentIndex(self, k):
                tried.append(k)
                self.currentIndex = k
                if self.pages[k][1].package is not None:
                    workspace.currentPackage = self.pages[k][1].package

        tabs = Tabs()
        saved = (ak._font_id, ak.find_font, ak._main_tab_widgets, ak.AutoKerningDialog.__dict__["main_window"])  # (the staticmethod itself: read off the class, Python 2 gave an unbound method)
        ak._font_id = lambda package: None if package is None else package.tfn
        ak.find_font = lambda ws, font_id: {u"One": one, u"Two": two}.get(font_id)
        ak._main_tab_widgets = lambda main: [tabs]
        ak.AutoKerningDialog.main_window = staticmethod(lambda: object())

        def restore():
            ak._font_id, ak.find_font, ak._main_tab_widgets = saved[:3]
            ak.AutoKerningDialog.main_window = saved[3]
        self.addCleanup(restore)

        class Owner(object):
            font_id = u"One"

        self.assertTrue(ak.focus_font(Owner(), FontLab))
        self.assertEqual(tried, [2], "the tab naming the font first")
        self.assertIs(workspace.currentPackage, one)
        self.assertTrue(ak.focus_font(Owner(), FontLab), "shown already: nothing switched")
        self.assertEqual(tried, [2])
        tabs.pages[2] = (u" Renamed ", Window(one))
        workspace.currentPackage, tabs.currentIndex = two, 1
        self.assertTrue(ak.focus_font(Owner(), FontLab), "found by trying the Font windows")
        tabs.pages[2] = (u" One ", Window(two))  # (no tab of the font: the tab shown before put back)
        workspace.currentPackage, tabs.currentIndex = two, 1
        del tried[:]
        self.assertFalse(ak.focus_font(Owner(), FontLab))
        self.assertEqual(tabs.currentIndex, 1)
        no_font = Owner()
        no_font.font_id = None
        self.assertTrue(ak.focus_font(no_font, FontLab), "a window with no font: nothing to show")

    def test_a_control_grayed_for_no_font_stays_grayed_whatever_the_tool_asks(self):
        class Button(object):
            def __init__(self):
                self.enabled, self.props = True, {}

            def property(self, name):
                return self.props.get(name)

            def setEnabled(self, on):
                self.enabled = on

        button = Button()
        button.props[ak.NO_FONT_PROP] = True
        button.enabled = False
        ak.enable(button, True)
        self.assertFalse(button.enabled)
        button.props[ak.NO_FONT_PROP] = None
        ak.enable(button, True)
        self.assertTrue(button.enabled)

    def test_a_window_has_a_font_by_its_package_or_its_own_word(self):
        class Tool(object):
            package = None
        self.assertFalse(ak.window_has_font(Tool()))
        tool = Tool()
        tool.works_without_font = True
        self.assertTrue(ak.window_has_font(tool), "Font Builder works without one")
        tool = Tool()
        tool.has_font = lambda: True
        self.assertTrue(ak.window_has_font(tool))

    def test_a_replaced_module_is_kept_alive(self):
        # (Python 2.7 empties a freed module's globals: a window of the copy a reinstall replaced printed
        # tracebacks at its signals)
        import types
        made = [types.ModuleType("m%d" % i) for i in range(30)]
        first = id(made[0])
        for module in made:
            ak.hold_module(module)
        ak.hold_module(made[-1])
        held = sys._freelab_held_modules
        del made[:]  # (only the holder keeps them now: none is let go, however many came after)
        self.assertTrue(any(id(m) == first for m in held), "the first is still held after 29 more")
        self.assertEqual(sum(1 for m in held if m is held[-1]), 1, "held once")
        for module in [m for m in held if m.__name__.startswith("m") and m.__name__[1:].isdigit()]:
            held.remove(module)  # (the test's own, let go)
        with io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            self.assertIn(u"hold_module(held)", handle.read(), "load_sibling holds the copy it replaces")

    def test_every_dropdowns_popup_list_is_left_alone_by_dark_mode(self):
        # (owner's image 162: the popup list, a window of its own, recolored by dark mode as one of FontLab's
        # lists, its light text with colored fringes)
        class Qt(object):
            WA_TransparentForMouseEvents = NoFocus = StrongFocus = 0

        old = ak._qt
        ak._qt = lambda: (type("QtCore", (), {"Qt": Qt}), type("QtGui", (), {"QComboBox": "QComboBox"}))
        self.addCleanup(lambda: setattr(ak, "_qt", old))

        class View(object):
            def __init__(self):
                self.props, self.container = {}, None

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

            def parentWidget(self):
                return self.container

        boxes = []
        for count, sheet in ((7, u""), (1, u""), (3, u"QComboBox { color: red; }")):
            combo = self.Combo(count)
            combo.styleSheet, combo.setMaxVisibleItems = sheet, lambda count: None
            popup = View()
            popup.container = View()  # (QComboBoxPrivateContainer: the popup window holding it)
            combo.view = lambda popup=popup: popup
            boxes.append((combo, popup))
            dialog = type("Dialog", (), {"findChildren": lambda dialog, kind, combo=combo: [combo]})()
            ak.style_combos(dialog)  # (as every window's states are kept, update_states)
            self.assertTrue(popup.property(ak.LEAVE_ALONE_PROP), "%d choices, sheet %r" % (count, sheet))
            self.assertTrue(popup.container.property(ak.LEAVE_ALONE_PROP), "its popup window too")
            self.assertFalse(popup.property(ak.POPUP_GRAY_PROP), "a light palette: ClearType's own text, no effect")
        ak.leave_popup_alone(object())  # (a box without a list: nothing raised)

    def test_a_dropdowns_list_gets_no_effect_and_loses_an_old_one(self):
        # (live, 2026-11-17: an opacity effect meant to smooth the popup's text in gray changed nothing, the list
        # paints an opaque background, and cost an offscreen render at every repaint: none now; one an earlier
        # build put on is taken off)
        class View(object):
            def __init__(self):
                self.props, self.effects = {}, []

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

            def parentWidget(self):
                return None

            def setGraphicsEffect(self, effect):
                self.effects.append(effect)

        view = View()
        combo = type("Combo", (), {"view": lambda c: view})()
        ak.leave_popup_alone(combo)
        self.assertEqual(view.effects, [], "no effect")
        self.assertTrue(view.property(ak.LEAVE_ALONE_PROP))
        view.setProperty(ak.POPUP_GRAY_PROP, True)  # (one an earlier build put on)
        ak.leave_popup_alone(combo)
        self.assertEqual(view.effects, [None], "taken off")
        self.assertFalse(view.property(ak.POPUP_GRAY_PROP))
        ak.leave_popup_alone(combo)
        self.assertEqual(view.effects, [None], "once")


class WindowFilterTests(unittest.TestCase):
    """Every FreeLab window's filter: help on a grayed-out control, tooltips laid out for the window, and
    selections cleared by a click beside them."""

    class Widget(object):
        def __init__(self, kinds=(), parent=None, **values):
            self.kinds = set(kinds) | set(["QWidget"])
            self.parent, self.children, self.props = parent, [], {}
            self.whatsThis = self.toolTip = u""
            self.enabled, self.visible, self.mouseTracking, self.selectionMode, self.width = True, True, False, 1, 1000
            self.at = None
            if parent is not None:
                parent.children.append(self)
            for name, value in values.items():
                setattr(self, name, value)

        def inherits(self, kind):
            return kind in self.kinds

        def parentWidget(self):
            return self.parent

        def isWindow(self):
            return self.parent is None

        def window(self):
            widget = self
            while widget.parent is not None:
                widget = widget.parent
            return widget

        def property(self, name):
            return self.props.get(name)

        def setProperty(self, name, value):
            self.props[name] = value

        def findChildren(self, kind):
            found = []
            for child in self.children:
                if child.inherits(kind):
                    found.append(child)
                found.extend(child.findChildren(kind))
            return found

        def childAt(self, pos):
            return self.at

    class View(Widget):
        def __init__(self, parent, rows=3, **values):
            WindowFilterTests.Widget.__init__(self, ("QAbstractItemView", "QAbstractScrollArea"), parent, **values)
            self.rows, self.selected, self.current, self.cleared = rows, True, True, 0
            self.port = WindowFilterTests.Widget((), self)
            view = self

            class Model(object):
                @property
                def hasSelection(self):
                    return view.selected

                def clearCurrentIndex(self):
                    view.current = False

            self.model = Model()

        def selectionModel(self):
            return self.model

        def clearSelection(self):
            self.selected = False
            self.cleared += 1

        def indexAt(self, pos):
            valid = pos[1] < self.rows * 20

            class Index(object):
                def isValid(self):
                    return valid

            return Index()

    class Event(object):
        def __init__(self, kind, button=1, pos=(5, 5)):
            self.kind, self.pressed, self.where = kind, button, pos

        def type(self):
            return self.kind

        def button(self):
            return self.pressed

        def pos(self):
            return self.where

        def globalPos(self):
            return self.where

    def setUp(self):
        case = self
        self.timers, self.helped = [], []

        class Core(object):
            class Qt(object):
                LeftButton, RightButton, ToolTipRole = 1, 2, 3

            class QTimer(object):
                def __init__(self, parent=None):
                    self.parent_ = parent  # (the window's filters are made with the window as parent)

                @staticmethod
                def singleShot(ms, slot):
                    case.timers.append(slot)

        class Gui(object):
            QAbstractItemView = "QAbstractItemView"

        old_qt, old_help, old_windows = ak._qt, ak.show_disabled_help, getattr(sys, "_freelab_windows", None)
        ak._qt = lambda: (Core, Gui)
        ak.show_disabled_help = lambda widget, where: case.helped.append(widget) or True
        sys._freelab_windows = None

        def restore():
            ak._qt, ak.show_disabled_help, sys._freelab_windows = old_qt, old_help, old_windows

        self.addCleanup(restore)

    def test_a_right_click_on_a_grayed_out_control_shows_its_help(self):
        # The owner: "greyed out buttons do not give access to their tooltips through right-clicking"
        window = self.Widget()
        window.whatsThis = u"The window's help."
        button = self.Widget(("QAbstractButton",), window, enabled=False, whatsThis=u"Writes the checked pairs.")
        pending = []
        self.assertTrue(ak.filter_event(window, button, self.Event(3, button=2), pending), "the release is taken")
        self.assertEqual(self.helped, [], "shown once the context menu had its chance")
        self.timers.pop()()
        self.assertEqual(self.helped, [button])
        self.assertTrue(ak.filter_event(window, button, self.Event(82), []), "a context menu, if Qt sends one")
        self.assertEqual(self.helped, [button, button])
        button.enabled = True
        self.assertFalse(ak.filter_event(window, button, self.Event(82), []), "an enabled one: Qt's own")
        self.assertEqual(ak.disabled_help(button), u"Writes the checked pairs.")
        button.whatsThis, button.toolTip = u"", u"Write them."
        self.assertEqual(ak.disabled_help(button), u"Write them.", "else its tooltip")
        button.toolTip = u""
        self.assertEqual(ak.disabled_help(button), u"The window's help.", "else its container's help")

    def test_a_value_typed_without_enter_is_taken_before_a_button_acts(self):
        # The owner (2026-11-16): 100 typed in Feature Code's Strokes over 130, Build clicked without Enter:
        # it built at 130. A press on any button of the window first commits the field with the focus.
        window = self.Widget()
        spin = self.Widget(("QAbstractSpinBox",), window, value=130, text=u"100")
        field = self.Widget(("QLineEdit",), spin)  # (the spin box's own line edit, focused while typed in)
        log = self.Widget(("QTextEdit",), window)
        build = self.Widget(("QAbstractButton",), window)
        heard = []

        def interpret():
            spin.value = int(spin.text)
            heard.append(("valueChanged", spin.value))
        spin.interpretText = interpret
        field.clearFocus = lambda: heard.append("focus out")
        log.clearFocus = lambda: heard.append("log focus out")
        focused = [field]
        ak._qt()[1].QApplication = type("App", (), {"focusWidget": staticmethod(lambda: focused[0])})
        self.assertFalse(ak.filter_event(window, build, self.Event(2), []), "the press goes on to the button")
        self.assertEqual(heard, [("valueChanged", 100), "focus out"], "the value taken, then the field left")
        self.assertEqual(spin.value, 100)
        del heard[:]
        ak.filter_event(window, build, self.Event(2, button=2), [])
        build.enabled = False
        ak.filter_event(window, build, self.Event(2), [])
        focused[0] = log
        build.enabled = True
        ak.filter_event(window, build, self.Event(2), [])
        other = self.Widget()
        focused[0] = self.Widget(("QLineEdit",), other)
        ak.filter_event(window, build, self.Event(2), [])
        self.assertEqual(heard, [], "a right-click, a grayed-out button, a text editor, another window's field: left alone")
        focused[0] = self.Widget(("QLineEdit",), window, clearFocus=lambda: heard.append("search left"))
        self.assertIs(ak.commit_typing(window, build), focused[0])
        self.assertEqual(heard, ["search left"], "a plain field: its editing ended (editingFinished)")
        del heard[:]
        spin.text, spin.clearFocus, focused[0] = u"120", lambda: heard.append("box left"), spin  # (Qt's focus proxy: the box)
        self.assertIs(ak.commit_typing(window, build), spin)
        self.assertEqual(heard, [("valueChanged", 120), "box left"], "the box focused itself: the same")

    def test_tooltips_are_as_wide_as_their_window_allows(self):
        # The owner: tooltips "stupidly compacted when there's ample space"
        measure = lambda text: 7 * len(text)
        short = u"Drag the space between two parts up or down to give one more room."
        laid_out = ak.tip_html(short, ak.tip_width(1000), measure)
        self.assertIn(u'width="%d"' % (7 * len(short) + ak.TIP_MARGIN), laid_out, "one line: as wide as it is")
        long = u"A sentence of some length that goes on. " * 6
        self.assertIn(u'width="%d"' % ak.tip_width(1000), ak.tip_html(long, ak.tip_width(1000), measure))
        self.assertEqual([ak.tip_width(w) for w in (400, 1000, 1400, 3000)], [360, 500, 700, 900])
        self.assertIsNone(ak.tip_html(u'<table width="300"><tr><td>Built</td></tr></table>', 500, measure),
                          "a tool's own layout is left as it is")
        self.assertIsNone(ak.tip_html(u"", 500, measure))
        self.assertIn(u"a &lt; b", ak.tip_html(u"a < b", 500, measure), "plain text stays plain")

    def test_paragraphs_of_a_tooltip_are_a_blank_line_apart(self):
        # The owner: "line jumps between paragraphs of tooltips so it reads better"
        measure = lambda text: 7 * len(text)
        self.assertIn(u"It is checked.<br><br>Click to write it.",
                      ak.tip_html(u"It is checked.\nClick to write it.", 500, measure))
        self.assertIn(u"<i>Now</i>%s.<br><br>Then" % ak.ITALIC_GAP, ak.tip_html(u"<i>Now</i>.<br>Then", 500, measure))
        self.assertIn(u"A V<br>T o", ak.tip_html(u"A V\nT o", 500, measure), "a list, a line each, stays")
        self.assertNotIn(u"<br><br><br>", ak.tip_html(u"One.<br><br>Two.", 500, measure))

    def test_a_click_beside_the_lists_clears_their_selection(self):
        # The owner: "It's never possible to unselect a row even by clicking outside any table"
        window = self.Widget()
        view = self.View(window)
        label = self.Widget(("QLabel",), window)
        window.at = label
        self.assertFalse(ak.filter_event(window, window, self.Event(2), []))
        self.assertEqual((view.selected, view.current), (False, False), "on a label: cleared")
        view.selected = view.current = True
        for target in (self.Widget(("QAbstractButton",), window, enabled=False),
                       self.Widget(("QLabel",), window, props={ak.LEAVE_ALONE_PROP: True}),
                       self.Widget(("QLabel",), window, mouseTracking=True)):
            window.at = target
            ak.filter_event(window, window, self.Event(2), [])
            self.assertTrue(view.selected, "a control, grayed out or not, or a picture: kept")
        window.at = label
        ak.filter_event(window, window, self.Event(2, button=2), [])
        self.assertTrue(view.selected, "a right-click: kept")
        ak.filter_event(window, view.port, self.Event(2, pos=(5, 30)), [])
        self.assertTrue(view.selected, "on a row: Qt's own")
        ak.filter_event(window, view.port, self.Event(2, pos=(5, 300)), [])
        self.assertFalse(view.selected, "under the last row: cleared")

    def test_some_lists_keep_their_selection(self):
        window = self.Widget()
        window.setProperty(ak.WINDOW_PROP, 1)
        pages, scripts, other = self.View(window), self.View(window), self.View(window)
        pages.setProperty(ak.KEEP_SELECTION_PROP, True)  # (Proof's pages)

        class Owner(object):
            tool, window_key, dialog, script_tree = "Font Check", 1, window, scripts

        sys._freelab_windows = {"fonts": {}, "kept": [Owner()], "next": 1, "hint": None}
        self.assertEqual([ak.keeps_selection(v) for v in (pages, scripts, other)], [True, True, False])
        other.selectionMode = 0
        self.assertTrue(ak.keeps_selection(other), "a list that selects nothing")
        other.selectionMode = 1
        window.at = window
        header = self.View(scripts)  # (a tree's header: a list of its own that shares the tree's selection)
        header.kinds = ("QAbstractItemView", "QHeaderView")
        ak.filter_event(window, window, self.Event(2), [])
        self.assertEqual([v.selected for v in (pages, scripts, other)], [True, True, False])
        self.assertTrue(header.selected, "a header is never cleared: that cleared the tree's selection, live")

    def test_the_window_is_walked_as_built_then_only_once_a_widget_is_added(self):
        # update_states walked every shown window each 300 ms: 1.3 ms of its 2.3 ms on Feature Code, live
        gui = ak._qt()[1]
        for kind in ak.HELP_KINDS + ("QWidget",):
            setattr(gui, kind, kind)
        filters = {}
        self.Widget.installEventFilter = lambda widget, watcher: filters.setdefault(id(widget), []).append(watcher)
        old_filters = getattr(sys, "_freelab_window_filters", None)
        sys._freelab_window_filters = None

        def restore():
            del self.Widget.installEventFilter
            sys._freelab_window_filters = old_filters

        self.addCleanup(restore)
        window = self.Widget()
        page = self.Widget((), window)
        self.Widget(("QAbstractButton",), page)
        self.assertTrue(ak.install_filters(window), "as built")
        self.assertFalse(ak.install_filters(window), "nothing added since: not walked")
        watcher = sys._freelab_window_filters[window.property(ak.WINDOW_FILTER_PROP)]
        self.assertIn(watcher.child_watch, filters[id(page)], "a container watched for new children")
        later = self.Widget(("QAbstractButton",), page, enabled=False, whatsThis=u"Builds them.")
        self.assertFalse(ak.install_filters(window), "Qt has not said so yet")
        self.assertFalse(watcher.child_watch.eventFilter(page, self.Event(ak.CHILD_ADDED)), "the event goes on")
        self.assertTrue(ak.install_filters(window), "a widget was added: walked")
        self.assertIn(watcher, filters[id(later)], "a control made later gets the filter")
        self.assertTrue(watcher.eventFilter(later, self.Event(3, button=2)), "and its right-click help")
        self.timers.pop()()
        self.assertEqual(self.helped, [later])
        self.assertFalse(ak.install_filters(window))
        watcher.eventFilter(window, self.Event(ak.CHILD_ADDED))  # (a child of the window itself)
        self.assertTrue(ak.install_filters(window))


class KerningCheckPreviewRuleTests(unittest.TestCase):
    """The review of November 23 (image 12): Kerning Check's two lines showed between three empty previews.
    A preview's caption and the line before it show only while that preview has a pair drawn."""

    class Part(object):
        def __init__(self):
            self.visible, self.properties, self.text, self.pixmap = True, {}, None, None

        def setVisible(self, on):
            self.visible = on

        def setProperty(self, name, value):
            self.properties[name] = value

        def property(self, name):
            return self.properties.get(name)

        def setText(self, text):
            self.text = text

        def clear(self):
            self.text, self.pixmap = u"", None

        def setPixmap(self, pixmap):
            self.pixmap = pixmap

    class Picture(object):
        def width(self):
            return 120

    def dialog(self):
        part = self.Part
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)  # (its window needs FontLab)
        dialog.ak = ak
        dialog.previews = [part(), part(), part()]
        dialog.preview_captions = [part(), part(), part()]
        dialog.lines = [part(), part()]
        dialog.preview_parts = [[dialog.preview_captions[0]], [dialog.lines[0], dialog.preview_captions[1]],
                                [dialog.lines[1], dialog.preview_captions[2]]]
        for parts in dialog.preview_parts:  # (as built)
            ak.preview_filled(parts, False)
        dialog.package = object()
        dialog.update_buttons_soon = lambda: None
        dialog.pair_picture = lambda left, right, value, room=False, width=None: self.Picture()
        return dialog

    @staticmethod
    def shown(dialog):
        return ([caption.visible for caption in dialog.preview_captions], [line.visible for line in dialog.lines])

    def test_captions_and_lines_only_over_a_pair_drawn(self):
        dialog = self.dialog()
        self.assertEqual(self.shown(dialog), ([False] * 3, [False] * 2), "nothing selected yet")
        self.assertTrue(all(p.property(ak.PREVIEW_EMPTY_PROP) for parts in dialog.preview_parts for p in parts),
                        "marked empty: the shared no_font_states leaves them hidden with a font")
        selected = [kc.Collision(u"T", u"o", -40, 5, -20, None, reference=(u"T", u"e"))]
        dialog.selected_finding = lambda: selected[0]
        dialog.update_previews()
        self.assertEqual(self.shown(dialog), ([True] * 3, [True] * 2), "now, adjusted, and the base pair")
        self.assertEqual([c.text for c in dialog.preview_captions], [u"Now: -40", u"Adjusted: -20", u"Base pair: -40"])
        selected[0] = kc.Collision(u"T", u"o", -40, 5, -20, None)  # (no base pair: two previews)
        dialog.update_previews()
        self.assertEqual(self.shown(dialog), ([True, True, False], [True, False]),
                         "no line beside the third preview's empty room, nor its caption")
        selected[0] = None  # (nothing selected: only the hint, if any, in the middle preview's room)
        dialog.update_previews()
        self.assertEqual(self.shown(dialog), ([False] * 3, [False] * 2), "emptied: hidden again")
        self.assertEqual(dialog.previews[1].text, dialog.preview_hint(), "the hint kept, without lines or captions")
        self.assertTrue(all(p.property(ak.PREVIEW_EMPTY_PROP) for parts in dialog.preview_parts for p in parts))
        dialog.package = None  # (the font closed: nothing to draw)
        selected[0] = kc.Collision(u"T", u"o", -40, 5, -20, None)
        dialog.update_previews()
        self.assertEqual(self.shown(dialog), ([False] * 3, [False] * 2))

    def test_lists_emptied_for_another_font_empty_the_previews(self):
        class Tree(object):
            def clear(self):
                pass

        calls = []
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.collisions, dialog.cleanup, dialog.masters = [type("Tab", (), {"tree": Tree()})() for _ in range(3)]
        dialog.current_font, dialog.package = lambda: None, object()
        dialog.read_font = lambda: calls.append("read")
        dialog.update_previews = lambda: calls.append("previews")
        dialog.update_buttons = lambda: calls.append("buttons")
        dialog.log = type("Log", (), {"add": lambda log, text, kind=None: None})()
        self.assertFalse(dialog.same_font())
        self.assertEqual(calls, ["read", "previews", "buttons"])

    def test_the_parts_are_hidden_as_built(self):
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        init = source.split(u"class KerningCheckDialog")[1].split(u"\n    def current_font")[0]
        built = init.split(u"self.preview_parts = []")[1].split(u"layout.addLayout(previews)")[0]
        self.assertIn(u"self.preview_parts[-1].append(self.ak.separator(vertical=True))", built)
        self.assertIn(u"self.preview_parts[-1].append(caption)", built)
        self.assertIn(u"self.ak.preview_filled(self.preview_parts[-1], False)", built)


class KerningCheckTableTests(unittest.TestCase):
    """The owner: Kerning Check's tables "aligned in terms of layout with the other ones"."""

    def test_the_pair_its_glyphs_then_its_numbers(self):
        self.assertEqual(kc.COLLISION_COLUMNS, (u"Pair", u"Glyphs", u"Kerning", u"Distance", u"Fix", u"Set by",
                                                u"Compared with"))
        self.assertEqual(kc.COLLISION_COLUMNS.index(u"Fix"), 4, "a fix dragged by hand is shown in its own column")
        self.assertTrue(set([u"Kerning", u"Distance", u"Fix", u"Value"]) <= set(kc.NUMBER_COLUMNS))
        self.assertEqual(ak.glyph_icon_size(2), (int(ak.GLYPH_ICON_SIZE * 2.8), int(ak.GLYPH_ICON_SIZE * 1.45)))

    def test_a_closed_font_empties_the_lists(self):
        class Tree(object):
            def __init__(self):
                self.cleared = 0

            def clear(self):
                self.cleared += 1

        class Tab(object):
            def __init__(self):
                self.tree, self.findings, self.first_checks, self.texts = Tree(), [1], [True], []
                self.status = type("Status", (), {"setText": lambda status, text: self.texts.append(text)})()

        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)  # (its window needs FontLab)
        dialog.collisions, dialog.cleanup, dialog.masters = Tab(), Tab(), Tab()
        calls = []
        dialog.read_font = lambda: calls.append("read") or False  # (no font left open)
        dialog.update_previews = lambda: calls.append("previews")
        dialog.update_buttons = lambda: calls.append("buttons")
        dialog.font_changed()
        for tab in (dialog.collisions, dialog.cleanup, dialog.masters):
            self.assertEqual((tab.tree.cleared, tab.findings, tab.first_checks, tab.texts), (1, [], [], [u""]))
        self.assertEqual(calls, ["read", "previews", "buttons"])
        self.assertEqual(dialog.stale, set(kc.TABS), "each list checked again as it is shown")

    def test_the_pictures_room_shows_nothing_until_a_pair_is_selected(self):
        # (owner's image 337: "Select a pair to see it here..." in this window's previews alone; no other
        # tool's empty previews say anything)
        class Label(object):
            def __init__(self):
                self.text = None

            def clear(self):
                self.text = u""

            def setText(self, text):
                self.text = text

        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.previews = [Label(), Label(), Label()]
        dialog.preview_captions = [Label(), Label(), Label()]
        dialog.package = object()
        dialog.selected_finding = lambda: None
        dialog.update_buttons_soon = lambda: None
        listed = type("Tab", (), {"findings": [object()]})()
        dialog.collisions = dialog.cleanup = dialog.masters = listed
        for index in (0, 1, 2):
            dialog.tabs = type("Tabs", (), {"currentIndex": index})()
            dialog.update_previews()
            self.assertEqual([label.text for label in dialog.previews], [u"", u"", u""])
            self.assertEqual([label.text for label in dialog.preview_captions], [u""] * 3, "nothing shown: no caption")
        self.assertFalse(hasattr(kc, "PREVIEW_HINTS"))

    def test_columns_fit_every_row_closed_groups_too(self):
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read().split(u"def resize(tab):")[1].split(u"\n    def ")[0]
        self.assertIn(u"fit_rows(tab.tree, range(tab.tree.columnCount - 1))", source)
        self.assertNotIn(u"resizeColumnToContents", source, "Qt measures only the rows it shows")

    def test_its_buttons_sit_at_the_bottom_as_every_tools(self):
        # (owner's report 152: they sat under each list, above the previews and the log)
        class Button(object):
            def __init__(self, name):
                self.name, self.visible = name, True

            def setVisible(self, on):
                self.visible = on

        class Row(qtfakes.CancelRow):
            @property
            def order(self):
                return ["|" if widget is None else widget.name if hasattr(widget, "name") else widget.text
                        for widget in self.items]

        class Tab(object):
            def __init__(self, key, action=True):
                self.action = Button(key + " action") if action else None
                self.check_all, self.check_none, self.restore = (Button(key + " all"), Button(key + " none"),
                                                                 Button(key + " restore"))

        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.ak = ak
        dialog.collisions, dialog.cleanup, dialog.masters = Tab("collisions"), Tab("cleanup"), Tab("masters", False)
        dialog.glyph_window_button, dialog.close_button = Button("glyph window"), Button("close")
        real = ak._qt
        ak._qt = lambda: (None, type("QtGui", (object,), {"QPushButton": staticmethod(qtfakes.CancelButton)}))
        self.addCleanup(setattr, ak, "_qt", real)
        row = dialog.bottom_row(type("QtGui", (), {"QHBoxLayout": Row}))
        self.assertEqual(row.order, ["collisions all", "collisions none", "collisions restore", "cleanup all",
                                     "cleanup none", "cleanup restore", "glyph window", "|", "collisions action",
                                     "cleanup action", "Cancel", "close"],
                         "checks at the left, the action, Cancel, then Close at the right")
        shown = lambda: sorted(b.name for tab in (dialog.collisions, dialog.cleanup) for b in
                               (tab.check_all, tab.check_none, tab.restore, tab.action) if b.visible)
        self.assertEqual(shown(), ["collisions action", "collisions all", "collisions none", "collisions restore"])
        dialog.pages = type("Pages", (), {"setCurrentIndex": lambda pages, index: None})()
        dialog.update_previews, dialog.stale, dialog.package = lambda: None, set(), None
        dialog.switch_page(1)
        self.assertEqual(shown(), ["cleanup action", "cleanup all", "cleanup none", "cleanup restore"])
        dialog.switch_page(2)
        self.assertEqual(shown(), [], "Masters: nothing to check or write")
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        init = source.split(u"class KerningCheckDialog")[1].split(u"\n    def current_font")[0]
        self.assertGreater(init.index(u"layout.addLayout(self.bottom_row(QtGui))"), init.index(u"layout.addWidget(self.log.widget)"),
                           "the bottom row under the log")
        self.assertNotIn(u"tab.buttons", source)

    def test_check_all_and_check_none_say_what_they_did(self):
        class Item(object):
            def __init__(self, parent=None):
                self.state, self.parent_item = 0, parent

            def checkState(self, column):
                return self.state

            def setCheckState(self, column, state):
                self.state = state

            def isHidden(self):
                return False

            def isExpanded(self):
                return False

            def parent(self):
                return self.parent_item

        group = Item()
        items = [Item(), Item(group), Item(group)]
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.ak, logged = ak, []
        dialog.log = type("Log", (), {"add": lambda log, text, level="info": logged.append(text)})()
        dialog.collisions, dialog.cleanup = object(), object()
        dialog.rows = lambda tab: items
        dialog.update_buttons = lambda: None
        old = ak._qt
        ak._qt = lambda: (type("Core", (), {"Qt": type("Qt", (), {"Checked": 2, "Unchecked": 0})}), None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        dialog.check_every(dialog.collisions, True)
        # (Tick, not Check, for check boxes: owner's image 261)
        self.assertEqual(logged[-1], u"<i>Tick all</i> ticked <b>3 pairs</b> (<b>2</b> of them in closed groups).")
        dialog.check_every(dialog.cleanup, False)
        self.assertEqual(logged[-1], u"<i>Untick all</i> unticked <b>3 entries</b> (<b>2</b> of them in closed groups).")

    def test_a_list_filled_says_what_the_pictures_room_is_for(self):
        # (live, 2026-11-16: the hint showed only once a pair was selected, then unselected)
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        lines = [line.strip() for line in source.splitlines()]
        fills = [index for index, line in enumerate(lines) if line == u"self.resize(tab)"]
        self.assertEqual(len(fills), 3, "the three lists' fillings")
        self.assertEqual([lines[index + 1].split(u"  #")[0] for index in fills], [u"self.update_previews()"] * 3,
                         "each followed by the pictures' room")


class KerningCheckReviewTests(unittest.TestCase):
    """The owner's review of 2026-11-17: Kerning Check's long steps in the window's top row (ak.busy_*), its
    Cleanup line with nothing listed, its separators with no font."""

    def fake_busy(self, stop_after=None):
        calls = []
        saved = dict((name, getattr(ak, name)) for name in ("busy_start", "busy_progress", "busy_end", "busy_stopping"))
        self.addCleanup(lambda: [setattr(ak, name, value) for name, value in saved.items()])

        def progress(owner, what=None, part=None, force=False, stoppable=True):
            calls.append(("progress", what, stoppable))
            if stop_after is not None and stoppable and sum(1 for c in calls if c[0] == "progress") > stop_after:
                raise ak.Stopped()
        ak.busy_start = lambda owner, what=u"", stoppable=True: calls.append(("start", what, stoppable))
        ak.busy_progress = progress
        ak.busy_end = lambda owner: calls.append(("end", None, None))
        ak.busy_stopping = lambda owner: False
        return calls

    def test_the_cleanup_line_with_nothing_listed(self):
        # (owner's image 190: "0 of 0 entries listed: none.")
        self.assertEqual(kc.cleanup_status(0, 0, {}), u"No entries listed.")
        self.assertEqual(kc.cleanup_status(0, 120, {}), u"No entries listed.")
        self.assertEqual(kc.cleanup_status(3, 120, {"redundant": 2, "tiny": 1}),
                         u"3 of 120 entries listed: 2 entries changing nothing, 1 tiny value.")
        self.assertEqual(kc.cleanup_status(1, 1, {"missing": 1}, u" with this glyph"),
                         u"1 of 1 entry with this glyph listed: 1 entry naming what is gone.")

    def test_its_separators_are_the_shared_ones(self):
        # (owner's images 202 and 210: hidden with no font, which only ak.separator's are)
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        # (owner's image 229: the line between a list's settings and its status separated nothing once the
        # status moved to the header; the header's line and those between the previews are the shared ones)
        self.assertEqual(source.count(u"self.ak.separator)"), 0, "no line between a list's settings and its table")
        self.assertEqual(source.count(u"self.ak.header_separator()"), 1)
        self.assertEqual(source.count(u"self.ak.separator(vertical=True)"), 1, "between two previews side by side")
        self.assertNotIn(u"QtGui.QFrame()", source)
        self.assertNotIn(u".setEnabled(", source, "every control's state through ak.enable")
        self.assertNotIn(u"processEvents", source, "the top row's progress lets events through")

    def test_the_header_holds_the_font_the_status_then_its_line(self):
        # (owner's images 222 vs 223: a separator between the top text and the tabs; image 229: the result line
        # under the font's, not under the settings row)
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        init = source.split(u"class KerningCheckDialog")[1].split(u"\n    def current_font")[0]
        order = [init.index(text) for text in (u"layout.addWidget(self.font_label)", u"layout.addWidget(self.status_line)",
                                               u"layout.addWidget(self.limit_widget)",
                                               u"layout.addWidget(self.ak.header_separator())",
                                               u"layout.addWidget(self.tabs)")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn(u"self.layout.addWidget(self.status)", source, "no status under a list's settings")

    def test_the_font_line_counts_masters_only_beyond_one(self):
        # (owner's images 223 and 238: "(1 master)" here, nothing elsewhere)
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(u"self.ak.font_named(self.package.tfn, self.master, count)", source)
        self.assertNotIn(u'counted(count, u"master")', source)
        self.assertEqual(ak.font_named(u"BIZ UDGothic", u"Regular", 1), u"<b>BIZ UDGothic</b>, master <b>Regular</b>")

    def test_the_shown_lists_status_is_the_headers(self):
        class Line(object):
            text = None

            def setText(self, text):
                self.text = text

        line = Line()
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.status_line = line
        current = [0]
        shown = lambda status: (dialog.collisions, dialog.cleanup, dialog.masters)[current[0]].status is status
        dialog.collisions, dialog.cleanup, dialog.masters = [type("Tab", (), {})() for _ in range(3)]
        for tab in (dialog.collisions, dialog.cleanup, dialog.masters):
            tab.status = kc.TabStatus(line, shown)
        dialog.collisions.status.setText(u"Collisions' line.")
        self.assertEqual(line.text, u"Collisions' line.")
        dialog.cleanup.status.setText(u"Cleanup's line.")
        self.assertEqual(line.text, u"Collisions' line.", "a list not shown keeps its line for later")
        current[0] = 1
        dialog.show_tab_status(1)
        self.assertEqual(line.text, u"Cleanup's line.")
        current[0] = 0
        dialog.show_tab_status(0)
        self.assertEqual(line.text, u"Collisions' line.")

    def test_the_collisions_row_reads_as_a_sentence(self):
        # (owner's image 243: a period after the last dropdown, "(e.g., Tcaron o vs. To)"; brief: Check inline after it)
        self.assertEqual(kc.COLLISION_MODES[0][1], u"and that many units closer than without the accent (e.g., "
                                                   u"\N{LATIN CAPITAL LETTER T WITH CARON}o vs. To)")
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        row = source.split(u"tab.settings.addWidget(QtGui.QLabel(\"List\"))")[1].split(u"tab.settings.addStretch(1)")[0]
        self.assertLess(row.index(u"tab.settings.addWidget(self.mode)"), row.index(u"sentence_end(tab.settings)"))
        self.assertLess(row.index(u"sentence_end(tab.settings)"), row.index(u"tab.settings.addWidget(self.collisions_button)"))
        self.assertIn(u"QLabel(\"Also list values smaller than\")", source)
        self.assertIn(u"QPushButton(TICK_ALL)", source)
        self.assertEqual((kc.TICK_ALL, kc.TICK_NONE), (u"Tick all", u"Untick all"))

    def test_the_collisions_line_is_right_at_zero_one_and_two(self):
        # (owner's image 229: "None of the 0 pairs kerned tighter comes within 41 units")
        status = lambda found, tight, relative=True: kc.collision_status(found, tight, 41, relative)
        self.assertEqual(status(0, 0), u"No pair is kerned tighter: nothing to check.")
        self.assertEqual(kc.collision_status(0, 0, 41, common=True, limited=u" with this glyph"),
                         u"No common pair with this glyph is kerned tighter: nothing to check.")
        self.assertEqual(status(0, 1), u"The only pair kerned tighter does not come within 41 units, and that many "
                                       u"units closer than without the accent.")
        self.assertEqual(status(1, 1, False), u"The only pair kerned tighter comes within 41 units of each other, "
                                              u"kerning applied.")
        self.assertEqual(status(0, 2), u"None of the 2 pairs kerned tighter comes within 41 units, and that many units "
                                       u"closer than without the accent.")
        self.assertEqual(status(1, 2, False), u"1 of the 2 pairs kerned tighter comes within 41 units of each other, "
                                              u"kerning applied.")
        self.assertEqual(status(2, 1438, False), u"2 of the 1,438 pairs kerned tighter come within 41 units of each "
                                                 u"other, kerning applied.")
        self.assertEqual(kc.collision_status(0, 0, 1, bold=ak.b), u"No pair is kerned tighter: nothing to check.")
        self.assertNotIn(u" 0 ", u" ".join(status(0, tight) for tight in (0, 1, 2)))

    def tab(self):
        class Tree(object):
            def clear(self):
                pass

        class Status(object):
            text = None

            def setText(self, text):
                self.text = text
        return type("Tab", (), {"tree": Tree(), "status": Status(), "action": None, "findings": [1],
                                "first_checks": [True]})()

    def test_a_stopped_check_lists_nothing_and_says_so(self):
        calls = self.fake_busy(stop_after=1)
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.ak, dialog.busy, dialog.only = ak, False, None
        dialog.cleanup = dialog.collisions = self.tab()
        dialog.masters = object()
        dialog.read_font = lambda: True
        dialog.update_previews = dialog.update_buttons = lambda: None
        dialog.tiny = type("Box", (), {"value": 5})()
        entries = [((u"A", False), (u"V%d" % n, False)) for n in range(60)]
        kerning = type("Kerning", (), {"entries": entries, "values": dict((e, -40) for e in entries), "members": {},
                                       "describe": staticmethod(lambda e: u"%s %s" % (e[0][0], e[1][0])),
                                       "pairs": staticmethod(lambda e: []),
                                       "candidates": staticmethod(lambda a, b: [])})()
        dialog.kerning = lambda master=None: kerning
        dialog.glyph_exists = lambda name: True
        dialog.check_cleanup()
        self.assertEqual([c[0] for c in calls], ["start", "progress", "progress", "end"])
        self.assertTrue(calls[0][2], "stoppable")
        self.assertFalse(dialog.busy)
        self.assertEqual(dialog.cleanup.findings, [])
        self.assertIn(u"was stopped: nothing is listed", dialog.cleanup.status.text)

    def test_a_write_is_never_stopped_and_always_ends(self):
        calls = self.fake_busy(stop_after=0)
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.ak, dialog.busy = ak, False
        dialog.collisions = self.tab()
        dialog.same_font = lambda: True
        chosen = [kc.Collision(u"T", u"o%d" % n, -60, 2, -40, None) for n in range(30)]
        dialog.checked = lambda tab: chosen
        written = []
        kerning = type("Kerning", (), {"current": staticmethod(lambda a, b: -60),
                                       "write": staticmethod(lambda *args: written.append(args))})()
        dialog.kerning = lambda master=None: kerning
        status = type("Status", (), {"undo": lambda s, text: text, "report": lambda s, log: None})()
        dialog.after_writing = lambda: status
        dialog.begin_writing = lambda: True
        checks = []
        dialog.check_collisions = lambda: checks.append(dialog.busy)
        dialog.log = type("Log", (), {"add": lambda log, text, kind="info": None})()
        dialog.write_fixes()
        self.assertEqual(len(written), 30, "all written, whatever was asked meanwhile")
        self.assertEqual((calls[0][0], calls[-1][0]), ("start", "end"))
        self.assertFalse(any(c[2] for c in calls if c[0] != "end"), "never stoppable")
        self.assertEqual(checks, [False], "checked again once the write is over")


class KerningCheckRoundThreeTests(unittest.TestCase):
    """The owner's round of images 283 to 318: the tabs' settings rows as tall as one another (285, 286), and
    every count bold with its noun (297, 301)."""

    def test_the_settings_rows_are_as_tall_as_one_another(self):
        # (owner's images 285 and 286: Masters' row, a button alone, was shorter than Cleanup's spin box row,
        # and its table moved up a few pixels as the tab was shown)
        class Hint(object):
            def __init__(self, height):
                self.value = height

            def height(self):
                return self.value

        class Control(object):
            def __init__(self, height):
                self.sizeHint = Hint(height)  # (PythonQt: a property read as an attribute)

        class Item(object):
            def __init__(self, widget):
                self.held = widget

            def widget(self):
                return self.held

        class Layout(object):
            def __init__(self, widgets):
                self.items = [Item(widget) for widget in widgets]

            def count(self):
                return len(self.items)

            def itemAt(self, index):
                return self.items[index]

        class Box(object):
            def __init__(self, *heights):
                self.held, self.least = Layout([Control(h) for h in heights] + [None]), None  # (None: a stretch)

            def layout(self):
                return self.held

            def setMinimumHeight(self, height):
                self.least = height

        collisions, cleanup, masters = Box(16, 24, 22, 23), Box(16, 24, 23), Box(23)
        self.assertEqual(kc.level_rows([collisions, cleanup, masters]), 24)
        self.assertEqual([box.least for box in (collisions, cleanup, masters)], [24, 24, 24],
                         "the button's row as tall as the spin box's")
        self.assertEqual(kc.level_rows([object()]), 0, "nothing readable: nothing set, and no error")
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.collisions, dialog.cleanup, dialog.masters = [type("Tab", (), {"settings_box": box})()
                                                             for box in (Box(30), Box(20), Box(10))]
        dialog.pages = type("Pages", (), {"setCurrentIndex": lambda pages, index: None})()
        dialog.show_tab_buttons = dialog.show_tab_status = dialog.update_previews = lambda *args: None
        dialog.stale, dialog.package = set(), None
        dialog.switch_page(2)
        self.assertEqual([tab.settings_box.least for tab in (dialog.collisions, dialog.cleanup, dialog.masters)],
                         [30, 30, 30], "measured again as a tab is shown")
        with io.open(kc.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(u"self.settings = QtGui.QHBoxLayout(self.settings_box)", source, "each row in a widget of its own")
        self.assertLess(source.index(u"self.level_settings()\n        self.read_font()"),
                        source.index(u"def current_font"), "levelled as the window is made")

    def test_counts_are_bold_with_their_nouns(self):
        # (owner's images 297 and 301: "**3** of **120 entries**" and "between **3** masters" bolded the number alone)
        self.assertEqual(kc.cleanup_status(3, 120, {"redundant": 2, "tiny": 1}, bold=ak.b),
                         u"<b>3 of 120 entries</b> listed: <b>2 entries</b> changing nothing, <b>1 tiny value</b>.")
        self.assertEqual(kc.cleanup_status(1, 1, {"missing": 1}, u" with this glyph", ak.b),
                         u"<b>1 of 1 entry</b> with this glyph listed: <b>1 entry</b> naming what is gone.")
        self.assertEqual(kc.collision_status(2, 1438, 41, False, bold=ak.b),
                         u"<b>2 of the 1,438 pairs</b> kerned tighter come within <b>41 units</b> of each other, "
                         u"kerning applied.")
        self.assertEqual(kc.collision_status(0, 2, 41, False, limited=u" with this glyph", bold=ak.b),
                         u"None of the <b>2 pairs</b> with this glyph kerned tighter comes within <b>41 units</b> of "
                         u"each other.")
        self.assertEqual(kc.masters_status(3, 2, bold=ak.b), u"<b>3 differences</b> between <b>2 masters</b>.")
        self.assertEqual(kc.masters_status(0, 3, bold=ak.b),
                         u"The <b>3 masters</b> kern the same entries, with the same signs.")
        self.assertEqual(kc.masters_status(1, 2, True, u" with this glyph", ak.b),
                         u"<b>1 difference</b> between <b>2 masters</b>, in the entries and classes with this glyph.")
        self.assertEqual(kc.masters_status(0, 2, True, u" with this glyph"),
                         u"The 2 masters kern the entries with this glyph the same, with the same signs, and their "
                         u"classes hold the same glyphs.")


class ChoiceSheetTests(unittest.TestCase):
    def test_the_chosen_suggestion_has_a_light_tint_of_the_highlight(self):
        # The owner: "the selected suggestions should probably get a light blue background to stand out from
        # the unavailable buttons"
        class Color(object):
            def red(self):
                return 0

            def green(self):
                return 120

            def blue(self):
                return 215

        class Palette(object):
            def color(self, role):
                return Color()

        class Gui(object):
            class QPalette(object):
                Highlight = 12

        old = ak._qt
        ak._qt = lambda: (None, Gui)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        sheet = ak.choice_sheet(Palette())
        self.assertIn(u"QToolButton:checked { background: rgba(0, 120, 215, %d);" % ak.CHOSEN_ALPHA, sheet)
        self.assertIn(u"QToolButton:disabled { background: transparent;", sheet, "the unavailable ones stay plain")
        self.assertLess(ak.CHOSEN_ALPHA, 128, "a light tint: the pair's ink stays legible in either palette")


class AutoKerningListTests(unittest.TestCase):
    """The owner, on Auto Kerning's table in dark mode: "The table headers look bad in dark mode here;
    probably yet another argument in favor of making this table adopt the same layout as other tables"."""

    class Stub(object):
        """Any widget the list's methods only tell things to."""

        def __init__(self, **values):
            self.__dict__.update(values)
            self.calls = []

        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return lambda *args: self.calls.append((name,) + args)

    class Color(object):
        def __init__(self, value, alpha=255):
            self.hex = value.hex if isinstance(value, AutoKerningListTests.Color) else value
            self.alpha = value.alpha if isinstance(value, AutoKerningListTests.Color) else alpha

        def name(self):
            return self.hex

        def setAlpha(self, alpha):
            self.alpha = alpha

        def red(self):
            return int(self.hex[1:3], 16)

        def green(self):
            return int(self.hex[3:5], 16)

        def blue(self):
            return int(self.hex[5:7], 16)

    class Palette(object):
        def __init__(self, text, highlight):
            self.text, self.highlight = text, highlight

        def color(self, role):
            return AutoKerningListTests.Color(self.text if role == "WindowText" else self.highlight)

    class Font(object):
        def __init__(self, other=None):
            self.bold = other.bold if other is not None else False

        def setBold(self, on):
            self.bold = on

    class Item(object):
        def __init__(self, texts):
            self.texts, self.values, self.aligned, self.fonts, self.tips, self.icons = list(texts), {}, {}, {}, {}, {}
            self.state = self.flags = None

        def setData(self, column, role, value):
            self.values[(column, role)] = value

        def data(self, column, role):
            return self.values.get((column, role))

        def setText(self, column, text):
            self.texts[column] = text

        def setFont(self, column, font):
            self.fonts[column] = font

        def setToolTip(self, column, tip):
            self.tips[column] = tip

        def setIcon(self, column, icon):
            self.icons[column] = icon

        def setCheckState(self, column, state):
            self.state = state

        def checkState(self, column):
            return self.state

        def setFlags(self, flags):
            self.flags = flags

        def setTextAlignment(self, column, value):
            self.aligned[column] = value

    class Tree(object):
        columnCount = 8

        def __init__(self):
            self.items, self.current, self.updates, self.header_aligned = [], None, 0, {}
            self.font = AutoKerningListTests.Font()

        @property
        def topLevelItemCount(self):  # (a Qt property: a value under PythonQt)
            return len(self.items)

        def topLevelItem(self, index):
            return self.items[index]

        def addTopLevelItem(self, item):
            self.items.append(item)

        def clear(self):
            self.items, self.current = [], None

        def selectedItems(self):
            return [self.current] if self.current is not None else []

        def setCurrentItem(self, item):
            self.current = item

        def scrollToItem(self, item):
            pass

        def setFocus(self):
            pass

        def header(self):
            return AutoKerningListTests.Stub()

        def resizeColumnToContents(self, column):
            pass

        def headerItem(self):
            tree = self
            return type("Header", (), {"setTextAlignment": lambda header, column, value: tree.header_aligned.update(
                {column: value})})()

        def viewport(self):
            return self

        def update(self):
            self.updates += 1

    def setUp(self):
        test = self

        class Qt(object):
            UserRole, Checked, Unchecked = 0x0100, 2, 0
            ItemIsSelectable, ItemIsEnabled, ItemIsUserCheckable = 1, 32, 16
            AlignRight, AlignVCenter = 0x02, 0x80

        class Rect(object):
            def __init__(self, *args):
                self.args = args

        class Delegate(object):
            painted = []

            def __init__(self, parent=None):
                pass

            @staticmethod
            def paint(delegate, painter, option, index):
                Delegate.painted.append(index)

        class QtCore(object):
            pass

        class QtGui(object):
            QTreeWidgetItem, QFont, QColor = test.Item, test.Font, test.Color
            QStyledItemDelegate = Delegate

            class QPalette(object):
                WindowText, Highlight = "WindowText", "Highlight"

            @staticmethod
            def QIcon():
                return "no picture"

        QtCore.Qt, QtCore.QRect = Qt, Rect
        self.Qt, self.QtGui = Qt, QtGui
        old = ak._qt, ak.glyph_icon
        ak._qt = lambda: (QtCore, QtGui)
        self.drawn = []
        ak.glyph_icon = lambda package, master, names, color, value=0: self.drawn.append(
            (tuple(names), color.name(), value)) or u"%s %s at %d in %s" % (names[0], names[1], value, color.name())

        def put_back():
            ak._qt, ak.glyph_icon = old
        self.addCleanup(put_back)

    def suggestion(self, left_char, right_char, left, right, current=0, **values):
        s = ak.Suggestion(left_char, right_char, left, right, current)
        s.values.update(values)
        return s

    def window(self, suggestions, text="#000000", highlight="#0078d7"):
        Stub = self.Stub
        d = ak.AutoKerningDialog.__new__(ak.AutoKerningDialog)  # (its window needs FontLab)
        d.tree, d.suggestions, d.icon_cache, d.adjustments = self.Tree(), suggestions, {}, {}
        d.dialog = Stub(palette=self.Palette(text, highlight), font=self.Font())
        d.package, d.master, d.font_kerning, d.script, d.selected = object(), u"Regular", None, "latin", None
        d.source = Stub(currentIndex=0)  # (Average of halfkern and Contour)
        d.choice_buttons = dict((key, Stub()) for key, _ in ak.CHOICES)
        for name in ("reset_button", "glyph_window_button", "preview_note", "related", "all_button", "none_button",
                     "apply_button", "restore_button", "classes_button", "check_button", "tolerance", "show_kind",
                     "order", "include_kerned", "pairs", "analyze_button"):
            setattr(d, name, Stub())
        d.only_picked, d.picked_room_kept = Stub(checked=False), True
        d.analysis, d.busy, d.common, d.fontlab, d.buttons_due = None, False, {}, None, False
        d.kerning_read = 1e12  # (the font's kerning read just now: not asked of FontLab again)
        d.previewed, d.logged = [], []
        d.show_preview = lambda s: d.previewed.append((s.left, s.right))
        d.log = type("Log", (), {"add": lambda log, text, level="info": d.logged.append((level, text))})()
        return d

    def test_writing_again_writes_nothing_and_says_so(self):
        # (owner's report 151: Write checked pairs, clicked again, logged "Wrote 0 entries for 0 pairs" each time)
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        to = self.suggestion(u"T", u"o", u"T", u"o", 0, halfkern=-90, contour=-70)
        d = self.window([av, to])
        stored = FakeKerning({}, {})

        class Package(object):
            path, tfn, upm = u"a.vfc", u"A", 1000

            @staticmethod
            def kerning(master):
                return stored

        d.package, d.analysis = Package(), ak.Analysis([av, to], {}, (None, None))
        d.after_writing = lambda package: type("Status", (), {"report": lambda status, log: None,
                                                              "undo": lambda status, text: text})()
        d.begin_kerning_write = lambda: True
        d.refresh_kerning()
        d.fill_table()
        enabled = lambda: [call[1] for call in d.apply_button.calls if call[0] == "setEnabled"][-1]
        self.assertTrue(enabled(), "two pairs to write")
        d.write()
        self.assertEqual(stored.stored, {(("A", False), ("V", False)): -70, (("T", False), ("o", False)): -80})
        self.assertIn(u"Wrote <b>2 entries</b> for <b>2 pairs</b> to master <b>Regular</b>", d.logged[-1][1])
        self.assertTrue(d.logged[-1][1].endswith(u" (<i>Edit &gt; Undo</i> takes them back)."),
                        "the write is a History step: the log says Undo takes it back")
        self.assertEqual([item.state for item in d.tree.items], [self.Qt.Checked] * 2, "its checks stay")
        self.assertFalse(enabled(), "nothing new to write: grayed out")
        d.write()
        self.assertEqual(d.logged[-1], ("info", u"Nothing was written: every ticked pair has the value it would be "
                                               u"given already."))
        self.assertFalse(any(u"Wrote 0" in text for _, text in d.logged))
        d.source = self.Stub(currentIndex=[key for key, _ in ak.SOURCES].index("halfkern"))
        d.update_buttons()
        self.assertTrue(enabled(), "another source: something new to write")

    def test_check_new_pairs_and_check_none_say_what_they_did(self):
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        kerned = self.suggestion(u"T", u"o", u"T", u"o", -40, halfkern=-90, contour=-70)
        d = self.window([av, kerned])
        d.fill_table()
        d.tree.items[1].setCheckState(0, self.Qt.Checked)
        d.check_all(False)
        self.assertEqual(d.logged[-1], ("info", u"<i>Untick all</i> unticked <b>2 pairs</b>."))
        d.tree.items[1].setCheckState(0, self.Qt.Checked)
        d.check_all(True)
        self.assertEqual(d.logged[-1], ("info", u"<i>Tick new pairs</i> ticked <b>1 pair</b> and unticked <b>1</b>."),
                         "a pair the font kerns is unchecked by it, as before, and said so")

    def test_rows_in_the_layout_of_the_other_lists(self):
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        kerned = self.suggestion(u"T", u"o", u"T", u"o", -40, halfkern=-90, contour=-70)
        hebrew = self.suggestion(u"\N{HEBREW LETTER BET}", u"\N{HEBREW LETTER ALEF}", u"bet", u"alef", 0, halfkern=-10,
                                 contour=-20)  # (bet left of alef)
        d = self.window([av, kerned, hebrew])
        d.fill_table()
        rows = d.tree.items
        self.assertEqual([item.texts[0] for item in rows], [u"AV", u"To", u"\N{HEBREW LETTER ALEF}\N{HEBREW LETTER BET}"],
                         "a Hebrew pair typed in text order, which Qt sets right to left: as read")
        self.assertEqual([item.data(0, self.Qt.UserRole) for item in rows], [0, 1, 2], "each row knows its pair")
        self.assertEqual([item.state for item in rows], [self.Qt.Checked, self.Qt.Unchecked, self.Qt.Checked],
                         "pairs the font kerns start unchecked")
        self.assertEqual(rows[0].texts[1:], [u"0", u"-80", u"-60", u"\N{EN DASH}", u"\N{EN DASH}", u"20", u"-70"])
        right = int(self.Qt.AlignRight | self.Qt.AlignVCenter)
        self.assertEqual(rows[0].aligned, dict((column, right) for column in range(1, 8)), "numbers right-aligned")
        self.assertEqual(d.tree.header_aligned, dict((column, 0x4 | 0x80) for column in range(8)),
                         "every header centered (owner's report 141)")
        self.assertEqual(self.drawn, [((u"A", u"V"), u"#000000", -70), ((u"T", u"o"), u"#000000", -80),
                                      ((u"bet", u"alef"), u"#000000", -15)],
                         "each pair drawn as on screen, at the value it takes, in the window's text color")
        self.assertEqual(rows[2].icons[0], u"bet alef at -15 in #000000")
        self.assertIn(u"Read right to left: alef first", rows[2].tips[0])
        with io.open(ak.__file__, encoding="utf-8") as handle:
            source = handle.read().split(u"class AutoKerningDialog")[1].split(u"\ndef font_class_suggestions")[0]
        for wanted in (u"QtGui.QTreeWidget()", u"setProperty(LEAVE_ALONE_PROP, True)", u"table_layout(self.tree, stretch=0)",
                       u"glyph_icon_size(2)"):
            self.assertIn(wanted, source)
        self.assertNotIn(u"QTableWidget", source, "no table left: its header was what looked bad")

    def test_a_pick_tints_the_row_from_the_palette_as_drawn(self):
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        d = self.window([av])
        d.fill_table()
        item = d.tree.items[0]
        self.assertEqual([item.data(column, ak.PICKED_ROLE) for column in range(8)], [None] * 8)
        d.tree.setCurrentItem(item)
        d.select()
        self.assertEqual((d.selected, d.previewed), (0, [(u"A", u"V")]))
        d.choose("halfkern")
        item = d.tree.items[0]
        self.assertEqual([item.data(column, ak.PICKED_ROLE) for column in range(8)], [True] * 8)
        self.assertTrue(item.fonts[7].bold)
        self.assertEqual(item.texts[7], u"-80")
        self.assertEqual(self.drawn[-1], ((u"A", u"V"), u"#000000", -80), "its picture at the value picked")
        d.reset()
        self.assertEqual([item.data(column, ak.PICKED_ROLE) for column in range(8)], [None] * 8)
        self.assertFalse(item.fonts[7].bold)

    def test_the_tint_and_the_flags_painted_by_one_delegate(self):
        d = self.window([])
        d.tree.setItemDelegate = d.tree.setItemDelegateForColumn = lambda *args: None
        delegate = d.tint_rows()
        filled = []
        painter = type("Painter", (), {"fillRect": lambda painter, rect, color: filled.append((rect, color))})()

        class Rect(object):
            def left(self):
                return 0

            def top(self):
                return 0

            def width(self):
                return 40

            def height(self):
                return 20

            def bottom(self):
                return 19

        option = type("Option", (), {"rect": Rect(), "palette": self.Palette("#ffffff", "#2a82da")})()

        def index(column, picked, flags=None):
            values = {ak.PICKED_ROLE: picked, ak.FLAG_ROLE: flags}
            return type("Index", (), {"data": lambda index, role: values.get(role), "column": lambda index: column})()

        delegate.paint(painter, option, index(3, True))
        self.assertEqual([(color.name(), color.alpha) for _, color in filled], [(u"#2a82da", ak.PICKED_ALPHA)],
                         "the highlight of the palette it is drawn with: a dark mode switch needs no new brush")
        del filled[:]
        delegate.paint(painter, option, index(3, None, u"#ff0000"))
        self.assertEqual(filled, [], "flags only in the pair's column")
        delegate.paint(painter, option, index(0, None, u"#ff0000,"))
        self.assertEqual([(color.name(), color.alpha) for _, color in filled],
                         [(u"#ff0000", ak.FLAG_TINT), (u"#ff0000", 255)], "a flag's tint, then its bar over the row")

    def test_kana_drawn_as_palt_sets_them(self):
        ka = self.suggestion(u"\N{KATAKANA LETTER KA}", u"\N{KATAKANA LETTER I}", u"ka", u"i", 0)
        d = self.window([ka])
        d.adjustments = {u"ka": (-20, -50), u"i": (-30, -60)}  # (placement, added width)
        self.assertEqual(d.icon_value(ka, -10), -10 + (-50 + 20) - 30)
        d.adjustments = {}
        self.assertEqual(d.icon_value(ka, -10), -10)

    def test_a_dark_mode_switch_redraws_what_came_from_the_palette(self):
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        d = self.window([av])
        d.fill_table()
        d.tree.setCurrentItem(d.tree.items[0])
        d.select()
        del self.drawn[:], d.previewed[:]
        d.dialog.palette = self.Palette("#dbdbdb", "#2a82da")  # (switched to dark)
        d.theme_changed()
        self.assertEqual(self.drawn, [((u"A", u"V"), u"#dbdbdb", -70)], "the pictures in the new text color")
        self.assertEqual(d.tree.items[0].icons[0], u"A V at -70 in #dbdbdb")
        self.assertEqual(d.previewed, [(u"A", u"V")], "the previews too")
        for button in d.choice_buttons.values():
            sheets = [call[1] for call in button.calls if call[0] == "setStyleSheet"]
            self.assertEqual(len(sheets), 1, "restyled once")
            self.assertIn(u"rgba(42, 130, 218,", sheets[0], "the chosen suggestion's tint, from the new highlight")
        self.assertGreater(d.tree.updates, 0, "the rows' tints repainted")
        self.assertFalse(hasattr(ak.AutoKerningDialog, "watch_palette"),
                         "no palette watcher of its own: FreeLab's shared mechanism calls theme_changed")

    def test_the_selected_pair_stays_selected_when_the_list_is_filled_again(self):
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        to = self.suggestion(u"T", u"o", u"T", u"o", 0, halfkern=-90, contour=-70)
        d = self.window([av, to])
        d.fill_table()
        d.tree.setCurrentItem(d.tree.items[1])
        d.select()
        d.suggestions = [to, av]  # (another order)
        d.fill_table()
        self.assertEqual((d.selected, d.tree.current.texts[0]), (0, u"To"))

    def test_checks_and_double_clicks_read_the_rows_from_the_list(self):
        av = self.suggestion(u"A", u"V", u"A", u"V", 0, halfkern=-80, contour=-60)
        to = self.suggestion(u"T", u"o", u"T", u"o", 0, halfkern=-90, contour=-70)
        d = self.window([av, to])
        d.fill_table()
        d.tree.items[1].setCheckState(0, self.Qt.Unchecked)
        d.harvest_checks()
        self.assertEqual([av.checked, to.checked], [True, False])
        self.assertTrue(d.row_checked(0))
        self.assertFalse(d.row_checked(1))
        self.assertFalse(d.row_checked(5), "no such row")
        d.check_all(False)
        self.assertEqual([item.state for item in d.tree.items], [self.Qt.Unchecked] * 2)
        opened, chosen = [], []
        d.show_in_glyph_window = lambda: opened.append(d.selected)
        d.choose = lambda key: chosen.append((d.selected, key))
        d.reset = lambda: chosen.append((d.selected, "reset"))
        d.item_double_clicked(d.tree.items[1], 2)
        d.item_double_clicked(d.tree.items[0], 0)
        d.item_double_clicked(d.tree.items[1], 7)
        self.assertEqual((opened, chosen), ([0], [(1, "halfkern"), (1, "reset")]))
        d.select_row(1)
        d.toggle_check()
        self.assertEqual(d.tree.items[1].state, self.Qt.Checked, "Space checks the selected pair")
        self.assertEqual(d.names_of_row(1), [u"T", u"o"])
        self.assertEqual(d.names_of_row(None), [])


class PairLinkTests(unittest.TestCase):
    def test_the_pairs_written_are_named_drawn_and_clickable(self):
        # The owner: "Auto kerning seems to never be in a situation where it'd display the list of characters"
        text = ak.pair_links([(u"A", u"V"), (u"T", u"o")])
        self.assertEqual(text, u'<a href="glyphname:A">A</a><a href="glyphname:V">V</a>, '
                               u'<a href="glyphname:T">T</a><a href="glyphname:o">o</a>')
        self.assertEqual([ak.linked_glyph_name(m) for m in re.findall(u'href="([^"]+)"', text)], [u"A", u"V", u"T", u"o"])
        self.assertEqual(ak.LOG_PAIRS_SHOWN, 12)
        with io.open(ak.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(u"self.log.follow(lambda: (self.fontlab, self.package, self.master))", source.split(u"class AutoKerningDialog")[1])


class CountedSuffixTests(unittest.TestCase):
    """A spin box's word follows its number: "1 unit", "2 units"."""

    class Spin(object):
        def __init__(self, value=0, double=False):
            self.value, self.double, self.suffix, self.slots = value, double, None, {}

        def inherits(self, name):
            return name == ("QDoubleSpinBox" if self.double else "QSpinBox")

        def setSuffix(self, text):
            self.suffix = text

        def connect(self, signal, slot):
            self.slots.setdefault(signal, []).append(slot)

        def set(self, value):
            self.value = value
            for slots in self.slots.values():
                for slot in slots:
                    slot(value)
            return self.suffix

    def test_set_now_and_at_every_change(self):
        spin = self.Spin(1)
        slot = ak.counted_suffix(spin, u"unit")
        self.assertEqual(spin.suffix, u" unit", "set as the box is made")
        self.assertEqual(list(spin.slots), ["valueChanged(int)"])
        self.assertEqual([spin.set(n) for n in (0, 1, 2, -1, 1)], [u" units", u" unit", u" units", u" units", u" unit"])
        self.assertIn(slot, sys._freelab_suffix_slots, "held: PythonQt drops a slot no Python object holds")

    def test_a_plural_of_its_own_and_a_double_box(self):
        spin = self.Spin(2, double=True)
        ak.counted_suffix(spin, u"entry", u"entries")
        self.assertEqual(list(spin.slots), ["valueChanged(double)"])
        self.assertEqual([spin.suffix, spin.set(1.0), spin.set(1.5)], [u" entries", u" entry", u" entries"])

    def test_a_value_read_through_a_method(self):
        spin = self.Spin(1)
        spin.value = lambda: 1  # (some builds give a property as a method)
        ak.counted_suffix(spin, u"glyph")
        self.assertEqual(spin.suffix, u" glyph")

    def test_a_box_that_fails_does_not_raise(self):
        spin = self.Spin(1)
        spin.setSuffix = lambda text: 1 // 0
        spin.connect = lambda signal, slot: 1 // 0
        slot = ak.counted_suffix(spin, u"unit")
        slot(3)  # a signal's handler must not raise

    def test_the_slots_of_closed_windows_are_let_go(self):
        for _ in range(300):
            ak.counted_suffix(self.Spin(1), u"unit")
        self.assertEqual(len(sys._freelab_suffix_slots), 256)


class CountedTextTests(unittest.TestCase):
    """Texts with a number follow it, at 0, 1, and 2."""

    def test_a_member_one_unit_looser(self):
        k = ak.FontKerning(FakeKerning({}, {}))
        plan = ak.ClassPlan("first", [u"e", u"E"], {u"e": "e", u"E": "eacute"}, k, [(u"E", 1, u"T"), (u"E", -2, u"V")])
        self.assertEqual(plan.describe_differs(), u"ET 1 unit looser than eT; EV 2 units tighter than eV")
        self.assertEqual(plan.describe(), u"New class kern1_e: e E (may need pairs of their own: %s)" % plan.describe_differs())

    def test_no_dash_or_dot_between_data_and_no_period_on_a_label(self):
        # The owner's rules: data beside data in parentheses (no interpunct, no em dash); short labels and
        # cell notes without a period; a spin box's word through counted_suffix
        import re
        escaped = [u" \\" + code + u" " for code in (u"N{EM DASH}", u"N{MIDDLE DOT}", u"u2014", u"u00b7", u"xb7")]
        for module in (ak, kc):
            with io.open(module.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
                source = handle.read()
            for mark in escaped + [u" \N{EM DASH} ", u" \N{MIDDLE DOT} "]:
                self.assertNotIn(mark, source)
            # (a tick's caption that is a sentence ends with a period: owner's image 324)
            self.assertEqual(re.findall(u"QCheckBox\\(u?\"[^\"]*[^.]\"\\)", source), [])
            self.assertNotIn(u"setSuffix(\"", source)
            self.assertNotIn(u"%d units ", source)
        self.assertEqual([text for text in ak.CHECK_BUTTON_TEXTS + ak.CLASS_COLUMNS if text.endswith(u".")], [])

    def test_counted(self):
        self.assertEqual([ak.counted(n, u"pair") for n in (0, 1, 2)], [u"0 pairs", u"1 pair", u"2 pairs"])
        self.assertEqual([ak.counted(n, u"entry", u"entries") for n in (0, 1, 2)], [u"0 entries", u"1 entry", u"2 entries"])


ARMENIAN_VO, ARMENIAN_SMALL_VO =u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}"
GEORGIAN_IN, MTAVRULI_IN = u"\N{GEORGIAN LETTER IN}", ak.unichr_(0x1C98)  # (Python 2.7 has no Mtavruli names)
KANA_RO, KANA_NO, KANA_I = u"\N{KATAKANA LETTER RO}", u"\N{HIRAGANA LETTER NO}", u"\N{HIRAGANA LETTER I}"
HEBREW_BET, HEBREW_YOD = u"\N{HEBREW LETTER BET}", u"\N{HEBREW LETTER YOD}"
CYRILLIC_EN, GREEK_ETA, DEVANAGARI_NA = (u"\N{CYRILLIC CAPITAL LETTER EN}", u"\N{GREEK CAPITAL LETTER ETA}",
                                         u"\N{DEVANAGARI LETTER NA}")


class ScriptTests(unittest.TestCase):
    def test_kinds_of_the_other_scripts(self):
        self.assertEqual(ak.category(ARMENIAN_VO), "upper")
        self.assertEqual(ak.category(ARMENIAN_SMALL_VO), "lower")
        self.assertEqual(ak.category(MTAVRULI_IN), "upper", "Mtavruli: Georgian's capitals")
        self.assertEqual(ak.category(GEORGIAN_IN), "lower", "Mkhedruli")
        for ch in (KANA_RO, u"\N{HIRAGANA LETTER SMALL TU}", u"\N{KATAKANA-HIRAGANA PROLONGED SOUND MARK}"):
            self.assertEqual(ak.category(ch), "kana", "small kana and the long vowel mark are kana too")
        self.assertEqual(ak.category(u"\N{IDEOGRAPHIC FULL STOP}"), "punctuation")
        self.assertEqual(ak.category(u"\N{ARMENIAN FULL STOP}"), "punctuation")
        self.assertEqual(ak.pair_kinds(KANA_NO, u"\N{IDEOGRAPHIC COMMA}"), ("kana", "kana"), "punctuation beside a kana: the kana's band")
        self.assertIsNone(ak.pair_kinds(u"\N{IDEOGRAPHIC COMMA}", u"\N{LEFT CORNER BRACKET}"))

    def test_kinds_of_cyrillic_greek_and_devanagari(self):
        self.assertEqual(ak.category(CYRILLIC_EN), "upper")
        self.assertEqual(ak.category(u"\N{CYRILLIC SMALL LETTER GHE WITH UPTURN}"), "lower", "Ukrainian's ghe")
        self.assertEqual(ak.category(u"\N{CYRILLIC CAPITAL LETTER IO}"), "upper")
        self.assertEqual(ak.category(u"\N{GREEK CAPITAL LETTER ALPHA WITH TONOS}"), "upper")
        self.assertEqual(ak.category(u"\N{GREEK SMALL LETTER FINAL SIGMA}"), "lower")
        self.assertEqual(ak.category(DEVANAGARI_NA), "lower", "one case, held to the lowercase band")
        self.assertEqual(ak.category(u"\N{DEVANAGARI DANDA}"), "punctuation")
        self.assertEqual([ak.script_of(ch) for ch in (CYRILLIC_EN, GREEK_ETA, DEVANAGARI_NA, u"\N{DEVANAGARI VOWEL SIGN AA}",
                                                      u"\N{CYRILLIC SMALL LETTER IE WITH GRAVE}", u"\N{CYRILLIC SMALL LETTER SCHWA}")],
                         ["cyrillic", "greek", "devanagari", None, None, None],
                         "vowel signs, grave-accented and Kazakh letters are not measured")
        self.assertEqual(len(ak.CYRILLIC_LETTERS), 2 * 47, "Russian, Ukrainian, Belarusian, Bulgarian, Serbian, Macedonian")
        self.assertEqual(len(ak.GREEK_CAPITALS), 33)
        self.assertEqual(len(ak.DEVANAGARI_LETTERS), 53)
        self.assertIn(u"\N{DOUBLE LOW-9 QUOTATION MARK}", ak.script_characters("cyrillic"))
        self.assertIn(u"\N{DEVANAGARI DOUBLE DANDA}", ak.script_characters("devanagari"))
        self.assertNotIn(u"0", ak.script_characters("greek"), "figures are Latin's")
        self.assertEqual(ak.font_scripts(ak.LETTERS + ak.CYRILLIC_LETTERS + ak.GREEK_LETTERS), ["latin", "cyrillic", "greek"])
        self.assertEqual(ak.font_scripts(ak.CYRILLIC_LETTERS.replace(u"\N{CYRILLIC SMALL LETTER PE}", u"")), [],
                         "Cyrillic without pe, a tuning letter: not measured")

    def test_right_to_left_pairs_are_kept_as_on_screen_and_typed_in_text_order(self):
        # On screen, bet stands left of yod in "yod bet" as typed: Auto Kerning keeps (bet, yod)
        self.assertTrue(ak.is_rtl_pair(HEBREW_BET, HEBREW_YOD))
        self.assertTrue(ak.is_rtl_pair(u".", HEBREW_YOD), "a mark of punctuation takes its partner's direction")
        self.assertFalse(ak.is_rtl_pair(u"A", u"V"))
        self.assertEqual(ak.text_order(HEBREW_BET, HEBREW_YOD), HEBREW_YOD + HEBREW_BET)
        self.assertEqual(ak.screen_order(HEBREW_YOD + HEBREW_BET), (HEBREW_BET, HEBREW_YOD))
        self.assertEqual(ak.text_order(u"A", u"V"), u"AV", "left to right as before")
        self.assertEqual(ak.screen_order(u"AV"), (u"A", u"V"))
        # an opening parenthesis typed before yod stands at its right, drawn as ")"
        self.assertEqual(ak.text_order(HEBREW_YOD, u")"), u"(" + HEBREW_YOD)
        self.assertEqual(ak.screen_order(u"(" + HEBREW_YOD), (HEBREW_YOD, u")"))
        for left, right in ((HEBREW_BET, HEBREW_YOD), (u".", HEBREW_YOD), (HEBREW_YOD, u"]"), (u"T", u"o")):
            self.assertEqual(ak.screen_order(ak.text_order(left, right)), (left, right))
        self.assertEqual(ak.pair_label(u"T", u"o"), u"To")
        self.assertEqual(ak.pair_label(HEBREW_BET, HEBREW_YOD), HEBREW_YOD + HEBREW_BET,
                         "typed in text order: Qt sets yod, the first, at the right")
        self.assertEqual(ak.pair_label(u".", HEBREW_YOD),
                         u"\N{RIGHT-TO-LEFT EMBEDDING}" + HEBREW_YOD + u".\N{POP DIRECTIONAL FORMATTING}",
                         "with a mark, inside a right-to-left embedding: the full stop stays at the left")
        s = ak.Suggestion(HEBREW_BET, HEBREW_YOD, u"bet", u"yod", 0)
        self.assertEqual(ak.rtl_note(s, True), u"Read right to left: yod first, at the right. ")
        # FontLab 7 keeps a right-to-left pair in text order (Noto Sans Hebrew: typed yod then bet, -64,
        # is FontLab's pair (yod, bet)): bet left of yod is read from and written to the key (yod, bet)
        self.assertEqual(s.key, (u"yod", u"bet"))
        self.assertEqual(ak.Suggestion(u"T", u"o", u"T", u"o", 0).key, (u"T", u"o"))
        self.assertEqual(ak.screen_of_key(HEBREW_YOD, HEBREW_BET, u"yod", u"bet"), (u"bet", u"yod"))
        self.assertEqual(ak.screen_of_key(HEBREW_YOD, None, u"yod", u"bet.alt"), (u"bet.alt", u"yod"),
                         "an unencoded glyph takes its partner's direction")
        self.assertEqual(ak.screen_of_key(u"T", u"o", u"T", u"o"), (u"T", u"o"))
        self.assertEqual(ak.screen_of_key(None, None, u"a.sc", u"b.sc"), (u"a.sc", u"b.sc"))
        for left, right in ((HEBREW_BET, HEBREW_YOD), (HEBREW_YOD, u"."), (u"T", u"o")):
            key = ak.kerning_key(left, right, left, right)
            self.assertEqual(ak.screen_of_key(key[0], key[1], key[0], key[1]), (left, right))

    def test_every_right_to_left_script_is_read_right_to_left_by_table(self):
        # Kerning Check and Font Compare read any font's keys: an Arabic, Syriac, or Adlam key is in text
        # order too (FontLab keeps a GPOS pair as the lookup holds it, typed order), though Auto Kerning
        # measures none of them. A table, not unicodedata: FontLab's Python knows Unicode 5.2 only
        alef, beh = u"\N{ARABIC LETTER ALEF}", u"\N{ARABIC LETTER BEH}"
        adlam = u"\U0001E900"  # (two UTF-16 code units on a narrow Python 2)
        for ch in (HEBREW_YOD, alef, u"\N{SYRIAC LETTER ALAPH}", u"\N{THAANA LETTER HAA}", u"\N{NKO LETTER A}",
                   u"\N{HEBREW PUNCTUATION MAQAF}", adlam):
            self.assertTrue(ak.is_rtl_char(ch), repr(ch))
        for ch in (u"A", u".", u"0", u"\N{ARABIC-INDIC DIGIT ONE}", u"\N{EXTENDED ARABIC-INDIC DIGIT ONE}",
                   u"\N{MONGOLIAN LETTER A}", u"\N{OGHAM LETTER BEITH}", u"\N{HIRAGANA LETTER A}", u"", None):
            self.assertFalse(ak.is_rtl_char(ch), repr(ch))
        self.assertEqual(ak.code_of_char(adlam), 0x1E900)
        self.assertEqual(ak.screen_of_key(beh, alef, u"beh", u"alef"), (u"alef", u"beh"))
        self.assertTrue(ak.is_rtl_pair(alef, beh))
        self.assertFalse(ak.is_rtl_pair(u"\N{ARABIC-INDIC DIGIT ONE}", u"\N{ARABIC-INDIC DIGIT TWO}"),
                         "numbers run left to right in right-to-left text")
        self.assertFalse(ak.is_rtl_pair(u"T", HEBREW_YOD), "a pair takes its first letter's script, as before")
        for left, right in ((alef, beh), (u".", alef)):
            key = ak.kerning_key(left, right, left, right)
            self.assertEqual(ak.screen_of_key(key[0], key[1], key[0], key[1]), (left, right))

    def test_a_multi_script_font_reads_each_key_by_its_own_glyphs(self):
        # One font with Latin, Hebrew, and Arabic: every key is read in its own direction, an unencoded
        # contextual form (uni0628.fina, yod.alt) by its base glyph's character, never by the font's script
        codes = {u"T": 0x54, u"o": 0x6F, u"yod": 0x05D9, u"bet": 0x05D1, u"uni0628": 0x0628, u"uni0627": 0x0627}

        class Glyph(object):
            def __init__(self, code):
                self.fgGlyph = type("FgGlyph", (object,), {"unicode": code})()

        class Package(object):
            def findName(self, name):
                return Glyph(codes[name]) if name in codes else (Glyph(0) if u"." in name else None)

        package = Package()
        self.assertEqual(ak.direction_char(package, u"uni0628.fina"), u"\N{ARABIC LETTER BEH}")
        self.assertEqual(ak.direction_char(package, u"yod.alt"), HEBREW_YOD)
        self.assertIsNone(ak.direction_char(package, u"a.sc"))
        chars = {}
        self.assertEqual(kc.screen_pair(ak, package, u"uni0628.fina", u"uni0627.fina", chars),
                         (u"uni0627.fina", u"uni0628.fina"), "two contextual forms: right to left")
        self.assertEqual(kc.screen_pair(ak, package, u"yod.alt", u"bet", chars), (u"bet", u"yod.alt"))
        self.assertEqual(kc.screen_pair(ak, package, u"T", u"o", chars), (u"T", u"o"), "the Latin key beside them")
        self.assertEqual(kc.screen_pair(ak, package, u"a.sc", u"o", chars), (u"a.sc", u"o"))

    def test_a_hebrew_pair_is_read_and_written_in_text_order(self):
        kerning = ak.FontKerning(FakeKerning({}, {((u"yod", False), (u"bet", False)): -64}))
        s = ak.Suggestion(HEBREW_BET, HEBREW_YOD, u"bet", u"yod", 0)
        self.assertEqual(kerning.current(*s.key), -64, "the font's kerning of bet left of yod")
        self.assertEqual(kerning.target(*s.key)[0], ((u"yod", False), (u"bet", False)), "written to that pair, not a reversed one")

    def test_an_entrys_first_pair_without_every_class_pair(self):
        kerning = ak.FontKerning(FakeKerning({u"T": ([u"T", u"Tcaron"], u"KernLeft"), u"o": ([u"o", u"oacute"], u"KernRight")},
                                             {((u"T", True), (u"o", True)): -80, ((u"A", False), (u"V", False)): -60}))
        for entry in kerning.entries:
            self.assertEqual(kerning.first_pair(entry), kerning.pairs(entry)[0])
        self.assertIsNone(ak.FontKerning(FakeKerning({u"e": ([], u"KernLeft")}, {((u"e", True), (u"x", False)): 5}))
                          .first_pair(((u"e", True), (u"x", False))), "an empty class")
        self.assertEqual(ak.rtl_note(ak.Suggestion(u"T", u"o", u"T", u"o", 0)), u"")

    def test_hebrew_and_thaana(self):
        self.assertEqual(len(ak.HEBREW_LETTERS), 27, "the five final forms included")
        self.assertEqual(ak.category(HEBREW_BET), "lower")
        self.assertEqual(ak.category(u"\N{THAANA LETTER RAA}"), "lower")
        self.assertEqual(ak.category(u"\N{HEBREW PUNCTUATION MAQAF}"), "punctuation")
        self.assertIsNone(ak.script_of(u"\N{HEBREW POINT QAMATS}"), "points are marks, not measured")
        self.assertIsNone(ak.script_of(u"\N{THAANA ABAFILI}"), "nor the fili")
        self.assertEqual(ak.script_of(u"\N{THAANA LETTER NOONU}"), "thaana")
        self.assertEqual(ak.font_scripts(ak.LETTERS + ak.HEBREW_LETTERS), ["latin", "hebrew"])
        self.assertEqual(ak.kind_character(u"\N{HEBREW LETTER LAMED}"), u"\N{HEBREW LETTER HE}")
        self.assertEqual(set(ak.RTL_SCRIPTS), set(["hebrew", "thaana"]))
        self.assertTrue(all(script in dict(ak.SCRIPTS) for script in ak.RTL_SCRIPTS))
        self.assertEqual(ak.MIRRORED[u"("], u")")

    def test_cyrillic_greek_and_devanagari_letters_take_their_controls(self):
        self.assertEqual(ak.kind_character(u"\N{CYRILLIC SMALL LETTER ZHE}"), u"\N{CYRILLIC SMALL LETTER EN}")
        self.assertEqual(ak.kind_character(u"\N{CYRILLIC CAPITAL LETTER ZHE}"), CYRILLIC_EN)
        self.assertEqual(ak.kind_character(u"\N{GREEK CAPITAL LETTER LAMDA}"), GREEK_ETA)
        self.assertEqual(ak.kind_character(u"\N{GREEK SMALL LETTER LAMDA}"), u"\N{GREEK SMALL LETTER ETA}")
        self.assertEqual(ak.kind_character(u"\N{DEVANAGARI LETTER KA}"), DEVANAGARI_NA)
        self.assertEqual(ak.SCRIPT_SIDE["cyrillic"], CYRILLIC_EN)

    def test_script_of_a_character(self):
        self.assertEqual([ak.script_of(ch) for ch in (u"a", u"7", ARMENIAN_VO, MTAVRULI_IN, GEORGIAN_IN, KANA_RO, u".", u"\N{CJK UNIFIED IDEOGRAPH-4E00}")],
                         ["latin", "latin", "armenian", "georgian", "georgian", "kana", None, None])

    def test_a_scripts_characters(self):
        self.assertIn(u"7", ak.script_characters("latin"))
        self.assertNotIn(u"7", ak.script_characters("armenian"), "figures are Latin's")
        self.assertIn(u"\N{ARMENIAN COMMA}", ak.script_characters("armenian"))
        self.assertIn(u"\N{IDEOGRAPHIC FULL STOP}", ak.script_characters("kana"))
        self.assertEqual(len(ak.MTAVRULI), 46)

    def test_the_scripts_a_font_has(self):
        latin = ak.LETTERS
        self.assertEqual(ak.font_scripts(latin + ak.KANA_LETTERS + ak.ARMENIAN_LETTERS), ["latin", "kana", "armenian"])
        self.assertEqual(ak.font_scripts(latin + ak.KANA_LETTERS.replace(KANA_RO, u"")), ["latin"], "kana without RO: not measured")
        self.assertEqual(ak.font_scripts(u"lno" + ak.GEORGIAN_LETTERS[:12]), [], "too few letters of either")
        mkhedruli = ak.GEORGIAN_LETTERS.replace(MTAVRULI_IN, u"")
        self.assertEqual(ak.font_scripts(mkhedruli), ["georgian"], "Mtavruli are not needed")

    def test_palt_rules_are_read_from_feature_code(self):
        prefix = u"@narrow = [a-hira i-hira];\n"
        code = (u"feature palt {\n# Proportional Alternate Widths\n"
                u"# >>> FreeLab palt (made by FreeLab CJK Spacing)\n"
                u"  pos ka-kata <-70 0 -130 0>;\n"
                u"  pos ka-kata <-10 0 -20 0>;  # a second rule: the first wins\n"
                u"  pos @narrow <-50 0 -100 0>;\n"
                u"  pos [u-hira @local] -80;\n"
                u"  pos ka-kata ki-kata -20;  # a pair: not palt's single adjustment\n"
                u"  @local = [e-hira];\n"
                u"# <<< FreeLab palt\n} palt;\n")
        self.assertEqual(ak.palt_adjustments(code, prefix),
                         {"ka-kata": (-70, -130), "a-hira": (-50, -100), "i-hira": (-50, -100), "u-hira": (0, -80),
                          "e-hira": (0, -80)})
        self.assertEqual(ak.palt_adjustments(u"", u""), {})
        self.assertEqual(ak.palt_adjustments(None), {})

    def test_how_the_kana_are_set(self):
        upm = 1000.0
        full = {"a": 1000, "i": 1000, "u": 1000}
        self.assertIsNone(ak.kana_setting(full, upm, {}), "full width and no palt: not kerned")
        self.assertEqual(ak.kana_setting(full, upm, {"a": (-80, -150), "i": (-60, -120)}), "palt")
        self.assertIsNone(ak.kana_setting(full, upm, {"a": (-80, -150)}), "palt narrows too few of them")
        self.assertEqual(ak.kana_setting(full, upm, {"a": (-20, -40), "i": (-30, -50), "u": (0, 0)}), "palt",
                         "a light palt (Source Han's leaves many kana wider than 90% of the em)")
        self.assertEqual(ak.kana_setting({"a": 760, "i": 820, "u": 1000}, upm, {}), "proportional")
        self.assertIsNone(ak.kana_setting({}, upm, {}))

    @unittest.skipIf(not os.path.isfile(os.path.join(HERE, os.pardir, "kerning", ak.SCRIPT_PAIRS_FILE)),
                     "kerning/script_pairs.txt not copied beside the script (run_tests.py's Python 2.7 files)")
    def test_common_pairs_add_the_other_scripts_after_latin(self):
        latin =ak.common_pairs(os.path.join(HERE, os.pardir, "kerning", ak.COMMON_PAIRS_FILE))
        every = ak.common_pairs()
        self.assertTrue(all(every[pair] == rank for pair, rank in latin.items()), "Latin's ranks unchanged")
        others = [pair for pair in every if pair not in latin]
        self.assertGreater(len(others), 3000)
        self.assertTrue(all(every[pair] >= len(latin) for pair in others))
        scripts = set(ak.script_of(ch) for pair in others for ch in pair) - set([None])
        self.assertEqual(scripts, set(["kana", "armenian", "georgian", "cyrillic", "greek", "devanagari", "hebrew", "thaana"]))
        self.assertIn(HEBREW_YOD + u"\N{HEBREW LETTER FINAL MEM}", every, "Hebrew's -im, in text order")
        self.assertNotIn(u"\N{HEBREW LETTER FINAL MEM}" + HEBREW_YOD, every, "(not as on screen)")
        self.assertIn(u"\N{CYRILLIC SMALL LETTER EN}\N{CYRILLIC SMALL LETTER A}", every, "Russian's na")
        self.assertIn(u"\N{GREEK CAPITAL LETTER TAU}\N{GREEK CAPITAL LETTER OMICRON}", every, "all-capital Greek")
        self.assertIn(u"\N{DEVANAGARI LETTER KA}\N{DEVANAGARI LETTER RA}", every, "Hindi's kar")
        self.assertTrue(any(ak.script_of(pair[0]) == "cyrillic" and pair[1] in u".," for pair in others),
                        "Cyrillic pairs with punctuation, from running text")
        self.assertIn(u"\N{HIRAGANA LETTER SMALL TU}\N{HIRAGANA LETTER TE}", every, "a pair of a small kana")
        self.assertIn(u"\N{ARMENIAN SMALL LETTER VO}\N{ARMENIAN SMALL LETTER YIWN}", every, "Armenian's ou")
        self.assertTrue(any(ak.category(pair[0]) == "upper" for pair in others if ak.script_of(pair[0]) == "georgian"),
                        "Mtavruli pairs, for all-capital text")

    def test_a_scripts_pairs(self):
        pairs = [KANA_RO + KANA_NO, KANA_NO + u"\N{IDEOGRAPHIC FULL STOP}", u"To", KANA_RO + u"o", u".,",
                 ARMENIAN_SMALL_VO + u","]
        self.assertEqual(ak.script_pairs(pairs, "kana"), set([KANA_RO + KANA_NO, KANA_NO + u"\N{IDEOGRAPHIC FULL STOP}"]),
                         "kana beside a mark, not beside a Latin letter")
        self.assertEqual(ak.script_pairs(pairs, "armenian"), set([ARMENIAN_SMALL_VO + u","]))

    def test_each_script_has_a_cache_of_its_own(self):
        self.assertEqual(ak.cache_path(u"font.vfc", u"Regular"), ak.cache_path(u"font.vfc", u"Regular", "latin"),
                         "Latin's cache is where it was")
        self.assertNotEqual(ak.cache_path(u"font.vfc", u"Regular"), ak.cache_path(u"font.vfc", u"Regular", "kana"))
        self.assertEqual(ak.method_fingerprint(None), ak.method_fingerprint(None, "latin"))
        self.assertNotEqual(ak.method_fingerprint(None), ak.method_fingerprint(None, "armenian"))

    def test_the_learned_model_is_used_for_its_scripts_only(self):
        self.assertEqual(ak.learned_scripts(None), ["latin"])
        self.assertEqual(ak.learned_scripts({"info": {"trained": "2026-11-10"}}), ["latin"], "an older model: Latin's")
        self.assertEqual(ak.learned_scripts({"info": {"scripts": ["latin", "armenian"]}}), ["latin", "armenian"])
        self.assertNotIn("kana", ak.learned_scripts(ak.learned_model()), "no kana model: too few fonts kern kana")
        if ak.learned_model() is None:
            return  # (learned_model.json is not copied beside the script for run_tests.py's Python 2.7 files)
        for script in ("latin", "cyrillic", "greek", "armenian", "georgian", "devanagari"):
            self.assertIn(script, ak.learned_scripts(ak.learned_model()), "held out, it beat the default in " + script)
        for script in ("hebrew", "thaana"):
            self.assertNotIn(script, ak.learned_scripts(ak.learned_model()), "not closer on the pairs Hebrew fonts kern; "
                                                                               "Thaana: one design")
        self.assertEqual(sorted(ak.learned_model()["info"]["trained on"]),
                         ["armenian", "cyrillic", "devanagari", "georgian", "greek", "latin"])

    def test_a_letter_takes_its_scripts_references(self):
        self.assertEqual(ak.kind_character(u"\N{ARMENIAN SMALL LETTER BEN}"), ARMENIAN_SMALL_VO)
        self.assertEqual(ak.kind_character(u"\N{ARMENIAN CAPITAL LETTER BEN}"), ARMENIAN_VO)
        self.assertEqual(ak.kind_character(ak.unichr_(0x1C91)), MTAVRULI_IN, "Mtavruli ban: Mtavruli in")
        self.assertEqual(ak.kind_character(u"\N{GEORGIAN LETTER BAN}"), GEORGIAN_IN)
        self.assertEqual(ak.kind_character(u"\N{HIRAGANA LETTER GA}"), KANA_RO)
        self.assertEqual(ak.kind_character(u"\N{LATIN SMALL LETTER O WITH STROKE}"), u"n", "Latin as before")

    def test_the_references_of_each_script_are_its_own_letters(self):
        for script, _ in ak.SCRIPTS:
            letters = ak.SCRIPT_LETTERS[script] + (ak.FIGURES if script == "latin" else u"")
            for chars in list(ak.SCRIPT_REFERENCES[script].values()) + [ak.SCRIPT_TUNING[script], ak.SCRIPT_CONTROLS[script]]:
                self.assertTrue(all(ch in letters for ch in chars), script)
            self.assertIn(ak.SCRIPT_SIDE[script], letters)


class AllScriptsTests(unittest.TestCase):
    def test_all_scripts_is_offered_for_two_scripts_or_more(self):
        self.assertEqual(ak.script_choices(["latin", "kana"]), ["latin", "kana", ak.ALL_SCRIPTS])
        self.assertEqual(ak.script_choices(["latin"]), ["latin"])
        self.assertEqual(ak.script_choices([]), ["latin"])
        self.assertEqual(ak.script_label(ak.ALL_SCRIPTS), u"All scripts")
        self.assertEqual(ak.script_label("armenian"), u"Armenian")

    def test_a_pairs_script(self):
        self.assertEqual(ak.pair_script(KANA_NO, u"\N{IDEOGRAPHIC FULL STOP}"), "kana")
        self.assertEqual(ak.pair_script(u",", ARMENIAN_SMALL_VO), "armenian", "a mark takes its partner's")
        self.assertEqual(ak.pair_script(u".", u","), "latin")

    def test_each_scripts_analysis_merged_into_one_list(self):
        def suggestion(left, right, raw):
            s = ak.Suggestion(left, right, left, right, 0)
            s.raw["halfkern"] = raw
            return s
        latin = ak.Analysis([suggestion(u"T", u"o", -80), suggestion(u"V", u"a", -60)],
                            {"halfkern": (0.5, 1.0)}, (None, None), measured=2)
        kana = ak.Analysis([suggestion(KANA_RO, KANA_NO, -40)], {"halfkern": (0.8, 1.0)}, (None, None), measured=1, reused=4)
        merged = ak.MergedAnalysis([("latin", latin), ("kana", kana)])
        self.assertEqual([(s.left, s.script) for s in merged.suggestions], [(u"T", "latin"), (u"V", "latin"), (KANA_RO, "kana")])
        self.assertEqual((merged.measured, merged.reused), (3, 4))
        self.assertEqual(ak.factors_of(merged, "kana"), {"halfkern": (0.8, 1.0)}, "each script keeps its own factors")
        self.assertEqual(ak.factors_of(latin, "kana"), {"halfkern": (0.5, 1.0)}, "one script's analysis: its factors")
        self.assertEqual(ak.factor_summary(merged), [u"halfkern tightens at 50% in Latin, 80% (from the font's kerning) in Kana"])
        self.assertEqual(ak.factor_summary(latin), [u"halfkern tightens at 50%"])
        same = ak.MergedAnalysis([("latin", latin), ("kana", ak.Analysis([suggestion(KANA_RO, KANA_I, -10)],
                                                                         {"halfkern": (0.5, 1.0)}, (None, None)))])
        self.assertEqual(ak.factor_summary(same), [u"halfkern tightens at 50%"], "alike in every script: said once")


class ScriptProofTests(unittest.TestCase):
    def test_kana_armenian_and_georgian_are_proofed_between_their_own_letters(self):
        names = [("ro", 0x30ED), ("no", 0x306E), ("i", 0x3044), ("ka", 0x30AB), ("Vo", 0x548), ("vo", 0x578),
                 ("oh", 0x585), ("ben", 0x562), ("in", 0x10D8), ("on", 0x10DD), ("ban", 0x10D1), ("H", 0x48), ("n", 0x6E), ("o", 0x6F)]
        package = ProofTests.Package(names)
        self.assertEqual(ak.proof_contexts(package, ["ka", "no"]), ["ro", "no", "i"])
        self.assertEqual(ak.proof_contexts(package, ["ben", "vo"]), ["Vo", "vo", "oh"])
        self.assertEqual(ak.proof_contexts(package, ["ban", "in"]), ["in", "on"], "no Mtavruli in this font: Mkhedruli's")


@unittest.skipIf(CORE is None, "auto kerning core not built: run tools/build-native.ps1 -Kern (%s)" % ak.kern_library_path())
class ScriptBandTests(unittest.TestCase):
    def test_a_loose_third_tuning_letter_is_left_out_of_the_halo(self):
        # in and on agree; san is spaced so loosely that no halo within reach makes it agree with them:
        # the halo is in and on's, grown until san's envelopes meet too (every reference pair overlaps)
        glyphs = {GEORGIAN_IN: stem("in"), u"\N{GEORGIAN LETTER ON}": stem("on"),
                  u"\N{GEORGIAN LETTER SAN}": stem("san", left_bearing=20, right_bearing=20)}
        tools = ak.make_bands(CORE, glyphs.get, glyphs, 100, PAD, "georgian")
        self.assertGreater(tools["bias"], ak.calibrate(CORE, [stem("in"), stem("on")], 100).bias)
        self.assertLess(tools["bias"], PAD)
        self.assertGreater(tools["halo"][("lower", "lower")].low, 0, "every reference pair overlaps")
        latin = {u"l": stem("l"), u"n": stem("n"), u"o": stem("o", left_bearing=60, right_bearing=60)}
        self.assertRaises(ValueError, ak.make_bands, CORE, latin.get, latin, 100, PAD)

    def test_kana_are_measured_by_their_own_band(self):
        glyphs = {KANA_RO: stem("ro"), KANA_NO: stem("no", left_bearing=12, right_bearing=12), KANA_I: stem("i")}
        tools = ak.make_bands(CORE, glyphs.get, glyphs, 100, PAD, "kana")
        self.assertEqual(sorted(tools["halo"]), [("kana", "kana")])
        loose = stem("ku", left_bearing=30, right_bearing=30)
        halo, contour = ak.measure_pair(tools, u"\N{KATAKANA LETTER KU}", KANA_RO, loose, stem("ro"), 100, float(PAD))
        self.assertLess(halo, 0, "a kana spaced looser than the references tightens")
        self.assertLess(contour, 0)
        halo, contour = ak.measure_pair(tools, KANA_RO, KANA_I, stem("ro"), stem("i"), 100, float(PAD))
        self.assertEqual(halo, 0.0, "spaced as the references: left alone")


GATE_FILE = os.path.join(HERE, os.pardir, "kerning", "train", "gate.py")


@unittest.skipUnless(os.path.isfile(GATE_FILE), "the training scripts are not in the Python 2.7 copy")
class LearnedGateTests(unittest.TestCase):
    """kerning/train/gate.py: where train.py --export lets the learned method be offered."""

    def setUp(self):
        sys.path.insert(0, os.path.dirname(GATE_FILE))
        try:
            import gate
        finally:
            sys.path.pop(0)
        self.gate = gate

    @staticmethod
    def summary(zero, average, learned, halfkern=(99, 99), contour=(99, 99)):
        scored = {"zero": zero, "average": average, "learned": learned, "halfkern": halfkern, "contour": contour}
        return dict((method, {"mae": all_pairs, "mae kerned": kerned}) for method, (all_pairs, kerned) in scored.items())

    def test_beating_no_kerning_is_a_switch_left_off(self):
        # Devanagari as scored on 2026-11-14: closer than the default, but not than leaving the pairs alone
        self.assertFalse(self.gate.BEAT_NO_KERNING, "the owner's decision, pending: the suggestion stays in Devanagari")
        devanagari = self.summary((4.0, 25.7), (12.2, 36.9), (4.8, 26.0))
        self.assertEqual(self.gate.reasons("devanagari", devanagari, 11), [])
        self.assertEqual(self.gate.reasons("devanagari", devanagari, 11, beat_no_kerning=True),
                         ["mae kerned 26.0 not below no kerning's 25.7"])
        self.assertEqual(self.gate.refused(["devanagari"], {"devanagari": devanagari}, {"devanagari": 11}, True),
                         {"devanagari": ["mae kerned 26.0 not below no kerning's 25.7"]})
        greek = self.summary((5.0, 31.1), (8.1, 20.5), (5.1, 17.1))
        self.assertEqual(self.gate.reasons("greek", greek, 60, beat_no_kerning=True), [],
                         "no kerning is never asked to be beaten over all pairs")

    def test_another_script_must_beat_the_default_on_both_measures(self):
        hebrew = self.summary((4.0, 36.4), (8.9, 26.6), (5.8, 28.3))
        self.assertEqual(self.gate.reasons("hebrew", hebrew, 19), ["mae kerned 28.3 not below the default's 26.6"])
        kana = self.summary((4.1, 41.8), (3.0, 26.6), (4.3, 41.8))
        self.assertEqual(len(self.gate.reasons("kana", kana, 8)), 2)
        self.assertEqual(len(self.gate.reasons("kana", kana, 8, beat_no_kerning=True)), 3)

    def test_another_script_needs_two_designs(self):
        thaana = self.summary((2.3, 30.9), (5.4, 30.2), (3.7, 26.0))
        self.assertEqual(self.gate.reasons("thaana", thaana, 1), ["1 design scored, 2 needed"])
        self.assertEqual(self.gate.reasons("thaana", thaana, 2), [])

    def test_latin_must_beat_every_method(self):
        latin = self.summary((9.4, 38.4), (22.0, 24.8), (8.5, 21.4), (17.4, 22.4), (27.3, 31.6))
        self.assertEqual(self.gate.reasons("latin", latin, 1), [], "Latin is not held to the design count")
        self.assertEqual(self.gate.reasons("latin", self.summary((8.0, 38.4), (22.0, 24.8), (8.5, 21.4)), 234),
                         ["mae 8.5 not below zero's"])
        self.assertEqual(self.gate.refused(["latin", "thaana", "mongolian"], {"latin": latin, "thaana": self.summary(
            (2.3, 30.9), (5.4, 30.2), (3.7, 26.0))}, {"latin": 234, "thaana": 1}),
            {"thaana": ["1 design scored, 2 needed"], "mongolian": ["not scored"]})


@unittest.skipIf(sys.version_info[0] < 3, "the pairs are counted by a Python 3 training script")
class ScriptPairCountTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning", "train"))
        import script_pairs
        self.sp = script_pairs

    def test_pairs_of_letters_and_of_a_letter_and_a_mark(self):
        counts = self.sp.count_pairs([u"ab, c.. ab"], u"abc", u",.")
        self.assertEqual(dict(counts), {u"ab": 2, u"b,": 1, u"c.": 1}, "no pair across a space, none of two marks")

    def test_all_capital_pairs_follow_the_lowercase_ones(self):
        counts = self.sp.with_capitals({u"ab": 8, u"a,": 4, u"Ab": 2}, lambda ch: ch.upper() if ch in u"ab" else None)
        self.assertEqual(counts[u"AB"], 8 * self.sp.CAPITALS_SHARE)
        self.assertEqual(counts[u"A,"], 4 * self.sp.CAPITALS_SHARE)
        self.assertEqual(counts[u"Ab"], 2, "a capital already there is not counted again")
        self.assertEqual(self.sp.mtavruli(GEORGIAN_IN), MTAVRULI_IN)
        self.assertIsNone(self.sp.mtavruli(u"a"))
        self.assertIsNone(self.sp.armenian_capital(u"\N{ARMENIAN SMALL LIGATURE ECH YIWN}"), "a ligature has no one capital")

    def test_capitals_of_cyrillic_and_greek(self):
        self.assertEqual(self.sp.script_capital(u"\N{CYRILLIC SMALL LETTER ZHE}", "cyrillic"), u"\N{CYRILLIC CAPITAL LETTER ZHE}")
        self.assertEqual(self.sp.script_capital(u"\N{GREEK SMALL LETTER ALPHA WITH TONOS}", "greek"),
                         u"\N{GREEK CAPITAL LETTER ALPHA}", "all-capital Greek drops the tonos")
        self.assertEqual(self.sp.script_capital(u"\N{GREEK SMALL LETTER IOTA WITH DIALYTIKA AND TONOS}", "greek"),
                         u"\N{GREEK CAPITAL LETTER IOTA WITH DIALYTIKA}", "and keeps the dialytika")
        self.assertEqual(self.sp.script_capital(u"\N{GREEK SMALL LETTER FINAL SIGMA}", "greek"), u"\N{GREEK CAPITAL LETTER SIGMA}")
        self.assertIsNone(self.sp.script_capital(u"\N{CYRILLIC CAPITAL LETTER ZHE}", "cyrillic"), "a capital already")
        self.assertIsNone(self.sp.script_capital(DEVANAGARI_NA, "devanagari"), "one case")

    def test_word_lists_give_letter_pairs_as_often_as_their_words(self):
        counts = self.sp.word_pair_counts({u"abc": 3, u"ba": 2, u"a-b": 5}, u"abc")
        self.assertEqual(dict(counts), {u"ab": 3, u"bc": 3, u"ba": 2}, "a hyphen breaks a pair")

    def test_a_script_not_recounted_keeps_its_section(self):
        import tempfile
        handle, path = tempfile.mkstemp(suffix=".txt")
        os.close(handle)
        try:
            with io.open(path, "w", encoding="utf-8") as out:
                out.write(u"# header\n# kana: 2 pairs, from 600 works\n" + KANA_RO + KANA_NO + u"\n" + KANA_NO + KANA_I
                          + u"\n# armenian: 1 pairs, from 3 articles\n" + ARMENIAN_SMALL_VO + u",\n")
            sections = self.sp.existing_sections(path)
        finally:
            os.remove(path)
        self.assertEqual(sections, {"kana": ([KANA_RO + KANA_NO, KANA_NO + KANA_I], u"600 works"),
                                    "armenian": ([ARMENIAN_SMALL_VO + u","], u"3 articles")})
        self.assertEqual(self.sp.existing_sections(path), {}, "no file: no sections")

    def test_the_fonts_fetched_for_other_scripts_add_no_latin(self):
        try:
            import dataset
        except ImportError:  # (numpy: the training's)
            self.skipTest("numpy is not installed")
        fetched = os.path.join(dataset.CORPUS_DIR, "kerning-fonts", "ofl", "lora", "Lora[wght].ttf")
        self.assertFalse(dataset.latin_measured(fetched), "Latin's training set stays the one the model was checked on")
        self.assertFalse(dataset.latin_measured(os.path.join(dataset.CORPUS_DIR, "language-font-sources", "NotoSans.ttf")))
        self.assertTrue(dataset.latin_measured(os.path.join(dataset.CORPUS_DIR, "Lora[wght].ttf")))
        self.assertIn("cyrillic", dataset.SCRIPT_SHAPING)
        self.assertEqual(set(dataset.SCRIPT_SHAPING), set(key for key, _ in ak.SCRIPTS), "every script is read as shaped")
        hebrew = dataset.script_common_pairs("hebrew")
        self.assertIn(u"\N{HEBREW LETTER FINAL MEM}" + HEBREW_YOD, hebrew, "measured as on screen: final mem at the left")
        self.assertEqual(dataset.script_common_pairs("cyrillic")[0], u"\N{CYRILLIC SMALL LETTER EN}\N{CYRILLIC SMALL LETTER A}")

    def test_hebrew_and_thaana_pairs_are_counted_without_their_marks(self):
        self.assertEqual(self.sp.without_marks(u"\N{HEBREW LETTER SHIN}\N{HEBREW POINT QAMATS}\N{HEBREW LETTER LAMED}"),
                         u"\N{HEBREW LETTER SHIN}\N{HEBREW LETTER LAMED}")
        text = u"\N{THAANA LETTER NOONU}\N{THAANA ABAFILI}\N{THAANA LETTER RAA}\N{THAANA SUKUN}."
        counts = self.sp.count_pairs([self.sp.without_marks(text)], ak.THAANA_LETTERS, ak.THAANA_PUNCTUATION)
        self.assertEqual(dict(counts), {u"\N{THAANA LETTER NOONU}\N{THAANA LETTER RAA}": 1, u"\N{THAANA LETTER RAA}.": 1},
                         "letters under their fili stand side by side")

    def test_pairs_are_kept_until_they_cover_the_share(self):
        counts = {u"ab": 50, u"bc": 30, u"cd": 15, u"de": 5}
        self.assertEqual(self.sp.kept(counts, 0.8), [u"ab", u"bc"])
        self.assertEqual(self.sp.kept(counts, 0.81), [u"ab", u"bc", u"cd"])

    def test_aozora_texts_lose_their_ruby_notes_and_colophon(self):
        import tempfile
        import zipfile
        rule = self.sp.HEADER_RULE
        text = (u"Title\r\n" + rule + u"\r\nkey to the marks\r\n" + rule + u"\r\n"
                u"\N{CJK UNIFIED IDEOGRAPH-732B}\N{LEFT DOUBLE ANGLE BRACKET}\N{HIRAGANA LETTER NE}\N{HIRAGANA LETTER KO}"
                u"\N{RIGHT DOUBLE ANGLE BRACKET}\N{HIRAGANA LETTER DE}\N{HIRAGANA LETTER A}\N{HIRAGANA LETTER RU}"
                u"\N{FULLWIDTH LEFT SQUARE BRACKET}\N{FULLWIDTH NUMBER SIGN}note\N{FULLWIDTH RIGHT SQUARE BRACKET}"
                u"\N{IDEOGRAPHIC FULL STOP}\r\n" + self.sp.FOOTER + u"source\r\n")
        handle, path = tempfile.mkstemp(suffix=".zip")
        os.close(handle)
        try:
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("work.txt", text.encode("cp932"))
            clean = self.sp.aozora_text(path)
        finally:
            os.remove(path)
        self.assertEqual(clean.strip(), u"\N{CJK UNIFIED IDEOGRAPH-732B}\N{HIRAGANA LETTER DE}\N{HIRAGANA LETTER A}"
                                        u"\N{HIRAGANA LETTER RU}\N{IDEOGRAPHIC FULL STOP}")



class ReviewOfNov19Tests(unittest.TestCase):
    """The owner's review of Nov 19 (images 350 to 392): the shared module's part."""

    def test_head_join_puts_a_blank_line_after_the_font(self):
        self.assertEqual(ak.head_join(u"<b>Sans</b>, master <b>Regular</b>.", u"Nothing to trim."),
                         u"<b>Sans</b>, master <b>Regular</b>.<br><br>Nothing to trim.")
        self.assertEqual(ak.head_join(u"<b>Sans</b>.", u""), u"<b>Sans</b>.", "the font alone: no blank line under it")
        self.assertEqual(ak.head_join(u"", u"No font is open."), u"No font is open.")

    def test_a_compile_error_in_the_fonts_own_aalt_says_where_it_is_fixed(self):
        line, level = ak.compile_report(u"[E] \"lookup\" use not allowed in 'aalt' feature\n[F] [internal] label not found")
        self.assertEqual(level, "error")
        self.assertIn(u"the font's own <i>aalt</i>", line)
        self.assertIn(u"Feature%20Check", line, "a link that opens Feature Check")
        line, level = ak.compile_report(u"[F] glyph class not defined (text was \"@nope\")")
        self.assertNotIn(u"aalt", line)

    def test_tabs_take_the_texts_color_on_either_window(self):
        """Owner's image 352 (a light window), then the review of November 23, image 5 (a dark one): a tab not
        chosen read as grayed out in a mid gray. Every tab takes the text's color; only a disabled one is gray."""
        first = ak.TAB_SHEET.split(u"}")[0]
        self.assertIn(u"color: palette(window-text);", first)
        self.assertNotIn(u"rgba(128, 128, 128, 255)", ak.TAB_SHEET, "no mid gray for a tab that can be chosen")
        self.assertIn(u"QTabBar::tab:disabled { color: rgba(128, 128, 128, 110); }", ak.TAB_SHEET)
        self.assertIn(u"QTabBar::tab:selected { color: palette(window-text); border-bottom: 2px solid palette(highlight); }",
                      ak.TAB_SHEET, "the chosen tab told by its underline")
        self.assertEqual(ak.tab_sheet(object()), ak.TAB_SHEET, "whatever the bar's palette")
        self.assertEqual(ak.TAB_SHEET_LIGHT, ak.TAB_SHEET)
        self.assertIn(ak.PALETTE_CHANGE, ak.WATCHED_EVENTS, "dark mode switched: the sheets follow")

    def test_an_open_list_is_as_wide_as_its_longest_choice(self):
        """Live 2026-11-19 (owner's image 357 again): popup_width called view.fontMetrics(), which PythonQt does not
        have; the failure was swallowed after the choices were marked measured, and every list stayed as wide
        as its box ("Korean (no... the font)"). Measured with a QFontMetrics of the list's font."""
        class Metrics(object):
            def __init__(self, font):
                self.font = font

            def width(self, text):
                return 7 * len(text)

        class View(object):  # (as PythonQt shows a list: its font a property, no fontMetrics())
            font, minimum, elide = "font", None, None

            def setTextElideMode(self, mode):
                self.elide = mode

            def setMinimumWidth(self, width):
                self.minimum = width

        class Combo(object):
            def __init__(self, texts):
                self.texts, self.list, self.props = texts, View(), {}
                self.count = len(texts)

            def view(self):
                return self.list

            def itemText(self, k):
                return self.texts[k]

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

        QtCore = type("QtCore", (), {"Qt": type("Qt", (), {"ElideNone": 3})})
        QtGui = type("QtGui", (), {"QFontMetrics": Metrics})
        real = ak._qt
        ak._qt = lambda: (QtCore, QtGui)
        try:
            combo = Combo([u"Japanese", u"Korean (no Hangul in the font)"])
            ak.popup_width(combo)
            self.assertEqual(combo.list.minimum, 7 * len(u"Korean (no Hangul in the font)") + ak.POPUP_PAD)
            self.assertEqual(combo.list.elide, 3, "never elided")
            combo.list.minimum = None
            ak.popup_width(combo)
            self.assertIsNone(combo.list.minimum, "the same choices: not measured again")
            broken = Combo([u"A", u"B"])
            QtGui.QFontMetrics = None  # (a failure: tried again next time)
            ak.popup_width(broken)
            self.assertIsNone(broken.property(ak.POPUP_WIDTH_PROP))
            QtGui.QFontMetrics = Metrics
            ak.popup_width(broken)
            self.assertEqual(broken.list.minimum, 7 + ak.POPUP_PAD)
        finally:
            ak._qt = real

    def test_grayed_fields_show_on_a_light_window(self):
        """Live 2026-11-19 (owner's image 366): on a light window, Windows' style filled a grayed field with the
        window's color, its frame a faint line, and Feature Code's empty field beside Glyphs vanished. Light
        windows' fields take a darker gray while grayed. The review of November 23 (images 2 and 4): the usable
        background was kept from the field's palette of the theme before, so every group is set from the
        application's palette of now, and a dark window's field takes its window's palette whole again."""
        class Color(object):
            def __init__(self, value):
                self.value = value.value if isinstance(value, Color) else value

            def lightness(self):
                return self.value

            def darker(self, percent):
                return Color(int(self.value * 100 / percent))

            def __eq__(self, other):
                return isinstance(other, Color) and other.value == self.value

            def __ne__(self, other):
                return not self == other

        class Palette(object):
            Active, Inactive, Disabled, Base, Window = "active", "inactive", "disabled", "base", "window"

            def __init__(self, colors=None):
                self.colors = dict(colors.colors) if isinstance(colors, Palette) else dict(colors or {})

            def color(self, *roles):
                key = roles[-1] if len(roles) == 1 else roles
                return self.colors.get(key, Color(-1))  # (-1: nothing set, the window's own)

            def setColor(self, group, role, color):
                self.colors[(group, role)] = color

        class Widget(object):
            def __init__(self, palette, parent=None, kind="QLineEdit"):
                self.palette, self.parent, self.kind, self.props, self.set = palette, parent, kind, {}, 0

            def parentWidget(self):
                return self.parent

            def inherits(self, name):
                return name == self.kind

            def setPalette(self, palette):
                self.palette, self.set = palette, self.set + 1

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

        def theme(window, base):
            return Palette({"window": Color(window), ("active", "base"): Color(base),
                            ("inactive", "base"): Color(base), ("disabled", "base"): Color(window)})

        app = {"palette": theme(240, 255)}
        # (the fields' own palettes are the dark theme's still, as when a window hears of a switch to light)
        field, spin = Widget(theme(40, 30)), Widget(theme(40, 30), kind="QAbstractSpinBox")
        inner = Widget(theme(40, 30), parent=spin)
        dialog = type("Dialog", (), {})()
        QtGui = type("QtGui", (), {"QColor": Color, "QPalette": Palette, "QLineEdit": "QLineEdit",
                                   "QAbstractSpinBox": "QAbstractSpinBox",
                                   "QApplication": type("App", (), {"instance": staticmethod(lambda: type(
                                       "A", (), {"palette": lambda self: app["palette"]})())})})
        dialog.findChildren = lambda kind: {"QLineEdit": [field, inner], "QAbstractSpinBox": [spin]}[kind]
        real = ak._qt
        ak._qt = lambda: (None, QtGui)
        try:
            ak.light_fields(dialog)
            want = Color(240).darker(ak.LIGHT_FIELD_DARKER)
            for widget in (field, spin):
                self.assertEqual(widget.palette.color("disabled", "base"), want)
                self.assertEqual(widget.palette.color("active", "base"), Color(255),
                                 "usable, the light theme's own: never the dark one its palette still held")
                self.assertEqual(widget.palette.color("inactive", "base"), Color(255))
            self.assertEqual(inner.set, 0, "a spin box's own field is drawn by its box")
            ak.light_fields(dialog)
            self.assertEqual(field.set, 1, "set once")
            untouched = Widget(theme(40, 30))
            dialog.findChildren = lambda kind: {"QLineEdit": [field, untouched], "QAbstractSpinBox": [spin]}[kind]
            app["palette"] = theme(40, 30)  # (dark mode switched on)
            ak.light_fields(dialog)
            self.assertEqual(field.palette.colors, {}, "its window's palette whole again: nothing of the light theme kept")
            self.assertEqual(spin.palette.colors, {})
            self.assertEqual(untouched.set, 0, "a field never set here is left to dark mode")
            sets = field.set
            ak.light_fields(dialog)
            self.assertEqual(field.set, sets, "taken back once")
            app["palette"] = theme(240, 255)  # (and off again)
            ak.light_fields(dialog)
            self.assertEqual(field.palette.color("active", "base"), Color(255))
            self.assertEqual(field.palette.color("disabled", "base"), want)
        finally:
            ak._qt = real


class ReviewOfNov23Tests(unittest.TestCase):
    """The owner's review of November 23 (thirteen images): the shared module's part."""

    def test_the_help_menu_is_fontlabs_main_windows(self):
        """Image 25: "What's This?" came out without a standard menu's margin and padding. A menu takes its
        look from its parent: FontLab's main window, not the tool's; made for the click, deleted after it."""
        made = []

        class Menu(object):
            def __init__(self, parent):
                self.parent, self.deleted, self.pick = parent, False, True
                made.append(self)

            def addAction(self, text):
                self.action = type("Action", (), {"text": text})()
                return self.action

            def exec_(self, where):
                return self.action if self.pick else None

            def deleteLater(self):
                self.deleted = True

        saved = (ak._qt, ak.AutoKerningDialog.main_window)
        ak._qt = lambda: (None, type("Gui", (), {"QMenu": Menu}))
        ak.AutoKerningDialog.main_window = staticmethod(lambda: "main window")

        def restore():
            ak._qt, ak.AutoKerningDialog.main_window = saved[0], staticmethod(saved[1])
        self.addCleanup(restore)
        self.assertTrue(ak.help_menu_picked("tool window", "here"))
        self.assertEqual((made[0].parent, made[0].deleted, made[0].action.text), ("main window", True, u"What's This?"))
        ak.AutoKerningDialog.main_window = staticmethod(lambda: None)
        self.assertTrue(ak._whats_this_menu("tool window", "here"))
        self.assertEqual(made[1].parent, "tool window", "no main window found: the tool's, as before")

    def test_the_help_menu_has_a_tooltips_frame(self):
        """Images 25 and 31: a menu of one entry has no use for a menu's margin; a tooltip's frame instead."""
        dark = ak.help_menu_sheet(u"#3c3c40", u"#e0e0e0", u"#3a6ea5", u"#ffffff")
        self.assertIn(u"background-color: #3c3c40; color: #e0e0e0; border: 1px solid #e0e0e0", dark)
        self.assertIn(u"QMenu::item:selected { background-color: #3a6ea5; color: #ffffff; }", dark)
        self.assertIn(u"QMenu::item { background-color: transparent; padding: 3px 8px; }", dark)
        # (dark mode mapped the light frame to a dark one once the menu was up: marked first, November 24)
        import inspect
        source = inspect.getsource(ak.help_menu_picked)
        self.assertLess(source.index("menu.setProperty(LEAVE_ALONE_PROP, True)"), source.index("menu.setStyleSheet("))

    def test_italics_get_a_hair_of_room_after_them(self):
        """Image 8: "Condense.otf in" read as "otfin". The interface font's italic is the upright one slanted,
        each letter reaching one or two pixels past its width (measured live); a small no-break space follows
        every italic run."""
        gap = ak.ITALIC_GAP
        self.assertEqual(ak.italic_gaps(u"Opening <i>a.otf</i> in FontLab"), u"Opening <i>a.otf</i>%s in FontLab" % gap)
        self.assertEqual(ak.italic_gaps(u"<i>Now</i>: <i>Then</i>."), u"<i>Now</i>%s: <i>Then</i>%s." % (gap, gap))
        once = ak.italic_gaps(u"<i>Tick all</i> and <b>bold</b>")
        self.assertEqual(ak.italic_gaps(once), once, "given once: a text that has them is left as it is")
        self.assertEqual(ak.italic_gaps(u"No italics, <b>bold</b>."), u"No italics, <b>bold</b>.")
        self.assertEqual(ak.italic_gaps(u""), u"")
        self.assertEqual(ak.italic_gaps(None), u"")
        self.assertIn(u"&nbsp;", gap, "never a place where a line breaks")
        self.assertNotIn(u"<i>", ak.i(u"plain").replace(u"<i>plain</i>", u""), "i() itself is as it was")

    def test_status_lines_and_log_lines_show_their_italics_with_room(self):
        self.assertIn(u"</i>%s" % ak.ITALIC_GAP, ak.italic_gaps(ak.sentences(u"Click <i>Analyze</i> first.")))
        source = io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        self.assertIn(u"italic_gaps(sentences(text))", source, "a status line's text")
        self.assertIn(u"(stamp, italic_gaps(text))", source, "a log's line")

    def test_a_tooltip_is_as_wide_as_qt_lays_its_text_out(self):
        """Image 9: every tooltip had room after its text, the margin of an estimated width. With the text's
        width as Qt lays it out, the tooltip is that wide and a pixel more; estimated when that fails."""
        measure = lambda text: 7 * len(text)
        asked = []

        def exact(text):
            asked.append(text)
            return 151.2

        laid_out = ak.tip_html(u"Tick glyphs or select a row first.", 500, measure, exact)
        self.assertIn(u'width="%d"' % (152 + ak.TIP_EXACT_MARGIN), laid_out)
        self.assertEqual(asked, [u"Tick glyphs or select a row first."], "the text as shown, measured once")
        self.assertLess(ak.TIP_EXACT_MARGIN, ak.TIP_MARGIN)
        self.assertIn(u'width="500"', ak.tip_html(u"Long.", 500, measure, lambda text: 2000.0), "never past its window's share")

        def broken(text):
            raise RuntimeError("no document")

        self.assertIn(u'width="%d"' % (7 * len(u"Short.") + ak.TIP_MARGIN), ak.tip_html(u"Short.", 500, measure, broken))
        italic = ak.tip_html(u"Click <i>Analyze</i> first.", 500, measure, exact)
        self.assertIn(u"<i>Analyze</i>%s first." % ak.ITALIC_GAP, italic)
        self.assertIn(ak.ITALIC_GAP, asked[-1], "measured with the room after its italics")

    def test_a_windows_dropdown_lists_follow_a_switch_of_theme(self):
        """Images 3 and 4: a dropdown's list kept the theme before (dark on a light window, then light on a dark
        one). The list is in a popup, a window of its own, which the walk over a window's widgets left out."""
        class Popup(object):
            pass

        class View(object):
            def __init__(self, popup):
                self.popup = popup

            def parentWidget(self):
                return self.popup

        class Combo(object):
            def __init__(self, view):
                self._view = view

            def view(self):
                if self._view == "raises":
                    raise RuntimeError("no list")
                return self._view

        one, two = Popup(), Popup()
        combos = [Combo(View(one)), Combo(View(two)), Combo(View(one)), Combo(None), Combo("raises")]
        window = type("Window", (), {"findChildren": lambda self, kind: combos})()
        real = ak._qt
        ak._qt = lambda: (None, type("QtGui", (), {"QComboBox": "QComboBox"}))
        try:
            self.assertEqual(ak.popup_windows(window), [one, two], "each popup once; a box without a list left out")
            broken = type("Window", (), {"findChildren": lambda self, kind: 1 / 0})()
            self.assertEqual(ak.popup_windows(broken), [])
        finally:
            ak._qt = real
        source = io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        self.assertIn(u"roots.extend(popup_windows(window))", source, "the walk a switch of theme makes takes them in")

    def test_a_previews_captions_and_lines_show_only_with_something_to_preview(self):
        """Images 6 and 12: captions over nothing (Auto Spacing), lines between empty previews (Kerning Check)."""
        class Part(object):
            def __init__(self):
                self.props, self.visible, self.calls = {}, True, []

            def setProperty(self, name, value):
                self.props[name] = value

            def property(self, name):
                return self.props.get(name)

            def setVisible(self, on):
                self.visible = on
                self.calls.append(on)

        caption, line = Part(), Part()
        ak.preview_filled([caption, None, line], False)
        self.assertEqual((caption.visible, line.visible), (False, False))
        self.assertTrue(caption.property(ak.PREVIEW_EMPTY_PROP) and line.property(ak.PREVIEW_EMPTY_PROP),
                        "marked: a font coming does not show them again (no_font_states)")
        caption.props[ak.NO_FONT_HIDDEN_PROP] = True
        ak.preview_filled([caption, None, line], True)
        self.assertEqual((caption.visible, line.visible), (True, True))
        self.assertIsNone(caption.property(ak.PREVIEW_EMPTY_PROP))
        self.assertIsNone(caption.property(ak.NO_FONT_HIDDEN_PROP))
        ak.preview_filled(None, True)  # (nothing raised)
        ak.preview_filled([object()], False)  # (a part that takes none of it: nothing raised)
        source = io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
        self.assertIn(u"(has_font or heads_section(line)) and not line.property(PREVIEW_EMPTY_PROP)", source)
        self.assertIn(u"if label.property(PREVIEW_EMPTY_PROP):", source)


class ReleaseCachesTests(unittest.TestCase):
    """Feature Check's checks of a writer's code (two compiled stub fonts of a CJK font's every glyph) outlived
    every window (live, 2026-11-19): a window let go empties them; the next write checks again."""

    def test_a_window_let_go_empties_feature_checks_cache(self):
        import types
        held = sys.modules.get(ak.FEATURE_CHECK_MODULE)
        module = types.ModuleType(ak.FEATURE_CHECK_MODULE)
        module._REPORTS = {("code", 3, 7): object(), ("code2", 3, 7): object()}
        sys.modules[ak.FEATURE_CHECK_MODULE] = module
        try:
            self.assertTrue(ak.release_caches())
            self.assertEqual(module._REPORTS, {})
            self.assertFalse(ak.release_caches(), "nothing left to empty")
            module._REPORTS[("code", 3, 7)] = object()
            owner = type("Tool", (object,), {})()
            owner.dialog = None
            self.assertIn("caches", ak.let_go(owner))
            self.assertEqual(module._REPORTS, {})
        finally:
            if held is None:
                sys.modules.pop(ak.FEATURE_CHECK_MODULE, None)
            else:
                sys.modules[ak.FEATURE_CHECK_MODULE] = held


class McpConventionTests(unittest.TestCase):
    """FreeLab follows FreeLab MCP's optional window conventions (its docs/WINDOW-TOOLS.md), so the MCP's generic
    window tools drive FreeLab's windows surely: each window and dialog says it is a script's, a window says what
    step it works at, controls take stable objectNames from the tool's attributes, icon-only buttons have names,
    and the buttons that write files need risky mode. FreeLab needs nothing of the MCP."""

    class Widget(object):
        def __init__(self, cls, window=None, bases=(), name=u""):
            self.cls, self.bases, self.win = cls, set((cls,) + tuple(bases)), window
            self.objectName, self.props, self.accessible = name, {}, None

        def inherits(self, name):
            return name in self.bases

        def metaObject(self):
            return self.cls

        def isWidgetType(self):
            return True

        def isWindow(self):
            return self.win is None

        def window(self):
            return self if self.win is None else self.win

        def setObjectName(self, name):
            self.objectName = name

        def setAccessibleName(self, name):
            self.accessible = name

        def property(self, name):
            return self.props.get(name)

        def setProperty(self, name, value):
            self.props[name] = value

    def tool(self):
        W = self.Widget
        window = W("QDialog")
        owner = type("Tool", (object,), {})()
        owner.dialog = window
        owner.check_button = W("QPushButton", window, ("QAbstractButton",))
        owner.tree = W("QTreeWidget", window, ("QAbstractItemView",))
        owner.font_label = W("QLabel", window, ("QFrame",))
        owner.named = W("QComboBox", window, name=u"chosenAlready")
        owner.box = W("QWidget", window)  # (a container: FreeLab MCP never lists it)
        owner.flag_button = W("QPushButton", window, ("QAbstractButton",))  # (dark mode reads flag... as FontLab's swatches)
        owner.other = W("QPushButton", W("QDialog"), ("QAbstractButton",))  # (another window's)
        owner.busy, owner.rows, owner.ak = False, [W("QLabel", window)], ak

        class Log(object):
            pass

        owner.log = Log()
        owner.log.view = W("QTextBrowser", window, ("QTextEdit",))
        owner.log.widget = W("QWidget", window)

        class Tab(object):
            pass

        owner.coverage = Tab()
        owner.coverage.status = W("QLabel", window)
        owner.coverage.owner = owner
        tabs = owner.tabs = W("QTabBar", window)
        tabs.count, tabs.tabText = 2, lambda index: [u"Coverage", u"Vertical metrics (3)"][index]
        pages = owner.pages = W("QStackedWidget", window)
        page_widgets = [W("QWidget", window), W("QWidget", window)]
        pages.count, pages.widget = 2, lambda index: page_widgets[index]
        return owner, page_widgets

    def test_a_tools_window_is_marked_and_its_controls_named_after_its_attributes(self):
        owner, page_widgets = self.tool()
        given = ak.mcp_conventions(owner)
        self.assertIs(owner.dialog.props.get("mcpScriptWindow"), True, "FreeLab's own window")
        self.assertIs(owner.dialog.props.get("mcpBusy"), False, "not busy: the property set, so FreeLab MCP reads it")
        self.assertEqual(owner.check_button.objectName, u"check_button")
        self.assertEqual(owner.tree.objectName, u"tree")
        self.assertEqual(owner.font_label.objectName, u"font_label", "a label too, for read_text")
        self.assertEqual(owner.tabs.objectName, u"tabs")
        self.assertEqual(owner.named.objectName, u"chosenAlready", "a name given is kept")
        self.assertEqual(owner.box.objectName, u"", "containers are left unnamed")
        self.assertEqual(owner.flag_button.objectName, u"", "never a name dark mode reads as FontLab's")
        self.assertEqual(owner.other.objectName, u"", "only the window's own controls")
        self.assertEqual(owner.rows[0].objectName, u"", "nor what a list holds")
        self.assertEqual(owner.log.view.objectName, u"log", "a part's view takes the part's name")
        self.assertEqual(owner.log.widget.objectName, u"")
        self.assertEqual(owner.coverage.status.objectName, u"coverage.status", "a part's control: the part's name and its own")
        self.assertEqual([page.objectName for page in page_widgets], [u"pages.coverage", u"pages.vertical_metrics"],
                         "the pages a tab bar switches, after their tabs")
        self.assertEqual(len(given), len(set(given)), "each name once")

    def test_names_are_given_once_and_never_changed(self):
        owner, _pages = self.tool()
        ak.mcp_conventions(owner)
        owner.renamed = owner.check_button  # (held under another name since)
        del owner.check_button
        owner.later_button = self.Widget("QPushButton", owner.dialog, ("QAbstractButton",))  # (made by the work)
        given = ak.name_controls(owner)
        self.assertEqual(owner.renamed.objectName, u"check_button")
        self.assertEqual(given, [u"later_button"], "only the control made since")
        owner.dialog.props["mcpBusy"] = u"Checking"
        ak.mcp_conventions(owner)
        self.assertEqual(owner.dialog.props["mcpBusy"], u"Checking", "a window at work stays busy")

    def test_busy_says_the_step_and_ends_false(self):
        owner, _pages = self.tool()
        timers = []

        class Timer(object):
            def __init__(self, parent=None):
                timers.append(self)

            def __getattr__(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return lambda *args: None

        class App(object):
            def installEventFilter(self, guard):
                pass

            def removeEventFilter(self, guard):
                pass

        class Gui(object):
            class QApplication(object):
                @staticmethod
                def instance():
                    return App()

                @staticmethod
                def processEvents():
                    steps.append(owner.dialog.props.get("mcpBusy"))

        class Core(object):
            QTimer = Timer

            class Qt(object):
                Key_Escape = 0x01000000

                @staticmethod
                def singleShot(ms, slot):
                    pass
        steps = []
        real = ak._qt
        ak._qt = lambda: (Core, Gui)
        try:
            ak.busy_start(owner, u"Reading the font")
            self.assertEqual(owner.dialog.props["mcpBusy"], u"Reading the font")
            ak.busy_progress(owner, u"Checking", 0.5)
            self.assertEqual(owner.dialog.props["mcpBusy"], u"Checking", "each step's name")
            ak.busy_progress(owner, None, 0.7, force=True)
            self.assertEqual(owner.dialog.props["mcpBusy"], u"Checking", "kept while the step goes on")
            self.assertEqual(steps[0], u"Reading the font", "set before the first events go through")
            ak.busy_end(owner)
            self.assertIs(owner.dialog.props["mcpBusy"], False, "over: False, never left unset")
            ak.busy_start(owner)
            self.assertIs(owner.dialog.props["mcpBusy"], True, "work with no step's name is busy too")
            ak.busy_end(owner)
        finally:
            ak._qt = real

    def test_the_top_rows_icon_buttons_have_names(self):
        made = []

        class Any(object):
            """A Qt object that does whatever it is asked, recording the names and properties it is given."""

            def __init__(self, *args):
                self.objectName, self.accessible, self.text_ = u"", None, None

            def __getattr__(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return Any()

            def __call__(self, *args, **kwargs):
                return Any()

            def setObjectName(self, name):
                self.objectName = name

            def setAccessibleName(self, name):
                self.accessible = name

            def setText(self, text):
                self.text_ = text

        class ToolButton(Any):
            InstantPopup = 2

            def __init__(self, *args):
                Any.__init__(self)
                made.append(self)

        class First(object):
            def inherits(self, name):
                return False

            def property(self, name):
                return None

        class Item(object):
            def __init__(self, widget):
                self.item = widget

            def widget(self):
                return self.item

            def layout(self):
                return None

        class Layout(object):
            def __init__(self):
                self.items = [Item(First())]

            def count(self):
                return len(self.items)

            def itemAt(self, index):
                return self.items[index] if index < len(self.items) else None

            def removeWidget(self, widget):
                self.items = [item for item in self.items if item.widget() is not widget]

            def insertLayout(self, index, layout):
                self.items.insert(index, Item(None))

        class Dialog(Any):
            def layout(self):
                return self.held

        class Gui(object):
            def __getattr__(self, name):
                return ToolButton if name == "QToolButton" else Any()
        dialog = Dialog()
        dialog.held = Layout()
        real, held = ak._qt, list(ak._TOOL_BUTTONS)
        ak._qt = lambda: (Any(), Gui())
        try:
            button = ak.add_tools_button(dialog, "Auto Kerning")
        finally:
            ak._qt = real
            ak._TOOL_BUTTONS[:] = held
        self.assertIsNotNone(button)
        names = dict((made_button.objectName, made_button.accessible) for made_button in made)
        self.assertEqual(names, {"freelabTools": u"Tools", "freelabPreviousTool": u"Previous tool",
                                 "freelabNextTool": u"Next tool", "freelabHelp": u"Help"})

    def test_the_file_writers_need_risky_mode_and_the_dialogs_are_freelabs(self):
        # The buttons that write files outside FontLab's History are marked mcpRisky where they are made
        root = os.path.join(HERE, os.pardir)
        writers = (("builder/freelab_font_builder.py", "self.save_button"), ("proof/freelab_proof.py", "self.save_button"),
                   ("cjk/freelab_cjk_vertical.py", "self.export_button"),
                   ("checks/freelab_font_check.py", "self.save_set_button"),
                   ("checks/freelab_font_check.py", "self.remove_set_button"))
        sources = {}
        for path, _attribute in writers:
            with io.open(os.path.join(root, path), encoding="utf-8") as handle:
                sources[path] = handle.read()
        for path, attribute in writers:
            source = sources[path]
            made = source.index(attribute + " = QtGui.QPushButton(")
            marked = re.search(r"mark_risky\((%s|button)\)" % re.escape(attribute), source[made:made + 600])
            self.assertTrue(marked, "%s in %s is marked risky right where it is made" % (attribute, path))
        # Every save dialog is reached from a marked button: each file asking where to save has a mark
        for name in os.listdir(root):
            folder = os.path.join(root, name)
            if not os.path.isdir(folder) or name in ("tests", "tools", "docs"):
                continue
            for file_name in os.listdir(folder):
                if not file_name.endswith(".py"):
                    continue
                with io.open(os.path.join(folder, file_name), encoding="utf-8") as handle:
                    source = handle.read()
                if ("getSaveFileName(" in source or "save_file_name(" in source) and "darkmode" not in name:
                    self.assertIn("mark_risky(", source, "%s/%s writes a file the user names" % (name, file_name))
                # every message box FreeLab shows says it is FreeLab's own
                for match in re.finditer(r"QMessageBox\((self\.dialog|[a-z_.]+)\)", source):
                    line = source[source.rfind("\n", 0, match.start()) + 1:source.find("\n", match.end())]
                    self.assertIn("mcp_script_window(", line, "%s/%s: %s" % (name, file_name, line.strip()))
                # and every dialog either is a tool's window (take_window marks it) or is marked where it is made
                for match in re.finditer(r"QtGui\.QDialog\(", source):
                    line = source[source.rfind("\n", 0, match.start()) + 1:source.find("\n", match.end())]
                    self.assertTrue("mcp_script_window(" in line or "take_window(" in source,
                                    "%s/%s: %s" % (name, file_name, line.strip()))
        self.assertEqual((ak.MCP_SCRIPT_WINDOW, ak.MCP_BUSY, ak.MCP_RISKY), ("mcpScriptWindow", "mcpBusy", "mcpRisky"))
        button = self.Widget("QPushButton")
        self.assertIs(ak.mark_risky(button), button)
        self.assertIs(button.props["mcpRisky"], True)


class SaveFileNameTests(unittest.TestCase):
    """Windows' own "Confirm Save As" box stays light in dark mode (owner's report, 2026-11-24): the save dialog
    is asked not to confirm replacing a file, so the tool asks in its own box; where this PythonQt takes no
    options, the plain call as before, and Windows' box asked of the name typed."""

    def dialog_class(self, refuse=(), named=True, broken=False):
        calls = []

        class Dialog(object):
            DontConfirmOverwrite = "the enum's value"

            @staticmethod
            def getSaveFileName(*args):
                calls.append(args)
                if broken:
                    raise RuntimeError("no dialog")
                if len(args) > 4 and (args[4] in refuse or "all" in refuse):
                    raise ValueError("Could not find matching overload for given arguments")
                return "C:/Temp/Hand.svg"
        if not named:
            del Dialog.DontConfirmOverwrite

        class Gui(object):
            QFileDialog = Dialog
        return Gui, calls

    def test_the_options_asked_where_this_pythonqt_takes_them(self):
        gui, calls = self.dialog_class()
        self.assertEqual(ak.save_file_name(gui, "parent", "Save", "C:/Temp/x.svg", "SVG (*.svg)"),
                         ("C:/Temp/Hand.svg", False), "Windows asked nothing: the tool asks")
        self.assertEqual(calls, [("parent", "Save", "C:/Temp/x.svg", "SVG (*.svg)", None, "the enum's value")])
        gui, calls = self.dialog_class(refuse=(None,))
        self.assertEqual(ak.save_file_name(gui, "parent", "Save", "C:/Temp/x.svg", "SVG (*.svg)")[1], False)
        self.assertEqual([call[4] for call in calls], [None, u""], "the filter as an empty string next")
        gui, calls = self.dialog_class(named=False)
        ak.save_file_name(gui, None, "Save", "", "")
        self.assertEqual(calls[0][5], ak.DONT_CONFIRM_OVERWRITE)
        self.assertEqual(ak.DONT_CONFIRM_OVERWRITE, 0x4, "QFileDialog::DontConfirmOverwrite")

    def test_the_plain_call_as_before_where_it_takes_none(self):
        gui, calls = self.dialog_class(refuse=("all",))
        self.assertEqual(ak.save_file_name(gui, "parent", "Save", "C:/Temp/x.svg", "SVG (*.svg)"),
                         ("C:/Temp/Hand.svg", True), "Windows' own box asked of the name typed")
        self.assertEqual(calls[-1], ("parent", "Save", "C:/Temp/x.svg", "SVG (*.svg)"))
        self.assertEqual(len(calls), 3)
        gui, calls = self.dialog_class(broken=True)
        self.assertEqual(ak.save_file_name(gui, "parent", "Save", "", ""), (u"", True), "never raises")
        self.assertEqual(len(calls), 2, "another error: the plain call, once")


class TextReviewTests(unittest.TestCase):
    """The interface-text review of November 24: each help names what the window really does, with "tick" for
    check boxes, and each count with its noun."""

    def source(self, module):
        path = module.__file__[:-1] if module.__file__.endswith(".pyc") else module.__file__
        with io.open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_auto_kerning_help_ticks_and_says_each_key_once(self):
        for words in (u"writes only the pairs you tick", u"Tick the pairs to write;\npairs the font kerns already start "
                      u"unticked", u"puts every tick and pick back", u"<i>Space</i> ticks or\nunticks the pair.<br>"):
            self.assertIn(words, ak.HELP)
        self.assertNotIn(u"uncheck", ak.HELP)
        keys = ak.HELP.split(u"<b>Keys in the list</b>")[1].split(u"<br>")[0]
        self.assertNotIn(u"Ctrl", keys, "said in the paragraph above")
        self.assertNotIn(u"Backspace", keys, "said in the paragraph above")
        self.assertIn(u"<i>Write ticked\npairs</i>", ak.CLASS_HELP, "the button's own name")

    def test_auto_kerning_controls_have_their_help(self):
        source = self.source(ak)
        main = source.split(u"class AutoKerningDialog")[1].split(u"\n    def ")[1]  # (its __init__)
        self.assertIn(u'self.none_button.setWhatsThis("Unticks every listed pair.")', main)
        self.assertIn(u"Spread: how far apart the methods' values lie", main)
        order = main.split(u"self.order.setWhatsThis(")[1].split(u")\n")[0]
        for words in (u"largest change", u"agreement first (the smallest Spread)", u"most common", u"alphabetical"):
            self.assertIn(words, order)
        self.assertNotIn(u"between H's, n's", main)
        self.assertIn(u"between its script's \"\n", main)
        self.assertNotIn(u"two H's", main)
        self.assertNotIn(u"this H's pair", main)
        self.assertEqual(ak.spread([-80, -60, None, -70]), 20, "how far the methods' values lie apart")
        classes = source.split(u"class ClassDialog")[1].split(u"\n    def show")[0]
        for button, words in ((u"all_button", u"Ticks every row of the list."),
                              (u"none_button", u"Unticks every row of the list."),
                              (u"apply_button", u"Makes the ticked new classes")):
            self.assertIn(u'self.%s.setWhatsThis(u"%s' % (button, words), classes)
        self.assertNotIn(u"here are this one's", source)

    def test_delete_resets_a_pick_as_backspace_does_and_the_help_says_so(self):
        # (the review of 2026-11-24: Delete was bound to reset with Backspace, and no help said it)
        source = self.source(ak)
        self.assertIn(u'("Delete", self.reset)', source)
        self.assertIn(u"<i>Backspace</i>, <i>Delete</i>, or <i>Reset pair</i>", u" ".join(ak.HELP.split()))
        self.assertIn(u"<i>Backspace</i> or <i>Delete</i> gives", source)

    def test_error_sentences_end_with_one_period(self):
        # (the review of 2026-11-24: "Stopped by an error: ..." had no period, and the log adds none)
        self.assertEqual(ak.error_sentence(u"Stopped by an error", ValueError(u"no master")),
                         u"Stopped by an error: no master.")
        self.assertEqual(ak.error_sentence(u"FontLab did not open the glyph", u"It failed."),
                         u"FontLab did not open the glyph: It failed.", "never two periods")
        self.assertEqual(ak.error_sentence(u"Stopped by an error", u"a < b "), u"Stopped by an error: a &lt; b.")
        self.assertEqual(ak.error_sentence(u"Stopped by an error", u""), u"Stopped by an error.")
        for module in (ak, kc):
            source = self.source(module)
            self.assertNotIn(u"Stopped by an error: %s", source)
            self.assertNotIn(u"did not open the pair: %s", source)
            self.assertNotIn(u"did not open: %s", source)
        for path in ("builder/freelab_font_builder.py", "cjk/freelab_cjk_spacing.py", "cjk/freelab_cjk_vertical.py",
                     "compose/freelab_glyph_compose.py", "compose/freelab_glyph_generation.py",
                     "features/freelab_alternates.py", "features/freelab_feature_check.py",
                     "features/freelab_feature_code.py", "spacing/freelab_auto_spacing.py",
                     "checks/freelab_font_check.py"):
            with io.open(os.path.join(HERE, os.pardir, *path.split("/")), encoding="utf-8") as handle:
                source = handle.read()
            for sentence in (u"Stopped by an error: %s", u"did not open the glyph: %s", u"did not open: %s"):
                self.assertNotIn(sentence, source, path)

    def test_the_busy_bar_help_says_a_write_is_never_stopped(self):
        # (shared by reads and writes; busy_progress never stops a write: stoppable=False)
        self.assertIn(u"A write to the font is never stopped", ak.BUSY_HELP)
        self.assertIn(u"<i>Cancel</i> (where the window has it) and <i>Esc</i> stop it at its next step", ak.BUSY_HELP)
        self.assertIn(u"tip = BUSY_HELP", self.source(ak))

    def test_kerning_classes_counts_take_their_nouns(self):
        text = ak.class_counts_text({"new": 1, "add": 2, "same": 0, "overlap": 1})
        self.assertEqual(text, u"<b>1 new class</b>, <b>2 classes to extend</b>, <b>0 classes</b> the font has "
                               u"already, <b>1 class</b> left as it is (it overlaps the font's classes). Nothing is "
                               u"changed until you create them.")
        self.assertIn(u"<b>2 classes</b> left as they are (they overlap", ak.class_counts_text({"overlap": 2}))
        self.assertEqual(ak.class_made_text(0, 0, 0), u"Made 0 classes and extended 0 classes.")
        self.assertEqual(ak.class_made_text(1, 0, 1), u"Made 1 class and extended 0 classes, and moved 1 pair into it.")
        self.assertEqual(ak.class_made_text(2, 1, 3), u"Made 2 classes and extended 1 class, and moved 3 pairs into them.")

    def test_kerning_check_help_describes_the_default_mode_first(self):
        self.assertEqual(kc.COLLISION_MODES[0][0], "relative", "the dropdown starts on it")
        collisions = kc.HELP.split(u"<b>Collisions</b>")[1].split(u"<br>")[0]
        self.assertLess(collisions.index(u"base pair"), collisions.index(u"<i>of each other, accented or not</i>"))
        self.assertIn(u"as far apart as the base pair", collisions)
        self.assertIn(u"drag the <i>Adjusted</i> preview's right glyph", collisions)
        source = self.source(kc)
        mode = source.split(u"self.mode.setWhatsThis(")[1].split(u")\n")[0]
        self.assertTrue(mode.startswith(u'u"Which pairs are listed.'))
        for gone in (u"How both glyphs' ink", u"closer by at least as many units than", u"It suits any font"):
            self.assertNotIn(gone, mode)
        self.assertIn(u"the worst first", source)
        self.assertNotIn(u"closest first: their kerning", source)
        self.assertIn(u'u"Removes the ticked entries from the current master."', source)
        self.assertNotIn(u"between H's, n's", source)


DOCS = os.path.join(HERE, os.pardir, "docs")


class CancelButtonTests(unittest.TestCase):
    """A window's Cancel button (the owner, 2026-11-24: "a 'Cancel' button left of 'Close' could be useful,
    especially when exporting very big character sets; greyed out when nothing is being exported"): right before
    Close, grayed but while work that can stop runs, and a click on it stops the work as Esc does."""

    class Button(object):
        def __init__(self, text=u""):
            self.text, self.props, self.enabled, self.slots = text, {}, True, {}
            self.tip = self.whats = None

        def setProperty(self, name, value):
            self.props[name] = value

        def property(self, name):
            return self.props.get(name)

        def setToolTip(self, text):
            self.tip = text

        def setWhatsThis(self, text):
            self.whats = text

        def setEnabled(self, on):
            self.enabled = bool(on)

        def isEnabled(self):
            return self.enabled

        def connect(self, signal, slot):
            self.slots[signal] = slot

    class Row(object):
        """A QHBoxLayout: its items in order (None for a stretch)."""

        def __init__(self, widgets):
            self.items = list(widgets)

        def count(self):
            return len(self.items)

        def itemAt(self, k):
            held = self.items[k]
            return type("Item", (object,), {"widget": lambda item: held})()

        def insertWidget(self, k, widget):
            self.items.insert(k, widget)

        def addWidget(self, widget):
            self.items.append(widget)

    def made(self, close_in_row=True):
        gui = type("Gui", (object,), {"QPushButton": staticmethod(lambda text: self.Button(text))})
        real = ak._qt
        ak._qt = lambda: (None, gui)
        self.addCleanup(setattr, ak, "_qt", real)
        owner = type("Tool", (object,), {})()
        build, close = self.Button(u"Build ticked glyphs"), self.Button(u"Close")
        row = self.Row([None, build, close] if close_in_row else [None, build])
        button = ak.cancel_button(owner, row, close, u"A save stopped leaves nothing behind.")
        return owner, row, button, build, close

    def test_cancel_stands_right_before_close_grayed_with_its_help(self):
        owner, row, button, build, close = self.made()
        self.assertEqual(row.items, [None, build, button, close], "immediately left of Close")
        self.assertIs(owner.cancel_button, button)
        self.assertEqual(button.text, u"Cancel")
        self.assertFalse(button.enabled, "grayed while nothing runs (never hidden: the row keeps its place)")
        self.assertEqual(button.tip, u"Stops the work in progress at its next step.")
        self.assertEqual(button.whats, ak.CANCEL_HELP + u" A save stopped leaves nothing behind.")
        self.assertIn(u"as <i>Esc</i> does", ak.CANCEL_HELP)
        self.assertIs(button.props[ak.CANCEL_PROP], True)
        self.assertIs(button.props[ak.WITHOUT_FONT_PROP], True, "no_font_states never gives it back with a font")
        self.assertIn("clicked()", button.slots)
        owner, row, button, build, close = self.made(close_in_row=False)
        self.assertEqual(row.items[-1], button, "no Close in the row: at its end")

    def test_it_is_usable_only_while_stoppable_work_runs_and_stops_it_as_esc(self):
        owner, row, button, build, close = self.made()
        state = ak._busy_state(owner)
        state.update({"running": True, "stoppable": True})
        ak.cancel_states(owner)
        self.assertTrue(button.enabled)
        self.assertTrue(ak.busy_cancel(owner))
        self.assertEqual((state["stop"], state["then"]), (True, None), "Esc's stop: nothing done after it")
        self.assertFalse(ak.busy_cancel(owner), "asked once")
        state.update({"stop": False, "stoppable": False})
        ak.cancel_states(owner)
        self.assertFalse(button.enabled, "a write to the font: grayed")
        self.assertFalse(ak.busy_cancel(owner))
        self.assertFalse(state["stop"])
        state.update({"running": False, "stoppable": True})
        ak.cancel_states(owner)
        self.assertFalse(button.enabled, "nothing runs: grayed")
        self.assertFalse(ak.busy_cancel(owner))
        ak.cancel_states(type("Bare", (object,), {})())  # (a window without one: nothing to do, no error)

    def test_busy_start_and_end_set_it_and_the_guard_lets_its_click_through(self):
        owner, row, button, build, close = self.made()
        filters = []

        class Timer(object):
            def __init__(self, parent=None):
                pass

            def __getattr__(self, name):
                if name.startswith("__"):
                    raise AttributeError(name)
                return lambda *args: None

        class App(object):
            def installEventFilter(self, guard):
                filters.append(guard)

            def removeEventFilter(self, guard):
                pass

        class Gui(object):
            QPushButton = staticmethod(lambda text: self.Button(text))

            class QApplication(object):
                @staticmethod
                def instance():
                    return App()

                @staticmethod
                def processEvents():
                    pass

        class Core(object):
            QTimer = Timer

            class Qt(object):
                Key_Escape = 0x01000000

                @staticmethod
                def singleShot(ms, slot):
                    pass

        class Window(object):
            def window(self):
                return self

            def property(self, name):
                return None

            def findChild(self, *args):
                return None

        window = Window()
        owner.dialog, owner.busy = window, True

        class Widget(object):
            def __init__(self, button, parent=None):
                self.button = button

            def isWidgetType(self):
                return True

            def window(self):
                return window

            def property(self, name):
                return self.button.property(name)

            def isEnabled(self):
                return self.button.enabled

            def inherits(self, name):
                return False

            def parentWidget(self):
                return None

        class Event(object):
            def __init__(self, kind):
                self.kind = kind

            def type(self):
                return self.kind

        ak._qt = lambda: (Core, Gui)
        ak.busy_start(owner, u"Saving the template")
        self.assertTrue(button.enabled, "stoppable work: usable")
        guard = filters[-1]
        state = ak._busy_state(owner)
        target = Widget(button)
        self.assertTrue(guard.eventFilter(target, Event(2)), "the press is taken, never reaching the window")
        self.assertFalse(state["stop"], "on release, as a click")
        self.assertTrue(guard.eventFilter(target, Event(3)))
        self.assertEqual((state["stop"], state["then"]), (True, None), "stopped as Esc stops it")
        self.assertRaises(ak.Stopped, ak.busy_progress, owner, None, 0.5)
        ak.busy_end(owner)
        self.assertFalse(button.enabled, "over: grayed")
        ak.busy_start(owner, u"Building the glyphs", stoppable=False)
        self.assertFalse(button.enabled, "a write to the font: grayed")
        guard = filters[-1]
        state = ak._busy_state(owner)
        self.assertTrue(guard.eventFilter(target, Event(3)))
        self.assertFalse(state["stop"], "a grayed Cancel stops nothing")
        ak.busy_end(owner)

    def test_a_write_that_goes_on_as_a_reading_gives_it_back(self):
        # (CJK Vertical reads its list again under its write's bar, which Esc stops: Cancel too, busy_stoppable)
        owner, row, button, build, close = self.made()
        state = ak._busy_state(owner)
        state.update({"running": True, "stoppable": False})
        ak.cancel_states(owner)
        self.assertFalse(button.enabled)
        ak.busy_stoppable(owner, True)
        self.assertTrue(button.enabled)
        self.assertTrue(ak.busy_cancel(owner), "stops as Esc would")
        state.update({"running": False, "stop": False, "stoppable": False})
        ak.cancel_states(owner)  # (busy_end's)
        ak.busy_stoppable(owner, True)
        self.assertFalse(button.enabled, "nothing runs: nothing to give back")
        self.assertFalse(state["stoppable"], "left as the last work had it")
        ak.busy_stoppable(type("Bare", (object,), {})())  # (a window without one: no error)


class CancelInEachWindowTests(unittest.TestCase):
    """The owner, 2026-11-24 ("a 'Cancel' button left of 'Close' could be useful ... greyed out ... when nothing
    is currently being exported"), asked for every window: Auto Kerning's and Kerning Check's here, right before
    Close, usable only while their work can stop, their help saying what a stop leaves."""

    def setUp(self):
        saved = dict((name, getattr(ak, name)) for name in ("busy_start", "busy_progress", "busy_end", "busy_stopping",
                                                            "fontlab_autokern"))
        self.addCleanup(lambda: [setattr(ak, name, value) for name, value in saved.items()])
        self.progressed, self.stopping = [], False

        def progress(owner, what=None, part=None, force=False, stoppable=True):
            self.progressed.append((what, owner.cancel_button.enabled))
            if self.stopping and stoppable:
                raise ak.Stopped()  # (as a click on Cancel makes it)
        ak.busy_start = lambda owner, what=u"", stoppable=True: None  # (the real ones need a window)
        ak.busy_end = lambda owner: None
        ak.busy_progress = progress
        ak.busy_stopping = lambda owner: False

    def test_auto_kerning_has_it_while_it_measures_or_asks_fontlab(self):
        with io.open(ak.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(u"buttons.addWidget(self.close_button)\n        cancel_button(self, buttons, self.close_button, "
                      u"AUTO_KERNING_CANCEL_NOTE)", source)
        dialog = ak.AutoKerningDialog.__new__(ak.AutoKerningDialog)
        row, button, close = qtfakes.cancel_made(ak, dialog, ak.AUTO_KERNING_CANCEL_NOTE, (u"Write ticked pairs",))
        self.assertEqual(row.items.index(button) + 1, row.items.index(close), "right before Close")
        self.assertFalse(button.enabled, "grayed while nothing runs")
        self.assertEqual(button.whats, ak.CANCEL_HELP + u" An analysis stopped changes nothing in the font.")
        seen = qtfakes.follow_cancel(self, ak)
        widget = type("Widget", (object,), {"setEnabled": lambda w, on: None})
        dialog.busy, dialog.refilter_again, dialog.package, dialog.focus, dialog.analysis = False, False, None, None, None
        dialog.analyze_button, dialog.update_buttons = widget(), lambda: None
        dialog.run_once = lambda: self.progressed.append((u"measuring", button.enabled))
        dialog.run()
        self.assertEqual(self.progressed, [(u"measuring", True)])
        self.assertEqual(seen, [(u"Measuring pairs", True, True), (None, None, False)], "grayed once it is over")
        # FontLab's values asked for a list filtered anew: its own bar, stoppable
        del seen[:], self.progressed[:]
        ak.fontlab_autokern = lambda package, master, left, right: 0
        dialog.master = u"Regular"
        dialog.analysis = type("Analysis", (object,), {"remember_fontlab": lambda a: None})()
        dialog.ask_fontlab([type("Pair", (object,), {"values": {}, "left": u"A", "right": u"V"})()])
        self.assertEqual(seen, [(u"Asking FontLab", True, True), (None, None, False)])
        self.assertEqual(self.progressed, [(u"Asking FontLab (0 of 1)", True)])
        # Write ticked pairs takes no bar: Cancel stays grayed through it
        write = source.split(u"\n    def write(self):\n")[1].split(u"\n    def ")[0]
        self.assertNotIn(u"busy_start", write)

    def check_dialog(self):
        dialog = kc.KerningCheckDialog.__new__(kc.KerningCheckDialog)
        dialog.ak, dialog.busy, dialog.only = ak, False, None
        qtfakes.cancel_made(ak, dialog, kc.CANCEL_NOTE, (u"Remove ticked entries",))
        return dialog

    def test_kerning_check_has_it_while_it_checks_not_while_it_writes(self):
        dialog = self.check_dialog()
        self.assertFalse(dialog.cancel_button.enabled)
        self.assertEqual(dialog.cancel_button.whats,
                         ak.CANCEL_HELP + u" A check stopped changes nothing in the font: its list is left empty.")
        seen = qtfakes.follow_cancel(self, ak)
        status = type("Status", (), {"text": None, "setText": lambda s, text: setattr(s, "text", text),
                                     "undo": lambda s, text: text, "report": lambda s, log: None})()
        tree = type("Tree", (), {"clear": lambda t: None})()
        dialog.cleanup = dialog.collisions = type("Tab", (), {"tree": tree, "status": status, "action": None,
                                                              "findings": [1], "first_checks": [True]})()
        dialog.masters = object()
        dialog.read_font = lambda: True
        dialog.update_previews = dialog.update_buttons = lambda: None
        dialog.tiny = type("Box", (), {"value": 5})()
        entries = [((u"A", False), (u"V%d" % n, False)) for n in range(60)]
        kerning = type("Kerning", (), {"entries": entries, "values": dict((e, -40) for e in entries), "members": {},
                                       "describe": staticmethod(lambda e: u"%s %s" % (e[0][0], e[1][0])),
                                       "pairs": staticmethod(lambda e: []), "candidates": staticmethod(lambda a, b: []),
                                       "current": staticmethod(lambda a, b: -60),
                                       "write": staticmethod(lambda *args: None)})()
        dialog.kerning = lambda master=None: kerning
        dialog.glyph_exists = lambda name: True
        self.stopping = True  # (Cancel clicked at the check's first step)
        dialog.check_cleanup()
        self.assertEqual(seen, [(kc.CLEANUP_STEP, True, True), (None, None, False)], "usable while it checks")
        self.assertEqual(self.progressed[0][1], True)
        self.assertIn(u"was stopped: nothing is listed", status.text, "the note's empty list")
        del seen[:], self.progressed[:]
        dialog.same_font = dialog.begin_writing = lambda: True
        dialog.checked = lambda tab: [kc.Collision(u"T", u"o", -60, 2, -40, None)]
        dialog.after_writing = lambda: status
        dialog.check_collisions = lambda: None
        dialog.log = type("Log", (), {"add": lambda log, text, kind="info": None})()
        dialog.write_fixes()
        self.assertEqual(seen, [(kc.WRITE_STEP, False, False), (None, None, False)], "grayed while it writes")
        self.assertEqual(self.progressed, [(kc.WRITE_STEP, False)], "and never stopped by the click")

    def test_the_python27_copy_skips_only_the_pages_claims(self):
        # (the Python 2.7 run copies no README.md or WINDOWS.md: DocsClaimTests skips there, nothing else here)
        pages = os.path.isfile(os.path.join(DOCS, "WINDOWS.md"))
        self.assertEqual(bool(getattr(DocsClaimTests, "__unittest_skip__", False)), not pages)
        for case in (CancelButtonTests, CancelInEachWindowTests):
            self.assertFalse(getattr(case, "__unittest_skip__", False), case.__name__)


# (the skip is this class's: it stood over CancelButtonTests, which needs no page, and the Python 2.7 run, whose
# copy holds no README.md or WINDOWS.md, errored here twice)
@unittest.skipUnless(os.path.isfile(os.path.join(DOCS, "WINDOWS.md")),
                     "the pages are not beside the tests (the Python 2.7 run's copy holds COVERAGE-GAPS.md alone)")
class DocsClaimTests(unittest.TestCase):
    """The pages' sentences the review of 2026-11-24 found the interface had moved past: each stays gone."""

    def page(self, name):
        folder = os.path.join(HERE, os.pardir) if name == "README.md" else DOCS
        with io.open(os.path.join(folder, name), encoding="utf-8") as handle:
            return handle.read()

    def test_stale_claims_stay_gone(self):
        gone = {
            "README.md": (u"Each write is one step of FontLab's History",),
            "WINDOWS.md": (u"Each write is one step of FontLab's History", u"it ends as one step of FontLab's History"),
            "GLYPH-COMPOSE.md": (u"a tab's *Build* button", u"within 12 units (per 1000)",
                                 u"every recipe starts from glyphs any Latin font has", u"between H's, n's, and o's"),
            "FONT-CHECK.md": (u"its two writing buttons", u"what *Fix* sets right", u"*Fix* does not touch",
                              u"a checked set completes"),
            "SPACING.md": (u"the script never changes them", u"; they are never changed",
                           u"covers every glyph with a character"),
            "KERNING.md": (u"Auto Kerning reads and writes through them, and never makes",
                           u"analyzes the font that is current then", u"owner's test font), closest first"),
            "CJK.md": (u"*Hangul:*", u"*Write* once more", u"more Hangul than kana or hanzi",
                       u"the code *Write the code* would write"),
            "FONT-BUILDER.md": (u"**Glyphs a sheet**", u"*Save template...*", u"*Add sheets...*"),
            "PROOF.md": (u"what a designer wants",),
        }
        for name, sentences in gone.items():
            text = self.page(name)
            for sentence in sentences:
                self.assertNotIn(sentence, text, name)

    def test_the_pages_name_what_the_interface_shows(self):
        self.assertIn(u"*Put back vhea*", self.page("WINDOWS.md"))
        self.assertIn(u"FreeLab shows its own at the left end of the tab under the mouse", self.page("WINDOWS.md"))
        self.assertIn(u"*Backspace*, *Delete*", self.page("KERNING.md"))
        self.assertIn(u"*Declare coverage*", self.page("FONT-CHECK.md").split(u"\n")[2])
        self.assertIn(u"*Set Hangul widths*", self.page("CJK.md"))
        self.assertIn(u"**Glyphs per sheet**", self.page("FONT-BUILDER.md"))
        self.assertIn(u"within 1.2% of the em", self.page("GLYPH-COMPOSE.md"))


if __name__ == "__main__":
    unittest.main()
