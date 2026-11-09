# -*- coding: utf-8 -*-
"""Dark-mode tests against fake PythonQt and fontlab modules; they run under Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import json
import math
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
from qtfakes import FakeGeometry, FakeWidget, FakeIcon, QAction, QColor, QPalette  # noqa: E402

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
        self.patch("detect_ink", lambda widget: getattr(widget, "ink", None))
        self.patch("_relight_editors", lambda app: None)
        self.patch("dark_icon", lambda icon, owner=None: Mapped(icon))
        self.patch("dark_pixmap", lambda pixmap: Mapped(pixmap))
        self.patch("_process_windows", lambda: [])
        self.patch("frame_keys", lambda widget: list(getattr(widget, "keys", [])))
        self.patch("icon_is_swatch", lambda icon: getattr(icon, "label", "") == "swatch")
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
        self.assertEqual(dm.map_rgb(255, 255, 255), (dm.DARK_GRAY,) * 3)
        self.assertEqual(dm.map_rgb(0, 0, 0), (dm.LIGHT_GRAY,) * 3)

    def test_hue_is_kept(self):
        # Hue as OKLab measures it (the mapping works there); pure blue was turning violet in CIELAB.
        for rgb in ((200, 30, 30), (30, 160, 60), (40, 80, 220), (0, 0, 255)):
            _, a1, b1 = dm.oklab(*rgb)
            _, a2, b2 = dm.oklab(*dm.map_rgb(*rgb))
            difference = abs(math.atan2(b1, a1) - math.atan2(b2, a2))
            self.assertLess(min(difference, 2 * math.pi - difference), 0.12, str(rgb))

    def test_tinted_whites_turn_grey(self):
        # #fffffa (FontLab's metrics background) turned khaki, and bluish whites navy, under HLS.
        for rgb in ((255, 255, 250), (238, 242, 255), (204, 228, 255)):
            out = dm.map_rgb(*rgb)
            self.assertLessEqual(max(out) - min(out), 18, (rgb, out))
            self.assertLess(dm._lightness(*out), 0.25)


    def test_cleartype_fringes_and_faint_tints_turn_gray(self):
        for rgb in ((220, 200, 160), (200, 220, 255), (255, 240, 230), (90, 70, 60)):
            out = dm.map_rgb(*rgb)
            self.assertEqual(max(out) - min(out), 0, (rgb, out))

    def test_marks_keep_their_color(self):
        r, g, b = dm.map_rgb(255, 0, 0)
        self.assertGreater(r, 3 * max(g, b, 1))

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


class ContentTests(DarkModeCase):
    def test_content_islands_keep_every_color(self):
        self.on()
        self.assertEqual(self.canvas.effect.freelab_keep_tint, dm.KEEP_TINT_CONTENT, "anchors and nodes keep their colors")
        self.assertEqual(self.search.effect.freelab_keep_tint, 0.0)
        node = (106, 160, 106)
        out = dm.map_rgb(*node, keep_tint=dm.KEEP_TINT_CONTENT)
        self.assertGreater(out[1], out[0] + 10)

    def test_mark_slots_keep_their_colors(self):
        slot = FakeWidget("QToolButton", "flagRed", parent=self.content, sheet=u"QToolButton{background-color:#ff8080;}",
                          inherits=("QAbstractButton",))
        self.on()
        self.assertEqual(slot.styleSheet, u"QToolButton{background-color:#ff8080;}")
        self.assertIsNone(slot.effect)

    def test_the_swatch_popup_is_darkened_but_not_its_swatches(self):
        popup = FakeWidget("ColorPickerPopup", parent=self.content, sheet=u"QWidget{background:white;}")
        item = FakeWidget("ColorPickerItem", parent=popup, sheet=u"QWidget{background:#ffffff;}")
        self.on()
        self.assertEqual(popup.styleSheet, dm.recolor_sheet(u"QWidget{background:white;}"))
        self.assertEqual(item.styleSheet, u"QWidget{background:#ffffff;}")

    def test_dark_interface_mode_leaves_content_light(self):
        dm.save_settings({"content": False})
        self.on()
        self.assertIsNone(self.canvas.effect)
        self.assertEqual(qtfakes.Preferences.color_workspace, QColor("#ffacacac"), "the workspace color is left too")
        self.assertIsNotNone(self.search.effect, "the interface is still dark")

    def test_dark_interface_mode_keeps_content_out_of_the_ink_around_it(self):
        dm.save_settings({"content": False})
        self.odd.light = "ink"
        cells = FakeWidget("FontCellChart", "fontChartView", parent=self.odd, inherits=("FontCellChart",))
        self.on()
        self.assertIsNone(cells.effect)
        self.assertIn(cells, list(self.odd.effect.freelab_protect.values()), "drawn as FontLab paints it")


class ShadeAndPickerTests(DarkModeCase):
    def tearDown(self):
        dm.set_shade("dark")
        DarkModeCase.tearDown(self)

    def test_medium_shade(self):
        dm.configure(dark=True, shade="medium")
        dm.run_queue()
        self.assertEqual(self.app.palette().color(QPalette.Window), QColor("#44444a"))
        self.assertEqual(dm.map_rgb(255, 255, 255), (60, 60, 60))
        self.assertIn(dm._hex((60, 60, 60)), self.content.styleSheet)

    def test_changing_the_shade_rebuilds(self):
        dm.configure(dark=True)
        dm.run_queue()
        dark_sheet = self.content.styleSheet
        dm.configure(shade="medium")
        dm.run_queue()
        self.assertNotEqual(self.content.styleSheet, dark_sheet)
        dm.configure(dark=False)
        dm.run_queue()
        self.assertEqual(self.content.styleSheet, PANEL_SHEET)

    def test_color_pickers_get_a_dark_frame_and_lose_it(self):
        picker = FakeWidget("QtColorPicker", "colorMark", parent=self.content, sheet=u"QtColorPicker{color: lightGray;}")
        self.on()
        self.assertEqual(picker.styleSheet, u"QtColorPicker{color: lightGray;}" + dm.PICKER_FRAME)
        self.assertEqual(picker.effect.freelab_kind, "picker", "only its arrow is mapped")
        self.off()
        self.assertEqual(picker.styleSheet, u"QtColorPicker{color: lightGray;}")
        self.assertIsNone(picker.effect)

    def test_effects_protect_the_effects_inside_them_but_not_themselves(self):
        self.on()
        dock_protect = list(self.dock.effect.freelab_protect.values())
        self.assertIn(self.search, dock_protect, "the search field's island is drawn as it comes out of its own effect")
        self.assertNotIn(self.dock, dock_protect)
        self.assertNotIn(self.canvas, list(getattr(self.canvas.effect, "freelab_protect", {}).values()),
                         "an effect that kept itself unmapped would draw its widget raw")

    def test_swatches_are_drawn_unmapped_by_the_effect_above_them(self):
        self.odd.light = "ink"
        slot = FakeWidget("QToolButton", "flagRed", parent=self.odd, inherits=("QAbstractButton",))
        self.on()
        self.assertEqual(list(self.odd.effect.freelab_protect.values()), [slot])

    def test_content_islands_keep_their_tints(self):
        self.on()
        self.assertEqual(self.canvas.effect.freelab_keep_tint, dm.KEEP_TINT_CONTENT)
        self.assertEqual(self.search.effect.freelab_keep_tint, 0.0)

    def test_dock_frame_ends_take_the_mapped_frame_color(self):
        self.on()
        r, g, b = dm.map_rgb(0xca, 0xcb, 0xcc)
        self.assertEqual(self.dock.effect.freelab_edge_target, (r << 16) | (g << 8) | b)


class OptionTests(DarkModeCase):
    def test_follow_windows_switches_with_windows(self):
        dark = [True]
        self.patch("windows_is_dark", lambda: dark[0])
        dm.configure(follow_windows=True)
        self.assertTrue(dm._state()["on"])
        watch = dm._state()["theme_watch"]
        self.assertTrue(watch is not None and watch.running)
        dark[0] = False
        watch.fire()
        dm.run_queue()
        self.assertFalse(dm._state()["on"])
        dark[0] = True
        watch.fire()
        self.assertTrue(dm._state()["on"])

    def test_switching_by_hand_stops_following(self):
        self.patch("windows_is_dark", lambda: True)
        dm.configure(follow_windows=True)
        dm.toggle()
        self.assertFalse(self.settings()["follow_windows"])
        self.assertIsNone(dm._state()["theme_watch"])

    def test_changing_the_content_option_rebuilds(self):
        dm.configure(dark=True)
        dm.run_queue()
        self.assertIsNotNone(self.canvas.effect)
        dm.configure(content=False)
        dm.run_queue()
        self.assertIsNone(self.canvas.effect)
        self.assertTrue(dm._state()["on"])

    def test_startup_follows_windows(self):
        self.patch("windows_is_dark", lambda: True)
        dm.save_settings({"enabled": False, "follow_windows": True})
        dm.startup()
        self.assertTrue(dm._state()["on"])

    def test_older_canvas_setting_still_counts(self):
        self.assertFalse(dm.content_setting({"canvas": False}))
        self.assertTrue(dm.content_setting({}))

class SheetTests(unittest.TestCase):
    def test_formats(self):
        sheet = dm.recolor_sheet(u"a{x:#fff;b:#ffffff;c:#80ffffff;d:rgb(255,255,255);e:rgba(255, 255, 255, 20);"
                                 u"f:rgb(100%,100%,100%);g:white;h:WHITE;}")
        dark = dm._hex(dm.map_rgb(255, 255, 255))
        self.assertEqual(sheet.count(dark), 4)  # #fff, #ffffff, white, WHITE
        self.assertIn(u"#80" + dark[1:], sheet)
        rgb = u"%d, %d, %d" % dm.map_rgb(255, 255, 255)
        self.assertIn(u"rgb(%s)" % rgb, sheet)
        self.assertIn(u"rgba(%s, 20)" % rgb, sheet)
        self.assertEqual(sheet.count(u"rgb(%s)" % rgb), 2)

    def test_both_css_spellings_of_gray_are_colors(self):
        for name in ("gray", "grey", "lightgray", "lightgrey", "darkgrey", "dimgrey"):
            self.assertIn(name, dm.NAMED_COLORS)
            self.assertNotIn(name, dm.recolor_sheet(u"a{x:%s;}" % name), name)

    def test_selectors_and_properties_are_left_alone(self):
        sheet = u"QFrame#frameBottom{white-space:x;} QWidget#add {color:#000} #face{}"
        out = dm.recolor_sheet(sheet)
        self.assertIn(u"QFrame#frameBottom", out)
        self.assertIn(u"QWidget#add", out)
        self.assertIn(u"white-space", out)
        self.assertIn(u"#face{", out)
        self.assertNotIn(u"#000}", out)

    def test_dark_surfaces_and_light_text_stay(self):
        out = dm.recolor_sheet(u"QWidget#bar{background:#2b2b2b;color:#ffffff;border:1px solid black;}")
        self.assertIn(u"background:#2b2b2b", out)
        self.assertIn(u"border:1px solid black", out)
        self.assertIn(u"color:#dcdcdc", out, "kept white text is capped below the selective threshold")

    def test_light_surfaces_and_dark_text_turn(self):
        out = dm.recolor_sheet(u"QLabel{background-color:#edeeef;color:#000000;selection-background-color:white;}")
        self.assertIn(u"background-color:%s" % dm._hex(dm.map_rgb(0xed, 0xee, 0xef)), out)
        self.assertIn(u"color:%s" % dm._hex(dm.map_rgb(0, 0, 0)), out)
        self.assertIn(u"selection-background-color:%s" % dm._hex(dm.map_rgb(255, 255, 255)), out)

    def test_selectors_with_colons_are_left_alone(self):
        sheet = u"QScrollBar::handle:hover{background:#a0a0a0;} QToolButton:checked{color:black;}"
        out = dm.recolor_sheet(sheet)
        self.assertIn(u"QScrollBar::handle:hover{", out)
        self.assertIn(u"QToolButton:checked{", out)

    def test_malformed_values_are_kept(self):
        for sheet in (u"a{color:rgb(1,2);}", u"a{color:rgb(x,y,z);}"):
            self.assertEqual(dm.recolor_sheet(sheet), sheet)


class ClassifyTests(unittest.TestCase):
    def test_classify_render(self):
        self.assertIsNone(dm.classify_render(10, 10, (100, 2, 0), True))
        self.assertEqual(dm.classify_render(10, 10, (100, 24, 0), True), "ink", "an editor's white margin")
        self.assertIsNone(dm.classify_render(10, 10, (100, 24, 0), False))
        self.assertEqual(dm.classify_render(10, 10, (100, 25, 1), True), "island")
        self.assertEqual(dm.classify_render(10, 10, (100, 25, 0), True), "ink")
        self.assertEqual(dm.classify_render(10, 10, (100, 90, 50), False), "ink")  # containers never flip whole
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
        self.assertEqual(dm.detect_light(box), "ink")

    def test_hidden_children_do_not_count(self):
        box = FakeWidget("QWidget", width=100, height=100)
        FakeWidget("QWidget", parent=box, width=100, height=80, visible=False)
        self.assertEqual(dm.detect_light(box), "island")


class SettingsModuleTests(unittest.TestCase):
    def test_settings_module_imports_without_fontlab(self):
        # FontLab runs it under Python 2.7: it must at least load there, with PythonQt imported only when shown.
        os.environ["FREELAB_NO_AUTOSTART"] = "1"
        try:
            import freelab_dark_mode_settings as settings  # noqa: F401
        finally:
            del os.environ["FREELAB_NO_AUTOSTART"]
        self.assertTrue(callable(settings.show_dialog))


class FakeSci(object):
    """SendScintilla on a fake editor: style colors, caret, and caret line, as Scintilla's BGR integers."""

    def __init__(self, fore, back, caret=0x000000, caret_line=0xffffff):
        self.colors = {}
        for style in range(256):
            self.colors[(dm.SCI_STYLESETFORE, style)] = fore.get(style, 0x000000)
            self.colors[(dm.SCI_STYLESETBACK, style)] = back.get(style, 0xffffff)
        self.colors[(dm.SCI_SETCARETFORE, None)] = caret
        self.colors[(dm.SCI_SETCARETLINEBACK, None)] = caret_line
        self.sets = 0

    def __call__(self, pointer, message, w, l):
        getters = {dm.SCI_STYLEGETFORE: dm.SCI_STYLESETFORE, dm.SCI_STYLEGETBACK: dm.SCI_STYLESETBACK}
        if message in getters:
            return self.colors[(getters[message], w)]
        if message == dm.SCI_GETCARETFORE:
            return self.colors[(dm.SCI_SETCARETFORE, None)]
        if message == dm.SCI_GETCARETLINEBACK:
            return self.colors[(dm.SCI_SETCARETLINEBACK, None)]
        self.sets += 1
        if message in (dm.SCI_STYLESETFORE, dm.SCI_STYLESETBACK):
            self.colors[(message, w)] = l
        else:
            self.colors[(message, None)] = w
        return 0


