"""Tests of FreeLab's Quick Overlay: the glyphs typed read, found in the font, with the glyphs their components
draw, and copied into a new font named in the family. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "compare"))
import freelab_quick_overlay as qo  # noqa: E402


class TextTests(unittest.TestCase):
    def test_characters_and_names_are_read_in_order(self):
        self.assertEqual(qo.parse_glyph_text(u"Ag /a.alt/b.sc 1"),
                         [("code", 0x41), ("code", 0x67), ("name", u"a.alt"), ("name", u"b.sc"), ("code", 0x31)])

    def test_a_double_slash_is_the_slash_and_a_pair_one_character(self):
        self.assertEqual(qo.parse_glyph_text(u"//"), [("code", 0x2F)])
        self.assertEqual(qo.parse_glyph_text(u"\U0001F600" if sys.maxunicode > 0xFFFF else u"\ud83d\ude00"),
                         [("code", 0x1F600)])

    def test_the_fonts_glyphs_found_each_once_and_what_it_lacks_said(self):
        names = set([u"A", u"g", u"a.alt"])
        by_code = {0x41: u"A", 0x67: u"g"}
        chosen, missing = qo.resolve(qo.parse_glyph_text(u"AgA/a.alt/zz \u00e9"), names, by_code)
        self.assertEqual(chosen, [u"A", u"g", u"a.alt"])
        self.assertEqual(missing, [u"/zz", u"U+00E9"])


class FlagTests(unittest.TestCase):
    def test_the_fonts_flags_listed_fontlabs_colors_first_with_their_counts(self):
        marks = [0, 241, 1, 1, 0, 61, 241, 1]
        self.assertEqual(qo.flag_choices(marks), [(1, u"Red (3 glyphs)", 3), (241, u"Blue (2 glyphs)", 2),
                                                  (61, u"Hue 60 (1 glyph)", 1)])
        self.assertEqual(qo.flag_choices([0, 0]), [], "no flag: nothing to choose")

    def test_a_flags_glyphs_in_the_fonts_order(self):
        marks = [(u"B", 1), (u"A", 0), (u"C", 1), (u"D", 241)]
        self.assertEqual(qo.flagged(marks, 1), [u"B", u"C"])
        self.assertEqual(qo.flagged(marks, 0), [], "none chosen")


class DialogTests(unittest.TestCase):
    """The owner's images 171 and 172: the note formatted as the other tools' (the font's name bold, FontLab's command
    in italics), the flags' line a choice of its own, and Overlay grayed out while there is nothing to overlay."""

    def test_the_note_names_the_font_in_bold_and_the_command_in_italics(self):
        note = qo.note_text(u"Sarabun")
        self.assertTrue(note.startswith(u"<i>Overlay Fonts</i> opened"))
        self.assertIn(u"glyphs of <b>Sarabun</b>, with", note)
        self.assertIn(u"<b>A &amp; B</b>", qo.note_text(u"A & B"), "the name made safe in rich text")
        self.assertIn(u"of the current font,", qo.note_text(None))

    def test_the_flags_line_stands_alone(self):
        self.assertEqual(qo.FLAG_PROMPT, u"Choose flagged glyphs:")

    def test_overlay_only_with_something_to_overlay(self):
        self.assertFalse(qo.can_overlay(u"", 0))
        self.assertFalse(qo.can_overlay(u"   ", 0), "spaces are nothing")
        self.assertTrue(qo.can_overlay(u"Ag", 0))
        self.assertTrue(qo.can_overlay(u"", 1), "a flag chosen alone")


class ComponentTests(unittest.TestCase):
    def test_the_glyphs_components_draw_come_first(self):
        parts = {u"Aacute": [u"A", u"acutecomb"], u"acutecomb": [], u"A": [], u"Ccedilla": [u"C", u"cedilla"],
                 u"cedilla": [u"cedillacomb"], u"C": [], u"cedillacomb": []}
        order = qo.with_components([u"Aacute", u"A", u"Ccedilla"], lambda name: parts.get(name, []))
        self.assertEqual(order, [u"A", u"acutecomb", u"Aacute", u"C", u"cedillacomb", u"cedilla", u"Ccedilla"])

    def test_a_loop_is_broken(self):
        parts = {u"a": [u"b"], u"b": [u"a"]}
        self.assertEqual(qo.with_components([u"a"], lambda name: parts.get(name, [])), [u"b", u"a"])


