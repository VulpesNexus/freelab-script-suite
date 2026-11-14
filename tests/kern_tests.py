"""Tests of FreeLab's auto kerning: the native core on synthetic glyphs, and the arithmetic around it.

The core's tests need its DLL (tools/build-native.ps1 -Kern, or the installer). Without it they are
skipped, and run_tests.py reports the skip. Valid Python 2.7 and Python 3.
"""

from __future__ import absolute_import, division, print_function

import ctypes
import io
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
        # after Diacritics built Tcaron (or moved its caron): only the pairs and entries with it
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
        self.assertEqual(kc.limit_line([u"L", u"l"], u"Diacritics built"), u"Pairs with the 2 glyphs Diacritics built: L l")
        self.assertEqual(kc.limit_line([u"L"], u"Diacritics built"), u"Pairs with the glyph Diacritics built: L")
        self.assertEqual(kc.limit_line([u"a", u"b", u"c"], None, shown=2), u"Pairs with these 3 glyphs: a b \N{HORIZONTAL ELLIPSIS}")
        self.assertEqual(kc.limit_line([u"a"]), u"Pairs with this glyph: a")

    def test_glyphs_handed_over_by_name_or_as_glyphs(self):
        glyph = type("Glyph", (), {"name": u"Ldot"})()
        self.assertEqual(kc.glyph_names([glyph, "ldot", u"Ldot", None]), [u"Ldot", u"ldot"])
        self.assertEqual(kc.glyph_names(None), [])

    def test_buttons_count_their_checked_rows(self):
        self.assertEqual(kc.action_text("cleanup", 0), u"Clean up checked entries")
        self.assertEqual(kc.action_text("cleanup", 1), u"Clean up 1 checked entry")
        self.assertEqual(kc.action_text("cleanup", 3), u"Clean up 3 checked entries")
        self.assertEqual(kc.action_text("collisions", 1), u"Write 1 checked fix")
        self.assertEqual(kc.action_text("collisions", 2), u"Write 2 checked fixes")
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
                kc.main(glyphs=["Ldot"], reason=u"Diacritics built")
                kc.main(["Ldot"], why=u"Diacritics moved marks of")
            finally:
                sys.stdout = saved
        else:
            with redirect(out):
                kc.main(glyphs=["Ldot"], reason=u"Diacritics built")
                kc.main(["Ldot"], why=u"Diacritics moved marks of")
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
        ak.before_changes(self.fontlab, package, u"FreeLab Diacritics")
        ak.notify_changed(self.fontlab, package, u"FreeLab Diacritics")
        package.state = 0  # (undone twice: back where the font was opened)
        self.assertEqual(ak.before_changes(self.fontlab, package, u"FreeLab Diacritics"), [package])

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

    def test_every_write_begins_with_before_changes_where_undo_needs_it(self):
        """Each tool that changes glyphs records the font first; kerning, feature code, and font info are
        the font's own state (recorded when FontLab opens a font: live, they went on Undo)."""
        root = os.path.join(HERE, os.pardir)
        expected = {"spacing/freelab_auto_spacing.py": 1, "cjk/freelab_cjk_spacing.py": 1,
                    "diacritics/freelab_diacritics.py": 1, "features/freelab_feature_code.py": 1,
                    "checks/freelab_font_check.py": 1, "kerning/freelab_auto_kerning.py": 1}
        for path, count in expected.items():
            with io.open(os.path.join(root, path), encoding="utf-8") as handle:
                source = handle.read()
            self.assertEqual(len(re.findall(r"(?<!def )before_changes\((?:self\.|owner\.)?fontlab", source)), count, path)