class LightPalette(object):
    class White(object):
        def red(self):
            return 255

        green = blue = red

    def color(self, role):
        return self.White()


class EditorTests(DarkModeCase):
    NAVY, RED, WHITE, DARK = 0xad7559, 0x6d6fd6, 0xffffff, 0x1e1e1e  # BGR

    def setUp(self):
        DarkModeCase.setUp(self)
        self.patch("_sci_pointer", lambda widget: 0x1000)
        self.editor = FakeWidget("QsciScintilla", "JsonCode")

    def use(self, sci):
        self.patch("_sci_send", lambda: sci)
        return sci

    def rgb(self, value):
        return dm._bgr_to_rgb(value)

    def test_text_colors_keep_their_hue(self):
        self.assertEqual(dm.editor_text_rgb((0, 0, 0)), tuple(dm.map_rgb(0, 0, 0)), "black text: light gray")
        r, g, b = dm.editor_text_rgb((0x59, 0x75, 0xad))
        self.assertGreater(b, r + 40, "navy keys stay blue")
        self.assertGreaterEqual(dm.oklab(r, g, b)[0], dm.EDITOR_TEXT_MIN_L - 0.02)
        self.assertEqual(dm.editor_paper_rgb((0x1e, 0x1e, 0x1e)), (0x1e, 0x1e, 0x1e), "dark paper kept")
        self.assertLess(dm._lightness(*dm.editor_paper_rgb((255, 255, 255))), 0.3, "white paper mapped dark")

    def test_editor_is_colored_natively_and_put_back(self):
        sci = self.use(FakeSci({0: 0x000000, 4: self.NAVY, 1: self.RED}, {s: self.DARK for s in range(256)}))
        dm._state()["on"] = True
        record = dm._record(self.editor)
        self.assertTrue(dm._darken_editor(self.editor, record))
        fore0 = self.rgb(sci.colors[(dm.SCI_STYLESETFORE, 0)])
        self.assertGreater(dm._lightness(*fore0), 0.6, "black text drawn light")
        self.assertFalse(dm._editor_restyled(self.editor, record))
        sets = sci.sets
        dm._darken_editor(self.editor, record)
        self.assertEqual(sci.sets, sets, "nothing set twice")
        sci.colors[(dm.SCI_STYLESETFORE, 0)] = 0x000000  # FontLab restyles the editor
        self.assertTrue(dm._editor_restyled(self.editor, record))
        dm._darken_editor(self.editor, record)
        self.assertGreater(dm._lightness(*self.rgb(sci.colors[(dm.SCI_STYLESETFORE, 0)])), 0.6)
        dm._restore_editor(self.editor, record)  # still on: FontLab's own colors back, as they were
        self.assertEqual(sci.colors[(dm.SCI_STYLESETFORE, 4)], self.NAVY)
        self.assertEqual(sci.colors[(dm.SCI_STYLESETBACK, 0)], self.DARK)
        self.assertNotIn("sci", record)

    def test_switching_off_gives_dark_made_editors_light_paper(self):
        sci = self.use(FakeSci({0: 0x000000, 11: 0xdcdcdc}, {s: self.DARK for s in range(256)}))
        state = dm._state()
        state["on"] = True
        record = dm._record(self.editor)
        dm._darken_editor(self.editor, record)
        state["on"] = False
        state["saved"] = {"palette": LightPalette()}
        dm._restore_editor(self.editor, record)
        self.assertEqual(sci.colors[(dm.SCI_STYLESETBACK, 0)], self.WHITE, "dark paper made light")
        self.assertEqual(sci.colors[(dm.SCI_STYLESETFORE, 0)], 0x000000, "black text kept")
        self.assertLess(dm._lightness(*self.rgb(sci.colors[(dm.SCI_STYLESETFORE, 11)])), 0.4, "light gray text made dark")

    def test_light_gray_text_stays_light(self):
        self.assertGreater(dm._lightness(*dm.editor_text_rgb((0xdc, 0xdc, 0xdc))), 0.6, "palette text on dark paper")

    def test_a_restyle_of_any_lexer_style_is_noticed(self):
        sci = self.use(FakeSci({5: self.NAVY}, {s: self.DARK for s in range(256)}))
        dm._state()["on"] = True
        record = dm._record(self.editor)
        dm._darken_editor(self.editor, record)
        self.assertFalse(dm._editor_restyled(self.editor, record))
        sci.colors[(dm.SCI_STYLESETFORE, 5)] = self.NAVY
        self.assertTrue(dm._editor_restyled(self.editor, record))

    def test_switching_off_leaves_a_light_made_editor_its_light_grays(self):
        sci = self.use(FakeSci({37: 0xc0c0c0}, {}))  # white paper: made in light mode
        state = dm._state()
        state["on"] = True
        record = dm._record(self.editor)
        dm._darken_editor(self.editor, record)
        state["on"] = False
        state["saved"] = {"palette": LightPalette()}
        dm._restore_editor(self.editor, record)
        self.assertEqual(sci.colors[(dm.SCI_STYLESETFORE, 37)], 0xc0c0c0)
        self.assertEqual(sci.colors[(dm.SCI_STYLESETBACK, 0)], self.WHITE)

    def test_a_color_fontlab_changed_meanwhile_is_left(self):
        sci = self.use(FakeSci({4: self.NAVY}, {}))
        dm._state()["on"] = True
        record = dm._record(self.editor)
        dm._darken_editor(self.editor, record)
        sci.colors[(dm.SCI_STYLESETFORE, 4)] = self.RED
        dm._restore_editor(self.editor, record)
        self.assertEqual(sci.colors[(dm.SCI_STYLESETFORE, 4)], self.RED)

    def test_without_scintilla_nothing_happens(self):
        self.patch("_sci_send", lambda: None)
        record = dm._record(self.editor)
        self.assertFalse(dm._darken_editor(self.editor, record))
        self.assertNotIn("sci", record)


