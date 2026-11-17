# -*- coding: utf-8 -*-
"""Bitmap-to-outline tracing for font glyphs, in pure Python (2.7 and 3).

The method follows the polygon-based tracing algorithm that Peter Selinger
published in "Potrace: a polygon-based tracing algorithm" (2003), written
anew from that description:

1. Path decomposition: the boundary between ink and paper pixels is split
   into closed lattice paths, ambiguous diagonal junctions are resolved by a
   turn policy, and paths that enclose no more than `turdsize` pixels are
   dropped.
2. Optimal polygon: each path is approximated by the polygon with the fewest
   edges whose edges are all "straight" sub-paths, and among those the one
   with the smallest penalty (edge length times the RMS distance of the path
   points to the edge), by dynamic programming over precomputed reach arrays.
3. Vertex adjustment: every polygon vertex moves to the point closest (least
   squares) to the lines fitted to its two adjacent edges, within a small
   square around the original lattice vertex.
4. Smoothing: each vertex becomes either a corner or a cubic Bezier between
   the midpoints of its two edges; `alphamax` sets where corners start.
5. Curve optimization: runs of convex curves are joined into single curves
   when the result stays within `opttolerance` pixels of the original.

Two changes to steps 3 and 4 are on by default and can be turned off:
`refine` fits the edges to sub-pixel boundary points read from antialiased
gray levels instead of to pixel corners, and `tangent` moves each edge onto
the boundary at the middle of its stretch, which removes the published
method's bias of curves toward their center of curvature. Together they
reduce the mean deviation by about a third on antialiased images, with the
same number of nodes.

On top of that it adds what fonts need: outer contours counterclockwise and
holes clockwise in font units (`to_font`), on-curve nodes at every horizontal
and vertical extreme (`extremes`), integer coordinates that keep smooth nodes
smooth (`round_nodes`), and speck removal scaled to the em (`speck_area`).

Coordinates returned by `trace` are pixel coordinates with y pointing down,
(0, 0) being the top-left corner of the top-left pixel.

From a QImage in Format_Grayscale8 (or Indexed8 with a gray color table),
pass its pixel bytes, its width and height, and its bytes per line as
`stride`, since Qt pads rows to multiples of 4 bytes.
"""
from __future__ import division

import math
from bisect import bisect_left

try:
    xrange
except NameError:  # Python 3
    xrange = range

__all__ = ["trace", "to_font", "extremes", "round_nodes", "trace_glyph",
           "speck_area", "gray_levels", "TURN_POLICIES"]

TURN_POLICIES = ("black", "white", "left", "right", "minority", "majority", "random")

# Step directions in y-down pixel space: east, south, west, north.
_DX = (1, 0, -1, 0)
_DY = (0, 1, 0, -1)


def _rnd(v):
    """Rounds half up, the same on Python 2 and 3."""
    return int(math.floor(v + 0.5))


# ---------------------------------------------------------------------------
# Bitmap
# ---------------------------------------------------------------------------

def _as_bytes(gray):
    if isinstance(gray, (bytes, bytearray)):
        return gray
    return bytes(bytearray(gray))


def _ink_rows(gray, width, height, threshold, stride):
    """Thresholds the image into rows of 0/1 bytes (1 = ink) with a one-pixel
    paper border on every side, so that every lookup next to a path stays in
    range."""
    table = bytes(bytearray([1 if v < threshold else 0 for v in xrange(256)]))
    blank = bytearray(width + 2)
    rows = [blank]
    for y in xrange(height):
        off = y * stride
        r = bytearray(1)
        r += bytearray(gray[off:off + width].translate(table))
        r.append(0)
        rows.append(r)
    rows.append(bytearray(width + 2))
    return rows


def _gray_rows(gray, width, height, stride):
    """Gray rows with the same one-pixel border as `_ink_rows`, filled with
    paper (255)."""
    edge = bytearray(b"\xff")
    rows = [bytearray(b"\xff" * (width + 2))]
    for y in xrange(height):
        off = y * stride
        r = bytearray(edge)
        r += bytearray(gray[off:off + width])
        r += edge
        rows.append(r)
    rows.append(bytearray(b"\xff" * (width + 2)))
    return rows


