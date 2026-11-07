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
    lib.freelab_map_anchors.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int, ctypes.c_double,
                                        ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int]
    lib.freelab_map_anchors.restype = ctypes.c_int64
    lib.freelab_defringe.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int]
    lib.freelab_defringe.restype = None
    return lib


LIB = _load()


def pixels(colors, alpha=255):
    return bytearray(b"".join(struct.pack("<BBBB", b, g, r, alpha) for r, g, b in colors))


def run_map(lib, buf, min_l=0.0, ink_below=-1.0, keep_tint=0.0, width=None, edge_neutral=0.0):
    array = (ctypes.c_char * len(buf)).from_buffer(buf)
    count = len(buf) // 4
    lib.freelab_map_lightness(ctypes.addressof(array), count, width or count, dm.DARK_OKL, dm.LIGHT_OKL, min_l,
                              ink_below, keep_tint, edge_neutral)


def anchors(lib, buf, width, mode, keep_tint=0.0, apply=1):
    array = (ctypes.c_char * len(buf)).from_buffer(buf)
    return lib.freelab_map_anchors(ctypes.addressof(array), len(buf) // 4, width, dm.ANCHOR_MODES[mode], dm.DARK_OKL,
                                   dm.LIGHT_OKL, keep_tint, dm.BACKGROUND_OKL, apply)


def rgb_at(buf, i):
    return tuple(buf[4 * i + 2 - k] for k in range(3))


def text_rows(paper, ink, rows=14, width=40, blend=None):
    """A line of "text" on paper: 1-pixel vertical strokes of ink every 6 pixels on rows 3 to 10,
    each with a blend pixel beside it (pixel 1 is ink, pixel 2 the blend, pixel 0 paper, on those rows)."""
    out = []
    for y in range(rows):
        for x in range(width):
            if 3 <= y <= 10 and x % 6 == 1:
                out.append(ink)
            elif 3 <= y <= 10 and x % 6 == 2 and blend is not None:
                out.append(blend)
            else:
                out.append(paper)
    return out