class FakeHooks(object):
    """The native engine's library, faked: what dark mode asks of it."""

    def __init__(self):
        self.calls = []

    def freelab_hooks_set_palette(self, dark, light):
        self.calls.append("set_palette")
        return 63

    def freelab_hooks_install(self, dark_l, light_l, keep_tint):
        self.calls.append("install")
        return 24

    def freelab_hooks_set_hooked(self, widgets, count):
        self.calls.append("set_hooked")
        self.hooked = count
        return count

    def freelab_hooks_set_ink(self, widgets, count):
        self.calls.append("set_ink")
        return count

    def freelab_hooks_add_ink_module(self, module):
        return 2

    def freelab_hooks_set_subpixel(self, widgets, count, background_okl):
        self.calls.append("set_subpixel")
        return count

    def freelab_hooks_remove(self):
        self.calls.append("remove")
        return 24


class LeaveAloneTests(DarkModeCase):
    def test_a_widget_can_ask_to_be_left_alone(self):
        # Auto Kerning's preview buttons draw pairs in the palette's own colors: mapped as icons, they
        # would have turned dark
        button = FakeWidget("QToolButton", "preview", parent=self.content, icon=FakeIcon("pair"),
                            inherits=("QAbstractButton",), light="ink")
        button.setProperty(dm.LEAVE_ALONE_PROP, True)
        self.on()
        self.assertIsNone(button.effect)
        self.assertEqual(button.icon.label, "pair", "its icon as it is")


    def test_a_marked_container_leaves_its_children_alone(self):
        panel = FakeWidget("QWidget", "previews", parent=self.content)
        panel.setProperty(dm.LEAVE_ALONE_PROP, True)
        button = FakeWidget("QToolButton", "preview", parent=panel, icon=FakeIcon("pair"),
                            inherits=("QAbstractButton",), light="ink")
        self.on()
        self.assertIsNone(button.effect)
        self.assertEqual(button.icon.label, "pair")

    def test_left_alone_icons_are_never_swapped(self):
        # Auto Kerning's previews once came back mapped (dark gray glyphs): the swap itself refuses them
        button = FakeWidget("QToolButton", "preview", parent=self.content, icon=FakeIcon("pair"),
                            inherits=("QAbstractButton",))
        button.setProperty(dm.LEAVE_ALONE_PROP, True)
        self.on()
        dm._darken_icons(button)
        dm._swap_icon(button)
        self.assertEqual(button.icon.label, "pair")


