#FLM: FreeLab: Toggle Dark Mode
# -*- coding: utf-8 -*-
"""FreeLab dark mode for FontLab's interface.

Run this file from FontLab's Scripts menu to switch dark mode on or off; the
choice is remembered. With the FreeLab startup hook installed
(tools/install-fontlab.ps1), FontLab applies the remembered choice at launch.

FontLab 7 has no theme: it colors its interface three ways, and dark mode
handles each.

1. The application palette and style: switched to Fusion with a dark palette.
2. About a thousand widgets carry their own stylesheet with fixed light
   colors, which win over the palette. Each is rewritten with every color's
   lightness inverted (hue and saturation kept).
3. Some widgets paint fixed light colors in FontLab's own code: the glyph
   canvas, rulers, tab bars, search fields, previews, and more. These become
   "islands": they keep their original light look, and a graphics effect maps
   the lightness of everything they draw, so black outlines turn light while
   mark colors keep their hue. Known ones are listed below; any other widget
   that still paints mostly light is found by rendering it once.

Icons and label images are mapped the same way, panel title strips through a
narrow effect. The mapping runs in a small native helper
(darkmode/native/freelab_pixels.c, built by tools/build-native.ps1); without
it, islands fall back to plain color inversion. Work is spread over short
timer slices so FontLab stays responsive, and widgets FontLab creates later
are picked up by a periodic sweep. Everything is saved first and restored
when dark mode is switched off, without a restart, including FontLab's
workspace color preference, which dark mode sets so the canvas comes out dark.

Valid Python 2.7 (FontLab 7) and Python 3 (FontLab 8).
"""

from __future__ import absolute_import, division, print_function

import json
import os
import re
import sys
import time

VERSION = "0.2.0"
MODULE_NAME = "freelab_dark_mode"
REAPPLY_DELAYS_MS = (0, 1500, 5000)  # FontLab may restyle itself after the startup script runs
ORIGINAL_STYLE_FALLBACK = "windowsvista"  # Qt's default on Windows; the only style plugin FontLab 7 ships

# Dark palette: (role, color for all groups, color for the Disabled group or None).
PALETTE = (
    ("Window", "#2d2d30", None),
    ("WindowText", "#dcdcdc", "#7f7f7f"),
    ("Base", "#1e1e1e", "#262626"),
    ("AlternateBase", "#262628", None),
    ("ToolTipBase", "#3c3c40", None),
    ("ToolTipText", "#e0e0e0", None),
    ("Text", "#dcdcdc", "#7f7f7f"),
    ("Button", "#3a3a3d", "#333336"),
    ("ButtonText", "#dcdcdc", "#7f7f7f"),
    ("BrightText", "#ff6b6b", None),
    ("Light", "#505054", None),
    ("Midlight", "#434347", None),
    ("Mid", "#2a2a2d", None),
    ("Dark", "#1b1b1d", None),
    ("Shadow", "#0e0e0f", None),
    ("Highlight", "#3d6fb4", "#3a3a3d"),
    ("HighlightedText", "#e0e0e0", "#9a9a9a"),
    ("Link", "#6aa8ff", None),
    ("LinkVisited", "#b48cff", None),
    ("PlaceholderText", "#8a8a8a", None),
)

# FreeLab 0.1 appended a block starting with this line to the application
# stylesheet; restore() still takes it out. (An application stylesheet change
# repolishes every widget, about a second in FontLab, and the palette already
# darkens menus and tooltips under Fusion.)
STYLESHEET_MARK = u"/* FreeLab dark mode */"

# Colors are mapped in OKLab, where lightness L follows what the eye sees and hues stay
# put: L becomes DARK_OKL + (1 - L) * (LIGHT_OKL - DARK_OKL), so white becomes the gray
# DARK_GRAY and black LIGHT_GRAY. Hue is kept. Chroma is kept up to L 0.65 and muted
# above it, down to a quarter at white, so tinted whites and pastels turn gray while
# marks and accents keep their color; it is reduced further only where sRGB cannot
# show it. Must match darkmode/native/freelab_pixels.c.
DARK_GRAY = 31  # #1f1f1f
LIGHT_GRAY = 219  # #dbdbdb
CHROMA_FULL_BELOW = 0.65
CHROMA_MIN_FACTOR = 0.25
MAX_MAPPED_LIGHTNESS = 0.89  # HLS: below WHITE_L, so selective effects never take a mapped color for FontLab's
# A color whose channels spread this little (max - min, 0-255) comes out pure gray: faint tints
# turn gray, and so do ClearType's colored text edges, which are drawn dark on light and then
# mapped. (Asking Qt for grayscale text smoothing instead made GDI drop smoothing altogether at
# FontLab's small UI sizes.)
NEUTRAL_SPREAD = 60
# Dark mode itself draws nothing at WHITE_L or lighter (mapped colors stop near
# 0.86, the palette above at 0.88), so a pixel at WHITE_L or above is a fixed
# light color FontLab painted. "Selective" effects map only those pixels, which
# makes them safe on any container, and idempotent.
WHITE_L = 0.9
BLACK_L = 0.25

# Widgets that paint fixed light colors in FontLab 7's own code (found live, 2026-11-06).
ISLAND_CLASSES = frozenset((
    "YTrackingFrame",  # the frame of every search field
    "FontPreviewWidget",  # Preview panel
    "GlyphHeaderView",  # list headers (Classes panel)
    "RulerDecorator",  # canvas rulers, when the canvas itself is not an island
    "ToolbarPanel",  # the tool bar
    "YTabBar",  # tab strips
    "FontCellChart",  # font window cells: the font-cell color preference, black glyphs, mark colors
    "CellChart",  # Font Map panel
    "YContinueWidget",  # the zigzag edge where a panel's content continues below
    "YNibShape", "YStrokeShape", "YBrushStrokePreview",  # Brush panel previews
))
ISLAND_NAMES = frozenset((("QListWidget", "historyList"),))  # its selected row is painted light
MARGIN_PARENTS = ("CodeEditor",)  # an unnamed narrow QWidget child is the line-number margin
MARGIN_MAX_WIDTH = 80
# A canvas is a plain QWidget child of these, with this name (None: any name). Only the glyph
# window's QWidget#widget: its other plain children (the text bar) are interface.
CANVAS_RULES = (("YSketchBoard", None), ("GlyphWindow", "widget"))
TITLE_CLASSES = ("YPanel",)  # panels paint their title strip themselves, above their children
TITLE_MAX_HEIGHT = 40
SKIP_CLASS_WORDS = ("ColorPicker", "ColorSource", "OpacityBar", "Eyedropper", "QDesktopScreenWidget")
# Mark-color buttons: the swatch keeps its color; only the white of "no color" turns dark.
# Color pickers keep their look, the white "no color" slot included (the owner preferred that to a half-dark frame).

# Panels (YPanel) paint their whole background a fixed #edeeef, which shows wherever their
# content paints none: beside tabs, behind scroll bars, under translucent labels. Their tab
# widget, which holds all that content, fills itself with the dark palette color instead.
FILL_CLASSES = ("YTabWidget",)  # under a panel or not (a floating panel's tab widget sits elsewhere)
# Containers that draw thin light frames between their children (the dock draws #cacbcc
# lines around every panel). Their own light colors are collected from one render, and an
# effect maps only pixels of exactly those colors: a lightness threshold would also catch
# dark mode's own light text.
KEYED_CLASSES = ("YDock",)
KEY_MIN_L = 0.45
MAX_KEYS = 16
# Inside islands, placeholder text ("Search", "Filter") is faint gray on white; this darker
# gray maps to a readable mid-gray instead of a faint one.
ISLAND_PLACEHOLDER = "#6a6a6a"

# Any other visible widget is rendered once without its children. If at least
# AUTO_WHITE_SHARE of it is near-white, it becomes an island when it paints mostly
# itself (its visible children cover less than AUTO_OWN_SHARE of it, as on a canvas
# with rulers) with dark text or marks on it (at least AUTO_BLACK_SHARE near-black),
# else selective.
AUTO_WHITE_SHARE = 0.25
AUTO_OWN_SHARE = 0.5
AUTO_STRIP_SHARE = 0.03  # a self-painted widget with less near-white than AUTO_WHITE_SHARE but at least this (an editor's white margin): selective
AUTO_BLACK_SHARE = 0.005
AUTO_MIN_ALPHA = 200
AUTO_MIN_AREA = 64

