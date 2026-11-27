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

That is the first of two options ("reorder", on by default). The second ("no_undock", off by
default) keeps the main window's tabs in it: the press on a main window tab is kept from FontLab's tab
bar, so there is no tab for it to drag away (the tab is chosen by FreeLab, as the click would have, and
FreeLab shows a close cross of its own on the tab under the mouse, FontLab showing none on such tabs);
should FontLab make a window all the same, the tab is merged back at the place it had when pressed;
and FontLab's Undock commands (Window > Docking) are hidden. With both, FreeLab follows the drag itself: the marker shows along the bar,
and a tab released on or near it moves to that place, one released anywhere else stays where it is;
with no_undock alone, a drag does nothing, so tabs do not reorder, as in FontLab.

Runs at FontLab's start (FreeLab's startup block). Scripts > FreeLab > Tab Docking switches
it off and on, and Scripts > FreeLab > Tab Docking Settings chooses the options; both are kept in
%LOCALAPPDATA%\\FreeLab\\tabs.json.

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
# The Dock button's tooltip, a sentence as the settings' tooltips are, saying what it does
DOCK_TIP = u"Puts this window's tabs back into the main window. A double-click on one of its tabs does the same."
MERGE_WINDOW = "actionMerge_Window"
# Window > Docking > Undock All Tabs, Undock Font Tabs, and Undock Glyph Tabs: hidden while no_undock is on
UNDOCK_ACTIONS = ("actionUndock_All", "actionUndock_Font", "actionUndock_Glyph")
DEFAULT_OPTIONS = {"reorder": True, "no_undock": False}
FILTER_REVISION, FILTER_CLASS_KEY = 6, "filter_class_v6"
MOVE_EVENT = 13  # QEvent::Move, sent to a window as it is dragged by its title bar
WINDOW_MARGIN = 12  # pixels around the main tab bar where a window dragged by its title bar docks (a tab's: TEAR_MARGIN)
FRAME_PROP = "freelab_tabs_frame"  # on a window of its own whose moves are followed  # the tab bars' filter: on a bar (WATCHED_PROP), and its class


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


def options(settings):
    """The two options as saved: reorder (a tab released on or near the main tab bar docks there) and
    no_undock (a main window tab never stays in a window of its own). A value that is not a boolean (a
    hand-edited file) counts as the default."""
    found = {}
    for key, default in DEFAULT_OPTIONS.items():
        value = settings.get(key, default) if isinstance(settings, dict) else default
        found[key] = value if isinstance(value, bool) else default
    return found


def _options():
    """The options tab docking runs with now (the defaults before start() has set them)."""
    found = _state().get("options")
    return found if isinstance(found, dict) else dict(DEFAULT_OPTIONS)


def is_on():
    return bool(_state().get("on"))


def summary(chosen, on=True):
    """One plain sentence saying what is on, for the Output panel."""
    if not on or not (chosen.get("reorder") or chosen.get("no_undock")):
        return u"FreeLab tab docking is off: FontLab handles tab dragging again."
    if chosen.get("reorder") and chosen.get("no_undock"):
        return (u"FreeLab tab docking is on: drag a tab along the tab bar to move it; a tab cannot be dragged "
                u"out of the main window.")
    if chosen.get("reorder"):
        return (u"FreeLab tab docking is on: drag a tab along the tab bar to move it; released on or near "
                u"the tab bar, a tab goes back into the main window.")
    return u"FreeLab tab docking is on: a tab cannot be dragged out of the main window."


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


FRAME_CLASSES = ("MainWindow", "YFrameWindow")  # the windows that hold document tabs


def _document_tab(widget):
    """(widget, its frame) when widget is a document area's tab widget, else None."""
    if _class(widget) != "YTabWidget":
        return None
    frame = widget.parentWidget()
    if frame is not None and _class(frame) == "YFrameWindow":
        return widget, frame
    return None


def _alive(widget):
    return bool(_class(widget))  # (a deleted object's wrapper raises: no class name)


def document_tab_widgets():
    """(tab widget, its frame) of every document area: the main window's and each window of its own.

    Looked for from the windows that hold them (FontLab's main window, and each of its windows of their
    own), through Qt's typed search, which wraps only the tab widgets: the walk over every widget it
    replaces wrapped some 5,000 each second, and the crashes of November 14 all came at the end of it
    (PythonQt freeing a wrapper twice). Where the typed search finds nothing (PythonQt gives nothing for
    findChildren(QWidget), and may give nothing for a class here too), the whole walk is made, but only
    when the set of those windows has changed since the walk before."""
    QtGui = _qt()[1]
    state = _state()
    windows = [w for w in QtGui.QApplication.topLevelWidgets() if _class(w) in FRAME_CLASSES]
    found = []
    tab_class = getattr(QtGui, "QTabWidget", None)
    if tab_class is not None:
        for window in windows:
            try:
                for widget in window.findChildren(tab_class):
                    pair = _document_tab(widget)
                    # (once each: a window of its own is a top-level window and a child of the main window too,
                    # and came twice, read live 2026-11-24)
                    if pair is not None and not any(pair[0] == known for known, _ in found):
                        found.append(pair)
            except Exception:
                continue
    if found:
        state["tab_walk"] = None
        return found
    signature = tuple(sorted(repr(w) for w in windows))
    walked = state.get("tab_walk")
    if walked is not None and walked[0] == signature and (walked[1] or time.time() - walked[2] < EMPTY_WALK_SECONDS):
        kept = [(w, f) for w, f in walked[1] if _alive(w) and _alive(f)]
        if len(kept) == len(walked[1]):
            return kept
        # (one of them deleted: a window docked and another torn off may have taken its address, and the
        # same signature: walked again)
    for widget in QtGui.QApplication.instance().allWidgets():
        pair = _document_tab(widget)
        if pair is not None:
            found.append(pair)
    state["tab_walk"] = (signature, found, time.time())
    return found


