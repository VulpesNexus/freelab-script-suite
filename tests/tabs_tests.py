# -*- coding: utf-8 -*-
"""Tests of FreeLab's tab docking (where a dropped tab goes). Valid Python 2.7 and Python 3."""
from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "windows"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_tabs as ft  # noqa: E402

TAB_WIDTH, BAR_HEIGHT = 100, 24
unichr_ = chr if sys.version_info[0] > 2 else unichr  # noqa: F821 (Python 2's)


class Point(object):
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class Rect(object):
    def __init__(self, left, width):
        self.left_, self.width_ = left, width

    def center(self):
        return Point(self.left_ + self.width_ // 2, BAR_HEIGHT // 2)

    def left(self):
        return self.left_

    def width(self):
        return self.width_


class Page(object):
    def __init__(self, kind="FontWindow"):
        self.kind = kind

    def metaObject(self):
        kind = self.kind
        return type("Meta", (), {"className": lambda _self: kind})()


class Bar(object):
    """A tab bar at global (0, 100), its tabs TAB_WIDTH wide; the tab widget is 1000 wide."""
    height = BAR_HEIGHT
    width = 1000

    def __init__(self, count):
        self.count = count

    def isVisible(self):
        return True

    def mapFromGlobal(self, point):
        return Point(point.x(), point.y() - 100)

    def tabRect(self, index):
        return Rect(index * TAB_WIDTH, TAB_WIDTH)


class SlotTests(unittest.TestCase):
    def setUp(self):
        self.pages = [Page("YSketchBoard"), Page(), Page(), Page()]
        self.bar = Bar(len(self.pages))
        self.page_of = lambda index: self.pages[index]

    def slot(self, x, page):
        return ft.drop_slot(self.bar, Point(x, 110), self.page_of, page)

    def test_before_the_tab_whose_left_half_it_falls_on(self):
        dragged = Page()  # from another window: not on this bar
        self.assertEqual(self.slot(210, dragged), 2)
        self.assertEqual(self.slot(290, dragged), 3, "right half: after it")

    def test_past_the_last_tab_goes_last(self):
        self.assertEqual(self.slot(990, Page()), 4)

    def test_the_sketchboard_stays_first(self):
        self.assertEqual(self.slot(5, Page()), 1)

    def test_the_dragged_tab_itself_is_left_out(self):
        dragged = self.pages[3]
        self.assertEqual(self.slot(990, dragged), 3, "the last of the three others")
        self.assertEqual(self.slot(110, dragged), 1)


class MarkerTests(unittest.TestCase):
    def test_the_marker_sits_in_the_gap(self):
        pages = [Page("YSketchBoard"), Page(), Page()]
        bar = Bar(3)
        dragged = Page()
        self.assertEqual(ft.marker_x(bar, lambda i: pages[i], dragged, 1), TAB_WIDTH, "before the second tab")
        self.assertEqual(ft.marker_x(bar, lambda i: pages[i], dragged, 3), 3 * TAB_WIDTH, "after the last")

    def test_the_dragged_tab_still_on_the_bar_is_skipped(self):
        pages = [Page("YSketchBoard"), Page(), Page()]
        bar = Bar(3)
        self.assertEqual(ft.marker_x(bar, lambda i: pages[i], pages[1], 1), 2 * TAB_WIDTH)


class NearTests(unittest.TestCase):
    def setUp(self):
        self.bar = Bar(3)

    def near(self, x, y):
        return ft.near_bar(self.bar, self.bar, Point(x, y))

    def test_on_and_near_the_bar(self):
        self.assertTrue(self.near(500, 110))
        self.assertTrue(self.near(500, 100 + BAR_HEIGHT + ft.TEAR_MARGIN), "just below, within the margin")
        self.assertTrue(self.near(500, 100 - ft.TEAR_MARGIN), "just above")

    def test_pulled_away_is_a_window(self):
        self.assertFalse(self.near(500, 100 + BAR_HEIGHT + ft.TEAR_MARGIN + 1))
        self.assertFalse(self.near(1000 + ft.TEAR_MARGIN + 1, 110), "beside the bar")


class Widget(object):
    """A widget of a fake PythonQt: its parent, whether it is a window, and its update() calls."""

    def __init__(self, parent=None, window=False, kind="QWidget"):
        self.parent, self.window, self.kind, self.updates = parent, window, kind, 0

    def parentWidget(self):
        return self.parent

    def isWindow(self):
        return self.window

    def isVisible(self):
        return True

    def isAncestorOf(self, other):
        while other is not None:
            if other is self:
                return True
            other = other.parent
        return False

    def update(self):
        self.updates += 1

    def tabAt(self, pos):
        return 0

    def metaObject(self):
        kind = self.kind
        return type("Meta", (), {"className": lambda _self: kind})()


class FakeQt(object):
    """PythonQt's modules as the filter and the repaint use them, installed for one test."""

    def __init__(self, widgets=()):
        widgets = list(widgets)
        app = type("App", (), {"allWidgets": lambda _self: widgets})()
        self.QtGui = type("QtGui", (), {"QApplication": type("QApplication", (), {
            "instance": staticmethod(lambda: app)})})
        self.QtCore = type("QtCore", (), {
            "QTimer": type("QTimer", (object,), {"singleShot": staticmethod(lambda ms, function: self.later.append(function))}),
            "QEvent": type("QEvent", (), {"MouseButtonPress": 2, "MouseButtonRelease": 3, "MouseButtonDblClick": 4}),
            "Qt": type("Qt", (), {"LeftButton": 1})})
        self.later = []

    def __enter__(self):
        self.saved = (sys.modules.get("PythonQt"), getattr(sys, "_freelab_tabs_state", None))
        sys.modules["PythonQt"] = self
        sys._freelab_tabs_state = {"on": True}
        return self

    def __exit__(self, *exc):
        module, state = self.saved
        if module is None:
            sys.modules.pop("PythonQt", None)
        else:
            sys.modules["PythonQt"] = module
        if state is None:
            del sys._freelab_tabs_state
        else:
            sys._freelab_tabs_state = state
        return False


class Event(object):
    def __init__(self, kind):
        self.kind = kind

    def type(self):
        return self.kind

    def pos(self):
        return Point(0, 0)


class HookTests(unittest.TestCase):
    def test_a_double_click_docks_only_while_on(self):
        frame = Widget(window=True, kind="YFrameWindow")
        bar = Widget(Widget(frame))
        with FakeQt() as qt:
            presses = ft._filter_class()()
            self.assertTrue(presses.eventFilter(bar, Event(4)), "on: taken, to dock its window")
            self.assertEqual(len(qt.later), 1)
            sys._freelab_tabs_state["on"] = False
            self.assertFalse(presses.eventFilter(bar, Event(4)), "off: left to FontLab")
            self.assertEqual(len(qt.later), 1)

    def test_a_double_click_is_fontlabs_without_reorder(self):
        frame = Widget(window=True, kind="YFrameWindow")
        bar = Widget(Widget(frame))
        with FakeQt() as qt:
            sys._freelab_tabs_state["options"] = {"reorder": False, "no_undock": True}
            presses = ft._filter_class()()
            self.assertFalse(presses.eventFilter(bar, Event(4)), "no_undock alone: FontLab's own double-click")
            self.assertEqual(qt.later, [])

    def test_the_repaint_reaches_the_frame_and_what_it_holds(self):
        frame = Widget(kind="YFrameWindow")
        inner, outside = Widget(Widget(frame)), Widget()
        main = Widget(frame)
        with FakeQt([frame, inner, outside]):
            saved = ft.main_tabs
            ft.main_tabs = lambda: (None, main)
            try:
                ft.refresh_main()
            finally:
                ft.main_tabs = saved
        self.assertEqual((frame.updates, inner.updates, outside.updates), (1, 1, 0))


class FindTests(unittest.TestCase):
    """The document areas are found from FontLab's windows, not by wrapping every widget each second:
    the crashes of November 14 all came at the end of that walk (PythonQt freeing a wrapper twice)."""

    def setUp(self):
        self.main = Widget(window=True, kind="MainWindow")
        self.frame = Widget(self.main, kind="YFrameWindow")
        self.tabs = Widget(self.frame, kind="YTabWidget")
        self.loose = Widget(window=True, kind="YFrameWindow")  # a window of its own
        self.loose_tabs = Widget(self.loose, kind="YTabWidget")
        self.other = Widget(self.main, kind="QTabWidget")  # a panel's tabs: no document area
        self.tops = [self.main, self.loose, Widget(window=True, kind="QMenu")]
        self.walks, self.typed = 0, {self.main: [self.tabs, self.other], self.loose: [self.loose_tabs]}
        case = self

        class App(object):
            def allWidgets(self):
                case.walks += 1
                return [case.main, case.frame, case.tabs, case.other, case.loose, case.loose_tabs]

        app = App()

        class Application(object):
            @staticmethod
            def instance():
                return app

            @staticmethod
            def topLevelWidgets():
                return list(case.tops)

        for top in (self.main, self.loose):
            top.findChildren = (lambda top: lambda kind: list(case.typed.get(top, [])))(top)
        self.gui = type("QtGui", (), {"QApplication": Application, "QTabWidget": "QTabWidget"})
        saved = (ft._qt, getattr(sys, "_freelab_tabs_state", None))
        ft._qt = lambda: (None, self.gui)
        sys._freelab_tabs_state = {"on": True, "held": []}

        def restore():
            ft._qt = saved[0]
            if saved[1] is None:
                del sys._freelab_tabs_state
            else:
                sys._freelab_tabs_state = saved[1]
        self.addCleanup(restore)

    def test_found_from_the_windows_that_hold_them(self):
        self.assertEqual(ft.document_tab_widgets(), [(self.tabs, self.frame), (self.loose_tabs, self.loose)])
        self.assertEqual(self.walks, 0, "no widget walked")

    def test_without_the_typed_search_the_walk_is_made_only_when_the_windows_change(self):
        self.typed = {}  # (as PythonQt gives for findChildren(QWidget))
        self.assertEqual(len(ft.document_tab_widgets()), 2)
        self.assertEqual(ft.document_tab_widgets(), [(self.tabs, self.frame), (self.loose_tabs, self.loose)])
        self.assertEqual(self.walks, 1, "the same windows: not walked again")
        self.tops.remove(self.loose)  # (the window docked back)
        ft.document_tab_widgets()
        self.assertEqual(self.walks, 2)

        def deleted():
            raise ValueError("destroyed")
        self.tabs.metaObject = deleted  # (deleted, and its address may be another's now, the windows' the same)
        ft.document_tab_widgets()
        self.assertEqual(self.walks, 3, "walked again")

    def test_each_pass_hooks_what_is_not_hooked_yet(self):
        # (a key of addresses was no proof: a window docked and another torn off in one pass may take the
        # same address, and its new bar went unhooked)
        hooked, buttons = [], []

        class Bar(object):
            def __init__(self):
                self.props = {}

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

            def installEventFilter(self, watcher):
                hooked.append(self)

        bars = {self.tabs: Bar(), self.loose_tabs: Bar()}
        saved = (ft._bar_of, ft._add_dock_button, ft._filter_class)
        ft._bar_of = lambda tab_widget: bars[tab_widget]
        ft._add_dock_button = lambda tab_widget: buttons.append(tab_widget)
        ft._filter_class = lambda: (lambda parent: ("filter of", parent))
        self.loose_tabs.findChild = lambda kind, name: None if not buttons else "button"
        self.loose_tabs.cornerWidget = lambda corner: "button"
        core = type("QtCore", (), {"Qt": type("Qt", (), {"TopRightCorner": 1})})
        ft._qt = lambda: (core, self.gui)
        try:
            self.gui.QToolButton = "QToolButton"
            self.assertTrue(ft.watch())
            self.assertEqual(hooked, [bars[self.tabs], bars[self.loose_tabs]])
            self.assertEqual(buttons, [self.loose_tabs], "the window of its own gets its Dock button")
            self.assertFalse(ft.watch(), "nothing new: nothing done")
            bars[self.loose_tabs] = Bar()  # (a new bar, as a new window at a reused address has)
            self.assertTrue(ft.watch(), "looked at all the same, and hooked")
            self.assertEqual(len(hooked), 3)
        finally:
            ft._bar_of, ft._add_dock_button, ft._filter_class = saved

    def test_no_dock_button_without_reorder(self):
        hooked, buttons, hidden = [], [], []

        class Bar(object):
            def __init__(self):
                self.props = {}

            def property(self, name):
                return self.props.get(name)

            def setProperty(self, name, value):
                self.props[name] = value

            def installEventFilter(self, watcher):
                hooked.append(self)

        bars = {self.tabs: Bar(), self.loose_tabs: Bar()}
        saved = (ft._bar_of, ft._add_dock_button, ft._filter_class, ft.hide_undock)
        ft._bar_of = lambda tab_widget: bars[tab_widget]
        ft._add_dock_button = lambda tab_widget: buttons.append(tab_widget)
        ft._filter_class = lambda: (lambda parent: ("filter of", parent))
        ft.hide_undock = lambda: hidden.append(1) or 0
        self.loose_tabs.findChild = lambda kind, name: None
        core = type("QtCore", (), {"Qt": type("Qt", (), {"TopRightCorner": 1})})
        ft._qt = lambda: (core, self.gui)
        sys._freelab_tabs_state["options"] = {"reorder": False, "no_undock": True}
        try:
            self.gui.QToolButton = "QToolButton"
            ft.watch()
            self.assertEqual(buttons, [], "no_undock alone: no Dock button")
            self.assertEqual(len(hooked), 2, "the bars hooked all the same (their presses are followed)")
            self.assertEqual(hidden, [1], "the Undock commands looked at")
        finally:
            ft._bar_of, ft._add_dock_button, ft._filter_class, ft.hide_undock = saved


class MergeTests(unittest.TestCase):
    """Docking goes through FontLab's Merge Window, which FontLab enables once it has seen the tab's
    window become the active one: not always at once."""

    class Action(object):
        objectName = ft.MERGE_WINDOW

        def __init__(self, ready_after):
            self.ready_after, self.asked, self.triggered = ready_after, 0, 0

        def isEnabled(self):
            self.asked += 1
            return self.ready_after is not None and self.asked > self.ready_after

        def trigger(self):
            self.triggered += 1

    class Frame(object):
        windowTitle = u"Cardo"

        def __init__(self):
            self.activated = 0

        def metaObject(self):
            return self

        def className(self):
            return "YFrameWindow"

        def raise_(self):
            pass

        def activateWindow(self):
            self.activated += 1

    def merge(self, ready_after):
        case, action, frame = self, self.Action(ready_after), self.Frame()

        class Main(object):
            def findChildren(self, kind):
                return [action]

        class Application(object):
            @staticmethod
            def processEvents():
                pass

            @staticmethod
            def activeWindow():
                return frame

        class Gui(object):
            QApplication, QAction = Application, object

        saved = (ft._qt, ft.main_window, ft.ACTIVATE_WAIT, getattr(sys, "_freelab_tabs_state", None))
        ft._qt, ft.main_window, ft.ACTIVATE_WAIT = (lambda: (None, Gui)), (lambda: Main()), 0.0
        sys._freelab_tabs_state = {"on": True}
        try:
            return ft.merge_window(frame), action, frame, list(ft._state().get("failures", []))
        finally:
            ft._qt, ft.main_window, ft.ACTIVATE_WAIT, sys._freelab_tabs_state = saved

    def test_the_command_is_waited_for(self):
        done, action, frame, failures = self.merge(ready_after=3)
        self.assertTrue(done)
        self.assertEqual((action.triggered, failures), (1, []))

    def test_a_command_that_stays_unavailable_is_reported(self):
        done, action, frame, failures = self.merge(ready_after=None)
        self.assertFalse(done)
        self.assertEqual(action.triggered, 0)
        self.assertEqual(frame.activated, 2, "asked once more on the way")
        self.assertEqual(len(failures), 1)
        self.assertIn(u"Merge Window command stayed unavailable", failures[0][1])
        self.assertIn(u"Cardo", failures[0][1])


class SettingTests(unittest.TestCase):
    def test_on_unless_switched_off(self):
        self.assertTrue(ft.enabled_setting({}))
        self.assertFalse(ft.enabled_setting({"enabled": False}))

    def test_the_options_default_to_reorder_alone(self):
        self.assertEqual(ft.options({}), {"reorder": True, "no_undock": False}, "today's behavior")
        self.assertEqual(ft.options({"enabled": True}), {"reorder": True, "no_undock": False}, "an earlier tabs.json")
        self.assertEqual(ft.options({"reorder": False, "no_undock": True}), {"reorder": False, "no_undock": True})

    def test_junk_counts_as_the_default(self):
        for junk in ("yes", 1, 0, None, [], {"a": 1}):
            self.assertEqual(ft.options({"reorder": junk, "no_undock": junk}), {"reorder": True, "no_undock": False},
                             repr(junk))
        self.assertEqual(ft.options(None), {"reorder": True, "no_undock": False})
        self.assertEqual(ft.options(["not", "a", "dict"]), {"reorder": True, "no_undock": False})

    def test_each_summary_says_what_is_on(self):
        texts = [ft.summary({"reorder": True, "no_undock": False}), ft.summary({"reorder": True, "no_undock": True}),
                 ft.summary({"reorder": False, "no_undock": True}), ft.summary({"reorder": True}, on=False),
                 ft.summary({"reorder": False, "no_undock": False})]
        self.assertEqual(len(set(texts[:4])), 4)
        self.assertEqual(texts[3], texts[4], "both options off is off")
        self.assertIn(u"is off", texts[3])
        for text in texts:
            self.assertTrue(text.endswith(u"."), text)
            self.assertNotIn(u"(s)", text)
        self.assertIn(u"cannot be dragged out", texts[2])
        # (the review of 2026-11-24: the off sentence had no verb)
        self.assertEqual(texts[3], u"FreeLab tab docking is off: FontLab handles tab dragging again.")

    def test_the_dock_buttons_tooltip_is_a_sentence(self):
        """As the settings' tooltips are (the review of 2026-11-24: no period, and the only imperative)."""
        self.assertEqual(ft.DOCK_TIP, u"Puts this window's tabs back into the main window. A double-click on one of "
                                      u"its tabs does the same.")


class Capture(object):
    """sys.stdout for a test: what print() wrote (unicode or str, as either Python gives it)."""

    def __init__(self):
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    def flush(self):
        pass

    def text(self):
        return u"".join(part if isinstance(part, type(u"")) else part.decode("ascii") for part in self.parts)


class StateCase(unittest.TestCase):
    """A fresh tab docking state (on), tabs.json in a temporary folder, and fake Qt modules whose single
    shots are collected in self.later; ft's functions patched for one test with self.patch."""

    def setUp(self):
        saved = (getattr(sys, "_freelab_tabs_state", None), os.environ.get("FREELAB_STATE_DIR"),
                 sys.modules.get("freelab_tabs"), sys.stdout)
        self.folder = tempfile.mkdtemp(prefix="freelab-tabs-")
        os.environ["FREELAB_STATE_DIR"] = self.folder
        sys._freelab_tabs_state = {"on": True}
        sys.modules["freelab_tabs"] = ft  # (what the dispatcher calls)

        def restore():
            state, folder, module, stdout = saved
            sys.stdout = stdout
            if state is None:
                if hasattr(sys, "_freelab_tabs_state"):
                    del sys._freelab_tabs_state
            else:
                sys._freelab_tabs_state = state
            if folder is None:
                os.environ.pop("FREELAB_STATE_DIR", None)
            else:
                os.environ["FREELAB_STATE_DIR"] = folder
            if module is not None:
                sys.modules["freelab_tabs"] = module
            shutil.rmtree(self.folder, ignore_errors=True)
        self.addCleanup(restore)
        self.later = []
        later = self.later
        core = type("QtCore", (), {
            "QTimer": type("QTimer", (object,), {"singleShot": staticmethod(lambda ms, function: later.append(function))}),
            "Qt": type("Qt", (), {"TopRightCorner": 1})})
        gui = type("QtGui", (), {"QAction": "QAction", "QToolButton": "QToolButton"})
        self.patch("_qt", lambda: (core, gui))

    def patch(self, name, value):
        original = getattr(ft, name)
        setattr(ft, name, value)
        self.addCleanup(setattr, ft, name, original)

    def run_later(self):
        while self.later:
            self.later.pop(0)()

    def saved(self):
        with open(os.path.join(self.folder, "tabs.json")) as handle:
            return json.load(handle)

    def save(self, data):
        with open(os.path.join(self.folder, "tabs.json"), "w") as handle:
            json.dump(data, handle)

    def set_options(self, reorder, no_undock):
        sys._freelab_tabs_state["options"] = {"reorder": reorder, "no_undock": no_undock}


class ConfigureTests(StateCase):
    """configure() saves the settings and applies them at once: started, stopped, or the options changed
    while running, without a restart."""

    def setUp(self):
        StateCase.setUp(self)
        self.calls = []
        state = sys._freelab_tabs_state

        def start(chosen=None):
            self.calls.append(("start", chosen))
            state["on"] = True

        def stop():
            self.calls.append(("stop",))
            state["on"] = False
        self.patch("start", start)
        self.patch("stop", stop)
        self.patch("apply_options", lambda chosen: self.calls.append(("apply", chosen)))

    def test_switching_on_saves_and_starts(self):
        sys._freelab_tabs_state["on"] = False
        result = ft.configure(enabled=True, reorder=True, no_undock=True)
        self.assertEqual(result, {"enabled": True, "reorder": True, "no_undock": True})
        self.assertEqual(self.saved(), result)
        self.assertEqual(self.calls, [("start", {"reorder": True, "no_undock": True})])

    def test_while_on_the_options_apply_at_once(self):
        self.save({"enabled": True, "other": 1})
        result = ft.configure(no_undock=True)
        self.assertEqual(result, {"enabled": True, "reorder": True, "no_undock": True, "other": 1}, "the rest kept")
        self.assertEqual(self.calls, [("apply", {"reorder": True, "no_undock": True})], "no restart")

    def test_both_options_off_is_off(self):
        result = ft.configure(enabled=True, reorder=False, no_undock=False)
        self.assertEqual(result, {"enabled": False, "reorder": False, "no_undock": False})
        self.assertEqual(self.saved(), result)
        self.assertEqual(self.calls, [("stop",)])

    def test_off_keeps_the_options(self):
        self.save({"enabled": True, "reorder": False, "no_undock": True})
        result = ft.configure(enabled=False)
        self.assertEqual(result, {"enabled": False, "reorder": False, "no_undock": True})
        self.assertEqual(self.calls, [("stop",)])
        self.calls[:] = []
        ft.configure(enabled=False)
        self.assertEqual(self.calls, [], "off already: nothing to stop")

    def test_startup_reads_the_options(self):
        sys._freelab_tabs_state["on"] = False
        self.save({"reorder": False, "no_undock": True})
        ft.startup()
        self.assertEqual(self.calls, [("start", {"reorder": False, "no_undock": True})])
        sys._freelab_tabs_state["on"] = False
        self.calls[:] = []
        self.save({"enabled": True, "reorder": False, "no_undock": False})
        ft.startup()
        self.assertEqual(self.calls, [], "both options off: not started")

    def test_the_switch_turns_reorder_on_when_both_are_off(self):
        sys._freelab_tabs_state["on"] = False
        self.save({"enabled": False, "reorder": False, "no_undock": False})
        sys.stdout = out = Capture()
        self.assertTrue(ft.toggle())
        self.assertEqual(self.calls, [("start", {"reorder": True, "no_undock": False})], "on always does something")
        self.assertEqual(self.saved(), {"enabled": True, "reorder": True, "no_undock": False})
        self.assertIn(u"is on", out.text())
        self.assertFalse(ft.toggle())
        self.assertEqual(self.calls[-1], ("stop",))
        self.assertEqual(self.saved(), {"enabled": False, "reorder": True, "no_undock": False}, "the options kept")
        self.assertIn(u"is off", out.text())

    def test_the_switch_keeps_the_options_chosen(self):
        sys._freelab_tabs_state["on"] = False
        self.save({"enabled": False, "reorder": False, "no_undock": True})
        sys.stdout = out = Capture()
        ft.toggle()
        self.assertEqual(self.calls, [("start", {"reorder": False, "no_undock": True})])
        self.assertIn(u"cannot be dragged out", out.text())


class ApplyTests(StateCase):
    def setUp(self):
        StateCase.setUp(self)
        self.calls = []
        for name in ("hide_marker", "_remove_dock_buttons", "show_undock"):
            self.patch(name, (lambda name: lambda: self.calls.append(name))(name))
        self.patch("watch", lambda force=False: self.calls.append("watch"))

    def test_reorder_off_takes_the_marker_and_the_dock_buttons_away(self):
        ft.apply_options({"reorder": False, "no_undock": True})
        self.assertEqual(self.calls, ["hide_marker", "_remove_dock_buttons", "watch"])
        self.assertEqual(ft._options(), {"reorder": False, "no_undock": True})

    def test_no_undock_off_shows_the_undock_commands(self):
        ft.apply_options({"reorder": True, "no_undock": False})
        self.assertEqual(self.calls, ["show_undock", "watch"])

    def test_junk_options_are_the_defaults(self):
        ft.apply_options({"reorder": "yes"})
        self.assertEqual(ft._options(), {"reorder": True, "no_undock": False})


class Frame(object):
    def __init__(self, name="", window=False):
        self.objectName, self.window = name, window

    def isWindow(self):
        return self.window


class Tabs(object):
    """A document area's tab widget: its pages, in its frame."""

    def __init__(self, frame, pages):
        self.frame, self.pages = frame, pages

    def parentWidget(self):
        return self.frame

    def widget(self, index):
        return self.pages[index]

    currentIndex = 0

    def indexOf(self, page):
        return self.pages.index(page) if page in self.pages else -1

    def setCurrentIndex(self, index):
        self.currentIndex = index


class MainTabs(Bar):
    """The main window's tab bar and tab widget in one (as near_bar and drop_slot read them)."""

    def __init__(self, pages):
        Bar.__init__(self, len(pages))
        self.pages = pages

    def widget(self, index):
        return self.pages[index]

    currentIndex = 0

    def indexOf(self, page):
        return self.pages.index(page) if page in self.pages else -1

    def setCurrentIndex(self, index):
        self.currentIndex = index


AWAY, NEAR = Point(500, 400), Point(110, 110)  # far below the bar; on it, at the second tab


class DragTests(StateCase):
    """A drag followed from the press to the release, and what is docked (dock() recorded) once FontLab has
    made its window (holder_of: the pages a window of its own holds)."""

    def setUp(self):
        StateCase.setUp(self)
        self.pages = [Page("YSketchBoard"), Page(), Page(), Page()]
        self.main = MainTabs(self.pages)
        self.main_area = Tabs(Frame(ft.MAIN_FRAME_NAME), self.pages)
        self.windows, self.docked, self.markers = {}, [], []
        self.down, self.at = True, Point(250, 110)
        self.patch("cursor_pos", lambda: self.at)
        self.patch("button_down", lambda: self.down)
        self.patch("drag_distance", lambda: 10)
        self.patch("main_tabs", lambda: (self.main, self.main))
        self.patch("show_marker", lambda page, point, margin=None: self.markers.append(point))
        self.patch("hide_marker", lambda: None)
        self.patch("holder_of", lambda page: self.windows.get(page))
        self.patch("dock", lambda page, target=None: self.docked.append((page, target)) or True)
        self.patch("refresh_main", lambda: None)

    def drag(self, tabs, index, to, moved=True, made_window=True):
        """Press tabs' tab at index, move (unless not moved), release at to; FontLab makes the tab a window
        of its own on the drop (unless not made_window); then what was put off for after the drop runs."""
        page = tabs.widget(index)
        self.down, self.at = True, Point(250, 110)
        ft.on_pressed(tabs, index)
        if moved:
            self.at = to
            ft.poll()
        self.down, self.at = False, to
        ft.poll()
        if made_window:
            self.windows[page] = Frame(window=True)
        self.run_later()
        return page

    def test_no_undock_keeps_the_press_from_fontlabs_tab_bar(self):
        """The owner, 2026-11-23: put back after the drop, a tab could still be grabbed. The press on a main
        window tab is kept from the bar (the filter returns what on_pressed says), and the release that ends
        it kept too. Nothing is chosen at the press (the view changed under a tab being moved)."""
        chosen = []
        self.main_area.indexOf, self.main_area.currentIndex = self.pages.index, 0
        self.main_area.setCurrentIndex = lambda index: chosen.append(index)
        self.set_options(False, True)
        self.assertTrue(ft.on_pressed(self.main_area, 2), "kept: FontLab has no tab to drag away")
        self.assertEqual(chosen, [], "not chosen while the button is held")
        self.assertTrue(ft.on_released(), "a release with the button still held is kept, and is no click")
        self.run_later()
        self.assertEqual(chosen, [], "the owner, 2026-11-23: a tab held some two seconds was shown, unmoved")
        self.assertEqual([what for when, what in sys._freelab_tabs_state["notes"]],
                         ["a release came with the button still held"])
        self.down = False
        self.assertTrue(ft.on_released(), "its release kept too")
        self.run_later()
        self.assertEqual(chosen, [2], "a click: chosen at the release")
        self.assertFalse(ft.on_released(), "once")
        self.assertFalse(ft.on_pressed(self.main_area, -1), "a press beside the tabs is the bar's")
        loose = Tabs(Frame(window=True), [Page()])
        self.assertFalse(ft.on_pressed(loose, 0), "a tab of a window of its own is FontLab's to drag")
        self.assertFalse(ft.on_released())
        self.set_options(True, False)
        self.assertFalse(ft.on_pressed(self.main_area, 2), "without no_undock the press is FontLab's, as before")
        self.assertFalse(ft.on_released())

    def test_with_both_freelab_moves_the_tab_itself_at_the_release(self):
        self.set_options(True, True)
        page = self.drag(self.main_area, 2, NEAR, made_window=False)
        self.assertEqual(self.docked, [(page, 1)], "moved along the bar: no window was ever made")
        self.assertEqual(len(self.markers), 1, "the marker shown while dragging")
        self.docked[:] = []
        self.drag(self.main_area, 2, AWAY, made_window=False)
        self.assertEqual(self.docked, [], "released away: it stays where it is")

    def cross_bar(self):
        """A tab bar of 100-pixel tabs with close crosses: a tab's cross is at its left end, 24 pixels."""
        class BarWithCrosses(object):
            tabsClosable, font = True, None

            def tabRect(self, index):
                return type("R", (), {"left": lambda self: 100 * index, "width": lambda self: 100})()

            def mapFromGlobal(self, point):
                return point
        return BarWithCrosses()

    def test_a_click_on_a_tabs_close_cross_closes_it(self):
        """The owner, 2026-11-23 and 24: the close cross took two clicks, and was not shown on main window
        tabs (FontLab shows none on tabs whose presses it never gets). Its place is the tab's left end, read
        from the owner's own closing clicks. A press there is kept like any other; released there, the tab
        is closed by FontLab's own slot; released elsewhere, it is a click on the tab."""
        bar = self.cross_bar()
        closed, chosen = [], []
        area = self.main_area
        area.onTabCloseRequested = lambda index: closed.append(index)
        area.setCurrentIndex = lambda index: chosen.append(index)
        self.set_options(True, True)
        self.assertEqual(ft.cross_zone(bar, 2), (200, 224))
        self.at = Point(210, 5)
        self.assertTrue(ft.on_pressed(area, 2, bar, Point(210, 5)), "on the cross: kept, like any press")
        self.assertIn("press at 210, cross zone (200, 224), kept", sys._freelab_tabs_state["presses"][-1][1])
        self.down = False
        self.assertTrue(ft.on_released())
        self.run_later()
        self.assertEqual((closed, chosen), ([2], []), "one click closes")
        self.down, self.at = True, Point(220, 5)
        self.assertTrue(ft.on_pressed(area, 2, bar, Point(220, 5)))
        self.down, self.at = False, Point(226, 5)  # (released off the cross, the mouse hardly moved)
        self.assertTrue(ft.on_released())
        self.run_later()
        self.assertEqual((closed, chosen), ([2], [2]), "released off the cross: the tab is chosen, not closed")
        self.down, self.at = True, Point(230, 5)
        self.assertTrue(ft.on_pressed(area, 2, bar, Point(230, 5)), "on the title")
        self.down = False
        self.assertTrue(ft.on_released())
        self.run_later()
        self.assertEqual(closed, [2], "a click on the title closes nothing")
        closed[:] = []
        ft.close_tab(area, self.pages[0])
        self.assertEqual(closed, [], "the Sketchboard does not close")
        bar.tabsClosable = False
        self.assertIsNone(ft.cross_zone(bar, 2), "no cross on these tabs")
        self.assertIsNone(ft.cross_zone(None, 2))
        self.assertFalse(ft.on_close_cross(object(), 2, Point(230, 5)), "a bar that cannot say: nothing raised")
        self.set_options(True, False)
        bar.tabsClosable = True
        self.assertFalse(ft.on_pressed(area, 2, bar, Point(210, 5)), "undockable: the cross is FontLab's own")

    def test_the_tab_under_the_mouse_shows_a_close_cross(self):
        """The owner, 2026-11-24: main window tabs showed no cross. FreeLab shows its own while the mouse is
        over the main tab bar (no_undock), and takes it away as the mouse leaves."""
        class Label(object):
            def __init__(self):
                self.visible, self.geometry = False, None

            def isVisible(self):
                return self.visible

            def show(self):
                self.visible = True

            def hide(self):
                self.visible = False

            def setGeometry(self, *box):
                self.geometry = box

            def raise_(self):
                pass

        class Timer(object):
            active = False

            def start(self):
                self.active = True

            def stop(self):
                self.active = False

        bar = self.cross_bar()
        bar.width, bar.height, bar.isVisible = 400, 22, lambda: True
        bar.tabAt = lambda point: point.x() // 100 if 0 <= point.x() < 400 else -1
        bar.parentWidget = lambda: self.main_area
        label, timer = Label(), Timer()
        state = sys._freelab_tabs_state
        state["hover_timer"] = timer
        self.patch("_cross_label", lambda bar: label)
        self.patch("_alive", lambda widget: True)
        self.patch("_in_main_window", lambda tabs: True)
        self.patch("_class", lambda widget: getattr(widget, "kind", ""))
        self.set_options(True, False)
        ft.on_bar_entered(bar)
        self.assertFalse(timer.active, "undockable: FontLab's own cross")
        self.set_options(True, True)
        ft.on_bar_entered(bar)
        self.assertTrue(timer.active)
        state["cross_label"] = label
        self.at = Point(250, 5)
        ft.hover_cross()
        self.assertEqual((label.visible, label.geometry), (True, (200 + ft.CROSS_INSET, 0, ft.CROSS_SIZE, 22)))
        self.at = Point(250, 60)  # (the mouse left the bar)
        ft.hover_cross()
        self.assertEqual((label.visible, timer.active), (False, False))

    def test_a_click_chooses_its_tab_at_the_release(self):
        """The owner, 2026-11-23: the view changed at the press, under a tab being moved. A click chooses its tab
        at its release; a drag moves it."""
        chosen = []
        self.main_area.indexOf, self.main_area.currentIndex = self.pages.index, 0
        self.main_area.setCurrentIndex = lambda index: chosen.append(index)
        self.set_options(True, True)
        self.assertTrue(ft.on_pressed(self.main_area, 2))
        self.down = False
        self.assertTrue(ft.on_released())
        self.assertEqual(chosen, [], "not from inside the filter")
        ft.poll()
        self.run_later()
        self.assertEqual(chosen, [2], "once, though the timer saw the button up too")
        self.down = True
        self.assertTrue(ft.on_pressed(self.main_area, 3))
        self.down, self.at = False, NEAR  # (moved before the release: a drag)
        self.assertTrue(ft.on_released())
        ft.poll()
        self.run_later()
        self.assertEqual(chosen, [2], "a drag chooses nothing here")
        self.assertEqual(self.docked, [(self.pages[3], 1)], "moved along the bar, once")

    def test_a_click_whose_release_the_bar_never_got_is_ended_by_the_timer(self):
        chosen = []
        self.main_area.indexOf, self.main_area.currentIndex = self.pages.index, 0
        self.main_area.setCurrentIndex = lambda index: chosen.append(index)
        self.set_options(True, True)
        self.assertTrue(ft.on_pressed(self.main_area, 2))
        self.down = False
        ft.poll()
        self.run_later()
        self.assertEqual(chosen, [2], "chosen all the same")
        self.assertTrue(ft.on_released(), "the release that comes late is still kept")
        self.run_later()
        self.assertEqual(chosen, [2], "once")

    def test_fontlabs_drop_highlight_left_showing_is_hidden(self):
        """The owner, 2026-11-23: the blue highlight stayed over the document area after a merge."""
        class Child(object):
            def __init__(self, kind, visible):
                self.kind, self.visible = kind, visible

            def isVisible(self):
                return self.visible

            def hide(self):
                self.visible = False

        children = [Child("YDropHighlight", True), Child("YTabWidget", True), Child("YDropHighlight", False)]
        frame = type("F", (), {"children": lambda self: children})()
        self.patch("document_tab_widgets", lambda: [(None, frame)])
        self.patch("_class", lambda widget: widget.kind)
        self.assertEqual(ft.clear_highlight(), 0, "not while a button is held: FontLab is showing a drop")
        self.down = False
        self.assertEqual(ft.clear_highlight(), 1)
        self.assertEqual([child.visible for child in children], [False, True, False], "the highlight only")

    def drop_frame(self, active=True, interval=500, lit=True):
        """A document area's frame with FontLab's drop timer and blue highlight among its children."""
        class Timer(object):
            kind = "QTimer"

            def __init__(self):
                self.active, self.interval, self.calls = active, interval, []

            def stop(self):
                self.active = False
                self.calls.append("stop")

            def start(self, interval):
                self.interval = interval
                self.calls.append(interval)

        class Light(object):
            kind, visible = "YDropHighlight", lit

            def isVisible(self):
                return self.visible

            def hide(self):
                self.visible = False

        timer, light = Timer(), Light()
        frame = type("F", (), {"kind": "YFrameWindow", "children": lambda self: [timer, light]})()
        self.patch("_class", lambda widget: getattr(widget, "kind", ""))
        return frame, timer, light

    def test_a_tab_dragged_out_gets_no_drop_highlight(self):
        """The owner, 2026-11-24: the blue highlight came up over the area the tab had just left, and made
        undocking hard. FontLab's drop timer is stopped, and the highlight hidden should it show."""
        frame, timer, light = self.drop_frame()
        self.set_options(True, False)
        drag = {"frame": frame, "from_main": True, "own": False, "tabs": None}
        ft.follow_drop(drag)
        self.assertEqual((timer.calls, light.visible), (["stop"], False))
        self.assertIn("drop timer running (500 ms), highlight shown", drag["trace"][-1][1])
        ft.follow_drop(drag)
        self.assertEqual(timer.calls, ["stop"], "idle now: left alone")
        ft.follow_drop({"from_main": True})  # (no main window: nothing raised)

    def test_a_window_dragged_gets_its_highlight_at_once(self):
        """The owner, 2026-11-23 and 24: the highlight lagged half a second. FontLab's timer is started again
        with almost no wait; without reorder it is FontLab's own."""
        frame, timer, light = self.drop_frame(lit=False)
        self.set_options(True, False)
        drag = {"frame": frame, "from_main": False, "window": True}
        ft.follow_drop(drag)
        ft.follow_drop(drag)
        self.assertEqual(timer.calls, [ft.DROP_TIMER_FAST_MS], "once: it is short already")
        frame, timer, light = self.drop_frame()
        self.set_options(False, True)
        ft.follow_drop({"frame": frame, "from_main": True, "own": False})
        self.assertEqual((timer.calls, light.visible), ([], True), "reorder off: FontLab's own drop")

    def test_a_held_tab_is_not_shown_before_the_release(self):
        """The owner, 2026-11-23 and 24: a tab held some two seconds was shown, unmoved, without a release."""
        chosen = []
        area = self.main_area
        area.count, area.currentIndex = 4, 0
        area.setCurrentIndex = lambda index: chosen.append(index) or setattr(area, "currentIndex", index)
        self.set_options(True, False)
        self.patch("follow_drop", lambda drag: None)
        self.assertFalse(ft.on_pressed(area, 2), "undockable: the press is FontLab's")
        ft.poll()
        self.assertEqual(chosen, [])
        area.currentIndex = 2  # (FontLab shows the held tab)
        ft.poll()
        self.assertEqual(chosen, [0], "put back")
        self.down = False
        ft.poll()
        self.run_later()
        self.assertEqual(chosen, [0, 2], "and chosen at the release, as a click")
        self.down = True
        ft.on_pressed(area, 3)
        area.count = 3  # (FontLab took the tab for its drag)
        area.currentIndex = 1
        ft.poll()
        self.assertEqual(chosen, [0, 2], "the bar lost a tab: FontLab's drag, left alone")

    def test_a_dock_that_failed_after_a_drop_is_tried_again(self):
        """2026-11-24: Merge Window stayed unavailable for the window just dropped, twice."""
        tries = []
        page = self.pages[2]
        self.windows[page] = Frame(window=True)
        self.patch("_alive", lambda widget: True)
        self.patch("dock", lambda page, target=None: tries.append(target) or len(tries) > 2)
        self.set_options(True, False)
        ft.dock_after_drop(page, 1)
        self.run_later()
        self.run_later()
        self.assertEqual(tries, [1, 1, 1], "until it docks")
        self.run_later()
        self.assertEqual(len(tries), 3)

    def test_a_tab_dragged_away_stays_and_is_chosen(self):
        chosen = []
        self.main.indexOf, self.main.currentIndex = self.pages.index, 0
        self.main.setCurrentIndex = lambda index: chosen.append(index)
        self.set_options(False, True)
        self.drag(self.main_area, 2, NEAR, made_window=False)
        self.assertEqual((self.docked, chosen), ([], [2]), "no_undock alone: not moved, chosen at the release")

    def test_a_window_dragged_by_its_title_bar_onto_the_tab_bar_docks(self):
        """The owner, 2026-11-23: FontLab's own blue highlight was hard to get. A window of its own moved with the
        button held is followed as a tab's drag is, and docks when released on the main tab bar."""
        page = Page()
        frame = Frame(window=True)
        loose = Tabs(frame, [page])
        loose.currentWidget = lambda: page
        self.patch("document_tab_widgets", lambda: [(self.main_area, self.main_area.frame), (loose, frame)])
        self.set_options(True, False)
        self.down, self.at = True, AWAY
        ft.on_window_moved(frame)
        drag = sys._freelab_tabs_state["drag"]
        self.assertTrue(drag["window"] and drag["page"] is page)
        ft.on_window_moved(frame)
        self.assertIs(sys._freelab_tabs_state["drag"], drag, "each step of the move: followed once")
        self.at = NEAR
        ft.poll()
        self.assertEqual(len(self.markers), 1, "the marker while it is over the bar")
        self.down = False
        ft.poll()
        self.windows[page] = frame
        self.run_later()
        self.assertEqual(self.docked, [(page, 1)], "docked at the marker's place")
        self.docked[:] = []
        self.down = False
        ft.on_window_moved(frame)
        self.assertIsNone(sys._freelab_tabs_state["drag"], "moved with no button held (a program, a snap): not a drag")
        self.down = True
        self.set_options(False, True)
        ft.on_window_moved(frame)
        self.assertIsNone(sys._freelab_tabs_state["drag"], "without reorder: FontLab's own")
        ft.on_window_moved(self.main_area.frame)
        self.assertIsNone(sys._freelab_tabs_state["drag"], "the main window is no window of its own")

    def test_reorder_alone_is_as_before(self):
        self.set_options(True, False)
        page = self.drag(self.main_area, 2, NEAR)
        self.assertEqual(self.docked, [(page, 1)], "docked at the marker's place")
        self.assertEqual(len(self.markers), 1, "the marker shown while dragging")
        self.docked[:] = []
        self.drag(self.main_area, 2, AWAY)
        self.assertEqual(self.docked, [], "released away: a window of its own")

    def test_no_undock_puts_a_main_window_tab_back_where_it_was(self):
        self.set_options(False, True)
        page = self.drag(self.main_area, 2, AWAY)
        self.assertEqual(self.docked, [(page, 2)])

    def test_no_undock_alone_puts_back_even_on_the_bar(self):
        # (FontLab makes a window of a tab dropped on its own bar: with no_undock alone it goes back, so
        # tabs do not reorder, as in FontLab)
        self.set_options(False, True)
        page = self.drag(self.main_area, 2, NEAR)
        self.assertEqual(self.docked, [(page, 2)], "its own place, not the marker's")
        self.assertEqual(self.markers, [], "no marker")

    def test_a_tab_still_in_the_main_window_is_left_alone(self):
        self.set_options(False, True)
        self.drag(self.main_area, 2, AWAY, made_window=False)
        self.assertEqual(self.docked, [], "a click, or FontLab did nothing")
        self.set_options(True, True)
        self.drag(self.main_area, 2, AWAY, made_window=False)
        self.assertEqual(self.docked, [])

    def test_a_short_drag_that_fontlab_made_a_window_of_goes_back(self):
        self.set_options(False, True)
        page = self.drag(self.main_area, 1, Point(252, 111), moved=False)
        self.assertEqual(self.docked, [(page, 1)], "the proof is the window, not the start distance")

    def test_with_both_near_the_bar_docks_at_the_slot_and_away_goes_back(self):
        self.set_options(True, True)
        page = self.drag(self.main_area, 2, NEAR)
        self.assertEqual(self.docked, [(page, 1)])
        self.docked[:] = []
        page = self.drag(self.main_area, 3, AWAY)
        self.assertEqual(self.docked, [(page, 3)])

    def test_a_tab_pressed_in_a_window_of_its_own_is_not_put_back(self):
        loose = Tabs(Frame(ft.MAIN_FRAME_NAME, window=True), [Page()])  # (a window of its own, whatever its name)
        self.set_options(False, True)
        self.drag(loose, 0, AWAY)
        self.assertEqual(self.docked, [], "undocked already: FontLab's")
        self.set_options(True, True)
        page = self.drag(loose, 0, NEAR)
        self.assertEqual(self.docked, [(page, 1)], "reorder still docks it on the bar")

    def test_put_back_does_nothing_once_no_undock_is_off(self):
        page = self.pages[2]
        self.windows[page] = Frame(window=True)
        self.set_options(True, False)
        self.assertFalse(ft.put_back(page, 2))
        self.assertEqual(self.docked, [])


class MarkerOptionTests(StateCase):
    def test_no_marker_without_reorder(self):
        hidden = []
        self.patch("hide_marker", lambda: hidden.append(1))

        def no_marker():
            raise AssertionError("a marker made")
        self.patch("_marker", no_marker)
        self.patch("main_tabs", lambda: (Bar(3), Bar(3)))
        self.set_options(False, True)
        ft.show_marker(Page(), NEAR)
        self.assertEqual(hidden, [1])


class Action(object):
    """A QAction of FontLab's main window: its name, whether it is shown, and its setVisible calls."""

    def __init__(self, name, visible=True):
        self.objectName, self.visible, self.sets, self.deleted = name, visible, [], False

    def isVisible(self):
        return self.visible

    def setVisible(self, value):
        self.sets.append(value)
        self.visible = value

    def metaObject(self):
        if self.deleted:
            raise ValueError("destroyed")
        return type("Meta", (), {"className": lambda _self: "QAction"})()


class UndockTests(StateCase):
    """FontLab's Undock commands are hidden while no_undock is on, hidden again when FontLab shows them,
    and shown again after, but only the ones FreeLab hid."""

    def setUp(self):
        StateCase.setUp(self)
        self.actions = {name: Action(name) for name in ft.UNDOCK_ACTIONS}
        self.actions["actionUndock_Glyph"].visible = False  # (hidden by FontLab itself: not FreeLab's to show)
        self.merge = Action(ft.MERGE_WINDOW)
        self.searches = 0
        case = self

        class Main(object):
            def findChildren(self, kind):
                case.searches += 1
                return [case.merge] + [a for a in case.actions.values() if not a.deleted]

        self.patch("main_window", lambda: Main())
        self.patch("document_tab_widgets", lambda: [])
        self.patch("hide_marker", lambda: None)

    def shown(self):
        return sorted(name for name, action in self.actions.items() if action.visible)

    def test_hidden_while_on_and_shown_after(self):
        self.set_options(True, True)
        self.assertEqual(ft.hide_undock(), 2)
        self.assertEqual(self.shown(), [])
        self.assertEqual(sorted(action.objectName for action in sys._freelab_tabs_state["undock_hidden"]),
                         ["actionUndock_All", "actionUndock_Font"])
        self.actions["actionUndock_All"].visible = True  # (FontLab shows it again)
        self.assertTrue(ft.watch())
        self.assertEqual(self.shown(), [], "hidden again by the next pass")
        self.assertFalse(ft.watch(), "nothing new")
        ft.apply_options({"reorder": True, "no_undock": False})
        self.assertEqual(self.shown(), ["actionUndock_All", "actionUndock_Font"])
        self.assertEqual(self.actions["actionUndock_Glyph"].sets, [], "FontLab's own hidden one left alone")
        self.assertEqual(self.merge.sets, [], "Merge Window untouched")
        ft.watch()
        self.assertEqual(self.shown(), ["actionUndock_All", "actionUndock_Font"], "not hidden while no_undock is off")

    def test_stopping_shows_them(self):
        self.set_options(False, True)
        ft.watch()
        self.assertEqual(self.shown(), [])
        ft.stop()
        self.assertEqual(self.shown(), ["actionUndock_All", "actionUndock_Font"])
        self.assertEqual(sys._freelab_tabs_state["undock_hidden"], [])

    def test_an_action_fontlab_made_anew_is_not_freelabs_to_show(self):
        """Codex, 2026-11-23: the hidden commands were remembered by name, so one FontLab deleted and made anew,
        hidden by FontLab itself, was shown when no_undock went off."""
        self.set_options(False, True)
        ft.watch()
        old = self.actions["actionUndock_All"]
        old.deleted = True
        new = self.actions["actionUndock_All"] = Action("actionUndock_All", visible=False)
        ft.apply_options({"reorder": True, "no_undock": False})
        self.assertEqual(new.sets, [], "never hidden by FreeLab: left as FontLab has it")
        self.assertEqual(old.sets, [False], "the deleted one is not touched again")
        self.assertTrue(self.actions["actionUndock_Font"].visible, "the one FreeLab hid, still there, is shown")

    def test_searched_once_while_they_live(self):
        ft.undock_actions()
        ft.undock_actions()
        self.assertEqual(self.searches, 1, "kept: not every action of the main window wrapped each second")
        self.actions["actionUndock_Font"].deleted = True
        self.assertEqual(len(ft.undock_actions()), 2)
        self.assertEqual(self.searches, 2, "one deleted: searched again")

    def test_none_found_is_searched_again_only_later(self):
        self.actions.clear()
        self.assertEqual(ft.undock_actions(), [])
        self.assertEqual(ft.undock_actions(), [])
        self.assertEqual(self.searches, 1)
        sys._freelab_tabs_state["undock_search"] -= ft.EMPTY_WALK_SECONDS + 1
        ft.undock_actions()
        self.assertEqual(self.searches, 2)


class LateDecisionTests(StateCase):
    """Codex, 2026-11-23: what was queued or installed before the options changed must not act on the options
    of before."""

    def calls(self):
        seen = []
        self.patch("dock", lambda page, target=None: seen.append(("dock", page, target)) or True)
        self.patch("put_back", lambda page, index: seen.append(("put back", page, index)) or True)
        self.patch("refresh_main", lambda: None)
        return seen

    def test_a_queued_drop_decides_with_the_options_of_now(self):
        seen = self.calls()
        self.set_options(True, True)
        ft.dock_after_drop("page", 1, True, 3)
        self.assertEqual(seen, [("dock", "page", 1)], "reorder on: at the marker's place")
        del seen[:]
        self.set_options(False, True)  # (switched off within the delay)
        ft.dock_after_drop("page", 1, True, 3)
        self.assertEqual(seen, [("put back", "page", 3)], "where it was pressed, not the marker's place")
        del seen[:]
        ft.dock_after_drop("page", 1, False, 0)
        self.assertEqual(seen, [], "a tab from a window of its own is left to FontLab")
        self.set_options(False, False)
        ft.dock_after_drop("page", 1, True, 3)
        self.assertEqual(seen, [], "both off: nothing docked")

    def test_a_window_is_not_docked_while_reorder_is_off(self):
        seen = self.calls()
        tabs = type("Tabs", (), {"currentWidget": lambda self: "page"})()
        self.set_options(False, True)
        ft.dock_frame(tabs)  # (a double-click queued before the switch, or an earlier version's filter)
        self.assertEqual(seen, [])
        self.set_options(True, False)
        ft.dock_frame(tabs)
        self.assertEqual(seen, [("dock", "page", None)])

    def test_an_earlier_versions_filter_is_taken_off_its_bar(self):
        """The filter before the options docked on a double-click itself, and stayed on its bar when FreeLab was
        installed again in the same session."""
        class Bar(object):
            def __init__(self):
                self.removed = []

            def removeEventFilter(self, watcher):
                self.removed.append(watcher)

        class Old(object):
            def __init__(self, bar):
                self.bar = bar

            def eventFilter(self, obj, event):
                return True

            def parent(self):
                return self.bar

        class New(Old):
            pass

        bar, other = Bar(), Bar()
        old, elsewhere, new = Old(bar), Old(other), New(bar)
        state = sys._freelab_tabs_state
        state["held"] = [old, elsewhere, new, "a slot", lambda: None]
        state[ft.FILTER_CLASS_KEY] = New
        ft._drop_old_filters(bar)
        self.assertEqual(bar.removed, [old], "the old one on this bar; this version's stays")
        self.assertEqual(other.removed, [])
        self.assertIn(old, state["held"], "still held: Qt deletes it with its bar")
        self.assertNotEqual(ft.FILTER_REVISION, 2, "a bar hooked by the version before is hooked again")
        self.assertNotEqual(ft.FILTER_CLASS_KEY, "filter_class_v2")


class SettingsScriptTests(unittest.TestCase):
    """windows/freelab_tabs_settings.py: Scripts > FreeLab > Tab Docking Settings."""

    def setUp(self):
        saved = (getattr(sys, "_freelab_tabs_state", None), sys.modules.get("freelab_tabs"),
                 os.environ.get("FREELAB_NO_AUTOSTART"))

        def restore():
            state, module, autostart = saved
            if state is None:
                if hasattr(sys, "_freelab_tabs_state"):
                    del sys._freelab_tabs_state
            else:
                sys._freelab_tabs_state = state
            sys.modules["freelab_tabs"] = module
            if autostart is None:
                os.environ.pop("FREELAB_NO_AUTOSTART", None)
            else:
                os.environ["FREELAB_NO_AUTOSTART"] = autostart
        self.addCleanup(restore)
        os.environ["FREELAB_NO_AUTOSTART"] = "1"
        import freelab_tabs_settings as settings
        self.settings = settings

    def test_the_running_module_is_used(self):
        sys._freelab_tabs_state = {"on": True, "module": ft}
        sys.modules.pop("freelab_tabs", None)
        self.assertIs(self.settings.tabs_module(), ft)

    def test_the_module_beside_it_is_loaded_without_starting(self):
        for autostart in (None, "1"):
            if hasattr(sys, "_freelab_tabs_state"):
                del sys._freelab_tabs_state
            sys.modules.pop("freelab_tabs", None)
            if autostart is None:
                os.environ.pop("FREELAB_NO_AUTOSTART", None)
            else:
                os.environ["FREELAB_NO_AUTOSTART"] = autostart
            module = self.settings.tabs_module()
            self.assertIsNot(module, ft)
            self.assertTrue(hasattr(module, "configure"))
            self.assertIs(sys.modules.get("freelab_tabs"), module)
            self.assertFalse((getattr(sys, "_freelab_tabs_state", None) or {}).get("on"), "not started")
            self.assertEqual(os.environ.get("FREELAB_NO_AUTOSTART"), autostart, "the environment as it was")

    def test_an_earlier_running_version_is_not_used(self):
        sys._freelab_tabs_state = {"on": True, "module": type("Old", (), {})()}  # (no configure)
        sys.modules.pop("freelab_tabs", None)
        self.assertTrue(hasattr(self.settings.tabs_module(), "configure"))

    def test_the_texts(self):
        s = self.settings
        for text in (s.REORDER, s.NO_UNDOCK, s.REORDER_TIP, s.NO_UNDOCK_TIP, s.OFF_NOTE):
            self.assertTrue(text.endswith(u"."), text)
            self.assertFalse(set(text) & set([unichr_(0xb7), unichr_(0x2014)]), "no interpuncts or em dashes")
        self.assertIn(u"window of its own", s.REORDER_TIP)
        self.assertIn(u"<i>Window &gt; Docking</i>", s.NO_UNDOCK_TIP)
        # The review of 2026-11-24: a window of its own dragged by its title bar docks too (on_window_moved); the
        # first box named by its caption, not its place; OK with both unticked leaves docking off
        self.assertIn(u"dragged there by its title bar", s.REORDER_TIP)
        self.assertIn(u"<i>%s</i>" % s.REORDER.rstrip(u"."), s.NO_UNDOCK_TIP)
        self.assertNotIn(u"first box", s.NO_UNDOCK_TIP)
        self.assertIn(u"with both unticked, it stays off", s.OFF_NOTE)
        # (the review of 2026-11-24: a button's or a command's name in italics)
        self.assertIn(u"a <i>Dock</i> button", s.REORDER_TIP)
        self.assertIn(u"FontLab's <i>Undock</i> commands", s.NO_UNDOCK_TIP)
        self.assertIn(u"<i>OK</i> switches it on", s.OFF_NOTE)


class _Control(object):
    """A dialog control: whatever it is asked to do, it does nothing, but its text, tooltip, and check."""
    made = []

    def __init__(self, *args):
        self.text = args[0] if args and isinstance(args[0], (type(u""), str)) else None
        self.checked, self.tip = False, None
        _Control.made.append(self)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args: None

    def setChecked(self, value):
        self.checked = bool(value)

    def isChecked(self):
        return self.checked

    def setToolTip(self, text):
        self.tip = text


class _Box(_Control):
    pass


class _Dialog(_Control):
    made = []
    run = [lambda dialog: 0]  # what exec_ does (a test sets it)

    def __init__(self, parent=None):
        _Control.__init__(self)
        self.parent_, self.deleted, self.props, self.title = parent, 0, {}, None
        _Dialog.made.append(self)

    def setWindowTitle(self, title):
        self.title = title

    def setProperty(self, name, value):
        self.props[name] = value

    def windowFlags(self):
        return 0

    def exec_(self):
        return _Dialog.run[0](self)

    def deleteLater(self):
        self.deleted += 1


class FakeTabs(object):
    """Tab docking as the settings dialog uses it: the saved settings, whether it runs, configure() noted."""
    options = staticmethod(ft.options)
    summary = staticmethod(ft.summary)

    def __init__(self, saved, on=True):
        self.saved, self.on, self.configured = saved, on, []

    def load_settings(self):
        return dict(self.saved)

    def is_on(self):
        return self.on

    def configure(self, **values):
        self.configured.append(values)
        return {"enabled": values["enabled"], "reorder": values["reorder"], "no_undock": values["no_undock"]}


class SettingsDialogTests(unittest.TestCase):
    """The dialog shows the saved options, OK configures tab docking with the boxes' choice, Cancel changes
    nothing; it has FontLab's main window as its parent and Qt deletes it once (as dark mode's settings)."""

    def setUp(self):
        import qtfakes
        qtfakes.install()
        self.qtfakes = qtfakes
        saved = (os.environ.get("FREELAB_NO_AUTOSTART"), sys.stdout)
        os.environ["FREELAB_NO_AUTOSTART"] = "1"
        import freelab_tabs_settings as settings
        self.settings = settings
        original = settings.tabs_module
        gui = sys.modules["PythonQt.QtGui"]
        self.main = qtfakes.FakeWidget("QMainWindow", name="MainWindow")
        gui.QApplication = type("App", (), {"topLevelWidgets": staticmethod(lambda: [self.main])})
        for name in ("QVBoxLayout", "QHBoxLayout", "QPushButton", "QLabel"):
            setattr(gui, name, _Control)
        gui.QCheckBox, gui.QDialog = _Box, _Dialog
        sys.modules["PythonQt.QtCore"].Qt.WindowFlags = staticmethod(int)
        sys.modules["PythonQt.QtCore"].Qt.WindowContextHelpButtonHint = 0x00010000
        _Dialog.made, _Control.made = [], []
        del qtfakes.QTimer.single_shots[:]
        sys.stdout = self.out = Capture()

        def restore():
            settings.tabs_module = original
            _Dialog.run[0] = lambda dialog: 0
            autostart, sys.stdout = saved
            if autostart is None:
                os.environ.pop("FREELAB_NO_AUTOSTART", None)
            else:
                os.environ["FREELAB_NO_AUTOSTART"] = autostart
            if hasattr(sys, "_freelab_tabs_settings_held"):
                del sys._freelab_tabs_settings_held
            qtfakes.uninstall()
        self.addCleanup(restore)

    def show(self, tabs, run):
        _Dialog.run[0] = run
        self.settings.tabs_module = lambda: tabs
        return self.settings.show_dialog()

    def boxes(self):
        return [c for c in _Control.made if isinstance(c, _Box)]

    def labels(self):
        return [c.text for c in _Control.made if type(c) is _Control and c.text]

    def freed_once(self, dialog):
        self.assertIn(dialog, self.settings.held_dialogs(), "held until Qt deletes it")
        for _ms, callback in list(self.qtfakes.QTimer.single_shots):
            callback()
        self.assertEqual(dialog.deleted, 1)
        self.assertNotIn(dialog, self.settings.held_dialogs())

    def test_ok_saves_what_the_boxes_say(self):
        tabs = FakeTabs({"enabled": True, "reorder": True, "no_undock": False})
        seen = {}

        def run(dialog):
            reorder, no_undock = self.boxes()
            seen["shown"] = (reorder.checked, no_undock.checked)
            seen["texts"] = (reorder.text, no_undock.text)
            seen["tips"] = (reorder.tip, no_undock.tip)
            no_undock.setChecked(True)
            return 1
        result = self.show(tabs, run)
        self.assertEqual(seen["shown"], (True, False), "the saved options")
        self.assertEqual(seen["texts"], (self.settings.REORDER, self.settings.NO_UNDOCK))
        self.assertEqual(seen["tips"], (self.settings.REORDER_TIP, self.settings.NO_UNDOCK_TIP))
        self.assertEqual(tabs.configured, [{"enabled": True, "reorder": True, "no_undock": True}])
        self.assertEqual(result, {"enabled": True, "reorder": True, "no_undock": True})
        self.assertNotIn(self.settings.OFF_NOTE, self.labels(), "running: no note")
        self.assertIn(u"is on", self.out.text())
        dialog = _Dialog.made[-1]
        self.assertIs(dialog.parent_, self.main)
        self.assertEqual(dialog.title, "FreeLab Tab Docking")
        self.assertIs(dialog.props.get("mcpScriptWindow"), True)
        self.freed_once(dialog)

    def test_both_unticked_is_off(self):
        tabs = FakeTabs({"enabled": True, "reorder": True, "no_undock": True})

        def run(dialog):
            for box in self.boxes():
                box.setChecked(False)
            return 1
        self.show(tabs, run)
        self.assertEqual(tabs.configured, [{"enabled": False, "reorder": False, "no_undock": False}])
        self.assertIn(u"is off", self.out.text())

    def test_cancel_changes_nothing(self):
        tabs = FakeTabs({"enabled": True})

        def run(dialog):
            self.boxes()[1].setChecked(True)
            return 0
        self.assertIsNone(self.show(tabs, run))
        self.assertEqual(tabs.configured, [])
        self.assertEqual(self.out.text(), u"")
        self.freed_once(_Dialog.made[-1])

    def test_off_says_so(self):
        tabs = FakeTabs({"enabled": False, "reorder": False, "no_undock": True}, on=False)
        seen = {}

        def run(dialog):
            seen["shown"] = tuple(box.checked for box in self.boxes())
            return 1
        self.show(tabs, run)
        self.assertEqual(seen["shown"], (False, True), "the saved options, though off")
        self.assertIn(self.settings.OFF_NOTE, self.labels())
        self.assertEqual(tabs.configured, [{"enabled": True, "reorder": False, "no_undock": True}], "OK switches it on")


if __name__ == "__main__":
    unittest.main()
