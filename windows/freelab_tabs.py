#FLM: Toggle Tab Docking
# -*- coding: utf-8 -*-
"""FreeLab tab docking: FontLab's document tabs reorder and dock back the way Photoshop's do.

FontLab 7 turns a tab into a window of its own whenever it is dropped anywhere, even on the tab
bar it came from, and only Window > Docking > Merge Window brings it back. FontLab handles the drag
itself (before any Qt event filter sees the mouse), so this works from the two signals its tab
widgets send, tabDragged and tabDropped:

- While a tab of the main window is dragged along the tab bar, it moves to the place under the
  mouse, as Photoshop's tabs do.
- A tab dropped on or near the main window's tab bar (within TEAR_MARGIN pixels) goes back into
  the main window at that place, from the main window or from a window of its own. FontLab makes
  the window first; it is merged back at once.
- A tab dropped farther away becomes a window, as before.
- A window of its own gets a Dock button beside its tabs, and a double-click on one of its tabs
  docks it too.

Runs at FontLab's start (FreeLab's startup block). Scripts > FreeLab > Toggle Tab Docking switches
it off and on; the choice is kept in %LOCALAPPDATA%\\FreeLab\\tabs.json.
"""
from __future__ import absolute_import, division, print_function

import json
import os
import sys

MODULE_NAME = "freelab_tabs"
TEAR_MARGIN = 48  # pixels around the main tab bar where a dropped tab docks back (Photoshop's feel)
WATCH_MS = 1000  # how often new tab widgets (a new window, a reopened font) are looked for
MAIN_FRAME_NAME = "YDropTargetContainer"  # the main window's document area
WATCHED_PROP = "freelab_tabs"
DOCK_BUTTON_NAME = "freelabDockButton"
MERGE_WINDOW = "actionMerge_Window"


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def _state():
    state = getattr(sys, "_freelab_tabs_state", None)
    if state is None:
        state = sys._freelab_tabs_state = {"on": False, "held": [], "pending": [], "drag": None}
    state.setdefault("pending", [])
    return state


def state_dir():
    override = os.environ.get("FREELAB_STATE_DIR")
    return override or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FreeLab")


def settings_path():
    return os.path.join(state_dir(), "tabs.json")


def load_settings():
    try:
        with open(settings_path(), "r") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data):
    folder = state_dir()
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(settings_path(), "w") as handle:
        json.dump(data, handle)


def enabled_setting(settings):
    return bool(settings.get("enabled", True))


# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------

def _class(widget):
    try:
        return widget.metaObject().className()
    except Exception:
        return ""


def main_window():
    QtGui = _qt()[1]
    app = QtGui.QApplication.instance()
    for widget in app.topLevelWidgets():
        if widget.inherits("QMainWindow") and _class(widget) == "MainWindow":
            return widget
    return None


def document_tab_widgets():
    """(tab widget, its frame) of every document area: the main window's and each window of its own."""
    QtGui = _qt()[1]
    found = []
    for widget in QtGui.QApplication.instance().allWidgets():
        if _class(widget) != "YTabWidget":
            continue
        frame = widget.parentWidget()
        if frame is not None and _class(frame) == "YFrameWindow":
            found.append((widget, frame))
    return found


def main_tabs():
    """(tab bar, tab widget) of the main window's document tabs, or (None, None)."""
    for widget, frame in document_tab_widgets():
        if frame.objectName == MAIN_FRAME_NAME and not frame.isWindow():
            return _bar_of(widget), widget
    return None, None


def _bar_of(tab_widget):
    QtGui = _qt()[1]
    bars = [b for b in tab_widget.findChildren(QtGui.QTabBar) if b.parentWidget() is tab_widget]
    return bars[0] if bars else None


def cursor_pos():
    """The mouse, in global coordinates (FontLab's drag reads it too, not the events' positions)."""
    return _qt()[1].QCursor.pos()


def near_bar(bar, tab_widget, point, margin=TEAR_MARGIN):
    """True when a global point lies on the tab bar's strip (the tab widget's width) or within margin of it."""
    if bar is None or tab_widget is None or not bar.isVisible():
        return False
    local = bar.mapFromGlobal(point)
    across = tab_widget.mapFromGlobal(point)
    height = bar.height
    return (-margin <= across.x() <= tab_widget.width + margin
            and -margin <= local.y() <= height + margin)


