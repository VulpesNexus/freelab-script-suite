# -*- coding: utf-8 -*-
"""Tests for the native pixel helper (darkmode/native/freelab_pixels.c), through ctypes (Python 3).

They need the built DLL (tools/build-native.ps1). Without it they are skipped,
and run_tests.py reports the skip.
"""

import ctypes
import os
import random
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "darkmode"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"

import freelab_dark_mode as dm  # noqa: E402

DLL = dm.native_path()


def _load():
    if not os.path.isfile(DLL):
        return None
    lib = ctypes.CDLL(DLL)
    lib.freelab_map_lightness.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_double,
                                          ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                          ctypes.c_double]
    lib.freelab_pixel_stats.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int, ctypes.c_double,
                                        ctypes.c_double, ctypes.POINTER(ctypes.c_int64)]
    lib.freelab_light_colors.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_double, ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_uint32), ctypes.c_int64]
    lib.freelab_light_colors.restype = ctypes.c_int64
    lib.freelab_map_keyed.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.c_int64, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                      ctypes.c_uint32]
    return lib


LIB = _load()


def pixels(colors, alpha=255):
    return bytearray(b"".join(struct.pack("<BBBB", b, g, r, alpha) for r, g, b in colors))


def run_map(lib, buf, min_l=0.0, ink_below=-1.0, keep_tint=0.0, width=None, edge_neutral=0.0):
    array = (ctypes.c_char * len(buf)).from_buffer(buf)
    count = len(buf) // 4
    lib.freelab_map_lightness(ctypes.addressof(array), count, width or count, dm.DARK_OKL, dm.LIGHT_OKL, min_l,
                              ink_below, keep_tint, edge_neutral)


def keyed(lib, buf, keys, width, min_l=-1.0, target=0):
    array = (ctypes.c_char * len(buf)).from_buffer(buf)
    lib.freelab_map_keyed(ctypes.addressof(array), len(buf) // 4, width, (ctypes.c_uint32 * len(keys))(*keys),
                          len(keys), dm.DARK_OKL, dm.LIGHT_OKL, 0.0, min_l, target)