class MenuOrderTests(unittest.TestCase):
    def test_working_order_then_dark_mode_then_mcp(self):
        texts = ["Diacritics", "Auto Kerning", "Auto Spacing", "CJK Spacing", "Toggle Dark Mode", "Dark Mode Settings",
                 "Feature Code", "Kerning Check", "Start Listener", "Something New"]
        self.assertEqual(ak.menu_order(texts),
                         ["Diacritics", "Auto Spacing", "CJK Spacing", "Auto Kerning", "Kerning Check", "Feature Code", None,
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
        third = self.open("Diacritics")
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
        second = self.open("Diacritics")
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
        second = self.open("Diacritics")
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
        diacritics = self.Tool(self.workspace, u"FreeLab Diacritics")  # (from FontLab's menu: in Proof's place)
        ak.take_window("Diacritics", diacritics)
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
        self.workspace.currentPackage = self.one  # FontLab shows the other font; the click is in Two's window
        self.active = check.dialog
        diacritics = self.open("Diacritics")
        self.assertIs(diacritics.current_font(), self.two)
        self.assertFalse(check.dialog.visible, "its window's tool gave way")
        self.active = None
        kerning = self.open("Auto Kerning")
        self.assertIs(kerning.current_font(), self.one, "from FontLab's menu: the font FontLab shows")

    def test_a_windows_button_names_its_font_for_the_tool_it_opens(self):
        # (FontLab may run the menu entry once the click is over, the window no longer the active one)
        self.workspace.currentPackage = self.two
        check = self.open("Font Check")
        self.workspace.currentPackage = self.one
        sys._freelab_windows["hint"] = (check.font_id, ak.time.time())
        self.assertIs(self.open("Diacritics").current_font(), self.two)
        self.assertIsNone(sys._freelab_windows["hint"], "used once")
        sys._freelab_windows["hint"] = (check.font_id, ak.time.time() - 60)
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

    def test_a_window_whose_font_was_closed_moves_to_the_current_font(self):
        proof = self.open("Proof")
        self.workspace.fonts, self.workspace.currentPackage = [self.two], self.two
        self.assertIs(proof.current_font(), self.two)
        self.assertEqual(proof.dialog.windowTitle, u"FreeLab Proof (Two)")
        self.assertIsNone(self.open("Proof"), "it is that font's window now")

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
        diacritics = self.open("Diacritics")
        self.assertFalse(proof.dialog.visible, "the next tool takes its place")
        self.assertTrue(diacritics.dialog.visible)

    def test_the_window_clicked_is_the_one_replaced(self):
        # A window whose font was closed moves to the font FontLab shows, which had a window already: a
        # tool opened from it replaced the other window, which the owner had not clicked
        moved = self.open("Proof")
        self.workspace.currentPackage = self.two
        other = self.open("Diacritics")
        self.workspace.fonts = [self.two]  # One closed
        self.assertIs(moved.current_font(), self.two)
        self.assertIs(sys._freelab_windows["fonts"][self.two.id], other, "one window per font: Two's own stays its")
        self.assertIs(ak.window_owner(moved.dialog), moved, "the moved one is still found")
        self.active = moved.dialog  # its tools button clicked
        check = self.open("Font Check")
        self.assertFalse(moved.dialog.visible, "the window clicked gives way")
        self.assertTrue(other.dialog.visible, "the other is left alone")
        self.assertIs(check.current_font(), self.two)
        self.assertIs(sys._freelab_windows["fonts"][self.two.id], check)
        self.active = other.dialog  # and from the other one, through its button's hint (the window no longer active)
        sys._freelab_windows["hint"] = (other.font_id, ak.time.time(), other.window_key)
        self.active = None
        spacing = self.open("Auto Spacing")
        self.assertFalse(other.dialog.visible)
        self.assertTrue(check.dialog.visible)
        self.assertTrue(spacing.dialog.visible)

    def test_a_size_qt_or_the_logs_grip_gives_is_not_a_size_given_by_hand(self):
        first = self.open("Proof", laid_out=(520, 360))  # Qt grew it to its layout as it showed it
        second = self.open("Diacritics")
        self.assertFalse(first.dialog.visible)
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

    def test_undo_and_redo_reach_fontlab_for_this_windows_font_only(self):
        proof = self.open("Proof")
        self.shortcuts["Ctrl+Z"]()
        self.shortcuts["Ctrl+Y"]()
        self.assertEqual(self.triggered, ["actionUndo", "actionRedo"])
        proof.busy = True  # inside its own loop
        self.shortcuts["Ctrl+Z"]()
        self.assertEqual(len(self.triggered), 2, "nothing while the tool is busy")
        proof.busy = False
        self.workspace.currentPackage = self.two  # FontLab shows the other font: its History, not this one's
        self.shortcuts["Ctrl+Z"]()
        self.assertEqual(len(self.triggered), 2)
        self.assertEqual(len(proof.lines), 1)
        level, text = proof.lines[0]
        self.assertEqual(level, "warning")
        self.assertIn(u"<b>One</b>'s Font window", text, "names the font to click")

    def test_an_undo_from_a_window_redraws_fontlabs_views(self):
        # The owner: "The log does mention the history changed, but it doesn't appear to actually reach FontLab"
        self.open("Proof")
        told = []

        class Items(object):
            def __getattr__(self, name):
                return lambda *args: told.append((name,) + args)

        fontlab = sys.modules["fontlab"]
        fontlab.flItems = Items()
        self.addCleanup(lambda: delattr(fontlab, "flItems"))
        self.shortcuts["Ctrl+Z"]()
        self.assertEqual(self.triggered, ["actionUndo"])
        self.assertEqual(told, [], "told once FontLab's command has run")
        self.run_timers()
        self.assertEqual([call[0] for call in told], ["notifyPackageUpdated", "notifyHistoryChanged"],
                         "not notifyPackageContentUpdated: 8.8 s a Ctrl+Z on a 3,700-glyph font, live")
        self.assertEqual(told[0][1:], (self.one.id,), "this window's font")
        self.assertNotIn("notifyChangesApplied", [call[0] for call in told], "no step of the History of its own")

    def test_a_window_whose_font_closed_is_reused_then_takes_the_next_font(self):
        # The owner: "after a font is closed and the script stays open, it still remains attached to the font it
        # belonged to, meaning navigating again opens a new window"; and "can't it also detect when a font then
        # gets open after its launch to hook into that one?"
        spacing = self.open("Auto Spacing")
        changes = []
        spacing.font_changed = lambda: changes.append(("spacing", spacing.font_id))
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")  # (FontLab's placeholder)
        self.assertEqual(ak.fonts_tick(self.workspace), [spacing])
        self.assertIsNone(spacing.font_id)
        self.assertEqual(spacing.dialog.windowTitle, u"FreeLab Auto Spacing", "its title without the font")
        self.assertEqual(changes, [("spacing", None)], "the tool shows its no-font state")
        self.assertIs(sys._freelab_windows["fonts"].get(None), spacing)
        self.assertEqual(ak.fonts_tick(self.workspace), [], "nothing more to do")
        self.assertIsNone(self.open("Auto Spacing"), "FontLab's menu brings it forward: no second window")
        self.active = spacing.dialog  # its arrow to the next tool
        kerning = self.open("Auto Kerning")
        self.active = None
        self.assertFalse(spacing.dialog.visible, "the window clicked gives way, as one with a font does")
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
        busy = self.open("Diacritics")  # (on Two too: it takes the window's place)
        self.workspace.fonts, self.workspace.currentPackage = [], self.Font(1, u"")
        busy.busy = True
        self.assertEqual(ak.fonts_tick(self.workspace), [], "a busy window is looked at next time")
        busy.busy = False
        self.assertEqual(ak.fonts_tick(self.workspace), [busy])
        self.assertIsNone(busy.font_id)

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

    def test_the_tools_follow_the_order_of_the_work(self):
        self.assertEqual(ak.FONT_TOOLS[0], "Diacritics")
        self.assertEqual(ak.FONT_TOOLS[-2:], ("Font Check", "Proof"), "checked before it is proofed")
        self.assertEqual(ak.tool_neighbors("Diacritics"), (None, "Auto Spacing"))
        self.assertEqual(ak.tool_neighbors("Kerning Check"), ("Auto Kerning", "Feature Code"))
        self.assertEqual(ak.tool_neighbors("Proof"), ("Font Check", None))
        self.assertEqual(ak.tool_neighbors("No Such Tool"), (None, None))


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
        # The owner: "Some open upwards still even when there's room below" (Diacritics' Character set on
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
        self.assertIn(u"<i>Now</i>.<br><br>Then", ak.tip_html(u"<i>Now</i>.<br>Then", 500, measure))
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
            self.assertEqual(re.findall(u"QCheckBox\\(u?\"[^\"]*\\.\"\\)", source), [])
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


if __name__ == "__main__":
    unittest.main()
