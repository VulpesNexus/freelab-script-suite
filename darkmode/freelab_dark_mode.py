#FLM: Dark Mode
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
    # Fonts panel: its rows, painted light. Left to the look at start, it was found an island or ink depending on
    # what it showed then (the fonts still opening); as ink, its text came out doubled and the style dot's letter
    # light (the owner's image 157, after a relaunch, 2026-11-26)
    "CIconView",
))
ISLAND_NAMES = frozenset((
    ("QListWidget", "historyList"),  # its selected row is painted light
    # Open Installed Fonts: each font's name on a pill its delegate paints; as ink, the names came out garbled
    # (seen in the survey of FontLab's dialogs, 2026-11-24, and clean as an island, tried live)
    ("QListWidget", "listFonts"),
    # Add Glyphs: its list of categories paints the selected row in a fixed light color, under text of the
    # palette's color (as ink, the text's edges came out rough and the selected row's text could not be read)
    ("YSelectableTree", "itemsList"),
))
# An island whose delegate takes its text's color from the palette: the color is set in its stylesheet too, since
# the palette an island is given does not outlast its stylesheet (read live, 2026-11-24: Add Glyphs' list still
# had the dark palette's light text, which the island's mapping then turned as dark as the list).
ISLAND_TEXT = {("YSelectableTree", "itemsList"): u"QTreeWidget{color:#000000;}"}
# The tool bar's checked tool: FontLab draws its blue icon on a light chip, and mapped with the bar, the icon's
# edges came out in light dots and gray (the owner, 2026-11-25: "selected tools look weird"). Over the bar's
# mapping, dark mode paints a dark chip of its own and the icon FontLab gives a checked tool, blue, as it is
# (draw_checked_tools). Not through the bar's stylesheet: a chip given there had edges, and moved the slant
# tool's icon up as it was checked (the owner, the same evening). Only the bar's tool buttons, which have its
# margin; the round buttons below have their own look.
CHECKED_TOOL_CHIP = "#3a3c40"
CHECKED_TOOL_ICON_SPREAD = 80  # a checked tool's icon pixel: strongly colored (FontLab's blue)
CHECKED_TOOL_FIND_PER_PAINT = 4  # unchecked tools whose icon's place is found in one paint of the bar
CHECKED_TOOL_ICON_L = 0.6  # an unchecked tool's icon pixel, on the bar as drawn: this dark at most (HLS)


def _dark_box(image):
    """(left, top) of the opaque pixels of a small QImage darker than CHECKED_TOOL_ICON_L, or None. Never raises."""
    try:
        QColor = _gui("QColor")
        left = top = None
        for y in range(image.height()):
            for x in range(image.width()):
                color = QColor.fromRgba(image.pixel(x, y))
                if color.alpha() < 128 or _lightness(color.red(), color.green(), color.blue()) >= CHECKED_TOOL_ICON_L:
                    continue
                left = x if left is None or x < left else left
                top = y if top is None or y < top else top
        return None if left is None else (left, top)
    except Exception:
        return None


# A document tab's close cross: FontLab draws it, while the mouse is over the tab, as a character in the application
# palette's text color, taken when the palette changes, not from the tab bar's own: the dark palette's light gray,
# on the tabs' white, came out nearly the tab's dark (the owner, November 25). A cross of dark mode's own, drawn where
# FontLab's was found, lagged FontLab's fading and its highlight under the mouse, and came out halved or missing (the
# owner's video, the same evening). So FontLab's own drawing is kept and made stronger: over the bar's mapping, each
# pixel of a tab's cross box gets the light color at the share of the way it goes from its tab's ground to the
# cross' color (draw_tab_crosses): the shape, its place, its fading, all FontLab's.
TAB_CROSS_COLOR = (212, 212, 212)  # the mouse on the cross
TAB_CROSS_DIM = (140, 140, 140)  # the mouse elsewhere on the tab: dimmer, as the owner liked FontLab's
TAB_CROSS_HIT = 7  # pixels from the cross' center: the mouse on it
TAB_CROSS_CENTER = 13  # pixels from a tab's left edge to its cross' center, as FontLab draws it
TAB_CROSS_PRESSED = (88, 88, 90)  # held down: a lighter rounded square under the cross
TAB_CROSS_SQUARE = 16
TAB_CROSS_PRESSED_SCALE = 0.8
TAB_CROSS_FROM = 4  # pixels from a tab's left edge: the box FontLab's cross is drawn in (its own: 8 to 17)
TAB_CROSS_SPAN = 14  # (the name starts at 18 at the nearest, the tab's padding)
TAB_CROSS_MIN_STEP = 3  # the cross' color this far from the tab's ground at least (mean of the channels)
TAB_CROSS_SLACK = 3  # a pixel past the cross' color by more is something else (FontLab's highlight under the mouse)


def _tab_cross_shares(image, cross):
    """Each pixel of a tab's cross box as [x, y, share]: how far it goes from the box's most frequent value (the
    tab's ground) toward `cross`, the cross' value (mean of the channels), for the pixels on the way. Empty when
    the box holds no cross. Never raises."""
    try:
        QColor = _gui("QColor")
        width, height = image.width(), image.height()
        values = []
        counts = {}
        for y in range(height):
            for x in range(width):
                color = QColor.fromRgb(image.pixel(x, y))
                value = (color.red() + color.green() + color.blue()) // 3
                values.append((x, y, value))
                counts[value] = counts.get(value, 0) + 1
        ground = max(counts, key=lambda v: counts[v])
        step = cross - ground
        if abs(step) < TAB_CROSS_MIN_STEP:
            return []
        shares = []
        for x, y, value in values:
            share = float(value - ground) / step
            if 0.0 < share <= 1.0 + float(TAB_CROSS_SLACK) / abs(step):
                shares.append([x, y, min(share, 1.0)])
        return shares
    except Exception:
        return []


def _colored_box(image):
    """(left, top) of the opaque, strongly colored pixels of a small QImage, or None. Never raises."""
    try:
        QColor = _gui("QColor")
        left = top = None
        for y in range(image.height()):
            for x in range(image.width()):
                color = QColor.fromRgba(image.pixel(x, y))
                if color.alpha() < 128:
                    continue
                if max(color.red(), color.green(), color.blue()) - min(color.red(), color.green(), color.blue()) \
                        >= CHECKED_TOOL_ICON_SPREAD:
                    left = x if left is None or x < left else left
                    top = y if top is None or y < top else top
        return None if left is None else (left, top)
    except Exception:
        return None
CHECKED_TOOL_ISLANDS = ("ToolbarPanel",)
CHECKED_TOOL_MARGIN = 5  # px left and right: the bar's buttons' own margin (QToolButton{margin:0 5 0 5;})
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


def swatch_rect(image, x, y, max_x):
    """The rectangle of the color at (x, y) in a QImage, found along its row (up to max_x) and its column: a picker's
    whole swatch. Kept as drawn: a picker painting its swatch wider than the square (Overlay Fonts', 21 by 18 pixels)
    had its edges mapped, and a black pick showed in a white frame (the owner's recording, November 26); colored picks
    kept their edges by their chroma only."""
    QRect = _core("QRect")
    color = image.pixel(x, y)
    left, right, top, bottom = x, x, y, y
    while left > 0 and image.pixel(left - 1, y) == color:
        left -= 1
    while right + 1 < max_x and image.pixel(right + 1, y) == color:
        right += 1
    while top > 0 and image.pixel(x, top - 1) == color:
        top -= 1
    while bottom + 1 < image.height() and image.pixel(x, bottom + 1) == color:
        bottom += 1
    return QRect(left, top, right - left + 1, bottom - top + 1)


PICKER_DARK_RING = 0x80  # the frame's pixels darker than this in every channel are dark mode's own


def dark_ring_image(image, rect):
    """A transparent QImage the size of `image` holding the dark pixels of the one-pixel ring around `rect` (dark mode's
    #55555a frame, PICKER_FRAME), to draw as they are: mapped again, they made a faint light edge that other color
    slots do not have (the owner's image 153). A picker's own light frame is left out (mapped), or None if none."""
    QImage = _gui("QImage")
    ring = QImage(image.width(), image.height(), QImage.Format_ARGB32)
    ring.fill(0)
    found = False
    x0, y0 = rect.x() - 1, rect.y() - 1
    x1, y1 = rect.x() + rect.width(), rect.y() + rect.height()
    for y in range(max(0, y0), min(image.height(), y1 + 1)):
        for x in range(max(0, x0), min(image.width(), x1 + 1)):
            if x0 < x < x1 and y0 < y < y1:
                continue  # (inside: the swatch)
            value = image.pixel(x, y)
            if value >> 24 and max((value >> 16) & 255, (value >> 8) & 255, value & 255) < PICKER_DARK_RING:
                ring.setPixel(x, y, value)
                found = True
    return ring if found else None
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
SWEEP_MS = 500  # how often to look for widgets FontLab created or showed (750 while a sweep cost 22 ms)
FULL_SWEEP_EVERY = 60  # every Nth sweep revisits every widget (replaced stylesheets, new icons): every 30 s
FOCUS_DRAIN_MS = 80  # a window that takes focus is darkened at once, up to this long, before it paints light
MAX_ERRORS = 50
NATIVE_VERSION = 157

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
SEPARATOR_PROP = "freelab_menu_separators"  # the stylesheet a menu's lighter separators were set as
SEPARATOR_LIGHTER = 190  # a menu separator's color: the window color this much lighter (Fusion's is hardly seen)
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
PICKED_PROP = "freelabPicked"  # a hooked island showing colors the user picked, drawn as they are (see PICKED_WIDGETS)
# A container whose own painting the native engine maps, its children left as they are (not an island: see
# _hook_frame). The dock's frame lines and the panels' backgrounds and title strips were effects, which drew the
# whole dock offscreen and mapped it at every repaint inside it: 132 ms for a panel's preview, 1 ms without
# (measured live, 2026-11-26).
FRAME_PROP = "freelabHookedFrame"
PROPS = (ID_PROP, SEEN_PROP, QUEUED_PROP, WATCHED_PROP, CHECKED_PROP, ISLAND_PROP, SHEET_PROP, DARK_SHEET_PROP, HOOKED_PROP, NATIVE_INK_PROP,
         PICKED_PROP, FRAME_PROP)

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
    return os.environ.get("FREELAB_PIXELS_DLL") or _built_or_beside(os.path.join(state_dir(), "bin", name), name)


def _built_or_beside(built, name, here=None):
    """A native library's path: the one the installer built (in FreeLab's own folder), else the one a release
    ships beside the scripts (a bin folder in Scripts\\FreeLab, for a copy dropped in with no installer run),
    else the built path again (where the messages say to look). Never raises."""
    try:
        if not os.path.isfile(built):
            here = here or os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
            beside = os.path.join(here, "bin", name)
            if os.path.isfile(beside):
                return beside
    except Exception:
        pass
    return built


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


HELP_CLASS = "QWhatsThat"  # Qt's window for What's This help


def _help_palette(app, palette):
    """What's This help given a palette of its own, the dark one with its shadow in the frame's color. Qt
    draws that window's frame in the tooltip text color, then dots in the shadow color over the frame's
    right and bottom sides: unseen on a light tooltip's black frame, a dashed edge on a dark one's light
    frame (the owner, November 23, image 22; read from a live one, November 24: #0e0e0f and #e0e0e0 by
    turns along the last row and column). Never raises."""
    try:
        QPalette = _gui("QPalette")
        own = QPalette(palette)
        own.setColor(QPalette.Shadow, palette.color(QPalette.ToolTipText))
        app.setPalette(own, HELP_CLASS)
    except Exception as exc:
        _note_error("help palette", exc)


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
                    darkest = getattr(lib, "freelab_gray_darkest", None)  # optional, as defringe is
                    if darkest is not None:
                        darkest.argtypes = [ctypes.c_void_p, ctypes.c_int64]
                        darkest.restype = None
                    gray_ct = getattr(lib, "freelab_gray_cleartype", None)  # optional, as defringe is
                    if gray_ct is not None:
                        gray_ct.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
                        gray_ct.restype = ctypes.c_int64
                    reground = getattr(lib, "freelab_reground", None)  # optional, as defringe is
                    if reground is not None:
                        reground.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
                        reground.restype = ctypes.c_int64
                    band_text = getattr(lib, "freelab_band_text", None)  # optional, as defringe is
                    if band_text is not None:
                        band_text.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
                        band_text.restype = ctypes.c_int64
                    pills = getattr(lib, "freelab_pills", None)  # optional, as defringe is
                    if pills is not None:
                        pills.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
                        pills.restype = ctypes.c_int64
                    reground_light = getattr(lib, "freelab_reground_light", None)  # optional, as defringe is
                    if reground_light is not None:
                        reground_light.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
                        reground_light.restype = ctypes.c_int64
                    state["native"] = (mapper, stats, collect, keyed, anchors, defringe, darkest, gray_ct, reground,
                                       band_text, pills, reground_light)
                else:
                    _note_error("native", "version mismatch")
            except Exception as exc:
                _note_error("native", exc)
    return state["native"]


def _address(image):
    import ctypes
    return ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))


ANCHOR_MODES = {"ink": 0, "all": 1, "relight": 2, "icon": 3, "subpixel": 4, "syntax": 5, "list": 6}


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


def _redraw_from(index, name, drawn, mapped):
    """`mapped` (a Format_ARGB32 QImage, the mapping of `drawn`) passed with `drawn` through the native helper's
    function at `index`, which draws some of its pixels again from `drawn`. Without it, `mapped` as it is."""
    native = _native()
    if native is None or len(native) <= index or native[index] is None:
        return mapped
    try:
        QImage = _gui("QImage")
        # copies of their own: an image converted to the format it has is shared with the one it came from, and
        # the helper's writes went to a buffer of the moment, not to the image returned (seen live, November 25)
        drawn = drawn.convertToFormat(QImage.Format_ARGB32).copy()
        mapped = mapped.convertToFormat(QImage.Format_ARGB32).copy()
        if drawn.width() != mapped.width() or drawn.height() != mapped.height():  # (ints: PythonQt's QSize has no
            return mapped                                                       # !=, and two always differed)
        native[index](_address(drawn), _address(mapped), mapped.width() * mapped.height(), mapped.width())
    except Exception as exc:
        _note_error(name, exc)
    return mapped


def reground_image(drawn, mapped, light=False):
    """`mapped` with the colored text of `drawn` drawn again in its own colors over the mapped paper (see
    freelab_reground); with `light`, light text too, and a sample drawn on a dark ground as it is (see
    freelab_reground_light, for REGROUND_LIGHT_WIDGETS only)."""
    if light:
        native = _native()
        if native is not None and len(native) > 11 and native[11] is not None:
            return _redraw_from(11, "reground light", drawn, mapped)
    return _redraw_from(8, "reground", drawn, mapped)


def pills_image(drawn, mapped):
    """`mapped` with each anchor's pill of `drawn` drawn again whole: its gray as mapped, plain, and its name from
    its coverage, so that nothing under the translucent pill shows across the name (see freelab_pills)."""
    return _redraw_from(10, "pills", drawn, mapped)


def band_text_image(drawn, mapped):
    """`mapped` with the light text on a strong color's band (a selected cell's name) drawn again from its
    coverage, in gray between the band and white (see freelab_band_text)."""
    return _redraw_from(9, "band text", drawn, mapped)


# Overlay Fonts' window (FontLab's ActionOverlay): each font's sample rows and preview in the color picked for it.
# Mapped, the colors changed (a dark red came out pink) and their edges broke into dots (the owner, November 25);
# its widgets' colored text is drawn again in its own colors over the mapping (reground_image).
REGROUND_WINDOWS = ("ActionOverlay",)
# Of those, the widgets that show the samples (the list's rows, by its viewport, and the preview): there, a light color
# picked is text too, and a sample FontLab drew on a dark ground is kept as drawn (the owner, November 26: #e7e3d7 came
# out hollow in the list and dark olive in the preview). Not the window's other widgets, whose light grays are
# borders and fields.
REGROUND_LIGHT_WIDGETS = ("FontPreviewWidget", "ActionOverlayList")  # (the class, or its parent's)
# Under the native engine, the same widgets show the colors as picked: the hooks map their grounds and FontLab's own
# grays, and leave the samples' fills and pictures as they are (the owner, November 26, image 152: a black pick shown
# white "feels like overreach"; images 150 and 151: white picks, white on the rows' white paper, came out hollow or not
# at all). The list's rows are FontLab's own painting, so its viewport is hooked too, not inked.
PICKED_WIDGETS = ("FontPreviewWidget", "YColorBar", "YOpacityBar")
# The color field and the opacity bar, left as FontLab paints them, kept its light look's sunken edge: a #808080 line
# along their top and left, light on the dark window (the owner's image 154). Hooked as picked surfaces, their pictures
# (the colors, the checkerboard) stay as they are and that line is drawn in dark mode's frame color.
PICKED_BARS = ("YColorBar", "YOpacityBar")
PICKED_LISTS = ("ActionOverlayList",)  # (by their viewports)


def _picked_surface(widget):
    """A widget of the Overlay window showing picked colors (PICKED_WIDGETS, or a PICKED_LISTS list's viewport)."""
    try:
        parent = widget.parentWidget()
        if _class_name(widget) not in PICKED_WIDGETS and not (
                parent is not None and _class_name(parent) in PICKED_LISTS
                and _prop(widget, "objectName") == "qt_scrollarea_viewport"):
            return False
        window = widget
        while window is not None and not window.isWindow():
            window = window.parentWidget()
        return window is not None and _class_name(window) in REGROUND_WINDOWS
    except Exception:
        return False


def _regrounds(effect):
    """Whether an effect's widget is in a window whose colored text keeps its colors (REGROUND_WINDOWS): "light" for
    REGROUND_LIGHT_WIDGETS, True for the window's others, False elsewhere. Asked once per effect. Never raises."""
    known = getattr(effect, "freelab_reground", None)
    if known is not None:
        return known
    try:
        widget = effect.freelab_widget
        window = widget.window()
        known = window is not None and _class_name(window) in REGROUND_WINDOWS
        if known:
            parent = widget.parentWidget()
            if _class_name(widget) in REGROUND_LIGHT_WIDGETS or (
                    parent is not None and _class_name(parent) in REGROUND_LIGHT_WIDGETS):
                known = "light"
    except Exception:
        known = False
    try:
        effect.freelab_reground = known
    except Exception:
        pass
    return known


