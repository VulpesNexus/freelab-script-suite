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

#define FREELAB_PIXELS_VERSION 158

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
#define TINTED_LINEAR_SPREAD 30 /* where tint is kept the mapping is not affine for colored pixels: the smoothing of a
                                * thin orange outline, mapped alone, came out lighter than its dark red core (dotted) */
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
/* Gray text's ClearType fringes in an area already dark (a bar dark mode's stylesheet darkened,
 * drawn opaque, so its text got subpixel smoothing): each fringe pixel becomes the mean of its
 * channels, the coverage grayscale smoothing would give. Row by row, colored pixels form runs;
 * a run is a fringe when its strongest channel flips (the two sides of a thin stem) or when a
 * light neutral pixel (a text core: DEFRINGE_TEXT_STEP above the ground) lies within
 * DEFRINGE_REACH pixels of it. Kept as they are:
 * - neutral pixels;
 * - colors with a channel darker than the ground: a fringe of gray text on a gray ground has
 *   every channel between the two. The ground is the most frequent opaque neutral gray, so a
 *   darker field or outline does not lower it;
 * - runs of DEFRINGE_MIN_RUN or more pixels of one strongest channel (colored text and its own
 *   smoothing), and colored runs with no text core beside them (a vertical colored line, a
 *   swatch edge);
 * - runs with no core, or longer than DEFRINGE_MAX_FRINGE, whose colors do not add up to gray
 *   (colored text's own ClearType edges, a bar of several colors: Font Check's green log
 *   and blue link, its coverage bars, all drawn gray before: 2026-11-25).
 * The pixels are changed in place, so text cores are flagged from each row's original pixels
 * first (rows wider than DEFRINGE_MAX_WIDTH are left as they are). */
#define DEFRINGE_NEUTRAL 6
#define DEFRINGE_FLOOR_TOLERANCE 8
#define DEFRINGE_MIN_RUN 3
#define DEFRINGE_TEXT_STEP 24
#define DEFRINGE_REACH 2
#define DEFRINGE_MAX_WIDTH 16384
#define DEFRINGE_MAX_FRINGE 6   /* longer runs of mixed colors are text edges only when they add up to gray */
#define DEFRINGE_FILL_REPEAT 3  /* a color this many times in one run: a fill under the text, not a fringe */
#define DEFRINGE_PAIR_SPREAD 48 /* most spread of a coreless run's mean color: edges that add up to gray */

static uint8_t defringe_core[DEFRINGE_MAX_WIDTH];
static uint8_t defringe_fill[DEFRINGE_MAX_WIDTH]; /* a run's pixels in a stretch of one color (a fill) */
static int same_rgb(const uint8_t *a, const uint8_t *b)
{
    return a[0] == b[0] && a[1] == b[1] && a[2] == b[2];
}

static int strongest_channel(const uint8_t *px)
{
    return px[2] >= px[1] && px[2] >= px[0] ? 2 : (px[1] >= px[0] ? 1 : 0);
}

static int min_channel(const uint8_t *px)
{
    return px[0] < px[1] ? (px[0] < px[2] ? px[0] : px[2]) : (px[1] < px[2] ? px[1] : px[2]);
}

static int colored(const uint8_t *px)
{
    return px[3] != 0 && spread_of(px) > DEFRINGE_NEUTRAL;
}

/* Each pixel made the gray of its darkest channel, its alpha kept: dark text ClearType has drawn, where each
 * channel holds another third of a stroke, so that the mean of the three is a third or two of the ink at most
 * (a panel's title on a narrow panel: its thin capitals came out uneven, some stems half as strong as others:
 * the owner, 2026-11-24). The darkest channel says how much ink the stroke has there. */
EXPORT void freelab_gray_darkest(uint8_t *pixels, int64_t count)
{
    int64_t i;
    for (i = 0; i < count; i++) {
        uint8_t *px = pixels + 4 * i, m = px[0];
        if (px[1] < m)
            m = px[1];
        if (px[2] < m)
            m = px[2];
        px[0] = px[1] = px[2] = m;
    }
}

