"""Offline test of the native dark mode's hook wrappers (Python 3, Windows, FontLab 7 installed).

FontLab's own Qt5Gui is loaded into this process and each wrapper is called on real Qt objects
(QImage, QPainter on it, QPen, QBrush, QPainterPath, QLinearGradient). Nothing of FontLab runs; a
crash only ends this process. Not part of run_tests.py yet (the native version is experimental):

    python tests/hooks_selftest.py <path to freelab_hooks.dll>
"""
import ctypes, os, sys
from ctypes import c_void_p, c_int, c_uint32, c_double, c_char

QT = r"C:\Program Files\Fontlab\FontLab 7"
os.add_dll_directory(QT)
gui = ctypes.CDLL(os.path.join(QT, "Qt5Gui.dll"))
hooks = ctypes.CDLL(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "freelab_hooks.dll"))
k32 = ctypes.WinDLL("kernel32")
k32.GetModuleHandleW.restype = c_void_p
base = k32.GetModuleHandleW("Qt5Gui.dll")


def okl_gray(byte):
    lin = (byte / 255 / 12.92) if byte / 255 <= 0.04045 else ((byte / 255 + 0.055) / 1.055) ** 2.4
    return lin ** (1 / 3)


hooks.freelab_hooks_test_bind.argtypes = [c_void_p, c_double, c_double]
bound = hooks.freelab_hooks_test_bind(base, okl_gray(31), okl_gray(219))
HOOKS = 24
print("bound", bound, "of", HOOKS)
hooks.freelab_hooks_test_wrapper.restype = c_void_p
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
lg_ctor = fn("??0QLinearGradient@@QEAA@NNNN@Z", c_void_p, c_double, c_double, c_double, c_double, restype=c_void_p)
stops = fn("?stops@QGradient@@QEBA?AV?$QVector@U?$QPair@NVQColor@@@@@@XZ", c_void_p, c_void_p, restype=c_void_p)
ARGB32 = 5
results = []


