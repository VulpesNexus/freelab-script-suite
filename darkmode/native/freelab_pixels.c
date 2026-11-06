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

#include <stdint.h>

#define FREELAB_PIXELS_VERSION 6

/* Built without the C runtime (no entry point, no imports); the compiler still expects this symbol when doubles are used. */
int _fltused = 0;

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
/* A color whose channels spread this little (max - min, 0-255) comes out pure gray: ClearType's
 * colored text edges, drawn dark on light and then mapped, would otherwise stay colored. */
#define NEUTRAL_SPREAD 60
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
static void map_rgb(uint8_t *r8, uint8_t *g8, uint8_t *b8, double dark_l, double light_l)
{
    double l, a, b, l2, k;
    int i;
    uint8_t maxc = *r8 > *g8 ? (*r8 > *b8 ? *r8 : *b8) : (*g8 > *b8 ? *g8 : *b8);
    uint8_t minc = *r8 < *g8 ? (*r8 < *b8 ? *r8 : *b8) : (*g8 < *b8 ? *g8 : *b8);
    linear_to_oklab(SRGB_TO_LINEAR[*r8], SRGB_TO_LINEAR[*g8], SRGB_TO_LINEAR[*b8], &l, &a, &b);
    k = maxc - minc <= NEUTRAL_SPREAD ? 0.0 : chroma_factor(l);
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

/* pixels: count 32-bit pixels as bytes B, G, R, A. With min_l at 0 or below every pixel is
 * mapped; otherwise only pixels whose lightness is at least min_l, or at most max_dark_l when
 * that is not negative (black text on an editor's dark paper). Runs of one color are mapped once. */
EXPORT void freelab_map_lightness(uint8_t *pixels, int64_t count, double dark_l, double light_l, double min_l,
                                  double max_dark_l)
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
        if (min_l <= 0.0) {
            map_rgb(&bytes[2], &bytes[1], &bytes[0], dark_l, light_l);
        } else {
            double l = lightness(bytes[2], bytes[1], bytes[0]);
            if (l >= min_l || (max_dark_l >= 0.0 && l <= max_dark_l))
                map_rgb(&bytes[2], &bytes[1], &bytes[0], dark_l, light_l);
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
