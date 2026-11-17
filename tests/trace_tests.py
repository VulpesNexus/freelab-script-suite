# -*- coding: utf-8 -*-
"""Unit tests for freelab_trace, on synthetic bitmaps. Runs unchanged on
Python 2.7 and 3: python trace_tests.py"""
from __future__ import division, print_function

import math
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "builder"))
import freelab_trace as ft  # noqa: E402

try:
    xrange
except NameError:
    xrange = range


# ---------------------------------------------------------------------------
# Synthetic images (0 = ink, 255 = paper)
# ---------------------------------------------------------------------------

def image_from_spans(width, height, spans_of_row):
    """Builds a binary image row by row from a function returning the ink
    spans [(x0, x1), ...] (x1 exclusive) of a row."""
    rows = []
    for y in xrange(height):
        row = bytearray(b"\xff" * width)
        for x0, x1 in spans_of_row(y):
            x0 = max(0, x0)
            x1 = min(width, x1)
            if x1 > x0:
                row[x0:x1] = b"\x00" * (x1 - x0)
        rows.append(bytes(row))
    return b"".join(rows)


def rect_spans(rects):
    def spans(y):
        return [(x0, x1) for x0, y0, x1, y1 in rects if y0 <= y < y1]
    return spans


def ring_spans(cx, cy, r_out, r_in=0.0, extra=()):
    """Pixels whose centers lie inside the ring, plus extra rectangles."""
    def spans(y):
        out = []
        dy = y + 0.5 - cy
        if abs(dy) < r_out:
            ho = math.sqrt(r_out * r_out - dy * dy)
            if abs(dy) < r_in:
                hi = math.sqrt(r_in * r_in - dy * dy)
                out.append((int(math.ceil(cx - ho - 0.5)), int(math.ceil(cx - hi - 0.5))))
                out.append((int(math.floor(cx + hi + 0.5)), int(math.floor(cx + ho + 0.5))))
            else:
                out.append((int(math.ceil(cx - ho - 0.5)), int(math.floor(cx + ho + 0.5))))
        for x0, y0, x1, y1 in extra:
            if y0 <= y < y1:
                out.append((x0, x1))
        return out
    return spans