def gray_cleartype_image(image):
    """A Format_ARGB32 copy of a QImage whose dark text's ClearType edges on a light ground are gray, before an
    island of the interface is mapped (see freelab_gray_cleartype). Without the native helper, unchanged."""
    image = image.convertToFormat(_gui("QImage").Format_ARGB32)
    native = _native()
    if native is not None and len(native) > 7 and native[7] is not None:
        try:
            native[7](_address(image), image.width() * image.height(), image.width())
        except Exception as exc:
            _note_error("gray cleartype", exc)
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


LIGHT_LABEL_MIN = 0.6  # a label's text this light (HLS lightness), on a parent this dark or darker,
DARK_PARENT_MAX = 0.4  # is drawn for the dark interface already
LABEL_DARK_SHARE = 0.8  # when this share of what lies beneath it is that dark too


def _color_lightness(color):
    name = color.name()  # "#rrggbb"
    return _lightness(int(name[1:3], 16), int(name[3:5], 16), int(name[5:7], 16))


def _light_text_label(widget):
    """A text label drawn from the dark palette: light text, no image, no colors of its own in its
    stylesheet or text, on a dark parent and dark ground. Right as drawn, it is protected from the
    ink effect around it, which mapped it among the whole window's colors: the font window's light
    gray "SEARCH HISTORY" and "BOOKMARKS" headers, too few pixels to weigh, were read as smoothing
    toward a white slot of its toolbar, and broke up."""
    if not widget.inherits("QLabel"):
        return False
    text = getattr(widget, "text", None)
    text = text() if callable(text) else text
    if not text or u"<" in text:
        return False  # (rich text brings colors of its own: the font window's selection count)
    pixmap = getattr(widget, "pixmap", None)
    pixmap = pixmap() if callable(pixmap) else pixmap
    if pixmap is not None and not pixmap.isNull():
        return False
    sheet = (_prop(widget, "styleSheet") or u"").lower()
    if "color" in sheet or "background" in sheet or "image" in sheet:
        return False
    QPalette = _qt()[1]
    parent = widget.parentWidget()
    if parent is None or _color_lightness(widget.palette.color(QPalette.WindowText)) < LIGHT_LABEL_MIN:
        return False
    if _color_lightness(parent.palette.color(QPalette.Window)) > DARK_PARENT_MAX:
        return False
    if not widget.isVisible():
        return False  # decided once shown: a hidden page's label may come to lie on a light badge
    try:
        geometry = _prop(widget, "geometry")
        key = (widget.palette.color(QPalette.WindowText).name(), geometry.width(), geometry.height(),
               _record(parent) and int(parent.property(ID_PROP)))  # the record gives the parent its id
    except Exception:
        return True
    record = _record(widget)
    cached = record.get("light_label")
    if cached is not None and cached[0] == key:
        return cached[1]  # sweeps revisit every label: the parent is grabbed again only when this changes
    result = _dark_ground(parent, geometry)
    record["light_label"] = (key, result)
    return result


