# -*- coding: utf-8 -*-
"""Tests of FreeLab's tab docking (where a dropped tab goes). Valid Python 2.7 and Python 3."""
from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "windows"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_tabs as ft  # noqa: E402

TAB_WIDTH, BAR_HEIGHT = 100, 24


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
            "QEvent": type("QEvent", (), {"MouseButtonPress": 2, "MouseButtonDblClick": 4}),
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


if __name__ == "__main__":
    unittest.main()
