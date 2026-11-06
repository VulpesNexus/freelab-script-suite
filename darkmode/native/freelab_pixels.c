/* FreeLab dark mode: map image lightness in place, keeping hue, saturation, and alpha.
 *
 * Same mapping as map_rgb() in freelab_dark_mode.py: in HLS terms (Python's
 * colorsys), L becomes dark_l + (1 - L) * (light_l - dark_l). FontLab's Python
 * calls it through ctypes on the pixels of a QImage in Format_ARGB32 (bytes
 * B, G, R, A on little-endian Windows), so whole widget images map in
 * milliseconds instead of seconds.
 *
 * Build: tools/build-native.ps1 (clang or MSVC, 64-bit, without the C runtime: the DLL imports nothing).
 */

#include <stdint.h>

#define FREELAB_PIXELS_VERSION 3

/* Built without the C runtime (no entry point, no imports); the compiler still expects this symbol when doubles are used. */
int _fltused = 0;

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

static double hue_channel(double m1, double m2, double hue)
{
    hue = hue - (double)(int64_t)hue; /* hue % 1.0 for hue >= 0 */
    if (hue < 0.0)
        hue += 1.0;
    if (hue < 1.0 / 6.0)
        return m1 + (m2 - m1) * hue * 6.0;
    if (hue < 0.5)
        return m2;
    if (hue < 2.0 / 3.0)
        return m1 + (m2 - m1) * (2.0 / 3.0 - hue) * 6.0;
    return m1;
}

static uint8_t to_byte(double c)
{
    double v = c * 255.0 + 0.5; /* Python's round() differs only on exact halves: at most 1 apart */
    if (v < 0.0)
        return 0;
    if (v > 255.0)
        return 255;
    return (uint8_t)v;
}

static double lightness(uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t maxc = r > g ? (r > b ? r : b) : (g > b ? g : b);
    uint8_t minc = r < g ? (r < b ? r : b) : (g < b ? g : b);
    return (maxc + minc) / 510.0;
}

static void map_rgb(uint8_t *r8, uint8_t *g8, uint8_t *b8, double dark_l, double light_l)
{
    double r = *r8 / 255.0, g = *g8 / 255.0, b = *b8 / 255.0;
    double maxc = r > g ? (r > b ? r : b) : (g > b ? g : b);
    double minc = r < g ? (r < b ? r : b) : (g < b ? g : b);
    double l = (minc + maxc) / 2.0;
    double h = 0.0, s = 0.0, m1, m2;
    if (maxc != minc) {
        double span = maxc - minc;
        double rc = (maxc - r) / span, gc = (maxc - g) / span, bc = (maxc - b) / span;
        s = l <= 0.5 ? span / (maxc + minc) : span / (2.0 - maxc - minc);
        if (r == maxc)
            h = bc - gc;
        else if (g == maxc)
            h = 2.0 + rc - bc;
        else
            h = 4.0 + gc - rc;
        h = h / 6.0;
        h = h - (double)(int64_t)h;
        if (h < 0.0)
            h += 1.0;
    }
    l = dark_l + (1.0 - l) * (light_l - dark_l);
    if (s == 0.0) {
        *r8 = *g8 = *b8 = to_byte(l);
        return;
    }
    m2 = l <= 0.5 ? l * (1.0 + s) : l + s - l * s;
    m1 = 2.0 * l - m2;
    *r8 = to_byte(hue_channel(m1, m2, h + 1.0 / 3.0));
    *g8 = to_byte(hue_channel(m1, m2, h));
    *b8 = to_byte(hue_channel(m1, m2, h - 1.0 / 3.0 + 1.0));
}

EXPORT int freelab_pixels_version(void)
{
    return FREELAB_PIXELS_VERSION;
}

/* pixels: count 32-bit pixels as bytes B, G, R, A. Only pixels whose lightness
 * is at least min_l are mapped (0 maps all). Runs of one color are mapped once. */
EXPORT void freelab_map_lightness(uint8_t *pixels, int64_t count, double dark_l, double light_l, double min_l)
{
    uint32_t last_in = 0, last_out = 0;
    int have_last = 0;
    uint32_t *p = (uint32_t *)pixels;
    int64_t i;
    for (i = 0; i < count; i++) {
        uint32_t v = p[i];
        uint8_t *bytes;
        if (have_last && v == last_in) {
            p[i] = last_out;
            continue;
        }
        last_in = v;
        bytes = (uint8_t *)&p[i];
        if (min_l <= 0.0 || lightness(bytes[2], bytes[1], bytes[0]) >= min_l)
            map_rgb(&bytes[2], &bytes[1], &bytes[0], dark_l, light_l);
        last_out = p[i];
        have_last = 1;
    }
}

/* counts[0]: pixels with alpha >= min_alpha; counts[1]: of those, lightness >= white_l;
 * counts[2]: of those, lightness <= black_l. */
EXPORT void freelab_pixel_stats(const uint8_t *pixels, int64_t count, int min_alpha, double white_l, double black_l,
                                int64_t *counts)
{
    int64_t i;
    counts[0] = counts[1] = counts[2] = 0;
    for (i = 0; i < count; i++) {
        const uint8_t *px = pixels + 4 * i;
        double l;
        if (px[3] < min_alpha)
            continue;
        counts[0]++;
        l = lightness(px[2], px[1], px[0]);
        if (l >= white_l)
            counts[1]++;
        else if (l <= black_l)
            counts[2]++;
    }
}

/* Distinct colors (0xRRGGBB) of pixels with alpha >= min_alpha and lightness >= min_l,
 * at most max_keys of them; returns how many were found (it stops counting at max_keys). */
EXPORT int64_t freelab_light_colors(const uint8_t *pixels, int64_t count, double min_l, int min_alpha,
                                    uint32_t *keys, int64_t max_keys)
{
    int64_t found = 0, i, k;
    for (i = 0; i < count && found < max_keys; i++) {
        const uint8_t *px = pixels + 4 * i;
        uint32_t rgb;
        if (px[3] < min_alpha || lightness(px[2], px[1], px[0]) < min_l)
            continue;
        rgb = ((uint32_t)px[2] << 16) | ((uint32_t)px[1] << 8) | px[0];
        for (k = 0; k < found && keys[k] != rgb; k++)
            ;
        if (k == found)
            keys[found++] = rgb;
    }
    return found;
}

/* Map only pixels whose color (0xRRGGBB, alpha ignored) is one of keys. */
EXPORT void freelab_map_keyed(uint8_t *pixels, int64_t count, const uint32_t *keys, int64_t nkeys,
                              double dark_l, double light_l)
{
    int64_t i, k;
    for (i = 0; i < count; i++) {
        uint8_t *px = pixels + 4 * i;
        uint32_t rgb = ((uint32_t)px[2] << 16) | ((uint32_t)px[1] << 8) | px[0];
        for (k = 0; k < nkeys; k++) {
            if (keys[k] == rgb) {
                map_rgb(&px[2], &px[1], &px[0], dark_l, light_l);
                break;
            }
        }
    }
}