EMPTY_WALK_SECONDS = 30  # a walk that found no document area (FontLab still building its window) is made again this late


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

CROSS_WIDTH = 24  # the close cross's zone: this far from a tab's left end
CROSS_INSET, CROSS_SIZE = 5, 16  # FreeLab's own cross: this far in from the tab's left end, this wide
HOVER_MS = 80  # how often the tab under the mouse is looked for, while the mouse is over the main tab bar
ENTER_EVENT = 10  # QEvent::Enter


def cross_zone(bar, index):
    """(left, right) in the bar of a tab's close cross, or None: the tab's left end. Read from
    closing clicks made by hand, 2026-11-24 (8 to 13 pixels from the left edge of tabs 571 wide, their titles
    centered far to the right); two earlier guesses, the tab's right end and the place of its icon, each
    left the cross needing two clicks. Never raises."""
    try:
        if bar is None or index < 0 or not bar.tabsClosable:
            return None
        rect = bar.tabRect(index)
        return rect.left(), rect.left() + CROSS_WIDTH
    except Exception:
        return None


def on_close_cross(bar, index, pos):
    """Whether a press at pos (in the bar) lies on a tab's close cross (cross_zone). Never raises."""
    zone = cross_zone(bar, index)
    try:
        return zone is not None and pos is not None and zone[0] <= pos.x() < zone[1]
    except Exception:
        return False


def on_pressed(tab_widget, index, bar=None, pos=None):
    """A press on a document tab (the bar's event filter): the tab a drag would take, then the mouse
    followed until it is released. FontLab takes the tab out of its bar as the drag starts."""
    state = _state()
    state["own_press"] = None
    if index < 0:
        state["drag"] = None
        return False
    # (where it was pressed: no_undock puts a main window tab back there, and leaves one that was in a
    # window of its own already to FontLab)
    from_main = _in_main_window(tab_widget)
    # no_undock: the press on a main window tab is kept from FontLab's tab bar, which then has no tab to
    # take away (the review of 2026-11-23: put back after the drop, a tab could still be grabbed, which was
    # the nuisance). With reorder FreeLab follows the mouse itself and moves the tab along the bar at the
    # release; no window is ever made. Nothing is chosen at the press: a click chooses its tab at the
    # release (on_released), so that the view does not change under a tab being moved (the review of
    # 2026-11-23).
    # (but a press on the tab's close cross, which is the bar's own: kept, the cross took two clicks; and
    # handed to the bar afterwards as a click made up here, the cross was no longer shown, a held tab was
    # chosen after two seconds, and a window no longer merged into another, the review of 2026-11-23. FontLab
    # follows the mouse beneath Qt's events, and a made-up click left it waiting for a release.)
    # (2026-11-24: FontLab showed no cross on main window tabs once their presses were kept from it, and
    # its own took two clicks. A press on the cross's place is kept like any other, and closes the tab at
    # its release there, _end_own; FreeLab shows a cross of its own on the tab under the mouse,
    # hover_cross.)
    own = bool(_options()["no_undock"] and from_main)
    on_cross = own and on_close_cross(bar, index, pos)
    if from_main:
        zone = cross_zone(bar, index)
        _note("press at %s, cross zone %s, %s" % (None if pos is None else pos.x(), zone, "kept" if own else "FontLab's"),
              "presses")
    drag = {"page": tab_widget.widget(index), "start": cursor_pos(), "started": False,
            "from_main": from_main, "index": index, "own": own, "tabs": tab_widget, "bar": bar,
            "at": None if pos is None else (pos.x(), pos.y()), "cross": on_cross}
    state["drag"] = drag
    if own:
        state["own_press"] = drag
    if from_main and not on_cross:
        try:  # (the tab shown at the press: kept until the release, hold_view)
            drag["shown"], drag["count"] = tab_widget.currentIndex, tab_widget.count
        except Exception:
            pass
    timer = state.get("poll_timer")
    if timer is not None:
        timer.start()
    return own


def on_window_moved(frame):
    """A window of its own moved (the filter on it, each step of a drag by its title bar): followed as a tab's
    drag is, so that released with the mouse on the main tab bar it docks there, at the marker's place.
    FontLab docks such a window only where its own blue highlight shows, which was hard to get (the review of
    2026-11-23). reorder only, and only while the mouse button is held: a window moved by a program, or
    snapped by Windows, is not being dragged."""
    state = _state()
    if state.get("drag") is not None or not _options()["reorder"]:
        return
    if not frame.isWindow() or not button_down():
        return  # (a tab bar moved in its layout sends the same event: no window)
    for tab_widget, holder in document_tab_widgets():
        if (holder is frame or holder == frame) and holder.isWindow():
            page = tab_widget.currentWidget()
            if page is None:
                return
            state["drag"] = {"page": page, "start": cursor_pos(), "started": True, "from_main": False,
                             "index": -1, "own": False, "window": True}
            timer = state.get("poll_timer")
            if timer is not None:
                timer.start()
            return


def on_released():
    """The release that ends a press FreeLab kept from the tab bar (on_pressed): kept from it too, since the
    bar never saw the press. True when kept. What the press was for is done from here, once the filter has
    returned: a click (the mouse not moved) handed to the bar, a drag ended (finish_own)."""
    state = _state()
    held = state.get("own_press")
    state["own_press"] = None
    if not held:
        return False
    drag = held
    if drag.get("released"):
        return True  # (poll saw the button up first, and ended the drag)
    if button_down():
        # A release with the button still held is not a real one (the review of 2026-11-23: a tab held some two
        # seconds without moving was shown, as if clicked): kept from the bar like the real one, which is
        # still to come, or which poll sees.
        state["own_press"] = held
        _note("a release came with the button still held")
        return True
    _end_own(drag, cursor_pos())
    return True


