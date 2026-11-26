"""Offline test of the native dark mode's hook wrappers (Python 3, Windows, FontLab 7 installed).

FontLab's own Qt5Gui is loaded into this process and each wrapper is called on real Qt objects
(QImage and a QPainter on it, QPen, QBrush, QPainterPath, QPalette). Nothing of FontLab runs; a
crash only ends this process. Painting into an image is not mapped by default (only widgets and
pixmaps are), so most checks first let images be mapped too. Not part of run_tests.py yet:

    python tests/hooks_selftest.py <path to freelab_hooks.dll>
"""
import ctypes
import os
import sys
from ctypes import c_void_p, c_int, c_uint32, c_double, c_char

QT = r"C:\Program Files\Fontlab\FontLab 7"
os.add_dll_directory(QT)
gui = ctypes.CDLL(os.path.join(QT, "Qt5Gui.dll"))
widgets_lib = ctypes.CDLL(os.path.join(QT, "Qt5Widgets.dll"))
hooks = ctypes.CDLL(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "freelab_hooks.dll"))
k32 = ctypes.WinDLL("kernel32")
k32.GetModuleHandleW.restype = c_void_p
base = k32.GetModuleHandleW("Qt5Gui.dll")
widgets_base = k32.GetModuleHandleW("Qt5Widgets.dll")
HOOKS = 31
hooks.freelab_hooks_set_hooked.argtypes = [c_void_p, c_int]
WIDGET, PIXMAP, IMAGE = 1, 2, 3


def okl_gray(byte):
    lin = (byte / 255 / 12.92) if byte / 255 <= 0.04045 else ((byte / 255 + 0.055) / 1.055) ** 2.4
    return lin ** (1 / 3)


hooks.freelab_hooks_test_bind.argtypes = [c_void_p, c_void_p, c_double, c_double]
bound = hooks.freelab_hooks_test_bind(base, widgets_base, okl_gray(31), okl_gray(219))
print("bound", bound, "of", HOOKS)
hooks.freelab_hooks_test_wrapper.restype = c_void_p
hooks.freelab_hooks_test_device_type.argtypes = [c_void_p]
hooks.freelab_hooks_test_devices.argtypes = [c_uint32]
KEEP = []


def wrapper(index, *argtypes, restype=None):
    return ctypes.CFUNCTYPE(restype, *argtypes)(hooks.freelab_hooks_test_wrapper(index))


def fn(name, *argtypes, restype=None):
    f = getattr(gui, name)
    f.argtypes = list(argtypes)
    f.restype = restype
    return f


def buf():
    b = (c_char * 256)()
    KEEP.append(b)  # alive until the end: an inline temporary is freed before the call
    return b


addr = ctypes.addressof
image_ctor = fn("??0QImage@@QEAA@HHW4Format@0@@Z", c_void_p, c_int, c_int, c_int, restype=c_void_p)
image_pixel = fn("?pixel@QImage@@QEBAIHH@Z", c_void_p, c_int, c_int, restype=c_uint32)
image_fill = fn("?fill@QImage@@QEAAXI@Z", c_void_p, c_uint32)
painter_ctor = fn("??0QPainter@@QEAA@PEAVQPaintDevice@@@Z", c_void_p, c_void_p, restype=c_void_p)
painter_end = fn("?end@QPainter@@QEAA_NXZ", c_void_p, restype=ctypes.c_bool)
painter_pen = fn("?pen@QPainter@@QEBAAEBVQPen@@XZ", c_void_p, restype=c_void_p)
painter_brush = fn("?brush@QPainter@@QEBAAEBVQBrush@@XZ", c_void_p, restype=c_void_p)
color_ctor = fn("??0QColor@@QEAA@HHHH@Z", c_void_p, c_int, c_int, c_int, c_int, restype=c_void_p)
color_rgba = fn("?rgba@QColor@@QEBAIXZ", c_void_p, restype=c_uint32)
brush_ctor = fn("??0QBrush@@QEAA@AEBVQColor@@W4BrushStyle@Qt@@@Z", c_void_p, c_void_p, c_int, restype=c_void_p)
brush_color = fn("?color@QBrush@@QEBAAEBVQColor@@XZ", c_void_p, restype=c_void_p)
pen_ctor = fn("??0QPen@@QEAA@AEBVQColor@@@Z", c_void_p, c_void_p, restype=c_void_p)
pen_color = fn("?color@QPen@@QEBA?AVQColor@@XZ", c_void_p, c_void_p, restype=c_void_p)
path_ctor = fn("??0QPainterPath@@QEAA@XZ", c_void_p, restype=c_void_p)
path_add_rect = fn("?addRect@QPainterPath@@QEAAXAEBVQRectF@@@Z", c_void_p, c_void_p)
palette_ctor = fn("??0QPalette@@QEAA@AEBVQColor@@@Z", c_void_p, c_void_p, restype=c_void_p)
palette_set_color = fn("?setColor@QPalette@@QEAAXW4ColorGroup@1@W4ColorRole@1@AEBVQColor@@@Z", c_void_p, c_int, c_int, c_void_p)
ARGB32, PREMULTIPLIED = 5, 6
results = []


