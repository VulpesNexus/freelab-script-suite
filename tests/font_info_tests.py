# -*- coding: utf-8 -*-
"""Tests of the font info FreeLab keeps in step with its writes (checks/freelab_font_info.py), and of Auto
Kerning's before_changes and notify_changed asking for it. Valid Python 2.7 and Python 3."""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "checks"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
import freelab_font_info as fi  # noqa: E402
import freelab_auto_kerning as ak  # noqa: E402

LATIN_1_LETTERS = [code for code in range(0xC0, 0x100) if code not in (0xD7, 0xF7)] + [0x152, 0x153, 0x160, 0x161,
                                                                                      0x178, 0x17D, 0x17E]
ASCII = list(range(0x20, 0x7F))
HANGUL = list(range(0xAC00, 0xD7A4))


class Info(object):
    """fgPackage.info's coverage and Win fields, as FontLab hands them to a script (lists of longs, floats)."""

    def __init__(self, ranges=(), pages=(), ascent=900.0, descent=250.0):
        self.openTypeOS2UnicodeRanges, self.openTypeOS2CodePageRanges = list(ranges), list(pages)
        self.openTypeOS2WinAscent, self.openTypeOS2WinDescent = ascent, descent


class RangeTests(unittest.TestCase):

    def test_a_bit_for_each_block_with_a_character(self):
        self.assertEqual(fi.unicode_bits([0x41, 0xE9, 0x101]), set([0, 1, 2]))
        self.assertEqual(fi.unicode_bits([0xAC00]), set([56]), "Hangul Syllables")
        self.assertEqual(fi.unicode_bits([0x1D00]), set([4]), "Phonetic Extensions: IPA Extensions' bit")

    def test_past_the_bmp_the_non_plane_0_bit_too(self):
        self.assertEqual(fi.unicode_bits([0x1F600]), set([57]), "an emoji: no block of its own among the ranges")
        self.assertEqual(fi.unicode_bits([0x1D11E]), set([57, 88]), "Musical Symbols")

    def test_a_code_point_between_blocks_sets_nothing(self):
        self.assertEqual(fi.unicode_bits([0x1C90]), set(), "Georgian Extended: not among OpenType's ranges")

    def test_names(self):
        self.assertEqual(fi.range_name(56), u"Hangul Syllables")
        self.assertEqual(fi.page_name(0), u"Latin 1 (1252)")
        self.assertEqual(fi.page_name(21), u"Korean Johab (1361)")


class CodePageTests(unittest.TestCase):

    def test_latin_1_needs_its_letters_and_ascii(self):
        self.assertIn(0, fi.code_page_bits(ASCII + LATIN_1_LETTERS))
        self.assertNotIn(0, fi.code_page_bits(ASCII + LATIN_1_LETTERS[1:]), "one letter short")
        self.assertNotIn(0, fi.code_page_bits(LATIN_1_LETTERS), "no ASCII")

    def test_symbols_and_the_florin_are_not_required(self):
        letters = dict(fi.page_letters())[0]
        for code in (0x20AC, 0xA9, 0x2122, 0x192, 0xAA, 0xBA, 0xB5):  # (euro, copyright, TM, florin, ordinals, micro)
            self.assertNotIn(code, letters)

    def test_greek_needs_greek_letters_not_its_symbols(self):
        letters = dict(fi.page_letters())[3]
        self.assertIn(0x3A9, letters, "Omega")
        self.assertNotIn(0x385, letters, "dialytika tonos: a symbol")

    def test_east_asian_pages_by_their_first_level(self):
        pages = dict(fi.page_letters())
        self.assertEqual(len(pages[19] - set(ASCII)), 2350, "KS X 1001's Hangul syllables")
        self.assertEqual(len(pages[21] - set(ASCII)), 11172, "every Hangul syllable")
        self.assertIn(0x3042, pages[17], "hiragana a")
        self.assertIn(0x4E9C, pages[17], "亜, JIS level 1's first kanji")
        self.assertNotIn(0x5F0C, pages[17], "弌, JIS level 2's first: not required")
        self.assertIn(0x554A, pages[18], "啊, GB 2312 level 1's first hanzi")
        self.assertIn(0x4E00, pages[20], "一, Big5's first")

    def test_hangul_fonts(self):
        self.assertEqual(fi.code_page_bits(ASCII + HANGUL) & set([19, 21]), set([19, 21]))
        self.assertEqual(fi.code_page_bits(ASCII + HANGUL[:-1]) & set([19, 21]), set([19]), "one short of Johab")

    def test_legacy_pages_are_not_managed(self):
        self.assertTrue(set([29, 30, 31, 48, 63]).isdisjoint(fi.managed_pages()))


