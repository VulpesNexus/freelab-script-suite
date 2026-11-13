/* FreeLab auto kerning: the measuring core, for FontLab 7's Python (64-bit Windows).
 *
 * The method is halfkern's (https://github.com/behdad/halfkern, Copyright 2022 Google LLC,
 * Apache License 2.0): each glyph's coverage gets an envelope, a halo that fades out over `bias`
 * pixels around the ink, at half strength, under the ink itself; a pair is moved until the
 * overlap of its two envelopes (the sum of the squared products) falls within a band calibrated
 * on the font's own ll, nn, and oo. This file is a new implementation of that method, not a copy
 * of halfkern's code: an exact Euclidean distance transform stands in for its fast-marching
 * distance, and the arithmetic follows its cairo compositing.
 *
 * No C runtime and no imports: every buffer comes from the caller.
 *
 * A second method measures contours instead: the average inverse cube of the distances between the
 * facing edges of the two glyphs, row by row, after Matthew Skala's description of Tsukurimashou's
 * kerning (freetype-devel, June 2012); written from that description, not from its code.
 *
 * Images are 8-bit coverage (0 to 255), rows `stride` bytes apart. Envelopes are written packed
 * (`width` bytes a row) and share one height, so a pair lines up row for row on the baseline.
 */
#include <stdint.h>

#define FREELAB_KERN_VERSION 2

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

#define INF_DIST 1e20

/* Built without the C runtime (no entry point, no imports); the compiler still expects this symbol when doubles are used. */
int _fltused = 0;

EXPORT int freelab_kern_version(void)
{
    return FREELAB_KERN_VERSION;
}

/* Bytes of scratch memory freelab_kern_envelope needs for an image of w by h. */
EXPORT int64_t freelab_kern_scratch_size(int w, int h)
{
    int64_t n = (int64_t)w * h, line = (w > h ? w : h) + 1;
    return n * 8 /* squared distances */ + line * 8 * 4 /* f, d, z */ + line * 4 /* v */ + 64;
}

static double sqrt_pos(double x)
{
    double r = x > 1.0 ? x : 1.0;
    int i;
    if (x <= 0.0)
        return 0.0;
    for (i = 0; i < 40; i++) { /* Newton: converges quickly from above */
        double next = 0.5 * (r + x / r);
        if (next >= r)
            break;
        r = next;
    }
    return r;
}

/* One line of the squared Euclidean distance transform (Felzenszwalb and Huttenlocher, "Distance
 * Transforms of Sampled Functions", 2012): d[q] = min over p of (q - p)^2 + f[p]. */
static double parabola_cut(const double *f, int q, int p)
{
    return ((f[q] + (double)q * q) - (f[p] + (double)p * p)) / (double)(2 * q - 2 * p);
}

static void edt_line(const double *f, int n, double *d, int *v, double *z)
{
    int k = 0, q;
    v[0] = 0;
    z[0] = -INF_DIST;
    z[1] = INF_DIST;
    for (q = 1; q < n; q++) {
        double s = parabola_cut(f, q, v[k]);
        while (s <= z[k]) {
            k--;
            s = parabola_cut(f, q, v[k]);
        }
        k++;
        v[k] = q;
        z[k] = s;
        z[k + 1] = INF_DIST;
    }
    k = 0;
    for (q = 0; q < n; q++) {
        while (z[k + 1] < (double)q)
            k++;
        d[q] = ((double)q - v[k]) * ((double)q - v[k]) + f[v[k]];
    }
}

/* The envelope of a coverage image: the halo (255 at full ink, falling by 255 / bias a pixel of
 * distance from it, truncated as an 8-bit value), halved, under the coverage itself (cairo's
 * OVER on 8-bit alpha). Distances are measured from fully covered pixels, as halfkern measures
 * them. Returns 0 when no pixel is fully covered (nothing to measure from). */