def _end_own(drag, point):
    """The end of a press FreeLab kept, once: a click (the mouse not moved) chooses its tab, a drag is ended
    (finish_own), both once the filter or the timer that saw the release has returned."""
    drag["released"] = True
    start = drag["start"]
    moved = drag["started"] or abs(point.x() - start.x()) + abs(point.y() - start.y()) >= drag_distance()
    if moved:
        _later_in(0, "finish_own", drag["page"], drag["index"], point, True)
    elif drag.get("cross") and _released_on_cross(drag, point):
        _later_in(0, "close_tab", drag.get("tabs"), drag["page"])
    else:
        _later_in(0, "choose_tab", drag.get("tabs"), drag["page"])
        if _options()["no_undock"] and drag["index"] >= 0:
            _later("put_back", drag["page"], drag["index"])  # (should FontLab have made a window all the same)


def _released_on_cross(drag, point):
    """Whether a press on a tab's close cross was released on it too (as a button's click is). Never raises."""
    try:
        bar = drag.get("bar")
        return on_close_cross(bar, drag["index"], bar.mapFromGlobal(point))
    except Exception:
        return False


def close_tab(tab_widget, page):
    """A click on a main window tab's close cross (no_undock, whose presses FontLab never sees): the tab
    closed by FontLab's own slot, which asks about unsaved changes as its cross does. Not the Sketchboard."""
    try:
        at = tab_widget.indexOf(page)
        if at >= 0 and _class(page) != "YSketchBoard":
            tab_widget.onTabCloseRequested(at)
    except Exception as exc:
        print("FreeLab tab docking: %s" % (exc,))


def on_bar_entered(bar):
    """The mouse came over a tab bar (its filter): over the main window's, with no_undock, the tab under it
    is looked for until the mouse leaves, to show its close cross (hover_cross)."""
    state = _state()
    if not _options()["no_undock"] or not _in_main_window(bar.parentWidget()):
        return
    state["hover_bar"] = bar
    timer = state.get("hover_timer")
    if timer is not None and not timer.active:
        timer.start()


def _cross_label(bar):
    """FreeLab's close cross, a child of the bar (Qt deletes it with it) that takes no mouse event: the
    press goes to the bar's filter, like any press on the tab."""
    QtCore, QtGui = _qt()
    state = _state()
    label = state.get("cross_label")
    if label is None or not _alive(label) or label.parentWidget() is not bar:
        label = QtGui.QLabel(u"\u00d7", bar)
        label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont(bar.font)
        font.setPointSizeF(max(font.pointSizeF(), 8.0) + 3.0)
        label.setFont(font)
        label.hide()
        state["cross_label"] = label
    return label


def hover_cross():
    """The close cross shown at the left end of the main window tab under the mouse (no_undock: FontLab
    shows none on tabs it gets no press on, the review of 2026-11-24), and taken away as the mouse leaves the
    bar, which also ends the looking. Not on the Sketchboard, which does not close. Never raises."""
    state = _state()
    bar = state.get("hover_bar")
    try:
        inside = False
        if bar is not None and _alive(bar) and _options()["no_undock"] and bar.isVisible():
            local = bar.mapFromGlobal(cursor_pos())
            inside = 0 <= local.x() < bar.width and 0 <= local.y() < bar.height
        if not inside:
            _hide_cross()
            return
        index = bar.tabAt(local)
        tabs = bar.parentWidget()
        if index < 0 or cross_zone(bar, index) is None or _class(tabs.widget(index)) == "YSketchBoard":
            label = state.get("cross_label")
            if label is not None and _alive(label):
                label.hide()
            return
        label = _cross_label(bar)
        rect = bar.tabRect(index)
        label.setGeometry(rect.left() + CROSS_INSET, 0, CROSS_SIZE, bar.height)
        if not label.isVisible():
            label.show()
        label.raise_()
    except Exception:
        _hide_cross()


def _hide_cross():
    """FreeLab's cross hidden and the looking for a tab under the mouse ended. Never raises."""
    state = _state()
    try:
        timer = state.get("hover_timer")
        if timer is not None:
            timer.stop()
        label = state.get("cross_label")
        if label is not None and _alive(label):
            label.hide()
    except Exception:
        pass
    state["hover_bar"] = None


def _note(what, key="notes"):
    """Something unexpected, kept with its time (state["notes"], the last few; "presses": where the last
    presses on main window tabs were, against the close cross's zone), to be read when a review reports
    what it led to. Never raises."""
    try:
        notes = _state().setdefault(key, [])
        notes.append((time.strftime("%H:%M:%S"), what))
        del notes[:-12]
    except Exception:
        pass


def choose_tab(tab_widget, page):
    """A click FreeLab kept from the tab bar (no_undock) chooses its tab, as FontLab's own would have at the
    press."""
    try:
        at = tab_widget.indexOf(page)
        if at >= 0 and tab_widget.currentIndex != at:
            tab_widget.setCurrentIndex(at)
    except Exception as exc:
        print("FreeLab tab docking: %s" % (exc,))


def finish_own(page, index, point, moved):
    """The end of a drag whose press FreeLab kept (no_undock): the tab is still in the main window. Moved
    and released on or near the bar, it goes to the marker's place (reorder); moved and released anywhere
    else, it stays where it is and is chosen, as FontLab's own press would have."""
    chosen = _options()
    bar, main = main_tabs()
    if moved and main is not None:
        if chosen["reorder"] and near_bar(bar, main, point):
            dock(page, drop_slot(bar, point, main.widget, page))
            return
        try:
            at = main.indexOf(page)
            if at >= 0 and main.currentIndex != at:
                main.setCurrentIndex(at)
        except Exception as exc:
            print("FreeLab tab docking: %s" % (exc,))
    if chosen["no_undock"] and index >= 0:
        _later("put_back", page, index)  # (should FontLab have made a window all the same)