def check(name, got, expect):
    rgb = got & 0xffffff
    light = max((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
    ok = {"dark": light < 80, "light": light > 150}.get(expect, rgb == expect)
    results.append(ok)
    print("%-46s %08x %s" % (name, got, "ok" if ok else "WRONG"))


def color(r, g, b, a=255):
    c = buf()
    color_ctor(addr(c), r, g, b, a)
    return c


def pen(c):
    p = buf()
    pen_ctor(addr(p), addr(c))
    return p


def brush(c, style=1):
    b = buf()
    brush_ctor(addr(b), addr(c), style)
    return b


def pen_rgba(p):
    out = buf()
    pen_color(p, addr(out))
    return color_rgba(addr(out))


def image(fmt=ARGB32, fill=None):
    img = buf()
    image_ctor(addr(img), 8, 8, fmt)
    if fill is not None:
        image_fill(addr(img), fill)
    return img


def painting(img, action):
    painter = buf()
    painter_ctor(addr(painter), addr(img))
    result = action(addr(painter))
    painter_end(addr(painter))
    return result


white, black = color(255, 255, 255), color(0, 0, 0)
rect, rectf = (c_int * 4)(0, 0, 7, 7), (c_double * 4)(0.0, 0.0, 8.0, 8.0)
origin = (c_double * 2)(0.0, 0.0)

# where colors are mapped: painting into an image is not (it stays light, mapped when drawn on screen)
img = image()
check("an image painter's device is an image", painting(img, lambda p: hooks.freelab_hooks_test_device_type(p)), IMAGE)
painting(img, lambda p: wrapper(0, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(white)))
check("fillRect(white) into an image: not mapped", image_pixel(addr(img), 2, 2), 0xffffff)
src = image(fill=0xffffffff)
target = image(fill=0xff000000)
painting(target, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(src)))
check("drawImage into an image: not mapped", image_pixel(addr(target), 3, 3), 0xffffff)

# the same calls where colors are mapped (images let through for the test)
hooks.freelab_hooks_test_devices((1 << WIDGET) | (1 << PIXMAP) | (1 << IMAGE))
painting(img, lambda p: wrapper(0, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(white)))
check("fillRect(QRect, white)", image_pixel(addr(img), 2, 2), "dark")
painting(img, lambda p: wrapper(2, c_void_p, c_int, c_int, c_int, c_int, c_void_p)(p, 0, 0, 8, 8, addr(black)))
check("fillRect(x,y,w,h, black)", image_pixel(addr(img), 3, 3), "light")
painting(img, lambda p: wrapper(3, c_void_p, c_int, c_int, c_int, c_int, c_int)(p, 0, 0, 8, 8, 3))
check("fillRect(x,y,w,h, Qt::white)", image_pixel(addr(img), 4, 4), "dark")
painting(img, lambda p: wrapper(1, c_void_p, c_void_p, c_void_p)(p, addr(rectf), addr(color(250, 250, 250))))
check("fillRect(QRectF, near white)", image_pixel(addr(img), 5, 5), "dark")
white_brush, black_brush = brush(white), brush(black)
painting(img, lambda p: wrapper(7, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(white_brush)))
check("fillRect(QRect, white brush)", image_pixel(addr(img), 2, 2), "dark")
painting(img, lambda p: wrapper(8, c_void_p, c_void_p, c_void_p)(p, addr(rectf), addr(black_brush)))
check("fillRect(QRectF, black brush)", image_pixel(addr(img), 2, 2), "light")
painting(img, lambda p: wrapper(9, c_void_p, c_int, c_int, c_int, c_int, c_void_p)(p, 0, 0, 8, 8, addr(white_brush)))
check("fillRect(x,y,w,h, white brush)", image_pixel(addr(img), 6, 6), "dark")
path = buf(); path_ctor(addr(path)); path_add_rect(addr(path), addr(rectf))
painting(img, lambda p: wrapper(10, c_void_p, c_void_p, c_void_p)(p, addr(path), addr(black_brush)))
check("fillPath(black brush)", image_pixel(addr(img), 4, 4), "light")
check("the brush itself is untouched", color_rgba(brush_color(addr(black_brush))), 0x000000)
black_pen = pen(black)
got = painting(img, lambda p: (wrapper(5, c_void_p, c_void_p)(p, addr(black_pen)), pen_rgba(painter_pen(p)))[1])
check("setPen(black pen)", got, "light")
check("the pen itself is untouched", pen_rgba(addr(black_pen)), 0x000000)
got = painting(img, lambda p: (wrapper(4, c_void_p, c_void_p)(p, addr(black)), pen_rgba(painter_pen(p)))[1])
check("setPen(black)", got, "light")
invalid = buf()  # QColor(): spec Invalid, alpha 0xffff, the rest 0; Qt paints it black
ctypes.memmove(invalid, bytes([0, 0, 0, 0, 0xff, 0xff] + [0] * 8), 14)
check("an invalid color is painted black (Qt)", painting(image(), lambda p: (fn("?setPen@QPainter@@QEAAXAEBVQColor@@@Z", c_void_p, c_void_p)(p, addr(invalid)), pen_rgba(painter_pen(p)))[1]), 0x000000)
got = painting(img, lambda p: (wrapper(4, c_void_p, c_void_p)(p, addr(invalid)), pen_rgba(painter_pen(p)))[1])
check("setPen(QColor()): mapped as black", got, "light")
painting(img, lambda p: wrapper(0, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(invalid)))
check("fillRect(QRect, QColor()): mapped as black", image_pixel(addr(img), 2, 2), "light")
white_pen = pen(white)
got = painting(img, lambda p: (wrapper(5, c_void_p, c_void_p)(p, addr(white_pen)), pen_rgba(painter_pen(p)))[1])
check("setPen(white pen): white kept", got, 0xffffff)
got = painting(img, lambda p: (wrapper(4, c_void_p, c_void_p)(p, addr(white)), pen_rgba(painter_pen(p)))[1])
check("setPen(white): white kept", got, 0xffffff)
got = painting(img, lambda p: (wrapper(4, c_void_p, c_void_p)(p, addr(color(0xed, 0xee, 0xef))), pen_rgba(painter_pen(p)))[1])
check("setPen(near white): mapped", got, "dark")
got = painting(img, lambda p: (wrapper(6, c_void_p, c_void_p)(p, addr(white_brush)), color_rgba(brush_color(painter_brush(p))))[1])
check("setBrush(white brush)", got, "dark")
blue_brush = brush(color(31, 120, 220))
got = painting(img, lambda p: (wrapper(6, c_void_p, c_void_p)(p, addr(blue_brush)), color_rgba(brush_color(painter_brush(p))))[1])
check("setBrush(mid blue) kept", got, 0x1f78dc)
painting(img, lambda p: wrapper(11, c_void_p, c_void_p)(p, addr(white_brush)))
results.append(True)

# the hooked widgets: any order, as many as given
others = (ctypes.c_uint64 * 3)(0x30000, 0x10000, 0x20000)
check("set_hooked takes the widgets", hooks.freelab_hooks_set_hooked(addr(others), 3), 3)
hooks.freelab_hooks_set_hooked(addr(others), 0)

# images drawn: a mapped copy, made once and reused; the image itself never changes
target = image(fill=0xff000000)
painting(target, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(src)))
check("drawImage(point, white image) mapped", image_pixel(addr(target), 3, 3), "dark")
check("the image itself is untouched", image_pixel(addr(src), 3, 3), 0xffffff)
target = image(fill=0xff000000)
painting(target, lambda p: wrapper(15, c_void_p, c_int, c_int, c_void_p, c_int, c_int, c_int, c_int, c_int)(p, 0, 0, addr(src), 0, 0, -1, -1, 0))
check("drawImage(x, y, white image) mapped", image_pixel(addr(target), 3, 3), "dark")
mapped_n, reused_n = ctypes.c_int64(), ctypes.c_int64()
hooks.freelab_hooks_image_counts(ctypes.byref(mapped_n), ctypes.byref(reused_n))
check("mapped once, then reused", mapped_n.value * 16 + reused_n.value, 0x11)
premul = image(PREMULTIPLIED, 0x80000000)
light_target = image(fill=0x00000000)
painting(light_target, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(premul)))
edge = image_pixel(addr(light_target), 1, 1)
results.append(0x70 <= (edge >> 24) <= 0x90 and (edge & 0xff) > 150)
print("%-46s %08x %s" % ("premultiplied edge: alpha kept, color light", edge, "ok" if results[-1] else "WRONG"))
# an image of another format (the Fonts tab's icon is 8-bit gray): converted, then mapped
GRAYSCALE8 = 24
gray = image(GRAYSCALE8, 255)
target = image(fill=0xff000000)
painting(target, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(gray)))
check("drawImage(point, white 8-bit gray image) mapped", image_pixel(addr(target), 3, 3), "dark")