class ChangedBitsTests(unittest.TestCase):

    def test_only_what_the_write_changed(self):
        self.assertEqual(fi.changed_bits([0, 5], before=[0, 1], after=[0, 1, 56]), {56: True})
        self.assertEqual(fi.changed_bits([0, 1, 56], before=[0, 56], after=[0]), {56: False})

    def test_hand_set_bits_stay(self):
        self.assertEqual(fi.changed_bits([0, 9], before=[0], after=[0]), {}, "bit 9 set by hand, nothing it covers")
        self.assertEqual(fi.changed_bits([0], before=[0, 1], after=[0, 1]), {}, "bit 1 cleared by hand: left so")

    def test_a_bit_declared_already_needs_no_change(self):
        self.assertEqual(fi.changed_bits([0, 56], before=[0], after=[0, 56]), {})


class ApplyTests(unittest.TestCase):

    def setUp(self):
        fi.forget()

    def tearDown(self):
        fi.forget()

    def test_hangul_built_sets_its_range_and_code_pages(self):
        info = Info(ranges=[0, 1], pages=[0])
        before, after = set(ASCII + LATIN_1_LETTERS), set(ASCII + LATIN_1_LETTERS + HANGUL)
        changes = fi.apply_bits(info, 7, fi.coverage(before), fi.coverage(after))
        self.assertEqual(info.openTypeOS2UnicodeRanges, [0, 1, 56])
        self.assertEqual(info.openTypeOS2CodePageRanges, [0, 19, 21])
        self.assertEqual(fi.changes_text(changes), u"Unicode ranges (added Hangul Syllables); code pages (added Korean "
                                                   u"Wansung (949), Korean Johab (1361))")
        self.assertFalse(fi.recorded(7), "nothing to follow: FontLab's History takes the bits back")

    def test_nothing_changed_nothing_recorded(self):
        info = Info(ranges=[0], pages=[])
        self.assertEqual(fi.apply_bits(info, 8, fi.coverage(ASCII), fi.coverage(ASCII + [0x42])), [])
        self.assertFalse(fi.recorded(8))

    def test_win_raised_to_the_ink_never_lowered(self):
        info = Info(ascent=900.0, descent=250.0)
        changes = fi.apply_win(info, 9, [(-120.0, 950.2), (-300.0, 700.0)], [u"Aringacute"])
        self.assertEqual((info.openTypeOS2WinAscent, info.openTypeOS2WinDescent), (951.0, 300.0))
        self.assertEqual(fi.changes_text(changes), u"Win ascent (900 to 951); Win descent (250 to 300)")
        info = Info(ascent=900.0, descent=250.0)
        self.assertEqual(fi.apply_win(info, 10, [(-100.0, 800.0)], [u"a"]), [], "within: unchanged")
        self.assertEqual(fi.apply_win(info, 10, [], [u"space"]), [], "no ink")

    def test_win_values_not_set_stay_unset(self):
        info = Info(ascent=0.0, descent=None)
        self.assertEqual(fi.apply_win(info, 11, [(-300.0, 950.0)], [u"Aringacute"]), [],
                         "0 reads as not set: one glyph's ink would clip the others")
        self.assertEqual((info.openTypeOS2WinAscent, info.openTypeOS2WinDescent), (0.0, None))