def _in_main_window(tab_widget):
    """True when tab_widget is the main window's document area (not a window of its own)."""
    try:
        frame = tab_widget.parentWidget()
        return frame is not None and frame.objectName == MAIN_FRAME_NAME and not frame.isWindow()
    except Exception:
        return False


def on_dropped(tab_widget):
    """FontLab's drop signal: no longer used (the release is followed instead); kept for connections
    an earlier version made in this FontLab session."""
    return None


def poll():
    """While a drag is followed: the marker where the tab would go (reorder); at the release, the tab
    docked back if it is on or near the main tab bar (reorder), else put back where it was pressed if it
    came from the main window (no_undock)."""
    state = _state()
    drag = state.get("drag")
    if drag is None:
        _stop_polling()
        return
    chosen = _options()
    point = cursor_pos()
    # (a tick that comes late: FontLab was busy meanwhile, as when its blue highlight comes up; kept in the
    # drag's trace, to tell where a stall seen falls)
    now, last = time.time(), drag.get("tick")
    drag["tick"] = now
    if last is not None and now - last > STALL_SECONDS:
        _trace(drag, "stalled %d ms" % ((now - last) * 1000))
    if button_down():
        if not drag["started"]:
            moved = abs(point.x() - drag["start"].x()) + abs(point.y() - drag["start"].y())
            drag["started"] = moved >= drag_distance()
        if drag["started"] and chosen["reorder"]:
            show_marker(drag["page"], point, WINDOW_MARGIN if drag.get("window") else TEAR_MARGIN)
        if "shown" in drag:
            hold_view(drag)
        follow_drop(drag)
        return
    _stop_polling()
    hide_marker()
    state["drag"] = None
    _trace(drag, "released")
    for delay in TRACE_AFTER_MS:
        _later_in(delay, "trace_after", drag)
    page = drag["page"]
    if page is None:
        return
    if drag.get("reverted") and not drag["started"] and not drag.get("own"):
        _later("choose_tab", drag.get("tabs"), page)  # (a click whose tab FreeLab held back: chosen now)
    if drag.get("own"):
        # (the press was kept from FontLab: ended by its release, on_released; here only when the bar was
        # not given that release)
        if not drag.get("released"):
            _end_own(drag, point)
        return
    if chosen["reorder"] and drag["started"]:
        bar, main = main_tabs()
        if main is not None and near_bar(bar, main, point, WINDOW_MARGIN if drag.get("window") else TEAR_MARGIN):
            _later("dock_after_drop", page, drop_slot(bar, point, main.widget, page),
                   bool(drag.get("from_main")), drag.get("index", -1))
            return
    if chosen["no_undock"] and drag.get("from_main") and drag.get("index", -1) >= 0:
        # Not only after a drag that passed the start distance: whether FontLab made a window is looked
        # at after its drop (put_back), and a tab still in the main window is left alone.
        _later("put_back", page, drag["index"])
    # (else released away: a window of its own, as FontLab made it)


STALL_SECONDS = 0.2  # a poll tick this late (they come every POLL_MS) is noted in the drag's trace
HOLD_REVERTS = 2  # how many times the tab shown is put back under a held press, before FontLab is let be
TRACE_AFTER_MS = (100, 300, 600, 1000, 1500)  # after a release, when FontLab's own drop is looked at again


def hold_view(drag):
    """The tab shown kept as it was at the press, while the press is held and the mouse has not moved:
    FontLab shows a tab held some two seconds, as if clicked (the review of 2026-11-23 and 24, with its own
    press as with one FreeLab kept). Put back at most HOLD_REVERTS times; the tab is chosen at the release
    (poll, or the kept press's own end). Not once a drag has started, nor when the bar has lost or gained a
    tab (FontLab took it for its drag). Never raises."""
    try:
        tabs = drag.get("tabs")
        shown = drag["shown"]
        if tabs is None or drag["started"] or tabs.count != drag.get("count", tabs.count):
            del drag["shown"]
            return
        if tabs.currentIndex == shown:
            return
        _note("the tab shown changed while a press was held")
        _trace(drag, "tab shown changed to %s" % (tabs.currentIndex,))
        if drag.get("reverted", 0) >= HOLD_REVERTS:
            del drag["shown"]
            return
        drag["reverted"] = drag.get("reverted", 0) + 1
        tabs.setCurrentIndex(shown)
    except Exception:
        drag.pop("shown", None)


def _drop_parts(frame):
    """(FontLab's drop timer, its blue highlight or None) of a document area's frame: the frame's own
    QTimer child (YFrameWindow.dropTimerOnTimeout is its slot) and its YDropHighlight child, made at the
    first drag over it."""
    timer = highlight = None
    for child in frame.children():
        name = _class(child)
        if name == HIGHLIGHT_CLASS:
            highlight = child
        elif name == "QTimer" and timer is None:
            timer = child
    return timer, highlight