# white artwork on transparency (FontLab's logo) is drawn white; it is no paper
set_pixel = fn("?setPixel@QImage@@QEAAXHHI@Z", c_void_p, c_int, c_int, c_uint32)
art = image(fill=0x00000000)
for x in range(2, 6):
    set_pixel(addr(art), x, 3, 0xffffffff)
target = image(fill=0xff000000)
painting(target, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(art)))
check("white artwork on transparency: drawn white", image_pixel(addr(target), 3, 3), 0xffffff)

# text smoothed on opaque paper keeps its coverage: half-covered gray lands halfway between the ends
paper = image(fill=0xffffffff)
for x in range(2, 6):
    set_pixel(addr(paper), x, 2, 0xff000000)
    set_pixel(addr(paper), x, 3, 0xff808080)
target = image(fill=0xff000000)
painting(target, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(paper)))
ink, half, ground = (image_pixel(addr(target), 3, y) & 0xff for y in (2, 3, 4))
results.append(ground < half < ink and abs((half - ground) - (ink - ground) * 0.5) <= (ink - ground) * 0.12)
print("%-46s %d %d %d %s" % ("opaque paper: smoothing keeps its coverage", ground, half, ink, "ok" if results[-1] else "WRONG"))

# a color font's glyph picture (yellow and white on transparency): mapped normally, kept while in color
emoji = image(fill=0x00000000)
for x in range(1, 7):
    set_pixel(addr(emoji), x, 2, 0xffffcc4d)
    set_pixel(addr(emoji), x, 4, 0xffffffff)
    set_pixel(addr(emoji), x, 5, 0xff000000)
