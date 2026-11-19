"""Tests of FreeLab's auto spacing: the suggestions and how composites follow. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import io
import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "spacing"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
import freelab_auto_kerning as ak  # noqa: E402
import freelab_auto_spacing as sp  # noqa: E402


def fake_busy(test, stop_after=None):
    """ak's top-row progress (busy_start, busy_progress, busy_end, busy_stopping) recorded, not shown: the
    calls made, as (name, what, part, stoppable). stop_after: busy_progress raises ak.Stopped from that
    call on, where it may (as the user's Esc would)."""
    calls = []
    saved = dict((name, getattr(ak, name)) for name in ("busy_start", "busy_progress", "busy_end", "busy_stopping"))
    test.addCleanup(lambda: [setattr(ak, name, value) for name, value in saved.items()])

    def progress(owner, what=None, part=None, force=False, stoppable=True):
        calls.append(("progress", what, part, stoppable))
        if stop_after is not None and stoppable and sum(1 for c in calls if c[0] == "progress") > stop_after:
            raise ak.Stopped()

    ak.busy_start = lambda owner, what=u"", stoppable=True: calls.append(("start", what, None, stoppable))
    ak.busy_progress = progress
    ak.busy_end = lambda owner: calls.append(("end", None, None, None))
    ak.busy_stopping = lambda owner: False
    return calls


def fake_dialog(test):
    """An Auto Spacing dialog made without its window (it needs FontLab), its widgets recording what they
    are told; test: the TestCase whose cleanup puts ak back."""
    class Widget(object):
        def __init__(self):
            self.text, self.visible, self.enabled = u"", True, True

        def setText(self, text):
            self.text = text

        def setVisible(self, on):
            self.visible = on

        def setEnabled(self, on):
            self.enabled = on

        def clear(self):
            self.text = u""

        def property(self, name):
            return None

    dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)
    dialog.ak, dialog.busy, dialog.master = ak, False, "Regular"
    dialog.tree, dialog.apply_button, dialog.composites_note, dialog.status = Widget(), Widget(), Widget(), Widget()
    dialog.spacings, dialog.listed, dialog.composites, dialog.unspaced_references = [], [], {}, []
    dialog.package = type("Package", (), {"master": "Regular"})()
    dialog.current_font = lambda: dialog.package
    dialog.update_buttons = lambda: None
    dialog.log = type("Log", (), {"add": lambda log, text, kind="info": None})()
    old = ak.history_mark
    ak.history_mark = lambda package: None
    test.addCleanup(lambda: setattr(ak, "history_mark", old))
    return dialog


