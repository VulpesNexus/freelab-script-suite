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
hooks = ctypes.CDLL(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "freelab_hooks.dll"))
k32 = ctypes.WinDLL("kernel32")
k32.GetModuleHandleW.restype = c_void_p
base = k32.GetModuleHandleW("Qt5Gui.dll")
HOOKS = 22
hooks.freelab_hooks_set_keep.argtypes = [c_void_p, c_int]
WIDGET, PIXMAP, IMAGE = 1, 2, 3


def okl_gray(byte):
    lin = (byte / 255 / 12.92) if byte / 255 <= 0.04045 else ((byte / 255 + 0.055) / 1.055) ** 2.4
    return lin ** (1 / 3)


hooks.freelab_hooks_test_bind.argtypes = [c_void_p, c_double, c_double]
bound = hooks.freelab_hooks_test_bind(base, okl_gray(31), okl_gray(219))
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
white_pen = pen(white)
got = painting(img, lambda p: (wrapper(5, c_void_p, c_void_p)(p, addr(white_pen)), pen_rgba(painter_pen(p)))[1])
check("setPen(white pen): white kept", got, 0xffffff)
got = painting(img, lambda p: (wrapper(4, c_void_p, c_void_p)(p, addr(white)), pen_rgba(painter_pen(p)))[1])
check("setPen(white): white kept", got, 0xffffff)
got = painting(img, lambda p: (wrapper(6, c_void_p, c_void_p)(p, addr(white_brush)), color_rgba(brush_color(painter_brush(p))))[1])
check("setBrush(white brush)", got, "dark")
blue_brush = brush(color(31, 120, 220))
got = painting(img, lambda p: (wrapper(6, c_void_p, c_void_p)(p, addr(blue_brush)), color_rgba(brush_color(painter_brush(p))))[1])
check("setBrush(mid blue) kept", got, 0x1f78dc)
painting(img, lambda p: wrapper(11, c_void_p, c_void_p)(p, addr(white_brush)))
results.append(True)

# a keep list that does not name this painter's device changes nothing
others = (ctypes.c_uint64 * 3)(0x30000, 0x10000, 0x20000)
hooks.freelab_hooks_set_keep(addr(others), 3)
painting(img, lambda p: wrapper(0, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(white)))
check("kept widgets elsewhere: still mapped", image_pixel(addr(img), 2, 2), "dark")
hooks.freelab_hooks_set_keep(addr(others), 0)

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
check("QPalette::color(Active, Text): light", color_rgba(wrapper(17, c_void_p, c_int, c_int, restype=c_void_p)(addr(pal), ACTIVE, TEXT)), 0x000000)
check("QPalette::color(Text): light", color_rgba(wrapper(18, c_void_p, c_int, restype=c_void_p)(addr(pal), TEXT)), 0x000000)
check("QPalette::brush(Active, Base): light", color_rgba(brush_color(wrapper(19, c_void_p, c_int, c_int, restype=c_void_p)(addr(pal), ACTIVE, BASE))), 0xffffff)
palette_set_color(addr(pal), ACTIVE, TEXT, addr(color(0x12, 0x34, 0x56)))
check("a color of FontLab's own: as it is", color_rgba(wrapper(17, c_void_p, c_int, c_int, restype=c_void_p)(addr(pal), ACTIVE, TEXT)), 0x123456)

calls = (ctypes.c_int64 * HOOKS)(); changed = (ctypes.c_int64 * HOOKS)()
hooks.freelab_hooks_counts(calls, changed, HOOKS)
print("calls  ", list(calls)); print("changed", list(changed))
ok = all(results) and bound == HOOKS
print("ALL OK" if ok else "FAILURES")
sys.exit(0 if ok else 1)