class FollowTests(unittest.TestCase):
    """FontLab's History takes back the ranges and code pages, not the Win values: after an undo, follow puts
    the Win values FreeLab raised back in step with the glyphs they were raised for."""

    def setUp(self):
        fi.forget()
        self.info = Info(ranges=[0], pages=[0])
        self.before = set(ASCII + LATIN_1_LETTERS)
        fi.apply_bits(self.info, 1, fi.coverage(self.before), fi.coverage(self.before | set(HANGUL)))
        fi.apply_win(self.info, 1, [(-100.0, 980.0)], [u"uniAC00"])
        self.extents = {u"uniAC00": [(-100.0, 980.0)]}

    def tearDown(self):
        fi.forget()

    def extent_of(self, names):
        return [extent for name in names for extent in self.extents.get(name, [])]

    def test_undo_takes_the_win_value_back_and_redo_raises_it_again(self):
        self.extents = {}  # (undone: the glyph is gone)
        changes = fi.follow(self.info, 1, self.extent_of)
        self.assertEqual(self.info.openTypeOS2WinAscent, 900.0, "back to the value before FreeLab raised it")
        self.assertEqual([c.field for c in changes], [fi.INFO_WIN_ASCENT])
        self.assertEqual(self.info.openTypeOS2UnicodeRanges, [0, 56], "the History's to take back, not follow's")
        self.extents = {u"uniAC00": [(-100.0, 980.0)]}
        fi.follow(self.info, 1, self.extent_of)
        self.assertEqual(self.info.openTypeOS2WinAscent, 980.0)

    def test_the_bits_are_not_recorded(self):
        fi.forget()
        fi.apply_bits(self.info, 2, fi.coverage(self.before), fi.coverage(self.before | set(HANGUL)))
        self.assertFalse(fi.recorded(2), "FontLab's History takes them back with the write (live)")

    def test_a_value_changed_by_hand_since_is_left(self):
        self.info.openTypeOS2WinAscent = 1000.0
        self.extents = {}
        self.assertEqual(fi.follow(self.info, 1, self.extent_of), [])
        self.assertEqual(self.info.openTypeOS2WinAscent, 1000.0, "set by hand: left")
        self.assertFalse(fi.recorded(1), "and forgotten")

    def test_a_follow_is_needed_only_when_the_glyphs_may_have_changed(self):
        fi.note_mark(1, 500, 4, wrote=True)
        self.assertFalse(fi.needs_follow(1, 500, 4))
        self.assertFalse(fi.needs_follow(1, 500, 5), "a later edit, the glyph count the same")
        self.assertTrue(fi.needs_follow(1, 499, 5), "a glyph taken out")
        self.assertTrue(fi.needs_follow(1, 500, 2), "back past FreeLab's write")
        fi.note_mark(1, 500, 2)
        self.assertFalse(fi.needs_follow(1, 500, 1))
        self.assertTrue(fi.needs_follow(1, 500, 4), "forward again: redone")
        self.assertFalse(fi.needs_follow(2, 500, 4), "a font FreeLab never changed the info of")

    def test_a_later_glyph_within_a_raise_keeps_it(self):
        """A raised the Win ascent 900 to 1000; B, built later to 950, raised nothing and was not recorded, so A
        undone took the value back to 900, under B (adversarial review 5). B relies on the raise: recorded with it."""
        fi.forget()
        info = Info(ascent=900.0, descent=250.0)
        fi.apply_win(info, 101, [(-400.0, 1000.0)], [u"A"])
        self.assertEqual(fi.apply_win(info, 101, [(-300.0, 950.0)], [u"B"]), [], "nothing raised")
        fi.apply_win(info, 101, [(-100.0, 850.0)], [u"C"])  # (within the value before the raise: relies on none)
        self.extents = {u"A": [(-100.0, 800.0)], u"B": [(-300.0, 950.0)], u"C": [(-100.0, 850.0)]}
        fi.follow(info, 101, self.extent_of)
        self.assertEqual((info.openTypeOS2WinAscent, info.openTypeOS2WinDescent), (950.0, 300.0),
                         "A redrawn lower: B's ink kept, ascent and descent alike")
        self.extents = {u"C": [(-100.0, 850.0)]}
        fi.follow(info, 101, self.extent_of)
        self.assertEqual((info.openTypeOS2WinAscent, info.openTypeOS2WinDescent), (900.0, 250.0), "both gone: as before")
        self.assertNotIn(u"C", sys._freelab_font_info[101]["win"][fi.INFO_WIN_ASCENT][2])
        # A value changed by hand since FreeLab left it: a later glyph within it is not FreeLab's to record
        info.openTypeOS2WinAscent = 1200.0
        fi.apply_win(info, 101, [(-100.0, 1100.0)], [u"D"])
        self.assertNotIn(u"D", sys._freelab_font_info[101]["win"][fi.INFO_WIN_ASCENT][2])

    def test_every_undo_and_redo_across_successive_writes_follows(self):
        """A redrawn twice, the Win ascent raised 900 to 1000, then to 1100, the glyph count unchanged: a second
        undo, below the last write only, was not followed and left 1000 (adversarial review 6). Each step across
        any of the writes is followed, back and forth."""
        fi.forget()
        info = Info(ascent=900.0, descent=250.0)

        def top(state):
            return 800.0 if state < 2 else 1000.0 if state < 4 else 1100.0

        def write(state):
            fi.apply_win(info, 102, [(-100.0, top(state))], [u"A"])
            fi.note_mark(102, 500, state, wrote=True)

        def move(state):
            if fi.needs_follow(102, 500, state):
                fi.follow(info, 102, lambda names: [(-100.0, top(state))])
            fi.note_mark(102, 500, state)
            return info.openTypeOS2WinAscent

        write(2)
        write(4)
        self.assertEqual(info.openTypeOS2WinAscent, 1100.0)
        steps = [3, 2, 1, 0, 1, 2, 3, 4, 2, 0, 4]  # (one step at a time, back and forth, then several at once)
        self.assertEqual([move(state) for state in steps],
                         [1000.0, 1000.0, 900.0, 900.0, 900.0, 1000.0, 1000.0, 1100.0, 1000.0, 900.0, 1100.0])
        self.assertFalse(fi.needs_follow(102, 500, 5), "a later edit crossing no write: nothing read")