EXPORT void freelab_defringe(uint8_t *pixels, int64_t count, int64_t width, int max_spread)
{
    int64_t histogram[256];
    int64_t i, row, best = 0;
    int ground = -1, v;
    if (width <= 0 || width > DEFRINGE_MAX_WIDTH)
        return;
    for (v = 0; v < 256; v++)
        histogram[v] = 0;
    for (i = 0; i < count; i++) {
        const uint8_t *px = pixels + 4 * i;
        if (px[3] == 255 && spread_of(px) <= DEFRINGE_NEUTRAL)
            histogram[min_channel(px)]++;
    }
    for (v = 0; v < 256; v++) {
        if (histogram[v] > best) {
            best = histogram[v];
            ground = v;
        }
    }
    if (ground < 0)
        return;  /* no opaque neutral pixel: nothing to tell fringes by (a transparent source smooths in grays already) */
    for (row = 0; row + width <= count; row += width) {
        int64_t x = 0, k;
        for (k = 0; k < width; k++) {
            const uint8_t *px = pixels + 4 * (row + k);
            defringe_core[k] = (uint8_t)(px[3] != 0 && spread_of(px) <= DEFRINGE_NEUTRAL
                                         && min_channel(px) >= ground + DEFRINGE_TEXT_STEP);
        }
        while (x < width) {
            int64_t start = x;
            int same = 1, channel, core = 0;
            if (!colored(pixels + 4 * (row + x))) {
                x++;
                continue;
            }
            channel = strongest_channel(pixels + 4 * (row + x));
            while (x < width && colored(pixels + 4 * (row + x))) {
                same = same && strongest_channel(pixels + 4 * (row + x)) == channel;
                x++;
            }
            if (same && x - start >= DEFRINGE_MIN_RUN)
                continue;  /* colored text */
            for (k = start - DEFRINGE_REACH; k < x + DEFRINGE_REACH; k++)
                if (k >= 0 && k < width && defringe_core[k])
                    core = 1;
            if (same && !core)
                continue;  /* no text beside it: a colored line or a swatch's edge */
            if (!core || x - start > DEFRINGE_MAX_FRINGE) {
                /* A light stem too thin for a core is a pair of opposite edges whose colors add up to gray, and
                 * so are the edges of small light text running across letters (7 to 12 pixels); colored text
                 * keeps ClearType where it is drawn on an opaque ground (a log's green counts, its blue link),
                 * and its edges add up to its color, as a bar of several colors does (Font Check's coverage,
                 * 150 pixels, a light gray end beside it for a core) */
                int64_t sum[3] = {0, 0, 0}, lo, hi;
                for (k = start; k < x; k++) {
                    const uint8_t *px = pixels + 4 * (row + k);
                    sum[0] += px[0];
                    sum[1] += px[1];
                    sum[2] += px[2];
                }
                lo = sum[0] < sum[1] ? (sum[0] < sum[2] ? sum[0] : sum[2]) : (sum[1] < sum[2] ? sum[1] : sum[2]);
                hi = sum[0] > sum[1] ? (sum[0] > sum[2] ? sum[0] : sum[2]) : (sum[1] > sum[2] ? sum[1] : sum[2]);
                if (hi - lo > DEFRINGE_PAIR_SPREAD * (x - start))
                    continue;
            }
            {
                /* Identical pixels side by side, DEFRINGE_FILL_REPEAT or more, are a fill the text is drawn on, not a
                 * fringe (ClearType's are one or two pixels wide): the Fonts panel's blue disc, cut into short runs by
                 * the R on it, came out a gray band across the disc (2026-11-27). They stay; the others are grayed. */
                int64_t from = start;
                while (from < x) {  /* first the stretches, on the pixels as they are */
                    int64_t end = from + 1;
                    while (end < x && same_rgb(pixels + 4 * (row + end), pixels + 4 * (row + from)))
                        end++;
                    for (k = from; k < end; k++)
                        defringe_fill[k] = (uint8_t)(end - from >= DEFRINGE_FILL_REPEAT);
                    from = end;
                }
                for (k = start; k < x; k++) {
                    uint8_t *px = pixels + 4 * (row + k);
                    if (defringe_fill[k])
                        continue;
                    if (spread_of(px) > max_spread || min_channel(px) + DEFRINGE_FLOOR_TOLERANCE < ground)
                        continue;
                    px[0] = px[1] = px[2] = (uint8_t)((px[0] + px[1] + px[2] + 1) / 3);
                }
            }
        }
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
#define ANCHORS_SUBPIXEL_SYNTAX 5 /* as ANCHORS_SUBPIXEL, for an editor on light paper: colored syntax, never black assumed */
#define ANCHORS_INK_LIST 6 /* as ANCHORS_INK, for a list's rows: drawn on nothing, its gray sub-items and glyph icons are ink too */
#define ANCHORS_SUBPIXEL 4 /* as ANCHORS_ALL, for ClearType text drawn on purpose (TrueType Hinting's preview):
                              each channel's coverage between the paper and the text is kept */
#define ICON_KEEP_CHROMA 0.08
#define ICON_KEEP_MIN_OKL 0.4
#define ICON_KEEP_MAX_OKL 0.85
/* Dim gray marks (icons drawn in dark gray, near black against white in light mode) on the dark
 * interface: mapped, then lightened this much further toward the light gray. */
#define DIM_INK_ABOVE_MAIN 0.08
#define DIM_INK_MAX_OKL 0.58
#define DIM_INK_LIFT 0.35
#define DIM_INK_MAX_OKL_BARE 0.66 /* on nothing (a list painting no background), gray drawn for a light ground: sub-items */
/* Glyph icons drawn on nothing, for a light ground (the font window's sidebar): FontLab draws them dark
 * gray, solid enough to pass for surfaces, and its badges as dark tiles behind white letters, in the
 * same colors. Each connected shape decides: none lighter than GLYPH_ICON_LIGHT_HLS inside its box, an
 * icon, mapped as ink; light text inside, a badge, drawn as it is (a black badge mapped light lost its
 * white letter). */
#define GLYPH_ICON_MAX_OKL 0.5
#define GLYPH_ICON_MAX_SIDE 48 /* pixels: a shape this large both ways (or four times as long) is a panel */
#define GLYPH_ICON_LIGHT_HLS 0.8
#define GLYPH_BADGE_MIN_LIGHT 4 /* light pixels in a shape's box: a badge's letters, */
#define GLYPH_BADGE_LIGHT_SHARE 0.04 /* as a share of the shape's own pixels */
#define GLYPH_TILE_FILL 85 /* percent of its box a tile fills, its dark ground and light letters together */
#define GLYPH_TILE_LETTER_HLS 0.45 /* a tile's letters this light at least: Malayalam's and Tamil's are mid-gray */
#define GLYPH_TILE_GROW_HLS 0.2 /* the flood goes through a tile's letters this light: their ClearType edges too, not its black border */
#define GLYPH_SOLID_SHARE 0.7 /* a shape filling this much of its box is a block, not a glyph */
#define GLYPH_ICON_NEAR 4 /* per channel: a pixel of the shape's color (premultiplied rounding of translucent text) */
#define GLYPH_ICON_GROW 24 /* per channel: the shape goes on through its blends with a translucent fill (a flag's tint) */
/* A row FontLab paints dark itself (the selected row of Export Profiles, #313131 from the dark palette,
 * with light ClearType text) is a panel of such a color, and the counters of its letters, closed off
 * by the text, are small shapes of that same color: mapped as glyph icons, they filled the letters
 * with light gray, and the text looked struck twice. A shape inside the box of a panel of its own
 * color, with only opaque pixels around it, is a hole in what is drawn on the panel, and goes as the
 * panel does. */
#define GLYPH_MAX_PANELS 64 /* panels remembered per image (later ones are not) */
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
#define LIGHT_SURFACE_MIN_COUNT 500 /* pixels: a light surface, of them all (a selected row holds thousands) */
#define BACKGROUND_SHARE 0.2 /* a color covering this much is a background, never ink */
#define FRINGE_SHARE 0.4 /* a dark, colored pixel this often right beside light ones is ClearType smoothing of light text */
#define LIGHT_FRINGE_SHARE 0.15 /* a light fringe this often beside lighter text (badges): smoothing */
#define FRINGE_LIGHT 0.4 /* HLS lightness of "light" for that, */
#define FRINGE_LIGHTER 0.15 /* and at least this much lighter than the pixel */
#define LIGHT_SURFACE_OKL 0.6
#define CONTENT_KEEP_CHROMA 0.1
#define CONTENT_KEEP_MIN_OKL 0.45
#define DEFRINGE_CHROMA 0.05 /* text this colored loses ClearType's fringes toward the paper */
#define MAIN_MIN_AREA_SHARE 0.1 /* the most frequent surface is the background only if it covers this much of the image
                                  * (an unticked box in a list painted on nothing is not) */
#define ON_LIGHT_SHARE 0.5 /* a text color this often inside a light surface (touching it, not the background) */
#define KEPT_TEXT_NEAR_LIGHT 0.03 /* OKLab L around the mapping's light end: the dark interface's own light text, */
#define KEPT_TEXT_MAX_SPREAD 12 /* a gray (a ClearType fringe of other text is tinted) */
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
static uint8_t white_mark[MAX_INDEXED]; /* decided on the pixels as drawn: 1 a white mark kept, 2 a box edge (ink); 4 light text on a kept color (content);
                                         * 3 a ClearType fringe (content) */
static uint8_t icon_px[MAX_INDEXED]; /* ink mode on nothing: 1 a glyph icon's pixel, mapped; 2 seen; 3 a badge's, kept */
static int32_t icon_queue[MAX_INDEXED]; /* a shape's pixels, found in turn */
static int last_paper_found; /* the last call found a main background */
static int mode_list; /* set per call: a list's rows (ANCHORS_INK_LIST) */

/* A list's rows are drawn on nothing, so their text's smoothing is its transparency. Dark text
 * mapped light keeps that coverage, and light on dark looks heavier than dark on light did: the
 * small counters of bold text (e, p, O in Export Profiles) filled in. The partly covered pixels of
 * light ink get less coverage (a power of it), as text drawn light on dark is. Only the edges: a pixel
 * the mapping changed, beside a more opaque one (a 4-neighbor). Gray sub-items drawn translucent
 * throughout keep their cores, and light pixels drawn as they are (a badge's white letters) stay. */
#define LIGHT_SMOOTHING_POWER 12 /* coverage ** (1 + 12 / 20): ** 1.6, bold counters open, small text whole */
#define LIGHT_SMOOTHING_MIN_HLS 0.55
static uint8_t smoothing_table[256];
static int smoothing_table_made;
static uint8_t thin_px[MAX_INDEXED]; /* a list's rows: 1 the mapping changed the pixel, 2 an edge thinned */

static int more_opaque_beside(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    uint32_t a = p[i] >> 24;
    int64_t x = i % width;
    return (x > 0 && (p[i - 1] >> 24) > a) || (x + 1 < width && (p[i + 1] >> 24) > a)
           || (i >= width && (p[i - width] >> 24) > a) || (i + width < count && (p[i + width] >> 24) > a);
}

static void thin_light_smoothing(uint32_t *p, int64_t count, int64_t width)
{
    int64_t i;
    if (!smoothing_table_made) {
        int a;
        for (a = 0; a < 256; a++) {
            double x = a / 255.0, y = 1.0, base = x;
            int k;
            /* x ** (1 + LIGHT_SMOOTHING_POWER / 20) without the C runtime: x times a root found by bisection */
            double lo = 0.0, hi = 1.0;
            for (k = 0; k < 40; k++) { /* r with r ** 20 == x ** LIGHT_SMOOTHING_POWER */
                double mid = (lo + hi) / 2.0, m = 1.0, t = 1.0;
                int e;
                for (e = 0; e < 20; e++)
                    m *= mid;
                for (e = 0; e < LIGHT_SMOOTHING_POWER; e++)
                    t *= base;
                if (m < t)
                    lo = mid;
                else
                    hi = mid;
            }
            y = x * lo;
            smoothing_table[a] = (uint8_t)(y * 255.0 + 0.5);
        }
        smoothing_table[255] = 255;
        smoothing_table_made = 1;
    }
    /* chosen first, written after: the alphas compared are the ones drawn */
    for (i = 0; i < count; i++) {
        uint32_t v = p[i], a = v >> 24;
        if (thin_px[i] != 1 || a == 0 || a == 255)
            continue;
        if (lightness((uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v) < LIGHT_SMOOTHING_MIN_HLS)
            continue;
        if (more_opaque_beside(p, i, width, count))
            thin_px[i] = 2;
    }
    for (i = 0; i < count; i++) {
        if (thin_px[i] == 2)
            p[i] = ((uint32_t)smoothing_table[p[i] >> 24] << 24) | (p[i] & 0xffffffU);
    }
}
static uint32_t generation = 0;

typedef struct {
    double r, g, b;
    double mr, mg, mb; /* mapped (equal to r, g, b when kept) */
    double hrun, vrun, okl, chroma, oa, ob;
    int64_t count, slot, beside_light, on_light;
    int64_t at_light; /* its pixels right beside a light surface (on_light: those not beside the main background too) */
    uint64_t touches; /* candidates right beside its pixels (all when not surveyed) */
    double light_okl; /* the lightest light surface it lies inside (on_light) */
    double ir, ig, ib; /* mapped as an island would (ink mode, inside a light surface) */
    int surface, line, long_line, mapped;
} Anchor;

static Anchor anchors[MAX_CANDIDATES];
static int anchor_count;
static uint32_t light_bits; /* ink mode: anchors that are light surfaces turned dark */
static uint32_t main_bit; /* ink mode: the kept main background (anchor 0), when there is one */
static uint32_t kept_text_bits; /* ink mode: light text drawn as it is on a light surface that turns dark too (see find_anchors) */
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
/* The lighter, readable text of the same hue that candidate k smooths (blue syntax for its navy
 * fringe), or -1. */
static int readable_partner(int k)
{
    const Anchor *c = &anchors[k];
    int j;
    for (j = 0; j < anchor_count; j++) {
        const Anchor *o = &anchors[j];
        if (j == k || o->surface || o->long_line || o->okl < INK_MAX_OKL || o->okl <= c->okl || o->chroma < INK_CHROMA)
            continue;
        if (c->touches != ~(uint64_t)0 && !((c->touches >> j) & 1U))
            continue; /* smoothing touches the text it smooths (Export Profiles' navy names are no smoothing of its blue boxes) */
        if ((c->oa * o->oa + c->ob * o->ob) / (c->chroma * o->chroma) >= SAME_HUE_COS)
            return j;
    }
    return -1;
}

static int smoothing_of_readable(int k)
{
    const Anchor *c = &anchors[k];
    int j;
    for (j = 0; j < anchor_count; j++) {
        const Anchor *o = &anchors[j];
        double dot;
        if (j == k || o->surface || o->long_line || o->okl < INK_MAX_OKL || o->okl <= c->okl || o->chroma < INK_CHROMA)
            continue;
        if (c->touches != ~(uint64_t)0 && !((c->touches >> j) & 1U))
            continue; /* smoothing touches the text it smooths (Export Profiles' navy names are no smoothing of its blue boxes) */
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
        double t, ee, res;
        if (j == k || o->surface || o->long_line || o->okl <= c->okl || o->chroma < INK_CHROMA)
            continue;
        if (c->touches != ~(uint64_t)0 && !((c->touches >> j) & 1U))
            continue; /* smoothing touches the text it smooths: the Output panel's dark gray lines, near enough
                       * to a blend of the paper and its red error lines by the fit below, lie apart from them
                       * (kept dark, they could not be read whenever an error was shown) */
        res = blend_fit(c->r, c->g, c->b, paper, o, &t, &ee); /* first: the comparison reads ee */
        if (res <= LOCAL_BLEND_TOLERANCE * LOCAL_BLEND_TOLERANCE * ee && t > 0.03 && t < 0.97)
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
    if (mode == ANCHORS_ALL && keep_tint > 0.0) {
        /* Content (the glyph canvas): a clearly colored mark of middle lightness or lighter (yellow or
         * orange outlines, red nodes, blue labels) reads on dark as drawn; inverted, a yellow outline
         * turned dark olive on the dark canvas and looked thin and jagged. Muted fills still turn. */
        double l, chroma;
        oklab_of(rgb, &l, &chroma);
        if (chroma >= CONTENT_KEEP_CHROMA && l >= CONTENT_KEEP_MIN_OKL)
            return rgb;
    }
    return mapped_one(rgb, dark_l, light_l, keep_tint);
}

/* A list's rows on a paper dark already (a list dark by its stylesheet): a gray clearly darker than the paper is
 * ink drawn for a light list, black on what is now dark (Generate Instance's "Ag" beside each style, the
 * sample of the font in the Glyph window's bar: the owner, 2026-11-25). Too rare to be an anchor, it was left
 * as drawn, dark on dark. It is taken for black ink over the paper, as much of it as it is darker, and comes
 * out as that much of light text over the paper. Returns 0 where that does not hold. */
#define DARK_INK_PAPER_HLS 0.3 /* the paper: this dark at most */
#define DARK_INK_MIN_COVER 0.3 /* less ink than this is a shade of the paper (a field's rounded corner) */
#define DARK_INK_SPREAD 30
static int dark_list_ink(uint32_t rgb, double dark_l, double light_l, uint32_t *out)
{
    const Anchor *paper;
    uint8_t px[3];
    double k = 0.0, light[3];
    uint32_t text;
    int ch;
    if (!mode_list || anchor_count < 1 || !anchors[0].surface || anchors[0].mapped)
        return 0;
    paper = &anchors[0];
    if (lightness((uint8_t)paper->r, (uint8_t)paper->g, (uint8_t)paper->b) > DARK_INK_PAPER_HLS)
        return 0;
    px[2] = (uint8_t)(rgb >> 16);
    px[1] = (uint8_t)(rgb >> 8);
    px[0] = (uint8_t)rgb;
    if (spread_of(px) > DARK_INK_SPREAD)
        return 0;
    {
        double pc[3], cover;
        pc[0] = paper->r; pc[1] = paper->g; pc[2] = paper->b;
        for (ch = 0; ch < 3; ch++) {
            double c = (double)((rgb >> (16 - 8 * ch)) & 255);
            if (c >= pc[ch] || pc[ch] <= 0.0)
                return 0; /* not darker than the paper */
            cover = (pc[ch] - c) / pc[ch];
            k += cover / 3.0;
        }
    }
    if (k < DARK_INK_MIN_COVER)
        return 0;
    text = mapped_one(0x000000U, dark_l, light_l, 0.0); /* black ink as it turns: the light of text */
    light[0] = (double)((text >> 16) & 255);
    light[1] = (double)((text >> 8) & 255);
    light[2] = (double)(text & 255);
    *out = pack(paper->r + k * (light[0] - paper->r), paper->g + k * (light[1] - paper->g),
                paper->b + k * (light[2] - paper->b));
    return 1;
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
static int light_surface_candidate(const Anchor *a);

static int is_blend(int k, int n)
{
    const Anchor *c = &anchors[k];
    int i, j;
    uint64_t surfaces = 0, reach = c->touches, seen = (uint64_t)1 << k;
    if (c->surface || c->long_line)
        return 0;
    for (i = 0; i < n; i++)
        surfaces |= anchors[i].surface ? (uint64_t)1 << i : 0U;
    /* what it reaches: the candidates it touches, and those the text-like ones among them touch, in turn */
    for (i = 0; i < n && c->touches != ~(uint64_t)0; i++) {
        if (((reach >> i) & 1U) && !((seen >> i) & 1U) && !anchors[i].surface) {
            seen |= (uint64_t)1 << i;
            reach |= anchors[i].touches;
            i = -1; /* again, with what it added */
        }
    }
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
            if (c->touches != ~(uint64_t)0 && !((c->touches >> i) & 1U) && !((c->touches >> j) & 1U))
                continue; /* a blend touches one of its ends at least (text fringes chain, but touch the paper) */
            if (c->touches != ~(uint64_t)0 && !((c->touches >> i) & 1U) && c->count > ink->count)
                continue; /* away from the surface and more frequent than the other end: a color of its own
                           * (a check box's blue, between white and its own darker edge) */
            if (ink->surface && !((c->touches >> j) & 1U))
                continue; /* a surface's edge touches it: gray text on a dark row lies between it and a white surface
                             * too (text fringes chain through each other, so text ink needs no touch) */
            /* A light surface that turns dark beside what stays (Preview Features' list, painted dark by
             * FontLab but for the near-white row under the pointer): colors of the dark rows fitted lines
             * to that row's colors, and dropped, they were redrawn as blends with those colors as they turn
             * dark: dark on dark. Three cases, each a color that lies elsewhere than the blend it fitted: */
            if (c->touches != ~(uint64_t)0 && light_surface_candidate(s)) {
                if (ink->surface && !light_surface_candidate(ink) && !((reach >> i) & 1U))
                    continue; /* the dark gray rings (#4f4f4f), on the line from the row to the dark base: they
                               * touch the base only, and nothing that touches them leads to the row (a smoothed
                               * edge two pixels wide reaches its surface through its other shade) */
                if (!ink->surface && !((ink->touches >> i) & 1U) && (ink->touches & surfaces)
                    && (double)c->at_light < ON_LIGHT_SHARE * (double)c->count)
                    continue; /* the light text (#dbdbdb), on the line from the row to the text's own yellowish
                               * fringe: that fringe lies only on the dark rows, and so does most of the text
                               * (a surface's edge smoothed in two shades lies all along it) */
            } else if (c->touches != ~(uint64_t)0 && !ink->surface && !((ink->touches >> i) & 1U) && !((reach >> j) & 1U)
                       && (double)ink->on_light >= ON_LIGHT_SHARE * (double)ink->count)
                continue; /* the rings again, on the line from the dark base to a pale fringe of the row's text:
                           * that fringe lies inside the row, and nothing that touches the rings leads to it */
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
                double t, ee, res;
                if (j == i || j == k || text->surface || text->long_line || text->okl <= c->okl
                    || c->count > 2 * text->count || !((c->touches >> j) & 1U))
                    continue; /* a fringe is rarer than the text it smooths, and beside it */
                res = blend_fit(c->r, c->g, c->b, s, text, &t, &ee); /* first: the comparison reads ee */
                if (res <= LOCAL_BLEND_TOLERANCE * LOCAL_BLEND_TOLERANCE * ee && t > 0.03 && t < 0.97)
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
    if (!a->surface || a->count < LIGHT_SURFACE_MIN_COUNT)
        return 0; /* (a few light letters are no surface: the Font window's script icons, white letters on dark
                   * tiles, turned the tiles light around their letters, the owner, 2026-11-25) */
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
        if (light >= 0)
            anchors[c].at_light++;
        if (light >= 0 && !main) {
            anchors[c].on_light++;
            if (anchors[light].okl > anchors[c].light_okl)
                anchors[c].light_okl = anchors[light].okl;
        }
    }
    for (k = 0; k < n; k++)
        h_anchor[anchors[k].slot] = -1;
}

/* ClearType's fringe of dark colored text on the dark paper (anchor 0): each of its channels lies
 * between the paper's and the text's, at a coverage of its own (the Output panel's dark red compiler
 * errors, about #8b0000, fringe in browns such as #340c00). The text it touches, mapped as ink (made
 * lighter in its own hue), or -1; cov: each channel's coverage, from the paper (0) to the text (1).
 * Mapped alone as dark ink, the fringe whose red is low turned light pink, lighter than the text it
 * smooths: light dots inside every letter (owner's report 155). */
#define CLEARTYPE_STEP 24.0 /* levels: a channel the text moves this far from the paper says its coverage */
#define CLEARTYPE_FLAT 10.0 /* levels: a channel that moves less stays this near the paper in a fringe */
#define CLEARTYPE_SLACK 0.08 /* a coverage this far past 0 or 1 still counts (rounding) */
static int cleartype_partner(int k, double cov[3])
{
    const Anchor *c = &anchors[k], *paper = &anchors[0];
    int j, best = -1;
    double best_far = 0.0, found[3];
    if (k == 0 || anchor_count < 3 || !paper->surface || paper->mapped || c->surface || c->long_line)
        return -1;
    for (j = 1; j < anchor_count; j++) { /* the farthest from the paper that fits: the text, not another fringe */
        const Anchor *o = &anchors[j];
        double cs[3], os[3], ps[3];
        double sum = 0.0, low = 2.0, high = -1.0, far;
        int ch, known = 0, fits = 1;
        cs[0] = c->r, cs[1] = c->g, cs[2] = c->b;
        os[0] = o->r, os[1] = o->g, os[2] = o->b;
        ps[0] = paper->r, ps[1] = paper->g, ps[2] = paper->b;
        if (j == k || o->surface || o->long_line || !o->mapped || o->chroma < INK_CHROMA || o->okl >= INK_MAX_OKL)
            continue; /* dark colored text the mapping made lighter (light text keeps its own smoothing rules) */
        if (c->touches != ~(uint64_t)0 && !((c->touches >> j) & 1U))
            continue; /* smoothing touches the text it smooths */
        for (ch = 0; ch < 3 && fits; ch++) {
            double step = os[ch] - ps[ch];
            if (step >= CLEARTYPE_STEP || step <= -CLEARTYPE_STEP) {
                double t = (cs[ch] - ps[ch]) / step;
                if (t < -CLEARTYPE_SLACK || t > 1.0 + CLEARTYPE_SLACK)
                    fits = 0;
                cov[ch] = t < 0.0 ? 0.0 : (t > 1.0 ? 1.0 : t);
                sum += cov[ch];
                known++;
                if (cov[ch] < low)
                    low = cov[ch];
                if (cov[ch] > high)
                    high = cov[ch];
            } else {
                cov[ch] = -1.0;
                if (cs[ch] - ps[ch] > CLEARTYPE_FLAT || ps[ch] - cs[ch] > CLEARTYPE_FLAT)
                    fits = 0;
            }
        }
        if (!fits || known < 2 || high < 0.05 || low > 0.95)
            continue; /* not between them, or the paper itself, or the text itself */
        far = (os[0] - ps[0]) * (os[0] - ps[0]) + (os[1] - ps[1]) * (os[1] - ps[1]) + (os[2] - ps[2]) * (os[2] - ps[2]);
        if (best >= 0 && far <= best_far)
            continue;
        for (ch = 0; ch < 3; ch++) /* (a channel the text leaves as the paper: the others' mean) */
            found[ch] = cov[ch] < 0.0 ? sum / (double)known : cov[ch];
        best = j;
        best_far = far;
    }
    if (best >= 0) {
        cov[0] = found[0];
        cov[1] = found[1];
        cov[2] = found[2];
    }
    return best;
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

/* Beside a light surface that turns dark (black text's ClearType fringes on a white header): its
 * light neighbors are that surface, not light text, so it is ink. */
static int touches_light_surface(int k)
{
    int j;
    if (anchors[k].touches == ~(uint64_t)0)
        return 0;
    for (j = 0; j < anchor_count; j++) {
        if (j != k && ((anchors[k].touches >> j) & 1U) && light_surface_candidate(&anchors[j]))
            return 1;
    }
    return 0;
}

/* Smoothing of kept light text (kept_text_bits) inside a light surface that turns dark (one of
 * `surfaces`): a color between that surface and the text becomes the same blend of the surface as it
 * turns and the text as drawn. Between the two only: what lies past the text (a gray ring's edge,
 * darker than the text) is no smoothing of it. */
static int kept_text_blend(double r, double g, double b, uint32_t surfaces, uint32_t *out)
{
    double best = -1.0, best_t = 0.0;
    int s, o, best_s = -1, best_o = -1;
    for (s = 0; s < anchor_count; s++) {
        const Anchor *a = &anchors[s];
        if (!((surfaces >> s) & 1U))
            continue;
        for (o = 0; o < anchor_count; o++) {
            const Anchor *text = &anchors[o];
            double er = text->r - a->r, eg = text->g - a->g, eb = text->b - a->b, ee = er * er + eg * eg + eb * eb;
            double dr = r - a->r, dg = g - a->g, db = b - a->b, t, res, tolerance;
            if (!((kept_text_bits >> o) & 1U) || ee <= 0.0)
                continue;
            t = (dr * er + dg * eg + db * eb) / ee; /* not clamped: past either end is no blend */
            if (t <= 0.0 || t > 1.0)
                continue;
            res = (dr - t * er) * (dr - t * er) + (dg - t * eg) * (dg - t * eg) + (db - t * eb) * (db - t * eb);
            tolerance = LOCAL_BLEND_TOLERANCE * LOCAL_BLEND_TOLERANCE * ee;
            if (tolerance < BLEND_MIN_TOLERANCE * BLEND_MIN_TOLERANCE)
                tolerance = BLEND_MIN_TOLERANCE * BLEND_MIN_TOLERANCE;
            if (res <= tolerance && (best < 0.0 || res < best)) {
                best = res;
                best_t = t;
                best_s = s;
                best_o = o;
            }
        }
    }
    if (best_s < 0)
        return 0;
    *out = pack(anchors[best_s].mr + best_t * (anchors[best_o].r - anchors[best_s].mr),
                anchors[best_s].mg + best_t * (anchors[best_o].g - anchors[best_s].mg),
                anchors[best_s].mb + best_t * (anchors[best_o].b - anchors[best_s].mb));
    return 1;
}

static void find_anchors(const uint32_t *p, int64_t count, int64_t width, int mode, double dark_l, double light_l,
                         double keep_tint, double main_default)
{
    int64_t i, total = 0, area = 0, last_slot = -1, min_count;
    int k, j, n;
    double main_l = main_default, share_of;
    int text_found = 0;
    uint32_t turned = 0; /* ink mode: text-like anchors turned with the light surface they lie in */
    /* Without a background of its own (a list painted on nothing: the font window's categories),
     * its dark gray text and headers were drawn for light paper: dim ink however close to the
     * dark gray beneath they come (kept, they nearly vanished and their smoothing turned dark). */
    int paper_found = 0;
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
        a->at_light = 0;
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
    if (anchor_count > 0 && anchors[0].surface && (double)anchors[0].count >= MAIN_MIN_AREA_SHARE * (double)area) {
        main_l = anchors[0].okl;
        paper_found = 1;
    } else
        share_of = (double)area;
    last_paper_found = paper_found;
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
        } else if (mode == ANCHORS_ALL || mode == ANCHORS_ICON || mode == ANCHORS_SUBPIXEL) {
            out = all_color(rgb, mode == ANCHORS_SUBPIXEL ? ANCHORS_ALL : mode, dark_l, light_l, keep_tint);
            a->mapped = out != rgb || mode != ANCHORS_ICON;
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
            turned |= 1U << j;
        } else if (!a->long_line && (double)a->count < BACKGROUND_SHARE * share_of && a->okl < INK_MAX_OKL
                   && (!a->surface || a->okl <= SURFACE_INK_MAX_OKL)
                   && (a->okl <= main_l - INK_BELOW_MAIN
                       || (a->chroma >= INK_CHROMA
                           && (touches_light_surface(j)
                               || ((double)a->beside_light < FRINGE_SHARE * (double)a->count && !smoothing_of_readable(j)))))) {
            out = mapped_one(rgb, dark_l, light_l, a->chroma >= INK_CHROMA ? 1.0 : 0.0);
            a->mapped = 1;
        } else if (!a->surface && !a->long_line && a->chroma < INK_CHROMA
                   && a->okl < (paper_found || !mode_list ? DIM_INK_MAX_OKL : DIM_INK_MAX_OKL_BARE)
                   && a->okl >= main_l + (paper_found ? DIM_INK_ABOVE_MAIN : -INK_BELOW_MAIN)
                   && (double)a->count < BACKGROUND_SHARE * (double)total
                   && (!paper_found || !fringe_of_lighter_color(j))) { /* (that test reads anchor 0 as the paper) */
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
        if (mode == ANCHORS_INK && !a->mapped && !a->surface && j > 0 && anchors[0].surface && !anchors[0].mapped) {
            /* Kept smoothing of colored text on the editor's dark paper (the navy of blue keys, frequent
             * enough to be an anchor across a whole editor): drawn as the blend of the paper and that
             * text, as it is when a repainted line alone has too few of it to be an anchor. */
            int o = readable_partner(j);
            if (o >= 0 && anchors[o].chroma >= DEFRINGE_CHROMA) {
                double t, ee, res = blend_fit(a->r, a->g, a->b, &anchors[0], &anchors[o], &t, &ee);
                if (ee > 0.0 && res <= LOCAL_BLEND_TOLERANCE * LOCAL_BLEND_TOLERANCE * ee && t > 0.0 && t < 1.0) {
                    out = pack(anchors[0].r + t * (anchors[o].r - anchors[0].r), anchors[0].g + t * (anchors[o].g - anchors[0].g),
                               anchors[0].b + t * (anchors[o].b - anchors[0].b));
                    a->mapped = 1;
                }
            }
        }
        a->mr = (double)((out >> 16) & 255);
        a->mg = (double)((out >> 8) & 255);
        a->mb = (double)(out & 255);
        h_anchor[a->slot] = (int8_t)j;
    }
    /* ClearType's fringes of dark colored text on the dark paper, mapped as ink above, drawn again
     * channel by channel from the paper and that text as they come out (cleartype_partner): as
     * ClearType draws the lighter text on the dark paper. After every anchor is mapped: the text may
     * come after its fringe. */
    for (j = 1; mode == ANCHORS_INK && j < anchor_count; j++) {
        Anchor *a = &anchors[j];
        double cov[3];
        int o;
        if (!a->mapped)
            continue;
        o = cleartype_partner(j, cov);
        if (o < 0)
            continue;
        a->mr = (double)clamp_byte(anchors[0].mr + cov[0] * (anchors[o].mr - anchors[0].mr));
        a->mg = (double)clamp_byte(anchors[0].mg + cov[1] * (anchors[o].mg - anchors[0].mg));
        a->mb = (double)clamp_byte(anchors[0].mb + cov[2] * (anchors[o].mb - anchors[0].mb));
    }
    /* Light text of the dark interface (gray, as light as the mapping's light end: the dark palette's
     * text color), kept as drawn, that FontLab also draws inside a surface it paints light itself
     * (Preview Features' row under the pointer: near-white, with that same light gray text, light on
     * light as painted). That surface turns dark and the text stays, so what lies between them there is
     * the text's smoothing (see kept_text_blend); turned as an island, it left the text's few full
     * pixels alone on the dark row, the letters in pieces. Not where a light surface holds dark text
     * (a dark text-like anchor with pixels inside one): its palest fringes lie on that same line, and
     * some are as frequent as text. */
    kept_text_bits = 0;
    for (j = 0; mode == ANCHORS_INK && light_bits && j < anchor_count; j++) {
        const Anchor *a = &anchors[j];
        uint8_t px[3];
        px[2] = (uint8_t)a->r;
        px[1] = (uint8_t)a->g;
        px[0] = (uint8_t)a->b;
        if (!a->mapped && !a->surface && !a->long_line && spread_of(px) <= KEPT_TEXT_MAX_SPREAD
            && a->okl >= light_l - KEPT_TEXT_NEAR_LIGHT && a->okl <= light_l + KEPT_TEXT_NEAR_LIGHT && a->on_light > 0
            && a->okl < a->light_okl)
            kept_text_bits |= 1U << j;
    }
    for (j = 0; kept_text_bits && j < anchor_count; j++) {
        if (!anchors[j].surface && anchors[j].on_light > 0 && anchors[j].okl < INK_MAX_OKL)
            kept_text_bits = 0;
    }
    for (j = 0; turned && j < anchor_count; j++) {
        Anchor *a = &anchors[j];
        uint32_t beside = 0, blend;
        int s, o, done = 0;
        if (!((turned >> j) & 1U))
            continue;
        for (s = 0; s < anchor_count; s++) /* the light surfaces it touches */
            beside |= ((light_bits >> s) & 1U) && ((a->touches >> s) & 1U) ? 1U << s : 0U;
        if (kept_text_bits && kept_text_blend(a->r, a->g, a->b, beside, &blend)) {
            a->mr = a->ir = (double)((blend >> 16) & 255);
            a->mg = a->ig = (double)((blend >> 8) & 255);
            a->mb = a->ib = (double)(blend & 255);
            continue;
        }
        /* The smoothed edge of a clearly colored surface kept as drawn (a checked mark's blue disk on
         * that row), frequent enough to be an anchor: the blend of the row as it turns and the disk, as
         * its rarer edge pixels are resolved (see resolve); turned alone, it outlined half the disk in
         * dark blue. */
        for (s = 0; s < anchor_count && !done; s++) {
            if (!((beside >> s) & 1U))
                continue;
            for (o = 0; o < anchor_count && !done; o++) {
                const Anchor *k = &anchors[o];
                double t, ee, res;
                uint8_t px[3];
                px[2] = (uint8_t)k->r;
                px[1] = (uint8_t)k->g;
                px[0] = (uint8_t)k->b;
                if (o == j || !k->surface || k->mapped || spread_of(px) <= LINEAR_SPREAD || !((a->touches >> o) & 1U))
                    continue;
                res = blend_fit(a->r, a->g, a->b, &anchors[s], k, &t, &ee); /* first: the comparison reads ee */
                if (ee > 0.0 && res <= BLEND_ANCHOR_TOLERANCE * BLEND_ANCHOR_TOLERANCE && t > 0.0 && t < 1.0) {
                    a->mr = a->ir = anchors[s].mr + t * (k->r - anchors[s].mr);
                    a->mg = a->ig = anchors[s].mg + t * (k->g - anchors[s].mg);
                    a->mb = a->ib = anchors[s].mb + t * (k->b - anchors[s].mb);
                    done = 1;
                }
            }
        }
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

/* Content on its paper (a glyph canvas): a colored pixel that is no anchor is taken for ink over the main
 * paper, as much of it as its distance from the paper says: the paper P, the pixel C = P + k (I - P), the ink
 * I where that line leaves the colors there are (a channel at 0 or 255), k the coverage. It comes out as the
 * paper as mapped plus k of the ink as content maps it (kept when clearly colored, turned over when not):
 * a red contour's smoothing is red at half strength over the dark canvas, as it was over the light one.
 * Before, each pixel was judged by its own color: a line's full pixels kept, light and red, its smoothing
 * turned over, dark, and every thin colored line came out as steps and dots (the owner, 2026-11-25:
 * "all color paths, contours and curves have this kind of jaggy edge"). Returns 0 where there is no light
 * main paper, or the pixel is no lighter mix of it (darker ink than any the paper could hold). */
#define PAPER_MIN_HLS 0.6 /* the main paper of a light canvas (a Font window cell's gray, b7b7b8, is 0.72) */
#define PAPER_MIN_COVER 0.04 /* less ink than this is the paper */
#define PAPER_FULL_COVER 0.7 /* a mark as FontLab draws it: this much of the pure ink */
static int paper_blend(uint32_t c, double dark_l, double light_l, double tint, uint32_t *out)
{
    const Anchor *paper;
    double pc[3], cc[3], ink[3], mapped[3], k = 0.0;
    uint32_t ink_rgb, ink_out;
    int ch;
    if (anchor_count < 1 || !anchors[0].surface || !anchors[0].mapped)
        return 0;
    paper = &anchors[0];
    if (lightness((uint8_t)paper->r, (uint8_t)paper->g, (uint8_t)paper->b) < PAPER_MIN_HLS)
        return 0;
    pc[0] = paper->r; pc[1] = paper->g; pc[2] = paper->b;
    cc[0] = (double)((c >> 16) & 255); cc[1] = (double)((c >> 8) & 255); cc[2] = (double)(c & 255);
    for (ch = 0; ch < 3; ch++) {
        double d = cc[ch] - pc[ch], need;
        if (d < 0.0)
            need = pc[ch] > 0.0 ? -d / pc[ch] : 1.0;
        else
            need = pc[ch] < 255.0 ? d / (255.0 - pc[ch]) : (d > 0.0 ? 1.0 : 0.0);
        if (need > k)
            k = need;
    }
    if (k > 1.0)
        k = 1.0;
    if (k < PAPER_MIN_COVER) {
        *out = pack(paper->mr, paper->mg, paper->mb);
        return 1;
    }
    for (ch = 0; ch < 3; ch++) {
        double v = pc[ch] + (cc[ch] - pc[ch]) / k;
        ink[ch] = v < 0.0 ? 0.0 : v > 255.0 ? 255.0 : v;
    }
    ink_rgb = pack(ink[0], ink[1], ink[2]);
    ink_out = all_color(ink_rgb, ANCHORS_ALL, dark_l, light_l, tint);
    {
        /* A line FontLab draws is seldom the full ink (its red is ff4646, 0.7 of pure red over the paper):
         * the mark as drawn, at PAPER_FULL_COVER, keeps the strength it has, and thinner smoothing fades
         * from it to the paper; past it, toward the pure ink. */
        double mark[3], from[3], to[3], w;
        uint32_t mark_out;
        for (ch = 0; ch < 3; ch++)
            mark[ch] = pc[ch] + PAPER_FULL_COVER * (ink[ch] - pc[ch]);
        mark_out = all_color(pack(mark[0], mark[1], mark[2]), ANCHORS_ALL, dark_l, light_l, tint);
        if (k <= PAPER_FULL_COVER) {
            w = k / PAPER_FULL_COVER;
            from[0] = paper->mr; from[1] = paper->mg; from[2] = paper->mb;
            to[0] = (double)((mark_out >> 16) & 255); to[1] = (double)((mark_out >> 8) & 255); to[2] = (double)(mark_out & 255);
        } else {
            w = (k - PAPER_FULL_COVER) / (1.0 - PAPER_FULL_COVER);
            from[0] = (double)((mark_out >> 16) & 255); from[1] = (double)((mark_out >> 8) & 255); from[2] = (double)(mark_out & 255);
            to[0] = (double)((ink_out >> 16) & 255); to[1] = (double)((ink_out >> 8) & 255); to[2] = (double)(ink_out & 255);
        }
        for (ch = 0; ch < 3; ch++)
            mapped[ch] = from[ch] + w * (to[ch] - from[ch]);
    }
    *out = pack(mapped[0], mapped[1], mapped[2]);
    return 1;
}

static uint32_t colored_anchor_bits; /* per call: anchors more colored than LINEAR_SPREAD (see resolve) */
#define KEPT_BLEND_SPREAD 40 /* a pixel this colored at least may be such an anchor's blend */

static uint32_t resolve(uint32_t c, int translucent, uint32_t mask, int mode, double dark_l, double light_l,
                        double keep_tint, double tint)
{
    uint32_t blend_out = 0;
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
    if (mode == ANCHORS_INK && dark_list_ink(c, dark_l, light_l, &blend_out))
        return blend_out; /* (before any pair: a pair of kept anchors explains it as drawn) */
    if (mode == ANCHORS_INK && (mask & light_bits) && !(mask & main_bit)
        && !lighter_than_light_surface(c, mask & light_bits)) { /* inside it, not at its edge */
        /* Beside a light surface that turns dark (a selected row, a white thumbnail), everything
         * turns as an island does: its rare marks (a digit, a glyph's gray edges) have no anchor
         * of their own, and pairs with far dark colors put them dark on the now dark surface. */
        uint8_t px[3];
        px[2] = (uint8_t)r;
        px[1] = (uint8_t)g;
        px[0] = (uint8_t)b;
        {
            /* the logo's smoothing toward the row: the blend of the row as it turns and the logo as drawn
             * (inverted alone, it ringed the logo) */
            uint32_t colored = 0;
            uint32_t blend;
            /* light text kept on such a row: its smoothing likewise, wherever it lies in the row (a thin
             * stem has no full pixel of the text's color near it) */
            if (kept_text_bits && kept_text_blend(r, g, b, mask & light_bits, &blend))
                return blend;
            for (j = 0; j < anchor_count; j++) {
                uint8_t q[3];
                q[2] = (uint8_t)anchors[j].r;
                q[1] = (uint8_t)anchors[j].g;
                q[0] = (uint8_t)anchors[j].b;
                if (((mask >> j) & 1U) && spread_of(q) > LINEAR_SPREAD)
                    colored |= 1U << j;
            }
            if (colored && best_pair(r, g, b, mask, mask, LOCAL_BLEND_TOLERANCE, &a_i, &b_i, &t)
                && (((colored >> a_i) & 1U) != ((colored >> b_i) & 1U))) {
                Anchor *a = &anchors[a_i], *o = &anchors[b_i];
                double ar = (colored >> a_i) & 1U ? a->r : a->ir, ag = (colored >> a_i) & 1U ? a->g : a->ig,
                       ab = (colored >> a_i) & 1U ? a->b : a->ib;
                double or_ = (colored >> b_i) & 1U ? o->r : o->ir, og = (colored >> b_i) & 1U ? o->g : o->ig,
                       ob = (colored >> b_i) & 1U ? o->b : o->ib;
                return pack(ar + t * (or_ - ar), ag + t * (og - ag), ab + t * (ob - ab));
            }
        }
        if (spread_of(px) > LINEAR_SPREAD)
            return c; /* clearly colored (a logo in a selected row of Export Profiles): as drawn, not inverted */
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
        if (spread_of(px) <= (tint > 0.0 ? TINTED_LINEAR_SPREAD : LINEAR_SPREAD)) {
            /* A blend with a strongly colored anchor, which the mapping keeps (red text on the Preview panel's
             * white): mapped alone, the smoothing went gray, a gray rim around the red letters (the owner,
             * 2026-11-25). Drawn as the blend of the two anchors as they come out. */
            if (keep_tint <= 0.0 && colored_anchor_bits && spread_of(px) > KEPT_BLEND_SPREAD /* (an island of the
                                     * interface, its ClearType grayed before: a canvas' ClearType colors are
                                     * anchors too, and its rulers' gray digits came out blue) */
                && best_pair(r, g, b, 0U, all, BLEND_TOLERANCE, &a_i, &b_i, &t)
                && (((colored_anchor_bits >> a_i) & 1U) || ((colored_anchor_bits >> b_i) & 1U))) {
                Anchor *a = &anchors[a_i], *o = &anchors[b_i];
                return pack(a->mr + t * (o->mr - a->mr), a->mg + t * (o->mg - a->mg), a->mb + t * (o->mb - a->mb));
            }
            return all_color(c, mode, dark_l, light_l, tint);
        }
    }
    if (mode == ANCHORS_ALL && tint > 0.0 && paper_blend(c, dark_l, light_l, tint, &blend_out))
        return blend_out; /* (before any pair: a line's color is seldom an anchor, and a far pair explained its
                           * smoothing no better than chance) */
    if (!(mask && best_pair(r, g, b, mask, mask, LOCAL_BLEND_TOLERANCE, &a_i, &b_i, &t))
        && !best_pair(r, g, b, 0U, all, BLEND_TOLERANCE, &a_i, &b_i, &t))
        return lone_color(c, mode, dark_l, light_l, tint);
    {
        Anchor *a = &anchors[a_i], *o = &anchors[b_i];
        double xr = r - (a->r + t * (o->r - a->r)), xg = g - (a->g + t * (o->g - a->g)), xb = b - (a->b + t * (o->b - a->b));
        if (!a->mapped && !o->mapped) {
            /* Colored syntax kept on an editor's dark paper (blue keys): ClearType's navy fringes between
             * the paper and the text become their plain blend, so the text keeps its weight. Gray text
             * keeps its fringes (blending those thinned it). */
            if (mode == ANCHORS_INK && ((mask >> a_i) & 1U) && ((mask >> b_i) & 1U) && (a_i == 0 || b_i == 0)
                && anchors[0].surface && (anchors[a_i == 0 ? b_i : a_i].chroma >= DEFRINGE_CHROMA))
                return pack(a->r + t * (o->r - a->r), a->g + t * (o->g - a->g), a->b + t * (o->b - a->b));
            return c;
        }
        return pack(a->mr + t * (o->mr - a->mr) + tint * xr, a->mg + t * (o->mg - a->mg) + tint * xg,
                    a->mb + t * (o->mb - a->mb) + tint * xb);
    }
}

/* ClearType puts colored fringes beside dark text strokes: a pixel this much lighter or darker
 * than a horizontal neighbor keeps no tint, even in content. Fainter lines (handles) keep theirs. */
#define FRINGE_STEP 0.3

/* left: the left neighbor as drawn (the loop has already mapped it in place: read mapped, a comb's
 * fill turned every slightly different pixel into a sharp edge, and gray). */
static int sharp_edge(const uint32_t *p, int64_t i, int64_t width, int64_t count, uint32_t left)
{
    const uint8_t *px = (const uint8_t *)&p[i];
    double l = lightness(px[2], px[1], px[0]);
    int64_t x = i % width;
    if (x > 0) {
        const uint8_t *q = (const uint8_t *)&left;
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

/* Content (islands that keep colors): light text on a colored surface it keeps, such as a selected
 * font cell's name on its blue header, stays as drawn: mapped with the white paper, it turned dark on
 * the blue, with light fringes. A light pixel qualifies when, walking each way past light pixels (the
 * text and its smoothing), a band comes within reach: a color the content keeps (all_color), strongly
 * saturated, of middle lightness, one hue on every side, and LIGHT_ON_COLOR_THICK pixels thick on
 * one side at least (between letters it is thin; a node's 1-px outline is thin on every side). Walking off the image (a partial
 * repaint's edge) neither proves nor disproves, but two sides must reach the band. near_band holds,
 * per pixel, which sides have a band pixel within reach, so most pixels are rejected at once. */
#define LIGHT_ON_COLOR_TEST_HLS 0.5
#define LIGHT_ON_COLOR_REACH 10
#define LIGHT_ON_COLOR_SPREAD 100 /* the band: strongly colored (ClearType's smoothing on it is less so) */
#define LIGHT_ON_COLOR_SMOOTHING_SPREAD 40
#define LIGHT_ON_COLOR_SMOOTHING_HLS 0.3
#define LIGHT_ON_COLOR_MIN_HLS 0.2
#define LIGHT_ON_COLOR_MAX_HLS 0.62
#define LIGHT_ON_COLOR_THICK 3
#define LIGHT_ON_COLOR_PAPER_NEAR 6 /* per channel: a pixel this near a paper's color is that paper */
#define LIGHT_ON_COLOR_SAME_HUE_COS2 0.64 /* cos 0.8, squared */
#define NEAR_BAND 0x10 /* the pixel is a band pixel; bits 1, 2, 4, 8: one within reach left, right, up, down */

static uint8_t near_band[MAX_INDEXED];

static int band_plain; /* set for an island of the interface: a band may be lighter, and nothing is "kept" */
#define LIGHT_ON_COLOR_MAX_HLS_PLAIN 0.8 /* (the Fonts panel's disc, 7ebcff, is 0.75) */

static int band_pixel(const uint8_t *q)
{
    double lq, l, chroma;
    if (q[3] < ANCHOR_MIN_ALPHA || spread_of(q) < LIGHT_ON_COLOR_SPREAD)
        return 0;
    lq = lightness(q[2], q[1], q[0]);
    if (band_plain)
        return lq >= LIGHT_ON_COLOR_MIN_HLS && lq <= LIGHT_ON_COLOR_MAX_HLS_PLAIN;
    if (lq < LIGHT_ON_COLOR_MIN_HLS || lq > LIGHT_ON_COLOR_MAX_HLS)
        return 0;
    oklab_of(((uint32_t)q[2] << 16) | ((uint32_t)q[1] << 8) | q[0], &l, &chroma);
    return chroma >= CONTENT_KEEP_CHROMA && l >= CONTENT_KEEP_MIN_OKL; /* kept as drawn by all_color */
}

static int same_hue(const uint8_t *q, double hr, double hg, double hb)
{
    double m = (q[0] + q[1] + q[2]) / 3.0, vr = q[2] - m, vg = q[1] - m, vb = q[0] - m;
    double dot = vr * hr + vg * hg + vb * hb;
    return dot > 0.0 && dot * dot >= LIGHT_ON_COLOR_SAME_HUE_COS2 * (vr * vr + vg * vg + vb * vb) * (hr * hr + hg * hg + hb * hb);
}

/* Fill near_band for the image; returns 0 when there is no band pixel at all. */
static int find_bands(const uint32_t *p, int64_t count, int64_t width)
{
    int64_t i, x, y, rows = count / width, any = 0;
    uint32_t last = 0;
    uint8_t last_band = 0;
    int have = 0;
    for (i = 0; i < count; i++) { /* (a run of one color answers once: OKLab's roots for each pixel of a Font
                                   * window's selected cells took most of its 110 ms) */
        if (!have || p[i] != last) {
            last = p[i];
            last_band = band_pixel((const uint8_t *)&p[i]) ? NEAR_BAND : 0;
            have = 1;
        }
        near_band[i] = last_band;
        any |= near_band[i];
    }
    if (!any)
        return 0;
    for (y = 0; y < rows; y++) {
        int64_t last = -1000;
        for (x = 0; x < width; x++) { /* a band pixel to the left */
            if (x - last <= LIGHT_ON_COLOR_REACH)
                near_band[y * width + x] |= 1;
            if (near_band[y * width + x] & NEAR_BAND)
                last = x;
        }
        last = 1000000000;
        for (x = width - 1; x >= 0; x--) { /* to the right */
            if (last - x <= LIGHT_ON_COLOR_REACH)
                near_band[y * width + x] |= 2;
            if (near_band[y * width + x] & NEAR_BAND)
                last = x;
        }
    }
    for (x = 0; x < width; x++) {
        int64_t last = -1000;
        for (y = 0; y < rows; y++) { /* above */
            if (y - last <= LIGHT_ON_COLOR_REACH)
                near_band[y * width + x] |= 4;
            if (near_band[y * width + x] & NEAR_BAND)
                last = y;
        }
        last = 1000000000;
        for (y = rows - 1; y >= 0; y--) { /* below */
            if (last - y <= LIGHT_ON_COLOR_REACH)
                near_band[y * width + x] |= 8;
            if (near_band[y * width + x] & NEAR_BAND)
                last = y;
        }
    }
    return 1;
}

static int near_rgb(uint32_t a, uint32_t b, int tolerance);

#define BAND_BLEND_RESIDUE 14 /* per channel: how far from the line between band and paper a blend may lie */
static int band_paper_blend(const uint8_t *v, uint32_t band)
{
    int a, ch;
    double b[3], c[3];
    b[0] = (double)((band >> 16) & 255U); b[1] = (double)((band >> 8) & 255U); b[2] = (double)(band & 255U);
    c[0] = v[2]; c[1] = v[1]; c[2] = v[0];
    for (a = 0; a < anchor_count; a++) {
        double w[3], dot = 0.0, len = 0.0, t, worst = 0.0;
        if (!anchors[a].surface || !anchors[a].mapped)
            continue;
        w[0] = anchors[a].r; w[1] = anchors[a].g; w[2] = anchors[a].b;
        for (ch = 0; ch < 3; ch++) {
            dot += (c[ch] - b[ch]) * (w[ch] - b[ch]);
            len += (w[ch] - b[ch]) * (w[ch] - b[ch]);
        }
        if (len <= 0.0)
            continue;
        t = dot / len;
        if (t <= 0.0 || t > 1.05)
            continue;
        for (ch = 0; ch < 3; ch++) {
            double d = c[ch] - (b[ch] + t * (w[ch] - b[ch]));
            d = d < 0.0 ? -d : d;
            worst = d > worst ? d : worst;
        }
        if (worst <= BAND_BLEND_RESIDUE)
            return 1;
    }
    return 0;
}

static int light_on_kept_color(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    int64_t x, y, rows;
    int dir, have = 0, hits = 0, thick = 0, sides;
    uint32_t band = 0;
    double hr = 0.0, hg = 0.0, hb = 0.0;
    const uint8_t *self = (const uint8_t *)&p[i];
    if (width <= 0 || lightness(self[2], self[1], self[0]) < LIGHT_ON_COLOR_TEST_HLS)
        return 0;
    sides = (near_band[i] & 1) + ((near_band[i] >> 1) & 1) + ((near_band[i] >> 2) & 1) + ((near_band[i] >> 3) & 1);
    if (sides < 2)
        return 0; /* the quick test: no band within reach on two sides */
    {
        /* The paper itself is no text: the counter of a colored letter (an overlaid font's red O in a Font
         * window cell) has the letter's color on every side, and kept as drawn, it stood light in the dark
         * cell (the owner, 2026-11-25). Text on a colored band is lighter than any paper around. */
        int a;
        uint32_t own = p[i] & 0xffffffU;
        for (a = 0; a < anchor_count; a++) {
            if (anchors[a].surface && anchors[a].mapped
                && near_rgb(pack(anchors[a].r, anchors[a].g, anchors[a].b), own, LIGHT_ON_COLOR_PAPER_NEAR))
                return 0;
        }
    }
    x = i % width;
    y = i / width;
    rows = count / width;
    for (dir = 0; dir < 4; dir++) {
        int64_t sx = dir == 0 ? 1 : dir == 1 ? -1 : 0, sy = dir == 2 ? 1 : dir == 3 ? -1 : 0, k;
        int found = 0;
        for (k = 1; k <= LIGHT_ON_COLOR_REACH && !found; k++) {
            const uint8_t *q;
            double lq;
            int64_t xx = x + sx * k, yy = y + sy * k;
            if (xx < 0 || xx >= width || yy < 0 || yy >= rows) {
                found = 2; /* off the image: undecided */
                break;
            }
            q = (const uint8_t *)&p[yy * width + xx];
            if (q[3] < ANCHOR_MIN_ALPHA)
                return 0;
            lq = lightness(q[2], q[1], q[0]);
            if (near_band[yy * width + xx] & NEAR_BAND) { /* (band_pixel, as find_bands found it) */
                int64_t t;
                double m = (q[0] + q[1] + q[2]) / 3.0;
                if (have && !same_hue(q, hr, hg, hb))
                    return 0;
                if (!have) {
                    hr = q[2] - m;
                    hg = q[1] - m;
                    hb = q[0] - m;
                    have = 1;
                    band = *(const uint32_t *)q & 0xffffffU;
                }
                for (t = 1; t < LIGHT_ON_COLOR_THICK; t++) { /* a band, not an outline */
                    const uint8_t *r;
                    int64_t tx = xx + sx * t, ty = yy + sy * t;
                    if (tx < 0 || tx >= width || ty < 0 || ty >= rows)
                        break;
                    r = (const uint8_t *)&p[ty * width + tx];
                    if (!(near_band[ty * width + tx] & NEAR_BAND) || !same_hue(r, hr, hg, hb))
                        break;
                }
                thick += t == LIGHT_ON_COLOR_THICK; /* between letters it is thin; above or below text, thick */
                found = 1;
                hits++;
            } else if (lq < LIGHT_ON_COLOR_TEST_HLS
                       && (spread_of(q) < LIGHT_ON_COLOR_SMOOTHING_SPREAD || lq < LIGHT_ON_COLOR_SMOOTHING_HLS)) {
                return 0; /* dark or gray: not on the colored surface */
            } /* else light (the text) or the text's colored smoothing: walked past */
        }
        if (!found)
            return 0;
    }
    if (hits < 2 || thick < 1)
        return 0;
    /* Nor is a blend of the band and a paper text: the smoothing between a thin colored line and the paper (an
     * overlaid font's red outlines in a Font window cell, crossed slantwise where they curve) and the paper
     * between two colored letters (red text on the Preview panel's white, where the Q's tail meets its bowl)
     * were kept light (the owner, 2026-11-25). Light text lies between the band and its own light color. */
    return !band_paper_blend(self, band);
}

/* Ink mode: a white pixel with only colored pixels around it, besides white ones (a check box's tick
 * on its blue box, a white glyph on a colored button), is drawn right for any interface and stays;
 * the same white elsewhere (an unticked box, a white row) is mapped. */
#define WHITE_MARK_REACH 1
#define BOX_MAX_RUN 16
#define WHITE_MARK_SAME_HUE_COS2 0.64 /* cos 0.8, squared */
#define WHITE_MARK_CONTROL_HLS 0.45 /* a control's color is of middle lightness or lighter */
#define WHITE_MARK_INK_REACH 3 /* px past the first colored pixel met: where a stroke's own color is */
#define WHITE_MARK_ENCLOSED 6 /* px: the control's color around a mark, each way */
#define WHITE_MARK_PURE_SPREAD 20 /* a white mark is pure white; its smoothing toward the box is colored */
#define WHITE_MARK_TEST_HLS 0.6 /* pixels this light are tested: the mark, and its smoothing */
#define WHITE_MARK_SPREAD 25 /* colored enough for a control (a pale tinted row, spread 22, is not) */
#define WHITE_MARK_STEP 0.05 /* the control is darker than the mark and its smoothing by this much (HLS): a flat light
                              * colored area (a selected flag swatch, dfbbbf) is no mark on a control of its own color */

static int white_run(const uint32_t *p, int64_t i, int64_t step, int64_t limit, int64_t width, int horizontal);

static int white_on_colored(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    int64_t x, y, dx, dy, rows;
    int colored = 0;
    double hr = 0.0, hg = 0.0, hb = 0.0, own;
    if (width <= 0)
        return 0;
    own = lightness((uint8_t)(p[i] >> 16), (uint8_t)(p[i] >> 8), (uint8_t)p[i]);
    if (white_run(p, i, -1, count, width, 1) + white_run(p, i, 1, count, width, 1) + 1 > BOX_MAX_RUN
        || white_run(p, i, -width, count, width, 0) + white_run(p, i, width, count, width, 0) + 1 > BOX_MAX_RUN)
        return 0; /* a mark is small (a tick in its box): a white row beside text's light fringes is no mark */
    x = i % width;
    y = i / width;
    rows = count / width;
    { /* enclosed: walking each way past the mark's white, the control's color comes within reach (a
       * tick in its box; white inside a letter beside light fringes is open on some side) */
        int dir;
        for (dir = 0; dir < 4; dir++) {
            int64_t sx = dir == 0 ? 1 : dir == 1 ? -1 : 0, sy = dir == 2 ? 1 : dir == 3 ? -1 : 0, k;
            int found = 0;
            for (k = 1; k <= WHITE_MARK_ENCLOSED && !found; k++) {
                const uint8_t *q;
                int64_t xx = x + sx * k, yy = y + sy * k;
                if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                    return 0;
                q = (const uint8_t *)&p[yy * width + xx];
                if (q[3] >= ANCHOR_MIN_ALPHA && lightness(q[2], q[1], q[0]) >= WHITE_HLS && spread_of(q) <= WHITE_MARK_PURE_SPREAD)
                    continue;
                if (q[3] < ANCHOR_MIN_ALPHA || spread_of(q) < WHITE_MARK_SPREAD || lightness(q[2], q[1], q[0]) < WHITE_MARK_CONTROL_HLS
                    || lightness(q[2], q[1], q[0]) > own - WHITE_MARK_STEP)
                    return 0;
                found = 1;
                { /* A mark stands in a control, a body of color. The white inside a colored letter (the counter
                   * of an a, an A's triangle: Overlay Fonts' sample on its white row) has strokes around it:
                   * where the color met, within a step or two (past its smoothing), is one of the picture's
                   * anchors and no surface, it is ink, and the white is the row's. Kept as a mark, it stood
                   * white in the dark row (the owner, 2026-11-25). */
                    int64_t t;
                    for (t = 0; t < WHITE_MARK_INK_REACH; t++) {
                        int64_t tx = xx + sx * t, ty = yy + sy * t;
                        uint32_t rgb;
                        int a;
                        if (tx < 0 || tx >= width || ty < 0 || ty >= rows)
                            break;
                        rgb = p[ty * width + tx] & 0xffffffU;
                        for (a = 0; a < anchor_count; a++) {
                            if (pack(anchors[a].r, anchors[a].g, anchors[a].b) == rgb) {
                                if (!anchors[a].surface)
                                    return 0;
                                t = WHITE_MARK_INK_REACH;
                                break;
                            }
                        }
                    }
                }
            }
            if (!found)
                return 0;
        }
    }
    for (dy = -WHITE_MARK_REACH; dy <= WHITE_MARK_REACH; dy++) {
        for (dx = -WHITE_MARK_REACH; dx <= WHITE_MARK_REACH; dx++) {
            const uint8_t *q;
            if (x + dx < 0 || x + dx >= width || y + dy < 0 || y + dy >= rows)
                continue;
            q = (const uint8_t *)&p[(y + dy) * width + x + dx];
            if (q[3] >= ANCHOR_MIN_ALPHA && lightness(q[2], q[1], q[0]) >= WHITE_HLS && spread_of(q) <= WHITE_MARK_PURE_SPREAD)
                continue; /* the mark itself: pure white (a pale tinted row, e9f0ff, is no mark) */
            if (q[3] < ANCHOR_MIN_ALPHA || spread_of(q) < WHITE_MARK_SPREAD
                || lightness(q[2], q[1], q[0]) < WHITE_MARK_CONTROL_HLS)
                return 0; /* beside nothing, gray, or dark (black text's ClearType fringes): no colored control */
            if (lightness(q[2], q[1], q[0]) > own - WHITE_MARK_STEP && (p[i] & 0xffffffU) != (*(const uint32_t *)q & 0xffffffU))
                return 0; /* as light as the pixel and another color: no control around a mark */
            {
                /* one control color (its blue and lighter blue smoothing): ClearType's fringes of black
                 * text on a white row come in opposite hues, and the white between them is no mark */
                double m = (q[0] + q[1] + q[2]) / 3.0, vr = q[2] - m, vg = q[1] - m, vb = q[0] - m;
                if (!colored) {
                    hr = vr;
                    hg = vg;
                    hb = vb;
                } else {
                    double dot = vr * hr + vg * hg + vb * hb;
                    double n1 = vr * vr + vg * vg + vb * vb, n2 = hr * hr + hg * hg + hb * hb;
                    if (dot <= 0.0 || dot * dot < WHITE_MARK_SAME_HUE_COS2 * n1 * n2)
                        return 0;
                }
            }
            colored = 1;
        }
    }
    return colored;
}

/* Ink mode: light text on a gray badge (Anchors & Pins' coordinates: white ClearType digits on a
 * mid-gray pill, #a0a2a4, in a white list). The digits' white is the list's white, one anchor, mapped
 * dark with the list: dark digits on the badge, their light fringes around them (unreadable). A light
 * pixel enclosed by one badge gray, each way within reach, past nothing but light pixels (the
 * text and its fringes), and thin one way at least (a stroke; the white inside a gray-framed box is as
 * wide as it is tall), is text on the badge: drawn from the badge as it comes out toward white, at
 * the pixel's own coverage per channel (kept, the badge's text is as drawn; turned dark, its text stays
 * light, as on FontAudit's badges). A badge's gray is an anchor solid one way at least (a badge's runs;
 * a gray letter's strokes are short), of low color (white_on_colored takes colored controls), darker
 * than the text, and of middle lightness (a dark gray tile behind white letters too). */
#define BADGE_REACH 10 /* px: the badge's gray within this many pixels up and down (a capital's stem is 8 at the size of a cell's caption), */
#define BADGE_REACH_ACROSS 48 /* and across (a line of digits' bars touch through their fringes) */
#define BADGE_MIN_HLS 0.3 /* a badge's gray is no darker (black text's counters are no badge text) */
#define BADGE_TEXT_STEP 0.01 /* the text (its fringes too) is lighter than its badge by this much (HLS) */
#define BADGE_LIGHT_HLS 0.5 /* what the walk crosses: the text and its fringes, this light at least */
#define BADGE_STROKE 3 /* px: text on a badge is this thin one way at least (across or down), */
#define BADGE_SAME_HLS 0.1 /* its stroke being what is about as light as the pixel (its fringes end it) */
#define BADGE_MAX_HLS 0.85 /* nor lighter (a light row is no badge) */
#define BADGE_MAX_COLORS 8
#define BADGE_SAME_GRAY 12 /* per channel: two badge grays this near are one badge seen over two grounds */
#define BADGE_MARK 16 /* white_mark: BADGE_MARK + the badge's index, for its text */

static uint32_t badge_colors[BADGE_MAX_COLORS], badge_out[BADGE_MAX_COLORS], badge_dark[BADGE_MAX_COLORS];
static int64_t badge_text_count[BADGE_MAX_COLORS];
static double badge_hls[BADGE_MAX_COLORS];
static int badge_count;
/* On a canvas (content), an anchor's pill is translucent: over a ground that changes under it (the baseline's
 * band, a guide) its warm gray takes a step or two, and only its frequent shades are candidates; the canvas'
 * own light grays (0.78 to 0.85) filled the BADGE_MAX_COLORS before the pill's turn; and the lines under it (a
 * guide, the side lines, a contour) ended the walks as dark. A walk then met another gray, a line, or nothing,
 * and the name's letters came out dark on one side of the line or all along (the owner, 2026-11-25). So on a
 * canvas a badge is no lighter than BADGE_PILL_MAX_HLS, a tinted badge's shades within BADGE_SHADE per channel
 * are it, and a walk crosses a thin line to a tinted badge (BADGE_CROSS_LINE). Lists (ink) keep the plain
 * rules: their badges are flat. Checked on every capture of the session's probes: only canvases with pills
 * change. */
#define BADGE_PILL_MAX_HLS 0.8
#define BADGE_SHADE 12 /* (the pill over the canvas' white above the baseline and its band below: 10 per channel
                        * apart, and the letters below the line came out dark: the owner, November 25) */
#define BADGE_PILL_MIN_RUN 2.0 /* a pill's gray runs both ways: a dashed sidebearing line, one pixel wide, was taken
                                * for a pill, and its shades took in the names' fringes */
#define BADGE_TINT 3 /* red above blue by this much at least: a tinted (warm) gray */
#define BADGE_PILL_STROKE 5 /* px: on a pill, a name drawn pale over a glyph's fill has its smoothing within the
                             * stroke's lightness, and an "n"'s stems ran 4 pixels across (the owner, 2026-11-25:
                             * "uni" dark in every name over the glyph) */
#define BADGE_CROSS_LINE 2 /* px: on a canvas, a walk crosses a dark line this thin (a guide, the side lines, a
                            * contour, drawn under a translucent pill) when the badge it reaches is a tinted
                            * one: FontLab's pill holds light names only, and black text's strokes on a
                            * neutral badge still end a walk (its counters are no light text) */
static int badge_pill;

static uint32_t resolve(uint32_t c, int translucent, uint32_t mask, int mode, double dark_l, double light_l,
                        double keep_tint, double tint);

/* The frequent colors a badge could be of (see above), once per call, each with the color it comes
 * out as: among all the candidates, a blend dropped as no anchor too (a gray badge lies on the line
 * from the list's white to its black text). */
static void find_badge_colors(int mode, double dark_l, double light_l, double keep_tint)
{
    int j;
    badge_count = 0;
    for (j = 0; j < candidate_count && badge_count < BADGE_MAX_COLORS; j++) {
        const Anchor *a = &candidates[j];
        uint8_t px[3];
        double hls;
        uint32_t rgb = pack(a->r, a->g, a->b);
        px[2] = (uint8_t)a->r;
        px[1] = (uint8_t)a->g;
        px[0] = (uint8_t)a->b;
        hls = lightness(px[2], px[1], px[0]);
        if (spread_of(px) >= WHITE_MARK_SPREAD || hls < BADGE_MIN_HLS || hls > (badge_pill ? BADGE_PILL_MAX_HLS : BADGE_MAX_HLS)
            || (a->hrun < SURFACE_RUN && a->vrun < SURFACE_RUN)
            || (badge_pill && (a->hrun < BADGE_PILL_MIN_RUN || a->vrun < BADGE_PILL_MIN_RUN)))
            continue;
        badge_colors[badge_count] = rgb;
        badge_text_count[badge_count] = 0;
        badge_dark[badge_count] = 0;
        badge_out[badge_count] = resolve(rgb, 0, 0U, mode, dark_l, light_l, keep_tint, 0.0) & 0xffffffU;
        badge_hls[badge_count++] = hls;
    }
}

static int badge_tinted(uint32_t b)
{
    return (int)((b >> 16) & 255U) - (int)(b & 255U) >= BADGE_TINT;
}

static int badge_color_of(uint32_t rgb)
{
    int k, ch;
    for (k = 0; k < badge_count; k++) {
        if (badge_colors[k] == rgb)
            return k;
    }
    for (k = 0; badge_pill && k < badge_count; k++) { /* (a shade of it: see badge_pill) */
        uint32_t b = badge_colors[k];
        int br = (int)((b >> 16) & 255U), bg = (int)((b >> 8) & 255U), bb = (int)(b & 255U);
        int r = (int)((rgb >> 16) & 255U), g = (int)((rgb >> 8) & 255U), bl = (int)(rgb & 255U);
        if (br - bb < BADGE_TINT || r - bl < BADGE_TINT || (br >= bg) != (r >= g) || (bg >= bb) != (g >= bl))
            continue; /* only a tinted gray and its shades tinted alike (the pill's warm gray: the canvas' own
                       * grays, the cells' bands, are neutral, and their shades are other surfaces) */
        for (ch = 0; ch < 3; ch++) {
            int d = (int)((rgb >> (8 * ch)) & 255U) - (int)((badge_colors[k] >> (8 * ch)) & 255U);
            if (d > BADGE_SHADE || d < -BADGE_SHADE)
                break;
        }
        if (ch == 3)
            return k;
    }
    return -1;
}

static uint8_t badge_near[MAX_INDEXED]; /* 1: a badge's gray within reach on the left and on the right */
static uint8_t badge_at[MAX_INDEXED]; /* text on a badge: the nearest badge pixel found, its way << 5 | its distance */

/* Which pixels have a badge's gray within reach on both sides along their row (light_on_gray_badge
 * asks that of each way; looked for in one pass a row, it spares the rest the walk). */
static void find_near_badges(const uint32_t *p, int64_t count, int64_t width)
{
    int64_t y, x, rows = width > 0 ? count / width : 0;
    for (y = 0; y < rows; y++) {
        const uint32_t *row = p + y * width;
        uint8_t *near = badge_near + y * width;
        int64_t last = -BADGE_REACH_ACROSS - 1, next = width + BADGE_REACH_ACROSS + 1;
        uint32_t seen = 0;
        int seen_badge = 0, have = 0;
        for (x = 0; x < width; x++) {
            uint32_t c = row[x] & 0xffffffU;
            if (!have || c != seen) { /* (the color's answer only: each pixel's alpha is its own) */
                seen = c;
                seen_badge = badge_color_of(c) >= 0;
                have = 1;
            }
            if (seen_badge && (row[x] >> 24) >= ANCHOR_MIN_ALPHA)
                last = x;
            near[x] = x - last <= BADGE_REACH_ACROSS;
        }
        have = 0;
        for (x = width - 1; x >= 0; x--) {
            uint32_t c = row[x] & 0xffffffU;
            if (!have || c != seen) {
                seen = c;
                seen_badge = badge_color_of(c) >= 0;
                have = 1;
            }
            if (seen_badge && (row[x] >> 24) >= ANCHOR_MIN_ALPHA)
                next = x;
            near[x] = near[x] && next - x <= BADGE_REACH_ACROSS;
        }
    }
}

static int near_rgb(uint32_t a, uint32_t b, int tolerance);

static int light_on_gray_badge(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    int64_t x, y, rows, k;
    int dir, badge = -1, run[4], nearest = 0, nearest_k = BADGE_REACH_ACROSS + 1, crossed = 0, stroke, blocked = 0;
    double own;
    if (!badge_count || width <= 0 || !badge_near[i])
        return 0;
    own = lightness((uint8_t)(p[i] >> 16), (uint8_t)(p[i] >> 8), (uint8_t)p[i]);
    if (own < BADGE_LIGHT_HLS || badge_color_of(p[i] & 0xffffffU) >= 0)
        return 0;
    x = i % width;
    y = i / width;
    rows = count / width;
    for (dir = 0; dir < 4; dir++) {
        int64_t sx = dir == 0 ? 1 : dir == 1 ? -1 : 0, sy = dir == 2 ? 1 : dir == 3 ? -1 : 0;
        int found = 0, same = 1, reach = sx ? BADGE_REACH_ACROSS : BADGE_REACH, dark_run = 0;
        run[dir] = 0;
        for (k = 1; k <= reach && !found; k++) {
            int64_t xx = x + sx * k, yy = y + sy * k;
            const uint8_t *q;
            int which;
            double l;
            if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                return 0;
            q = (const uint8_t *)&p[yy * width + xx];
            if (q[3] < ANCHOR_MIN_ALPHA)
                return 0;
            which = badge_color_of(*(const uint32_t *)q & 0xffffffU);
            l = lightness(q[2], q[1], q[0]);
            if (which >= 0) {
                if ((badge >= 0 && which != badge && !near_rgb(badge_colors[which], badge_colors[badge], BADGE_SAME_GRAY))
                    || badge_hls[which] > own - BADGE_TEXT_STEP)
                    return 0; /* two grays, or one as light as the pixel: no text on its badge (two shades of
                               * one gray are one badge: an anchor's pill, translucent, over the canvas' picture) */
                badge = which;
                found = 1;
                if (k < nearest_k) {
                    nearest_k = (int)k;
                    nearest = dir << 5 | (int)k;
                }
            } else if (l < BADGE_LIGHT_HLS) {
                if (!badge_pill || ++dark_run > BADGE_CROSS_LINE) {
                    if (badge_pill && sy && !blocked) {
                        blocked = 1; /* (a glyph's slanted contour under the pill runs on below a stem: one way
                                      * up or down, the other reaching the pill: the owner, November 25) */
                        break;
                    }
                    return 0; /* dark before the gray: no badge around the pixel */
                }
                crossed = 1; /* (a line under a translucent pill: see BADGE_CROSS_LINE) */
                same = 0;
                continue;
            }
            dark_run = 0;
            same = same && l >= own - BADGE_SAME_HLS && spread_of(q) <= WHITE_MARK_PURE_SPREAD;
            run[dir] += same && !found; /* the pixel's own stroke, up to its fringe or the badge */
        }
        if (!found && blocked == 1) {
            blocked = 2; /* (once: the other way must reach the pill) */
            crossed = 1;
            continue;
        }
        if (!found)
            return 0;
    }
    /* Text is thin one way at least (a stroke, a bar); the white inside a gray-framed box is as wide
     * as it is tall. */
    stroke = badge_pill && badge_tinted(badge_colors[badge]) ? BADGE_PILL_STROKE : BADGE_STROKE;
    if (run[0] + run[1] + 1 > stroke && run[2] + run[3] + 1 > stroke)
        return 0;
    if (crossed && !badge_tinted(badge_colors[badge]))
        return 0;
    badge_at[i] = (uint8_t)nearest;
    return badge + 1;
}

/* A badge whose light text reads badly on it as it comes out (Anchors & Pins' #a0a2a4 kept, white on
 * it about 2.6:1, live) is drawn darker, in its own hue: to the luminance of the Classes panel's badge
 * gray (#646464, about 5.9:1 with white), when its own gives white less than 4.5:1. The color for that,
 * or 0 for none (the badge as it comes out is dark enough). */
#define BADGE_MAX_LUMINANCE 0.1833 /* white on it at 4.5:1 at least */
#define BADGE_DARK_LUMINANCE 0.1274 /* #646464 */
#define BADGE_MIN_TEXT 6 /* pixels: a badge with less light text on it is left as it comes out */

static double luminance_of(uint32_t rgb)
{
    return 0.2126 * SRGB_TO_LINEAR[(rgb >> 16) & 255] + 0.7152 * SRGB_TO_LINEAR[(rgb >> 8) & 255]
           + 0.0722 * SRGB_TO_LINEAR[rgb & 255];
}

static uint32_t darker_badge(uint32_t rgb)
{
    double y = luminance_of(rgb), f;
    if (y <= BADGE_MAX_LUMINANCE)
        return 0;
    f = BADGE_DARK_LUMINANCE / y;
    return ((uint32_t)linear_to_byte(SRGB_TO_LINEAR[(rgb >> 16) & 255] * f) << 16)
           | ((uint32_t)linear_to_byte(SRGB_TO_LINEAR[(rgb >> 8) & 255] * f) << 8)
           | (uint32_t)linear_to_byte(SRGB_TO_LINEAR[rgb & 255] * f) | 0x01000000U; /* (never 0) */
}

/* Text on a badge (light_on_gray_badge), its coverage from the badge toward white drawn again from
 * the badge as it comes out (to: the badge pixel beside it as the mapping drew it, so the
 * text's smoothing meets the badge exactly; badge_out only where nothing is written: detection). */
static uint32_t badge_text(uint32_t v, int k, uint32_t to)
{
    uint32_t from = badge_colors[k];
    double out[3], t = 0.0;
    int ch;
    for (ch = 0; ch < 3; ch++) { /* the pixel's coverage, the mean of its channels' (grayscale smoothing:
                                  * ClearType's colored fringes, drawn for the light badge, are left out) */
        int shift = 16 - 8 * ch;
        double c = (double)((v >> shift) & 255), f = (double)((from >> shift) & 255);
        t += (f < 255.0 ? (c - f) / (255.0 - f) : 1.0) / 3.0;
    }
    t = t < 0.0 ? 0.0 : t > 1.0 ? 1.0 : t;
    for (ch = 0; ch < 3; ch++) {
        double o = (double)((to >> (16 - 8 * ch)) & 255);
        out[ch] = o + t * (255.0 - o);
    }
    return (v & 0xff000000U) | (pack(out[0], out[1], out[2]) & 0xffffffU);
}

/* Ink mode: the edge of a small white shape drawn on nothing (an unticked box a list's delegate paints
 * as a white square) gets a frame color: mapped whole, the box was a dark square with no outline. */
#define BOX_INK_HLS 0.45 /* darker than an unticked box's own gray frame */
#define BOX_FRAME 0x999999U /* the gray FontLab draws on the box's top and left: the added sides match it */

static int white_run(const uint32_t *p, int64_t i, int64_t step, int64_t limit, int64_t width, int horizontal)
{
    int64_t n = 0, j = i;
    while (n <= BOX_MAX_RUN) {
        const uint8_t *q;
        j += step;
        if (j < 0 || j >= limit || (horizontal && (j / width) != (i / width)))
            break;
        q = (const uint8_t *)&p[j];
        if (q[3] < ANCHOR_MIN_ALPHA || lightness(q[2], q[1], q[0]) < WHITE_HLS)
            break;
        n++;
    }
    return (int)n;
}

static int small_box_edge(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    int64_t x = i % width, nb[4];
    int side, beside_nothing = 0;
    nb[0] = x > 0 ? i - 1 : -1;
    nb[1] = x + 1 < width ? i + 1 : -1;
    nb[2] = i - width;
    nb[3] = i + width < count ? i + width : -1;
    for (side = 0; side < 4; side++)
        beside_nothing |= nb[side] < 0 || (p[nb[side]] >> 24) < ANCHOR_MIN_ALPHA;
    if (!beside_nothing)
        return 0;
    if (white_run(p, i, -1, count, width, 1) + white_run(p, i, 1, count, width, 1) + 1 > BOX_MAX_RUN
        || white_run(p, i, -width, count, width, 0) + white_run(p, i, width, count, width, 0) + 1 > BOX_MAX_RUN)
        return 0;
    { /* an empty box: a glyph thumbnail has dark ink inside (framed, it showed broken square outlines) */
        int64_t y = i / width, rows = count / width, dx, dy;
        for (dy = -BOX_MAX_RUN; dy <= BOX_MAX_RUN; dy++) {
            for (dx = -BOX_MAX_RUN; dx <= BOX_MAX_RUN; dx++) {
                const uint8_t *q;
                if (x + dx < 0 || x + dx >= width || y + dy < 0 || y + dy >= rows)
                    continue;
                q = (const uint8_t *)&p[(y + dy) * width + x + dx];
                if (q[3] >= ANCHOR_MIN_ALPHA && lightness(q[2], q[1], q[0]) < BOX_INK_HLS)
                    return 0;
            }
        }
    }
    return 1;
}

/* ANCHORS_SUBPIXEL: text drawn with ClearType on light paper (TrueType Hinting's preview; an editor
 * that took its paper from a light palette). Each channel is paper * (1 - coverage) + text * coverage,
 * the coverage differing per channel (the subpixels). The text is the color around the pixel that
 * explains it and lies farthest from the paper (a blue key's core, black; a fringe explains itself
 * but lies nearer); its dark-mode color keeps it if of middle lightness and colored (syntax colors),
 * else turns its lightness. Each channel's coverage is redrawn from the mapped paper toward that color:
 * ClearType's own light-on-dark rendering, the subpixel structure kept. */
#define SUBPIXEL_MIN_CONTRAST 30.0

static double rgb_channel(uint32_t c, int ch)
{
    return (double)((c >> (16 - 8 * ch)) & 255U);
}

static uint32_t subpixel_text_mapped(uint32_t t, double dark_l, double light_l)
{
    if (icon_keeps(t))
        return t;
    return all_color(t, ANCHORS_ALL, dark_l, light_l, 0.0);
}

static int mode_icon_fallback; /* set per call: editors (colored syntax) */

static uint32_t subpixel_color(uint32_t c, uint32_t mask, double dark_l, double light_l)
{
    const Anchor *paper = &anchors[0];
    uint32_t pc = pack(paper->r, paper->g, paper->b), mp = pack(paper->mr, paper->mg, paper->mb);
    uint32_t text = 0x000000U, mt;
    double best = 1e9, cov[3], best_cov[3], out[3];
    int j, ch, found = 0;
    for (j = 1; j <= anchor_count; j++) {
        uint32_t t;
        double err = 0.0, sum = 0.0, dist = 0.0, score;
        int valid = 0;
        if (j < anchor_count) {
            const Anchor *a = &anchors[j];
            if (!mode_icon_fallback)
                continue; /* the hinting preview's text is black: its ClearType colors are fringes, never text */
            if (!((mask >> j) & 1U) || a->surface || a->okl >= paper->okl - 0.15)
                continue;
            t = pack(a->r, a->g, a->b);
        } else {
            uint8_t px[3];
            px[2] = (uint8_t)(c >> 16);
            px[1] = (uint8_t)(c >> 8);
            px[0] = (uint8_t)c;
            if (found || (mode_icon_fallback && spread_of(px) > LINEAR_SPREAD))
                break; /* a strongly colored pixel with no text color around (a rare red digit): as icons map */
            t = 0x000000U; /* else the smoothing of dark text with no core of its own (a thin quote): black */
        }
        for (ch = 0; ch < 3; ch++) {
            double p = rgb_channel(pc, ch), f = rgb_channel(t, ch), v = rgb_channel(c, ch);
            dist += (p - f) * (p - f);
            if (p - f >= SUBPIXEL_MIN_CONTRAST || f - p >= SUBPIXEL_MIN_CONTRAST) {
                cov[ch] = (p - v) / (p - f);
                err += cov[ch] < 0.0 ? -cov[ch] : cov[ch] > 1.0 ? cov[ch] - 1.0 : 0.0;
                sum += cov[ch];
                valid++;
            } else {
                cov[ch] = -1000.0;
            }
        }
        if (!valid)
            continue;
        for (ch = 0; ch < 3; ch++) {
            if (cov[ch] == -1000.0)
                cov[ch] = sum / valid;
            cov[ch] = cov[ch] < 0.0 ? 0.0 : cov[ch] > 1.0 ? 1.0 : cov[ch];
        }
        score = 10.0 * err - sqrt_pos(dist) / 442.0;
        if (score < best) {
            best = score;
            text = t;
            found = 1;
            best_cov[0] = cov[0];
            best_cov[1] = cov[1];
            best_cov[2] = cov[2];
        }
    }
    if (!found) /* no text color around (a rare red digit): its own dark-mode color, as icons map */
        return subpixel_text_mapped(c, dark_l, light_l);
    mt = subpixel_text_mapped(text, dark_l, light_l);
    if (mode_icon_fallback) {
        /* editors: one coverage per pixel, the channels' mean: gray smoothing, as the Features panel's
         * editor draws (ClearType's per-channel colors read as fringes on a dark paper) */
        double mean = (best_cov[0] + best_cov[1] + best_cov[2]) / 3.0;
        best_cov[0] = best_cov[1] = best_cov[2] = mean;
    }
    for (ch = 0; ch < 3; ch++)
        out[ch] = rgb_channel(mp, ch) + best_cov[ch] * (rgb_channel(mt, ch) - rgb_channel(mp, ch));
    return pack(out[0], out[1], out[2]);
}

/* ClearType colors a stroke's two sides in complementary hues (orange left, blue right): a colored
 * pixel with a pixel of the opposite hue this close along its row is such a fringe (the canvas's
 * measurement labels) and keeps no tint; colored text and marks have no opposite hue beside them. */
#define CLEARTYPE_REACH 3
#define GRAY_TEXT_STEP 0.08 /* black text on a dark editor paper differs from it this little */
#define FRINGE_MAX_SPREAD 110 /* colored text itself (a red digit's core) is more saturated than its fringes */
#define CLEARTYPE_MIN_SPREAD 24
#define CLEARTYPE_OPPOSITE_COS -0.5

static int cleartype_fringe(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    const uint8_t *px = (const uint8_t *)&p[i];
    double m, vr, vg, vb, norm2;
    int64_t x, d;
    uint32_t own;
    if (spread_of(px) < CLEARTYPE_MIN_SPREAD)
        return 0; /* first: most pixels stop here */
    m = (px[0] + px[1] + px[2]) / 3.0;
    vr = px[2] - m;
    vg = px[1] - m;
    vb = px[0] - m;
    norm2 = vr * vr + vg * vg + vb * vb;
    x = i % width;
    if (norm2 <= 0.0)
        return 0;
    own = p[i] & 0xffffffU;
    /* No square root, and a neighbor of the pixel's own color is passed at once: a tinted surface (a Font
     * window's selected cells, pale blue, a million pixels of it) took a second to test, seven roots a pixel
     * (the owner, 2026-11-24: menus slow to answer with many cells selected). The cosine test squared:
     * dot / (|v| |q|) <= c, with c negative, is dot < 0 and dot * dot >= c * c * |v|^2 * |q|^2. */
    for (d = -CLEARTYPE_REACH; d <= CLEARTYPE_REACH; d++) {
        const uint8_t *q;
        double qm, qr, qg, qb, qn2, dot;
        if (d == 0 || x + d < 0 || x + d >= width || i + d >= count)
            continue;
        if ((p[i + d] & 0xffffffU) == own)
            continue; /* its own color: the same hue, never the opposite one */
        q = (const uint8_t *)&p[i + d];
        if (q[3] < ANCHOR_MIN_ALPHA || spread_of(q) < CLEARTYPE_MIN_SPREAD)
            continue;
        qm = (q[0] + q[1] + q[2]) / 3.0;
        qr = q[2] - qm;
        qg = q[1] - qm;
        qb = q[0] - qm;
        qn2 = qr * qr + qg * qg + qb * qb;
        dot = vr * qr + vg * qg + vb * qb;
        if (qn2 > 0.0 && dot < 0.0
            && dot * dot >= CLEARTYPE_OPPOSITE_COS * CLEARTYPE_OPPOSITE_COS * norm2 * qn2)
            return 1;
    }
    return 0;
}

/* Beside gray text: a near-neutral pixel this close along the row, clearly lighter or darker than
 * the paper (white or black text's core). Colored text (a red digit) has none: its fringes stay. */
static int beside_gray_text(const uint32_t *p, int64_t i, int64_t width, int64_t count, double paper_l)
{
    int64_t x = i % width, d;
    for (d = -CLEARTYPE_REACH; d <= CLEARTYPE_REACH; d++) {
        const uint8_t *q;
        double l;
        if (d == 0 || x + d < 0 || x + d >= width || i + d >= count)
            continue;
        q = (const uint8_t *)&p[i + d];
        if (q[3] < ANCHOR_MIN_ALPHA || spread_of(q) >= CLEARTYPE_MIN_SPREAD)
            continue;
        l = lightness(q[2], q[1], q[0]);
        if (l - paper_l >= GRAY_TEXT_STEP || paper_l - l >= GRAY_TEXT_STEP)
            return 1;
    }
    return 0;
}

static int near_rgb(uint32_t a, uint32_t b, int tolerance)
{
    int k;
    for (k = 0; k < 24; k += 8) {
        int d = (int)((a >> k) & 255) - (int)((b >> k) & 255);
        if (d > tolerance || d < -tolerance)
            return 0;
    }
    return 1;
}

/* A pixel of a light surface the mapping turns dark (a selected row): no letter of a badge. */
static int light_row_pixel(int64_t at)
{
    return a_index[at] >= 0 && anchors[a_index[at]].mapped && light_surface_candidate(&anchors[a_index[at]]);
}

/* A dark, low-color anchor whose shapes decide one by one (see GLYPH_ICON_MAX_OKL). */
static int glyph_icon_anchor(const Anchor *a, int64_t area)
{
    return !a->long_line && a->chroma < INK_CHROMA && a->okl < GLYPH_ICON_MAX_OKL
           && (double)a->count < BACKGROUND_SHARE * (double)area;
}

/* Fills icon_px for an image painted on nothing (ink mode, no main background, a_index made): the
 * pixels of each connected shape of a dark gray anchor, translucent edges included, 1 for an icon
 * (mapped as ink), 3 for a badge (kept as drawn); returns whether any shape was found. */
static int find_glyph_icons(const uint32_t *p, int64_t count, int64_t width)
{
    int64_t i, rows = count / width;
    int32_t *queue = icon_queue;
    int j, found = 0, which[MAX_ANCHORS], panels = 0;
    uint32_t colors[MAX_ANCHORS];
    const Anchor *panel_of[GLYPH_MAX_PANELS];
    int64_t panel_box[GLYPH_MAX_PANELS][4];
    for (j = 0; j < anchor_count; j++) {
        if (glyph_icon_anchor(&anchors[j], count)) {
            which[found] = j;
            colors[found++] = pack(anchors[j].r, anchors[j].g, anchors[j].b);
        }
    }
    if (!found)
        return 0;
    for (i = 0; i < count; i++)
        icon_px[i] = 0;
    for (i = 0; i < count; i++) {
        int64_t head = 0, tail = 0, k, x0, x1, y0, y1, x, y, light = 0, on_row = 0, letters = 0;
        uint32_t rgb = 0;
        const Anchor *a = NULL;
        int verdict, hole = 0, bare = 0;
        if (icon_px[i] || (p[i] >> 24) == 0)
            continue;
        for (j = 0; j < found && a == NULL; j++) { /* (gray text drawn translucent: none of its pixels is the anchor itself) */
            if (near_rgb(p[i], colors[j], GLYPH_ICON_NEAR)) {
                a = &anchors[which[j]];
                rgb = colors[j];
            }
        }
        if (a == NULL)
            continue;
        icon_px[i] = 2;
        queue[tail++] = (int32_t)i;
        x0 = x1 = i % width;
        y0 = y1 = i / width;
        while (head < tail) {
            int64_t q = queue[head++], qx = q % width, qy = q / width, n[4];
            int d;
            if (qx < x0) x0 = qx;
            if (qx > x1) x1 = qx;
            if (qy < y0) y0 = qy;
            if (qy > y1) y1 = qy;
            n[0] = qx > 0 ? q - 1 : -1;
            n[1] = qx + 1 < width ? q + 1 : -1;
            n[2] = qy > 0 ? q - width : -1;
            n[3] = qy + 1 < rows ? q + width : -1;
            for (d = 0; d < 4; d++) {
                int64_t m = n[d];
                if (m >= 0 && (p[m] >> 24) < ANCHOR_MIN_ALPHA)
                    bare = 1; /* drawn on nothing, or smoothed toward it */
                if (m >= 0 && !icon_px[m] && (p[m] >> 24) > 0
                    && (near_rgb(p[m], rgb, GLYPH_ICON_GROW)
                        /* through its light letters too, opaque (a tile: the Font window's script icons, cut in
                         * pieces by their letters, each piece too small for a badge, came out light: the owner,
                         * 2026-11-25); a glyph icon drawn on nothing has no opaque light pixel on it */
                        || ((p[m] >> 24) == 255 && !light_row_pixel(m)
                            && lightness((uint8_t)(p[m] >> 16), (uint8_t)(p[m] >> 8), (uint8_t)p[m]) >= GLYPH_TILE_GROW_HLS))) {
                    icon_px[m] = 2;
                    queue[tail++] = (int32_t)m;
                }
            }
        }
        if ((x1 - x0 >= GLYPH_ICON_MAX_SIDE && y1 - y0 >= GLYPH_ICON_MAX_SIDE) || x1 - x0 >= 4 * GLYPH_ICON_MAX_SIDE
            || y1 - y0 >= 4 * GLYPH_ICON_MAX_SIDE) {
            if (panels < GLYPH_MAX_PANELS) {
                panel_of[panels] = a;
                panel_box[panels][0] = x0;
                panel_box[panels][1] = x1;
                panel_box[panels][2] = y0;
                panel_box[panels++][3] = y1;
            }
            continue; /* a panel: as the anchor decided (a word, joined through its smoothing, is long but low) */
        }
        /* (rows are read top to bottom: a panel is met before the holes inside its box; a dot of gray
         * text drawn on nothing, inside the box of a long word, touches nothing opaque and is no hole) */
        for (j = 0; j < panels && !hole && !bare; j++)
            hole = panel_of[j] == a && x0 >= panel_box[j][0] && x1 <= panel_box[j][1] && y0 >= panel_box[j][2]
                   && y1 <= panel_box[j][3];
        if (hole)
            continue; /* a letter's counter on a panel of its own color: the panel's, as the anchor decided */
        for (y = y0; y <= y1; y++) {
            for (x = x0; x <= x1; x++) {
                int64_t at = y * width + x;
                uint32_t v = p[at];
                if ((v >> 24) >= ANCHOR_MIN_ALPHA && light_row_pixel(at))
                    on_row++;
                else if ((v >> 24) >= ANCHOR_MIN_ALPHA) {
                    double l = lightness((uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v);
                    light += l >= GLYPH_ICON_LIGHT_HLS;
                    letters += l >= GLYPH_TILE_LETTER_HLS;
                }
            }
        }
        /* A tile (see the flood above): its box filled, letters on it of middle lightness at least (Malayalam's and
         * Tamil's, mid-gray, came out on a light tile): as drawn. */
        if (letters >= GLYPH_BADGE_MIN_LIGHT && on_row == 0 && tail * 100 >= GLYPH_TILE_FILL * (x1 - x0 + 1) * (y1 - y0 + 1)
            && x1 - x0 >= 7 && y1 - y0 >= 7 && letters < tail) {
            for (k = 0; k < tail; k++)
                icon_px[queue[k]] = 3;
            continue;
        }
        /* light letters on it: a badge; a light pixel or two (a tag's hole): an icon. A shape whose box
         * holds more of a light row than of other light pixels is text on that row, its smoothing toward
         * the row being the light pixels: no badge (Overlay Fonts' sample, black on its selected row: the
         * letters with counters were kept dark, light edges around them; the owner, 2026-11-24). A badge
         * on a row fills its box but for its rounded corners. */
        if (light >= GLYPH_BADGE_MIN_LIGHT && (double)light >= GLYPH_BADGE_LIGHT_SHARE * (double)tail && on_row <= light
            && (2 * tail >= (x1 - x0 + 1) * (y1 - y0 + 1)
                || (tail + light) * 100 >= GLYPH_TILE_FILL * (x1 - x0 + 1) * (y1 - y0 + 1))
            && x1 - x0 >= 7 && y1 - y0 >= 7) { /* (and a badge fills half its box at least, or, a tile, fills it with
                                                * its letters: the Font window's Bengali and Kannada script icons,
                                                * their letters more than half the tile, came out light gray: the
                                                * owner, 2026-11-25; and holds letters: a letter or its end does
                                                * neither) */
            verdict = 3;
            for (y = y0; y <= y1; y++) { /* its letters and their smoothing too, as drawn */
                for (x = x0; x <= x1; x++) {
                    int64_t at = y * width + x;
                    if (!icon_px[at] && (p[at] >> 24) > 0 && !light_row_pixel(at))
                        icon_px[at] = 3;
                }
            }
        } else if ((double)tail >= GLYPH_SOLID_SHARE * (double)((x1 - x0 + 1) * (y1 - y0 + 1)) && x1 - x0 >= 5 && y1 - y0 >= 5)
            verdict = 2; /* a filled block (a selected row's dark branch cell): as the anchor decided */
        else
            verdict = a->mapped ? 2 : 1; /* dark text already mapped as ink stays so */
        for (k = 0; k < tail; k++)
            icon_px[queue[k]] = (uint8_t)verdict;
    }
    return 1;
}

/* Whether a ClearType fringe is dark text's on a white ground: a near-white, low-color pixel within reach
 * along its row, and no pixel there lighter than it by much that is colored (light text's fringes on a dark
 * or colored ground have none), and none of pure white (see DARK_TEXT_PURE_WHITE). */
#define DARK_TEXT_REACH 4
#define DARK_TEXT_VETO_REACH 12 /* pure white this near, along the row: not a tag */
#define DARK_TEXT_PAPER_HLS 0.9
#define DARK_TEXT_PURE_WHITE 253 /* every channel: FontLab's tags and pills are off-white (f8f8f9) */
static int dark_text_white_ok; /* set by freelab_gray_cleartype: an interface's pure white is a ground like any */
static int dark_text_fringe(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    int64_t x = i % width, d;
    int found = 0;
    for (d = -DARK_TEXT_VETO_REACH; d <= DARK_TEXT_VETO_REACH; d++) {
        const uint8_t *q;
        if (d == 0 || x + d < 0 || x + d >= width || i + d < 0 || i + d >= count)
            continue;
        q = (const uint8_t *)&p[i + d];
        if (q[3] < ANCHOR_MIN_ALPHA)
            continue;
        if (q[0] >= DARK_TEXT_PURE_WHITE && q[1] >= DARK_TEXT_PURE_WHITE && q[2] >= DARK_TEXT_PURE_WHITE
            && !dark_text_white_ok)
            return 0; /* on pure white: TrueType Hinting's preview, whose ClearType colors are what it shows */
        if (d < -DARK_TEXT_REACH || d > DARK_TEXT_REACH)
            continue;
        /* the tag's ground: off-white, flat (the same color twice running: smoothing never is) */
        if (spread_of(q) < CLEARTYPE_MIN_SPREAD && lightness(q[2], q[1], q[0]) >= DARK_TEXT_PAPER_HLS
            && ((x + d + 1 < width && i + d + 1 < count && p[i + d + 1] == p[i + d])
                || (x + d - 1 >= 0 && i + d - 1 >= 0 && p[i + d - 1] == p[i + d])))
            found = 1;
    }
    /* above and below too: inside a word no ground runs flat along the row, but the tag's does just over
     * and under the line of text */
    for (d = -DARK_TEXT_VETO_REACH; d <= DARK_TEXT_VETO_REACH; d++) {
        const uint8_t *q;
        int64_t at = i + d * width;
        if (d == 0 || at < 0 || at >= count)
            continue;
        q = (const uint8_t *)&p[at];
        if (q[3] < ANCHOR_MIN_ALPHA)
            continue;
        if (q[0] >= DARK_TEXT_PURE_WHITE && q[1] >= DARK_TEXT_PURE_WHITE && q[2] >= DARK_TEXT_PURE_WHITE
            && !dark_text_white_ok)
            return 0;
        if (spread_of(q) < CLEARTYPE_MIN_SPREAD && lightness(q[2], q[1], q[0]) >= DARK_TEXT_PAPER_HLS
            && ((x + 1 < width && at + 1 < count && p[at + 1] == p[at]) || (x - 1 >= 0 && at - 1 >= 0 && p[at - 1] == p[at])))
            found = 1;
    }
    return found;
}

/* Colored text drawn with ClearType on pure white (TrueType Hinting's size numbers, navy #000080, and the
 * number on the navy box of the size shown): each channel is white * (1 - coverage) + text * coverage.
 * Mapped as other pixels, its edges came out a dim mix of purples and teals; dark_text_fringe, for black
 * text, leaves pure white alone (the preview above shows ClearType's colors on purpose). Small numbers
 * have no pixel of the text color itself, so it is the picture's most frequent dark, strongly colored
 * exact color (colored_text_color), and only one the mapping moves far (the Font window's selected cell
 * keeps its blue: a surface, not text). Found on the pixels as drawn, before any is mapped: a colored
 * pixel with pure white within COLORED_CT_REACH, whose most inked pixel near leans to the text color's
 * channel, and with no pixel within a letter's reach (COLORED_CT_VETO_REACH) below the text color in any
 * channel (ClearType never draws navy text's blue below navy's 128; small black text, whose thin stems
 * look like navy's, has an orange edge's low blue or a black core). Each such pixel is redrawn with one
 * coverage, its channels' mean, from the mapped white toward the mapped text color: gray smoothing in the
 * text's own dark-mode color, as the editors get (the owner, 2026-11-25: soft numbers, colored edges).
 * Checked on every capture of the session's probes: only the hinting numbers change. */
#define COLORED_CT_MARK 5          /* white_mark */
#define COLORED_CT_REACH 2
#define COLORED_CT_MIN_SPREAD 90
#define COLORED_CT_MAX_LOW 40      /* the text color's darkest channel at most */
#define COLORED_CT_MAX_HLS 0.4
#define COLORED_CT_LEEWAY 24       /* how much darker than the text color a channel may be */
#define COLORED_CT_MIN_CONTRAST 30.0
static uint32_t colored_out[MAX_INDEXED];

/* The text color: the most frequent exact color that is dark and strongly colored (navy: the box of the
 * size shown, the cores of larger numbers); 0x1000000 when the picture has none of COLORED_CT_MIN_COUNT. */
#define COLORED_CT_MIN_COUNT 20
#define COLORED_CT_COLORS 512 /* distinct candidates counted (a hinting preview has some 155: its black text's edges) */
#define COLORED_CT_NEAR_SPREAD 60  /* the darkest pixel near: colored, led by the text color's channel, */
#define COLORED_CT_NEAR_LOW 70     /* and dark in one channel at least */
#define COLORED_CT_VETO_REACH 6    /* pixels: a letter's reach, for a pixel below the text color */
#define COLORED_CT_PIXEL_SPREAD 16 /* the pixel itself: colored */
#define COLORED_CT_MIN_MOVE 120    /* how far the mapping moves the color (channels' sum) for it to be text's */
static int strongest_of(uint32_t c)
{
    int r = (int)((c >> 16) & 255U), g = (int)((c >> 8) & 255U), b = (int)(c & 255U);
    return r >= g && r >= b ? 2 : (g >= b ? 1 : 0); /* (as strongest_channel: memory order) */
}

static uint32_t ct_colors[COLORED_CT_COLORS];
static int64_t ct_counts[COLORED_CT_COLORS];

static uint32_t colored_text_color(const uint32_t *p, int64_t count)
{
    uint32_t *colors = ct_colors;
    int64_t *counts = ct_counts, i, best = 0;
    int n = 0, k;
    uint32_t found = 0x1000000U;
    for (i = 0; i < count; i++) {
        const uint8_t *q = (const uint8_t *)&p[i];
        int high, low;
        uint32_t c;
        if (q[3] < ANCHOR_MIN_ALPHA)
            continue;
        high = q[0] > q[1] ? (q[0] > q[2] ? q[0] : q[2]) : (q[1] > q[2] ? q[1] : q[2]);
        low = q[0] < q[1] ? (q[0] < q[2] ? q[0] : q[2]) : (q[1] < q[2] ? q[1] : q[2]);
        if (high - low < COLORED_CT_MIN_SPREAD || low > COLORED_CT_MAX_LOW || (high + low) / 510.0 > COLORED_CT_MAX_HLS)
            continue;
        c = p[i] & 0xffffffU;
        for (k = 0; k < n && colors[k] != c; k++)
            ;
        if (k == n) {
            if (n == COLORED_CT_COLORS)
                continue;
            colors[n] = c;
            counts[n++] = 0;
        }
        counts[k]++;
    }
    for (k = 0; k < n; k++) {
        if (counts[k] >= COLORED_CT_MIN_COUNT && counts[k] > best) {
            best = counts[k];
            found = colors[k];
        }
    }
    return found;
}

static int colored_cleartype(const uint32_t *p, int64_t i, int64_t width, int64_t count, uint32_t t)
{
    int64_t x = i % width, dx, dy;
    const uint8_t *v = (const uint8_t *)&p[i];
    int white = 0, ch, t_high = (int)((t >> 16) & 255U);
    double darkest = 256.0;
    const uint8_t *dark = 0;
    if (t <= 0xffffffU) {
        if ((int)((t >> 8) & 255U) > t_high)
            t_high = (int)((t >> 8) & 255U);
        if ((int)(t & 255U) > t_high)
            t_high = (int)(t & 255U);
    }
    if (t > 0xffffffU || v[3] < ANCHOR_MIN_ALPHA || spread_of(v) < COLORED_CT_PIXEL_SPREAD)
        return 0; /* (pure white, grays: no navy smoothing is gray but by chance, and grays are most of a canvas) */
    for (ch = 0; ch < 3; ch++)
        if ((int)v[ch] + COLORED_CT_LEEWAY < (int)((t >> (8 * ch)) & 255U))
            return 0;
    for (dy = -COLORED_CT_REACH; dy <= COLORED_CT_REACH; dy++) {
        for (dx = -COLORED_CT_REACH; dx <= COLORED_CT_REACH; dx++) {
            int64_t at = i + dy * width + dx;
            const uint8_t *q;
            int high;
            double l;
            if (x + dx < 0 || x + dx >= width || at < 0 || at >= count)
                continue;
            q = (const uint8_t *)&p[at];
            if (q[3] < ANCHOR_MIN_ALPHA)
                continue;
            if (q[0] >= DARK_TEXT_PURE_WHITE && q[1] >= DARK_TEXT_PURE_WHITE && q[2] >= DARK_TEXT_PURE_WHITE) {
                white = 1;
                continue;
            }
            high = q[0] > q[1] ? (q[0] > q[2] ? q[0] : q[2]) : (q[1] > q[2] ? q[1] : q[2]);
            if (high + COLORED_CT_LEEWAY < t_high)
                return 0; /* darker than the text color at its brightest: black text, a dark ground */
            for (ch = 0; ch < 3; ch++) /* each a blend of white and the text color: no channel below the color's
                                        * (black text's orange edges have a low blue) */
                if ((int)q[ch] + COLORED_CT_LEEWAY < (int)((t >> (8 * ch)) & 255U))
                    return 0;
            l = (double)min_channel(q); /* the most ink: its lowest channel (navy's red and green) */
            if (l < darkest) {
                darkest = l;
                dark = q;
            }
        }
    }
    if (!white || dark == 0 || spread_of(dark) < COLORED_CT_NEAR_SPREAD || strongest_channel(dark) != strongest_of(t)
        || min_channel(dark) > COLORED_CT_NEAR_LOW)
        return 0; /* (a light fringe the darkest near: gray text, a ruler's digits on its near-white strip) */
    /* Small black text's thin stems are drawn as navy's would be ((43,43,128) beside (255,212,128)); its
     * letter has a pixel below the text color somewhere (an orange edge's low blue, a black core), navy
     * text never: looked for over a letter's reach (the Fonts panel's list as drawn, the owner's fonts) */
    for (dy = -COLORED_CT_VETO_REACH; dy <= COLORED_CT_VETO_REACH; dy++) {
        for (dx = -COLORED_CT_VETO_REACH; dx <= COLORED_CT_VETO_REACH; dx++) {
            int64_t at = i + dy * width + dx;
            const uint8_t *q;
            if (x + dx < 0 || x + dx >= width || at < 0 || at >= count)
                continue;
            q = (const uint8_t *)&p[at];
            if (q[3] < ANCHOR_MIN_ALPHA)
                continue;
            for (ch = 0; ch < 3; ch++)
                if ((int)q[ch] + COLORED_CT_LEEWAY < (int)((t >> (8 * ch)) & 255U))
                    return 0;
        }
    }
    return 1;
}

static uint32_t colored_cleartype_color(uint32_t c, uint32_t t, int mode, double dark_l, double light_l,
                                        double keep_tint)
{
    uint32_t mw = resolve(0xffffffU, 0, 0U, mode, dark_l, light_l, keep_tint, 0.0) & 0xffffffU;
    uint32_t mt = resolve(t, 0, 0U, mode, dark_l, light_l, keep_tint, 0.0) & 0xffffffU;
    double sum = 0.0, cov, out[3];
    int ch, valid = 0;
    for (ch = 0; ch < 3; ch++) {
        double f = rgb_channel(t, ch), value = rgb_channel(c, ch);
        if (255.0 - f >= COLORED_CT_MIN_CONTRAST) {
            double one = (255.0 - value) / (255.0 - f);
            sum += one < 0.0 ? 0.0 : one > 1.0 ? 1.0 : one;
            valid++;
        }
    }
    cov = valid ? sum / valid : 1.0;
    for (ch = 0; ch < 3; ch++)
        out[ch] = rgb_channel(mw, ch) + cov * (rgb_channel(mt, ch) - rgb_channel(mw, ch));
    return pack(out[0], out[1], out[2]);
}

/* Ink: colored text a list draws with ClearType on its light rows (Overlay Fonts' samples, "AaGg123" in each
 * layer's color, on white and on the light blue of the selected row). Kept as drawn, the text's edges, of
 * every hue but its own, stayed around it: dark edges, a gray and purple patch in each G (the owner,
 * 2026-11-25). A pixel with a strongly colored anchor (the text's color) and a light paper of low color
 * within COLORED_TEXT_REACH, its channels between the two, is drawn with one coverage, the mean of its
 * channels', from the paper as it comes out toward the text as it comes out. */
#define COLORED_TEXT_REACH 2
#define COLORED_TEXT_MIN_SPREAD 80   /* the text's color: strongly colored */
#define COLORED_TEXT_MIN_COUNT 12    /* and frequent (an anchor of the image) */
#define COLORED_TEXT_NEAR 16         /* per channel: a pixel this near the text's color is the text */
#define COLORED_TEXT_PAPER_HLS 0.85
#define COLORED_TEXT_PAPER_SPREAD 30
#define COLORED_TEXT_MIN_DISTANCE 150 /* channels' sum between paper and text */
#define COLORED_TEXT_MAX 8
#define COLORED_TEXT_OVERSHOOT 90 /* per channel past the text's color, toward away from the paper */
static uint32_t colored_text[COLORED_TEXT_MAX];
static int colored_text_count;

static void colored_text_anchors(int on)
{
    int j;
    colored_text_count = 0;
    for (j = 0; on && j < anchor_count && colored_text_count < COLORED_TEXT_MAX; j++) {
        uint8_t q[3];
        q[2] = (uint8_t)anchors[j].r;
        q[1] = (uint8_t)anchors[j].g;
        q[0] = (uint8_t)anchors[j].b;
        if (spread_of(q) >= COLORED_TEXT_MIN_SPREAD && anchors[j].count >= COLORED_TEXT_MIN_COUNT)
            colored_text[colored_text_count++] = pack(anchors[j].r, anchors[j].g, anchors[j].b);
    }
}

static int colored_text_on_light(const uint32_t *p, int64_t i, int64_t width, int64_t count, int mode, double dark_l,
                                 double light_l, double keep_tint, uint32_t *out)
{
    int64_t x = i % width, dx, dy;
    const uint8_t *v = (const uint8_t *)&p[i];
    uint32_t text = 0x1000000U, paper = 0x1000000U, c = p[i] & 0xffffffU, mt, mp;
    double paper_l = 0.0, sum = 0.0, cov, o[3];
    int ch, valid = 0, k;
    if (!colored_text_count || spread_of(v) < 12)
        return 0; /* (gray pixels: the paper, gray text) */
    for (dy = -COLORED_TEXT_REACH; dy <= COLORED_TEXT_REACH; dy++) {
        for (dx = -COLORED_TEXT_REACH; dx <= COLORED_TEXT_REACH; dx++) {
            int64_t at = i + dy * width + dx;
            const uint8_t *q;
            double l;
            if (x + dx < 0 || x + dx >= width || at < 0 || at >= count)
                continue;
            q = (const uint8_t *)&p[at];
            if (q[3] < ANCHOR_MIN_ALPHA)
                continue;
            for (k = 0; k < colored_text_count && text > 0xffffffU; k++)
                if (near_rgb(colored_text[k], p[at] & 0xffffffU, COLORED_TEXT_NEAR))
                    text = colored_text[k];
            l = lightness(q[2], q[1], q[0]);
            if (spread_of(q) <= COLORED_TEXT_PAPER_SPREAD && l >= COLORED_TEXT_PAPER_HLS && l > paper_l) {
                paper_l = l;
                paper = p[at] & 0xffffffU;
            }
        }
    }
    if (text > 0xffffffU || paper > 0xffffffU || near_rgb(text, c, COLORED_TEXT_NEAR))
        return 0; /* (the text itself: as the mapping keeps it) */
    {
        int distance = 0;
        for (ch = 0; ch < 3; ch++) {
            int d = (int)rgb_channel(text, ch) - (int)rgb_channel(paper, ch);
            distance += d < 0 ? -d : d;
        }
        if (distance < COLORED_TEXT_MIN_DISTANCE)
            return 0;
    }
    for (ch = 0; ch < 3; ch++) {
        double t = rgb_channel(text, ch), w = rgb_channel(paper, ch), value = rgb_channel(c, ch);
        double lo = t < w ? t : w, hi = t < w ? w : t;
        /* (past the text's own color, ClearType's contrast overshoots: a bold sample's edges darker than its green,
         * kept as drawn, ringed it dark) */
        if (value < lo - (t < w ? COLORED_TEXT_OVERSHOOT : COLORED_CT_LEEWAY)
            || value > hi + (t > w ? COLORED_TEXT_OVERSHOOT : COLORED_CT_LEEWAY))
            return 0; /* not between the two: another color */
        if (hi - lo >= COLORED_CT_MIN_CONTRAST) {
            double one = (w - value) / (w - t);
            sum += one < 0.0 ? 0.0 : one > 1.0 ? 1.0 : one;
            valid++;
        }
    }
    if (!valid)
        return 0;
    cov = sum / valid;
    mt = text; /* (ink keeps colored text as drawn; mapped alone, a repainted row's green came out dark) */
    mp = resolve(paper, 0, 0U, mode, dark_l, light_l, keep_tint, 0.0) & 0xffffffU;
    for (ch = 0; ch < 3; ch++)
        o[ch] = rgb_channel(mp, ch) + cov * (rgb_channel(mt, ch) - rgb_channel(mp, ch));
    *out = pack(o[0], o[1], o[2]);
    return 1;
}

/* A strongly colored mark with a white halo (the Scoreboard's orange word, drawn for a light canvas, shown in
 * a window of its own with the ink effect): ink, with no anchor to map, turns the halo's whites dark as
 * stray whites, and the blends between the mark and its halo, kept as drawn, ringed the word in light dots
 * (the owner, 2026-11-25). Such a blend is drawn again as the blend of the mark and what the white becomes.
 * The pixel (BGRA) is changed in place; 1 when it was such a blend. */
#define HALO_WHITE_HLS 0.95 /* the halo: this light, of low color */
#define HALO_MARK_SPREAD 60 /* the mark it rings: strongly colored */
#define HALO_MAX_ALPHA 250 /* a halo is translucent (the Scoreboard's, 220); a white mark on a control is opaque */
static int halo_blend(uint8_t *px, double dark_l, double light_l)
{
    int a_i = -1, b_i = -1, j;
    double t = 0.0;
    uint32_t all = anchor_count >= 32 ? 0xffffffffU : ((1U << anchor_count) - 1U);
    const Anchor *w, *k;
    uint8_t q[3], white[3];
    if (!best_pair((double)px[2], (double)px[1], (double)px[0], 0U, all, BLEND_TOLERANCE, &a_i, &b_i, &t))
        return 0;
    for (j = 0; j < 2; j++) {
        const Anchor *x = &anchors[j == 0 ? a_i : b_i];
        q[2] = (uint8_t)x->r;
        q[1] = (uint8_t)x->g;
        q[0] = (uint8_t)x->b;
        if (lightness(q[2], q[1], q[0]) >= HALO_WHITE_HLS && spread_of(q) <= LINEAR_SPREAD)
            break;
    }
    if (j == 2)
        return 0;
    w = &anchors[j == 0 ? a_i : b_i];
    k = &anchors[j == 0 ? b_i : a_i];
    q[2] = (uint8_t)k->r;
    q[1] = (uint8_t)k->g;
    q[0] = (uint8_t)k->b;
    if (spread_of(q) <= HALO_MARK_SPREAD)
        return 0;
    if (j == 0)
        t = 1.0 - t; /* t: from the mark toward the white */
    white[2] = (uint8_t)w->r;
    white[1] = (uint8_t)w->g;
    white[0] = (uint8_t)w->b;
    map_rgb(&white[2], &white[1], &white[0], dark_l, light_l, 0.0);
    px[2] = (uint8_t)(k->r + t * ((double)white[2] - k->r) + 0.5);
    px[1] = (uint8_t)(k->g + t * ((double)white[1] - k->g) + 0.5);
    px[0] = (uint8_t)(k->b + t * ((double)white[0] - k->b) + 0.5);
    return 1;
}

/* Colored text drawn on a light paper, kept in its own color over the mapped paper (Overlay Fonts' sample
 * rows and preview: each font in the color the owner picks for it). Mapped, a dark red came out pink and
 * its edges in light dots, and as the color was dragged the mess changed with it (the owner, 2026-11-25:
 * "a different approach entirely that leaves colored text intact"). Over a paper, a smoothed pixel is the
 * text's color mixed with the paper's. The picture's text colors are its frequent strong colors (cores); a
 * pixel near a core is put on the line from its paper (the nearest pixel of a paper color) to the text color
 * that fits it best, and drawn again at that share between the paper as mapped (that same pixel's, mapped)
 * and the text's own color. A pixel no single text color fits (two fonts overlapping) is followed from its
 * paper through the pixel to the edge of the RGB cube instead, which gives a color and its share. Black text's
 * ClearType fringes give strong colors too, but no core; neutral content (gray, black, white on gray) keeps the
 * mapping. `orig` is the picture as drawn, `out` the same picture mapped; returns how many pixels were drawn
 * again. */
#define REGROUND_TABLE 16384
#define REGROUND_PAPERS 4
#define REGROUND_PAPER_HLS 0.75 /* a paper: this light at least, */
#define REGROUND_PAPER_SHARE 0.05 /* and this share of the picture's pixels at least (rows alternate two) */
#define REGROUND_TEXTS 8
#define REGROUND_TEXT_COUNT 40 /* a text color: a pixel color this frequent, */
#define REGROUND_TEXT_SPREAD 40 /* this strong (its channels this far apart), */
#define REGROUND_TEXT_SHARE 0.5 /* and this far from white, followed to the cube's edge (a pill's gray and its
                                 * name's fringes: 0.25 to 0.45) */
#define REGROUND_FIT 24.0 /* per channel, root mean square: a pixel on a text color's line */
#define REGROUND_MIN_STEP 3 /* per channel: a pixel this near its paper is paper */
#define REGROUND_REACH 2 /* a core this near */
#define REGROUND_PAPER_REACH 4 /* a paper pixel this near (else the main paper) */
/* Light text (freelab_reground_light: a near-white color picked, #e7e3d7 on the selected row's #e9f0ff, the owner,
 * 2026-11-26): too weak for the tests above, and frequent enough to pass for a paper, it was mapped with the paper
 * and its letters came out hollow. In the widgets that show samples, a light color is text when its edges blend
 * into a paper: its neighbors are mostly paper or the smoothing between that paper and it. A paper's neighbors
 * are other papers, edge to edge (a row beside a row); a pill's white name sits on the pill's gray. */
#define REGROUND_LIGHT_PAPERS 6 /* paper candidates looked at, before those that are light text are set aside */
#define REGROUND_LIGHT_MIN_EDGES 8 /* edge neighbors that are smoothing toward a paper, at least */
#define REGROUND_LIGHT_SMOOTH 0.15 /* and this share of its edge neighbors, */
#define REGROUND_LIGHT_ON_PAPER 0.75 /* smoothing and paper together this share at least, around a group of its pixels */
#define REGROUND_LIGHT_COLOR_ON_PAPER 0.5 /* and around all of the color's pixels */
#define REGROUND_LIGHT_COLOR_SOLID 0.6 /* the color's pixels inside a solid run, this share at most (a list's dark empty
                                        * part, taken as a text color, made near-white text its smoothing; the text with
                                        * a pill of its own gray: some 60%) */
#define REGROUND_LIGHT_FIT 0.4 /* a light text's line is short: a pixel on it within this share of its length */
#define REGROUND_LIGHT_PASSES 64 /* sweeps that carry "reaches a paper" through a light text's cores, at most */
#define REGROUND_DARK_GROUND_HLS 0.4 /* a sample with no light paper, its most frequent color this dark: as drawn */
/* In the samples, two rules and no gap between them (the owner, 2026-11-26): a color is text by the strong-color
 * test, or else by its shape, whatever its lightness. A light rule from 0.75 up had left a pale yellow (#dfde92, at
 * 0.72) to neither, mapped dark with light edges, and a dark gray pick (#202020) came out light. By its shape: */
#define REGROUND_LIGHT_SOLID 0.5 /* this share of its pixels inside a solid run at most: strokes (the pill's gray on
                                  * the row is a solid block) */
#define REGROUND_PAPER_SPAN 0.6 /* on a dark ground, a light paper runs this share of the picture's width on a line */
static uint32_t reground_keys[REGROUND_TABLE];
static int64_t reground_counts[REGROUND_TABLE];
static uint8_t reground_core[MAX_INDEXED];
static int32_t reground_group[MAX_INDEXED]; /* a group of light cores being looked at */
static uint8_t reground_asked[REGROUND_TABLE];
static int64_t reground_smooth[REGROUND_TABLE], reground_papered[REGROUND_TABLE], reground_other[REGROUND_TABLE];
static int64_t reground_inner[REGROUND_TABLE], reground_pixels[REGROUND_TABLE];

static void rgb_of(uint32_t rgb, int c[3]);

static double reground_tolerance(double len, int light)
{
    double tol = 3.0 * REGROUND_FIT * REGROUND_FIT;
    if (light && REGROUND_LIGHT_FIT * REGROUND_LIGHT_FIT * len < tol)
        tol = REGROUND_LIGHT_FIT * REGROUND_LIGHT_FIT * len; /* (len: the line's squared length) */
    return tol;
}

static int64_t reground_find(uint32_t rgb)
{
    uint32_t key = (rgb & 0xffffffU) | 0x1000000U, h = (uint32_t)(key * 2654435761U) >> 18;
    int probe;
    for (probe = 0; probe < REGROUND_TABLE; probe++, h = (h + 1) & (REGROUND_TABLE - 1)) {
        if (reground_keys[h] == key)
            return (int64_t)h;
        if (reground_keys[h] == 0)
            return -1;
    }
    return -1;
}

/* For each color of the table marked in reground_asked, its pixels' four neighbors of another color counted as a
 * paper, as smoothing from a paper toward it (on the line, short of both ends), or as something else. A neighbor
 * on the line near the color's own end is its own shade, not counted. */
static void reground_edges(const uint32_t *p, int64_t count, int64_t width, const uint32_t *papers, int npapers)
{
    int64_t i, rows = count / width, last_k = -1;
    uint32_t last = 0xffffffffU;
    for (i = 0; i < REGROUND_TABLE; i++)
        reground_smooth[i] = reground_papered[i] = reground_other[i] = reground_inner[i] = reground_pixels[i] = 0;
    for (i = 0; i < count; i++) {
        int64_t k, x, y;
        int d, c[3], same;
        uint32_t own;
        if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        own = p[i] & 0xffffffU;
        if (own != last) { /* (runs of one color: looked up once) */
            last = own;
            last_k = reground_find(own);
        }
        k = last_k;
        if (k < 0 || !reground_asked[k])
            continue;
        rgb_of(own, c);
        x = i % width;
        y = i / width;
        same = 0;
        for (d = 0; d < 4; d++) {
            int64_t xx = x + (d == 0) - (d == 1), yy = y + (d == 2) - (d == 3), n;
            uint32_t near;
            int m, kind = 0; /* 1 paper, 2 smoothing, 3 its own shade */
            if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                continue;
            n = yy * width + xx;
            if ((p[n] >> 24) < ANCHOR_MIN_ALPHA) {
                reground_other[k]++;
                continue;
            }
            near = p[n] & 0xffffffU;
            if (near == own) {
                same++;
                continue;
            }
            for (m = 0; m < npapers && !kind; m++)
                if (near == papers[m])
                    kind = 1;
            for (m = 0; m < npapers && !kind; m++) {
                int pp[3], q[3], ch;
                double dot = 0.0, len = 0.0, share, fit = 0.0;
                if (papers[m] == own)
                    continue;
                rgb_of(papers[m], pp);
                rgb_of(near, q);
                for (ch = 0; ch < 3; ch++) {
                    dot += (double)(q[ch] - pp[ch]) * (double)(c[ch] - pp[ch]);
                    len += (double)(c[ch] - pp[ch]) * (double)(c[ch] - pp[ch]);
                }
                if (len <= 0.0)
                    continue;
                share = dot / len;
                if (share <= 0.05)
                    continue;
                for (ch = 0; ch < 3; ch++) {
                    double dd = (double)(q[ch] - pp[ch]) - (share > 1.0 ? 1.0 : share) * (double)(c[ch] - pp[ch]);
                    fit += dd * dd;
                }
                if (fit <= reground_tolerance(len, 1))
                    kind = share >= 0.95 ? 3 : 2;
            }
            if (kind == 1)
                reground_papered[k]++;
            else if (kind == 2)
                reground_smooth[k]++;
            else if (kind == 0)
                reground_other[k]++;
        }
        reground_pixels[k]++;
        if (same == 4)
            reground_inner[k]++;
    }
}

static int reground_sits(int64_t k)
{
    int64_t total = reground_smooth[k] + reground_papered[k] + reground_other[k];
    /* (whether its pixels are strokes lying on the paper is asked of each group of them, more strictly: a pick of the
     * pill's own gray is the text's color and the pill's, whose white name pulls the color's share down. Without this
     * looser test of the color, smoothed shades near the paper took the text colors' slots) */
    return total > 0 && reground_smooth[k] >= REGROUND_LIGHT_MIN_EDGES
        && (double)reground_smooth[k] >= REGROUND_LIGHT_SMOOTH * (double)total
        && (double)(reground_smooth[k] + reground_papered[k]) >= REGROUND_LIGHT_COLOR_ON_PAPER * (double)total
        && (double)reground_inner[k] <= REGROUND_LIGHT_COLOR_SOLID * (double)reground_pixels[k];
}

static double reground_unmix(const uint8_t *q, const int paper[3], double color[3])
{
    int v[3], ch, moved = 0;
    double t = 1e9;
    v[0] = (int)q[2] - paper[0];
    v[1] = (int)q[1] - paper[1];
    v[2] = (int)q[0] - paper[2];
    for (ch = 0; ch < 3; ch++)
        if (v[ch] >= REGROUND_MIN_STEP || v[ch] <= -REGROUND_MIN_STEP)
            moved = 1;
    if (!moved)
        return 0.0;
    for (ch = 0; ch < 3; ch++) {
        double limit;
        if (v[ch] < 0)
            limit = (double)paper[ch] / (double)(-v[ch]);
        else if (v[ch] > 0)
            limit = (double)(255 - paper[ch]) / (double)v[ch];
        else
            continue;
        if (limit < t)
            t = limit;
    }
    if (t < 1.0)
        t = 1.0;
    for (ch = 0; ch < 3; ch++) {
        double c = (double)paper[ch] + t * (double)v[ch];
        color[ch] = c < 0.0 ? 0.0 : c > 255.0 ? 255.0 : c;
    }
    return 1.0 / t;
}

static double reground_spread(const double color[3])
{
    double hi = color[0], lo = color[0];
    int ch;
    for (ch = 1; ch < 3; ch++) {
        if (color[ch] > hi)
            hi = color[ch];
        if (color[ch] < lo)
            lo = color[ch];
    }
    return hi - lo;
}

static void rgb_of(uint32_t rgb, int c[3])
{
    c[0] = (int)((rgb >> 16) & 255U);
    c[1] = (int)((rgb >> 8) & 255U);
    c[2] = (int)(rgb & 255U);
}

static int64_t reground_run(const uint8_t *orig, uint8_t *out, int64_t count, int64_t width, int light)
{
    const uint32_t *p = (const uint32_t *)orig;
    uint32_t papers[REGROUND_LIGHT_PAPERS], texts[REGROUND_TEXTS];
    int npapers = 0, ntexts = 0, k, j, main_paper[3], main_ground[3], have_ground = 0, text_light[REGROUND_TEXTS];
    int64_t i, rows, written = 0, opaque = 0;
    if (count <= 0 || width <= 0 || count > MAX_INDEXED)
        return 0;
    rows = count / width;
    for (k = 0; k < REGROUND_TABLE; k++) {
        reground_keys[k] = 0;
        reground_counts[k] = 0;
    }
    for (i = 0; i < count; i++) {
        uint32_t key, h;
        int probe;
        if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        opaque++;
        key = (p[i] & 0xffffffU) | 0x1000000U;
        h = (uint32_t)(key * 2654435761U) >> 18;
        for (probe = 0; probe < REGROUND_TABLE; probe++, h = (h + 1) & (REGROUND_TABLE - 1)) {
            if (reground_keys[h] == key) {
                reground_counts[h]++;
                break;
            }
            if (reground_keys[h] == 0) {
                reground_keys[h] = key;
                reground_counts[h] = 1;
                break;
            }
        }
    }
    /* the papers, most frequent first, and the text colors */
    for (j = 0; j < (light ? REGROUND_LIGHT_PAPERS : REGROUND_PAPERS); j++) {
        int64_t best = -1;
        for (k = 0; k < REGROUND_TABLE; k++) {
            int c[3], m, taken = 0;
            if (!reground_keys[k] || (best >= 0 && reground_counts[k] <= reground_counts[best]))
                continue;
            if ((double)reground_counts[k] < REGROUND_PAPER_SHARE * (double)opaque)
                continue;
            for (m = 0; m < npapers; m++)
                taken |= papers[m] == (reground_keys[k] & 0xffffffU);
            rgb_of(reground_keys[k] & 0xffffffU, c);
            if (taken || lightness((uint8_t)c[0], (uint8_t)c[1], (uint8_t)c[2]) < REGROUND_PAPER_HLS)
                continue;
            best = k;
        }
        if (best < 0)
            break;
        papers[npapers++] = reground_keys[best] & 0xffffffU;
    }
    if (light) {
        /* a dark ground: FontLab drew the sample on the dark palette already, in the colors picked (Overlay Fonts'
         * preview, #e7e3d7 on #2d2d30: mapped, its letters came out dark olive on the dark ground, the owner's report
         * of 2026-11-26). There, a light color is a paper only if it runs across the picture on some line, as a
         * list's row does (its letters, frequent enough to pass for a paper, never do); with no paper left, the sample
         * is drawn as it is */
        int64_t best = -1;
        int c[3];
        for (k = 0; k < REGROUND_TABLE; k++)
            if (reground_keys[k] && (best < 0 || reground_counts[k] > reground_counts[best]))
                best = k;
        if (best >= 0) {
            rgb_of(reground_keys[best] & 0xffffffU, c);
            /* (mostly transparent: drawn on nothing, over what is behind it, the dark window; the effect's picture of
             * the preview) */
            if (2 * opaque < count || lightness((uint8_t)c[0], (uint8_t)c[1], (uint8_t)c[2]) < REGROUND_DARK_GROUND_HLS) {
                int kept = 0;
                for (j = 0; j < npapers; j++) {
                    int64_t run = 0, longest = 0;
                    for (i = 0; i < count; i++) {
                        if (i % width == 0)
                            run = 0;
                        run = ((p[i] >> 24) >= ANCHOR_MIN_ALPHA && (p[i] & 0xffffffU) == papers[j]) ? run + 1 : 0;
                        if (run > longest)
                            longest = run;
                    }
                    if ((double)longest >= REGROUND_PAPER_SPAN * (double)width)
                        papers[kept++] = papers[j];
                }
                npapers = kept;
                if (!npapers) {
                    for (i = 0; i < 4 * count; i++)
                        out[i] = orig[i];
                    return count;
                }
            }
        }
    }
    if (!npapers)
        return 0;
    if (light) {
        /* a candidate after the first whose edges blend into another is light text, frequent enough to pass for a
         * paper (large letters in the preview) */
        int kept = 1;
        for (k = 0; k < REGROUND_TABLE; k++)
            reground_asked[k] = 0;
        for (j = 1; j < npapers; j++) {
            int64_t at = reground_find(papers[j]);
            if (at >= 0)
                reground_asked[at] = 1;
        }
        reground_edges(p, count, width, papers, npapers);
        for (j = 1; j < npapers; j++) {
            int64_t at = reground_find(papers[j]);
            if (at >= 0 && reground_sits(at))
                continue;
            if (kept < REGROUND_PAPERS)
                papers[kept++] = papers[j];
        }
        npapers = kept;
    }
    rgb_of(papers[0], main_paper);
    if (light) {
        /* the colors that may be text by their shape: frequent, no paper, and not the picture's ground (its most
         * frequent color: a list's dark empty part, taken as a text color, made near-white text its smoothing) */
        int64_t ground_k = -1;
        for (k = 0; k < REGROUND_TABLE; k++)
            if (reground_keys[k] && (ground_k < 0 || reground_counts[k] > reground_counts[ground_k]))
                ground_k = k;
        for (k = 0; k < REGROUND_TABLE; k++) {
            int c[3], m, paper = 0;
            reground_asked[k] = 0;
            if (!reground_keys[k] || reground_counts[k] < REGROUND_TEXT_COUNT || k == ground_k)
                continue;
            for (m = 0; m < npapers; m++)
                paper |= papers[m] == (reground_keys[k] & 0xffffffU);
            rgb_of(reground_keys[k] & 0xffffffU, c);
            if (!paper)
                reground_asked[k] = 1; /* (any color: what the strong-color test below leaves, this one takes) */
        }
        reground_edges(p, count, width, papers, npapers);
        for (k = 0; k < REGROUND_TABLE; k++)
            reground_asked[k] = reground_asked[k] && reground_sits(k);
    }
    /* the text colors, most frequent first; a color on the line from the paper to one already taken is that
     * one's smoothing (a dark color's shades are strong and frequent too: taken in the table's order, they
     * filled the list, and runs of the text itself had no core near them: light pixels at its edges) */
    while (ntexts < REGROUND_TEXTS) {
        int64_t best = -1;
        for (k = 0; k < REGROUND_TABLE; k++) {
            int c[3], m, on_line = 0;
            double color[3];
            uint8_t q[4];
            if (!reground_keys[k] || reground_counts[k] < REGROUND_TEXT_COUNT
                || (best >= 0 && reground_counts[k] <= reground_counts[best]))
                continue;
            rgb_of(reground_keys[k] & 0xffffffU, c);
            q[2] = (uint8_t)c[0];
            q[1] = (uint8_t)c[1];
            q[0] = (uint8_t)c[2];
            if (((c[0] > c[1] ? (c[0] > c[2] ? c[0] : c[2]) : (c[1] > c[2] ? c[1] : c[2]))
                    - (c[0] < c[1] ? (c[0] < c[2] ? c[0] : c[2]) : (c[1] < c[2] ? c[1] : c[2])) < REGROUND_TEXT_SPREAD
                    || reground_unmix(q, main_paper, color) < REGROUND_TEXT_SHARE)
                    && !(light && reground_asked[k]))
                continue; /* (weak: a light text's only way in) */
            for (m = 0; m < ntexts && !on_line; m++) {
                int t[3], ch;
                double dot = 0.0, len = 0.0, share, fit = 0.0;
                rgb_of(texts[m], t);
                for (ch = 0; ch < 3; ch++) {
                    dot += (double)(c[ch] - main_paper[ch]) * (double)(t[ch] - main_paper[ch]);
                    len += (double)(t[ch] - main_paper[ch]) * (double)(t[ch] - main_paper[ch]);
                }
                if (len <= 0.0 || (reground_keys[k] & 0xffffffU) == texts[m]) {
                    on_line = (reground_keys[k] & 0xffffffU) == texts[m];
                    continue;
                }
                share = dot / len;
                share = share < 0.0 ? 0.0 : share > 1.0 ? 1.0 : share;
                for (ch = 0; ch < 3; ch++) {
                    double d = (double)(c[ch] - main_paper[ch]) - share * (double)(t[ch] - main_paper[ch]);
                    fit += d * d;
                }
                on_line = fit <= reground_tolerance(len, light);
                if (light && on_line) {
                    /* near the paper, every line from it passes close: within a share of its own distance (a
                     * near-white text color counted as the smoothing of the pill's gray, taken first) */
                    double own = 0.0;
                    for (ch = 0; ch < 3; ch++)
                        own += (double)(c[ch] - main_paper[ch]) * (double)(c[ch] - main_paper[ch]);
                    on_line = fit <= reground_tolerance(own, 1);
                }
            }
            if (!on_line)
                best = k;
        }
        if (best < 0)
            break;
        texts[ntexts++] = reground_keys[best] & 0xffffffU;
        reground_counts[best] = -reground_counts[best]; /* (taken: out of the next rounds) */
    }
    for (k = 0; k < REGROUND_TABLE; k++)
        if (reground_counts[k] < 0)
            reground_counts[k] = -reground_counts[k];
    if (!ntexts)
        return 0;
    for (k = 0; k < ntexts; k++) {
        int c[3], hi, lo;
        uint8_t q[4];
        double color[3];
        rgb_of(texts[k], c);
        q[2] = (uint8_t)c[0];
        q[1] = (uint8_t)c[1];
        q[0] = (uint8_t)c[2];
        hi = c[0] > c[1] ? (c[0] > c[2] ? c[0] : c[2]) : (c[1] > c[2] ? c[1] : c[2]);
        lo = c[0] < c[1] ? (c[0] < c[2] ? c[0] : c[2]) : (c[1] < c[2] ? c[1] : c[2]);
        text_light[k] = light && (hi - lo < REGROUND_TEXT_SPREAD || reground_unmix(q, main_paper, color) < REGROUND_TEXT_SHARE);
    }
    for (i = 0; i < count && !have_ground; i++) {
        if ((p[i] >> 24) >= ANCHOR_MIN_ALPHA && (p[i] & 0xffffffU) == papers[0]) {
            main_ground[0] = out[4 * i + 2];
            main_ground[1] = out[4 * i + 1];
            main_ground[2] = out[4 * i];
            have_ground = 1;
        }
    }
    if (!have_ground)
        return 0;
    /* a core: a pixel on a text color's line from the main paper, at half its share at least (the text's own
     * pixels are not all of one color: a lighter shade along a G's bar, four pixels from the nearest of the exact
     * color, came out light) */
    for (i = 0; i < count; i++) {
        int paper_pixel = 0;
        reground_core[i] = 0;
        if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        for (k = 0; k < npapers; k++)
            paper_pixel |= (p[i] & 0xffffffU) == papers[k];
        if (paper_pixel)
            continue;
        if (i > 0 && p[i] == p[i - 1]) {
            reground_core[i] = reground_core[i - 1]; /* (the pixel before's answer: runs of one color) */
            continue;
        }
        for (k = 0; k < ntexts && !reground_core[i]; k++) {
            int t[3], v[3], ch;
            double dot = 0.0, len = 0.0, share, fit = 0.0;
            rgb_of(texts[k], t);
            v[0] = (int)orig[4 * i + 2] - main_paper[0];
            v[1] = (int)orig[4 * i + 1] - main_paper[1];
            v[2] = (int)orig[4 * i] - main_paper[2];
            for (ch = 0; ch < 3; ch++) {
                dot += (double)v[ch] * (double)(t[ch] - main_paper[ch]);
                len += (double)(t[ch] - main_paper[ch]) * (double)(t[ch] - main_paper[ch]);
            }
            if (len <= 0.0)
                continue;
            share = dot / len;
            if (share < REGROUND_TEXT_SHARE)
                continue;
            share = share > 1.0 ? 1.0 : share;
            for (ch = 0; ch < 3; ch++) {
                double d = (double)v[ch] - share * (double)(t[ch] - main_paper[ch]);
                fit += d * d;
            }
            if (fit <= reground_tolerance(len, light))
                reground_core[i] = text_light[k] ? 2 : 1;
        }
    }
    if (light) {
        /* a light text's core is one only where it reaches a paper, at once or through other such cores: a pill's
         * white name has light blends of its own on a light text's short line (dark blocks in "Sarabun Regular" on
         * the pill), and sits on the pill's gray, not on the paper; a large letter's inside reaches it through its
         * edge */
        int64_t changed = 1;
        int pass;
        for (i = 0; i < count; i++) {
            int64_t x = i % width, y = i / width, xx, yy;
            int reach = 0;
            if (reground_core[i] != 2)
                continue;
            for (yy = y - REGROUND_REACH; yy <= y + REGROUND_REACH && !reach; yy++)
                for (xx = x - REGROUND_REACH; xx <= x + REGROUND_REACH && !reach; xx++) {
                    int64_t n;
                    if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                        continue;
                    n = yy * width + xx;
                    if ((p[n] >> 24) < ANCHOR_MIN_ALPHA)
                        continue;
                    for (k = 0; k < npapers && !reach; k++)
                        reach = (p[n] & 0xffffffU) == papers[k];
                }
            if (reach)
                reground_core[i] = 3; /* (reaches a paper) */
        }
        for (pass = 0; pass < REGROUND_LIGHT_PASSES && changed; pass++) {
            changed = 0;
            for (i = 0; i < count; i++) /* down and right */
                if (reground_core[i] == 2 && ((i % width > 0 && reground_core[i - 1] == 3)
                                              || (i >= width && reground_core[i - width] == 3))) {
                    reground_core[i] = 3;
                    changed++;
                }
            for (i = count - 1; i >= 0; i--) /* up and left */
                if (reground_core[i] == 2 && ((i % width < width - 1 && reground_core[i + 1] == 3)
                                              || (i + width < count && reground_core[i + width] == 3))) {
                    reground_core[i] = 3;
                    changed++;
                }
        }
        /* and each group of such cores is strokes, not a solid block: a gray pick near the pill's gray took the pill
         * as text, and its name broke (no color tells them apart when the pick is the pill's gray; the shape does) */
        /* and lies on the paper: around a letter is paper, or smoothing from the paper toward its own color (the
         * pill's smoothed rim, as light as a #c0c0c0 pick, has the pill's gray on its inner side) */
        for (i = 0; i < count; i++) {
            int64_t head = 0, n = 0, inner = 0, papered = 0, other = 0, m;
            if (reground_core[i] != 3)
                continue;
            reground_core[i] = 5; /* (in the group being found) */
            reground_group[n++] = (int32_t)i;
            while (head < n) {
                int64_t j = reground_group[head++], x = j % width, y = j / width;
                int d, around = 0, own[3];
                rgb_of(p[j] & 0xffffffU, own);
                for (d = 0; d < 4; d++) {
                    int64_t xx = x + (d == 0) - (d == 1), yy = y + (d == 2) - (d == 3), q;
                    int ch, on = 0;
                    if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                        continue;
                    q = yy * width + xx;
                    if (reground_core[q] == 3) {
                        reground_core[q] = 5;
                        reground_group[n++] = (int32_t)q;
                    }
                    if (reground_core[q] == 5) {
                        around++;
                        continue;
                    }
                    if ((p[q] >> 24) >= ANCHOR_MIN_ALPHA) {
                        int near[3];
                        double dot = 0.0, len = 0.0, share, fit = 0.0;
                        for (k = 0; k < npapers && !on; k++)
                            on = (p[q] & 0xffffffU) == papers[k];
                        rgb_of(p[q] & 0xffffffU, near);
                        for (ch = 0; ch < 3 && !on; ch++) {
                            dot += (double)(near[ch] - main_paper[ch]) * (double)(own[ch] - main_paper[ch]);
                            len += (double)(own[ch] - main_paper[ch]) * (double)(own[ch] - main_paper[ch]);
                        }
                        if (!on && len > 0.0) {
                            share = dot / len;
                            for (ch = 0; ch < 3; ch++) {
                                double dd = (double)(near[ch] - main_paper[ch]) - share * (double)(own[ch] - main_paper[ch]);
                                fit += dd * dd;
                            }
                            on = share > -0.05 && share <= 1.05 && fit <= reground_tolerance(len, 1);
                        }
                        on = on || reground_core[q] == 1;
                    }
                    if (on)
                        papered++;
                    else
                        other++;
                }
                if (around == 4)
                    inner++;
            }
            for (m = 0; m < n; m++)
                reground_core[reground_group[m]] = ((double)inner > REGROUND_LIGHT_SOLID * (double)n
                    || (double)papered < REGROUND_LIGHT_ON_PAPER * (double)(papered + other)) ? 2 : 4;
        }
        for (i = 0; i < count; i++)
            reground_core[i] = reground_core[i] == 1 || reground_core[i] == 4;
    }
    for (i = 0; i < count; i++) {
        int64_t x = i % width, y = i / width, xx, yy, nearest = -1;
        int near = 0, ch, paper[3], ground[3], best_text = -1, is_paper = 0, dist = 1 << 30;
        double best_fit = 1e18, best_share = 0.0, best_tol = 0.0;
        uint32_t c = p[i] & 0xffffffU;
        if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        for (k = 0; k < npapers; k++)
            is_paper |= c == papers[k];
        if (is_paper)
            continue;
        for (yy = y - REGROUND_REACH; yy <= y + REGROUND_REACH && !near; yy++)
            for (xx = x - REGROUND_REACH; xx <= x + REGROUND_REACH && !near; xx++)
                if (xx >= 0 && xx < width && yy >= 0 && yy < rows && reground_core[yy * width + xx])
                    near = 1;
        if (!near)
            continue;
        /* its paper: the nearest pixel of a paper color, mapped as that pixel was */
        for (yy = y - REGROUND_PAPER_REACH; yy <= y + REGROUND_PAPER_REACH; yy++)
            for (xx = x - REGROUND_PAPER_REACH; xx <= x + REGROUND_PAPER_REACH; xx++) {
                int64_t n;
                int d;
                if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                    continue;
                n = yy * width + xx;
                if ((p[n] >> 24) < ANCHOR_MIN_ALPHA)
                    continue;
                d = (int)((xx - x) * (xx - x) + (yy - y) * (yy - y));
                if (d >= dist)
                    continue;
                for (k = 0; k < npapers; k++)
                    if ((p[n] & 0xffffffU) == papers[k]) {
                        dist = d;
                        nearest = n;
                    }
            }
        if (nearest >= 0) {
            rgb_of(p[nearest] & 0xffffffU, paper);
            ground[0] = out[4 * nearest + 2];
            ground[1] = out[4 * nearest + 1];
            ground[2] = out[4 * nearest];
        } else {
            for (ch = 0; ch < 3; ch++) {
                paper[ch] = main_paper[ch];
                ground[ch] = main_ground[ch];
            }
        }
        /* the text color whose line from the paper passes nearest the pixel */
        for (k = 0; k < ntexts; k++) {
            int t[3], v[3];
            double dot = 0.0, len = 0.0, share, fit = 0.0;
            rgb_of(texts[k], t);
            v[0] = (int)orig[4 * i + 2] - paper[0];
            v[1] = (int)orig[4 * i + 1] - paper[1];
            v[2] = (int)orig[4 * i] - paper[2];
            for (ch = 0; ch < 3; ch++) {
                dot += (double)v[ch] * (double)(t[ch] - paper[ch]);
                len += (double)(t[ch] - paper[ch]) * (double)(t[ch] - paper[ch]);
            }
            if (len <= 0.0)
                continue;
            share = dot / len;
            share = share < 0.0 ? 0.0 : share > 1.0 ? 1.0 : share;
            for (ch = 0; ch < 3; ch++) {
                double d = (double)v[ch] - share * (double)(t[ch] - paper[ch]);
                fit += d * d;
            }
            if (fit < best_fit) {
                best_fit = fit;
                best_text = k;
                best_share = share;
                best_tol = reground_tolerance(len, light);
            }
        }
        if (best_text >= 0 && best_fit <= best_tol) {
            int t[3];
            rgb_of(texts[best_text], t);
            for (ch = 0; ch < 3; ch++) {
                double o = (double)ground[ch] + best_share * (double)(t[ch] - ground[ch]);
                out[4 * i + 2 - ch] = (uint8_t)(o < 0.0 ? 0.0 : o > 255.0 ? 255.0 : o + 0.5);
            }
            written++;
        } else {
            double color[3], share = reground_unmix(orig + 4 * i, paper, color);
            if (share <= 0.0)
                continue;
            if (reground_spread(color) < REGROUND_TEXT_SPREAD) {
                /* a pixel beside a text color's core that neither fits its line nor is a color of its own (a
                 * shade's smoothing over another ground): left to the mapping, it came out a light pixel at the
                 * text's edge (the owner, 2026-11-25: "white pixels bleeding"); drawn on that line instead */
                int t[3];
                if (best_text < 0)
                    continue;
                rgb_of(texts[best_text], t);
                for (ch = 0; ch < 3; ch++) {
                    double o = (double)ground[ch] + best_share * (double)(t[ch] - ground[ch]);
                    out[4 * i + 2 - ch] = (uint8_t)(o < 0.0 ? 0.0 : o > 255.0 ? 255.0 : o + 0.5);
                }
                written++;
                continue;
            }
            for (ch = 0; ch < 3; ch++) {
                double o = (double)ground[ch] + share * (color[ch] - (double)ground[ch]);
                out[4 * i + 2 - ch] = (uint8_t)(o < 0.0 ? 0.0 : o > 255.0 ? 255.0 : o + 0.5);
            }
            written++;
        }
    }
    return written;
}

EXPORT int64_t freelab_reground(const uint8_t *orig, uint8_t *out, int64_t count, int64_t width)
{
    return reground_run(orig, out, count, width, 0);
}

/* The same, light text included (see REGROUND_LIGHT_PAPERS): for the widgets that show samples only. */
EXPORT int64_t freelab_reground_light(const uint8_t *orig, uint8_t *out, int64_t count, int64_t width)
{
    return reground_run(orig, out, count, width, 1);
}

/* Light text on a band of a strong color, on a canvas (a selected cell's name, white on the selection's blue):
 * ClearType's colored edges were kept, and the mapping turned a few of the letters' pixels dark (the owner,
 * 2026-11-25: "degree" fringed, with a black pixel in its g). Each pixel with the band's color within reach on
 * its four sides, and lighter than the band, is drawn again from its coverage: its channels' mean share of the
 * way from the band's color to white, in gray between the two. A band color: a strong color (BAND_TEXT_SPREAD)
 * in runs of BAND_TEXT_RUN pixels along a row. `orig` is the picture as drawn, `out` the same picture mapped;
 * returns how many pixels were drawn again. */
#define BAND_TEXT_COLORS 4
#define BAND_TEXT_SPREAD 60
#define BAND_TEXT_RUN 24
#define BAND_TEXT_REACH_ACROSS 48
#define BAND_TEXT_REACH 10
#define BAND_TEXT_STEP 0.05 /* HLS: the text lighter than its band by this much at least */

static int band_text_reaches(const uint32_t *p, int64_t i, int64_t width, int64_t rows, uint32_t band)
{
    int64_t x = i % width, y = i / width, k;
    int dir;
    for (dir = 0; dir < 4; dir++) {
        int64_t sx = dir == 0 ? 1 : dir == 1 ? -1 : 0, sy = dir == 2 ? 1 : dir == 3 ? -1 : 0;
        int64_t reach = sx ? BAND_TEXT_REACH_ACROSS : BAND_TEXT_REACH;
        int found = 0;
        for (k = 1; k <= reach && !found; k++) {
            int64_t xx = x + sx * k, yy = y + sy * k;
            if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                break;
            found = (p[yy * width + xx] & 0xffffffU) == band;
        }
        if (!found)
            return 0;
    }
    return 1;
}

#define BAND_TEXT_MAX_ROWS 65536
static int32_t band_rows_before[BAND_TEXT_MAX_ROWS + 1]; /* rows above y holding a band pixel: a prefix count */

EXPORT int64_t freelab_band_text(const uint8_t *orig, uint8_t *out, int64_t count, int64_t width)
{
    const uint32_t *p = (const uint32_t *)orig;
    uint32_t bands[BAND_TEXT_COLORS];
    int nbands = 0, k;
    int64_t i, y, x, rows, written = 0;
    if (count <= 0 || width <= 0)
        return 0;
    rows = count / width;
    if (rows > BAND_TEXT_MAX_ROWS)
        return 0;
    for (y = 0; y < rows && nbands < BAND_TEXT_COLORS; y++) {
        int64_t run = 1;
        for (x = 1; x <= width && nbands < BAND_TEXT_COLORS; x++) {
            uint32_t prev = p[y * width + x - 1];
            if (x < width && p[y * width + x] == prev) {
                run++;
                continue;
            }
            if (run >= BAND_TEXT_RUN && (prev >> 24) >= ANCHOR_MIN_ALPHA) {
                uint8_t q[3];
                int known = 0;
                q[0] = (uint8_t)prev;
                q[1] = (uint8_t)(prev >> 8);
                q[2] = (uint8_t)(prev >> 16);
                for (k = 0; k < nbands; k++)
                    known |= bands[k] == (prev & 0xffffffU);
                if (!known && spread_of(q) >= BAND_TEXT_SPREAD)
                    bands[nbands++] = prev & 0xffffffU;
            }
            run = 1;
        }
    }
    if (!nbands)
        return 0;
    /* only rows with a band pixel, and one within reach above and below, are looked at: walked from every
     * pixel, a cell chart took 115 ms, more than its mapping (the owner, 2026-11-25: FontLab stopped answering
     * as a color was dragged in Overlay Fonts, both Font windows repainting at each step) */
    band_rows_before[0] = 0;
    for (y = 0; y < rows; y++) {
        int has = 0;
        for (x = 0; x < width && !has; x++)
            for (k = 0; k < nbands && !has; k++)
                has = (p[y * width + x] & 0xffffffU) == bands[k];
        band_rows_before[y + 1] = band_rows_before[y] + has;
    }
    for (i = 0; i < count; i++) {
        uint32_t c = p[i] & 0xffffffU;
        int r = (int)((c >> 16) & 255U), g = (int)((c >> 8) & 255U), b = (int)(c & 255U), on = -1;
        int64_t row = i / width, up = row - BAND_TEXT_REACH < 0 ? 0 : row - BAND_TEXT_REACH;
        int64_t down = row + BAND_TEXT_REACH + 1 > rows ? rows : row + BAND_TEXT_REACH + 1;
        if (band_rows_before[row + 1] == band_rows_before[row] || band_rows_before[row] == band_rows_before[up]
            || band_rows_before[down] == band_rows_before[row + 1]) {
            i = (row + 1) * width - 1; /* (the rest of the row) */
            continue;
        }
        if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        for (k = 0; k < nbands && on < 0; k++)
            if (c != bands[k] && band_text_reaches(p, i, width, rows, bands[k]))
                on = k;
        if (on < 0)
            continue;
        {
            uint32_t band = bands[on];
            int br = (int)((band >> 16) & 255U), bg = (int)((band >> 8) & 255U), bb = (int)(band & 255U);
            double t = 0.0, o[3];
            int ch;
            if (lightness((uint8_t)r, (uint8_t)g, (uint8_t)b) < lightness((uint8_t)br, (uint8_t)bg, (uint8_t)bb) + BAND_TEXT_STEP)
                continue;
            t += br < 255 ? ((double)r - br) / (255.0 - br) : 1.0;
            t += bg < 255 ? ((double)g - bg) / (255.0 - bg) : 1.0;
            t += bb < 255 ? ((double)b - bb) / (255.0 - bb) : 1.0;
            t /= 3.0;
            t = t < 0.0 ? 0.0 : t > 1.0 ? 1.0 : t;
            o[0] = br + t * (255.0 - br);
            o[1] = bg + t * (255.0 - bg);
            o[2] = bb + t * (255.0 - bb);
            for (ch = 0; ch < 3; ch++)
                out[4 * i + 2 - ch] = (uint8_t)(o[ch] + 0.5);
            written++;
        }
    }
    return written;
}

/* An anchor's pill on a canvas, drawn again whole over the mapping: its gray as mapped, plain, and its name
 * from its coverage. The pill is translucent, and what runs under it (the baseline, a guide, a glyph's
 * contour, its fill) showed through it and across its name, which the pixel rules could not tell from the
 * letters (the owner, 2026-11-25: "anything that overlaps with contours or other elements makes it a mess").
 * A pill: pieces of one warm gray shade each (PILL_SHADE_STEP), the pill's two halves over the canvas' two
 * grounds and the pieces a line cuts it into, joined when they touch; PILL_MIN_HEIGHT to PILL_MAX_HEIGHT rows,
 * wider than tall. In each of its rows, between its first and last pixel of a shade, a pixel lighter than its
 * shade (PILL_TEXT_STEP) is the name, drawn from its share of the way from the shade to white; any other is
 * the pill. `orig` is the picture as drawn, `out` the same picture mapped; returns how many pills. */
#define PILL_MAX_PIECES 4096
#define PILL_SHADE_STEP 3 /* per channel: a piece's pixels, against its first */
#define PILL_JOIN_GAP 3 /* pixels: pieces this near are one pill */
#define PILL_JOIN_SHADES 16 /* per channel: and their shades this near */
#define PILL_MIN_HEIGHT 9
#define PILL_MAX_HEIGHT 26
#define PILL_MIN_WIDTH 16
#define PILL_PIECE_MIN_WIDTH 6
#define PILL_PIECE_FILL 0.4 /* a piece fills its box this much at least (the name's letters are holes in it) */
#define PILL_TEXT_STEP 0.06 /* HLS */
#define PILL_REF_REACH 48

typedef struct {
    int x0, y0, x1, y1, parent, keep, warm;
    int64_t n, first;
    uint32_t color;
} PillPiece;

static int32_t pill_label[MAX_INDEXED]; /* the piece a pixel is in, + 1 (0: none) */
static int32_t pill_stack[MAX_INDEXED];
static int32_t pill_members[MAX_INDEXED]; /* the pixels of the piece being found, but its first */
static PillPiece pill_pieces[PILL_MAX_PIECES + 1]; /* (the last: "looked at, no piece", never kept) */

/* 2 for a warm gray (a pill's own), 1 for a near neutral one (the translucent pill over the template glyphs' purple
 * grays: #9c9a9a beside #a09e9c, the owner's report of 2026-11-26: the name broke over that half only), 0 for
 * neither. The pill is as dark as PILL_MIN_HLS while its anchor is under the mouse (#7e7a72, opaque). */
#define PILL_MIN_HLS 0.42
#define PILL_NEUTRAL_STEP 4 /* per channel, between any two: a near neutral gray */
#define PILL_NEUTRAL_MIN_HEIGHT 3 /* rows: a near neutral piece is part of a pill's body (a dashed line's is 1) */
static int pill_shade(uint32_t px)
{
    int r = (int)((px >> 16) & 255U), g = (int)((px >> 8) & 255U), b = (int)(px & 255U);
    double l;
    if ((px >> 24) < ANCHOR_MIN_ALPHA)
        return 0;
    l = lightness((uint8_t)r, (uint8_t)g, (uint8_t)b);
    if (l < PILL_MIN_HLS || l > 0.8)
        return 0;
    if (r >= g && g >= b && r - b >= 3 && r - b <= 14)
        return 2;
    /* (the template glyphs' own grays lean blue: #c3c3cb, and they are no pill) */
    return b <= r + 1 && (r > g ? r - g : g - r) <= PILL_NEUTRAL_STEP && (g > b ? g - b : b - g) <= PILL_NEUTRAL_STEP
        && (r > b ? r - b : b - r) <= PILL_NEUTRAL_STEP;
}

static int pill_near(uint32_t a, uint32_t b, int step)
{
    int ch;
    for (ch = 0; ch < 3; ch++) {
        int d = (int)((a >> (8 * ch)) & 255U) - (int)((b >> (8 * ch)) & 255U);
        if (d > step || d < -step)
            return 0;
    }
    return 1;
}

static int pill_root(int k)
{
    while (pill_pieces[k].parent != k)
        k = pill_pieces[k].parent = pill_pieces[pill_pieces[k].parent].parent;
    return k;
}

EXPORT int64_t freelab_pills(const uint8_t *orig, uint8_t *out, int64_t count, int64_t width)
{
    const uint32_t *p = (const uint32_t *)orig;
    int64_t i, rows, pills = 0, members = 0;
    int npieces = 0, a, b;
    if (count <= 0 || width <= 0 || count > MAX_INDEXED)
        return 0;
    rows = count / width;
    pill_pieces[PILL_MAX_PIECES].keep = 0;
    pill_pieces[PILL_MAX_PIECES].warm = 0;
    pill_pieces[PILL_MAX_PIECES].parent = PILL_MAX_PIECES;
    for (i = 0; i < count; i++)
        pill_label[i] = 0;
    /* pieces: 4-connected pixels of one shade */
    for (i = 0; i < count && npieces < PILL_MAX_PIECES; i++) {
        int64_t top = 0;
        PillPiece *pc;
        if (pill_label[i] || !pill_shade(p[i]))
            continue;
        pc = &pill_pieces[npieces];
        members = 0;
        pc->x0 = pc->x1 = (int)(i % width);
        pc->y0 = pc->y1 = (int)(i / width);
        pc->n = 0;
        pc->first = i;
        pc->color = p[i] & 0xffffffU;
        pc->parent = npieces;
        pc->keep = 0;
        pc->warm = pill_shade(p[i]) == 2;
        pill_label[i] = npieces + 1;
        pill_stack[top++] = (int32_t)i;
        while (top > 0) {
            int64_t j = pill_stack[--top], x = j % width, y = j / width;
            int dir;
            pc->n++;
            if (x < pc->x0) pc->x0 = (int)x;
            if (x > pc->x1) pc->x1 = (int)x;
            if (y < pc->y0) pc->y0 = (int)y;
            if (y > pc->y1) pc->y1 = (int)y;
            for (dir = 0; dir < 4; dir++) {
                int64_t xx = x + (dir == 0 ? 1 : dir == 1 ? -1 : 0), yy = y + (dir == 2 ? 1 : dir == 3 ? -1 : 0), q;
                if (xx < 0 || xx >= width || yy < 0 || yy >= rows)
                    continue;
                q = yy * width + xx;
                if (pill_label[q] || !pill_shade(p[q]) || !pill_near(p[q] & 0xffffffU, pc->color, PILL_SHADE_STEP))
                    continue;
                pill_label[q] = npieces + 1;
                pill_stack[top++] = (int32_t)q;
                pill_members[members++] = (int32_t)q;
            }
        }
        {
            int w = pc->x1 - pc->x0 + 1, h = pc->y1 - pc->y0 + 1;
            pc->keep = w >= PILL_PIECE_MIN_WIDTH && h <= PILL_MAX_HEIGHT && (double)pc->n >= PILL_PIECE_FILL * w * h
                && (pc->warm || h >= PILL_NEUTRAL_MIN_HEIGHT);
        }
        if (!pc->keep) {
            /* no part of a pill: its pixels marked as looked at, its slot given back (the canvas' smoothed gray lines
             * are near neutral pieces by the thousand, and filled the slots before the scan reached a pill lower
             * down: "b.uni0326" on the baseline was missed) */
            int64_t m;
            pill_label[i] = PILL_MAX_PIECES + 1;
            for (m = 0; m < members; m++)
                pill_label[pill_members[m]] = PILL_MAX_PIECES + 1;
            continue;
        }
        npieces++;
    }
    /* a near neutral piece is kept only beside a warm one it could be joined to (no chain of neutral pieces) */
    for (a = 0; a < npieces; a++) {
        PillPiece *pa = &pill_pieces[a];
        int beside = 0;
        if (!pa->keep || pa->warm)
            continue;
        for (b = 0; b < npieces && !beside; b++) {
            PillPiece *pb = &pill_pieces[b];
            if (b == a || !pb->keep || !pb->warm)
                continue;
            beside = !(pb->y0 - pa->y1 > PILL_JOIN_GAP || pa->y0 - pb->y1 > PILL_JOIN_GAP
                       || pb->x0 - pa->x1 > PILL_JOIN_GAP || pa->x0 - pb->x1 > PILL_JOIN_GAP)
                && pill_near(pa->color, pb->color, PILL_JOIN_SHADES);
        }
        if (!beside)
            pa->keep = 0;
    }
    for (a = 0; a < npieces; a++)
        for (b = a + 1; b < npieces; b++) {
            PillPiece *pa = &pill_pieces[a], *pb = &pill_pieces[b];
            if (!pa->keep || !pb->keep)
                continue;
            if (pb->y0 - pa->y1 > PILL_JOIN_GAP || pa->y0 - pb->y1 > PILL_JOIN_GAP
                || pb->x0 - pa->x1 > PILL_JOIN_GAP || pa->x0 - pb->x1 > PILL_JOIN_GAP
                || !pill_near(pa->color, pb->color, PILL_JOIN_SHADES))
                continue;
            pill_pieces[pill_root(b)].parent = pill_root(a);
        }
    for (a = 0; a < npieces; a++) {
        int x0 = 1 << 30, y0 = 1 << 30, x1 = -1, y1 = -1, main = -1, y, warm = 0;
        int64_t main_n = 0;
        uint8_t ground[3];
        if (!pill_pieces[a].keep || pill_root(a) != a)
            continue;
        for (b = 0; b < npieces; b++) {
            PillPiece *pb = &pill_pieces[b];
            if (!pb->keep || pill_root(b) != a)
                continue;
            if (pb->x0 < x0) x0 = pb->x0;
            if (pb->y0 < y0) y0 = pb->y0;
            if (pb->x1 > x1) x1 = pb->x1;
            if (pb->y1 > y1) y1 = pb->y1;
            if (pb->n > main_n) {
                main_n = pb->n;
                main = b;
            }
            warm |= pb->warm;
        }
        if (!warm) /* (a pill has a warm part: near neutral grays alone are the canvas' own) */
            continue;
        if (main < 0 || y1 - y0 + 1 < PILL_MIN_HEIGHT || y1 - y0 + 1 > PILL_MAX_HEIGHT || x1 - x0 + 1 < PILL_MIN_WIDTH
            || x1 - x0 < y1 - y0)
            continue;
        ground[0] = out[4 * pill_pieces[main].first];
        ground[1] = out[4 * pill_pieces[main].first + 1];
        ground[2] = out[4 * pill_pieces[main].first + 2];
        for (y = y0; y <= y1; y++) {
            int left = -1, right = -1, x, s, ends[3][2];
            /* the row's span: its own pill pixels, widened to the rows above and below where both reach
             * further (a line along the row, under the pill's end: the anchor's own line, the baseline) */
            for (s = 0; s < 3; s++) {
                int yy = y - 1 + s;
                ends[s][0] = 1 << 30;
                ends[s][1] = -1;
                if (yy < y0 || yy > y1)
                    continue;
                for (x = x0; x <= x1; x++) {
                    int32_t l = pill_label[(int64_t)yy * width + x];
                    if (l && pill_pieces[l - 1].keep && pill_root(l - 1) == a) {
                        if (x < ends[s][0])
                            ends[s][0] = x;
                        ends[s][1] = x;
                    }
                }
            }
            left = ends[1][0];
            right = ends[1][1];
            if (ends[0][1] >= 0 && ends[2][1] >= 0) {
                int reach_left = ends[0][0] > ends[2][0] ? ends[0][0] : ends[2][0];
                int reach_right = ends[0][1] < ends[2][1] ? ends[0][1] : ends[2][1];
                if (right < 0 || reach_left < left)
                    left = reach_left;
                if (right < 0 || reach_right > right)
                    right = reach_right;
            }
            if (right < 0 || left > right)
                continue;
            for (x = left; x <= right; x++) {
                int64_t j = (int64_t)y * width + x;
                uint32_t v = p[j];
                int32_t l = pill_label[j];
                uint32_t ref = pill_pieces[main].color;
                int ch, k;
                double t = 0.0;
                if (!(l && pill_pieces[l - 1].keep && pill_root(l - 1) == a)) {
                    /* the shade under the pixel: the nearest of the pill's pixels along its row */
                    for (k = 1; k <= PILL_REF_REACH; k++) {
                        int found = 0, s;
                        for (s = -1; s <= 1 && !found; s += 2) {
                            int xx = x + s * k;
                            int32_t m;
                            if (xx < x0 || xx > x1)
                                continue;
                            m = pill_label[(int64_t)y * width + xx];
                            if (m && pill_pieces[m - 1].keep && pill_root(m - 1) == a) {
                                ref = pill_pieces[m - 1].color;
                                found = 1;
                            }
                        }
                        if (found)
                            break;
                    }
                    if (lightness((uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v)
                        >= lightness((uint8_t)(ref >> 16), (uint8_t)(ref >> 8), (uint8_t)ref) + PILL_TEXT_STEP) {
                        for (ch = 0; ch < 3; ch++) {
                            double c = (double)((v >> (8 * ch)) & 255U), r = (double)((ref >> (8 * ch)) & 255U);
                            t += (r < 255.0 ? (c - r) / (255.0 - r) : 1.0) / 3.0;
                        }
                        t = t < 0.0 ? 0.0 : t > 1.0 ? 1.0 : t;
                    }
                }
                for (ch = 0; ch < 3; ch++)
                    out[4 * j + ch] = (uint8_t)((double)ground[ch] + t * (255.0 - (double)ground[ch]) + 0.5);
            }
        }
        pills++;
    }
    return pills;
}

/* Dark text ClearType drew on a light ground, in an island of the interface (the Fonts panel's names, black
 * on its near-white list): each pixel of a stroke's edges made the gray of its darkest channel, before the
 * island is mapped. Mapped with their colors, the edges came out orange and blue around the light text, with
 * a channel darker than the dark ground, which the defringe pass after keeps (the owner, 2026-11-25). The
 * pixels are judged as drawn, then changed; returns how many were. */
static uint8_t gray_ct_mark[MAX_INDEXED];

/* Whether a flat surface of a strong color lies within GRAY_CT_SURFACE_REACH of a pixel: a pixel of
 * GRAY_CT_SURFACE_SPREAD or more whose four neighbors are its color. On one (the Fonts panel's light-blue disc
 * around a selected style's letter), the disc's own pixels beside the letter were made the gray of their channels
 * and came out a gray block beside the "R" (the owner, 2026-11-25); ClearType's fringes are strong colors too,
 * but never flat. */
#define GRAY_CT_SURFACE_REACH 3
#define GRAY_CT_SURFACE_SPREAD 60
static int on_colored_surface(const uint32_t *p, int64_t i, int64_t width, int64_t count)
{
    int64_t x = i % width, y = i / width, rows = count / width, xx, yy;
    for (yy = y - GRAY_CT_SURFACE_REACH; yy <= y + GRAY_CT_SURFACE_REACH; yy++)
        for (xx = x - GRAY_CT_SURFACE_REACH; xx <= x + GRAY_CT_SURFACE_REACH; xx++) {
            uint32_t c;
            uint8_t q[3];
            if (xx < 1 || xx >= width - 1 || yy < 1 || yy >= rows - 1)
                continue;
            c = p[yy * width + xx];
            q[0] = (uint8_t)c;
            q[1] = (uint8_t)(c >> 8);
            q[2] = (uint8_t)(c >> 16);
            if (spread_of(q) < GRAY_CT_SURFACE_SPREAD)
                continue;
            if (p[yy * width + xx - 1] == c && p[yy * width + xx + 1] == c && p[(yy - 1) * width + xx] == c
                && p[(yy + 1) * width + xx] == c)
                return 1;
        }
    return 0;
}

EXPORT int64_t freelab_gray_cleartype(uint8_t *pixels, int64_t count, int64_t width)
{
    uint32_t *p = (uint32_t *)pixels;
    int64_t i, changed = 0;
    if (width <= 0 || count > MAX_INDEXED)
        return 0;
    dark_text_white_ok = 1;
    for (i = 0; i < count; i++)
        gray_ct_mark[i] = (uint8_t)((p[i] >> 24) >= ANCHOR_MIN_ALPHA && cleartype_fringe(p, i, width, count)
                                    && dark_text_fringe(p, i, width, count) && !on_colored_surface(p, i, width, count));
    dark_text_white_ok = 0;
    for (i = 0; i < count; i++) {
        uint8_t *px = pixels + 4 * i;
        if (gray_ct_mark[i]) {
            px[0] = px[1] = px[2] = (uint8_t)((px[0] + px[1] + px[2] + 1) / 3); /* (the channels' mean: the darkest made the names bold) */
            changed++;
        }
    }
    return changed;
}

EXPORT int64_t freelab_map_anchors(uint8_t *pixels, int64_t count, int64_t width, int mode, double dark_l,
                                   double light_l, double keep_tint, double main_default, int apply)
{
    uint32_t *p = (uint32_t *)pixels;
    uint32_t last_in = 0, last_out = 0;
    int have_last = 0, any_mapped = 0, j, local, tinted, last_edge = 0, glyph_icons = 0;
    uint32_t paper_bit, other_surfaces, other_surface_bits;
    int white_marks = 0, fringes = 0, bands = 0, thin, badge, darkened = 0, plain_marks = 0;
    uint32_t left_orig = 0, text;
    double paper_hls;
    int64_t i, changed = 0;
    mode_icon_fallback = mode == ANCHORS_SUBPIXEL_SYNTAX;
    mode_list = mode == ANCHORS_INK_LIST;
    if (mode_list)
        mode = ANCHORS_INK;
    if (mode_icon_fallback)
        mode = ANCHORS_SUBPIXEL;
    find_anchors(p, count, width, mode, dark_l, light_l, keep_tint, main_default);
    colored_anchor_bits = 0;
    for (j = 0; j < anchor_count && j < 32; j++) {
        uint8_t q[3];
        q[2] = (uint8_t)anchors[j].r;
        q[1] = (uint8_t)anchors[j].g;
        q[0] = (uint8_t)anchors[j].b;
        if (spread_of(q) > LINEAR_SPREAD)
            colored_anchor_bits |= 1U << j;
    }
    thin = mode_list && apply && width > 0 && count <= MAX_INDEXED; /* light ink's edges thinned after */
    for (i = 0; thin && i < count; i++)
        thin_px[i] = 0;
    for (j = 0; j < anchor_count; j++)
        any_mapped |= anchors[j].mapped;
    /* (a list on a dark paper may hold dark ink that is no anchor: see dark_list_ink) */
    any_mapped |= mode_list && anchor_count > 0 && anchors[0].surface && !anchors[0].mapped
                  && lightness((uint8_t)anchors[0].r, (uint8_t)anchors[0].g, (uint8_t)anchors[0].b) <= DARK_INK_PAPER_HLS;
    /* White marks and box edges are judged on the pixels as drawn, before any is mapped: mapped in
     * place first, a box's inside read as ink at its bottom and right edges. */
    white_marks = mode == ANCHORS_INK && width > 0 && count <= MAX_INDEXED;
    paper_hls = anchor_count > 0 && anchors[0].surface ? lightness((uint8_t)anchors[0].r, (uint8_t)anchors[0].g, (uint8_t)anchors[0].b) : 0.15;
    fringes = (mode == ANCHORS_ALL || mode == ANCHORS_ICON) && keep_tint > 0.0 && width > 0 && count <= MAX_INDEXED;
    bands = fringes && find_bands(p, count, width);
    text = fringes ? colored_text_color(p, count) : 0x1000000U;
    if (text <= 0xffffffU) {
        uint32_t mapped_text = resolve(text, 0, 0U, mode, dark_l, light_l, keep_tint, 0.0) & 0xffffffU;
        int moved = 0, ch;
        for (ch = 0; ch < 3; ch++) {
            int d = (int)((mapped_text >> (8 * ch)) & 255U) - (int)((text >> (8 * ch)) & 255U);
            moved += d < 0 ? -d : d;
        }
        if (moved < COLORED_CT_MIN_MOVE)
            text = 0x1000000U; /* kept as it is: a surface (the Font window's selected cell), not text */
    }
    for (i = 0; fringes && i < count; i++) { /* on the pixels as drawn, before any is mapped */
        white_mark[i] = 0;
        if ((p[i] >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        if (colored_cleartype(p, i, width, count, text)) {
            white_mark[i] = COLORED_CT_MARK; /* colored text's ClearType on white: drawn from the color found */
            colored_out[i] = colored_cleartype_color(p[i] & 0xffffffU, text, mode, dark_l, light_l, keep_tint)
                             | (p[i] & 0xff000000U);
        }
        else if (bands && light_on_kept_color(p, i, width, count))
            white_mark[i] = 4; /* light text on a colored surface the content keeps: kept as drawn */
        else if (cleartype_fringe(p, i, width, count))
            white_mark[i] = 3;
    }
    /* An island of the interface (everything mapped, no tint kept): light text on a strongly colored surface
     * stays as drawn, as content's does on a surface it keeps. The Fonts panel's style links are a light letter
     * on a light blue disc; turned over with the rest, the disc came out dark blue and the letter darker still
     * (the owner, 2026-11-24 and 25: "hard-to-read black text"). */
    plain_marks = (mode == ANCHORS_ALL || mode == ANCHORS_ICON) && !fringes && width > 0 && count <= MAX_INDEXED;
    band_plain = plain_marks;
    plain_marks = plain_marks && find_bands(p, count, width);
    for (i = 0; plain_marks && i < count; i++) {
        white_mark[i] = (uint8_t)((p[i] >> 24) >= ANCHOR_MIN_ALPHA && !(near_band[i] & NEAR_BAND)
                                  && light_on_kept_color(p, i, width, count));
    }
    band_plain = 0;
    badge_count = 0;
    badge_pill = fringes && !white_marks;
    if (white_marks || fringes) {
        find_badge_colors(mode, dark_l, light_l, keep_tint);
        if (badge_count)
            find_near_badges(p, count, width);
    }
    /* Content too (a canvas): light text on a gray badge, an anchor's name on its pill. Turned over with the
     * rest, the white name came out darker than its pill, and could not be read (the owner's review of
     * 2026-11-24). Found as in ink mode, over a fringe's mark, and drawn the same way: from the badge as it
     * comes out toward white. */
    for (i = 0; fringes && badge_count && i < count; i++) {
        uint32_t v = p[i];
        if ((v >> 24) < ANCHOR_MIN_ALPHA || white_mark[i] == 4 || white_mark[i] == COLORED_CT_MARK)
            continue;
        if (lightness((uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v) >= BADGE_LIGHT_HLS
            && (badge = light_on_gray_badge(p, i, width, count)) > 0) {
            white_mark[i] = (uint8_t)(BADGE_MARK + badge - 1);
            badge_text_count[badge - 1]++;
        }
    }
    colored_text_anchors(white_marks);
    for (i = 0; white_marks && i < count; i++) {
        uint32_t v = p[i], blended;
        double l = lightness((uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v);
        white_mark[i] = 0;
        if ((v >> 24) < ANCHOR_MIN_ALPHA)
            continue;
        if (colored_text_on_light(p, i, width, count, mode, dark_l, light_l, keep_tint, &blended)) {
            white_mark[i] = COLORED_CT_MARK;
            colored_out[i] = blended | (v & 0xff000000U);
        }
        else if (l >= WHITE_MARK_TEST_HLS && white_on_colored(p, i, width, count))
            white_mark[i] = 1;
        else if (l >= BADGE_LIGHT_HLS && (badge = light_on_gray_badge(p, i, width, count)) > 0)
        {
            white_mark[i] = (uint8_t)(BADGE_MARK + badge - 1); /* light text on a gray badge */
            badge_text_count[badge - 1]++;
        }
        else if (l >= WHITE_HLS && small_box_edge(p, i, width, count))
            white_mark[i] = 2;
        else if (spread_of((const uint8_t *)&p[i]) <= FRINGE_MAX_SPREAD && cleartype_fringe(p, i, width, count)
                 && beside_gray_text(p, i, width, count, paper_hls))
            white_mark[i] = 3; /* kept as drawn, it turns gray (light text in a list painted opaque) */
    }
    for (j = 0; (white_marks || fringes) && j < badge_count; j++) { /* badges too light for their text drawn darker */
        int a;
        badge_dark[j] = badge_text_count[j] >= BADGE_MIN_TEXT ? darker_badge(badge_out[j]) : 0;
        if (!badge_dark[j])
            continue;
        badge_out[j] = badge_dark[j] & 0xffffffU;
        darkened = any_mapped = 1;
        for (a = 0; a < anchor_count; a++) { /* an anchor: its edges' blends follow it */
            if (pack(anchors[a].r, anchors[a].g, anchors[a].b) == badge_colors[j]) {
                anchors[a].mr = (double)((badge_out[j] >> 16) & 255);
                anchors[a].mg = (double)((badge_out[j] >> 8) & 255);
                anchors[a].mb = (double)(badge_out[j] & 255);
                anchors[a].mapped = 1;
                any_mapped = 1;
            }
        }
    }
    if (!any_mapped && mode == ANCHORS_RELIGHT)
        return 0;
    /* Where everything is mapped (all, icon, subpixel), an image with no anchor mapped (none found, no
     * color being there three times: a gray ramp, a single pixel; or, as an icon, every anchor kept)
     * goes on below, each pixel by the mode's own fallback; ink, which maps only what is wrong on a
     * dark interface, has nothing to map but stray whites. */
    if (!any_mapped && mode != ANCHORS_ALL && mode != ANCHORS_ICON && mode != ANCHORS_SUBPIXEL) {
        /* Nothing to map but stray whites (a pure white pixel that is no anchor). */
        for (i = 0; i < count; i++) {
            uint8_t *px = pixels + 4 * i;
            if (px[3] > 0 && lightness(px[2], px[1], px[0]) >= WHITE_HLS) {
                if (white_marks && ((white_mark[i] == 1 && px[3] >= HALO_MAX_ALPHA) || white_mark[i] >= BADGE_MARK))
                    continue; /* (a badge's text: no anchor is mapped, its badge neither; a translucent white
                               * enclosed by a colored mark is its halo, see halo_blend, never a mark on it) */
                if (white_marks && white_mark[i] == 2) {
                    changed++;
                    if (apply)
                        p[i] = (p[i] & 0xff000000U) | BOX_FRAME;
                    continue;
                }
                changed++;
                if (apply)
                    map_rgb(&px[2], &px[1], &px[0], dark_l, light_l, 0.0);
            } else if (px[3] >= ANCHOR_MIN_ALPHA && halo_blend(px, dark_l, light_l)) {
                changed++; /* (halo_blend draws it when apply: it is called on the pixel itself) */
            }
        }
        return changed;
    }
    /* Neighborhoods matter where kept and mapped anchors could explain the same pixel. */
    local = (mode == ANCHORS_INK || mode == ANCHORS_RELIGHT || mode == ANCHORS_SUBPIXEL) && width > 0 && count <= MAX_INDEXED;
    if (local)
        index_pixels(p, count);
    glyph_icons = local && mode_list && !last_paper_found && find_glyph_icons(p, count, width);
    tinted = (mode == ANCHORS_ALL || mode == ANCHORS_ICON) && keep_tint > 0.0 && width > 0;
    /* Text smoothing lies between the paper and the text, even where the pixels around are all
     * fringes (ClearType's navy and red beside blue syntax on a dark editor): the kept paper always
     * counts as around, or a far pair of text colors (blue and black ink) claimed those fringes. */
    other_surface_bits = 0;
    for (j = 1; j < anchor_count; j++)
        other_surface_bits |= anchors[j].surface ? 1U << j : 0U;
    paper_bit = mode == ANCHORS_INK && anchor_count > 1 && anchors[0].surface && !anchors[0].mapped ? 1U : 0U;
    main_bit = paper_bit;
    other_surfaces = 0;
    for (j = 1; j < anchor_count; j++)
        other_surfaces |= anchors[j].surface ? 1U << j : 0U;
    for (i = 0; i < count; i++) {
        uint32_t v = p[i], alpha = v >> 24, c, key, out, mask = 0, prev_orig = left_orig;
        int edge;
        left_orig = v; /* as drawn, before this pixel is mapped */
        if (alpha == 0)
            continue;
        if (darkened && alpha >= ANCHOR_MIN_ALPHA) { /* a badge drawn darker, an anchor or not (a blend dropped) */
            int bk = badge_color_of(v & 0xffffffU);
            if (bk >= 0 && badge_dark[bk]) {
                out = (v & 0xff000000U) | badge_out[bk];
                have_last = 0;
                if (out != v) {
                    changed++;
                    if (apply)
                        p[i] = out;
                }
                continue;
            }
        }
        if (glyph_icons && (icon_px[i] == 1 || icon_px[i] == 3)) {
            out = icon_px[i] == 1 ? (mapped_one(v & 0xffffffU, dark_l, light_l, 0.0) | (v & 0xff000000U)) : v;
            have_last = 0;
            if (out != v) {
                changed++;
                if (apply)
                    p[i] = out;
                if (thin)
                    thin_px[i] = 1;
            }
            continue;
        }
        if ((white_marks || plain_marks) && white_mark[i] == 1) { /* the mark and its smoothing toward the box */
            have_last = 0;
            continue;
        }
        if ((white_marks || fringes) && white_mark[i] >= BADGE_MARK) { /* text on a gray badge: once its badge is drawn (below) */
            have_last = 0;
            continue;
        }
        if (fringes && white_mark[i] == 4) {
            have_last = 0;
            continue;
        }
        if ((fringes || white_marks) && white_mark[i] == COLORED_CT_MARK) {
            have_last = 0;
            if (colored_out[i] != v) {
                changed++;
                if (apply)
                    p[i] = colored_out[i];
                if (thin)
                    thin_px[i] = 1;
            }
            continue;
        }
        if (white_marks && white_mark[i] == 2) {
            changed++;
            if (apply)
                p[i] = (v & 0xff000000U) | BOX_FRAME;
            if (thin)
                thin_px[i] = 1;
            have_last = 0;
            continue;
        }
        if (local && alpha >= ANCHOR_MIN_ALPHA && a_index[i] < 0)
            mask = neighborhood(i, count, width);
        if (mask && !(mask & other_surfaces))
            mask |= paper_bit; /* not on another surface (a light row): the paper is around */
        /* ClearType fringes lose their tint; a lightness step alone no longer does (thin colored outlines
         * beside a light background turned dotted). Large images, not surveyed, keep the step test. */
        edge = tinted && (fringes ? white_mark[i] == 3 : sharp_edge(p, i, width, count, prev_orig));
        if (have_last && v == last_in && edge == last_edge && (!local || mask == 0 || a_index[i] >= 0)
            && !(white_marks && white_mark[i] == 3)) {
            if (last_out != v) {
                changed++;
                if (apply)
                    p[i] = last_out;
                if (thin)
                    thin_px[i] = 1;
            }
            continue;
        }
        c = v & 0xffffff;
        if (fringes && white_mark[i] == 3 && dark_text_fringe(p, i, width, count)) {
            /* ClearType's smoothing of dark text on white, kept content (a FontAudit caption on its white tag,
             * the sizes under TrueType Hinting's preview): each channel holds another third of the stroke,
             * so the pixel's own lightness is a third or two of the ink at most, and turned over, thin text
             * came out dim, most of it fringe (the owner, 2026-11-24). Its darkest channel says how much ink
             * the stroke has there: mapped from that, as gray. */
            uint32_t m = (uint32_t)min_channel((const uint8_t *)&v);
            c = (m << 16) | (m << 8) | m;
        }
        if (mode == ANCHORS_SUBPIXEL) {
            int a_here = local ? a_index[i] : -1;
            /* only surfaces map as anchors: ClearType's frequent fringe colors are anchors too, and
             * mapped as such kept their orange and blue */
            uint32_t around = local ? neighborhood(i, count, width) : 0U;
            if (a_here >= 0 && anchors[a_here].surface)
                out = pack(anchors[a_here].mr, anchors[a_here].mg, anchors[a_here].mb);
            else if (anchor_count > 0 && anchors[0].surface && (around & 1U) && !(around & other_surface_bits))
                out = subpixel_color(c, around | (a_here >= 0 ? 1U << a_here : 0U), dark_l, light_l); /* text on the main paper */
            else
                out = all_color(c, ANCHORS_ALL, dark_l, light_l, 0.0);
            out |= v & 0xff000000U;
            have_last = 0;
            if (out != v) {
                changed++;
                if (apply)
                    p[i] = out;
                if (thin)
                    thin_px[i] = 1;
            }
            continue;
        }
        key = c | (alpha < ANCHOR_MIN_ALPHA ? 0x1000000U : 0U) | (edge ? 0x2000000U : 0U);
        if (!memo_get(key, mask, &out)) {
            out = resolve(c, alpha < ANCHOR_MIN_ALPHA, mask, mode, dark_l, light_l, keep_tint,
                          (mode == ANCHORS_ALL || mode == ANCHORS_ICON) && !edge ? keep_tint : 0.0);
            memo_put(key, mask, out);
        }
        if (white_marks && white_mark[i] == 3) {
            /* a ClearType fringe of gray text, kept or mapped: the gray of its (mapped) lightness */
            double l, chroma;
            uint32_t g;
            oklab_of(out & 0xffffffU, &l, &chroma);
            g = (uint32_t)gray_byte(l);
            out = (g << 16) | (g << 8) | g;
            out |= v & 0xff000000U;
            have_last = 0;
            if (out != v) {
                changed++;
                if (apply)
                    p[i] = out;
                if (thin)
                    thin_px[i] = 1;
            }
            continue;
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
            if (thin)
                thin_px[i] = 1;
        }
    }
    for (i = 0; (white_marks || fringes) && badge_count && i < count; i++) { /* text on a gray badge, from the badge as drawn */
        uint32_t v = p[i], out, to;
        int64_t step, at;
        int k;
        if (white_mark[i] < BADGE_MARK)
            continue;
        k = white_mark[i] - BADGE_MARK;
        step = badge_at[i] & 31;
        switch (badge_at[i] >> 5) {
        case 0: at = i + step; break;
        case 1: at = i - step; break;
        case 2: at = i + step * width; break;
        default: at = i - step * width; break;
        }
        to = apply && at >= 0 && at < count ? p[at] & 0xffffffU : badge_out[k];
        out = badge_text(v, k, to);
        if (out != v) {
            changed++;
            if (apply)
                p[i] = out;
        }
    }
    if (thin)
        thin_light_smoothing(p, count, width);
    return changed;
}

/* Diagnostics: the pre-pass decision of each pixel of the last call (0 none, 1 white mark kept, 2 box
 * edge, 3 ClearType fringe, BADGE_MARK and up text on a gray badge), when it ran (ink and tinted
 * content modes, images up to MAX_INDEXED). */
EXPORT void freelab_last_marks(uint8_t *out, int64_t count)
{
    int64_t i;
    for (i = 0; i < count && i < MAX_INDEXED; i++)
        out[i] = white_mark[i];
}

/* Diagnostics: each pixel's shape verdict of the last call (see icon_px; 0 when that pass did not run). */
EXPORT void freelab_last_icons(uint8_t *out, int64_t count)
{
    int64_t i;
    for (i = 0; i < count && i < MAX_INDEXED; i++)
        out[i] = icon_px[i];
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
