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

#define FREELAB_HOOKS_VERSION 49

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
#define QIMAGE_INVALID 0
/* A 32-bit format the mapping reads; any other (an icon loaded from an indexed, grayscale, or 1-bit PNG: 321 of
 * FontLab's resources, its Fonts panel's tab icon among them) is converted to ARGB32 first. Drawn as it was, it kept
 * its light-mode colors (the review of 2026-11-26: the Fonts tab's icon, "and that's not the only one"). */
#define MAPPED_FORMAT(f) ((f) == QIMAGE_RGB32 || (f) == QIMAGE_ARGB32 || (f) == QIMAGE_ARGB32_PREMULTIPLIED)

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

/* The widgets whose painting is mapped: the surfaces FontLab paints itself that the script engine
 * makes islands of (the glyph canvas, font cells, previews, rulers), as sorted QWidget addresses.
 * Everything else is left to the script engine's ways. A widget's QPaintDevice part follows its
 * QObject part (a table pointer and d_ptr, 16 bytes), so a painter's widget device, less 16, is the
 * widget. */
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

/* Lists whose rows Qt draws in colors FontLab puts in their data (the Metrics panel's widths, in
 * black): on these viewports, dark pens (from FontLab's code, or from Qt's item drawing in
 * Qt5Widgets) are mapped light as they are set, and nothing else is. The script engine maps such
 * lists' pixels afterwards (its ink effect), which left dark remnants in rows repainted while
 * scrolling. */
static uintptr_t ink_widgets[KEEP_MAX];
static int ink_count;

/* Surfaces that show colors the user picked (Overlay Fonts' sample rows and preview): of the hooked
 * surfaces, those whose brushes and images are drawn as they are. FontLab fills each sample glyph with
 * a brush of the layer's color, or draws it from an image in that color; mapped, a black pick came out
 * white and a white one dark (the review: "black or near-black hues being displayed at pure white when
 * the user specifically selects this kind of color feels like overreach", image 152). Their grounds
 * (fillRect) and pens are mapped as anywhere, and so is FontLab's own gray of the rows' pills. */
#define PICKED_MAX 64
static uintptr_t picked_widgets[PICKED_MAX];
static int picked_count;
#define PICKED_INTERFACE_GRAY 0xa0a2a4U /* the pill behind a row's font name */

/* Widgets whose text is drawn with dark mode's smoothing (the panels' titles): a font FontLab hands to setFont on
 * one is drawn as a copy with text_strategy (QFont::StyleStrategy) set. FontLab keeps a copy of a panel's font,
 * read again only as the panel is laid out, so a strategy set on the panel itself reached the title late or never. */
#define TEXT_STRATEGY_MAX 128
static uintptr_t text_strategy_widgets[TEXT_STRATEGY_MAX];
static int text_strategy_count, text_strategy;

static int picked_target(const void *painter);

static int in_sorted(const uintptr_t *set, int count, uintptr_t value)
{
    int lo = 0, hi = count - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (set[mid] == value)
            return 1;
        if (set[mid] < value)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return 0;
}

static int set_sorted(uintptr_t *set, const uint64_t *values, int count)
{
    int i, j, n = 0;
    for (i = 0; i < count && n < KEEP_MAX; i++)
        set[n++] = (uintptr_t)values[i];
    for (i = 1; i < n; i++) { /* insertion sort: a few hundred at most */
        uintptr_t v = set[i];
        for (j = i - 1; j >= 0 && set[j] > v; j--)
            set[j + 1] = set[j];
        set[j + 1] = v;
    }
    return n;
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
static void *(*qt_pen_from_style)(void *, int);
static int (*qt_pen_style)(const void *);
static char (*qt_painter_active)(const void *);
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
static void *(*qt_image_convert)(const void *, void *, int, int);
static void *(*qt_font_copy)(void *, const void *);
static void (*qt_font_dtor)(void *);
static void (*qt_font_set_strategy)(void *, int);
static char (*qt_painter_has_clipping)(const void *);
static void *(*qt_painter_clip_bounds)(const void *, double *); /* a QRectF (x, y, w, h), returned by value */

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
    {"??0QPen@@QEAA@W4PenStyle@Qt@@@Z", (void **)&qt_pen_from_style},
    {"?style@QPen@@QEBA?AW4PenStyle@Qt@@XZ", (void **)&qt_pen_style},
    {"?isActive@QPainter@@QEBA_NXZ", (void **)&qt_painter_active},
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
    {"?convertToFormat@QImage@@QEBA?AV1@W4Format@1@V?$QFlags@W4ImageConversionFlag@Qt@@@@@Z", (void **)&qt_image_convert},
    {"??0QFont@@QEAA@AEBV0@@Z", (void **)&qt_font_copy},
    {"??1QFont@@QEAA@XZ", (void **)&qt_font_dtor},
    {"?setStyleStrategy@QFont@@QEAAXW4StyleStrategy@1@@Z", (void **)&qt_font_set_strategy},
    {"?hasClipping@QPainter@@QEBA_NXZ", (void **)&qt_painter_has_clipping},
    {"?clipBoundingRect@QPainter@@QEBA?AVQRectF@@XZ", (void **)&qt_painter_clip_bounds},
};
#define QT_NEEDED (int)(sizeof(qt_needed) / sizeof(qt_needed[0]))

/* The hooked imports: name and wrapper; originals are Qt's own exports. */
enum {
    H_FILL_RECT, H_FILL_RECTF, H_FILL_XYWH, H_FILL_XYWH_GLOBAL, H_SET_PEN_COLOR, H_SET_PEN, H_SET_BRUSH,
    H_FILL_RECT_BRUSH, H_FILL_RECTF_BRUSH, H_FILL_XYWH_BRUSH, H_FILL_PATH, H_SET_BACKGROUND, H_PIXMAP_FILL,
    H_DRAW_IMAGE_PT, H_DRAW_IMAGE_RECT_SRC, H_DRAW_IMAGE_XY, H_DRAW_IMAGE_RECTF,
    H_PALETTE_COLOR_GROUP, H_PALETTE_COLOR, H_PALETTE_BRUSH_GROUP,
    H_DRAW_PIXMAP_RECT, H_DRAW_PIXMAP_PT, H_PAINTER_ON, H_PAINTER_OFF, H_PAINTER_BEGIN, H_PAINTER_END,
    H_WIDGET_PALETTE, /* from Qt5Widgets: the only one */
    H_PAINTER_PEN, H_PAINTER_BRUSH, H_SET_PEN_STYLE, H_SET_BRUSH_STYLE, H_SET_FONT,
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
    "??0QPainter@@QEAA@PEAVQPaintDevice@@@Z",
    "??1QPainter@@QEAA@XZ",
    "?begin@QPainter@@QEAA_NPEAVQPaintDevice@@@Z",
    "?end@QPainter@@QEAA_NXZ",
    "?palette@QWidget@@QEBAAEBVQPalette@@XZ",
    "?pen@QPainter@@QEBAAEBVQPen@@XZ",
    "?brush@QPainter@@QEBAAEBVQBrush@@XZ",
    "?setPen@QPainter@@QEAAXW4PenStyle@Qt@@@Z",
    "?setBrush@QPainter@@QEAAXW4BrushStyle@Qt@@@Z",
    "?setFont@QPainter@@QEAAXAEBVQFont@@@Z",
};

static const char *hook_dll(int index)
{
    return index == H_WIDGET_PALETTE ? "Qt5Widgets.dll" : "Qt5Gui.dll";
}
#define MODULES 4
static void *originals[H_COUNT];
static void **slots[MODULES][H_COUNT];
static int module_count;
static int module_ink[MODULES]; /* Qt5Widgets: only its pens, through the ink wrappers */
static int module_svg[MODULES]; /* Qt5Svg: FontLab's SVG artwork (its logo, a color font's SVG glyphs) */
/* The current font draws in color (SVG, color layers, bitmaps): its pictures are what the user gets,
 * so they are drawn as they are. Qt5Svg's slots point at Qt again (a color glyph's SVG is painted
 * through it on the canvas), and a picture FontLab drew into an image (a glyph cell) is not mapped.
 * Pixmaps (icons, the interface's artwork) are mapped as ever. */
static int color_content;
static int64_t hook_calls[H_COUNT];
static int64_t hook_changed[H_COUNT];

/* ---- the color rule --------------------------------------------------------------------------- */

/* Colors as the script maps them (lightness inverted in OKLab, grays to dark mode's grays); clearly
 * colored ones of middle lightness or lighter (selection blues, marks, node colors) kept. */
/* The glyph canvases: their paper is the canvas' ground. FontLab paints a canvas on the workspace color dark mode
 * sets (#f0f0f0, mapped to about #2a2a2a), but draws some of its own surfaces there in pure white (TrueType Hinting's
 * strip of sizes and its pictures), which mapped to the darker #1f1f1f: a dark box on the canvas, where light mode has
 * white on white (images 183 and 189, 2026-11-26). On a canvas, a neutral at least as light as the
 * workspace color (canvas_paper_l) maps to the canvas' ground (canvas_dark_l), and a picture's paper too. */
#define CANVAS_MAX 64
static uintptr_t canvas_widgets[CANVAS_MAX];
static int canvas_count, canvas_paint; /* canvas_paint: the painter screen_mode last looked at is on a canvas */
static int test_canvas; /* the self-test only: an image painter counts as on a canvas */
static double canvas_dark_l = -1.0, canvas_paper_l = 2.0;
#define CANVAS_NEUTRAL_CHROMA 0.02
#define MAP_DARK_L (canvas_paint && canvas_dark_l >= 0.0 ? canvas_dark_l : hook_dark_l)

