"""Tests of Font Check's bundled autonym font (checks/autonym_fonts): it has every character
checks/train/autonym_fonts.py found no installed font draws for Qt, it is a plain static TrueType font
named FreeLab Autonyms, its license is beside it, and Font Check finds and registers it.
Valid Python 2.7 and Python 3; reads the font with the struct module alone (no fontTools)."""

from __future__ import absolute_import, division, print_function

import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.join(HERE, os.pardir, "checks")
sys.path.insert(0, CHECKS)
import freelab_font_check as fc  # noqa: E402

FOLDER = os.path.join(CHECKS, "autonym_fonts")
INFO_FILE = os.path.join(FOLDER, "autonym_fonts.json")
LICENSE_FILE = os.path.join(FOLDER, "FreeLabAutonyms_LICENSE")
MAX_SIZE = 1024 * 1024  # well under a megabyte, the owner asked


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
                start, end, glyph = struct.unpack(">LLL", sub[16 + 12 * g:28 + 12 * g])
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


def info():
    with io.open(INFO_FILE, encoding="utf-8") as handle:
        return json.load(handle)


class BundledFontTests(unittest.TestCase):
    def setUp(self):
        self.info = info()
        self.path = os.path.join(FOLDER, self.info["file"])
        self.tables = read_tables(self.path)

    def test_has_every_required_character(self):
        required = [int(code, 16) for code in self.info["required"].split()]
        self.assertTrue(required, "the characters needed are listed")
        have = cmap_codes(self.tables["cmap"])
        missing = [u"U+%04X" % code for code in required if code not in have]
        self.assertEqual(missing, [], "the bundled font lacks these")
        self.assertEqual(self.info["not_covered"], u"", "every character found a source")

    def test_required_characters_are_autonyms(self):
        with io.open(os.path.join(CHECKS, fc.LANGUAGES_FILE), encoding="utf-8") as handle:
            text = u"".join(row[2] for row in json.load(handle)["orthographies"])
        used = set(fc.code_points(text))
        stray = [code for code in self.info["required"].split() if int(code, 16) not in used]
        self.assertEqual(stray, [], "only the autonyms' characters are bundled")

    def test_sources_add_up_to_required(self):
        supplied = sorted(int(c, 16) for s in self.info["sources"] for c in s["code_points"].split())
        self.assertEqual(supplied, sorted(int(c, 16) for c in self.info["required"].split()))

    def test_static_truetype_named_apart(self):
        for tag in ("glyf", "cmap", "name", "OS/2"):
            self.assertIn(tag, self.tables)
        for tag in ("fvar", "gvar", "COLR", "CPAL", "CFF2", "sbix", "SVG "):
            self.assertNotIn(tag, self.tables, "FontLab's Qt 5 needs a plain static font")
        found = names(self.tables["name"])
        self.assertEqual(found[1], fc.AUTONYM_FAMILY)
        self.assertEqual(self.info["family"], fc.AUTONYM_FAMILY)
        self.assertNotIn(u"Noto", found[1] + found[4] + found[6], "never mistaken for an installed Noto font")
        self.assertIn(u"Open Font License", found[13])

    def test_small(self):
        size = os.path.getsize(self.path)
        self.assertLess(size, MAX_SIZE)
        self.assertEqual(size, self.info["size"], "autonym_fonts.json describes this build")

    def test_license_beside_it(self):
        with io.open(LICENSE_FILE, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(u"SIL OPEN FONT LICENSE Version 1.1", text)
        for source in self.info["sources"]:
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
        return [fc.AUTONYM_FAMILY] if index == 7 else []


class FakeGui(object):
    QFontDatabase = FakeDatabase


class FakeCore(object):
    QByteArray = staticmethod(lambda data: data)


class FindingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="freelab-autonyms-")
        FakeDatabase.known, FakeDatabase.added, FakeDatabase.refuse = [], [], False

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_in_the_repository_folder(self):
        self.assertEqual(os.path.normcase(os.path.abspath(fc.autonym_font_path(CHECKS))),
                         os.path.normcase(os.path.abspath(os.path.join(FOLDER, fc.AUTONYM_FONT_FILE))))

    def test_installed_flat_beside_the_script(self):
        self.assertIsNone(fc.autonym_font_path(self.folder))
        flat = os.path.join(self.folder, fc.AUTONYM_FONT_FILE)
        shutil.copyfile(os.path.join(FOLDER, fc.AUTONYM_FONT_FILE), flat)
        self.assertEqual(fc.autonym_font_path(self.folder), flat)

    def test_family_list(self):
        self.assertEqual(fc.with_fallback(u"Segoe UI", u"FreeLab Autonyms"), u"Segoe UI,FreeLab Autonyms")
        self.assertEqual(fc.with_fallback(u"Segoe UI,FreeLab Autonyms", u"FreeLab Autonyms"),
                         u"Segoe UI,FreeLab Autonyms", "added once")
        self.assertEqual(fc.with_fallback(u"", u"FreeLab Autonyms"), u"FreeLab Autonyms")

    def test_registered_once(self):
        self.assertEqual(fc.register_autonym_font(FakeCore, FakeGui), fc.AUTONYM_FAMILY)
        self.assertEqual(len(FakeDatabase.added), 1)
        FakeDatabase.known = [fc.AUTONYM_FAMILY]
        self.assertEqual(fc.register_autonym_font(FakeCore, FakeGui), fc.AUTONYM_FAMILY)
        self.assertEqual(len(FakeDatabase.added), 1, "already known to Qt: not added again")

    def test_refused(self):
        FakeDatabase.refuse = True
        self.assertIsNone(fc.register_autonym_font(FakeCore, FakeGui))


if __name__ == "__main__":
    unittest.main()