TEXT_ROW = 3 * 40  # the first pixel of the first row with text in text_rows


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
        run_map(LIB, buf, min_l=dm.WHITE_L, ink_below=0.115)  # the pixel-by-pixel ink path, still exported
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

    def test_ink_on_dark_paper_turns_light_and_blends_follow(self):
        paper, ink, half = (41, 41, 41), (0, 0, 0), (20, 20, 20)
        buf = pixels(text_rows(paper, ink, blend=half))
        anchors(LIB, buf, 40, "ink")
        self.assertEqual(rgb_at(buf, 0), paper, "the dark paper stays")
        light = rgb_at(buf, TEXT_ROW + 1)
        self.assertEqual(light, dm.map_rgb(*ink), "black text becomes light text")
        expected = paper[0] + (light[0] - paper[0]) * (paper[0] - half[0]) / float(paper[0])
        self.assertLessEqual(abs(rgb_at(buf, TEXT_ROW + 2)[0] - expected), 2, "smoothing is the same blend of the mapped colors")

    def test_colored_dark_ink_keeps_its_hue(self):
        buf = pixels(text_rows((41, 41, 41), (58, 63, 127)))  # the navy of FontLab's Export Profiles list
        anchors(LIB, buf, 40, "ink")
        r, g, b = rgb_at(buf, TEXT_ROW + 1)
        self.assertGreater(b, r + 30, "still blue")
        self.assertGreater(dm.oklab(r, g, b)[0], 0.6, "and light")

    def test_colored_ink_is_not_smoothing_of_a_lighter_color_it_does_not_touch(self):
        # Export Profiles: navy names, and blue check boxes elsewhere in the list.
        width, colors = 40, []
        for y in range(14):
            for x in range(width):
                if 3 <= y <= 10 and x % 6 == 1 and x < 24:
                    colors.append((58, 63, 127))
                elif 3 <= y <= 6 and 30 <= x <= 33:
                    colors.append((65, 155, 249))
                else:
                    colors.append((41, 41, 41))
        buf = pixels(colors)
        anchors(LIB, buf, width, "ink")
        r, g, b = rgb_at(buf, TEXT_ROW + 1)
        self.assertGreater(dm.oklab(r, g, b)[0], 0.6, "the navy turns light")

    def test_a_logo_in_a_light_row_keeps_its_color_and_smooth_edges(self):
        # A selected light row (turning dark) holding a blue logo, with a half-blend pixel at its edge.
        width, colors = 40, []
        for y in range(14):
            for x in range(width):
                if y < 2 or y > 11:
                    colors.append((41, 41, 41))
                elif 10 <= x <= 15 and 4 <= y <= 9:
                    colors.append((30, 90, 230))
                elif x == 16 and 4 <= y <= 9:
                    colors.append((126, 160, 243))  # halfway between the logo and the row
                else:
                    colors.append((222, 230, 255))
        buf = pixels(colors)
        anchors(LIB, buf, width, "ink")
        row, logo, edge = rgb_at(buf, 5 * width + 25), rgb_at(buf, 5 * width + 12), rgb_at(buf, 5 * width + 16)
        self.assertLess(dm.oklab(*row)[0], 0.4, "the row turns dark")
        self.assertEqual(logo, (30, 90, 230), "the logo as drawn")
        for k in range(3):
            self.assertTrue(min(row[k], logo[k]) - 3 <= edge[k] <= max(row[k], logo[k]) + 3, "its edge between the two: %r" % (edge,))

    def test_light_text_and_dark_surfaces_stay(self):
        colors = text_rows((30, 30, 30), (220, 220, 220), blend=(125, 125, 125))
        buf = pixels(colors)
        self.assertEqual(anchors(LIB, buf, 40, "ink"), 0)
        self.assertEqual(bytes(buf), bytes(pixels(colors)))

    def test_cleartype_fringes_of_light_text_stay(self):
        # Native light text: a blue fringe left of each stroke and a yellow one right of it (seen in FontLab).
        width, colors = 42, []
        for y in range(14):
            for x in range(width):
                band = 3 <= y <= 10
                if band and x % 6 == 1:
                    colors.append((30, 62, 125))
                elif band and x % 6 == 2:
                    colors.append((220, 220, 220))
                elif band and x % 6 == 3:
                    colors.append((188, 188, 125))
                else:
                    colors.append((30, 30, 30))
        buf = pixels(colors)
        self.assertEqual(anchors(LIB, buf, width, "ink"), 0, "light text and its fringes are left as drawn")

    def test_black_text_drawn_on_nothing_turns_light(self):
        # FontLab's Unicode ranges list paints no background: only its black text is opaque.
        buf = bytearray()
        for y in range(14):
            for x in range(40):
                if 3 <= y <= 10 and x % 6 == 1:
                    buf += struct.pack("<BBBB", 0, 0, 0, 255)
                elif 3 <= y <= 10 and x % 6 == 2:
                    buf += struct.pack("<BBBB", 0, 0, 0, 120)
                else:
                    buf += struct.pack("<BBBB", 0, 0, 0, 0)
        anchors(LIB, buf, 40, "ink")
        self.assertEqual(rgb_at(buf, TEXT_ROW + 1), dm.map_rgb(0, 0, 0), "the text is ink, not a background")
        self.assertEqual(rgb_at(buf, TEXT_ROW + 2), dm.map_rgb(0, 0, 0), "its smoothing too, alpha kept")
        self.assertEqual(buf[4 * (TEXT_ROW + 2) + 3], 120)

    def test_a_gray_frame_drawn_on_nothing_stays(self):
        # A glyph-panel field: only its 1-pixel gray frame is opaque.
        buf = bytearray()
        for y in range(19):
            for x in range(72):
                edge = y in (0, 18) or x in (0, 71)
                buf += struct.pack("<BBBB", 74, 74, 74, 255) if edge else struct.pack("<BBBB", 0, 0, 0, 0)
        before = bytes(buf)
        anchors(LIB, buf, 72, "ink")
        self.assertEqual(bytes(buf), before)

    def test_fringes_of_kept_text_are_not_claimed_by_far_ink_pairs(self):
        # A rare navy ClearType pixel inside blue syntax, with only blue around it and black string
        # ink further on: it is paper + blue (kept), not blue + black ink (mapped light).
        width, colors = 20, []
        for y in range(14):
            for x in range(width):
                band = 3 <= y <= 10
                if band and y == 6 and x % 10 == 2:
                    colors.append((30, 30, 78))  # navy fringe
                elif band and x % 10 <= 4:
                    colors.append((50, 88, 173) if (x + y) % 2 else (60, 100, 180))  # blue strokes, no surface
                elif band and x % 10 == 7:
                    colors.append((10, 0, 10))  # black ink
                else:
                    colors.append((30, 30, 30))
        buf = pixels(colors)
        anchors(LIB, buf, width, "ink")
        r, g, b = rgb_at(buf, 6 * width + 2)
        self.assertLess(dm.oklab(r, g, b)[0], 0.4, "stays dark: smoothing between the paper and the blue")
        self.assertLessEqual(max(r, g, b) - min(r, g, b), 40, "its navy tint is gone: the plain blend of the two")

    def test_a_tick_on_a_blue_box_stays_white_and_an_unticked_box_gets_a_frame(self):
        # A list delegate's check boxes on nothing: a white tick on a blue box, and a white square.
        width, rows, buf = 40, 14, bytearray()
        for y in range(rows):
            for x in range(width):
                if 1 <= y <= 12 and 1 <= x <= 12:
                    tick = (y == 7 and 4 <= x <= 9) or (x == 6 and 4 <= y <= 9)
                    buf += struct.pack("<BBBB", 255, 255, 255, 255) if tick else struct.pack("<BBBB", 0xf9, 0x9b, 0x41, 255)
                elif 1 <= y <= 12 and 21 <= x <= 32:
                    buf += struct.pack("<BBBB", 255, 255, 255, 255)
                else:
                    buf += struct.pack("<BBBB", 0, 0, 0, 0)
        anchors(LIB, buf, width, "ink")
        self.assertEqual(rgb_at(buf, 7 * width + 6), (255, 255, 255), "the tick")
        self.assertEqual(rgb_at(buf, 7 * width + 21), (0x99, 0x99, 0x99), "the unticked box's edge: a frame")
        self.assertLess(rgb_at(buf, 7 * width + 26)[0], 100, "its inside: dark")

    def test_subpixel_text_keeps_each_channel_coverage(self):
        # ClearType black text on white paper: a fringe pixel's channels are the paper times (1 - coverage).
        width, colors = 40, []
        for y in range(14):
            for x in range(width):
                if 3 <= y <= 10 and x % 6 == 1:
                    colors.append((0, 0, 0))
                elif 3 <= y <= 10 and x % 6 == 2:
                    colors.append((255, 128, 0))  # coverage 0, 0.5, 1
                else:
                    colors.append((255, 255, 255))
        buf = pixels(colors)
        anchors(LIB, buf, width, "subpixel")
        paper, text = rgb_at(buf, 0), rgb_at(buf, TEXT_ROW + 1)
        self.assertLess(paper[0], 80, "the paper turns dark")
        self.assertGreater(text[0], 180, "the text light")
        r, g, b = rgb_at(buf, TEXT_ROW + 2)
        self.assertLessEqual(abs(r - paper[0]), 2, "no red coverage: the paper")
        self.assertLessEqual(abs(b - text[2]), 2, "full blue coverage: the text")
        self.assertLessEqual(abs(g - (paper[1] + text[1]) / 2.0), 3, "half green coverage: halfway")

    def test_gray_fringes_of_colored_text_are_not_dim_marks(self):
        # Blue syntax on a dark editor paper fringes in gray-teal (#59757d), which must not be lifted.
        paper, blue, fringe = (30, 30, 30), (69, 117, 173), (89, 117, 125)
        buf = pixels(text_rows(paper, blue, blend=fringe))
        anchors(LIB, buf, 40, "ink")
        self.assertEqual(rgb_at(buf, TEXT_ROW + 2), fringe)

    def test_light_badges_turn_dark_without_touching_light_text_beside_them(self):
        # Gray text (192) on a dark row, and a gray badge (160) with black text: all on one gray line.
        width, rows = 60, 14
        colors = []
        for y in range(rows):
            for x in range(width):
                if 30 <= x < 56 and 2 <= y < 12:
                    colors.append((0, 0, 0) if x % 5 == 2 and 5 <= y < 9 else (160, 160, 160))
                elif x < 20 and x % 4 == 1:
                    colors.append((192, 192, 192))
                elif x < 20 and x % 4 == 2:
                    colors.append((90, 90, 90))  # smoothing of the light text
                else:
                    colors.append((31, 31, 31))
        buf = pixels(colors)
        anchors(LIB, buf, width, "ink")
        self.assertEqual(rgb_at(buf, 1), (192, 192, 192), "light text stays")
        self.assertEqual(rgb_at(buf, 2), (90, 90, 90), "and so does its smoothing")
        badge = rgb_at(buf, 2 * width + 31)
        self.assertLess(badge[0], 120, "the badge turns dark: %r" % (badge,))
        self.assertGreater(rgb_at(buf, 6 * width + 32)[0], 150, "its black text turns light")

    def test_all_mode_maps_white_paper_and_black_text(self):
        buf = pixels(text_rows((255, 255, 255), (0, 0, 0), blend=(128, 128, 128)))
        anchors(LIB, buf, 40, "all")
        white, black, half = rgb_at(buf, 0), rgb_at(buf, TEXT_ROW + 1), rgb_at(buf, TEXT_ROW + 2)
        self.assertEqual(white, dm.map_rgb(255, 255, 255))
        self.assertEqual(black, dm.map_rgb(0, 0, 0))
        self.assertLessEqual(abs(half[0] - (white[0] + black[0]) / 2.0), 2)

    def test_detection_writes_nothing(self):
        colors = text_rows((41, 41, 41), (0, 0, 0))
        buf = pixels(colors)
        self.assertGreater(anchors(LIB, buf, 40, "ink", apply=0), 0)
        self.assertEqual(bytes(buf), bytes(pixels(colors)))

    def test_keyed_also_maps_near_white(self):
        buf = pixels([(250, 250, 250), (60, 60, 60)])
        keyed(LIB, buf, [0xcacbcc], 2, dm.WHITE_L)
        self.assertLess(buf[0], 60, "a white frame corner turns dark")
        self.assertEqual(buf[4], 60)

    def test_edges_lose_tint_flat_areas_keep_it(self):
        # One row: a flat pink mark area, then a ClearType-like fringe pixel next to dark text.
        row = [(255, 205, 205)] * 3 + [(235, 200, 160), (40, 40, 40)]
        buf = pixels(row)
        run_map(LIB, buf, keep_tint=1.0, width=len(row), edge_neutral=0.12)
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

    def test_defringe(self):
        g, text = (52, 52, 52), (172, 172, 172)
        left, right = (190, 132, 77), (77, 132, 190)  # a gray stem's fringes: the strongest channel flips
        dark_blue = (0, 78, 154)  # a channel below the ground
        light_blue, blue_edge = (67, 133, 214), (56, 85, 118)  # colored text: a run of one strongest channel
        rows = [[g, left, text, right, g, g, g],
                [g, dark_blue, g, blue_edge, light_blue, blue_edge, g]]
        buf = pixels(rows[0] + rows[1])
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_defringe(ctypes.addressof(array), len(buf) // 4, 7, dm.DEFRINGE_MAX_SPREAD)
        self.assertEqual(buf[:28], pixels([g, (133, 133, 133), text, (133, 133, 133), g, g, g]),
                         "gray text's fringes: the mean of their channels")
        self.assertEqual(buf[28:], pixels(rows[1]), "colors darker than the ground and colored text unchanged")


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
