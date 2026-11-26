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

#define FREELAB_HOOKS_VERSION 25

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
    H_PAINTER_PEN, H_PAINTER_BRUSH, H_SET_PEN_STYLE, H_SET_BRUSH_STYLE,
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
    if (!keep_count || !kept_widget(device))
        return 0; /* not one of the hooked surfaces: the script engine's */
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

/* White pens stay white: FontLab draws white lines and text only where they stand out, on a color
 * (a selected cell's blue header) or on dark; mapped with the white paper, they turned dark. White
 * fills are still mapped (they are the paper). */
static int white_pen(const qcolor *c)
{
    return (painted_rgba(c) & 0xffffffU) == 0xffffffU; /* pure white only: near-whites (a tab strip's
                                                          * #edeeef edge) are paper-colored lines */
}

/* The pen to paint with: pen itself, or a mapped copy in tmp (then *copied is 1; destroy it after). */
static const void *mapped_pen(const void *pen, qhandle *tmp, int *copied)
{
    qcolor c, m;
    *copied = 0;
    if (!qt_pen_is_solid(pen))
        return pen; /* a gradient or texture pen: setColor would replace it */
    qt_pen_color(pen, &c);
    if (white_pen(&c) || !map_qcolor(&c, &m))
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
    qhandle pen, brush; /* the copies last handed out */
} painter_note;
static painter_note painter_notes[PAINTERS_MAX];

static void drop_note(painter_note *n)
{
    if (n->has_pen)
        qt_pen_dtor(&n->pen);
    if (n->has_brush)
        qt_brush_dtor(&n->brush);
    n->pen_n = n->brush_n = n->pen_next = n->brush_next = n->has_pen = n->has_brush = n->badge = 0;
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
    if (memo_used[h] && memo_in[h] == rgb)
        return memo_out[h];
    memo_in[h] = rgb;
    memo_out[h] = map_qrgb(rgb | 0xff000000U) & 0xffffffU;
    memo_used[h] = 1;
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
    if (mode != SCREEN_SUBPIXEL && clear && white_artwork(bits, w, h, stride, format))
        return;
    if (pictures && mode != SCREEN_SUBPIXEL && color_content && is_picture(bits, w, h, stride, format, clear))
        return; /* a color glyph: drawn as the font has it */
    if (mode == SCREEN_SUBPIXEL && stride == w * 4) {
        /* opaque ClearType text on paper: the pixel helper's subpixel mapping, as the script engine's */
        freelab_map_anchors(bits, (int64_t)w * h, w, ANCHORS_SUBPIXEL, hook_dark_l, hook_light_l, 0.0,
                            subpixel_background_okl, 1);
        return;
    }
    if (!clear && stride == w * 4 && (int64_t)w * h <= ANCHORED_MAX_PIXELS) {
        /* text or glyphs drawn on paper (an installed font's preview): mapped by anchor blends */
        freelab_map_anchors(bits, (int64_t)w * h, w, ANCHORS_ALL, hook_dark_l, hook_light_l, hook_keep_tint,
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
    key = qt_image_cache_key(image) * 4 + (mode == SCREEN_SUBPIXEL) + 2 * color_content; /* a copy per mapping */
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
    key = key * 4 + (mode == SCREEN_SUBPIXEL); /* the same copy in color or not: pictures are images' */
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

#define COLOR_ON_SCREEN(index, painter, call_with)                    \
    {                                                                 \
        qcolor m;                                                     \
        const qcolor *use = c;                                        \
        hook_calls[index]++;                                          \
        if (on_screen(painter) && map_qcolor(c, &m)) {                \
            hook_changed[index]++;                                    \
            use = &m;                                                 \
        }                                                             \
        trace_color(index, painter, c, use);                          \
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
    if (on_screen(p)) {
        if ((!white_pen(c) || palette_light_color(c)) && !dark_on_badge(p, c) && map_qcolor(c, &m)) {
            hook_changed[H_SET_PEN_COLOR]++;
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
    if (on_screen(p)) {
        qcolor c;
        qt_pen_color(pen, &c);
        if (!dark_on_badge(p, &c))
            use = mapped_pen(pen, &tmp, &copied);
    } else if (ink_target(p))
        use = ink_pen(pen, &tmp, &copied);
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
        if (on_screen(painter))                                      \
            use = mapped_brush(brush, &tmp, &copied);                \
        hook_changed[index] += copied;                               \
        trace_brush(index, painter, brush, use);                     \
        call_with;                                                   \
        if (copied)                                                  \
            qt_brush_dtor(&tmp);                                     \
    }

static void w_set_brush(void *p, const void *brush)
{
    int style = qt_brush_style(brush);
    note_badge(p, hooks_on && style == BRUSH_SOLID && badge_color(qt_color_rgba(qt_brush_color(brush))));
    BRUSH_ON_SCREEN(H_SET_BRUSH, p, (note_brush(p, brush, use), ORIGINAL(H_SET_BRUSH, one_fn)(p, use)))
}

/* setPen(Qt::PenStyle) and setBrush(Qt::BrushStyle) make Qt's black pen or brush of that style
 * (QPen(style), QBrush(Qt::black, style)): FontLab writes the Fonts panel's file names with
 * setPen(Qt::SolidLine), which stayed black on the dark list. On screen they are set as the mapped
 * black instead, through the hooked setPen(QPen) and setBrush(QBrush); no pen or no brush passes. */
#define PEN_NONE 0
typedef void (*style_fn)(void *, int);

static void w_set_pen_style(void *p, int style)
{
    qcolor black, m;
    qhandle tmp;
    int ink = 0;
    hook_calls[H_SET_PEN_STYLE]++;
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

static void w_set_brush_style(void *p, int style)
{
    qcolor black, m;
    qhandle tmp;
    hook_calls[H_SET_BRUSH_STYLE]++;
    note_badge(p, 0);
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
typedef const void *(*pen_getter_fn)(const void *);
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
    forget_painter(painter);
    ORIGINAL(H_PAINTER_OFF, painter_off_fn)(painter);
}

static char w_painter_begin(void *painter, void *device)
{
    char result = ORIGINAL(H_PAINTER_BEGIN, painter_begin_fn)(painter, device);
    hook_calls[H_PAINTER_BEGIN]++;
    forget_painter(painter);
    if (result)
        note_painter(painter);
    trace_painter_pen(H_PAINTER_BEGIN, painter);
    return result;
}

static char w_painter_end(void *painter)
{
    hook_calls[H_PAINTER_END]++;
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
    (void *)w_painter_brush, (void *)w_set_pen_style, (void *)w_set_brush_style,
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

EXPORT void freelab_hooks_test_devices(uint32_t mask)
{
    map_devices = mask;
}

EXPORT int freelab_hooks_test_device_type(const void *painter)
{
    void *device = qt_painter_device(painter);
    return device ? ((int (*)(const void *))((void ***)device)[0][1])(device) : -1;
}
