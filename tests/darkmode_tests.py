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

    def test_a_cursors_light_glow_is_made_a_dark_one(self):
        """The owner, November 25: a light shadow beside the arrow over the dark canvas. FontLab's cursors carry
        a white glow for a light canvas."""
        class Color(object):
            def __init__(self, r, g, b, a=255):
                self.rgba = (r, g, b, a)

            @staticmethod
            def fromRgba(value):
                return Color((value >> 16) & 255, (value >> 8) & 255, value & 255, (value >> 24) & 255)

            def alpha(self):
                return self.rgba[3]

            def red(self):
                return self.rgba[0]

            def green(self):
                return self.rgba[1]

            def blue(self):
                return self.rgba[2]

        class Picture(object):
            def __init__(self, pixels):
                self.pixels = pixels

            def width(self):
                return len(self.pixels)

            def height(self):
                return 1

            def pixel(self, x, y):
                return self.pixels[x]

            def setPixelColor(self, x, y, color):
                r, g, b, a = color.rgba
                self.pixels[x] = (a << 24) | (r << 16) | (g << 8) | b

        self.patch("_gui", lambda name: Color if name == "QColor" else None)
        clear, white, black, glow, edge = 0x00000000, 0xffffffff, 0xff000000, 0x60ffffff, 0x80101010
        picture = Picture([clear, white, black, glow, edge])
        self.assertTrue(dm.glow_to_shadow(picture))
        self.assertEqual(picture.pixels, [clear, white, black, 0x60000000, edge],
                         "the glow black at the opacity it had; the arrow, its outline, and the outline's own smoothing as drawn")
        self.assertFalse(dm.glow_to_shadow(Picture([clear, white, black, edge])), "no glow: nothing to make")

    def test_a_canvas_pictures_are_found_where_fontlab_draws_them(self):
        """The owner, November 25: a picture in a glyph came out as its negative. Its place comes from FontLab:
        the element's transform, the glyph's place in its line, the canvas' transform."""
        import sys as system
        import types

        class Rect(object):
            def __init__(self, x, y, w, h):
                self.box = (x, y, w, h)

            def toAlignedRect(self):
                return self.box

        class Scale(object):
            def __init__(self, k, dx=0.0, dy=0.0):
                self.k, self.dx, self.dy = k, dx, dy

            def mapRect(self, rect):
                x, y, w, h = rect.box
                return Rect(x * self.k + self.dx, y * self.k + self.dy, w * self.k, h * self.k)

        class Image(object):
            def __init__(self, w, h):
                self.w, self.h = w, h

            def isNull(self):
                return not self.w

            def width(self):
                return self.w

            def height(self):
                return self.h

        class Shape(object):
            def __init__(self, image, transform):
                self.image, self.transform = image, transform

        class Layer(object):
            def __init__(self, shapes):
                self.shapes = shapes

        class Glyph(object):
            def __init__(self, layer):
                self.activeLayer = layer

        class Info(object):
            def __init__(self, glyph):
                self.glyph = glyph

        class Block(object):
            def __init__(self, infos):
                self.infos = infos

            def getAllGlyphs(self):
                return self.infos

            def getGlyphTransform(self, index):
                return Scale(1.0, dx=1000.0 * index)

        class Canvas(object):
            transform = Scale(0.5)

            def textBlocks(self):
                return [Block([Info(Glyph(Layer([Shape(Image(0, 0), Scale(1.0))]))),
                               Info(Glyph(Layer([Shape(Image(300, 200), Scale(2.0))])))])]

        class Workspace(object):
            def getCanvasForViewport(self, widget):
                return Canvas() if widget == "canvas" else None

        fake = types.ModuleType("fontlab")
        fake.flWorkspace = types.SimpleNamespace(instance=lambda: Workspace()) if hasattr(types, "SimpleNamespace") else None
        if fake.flWorkspace is None:
            class Holder(object):
                @staticmethod
                def instance():
                    return Workspace()
            fake.flWorkspace = Holder
        saved = system.modules.get("fontlab")
        system.modules["fontlab"] = fake

        def restore():
            if saved is None:
                system.modules.pop("fontlab", None)
            else:
                system.modules["fontlab"] = saved
        self.addCleanup(restore)
        self.patch("_core", lambda name: (lambda x, y, w, h: Rect(x, y, w, h)) if name == "QRectF" else None)
        self.assertEqual(dm._find_picture_rects("canvas"), [(500.0, 0.0, 300.0, 200.0)],
                         "the second glyph's picture: 300 by 200, doubled, its glyph 1,000 units on, the canvas halved")
        self.assertEqual(dm._find_picture_rects("elsewhere"), [], "no canvas: none")

    def test_a_pickers_bare_declarations_are_wrapped(self):
        """The owner, November 24: Overlay Fonts' opacity dropdown stayed white. Its stylesheet is "color:
        lightGray;", declarations with no selector: with the frame's rule after them Qt read neither, drew a plain
        button from the dark palette, and the picker's effect turned that light."""
        picker = FakeWidget("QtColorPicker", "buttonColor", parent=self.content, sheet=u"color: lightGray;")
        self.on()
        self.assertEqual(picker.styleSheet, u"QtColorPicker{color: lightGray;}" + dm.PICKER_FRAME)
        self.off()
        self.assertEqual(picker.styleSheet, u"color: lightGray;")

    def test_a_fields_ground_decides_whether_it_is_mapped(self):
        """The owner, November 24: Actions' "Glyph" and "Baseline", a unit beside a field, and text typed in the
        Glyph window's fields came out heavy or fringed; a white square stood in the corner of the metrics table."""
        class Color(object):
            def __init__(self, value):
                self.value = value

            @staticmethod
            def fromRgba(value):
                return Color(value)

            def alpha(self):
                return (self.value >> 24) & 255

            def red(self):
                return (self.value >> 16) & 255

            def green(self):
                return (self.value >> 8) & 255

            def blue(self):
                return self.value & 255

        class Picture(object):
            def __init__(self, corners, width=40, height=14):
                self.corners, self.w, self.h = corners, width, height

            def toImage(self):
                return self

            def width(self):
                return self.w

            def height(self):
                return self.h

            def pixel(self, x, y):
                return self.corners[(x > self.w // 2) + 2 * (y > self.h // 2)]

        class Rect(object):
            def left(self):
                return 2

            def right(self):
                return 30

            def top(self):
                return 1

            def bottom(self):
                return 12

        self.patch("_gui", lambda name: Color if name == "QColor" else None)
        dark, light, bare = 0xff1f1f1f, 0xffecf1f6, 0x00000000
        self.assertTrue(dm.dark_ground(Picture([dark, dark, dark, dark])))
        self.assertTrue(dm.dark_ground(Picture([dark, 0xffdbdbdb, dark, dark])), "a letter's end in one corner")
        self.assertFalse(dm.dark_ground(Picture([bare, bare, bare, bare])), "drawn on nothing: judged with what is under it")
        self.assertFalse(dm.dark_ground(Picture([light, light, light, light])), "a light field is mapped as ever")
        self.assertFalse(dm.dark_ground(Picture([dark] * 4, width=3)), "too small to tell")
        self.assertTrue(dm.light_ground(Picture([light, light, light, light]), Rect()))
        self.assertTrue(dm.light_ground(Picture([light, dark, light, light]), Rect()))
        self.assertFalse(dm.light_ground(Picture([dark, dark, light, light]), Rect()))
        self.assertFalse(dm.light_ground(Picture([bare, bare, bare, bare]), Rect()))

    def test_a_lists_wide_picture_is_no_logo(self):
        """The owner, November 24: Overlay Fonts' sample text. A line of text drawn as a list's picture is mapped
        with its row; drawn from its icon in a logo's square, it came out dark."""
        class Size(object):
            def __init__(self, w, h):
                self.w, self.h = w, h

            def width(self):
                return self.w

            def height(self):
                return self.h

        class Icon(FakeIcon):
            def __init__(self, sizes):
                FakeIcon.__init__(self)
                self.sizes = sizes

            def availableSizes(self):
                return self.sizes

        state = {"mapped_keys": set(), "icon_cache": {}, "originals": {}}
        self.assertFalse(dm._logo_icon(Icon([Size(120, 24)]), state))
        self.patch("icon_is_swatch", lambda icon: True)
        self.assertTrue(dm._logo_icon(Icon([Size(32, 32)]), state), "a square picture goes on to the logo rules")

    def test_a_menu_holds_the_pictures_under_it_but_not_its_own(self):
        """The owner, November 24: menus slow to answer over a Font window. FontLab repaints its windows as the mouse
        moves over a menu's entries."""
        import sys as system
        saved = getattr(system, "_freelab_paint_hold", None)
        system._freelab_paint_hold = None
        self.addCleanup(setattr, system, "_freelab_paint_hold", saved)

        class Menu(object):
            def isAncestorOf(self, widget):
                return widget is inside

            def inherits(self, name):
                return name == "QMenu"

        class Under(object):
            def window(self):
                return self

            def inherits(self, name):
                return False

        menu, inside, under = Menu(), Under(), Under()
        app = dm._qt()[0]
        had = getattr(app, "activePopupWidget", None)
        app.activePopupWidget = staticmethod(lambda: menu)

        def restore():
            if had is None:
                del app.activePopupWidget
            else:
                app.activePopupWidget = had
        self.addCleanup(restore)
        hold = dm._paint_hold()
        self.assertEqual(hold, (dm.POPUP_HOLD, id(menu)))
        self.assertFalse(dm._held_in_popup(hold, under), "a window under the menu: held")
        self.assertTrue(dm._held_in_popup(hold, inside), "the menu's own: painted as ever")
        self.assertTrue(dm._held_in_popup(hold, menu))
        self.assertFalse(dm._held_in_popup("a drag", inside), "a drag holds everything large")
        app.activePopupWidget = staticmethod(lambda: None)
        self.assertIsNone(dm._paint_hold())

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


class _Control(object):
    """A settings dialog control: whatever it is asked to do, it does nothing, but checks and signals."""

    def __init__(self, *args):
        self.checked, self.slots = False, {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *args: None

    def setChecked(self, value):
        self.checked = bool(value)

    def isChecked(self):
        return self.checked

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)


class _SettingsDialog(_Control):
    made = []
    run = [lambda dialog: 0]  # what exec_ does (a test sets it)

    def __init__(self, parent=None):
        _Control.__init__(self)
        self.parent_, self.deleted, self.props = parent, 0, {}
        _SettingsDialog.made.append(self)

    def setProperty(self, name, value):
        self.props[name] = value

    def windowFlags(self):
        return 0

    def exec_(self):
        return _SettingsDialog.run[0](self)

    def deleteLater(self):
        self.deleted += 1


class _FakeDarkMode(object):
    def __init__(self, fail=False):
        self.configured, self.fail = [], fail

    def load_settings(self):
        return {"enabled": True}

    def content_setting(self, settings):
        return bool(settings.get("content", True))

    def windows_is_dark(self):
        return True

    def configure(self, **values):
        if self.fail:
            raise RuntimeError("configure failed")
        self.configured.append(values)
        return dict(values, enabled=True)


class SettingsDialogLifetimeTests(unittest.TestCase):
    """The settings dialog has FontLab's main window as its parent, its watch timer stops when it closes,
    and Qt deletes it once (deleteLater from a plain timer): never left running and held by dark mode's
    sweep, never deleted by PythonQt at a random moment. Reviewed 2026-11-15."""

    def setUp(self):
        qtfakes.install()
        os.environ["FREELAB_NO_AUTOSTART"] = "1"
        try:
            import freelab_dark_mode_settings as settings
        finally:
            del os.environ["FREELAB_NO_AUTOSTART"]
        self.settings = settings
        original = settings.dark_mode_module
        self.addCleanup(lambda: setattr(settings, "dark_mode_module", original))
        gui = sys.modules["PythonQt.QtGui"]
        self.main = FakeWidget("QMainWindow", name="MainWindow")
        self.tops = [self.main]
        gui.QApplication = type("App", (), {"topLevelWidgets": staticmethod(lambda: list(self.tops))})
        for name in ("QVBoxLayout", "QHBoxLayout", "QRadioButton", "QCheckBox", "QPushButton", "QLabel", "QButtonGroup"):
            setattr(gui, name, _Control)
        gui.QDialog = _SettingsDialog
        sys.modules["PythonQt.QtCore"].Qt.WindowFlags = staticmethod(int)
        sys.modules["PythonQt.QtCore"].Qt.WindowContextHelpButtonHint = 0x00010000
        _SettingsDialog.made = []
        del qtfakes.QTimer.single_shots[:]
        if hasattr(sys, "_freelab_dark_mode_settings_held"):
            del sys._freelab_dark_mode_settings_held
        self.addCleanup(qtfakes.uninstall)
        self.addCleanup(lambda: delattr(sys, "_freelab_dark_mode_settings_held")
                        if hasattr(sys, "_freelab_dark_mode_settings_held") else None)
        self.addCleanup(lambda: _SettingsDialog.run.__setitem__(0, lambda dialog: 0))

    def show(self, dm, run):
        _SettingsDialog.run[0] = run
        self.settings.dark_mode_module = lambda: dm
        return self.settings.show_dialog()

    def watch(self, dialog):
        return [t for t in qtfakes.timers() if t.parent() is dialog][0]

    def freed_once(self, dialog):
        self.assertIn(dialog, self.settings.held_dialogs(), "held until Qt deletes it")
        for _ms, callback in list(qtfakes.QTimer.single_shots):
            callback()
        self.assertEqual(dialog.deleted, 1)
        self.assertNotIn(dialog, self.settings.held_dialogs())

    def test_cancel_stops_the_watch_and_frees_the_dialog(self):
        seen = {}

        def run(dialog):
            seen["running"] = self.watch(dialog).running
            return 0
        self.assertIsNone(self.show(_FakeDarkMode(), run))
        dialog = _SettingsDialog.made[-1]
        self.assertIs(dialog.parent_, self.main)
        self.assertTrue(seen["running"])
        watch = self.watch(dialog)
        self.assertFalse(watch.running)
        self.assertIsNone(watch.callback, "disconnected")
        self.freed_once(dialog)

    def test_the_dialog_says_it_is_freelabs_own(self):
        # FreeLab MCP's window tools take a modal dialog for a question of FontLab's (risky mode) unless it says so
        self.show(_FakeDarkMode(), lambda dialog: 0)
        dialog = _SettingsDialog.made[-1]
        self.assertIs(dialog.props.get("mcpScriptWindow"), True)
        self.freed_once(dialog)

    def test_each_option_has_a_tooltip(self):
        """As Tab Docking Settings' options have (the review of 2026-11-24); Automatic named as dark mode's message
        names it."""
        tips = {}

        class Option(_Control):
            def __init__(self, label=u"", *args):
                _Control.__init__(self)
                self.label = label

            def setToolTip(self, text):
                tips[self.label] = text
        gui = sys.modules["PythonQt.QtGui"]
        gui.QRadioButton = gui.QCheckBox = Option
        self.show(_FakeDarkMode(), lambda dialog: 0)
        s = self.settings
        self.assertEqual(dict(s.THEMES)["automatic"], u"Automatic (follows Windows)")
        self.assertEqual(tips[u"Automatic (follows Windows)"], s.AUTOMATIC_TIP)
        self.assertEqual(tips[s.MIXED], s.MIXED_TIP)
        for _key, label in s.SHADES:
            self.assertEqual(tips[label], s.SHADE_TIP)
        for text in (s.AUTOMATIC_TIP, s.MIXED_TIP, s.SHADE_TIP):
            self.assertTrue(text.endswith(u"."), text)
        # Grayed only where system_light grays them: Mixed and the shades, not Automatic
        self.assertIn(u"Grayed", s.MIXED_TIP)
        self.assertIn(u"Grayed", s.SHADE_TIP)
        self.assertNotIn(u"Grayed", s.AUTOMATIC_TIP)

    def test_ok_frees_it_too(self):
        result = self.show(_FakeDarkMode(), lambda dialog: 1)
        self.assertTrue(result["dark"])
        dialog = _SettingsDialog.made[-1]
        self.assertFalse(self.watch(dialog).running)
        self.freed_once(dialog)

    def test_a_failing_configure_still_stops_and_frees(self):
        with self.assertRaises(RuntimeError):
            self.show(_FakeDarkMode(fail=True), lambda dialog: 1)
        dialog = _SettingsDialog.made[-1]
        self.assertFalse(self.watch(dialog).running)
        self.freed_once(dialog)

    def test_repeated_visits_leave_nothing_running(self):
        for _visit in range(3):
            self.show(_FakeDarkMode(), lambda dialog: 0)
            for _ms, callback in list(qtfakes.QTimer.single_shots):
                callback()
            del qtfakes.QTimer.single_shots[:]
        self.assertEqual(self.settings.held_dialogs(), [])
        self.assertEqual([t for t in qtfakes.timers() if t.running], [])
        self.assertEqual([d.deleted for d in _SettingsDialog.made], [1, 1, 1])

    def test_without_fontlab_main_window_it_is_kept_not_deleted(self):
        self.tops[:] = []
        self.show(_FakeDarkMode(), lambda dialog: 0)
        dialog = _SettingsDialog.made[-1]
        self.assertIsNone(dialog.parent_)
        self.assertFalse(self.watch(dialog).running)
        self.assertEqual(qtfakes.QTimer.single_shots, [])
        self.assertIn(dialog, self.settings.held_dialogs(), "parentless: PythonQt's to delete, so held")
        self.assertEqual(dialog.deleted, 0)


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


class SelectedAsPaintedTests(unittest.TestCase):
    """A selected row is drawn again as FontLab painted it only when that is light text on a dark row."""

    def test_which_selected_rows_are_drawn_as_painted(self):
        self.assertTrue(dm.selected_as_painted(5000, 300, 0), "Export Profiles: light text on the dark highlight")
        self.assertFalse(dm.selected_as_painted(5000, 0, 400), "dark ink on it: mapped")
        self.assertFalse(dm.selected_as_painted(5000, 4500, 0),
                         "Preview Features' row under the pointer, near-white: mapped, or it stays a white band")
        self.assertFalse(dm.selected_as_painted(0, 0, 0), "nothing drawn")


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
    # Inside the ink effect, a label's image is mapped once, by the effect (a label mapped first, then
    # mapped again by the effect, went wrong). The font window's mark flag is the exception: the effect
    # left its black pole black, so dark mode maps its image and has the effect draw it as it is.
    def test_a_label_inside_the_ink_effect_keeps_its_image(self):
        self.odd.light = "ink"
        label = FakeWidget("QLabel", "labelIcon", parent=self.odd, inherits=("QLabel",))
        original = label.pixmap = LabelPixmap()
        self.on()
        self.assertIsNotNone(self.odd.effect)
        self.assertIs(label.pixmap, original)

    def test_a_label_mapped_before_the_ink_effect_gets_its_image_back(self):
        box = FakeWidget("QWidget", "box", parent=self.content)
        label = FakeWidget("QLabel", "labelIcon", parent=box, inherits=("QLabel",))
        original = label.pixmap = LabelPixmap()
        self.on()
        self.assertIsInstance(label.pixmap, Mapped)
        dm._set_effect(box, dm._record(box), "ink")
        self.assertIs(label.pixmap, original)
        self.assertNotIn("pixmap", dm._record(label), "nothing left to restore when switching off")

    def test_the_mark_flag_is_mapped_and_drawn_as_mapped(self):
        self.odd.light = "ink"
        flag = FakeWidget("QLabel", "labelMark", parent=self.odd, inherits=("QLabel",))
        flag.pixmap = LabelPixmap()
        self.on()
        self.assertIsInstance(flag.pixmap, Mapped, "its pole made light")
        self.assertTrue(dm._record(flag).get("protected"), "the ink effect draws it unmapped")
        dm._set_effect(self.odd, dm._record(self.odd), "ink")
        self.assertIsInstance(flag.pixmap, Mapped, "not handed back to the effect")

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
        flag = FakeWidget("QLabel", "labelIcon", parent=box, inherits=("QLabel",))
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

    def test_a_combo_box_that_lost_its_stylesheet_is_plain_again(self):
        # FreeLab draws a dropdown with one choice as a label, through a stylesheet, and takes the
        # stylesheet away when a second choice comes (Glyph Compose's Script dropdown). Dark mode kept the
        # sheet it had seen, took the dropdown for a styled one ever after, and its ink effect garbled it.
        dialog = FakeWidget("QDialog", parent=None, window=True)
        combo = FakeWidget("QComboBox", parent=dialog, inherits=("QComboBox",), light="ink",
                           sheet=u"QComboBox { border: none; background: transparent; }")
        self.app.roots.append(dialog)
        self.on()
        self.assertIsNotNone(combo.effect, "styled: looked at as any widget")
        combo.setStyleSheet(u"")
        dm._sweep()
        dm.run_queue()
        self.assertIsNone(combo.effect)
        self.assertIsNone(combo.property(dm.SHEET_PROP))
        self.assertIsNone(combo.property(dm.ISLAND_PROP))
        self.assertTrue(dm._plain_input(combo))

    def test_a_widget_that_asks_later_to_be_left_alone_loses_its_effect(self):
        dialog = FakeWidget("QDialog", parent=None, window=True)
        combo = FakeWidget("QComboBox", parent=dialog, inherits=("QComboBox",), light="ink",
                           sheet=u"QComboBox { color: red; }")
        self.app.roots.append(dialog)
        self.on()
        self.assertIsNotNone(combo.effect)
        combo.setProperty(dm.LEAVE_ALONE_PROP, True)
        dm.process(combo)
        self.assertIsNone(combo.effect)


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


class RetiredEngineTests(DarkModeCase):
    """The native engine is gone: a saved choice of it, its start guard, its library left in the bin
    folder, and its hooks put in by an earlier version this session all end in the script engine."""

    def save(self, **values):
        """darkmode.json as an older version wrote it (load_settings drops the retired keys)."""
        with open(os.path.join(self.tmp, "darkmode.json"), "w") as handle:
            json.dump(values, handle)

    def test_a_saved_native_engine_runs_the_script_engine_and_loads_no_hooks(self):
        self.save(engine="native", native_pending=True, enabled=True)
        folder = os.path.join(self.tmp, "bin")
        os.makedirs(folder)
        with open(os.path.join(folder, "freelab_hooks-v20-115.dll"), "wb") as handle:
            handle.write(b"")  # left by an older install
        import ctypes
        loaded, saved = [], (ctypes.CDLL, ctypes.PyDLL, ctypes.WinDLL)

        def recorder(original):
            def load(name, *args, **kwargs):
                loaded.append(name)
                return original(name, *args, **kwargs)
            return load
        ctypes.CDLL, ctypes.PyDLL, ctypes.WinDLL = [recorder(original) for original in saved]
        try:
            self.on()
            dm.configure(dark=True, shade="medium")  # a save: what is read is what is written back
            dm.run_queue()
        finally:
            ctypes.CDLL, ctypes.PyDLL, ctypes.WinDLL = saved
        self.assertEqual([name for name in loaded if "hooks" in str(name)], [], "the hooks library is never loaded")
        self.assertEqual(dm.status()["errors"], [])
        self.assertEqual(self.kind(self.search), "island", "the script engine's island")
        self.assertNotIn("engine", dm.load_settings(), "read as nothing")
        written = self.settings()
        self.assertNotIn("engine", written)
        self.assertNotIn("native_pending", written)
        self.assertEqual(written.get("shade"), "medium")

    def test_hooks_an_earlier_version_put_in_this_session_are_taken_out(self):
        class Library(object):  # the earlier version's library, loaded in FontLab already
            removed = 0

            def freelab_hooks_remove(self):
                Library.removed += 1
                return 24
        self.on()
        state = dm._state()
        state["hooked"], state["hooked_lib"], state["engine"] = True, Library(), "native"
        self.search.setProperty("freelabHooked", True)
        dm.apply_dark()  # this version run from the Scripts menu (or the next switch)
        dm.run_queue()
        self.assertEqual(Library.removed, 1)
        self.assertNotIn("hooked", state)
        self.assertNotIn("hooked_lib", state)
        self.assertNotIn("engine", state)
        self.assertTrue(dm.status()["on"])
        self.assertEqual(self.kind(self.search), "island", "rebuilt by the script engine")
        self.off()
        self.assertEqual(Library.removed, 1, "taken out once")
        self.assertIsNone(self.search.property("freelabHooked"), "its mark removed with dark mode's own")

    def test_an_old_library_that_fails_is_noted_not_raised(self):
        class Broken(object):
            def freelab_hooks_remove(self):
                raise OSError("gone")
        self.on()
        state = dm._state()
        state["hooked"], state["hooked_lib"] = True, Broken()
        self.off()
        self.assertNotIn("hooked", state)
        self.assertTrue(any("old native engine" in e for e in dm.status()["errors"]), dm.status()["errors"])

    def test_the_settings_dialog_offers_no_engine(self):
        import freelab_dark_mode_settings as settings
        self.assertFalse(hasattr(settings, "ENGINES"))
        self.assertFalse(hasattr(dm, "engine_setting") or hasattr(dm, "hooks_path") or hasattr(dm, "native"))



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
        # (Open Installed Fonts' list: its names were garbled as ink, the survey of 2026-11-24)
        self.assertEqual(dm.widget_kind(FakeWidget("QListWidget", "listFonts", inherits=("QListWidget",))), "island")
        # (Add Glyphs' list: an island whose text color is set in its stylesheet, tried live 2026-11-24)
        self.assertEqual(dm.widget_kind(FakeWidget("YSelectableTree", "itemsList", inherits=("YSelectableTree",))), "island")
        self.assertIn(u"color:#000000", dm.ISLAND_TEXT[("YSelectableTree", "itemsList")])
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

    def test_an_icon_held_at_twice_its_size_is_still_an_icon(self):
        """FontLab's warning dialogs hold their 64-pixel question mark as 128 pixels for sharp screens:
        counted in its own pixels it passed for artwork, and kept its light edge on the dark dialog."""
        class Pixmap(object):
            def __init__(self, side, ratio=None):
                self.side, self.ratio = side, ratio
                self.key = FakeIcon().key

            def isNull(self):
                return False

            def cacheKey(self):
                return self.key

            def width(self):
                return self.side

            def height(self):
                return self.side

            def devicePixelRatio(self):
                if self.ratio is None:
                    raise AttributeError("an older Qt")
                return self.ratio

        sharp = FakeWidget("QLabel", parent=self.content, inherits=("QLabel",))
        small = FakeWidget("QLabel", parent=self.content, inherits=("QLabel",))
        plain = FakeWidget("QLabel", parent=self.content, inherits=("QLabel",))
        sharp.pixmap, small.pixmap, plain.pixmap = Pixmap(60, 2.0), Pixmap(20), Pixmap(128, 1.0)
        self.on()
        self.assertIsInstance(sharp.pixmap, Mapped, "30 pixels as drawn: an icon")
        self.assertIsInstance(small.pixmap, Mapped, "no ratio known: its own pixels")
        self.assertEqual(plain.pixmap.side, 128, "128 pixels as drawn: a picture, left alone")
        self.assertEqual(dm._pixel_ratio(Pixmap(128, 2.0)), 2.0)

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

    def test_fontlabs_drop_highlight_is_never_rendered_to_be_looked_at(self):
        """The owner, November 24: every drag of a window over the main window stalled for two seconds as the
        blue highlight came up. It grows step by step, and at each size it was rendered and its pixels counted."""
        self.on()
        looked = []
        self.patch("detect_light", lambda widget: looked.append(widget))
        self.patch("detect_ink", lambda widget: looked.append(widget))
        highlight = FakeWidget("YDropHighlight", parent=self.content)
        plain = FakeWidget("QWidget", parent=self.content)
        for widget in (highlight, plain):
            dm.process(widget)
        self.assertEqual(looked, [plain, plain], "the plain one is looked at (light, then ink); the highlight never")
        self.assertIsNone(highlight.graphicsEffect())

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


class ToolWindowTests(DarkModeCase):
    """FreeLab's tool windows: told once dark mode has switched (their shared module follows), and
    forgotten once closed for good (the records held their widgets, which kept them from being freed)."""

    def setUp(self):
        DarkModeCase.setUp(self)
        self.told = []
        case = self

        def hook(dark):
            # what the tools see when told: the palette and the style already set, the queue not yet worked
            case.told.append((dark, dm._app_is_dark(case.app, QPalette), case.app.style().objectName,
                              bool(dm._state()["queue"])))
        self.old_hook = getattr(sys, dm.TOOLS_HOOK, None)
        setattr(sys, dm.TOOLS_HOOK, hook)

    def tearDown(self):
        setattr(sys, dm.TOOLS_HOOK, self.old_hook)
        DarkModeCase.tearDown(self)

    def test_the_tools_are_told_after_each_switch_either_way(self):
        dm.apply_dark()
        self.assertEqual(self.told, [(True, True, "Fusion", False)],
                         "after the palette and the style, before any widget is looked at")
        dm.run_queue()
        dm.apply_dark()  # (a reapply while on: nothing switched)
        self.assertEqual(len(self.told), 1)
        dm.restore()
        self.assertEqual(self.told[-1], (False, False, "windowsvista", False), "once every widget is undone")
        self.on()
        self.off()
        self.assertEqual([entry[0] for entry in self.told], [True, False, True, False], "every time, both ways")

    def test_a_tool_failing_never_stops_the_switch(self):
        def broken(dark):
            raise RuntimeError("a tool's bug")
        setattr(sys, dm.TOOLS_HOOK, broken)
        self.on()
        self.assertEqual(self.app.style().objectName, "Fusion")
        self.assertTrue(any("a tool's bug" in u"%s" % error for error in dm._state()["errors"]))

    def test_a_closed_tool_window_is_forgotten(self):
        W = FakeWidget
        tool = W("QDialog", "tool", window=True, width=600, height=400)
        part = W("QWidget", parent=tool, sheet=u"QWidget{background:white;}")
        label = W("QLabel", parent=part, inherits=("QLabel",))
        label.ink = "ink"
        self.app.roots.append(tool)
        self.on()
        self.assertEqual(self.kind(label), "ink")
        self.assertNotEqual(part.styleSheet, u"QWidget{background:white;}")
        def of_tool(record):
            return record["obj"].isWidgetType() and tool.isAncestorOf(record["obj"])
        kept = len([r for r in dm._state()["records"].values() if not of_tool(r)])
        dm._enqueue([label], "dark")  # (one waiting in the queue too)
        self.assertTrue(dm.forget(tool))
        self.assertEqual(part.styleSheet, u"QWidget{background:white;}", "undone as when switched off")
        self.assertIsNone(label.effect, "its effect removed through Qt before its record goes")
        self.assertFalse([r for r in dm._state()["records"].values() if of_tool(r)])
        self.assertEqual(len(dm._state()["records"]), kept, "FontLab's own widgets keep theirs")
        self.assertFalse([item for item in dm._state()["queue"] if item[1] is label])
        self.assertFalse(dm.forget(tool), "nothing left to forget")

    def test_the_tools_are_told_which_palettes_are_dark_modes(self):
        # (their windows polished again after a switch keep an island's palette, and read again one their
        # own stylesheets set)
        self.board.light = None
        self.on()
        island = [w for w in self.app.allWidgets() if dm._record(w, create=False) and "palette" in dm._record(w, create=False)]
        self.assertTrue(island, "the canvas is an island")
        self.assertTrue(dm.owns_palette(island[0]))
        self.assertFalse(dm.owns_palette(self.label))
        self.off()
        self.assertFalse(dm.owns_palette(island[0]), "undone: the palette is no longer dark mode's")


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

    def test_switching_by_hand_says_automatic_is_off(self):
        """Named as the settings dialog names it, Automatic (follows Windows) (the review of 2026-11-24)."""
        dm.save_settings({"enabled": False, "follow_windows": True})
        written = []
        out = type("Out", (), {"write": lambda self, text: written.append(u"%s" % text), "flush": lambda self: None})()
        saved, sys.stdout = sys.stdout, out
        try:
            dm.toggle()
        finally:
            sys.stdout = saved
        self.assertIn(u"It no longer follows Windows: Automatic, in Scripts > FreeLab > Dark Mode Settings, turns that "
                      u"back on.", u"".join(written))
        self.assertFalse(self.settings()["follow_windows"])

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
        self.assertEqual(qtfakes.timers(), [])

    def test_startup_on_applies_and_schedules(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        intervals = [t.interval for t in qtfakes.timers() if t.single]
        self.assertEqual(intervals, list(dm.REAPPLY_DELAYS_MS))
        # FontLab puts its own style and palette back after the startup script: a reapply wins them back.
        self.app.setStyle(qtfakes.FakeStyle("windowsvista"))
        self.app.setPalette(QPalette())
        [t for t in qtfakes.timers() if t.single][1].fire()
        self.assertEqual(self.app.style().objectName, "Fusion")

    def test_worker_runs_in_slices_and_stops(self):
        dm.apply_dark()
        worker = dm._state()["worker"]
        self.assertTrue(worker is not None and worker.running and worker.interval == 0)
        while dm._state()["queue"]:
            worker.fire()
        worker.fire()
        self.assertIsNone(dm._state()["worker"])

    def test_the_worker_never_lets_go_of_itself_while_it_emits(self):
        # The worker stops itself once the queue drains, inside its own timeout: that must never drop the
        # last reference to a parentless timer (PythonQt would delete it while it emits). Reviewed 2026-11-15.
        dm.apply_dark()
        while dm._state()["queue"]:
            qtfakes.fire_unheld(lambda: dm._state()["worker"])
        self.assertIsNone(dm._state()["worker"])
        self.assertEqual(qtfakes.QTimer.deleted_while_emitting, [])
        made = len(qtfakes.timers())
        dm._enqueue([self.content], "dark")  # queued again: the same timer starts again, none is made
        self.assertTrue(dm._state()["worker"].running)
        self.assertEqual(len(qtfakes.timers()), made)
        while dm._state()["queue"]:
            qtfakes.fire_unheld(lambda: dm._state()["worker"])

    def test_every_timer_has_a_parent_and_stays_held(self):
        # A parentless timer made from Python is PythonQt's to delete whenever its last reference goes;
        # dark mode's timers have FontLab's application as their parent, and are kept for reuse.
        dark = [True]
        self.patch("windows_is_dark", lambda: dark[0])
        dm.save_settings({"enabled": True})
        dm.startup()
        dm.configure(follow_windows=True)
        dm.run_queue()
        dm.toggle()
        dm.run_queue()
        dm.toggle()
        dm.startup()
        dm.run_queue()
        dm.configure(follow_windows=False)
        made = qtfakes.timers()
        self.assertTrue(made)
        self.assertEqual([t for t in made if t.parent() is None], [])
        self.assertEqual(qtfakes.QTimer.deleted_while_emitting, [])

    def test_reapply_timers_are_reused(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        before = list(dm._state()["timers"])
        dm.schedule_reapply()
        dm.schedule_reapply()
        self.assertEqual([id(t) for t in dm._state()["timers"]], [id(t) for t in before])
        self.assertEqual(sorted(t.interval for t in dm._state()["timers"]), sorted(dm.REAPPLY_DELAYS_MS))
        self.assertTrue(all(t.running for t in dm._state()["timers"]))

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

    def test_a_full_sweep_prunes_dead_records_and_wrappers(self):
        self.on()
        state = dm._state()
        count = len(state["records"])
        self.search.deleted = True
        dm._sweep()
        self.assertEqual(len(state["records"]), count, "not each sweep: at a full one")
        self.assertIn(id(self.search), state["known"])
        state["sweeps"] = dm.FULL_SWEEP_EVERY - 1
        dm._sweep()
        self.assertEqual(len(state["records"]), count - 1)
        self.assertNotIn(id(self.search), state["known"], "a deleted widget's wrapper let go")

    def test_sweeps_hold_the_wrappers_and_find_new_widgets_by_them(self):
        # PythonQt made a wrapper for each widget each sweep listed that Python did not hold, and freed it as
        # the list went: about 2,000 a sweep, live. Held, the same come back, and a new widget is one not held
        self.on()
        state = dm._state()
        dm._sweep()
        self.assertEqual(sorted(state["known"]), sorted(id(w) for w in self.app.allWidgets()), "every widget held")
        reads = []
        for widget in self.app.allWidgets():
            original = widget.property
            widget.property = (lambda original: lambda name: reads.append(name) or original(name))(original)
        late = FakeWidget("QWidget", parent=self.content, sheet=u"QWidget{background:white;}")
        dm._sweep()
        self.assertNotIn(dm.SEEN_PROP, reads, "widgets held are not asked whether they were seen")
        dm.run_queue()
        self.assertEqual(late.styleSheet, dm.recolor_sheet(u"QWidget{background:white;}"), "a new widget: themed")
        self.off()
        self.assertEqual(state["known"], {}, "switched off: let go")

    def test_switching_off_keeps_the_wrappers_of_live_parentless_widgets(self):
        # Let go of, the last reference to a widget made from Python with no parent (another script's
        # dialog its maker dropped) makes PythonQt delete it there and then, inside the loop: never in bulk
        loose = FakeWidget("QDialog", "someone's dialog", window=True)
        gone = FakeWidget("QDialog", "deleted", window=True)
        self.app.roots.extend([loose, gone])
        self.on()
        dm._sweep()
        state = dm._state()
        self.assertTrue(all(id(w) in state["known"] for w in (loose, gone, self.label)))
        gone.deleted = True
        self.off()
        kept = state["parentless"]
        self.assertTrue(any(w is loose for w in kept), "alive and parentless: held for the session")
        self.assertFalse(any(w is gone for w in kept), "deleted: let go")
        self.assertFalse(any(w is self.label for w in kept), "with a parent (Qt's to delete): let go")
        self.on()
        dm._sweep()
        self.off()
        self.assertEqual(len([w for w in state["parentless"] if w is loose]), 1, "held once")

    def test_toggling_off_cancels_timers(self):
        dm.save_settings({"enabled": True})
        dm.startup()
        dm.toggle()
        dm.run_queue()  # the worker stops once switching off has restored every widget
        self.assertTrue(all(not t.running for t in qtfakes.timers()))


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

    def test_a_cell_chart_fills_the_room_its_cells_leave(self):
        """The owner, November 24: a white band beside the glyph window's few cells. The chart fills itself in
        FontLab's light window color, which its island effect maps dark; taken back with dark mode."""
        cells = FakeWidget("FontCellChart", "fontChartView", parent=self.odd, inherits=("FontCellChart",))
        QPalette = dm._gui("QPalette")
        self.on()
        self.assertIsNotNone(cells.effect)
        # (in its stylesheet, drawn by the style: the palette's color did not outlast a repolish, and a font
        # window merged back into the main window came out light under its cells, the owner, November 24)
        light = dm._state()["saved"]["palette"].color(QPalette.Window).name()
        self.assertIn(u"FontCellChart{background-color:%s;}" % light, cells.styleSheet)
        styled = dm._core("Qt").WA_StyledBackground
        self.assertTrue(cells.testAttribute(styled))
        self.assertIsNone(dm._chart_fill_rule(self.odd), "a cell chart only")
        self.off()
        self.assertFalse(cells.testAttribute(styled), "as FontLab had it")
        self.assertNotIn(u"background-color:%s" % light, cells.styleSheet or u"")

    def test_a_freelab_windows_caption_is_never_taken_for_ink(self):
        """The owner, November 24: Font Builder's Ink darker than: looked blurrier than Make: beside it. It had
        been given the ink effect, and text drawn through an effect loses ClearType."""
        class Label(object):
            width, height = 120, 20

            def __init__(self, kind, window_mark):
                self.kind, self.mark = kind, window_mark

            def inherits(self, name):
                return name == self.kind

            def window(self):
                mark = self.mark
                return type("W", (), {"property": lambda self, name: mark if name == dm.FREELAB_WINDOW_PROP else None})()

        self.assertTrue(dm._freelab_caption(Label("QLabel", 3)))
        self.assertFalse(dm._freelab_caption(Label("QLabel", None)), "FontLab's own labels are still looked at")
        self.assertFalse(dm._freelab_caption(Label("QTreeView", 3)), "labels only")
        self.assertFalse(dm._freelab_caption(object()), "nothing raised")
        label = Label("QLabel", 3)
        label.isWindow = lambda: False
        saved = (dm._shows_picture, dm.own_render)
        dm._shows_picture = lambda widget: False
        dm.own_render = lambda widget: self.fail("a FreeLab caption is not rendered to look for ink")
        try:
            self.assertIsNone(dm.detect_ink(label))
        finally:
            dm._shows_picture, dm.own_render = saved

    def test_large_widgets_pictures_are_held_for_the_length_of_a_drag(self):
        """The owner, November 24: dragging a window over the main window stalled for seconds as FontLab's blue
        highlight came up, and not with dark mode off. Each repaint under the highlight drew and mapped the
        widget anew (111 ms for a font window, read live); Qt keeps no picture of a widget for its effect."""
        import sys as system
        import time as clock
        saved = (getattr(system, "_freelab_paint_hold", None), getattr(system, "_freelab_held", None))
        system._freelab_held = None

        def restore():
            system._freelab_paint_hold, system._freelab_held = saved
        self.addCleanup(restore)

        class Effect(object):
            updates = 0

            def update(self):
                self.updates += 1

        system._freelab_paint_hold = None
        self.assertIsNone(dm._paint_hold(), "no drag")
        system._freelab_paint_hold = ("drag 1", clock.time() - 0.1)
        self.assertIsNone(dm._paint_hold(), "a drag whose time is past: tab docking stopped saying so")
        system._freelab_paint_hold = ("drag 1", clock.time() + 60)
        self.assertEqual(dm._paint_hold(), "drag 1")
        effect, painted = Effect(), []

        def paint():
            painted.append(1)
            return "picture %d" % len(painted)
        box = (0, 0, 1715, 1329)
        self.assertEqual(dm._held_picture(effect, "drag 1", box, paint), "picture 1")
        self.assertEqual(dm._held_picture(effect, "drag 1", box, paint), "picture 1", "held: not painted again")
        self.assertEqual(dm._held_picture(effect, "drag 1", (0, 0, 900, 1329), paint), "picture 2", "another size")
        self.assertEqual(dm._held_picture(effect, "drag 2", (0, 0, 900, 1329), paint), "picture 3", "another drag")
        self.assertEqual(dm._release_held(), 0, "a drag is on: held still")
        system._freelab_paint_hold = ("drag 2", clock.time() - 0.1)
        self.assertEqual((dm._release_held(), effect.updates, dm._held()), (1, 1, {}), "let go, and repainted")
        self.assertEqual(dm._release_held(), 0)

    def test_whats_this_help_has_no_dashed_edge(self):
        """The owner, November 23 (image 22): the help's right and bottom sides were dashed. Qt dots its shadow
        color over the frame there: the help's own palette has it in the frame's color."""
        self.on()
        QPalette = dm._gui("QPalette")
        own = self.app.class_palettes[dm.HELP_CLASS]
        self.assertEqual(own.color(QPalette.Shadow).name(), own.color(QPalette.ToolTipText).name())
        self.assertNotEqual(self.app.palette().color(QPalette.Shadow).name(), own.color(QPalette.Shadow).name(),
                            "the application's own shadow stays")
        self.off()
        self.assertEqual(self.app.class_palettes, {}, "gone with dark mode")

    def test_a_medium_shades_title_bars_take_the_windows_gray(self):
        """The owner, November 23 (image 28): Windows' dark title bar on a medium gray window."""
        state = dm._state()
        saved = (state.get("shade"), state.get("title_shade"), state.get("dark_windows"))

        def restore():
            state["shade"], state["title_shade"], state["dark_windows"] = saved
        self.addCleanup(restore)
        def bar(palette):  # (the shade's window gray at TITLE_BAR_PERCENT, as 0x00bbggrr)
            window = dict((entry[0], entry[1]) for entry in palette)["Window"]
            red, green, blue = [int(round(int(window[i:i + 2], 16) * dm.TITLE_BAR_PERCENT / 100.0)) for i in (1, 3, 5)]
            return red | (green << 8) | (blue << 16)
        medium_bar, dark_bar = bar(dm.PALETTE_MEDIUM), bar(dm.PALETTE_DARK)
        state["shade"] = "medium"
        self.assertEqual(dm.caption_color(), medium_bar, "0x00bbggrr, as Windows takes it")
        self.assertEqual(dm.caption_color(False), dm.DWMWA_COLOR_DEFAULT, "light again: Windows' own")
        state["shade"] = "dark"
        self.assertEqual(dm.caption_color(), dark_bar, "the dark shade: the same step from its windows (images 32, 33)")
        self.assertEqual(dark_bar, 0x292626)
        calls = []
        self.patch("_process_windows", lambda: [101])
        self.patch("_set_title_bar", lambda hwnd, dark: calls.append((hwnd, dm.caption_color(dark))))
        self.patch("_is_window", lambda hwnd: True)
        state["dark_windows"], state["title_shade"] = set(), None
        old_platform = sys.platform
        sys.platform = "win32"
        try:
            dm.dark_title_bars(True)
            dm.dark_title_bars(True)
            state["shade"] = "medium"
            dm.dark_title_bars(True)  # the shade changed: the window's title bar is set again
            dm.dark_title_bars(True)
        finally:
            sys.platform = old_platform
        self.assertEqual(calls, [(101, dark_bar), (101, medium_bar)])


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


class InterfaceTextTests(DarkModeCase):
    """Text Qt draws on the dark interface goes through the defringe effect (ClearType's colored edges, the
    owner's most frequent complaint, November 24 and 25)."""

    def freelab_window(self):
        window = FakeWidget("QDialog", "fontCheck", window=True, width=800, height=600, inherits=("QDialog",))
        window.setProperty(dm.FREELAB_WINDOW_PROP, 1)
        tree = FakeWidget("QListView", "languages", parent=window, width=600, height=400,
                          inherits=("QAbstractItemView",))
        viewport = FakeWidget("QWidget", "qt_scrollarea_viewport", parent=tree, width=600, height=400)
        self.app.roots = [self.main, window]
        return viewport

    def light_label(self, text, ink="#afafaf", parent=None):
        panel = FakeWidget("QWidget", "captions", parent=parent or self.main)
        panel.palette.setColor(QPalette.Window, QColor("#292929"))
        label = FakeWidget("QLabel", "caption", parent=panel, inherits=("QLabel",))
        label.text = text
        label.palette.setColor(QPalette.WindowText, QColor(ink))
        return label

    def test_a_light_label_is_defringed(self):
        label = self.light_label(u"Kerning")
        self.on()
        self.assertEqual(self.kind(label), "defringe")

    def test_a_dark_label_or_one_with_no_text_is_not(self):
        self.assertFalse(dm._ui_text_widget(self.light_label(u"Name", ink="#202020")))
        self.assertFalse(dm._ui_text_widget(self.light_label(u"  ")))

    def test_a_freelab_windows_rich_text_label_is_defringed(self):
        self.freelab_window()
        label = FakeWidget("QLabel", "summary", inherits=("QLabel",))
        label.text = u"<b>2,512</b> languages"
        self.patch("_freelab_caption", lambda widget: widget is label)
        self.assertTrue(dm._ui_text_widget(label))
        self.patch("_freelab_caption", lambda widget: False)
        self.assertFalse(dm._ui_text_widget(label), "rich text elsewhere is not")

    def test_text_under_a_mapping_effect_is_not(self):
        panel = FakeWidget("QWidget", "sidebar", parent=self.main)
        panel.setProperty(dm.ISLAND_PROP, "ink")
        label = self.light_label(u"Kerning", parent=panel)
        button = FakeWidget("QToolButton", "go", parent=panel, inherits=("QAbstractButton",))
        button.text = u"Go"
        self.assertFalse(dm._ui_text_widget(label))
        self.assertFalse(dm._ui_text_widget(button))

    def test_a_button_with_a_light_face_is_not(self):
        button = FakeWidget("QToolButton", "white", parent=self.main, width=10, height=10,
                            inherits=("QAbstractButton",))
        button.text = u"Go"
        self.patch("own_render", lambda widget: widget)
        self.patch("image_stats", lambda image: (100, 60, 0))
        self.assertFalse(dm._ui_text_widget(button))
        self.patch("image_stats", lambda image: (100, 5, 0))
        self.assertTrue(dm._ui_text_widget(button))

    def test_a_freelab_list_is_defringed(self):
        viewport = self.freelab_window()
        self.on()
        self.assertEqual(self.kind(viewport), "defringe")

    def test_a_freelab_list_keeps_it_when_looked_at_again(self):
        viewport = self.freelab_window()
        self.on()
        effect = viewport.effect
        for _ in range(3):  # (full sweeps: it lost it at one, got it back at the next)
            dm.process(viewport)
        self.assertEqual(self.kind(viewport), "defringe")
        self.assertIs(viewport.effect, effect)

    def test_a_freelab_tab_bar_left_alone_is_defringed(self):
        viewport = self.freelab_window()
        bar = FakeWidget("QTabBar", parent=viewport.parentWidget().parentWidget(), inherits=("QTabBar",))
        bar.setProperty(dm.LEAVE_ALONE_PROP, True)
        lone = FakeWidget("QTabBar", parent=self.main, inherits=("QTabBar",))
        lone.setProperty(dm.LEAVE_ALONE_PROP, True)
        self.on()
        self.assertEqual(self.kind(bar), "defringe")
        self.assertIsNone(lone.effect, "outside FreeLab's windows, left alone as asked")

    def test_a_freelab_dropdown_is_defringed(self):
        viewport = self.freelab_window()
        combo = FakeWidget("QComboBox", parent=viewport.parentWidget().parentWidget(), inherits=("QComboBox",))
        combo.setProperty(dm.LEAVE_ALONE_PROP, True)
        self.on()
        self.assertEqual(self.kind(combo), "defringe")
        dm.process(combo)
        self.assertEqual(self.kind(combo), "defringe", "kept when looked at again")

    def test_a_list_outside_freelab_windows_is_not(self):
        tree = FakeWidget("QTreeWidget", parent=self.main, inherits=("QAbstractItemView",))
        viewport = FakeWidget("QWidget", "qt_scrollarea_viewport", parent=tree)
        self.assertFalse(dm._freelab_view_text(viewport))

    def test_another_effect_is_left_in_place(self):
        viewport = self.freelab_window()
        theirs = object()
        viewport.effect = theirs
        self.assertFalse(dm._freelab_view_text(viewport))

    def test_switching_off_leaves_no_trace(self):
        self.freelab_window()
        self.light_label(u"Kerning")
        self.on()
        self.off()
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


class _Image(object):
    """A QImage's pixels (ARGB32), for keep_colors."""

    def __init__(self, width, height, pixels=None):
        self.w, self.h, self.pixels = width, height, dict(pixels or {})

    def width(self):
        return self.w

    def height(self):
        return self.h

    def pixel(self, x, y):
        return self.pixels.get((x, y), 0)

    def setPixel(self, x, y, value):
        self.pixels[(x, y)] = value

    def copy(self):
        return _Image(self.w, self.h, self.pixels)


class MenuTickFrameTests(unittest.TestCase):
    """The review of November 23, image 13: on a menu's highlighted row, dark pixels showed at the right, the
    bottom, and the corners of a ticked switch's box (Scripts > FreeLab > Dark Mode): Fusion's own outline,
    a pixel wider and taller than dark mode's rounded frame. In a menu the frame is drawn right over it."""

    class Rect(object):
        def __init__(self, x, y, w, h):
            self.box = (x, y, w, h)

        def adjusted(self, left, top, right, bottom):
            x, y, w, h = self.box
            return MenuTickFrameTests.Rect(x + left, y + top, w + right - left, h + bottom - top)

        def x(self):
            return self.box[0]

        def y(self):
            return self.box[1]

        def width(self):
            return self.box[2]

        def height(self):
            return self.box[3]

        def center(self):
            return (self.box[0] + self.box[2] // 2, self.box[1] + self.box[3] // 2)

    class Action(object):
        def __init__(self, checked):
            self.checked = checked

        def isChecked(self):
            return self.checked

    class Painter(object):
        Antialiasing = "antialiasing"

        def __init__(self):
            self.drawn, self.pens = [], []

        def drawLine(self, start, end):
            self.drawn.append(("line", start, end))

        def save(self):
            pass

        def restore(self):
            pass

        def setRenderHint(self, hint, on):
            pass

        def setBrush(self, brush):
            pass

        def setPen(self, pen):
            self.pens.append(pen)

        def drawRoundedRect(self, rect, rx, ry):
            self.drawn.append(("rounded", rect.box))

        def drawRect(self, rect):
            self.drawn.append(("square", rect.box))

        def drawEllipse(self, rect):
            self.drawn.append(("ellipse", rect.box))

    class Widget(object):
        def __init__(self, kind, action=None):
            self.kind, self.styleSheet, self.action, self.asked = kind, u"", action, []

        def inherits(self, name):
            return name == self.kind

        def parentWidget(self):
            return None

        def actionAt(self, point):
            self.asked.append(point)
            return self.action

        def logicalDpiX(self):
            return 96

    def framed(self, window=30):
        tests = self

        class Pen(object):
            def __init__(self, color):
                self.color, self.width = color, 1.0

            def setWidthF(self, width):
                self.width = width

        class ProxyStyle(object):
            def __init__(self, base=None):
                self.base = base

            def drawPrimitive(self, element, option, painter, widget=None):
                painter.drawn.append(("fusion", element))

        class Color(object):
            def __init__(self, *args):
                self.args = args

            def red(self):
                return window

            green = blue = red

            def name(self):
                return u"#%02x%02x%02x" % (window, window, window)

        gui = {"QProxyStyle": ProxyStyle,
               "QStyle": type("QStyle", (), {"PE_IndicatorCheckBox": 7, "PE_IndicatorRadioButton": 8, "PE_PanelMenu": 9,
                                             "PE_FrameMenu": 10}),
               "QPainter": tests.Painter, "QBrush": lambda: "no brush", "QPen": Pen,
               "QPalette": type("QPalette", (), {"Window": "window", "WindowText": "text"})}
        saved = (dm._gui, dm._core, dm._qt, dm._state)
        state = {"shade": "dark"}
        dm._gui = lambda name: gui[name]
        dm._core = lambda name: {"QRectF": lambda rect: rect, "QPointF": lambda x, y: (round(x, 2), round(y, 2))}[name]
        dm._qt = lambda: (None, None, Color)
        dm._state = lambda: state

        def restore():
            dm._gui, dm._core, dm._qt, dm._state = saved
        self.addCleanup(restore)
        option = type("Option", (), {"rect": tests.Rect(10, 20, 13, 13),
                                     "palette": type("P", (), {"color": lambda self, role: Color(role)})()})()
        return dm._framed_style("fusion"), option

    def test_a_ticked_menu_entry_shows_the_mark_alone_in_the_texts_color(self):
        """The owner, November 23: the tick FontLab's light look has (the mark alone), in the text's color."""
        style, option = self.framed()
        painter, menu = self.Painter(), self.Widget("QMenu", self.Action(True))
        style.drawPrimitive(7, option, painter, menu)
        lines = [entry for entry in painter.drawn if entry[0] == "line"]
        self.assertEqual(len(painter.drawn), 2, "no box: Fusion's is not drawn")
        self.assertEqual(len(lines), 2, "down to the corner, up to the end")
        self.assertEqual(lines[0][2], lines[1][1], "one stroke after the other")
        for _, start, end in lines:
            for x, y in (start, end):
                self.assertTrue(10 <= x <= 23 and 20 <= y <= 33, "inside the entry's box")
        self.assertEqual(menu.asked, [(16, 26)], "the entry under the box says whether it is ticked")
        self.assertEqual(painter.pens[-1].color.args, ("text",))
        self.assertEqual(painter.pens[-1].width, dm.MENU_TICK_WIDTH)

    def test_a_menu_entry_not_ticked_shows_nothing(self):
        style, option = self.framed()
        painter = self.Painter()
        style.drawPrimitive(7, option, painter, self.Widget("QMenu", self.Action(False)))
        self.assertEqual(painter.drawn, [])

    def test_a_light_menu_is_left_to_the_style(self):
        style, option = self.framed(window=240)
        painter = self.Painter()
        style.drawPrimitive(7, option, painter, self.Widget("QMenu", self.Action(True)))
        self.assertEqual(painter.drawn, [("fusion", 7)])
        painter = self.Painter()
        style.drawPrimitive(9, option, painter, self.Widget("QMenu"))
        self.assertEqual(painter.drawn, [("fusion", 9)], "no line beside the ticks either")

    def test_a_dark_menu_gets_the_line_beside_its_ticks(self):
        """The owner, November 23: FontLab's light look has a line beside a menu's ticks; Fusion draws none."""
        style, option = self.framed()
        option.rect = self.Rect(0, 0, 176, 375)
        painter = self.Painter()
        style.drawPrimitive(9, option, painter, self.Widget("QMenu"))
        self.assertEqual(painter.drawn, [("fusion", 9), ("line", (dm.MENU_GUTTER + 0.5, 1), (dm.MENU_GUTTER + 0.5, 373)),
                                         ("line", (dm.MENU_GUTTER + 1.5, 1), (dm.MENU_GUTTER + 1.5, 373)),
                                         ("square", (0.5, 0.5, 175.0, 374.0))],
                         "over the panel, before the entries are drawn: two pixels wide, from the frame to the frame")
        frame_color = (dm.lighter_name(u"#1e1e1e", dm.MENU_FRAME_LIGHTER),)
        self.assertEqual([pen.args for pen in painter.pens], [frame_color, frame_color],
                         "the owner, November 23 (images 23 and 24): the line and the frame share one color")
        self.assertLess(dm.MENU_FRAME_LIGHTER, dm.SEPARATOR_LIGHTER, "nearer the menu's own than the separators'")
        painter = self.Painter()
        style.drawPrimitive(10, option, painter, self.Widget("QMenu"))
        self.assertEqual(painter.drawn, [("fusion", 10), ("square", (0.5, 0.5, 175.0, 374.0))],
                         "the frame again once the entries are drawn, over Fusion's near-black one")
        self.assertEqual(painter.pens[-1].args, frame_color)
        painter = self.Painter()
        style.drawPrimitive(10, option, painter, self.Widget("QFrame"))
        self.assertEqual(painter.drawn, [("fusion", 10)], "a menu's frame only")
        painter = self.Painter()
        style.drawPrimitive(9, option, painter, self.Widget("QFrame"))
        self.assertEqual(painter.drawn, [("fusion", 9)], "a menu's panel only")

    def test_the_separators_start_where_the_menus_line_is_drawn_at_any_scale(self):
        """Codex, 2026-11-23: the line was drawn at the menu's scale (34 px in at 150 %) and the separators' start
        was a fixed 23 px: they ran into the ticks' column on a scaled display."""
        for dpi, offset in ((96, 23), (144, 34), (192, 46)):
            menu = self.Widget("QMenu")
            menu.logicalDpiX = lambda dpi=dpi: dpi
            self.assertEqual(dm._gutter_offset(menu), offset)
            style, option = self.framed()
            option.rect = self.Rect(0, 0, 176, 375)
            painter = self.Painter()
            style.drawPrimitive(9, option, painter, menu)
            self.assertEqual(painter.drawn[1][1][0], offset + 0.5, "the line")
            self.assertIn(u"margin: 4px 8px 4px %dpx;" % offset, dm.separator_sheet(u"#3a3a3a", dm._gutter_offset(menu)),
                          "the separators' start")
        self.assertEqual(dm._gutter_offset(object()), dm.MENU_GUTTER, "a menu that cannot say its scale: unscaled")
        self.assertIn(u"%dpx; }" % dm.MENU_GUTTER, dm.separator_sheet(u"#3a3a3a"))

    def test_a_menus_tick_that_cannot_be_read_is_framed_right_over_the_styles_outline(self):
        style, option = self.framed()
        painter = self.Painter()
        style.drawPrimitive(7, option, painter, self.Widget("QMenu"))
        self.assertEqual(painter.drawn, [("fusion", 7), ("square", (10.5, 20.5, 12, 12))],
                         "every side on the outline's own pixels, corners included")

    def test_a_check_box_anywhere_else_keeps_its_rounded_frame(self):
        style, option = self.framed()
        painter = self.Painter()
        style.drawPrimitive(7, option, painter, self.Widget("QCheckBox"))
        self.assertEqual(painter.drawn, [("fusion", 7), ("rounded", (10.5, 20.5, 11, 11))])
        painter = self.Painter()
        style.drawPrimitive(7, option, painter, None)  # (drawn with no widget: a list's own box)
        self.assertEqual(painter.drawn[-1], ("rounded", (10.5, 20.5, 11, 11)))
        painter = self.Painter()
        style.drawPrimitive(8, option, painter, self.Widget("QMenu"))
        self.assertEqual(painter.drawn[-1][0], "ellipse", "a radio button's ring is as it was")
        self.assertFalse(dm._in_menu(object()), "a widget that cannot say: no menu, nothing raised")


class KeepColorsTests(unittest.TestCase):
    BLUE, WHITE, PALE = 0xff1060c0, 0xffffffff, 0xff90b8e8

    def picture(self):
        """A blue square on transparency, a white dot inside it, and a pale pixel on its right edge."""
        pixels = dict(((x, y), self.BLUE) for x in range(1, 6) for y in range(1, 6))
        pixels[(3, 3)] = self.WHITE
        pixels[(6, 3)] = self.PALE
        return _Image(7, 7, pixels)

    def test_a_white_detail_inside_the_picture_stays(self):
        original = self.picture()
        result = dm.keep_colors(original, original.copy())
        self.assertEqual(result.pixel(3, 3), self.WHITE, "the white ? of a question icon")
        self.assertEqual(result.pixel(2, 2), self.BLUE)

    def test_smoothing_toward_white_on_the_outline_is_cleaned(self):
        original = self.picture()
        value = dm.keep_colors(original, original.copy()).pixel(6, 3)
        self.assertEqual(value & 0xffffff, self.BLUE & 0xffffff, "the edge takes the color beside it")
        self.assertTrue(0 < value >> 24 < 255, "as transparent as it was mixed with white")


class _Index(object):
    def __init__(self, row):
        self._row = row

    def isValid(self):
        return 0 <= self._row < 1000

    def row(self):
        return self._row

    def parent(self):
        return None


class _Rect(object):
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    def top(self):
        return self.y

    def bottom(self):
        return self.y + self.h - 1

    def height(self):
        return self.h

    def isEmpty(self):
        return self.w <= 0 or self.h <= 0

    def intersected(self, other):
        top, bottom = max(self.y, other.y), min(self.y + self.h, other.y + other.h)
        return _Rect(self.x, top, self.w, bottom - top)


class SelectedRowTests(DarkModeCase):
    """A list's selected rows are found among the rows on screen, never by copying the whole selection."""

    class Selection(object):
        def __init__(self, rows):
            self.rows = rows

        @property
        def hasSelection(self):  # a property under PythonQt, as FontLab has it
            return bool(self.rows)

        def rowIntersectsSelection(self, row, parent):
            return row in self.rows

        def selectedIndexes(self):
            raise AssertionError("the whole selection copied")

    class Model(object):
        def index(self, row, column, parent):
            return _Index(row)

    class View(object):
        def __init__(self, selected, scrolled):
            self.selection, self.model_, self.scrolled = SelectedRowTests.Selection(selected), SelectedRowTests.Model(), scrolled

        def selectionModel(self):
            return self.selection

        def model(self):
            return self.model_

        def inherits(self, name):
            return False

        def indexAt(self, point):
            return _Index(self.scrolled)

        def visualRect(self, index):
            return _Rect(0, (index.row() - self.scrolled) * 20, 300, 20)

    def setUp(self):
        DarkModeCase.setUp(self)
        core = dm._core
        self.patch("_core", lambda name: {"QRect": _Rect, "QPoint": lambda x, y: None}.get(name) or core(name))

    def test_the_selected_rows_on_screen(self):
        view = self.View(selected=set(range(1000)) - set([502]), scrolled=500)  # everything but one, scrolled down
        rows = dm._selected_rows(view, 300, 100)
        self.assertEqual([r.top() for r in rows], [0, 20, 60, 80], "rows 500, 501, 503, and 504")
        self.assertEqual(rows[-1].height(), 20)

    def test_nothing_selected(self):
        self.assertEqual(dm._selected_rows(self.View(selected=set(), scrolled=0), 300, 100), [])


class RestoreCacheTests(DarkModeCase):
    def test_switching_off_forgets_the_list_logos(self):
        self.on()
        state = dm._state()
        state["logo_keys"] = {1: "logo at the dark shade"}
        self.off()
        self.assertNotIn("logo_keys", state)


def _ancestors(widget):
    parent = widget.parentWidget()
    while parent is not None:
        yield parent
        parent = parent.parentWidget()


if __name__ == "__main__":
    unittest.main()