def follow_drop(drag):
    """FontLab's own drop target on the main window, each step of a drag. Never raises.

    A tab dragged out of the main window: FontLab's blue highlight came up over the document area the tab
    had just left, and a release there put the tab back, which made undocking hard (the review of 2026-11-24).
    The highlight is hidden while the drag is young (grace_over), then left to FontLab.

    (The frame's QTimer, taken for FontLab's wait before the highlight, never ran in 25 drags followed live
    on 2026-11-24: it is only read here, for the trace. The wait and the stall seen as the
    highlight came up were dark mode's, mapping the widgets under it at each repaint.)

    What is seen is kept (_trace), to be read when a review reports how it went."""
    hold_paint(drag)
    try:
        frame = drag.get("frame")
        if frame is None or not _alive(frame):
            bar, main = main_tabs()
            frame = drag["frame"] = main.parentWidget() if main is not None else None
            if frame is None:
                return
        timer, highlight = _drop_parts(frame)
        active = bool(timer is not None and timer.active)
        interval = timer.interval if timer is not None else None
        lit = bool(highlight is not None and highlight.isVisible())
        seen = (active, interval, lit, drag["tabs"].count if drag.get("tabs") is not None else None)
        if seen != drag.get("seen"):
            drag["seen"] = seen
            _trace(drag, "drop timer %s (%s ms), highlight %s, tabs %s" % (
                "running" if active else "idle", interval, "shown" if lit else "hidden", seen[3]))
        if not _options()["reorder"]:
            return
        if drag.get("from_main") and not drag.get("own") and not drag.get("window"):
            if not grace_over(drag, frame) and lit:
                highlight.hide()
    except Exception:
        pass


HIGHLIGHT_GRACE_SECONDS = 1.5  # how long a tab just dragged out is not offered its own area back


def grace_over(drag, frame):
    """Whether a tab dragged out of the main window may be offered the main window again. Not at first: the
    blue highlight over the area the tab had just left made undocking hard (the review of 2026-11-24). Once the
    tab has been held HIGHLIGHT_GRACE_SECONDS, or the mouse has left the document area, FontLab's highlight
    is its own again: hidden at every step for the whole drag, it flashed and went each time FontLab showed
    it, as if the tab could never be docked back (the review, the same day). Never raises."""
    try:
        if drag.get("grace_over"):
            return True
        begun = drag.setdefault("followed", time.time())
        over = time.time() - begun >= HIGHLIGHT_GRACE_SECONDS
        if not over:
            local = frame.mapFromGlobal(cursor_pos())
            over = not (0 <= local.x() < frame.width and 0 <= local.y() < frame.height)
        if over:
            drag["grace_over"] = True
            _trace(drag, "the highlight is FontLab's again")
        return over
    except Exception:
        return True


PAINT_HOLD_SECONDS = 1.5  # how long after a drag's last step dark mode still holds its pictures


def hold_paint(drag):
    """Dark mode told a drag is on, at each of its steps: it holds large widgets' pictures meanwhile, in place
    of mapping each anew at every repaint under FontLab's blue highlight (see its HOLD_PIXELS; a window
    dragged over the main window stalled for 2.1 seconds each time the highlight came up, the review of
    2026-11-24). Left on sys, which both modules read: neither imports the other. Never raises."""
    try:
        import sys
        now = time.time()
        sys._freelab_paint_hold = (drag.setdefault("hold", now), now + PAINT_HOLD_SECONDS)
    except Exception:
        pass


def _trace(drag, what):
    """A step of a drag, with the milliseconds since its press (state["traces"]: the last few drags).
    Never raises."""
    try:
        steps = drag.get("trace")
        if steps is None:
            steps = drag["trace"] = []
            drag["t0"] = time.time()
            traces = _state().setdefault("traces", [])
            traces.append(steps)
            del traces[:-12]
            steps.append((time.strftime("%H:%M:%S"), "from main" if drag.get("from_main") else
                          "a window" if drag.get("window") else "from a window", "kept" if drag.get("own") else ""))
        if len(steps) < 60:
            steps.append((int((time.time() - drag["t0"]) * 1000), what))
    except Exception:
        pass


def trace_after(drag):
    """After a release: how FontLab's own drop stands (its timer, its highlight, the windows of their own)."""
    try:
        frame = drag.get("frame")
        if frame is None or not _alive(frame):
            return
        timer, highlight = _drop_parts(frame)
        windows = len([1 for widget, holder in document_tab_widgets() if holder.isWindow() and holder.isVisible()])
        _trace(drag, "after: drop timer %s, highlight %s, windows %s" % (
            "running" if timer is not None and timer.active else "idle",
            "shown" if highlight is not None and highlight.isVisible() else "hidden", windows))
    except Exception:
        pass


DOCK_RETRY_MS, DOCK_RETRIES = 250, 2  # Merge Window not yet available just after a drop: asked again this late


def dock_retry(page, slot, left):
    """A dock that failed just after a drop tried again (FontLab's Merge Window stayed unavailable for the
    window just dropped, twice in one session, 2026-11-24), while the tab is still in a window of its own."""
    if not _alive(page) or holder_of(page) is None or not _options()["reorder"]:
        return
    if dock(page, slot):
        refresh_main()
    elif left > 1:
        _later_in(DOCK_RETRY_MS, "dock_retry", page, slot, left - 1)


def _later(function, *args):
    """function(*args) through the dispatcher once FontLab has finished its own drop."""
    _later_in(DOCK_DELAY_MS, function, *args)


def _later_in(delay, function, *args):
    """function(*args) through the dispatcher, delay milliseconds from now."""
    QtCore = _qt()[0]
    state = _state()
    later = (lambda call: lambda: call(function, *args))(_dispatcher())
    state["pending"].append(later)
    del state["pending"][:-16]  # the last few kept alive until they have run
    QtCore.QTimer.singleShot(delay, later)


def _stop_polling():
    timer = _state().get("poll_timer")
    if timer is not None:
        timer.stop()


def dock_after_drop(page, slot, from_main=False, index=-1):
    """A tab released on or near the bar docked at its slot, once FontLab's own drop is over. Decided with
    the options of now, not of the release (Codex, 2026-11-23: reorder switched off within the delay, the
    tab still went to the marker's place): without reorder, a main window tab goes back where it was
    pressed when no_undock is on, and nothing is docked otherwise."""
    chosen = _options()
    if not chosen["reorder"]:
        if chosen["no_undock"] and from_main and index >= 0:
            put_back(page, index)
        return
    if not dock(page, slot) and _alive(page) and holder_of(page) is not None:
        _later_in(DOCK_RETRY_MS, "dock_retry", page, slot, DOCK_RETRIES)
    refresh_main()