# FontLab's workspace color while dark: #f0f0f0 maps to about #2a2a2a on the canvas island.
WORKSPACE_DARK = "#fff0f0f0"

SLICE_MS = 20  # work per timer slice, so FontLab stays responsive
SWEEP_MS = 750  # how often to look for widgets FontLab created or showed
FULL_SWEEP_EVERY = 40  # every Nth sweep revisits every widget (replaced stylesheets, new icons)
FOCUS_DRAIN_MS = 80  # a window that takes focus is darkened at once, up to this long, before it paints light
MAX_ERRORS = 50
NATIVE_VERSION = 7

ID_PROP = "freelab_id"  # dynamic properties FreeLab sets on widgets, all removed by restore()
SEEN_PROP = "freelab_seen"
QUEUED_PROP = "freelab_queued"  # in the work queue already: never queued twice
WATCHED_PROP = "freelab_watched"  # restyled by FontLab while dark: watched for style changes
STYLE_CHANGE_EVENT = 100  # QEvent::StyleChange
EFFECT_PROP = "freelab_effect"  # set on FreeLab's own graphics effects

CHECKED_PROP = "freelab_checked"  # the size ("WxH") at which the widget was last looked at for fixed light painting
ISLAND_PROP = "freelab_island"  # found to paint light: "island" or "selective"
SHEET_PROP = "freelab_sheet"  # the widget's own stylesheet
DARK_SHEET_PROP = "freelab_sheet_dark"  # what dark mode set instead
PROPS = (ID_PROP, SEEN_PROP, QUEUED_PROP, WATCHED_PROP, CHECKED_PROP, ISLAND_PROP, SHEET_PROP, DARK_SHEET_PROP)

NAMED_COLORS = {
    "white": (255, 255, 255), "black": (0, 0, 0), "whitesmoke": (245, 245, 245),
    "gainsboro": (220, 220, 220), "lightgray": (211, 211, 211), "lightgrey": (211, 211, 211),
    "silver": (192, 192, 192), "darkgray": (169, 169, 169), "darkgrey": (169, 169, 169),
    "gray": (128, 128, 128), "grey": (128, 128, 128), "dimgray": (105, 105, 105), "dimgrey": (105, 105, 105),  # CSS spells both
}
_COLOR_RE = re.compile(
    r"(?<![\w#])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w])"
    r"|(?<![\w-])rgba?\(([^()]*)\)"
    r"|(?<![\w-])(?:" + "|".join(sorted(NAMED_COLORS, key=len, reverse=True)) + r")(?![\w-])",
    re.IGNORECASE)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def state_dir():
    override = os.environ.get("FREELAB_STATE_DIR")
    return override or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FreeLab")


def settings_path():
    return os.path.join(state_dir(), "darkmode.json")


def native_path():
    # Versioned name: FontLab keeps a loaded DLL locked, so a newer one must not need the same file.
    name = "freelab_pixels-v%d.dll" % NATIVE_VERSION
    return os.environ.get("FREELAB_PIXELS_DLL") or os.path.join(state_dir(), "bin", name)


def load_settings():
    try:
        with open(settings_path()) as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def save_settings(data):
    path = settings_path()
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w") as handle:
        json.dump(data, handle)


# ---------------------------------------------------------------------------
# Qt helpers
# ---------------------------------------------------------------------------

def _qt():
    """Return (QApplication, QPalette, QColor, QStyleFactory, QTimer) from PythonQt."""
    from PythonQt.QtCore import QTimer
    from PythonQt.QtGui import QColor, QPalette
    try:
        from PythonQt.QtGui import QApplication, QStyleFactory
    except ImportError:
        from PythonQt.QtWidgets import QApplication, QStyleFactory
    return QApplication, QPalette, QColor, QStyleFactory, QTimer


def _gui(name):
    """One class from PythonQt.QtGui (PythonQt's Qt 5 build puts the widgets there too)."""
    import PythonQt.QtGui as gui
    return getattr(gui, name)


def _core(name):
    import PythonQt.QtCore as core
    return getattr(core, name)


def _state():
    state = getattr(sys, "_freelab_dark_mode", None)
    if state is None:
        state = {}
        sys._freelab_dark_mode = state  # survives FontLab clearing the script namespace
    for key, default in (("on", False), ("saved", None), ("timers", []), ("sweeper", None), ("worker", None),
                         ("sweeps", 0), ("queue", []), ("records", {}), ("next_id", 0), ("icon_cache", {}),
                         ("mapped_keys", set()), ("originals", {}), ("swatches", set()), ("errors", []), ("canvas", True)):
        state.setdefault(key, default)  # older versions of this file kept fewer keys
    return state


def _prop(obj, name):
    """Read a Qt property. PythonQt returns its value (app.styleSheet is a string); PyQt and PySide return a getter."""
    value = getattr(obj, name)
    return value() if callable(value) else value


def _text(exc):
    """An exception as text, whatever its message bytes (Windows may report in the ANSI code page)."""
    try:
        return u"%s" % (exc,)
    except Exception:
        return repr(exc)


SLOW_MS = 100  # with "log": true in darkmode.json, steps slower than this are written to darkmode.log


def _log(message):
    """Append a line to darkmode.log when logging is on (the setting is read once per switch-on)."""
    if not _state().get("log"):
        return
    try:
        with open(os.path.join(state_dir(), "darkmode.log"), "a") as handle:
            handle.write("%s %s\n" % (time.strftime("%H:%M:%S"), message))
    except (IOError, OSError):
        pass


def _note_error(where, exc):
    errors = _state()["errors"]
    errors.append(u"%s: %s" % (where, _text(exc)))
    del errors[:-MAX_ERRORS]


def _class_name(widget):
    return widget.metaObject().className()


def _alive(widget):
    try:
        widget.metaObject()
        return True
    except Exception:  # PythonQt raises once FontLab has deleted the widget
        return False


# QPalette::PlaceholderText arrived in Qt 5.12. FontLab 7 runs Qt 5.14, but its PythonQt
# wrappers predate the role and lack the name; Qt still takes the plain number.
PLACEHOLDER_ROLE_VALUE = 20


def _role(QPalette, name):
    """A palette role by name; PlaceholderText by number when PythonQt lacks the name. None if Qt is too old."""
    role = getattr(QPalette, name, None)
    if role is None and name == "PlaceholderText" and _qt_at_least(5, 12):
        role = PLACEHOLDER_ROLE_VALUE
    return role


def _qt_at_least(major, minor):
    try:
        version = _core("qVersion")()
    except Exception:
        try:
            version = _core("QT_VERSION_STR")
        except Exception:
            return False
    try:
        parts = [int(n) for n in str(version).split(".")[:2]]
    except ValueError:
        return False
    return parts >= [major, minor]


def build_palette(QPalette, QColor, base=None):
    palette = QPalette(base) if base is not None else QPalette()
    for role_name, color, disabled in PALETTE:
        role = _role(QPalette, role_name)
        if role is None:  # PlaceholderText is Qt 5.12 and newer
            continue
        palette.setColor(role, QColor(color))
        if disabled is not None:
            palette.setColor(QPalette.Disabled, role, QColor(disabled))
    return palette


def _strip_ours(sheet):
    sheet = sheet or u""
    index = sheet.find(STYLESHEET_MARK)
    return sheet[:index].rstrip() if index >= 0 else sheet


# ---------------------------------------------------------------------------
# Color mapping
# ---------------------------------------------------------------------------

_SRGB_TO_LINEAR = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (i / 255.0 for i in range(256))]


def _cbrt(x):
    return x ** (1.0 / 3.0) if x > 0 else 0.0


def _linear_to_byte(v):
    """Nearest sRGB byte, nearest measured in linear light (as the native helper does)."""
    if v <= 0.0:
        return 0
    if v >= 1.0:
        return 255
    lo, hi = 0, 255
    while lo < hi:
        mid = (lo + hi) // 2
        if _SRGB_TO_LINEAR[mid] < v:
            lo = mid + 1
        else:
            hi = mid
    if lo > 0 and v - _SRGB_TO_LINEAR[lo - 1] <= _SRGB_TO_LINEAR[lo] - v:
        return lo - 1
    return lo


