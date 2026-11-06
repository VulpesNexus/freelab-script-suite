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
    lib.freelab_map_lightness.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_double, ctypes.c_double,
                                          ctypes.c_double, ctypes.c_double]
    lib.freelab_pixel_stats.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int, ctypes.c_double,
                                        ctypes.c_double, ctypes.POINTER(ctypes.c_int64)]
    lib.freelab_light_colors.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_double, ctypes.c_int,
                                         ctypes.POINTER(ctypes.c_uint32), ctypes.c_int64]
    lib.freelab_light_colors.restype = ctypes.c_int64
    lib.freelab_map_keyed.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int64,
                                      ctypes.c_double, ctypes.c_double]
    return lib


LIB = _load()


def pixels(colors, alpha=255):
    return bytearray(b"".join(struct.pack("<BBBB", b, g, r, alpha) for r, g, b in colors))


def run_map(lib, buf, min_l=0.0, max_dark_l=-1.0):
    array = (ctypes.c_char * len(buf)).from_buffer(buf)
    lib.freelab_map_lightness(ctypes.addressof(array), len(buf) // 4, dm.DARK_OKL, dm.LIGHT_OKL, min_l, max_dark_l)


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

    def test_edges_map_near_white_and_near_black_only(self):
        colors = [(255, 255, 255), (0, 0, 0), (30, 30, 30), (40, 160, 60), (12, 12, 12)]  # paper #1e1e1e, green syntax
        buf = pixels(colors)
        run_map(LIB, buf, min_l=dm.WHITE_L, max_dark_l=dm.EDGES_MAX_DARK_L)
        out = [tuple(buf[4 * i + 2 - k] for k in range(3)) for i in range(len(colors))]
        self.assertEqual(out[0], dm.map_rgb(255, 255, 255))
        self.assertEqual(out[1], dm.map_rgb(0, 0, 0))
        self.assertEqual(out[2:4], colors[2:4], "the paper and the syntax colors stay")
        self.assertEqual(out[4], dm.map_rgb(12, 12, 12))

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
        keys = (ctypes.c_uint32 * 1)(0xcacbcc)
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_map_keyed(ctypes.addressof(array), 3, keys, 1, dm.DARK_OKL, dm.LIGHT_OKL)
        out = [tuple(buf[4 * i + 2 - k] for k in range(3)) for i in range(3)]
        expected = dm.map_rgb(202, 203, 204)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(out[0], expected)), 1)
        self.assertEqual(out[1:], colors[1:])


if __name__ == "__main__":
    unittest.main()