def put_back(page, index):
    """no_undock: a main window tab that FontLab made a window of its own of (on the drop, wherever it
    was) merged back, at the index it had when pressed (valid then; clamped to the bar by dock). One
    still in the main window (a click, or a drag FontLab did nothing with) is left alone. True when
    put back."""
    if not _options()["no_undock"]:
        return False
    if not _alive(page) or holder_of(page) is None:  # (not alive: the click was on its close cross)
        return False
    done = dock(page, index)
    refresh_main()
    return done


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
    clear_highlight()
    for delay in HIGHLIGHT_CHECKS_MS:  # (FontLab shows it from a timer of its own, which may come after the merge)
        _later_in(delay, "clear_highlight")


HIGHLIGHT_CLASS = "YDropHighlight"  # FontLab's blue drop highlight: a child of a document area's frame, hidden but in a drag
HIGHLIGHT_CHECKS_MS = (400, 1500)


def clear_highlight():
    """FontLab's blue drop highlight hidden where it shows with no mouse button held: it stayed over the
    whole document area after a window was merged by Merge Window while FontLab was showing a drop for it
    (the review of 2026-11-23; read live: still visible minutes later, no drag, no window of its own left).
    FontLab shows it again at its next drag. The number hidden; never raises."""
    count = 0
    try:
        if button_down():
            return 0
        for tab_widget, frame in document_tab_widgets():
            for child in frame.children():
                if _class(child) == HIGHLIGHT_CLASS and child.isVisible():
                    child.hide()
                    count += 1
    except Exception:
        pass
    return count


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


def show_marker(page, point, margin=TEAR_MARGIN):
    """The marker at the gap the tab would go into, when the mouse is on or near the main tab bar (and
    reorder is on: no_undock alone docks nowhere new)."""
    QtCore, QtGui = _qt()
    if not _options()["reorder"]:
        hide_marker()
        return
    bar, main = main_tabs()
    if main is None or not near_bar(bar, main, point, margin):
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
    asked = time.time()
    frame.raise_()
    frame.activateWindow()
    active = None
    for attempt in range(ACTIVATE_TRIES):
        # (looked at before any event is processed: a window just dropped is the active one already, and
        # processing FontLab's pending events first was most of a dock's wait, read live 2026-11-24)
        try:
            active = QtGui.QApplication.activeWindow()
        except Exception:
            active = None  # not known: merged as before
        if actions[0].isEnabled() and (active is None or active is frame or active == frame
                                       or _class(active) != "YFrameWindow"):
            break
        QtGui.QApplication.processEvents()
        time.sleep(ACTIVATE_WAIT)
        if attempt == ACTIVATE_TRIES // 2:
            frame.activateWindow()  # (asked once more: another window had taken the activation back)
    if not actions[0].isEnabled():
        return _fail(u"FontLab's Merge Window command stayed unavailable for %s (the active window: %s)."
                     % (_describe(frame), _describe(active)))
    if active is not None and active is not frame and active != frame and _class(active) == "YFrameWindow":
        # another window of its own is still the active one: Merge Window would merge that one
        return _fail(u"another window stayed the active one (%s), not %s." % (_describe(active), _describe(frame)))
    began = time.time()
    actions[0].trigger()
    QtGui.QApplication.processEvents()
    _note("Merge Window took %d ms, after %d ms to make its window active (%d tries)" % (
        (time.time() - began) * 1000, (began - asked) * 1000, attempt + 1), "merges")
    return True


def dock(page, target=None):
    """Put a document tab into the main window (merging the window that holds it), at target if given;
    a window it left empty is closed (FontLab keeps it open, and merging it does nothing)."""
    steps, began = [], time.time()

    def step(name):
        steps.append("%s %d ms" % (name, (time.time() - began) * 1000))

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
        step("merged at")
        at = main.indexOf(page)
        if at < 0:
            return _fail(u"FontLab's Merge Window ran, but the tab is not in the main window.")
    if target is not None and bar.count > 0:
        # (clamped: a place found at the press or the release may be past the end if a tab closed since)
        target = max(0, min(target, bar.count - 1))
        if target != at:
            bar.moveTab(at, target)
    step("moved at")
    for widget, frame in document_tab_widgets():
        if frame.isWindow() and frame.isVisible() and widget.count == 0:
            frame.close()
    step("empty windows closed at")
    main.setCurrentIndex(main.indexOf(page))
    step("tab chosen at")
    window = main_window()
    if window is not None:
        window.activateWindow()
    step("main window made active at")
    # (where a dock's time goes, kept to be read when a slow one is reported: state["merges"])
    _note("dock: " + ", ".join(steps), "merges")
    return True


def dock_frame(tab_widget):
    """A window of its own docked (its Dock button, a double-click on its tab): reorder's, so nothing while
    it is off (a click or a filter queued before the option changed, or an earlier version's filter)."""
    if not _options()["reorder"]:
        return
    page = tab_widget.currentWidget()
    if page is not None:
        dock(page)
        refresh_main()


def on_double_click(tab_widget):
    """A double-click on a document tab (the bar's event filter): True when taken, to dock the window of
    its own that holds it (reorder only; otherwise, and on a main window tab, the double-click is
    FontLab's). Decided here rather than in the filter, so that a reloaded module decides."""
    if not _options()["reorder"]:
        return False
    frame = tab_widget.parentWidget() if tab_widget is not None else None
    if frame is None or not frame.isWindow():
        return False
    QtCore = _qt()[0]
    state = _state()
    later = (lambda call: lambda: call("dock_frame", tab_widget))(_dispatcher())
    state["pending"].append(later)
    del state["pending"][:-16]
    QtCore.QTimer.singleShot(0, later)
    return True