def oklab(r, g, b):
    """OKLab of an sRGB color (0-255 channels): lightness that follows the eye, hues that stay put."""
    r, g, b = _SRGB_TO_LINEAR[r], _SRGB_TO_LINEAR[g], _SRGB_TO_LINEAR[b]
    lc = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    mc = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    sc = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (0.2104542553 * lc + 0.7936177850 * mc - 0.0040720468 * sc,
            1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc,
            0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc)


def _oklab_to_linear(l, a, b):
    lc = l + 0.3963377774 * a + 0.2158037573 * b
    mc = l - 0.1055613458 * a - 0.0638541728 * b
    sc = l - 0.0894841775 * a - 1.2914855480 * b
    lv, mv, sv = lc * lc * lc, mc * mc * mc, sc * sc * sc
    rgb = (4.0767416621 * lv - 3.3077115913 * mv + 0.2309699292 * sv,
           -1.2684380046 * lv + 2.6097574011 * mv - 0.3413193965 * sv,
           -0.0041960863 * lv - 0.7034186147 * mv + 1.7076147010 * sv)
    return rgb, all(-1e-9 <= c <= 1.0 + 1e-9 for c in rgb)


def _oklab_to_bytes(l, a, b):
    rgb, inside = _oklab_to_linear(l, a, b)
    if not inside:
        lo, hi = 0.0, 1.0
        for _ in range(12):  # the most chroma sRGB can show at this lightness
            mid = (lo + hi) / 2.0
            if _oklab_to_linear(l, a * mid, b * mid)[1]:
                lo = mid
            else:
                hi = mid
        rgb = _oklab_to_linear(l, a * lo, b * lo)[0]
    return tuple(_linear_to_byte(c) for c in rgb)


def _chroma_factor(l):
    if l <= CHROMA_FULL_BELOW:
        return 1.0
    if l >= 1.0:
        return CHROMA_MIN_FACTOR
    return 1.0 - (1.0 - CHROMA_MIN_FACTOR) * (l - CHROMA_FULL_BELOW) / (1.0 - CHROMA_FULL_BELOW)


DARK_OKL = oklab(DARK_GRAY, DARK_GRAY, DARK_GRAY)[0]
LIGHT_OKL = oklab(LIGHT_GRAY, LIGHT_GRAY, LIGHT_GRAY)[0]


def map_rgb(r, g, b, neutral=None):
    """Map a light-theme color to its dark-theme counterpart (0-255 channels)."""
    neutral = NEUTRAL_SPREAD if neutral is None else neutral
    l, a, bb = oklab(r, g, b)
    k = 0.0 if max(r, g, b) - min(r, g, b) <= neutral else _chroma_factor(l)
    l2 = DARK_OKL + (1.0 - l) * (LIGHT_OKL - DARK_OKL)
    for _ in range(20):
        rgb = _oklab_to_bytes(l2, a * k, bb * k)
        if _lightness(*rgb) < MAX_MAPPED_LIGHTNESS:
            break
        l2 -= 0.01
    return rgb

def _hex(rgb):
    return u"#%02x%02x%02x" % rgb


def _channel(text):
    text = text.strip()
    if text.endswith("%"):
        return int(round(float(text[:-1]) * 2.55))
    return int(round(float(text)))


# What a stylesheet color is for decides whether it changes. Text that is already light
# (on a background that is already dark) stays, and so do backgrounds and borders that are
# already dark: a dark bar in light mode is still a dark bar in dark mode.
TEXT_PROPERTIES = ("color", "selection-color")
SURFACE_PREFIXES = ("background", "border", "alternate-background", "selection-background", "gridline", "outline")
KEEP_TEXT_FROM_L = 0.6  # OKLab: text this light or lighter stays
KEEP_SURFACE_BELOW_L = 0.45  # OKLab: surfaces darker than this stay
KEPT_TEXT_CAP = (220, 220, 220)  # kept white text, capped below the selective threshold
_DECLARATION_RE = re.compile(r"([A-Za-z-]+)(\s*:\s*)([^;{}]*)")


def recolor(rgb, prop=None):
    """The dark-mode color for a stylesheet color used by property prop (None: always mapped)."""
    if prop is not None:
        l = oklab(*rgb)[0]
        if prop in TEXT_PROPERTIES and l >= KEEP_TEXT_FROM_L:
            return KEPT_TEXT_CAP if _lightness(*rgb) >= MAX_MAPPED_LIGHTNESS else tuple(rgb)
        if prop.startswith(SURFACE_PREFIXES) and l < KEEP_SURFACE_BELOW_L:
            return tuple(rgb)
    return map_rgb(*rgb)


def _recolor_token(match, prop):
    token = match.group(0)
    try:
        if match.group(1) is not None:  # rgb(...) or rgba(...)
            parts = match.group(1).split(",")
            if len(parts) not in (3, 4):
                return token
            original = tuple(max(0, min(255, _channel(p))) for p in parts[:3])
            rgb = recolor(original, prop)
            if rgb == original:
                return token  # kept as written
            if len(parts) == 3:
                return u"rgb(%d, %d, %d)" % rgb
            return u"rgba(%d, %d, %d, %s)" % (rgb + (parts[3].strip(),))
        if token.startswith("#"):
            digits = token[1:]
            if len(digits) == 3:
                digits = u"".join(c * 2 for c in digits)
            alpha, digits = (digits[:2], digits[2:]) if len(digits) == 8 else (u"", digits)
            original = (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
            rgb = recolor(original, prop)
            return token if rgb == original else u"#" + alpha + _hex(tuple(rgb))[1:]
        original = NAMED_COLORS[token.lower()]
        rgb = recolor(original, prop)
        return token if rgb == original else _hex(tuple(rgb))
    except (ValueError, KeyError):
        return token


def recolor_sheet(sheet):
    """Return a stylesheet with its literal colors turned dark (see recolor)."""
    def declaration(match):
        prop = match.group(1).lower()
        value = _COLOR_RE.sub(lambda color: _recolor_token(color, prop), match.group(3))
        return match.group(1) + match.group(2) + value
    return _DECLARATION_RE.sub(declaration, sheet)


def _native():
    """The native helper's (map, stats) functions, or None when the DLL is missing or unusable."""
    state = _state()
    if state.get("native_path") != native_path():
        state["native_path"] = native_path()
        state["native"] = None
        path = native_path()
        if os.path.isfile(path):
            try:
                import ctypes
                lib = ctypes.CDLL(path)
                if lib.freelab_pixels_version() == NATIVE_VERSION:
                    mapper = lib.freelab_map_lightness
                    mapper.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                       ctypes.c_double, ctypes.c_int]
                    mapper.restype = None
                    stats = lib.freelab_pixel_stats
                    stats.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int, ctypes.c_double, ctypes.c_double,
                                      ctypes.POINTER(ctypes.c_int64)]
                    stats.restype = None
                    collect = lib.freelab_light_colors
                    collect.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_double, ctypes.c_int,
                                        ctypes.POINTER(ctypes.c_uint32), ctypes.c_int64]
                    collect.restype = ctypes.c_int64
                    keyed = lib.freelab_map_keyed
                    keyed.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int64,
                                      ctypes.c_double, ctypes.c_double, ctypes.c_int]
                    keyed.restype = None
                    state["native"] = (mapper, stats, collect, keyed)
                else:
                    _note_error("native", "version mismatch")
            except Exception as exc:
                _note_error("native", exc)
    return state["native"]


def _address(image):
    import ctypes
    return ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))


def map_image(image, min_l=0.0, keys=None, ink_below=-1.0, neutral=None):
    """Return a Format_ARGB32 copy of a QImage with its lightness mapped like map_rgb.

    Only pixels at min_l or lighter are mapped (0 maps all); pixels darker than
    ink_below, when it is above 0, move toward light text by their coverage; with
    neutral, colors whose channels spread that little turn gray (NEUTRAL_SPREAD by
    default, 0 for content that must keep its colors); with keys (0xRRGGBB
    integers), only pixels of exactly those colors. Without the native helper
    (or if its buffer cannot be reached) a full mapping inverts the colors
    instead, which also flips their hue, and a partial one does nothing.
    """
    QImage = _gui("QImage")
    image = image.convertToFormat(QImage.Format_ARGB32)
    native = _native()
    neutral = NEUTRAL_SPREAD if neutral is None else neutral
    if native is not None:
        try:
            count = image.width() * image.height()
            if keys:
                import ctypes
                native[3](_address(image), count, (ctypes.c_uint32 * len(keys))(*keys), len(keys), DARK_OKL, LIGHT_OKL,
                          neutral)
            else:
                native[0](_address(image), count, DARK_OKL, LIGHT_OKL, min_l, ink_below, neutral)
            return image
        except Exception as exc:
            _note_error("map_image", exc)
            _state()["native"] = None
    if min_l <= 0.0 and not keys:
        image.invertPixels()
    return image


