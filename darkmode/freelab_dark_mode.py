#FLM: FreeLab: Toggle Dark Mode
# -*- coding: utf-8 -*-
"""FreeLab dark mode for FontLab's interface.

Run this file from FontLab's Scripts menu to switch dark mode on or off; the
choice is remembered. With the FreeLab startup hook installed
(tools/install-fontlab.ps1), FontLab applies the remembered choice at launch.

It switches the Qt application to the Fusion style with a dark palette and
appends a stylesheet to FontLab's own. Everything it changes is saved first
and restored when dark mode is switched off, without a restart. The glyph
canvas and font window cells are painted by FontLab from its own color
preferences, which this file does not touch.

Valid Python 2.7 (FontLab 7) and Python 3 (FontLab 8).
"""

from __future__ import absolute_import, division, print_function

import json
import os
import sys

VERSION = "0.1.0"
MODULE_NAME = "freelab_dark_mode"
REAPPLY_DELAYS_MS = (0, 1500, 5000)  # FontLab may restyle itself after the startup script runs

# Dark palette: (role, color for all groups, color for the Disabled group or None).
PALETTE = (
    ("Window", "#2d2d30", None),
    ("WindowText", "#dcdcdc", "#7f7f7f"),
    ("Base", "#1e1e1e", "#262626"),
    ("AlternateBase", "#262628", None),
    ("ToolTipBase", "#3c3c40", None),
    ("ToolTipText", "#e6e6e6", None),
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
    ("HighlightedText", "#ffffff", "#9a9a9a"),
    ("Link", "#6aa8ff", None),
    ("LinkVisited", "#b48cff", None),
    ("PlaceholderText", "#8a8a8a", None),
)

STYLESHEET = u"""
/* FreeLab dark mode */
QToolTip { color: #e6e6e6; background-color: #3c3c40; border: 1px solid #55555a; }
QMenu { background-color: #2d2d30; color: #dcdcdc; border: 1px solid #45454a; }
QMenu::item:selected { background-color: #3d6fb4; color: #ffffff; }
QMenu::item:disabled { color: #7f7f7f; }
QMenu::separator { height: 1px; background: #45454a; margin: 4px 8px; }
QMenuBar { background-color: #2d2d30; color: #dcdcdc; }
QMenuBar::item:selected { background-color: #3d6fb4; color: #ffffff; }
"""
STYLESHEET_MARK = u"/* FreeLab dark mode */"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def settings_path():
    override = os.environ.get("FREELAB_STATE_DIR")
    base = override or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FreeLab")
    return os.path.join(base, "darkmode.json")


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
# Qt
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


def _state():
    state = getattr(sys, "_freelab_dark_mode", None)
    if state is None:
        state = {"on": False, "saved": None, "timers": []}
        sys._freelab_dark_mode = state  # survives FontLab clearing the script namespace
    return state


def build_palette(QPalette, QColor, base=None):
    palette = QPalette(base) if base is not None else QPalette()
    for role_name, color, disabled in PALETTE:
        role = getattr(QPalette, role_name, None)
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


def apply_dark():
    """Switch the interface to dark. Saves what it changes the first time."""
    QApplication, QPalette, QColor, QStyleFactory, QTimer = _qt()
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("No Qt application is running.")
    state = _state()
    if state["saved"] is None:
        state["saved"] = {
            "style": app.style().objectName(),
            "palette": QPalette(app.palette()),
        }
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    app.setPalette(build_palette(QPalette, QColor))
    app.setStyleSheet(_strip_ours(app.styleSheet()) + u"\n" + STYLESHEET)
    state["on"] = True


def restore():
    """Put back the style and palette saved by apply_dark, and take FreeLab's block out of the stylesheet.

    The rest of the stylesheet is FontLab's and is left as it is now, including
    any change FontLab made to it while dark mode was on.
    """
    QApplication, QPalette, QColor, QStyleFactory, QTimer = _qt()
    app = QApplication.instance()
    state = _state()
    _cancel_timers(state)
    saved = state["saved"]
    if app is None or saved is None:
        state["on"] = False
        return
    style = QStyleFactory.create(saved["style"]) if saved["style"] else None
    if style is not None:
        app.setStyle(style)
    app.setPalette(saved["palette"])
    app.setStyleSheet(_strip_ours(app.styleSheet()))
    state["on"] = False


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
            print("FreeLab dark mode could not reapply: %s" % (exc,))


def schedule_reapply():
    """Apply again shortly after startup, in case FontLab sets its own style after this script."""
    QApplication, QPalette, QColor, QStyleFactory, QTimer = _qt()
    state = _state()
    _cancel_timers(state)
    for delay in REAPPLY_DELAYS_MS:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.setInterval(delay)
        try:
            connected = timer.connect("timeout()", _reapply_if_on) is not False
        except Exception:
            connected = False
        if not connected:
            timer.timeout.connect(_reapply_if_on)
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
    settings = load_settings()
    if _state()["on"]:
        restore()
        settings["enabled"] = False
        message = "FreeLab dark mode is off."
    else:
        apply_dark()
        settings["enabled"] = True
        message = "FreeLab dark mode is on. Run this script again to switch it off."
    save_settings(settings)
    print(message)
    return settings["enabled"]


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
