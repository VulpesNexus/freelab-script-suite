#FLM: Toggle Dark Mode
# -*- coding: utf-8 -*-
"""FreeLab dark mode for FontLab's interface.

Run this file from FontLab's Scripts menu to switch dark mode on or off; the
choice is remembered. With the FreeLab startup hook installed
(tools/install-fontlab.ps1), FontLab applies the remembered choice at launch.

FontLab 7 has no theme: it colors its interface in three main ways, and dark
mode handles each (docs/DARKMODE.md lists every case).

1. The application palette and style: switched to Fusion with a dark palette.
2. About a thousand widgets carry their own stylesheet with fixed light
   colors, which win over the palette. Each is rewritten with its colors
   mapped to dark mode's grays (colored ones keep their hue).
3. Some widgets paint fixed colors in FontLab's own code: the glyph canvas,
   rulers, tab bars, search fields, previews, list rows, and more. Those that
   paint mostly light become "islands": they keep their original light look,
   and a graphics effect maps everything they draw, so black outlines turn
   light while mark colors keep their hue. Lists, text views, and widgets with
   dark text on the dark interface get an "ink" effect, which maps only their
   light surfaces and dark text. Known ones are listed below; others are found
   by rendering them once.

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

VERSION = "0.3.0"
MODULE_NAME = "freelab_dark_mode"
REAPPLY_DELAYS_MS = (0, 1500, 5000)  # FontLab may restyle itself after the startup script runs
ORIGINAL_STYLE_FALLBACK = "windowsvista"  # Qt's default on Windows; the only style plugin FontLab 7 ships

# Dark palette: (role, color for all groups, color for the Disabled group or None).
PALETTE_DARK = (
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
    ("Light", "#505054", "#00000000"),  # disabled: Fusion etches disabled menu text with it, a light shadow
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
# The medium shade: the same, in lighter grays.
PALETTE_MEDIUM = (
    ("Window", "#44444a", None),
    ("WindowText", "#e0e0e0", "#9a9a9a"),
    ("Base", "#3c3c40", "#424246"),
    ("AlternateBase", "#424246", None),
    ("ToolTipBase", "#56565c", None),
    ("ToolTipText", "#e0e0e0", None),
    ("Text", "#e0e0e0", "#9a9a9a"),
    ("Button", "#505056", "#4a4a50"),
    ("ButtonText", "#e0e0e0", "#9a9a9a"),
    ("BrightText", "#ff8080", None),
    ("Light", "#6a6a72", "#00000000"),
    ("Midlight", "#5c5c63", None),
    ("Mid", "#3e3e43", None),
    ("Dark", "#303034", None),
    ("Shadow", "#202023", None),
    ("Highlight", "#4a7cc4", "#505056"),
    ("HighlightedText", "#e0e0e0", "#b0b0b0"),
    ("Link", "#8ab8ff", None),
    ("LinkVisited", "#c4a0ff", None),
    ("PlaceholderText", "#a0a0a0", None),
)
PALETTE = PALETTE_DARK
# Shades: (palette, the gray white maps to, the gray black maps to).
SHADES = {"dark": (PALETTE_DARK, 31, 219), "medium": (PALETTE_MEDIUM, 60, 226)}

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
DARK_GRAY = 31  # #1f1f1f (the "dark" shade; "medium" changes these, see SHADES)
LIGHT_GRAY = 219  # #dbdbdb
# An editor's margin (white, at its left) is mapped whole, its numbers to this gray, like the
# Features panel's: MARGIN_SHARE of the way from DARK_GRAY to LIGHT_GRAY.
MARGIN_SHARE = 0.55
MARGIN_GRAY = int(DARK_GRAY + MARGIN_SHARE * (LIGHT_GRAY - DARK_GRAY))
CHROMA_FULL_BELOW = 0.65
CHROMA_MIN_FACTOR = 0.25
MAX_MAPPED_LIGHTNESS = 0.89  # HLS: below WHITE_L, so the ink mapping never takes a mapped color for FontLab's
# Colors whose channels spread this little (max - min, 0-255) are mapped linearly: their mean is
# inverted between the two grays, and keep_tint (0 to 1) of each channel's distance from the
# mean is kept. Text smoothing lives in these colors (blends of text and background, ClearType's
# colored edges), and only a linear mapping keeps a blend a blend; the perceptual mapping moved
# edge pixels to the wrong brightness. The interface keeps no tint (gray, as the owner prefers,
# and no ClearType fringes); content keeps it all (muted anchors, nodes, marks).
# (Asking Qt for grayscale text smoothing instead made GDI drop smoothing altogether at FontLab's
# small UI sizes.)
LINEAR_SPREAD = 110
MAX_LINEAR_CHANNEL = 235.0
KEEP_TINT_CONTENT = 1.0
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
    "CellChartScrollBar",  # the cell charts' own light scroll bars
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
# Left as they are: color swatches (the popup that holds them is darkened), color sources, and
# the font window's mark slots (QToolButton#flagRed and the like, colored by their stylesheets),
# which must show the real mark colors.
SKIP_CLASSES = ("ColorPickerItem", "ColorPickerButton", "QtColorPicker", "QDesktopScreenWidget",
                "YHueBar", "YSaturationBar", "YColorBar", "YColorPreview", "YColorRing", "ColorMap",  # color controls (audit of FontLab 7.2's classes)
                "YSimpleSlider")  # drawn from the palette: its white knob is right on dark already
SKIP_CLASS_WORDS = ("ColorSource", "OpacityBar", "Eyedropper")
SWATCH_NAME_PREFIXES = ("flag",)
# The Color panel's channel sliders draw color gradients (their stylesheets): color controls too.
# Under the ink effect, partial repaints left blocky patches in the red and blue tracks.
COLOR_SLIDER_PANELS = ("ColorPanel",)
# Color pickers keep their swatch (the white "no color" slot included), but their button frame,
# drawn white by the style, gets this thin dark border instead (appended to their own stylesheet).
PICKER_FRAME = u"\nQtColorPicker { border: 1px solid #55555a; border-radius: 2px; background: transparent; }"
# A picker draws its swatch at the left, about as wide as it is tall, inside a light frame of its own,
# and a dark arrow after this gap: the "picker" effect maps all of it but the swatch's inside (the
# frame on the swatch's side stayed white).
PICKER_SWATCH_GAP = 3  # the swatch's side ends this far past a square as tall as the picker
PICKER_KEEP_CHROMA = 48  # around the swatch's inside, pixels this colored keep their color
# Color pickers and mark-color buttons keep their look, the white "no color" slot included (the owner
# preferred that to a half-dark frame).

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
# else ink.
AUTO_WHITE_SHARE = 0.25
AUTO_OWN_SHARE = 0.5
AUTO_STRIP_SHARE = 0.03  # a self-painted widget with less near-white than AUTO_WHITE_SHARE but at least this (an editor's white margin): ink
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
NATIVE_VERSION = 104

ID_PROP = "freelab_id"  # dynamic properties FreeLab sets on widgets, all removed by restore()
SEEN_PROP = "freelab_seen"
QUEUED_PROP = "freelab_queued"  # in the work queue already: never queued twice
WATCHED_PROP = "freelab_watched"  # restyled by FontLab while dark: watched for style changes
STYLE_CHANGE_EVENT = 100  # QEvent::StyleChange
EFFECT_PROP = "freelab_effect"  # set on FreeLab's own graphics effects

CHECKED_PROP = "freelab_checked"  # the size ("WxH") at which the widget was last looked at for fixed light painting
ISLAND_PROP = "freelab_island"  # found by rendering: "island" or "ink"
SHEET_PROP = "freelab_sheet"  # the widget's own stylesheet
DARK_SHEET_PROP = "freelab_sheet_dark"  # what dark mode set instead
MENU_HOOK_PROP = "freelab_menu_hooked"  # aboutToShow connected (kept: the hook stays, idle while off)
HOOKED_PROP = "freelabHooked"  # an island the native engine's hooks map, rather than an effect
NATIVE_INK_PROP = "freelabNativeInk"  # a list whose dark pens the native engine maps, rather than the ink effect
# Lists whose rows Qt draws, in colors FontLab puts in their data: under the native engine, their
# viewports' dark pens are mapped as they are set (in FontLab's program and in Qt5Widgets), with no
# effect. Only lists whose delegates leave the drawing to Qt (Metrics' sets colors only); a delegate
# of FontLab's that paints its rows (FontAudit's badges, the Elements tree) keeps the ink effect.
NATIVE_INK_DELEGATES = ("QStyledItemDelegate", "QItemDelegate", "MetricsDataDelegate")
# Islands Qt draws (from their stylesheet), out of the hooks' reach: the script engine's island
# under either engine (the continue edge's white line stayed white).
SCRIPT_ISLAND_CLASSES = ("YContinueWidget",)
# FontLab's classes built on widgets Qt draws: inside a hooked island they are processed as any
# widget (a search field's line edit keeps its placeholder's ink), not hooked.
QT_DRAWN_BASES = ("QLineEdit", "QAbstractButton", "QAbstractScrollArea", "QAbstractSpinBox", "QComboBox",
                  "QLabel", "QAbstractSlider", "QTabBar")
PROPS = (ID_PROP, SEEN_PROP, QUEUED_PROP, WATCHED_PROP, CHECKED_PROP, ISLAND_PROP, SHEET_PROP, DARK_SHEET_PROP, HOOKED_PROP, NATIVE_INK_PROP)

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
    # Written beside it, then moved over it: a write cut short (FontLab killed, a full disk) must not
    # leave a truncated file, which reads as no settings and would lose the saved workspace color.
    temp = path + ".tmp"
    with open(temp, "w") as handle:
        json.dump(data, handle)
    try:
        os.replace(temp, path)  # Python 3
    except AttributeError:  # Python 2.7 cannot rename over a file on Windows
        if os.path.exists(path):
            os.remove(path)
        os.rename(temp, path)


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
MARGIN_OKL = oklab(MARGIN_GRAY, MARGIN_GRAY, MARGIN_GRAY)[0]


def _palette_okl(role_name):
    color = dict((role, value) for role, value, _disabled in PALETTE)[role_name].lstrip("#")
    return oklab(int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))[0]


# What lies beneath a widget that paints no background of its own: the palette's window color.
# Dark ink is judged against it (see freelab_pixels.c).
BACKGROUND_OKL = _palette_okl("Window")


def set_shade(shade):
    """Switch the mapping and the palette to a shade ("dark" or "medium"); returns the shade used."""
    global PALETTE, DARK_GRAY, LIGHT_GRAY, MARGIN_GRAY, DARK_OKL, LIGHT_OKL, MARGIN_OKL, BACKGROUND_OKL
    if shade not in SHADES:
        shade = "dark"
    PALETTE, DARK_GRAY, LIGHT_GRAY = SHADES[shade]
    MARGIN_GRAY = int(DARK_GRAY + MARGIN_SHARE * (LIGHT_GRAY - DARK_GRAY))
    DARK_OKL = oklab(DARK_GRAY, DARK_GRAY, DARK_GRAY)[0]
    LIGHT_OKL = oklab(LIGHT_GRAY, LIGHT_GRAY, LIGHT_GRAY)[0]
    MARGIN_OKL = oklab(MARGIN_GRAY, MARGIN_GRAY, MARGIN_GRAY)[0]
    BACKGROUND_OKL = _palette_okl("Window")
    return shade


def _gray_byte(l):
    """The sRGB gray whose OKLab lightness is l (for a gray, L is the cube root of linear light)."""
    return float(_linear_to_byte(l * l * l))


def map_rgb(r, g, b, keep_tint=0.0, dark_l=None, light_l=None):
    """Map a light-theme color to its dark-theme counterpart (0-255 channels). Must match the native helper."""
    dark_l = DARK_OKL if dark_l is None else dark_l
    light_l = LIGHT_OKL if light_l is None else light_l
    if max(r, g, b) - min(r, g, b) <= LINEAR_SPREAD:
        dark, light = _gray_byte(dark_l), _gray_byte(light_l)
        mean = (r + g + b) / 3.0
        base = light - mean * (light - dark) / 255.0
        return tuple(int(min(MAX_LINEAR_CHANNEL, max(0.0, base + (c - mean) * keep_tint)) + 0.5) for c in (r, g, b))
    l, a, bb = oklab(r, g, b)
    k = _chroma_factor(l)
    l2 = dark_l + (1.0 - l) * (light_l - dark_l)
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
KEPT_TEXT_CAP = (220, 220, 220)  # kept white text, capped below WHITE_L
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
                    mapper.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_double, ctypes.c_double,
                                       ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
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
                    keyed.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.POINTER(ctypes.c_uint32),
                                      ctypes.c_int64, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                      ctypes.c_uint32]
                    keyed.restype = None
                    anchors = lib.freelab_map_anchors
                    anchors.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int, ctypes.c_double,
                                        ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int]
                    anchors.restype = ctypes.c_int64
                    defringe = getattr(lib, "freelab_defringe", None)  # optional: a build without it still maps
                    if defringe is not None:
                        defringe.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int]
                        defringe.restype = None
                    state["native"] = (mapper, stats, collect, keyed, anchors, defringe)
                else:
                    _note_error("native", "version mismatch")
            except Exception as exc:
                _note_error("native", exc)
    return state["native"]


def _address(image):
    import ctypes
    return ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))


ANCHOR_MODES = {"ink": 0, "all": 1, "relight": 2, "icon": 3, "subpixel": 4, "syntax": 5}


def map_image(image, min_l=0.0, keys=None, ink_below=-1.0, keep_tint=0.0, light_l=None, edge_neutral=0.0, edge_target=0,
              anchors=None, dark_l=None):
    """Return a Format_ARGB32 copy of a QImage with its lightness mapped like map_rgb.

    With anchors ("all" or "ink"), the native helper's anchor blends (see
    darkmode/native/freelab_pixels.c): the image's few flat colors are mapped
    (all of them, or on the dark interface only white and light surfaces and dark
    ink), and smoothing between two of them becomes the same blend of the mapped
    colors. Otherwise, pixel by pixel: only pixels at min_l or lighter are mapped
    (0 maps all); pixels darker than ink_below, when it is above 0, move toward
    light text by their coverage; with keys (0xRRGGBB integers), only pixels of
    exactly those colors. keep_tint is how much of a low-color pixel's tint
    survives (0 for the interface, 1 for content); light_l and dark_l override the
    two ends (gray numbers in an editor's margin; an editor turned light again).
    Without the native helper (or if its buffer cannot be reached) a full mapping
    inverts the colors instead, which also flips their hue, and a partial one
    does nothing.
    """
    QImage = _gui("QImage")
    image = image.convertToFormat(QImage.Format_ARGB32)
    native = _native()
    light_l = LIGHT_OKL if light_l is None else light_l
    dark_l = DARK_OKL if dark_l is None else dark_l
    if native is not None:
        try:
            count, width = image.width() * image.height(), image.width()
            if anchors:
                native[4](_address(image), count, width, ANCHOR_MODES[anchors], dark_l, light_l, keep_tint,
                          BACKGROUND_OKL, 1)
            elif keys:
                import ctypes
                native[3](_address(image), count, width, (ctypes.c_uint32 * len(keys))(*keys), len(keys), dark_l,
                          light_l, keep_tint, min_l, edge_target)
            else:
                native[0](_address(image), count, width, dark_l, light_l, min_l, ink_below, keep_tint, edge_neutral)
            return image
        except Exception as exc:
            _note_error("map_image", exc)
            _state()["native"] = None
    if anchors in ("all", "icon", "subpixel", "syntax") or (not anchors and min_l <= 0.0 and not keys):
        image.invertPixels()
    return image


def defringe_image(image):
    """A Format_ARGB32 copy of a QImage whose gray text's ClearType fringes are gray (real colors kept).

    Without the native helper, the copy is unchanged.
    """
    image = image.convertToFormat(_gui("QImage").Format_ARGB32)
    native = _native()
    if native is not None and native[5] is not None:
        try:
            native[5](_address(image), image.width() * image.height(), image.width(), DEFRINGE_MAX_SPREAD)
        except Exception as exc:
            _note_error("defringe", exc)
    return image


DEFRINGE_MAX_SPREAD = 255  # any fringe: the ground and the text cores decide, not the spread


def ink_count(image):
    """How many pixels the "ink" anchor mapping would change in a QImage (0 without the native helper)."""
    native = _native()
    if native is None:
        return 0
    image = image.convertToFormat(_gui("QImage").Format_ARGB32)
    return int(native[4](_address(image), image.width() * image.height(), image.width(), ANCHOR_MODES["ink"],
                         DARK_OKL, LIGHT_OKL, 0.0, BACKGROUND_OKL, 0))


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

_SHEET_IMAGE_RE = re.compile(r"url\(\s*([\"']?)(:/[^\"')]+)\1\s*\)")


def map_sheet_images(sheet, mapped_path):
    """Point a stylesheet's resource images (url(:/...)) at mapped copies; mapped_path(resource) gives
    the copy's file, or None to leave that image as it is."""
    def replace(match):
        path = mapped_path(match.group(2))
        return match.group(0) if not path else u"url(\"%s\")" % path.replace("\\", "/")
    return _SHEET_IMAGE_RE.sub(replace, sheet)


def _mapped_resource(resource):
    """A dark copy of one of FontLab's resource images (arrows, check boxes, info-bar icons that its
    stylesheets name), saved once per shade; None for pictures, color swatches, white artwork (the
    logo in the Welcome dialog's bottom bar), and failures."""
    state = _state()
    cache = state.setdefault("sheet_images", {})
    key = (state.get("shade", "dark"), resource)
    if key in cache:
        return cache[key]
    path = None
    try:
        QImage = _gui("QImage")
        image = QImage(resource)
        if (not image.isNull() and image.width() <= MAX_ICON_SIDE and image.height() <= MAX_ICON_SIDE
                and not is_swatch(image) and not is_white_artwork(image)):  # FontLab's logo stays white
            folder = os.path.join(state_dir(), "cache", "images-%s-%s-%d" % (VERSION, key[0], NATIVE_VERSION))
            if not os.path.isdir(folder):
                os.makedirs(folder)
            stem, ext = os.path.splitext(resource[2:].replace("/", "_"))
            path = os.path.join(folder, stem + ".png")
            if not os.path.isfile(path):
                map_image(image, anchors="icon").save(path)
                base, _ext = os.path.splitext(resource)
                double = QImage(base + "@2x" + ext)  # Qt picks name@2x.png on high-density screens
                if not double.isNull():
                    map_image(double, anchors="icon").save(os.path.join(folder, stem + "@2x.png"))
    except Exception as exc:
        _note_error("sheet image", exc)
        path = None
    cache[key] = path
    return path


PLAIN_INPUTS = ("QComboBox", "QAbstractSpinBox", "QLineEdit")


def _plain_input(widget):
    """A combo box, spin box, or field of Qt's with no stylesheet on it or around it (FreeLab's own
    dialogs): Fusion draws it from the dark palette alone. The ink effect, which its dark outlines
    and arrows set off, garbled its text and hid its arrows."""
    if not any(widget.inherits(c) for c in PLAIN_INPUTS):
        return False
    current = widget
    while current is not None:
        if current.property(SHEET_PROP) or _prop(current, "styleSheet"):
            return False
        if current.isWindow():
            return True
        current = current.parentWidget()
    return True


def _shows_white_artwork(widget):
    """A label whose stylesheet shows only white artwork (the Welcome dialog's logo), or a button
    whose icon has white artwork (a checked state's white mark): no effect over them."""
    if widget.inherits("QAbstractButton"):
        return _icon_has_white_artwork(_prop(widget, "icon"))
    if not widget.inherits("QLabel"):
        return False
    sheet = widget.property(SHEET_PROP) or _prop(widget, "styleSheet") or u""
    resources = [m.group(2) for m in _SHEET_IMAGE_RE.finditer(sheet)]
    if not resources:
        return False
    QImage = _gui("QImage")
    return all(is_white_artwork(QImage(resource)) for resource in resources)


def _icon_has_white_artwork(icon):
    if icon is None or icon.isNull():
        return False
    original = _state()["originals"].get(icon.cacheKey(), icon)
    sizes = list(original.availableSizes())
    if not sizes:
        return False
    QIcon = _gui("QIcon")
    for icon_state in (QIcon.Off, QIcon.On):
        pixmap = original.pixmap(sizes[0], QIcon.Normal, icon_state)
        if not pixmap.isNull() and is_white_artwork(pixmap.toImage()):
            return True
    return False


def _darken_sheet(widget):
    sheet = _prop(widget, "styleSheet")
    if not sheet:
        return
    ours = widget.property(DARK_SHEET_PROP)
    if sheet == ours:
        return  # already ours
    if ours is not None:
        _watch(widget)  # FontLab restyles this one while it works (fields while a glyph is edited): catch it at once
    dark = map_sheet_images(recolor_sheet(sheet), _mapped_resource)
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
                    image = pixmap.toImage()
                    if is_white_artwork(image):  # a white check on a checked button's blue: white on purpose
                        image = whitened(image)
                    else:
                        image = map_image(image, anchors="icon")
                    result.addPixmap(QPixmap.fromImage(image), mode, icon_state)
    return result


def dark_pixmap(pixmap):
    """A label's image mapped; white artwork (FontLab's logo) stays as it is. Button icons do not get
    that rule: a toggled button's white icon, kept, turned black under the button's ink effect."""
    image = pixmap.toImage()
    return _gui("QPixmap").fromImage(whitened(image) if is_white_artwork(image) else map_image(image, anchors="icon"))


ARTWORK_WHITE = 235  # every visible pixel at least this light, on transparency: white artwork
ARTWORK_SAMPLE = 24  # sides of the scaled copy looked at


def whitened(image):
    """White artwork with every pixel white, its transparency kept: its faint edge pixels (dark in
    some of FontLab's icons) made a dark halo on the gray of a checked button."""
    QImage = _gui("QImage")
    image = image.convertToFormat(QImage.Format_ARGB32)  # straight alpha
    for y in range(image.height()):
        for x in range(image.width()):
            alpha = (image.pixel(x, y) >> 24) & 255
            if alpha:
                image.setPixel(x, y, (alpha << 24) | 0xffffff)
    return image


def is_white_artwork(image):
    """White artwork on transparency (FontLab's logo, white glyphs on icons meant for color): drawn
    white on purpose, it stays white; mapped as paper, the logo turned black."""
    QImage, Qt = _gui("QImage"), _core("Qt")
    if image.isNull() or not image.hasAlphaChannel():
        return False
    small = image.convertToFormat(QImage.Format_ARGB32)
    if small.width() > ARTWORK_SAMPLE or small.height() > ARTWORK_SAMPLE:
        small = small.scaled(ARTWORK_SAMPLE, ARTWORK_SAMPLE, Qt.KeepAspectRatio, Qt.FastTransformation)  # no blending: its own pixels
    seen = clear = False
    for y in range(small.height()):
        for x in range(small.width()):
            value = small.pixel(x, y)
            alpha = (value >> 24) & 255
            if alpha < 255:
                clear = True
            if alpha < 64:
                continue  # smoothing toward transparency: blended, not the artwork's color
            if min((value >> 16) & 255, (value >> 8) & 255, value & 255) < ARTWORK_WHITE:
                return False
            seen = True
    return seen and clear


SWATCH_CHROMA = 80  # max - min of the channels: clearly colored
GRAY_ICON_SHARE = 0.5  # a list icon at most this colored is mapped (Autohinting's has colored parts, kept as
                       # icons keep them); colorful logos (Export Profiles' formats) are not: mapped, they turned jagged
GRAY_ICON_MIN_ALPHA = 32  # faint line icons count too (Grid & Guides draws no pixel half opaque at 16 px)
SWATCH_SHARE = 0.4  # an icon this colored is a color swatch (mark colors): left as it is
SWATCH_FILL = 0.5  # and this filled: a swatch is a solid shape; a thin colored glyph (the red Y and X of
                   # TrueType Hinting's direction buttons, black stems included) is an icon


def is_swatch(image):
    """True for an image that is mostly filled and clearly colored: a color swatch, which must keep its color."""
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
    return opaque >= SWATCH_FILL * 144 and colored >= SWATCH_SHARE * opaque


def icon_is_gray(icon):
    """Mostly gray: a list's light-mode page icon, which is mapped; colorful ones (format logos) are not."""
    QImage, QColor, Qt = _gui("QImage"), _gui("QColor"), _core("Qt")
    sizes = list(icon.availableSizes())
    pixmap = icon.pixmap(sizes[0] if sizes else _core("QSize")(16, 16))
    if pixmap.isNull():
        return False
    small = pixmap.toImage().convertToFormat(QImage.Format_ARGB32).scaled(12, 12, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    opaque = colored = 0
    for y in range(12):
        for x in range(12):
            color = QColor.fromRgba(small.pixel(x, y))
            if color.alpha() < GRAY_ICON_MIN_ALPHA:
                continue
            opaque += 1
            channels = (color.red(), color.green(), color.blue())
            colored += max(channels) - min(channels) >= SWATCH_CHROMA
    return colored <= GRAY_ICON_SHARE * opaque  # an icon with nothing visible at this size counts as gray


def icon_is_swatch(icon):
    sizes = list(icon.availableSizes())
    size = sizes[0] if sizes else _core("QSize")(16, 16)
    pixmap = icon.pixmap(size)
    return not pixmap.isNull() and is_swatch(pixmap.toImage())


def _swap_icon(obj):
    if obj.property(LEAVE_ALONE_PROP):
        return
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
    if _under_ink(label):
        return  # the ink effect around it maps its image as drawn (see _unswap_labels_inside)
    new = dark_pixmap(pixmap)
    state["mapped_keys"].add(new.cacheKey())
    _record(label)["pixmap"] = pixmap
    label.setPixmap(new)


def _under_ink(widget):
    """Inside a widget FreeLab's ink effect maps (within its window)."""
    current = widget
    while not current.isWindow():
        current = current.parentWidget()
        if current is None:
            return False
        record = _record(current, create=False)
        if record is not None and record.get("kind") == "ink" and record.get("effect") is not None and _ours(current, record):
            return True
    return False


def _unswap_labels_inside(widget):
    """Give the labels inside a widget that now gets the ink effect their images back as FontLab drew
    them. Mapped twice, a mapped image went wrong: the font window's mark flag (red, with a black pole
    made light) lay beside the white "no flag" slot, and the ink effect read the light pole as
    smoothing between the dark paper and that white, and turned it dark again. Its black pole as
    drawn is plain ink, which the effect maps light."""
    state = _state()
    for record in list(state["records"].values()):
        label = record.get("obj")
        if "pixmap" not in record or label is None or not _alive(label) or not widget.isAncestorOf(label):
            continue
        original = record.pop("pixmap")
        current = _prop(label, "pixmap")
        if current is not None and current.cacheKey() in state["mapped_keys"]:
            label.setPixmap(original)  # else FontLab set another image since: it stays


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
    if widget.property(LEAVE_ALONE_PROP):
        return  # FreeLab's own pictures (Auto Kerning's previews): drawn for the palette, never mapped
    if widget.inherits("QTreeWidget") or widget.inherits("QListWidget"):
        _swap_item_icons(widget)
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


def _list_items(widget):
    """The items of a QTreeWidget (all levels) or a QListWidget."""
    items = []
    if widget.inherits("QTreeWidget"):
        pending = [widget.topLevelItem(i) for i in range(_prop(widget, "topLevelItemCount"))]
        while pending:
            item = pending.pop()
            if item is None:
                continue
            items.append(item)
            pending.extend(item.child(i) for i in range(item.childCount()))
    else:
        items = [widget.item(i) for i in range(_prop(widget, "count"))]
    return [item for item in items if item is not None]


LOGO_ROWS_MAX = 200  # visible rows looked at per paint
LOGO_MIN_SIDE = 24  # a list icon drawn this large or larger is a picture (Export Profiles' formats are 32 px)


def _logo_rects(view):
    """The viewport rectangles of the visible logo icons in a list (the style's decoration place:
    at the left of the cell, centered), for icons dark mode leaves as FontLab draws them."""
    QRect, QPoint, Qt = _core("QRect"), _core("QPoint"), _core("Qt")
    QStyle = _gui("QStyle")
    model = view.model()
    if model is None:
        return []
    state = _state()
    logos = state.setdefault("logo_keys", {})
    style = view.style()
    size = view.iconSize.width() if view.iconSize.width() > 0 else style.pixelMetric(QStyle.PM_SmallIconSize)
    margin = style.pixelMetric(QStyle.PM_FocusFrameHMargin) + 1
    viewport = view.viewport()
    rects = []
    first = view.indexAt(QPoint(1, 1))
    if not first.isValid():
        return []
    index = first
    for _ in range(LOGO_ROWS_MAX):
        row_rect = view.visualRect(index)
        if not index.isValid() or row_rect.top() > viewport.height:
            break
        for column in range(model.columnCount(index.parent())):
            cell = model.index(index.row(), column, index.parent())
            icon = model.data(cell, Qt.DecorationRole)
            if icon is None or not hasattr(icon, "availableSizes") or icon.isNull():  # icons only (not pixmaps)
                continue
            key = icon.cacheKey()
            logo = logos.get(key)
            if logo is None:
                large = any(s.width() >= LOGO_MIN_SIDE for s in icon.availableSizes())  # a picture, not a line icon
                logo = logos[key] = key not in state["mapped_keys"] and (large or icon_is_swatch(icon) or not icon_is_gray(icon))
            if logo:
                r = view.visualRect(cell)
                rects.append(QRect(r.x() + margin, r.y() + (r.height() - size) // 2, size, size))
        if view.inherits("QTreeView"):
            index = view.indexBelow(index)
        else:  # flat lists and tables: the next row of the model
            index = model.index(index.row() + 1, 0, index.parent())
    return rects


def _swap_item_icons(widget):
    """Item icons of FontLab's lists (Font Info's and Preferences' pages): drawn for light mode, the
    gray ones nearly vanished on dark. Mapped as button icons are; colorful ones and logos (Export
    Profiles' formats) stay as drawn. Items are never kept: FontLab deletes and rebuilds them, and a
    deleted item is no Qt object Python can tell is gone (restoring through one crashed FontLab)."""
    state = _state()
    record = _record(widget)
    tree = widget.inherits("QTreeWidget")
    for item in _list_items(widget):
        icon = item.icon(0) if tree else item.icon()
        if icon is None or icon.isNull():
            continue
        key = icon.cacheKey()
        if key in state["mapped_keys"] or key in state["swatches"]:
            continue
        if key not in state["icon_cache"] and (icon_is_swatch(icon) or not icon_is_gray(icon)):
            state["swatches"].add(key)  # colorful (Export Profiles' format logos): left as drawn, mapped they turned jagged
            continue
        new = state["icon_cache"].get(key)
        if new is None:
            new = state["icon_cache"][key] = dark_icon(icon)
            state["mapped_keys"].add(new.cacheKey())
            state["originals"][new.cacheKey()] = icon
        record["item_icons"] = True
        if tree:
            item.setIcon(0, new)
        else:
            item.setIcon(new)


def _restore_item_icons(widget, record):
    """Put back the originals of the mapped icons the list shows now, through its current items."""
    record.pop("item_icons", None)
    originals = _state()["originals"]
    tree = widget.inherits("QTreeWidget")
    for item in _list_items(widget):
        icon = item.icon(0) if tree else item.icon()
        original = originals.get(icon.cacheKey()) if icon is not None and not icon.isNull() else None
        if original is None:
            continue
        if tree:
            item.setIcon(0, original)
        else:
            item.setIcon(original)


def _restore_icons(obj, record):
    if "item_icons" in record:
        _restore_item_icons(obj, record)
    if "icon" in record:
        obj.setIcon(record.pop("icon"))
    if "pixmap" in record:
        obj.setPixmap(record.pop("pixmap"))


# ---------------------------------------------------------------------------
# Islands, ink areas, editors, and panel titles
# ---------------------------------------------------------------------------

_EFFECTS = {}
EFFECT_MIN_L = {"keyed": WHITE_L}
# Effect kinds. Drawn by anchor blends (see map_image):
# "island": everything mapped (a widget kept in FontLab's light look).
# "ink": on the dark interface, only what is wrong there: white and light surfaces, and dark
#   text or icons (FontLab paints list rows, badges, and previews in fixed colors).
# "edges": editors (QScintilla): their white margin mapped to gray numbers, then "ink" on a paper
#   that is already dark, or everything on a paper taken from a light palette.
# "subpixel": ClearType black text (TrueType Hinting's preview), mapped channel by channel.
# "relight": after switching off, an editor whose paper stayed dark, mapped light again.
# Drawn otherwise:
# "keyed": only the listed frame colors mapped. "title": a panel drawn as it is, its title strip
#   mapped. "picker": the swatch as it is, the arrow beside it mapped. "defringe": a widget dark
#   already, drawn as it is, its gray text's ClearType fringes made gray (freelab_defringe).
EDGES_PARENTS = ("QsciScintilla",)  # their viewport (QWidget#qt_scrollarea_viewport) paints the text
# Scroll areas whose viewport paints item rows or text, in colors of FontLab's own: "ink".
INK_VIEW_PARENTS = ("QAbstractItemView", "QTextEdit", "QPlainTextEdit", "QtnPropertyView")
# Tiny light text that ClearType draws as blue and yellow fringes with no light core (the font window's
# "Name: Encoding: None Index" selectors): any effect draws it through a transparent image, where text
# gets grayscale smoothing; the ink mapping leaves light text as it is.
GRAYSCALE_TEXT_CLASSES = ("YSelector",)
STYLE_DRAWN_BUTTONS = ("QRadioButton", "QCheckBox", "QPushButton")  # never ink by render detection
# Bars dark mode's stylesheet already darkens inside a window drawn through the ink effect: kept
# out of its mapping (which garbled their labels) and drawn with their text's ClearType fringes
# made gray. (parent class, object name)
DEFRINGE_NAMES = (("FontWindow", "frameBottom"),)
GRAYSCALE_TEXT_NAMES = ("labelMode",)  # the colon between those selectors
# Text drawn with ClearType on purpose (TrueType Hinting's preview): each channel's coverage is kept
# and redrawn light on dark ("subpixel" mapping), which inverting lightness cannot do.
SUBPIXEL_CLASSES = ("RenderWidget",)
LEGACY_KINDS = {"selective": "ink"}  # recorded on widgets by FreeLab 0.2 before the anchor blends

# Content keeps every color: anchors, nodes, and marks carry meaning even when muted.
# Interface islands keep no tint of low-color pixels (LINEAR_SPREAD), which removes ClearType fringes.
CONTENT_CLASSES = ("FontCellChart", "CellChart", "YNibShape", "YStrokeShape", "YBrushStrokePreview", "FontPreviewWidget")


def gray_image(image):
    """The image in grays (its alpha kept): ClearType's colored fringes become plain smoothing."""
    QImage = _gui("QImage")
    try:
        gray = image.convertToFormat(QImage.Format_Grayscale8)
    except Exception:  # an older Qt: leave it in color
        return image
    alpha = image.convertToFormat(QImage.Format_Alpha8) if image.hasAlphaChannel() else None
    out = gray.convertToFormat(QImage.Format_ARGB32)
    if alpha is not None:
        out.setAlphaChannel(alpha)
    return out


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

        def draw_mapped(painter, pixmap, offset, area, min_l, keys=None, ink_below=-1.0, keep_tint=0.0, light_l=None,
                        edge_neutral=0.0, edge_target=0, anchors=None, dark_l=None, gray=False, analyze=None):
            """Draw the part of pixmap that lands on `area` (painter coordinates), mapped.

            analyze: a larger rect (painter coordinates) whose pixels decide the mapping, of which
            only the repainted part is drawn: the ink mapping weighs colors against each other, and
            a few repainted rows alone (a clicked page in Font Info's list, an edited line in Source)
            came out differently from the whole widget.
            """
            area = area.intersected(QRect(offset, pixmap.size()))
            if painter.hasClipping():
                area = area.intersected(painter.clipBoundingRect().toAlignedRect())
            if area.isEmpty():
                return
            if analyze is not None:
                analyze = analyze.intersected(QRect(offset, pixmap.size()))
                if analyze.contains(area) and analyze != area:
                    part = pixmap.copy(analyze.translated(-offset.x(), -offset.y())).toImage()
                    if gray:
                        part = gray_image(part)
                    mapped = map_image(part, min_l, keys, ink_below, keep_tint, light_l, edge_neutral, edge_target,
                                       anchors, dark_l)
                    painter.drawImage(area.topLeft(), mapped, area.translated(-analyze.x(), -analyze.y()))
                    return
            if True:
                part = pixmap.copy(area.translated(-offset.x(), -offset.y())).toImage()
                if gray:
                    part = gray_image(part)
                painter.drawImage(area.topLeft(), map_image(part, min_l, keys, ink_below, keep_tint, light_l, edge_neutral,
                                                            edge_target, anchors, dark_l))

        class MapEffect(QGraphicsEffect):
            """Draw the widget with its colors mapped: by anchor blends (islands, ink, editors), or by key (frames)."""

            def draw(self, painter):
                try:
                    pixmap, offset = source(self)
                    whole = QRect(offset, pixmap.size())
                    kind = self.freelab_kind
                    if kind == "keyed":
                        draw_mapped(painter, pixmap, offset, whole, self.freelab_min_l, self.freelab_keys, -1.0,
                                    self.freelab_keep_tint, None, 0.0, self.freelab_edge_target)
                        keep_unmapped(self, painter, pixmap, offset)  # a frame color may recur inside a panel
                        return
                    if kind == "relight":  # an editor left dark after switching off: its dark paper white, its light text black
                        draw_mapped(painter, pixmap, offset, whole, 0.0, None, -1.0, 0.0, None, 0.0, 0, "relight")
                        return
                    if kind == "picker":  # the swatch as it is; its frame and the dark arrow beside it mapped
                        side = pixmap.height() - 2  # the swatch: a square at the left, inside a 2-px frame
                        image = pixmap.toImage()
                        draw_mapped(painter, pixmap, offset, whole, 0.0, None, -1.0, 0.0, None, 0.0, 0, "all")
                        if side > 6:
                            inside = QRect(3, 3, side - 4, side - 4)  # the swatch within the frame FontLab paints light
                            probe_x, probe_y = side // 4 + 1, side // 4 + 1  # off the "no color" diagonal
                            if _gui("QColor").fromRgba(image.pixel(probe_x, probe_y)).alpha() < 200:
                                # Some pickers paint "no color" transparent: give them the white slot others paint.
                                painter.fillRect(inside.translated(offset), Qt.white)
                            painter.drawPixmap(inside.translated(offset), pixmap, inside)
                        # Around that square, only the light frame is mapped: a picker that paints its
                        # swatch at full height (the mark color's) keeps its color to the edges.
                        split = min(pixmap.width(), pixmap.height() + PICKER_SWATCH_GAP)
                        colored = _colored_part(image, QRect(0, 0, split, pixmap.height()))
                        if colored is not None:
                            painter.drawImage(offset, colored)
                        return
                    if kind == "defringe":  # dark already (its stylesheet): only its text's fringes made gray
                        area = whole
                        if painter.hasClipping():
                            area = area.intersected(painter.clipBoundingRect().toAlignedRect())
                        if not area.isEmpty():
                            # decided on the whole widget (its ground), drawn where it is repainted
                            image = defringe_image(pixmap.toImage())
                            painter.drawImage(area.topLeft(), image, area.translated(-offset.x(), -offset.y()))
                        keep_unmapped(self, painter, pixmap, offset)
                        return
                    anchors = {"island": "all", "subpixel": "subpixel"}.get(kind, "ink")
                    editor = self.freelab_widget.parentWidget() if kind == "edges" else None
                    editor_record = _record(editor, create=False) if editor is not None else None
                    native = editor_record is not None and editor_record.get("sci")
                    if native and _editor_restyled(editor, editor_record):
                        # FontLab set its own colors again: this paint goes through the pixel mapping below,
                        # and the editor is colored anew right after it
                        native = False
                        _core("QTimer").singleShot(0, lambda: _recolor_editor(editor))
                    if native:
                        # colored natively (see _darken_editor): its text as drawn, only the margin mapped
                        painter.drawPixmap(offset, pixmap)
                        margin = editor_margin(pixmap)
                        if margin:
                            draw_mapped(painter, pixmap, offset, QRect(offset.x(), offset.y(), margin, pixmap.height()),
                                        0.0, None, -1.0, 0.0, MARGIN_OKL)
                        return
                    if kind == "edges":
                        if light_paper(pixmap, 0):
                            # paper the editor took from a light palette: its ClearType text redrawn per channel
                            # toward each syntax color's dark-mode color (blue keys and red numbers kept), as
                            # ClearType draws light text on dark; inverting lightness left every edge fringed. Mapped
                            # in one piece, margin included: on white paper every column looks like the margin
                            anchors = "syntax"
                        else:
                            margin = editor_margin(pixmap)
                            if margin:
                                draw_mapped(painter, pixmap, offset, QRect(offset.x(), offset.y(), margin, pixmap.height()),
                                            0.0, None, -1.0, 0.0, MARGIN_OKL)
                                whole = QRect(offset.x() + margin, offset.y(), pixmap.width() - margin, pixmap.height())
                    # Fields paint an opaque background, so their light text keeps ClearType's colored
                    # fringes even inside an effect: grays, unless text is selected (the blue highlight).
                    gray = getattr(self, "freelab_gray", False) and not (
                        self.freelab_widget.inherits("QLineEdit") and _prop(self.freelab_widget, "hasSelectedText"))
                    draw_mapped(painter, pixmap, offset, whole, 0.0, None, -1.0, self.freelab_keep_tint, None, 0.0, 0,
                                anchors, None, gray, QRect(whole) if kind in ("ink", "edges") else None)
                    if kind == "ink":
                        keep_logos(self, painter, pixmap, offset)
                    keep_unmapped(self, painter, pixmap, offset)
                except Exception as exc:
                    _note_error("effect", exc)
                    self.drawSource(painter)

        def keep_logos(effect, painter, pixmap, offset):
            """A list's logo icons (Export Profiles' formats) as FontLab draws them, over the ink mapping,
            which inverted their dark parts with rough edges; the rows' text is still mapped."""
            view = effect.freelab_widget.parentWidget()
            if view is None or not view.inherits("QAbstractItemView"):
                return
            try:
                rects = _logo_rects(view)
            except Exception as exc:  # the mapping is drawn already: only the logos are left mapped
                _note_error("list logos", exc)
                return
            for rect in rects:
                area = rect.translated(offset).intersected(QRect(offset, pixmap.size()))
                if painter.hasClipping():
                    area = area.intersected(painter.clipBoundingRect().toAlignedRect())
                if not area.isEmpty():
                    painter.drawPixmap(area.topLeft(), pixmap, area.translated(-offset.x(), -offset.y()))

        def keep_unmapped(effect, painter, pixmap, offset):
            """Draw protected descendants (color swatches, mark slots, pickers) as they are, over the mapping."""
            owner = effect.freelab_widget
            protect = getattr(effect, "freelab_protect", {})
            for key, widget in list(protect.items()):
                if not _alive(widget) or widget is owner or not owner.isAncestorOf(widget):
                    # moved out (an undocked panel): Qt's mapTo walks off a parent chain that
                    # does not reach the owner and crashes on the null at its end
                    del protect[key]
                    continue
                if not widget.isVisible():
                    continue
                corner = widget.mapTo(owner, QPoint(0, 0))
                area = QRect(corner.x() + offset.x(), corner.y() + offset.y(), _prop(widget, "width"),
                             _prop(widget, "height")).intersected(QRect(offset, pixmap.size()))
                if not area.isEmpty():
                    painter.drawPixmap(area.topLeft(), pixmap, area.translated(-offset.x(), -offset.y()))

        class TitleEffect(QGraphicsEffect):
            """Draw a panel as it is, then its title strip mapped."""

            def draw(self, painter):
                try:
                    pixmap, offset = source(self)
                    painter.drawPixmap(offset, pixmap)
                    height = title_height(self.freelab_widget)
                    if height > 0:
                        # Gray first: a hovered title's text is black, with ClearType fringes saturated enough
                        # to be anchors of their own, which kept their blue and orange.
                        area = QRect(offset.x(), offset.y(), pixmap.width(), height)
                        if painter.hasClipping():
                            area = area.intersected(painter.clipBoundingRect().toAlignedRect())
                        if not area.isEmpty():
                            part = pixmap.copy(area.translated(-offset.x(), -offset.y())).toImage()
                            part = gray_image(part)
                            painter.drawImage(area.topLeft(), map_image(part, 0.0, None, -1.0, 0.0, None, 0.0, 0, "all"))
                except Exception as exc:
                    _note_error("title", exc)
                    self.drawSource(painter)

        _EFFECTS["map"] = MapEffect
        _EFFECTS["title"] = TitleEffect
    return _EFFECTS


def editor_margin(pixmap):
    """Width of an editor's white margin at the left of its rendered pixmap (0 when there is none)."""
    # Column by column, sampled on rows across the editor: a margin column stays largely white where
    # line numbers cross it (one row alone stopped at the first digit it met).
    QColor, QImage = _gui("QColor"), _gui("QImage")
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    rows = [image.height() * i // MARGIN_SAMPLES for i in range(1, MARGIN_SAMPLES)]
    width = 0
    for x in range(min(image.width(), 120)):
        white = 0
        for y in rows:
            color = QColor.fromRgba(image.pixel(x, y))
            white += _lightness(color.red(), color.green(), color.blue()) >= WHITE_L
        if white < MARGIN_WHITE_SHARE * len(rows):
            break
        width = x + 1
    return width if width >= 8 else 0


MARGIN_SAMPLES = 16
MARGIN_WHITE_SHARE = 0.25  # digits cover a column now and then; the paper beside the margin is never white


def light_paper(pixmap, margin):
    """True when most of an editor's text area is light: it took its paper from a light palette
    (an editor made before dark mode was switched on, or kept from before a switch)."""
    QColor, QImage = _gui("QColor"), _gui("QImage")
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    light = dark = 0
    for i in range(1, 9):
        y = image.height() * i // 9
        for j in range(1, 9):
            x = margin + (image.width() - margin) * j // 9
            if 0 <= x < image.width() and 0 <= y < image.height():
                color = QColor.fromRgba(image.pixel(x, y))
                light += _lightness(color.red(), color.green(), color.blue()) >= WHITE_L
                dark += _lightness(color.red(), color.green(), color.blue()) < 0.3
    return light > dark


# ---------------------------------------------------------------------------
# Editors (QScintilla), colored natively
# ---------------------------------------------------------------------------
# FontLab gives its editors (Source, Features, TrueType Hinting's program) light-theme style colors:
# black and navy text, sometimes on white paper. Mapping their pixels left ClearType's colored
# fringes on every edge, changing with each partial repaint (a selection, a click). Where
# QScintilla's own SendScintilla can be reached, dark mode sets each style's colors instead, so the
# editor draws light text on dark paper itself, smoothed as any dark editor's text is; only the
# margin is still mapped by the "edges" effect. The original colors are written back on switching off.

SCI_DLL = "qscintilla2_qt5.dll"
SCI_SEND = "?SendScintilla@QsciScintillaBase@@QEBAJIKJ@Z"  # long SendScintilla(unsigned int, unsigned long, long) const
SCI_STYLESETFORE, SCI_STYLESETBACK, SCI_STYLEGETFORE, SCI_STYLEGETBACK = 2051, 2052, 2481, 2482
SCI_SETCARETFORE, SCI_GETCARETFORE = 2069, 2138
SCI_SETCARETLINEBACK, SCI_GETCARETLINEBACK = 2098, 2097
SCI_STYLES = tuple(s for s in range(256) if s != 33)  # every style (QScintilla numbers its own down from 255); 33, line numbers, is the margin's
SCI_CHECKED_STYLES = 40  # lexer and predefined styles: compared on every repaint
EDITOR_GRAY_SPREAD = 24  # editor text with less spread than this is gray (black text, gray comments)
EDITOR_TEXT_MIN_L = 0.76  # colored text is lightened to at least this OKLab lightness, its hue kept
_SCI = {}


def _sci_send():
    """QScintilla's SendScintilla through ctypes, or None (another build, or not Windows)."""
    if "send" not in _SCI:
        _SCI["send"] = None
        if os.name == "nt":
            try:
                import ctypes
                send = getattr(ctypes.PyDLL(SCI_DLL), SCI_SEND)  # the copy FontLab loaded; keeps the interpreter lock
                send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulong, ctypes.c_long]
                send.restype = ctypes.c_long
                _SCI["send"] = send
            except (OSError, AttributeError):
                pass  # no such library or entry point: editors keep the pixel mapping
    return _SCI["send"]


def _sci_pointer(widget):
    """The editor's C++ address, from Qt's own description of it ("QsciScintilla(0x..., name=...)")."""
    import re
    match = re.match(r"\s*\w+\((0x[0-9a-fA-F]+)", repr(widget))
    pointer = int(match.group(1), 16) if match else 0
    return pointer or None


def _bgr_to_rgb(value):
    return (value & 255, (value >> 8) & 255, (value >> 16) & 255)


def _rgb_to_bgr(rgb):
    return rgb[0] | (rgb[1] << 8) | (rgb[2] << 16)


def editor_text_rgb(rgb):
    """An editor style's text color in dark mode: dark grays made light (light ones kept, as stylesheet
    text is: an editor made under the dark palette has light gray text already), colors lightened with
    their hue kept."""
    if max(rgb) - min(rgb) < EDITOR_GRAY_SPREAD:
        return tuple(recolor(rgb, "color"))
    l, a, b = oklab(*rgb)
    return tuple(_oklab_to_bytes(max(l, EDITOR_TEXT_MIN_L), a, b))


def editor_paper_rgb(rgb):
    """An editor style's background in dark mode: light ones mapped dark, dark ones kept."""
    return tuple(recolor(rgb, "background"))


def _editor_keys():
    keys = [(SCI_STYLEGETFORE, SCI_STYLESETFORE, style, editor_text_rgb) for style in SCI_STYLES]
    keys += [(SCI_STYLEGETBACK, SCI_STYLESETBACK, style, editor_paper_rgb) for style in SCI_STYLES]
    keys.append((SCI_GETCARETFORE, SCI_SETCARETFORE, None, editor_text_rgb))
    keys.append((SCI_GETCARETLINEBACK, SCI_SETCARETLINEBACK, None, editor_paper_rgb))
    return keys


def _sci_get(send, pointer, getter, style):
    return send(pointer, getter, style if style is not None else 0, 0) & 0xFFFFFF


def _sci_set(send, pointer, setter, style, value):
    if style is None:
        send(pointer, setter, value, 0)
    else:
        send(pointer, setter, style, value)


def _darken_editor(widget, record):
    """Give a QScintilla editor dark-mode style colors; True when it is colored natively.

    Each color it holds that dark mode did not set is taken as FontLab's (it may restyle an editor
    at any time) and replaced by its dark-mode counterpart.
    """
    send = _sci_send()
    pointer = _sci_pointer(widget) if send is not None else None
    if pointer is None:
        return False
    sci = record.setdefault("sci", {"orig": {}, "set": {}})
    for getter, setter, style, rule in _editor_keys():
        key = (setter, style)
        current = _sci_get(send, pointer, getter, style)
        if sci["set"].get(key) == current:
            continue
        sci["orig"][key] = current
        value = _rgb_to_bgr(rule(_bgr_to_rgb(current)))
        sci["set"][key] = value
        if value != current:
            _sci_set(send, pointer, setter, style, value)
    return True


def _recolor_editor(widget):
    """Color an editor natively while dark mode is on; errors are noted, never raised (a timer may call it)."""
    try:
        if _state()["on"] and _alive(widget):
            record = _record(widget)
            if _darken_editor(widget, record):
                widget.viewport().update()
            else:
                _drop_record(widget, record)
    except Exception as exc:
        _note_error("editor", exc)


def _editor_restyled(widget, record):
    """True when FontLab has set its own colors again since dark mode set its own: any lexer or
    predefined style, the caret, or the caret line (higher styles wait for the sweep)."""
    sci = record.get("sci")
    send = _sci_send()
    pointer = _sci_pointer(widget) if sci and send is not None else None
    if pointer is None:
        return False
    for getter, setter, style, _rule in _editor_keys():
        if style is not None and style >= SCI_CHECKED_STYLES:
            continue
        if _sci_get(send, pointer, getter, style) != sci["set"].get((setter, style)):
            return True
    return False


def _restore_editor(widget, record):
    """Put back FontLab's colors where dark mode's are still in place.

    An editor FontLab made while dark mode was on took dark paper from the dark palette: switched
    off, it gets light paper (and dark text where its text was light gray) instead, which the
    relight effect used to approximate by mapping its pixels.
    """
    sci = record.pop("sci", None)
    send = _sci_send()
    pointer = _sci_pointer(widget) if sci and send is not None else None
    if pointer is None:
        return
    # relit only when FontLab made it under the dark palette (its own paper dark): an editor made in
    # light mode keeps its own light-gray styles (indent guides, whitespace)
    paper_key = (SCI_STYLESETBACK, 32)
    relight = (not _state()["on"] and paper_key in sci["orig"]
               and _lightness(*_bgr_to_rgb(sci["orig"][paper_key])) < 0.3)
    saved = _state().get("saved") or {}
    paper = saved.get("palette")
    light_paper_rgb = None
    if paper is not None:
        base = paper.color(_gui("QPalette").Base)
        light_paper_rgb = (base.red(), base.green(), base.blue())
    for getter, setter, style, rule in _editor_keys():
        key = (setter, style)
        if key not in sci["orig"] or _sci_get(send, pointer, getter, style) != sci["set"].get(key):
            continue  # FontLab changed it meanwhile: its own
        value = sci["orig"][key]
        if relight:
            rgb = _bgr_to_rgb(value)
            light = _lightness(*rgb)
            if rule is editor_paper_rgb and light < 0.3 and light_paper_rgb is not None:
                value = _rgb_to_bgr(light_paper_rgb)
            elif rule is editor_text_rgb and light >= 0.6 and max(rgb) - min(rgb) < EDITOR_GRAY_SPREAD:
                value = _rgb_to_bgr(tuple(map_rgb(*rgb)))
        _sci_set(send, pointer, setter, style, value)


def frame_target(keys):
    """The mapped color of the lightest frame key, as 0xRRGGBB: the color a frame's blended ends take."""
    lightest = max(keys, key=lambda k: _lightness((k >> 16) & 255, (k >> 8) & 255, k & 255))
    r, g, b = map_rgb((lightest >> 16) & 255, (lightest >> 8) & 255, lightest & 255)
    return (r << 16) | (g << 8) | b


def title_height(panel):
    """The panel's title strip: from its top to its first visible child widget."""
    tops = [_prop(child, "y") for child in panel.children()
            if child.isWidgetType() and child.isVisible()]
    top = min(tops) if tops else 0
    return top if 0 < top <= TITLE_MAX_HEIGHT else 0


def widget_kind(widget, canvas=True):
    """"island", "ink", "edges", "subpixel", "keyed", "fill", "title", "defringe", or None: how dark mode treats this widget beyond its stylesheet."""
    cls = _class_name(widget)
    if _is_one_of(widget, cls, ISLAND_CLASSES) or (cls, _prop(widget, "objectName")) in ISLAND_NAMES:
        return "island"
    if cls in KEYED_CLASSES:
        return "keyed"

    parent = widget.parentWidget()
    if parent is not None:
        parent_cls = _class_name(parent)
        if (parent_cls, _prop(widget, "objectName")) in DEFRINGE_NAMES:
            return "defringe"
        if cls == "QWidget":
            if parent_cls in EDGES_PARENTS and _prop(widget, "objectName") == "qt_scrollarea_viewport":
                return "edges"  # the text area, not the scroll bar containers
            if parent_cls in MARGIN_PARENTS and _prop(widget, "width") <= MARGIN_MAX_WIDTH:
                return "island"
            if canvas and _is_canvas(widget, parent_cls):
                return "island"
            if _prop(widget, "objectName") == "qt_scrollarea_viewport" and any(parent.inherits(c) for c in INK_VIEW_PARENTS):
                return "ink"
    if (cls in GRAYSCALE_TEXT_CLASSES or (cls == "QLabel" and _prop(widget, "objectName") in GRAYSCALE_TEXT_NAMES)
            or widget.inherits("QLineEdit")):  # fields: typed and placeholder text
        return "ink"
    if cls in SUBPIXEL_CLASSES:
        return "subpixel"
    if cls in FILL_CLASSES:
        return "fill"
    if cls in TITLE_CLASSES:
        return "title"
    found = widget.property(ISLAND_PROP)
    if not found:
        return None
    return LEGACY_KINDS.get(str(found), str(found))


def _is_one_of(widget, cls, names):
    """The class is one of names, or derives from one (FontLab subclasses its charts and previews)."""
    return cls in names or any(widget.inherits(name) for name in names)


def _is_canvas(widget, parent_cls):
    return any(parent_cls == rule_parent and name in (None, _prop(widget, "objectName"))
               for rule_parent, name in CANVAS_RULES)


def is_content(widget):
    """Glyph canvases, font cells, previews: their colors (anchors, nodes, marks) are kept."""
    if _is_one_of(widget, _class_name(widget), CONTENT_CLASSES):
        return True
    parent = widget.parentWidget()
    return (_class_name(widget) == "QWidget" and parent is not None
            and _is_canvas(widget, _class_name(parent)))


def _colored_part(image, area):
    """The clearly colored pixels of image within area (the rest transparent), or None if none."""
    QImage = _gui("QImage")
    part = image.copy(area).convertToFormat(QImage.Format_ARGB32)
    any_colored = False
    for y in range(part.height()):
        for x in range(part.width()):
            value = part.pixel(x, y)
            r, g, b = (value >> 16) & 255, (value >> 8) & 255, value & 255
            if ((value >> 24) & 255) and max(r, g, b) - min(r, g, b) >= PICKER_KEEP_CHROMA:
                any_colored = True
            else:
                part.setPixel(x, y, 0)
    return part if any_colored else None


def _frame_picker(widget):
    own = _prop(widget, "styleSheet") or u""
    if own == widget.property(DARK_SHEET_PROP):
        return
    framed = own + PICKER_FRAME
    widget.setProperty(SHEET_PROP, own)
    widget.setProperty(DARK_SHEET_PROP, framed)
    widget.setStyleSheet(framed)


def _protect(widget):
    """Have every mapping effect above this widget draw it unmapped (swatches keep their real colors)."""
    _record(widget)["protected"] = True  # gives it an id; effects made later (a dock's keyed effect is
                                         # replaced when its frame colors are read again) protect it too
    key = int(widget.property(ID_PROP))
    current = widget
    while not current.isWindow():
        current = current.parentWidget()
        if current is None:
            return
        record = _record(current, create=False)
        if record is None or record.get("effect") is None or record.get("kind") == "title" or not _ours(current, record):
            continue
        effect = record["effect"]
        protect = getattr(effect, "freelab_protect", None)
        if protect is None:
            protect = effect.freelab_protect = {}
        if key not in protect:
            protect[key] = widget
            widget.update()  # shown before it was found (a Color panel mode): drawn mapped until now, and
                             # partial repaints kept bands of that


def _drawn_natively(widget):
    """Painted dark by the native engine's hooks (a hooked island, a list's native ink)."""
    try:
        return bool(widget.property(HOOKED_PROP) or widget.property(NATIVE_INK_PROP))
    except Exception:  # deleted meanwhile
        return False


def _protect_effects_inside(widget, effect):
    """Have a new effect draw unmapped the widgets inside it that already have an effect."""
    protect = getattr(effect, "freelab_protect", None)
    if protect is None:
        protect = effect.freelab_protect = {}
    own = widget.property(ID_PROP)
    for key, record in list(_state()["records"].items()):
        inner = record.get("obj")
        if inner is None or record.get("kind") == "title":
            continue
        if record.get("effect") is None and not record.get("protected") and not _drawn_natively(inner):
            continue
        if own is not None and key == int(own):
            continue  # Qt's isAncestorOf is true for the widget itself
        try:
            if widget.isAncestorOf(inner):
                protect[key] = inner
        except Exception:  # deleted meanwhile
            continue
    if not _state()["canvas"]:  # "dark interface": the light content inside keeps FontLab's look
        for inner in _descendants(widget):
            if inner is not widget and is_content(inner):
                _record(inner)
                protect[int(inner.property(ID_PROP))] = inner


def _drop_stray_effect(widget):
    """Remove a FreeLab effect this session has no record of: a relight effect from switching off,
    or one an older version left on a widget it no longer treats (Qt deletes it; any Python
    reference to it, as in the relight list, then points to nothing and is pruned)."""
    if widget.graphicsEffect() is None or not _ours(widget):
        return
    record = _record(widget, create=False)
    if record is None or record.get("effect") is None:
        widget.setGraphicsEffect(None)


# Check boxes and radio buttons: Fusion frames them a little darker than the window color,
# which vanishes on a dark palette; the style draws this frame over it (see _framed_style).
INDICATOR_BORDER = {"dark": "#8c8c92", "medium": "#a8a8ae"}


LEAVE_ALONE_PROP = "freelabLeaveAlone"  # set by FreeLab's own tools on what they draw themselves (previews)


def _left_alone(widget, name):
    return (name in SKIP_CLASSES or any(word in name for word in SKIP_CLASS_WORDS) or bool(widget.property(LEAVE_ALONE_PROP))
            or (widget.inherits("QAbstractButton") and (_prop(widget, "objectName") or u"").startswith(SWATCH_NAME_PREFIXES))
            or (widget.inherits("QAbstractSlider") and _within(widget, COLOR_SLIDER_PANELS)))


def _within(widget, classes):
    current = widget.parentWidget()
    while current is not None:
        if _class_name(current) in classes:
            return True
        if current.isWindow():
            return False
        current = current.parentWidget()
    return False


def _island_ancestor(widget, canvas):
    """The island drawing this widget, if any. An effect draws only within its window, so the search stops there."""
    current = widget
    while not current.isWindow():
        parent = current.parentWidget()
        if parent is None:
            return None
        if parent.property(HOOKED_PROP) is None and widget_kind(parent, canvas) == "island":
            return parent  # (a hooked island maps only its own painting: its children are processed as any)
        current = parent
    return None


def classify_render(width, height, stats, mostly_own):
    """Decide from a widget's own rendering whether it paints fixed light colors.

    stats: (opaque, near-white, near-black) pixel counts. Returns "island" for a
    widget that paints mostly itself, with dark marks on light (text, outlines:
    everything must flip), "ink" for other light areas, else None.
    """
    area = float(width * height)
    opaque, white, black = stats
    if area <= 0:
        return None
    if white < AUTO_WHITE_SHARE * area:
        return "ink" if mostly_own and white >= AUTO_STRIP_SHARE * area else None
    if mostly_own and black >= AUTO_BLACK_SHARE * area:
        return "island"
    return "ink"


# A widget whose own painting has this much dark ink on the dark interface (text or marks in
# FontLab's fixed dark colors: previews, labels, custom rows) gets the "ink" effect.
AUTO_INK_SHARE = 0.003
AUTO_INK_MIN = 24


def classify_ink(width, height, changed):
    """"ink" when the ink mapping would change enough of a widget's own painting, else None."""
    return "ink" if changed >= max(AUTO_INK_MIN, AUTO_INK_SHARE * width * height) else None


def detect_ink(widget):
    """Render the widget alone and look for dark ink (after its icons are mapped: those need no effect)."""
    width, height = _prop(widget, "width"), _prop(widget, "height")
    if width * height < AUTO_MIN_AREA or widget.isWindow() or _shows_picture(widget):
        return None
    if any(widget.inherits(c) for c in STYLE_DRAWN_BUTTONS):
        return None  # the style draws them from the dark palette: mapped as ink, radio circles turned jagged
    if widget.inherits("QAbstractButton") and _swapped_icon(widget):
        return None  # its icon is mapped already; a colored icon (the red Y of TrueType Hinting) read as ink,
        # and the effect then lightened the checked button's rounded corners
    return classify_ink(width, height, ink_count(own_render(widget)))


def _swapped_icon(button):
    icon = _prop(button, "icon")
    return icon is not None and not icon.isNull() and icon.cacheKey() in _state()["mapped_keys"]


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
    content = kind == "island" and is_content(widget)
    effect.freelab_keep_tint = KEEP_TINT_CONTENT if content else 0.0
    effect.freelab_edge_target = frame_target(keys) if keys else 0
    effect.freelab_kind = kind
    effect.freelab_gray = kind == "ink" and _gray_text(widget)
    effect.setProperty(EFFECT_PROP, kind)
    widget.setGraphicsEffect(effect)  # deletes any effect FreeLab set before
    record["effect"], record["kind"] = effect, kind  # PythonQt deletes it if no Python reference is kept
    # Effects nest: each draws the widgets inside it that have an effect of their own as they come out
    # of it (the font window's ink effect had mapped its glyph cells' island a second time).
    if kind != "title":
        _protect(widget)
        if kind != "picker":
            _protect_effects_inside(widget, effect)
    if kind == "ink":
        _unswap_labels_inside(widget)


def _gray_text(widget):
    """Fields and selectors: drawn in grays before mapping (their light text's ClearType fringes)."""
    return (_class_name(widget) in GRAYSCALE_TEXT_CLASSES or widget.inherits("QLineEdit")
            or (_class_name(widget) == "QLabel" and _prop(widget, "objectName") in GRAYSCALE_TEXT_NAMES))


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
    # The copy may hold the dark palette's light text (the field took it before the island's light
    # palette reached it): give it the light look's text colors, which the island maps light.
    light = _island_palette()
    for name in ("Text", "WindowText", "ButtonText"):
        palette.setColor(getattr(QPalette, name), light.color(getattr(QPalette, name)))
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
        if "sci" in record:
            try:
                _restore_editor(widget, record)
            except Exception as exc:
                _note_error("editor", exc)
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


def _win_api(name):
    """A Windows DLL whose functions keep Python's interpreter lock while they run.

    ctypes.windll releases the lock during each call. SetWindowPos (and DWM)
    send messages to FontLab's own windows synchronously, so Qt runs event
    filters, PythonQt shells, and slots inside the call: Python code without the
    lock, which crashed FontLab in PyErr_SetObject the moment one of them looked
    up a missing attribute (seen on opening the "Update / Install Scripts" dialog).
    PyDLL keeps the lock; on 64-bit Windows its calling convention is the same.
    """
    import ctypes
    return ctypes.PyDLL(name)


def _process_windows():
    """Handles of this process's visible top-level windows (PythonQt cannot return winId())."""
    import ctypes
    from ctypes import wintypes
    user32 = _win_api("user32")
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
    dwm = _win_api("dwmapi")
    for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE - 1):
        if dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
            break
    _win_api("user32").SetWindowPos(handle, None, 0, 0, 0, 0, SWP_FLAGS)  # redraw the frame now


def _is_window(hwnd):
    import ctypes
    return bool(_win_api("user32").IsWindow(ctypes.c_void_p(hwnd)))


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
    _drop_stray_effect(widget)
    visible_unchecked = widget.isVisible() and _unchecked(widget)
    if visible_unchecked:
        widget.setProperty(CHECKED_PROP, _size_key(widget))  # sweeps need not queue it again at this size
    name = _class_name(widget)
    if name == "QtColorPicker":
        _frame_picker(widget)
        _set_effect(widget, _record(widget), "picker")
        _protect(widget)
        return
    if _left_alone(widget, name):
        _note_sheet_as_seen(widget)
        _protect(widget)
        return
    canvas = state["canvas"]
    if not canvas and is_content(widget):
        _note_sheet_as_seen(widget)  # "dark interface" mode: canvases, font cells, and previews keep FontLab's look
        _protect(widget)  # and the ink effect of the window around them must not map them (garbled cells)
        return
    if _in_hooked_island(widget):
        _hook_island(widget)  # FontLab's own painting inside a hooked island (the canvas's labels): mapped as it
        return
    if _island_ancestor(widget, canvas) is not None:
        _undo_widget(widget, keep_props=True, keep_placeholder=True)  # the island maps it as drawn in light mode
        _set_placeholder(widget)
        _show_original_icon(widget)
        _note_sheet_as_seen(widget)
        return
    kind = widget_kind(widget, canvas)
    if kind == "island":
        _island(widget)
        return
    _darken_sheet(widget)
    if widget.inherits("QsciScintilla"):
        _recolor_editor(widget)  # after its stylesheet: a repolish could reset QScintilla's defaults
    if kind is None and visible_unchecked and _shows_white_artwork(widget):
        visible_unchecked = False  # FontLab's logo: white on purpose, no effect (the ink effect blackened its edges)
    if _plain_input(widget):
        kind, visible_unchecked = None, False  # Fusion draws it from the dark palette: right as it is
    if kind is None and visible_unchecked:
        found = detect_light(widget)  # before its icons are mapped light
        found = LEGACY_KINDS.get(found, found)
        if found:
            widget.setProperty(ISLAND_PROP, found)
            kind = found
            if found == "island":
                _island(widget)
                return
    _darken_icons(widget)
    if widget.inherits("QAbstractButton") and _icon_has_white_artwork(_prop(widget, "icon")):
        _protect(widget)  # its white mark as it is: the dock's keyed effect turned the white middles dark
    if kind is None and visible_unchecked:
        found = detect_ink(widget)
        if found:
            widget.setProperty(ISLAND_PROP, found)
            kind = found
    if kind == "ink" and _native_ink_target(widget):
        _native_ink(widget)
    elif kind in ("ink", "edges", "title", "subpixel", "defringe"):
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
        if state.get("hooked") and full:
            _update_hooked(app)  # forgets islands FontLab deleted (their addresses may be reused)
        _hook_menus(todo)
        _enqueue(todo, "dark")
        if len(todo) > 200 and not full:
            _log("sweep %d queued %d (queue %d)" % (state["sweeps"], len(todo), len(state["queue"])))
    dark_title_bars(True)  # windows opened since the last sweep
    if full:
        _prune_relit()
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


def _hook_menus(widgets):
    """Darken a menu as it opens (QMenu.aboutToShow), not at the next sweep: a menu opened right
    after switching on, while thousands of widgets wait in the queue, flashed light. The hook stays
    connected (a menu is never hooked twice) and does nothing while dark mode is off."""
    for widget in widgets:
        try:
            if not widget.inherits("QMenu") or widget.property(MENU_HOOK_PROP) is not None:
                continue
            if widget.connect("aboutToShow()", _menu_hook(widget)) is not False:
                widget.setProperty(MENU_HOOK_PROP, True)
        except Exception as exc:
            _note_error("menu hook", exc)


def _menu_hook(menu):
    def shown():
        module = _module()
        if module is not None:
            module._on_menu_shown(menu)
    return shown


def _on_menu_shown(menu):
    state = _state()
    if not state["on"] or state.get("busy") or not _alive(menu):
        return
    state["busy"] = True  # the worker must not re-enter from a signal sent while processing
    try:
        for widget in [menu] + _descendants(menu):
            if widget.property(SEEN_PROP) is None or widget.property(QUEUED_PROP) == "dark":
                widget.setProperty(QUEUED_PROP, None)
                process(widget)
    except Exception as exc:  # a Qt signal handler must not raise
        _note_error("menu", exc)
    finally:
        state["busy"] = False


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

# ---------------------------------------------------------------------------
# Options: "content" (False: dark interface, FontLab's light glyphs and canvas)
# and "follow_windows" (dark while Windows apps are dark), in darkmode.json
# ---------------------------------------------------------------------------

THEME_WATCH_MS = 3000
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def content_setting(settings):
    """Whether glyph canvases, font cells, and previews go dark too (the older "canvas" key counts)."""
    return bool(settings.get("content", settings.get("canvas", True)))


def windows_is_dark():
    """True when Windows apps are set to dark (AppsUseLightTheme = 0); False when unknown."""
    if sys.platform != "win32":
        return False
    try:
        try:
            import winreg
        except ImportError:
            import _winreg as winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY)
        try:
            value = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        finally:
            winreg.CloseKey(key)
        return int(value) == 0
    except Exception:
        return False


def _theme_hook():
    module = _module()
    if module is not None:
        module._follow_windows()


def _follow_windows():
    """Timer, while following Windows: switch to match its app mode."""
    try:
        dark = windows_is_dark()
        if dark and not _state()["on"]:
            apply_dark()
        elif not dark and _state()["on"]:
            restore()
    except Exception as exc:  # a Qt timer callback must not raise
        _note_error("follow windows", exc)


def _watch_windows(follow):
    state = _state()
    state.setdefault("theme_watch", None)
    if follow:
        _start_timer(state, "theme_watch", THEME_WATCH_MS, _theme_hook)
    else:
        _stop_timer(state, "theme_watch")


# ---------------------------------------------------------------------------
# The native engine (darkmode/native/freelab_hooks.c)
# ---------------------------------------------------------------------------
# Two engines darken the islands, the surfaces FontLab paints itself in fixed light colors (the glyph
# canvas, font cells, previews, rulers): "script" gives each FontLab's light look and maps the pixels
# it drew, through a graphics effect; "native" maps the colors FontLab hands to Qt as it paints them,
# in the hooks library, before anything is drawn. Everything else (palette, Fusion, stylesheets,
# icons, title bars, editors, lists, the other effects) is the same in both. If the native engine cannot start (no library, another Qt build), the script engine runs.
ENGINES = ("script", "native")
HOOKS_VERSION = 17
PALETTE_GROUPS, PALETTE_ROLES = 3, 21


def engine_setting(settings):
    engine = settings.get("engine", "script")
    return engine if engine in ENGINES else "script"


def hooks_path():
    name = "freelab_hooks-v%d-%d.dll" % (HOOKS_VERSION, NATIVE_VERSION)  # both: a loaded library stays locked
    return os.environ.get("FREELAB_HOOKS_DLL") or os.path.join(state_dir(), "bin", name)


def _hooks():
    """The hooks library, loaded once per FontLab session (its import-table state lives in it), or None."""
    holder = _state()
    lib = holder.get("hooks_lib")
    if lib is not None and holder.get("hooks_lib_path") == hooks_path():
        return lib
    path = hooks_path()
    if not os.path.isfile(path):
        raise RuntimeError("the native engine's library is missing: %s (tools/install-fontlab.ps1 builds it)" % path)
    import ctypes
    lib = ctypes.PyDLL(path)  # keeps the interpreter lock: the wrappers never call back into Python
    if lib.freelab_hooks_version() != HOOKS_VERSION * 1000 + NATIVE_VERSION:
        raise RuntimeError("the native engine's library is another version")
    lib.freelab_hooks_init.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.freelab_hooks_add_module.argtypes = [ctypes.c_void_p]
    lib.freelab_hooks_set_palette.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.freelab_hooks_install.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    lib.freelab_hooks_set_hooked.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.freelab_hooks_set_ink.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.freelab_hooks_add_ink_module.argtypes = [ctypes.c_void_p]
    lib.freelab_hooks_set_subpixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double]
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    qtgui = kernel32.GetModuleHandleW(u"Qt5Gui.dll")
    virtual_protect = ctypes.cast(kernel32.VirtualProtect, ctypes.c_void_p).value
    qtwidgets = kernel32.GetModuleHandleW(u"Qt5Widgets.dll")
    if not qtgui or not qtwidgets or lib.freelab_hooks_init(qtgui, virtual_protect, qtwidgets) != 1:
        raise RuntimeError("Qt is not the build the native engine knows (Qt 5.14.2)")
    found = lib.freelab_hooks_add_module(kernel32.GetModuleHandleW(None))  # FontLab's own program
    if found not in (-2,) and found < HOOKS_MIN_FOUND:
        raise RuntimeError("FontLab's program imports only %d of the calls the native engine maps" % found)
    svg = kernel32.GetModuleHandleW(u"Qt5Svg.dll")
    if svg:  # FontLab draws some artwork (its logo) by handing an SVG to QSvgRenderer, which paints in Qt5Svg
        lib.freelab_hooks_add_module(svg)
    lib.freelab_hooks_add_ink_module(qtwidgets)  # its pens, for the lists' rows it draws (the ink viewports only)
    holder["hooks_lib"], holder["hooks_lib_path"] = lib, path
    return lib


HOOKS_MIN_FOUND = 25  # of 29: FontLab 7.2's program imports all of them


def _palette_table(palette):
    """A palette's colors as 0xAARRGGBB, groups (Active, Disabled, Inactive) by roles."""
    import ctypes
    QPalette = _gui("QPalette")
    table = (ctypes.c_uint32 * (PALETTE_GROUPS * PALETTE_ROLES))()
    groups = (QPalette.Active, QPalette.Disabled, QPalette.Inactive)
    for g, group in enumerate(groups):
        for role in range(PALETTE_ROLES):
            try:
                table[g * PALETTE_ROLES + role] = palette.color(group, role).rgba() & 0xffffffff
            except Exception:
                table[g * PALETTE_ROLES + role] = 0
    return table


NATIVE_SETTLE_MS = 15000  # the native engine counts as started once it has run this long
NATIVE_FELL_BACK = ("FreeLab dark mode: FontLab closed while the native engine was starting, so the script "
                    "engine runs instead. To try the native engine again, choose it in Scripts > FreeLab > "
                    "Dark Mode Settings.")


def _install_hooks(app):
    """Start the native engine: FontLab's palette reads answer light, its painting is mapped. True when on.

    A guard against a crash at start: darkmode.json holds native_pending from just before the hooks go
    in until the engine has run NATIVE_SETTLE_MS. Found at the next start, it means FontLab closed
    while the engine was starting (most likely a crash): the script engine runs from then on.
    """
    state = _state()
    if state.get("hooked"):
        # applied again while on (the re-applies after a switch, a sweep of settings): the hooks are
        # in; only the palette FontLab's code sees is brought up to date
        try:
            import ctypes
            dark, light = _palette_table(app.palette()), _palette_table(state["saved"]["palette"])
            state["hooked_lib"].freelab_hooks_set_palette(ctypes.addressof(dark), ctypes.addressof(light))
        except Exception as exc:
            _note_error("native engine", exc)
        return True
    settings = load_settings()
    # A mark this FontLab session set is its own start, still settling (state lives as long as FontLab
    # does); only one left by an earlier session means FontLab closed while the engine was starting.
    if settings.pop("native_pending", None) and not state.get("native_pending_mine"):
        settings["engine"] = "script"
        save_settings(settings)
        state["engine"] = "script"
        _note_error("native engine", "FontLab closed while it was starting; the script engine runs instead")
        print(NATIVE_FELL_BACK)
        return False
    settings["native_pending"] = True
    save_settings(settings)
    state["native_pending_mine"] = True
    try:
        lib = _hooks()
        import ctypes
        dark, light = _palette_table(app.palette()), _palette_table(state["saved"]["palette"])
        lib.freelab_hooks_set_palette(ctypes.addressof(dark), ctypes.addressof(light))
        lib.freelab_hooks_install(DARK_OKL, LIGHT_OKL, KEEP_TINT_CONTENT)
        state["hooked"], state["hooked_lib"] = True, lib
        state["hooked_addresses"], state["ink_addresses"] = [], []
        _update_hooked(app)
    except Exception as exc:
        _clear_native_pending()
        _note_error("native engine", exc)
        state["engine"] = "script"  # falls back: dark mode still works, through effects
        _remove_hooks(app)  # never both engines at once
        return False
    _repaint_all(app)
    _core("QTimer").singleShot(NATIVE_SETTLE_MS, _native_settled)
    return True


def _clear_native_pending():
    settings = load_settings()
    if settings.pop("native_pending", None):
        save_settings(settings)


def _native_settled():
    try:
        if _state().get("hooked"):
            _clear_native_pending()
    except Exception as exc:  # a Qt timer callback must not raise
        _note_error("native engine", exc)


def _island(widget):
    """An island: the native engine hooks one FontLab paints itself; otherwise (the script engine, or
    an item view, whose rows Qt draws) the script engine's light look and effect."""
    state = _state()
    if state.get("engine") == "native" and state.get("hooked") and _hookable(widget):
        _hook_island(widget)
    else:
        _make_island(widget)


def _child_widgets(widget):
    """The widgets inside `widget`, from its own children (not a scan of every widget, as
    _descendants does: a hooked island is met hundreds of times at start)."""
    found, pending = [], [widget]
    while pending:
        for child in pending.pop().children():
            try:
                if child.isWidgetType():
                    found.append(child)
                    pending.append(child)
            except Exception:
                pass
    return found


def _in_hooked_island(widget):
    """A widget of FontLab's own class (Qt's start with Q) inside a hooked island: the script engine's
    island effect covers it, so the hooks map it too."""
    if _class_name(widget).startswith("Q") or widget.property(HOOKED_PROP):
        return False
    if any(widget.inherits(base) for base in QT_DRAWN_BASES):
        return False
    state = _state()
    if state.get("engine") != "native" or not state.get("hooked"):
        return False
    current = widget
    while not current.isWindow():
        current = current.parentWidget()
        if current is None:
            return False
        if current.property(HOOKED_PROP):
            return True
    return False


def _hookable(widget):
    if widget.inherits("QAbstractItemView") or _class_name(widget) in SCRIPT_ISLAND_CLASSES:
        return False
    parent = widget.parentWidget()
    return not (parent is not None and parent.inherits("QAbstractItemView"))


def _hook_island(widget):
    """Leave the island's painting to the hooks: no light look, no effect. Qt still draws its
    stylesheet and icons, which are darkened as any widget's."""
    first = widget.property(HOOKED_PROP) is None
    _clear_effect(widget, _record(widget))  # an effect dark mode set before it was found in a hooked island
    widget.setProperty(HOOKED_PROP, True)
    _protect(widget)  # dark as it is painted: an effect around it (the font window's ink) must not map it again
    _darken_sheet(widget)
    _darken_icons(widget)
    if first:
        _enqueue([w for w in _child_widgets(widget) if _in_hooked_island(w)], "dark")
    state = _state()
    pointer = _sci_pointer(widget)
    if pointer and pointer not in state.setdefault("hooked_addresses", []):
        state["hooked_addresses"].append(pointer)
        _send_hooked(state)


def _update_hooked(app):
    """The hooked islands' addresses, rebuilt from the living widgets (FontLab deletes and makes
    windows; a deleted island's address may come back as another widget's)."""
    state = _state()
    if state.get("hooked_lib") is None or not state.get("hooked"):
        return
    addresses, inks = [], []
    for widget in app.allWidgets():
        try:
            hooked, ink = widget.property(HOOKED_PROP), widget.property(NATIVE_INK_PROP)
            if hooked or ink:
                pointer = _sci_pointer(widget)
                if pointer:
                    (addresses if hooked else inks).append(pointer)
        except Exception:
            pass
    if addresses != state.get("hooked_addresses"):
        state["hooked_addresses"] = addresses
        _send_hooked(state)
    if inks != state.get("ink_addresses"):
        state["ink_addresses"] = inks
        _send_ink(state)


def _native_ink_target(widget):
    state = _state()
    if state.get("engine") != "native" or not state.get("hooked"):
        return False
    parent = widget.parentWidget()
    if _prop(widget, "objectName") != "qt_scrollarea_viewport" or parent is None or not parent.inherits("QAbstractItemView"):
        return False
    delegates = [parent.itemDelegate()]
    model = parent.model()
    for column in range(min(model.columnCount() if model is not None else 0, 64)):
        delegates.append(parent.itemDelegateForColumn(column))
    return all(d is None or _class_name(d) in NATIVE_INK_DELEGATES for d in delegates)


def _native_ink(widget):
    """A list's viewport: its dark pens are mapped by the hooks, with no effect."""
    _clear_effect(widget, _record(widget))
    widget.setProperty(NATIVE_INK_PROP, True)
    _protect(widget)
    state = _state()
    pointer = _sci_pointer(widget)
    if pointer and pointer not in state.setdefault("ink_addresses", []):
        state["ink_addresses"].append(pointer)
        _send_ink(state)
    widget.update()


def _send_ink(state):
    import ctypes
    addresses = state["ink_addresses"]
    table = (ctypes.c_uint64 * max(1, len(addresses)))(*addresses)
    state["hooked_lib"].freelab_hooks_set_ink(ctypes.addressof(table), len(addresses))


def _send_hooked(state):
    import ctypes
    addresses = state["hooked_addresses"]
    table = (ctypes.c_uint64 * max(1, len(addresses)))(*addresses)
    state["hooked_lib"].freelab_hooks_set_hooked(ctypes.addressof(table), len(addresses))


def _remove_hooks(app):
    state = _state()
    if not state.get("hooked"):
        return
    state["hooked"] = False
    _clear_native_pending()  # switched off in order: no crash to guard against
    try:
        state["hooked_lib"].freelab_hooks_remove()
    except Exception as exc:
        _note_error("native engine", exc)
    _repaint_all(app)


def _repaint_all(app):
    try:
        _gui("QPixmapCache").clear()  # pixmaps drawn before (light, or dark) are drawn again
    except Exception:
        pass
    for widget in app.allWidgets():
        try:
            if widget.isVisible():
                widget.update()
        except Exception:
            pass


def native():
    """True when the native engine is the one running."""
    state = _state()
    return state["on"] and state.get("engine") == "native" and bool(state.get("hooked"))


def configure(dark=None, content=None, follow_windows=None, shade=None, engine=None):
    """Change the options and apply them now; None leaves an option as it is. Returns the settings."""
    settings = load_settings()
    old_content = content_setting(settings)
    old_shade = settings.get("shade", "dark")
    if shade is not None:
        settings["shade"] = shade if shade in SHADES else "dark"
    if dark is not None:
        settings["enabled"] = bool(dark)
    if content is not None:
        settings["content"] = bool(content)
        settings.pop("canvas", None)
    if follow_windows is not None:
        settings["follow_windows"] = bool(follow_windows)
    old_engine = engine_setting(settings)
    if engine is not None:
        settings["engine"] = engine if engine in ENGINES else "script"
    save_settings(settings)
    follow = bool(settings.get("follow_windows"))
    want_dark = windows_is_dark() if follow else bool(settings.get("enabled"))
    state = _state()
    if state["on"] and (not want_dark or content_setting(settings) != old_content
                        or settings.get("shade", "dark") != old_shade or engine_setting(settings) != old_engine):
        restore()  # a change of content mode, shade, or engine is rebuilt from scratch
    if want_dark and not state["on"]:
        apply_dark()
    _watch_windows(follow)
    return settings


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

INDICATOR_FRAME_DARK_BELOW = 0.5  # HLS lightness of the option's window color: a dark palette


def _framed_style(fusion):
    """Fusion, with a visible frame around check boxes and radio buttons.

    Fusion frames them a little darker than the window color, which vanishes on a dark
    palette; and some of FontLab's lists and property grids draw them with no widget,
    where no stylesheet can reach. A proxy style is the one place that sees them all. Its
    Python method runs for every primitive Qt draws, so it does as little as it can.
    Falls back to plain Fusion when PythonQt has no QProxyStyle.
    """
    state = _state()
    try:
        QProxyStyle = _gui("QProxyStyle")
    except AttributeError:
        return fusion
    classes = state.setdefault("style_classes", {})
    cls = classes.get(id(_module()))
    if cls is None:
        QStyle, QColor, QRectF, QPainter = _gui("QStyle"), _qt()[2], _core("QRectF"), _gui("QPainter")
        antialiasing, no_brush = QPainter.Antialiasing, _gui("QBrush")()  # an empty brush fills nothing
        check, radio = int(QStyle.PE_IndicatorCheckBox), int(QStyle.PE_IndicatorRadioButton)
        window_role = _gui("QPalette").Window

        class FreeLabStyle(QProxyStyle):
            def drawPrimitive(self, element, option, painter, widget=None):
                QProxyStyle.drawPrimitive(self, element, option, painter, widget)
                try:
                    which = int(element)
                    if which != check and which != radio:
                        return
                    if _sheet_styles_indicators(widget):
                        return  # FontLab's own images (blue boxes): a frame would show at their rounded corners
                    window = option.palette.color(window_role)
                    if _lightness(window.red(), window.green(), window.blue()) >= INDICATOR_FRAME_DARK_BELOW:
                        return
                    painter.save()
                    try:
                        painter.setRenderHint(antialiasing, True)
                        painter.setBrush(no_brush)
                        painter.setPen(QColor(INDICATOR_BORDER.get(_state().get("shade", "dark"), INDICATOR_BORDER["dark"])))
                        box = QRectF(option.rect).adjusted(0.5, 0.5, -1.5, -1.5)
                        if which == check:
                            painter.drawRoundedRect(box, 1.5, 1.5)
                        else:
                            painter.drawEllipse(box)
                    finally:
                        painter.restore()
                except Exception as exc:  # a paint path must never raise
                    _note_error("style", exc)

        cls = classes[id(_module())] = FreeLabStyle
    style = cls(fusion)
    state.setdefault("styles", []).append(style)  # Qt owns it once set; PythonQt would delete it if unreferenced
    return style


def _sheet_styles_indicators(widget, depth=8):
    """True when the widget or an ancestor has a stylesheet with indicator rules (images FontLab draws).
    (PythonQt cannot read a style option's state, so the stylesheet is what tells them apart.)"""
    current = widget
    while current is not None and depth > 0:
        if u"indicator" in (_prop(current, "styleSheet") or u""):
            return True
        current = current.parentWidget()
        depth -= 1
    return False


def _class_chain(obj):
    """Class names from obj's own up to QObject."""
    names = []
    try:
        meta = obj.metaObject()
        while meta is not None:
            names.append(str(meta.className()))
            meta = meta.superClass()
    except Exception:
        pass
    return names


def _keep_module(state):
    """Keep this version of the file referenced for as long as FontLab runs.

    Qt calls into every version that made something: the focus hook, the style watcher,
    the style, effects made before a reload, and the relight effects that switching off
    makes. A freed Python 2 module has its globals set to None, which broke them all
    ('NoneType' object is not callable), so switching off keeps its version too.
    """
    state["module"] = sys.modules.get(MODULE_NAME) or state.get("module")  # see _module()
    versions = state.setdefault("modules", [])
    if state["module"] is not None and all(m is not state["module"] for m in versions):
        versions.append(state["module"])


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
            # FontLab 7.2 holds a QProxyStyle subclass; whether it is the application style is not
            # known yet (switching to Fusion would drop it). Kept for diagnostics: status() shows it.
            "style_chain": _class_chain(app.style()),
        }
    state["saved"].setdefault("font", _gui("QFont")(app.font()))  # a state kept from before fonts were saved
    settings = load_settings()
    state["canvas"] = content_setting(settings)
    state["engine"] = engine_setting(settings)
    state["log"] = bool(settings.get("log", False))
    shade = set_shade(settings.get("shade", "dark"))
    state["shade"] = shade
    if not (state["on"] and _app_is_dark(app, QPalette)):  # a style change repolishes every widget: only when needed
        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            app.setStyle(_framed_style(fusion))
        app.setPalette(build_palette(QPalette, QColor))
        app.setFont(state["saved"]["font"])  # undoes the grayscale text smoothing an earlier version set
    state["on"] = True
    _keep_module(state)
    state["queue"][:] = [item for item in state["queue"] if item[0] == "dark"]  # switching off may not have finished
    if state["engine"] == "native":
        _install_hooks(app)  # falls back to the script engine when it cannot start
    _darken_preferences()  # a near-white workspace, which either engine maps to dark mode's canvas
    dark_title_bars(True)
    widgets = list(app.allWidgets())
    _enqueue([w for w in widgets if not w.isVisible()], "dark")
    _enqueue([w for w in widgets if w.isVisible()], "dark")  # visible ones first
    _start_timer(state, "sweeper", SWEEP_MS, _sweep)
    _hook_focus(app)  # stays connected; it does nothing while dark mode is off
    _hook_menus(widgets)


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
    if app is not None:
        _remove_hooks(app)
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
    _keep_module(state)  # its relight effects call into it
    _relight_editors(app)