class FakeCalls(object):
    """FontLab's side, recorded: the source's glyphs as {name: (width, components, codes)}."""

    def __init__(self, glyphs, refuse=()):
        self.glyphs = glyphs
        self.refuse = set(refuse)
        self.made = {}
        self.log = []
        self.names = None
        self.metrics = {}

    def master(self, package):
        return u"Regular"

    def family(self, package):
        return u"Sample Sans"

    def upm(self, package):
        return 1000

    def new_package(self):
        return "new"

    def masters(self, package):
        return [u"Regular"] if package == "new" else [u"Regular"]

    def rename_master(self, package, old, new):
        self.log.append(("rename", old, new))

    def set_upm(self, package, upm):
        self.log.append(("upm", upm))

    def set_names(self, package, family, style):
        self.names = (family, style)

    def set_info_family(self, package, family, style):
        pass

    def show_package(self, package):
        self.log.append(("shown",))

    def new_glyph(self, package, name):
        if name in self.refuse:
            raise RuntimeError("refused")
        self.made[name] = {"components": None, "width": None, "codes": None, "contours": False}
        return name

    def new_layer(self, glyph, master):
        return glyph

    def init_layer(self, package, layer):
        pass

    def layer(self, package, name, master):
        return name if name in self.glyphs else None

    def width(self, layer):
        return self.glyphs[layer][0]

    def components(self, layer):
        return [(base, None) for base in self.glyphs[layer][1]]

    def set_components(self, package, target, parts, width):
        for base, _ in parts:
            assert base in self.made, "a component made before its glyph"
        self.made[target]["components"] = [base for base, _ in parts]

    def copy_contours(self, layer, target):
        self.made[target]["contours"] = True

    def copy_anchors(self, layer, target):
        pass

    def set_width(self, target, width):
        self.made[target]["width"] = width

    def find_glyph(self, package, name):
        return name if name in self.made else None

    def codes_of(self, package, name):
        return list(self.glyphs[name][2])

    def set_codes(self, glyph, codes):
        self.made[glyph]["codes"] = codes

    def update_glyph(self, glyph):
        pass

    def metric(self, package, attribute):
        return {"ascender_value": 750.0, "descender_value": -250.0}.get(attribute, 0.0)

    def set_metric(self, package, attribute, value):
        self.metrics[attribute] = value

    def rebuild_maps(self, package):
        self.log.append(("maps",))

    def glyphs_shown(self, package):
        self.log.append(("glyphs shown",))


class BuildTests(unittest.TestCase):
    GLYPHS = {u"A": (600, [], [0x41]), u"acutecomb": (0, [], [0x301]), u"Aacute": (600, [u"A", u"acutecomb"], [0xC1]),
              u"g": (520, [], [0x67])}

    def test_the_new_font_holds_the_glyphs_as_the_source_has_them_named_in_its_family(self):
        calls = FakeCalls(self.GLYPHS)
        order = qo.with_components([u"Aacute", u"g"], lambda name: [b for b, _ in calls.components(name)])
        package, refused = qo.build_overlay_font(calls, "source", order)
        self.assertEqual(package, "new")
        self.assertEqual(refused, [])
        self.assertEqual(calls.names, (u"Sample Sans", qo.STYLE), "named in the family: Add Family Members lists it")
        self.assertEqual(sorted(calls.made), [u"A", u"Aacute", u"acutecomb", u"g"])
        self.assertEqual(calls.made[u"Aacute"]["components"], [u"A", u"acutecomb"])
        self.assertEqual(calls.made[u"g"]["width"], 520)
        self.assertEqual(calls.made[u"Aacute"]["codes"], [0xC1])
        self.assertTrue(calls.made[u"g"]["contours"])
        self.assertEqual(calls.metrics["ascender_value"], 750.0)
        self.assertIn(("upm", 1000), calls.log)
        self.assertEqual(calls.log[-2:], [("maps",), ("glyphs shown",)])

    def test_what_fontlab_refuses_is_said_and_the_rest_made(self):
        calls = FakeCalls(self.GLYPHS, refuse=[u"g"])
        package, refused = qo.build_overlay_font(calls, "source", [u"A", u"g"])
        self.assertIn(u"A", calls.made)
        self.assertEqual(refused, [u"Glyphs not added: g."])


if __name__ == "__main__":
    unittest.main()