def light_colors(image):
    """The distinct opaque colors (0xRRGGBB) at KEY_MIN_L or lighter in a QImage, at most MAX_KEYS; [] without the helper."""
    native = _native()
    if native is None:
        return []
    import ctypes
    image = image.convertToFormat(_gui("QImage").Format_ARGB32)
    keys = (ctypes.c_uint32 * MAX_KEYS)()
    found = native[2](_address(image), image.width() * image.height(), KEY_MIN_L, AUTO_MIN_ALPHA, keys, MAX_KEYS)
    return [int(k) for k in keys[:found]]


def image_stats(image):
    """(opaque, near-white, near-black) pixel counts of a QImage; opaque means alpha >= AUTO_MIN_ALPHA."""
    QImage = _gui("QImage")
    native = _native()
    if native is not None:
        import ctypes
        image = image.convertToFormat(QImage.Format_ARGB32)
        counts = (ctypes.c_int64 * 3)()
        native[1](_address(image), image.width() * image.height(), AUTO_MIN_ALPHA, WHITE_L, BLACK_L, counts)
        return tuple(int(n) for n in counts)
    # Without the helper: a 24 x 24 sample, scaled to the full size.
    Qt, QColor = _core("Qt"), _gui("QColor")
    small = image.convertToFormat(QImage.Format_ARGB32).scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    opaque = white = black = 0
    for y in range(24):
        for x in range(24):
            color = QColor.fromRgba(small.pixel(x, y))
            if color.alpha() < AUTO_MIN_ALPHA:
                continue
            opaque += 1
            light = _lightness(color.red(), color.green(), color.blue())
            white += light >= WHITE_L
            black += light <= BLACK_L
    scale = image.width() * image.height() / 576.0
    return int(opaque * scale), int(white * scale), int(black * scale)


def _lightness(r, g, b):
    return (max(r, g, b) + min(r, g, b)) / 510.0


# ---------------------------------------------------------------------------
# Per-widget records (effects, palettes, icons), so restore() can undo them
# ---------------------------------------------------------------------------

def _record(obj, create=True):
    state = _state()
    key = obj.property(ID_PROP)
    if key is None:
        if not create:
            return None
        state["next_id"] += 1
        key = state["next_id"]
        obj.setProperty(ID_PROP, key)
    key = int(key)
    record = state["records"].get(key)
    if record is None and create:
        record = state["records"][key] = {"obj": obj}
    return record


def _drop_record(obj, record):
    key = obj.property(ID_PROP)
    if key is not None and len(record) == 1:  # only "obj" left
        _state()["records"].pop(int(key), None)


# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

def _darken_sheet(widget):
    sheet = _prop(widget, "styleSheet")
    if not sheet:
        return
    ours = widget.property(DARK_SHEET_PROP)
    if sheet == ours:
        return  # already ours
    if ours is not None:
        _watch(widget)  # FontLab restyles this one while it works (fields while a glyph is edited): catch it at once
    dark = recolor_sheet(sheet)
    widget.setProperty(SHEET_PROP, sheet)
    widget.setProperty(DARK_SHEET_PROP, dark)
    if dark != sheet:
        widget.setStyleSheet(dark)


def _watcher():
    """The one event filter dark mode installs on restyled widgets (a QTimer: PythonQt has no QObject to subclass)."""
    state = _state()
    if state.get("watcher") is None:
        QTimer = _qt()[4]

        class StyleWatcher(QTimer):
            def eventFilter(self, obj, event):
                try:
                    if event.type() == STYLE_CHANGE_EVENT:
                        module = _module()
                        if module is not None:
                            module._on_style_change(obj)
                except Exception as exc:  # an event filter must never raise
                    _note_error("watcher", exc)
                return False

        state["watcher"] = StyleWatcher()
    return state["watcher"]


def _watch(widget):
    if widget.property(WATCHED_PROP) is None:
        widget.setProperty(WATCHED_PROP, True)
        widget.installEventFilter(_watcher())


def _unwatch(widget):
    if widget.property(WATCHED_PROP) is not None:
        widget.removeEventFilter(_watcher())
        widget.setProperty(WATCHED_PROP, None)


def _on_style_change(widget):
    """A watched widget was restyled: darken its new stylesheet before it paints."""
    state = _state()
    if not state["on"] or state.get("restyling"):
        return  # our own setStyleSheet below sends a style change too
    ours = widget.property(DARK_SHEET_PROP)
    if ours is None or _prop(widget, "styleSheet") == ours:
        return
    state["restyling"] = True
    try:
        process(widget)
    finally:
        state["restyling"] = False


def _restore_sheet(widget):
    original = widget.property(SHEET_PROP)
    if original is None:
        return
    if _prop(widget, "styleSheet") == widget.property(DARK_SHEET_PROP):
        widget.setStyleSheet(original)  # else FontLab replaced it since: keep FontLab's
    widget.setProperty(SHEET_PROP, None)
    widget.setProperty(DARK_SHEET_PROP, None)


# ---------------------------------------------------------------------------
# Icons and label images
# ---------------------------------------------------------------------------

def dark_icon(icon, owner=None):
    """A QIcon with every pixmap of `icon` (all sizes, modes, and states) mapped."""
    QIcon, QPixmap = _gui("QIcon"), _gui("QPixmap")
    sizes = list(icon.availableSizes())
    if not sizes:
        size = _prop(owner, "iconSize") if owner is not None and hasattr(owner, "iconSize") else None
        sizes = [size if size is not None else _core("QSize")(16, 16)]
    result = QIcon()
    for size in sizes:
        for mode in (QIcon.Normal, QIcon.Disabled, QIcon.Active, QIcon.Selected):
            for icon_state in (QIcon.Off, QIcon.On):
                pixmap = icon.pixmap(size, mode, icon_state)
                if not pixmap.isNull():
                    result.addPixmap(QPixmap.fromImage(map_image(pixmap.toImage())), mode, icon_state)
    return result


def dark_pixmap(pixmap):
    return _gui("QPixmap").fromImage(map_image(pixmap.toImage()))


SWATCH_CHROMA = 80  # max - min of the channels: clearly colored
SWATCH_SHARE = 0.4  # an icon this colored is a color swatch (mark colors): left as it is