class LabelPixmap(object):
    def __init__(self, side=16):
        self.side = side
        self.key = FakeIcon().key

    def isNull(self):
        return False

    def cacheKey(self):
        return self.key

    def width(self):
        return self.side

    def height(self):
        return self.side


class VisibleColumnTests(unittest.TestCase):
    class View(object):
        def __init__(self, hidden=()):
            self.hidden = hidden

        def columnViewportPosition(self, column):
            return column * 100 - 30  # scrolled 30 pixels to the right

        def columnWidth(self, column):
            return 100

        def isColumnHidden(self, column):
            return column in self.hidden

    def test_only_the_columns_on_screen(self):
        self.assertEqual(dm._visible_columns(self.View(), 8, 250), [0, 1, 2])
        self.assertEqual(dm._visible_columns(self.View(hidden=(1,)), 8, 250), [0, 2])
        self.assertEqual(dm._visible_columns(object(), 3, 250), [0, 1, 2], "a list: its one column, or all")


class InkLabelTests(DarkModeCase):
    # The font window's mark flag (QLabel#labelMark): mapped, then mapped again by the window's ink
    # effect, its pole turned black. Inside the ink effect, a label's image is mapped once, by the effect.
    def test_a_label_inside_the_ink_effect_keeps_its_image(self):
        self.odd.light = "ink"
        flag = FakeWidget("QLabel", "labelMark", parent=self.odd, inherits=("QLabel",))
        original = flag.pixmap = LabelPixmap()
        self.on()
        self.assertIsNotNone(self.odd.effect)
        self.assertIs(flag.pixmap, original)

    def test_a_label_mapped_before_the_ink_effect_gets_its_image_back(self):
        box = FakeWidget("QWidget", "box", parent=self.content)
        flag = FakeWidget("QLabel", "labelMark", parent=box, inherits=("QLabel",))
        original = flag.pixmap = LabelPixmap()
        self.on()
        self.assertIsInstance(flag.pixmap, Mapped)
        dm._set_effect(box, dm._record(box), "ink")
        self.assertIs(flag.pixmap, original)
        self.assertNotIn("pixmap", dm._record(flag), "nothing left to restore when switching off")

    def test_a_protected_widget_between_keeps_its_labels_images(self):
        # the ink effect draws a protected widget (the defringe bar) unmapped: an image inside it stays
        # as dark mode mapped it, and is never handed back to the effect
        box = FakeWidget("QWidget", "box", parent=self.content)
        bar = FakeWidget("QFrame", "frameBottom", parent=box)
        icon = FakeWidget("QLabel", "labelIcon", parent=bar, inherits=("QLabel",))
        icon.pixmap = LabelPixmap()
        self.on()
        mapped = icon.pixmap
        self.assertIsInstance(mapped, Mapped)
        dm._protect(bar)
        dm._set_effect(box, dm._record(box), "ink")
        self.assertFalse(dm._under_ink(icon))
        self.assertIs(icon.pixmap, mapped)

    def test_an_image_fontlab_replaced_meanwhile_stays(self):
        box = FakeWidget("QWidget", "box", parent=self.content)
        flag = FakeWidget("QLabel", "labelMark", parent=box, inherits=("QLabel",))
        flag.pixmap = LabelPixmap()
        self.on()
        newer = flag.pixmap = LabelPixmap()  # FontLab's own, set after the swap
        dm._set_effect(box, dm._record(box), "ink")
        self.assertIs(flag.pixmap, newer)


