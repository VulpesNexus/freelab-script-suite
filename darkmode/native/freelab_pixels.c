/* FreeLab dark mode: map image lightness in place, keeping hue, saturation, and alpha.
 *
 * Same mapping as map_rgb() in freelab_dark_mode.py (OKLab lightness inverted
 * between two values, hue kept, light colors' chroma muted). FontLab's Python
 * calls it through ctypes on the pixels of a QImage in Format_ARGB32 (bytes
 * B, G, R, A on little-endian Windows), so whole widget images map in
 * milliseconds instead of seconds.
 *
 * Build: tools/build-native.ps1 (clang or MSVC, 64-bit, without the C runtime: the DLL imports nothing).
 */

#include <stddef.h>
#include <stdint.h>

#define FREELAB_PIXELS_VERSION 50

/* Built without the C runtime (no entry point, no imports); the compiler still expects this symbol when doubles are used. */
int _fltused = 0;

/* ...and calls memcpy for struct copies. A byte loop: -fno-builtin keeps it from becoming a call to itself. */
#if defined(_MSC_VER) && !defined(__clang__)
#pragma function(memcpy)
#endif
void *memcpy(void *dst, const void *src, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (n--)
        *d++ = *s++;
    return dst;
}

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

/* sRGB byte -> linear light (generated: c / 12.92, or ((c + 0.055) / 1.055) ^ 2.4). */
static const double SRGB_TO_LINEAR[256] = {
    0.000000000000, 0.000303526984, 0.000607053967, 0.000910580951,
    0.001214107934, 0.001517634918, 0.001821161901, 0.002124688885,
    0.002428215868, 0.002731742852, 0.003035269835, 0.003346535764,
    0.003676507324, 0.004024717018, 0.004391442037, 0.004776953481,
    0.005181516702, 0.005605391624, 0.006048833023, 0.006512090793,
    0.006995410187, 0.007499032043, 0.008023192985, 0.008568125618,
    0.009134058702, 0.009721217320, 0.010329823030, 0.010960094006,
    0.011612245180, 0.012286488357, 0.012983032342, 0.013702083047,
    0.014443843596, 0.015208514423, 0.015996293366, 0.016807375753,
    0.017641954488, 0.018500220128, 0.019382360957, 0.020288563057,
    0.021219010376, 0.022173884793, 0.023153366178, 0.024157632449,
    0.025186859627, 0.026241221895, 0.027320891639, 0.028426039504,
    0.029556834438, 0.030713443733, 0.031896033073, 0.033104766571,
    0.034339806809, 0.035601314875, 0.036889450401, 0.038204371595,
    0.039546235277, 0.040915196907, 0.042311410621, 0.043735029257,
    0.045186204386, 0.046665086337, 0.048171824227, 0.049706565984,
    0.051269458374, 0.052860647023, 0.054480276442, 0.056128490050,
    0.057805430191, 0.059511238163, 0.061246054232, 0.063010017653,
    0.064803266693, 0.066625938644, 0.068478169844, 0.070360095697,
    0.072271850682, 0.074213568380, 0.076185381481, 0.078187421805,
    0.080219820314, 0.082282707130, 0.084376211544, 0.086500462037,
    0.088655586286, 0.090841711183, 0.093058962847, 0.095307466631,
    0.097587347142, 0.099898728247, 0.102241733088, 0.104616484091,
    0.107023102978, 0.109461710778, 0.111932427837, 0.114435373827,
    0.116970667759, 0.119538427988, 0.122138772230, 0.124771817561,
    0.127437680436, 0.130136476690, 0.132868321554, 0.135633329655,
    0.138431615032, 0.141263291140, 0.144128470858, 0.147027266498,
    0.149959789811, 0.152926151996, 0.155926463708, 0.158960835061,
    0.162029375639, 0.165132194502, 0.168269400190, 0.171441100733,
    0.174647403656, 0.177888415984, 0.181164244250, 0.184474994500,
    0.187820772301, 0.191201682741, 0.194617830442, 0.198069319560,
    0.201556253794, 0.205078736390, 0.208636870145, 0.212230757414,
    0.215860500114, 0.219526199729, 0.223227957317, 0.226965873510,
    0.230740048524, 0.234550582161, 0.238397573812, 0.242281122466,
    0.246201326708, 0.250158284730, 0.254152094331, 0.258182852922,
    0.262250657530, 0.266355604803, 0.270497791013, 0.274677312060,
    0.278894263477, 0.283148740430, 0.287440837727, 0.291770649818,
    0.296138270798, 0.300543794416, 0.304987314070, 0.309468922818,
    0.313988713376, 0.318546778125, 0.323143209113, 0.327778098057,
    0.332451536346, 0.337163615048, 0.341914424909, 0.346704056355,
    0.351532599500, 0.356400144146, 0.361306779784, 0.366252595599,
    0.371237680474, 0.376262122991, 0.381326011433, 0.386429433787,
    0.391572477750, 0.396755230726, 0.401977779832, 0.407240211902,
    0.412542613484, 0.417885070848, 0.423267669986, 0.428690496614,
    0.434153636175, 0.439657173841, 0.445201194516, 0.450785782838,
    0.456411023180, 0.462076999654, 0.467783796112, 0.473531496148,
    0.479320183101, 0.485149940056, 0.491020849848, 0.496932995061,
    0.502886458033, 0.508881320855, 0.514917665377, 0.520995573204,
    0.527115125706, 0.533276404011, 0.539479489012, 0.545724461370,
    0.552011401512, 0.558340389634, 0.564711505705, 0.571124829465,
    0.577580440430, 0.584078417891, 0.590618840919, 0.597201788364,
    0.603827338855, 0.610495570808, 0.617206562420, 0.623960391675,
    0.630757136346, 0.637596873994, 0.644479681971, 0.651405637420,
    0.658374817279, 0.665387298282, 0.672443156958, 0.679542469633,
    0.686685312435, 0.693871761292, 0.701101891933, 0.708375779892,
    0.715693500506, 0.723055128922, 0.730460740090, 0.737910408773,
    0.745404209540, 0.752942216776, 0.760524504675, 0.768151147248,
    0.775822218317, 0.783537791526, 0.791297940333, 0.799102738014,
    0.806952257669, 0.814846572216, 0.822785754396, 0.830769876775,
    0.838799011741, 0.846873231510, 0.854992608124, 0.863157213454,
    0.871367119199, 0.879622396888, 0.887923117882, 0.896269353374,
    0.904661174391, 0.913098651793, 0.921581856277, 0.930110858375,
    0.938685728458, 0.947306536733, 0.955973353249, 0.964686247894,
    0.973445290398, 0.982250550333, 0.991102097114, 1.000000000000,
};

static double cbrt_pos(double x)
{
    double y = 1.0 + (x - 1.0) / 3.0; /* tangent at 1; Newton converges from above */
    int i;
    if (x <= 0.0)
        return 0.0;
    if (y <= 0.0)
        y = 0.5;
    for (i = 0; i < 40; i++)
        y -= (y * y * y - x) / (3.0 * y * y);
    return y;
}

/* Nearest sRGB byte to a linear value, nearest measured in linear light. */
static uint8_t linear_to_byte(double v)
{
    int lo = 0, hi = 255;
    if (v <= 0.0)
        return 0;
    if (v >= 1.0)
        return 255;
    while (lo < hi) { /* first entry >= v */
        int mid = (lo + hi) / 2;
        if (SRGB_TO_LINEAR[mid] < v)
            lo = mid + 1;
        else
            hi = mid;
    }
    if (lo > 0 && v - SRGB_TO_LINEAR[lo - 1] <= SRGB_TO_LINEAR[lo] - v)
        return (uint8_t)(lo - 1);
    return (uint8_t)lo;
}

