/* FreeLab native dark mode: FontLab's own painting, mapped as FontLab hands its colors to Qt.
 *
 * The native engine is the script engine without its pixel effects. Qt's own widgets are darkened as
 * the script does (dark palette, Fusion, stylesheets, icons, title bars, editors), and everything
 * FontLab paints itself (the glyph canvas, font cells, previews, panel titles, dock frames) is mapped
 * here instead of through effects: the entries of FontLab 7.exe's import table for Qt's
 * color-carrying painting calls point at wrappers that map the color, then call Qt, which then draws
 * dark itself, text smoothing included. Only FontLab's import table changes; Qt's code is untouched,
 * and removing the hooks writes the original addresses back.
 *
 * Three rules keep every color mapped exactly once:
 * - FontLab's code works in light colors. Under the dark palette, a color it reads from a palette is
 *   already dark; mapped again it would turn light. So FontLab's own palette reads (QPalette::color,
 *   QPalette::brush) answer with the light palette's color wherever the palette holds the dark
 *   palette's color for that slot.
 * - Colors are mapped only where they reach the screen: on a painter whose device is a widget.
 *   Painting into an image or a pixmap stays light, so an image or pixmap FontLab renders and keeps
 *   (its glyph cells, thumbnails) is mapped once when it is drawn on a widget, one it saves (an
 *   export) is never dark, and the cursors it paints into pixmaps keep their black shadows.
 * - Colors are mapped where they are used (setPen, setBrush, fillRect, fillPath, setBackground), on
 *   temporary copies, never where they are made: FontLab keeps its pens and brushes, and a QColor it
 *   makes may be a mark color it saves in a font.
 *
 * No C runtime and no imports: the caller passes the module bases and VirtualProtect. The Qt 5 ABI
 * (Qt 5.14.2, MSVC x64) is what FontLab 7 ships: on x64 a member function takes `this` first, and
 * one returning a class by value takes the return slot next; every Qt function used is looked up by
 * its decorated name first, and nothing is hooked when one is missing.
 */
#include "freelab_pixels.c"

#define FREELAB_HOOKS_VERSION 9

typedef int (*virtual_protect_fn)(void *, size_t, uint32_t, uint32_t *);
#define PAGE_READWRITE_ 0x04

/* QColor (Qt 5): its spec, then alpha, red, green, blue as 16-bit values (and a pad). */
typedef struct {
    int32_t spec;
    uint16_t alpha, red, green, blue, pad;
} qcolor;
#define QCOLOR_INVALID 0
#define QCOLOR_RGB 1
#define QIMAGE_RGB32 4
#define QIMAGE_ARGB32 5
#define QIMAGE_ARGB32_PREMULTIPLIED 6

/* QPen and QBrush hold one pointer; room for a copy. */
typedef struct {
    void *d[2];
} qhandle;

/* QInternal::PaintDeviceFlags: what a painter paints on. */
#define DEVICE_WIDGET 1
#define DEVICE_PIXMAP 2
#define DEVICE_IMAGE 3

static virtual_protect_fn vprotect;
static int hooks_on;
static double hook_dark_l = 0.18, hook_light_l = 0.88;
static uint32_t map_devices = 1U << DEVICE_WIDGET; /* pixmaps stay light: cursors are painted into them */
static double hook_keep_tint = 1.0; /* content keeps its tints (a selected cell's pale blue), as the script's islands do */

/* Widgets whose painting is left as FontLab draws it (color swatches and pickers; in Mixed, the
 * canvases, cells, and previews): sorted QWidget addresses. A widget's QPaintDevice part follows
 * its QObject part (a table pointer and d_ptr, 16 bytes), so a painter's widget device, less 16, is
 * the widget. */
#define KEEP_MAX 4096
#define QPAINTDEVICE_IN_QWIDGET 16
static uintptr_t keep_widgets[KEEP_MAX];
static int keep_count;

/* ClearType previews (TrueType Hinting's): the images drawn on them are black text rendered per
 * subpixel on light paper, mapped with the pixel helper's subpixel mapping (each channel's coverage
 * redrawn from the dark paper toward light text) instead of the color rule, which left the fringes
 * colored. Few: a plain list. */
#define SUBPIXEL_MAX 64
static uintptr_t subpixel_widgets[SUBPIXEL_MAX];
static int subpixel_count;
static double subpixel_background_okl = 0.2;