def is_swatch(image):
    """True for an image that is mostly clearly colored: a color swatch, which must keep its color."""
    QImage, QColor, Qt = _gui("QImage"), _gui("QColor"), _core("Qt")
    small = image.convertToFormat(QImage.Format_ARGB32).scaled(12, 12, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    opaque = colored = 0
    for y in range(12):
        for x in range(12):
            color = QColor.fromRgba(small.pixel(x, y))
            if color.alpha() < 128:
                continue
            opaque += 1
            channels = (color.red(), color.green(), color.blue())
            colored += max(channels) - min(channels) >= SWATCH_CHROMA
    return opaque > 0 and colored >= SWATCH_SHARE * opaque


def icon_is_swatch(icon):
    sizes = list(icon.availableSizes())
    size = sizes[0] if sizes else _core("QSize")(16, 16)
    pixmap = icon.pixmap(size)
    return not pixmap.isNull() and is_swatch(pixmap.toImage())


def _swap_icon(obj):
    state = _state()
    icon = _prop(obj, "icon")
    if icon is None or icon.isNull():
        return
    key = icon.cacheKey()
    if key in state["mapped_keys"] or key in state["swatches"]:
        return  # already dark (also covers buttons that follow their action's icon), or a color swatch
    if key not in state["icon_cache"] and icon_is_swatch(icon):
        state["swatches"].add(key)
        return
    new = state["icon_cache"].get(key)
    if new is None:
        new = state["icon_cache"][key] = dark_icon(icon, obj)
        state["mapped_keys"].add(new.cacheKey())
        state["originals"][new.cacheKey()] = icon
    _record(obj)["icon"] = icon  # the latest original, should FontLab have changed it since
    obj.setIcon(new)


MAX_ICON_SIDE = 64  # label images larger than this are pictures (artwork, previews), left as they are


def _swap_pixmap(label):
    state = _state()
    pixmap = _prop(label, "pixmap")
    if pixmap is None or pixmap.isNull() or pixmap.cacheKey() in state["mapped_keys"]:
        return
    if pixmap.width() > MAX_ICON_SIDE or pixmap.height() > MAX_ICON_SIDE:
        return
    new = dark_pixmap(pixmap)
    state["mapped_keys"].add(new.cacheKey())
    _record(label)["pixmap"] = pixmap
    label.setPixmap(new)


def _show_original_icon(widget):
    """In an island, a button that follows a menu action shows the action's mapped icon: put the original back.

    No record is kept: switching off restores the action, and the button follows it again.
    """
    if not widget.inherits("QAbstractButton"):
        return
    icon = _prop(widget, "icon")
    if icon is not None and not icon.isNull() and widget.property(ID_PROP) is None:
        original = _state()["originals"].get(icon.cacheKey())
        if original is not None:
            widget.setIcon(original)


def _darken_icons(widget):
    if widget.inherits("QAbstractButton"):
        _swap_icon(widget)
    elif widget.inherits("QLabel"):
        _swap_pixmap(widget)
    if widget.inherits("QMenu"):
        for action in widget.actions():
            try:
                _swap_icon(action)
            except Exception as exc:
                _note_error("action icon", exc)


def _restore_icons(obj, record):
    if "icon" in record:
        obj.setIcon(record.pop("icon"))
    if "pixmap" in record:
        obj.setPixmap(record.pop("pixmap"))


# ---------------------------------------------------------------------------
# Islands, selective areas, and panel titles
# ---------------------------------------------------------------------------

_EFFECTS = {}
EFFECT_MIN_L = {"island": 0.0, "selective": WHITE_L, "edges": WHITE_L}
# "edges": editors (QScintilla) paint black text and a white margin on a paper that is already
# dark (#1e1e1e, lightness 0.118): map the near-white, move pixels darker than the paper toward
# light text by their coverage (which keeps the text's smoothing), and leave the paper and
# syntax colors.
EDGES_INK_BELOW = 0.115
EFFECT_INK_BELOW = {"edges": EDGES_INK_BELOW}
EDGES_PARENTS = ("QsciScintilla",)  # their viewport (QWidget#qt_scrollarea_viewport) paints the text
# Content keeps every color: anchors, nodes, and marks carry meaning even when muted.
# Interface islands turn faint colors gray (NEUTRAL_SPREAD), which removes ClearType fringes.
CONTENT_CLASSES = ("FontCellChart", "CellChart", "YNibShape", "YStrokeShape", "YBrushStrokePreview", "FontPreviewWidget")


def _effect_classes():
    """{"map": MapEffect, "title": TitleEffect}, defined on first use: they need PythonQt."""
    if not _EFFECTS:
        QGraphicsEffect = _gui("QGraphicsEffect")
        Qt, QPoint, QRect = _core("Qt"), _core("QPoint"), _core("QRect")

        def source(effect):
            """The source pixmap and the painter position of its top-left corner.

            Qt puts the pixmap at an offset: zero for a widget drawn directly,
            not zero when the widget sits inside another effect's widget.
            """
            offset = QPoint()
            pixmap = effect.sourcePixmap(Qt.LogicalCoordinates, offset, QGraphicsEffect.NoPad)
            return pixmap, offset

        def draw_mapped(painter, pixmap, offset, area, min_l, keys=None, ink_below=-1.0, neutral=None):
            """Draw the part of pixmap that lands on `area` (painter coordinates), mapped."""
            area = area.intersected(QRect(offset, pixmap.size()))
            if painter.hasClipping():
                area = area.intersected(painter.clipBoundingRect().toAlignedRect())
            if not area.isEmpty():
                part = pixmap.copy(area.translated(-offset.x(), -offset.y())).toImage()
                painter.drawImage(area.topLeft(), map_image(part, min_l, keys, ink_below, neutral))

        class MapEffect(QGraphicsEffect):
            """Draw the widget with its pixels' lightness mapped (all of them, or only those at freelab_min_l and up)."""

            def draw(self, painter):
                try:
                    pixmap, offset = source(self)
                    draw_mapped(painter, pixmap, offset, QRect(offset, pixmap.size()), self.freelab_min_l,
                                self.freelab_keys, self.freelab_ink_below, self.freelab_neutral)
                except Exception as exc:
                    _note_error("effect", exc)
                    self.drawSource(painter)

        class TitleEffect(QGraphicsEffect):
            """Draw a panel as it is, then its title strip mapped."""

            def draw(self, painter):
                try:
                    pixmap, offset = source(self)
                    painter.drawPixmap(offset, pixmap)
                    height = title_height(self.freelab_widget)
                    if height > 0:
                        draw_mapped(painter, pixmap, offset, QRect(offset.x(), offset.y(), pixmap.width(), height), 0.0)
                except Exception as exc:
                    _note_error("title", exc)
                    self.drawSource(painter)

        _EFFECTS["map"] = MapEffect
        _EFFECTS["title"] = TitleEffect
    return _EFFECTS


def title_height(panel):
    """The panel's title strip: from its top to its first visible child widget."""
    tops = [_prop(child, "y") for child in panel.children()
            if child.isWidgetType() and child.isVisible()]
    top = min(tops) if tops else 0
    return top if 0 < top <= TITLE_MAX_HEIGHT else 0


def widget_kind(widget, canvas=True):
    """"island", "selective", "edges", "keyed", "fill", "title", or None: how dark mode treats this widget beyond its stylesheet."""
    cls = _class_name(widget)
    if cls in ISLAND_CLASSES or (cls, _prop(widget, "objectName")) in ISLAND_NAMES:
        return "island"
    if cls in KEYED_CLASSES:
        return "keyed"

    parent = widget.parentWidget()
    if parent is not None:
        parent_cls = _class_name(parent)
        if cls == "QWidget":
            if parent_cls in EDGES_PARENTS:
                return "edges"
            if parent_cls in MARGIN_PARENTS and _prop(widget, "width") <= MARGIN_MAX_WIDTH:
                return "island"
            if canvas and _is_canvas(widget, parent_cls):
                return "island"
    if cls in FILL_CLASSES:
        return "fill"
    if cls in TITLE_CLASSES:
        return "title"
    found = widget.property(ISLAND_PROP)
    return str(found) if found else None


def _is_canvas(widget, parent_cls):
    return any(parent_cls == rule_parent and name in (None, _prop(widget, "objectName"))
               for rule_parent, name in CANVAS_RULES)


def is_content(widget):
    """Glyph canvases, font cells, previews: their colors (anchors, nodes, marks) are kept."""
    if _class_name(widget) in CONTENT_CLASSES:
        return True
    parent = widget.parentWidget()
    return (_class_name(widget) == "QWidget" and parent is not None
            and _is_canvas(widget, _class_name(parent)))


def _island_ancestor(widget, canvas):
    """The island drawing this widget, if any. An effect draws only within its window, so the search stops there."""
    current = widget
    while not current.isWindow():
        parent = current.parentWidget()
        if parent is None:
            return None
        if widget_kind(parent, canvas) == "island":
            return parent
        current = parent
    return None


def classify_render(width, height, stats, mostly_own):
    """Decide from a widget's own rendering whether it paints fixed light colors.

    stats: (opaque, near-white, near-black) pixel counts. Returns "island" for a
    widget that paints mostly itself, with dark marks on light (text, outlines:
    everything must flip), "selective" for other light areas, else None.
    """
    area = float(width * height)
    opaque, white, black = stats
    if area <= 0:
        return None
    if white < AUTO_WHITE_SHARE * area:
        return "selective" if mostly_own and white >= AUTO_STRIP_SHARE * area else None
    if mostly_own and black >= AUTO_BLACK_SHARE * area:
        return "island"
    return "selective"


def _visible_child_widgets(widget):
    return [c for c in widget.children() if c.isWidgetType() and c.isVisible()]


def own_render(widget):
    """The widget's own painting, children excluded, as a QImage."""
    QPixmap, QColor, QWidget, QRegion = _gui("QPixmap"), _gui("QColor"), _gui("QWidget"), _gui("QRegion")
    pixmap = QPixmap(_prop(widget, "width"), _prop(widget, "height"))
    pixmap.fill(QColor(0, 0, 0, 0))
    widget.render(pixmap, _core("QPoint")(0, 0), QRegion(), QWidget.DrawWindowBackground)
    return pixmap.toImage()


def detect_light(widget):
    """Render the widget alone (no children) and classify its own painting with classify_render."""
    width, height = _prop(widget, "width"), _prop(widget, "height")
    if width * height < AUTO_MIN_AREA or widget.isWindow() or _shows_picture(widget):
        return None
    covered = sum(_prop(c, "width") * _prop(c, "height") for c in _visible_child_widgets(widget))
    mostly_own = covered < AUTO_OWN_SHARE * width * height
    return classify_render(width, height, image_stats(own_render(widget)), mostly_own)


def _shows_picture(widget):
    """A label showing an image larger than an icon (artwork): never treated as painting light."""
    if not widget.inherits("QLabel"):
        return False
    pixmap = _prop(widget, "pixmap")
    return pixmap is not None and not pixmap.isNull() and (
        pixmap.width() > MAX_ICON_SIDE or pixmap.height() > MAX_ICON_SIDE)


def frame_keys(widget):
    """The light colors a keyed container paints itself (its frames)."""
    return light_colors(own_render(widget))


def _ours(widget, record=None):
    """True when the widget's effect is one FreeLab set.

    Told by a Qt property on the effect, not by Python identity: PythonQt may hand
    back another wrapper for the same effect, and taking FreeLab's own effect for a
    foreign one once made dark mode drop its last Python reference to an effect still
    installed, so PythonQt freed it under the widget and FontLab crashed on the next
    repaint.
    """
    current = widget.graphicsEffect()
    if current is None:
        return False
    try:
        return current.property(EFFECT_PROP) is not None
    except Exception:
        return False


def _set_effect(widget, record, kind, keys=None):
    if record.get("kind") == kind and _ours(widget, record):
        return
    if widget.graphicsEffect() is not None and not _ours(widget, record):
        return  # FontLab's own effect: leave it (setGraphicsEffect would delete it)
    classes = _effect_classes()
    effect = classes["title"]() if kind == "title" else classes["map"]()
    effect.freelab_widget = widget
    effect.freelab_min_l = EFFECT_MIN_L.get(kind, 0.0)
    effect.freelab_keys = keys
    effect.freelab_ink_below = EFFECT_INK_BELOW.get(kind, -1.0)
    effect.freelab_neutral = 0 if kind == "island" and is_content(widget) else NEUTRAL_SPREAD
    effect.setProperty(EFFECT_PROP, kind)
    widget.setGraphicsEffect(effect)  # deletes any effect FreeLab set before
    record["effect"], record["kind"] = effect, kind  # PythonQt deletes it if no Python reference is kept


def _clear_effect(widget, record):
    """Remove FreeLab's effect through Qt, which deletes it, and only then drop the Python reference.

    When the widget no longer holds FreeLab's effect, Qt already deleted it (FontLab
    set its own in its place), so dropping the reference is safe.
    """
    if record.get("effect") is not None:
        if _ours(widget, record):
            widget.setGraphicsEffect(None)
        record.pop("effect", None)
    record.pop("kind", None)


def _light_cascade(widget):
    """The original stylesheets of the widget's ancestors, outermost first."""
    sheets = []
    parent = widget.parentWidget()
    while parent is not None:
        original = parent.property(SHEET_PROP)
        if original is None:
            original = _prop(parent, "styleSheet")  # not darkened (yet): still FontLab's
        if original:
            sheets.append(original)
        parent = parent.parentWidget()
    return u"\n".join(reversed(sheets))


def _make_island(widget):
    """Give the widget and everything in it FontLab's light look, then map all of it.

    A widget's own stylesheet beats inherited rules whatever their specificity,
    so prepending the ancestors' original stylesheets to its own undoes the
    dark rules that would otherwise cascade into the island.
    """
    state = _state()
    record = _record(widget)
    if record.get("kind") == "island" and _ours(widget, record):
        expected = widget.property(DARK_SHEET_PROP)
        if expected is None or _prop(widget, "styleSheet") == expected:
            return
        # FontLab replaced the island's stylesheet: take the new one as its own, and prepend the cascade again.
        widget.setProperty(SHEET_PROP, None)
        widget.setProperty(DARK_SHEET_PROP, None)
    if widget.graphicsEffect() is not None and not _ours(widget, record):
        return  # FontLab's own effect: an island needs the widget's only effect slot
    _undo_widget(widget, keep_props=True)
    record = _record(widget)
    if "palette" not in record:
        attribute = _core("Qt").WA_SetPalette
        record["palette"] = _gui("QPalette")(_prop(widget, "palette")) if widget.testAttribute(attribute) else None
    widget.setPalette(_island_palette())  # FontLab's own light palette, before the stylesheet repolishes
    own = _prop(widget, "styleSheet") or u""
    combined = (_light_cascade(widget) + u"\n" + own).strip()
    if combined != own:
        widget.setProperty(SHEET_PROP, own)
        widget.setProperty(DARK_SHEET_PROP, combined)
        widget.setStyleSheet(combined)
    else:
        _note_sheet_as_seen(widget)
    _set_effect(widget, record, "island")
    _enqueue(_descendants(widget), "dark")  # each undoes what dark mode did to it


def _island_palette():
    QPalette = _gui("QPalette")
    palette = QPalette(_state()["saved"]["palette"])
    role = _role(QPalette, "PlaceholderText")
    if role is not None:
        palette.setColor(role, _qt()[2](ISLAND_PLACEHOLDER))
    return palette


def _descendants(widget):
    # Not findChildren(QWidget): under PythonQt it returns an empty list.
    return [w for w in _qt()[0].instance().allWidgets() if widget.isAncestorOf(w)]


def _set_placeholder(widget):
    """Line edits in islands: a darker placeholder, so it maps to a readable gray (FontLab gives them their own palettes)."""
    if not widget.inherits("QLineEdit"):
        return
    QPalette = _gui("QPalette")
    role = _role(QPalette, "PlaceholderText")
    record = _record(widget)
    if role is None or "placeholder" in record:
        return
    attribute = _core("Qt").WA_SetPalette
    palette = QPalette(_prop(widget, "palette"))
    record["placeholder"] = QPalette(palette) if widget.testAttribute(attribute) else None
    palette.setColor(role, _qt()[2](ISLAND_PLACEHOLDER))
    widget.setPalette(palette)


def _undo_widget(widget, keep_props=False, keep_placeholder=False):
    """Take back everything dark mode did to one widget."""
    _restore_sheet(widget)
    record = _record(widget, create=False)
    if record is not None:
        _clear_effect(widget, record)
        if "placeholder" in record and not keep_placeholder:
            palette = record.pop("placeholder")
            widget.setPalette(palette if palette is not None else _gui("QPalette")())
        if "palette" in record:
            palette = record.pop("palette")
            widget.setPalette(palette if palette is not None else _gui("QPalette")())  # empty: inherit again
        if "autofill" in record:
            widget.setAutoFillBackground(record.pop("autofill"))
        _restore_icons(widget, record)
        _drop_record(widget, record)
    if widget.inherits("QMenu"):
        for action in widget.actions():
            action_record = _record(action, create=False)
            if action_record is not None:
                _restore_icons(action, action_record)
                _drop_record(action, action_record)
                action.setProperty(ID_PROP, None)
    if not keep_props:
        _unwatch(widget)
        for name in PROPS:
            widget.setProperty(name, None)


# ---------------------------------------------------------------------------
# Windows title bars
# ---------------------------------------------------------------------------

DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 10 20H1 and later; 19 before that
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE, NOMOVE, NOZORDER, NOACTIVATE, FRAMECHANGED


def _process_windows():
    """Handles of this process's visible top-level windows (PythonQt cannot return winId())."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    pid = os.getpid()
    found = []

    def collect(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(int(hwnd))
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(collect)
    user32.EnumWindows(callback, 0)
    return found


def _set_title_bar(hwnd, dark):
    import ctypes
    handle = ctypes.c_void_p(hwnd)
    value = ctypes.c_int(1 if dark else 0)
    dwm = ctypes.windll.dwmapi
    for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE - 1):
        if dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
            break
    ctypes.windll.user32.SetWindowPos(handle, None, 0, 0, 0, 0, SWP_FLAGS)  # redraw the frame now


def _is_window(hwnd):
    import ctypes
    return bool(ctypes.windll.user32.IsWindow(ctypes.c_void_p(hwnd)))


def dark_title_bars(dark):
    """Ask Windows to draw FontLab's visible title bars dark (each window once), or light again.

    Once per window: every call also makes Windows recompute the window's frame,
    and repeating that on a dialog that is still opening kept it relaying itself
    out without end. Handles of destroyed windows are forgotten, so a new window
    that reuses one is darkened too.
    """
    if sys.platform != "win32":
        return
    state = _state()
    done = state.setdefault("dark_windows", set())
    try:
        for hwnd in [h for h in done if not _is_window(h)]:
            done.discard(hwnd)
        if dark:
            for hwnd in _process_windows():
                if hwnd not in done:
                    done.add(hwnd)
                    _set_title_bar(hwnd, True)
        else:
            for hwnd in list(done):
                _set_title_bar(hwnd, False)
            done.clear()
    except Exception as exc:
        _note_error("title bar", exc)


# ---------------------------------------------------------------------------
# Work queue
# ---------------------------------------------------------------------------

def process(widget):
    """Darken one widget, or hand it to the island that contains it.

    Its unprocessed ancestors go first, outermost first: until their
    stylesheets are dark, the widget inherits light rules and would look like
    one that paints light itself.
    """
    state = _state()
    pending = []
    parent = widget.parentWidget()
    while parent is not None and parent.property(SEEN_PROP) is None:
        pending.append(parent)
        parent = parent.parentWidget()
    for ancestor in reversed(pending):
        process(ancestor)
    widget.setProperty(SEEN_PROP, True)
    visible_unchecked = widget.isVisible() and _unchecked(widget)
    if visible_unchecked:
        widget.setProperty(CHECKED_PROP, _size_key(widget))  # sweeps need not queue it again at this size
    name = _class_name(widget)
    if any(word in name for word in SKIP_CLASS_WORDS):
        _note_sheet_as_seen(widget)
        return
    canvas = state["canvas"]
    if _island_ancestor(widget, canvas) is not None:
        _undo_widget(widget, keep_props=True, keep_placeholder=True)  # the island maps it as drawn in light mode
        _set_placeholder(widget)
        _show_original_icon(widget)
        _note_sheet_as_seen(widget)
        return
    kind = widget_kind(widget, canvas)
    if kind == "island":
        _make_island(widget)
        return
    _darken_sheet(widget)
    if kind is None and visible_unchecked:
        found = detect_light(widget)  # before its icons are mapped light
        if found:
            widget.setProperty(ISLAND_PROP, found)
            kind = found
            if found == "island":
                _make_island(widget)
                return
    _darken_icons(widget)
    if kind in ("selective", "edges", "title"):
        _set_effect(widget, _record(widget), kind)
    elif kind == "keyed" and widget.isVisible():
        record = _record(widget)
        if record.get("kind") != "keyed":
            keys = frame_keys(widget)
            if keys:
                _set_effect(widget, record, "keyed", keys)
    elif kind == "fill":
        record = _record(widget)
        if "autofill" not in record:
            record["autofill"] = bool(_prop(widget, "autoFillBackground"))
            widget.setAutoFillBackground(True)


def _enqueue(widgets, action):
    """Queue (action, widget) pairs, each widget once; the queue is a stack, so the last ones queued run first."""
    queue = _state()["queue"]
    for widget in widgets:
        if widget.property(QUEUED_PROP) != action:
            widget.setProperty(QUEUED_PROP, action)
            queue.append((action, widget))
    _start_worker()


def _work():
    state = _state()
    if state.get("busy"):
        _log("re-entered work (queue %d)" % len(state["queue"]))
        return  # re-entered from inside processing (a Qt signal or paint): the outer loop carries on
    state["busy"] = True
    started = time.time()
    try:
        _work_slice(state)
    finally:
        state["busy"] = False
        elapsed = (time.time() - started) * 1000
        if elapsed > SLOW_MS:
            _log("slow slice %.0f ms, queue now %d" % (elapsed, len(state["queue"])))


def _work_slice(state):
    deadline = time.time() + SLICE_MS / 1000.0
    queue = state["queue"]
    while queue and time.time() < deadline:
        action, widget = queue.pop()
        if not _alive(widget):
            continue
        if widget.property(QUEUED_PROP) != action:
            continue  # superseded by a later entry for the other action
        widget.setProperty(QUEUED_PROP, None)
        try:
            if action == "dark":
                if state["on"]:
                    process(widget)
            elif not state["on"]:  # left over from switching off, after switching on again: skip
                _undo_widget(widget)
        except Exception as exc:  # one odd widget must not stop the rest
            _note_error(u"%s %s" % (action, _class_name(widget)), exc)
    if not queue:
        _stop_timer(state, "worker")


def run_queue():
    """Finish the queue now (tests and diagnostics)."""
    while _state()["queue"]:
        _work()


def _sweep():
    """Timer: queue widgets FontLab created or showed since the last sweep."""
    state = _state()
    if not state["on"] or state.get("busy"):
        return
    app = _qt()[0].instance()
    if app is None:
        return
    state["sweeps"] += 1
    full = state["sweeps"] % FULL_SWEEP_EVERY == 0
    todo = [w for w in app.allWidgets()
            if full or w.property(SEEN_PROP) is None or (w.isVisible() and (_unchecked(w) or _restyled(w)))]
    if todo:
        _enqueue(todo, "dark")
        if len(todo) > 200 and not full:
            _log("sweep %d queued %d (queue %d)" % (state["sweeps"], len(todo), len(state["queue"])))
    dark_title_bars(True)  # windows opened since the last sweep
    for key, record in list(state["records"].items()):
        if not _alive(record["obj"]):
            del state["records"][key]


def _module():
    """The current version of this module. FontLab may drop modules from sys.modules between script
    runs, and a Python 2 module that is no longer referenced has its globals set to None: every
    timer and effect would then fail. The state keeps a reference, refreshed by every apply."""
    return sys.modules.get(MODULE_NAME) or _state().get("module")


def _focus_hook(*_args):
    """QApplication.focusChanged: a new window or tab usually takes focus as it opens."""
    module = _module()
    if module is not None:
        module._on_focus()


def _on_focus():
    state = _state()
    if not state["on"] or state.get("busy"):
        return
    try:
        _sweep()
        deadline = time.time() + FOCUS_DRAIN_MS / 1000.0
        while state["queue"] and time.time() < deadline:
            _work()
    except Exception as exc:  # a Qt signal handler must not raise
        _note_error("focus", exc)


def _hook_focus(app):
    state = _state()
    if state.get("focus_hooked"):
        return
    try:
        if app.connect("focusChanged(QWidget*,QWidget*)", _focus_hook) is not False:
            state["focus_hooked"] = True
    except Exception as exc:
        _note_error("focus hook", exc)


def _size_key(widget):
    return u"%dx%d" % (_prop(widget, "width"), _prop(widget, "height"))


def _unchecked(widget):
    """Not looked at yet at its current size: a panel classified while it was still opening,
    at a placeholder size, gets a second look once it has its real one."""
    return widget.property(CHECKED_PROP) != _size_key(widget)


def _restyled(widget):
    """True when FontLab replaced the stylesheet dark mode set, or gave a widget its first one
    (cheap enough for every sweep)."""
    ours = widget.property(DARK_SHEET_PROP)
    sheet = _prop(widget, "styleSheet")
    if ours is None:
        return bool(sheet)
    return sheet != ours


def _note_sheet_as_seen(widget):
    """For widgets whose stylesheet dark mode leaves as it is (inside an island, skipped): remember
    it, so sweeps take only a later change for a restyle."""
    sheet = _prop(widget, "styleSheet")
    if sheet:
        widget.setProperty(DARK_SHEET_PROP, sheet)


def _connect_timeout(timer, callback):
    try:
        connected = timer.connect("timeout()", callback) is not False
    except Exception:
        connected = False
    if not connected:
        timer.timeout.connect(callback)


def _start_timer(state, key, interval, callback):
    if state[key] is not None:
        return
    timer = _qt()[4]()
    timer.setInterval(interval)
    _connect_timeout(timer, callback)
    timer.start()
    state[key] = timer


def _stop_timer(state, key):
    if state[key] is not None:
        try:
            state[key].stop()
        except Exception:
            pass
        state[key] = None


def _start_worker():
    _start_timer(_state(), "worker", 0, _work)


# ---------------------------------------------------------------------------
# FontLab preferences
# ---------------------------------------------------------------------------

def _preferences():
    try:
        import fontlab
        return fontlab.flPreferences()
    except Exception:  # outside FontLab
        return None


def _argb(color):
    QColor = _qt()[2]
    return color.name(QColor.HexArgb).lower()


def _darken_preferences():
    prefs = _preferences()
    if prefs is None or not _state()["canvas"]:
        return
    current = _argb(prefs.colorWorkspace)
    if current != WORKSPACE_DARK:
        settings = load_settings()
        # Keep an earlier original: after a crash with dark mode on, the current color may not be the user's.
        if not settings.get("saved_workspace"):
            settings["saved_workspace"] = current
            save_settings(settings)
        prefs.colorWorkspace = _qt()[2](WORKSPACE_DARK)


def _restore_preferences():
    settings = load_settings()
    saved = settings.pop("saved_workspace", None)
    prefs = _preferences()
    if saved is None or prefs is None:
        return
    if _argb(prefs.colorWorkspace) == WORKSPACE_DARK:  # else the user picked another color since: keep it
        prefs.colorWorkspace = _qt()[2](saved)
    save_settings(settings)


# ---------------------------------------------------------------------------
# On and off
# ---------------------------------------------------------------------------

def _app_is_dark(app, QPalette):
    return app.palette().color(QPalette.Window).name() == PALETTE[0][1]


def apply_dark():
    """Switch the interface to dark. Saves what it changes the first time."""
    QApplication, QPalette, QColor, QStyleFactory, QTimer = _qt()
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("No Qt application is running.")
    state = _state()
    if state["saved"] is None:
        state["saved"] = {
            # Under widget stylesheets app.style() is Qt's QStyleSheetStyle wrapper, whose name is empty.
            "style": _prop(app.style(), "objectName") or ORIGINAL_STYLE_FALLBACK,
            "palette": QPalette(app.palette()),
            "font": _gui("QFont")(app.font()),
        }
    state["saved"].setdefault("font", _gui("QFont")(app.font()))  # a state kept from before fonts were saved
    settings = load_settings()
    state["canvas"] = bool(settings.get("canvas", True))
    state["log"] = bool(settings.get("log", False))
    if not (state["on"] and _app_is_dark(app, QPalette)):  # a style change repolishes every widget: only when needed
        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            app.setStyle(fusion)
        app.setPalette(build_palette(QPalette, QColor))
        app.setFont(state["saved"]["font"])  # undoes the grayscale text smoothing an earlier version set
    state["on"] = True
    state["module"] = sys.modules.get(MODULE_NAME) or state.get("module")  # see _module()
    # Every version of this file loaded so far stays referenced: Qt still calls into older ones
    # (the focus hook, the style watcher, effects made before a reload), and a freed Python 2
    # module has its globals set to None, which broke them all ('NoneType' object is not callable).
    versions = state.setdefault("modules", [])
    if state["module"] is not None and all(m is not state["module"] for m in versions):
        versions.append(state["module"])
    state["queue"][:] = [item for item in state["queue"] if item[0] == "dark"]  # switching off may not have finished
    _darken_preferences()
    dark_title_bars(True)
    widgets = list(app.allWidgets())
    _enqueue([w for w in widgets if not w.isVisible()], "dark")
    _enqueue([w for w in widgets if w.isVisible()], "dark")  # visible ones first
    _start_timer(state, "sweeper", SWEEP_MS, _sweep)
    _hook_focus(app)  # stays connected; it does nothing while dark mode is off


def restore():
    """Put back FontLab's style, palette, stylesheets, icons, and workspace color.

    The application stylesheet is FontLab's apart from FreeLab's block, and is
    left as it is now, including any change FontLab made to it meanwhile.
    """
    QApplication, QPalette, QColor, QStyleFactory, QTimer = _qt()
    app = QApplication.instance()
    state = _state()
    _cancel_timers(state)
    _stop_timer(state, "sweeper")
    _stop_timer(state, "worker")
    del state["queue"][:]
    was_on, state["on"] = state["on"], False
    saved = state["saved"]
    if app is None or saved is None:
        return
    for record in list(state["records"].values()):  # effects, palettes, icons: quick, all at once
        obj = record["obj"]
        if not _alive(obj):
            continue
        try:
            if obj.isWidgetType():
                _undo_widget(obj)
            else:
                _restore_icons(obj, record)
                obj.setProperty(ID_PROP, None)
        except Exception as exc:
            _note_error("restore", exc)
    state["records"].clear()
    state["icon_cache"].clear()
    state["mapped_keys"].clear()
    state["originals"].clear()
    state["swatches"].clear()
    if was_on:
        _restore_preferences()
    dark_title_bars(False)
    style = QStyleFactory.create(saved["style"] or ORIGINAL_STYLE_FALLBACK)
    if style is not None:
        app.setStyle(style)
    app.setPalette(saved["palette"])
    if saved.get("font") is not None:
        app.setFont(saved["font"])
    sheet = _prop(app, "styleSheet") or u""
    if STYLESHEET_MARK in sheet:  # left by FreeLab 0.1, which also styled menus through the application
        app.setStyleSheet(_strip_ours(sheet))
    # Stylesheets, at once: switching off is rare and asked for, and a half-restored
    # interface (should anything interrupt the slices) is worse than a short freeze.
    _enqueue(list(app.allWidgets()), "light")
    run_queue()


def status():
    """A summary for diagnostics."""
    state = _state()
    kinds = [r.get("kind") for r in state["records"].values()]
    return {
        "version": VERSION, "on": state["on"], "queue": len(state["queue"]), "records": len(state["records"]),
        "islands": kinds.count("island"), "titles": kinds.count("title"), "native": _native() is not None,
        "canvas": state["canvas"], "errors": list(state["errors"][-10:]),
    }


def _cancel_timers(state):
    for timer in state["timers"]:
        try:
            timer.stop()
        except Exception:
            pass
    state["timers"] = []


def _reapply_if_on():
    state = _state()
    if state["on"]:
        try:
            apply_dark()
        except Exception as exc:
            print("FreeLab dark mode could not reapply: %s" % (_text(exc),))


def schedule_reapply():
    """Apply again shortly after startup, in case FontLab sets its own style after this script."""
    QTimer = _qt()[4]
    state = _state()
    _cancel_timers(state)
    for delay in REAPPLY_DELAYS_MS:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(delay)
        _connect_timeout(timer, _reapply_if_on)
        timer.start()
        state["timers"].append(timer)  # kept referenced until they fire


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def startup():
    """Called by FontLab's startup script: apply dark mode if it was left on."""
    if load_settings().get("enabled"):
        apply_dark()
        schedule_reapply()


def toggle():
    if _state()["on"]:
        restore()
        enabled = False
        message = "FreeLab dark mode is off."
    else:
        apply_dark()
        enabled = True
        message = "FreeLab dark mode is on. Run this script again to switch it off."
    settings = load_settings()  # after apply/restore, which keep the saved workspace color here
    settings["enabled"] = enabled
    save_settings(settings)
    print(message)
    return enabled


def load_as_module(path):
    """Load this file as a real module, so its globals are not FontLab's script namespace."""
    if sys.version_info[0] == 2:
        # open() takes a unicode path through the wide Windows API; imp.load_source does not.
        import imp
        module = imp.new_module(MODULE_NAME)
        module.__file__ = path
        sys.modules[MODULE_NAME] = module
        with open(path, "rb") as handle:
            source = handle.read()
        exec(compile(source, MODULE_NAME + ".py", "exec", 0, True), module.__dict__)
    else:
        import importlib.util
        spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[MODULE_NAME] = module
        spec.loader.exec_module(module)
    sys.modules[MODULE_NAME] = module
    return module


def _run_as_script():
    if __name__ == MODULE_NAME:
        return None  # imported: the importer decides
    path = globals().get("__file__")
    if path and os.path.isfile(path):
        return load_as_module(path).toggle()
    return toggle()


if not os.environ.get("FREELAB_NO_AUTOSTART"):
    _run_as_script()
