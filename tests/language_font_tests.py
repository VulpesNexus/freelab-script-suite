"""Tests of Font Check's languages list font (checks/language_font): it has every character
checks/train/language_font.py bundled (every character the list shows but the ideographs, Hangul
syllables, cuneiform signs, and hieroglyphs only its Missing column shows), it is a plain static
TrueType font named FreeLab Languages that claims the writing systems it draws, its license is beside
it, and Font Check finds it, registers it once, and sizes the list's text.
Valid Python 2.7 and Python 3; reads the font with the struct module alone (no fontTools)."""

from __future__ import absolute_import, division, print_function

import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unicodedata
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.join(HERE, os.pardir, "checks")
sys.path.insert(0, CHECKS)
import freelab_font_check as fc  # noqa: E402

FOLDER = os.path.join(CHECKS, fc.LIST_FONT_FOLDER)
INFO_FILE = os.path.join(FOLDER, "language_font.json")
LICENSE_FILE = os.path.join(FOLDER, "FreeLabLanguages_LICENSE")
MAX_SIZE = 3 * 1024 * 1024  # the owner's limit
LEFT_TO_SYSTEM = (((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x20000, 0x2FFFF), (0xF900, 0xFAFF)),  # ideographs
                  ((0xAC00, 0xD7A3),),  # Hangul syllables
                  ((0x12000, 0x1254F),),  # cuneiform
                  ((0x13000, 0x1345F),))  # Egyptian hieroglyphs
CODE_PAGE_BITS = {"Latin 1": 0, "Cyrillic": 2, "Greek": 3, "Hebrew": 5, "Arabic": 6, "Thai": 16, "Japanese": 17,
                  "Korean": 19}


def read_tables(path):
    with open(path, "rb") as handle:
        data = handle.read()
    count = struct.unpack(">H", data[4:6])[0]
    tables = {}
    for at in range(12, 12 + 16 * count, 16):
        tag, _, offset, length = struct.unpack(">4sLLL", data[at:at + 16])
        tables[tag.decode("latin-1")] = data[offset:offset + length]
    return tables


def cmap_codes(table):
    """The code points of a cmap table's Unicode subtables (formats 4 and 12)."""
    codes = set()
    count = struct.unpack(">H", table[2:4])[0]
    for at in range(4, 4 + 8 * count, 8):
        platform, encoding, offset = struct.unpack(">HHL", table[at:at + 8])
        if (platform, encoding) not in ((3, 1), (3, 10), (0, 3), (0, 4)):
            continue
        sub = table[offset:]
        form = struct.unpack(">H", sub[:2])[0]
        if form == 4:
            segments = struct.unpack(">H", sub[6:8])[0] // 2
            ends = struct.unpack(">%dH" % segments, sub[14:14 + 2 * segments])
            base = 16 + 2 * segments
            starts = struct.unpack(">%dH" % segments, sub[base:base + 2 * segments])
            deltas = struct.unpack(">%dh" % segments, sub[base + 2 * segments:base + 4 * segments])
            ranges_at = base + 4 * segments
            offsets = struct.unpack(">%dH" % segments, sub[ranges_at:ranges_at + 2 * segments])
            for i in range(segments):
                for code in range(starts[i], ends[i] + 1):
                    if code == 0xFFFF:
                        continue
                    if offsets[i] == 0:
                        glyph = (code + deltas[i]) & 0xFFFF
                    else:
                        where = ranges_at + 2 * i + offsets[i] + 2 * (code - starts[i])
                        glyph = struct.unpack(">H", sub[where:where + 2])[0]
                        glyph = (glyph + deltas[i]) & 0xFFFF if glyph else 0
                    if glyph:
                        codes.add(code)
        elif form == 12:
            groups = struct.unpack(">L", sub[12:16])[0]
            for g in range(groups):
                start, end, _ = struct.unpack(">LLL", sub[16 + 12 * g:28 + 12 * g])
                codes.update(range(start, end + 1))
    return codes


def names(table):
    """{name ID: text} of a name table's Windows Unicode records."""
    count, strings = struct.unpack(">HH", table[2:6])
    found = {}
    for at in range(6, 6 + 12 * count, 12):
        platform, encoding, _, name_id, length, offset = struct.unpack(">6H", table[at:at + 12])
        if (platform, encoding) == (3, 1):
            found[name_id] = table[strings + offset:strings + offset + length].decode("utf-16-be")
    return found


def left_to_system(code):
    return any(low <= code <= high for ranges in LEFT_TO_SYSTEM for low, high in ranges)


