# -*- coding: utf-8 -*-
"""Tests of Feature Code's Stylistic alternates tab (its pure parts). Valid Python 2.7 and Python 3."""
from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_alternates as fa  # noqa: E402
import re  # noqa: E402


def plain(text):
    """A rich-text line without its bold (each count bold with its noun: tested on its own)."""
    return re.sub(u"</?b>", u"", text) if text is not None else text


def words(*args, **kwargs):
    """fa.build_words, its line without its bold."""
    label, line = fa.build_words(*args, **kwargs)
    return label, plain(line)


def problem_words(*args, **kwargs):
    """fa.build_problem, without its bold."""
    return plain(fa.build_problem(*args, **kwargs))


class SuggestionTests(unittest.TestCase):
    def test_the_model_reads(self):
        model = fa.load_model()
        self.assertIsNotNone(model)
        rows, families, varied = model
        self.assertEqual(rows[0][0], u"a", "the most varied character in the corpus")
        self.assertGreater(families, varied)

    def test_suggestions_list_what_the_font_has_and_its_alternates(self):
        rows = [(u"a", 49), (u"g", 46), (u"Q", 35)]
        cmap = {ord(u"a"): u"a", ord(u"Q"): u"Q"}
        names = set([u"a", u"a.ss01", u"a.sc", u"Q", u"Q.cv01"])
        found = fa.suggestions(rows, cmap, names)
        self.assertEqual([(ch, alternates) for ch, _, _, alternates in found],
                         [(u"a", [u"a.ss01"]), (u"Q", [u"Q.cv01"])], "g is not in the font; a.sc is no stylistic alternate")

    def test_the_next_free_set(self):
        self.assertEqual(fa.free_set_name(u"a", set([u"a", u"a.ss01"])), u"a.ss02")

    def test_scopes(self):
        self.assertTrue(fa.in_scope(u"a", "lower"))
        self.assertFalse(fa.in_scope(u"A", "lower"))
        self.assertTrue(fa.in_scope(u"A", "both"))
        self.assertFalse(fa.in_scope(u"1", "both"))


class VariantTests(unittest.TestCase):
    def test_the_same_seed_makes_the_same_variants(self):
        self.assertEqual(fa.variant_params(u"a", 1, "subtle", 7), fa.variant_params(u"a", 1, "subtle", 7))
        self.assertNotEqual(fa.variant_params(u"a", 1, "subtle", 7), fa.variant_params(u"a", 2, "subtle", 7))

    def test_each_change_stays_within_the_strengths_reach(self):
        for key, _, rotation, scale, slant, rise in fa.STRENGTHS:
            for number in range(1, 5):
                r, sx, sy, k, up = fa.variant_params(u"g", number, key, 3)
                self.assertLessEqual(abs(r), rotation)
                self.assertLessEqual(abs(sx - 1), scale + 1e-9)
                self.assertLessEqual(abs(sy - 1), scale + 1e-9)
                self.assertLessEqual(abs(k), slant)
                self.assertLessEqual(abs(up), rise)

    def moved(self, params, half_width, half_height, cx=250.0, cy=50.0):
        """How far the corners of a glyph's box move under a variant's matrix, at most (font units)."""
        a, b, c, d, e, f = fa.variant_matrix(params, cx, cy, 1000.0)
        far = 0.0
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y = cx + dx * half_width, cy + dy * half_height
            far = max(far, ((a * x + c * y + e - x) ** 2 + (b * x + d * y + f - y) ** 2) ** 0.5)
        return far

    def test_a_small_mark_is_changed_in_proportion(self):
        """The same recipe serves a period and a letter: each change is made about the glyph's own ink, so
        it moves a 100-unit period a seventh as far as a 700-unit letter; the baseline shift, a share of
        the em, is the one change that does not shrink with the mark."""
        for key, _, rotation, scale, slant, rise in fa.STRENGTHS:
            most = (rotation, 1.0 + scale, 1.0 + scale, slant, 0.0)  # every change at its reach, no shift
            period, letter = self.moved(most, 50.0, 50.0), self.moved(most, 350.0, 350.0, cy=350.0)
            self.assertAlmostEqual(letter / period, 7.0, 6, "in proportion to the ink")
            self.assertLess(period, {"subtle": 3.5, "moderate": 7.0, "bold": 13.0}[key], key)
            self.assertAlmostEqual(self.moved((0.0, 1.0, 1.0, 0.0, rise), 50.0, 50.0), rise * 1000.0, 6)
        subtle = fa.STRENGTHS[0]
        self.assertAlmostEqual(self.moved((0.0, 1.0 + subtle[3], 1.0 + subtle[3], 0.0, 0.0), 50.0, 50.0), 2 ** 0.5, 6,
                               "a 100-unit period 2% larger: 1 unit a side")
        self.assertLess(self.moved((subtle[2], 1.0, 1.0, 0.0, 0.0), 50.0, 50.0), 1.0, "its rotation: under a unit")
        self.assertLess(self.moved((0.0, 1.0, 1.0, subtle[4], 0.0), 50.0, 50.0), 1.0, "its slant too")
        self.assertEqual(subtle[5] * 1000.0, 5.0, "and its baseline shift up to 5 units: what shows on a period")

    def test_the_matrix_keeps_the_center(self):
        a, b, c, d, e, f = fa.variant_matrix((1.2, 1.03, 0.98, 2.0, 0.0), 250.0, 300.0, 1000.0)
        self.assertAlmostEqual(a * 250 + c * 300 + e, 250.0, 6)
        self.assertAlmostEqual(b * 250 + d * 300 + f, 300.0, 6)
        a, b, c, d, e, f = fa.variant_matrix((0.0, 1.0, 1.0, 0.0, 0.01), 250.0, 300.0, 1000.0)
        self.assertEqual((round(a, 9), round(b, 9), round(c, 9), round(d, 9), round(e, 9), round(f, 9)),
                         (1.0, 0.0, 0.0, 1.0, 0.0, 10.0), "a baseline shift alone: raised by 1% of the em")


# ---------------------------------------------------------------------------
# The tab, run on fakes (features_tests' Qt fakes; a font whose layers keep the shapes they are given)
# ---------------------------------------------------------------------------

import features_tests as ft  # noqa: E402


class Box(ft.Anything):
    """A spin box, a combo box, a line edit, or a label: its value, index, or text kept."""

    def __init__(self, *args):
        self.value, self.currentIndex, self.text, self.slots, self.enabled, self.pixmap = 0, 0, u"", {}, True, None
        self.checked, self.labels = False, []
        self.placeholder, self.whats, self.tip = u"", u"", u""  # its gray words, its What's This, its tooltip

    def setPlaceholderText(self, text):
        self.placeholder = text

    def setWhatsThis(self, text):
        self.whats = text

    def setToolTip(self, text):
        self.tip = text

    def setValue(self, value):
        self.value = value

    def setChecked(self, on):
        self.checked = on

    def addItem(self, label):
        self.labels.append(label)

    def setCurrentIndex(self, index):
        self.currentIndex = index

    def setText(self, text):
        self.text = text

    def setVisible(self, on):
        self.visible = on

    def setEnabled(self, on):
        self.enabled = on

    def setPixmap(self, pixmap):
        self.pixmap = pixmap

    def clear(self):
        self.pixmap, self.labels = None, []

    def connect(self, signal, slot):
        self.slots.setdefault(signal, []).append(slot)


class Tree(ft.FakeTree):
    """The list: its column names and its pictures' size kept."""

    def setHeaderLabels(self, labels):
        self.headers = list(labels)

    def setIconSize(self, size):
        self.icon_size = size


class Size(object):
    def __init__(self, width, height):
        self.width, self.height = width, height


class Item(ft.FakeItem):
    """A row: its pictures kept, by column."""

    def setIcon(self, column, icon):
        self.__dict__.setdefault("icons", {})[column] = icon


class Timer(ft.Anything):
    """Qt's timer: a call on the next turn of the event loop, made at once here."""

    @staticmethod
    def singleShot(interval, slot):
        slot()


class Pixmap(ft.Anything):
    def __init__(self, *args):
        self.drawn = []


class Painter(ft.Anything):
    """Records the outlines each picture got."""

    def __init__(self, pixmap=None):
        self.pixmap = pixmap

    def fillPath(self, path, brush):
        self.pixmap.drawn.append(path)


class Layer(object):
    def __init__(self, advance=500, shapes=1):
        self.advanceWidth, self.shapes, self.isNull = advance, [ft.Anything() for _ in range(shapes)], False
        center = ft.Anything()
        center.x, center.y = (lambda: 250.0), (lambda: 350.0)
        self.boundingBox = ft.Anything()
        self.boundingBox.center = lambda: center

    def addShape(self, shape):
        self.shapes.append(shape)

    def removeAllShapes(self):
        self.shapes = []


