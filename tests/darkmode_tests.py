# -*- coding: utf-8 -*-
"""Dark-mode tests against fake PythonQt and fontlab modules; they run under Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import colorsys
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "darkmode"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"

import qtfakes  # noqa: E402
import freelab_dark_mode as dm  # noqa: E402
from qtfakes import FakeWidget, FakeIcon, QAction, QColor, QPalette  # noqa: E402

PANEL_SHEET = u"QWidget{background:#edeeef;color:black;}\nQToolButton{background-color:white;}"
DARK_PANEL_SHEET = dm.recolor_sheet(PANEL_SHEET)


class Mapped(object):
    """Stands for a mapped icon or pixmap (no real images in these tests)."""

    def __init__(self, original):
        self.original = original
        self.key = FakeIcon().key

    def isNull(self):
        return False

    def cacheKey(self):
        return self.key


class DarkModeCase(unittest.TestCase):
    placeholder = True

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="freelab-dark-")
        self._old_env = dict((k, os.environ.get(k)) for k in ("FREELAB_STATE_DIR", "FREELAB_PIXELS_DLL"))
        os.environ["FREELAB_STATE_DIR"] = self.tmp
        os.environ["FREELAB_PIXELS_DLL"] = os.path.join(self.tmp, "missing.dll")
        if hasattr(sys, "_freelab_dark_mode"):
            del sys._freelab_dark_mode
        self.app = qtfakes.install(remove_placeholder=not self.placeholder)
        self._patched = {}
        self.patch("detect_light", lambda widget: widget.light)
        self.patch("dark_icon", lambda icon, owner=None: Mapped(icon))
        self.patch("dark_pixmap", lambda pixmap: Mapped(pixmap))
        self.patch("_process_windows", lambda visible_only=True: [])
        self.patch("frame_keys", lambda widget: list(getattr(widget, "keys", [])))
        self.build_tree()
        self.original_app = (self.app.style().objectName, self.app.palette(), self.app.styleSheet)

    def patch(self, name, value):
        self._patched.setdefault(name, getattr(dm, name))
        setattr(dm, name, value)

    def tearDown(self):
        for name, value in self._patched.items():
            setattr(dm, name, value)
        qtfakes.uninstall()
        if hasattr(sys, "_freelab_dark_mode"):
            del sys._freelab_dark_mode
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build_tree(self):
        W = FakeWidget
        self.main = W("MainWindow", "MainWindow", window=True, width=2000, height=1000)
        self.dock = W("YDock", parent=self.main)
        self.dock.keys = [0xcacbcc]
        self.panel = W("YPanel", parent=self.dock, width=200, height=300)
        self.tabs = W("YTabWidget", parent=self.panel, y=21, sheet=u"QTabWidget{background:none;}")
        self.content = W("PinsPanel", "PinsPanel", parent=self.tabs, sheet=PANEL_SHEET)
        self.label = W("QLabel", "legend", parent=self.content, sheet=u"QLabel{background:rgba(255,255,255,100);}",
                       inherits=("QLabel",))
        self.button = W("QToolButton", "mirror", parent=self.content, icon=FakeIcon("mirror"),
                        inherits=("QAbstractButton",))
        self.swatch = W("ColorPickerItem", parent=self.content, sheet=u"QWidget{background:#ff0000;}")
        self.search = W("YTrackingFrame", "searchFrame", parent=self.content, sheet=u"QWidget{background:white;}")
        self.edit = W("YLineEditArrowDown", parent=self.search, sheet=u"QLineEdit{color:black;}", inherits=("QLineEdit",))
        self.board = W("YSketchBoard", parent=self.main)
        self.canvas = W("QWidget", parent=self.board, width=1500, height=900)
        self.ruler = W("RulerDecorator", parent=self.canvas)
        self.odd = W("QWidget", "odd", parent=self.dock, light="selective")
        self.menu = W("QMenu", parent=self.main, inherits=("QMenu",), visible=False)
        self.action = QAction(FakeIcon("save"))
        self.menu._actions.append(self.action)
        self.app.roots = [self.main]

    def settings(self):
        with open(os.path.join(self.tmp, "darkmode.json")) as handle:
            return json.load(handle)

    def on(self):
        dm.apply_dark()
        dm.run_queue()

    def off(self):
        dm.restore()
        dm.run_queue()

    def kind(self, widget):
        record = dm._record(widget, create=False)
        return record and record.get("kind")

    def no_freelab_traces(self):
        for widget in self.app.allWidgets():
            for name in dm.PROPS:
                self.assertIsNone(widget.property(name), "%s left on %s" % (name, widget._cls))
            self.assertIsNone(widget.effect, widget._cls)
        self.assertIsNone(self.action.property(dm.ID_PROP))
        self.assertEqual(dm._state()["records"], {})


class ColorTests(unittest.TestCase):
    def test_white_and_black_land_on_the_bounds(self):
        dark = int(round(dm.DARK_L * 255))
        light = int(round(dm.LIGHT_L * 255))
        self.assertEqual(dm.map_rgb(255, 255, 255), (dark, dark, dark))
        self.assertEqual(dm.map_rgb(0, 0, 0), (light, light, light))

    def test_hue_is_kept(self):
        for rgb in ((200, 30, 30), (30, 160, 60), (40, 80, 220)):
            h1 = colorsys.rgb_to_hls(*[c / 255.0 for c in rgb])[0]
            h2 = colorsys.rgb_to_hls(*[c / 255.0 for c in dm.map_rgb(*rgb)])[0]
            self.assertAlmostEqual(h1, h2, delta=0.02)

    def test_nothing_mapped_reaches_white_l(self):
        # The selective effects rely on it: a pixel at WHITE_L or above was never mapped.
        for r in range(0, 256, 17):
            for g in range(0, 256, 17):
                for b in range(0, 256, 17):
                    self.assertLess(dm._lightness(*dm.map_rgb(r, g, b)), dm.WHITE_L)

    def test_palette_stays_below_white_l(self):
        for _role, color, disabled in dm.PALETTE:
            for value in filter(None, (color, disabled)):
                rgb = QColor(value).rgba[:3]
                self.assertLess(dm._lightness(*rgb), dm.WHITE_L, value)


class SheetTests(unittest.TestCase):
    def test_formats(self):
        sheet = dm.recolor_sheet(u"a{color:#fff;b:#ffffff;c:#80ffffff;d:rgb(255,255,255);e:rgba(255, 255, 255, 20);"
                                 u"f:rgb(100%,100%,100%);g:white;h:WHITE;}")
        dark = dm._hex(dm.map_rgb(255, 255, 255))
        self.assertEqual(sheet.count(dark), 4)  # #fff, #ffffff, white, WHITE
        self.assertIn(u"#80" + dark[1:], sheet)
        rgb = u"%d, %d, %d" % dm.map_rgb(255, 255, 255)
        self.assertIn(u"rgb(%s)" % rgb, sheet)
        self.assertIn(u"rgba(%s, 20)" % rgb, sheet)
        self.assertEqual(sheet.count(u"rgb(%s)" % rgb), 2)

    def test_selectors_and_properties_are_left_alone(self):
        sheet = u"QFrame#frameBottom{white-space:x;} QWidget#add {color:#000} #face{}"
        out = dm.recolor_sheet(sheet)
        self.assertIn(u"QFrame#frameBottom", out)
        self.assertIn(u"QWidget#add", out)
        self.assertIn(u"white-space", out)
        self.assertIn(u"#face{", out)
        self.assertNotIn(u"#000}", out)

    def test_malformed_values_are_kept(self):
        for sheet in (u"a{color:rgb(1,2);}", u"a{color:rgb(x,y,z);}"):
            self.assertEqual(dm.recolor_sheet(sheet), sheet)


class ClassifyTests(unittest.TestCase):
    def test_classify_render(self):
        self.assertIsNone(dm.classify_render(10, 10, (100, 24, 0), True))
        self.assertEqual(dm.classify_render(10, 10, (100, 25, 1), True), "island")
        self.assertEqual(dm.classify_render(10, 10, (100, 25, 0), True), "selective")
        self.assertEqual(dm.classify_render(10, 10, (100, 90, 50), False), "selective")  # containers never flip whole
        self.assertIsNone(dm.classify_render(0, 0, (0, 0, 0), True))


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.seen = []
        self._saved = (dm.own_render, dm.image_stats)
        dm.own_render = lambda widget: None
        dm.image_stats = lambda image: (10000, 5000, 100)  # light, with dark marks

    def tearDown(self):
        dm.own_render, dm.image_stats = self._saved

    def test_canvas_with_rulers_is_an_island(self):
        canvas = FakeWidget("QWidget", "widget", width=100, height=100)
        FakeWidget("RulerDecorator", parent=canvas, width=100, height=16)
        FakeWidget("RulerDecorator", parent=canvas, width=16, height=100)
        self.assertEqual(dm.detect_light(canvas), "island")

    def test_container_mostly_covered_is_selective(self):
        box = FakeWidget("QWidget", width=100, height=100)
        FakeWidget("QWidget", parent=box, width=100, height=80)
        self.assertEqual(dm.detect_light(box), "selective")

    def test_hidden_children_do_not_count(self):
        box = FakeWidget("QWidget", width=100, height=100)
        FakeWidget("QWidget", parent=box, width=100, height=80, visible=False)
        self.assertEqual(dm.detect_light(box), "island")


class KindTests(DarkModeCase):
    def test_kinds(self):
        self.assertEqual(dm.widget_kind(self.search), "island")
        self.assertEqual(dm.widget_kind(FakeWidget("FontCellChart", "fontChartView")), "island")
        glyph_canvas = FakeWidget("QWidget", "widget", parent=FakeWidget("GlyphWindow", "GlyphWindow"))
        self.assertEqual(dm.widget_kind(glyph_canvas, canvas=True), "island")
        self.assertEqual(dm.widget_kind(self.canvas, canvas=True), "island")
        self.assertIsNone(dm.widget_kind(self.canvas, canvas=False))
        self.assertEqual(dm.widget_kind(self.ruler), "island")
        self.assertEqual(dm.widget_kind(self.tabs), "fill")
        self.assertEqual(dm.widget_kind(self.panel), "title")
        self.assertIsNone(dm.widget_kind(self.content))
        margin = FakeWidget("QWidget", parent=FakeWidget("CodeEditor"), width=14)
        self.assertEqual(dm.widget_kind(margin), "island")
        wide = FakeWidget("QWidget", parent=FakeWidget("CodeEditor"), width=300)
        self.assertIsNone(dm.widget_kind(wide))
        history = FakeWidget("QListWidget", "historyList")
        self.assertEqual(dm.widget_kind(history), "island")

    def test_title_height(self):
        self.assertEqual(dm.title_height(self.panel), 21)
        self.tabs.y = 60
        self.assertEqual(dm.title_height(self.panel), 0)  # too tall to be a title


class OnOffTests(DarkModeCase):
    def test_on_darkens_sheets_and_keeps_originals(self):
        self.on()
        self.assertEqual(self.app.style().objectName, "Fusion")
        self.assertEqual(self.app.palette().color(QPalette.Window), QColor("#2d2d30"))
        self.assertEqual(self.content.styleSheet, DARK_PANEL_SHEET)
        self.assertEqual(self.content.property(dm.SHEET_PROP), PANEL_SHEET)
        self.assertEqual(self.swatch.styleSheet, u"QWidget{background:#ff0000;}", "swatches keep their color")
        self.assertEqual(self.app.styleSheet, u"", "no application stylesheet: it repolishes everything")

    def test_off_restores_everything(self):
        sheets = dict((id(w), w.styleSheet) for w in self.app.allWidgets())
        self.on()
        self.off()
        self.assertEqual((self.app.style().objectName, self.app.palette(), self.app.styleSheet), self.original_app)
        for widget in self.app.allWidgets():
            self.assertEqual(widget.styleSheet, sheets[id(widget)], widget._cls)
            self.assertFalse(widget.set_palette, widget._cls)
        self.assertEqual(self.button.icon.label, "mirror")
        self.assertEqual(self.action.icon.label, "save")
        self.assertFalse(self.tabs.autoFillBackground)
        self.no_freelab_traces()

    def test_island_gets_light_cascade_palette_and_effect(self):
        self.on()
        self.assertEqual(self.kind(self.search), "island")
        self.assertIsNotNone(self.search.effect)
        self.assertEqual(self.search.effect.freelab_min_l, 0.0)
        self.assertEqual(self.search.palette.color(QPalette.Window), QColor(qtfakes.LIGHT_WINDOW))
        # Ancestors' original rules first, its own last: its own stylesheet wins over the dark ones it inherits.
        self.assertEqual(self.search.styleSheet, u"QTabWidget{background:none;}\n" + PANEL_SHEET + u"\nQWidget{background:white;}")
        self.assertEqual(self.edit.styleSheet, u"QLineEdit{color:black;}", "inside an island: left light")

    def test_nested_island_is_undone_inside_canvas(self):
        self.on()
        self.assertEqual(self.kind(self.canvas), "island")
        self.assertIsNone(self.ruler.effect, "mapped once, by the canvas")

    def test_canvas_setting_off(self):
        dm.save_settings({"canvas": False})
        self.on()
        self.assertIsNone(self.canvas.effect)
        self.assertEqual(self.kind(self.ruler), "island")
        self.assertEqual(qtfakes.Preferences.color_workspace, QColor("#ffacacac"), "workspace untouched")

    def test_fill_title_selective_and_icons(self):
        self.on()
        self.assertTrue(self.tabs.autoFillBackground)
        self.assertEqual(self.kind(self.panel), "title")
        self.assertEqual(self.kind(self.odd), "selective")
        self.assertEqual(self.odd.effect.freelab_min_l, dm.WHITE_L)
        self.assertIsInstance(self.button.icon, Mapped)
        self.assertIsInstance(self.action.icon, Mapped)

    def test_icons_are_not_mapped_twice(self):
        self.on()
        mapped = self.button.icon
        dm.apply_dark()
        dm.run_queue()
        self.assertIs(self.button.icon, mapped)
        follower = FakeWidget("QToolButton", parent=self.content, icon=mapped, inherits=("QAbstractButton",))
        dm.process(follower)
        self.assertIs(follower.icon, mapped, "a button showing an already mapped icon keeps it")

    def test_ancestors_are_processed_first(self):
        seen = []

        def detect(widget):
            parent = widget.parentWidget()
            seen.append(parent is None or parent.property(dm.SEEN_PROP) is not None)
            return widget.light

        self.patch("detect_light", detect)
        dm.apply_dark()
        dm._state()["queue"].sort(key=lambda item: -len(list(_ancestors(item[1]))))  # deepest popped last...
        dm._state()["queue"].reverse()  # ...now deepest first
        dm.run_queue()
        self.assertTrue(seen and all(seen))

    def test_restore_keeps_a_stylesheet_fontlab_replaced(self):
        self.on()
        self.content.setStyleSheet(u"QWidget{color:red;}")
        self.off()
        self.assertEqual(self.content.styleSheet, u"QWidget{color:red;}")

    def test_replaced_stylesheet_is_darkened_again(self):
        self.on()
        self.content.setStyleSheet(u"QWidget{background:white;}")
        dm.process(self.content)
        self.assertEqual(self.content.styleSheet, dm.recolor_sheet(u"QWidget{background:white;}"))

    def test_style_is_set_once(self):
        self.on()
        dm.apply_dark()
        dm.run_queue()
        self.assertEqual(self.app.style_sets, 1)

    def test_old_application_block_is_removed(self):
        self.app.setStyleSheet(u"QLabel{}\n" + dm.STYLESHEET_MARK + u"\nQMenu{}")
        self.on()
        self.off()
        self.assertEqual(self.app.styleSheet, u"QLabel{}")

    def test_deleted_widgets_are_skipped(self):
        dm.apply_dark()
        self.label.deleted = True
        dm.run_queue()
        self.assertEqual(dm._state()["errors"], [])


class PreferenceTests(DarkModeCase):
    def test_workspace_saved_set_and_restored(self):
        self.on()
        self.assertEqual(qtfakes.Preferences.color_workspace.name(QColor.HexArgb), dm.WORKSPACE_DARK)
        self.assertEqual(self.settings()["saved_workspace"], u"#ffacacac")
        self.off()
        self.assertEqual(qtfakes.Preferences.color_workspace, QColor("#ffacacac"))
        self.assertNotIn("saved_workspace", self.settings())

    def test_workspace_changed_meanwhile_is_kept(self):
        self.on()
        qtfakes.Preferences.color_workspace = QColor("#ff123456")
        self.off()
        self.assertEqual(qtfakes.Preferences.color_workspace, QColor("#ff123456"))


class ToggleTests(DarkModeCase):
    def test_toggle_saves_the_choice(self):
        self.assertTrue(dm.toggle())
        self.assertEqual(self.settings()["enabled"], True)
        self.assertFalse(dm.toggle())
        self.assertEqual(self.settings()["enabled"], False)

    def test_other_settings_survive(self):
        dm.save_settings({"enabled": False, "future": 1})
        dm.toggle()
        settings = self.settings()
        self.assertEqual((settings["enabled"], settings["future"]), (True, 1))

    def test_bad_settings_file_reads_as_off(self):
        with open(os.path.join(self.tmp, "darkmode.json"), "w") as handle:
            handle.write("[not json")
        dm.startup()
        self.assertEqual(self.app.style().objectName, "windowsvista")

    def test_restore_without_apply_is_harmless(self):
        dm.restore()
        dm.run_queue()
        self.assertEqual((self.app.style().objectName, self.app.palette(), self.app.styleSheet), self.original_app)


class TimerTests(DarkModeCase):
    def test_startup_off_does_nothing(self):
        dm.startup()
        self.assertEqual(qtfakes.QTimer.made, [])

    def test_startup_on_applies_and_schedules(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        intervals = [t.interval for t in qtfakes.QTimer.made if t.single]
        self.assertEqual(intervals, list(dm.REAPPLY_DELAYS_MS))
        # FontLab puts its own style and palette back after the startup script: a reapply wins them back.
        self.app.setStyle(qtfakes.FakeStyle("windowsvista"))
        self.app.setPalette(QPalette())
        [t for t in qtfakes.QTimer.made if t.single][1].fire()
        self.assertEqual(self.app.style().objectName, "Fusion")

    def test_worker_runs_in_slices_and_stops(self):
        dm.apply_dark()
        worker = dm._state()["worker"]
        self.assertTrue(worker is not None and worker.running and worker.interval == 0)
        while dm._state()["queue"]:
            worker.fire()
        worker.fire()
        self.assertIsNone(dm._state()["worker"])

    def test_sweep_picks_up_new_widgets(self):
        self.on()
        late = FakeWidget("QWidget", parent=self.content, sheet=u"QWidget{background:white;}")
        dm._sweep()
        dm.run_queue()
        self.assertEqual(late.styleSheet, dm.recolor_sheet(u"QWidget{background:white;}"))

    def test_focus_change_darkens_a_new_window_at_once(self):
        self.on()
        late = FakeWidget("QWidget", parent=self.content, sheet=u"QWidget{background:white;}")
        self.app.emit("focusChanged(QWidget*,QWidget*)", None, late)
        self.assertEqual(late.styleSheet, dm.recolor_sheet(u"QWidget{background:white;}"), "no timer needed")

    def test_focus_hook_is_connected_once_and_idle_when_off(self):
        self.on()
        dm.apply_dark()
        self.assertEqual(len(self.app.signals["focusChanged(QWidget*,QWidget*)"]), 1)
        self.off()
        late = FakeWidget("QWidget", parent=self.content, sheet=u"QWidget{background:white;}")
        self.app.emit("focusChanged(QWidget*,QWidget*)", None, late)
        self.assertEqual(late.styleSheet, u"QWidget{background:white;}")

    def test_sweep_prunes_dead_records(self):
        self.on()
        count = len(dm._state()["records"])
        self.search.deleted = True
        dm._sweep()
        self.assertEqual(len(dm._state()["records"]), count - 1)

    def test_toggling_off_cancels_timers(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        dm.toggle()
        dm.run_queue()  # the worker stops once switching off has restored every widget
        self.assertTrue(all(not t.running for t in qtfakes.QTimer.made))


class TitleBarTests(DarkModeCase):
    def test_title_bars_follow_dark_mode(self):
        dark = {101: False, 102: False, 103: False}  # 103: hidden
        calls = []

        def windows(visible_only=True):
            return [101, 102] if visible_only else [101, 102, 103]

        def set_bar(hwnd, value):
            calls.append((hwnd, value))
            dark[hwnd] = value

        self.patch("_process_windows", windows)
        self.patch("_set_title_bar", set_bar)
        self.patch("_title_bar_is_dark", lambda hwnd: dark[hwnd])
        old_platform = sys.platform
        sys.platform = "win32"
        try:
            dm.dark_title_bars(True)
            dm.dark_title_bars(True)  # already dark: not again
            dark[103] = True  # made dark while it was shown, hidden since
            dm.dark_title_bars(False)
        finally:
            sys.platform = old_platform
        self.assertEqual(calls, [(101, True), (102, True), (101, False), (102, False), (103, False)])


class ReviewTests(DarkModeCase):
    """Cases found by the independent review of 2026-11-06."""

    def test_on_again_before_off_finished(self):
        self.on()
        dm.restore()  # light entries queued, not run yet
        dm.apply_dark()
        dm.run_queue()
        self.assertEqual(self.content.styleSheet, DARK_PANEL_SHEET)
        self.assertEqual(self.kind(self.search), "island")

    def test_popup_window_inside_an_island_is_darkened_itself(self):
        popup = FakeWidget("QMenu", parent=self.search, window=True, inherits=("QMenu",))
        action = QAction(FakeIcon("tool"))
        popup._actions.append(action)
        self.on()
        self.assertIsNone(dm._island_ancestor(popup, True))
        self.assertIsInstance(action.icon, Mapped)

    def test_fontlabs_own_effect_survives(self):
        theirs = object()
        self.odd.effect = theirs
        self.panel.effect = theirs
        self.on()
        self.off()
        self.assertIs(self.odd.effect, theirs)
        self.assertIs(self.panel.effect, theirs)

    def test_island_stylesheet_replaced_gets_the_cascade_again(self):
        self.on()
        self.search.setStyleSheet(u"QWidget{background:white;border:1px solid blue;}")
        dm.process(self.search)
        self.assertTrue(self.search.styleSheet.startswith(u"QTabWidget{background:none;}"))
        self.assertTrue(self.search.styleSheet.endswith(u"QWidget{background:white;border:1px solid blue;}"))
        self.off()
        self.assertEqual(self.search.styleSheet, u"QWidget{background:white;border:1px solid blue;}")

    def test_button_in_island_following_a_mapped_action_shows_the_original(self):
        follower = FakeWidget("QToolButton", parent=self.search, inherits=("QAbstractButton",))
        self.app.roots = [self.main]
        dm.apply_dark()
        dm.process(self.menu)  # the menu maps the action icon first
        follower.icon = self.action.icon  # the button follows its action
        dm.run_queue()
        self.assertEqual(follower.icon.label, "save")

    def test_errors_with_undecodable_text_are_kept(self):
        class Odd(Exception):
            def __str__(self):
                return "\x83\x82"  # bytes in the ANSI code page under Python 2

            def __unicode__(self):
                raise UnicodeDecodeError("ascii", b"\x83", 0, 1, "bad")

        dm._note_error("native", Odd())
        self.assertEqual(len(dm._state()["errors"]), 1)

    def test_fontlab_case_placeholder_by_number_through_on_and_off(self):
        saved = QPalette.PlaceholderText
        del QPalette.PlaceholderText
        try:
            own = QPalette()
            own.setColor(QPalette.Text, QColor("#000000"))
            self.edit.setPalette(own)
            self.on()
            self.assertEqual(self.edit.palette.color(dm.PLACEHOLDER_ROLE_VALUE), QColor(dm.ISLAND_PLACEHOLDER))
            self.off()
            self.assertEqual(self.edit.palette, own, "its own palette is back")
        finally:
            QPalette.PlaceholderText = saved

    def test_repeated_cycles_leave_no_trace(self):
        sheets = dict((id(w), w.styleSheet) for w in self.app.allWidgets())
        for _ in range(3):
            self.on()
            self.off()
        for widget in self.app.allWidgets():
            self.assertEqual(widget.styleSheet, sheets[id(widget)])
        self.no_freelab_traces()


class FrameAndPlaceholderTests(DarkModeCase):
    def test_dock_frames_are_keyed(self):
        self.on()
        self.assertEqual(self.kind(self.dock), "keyed")
        self.assertEqual(self.dock.effect.freelab_keys, [0xcacbcc])

    def test_dock_without_light_frames_gets_no_effect(self):
        self.dock.keys = []
        self.on()
        self.assertIsNone(self.dock.effect)

    def test_island_line_edit_gets_a_darker_placeholder(self):
        self.on()
        placeholder = self.edit.palette.color(QPalette.PlaceholderText)
        self.assertEqual(placeholder, QColor(dm.ISLAND_PLACEHOLDER))
        self.off()
        self.assertFalse(self.edit.set_palette)

    def test_placeholder_role_by_number_when_pythonqt_lacks_the_name(self):
        saved = QPalette.PlaceholderText
        del QPalette.PlaceholderText
        try:
            self.assertEqual(dm._role(QPalette, "PlaceholderText"), dm.PLACEHOLDER_ROLE_VALUE)
            qtfakes.QT_VERSION[0] = "5.11.3"
            self.assertIsNone(dm._role(QPalette, "PlaceholderText"))
        finally:
            QPalette.PlaceholderText = saved

    def test_light_colors_without_the_helper(self):
        self.assertEqual(dm.light_colors(None), [])


class OldQtTests(DarkModeCase):
    placeholder = False

    def test_missing_palette_role_is_skipped(self):
        qtfakes.QT_VERSION[0] = "5.9.0"  # neither the name nor the role
        dm.apply_dark()
        roles = set(role for _group, role in self.app.palette().colors)
        self.assertNotIn("PlaceholderText", roles)
        self.assertIn("Window", roles)


def _ancestors(widget):
    parent = widget.parentWidget()
    while parent is not None:
        yield parent
        parent = parent.parentWidget()


if __name__ == "__main__":
    unittest.main()