class LightLabelTests(DarkModeCase):
    # The font window's "SEARCH HISTORY" header: light gray text from the dark palette, on its dark
    # panel. The window's ink effect mapped it among the window's colors and broke it up.
    def title_label(self, text, parent_window="#292929", ink="#afafaf", sheet=u"QLabel{padding-left: 2px;}"):
        panel = FakeWidget("QWidget", "historyWidget", parent=self.content)
        panel.palette.setColor(QPalette.Window, QColor(parent_window))
        label = FakeWidget("YTitleLabel", "historyLabel", parent=panel, sheet=sheet, inherits=("QLabel",))
        label.text = text
        label.palette.setColor(QPalette.WindowText, QColor(ink))
        return label

    def test_light_text_from_the_dark_palette_is_protected(self):
        label = self.title_label(u"SEARCH HISTORY")
        self.on()
        self.assertTrue(dm._record(label).get("protected"))

    def test_a_light_badge_under_the_parents_ink_is_read_unmapped(self):
        # the parent's own ink effect shows its light badge dark in a grab: read with the effect paused,
        # the label on the badge is not protected (it would be drawn light on light)
        label = self.title_label(u"3")
        panel = label.parentWidget()
        panel.light = "ink"
        panel.ground, panel.mapped_ground = 0xf0f0f0, 0x303030
        self.on()
        self.assertIsNotNone(panel.effect)
        self.assertFalse(dm._record(label).get("protected"))
        self.assertTrue(panel.grabs and not any(panel.grabs), "grabbed with the effect paused")
        self.assertTrue(panel.effect.enabled, "and the effect on again")

    def test_the_ground_is_grabbed_again_only_when_the_label_changes(self):
        label = self.title_label(u"SEARCH HISTORY")
        panel = label.parentWidget()
        panel.ground = 0x292929
        self.on()
        self.assertTrue(dm._record(label).get("protected"))
        grabs = len(panel.grabs)
        self.assertTrue(dm._light_text_label(label))
        self.assertEqual(len(panel.grabs), grabs, "a sweep's second look reads the cache")
        label.geometry = FakeGeometry(140, 20)
        dm._light_text_label(label)
        self.assertEqual(len(panel.grabs), grabs + 1, "resized: looked at again")

    def test_a_hidden_label_is_decided_when_shown(self):
        label = self.title_label(u"BOOKMARKS")
        label.visible = False
        self.on()
        record = dm._record(label, create=False) or {}
        self.assertFalse(record.get("protected"), "not protected unseen: it may come to lie on a light badge")

    def test_rich_text_dark_text_or_a_light_parent_are_not(self):
        rich = self.title_label(u'<span style="color:#ff0000">2</span> selected')
        dark = self.title_label(u"Name", ink="#202020")
        on_light = self.title_label(u"Name", parent_window="#f0f0f0")
        colored = self.title_label(u"Name", sheet=u"QLabel{color: #ffffff;}")
        self.on()
        for label in (rich, dark, on_light, colored):
            record = dm._record(label, create=False) or {}
            self.assertFalse(record.get("protected"), label.text)


class PlainInputTests(DarkModeCase):
    def test_a_plain_combo_box_gets_no_effect(self):
        # FreeLab's own dialogs: Qt's combo boxes and spin boxes with no stylesheet anywhere. Their
        # dark outlines set off the ink detection, whose effect garbled their text and hid their arrows.
        dialog = FakeWidget("QDialog", parent=None, window=True)
        combo = FakeWidget("QComboBox", parent=dialog, inherits=("QComboBox",), light="ink")
        styled = FakeWidget("QComboBox", parent=self.content, inherits=("QComboBox",), light="ink")
        self.app.roots.append(dialog)
        self.on()
        self.assertIsNone(combo.effect)
        self.assertIsNotNone(styled.effect, "under FontLab's stylesheets the ink detection stays")