class ImageMemoryTests(unittest.TestCase):
    def test_a_measuring_keeps_the_references_and_a_few_images(self):
        """Live 2026-11-19: Auto Spacing kept every measured glyph's image with its envelopes, 5 GB more of
        FontLab's memory for Noto Sans JP's 4,954 glyphs until the analysis ended."""
        images = ak.FontLabGlyphs.__new__(ak.FontLabGlyphs)
        images.images, images.keep, images.most, images._drawn = {}, set(), None, []
        for k in range(10):
            images.remember(u"g%d" % k, k)
        self.assertEqual(len(images.images), 10, "unlimited by default (Auto Kerning's)")
        self.assertIs(sp.keep_few(images, [u"H", u"n"]), images)
        self.assertEqual((images.keep, images.most), (set([u"H", u"n"]), sp.IMAGES_KEPT))
        images.images, images._drawn = {}, []
        images.remember(u"H", "h")
        for k in range(sp.IMAGES_KEPT + 20):
            images.remember(u"g%d" % k, k)
        self.assertEqual(len(images.images), sp.IMAGES_KEPT + 1, "the references and the last drawn")
        self.assertIn(u"H", images.images)
        self.assertNotIn(u"g0", images.images, "the oldest let go")
        self.assertIn(u"g%d" % (sp.IMAGES_KEPT + 19), images.images)
        old = object()
        self.assertIs(sp.keep_few(old, [u"H"]), old, "an older shared module: nothing done")
        with io.open(sp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            source = handle.read()
        measure = source.split(u"    def measure(self, package, master")[1].split(u"\n    def ")[0]
        self.assertIn(u"keep_few(glyphs, fixed_names)", measure)
        self.assertIn(u"keep_few(again, fixed_names)", measure, "and each settling pass's")


class BusyTests(unittest.TestCase):
    """Owner's image 178: Measuring... held the window until Windows called it Not Responding. The long steps
    now run under the window's top-row progress (ak.busy_*), stoppable; the write never is."""

    def test_the_measuring_tells_its_progress_and_can_be_stopped(self):
        glyphs = [sp.Spacing(ch, ch, "upper", 20, 20, 600) for ch in u"ABCD"]
        parts = []
        sp.suggest_spacing(glyphs, lambda a, b: -10, lambda ch: ch, lambda ch: "upper", progress=parts.append)
        self.assertEqual(parts, [0.0, 0.25, 0.5, 0.75], "before each glyph")

        def stop(part):
            raise ak.Stopped()
        self.assertRaises(ak.Stopped, sp.suggest_spacing, glyphs, lambda a, b: -10, lambda ch: ch, lambda ch: "upper",
                          progress=stop)
        parts = []
        sp.settle_spacing(glyphs, lambda moved: (lambda a, b: -10), lambda ch: ch, lambda ch: "upper", passes=3,
                          progress=parts.append)
        self.assertTrue(parts and all(0.0 <= part <= 1.0 for part in parts), parts)
        self.assertEqual(parts, sorted(parts), "the bar only moves on")
        self.assertEqual(sp.measure_part(sp.DRAW_STEP, 0.0), 0.0)
        self.assertEqual(sp.measure_part(sp.COMPOSITES_STEP, 1.0), 1.0)
        self.assertLess(sp.measure_part(sp.MEASURE_STEP, 1.0), sp.measure_part(sp.SETTLE_STEP, 0.5))

    def dialog(self):
        return fake_dialog(self)

    def test_a_stopped_measuring_leaves_the_list_empty(self):
        calls = fake_busy(self, stop_after=1)
        dialog = self.dialog()

        def measure(package, master, only=None, progress=None):
            for _ in range(5):
                progress(sp.MEASURE_STEP, 0.5)
            return [sp.Spacing(u"T", "T", "upper", 20, 25, 500)], {}
        dialog.measure = measure
        dialog.fill = lambda progress=None: self.fail("not listed once stopped")
        dialog.run()
        self.assertEqual([c[0] for c in calls], ["start", "progress", "progress", "end"], "ended though stopped")
        self.assertTrue(calls[0][3], "stoppable")
        self.assertFalse(dialog.busy)
        self.assertEqual(dialog.spacings, [])
        self.assertIn(u"Measuring was stopped", dialog.status.text)
        self.assertFalse(dialog.composites_note.visible)

    def test_measuring_ends_its_progress_on_an_error(self):
        calls = fake_busy(self)
        dialog = self.dialog()

        def measure(package, master, only=None, progress=None):
            raise ValueError("no references")
        dialog.measure = measure
        dialog.run()
        self.assertEqual([c[0] for c in calls], ["start", "end"])
        self.assertFalse(dialog.busy)
        self.assertFalse(dialog.failed, "not the font's doing: Analyze may try again")


class FailureTests(unittest.TestCase):
    """Owner's images 218, 224, and 253: "No halo makes ll, nn, oo agree" in red, said nothing; the top line
    went blank; Analyze stayed clickable though nothing could be done."""

    def test_the_failure_is_said_in_plain_words(self):
        text = sp.references_failed_text(ak.SCRIPT_TUNING["latin"], ValueError(u"no halo makes ll, nn, oo agree"))
        self.assertNotIn(u"halo", text.lower())
        self.assertIn(u"each set beside itself (ll, nn, oo)", text)
        self.assertIn(u"too differently apart", text, "why it failed for this font")
        self.assertIn(u"Space l, n, and o by eye first", text, "what the user can do")
        thin = sp.references_failed_text(u"lno", ValueError(u"l has no solid ink to measure from"))
        self.assertIn(u"no stroke thick enough", thin)
        self.assertTrue(issubclass(sp.CannotSpace, ValueError))

    def dialog(self):
        dialog = fake_dialog(self)
        dialog.package =type("Package", (), {"master": "Regular", "tfn": u"!The Black Bloc", "mastersCount": 1})()
        logged = dialog.logged = []
        dialog.log = type("Log", (), {"add": lambda log, text, kind="info": logged.append((kind, text))})()
        return dialog

    def test_the_top_line_keeps_the_font_and_analyze_grays(self):
        fake_busy(self)
        dialog = self.dialog()

        def measure(package, master, only=None, progress=None):
            raise sp.CannotSpace(sp.references_failed_text(u"lno", u"no halo makes ll, nn, oo agree"))
        dialog.measure = measure
        dialog.run()
        self.assertTrue(dialog.failed)
        self.assertEqual(dialog.status.text, u"<b>!The Black Bloc</b>, master <b>Regular</b>.<br><br>" + sp.FAILED_TEXT)
        self.assertEqual([kind for kind, _ in dialog.logged], ["error"])
        self.assertIn(u"Auto Spacing measures every glyph against l, n, and o", dialog.logged[0][1])

        # Analyze and the choice that only feeds it grayed; given back once the font changes so that it can
        class Widget(object):
            def __init__(self):
                self.enabled = True

            def setEnabled(self, on):
                self.enabled = on

            def property(self, name):
                return None

        for name in ("all_button", "none_button", "restore_button", "glyph_window_button", "kerning_button", "follow",
                     "group", "tolerance", "analyze_button"):
            setattr(dialog, name, Widget())
        dialog.tree = type("Tree", (), {"topLevelItemCount": 0})()
        dialog.first_checks, dialog.spaced, dialog.buttons_due = {}, [], False
        dialog.selected = lambda: None
        old = sp._qt
        sp._qt = lambda: (type("Core", (), {"Qt": type("Qt", (), {"Checked": 2, "Unchecked": 0})}), None)
        self.addCleanup(lambda: setattr(sp, "_qt", old))
        sp.AutoSpacingDialog.update_buttons(dialog)
        self.assertEqual((dialog.analyze_button.enabled, dialog.group.enabled), (False, False))
        dialog.failed = False  # (run measured the changed font)
        sp.AutoSpacingDialog.update_buttons(dialog)
        self.assertEqual((dialog.analyze_button.enabled, dialog.group.enabled), (True, True))

    def test_a_stopped_measuring_keeps_the_font_line(self):
        fake_busy(self, stop_after=0)
        dialog = self.dialog()
        dialog.measure = lambda package, master, only=None, progress=None: progress(sp.MEASURE_STEP, 0.5)
        dialog.run()
        self.assertTrue(dialog.status.text.startswith(u"<b>!The Black Bloc</b>, master <b>Regular</b>.<br><br>Measuring was "
                                                      u"stopped"), dialog.status.text)


class ReferenceTests(unittest.TestCase):
    MODEL = {"references": {"H": {"by": "height", "height_of": "H", "left": 0.08, "right": 0.075},
                            "o": {"by": "width", "height_of": "x", "left": 0.2, "right": 0.2}}}

    def test_unspaced(self):
        self.assertTrue(sp.unspaced(0, 40, 1000), "a side at its ink")
        self.assertTrue(sp.unspaced(10, 50, 1000), "one side five times the other")
        self.assertFalse(sp.unspaced(50, 55, 1000))
        self.assertFalse(sp.unspaced(25, 30, 1000), "tight is not unspaced")

    def test_reference_changes_from_the_corpus(self):
        self.assertEqual(sp.reference_changes(u"H", 0, 0, 600, {"H": 700}, self.MODEL), (56, 53))
        self.assertEqual(sp.reference_changes(u"o", 10, 30, 400, {"x": 500}, self.MODEL), (70, 50), "by its ink's width")
        self.assertIsNone(sp.reference_changes(u"n", 0, 0, 400, {"x": 500}, self.MODEL), "not in the model")
        self.assertIsNone(sp.reference_changes(u"H", 0, 0, 600, {}, self.MODEL), "no cap height")


class _Box(object):
    def __init__(self, left, right):
        self.l, self.r = left, right

    def left(self):
        return self.l

    def right(self):
        return self.r


class _Shape(object):
    def __init__(self, left, right):
        self.boundingBox = _Box(left, right)


class _Layer(object):
    def __init__(self, width, *boxes):
        self.advanceWidth = width
        self.shapes = [_Shape(*box) for box in boxes]


class OverhangTests(unittest.TestCase):
    def test_a_horn_past_a_tighter_width_is_caught(self):
        horned = _Layer(600, (40, 560), (520, 640))  # O, and a horn 40 units past its width
        self.assertEqual(sp.mark_overhang(horned, -10, -30), 20.0, "sticks out 20 units further once tighter")
        self.assertEqual(sp.mark_overhang(horned, 10, 30), 0.0, "looser: no further")

    def test_each_side_is_weighed_against_itself(self):
        mark = _Layer(500, (40, 460), (-30, 480))  # out 30 units on the left already
        self.assertEqual(sp.mark_overhang(mark, 0, -45), 25.0, "grows out 25 units on the right")

    def test_an_accent_over_the_letter_never_overhangs(self):
        acute = _Layer(500, (40, 460), (200, 300))
        self.assertEqual(sp.mark_overhang(acute, -20, -40), 0.0)

    def test_a_zero_width_mark_is_placed_by_its_components_transform(self):
        # (owner's images 144/146: ucircumflexbelow was named as sticking out, its mark well inside its 451
        # units: the mark's box was read in its own units, where a zero-width mark lies left of its origin)
        class Rect(object):
            def __init__(self, left, right):
                self.l, self.r = left, right

            def left(self):
                return self.l

            def right(self):
                return self.r

            def top(self):
                return -230.0

            def bottom(self):
                return -120.0

        class Transform(object):
            def __init__(self, dx, scale=1.0):
                self.x, self.scale = dx, scale

            def m11(self):
                return self.scale

            def m21(self):
                return 0.0

            def dx(self):
                return self.x

        class Component(object):
            isComponent = True

            def __init__(self, name, dx, scale=1.0):
                self.shapeData = type("Data", (), {"componentGlyph": name})()
                self.transform = Transform(dx, scale)
                self.boundingBox = Rect(-300, -100)  # (in its own units, as FontLab may give it)

        layer = _Layer(451, (40, 410))
        layer.shapes.append(Component("circumflexbelowcomb", 425))
        boxes = {"circumflexbelowcomb": Rect(-300, -100)}
        self.assertEqual(sp.mark_overhang(layer, -12, -24, boxes.get), 0.0, "placed at 125 to 325: inside")
        self.assertGreater(sp.mark_overhang(layer, -12, -24), 0.0, "read in its own units: the false warning")
        self.assertEqual(sp.shape_span(layer.shapes[1], boxes.get), (125.0, 325.0))
        mirrored = Component("circumflexbelowcomb", 100, scale=-1.0)
        self.assertEqual(sp.shape_span(mirrored, boxes.get), (200.0, 400.0), "a mirrored mark's corners mapped")
        self.assertEqual(sp.shape_span(mirrored, lambda name: None), (-300.0, -100.0), "unreadable: its own box")
        self.assertEqual(sp.shape_span(_Shape(10, 20), boxes.get), (10.0, 20.0), "a drawn shape: its own box")

    def test_a_glyph_named_in_the_log_opens_between_its_references(self):
        # (the owner could not see the diacritics the log named: each opened alone)
        opened = []
        dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)

        class Fg(object):
            unicode, unicodes = 0x1E77, [0x1E77]

        class Glyph(object):
            isNull, fgGlyph = False, Fg()

            def __init__(self, name):
                self.name = name

        class Package(object):
            @staticmethod
            def findName(name):
                return Glyph(name) if name in (u"ucircumflexbelow", u"n", u"o") else None

            @staticmethod
            def findUnicode(code):
                return Glyph({0x6E: u"n", 0x6F: u"o"}.get(code, u"x")) if code in (0x6E, 0x6F) else None

        class Ak(object):
            pass

        for name in ("glyph_of_link", "main_code", "unichr_", "category", "script_of", "font_glyphs", "html",
                     "linked_glyph_name", "linked_code", "GLYPH_NAME_LINK"):
            setattr(Ak, name, getattr(ak, name) if not callable(getattr(ak, name)) else staticmethod(getattr(ak, name)))
        Ak.show_in_glyph_window = staticmethod(lambda fontlab, text: opened.append(text))
        dialog.ak, dialog.package, dialog.fontlab = Ak(), Package(), None
        dialog.kind_of = lambda ch: None
        self.assertIsNone(dialog.log_link(u"glyphname:ucircumflexbelow"))
        self.assertEqual(opened, [u"/n/n/ucircumflexbelow/n/n/space/o/o/ucircumflexbelow/o/o"])
        self.assertFalse(dialog.log_link(u"glyphname:gone"), "a glyph the font no longer has: left to the log")
        with io.open(sp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            self.assertIn(u"self.log.link_handler = self.log_link", handle.read())


class SpacingTests(unittest.TestCase):
    def test_each_side_takes_what_its_reference_pair_asks(self):
        # T's right side wants 30 units less beside H; its left side 12 more; a's sides beside n
        wants = {(u"T", u"H"): -30, (u"H", u"T"): 12, (u"a", u"n"): 4, (u"n", u"a"): None}
        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500), sp.Spacing(u"a", "a", "lower", 30, 20, 450)]
        sp.suggest_spacing(glyphs, lambda left, right: wants.get((left, right)), ak.kind_character, ak.category)
        t, a = glyphs
        self.assertEqual((t.left_change, t.right_change), (12, -30))
        self.assertEqual((a.left_change, a.right_change), (None, 4))
        self.assertEqual(t.changes(6), (12, -30))
        self.assertEqual(a.changes(6), (0, 0), "4 units is within the tolerance; an unmeasured side stays")
        self.assertTrue(t.listed(6))
        self.assertFalse(a.listed(6))

    def test_references_by_kind(self):
        self.assertEqual(sp.reference_for(ak.kind_character(u"\N{LATIN CAPITAL LETTER O WITH STROKE}"), ak.category), u"H")
        self.assertEqual(sp.reference_for(u"g", ak.category), u"n")
        self.assertEqual(sp.reference_for(u"7", ak.category), u"0")
        self.assertEqual(sp.reference_for(u"?", ak.category), u"n", "punctuation sits among lowercase most")

    def test_other_scripts_take_their_own_references(self):
        vo, small_vo = u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}"
        refs = lambda ch: sp.reference_for(ak.kind_character(ch), ak.category, ak.script_of)
        self.assertEqual(refs(u"\N{ARMENIAN CAPITAL LETTER BEN}"), vo)
        self.assertEqual(refs(u"\N{ARMENIAN SMALL LETTER BEN}"), small_vo)
        self.assertEqual(refs(ak.unichr_(0x1C91)), ak.unichr_(0x1C98), "Mtavruli against Mtavruli in")
        self.assertEqual(refs(u"\N{GEORGIAN LETTER BAN}"), u"\N{GEORGIAN LETTER IN}")
        self.assertEqual(refs(u"\N{HIRAGANA LETTER KA}"), u"\N{KATAKANA LETTER RO}")
        self.assertEqual(refs(u"\N{CYRILLIC CAPITAL LETTER ZHE}"), u"\N{CYRILLIC CAPITAL LETTER EN}")
        self.assertEqual(refs(u"\N{CYRILLIC SMALL LETTER ZHE}"), u"\N{CYRILLIC SMALL LETTER EN}")
        self.assertEqual(refs(u"\N{GREEK CAPITAL LETTER SIGMA}"), u"\N{GREEK CAPITAL LETTER ETA}")
        self.assertEqual(refs(u"\N{GREEK SMALL LETTER LAMDA}"), u"\N{GREEK SMALL LETTER ETA}")
        self.assertEqual(refs(u"\N{DEVANAGARI LETTER KA}"), u"\N{DEVANAGARI LETTER NA}")
        self.assertEqual(refs(u"\N{HEBREW LETTER BET}"), u"\N{HEBREW LETTER HE}")
        self.assertEqual(refs(u"\N{THAANA LETTER BAA}"), u"\N{THAANA LETTER NOONU}")
        for script in ("cyrillic", "greek", "devanagari", "hebrew", "thaana"):
            for straight in sp.SCRIPT_SPACING_REFERENCES[script].values():
                self.assertIn(straight, sp.ROUND_REFERENCES, "each straight reference has its round one")
        self.assertEqual(refs(u"T"), u"H", "Latin as before")
        self.assertEqual(sp.reference_for(u"T", ak.category), u"H", "without script_of: Latin's")
        self.assertEqual(sp.ROUND_REFERENCES[small_vo], u"\N{ARMENIAN SMALL LETTER OH}")
        fixed = sp.fixed_characters(ak)
        for ch in (u"H", small_vo, u"\N{GEORGIAN LETTER ON}", u"\N{HIRAGANA LETTER NO}"):
            self.assertIn(ch, fixed, "a reference is never changed")

    def test_letters_of_every_script_auto_kerning_knows(self):
        class Group(object):
            currentIndex = 0  # Letters

        class Dialog(object):
            group, package = Group(), None

        dialog = Dialog()
        dialog.ak = ak
        characters = getattr(sp.AutoSpacingDialog.characters, "__func__", sp.AutoSpacingDialog.characters)
        letters = characters(dialog)
        for ch in (u"\N{CYRILLIC CAPITAL LETTER ZHE}", u"\N{GREEK SMALL LETTER LAMDA}", u"\N{DEVANAGARI LETTER KA}",
                   u"\N{HEBREW LETTER BET}", u"\N{THAANA LETTER BAA}", u"\N{ARMENIAN SMALL LETTER BEN}", u"T"):
            self.assertIn(ch, letters, "live, Noto Sans listed no Cyrillic or Greek letter under Letters")
        self.assertEqual(len(letters), len(set(letters)), "each once")
        Group.currentIndex = 2  # Letters, figures, and punctuation
        punctuation = characters(dialog)
        self.assertIn(u"\N{HEBREW PUNCTUATION MAQAF}", punctuation)
        self.assertIn(u"\N{DEVANAGARI DANDA}", punctuation)

    def test_references_to_space_by_script(self):
        vo, small_vo, oh = u"\N{ARMENIAN CAPITAL LETTER VO}", u"\N{ARMENIAN SMALL LETTER VO}", u"\N{ARMENIAN SMALL LETTER OH}"
        sides = {u"H": ("H", 50, 50, 700), u"n": ("n", 40, 38, 500), u"o": ("o", 35, 35, 500),
                 vo: ("Vo", 0, 0, 600), small_vo: ("vo", 40, 40, 500), oh: ("oh", 36, 36, 500)}
        self.assertEqual(sp.references_to_space(sides, 1000), [vo, small_vo, oh], "Armenian's capital vo is unspaced")
        sides[vo] = ("Vo", 50, 50, 600)
        self.assertEqual(sp.references_to_space(sides, 1000), [])
        sides[u"n"] = ("n", 0, 2, 500)
        self.assertEqual(sp.references_to_space(sides, 1000), [u"H", u"n", u"o"], "Latin's alone")
        # (owner's image 335: n and o spaced from the corpus without l, ll no longer agreed with nn and oo,
        # and nothing could be spaced after: l is spaced with them)
        sides[u"l"] = ("l", 3, 4, 200)
        self.assertEqual(sp.references_to_space(sides, 1000), [u"H", u"l", u"n", u"o"])

    def test_a_write_that_leaves_the_font_unmeasurable_says_it_once(self):
        # (owner's image 335: "Stopped by an error" with the analysis's own message, then that message again)
        source = io.open(os.path.join(HERE, os.pardir, "spacing", "freelab_auto_spacing.py"), encoding="utf-8").read()
        write = source[source.index(u"except CannotSpace:\n                pass"):]
        self.assertLess(write.index(u"except CannotSpace:"), write.index(u"except Exception as exc:  # what was changed"))

    def test_l_has_a_row_in_the_reference_model(self):
        path = os.path.join(HERE, os.pardir, "spacing", sp.REFERENCE_MODEL_FILE)
        if not os.path.exists(path):
            self.skipTest("the model is not beside this copy of the tests (the Python 2.7 run copies the code)")
        model = sp.load_reference_model(path)
        changes = sp.reference_changes(u"l", 0, 0, 80, {u"x": 500, u"H": 700}, model)
        self.assertIsNotNone(changes, "spaced as the corpus spaces it, or ll stays apart from nn and oo")
        self.assertTrue(all(change > 0 for change in changes))

    def test_changes_settle_in_one_analysis(self):
        # the methods want T's right side 40 units tighter and its left side 30 looser, but each measure
        # closes half of a tightening (halfkern's factor): measured once, T's right side moves 20;
        # spaced again it would ask for 10 more, then 5: the several clicks the list took
        targets = {("T", "right"): -40, ("T", "left"): 30, ("a", "right"): -9}

        def measure_at(moved):
            def measure(left, right):
                glyph, side = (right, "left") if left in u"Hn" else (left, "right")
                if (glyph, side) not in targets:
                    return None
                done = moved.get(glyph, (0, 0))[0 if side == "left" else 1]
                gap = targets[(glyph, side)] - done
                return int(gap * (0.5 if gap < 0 else 1.0))  # (truncated: the same in Python 2 and 3)
            return measure

        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500), sp.Spacing(u"a", "a", "lower", 30, 20, 450)]
        sp.suggest_spacing(glyphs, measure_at({}), ak.kind_character, ak.category)
        t, a = glyphs
        self.assertEqual((t.left_change, t.right_change), (30, -20), "one measure: half of the tightening")
        passes = sp.settle_spacing(glyphs, measure_at, ak.kind_character, ak.category, settle=2)
        self.assertEqual((t.left_change, t.right_change), (30, -38), "measured again until the step is under 2 units")
        self.assertEqual(a.right_change, -7)
        self.assertEqual(passes, 5)
        self.assertEqual(measure_at({"T": (30, -38)})(u"T", u"H"), -1, "the next analysis asks nothing worth listing")
        capped = [sp.Spacing(u"T", "T", "upper", 20, 25, 500)]
        sp.suggest_spacing(capped, measure_at({}), ak.kind_character, ak.category)
        self.assertEqual(sp.settle_spacing(capped, measure_at, ak.kind_character, ak.category, settle=2, passes=2), 2)
        self.assertEqual(capped[0].right_change, -30, "the passes are capped")

    def test_a_side_that_overshoots_takes_half_the_way_back(self):
        def measure_at(moved):
            done = moved.get("T", (0, 0))[1]
            return lambda left, right: (12 if done else -40) if left == u"T" else None  # past its target after a step
        glyphs = [sp.Spacing(u"T", "T", "upper", 20, 25, 500)]
        sp.suggest_spacing(glyphs, measure_at({}), ak.kind_character, ak.category)
        self.assertEqual(sp.settle_spacing(glyphs, measure_at, ak.kind_character, ak.category, settle=2), 2)
        self.assertEqual(glyphs[0].right_change, -34, "-40, then half of the 12 back: it settles between")
        self.assertIsNone(glyphs[0].left_change, "an unmeasured side stays unmeasured")

    def test_apply_note_says_what_one_click_took(self):
        self.assertEqual(sp.apply_note(1, 0, 6), u"")
        self.assertEqual(sp.apply_note(2, 1, 6),
                         u"It took 2 passes: measured again after spacing, 1 glyph still had a side 6 units or more off, "
                         u"and was spaced again (the measuring's pixels round each change a little).")
        self.assertIn(u"the other 20 glyphs measured against them again", sp.apply_note(1, 0, 6, 20))

    def test_composites_follow_their_base(self):
        composites = {"eacute": ("e", ["acute"]), "ecircumflexacute": ("ecircumflex", ["acute"]),
                      "ecircumflex": ("e", ["circumflex"]), "f_e": ("f", ["e"]), "aacute": ("a", ["acute"])}
        moves = sp.composite_moves(composites, {"e": (5, -3), "f": (2, 2)})
        self.assertEqual(moves["eacute"], (5, 2), "its accent moves with the e's outline; its width follows")
        self.assertEqual(moves["ecircumflexacute"], (5, 2), "built on a composite that follows")
        self.assertIsNone(moves["f_e"], "two of its letters changed: left for a look")
        self.assertNotIn("aacute", moves)


