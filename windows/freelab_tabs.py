#FLM: Tab Docking
# -*- coding: utf-8 -*-
"""FreeLab tab docking: FontLab's document tabs reorder and dock back the way Photoshop's do.

FontLab 7 turns a tab into a window of its own whenever it is dropped anywhere, even on the tab
bar it came from, and only Window > Docking > Merge Window brings it back. FontLab handles the drag
itself, before any Qt event filter sees the mouse moves (and takes the tab out of its bar as the
drag starts), so this follows the drag from outside: a press on a document tab notes the tab, and a
short timer then watches the mouse until its button is released.

- While the mouse is on or near the main window's tab bar (within TEAR_MARGIN pixels), a marker
  shows where the tab will go.
- Released there, the tab goes into the main window at that place, from the main window or from a
  window of its own (FontLab may make that window first; it is merged back at once, and a window
  the tab left empty is closed).
- Released farther away, the tab is a window of its own, as FontLab makes it.
- A window of its own gets a Dock button beside its tabs; a double-click on one of its tabs docks it.

Runs at FontLab's start (FreeLab's startup block). Scripts > FreeLab > Tab Docking switches
it off and on; the choice is kept in %LOCALAPPDATA%\\FreeLab\\tabs.json.

Every timer, connection, and filter calls through _dispatcher, which looks the module up when it is
called: Python 2 empties a module's globals once nothing holds it, and a reloaded module (or a
second copy) must not leave callbacks that fail.
"""
from __future__ import absolute_import, division, print_function

import json
import os
import sys
import time

MODULE_NAME = "freelab_tabs"
TEAR_MARGIN = 40  # pixels around the main tab bar where a released tab docks back (Photoshop's feel)
WATCH_MS = 1000  # how often new tab widgets (a new window, a reopened font) are looked for
POLL_MS = 25  # how often a drag in progress is followed
DOCK_DELAY_MS = 60  # after the release, so FontLab has finished its own drop first
MARKER_WIDTH = 4
MAIN_FRAME_NAME = "YDropTargetContainer"  # the main window's document area
WATCHED_PROP = "freelab_tabs"
LEAVE_ALONE_PROP = "freelabLeaveAlone"  # dark mode leaves the marker as drawn
DOCK_BUTTON_NAME = "freelabDockButton"
MERGE_WINDOW = "actionMerge_Window"


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def _state():
    state = getattr(sys, "_freelab_tabs_state", None)
    if state is None:
        state = sys._freelab_tabs_state = {"on": False}
    for key, value in (("held", []), ("pending", []), ("drag", None)):
        state.setdefault(key, value)
    return state


def _dispatcher():
    """call(name, *args): the function of that name in this module as loaded now, called while tab
    docking is on; errors printed, never raised (into a Qt slot or filter). Uses only what its
    closure holds, so it keeps working when this copy of the module is gone."""
    modules, name, holder = sys.modules, MODULE_NAME, sys

    def call(function, *args):
        try:
            state = getattr(holder, "_freelab_tabs_state", None) or {}
            module = modules.get(name) or state.get("module")
            if module is not None and state.get("on"):
                return getattr(module, function)(*args)
        except Exception as exc:
            try:
                print("FreeLab tab docking: %s" % (exc,))
            except Exception:
                pass
        return None
    return call


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
    for widget in QtGui.QApplication.instance().topLevelWidgets():
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


def button_down():
    """The primary mouse button held, as Windows has it now (FontLab's drag keeps Qt's own idea of the
    buttons from being updated)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        key = 0x02 if user32.GetSystemMetrics(23) else 0x01  # SM_SWAPBUTTON: the right button is primary
        return bool(user32.GetAsyncKeyState(key) & 0x8000)
    except Exception:
        return bool(int(_qt()[1].QApplication.mouseButtons()) & 1)


def drag_distance():
    """Qt's drag start distance (PythonQt gives it as a property of the application, not a call)."""
    QtGui = _qt()[1]
    for source in (QtGui.QApplication.instance(), QtGui.QApplication):
        value = getattr(source, "startDragDistance", None)
        try:
            value = value() if callable(value) else value
            if value:
                return int(value)
        except Exception:
            pass
    return 10