def check(name, got, expect):
    rgb = got & 0xffffff
    light = max((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
    ok = {"dark": light < 80, "light": light > 150}.get(expect, rgb == expect)
    results.append(ok)
    print("%-40s %08x %s" % (name, got, "ok" if ok else "WRONG"))


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


def image():
    img = buf()
    image_ctor(addr(img), 8, 8, ARGB32)
    return img


def painting(img, action):
    painter = buf()
    painter_ctor(addr(painter), addr(img))
    result = action(addr(painter))
    painter_end(addr(painter))
    return result


white, black = color(255, 255, 255), color(0, 0, 0)
img = image()
rect, rectf = (c_int * 4)(0, 0, 7, 7), (c_double * 4)(0.0, 0.0, 8.0, 8.0)

wrapper(13, c_void_p, c_uint32)(addr(img), 0xffffffff)
check("QImage::fill(white pixel)", image_pixel(addr(img), 1, 1), "dark")
wrapper(14, c_void_p, c_int)(addr(img), 3)
check("QImage::fill(Qt::white)", image_pixel(addr(img), 1, 1), "dark")
painting(img, lambda p: wrapper(0, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(white)))
check("fillRect(QRect, white)", image_pixel(addr(img), 2, 2), "dark")
painting(img, lambda p: wrapper(2, c_void_p, c_int, c_int, c_int, c_int, c_void_p)(p, 0, 0, 8, 8, addr(black)))
check("fillRect(x,y,w,h, black)", image_pixel(addr(img), 3, 3), "light")
painting(img, lambda p: wrapper(3, c_void_p, c_int, c_int, c_int, c_int, c_int)(p, 0, 0, 8, 8, 3))
check("fillRect(x,y,w,h, Qt::white)", image_pixel(addr(img), 4, 4), "dark")
painting(img, lambda p: wrapper(1, c_void_p, c_void_p, c_void_p)(p, addr(rectf), addr(color(250, 250, 250))))
check("fillRect(QRectF, near white)", image_pixel(addr(img), 5, 5), "dark")

white_brush = brush(white)
painting(img, lambda p: wrapper(7, c_void_p, c_void_p, c_void_p)(p, addr(rect), addr(white_brush)))
check("fillRect(QRect, white brush)", image_pixel(addr(img), 2, 2), "dark")
black_brush = brush(black)
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
got = painting(img, lambda p: (wrapper(6, c_void_p, c_void_p)(p, addr(white_brush)), color_rgba(brush_color(painter_brush(p))))[1])
check("setBrush(white brush)", got, "dark")
blue_brush = brush(color(31, 120, 220))
got = painting(img, lambda p: (wrapper(6, c_void_p, c_void_p)(p, addr(blue_brush)), color_rgba(brush_color(painter_brush(p))))[1])
check("setBrush(mid blue) kept", got, 0x1f78dc)
got = painting(img, lambda p: (wrapper(11, c_void_p, c_void_p)(p, addr(white_brush)), 0)[1])
results.append(True)
print("%-40s %s" % ("setBackground(white brush)", "called"))

grad = buf(); lg_ctor(addr(grad), 0.0, 0.0, 1.0, 0.0)
wrapper(15, c_void_p, c_double, c_void_p)(addr(grad), 0.5, addr(white))
vec = buf(); stops(addr(grad), addr(vec))
d = c_void_p.from_address(addr(vec)).value  # QVector's QArrayData*: size at 4, data offset at 16
first = d + ctypes.c_int64.from_address(d + 16).value  # QPair<double, QColor>: the color at 8
check("QGradient::setColorAt(white)", color_rgba(first + 8), "dark")

# images: drawn as a mapped copy, kept and reused; FontLab's own image never changes
draw_image_pt = fn("?drawImage@QPainter@@QEAAXAEBVQPointF@@AEBVQImage@@@Z", c_void_p, c_void_p, c_void_p)
src = image()
image_fill = fn("?fill@QImage@@QEAAXI@Z", c_void_p, c_uint32)
image_fill(addr(src), 0xffffffff)
target = image()
image_fill(addr(target), 0xff000000)
origin = (c_double * 2)(0.0, 0.0)
painting(target, lambda p: wrapper(16, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(src)))
check("drawImage(point, white image) mapped", image_pixel(addr(target), 3, 3), "dark")
check("the image itself is untouched", image_pixel(addr(src), 3, 3), 0xffffff)
image_fill(addr(target), 0xff000000)
painting(target, lambda p: wrapper(18, c_void_p, c_int, c_int, c_void_p, c_int, c_int, c_int, c_int, c_int)(p, 0, 0, addr(src), 0, 0, -1, -1, 0))
check("drawImage(x, y, white image) mapped", image_pixel(addr(target), 3, 3), "dark")
mapped_n, reused_n = ctypes.c_int64(), ctypes.c_int64()
hooks.freelab_hooks_image_counts(ctypes.byref(mapped_n), ctypes.byref(reused_n))
check("mapped once, then reused", mapped_n.value * 16 + reused_n.value, 0x11)
# a glyph's smoothed edge: half-transparent black in a premultiplied image comes out half-transparent light
premul = buf(); image_ctor(addr(premul), 4, 4, 6)
image_fill(addr(premul), 0x80000000)
light_target = image()
image_fill(addr(light_target), 0x00000000)
painting(light_target, lambda p: wrapper(16, c_void_p, c_void_p, c_void_p)(p, addr(origin), addr(premul)))
edge = image_pixel(addr(light_target), 1, 1)
results.append(0x70 <= (edge >> 24) <= 0x90 and (edge & 0xff) > 150)
print("%-40s %08x %s" % ("premultiplied edge: alpha kept, color light", edge, "ok" if results[-1] else "WRONG"))
painter_set_brush_raw = fn("?setBrush@QPainter@@QEAAXAEBVQBrush@@@Z", c_void_p, c_void_p)
image_fill(addr(target), 0xff000000)
painting(target, lambda p: (painter_set_brush_raw(p, addr(white_brush)), wrapper(22, c_void_p, c_void_p)(p, addr(path)))[1])
check("drawPath(white brush, unhooked) as is", image_pixel(addr(target), 4, 4), 0xffffff)
pixels = (ctypes.c_uint32 * 16)(*([0xff336699] * 16))
wrapped = buf()
wrapper(23, c_void_p, c_void_p, c_int, c_int, c_int, c_int, c_void_p, c_void_p, restype=c_void_p)(
    addr(wrapped), addr(pixels), 4, 4, 16, ARGB32, None, None)
check("QImage(data) wraps the buffer", image_pixel(addr(wrapped), 1, 1), 0x336699)
drawn, wrapped_f = (ctypes.c_int64 * 32)(), (ctypes.c_int64 * 32)()
hooks.freelab_hooks_formats(drawn, wrapped_f, 32)
check("formats noted (ARGB32 drawn twice)", drawn[ARGB32], 2)
check("formats noted (ARGB32 wrapped once)", wrapped_f[ARGB32], 1)

calls = (ctypes.c_int64 * HOOKS)(); changed = (ctypes.c_int64 * HOOKS)()
hooks.freelab_hooks_counts(calls, changed, HOOKS)
print("calls  ", list(calls)); print("changed", list(changed))
print("ALL OK" if all(results) and bound == HOOKS else "FAILURES")
sys.exit(0 if all(results) and bound == HOOKS else 1)