static uint32_t map_qrgb(uint32_t rgb)
{
    double l, chroma;
    oklab_of(rgb & 0xffffffU, &l, &chroma);
    if (chroma >= CONTENT_KEEP_CHROMA && l >= CONTENT_KEEP_MIN_OKL)
        return rgb;
    if (canvas_paint && canvas_dark_l >= 0.0 && l >= canvas_paper_l && chroma < CANVAS_NEUTRAL_CHROMA)
        return (rgb & 0xff000000U) | (mapped_one(0xffffffU, canvas_dark_l, hook_light_l, 0.0) & 0xffffffU);
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

/* A color as Qt paints it: an invalid QColor (QColor(), a color FontLab never set) is painted black
 * (setPen(QColor()) is QPen(Qt::black); a brush of it fills opaque black). FontLab writes the Fonts
 * panel's file names after setPen(QColor()): skipped as invalid, they stayed black on the dark list. */
static uint32_t painted_rgba(const qcolor *c)
{
    return c->spec == QCOLOR_INVALID ? 0xff000000U : qt_color_rgba(c);
}

/* out = the dark-mode counterpart of c; returns 1 when it differs (an invalid color: always). */
static int map_qcolor(const qcolor *c, qcolor *out)
{
    uint32_t argb, mapped;
    *out = *c;
    argb = painted_rgba(c);
    mapped = map_qrgb(argb);
    if (mapped == argb && c->spec != QCOLOR_INVALID)
        return 0;
    set_qcolor(out, mapped);
    return 1;
}

/* Where the painter paints: 0 where nothing is mapped, 1 on a widget whose colors are mapped, 2 on a
 * ClearType preview (colors mapped, images mapped per subpixel). Its device's devType() is the
 * second entry of QPaintDevice's table of virtual functions (after the destructor). */
#define SCREEN_PLAIN 1
#define SCREEN_SUBPIXEL 2
#define SCREEN_INK_ICON 3 /* a small neutral image on an ink list: the icon rule (see map_image_pixels) */
/* Containers whose own painting is mapped (the dock, the panels, the Font window), apart from the islands: their
 * painting is mapped as an island's, but their palettes are not answered light outside painting. FontLab reads the
 * Font window's palette to color its document tab's name: answered light (black), the names came out black on the
 * dark tab bar (image 179, 2026-11-26). */
#define FRAME_MAX 256
static uintptr_t frame_widgets[FRAME_MAX];
static int frame_count;

static int frame_widget(const void *device)
{
    return frame_count && in_sorted(frame_widgets, frame_count, (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET);
}

static int screen_mode(const void *painter)
{
    void *device;
    int type;
    canvas_paint = 0;
    if (!hooks_on)
        return 0;
    device = qt_painter_device(painter);
    if (!device)
        return 0;
    type = ((int (*)(const void *))((void ***)device)[0][1])(device);
    if (type <= 0 || type >= 32 || !((map_devices >> type) & 1U))
        return 0;
    if (type != DEVICE_WIDGET) {
        canvas_paint = test_canvas; /* (the self-test's images, standing for a canvas: freelab_hooks_test_canvas) */
        return SCREEN_PLAIN;
    }
    if ((!keep_count || !kept_widget(device)) && !frame_widget(device))
        return 0; /* not one of the hooked surfaces: the script engine's */
    canvas_paint = canvas_count && in_sorted(canvas_widgets, canvas_count, (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET);
    return subpixel_count && subpixel_widget(device) ? SCREEN_SUBPIXEL : SCREEN_PLAIN;
}

static int on_screen(const void *painter)
{
    return screen_mode(painter) != 0;
}

static int ink_target(const void *painter)
{
    void *device;
    if (!hooks_on || !ink_count)
        return 0;
    device = qt_painter_device(painter);
    if (!device || ((int (*)(const void *))((void ***)device)[0][1])(device) != DEVICE_WIDGET)
        return 0;
    return in_sorted(ink_widgets, ink_count, (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET);
}

static int picked_target(const void *painter)
{
    void *device;
    if (!hooks_on || !picked_count)
        return 0;
    device = qt_painter_device(painter);
    if (!device || ((int (*)(const void *))((void ***)device)[0][1])(device) != DEVICE_WIDGET)
        return 0;
    return in_sorted(picked_widgets, picked_count, (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET);
}

/* A dark ground filled on a picked surface: FontLab's own choice for contrast, drawn as it is. For a
 * light pick, it fills the selected row navy (#2a3754) so that the sample shows; mapped, the row turned
 * pale (recording, a white pick). Light grounds (the rows' paper) are mapped as anywhere. */
#define PICKED_DARK_GROUND_OKL 0.5
/* FontLab's two grounds for the selected row (pale behind a darker pick, navy behind a light one) are
 * one color in dark mode: the navy is drawn as the pale one mapped (images 155 and 156,
 * where the highlight changed shade with the pick). */
#define PICKED_SELECTION_PALE 0xe9f0ffU
#define PICKED_SELECTION_NAVY 0x2a3754U
static int picked_dark_ground(const void *painter, const qcolor *c, qcolor *out)
{
    double l, chroma;
    uint32_t argb;
    if (!picked_target(painter))
        return 0;
    argb = painted_rgba(c);
    if ((argb & 0xffffffU) == PICKED_SELECTION_NAVY) {
        set_qcolor(out, (argb & 0xff000000U) | (map_qrgb(0xff000000U | PICKED_SELECTION_PALE) & 0xffffffU));
        return 1;
    }
    oklab_of(argb & 0xffffffU, &l, &chroma);
    if (l >= PICKED_DARK_GROUND_OKL)
        return 0;
    *out = *c;
    return 1;
}

/* FontLab's sunken edge on a picked surface (the color field's and the opacity bar's #808080 line along
 * their top and left), drawn in dark mode's frame color (the color slot's, PICKER_FRAME): mapped, the
 * mid gray stays mid gray, a light edge on the dark window (image 154). */
#define PICKED_FRAME_GRAY 0x808080U
#define PICKED_FRAME_DARK 0x292929U /* the panel's own: drawn as the slots' gray, it still read as a light edge
                                     * (image 184, 2026-11-26) */
static int picked_frame(const void *painter, const qcolor *c, qcolor *out)
{
    uint32_t argb = painted_rgba(c);
    if ((argb & 0xffffffU) != PICKED_FRAME_GRAY || !picked_target(painter))
        return 0;
    set_qcolor(out, (argb & 0xff000000U) | PICKED_FRAME_DARK);
    return 1;
}

/* A brush set on a picked surface: drawn as it is, unless it is FontLab's interface gray. */
static int picked_brush(const void *painter, const void *brush)
{
    return picked_target(painter) && (qt_color_rgba(qt_brush_color(brush)) & 0xffffffU) != PICKED_INTERFACE_GRAY;
}

/* White pens stay white: FontLab draws white lines and text only where they stand out, on a color
 * (a selected cell's blue header) or on dark; mapped with the white paper, they turned dark. White
 * fills are still mapped (they are the paper). */
static int white_pen(const qcolor *c)
{
    return (painted_rgba(c) & 0xffffffU) == 0xffffffU; /* pure white only: near-whites (a tab strip's
                                                          * #edeeef edge) are paper-colored lines */
}

/* A translucent pure white pen: on a glyph canvas, a halo drawn to stand a mark out from what is under it, invisible on
 * light mode's white canvas. The Eraser's drop, a black ring in a 40% white halo, came out a light ring in a light glow
 * on the dark canvas (images 190 and 191, 2026-11-27): on a canvas, the halo takes the canvas' ground. */
static int halo_pen(const qcolor *c)
{
    uint32_t argb = painted_rgba(c);
    return (argb & 0xffffffU) == 0xffffffU && (argb >> 24) < 255;
}

/* The pen to paint with: pen itself, or a mapped copy in tmp (then *copied is 1; destroy it after). */
static const void *mapped_pen(const void *pen, qhandle *tmp, int *copied, int map_white)
{
    qcolor c, m;
    *copied = 0;
    if (!qt_pen_is_solid(pen))
        return pen; /* a gradient or texture pen: setColor would replace it */
    qt_pen_color(pen, &c);
    if ((white_pen(&c) && !map_white) || !map_qcolor(&c, &m))
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

/* A color FontLab passes as the light palette's own (the reference a palette read handed it). */
static int palette_light_color(const qcolor *c)
{
    return c >= &light_colors[0][0] && c < &light_colors[0][0] + GROUPS * ROLES;
}
static qhandle light_brushes[GROUPS][ROLES];
static uint8_t light_brush_made[GROUPS][ROLES];
static int64_t palette_swapped;

static int resolved_group(const void *palette, int group)
{
    if (group == GROUP_CURRENT)
        group = qt_palette_current_group(palette);
    return group >= 0 && group < GROUPS ? group : -1;
}

/* Painters FontLab's code has active on a hooked surface: while one is, its palette reads answer
 * light (it paints in light colors, mapped once); otherwise (its cursors, other widgets, anything
 * outside painting) they read the dark palette, as under the script engine. */
#define PAINTERS_MAX 64
static const void *hooked_painters[PAINTERS_MAX];
static int hooked_painter_count;

/* FontLab reads a painter's pen or brush back and sets a color made from it (a label's box from its
 * text color): handed the mapped color, it had it mapped again (black text, a light box). Each
 * hooked painter notes the colors its pen and brush were mapped from, and QPainter::pen() and
 * brush() hand FontLab a copy in its own color. */
#define NOTED_PAIRS 8
typedef struct {
    uint32_t pen_out[NOTED_PAIRS], pen_in[NOTED_PAIRS], brush_out[NOTED_PAIRS], brush_in[NOTED_PAIRS];
    int pen_n, brush_n, pen_next, brush_next, has_pen, has_brush;
    int badge; /* its brush is a light color kept as it is (see dark_on_badge) */
    int dark_box; /* its brush is a dark box mapped light (see on_dark_box) */
    int light_box; /* its brush is a light box mapped dark (see box_contrast), */
    int warning; /* its brush is a mark's red or orange on a glyph canvas (see warning_brush) */
    int white_pen; /* its pen was last set pure white */
    double box_in_l, box_out_l; /* its lightness before and after */
    qhandle pen, brush; /* the copies last handed out */
} painter_note;
static painter_note painter_notes[PAINTERS_MAX];

static void drop_note(painter_note *n)
{
    if (n->has_pen)
        qt_pen_dtor(&n->pen);
    if (n->has_brush)
        qt_brush_dtor(&n->brush);
    n->pen_n = n->brush_n = n->pen_next = n->brush_next = n->has_pen = n->has_brush = n->badge = n->dark_box = 0;
    n->light_box = 0;
    /* (and the warning and the white pen: left set, the next painter noted in the slot began with them, its white pen
     * drawn in the canvas' ground before any brush, or its pen turned white by its first brush: Codex's review) */
    n->warning = n->white_pen = 0;
}

static void note_painter(const void *painter)
{
    if (screen_mode(painter) && hooked_painter_count < PAINTERS_MAX) {
        drop_note(&painter_notes[hooked_painter_count]);
        hooked_painters[hooked_painter_count++] = painter;
    }
}

static void forget_painter(const void *painter)
{
    int i;
    for (i = 0; i < hooked_painter_count; i++) {
        if (hooked_painters[i] == painter) {
            drop_note(&painter_notes[i]);
            hooked_painter_count--;
            if (i != hooked_painter_count) {
                hooked_painters[i] = hooked_painters[hooked_painter_count];
                painter_notes[i] = painter_notes[hooked_painter_count]; /* the copies move with it */
                painter_notes[hooked_painter_count].has_pen = painter_notes[hooked_painter_count].has_brush = 0;
            }
            return;
        }
    }
}

static painter_note *find_note(const void *painter)
{
    int i;
    for (i = 0; i < hooked_painter_count; i++)
        if (hooked_painters[i] == painter)
            return &painter_notes[i];
    return 0;
}

static void note_pair(uint32_t *outs, uint32_t *ins, int *n, int *next, uint32_t out, uint32_t in)
{
    int i;
    for (i = 0; i < *n; i++) {
        if (outs[i] == out) {
            ins[i] = in;
            return;
        }
    }
    outs[*next] = out;
    ins[*next] = in;
    *next = (*next + 1) % NOTED_PAIRS;
    if (*n < NOTED_PAIRS)
        (*n)++;
}

static int noted_source(const uint32_t *outs, const uint32_t *ins, int n, uint32_t out, uint32_t *in)
{
    int i;
    for (i = 0; i < n; i++) {
        if (outs[i] == out) {
            *in = ins[i];
            return 1;
        }
    }
    return 0;
}

static void note_pen(const void *painter, const qcolor *in, const qcolor *out)
{
    painter_note *n;
    if (in == out || !(n = find_note(painter)))
        return;
    note_pair(n->pen_out, n->pen_in, &n->pen_n, &n->pen_next, qt_color_rgba(out), painted_rgba(in));
}

static void note_brush(const void *painter, const void *in, const void *out)
{
    painter_note *n;
    if (in == out || !(n = find_note(painter)))
        return;
    note_pair(n->brush_out, n->brush_in, &n->brush_n, &n->brush_next, qt_color_rgba(qt_brush_color(out)),
              qt_color_rgba(qt_brush_color(in)));
}

/* Badges: FontLab fills a shape with a light, clearly colored brush and writes on it in black (the
 * Fonts panel's style dot, pale blue with a black "R"). The color rule keeps such a fill as it is
 * (CONTENT_KEEP_CHROMA), so the dark text written on it stays dark too: mapped light, it was pale on
 * pale blue. Only while the painter's brush is that fill; any other brush ends it. */
#define BADGE_MIN_OKL 0.7
#define BADGE_DARK_OKL 0.5
static int64_t badge_kept;

static int badge_color(uint32_t argb)
{
    double l, chroma;
    if ((argb >> 24) < 128)
        return 0;
    oklab_of(argb & 0xffffffU, &l, &chroma);
    return chroma >= CONTENT_KEEP_CHROMA && l >= BADGE_MIN_OKL;
}

static void note_badge(const void *painter, int badge)
{
    painter_note *n = find_note(painter);
    if (n)
        n->badge = badge;
}

/* FontAudit's markers on the glyph canvas: a red or orange shape outlined in pure white, the outline invisible on light
 * mode's white canvas. White pens stay white elsewhere (white_pen), and so the outline stood as a jagged white rim
 * around each marker on the dark canvas. On a canvas, a pure white pen with such a brush (a saturated red to orange) is
 * drawn in the canvas' ground: whichever of the two FontLab sets first, the other follows. White text on another color
 * (TrueType Hinting's selected size, white on navy) is not touched. */
#define WARNING_MIN_CHROMA 0.15
static int warning_brush(uint32_t argb)
{
    double l, chroma, a, b;
    if ((argb >> 24) < 128)
        return 0;
    oklab_of(argb & 0xffffffU, &l, &chroma);
    oklab_ab(argb & 0xffffffU, &a, &b);
    return chroma >= WARNING_MIN_CHROMA && a > 0.0 && b > -0.02 && b < a * 2.5; /* red to orange, not yellow or pink */
}

static void note_white_pen(const void *painter, int white)
{
    painter_note *n = find_note(painter);
    if (n)
        n->white_pen = white;
}

static int on_warning(const void *painter)
{
    painter_note *n = find_note(painter);
    return n != 0 && n->warning;
}

static int pen_is_white(const void *painter)
{
    painter_note *n = find_note(painter);
    return n != 0 && n->white_pen;
}

/* On a dark box mapped light (see on_dark_box), dark and middle grays are drawn darker still, so the text stands out
 * from the box: the glyph's caption, selected or with the mouse near it, is #1f1f1f at 70% under #646464 and #404040
 * text. Mapped as anywhere, the text came out #919191 on the box's #969696 (image 173, 2026-11-26); kept
 * as it was, #646464 on that mid gray still hardly read (recording, the same evening: the box is
 * translucent, so over the dark canvas it ends mid gray, not light). Such a pen is drawn at the mapping's dark end,
 * its hue kept. */
#define DARK_BOX_KEEP_OKL 0.6

static int dark_on_box(const void *painter, const qcolor *c, qcolor *m)
{
    painter_note *n = find_note(painter);
    double l, chroma, a, b;
    uint32_t argb;
    uint8_t r8, g8, b8;
    if (!n || !n->dark_box)
        return 0;
    argb = painted_rgba(c);
    oklab_of(argb & 0xffffffU, &l, &chroma);
    if (l >= DARK_BOX_KEEP_OKL)
        return 0;
    if (l > hook_dark_l)
        l = hook_dark_l;
    oklab_ab(argb & 0xffffffU, &a, &b);
    oklab_to_bytes(l, a, b, &r8, &g8, &b8);
    set_qcolor(m, (argb & 0xff000000U) | ((uint32_t)r8 << 16) | ((uint32_t)g8 << 8) | b8);
    badge_kept++;
    return 1;
}

static int dark_on_badge(const void *painter, const qcolor *c)
{
    painter_note *n;
    double l, chroma;
    if (!(n = find_note(painter)) || !n->badge)
        return 0;
    oklab_of(painted_rgba(c) & 0xffffffU, &l, &chroma);
    if (l >= BADGE_DARK_OKL)
        return 0;
    badge_kept++;
    return 1;
}

/* Dark boxes: FontLab fills a label dark and writes on it in white (on the canvas, the glyph's caption while
 * everything is selected, the measurements shown on hovering). The fill is mapped light, as dark ink is; the
 * white text, kept white as white pens are (see white_pen), then stood white on light gray, unreadable (the
 * image 159, 2026-11-26). While the painter's brush is such a box, white pens are mapped with it. A box:
 * a solid fill, mostly opaque, of little color (a dark colored fill is kept: CONTENT_KEEP_CHROMA), darker than
 * DARK_BOX_OKL but not black (FontLab's labels: #282828, #434343; black is a glyph's fill, with white marks on
 * it that stay white). Any other brush ends it. */
#define DARK_BOX_OKL 0.5
#define DARK_BOX_MIN_OKL 0.15
#define DARK_BOX_MIN_ALPHA 128

static int dark_box_color(const qcolor *c)
{
    uint32_t argb = painted_rgba(c);
    double l, chroma;
    if ((argb >> 24) < DARK_BOX_MIN_ALPHA)
        return 0;
    oklab_of(argb & 0xffffffU, &l, &chroma);
    return l < DARK_BOX_OKL && l >= DARK_BOX_MIN_OKL && chroma < CONTENT_KEEP_CHROMA;
}

static void note_dark_box(const void *painter, int dark_box)
{
    painter_note *n = find_note(painter);
    if (n)
        n->dark_box = dark_box;
}

static int on_dark_box(const void *painter)
{
    painter_note *n = find_note(painter);
    return n != 0 && n->dark_box;
}

/* Light boxes: FontLab writes a segment's length in blue and its angle in gray on a small white box at 60 to 70%
 * (the canvas' measurement labels). The box is mapped dark, as paper is, while a middle-lightness pen keeps about
 * the lightness it had (blue is kept as a color; #646464 maps to #919191), so the numbers stood dim on their dark
 * boxes (the roadmap's "measurement labels come out dim"). While the painter's brush is such a box, a pen darker
 * than the box is lightened, its hue kept, until it stands as far above the mapped box as it stood below the box
 * in light mode, at most to the light end of the mapping (black text on it, mapped to that end, is unchanged). */
#define LIGHT_BOX_MIN_OKL 0.85
#define LIGHT_BOX_MIN_ALPHA 128

static void note_light_box(const void *painter, const void *brush, int on)
{
    painter_note *n = find_note(painter);
    qcolor m;
    double l, chroma;
    uint32_t argb;
    if (!n)
        return;
    n->light_box = 0;
    if (!on)
        return;
    argb = painted_rgba(qt_brush_color(brush));
    if ((argb >> 24) < LIGHT_BOX_MIN_ALPHA)
        return;
    oklab_of(argb & 0xffffffU, &l, &chroma);
    if (l < LIGHT_BOX_MIN_OKL || chroma >= CONTENT_KEEP_CHROMA || !map_qcolor(qt_brush_color(brush), &m))
        return;
    n->box_in_l = l;
    oklab_of(qt_color_rgba(&m) & 0xffffffU, &n->box_out_l, &chroma);
    n->light_box = 1;
}

/* m: the pen's color as mapped (c the one FontLab gave). Lightened in place on a light box; 1 if it changed. */
static int box_contrast(const void *painter, const qcolor *c, qcolor *m)
{
    painter_note *n = find_note(painter);
    double in_l, out_l, chroma, target, a, b;
    uint32_t rgba;
    uint8_t r8, g8, b8;
    if (!n || !n->light_box)
        return 0;
    oklab_of(painted_rgba(c) & 0xffffffU, &in_l, &chroma);
    if (in_l >= n->box_in_l)
        return 0;
    target = n->box_out_l + (n->box_in_l - in_l);
    if (target > hook_light_l)
        target = hook_light_l;
    rgba = qt_color_rgba(m);
    oklab_of(rgba & 0xffffffU, &out_l, &chroma);
    if (out_l >= target)
        return 0;
    oklab_ab(rgba & 0xffffffU, &a, &b);
    oklab_to_bytes(target, a, b, &r8, &g8, &b8);
    set_qcolor(m, (rgba & 0xff000000U) | ((uint32_t)r8 << 16) | ((uint32_t)g8 << 8) | b8);
    return 1;
}

/* The light palette's slot for a color the dark palette holds there, or -1. */
/* The palettes of the hooked widgets (QWidget::palette() hands out the widget's own): FontLab often
 * reads a color before it begins painting, or keeps it. Read from one of these, at any time, it is
 * the light color; read from another palette (the application's, as its cursors do), only while
 * it paints a hooked widget. */
#define PALETTES_MAX 1024
static const void *hooked_palettes[PALETTES_MAX];
static int hooked_palette_count;

static int hooked_palette(const void *palette)
{
    int i;
    for (i = 0; i < hooked_palette_count; i++)
        if (hooked_palettes[i] == palette)
            return 1;
    return 0;
}

static int light_slot(const void *palette, int group, int role, const qcolor *real)
{
    if (!hooks_on || !have_palette || (!hooked_painter_count && !hooked_palette(palette)) || group < 0
        || role < 0 || role >= ROLES || real->spec == QCOLOR_INVALID)
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
    uint8_t image[QIMAGE_SIZE]; /* first: a QImage kept here has its pointers 8-byte aligned (after the
                                 * fields below it sat at offset 20) */
    int64_t key;
    uint64_t stamp;
    int used;
} image_cache[IMAGE_SLOTS];
static uint64_t image_clock;
static volatile long image_busy;
static uint32_t memo_in[MEMO], memo_out[MEMO];
static uint8_t memo_used[MEMO];
static int64_t images_mapped, images_reused;

static uint32_t memo_map(uint32_t rgb)
{
    uint32_t h = (rgb * 2654435761U) >> 20; /* 12 bits */
    uint8_t kind = (uint8_t)(1 + (canvas_paint != 0)); /* (a canvas maps its paper otherwise: kept apart) */
    if (memo_used[h] == kind && memo_in[h] == rgb)
        return memo_out[h];
    memo_in[h] = rgb;
    memo_out[h] = map_qrgb(rgb | 0xff000000U) & 0xffffffU;
    memo_used[h] = kind;
    return memo_out[h];
}

/* White artwork on transparency (FontLab's logo, white icons): every visible pixel near-white. It
 * is drawn white on purpose, on a color or on dark; mapped as paper, the logo turned dark. */
#define ARTWORK_WHITE 235
static int white_artwork(const uint8_t *bits, int w, int h, int stride, int format)
{
    int x, y, seen = 0;
    if (format == QIMAGE_RGB32)
        return 0; /* opaque: paper */
    for (y = 0; y < h; y++) {
        const uint32_t *row = (const uint32_t *)(bits + (int64_t)y * stride);
        for (x = 0; x < w; x++) {
            uint32_t v = row[x], a = v >> 24, r = (v >> 16) & 255, g = (v >> 8) & 255, b = v & 255;
            if (a == 0)
                continue;
            if (format == QIMAGE_ARGB32_PREMULTIPLIED) {
                r = r * 255 / a;
                g = g * 255 / a;
                b = b * 255 / a;
            }
            if (r < ARTWORK_WHITE || g < ARTWORK_WHITE || b < ARTWORK_WHITE)
                return 0;
            seen = 1;
        }
    }
    return seen;
}

static int has_transparency(const uint8_t *bits, int w, int h, int stride)
{
    int x, y;
    for (y = 0; y < h; y++) {
        const uint32_t *row = (const uint32_t *)(bits + (int64_t)y * stride);
        for (x = 0; x < w; x++)
            if ((row[x] >> 24) < 255)
                return 1;
    }
    return 0;
}

/* A picture, not ink: a color glyph (an emoji) FontLab drew into an image. Of its visible pixels, at
 * least PICTURE_SHARE percent are colored, or (on transparency, where a glyph's ink is black) light;
 * a glyph drawn in black, smoothed toward transparency, is none of these. A quarter: a color glyph is
 * mostly its colors (an emoji's fills and its light parts), while a gray glyph or icon with a colored
 * accent or a few white highlights has some percent of them, and is ink to map (at 1%, it was not). */
#define PICTURE_CHROMA 40 /* max - min of the channels */
#define PICTURE_LIGHT 150 /* every channel at least this: white or light gray parts */
#define PICTURE_SHARE 25
#define PICTURE_MIN 4
static int is_picture(const uint8_t *bits, int w, int h, int stride, int format, int clear)
{
    int x, y;
    int64_t visible = 0, colored = 0;
    for (y = 0; y < h; y++) {
        const uint32_t *row = (const uint32_t *)(bits + (int64_t)y * stride);
        for (x = 0; x < w; x++) {
            uint32_t v = row[x], a = format == QIMAGE_RGB32 ? 255 : v >> 24, r, g, b, hi, lo;
            if (a < 128)
                continue; /* smoothing: blended, not the picture's own color */
            r = (v >> 16) & 255;
            g = (v >> 8) & 255;
            b = v & 255;
            if (format == QIMAGE_ARGB32_PREMULTIPLIED && a < 255) {
                r = r * 255 / a;
                g = g * 255 / a;
                b = b * 255 / a;
            }
            hi = r > g ? (r > b ? r : b) : (g > b ? g : b);
            lo = r < g ? (r < b ? r : b) : (g < b ? g : b);
            visible++;
            colored += hi - lo >= PICTURE_CHROMA || (clear && lo >= PICTURE_LIGHT);
        }
    }
    return colored >= PICTURE_MIN && colored * 100 >= visible * PICTURE_SHARE;
}

/* An icon FontLab draws itself on a hooked surface (its panels' tabs: the node panel's note, the anchors' red
 * pin): small, on transparency. Mapped color by color with content's tints kept, the node icon's pale yellow note
 * came out an olive block and the red marks dimmed (images 161 to 163, 2026-11-26). It is mapped as
 * dark mode maps every other icon (the script engine's map_image with anchors "icon"): its faces by anchor
 * blends, its colored marks kept. Straight alpha for the pixel helper, premultiplied again after. */
#define ICON_MAX_SIDE 32
static void map_icon_pixels(uint8_t *bits, int w, int h, int format)
{
    uint32_t *p = (uint32_t *)bits;
    int64_t i, n = (int64_t)w * h;
    if (format == QIMAGE_ARGB32_PREMULTIPLIED) {
        for (i = 0; i < n; i++) {
            uint32_t v = p[i], a = v >> 24, r, g, b;
            if (a == 0 || a == 255)
                continue;
            r = ((v >> 16) & 255) * 255 / a;
            g = ((v >> 8) & 255) * 255 / a;
            b = (v & 255) * 255 / a;
            p[i] = (a << 24) | ((r > 255 ? 255 : r) << 16) | ((g > 255 ? 255 : g) << 8) | (b > 255 ? 255 : b);
        }
    }
    freelab_map_anchors(bits, n, w, ANCHORS_ICON, MAP_DARK_L, hook_light_l, 0.0, MAP_DARK_L, 1);
    if (format == QIMAGE_ARGB32_PREMULTIPLIED) {
        for (i = 0; i < n; i++) {
            uint32_t v = p[i], a = v >> 24;
            if (a == 255)
                continue;
            p[i] = (a << 24) | (((((v >> 16) & 255) * a + 127) / 255) << 16) | (((((v >> 8) & 255) * a + 127) / 255) << 8)
                   | (((v & 255) * a + 127) / 255);
        }
    }
}

/* Opaque images up to this many pixels are mapped by anchor blends (the script engine's islands):
 * text smoothed on paper keeps its coverage, which a color-by-color mapping bent (edges too thin). */
#define ANCHORED_MAX_PIXELS (1 << 20)

/* pictures: an image FontLab drew (a glyph cell), which may hold a color glyph; a pixmap's is 0. */
static void map_image_pixels(void *image, int format, int mode, int pictures)
{
    uint8_t *bits = qt_image_bits(image); /* detaches: the copy gets pixels of its own */
    int w = qt_image_width(image), h = qt_image_height(image), stride = qt_image_bytes_per_line(image), x, y;
    int clear;
    if (!bits || w <= 0 || h <= 0)
        return;
    clear = has_transparency(bits, w, h, stride);
    if (mode == SCREEN_INK_ICON) {
        /* On an ink list (its rows Qt draws, only its pens mapped): FontLab's delegates draw their check boxes as small
         * images. The checked one, blue with a white tick, is drawn as designed (mapped with the ink effect, its tick
         * came out dark: image 202, 2026-11-27); the empty one, a white box, by the icon rule. */
        if (clear && w <= ICON_MAX_SIDE && h <= ICON_MAX_SIDE && stride == w * 4
            && !is_picture(bits, w, h, stride, format, 0))
            map_icon_pixels(bits, w, h, format);
        return;
    }
    if (mode != SCREEN_SUBPIXEL && clear && white_artwork(bits, w, h, stride, format))
        return;
    if (pictures && mode != SCREEN_SUBPIXEL && color_content && is_picture(bits, w, h, stride, format, clear))
        return; /* a color glyph: drawn as the font has it */
    if (mode != SCREEN_SUBPIXEL && clear && w <= ICON_MAX_SIDE && h <= ICON_MAX_SIDE && stride == w * 4) {
        map_icon_pixels(bits, w, h, format);
        return;
    }
    if (mode == SCREEN_SUBPIXEL && stride == w * 4) {
        /* opaque ClearType text on paper: the pixel helper's subpixel mapping, as the script engine's */
        freelab_map_anchors(bits, (int64_t)w * h, w, ANCHORS_SUBPIXEL, hook_dark_l, hook_light_l, 0.0,
                            subpixel_background_okl, 1);
        return;
    }
    if (!clear && stride == w * 4 && (int64_t)w * h <= ANCHORED_MAX_PIXELS) {
        /* text or glyphs drawn on paper (an installed font's preview): mapped by anchor blends */
        freelab_map_anchors(bits, (int64_t)w * h, w, ANCHORS_ALL, MAP_DARK_L, hook_light_l, hook_keep_tint,
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
    if (format == QIMAGE_INVALID)
        return image;
    if (__sync_lock_test_and_set(&image_busy, 1))
        return image; /* another thread is mapping: drawn as it is this once */
    key = qt_image_cache_key(image) * 16 + (mode == SCREEN_SUBPIXEL) + 2 * color_content + 4 * (canvas_paint != 0)
          + 8 * (mode == SCREEN_INK_ICON); /* a copy per mapping */
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
    if (MAPPED_FORMAT(format)) {
        qt_image_copy(image_cache[slot].image, image);
    } else {
        qt_image_convert(image, image_cache[slot].image, QIMAGE_ARGB32, 0);
        format = QIMAGE_ARGB32;
    }
    map_image_pixels(image_cache[slot].image, format, mode, 1);
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
    uint8_t pixmap[QPIXMAP_SIZE]; /* first, 8-byte aligned, as the images' */
    int64_t key;
    uint64_t stamp;
    int used;
} pixmap_cache[PIXMAP_SLOTS];
static int64_t pixmaps_mapped, pixmaps_reused;

static const void *mapped_pixmap(const void *pixmap, int mode)
{
    int i, slot = -1, format;
    int64_t key;
    uint64_t oldest = ~0ULL;
    int64_t image_storage[QIMAGE_SIZE / 8]; /* a QImage on the stack, 8-byte aligned */
    uint8_t *image = (uint8_t *)image_storage;
    const void *result = pixmap;
    key = qt_pixmap_cache_key(pixmap);
    if (key == 0)
        return pixmap;
    key = key * 8 + (mode == SCREEN_SUBPIXEL) + 4 * (canvas_paint != 0); /* the same copy in color or not: pictures are images' */
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
    if (format != QIMAGE_INVALID && !MAPPED_FORMAT(format)) {
        int64_t converted_storage[QIMAGE_SIZE / 8];
        qt_image_convert(image, converted_storage, QIMAGE_ARGB32, 0);
        qt_image_dtor(image);
        memcpy(image_storage, converted_storage, sizeof(image_storage)); /* (a QImage is a d-pointer: moved) */
        format = QIMAGE_ARGB32;
    }
    if (MAPPED_FORMAT(format)) {
        map_image_pixels(image, format, mode, 0);
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
/* The ink rule: a dark color (not one of the dark palette's own) mapped light; any other kept. */
#define INK_MAX_OKL 0.5
static int ink_qcolor(const qcolor *c, qcolor *out)
{
    uint32_t argb, rgb, mapped;
    double l, chroma;
    int g, r;
    *out = *c;
    argb = painted_rgba(c);
    rgb = argb & 0xffffffU;
    oklab_of(rgb, &l, &chroma);
    if (l >= INK_MAX_OKL || (argb >> 24) == 0)
        return 0;
    for (g = 0; have_palette && g < GROUPS; g++)
        for (r = 0; r < ROLES; r++)
            if ((palette_dark[g][r] & 0xffffffU) == rgb && rgb != 0)
                return 0; /* dark mode's own color (a frame, a grid line): right already */
    mapped = map_qrgb(argb);
    if (mapped == argb)
        return 0;
    set_qcolor(out, mapped);
    return 1;
}

static const void *ink_pen(const void *pen, qhandle *tmp, int *copied)
{
    qcolor c, m;
    *copied = 0;
    if (!qt_pen_is_solid(pen))
        return pen;
    qt_pen_color(pen, &c);
    if (!ink_qcolor(&c, &m))
        return pen;
    qt_pen_copy(tmp, pen);
    qt_pen_set_color(tmp, &m);
    *copied = 1;
    return tmp;
}

/* A diagnostic trace (off unless asked for): each color FontLab hands to a painter on a widget,
 * mapped or not, with the widget. Read with freelab_hooks_trace. */
#define TRACE_MAX 8192
typedef struct { uint64_t widget; uint32_t in, out; int32_t hook, mapped_surface; } trace_entry;
static trace_entry trace_ring[TRACE_MAX];
static int trace_on, trace_count;

static void trace_rgba(int hook, const void *painter, uint32_t in, uint32_t out)
{
    void *device;
    trace_entry *e;
    if (!trace_on || trace_count >= TRACE_MAX)
        return;
    device = qt_painter_device(painter);
    if (!device || ((int (*)(const void *))((void ***)device)[0][1])(device) != DEVICE_WIDGET)
        return;
    e = &trace_ring[trace_count++];
    e->widget = (uint64_t)((uintptr_t)device - QPAINTDEVICE_IN_QWIDGET);
    e->in = in;
    e->out = out;
    e->hook = hook;
    e->mapped_surface = screen_mode(painter);
}

static void trace_color(int hook, const void *painter, const qcolor *in, const qcolor *out)
{
    if (trace_on) /* (an invalid color as the black Qt paints, its alpha byte 0xfe to tell it apart) */
        trace_rgba(hook, painter, in->spec == QCOLOR_INVALID ? 0xfe000000U : qt_color_rgba(in), painted_rgba(out));
}

static void trace_brush(int hook, const void *painter, const void *in, const void *out)
{
    if (trace_on && qt_brush_style(in) == BRUSH_SOLID)
        trace_color(hook, painter, qt_brush_color(in), qt_brush_color(out));
}

static void trace_pen(int hook, const void *painter, const void *in, const void *out)
{
    qcolor a, b;
    if (!trace_on)
        return;
    qt_pen_color(in, &a);
    qt_pen_color(out, &b);
    trace_color(hook, painter, &a, &b);
}

/* The swatches of the color palettes (FontLab's ColorPickerItem): each paints a light checkerboard (#e1e1e1 and white
 * squares), then its color over it, both inside rounded, smoothed corners. Where a corner is partly covered, the
 * checkerboard shows through the color: on light mode's light popup that is invisible, on the dark popup every swatch
 * had a light rim at its corners, a faint frame around the dark ones (image 187, 2026-11-26). On a swatch,
 * the checkerboard's squares are held back until the painter's next call: an opaque color filled next hides those it
 * covers anyway, and they are dropped (see drop_covered); anything else (a translucent color, no color, a pen, the
 * painter's end) draws them first, as FontLab drew them. */
#define SWATCH_MAX 8192
#define HELD_MAX 32
#define CHECKER_LIGHT 0xffe1e1e1U
#define CHECKER_WHITE 0xffffffffU
static uintptr_t swatch_widgets[SWATCH_MAX];
static int swatch_count;
static struct {
    int index;                 /* the fill it came from: H_FILL_RECT, H_FILL_RECTF or H_FILL_XYWH */
    unsigned char rect[32];    /* its QRect or QRectF, copied */
    int xywh[4];
    qcolor color;
} held[HELD_MAX];
static const void *held_painter;
static int held_count;
static int test_swatch; /* the self-test only: an image painter counts as on a swatch */
static int64_t swatch_held, swatch_dropped; /* squares held back, and of them those dropped under a color */

static int swatch_target(const void *painter)
{
    void *device;
    int type;
    if (!hooks_on || (!swatch_count && !test_swatch))
        return 0;
    device = qt_painter_device(painter);
    if (!device)
        return 0;
    type = ((int (*)(const void *))((void ***)device)[0][1])(device);
    if (type != DEVICE_WIDGET)
        return test_swatch && type == DEVICE_IMAGE; /* (freelab_hooks_test_swatch) */
    return swatch_count && in_sorted(swatch_widgets, swatch_count, (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET);
}

static uint32_t qcolor_argb(const qcolor *c)
{
    return ((uint32_t)(c->alpha >> 8) << 24) | ((uint32_t)(c->red >> 8) << 16) | ((uint32_t)(c->green >> 8) << 8)
           | (uint32_t)(c->blue >> 8);
}

/* The held squares drawn, on their painter (still active: every call that could end it draws them first). */
static void flush_held(void)
{
    int i, n = held_count;
    held_count = 0;
    for (i = 0; i < n; i++) {
        void *p = (void *)held_painter;
        if (held[i].index == H_FILL_XYWH)
            ORIGINAL(H_FILL_XYWH, xywh_fn)(p, held[i].xywh[0], held[i].xywh[1], held[i].xywh[2], held[i].xywh[3],
                                           &held[i].color);
        else
            ORIGINAL(held[i].index, two_fn)(p, held[i].rect, &held[i].color);
    }
}

/* Before any other call on the painter holding squares: they are drawn first. */
static void settle_held(const void *painter)
{
    if (held_count && held_painter == painter)
        flush_held();
}

/* A fill's area as left, top, right, bottom, in the painter's coordinates (empty when right <= left or bottom <= top). */
static void fill_area(int index, const void *rect, const int *xywh, double *area)
{
    if (index == H_FILL_XYWH) {
        area[0] = xywh[0];
        area[1] = xywh[1];
        area[2] = (double)xywh[0] + xywh[2];
        area[3] = (double)xywh[1] + xywh[3];
    } else if (index == H_FILL_RECTF) {
        double f[4]; /* QRectF: x, y, width, height */
        memcpy(f, rect, sizeof(f));
        area[0] = f[0];
        area[1] = f[1];
        area[2] = f[0] + f[2];
        area[3] = f[1] + f[3];
    } else {
        int32_t q[4]; /* QRect: x1, y1, x2, y2, its last pixels included */
        memcpy(q, rect, sizeof(q));
        area[0] = q[0];
        area[1] = q[1];
        area[2] = q[2] + 1.0;
        area[3] = q[3] + 1.0;
    }
}

/* An opaque color filled on a swatch after held squares: the squares it covers are dropped (hidden under it anyway, but
 * for the smoothed corners), and the others are kept, to be drawn first. All of them had been dropped, so a color over
 * part of the checkerboard took the rest of it away (Codex's review). A square counts as covered when the part of it
 * the painter's clip can show (its bounding rectangle: the swatch's rounded corners) lies inside the color. */
static void drop_covered(const void *painter, int index, const void *rect, const int *xywh)
{
    double fill[4], clip[4], square[4];
    int i, n = 0, clipped = qt_painter_has_clipping(painter) != 0;
    fill_area(index, rect, xywh, fill);
    if (clipped) {
        double bounds[4]; /* QRectF: x, y, width, height */
        qt_painter_clip_bounds(painter, bounds);
        clip[0] = bounds[0];
        clip[1] = bounds[1];
        clip[2] = bounds[0] + bounds[2];
        clip[3] = bounds[1] + bounds[3];
    }
    for (i = 0; i < held_count; i++) {
        int covered;
        fill_area(held[i].index, held[i].rect, held[i].xywh, square);
        if (clipped) {
            if (square[0] < clip[0]) square[0] = clip[0];
            if (square[1] < clip[1]) square[1] = clip[1];
            if (square[2] > clip[2]) square[2] = clip[2];
            if (square[3] > clip[3]) square[3] = clip[3];
        }
        if (square[2] <= square[0] || square[3] <= square[1])
            covered = clipped; /* clipped away: nothing of it shows; (no area of its own: drawn as FontLab drew it) */
        else
            covered = square[0] >= fill[0] && square[1] >= fill[1] && square[2] <= fill[2] && square[3] <= fill[3];
        if (covered)
            swatch_dropped++;
        else
            held[n++] = held[i];
    }
    held_count = n;
}

/* A fill on a swatch: 1 when it is a checkerboard square, held back; an opaque fill after held squares drops those it
 * covers and draws the others first. */
static int swatch_fill(int index, const void *painter, const void *rect, int x, int y, int w, int h, const qcolor *c)
{
    uint32_t argb;
    if (held_count && held_painter != painter)
        flush_held(); /* (another painter: the held ones are drawn where they belong) */
    if (c->spec != QCOLOR_RGB || !swatch_target(painter))
        return held_count ? (flush_held(), 0) : 0;
    argb = qcolor_argb(c);
    if (argb == CHECKER_LIGHT || argb == CHECKER_WHITE) {
        if (held_count == HELD_MAX)
            flush_held();
        held_painter = painter;
        held[held_count].index = index;
        if (index == H_FILL_XYWH) {
            held[held_count].xywh[0] = x;
            held[held_count].xywh[1] = y;
            held[held_count].xywh[2] = w;
            held[held_count].xywh[3] = h;
        } else {
            memcpy(held[held_count].rect, rect, index == H_FILL_RECTF ? 32 : 16);
        }
        held[held_count].color = *c;
        held_count++;
        swatch_held++;
        return 1;
    }
    if (held_count) {
        if ((argb >> 24) == 255) {
            int xywh[4];
            xywh[0] = x;
            xywh[1] = y;
            xywh[2] = w;
            xywh[3] = h;
            drop_covered(painter, index, rect, xywh); /* the color covers them, or some of them */
        }
        flush_held(); /* (the others, under the color as FontLab drew them) */
    }
    return 0;
}

/* The palettes' swatches (any order; at most SWATCH_MAX): see swatch_widgets. Shell sort: thousands of them (a
 * palette per color slot), and no C library here. */
EXPORT int freelab_hooks_set_swatches(const uint64_t *widgets, int count)
{
    int i, j, gap, n = 0;
    held_count = 0;
    for (i = 0; i < count && n < SWATCH_MAX; i++)
        swatch_widgets[n++] = (uintptr_t)widgets[i];
    for (gap = n / 2; gap > 0; gap /= 2)
        for (i = gap; i < n; i++) {
            uintptr_t v = swatch_widgets[i];
            for (j = i; j >= gap && swatch_widgets[j - gap] > v; j -= gap)
                swatch_widgets[j] = swatch_widgets[j - gap];
            swatch_widgets[j] = v;
        }
    swatch_count = n;
    return n;
}

#define COLOR_ON_SCREEN(index, painter, held_call, call_with)         \
    {                                                                 \
        qcolor m;                                                     \
        const qcolor *use = c;                                        \
        hook_calls[index]++;                                          \
        if (held_call)                                                \
            return;                                                   \
        if (on_screen(painter) && (picked_dark_ground(painter, c, &m) || map_qcolor(c, &m))) { \
            hook_changed[index]++;                                    \
            use = &m;                                                 \
        }                                                             \
        trace_color(index, painter, c, use);                          \
        call_with;                                                    \
    }

static void w_fill_rect(void *p, const void *r, const qcolor *c)
    COLOR_ON_SCREEN(H_FILL_RECT, p, swatch_fill(H_FILL_RECT, p, r, 0, 0, 0, 0, c), ORIGINAL(H_FILL_RECT, two_fn)(p, r, use))
static void w_fill_rectf(void *p, const void *r, const qcolor *c)
    COLOR_ON_SCREEN(H_FILL_RECTF, p, swatch_fill(H_FILL_RECTF, p, r, 0, 0, 0, 0, c), ORIGINAL(H_FILL_RECTF, two_fn)(p, r, use))
static void w_fill_xywh(void *p, int x, int y, int w, int h, const qcolor *c)
    COLOR_ON_SCREEN(H_FILL_XYWH, p, swatch_fill(H_FILL_XYWH, p, 0, x, y, w, h, c), ORIGINAL(H_FILL_XYWH, xywh_fn)(p, x, y, w, h, use))
static void w_set_pen_color(void *p, const qcolor *c)
{
    qcolor m;
    const qcolor *use = c;
    hook_calls[H_SET_PEN_COLOR]++;
    settle_held(p);
    if (on_screen(p)) {
        if (picked_frame(p, c, &m) || dark_on_box(p, c, &m)) {
            hook_changed[H_SET_PEN_COLOR]++;
            use = &m;
        } else if ((!white_pen(c) || palette_light_color(c) || on_dark_box(p) || (canvas_paint && (on_warning(p) || halo_pen(c))))
                   && !dark_on_badge(p, c) && map_qcolor(c, &m)) {
            hook_changed[H_SET_PEN_COLOR]++;
            use = &m;
        }
        note_white_pen(p, white_pen(c));
        if (use == c)
            m = *c;
        if (box_contrast(p, c, &m)) {
            hook_changed[H_SET_PEN_COLOR] += use == c;
            use = &m;
        }
    } else if (ink_target(p) && ink_qcolor(c, &m)) {
        hook_changed[H_SET_PEN_COLOR]++;
        use = &m;
    }
    trace_color(H_SET_PEN_COLOR, p, c, use);
    note_pen(p, c, use);
    ORIGINAL(H_SET_PEN_COLOR, one_fn)(p, use);
}

static void w_fill_xywh_global(void *p, int x, int y, int w, int h, int global)
{
    qcolor c, m;
    hook_calls[H_FILL_XYWH_GLOBAL]++;
    settle_held(p);
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
    settle_held(p);
    if (on_screen(p)) {
        qcolor c, frame;
        qt_pen_color(pen, &c);
        if (qt_pen_is_solid(pen) && (picked_frame(p, &c, &frame) || dark_on_box(p, &c, &frame))) {
            qt_pen_copy(&tmp, pen);
            qt_pen_set_color(&tmp, &frame);
            use = &tmp;
            copied = 1;
        } else if (!dark_on_badge(p, &c)) {
            qcolor shown;
            use = mapped_pen(pen, &tmp, &copied, on_dark_box(p) || (canvas_paint && (on_warning(p) || halo_pen(&c))));
            qt_pen_color(use, &shown);
            if (qt_pen_is_solid(pen) && box_contrast(p, &c, &shown)) {
                if (!copied) {
                    qt_pen_copy(&tmp, pen);
                    copied = 1;
                    use = &tmp;
                }
                qt_pen_set_color(&tmp, &shown);
            }
        }
    } else if (ink_target(p))
        use = ink_pen(pen, &tmp, &copied);
    {
        qcolor given;
        qt_pen_color(pen, &given);
        note_white_pen(p, qt_pen_is_solid(pen) && white_pen(&given));
    }
    hook_changed[H_SET_PEN] += copied;
    trace_pen(H_SET_PEN, p, pen, use);
    if (copied) {
        qcolor a, b;
        qt_pen_color(pen, &a);
        qt_pen_color(use, &b);
        note_pen(p, &a, &b);
    }
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
        settle_held(painter);                                        \
        if (on_screen(painter) && !(index == H_SET_BRUSH && picked_brush(painter, brush))) \
            use = mapped_brush(brush, &tmp, &copied);                \
        hook_changed[index] += copied;                               \
        trace_brush(index, painter, brush, use);                     \
        call_with;                                                   \
        if (copied)                                                  \
            qt_brush_dtor(&tmp);                                     \
    }

typedef const void *(*pen_getter_fn)(const void *);

/* A warning brush set or left (see warning_brush): a pure white pen set before it is drawn in the canvas' ground while
 * it lasts, and white again after. */
static void note_warning(void *painter, int warning)
{
    painter_note *n = find_note(painter);
    const void *pen;
    qhandle tmp;
    qcolor c;
    if (!n || n->warning == warning) {
        if (n)
            n->warning = warning;
        return;
    }
    n->warning = warning;
    if (!n->white_pen)
        return;
    pen = ORIGINAL(H_PAINTER_PEN, pen_getter_fn)(painter);
    if (!pen || !qt_pen_is_solid(pen))
        return;
    set_qcolor(&c, warning ? 0xff000000U | map_qrgb(0xffffffffU) : 0xffffffffU);
    qt_pen_copy(&tmp, pen);
    qt_pen_set_color(&tmp, &c);
    ORIGINAL(H_SET_PEN, one_fn)(painter, &tmp);
    qt_pen_dtor(&tmp);
}

static void w_set_brush(void *p, const void *brush)
{
    int style = qt_brush_style(brush);
    note_badge(p, hooks_on && style == BRUSH_SOLID && badge_color(qt_color_rgba(qt_brush_color(brush))));
    /* (on the glyph canvases only, where the caption's box is: a tab bar's hover highlight, #606060, was taken for one,
     * and the next tab's name came out black: image 192, 2026-11-27) */
    note_dark_box(p, hooks_on && style == BRUSH_SOLID && on_screen(p) && canvas_paint && !picked_brush(p, brush)
                     && dark_box_color(qt_brush_color(brush)));
    note_light_box(p, brush, hooks_on && style == BRUSH_SOLID && on_screen(p) && !picked_brush(p, brush));
    note_warning(p, hooks_on && style == BRUSH_SOLID && on_screen(p) && canvas_paint
                    && warning_brush(qt_color_rgba(qt_brush_color(brush))));
    BRUSH_ON_SCREEN(H_SET_BRUSH, p, (note_brush(p, brush, use), ORIGINAL(H_SET_BRUSH, one_fn)(p, use)))
}

/* setPen(Qt::PenStyle) and setBrush(Qt::BrushStyle) make Qt's black pen or brush of that style
 * (QPen(style), QBrush(Qt::black, style)), as an invalid color does (painted_rgba). On screen they
 * are set as the mapped black instead, through the hooked setPen(QPen) and setBrush(QBrush); no pen
 * or no brush passes (FontLab sets Qt::NoPen before each glyph it fills). */
#define PEN_NONE 0
typedef void (*style_fn)(void *, int);

static void w_set_pen_style(void *p, int style)
{
    qcolor black, m;
    qhandle tmp;
    int ink = 0;
    hook_calls[H_SET_PEN_STYLE]++;
    settle_held(p);
    if (style != PEN_NONE && (on_screen(p) || (ink = ink_target(p)) != 0)) {
        set_qcolor(&black, 0xff000000U);
        if (ink ? ink_qcolor(&black, &m) : (!dark_on_badge(p, &black) && map_qcolor(&black, &m))) {
            hook_changed[H_SET_PEN_STYLE]++;
            qt_pen_from_style(&tmp, style);
            qt_pen_set_color(&tmp, &m);
            trace_color(H_SET_PEN_STYLE, p, &black, &m);
            note_pen(p, &black, &m);
            ORIGINAL(H_SET_PEN, one_fn)(p, &tmp);
            qt_pen_dtor(&tmp);
            return;
        }
    }
    trace_rgba(H_SET_PEN_STYLE, p, 0xff000000U, (uint32_t)style);
    ORIGINAL(H_SET_PEN_STYLE, style_fn)(p, style);
}

/* setFont on a widget of text_strategy_widgets: a copy with dark mode's smoothing (FontLab's font never changes). */
#define QFONT_SIZE 64 /* room for a QFont (16 bytes in Qt 5) */
static void w_set_font(void *p, const void *font)
{
    void *device;
    hook_calls[H_SET_FONT]++;
    settle_held(p);
    if (hooks_on && text_strategy_count && (device = qt_painter_device(p)) != 0
        && ((int (*)(const void *))((void ***)device)[0][1])(device) == DEVICE_WIDGET
        && in_sorted(text_strategy_widgets, text_strategy_count, (uintptr_t)device - QPAINTDEVICE_IN_QWIDGET)) {
        int64_t storage[QFONT_SIZE / 8];
        qt_font_copy(storage, font);
        qt_font_set_strategy(storage, text_strategy);
        hook_changed[H_SET_FONT]++;
        ORIGINAL(H_SET_FONT, one_fn)(p, storage);
        qt_font_dtor(storage);
        return;
    }
    ORIGINAL(H_SET_FONT, one_fn)(p, font);
}

static void w_set_brush_style(void *p, int style)
{
    qcolor black, m;
    qhandle tmp;
    hook_calls[H_SET_BRUSH_STYLE]++;
    settle_held(p);
    note_badge(p, 0);
    note_dark_box(p, 0); /* (black: no box of either kind, see dark_box_color) */
    note_light_box(p, 0, 0);
    if (style >= BRUSH_SOLID && style <= BRUSH_LAST_PATTERN && on_screen(p)) {
        set_qcolor(&black, 0xff000000U);
        if (map_qcolor(&black, &m)) {
            hook_changed[H_SET_BRUSH_STYLE]++;
            qt_brush_from_color(&tmp, &m, style);
            trace_color(H_SET_BRUSH_STYLE, p, &black, &m);
            {
                qhandle source;
                qt_brush_from_color(&source, &black, style);
                note_brush(p, &source, &tmp);
                qt_brush_dtor(&source);
            }
            ORIGINAL(H_SET_BRUSH, one_fn)(p, &tmp);
            qt_brush_dtor(&tmp);
            return;
        }
    }
    ORIGINAL(H_SET_BRUSH_STYLE, style_fn)(p, style);
}

/* A painter's pen in the trace as it begins (out: the painter; mapped_surface: the pen's style). */
static void trace_painter_pen(int index, const void *painter)
{
    qcolor c;
    const void *pen;
    int before;
    if (!trace_on || !painter || !qt_painter_active(painter)) /* (an inactive painter has no state) */
        return;
    pen = ORIGINAL(H_PAINTER_PEN, pen_getter_fn)(painter);
    qt_pen_color(pen, &c);
    before = trace_count;
    trace_rgba(index, painter, qt_color_rgba(&c), (uint32_t)(uintptr_t)painter);
    if (trace_count > before)
        trace_ring[trace_count - 1].mapped_surface = qt_pen_style(pen);
}
static void w_set_background(void *p, const void *brush) BRUSH_ON_SCREEN(H_SET_BACKGROUND, p, ORIGINAL(H_SET_BACKGROUND, one_fn)(p, use))
static void w_fill_rect_brush(void *p, const void *r, const void *brush) BRUSH_ON_SCREEN(H_FILL_RECT_BRUSH, p, ORIGINAL(H_FILL_RECT_BRUSH, two_fn)(p, r, use))
static void w_fill_rectf_brush(void *p, const void *r, const void *brush) BRUSH_ON_SCREEN(H_FILL_RECTF_BRUSH, p, ORIGINAL(H_FILL_RECTF_BRUSH, two_fn)(p, r, use))
static void w_fill_path(void *p, const void *path, const void *brush) BRUSH_ON_SCREEN(H_FILL_PATH, p, ORIGINAL(H_FILL_PATH, two_fn)(p, path, use))
static void w_fill_xywh_brush(void *p, int x, int y, int w, int h, const void *brush) BRUSH_ON_SCREEN(H_FILL_XYWH_BRUSH, p, ORIGINAL(H_FILL_XYWH_BRUSH, xywh_fn)(p, x, y, w, h, use))

/* An image or pixmap drawn, in the trace: in, its format (an image's; 0xff for a pixmap) in the top byte and its
 * cache key's low 24 bits; out, 1 if a mapped copy was drawn. */
static void trace_picture(int hook, const void *painter, const void *picture, int is_image, int mapped)
{
    if (trace_on)
        trace_rgba(hook, painter, ((is_image ? (uint32_t)qt_image_format(picture) : 0xffU) << 24)
                   | ((uint32_t)(is_image ? qt_image_cache_key(picture) : qt_pixmap_cache_key(picture)) & 0xffffffU),
                   (uint32_t)mapped);
}

/* An image argument, drawn as a mapped copy on screen. */
#define IMAGE_ON_SCREEN(index, painter, call_with)                    \
    {                                                                 \
        const void *use = image;                                      \
        int mode = screen_mode(painter);                              \
        hook_calls[index]++;                                          \
        settle_held(painter);                                         \
        if (!mode && ink_target(painter))                             \
            mode = SCREEN_INK_ICON;                                   \
        if (mode && !picked_target(painter))                          \
            use = mapped_image(image, mode);                          \
        hook_changed[index] += use != image;                          \
        trace_picture(index, painter, image, 1, use != image);        \
        call_with;                                                    \
    }

static void w_draw_image_pt(void *p, const void *at, const void *image) IMAGE_ON_SCREEN(H_DRAW_IMAGE_PT, p, ORIGINAL(H_DRAW_IMAGE_PT, two_fn)(p, at, use))
static void w_draw_image_rect_src(void *p, const void *target, const void *image, const void *source, int flags) IMAGE_ON_SCREEN(H_DRAW_IMAGE_RECT_SRC, p, ORIGINAL(H_DRAW_IMAGE_RECT_SRC, rect_src_fn)(p, target, use, source, flags))
static void w_draw_image_xy(void *p, int x, int y, const void *image, int sx, int sy, int sw, int sh, int flags) IMAGE_ON_SCREEN(H_DRAW_IMAGE_XY, p, ORIGINAL(H_DRAW_IMAGE_XY, xy_image_fn)(p, x, y, use, sx, sy, sw, sh, flags))
static void w_draw_image_rectf(void *p, const void *target, const void *image) IMAGE_ON_SCREEN(H_DRAW_IMAGE_RECTF, p, ORIGINAL(H_DRAW_IMAGE_RECTF, two_fn)(p, target, use))

/* Palette reads in the trace: the palette, its color, the answer, and group, role, painters active. */
static void trace_palette(int hook, const void *palette, int group, int role, uint32_t real, uint32_t answer)
{
    trace_entry *e;
    if (!trace_on || trace_count >= TRACE_MAX)
        return;
    e = &trace_ring[trace_count++];
    e->widget = (uint64_t)(uintptr_t)palette;
    e->in = real;
    e->out = answer;
    e->hook = hook;
    e->mapped_surface = (group & 255) | ((role & 255) << 8) | (hooked_painter_count << 16) | (hooked_palette(palette) << 24);
}

static const qcolor *w_palette_color_group(const void *palette, int group, int role)
{
    const qcolor *real = ORIGINAL(H_PALETTE_COLOR_GROUP, palette_color_group_fn)(palette, group, role);
    int slot = light_slot(palette, resolved_group(palette, group), role, real);
    hook_calls[H_PALETTE_COLOR_GROUP]++;
    trace_palette(H_PALETTE_COLOR_GROUP, palette, group, role, qt_color_rgba(real), slot < 0 ? qt_color_rgba(real) : palette_light[slot / ROLES][slot % ROLES]);
    if (slot < 0)
        return real;
    palette_swapped++;
    hook_changed[H_PALETTE_COLOR_GROUP]++;
    return &light_colors[slot / ROLES][slot % ROLES];
}

static const qcolor *w_palette_color(const void *palette, int role)
{
    const qcolor *real = ORIGINAL(H_PALETTE_COLOR, palette_color_fn)(palette, role);
    int slot = light_slot(palette, resolved_group(palette, GROUP_CURRENT), role, real);
    hook_calls[H_PALETTE_COLOR]++;
    trace_palette(H_PALETTE_COLOR, palette, GROUP_CURRENT, role, qt_color_rgba(real), slot < 0 ? qt_color_rgba(real) : palette_light[slot / ROLES][slot % ROLES]);
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
    slot = light_slot(palette, g, role, qt_brush_color(real));
    trace_palette(H_PALETTE_BRUSH_GROUP, palette, group, role, qt_color_rgba(qt_brush_color(real)),
                  slot < 0 || !light_brush_made[slot / ROLES][slot % ROLES] ? qt_color_rgba(qt_brush_color(real)) : palette_light[slot / ROLES][slot % ROLES]);
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
    settle_held(p);
    if (mode && !picked_target(p))
        use = mapped_pixmap(pixmap, mode);
    hook_changed[H_DRAW_PIXMAP_RECT] += use != pixmap;
    trace_picture(H_DRAW_PIXMAP_RECT, p, pixmap, 0, use != pixmap);
    ORIGINAL(H_DRAW_PIXMAP_RECT, two_fn)(p, target, use);
}

static void w_draw_pixmap_pt(void *p, const void *at, const void *pixmap)
{
    const void *use = pixmap;
    int mode = screen_mode(p);
    hook_calls[H_DRAW_PIXMAP_PT]++;
    settle_held(p);
    if (mode && !picked_target(p))
        use = mapped_pixmap(pixmap, mode);
    hook_changed[H_DRAW_PIXMAP_PT] += use != pixmap;
    trace_picture(H_DRAW_PIXMAP_PT, p, pixmap, 0, use != pixmap);
    ORIGINAL(H_DRAW_PIXMAP_PT, two_fn)(p, at, use);
}

typedef void *(*painter_on_fn)(void *, void *);
typedef void (*painter_off_fn)(void *);
typedef char (*painter_begin_fn)(void *, void *);
typedef char (*painter_end_fn)(void *);

static void *w_painter_on(void *painter, void *device)
{
    void *result = ORIGINAL(H_PAINTER_ON, painter_on_fn)(painter, device);
    hook_calls[H_PAINTER_ON]++;
    note_painter(painter);
    trace_painter_pen(H_PAINTER_ON, painter);
    return result;
}

static void w_painter_off(void *painter)
{
    hook_calls[H_PAINTER_OFF]++;
    settle_held(painter);
    forget_painter(painter);
    ORIGINAL(H_PAINTER_OFF, painter_off_fn)(painter);
}

static char w_painter_begin(void *painter, void *device)
{
    char result = ORIGINAL(H_PAINTER_BEGIN, painter_begin_fn)(painter, device);
    hook_calls[H_PAINTER_BEGIN]++;
    settle_held(painter);
    forget_painter(painter);
    if (result)
        note_painter(painter);
    trace_painter_pen(H_PAINTER_BEGIN, painter);
    return result;
}

static char w_painter_end(void *painter)
{
    hook_calls[H_PAINTER_END]++;
    settle_held(painter);
    forget_painter(painter);
    return ORIGINAL(H_PAINTER_END, painter_end_fn)(painter);
}

typedef const void *(*widget_palette_fn)(const void *);
static const void *w_widget_palette(const void *widget)
{
    const void *palette = ORIGINAL(H_WIDGET_PALETTE, widget_palette_fn)(widget);
    hook_calls[H_WIDGET_PALETTE]++;
    trace_palette(H_WIDGET_PALETTE, palette, 0, 0, (uint32_t)(uintptr_t)widget, (uint32_t)((uintptr_t)widget >> 32));
    if (hooks_on && keep_count && kept_widget((const uint8_t *)widget + QPAINTDEVICE_IN_QWIDGET) && !hooked_palette(palette)
        && hooked_palette_count < PALETTES_MAX) {
        hooked_palettes[hooked_palette_count++] = palette;
        hook_changed[H_WIDGET_PALETTE]++;
    }
    return palette;
}

/* Qt5Widgets' own pens (its item drawing): mapped only on the ink viewports. */
static int64_t ink_calls, ink_changed;
static void w_ink_set_pen_color(void *p, const qcolor *c)
{
    qcolor m;
    const qcolor *use = c;
    ink_calls++;
    if (ink_target(p) && ink_qcolor(c, &m)) {
        ink_changed++;
        use = &m;
    }
    trace_color(H_COUNT + H_SET_PEN_COLOR, p, c, use); /* (past H_COUNT: Qt5Widgets' own) */
    ORIGINAL(H_SET_PEN_COLOR, one_fn)(p, use);
}

static void w_ink_set_pen(void *p, const void *pen)
{
    qhandle tmp;
    int copied = 0;
    const void *use = pen;
    ink_calls++;
    if (ink_target(p))
        use = ink_pen(pen, &tmp, &copied);
    ink_changed += copied;
    trace_pen(H_COUNT + H_SET_PEN, p, pen, use);
    ORIGINAL(H_SET_PEN, one_fn)(p, use);
    if (copied)
        qt_pen_dtor(&tmp);
}

typedef const void *(*painter_getter_fn)(const void *);
static const void *w_painter_pen(const void *painter)
{
    const void *real = ORIGINAL(H_PAINTER_PEN, painter_getter_fn)(painter);
    painter_note *n;
    qcolor current, source;
    uint32_t in;
    hook_calls[H_PAINTER_PEN]++;
    if (!hooks_on || !(n = find_note(painter)) || !n->pen_n)
        return real;
    qt_pen_color(real, &current);
    if (current.spec == QCOLOR_INVALID || !noted_source(n->pen_out, n->pen_in, n->pen_n, qt_color_rgba(&current), &in))
        return real;
    if (n->has_pen)
        qt_pen_dtor(&n->pen);
    qt_pen_copy(&n->pen, real);
    n->has_pen = 1;
    set_qcolor(&source, in);
    qt_pen_set_color(&n->pen, &source);
    hook_changed[H_PAINTER_PEN]++;
    return &n->pen;
}

static const void *w_painter_brush(const void *painter)
{
    const void *real = ORIGINAL(H_PAINTER_BRUSH, painter_getter_fn)(painter);
    painter_note *n;
    qcolor source;
    uint32_t in;
    int style;
    hook_calls[H_PAINTER_BRUSH]++;
    if (!hooks_on || !(n = find_note(painter)) || !n->brush_n)
        return real;
    style = qt_brush_style(real);
    if (style < BRUSH_SOLID || style > BRUSH_LAST_PATTERN
        || !noted_source(n->brush_out, n->brush_in, n->brush_n, qt_color_rgba(qt_brush_color(real)), &in))
        return real;
    if (n->has_brush)
        qt_brush_dtor(&n->brush);
    qt_brush_copy(&n->brush, real);
    n->has_brush = 1;
    set_qcolor(&source, in);
    qt_brush_set_color(&n->brush, &source);
    hook_changed[H_PAINTER_BRUSH]++;
    return &n->brush;
}

static void *wrappers[H_COUNT] = {
    (void *)w_fill_rect, (void *)w_fill_rectf, (void *)w_fill_xywh, (void *)w_fill_xywh_global,
    (void *)w_set_pen_color, (void *)w_set_pen, (void *)w_set_brush, (void *)w_fill_rect_brush,
    (void *)w_fill_rectf_brush, (void *)w_fill_xywh_brush, (void *)w_fill_path, (void *)w_set_background,
    (void *)w_pixmap_fill, (void *)w_draw_image_pt, (void *)w_draw_image_rect_src, (void *)w_draw_image_xy,
    (void *)w_draw_image_rectf, (void *)w_palette_color_group, (void *)w_palette_color, (void *)w_palette_brush_group,
    (void *)w_draw_pixmap_rect, (void *)w_draw_pixmap_pt, (void *)w_painter_on, (void *)w_painter_off,
    (void *)w_painter_begin, (void *)w_painter_end, (void *)w_widget_palette, (void *)w_painter_pen,
    (void *)w_painter_brush, (void *)w_set_pen_style, (void *)w_set_brush_style, (void *)w_set_font,
};

static void *wrapper_for(int module, int index)
{
    if (!module_ink[module])
        return wrappers[index];
    return index == H_SET_PEN_COLOR ? (void *)w_ink_set_pen_color : index == H_SET_PEN ? (void *)w_ink_set_pen : 0;
}

/* Of Qt5Svg's slots, those that carry colors (a painter's life and palette reads stay hooked: a
 * painter noted through one wrapper is forgotten through another). */
static int svg_color_hook(int index)
{
    return index != H_PAINTER_ON && index != H_PAINTER_OFF && index != H_PAINTER_BEGIN && index != H_PAINTER_END;
}

static int svg_left_alone(int module, int index)
{
    return module_svg[module] && color_content && svg_color_hook(index);
}

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

static int resolve_qt(const uint8_t *qtgui, const uint8_t *qtwidgets)
{
    int i;
    for (i = 0; i < QT_NEEDED; i++) {
        *qt_needed[i].slot = find_export(qtgui, qt_needed[i].name);
        if (!*qt_needed[i].slot)
            return 0;
    }
    for (i = 0; i < H_COUNT; i++) {
        originals[i] = find_export(i == H_WIDGET_PALETTE ? qtwidgets : qtgui, hook_names[i]);
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
EXPORT int freelab_hooks_init(uint8_t *qtgui, void *virtual_protect, uint8_t *qtwidgets)
{
    vprotect = (virtual_protect_fn)virtual_protect;
    return qtgui && qtwidgets && resolve_qt(qtgui, qtwidgets);
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
        slots[m][i] = find_import_slot(module, hook_dll(i), hook_names[i]);
        found += slots[m][i] != 0;
    }
    return found;
}

/* Qt5Widgets: its pens are hooked for the ink viewports only; returns how many of the two were found. */
EXPORT int freelab_hooks_add_ink_module(uint8_t *module)
{
    int m, found = 0;
    for (m = 0; m < module_count; m++)
        if (module_ink[m])
            return -2; /* added already */
    if (module_count >= MODULES)
        return -1;
    m = module_count++;
    module_ink[m] = 1;
    slots[m][H_SET_PEN_COLOR] = find_import_slot(module, "Qt5Gui.dll", hook_names[H_SET_PEN_COLOR]);
    slots[m][H_SET_PEN] = find_import_slot(module, "Qt5Gui.dll", hook_names[H_SET_PEN]);
    found = (slots[m][H_SET_PEN_COLOR] != 0) + (slots[m][H_SET_PEN] != 0);
    return found;
}

/* The ink viewports (any order; at most KEEP_MAX); returns how many. */
EXPORT int freelab_hooks_set_ink(const uint64_t *widgets, int count)
{
    ink_count = set_sorted(ink_widgets, widgets, count);
    return ink_count;
}

/* The surfaces showing picked colors (any order; at most PICKED_MAX; each also hooked); returns how many. */
EXPORT int freelab_hooks_set_picked(const uint64_t *widgets, int count)
{
    int i, j, n = 0;
    for (i = 0; i < count && n < PICKED_MAX; i++)
        picked_widgets[n++] = (uintptr_t)widgets[i];
    for (i = 1; i < n; i++) {
        uintptr_t v = picked_widgets[i];
        for (j = i - 1; j >= 0 && picked_widgets[j] > v; j--)
            picked_widgets[j + 1] = picked_widgets[j];
        picked_widgets[j + 1] = v;
    }
    picked_count = n;
    return n;
}

/* The widgets whose text setFont gives strategy (any order; at most TEXT_STRATEGY_MAX), see text_strategy_widgets. */
EXPORT int freelab_hooks_set_text_strategy(const uint64_t *widgets, int count, int strategy)
{
    int i, j, n = 0;
    for (i = 0; i < count && n < TEXT_STRATEGY_MAX; i++)
        text_strategy_widgets[n++] = (uintptr_t)widgets[i];
    for (i = 1; i < n; i++) {
        uintptr_t v = text_strategy_widgets[i];
        for (j = i - 1; j >= 0 && text_strategy_widgets[j] > v; j--)
            text_strategy_widgets[j + 1] = text_strategy_widgets[j];
        text_strategy_widgets[j + 1] = v;
    }
    text_strategy = strategy;
    text_strategy_count = n;
    return n;
}

EXPORT void freelab_hooks_ink_counts(int64_t *calls, int64_t *changed)
{
    *calls = ink_calls;
    *changed = ink_changed;
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

/* The widgets whose painting is mapped (any order; at most KEEP_MAX); returns how many. */
EXPORT int freelab_hooks_set_hooked(const uint64_t *widgets, int count)
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
    hooked_palette_count = 0; /* noted again as FontLab reads them (a deleted widget's may be reused) */
    return n;
}

/* The glyph canvases (any order; at most CANVAS_MAX), the lightness their paper maps to, and the lightness from which
 * a neutral is paper (the workspace color's): see canvas_widgets. A dark_l below 0 leaves canvases as any surface. */
EXPORT int freelab_hooks_set_canvas(const uint64_t *widgets, int count, double dark_l, double paper_l)
{
    int i, j, n = 0;
    for (i = 0; i < count && n < CANVAS_MAX; i++)
        canvas_widgets[n++] = (uintptr_t)widgets[i];
    for (i = 1; i < n; i++) {
        uintptr_t v = canvas_widgets[i];
        for (j = i - 1; j >= 0 && canvas_widgets[j] > v; j--)
            canvas_widgets[j + 1] = canvas_widgets[j];
        canvas_widgets[j + 1] = v;
    }
    canvas_dark_l = dark_l;
    canvas_paper_l = paper_l;
    canvas_count = n;
    for (i = 0; i < MEMO; i++)
        memo_used[i] = 0;
    return n;
}

/* The containers whose own painting is mapped (any order; at most FRAME_MAX): see frame_widgets. */
EXPORT int freelab_hooks_set_frames(const uint64_t *widgets, int count)
{
    int i, j, n = 0;
    for (i = 0; i < count && n < FRAME_MAX; i++)
        frame_widgets[n++] = (uintptr_t)widgets[i];
    for (i = 1; i < n; i++) {
        uintptr_t v = frame_widgets[i];
        for (j = i - 1; j >= 0 && frame_widgets[j] > v; j--)
            frame_widgets[j + 1] = frame_widgets[j];
        frame_widgets[j + 1] = v;
    }
    frame_count = n;
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

/* What install wrote, to put back if a slot cannot be written. */
static void *install_was[MODULES][H_COUNT];
static uint8_t install_wrote[MODULES][H_COUNT];

/* Point the import slots at the wrappers (mapping on); returns how many were hooked. All or none: when
 * a slot cannot be written, the slots this call wrote get their addresses back, mapping is as it was,
 * and it returns -2 (painters noted by one hook and never forgotten by another had kept FontLab's
 * palette reads light). -1: not initialized. */
EXPORT int freelab_hooks_install(double dark_l, double light_l, double keep_tint)
{
    int i, m, hooked = 0, was_on = hooks_on, failed = 0;
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
            install_wrote[m][i] = 0;
    for (m = 0; m < module_count && !failed; m++)
        for (i = 0; i < H_COUNT && !failed; i++) {
            void *was;
            if (!slots[m][i] || !wrapper_for(m, i) || svg_left_alone(m, i) || *slots[m][i] == wrapper_for(m, i))
                continue;
            was = *slots[m][i];
            if (!write_slot(slots[m][i], wrapper_for(m, i))) {
                failed = 1;
                break;
            }
            install_was[m][i] = was;
            install_wrote[m][i] = 1;
            hooked++;
        }
    if (!failed)
        return hooked;
    for (m = 0; m < module_count; m++)
        for (i = 0; i < H_COUNT; i++)
            if (install_wrote[m][i])
                write_slot(slots[m][i], install_was[m][i]); /* one that stays a wrapper passes through while mapping is off */
    hooks_on = was_on;
    if (!was_on) { /* painters noted meanwhile, as remove forgets them */
        for (i = 0; i < hooked_painter_count; i++)
            drop_note(&painter_notes[i]);
        hooked_painter_count = 0;
        hooked_palette_count = 0;
    }
    return -2;
}

/* Qt5Svg: as add_module, and its color-carrying slots point at Qt while the current font is in color. */
EXPORT int freelab_hooks_add_svg_module(uint8_t *module)
{
    int before = module_count, found = freelab_hooks_add_module(module);
    if (found >= 0 && module_count > before)
        module_svg[module_count - 1] = 1;
    return found;
}

/* The current font draws in color (1) or not (0): Qt5Svg's color slots go back to Qt or to the
 * wrappers, and pictures drawn into images are drawn as they are. Returns how many slots changed. */
EXPORT int freelab_hooks_set_color_content(int on)
{
    int i, m, changed = 0;
    on = on != 0;
    if (on == color_content)
        return 0;
    color_content = on;
    if (!hooks_on)
        return 0; /* install points the slots as they should be */
    for (m = 0; m < module_count; m++) {
        if (!module_svg[m])
            continue;
        for (i = 0; i < H_COUNT; i++) {
            void *target;
            if (!slots[m][i] || !svg_color_hook(i))
                continue;
            target = on ? originals[i] : wrapper_for(m, i);
            if (*slots[m][i] != target && write_slot(slots[m][i], target))
                changed++;
        }
    }
    return changed;
}

EXPORT int freelab_hooks_color_content(void)
{
    return color_content;
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
            if (slots[m][i] && wrapper_for(m, i) && *slots[m][i] == wrapper_for(m, i) && write_slot(slots[m][i], originals[i]))
                restored++;
    clear_image_cache(); /* the slots point at Qt again: no wrapper can be drawing a copy now */
    for (i = 0; i < hooked_painter_count; i++)
        drop_note(&painter_notes[i]);
    hooked_painter_count = 0;
    hooked_palette_count = 0;
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

/* Dark pens kept dark on a badge (see dark_on_badge). */
EXPORT int64_t freelab_hooks_badge_count(void)
{
    return badge_kept;
}

/* Images mapped (new copies) and reused (copies drawn again); pixmaps the same. */
EXPORT void freelab_hooks_image_counts(int64_t *mapped, int64_t *reused)
{
    *mapped = images_mapped;
    *reused = images_reused;
}

/* The diagnostic trace: on (cleared) or off; read copies up to max entries, returns how many. */
EXPORT void freelab_hooks_trace_on(int on)
{
    trace_count = 0;
    trace_on = on;
}

EXPORT int freelab_hooks_trace(trace_entry *out, int max)
{
    int i;
    for (i = 0; i < trace_count && i < max; i++)
        out[i] = trace_ring[i];
    return i;
}

EXPORT void freelab_hooks_pixmap_counts(int64_t *mapped, int64_t *reused)
{
    *mapped = pixmaps_mapped;
    *reused = pixmaps_reused;
}

/* Tests only: wrappers bound with no import table (resolve_qt sets every original), a wrapper's
 * address, the device types mapped, and the devType of a painter's device. */
EXPORT int freelab_hooks_test_bind(uint8_t *qtgui, uint8_t *qtwidgets, double dark_l, double light_l)
{
    if (!resolve_qt(qtgui, qtwidgets))
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

EXPORT void freelab_hooks_test_canvas(int on)
{
    test_canvas = on;
}

EXPORT void freelab_hooks_test_swatch(int on)
{
    test_swatch = on;
}

/* The swatches' checkerboard squares held back so far, and of them those dropped under an opaque color. */
EXPORT void freelab_hooks_swatch_counts(int64_t *held_squares, int64_t *dropped)
{
    *held_squares = swatch_held;
    *dropped = swatch_dropped;
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