def _relight_editors(app):
    """Editors FontLab made while dark mode was on took their paper from the dark palette, once:
    they would stay dark. Each gets a "relight" effect, which maps it light, until dark mode
    takes it over again (its "edges" effect replaces this one)."""
    relit = _state().setdefault("relit", [])
    for widget in app.allWidgets():
        try:
            parent = widget.parentWidget()
            if (parent is None or _class_name(widget) != "QWidget" or _class_name(parent) not in EDGES_PARENTS
                    or _prop(widget, "objectName") != "qt_scrollarea_viewport"):
                continue
            if widget.graphicsEffect() is not None or _prop(widget, "width") * _prop(widget, "height") <= 0:
                continue
            pixmap = widget.grab()
            if pixmap.isNull() or light_paper(pixmap, editor_margin(pixmap)):
                continue
            effect = _effect_classes()["map"]()
            effect.freelab_widget = widget
            effect.freelab_kind = "relight"
            effect.setProperty(EFFECT_PROP, "relight")
            widget.setGraphicsEffect(effect)
            relit.append(effect)  # PythonQt deletes an effect nothing in Python refers to
        except Exception as exc:
            _note_error("relight", exc)


def _prune_relit():
    """Forget relight effects Qt has deleted (dark mode replaced them, or the editor went away)."""
    state = _state()
    state["relit"] = [effect for effect in state.get("relit", []) if _alive(effect)]


def status():
    """A summary for diagnostics."""
    state = _state()
    kinds = [r.get("kind") for r in state["records"].values()]
    return {
        "version": VERSION, "on": state["on"], "queue": len(state["queue"]), "records": len(state["records"]),
        "islands": kinds.count("island"), "titles": kinds.count("title"), "native": _native() is not None,
        "canvas": state["canvas"], "engine": state.get("engine", "script"), "hooked": bool(state.get("hooked")),
        "errors": list(state["errors"][-10:]),
        "original_style": (state["saved"] or {}).get("style_chain"),
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
    """Called by FontLab's startup script: apply dark mode if it was left on, or if following Windows and it is dark."""
    settings = load_settings()
    follow = bool(settings.get("follow_windows"))
    if (windows_is_dark() if follow else settings.get("enabled")):
        apply_dark()
        schedule_reapply()
    _watch_windows(follow)


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
    if settings.get("follow_windows"):
        settings["follow_windows"] = False  # switching by hand stops following Windows
        _watch_windows(False)
        message += " (No longer following Windows: Scripts > FreeLab > Dark Mode Settings turns that back on.)"
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
