/* FreeLab native dark mode (experimental): FontLab's own colors, mapped as FontLab paints with them.
 *
 * The script version of dark mode maps the pixels widgets have drawn. This one changes the colors
 * before anything is drawn: it points the entries of FontLab 7.exe's import table for Qt's
 * color-carrying painting calls at wrappers that map the color, then call Qt, which then draws dark
 * itself, text smoothing included. Only FontLab's import table changes; Qt's code is untouched, and
 * removing the hooks writes the original addresses back.
 *
 * Colors are mapped where they are used, on the painter (setPen, setBrush, fillRect, fillPath,
 * setBackground) and in fills, never where they are made: FontLab builds most pens and brushes once
 * and keeps them (mapped at construction, those made before the hooks stayed light, and those made
 * after would be mapped twice when used), and a QColor it makes may be a mark color it saves in a
 * font. A pen or brush is mapped on a temporary copy; FontLab's own object is never changed.
 *
 * No C runtime and no imports: the caller passes the module bases and VirtualProtect. The Qt 5
 * ABI (Qt 5.14.2, MSVC x64) is what FontLab 7 ships: on x64 a member function takes `this` as its
 * first argument, and one returning a class by value takes the return slot next.
 */
#include "freelab_pixels.c"

#define FREELAB_HOOKS_VERSION 2

typedef int (*virtual_protect_fn)(void *, size_t, uint32_t, uint32_t *);
#define PAGE_READWRITE_ 0x04

/* QColor (Qt 5): its spec, then alpha, red, green, blue as 16-bit values (and a pad). */
typedef struct {
    int32_t spec;
    uint16_t alpha, red, green, blue, pad;
} qcolor;
#define QCOLOR_INVALID 0
#define QCOLOR_RGB 1

/* QPen and QBrush hold one pointer; room for a temporary copy. */
typedef struct {
    void *d[2];
} qhandle;

static virtual_protect_fn vprotect;
static int hooks_on;
static double hook_dark_l = 0.18, hook_light_l = 0.88;

/* Qt functions called directly (resolved from Qt5Gui's export table). */
static uint32_t (*qt_color_rgba)(const qcolor *);
static void *(*qt_color_from_global)(qcolor *, int);
static void (*qt_image_fill_color)(void *, const qcolor *);
static int (*qt_image_format)(const void *);
static int (*qt_pen_is_solid)(const void *);
static qcolor *(*qt_pen_color)(const void *, qcolor *);
static void *(*qt_pen_copy)(void *, const void *);
static void (*qt_pen_set_color)(void *, const qcolor *);
static void (*qt_pen_dtor)(void *);
static int (*qt_brush_style)(const void *);
static const qcolor *(*qt_brush_color)(const void *);
static void *(*qt_brush_copy)(void *, const void *);
static void (*qt_brush_set_color)(void *, const qcolor *);
static void (*qt_brush_dtor)(void *);

static struct {
    const char *name;
    void **slot;
} qt_needed[] = {
    {"?rgba@QColor@@QEBAIXZ", (void **)&qt_color_rgba},
    {"??0QColor@@QEAA@W4GlobalColor@Qt@@@Z", (void **)&qt_color_from_global},
    {"?fill@QImage@@QEAAXAEBVQColor@@@Z", (void **)&qt_image_fill_color},
    {"?format@QImage@@QEBA?AW4Format@1@XZ", (void **)&qt_image_format},
    {"?isSolid@QPen@@QEBA_NXZ", (void **)&qt_pen_is_solid},
    {"?color@QPen@@QEBA?AVQColor@@XZ", (void **)&qt_pen_color},
    {"??0QPen@@QEAA@AEBV0@@Z", (void **)&qt_pen_copy},
    {"?setColor@QPen@@QEAAXAEBVQColor@@@Z", (void **)&qt_pen_set_color},
    {"??1QPen@@QEAA@XZ", (void **)&qt_pen_dtor},
    {"?style@QBrush@@QEBA?AW4BrushStyle@Qt@@XZ", (void **)&qt_brush_style},
    {"?color@QBrush@@QEBAAEBVQColor@@XZ", (void **)&qt_brush_color},
    {"??0QBrush@@QEAA@AEBV0@@Z", (void **)&qt_brush_copy},
    {"?setColor@QBrush@@QEAAXAEBVQColor@@@Z", (void **)&qt_brush_set_color},
    {"??1QBrush@@QEAA@XZ", (void **)&qt_brush_dtor},
};
#define QT_NEEDED (int)(sizeof(qt_needed) / sizeof(qt_needed[0]))

