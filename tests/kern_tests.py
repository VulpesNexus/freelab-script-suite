"""Tests of FreeLab's auto kerning: the native core on synthetic glyphs, and the arithmetic around it.

The core's tests need its DLL (tools/build-native.ps1 -Kern, or the installer). Without it they are
skipped, and run_tests.py reports the skip. Valid Python 2.7 and Python 3.
"""

from __future__ import absolute_import, division, print_function

import ctypes
import io
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