# -- Auto Kerning's writes asking for it --------------------------------------------------------------

class Glyph(object):
    def __init__(self, name, codes):
        self.name, self.unicodes = name, list(codes)
        self.unicode = codes[0] if codes else None
        self.state = 0

    def currentHistoryState(self):
        return self.state

    def initialHistoryState(self):
        return 0

    def update(self):
        pass


class FgPackage(object):
    def __init__(self, key, glyphs, info):
        self.id, self.glyphs, self.info = key, glyphs, info


class Package(object):
    def __init__(self, key, glyphs, info):
        self.name, self.state, self.flags = "font", 0, []
        self.fgPackage = FgPackage(key, glyphs, info)
        self.masters = [u"Regular"]

    @property
    def glyphsCount(self):
        return len(self.fgPackage.glyphs)

    def currentHistoryState(self):
        return self.state

    def initialHistoryState(self):
        return 0

    def setFlag(self, flag, value):
        self.flags.append((flag, value))

    def findName(self, name):
        for glyph in self.fgPackage.glyphs:
            if glyph.name == name:
                return glyph
        return None


class Items(object):
    def __init__(self):
        self.index = 0

    def notifyChangesApplied(self, title, objects, recursive):
        self.index += 1
        for obj in objects if isinstance(objects, list) else [objects]:
            obj.state = self.index

    def notifyPackageContentUpdated(self, key):
        pass


class Log(object):
    def __init__(self):
        self.lines = []

    def add(self, text, kind="info"):
        self.lines.append((kind, text))