def _dark_ground(parent, rect):
    """Whether the parent paints rect dark, read as the parent draws it without FreeLab's effect: a
    parent with the ink effect would show a light badge already mapped dark (grab draws a widget
    through its own effect), and the label on it would be kept light on the light badge."""
    effect = parent.graphicsEffect()
    paused = effect is not None and _ours(parent) and bool(_prop(effect, "enabled"))
    try:
        if paused:
            effect.setEnabled(False)
        try:
            image = parent.grab(rect).toImage()
        finally:
            if paused:
                effect.setEnabled(True)
        width, height = image.width(), image.height()
    except Exception:
        return True
    if not width or not height:
        return True
    samples = [image.pixel(x, y) for y in range(0, height, max(1, height // 4)) for x in range(0, width, max(1, width // 12))]
    dark = sum(1 for v in samples if _lightness((v >> 16) & 255, (v >> 8) & 255, v & 255) <= DARK_PARENT_MAX)
    return dark >= LABEL_DARK_SHARE * len(samples)


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
        # Its stylesheet was taken away since (a FreeLab dropdown is drawn as a label while it has one
        # choice, and is a plain dropdown again with two): the sheet remembered here made it pass for
        # a styled input ever after, and the ink effect garbled it.
        if widget.property(SHEET_PROP) is not None or widget.property(DARK_SHEET_PROP) is not None:
            widget.setProperty(SHEET_PROP, None)
            widget.setProperty(DARK_SHEET_PROP, None)
        return
    if sheet == widget.property(SEPARATOR_PROP):
        return  # a menu's lighter separators: drawn as set
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


WATCHER_REVISION = 4  # raised when the filter below learns another event: a session that loaded an older one
TAB_MOUSE_EVENTS = (2, 3, 5, 10, 11, 127, 128, 129)  # press, release, move, enter, leave, and the hover ones


def _on_tab_mouse(bar, kind):
    """A tab bar's mouse moved, entered, left, or was pressed: the bar repainted when the mouse comes onto a tab's
    close cross or leaves it, or presses it (see draw_tab_crosses). FontLab repaints a tab as the mouse enters
    it, not as it moves onto the cross within, so the cross kept the look of the moment the tab was entered.
    Never raises."""
    try:
        record = _record(bar)
        hot = None
        if kind not in (11, 128):  # (leave)
            mouse = bar.mapFromGlobal(_gui("QCursor").pos())
            k = bar.tabAt(mouse)
            if k >= 0:
                tab = bar.tabRect(k)
                cx, cy = tab.x() + TAB_CROSS_CENTER, tab.y() + tab.height() / 2.0
                on = abs(mouse.x() - cx) <= TAB_CROSS_HIT and abs(mouse.y() - cy) <= TAB_CROSS_HIT
                held = on and bool(int(_qt()[0].instance().mouseButtons()) & int(_core("Qt").LeftButton))
                hot = (k, on, held)
        if record.get("cross_hot") != hot:
            record["cross_hot"] = hot
            bar.update()
    except Exception as exc:
        _note_error("tab mouse", exc)


def _watcher():
    """The one event filter dark mode installs on watched widgets (a QTimer: PythonQt has no QObject to
    subclass). A module loaded again in the same session makes its own when the one the session holds is an
    older revision, which knew fewer events (the cursor's, November 25: the filter of the session's first
    module went on answering, and no canvas' cursor was ever replaced); the older one is kept referenced, as
    the widgets it is still installed on call it."""
    state = _state()
    if state.get("watcher") is None or state.get("watcher_revision") != WATCHER_REVISION:
        QTimer = _qt()[4]

        class StyleWatcher(QTimer):
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind in MOVE_GUARD_EVENTS and obj.property(MOVE_GUARD_PROP):
                        module = _module()
                        if module is not None:
                            return bool(module._on_guarded_mouse(obj, event, kind))
                    elif kind == STYLE_CHANGE_EVENT:
                        module = _module()
                        if module is not None:
                            module._on_style_change(obj)
                    elif kind == CURSOR_CHANGE_EVENT:
                        module = _module()
                        if module is not None:
                            module._fix_cursor(obj)
                    elif kind == PAINT_EVENT and obj.property(MARK_FLAG_PROP):
                        module = _module()
                        if module is not None:
                            module._on_flag_paint(obj)
                    elif kind in TAB_MOUSE_EVENTS and obj.inherits("QTabBar"):
                        module = _module()
                        if module is not None:
                            module._on_tab_mouse(obj, kind)
                except Exception as exc:  # an event filter must never raise
                    _note_error("watcher", exc)
                return False

        if state.get("watcher") is not None:
            state.setdefault("old_watchers", []).append(state["watcher"])
        app = _qt()[0].instance()
        state["watcher"] = StyleWatcher(app) if app is not None else StyleWatcher()  # (held: see _new_timer)
        state["watcher_revision"] = WATCHER_REVISION
    return state["watcher"]


def _watch(widget):
    """The widget watched by this revision's filter (WATCHED_PROP holds the revision that watches it; True was
    the first's)."""
    seen = widget.property(WATCHED_PROP)
    if seen == WATCHER_REVISION and seen is not True:
        return
    watcher = _watcher()
    if seen is not None:
        for old in _state().get("old_watchers", ()):
            try:
                widget.removeEventFilter(old)
            except Exception:
                pass
    widget.setProperty(WATCHED_PROP, WATCHER_REVISION)
    widget.installEventFilter(watcher)


def _unwatch(widget):
    if widget.property(MOVE_GUARD_PROP):
        return  # its mouse moves are still guarded, dark mode on or off
    if widget.property(WATCHED_PROP) is not None:
        widget.removeEventFilter(_watcher())
        for old in _state().get("old_watchers", ()):
            try:
                widget.removeEventFilter(old)
            except Exception:
                pass
        widget.setProperty(WATCHED_PROP, None)


# FontLab's own crash, guarded here whether dark mode is on or off: Overlay Fonts applies the color of its color
# bar (barColor) at each mouse move of a drag on it, and lets the event loop run while it does, so the next move
# is handled inside the one before. A quick drag nested about forty moves, some 26 KB of stack each, and the main
# thread's 1 MB overflowed (crash dumps of November 25, dark mode off, and November 26, on; the size of the font
# changes nothing). In the windows named here, a move that comes while one is handled is held back, and only the
# latest is handled once that one is over: one move at a time, the bar following the mouse as fast as FontLab
# applies a color.
MOVE_GUARD_WINDOWS = ("ActionOverlay",)
MOVE_GUARD_PROP = "freelab_move_guard"
MOUSE_MOVE_EVENT = 5
MOVE_GUARD_EVENTS = (2, 3, 4, 5)  # press, release, double click, move


def _guard_focus(now):
    """QApplication.focusChanged: a window named in MOVE_GUARD_WINDOWS has its widgets' moves guarded as it
    takes focus (again at each focus change in it, for widgets it made since). Never raises."""
    try:
        if now is None:
            return
        window = now.window()
        if window is None or _class_name(window) not in MOVE_GUARD_WINDOWS:
            return
        for widget in [window] + _descendants(window):
            if not widget.property(MOVE_GUARD_PROP):
                widget.setProperty(MOVE_GUARD_PROP, True)
            _watch(widget)
    except Exception as exc:
        _note_error("move guard", exc)


def _on_guarded_mouse(widget, event, kind):
    """A guarded widget's mouse event (see MOVE_GUARD_WINDOWS): True when it is held back. A move with a button
    held is sent again from here, so that what it leads to is known to be over when sendEvent returns; a move
    that comes meanwhile is held back, kept if it is the latest, and sent once that one is over. The same move
    passed on to a parent that ignored it goes on; a press or release drops a move held back before it."""
    moves = _state().setdefault("moves", {"busy": False, "pending": None, "passing": False, "at": None})
    if kind != MOUSE_MOVE_EVENT:
        moves["pending"] = None
        return False
    if moves["passing"]:
        moves["passing"] = False
        return False  # the move sent below
    if not int(event.buttons()):
        return False  # (no drag: as it is)
    screen = event.screenPos()
    if moves["busy"]:
        if moves["at"] == (screen.x(), screen.y()):
            return False  # the move being sent, passed on to a parent
        moves["pending"] = (widget, event.localPos(), screen, event.button(), event.buttons(), event.modifiers())
        return True
    app = _qt()[0].instance()
    QMouseEvent, QEvent = _gui("QMouseEvent"), _core("QEvent")
    move = (widget, event.localPos(), screen, event.button(), event.buttons(), event.modifiers())
    moves["busy"] = True
    try:
        while move is not None:
            target, local, screen, button, held, modifiers = move
            moves["pending"] = None
            moves["at"] = (screen.x(), screen.y())
            moves["passing"] = True
            try:
                app.sendEvent(target, QMouseEvent(QEvent.MouseMove, local, screen, button, held, modifiers))
            finally:
                moves["passing"] = False
            move = moves["pending"]
    finally:
        moves["busy"] = False
        moves["pending"] = None
        moves["at"] = None
    return True


# FontLab's own defect, mended here whether dark mode is on or off: the slant tool's picture for its checked state is
# drawn a pixel higher in its image than the unchecked one (16 by 17 both, read live on 2026-11-26; every other
# tool's two line up), so its icon jumps up as the tool is checked, in FontLab's light look too. The button is given
# the same icon with the checked picture moved to where the unchecked one is.
ALIGNED_ICONS = (("ToolbarPanel", "buttonSlant"),)
ALIGN_MAX_SHIFT = 2  # pixels: a larger gap between the two pictures is a drawing of its own, left alone


def _opaque_box(image):
    """(left, top, right, bottom) of a QImage's opaque pixels, or None."""
    QColor = _gui("QColor")
    left = top = right = bottom = None
    for y in range(image.height()):
        for x in range(image.width()):
            if QColor.fromRgba(image.pixel(x, y)).alpha() < 128:
                continue
            left = x if left is None or x < left else left
            right = x if right is None or x > right else right
            top = y if top is None or y < top else top
            bottom = y if bottom is None or y > bottom else bottom
    return None if left is None else (left, top, right, bottom)


def checked_shift(off_box, on_box):
    """(dx, dy) that moves the checked picture onto the unchecked one, when it is the same drawing shifted by at
    most ALIGN_MAX_SHIFT; None otherwise (nothing to mend, or not a shift)."""
    if off_box is None or on_box is None:
        return None
    dx, dy = off_box[0] - on_box[0], off_box[1] - on_box[1]
    if (dx, dy) == (0, 0) or abs(dx) > ALIGN_MAX_SHIFT or abs(dy) > ALIGN_MAX_SHIFT:
        return None
    if (off_box[2] - off_box[0], off_box[3] - off_box[1]) != (on_box[2] - on_box[0], on_box[3] - on_box[1]):
        return None
    return dx, dy


def _align_checked_icon(button):
    """The button given its icon with each checked picture moved onto the unchecked one (see ALIGNED_ICONS). True
    when it was changed; an icon already aligned is left as it is, so this can run again."""
    QIcon, QPixmap, QPainter = _gui("QIcon"), _gui("QPixmap"), _gui("QPainter")
    icon = _prop(button, "icon")
    if icon is None or icon.isNull():
        return False
    sizes = list(icon.availableSizes(QIcon.Normal, QIcon.Off))
    if not sizes:
        return False
    size = max(sizes, key=lambda s: s.width() * s.height())
    shift = checked_shift(_opaque_box(icon.pixmap(size, QIcon.Normal, QIcon.Off).toImage()),
                          _opaque_box(icon.pixmap(size, QIcon.Normal, QIcon.On).toImage()))
    if shift is None:
        return False
    aligned = QIcon()
    for mode in (QIcon.Normal, QIcon.Disabled, QIcon.Active, QIcon.Selected):
        for state in (QIcon.Off, QIcon.On):
            for each in icon.availableSizes(mode, state):
                picture = icon.pixmap(each, mode, state)
                if state == QIcon.On:
                    moved = QPixmap(picture.size())
                    moved.fill(_core("Qt").transparent)
                    painter = QPainter(moved)
                    try:
                        painter.drawPixmap(shift[0], shift[1], picture)
                    finally:
                        painter.end()
                    picture = moved
                aligned.addPixmap(picture, mode, state)
    button.setIcon(aligned)
    return True


def _align_icons(app):
    """FontLab's icons named in ALIGNED_ICONS mended, once a session (the tool bar is made at launch). Never raises."""
    state = _state()
    if state.get("icons_aligned"):
        return
    try:
        QToolButton = _gui("QToolButton")
        for widget in app.allWidgets():
            for owner, name in ALIGNED_ICONS:
                if _class_name(widget) != owner:
                    continue
                for button in widget.findChildren(QToolButton):
                    if button.objectName == name:
                        _align_checked_icon(button)
                        state["icons_aligned"] = True
    except Exception as exc:
        _note_error("icon alignment", exc)


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


LOGO_KEEP_CHROMA = 48  # max - min of the channels: a logo's colored part (its blue T, its teal O), kept as drawn
LOGO_PALE = 120  # a colored pixel with every channel this light or lighter is smoothing toward white


def _chroma(value):
    r, g, b = (value >> 16) & 255, (value >> 8) & 255, value & 255
    return max(r, g, b) - min(r, g, b)


def keep_colors(original, mapped):
    """mapped with original's clearly colored pixels put back (both Format_ARGB32, one size): a logo's
    colors are its own, its dark shading included (mapped as ink, a blue T's navy turned pale). Its
    edges were smoothed toward white: a paler pixel beside a colored one, on the picture's outline
    (beside a transparent pixel or the image's border), becomes that color, as transparent as it was
    mixed with white, so the edge is smooth on any row. A pale pixel inside the picture is its own
    (the white "?" of a message box's blue question icon), left as it is: cleaned too, it turned
    transparent and the "?" lost a pixel on each side."""
    width, height = min(original.width(), mapped.width()), min(original.height(), mapped.height())
    kept = set()
    for y in range(height):
        for x in range(width):
            value = original.pixel(x, y)
            darkest = min((value >> 16) & 255, (value >> 8) & 255, value & 255)
            if (value >> 24) & 255 and _chroma(value) >= LOGO_KEEP_CHROMA and darkest < LOGO_PALE:
                mapped.setPixel(x, y, value)
                kept.add((x, y))
    for y in range(height):
        for x in range(width):
            if (x, y) in kept:
                continue
            value = original.pixel(x, y)
            alpha = (value >> 24) & 255
            if not alpha:
                continue
            near = [original.pixel(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    if (x + dx, y + dy) in kept]
            if not near:
                continue
            outline = any(not (0 <= x + dx < width and 0 <= y + dy < height)
                          or not (original.pixel(x + dx, y + dy) >> 24) & 255
                          for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            if not outline:
                continue  # inside the picture: a white detail, not smoothing toward white
            color = max(near, key=_chroma)
            shares = []
            for shift in (16, 8, 0):
                c, v = (color >> shift) & 255, (value >> shift) & 255
                if 255 - c >= 40:
                    if v < c - 8:
                        shares = None  # darker than the color: no mix with white (another part of the logo)
                        break
                    shares.append(max(0.0, min(1.0, (255.0 - v) / (255.0 - c))))
            if not shares:
                continue
            share = sum(shares) / len(shares)
            mapped.setPixel(x, y, (int(round(share * alpha)) << 24) | (color & 0xffffff))
    return mapped


def dark_logo(icon, map_grays=True):
    """A logo (a picture in a list: Export Profiles' formats) mapped as icons are, its colors kept;
    without map_grays, only its colored edges cleaned of their smoothing toward white."""
    QIcon, QPixmap, QImage = _gui("QIcon"), _gui("QPixmap"), _gui("QImage")
    result = QIcon()
    sizes = list(icon.availableSizes()) or [_core("QSize")(32, 32)]
    for size in sizes:
        for mode in (QIcon.Normal, QIcon.Disabled, QIcon.Active, QIcon.Selected):
            for icon_state in (QIcon.Off, QIcon.On):
                pixmap = icon.pixmap(size, mode, icon_state)
                if pixmap.isNull():
                    continue
                original = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
                mapped = map_image(original, anchors="icon") if map_grays else original.copy()
                result.addPixmap(QPixmap.fromImage(keep_colors(original, mapped)), mode, icon_state)
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
    if _asked_to_be_left_alone(obj):
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
COLOR_PICTURE_SIDE = 32  # a colorful label image this large or larger (a message box's icon) is left as drawn too
# The font window's mark flag (a red flag on a black pole): its image is mapped by dark mode, and the
# ink effect around it draws it as mapped (protected). Left to the effect, as other labels inside it
# are, its pole stayed black: the effect read the thin black line beside the red as the flag's own.
# FontLab hands it a new image for each glyph's mark; a paint of an image not mapped yet swaps it.
MARK_FLAG_NAMES = ("labelMark",)
MARK_FLAG_PROP = "freelabMarkFlag"
PAINT_EVENT = 12


def _pixel_ratio(pixmap):
    """How many of a pixmap's pixels make one pixel of the interface, each way (1 for most)."""
    try:
        ratio = float(pixmap.devicePixelRatio())
    except Exception:
        return 1.0
    return ratio if ratio >= 1.0 else 1.0


def _swap_pixmap(label):
    state = _state()
    pixmap = _prop(label, "pixmap")
    if pixmap is None or pixmap.isNull() or pixmap.cacheKey() in state["mapped_keys"]:
        return
    # Its size as drawn: FontLab's warning dialogs (Coordinates Rounding) hold their 64-pixel question
    # mark at twice the size, for sharp screens. Counted in the image's own pixels, it passed for a
    # picture too large to be an icon, and kept its edge smoothed toward white: a light ring on dark.
    ratio = _pixel_ratio(pixmap)
    if pixmap.width() / ratio > MAX_ICON_SIDE or pixmap.height() / ratio > MAX_ICON_SIDE:
        return
    flag = (_prop(label, "objectName") or u"") in MARK_FLAG_NAMES
    if (not flag and max(pixmap.width(), pixmap.height()) / ratio >= COLOR_PICTURE_SIDE
            and not icon_is_gray(_gui("QIcon")(pixmap))):
        # A colorful picture (a message box's question mark): its colors as drawn, its edges smoothed toward
        # white cleaned (keep_colors), and drawn as that over any effect around it (mapped with the dialog,
        # or as drawn on dark, its edges were jagged)
        image = pixmap.toImage().convertToFormat(_gui("QImage").Format_ARGB32)
        clean = _gui("QPixmap").fromImage(keep_colors(image, image.copy()))
        if ratio != 1.0:
            clean.setDevicePixelRatio(ratio)
        state["mapped_keys"].add(clean.cacheKey())
        _record(label)["pixmap"] = pixmap
        label.setPixmap(clean)
        _protect(label)
        return
    if not flag and _under_ink(label):
        return  # the ink effect around it maps its image as drawn (see _unswap_labels_inside)
    new = dark_pixmap(pixmap)
    state["mapped_keys"].add(new.cacheKey())
    _record(label)["pixmap"] = pixmap
    label.setPixmap(new)
    if flag:
        _protect(label)  # drawn as mapped, not mapped again by an effect around it
        label.setProperty(MARK_FLAG_PROP, True)
        _watch(label)


def _on_flag_paint(label):
    """The mark flag paints: an image FontLab set since (another glyph's mark) is mapped in turn."""
    state = _state()
    if not state["on"]:
        return
    pixmap = _prop(label, "pixmap")
    if pixmap is not None and not pixmap.isNull() and pixmap.cacheKey() not in state["mapped_keys"]:
        QTimer = _qt()[4]
        QTimer.singleShot(0, lambda: _swap_pixmap(label) if _alive(label) else None)


def _under_ink(widget):
    """Inside a widget FreeLab's ink effect maps (within its window), with nothing between them that
    the effect draws unmapped: a protected widget (the defringe bar, a left-alone one), a hooked
    island, or a list the native ink paints keep their images as dark mode made them."""
    current = widget
    while not current.isWindow():
        current = current.parentWidget()
        if current is None:
            return False
        record = _record(current, create=False)
        if record is not None and record.get("kind") == "ink" and record.get("effect") is not None and _ours(current, record):
            return True
        if (record is not None and record.get("protected")) or _drawn_natively(current):
            return False
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
        if record.get("protected"):
            continue  # the mark flag: drawn as dark mode mapped it
        if not _under_ink(label):
            continue  # a protected widget between them: the effect draws it unmapped, the mapped image stays
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
    if _asked_to_be_left_alone(widget):
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
LOGO_MAX_ASPECT = 2  # wider than this many times its height, a list's picture is no logo: a line of text, mapped
# with its row (drawn from its icon in a logo's square, Overlay Fonts' sample text came out dark with light
# edges over its first letters: the owner, November 24)
LOGO_MIN_SIDE = 24  # a list icon drawn this large or larger is a picture (Export Profiles' formats are 32 px)


def _visible_columns(view, count, width):
    """The columns of a view that lie on its viewport (every column of a view that cannot say): a wide
    table under the ink effect asked the model for every column of every visible row on each paint."""
    if not hasattr(view, "columnViewportPosition") or not hasattr(view, "columnWidth"):
        return list(range(count))
    found = []
    for column in range(count):
        try:
            if hasattr(view, "isColumnHidden") and view.isColumnHidden(column):
                continue
            left = view.columnViewportPosition(column)
            if left < width and left + view.columnWidth(column) > 0:
                found.append(column)
        except Exception:
            return list(range(count))
    return found


def _logo_rects(view):
    """The viewport rectangles of the visible logo icons in a list (the style's decoration place:
    at the left of the cell, centered), for icons dark mode leaves as FontLab draws them."""
    return [rect for rect, _ in _logo_places(view)]


SELECTED_INK_SHARE = 0.01  # a selected row with more near-black pixels than this holds dark ink: mapped
SELECTED_LIGHT_SHARE = 0.5  # a selected row FontLab paints light itself (Preview Features' row under the pointer): mapped, as any light surface
SELECTED_ROWS_MAX = 200


def selected_as_painted(opaque, white, black):
    """Whether a selected row is drawn again as FontLab painted it, over the mapping: light text on the
    dark palette's highlight (Export Profiles). Not a row holding dark ink, and not a row FontLab
    paints light whatever the palette (Preview Features' row under the pointer, near-white with pale
    text: left as painted, it stayed a white band in a dark list)."""
    return bool(opaque) and black <= SELECTED_INK_SHARE * opaque and white <= SELECTED_LIGHT_SHARE * opaque


def _selected_rows(view, width, height):
    """The viewport rectangles of a list's visible selected rows (full width): the rows on screen are
    walked from the top, as _logo_places does, at most SELECTED_ROWS_MAX of them. A copy of the whole
    selection, made on every paint, was slow under a long table with everything selected, and its
    first indexes were not always the rows on screen."""
    QRect, QPoint = _core("QRect"), _core("QPoint")
    selection = view.selectionModel() if hasattr(view, "selectionModel") else None
    model = view.model()
    if selection is None or model is None or not _prop(selection, "hasSelection"):  # (a property in PythonQt)
        return []
    index = view.indexAt(QPoint(1, 1))
    tree = view.inherits("QTreeView")
    rows = []
    for _ in range(SELECTED_ROWS_MAX):
        if not index.isValid():
            break
        r = view.visualRect(index)
        if r.top() >= height:
            break
        if not r.isEmpty() and r.bottom() >= 0 and selection.rowIntersectsSelection(index.row(), index.parent()):
            rows.append(QRect(0, r.top(), width, r.height()).intersected(QRect(0, 0, width, height)))
        if tree:
            index = view.indexBelow(index)
        else:  # flat lists and tables: the next row of the model
            index = model.index(index.row() + 1, 0, index.parent())
    return rows


ICON_TILE_SHARE = 0.7  # of an icon's pixels opaque: a tile, not a line icon


def _icon_is_tile(icon):
    """Whether an icon is mostly opaque (a square tile, as the Font window's script icons). Never raises."""
    try:
        sizes = icon.availableSizes()
        if not sizes:
            return False
        image = icon.pixmap(sizes[0]).toImage()
        opaque, _white, _black = image_stats(image)
        return opaque >= ICON_TILE_SHARE * image.width() * image.height()
    except Exception:
        return False


def _logo_icon(icon, state):
    """The icon a list's logo is drawn from over its mapped row, or False for a line icon the row's
    mapping takes care of. A logo is a picture (LOGO_MIN_SIDE or larger), a swatch, or colorful. A
    gray picture (Export Profiles' TrueType and OpenType badges) is drawn from its mapped copy:
    left to the row's mapping, which also mapped the copy already put in the list, its edges came out
    jagged."""
    key = icon.cacheKey()
    mapped = key in state["mapped_keys"]
    sizes = icon.availableSizes()
    if any(s.width() > LOGO_MAX_ASPECT * s.height() for s in sizes):
        return False  # a line of sample text (Overlay Fonts' "AaGg123"), not a logo: the row's mapping draws it
    large = any(s.width() >= LOGO_MIN_SIDE for s in sizes)  # a picture, not a line icon
    if mapped:
        # dark already: its own smoothing, over the dark row. A small one too when it is a tile (the Font window's
        # script icons, light letters on a dark square): mapped again with the row, some tiles passed for dark
        # glyph icons and came out light gray under their light letters (Bengali, Kannada: the owner, 2026-11-25)
        return icon if large or _icon_is_tile(icon) else False
    if icon_is_swatch(icon):
        return icon  # as FontLab draws it
    if not icon_is_gray(icon):  # colorful: as drawn, its colored edges cleaned (smoothed toward white, ragged on dark)
        clean = state["icon_cache"].get(("clean", key))
        if clean is None:
            clean = state["icon_cache"][("clean", key)] = dark_logo(icon, False) if large else icon
        return clean
    if not large:
        return False
    dark = state["icon_cache"].get(key)
    if dark is None:
        dark = state["icon_cache"][key] = dark_logo(icon)
        state["mapped_keys"].add(dark.cacheKey())
        state["originals"][dark.cacheKey()] = icon
    return dark


def _logo_places(view):
    """[(viewport rectangle, QIcon)] of the visible logo icons in a list (see _logo_rects)."""
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
    columns = _visible_columns(view, model.columnCount(first.parent()), viewport.width)
    for _ in range(LOGO_ROWS_MAX):
        row_rect = view.visualRect(index)
        if not index.isValid() or row_rect.top() > viewport.height:
            break
        for column in columns:
            cell = model.index(index.row(), column, index.parent())
            icon = model.data(cell, Qt.DecorationRole)
            if icon is None or not hasattr(icon, "availableSizes") or icon.isNull():  # icons only (not pixmaps)
                continue
            key = icon.cacheKey()
            logo = logos.get(key)
            if logo is None:
                logo = logos[key] = _logo_icon(icon, state)
            if logo:
                r = view.visualRect(cell)
                rects.append((QRect(r.x() + margin, r.y() + (r.height() - size) // 2, size, size), logo))
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
            large = any(s.width() >= LOGO_MIN_SIDE for s in icon.availableSizes())  # a logo: its colors kept
            new = state["icon_cache"][key] = dark_logo(icon) if large else dark_icon(icon)
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
# Tables of small figures FontLab draws with ClearType on a light ground: mapped as ink, their digits kept
# orange and blue fringes on the dark cells (the Glyph window's metrics table: the owner, November 24). Drawn
# in grays before the mapping, as fields are.
GRAY_INK_CLASSES = ("MetricsTable",)
# (a slider too: Fusion draws its groove and handle from the dark palette, and taken for ink, Autotrace's
# handles came out light with ragged corners: the owner, November 24; not seen again here, Autotrace needing
# a picture in the glyph)
STYLE_DRAWN_BUTTONS = ("QRadioButton", "QCheckBox", "QPushButton", "QSlider")  # never ink by render detection
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


def darkest_gray_image(image):
    """The image in grays, each pixel the gray of its darkest channel (the native helper's
    freelab_gray_darkest: dark text as ClearType draws it comes out whole, its strokes even), or gray_image's
    where the helper cannot do it."""
    native = _native()
    darkest = native[6] if native is not None and len(native) > 6 else None
    if darkest is None:
        return gray_image(image)
    try:
        out = image.convertToFormat(_gui("QImage").Format_ARGB32)
        darkest(_address(out), out.width() * out.height())
        return out
    except Exception as exc:
        _note_error("darkest gray", exc)
        return gray_image(image)


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
                        edge_neutral=0.0, edge_target=0, anchors=None, dark_l=None, gray=False, analyze=None,
                        plain=False, defringe=False, cache=None, gray_ct=False, reground=False):
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

            def compute(part):
                drawn = part
                if gray:
                    part = gray_image(part)
                if gray_ct:
                    part = gray_cleartype_image(part)
                mapped = part if plain else map_image(part, min_l, keys, ink_below, keep_tint, light_l, edge_neutral,
                                                      edge_target, anchors, dark_l)
                if reground and not plain:
                    mapped = reground_image(drawn, mapped, light=reground == "light")
                if anchors == "all" and keep_tint > 0.0 and not plain:  # a canvas: a selected cell's name, anchors' pills
                    mapped = pills_image(drawn, band_text_image(drawn, mapped))
                return defringe_image(mapped) if defringe else mapped

            def signature(rect):
                return (rect.x(), rect.y(), rect.width(), rect.height(), min_l, tuple(keys or ()), ink_below, keep_tint,
                        light_l, edge_neutral, edge_target, anchors, dark_l, gray, plain, defringe, gray_ct, reground)

            if analyze is not None:
                analyze = analyze.intersected(QRect(offset, pixmap.size()))
                if analyze.contains(area) and not analyze == area:  # (PythonQt has no != for Qt's values: always true)
                    part = pixmap.copy(analyze.translated(-offset.x(), -offset.y())).toImage()
                    mapped = _cached_map(cache, signature(analyze), part, compute)
                    painter.drawImage(area.topLeft(), mapped, area.translated(-analyze.x(), -analyze.y()))
                    return
            part = pixmap.copy(area.translated(-offset.x(), -offset.y())).toImage()
            painter.drawImage(area.topLeft(), _cached_map(cache, signature(area), part, compute))

        class MapEffect(QGraphicsEffect):
            """Draw the widget with its colors mapped: by anchor blends (islands, ink, editors), or by key (frames)."""

            def draw(self, painter):
                # (timed: where a slow repaint's time goes is read from _paint_times when one is reported,
                # as the stall the owner saw when FontLab's blue drop highlight came up, November 24)
                began = time.time()
                depth = _DRAWING[0]
                if getattr(self, "freelab_drawing", False) or depth >= MAX_DRAW_DEPTH:
                    # Drawn again from inside its own drawing (an event loop run during a paint), or nested past
                    # any real nesting of effects: drawn as it is. Mapped, each level started the next, and the
                    # stack ran out as a color was dragged in Overlay Fonts (the owner, 2026-11-25: FontLab died
                    # after a few seconds; the stack held hundreds of nested message dispatches).
                    try:
                        self.drawSource(painter)
                    except Exception:
                        pass
                    return
                self.freelab_drawing = True
                _DRAWING[0] = depth + 1
                try:
                    hold = _paint_hold()
                    if hold is None or not self.draw_held(painter, hold):
                        self.paint_mapped(painter)
                finally:
                    _DRAWING[0] = depth
                    self.freelab_drawing = False
                    _paint_timed(self, (time.time() - began) * 1000.0)

            def draw_held(self, painter, hold):
                """The widget's picture held for this drag drawn (see HOLD_PIXELS): True when it was."""
                try:
                    box = self.sourceBoundingRect(Qt.LogicalCoordinates).toAlignedRect()
                    if _held_in_popup(hold, self.freelab_widget):
                        held_down = bool(int(_qt()[0].instance().mouseButtons()) & int(Qt.LeftButton))
                        if not (hold[0] == MODAL_HOLD and held_down and box.width() * box.height() >= MODAL_OWN_PIXELS):
                            return False
                        hold = (MODAL_OWN_HOLD, hold[1])  # (the dialog's own, while a color is dragged)
                    elif box.width() * box.height() < HOLD_PIXELS:
                        return False

                    def paint():
                        QImage, QPainter = _gui("QImage"), _gui("QPainter")
                        image = QImage(box.size(), QImage.Format_ARGB32_Premultiplied)
                        image.fill(Qt.transparent)
                        inner = QPainter(image)
                        try:
                            inner.translate(-box.x(), -box.y())
                            self.paint_mapped(inner)
                        finally:
                            inner.end()
                        return image
                    picture = _held_picture(self, hold, (box.x(), box.y(), box.width(), box.height()), paint)
                    painter.drawImage(box.topLeft(), picture)
                    return True
                except Exception as exc:
                    _note_error("held", exc)
                    return False

            def paint_mapped(self, painter):
                try:
                    pixmap, offset = source(self)
                    whole = QRect(offset, pixmap.size())
                    kind = self.freelab_kind
                    if kind == "keyed":
                        draw_mapped(painter, pixmap, offset, whole, self.freelab_min_l, self.freelab_keys, -1.0,
                                    self.freelab_keep_tint, None, 0.0, self.freelab_edge_target, cache=id(self))
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
                            else:
                                inside = inside.united(swatch_rect(image, probe_x, probe_y, min(
                                    pixmap.width(), pixmap.height() + PICKER_SWATCH_GAP)))
                                ring = dark_ring_image(image, inside)
                                if ring is not None:
                                    painter.drawImage(offset, ring)
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
                            image = _cached_map(id(self), ("defringe",), pixmap.toImage(), defringe_image)
                            painter.drawImage(area.topLeft(), image, area.translated(-offset.x(), -offset.y()))
                        keep_unmapped(self, painter, pixmap, offset)
                        return
                    anchors = {"island": "all", "subpixel": "subpixel"}.get(kind, "ink")
                    if kind == "ink" and getattr(self, "freelab_list", False):
                        anchors = "list"
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
                    logos, mapped_from = (logo_places(self), pixmap) if kind == "ink" else ([], pixmap)
                    if logos:
                        mapped_from = without_logos(pixmap, logos)
                    holes = kept_areas(self, pixmap, offset, KEPT_HOLE_PIXELS)
                    if holes:
                        mapped_from = without_kept(mapped_from, holes)
                    # A field or a selector drawn light on a dark ground already (its stylesheet's, or the dark
                    # palette's): grayed, never mapped. Mapped, so small a picture has no ground to judge by,
                    # and its text came out doubled and heavy (Actions' "Glyph" and "Baseline", a unit beside
                    # a field, text typed in the Glyph window's small fields: the owner, November 24).
                    plain = gray and kind == "ink" and dark_ground(pixmap)
                    draw_mapped(painter, mapped_from, offset, whole, 0.0, None, -1.0, self.freelab_keep_tint, None, 0.0, 0,
                                anchors, None, gray, QRect(whole) if kind in ("ink", "edges") else None, plain,
                                # A list's rows, a text view's lines: light text ClearType has drawn on the dark ground (dark by
                                # its stylesheet, or just mapped) keeps its blue and yellow edges through the
                                # mapping; they are made gray after it. Found by tools/find_fringes.py on a
                                # screenshot (Pairs & Phrases: 6,993 pairs of opposite hues, 4 after).
                                (kind == "ink" and bool(getattr(self, "freelab_view", False)))
                                # an island of the interface (no colors kept: not a canvas), the Fonts panel's
                                # list among them (5,240 pairs as drawn, 615 mapped, 233 defringed)
                                or (kind == "island" and not self.freelab_keep_tint),
                                cache=id(self) if not logos else None,
                                # the same island's dark text, drawn with ClearType on a light ground: its edges made
                                # gray before the mapping (see gray_cleartype_image)
                                gray_ct=kind == "island" and not self.freelab_keep_tint,
                                reground=_regrounds(self))
                    if kind == "ink" and getattr(self, "freelab_list", False):
                        # from the copy without logos: FontLab's logo, with its light fringe, showed through
                        # the cleaned logo's smoothing drawn over it
                        draw_selected(self, painter, mapped_from, offset)
                    if logos:
                        draw_logos(painter, pixmap, offset, logos)
                    keep_unmapped(self, painter, pixmap, offset)
                    if kind == "island" and self.freelab_keep_tint:
                        keep_pictures(self, painter, pixmap, offset)
                    if kind == "island" and _class_name(self.freelab_widget) in CHECKED_TOOL_ISLANDS:
                        draw_checked_tools(self, painter, pixmap, offset)
                    if kind == "island" and self.freelab_widget.inherits("QTabBar") \
                            and _prop(self.freelab_widget, "tabsClosable"):
                        draw_tab_crosses(self, painter, pixmap, offset)
                except Exception as exc:
                    _note_error("effect", exc)
                    self.drawSource(painter)

        def draw_selected(effect, painter, pixmap, offset):
            """A list's selected rows as Qt drew them, over the mapping: their highlight and light text
            are the dark palette's already, and mapped again the text's smoothing came out fringed
            (Export Profiles); ClearType's colored fringes made gray. A selected row with dark ink in it
            (FontLab's own colors) stays mapped."""
            view = effect.freelab_widget.parentWidget()
            if view is None or not view.inherits("QAbstractItemView"):
                return
            try:
                rows = _selected_rows(view, pixmap.width(), pixmap.height())
                if not rows:
                    return
                image = pixmap.toImage()
                for rect in rows:
                    part = image.copy(rect)
                    opaque, white, black = image_stats(part)
                    if selected_as_painted(opaque, white, black):
                        area = rect.translated(offset)
                        if painter.hasClipping():
                            area = area.intersected(painter.clipBoundingRect().toAlignedRect())
                        if not area.isEmpty():
                            # ClearType's fringes of the light text made gray (orange and blue around white letters)
                            source = area.translated(-offset.x(), -offset.y())
                            painter.drawImage(area.topLeft(), defringe_image(image.copy(source)))
            except Exception as exc:
                _note_error("list selection", exc)

        def logo_places(effect):
            """[(rect, icon)] of a list's logo icons (Export Profiles' formats), or [] (not a list, or failed)."""
            view = effect.freelab_widget.parentWidget()
            if view is None or not view.inherits("QAbstractItemView"):
                return []
            try:
                return _logo_places(view)
            except Exception as exc:
                _note_error("list logos", exc)
                return []

        def without_logos(pixmap, logos):
            """A copy of the source with each logo's place filled with the row's color beside it (its top
            left corner's pixel, the logo's margin): mapped, the row is whole, with no logo under the icons."""
            QPainter = _gui("QPainter")
            copy = pixmap.copy()
            image = pixmap.toImage()
            painter = QPainter(copy)
            try:
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                for rect, _ in logos:
                    x, y = max(0, rect.x() - 1), max(0, rect.y())
                    if 0 <= x < image.width() and 0 <= y < image.height():
                        painter.fillRect(rect, _gui("QColor").fromRgba(image.pixel(x, y)))
            finally:
                painter.end()
            return copy

        def draw_logos(painter, pixmap, offset, logos):
            """A list's logo icons drawn over the mapped rows, each from its own icon (its smoothing over
            the dark row, not over FontLab's light one: copied pixels brought a light fringe, jagged)."""
            for rect, icon in logos:
                area = rect.translated(offset).intersected(QRect(offset, pixmap.size()))
                if painter.hasClipping():
                    area = area.intersected(painter.clipBoundingRect().toAlignedRect())
                if area.isEmpty():
                    continue
                try:
                    painter.save()
                    painter.setClipRect(area)
                    icon.paint(painter, rect.translated(offset))
                    painter.restore()
                except Exception as exc:
                    _note_error("list logos", exc)

        def kept_areas(effect, pixmap, offset, min_pixels):
            """The areas (pixmap coordinates) of the protected descendants keep_unmapped draws as they are, of
            min_pixels or more: mapped, they are drawn over at once."""
            owner = effect.freelab_widget
            found = []
            for widget in list(getattr(effect, "freelab_protect", {}).values()):
                try:
                    if not _alive(widget) or widget is owner or not owner.isAncestorOf(widget) or not widget.isVisible():
                        continue
                    if _prop(widget, "width") * _prop(widget, "height") < min_pixels:
                        continue
                    corner = widget.mapTo(owner, QPoint(0, 0))
                    local = QRect(corner.x(), corner.y(), _prop(widget, "width"), _prop(widget, "height")).intersected(
                        QRect(QPoint(0, 0), pixmap.size()))
                    if local.isEmpty():
                        continue
                    record = _record(widget, create=False)
                    if record is not None and record.get("kind") == "ink" and light_ground(pixmap, local):
                        continue  # (left to the parent's mapping: see keep_unmapped)
                    found.append(local)
                except Exception:
                    continue
            return found

        def without_kept(pixmap, areas):
            """A copy of pixmap with areas cleared to transparent: the mapping passes over them at once, and
            reads no colors there (the Font window's ink effect mapped its whole cell chart, an island of its
            own drawn over it after: 2 s with overlaid fonts' colored glyphs, the owner, 2026-11-25)."""
            QPainter = _gui("QPainter")
            copy = QPixmap_copy(pixmap)
            painter = QPainter(copy)
            try:
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                for area in areas:
                    painter.fillRect(area, Qt.transparent)
            finally:
                painter.end()
            return copy

        def QPixmap_copy(pixmap):
            return pixmap.copy(QRect(QPoint(0, 0), pixmap.size()))

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
                if area.isEmpty():
                    continue
                local = area.translated(-offset.x(), -offset.y())
                record = _record(widget, create=False)
                if record is not None and record.get("kind") == "ink" and light_ground(pixmap, local):
                    # A selector or a field with an effect of its own, drawn on nothing, where its parent
                    # paints a light ground under it: left to the parent's mapping. Drawn as it is, the
                    # ground came with it: a white square in the corner of the Glyph window's metrics table
                    # (the owner, November 24). On a ground dark already (the Font window's bar) it is kept.
                    continue
                painter.drawPixmap(area.topLeft(), pixmap, local)

        def draw_checked_tools(effect, painter, pixmap, offset):
            """Each checked tool button of the bar: a dark chip, and its checked icon as FontLab gives it, over the
            bar's mapping (see CHECKED_TOOL_CHIP)."""
            QPainterPath, QToolButton, QIcon, QColor = (_gui("QPainterPath"), _gui("QToolButton"), _gui("QIcon"),
                                                        _gui("QColor"))
            QPainter = _gui("QPainter")
            owner = effect.freelab_widget
            unchecked_at = _state().setdefault("tool_icon_at", {})
            found = 0
            for button in owner.findChildren(QToolButton):
                try:
                    if not button.isVisible() or u"margin" not in (_prop(button, "styleSheet") or u""):
                        continue
                    if not button.isChecked():
                        # where FontLab draws the icon unchecked, found once per tool, a few a paint: FontLab draws
                        # a checked icon elsewhere for some (the slant tool's, a pixel up, in its light look too:
                        # the owner, November 25), and it is drawn checked where it was unchecked
                        if id(button) not in unchecked_at and found < CHECKED_TOOL_FIND_PER_PAINT:
                            found += 1
                            corner = button.mapTo(owner, QPoint(0, 0))
                            unchecked_at[id(button)] = _dark_box(pixmap.copy(QRect(
                                corner.x(), corner.y(), _prop(button, "width"), _prop(button, "height"))).toImage())
                        continue
                    corner = button.mapTo(owner, QPoint(0, 0))
                    width, height = _prop(button, "width"), _prop(button, "height")
                    local = QRect(corner.x() + CHECKED_TOOL_MARGIN, corner.y(), width - 2 * CHECKED_TOOL_MARGIN, height)
                    if local.width() <= 0:
                        continue
                    area = local.translated(offset)
                    path = QPainterPath()
                    path.addRoundedRect(_core("QRectF")(area), 5.0, 5.0)
                    size = _prop(button, "iconSize")
                    icon = _prop(button, "icon")
                    painter.save()
                    try:
                        painter.setRenderHint(QPainter.Antialiasing, True)
                        painter.fillPath(path, QColor(CHECKED_TOOL_CHIP))
                        if icon is not None and not icon.isNull():
                            picture = icon.pixmap(size, QIcon.Normal, QIcon.On)
                            x = corner.x() + offset.x() + (width - picture.width()) // 2
                            y = corner.y() + offset.y() + (height - picture.height()) // 2
                            # where FontLab drew it: its colored pixels in the button as painted (the slant tool's
                            # picture, 16 by 17, is scaled and placed a pixel off from plain centering, so the icon
                            # moved as it was checked: the owner, November 25)
                            drawn = _colored_box(pixmap.copy(QRect(corner.x(), corner.y(), width, height)).toImage())
                            before = unchecked_at.get(id(button))
                            if before is not None and drawn is not None and abs(before[0] - drawn[0]) <= 2 \
                                    and abs(before[1] - drawn[1]) <= 2:
                                drawn = before
                            own = _colored_box(picture.toImage())
                            if drawn is not None and own is not None:
                                x = corner.x() + offset.x() + drawn[0] - own[0]
                                y = corner.y() + offset.y() + drawn[1] - own[1]
                            painter.drawPixmap(QPoint(x, y), picture)
                    finally:
                        painter.restore()
                except Exception as exc:
                    _note_error("checked tool", exc)

        def draw_tab_crosses(effect, painter, pixmap, offset):
            """A document tab's close cross, light, over the bar's mapping, where FontLab drew its own (see
            TAB_CROSS_COLOR)."""
            QColor, QImage, QPainter = _gui("QColor"), _gui("QImage"), _gui("QPainter")
            app = _qt()[0].instance()
            bar = effect.freelab_widget
            text = app.palette().color(_gui("QPalette").WindowText)
            cross = (text.red() + text.green() + text.blue()) // 3
            mouse = bar.mapFromGlobal(_gui("QCursor").pos())
            held = bool(int(app.mouseButtons()) & int(Qt.LeftButton))
            for k in range(bar.count):
                try:
                    tab = bar.tabRect(k)
                    box = QRect(tab.x() + TAB_CROSS_FROM, tab.y(), TAB_CROSS_SPAN, tab.height())
                    if box.width() <= 0 or box.height() <= 0 or box.right() >= pixmap.width():
                        continue
                    shares = _tab_cross_shares(pixmap.copy(box).toImage(), cross)
                    if not shares:
                        continue
                    weight = sum(share for _, _, share in shares)
                    cx = box.x() + sum(x * share for x, _, share in shares) / weight + 0.5
                    cy = box.y() + sum(y * share for _, y, share in shares) / weight + 0.5
                    on = abs(mouse.x() - cx) <= TAB_CROSS_HIT and abs(mouse.y() - cy) <= TAB_CROSS_HIT
                    pressed = on and held
                    red, green, blue = TAB_CROSS_COLOR if on else TAB_CROSS_DIM
                    overlay = QImage(box.width(), box.height(), QImage.Format_ARGB32)
                    overlay.fill(0)
                    for x, y, share in shares:
                        overlay.setPixelColor(x, y, QColor(red, green, blue, int(round(255 * share))))
                    painter.save()
                    try:
                        painter.translate(offset.x() + cx, offset.y() + cy)
                        if pressed:
                            # held down: a lighter rounded square, and the cross a little smaller (the owner,
                            # November 25: the feedback FontLab's own gives as the cross is clicked)
                            painter.setRenderHint(QPainter.Antialiasing, True)
                            painter.setPen(Qt.NoPen)
                            painter.setBrush(QColor(*TAB_CROSS_PRESSED))
                            half = TAB_CROSS_SQUARE / 2.0
                            painter.drawRoundedRect(_core("QRectF")(-half, -half, 2 * half, 2 * half), 3.0, 3.0)
                            painter.scale(TAB_CROSS_PRESSED_SCALE, TAB_CROSS_PRESSED_SCALE)
                        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                        painter.drawImage(_core("QPointF")(box.x() - cx, box.y() - cy), overlay)
                    finally:
                        painter.restore()
                except Exception as exc:
                    _note_error("tab cross", exc)

        def keep_pictures(effect, painter, pixmap, offset):
            """The pictures of the glyphs a canvas shows, drawn as they are over its mapping (see
            _picture_rects): a scan or a screenshot turned over came out as a negative."""
            for rect in _picture_rects(effect):
                area = rect.translated(offset).intersected(QRect(offset, pixmap.size()))
                if painter.hasClipping():
                    area = area.intersected(painter.clipBoundingRect().toAlignedRect())
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
                            part = darkest_gray_image(part)  # (not the channels' mean: thin capitals came out uneven)
                            painter.drawImage(area.topLeft(), map_image(part, 0.0, None, -1.0, 0.0, None, 0.0, 0, "all"))
                except Exception as exc:
                    _note_error("title", exc)
                    self.drawSource(painter)

        _EFFECTS["map"] = MapEffect
        _EFFECTS["title"] = TitleEffect
    return _EFFECTS


# Large widgets' pictures held for the length of a drag. FontLab's blue drop highlight, as it comes up over
# the document area, makes every widget under it repaint, time after time, and Qt keeps no picture of a
# widget for its effect: each repaint drew the widget and mapped it anew (measured live, November 24: 111 ms
# for a font window of 1,715 by 1,329 pixels with its cell chart inside, and a window dragged over the main
# window stalled for 2.1 seconds each time the highlight came up; with dark mode off, no stall). While tab
# docking says a drag is on (sys._freelab_paint_hold, written at each step of a drag, which no longer
# counts once its time is past), a large widget is painted once and that picture drawn at each repaint. What
# changes inside one during the drag shows when the drag is over (_release_held).
HOLD_PIXELS = 150000  # smaller widgets are mapped in a millisecond or two: never held


def _paint_hold():
    """What large widgets' pictures are held for (any value that names it), or None: a drag tab docking
    follows, or an open menu or dropdown list (POPUP_HOLD and the popup's own identity). Never raises."""
    try:
        import sys
        hold = getattr(sys, "_freelab_paint_hold", None)
        if hold and time.time() < hold[1]:
            return hold[0]
        popup = _qt()[0].activePopupWidget()
        if popup is not None:
            return (POPUP_HOLD, id(popup))
        modal = _qt()[0].activeModalWidget()
        if modal is not None:
            return (MODAL_HOLD, id(modal))
    except Exception:
        pass
    return None


# While a menu or a dropdown list is open, the widgets under it are held too: FontLab repaints its windows as
# the mouse moves over a menu's entries, and each repaint drew and mapped a Font window anew (the owner,
# November 24: with many cells selected, "menus and such laggy and mostly unresponsive"). The popup's own
# widgets are never held: its rows change as the mouse moves.
POPUP_HOLD = "popup"
# While a modal dialog is open, the windows behind it cannot be scrolled or clicked, and FontLab repaints them as
# the dialog changes what they show: dragging a color in Overlay Fonts repainted the Font window's cells at each
# step, each drawn by FontLab and mapped anew, and FontLab stopped answering, then died (the owner, 2026-11-25;
# laggy with dark mode off too, less). Their large widgets are held as for a menu, and drawn again at most every
# MODAL_REFRESH seconds, and once after the last change, so they still follow the dialog. The dialog's own
# widgets are painted as ever.
MODAL_HOLD = "modal"
MODAL_REFRESH = 0.4
# While the mouse is held down in the modal dialog (a color dragged), its own large widgets are held too, drawn
# anew at most every MODAL_OWN_REFRESH seconds: each step's paints must end before FontLab's next step begins.
MODAL_OWN_HOLD = "modal-own"
MODAL_OWN_REFRESH = 0.15
MODAL_OWN_PIXELS = 40000  # (Overlay Fonts' list, 564 by 314, and preview, 552 by 161)
HOLD_REFRESH = {MODAL_HOLD: MODAL_REFRESH, MODAL_OWN_HOLD: MODAL_OWN_REFRESH}
# Effects drawing inside effects (a dock's, a panel's, a list's): never this deep but by re-entry (MapEffect.draw)
MAX_DRAW_DEPTH = 12
_DRAWING = [0]


def _held_in_popup(hold, widget):
    """Whether a widget is part of the popup or modal dialog its pictures would be held for (then it is painted
    as ever)."""
    try:
        if not (isinstance(hold, tuple) and hold and hold[0] in (POPUP_HOLD, MODAL_HOLD)):
            return False
        if hold[0] == MODAL_HOLD:
            modal = _qt()[0].activeModalWidget()
            return modal is None or widget is modal or modal.isAncestorOf(widget)
        popup = _qt()[0].activePopupWidget()
        return popup is None or widget is popup or popup.isAncestorOf(widget) or widget.window().inherits("QMenu")
    except Exception:
        return True


def _held():
    """{id(effect): (the drag, (x, y, width, height), the picture, the effect)}; on sys, to outlast a reload."""
    import sys
    found = getattr(sys, "_freelab_held", None)
    if found is None:
        found = sys._freelab_held = {}
    return found


def _held_picture(effect, hold, rect, paint):
    """The picture of an effect's widget for this drag: the one held, or paint() called and its result held."""
    held = _held()
    kept = held.get(id(effect))
    refresh = HOLD_REFRESH.get(hold[0]) if isinstance(hold, tuple) and hold else None
    now = time.time()
    if refresh is not None and _mouse_held():
        # A color dragged: not drawn anew until the mouse is let go. Drawn every 0.15 s, FontLab's drag still
        # nested its message handling inside the paints until it stopped answering and died (the owner, 2026-11-25;
        # it died once with dark mode off too): no widget of FontLab's is drawn for the effects during the drag.
        refresh = float("inf")
    if kept is None or kept[0] != hold or kept[1] != rect or (refresh is not None and now - kept[4] >= refresh):
        kept = held[id(effect)] = (hold, rect, paint(), effect, now, False)
    elif refresh is not None and not kept[5]:
        # a repaint asked for and not drawn: one more, once the refresh's time has come (the dialog's last change)
        held[id(effect)] = kept[:5] + (True,)
        try:
            wait = HOLD_REFRESH.get(hold[0], MODAL_REFRESH)
            _core("QTimer").singleShot(int(wait * 1000) + 50, _modal_refresh(effect))
        except Exception:
            pass
    return kept[2]


def _mouse_held():
    """Whether the left mouse button is down (a drag in a dialog). Never raises."""
    try:
        return bool(int(_qt()[0].instance().mouseButtons()) & int(_core("Qt").LeftButton))
    except Exception:
        return False


def _modal_refresh(effect):
    """A callback repainting an effect's widget held under a modal dialog, its next picture drawn anew; while the
    mouse is still held, asked again later."""
    def refresh():
        try:
            if _mouse_held():
                _core("QTimer").singleShot(int(MODAL_OWN_REFRESH * 1000), _modal_refresh(effect))
                return
            kept = _held().get(id(effect))
            if kept is not None:
                _held()[id(effect)] = kept[:4] + (0.0, False)  # (stale: drawn anew at the repaint)
            effect.update()
        except Exception:
            pass
    return refresh


def _release_held():
    """The held pictures let go once no drag is on, and their widgets repainted. Never raises."""
    try:
        held = _held()
        if not held or _paint_hold() is not None:
            return 0
        effects = [kept[3] for kept in held.values()]
        held.clear()
        for effect in effects:
            try:
                effect.update()
            except Exception:
                pass
        return len(effects)
    except Exception:
        return 0


# A large widget's repaint whose pixels are what they were at its last repaint (FontLab repaints its canvas, its
# cell chart, and its docks as a menu opens and closes, as the window is activated, as focus moves) is drawn
# from the mapping kept then: mapping the 1702 by 1134 glyph canvas took 50 ms each time, against 7 ms for
# FontLab to paint it, and opening a menu took 65 ms where light mode takes 13 (the owner, 2026-11-25: menus
# lag). Small widgets too: a panel's repaint remapped each of its hundreds of small ink effects (the main
# window's repaint: 74 ms, against 16 in light mode). Two images compare in about 1 ms for the canvas, far less
# for a button. Kept up to MAP_CACHE_PIXELS pixels (each kept twice, as drawn and as mapped), the least
# recently used let go first: two fonts with a Font window and a Glyph window each, and the docks, hold some
# 17.7 million (12 million made the windows evict each other at each tab switch: 600 ms where 300 do).
MAP_CACHE_PIXELS = 24000000
# A protected descendant this large (a cell chart, a canvas, a panel with its own effect inside a window's) is
# left out of its parent's mapping: kept_areas. Smaller ones (swatches, mark slots) are mapped as before.
KEPT_HOLE_PIXELS = 40000


def _map_cache():
    """{"entries": {key: [signature, source image, mapped image, pixels, last use]}, "pixels", "clock", "hits",
    "misses"}; on sys, to outlast a reload (its images are Qt's, keyed by effect and by everything the mapping
    was asked)."""
    import sys
    found = getattr(sys, "_freelab_map_cache", None)
    if found is None or not isinstance(found.get("entries"), dict):
        found = sys._freelab_map_cache = {"entries": {}, "pixels": 0, "clock": 0, "hits": 0, "misses": 0}
    return found


def _cached_map(key, signature, part, compute):
    """compute(part) as kept, when the same effect asked the same of the same pixels last time; else computed and
    kept. Never raises past compute's own errors."""
    if key is None:
        return compute(part)
    cache = _map_cache()
    entries = cache["entries"]
    cache["clock"] += 1
    entry = entries.get(key)
    if entry is not None:
        try:
            if entry[0] == signature and entry[1].size() == part.size() and entry[1] == part:
                cache["hits"] += 1
                entry[4] = cache["clock"]
                return entry[2]
        except Exception:
            pass
        cache["pixels"] -= entry[3]
        del entries[key]
    cache["misses"] += 1
    mapped = compute(part)
    pixels = part.width() * part.height()
    if pixels <= MAP_CACHE_PIXELS // 4:
        entries[key] = [signature, part, mapped, pixels, cache["clock"]]
        cache["pixels"] += pixels
        if cache["pixels"] > MAP_CACHE_PIXELS:
            for old_key, old in sorted(entries.items(), key=lambda item: item[1][4]):
                if cache["pixels"] <= MAP_CACHE_PIXELS * 3 // 4:
                    break
                cache["pixels"] -= old[3]
                del entries[old_key]
    return mapped


def _forget_map_cache():
    """The kept mappings let go (switching off, another theme). Never raises."""
    try:
        cache = _map_cache()
        cache["entries"].clear()
        cache["pixels"] = 0
    except Exception:
        pass


PAINT_SLOW_MS = 30.0  # a mapped repaint this long is kept in _paint_times' list
PAINT_KEPT = 60


def _paint_times():
    """The time dark mode's effects take to repaint: {"count", "ms", "slow": the last PAINT_KEPT repaints of
    PAINT_SLOW_MS or more, each (clock time, ms, class, name, width, height, kind)}. Kept on sys, so that it
    outlasts a reload."""
    import sys
    found = getattr(sys, "_freelab_paint_times", None)
    if found is None:
        found = sys._freelab_paint_times = {"count": 0, "ms": 0.0, "slow": []}
    return found


def _paint_timed(effect, ms):
    """One mapped repaint counted (_paint_times). Never raises: it runs inside a paint."""
    try:
        times = _paint_times()
        times["count"] += 1
        times["ms"] += ms
        if ms >= PAINT_SLOW_MS:
            widget = effect.freelab_widget
            times["slow"].append((time.strftime("%H:%M:%S"), int(ms), _class_name(widget), _prop(widget, "objectName"),
                                  _prop(widget, "width"), _prop(widget, "height"), effect.freelab_kind))
            del times["slow"][:-PAINT_KEPT]
    except Exception:
        pass


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


DARK_GROUND_L = 0.3  # a ground this dark needs no mapping (dark mode's own grays are darker)


LIGHT_GROUND_L = 0.6
LIGHT_GROUND_INSET = 3


def light_ground(pixmap, rect):
    """True when a rectangle of a picture stands on a light, opaque ground: three at least of four points just
    inside its corners (LIGHT_GROUND_INSET pixels in: at the very corners, a field with rounded corners shows
    what is under it, and a field drawn dark on a light canvas read as light and was mapped a second time).
    Never raises."""
    try:
        QColor = _gui("QColor")
        image = pixmap.toImage()
        light = 0
        inset = max(0, min(LIGHT_GROUND_INSET, (rect.right() - rect.left()) // 4, (rect.bottom() - rect.top()) // 4))
        for x, y in ((rect.left() + inset, rect.top() + inset), (rect.right() - inset, rect.top() + inset),
                     (rect.left() + inset, rect.bottom() - inset), (rect.right() - inset, rect.bottom() - inset)):
            if 0 <= x < image.width() and 0 <= y < image.height():
                color = QColor.fromRgba(image.pixel(x, y))
                light += color.alpha() >= 200 and _lightness(color.red(), color.green(), color.blue()) >= LIGHT_GROUND_L
        return light >= 3
    except Exception:
        return False


def dark_ground(pixmap):
    """True when a small widget's picture stands on a dark, opaque ground: three of its four corners at least
    (one may hold a letter's end or a frame's rounding). A transparent ground is none: its text is judged with
    what it stands on, by the mapping. Never raises."""
    try:
        QColor = _gui("QColor")
        image = pixmap.toImage()
        width, height = image.width(), image.height()
        if width < 4 or height < 4:
            return False
        dark = 0
        for x, y in ((1, 1), (width - 2, 1), (1, height - 2), (width - 2, height - 2)):
            color = QColor.fromRgba(image.pixel(x, y))
            dark += color.alpha() >= 200 and _lightness(color.red(), color.green(), color.blue()) < DARK_GROUND_L
        return dark >= 3
    except Exception:
        return False


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


# A text button FontLab paints itself, light whatever its stylesheet says (Replace Element's Elements and
# Glyphs: white, pale blue when checked), with its text in the color the stylesheet gives, which dark mode
# has made light: light on light, and mapped, dark on dark (the owner, November 24: "two bad buttons"). Its
# text is made dark by a rule of its own, so that it is the light button FontLab meant, and it is mapped
# whole, as an island.
BUTTON_INK = u"\nQToolButton{color:#000000;}"


# Icon buttons FontLab paints itself, white, and gray when checked (the Font window's five view buttons). Their
# icons were mapped for a dark face, the buttons kept as drawn for their white marks, and so they stood white
# in the dark bar, or dark once something else mapped them: "the only buttons that still keep stale painting"
# (the owner, November 24). One found white marks its siblings too: a checked one is gray when looked at.
LIGHT_FACE_PROP = "freelab_light_face"
LIGHT_FACE_SHARE = 0.6  # of its opaque pixels near white: a white face (a checked one, gray under a white icon: 0.37)


def _light_face_button(widget, look):
    """Whether a tool button is one FontLab paints white itself: marked so already, or (look: it may be
    rendered now) found white, its siblings with icons then marked with it and looked at again. Never raises."""
    try:
        if not widget.inherits("QToolButton"):
            return False
        if widget.property(LIGHT_FACE_PROP):
            return True
        icon = _prop(widget, "icon")
        if not look or icon is None or icon.isNull() or _class_name(widget) == "QtColorPicker":
            return False
        opaque, white, _black = image_stats(own_render(widget))
        if not opaque or white < LIGHT_FACE_SHARE * opaque:
            return False
        widget.setProperty(LIGHT_FACE_PROP, True)
        parent = widget.parentWidget()
        for sibling in (parent.children() if parent is not None else ()):
            if sibling is widget or not sibling.isWidgetType() or not sibling.inherits("QToolButton"):
                continue
            other = _prop(sibling, "icon")
            if other is None or other.isNull() or _class_name(sibling) == "QtColorPicker" or not _prop(sibling, "checkable"):
                continue
            sibling.setProperty(LIGHT_FACE_PROP, True)
            sibling.setProperty(CHECKED_PROP, None)  # (looked at again at the next sweep)
        return True
    except Exception:
        return False


def _own_sheet_ground(widget):
    """Whether the widget's own stylesheet sets a background for the widget itself, by its object name
    (QWidget#widgetButtons{background: ...}). Never raises."""
    try:
        name = _prop(widget, "objectName") or u""
        sheet = _prop(widget, "styleSheet") or u""
        if not name or u"#" + name not in sheet:
            return False
        return re.search(u"#" + re.escape(name) + u"\\s*\\{[^}]*background(-color)?\\s*:", sheet) is not None
    except Exception:
        return False


# Text Qt draws itself, outside any effect, gets Windows' ClearType: each stroke's sides in orange and blue,
# meant for dark text on light. On the dark interface they show as colored edges around every word of the
# menu bar, the buttons, the labels (the owner's most frequent complaint, November 24 and 25; counted with
# tools/find_fringes.py: 2,878 pairs of opposite hues on the main window, 807 once the menu bar and buttons
# went through an effect). Drawn through an effect, text gets grayscale smoothing, and the defringe effect
# makes what ClearType is left gray. Not a widget that paints a light face of its own (a tool button FontLab
# keeps white, mapped by the ink of the panel around it: drawn as it is, it stood white).
# Not text under an effect that maps it (an ink or island effect above it): its own effect would shield it from
# that mapping (see _set_effect), and dark text FontLab draws there would stay dark. Not a dropdown: Fusion
# draws it from the dark palette (see _plain_input), and its effect gained nothing (277 pairs before, 283 after).
UI_TEXT_CLASSES = ("QMenuBar", "QLabel", "QAbstractButton", "QGroupBox", "QTabBar")
UI_TEXT_LIGHT_SHARE = 0.25  # of its area near white: a light face
MAPPING_KINDS = ("ink", "island")


def _mapped_from_above(widget):
    """Whether an effect of a widget above this one (up to its window) maps what it draws. Never raises."""
    try:
        parent = widget.parentWidget()
        while parent is not None:
            if parent.property(ISLAND_PROP) in MAPPING_KINDS:
                return True
            record = _record(parent, create=False)
            if record is not None and record.get("kind") in MAPPING_KINDS and _ours(parent, record):
                return True
            if parent.isWindow():
                return False
            parent = parent.parentWidget()
        return False
    except Exception:
        return True


def _has_defringe(widget):
    """Whether the widget's effect is dark mode's defringe effect. Never raises."""
    try:
        record = _record(widget, create=False)
        return record is not None and record.get("kind") == "defringe" and _ours(widget, record)
    except Exception:
        return False


def _free_or_defringed(widget):
    """No effect yet, or dark mode's defringe effect already: looked at again (a full sweep processes every
    widget), a widget with the effect failed a test for "no effect", went on to the branches that take an effect
    off (left alone, a plain input), and lost it, to get it back at the next full sweep. Never raises."""
    try:
        return widget.graphicsEffect() is None or _has_defringe(widget)
    except Exception:
        return False


def _freelab_view_text(widget):
    """Whether a widget is the text area of a list or a text view in one of FreeLab's own windows, with no effect
    but the defringe one. Never raises."""
    try:
        if _prop(widget, "objectName") != "qt_scrollarea_viewport" or not _free_or_defringed(widget):
            return False
        parent = widget.parentWidget()
        if parent is None or not any(parent.inherits(c) for c in INK_VIEW_PARENTS):
            return False
        return _in_freelab_window(parent)
    except Exception:
        return False


TEXT_BOX_CLASSES = ("QTextEdit", "QPlainTextEdit")  # (QTextBrowser derives from QTextEdit)


def _freelab_text_box(widget):
    """Whether a widget is the text area of a text box (TEXT_BOX_CLASSES) in one of FreeLab's own windows. Never
    raises."""
    try:
        if _prop(widget, "objectName") != "qt_scrollarea_viewport":
            return False
        parent = widget.parentWidget()
        return parent is not None and any(parent.inherits(c) for c in TEXT_BOX_CLASSES) and _in_freelab_window(parent)
    except Exception:
        return False


def _in_freelab_window(widget):
    """Whether the widget is (in) one of FreeLab's own windows. Never raises."""
    try:
        window = widget  # (its window, as Qt's window(): the first widget up that is one)
        while window is not None and not window.isWindow():
            window = window.parentWidget()
        return window is not None and window.property(FREELAB_WINDOW_PROP) is not None
    except Exception:
        return False


def _freelab_text(widget):
    """Text in one of FreeLab's own windows to draw through the defringe effect, though it asked to be left alone:
    FreeLab asks for its tabs, buttons, and lists, drawn in the dialog's colors with nothing to map, and the
    defringe effect maps nothing (Font Check: 3,433 pairs of opposite hues left, on its tabs and check boxes,
    once its lists and labels had it; 1,278 once its tabs and buttons had it, on its dropdowns and fields). A
    dropdown, spin box, or field there takes it too: it maps nothing, so its arrows stay (see _plain_input).
    Never raises."""
    try:
        if _freelab_view_text(widget):
            return True
        if not _in_freelab_window(widget):
            return False
        if any(widget.inherits(c) for c in PLAIN_INPUTS):
            if not _free_or_defringed(widget):
                return False
            return _has_defringe(widget) or (widget.isVisible() and not _mapped_from_above(widget))
        return _ui_text_widget(widget)
    except Exception:
        return False


def _icon_only_button(widget):
    """A tool button that shows its icon alone (Qt::ToolButtonIconOnly, with an icon): its text, kept for its tooltip,
    is never drawn, so there is no text to defringe. 64 of FontLab's had the defringe effect, each drawn offscreen at
    every repaint for nothing (a tab switch to a Font window: 139 effect draws, 375 of its 505 ms; 2026-11-26).
    Never raises."""
    try:
        if not widget.inherits("QToolButton"):
            return False
        icon = _prop(widget, "icon")
        return int(_prop(widget, "toolButtonStyle")) == 0 and icon is not None and not icon.isNull()
    except Exception:
        return False


def _ui_text_widget(widget):
    """Whether a widget is text Qt draws on the dark interface, to be drawn through the defringe effect. Never
    raises."""
    try:
        if not any(widget.inherits(c) for c in UI_TEXT_CLASSES) or not _free_or_defringed(widget):
            return False
        if _icon_only_button(widget):
            return False
        if _has_defringe(widget):
            return True  # (decided before: not rendered again)
        if not widget.isVisible() or _mapped_from_above(widget):
            return False
        if not any(widget.inherits(c) for c in ("QMenuBar", "QTabBar", "QGroupBox")):
            text = _prop(widget, "text")
            if not text or not (u"%s" % text).strip():
                return False
        width, height = _prop(widget, "width"), _prop(widget, "height")
        if width * height <= 0:
            return False
        if widget.inherits("QLabel"):
            # Only light text on a dark ground, already shielded from any mapping above (see _light_text_label):
            # rich text, dark text, or a label on a light badge needs that mapping. A FreeLab window's label is drawn
            # from the palette, its rich text too (Font Check's summary, its numbers in bold: 14,053 pairs left)
            return not _shows_picture(widget) and (_freelab_caption(widget) or _light_text_label(widget))
        if not widget.inherits("QAbstractButton"):
            return True  # (only a button paints a face of its own: rendering each to see doubled the time
            # switching on takes, 15 s to 25 s with FontLab's windows open)
        _opaque, white, _black = image_stats(own_render(widget))
        return white < UI_TEXT_LIGHT_SHARE * width * height
    except Exception:
        return False


def _light_faced_text_button(widget):
    """A tool button with text and no icon whose text the palette makes light, found to paint light all the
    same (the caller's ink detection). Never raises."""
    try:
        if not widget.inherits("QToolButton") or not (_prop(widget, "text") or u"").strip():
            return False
        icon = _prop(widget, "icon")
        if icon is not None and not icon.isNull():
            return False
        return _color_lightness(widget.palette.color(_gui("QPalette").ButtonText)) >= LIGHT_LABEL_MIN
    except Exception:
        return False


def _dark_button_text(widget):
    own = _prop(widget, "styleSheet") or u""
    if own == widget.property(DARK_SHEET_PROP):
        return
    widget.setProperty(SHEET_PROP, own)
    widget.setProperty(DARK_SHEET_PROP, own + BUTTON_INK)
    widget.setStyleSheet(own + BUTTON_INK)


def _in_fontlab_view(widget):
    """Whether a widget is one of FontLab's own lists or its viewport (not a FreeLab tool's). Never raises."""
    try:
        if widget is None:
            return False
        view = widget if widget.inherits("QAbstractItemView") else widget.parentWidget()
        if view is None or not view.inherits("QAbstractItemView"):
            return False
        return view.window().property(FREELAB_WINDOW_PROP) is None
    except Exception:
        return False


# FontLab's cursors are never altered: they are drawn as FontLab has them, its black arrow and tools with their
# white glow, whatever the canvas. Dark mode once made copies for the dark canvas (the glow made a shadow, the
# arrow turned white with black edges), which looked inverted and bad (the owner, 2026-11-26: "they should
# probably be safeguarded to never be altered"). What remains only undoes such a copy, which an earlier version of
# dark mode may have left on a canvas in this FontLab session, at the canvas' next cursor change
# (CURSOR_CHANGE_EVENT) or as dark mode switches off.
CURSOR_CHANGE_EVENT = 183  # QEvent::CursorChange
BITMAP_CURSOR = 24  # Qt::BitmapCursor: a cursor made of a picture


def _fix_cursor(widget):
    """FontLab's own cursor back on the widget if an earlier version of dark mode replaced it; nothing else (a
    cursor is never altered). Never raises (it runs from an event filter)."""
    try:
        record = _record(widget)
        if "cursor" in record:
            _restore_cursor(widget, record)
    except Exception as exc:
        _note_error("cursor", exc)
    return False


def _restore_cursor(widget, record):
    """FontLab's own cursor back on a widget whose cursor is dark mode's copy. Never raises."""
    try:
        original = record.pop("cursor", None)
        if original is None:
            return
        cursor = widget.cursor() if callable(widget.cursor) else widget.cursor
        pixmap = cursor.pixmap() if int(cursor.shape()) == BITMAP_CURSOR else None
        if pixmap is not None and pixmap.cacheKey() in _state().get("cursor_keys", ()):
            widget.setCursor(original)
    except Exception as exc:
        _note_error("cursor", exc)


# A canvas' pictures (a scan or a screenshot placed in a glyph, to trace or to compare) are pixels like the rest
# of the canvas, and the canvas is mapped whole: a picture came out as its negative, and whatever FontLab draws
# over it with it (the owner, November 25: "inverted images also mess up with other stuff"). FontLab says where
# each picture is: an element whose image is not null, in the shown layer of each glyph of the canvas' text;
# the element's transform, the glyph's place in its line, and the canvas' own transform take it to the screen.
# Its area is drawn as it is, over the mapping, with what FontLab draws on it in its light colors.
PICTURE_RECTS_SECONDS = 0.15  # how long the places found are used before they are asked again (a repaint is often)
PICTURE_MAX_GLYPHS = 200  # glyphs of a canvas' text looked at


def _picture_rects(effect):
    """The rectangles (widget coordinates, QRect) of the pictures a canvas shows, or []. Asked of FontLab at most
    every PICTURE_RECTS_SECONDS. Never raises."""
    try:
        now = time.time()
        kept = getattr(effect, "freelab_pictures", None)
        if kept is not None and now - kept[0] < PICTURE_RECTS_SECONDS:
            return kept[1]
        rects = []
        try:
            rects = _find_picture_rects(effect.freelab_widget)
        except Exception as exc:
            _note_error("pictures", exc)
        effect.freelab_pictures = (now, rects)
        return rects
    except Exception:
        return []


def _find_picture_rects(widget):
    import fontlab
    QRectF = _core("QRectF")
    workspace = fontlab.flWorkspace.instance()
    canvas = workspace.getCanvasForViewport(widget)
    if canvas is None:
        return []
    found = []
    to_screen = canvas.transform
    for block in canvas.textBlocks():
        glyphs = block.getAllGlyphs()
        for index, info in enumerate(glyphs[:PICTURE_MAX_GLYPHS]):
            glyph = info.glyph
            if glyph is None:
                continue
            layer = glyph.activeLayer
            layer = layer() if callable(layer) else layer
            if layer is None:
                continue
            for shape in layer.shapes:
                image = shape.image
                if image is None or image.isNull():
                    continue
                rect = QRectF(0, 0, image.width(), image.height())
                rect = shape.transform.mapRect(rect)
                rect = block.getGlyphTransform(index).mapRect(rect)
                rect = to_screen.mapRect(rect)
                found.append(rect.toAlignedRect())
    return found


def _frame_picker(widget):
    own = _prop(widget, "styleSheet") or u""
    if own == widget.property(DARK_SHEET_PROP):
        return
    # (declarations with no selector, as Overlay Fonts' "color: lightGray;": followed by a rule, Qt reads
    # neither, the picker was drawn as a plain button from the dark palette, and its effect turned that light:
    # the owner, November 24, "the opacity dropdown still being white")
    framed = (u"QtColorPicker{%s}" % own if own.strip() and u"{" not in own else own) + PICKER_FRAME
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


def _asked_to_be_left_alone(obj):
    """The widget, or one of its ancestors within its window, carries LEAVE_ALONE_PROP (a FreeLab
    tool may mark a whole panel of previews). An action counts by its own property."""
    current = obj
    try:
        while current is not None:
            if current.property(LEAVE_ALONE_PROP):
                return True
            if not current.isWidgetType() or current.isWindow():
                return False
            current = current.parentWidget()
    except Exception:  # deleted meanwhile
        return False
    return False


def _left_alone(widget, name):
    return (name in SKIP_CLASSES or any(word in name for word in SKIP_CLASS_WORDS) or _asked_to_be_left_alone(widget)
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


FREELAB_WINDOW_PROP = "freelab_window"  # on a FreeLab tool's window (the shared module's WINDOW_PROP)


def _freelab_caption(widget):
    """A label of a FreeLab tool's window: drawn from the palette, so it has no fixed dark ink to map. One
    was taken for ink all the same (Font Builder's Ink darker than:, the owner, November 24: read live, it
    had the ink effect and the caption beside it had none), and text drawn through an effect loses
    ClearType: it looked blurrier than its neighbors. Never raises."""
    try:
        if not widget.inherits("QLabel"):
            return False
        window = widget.window()
        return window is not None and window.property(FREELAB_WINDOW_PROP) is not None
    except Exception:
        return False


def detect_ink(widget):
    """Render the widget alone and look for dark ink (after its icons are mapped: those need no effect)."""
    width, height = _prop(widget, "width"), _prop(widget, "height")
    if width * height < AUTO_MIN_AREA or widget.isWindow() or _shows_picture(widget):
        return None
    if _freelab_caption(widget):
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
    if widget.inherits("QSlider"):
        return None  # the style's (see STYLE_DRAWN_BUTTONS)
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
    # a list's rows (the font window's sidebar): drawn on nothing, gray sub-items and dark glyph icons are ink too
    parent = widget.parentWidget()
    effect.freelab_list = kind == "ink" and parent is not None and parent.inherits("QAbstractItemView")
    # a list's or a text view's own area (the Output panel's too): its text's colored edges are made gray
    # after the mapping (see draw_mapped's defringe)
    effect.freelab_view = kind == "ink" and parent is not None and any(parent.inherits(c) for c in INK_VIEW_PARENTS)
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


def _forget_effect(widget):
    """A widget dark mode now leaves as drawn: the effect and the kind it was given earlier go."""
    record = _record(widget, create=False)
    if record is not None and record.get("effect") is not None:
        _clear_effect(widget, record)
    if widget.property(ISLAND_PROP) is not None:
        widget.setProperty(ISLAND_PROP, None)


def _gray_text(widget):
    """Fields and selectors: drawn in grays before mapping (their light text's ClearType fringes)."""
    return (_class_name(widget) in GRAYSCALE_TEXT_CLASSES or _class_name(widget) in GRAY_INK_CLASSES
            or widget.inherits("QLineEdit")
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
    text_rule = ISLAND_TEXT.get((_class_name(widget), _prop(widget, "objectName")))
    if text_rule:
        combined = (combined + u"\n" + text_rule).strip()
    fill_rule = _chart_fill_rule(widget)
    if fill_rule:
        combined = (combined + u"\n" + fill_rule).strip()
    if combined != own:
        widget.setProperty(SHEET_PROP, own)
        widget.setProperty(DARK_SHEET_PROP, combined)
        widget.setStyleSheet(combined)
    else:
        _note_sheet_as_seen(widget)
    _set_effect(widget, record, "island")
    _fill_chart(widget, record)
    _enqueue(_descendants(widget), "dark")  # each undoes what dark mode did to it


FILLED_ISLANDS = ("FontCellChart", "CellChart")  # cell charts: they paint their cells and nothing between or after them


def _chart_fill_rule(widget):
    """The stylesheet rule that fills a cell chart in FontLab's light window color (which the chart's island
    effect maps to the dark one), or None for any other widget. In the stylesheet, since a color given through
    the palette does not outlast a repolish: a font window merged back into the main window came out with its
    room under the cells light (the owner, November 24; read live: the palette's window color back at the
    dark one after a repolish, which the effect then mapped light, and still the light one with this rule)."""
    try:
        name = _class_name(widget)
        if not _is_one_of(widget, name, FILLED_ISLANDS):
            return None
        return u"%s{background-color:%s;}" % (name, _state()["saved"]["palette"].color(_gui("QPalette").Window).name())
    except Exception:
        return None


def _fill_chart(widget, record):
    """A cell chart made to fill itself (its stylesheet's background, _chart_fill_rule, drawn by the style:
    WA_StyledBackground; Qt takes autoFillBackground off a widget whose stylesheet has a background). The
    chart paints its cells only: where a strip has fewer glyphs than it has room for (the glyph window's bar
    of glyphs), the light background of the widget behind showed through as a white band, since an effect
    leaves the place of an inner effect's widget unmapped (the owner, November 24; tried live: the band read
    #f4f4f4, and #2a2a2a, the bar's own, once the chart filled itself). Taken back with the island (the
    record's "styled"). Never raises."""
    try:
        if not _is_one_of(widget, _class_name(widget), FILLED_ISLANDS):
            return
        attribute = _core("Qt").WA_StyledBackground
        if "styled" not in record:
            record["styled"] = bool(widget.testAttribute(attribute))
        widget.setAttribute(attribute, True)
    except Exception as exc:
        _note_error("chart fill", exc)


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
        if "styled" in record:
            widget.setAttribute(_core("Qt").WA_StyledBackground, record.pop("styled"))
        if "tracking" in record:
            widget.setMouseTracking(record.pop("tracking"))
        if "font" in record:
            font = record.pop("font")
            widget.setFont(font if font is not None else _gui("QFont")())  # (empty: inherit again)
        record.pop("cross_hot", None)
        if "cursor" in record:
            _restore_cursor(widget, record)
        if "sci" in record:
            try:
                _restore_editor(widget, record)
            except Exception as exc:
                _note_error("editor", exc)
        _restore_icons(widget, record)
        _drop_record(widget, record)
    if widget.inherits("QMenu"):
        try:
            _restore_separators(widget)
        except Exception as exc:
            _note_error("menu separators", exc)
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
DWMWA_CAPTION_COLOR = 35  # Windows 11: a title bar's own color (earlier Windows refuses it, which is ignored)
DWMWA_COLOR_DEFAULT = 0xFFFFFFFF  # Windows' own color again
TITLE_BAR_PERCENT = 85  # a dark title bar's gray: its shade's window color at this much
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


def caption_color(dark=True):
    """The color asked of Windows for a title bar, as a COLORREF (0x00bbggrr): the shade's window gray, a
    little darker (TITLE_BAR_PERCENT), so that the bar stands apart from its window by the same step in
    both shades (the owner, November 23 and 24, images 28, 32, and 33: Windows' own dark bar was far from
    the medium shade's windows, and bluish against the dark shade's). Windows' own in light mode."""
    if not dark:
        return DWMWA_COLOR_DEFAULT
    palette = SHADES.get(_state().get("shade", "dark"), SHADES["dark"])[0]
    name = lighter_name(dict((entry[0], entry[1]) for entry in palette)["Window"], TITLE_BAR_PERCENT)
    red, green, blue = [int(name[i:i + 2], 16) for i in (1, 3, 5)]
    return red | (green << 8) | (blue << 16)


def _set_title_bar(hwnd, dark):
    import ctypes
    handle = ctypes.c_void_p(hwnd)
    value = ctypes.c_int(1 if dark else 0)
    dwm = _win_api("dwmapi")
    for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE - 1):
        if dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
            break
    color = ctypes.c_uint(caption_color(dark))
    dwm.DwmSetWindowAttribute(handle, DWMWA_CAPTION_COLOR, ctypes.byref(color), ctypes.sizeof(color))
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
        if dark and state.get("title_shade") != state.get("shade", "dark"):
            done.clear()  # (the shade changed: each title bar is given the new shade's color)
            state["title_shade"] = state.get("shade", "dark")
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

# Widgets never rendered to see what they paint. FontLab's blue drop highlight, made anew at each drag,
# grows over the document area step by step: at each size it was one not looked at yet, and was rendered and
# its pixels counted again, 82 ms each time, some 26 times: every drag of a window over the main window
# stalled for 2.1 to 2.2 seconds as the highlight came up (profiled live in the owner's drag, November 24:
# 4.6 of 7.4 seconds in ink_count). It paints a translucent blue and nothing to map.
NEVER_DETECTED = ("YDropHighlight",)


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
    first_look = visible_unchecked  # (kept: the rules below switch visible_unchecked off as they decide)
    if visible_unchecked:
        widget.setProperty(CHECKED_PROP, _size_key(widget))  # sweeps need not queue it again at this size
    name = _class_name(widget)
    if name in NEVER_DETECTED:
        visible_unchecked = False
    if name == "QtColorPicker":
        _frame_picker(widget)
        _set_effect(widget, _record(widget), "picker")
        _protect(widget)
        return
    if name in PICKED_BARS and _native_hooked() and _picked_surface(widget):
        _hook_island(widget)  # (color controls are left alone otherwise: see PICKED_BARS)
        return
    if _freelab_text_box(widget):
        # The text area of a FreeLab tool's text box (a Code preview, a log): no effect, the box's text smoothed in
        # grays. Through the defringe effect, colored code came out gray inside each letter, its color left only at
        # the edges (the owner's images 165 and 166, 2026-11-26): thin colored strokes are all edge pixels, which the
        # effect could not tell from ClearType's fringes. Drawn in grays, there are no fringes to take out.
        _forget_effect(widget)
        _gray_text(widget.parentWidget())
        _note_sheet_as_seen(widget)
        return
    if _freelab_text(widget):
        # A FreeLab tool's list, log, label, tab, or button, drawn by FreeLab from the dark palette: its text's
        # ClearType edges made gray by the defringe effect, which leaves every real color as drawn, so one that
        # asked to be left alone for its pictures takes it too (Font Check: 31,385 pairs of opposite hues before)
        _note_sheet_as_seen(widget)
        _set_effect(widget, _record(widget), "defringe")
        return
    if _left_alone(widget, name):
        _forget_effect(widget)  # one it got before it asked (a dropdown down to one choice)
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
    island = _island_ancestor(widget, canvas)
    if island is not None and widget.inherits("QLineEdit") and is_content(island):
        # A field FontLab puts on a canvas (the Glyph window's width and sidebearing fields, as they are
        # typed in): a field like any other, its stylesheet darkened and its text drawn in grays, kept out of
        # the canvas' mapping, which keeps colors and so kept ClearType's orange and blue around the digits
        # (the owner, November 24).
        island = None
    if island is not None:
        _undo_widget(widget, keep_props=True, keep_placeholder=True)  # the island maps it as drawn in light mode
        _set_placeholder(widget)
        _show_original_icon(widget)
        _note_sheet_as_seen(widget)
        return
    kind = widget_kind(widget, canvas)
    if kind == "island":
        _island(widget)
        if is_content(widget):
            _watch(widget)  # (a cursor an earlier dark mode replaced, given back: _fix_cursor)
            _fix_cursor(widget)
        elif widget.inherits("QTabBar"):
            _watch(widget)  # (its close crosses follow the mouse: _on_tab_mouse)
            record = _record(widget)
            if "tracking" not in record:  # (moves, not only entering and leaving: taken back with the island)
                record["tracking"] = bool(widget.hasMouseTracking())
                widget.setMouseTracking(True)
        return
    _darken_sheet(widget)
    if _own_sheet_ground(widget):
        # Its stylesheet gives it a ground of its own, dark now: kept out of the mapping of any effect above
        # it. Inside a table mapped as ink on its light paper, the dark block was ink, and came out light
        # (the three buttons at the right of the Glyph window's metrics table, in a light box: the owner,
        # November 25).
        _protect(widget)
    if widget.inherits("QsciScintilla"):
        _recolor_editor(widget)  # after its stylesheet: a repolish could reset QScintilla's defaults
    if kind is None and visible_unchecked and _shows_white_artwork(widget):
        visible_unchecked = False  # FontLab's logo: white on purpose, no effect (the ink effect blackened its edges)
    if _plain_input(widget):
        kind, visible_unchecked = None, False  # Fusion draws it from the dark palette: right as it is
        if not _has_defringe(widget):
            _forget_effect(widget)  # one it got while it had a stylesheet of its own (not its defringe effect)
    elif kind is None and _light_text_label(widget):
        _protect(widget)  # light text from the dark palette: no effect above may map it again
        visible_unchecked = False
    if kind is None and visible_unchecked:
        found = detect_light(widget)  # before its icons are mapped light
        found = LEGACY_KINDS.get(found, found)
        if found:
            widget.setProperty(ISLAND_PROP, found)
            kind = found
            if found == "island":
                _island(widget)
                return
    if _light_face_button(widget, kind is None and first_look):
        # FontLab paints it itself, white (gray when checked), whatever its stylesheet says: mapped as ink with
        # the icon FontLab gave it (see _light_face_button)
        record = _record(widget)
        if "icon" in record:
            widget.setIcon(record.pop("icon"))  # (the one mapped for a dark face goes)
        else:
            _show_original_icon(widget)
        widget.setProperty(ISLAND_PROP, "ink")
        _set_effect(widget, record, "ink")
        return
    _darken_icons(widget)
    if widget.inherits("QAbstractButton") and _icon_has_white_artwork(_prop(widget, "icon")):
        _protect(widget)  # its white mark as it is: the dock's keyed effect turned the white middles dark
    if kind is None and visible_unchecked:
        found = detect_ink(widget)
        if found:
            widget.setProperty(ISLAND_PROP, found)
            kind = found
    if kind is None and _ui_text_widget(widget):
        kind = "defringe"  # (see UI_TEXT_CLASSES)
    elif kind is None and _has_defringe(widget) and _icon_only_button(widget):
        _forget_effect(widget)  # (one an earlier version gave it: see _icon_only_button)
    if kind == "ink" and widget.property(ISLAND_PROP) == "ink" and _light_faced_text_button(widget):
        # (found to paint light, by either look above: see BUTTON_INK)
        _dark_button_text(widget)
        widget.setProperty(ISLAND_PROP, "island")
        _make_island(widget)
        return
    if kind == "ink" and _native_hooked() and _picked_surface(widget):
        _hook_island(widget)  # (a list's viewport whose rows FontLab paints: see PICKED_WIDGETS)
    elif kind == "ink" and _native_ink_target(widget):
        _native_ink(widget)
    elif (kind in FRAME_KINDS or (kind == "ink" and _ink_frame(widget))) and _native_hooked():
        _hook_frame(widget)  # (its own painting mapped at the source: see FRAME_PROP)
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
    """Timer: queue widgets FontLab created or showed since the last sweep.

    Every widget's wrapper is held (state["known"]): PythonQt makes a wrapper for each widget
    allWidgets() lists that Python does not hold yet, and frees it as the list goes. Held, the same
    wrappers come back each sweep, nothing is made or freed (live, November 15: about 2,000 wrappers made
    and freed each sweep before, of 4,754 widgets; FontLab's crashes of November 14 were PythonQt freeing
    a wrapper twice), and "seen before" is a lookup in Python rather than a Qt property read. A sweep
    took 22 ms, now about 8 (measured live, with nothing to queue), so it runs more often (SWEEP_MS) for
    less. The wrappers of deleted widgets, and dark mode's records of them, are let go on the full
    sweeps."""
    state = _state()
    if not state["on"] or state.get("busy"):
        return
    app = _qt()[0].instance()
    if app is None:
        return
    _release_held()
    state["sweeps"] += 1
    full = state["sweeps"] % FULL_SWEEP_EVERY == 0
    known = state.setdefault("known", {})
    todo = []
    for widget in app.allWidgets():
        key = id(widget)
        if key not in known:  # (a wrapper Python held not: a widget not listed before)
            known[key] = widget
            if widget.property(SEEN_PROP) is None:
                todo.append(widget)
                continue
        if full or (widget.isVisible() and (_unchecked(widget) or _restyled(widget))):
            todo.append(widget)
    if todo:
        if state.get("hooked") and full:
            _update_hooked(app)  # forgets islands FontLab deleted (their addresses may be reused)
        _hook_menus(todo)
        _enqueue(todo, "dark")
        if len(todo) > 200 and not full:
            _log("sweep %d queued %d (queue %d)" % (state["sweeps"], len(todo), len(state["queue"])))
    dark_title_bars(True)  # windows opened since the last sweep
    _follow_color_font(full)
    if full:
        _prune_relit()
        _prune_known(state)


def _prune_known(state):
    """The wrappers of deleted widgets let go, at a moment of dark mode's choosing (a full sweep), and
    dark mode's records of them. A deleted widget's wrapper frees nothing of Qt's."""
    known = state.get("known") or {}
    for key, widget in list(known.items()):
        if not _alive(widget):
            del known[key]
    for key, record in list(state["records"].items()):
        if not _alive(record["obj"]):
            del state["records"][key]


def _release_known(state):
    """The wrappers the sweeps held, let go (switching off, or on anew), but for those of widgets alive
    with no parent: those go to state["parentless"], held for the session. Such a widget may be one
    made from Python that its maker let go on purpose (another script's dialog, a probe's label):
    PythonQt deletes a widget made from Python once its last Python reference goes, and letting go of
    thousands of wrappers at once would delete them all at that moment, from inside this loop, the
    pattern of FontLab's crashes of November 14. They are few (FontLab's own windows among them, whose
    wrappers delete nothing), and never let go in bulk. A deleted widget's wrapper, or one with a
    parent (Qt's to delete), is let go."""
    known, state["known"] = state.get("known") or {}, {}
    kept = state.setdefault("parentless", [])
    held = set(id(widget) for widget in kept)
    for widget in known.values():
        try:
            if not _alive(widget) or widget.parentWidget() is not None:
                continue
        except Exception:
            continue
        if id(widget) not in held:
            kept.append(widget)
            held.add(id(widget))


COLOR_SAMPLE = 48  # glyphs looked at for SVG or bitmap pictures, after every glyph's color flag


def _color_font_key(package):
    """Which open font and master: FontLab's own number for the font (fgPackage.id, the same through
    every Python wrapper of it; two reads of currentPackage give two wrappers), its name, and the
    master. Two versions of one font (a mono and a color one) share the name and glyph count."""
    try:
        number = package.fgPackage.id
    except Exception:
        number = None
    return (number, getattr(package, "tfn", None), package.master)


def font_in_color(package, cache=None):
    """True for a font that draws in color: shapes with their own colors (COLR, as FontLab imports
    it), or pictures (SVG or bitmap glyphs). Every glyph is looked at, a long while for a large CJK
    font: with a cache (a dict), the answer is kept per open font and master until its glyph count
    changes. Each test fails on its own, and the glyphs are never indexed by position (indexing
    FontLab's native sequences crashed FontLab 8, beyond the reach of try)."""
    try:
        glyphs = package.fgPackage.glyphs
        count, master = len(glyphs), package.master
        key = _color_font_key(package)
    except Exception:
        return False
    if cache is not None and cache.get(key, (None,))[0] == count:
        return cache[key][1]
    step, names, colors, found = max(1, count // COLOR_SAMPLE), [], True, False
    try:
        for i, glyph in enumerate(glyphs):
            if i % step == 0:
                try:
                    names.append(glyph.name)
                except Exception:
                    pass
            if colors:
                try:
                    if glyph.hasColors():
                        found = True
                        break
                except Exception:
                    colors = False  # no color flag: the pictures are still looked for
    except Exception:
        pass
    if not found:
        try:
            for name in names:
                glyph = package.findName(name)
                layer = glyph.getLayerByName(master) if glyph is not None else None
                if layer is not None and any(shape.shapeType == "ShapeImage" for shape in layer.shapes):
                    found = True
                    break
        except Exception:
            pass
    if cache is not None:
        cache[key] = (count, found)
    return found


def _follow_color_font(full):
    """A color font's own rules: while it is the current font, the native engine draws its pictures
    and SVG glyphs as they are (what the user gets), mapping only what FontLab paints around them."""
    state = _state()
    lib = state.get("hooked_lib") if state.get("hooked") else None
    if lib is None:
        return
    try:
        import fontlab
        package = fontlab.flWorkspace.instance().currentPackage
        key = _color_font_key(package) if package is not None else None
    except Exception:
        return
    if key == state.get("color_font_key") and not full:
        return
    on = bool(package is not None and font_in_color(package, state.setdefault("color_fonts", {})))
    state["color_font_key"] = key
    if on != state.get("color_content", False):
        state["color_content"] = on
        lib.freelab_hooks_set_color_content(1 if on else 0)
        _log("a color font is %s" % ("current" if on else "no longer current"))
        _repaint_all(_qt()[0].instance())


def _module():
    """The current version of this module. FontLab may drop modules from sys.modules between script
    runs, and a Python 2 module that is no longer referenced has its globals set to None: every
    timer and effect would then fail. The state keeps a reference, refreshed by every apply."""
    return sys.modules.get(MODULE_NAME) or _state().get("module")


def _focus_hook(*args):
    """QApplication.focusChanged: a new window or tab usually takes focus as it opens."""
    module = _module()
    if module is not None:
        if len(args) > 1:
            module._guard_focus(args[1])
        if not _state().get("icons_aligned"):
            module._align_icons(_qt()[0].instance())
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


def lighter_name(name, factor):
    """#rrggbb with each channel times factor percent, at most 255 (QColor.lighter, for grays)."""
    channels = [int(name[i:i + 2], 16) for i in (1, 3, 5)]
    return u"#" + u"".join(u"%02x" % min(255, int(round(c * factor / 100.0))) for c in channels)


def separator_sheet(color_name, gutter=None):
    """The stylesheet a dark menu's separators are drawn with: a line of the given color, starting at the line
    beside the menu's ticks. (Only that:
    any rule more, a check mark's, made Qt draw the whole menu by the stylesheet, out of Fusion's look.)"""
    # (from the line beside the ticks to the right edge, as FontLab's light look has them: _menu_gutter)
    return u"QMenu::separator { height: 1px; background: %s; margin: 4px 8px 4px %dpx; }" % (
        color_name, MENU_GUTTER if gutter is None else gutter)


def _lighten_separators(menu):
    """Fusion draws a menu separator in a shade of the window color barely apart from it on a dark
    menu; a menu with no stylesheet of its own gets lighter ones (taken off again with dark mode)."""
    if menu.property(SEPARATOR_PROP) is not None or _prop(menu, "styleSheet"):
        return
    palette = _prop(menu, "palette")
    window = palette.color(_gui("QPalette").Window).name()
    # (a check mark drawn by an indicator rule here made Qt draw the whole menu by the stylesheet: no)
    # (the separators start where this menu's line beside the ticks is drawn, at its own scale: Codex,
    # 2026-11-23, a fixed 23 px against a line drawn at 34 on a display at 150 %)
    sheet = separator_sheet(lighter_name(window, SEPARATOR_LIGHTER), _gutter_offset(menu))
    menu.setProperty(SEPARATOR_PROP, sheet)
    menu.setStyleSheet(sheet)


def _restore_separators(menu):
    sheet = menu.property(SEPARATOR_PROP)
    if sheet is None:
        return
    if _prop(menu, "styleSheet") == sheet:
        menu.setStyleSheet(u"")  # else FontLab restyled it since: keep FontLab's
    menu.setProperty(SEPARATOR_PROP, None)


def _on_menu_shown(menu):
    state = _state()
    if not state["on"] or state.get("busy") or not _alive(menu):
        return
    state["busy"] = True  # the worker must not re-enter from a signal sent while processing
    try:
        try:
            _lighten_separators(menu)
        except Exception as exc:
            _note_error("menu separators", exc)
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


def _timer_slot(name):
    """A timer's slot: the function of that name in the version of this module loaded now. Uses only
    what its closure holds, so a timer kept across reloads calls the current version."""
    modules, holder = sys.modules, sys

    def slot():
        state = getattr(holder, "_freelab_dark_mode", None) or {}
        module = modules.get(MODULE_NAME) or state.get("module")
        if module is not None:
            getattr(module, name)()
    return slot


def _new_timer(name=None):
    """A timer whose parent is FontLab's application, so PythonQt never deletes it (it deletes a timer
    made from Python with no parent the moment its last Python reference goes, even while that timer
    emits: the worker stopping itself in its own timeout did that). Dark mode keeps its timers and
    starts them again rather than making new ones; Qt deletes them with the application."""
    QApplication, QTimer = _qt()[0], _qt()[4]
    app = QApplication.instance()
    timer = QTimer(app) if app is not None else QTimer()
    if name is not None:
        _connect_timeout(timer, _timer_slot(name))
    return timer


def _kept_timers(state):
    """Every timer dark mode made, held for the session: never let go, so never PythonQt's to delete."""
    return state.setdefault("kept_timers", {})


def _start_timer(state, key, interval, callback):
    """Start the timer of that key (made once, kept: _new_timer) unless it runs; callback is a function of
    this module, called through _timer_slot."""
    if state.get(key) is not None:
        return
    kept = _kept_timers(state)
    timer = kept.get(key)
    if timer is None or not _alive(timer):
        timer = kept[key] = _new_timer(callback.__name__)
    timer.setInterval(interval)
    timer.start()
    state[key] = timer


def _stop_timer(state, key):
    """Stop the timer of that key; state[key] goes back to None, but the timer stays held (kept_timers):
    this may run inside that very timer's timeout (the worker stops itself)."""
    timer = state.get(key)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
        kept = _kept_timers(state)
        if kept.get(key) is not timer:  # (one an earlier version made, parentless: held for the session)
            state.setdefault("retired_timers", []).append(timer)
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
HOOKS_VERSION = 37
PALETTE_GROUPS, PALETTE_ROLES = 3, 21


def engine_setting(settings):
    """The engine chosen, native unless the pixel ("script") engine was (the owner, 2026-11-26: the canvas's marks,
    each recognized after the fact by the pixel rules, never came out right together; the pixel engine is the
    fallback, and what runs wherever the hooks do not reach)."""
    engine = settings.get("engine", "native")
    return engine if engine in ENGINES else "native"


def hooks_path():
    name = "freelab_hooks-v%d-%d.dll" % (HOOKS_VERSION, NATIVE_VERSION)  # both: a loaded library stays locked
    return os.environ.get("FREELAB_HOOKS_DLL") or os.path.join(state_dir(), "bin", name)


NATIVE_QT_VERSION = "5.14.2"  # the Qt the native engine's wrappers were written against (MSVC, 64-bit)


def _qt_runtime_version():
    """The version of the Qt5Core.dll loaded in this process, from its own qVersion() (an undecorated C
    export), or None."""
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        handle = kernel32.GetModuleHandleW(u"Qt5Core.dll")
        if not handle:
            return None
        function = ctypes.PyDLL("Qt5Core.dll", handle=handle).qVersion
        function.restype = ctypes.c_char_p
        return function().decode("ascii", "replace")
    except Exception:
        return None


def native_build_problem(version, pointer_bytes):
    """Why this process is not the build the native engine knows, or None. Checked: a 64-bit process and
    Qt's own version, exactly; then (freelab_hooks_init, freelab_hooks_add_module) the MSVC-decorated Qt
    exports and FontLab's imports it hooks. Not checked: the compiler a same-version Qt was built with,
    or its object layouts beyond that (docs/NATIVE.md)."""
    if pointer_bytes != 8:
        return "the native engine needs a 64-bit FontLab"
    if version != NATIVE_QT_VERSION:
        return "Qt is %s, not the build the native engine knows (Qt %s)" % (version or "of an unknown version",
                                                                          NATIVE_QT_VERSION)
    return None


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
    problem = native_build_problem(_qt_runtime_version(), ctypes.sizeof(ctypes.c_void_p))
    if problem:  # (before anything is looked up or hooked)
        raise RuntimeError(problem)
    lib.freelab_hooks_init.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    lib.freelab_hooks_add_module.argtypes = [ctypes.c_void_p]
    lib.freelab_hooks_set_palette.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.freelab_hooks_install.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    lib.freelab_hooks_set_hooked.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.freelab_hooks_set_ink.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.freelab_hooks_set_picked.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.freelab_hooks_set_text_strategy.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.freelab_hooks_set_frames.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.freelab_hooks_add_ink_module.argtypes = [ctypes.c_void_p]
    lib.freelab_hooks_set_subpixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double]
    lib.freelab_hooks_add_svg_module.argtypes = [ctypes.c_void_p]
    lib.freelab_hooks_set_color_content.argtypes = [ctypes.c_int]
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
        lib.freelab_hooks_add_svg_module(svg)  # left to Qt while a color font is current (its SVG glyphs)
    lib.freelab_hooks_add_ink_module(qtwidgets)  # its pens, for the lists' rows it draws (the ink viewports only)
    holder["hooks_lib"], holder["hooks_lib_path"] = lib, path
    return lib


HOOKS_MIN_FOUND = 25  # of 32: FontLab 7.2's program imports all of them


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
        if lib.freelab_hooks_install(DARK_OKL, LIGHT_OKL, KEEP_TINT_CONTENT) < 0:
            # a slot it could not write: the library put back the ones it had written
            raise RuntimeError("the native engine could not hook FontLab's calls")
        state["hooked"], state["hooked_lib"] = True, lib
        state["hooked_addresses"], state["ink_addresses"], state["picked_addresses"] = [], [], []
        state["text_addresses"], state["frame_addresses"] = [], []
        _send_picked(state)  # (none: the library keeps the last list for the FontLab session)
        _send_text_strategy(state)
        _send_frames(state)
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


def _gray_text(widget):
    """Text drawn light on dark by the hooks is drawn with grayscale smoothing (see NATIVE_GRAY_TEXT). The widget gets a
    font that sets the strategy alone, so it still takes the rest from its parent; its own font comes back on off."""
    record = _record(widget)
    if "font" in record:
        return
    QFont = _gui("QFont")
    try:
        own = widget.testAttribute(_core("Qt").WA_SetFont)
        record["font"] = QFont(_prop(widget, "font")) if own else None
        font = QFont(_prop(widget, "font")) if own else QFont()
        font.setStyleStrategy(QFont.NoSubpixelAntialias)
        widget.setFont(font)
    except Exception as exc:
        record.pop("font", None)
        _note_error("gray text", exc)


# ClearType drawn light on dark by Qt itself, on the surfaces the hooks map: its colored subpixel edges came out deep
# blue and brown, read as breaks inside the letters (the Fonts panel's names, the owner's image 148, 2026-11-26; seen
# in a screen copy, "Essential" broken). Grayscale smoothing, as dark applications draw light text, is clean.
NATIVE_GRAY_TEXT = True


def _hook_island(widget):
    """Leave the island's painting to the hooks: no light look, no effect. Qt still draws its
    stylesheet and icons, which are darkened as any widget's."""
    first = widget.property(HOOKED_PROP) is None
    _clear_effect(widget, _record(widget))  # an effect dark mode set before it was found in a hooked island
    widget.setProperty(HOOKED_PROP, True)
    if NATIVE_GRAY_TEXT and not widget.inherits("QTabBar"):  # (tab titles keep ClearType: see TITLE_TEXT_STRATEGY)
        _gray_text(widget)
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
    if pointer and _picked_surface(widget) and pointer not in state.setdefault("picked_addresses", []):
        widget.setProperty(PICKED_PROP, True)
        state["picked_addresses"].append(pointer)
        _send_picked(state)
        widget.update()


FRAME_KINDS = ("title", "keyed")  # the panels (TITLE_CLASSES) and the dock (KEYED_CLASSES)


# A panel's title text, drawn by the panel and mapped by the hooks, is drawn in this smoothing (QFont::StyleStrategy):
# the hooks set it on the font FontLab hands to the painter, as it is drawn (freelab_hooks_set_text_strategy). Set on
# the panel's own font, it reached the title only as the panel was next laid out (FontLab keeps a copy of the font),
# and changed the text inside the panel too. ClearType, as the tab titles: of seven smoothings compared side by side
# (grayscale, ClearType, each with three hintings, and none), the owner chose ClearType (image 182, 2026-11-26).
TITLE_TEXT_STRATEGY = 1  # QFont::PreferDefault (ClearType)


FRAME_MIN_PIXELS = 500000  # a FontLab container found to need the ink effect, this large or more: hooked instead


def _ink_frame(widget):
    """A large container of FontLab's own class found to paint light (kind "ink"), whose own painting the hooks can
    map: the Font window (2.28 million pixels), whose ink effect drew it whole offscreen at every repaint, 294 of a
    tab switch's 411 ms (measured live, 2026-11-26). Never raises."""
    try:
        if _class_name(widget).startswith("Q") or widget.inherits("QAbstractScrollArea") or not _hookable(widget):
            return False
        return _prop(widget, "width") * _prop(widget, "height") >= FRAME_MIN_PIXELS
    except Exception:
        return False


def _hook_frame(widget):
    """Leave a container's own painting to the hooks (its frames, background, title strip), with no effect; its
    children are processed as anywhere else (an island would have its FontLab-class children hooked too). The first
    time, what is inside it is looked at again: a child the container's effect mapped, unlooked at as mapped from
    above, may need a treatment of its own now. True the first time."""
    first = not widget.property(FRAME_PROP)
    _clear_effect(widget, _record(widget))
    widget.setProperty(FRAME_PROP, True)
    if first:
        inside = _child_widgets(widget)
        for child in inside:
            try:
                child.setProperty(CHECKED_PROP, None)
            except Exception:
                pass
        _enqueue([w for w in inside if w.isVisible()], "dark")
    state = _state()
    pointer = _sci_pointer(widget)
    if pointer and _class_name(widget) in TITLE_CLASSES and pointer not in state.setdefault("text_addresses", []):
        state["text_addresses"].append(pointer)  # (its title in TITLE_TEXT_STRATEGY, set as it is drawn)
        _send_text_strategy(state)
    if pointer and pointer not in state.setdefault("frame_addresses", []):
        state["frame_addresses"].append(pointer)  # (not an island: its palette is not answered light, see _send_frames)
        _send_frames(state)
        widget.update()
    return first


def _send_frames(state):
    import ctypes
    addresses = state.get("frame_addresses", [])
    table = (ctypes.c_uint64 * max(1, len(addresses)))(*addresses)
    state["hooked_lib"].freelab_hooks_set_frames(ctypes.addressof(table), len(addresses))


def _send_text_strategy(state):
    import ctypes
    addresses = state.get("text_addresses", [])
    table = (ctypes.c_uint64 * max(1, len(addresses)))(*addresses)
    state["hooked_lib"].freelab_hooks_set_text_strategy(ctypes.addressof(table), len(addresses), TITLE_TEXT_STRATEGY)


def _native_hooked():
    state = _state()
    return state.get("engine") == "native" and bool(state.get("hooked"))


def _send_picked(state):
    import ctypes
    addresses = state.get("picked_addresses", [])
    table = (ctypes.c_uint64 * max(1, len(addresses)))(*addresses)
    state["hooked_lib"].freelab_hooks_set_picked(ctypes.addressof(table), len(addresses))


def _update_hooked(app):
    """The hooked islands' addresses, rebuilt from the living widgets (FontLab deletes and makes
    windows; a deleted island's address may come back as another widget's)."""
    state = _state()
    if state.get("hooked_lib") is None or not state.get("hooked"):
        return
    addresses, inks, picked, texts, frames = [], [], [], [], []
    for widget in app.allWidgets():
        try:
            hooked, ink, frame = widget.property(HOOKED_PROP), widget.property(NATIVE_INK_PROP), widget.property(FRAME_PROP)
            if hooked or ink or frame:
                pointer = _sci_pointer(widget)
                if pointer:
                    if frame:
                        frames.append(pointer)
                        if _class_name(widget) in TITLE_CLASSES:
                            texts.append(pointer)
                    elif hooked:
                        addresses.append(pointer)
                        if widget.property(PICKED_PROP):
                            picked.append(pointer)
                    else:
                        inks.append(pointer)
        except Exception:
            pass
    if addresses != state.get("hooked_addresses"):
        state["hooked_addresses"] = addresses
        _send_hooked(state)
    if frames != state.get("frame_addresses"):
        state["frame_addresses"] = frames
        _send_frames(state)
    if texts != state.get("text_addresses"):
        state["text_addresses"] = texts
        _send_text_strategy(state)
    if picked != state.get("picked_addresses"):
        state["picked_addresses"] = picked
        _send_picked(state)
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
    if NATIVE_GRAY_TEXT and widget.parentWidget() is not None:
        _gray_text(widget.parentWidget())  # (the list: its delegates take the rows' font from it)
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
        panel_menu = int(getattr(QStyle, "PE_PanelMenu", -1))
        focus_rect = int(getattr(QStyle, "PE_FrameFocusRect", -1))
        frame_menu = int(getattr(QStyle, "PE_FrameMenu", -1))
        window_role = _gui("QPalette").Window

        def dark(option):
            window = option.palette.color(window_role)
            return _lightness(window.red(), window.green(), window.blue()) < INDICATOR_FRAME_DARK_BELOW

        class FreeLabStyle(QProxyStyle):
            def drawPrimitive(self, element, option, painter, widget=None):
                which = -2
                try:
                    which = int(element)
                    # A menu's tick, as FontLab's light look has it (the owner, November 23): the mark alone, in
                    # the text's color, and nothing for an entry not ticked. Fusion's own is a filled box.
                    if which == check and _in_menu(widget) and dark(option) and _menu_tick(option, painter, widget):
                        return
                    # No focus frame around the current row of FontLab's lists: Fusion draws it dark, and the
                    # list's mapping, which turns dark ink light, made it a white frame around the row last
                    # clicked (the Actions list: the owner, November 24). The row's highlight shows where it is.
                    if which == focus_rect and which >= 0 and _in_fontlab_view(widget):
                        return
                except Exception as exc:  # (drawn as the style draws it, below)
                    _note_error("style", exc)
                try:
                    QProxyStyle.drawPrimitive(self, element, option, painter, widget)
                except ValueError:
                    # PythonQt found no overload for some options with their widget (a tool button's
                    # menu arrow: a QStyleOptionToolButton): drawn without the widget, or not at all
                    try:
                        QProxyStyle.drawPrimitive(self, element, option, painter)
                    except Exception:
                        return
                try:
                    if which == panel_menu and which >= 0:
                        if _in_menu(widget) and dark(option):
                            _menu_gutter(option, painter, widget)
                        return
                    if which == frame_menu and which >= 0:
                        if _in_menu(widget) and dark(option):
                            _menu_frame(option, painter)  # (drawn last, over the entries: Fusion's is near black)
                        return
                    if which != check and which != radio:
                        return
                    if _sheet_styles_indicators(widget):
                        return  # FontLab's own images (blue boxes): a frame would show at their rounded corners
                    if not dark(option):
                        return
                    painter.save()
                    try:
                        painter.setRenderHint(antialiasing, True)
                        painter.setBrush(no_brush)
                        painter.setPen(QColor(INDICATOR_BORDER.get(_state().get("shade", "dark"), INDICATOR_BORDER["dark"])))
                        box = QRectF(option.rect).adjusted(0.5, 0.5, -1.5, -1.5)
                        if which == check and _in_menu(widget):
                            # A menu's tick whose entry could not be read (_menu_tick): Fusion's box, whose own
                            # outline, a dark one a pixel wider and taller than this frame and square at its
                            # corners, showed around it on the highlighted row (the review of November 23,
                            # image 13). Drawn right over it, corners included (on half pixels, so each side is
                            # one whole pixel).
                            painter.drawRect(QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5))
                        elif which == check:
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


MENU_TICK = ((0.20, 0.52), (0.42, 0.74), (0.82, 0.26))  # a menu's tick across its box: down to the corner, up to the end
MENU_TICK_WIDTH = 1.4  # pixels: the tick's stroke
MENU_GUTTER = 23  # pixels at 96 dpi from a menu's left edge to the line beside its ticks and icons (Fusion's text: 27)
# A menu's frame and the line beside its ticks share one color, near the menu's own, and the line is thicker
# than the separators between entries, as in FontLab's light look (the owner, November 23, images 23 and 24):
# the window color this much lighter (the separators: SEPARATOR_LIGHTER, plainer).
MENU_FRAME_LIGHTER = 145
MENU_GUTTER_WIDTH = 2  # pixels


def _menu_tick(option, painter, widget):
    """A menu entry's tick drawn as FontLab's light look draws it, the mark alone: in the text's color when the
    entry is ticked, nothing when it is not. The entry is the one under the box (PythonQt cannot read the
    option's own state). False when the entry cannot be read: the style then draws its box."""
    action = widget.actionAt(option.rect.center())
    if action is None:
        return False
    if not action.isChecked():
        return True
    QPointF, QPen, QPainter, QPalette = _core("QPointF"), _gui("QPen"), _gui("QPainter"), _gui("QPalette")
    rect = option.rect
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    points = [QPointF(x + fx * w, y + fy * h) for fx, fy in MENU_TICK]
    painter.save()
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(option.palette.color(QPalette.WindowText))
        pen.setWidthF(MENU_TICK_WIDTH)
        painter.setPen(pen)
        painter.drawLine(points[0], points[1])
        painter.drawLine(points[1], points[2])
    finally:
        painter.restore()
    return True


def _gutter_offset(menu):
    """How far in from a menu's left edge the line beside its ticks is, in pixels: MENU_GUTTER at the menu's
    own scale (its logical dots per inch over 96), the one figure the line and the separators' start share."""
    try:
        scale = float(menu.logicalDpiX()) / 96.0
    except Exception:
        scale = 1.0
    return int(MENU_GUTTER * max(1.0, scale))


def _menu_gutter(option, painter, widget):
    """The line beside a menu's ticks and icons, which FontLab's light look has and Fusion does not (the owner,
    November 23): drawn over the menu's panel, before its entries, in the color of the menu's frame and from
    one edge of it to the other. A highlighted entry covers it, as it covers the panel."""
    QPalette, QColor, QPointF = _gui("QPalette"), _qt()[2], _core("QPointF")
    rect = option.rect
    x = rect.x() + _gutter_offset(widget) + 0.5
    window = option.palette.color(QPalette.Window).name()
    painter.save()
    try:
        painter.setPen(QColor(lighter_name(window, MENU_FRAME_LIGHTER)))
        for step in range(MENU_GUTTER_WIDTH):
            painter.drawLine(QPointF(x + step, rect.y() + 1), QPointF(x + step, rect.y() + rect.height() - 2))
        _menu_frame(option, painter)
    finally:
        painter.restore()


def _menu_frame(option, painter):
    """A dark menu's frame, one pixel around it, in the color of the line beside its ticks (_menu_gutter)."""
    QPalette, QColor, QRectF = _gui("QPalette"), _qt()[2], _core("QRectF")
    window = option.palette.color(QPalette.Window).name()
    painter.save()
    try:
        painter.setBrush(_gui("QBrush")())
        painter.setPen(QColor(lighter_name(window, MENU_FRAME_LIGHTER)))
        painter.drawRect(QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5))
    finally:
        painter.restore()


def _in_menu(widget):
    """True when a primitive is drawn for a menu (the widget Qt hands the style is the QMenu). Never raises."""
    try:
        return widget is not None and bool(widget.inherits("QMenu"))
    except Exception:
        return False


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
    _forget_map_cache()  # (mapped for another shade, or by an earlier module)
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
    switched = not (state["on"] and _app_is_dark(app, QPalette))
    if switched:  # a style change repolishes every widget: only when needed
        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            app.setStyle(_framed_style(fusion))
        app.setPalette(build_palette(QPalette, QColor))
        app.setFont(state["saved"]["font"])  # undoes the grayscale text smoothing an earlier version set
    _help_palette(app, build_palette(QPalette, QColor))  # (each time: a class's palette goes with the application's)
    state["on"] = True
    if switched:
        _tell_tools(True)  # (before the queue: FreeLab's windows in their new colors when they are looked at)
    _keep_module(state)
    state["queue"][:] = [item for item in state["queue"] if item[0] == "dark"]  # switching off may not have finished
    if state["engine"] == "native":
        _install_hooks(app)  # falls back to the script engine when it cannot start
    _darken_preferences()  # a near-white workspace, which either engine maps to dark mode's canvas
    dark_title_bars(True)
    widgets = list(app.allWidgets())
    if switched:
        _release_known(state)  # (the sweeps hold every widget's wrapper anew: _sweep)
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
    _forget_map_cache()
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
    _release_known(state)  # (the widgets' wrappers the sweeps held, let go now: but parentless ones)
    state["icon_cache"].clear()
    state["mapped_keys"].clear()
    state["originals"].clear()
    state["swatches"].clear()
    state.pop("logo_keys", None)  # list logos mapped at this shade: another shade maps them anew
    state.pop("color_fonts", None)  # fonts found in color or not: looked at anew when switched on
    if was_on:
        _restore_preferences()
    dark_title_bars(False)
    style = QStyleFactory.create(saved["style"] or ORIGINAL_STYLE_FALLBACK)
    if style is not None:
        app.setStyle(style)
    app.setPalette(saved["palette"])  # (the help's own palette goes with it: Qt forgets each class's)
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
    _tell_tools(False)


TOOLS_HOOK = "_freelab_theme_hook"  # set by FreeLab's tools (their shared module's hook_theme)


def _tell_tools(dark):
    """FreeLab's tool windows follow the switch at once (their shared module's theme_switched): their
    widgets under a stylesheet kept the theme of before, and their pictures were drawn in it. Called
    once the palette and the style are both set, either way; nothing when no tool window was opened."""
    hook = getattr(sys, TOOLS_HOOK, None)
    if hook is None:
        return
    try:
        hook(dark)
    except Exception as exc:  # the switch goes on whatever a tool does
        _note_error("tools", exc)


def owns_palette(widget):
    """Whether dark mode set this widget's palette (an island's, a field's placeholder): FreeLab's tools
    then leave it be as they polish their windows again after a switch."""
    record = _record(widget, create=False)
    return record is not None and ("palette" in record or "placeholder" in record)


def forget(window):
    """A FreeLab tool window closed for good (its shared module's let_go): what dark mode did to its
    widgets undone, and their records dropped. The records held the widgets (and their effects), which
    kept the window from being freed. True when there was something to forget."""
    state = _state()
    found = False
    try:
        widgets = _descendants(window)  # (the window itself too: Qt's isAncestorOf includes it)
    except Exception:
        widgets = [window]
    for widget in widgets:
        try:
            if widget.property(SHEET_PROP) is not None or _record(widget, create=False) is not None:
                found = True
            _undo_widget(widget)  # (an effect removed through Qt, then dropped: never freed under the widget)
        except Exception as exc:
            _note_error("forget", exc)
    for key, record in list(state["records"].items()):
        obj = record.get("obj")
        try:
            if obj is None or not _alive(obj) or not obj.isWidgetType():
                continue
            if not (obj is window or obj == window or window.isAncestorOf(obj)):
                continue
        except Exception:
            continue
        state["records"].pop(key, None)  # (one _undo_widget could not drop)
        found = True
    queue = state["queue"]
    kept = []
    for item in queue:
        try:
            if item[1] is window or item[1] == window or window.isAncestorOf(item[1]):
                found = True
                continue
        except Exception:
            pass
        kept.append(item)
    queue[:] = kept
    return found


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
    """The reapply timers stopped, and kept (schedule_reapply starts them again)."""
    for timer in state["timers"]:
        try:
            timer.stop()
        except Exception:
            pass


def _reapply_if_on():
    state = _state()
    if state["on"]:
        try:
            apply_dark()
        except Exception as exc:
            print("FreeLab dark mode could not reapply: %s" % (_text(exc),))


def schedule_reapply():
    """Apply again shortly after startup, in case FontLab sets its own style after this script."""
    state = _state()
    _cancel_timers(state)
    timers = state["timers"]
    for index, delay in enumerate(REAPPLY_DELAYS_MS):
        timer = timers[index] if index < len(timers) and _alive(timers[index]) else None
        if timer is None:  # (made once, kept for the session: _new_timer)
            timer = _new_timer("_reapply_if_on")
            timer.setSingleShot(True)
            if index < len(timers):
                state.setdefault("retired_timers", []).append(timers[index])
                timers[index] = timer
            else:
                timers.append(timer)
        timer.setInterval(delay)
        timer.start()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def startup():
    """Called by FontLab's startup script: apply dark mode if it was left on, or if following Windows and it is dark."""
    settings = load_settings()
    follow = bool(settings.get("follow_windows"))
    app = _qt()[0].instance()
    if app is not None:
        _hook_focus(app)  # (Overlay Fonts' moves guarded, dark mode on or off: see MOVE_GUARD_WINDOWS)
        _align_icons(app)  # (and again at focus changes until the tool bar is there: see ALIGNED_ICONS)
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
        message += (" (It no longer follows Windows: Automatic, in Scripts > FreeLab > Dark Mode Settings, turns "
                    "that back on.)")
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