def near_bar(bar, tab_widget, point, margin=TEAR_MARGIN):
    """True when a global point lies on the tab bar's strip (the tab widget's width) or within margin of it."""
    if bar is None or tab_widget is None or not bar.isVisible():
        return False
    local = bar.mapFromGlobal(point)
    across = tab_widget.mapFromGlobal(point)
    return (-margin <= across.x() <= tab_widget.width + margin
            and -margin <= local.y() <= bar.height + margin)


def drop_slot(bar, point, page_of, page):
    """Where a tab released at a global point goes among the bar's other tabs (page itself left out,
    if still there): before the first tab whose middle lies right of the mouse, else last.
    page_of(index) is the tab's widget. FontLab's Sketchboard stays first."""
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


def marker_x(bar, page_of, page, slot):
    """The x (in the bar) of the gap a tab goes into: the left edge of the tab it goes before, or the
    right edge of the last."""
    others = [k for k in range(bar.count) if page_of(k) is not page]
    if not others:
        return 0
    if slot < len(others):
        return bar.tabRect(others[slot]).left()
    last = bar.tabRect(others[-1])
    return last.left() + last.width()


# ---------------------------------------------------------------------------
# Following a drag
# ---------------------------------------------------------------------------

def on_pressed(tab_widget, index):
    """A press on a document tab (the bar's event filter): the tab a drag would take, then the mouse
    followed until it is released. FontLab takes the tab out of its bar as the drag starts."""
    state = _state()
    if index < 0:
        state["drag"] = None
        return
    state["drag"] = {"page": tab_widget.widget(index), "start": cursor_pos(), "started": False}
    timer = state.get("poll_timer")
    if timer is not None:
        timer.start()


def on_dropped(tab_widget):
    """FontLab's drop signal: no longer used (the release is followed instead); kept for connections
    an earlier version made in this FontLab session."""
    return None


def poll():
    """While a drag is followed: the marker where the tab would go; at the release, the tab docked
    back if it is on or near the main tab bar."""
    QtCore, QtGui = _qt()
    state = _state()
    drag = state.get("drag")
    if drag is None:
        _stop_polling()
        return
    point = cursor_pos()
    if button_down():
        if not drag["started"]:
            moved = abs(point.x() - drag["start"].x()) + abs(point.y() - drag["start"].y())
            drag["started"] = moved >= drag_distance()
        if drag["started"]:
            show_marker(drag["page"], point)
        return
    _stop_polling()
    hide_marker()
    state["drag"] = None
    if not drag["started"] or drag["page"] is None:
        return
    bar, main = main_tabs()
    if main is None or not near_bar(bar, main, point):
        return  # released away: a window of its own, as FontLab made it
    page, slot = drag["page"], drop_slot(bar, point, main.widget, drag["page"])
    later = (lambda call: lambda: call("dock_after_drop", page, slot))(_dispatcher())
    state["pending"].append(later)
    del state["pending"][:-16]  # the last few kept alive until they have run
    QtCore.QTimer.singleShot(DOCK_DELAY_MS, later)


def _stop_polling():
    timer = _state().get("poll_timer")
    if timer is not None:
        timer.stop()


def dock_after_drop(page, slot):
    dock(page, slot)
    refresh_main()


def refresh_main():
    """Repaint the main window's document area: FontLab's blue drop highlight stayed on it after a
    tab it was showing a drop for was docked by Merge Window instead."""
    QtGui = _qt()[1]
    bar, main = main_tabs()
    frame = main.parentWidget() if main is not None else None
    if frame is None:
        return
    # Not findChildren(QWidget): under PythonQt it returns an empty list. (isAncestorOf is true of the frame itself.)
    for widget in QtGui.QApplication.instance().allWidgets():
        if frame.isAncestorOf(widget) and widget.isVisible():
            widget.update()


def _marker():
    QtCore, QtGui = _qt()
    state = _state()
    marker = state.get("marker")
    if marker is None:
        marker = QtGui.QWidget(None, QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint)
        marker.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        marker.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        marker.setProperty(LEAVE_ALONE_PROP, True)
        marker.setAutoFillBackground(True)
        state["marker"] = marker
    return marker