def gray_levels(gray, width, height, threshold=128, stride=None):
    """Estimates the ink and paper gray levels of an image: the medians of the
    sampled pixels below and at or above `threshold`. Returns (ink, paper)."""
    gray = _as_bytes(gray)
    if stride is None:
        stride = width
    step = 3
    data = sorted(bytearray(gray[:stride * height][::step]))
    if not data:
        return 0, 255
    split = bisect_left(data, threshold)
    lo = data[split // 2] if split > 0 else 0
    hi = data[(split + len(data)) // 2] if split < len(data) else 255
    if hi - lo < 32:  # nearly uniform image: assume full contrast
        lo, hi = 0, 255
    return lo, hi


def _boundary_pixels(rows, width, height, policy):
    """Padded coordinates of every pixel that touches, or is diagonal to, a
    boundary edge of the thresholded image."""
    todo = set()
    tadd = todo.add
    for xs, ys, area in _decompose(rows, width, height, -1, policy, None):
        n = len(xs)
        for k in xrange(n):
            x = xs[k]
            y = ys[k]
            j = k + 1 if k + 1 < n else 0
            dx = xs[j] - x
            if dx:
                px = x if dx == 1 else x - 1
                for qx in (px - 1, px, px + 1):
                    tadd((qx, y - 1))
                    tadd((qx, y))
            else:
                py = y if ys[j] > y else y - 1
                for qy in (py - 1, py, py + 1):
                    tadd((x - 1, qy))
                    tadd((x, qy))
    return todo


def _denoise(rows, grows, width, height, threshold, policy):
    """Thresholds a 3 x 3 tent-filtered image instead of the raw one. Only
    pixels whose neighborhood mixes ink and paper can change, and those all
    touch the boundary, so only they are filtered. Works in place."""
    changes = []
    for px, py in _boundary_pixels(rows, width, height, policy):
        if px < 1 or px > width or py < 1 or py > height:
            continue
        a = grows[py - 1]
        b = grows[py]
        c = grows[py + 1]
        v = (4 * b[px] + 2 * (b[px - 1] + b[px + 1] + a[px] + c[px])
             + a[px - 1] + a[px + 1] + c[px - 1] + c[px + 1])
        changes.append((px, py, 1 if v < 16 * threshold else 0))
    for px, py, ink in changes:
        rows[py][px] = ink


def _upsample2(rows, grows, width, height, threshold, policy):
    """Thresholded rows of the image enlarged twice by bilinear interpolation.
    A sub-pixel can differ from the nearest-neighbor enlargement only where
    its 2 x 2 source neighborhood mixes ink and paper, which happens only next
    to a boundary edge, so only the pixels along the 1x boundary paths are
    interpolated. Returns padded rows and the new size."""
    W2, H2 = 2 * width, 2 * height
    out = [bytearray(W2 + 2)]
    for y in xrange(1, height + 1):
        src = rows[y]
        r = bytearray(W2 + 2)
        inner = src[1:width + 1]
        r[1:W2 + 1:2] = inner
        r[2:W2 + 2:2] = inner
        out.append(r)
        out.append(bytearray(r))
    out.append(bytearray(W2 + 2))
    g = grows
    for px, py in _boundary_pixels(rows, width, height, policy):
        if px < 1 or px > width or py < 1 or py > height:
            continue
        row = g[py]
        v00 = 0.5625 * row[px]
        orow0 = out[2 * py - 1]
        orow1 = out[2 * py]
        for qy in (0, 1):
            nrow = g[py - 1] if qy == 0 else g[py + 1]
            orow = orow0 if qy == 0 else orow1
            for qx in (0, 1):
                nx = px - 1 if qx == 0 else px + 1
                val = v00 + 0.1875 * (row[nx] + nrow[px]) + 0.0625 * nrow[nx]
                orow[2 * px - 1 + qx] = 1 if val < threshold else 0
    return out, W2, H2


# ---------------------------------------------------------------------------
# Path decomposition
# ---------------------------------------------------------------------------

def _majority(rows, x, y, w2, h2):
    """1 if ink is the majority around lattice vertex (x, y), 0 if paper,
    -1 on a tie, looking at squares of growing size."""
    for r in (2, 3, 4):
        ct = 0
        x0 = max(0, x - r)
        x1 = min(w2, x + r)
        for yy in xrange(max(0, y - r), min(h2, y + r)):
            ct += sum(rows[yy][x0:x1])
        total = 4 * r * r
        if 2 * ct > total:
            return 1
        if 2 * ct < total:
            return 0
    return -1


def _connect_ink(policy, rows, x, y, d, w2, h2):
    """Decides an ambiguous (diagonal) junction: True joins the two ink
    pixels, False keeps them apart."""
    if policy == "black":
        return True
    if policy == "white":
        return False
    if policy == "right":
        return True
    if policy == "left":
        return False
    if policy == "random":
        h = (x * 73856093) ^ (y * 19349663)
        return bool((h >> 3) & 1)
    maj = _majority(rows, x, y, w2, h2)
    if maj < 0:
        return policy == "majority"
    if policy == "majority":
        return maj == 1
    return maj == 0  # minority


def _trace_path(rows, x, y, d, w1, visited, policy, w2, h2):
    """Follows one closed boundary with ink on the left, from vertex (x, y)
    leaving in direction d. Marks the vertical edges it uses. Returns the
    vertex lists and the signed area (negative for outer contours)."""
    xs = []
    ys = []
    x0, y0, d0 = x, y, d
    area = 0
    vadd = visited.add
    while True:
        xs.append(x)
        ys.append(y)
        if d == 0:
            x += 1
        elif d == 1:
            vadd(y * w1 + x)
            area += x
            y += 1
        elif d == 2:
            x -= 1
        else:
            y -= 1
            vadd(y * w1 + x)
            area -= x
        if d == 0:
            left = rows[y - 1][x]
            right = rows[y][x]
        elif d == 1:
            left = rows[y][x]
            right = rows[y][x - 1]
        elif d == 2:
            left = rows[y][x - 1]
            right = rows[y - 1][x - 1]
        else:
            left = rows[y - 1][x - 1]
            right = rows[y - 1][x]
        if left:
            if right:
                d = (d + 1) & 3
        elif right:
            if _connect_ink(policy, rows, x, y, d, w2, h2):
                d = (d + 1) & 3
            else:
                d = (d + 3) & 3
        else:
            d = (d + 3) & 3
        if x == x0 and y == y0 and d == d0:
            break
    return xs, ys, area


def _decompose(rows, w, h, turdsize, policy, report):
    """Finds every boundary path of the padded bitmap. Returns a list of
    (xs, ys, area) in scan order; the start vertex of each path is the top
    corner of its first vertical edge in that order."""
    w1 = w + 3
    w2 = w + 2
    h2 = h + 2
    visited = set()
    paths = []
    specks = []
    for y in xrange(1, h + 1):
        row = rows[y]
        found = []
        i = row.find(b"\x00\x01")
        while i >= 0:
            found.append((i + 1, 0))
            i = row.find(b"\x00\x01", i + 1)
        i = row.find(b"\x01\x00")
        while i >= 0:
            found.append((i + 1, 1))
            i = row.find(b"\x01\x00", i + 1)
        if not found:
            continue
        found.sort()
        base = y * w1
        for x, kind in found:
            if (base + x) in visited:
                continue
            if kind == 0:
                xs, ys, area = _trace_path(rows, x, y, 1, w1, visited, policy, w2, h2)
            else:
                xs, ys, area = _trace_path(rows, x, y + 1, 3, w1, visited, policy, w2, h2)
                xs = xs[1:] + xs[:1]
                ys = ys[1:] + ys[:1]
            if abs(area) <= turdsize:
                specks.append((xs[0] - 1, ys[0] - 1, abs(area), "ink" if area < 0 else "hole"))
                continue
            paths.append((xs, ys, area))
    if report is not None:
        report["specks"] = specks
    return paths


def _inside(px, py, xs, ys):
    """Even-odd test of the point (px, py), not on the lattice, against a
    lattice path."""
    n = len(xs)
    c = False
    for i in xrange(n):
        j = i + 1 if i + 1 < n else 0
        if xs[i] == xs[j] and xs[i] > px:
            ya, yb = ys[i], ys[j]
            if (ya < py) != (yb < py):
                c = not c
    return c


def _nesting(paths):
    """Parent index of every path (-1 for top level): the smallest path that
    contains a pixel just inside it."""
    n = len(paths)
    parents = [-1] * n
    if n < 2:
        return parents
    boxes = [(min(p[0]), min(p[1]), max(p[0]), max(p[1])) for p in paths]
    for i in xrange(n):
        xs, ys, area = paths[i]
        # the first vertex is a top corner; the pixel below-right (outer) or
        # below-right (hole) of it lies inside the path
        px, py = xs[0] + 0.5, ys[0] + 0.5
        best, best_a = -1, None
        for j in xrange(n):
            if j == i:
                continue
            b = boxes[j]
            if not (b[0] < px < b[2] and b[1] < py < b[3]):
                continue
            aj = abs(paths[j][2])
            if aj <= abs(area):
                continue
            if _inside(px, py, paths[j][0], paths[j][1]):
                if best_a is None or aj < best_a:
                    best, best_a = j, aj
        parents[i] = best
    return parents


# ---------------------------------------------------------------------------
# Optimal polygon
# ---------------------------------------------------------------------------

def _polygon(xs, ys):
    """Indices of the optimal polygon's vertices on the path, starting at 0."""
    n = len(xs)
    dirs = [0] * n
    for i in xrange(n):
        j = i + 1 if i + 1 < n else 0
        dx = xs[j] - xs[i]
        if dx == 1:
            dirs[i] = 0
        elif dx == -1:
            dirs[i] = 2
        elif ys[j] > ys[i]:
            dirs[i] = 1
        else:
            dirs[i] = 3
    # run length: steps from i until the direction changes
    runlen = [0] * n
    nxt = -1
    for i in xrange(2 * n - 1, -1, -1):
        ii = i - n if i >= n else i
        i1 = i + 1
        while i1 >= n:
            i1 -= n
        if dirs[i1] != dirs[ii]:
            nxt = i + 1
        if i < n:
            runlen[i] = nxt - i

    # lon[i]: the furthest vertex k (unwrapped) such that the path from i to
    # k is straight: it uses at most three directions, and the ray from p[i]
    # toward each vertex stays within the cone allowed by the unit squares
    # (half size 1) around the vertices before it.
    lonk = [0] * n
    for i in xrange(n):
        x0 = xs[i]
        y0 = ys[i]
        seen = 0
        k = i
        has = False
        ax = ay = bx = by = 0
        limit = i + n - 1
        while True:
            kk = k - n if k >= n else k
            d = dirs[kk]
            seen |= 1 << d
            if seen == 15:
                lon = k
                break
            L = runlen[kk]
            k2 = k + L
            if k2 >= limit:
                lon = limit
                break
            k2m = k2 - n if k2 >= n else k2
            vx = xs[k2m] - x0
            vy = ys[k2m] - y0
            if vx > 1 or vx < -1 or vy > 1 or vy < -1:
                if has and (ax * vy - ay * vx > 0 or bx * vy - by * vx < 0):
                    # the run's end leaves the cone: find the last vertex on
                    # the run that stays inside it
                    ddx = _DX[d]
                    ddy = _DY[d]
                    qx = xs[kk] - x0
                    qy = ys[kk] - y0
                    t = L - 1
                    cad = ax * ddy - ay * ddx
                    if cad > 0:
                        tt = (ay * qx - ax * qy) // cad
                        if tt < t:
                            t = tt
                    cbd = bx * ddy - by * ddx
                    if cbd < 0:
                        tt = (bx * qy - by * qx) // (-cbd)
                        if tt < t:
                            t = tt
                    if t < 0:
                        t = 0
                    lon = k + t
                    break
                # tighten the cone with the extreme corners of the square
                if vy > 0 or (vy == 0 and vx > 0):
                    cx = vx - 1
                else:
                    cx = vx + 1
                if vx > 0 or (vx == 0 and vy < 0):
                    cy = vy + 1
                else:
                    cy = vy - 1
                if vy > 0 or (vy == 0 and vx < 0):
                    ex = vx + 1
                else:
                    ex = vx - 1
                if vx > 0 or (vx == 0 and vy > 0):
                    ey = vy - 1
                else:
                    ey = vy + 1
                if not has:
                    ax, ay, bx, by = cx, cy, ex, ey
                    has = True
                else:
                    if ax * cy - ay * cx < 0:
                        ax, ay = cx, cy
                    if bx * ey - by * ex > 0:
                        bx, by = ex, ey
            k = k2
        lonk[i] = lon
    # a sub-path of a straight path is straight: make lon nondecreasing
    for _ in (0, 1):
        for i in xrange(n - 1, -1, -1):
            nx_ = lonk[i + 1] if i + 1 < n else lonk[0] + n
            if lonk[i] > nx_:
                lonk[i] = nx_

    # clip0[i]: the furthest j such that the segment (i, j) is allowed, which
    # needs the path from i - 1 to j + 1 to be straight
    clip0 = [0] * (n + 1)
    for i in xrange(n):
        prev = lonk[i - 1] if i > 0 else lonk[n - 1] - n
        c = prev - 1
        if c < i + 1:
            c = i + 1
        if c > n:
            c = n
        clip0[i] = c
    clip0[n] = n
    for i in xrange(n - 1, -1, -1):  # keep it nondecreasing
        if clip0[i] > clip0[i + 1]:
            clip0[i] = clip0[i + 1]
    # clip1[j]: the smallest i with clip0[i] >= j
    clip1 = [0] * (n + 1)
    i = 0
    for j in xrange(1, n + 1):
        while clip0[i] < j:
            i += 1
        clip1[j] = i
    # fewest segments from 0 to n, greedily
    seg0 = [0]
    while seg0[-1] < n:
        seg0.append(clip0[seg0[-1]])
    m = len(seg0) - 1
    seg1 = [0] * (m + 1)
    seg1[m] = n
    for k in xrange(m - 1, -1, -1):
        seg1[k] = clip1[seg1[k + 1]]
    seg1[0] = 0

    # prefix sums of the vertices, relative to vertex 0 (exact integers)
    ox = xs[0]
    oy = ys[0]
    SX = [0] * (n + 2)
    SY = [0] * (n + 2)
    SXX = [0] * (n + 2)
    SXY = [0] * (n + 2)
    SYY = [0] * (n + 2)
    for k in xrange(n + 1):
        kk = k if k < n else 0
        px = xs[kk] - ox
        py = ys[kk] - oy
        SX[k + 1] = SX[k] + px
        SY[k + 1] = SY[k] + py
        SXX[k + 1] = SXX[k] + px * px
        SXY[k + 1] = SXY[k] + px * py
        SYY[k + 1] = SYY[k] + py * py
    RX = [xs[k] - ox for k in xrange(n)] + [0]
    RY = [ys[k] - oy for k in xrange(n)] + [0]

    sqrt = math.sqrt
    prev_lo = 0
    prev_cost = [0.0]
    backs = []
    for k in xrange(1, m + 1):
        lo = seg1[k]
        hi = seg0[k]
        cost = []
        back = []
        plo = seg1[k - 1]
        phi = seg0[k - 1]
        for j in xrange(lo, hi + 1):
            xj = RX[j]
            yj = RY[j]
            ilo = clip1[j]
            if ilo < plo:
                ilo = plo
            ihi = j - 1
            if ihi > phi:
                ihi = phi
            best = -1.0
            bi = -1
            for i in xrange(ilo, ihi + 1):
                xi = RX[i]
                yi = RY[i]
                a = yi - yj
                b = xj - xi
                c = -(a * xi + b * yi)
                N = j - i + 1
                S = (a * a * (SXX[j + 1] - SXX[i]) + b * b * (SYY[j + 1] - SYY[i])
                     + 2 * a * b * (SXY[j + 1] - SXY[i]) + 2 * a * c * (SX[j + 1] - SX[i])
                     + 2 * b * c * (SY[j + 1] - SY[i]) + c * c * N)
                v = prev_cost[i - prev_lo] + sqrt(S / N if S > 0 else 0.0)
                if bi < 0 or v < best:
                    best = v
                    bi = i
            cost.append(best)
            back.append(bi)
        backs.append((lo, back))
        prev_cost = cost
        prev_lo = lo
    idx = [n]
    j = n
    for k in xrange(m, 0, -1):
        lo, back = backs[k - 1]
        j = back[j - lo]
        idx.append(j)
    idx.reverse()
    return idx  # idx[0] == 0, idx[-1] == n


# ---------------------------------------------------------------------------
# Vertex adjustment
# ---------------------------------------------------------------------------

def _fit_line(n_, sx, sy, sxx, sxy, syy, fx, fy):
    """Normal (nx, ny) and offset c of the least-squares line n.p = c through
    n_ points with the given sums; (fx, fy) is a fallback direction."""
    mx = sx / n_
    my = sy / n_
    a = sxx / n_ - mx * mx
    b = sxy / n_ - mx * my
    c = syy / n_ - my * my
    if n_ >= 2 and (a + c) > 1e-12:
        lam = (a + c) / 2.0 - math.sqrt(((a - c) / 2.0) ** 2 + b * b)
        v1x, v1y = b, lam - a
        v2x, v2y = lam - c, b
        if v1x * v1x + v1y * v1y >= v2x * v2x + v2y * v2y:
            nx, ny = v1x, v1y
        else:
            nx, ny = v2x, v2y
        ln = math.hypot(nx, ny)
        if ln > 1e-12:
            nx /= ln
            ny /= ln
            return nx, ny, nx * mx + ny * my
    ln = math.hypot(fx, fy)
    if ln < 1e-12:
        return 1.0, 0.0, mx
    nx, ny = -fy / ln, fx / ln
    return nx, ny, nx * mx + ny * my


def _tangent_shift(nx, ny, c, px, py):
    """How far the line n.p = c must move along n to touch, at the middle of
    their span, the points (px, py) it was fitted to: the value at that middle
    of a parabola fitted to the residuals. Makes an edge fitted to a curved
    stretch its tangent rather than its secant."""
    cnt = len(px)
    if cnt < 5:
        return 0.0
    tx, ty = -ny, nx
    us = [tx * px[i] + ty * py[i] for i in xrange(cnt)]
    um = sum(us) / cnt
    s0 = float(cnt)
    s1 = s2 = s3 = s4 = r0 = r1 = r2 = 0.0
    umin = umax = us[0] - um
    for i in xrange(cnt):
        u = us[i] - um
        if u < umin:
            umin = u
        elif u > umax:
            umax = u
        r = nx * px[i] + ny * py[i] - c
        u2 = u * u
        s1 += u
        s2 += u2
        s3 += u2 * u
        s4 += u2 * u2
        r0 += r
        r1 += r * u
        r2 += r * u2
    # normal equations for r = a + b u + q u^2
    m = ((s0, s1, s2), (s1, s2, s3), (s2, s3, s4))
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    if abs(det) < 1e-9:
        return 0.0
    da = (r0 * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
          - m[0][1] * (r1 * m[2][2] - m[1][2] * r2)
          + m[0][2] * (r1 * m[2][1] - m[1][1] * r2))
    db = (m[0][0] * (r1 * m[2][2] - m[1][2] * r2)
          - r0 * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
          + m[0][2] * (m[1][0] * r2 - r1 * m[2][0]))
    dq = (m[0][0] * (m[1][1] * r2 - r1 * m[2][1])
          - m[0][1] * (m[1][0] * r2 - r1 * m[2][0])
          + r0 * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    u = (umin + umax) / 2.0
    shift = (da + db * u + dq * u * u) / det
    return max(-0.5, min(0.5, shift))


def _adjust(xs, ys, idx, half, qx=None, qy=None, tangent=False):
    """Moves every polygon vertex to the point within `half` (L-infinity) of
    its lattice vertex that is closest to the two adjacent fitted lines.
    The lines are fitted to the path vertices, or to the edge samples
    (qx, qy) when given; `tangent` moves each line onto the boundary at the
    middle of its stretch (see `_tangent_shift`). Returns absolute (x, y)
    vertices."""
    n = len(xs)
    m = len(idx) - 1
    ox = xs[0]
    oy = ys[0]
    if qx is None:
        inclusive = 1
        sx = [float(xs[k] - ox) for k in xrange(n)] + [0.0]
        sy = [float(ys[k] - oy) for k in xrange(n)] + [0.0]
    else:
        inclusive = 0
        sx = [qx[k] - ox for k in xrange(n)]
        sy = [qy[k] - oy for k in xrange(n)]
    ns = len(sx)
    SX = [0.0] * (ns + 1)
    SY = [0.0] * (ns + 1)
    SXX = [0.0] * (ns + 1)
    SXY = [0.0] * (ns + 1)
    SYY = [0.0] * (ns + 1)
    for k in xrange(ns):
        px = sx[k]
        py = sy[k]
        SX[k + 1] = SX[k] + px
        SY[k + 1] = SY[k] + py
        SXX[k + 1] = SXX[k] + px * px
        SXY[k + 1] = SXY[k] + px * py
        SYY[k + 1] = SYY[k] + py * py
    lines = []
    for k in xrange(m):
        i = idx[k]
        j = idx[k + 1]
        a = i
        b = j + inclusive
        cnt = b - a
        jj = j if j < n else 0
        fx = xs[jj] - xs[i]
        fy = ys[jj] - ys[i]
        if cnt <= 0:
            lines.append(_fit_line(1, 0.0, 0.0, 0.0, 0.0, 0.0, fx, fy))
            continue
        nx, ny, c = _fit_line(cnt, SX[b] - SX[a], SY[b] - SY[a], SXX[b] - SXX[a],
                              SXY[b] - SXY[a], SYY[b] - SYY[a], fx, fy)
        if tangent:
            c += _tangent_shift(nx, ny, c, sx[a:b], sy[a:b])
        lines.append((nx, ny, c))
    verts = []
    for k in xrange(m):
        n1x, n1y, c1 = lines[k - 1]
        n2x, n2y, c2 = lines[k]
        i = idx[k]
        cx = xs[i] - ox
        cy = ys[i] - oy
        A = n1x * n1x + n2x * n2x
        B = n1x * n1y + n2x * n2y
        C = n1y * n1y + n2y * n2y
        D = n1x * c1 + n2x * c2
        E = n1y * c1 + n2y * c2
        det = A * C - B * B
        if det > 1e-6:
            vx = (D * C - B * E) / det
            vy = (A * E - B * D) / det
        else:
            # nearly parallel lines: the point of their mean line closest to
            # the lattice vertex
            nx = n1x + n2x
            ny = n1y + n2y
            ln = math.hypot(nx, ny)
            if ln < 1e-9:
                nx, ny, ln = n2x, n2y, 1.0
            nx /= ln
            ny /= ln
            cm = (c1 * (n1x * nx + n1y * ny) + c2 * (n2x * nx + n2y * ny)) / 2.0
            off = cm - (nx * cx + ny * cy)
            vx = cx + off * nx
            vy = cy + off * ny
        if abs(vx - cx) > half or abs(vy - cy) > half:
            def q(x, y):
                return A * x * x + 2 * B * x * y + C * y * y - 2 * D * x - 2 * E * y
            best = None
            for ex in (cx - half, cx + half):
                y = (E - B * ex) / C if C > 1e-12 else cy
                y = min(max(y, cy - half), cy + half)
                val = q(ex, y)
                if best is None or val < best[0]:
                    best = (val, ex, y)
            for ey in (cy - half, cy + half):
                x = (D - B * ey) / A if A > 1e-12 else cx
                x = min(max(x, cx - half), cx + half)
                val = q(x, ey)
                if val < best[0]:
                    best = (val, x, ey)
            vx, vy = best[1], best[2]
        verts.append((vx + ox, vy + oy))
    return verts


def _edge_points(xs, ys, grows, cov):
    """Sub-pixel boundary samples, one per path edge: the edge midpoint moved
    along the edge normal by the ink coverage read from the two pixels on
    either side (`cov` maps gray to coverage; None keeps the midpoints).
    Returns two lists of absolute coordinates."""
    n = len(xs)
    qx = [0.0] * n
    qy = [0.0] * n
    for k in xrange(n):
        x = xs[k]
        y = ys[k]
        j = k + 1 if k + 1 < n else 0
        dx = xs[j] - x
        dy = ys[j] - y
        if cov is None:
            delta = 0.0
        else:
            if dx == 1:
                cin = cov[grows[y - 1][x]]
                cout = cov[grows[y][x]]
            elif dx == -1:
                cin = cov[grows[y][x - 1]]
                cout = cov[grows[y - 1][x - 1]]
            elif dy == 1:
                cin = cov[grows[y][x]]
                cout = cov[grows[y][x - 1]]
            else:
                cin = cov[grows[y - 1][x - 1]]
                cout = cov[grows[y - 1][x]]
            delta = cin + cout - 1.0
        # outward normal (paper side) is to the right of the step
        qx[k] = x + 0.5 * dx - delta * dy
        qy[k] = y + 0.5 * dy + delta * dx
    return qx, qy


def _refit(P0, P1, P2, P3, qx, qy):
    """Least-squares handle lengths for the cubic (P0, P1, P2, P3) through the
    points (qx, qy), keeping its end points and tangent directions. Returns
    new (P1, P2), or None when the fit is not trustworthy."""
    n = len(qx)
    if n < 4:
        return None
    u0x, u0y = P1[0] - P0[0], P1[1] - P0[1]
    u3x, u3y = P2[0] - P3[0], P2[1] - P3[1]
    L0 = math.hypot(u0x, u0y)
    L3 = math.hypot(u3x, u3y)
    if L0 < 1e-9 or L3 < 1e-9:
        return None
    u0x /= L0
    u0y /= L0
    u3x /= L3
    u3y /= L3
    dot = u0x * u3x + u0y * u3y
    # chord-length parameters
    ts = [0.0] * n
    acc = 0.0
    px, py = P0
    for i in xrange(n):
        acc += math.hypot(qx[i] - px, qy[i] - py)
        ts[i] = acc
        px, py = qx[i], qy[i]
    acc += math.hypot(P3[0] - px, P3[1] - py)
    if acc < 1e-9:
        return None
    ts = [t / acc for t in ts]
    p0x, p0y = P0
    p3x, p3y = P3
    a, b = L0, L3
    for it in xrange(3):
        s11 = s12 = s22 = r1 = r2 = 0.0
        for i in xrange(n):
            t = ts[i]
            mt = 1.0 - t
            b1 = 3.0 * mt * mt * t
            b2 = 3.0 * mt * t * t
            e0 = mt * mt * mt + b1
            e3 = b2 + t * t * t
            rx = qx[i] - e0 * p0x - e3 * p3x
            ry = qy[i] - e0 * p0y - e3 * p3y
            s11 += b1 * b1
            s12 += b1 * b2
            s22 += b2 * b2
            r1 += b1 * (u0x * rx + u0y * ry)
            r2 += b2 * (u3x * rx + u3y * ry)
        m12 = s12 * dot
        det = s11 * s22 - m12 * m12
        if det < 1e-12:
            return None
        a = (r1 * s22 - m12 * r2) / det
        b = (s11 * r2 - m12 * r1) / det
        if not (0.25 * L0 < a < 3.0 * L0 and 0.25 * L3 < b < 3.0 * L3):
            return None
        if it == 2:
            break
        # one Newton step per parameter toward the closest point
        c1x, c1y = p0x + a * u0x, p0y + a * u0y
        c2x, c2y = p3x + b * u3x, p3y + b * u3y
        for i in xrange(n):
            t = ts[i]
            mt = 1.0 - t
            bx = mt * mt * mt * p0x + 3 * mt * mt * t * c1x + 3 * mt * t * t * c2x + t * t * t * p3x
            by = mt * mt * mt * p0y + 3 * mt * mt * t * c1y + 3 * mt * t * t * c2y + t * t * t * p3y
            dx = 3 * (mt * mt * (c1x - p0x) + 2 * mt * t * (c2x - c1x) + t * t * (p3x - c2x))
            dy = 3 * (mt * mt * (c1y - p0y) + 2 * mt * t * (c2y - c1y) + t * t * (p3y - c2y))
            ddx = 6 * (mt * (c2x - 2 * c1x + p0x) + t * (p3x - 2 * c2x + c1x))
            ddy = 6 * (mt * (c2y - 2 * c1y + p0y) + t * (p3y - 2 * c2y + c1y))
            ex, ey = bx - qx[i], by - qy[i]
            f = ex * dx + ey * dy
            fp = dx * dx + dy * dy + ex * ddx + ey * ddy
            if fp > 1e-12:
                t -= f / fp
                ts[i] = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return (p0x + a * u0x, p0y + a * u0y), (p3x + b * u3x, p3y + b * u3y)


def _refit_curves(segs, spans, idx, n, qx, qy):
    """Refits every curve of a traced path to the edge samples it covers."""
    m = len(idx) - 1

    def vpos(k):
        q, r = divmod(k, m)
        return idx[r] + n * q

    prev_end = segs[-1][-1]
    for i in xrange(len(segs)):
        s = segs[i]
        start = prev_end
        prev_end = s[-1]
        if s[0] != "curve":
            continue
        ka, kb = spans[i]
        if kb < ka:
            kb += m
        ps = (vpos(ka - 1) + vpos(ka)) / 2.0
        pe = (vpos(kb) + vpos(kb + 1)) / 2.0
        j0 = int(math.ceil(ps - 0.5))
        j1 = int(math.floor(pe - 0.5))
        if j1 - j0 < 3:
            continue
        sx = [qx[j % n] for j in xrange(j0, j1 + 1)]
        sy = [qy[j % n] for j in xrange(j0, j1 + 1)]
        res = _refit(start, s[1], s[2], s[3], sx, sy)
        if res is not None:
            segs[i] = ("curve", res[0], res[1], s[3])


# ---------------------------------------------------------------------------
# Smoothing and curve optimization
# ---------------------------------------------------------------------------

def _bez(p0, p1, p2, p3, t):
    mt = 1.0 - t
    a = mt * mt * mt
    b = 3.0 * mt * mt * t
    c = 3.0 * mt * t * t
    d = t * t * t
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
            a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


def _tangent_t(p0, p1, p2, p3, wx, wy):
    """Parameter in [0, 1] where the curve's tangent points along (wx, wy),
    or None."""
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    bx, by = p2[0] - p1[0], p2[1] - p1[1]
    cx, cy = p3[0] - p2[0], p3[1] - p2[1]
    A = ax * wy - ay * wx
    B = bx * wy - by * wx
    C = cx * wy - cy * wx
    qa = A - 2.0 * B + C
    qb = 2.0 * (B - A)
    qc = A
    roots = []
    if abs(qa) < 1e-12:
        if abs(qb) > 1e-12:
            roots.append(-qc / qb)
    else:
        disc = qb * qb - 4.0 * qa * qc
        if disc < 0:
            if disc > -1e-12:
                disc = 0.0
            else:
                return None
        s = math.sqrt(disc)
        roots.append((-qb + s) / (2.0 * qa))
        roots.append((-qb - s) / (2.0 * qa))
    for t in roots:
        if -1e-9 <= t <= 1.0 + 1e-9:
            t = min(max(t, 0.0), 1.0)
            mt = 1.0 - t
            dx = mt * mt * ax + 2 * mt * t * bx + t * t * cx
            dy = mt * mt * ay + 2 * mt * t * by + t * t * cy
            if dx * wx + dy * wy > 0:
                return t
    return None


def _curve_area_ratio(a):
    """Area between a cubic and its chord, as a fraction of the triangle
    (start, corner, end), when both handles reach the fraction `a` of the way
    to the corner."""
    return 0.3 * (4.0 * a - a * a)


def _smooth(V, alphamax):
    """Corner flags, alphas, and edge midpoints for polygon vertices V."""
    m = len(V)
    S = []
    corner = []
    alpha = []
    for k in xrange(m):
        a = V[k - 1]
        b = V[k]
        c = V[(k + 1) % m]
        S.append(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))
        dx = c[0] - a[0]
        dy = c[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-12:
            al = 4.0 / 3.0
        else:
            dist = abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / ln / 2.0
            h = (abs(dx) + abs(dy)) / ln / 2.0
            al = (4.0 / 3.0) * (1.0 - h / dist) if dist > h else 0.0
        if al >= alphamax:
            corner.append(True)
            alpha.append(al)
        else:
            corner.append(False)
            alpha.append(min(max(al, 0.55), 1.0))
    return S, corner, alpha


def _curves(V, alphamax, opticurve, tol):
    """Segments for one closed polygon: a list of ("line", p) and
    ("curve", c1, c2, p), each starting where the previous one ends, and for
    each segment the first and last polygon vertex it stands for."""
    m = len(V)
    S, corner, alpha = _smooth(V, alphamax)
    E = [S[(k + 1) % m] for k in xrange(m)]
    C1 = []
    C2 = []
    for k in xrange(m):
        v = V[k]
        al = alpha[k]
        s = S[k]
        e = E[k]
        C1.append((s[0] + al * (v[0] - s[0]), s[1] + al * (v[1] - s[1])))
        C2.append((e[0] + al * (v[0] - e[0]), e[1] + al * (v[1] - e[1])))

    def single(k):
        if corner[k]:
            return [("line", V[k]), ("line", E[k])]
        return [("curve", C1[k], C2[k], E[k])]

    r = 0
    for k in xrange(m):
        if corner[k]:
            r = k
            break
    order = [(r + t) % m for t in xrange(m)]
    if not opticurve or m < 3:
        out = []
        spans = []
        for k in order:
            s = single(k)
            out.extend(s)
            spans.extend([(k, k)] * len(s))
        return out, spans

    # convexity and turning angle at every vertex
    sign = []
    turn = []
    for k in xrange(m):
        a = V[k - 1]
        b = V[k]
        c = V[(k + 1) % m]
        ux, uy = b[0] - a[0], b[1] - a[1]
        wx, wy = c[0] - b[0], c[1] - b[1]
        cr = ux * wy - uy * wx
        sign.append(1 if cr > 0 else (-1 if cr < 0 else 0))
        turn.append(abs(math.atan2(cr, ux * wx + uy * wy)))
    limit = math.radians(179.0)

    def merge(a, b):
        ka = order[a]
        kb = order[b]
        P0 = S[ka]
        P3 = E[kb]
        va = V[ka]
        vp = V[ka - 1]
        vb = V[kb]
        vn = V[(kb + 1) % m]
        d0x, d0y = va[0] - vp[0], va[1] - vp[1]
        d1x, d1y = vn[0] - vb[0], vn[1] - vb[1]
        den = d0x * d1y - d0y * d1x
        if abs(den) < 1e-12:
            return None
        rx, ry = P3[0] - P0[0], P3[1] - P0[1]
        u = (rx * d1y - ry * d1x) / den
        w = (ry * d0x - rx * d0y) / den
        if u <= 0 or w <= 0:
            return None
        O = (P0[0] + u * d0x, P0[1] + u * d0y)
        # area between the chain of curves and the chord, relative to P0
        area = 0.0
        px, py = 0.0, 0.0
        for t in xrange(a, b + 1):
            k = order[t]
            e = E[k]
            qx, qy = e[0] - P0[0], e[1] - P0[1]
            area += px * qy - py * qx
            px, py = qx, qy
            s = S[k]
            v = V[k]
            tri = (v[0] - s[0]) * (e[1] - s[1]) - (v[1] - s[1]) * (e[0] - s[0])
            area += _curve_area_ratio(alpha[k]) * tri
        T = (O[0] - P0[0]) * ry - (O[1] - P0[1]) * rx
        if abs(T) < 1e-12:
            return None
        R = area / T
        if R <= 0 or R > _curve_area_ratio(1.0):
            return None
        s = 2.0 - math.sqrt(max(0.0, 4.0 - R / 0.3))
        P1 = (P0[0] + s * (O[0] - P0[0]), P0[1] + s * (O[1] - P0[1]))
        P2 = (P3[0] + s * (O[0] - P3[0]), P3[1] + s * (O[1] - P3[1]))
        pen = 0.0
        # junctions between the original curves: same tangent, close by
        for t in xrange(a + 1, b + 1):
            k = order[t]
            v0 = V[k - 1]
            v1 = V[k]
            wx, wy = v1[0] - v0[0], v1[1] - v0[1]
            tt = _tangent_t(P0, P1, P2, P3, wx, wy)
            if tt is None:
                return None
            p = _bez(P0, P1, P2, P3, tt)
            ln = math.hypot(wx, wy)
            q = S[k]
            dd = (wx * (p[1] - q[1]) - wy * (p[0] - q[0])) / ln
            if abs(dd) > tol:
                return None
            # the touching point must lie along this polygon edge
            uu = ((p[0] - v0[0]) * wx + (p[1] - v0[1]) * wy) / (ln * ln)
            if uu < -0.25 or uu > 1.25:
                return None
            pen += dd * dd
        # the middle of every original curve
        for t in xrange(a, b + 1):
            k = order[t]
            s0 = S[k]
            e0 = E[k]
            wx, wy = e0[0] - s0[0], e0[1] - s0[1]
            ln = math.hypot(wx, wy)
            if ln < 1e-12:
                continue
            tt = _tangent_t(P0, P1, P2, P3, wx, wy)
            if tt is None:
                return None
            p = _bez(P0, P1, P2, P3, tt)
            q = _bez(s0, C1[k], C2[k], e0, 0.5)
            dd = (wx * (p[1] - q[1]) - wy * (p[0] - q[0])) / ln
            if abs(dd) > tol:
                return None
            pen += dd * dd
        return pen, P1, P2, P3

    # candidate runs: smooth vertices of one convexity, turning less than
    # `limit` in total
    cand = {}
    for a in xrange(m):
        ka = order[a]
        if corner[ka] or sign[ka] == 0:
            continue
        tsum = turn[ka]
        for b in xrange(a + 1, m):
            kb = order[b]
            if corner[kb] or sign[kb] != sign[ka]:
                break
            tsum += turn[kb]
            if tsum >= limit:
                break
            res = merge(a, b)
            if res is not None:
                cand[(a, b)] = res
    # fewest segments, then least penalty
    INF = (1 << 30, 0.0)
    best = [INF] * (m + 1)
    prev = [-1] * (m + 1)
    best[0] = (0, 0.0)
    ends = {}
    for (a, b) in sorted(cand):  # sorted: the same choice on Python 2 and 3
        ends.setdefault(b + 1, []).append(a)
    for j in xrange(1, m + 1):
        c0, p0 = best[j - 1]
        best[j] = (c0 + 1, p0)
        prev[j] = j - 1
        for a in ends.get(j, ()):
            ca, pa = best[a]
            pen = cand[(a, j - 1)][0]
            v = (ca + 1, pa + pen)
            if v < best[j]:
                best[j] = v
                prev[j] = a
    pieces = []
    j = m
    while j > 0:
        a = prev[j]
        pieces.append((a, j - 1))
        j = a
    pieces.reverse()
    out = []
    spans = []
    for a, b in pieces:
        if a == b:
            s = single(order[a])
            out.extend(s)
            spans.extend([(order[a], order[a])] * len(s))
        else:
            _, P1, P2, P3 = cand[(a, b)]
            out.append(("curve", P1, P2, P3))
            spans.append((order[a], order[b]))
    return out, spans


def _drop_collinear(segs):
    """Removes line end points that lie on the straight line through their
    neighbors (midpoints between two corners)."""
    changed = True
    while changed and len(segs) > 3:
        changed = False
        n = len(segs)
        for k in xrange(n):
            s = segs[k]
            t = segs[(k + 1) % n]
            if s[0] != "line" or t[0] != "line":
                continue
            p = segs[k - 1][-1]
            q = s[1]
            r = t[1]
            ux, uy = q[0] - p[0], q[1] - p[1]
            wx, wy = r[0] - q[0], r[1] - q[1]
            lu = math.hypot(ux, uy)
            lw = math.hypot(wx, wy)
            if lu < 1e-12 or lw < 1e-12:
                del segs[k]
                changed = True
                break
            if abs(ux * wy - uy * wx) < 1e-9 * lu * lw and ux * wx + uy * wy > 0:
                del segs[k]
                changed = True
                break
    return segs


# ---------------------------------------------------------------------------
# Tracing entry point
# ---------------------------------------------------------------------------

def trace(gray, width, height, threshold=128, turdsize=2, turnpolicy="minority",
          alphamax=1.0, opticurve=True, opttolerance=0.2, stride=None,
          refine=True, tangent=True, refit=False, upsample=1, denoise=False,
          report=None):
    """Traces a grayscale image into closed outlines.

    gray: bytes, bytearray, or str of 8-bit pixels, row-major, top row first,
        0 = black ink, 255 = paper; `stride` bytes per row (default `width`).
    threshold: pixels darker than this are ink; None picks the midpoint of
        the estimated ink and paper levels.
    turdsize: paths enclosing this many pixels or fewer are dropped (specks
        of ink and pinholes in ink alike).
    turnpolicy: how diagonal pixel junctions are resolved, one of
        TURN_POLICIES ("left" and "right" are relative to a path that keeps
        ink on its left, so they act like "white" and "black").
    alphamax: corner threshold (0 makes every vertex a corner, 4/3 none).
    opticurve, opttolerance: join runs of curves when the joined curve stays
        within `opttolerance` pixels of them.
    refine: fit the polygon edges to sub-pixel boundary points estimated from
        the antialiased gray levels instead of the pixel corners (same node
        count, smaller deviation on antialiased and scanned images).
    tangent: move each fitted polygon edge onto the boundary at the middle of
        its stretch, so that edges along curves are tangents rather than
        secants; this removes the published algorithm's bias of curves
        toward their center of curvature. With refine and tangent both
        False, the result follows the published algorithm.
    refit: afterwards, refit each curve's handle lengths by least squares to
        the boundary points it covers (end points and tangents unchanged);
        off by default, as it did not help on the test glyphs.
    upsample: 2 traces a twice-enlarged bilinear interpolation of the image:
        about half the deviation on antialiased images, but about twice the
        nodes and time, and unusable on binary images; 1 traces the pixels as
        they are.
    denoise: threshold a 3 x 3 tent-filtered image (computed next to the
        boundary only): far fewer nodes on noisy scans, rounder corners.
    report: an optional dict that receives "specks" (dropped paths as
        (x, y, area, kind)), "kinds" ("outer" or "hole" per contour),
        "parents" (index of the enclosing contour or -1), and "levels".

    Returns a list of contours in pixel coordinates (y down). Each contour is
    a list of ("line", (x, y)) and ("curve", (x1, y1), (x2, y2), (x, y))
    segments, each starting at the end of the previous one (the last ends at
    the start of the first). Outer contours run counterclockwise once y
    points up (negative shoelace area in pixel space), holes the other way.
    """
    gray = _as_bytes(gray)
    if stride is None:
        stride = width
    if len(gray) < stride * (height - 1) + width:
        raise ValueError("gray holds fewer than height rows of width pixels")
    if turnpolicy not in TURN_POLICIES:
        raise ValueError("unknown turn policy: %r" % (turnpolicy,))
    levels = None
    if threshold is None or refine:
        levels = gray_levels(gray, width, height, 128 if threshold is None else threshold, stride)
        if threshold is None:
            threshold = (levels[0] + levels[1] + 1) // 2
    rows = _ink_rows(gray, width, height, threshold, stride)
    grows = None
    if denoise or refine or upsample == 2:
        grows = _gray_rows(gray, width, height, stride)
    if denoise:
        _denoise(rows, grows, width, height, threshold, turnpolicy)
    factor = 1
    w, h = width, height
    if upsample == 2:
        rows, w, h = _upsample2(rows, grows, width, height, threshold, turnpolicy)
        factor = 2
        turdsize = turdsize * 4
        opttolerance = opttolerance * 2  # stays in source pixels
        refine = False
        refit = False
    elif upsample != 1:
        raise ValueError("upsample must be 1 or 2")
    paths = _decompose(rows, w, h, turdsize, turnpolicy, report)
    cov = None
    half = 0.5
    if refine:
        lo, hi = levels
        cov = [min(1.0, max(0.0, (hi - v) / float(hi - lo))) for v in xrange(256)]
        half = 1.0
    contours = []
    kinds = []
    inv = 1.0 / factor
    for xs, ys, area in paths:
        idx = _polygon(xs, ys)
        if len(idx) < 4:  # fewer than three edges: keep the path's corners
            idx = [k for k in xrange(len(xs))
                   if (xs[k] - xs[k - 1], ys[k] - ys[k - 1]) !=
                   (xs[(k + 1) % len(xs)] - xs[k], ys[(k + 1) % len(xs)] - ys[k])]
            if idx[0] != 0:
                idx = [0] + idx
            idx.append(len(xs))
        qx = qy = None
        if refine or refit:
            qx, qy = _edge_points(xs, ys, grows, cov)
        if refine:
            V = _adjust(xs, ys, idx, half, qx, qy, tangent)
        else:
            V = _adjust(xs, ys, idx, half, tangent=tangent)
        segs, spans = _curves(V, alphamax, opticurve, opttolerance)
        if refit:
            _refit_curves(segs, spans, idx, len(xs), qx, qy)
        segs = _drop_collinear(segs)
        out = []
        for s in segs:
            if s[0] == "line":
                p = s[1]
                out.append(("line", ((p[0] - 1) * inv, (p[1] - 1) * inv)))
            else:
                out.append(("curve",) + tuple(((p[0] - 1) * inv, (p[1] - 1) * inv) for p in s[1:]))
        contours.append(out)
        kinds.append("outer" if area < 0 else "hole")
    if report is not None:
        report["kinds"] = kinds
        report["parents"] = _nesting(paths)
        report["levels"] = levels
        report["threshold"] = threshold
        if factor != 1:
            report["specks"] = [(x * inv, y * inv, a * inv * inv, k)
                                for x, y, a, k in report.get("specks", [])]
    return contours


# ---------------------------------------------------------------------------
# Font units, extremes, rounding
# ---------------------------------------------------------------------------

def _angle(ax, ay, bx, by):
    la = math.hypot(ax, ay)
    lb = math.hypot(bx, by)
    if la < 1e-12 or lb < 1e-12:
        return 0.0
    c = (ax * bx + ay * by) / (la * lb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _kinds(pts, segs):
    """'smooth' or 'on' for every on-curve point of a parsed contour."""
    n = len(pts)
    out = []
    for k in xrange(n):
        p = pts[k]
        sin = segs[k - 1]
        sout = segs[k]
        if sin is None and sout is None:
            out.append("on")
            continue
        q = pts[k - 1]
        if sin is None:
            ix, iy = p[0] - q[0], p[1] - q[1]
        else:
            c1, c2 = sin
            ix, iy = p[0] - c2[0], p[1] - c2[1]
            if abs(ix) + abs(iy) < 1e-9:
                ix, iy = p[0] - c1[0], p[1] - c1[1]
        r = pts[(k + 1) % n]
        if sout is None:
            ox, oy = r[0] - p[0], r[1] - p[1]
        else:
            c1, c2 = sout
            ox, oy = c1[0] - p[0], c1[1] - p[1]
            if abs(ox) + abs(oy) < 1e-9:
                ox, oy = c2[0] - p[0], c2[1] - p[1]
        out.append("smooth" if _angle(ix, iy, ox, oy) < 0.5 else "on")
    return out


def _emit(pts, kinds, segs):
    nodes = []
    for k in xrange(len(pts)):
        p = pts[k]
        nodes.append((p[0], p[1], kinds[k]))
        s = segs[k]
        if s is not None:
            nodes.append((s[0][0], s[0][1], "off"))
            nodes.append((s[1][0], s[1][1], "off"))
    return nodes


def _parse(nodes):
    """Splits a closed node list (on, off, off, on, ...) into on-curve points,
    their kinds, and per-segment handles (None for lines)."""
    n = len(nodes)
    start = 0
    while start < n and nodes[start][2] == "off":
        start += 1
    if start == n:
        return [], [], []
    nodes = list(nodes[start:]) + list(nodes[:start])
    pts = []
    kinds = []
    segs = []
    i = 0
    while i < n:
        x, y, kind = nodes[i]
        pts.append([float(x), float(y)])
        kinds.append(kind)
        if i + 1 < n + 1 and nodes[(i + 1) % n][2] == "off":
            a = nodes[(i + 1) % n]
            b = nodes[(i + 2) % n]
            segs.append([[float(a[0]), float(a[1])], [float(b[0]), float(b[1])]])
            i += 3
        else:
            segs.append(None)
            i += 1
    return pts, kinds, segs


def to_font(contours, scale, x0, y_top):
    """Maps traced contours to font units (x = x0 + px * scale,
    y = y_top - py * scale) and returns them as FontLab-style node lists of
    (x, y, kind), kind being "on" (corner), "smooth" (tangent-continuous
    on-curve node), or "off" (cubic handle), starting with an on-curve node.
    Outer contours come out counterclockwise and holes clockwise."""
    out = []
    for c in contours:
        if not c:
            continue
        pts = []
        segs = []
        e = c[-1][-1]
        prev = (x0 + e[0] * scale, y_top - e[1] * scale)
        for s in c:
            pts.append(prev)
            if s[0] == "line":
                segs.append(None)
                p = s[1]
            else:
                segs.append(((x0 + s[1][0] * scale, y_top - s[1][1] * scale),
                             (x0 + s[2][0] * scale, y_top - s[2][1] * scale)))
                p = s[3]
            prev = (x0 + p[0] * scale, y_top - p[1] * scale)
        out.append(_emit(pts, _kinds(pts, segs), segs))
    return out


def _lerp(a, b, t):
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]


def _split(p0, c1, c2, p3, t):
    a = _lerp(p0, c1, t)
    b = _lerp(c1, c2, t)
    c = _lerp(c2, p3, t)
    d = _lerp(a, b, t)
    e = _lerp(b, c, t)
    f = _lerp(d, e, t)
    return (a, d, f), (e, c)


def _extreme_ts(p0, c1, c2, p3, axis):
    """Parameters in (0, 1) where the curve's derivative along `axis`
    (0 = x, 1 = y) vanishes."""
    a = c1[axis] - p0[axis]
    b = c2[axis] - c1[axis]
    c = p3[axis] - c2[axis]
    qa = a - 2.0 * b + c
    qb = 2.0 * (b - a)
    qc = a
    eps = 1e-9
    out = []
    if abs(qa) < 1e-12:
        if abs(qb) > 1e-12:
            out.append(-qc / qb)
    else:
        disc = qb * qb - 4.0 * qa * qc
        if disc >= 0:
            s = math.sqrt(disc)
            out.append((-qb + s) / (2.0 * qa))
            out.append((-qb - s) / (2.0 * qa))
    return [t for t in out if eps < t < 1.0 - eps]


def _contours_arg(nodes):
    """True when `nodes` is a list of contours rather than one contour."""
    return bool(nodes) and isinstance(nodes[0], list) and nodes[0] and \
        isinstance(nodes[0][0], (list, tuple))


def extremes(nodes, min_segment=0.5, round_coords=False):
    """Adds on-curve nodes at every horizontal and vertical extreme of every
    curve (exact de Casteljau splits, so the shape is unchanged). When a split
    would leave a piece shorter than `min_segment` units, the curve is nudged
    instead: the handle at the nearby node is made horizontal or vertical (and
    the other handle of a smooth node with it), which puts the extreme on that
    node. Then optionally rounds to integers with `round_nodes`.

    Accepts one node list or a list of them, and returns the same shape."""
    if _contours_arg(nodes):
        return [extremes(c, min_segment, round_coords) for c in nodes]
    pts, kinds, segs = _parse(nodes)
    n = len(pts)
    if n == 0:
        return []
    # snap handles that are already axis-aligned to within rounding noise
    for k in xrange(n):
        s = segs[k]
        if s is None:
            continue
        for h, p in ((s[0], pts[k]), (s[1], pts[(k + 1) % n])):
            for ax in (0, 1):
                if abs(h[ax] - p[ax]) < 1e-7 * (1.0 + abs(h[1 - ax] - p[1 - ax])):
                    h[ax] = p[ax]
    # nudge extremes that sit too close to a node: make the handles at that
    # node level, when that moves them by no more than `max_nudge`;
    # otherwise the curve stays whole and its extreme stays within
    # `min_segment` of the node
    max_nudge = max(1.0, 2.0 * min_segment)
    for k in xrange(n):
        s = segs[k]
        if s is None:
            continue
        p0 = pts[k]
        p3 = pts[(k + 1) % n]
        for axis in (0, 1):
            for t in _extreme_ts(p0, s[0], s[1], p3, axis):
                (a, d, f), _ = _split(p0, s[0], s[1], p3, t)
                if math.hypot(f[0] - p0[0], f[1] - p0[1]) < min_segment:
                    j, mine, pend = k, s[0], 1
                    other = segs[k - 1]
                elif math.hypot(p3[0] - f[0], p3[1] - f[1]) < min_segment:
                    j = (k + 1) % n
                    mine, pend = s[1], 0
                    other = segs[j]
                else:
                    continue
                node = pts[j]
                smooth = kinds[j] == "smooth"
                if smooth and other is None:
                    continue  # a line fixes this tangent
                move = abs(mine[axis] - node[axis])
                if smooth:
                    move = max(move, abs(other[pend][axis] - node[axis]))
                if move > max_nudge:
                    continue
                mine[axis] = node[axis]
                if smooth:
                    other[pend][axis] = node[axis]
    # split at the remaining extremes
    npts = []
    nkinds = []
    nsegs = []
    for k in xrange(n):
        s = segs[k]
        p0 = pts[k]
        npts.append(p0)
        nkinds.append(kinds[k])
        if s is None:
            nsegs.append(None)
            continue
        p3 = pts[(k + 1) % n]
        ts = [(t, 0) for t in _extreme_ts(p0, s[0], s[1], p3, 0)]
        ts += [(t, 1) for t in _extreme_ts(p0, s[0], s[1], p3, 1)]
        ts.sort()
        c1, c2 = s
        cur0 = p0
        consumed = 0.0
        for t, axis in ts:
            tl = (t - consumed) / (1.0 - consumed)
            if tl <= 1e-9 or tl >= 1.0 - 1e-9:
                continue
            (a, d, f), (e, c) = _split(cur0, c1, c2, p3, tl)
            if math.hypot(f[0] - cur0[0], f[1] - cur0[1]) < min_segment or \
                    math.hypot(p3[0] - f[0], p3[1] - f[1]) < min_segment:
                continue
            d[axis] = f[axis]
            e[axis] = f[axis]
            nsegs.append([a, d])
            npts.append(f)
            nkinds.append("smooth")
            cur0, c1, c2 = f, e, c
            consumed = t
        nsegs.append([c1, c2])
    result = _emit(npts, nkinds, nsegs)
    if round_coords:
        result = round_nodes(result)
    return result


def _gcd(a, b):
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def _primitive_dirs(tx, ty, maxlen):
    """Primitive integer vectors pointing close to the unit vector (tx, ty),
    with the larger component at most `maxlen`."""
    out = []
    if abs(tx) >= abs(ty):
        s = 1 if tx > 0 else -1
        slope = ty / tx
        for p in xrange(1, maxlen + 1):
            f = int(math.floor(p * slope))
            for q in (f, f + 1):
                if _gcd(p, q) == 1:
                    out.append((s * p, s * q))
    else:
        s = 1 if ty > 0 else -1
        slope = tx / ty
        for p in xrange(1, maxlen + 1):
            f = int(math.floor(p * slope))
            for q in (f, f + 1):
                if _gcd(p, q) == 1:
                    out.append((s * q, s * p))
    return out


def _collinear_handles(tx, ty, lin, lout):
    """Integer offsets (in, out) from a smooth node for its two handles, both
    multiples of one primitive integer vector (so exactly collinear), near
    -lin * t and lout * t for the unit tangent t = (tx, ty)."""
    maxlen = int(min(64.0, max(1.0, max(lin, lout) + 1.0)))
    best = None
    for vx, vy in _primitive_dirs(tx, ty, maxlen):
        lv = math.hypot(vx, vy)
        a = max(1, _rnd(lout / lv))
        b = max(1, _rnd(lin / lv))
        d1 = math.hypot(a * vx - lout * tx, a * vy - lout * ty)
        d2 = math.hypot(b * vx - lin * tx, b * vy - lin * ty)
        key = (max(d1, d2), d1 + d2)
        if best is None or key < best[0]:
            best = (key, (-b * vx, -b * vy), (a * vx, a * vy))
    return best[1], best[2]


def _near_points(x, y, radius):
    """Integer points within `radius` of (x, y), nearest first, as
    (distance, (px, py))."""
    out = []
    x0 = int(math.floor(x - radius))
    y0 = int(math.floor(y - radius))
    r2 = radius * radius
    for px in xrange(x0, x0 + int(2 * radius) + 2):
        for py in xrange(y0, y0 + int(2 * radius) + 2):
            d2 = (px - x) ** 2 + (py - y) ** 2
            if d2 <= r2:
                out.append((math.sqrt(d2), (px, py)))
    out.sort()
    return out


def _smooth_pair(node, hin, hout, tx, ty, lin, lout, max_angle=0.95):
    """Integer positions for the two handles of a smooth node at integer
    `node`, near the ideal positions `hin` and `hout`: either exactly
    collinear (multiples of one primitive vector) or within `max_angle`
    degrees, whichever moves the handles least."""
    oin, oout = _collinear_handles(tx, ty, lin, lout)
    bin_ = (node[0] + oin[0], node[1] + oin[1])
    bout = (node[0] + oout[0], node[1] + oout[1])
    best = max(math.hypot(bin_[0] - hin[0], bin_[1] - hin[1]),
               math.hypot(bout[0] - hout[0], bout[1] - hout[1]))
    if best <= 0.75:
        return bin_, bout
    cos_min = math.cos(math.radians(max_angle))
    cin = _near_points(hin[0], hin[1], min(best, 2.5))
    cout = _near_points(hout[0], hout[1], min(best, 2.5))
    nx, ny = node
    for do, po in cout:
        if do >= best:
            break
        ox, oy = po[0] - nx, po[1] - ny
        lo = math.hypot(ox, oy)
        if lo < 1e-9:
            continue
        for di, pi in cin:
            if di >= best:
                break
            ix, iy = nx - pi[0], ny - pi[1]
            li = math.hypot(ix, iy)
            if li < 1e-9:
                continue
            if (ix * ox + iy * oy) >= cos_min * li * lo:
                m = max(do, di)
                if m < best:
                    best = m
                    bin_, bout = pi, po
                break
    return bin_, bout


def _line_handle(vx, vy, length):
    """Integer offset for a handle that continues a line with integer
    direction (vx, vy) at a smooth node: an exact multiple of the line's
    primitive direction when that lands within a unit or so, otherwise the
    integer point closest in direction among those of about the right length.
    Returns (offset, angle error in degrees, displacement)."""
    g = _gcd(vx, vy)
    px, py = vx // g, vy // g
    lp = math.hypot(px, py)
    ll = math.hypot(vx, vy)
    tx, ty = vx / ll, vy / ll
    a = max(1, _rnd(length / lp))
    best = ((a * px, a * py), 0.0, abs(a * lp - length))
    if best[2] <= 1.0:
        return best
    span = max(2, int(0.35 * length) + 1)
    major_x = abs(tx) >= abs(ty)
    center = _rnd((tx if major_x else ty) * length)
    sgn = 1 if (tx if major_x else ty) > 0 else -1
    for u in xrange(center - span, center + span + 1):
        if u * sgn <= 0:
            continue
        if major_x:
            du, dv = u, _rnd(u * ty / tx)
        else:
            du, dv = _rnd(u * tx / ty), u
        err = abs(math.degrees(math.atan2(du * ty - dv * tx, du * tx + dv * ty)))
        disp = math.hypot(du - length * tx, dv - length * ty)
        if err <= 1.0 and disp < best[2]:
            best = ((du, dv), err, disp)
    return best


def round_nodes(nodes):
    """Rounds node coordinates to integers. Handles move with their node
    before rounding, and the handles of smooth nodes are then placed so that
    they stay collinear with the node (within 1 degree; exactly when the
    tangent is horizontal or vertical). Degenerate segments are removed.

    Accepts one node list or a list of them, and returns the same shape."""
    if _contours_arg(nodes):
        return [round_nodes(c) for c in nodes]
    pts, kinds, segs = _parse(nodes)
    n = len(pts)
    if n == 0:
        return []
    rp = [(_rnd(p[0]), _rnd(p[1])) for p in pts]
    rs = []
    for k in xrange(n):
        s = segs[k]
        if s is None:
            rs.append(None)
            continue
        a = pts[k]
        b = pts[(k + 1) % n]
        ra = rp[k]
        rb = rp[(k + 1) % n]
        h1 = (s[0][0] + ra[0] - a[0], s[0][1] + ra[1] - a[1])
        h2 = (s[1][0] + rb[0] - b[0], s[1][1] + rb[1] - b[1])
        rs.append([h1, h2])
    # axes in which each node is an extreme (its curve handles level with it)
    ext = []
    for k in xrange(n):
        p = pts[k]
        hs = []
        if segs[k - 1] is not None:
            hs.append(segs[k - 1][1])
        if segs[k] is not None:
            hs.append(segs[k][0])
        ext.append(tuple(ax for ax in (0, 1) if hs and all(h[ax] == p[ax] for h in hs)))
    # merge nodes that round onto their successor: the segment between them
    # vanishes, and the surviving node keeps a corner or an extreme that
    # either of them had
    k = 0
    while len(rp) > 2 and k < len(rp):
        j = (k + 1) % len(rp)
        if rp[k] != rp[j]:
            k += 1
            continue
        kind = "on" if "on" in (kinds[k], kinds[j]) else "smooth"
        axes = tuple(sorted(set(ext[k]) | set(ext[j])))
        del rp[k], kinds[k], rs[k], ext[k]
        j = k if k < len(rp) else 0
        kinds[j] = kind
        ext[j] = axes
        k = max(0, k - 1)
    n = len(rp)
    if n < 2:
        return []
    for k in xrange(n):
        node = rp[k]
        for ax in ext[k]:
            for s, e in ((rs[k - 1], 1), (rs[k], 0)):
                if s is not None:
                    h = list(s[e])
                    h[ax] = node[ax]
                    s[e] = tuple(h)
    # smooth nodes: both handles on one integer direction
    for k in xrange(n):
        if kinds[k] != "smooth":
            continue
        sin = rs[k - 1]
        sout = rs[k]
        node = rp[k]
        if sin is None and sout is None:
            continue
        if sin is not None and sout is not None:
            ix, iy = node[0] - sin[1][0], node[1] - sin[1][1]
            ox, oy = sout[0][0] - node[0], sout[0][1] - node[1]
            li = math.hypot(ix, iy)
            lo = math.hypot(ox, oy)
            if li < 1e-9 or lo < 1e-9:
                continue
            dx, dy = ix / li + ox / lo, iy / li + oy / lo
            ln = math.hypot(dx, dy)
            if ln < 1e-9:
                continue
            sin[1], sout[0] = _smooth_pair(node, sin[1], sout[0], dx / ln, dy / ln, li, lo)
            continue
        # a line on one side fixes the direction; when the exact direction
        # is out of reach, try moving the node by one unit (the line's other
        # end is a corner, so nothing else depends on it)
        if sin is None:
            other = rp[k - 1]
            h = sout[0]
            sign = 1
        else:
            other = rp[(k + 1) % n]
            h = sin[1]
            sign = -1
        L = math.hypot(h[0] - node[0], h[1] - node[1])
        hx, hy = h[0] - node[0], h[1] - node[1]
        shifts = [(0, 0)]
        other_kind = kinds[k - 1] if sin is None else kinds[(k + 1) % n]
        if other_kind != "smooth":
            shifts += [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        best = None
        for sx, sy in shifts:
            nd = (node[0] + sx, node[1] + sy)
            if sign > 0:
                vx, vy = nd[0] - other[0], nd[1] - other[1]
            else:
                vx, vy = other[0] - nd[0], other[1] - nd[1]
            if vx == 0 and vy == 0:
                continue
            off, err, disp = _line_handle(sign * vx, sign * vy, L)
            # displacement of the handle relative to where it was, plus the
            # node's own move
            dh = math.hypot(nd[0] + off[0] - node[0] - hx, nd[1] + off[1] - node[1] - hy)
            key = (err > 1.0, dh + math.hypot(sx, sy), err)
            if best is None or key < best[0]:
                best = (key, nd, off)
            if (sx, sy) == (0, 0) and err <= 1.0 and dh <= 1.0:
                break
        if best is None:
            continue
        nd, off = best[1], best[2]
        if nd != node:
            # keep the curve's other handles where they were relative to it
            rp[k] = nd
            node = nd
        hpos = (node[0] + off[0], node[1] + off[1])
        if sin is None:
            sout[0] = hpos
        else:
            sin[1] = hpos
    # remaining handles: plain rounding
    for k in xrange(n):
        s = rs[k]
        if s is None:
            continue
        s[0] = (_rnd(s[0][0]), _rnd(s[0][1]))
        s[1] = (_rnd(s[1][0]), _rnd(s[1][1]))
    # keep every handle inside its curve's end-point box, so that rounding
    # cannot add extremes between nodes. A handle that pokes out on its own
    # node's side is flattened onto the node's coordinate (with the other
    # handle of a smooth node); one that pokes out past the far end is
    # shortened along its own direction at smooth nodes, clamped elsewhere.
    for k in xrange(n):
        s = rs[k]
        if s is None:
            continue
        p = rp[k]
        q = rp[(k + 1) % n]
        lo = (min(p[0], q[0]), min(p[1], q[1]))
        hi = (max(p[0], q[0]), max(p[1], q[1]))
        # Only an axis along which the curve itself passes its end points
        # (an extreme between the nodes) is clamped: a handle outside the box
        # of a curve that stays monotone is left where it is (a valid curve,
        # integral already, was moved by 40/9 units otherwise: review 9)
        overshoot = []
        for ax in (0, 1):
            far = 0.0
            for t in _extreme_ts(p, s[0], s[1], q, ax):
                v = _bez(p, s[0], s[1], q, t)[ax]
                far = max(far, lo[ax] - v, v - hi[ax])
            overshoot.append(far > 0.25)
        for end in (0, 1):
            j = k if end == 0 else (k + 1) % n
            node = rp[j]
            h = list(s[end])
            for ax in (0, 1):
                if not overshoot[ax] or lo[ax] <= h[ax] <= hi[ax]:
                    continue
                v = lo[ax] if h[ax] < lo[ax] else hi[ax]
                if node[ax] == v:
                    partner = rs[j - 1] if end == 0 else rs[j]
                    if kinds[j] == "smooth":
                        if partner is None:
                            continue  # a line fixes this tangent
                        pi = 1 if end == 0 else 0
                        ph = list(partner[pi])
                        ph[ax] = v
                        partner[pi] = tuple(ph)
                    h[ax] = v
                elif kinds[j] == "smooth":
                    dx, dy = h[0] - node[0], h[1] - node[1]
                    g = _gcd(dx, dy)
                    if g == 0:
                        continue
                    ux, uy = dx // g, dy // g
                    a = g
                    while a > 1 and not (lo[0] <= node[0] + a * ux <= hi[0] and
                                         lo[1] <= node[1] + a * uy <= hi[1]):
                        a -= 1
                    h = [node[0] + a * ux, node[1] + a * uy]
                else:
                    h[ax] = v
            s[end] = tuple(h)
    # drop zero-length segments
    keep_pts = []
    keep_kinds = []
    keep_segs = []
    for k in xrange(n):
        p = rp[k]
        q = rp[(k + 1) % n]
        if p == q:
            continue  # the next node takes over; this segment vanishes
        keep_pts.append(p)
        keep_kinds.append(kinds[k])
        keep_segs.append(rs[k])
    if len(keep_pts) < 2:
        return []
    return _emit(keep_pts, keep_kinds, keep_segs)


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def speck_area(em_px, fraction=0.02):
    """Speck size in pixels for an em of `em_px` pixels: paths no larger than
    a square of `fraction` em are treated as specks (at least 2 pixels)."""
    side = fraction * em_px
    return max(2, int(side * side))


def trace_glyph(gray, width, height, scale, x0, y_top, stride=None, em_px=None,
                upm=None, turdsize=None, add_extremes=True, round_coords=True,
                report=None, **options):
    """trace -> to_font -> extremes -> rounding, in one call.

    scale: font units per pixel; (x0, y_top): font coordinates of the image's
    top-left corner. em_px: the em size in pixels (or give `upm`, the font's
    units per em, and it is upm / scale); when known and `turdsize` is None,
    paths smaller than `speck_area(em_px)` are dropped as specks, otherwise
    those of 2 pixels or fewer. Other keyword options go to `trace`. Returns
    a list of node lists in font units."""
    if em_px is None and upm:
        em_px = upm / float(scale)
    if turdsize is None:
        turdsize = speck_area(em_px) if em_px else 2
    contours = trace(gray, width, height, turdsize=turdsize, stride=stride,
                     report=report, **options)
    nodes = to_font(contours, scale, x0, y_top)
    if add_extremes:
        nodes = [extremes(c, 0.5, round_coords) for c in nodes]
    elif round_coords:
        nodes = [round_nodes(c) for c in nodes]
    return [c for c in nodes if c]