class ProtectionTests(DarkModeCase):
    def test_a_replaced_effect_still_draws_color_controls_unmapped(self):
        # a dock's keyed effect is replaced when its frame colors are read again; the Color panel's
        # wheel, which has no effect of its own, was then mapped (its white corner turned dark)
        self.on()
        self.assertIn(self.swatch, list(self.dock.effect.freelab_protect.values()))
        record = dm._record(self.dock)
        dm._set_effect(self.dock, record, "keyed", [0xcacbcc])
        self.assertIn(self.swatch, list(self.dock.effect.freelab_protect.values()), "protected by the new effect too")


class ListIconTests(DarkModeCase):
    """Restoring a list's icons goes through the items it has then: FontLab deletes and rebuilds
    items, and a deleted item is no Qt object Python can tell is gone (writing through one crashed
    FontLab when switching off after Export Profiles was closed)."""

    def test_icons_are_put_back_through_the_current_items(self):
        class Item(object):
            def __init__(self, icon):
                self._icon, self.dead = icon, False

            def icon(self):
                return self._icon

            def setIcon(self, icon):
                assert not self.dead, "written through a deleted item"
                self._icon = icon

        class ListWidget(FakeWidget):
            pass

        lst = ListWidget("QListWidget", parent=self.main, inherits=("QListWidget",))
        page = FakeIcon("page")
        lst.rows = [Item(page)]
        self.patch("_list_items", lambda widget: list(widget.rows))
        self.patch("icon_is_swatch", lambda icon: False)
        self.patch("icon_is_gray", lambda icon: True)
        self.patch("dark_icon", lambda icon: FakeIcon("mapped " + icon.label))
        dm._state()  # the session state, with its caches
        dm._swap_item_icons(lst)
        self.assertEqual(lst.rows[0].icon().label, "mapped page")
        old = lst.rows[0]
        old.dead = True  # FontLab rebuilt the list: the old item is gone, a new one shows the mapped icon
        lst.rows = [Item(old.icon())]
        dm._restore_item_icons(lst, dm._record(lst))
        self.assertEqual(lst.rows[0].icon().label, "page")


class EngineTests(DarkModeCase):
    def save(self, **values):
        settings = dm.load_settings()
        settings.update(values)
        dm.save_settings(settings)

    def test_engine_setting(self):
        self.assertEqual(dm.engine_setting({}), "script")
        self.assertEqual(dm.engine_setting({"engine": "native"}), "native")
        self.assertEqual(dm.engine_setting({"engine": "warp"}), "script")

    def test_native_without_its_library_falls_back_to_the_script_engine(self):
        self.save(engine="native")
        self.on()
        status = dm.status()
        self.assertEqual((status["engine"], status["hooked"]), ("script", False))
        self.assertTrue(any("native engine" in e for e in status["errors"]))
        self.assertEqual(self.kind(self.search), "island", "the script engine's effects are in place")
        self.assertNotIn("native_pending", self.settings(), "nothing left to guard")

    def test_a_crash_while_starting_turns_the_native_engine_off(self):
        self.save(engine="native", native_pending=True)
        dm._state().pop("native_pending_mine", None)  # the mark is an earlier session's
        self.patch("_hooks", lambda: self.fail("the hooks must not go in again"))
        self.on()
        self.assertEqual(dm.status()["engine"], "script")
        self.assertEqual(self.settings().get("engine"), "script")
        self.assertNotIn("native_pending", self.settings())

    def test_native_engine_maps_no_pixels_of_what_fontlab_paints(self):
        hooks = FakeHooks()
        self.patch("_hooks", lambda: hooks)
        self.patch("_palette_table", lambda palette: (dm.ctypes_array(1) if hasattr(dm, "ctypes_array") else __import__("ctypes").c_uint32(0)))
        self.save(engine="native")
        popup = FakeWidget("YPopupHost", parent=self.canvas)  # FontLab's labels over the glyph canvas
        del qtfakes.QTimer.single_shots[:]
        self.on()
        status = dm.status()
        self.assertEqual((status["engine"], status["hooked"]), ("native", True), status["errors"])
        self.assertEqual(hooks.calls[:2], ["set_palette", "install"])
        self.assertIsNone(self.kind(self.search), "an island FontLab paints: hooked, no effect")
        self.assertTrue(self.search.property(dm.HOOKED_PROP))
        self.assertIn(self.search, list(self.dock.effect.freelab_protect.values()),
                      "dark as it is painted: the dock's effect must not map it again")
        self.assertTrue(self.canvas.property(dm.HOOKED_PROP))
        self.assertTrue(popup.property(dm.HOOKED_PROP), "FontLab's own painting inside a hooked island: hooked too")
        self.assertIsNone(self.edit.property(dm.HOOKED_PROP), "a line edit (Qt draws it) inside one: processed as any")
        self.assertEqual(self.kind(self.panel), "title", "the script engine's other effects stay")
        self.assertNotEqual(self.search.styleSheet, u"QWidget{background:white;}", "Qt draws stylesheets: darkened as ever")
        self.assertTrue(self.settings().get("native_pending"), "guarded until it has run a while")
        settle = [cb for ms, cb in qtfakes.QTimer.single_shots if ms == dm.NATIVE_SETTLE_MS]
        self.assertEqual(len(settle), 1)
        settle[0]()
        self.assertNotIn("native_pending", self.settings())
        self.off()
        self.assertIn("remove", hooks.calls)
        self.assertFalse(dm.status()["hooked"])

    def test_applying_again_while_on_keeps_the_hooks(self):
        # the re-applies after a switch (0, 1.5, and 5 s) came while the start was still settling,
        # took their own mark for a crash, and ran the script engine over the hooks
        hooks = FakeHooks()
        self.patch("_hooks", lambda: hooks)
        self.patch("_palette_table", lambda palette: __import__("ctypes").c_uint32(0))
        self.save(engine="native", enabled=True)
        self.on()
        dm.apply_dark()
        dm.run_queue()
        dm._reapply_if_on()
        dm.run_queue()
        status = dm.status()
        self.assertEqual((status["engine"], status["hooked"], status["errors"]), ("native", True, []))
        self.assertEqual(hooks.calls.count("install"), 1)
        self.assertIsNone(self.kind(self.search), "no script effects over the hooks")

    def test_switching_engines_rebuilds(self):
        hooks = FakeHooks()
        self.patch("_hooks", lambda: hooks)
        self.patch("_palette_table", lambda palette: __import__("ctypes").c_uint32(0))
        self.on()
        self.assertEqual(self.kind(self.search), "island")
        dm.configure(dark=True, engine="native")
        dm.run_queue()
        self.assertEqual((dm.status()["engine"], dm.status()["hooked"]), ("native", True), dm.status()["errors"])
        self.assertIsNone(self.kind(self.search))
        dm.configure(dark=True, engine="script")
        dm.run_queue()
        self.assertEqual(self.kind(self.search), "island")
        self.assertIn("remove", hooks.calls)