class WriteTests(unittest.TestCase):

    def setUp(self):
        fi.forget()
        self.saved = getattr(sys, "_freelab_history", None), ak.master_extents, sys.modules.get(ak.FONT_INFO_MODULE)
        sys._freelab_history = None
        self.fontlab = type("FontLab", (), {})()
        self.fontlab.flItems = Items()
        self.extents = {}
        ak.master_extents = lambda package, glyphs: [e for g in glyphs for e in self.extents.get(g.name, [])]
        sys.modules[ak.FONT_INFO_MODULE] = fi  # (the other suites' writes run without it: taken out again)
        self.info = Info(ranges=[0], pages=[], ascent=900.0, descent=250.0)
        self.package = Package(21, [Glyph(u"A", [0x41])], self.info)

    def tearDown(self):
        sys._freelab_history, ak.master_extents, module = self.saved
        if module is None:
            sys.modules.pop(ak.FONT_INFO_MODULE, None)
        else:
            sys.modules[ak.FONT_INFO_MODULE] = module
        fi.forget()

    def build(self, name, code, extent=None, coverage=True):
        ak.before_changes(self.fontlab, self.package, u"FreeLab Glyph Compose", coverage=coverage)
        glyph = Glyph(name, [code])
        self.package.fgPackage.glyphs.append(glyph)
        if extent:
            self.extents[name] = [extent]
        return ak.notify_changed(self.fontlab, self.package, u"FreeLab Glyph Compose", [glyph], coverage=coverage)

    def test_a_build_updates_the_font_info_and_says_so(self):
        status = self.build(u"uniAC00", 0xAC00, (-120.0, 960.0))
        self.assertEqual(self.info.openTypeOS2UnicodeRanges, [0, 56])
        self.assertEqual(self.info.openTypeOS2WinAscent, 960.0)
        log = Log()
        self.assertTrue(status.report(log))
        self.assertEqual(log.lines, [("done", u"Updated the font info to match: Unicode ranges (added Hangul Syllables); "
                                              u"Win ascent (900 to 960). <i>Edit &gt; Undo</i> takes it back with the "
                                              u"glyphs (the Win values while this window is open).")])

    def test_a_write_that_does_not_ask_leaves_the_font_info(self):
        status = self.build(u"uniAC00", 0xAC00, (-120.0, 960.0), coverage=False)
        self.assertEqual((self.info.openTypeOS2UnicodeRanges, self.info.openTypeOS2WinAscent), ([0], 900.0))
        self.assertEqual(status.info_changes, [])

    def test_an_undo_seen_by_a_window_puts_the_font_info_back(self):
        self.build(u"uniAC00", 0xAC00, (-120.0, 960.0))
        written = self.package.state
        self.package.fgPackage.glyphs.pop()  # (Edit > Undo: the glyph gone, the font info as FreeLab left it)
        self.package.state = written - 1
        log = Log()
        changes = ak.follow_font_info(self.package, log, when_needed=True)
        self.assertEqual([c.field for c in changes], [fi.INFO_WIN_ASCENT], "the ranges are the History's")
        self.assertEqual(self.info.openTypeOS2WinAscent, 900.0)
        self.assertEqual(log.lines[0][0], "done")
        self.assertIn(u"Put the font info back in step with the glyphs", log.lines[0][1])
        self.assertEqual(ak.follow_font_info(self.package, log, when_needed=True), [], "nothing moved since")

    def test_an_undo_no_window_saw_is_followed_before_the_next_write(self):
        self.build(u"uniAC00", 0xAC00, (-120.0, 960.0))
        self.package.fgPackage.glyphs.pop()  # (Edit > Undo, no FreeLab window open: the History takes the
        self.info.openTypeOS2UnicodeRanges = [0]  # ranges back, not the Win ascent)
        self.package.state = 0
        status = self.build(u"B", 0x42)
        self.assertEqual((self.info.openTypeOS2UnicodeRanges, self.info.openTypeOS2WinAscent), ([0], 900.0),
                         "the Win ascent put back before the write; B changes nothing")
        self.assertEqual(status.info_changes, [])


if __name__ == "__main__":
    unittest.main()