EXPORT int freelab_kern_envelope(const uint8_t *cov, int w, int h, int stride, int bias, uint8_t *out, uint8_t *scratch)
{
    double *dist = (double *)(((uintptr_t)scratch + 15) & ~(uintptr_t)15);
    int line = (w > h ? w : h) + 1, x, y, any = 0;
    double *f = dist + (int64_t)w * h, *d = f + line, *z = d + line;
    int *v = (int *)(z + line + 1);
    double scale;
    if (w <= 0 || h <= 0 || bias <= 0)
        return 0;
    scale = 255.0 / bias;
    for (y = 0; y < h; y++)
        for (x = 0; x < w; x++) {
            int full = cov[(int64_t)y * stride + x] == 255;
            dist[(int64_t)y * w + x] = full ? 0.0 : INF_DIST;
            any |= full;
        }
    if (!any)
        return 0;
    for (x = 0; x < w; x++) { /* columns */
        for (y = 0; y < h; y++)
            f[y] = dist[(int64_t)y * w + x];
        edt_line(f, h, d, v, z);
        for (y = 0; y < h; y++)
            dist[(int64_t)y * w + x] = d[y];
    }
    for (y = 0; y < h; y++) { /* rows */
        double *row = dist + (int64_t)y * w;
        for (x = 0; x < w; x++)
            f[x] = row[x];
        edt_line(f, w, d, v, z);
        for (x = 0; x < w; x++)
            row[x] = d[x];
    }
    for (y = 0; y < h; y++) {
        for (x = 0; x < w; x++) {
            double r = dist[(int64_t)y * w + x], halo = 0.0;
            int c = cov[(int64_t)y * stride + x], a, halved;
            if (r < (double)bias * bias)
                halo = 255.0 - scale * sqrt_pos(r);
            a = halo > 0.0 ? (int)halo : 0; /* numpy's truncation to uint8 */
            halved = (a * 127 + 127) / 255; /* DEST_OUT at half alpha: a * (1 - 128/255) */
            out[(int64_t)y * w + x] = (uint8_t)(c + (halved * (255 - c) + 127) / 255); /* coverage OVER the halo */
        }
    }
    return 1;
}

/* The overlap of two envelopes of height h: the right one at x 0, the left one at l_offset
 * (in the right one's pixels), and the sum of the squared products (cairo's IN) where both are.
 * reduce_max: the largest squared product instead of the sum. */
EXPORT double freelab_kern_overlap(const uint8_t *l, int lw, const uint8_t *r, int rw, int h, int l_offset, int reduce_max)
{
    int x0 = l_offset > 0 ? l_offset : 0, x1 = lw + l_offset < rw ? lw + l_offset : rw, x, y;
    double total = 0.0;
    if (x1 <= x0)
        return 0.0;
    for (y = 0; y < h; y++) {
        const uint8_t *lr = l + (int64_t)y * lw - l_offset, *rr = r + (int64_t)y * rw;
        for (x = x0; x < x1; x++) {
            int p = lr[x] * rr[x];
            double m;
            if (!p)
                continue;
            p = (p + 127) / 255;
            m = (double)p * p;
            if (reduce_max) {
                if (m > total)
                    total = m;
            } else {
                total += m;
            }
        }
    }
    return total;
}

/* Kern a pair as halfkern does: from no kerning, step a pixel at a time, closer while the overlap
 * is below min_s, or apart while it is above max_s, up to 2 * bias pixels either way. base_offset
 * is the left envelope's position with no kerning. Writes the kerning in pixels (negative is
 * closer, not yet halved) and the overlap there; returns 1, or 0 when no step reached the band. */
EXPORT int freelab_kern_pair(const uint8_t *l, int lw, const uint8_t *r, int rw, int h, int base_offset, int bias,
                             double min_s, double max_s, int reduce_max, int *kern_out, double *s_out)
{
    int kern = 0;
    double s = freelab_kern_overlap(l, lw, r, rw, h, base_offset, reduce_max);
    if (s < min_s) {
        for (kern = -1; kern >= -2 * bias; kern--) {
            s = freelab_kern_overlap(l, lw, r, rw, h, base_offset - kern, reduce_max);
            if (s >= min_s)
                break;
        }
        if (kern < -2 * bias)
            return 0;
    } else if (s > max_s) {
        for (kern = 1; kern <= 2 * bias; kern++) {
            s = freelab_kern_overlap(l, lw, r, rw, h, base_offset - kern, reduce_max);
            if (s <= max_s)
                break;
        }
        if (kern > 2 * bias)
            return 0;
    }
    *kern_out = kern;
    *s_out = s;
    return 1;
}


/* ---- contour distance ---------------------------------------------------------------------- */

#define NO_INK 1e9 /* a left profile with no ink in the row; the right profile holds -NO_INK */

/* Each row's left and right ink edges, where the coverage crosses half, between pixel centres
 * (x + 0.5): left[y] and right[y], or NO_INK and -NO_INK in a row without ink. Returns the
 * number of rows with ink. */