/* OKLab (Bjorn Ottosson, 2020): lightness that follows the eye, and hues that stay put. */
static void linear_to_oklab(double r, double g, double b, double *l, double *a, double *bb)
{
    double lc = cbrt_pos(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    double mc = cbrt_pos(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    double sc = cbrt_pos(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    *l = 0.2104542553 * lc + 0.7936177850 * mc - 0.0040720468 * sc;
    *a = 1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc;
    *bb = 0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc;
}

static int oklab_to_linear(double l, double a, double b, double *r, double *g, double *bl)
{
    double lc = l + 0.3963377774 * a + 0.2158037573 * b;
    double mc = l - 0.1055613458 * a - 0.0638541728 * b;
    double sc = l - 0.0894841775 * a - 1.2914855480 * b;
    double lv = lc * lc * lc, mv = mc * mc * mc, sv = sc * sc * sc;
    *r = 4.0767416621 * lv - 3.3077115913 * mv + 0.2309699292 * sv;
    *g = -1.2684380046 * lv + 2.6097574011 * mv - 0.3413193965 * sv;
    *bl = -0.0041960863 * lv - 0.7034186147 * mv + 1.7076147010 * sv;
    return *r >= -1e-9 && *r <= 1.0 + 1e-9 && *g >= -1e-9 && *g <= 1.0 + 1e-9 && *bl >= -1e-9 && *bl <= 1.0 + 1e-9;
}

/* Chroma kept for a color of OKLab lightness l: all of it up to CHROMA_FULL_BELOW, then
 * less and less, down to CHROMA_MIN_FACTOR at white: tinted whites and pastels turn gray. */
#define CHROMA_FULL_BELOW 0.65
#define CHROMA_MIN_FACTOR 0.25
/* Colors whose channels spread this little (max - min, 0-255) are mapped linearly: their mean
 * is inverted between the two grays, and keep_tint (0 to 1) of each channel's distance from
 * the mean is kept. Text smoothing lives in these colors (blends of text and background, and
 * ClearType's colored edges), and only a linear mapping keeps a blend a blend: the perceptual
 * one below moved edge pixels to the wrong brightness. The interface passes keep_tint 0 (gray);
 * content passes 1, keeping the hue of muted anchors, nodes, and marks. */
#define LINEAR_SPREAD 110
#define MAX_LINEAR_CHANNEL 235.0

/* The sRGB gray whose OKLab lightness is l (for a gray, L is the cube root of linear light). */
static double gray_byte(double l)
{
    return (double)linear_to_byte(l * l * l);
}
/* No mapped color may reach the selective threshold (HLS lightness 0.9): one that would is darkened. */
#define MAX_HLS_LIGHTNESS 0.89

static double chroma_factor(double l)
{
    if (l <= CHROMA_FULL_BELOW)
        return 1.0;
    if (l >= 1.0)
        return CHROMA_MIN_FACTOR;
    return 1.0 - (1.0 - CHROMA_MIN_FACTOR) * (l - CHROMA_FULL_BELOW) / (1.0 - CHROMA_FULL_BELOW);
}

static void oklab_to_bytes(double l, double a, double b, uint8_t *r8, uint8_t *g8, uint8_t *b8)
{
    double ro, go, bo;
    if (!oklab_to_linear(l, a, b, &ro, &go, &bo)) {
        double lo = 0.0, hi = 1.0;
        int i;
        for (i = 0; i < 12; i++) { /* the most chroma sRGB can show at this lightness */
            double mid = (lo + hi) / 2.0;
            if (oklab_to_linear(l, a * mid, b * mid, &ro, &go, &bo))
                lo = mid;
            else
                hi = mid;
        }
        oklab_to_linear(l, a * lo, b * lo, &ro, &go, &bo);
    }
    *r8 = linear_to_byte(ro);
    *g8 = linear_to_byte(go);
    *b8 = linear_to_byte(bo);
}
static double lightness(uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t maxc = r > g ? (r > b ? r : b) : (g > b ? g : b);
    uint8_t minc = r < g ? (r < b ? r : b) : (g < b ? g : b);
    return (maxc + minc) / 510.0;
}

/* The mapping of freelab_dark_mode.map_rgb: in OKLab, L becomes dark + (1 - L) * (light - dark),
 * hue kept, chroma scaled by chroma_factor and reduced further only as sRGB requires; a result
 * at MAX_HLS_LIGHTNESS or above is darkened until it is below. */
static void map_rgb(uint8_t *r8, uint8_t *g8, uint8_t *b8, double dark_l, double light_l, double keep_tint)
{
    double l, a, b, l2, k;
    int i;
    uint8_t maxc = *r8 > *g8 ? (*r8 > *b8 ? *r8 : *b8) : (*g8 > *b8 ? *g8 : *b8);
    uint8_t minc = *r8 < *g8 ? (*r8 < *b8 ? *r8 : *b8) : (*g8 < *b8 ? *g8 : *b8);
    if (maxc - minc <= LINEAR_SPREAD) {
        double dark = gray_byte(dark_l), light = gray_byte(light_l);
        double mean = (*r8 + *g8 + *b8) / 3.0;
        double base = light - mean * (light - dark) / 255.0;
        uint8_t *channels[3];
        int c;
        channels[0] = r8;
        channels[1] = g8;
        channels[2] = b8;
        for (c = 0; c < 3; c++) {
            double v = base + (*channels[c] - mean) * keep_tint;
            if (v < 0.0)
                v = 0.0;
            if (v > MAX_LINEAR_CHANNEL)
                v = MAX_LINEAR_CHANNEL;
            *channels[c] = (uint8_t)(v + 0.5);
        }
        return;
    }
    linear_to_oklab(SRGB_TO_LINEAR[*r8], SRGB_TO_LINEAR[*g8], SRGB_TO_LINEAR[*b8], &l, &a, &b);
    k = chroma_factor(l);
    l2 = dark_l + (1.0 - l) * (light_l - dark_l);
    for (i = 0; i < 20; i++) {
        oklab_to_bytes(l2, a * k, b * k, r8, g8, b8);
        if (lightness(*r8, *g8, *b8) < MAX_HLS_LIGHTNESS)
            break;
        l2 -= 0.01;
    }
}
EXPORT int freelab_pixels_version(void)
{
    return FREELAB_PIXELS_VERSION;
}

/* pixels: count 32-bit pixels as bytes B, G, R, A, in rows of width. With min_l at 0 or below
 * every pixel is mapped. Otherwise only pixels whose lightness is at least min_l are; and when
 * ink_below is above 0, a grayish pixel darker than that (black text on an editor's dark paper,
 * and its smoothed edges) moves toward LIGHT_TEXT by its coverage, 1 - lightness / ink_below,
 * which keeps the text's smoothing. With edge_neutral above 0, a low-color pixel whose
 * lightness differs from a horizontal neighbor's by that much (text and outline edges, where
 * ClearType puts its colored fringes) keeps no tint, while flat areas (marks) keep keep_tint. */
#define LIGHT_TEXT 219.0
#define INK_SPREAD 40

static uint8_t spread_of(const uint8_t *px)
{
    uint8_t maxc = px[2] > px[1] ? (px[2] > px[0] ? px[2] : px[0]) : (px[1] > px[0] ? px[1] : px[0]);
    uint8_t minc = px[2] < px[1] ? (px[2] < px[0] ? px[2] : px[0]) : (px[1] < px[0] ? px[1] : px[0]);
    return (uint8_t)(maxc - minc);
}

EXPORT void freelab_map_lightness(uint8_t *pixels, int64_t count, int64_t width, double dark_l, double light_l,
                                  double min_l, double ink_below, double keep_tint, double edge_neutral)
{
    uint32_t last_in = 0, last_out = 0, left = 0;
    int have_last = 0;
    uint32_t *p = (uint32_t *)pixels;
    int64_t i;
    for (i = 0; i < count; i++) {
        uint32_t v = p[i];
        uint8_t *bytes = (uint8_t *)&p[i];
        int64_t x = width > 0 ? i % width : 1;
        double tint = keep_tint;
        if (edge_neutral > 0.0 && spread_of(bytes) <= LINEAR_SPREAD) {
            double l = lightness(bytes[2], bytes[1], bytes[0]);
            const uint8_t *lb = (const uint8_t *)&left;
            const uint8_t *rb = (x + 1 < width && i + 1 < count) ? (const uint8_t *)&p[i + 1] : 0;
            if ((x > 0 && (l - lightness(lb[2], lb[1], lb[0]) >= edge_neutral || lightness(lb[2], lb[1], lb[0]) - l >= edge_neutral))
                || (rb && (l - lightness(rb[2], rb[1], rb[0]) >= edge_neutral || lightness(rb[2], rb[1], rb[0]) - l >= edge_neutral)))
                tint = 0.0;
        }
        left = v;  /* the original, before mapping */
        if (edge_neutral <= 0.0 && have_last && v == last_in) {
            p[i] = last_out;
            continue;
        }
        last_in = v;
        if (min_l <= 0.0) {
            map_rgb(&bytes[2], &bytes[1], &bytes[0], dark_l, light_l, tint);
        } else {
            double l = lightness(bytes[2], bytes[1], bytes[0]);
            if (l >= min_l) {
                map_rgb(&bytes[2], &bytes[1], &bytes[0], dark_l, light_l, tint);
            } else if (ink_below > 0.0 && l < ink_below && spread_of(bytes) <= INK_SPREAD) {
                double coverage = 1.0 - l / ink_below;
                int k;
                for (k = 0; k < 3; k++)
                    bytes[k] = (uint8_t)(bytes[k] + (LIGHT_TEXT - bytes[k]) * coverage + 0.5);
            }
        }
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
/* Map pixels whose color (0xRRGGBB, alpha ignored) is one of keys, and, when min_l is above 0,
 * pixels at least that light too (the dock's frame corners, which a render alone may not show). */
EXPORT void freelab_map_keyed(uint8_t *pixels, int64_t count, int64_t width, const uint32_t *keys, int64_t nkeys,
                              double dark_l, double light_l, double keep_tint, double min_l, uint32_t edge_target)
{
    int64_t i, k;
    for (i = 0; i < count; i++) {
        uint8_t *px = pixels + 4 * i;
        uint32_t rgb = ((uint32_t)px[2] << 16) | ((uint32_t)px[1] << 8) | px[0];
        int64_t row = width > 0 ? i / width : 1;
        for (k = 0; k < nkeys && keys[k] != rgb; k++)
            ;
        if (k < nkeys || (min_l > 0.0 && lightness(px[2], px[1], px[0]) >= min_l)) {
            map_rgb(&px[2], &px[1], &px[0], dark_l, light_l, keep_tint);
        } else if (edge_target && width > 0 && (row == 0 || row == count / width - 1)) {
            /* The frame's antialiased ends on the first and last rows blend with what lies beneath,
             * so their colors match no key: they take the mapped frame color. */
            double l = lightness(px[2], px[1], px[0]);
            if (l >= 0.3 && l < min_l) {
                px[2] = (uint8_t)(edge_target >> 16);
                px[1] = (uint8_t)(edge_target >> 8);
                px[0] = (uint8_t)edge_target;
            }
        }
    }
}

/* ---------------------------------------------------------------------------
 * Anchor blends: smoothing-correct mapping of what FontLab paints.
 *
 * A widget paints a few flat colors (its "anchors": backgrounds, text, frames) and
 * smooths their edges with blends of two of them. Mapping each pixel on its own moves
 * blends to the wrong brightness (text looked ragged or haloed). Here the anchors are
 * found first (the most frequent opaque colors), each is mapped or kept, and every other
 * pixel that is a blend of two anchors (within a tolerance that covers ClearType's
 * colored edges) becomes the same blend of their mapped colors: smoothing stays smooth,
 * and ClearType fringes turn neutral. A frequent color that is itself only a blend
 * (smoothing between a background and darker text) is not an anchor. Where several
 * pairs would explain a pixel (gray text, gray rows, and gray badges all lie on one
 * line), the anchors found around the pixel decide.
 *
 * mode ANCHORS_ALL (islands, light paper): every anchor is mapped (keep_tint as given).
 * mode ANCHORS_INK (the dark interface): only what is wrong on a dark interface is mapped:
 * white surfaces and lines; light, low-color surfaces (badges, light rows); and dark
 * "ink" (text-like shapes darker than the main background, or dark and colored), which
 * becomes light ink of the same hue. Light text, dark surfaces, and colored surfaces stay.
 * main_default: the OKLab lightness beneath, for a widget that paints no background of its own.
 * Returns how many pixels changed (with apply 0, nothing is written: detection).
 * --------------------------------------------------------------------------- */
#define ANCHORS_INK 0
#define ANCHORS_ALL 1
#define ANCHORS_RELIGHT 2 /* back to light: a dark main paper turns white, light gray text black, the rest stays */
#define ANCHORS_ICON 3 /* as ANCHORS_ALL, but colored parts of middle lightness (blue guides, green fills) stay */
#define ICON_KEEP_CHROMA 0.08
#define ICON_KEEP_MIN_OKL 0.4
#define ICON_KEEP_MAX_OKL 0.85
/* Dim gray marks (icons drawn in dark gray, near black against white in light mode) on the dark
 * interface: mapped, then lightened this much further toward the light gray. */
#define DIM_INK_ABOVE_MAIN 0.08
#define DIM_INK_MAX_OKL 0.58
#define DIM_INK_LIFT 0.35
#define RELIGHT_PAPER_OKL 0.35
#define RELIGHT_TEXT_OKL 0.75
#define RELIGHT_SPREAD 30
#define RELIGHT_BLEND_TOLERANCE 0.08 /* tight: syntax colors lie near the line from a dark paper to white */
#define HASH_SIZE 16384 /* a power of two */
#define MEMO_SIZE 8192 /* a power of two */
#define MAX_ANCHORS 32
#define MAX_CANDIDATES 48 /* frequent colors looked at; blends among them are dropped */
#define ANCHOR_MIN_ALPHA 200
#define WHITE_HLS 0.9
#define SURFACE_RUN 4.0 /* mean run, across and down, of a surface's pixels */
#define LINE_RUN 8.0 /* mean run, across or down, of a (white) line's pixels */
#define LONG_LINE_RUN 24.0 /* a dark color this long and thin is a separator, not text (stems are shorter) */
#define LIGHT_SURFACE_RUN 6.0 /* a light surface is solid one way at least (badges, rows), unlike most text strokes */
#define BACKGROUND_SHARE 0.2 /* a color covering this much is a background, never ink */
#define FRINGE_SHARE 0.4 /* a dark, colored pixel this often right beside light ones is ClearType smoothing of light text */
#define LIGHT_FRINGE_SHARE 0.15 /* a light fringe this often beside lighter text (badges): smoothing */
#define FRINGE_LIGHT 0.4 /* HLS lightness of "light" for that, */
#define FRINGE_LIGHTER 0.15 /* and at least this much lighter than the pixel */
#define LIGHT_SURFACE_OKL 0.6
#define ON_LIGHT_SHARE 0.5 /* a text color this often inside a light surface (touching it, not the background) */
#define LIGHT_SURFACE_SPREAD 60
#define INK_MAX_OKL 0.5
#define INK_BELOW_MAIN 0.1 /* ink is at least this much darker (OKLab L) than the main background */
#define INK_CHROMA 0.05 /* or this colored */
#define SURFACE_INK_MAX_OKL 0.18 /* a solid area is ink only when near black (large glyph strokes), never a dark panel or a selection */
#define BLEND_TOLERANCE 0.25 /* of the distance between the two anchors */
#define LOCAL_BLEND_TOLERANCE 0.6 /* when both anchors are right around the pixel (strong ClearType fringes on small text,
                                    white text on a light badge) */
#define BLEND_MIN_TOLERANCE 12.0
#define BLEND_ANCHOR_TOLERANCE 6.0 /* a candidate this close to a blend of two others is a blend */
#define NEAR_ANCHOR 40.0 /* translucent pixels: their color is an anchor's if this close */
#define NEIGHBORHOOD 2 /* anchors within this many pixels decide between pairs */
#define MAX_INDEXED (1 << 22) /* pixels: larger images resolve pairs without neighborhoods */
#define SAMPLE_ABOVE (1 << 20) /* pixels: larger images are counted on every other row */

static uint32_t h_key[HASH_SIZE], h_gen[HASH_SIZE];
static int64_t h_count[HASH_SIZE], h_hruns[HASH_SIZE], h_vruns[HASH_SIZE], h_beside_light[HASH_SIZE];
static int8_t h_anchor[HASH_SIZE];
static uint32_t m_key[MEMO_SIZE], m_mask[MEMO_SIZE], m_val[MEMO_SIZE], m_gen[MEMO_SIZE];
static int8_t a_index[MAX_INDEXED];
static uint32_t generation = 0;

typedef struct {
    double r, g, b;
    double mr, mg, mb; /* mapped (equal to r, g, b when kept) */
    double hrun, vrun, okl, chroma, oa, ob;
    int64_t count, slot, beside_light, on_light;
    uint64_t touches; /* candidates right beside its pixels (all when not surveyed) */
    double light_okl; /* the lightest light surface it lies inside (on_light) */
    double ir, ig, ib; /* mapped as an island would (ink mode, inside a light surface) */
    int surface, line, long_line, mapped;
} Anchor;

static Anchor anchors[MAX_CANDIDATES];
static int anchor_count;
static uint32_t light_bits; /* ink mode: anchors that are light surfaces turned dark */
static uint32_t main_bit; /* ink mode: the kept main background (anchor 0), when there is one */
static Anchor candidates[MAX_CANDIDATES]; /* diagnostics: the candidates of the last call */
static int candidate_count, candidate_dropped[MAX_CANDIDATES];

static uint32_t hash32(uint32_t x)
{
    x ^= x >> 16;
    x *= 0x7feb352dU;
    x ^= x >> 15;
    x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}

static int64_t color_slot(uint32_t key, int insert)
{
    uint32_t i = hash32(key) & (HASH_SIZE - 1);
    int probe;
    for (probe = 0; probe < 64; probe++) {
        if (h_gen[i] != generation) {
            if (!insert)
                return -1;
            h_gen[i] = generation;
            h_key[i] = key;
            h_count[i] = h_hruns[i] = h_vruns[i] = h_beside_light[i] = 0;
            h_anchor[i] = -1;
            return i;
        }
        if (h_key[i] == key)
            return i;
        i = (i + 1) & (HASH_SIZE - 1);
    }
    return -1; /* table crowded: the color is not counted */
}

static int memo_get(uint32_t key, uint32_t mask, uint32_t *value)
{
    uint32_t i = hash32(key ^ hash32(mask)) & (MEMO_SIZE - 1);
    int probe;
    for (probe = 0; probe < 8; probe++) {
        if (m_gen[i] != generation)
            return 0;
        if (m_key[i] == key && m_mask[i] == mask) {
            *value = m_val[i];
            return 1;
        }
        i = (i + 1) & (MEMO_SIZE - 1);
    }
    return 0;
}

static void memo_put(uint32_t key, uint32_t mask, uint32_t value)
{
    uint32_t i = hash32(key ^ hash32(mask)) & (MEMO_SIZE - 1);
    int probe;
    for (probe = 0; probe < 8; probe++) {
        if (m_gen[i] != generation || (m_key[i] == key && m_mask[i] == mask)) {
            m_gen[i] = generation;
            m_key[i] = key;
            m_mask[i] = mask;
            m_val[i] = value;
            return;
        }
        i = (i + 1) & (MEMO_SIZE - 1);
    }
}

static double sqrt_pos(double x)
{
    double y;
    int i;
    if (x <= 0.0)
        return 0.0;
    y = x > 1.0 ? x : 1.0;
    for (i = 0; i < 60; i++)
        y = 0.5 * (y + x / y);
    return y;
}

static uint8_t clamp_byte(double v)
{
    if (v <= 0.0)
        return 0;
    if (v >= 255.0)
        return 255;
    return (uint8_t)(v + 0.5);
}

static uint32_t pack(double r, double g, double b)
{
    return ((uint32_t)clamp_byte(r) << 16) | ((uint32_t)clamp_byte(g) << 8) | clamp_byte(b);
}

static void oklab_of(uint32_t rgb, double *l, double *chroma)
{
    double a, b;
    linear_to_oklab(SRGB_TO_LINEAR[(rgb >> 16) & 255], SRGB_TO_LINEAR[(rgb >> 8) & 255], SRGB_TO_LINEAR[rgb & 255],
                    l, &a, &b);
    *chroma = sqrt_pos(a * a + b * b);
}

static void oklab_ab(uint32_t rgb, double *a, double *b)
{
    double l;
    linear_to_oklab(SRGB_TO_LINEAR[(rgb >> 16) & 255], SRGB_TO_LINEAR[(rgb >> 8) & 255], SRGB_TO_LINEAR[rgb & 255],
                    &l, a, b);
}

/* A dark colored candidate whose hue matches readable (lighter) text-like color: that color's
 * smoothing against a dark background (red error text in the Output panel), not ink. */
#define SAME_HUE_COS 0.9
static int smoothing_of_readable(int k)
{
    const Anchor *c = &anchors[k];
    int j;
    for (j = 0; j < anchor_count; j++) {
        const Anchor *o = &anchors[j];
        double dot;
        if (j == k || o->surface || o->long_line || o->okl < INK_MAX_OKL || o->okl <= c->okl || o->chroma < INK_CHROMA)
            continue;
        dot = (c->oa * o->oa + c->ob * o->ob) / (c->chroma * o->chroma);
        if (dot >= SAME_HUE_COS)
            return 1;
    }
    return 0;
}

/* A low-color candidate lying between the background (anchor 0) and lighter colored text is that
 * text's ClearType smoothing (blue syntax on a dark editor paper fringes in gray-teal), never a dim
 * gray mark of its own: lifting it put light dots inside the text. */
static double blend_fit(double r, double g, double b, const Anchor *a, const Anchor *o, double *t_out, double *ee_out);

static int fringe_of_lighter_color(int k)
{
    const Anchor *c = &anchors[k], *paper = &anchors[0];
    int j;
    if (k == 0 || anchor_count == 0 || !paper->surface)
        return 0;
    for (j = 1; j < anchor_count; j++) {
        const Anchor *o = &anchors[j];
        double t, ee;
        if (j == k || o->surface || o->long_line || o->okl <= c->okl || o->chroma < INK_CHROMA)
            continue;
        if (blend_fit(c->r, c->g, c->b, paper, o, &t, &ee) <= LOCAL_BLEND_TOLERANCE * LOCAL_BLEND_TOLERANCE * ee
            && t > 0.03 && t < 0.97)
            return 1;
    }
    return 0;
}

static uint32_t mapped_one(uint32_t rgb, double dark_l, double light_l, double keep_tint)
{
    uint8_t r = (uint8_t)(rgb >> 16), g = (uint8_t)(rgb >> 8), b = (uint8_t)rgb;
    map_rgb(&r, &g, &b, dark_l, light_l, keep_tint);
    return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

static void oklab_of(uint32_t rgb, double *l, double *chroma);

/* ANCHORS_ICON: a colored color of middle lightness reads on light and dark alike: kept. */
static int icon_keeps(uint32_t rgb)
{
    double l, chroma;
    oklab_of(rgb, &l, &chroma);
    return chroma >= ICON_KEEP_CHROMA && l >= ICON_KEEP_MIN_OKL && l <= ICON_KEEP_MAX_OKL;
}

static uint32_t all_color(uint32_t rgb, int mode, double dark_l, double light_l, double keep_tint)
{
    if (mode == ANCHORS_ICON && icon_keeps(rgb))
        return rgb;
    return mapped_one(rgb, dark_l, light_l, keep_tint);
}

/* The fallback for a pixel no anchor or blend explains. */
static uint32_t lone_color(uint32_t rgb, int mode, double dark_l, double light_l, double keep_tint)
{
    if (mode == ANCHORS_RELIGHT)
        return rgb;
    if (mode == ANCHORS_ALL || mode == ANCHORS_ICON)
        return all_color(rgb, mode, dark_l, light_l, keep_tint);
    if (lightness((uint8_t)(rgb >> 16), (uint8_t)(rgb >> 8), (uint8_t)rgb) >= WHITE_HLS)
        return mapped_one(rgb, dark_l, light_l, 0.0); /* stray white: as the selective mapping did */
    return rgb;
}

/* How far (squared) color c lies from the segment a-b, and where along it (t, 0 to 1). */
static double blend_fit(double r, double g, double b, const Anchor *a, const Anchor *o, double *t_out, double *ee_out)
{
    double dr = r - a->r, dg = g - a->g, db = b - a->b;
    double er = o->r - a->r, eg = o->g - a->g, eb = o->b - a->b;
    double ee = er * er + eg * eg + eb * eb, t, xr, xg, xb;
    *ee_out = ee;
    if (ee <= 0.0) {
        *t_out = 0.0;
        return dr * dr + dg * dg + db * db;
    }
    t = (dr * er + dg * eg + db * eb) / ee;
    if (t < 0.0)
        t = 0.0;
    if (t > 1.0)
        t = 1.0;
    xr = dr - t * er;
    xg = dg - t * eg;
    xb = db - t * eb;
    *t_out = t;
    return xr * xr + xg * xg + xb * xb;
}

/* A text-like candidate lying between a surface more frequent than itself and either another
 * surface (a badge's rounded edge) or darker (or more colored) text-like candidate, of any
 * frequency, is smoothing between them, not a color of its own. Smoothing between a background
 * and lighter text is left alone: it stays as it is anyway. */
static int is_blend(int k, int n)
{
    const Anchor *c = &anchors[k];
    int i, j;
    if (c->surface || c->long_line)
        return 0;
    if (c->okl < c->light_okl && (double)c->on_light >= ON_LIGHT_SHARE * (double)c->count)
        return 0; /* gray text on a light row lies between the background and a white surface too */
    for (i = 0; i < k; i++) {
        const Anchor *s = &anchors[i];
        if (!s->surface)
            continue;
        for (j = 0; j < n; j++) {
            const Anchor *ink = &anchors[j];
            double t, ee;
            if (j == i || j == k || ink->long_line)
                continue;
            if (!ink->surface && !(ink->okl < c->okl || ink->chroma > c->chroma + 0.02))
                continue;
            if (ink->surface && !((c->touches >> j) & 1U))
                continue; /* a surface's edge touches it: gray text on a dark row lies between it and a white surface
                             * too (text fringes chain through each other, so text ink needs no touch) */
            if (blend_fit(c->r, c->g, c->b, s, ink, &t, &ee) <= BLEND_ANCHOR_TOLERANCE * BLEND_ANCHOR_TOLERANCE
                && t > 0.03 && t < 0.97)
                return 1;
        }
        /* ClearType's fringes of light text on a light surface (white digits on a gray badge): beside
         * the lighter text (touching it, where neighbors were surveyed; else often right beside much
         * lighter pixels: ClearType chains its fringes), and roughly between it and the surface. */
        if (c->okl > s->okl
            && (c->touches != ~(uint64_t)0 || (double)c->beside_light >= LIGHT_FRINGE_SHARE * (double)c->count)) {
            for (j = 0; j < n; j++) {
                const Anchor *text = &anchors[j];
                double t, ee;
                if (j == i || j == k || text->surface || text->long_line || text->okl <= c->okl
                    || c->count > 2 * text->count || !((c->touches >> j) & 1U))
                    continue; /* a fringe is rarer than the text it smooths, and beside it */
                if (blend_fit(c->r, c->g, c->b, s, text, &t, &ee) <= LOCAL_BLEND_TOLERANCE * LOCAL_BLEND_TOLERANCE * ee
                    && t > 0.03 && t < 0.97)
                    return 1;
            }
        }
    }
    return 0;
}

/* True when a horizontal neighbor of pixel i (of color c) is light, and much lighter than it. */
static int beside_light_pixel(const uint32_t *p, int64_t i, int64_t x, int64_t width, int64_t count, uint32_t c)
{
    const uint8_t *own = (const uint8_t *)&p[i];
    double floor = lightness(own[2], own[1], own[0]) + FRINGE_LIGHTER;
    int side;
    if (floor < FRINGE_LIGHT)
        floor = FRINGE_LIGHT;
    for (side = -1; side <= 1; side += 2) {
        int64_t j = i + side;
        const uint8_t *q;
        if ((side < 0 && x == 0) || (side > 0 && (j >= count || (width > 0 && x + 1 >= width))))
            continue;
        if ((p[j] >> 24) < ANCHOR_MIN_ALPHA || (p[j] & 0xffffff) == c)
            continue;
        q = (const uint8_t *)&p[j];
        if (lightness(q[2], q[1], q[0]) >= floor)
            return 1;
    }
    return 0;
}

/* Relighting: every color between the paper (anchor 0) and another color is that color's smoothing,
 * however frequent (text on a dark paper smooths through many dark shades). */
static void drop_paper_blends(void)
{
    int keep[MAX_ANCHORS], k, j, n = 0;
    for (k = 0; k < anchor_count; k++) {
        keep[k] = 1;
        for (j = 1; j < anchor_count && k > 0; j++) {
            double t, ee, res;
            if (j == k || anchors[j].surface || anchors[j].long_line)
                continue; /* toward text colors only: the margin, a surface, is no text */
            res = blend_fit(anchors[k].r, anchors[k].g, anchors[k].b, &anchors[0], &anchors[j], &t, &ee);
            if (t > 0.05 && t < 0.95 && res <= RELIGHT_BLEND_TOLERANCE * RELIGHT_BLEND_TOLERANCE * ee + 144.0) {
                keep[k] = 0;
                break;
            }
        }
    }
    for (k = 0; k < anchor_count; k++) {
        if (keep[k])
            anchors[n++] = anchors[k];
    }
    anchor_count = n;
}

/* Surfaces the ink mapping turns dark: white ones, and light low-color ones solid one way. */
static int light_surface_candidate(const Anchor *a)
{
    uint8_t px[3];
    px[2] = (uint8_t)a->r;
    px[1] = (uint8_t)a->g;
    px[0] = (uint8_t)a->b;
    if (!a->surface)
        return 0;
    if (lightness(px[2], px[1], px[0]) >= WHITE_HLS)
        return 1;
    return (a->hrun >= LIGHT_SURFACE_RUN || a->vrun >= LIGHT_SURFACE_RUN) && a->okl >= LIGHT_SURFACE_OKL
           && spread_of(px) <= LIGHT_SURFACE_SPREAD;
}

static int candidate_at(const uint32_t *p, int64_t i)
{
    int64_t slot;
    if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
        return -1;
    slot = color_slot(p[i] & 0xffffff, 0);
    return slot >= 0 ? h_anchor[slot] : -1;
}

/* For each text-like candidate: which candidates touch its pixels, and (ink mode) how many of its
 * pixels lie inside a light surface that turns dark (touching it, not the main background): text on
 * a selected light row or a white badge turns light with it; a light surface's smoothed edge touches
 * the background too. Large images are not surveyed: everything counts as touching. */
static void survey_neighbors(const uint32_t *p, int64_t count, int64_t width, int n)
{
    int8_t kind[MAX_CANDIDATES]; /* 1: a light surface; 2: the main background */
    int k, any = 0, main_found = 0;
    int64_t i;
    for (k = 0; k < n; k++) {
        kind[k] = 0;
        h_anchor[anchors[k].slot] = (int8_t)k;
        if (light_surface_candidate(&anchors[k])) {
            kind[k] = 1;
            any = 1;
        } else if (anchors[k].surface && !main_found) {
            kind[k] = 2;
            main_found = 1;
        }
    }
    for (k = 0; k < n; k++)
        anchors[k].touches = width > 0 && count <= SAMPLE_ABOVE ? 0U : ~(uint64_t)0;
    for (i = 0; width > 0 && count <= SAMPLE_ABOVE && i < count; i++) {
        int c = candidate_at(p, i), light = -1, main = 0, side;
        int64_t x = i % width, nb[4];
        if (c < 0 || anchors[c].surface)
            continue;
        nb[0] = x > 0 ? i - 1 : -1;
        nb[1] = x + 1 < width && i + 1 < count ? i + 1 : -1;
        nb[2] = i >= width ? i - width : -1;
        nb[3] = i + width < count ? i + width : -1;
        for (side = 0; side < 4; side++) {
            int o = nb[side] >= 0 ? candidate_at(p, nb[side]) : -1;
            if (o >= 0)
                anchors[c].touches |= (uint64_t)1 << o;
            if (o >= 0 && kind[o] == 1 && (light < 0 || anchors[o].okl > anchors[light].okl))
                light = o;
            else if (o >= 0 && kind[o] == 2)
                main = 1;
        }
        if (light >= 0 && !main) {
            anchors[c].on_light++;
            if (anchors[light].okl > anchors[c].light_okl)
                anchors[c].light_okl = anchors[light].okl;
        }
    }
    for (k = 0; k < n; k++)
        h_anchor[anchors[k].slot] = -1;
}

/* A colored candidate inside a light surface that touches darker text there is ClearType's fringe
 * of that text (bluish, orange): it turns gray, not dark blue; colored text itself keeps its hue. */
static int fringe_of_darker_text(int k)
{
    const Anchor *c = &anchors[k];
    int j;
    for (j = 0; j < anchor_count; j++) {
        const Anchor *o = &anchors[j];
        if (j != k && !o->surface && ((c->touches >> j) & 1U) && o->okl < c->okl - 0.05
            && (double)o->on_light >= ON_LIGHT_SHARE * (double)o->count)
            return 1;
    }
    return 0;
}

static void find_anchors(const uint32_t *p, int64_t count, int64_t width, int mode, double dark_l, double light_l,
                         double keep_tint, double main_default)
{
    int64_t i, total = 0, area = 0, last_slot = -1, min_count;
    int k, j, n;
    double main_l = main_default, share_of;
    int text_found = 0;
    generation++;
    if (generation == 0)
        generation = 1;
    for (i = 0; i < count; i++) {
        uint32_t v = p[i], c = v & 0xffffff;
        int64_t x = width > 0 ? i % width : i, slot;
        int left_same, up_same;
        if (count > SAMPLE_ABOVE && width > 0 && x == 0 && (i / width) % 2 == 1) {
            i += width - 1; /* large images (a glyph canvas): every other row is enough to find the anchors */
            last_slot = -1;
            continue;
        }
        area++;
        if ((v >> 24) < ANCHOR_MIN_ALPHA) {
            last_slot = -1;
            continue;
        }
        left_same = x > 0 && (p[i - 1] >> 24) >= ANCHOR_MIN_ALPHA && (p[i - 1] & 0xffffff) == c;
        up_same = width > 0 && i >= width && (p[i - width] >> 24) >= ANCHOR_MIN_ALPHA && (p[i - width] & 0xffffff) == c;
        slot = left_same && last_slot >= 0 ? last_slot : color_slot(c, 1);
        last_slot = slot;
        if (slot < 0)
            continue;
        h_count[slot]++;
        h_hruns[slot] += !left_same;
        h_vruns[slot] += !up_same;
        if (beside_light_pixel(p, i, x, width, count, c))
            h_beside_light[slot]++;
        total++;
    }
    n = 0;
    min_count = total / 4000 > 3 ? total / 4000 : 3;
    for (i = 0; i < HASH_SIZE; i++) {
        int64_t c = h_count[i];
        if (h_gen[i] != generation || c < min_count)
            continue;
        if (n == MAX_CANDIDATES && c <= anchors[MAX_CANDIDATES - 1].count)
            continue;
        k = n < MAX_CANDIDATES ? n++ : MAX_CANDIDATES - 1;
        while (k > 0 && anchors[k - 1].count < c) { /* most frequent first */
            anchors[k] = anchors[k - 1];
            k--;
        }
        anchors[k].r = (double)((h_key[i] >> 16) & 255);
        anchors[k].g = (double)((h_key[i] >> 8) & 255);
        anchors[k].b = (double)(h_key[i] & 255);
        anchors[k].count = c;
        anchors[k].slot = i;
        anchors[k].beside_light = h_beside_light[i];
        anchors[k].hrun = (double)c / (double)(h_hruns[i] > 0 ? h_hruns[i] : 1);
        anchors[k].vrun = (double)c / (double)(h_vruns[i] > 0 ? h_vruns[i] : 1);
    }
    for (k = 0; k < n; k++) {
        Anchor *a = &anchors[k];
        a->surface = a->hrun >= SURFACE_RUN && a->vrun >= SURFACE_RUN;
        a->line = !a->surface && (a->hrun >= LINE_RUN || a->vrun >= LINE_RUN);
        a->long_line = !a->surface && (a->hrun >= LONG_LINE_RUN || a->vrun >= LONG_LINE_RUN);
        oklab_of(pack(a->r, a->g, a->b), &a->okl, &a->chroma);
        oklab_ab(pack(a->r, a->g, a->b), &a->oa, &a->ob);
        a->on_light = 0;
        a->light_okl = 0.0;
    }
    survey_neighbors(p, count, width, n);
    /* Drop blends (see is_blend), judged among all candidates before any is dropped. */
    {
        int keep[MAX_CANDIDATES], moved[MAX_CANDIDATES];
        for (k = 0; k < n; k++) {
            keep[k] = !is_blend(k, n);
            candidates[k] = anchors[k];
            candidate_dropped[k] = !keep[k];
        }
        candidate_count = n;
        anchor_count = 0;
        for (k = 0; k < n; k++) {
            moved[k] = -1;
            if (keep[k] && anchor_count < MAX_ANCHORS) {
                moved[k] = anchor_count;
                anchors[anchor_count++] = anchors[k];
            }
        }
        for (k = 0; k < anchor_count; k++) { /* renumber what each kept anchor touches */
            uint64_t was = anchors[k].touches, now = 0;
            if (was == ~(uint64_t)0)
                continue;
            for (j = 0; j < n; j++) {
                if (((was >> j) & 1U) && moved[j] >= 0)
                    now |= (uint64_t)1 << moved[j];
            }
            anchors[k].touches = now;
        }
    }
    /* A widget that paints no background (what lies beneath shows through: main_default) has only
     * its text opaque: that text's share counts against its whole area, or black text drawn on
     * nothing (FontLab's Unicode ranges and codepages lists) would pass for the background. Dim
     * marks (a field's gray frame drawn on nothing) keep the share of the opaque pixels. */
    share_of = (double)total;
    if (anchor_count > 0 && anchors[0].surface)
        main_l = anchors[0].okl;
    else
        share_of = (double)area;
    if (mode == ANCHORS_RELIGHT && anchor_count > 2)
        drop_paper_blends();
    light_bits = 0;
    for (j = 0; j < anchor_count; j++) {
        Anchor *a = &anchors[j];
        uint32_t rgb = pack(a->r, a->g, a->b), out = rgb;
        double hls = lightness((uint8_t)a->r, (uint8_t)a->g, (uint8_t)a->b);
        uint8_t px[3];
        px[2] = (uint8_t)a->r;
        px[1] = (uint8_t)a->g;
        px[0] = (uint8_t)a->b;
        a->mapped = 0;
        if (mode == ANCHORS_RELIGHT) {
            if (spread_of(px) <= RELIGHT_SPREAD && a->surface && a->okl < RELIGHT_PAPER_OKL && j == 0) {
                out = 0xffffff;
                a->mapped = 1;
            } else if (spread_of(px) <= RELIGHT_SPREAD && !a->surface && a->okl >= RELIGHT_TEXT_OKL && !text_found) {
                text_found = 1; /* the editor's own text color: the most frequent light one */
                out = 0x000000;
                a->mapped = 1;
            }
        } else if (mode == ANCHORS_ALL || mode == ANCHORS_ICON) {
            out = all_color(rgb, mode, dark_l, light_l, keep_tint);
            a->mapped = out != rgb || mode == ANCHORS_ALL;
        } else if (hls >= WHITE_HLS && (a->surface || a->line)) {
            out = mapped_one(rgb, dark_l, light_l, 0.0);
            a->mapped = 1;
        } else if (a->surface && (a->hrun >= LIGHT_SURFACE_RUN || a->vrun >= LIGHT_SURFACE_RUN)
                   && a->okl >= LIGHT_SURFACE_OKL && spread_of(px) <= LIGHT_SURFACE_SPREAD) {
            out = mapped_one(rgb, dark_l, light_l, 0.0);
            a->mapped = 1;
        } else if (!a->surface && !a->long_line && a->okl <= a->light_okl + 0.01
                   && (double)a->on_light >= ON_LIGHT_SHARE * (double)a->count) {
            /* text darker than the light surface it lies in turns as that surface does, as an island
             * (ClearType's palest fringes too); white text on a gray badge, lighter than it, stays */
            int colored = a->chroma >= INK_CHROMA && !fringe_of_darker_text(j);
            out = colored ? mapped_one(rgb, dark_l, light_l, 1.0) : all_color(rgb, ANCHORS_ALL, dark_l, light_l, 0.0);
            a->mapped = 1;
        } else if (!a->long_line && (double)a->count < BACKGROUND_SHARE * share_of && a->okl < INK_MAX_OKL
                   && (!a->surface || a->okl <= SURFACE_INK_MAX_OKL)
                   && (a->okl <= main_l - INK_BELOW_MAIN
                       || (a->chroma >= INK_CHROMA && (double)a->beside_light < FRINGE_SHARE * (double)a->count
                           && !smoothing_of_readable(j)))) {
            out = mapped_one(rgb, dark_l, light_l, a->chroma >= INK_CHROMA ? 1.0 : 0.0);
            a->mapped = 1;
        } else if (!a->surface && !a->long_line && a->chroma < INK_CHROMA && a->okl < DIM_INK_MAX_OKL
                   && a->okl >= main_l + DIM_INK_ABOVE_MAIN && (double)a->count < BACKGROUND_SHARE * (double)total
                   && !fringe_of_lighter_color(j)) {
            double light = gray_byte(light_l);
            out = mapped_one(rgb, dark_l, light_l, 0.0);
            out = pack(((out >> 16) & 255) + (light - ((out >> 16) & 255)) * DIM_INK_LIFT,
                       ((out >> 8) & 255) + (light - ((out >> 8) & 255)) * DIM_INK_LIFT,
                       (out & 255) + (light - (out & 255)) * DIM_INK_LIFT);
            a->mapped = 1;
        }
        if (mode == ANCHORS_INK) {
            uint32_t island = all_color(rgb, ANCHORS_ALL, dark_l, light_l, 0.0);
            a->ir = (double)((island >> 16) & 255);
            a->ig = (double)((island >> 8) & 255);
            a->ib = (double)(island & 255);
            if (a->mapped && light_surface_candidate(a))
                light_bits |= 1U << j;
        }
        a->mr = (double)((out >> 16) & 255);
        a->mg = (double)((out >> 8) & 255);
        a->mb = (double)(out & 255);
        h_anchor[a->slot] = (int8_t)j;
    }
}

/* Which anchor each pixel is (-1: none), for neighborhoods. */
static void index_pixels(const uint32_t *p, int64_t count)
{
    int64_t i;
    uint32_t last = 0;
    int8_t last_index = -1;
    int have = 0;
    for (i = 0; i < count; i++) {
        uint32_t v = p[i];
        if ((v >> 24) < ANCHOR_MIN_ALPHA) {
            a_index[i] = -1;
            continue;
        }
        if (!have || v != last) {
            int64_t slot = color_slot(v & 0xffffff, 0);
            last_index = slot >= 0 ? h_anchor[slot] : -1;
            last = v;
            have = 1;
        }
        a_index[i] = last_index;
    }
}

static uint32_t neighborhood(int64_t i, int64_t count, int64_t width)
{
    uint32_t mask = 0;
    int64_t x = i % width, y = i / width, rows = count / width, dx, dy;
    for (dy = -NEIGHBORHOOD; dy <= NEIGHBORHOOD; dy++) {
        int64_t yy = y + dy;
        if (yy < 0 || yy >= rows)
            continue;
        for (dx = -NEIGHBORHOOD; dx <= NEIGHBORHOOD; dx++) {
            int64_t xx = x + dx;
            int8_t a;
            if (xx < 0 || xx >= width)
                continue;
            a = a_index[yy * width + xx];
            if (a >= 0)
                mask |= 1U << a;
        }
    }
    return mask;
}

/* The best pair for color (r, g, b): both anchors in `both` if possible, else at least one in `one`. */
static double anchor_spread(const Anchor *a)
{
    double hi = a->r > a->g ? (a->r > a->b ? a->r : a->b) : (a->g > a->b ? a->g : a->b);
    double lo = a->r < a->g ? (a->r < a->b ? a->r : a->b) : (a->g < a->b ? a->g : a->b);
    return hi - lo;
}

#define FAR_PAIR_EXTRA_SPREAD 40.0 /* a far pair's blend is at most this much more colored than its anchors */
#define FAR_PAIR_MAX_DISTANCE 30.0 /* and this far (RGB) from the line between them, however long the line */

static int best_pair(double r, double g, double b, uint32_t both, uint32_t one, double local_tolerance, int *pa, int *pb,
                     double *pt)
{
    double best = -1.0, hi = r > g ? (r > b ? r : b) : (g > b ? g : b), lo = r < g ? (r < b ? r : b) : (g < b ? g : b);
    int j, k;
    for (j = 0; j < anchor_count; j++) {
        for (k = j + 1; k < anchor_count; k++) {
            double t, ee, res, tol;
            int in_both = ((both >> j) & 1) && ((both >> k) & 1);
            int in_one = ((one >> j) & 1) || ((one >> k) & 1);
            if (!in_both && !in_one)
                continue;
            res = blend_fit(r, g, b, &anchors[j], &anchors[k], &t, &ee);
            if (ee <= 0.0)
                continue;
            tol = (in_both ? local_tolerance * local_tolerance : BLEND_TOLERANCE * BLEND_TOLERANCE) * ee;
            if (tol < BLEND_MIN_TOLERANCE * BLEND_MIN_TOLERANCE)
                tol = BLEND_MIN_TOLERANCE * BLEND_MIN_TOLERANCE;
            if (!in_both && tol > FAR_PAIR_MAX_DISTANCE * FAR_PAIR_MAX_DISTANCE)
                tol = FAR_PAIR_MAX_DISTANCE * FAR_PAIR_MAX_DISTANCE;
            if (res > tol)
                continue;
            if (!in_both) {
                /* Spread is convex: a blend is no more colored than the more colored of its two ends.
                 * Far pairs keep to that (a red digit fitted the long black-to-white line within its
                 * loose tolerance and turned white); pairs from around the pixel explain ClearType's
                 * colored fringes, which exceed it. */
                double ends = anchor_spread(&anchors[j]) > anchor_spread(&anchors[k]) ? anchor_spread(&anchors[j])
                                                                                       : anchor_spread(&anchors[k]);
                if (hi - lo > ends + FAR_PAIR_EXTRA_SPREAD)
                    continue;
                res += 1e9; /* a pair from around the pixel always wins */
            }
            if (best < 0.0 || res < best) {
                best = res;
                *pa = j;
                *pb = k;
                *pt = t;
            }
        }
    }
    return best >= 0.0;
}

/* tint: how much of a pixel's color beyond the blend that explains it is kept (content keeps its
 * small tinted details, such as node fills and handles; the interface and text edges keep none). */
/* A pixel lighter than the light surfaces around it: smoothing of white text on a gray badge, which
 * stays light while the badge turns dark, unlike dark text inside a light row. */
static int lighter_than_light_surface(uint32_t c, uint32_t surfaces)
{
    double l, chroma, surface_l = 0.0;
    int j;
    for (j = 0; j < anchor_count; j++) {
        if (((surfaces >> j) & 1U) && anchors[j].okl > surface_l)
            surface_l = anchors[j].okl;
    }
    oklab_of(c, &l, &chroma);
    return l > surface_l + 0.01;
}

static uint32_t resolve(uint32_t c, int translucent, uint32_t mask, int mode, double dark_l, double light_l,
                        double keep_tint, double tint)
{
    double r = (double)((c >> 16) & 255), g = (double)((c >> 8) & 255), b = (double)(c & 255);
    double best = -1.0, t = 0.0;
    int a_i = -1, b_i = -1, j;
    uint32_t all = anchor_count >= 32 ? 0xffffffffU : ((1U << anchor_count) - 1U);
    if (translucent) { /* smoothed edges against nothing: the color is the shape's own */
        for (j = 0; j < anchor_count; j++) {
            double dr = r - anchors[j].r, dg = g - anchors[j].g, db = b - anchors[j].b;
            double d2 = dr * dr + dg * dg + db * db;
            if (d2 <= NEAR_ANCHOR * NEAR_ANCHOR && (best < 0.0 || d2 < best)) {
                best = d2;
                a_i = j;
            }
        }
        if (a_i >= 0) {
            Anchor *a = &anchors[a_i];
            if (!a->mapped)
                return c;
            return pack(a->mr + r - a->r, a->mg + g - a->g, a->mb + b - a->b);
        }
        return lone_color(c, mode, dark_l, light_l, keep_tint);
    }
    for (j = 0; j < anchor_count; j++) {
        if (anchors[j].r == r && anchors[j].g == g && anchors[j].b == b)
            return pack(anchors[j].mr, anchors[j].mg, anchors[j].mb);
    }
    if (mode == ANCHORS_INK && (mask & light_bits) && !(mask & main_bit)
        && !lighter_than_light_surface(c, mask & light_bits)) { /* inside it, not at its edge */
        /* Beside a light surface that turns dark (a selected row, a white thumbnail), everything
         * turns as an island does: its rare marks (a digit, a glyph's gray edges) have no anchor
         * of their own, and pairs with far dark colors put them dark on the now dark surface. */
        uint8_t px[3];
        px[2] = (uint8_t)r;
        px[1] = (uint8_t)g;
        px[0] = (uint8_t)b;
        if (spread_of(px) > LINEAR_SPREAD && (best_pair(r, g, b, mask, mask, LOCAL_BLEND_TOLERANCE, &a_i, &b_i, &t)
                                              || best_pair(r, g, b, 0U, all, BLEND_TOLERANCE, &a_i, &b_i, &t))) {
            Anchor *a = &anchors[a_i], *o = &anchors[b_i];
            return pack(a->ir + t * (o->ir - a->ir), a->ig + t * (o->ig - a->ig), a->ib + t * (o->ib - a->ib));
        }
        return all_color(c, ANCHORS_ALL, dark_l, light_l, 0.0);
    }
    if (mode == ANCHORS_ALL || mode == ANCHORS_ICON) {
        /* Where everything is mapped, the linear mapping of low-color pixels already keeps blends
         * blends (it is affine): only colored pixels need a pair, which spares the many colors of
         * a font window's smoothed glyphs the search. */
        uint8_t px[3];
        px[2] = (uint8_t)r;
        px[1] = (uint8_t)g;
        px[0] = (uint8_t)b;
        if (spread_of(px) <= LINEAR_SPREAD)
            return all_color(c, mode, dark_l, light_l, tint);
    }
    if (!(mask && best_pair(r, g, b, mask, mask, LOCAL_BLEND_TOLERANCE, &a_i, &b_i, &t))
        && !best_pair(r, g, b, 0U, all, BLEND_TOLERANCE, &a_i, &b_i, &t))
        return lone_color(c, mode, dark_l, light_l, tint);
    {
        Anchor *a = &anchors[a_i], *o = &anchors[b_i];
        double xr = r - (a->r + t * (o->r - a->r)), xg = g - (a->g + t * (o->g - a->g)), xb = b - (a->b + t * (o->b - a->b));
        if (!a->mapped && !o->mapped)
            return c;
        return pack(a->mr + t * (o->mr - a->mr) + tint * xr, a->mg + t * (o->mg - a->mg) + tint * xg,
                    a->mb + t * (o->mb - a->mb) + tint * xb);
    }
}

/* ClearType puts colored fringes beside dark text strokes: a pixel this much lighter or darker
 * than a horizontal neighbor keeps no tint, even in content. Fainter lines (handles) keep theirs. */
#define FRINGE_STEP 0.3

static int sharp_edge(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    const uint8_t *px = (const uint8_t *)&p[i];
    double l = lightness(px[2], px[1], px[0]);
    int64_t x = i % width;
    if (x > 0) {
        const uint8_t *q = (const uint8_t *)&p[i - 1];
        double d = l - lightness(q[2], q[1], q[0]);
        if (d >= FRINGE_STEP || -d >= FRINGE_STEP)
            return 1;
    }
    if (x + 1 < width && i + 1 < count) {
        const uint8_t *q = (const uint8_t *)&p[i + 1];
        double d = l - lightness(q[2], q[1], q[0]);
        if (d >= FRINGE_STEP || -d >= FRINGE_STEP)
            return 1;
    }
    return 0;
}

EXPORT int64_t freelab_map_anchors(uint8_t *pixels, int64_t count, int64_t width, int mode, double dark_l,
                                   double light_l, double keep_tint, double main_default, int apply)
{
    uint32_t *p = (uint32_t *)pixels;
    uint32_t last_in = 0, last_out = 0;
    int have_last = 0, any_mapped = 0, j, local, tinted, last_edge = 0;
    uint32_t paper_bit, other_surfaces;
    int64_t i, changed = 0;
    find_anchors(p, count, width, mode, dark_l, light_l, keep_tint, main_default);
    for (j = 0; j < anchor_count; j++)
        any_mapped |= anchors[j].mapped;
    if (!any_mapped && mode == ANCHORS_RELIGHT)
        return 0;
    if (!any_mapped) {
        /* Nothing to map but stray whites (a pure white pixel that is no anchor). */
        for (i = 0; i < count; i++) {
            uint8_t *px = pixels + 4 * i;
            if (px[3] > 0 && lightness(px[2], px[1], px[0]) >= WHITE_HLS) {
                changed++;
                if (apply)
                    map_rgb(&px[2], &px[1], &px[0], dark_l, light_l, 0.0);
            }
        }
        return changed;
    }
    /* Neighborhoods matter where kept and mapped anchors could explain the same pixel. */
    local = (mode == ANCHORS_INK || mode == ANCHORS_RELIGHT) && width > 0 && count <= MAX_INDEXED;
    if (local)
        index_pixels(p, count);
    tinted = (mode == ANCHORS_ALL || mode == ANCHORS_ICON) && keep_tint > 0.0 && width > 0;
    /* Text smoothing lies between the paper and the text, even where the pixels around are all
     * fringes (ClearType's navy and red beside blue syntax on a dark editor): the kept paper always
     * counts as around, or a far pair of text colors (blue and black ink) claimed those fringes. */
    paper_bit = mode == ANCHORS_INK && anchor_count > 1 && anchors[0].surface && !anchors[0].mapped ? 1U : 0U;
    main_bit = paper_bit;
    other_surfaces = 0;
    for (j = 1; j < anchor_count; j++)
        other_surfaces |= anchors[j].surface ? 1U << j : 0U;
    for (i = 0; i < count; i++) {
        uint32_t v = p[i], alpha = v >> 24, c, key, out, mask = 0;
        int edge;
        if (alpha == 0)
            continue;
        if (local && alpha >= ANCHOR_MIN_ALPHA && a_index[i] < 0)
            mask = neighborhood(i, count, width);
        if (mask && !(mask & other_surfaces))
            mask |= paper_bit; /* not on another surface (a light row): the paper is around */
        edge = tinted && sharp_edge(p, i, width, count);
        if (have_last && v == last_in && edge == last_edge && (!local || mask == 0 || a_index[i] >= 0)) {
            if (last_out != v) {
                changed++;
                if (apply)
                    p[i] = last_out;
            }
            continue;
        }
        c = v & 0xffffff;
        key = c | (alpha < ANCHOR_MIN_ALPHA ? 0x1000000U : 0U) | (edge ? 0x2000000U : 0U);
        if (!memo_get(key, mask, &out)) {
            out = resolve(c, alpha < ANCHOR_MIN_ALPHA, mask, mode, dark_l, light_l, keep_tint,
                          (mode == ANCHORS_ALL || mode == ANCHORS_ICON) && !edge ? keep_tint : 0.0);
            memo_put(key, mask, out);
        }
        out |= v & 0xff000000U;
        last_in = v;
        last_out = out;
        last_edge = edge;
        have_last = mask == 0;
        if (out != v) {
            changed++;
            if (apply)
                p[i] = out;
        }
    }
    return changed;
}

/* Diagnostics: the candidates of the last call before blends were dropped: 0xRRGGBB, and per
 * candidate six numbers: count, flags (1 dropped, 2 surface, 4 line, 8 long line), beside_light,
 * on_light, touches (low 32 bits), and OKLab lightness times 1000. */
EXPORT int64_t freelab_last_candidates(uint32_t *rgb, int64_t *info, int64_t max)
{
    int64_t k;
    for (k = 0; k < candidate_count && k < max; k++) {
        const Anchor *a = &candidates[k];
        rgb[k] = pack(a->r, a->g, a->b);
        info[6 * k] = a->count;
        info[6 * k + 1] = candidate_dropped[k] | (a->surface ? 2 : 0) | (a->line ? 4 : 0) | (a->long_line ? 8 : 0);
        info[6 * k + 2] = a->beside_light;
        info[6 * k + 3] = a->on_light;
        info[6 * k + 4] = (int64_t)(a->touches & 0xffffffffU);
        info[6 * k + 5] = (int64_t)(a->okl * 1000.0);
    }
    return candidate_count;
}

/* Diagnostics: the anchors of the last call, as 0xRRGGBB, counts, and flags (1 mapped, 2 surface,
 * 4 line, 8 long line), at most max of them; returns how many there were. */
EXPORT int64_t freelab_last_anchors(uint32_t *rgb, int64_t *counts, int *flags, int64_t max)
{
    int64_t j;
    for (j = 0; j < anchor_count && j < max; j++) {
        rgb[j] = pack(anchors[j].r, anchors[j].g, anchors[j].b);
        counts[j] = anchors[j].count;
        flags[j] = anchors[j].mapped | (anchors[j].surface << 1) | (anchors[j].line << 2) | (anchors[j].long_line << 3);
    }
    return anchor_count;
}