def shown_characters():
    """Every character the languages list can show, and those of its first column alone (names,
    autonyms, script headings)."""
    with io.open(os.path.join(CHECKS, fc.LANGUAGES_FILE), encoding="utf-8") as handle:
        data = json.load(handle)
    first, everything = set(), set()
    for row in data["orthographies"]:
        name, autonym, script, base, auxiliary, marks = row[1], row[2], row[3], row[7], row[8], row[9]
        first.update(fc.code_points(name + autonym + script))
        everything.update(fc.code_points(data["texts"][base] + data["texts"][auxiliary] + marks))
    first.update(fc.code_points(u"(0123456789) +" + fc.DOTTED_CIRCLE + u"\N{HORIZONTAL ELLIPSIS}LanguageMissing"))
    everything.update(first)
    everything.discard(0x20)
    return first, everything


def is_format(code):
    """A control or format character (a joiner): the shaper uses it, and no glyph is drawn."""
    try:
        return unicodedata.category(fc.char_of(code)).startswith(u"C")
    except TypeError:  # (past U+FFFF on a narrow Python 2)
        return False


def use_list_font(tree):
    """Font Check's FontCheckDialog.use_list_font on a tree (it reads nothing else of the dialog)."""
    method = fc.FontCheckDialog.use_list_font
    getattr(method, "__func__", method)(None, tree)


def info():
    with io.open(INFO_FILE, encoding="utf-8") as handle:
        return json.load(handle)


class ListFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.info = info()
        cls.path = os.path.join(FOLDER, cls.info["file"])
        cls.tables = read_tables(cls.path)
        cls.cmap = cmap_codes(cls.tables["cmap"])

    def test_has_every_required_character(self):
        required = [int(code, 16) for code in self.info["required"].split()]
        self.assertGreater(len(required), 5000)
        missing = [u"U+%04X" % code for code in required if code not in self.cmap]
        self.assertEqual(missing, [], "the bundled font lacks these")
        self.assertEqual(self.info["not_covered"], u"", "every character found a source")

    def test_first_column_whole(self):
        first, _ = shown_characters()
        missing = [u"U+%04X" % code for code in sorted(first) if code not in self.cmap]
        self.assertEqual(missing, [], "every name, autonym, and script heading in the one font")

    def test_missing_column_whole_but_what_is_left(self):
        _, everything = shown_characters()
        missing = [u"U+%04X" % code for code in sorted(everything)
                   if code not in self.cmap and not left_to_system(code) and not is_format(code)]
        self.assertEqual(missing, [], "only ideographs, Hangul syllables, cuneiform, and hieroglyphs are left out")

    def test_sources_add_up_to_required(self):
        supplied = sorted(int(c, 16) for s in self.info["fonts"] for c in s["code_points"].split())
        self.assertEqual(supplied, sorted(int(c, 16) for c in self.info["required"].split()))

    def test_static_truetype_named_apart(self):
        for tag in ("glyf", "cmap", "name", "OS/2", "GSUB", "GPOS"):
            self.assertIn(tag, self.tables)
        for tag in ("fvar", "gvar", "COLR", "CPAL", "CFF ", "CFF2", "sbix", "SVG "):
            self.assertNotIn(tag, self.tables, "FontLab's Qt 5 needs a plain static font")
        found = names(self.tables["name"])
        self.assertEqual(found[1], fc.LIST_FAMILY)
        self.assertEqual(self.info["family"], fc.LIST_FAMILY)
        self.assertNotIn(u"Noto", found[1] + found[4] + found[6], "never mistaken for an installed Noto font")
        self.assertNotIn(u"Source", found[1] + found[4] + found[6], "nor uses the CJK fonts' Reserved Font Name")
        self.assertIn(u"Open Font License", found[13])

    def test_claims_its_writing_systems(self):
        """Qt 5 takes another family for a script whose writing system the font does not claim."""
        os2 = self.tables["OS/2"]
        code_pages = struct.unpack(">L", os2[78:82])[0]
        for name, bit in CODE_PAGE_BITS.items():
            self.assertTrue(code_pages >> bit & 1, name)
        ranges = struct.unpack(">4L", os2[42:58])
        for bit in (0, 7, 9, 10, 11, 13, 15, 24, 26, 56, 70, 71, 72, 73, 74, 80):
            self.assertTrue(ranges[bit // 32] >> (bit % 32) & 1, "Unicode range bit %d" % bit)

    def test_line_holds_the_ink(self):
        hhea = self.tables["hhea"]
        ascent, descent = struct.unpack(">hh", hhea[4:8])
        self.assertEqual([ascent, descent], self.info["line"])
        os2 = self.tables["OS/2"]
        win_ascent, win_descent = struct.unpack(">HH", os2[74:78])
        self.assertEqual((win_ascent, -win_descent), (ascent, descent), "Windows draws the same line")

    def test_small_enough(self):
        size = os.path.getsize(self.path)
        self.assertLess(size, MAX_SIZE)
        self.assertEqual(size, self.info["size"], "language_font.json describes this build")

    def test_license_beside_it(self):
        with io.open(LICENSE_FILE, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(u"SIL OPEN FONT LICENSE", text.upper())
        for source in self.info["fonts"]:
            self.assertIn(source["copyright"], text)
            self.assertIn(source["family"], text)


class FakeDatabase(object):
    """QFontDatabase's static calls, as Font Check makes them."""
    known, added, refuse = [], [], False

    def families(self):
        return list(FakeDatabase.known)

    @staticmethod
    def addApplicationFont(path):
        if FakeDatabase.refuse:
            return -1
        FakeDatabase.added.append(path)
        return 7

    @staticmethod
    def addApplicationFontFromData(data):
        return -1

    @staticmethod
    def applicationFontFamilies(index):
        return [fc.LIST_FAMILY] if index == 7 else []


class FakeFont(object):
    def __init__(self, other=None, points=9.0, pixels=-1):
        self.family = other.family if other else u"MS Shell Dlg 2"
        self.points = other.points if other else points
        self.pixels = other.pixels if other else pixels

    def setFamily(self, family):
        self.family = family

    def pointSizeF(self):
        return self.points

    def pixelSize(self):
        return self.pixels

    def setPointSizeF(self, size):
        self.points, self.pixels = size, -1

    def setPixelSize(self, size):
        self.points, self.pixels = -1, size


class FakeGui(object):
    QFontDatabase = FakeDatabase
    QFont = FakeFont


class FakeCore(object):
    QByteArray = staticmethod(lambda data: data)


class FakeTree(object):
    def __init__(self, font):
        self.font = font  # (a property: a value under PythonQt)

    def setFont(self, font):
        self.font = font


class FindingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="freelab-list-font-")
        FakeDatabase.known, FakeDatabase.added, FakeDatabase.refuse = [], [], False
        self.qt = fc._qt
        fc._qt = lambda: (FakeCore, FakeGui)

    def tearDown(self):
        fc._qt = self.qt
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_in_the_repository_folder(self):
        self.assertEqual(os.path.normcase(os.path.abspath(fc.list_font_path(CHECKS))),
                         os.path.normcase(os.path.abspath(os.path.join(FOLDER, fc.LIST_FONT_FILE))))

    def test_installed_flat_beside_the_script(self):
        self.assertIsNone(fc.list_font_path(self.folder))
        flat = os.path.join(self.folder, fc.LIST_FONT_FILE)
        shutil.copyfile(os.path.join(FOLDER, fc.LIST_FONT_FILE), flat)
        self.assertEqual(fc.list_font_path(self.folder), flat)

    def test_scaled_size(self):
        self.assertEqual(fc.scaled_size(8.0, -1), ("point", 10.0))
        self.assertEqual(fc.scaled_size(9.0, -1), ("point", 11.25))
        self.assertEqual(fc.scaled_size(-1, 12), ("pixel", 15))
        self.assertEqual(fc.scaled_size(-1, -1), (None, None), "no size known: left alone")

    def test_registered_once(self):
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual(len(FakeDatabase.added), 1)
        FakeDatabase.known = [fc.LIST_FAMILY]
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual(len(FakeDatabase.added), 1, "already known to Qt: not added again")

    def test_refused(self):
        FakeDatabase.refuse = True
        self.assertIsNone(fc.register_list_font(FakeCore, FakeGui))

    def test_list_in_one_family_larger(self):
        tree = FakeTree(FakeFont(points=9.0))
        use_list_font(tree)
        self.assertEqual(tree.font.family, fc.LIST_FAMILY, "one family, no fallback list")
        self.assertEqual(tree.font.points, 11.25)

    def test_refused_font_still_larger(self):
        FakeDatabase.refuse = True
        tree = FakeTree(FakeFont(points=8.0))
        use_list_font(tree)
        self.assertEqual((tree.font.family, tree.font.points), (u"MS Shell Dlg 2", 10.0))

    def test_never_raises(self):
        class Broken(object):
            @property
            def font(self):
                raise RuntimeError("no font")
        use_list_font(Broken())


if __name__ == "__main__":
    unittest.main()