def drop_slot(bar, point, page_of, page):
    """Where a tab dropped at a global point goes among the bar's other tabs (page itself left out, if
    still there): before the first tab whose middle lies right of the mouse, else last. page_of(index)
    is the tab's widget. FontLab's Sketchboard stays first."""
    x = bar.mapFromGlobal(point).x()
    slot = 0
    others = [k for k in range(bar.count) if page_of(k) is not page]
    for k in others:
        if x < bar.tabRect(k).center().x():
            break
        slot += 1
    if slot == 0 and others and _class(page_of(others[0])) == "YSketchBoard":
        slot = 1
    return slot


# ---------------------------------------------------------------------------
# Dragging and dropping
# ---------------------------------------------------------------------------

def on_pressed(tab_widget, index):
    """A press on a document tab (the bar's event filter): the tab a drag would take. FontLab takes it
    out of the bar as the drag starts, so it is noted here."""
    _state()["drag"] = (tab_widget, tab_widget.widget(index)) if index >= 0 else None


def on_dropped(tab_widget):
    """A tab is dropped (FontLab's signal, after it made a window of it): on or near the main tab bar,
    it is docked back where the mouse is."""
    QtCore = _qt()[0]
    state = _state()
    drag, state["drag"] = state["drag"], None
    if not state["on"] or drag is None or drag[0] is not tab_widget or drag[1] is None:
        return
    page = drag[1]
    bar, main = main_tabs()
    point = cursor_pos()
    if main is None or not near_bar(bar, main, point):
        return  # dropped away: a window of its own, as FontLab made it
    slot = drop_slot(bar, point, main.widget, page)
    later = lambda: _dock_safely(page, slot)
    state["pending"].append(later)
    QtCore.QTimer.singleShot(0, later)


def _dock_safely(page, target):
    try:
        dock(page, target)
    except Exception as exc:
        print("FreeLab tab docking: %s" % (exc,))
    finally:
        pending = _state()["pending"]
        del pending[:-16]  # the last few kept alive until they have run


def holder_of(page):
    """The window of its own (a YFrameWindow) whose tabs hold page, or None."""
    for widget, frame in document_tab_widgets():
        if frame.isWindow() and widget.indexOf(page) >= 0:
            return frame
    return None


def merge_window(frame):
    """Window > Docking > Merge Window for that window: it is made the active one first."""
    QtGui = _qt()[1]
    main = main_window()
    if main is None:
        return False
    actions = [a for a in main.findChildren(QtGui.QAction) if a.objectName == MERGE_WINDOW]
    if not actions:
        return False
    frame.raise_()
    frame.activateWindow()
    QtGui.QApplication.processEvents()
    if not actions[0].isEnabled():
        return False
    actions[0].trigger()
    QtGui.QApplication.processEvents()
    return True


def dock(page, target=None):
    """Put a document tab into the main window (merging the window that holds it), at target if given."""
    bar, main = main_tabs()
    if main is None:
        return False
    at = main.indexOf(page)
    if at < 0:
        frame = holder_of(page)
        if frame is None or not merge_window(frame):
            return False
        at = main.indexOf(page)
        if at < 0:
            return False
    if target is not None and 0 <= target < bar.count and target != at:
        bar.moveTab(at, target)
        at = target
    main.setCurrentIndex(at)
    for widget, frame in document_tab_widgets():
        if frame.isWindow() and frame.isVisible() and widget.count == 0:
            frame.close()  # the window the tab came from, left empty (FontLab keeps it open; merging it does nothing)
    main.setCurrentIndex(main.indexOf(page))
    return True


# ---------------------------------------------------------------------------
# Windows of their own: a Dock button, and a double-click on a tab
# ---------------------------------------------------------------------------

def _add_dock_button(tab_widget):
    QtCore, QtGui = _qt()
    corner = QtCore.Qt.TopRightCorner
    if tab_widget.cornerWidget(corner) is not None:
        return  # FontLab's own corner widget stays
    button = QtGui.QToolButton(tab_widget)
    button.setObjectName(DOCK_BUTTON_NAME)
    button.setText(u"Dock")
    button.setAutoRaise(True)
    button.setToolTip(u"Put this window's tabs back into the main window (or double-click a tab)")
    handler = lambda *args: _call("dock_frame", tab_widget)
    _state()["held"].append(handler)
    button.connect("clicked()", handler)
    tab_widget.setCornerWidget(button, corner)
    button.show()


def dock_frame(tab_widget):
    page = tab_widget.currentWidget()
    if page is not None:
        dock(page)