EXPORT int freelab_kern_profiles(const uint8_t *cov, int w, int h, int stride, double *left, double *right)
{
    int x, y, rows = 0;
    for (y = 0; y < h; y++) {
        const uint8_t *row = cov + (int64_t)y * stride;
        left[y] = NO_INK;
        right[y] = -NO_INK;
        for (x = 0; x < w; x++) {
            if (row[x] >= 128) {
                double before = x > 0 ? row[x - 1] : 0;
                left[y] = (x - 0.5) + (128.0 - before) / ((double)row[x] - before);
                break;
            }
        }
        if (x == w)
            continue;
        rows++;
        for (x = w - 1; x >= 0; x--) {
            if (row[x] >= 128) {
                double after = x < w - 1 ? row[x + 1] : 0;
                right[y] = (x + 0.5) + ((double)row[x] - 128.0) / ((double)row[x] - after);
                break;
            }
        }
    }
    return rows;
}

/* The contour with its angle limited: it moves at most `slope` pixels across for each row up or
 * down, so a shape reaches out at that angle into the rows above and below it (a period's edge
 * rises toward an apostrophe above the pair, which then cannot slide over it). */
EXPORT void freelab_kern_extend(double *profile, int h, double slope, int is_right)
{
    int y;
    for (y = 1; y < h; y++) {
        double reach = is_right ? profile[y - 1] - slope : profile[y - 1] + slope;
        if (is_right ? reach > profile[y] : reach < profile[y])
            profile[y] = reach;
    }
    for (y = h - 2; y >= 0; y--) {
        double reach = is_right ? profile[y + 1] - slope : profile[y + 1] + slope;
        if (is_right ? reach > profile[y] : reach < profile[y])
            profile[y] = reach;
    }
}

/* The pair's measure with the left image at `offset` in the right one's pixels: the mean over the
 * rows of 1 / gap^3, each gap at least `floor` pixels. Rows where either contour is missing count
 * for nothing. */
EXPORT double freelab_kern_contour_measure(const double *right_of_left, const double *left_of_right, int h,
                                           double offset, double floor)
{
    double total = 0.0;
    int y;
    for (y = 0; y < h; y++) {
        double gap;
        if (right_of_left[y] <= -NO_INK / 2 || left_of_right[y] >= NO_INK / 2)
            continue;
        gap = left_of_right[y] - (right_of_left[y] + offset);
        if (gap < floor)
            gap = floor;
        total += 1.0 / (gap * gap * gap);
    }
    return total / (h > 0 ? h : 1);
}

/* The narrowest gap between the raw contours (no angle limit), with the left image at `offset`. */
EXPORT double freelab_kern_closest(const double *right_of_left, const double *left_of_right, int h, double offset)
{
    double closest = NO_INK;
    int y;
    for (y = 0; y < h; y++) {
        double gap;
        if (right_of_left[y] <= -NO_INK / 2 || left_of_right[y] >= NO_INK / 2)
            continue;
        gap = left_of_right[y] - (right_of_left[y] + offset);
        if (gap < closest)
            closest = gap;
    }
    return closest;
}

/* The kerning (pixels, negative closer) that brings the measure into [low, high], found by
 * bisection within `range` pixels either way: 0 when it is already there. Returns 0 when the band
 * cannot be reached within range. */
EXPORT int freelab_kern_contour_pair(const double *right_of_left, const double *left_of_right, int h, double base_offset,
                                     double range, double floor, double low, double high, double *kern_out)
{
    double m = freelab_kern_contour_measure(right_of_left, left_of_right, h, base_offset, floor), target, a, b;
    int i, closer;
    if (m >= low && m <= high) {
        *kern_out = 0.0;
        return 1;
    }
    closer = m < low; /* too little interaction: the pair is too loose */
    target = closer ? low : high;
    a = 0.0;
    b = closer ? -range : range;
    if (closer ? freelab_kern_contour_measure(right_of_left, left_of_right, h, base_offset - b, floor) < target
               : freelab_kern_contour_measure(right_of_left, left_of_right, h, base_offset - b, floor) > target)
        return 0;
    for (i = 0; i < 60; i++) { /* the measure grows as the pair closes in */
        double mid = 0.5 * (a + b), mm = freelab_kern_contour_measure(right_of_left, left_of_right, h, base_offset - mid, floor);
        if (closer ? mm < target : mm > target)
            a = mid;
        else
            b = mid;
    }
    *kern_out = 0.5 * (a + b);
    return 1;
}
