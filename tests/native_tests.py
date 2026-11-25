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

    def test_dark_gray_text_drawn_on_nothing_turns_light(self):
        # The font window's categories: headers and empty categories in dark gray, close to the dark
        # gray beneath, and a light badge more frequent than that text (taken for the paper, it made
        # the text a "fringe" between the badge and a red flag).
        width, buf = 60, bytearray()
        for y in range(40):
            for x in range(width):
                gray = (0x3c, 0x3c, 0x3c) if x < 24 else (0, 0, 0)  # gray headers, black items
                if 3 <= y <= 10 and x % 6 == 1:
                    buf += struct.pack("<BBBB", gray[2], gray[1], gray[0], 255)
                elif 3 <= y <= 10 and x % 6 == 2:
                    buf += struct.pack("<BBBB", gray[2], gray[1], gray[0], 120)
                elif 30 <= y <= 32:
                    buf += struct.pack("<BBBB", 0xd5, 0xcb, 0xcb, 255)  # the badges
                elif y == 35 and x < 3:
                    buf += struct.pack("<BBBB", 0x2c, 0x27, 0xc1, 255)  # the flag's red
                else:
                    buf += struct.pack("<BBBB", 0, 0, 0, 0)
        anchors(LIB, buf, width, "ink")
        text = rgb_at(buf, 3 * width + 1)
        self.assertGreater(min(text), 0x90, "light on the dark interface: %r" % (text,))
        self.assertGreater(min(rgb_at(buf, 3 * width + 2)), 0x90, "its smoothing too")
        self.assertEqual(buf[4 * (3 * width + 2) + 3], 120, "alpha kept")

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

    def test_dark_gray_lines_apart_from_red_lines_are_lifted(self):
        # FontLab's Output panel: its output in dark gray (#404040), its errors in red, each on lines of
        # its own. The gray fits a blend of the paper and the red loosely, and was kept as the red's
        # smoothing: unreadable on the dark paper whenever an error was shown. Smoothing touches its text.
        paper, gray, red = (30, 30, 30), (64, 64, 64), (255, 0, 0)
        buf = pixels(text_rows(paper, gray) + text_rows(paper, red) + text_rows(paper, gray))
        anchors(LIB, buf, 40, "ink")
        for row in (TEXT_ROW, TEXT_ROW + 28 * 40):
            r, g, b = rgb_at(buf, row + 1)
            self.assertGreater(dm.oklab(r, g, b)[0], 0.6, "the gray text is light enough to read")
        self.assertEqual(rgb_at(buf, TEXT_ROW + 14 * 40 + 1), red, "the red stays")
        self.assertEqual(rgb_at(buf, 0), paper)

    def test_cleartype_fringes_of_dark_red_text_stay_dark(self):
        # Owner's report 155: FontLab's Output panel writes compiler errors in a dark red (about #8b0000) on its
        # dark paper. The red is made lighter as ink; its ClearType fringes, each channel at its own coverage
        # (#340c00: little red, more green and blue gone), were mapped alone as dark ink and turned light pink
        # (#eac2b6), light dots inside every letter. They are drawn again, channel by channel, from the paper
        # and the text as they come out.
        paper, red = (30, 30, 30), (139, 0, 0)
        covs = [(0.2, 0.6, 1.0), (1.0, 0.6, 0.2), (0.6, 0.3, 0.1)]
        width = 6 * len(covs)
        colors = []
        for y in range(14):
            for x in range(width):
                k = x // 6
                if 3 <= y <= 10 and x % 6 == 1:
                    colors.append(red)
                elif 3 <= y <= 10 and x % 6 == 2:
                    colors.append(tuple(int(round(p + (c - p) * t)) for p, c, t in zip(paper, red, covs[k])))
                else:
                    colors.append(paper)
        buf = pixels(colors)
        anchors(LIB, buf, width, "ink")
        text = rgb_at(buf, 3 * width + 1)
        self.assertGreater(dm.oklab(*text)[0], 0.6, "the dark red made light enough to read: %r" % (text,))
        self.assertGreater(text[0], text[1] + 60, "and still red")
        for k, cov in enumerate(covs):
            r, g, b = rgb_at(buf, 3 * width + 6 * k + 2)
            self.assertLess(dm.oklab(r, g, b)[0], dm.oklab(*text)[0] + 0.02,
                            "a fringe (%r) no lighter than its text: %r" % (cov, (r, g, b)))
            if k == 2:
                continue  # (its colors fit a blend of the others: resolved as that blend, dark enough)
            for channel, value, t in zip("rgb", (r, g, b), cov):
                want = paper["rgb".index(channel)] + t * (text["rgb".index(channel)] - paper["rgb".index(channel)])
                self.assertLessEqual(abs(value - want), 3, "%s at its own coverage %.1f: %r" % (channel, t, (r, g, b)))
        self.assertEqual(rgb_at(buf, 0), paper)

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

    def badge_list(self, frame_box=False, gray=(160, 162, 164)):
        """A white list (light mode): black text, a mid-gray badge (#a0a2a4) with white digits and their
        ClearType fringes (Anchors & Pins' coordinates), and, with frame_box, a white box framed in that
        gray (11 pixels inside). Returns (buffer, width)."""
        white, black = (255, 255, 255), (0, 0, 0)
        blue, amber = (176, 208, 240), (239, 208, 179)  # (the digits' fringes)
        width, rows = 90, 22
        image = dict(((x, y), white) for x in range(width) for y in range(rows))
        for y in range(6, 14):  # black text at the left
            for x in range(4, 30, 4):
                image[(x, y)] = black
        for y in range(4, 16):  # the badge, 34 by 12, its digits' stems and bars in white
            for x in range(50, 84):
                image[(x, y)] = gray
        for start in range(54, 80, 6):
            for y in range(7, 13):
                image[(start + 2, y)] = white
                image[(start + 1, y)], image[(start + 3, y)] = blue, amber
            for x in range(start + 1, start + 4):
                image[(x, 7)] = image[(x, 12)] = white
        if frame_box:
            for y in range(4, 17):
                for x in range(34, 47):
                    edge = x in (34, 46) or y in (4, 16)
                    image[(x, y)] = gray if edge else white
        colors = [image[(x, y)] for y in range(rows) for x in range(width)]
        return pixels(colors), width

    def test_white_text_on_a_gray_badge_stays_light(self):
        # Anchors & Pins (2026-11-15): the digits' white is the list's white; mapped with it, the digits
        # turned dark on the gray badge, their light fringes around them.
        buf, width = self.badge_list()
        anchors(LIB, buf, width, "ink")
        self.assertLess(rgb_at(buf, 0)[0], 60, "the list turns dark")
        self.assertGreater(rgb_at(buf, 8 * width + 4)[0], 180, "its black text light")
        stem, bar = rgb_at(buf, 9 * width + 56), rgb_at(buf, 7 * width + 56)
        badge = rgb_at(buf, 5 * width + 52)
        for name, pixel in (("a stem", stem), ("a bar", bar)):
            self.assertGreater(min(pixel), 230, "%s of a digit stays white: %r" % (name, pixel))
        self.assertLess(max(badge), max(stem) - 60, "and stands out on its badge: %r" % (badge,))
        fringe = rgb_at(buf, 9 * width + 55)
        self.assertGreater(sum(fringe), sum(badge), "its fringe lies between the badge and the digit: %r" % (fringe,))

    def test_a_kept_badge_too_light_for_its_text_is_drawn_darker(self):
        # (live, 2026-11-16: white digits on Anchors & Pins' kept #a0a2a4, about 2.6:1, read weakly)
        def luminance(rgb):
            linear = [c / 255.0 / 12.92 if c <= 10 else ((c / 255.0 + 0.055) / 1.055) ** 2.4 for c in rgb]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        for gray in ((128, 128, 128), (118, 120, 122)):  # (kept as drawn: no light surface to turn dark)
            buf, width = self.badge_list(gray=gray)
            anchors(LIB, buf, width, "ink")
            badge, edge = rgb_at(buf, 5 * width + 52), rgb_at(buf, 4 * width + 50)
            self.assertLessEqual((1.05 / (luminance(badge) + 0.05)), 6.5, "about the Classes badge's gray: %r" % (badge,))
            self.assertGreaterEqual(1.05 / (luminance(badge) + 0.05), 4.5, "white on it at 4.5:1 at least: %r" % (badge,))
            self.assertEqual(edge, badge, "the whole badge")
            self.assertLessEqual(max(badge) - min(badge), max(gray) - min(gray) + 1, "in its own hue")
            self.assertEqual(rgb_at(buf, 9 * width + 56), (255, 255, 255), "its digits white")
            fringe = rgb_at(buf, 9 * width + 55)
            self.assertLessEqual(max(fringe) - min(fringe), 3, "their smoothing gray, no ClearType fringe: %r" % (fringe,))
            self.assertGreater(fringe[0], badge[0], "between the badge and the digit")
        buf, width = self.badge_list(gray=(140, 140, 140))
        anchors(LIB, buf, width, "ink")
        self.assertEqual(rgb_at(buf, 5 * width + 52), (116, 116, 116), "one dark enough as it comes out is left so")

    def test_a_translucent_edge_of_the_badge_s_gray_does_not_hide_it(self):
        # (the row's color cache once kept the answer of the run's first pixel, its alpha included: a
        # translucent edge of the badge's own gray made the rest of the row no badge)
        buf, width = self.badge_list()
        for y in range(4, 16):
            buf[4 * (y * width + 50) + 3] = 100  # the badge's left edge: its gray, at alpha 100
        anchors(LIB, buf, width, "ink")
        self.assertGreater(min(rgb_at(buf, 9 * width + 56)), 230, "the digits stay white")

    def test_badge_text_smoothing_meets_the_badge_as_drawn(self):
        buf, width = self.badge_list()
        half = 9 * width + 61  # a stem's left fringe, made halfway between the badge and white
        for k, value in enumerate((207, 208, 209)):
            buf[4 * half + 2 - k] = value
        anchors(LIB, buf, width, "ink")
        badge = rgb_at(buf, 9 * width + 59)  # the badge beside it, as the mapping drew it
        for channel, got in enumerate(rgb_at(buf, half)):
            self.assertLessEqual(abs(got - (badge[channel] + 255) / 2.0), 2.5, "halfway from the badge to white")

    def test_a_gray_framed_white_box_is_no_badge(self):
        buf, width = self.badge_list(frame_box=True)
        anchors(LIB, buf, width, "ink")
        self.assertLess(rgb_at(buf, 10 * width + 40)[0], 80, "its inside turns dark with the list")
        self.assertGreater(min(rgb_at(buf, 9 * width + 56)), 230, "the badge's digits stay white beside it")

    def test_the_white_inside_gray_letters_turns_dark(self):
        # Gray text (#a0a2a4, the badge's gray, as a word's strokes): its counters are the list's white.
        gray, white = (160, 162, 164), (255, 255, 255)
        width, colors = 40, []
        for y in range(14):
            for x in range(width):
                ring = 3 <= y <= 9 and x % 6 in (1, 4) or y in (3, 9) and x % 6 in (2, 3)
                colors.append(gray if ring else white)
        buf = pixels(colors)
        anchors(LIB, buf, width, "ink")
        self.assertLess(rgb_at(buf, 6 * width + 2)[0], 80, "an o's counter turns dark with the paper")

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

    def test_light_text_on_a_kept_color_stays(self):
        # a selected font cell: white paper above, its blue header holding white text (content keeps colors)
        width, white, blue = 24, (255, 255, 255), (31, 98, 162)
        rows = [[white] * width for _ in range(3)]
        for y in range(3, 14):
            rows.append([white if 7 <= y <= 9 and 10 <= x <= 13 else blue for x in range(width)])
        buf = pixels([px for row in rows for px in row])
        anchors(LIB, buf, width, "all", keep_tint=dm.KEEP_TINT_CONTENT)
        at = lambda x, y: tuple(buf[4 * (y * width + x) + k] for k in (2, 1, 0))
        self.assertEqual(at(11, 8), white, "the text on the header stays white")
        self.assertEqual(at(2, 8), blue, "the header keeps its blue")
        self.assertLess(max(at(5, 1)), 100, "the paper turns dark")

    def defringe(self, rows):
        buf = pixels([px for row in rows for px in row])
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_defringe(ctypes.addressof(array), len(buf) // 4, len(rows[0]), dm.DEFRINGE_MAX_SPREAD)
        width = 4 * len(rows[0])
        return [buf[i:i + width] for i in range(0, len(buf), width)]

    def test_defringe(self):
        g, text, field = (52, 52, 52), (172, 172, 172), (20, 20, 20)
        left, right = (190, 132, 77), (77, 132, 190)  # a gray stem's fringes: the strongest channel flips
        dark_blue = (0, 78, 154)  # a channel below the ground
        light_blue, blue_edge = (67, 133, 214), (56, 85, 118)  # colored text: a run of one strongest channel
        rows = [[g, left, text, right, g, g, g, field],
                [g, dark_blue, g, blue_edge, light_blue, blue_edge, g, g],
                [g, g, left, right, g, g, g, g]]  # a thin stem: no neutral core, the flip tells it
        out = self.defringe(rows)
        mean_left, mean_pair = (133, 133, 133), (133, 133, 133)
        self.assertEqual(out[0], pixels([g, mean_left, text, (133, 133, 133), g, g, g, field]),
                         "gray text's fringes beside its core: the mean of their channels")
        self.assertEqual(out[1], pixels(rows[1]), "colors darker than the ground and colored text unchanged")
        self.assertEqual(out[2], pixels([g, g, mean_pair, mean_pair, g, g, g, g]))

    def test_defringe_keeps_lone_colors(self):
        g, line, blend = (45, 45, 48), (61, 111, 180), (91, 43, 43)
        rows = [[g, g, line, g, g, blend, g, (14, 14, 14)]] * 3  # a vertical blue line, a red edge, a dark pixel
        out = self.defringe(rows)
        self.assertEqual(b"".join(out), pixels([px for row in rows for px in row]),
                         "no text core beside them: a colored line and a swatch edge stay colored")

    def test_defringe_keeps_colored_text_and_bars(self):
        g, light = (40, 40, 40), (200, 200, 200)
        green_left, green_right = (150, 200, 60), (60, 190, 150)  # green text's own ClearType edges: a flip
        bar = [(60, 170, 100)] * 6 + [(230, 150, 40)] * 2  # a coverage bar: green, then orange
        rows = [[g, green_left, green_right, g, g, g, g, g, g, g],
                [g] + bar + [light]]  # (a light neutral right after the bar)
        out = self.defringe(rows)
        self.assertEqual(out[0], pixels(rows[0]), "colored text's edges add up to its color: kept")
        self.assertEqual(out[1], pixels(rows[1]), "a run longer than text edges that adds up to a color: a bar, kept")

    def test_defringe_grays_small_text_edges_across_letters(self):
        g = (30, 30, 30)
        warm, cool = (170, 120, 60), (60, 120, 170)  # small light text: edges running across letters, no core
        run = [warm, cool] * 5
        out = self.defringe([[g] + run + [g]])
        mean = (117, 117, 117)  # (170 + 120 + 60) / 3, rounded
        self.assertEqual(out[0], pixels([g] + [mean] * 10 + [g]))


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

    @staticmethod
    def sidebar(width=64, height=96):
        """A list's rows drawn on nothing, for a light ground (the font window's sidebar): a dark gray
        glyph icon, a dark gray badge with a white letter, black text, and gray sub-item text, over\n        empty rows (no color covers enough to be its background)."""
        icon, badge, white, black, gray = (64, 65, 66), (64, 65, 66), (255, 255, 255), (0, 0, 0), (124, 124, 124)
        image = {}
        for y in range(4, 14):  # the icon: a frame of strokes, 8 by 10, a third filled
            for x in range(4, 12):
                if x in (4, 11) or y in (4, 8, 13):
                    image[(x, y)] = icon
        for y in range(4, 20):  # the badge: 16 by 16, a white bar for its letter
            for x in range(20, 36):
                image[(x, y)] = white if 26 <= x <= 27 and 7 <= y <= 16 else badge
        for y in range(4, 14):  # black text and gray text: 1-pixel strokes
            for x in range(40, 50, 3):
                image[(x, y)] = black
            for x in range(52, 62, 3):
                image[(x, y)] = gray
        out = bytearray()
        for y in range(height):
            for x in range(width):
                color = image.get((x, y))
                out += struct.pack("<BBBB", color[2], color[1], color[0], 255) if color else b"\0\0\0\0"
        return out

    def test_list_mode_maps_glyph_icons_and_gray_rows_on_nothing(self):
        width = 64
        ink, listed = self.sidebar(), self.sidebar()
        anchors(LIB, ink, width, "ink")
        anchors(LIB, listed, width, "list")
        at = lambda buf, x, y: rgb_at(buf, y * width + x)
        self.assertEqual(at(ink, 4, 6), (64, 65, 66), "ink mode: a dark surface on nothing stays")
        self.assertGreater(at(listed, 4, 6)[0], 150, "list mode: the glyph icon turns light")
        self.assertEqual(at(listed, 21, 5), (64, 65, 66), "the badge stays as drawn")
        self.assertEqual(at(listed, 26, 10), (255, 255, 255), "its white letter too")
        self.assertGreater(at(listed, 40, 6)[0], 150, "black text turns light")
        self.assertEqual(at(ink, 52, 6), (124, 124, 124), "ink mode: mid gray on nothing stays")
        self.assertGreater(at(listed, 52, 6)[0], 150, "list mode: gray sub-item text turns light")

    def test_list_mode_thins_only_the_edges_it_mapped(self):
        # On nothing: black text (opaque) with its smoothing beside it, a smoothing pixel with nothing more
        # opaque beside it, a block of text drawn translucent throughout (a gray sub-item), and light text
        # with its smoothing, kept as drawn.
        width, buf = 40, bytearray()
        for y in range(14):
            for x in range(width):
                if 3 <= y <= 10 and x % 6 == 1:
                    buf += struct.pack("<BBBB", 0, 0, 0, 255)
                elif 3 <= y <= 10 and x % 6 in (2, 4):
                    buf += struct.pack("<BBBB", 0, 0, 0, 120)
                elif 11 <= y <= 13 and 30 <= x < 36:
                    buf += struct.pack("<BBBB", 0, 0, 0, 153)
                elif y == 0 and x < 20 and x % 2 == 0:
                    buf += struct.pack("<BBBB", 192, 192, 192, 255)
                elif y == 0 and x < 20:
                    buf += struct.pack("<BBBB", 192, 192, 192, 120)
                else:
                    buf += struct.pack("<BBBB", 0, 0, 0, 0)
        anchors(LIB, buf, width, "list")
        alpha = lambda x, y: buf[4 * (y * width + x) + 3]
        self.assertEqual(rgb_at(buf, TEXT_ROW + 2), dm.map_rgb(0, 0, 0), "the smoothing turns light")
        self.assertLess(alpha(2, 3), 100, "and is thinned, beside the more opaque text")
        self.assertEqual(alpha(4, 3), 120, "nothing more opaque beside it: as drawn")
        self.assertEqual(rgb_at(buf, 12 * width + 32), dm.map_rgb(0, 0, 0), "the translucent block turns light")
        self.assertEqual((alpha(32, 12), alpha(30, 12)), (153, 153), "its core and its edge keep their coverage")
        self.assertEqual(rgb_at(buf, 1), (192, 192, 192), "light text stays")
        self.assertEqual(alpha(1, 0), 120, "its smoothing, not mapped, is not thinned")

    def test_list_mode_leaves_the_counters_of_light_text_on_a_dark_row(self):
        # Export Profiles: navy names drawn on nothing, and the selected row FontLab paints dark itself
        # (#313131) with light text. The row's color closed off inside each letter is a small shape of a
        # dark gray: mapped as a glyph icon, it filled the letters with light gray.
        width, rows, buf = 220, 240, bytearray()  # the row a small part of the list: no background of its own
        row, text, smooth, navy = (0x31, 0x31, 0x31), (0xdb, 0xdb, 0xdb), (0x86, 0x86, 0x86), (58, 63, 127)
        for y in range(rows):
            for x in range(width):
                letter = (x - 20) % 12 if 20 <= x < 200 else 99  # each letter: a 6 by 8 ring, smoothing at its right
                if 10 <= y < 30:
                    if 14 <= y <= 21 and letter < 6:
                        color = row if 2 <= letter <= 3 and 16 <= y <= 19 else text
                    elif 14 <= y <= 21 and letter == 6:
                        color = smooth
                    else:
                        color = row
                    buf += struct.pack("<BBBB", color[2], color[1], color[0], 255)
                elif 2 <= y <= 7 and x % 6 == 1:
                    buf += struct.pack("<BBBB", navy[2], navy[1], navy[0], 255)
                elif 2 <= y <= 7 and x % 6 == 2:
                    buf += struct.pack("<BBBB", navy[2], navy[1], navy[0], 120)
                else:
                    buf += struct.pack("<BBBB", 0, 0, 0, 0)
        before = bytes(buf)
        anchors(LIB, buf, width, "list")
        r, g, b = rgb_at(buf, 3 * width + 1)
        self.assertGreater(dm.oklab(r, g, b)[0], 0.6, "the navy name turns light")
        self.assertGreater(b, r + 30, "and stays blue")
        row_bytes = slice(4 * 10 * width, 4 * 30 * width)
        self.assertEqual(rgb_at(buf, 17 * width + 22), row, "a letter's counter stays the row's color")
        self.assertEqual(rgb_at(buf, 17 * width + 20), text, "the light text as drawn")
        self.assertEqual(rgb_at(buf, 17 * width + 26), smooth, "its smoothing too")
        self.assertEqual(bytes(buf[row_bytes]), before[row_bytes], "the whole row as FontLab painted it")

    @staticmethod
    def features(hover=True):
        """Preview Features' list as FontLab paints it for a dark interface, on its own dark base: rows of
        light gray ClearType text (a full stroke between a navy and a yellowish fringe), a dark gray ring
        at the left of each, and the row under the pointer (rows 60 to 71) near-white, with the same light
        gray text between its pale fringes, a gray ring, and a checked mark's blue disk."""
        base, text, ring, band = (0x1e, 0x1e, 0x1e), (0xdb, 0xdb, 0xdb), (0x4f, 0x4f, 0x4f), (0xe9, 0xf0, 0xff)
        left, right = (0x1e, 0x3e, 0x7c), (0xbb, 0xbb, 0x7c)  # the text's fringes on the base,
        pale_left, pale_right = (0xe7, 0xf0, 0xff), (0xe9, 0xec, 0xed)  # and on the near-white row
        band_ring, disk = (0xb4, 0xb8, 0xbf), (0x41, 0x9b, 0xf9)
        width, rows, out = 120, 96, []
        for y in range(rows):
            line, top = y % 12, y - y % 12
            on_band = hover and top == 60
            for x in range(width):
                color = band if on_band else base
                if 2 <= line <= 9 and 4 <= x <= 11 and (line in (2, 9) or x in (4, 11)):
                    color = band_ring if on_band else ring
                elif on_band and 2 <= line <= 9 and 60 <= x <= 67:
                    color = disk
                elif 3 <= line <= 8 and 20 <= x < 56 and x % 6 == 2:
                    color = pale_left if on_band else left
                elif 3 <= line <= 8 and 20 <= x < 56 and x % 6 == 3:
                    color = text
                elif 3 <= line <= 8 and 20 <= x < 56 and x % 6 == 4:
                    color = pale_right if on_band else right
                out.append(color)
        return width, pixels(out)

    def test_light_text_and_rings_on_a_dark_list_with_one_near_white_row(self):
        # The near-white row made the light text on the dark rows a blend of that row and the text's own
        # yellowish fringe (which lies only on the dark rows), and the rings a blend of the dark base and
        # a pale fringe of the row's text (which lies only on that row): both were redrawn as blends with
        # the row's colors as they turn dark, dark on dark.
        text, ring, band = (0xdb, 0xdb, 0xdb), (0x4f, 0x4f, 0x4f), dm.map_rgb(0xe9, 0xf0, 0xff)
        for mode in ("list", "ink"):
            width, buf = self.features()
            anchors(LIB, buf, width, mode)
            at = lambda x, y: rgb_at(buf, y * width + x)
            self.assertEqual(at(0, 0), (0x1e, 0x1e, 0x1e), "the dark base stays")
            self.assertEqual(at(21, 5), text, "%s: the light text on a dark row as painted" % mode)
            self.assertGreaterEqual(min(at(4, 5)), ring[0], "%s: a ring no darker than painted" % mode)
            self.assertEqual(len(set(at(4, 5))), 1, "and gray")
            self.assertEqual(at(100, 65), band, "the near-white row turns dark, as any light surface")
            self.assertLess(max(band), 0x40)
            self.assertEqual(at(21, 65), text, "its light text stays, readable on it now")
            # its smoothing: the same share of the way from the row to the text (the left fringe is nearly
            # the row's color, the right one over a third of the way)
            self.assertGreaterEqual(min(at(20, 65)), max(band), "the text's faint smoothing is no darker than the row")
            self.assertLess(max(at(20, 65)), max(band) + 20)
            self.assertGreater(min(at(22, 65)), max(band) + 40, "its stronger smoothing is lighter than the row")
            self.assertLess(max(at(22, 65)), text[0] - 40, "and darker than the text")
            self.assertGreater(min(at(4, 65)), max(band) + 20, "the row's ring shows on it")
            self.assertEqual(at(62, 65), (0x41, 0x9b, 0xf9), "the blue disk stays")
            # with no row under the pointer, the dark rows come out the same
            width, plain = self.features(hover=False)
            anchors(LIB, plain, width, mode)
            self.assertEqual(bytes(plain[:4 * 60 * width]), bytes(buf[:4 * 60 * width]), "%s: the same with no near-white row" % mode)

    def test_with_no_anchor_everything_mapped_maps_each_pixel(self):
        # No color three times (a gray ramp, one pixel): where every color is mapped, each pixel is mapped
        # on its own; ink still maps only stray whites
        ramp = [(g, g, g) for g in range(256)]
        buf = pixels(ramp)
        anchors(LIB, buf, 256, "all")
        for i, rgb in enumerate(ramp):
            self.assertEqual(rgb_at(buf, i), dm.map_rgb(*rgb), rgb)
        for mode in ("all", "icon", "subpixel"):
            one = pixels([(0, 0, 0)])
            anchors(LIB, one, 1, mode)
            self.assertEqual(rgb_at(one, 0), dm.map_rgb(0, 0, 0), mode)
        one = pixels([(0, 0, 0), (255, 255, 255)])
        anchors(LIB, one, 2, "ink")
        self.assertEqual(rgb_at(one, 0), (0, 0, 0), "ink: dark on the dark interface is right as it is")
        self.assertEqual(rgb_at(one, 1), dm.map_rgb(255, 255, 255), "a stray white is not")


@unittest.skipIf(LIB is None, "native helper not built: run tools/build-native.ps1 (%s)" % DLL)
class ReviewOfNovember24Tests(unittest.TestCase):
    def map(self, rows, mode, tint):
        width = len(rows[0])
        buf = pixels([color for row in rows for color in row])
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_map_anchors(ctypes.addressof(array), len(buf) // 4, width, mode, dm.DARK_OKL, dm.LIGHT_OKL, tint,
                                dm.DARK_OKL, 1)
        return [[tuple(reversed(struct.unpack_from("<BBB", buf, 4 * (y * width + x)))) for x in range(width)]
                for y in range(len(rows))]

    def test_the_darkest_channel_is_a_strokes_gray(self):
        """A panel's title on a narrow panel: ClearType's thin capitals came out uneven as the channels' mean."""
        buf = pixels([(131, 190, 249), (218, 161, 103), (73, 73, 73), (210, 211, 213)]) + pixels([(10, 200, 30)], alpha=7)
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_gray_darkest.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        LIB.freelab_gray_darkest(ctypes.addressof(array), len(buf) // 4)
        self.assertEqual([tuple(buf[4 * i:4 * i + 4]) for i in range(5)],
                         [(131, 131, 131, 255), (103, 103, 103, 255), (73, 73, 73, 255), (210, 210, 210, 255), (10, 10, 10, 7)])

    def test_light_text_on_a_gray_pill_stays_lighter_than_its_pill_on_a_canvas(self):
        """An anchor's name on its gray pill: turned over with the rest of the canvas, the white name came out
        darker than its pill."""
        ground, pill, name = (240, 240, 240), (176, 174, 170), (255, 255, 255)
        rows = [[ground] * 40 for _ in range(4)]
        for y in range(14):
            row = [ground] * 4 + [pill] * 32 + [ground] * 4
            if 4 <= y < 10:
                for x in (10, 11, 16, 17, 22, 23):  # three stems, two pixels wide
                    row[x] = name
            rows.append(row)
        rows += [[ground] * 40 for _ in range(4)]
        out = self.map(rows, 1, 1.0)
        on_pill, on_name = out[6][6], out[8][10]
        self.assertGreater(sum(on_name), sum(on_pill) + 150, "the name clearly lighter than the pill it is on")
        self.assertLess(sum(out[1][1]), 3 * 100, "and the canvas dark")

    def test_a_name_on_a_pill_a_guide_crosses_stays_light(self):
        """The owner, 2026-11-25: a name on a pill a guide crosses had its letters dark. The pill is translucent:
        over the canvas' two grounds it is two shades of warm gray, each in two steps, the guide's dashes and a
        side line run under it, and the canvas' own light grays came first among the badge colors."""
        above, below, guide, name = (212, 212, 212), (232, 232, 234), (80, 78, 74), (236, 236, 235)
        rows = []
        for y in range(20):
            row = [above if y < 10 else below] * 44
            if 3 <= y < 17:
                for x in range(4, 40):
                    if y < 10:
                        row[x] = (162, 160, 157) if x < 22 else (164, 162, 158)
                    else:
                        row[x] = (173, 171, 168) if x < 22 else (176, 174, 170)
            if y == 10:
                row = [guide if x % 4 < 2 else row[x] for x in range(44)]
            if 3 <= y < 17:
                row[30] = guide  # a side line under the pill
            if 6 <= y < 14:
                for x in (10, 11, 16, 17, 25, 26, 34, 35):  # stems, two pixels wide
                    row[x] = name
            rows.append(row)
        for _ in range(4):
            rows.append([below] * 44)
        for k in range(8):  # the canvas' own light grays, in tiles (its shaded bands): more frequent than the pill
            gray = 200 + 3 * k
            rows += [[(gray, gray, gray + 8)] * 44 for _ in range(6)]
        out = self.map(rows, 1, 1.0)
        for (y, x, pill_x) in ((7, 10, 7), (12, 16, 7), (7, 34, 37), (12, 25, 21)):
            self.assertGreater(sum(out[y][x]), sum(out[y][pill_x]) + 150, "the name lighter than its pill at %d,%d" % (x, y))

    def test_a_name_on_a_pill_over_the_baseline_stays_light_below_it(self):
        """The owner, November 25: names on the pills along the baseline were still muddled. The pill over the
        canvas' white above the baseline and its band below is two warm grays 10 apart per channel, the letters
        below the line faint; a dashed sidebearing line, one pixel wide, was taken for a pill; and a glyph's
        slanted contour under a stem ended the walk down."""
        above, below, line = (240, 240, 240), (217, 217, 217), (75, 73, 69)
        pill_above, pill_below, side = (176, 174, 170), (166, 164, 160), (184, 184, 181)
        name_above, name_below, fringe = (239, 238, 238), (201, 200, 198), (190, 188, 185)
        rows = []
        for y in range(40):
            ground = above if y < 20 else below
            row = [ground] * 60
            if 12 <= y < 32:
                for x in range(6, 54):
                    row[x] = pill_above if y < 20 else pill_below
            if y == 20:
                row = [line] * 60  # the baseline, under the pill
            if 16 <= y < 25:
                for x in (14, 22, 30, 38):  # stems, a pixel wide, with a fringe on their right
                    if y != 20:
                        row[x] = name_above if y < 20 else name_below
                        row[x + 1] = fringe if y > 20 else row[x + 1]
            if 25 <= y < 40:
                row[30 + (y - 25) // 3] = line  # a glyph's slanted contour, from under a stem's foot down
            rows.append(row)
        for row in rows:  # dashed sidebearing lines: a pixel wide, two shades, frequent
            for x in (2, 58):
                row[x] = side
        for _ in range(4):
            rows.append([below] * 2 + [side] + [below] * 54 + [side] + [below] * 2)
        out = self.map(rows, 1, 1.0)
        for (y, x, pill_x) in ((17, 14, 18), (23, 22, 18), (23, 23, 18), (23, 30, 26), (24, 30, 26), (23, 38, 42)):
            self.assertGreater(sum(out[y][x]), sum(out[y][pill_x]) + 60,
                               "the name lighter than its pill at %d,%d" % (x, y))

    def test_a_colored_lines_smoothing_fades_to_the_paper_on_a_canvas(self):
        """The owner, 2026-11-25: every colored contour had a jagged edge. A line's full pixels were kept, light
        and red, and its smoothing, judged pixel by pixel, was turned over to a dark red: steps and dots."""
        paper, full, half, faint = (240, 240, 240), (255, 70, 70), (248, 155, 155), (243, 205, 205)
        rows = [[paper] * 60 for _ in range(40)]
        for y in range(5, 35):  # a slanted line: its core, and smoothing on each side
            x = 10 + y
            rows[y][x - 1], rows[y][x], rows[y][x + 1] = faint, full, half
        out = self.map(rows, 1, 1.0)
        ground, core, soft, softer = out[2][2], out[20][30], out[20][31], out[20][29]
        self.assertLess(sum(ground), 3 * 80, "the canvas dark")
        self.assertGreater(core[0], 200, "the line as red as drawn")
        self.assertGreater(core[0] - core[1], 120)
        for name, pixel in (("half", soft), ("faint", softer)):
            self.assertGreater(pixel[0], pixel[1] + 10, "%s smoothing still red" % name)
            self.assertGreater(pixel[0], ground[0] + 15, "and lighter than the canvas, not turned over below it")
            self.assertLess(pixel[0], core[0], "and weaker than the line")
        self.assertGreater(soft[0], softer[0], "more of the line, more red: a ramp, not steps")

    def test_black_ink_on_a_list_dark_already_turns_light(self):
        """Generate Instance's "Ag" beside each style: black on a list its stylesheet makes dark, too rare to be an
        anchor, stayed dark on dark."""
        paper, text, ink = (30, 30, 30), (220, 220, 220), (4, 4, 4)
        rows = [[paper] * 40 for _ in range(20)]
        for y in range(6, 14):
            for x in range(4, 8):
                rows[y][x] = ink
            for x in range(20, 36, 2):
                rows[y][x] = text
        buf = pixels([color for row in rows for color in row])
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_map_anchors(ctypes.addressof(array), len(buf) // 4, 40, 6, dm.DARK_OKL, dm.LIGHT_OKL, 0.0,
                                dm.DARK_OKL, 1)
        out = lambda x, y: tuple(reversed(struct.unpack_from("<BBB", buf, 4 * (y * 40 + x))))
        self.assertGreater(sum(out(5, 9)), 3 * 150, "the black ink light now")
        self.assertEqual(out(1, 1), paper, "the paper as it was")
        self.assertEqual(out(20, 9), text, "light text as it was")

    def test_a_colored_letters_counter_is_the_paper_not_kept_text(self):
        """An overlaid font's red O in a Font window cell: its counter, the cell's gray with red on every side,
        was kept as light text on a colored band and stood light in the dark cell."""
        paper, red = (183, 183, 184), (200, 59, 59)
        rows = [[paper] * 40 for _ in range(40)]
        for y in range(8, 32):
            for x in range(8, 32):
                if not (12 <= x < 28 and 12 <= y < 28):
                    rows[y][x] = red
        out = self.map(rows, 1, 1.0)
        self.assertLess(sum(out[20][20]), sum(paper) - 200, "the counter dark, as the paper around the letter")
        self.assertEqual(out[20][20], out[2][2], "the same as the paper outside")

    def test_dark_text_on_a_tag_is_mapped_from_its_darkest_channel_but_not_on_pure_white(self):
        """FontAudit's captions: ClearType's edges of thin dark text, turned over by their own lightness, were
        most of the text and dim. TrueType Hinting's preview, on pure white, shows those colors on purpose."""
        def picture(paper):
            rows = [[paper] * 24 for _ in range(12)]
            for y in range(3, 9):
                rows[y][10], rows[y][11], rows[y][12] = (218, 161, 103), (73, 73, 73), (131, 190, 249)
            return rows
        tag = self.map(picture((248, 248, 249)), 1, 1.0)
        white = self.map(picture((255, 255, 255)), 1, 1.0)
        edge = tag[5][12]
        self.assertLessEqual(max(edge) - min(edge), 12, "gray: no color left on a tag")
        self.assertGreater(sum(edge), sum(tag[5][2]) + 120, "and light on the dark tag")
        self.assertGreater(max(white[5][12]) - min(white[5][12]), 12, "on pure white the edge keeps its color")

    def colored_numbers(self, orange_near):
        white, navy = (255, 255, 255), (0, 0, 128)
        left, core, right = (255, 170, 128), (43, 43, 170), (170, 255, 128)  # one coverage on average, apart
        rows = [[white] * 40 for _ in range(20)]
        for y in range(5):
            rows[y][:8] = [navy] * 8  # the box of the size shown: the text color, 40 pixels
        rows[10][10:13] = [left, core, right]
        if orange_near:
            rows[10][15] = (230, 150, 40)  # black text's orange edge: a blue far below navy's
        return self.map(rows, 1, 1.0)[10]

    def test_colored_cleartype_text_on_white_is_smoothed_in_its_color(self):
        """TrueType Hinting's navy size numbers: their ClearType edges came out a dim mix of purples and teals."""
        row = self.colored_numbers(False)
        self.assertEqual(row[10], row[12], "the same coverage on average: the same color")
        self.assertGreater(sum(row[11]), sum(row[10]), "the core more inked toward the light text color")

    def test_a_colored_words_white_halo_and_its_blends_turn_dark_together(self):
        """The Scoreboard's orange word, drawn with a white halo for a light canvas: under the ink effect its halo
        turned dark, and the blends between the word and its halo, kept, ringed it in light dots."""
        orange, white, blend = (200, 100, 0), (250, 250, 250), (223, 169, 116)
        buf = bytearray()
        for _ in range(6):
            buf += pixels([(0, 0, 0)] * 2, alpha=0) + pixels([white] * 3, alpha=220) + pixels([blend], alpha=238)
            buf += pixels([orange] * 10) + pixels([blend], alpha=238) + pixels([white] * 3, alpha=220)
            buf += pixels([(0, 0, 0)] * 2, alpha=0)
        anchors(LIB, buf, 22, "ink")
        halo, edge, mark = rgb_at(buf, 3), rgb_at(buf, 5), rgb_at(buf, 8)
        self.assertEqual(mark, orange, "the word as drawn")
        self.assertLess(sum(halo), 3 * 80, "its halo dark")
        self.assertLess(sum(edge), sum(orange), "the blend between them no lighter than the word")
        self.assertGreater(sum(edge), sum(halo))

    def test_dark_cleartype_text_on_light_is_grayed_before_an_island_maps_it(self):
        """The Fonts panel's names: black ClearType text on its near-white list came out with orange and blue edges."""
        paper, left, core, right = (250, 250, 250), (250, 208, 125), (42, 0, 83), (125, 208, 250)
        row = [paper] * 4 + [left, core, right] + [paper] * 4
        buf = pixels(row * 6)
        LIB.freelab_gray_cleartype.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
        array = (ctypes.c_char * len(buf)).from_buffer(buf)
        LIB.freelab_gray_cleartype(ctypes.addressof(array), len(buf) // 4, len(row))
        for x in (4, 6):
            got = rgb_at(buf, len(row) * 2 + x)
            self.assertEqual(got[0], got[1], "an edge made gray")
            self.assertEqual(got[1], got[2])
        self.assertEqual(rgb_at(buf, len(row) * 2), paper, "the paper as it is")

    def test_colored_text_on_white_keeps_its_color_to_its_edges_in_an_island(self):
        """Red text on the Preview panel's white: its smoothing went gray, a gray rim around the letters."""
        white, red, edge = (255, 255, 255), (205, 62, 58), (224, 134, 132)
        rows = [[white] * 30 for _ in range(20)]
        for y in range(4, 16):
            rows[y][8:20] = [red] * 12
            rows[y][7], rows[y][20] = edge, edge
        out = self.map(rows, 1, 0.0)[10]
        self.assertGreater(out[7][0] - out[7][2], 40, "the edge reddish, not gray")
        self.assertLess(sum(out[7]), sum(out[10]), "and darker than the red")

    def test_a_thin_colored_outline_keeps_no_light_dots(self):
        """An overlaid font's red outlines in a Font window cell: the smoothing inside them stayed light."""
        cell, red, blend = (183, 183, 184), (214, 58, 52), (187, 150, 151)
        rows = [[cell] * 40 for _ in range(40)]
        for k in range(8, 32):  # a ring, 1 pixel wide, its smoothing inside
            for (x, y) in ((k, 8), (k, 31), (8, k), (31, k)):
                rows[y][x] = red
            for (x, y) in ((k, 9), (k, 30), (9, k), (30, k)):
                if 9 <= x <= 30 and 9 <= y <= 30:
                    rows[y][x] = blend
        out = self.map(rows, 1, 1.0)
        self.assertLess(sum(out[9][20]), 3 * 120, "the smoothing toward the dark cell, not kept light")

    def test_small_black_text_is_not_taken_for_colored(self):
        row = self.colored_numbers(True)
        self.assertNotEqual(row[10], row[12])


if __name__ == "__main__":
    unittest.main()