glyph = image(fill=0x00000000)
for x in range(1, 7):
    set_pixel(addr(glyph), x, 3, 0xff000000)
hooks.freelab_hooks_set_color_content.argtypes = [c_int]


def drawn(source):
    out = image(fill=0xff808080)
    painting(out, lambda p: wrapper(13, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(source)))
    return out


check("not in color: the emoji's white mapped", image_pixel(addr(drawn(emoji)), 3, 4), "dark")
check("color on (no slots while unhooked)", hooks.freelab_hooks_set_color_content(1), 0)
check("in color: the emoji's yellow kept", image_pixel(addr(drawn(emoji)), 3, 2), 0xffcc4d)
check("in color: the emoji's white kept", image_pixel(addr(drawn(emoji)), 3, 4), 0xffffff)
check("in color: the emoji's black kept", image_pixel(addr(drawn(emoji)), 3, 5), 0x000000)
check("in color: a black glyph still mapped", image_pixel(addr(drawn(glyph)), 3, 3), "light")
accented = image(fill=0x00000000)  # black ink with a colored accent: a fifth of it, under a quarter
for x in range(8):
    set_pixel(addr(accented), x, 2, 0xff000000)
    set_pixel(addr(accented), x, 3, 0xff000000)
for x in range(2, 6):
    set_pixel(addr(accented), x, 5, 0xffffcc4d)