class Glyph(object):
    def __init__(self, name, code=None, drawn=True):
        self.name, self.isNull, self.fgGlyph = name, False, ft.FakeFgGlyph(name, code)
        self.layers = {u"Regular": Layer()} if drawn else {}

    def getLayerByName(self, master, create=False):
        if master not in self.layers and create:
            self.layers[master] = Layer(0, 0)
        return self.layers.get(master)

    def update(self):
        pass


class Font(object):
    def __init__(self, glyphs):
        self.glyphs = [Glyph(name, code) for name, code in glyphs]
        self.by_name = dict((g.name, g) for g in self.glyphs)
        self.fgPackage = ft.Anything()
        self.fgPackage.glyphs = [g.fgGlyph for g in self.glyphs]
        self.fgPackage.id = 7
        self.isNull, self.upm, self.tfn, self.path = False, 1000, u"Fake", u"fake.vfc"
        self.master, self.masters = u"Regular", [u"Regular"]

    def findName(self, name):
        return self.by_name.get(name)

    def addGlyph(self, glyph):
        added = Glyph(glyph.name, None, drawn=False)
        self.glyphs.append(added)
        self.by_name[added.name] = added
        self.fgPackage.glyphs.append(added.fgGlyph)


class Owner(object):
    """What the tab asks of the Feature Code dialog."""

    def __init__(self, ak, package, often=u"les"):
        self.ak, self.package, self.often = ak, package, often
        self.fontlab = ft.Anything()
        self.fontlab.flGlyph, self.fontlab.flItems = ft.FakeNewGlyph, ft.FakeItems()
        self.dialog, self.log = ft.Anything(), ft.Anything()
        self.logged, self.shown, self.busy, self.was_busy, self.runs, self.page = [], [], False, [], 0, None
        self.stoppable = []  # (each set_busy's and progress's: a build is a write, never stopped)
        self.log.add = lambda text, level="info": self.logged.append((level, text))

    headings = []  # (the headings' words, as the tab asked for them)

    @staticmethod
    def heading(QtGui, text):
        Owner.headings.append(text)
        return Box()

    def build_masters(self, package):
        return list(package.masters)

    def glyph_print(self, package, name, masters):
        """What a glyph is in each master, as the dialog's glyph_print tells a glyph changed since."""
        glyph = package.findName(name)
        if glyph is None:
            return None
        return tuple((master, tuple(id(shape) for shape in glyph.layers[master].shapes),
                      glyph.layers[master].advanceWidth) for master in masters if master in glyph.layers)

    def current_font(self):
        return self.package

    def doubled(self, ch):
        return ch in self.often

    def kind(self, ch):
        return ft.fc.char_kind(ch)

    def picture(self, names):
        return ("picture",) + tuple(names)

    def set_busy(self, on, what=u"", stoppable=True):
        self.busy = on
        self.was_busy.append(on)
        self.stoppable.append(stoppable)

    def progress(self, what, done=None, total=None, force=False, stoppable=True):
        self.shown.append((what, done, total))
        self.stoppable.append(stoppable)

    def run(self):
        self.runs += 1
        if self.page is not None:
            self.page.fill()


LATIN = [(u"a", 0x61), (u"e", 0x65), (u"l", 0x6C), (u"s", 0x73), (u"u", 0x75), (u"x", 0x78), (u"A", 0x41),
         (u"ampersand", 0x26), (u"u.01", None), (u"u.02", None), (u"l.alt1", None), (u"a.sc", None),
         (u"nine", 0x39), (u"period", 0x2E), (u"plus", 0x2B), (u"space", 0x20)]
DESIGNS = [(u"W", 0x57), (u"W.ss01", None), (u"w", 0x77), (u"w.ss01", None), (u"w.2", None), (u"a", 0x61),
           (u"a.sc", None), (u"a.alt1", None), (u"space", 0x20)]


class Transform(ft.Anything):
    """A matrix whose mapped outline is the outline it was given (what a preview drew is told by it)."""

    def map(self, path):
        return path


def install_fake_qt():
    """PythonQt faked for the tab; what was there before, to put back."""
    saved = sys.modules.get("PythonQt")
    qt = ft.Anything()
    qt.QtCore = ft._FakeQtModule({"Qt": ft.FakeQt, "QSize": Size, "QTimer": Timer})
    qt.QtGui = ft._FakeQtModule({"QTreeWidget": Tree, "QTreeWidgetItem": Item, "QLineEdit": Box,
                                 "QPushButton": ft.FakeButton, "QSpinBox": Box, "QComboBox": Box, "QLabel": Box,
                                 "QCheckBox": Box, "QIcon": lambda picture: picture, "QTransform": Transform,
                                 "QPixmap": Pixmap, "QPainter": Painter})
    sys.modules["PythonQt"] = qt
    return saved