class TableTests(unittest.TestCase):
    """The owner: "Maybe this table should be aligned in terms of layout with the other ones?" The glyph
    drawn from the font beside its character, its name, its code point, then its numbers."""

    def dialog(self):
        dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)  # (its window needs FontLab: its rows do not)
        dialog.ak = ak
        return dialog

    def test_a_rows_cells(self):
        s = sp.Spacing(u"\N{LATIN CAPITAL LETTER A WITH GRAVE}", u"Agrave", "upper", 12.4, 30, 600)
        s.left_change, s.right_change = -8, 0
        texts = self.dialog().row_texts(s, 6)
        self.assertEqual(texts, [u"\N{LATIN CAPITAL LETTER A WITH GRAVE}", u"Agrave", u"U+00C0", u"12", u"-8", u"30",
                                 u"0", u"592"])
        self.assertEqual(len(texts), len(sp.AutoSpacingDialog.COLUMNS))
        s.reference = True
        self.assertEqual(self.dialog().row_texts(s, 6)[1], u"Agrave (reference)", "said in its name's cell")

    def test_the_columns_match_the_other_tools(self):
        self.assertEqual(sp.AutoSpacingDialog.COLUMNS[:3], ("Glyph", "Name", "Unicode"))
        self.assertEqual([sp.AutoSpacingDialog.COLUMNS[c] for c in sp.AutoSpacingDialog.NUMBERS],
                         ["Left now", "Left change", "Right now", "Right change", "Width"], "the numbers, right-aligned")
        self.assertEqual(ak.glyph_icon_size(), (int(ak.GLYPH_ICON_SIZE * 1.6), int(ak.GLYPH_ICON_SIZE * 1.45)))
        self.assertEqual(ak.unicode_label(0xC0), u"U+00C0")
        self.assertEqual(ak.unicode_label(0x1F600), u"U+1F600")
        self.assertEqual(ak.unicode_label(None), u"")

    def test_a_closed_font_empties_the_window(self):
        dialog = self.dialog()
        runs = []
        dialog.run = lambda: runs.append(1)
        dialog.spaced = [u"A"]
        dialog.font_changed()
        self.assertEqual((runs, dialog.spaced), ([1], []), "measured anew (or the no-font line), nothing left to check")


