# -*- coding: utf-8 -*-
"""Tests of Feature Code's Stylistic alternates tab (its pure parts). Valid Python 2.7 and Python 3."""
from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "features"))
import freelab_alternates as fa  # noqa: E402


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
        self.log.add = lambda text, level="info": self.logged.append((level, text))

    @staticmethod
    def heading(QtGui, text):
        return Box()

    def current_font(self):
        return self.package

    def doubled(self, ch):
        return ch in self.often

    def kind(self, ch):
        return ft.fc.char_kind(ch)

    def picture(self, names):
        return ("picture",) + tuple(names)

    def set_busy(self, on):
        self.busy = on
        self.was_busy.append(on)

    def progress(self, what, done=None, total=None, force=False):
        self.shown.append((what, done, total))

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
    qt.QtCore = ft._FakeQtModule({"Qt": ft.FakeQt, "QSize": Size})
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

    def row(self, page, glyph):
        return [item for item in page.tree.items if item.data(0, ft.USER_ROLE) == glyph][0]

    def pick(self, page, key):
        page.scope_box.setCurrentIndex([scope for scope, _ in page.scope_rows].index(key))
        page.update_buttons()

    def test_the_build_says_its_scope_before_the_click(self):
        """Build variants built every letter of the Letters scope (1,102 of them) while two rows were
        checked: the scope is the checked characters at first, and the button and the line under the
        settings count what a click builds."""
        page, owner = self.page()
        self.assertEqual(page.scope(), "checked")
        self.assertEqual(page.build_button.text, u"Build variants")
        self.assertFalse(page.build_button.enabled, "nothing checked: nothing to build")
        self.assertIn(u"No letter, figure, or punctuation mark is checked", page.scope_note.text)
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.row(page, u"l").setCheckState(0, ft.CHECKED)
        self.row(page, u"plus").setCheckState(0, ft.CHECKED)
        self.assertEqual(page.characters_in_scope()[0], [u"a", u"l"], "the checked letters; a plus sign takes no turns")
        self.assertEqual(page.build_button.text, u"Build 3 variants")
        self.assertEqual(page.scope_note.text, u"2 glyphs (a, l): 3 variants to build; 1 variant the font has "
                                               u"already is left as it is.")
        self.assertTrue(page.build_button.enabled)
        page.build_variants()
        self.assertEqual(sorted(g.name for g in owner.package.glyphs if u".alt" in g.name),
                         [u"a.alt1", u"a.alt2", u"l.alt1", u"l.alt2"], "the checked letters' variants, and no other")
        done = [text for level, text in owner.logged if level == "done"]
        self.assertTrue(done and u"Built <b>3 variants</b> of 2 glyphs" in done[0], owner.logged)
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
        self.assertEqual(page.scope_note.text, u"3 glyphs (ampersand, nine, period): 6 variants to build.")
        page.build_variants()
        built = sorted(g.name for g in owner.package.glyphs if u".alt" in g.name and not g.name.startswith(u"l."))
        self.assertEqual(built, [u"ampersand.alt1", u"ampersand.alt2", u"nine.alt1", u"nine.alt2", u"period.alt1",
                                 u"period.alt2"])
        self.assertEqual(owner.package.by_name[u"nine.alt1"].layers[u"Regular"].advanceWidth, 500, "the figure's width")
        done = [text for level, text in owner.logged if level == "done"]
        self.assertIn(u"Built <b>6 variants</b> of 3 glyphs", done[0])
        self.assertIn(u"the glyphs that double most in text first", done[0])

    def test_the_other_scopes(self):
        page, owner = self.page()
        owner.often = u"les9.+ "
        self.pick(page, "doubled")
        self.assertEqual(page.characters_in_scope()[0], [u"period", u"nine", u"e", u"l", u"s"],
                         "the letters, figures, and marks that often stand doubled in text; no symbol, no space")
        self.pick(page, "typed")
        page.letters_edit.setText(u"xu9.+ xq")
        page.update_buttons()
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
                         [u"The checked glyphs", u"Often doubled", u"These glyphs",
                          u"Lowercase letters", u"Capitals", u"Capitals and lowercase", u"Everything"])
        self.assertEqual(ft.fc.TURN_CHECKS[0][1], u"Often doubled", "the first tab's words for the same glyphs")
        for words in (u"<i>Often doubled</i>, the glyphs that often stand doubled in text",
                      u"<i>Everything</i>, every letter, figure, and punctuation mark of the font"):
            self.assertIn(words, page.scope_box.whats)

    def test_the_box_says_what_to_type_only_while_it_is_used(self):
        """Its gray example read "lest", which nobody took for one: the box says what to type while These
        glyphs is picked, and is grayed out, with no words in it, otherwise."""
        page, owner = self.page()
        self.assertEqual(page.scope(), "checked")
        self.assertFalse(page.letters_edit.enabled)
        self.assertEqual(page.letters_edit.placeholder, u"", "grayed out: no words in it")
        self.pick(page, "typed")
        self.assertTrue(page.letters_edit.enabled)
        self.assertEqual(page.letters_edit.placeholder, u"Type characters: a g 0 !")
        page.letters_edit.setText(fa.TYPED_HINT.split(u": ")[1])  # (what it says to type is taken as it says)
        page.update_buttons()
        self.assertEqual(page.characters_in_scope()[0], [u"a"], "of a, g, 0, and !, the font has a; spaces pass")
        self.assertNotIn(u"lest", page.letters_edit.whats)
        self.assertIn(u"with spaces or without (a g 0 !)", page.letters_edit.whats)
        self.pick(page, "all")
        self.assertFalse(page.letters_edit.enabled)
        self.assertEqual(page.letters_edit.placeholder, u"")

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

    def test_the_option_is_grayed_out_in_a_font_with_no_alternate(self):
        """The owner: the option should read "Also build variants from existing alternates", and be grayed
        out where the font has no alternate at all. It then counts as unchecked, its check kept."""
        self.assertEqual(fa.DESIGNS_LABEL, u"Also build variants from existing alternates")
        turns = lambda ch: bool(ch) and ft.fc.char_kind(ch) is not None
        self.assertTrue(fa.has_designs({0x57: u"W"}, fa.alternates_index([u"W", u"W.ss01"]), turns))
        self.assertFalse(fa.has_designs({0x57: u"W"}, fa.alternates_index([u"W", u"W.alt1", u"W.sc"]), turns),
                         "a built variant and a small capital are no designs to build from")
        self.assertFalse(fa.has_designs({0x2B: u"plus"}, fa.alternates_index([u"plus", u"plus.ss01"]), turns),
                         "a symbol takes no turns: its alternate serves no variant")
        page, owner = self.page([(u"a", 0x61), (u"W", 0x57), (u"a.alt1", None), (u"space", 0x20)], ((u"a", 49), (u"W", 22)))
        self.assertFalse(page.designs)
        self.assertFalse(page.designs_box.enabled)
        self.assertTrue(page.designs_box.whats.startswith(u"Grayed out: this font has no alternate to build from"))
        self.assertIn(u"Grayed out", page.designs_box.tip, "said on hover too")
        page.designs_box.setChecked(True)  # (set in a font that had some, kept here)
        page.update_buttons()
        self.assertFalse(page.from_designs(), "counts as unchecked")
        self.assertTrue(page.designs_box.checked, "the user's setting is kept")
        self.row(page, u"W").setCheckState(0, ft.CHECKED)
        self.assertEqual(page.scope_note.text, u"1 glyph (W): 2 variants to build.", "no count of alternates: none used")
        # An alternate drawn (the font read again): the option is back, checked as it was left
        drawn = ft.FakeNewGlyph()
        drawn.name = u"W.ss01"
        owner.package.addGlyph(drawn)
        owner.package.by_name[u"W.ss01"].layers[u"Regular"] = Layer()
        page.fill()
        self.assertTrue(page.designs and page.designs_box.enabled and page.from_designs())
        self.assertEqual(page.designs_box.whats, fa.DESIGNS_WHAT)
        self.assertEqual(page.designs_box.tip, u"")
        # The fonts of the other tests have alternates: the option is theirs to check
        self.assertTrue(self.page()[0].designs_box.enabled, "u.01 and u.02 are designs of u")

    def test_a_scope_per_script_and_one_for_every_glyph(self):
        """The owner asked for a dropdown of which glyphs get a variant (common pairs, all Latin, all
        glyphs): the font's scripts are scopes, Latin first, and one scope takes every glyph that can
        take turns."""
        glyphs = LATIN + [(u"uni0434", 0x434), (u"uni0436", 0x436), (u"uni0416", 0x416), (u"alpha", 0x3B1),
                          (u"uni0434.loclBGR", None)]
        page, owner = self.page(glyphs)
        self.assertEqual(page.scope_box.labels,
                         [u"The checked glyphs", u"Often doubled", u"These glyphs",
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
        self.assertIsNone(fa.build_problem(6000, 59535))
        self.assertEqual(fa.build_problem(3000, 62536),
                         u"Nothing can be built: the font has 62,536 glyphs, this build would add 3,000 glyphs, and "
                         u"a font holds 65,535 glyphs at most. Choose fewer glyphs (a script, a case, or the glyphs "
                         u"that often double in text) or fewer variants each.")
        self.assertIn(u"the font has 65,535 glyphs, this build would add 1 glyph,", fa.build_problem(1, 65535))
        self.assertEqual(fa.build_problem(6001, 100),
                         u"Nothing can be built: 6,001 variants is more than one click builds (6,000 at most: more "
                         u"could not all take turns in the first tab's code). Choose fewer glyphs (a script, a case, "
                         u"or the glyphs that often double in text) or fewer variants each.")
        self.assertIsNone(fa.build_problem(6000, 100, pace=0.1), "10 minutes: allowed")
        self.assertEqual(fa.build_problem(3000, 100, pace=0.5),
                         u"Nothing can be built: 3,000 variants would take about 25 minutes at the last build's pace, "
                         u"and one click builds for 10 minutes at most. Choose fewer glyphs or fewer variants each.")
        self.assertIsNone(fa.build_problem(0, 65535), "nothing to build: nothing to refuse")
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
        self.assertIn(u"6,600 variants is more than one click builds (6,000 at most", page.scope_note.text)
        page.build_variants()
        self.assertEqual(len(owner.package.glyphs), 2200, "nothing made")
        self.assertEqual(owner.was_busy, [])
        self.assertEqual([level for level, _ in owner.logged], ["warning"])
        # The last build's pace refuses one that would take too long; a long one allowed says only that it
        # may take a bit (the owner, 2026-11-14: no time, no word of the progress)
        page.count_box.setValue(1)
        page.pace = 0.25
        page.update_buttons()
        self.assertTrue(page.scope_note.text.endswith(u"to build. A build this large may take a bit."),
                        page.scope_note.text)
        self.assertNotIn(u"minute", page.scope_note.text)
        page.pace = 0.5
        page.update_buttons()
        self.assertFalse(page.build_button.enabled)
        self.assertIn(u"would take about 18 minutes at the last build's pace", page.scope_note.text)

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
        self.assertEqual((page.all_button.text, page.none_button.text), (u"Check all", u"Check none"))
        self.assertTrue(page.all_button.enabled)
        self.assertFalse(page.none_button.enabled, "nothing checked: nothing to uncheck")
        page.all_button.slots["clicked()"][0]()
        self.assertEqual(len(page.checked_glyphs()), len(page.tree.items))
        self.assertFalse(page.all_button.enabled, "all checked: nothing more to check")
        self.assertTrue(page.none_button.enabled)
        self.assertTrue(page.copy_button.enabled)
        self.assertEqual(page.build_button.text, u"Build 11 variants", "the build's count follows the checks")
        self.row(page, u"a").setCheckState(0, ft.UNCHECKED)
        self.assertTrue(page.all_button.enabled and page.none_button.enabled)
        page.none_button.slots["clicked()"][0]()
        self.assertEqual(page.checked_glyphs(), [])
        self.assertFalse(page.copy_button.enabled)
        owner.busy = True
        page.check_all(True)
        self.assertEqual(page.checked_glyphs(), [], "busy: no click taken")

    def test_the_two_jobs_are_told_apart(self):
        """The owner built variants without making copies first and wondered what the copies were for:
        the button says what its copies are for, and each part says that neither is a step of the other."""
        page, owner = self.page()
        self.assertEqual(page.copy_button.text, u"Make copies to redraw")
        self.assertIn(u"To draw an alternate by hand, check a glyph, then click <i>Make copies to redraw</i>",
                      page.note.text)
        self.assertIn(u"The variants below are another job, and need no such copy.", page.note.text)
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
                         [u"W", u"W.2", u"W.alt", u"W.calt1", u"W.cv05", u"W.salt", u"W.ss01"],
                         "the glyph and its drawn alternates; no built variant, no small capital, no other glyph's")
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
        self.assertEqual(fa.variants_planned([u"W"], 3, names, designs=True), [(u"W", [(u"W.alt3", 3, u"W")])])
        self.assertEqual(fa.variants_planned([u"W"], 3, names), [(u"W", [(u"W.alt3", 3, u"W")])],
                         "number 2 is taken by the alternate's variant: W.alt2 is not built beside it")

    def test_the_option_builds_from_both_designs(self):
        page, owner = self.page(DESIGNS, ((u"W", 22), (u"w", 20), (u"a", 49)))
        self.row(page, u"W").setCheckState(0, ft.CHECKED)
        self.assertEqual(page.scope_note.text, u"1 glyph (W): 2 variants to build.")
        page.designs_box.setChecked(True)
        page.designs_box.slots["toggled(bool)"][0](True)
        self.assertEqual(page.scope_note.text, u"1 glyph (W): 2 variants to build (1 from the font's alternates).")
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
        self.assertIn(u"Built <b>2 variants</b> of 1 glyph: ", done)
        self.assertIn(u"(subtle, seed 1, 1 from the font's alternates)", done)
        # Read again: the variants are the font's, and no design; nothing more to build of W
        item = self.row(page, u"W")
        page.draw_preview()
        self.assertEqual(page.existing_caption.text, u"In the font: W, W.alt1, W.ss01, W.ss01.alt2")
        self.assertIn(u"Nothing to build of W", page.preview_caption.text)
        page.count_box.setValue(3)
        page.draw_preview()
        self.assertEqual(page.preview_caption.text, u"To build (Subtle, seed 1): W.alt3", "the third from W again")
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
        self.assertEqual(fa.build_words(plan(1), 1, "all"), (u"Build 1 variant", u"1 glyph (g0): 1 variant to build."))
        self.assertEqual(fa.build_words(plan(2), 1, "all"),
                         (u"Build 2 variants", u"2 glyphs (g0, g1): 2 variants to build."))
        self.assertEqual([fa.build_words(plan(2, others), 1, "all", designs=True)[1] for others in (0, 1, 2)],
                         [u"2 glyphs (g0, g1): 2 variants to build (0 from the font's alternates).",
                          u"2 glyphs (g0, g1): 2 variants to build (1 from the font's alternates).",
                          u"2 glyphs (g0, g1): 2 variants to build (2 from the font's alternates)."])
        self.assertEqual(fa.build_words([(u"a", [])], 1, "all"),
                         (u"Build variants", u"1 glyph (a): 0 variants to build; 1 variant the font has already is "
                                             u"left as it is."))
        self.assertEqual(fa.build_words([], 2, "all")[1], u"The font has no letter, figure, or punctuation mark.")
        self.assertEqual([fa.counted(n, u"glyph") for n in (0, 1, 2, 65535)],
                         [u"0 glyphs", u"1 glyph", u"2 glyphs", u"65,535 glyphs"])
        self.assertEqual(fa.build_words(plan(3), 1, "all", problem=u"Refused.")[1], u"Refused.")

    def test_a_long_build_shows_its_progress_and_takes_no_clicks(self):
        """A build of a whole alphabet left FontLab not responding: each letter is counted in the top
        line, and the dialog is busy meanwhile, so a click the window answers starts nothing."""
        glyphs = [(u"uni%04X" % code, code) for code in range(0x100, 0x180) if fa.in_scope(fa.to_char(code), "both")]
        page, owner = self.page(glyphs)
        self.pick(page, "both")
        letters = len(glyphs)
        self.assertEqual(page.build_button.text, u"Build %d variants" % (2 * letters))
        self.assertTrue(page.scope_note.text.endswith(u" " + fa.LONG_BUILD_WORDS))
        self.assertEqual(fa.LONG_BUILD_WORDS, u"A build this large may take a bit.", "the owner's words")
        self.assertNotIn(u"top line", page.scope_note.text)
        self.assertIn(u"uni0107\N{HORIZONTAL ELLIPSIS})", page.scope_note.text, "the first letters named, not all")
        seen = []
        owner.progress = lambda what, done=None, total=None, force=False: seen.append((what, done, total, owner.busy))
        page.build_variants()
        counted = [row for row in seen if row[0] == u"Building variants"]
        self.assertEqual([row[1] for row in counted], list(range(letters)), "each letter counted")
        self.assertTrue(all(row[2] == letters and row[3] for row in counted), "busy while the window answers")
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
                         u"Nothing to build of l: the font has this variant already (at the left).")
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
        self.assertEqual((page.note.text, page.scope_note.text), (u"", u""))
        page, owner = self.page()
        self.assertEqual(page.scope(), "checked")
        self.assertTrue(page.scope_box.enabled, "a font: its scope can be picked")
        self.assertEqual([box.enabled for box in (page.count_box, page.strength_box, page.seed_box)], [False] * 3,
                         "no glyph in scope: nothing for them to set")
        self.row(page, u"a").setCheckState(0, ft.CHECKED)
        self.assertEqual([box.enabled for box in (page.count_box, page.strength_box, page.seed_box)], [True] * 3)
        page, owner = self.page([(u"zero", 0x30), (u"space", 0x20)], ((u"a", 49),))
        self.assertEqual(page.tree.items, [])
        self.assertTrue(page.note.text.startswith(u"The font has none of the glyphs fonts most often give"))

    def test_what_a_click_builds_in_words(self):
        plan = fa.variants_planned([u"a", u"g"], 2, set([u"a", u"g", u"a.alt1", u"a.alt2"]))
        self.assertEqual(plan, [(u"a", []), (u"g", [(u"g.alt1", 1, u"g"), (u"g.alt2", 2, u"g")])])
        self.assertEqual(fa.build_words(plan, 2, "both"),
                         (u"Build 2 variants", u"2 glyphs (a, g): 2 variants to build; 2 variants the font has already "
                                               u"are left as they are."))
        self.assertEqual(fa.build_words([(u"period", [u"period.alt1"])], 1, "typed"),
                         (u"Build 1 variant", u"1 glyph (period): 1 variant to build."))
        self.assertEqual(fa.build_words([], 2, "typed")[0], u"Build variants")
        self.assertEqual(fa.build_words([], 2, "doubled")[1], u"The font has no glyph that often stands doubled in text.")
        self.assertEqual(fa.build_words([], 2, "lower")[1], u"The font has no such letters.")
        self.assertEqual(fa.alternates_of(u"u", [u"u", u"u.01", u"u.sc", u"u.alt1", u"ugrave.01"]), [u"u.01", u"u.alt1"])


if __name__ == "__main__":
    unittest.main()