def show_marker(page, point):
    """The marker at the gap the tab would go into, when the mouse is on or near the main tab bar."""
    QtCore, QtGui = _qt()
    bar, main = main_tabs()
    if main is None or not near_bar(bar, main, point):
        hide_marker()
        return
    slot = drop_slot(bar, point, main.widget, page)
    x = marker_x(bar, main.widget, page, slot)
    marker = _marker()
    palette = marker.palette
    palette.setColor(QtGui.QPalette.Window, QtGui.QApplication.palette().color(QtGui.QPalette.Highlight))
    marker.setPalette(palette)
    top_left = bar.mapToGlobal(QtCore.QPoint(x - MARKER_WIDTH // 2, 0))
    marker.setGeometry(top_left.x(), top_left.y(), MARKER_WIDTH, max(8, bar.height))
    if not marker.isVisible():
        marker.show()
    marker.raise_()


def hide_marker():
    marker = _state().get("marker")
    if marker is not None and marker.isVisible():
        marker.hide()


# ---------------------------------------------------------------------------
# Docking
# ---------------------------------------------------------------------------

def holder_of(page):
    """The window of its own (a YFrameWindow) whose tabs hold page, or None."""
    for widget, frame in document_tab_widgets():
        if frame.isWindow() and widget.indexOf(page) >= 0:
            return frame
    return None


ACTIVATE_TRIES, ACTIVATE_WAIT = 10, 0.02  # how long Merge Window is waited for, once its window is made active


def _fail(reason):
    """Why a tab could not be docked: said in FontLab's Output panel and kept (state["failures"], the
    last few with their times), since a dock that does nothing gave no hint of its cause."""
    state = _state()
    failures = state.setdefault("failures", [])
    failures.append((time.strftime("%H:%M:%S"), reason))
    del failures[:-8]
    try:
        print("FreeLab tab docking: %s" % reason)
    except Exception:
        pass
    return False


def _describe(widget):
    try:
        return u"%s \"%s\"" % (_class(widget), widget.windowTitle) if widget is not None else u"none"
    except Exception:
        return u"unknown"


def merge_window(frame):
    """Window > Docking > Merge Window for that window: it is made the active one first, and waited
    for a moment (FontLab enables the command once it has seen the window become active, which with
    other windows open, a FreeLab tool's among them, is not always at once)."""
    QtGui = _qt()[1]
    main = main_window()
    if main is None:
        return _fail(u"FontLab's main window was not found.")
    actions = [a for a in main.findChildren(QtGui.QAction) if a.objectName == MERGE_WINDOW]
    if not actions:
        return _fail(u"FontLab's Merge Window command was not found.")
    frame.raise_()
    frame.activateWindow()
    active = None
    for attempt in range(ACTIVATE_TRIES):
        QtGui.QApplication.processEvents()
        try:
            active = QtGui.QApplication.activeWindow()
        except Exception:
            active = None  # not known: merged as before
        if actions[0].isEnabled() and (active is None or active is frame or _class(active) != "YFrameWindow"):
            break
        time.sleep(ACTIVATE_WAIT)
        if attempt == ACTIVATE_TRIES // 2:
            frame.activateWindow()  # (asked once more: another window had taken the activation back)
    if not actions[0].isEnabled():
        return _fail(u"FontLab's Merge Window command stayed unavailable for %s (the active window: %s)."
                     % (_describe(frame), _describe(active)))
    if active is not None and active is not frame and _class(active) == "YFrameWindow":
        # another window of its own is still the active one: Merge Window would merge that one
        return _fail(u"another window stayed the active one (%s), not %s." % (_describe(active), _describe(frame)))
    actions[0].trigger()
    QtGui.QApplication.processEvents()
    return True


def dock(page, target=None):
    """Put a document tab into the main window (merging the window that holds it), at target if given;
    a window it left empty is closed (FontLab keeps it open, and merging it does nothing)."""
    bar, main = main_tabs()
    if main is None:
        return _fail(u"the main window's tabs were not found.")
    at = main.indexOf(page)
    if at < 0:
        frame = holder_of(page)
        if frame is None:
            return _fail(u"the tab's window was not found (FontLab may have moved the tab since).")
        if not merge_window(frame):
            return False
        at = main.indexOf(page)
        if at < 0:
            return _fail(u"FontLab's Merge Window ran, but the tab is not in the main window.")
    if target is not None and 0 <= target < bar.count and target != at:
        bar.moveTab(at, target)
    for widget, frame in document_tab_widgets():
        if frame.isWindow() and frame.isVisible() and widget.count == 0:
            frame.close()
    main.setCurrentIndex(main.indexOf(page))
    window = main_window()
    if window is not None:
        window.activateWindow()
    return True


def dock_frame(tab_widget):
    page = tab_widget.currentWidget()
    if page is not None:
        dock(page)
        refresh_main()


# ---------------------------------------------------------------------------
# Hooks: a filter on each document tab bar, a Dock button on each window of its own
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
    handler = (lambda call: lambda *args: call("dock_frame", tab_widget))(_dispatcher())
    _state()["held"].append(handler)
    button.connect("clicked()", handler)
    tab_widget.setCornerWidget(button, corner)
    button.show()


def _filter_class():
    QtCore = _qt()[0]
    state = _state()
    if "filter_class_v2" not in state:
        call, holder = _dispatcher(), sys  # (the closure's: this module's globals may be gone when it runs)

        class TabPresses(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            """On a document tab bar: a press starts following a possible drag; a double-click on a
            tab of a window of its own docks that window."""

            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                        call("on_pressed", obj.parentWidget(), obj.tabAt(event.pos()))
                    elif kind == QtCore.QEvent.MouseButtonDblClick and obj.tabAt(event.pos()) >= 0:
                        if not (getattr(holder, "_freelab_tabs_state", None) or {}).get("on"):
                            return False  # off: the double-click is FontLab's
                        tab_widget = obj.parentWidget()
                        frame = tab_widget.parentWidget() if tab_widget is not None else None
                        if frame is not None and frame.isWindow():
                            QtCore.QTimer.singleShot(0, lambda: call("dock_frame", tab_widget))
                            return True
                except Exception:
                    pass  # an event filter must never raise
                return False
        state["filter_class_v2"] = TabPresses
    return state["filter_class_v2"]


def watch():
    """Hook every document tab bar not seen yet, and give windows of their own their Dock button."""
    QtCore, QtGui = _qt()
    state = _state()
    for tab_widget, frame in document_tab_widgets():
        try:
            if frame.isWindow():
                button = tab_widget.findChild(QtGui.QToolButton, DOCK_BUTTON_NAME)
                if button is None:
                    _add_dock_button(tab_widget)
                elif tab_widget.cornerWidget(QtCore.Qt.TopRightCorner) is None:  # put back after an off
                    tab_widget.setCornerWidget(button, QtCore.Qt.TopRightCorner)
                    button.show()
            bar = _bar_of(tab_widget)
            if bar is not None and bar.property(WATCHED_PROP) != 2:
                presses = _filter_class()()
                state["held"].append(presses)
                bar.installEventFilter(presses)
                bar.setProperty(WATCHED_PROP, 2)  # (1 or True: an earlier version's filter, which does nothing now)
        except Exception as exc:
            print("FreeLab tab docking: %s" % (exc,))


def _timer(key, interval, function):
    """A fresh timer calling function through the dispatcher (an earlier one stopped and replaced)."""
    QtCore = _qt()[0]
    state = _state()
    old = state.get(key)
    if old is not None:
        old.stop()
    timer = QtCore.QTimer()
    timer.setInterval(interval)
    tick = (lambda call: lambda: call(function))(_dispatcher())
    state[key + "_tick"] = tick
    timer.connect("timeout()", tick)
    state[key] = timer
    return timer


def start():
    state = _state()
    state["on"] = True
    state["module"] = sys.modules.get(__name__)  # what the dispatcher calls, should FontLab drop it
    _timer("timer", WATCH_MS, "watch").start()
    _timer("poll_timer", POLL_MS, "poll")
    watch()


def stop():
    """Off: FontLab's own ways again. Filters stay (they do nothing while off); Dock buttons go."""
    QtCore, QtGui = _qt()
    state = _state()
    state["on"] = False
    state["drag"] = None
    for key in ("timer", "poll_timer"):
        if state.get(key) is not None:
            state[key].stop()
    hide_marker()
    for tab_widget, frame in document_tab_widgets():
        button = tab_widget.findChild(QtGui.QToolButton, DOCK_BUTTON_NAME)
        if button is not None:
            tab_widget.setCornerWidget(None, QtCore.Qt.TopRightCorner)
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
        message = (u"FreeLab tab docking is on: drag a tab along the tab bar to move it; released on or near "
                   u"the tab bar, a tab goes back into the main window. Run this script again to switch it off.")
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