check("in color: a glyph with a colored accent mapped", image_pixel(addr(drawn(accented)), 3, 2), "light")
hooks.freelab_hooks_set_color_content(0)
check("color off: the emoji's white mapped again", image_pixel(addr(drawn(emoji)), 3, 4), "dark")

# palette reads: the light color wherever the palette holds the dark palette's color for the slot
ACTIVE, TEXT, BASE, ROLES = 0, 6, 9, 21
dark_table = (c_uint32 * (3 * ROLES))(*([0] * (3 * ROLES)))
light_table = (c_uint32 * (3 * ROLES))(*([0] * (3 * ROLES)))
dark_table[ACTIVE * ROLES + TEXT], light_table[ACTIVE * ROLES + TEXT] = 0xffdcdcdc, 0xff000000
dark_table[ACTIVE * ROLES + BASE], light_table[ACTIVE * ROLES + BASE] = 0xff1e1e1e, 0xffffffff
hooks.freelab_hooks_set_palette.argtypes = [c_void_p, c_void_p]
hooks.freelab_hooks_set_palette(addr(dark_table), addr(light_table))
pal = buf(); palette_ctor(addr(pal), addr(color(240, 240, 240)))
palette_set_color(addr(pal), ACTIVE, TEXT, addr(color(0xdc, 0xdc, 0xdc)))
palette_set_color(addr(pal), ACTIVE, BASE, addr(color(0x1e, 0x1e, 0x1e)))
read_text = lambda: color_rgba(wrapper(17, c_void_p, c_int, c_int, restype=c_void_p)(addr(pal), ACTIVE, TEXT))
check("no hooked painter: the dark palette's color", read_text(), 0xdcdcdc)
# a painter made through the hooks, on a surface they map: light while it is active
canvas = image()
tracked = buf()
wrapper(22, c_void_p, c_void_p, restype=c_void_p)(addr(tracked), addr(canvas))
check("QPalette::color(Active, Text): light", read_text(), 0x000000)
check("QPalette::color(Text): light", color_rgba(wrapper(18, c_void_p, c_int, restype=c_void_p)(addr(pal), TEXT)), 0x000000)
check("QPalette::brush(Active, Base): light", color_rgba(brush_color(wrapper(19, c_void_p, c_int, c_int, restype=c_void_p)(addr(pal), ACTIVE, BASE))), 0xffffff)
palette_white = wrapper(17, c_void_p, c_int, c_int, restype=c_void_p)(addr(pal), ACTIVE, BASE)
wrapper(4, c_void_p, c_void_p)(addr(tracked), palette_white)
check("setPen(the palette's white): mapped", pen_rgba(painter_pen(addr(tracked))), "dark")
palette_set_color(addr(pal), ACTIVE, TEXT, addr(color(0x12, 0x34, 0x56)))
check("a color of FontLab's own: as it is", read_text(), 0x123456)
palette_set_color(addr(pal), ACTIVE, TEXT, addr(color(0xdc, 0xdc, 0xdc)))
# read back, the pen and brush are FontLab's own colors (it makes colors from them)
wrapper(4, c_void_p, c_void_p)(addr(tracked), addr(black))
check("pen read back: the color set, not the mapped", pen_rgba(wrapper(27, c_void_p, restype=c_void_p)(addr(tracked))), 0x000000)
check("the painter itself draws the mapped", pen_rgba(painter_pen(addr(tracked))), "light")
wrapper(6, c_void_p, c_void_p)(addr(tracked), addr(white_brush))
check("brush read back: the color set", color_rgba(brush_color(wrapper(28, c_void_p, restype=c_void_p)(addr(tracked)))), 0xffffff)
check("the painter's brush: mapped", color_rgba(brush_color(painter_brush(addr(tracked)))), "dark")
# setPen(Qt::PenStyle), setBrush(Qt::BrushStyle): Qt's black of that style, mapped; none passes
pen_style = fn("?style@QPen@@QEBA?AW4PenStyle@Qt@@XZ", c_void_p, restype=c_int)
brush_style = fn("?style@QBrush@@QEBA?AW4BrushStyle@Qt@@XZ", c_void_p, restype=c_int)
set_pen_style, set_brush_style = wrapper(29, c_void_p, c_int), wrapper(30, c_void_p, c_int)
set_pen_style(addr(tracked), 3)  # Qt::DotLine
check("setPen(Qt::DotLine): black mapped", pen_rgba(painter_pen(addr(tracked))), "light")
check("its style kept", pen_style(painter_pen(addr(tracked))), 3)
check("read back: black", pen_rgba(wrapper(27, c_void_p, restype=c_void_p)(addr(tracked))), 0x000000)
set_pen_style(addr(tracked), 0)
check("setPen(Qt::NoPen): no pen", pen_style(painter_pen(addr(tracked))), 0)
set_brush_style(addr(tracked), 1)
check("setBrush(Qt::SolidPattern): black mapped", color_rgba(brush_color(painter_brush(addr(tracked)))), "light")
set_brush_style(addr(tracked), 0)
check("setBrush(Qt::NoBrush): no brush", brush_style(painter_brush(addr(tracked))), 0)
# a badge: dark text on a light, clearly colored fill (kept as it is) stays dark, until another brush
pale_blue = brush(color(0x7e, 0xbc, 0xff))
set_brush = wrapper(6, c_void_p, c_void_p)
set_pen_color = wrapper(4, c_void_p, c_void_p)
set_brush(addr(tracked), addr(pale_blue))
check("a pale blue fill: kept", color_rgba(brush_color(painter_brush(addr(tracked)))), 0x7ebcff)
set_pen_color(addr(tracked), addr(black))
check("black on it: kept black", pen_rgba(painter_pen(addr(tracked))), 0x000000)
wrapper(5, c_void_p, c_void_p)(addr(tracked), addr(black_pen))
check("a black pen on it: kept black", pen_rgba(painter_pen(addr(tracked))), 0x000000)
set_pen_style(addr(tracked), 1)
check("setPen(Qt::SolidLine) on it: kept black", pen_rgba(painter_pen(addr(tracked))), 0x000000)
set_pen_color(addr(tracked), addr(invalid))
check("setPen(QColor()) on it: kept black", pen_rgba(painter_pen(addr(tracked))), 0x000000)
set_pen_color(addr(tracked), addr(color(0xc0, 0xc0, 0xc0)))
check("a light pen on it: mapped as ever", pen_rgba(painter_pen(addr(tracked))), "dark")
set_brush_style(addr(tracked), 0)
set_pen_color(addr(tracked), addr(black))
check("no brush: black mapped again", pen_rgba(painter_pen(addr(tracked))), "light")
set_brush(addr(tracked), addr(pale_blue))
set_brush(addr(tracked), addr(white_brush))
set_pen_color(addr(tracked), addr(black))
check("a white brush after it: black mapped", pen_rgba(painter_pen(addr(tracked))), "light")
set_brush(addr(tracked), addr(blue_brush))
set_pen_color(addr(tracked), addr(black))
check("a mid blue brush is no badge: black mapped", pen_rgba(painter_pen(addr(tracked))), "light")
# a dark box: white text on a dark gray label (the glyph's caption, all selected) is mapped with the box (image 159)
label_gray, glyph_black = color(0x43, 0x43, 0x43), color(0, 0, 0)  # (held: their buffers outlive the calls)
label_brush, glyph_brush = brush(label_gray), brush(glyph_black)
set_brush(addr(tracked), addr(label_brush))
check("a dark gray label: mapped light", color_rgba(brush_color(painter_brush(addr(tracked)))), "light")
set_pen_color(addr(tracked), addr(white))
check("white text on it: mapped dark with it", pen_rgba(painter_pen(addr(tracked))), "dark")
caption_gray = color(0x64, 0x64, 0x64)
set_pen_color(addr(tracked), addr(caption_gray))
check("gray text on it: kept, dark on the light box (173)", pen_rgba(painter_pen(addr(tracked))), 0x646464)
set_brush(addr(tracked), addr(glyph_brush))
set_pen_color(addr(tracked), addr(white))
check("on black (a glyph's fill): white kept", pen_rgba(painter_pen(addr(tracked))), 0xffffff)
set_brush(addr(tracked), addr(white_brush))
set_pen_color(addr(tracked), addr(white))
check("no dark box: white kept", pen_rgba(painter_pen(addr(tracked))), 0xffffff)
# a light box: a measurement's blue number on a 60% white label is lightened to keep its contrast with the mapped box
length_blue = color(0x46, 0x78, 0xaa)
set_brush_style(addr(tracked), 0)
set_pen_color(addr(tracked), addr(length_blue))
plain = pen_rgba(painter_pen(addr(tracked)))
label_white = color(255, 255, 255, 0x96)
label_box = brush(label_white)
set_brush(addr(tracked), addr(label_box))
set_pen_color(addr(tracked), addr(length_blue))
boxed = pen_rgba(painter_pen(addr(tracked)))
channels = lambda v: ((v >> 16) & 255) + ((v >> 8) & 255) + (v & 255)
results.append(channels(boxed) > channels(plain) + 30 and (boxed & 0xff) > ((boxed >> 16) & 0xff))
print("%-46s %08x %s (%08x without the box)" % ("blue on a white label: lighter, still blue", boxed,
                                                "ok" if results[-1] else "WRONG", plain))