class ChoiceAndCheckTests(unittest.TestCase):
    def source(self):
        import io
        with io.open(sp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            return handle.read()

    def test_the_dropdown_starts_on_everything(self):
        # (owner's report 143)
        self.assertEqual(sp.GROUPS[sp.default_group()], ("everything", "Everything"))
        source = self.source()
        self.assertLess(source.index(u"self.group.setCurrentIndex(default_group())"),
                        source.index(u'self.group.connect("currentIndexChanged(int)"'), "set before it is heard")

    def test_check_all_and_check_none_say_how_many(self):
        # (owner's report 118: these buttons left no line in the log)
        class Item(object):
            def __init__(self, state):
                self.state = state

            def checkState(self, column):
                return self.state

            def setCheckState(self, column, state):
                self.state = state

            def isHidden(self):
                return False

            def parent(self):
                return None

        items = [Item(0), Item(2), Item(0)]
        dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)
        dialog.ak, logged = ak, []
        dialog.tree = type("Tree", (), {"topLevelItemCount": 3, "topLevelItem": lambda tree, row: items[row]})()
        dialog.log = type("Log", (), {"add": lambda log, text, level="info": logged.append(text)})()
        dialog.update_buttons = lambda: None
        old = ak._qt
        ak._qt = lambda: (type("Core", (), {"Qt": type("Qt", (), {"Checked": 2, "Unchecked": 0})}), None)
        self.addCleanup(lambda: setattr(ak, "_qt", old))
        dialog.check_all(True)
        # (Tick, not Check, for check boxes: owner's image 261)
        self.assertEqual(logged, [u"<i>Tick all</i> ticked <b>2 glyphs</b>."])
        dialog.check_all(False)
        self.assertEqual(logged[-1], u"<i>Tick none</i> unticked <b>3 glyphs</b>.")
        self.assertEqual([item.state for item in items], [0, 0, 0])
        self.assertIn(u"layout = self.ak.window_layout(dialog)", self.source(), "its window scrolls on a small screen")