static int subpixel_widget(const void *device)
{
    uintptr_t widget = (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET;
    int i;
    for (i = 0; i < subpixel_count; i++)
        if (subpixel_widgets[i] == widget)
            return 1;
    return 0;
}

static int kept_widget(const void *device)
{
    uintptr_t widget = (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET;
    int lo = 0, hi = keep_count - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (keep_widgets[mid] == widget)
            return 1;
        if (keep_widgets[mid] < widget)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return 0;
}

/* Qt functions called directly (resolved from Qt5Gui's export table). */
static uint32_t (*qt_color_rgba)(const qcolor *);
static void *(*qt_color_from_global)(qcolor *, int);
static int (*qt_image_format)(const void *);
static int (*qt_pen_is_solid)(const void *);
static qcolor *(*qt_pen_color)(const void *, qcolor *);
static void *(*qt_pen_copy)(void *, const void *);
static void (*qt_pen_set_color)(void *, const qcolor *);
static void (*qt_pen_dtor)(void *);
static int (*qt_brush_style)(const void *);
static const qcolor *(*qt_brush_color)(const void *);
static void *(*qt_brush_copy)(void *, const void *);
static void *(*qt_brush_from_color)(void *, const qcolor *, int);
static void (*qt_brush_set_color)(void *, const qcolor *);
static void (*qt_brush_dtor)(void *);
static void *(*qt_image_copy)(void *, const void *);
static void (*qt_image_dtor)(void *);
static int64_t (*qt_image_cache_key)(const void *);
static uint8_t *(*qt_image_bits)(void *);
static int (*qt_image_width)(const void *);
static int (*qt_image_height)(const void *);
static int (*qt_image_bytes_per_line)(const void *);
static void *(*qt_painter_device)(const void *);
static int64_t (*qt_pixmap_cache_key)(const void *);
static void *(*qt_pixmap_to_image)(const void *, void *);
static void *(*qt_pixmap_from_image)(void *, const void *, int);
static void (*qt_pixmap_dtor)(void *);
static int (*qt_palette_current_group)(const void *);

static struct {
    const char *name;
    void **slot;
} qt_needed[] = {
    {"?rgba@QColor@@QEBAIXZ", (void **)&qt_color_rgba},
    {"??0QColor@@QEAA@W4GlobalColor@Qt@@@Z", (void **)&qt_color_from_global},
    {"?format@QImage@@QEBA?AW4Format@1@XZ", (void **)&qt_image_format},
    {"?isSolid@QPen@@QEBA_NXZ", (void **)&qt_pen_is_solid},
    {"?color@QPen@@QEBA?AVQColor@@XZ", (void **)&qt_pen_color},
    {"??0QPen@@QEAA@AEBV0@@Z", (void **)&qt_pen_copy},
    {"?setColor@QPen@@QEAAXAEBVQColor@@@Z", (void **)&qt_pen_set_color},
    {"??1QPen@@QEAA@XZ", (void **)&qt_pen_dtor},
    {"?style@QBrush@@QEBA?AW4BrushStyle@Qt@@XZ", (void **)&qt_brush_style},
    {"?color@QBrush@@QEBAAEBVQColor@@XZ", (void **)&qt_brush_color},
    {"??0QBrush@@QEAA@AEBV0@@Z", (void **)&qt_brush_copy},
    {"??0QBrush@@QEAA@AEBVQColor@@W4BrushStyle@Qt@@@Z", (void **)&qt_brush_from_color},
    {"?setColor@QBrush@@QEAAXAEBVQColor@@@Z", (void **)&qt_brush_set_color},
    {"??1QBrush@@QEAA@XZ", (void **)&qt_brush_dtor},
    {"??0QImage@@QEAA@AEBV0@@Z", (void **)&qt_image_copy},
    {"??1QImage@@UEAA@XZ", (void **)&qt_image_dtor},
    {"?cacheKey@QImage@@QEBA_JXZ", (void **)&qt_image_cache_key},
    {"?bits@QImage@@QEAAPEAEXZ", (void **)&qt_image_bits},
    {"?width@QImage@@QEBAHXZ", (void **)&qt_image_width},
    {"?height@QImage@@QEBAHXZ", (void **)&qt_image_height},
    {"?bytesPerLine@QImage@@QEBAHXZ", (void **)&qt_image_bytes_per_line},
    {"?device@QPainter@@QEBAPEAVQPaintDevice@@XZ", (void **)&qt_painter_device},
    {"?cacheKey@QPixmap@@QEBA_JXZ", (void **)&qt_pixmap_cache_key},
    {"?toImage@QPixmap@@QEBA?AVQImage@@XZ", (void **)&qt_pixmap_to_image},
    {"?fromImage@QPixmap@@SA?AV1@AEBVQImage@@V?$QFlags@W4ImageConversionFlag@Qt@@@@@Z", (void **)&qt_pixmap_from_image},
    {"??1QPixmap@@UEAA@XZ", (void **)&qt_pixmap_dtor},
    {"?currentColorGroup@QPalette@@QEBA?AW4ColorGroup@1@XZ", (void **)&qt_palette_current_group},
};
#define QT_NEEDED (int)(sizeof(qt_needed) / sizeof(qt_needed[0]))

/* The hooked imports: name and wrapper; originals are Qt's own exports. */
enum {
    H_FILL_RECT, H_FILL_RECTF, H_FILL_XYWH, H_FILL_XYWH_GLOBAL, H_SET_PEN_COLOR, H_SET_PEN, H_SET_BRUSH,
    H_FILL_RECT_BRUSH, H_FILL_RECTF_BRUSH, H_FILL_XYWH_BRUSH, H_FILL_PATH, H_SET_BACKGROUND, H_PIXMAP_FILL,
    H_DRAW_IMAGE_PT, H_DRAW_IMAGE_RECT_SRC, H_DRAW_IMAGE_XY, H_DRAW_IMAGE_RECTF,
    H_PALETTE_COLOR_GROUP, H_PALETTE_COLOR, H_PALETTE_BRUSH_GROUP,
    H_DRAW_PIXMAP_RECT, H_DRAW_PIXMAP_PT,
    H_COUNT
};
static const char *hook_names[H_COUNT] = {
    "?fillRect@QPainter@@QEAAXAEBVQRect@@AEBVQColor@@@Z",
    "?fillRect@QPainter@@QEAAXAEBVQRectF@@AEBVQColor@@@Z",
    "?fillRect@QPainter@@QEAAXHHHHAEBVQColor@@@Z",
    "?fillRect@QPainter@@QEAAXHHHHW4GlobalColor@Qt@@@Z",
    "?setPen@QPainter@@QEAAXAEBVQColor@@@Z",
    "?setPen@QPainter@@QEAAXAEBVQPen@@@Z",
    "?setBrush@QPainter@@QEAAXAEBVQBrush@@@Z",
    "?fillRect@QPainter@@QEAAXAEBVQRect@@AEBVQBrush@@@Z",
    "?fillRect@QPainter@@QEAAXAEBVQRectF@@AEBVQBrush@@@Z",
    "?fillRect@QPainter@@QEAAXHHHHAEBVQBrush@@@Z",
    "?fillPath@QPainter@@QEAAXAEBVQPainterPath@@AEBVQBrush@@@Z",
    "?setBackground@QPainter@@QEAAXAEBVQBrush@@@Z",
    "?fill@QPixmap@@QEAAXAEBVQColor@@@Z",
    "?drawImage@QPainter@@QEAAXAEBVQPointF@@AEBVQImage@@@Z",
    "?drawImage@QPainter@@QEAAXAEBVQRect@@AEBVQImage@@0V?$QFlags@W4ImageConversionFlag@Qt@@@@@Z",
    "?drawImage@QPainter@@QEAAXHHAEBVQImage@@HHHHV?$QFlags@W4ImageConversionFlag@Qt@@@@@Z",
    "?drawImage@QPainter@@QEAAXAEBVQRectF@@AEBVQImage@@@Z",
    "?color@QPalette@@QEBAAEBVQColor@@W4ColorGroup@1@W4ColorRole@1@@Z",
    "?color@QPalette@@QEBAAEBVQColor@@W4ColorRole@1@@Z",
    "?brush@QPalette@@QEBAAEBVQBrush@@W4ColorGroup@1@W4ColorRole@1@@Z",
    "?drawPixmap@QPainter@@QEAAXAEBVQRect@@AEBVQPixmap@@@Z",
    "?drawPixmap@QPainter@@QEAAXAEBVQPointF@@AEBVQPixmap@@@Z",
};
#define MODULES 4
static void *originals[H_COUNT];
static void **slots[MODULES][H_COUNT];
static int module_count;
static int64_t hook_calls[H_COUNT];
static int64_t hook_changed[H_COUNT];

/* ---- the color rule --------------------------------------------------------------------------- */

/* Colors as the script maps them (lightness inverted in OKLab, grays to dark mode's grays); clearly
 * colored ones of middle lightness or lighter (selection blues, marks, node colors) kept. */
static uint32_t map_qrgb(uint32_t rgb)
{
    double l, chroma;
    oklab_of(rgb & 0xffffffU, &l, &chroma);
    if (chroma >= CONTENT_KEEP_CHROMA && l >= CONTENT_KEEP_MIN_OKL)
        return rgb;
    return (rgb & 0xff000000U) | (mapped_one(rgb & 0xffffffU, hook_dark_l, hook_light_l, hook_keep_tint) & 0xffffffU);
}

static void set_qcolor(qcolor *out, uint32_t argb)
{
    out->spec = QCOLOR_RGB;
    out->alpha = (uint16_t)(((argb >> 24) & 255) * 0x101);
    out->red = (uint16_t)(((argb >> 16) & 255) * 0x101);
    out->green = (uint16_t)(((argb >> 8) & 255) * 0x101);
    out->blue = (uint16_t)((argb & 255) * 0x101);
    out->pad = 0;
}

/* out = the dark-mode counterpart of c; returns 1 when it differs. */
static int map_qcolor(const qcolor *c, qcolor *out)
{
    uint32_t argb, mapped;
    *out = *c;
    if (c->spec == QCOLOR_INVALID)
        return 0;
    argb = qt_color_rgba(c);
    mapped = map_qrgb(argb);
    if (mapped == argb)
        return 0;
    set_qcolor(out, mapped);
    return 1;
}

/* Where the painter paints: 0 where nothing is mapped, 1 on a widget whose colors are mapped, 2 on a
 * ClearType preview (colors mapped, images mapped per subpixel). Its device's devType() is the
 * second entry of QPaintDevice's table of virtual functions (after the destructor). */
#define SCREEN_PLAIN 1
#define SCREEN_SUBPIXEL 2
static int screen_mode(const void *painter)
{
    void *device;
    int type;
    if (!hooks_on)
        return 0;
    device = qt_painter_device(painter);
    if (!device)
        return 0;
    type = ((int (*)(const void *))((void ***)device)[0][1])(device);
    if (type <= 0 || type >= 32 || !((map_devices >> type) & 1U))
        return 0;
    if (type != DEVICE_WIDGET)
        return SCREEN_PLAIN;
    if (keep_count && kept_widget(device))
        return 0;
    return subpixel_count && subpixel_widget(device) ? SCREEN_SUBPIXEL : SCREEN_PLAIN;
}

static int on_screen(const void *painter)
{
    return screen_mode(painter) != 0;
}

/* White pens stay white: FontLab draws white lines and text only where they stand out, on a color
 * (a selected cell's blue header) or on dark; mapped with the white paper, they turned dark. White
 * fills are still mapped (they are the paper). */
static int white_pen(const qcolor *c)
{
    uint32_t rgb = qt_color_rgba(c);
    uint32_t r = (rgb >> 16) & 255, g = (rgb >> 8) & 255, b = rgb & 255;
    uint32_t lo = r < g ? (r < b ? r : b) : (g < b ? g : b), hi = r > g ? (r > b ? r : b) : (g > b ? g : b);
    return lo >= 235 && hi - lo <= 12;
}

/* The pen to paint with: pen itself, or a mapped copy in tmp (then *copied is 1; destroy it after). */
static const void *mapped_pen(const void *pen, qhandle *tmp, int *copied)
{
    qcolor c, m;
    *copied = 0;
    if (!qt_pen_is_solid(pen))
        return pen; /* a gradient or texture pen: setColor would replace it */
    qt_pen_color(pen, &c);
    if (c.spec == QCOLOR_INVALID || white_pen(&c) || !map_qcolor(&c, &m))
        return pen;
    qt_pen_copy(tmp, pen);
    qt_pen_set_color(tmp, &m);
    *copied = 1;
    return tmp;
}

/* Brush styles that paint with the brush's color: solid and the hatch patterns (not gradients, textures). */
#define BRUSH_SOLID 1
#define BRUSH_LAST_PATTERN 14
static const void *mapped_brush(const void *brush, qhandle *tmp, int *copied)
{
    qcolor m;
    int style;
    *copied = 0;
    style = qt_brush_style(brush);
    if (style < BRUSH_SOLID || style > BRUSH_LAST_PATTERN)
        return brush;
    if (!map_qcolor(qt_brush_color(brush), &m))
        return brush;
    qt_brush_copy(tmp, brush);
    qt_brush_set_color(tmp, &m);
    *copied = 1;
    return tmp;
}

/* ---- the light palette FontLab's code sees ------------------------------------------------------ */

#define GROUPS 3 /* Active, Disabled, Inactive */
#define ROLES 21
#define GROUP_CURRENT 4
static int have_palette;
static uint32_t palette_dark[GROUPS][ROLES], palette_light[GROUPS][ROLES];
static qcolor light_colors[GROUPS][ROLES];
static qhandle light_brushes[GROUPS][ROLES];
static uint8_t light_brush_made[GROUPS][ROLES];
static int64_t palette_swapped;

static int resolved_group(const void *palette, int group)
{
    if (group == GROUP_CURRENT)
        group = qt_palette_current_group(palette);
    return group >= 0 && group < GROUPS ? group : -1;
}

/* The light palette's slot for a color the dark palette holds there, or -1. */
static int light_slot(int group, int role, const qcolor *real)
{
    if (!hooks_on || !have_palette || group < 0 || role < 0 || role >= ROLES || real->spec == QCOLOR_INVALID)
        return -1;
    return qt_color_rgba(real) == palette_dark[group][role] ? group * ROLES + role : -1;
}

/* ---- images --------------------------------------------------------------------------------------
 * FontLab draws its glyph cells (and other content) from images it rendered and keeps. Each image
 * drawn on screen is mapped once, into a copy kept under the image's cacheKey, which Qt changes
 * whenever the image's pixels change: a re-rendered cell is a new key, and a stale copy is never
 * drawn. The copies live in a fixed table (no C runtime here); the oldest gives way. Pixels are
 * unpremultiplied, mapped with map_qrgb (with a small memo of recent colors), and premultiplied again,
 * so smoothing toward transparency survives. */
#define IMAGE_SLOTS 1024
#define QIMAGE_SIZE 64 /* room for a QImage (32 bytes in Qt 5) */
#define MEMO 4096
static struct {
    int64_t key;
    uint64_t stamp;
    int used;
    uint8_t image[QIMAGE_SIZE];
} image_cache[IMAGE_SLOTS];
static uint64_t image_clock;
static volatile long image_busy;
static uint32_t memo_in[MEMO], memo_out[MEMO];
static uint8_t memo_used[MEMO];
static int64_t images_mapped, images_reused;

static uint32_t memo_map(uint32_t rgb)
{
    uint32_t h = (rgb * 2654435761U) >> 20; /* 12 bits */
    if (memo_used[h] && memo_in[h] == rgb)
        return memo_out[h];
    memo_in[h] = rgb;
    memo_out[h] = map_qrgb(rgb | 0xff000000U) & 0xffffffU;
    memo_used[h] = 1;
    return memo_out[h];
}

static void map_image_pixels(void *image, int format, int mode)
{
    uint8_t *bits = qt_image_bits(image); /* detaches: the copy gets pixels of its own */
    int w = qt_image_width(image), h = qt_image_height(image), stride = qt_image_bytes_per_line(image), x, y;
    if (!bits || w <= 0 || h <= 0)
        return;
    if (mode == SCREEN_SUBPIXEL && stride == w * 4) {
        /* opaque ClearType text on paper: the pixel helper's subpixel mapping, as the script engine's */
        freelab_map_anchors(bits, (int64_t)w * h, w, ANCHORS_SUBPIXEL, hook_dark_l, hook_light_l, 0.0,
                            subpixel_background_okl, 1);
        return;
    }
    for (y = 0; y < h; y++) {
        uint32_t *row = (uint32_t *)(bits + (int64_t)y * stride);
        for (x = 0; x < w; x++) {
            uint32_t v = row[x], a = format == QIMAGE_RGB32 ? 255 : v >> 24, r, g, b, m;
            if (a == 0)
                continue;
            r = (v >> 16) & 255;
            g = (v >> 8) & 255;
            b = v & 255;
            if (format == QIMAGE_ARGB32_PREMULTIPLIED && a < 255) {
                r = r * 255 / a;
                g = g * 255 / a;
                b = b * 255 / a;
                if (r > 255) r = 255;
                if (g > 255) g = 255;
                if (b > 255) b = 255;
            }
            m = memo_map((r << 16) | (g << 8) | b);
            r = (m >> 16) & 255;
            g = (m >> 8) & 255;
            b = m & 255;
            if (format == QIMAGE_ARGB32_PREMULTIPLIED && a < 255) {
                r = (r * a + 127) / 255;
                g = (g * a + 127) / 255;
                b = (b * a + 127) / 255;
            }
            row[x] = (format == QIMAGE_RGB32 ? (v & 0xff000000U) : (a << 24)) | (r << 16) | (g << 8) | b;
        }
    }
}

/* The image to draw: a mapped copy of image, or image itself (another format, or busy). */
static const void *mapped_image(const void *image, int mode)
{
    int format, i, slot = -1;
    int64_t key;
    uint64_t oldest = ~0ULL;
    const void *result = image;
    format = qt_image_format(image);
    if (format != QIMAGE_RGB32 && format != QIMAGE_ARGB32 && format != QIMAGE_ARGB32_PREMULTIPLIED)
        return image;
    if (__sync_lock_test_and_set(&image_busy, 1))
        return image; /* another thread is mapping: drawn as it is this once */
    key = qt_image_cache_key(image) * 2 + (mode == SCREEN_SUBPIXEL); /* a copy per mapping */
    for (i = 0; i < IMAGE_SLOTS; i++) {
        if (image_cache[i].used && image_cache[i].key == key) {
            image_cache[i].stamp = ++image_clock;
            images_reused++;
            result = image_cache[i].image;
            goto done;
        }
        if (!image_cache[i].used) {
            if (oldest != 0) {
                oldest = 0;
                slot = i;
            }
        } else if (image_cache[i].stamp < oldest) {
            oldest = image_cache[i].stamp;
            slot = i;
        }
    }
    if (slot < 0)
        goto done;
    if (image_cache[slot].used)
        qt_image_dtor(image_cache[slot].image);
    qt_image_copy(image_cache[slot].image, image);
    map_image_pixels(image_cache[slot].image, format, mode);
    image_cache[slot].key = key;
    image_cache[slot].stamp = ++image_clock;
    image_cache[slot].used = 1;
    images_mapped++;
    result = image_cache[slot].image;
done:
    __sync_lock_release(&image_busy);
    return result;
}

/* ---- pixmaps -----------------------------------------------------------------------------------
 * Pixmaps are light, as FontLab paints or loads them: one it draws on a widget is drawn as a mapped
 * copy, made through an image, kept under its cacheKey like the images. */
#define PIXMAP_SLOTS 512
#define QPIXMAP_SIZE 64
static struct {
    int64_t key;
    uint64_t stamp;
    int used;
    uint8_t pixmap[QPIXMAP_SIZE];
} pixmap_cache[PIXMAP_SLOTS];
static int64_t pixmaps_mapped, pixmaps_reused;

static const void *mapped_pixmap(const void *pixmap, int mode)
{
    int i, slot = -1, format;
    int64_t key;
    uint64_t oldest = ~0ULL;
    uint8_t image[QIMAGE_SIZE];
    const void *result = pixmap;
    key = qt_pixmap_cache_key(pixmap);
    if (key == 0)
        return pixmap;
    key = key * 2 + (mode == SCREEN_SUBPIXEL);
    if (__sync_lock_test_and_set(&image_busy, 1))
        return pixmap;
    for (i = 0; i < PIXMAP_SLOTS; i++) {
        if (pixmap_cache[i].used && pixmap_cache[i].key == key) {
            pixmap_cache[i].stamp = ++image_clock;
            pixmaps_reused++;
            result = pixmap_cache[i].pixmap;
            goto done;
        }
        if (!pixmap_cache[i].used) {
            if (oldest != 0) {
                oldest = 0;
                slot = i;
            }
        } else if (pixmap_cache[i].stamp < oldest) {
            oldest = pixmap_cache[i].stamp;
            slot = i;
        }
    }
    if (slot < 0)
        goto done;
    qt_pixmap_to_image(pixmap, image);
    format = qt_image_format(image);
    if (format == QIMAGE_RGB32 || format == QIMAGE_ARGB32 || format == QIMAGE_ARGB32_PREMULTIPLIED) {
        map_image_pixels(image, format, mode);
        if (pixmap_cache[slot].used)
            qt_pixmap_dtor(pixmap_cache[slot].pixmap);
        qt_pixmap_from_image(pixmap_cache[slot].pixmap, image, 0);
        pixmap_cache[slot].key = key;
        pixmap_cache[slot].stamp = ++image_clock;
        pixmap_cache[slot].used = 1;
        pixmaps_mapped++;
        result = pixmap_cache[slot].pixmap;
    }
    qt_image_dtor(image);
done:
    __sync_lock_release(&image_busy);
    return result;
}

static void clear_pixmap_cache(void)
{
    int i;
    for (i = 0; i < PIXMAP_SLOTS; i++) {
        if (pixmap_cache[i].used) {
            qt_pixmap_dtor(pixmap_cache[i].pixmap);
            pixmap_cache[i].used = 0;
        }
    }
}

static void clear_image_cache(void)
{
    int i;
    for (i = 0; i < IMAGE_SLOTS; i++) {
        if (image_cache[i].used) {
            qt_image_dtor(image_cache[i].image);
            image_cache[i].used = 0;
        }
    }
}

/* ---- wrappers ----------------------------------------------------------------------------------- */

typedef void (*two_fn)(void *, const void *, const void *);
typedef void (*xywh_fn)(void *, int, int, int, int, const void *);
typedef void (*xywh_global_fn)(void *, int, int, int, int, int);
typedef void (*one_fn)(void *, const void *);
typedef void (*rect_src_fn)(void *, const void *, const void *, const void *, int);
typedef void (*xy_image_fn)(void *, int, int, const void *, int, int, int, int, int);
typedef const qcolor *(*palette_color_group_fn)(const void *, int, int);
typedef const qcolor *(*palette_color_fn)(const void *, int);
typedef const void *(*palette_brush_group_fn)(const void *, int, int);

#define ORIGINAL(index, type) ((type)originals[index])

/* A color argument, mapped on screen. */
#define COLOR_ON_SCREEN(index, painter, call_with)                    \
    {                                                                 \
        qcolor m;                                                     \
        const qcolor *use = c;                                        \
        hook_calls[index]++;                                          \
        if (on_screen(painter) && map_qcolor(c, &m)) {                \
            hook_changed[index]++;                                    \
            use = &m;                                                 \
        }                                                             \
        call_with;                                                    \
    }

static void w_fill_rect(void *p, const void *r, const qcolor *c) COLOR_ON_SCREEN(H_FILL_RECT, p, ORIGINAL(H_FILL_RECT, two_fn)(p, r, use))
static void w_fill_rectf(void *p, const void *r, const qcolor *c) COLOR_ON_SCREEN(H_FILL_RECTF, p, ORIGINAL(H_FILL_RECTF, two_fn)(p, r, use))
static void w_fill_xywh(void *p, int x, int y, int w, int h, const qcolor *c) COLOR_ON_SCREEN(H_FILL_XYWH, p, ORIGINAL(H_FILL_XYWH, xywh_fn)(p, x, y, w, h, use))
static void w_set_pen_color(void *p, const qcolor *c)
{
    qcolor m;
    const qcolor *use = c;
    hook_calls[H_SET_PEN_COLOR]++;
    if (on_screen(p) && c->spec != QCOLOR_INVALID && !white_pen(c) && map_qcolor(c, &m)) {
        hook_changed[H_SET_PEN_COLOR]++;
        use = &m;
    }
    ORIGINAL(H_SET_PEN_COLOR, one_fn)(p, use);
}

static void w_fill_xywh_global(void *p, int x, int y, int w, int h, int global)
{
    qcolor c, m;
    hook_calls[H_FILL_XYWH_GLOBAL]++;
    if (on_screen(p)) {
        c.spec = QCOLOR_INVALID;
        qt_color_from_global(&c, global);
        if (map_qcolor(&c, &m)) {
            hook_changed[H_FILL_XYWH_GLOBAL]++;
            ORIGINAL(H_FILL_XYWH, xywh_fn)(p, x, y, w, h, &m);
            return;
        }
    }
    ORIGINAL(H_FILL_XYWH_GLOBAL, xywh_global_fn)(p, x, y, w, h, global);
}

static void w_pixmap_fill(void *pixmap, const qcolor *c)
{
    qcolor m;
    const qcolor *use = c;
    hook_calls[H_PIXMAP_FILL]++; /* observed only: pixmaps stay light, mapped when drawn on a widget */
    (void)m;
    ORIGINAL(H_PIXMAP_FILL, one_fn)(pixmap, use);
}

static void w_set_pen(void *p, const void *pen)
{
    qhandle tmp;
    int copied = 0;
    const void *use = pen;
    hook_calls[H_SET_PEN]++;
    if (on_screen(p))
        use = mapped_pen(pen, &tmp, &copied);
    hook_changed[H_SET_PEN] += copied;
    ORIGINAL(H_SET_PEN, one_fn)(p, use);
    if (copied)
        qt_pen_dtor(&tmp);
}

/* A brush argument, mapped on screen. */
#define BRUSH_ON_SCREEN(index, painter, call_with)                   \
    {                                                                \
        qhandle tmp;                                                 \
        int copied = 0;                                              \
        const void *use = brush;                                     \
        hook_calls[index]++;                                         \
        if (on_screen(painter))                                      \
            use = mapped_brush(brush, &tmp, &copied);                \
        hook_changed[index] += copied;                               \
        call_with;                                                   \
        if (copied)                                                  \
            qt_brush_dtor(&tmp);                                     \
    }

static void w_set_brush(void *p, const void *brush) BRUSH_ON_SCREEN(H_SET_BRUSH, p, ORIGINAL(H_SET_BRUSH, one_fn)(p, use))
static void w_set_background(void *p, const void *brush) BRUSH_ON_SCREEN(H_SET_BACKGROUND, p, ORIGINAL(H_SET_BACKGROUND, one_fn)(p, use))
static void w_fill_rect_brush(void *p, const void *r, const void *brush) BRUSH_ON_SCREEN(H_FILL_RECT_BRUSH, p, ORIGINAL(H_FILL_RECT_BRUSH, two_fn)(p, r, use))
static void w_fill_rectf_brush(void *p, const void *r, const void *brush) BRUSH_ON_SCREEN(H_FILL_RECTF_BRUSH, p, ORIGINAL(H_FILL_RECTF_BRUSH, two_fn)(p, r, use))
static void w_fill_path(void *p, const void *path, const void *brush) BRUSH_ON_SCREEN(H_FILL_PATH, p, ORIGINAL(H_FILL_PATH, two_fn)(p, path, use))
static void w_fill_xywh_brush(void *p, int x, int y, int w, int h, const void *brush) BRUSH_ON_SCREEN(H_FILL_XYWH_BRUSH, p, ORIGINAL(H_FILL_XYWH_BRUSH, xywh_fn)(p, x, y, w, h, use))

/* An image argument, drawn as a mapped copy on screen. */
#define IMAGE_ON_SCREEN(index, painter, call_with)                    \
    {                                                                 \
        const void *use = image;                                      \
        int mode = screen_mode(painter);                              \
        hook_calls[index]++;                                          \
        if (mode)                                                     \
            use = mapped_image(image, mode);                          \
        hook_changed[index] += use != image;                          \
        call_with;                                                    \
    }

static void w_draw_image_pt(void *p, const void *at, const void *image) IMAGE_ON_SCREEN(H_DRAW_IMAGE_PT, p, ORIGINAL(H_DRAW_IMAGE_PT, two_fn)(p, at, use))
static void w_draw_image_rect_src(void *p, const void *target, const void *image, const void *source, int flags) IMAGE_ON_SCREEN(H_DRAW_IMAGE_RECT_SRC, p, ORIGINAL(H_DRAW_IMAGE_RECT_SRC, rect_src_fn)(p, target, use, source, flags))
static void w_draw_image_xy(void *p, int x, int y, const void *image, int sx, int sy, int sw, int sh, int flags) IMAGE_ON_SCREEN(H_DRAW_IMAGE_XY, p, ORIGINAL(H_DRAW_IMAGE_XY, xy_image_fn)(p, x, y, use, sx, sy, sw, sh, flags))
static void w_draw_image_rectf(void *p, const void *target, const void *image) IMAGE_ON_SCREEN(H_DRAW_IMAGE_RECTF, p, ORIGINAL(H_DRAW_IMAGE_RECTF, two_fn)(p, target, use))

static const qcolor *w_palette_color_group(const void *palette, int group, int role)
{
    const qcolor *real = ORIGINAL(H_PALETTE_COLOR_GROUP, palette_color_group_fn)(palette, group, role);
    int slot = light_slot(resolved_group(palette, group), role, real);
    hook_calls[H_PALETTE_COLOR_GROUP]++;
    if (slot < 0)
        return real;
    palette_swapped++;
    hook_changed[H_PALETTE_COLOR_GROUP]++;
    return &light_colors[slot / ROLES][slot % ROLES];
}

static const qcolor *w_palette_color(const void *palette, int role)
{
    const qcolor *real = ORIGINAL(H_PALETTE_COLOR, palette_color_fn)(palette, role);
    int slot = light_slot(resolved_group(palette, GROUP_CURRENT), role, real);
    hook_calls[H_PALETTE_COLOR]++;
    if (slot < 0)
        return real;
    palette_swapped++;
    hook_changed[H_PALETTE_COLOR]++;
    return &light_colors[slot / ROLES][slot % ROLES];
}

static const void *w_palette_brush_group(const void *palette, int group, int role)
{
    const void *real = ORIGINAL(H_PALETTE_BRUSH_GROUP, palette_brush_group_fn)(palette, group, role);
    int g = resolved_group(palette, group), slot;
    hook_calls[H_PALETTE_BRUSH_GROUP]++;
    if (qt_brush_style(real) != BRUSH_SOLID)
        return real;
    slot = light_slot(g, role, qt_brush_color(real));
    if (slot < 0 || !light_brush_made[slot / ROLES][slot % ROLES])
        return real;
    palette_swapped++;
    hook_changed[H_PALETTE_BRUSH_GROUP]++;
    return &light_brushes[slot / ROLES][slot % ROLES];
}

static void w_draw_pixmap_rect(void *p, const void *target, const void *pixmap)
{
    const void *use = pixmap;
    int mode = screen_mode(p);
    hook_calls[H_DRAW_PIXMAP_RECT]++;
    if (mode)
        use = mapped_pixmap(pixmap, mode);
    hook_changed[H_DRAW_PIXMAP_RECT] += use != pixmap;
    ORIGINAL(H_DRAW_PIXMAP_RECT, two_fn)(p, target, use);
}

static void w_draw_pixmap_pt(void *p, const void *at, const void *pixmap)
{
    const void *use = pixmap;
    int mode = screen_mode(p);
    hook_calls[H_DRAW_PIXMAP_PT]++;
    if (mode)
        use = mapped_pixmap(pixmap, mode);
    hook_changed[H_DRAW_PIXMAP_PT] += use != pixmap;
    ORIGINAL(H_DRAW_PIXMAP_PT, two_fn)(p, at, use);
}

static void *wrappers[H_COUNT] = {
    (void *)w_fill_rect, (void *)w_fill_rectf, (void *)w_fill_xywh, (void *)w_fill_xywh_global,
    (void *)w_set_pen_color, (void *)w_set_pen, (void *)w_set_brush, (void *)w_fill_rect_brush,
    (void *)w_fill_rectf_brush, (void *)w_fill_xywh_brush, (void *)w_fill_path, (void *)w_set_background,
    (void *)w_pixmap_fill, (void *)w_draw_image_pt, (void *)w_draw_image_rect_src, (void *)w_draw_image_xy,
    (void *)w_draw_image_rectf, (void *)w_palette_color_group, (void *)w_palette_color, (void *)w_palette_brush_group,
    (void *)w_draw_pixmap_rect, (void *)w_draw_pixmap_pt,
};

/* ---- PE tables ---------------------------------------------------------------------------------- */

static uint32_t rd32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

static int same_text(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}

static int same_dll(const char *a, const char *b) /* ASCII, case-insensitive */
{
    while (*a && *b) {
        char x = *a >= 'A' && *a <= 'Z' ? (char)(*a + 32) : *a, y = *b >= 'A' && *b <= 'Z' ? (char)(*b + 32) : *b;
        if (x != y)
            return 0;
        a++;
        b++;
    }
    return *a == *b;
}

/* The data directory entry (rva) of a 64-bit image, or 0. */
static uint32_t directory_rva(const uint8_t *base, int index, uint32_t *size)
{
    const uint8_t *nt;
    if (rd16(base) != 0x5a4d)
        return 0;
    nt = base + rd32(base + 0x3c);
    if (rd32(nt) != 0x4550 || rd16(nt + 24) != 0x20b) /* PE32+ only */
        return 0;
    if (size)
        *size = rd32(nt + 24 + 112 + index * 8 + 4);
    return rd32(nt + 24 + 112 + index * 8);
}

static void *find_export(const uint8_t *base, const char *name)
{
    uint32_t size, rva = directory_rva(base, 0, &size), i, count, names, ordinals, functions;
    const uint8_t *dir;
    if (!rva)
        return 0;
    dir = base + rva;
    count = rd32(dir + 24);
    functions = rd32(dir + 28);
    names = rd32(dir + 32);
    ordinals = rd32(dir + 36);
    for (i = 0; i < count; i++) {
        if (same_text((const char *)(base + rd32(base + names + i * 4)), name)) {
            uint16_t ordinal = rd16(base + ordinals + i * 2);
            uint32_t function = rd32(base + functions + ordinal * 4);
            if (function >= rva && function < rva + size)
                return 0; /* a forwarder: not expected in Qt5Gui */
            return (void *)(base + function);
        }
    }
    return 0;
}

/* The import table slot of `name` from `dll` in the module at base, or 0. */
static void **find_import_slot(uint8_t *base, const char *dll, const char *name)
{
    uint32_t rva = directory_rva(base, 1, 0);
    const uint8_t *desc;
    if (!rva)
        return 0;
    for (desc = base + rva; rd32(desc + 12) != 0; desc += 20) {
        uint32_t lookup = rd32(desc) ? rd32(desc) : rd32(desc + 16), iat = rd32(desc + 16), k;
        if (!same_dll((const char *)(base + rd32(desc + 12)), dll))
            continue;
        for (k = 0;; k++) {
            uint64_t entry = *(const uint64_t *)(base + lookup + k * 8);
            if (entry == 0)
                break;
            if (entry & 0x8000000000000000ULL)
                continue; /* by ordinal */
            if (same_text((const char *)(base + (uint32_t)entry + 2), name))
                return (void **)(base + iat + k * 8);
        }
    }
    return 0;
}

static int write_slot(void **slot, void *value)
{
    uint32_t old, ignored;
    if (!vprotect(slot, sizeof(void *), PAGE_READWRITE_, &old))
        return 0;
    *(void *volatile *)slot = value;
    vprotect(slot, sizeof(void *), old, &ignored);
    return 1;
}

static int resolve_qt(const uint8_t *qtgui)
{
    int i;
    for (i = 0; i < QT_NEEDED; i++) {
        *qt_needed[i].slot = find_export(qtgui, qt_needed[i].name);
        if (!*qt_needed[i].slot)
            return 0;
    }
    for (i = 0; i < H_COUNT; i++) {
        originals[i] = find_export(qtgui, hook_names[i]);
        if (!originals[i])
            return 0;
    }
    return 1;
}

/* ---- exports ------------------------------------------------------------------------------------ */

EXPORT int freelab_hooks_version(void)
{
    return FREELAB_HOOKS_VERSION * 1000 + FREELAB_PIXELS_VERSION;
}

/* Resolve every Qt function used; 1, or 0 when one is missing (another Qt build: nothing is hooked). */
EXPORT int freelab_hooks_init(uint8_t *qtgui, void *virtual_protect)
{
    vprotect = (virtual_protect_fn)virtual_protect;
    return resolve_qt(qtgui);
}

/* A module whose imports from Qt5Gui are hooked (FontLab 7.exe); returns how many of its imports were found. */
EXPORT int freelab_hooks_add_module(uint8_t *module)
{
    int i, found = 0, m;
    for (m = 0; m < module_count; m++)
        if (slots[m][0] && (uint8_t *)slots[m][0] >= module && (uint8_t *)slots[m][0] < module + 0x10000000)
            return -2; /* added already */
    if (module_count >= MODULES)
        return -1;
    m = module_count++;
    for (i = 0; i < H_COUNT; i++) {
        slots[m][i] = find_import_slot(module, "Qt5Gui.dll", hook_names[i]);
        found += slots[m][i] != 0;
    }
    return found;
}

/* The dark palette dark mode set and the light one FontLab had, as 0xAARRGGBB, groups x roles. */
EXPORT int freelab_hooks_set_palette(const uint32_t *dark, const uint32_t *light)
{
    int g, r;
    if (!qt_brush_from_color)
        return 0;
    for (g = 0; g < GROUPS; g++) {
        for (r = 0; r < ROLES; r++) {
            palette_dark[g][r] = dark[g * ROLES + r];
            palette_light[g][r] = light[g * ROLES + r];
            set_qcolor(&light_colors[g][r], palette_light[g][r]);
            if (light_brush_made[g][r])
                qt_brush_dtor(&light_brushes[g][r]);
            qt_brush_from_color(&light_brushes[g][r], &light_colors[g][r], BRUSH_SOLID);
            light_brush_made[g][r] = 1;
        }
    }
    have_palette = 1;
    return GROUPS * ROLES;
}

/* The widgets left as FontLab draws them (any order; at most KEEP_MAX); returns how many are kept. */
EXPORT int freelab_hooks_set_keep(const uint64_t *widgets, int count)
{
    int i, j, n = 0;
    for (i = 0; i < count && n < KEEP_MAX; i++)
        keep_widgets[n++] = (uintptr_t)widgets[i];
    for (i = 1; i < n; i++) { /* insertion sort: a few hundred at most */
        uintptr_t v = keep_widgets[i];
        for (j = i - 1; j >= 0 && keep_widgets[j] > v; j--)
            keep_widgets[j + 1] = keep_widgets[j];
        keep_widgets[j + 1] = v;
    }
    keep_count = n;
    return n;
}

/* The ClearType previews (any order; at most SUBPIXEL_MAX), and the paper lightness the subpixel
 * mapping uses (BACKGROUND_OKL); returns how many. */
EXPORT int freelab_hooks_set_subpixel(const uint64_t *widgets, int count, double background_okl)
{
    int i, n = 0;
    for (i = 0; i < count && n < SUBPIXEL_MAX; i++)
        subpixel_widgets[n++] = (uintptr_t)widgets[i];
    subpixel_count = n;
    subpixel_background_okl = background_okl;
    return n;
}

/* Point the import slots at the wrappers (mapping on); returns how many were hooked. */
EXPORT int freelab_hooks_install(double dark_l, double light_l, double keep_tint)
{
    int i, m, hooked = 0;
    if (!vprotect)
        return -1;
    hook_dark_l = dark_l;
    hook_light_l = light_l;
    hook_keep_tint = keep_tint;
    clear_image_cache(); /* a new shade: copies made with the old one are stale */
    clear_pixmap_cache();
    for (i = 0; i < 4096; i++)
        memo_used[i] = 0;
    hooks_on = 1;
    for (m = 0; m < module_count; m++)
        for (i = 0; i < H_COUNT; i++)
            if (slots[m][i] && *slots[m][i] != wrappers[i] && write_slot(slots[m][i], wrappers[i]))
                hooked++;
    return hooked;
}

/* Mapping on or off without touching the slots (the wrappers then pass everything through). */
EXPORT void freelab_hooks_enable(int on)
{
    hooks_on = on;
}

/* Write the original addresses back; returns how many slots were restored. */
EXPORT int freelab_hooks_remove(void)
{
    int i, m, restored = 0;
    hooks_on = 0;
    for (m = 0; m < module_count; m++)
        for (i = 0; i < H_COUNT; i++)
            if (slots[m][i] && *slots[m][i] == wrappers[i] && write_slot(slots[m][i], originals[i]))
                restored++;
    clear_image_cache(); /* the slots point at Qt again: no wrapper can be drawing a copy now */
    clear_pixmap_cache();
    return restored;
}

/* calls[i], changed[i] for each hook, in the order of hook_names; returns H_COUNT. */
EXPORT int freelab_hooks_counts(int64_t *calls, int64_t *changed, int max)
{
    int i;
    for (i = 0; i < H_COUNT && i < max; i++) {
        calls[i] = hook_calls[i];
        changed[i] = hook_changed[i];
    }
    return H_COUNT;
}

/* Images mapped (new copies) and reused (copies drawn again); pixmaps the same. */
EXPORT void freelab_hooks_image_counts(int64_t *mapped, int64_t *reused)
{
    *mapped = images_mapped;
    *reused = images_reused;
}

EXPORT void freelab_hooks_pixmap_counts(int64_t *mapped, int64_t *reused)
{
    *mapped = pixmaps_mapped;
    *reused = pixmaps_reused;
}

/* Tests only: wrappers bound with no import table (resolve_qt sets every original), a wrapper's
 * address, the device types mapped, and the devType of a painter's device. */
EXPORT int freelab_hooks_test_bind(uint8_t *qtgui, double dark_l, double light_l)
{
    if (!resolve_qt(qtgui))
        return -1;
    hook_dark_l = dark_l;
    hook_light_l = light_l;
    hooks_on = 1;
    return H_COUNT;
}

EXPORT void *freelab_hooks_test_wrapper(int index)
{
    return index >= 0 && index < H_COUNT ? wrappers[index] : 0;
}

EXPORT void freelab_hooks_test_devices(uint32_t mask)
{
    map_devices = mask;
}

EXPORT int freelab_hooks_test_device_type(const void *painter)
{
    void *device = qt_painter_device(painter);
    return device ? ((int (*)(const void *))((void ***)device)[0][1])(device) : -1;
}