/* The hooked imports: name, wrapper, original. */
enum {
    H_FILL_RECT, H_FILL_RECTF, H_FILL_XYWH, H_FILL_XYWH_GLOBAL, H_SET_PEN_COLOR, H_SET_PEN, H_SET_BRUSH,
    H_FILL_RECT_BRUSH, H_FILL_RECTF_BRUSH, H_FILL_XYWH_BRUSH, H_FILL_PATH, H_SET_BACKGROUND,
    H_PIXMAP_FILL, H_IMAGE_FILL_PIXEL, H_IMAGE_FILL_GLOBAL, H_GRADIENT_STOP,
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
    "?fill@QImage@@QEAAXI@Z",
    "?fill@QImage@@QEAAXW4GlobalColor@Qt@@@Z",
    "?setColorAt@QGradient@@QEAAXNAEBVQColor@@@Z",
};
static void *originals[H_COUNT];
static void **slots[H_COUNT];
static int64_t hook_calls[H_COUNT];
static int64_t hook_changed[H_COUNT];

/* ---- the color rule --------------------------------------------------------------------------- */

/* Interface colors as the script maps them (lightness inverted in OKLab, grays to dark mode's grays);
 * clearly colored ones of middle lightness or lighter (selection blues, marks, node colors) kept. */
static uint32_t map_qrgb(uint32_t rgb)
{
    double l, chroma;
    oklab_of(rgb & 0xffffffU, &l, &chroma);
    if (chroma >= CONTENT_KEEP_CHROMA && l >= CONTENT_KEEP_MIN_OKL)
        return rgb;
    return (rgb & 0xff000000U) | (mapped_one(rgb & 0xffffffU, hook_dark_l, hook_light_l, 0.0) & 0xffffffU);
}

/* out = the dark-mode counterpart of c; returns 1 when it differs. */
static int map_qcolor(const qcolor *c, qcolor *out)
{
    uint32_t argb, mapped;
    *out = *c;
    if (!hooks_on || c->spec == QCOLOR_INVALID || qt_color_rgba == 0)
        return 0;
    argb = qt_color_rgba(c);
    mapped = map_qrgb(argb);
    if (mapped == argb)
        return 0;
    out->spec = QCOLOR_RGB;
    out->alpha = (uint16_t)(((argb >> 24) & 255) * 0x101);
    out->red = (uint16_t)(((mapped >> 16) & 255) * 0x101);
    out->green = (uint16_t)(((mapped >> 8) & 255) * 0x101);
    out->blue = (uint16_t)((mapped & 255) * 0x101);
    out->pad = 0;
    return 1;
}

static void global_color(int global, qcolor *out)
{
    out->spec = QCOLOR_INVALID;
    if (qt_color_from_global)
        qt_color_from_global(out, global);
}

