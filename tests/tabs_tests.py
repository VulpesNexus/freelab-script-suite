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


class SettingTests(unittest.TestCase):
    def test_on_unless_switched_off(self):
        self.assertTrue(ft.enabled_setting({}))
        self.assertFalse(ft.enabled_setting({"enabled": False}))


if __name__ == "__main__":
    unittest.main()