# ---------------------------------------------------------------------------
# FontLab's Undock commands, hidden while no_undock is on
# ---------------------------------------------------------------------------

def undock_actions():
    """Window > Docking's Undock commands (QActions of the main window). Kept once found, while each is
    alive: watch() asks every second, and the typed search wraps every action of the main window. Where
    none is found, searched again only this late (EMPTY_WALK_SECONDS)."""
    QtGui = _qt()[1]
    state = _state()
    found = state.get("undock_actions")
    if found and all(_alive(action) for action in found):
        return found
    if found is not None and not found and time.time() - state.get("undock_search", 0) < EMPTY_WALK_SECONDS:
        return []
    main = main_window()
    found = [a for a in main.findChildren(QtGui.QAction) if a.objectName in UNDOCK_ACTIONS] if main is not None else []
    state["undock_actions"], state["undock_search"] = found, time.time()
    return found


def hide_undock():
    """Hide the Undock commands that are shown (each pass: FontLab may show them again), noting the ones
    FreeLab hid, so that only those are shown again. FontLab's enabling of them is left as it is. The
    number newly hidden."""
    state = _state()
    hidden = state.setdefault("undock_hidden", [])
    count = 0
    for action in undock_actions():
        if action.isVisible():
            action.setVisible(False)
            count += 1
            # (the action itself, not its name: one FontLab made anew under the same name was never hidden
            # by FreeLab, and is not FreeLab's to show; Codex, 2026-11-23)
            if all(action is not known for known in hidden):
                hidden.append(action)
    return count


def show_undock():
    """Show again the Undock commands FreeLab hid (no_undock switched off, or tab docking stopped)."""
    state = _state()
    hidden = state.get("undock_hidden") or []
    state["undock_hidden"] = []
    for action in hidden:
        try:
            if _alive(action):  # (one deleted since is gone with its menu entry)
                action.setVisible(True)
        except Exception:
            continue


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
    button.setToolTip(DOCK_TIP)
    handler = (lambda call: lambda *args: call("dock_frame", tab_widget))(_dispatcher())
    _state()["held"].append(handler)
    button.connect("clicked()", handler)
    tab_widget.setCornerWidget(button, corner)
    button.show()