/* The pen to paint with: pen itself, or a mapped copy in tmp (then *copied is 1; destroy it after). */
static const void *mapped_pen(const void *pen, qhandle *tmp, int *copied)
{
    qcolor c, m;
    *copied = 0;
    if (!hooks_on || !qt_pen_is_solid(pen))
        return pen; /* a gradient or texture pen: setColor would replace it */
    qt_pen_color(pen, &c);
    if (!map_qcolor(&c, &m))
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
    if (!hooks_on)
        return brush;
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

/* ---- wrappers ----------------------------------------------------------------------------------- */

typedef void (*fill_rect_fn)(void *, const void *, const void *);
typedef void (*fill_xywh_fn)(void *, int, int, int, int, const void *);
typedef void (*fill_xywh_global_fn)(void *, int, int, int, int, int);
typedef void (*one_arg_fn)(void *, const void *);
typedef void (*image_fill_pixel_fn)(void *, uint32_t);
typedef void (*image_fill_global_fn)(void *, int);
typedef void (*gradient_stop_fn)(void *, double, const qcolor *);

#define COLOR_WRAPPER(fn_name, index, call)              \
    {                                                   \
        qcolor m;                                       \
        hook_calls[index]++;                            \
        hook_changed[index] += map_qcolor(c, &m);       \
        call;                                           \
    }

static void w_fill_rect(void *p, const void *r, const qcolor *c) COLOR_WRAPPER(w_fill_rect, H_FILL_RECT, ((fill_rect_fn)originals[H_FILL_RECT])(p, r, &m))
static void w_fill_rectf(void *p, const void *r, const qcolor *c) COLOR_WRAPPER(w_fill_rectf, H_FILL_RECTF, ((fill_rect_fn)originals[H_FILL_RECTF])(p, r, &m))
static void w_fill_xywh(void *p, int x, int y, int w, int h, const qcolor *c) COLOR_WRAPPER(w_fill_xywh, H_FILL_XYWH, ((fill_xywh_fn)originals[H_FILL_XYWH])(p, x, y, w, h, &m))
static void w_set_pen_color(void *p, const qcolor *c) COLOR_WRAPPER(w_set_pen_color, H_SET_PEN_COLOR, ((one_arg_fn)originals[H_SET_PEN_COLOR])(p, &m))
static void w_pixmap_fill(void *p, const qcolor *c) COLOR_WRAPPER(w_pixmap_fill, H_PIXMAP_FILL, ((one_arg_fn)originals[H_PIXMAP_FILL])(p, &m))
static void w_gradient_stop(void *g, double at, const qcolor *c) COLOR_WRAPPER(w_gradient_stop, H_GRADIENT_STOP, ((gradient_stop_fn)originals[H_GRADIENT_STOP])(g, at, &m))

static void w_fill_xywh_global(void *painter, int x, int y, int w, int h, int global)
{
    qcolor c, m;
    hook_calls[H_FILL_XYWH_GLOBAL]++;
    global_color(global, &c);
    if (hooks_on && originals[H_FILL_XYWH] && c.spec != QCOLOR_INVALID && map_qcolor(&c, &m)) {
        hook_changed[H_FILL_XYWH_GLOBAL]++;
        ((fill_xywh_fn)originals[H_FILL_XYWH])(painter, x, y, w, h, &m);
        return;
    }
    ((fill_xywh_global_fn)originals[H_FILL_XYWH_GLOBAL])(painter, x, y, w, h, global);
}

static void w_set_pen(void *painter, const void *pen)
{
    qhandle tmp;
    int copied;
    const void *use;
    hook_calls[H_SET_PEN]++;
    use = mapped_pen(pen, &tmp, &copied);
    hook_changed[H_SET_PEN] += copied;
    ((one_arg_fn)originals[H_SET_PEN])(painter, use);
    if (copied)
        qt_pen_dtor(&tmp);
}

#define BRUSH_WRAPPER(index, call)                       \
    {                                                   \
        qhandle tmp;                                    \
        int copied;                                     \
        const void *use;                                \
        hook_calls[index]++;                            \
        use = mapped_brush(brush, &tmp, &copied);       \
        hook_changed[index] += copied;                  \
        call;                                           \
        if (copied)                                     \
            qt_brush_dtor(&tmp);                        \
    }

static void w_set_brush(void *p, const void *brush) BRUSH_WRAPPER(H_SET_BRUSH, ((one_arg_fn)originals[H_SET_BRUSH])(p, use))
static void w_set_background(void *p, const void *brush) BRUSH_WRAPPER(H_SET_BACKGROUND, ((one_arg_fn)originals[H_SET_BACKGROUND])(p, use))
static void w_fill_rect_brush(void *p, const void *r, const void *brush) BRUSH_WRAPPER(H_FILL_RECT_BRUSH, ((fill_rect_fn)originals[H_FILL_RECT_BRUSH])(p, r, use))
static void w_fill_rectf_brush(void *p, const void *r, const void *brush) BRUSH_WRAPPER(H_FILL_RECTF_BRUSH, ((fill_rect_fn)originals[H_FILL_RECTF_BRUSH])(p, r, use))
static void w_fill_path(void *p, const void *path, const void *brush) BRUSH_WRAPPER(H_FILL_PATH, ((fill_rect_fn)originals[H_FILL_PATH])(p, path, use))
static void w_fill_xywh_brush(void *p, int x, int y, int w, int h, const void *brush) BRUSH_WRAPPER(H_FILL_XYWH_BRUSH, ((fill_xywh_fn)originals[H_FILL_XYWH_BRUSH])(p, x, y, w, h, use))

/* QImage::fill(uint) takes a pixel value in the image's own format: mapped only for the 32-bit RGB
 * formats with an opaque value (an index or a premultiplied value would be something else). */
#define QIMAGE_RGB32 4
#define QIMAGE_ARGB32 5
#define QIMAGE_ARGB32_PREMULTIPLIED 6
static void w_image_fill_pixel(void *image, uint32_t pixel)
{
    hook_calls[H_IMAGE_FILL_PIXEL]++;
    if (hooks_on && qt_image_format) {
        int format = qt_image_format(image);
        if ((format == QIMAGE_RGB32 || format == QIMAGE_ARGB32 || format == QIMAGE_ARGB32_PREMULTIPLIED)
            && (format == QIMAGE_RGB32 || (pixel >> 24) == 255)) {
            uint32_t mapped = map_qrgb(pixel | 0xff000000U);
            if ((mapped & 0xffffffU) != (pixel & 0xffffffU)) {
                hook_changed[H_IMAGE_FILL_PIXEL]++;
                pixel = (pixel & 0xff000000U) | (mapped & 0xffffffU);
            }
        }
    }
    ((image_fill_pixel_fn)originals[H_IMAGE_FILL_PIXEL])(image, pixel);
}

static void w_image_fill_global(void *image, int global)
{
    qcolor c, m;
    hook_calls[H_IMAGE_FILL_GLOBAL]++;
    global_color(global, &c);
    if (hooks_on && qt_image_fill_color && c.spec != QCOLOR_INVALID && map_qcolor(&c, &m)) {
        hook_changed[H_IMAGE_FILL_GLOBAL]++;
        qt_image_fill_color(image, &m);
        return;
    }
    ((image_fill_global_fn)originals[H_IMAGE_FILL_GLOBAL])(image, global);
}

static void *wrappers[H_COUNT] = {
    (void *)w_fill_rect, (void *)w_fill_rectf, (void *)w_fill_xywh, (void *)w_fill_xywh_global,
    (void *)w_set_pen_color, (void *)w_set_pen, (void *)w_set_brush, (void *)w_fill_rect_brush,
    (void *)w_fill_rectf_brush, (void *)w_fill_xywh_brush, (void *)w_fill_path, (void *)w_set_background,
    (void *)w_pixmap_fill, (void *)w_image_fill_pixel, (void *)w_image_fill_global, (void *)w_gradient_stop,
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
    return 1;
}

/* ---- exports ------------------------------------------------------------------------------------ */

EXPORT int freelab_hooks_version(void)
{
    return FREELAB_HOOKS_VERSION * 1000 + FREELAB_PIXELS_VERSION;
}

/* Resolve what the wrappers call; returns the number of hookable imports found in the module,
 * or -1 when one of Qt's functions is missing (another Qt build: nothing is hooked). */
EXPORT int freelab_hooks_init(uint8_t *module, uint8_t *qtgui, void *virtual_protect)
{
    int i, found = 0;
    vprotect = (virtual_protect_fn)virtual_protect;
    if (!resolve_qt(qtgui))
        return -1;
    for (i = 0; i < H_COUNT; i++) {
        if (!slots[i]) {
            slots[i] = find_import_slot(module, "Qt5Gui.dll", hook_names[i]);
            originals[i] = slots[i] ? *slots[i] : 0;
        }
        found += slots[i] != 0;
    }
    return found;
}

/* Point the import slots at the wrappers (mapping on); returns how many were hooked. */
EXPORT int freelab_hooks_install(double dark_l, double light_l)
{
    int i, hooked = 0;
    if (!vprotect)
        return -1;
    hook_dark_l = dark_l;
    hook_light_l = light_l;
    hooks_on = 1;
    for (i = 0; i < H_COUNT; i++)
        if (slots[i] && originals[i] && write_slot(slots[i], wrappers[i]))
            hooked++;
    return hooked;
}

/* Mapping on or off without touching the slots (the wrappers then pass colors through). */
EXPORT void freelab_hooks_enable(int on)
{
    hooks_on = on;
}

/* Write the original addresses back; returns how many slots were restored. */
EXPORT int freelab_hooks_remove(void)
{
    int i, restored = 0;
    hooks_on = 0;
    for (i = 0; i < H_COUNT; i++)
        if (slots[i] && originals[i] && *slots[i] == wrappers[i] && write_slot(slots[i], originals[i]))
            restored++;
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

/* Tests only: bind the wrappers to Qt's own functions (no import table involved), and hand out a
 * wrapper's address, so a test process can call each wrapper on real Qt objects. */
EXPORT int freelab_hooks_test_bind(uint8_t *qtgui, double dark_l, double light_l)
{
    int i, bound = 0;
    if (!resolve_qt(qtgui))
        return -1;
    for (i = 0; i < H_COUNT; i++) {
        originals[i] = find_export(qtgui, hook_names[i]);
        bound += originals[i] != 0;
    }
    hook_dark_l = dark_l;
    hook_light_l = light_l;
    hooks_on = 1;
    return bound;
}

EXPORT void *freelab_hooks_test_wrapper(int index)
{
    return index >= 0 && index < H_COUNT ? wrappers[index] : 0;
}