class KindTests(DarkModeCase):
    def test_kinds(self):
        self.assertEqual(dm.widget_kind(self.search), "island")
        self.assertIsNone(dm.widget_kind(FakeWidget("QtColorPicker", "colorMark")), "color pickers are left as they are")
        viewport = FakeWidget("QWidget", "qt_scrollarea_viewport", parent=FakeWidget("QsciScintilla", "XmlCode"))
        self.assertEqual(dm.widget_kind(viewport), "edges")
        badges = FakeWidget("QWidget", "qt_scrollarea_viewport", parent=FakeWidget("YSelectableTree", "listClasses"))
        self.assertIsNone(dm.widget_kind(badges), "the Classes badges stay as FontLab draws them")
        text_bar = FakeWidget("QWidget", "widgetString", parent=FakeWidget("GlyphWindow", "GlyphWindow"))
        self.assertIsNone(dm.widget_kind(text_bar), "only the glyph window's QWidget#widget is its canvas")
        self.assertEqual(dm.widget_kind(FakeWidget("YContinueWidget", "widgetContinue")), "island")
        self.assertEqual(dm.widget_kind(FakeWidget("YTabWidget", parent=FakeWidget("QSplitter"))), "fill")
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
        bar = FakeWidget("QFrame", "frameBottom", parent=FakeWidget("FontWindow", "FontWindow"))
        self.assertEqual(dm.widget_kind(bar), "defringe", "dark already: kept out of the window's mapping")
        self.assertIsNone(dm.widget_kind(FakeWidget("QFrame", "frameBottom", parent=FakeWidget("GlyphWindow"))))

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

    def test_fill_title_ink_and_icons(self):
        self.on()
        self.assertTrue(self.tabs.autoFillBackground)
        self.assertEqual(self.kind(self.panel), "title")
        self.assertEqual(self.kind(self.odd), "ink", "found as \"selective\" by FreeLab 0.2: now ink")
        self.assertEqual(self.odd.effect.freelab_kind, "ink")
        self.assertIsInstance(self.button.icon, Mapped)
        self.assertIsInstance(self.action.icon, Mapped)

    def test_color_swatch_icons_keep_their_color(self):
        mark = FakeWidget("QToolButton", "markRed", parent=self.content, icon=FakeIcon("swatch"),
                          inherits=("QAbstractButton",))
        self.on()
        self.assertEqual(mark.icon.label, "swatch")
        self.assertIsInstance(self.button.icon, Mapped)

    def test_pictures_are_left_alone(self):
        class Pixmap(object):
            def __init__(self, side):
                self.side = side
                self.key = FakeIcon().key

            def isNull(self):
                return False

            def cacheKey(self):
                return self.key

            def width(self):
                return self.side

            def height(self):
                return self.side

        icon = FakeWidget("QLabel", parent=self.content, inherits=("QLabel",))
        art = FakeWidget("QLabel", parent=self.content, inherits=("QLabel",))
        icon.pixmap, art.pixmap = Pixmap(16), Pixmap(400)
        self.on()
        self.assertIsInstance(icon.pixmap, Mapped)
        self.assertEqual(art.pixmap.side, 400, "artwork such as the About picture stays")

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

    def test_menus_are_darkened_as_they_open(self):
        dm.apply_dark()  # the queue is not run: a menu opened now must not wait for it
        self.assertEqual(len(self.menu.connections["aboutToShow()"]), 1)
        self.assertIsNone(self.menu.property(dm.SEEN_PROP))
        self.menu.emit("aboutToShow()")
        self.assertTrue(self.menu.property(dm.SEEN_PROP))
        self.assertIn(u"QMenu::separator", self.menu.styleSheet, "lighter separators")
        self.off()
        self.assertEqual(self.menu.styleSheet, u"", "taken off with dark mode")
        self.on()
        self.assertEqual(len(self.menu.connections["aboutToShow()"]), 1, "hooked once, across switches")
        self.assertEqual(dm._state()["errors"], [])

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
    def test_title_bars_are_set_once_per_window(self):
        alive = set([101, 102])
        calls = []
        self.patch("_process_windows", lambda: sorted(alive))
        self.patch("_set_title_bar", lambda hwnd, dark: calls.append((hwnd, dark)))
        self.patch("_is_window", lambda hwnd: hwnd in alive)
        old_platform = sys.platform
        sys.platform = "win32"
        try:
            dm.dark_title_bars(True)
            dm.dark_title_bars(True)  # every sweep: nothing again (each call makes Windows redo the frame)
            alive.discard(102)
            alive.add(103)
            dm.dark_title_bars(True)  # a new window, and a closed one forgotten
            dm.dark_title_bars(False)
        finally:
            sys.platform = old_platform
        self.assertEqual(calls, [(101, True), (102, True), (103, True), (101, False), (103, False)])