class HistoryFailureTests(unittest.TestCase):
    """Review of 2026-11-15: a failed History record before the write let Auto Spacing write anyway, and a
    failed step after it was followed by "Edit > Undo takes it back"."""

    def setUp(self):
        self.saved = getattr(sys, "_freelab_history", None)
        sys._freelab_history = None
        self.addCleanup(lambda: setattr(sys, "_freelab_history", self.saved))
        self.busy_calls = fake_busy(self)

    def dialog(self, refuse_before, refuse_after):
        steps = []

        class Items(object):
            def notifyChangesApplied(self, title, objects, recursive):
                if (refuse_before if title.endswith(u"(before)") else refuse_after):
                    raise RuntimeError("History refused")
                steps.append(title)

            def notifyPackageContentUpdated(self, key):
                pass

        class Package(object):
            master, glyphsCount, path, id = "Regular", 1, u"a.vfc", 21
            fgPackage = type("Fg", (), {"id": 21})()

            def currentHistoryState(self):
                return 0

            def initialHistoryState(self):
                return 0

            def setFlag(self, flag, value):
                pass

        dialog = sp.AutoSpacingDialog.__new__(sp.AutoSpacingDialog)
        dialog.ak, dialog.busy, dialog.package, dialog.master = ak, False, Package(), "Regular"
        dialog.fontlab = type("FontLab", (), {"flItems": Items()})()
        dialog.logged, dialog.writes = [], []
        dialog.log = type("Log", (), {"add": lambda _, text, kind="info": dialog.logged.append((kind, text))})()
        dialog.harvest = dialog.run = lambda: None
        dialog.current_font = lambda: dialog.package
        dialog.tolerance = type("Box", (), {"value": 6})()
        dialog.follow = type("Box", (), {"checked": False})()
        row = sp.Spacing(u"T", "T", "upper", 20, 25, 500)
        row.checked = True
        dialog.listed = [row]

        def write_spacings(rows, tolerance, totals):
            dialog.writes.append([s.name for s in rows])
            totals["T"] = (0, -5)
            return [], 0
        dialog.write_spacings = write_spacings
        return dialog, steps

    def test_nothing_is_written_when_the_font_cannot_be_recorded_first(self):
        dialog, steps = self.dialog(refuse_before=True, refuse_after=False)
        dialog.apply()
        self.assertEqual(dialog.writes, [], "no glyph changed")
        self.assertEqual(steps, [])
        self.assertEqual([kind for kind, _ in dialog.logged], ["error"])
        self.assertIn(u"Nothing was changed", dialog.logged[0][1])

    def test_a_step_not_recorded_promises_no_undo(self):
        dialog, steps = self.dialog(refuse_before=False, refuse_after=True)
        dialog.apply()
        self.assertEqual(dialog.writes, [["T"]])
        self.assertFalse(any(u"Undo</i> (or" in text for _, text in dialog.logged), dialog.logged)
        errors = [text for kind, text in dialog.logged if kind == "error"]
        self.assertEqual(len(errors), 1, dialog.logged)
        self.assertIn(u"cannot take it back", errors[0])

    def test_a_recorded_write_promises_undo(self):
        dialog, steps = self.dialog(refuse_before=False, refuse_after=False)
        dialog.apply()
        self.assertEqual(steps, [u"FreeLab Auto Spacing (before)", u"FreeLab Auto Spacing"])
        self.assertTrue(any(u"<i>Edit &gt; Undo</i> (or the <i>History</i> panel) takes it back." in text
                            for _, text in dialog.logged), dialog.logged)
        self.assertEqual([kind for kind, _ in dialog.logged if kind == "error"], [])
        # (under the top row's progress, never stoppable: one History step)
        self.assertEqual(self.busy_calls[0][0], "start")
        self.assertEqual(self.busy_calls[-1][0], "end")
        self.assertFalse(any(stoppable for name, _, _, stoppable in self.busy_calls if name in ("start", "progress")))

    def test_a_write_that_raises_still_ends_its_progress(self):
        dialog, steps = self.dialog(refuse_before=False, refuse_after=False)

        def write_spacings(rows, tolerance, totals):
            raise RuntimeError("FontLab refused")
        dialog.write_spacings = write_spacings
        dialog.apply()
        self.assertEqual(self.busy_calls[-1][0], "end")
        self.assertFalse(dialog.busy)
        self.assertTrue(any(u"FontLab refused" in text for kind, text in dialog.logged if kind == "error"))