set_pen_color(addr(tracked), addr(black))
check("black on it: mapped as ever", pen_rgba(painter_pen(addr(tracked))), "light")
set_brush_style(addr(tracked), 0)
hooks.freelab_hooks_badge_count.restype = ctypes.c_int64
check("dark pens kept on badges and boxes", hooks.freelab_hooks_badge_count(), 5)
wrapper(25, c_void_p, restype=ctypes.c_bool)(addr(tracked))
check("ended: the dark palette's color again", read_text(), 0xdcdcdc)
check("begun again: light", (wrapper(24, c_void_p, c_void_p, restype=ctypes.c_bool)(addr(tracked), addr(canvas)), read_text())[1], 0x000000)
wrapper(23, c_void_p)(addr(tracked))
check("destroyed: the dark palette's color", read_text(), 0xdcdcdc)
hooks.freelab_hooks_test_devices(1 << WIDGET)
other = buf()
wrapper(22, c_void_p, c_void_p, restype=c_void_p)(addr(other), addr(canvas))
check("a painter on a surface not mapped: dark", read_text(), 0xdcdcdc)
wrapper(23, c_void_p)(addr(other))

calls = (ctypes.c_int64 * HOOKS)(); changed = (ctypes.c_int64 * HOOKS)()
hooks.freelab_hooks_counts(calls, changed, HOOKS)