def make_page(ak, glyphs=LATIN, model=((u"a", 49), (u"u", 9), (u"l", 25), (u"&", 17), (u"+", 3), (u"9", 2), (u".", 1))):
    owner = Owner(ak, Font(glyphs))
    page = owner.page = fa.AlternatesPage(owner)
    page.model = (list(model), 412, 128)
    page.count_box.setValue(2)
    page.seed_box.setValue(1)
    page.fill()
    return page, owner


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
        os.environ["FREELAB_NO_AUTOSTART"] = "1"
        import freelab_auto_kerning as ak
        cls.ak, cls.layer_path = ak, ak.layer_path
        ak.layer_path = lambda layer: ("outline", id(layer))
        cls.saved = install_fake_qt()

    @classmethod
    def tearDownClass(cls):
        cls.ak.layer_path = cls.layer_path
        if cls.saved is None:
            sys.modules.pop("PythonQt", None)
        else:
            sys.modules["PythonQt"] = cls.saved

    def page(self, *args):
        return make_page(self.ak, *args)

    def row(self, page, glyph, key=fa.SUGGESTIONS_KEY):
        """A glyph's row in a group of the list (Suggestions, unless another is named)."""
        return [item for item in page.group_rows(key) if item.data(0, ft.USER_ROLE) == glyph][0]

    def listed(self, page, key=fa.SELECTED_KEY):
        """The glyphs a group lists, and those of them ticked."""
        rows = page.group_rows(key)
        return ([item.data(0, ft.USER_ROLE) for item in rows],
                [item.data(0, ft.USER_ROLE) for item in rows if item.checkState(0) == ft.CHECKED])

    def pick(self, page, key):
        """A scope picked in the Glyphs dropdown, as Qt tells the tab."""
        index = [scope for scope, _ in page.scope_rows].index(key)
        page.scope_box.setCurrentIndex(index)
        page.scope_box.slots["currentIndexChanged(int)"][0](index)

    def type(self, page, text):
        """Characters typed in the box, as Qt tells the tab."""
        page.letters_edit.setText(text)
        page.letters_edit.slots["textChanged(QString)"][0](text)

    def test_empty_notes_take_no_room_and_the_previews_hold_the_spare_height(self):
        """Owner's image 198: the empty line under the list's heading: hidden while it says nothing. Owner's
        image 287: with the previews hidden, the part's spare height went to the heading and the paragraph,
        blank bands above and below the paragraph. The previews stay, empty when there is nothing to draw
        (owner's image 296), their captions hidden; the part ends with them, over the splitter's handle."""
        page, owner = self.page()
        self.assertTrue(page.note.visible)
        self.assertEqual(page.build_glyphs(), [], "nothing ticked: nothing to build, nothing to preview")
        self.assertTrue(page.existing.visible and page.preview.visible, "the previews' room stays")
        self.assertIsNone(page.existing.pixmap)
        self.assertFalse(page.existing_caption.visible or page.preview_caption.visible)
        owner.package = None
        page.fill()
        page.update_buttons()
        self.assertEqual([label.visible for label in (page.note, page.scope_note, page.existing_caption,
                                                      page.preview_caption)], [False] * 4)
        self.assertTrue(page.existing.visible and page.preview.visible)
        self.assertEqual(page.tree.items, [], "no font: no group")

    def test_the_build_says_its_scope_before_the_click(self):
        """Build variants built every letter of the Letters scope (1,102 of them) while two rows were
        checked: the scope is the checked characters at first, and the button and the line under the
        settings count what a click builds."""
        page, owner = self.page()
        self.assertEqual(page.scope(), "checked")
        self.assertEqual(page.build_button.text, u"Build variants")
        self.assertFalse(page.build_button.enabled, "nothing checked: nothing to build")
        self.assertIn(u"No suggestion ticked in the list above can take turns", plain(page.scope_note.text))
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.row(page, u"l").setCheckState(0, ft.CHECKED)
        self.row(page, u"plus").setCheckState(0, ft.CHECKED)
        self.assertEqual(page.characters_in_scope()[0], [u"a", u"l"], "the checked letters; a plus sign takes no turns")
        self.assertEqual(self.listed(page), ([u"a", u"l"], [u"a", u"l"]), "listed in Selected glyphs, ticked")
        self.assertEqual(page.build_button.text, u"Build 3 variants")
        # (each count bold with its noun: owner's image 297)
        self.assertEqual(page.scope_note.text, u"<b>2 glyphs</b> (a, l): <b>3 variants</b> to build; <b>1 variant</b> "
                                               u"the font has already is left as it is.")
        self.assertTrue(page.build_button.enabled)
        page.build_variants()
        self.assertEqual(sorted(g.name for g in owner.package.glyphs if u".alt" in g.name),
                         [u"a.alt1", u"a.alt2", u"l.alt1", u"l.alt2"], "the checked letters' variants, and no other")
        done = [text for level, text in owner.logged if level == "done"]
        self.assertTrue(done and u"Built <b>3 variants</b> of <b>2 glyphs</b>" in done[0], owner.logged)
        self.assertIn(u': <a href="glyphname:a.alt1">a.alt1</a> <a href="glyphname:a.alt2">a.alt2</a> '
                      u'<a href="glyphname:l.alt2">l.alt2</a> (subtle, seed 1)', done[0],
                      "a few variants: each named, a link the log draws and opens")
        self.assertEqual([text for level, text in owner.logged if level == "warning"],
                         [u"<b>1 variant</b> the font has already, left as it is."])
        self.assertEqual(owner.runs, 1, "the font read again")
        # Starting copies are named as links too
        del owner.logged[:]
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        page.make_copies()
        self.assertIn(u'<a href="glyphname:a.ss01">a.ss01</a>', owner.logged[0][1])

    def test_figures_and_punctuation_are_built_when_chosen(self):
        """The builder skipped figures and punctuation marks, checked or typed: they are built as letters
        are, with their advance width kept (a tabular figure stays tabular)."""
        page, owner = self.page()
        for glyph in (u"nine", u"period", u"ampersand", u"plus"):
            self.row(page, glyph).setCheckState(0, ft.CHECKED)
        self.assertEqual(page.characters_in_scope()[0], [u"ampersand", u"nine", u"period"],
                         "a figure and two punctuation marks; not the plus sign, a symbol")
        self.assertEqual(page.scope_note.text, u"<b>3 glyphs</b> (ampersand, nine, period): <b>6 variants</b> to build.")
        page.build_variants()
        built = sorted(g.name for g in owner.package.glyphs if u".alt" in g.name and not g.name.startswith(u"l."))
        self.assertEqual(built, [u"ampersand.alt1", u"ampersand.alt2", u"nine.alt1", u"nine.alt2", u"period.alt1",
                                 u"period.alt2"])
        self.assertEqual(owner.package.by_name[u"nine.alt1"].layers[u"Regular"].advanceWidth, 500, "the figure's width")
        done = [text for level, text in owner.logged if level == "done"]
        self.assertIn(u"Built <b>6 variants</b> of <b>3 glyphs</b>", done[0])
        self.assertIn(u"the glyphs that double most in text first", done[0])

    def test_the_other_scopes(self):
        page, owner = self.page()
        owner.often = u"les9.+ "
        self.pick(page, "doubled")
        self.assertEqual(page.characters_in_scope()[0], [u"period", u"nine", u"e", u"l", u"s"],
                         "the letters, figures, and marks that often stand doubled in text; no symbol, no space")
        self.pick(page, "typed")
        self.type(page, u"xu9.+ xq")
        self.assertEqual(page.characters_in_scope()[0], [u"x", u"u", u"nine", u"period"],
                         "as typed, once each; those the font has, a figure and a period among them")
        self.assertTrue(page.letters_edit.enabled)
        self.assertEqual(page.build_button.text, u"Build 8 variants")
        self.pick(page, "both")
        self.assertFalse(page.letters_edit.enabled)
        self.assertEqual(page.characters_in_scope()[0], [u"A", u"a", u"e", u"l", u"s", u"u", u"x"], "a case: letters only")
        self.assertEqual(page.build_button.text, u"Build 13 variants")
        # A scope's name is the name alone; what it holds is in the box's What's This
        self.assertEqual([label for _, label in fa.SCOPES],
                         [u"The ticked suggestions", u"Often doubled", u"These glyphs",
                          u"Lowercase letters", u"Capitals", u"Capitals and lowercase", u"Everything"])
        self.assertEqual(ft.fc.TURN_CHECK_LABELS["often"], u"Tick often doubled",
                         "the first tab's words for the same glyphs (its button in the bottom row)")
        for words in (u"<i>Often doubled</i>, the glyphs that often stand doubled in text",
                      u"<i>Everything</i>, every letter, figure, and punctuation mark of the font"):
            self.assertIn(words, page.scope_box.whats)

    def test_the_box_says_what_to_type_only_while_it_is_used(self):
        """Its gray example read "lest", which nobody took for one: the box says what to type while These
        glyphs is picked, and is grayed out, with no words in it, otherwise. Its words end with an ellipsis,
        as every field's (owner's image 309); with no font, it says n/a. Owner's image 296: with nothing
        typed, the previews showed a; they are empty."""
        page, owner = self.page()
        self.assertEqual(page.scope(), "checked")
        self.assertFalse(page.letters_edit.enabled)
        self.assertEqual(page.letters_edit.placeholder, u"", "grayed out: no words in it")
        self.pick(page, "typed")
        self.assertTrue(page.letters_edit.enabled)
        self.assertEqual(page.letters_edit.placeholder, u"Type characters\N{HORIZONTAL ELLIPSIS}")
        self.assertEqual(self.listed(page), ([], []))
        self.assertIsNone(page.preview_glyph(), "nothing typed: nothing previewed")
        page.draw_preview()
        self.assertIsNone(page.existing.pixmap)
        self.assertFalse(page.existing_caption.visible)
        self.type(page, u"a g 0 !")  # (the example its What's This gives, taken as it says)
        self.assertEqual(page.characters_in_scope()[0], [u"a"], "of a, g, 0, and !, the font has a; spaces pass")
        self.assertEqual(self.listed(page), ([u"a"], [u"a"]), "listed as typed")
        self.assertEqual(page.preview_glyph(), u"a")
        self.assertNotIn(u"lest", page.letters_edit.whats)
        self.assertIn(u"with spaces or without (a g 0 !)", page.letters_edit.whats)
        self.pick(page, "all")
        self.assertFalse(page.letters_edit.enabled)
        self.assertEqual(page.letters_edit.placeholder, u"")
        owner.package = None
        page.fill()
        self.assertEqual(page.letters_edit.placeholder, u"n/a", "no font: grayed out, n/a")
        self.assertFalse(page.letters_edit.enabled)

    def test_buttons_are_grayed_out_while_the_window_is_busy_too(self):
        """Auto Kerning's enable() leaves a widget alone when it reports the state asked for, and a widget
        whose container is disabled reports disabled: set while the font was read after a build (the
        lists disabled meanwhile), a button to gray out stayed clickable once the lists came back."""
        page, owner = self.page()
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.assertTrue(page.build_button.enabled and page.copy_button.enabled)
        buttons = (page.build_button, page.copy_button, page.none_button)
        for button in buttons:  # as Qt reports a widget in a disabled container: disabled, whatever its own state
            button.__class__ = ft.ContainedButton
            button.own = True
        ft.ContainedButton.container_disabled = True
        try:
            self.row(page, u"a").setCheckState(0, ft.UNCHECKED)  # (nothing left to build, copy, or uncheck)
        finally:
            ft.ContainedButton.container_disabled = False
        self.assertEqual([button.enabled for button in buttons], [False, False, False],
                         "grayed out once the container is enabled again")

    def test_the_option_is_grayed_out_while_no_glyph_in_scope_has_an_alternate(self):
        """The owner: the option should read "Also build variants from existing alternates", and be grayed
        out where there is no alternate to build from. It then counts as unticked, its tick kept. Owner's
        image 269: it stayed grayed out after a build of variants, the font's only alternates being the
        ones FreeLab built: they are alternates to build from too, and the scope decides (not the font)."""
        self.assertEqual(fa.DESIGNS_LABEL, u"Also build variants from existing alternates.")
        turns = lambda ch: bool(ch) and ft.fc.char_kind(ch) is not None
        self.assertTrue(fa.has_designs({0x57: u"W"}, fa.alternates_index([u"W", u"W.ss01"]), turns))
        self.assertTrue(fa.has_designs({0x57: u"W"}, fa.alternates_index([u"W", u"W.alt1"]), turns),
                        "a variant built before is an alternate to build from")
        self.assertFalse(fa.has_designs({0x57: u"W"}, fa.alternates_index([u"W", u"W.sc"]), turns),
                         "a small capital is no design to build from")
        self.assertFalse(fa.has_designs({0x2B: u"plus"}, fa.alternates_index([u"plus", u"plus.ss01"]), turns),
                         "a symbol takes no turns: its alternate serves no variant")
        self.assertTrue(fa.designs_in([u"a", u"W"], fa.alternates_index([u"a", u"W", u"a.alt1"])))
        self.assertFalse(fa.designs_in([u"W"], fa.alternates_index([u"a", u"W", u"a.alt1"])), "W has none")
        page, owner = self.page([(u"a", 0x61), (u"W", 0x57), (u"a.alt1", None), (u"space", 0x20)], ((u"a", 49), (u"W", 22)))
        self.assertFalse(page.designs_box.enabled, "nothing ticked: no glyph in scope")
        self.row(page, u"W").setCheckState(0, ft.CHECKED)
        self.assertFalse(page.designs_box.enabled, "W has no alternate")
        self.assertTrue(page.designs_box.whats.startswith(u"Grayed out: no glyph in scope has an alternate to build from"))
        self.assertIn(u"Grayed out", page.designs_box.tip, "said on hover too")
        page.designs_box.setChecked(True)  # (set for other glyphs, kept here)
        page.update_buttons()
        self.assertFalse(page.from_designs(), "counts as unticked")
        self.assertTrue(page.designs_box.checked, "the user's setting is kept")
        self.assertEqual(plain(page.scope_note.text), u"1 glyph (W): 2 variants to build.", "no count of alternates: none used")
        # a has a.alt1 (a variant built before): ticked, the option is back, ticked as it was left
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.assertTrue(page.designs_box.enabled and page.from_designs())
        self.assertEqual(page.designs_box.whats, fa.DESIGNS_WHAT)
        self.assertEqual(page.designs_box.tip, u"")
        self.assertEqual(plain(page.scope_note.text), u"2 glyphs (a, W): 3 variants to build (1 from the font's alternates); "
                                               u"1 variant the font has already is left as it is.",
                         "a.alt2 made of a.alt1, the alternate it has")
        # The fonts of the other tests have alternates: the option is theirs to tick
        page = self.page()[0]
        self.row(page, u"u").setCheckState(0, ft.CHECKED)
        self.assertTrue(page.designs_box.enabled, "u.01 and u.02 are designs of u")

    def test_a_scope_per_script_and_one_for_every_glyph(self):
        """The owner asked for a dropdown of which glyphs get a variant (common pairs, all Latin, all
        glyphs): the font's scripts are scopes, Latin first, and one scope takes every glyph that can
        take turns."""
        glyphs = LATIN + [(u"uni0434", 0x434), (u"uni0436", 0x436), (u"uni0416", 0x416), (u"alpha", 0x3B1),
                          (u"uni0434.loclBGR", None)]
        page, owner = self.page(glyphs)
        self.assertEqual(page.scope_box.labels,
                         [u"The ticked suggestions", u"Often doubled", u"These glyphs",
                          u"Latin glyphs", u"Cyrillic glyphs", u"Greek glyphs",
                          u"Lowercase letters", u"Capitals", u"Capitals and lowercase", u"Everything"],
                         "Latin first, then the script with the most glyphs")
        self.pick(page, "script:Latin")
        self.assertEqual(page.characters_in_scope()[0], [u"A", u"a", u"e", u"l", u"s", u"u", u"x"],
                         "a script's glyphs: no figure, no shared punctuation mark, no form of a glyph")
        self.pick(page, "script:Cyrillic")
        self.assertEqual(page.characters_in_scope()[0], [u"uni0416", u"uni0434", u"uni0436"])
        self.assertEqual(page.build_button.text, u"Build 6 variants")
        self.pick(page, "all")
        self.assertEqual(page.characters_in_scope()[0],
                         [u"ampersand", u"period", u"nine", u"A", u"a", u"e", u"l", u"s", u"u", u"x", u"alpha",
                          u"uni0416", u"uni0434", u"uni0436"], "every letter, figure, and mark; no plus sign, no space")
        # The scope picked stays picked when the font is read again; a script the font lost falls back
        self.pick(page, "script:Cyrillic")
        page.fill()
        self.assertEqual(page.scope(), "script:Cyrillic")
        owner.package = Font(LATIN)
        page.fill()
        self.assertEqual(page.scope(), "checked")
        self.assertNotIn(u"Cyrillic glyphs", page.scope_box.labels)

    def test_scripts_and_cases_do_not_depend_on_the_python(self):
        """FontLab's Python 2.7 knows Unicode 5.2: a letter encoded since (U+A7AE, a capital of Unicode
        7.0) has no category there. Scripts and cases are read from the model's tables instead."""
        self.assertEqual(fa.script_of(u"a"), u"Latin")
        char = fa.to_char
        self.assertEqual(fa.script_of(char(0xA7AE)), u"Latin")
        self.assertEqual(fa.script_of(char(0x434)), u"Cyrillic")
        self.assertEqual(fa.script_of(char(0x4E00)), u"Han")
        self.assertEqual(fa.script_of(char(0x3042)), u"Hiragana")
        self.assertIsNone(fa.script_of(u"1"), "a figure belongs to no script")
        self.assertIsNone(fa.script_of(u"."))
        self.assertTrue(fa.in_scope(char(0xA7AE), "upper"))
        self.assertFalse(fa.in_scope(char(0xA7AE), "lower"))
        self.assertTrue(fa.in_scope(char(0x1C5), "upper"), "a title-case letter counts as a capital")
        self.assertFalse(fa.in_scope(char(0x4E00), "both"), "an ideograph has no case")
        self.assertEqual(fa.font_scripts([char(0x434), char(0x436), u"a", u"b", u"1", u"."]), [u"Latin", u"Cyrillic"])
        self.assertEqual(fa.font_scripts([char(0x434), char(0x436), char(0x3B1)]), [u"Cyrillic", u"Greek"])
        # Without the table (a file missing beside the script), the running Python answers
        self.assertTrue(fa.in_scope(u"a", "lower", cases=()))
        self.assertEqual(fa.load_tables(os.path.join(HERE, "no-such-file.json")), {"scripts": None, "cases": None})

    def test_a_build_too_large_is_refused_before_anything_is_made(self):
        """Every glyph of a CJK font times three variants cannot fit a font (65,535 glyphs), and more
        variants than the first tab's turns serve are of no use: the line under the settings says so,
        the button is grayed out, and a click builds nothing."""
        self.assertEqual(fa.BUILD_MOST, ft.fc.TURN_BYTES_MAX // 8, "what the first tab's turns by position serve")
        self.assertIsNone(problem_words(6000, 59535))
        self.assertEqual(problem_words(3000, 62536),
                         u"Nothing can be built: the font has 62,536 glyphs, this build would add 3,000 glyphs, and "
                         u"a font holds 65,535 glyphs at most. Choose fewer glyphs (a script, a case, or the glyphs "
                         u"that often double in text) or fewer variants each.")
        self.assertIn(u"the font has 65,535 glyphs, this build would add 1 glyph,", problem_words(1, 65535))
        self.assertEqual(problem_words(6001, 100),
                         u"Nothing can be built: 6,001 variants is more than one click builds (6,000 at most: more "
                         u"could not all take turns in the first tab's code). Choose fewer glyphs (a script, a case, "
                         u"or the glyphs that often double in text) or fewer variants each.")
        self.assertIsNone(problem_words(6000, 100, pace=0.1), "10 minutes: allowed")
        self.assertEqual(problem_words(3000, 100, pace=0.5),
                         u"Nothing can be built: 3,000 variants would take about 25 minutes at the last build's pace, "
                         u"and one click builds for 10 minutes at most. Choose fewer glyphs or fewer variants each.")
        self.assertIsNone(problem_words(0, 65535), "nothing to build: nothing to refuse")
        self.assertIn(u"<b>6,001 variants</b> is more than one click builds (<b>6,000</b> at most",
                      fa.build_problem(6001, 100), "each count bold with its noun, a number alone bold alone")
        self.assertEqual([fa.duration(seconds) for seconds in (0, 20, 60, 100, 600)],
                         [u"1 minute", u"1 minute", u"1 minute", u"2 minutes", u"10 minutes"])
        # In the tab: 2,200 ideographs, 3 variants each
        glyphs = [(u"uni%04X" % code, code) for code in range(0x4E00, 0x4E00 + 2200)]
        page, owner = self.page(glyphs)
        self.assertIn(u"Han glyphs", page.scope_box.labels)
        self.pick(page, "all")
        self.assertEqual(page.build_button.text, u"Build 4,400 variants")
        self.assertTrue(page.build_button.enabled)
        page.count_box.setValue(3)
        page.update_buttons()
        self.assertEqual(page.build_button.text, u"Build variants")
        self.assertFalse(page.build_button.enabled)
        self.assertIn(u"6,600 variants is more than one click builds (6,000 at most", plain(page.scope_note.text))
        page.build_variants()
        self.assertEqual(len(owner.package.glyphs), 2200, "nothing made")
        self.assertEqual(owner.was_busy, [])
        self.assertEqual([level for level, _ in owner.logged], ["warning"])
        # The last build's pace refuses one that would take too long; a long one allowed says only that it
        # may take a bit (the owner, 2026-11-14: no time, no word of the progress)
        page.count_box.setValue(1)
        page.pace = 0.25
        page.update_buttons()
        self.assertTrue(plain(page.scope_note.text).endswith(u"to build. A build this large may take a bit."),
                        plain(page.scope_note.text))
        self.assertNotIn(u"minute", plain(page.scope_note.text))
        page.pace = 0.5
        page.update_buttons()
        self.assertFalse(page.build_button.enabled)
        self.assertIn(u"would take about 18 minutes at the last build's pace", plain(page.scope_note.text))

    def test_the_list_checks_all_or_none_and_looks_like_the_other_lists(self):
        """The suggestions had no quick way to check all or none, and looked cramped: its rows were one
        line of text high where the window's other lists have pictures. It draws its glyphs too."""
        page, owner = self.page()
        self.assertEqual(page.tree.headers, [u"Unicode", u"Glyph", u"Fonts with alternates", u"Current alternates"])
        self.assertEqual((page.tree.icon_size.width, page.tree.icon_size.height), (fa.ICON_SIZE * 3, fa.ICON_SIZE))
        self.assertEqual(fa.ICON_SIZE, ft.fc.ICON_SIZE, "the row height of the window's other lists")
        row = self.row(page, u"u")
        self.assertEqual(row.icons, {1: ("picture", u"u"), 3: ("picture", u"u.01", u"u.02")})
        self.assertEqual(self.row(page, u"a").icons, {1: ("picture", u"a")}, "no alternate: no picture of one")
        self.assertEqual((page.all_button.text, page.none_button.text), (u"Tick all", u"Tick none"))
        self.assertTrue(page.all_button.enabled)
        self.assertFalse(page.none_button.enabled, "nothing checked: nothing to uncheck")
        suggested = len(page.group_rows(fa.SUGGESTIONS_KEY))
        page.all_button.slots["clicked()"][0]()
        self.assertEqual(len(page.checked_glyphs()), suggested)
        # Owner's report 118: these buttons left no line in the log
        self.assertEqual(owner.logged[-1][1], u"<i>Tick all</i> ticked <b>%d glyphs</b>." % suggested)
        self.assertFalse(page.all_button.enabled, "all checked: nothing more to check")
        self.assertTrue(page.none_button.enabled)
        self.assertTrue(page.copy_button.enabled)
        self.assertEqual(page.build_button.text, u"Build 11 variants", "the build's count follows the checks")
        self.row(page, u"a").setCheckState(0, ft.UNCHECKED)
        self.assertTrue(page.all_button.enabled and page.none_button.enabled)
        page.none_button.slots["clicked()"][0]()
        self.assertEqual(page.checked_glyphs(), [])
        self.assertEqual(owner.logged[-1][1], u"<i>Tick none</i> unticked <b>%d glyphs</b>." % (suggested - 1))
        self.assertFalse(page.copy_button.enabled)
        owner.busy = True
        page.check_all(True)
        self.assertEqual(page.checked_glyphs(), [], "busy: no click taken")

    def test_the_two_jobs_are_told_apart(self):
        """The owner built variants without making copies first and wondered what the copies were for:
        the button says what its copies are for, and each part says that neither is a step of the other."""
        page, owner = self.page()
        self.assertEqual(page.copy_button.text, u"Make copies to redraw")
        self.assertIn(u"To draw an alternate by hand, tick a glyph, then click <i>Make copies to redraw</i>",
                      page.note.text)
        self.assertIn(u"<i>Selected glyphs</i>: the glyphs <i>Variants that take turns</i> builds, as its "
                      u"<i>Glyphs</i> dropdown picks them, another job, which needs no such copy.", page.note.text)
        # (a count bold with its noun; a number whose noun is outside, bold alone: owner's image 301)
        self.assertIn(u"(of <b>412 open-licensed families</b>, <b>128</b> have alternates)", page.note.text)
        for glyph in (u"a", u"l"):
            self.row(page, glyph).setCheckState(0, ft.CHECKED)
        page.make_copies()
        self.assertIn(u"Made <b>2 copies to redraw</b>: ", owner.logged[0][1])
        self.assertIn(u"the <i>Forms</i> tab writes their sets; <i>Edit &gt; Undo</i> takes them back.", owner.logged[0][1])
        del owner.logged[:]
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.row(page, u"l").setCheckState(0, ft.UNCHECKED)
        page.make_copies()
        self.assertIn(u"Made <b>1 copy to redraw</b>: ", owner.logged[0][1])
        self.assertIn(u"writes its set; <i>Edit &gt; Undo</i> takes it back.", owner.logged[0][1])

    # Variants built from a glyph's alternates as well as from the glyph (the owner's font has W and
    # W.ss01, two designs: both variants were made of W)

    def test_the_designs_of_a_glyph(self):
        names = [u"W", u"W.ss01", u"W.2", u"W.salt", u"W.alt", u"W.alt1", u"W.ss01.alt2", u"W.sc", u"W.cv05",
                 u"W.calt1", u"W.swsh", u"Wacute.ss01"]
        alternates = fa.alternates_of(u"W", names)
        self.assertEqual(fa.designs_of(u"W", alternates),
                         [u"W", u"W.2", u"W.alt", u"W.alt1", u"W.calt1", u"W.cv05", u"W.salt", u"W.ss01"],
                         "the glyph and its alternates, a variant built before among them (owner's image 269); no "
                         "variant of an alternate, no small capital, no other glyph's")
        self.assertEqual(fa.variant_numbers(u"W", alternates), {1: u"W.alt1", 2: u"W.ss01.alt2"})
        self.assertEqual(fa.alternates_index(names)[u"W"], alternates, "the same alternates, read once for the font")
        self.assertEqual(fa.designs_of(u"a", []), [u"a"])

    def test_variants_are_spread_over_the_designs_in_turn(self):
        names = set([u"W", u"W.ss01", u"w", u"w.ss01", u"w.2", u"a"])
        self.assertEqual(fa.variants_planned([u"W", u"w", u"a"], 4, names, designs=True),
                         [(u"W", [(u"W.alt1", 1, u"W"), (u"W.ss01.alt2", 2, u"W.ss01"), (u"W.alt3", 3, u"W"),
                                  (u"W.ss01.alt4", 4, u"W.ss01")]),
                          (u"w", [(u"w.alt1", 1, u"w"), (u"w.2.alt2", 2, u"w.2"), (u"w.ss01.alt3", 3, u"w.ss01"),
                                  (u"w.alt4", 4, u"w")]),
                          (u"a", [(u"a.alt1", 1, u"a"), (u"a.alt2", 2, u"a"), (u"a.alt3", 3, u"a"),
                                  (u"a.alt4", 4, u"a")])])
        self.assertEqual(fa.variants_planned([u"W"], 2, names),
                         [(u"W", [(u"W.alt1", 1, u"W"), (u"W.alt2", 2, u"W")])], "without the option: as before")
        # A number is given once, whatever the design: no two variants of a glyph share one
        names.update([u"W.alt1", u"W.ss01.alt2"])
        self.assertEqual(fa.variants_planned([u"W"], 3, names, designs=True), [(u"W", [(u"W.ss01.alt3", 3, u"W.ss01")])],
                         "W, W.alt1 (built before), and W.ss01 in turn: the third from W.ss01")
        self.assertEqual(fa.variants_planned([u"W"], 3, names), [(u"W", [(u"W.alt3", 3, u"W")])],
                         "number 2 is taken by the alternate's variant: W.alt2 is not built beside it")

    def test_the_option_builds_from_both_designs(self):
        page, owner = self.page(DESIGNS, ((u"W", 22), (u"w", 20), (u"a", 49)))
        self.row(page, u"W").setCheckState(0, ft.CHECKED)
        self.assertEqual(plain(page.scope_note.text), u"1 glyph (W): 2 variants to build.")
        page.designs_box.setChecked(True)
        page.designs_box.slots["toggled(bool)"][0](True)
        self.assertEqual(plain(page.scope_note.text), u"1 glyph (W): 2 variants to build (1 from the font's alternates).")
        item = self.row(page, u"W")
        page.tree.selectedItems = lambda: [item]
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: W, W.ss01")
        self.assertEqual(page.preview_caption.text, u"To build (Subtle, seed 1): W.alt1, W.ss01.alt2")
        font = owner.package
        self.assertEqual([path[1] for path in page.preview.pixmap.drawn],
                         [id(font.by_name[u"W"].layers[u"Regular"]), id(font.by_name[u"W.ss01"].layers[u"Regular"])],
                         "each variant drawn from the design it is a copy of")
        font.by_name[u"W.ss01"].layers[u"Regular"].advanceWidth = 640
        font.by_name[u"W.ss01"].layers[u"Regular"].shapes = [ft.Anything(), ft.Anything()]
        page.build_variants()
        self.assertEqual(sorted(g.name for g in font.glyphs if u".alt" in g.name and g.name[0] == u"W"),
                         [u"W.alt1", u"W.ss01.alt2"])
        built = font.by_name[u"W.ss01.alt2"].layers[u"Regular"]
        self.assertEqual((built.advanceWidth, len(built.shapes)), (640, 2), "a copy of the alternate, with its width")
        self.assertEqual(font.by_name[u"W.alt1"].layers[u"Regular"].advanceWidth, 500)
        done = [text for level, text in owner.logged if level == "done"][0]
        self.assertIn(u"Built <b>2 variants</b> of <b>1 glyph</b>: ", done)
        self.assertIn(u"(subtle, seed 1, <b>1</b> from the font's alternates)", done)
        # Read again: the variants are the font's; nothing more to build of W
        item = self.row(page, u"W")
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: W, W.alt1, W.ss01, W.ss01.alt2")
        self.assertIn(u"Nothing to build of W", page.preview_caption.text)
        page.count_box.setValue(3)
        page.draw_preview()
        self.assertEqual(page.preview_caption.text, u"To build (Subtle, seed 1): W.ss01.alt3",
                         "the third from the third design: W, W.alt1 (built before), W.ss01")
        # The first tab cycles them all in W's turn, and leaves W.ss01 to the Forms tab, as before
        names = [g.name for g in font.glyphs]
        sets = ft.fc.alternate_sets(names, lambda name: name in (u"W", u"w", u"a"))
        self.assertEqual(sets[u"W"], [u"W.alt1", u"W.ss01.alt2"])
        self.assertEqual(sets[u"a"], [u"a.alt1"])
        self.assertNotIn(u"W.ss01", sets)

    def test_the_first_tab_reads_every_name_the_builder_gives(self):
        for suffix in (u"ss01", u"cv12", u"salt", u"alt", u"calt1", u"2", u"01"):
            design = u"W.%s" % suffix
            self.assertEqual(fa.designs_of(u"W", [design]), [u"W", design], design)
            name = fa.variants_planned([u"W"], 2, set([u"W", design]), designs=True)[0][1][1][0]
            self.assertEqual(name, design + u".alt2")
            self.assertEqual(ft.fc.alternate_sets([u"W", design, name], lambda glyph: glyph == u"W")[u"W"][-1], name)
        # A small capital's alternate is not in the glyph's turn, nor a variant whose design is gone
        self.assertEqual(ft.fc.alternate_sets([u"a", u"a.sc", u"a.sc.alt1"], lambda glyph: True), {})
        self.assertEqual(ft.fc.alternate_sets([u"W", u"W.ss01.alt2"], lambda glyph: True), {})
        self.assertEqual(fa.designs_of(u"W", [u"W.swsh", u"W.ssty"]), [u"W"], "no suffix the first tab would read back")

    def test_counted_texts_follow_their_number(self):
        plan = lambda n, others=0: [(u"g%d" % i, [(u"g%d.alt1" % i, 1, u"g%d.ss01" % i if i < others else u"g%d" % i)])
                                    for i in range(n)]
        self.assertEqual(words(plan(1), 1, "all"), (u"Build 1 variant", u"1 glyph (g0): 1 variant to build."))
        self.assertEqual(words(plan(2), 1, "all"),
                         (u"Build 2 variants", u"2 glyphs (g0, g1): 2 variants to build."))
        self.assertEqual([words(plan(2, others), 1, "all", designs=True)[1] for others in (0, 1, 2)],
                         [u"2 glyphs (g0, g1): 2 variants to build (0 from the font's alternates).",
                          u"2 glyphs (g0, g1): 2 variants to build (1 from the font's alternates).",
                          u"2 glyphs (g0, g1): 2 variants to build (2 from the font's alternates)."])
        self.assertEqual(words([(u"a", [])], 1, "all"),
                         (u"Build variants", u"1 glyph (a): no variant to build; 1 variant the font has already is "
                                             u"left as it is."))
        self.assertEqual(words([], 2, "all")[1],
                         u"The font has no glyph that can take turns (a letter's, a figure's, or a punctuation mark's).")
        self.assertEqual([fa.counted(n, u"glyph") for n in (0, 1, 2, 65535)],
                         [u"0 glyphs", u"1 glyph", u"2 glyphs", u"65,535 glyphs"])
        self.assertEqual(words(plan(3), 1, "all", problem=u"Refused.")[1], u"Refused.")

    def test_a_long_build_shows_its_progress_and_takes_no_clicks(self):
        """A build of a whole alphabet left FontLab not responding: each letter is counted in the top
        line, and the dialog is busy meanwhile, so a click the window answers starts nothing."""
        glyphs = [(u"uni%04X" % code, code) for code in range(0x100, 0x180) if fa.in_scope(fa.to_char(code), "both")]
        page, owner = self.page(glyphs)
        self.pick(page, "both")
        letters = len(glyphs)
        self.assertEqual(page.build_button.text, u"Build %d variants" % (2 * letters))
        self.assertTrue(plain(page.scope_note.text).endswith(u" " + fa.LONG_BUILD_WORDS))
        self.assertEqual(fa.LONG_BUILD_WORDS, u"A build this large may take a bit.", "the owner's words")
        self.assertNotIn(u"top line", plain(page.scope_note.text))
        self.assertIn(u"uni0107\N{HORIZONTAL ELLIPSIS})", page.scope_note.text, "the first letters named, not all")
        seen = []
        owner.progress = lambda what, done=None, total=None, force=False, stoppable=True: seen.append(
            (what, done, total, owner.busy and not stoppable))
        page.build_variants()
        counted = [row for row in seen if row[0] == u"Building variants"]
        self.assertEqual([row[1] for row in counted], list(range(letters)), "each letter counted")
        self.assertTrue(all(row[2] == letters and row[3] for row in counted),
                        "busy while the window answers, never stopped half way (a write)")
        self.assertEqual(owner.was_busy, [True, False])
        self.assertEqual(sum(1 for g in owner.package.glyphs if u".alt" in g.name), 2 * letters)
        self.assertNotIn(u"glyphname:", owner.logged[0][1], "a whole alphabet's variants are counted, not named")
        owner.busy = True
        page.build_variants()
        page.make_copies()
        self.assertEqual(sum(1 for g in owner.package.glyphs if u".alt" in g.name), 2 * letters, "busy: nothing started")
        self.assertEqual(owner.runs, 1)

    def test_a_glyph_added_meanwhile_is_not_added_twice(self):
        """The names were read when the list was made; a glyph of a planned name added since (in FontLab,
        while the window answered) was added a second time under the same name."""
        page, owner = self.page()
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        page.update_buttons()
        owner.package.addGlyph(Glyph(u"a.alt1"))  # (added in FontLab since: the list does not know it)
        page.build_variants()
        self.assertEqual(sorted(g.name for g in owner.package.glyphs if g.name.startswith(u"a.alt")), [u"a.alt1", u"a.alt2"],
                         "a.alt1 once: the font's own, left as it is")
        self.assertIn(u"<b>1 variant</b> the font has already, left as it is.",
                      [text for level, text in owner.logged if level == "warning"])
        self.assertIsNone(page.copy_glyph(u"a", u"a.alt2"), "asked of the font at the moment of writing")
        self.assertEqual(sum(1 for g in owner.package.glyphs if g.name == u"a.alt2"), 1)

    def test_the_previews_show_the_fonts_alternates_and_the_variants_to_build(self):
        """The preview showed the seed variants only: a letter's alternates in the font (u.01, u.02) and
        variants built before were nowhere. They are at the left; what a build would add at the right."""
        page, owner = self.page()
        item = self.row(page, u"u")
        page.tree.selectedItems = lambda: [item]
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: u, u.01, u.02")
        self.assertEqual(len(page.existing.pixmap.drawn), 3, "the letter and its two alternates")
        self.assertEqual(page.preview_caption.text, u"To build (Subtle, seed 1): u.alt1, u.alt2")
        self.assertEqual(len(page.preview.pixmap.drawn), 2)
        item = self.row(page, u"l")
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: l, l.alt1", "a variant built before is the font's")
        self.assertEqual(page.preview_caption.text, u"To build (Subtle, seed 1): l.alt2", "and is not built again")
        self.assertEqual(len(page.preview.pixmap.drawn), 1)
        page.count_box.setValue(1)
        page.draw_preview()
        self.assertIsNone(page.preview.pixmap)
        self.assertEqual(page.preview_caption.text,
                         u"Nothing to build of l: the font has this variant already (see left).")
        # Built, the variants move to the left of the same letter's previews
        page.count_box.setValue(2)
        item.setCheckState(0, ft.CHECKED)
        page.build_variants()
        item = self.row(page, u"l")
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: l, l.alt1, l.alt2")
        self.assertIn(u"the font has these variants already", page.preview_caption.text)

    def test_nothing_to_act_on_takes_no_click(self):
        """The owner's audit of what stays clickable with nothing loaded: with no font, no control of the
        tab takes a click; with no glyph in scope (nothing checked), the variants' count, strength, and
        seed are grayed out with the button; a font with none of the suggested glyphs says so."""
        owner = Owner(self.ak, None)
        page = owner.page = fa.AlternatesPage(owner)
        page.fill()
        controls = [page.all_button, page.none_button, page.copy_button, page.scope_box, page.letters_edit,
                    page.count_box, page.strength_box, page.seed_box, page.designs_box, page.build_button]
        self.assertEqual([c for c in controls if c.enabled], [], "no font: nothing clickable")
        self.assertEqual((page.note.text, plain(page.scope_note.text)), (u"", u""))
        page, owner = self.page()
        self.assertEqual(page.scope(), "checked")
        self.assertTrue(page.scope_box.enabled, "a font: its scope can be picked")
        self.assertEqual([box.enabled for box in (page.count_box, page.strength_box, page.seed_box)], [False] * 3,
                         "no glyph in scope: nothing for them to set")
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.assertEqual([box.enabled for box in (page.count_box, page.strength_box, page.seed_box)], [True] * 3)
        page, owner = self.page([(u"zero", 0x30), (u"space", 0x20)], ((u"a", 49),))
        self.assertEqual(page.group_rows(fa.SUGGESTIONS_KEY), [])
        self.assertEqual([group.text(0) for group in page.tree.items], [u"Suggestions (0)", u"Selected glyphs (0)"])
        self.assertTrue(page.note.text.startswith(u"The font has none of the glyphs fonts most often give"))

    def test_a_new_seed_builds_the_variants_built_here_again_in_place(self):
        """Owner's image 270: after a build, another seed left nothing to build ("the font has these variants
        already"), where the owner wanted the same variants with another seed. Variants this tab built and
        nobody changed since are built again in place, as one step of the History; the font's own variants,
        and one drawn over since, are left as they are."""
        page, owner = self.page()
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.row(page, u"l").setCheckState(0, ft.CHECKED)
        page.build_variants()  # a.alt1, a.alt2, l.alt2 (l.alt1 is the font's own)
        font = owner.package
        self.assertEqual(sorted(page.ours), [u"a.alt1", u"a.alt2", u"l.alt2"])
        self.assertEqual(sorted(page.checked_glyphs()), [u"a", u"l"], "the font read again: its ticks kept")
        self.assertEqual(page.ours[u"a.alt1"], (u"subtle", 1))
        self.assertEqual(page.build_button.text, u"Build variants")
        self.assertFalse(page.build_button.enabled, "the same settings: nothing to build")
        item = self.row(page, u"a")
        page.tree.selectedItems = lambda: [item]
        page.draw_preview()
        self.assertEqual(page.preview_caption.text, u"Nothing to build of a: the font has these variants already (see left).")
        page.seed_box.setValue(2)
        page.update_buttons()
        self.assertTrue(page.build_button.enabled, "another seed: the variants built here are to build again")
        self.assertEqual(page.build_button.text, u"Build 3 variants")
        self.assertEqual(plain(page.scope_note.text), u"2 glyphs (a, l): 3 variants to build, all of them built here before "
                                               u"with other settings, replaced in place; 1 variant the font has "
                                               u"already is left as it is.")
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: a, a.alt1, a.alt2")
        self.assertEqual(page.preview_caption.text, u"To build (Subtle, seed 2): a.alt1, a.alt2")
        before = [shape for shape in font.by_name[u"a.alt1"].layers[u"Regular"].shapes]
        count = len(font.glyphs)
        steps = [step for step in owner.fontlab.flItems.steps if not step.endswith(u"(before)")]
        del owner.logged[:]
        page.build_variants()
        self.assertEqual(len(font.glyphs), count, "replaced in place: no glyph added")
        after = font.by_name[u"a.alt1"].layers[u"Regular"].shapes
        self.assertTrue(after and not any(shape in before for shape in after), "a.alt1 made again")
        self.assertEqual([step for step in owner.fontlab.flItems.steps if not step.endswith(u"(before)")],
                         steps + [u"FreeLab Feature Code"], "one step of the History: one Undo takes it back")
        done = [text for level, text in owner.logged if level == "done"]
        self.assertTrue(done and done[0].startswith(u"Built <b>3 variants</b> again in place: "), owner.logged)
        self.assertIn(u"(subtle, seed 2): they were built here before with other settings.", done[0])
        self.assertEqual(page.ours[u"a.alt1"], (u"subtle", 2))
        # A variant drawn over since is the user's: never replaced; the strength changes the others too
        font.by_name[u"a.alt2"].layers[u"Regular"].shapes.append(ft.Anything())
        page.fill()
        self.assertNotIn(u"a.alt2", page.ours)
        page.strength_box.setCurrentIndex(1)
        page.update_buttons()
        self.assertEqual(page.build_button.text, u"Build 2 variants", "a.alt1 and l.alt2; not a.alt2, drawn over")
        page.seed_box.setValue(1)
        page.strength_box.setCurrentIndex(0)
        self.assertEqual(fa.variants_planned([u"a"], 2, set([u"a", u"a.alt1", u"a.alt2"]), ours={u"a.alt1": (u"subtle", 1)},
                                             settings=(u"subtle", 1)), [(u"a", [])], "as built: left as it is")
        self.assertEqual(fa.variant_source(u"W.ss01.alt2", 2), u"W.ss01")

    def test_the_tab_is_two_parts_and_its_buttons_go_to_the_bottom_row(self):
        """Owner's images 244, 245, 246, 258 to 260: the heading lost "(handwriting)"; the tab is two parts of a
        splitter (it had no handle), its buttons in the window's bottom row (none between a list and its
        handle); the previews' captions are a preview's (quiet), a line between the two previews."""
        del Owner.headings[:]
        page, owner = self.page()
        self.assertEqual(Owner.headings, [u"Glyphs for alternates", u"Variants that take turns"])
        self.assertIs(page.widget, page.parts, "the tab is its splitter")
        left, right = page.bottom_buttons()
        self.assertEqual([button.text for button in left], [u"Tick all", u"Tick none"])
        self.assertEqual([button.text for button in right], [u"Make copies to redraw", u"Build variants"])
        self.assertFalse(page.existing_caption.enabled or page.preview_caption.enabled,
                         "drawn in the quiet color (ak.preview_caption)")
        self.assertIsNotNone(page.preview_line, "a line between the two previews")

    # -- the owner's round of 2026-11-18 (images 283 to 318) --------------------------------

    def test_the_list_has_suggestions_and_the_selected_glyphs(self):
        """Owner's image 302: the glyphs a set of the Glyphs dropdown picks were nowhere to see or untick. The
        list has two groups, laid out as the window's other grouped lists (a bold row, its count in
        parentheses, closable): Suggestions (copied by Make copies to redraw) and Selected glyphs (built by
        Build N variants), each button acting on its own group's ticks."""
        page, owner = self.page(LATIN + [(u"uni0434", 0x434), (u"uni0436", 0x436)])
        groups = page.tree.items
        self.assertEqual([group.text(0) for group in groups], [u"Suggestions (7)", u"Selected glyphs (0)"])
        self.assertTrue(all(group.expanded for group in groups), "open at first")
        self.assertEqual([group.checkState(0) for group in groups], [ft.UNCHECKED] * 2, "no tick box of their own")
        self.assertEqual(self.listed(page, fa.SUGGESTIONS_KEY)[0], [u"a", u"u", u"l", u"ampersand", u"plus", u"nine",
                                                                    u"period"], "the model's order")
        # The ticked suggestions (at first): Selected glyphs follows the ticks
        self.assertEqual(fa.SCOPES[0], ("checked", u"The ticked suggestions"))
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.row(page, u"u").setCheckState(0, ft.CHECKED)
        self.assertEqual(self.listed(page), ([u"a", u"u"], [u"a", u"u"]))
        self.assertEqual(page.tree.items[1].text(0), u"Selected glyphs (2)")
        self.assertEqual(page.build_button.text, u"Build 4 variants")
        # Unticked in Selected glyphs: out of the build and of the previews, the suggestion still ticked
        self.row(page, u"a", fa.SELECTED_KEY).setCheckState(0, ft.UNCHECKED)
        self.assertEqual(page.build_glyphs(), [u"u"])
        self.assertEqual(page.build_button.text, u"Build 2 variants")
        self.assertEqual(page.preview_glyph(), u"u")
        item = self.row(page, u"a", fa.SELECTED_KEY)
        page.tree.selectedItems = lambda: [item]
        self.assertEqual(page.preview_glyph(), u"u", "an unticked glyph is out of the preview, selected or not")
        page.tree.selectedItems = lambda: []
        self.assertEqual(page.checked_glyphs(), [u"a", u"u"], "Make copies to redraw: the ticked suggestions")
        self.assertTrue(page.copy_button.enabled)
        self.row(page, u"l").setCheckState(0, ft.CHECKED)  # (a new tick: listed, ticked; a stays unticked)
        self.assertEqual(self.listed(page), ([u"a", u"u", u"l"], [u"u", u"l"]))
        self.row(page, u"u").setCheckState(0, ft.UNCHECKED)  # (unticked as a suggestion: out of the pick)
        self.assertEqual(self.listed(page), ([u"a", u"l"], [u"l"]))
        # A set picked: its glyphs listed, all ticked, in place of the last pick; the suggestions keep theirs
        self.pick(page, "script:Cyrillic")
        self.assertEqual(self.listed(page), ([u"uni0434", u"uni0436"], [u"uni0434", u"uni0436"]))
        self.assertEqual(page.checked_glyphs(), [u"a", u"l"])
        row = self.row(page, u"uni0434", fa.SELECTED_KEY)
        self.assertEqual(row.texts[:4], [u"\N{CYRILLIC SMALL LETTER DE}", u"uni0434", fa.NO_DATA, fa.NO_DATA],
                         "a column that means nothing for it (no count of the model, no alternate): a dash")
        self.assertEqual(self.row(page, u"u", fa.SUGGESTIONS_KEY).texts[3], u"u.01 u.02")
        row.setCheckState(0, ft.UNCHECKED)
        self.assertEqual(page.build_glyphs(), [u"uni0436"])
        page.build_variants()
        self.assertEqual(sorted(g.name for g in owner.package.glyphs if u".alt" in g.name),
                         [u"l.alt1", u"uni0436.alt1", u"uni0436.alt2"], "the ticked selected glyph only")
        self.assertEqual(self.listed(page), ([u"uni0434", u"uni0436"], [u"uni0436"]),
                         "the font read again: the pick and its ticks kept")
        self.pick(page, "both")  # (another pick: its glyphs all ticked)
        self.assertEqual(self.listed(page)[0], self.listed(page)[1])
        self.assertIn(u"uni0434", self.listed(page)[0])
        # Every glyph of Selected glyphs unticked: the line says so
        for item in page.group_rows(fa.SELECTED_KEY):
            item.setCheckState(0, ft.UNCHECKED)
        self.assertEqual(plain(page.scope_note.text), u"Every glyph of <i>Selected glyphs</i> is unticked: tick some in the list "
                                                      u"above, or pick other glyphs here.")
        self.assertFalse(page.build_button.enabled)
        # Tick all and Tick none: both groups
        page.all_button.slots["clicked()"][0]()
        self.assertEqual(self.listed(page)[0], self.listed(page)[1])
        self.assertEqual(len(page.checked_glyphs()), 7)
        page.none_button.slots["clicked()"][0]()
        self.assertEqual((self.listed(page)[1], page.checked_glyphs(), page.build_glyphs()), ([], [], []))
        # A group closed stays closed when the list is made again
        page.tree.items[0].setExpanded(False)
        self.pick(page, "upper")
        self.assertEqual([group.expanded for group in page.tree.items], [False, True])

    def test_selected_glyphs_follow_the_ticks_on_the_next_turn(self):
        """The list is made again when a suggestion's tick changes (Selected glyphs follows it), and making it
        again deletes the row whose tick Qt is telling of: made on the next turn of the event loop, never
        inside Qt's own signal (FontLab would read a deleted row)."""
        later = []

        class Waiting(ft.Anything):
            @staticmethod
            def singleShot(interval, slot):
                later.append(slot)

        page, owner = self.page()
        timer, page_qt = Timer, sys.modules["PythonQt"].QtCore.classes
        page_qt["QTimer"] = Waiting
        try:
            self.row(page, u"a").setCheckState(0, ft.CHECKED)
            self.row(page, u"l").setCheckState(0, ft.CHECKED)
            self.assertEqual(self.listed(page), ([], []), "not inside the signal")
            self.assertEqual(len(later), 1, "once for both ticks")
            later.pop()()
            self.assertEqual(self.listed(page), ([u"a", u"l"], [u"a", u"l"]))
        finally:
            page_qt["QTimer"] = timer

    def test_a_pick_too_large_for_one_click_is_not_listed(self):
        """A whole CJK font's glyphs in Selected glyphs took seconds at each pick, and one click could never
        build them (a variant each passes what one click builds): such a pick is counted, not listed, and
        the line says why."""
        glyphs = [(u"uni%04X" % code, code) for code in range(0x4E00, 0x4E00 + 30)]
        most = fa.SELECTED_MOST
        fa.SELECTED_MOST = 20
        try:
            page, owner = self.page(glyphs)
            self.pick(page, "all")
            self.assertEqual(self.listed(page), ([], []))
            self.assertEqual(page.tree.items[1].text(0), u"Selected glyphs (30)")
            self.assertTrue(plain(page.scope_note.text).startswith(u"Nothing can be built: 30 glyphs are picked"),
                            page.scope_note.text)
            self.assertFalse(page.build_button.enabled)
            fa.SELECTED_MOST = 40
            self.pick(page, "all")
            self.assertEqual(len(self.listed(page)[1]), 30)
            # Past ROW_PICTURES, a row is drawn once it is clicked
            pictures = fa.ROW_PICTURES
            fa.ROW_PICTURES = 10
            try:
                self.pick(page, "script:Han")
            finally:
                fa.ROW_PICTURES = pictures
            rows = page.group_rows(fa.SELECTED_KEY)
            self.assertIn(1, rows[0].icons)
            self.assertFalse(getattr(rows[20], "icons", {}))
            self.assertEqual(rows[20].toolTip(1), fa.ROW_PICTURE_TIP)
            page.tree.selectedItems = lambda: [rows[20]]
            page.tree.slots["itemSelectionChanged()"][0]()
            self.assertIn(1, rows[20].icons)
            self.assertEqual(rows[20].toolTip(1), u"")
        finally:
            fa.SELECTED_MOST = most

    def test_what_a_click_builds_in_words(self):
        plan = fa.variants_planned([u"a", u"g"], 2, set([u"a", u"g", u"a.alt1", u"a.alt2"]))
        self.assertEqual(plan, [(u"a", []), (u"g", [(u"g.alt1", 1, u"g"), (u"g.alt2", 2, u"g")])])
        self.assertEqual(words(plan, 2, "both"),
                         (u"Build 2 variants", u"2 glyphs (a, g): 2 variants to build; 2 variants the font has already "
                                               u"are left as they are."))
        self.assertEqual(words([(u"period", [u"period.alt1"])], 1, "typed"),
                         (u"Build 1 variant", u"1 glyph (period): 1 variant to build."))
        self.assertEqual(words([], 2, "typed")[0], u"Build variants")
        self.assertEqual(words([], 2, "doubled")[1], u"The font has no glyph that often stands doubled in text.")
        self.assertEqual(words([], 2, "lower")[1], u"The font has no such letters.")
        self.assertEqual(fa.alternates_of(u"u", [u"u", u"u.01", u"u.sc", u"u.alt1", u"ugrave.01"]), [u"u.01", u"u.alt1"])



class BaselineReachTests(unittest.TestCase):
    def test_no_reach_keeps_the_variants_as_before(self):
        self.assertEqual(fa.variant_params(u"a", 1, "bold", 3), fa.variant_params(u"a", 1, "bold", 3, 0, 1000.0))

    def test_a_reach_moves_up_or_down_within_it_from_the_seed(self):
        plain = fa.variant_params(u"a", 1, "bold", 3)
        moved = fa.variant_params(u"a", 1, "bold", 3, 40, 1000.0)
        self.assertEqual(moved[:4], plain[:4], "the other changes are the same")
        self.assertLessEqual(abs(moved[4] - plain[4]), 0.040001)
        self.assertNotEqual(moved[4], plain[4])
        self.assertEqual(moved, fa.variant_params(u"a", 1, "bold", 3, 40, 1000.0), "the same seed, the same move")


if __name__ == "__main__":
    unittest.main()