class EffectOwnershipTests(DarkModeCase):
    """FontLab crashed in PythonQt.dll (2026-11-06) when an effect FreeLab still had installed lost its Python reference."""

    def rewrap_all(self):
        for widget in self.app.allWidgets():
            widget.rewrap = True

    def test_own_effects_are_recognized_through_a_new_wrapper(self):
        self.rewrap_all()
        self.on()
        for _ in range(3):  # full sweeps revisit islands
            dm._state()["sweeps"] = dm.FULL_SWEEP_EVERY - 1
            dm._sweep()
            dm.run_queue()
        for widget in self.app.allWidgets():
            record = dm._record(widget, create=False)
            if widget.effect is not None:
                self.assertIsNotNone(record and record.get("effect"), "an installed effect keeps its Python reference: %s" % widget._cls)
                self.assertIs(record["effect"], widget.effect)

    def test_off_removes_own_effects_through_qt(self):
        self.rewrap_all()
        self.on()
        self.off()
        for widget in self.app.allWidgets():
            self.assertIsNone(widget.effect, widget._cls)


class RecheckTests(DarkModeCase):
    def test_a_widget_is_looked_at_again_when_its_size_changes(self):
        calls = []

        def detect(widget):
            calls.append((widget.objectName, widget.width))
            return None

        self.patch("detect_light", detect)
        brush = FakeWidget("QWidget", "brush", parent=self.content, width=10, height=10)
        self.on()
        brush.width, brush.height = 200, 200  # laid out after it was first seen
        dm._sweep()
        dm.run_queue()
        self.assertEqual([c for c in calls if c[0] == "brush"], [("brush", 10), ("brush", 200)])
        dm._sweep()
        dm.run_queue()
        self.assertEqual(len([c for c in calls if c[0] == "brush"]), 2, "same size: not again")

    def test_fonts_are_left_as_they_are(self):
        # Grayscale smoothing made GDI drop smoothing altogether at FontLab's small UI sizes.
        before = self.app.font()
        self.on()
        self.assertEqual(self.app.font(), before)
        self.off()
        self.assertEqual(self.app.font(), before)

    def test_every_loaded_version_stays_referenced(self):
        self.on()
        first = sys.modules["freelab_dark_mode"]
        stand_in = type(sys)("freelab_dark_mode")  # what a reload puts in sys.modules
        sys.modules["freelab_dark_mode"] = stand_in
        try:
            dm.apply_dark()
            self.assertTrue(any(m is first for m in dm._state()["modules"]))
            self.assertTrue(any(m is stand_in for m in dm._state()["modules"]))
        finally:
            sys.modules["freelab_dark_mode"] = first

    def test_the_module_stays_referenced(self):
        self.on()
        self.assertIs(dm._state()["module"], sys.modules["freelab_dark_mode"])
        saved = sys.modules.pop("freelab_dark_mode")
        try:
            self.assertIs(dm._module(), saved, "found through the state when FontLab drops it from sys.modules")
        finally:
            sys.modules["freelab_dark_mode"] = saved


class RestyleTests(DarkModeCase):
    def test_sweep_catches_a_restyle_and_then_watches(self):
        self.on()
        self.content.setStyleSheet(u"QWidget{background:white;}")  # FontLab, while a glyph is edited
        dm._sweep()
        dm.run_queue()
        self.assertEqual(self.content.styleSheet, dm.recolor_sheet(u"QWidget{background:white;}"))
        self.assertTrue(self.content.filters, "watched from now on")
        self.content.setStyleSheet(u"QWidget{background:#f0f0f0;}")  # the next restyle: darkened at once
        self.assertEqual(self.content.styleSheet, dm.recolor_sheet(u"QWidget{background:#f0f0f0;}"))

    def test_a_first_stylesheet_counts_as_a_restyle(self):
        self.on()
        self.assertFalse(self.button.styleSheet)
        self.button.setStyleSheet(u"QToolButton{background:#5fcf00;}")  # "Set": FontLab turns it green
        dm._sweep()
        dm.run_queue()
        self.assertEqual(self.button.styleSheet, dm.recolor_sheet(u"QToolButton{background:#5fcf00;}"))

    def test_sweeps_leave_island_contents_and_swatches_alone(self):
        self.on()
        dm._sweep()
        self.assertEqual(dm._state()["queue"], [], "their own stylesheets are noted, not taken for restyles")

    def test_watching_stops_when_dark_mode_is_off(self):
        self.on()
        self.content.setStyleSheet(u"QWidget{background:white;}")
        dm.process(self.content)
        self.off()
        self.assertEqual(self.content.filters, [])
        self.content.setStyleSheet(u"QWidget{background:white;}")
        self.assertEqual(self.content.styleSheet, u"QWidget{background:white;}")


class QueueTests(DarkModeCase):
    def test_a_widget_is_queued_once(self):
        dm.apply_dark()
        before = len(dm._state()["queue"])
        dm._enqueue(self.app.allWidgets(), "dark")
        self.assertEqual(len(dm._state()["queue"]), before)

    def test_sweeps_do_not_requeue_handled_widgets(self):
        self.on()
        for _ in range(3):
            dm._sweep()
        self.assertEqual(dm._state()["queue"], [], "island contents, swatches, and islands are checked too")

    def test_saved_workspace_is_not_overwritten(self):
        dm.save_settings({"saved_workspace": u"#ffacacac"})
        qtfakes.Preferences.color_workspace = QColor("#ffffffff")  # FontLab reset after a crash with dark mode on
        self.on()
        self.assertEqual(self.settings()["saved_workspace"], u"#ffacacac")
        self.off()
        self.assertEqual(qtfakes.Preferences.color_workspace, QColor("#ffacacac"))

    def test_switching_off_finishes_at_once(self):
        self.on()
        dm.restore()
        self.assertEqual(dm._state()["queue"], [])
        self.assertEqual(self.content.styleSheet, PANEL_SHEET)

    def test_reentered_work_does_nothing(self):
        dm.apply_dark()
        state = dm._state()
        state["busy"] = True
        size = len(state["queue"])
        dm._work()
        self.assertEqual(len(state["queue"]), size)
        state["busy"] = False

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