def antialiased_disc(size, cx, cy, r_out, r_in, ss=4):
    """A ring with pixel coverage computed by ss x ss supersampling."""
    out = bytearray(size * size)
    for y in xrange(size):
        for x in xrange(size):
            # cheap rejection far from the edges
            d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if d > r_out + 1 or (r_in > 0 and d < r_in - 1):
                out[y * size + x] = 255
                continue
            if r_in + 1 < d < r_out - 1:
                out[y * size + x] = 0
                continue
            cov = 0
            for sy in xrange(ss):
                for sx in xrange(ss):
                    dd = math.hypot(x + (sx + 0.5) / ss - cx, y + (sy + 0.5) / ss - cy)
                    if r_in <= dd <= r_out:
                        cov += 1
            out[y * size + x] = 255 - int(round(255.0 * cov / (ss * ss)))
    return bytes(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def segment_points(contour, steps=32):
    """Dense points along a traced contour (pixel coordinates)."""
    pts = []
    cur = contour[-1][-1]
    for s in contour:
        if s[0] == "line":
            p = s[1]
            for k in xrange(steps):
                t = k / steps
                pts.append((cur[0] + (p[0] - cur[0]) * t, cur[1] + (p[1] - cur[1]) * t))
            cur = p
        else:
            for k in xrange(steps):
                pts.append(ft._bez(cur, s[1], s[2], s[3], k / steps))
            cur = s[3]
    return pts


def shoelace(pts):
    a = 0.0
    n = len(pts)
    for i in xrange(n):
        x0, y0 = pts[i][0], pts[i][1]
        x1, y1 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def node_curves(nodes):
    """(p0, c1, c2, p3) for every curve of a node list."""
    n = len(nodes)
    out = []
    for i in xrange(n):
        if nodes[i][2] != "off" and nodes[(i + 1) % n][2] == "off":
            out.append(tuple(nodes[(i + k) % n] for k in xrange(4)))
    return out


def font_points(nodes, steps=48):
    pts = []
    n = len(nodes)
    i = 0
    start = 0
    while nodes[start][2] == "off":
        start += 1
    nodes = list(nodes[start:]) + list(nodes[:start])
    while i < n:
        p0 = nodes[i]
        if nodes[(i + 1) % n][2] == "off":
            c1, c2, p3 = nodes[(i + 1) % n], nodes[(i + 2) % n], nodes[(i + 3) % n]
            for k in xrange(steps):
                pts.append(ft._bez(p0, c1, c2, p3, k / steps))
            i += 3
        else:
            pts.append((p0[0], p0[1]))
            i += 1
    return pts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class SquareTest(unittest.TestCase):
    def setUp(self):
        self.w = self.h = 40
        self.img = image_from_spans(40, 40, rect_spans([(10, 10, 30, 30)]))

    def test_square_is_four_lines(self):
        c = ft.trace(self.img, 40, 40)
        self.assertEqual(len(c), 1)
        self.assertTrue(all(s[0] == "line" for s in c[0]))
        self.assertEqual(len(c[0]), 4)
        corners = sorted((round(s[1][0], 3), round(s[1][1], 3)) for s in c[0])
        self.assertEqual(corners, [(10, 10), (10, 30), (30, 10), (30, 30)])

    def test_orientation(self):
        rep = {}
        c = ft.trace(self.img, 40, 40, report=rep)
        self.assertEqual(rep["kinds"], ["outer"])
        self.assertLess(shoelace([s[-1] for s in c[0]]), 0)  # pixel space, y down
        nodes = ft.to_font(c, 2.0, 100, 500)[0]
        self.assertGreater(shoelace(nodes), 0)  # font units: counterclockwise
        self.assertTrue(all(k == "on" for _, _, k in nodes))
        xs = sorted(set(x for x, _, _ in nodes))
        ys = sorted(set(y for _, y, _ in nodes))
        self.assertEqual(xs, [120, 160])
        self.assertEqual(ys, [440, 480])

    def test_input_types_and_stride(self):
        ref = ft.trace(self.img, 40, 40)
        self.assertEqual(ft.trace(bytearray(self.img), 40, 40), ref)
        padded = b"".join(self.img[y * 40:(y + 1) * 40] + b"\x7f\x00\x00\x00" for y in xrange(40))
        self.assertEqual(ft.trace(padded, 40, 40, stride=44), ref)
        self.assertRaises(ValueError, ft.trace, self.img[:-1], 40, 40)


class LShapeTest(unittest.TestCase):
    def test_six_corners(self):
        img = image_from_spans(60, 60, rect_spans([(10, 10, 20, 50), (20, 40, 50, 50)]))
        c = ft.trace(img, 60, 60)
        self.assertEqual(len(c), 1)
        self.assertTrue(all(s[0] == "line" for s in c[0]))
        pts = sorted((round(s[1][0], 3), round(s[1][1], 3)) for s in c[0])
        self.assertEqual(pts, [(10, 10), (10, 50), (20, 10), (20, 40), (50, 40), (50, 50)])
        nodes = ft.to_font(c, 1, 0, 0)[0]
        self.assertGreater(shoelace(nodes), 0)


class RingTest(unittest.TestCase):
    size = 100
    cx = cy = 50.0
    r_out, r_in = 36.0, 18.0

    def check_ring(self, img, tol):
        rep = {}
        c = ft.trace(img, self.size, self.size, report=rep)
        self.assertEqual(len(c), 2)
        self.assertEqual(rep["kinds"], ["outer", "hole"])
        self.assertEqual(rep["parents"], [-1, 0])
        a0 = shoelace(segment_points(c[0]))
        a1 = shoelace(segment_points(c[1]))
        self.assertLess(a0, 0)
        self.assertGreater(a1, 0)
        for contour, r in ((c[0], self.r_out), (c[1], self.r_in)):
            for x, y in segment_points(contour):
                self.assertLess(abs(math.hypot(x - self.cx, y - self.cy) - r), tol)
            self.assertTrue(all(s[0] == "curve" for s in contour))
        return c

    def test_binary_ring(self):
        img = image_from_spans(self.size, self.size, ring_spans(self.cx, self.cy, self.r_out, self.r_in))
        self.check_ring(img, 0.6)

    def test_antialiased_ring_refined(self):
        img = antialiased_disc(self.size, self.cx, self.cy, self.r_out, self.r_in)
        plain = ft.trace(img, self.size, self.size, refine=False, tangent=False)
        better = ft.trace(img, self.size, self.size)

        def err(c):
            e = []
            for contour, r in zip(c, (self.r_out, self.r_in)):
                e += [abs(math.hypot(x - self.cx, y - self.cy) - r) for x, y in segment_points(contour)]
            return sum(e) / len(e)
        self.assertLess(err(plain), 0.25)
        self.assertLess(err(better), 0.6 * err(plain))
        self.check_ring(img, 0.35)

    def test_font_orientation_and_extremes(self):
        img = image_from_spans(self.size, self.size, ring_spans(self.cx, self.cy, self.r_out, self.r_in))
        c = ft.trace(img, self.size, self.size)
        fonts = ft.to_font(c, 10.0, 0, 1000)
        self.assertGreater(shoelace(font_points(fonts[0])), 0)  # outer counterclockwise
        self.assertLess(shoelace(font_points(fonts[1])), 0)  # hole clockwise
        for nodes in fonts:
            e = ft.extremes(nodes)
            pts = font_points(e, 200)
            on = [(x, y) for x, y, k in e if k != "off"]
            for ax in (0, 1):
                for ext in (min(p[ax] for p in pts), max(p[ax] for p in pts)):
                    self.assertTrue(any(abs(p[ax] - ext) < 1e-6 for p in on),
                                    "extreme %r on axis %d has no node" % (ext, ax))
            # no curve reaches past its end points (beyond the 0.5-unit
            # allowance for extremes too close to a node to split at)
            for p0, c1, c2, p3 in node_curves(e):
                for ax in (0, 1):
                    lo, hi = min(p0[ax], p3[ax]), max(p0[ax], p3[ax])
                    for k in xrange(1, 64):
                        v = ft._bez(p0, c1, c2, p3, k / 64.0)[ax]
                        self.assertTrue(lo - 0.5 <= v <= hi + 0.5)

    def test_extremes_keep_the_shape(self):
        img = image_from_spans(self.size, self.size, ring_spans(self.cx, self.cy, self.r_out, self.r_in))
        nodes = ft.to_font(ft.trace(img, self.size, self.size), 10.0, 0, 1000)[0]
        before = node_curves(nodes)
        after = node_curves(ft.extremes(nodes, 0.0))
        dense = []
        for p0, c1, c2, p3 in before:
            dense += [ft._bez(p0, c1, c2, p3, k / 4000.0) for k in xrange(4001)]
        for p0, c1, c2, p3 in after:
            for k in xrange(9):
                q = ft._bez(p0, c1, c2, p3, k / 8.0)
                d = min(math.hypot(q[0] - p[0], q[1] - p[1]) for p in dense)
                self.assertLess(d, 0.1)  # the sampling step of `dense`

    def test_rounding_keeps_smooth_nodes(self):
        img = antialiased_disc(self.size, self.cx, self.cy, self.r_out, self.r_in)
        glyph = ft.trace_glyph(img, self.size, self.size, 7.3, 13.2, 811.7)
        self.assertEqual(len(glyph), 2)
        for nodes in glyph:
            n = len(nodes)
            for i, (x, y, k) in enumerate(nodes):
                self.assertEqual((x, y), (int(x), int(y)))
                if k != "smooth":
                    continue
                a, b = nodes[i - 1], nodes[(i + 1) % n]
                v1 = (x - a[0], y - a[1])
                v2 = (b[0] - x, b[1] - y)
                cs = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
                self.assertLess(math.degrees(math.acos(max(-1.0, min(1.0, cs)))), 1.0)

    def test_rounding_leaves_an_integral_monotone_curve_alone(self):
        # (a handle outside the end points' box of a curve that has no extreme between them: clamping it
        # moved a valid curve by 40/9 units; review 9)
        for scale in (1, 10):
            nodes = [(x * scale, y * scale, k) for x, y, k in
                     [(0, 0, "on"), (110, 30, "off"), (50, 40, "off"), (100, 100, "on")]]
            self.assertEqual(ft.extremes(nodes, round_coords=True), nodes)

    def test_island_in_hole(self):
        img = image_from_spans(self.size, self.size, ring_spans(
            self.cx, self.cy, self.r_out, self.r_in, extra=[(44, 44, 56, 56)]))
        rep = {}
        self.assertEqual(len(ft.trace(img, self.size, self.size, report=rep)), 3)
        self.assertEqual(rep["kinds"], ["outer", "hole", "outer"])
        self.assertEqual(rep["parents"], [-1, 0, 1])


class DiagonalTest(unittest.TestCase):
    def test_thick_diagonal_stroke(self):
        def spans(y):
            return [(y - 1, y + 3)] if 10 <= y < 90 else []
        img = image_from_spans(100, 100, spans)
        c = ft.trace(img, 100, 100)
        self.assertEqual(len(c), 1)
        pts = segment_points(c[0])
        # the 4-pixel-wide ends are too small to read as corners, so they
        # are rounded off (as in the published algorithm): about 17% of the
        # area of this short stroke
        area = abs(shoelace(pts))
        self.assertTrue(0.8 * 320 < area < 320, area)
        self.assertLess(abs(min(y for _, y in pts) - 10), 0.01)
        self.assertLess(abs(max(y for _, y in pts) - 90), 0.01)

    def test_one_pixel_diagonal_and_turn_policy(self):
        def spans(y):
            return [(y, y + 1)] if 10 <= y < 30 else []
        img = image_from_spans(40, 40, spans)
        joined = ft.trace(img, 40, 40, turdsize=0, turnpolicy="black")
        apart = ft.trace(img, 40, 40, turdsize=0, turnpolicy="white")
        self.assertEqual(len(joined), 1)
        self.assertEqual(len(apart), 20)
        # minority: ink is the minority color around each junction here
        self.assertEqual(len(ft.trace(img, 40, 40, turdsize=0)), 1)


class SpeckTest(unittest.TestCase):
    def test_speck_dropped_and_reported(self):
        img = image_from_spans(50, 50, rect_spans([(10, 10, 40, 40), (45, 3, 46, 4)]))
        rep = {}
        c = ft.trace(img, 50, 50, report=rep)
        self.assertEqual(len(c), 1)
        self.assertEqual(rep["specks"], [(45, 3, 1, "ink")])
        self.assertEqual(len(ft.trace(img, 50, 50, turdsize=0)), 2)

    def test_pinhole_filled(self):
        img = image_from_spans(50, 50, rect_spans([(10, 10, 25, 40), (26, 10, 40, 40),
                                                   (25, 10, 26, 20), (25, 21, 26, 40)]))
        rep = {}
        c = ft.trace(img, 50, 50, report=rep)
        self.assertEqual(len(c), 1)
        self.assertEqual(rep["specks"][0][3], "hole")

    def test_speck_area_scales_with_em(self):
        self.assertEqual(ft.speck_area(1000), 400)
        self.assertEqual(ft.speck_area(300), 36)
        self.assertEqual(ft.speck_area(50), 2)


class TimingTest(unittest.TestCase):
    def test_700px_glyph(self):
        # a ring and two bars: about 4,000 boundary pixels
        img = image_from_spans(700, 700, ring_spans(350, 350, 300, 220, extra=[
            (30, 600, 670, 680), (330, 20, 370, 680)]))
        best = None
        for _ in xrange(2):
            t = time.time()
            glyph = ft.trace_glyph(img, 700, 700, 1.5, 0, 1000, em_px=700)
            dt = time.time() - t
            best = dt if best is None else min(best, dt)
        sys.stderr.write("\n  700 px glyph: %.3f s (Python %d.%d)\n" % (best, sys.version_info[0], sys.version_info[1]))
        self.assertTrue(glyph)
        self.assertLess(best, 2.0)


if __name__ == "__main__":
    unittest.main()