# installing is all or none: a slot that cannot be written puts back the ones written before it.
# Qt5Widgets' imports from Qt5Gui stand in for FontLab's (this process's own copy of them).
k32.VirtualProtect.argtypes = [c_void_p, ctypes.c_size_t, c_uint32, ctypes.POINTER(c_uint32)]
k32.VirtualProtect.restype = c_int
protect_type = ctypes.CFUNCTYPE(c_int, c_void_p, ctypes.c_size_t, c_uint32, ctypes.POINTER(c_uint32))
protect_calls = [0, None]  # calls so far, the call that fails


def protect(address, size, new, old):
    protect_calls[0] += 1
    if protect_calls[0] == protect_calls[1]:
        return 0
    return k32.VirtualProtect(address, size, new, old)


protect_fn = protect_type(protect)
hooks.freelab_hooks_init.argtypes = [c_void_p, c_void_p, c_void_p]
hooks.freelab_hooks_add_module.argtypes = [c_void_p]
hooks.freelab_hooks_install.argtypes = [c_double, c_double, c_double]
check("init with a VirtualProtect of the test's", hooks.freelab_hooks_init(base, ctypes.cast(protect_fn, c_void_p).value, widgets_base), 1)
found = hooks.freelab_hooks_add_module(widgets_base)
results.append(found >= 3)
print("%-46s %d %s" % ("Qt5Widgets' slots found", found, "ok" if results[-1] else "WRONG"))
protect_calls[:] = [0, 5]  # two calls a slot: the third slot fails
check("a slot not written: install fails (-2)", hooks.freelab_hooks_install(okl_gray(31), okl_gray(219), 0.0) + 2, 0)
check("and the slots written before it are put back", hooks.freelab_hooks_remove(), 0)
protect_calls[:] = [0, None]
installed = hooks.freelab_hooks_install(okl_gray(31), okl_gray(219), 0.0)
check("every slot written: all hooked", installed, found)
check("and all put back", hooks.freelab_hooks_remove(), found)
print("calls  ", list(calls)); print("changed", list(changed))
ok = all(results) and bound == HOOKS
print("ALL OK" if ok else "FAILURES")
sys.exit(0 if ok else 1)