@unittest.skipIf(LIB is None, "native helper not built: run tools/build-native.ps1 (%s)" % DLL)
class NativeTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(LIB.freelab_pixels_version(), dm.NATIVE_VERSION)

    def test_matches_python_mapping(self):
        random.seed(7)
        colors = [(r, g, b) for r in range(0, 256, 15) for g in range(0, 256, 15) for b in range(0, 256, 15)]
        colors += [tuple(random.randrange(256) for _ in range(3)) for _ in range(5000)]
        colors += [colors[0]] * 3  # a run of one color takes the cached path
        buf = pixels(colors, alpha=200)
        run_map(LIB, buf)
        for i, rgb in enumerate(colors):
            b, g, r, a = buf[4 * i:4 * i + 4]
            expected = dm.map_rgb(*rgb)
            self.assertLessEqual(max(abs(r - expected[0]), abs(g - expected[1]), abs(b - expected[2])), 1, rgb)
            self.assertEqual(a, 200)

    def test_min_l_maps_only_light_pixels(self):
        colors = [(255, 255, 255), (240, 240, 240), (128, 128, 128), (31, 31, 31), (225, 225, 225)]  # 225: L 0.88
        buf = pixels(colors)
        run_map(LIB, buf, min_l=dm.WHITE_L)
        out = [tuple(buf[4 * i + 2 - k] for k in range(3)) for i in range(len(colors))]
        self.assertEqual(out[0], dm.map_rgb(255, 255, 255))
        self.assertEqual(out[1], dm.map_rgb(240, 240, 240))
        self.assertEqual(out[2:], colors[2:], "below WHITE_L: untouched")

    def test_edges_map_white_and_ink_by_coverage(self):
        colors = [(255, 255, 255), (0, 0, 0), (30, 30, 30), (40, 160, 60), (15, 15, 15)]  # paper #1e1e1e, green syntax
        buf = pixels(colors)
        run_map(LIB, buf, min_l=dm.WHITE_L, ink_below=dm.EDGES_INK_BELOW)
        out = [tuple(buf[4 * i + 2 - k] for k in range(3)) for i in range(len(colors))]
        self.assertEqual(out[0], dm.map_rgb(255, 255, 255))
        self.assertEqual(out[1], (219, 219, 219), "full ink: light text")
        self.assertEqual(out[2:4], colors[2:4], "the paper and the syntax colors stay")
        self.assertTrue(30 < out[4][0] < 219, "a smoothed edge pixel lands between paper and text: %r" % (out[4],))

    def test_matches_python_with_tint_kept(self):
        random.seed(11)
        colors = [tuple(random.randrange(256) for _ in range(3)) for _ in range(3000)]
        buf = pixels(colors)
        run_map(LIB, buf, keep_tint=1.0)
        for i, rgb in enumerate(colors):
            got = tuple(buf[4 * i + 2 - k] for k in range(3))
            expected = dm.map_rgb(*rgb, keep_tint=1.0)
            self.assertLessEqual(max(abs(a - b) for a, b in zip(got, expected)), 1, rgb)

    def test_smoothing_blends_stay_blends(self):
        # A pixel halfway between white paper and black text maps halfway between the mapped two.
        buf = pixels([(255, 255, 255), (0, 0, 0), (128, 128, 128)])
        run_map(LIB, buf)
        white, black, half = (buf[0], buf[4], buf[8])
        self.assertLessEqual(abs(half - (white + black) / 2.0), 1.5)

    def test_keyed_also_maps_near_white(self):
        buf = pixels([(250, 250, 250), (60, 60, 60)])
        keyed(LIB, buf, [0xcacbcc], 2, dm.WHITE_L)
        self.assertLess(buf[0], 60, "a white frame corner turns dark")
        self.assertEqual(buf[4], 60)

    def test_edges_lose_tint_flat_areas_keep_it(self):
        # One row: a flat pink mark area, then a ClearType-like fringe pixel next to dark text.
        row = [(255, 205, 205)] * 3 + [(235, 200, 160), (40, 40, 40)]
        buf = pixels(row)
        run_map(LIB, buf, keep_tint=1.0, width=len(row), edge_neutral=dm.EDGE_NEUTRAL)
        out = [tuple(buf[4 * i + 2 - k] for k in range(3)) for i in range(len(row))]
        self.assertGreater(out[1][0], out[1][1] + 5, "the mark keeps its pink")
        self.assertEqual(max(out[3]) - min(out[3]), 0, "the fringe turns gray: %r" % (out[3],))

    def test_frame_ends_on_the_first_and_last_rows_take_the_target(self):
        width = 3
        buf = pixels([(152, 152, 153), (40, 40, 40), (40, 40, 40),
                      (152, 152, 153), (40, 40, 40), (40, 40, 40),
                      (190, 190, 192), (40, 40, 40), (40, 40, 40)])
        keyed(LIB, buf, [0xcacbcc], width, dm.WHITE_L, 0x454545)
        firsts = [tuple(buf[4 * (r * width) + 2 - k] for k in range(3)) for r in range(3)]
        self.assertEqual(firsts[0], (0x45, 0x45, 0x45))
        self.assertEqual(firsts[1], (152, 152, 153), "a middle row is left")
        self.assertEqual(firsts[2], (0x45, 0x45, 0x45))

    def test_content_keeps_muted_colors(self):
        node = (106, 160, 106)  # a muted green node: channels spread by 54
        ui, content = pixels([node]), pixels([node])
        run_map(LIB, ui)
        run_map(LIB, content, keep_tint=dm.KEEP_TINT_CONTENT)
        self.assertEqual(ui[0], ui[1])  # gray in the interface
        self.assertGreater(content[1], content[0] + 10, "still green on the canvas")

    def test_stats(self):
        colors = [(255, 255, 255)] * 3 + [(0, 0, 0)] * 2 + [(128, 128, 128)]
        buf = pixels(colors) + pixels([(255, 255, 255)], alpha=10)
        counts = (ctypes.c_int64 * 3)()
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_pixel_stats(ctypes.addressof(array), len(buf) // 4, dm.AUTO_MIN_ALPHA, dm.WHITE_L, dm.BLACK_L, counts)
        self.assertEqual(tuple(counts), (6, 3, 2))


@unittest.skipIf(LIB is None, "native helper not built: run tools/build-native.ps1 (%s)" % DLL)
class KeyedTests(unittest.TestCase):
    def test_light_colors_are_distinct_light_and_opaque(self):
        buf = pixels([(202, 203, 204), (45, 45, 48), (202, 203, 204), (163, 163, 165)]) + pixels([(250, 250, 250)], alpha=10)
        keys = (ctypes.c_uint32 * 4)()
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        found = LIB.freelab_light_colors(ctypes.addressof(array), len(buf) // 4, dm.KEY_MIN_L, dm.AUTO_MIN_ALPHA, keys, 4)
        self.assertEqual(sorted(keys[:found]), sorted([0xcacbcc, 0xa3a3a5]))

    def test_light_colors_stop_at_max_keys(self):
        buf = pixels([(200 + i, 200, 200) for i in range(10)])
        keys = (ctypes.c_uint32 * 3)()
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        self.assertEqual(LIB.freelab_light_colors(ctypes.addressof(array), 10, 0.45, 200, keys, 3), 3)

    def test_map_keyed_maps_only_the_keys(self):
        colors = [(202, 203, 204), (220, 220, 220), (202, 203, 205)]
        buf = pixels(colors)
        keyed(LIB, buf, [0xcacbcc], 3)
        out = [tuple(buf[4 * i + 2 - k] for k in range(3)) for i in range(3)]
        expected = dm.map_rgb(202, 203, 204)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(out[0], expected)), 1)
        self.assertEqual(out[1:], colors[1:])


if __name__ == "__main__":
    unittest.main()