def _filter_class():
    QtCore = _qt()[0]
    state = _state()
    if FILTER_CLASS_KEY not in state:
        call = _dispatcher()  # (the closure's: this module's globals may be gone when it runs)

        class TabPresses(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            """On a document tab bar: a press starts following a possible drag; a double-click on a
            tab of a window of its own docks that window (on_double_click decides; while off, the
            dispatcher calls nothing and the double-click is FontLab's)."""

            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == ENTER_EVENT:  # (the mouse over a tab bar: its close cross, no_undock)
                        call("on_bar_entered", obj)
                        return False
                    if kind == MOVE_EVENT:  # (on a window of its own: dragged by its title bar)
                        call("on_window_moved", obj)
                        return False
                    if kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                        # (True: kept from the bar, so that FontLab has no tab to drag away, no_undock)
                        return bool(call("on_pressed", obj.parentWidget(), obj.tabAt(event.pos()), obj, event.pos()))
                    elif kind == getattr(QtCore.QEvent, "MouseButtonRelease", 3) and event.button() == QtCore.Qt.LeftButton:
                        return bool(call("on_released"))
                    elif kind == QtCore.QEvent.MouseButtonDblClick and obj.tabAt(event.pos()) >= 0:
                        return bool(call("on_double_click", obj.parentWidget()))
                except Exception:
                    pass  # an event filter must never raise
                return False
        state[FILTER_CLASS_KEY] = TabPresses
    return state[FILTER_CLASS_KEY]


def _drop_old_filters(bar):
    """An earlier version's filter taken off a tab bar (those FreeLab holds whose parent is the bar): the one
    before the options took a double-click on a window's tab and docked it itself, whatever reorder says,
    and stayed on its bar when FreeLab was installed again in the same FontLab session (Codex, 2026-11-23).
    The filter object stays held: Qt deletes it with its bar. Never raises."""
    state = _state()
    current = state.get(FILTER_CLASS_KEY)
    for held in state.get("held", []):
        try:
            if not hasattr(held, "eventFilter") or (current is not None and isinstance(held, current)):
                continue
            parent = held.parent()
            if parent is bar or parent == bar:
                bar.removeEventFilter(held)
        except Exception:
            continue


def _follow_moves(frame):
    """A window of its own given the filter that follows its moves (on_window_moved), once: dragged by its
    title bar onto the main tab bar, it docks there. True when it was put on. A window that will not take
    it is left as it is (its tab bar is hooked all the same). Never raises."""
    try:
        if not frame.isWindow() or frame.property(FRAME_PROP) == FILTER_REVISION:
            return False
        moves = _filter_class()(frame)  # (its parent the window: Qt deletes it with it, never PythonQt)
        _state()["held"].append(moves)
        frame.installEventFilter(moves)
        frame.setProperty(FRAME_PROP, FILTER_REVISION)
        return True
    except Exception:
        return False


def watch(force=False):
    """Hook every document tab bar not hooked yet, and give windows of their own their Dock button. Each
    document area found is looked at every pass, a few calls each (whether its bar is hooked, its Dock
    button there): a key of the areas' addresses was no proof, as a window docked and another torn off
    within one pass may take the same address. True when something was hooked or added. (force: kept
    for callers of an earlier version; every pass looks.) The Dock buttons only while reorder is on; the
    Undock commands hidden again while no_undock is on (FontLab may show them again)."""
    QtCore, QtGui = _qt()
    state = _state()
    chosen = _options()
    changed = False
    for tab_widget, frame in document_tab_widgets():
        try:
            if frame.isWindow() and chosen["reorder"]:
                button = tab_widget.findChild(QtGui.QToolButton, DOCK_BUTTON_NAME)
                if button is None:
                    _add_dock_button(tab_widget)
                    changed = True
                elif tab_widget.cornerWidget(QtCore.Qt.TopRightCorner) is None:  # put back after an off
                    tab_widget.setCornerWidget(button, QtCore.Qt.TopRightCorner)
                    button.show()
                    changed = True
            changed = _follow_moves(frame) or changed
            bar = _bar_of(tab_widget)
            if bar is not None and bar.property(WATCHED_PROP) != FILTER_REVISION:
                _drop_old_filters(bar)  # (2: the filter before the options, which docked on a double-click itself)
                presses = _filter_class()(bar)  # (its parent the bar: Qt deletes it with it, never PythonQt)
                state["held"].append(presses)
                bar.installEventFilter(presses)
                bar.setProperty(WATCHED_PROP, FILTER_REVISION)  # (1 or True: a filter that does nothing now)
                changed = True
        except Exception as exc:
            print("FreeLab tab docking: %s" % (exc,))
    try:
        if chosen["no_undock"]:
            changed = bool(hide_undock()) or changed
        elif state.get("undock_hidden"):
            show_undock()
    except Exception as exc:
        print("FreeLab tab docking: %s" % (exc,))
    return changed


def _timer(key, interval, function):
    """A fresh timer calling function through the dispatcher (an earlier one stopped and replaced)."""
    QtCore = _qt()[0]
    state = _state()
    old = state.get(key)
    if old is not None:
        old.stop()
        # (kept: a timer made from Python with no parent is deleted by PythonQt as its last reference goes,
        # at whatever moment that is)
        state.setdefault("held", []).append(old)
    timer = QtCore.QTimer()
    timer.setInterval(interval)
    tick = (lambda call: lambda: call(function))(_dispatcher())
    state[key + "_tick"] = tick
    timer.connect("timeout()", tick)
    state[key] = timer
    return timer


def start(chosen=None):
    """On, with the options given (else those saved)."""
    state = _state()
    state["on"] = True
    state["module"] = sys.modules.get(__name__)  # what the dispatcher calls, should FontLab drop it
    _timer("timer", WATCH_MS, "watch").start()
    _timer("poll_timer", POLL_MS, "poll")
    _timer("hover_timer", HOVER_MS, "hover_cross")
    apply_options(options(load_settings()) if chosen is None else chosen)  # (watch: the Dock buttons put back after an off)


def apply_options(chosen):
    """The options in force at once, without a restart: reorder off takes the marker and the Dock buttons
    away (windows of their own stay as they are); no_undock hides FontLab's Undock commands, and off
    shows again the ones it hid."""
    state = _state()
    chosen = options(chosen)
    state["options"] = chosen
    if not chosen["reorder"]:
        hide_marker()
        _remove_dock_buttons()
    if not chosen["no_undock"]:
        try:
            show_undock()
        except Exception as exc:
            print("FreeLab tab docking: %s" % (exc,))
    if state.get("on"):
        watch(force=True)  # (Dock buttons added, the Undock commands hidden)


def _remove_dock_buttons():
    QtCore, QtGui = _qt()
    for tab_widget, frame in document_tab_widgets():
        button = tab_widget.findChild(QtGui.QToolButton, DOCK_BUTTON_NAME)
        if button is not None:
            tab_widget.setCornerWidget(None, QtCore.Qt.TopRightCorner)
            button.hide()


def stop():
    """Off: FontLab's own ways again. Filters stay (they do nothing while off); Dock buttons go, and the
    Undock commands FreeLab hid are shown."""
    state = _state()
    state["on"] = False
    state["drag"] = None
    _hide_cross()
    for key in ("timer", "poll_timer", "hover_timer"):
        if state.get(key) is not None:
            state[key].stop()
    hide_marker()
    _remove_dock_buttons()
    try:
        show_undock()
    except Exception as exc:
        print("FreeLab tab docking: %s" % (exc,))


def _anything(chosen):
    return bool(chosen["reorder"] or chosen["no_undock"])


def startup():
    """Called by FontLab's startup script: on unless switched off (or both options are)."""
    settings = load_settings()
    chosen = options(settings)
    if enabled_setting(settings) and _anything(chosen):
        start(chosen)


def configure(enabled=None, reorder=None, no_undock=None):
    """Save what is given (None: kept as saved) and apply it at once: started, stopped, or the options
    changed while running. Both options off is off. The settings as saved."""
    settings = load_settings()
    chosen = options(settings)
    if reorder is not None:
        chosen["reorder"] = bool(reorder)
    if no_undock is not None:
        chosen["no_undock"] = bool(no_undock)
    on = enabled_setting(settings) if enabled is None else bool(enabled)
    on = on and _anything(chosen)
    settings.update(chosen)
    settings["enabled"] = on
    save_settings(settings)
    if on and is_on():
        apply_options(chosen)
    elif on:
        start(chosen)
    elif is_on():
        stop()
    return dict(settings)


def toggle():
    """Scripts > FreeLab > Tab Docking: the master switch. On, with the options last chosen; with both
    off, reorder is switched on (and saved), so that on always does something."""
    settings = load_settings()
    on = not _state()["on"]
    chosen = options(settings)
    if on:
        if not _anything(chosen):
            chosen["reorder"] = True
        settings.update(chosen)
        start(chosen)
        message = summary(chosen) + u" Run this script again to switch it off."
    else:
        stop()
        message = summary(chosen, on=False)
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