class WordingTests(unittest.TestCase):
    """The owner's rules for interface texts, read from the script (its dialog needs FontLab)."""

    def source(self):
        import io
        with io.open(sp.__file__.replace(".pyc", ".py"), encoding="utf-8") as handle:
            return handle.read()

    def test_no_dash_or_dot_between_data(self):
        escaped = [u" \\" + code + u" " for code in (u"N{EM DASH}", u"N{MIDDLE DOT}", u"u2014", u"u00b7", u"xb7")]
        for mark in escaped + [u" \N{EM DASH} ", u" \N{MIDDLE DOT} "]:
            self.assertNotIn(mark, self.source())

    def test_a_check_box_sentence_ends_with_a_period(self):
        # (owner's image 324: a tick's caption that is a sentence takes its period)
        self.assertIn(u"QCheckBox(\"Glyphs built from components follow the glyphs they are built on.\")", self.source())

    def test_the_units_box_follows_its_number(self):
        self.assertNotIn(u"setSuffix(", self.source(), "ak.counted_suffix sets it: 1 unit, 2 units")
        self.assertIn(u"counted_suffix(self.tolerance, u\"unit\")", self.source())

    def test_the_composites_note_says_none_or_hides(self):
        # (owner's image 188: "0 glyphs built from components follow the listed glyphs.")
        self.assertEqual(sp.composites_text(0, 0), u"", "hidden: nothing to say")
        self.assertEqual(sp.composites_text(1, 0), u"1 glyph built from components follows the listed glyphs.")
        self.assertEqual(sp.composites_text(3, 0), u"3 glyphs built from components follow the listed glyphs.")
        self.assertEqual(sp.composites_text(0, 2), u"No glyph built from components follows the listed glyphs; 2 built "
                                                   u"on two of them are left as they are.")
        self.assertEqual(sp.composites_text(2, 1), u"2 glyphs built from components follow the listed glyphs; 1 built "
                                                   u"on two of them is left as it is.")
        self.assertNotIn(u"QApplication.processEvents", self.source(), "the top row's progress lets events through")

    def test_the_options_row_holds_the_tick_and_analyze_inline(self):
        # (owner's images 254 and 262: the tick above the list beside "List changes of at least"; Analyze at the
        # end of its options, not at the window's right edge; "Show: [Everything]", brief's captions)
        source = self.source()
        init = source.split(u"class AutoSpacingDialog")[1].split(u"\n    def current_font")[0]
        row = init.split(u"row = QtGui.QHBoxLayout()")[1].split(u"layout.addLayout(row)")[0]
        order = [row.index(text) for text in (u'QLabel("Show:")', u"row.addWidget(self.group)",
                                              u'QLabel("List changes of at least")', u"row.addWidget(self.tolerance)",
                                              u'sentence_end(row)', u"row.addWidget(self.follow)",
                                              u"row.addWidget(self.analyze_button)", u"row.addStretch(1)")]
        self.assertEqual(order, sorted(order), "left-aligned: the stretch after Analyze")
        self.assertEqual(row.count(u"addStretch"), 1)
        self.assertNotIn(u"layout.addWidget(self.follow)", init, "no longer above the log")
        self.assertIn(u"layout.addWidget(self.ak.header_separator())", init)
        self.assertLess(init.index(u"layout.addWidget(self.composites_note)"), init.index(u"row = QtGui.QHBoxLayout()"),
                        "the note in the header, not under the list")

    def test_the_previews_have_quiet_captions_and_a_line_between(self):
        # (brief: every preview caption the shared preview_caption, a line between two previews side by side)
        source = self.source()
        self.assertIn(u"self.ak.preview_caption(caption)", source)
        self.assertEqual(source.count(u"self.ak.separator(vertical=True)"), 1)
        picture = source.split(u"    def picture(")[1].split(u"\n    def ")[0]
        self.assertNotIn(u"drawText", picture, "the caption is the label over the picture")

    def test_tick_not_check(self):
        # (owner's image 261)
        source = self.source()
        for old in (u'"Check all"', u'"Check none"', u"Space checked glyphs", u"Checks restored"):
            self.assertNotIn(old, source)
        self.assertEqual(sp.APPLY_BUTTON, u"Space ticked glyphs")
        # (a tool named in the log is a link that opens it: owner's image 220)
        self.assertIn(u'ak.tool_link(u"Auto Kerning")', source)

    def test_the_status_counts_right_at_zero_one_and_two(self):
        status = lambda listed, drawn: sp.spacing_status(listed, drawn, 6)
        self.assertEqual(status(0, 0), u"No drawn glyph of this choice to space.")
        self.assertEqual(status(0, 1), u"The only drawn glyph does not have a side 6 units or more from the suggestion.")
        self.assertEqual(status(1, 1), u"The only drawn glyph has a side 6 units or more from the suggestion. Nothing "
                                       u"changes until you click Space ticked glyphs.")
        self.assertEqual(status(0, 2), u"None of the 2 drawn glyphs has a side 6 units or more from the suggestion.")
        self.assertEqual(status(1, 2), u"1 of 2 drawn glyphs has a side 6 units or more from the suggestion. Nothing "
                                       u"changes until you click Space ticked glyphs.")
        self.assertEqual(sp.spacing_status(1200, 13932, 1, 3, ak.b, ak.i),
                         u"<b>1,200 of 13,932 drawn glyphs</b> have a side <b>1 unit</b> or more from the "
                         u"suggestion. Nothing changes until you click <i>Space ticked glyphs</i>. Each change was "
                         u"measured again with it made, until the changes settled (<b>3 passes</b>): halfkern closes "
                         u"half of a tightening at a time, so one measure leaves part of it.")

    def test_the_log_counts(self):
        self.assertIn(u"1 glyph still had a side 1 unit or more off, and was spaced again", sp.apply_note(2, 1, 1))
        self.assertIn(u"2 glyphs still had a side 2 units or more off, and were spaced again", sp.apply_note(3, 2, 2))
        self.assertEqual(sp.apply_note(1, 0, 2), u"")

    def test_counts_are_bold_with_their_nouns(self):
        # Round 3's convention 18 (owner's images 297 and 301): a count bold together with its noun, a number
        # with no noun of its own bold alone; never only the number when its noun follows
        self.assertEqual(sp.apply_note(3, 2, 2, 20, ak.b),
                         u"The references were spaced first, and the other <b>20 glyphs</b> measured against them "
                         u"again: their changes differ from the list's. It took <b>3 passes</b>: measured again after "
                         u"spacing, <b>2 glyphs</b> still had a side <b>2 units</b> or more off, and were spaced again "
                         u"(the measuring's pixels round each change a little).")
        self.assertEqual(sp.composites_text(3, 2, ak.b), u"<b>3 glyphs</b> built from components follow the listed "
                                                         u"glyphs; <b>2</b> built on two of them are left as they are.")
        self.assertEqual(sp.composites_text(0, 1, ak.b), u"No glyph built from components follows the listed glyphs; "
                                                         u"<b>1</b> built on two of them is left as it is.")
        line = sp.unspaced_line([u"H", u"n"], 412, ak.b, ak.i)
        self.assertIn(u"<b>H, n</b> come first, unticked, spaced as <b>412 open-licensed families</b> space theirs.",
                      line)
        self.assertIn(u"then click <i>Analyze</i>:", line)
        self.assertIn(u"as 1 open-licensed family spaces theirs.", sp.unspaced_line([u"H"], 1))
        source = self.source()
        self.assertIn(u"composites_text(following, left_out, self.ak.b)", source, "the note under the font line, bold")
        self.assertIn(u"measured_again if not unread else 0, ak.b)", source, "the log's note, bold")


if __name__ == "__main__":
    unittest.main()
