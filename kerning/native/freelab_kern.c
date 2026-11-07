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
 * Images are 8-bit coverage (0 to 255), rows `stride` bytes apart. Envelopes are written packed
 * (`width` bytes a row) and share one height, so a pair lines up row for row on the baseline.
 */
#include <stdint.h>

#define FREELAB_KERN_VERSION 1

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