def _module():
    """This module as loaded last (a reload replaces the code every connection and filter calls)."""
    return sys.modules.get(MODULE_NAME) or _state().get("module")


def _call(name, *args):
    try:
        module = _module()
        if module is not None and module._state()["on"]:
            return getattr(module, name)(*args)
    except Exception as exc:  # a slot or a filter must not raise into FontLab
        print("FreeLab tab docking: %s" % (exc,))
    return None


def _filter_class():
    QtCore = _qt()[0]
    state = _state()
    if "filter_class" not in state:
        class TabPresses(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            """On a document tab bar: a press notes the tab a drag would take; a double-click on a tab
            of a window of its own docks that window."""

            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                        _call("on_pressed", obj.parentWidget(), obj.tabAt(event.pos()))
                    elif kind == QtCore.QEvent.MouseButtonDblClick and obj.tabAt(event.pos()) >= 0:
                        tab_widget = obj.parentWidget()
                        frame = tab_widget.parentWidget() if tab_widget is not None else None
                        if frame is not None and frame.isWindow() and _module()._state()["on"]:
                            later = lambda: _call("dock_frame", tab_widget)
                            _module()._state()["pending"].append(later)
                            QtCore.QTimer.singleShot(0, later)
                            return True
                except Exception:
                    pass  # an event filter must never raise
                return False
        state["filter_class"] = TabPresses
    return state["filter_class"]


def watch():
    """Hook every document tab widget not seen yet (FontLab's drop signal, a filter on its bar), and
    give windows of their own their Dock button."""
    state = _state()
    if not state["on"]:
        return
    for tab_widget, frame in document_tab_widgets():
        try:
            if frame.isWindow():
                button = tab_widget.findChild(_qt()[1].QToolButton, DOCK_BUTTON_NAME)
                if button is None:
                    _add_dock_button(tab_widget)
                elif tab_widget.cornerWidget(_qt()[0].Qt.TopRightCorner) is None:  # put back after an off
                    tab_widget.setCornerWidget(button, _qt()[0].Qt.TopRightCorner)
                    button.show()
            bar = _bar_of(tab_widget)
            if bar is not None and bar.property(WATCHED_PROP) is None:
                presses = _filter_class()()
                state["held"].append(presses)
                bar.installEventFilter(presses)
                bar.setProperty(WATCHED_PROP, True)
            if tab_widget.property(WATCHED_PROP) is None:
                dropped = (lambda tw: lambda *args: _call("on_dropped", tw))(tab_widget)
                state["held"].append(dropped)
                tab_widget.connect("tabDropped(YTab*,QPoint)", dropped)
                tab_widget.setProperty(WATCHED_PROP, True)
        except Exception as exc:
            print("FreeLab tab docking: %s" % (exc,))


def start():
    QtCore = _qt()[0]
    state = _state()
    state["on"] = True
    state["module"] = sys.modules.get(__name__)  # what the connections call, should FontLab drop it
    if state.get("timer") is None:
        timer = QtCore.QTimer()
        timer.setInterval(WATCH_MS)
        tick = lambda: _call("watch")
        state["tick"] = tick
        timer.connect("timeout()", tick)
        state["timer"] = timer
    state["timer"].start()
    watch()


def stop():
    """Off: FontLab's own ways again. Connections stay (they do nothing while off); Dock buttons go."""
    QtGui = _qt()[1]
    state = _state()
    state["on"] = False
    if state.get("timer") is not None:
        state["timer"].stop()
    for tab_widget, frame in document_tab_widgets():
        button = tab_widget.findChild(QtGui.QToolButton, DOCK_BUTTON_NAME)
        if button is not None:
            tab_widget.setCornerWidget(None, _qt()[0].Qt.TopRightCorner)
            button.hide()


def startup():
    """Called by FontLab's startup script: on unless switched off."""
    if enabled_setting(load_settings()):
        start()


def toggle():
    settings = load_settings()
    on = not _state()["on"]
    if on:
        start()
        message = (u"FreeLab tab docking is on: drag tabs along the tab bar to reorder them; a tab dropped "
                   u"near the tab bar goes back into the main window. Run this script again to switch it off.")
    else:
        stop()
        message = u"FreeLab tab docking is off: FontLab's own tab dragging again."
    settings["enabled"] = on
    save_settings(settings)
    print(message)
    return on


def load_as_module(path):
    """Load this file as a real module, so its globals are not FontLab's script namespace."""
    if sys.version_info[0] == 2:
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
