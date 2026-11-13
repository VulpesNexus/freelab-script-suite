"""Tests of Font Check's font (checks/language_font), five files that Qt falls back across (FreeLang
Essential, CJK, Extended General, Extended Mongolian-Tibetan, and Extended Duployan, the last one
optional): together they have every character of checks/font_characters.json (the names, the other
names, the orthographies' characters, and the character sets': what the lists, tooltips, and pictures
show), each in one of them (but the characters of a font's own family name, which each font has), but
those no source font supplies, which are listed here, as are those that come from fonts other than
Noto's, none of them a bitmap's pixels; Andika's letters and Unicodia Funky's four combining
parentheses meet Noto Sans's marks and letters through anchors carried into its lookups; each is a
plain static TrueType font named apart, within its limits (65,535 glyphs, and layout lookups within
65,535 bytes), on the same line as the others, that claims the writing systems it draws; their
license is beside them; and Font Check finds them, registers each once, gives Qt the others as the
first one's substitutes, and sizes the list's text.
Valid Python 2.7 and Python 3; reads the fonts with the struct module alone (no fontTools)."""

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
LICENSE_FILE = os.path.join(FOLDER, "FreeLang_LICENSE")
CHARACTERS_FILE = os.path.join(CHECKS, "font_characters.json")  # checks/train/orthographies.py --characters
PARTS = ("names", "other_names", "orthographies", "sets")
# The font was one file of 8.3 MB (29,402 characters) until every small script and symbol block of
# Unicode became a character set (40,444 characters): one font cannot hold their glyphs and layout
# (65,535 glyphs; a GSUB table's lookups within 65,535 bytes), so it was three, and is five, 12.8 MB
# together as built: Essential 1.7 MB, CJK 3.7 MB (the 11,172 Hangul syllables and the hanja 2.5 MB),
# Extended General 4.6 MB (cuneiform 0.8 MB, hieroglyphs 0.6 MB, Symbols 2 0.5 MB), Extended
# Mongolian-Tibetan 0.8 MB (Noto Serif Tibetan 0.6 MB of it), and Extended Duployan 1.6 MB (its
# layout's 9,378 glyphs). Each bound leaves about a fifth of room: a build past one is one whose data
# or sources grew, and is to be looked at before it ships.
MAX_SIZES = {u"Essential": 2100 * 1024, u"CJK": 4400 * 1024, u"Extended General": 5600 * 1024,
             u"Extended Mongolian-Tibetan": 1050 * 1024, u"Extended Duployan": 1900 * 1024}
LABELS = (u"Essential", u"CJK", u"Extended General", u"Extended Mongolian-Tibetan", u"Extended Duployan")
# The tools work without these files, published beside each release rather than kept in the repository:
# a test of a file is skipped without it.
OPTIONAL = (u"CJK", u"Extended General", u"Extended Mongolian-Tibetan", u"Extended Duployan")
GDI_FAMILY_LIMIT = 31  # characters of a family name Windows (GDI) and so Qt can register
MAX_GLYPHS = 65535  # a TrueType font's glyph indices are 16 bits wide
MAX_LOOKUP_BYTES = 65535  # and its lookups are reached by 16-bit offsets (checks/train/language_font.py: lookup_bytes)
# The sources that keep their layout though no language's text draws from them: each has a font of its
# own (with Noto Serif Tibetan, or alone), the stated exception to the rule of running text.
OWN_LAYOUT = {u"Noto Sans Mongolian": u"Extended Mongolian-Tibetan", u"Noto Sans Duployan": u"Extended Duployan"}
# The one source in two fonts: Unicodia Funky's four combining parentheses are in the Essential font,
# where Noto Sans's letters take them; the rest of it is in the Extended General font.
ELSEWHERE = {u"UnicodiaFunky": (u"Essential", u"1AC1-1AC4")}
# What no source font has (checks/train/language_font.py found no source): hexadecimal code points
# and ranges, as in checks/font_characters.json. Qt takes such a character from a system font, or shows
# a box. Looked for on 2026-11-13 in every font of notofonts.github.io at the pinned commit (but the
# fonts of SignWriting, Nushu, Khitan, and the two test fonts), in 23 Noto fonts of google/fonts, and
# in the fonts Unicodia bundles: no font under an open license has them. Unicodia's "Noto Serif Tai
# Yo" 1.030 is no Noto font and declares no license or copyright; its Syriac font (Serto Antioch
# Bible) forbids commercial use; the emoji are in Noto's color font alone. A character added to
# checks/font_characters.json that no source has is listed here.
NOT_SUPPLIED = (u"0860-086A "  # Syriac Supplement (the Malayalam letters of Syriac)
                u"31BC-31BF "  # Bopomofo Extended (Unicode 13)
                u"1E6C0-1E6DE 1E6E0-1E6F5 1E6FE-1E6FF "  # Tai Yo (Unicode 17): the whole script
                u"1F6D8 "  # Transport and Map Symbols (Unicode 17)
                u"1FA89-1FA8A 1FA8E-1FA8F 1FABE 1FAC6 1FAC8 1FACD 1FADC 1FADF 1FAE9-1FAEA 1FAEF")  # emoji of Unicode 16 and 17
# What comes from fonts other than Noto's, by the family language_font.json names: the build looks in
# them last, for what no Noto font has, and a top-up that takes more from them fails here until it is
# looked at and listed. Until 2026-11-13 sixteen characters came from GNU Unifont, a bitmap's pixels;
# they come from Unicodia Funky's outlines, and no source may be a bitmap font again (BITMAP_FONTS).
OTHER_SOURCES = {
    u"Noto Emoji": (u"23EB-23EC 23F0 "  # Miscellaneous Technical: emoji
                    u"2705 270A 2728 274C 274E 2754-2755 2795-2797 27B0 27BF "  # Dingbats: emoji
                    u"1F1E6-1F1FF "  # Enclosed Alphanumeric Supplement: the regional indicators
                    u"1F600-1F60F 1F611-1F64F "  # Emoticons
                    u"1F680-1F686 1F688-1F68C 1F68E-1F690 1F692-1F693 1F695-1F697 1F699-1F6AC 1F6AE-1F6B1 1F6B3-1F6B8 "
                    u"1F6BB 1F6BD-1F6C5 1F6CC 1F6D0-1F6D2 1F6DC-1F6DF 1F6EB-1F6EC 1F6F4-1F6F6 "  # Transport and Map Symbols
                    u"1F7F0 "  # Geometric Shapes Extended
                    u"1F90C-1F93A 1F93C-1F945 1F947-1F9FF "  # Supplemental Symbols and Pictographs
                    u"1FA75-1FA77 1FA7B-1FA7C 1FA87-1FA88 1FAA9-1FAAF 1FAB7-1FABD 1FABF 1FAC3-1FAC5 1FACE-1FACF "
                    u"1FAD7-1FADB 1FAE0-1FAE8 1FAF0-1FAF8"),  # Symbols and Pictographs Extended-A
    u"Andika": (u"1C89-1C8A "  # Cyrillic Extended-C: tje (Unicode 16)
                u"A7CB-A7CD A7DA-A7DC"),  # Latin Extended-D (Unicode 16)
    u"UnicodiaFunky": (u"0C5C 0CDC "  # a Telugu and a Kannada letter (Unicode 17)
                       u"1AC1-1AC4 "  # Combining Diacritical Marks Extended (Unicode 14)
                       u"1B4E-1B4F 1B7F "  # Balinese (Unicode 16)
                       u"2427-2429 2B96 "  # Control Pictures, Miscellaneous Symbols and Arrows
                       u"10940-10959 "  # Sidetic (no Noto font)
                       u"10D40-10D65 10D69-10D85 10D8E-10D8F "  # Garay (no Noto font)
                       u"11B60-11B67 "  # Sharada Supplement (Unicode 17)
                       u"11DB0-11DDB 11DE0-11DE9 "  # Tolong Siki (no Noto font)
                       u"11F5A "  # Kawi (Unicode 16)
                       u"16100-16139 "  # Gurung Khema (Noto's is unreleased)
                       u"1CEC0-1CED0 1CEE0-1CEF0 "  # Miscellaneous Symbols Supplement (Unicode 17)
                       u"1E5D0-1E5FA 1E5FF "  # Ol Onal (Noto's is unreleased)
                       u"1F777-1F77A 1F8C0-1F8C1 1F8D0-1F8D8 1FA54-1FA57 1FBFA"),  # alchemical, arrows, chess, legacy computing
    # Scripts no Noto font draws, each from the font made for it:
    u"Kanchenjunga": u"16D40-16D79",  # Kirat Rai (SIL); it draws an orthography, and keeps its layout
    u"Kedebideri": u"16EA0-16EB8 16EBB-16ED3",  # Beria Erfe (SIL)
    u"Daarage": (u"11380-11389 1138B 1138E 11390-113B5 113B7-113C0 113C2 113C5 113C7-113CA 113CC-113D5 113D7-113D8 "
                 u"113E1-113E2"),  # Tulu-Tigalari
    # A few characters each, which the script's Noto font lacks:
    u"Padauk Book": u"116D0-116E3",  # Myanmar Extended-C: digits (SIL's Myanmar font)
    u"Shafarik": u"2C2F 2C5F",  # two Glagolitic letters of Unicode 14
    u"BabelStone Pseudographica": u"1F8B2-1F8BB 1FBCB-1FBEF",  # arrows and legacy computing symbols of Unicode 16
}
# The sources that draw a language's text, and so keep their layout; the others draw characters one
# at a time, and keep their character map alone.
SCRIPT_FONTS = (u"Kanchenjunga",)
# What the fonts of OTHER_SOURCES have carried into Noto Sans's mark lookups (language_font.json's
# anchors_carried, of the Essential font): Andika's letters as bases of Noto Sans's marks, and Unicodia
# Funky's four combining parentheses as marks of them. (While the font was three, Unicodia Funky was
# whole in the Extended font, out of Noto Sans's reach, and the four were placed by their outlines.)
ANCHORS_CARRIED = {u"Andika": {u"bases": u"1C89-1C8A A7CB-A7CD A7DA-A7DC", u"marks": u""},
                   u"UnicodiaFunky": {u"bases": u"", u"marks": u"1AC1-1AC4"}}
# Fonts whose outlines are a bitmap's pixels (or are bitmaps): never a source.
BITMAP_FONTS = (u"unifont", u"fairfax", u"terminus", u"fixedsys", u"unscii", u"proggy", u"bitmap", u"pixel")
# Where a source that is not one of the two Noto repositories at a pinned commit comes from: a
# release, pinned by its version in the address, or another repository's file at a pinned commit.
RELEASES = (u"https://github.com/silnrsi/font-andika/releases/download/v7.000/",
            u"https://github.com/silnrsi/font-kanchenjunga/releases/download/v2.001/",
            u"https://github.com/silnrsi/font-kedebideri/releases/download/v3.001/",
            u"https://github.com/silnrsi/font-padauk/releases/download/v6.000/",
            u"https://raw.githubusercontent.com/Mercury13/unicodia/df2b09c61e8fdc06f96fc6d6b194427f61bb2e38/Fonts/")
# The one Noto font taken from its project's release, not from the pinned commit: the commit's version
# (2.000) draws 49 of Dives Akuru's 72 characters, and 1.001 draws them all.
NOTO_RELEASES = {u"Noto Serif Dives Akuru": u"https://github.com/notofonts/dives-akuru/releases/download/NotoSerifDivesAkuru-v1.001/"}
# The scripts of the Essential font: Unicode's Recommended Scripts (UAX #31 revision 43, Table 5),
# Common and Inherited aside, but Han, Hangul, Hiragana, and Katakana, which are the CJK font's, and
# Tibetan, which has a font with Mongolian.
RECOMMENDED_SCRIPTS = (u"Arab", u"Armn", u"Beng", u"Cyrl", u"Deva", u"Ethi", u"Geor", u"Grek", u"Gujr", u"Guru", u"Hebr",
                       u"Knda", u"Khmr", u"Laoo", u"Latn", u"Mlym", u"Mymr", u"Orya", u"Sinh", u"Taml", u"Telu", u"Thaa",
                       u"Thai")
CODE_PAGE_BITS = {"Latin 1": 0, "Cyrillic": 2, "Greek": 3, "Hebrew": 5, "Arabic": 6, "Thai": 16, "Japanese": 17,
                  "Chinese": 18, "Korean": 19}


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


def cmap_formats(table):
    """The formats of a cmap table's subtables."""
    count = struct.unpack(">H", table[2:4])[0]
    offsets = [struct.unpack(">HHL", table[at:at + 8])[2] for at in range(4, 4 + 8 * count, 8)]
    return sorted(set(struct.unpack(">H", table[offset:offset + 2])[0] for offset in offsets))


def cmap_glyphs(table):
    """{code point: glyph index} of a cmap table's format 12 subtable (which maps every character)."""
    found = {}
    count = struct.unpack(">H", table[2:4])[0]
    for at in range(4, 4 + 8 * count, 8):
        sub = table[struct.unpack(">HHL", table[at:at + 8])[2]:]
        if struct.unpack(">H", sub[:2])[0] == 12:
            for g in range(struct.unpack(">L", sub[12:16])[0]):
                start, end, glyph = struct.unpack(">LLL", sub[16 + 12 * g:28 + 12 * g])
                for code in range(start, end + 1):
                    found[code] = glyph + code - start
    return found


def glyph_length(tables, glyph):
    """The bytes of a glyph's outline (0 for an empty glyph)."""
    loca = tables["loca"]
    if struct.unpack(">h", tables["head"][50:52])[0]:
        start, end = struct.unpack(">LL", loca[4 * glyph:4 * glyph + 8])
    else:
        start, end = [2 * v for v in struct.unpack(">HH", loca[2 * glyph:2 * glyph + 4])]
    return end - start


def glyph_curves(tables, glyph):
    """How many off-curve points a simple glyph has (0 for a composite or an empty one): a bitmap's
    pixels are straight lines alone."""
    long_offsets = struct.unpack(">h", tables["head"][50:52])[0]
    loca = tables["loca"]
    if long_offsets:
        start, end = struct.unpack(">LL", loca[4 * glyph:4 * glyph + 8])
    else:
        start, end = [2 * v for v in struct.unpack(">HH", loca[2 * glyph:2 * glyph + 4])]
    data = tables["glyf"][start:end]
    if len(data) < 10:
        return 0
    contours = struct.unpack(">h", data[:2])[0]
    if contours <= 0:
        return 0
    points = struct.unpack(">H", data[10 + 2 * contours - 2:10 + 2 * contours])[0] + 1
    at = 10 + 2 * contours
    at += 2 + struct.unpack(">H", data[at:at + 2])[0]  # (the instructions)
    seen = curves = 0
    while seen < points:
        flag = struct.unpack(">B", data[at:at + 1])[0]
        repeat = 1
        at += 1
        if flag & 8:
            repeat += struct.unpack(">B", data[at:at + 1])[0]
            at += 1
        seen += repeat
        if not flag & 1:
            curves += repeat
    return curves


def coverage_glyphs(data):
    """The glyph indices of an OpenType coverage table."""
    form, count = struct.unpack(">HH", data[:4])
    if form == 1:
        return set(struct.unpack(">%dH" % count, data[4:4 + 2 * count]))
    found = set()
    for at in range(4, 4 + 6 * count, 6):
        start, end, _ = struct.unpack(">HHH", data[at:at + 6])
        found.update(range(start, end + 1))
    return found


def attachments(gpos, kind):
    """[(the marks' glyph indices, the bases')] of a GPOS table's mark-to-base (kind 4) or
    mark-to-mark (kind 6) subtables, those behind extension lookups too."""
    found = []
    lookups = gpos[struct.unpack(">H", gpos[8:10])[0]:]
    for at in struct.unpack(">%dH" % struct.unpack(">H", lookups[:2])[0], lookups[2:2 + 2 * struct.unpack(">H", lookups[:2])[0]]):
        lookup = lookups[at:]
        form, _, count = struct.unpack(">HHH", lookup[:6])
        for offset in struct.unpack(">%dH" % count, lookup[6:6 + 2 * count]):
            sub, this = lookup[offset:], form
            if this == 9:
                _, this, far = struct.unpack(">HHL", sub[:8])
                sub = sub[far:]
            if this == kind:
                marks, bases = struct.unpack(">HH", sub[2:6])
                found.append((coverage_glyphs(sub[marks:]), coverage_glyphs(sub[bases:])))
    return found


def glyph_class(gdef, glyph):
    """A glyph's class in a GDEF table's glyph class definition (1 base, 2 ligature, 3 mark), or 0."""
    data = gdef[struct.unpack(">H", gdef[4:6])[0]:]
    form = struct.unpack(">H", data[:2])[0]
    if form == 1:
        start, count = struct.unpack(">HH", data[2:6])
        return struct.unpack(">H", data[6 + 2 * (glyph - start):8 + 2 * (glyph - start)])[0] if start <= glyph < start + count else 0
    for at in range(4, 4 + 6 * struct.unpack(">H", data[2:4])[0], 6):
        start, end, value = struct.unpack(">HHH", data[at:at + 6])
        if start <= glyph <= end:
            return value
    return 0


def lookup_bytes(table):
    """What a GSUB or GPOS table's lookup list needs within reach of 16-bit offsets, counted as
    checks/train/language_font.py counts it: the count and the lookups' offsets, each lookup's header
    (and its mark filtering set), and ten bytes per subtable (its offset and an extension record)."""
    lookups = table[struct.unpack(">H", table[8:10])[0]:]
    count = struct.unpack(">H", lookups[:2])[0]
    size = 2 if count else 0
    for at in struct.unpack(">%dH" % count, lookups[2:2 + 2 * count]):
        _, flag, subtables = struct.unpack(">HHH", lookups[at:at + 6])
        size += 2 + 6 + (2 if flag & 0x10 else 0) + 10 * subtables
    return size


def codes_of(text):
    """The code points of hexadecimal code points and ranges ("0041-005A 00DF")."""
    codes = set()
    for part in text.split():
        low, _, high = part.partition("-")
        codes.update(range(int(low, 16), int(high or low, 16) + 1))
    return codes


def required_characters():
    """({part: its code points}, the counts) of checks/font_characters.json: what the font must draw."""
    with io.open(CHARACTERS_FILE, encoding="utf-8") as handle:
        data = json.load(handle)
    return dict((part, codes_of(data[part])) for part in PARTS), data["counts"]


def names(table):
    """{name ID: text} of a name table's Windows Unicode records."""
    count, strings = struct.unpack(">HH", table[2:6])
    found = {}
    for at in range(6, 6 + 12 * count, 12):
        platform, encoding, _, name_id, length, offset = struct.unpack(">6H", table[at:at + 12])
        if (platform, encoding) == (3, 1):
            found[name_id] = table[strings + offset:strings + offset + length].decode("utf-16-be")
    return found


def shown_characters():
    """Every character the languages list can show, read here from both orthography files
    (Hyperglot's, and the second one's), and those of its first column alone (names, autonyms, script
    headings)."""
    first, everything = set(), set()
    for file_name in (fc.LANGUAGES_FILE, fc.ORTHOGRAPHIES_FILE):
        with io.open(os.path.join(CHECKS, file_name), encoding="utf-8") as handle:
            data = json.load(handle)
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
        cls.files = dict((row["font"], row) for row in cls.info["files"])  # by label: Essential, CJK, ...
        # (an optional font's file may be absent where the tests run: what is read from it is then skipped)
        cls.present = [row["font"] for row in cls.info["files"] if os.path.isfile(os.path.join(FOLDER, row["file"]))]
        cls.fonts = dict((label, read_tables(os.path.join(FOLDER, cls.files[label]["file"]))) for label in cls.present)
        cls.cmaps = dict((label, cmap_codes(tables["cmap"])) for label, tables in cls.fonts.items())
        cls.tables = cls.fonts[u"Essential"]
        cls.cmap = set().union(*cls.cmaps.values())  # (what the fonts draw together)
        # (a font's copy of its own family name's characters, which the Essential font supplies, aside)
        cls.sources = [source for source in cls.info["fonts"] if source["subset"] != u"name"]
        cls.names = dict((source["font"], codes_of(source["code_points"])) for source in cls.info["fonts"]
                         if source["subset"] == u"name")
        cls.absent = set(code for source in cls.sources if source["font"] not in cls.present
                         for code in codes_of(source["code_points"]))  # (an absent optional font's characters)

    def font_of(self, code):
        """The tables of the font that draws a character (the first, in Font Check's order)."""
        return [self.fonts[label] for label in LABELS if code in self.cmaps.get(label, ())][0]

    def curves(self, code):
        tables = self.font_of(code)
        return glyph_curves(tables, cmap_glyphs(tables["cmap"])[code])

    def test_five_fonts_each_character_once(self):
        """The five, as Font Check names them, the last one optional; a character is in one of them,
        but those of a font's own family name, which the font has too."""
        self.assertEqual([row["font"] for row in self.info["files"]], list(LABELS))
        self.assertEqual([row["font"] for row in self.info["files"] if row["optional"]], list(OPTIONAL))
        self.assertEqual([label for label in LABELS if label not in self.present and label not in OPTIONAL], [],
                         "only an optional font's file may be absent")
        self.assertEqual(self.files[u"Essential"]["file"], fc.LIST_FONT_FILE)
        self.assertEqual([(row["file"], row["family"]) for row in self.info["files"][1:]],
                         [tuple(pair) for pair in fc.LIST_FONT_FALLBACKS])
        copies = sum(len(self.names[label]) for label in self.present if label in self.names)
        self.assertEqual(sum(len(codes) for codes in self.cmaps.values()) - copies, len(self.cmap))
        for label in self.present:
            self.assertEqual(len(self.cmaps[label]), self.files[label]["characters"], label)
        general, mongolian = u"Extended General", u"Extended Mongolian-Tibetan"
        for low, high, label in ((0x41, 0x42, u"Essential"), (0x410, 0x44F, u"Essential"), (0x391, 0x3A1, u"Essential"),
                                 (0x900, 0x939, u"Essential"), (0x2010, 0x2012, u"Essential"), (0x300, 0x306, u"Essential"),
                                 (0x30, 0x39, u"Essential"), (0x20A0, 0x20BF, u"Essential"), (0x1AC1, 0x1AC4, u"Essential"),
                                 (0xAC00, 0xD7A3, u"CJK"), (0x3041, 0x3096, u"CJK"), (0x4E00, 0x4E0F, u"CJK"),
                                 (0x12000, 0x12010, general), (0x2800, 0x28FF, general), (0x10D40, 0x10D65, general),
                                 (0x1820, 0x1842, mongolian), (0xF40, 0xF47, mongolian), (0x1BC00, 0x1BC6A, u"Extended Duployan")):
            found = set(l for l in self.cmaps for code in range(low, high + 1) if code in self.cmaps[l])
            self.assertEqual(found, set([label]) & set(self.present), "U+%04X to U+%04X" % (low, high))
        scripts = self.files[u"Essential"]["scripts"]
        self.assertEqual(scripts, sorted(RECOMMENDED_SCRIPTS), "the Recommended Scripts but the CJK font's and Tibetan")
        # (Latin: the letters of each font's own family name)
        self.assertEqual(self.files[u"CJK"]["scripts"], [u"Bopo", u"Hang", u"Hani", u"Hira", u"Kana", u"Latn"])
        self.assertEqual(self.files[mongolian]["scripts"], [u"Latn", u"Mong", u"Tibt"])
        self.assertEqual(self.files[u"Extended Duployan"]["scripts"], [u"Dupl", u"Latn"])

    def test_each_font_draws_its_own_family_name(self):
        """A font list draws a family's name in the family: every font has the characters of its own
        name, the four fallback fonts as copies of Noto Sans's (the Essential font's Latin), with the
        character map alone. Text still takes them from the Essential font, which comes first."""
        self.assertEqual(sorted(self.names), sorted(LABELS[1:]))
        first = [source for source in self.info["fonts"] if source["font"] == u"Essential"][0]
        self.assertEqual((first["family"], first["subset"]), (u"Noto Sans", u"own"))
        for row in self.info["files"]:
            wanted = set(fc.code_points(row["full_family"]))  # (the longer name: it has the shorter one's characters)
            self.assertEqual(set(fc.code_points(row["family"])) - wanted, set(), row["font"])
            if row["font"] in self.present:
                self.assertEqual(sorted(wanted - self.cmaps[row["font"]]), [], row["font"])
            if row["font"] == u"Essential":
                self.assertEqual(row["name_subset"], [])
                continue
            self.assertEqual(self.names[row["font"]], wanted, row["font"])
            self.assertEqual(sorted(wanted - codes_of(first["code_points"])), [], "copies of Noto Sans's")
            copy = [source for source in self.info["fonts"] if source["font"] == row["font"] and source["subset"] == u"name"][0]
            self.assertEqual((copy["family"], copy["sha256"], copy["layout"]),
                             (u"Noto Sans", first["sha256"], u"none (character map only)"))
            self.assertEqual(row["name_subset"], [[len(wanted), len(wanted) + 1]], "its characters and .notdef")
        dash = [code for code in fc.code_points(self.files[u"Extended Mongolian-Tibetan"]["family"]) if code > 0x7E]
        self.assertEqual(dash, [0x2013], "an en dash joins Mongolian and Tibetan in the fourth family's name")
        for row in self.info["files"]:
            self.assertEqual([c for c in row["file"] if ord(c) > 0x7E], [], "a file name is ASCII")
            self.assertTrue(row["family"].startswith(fc.LIST_DISPLAY_NAME + u" "), "what Diacritics' font chooser leaves out")

    def test_has_every_required_character(self):
        """Everything checks/font_characters.json asks for, but the characters listed in NOT_SUPPLIED."""
        parts, counts = required_characters()
        required = set().union(*parts.values())
        self.assertEqual(len(required), counts["all"])
        self.assertGreater(len(required), 40000)
        not_supplied = codes_of(NOT_SUPPLIED)
        missing = [u"U+%04X" % code for code in sorted(required - not_supplied - self.absent) if code not in self.cmap]
        self.assertEqual(missing, [], "the bundled font lacks these")
        self.assertEqual([u"U+%04X" % code for code in sorted(not_supplied) if code in self.cmap], [],
                         "a character the font draws now: take it out of NOT_SUPPLIED")
        self.assertEqual(sorted(not_supplied - required), [], "NOT_SUPPLIED lists only characters asked for")
        self.assertEqual(codes_of(self.info["not_covered"]), not_supplied, "language_font.json lists the same")
        self.assertEqual(sum(self.info["not_covered_blocks"].values()), len(not_supplied))

    def test_every_part_counted(self):
        """language_font.json's counts: [asked, drawn] for the whole and for each part."""
        parts, counts = required_characters()
        not_supplied = codes_of(NOT_SUPPLIED)
        for part in PARTS:
            self.assertEqual(self.info["counts"][part], [counts[part], len(parts[part] - not_supplied)], part)
        self.assertEqual(self.info["counts"]["all"], [counts["all"], counts["all"] - len(not_supplied)])
        for part in ("names", "other_names"):  # (what a row or a tooltip always shows is whole)
            self.assertEqual(sorted(parts[part] & not_supplied), [], part)

    def test_bulk_scripts_bundled(self):
        """What the first builds left to the system's fonts: the Hangul syllables, the ideographs of
        Chinese, Japanese, and Korean, cuneiform, hieroglyphs, and the mathematical alphanumerics."""
        self.assertEqual([code for code in range(0xAC00, 0xD7A4) if code not in self.cmap], [])
        for low, high, least in ((0x4E00, 0x9FFF, 3600), (0x12000, 0x1254F, 1200), (0x13000, 0x1345F, 1000),
                                 (0x1D400, 0x1D7FF, 900)):
            self.assertGreaterEqual(len([code for code in range(low, high + 1) if code in self.cmap]), least,
                                    "U+%04X to U+%04X" % (low, high))

    def test_first_column_whole(self):
        first, _ = shown_characters()
        missing = [u"U+%04X" % code for code in sorted(first) if code not in self.cmap]
        self.assertEqual(missing, [], "every name, autonym, and script heading in the one font")

    def test_missing_column_whole_but_what_no_font_has(self):
        _, everything = shown_characters()
        not_supplied = codes_of(NOT_SUPPLIED)
        missing = [u"U+%04X" % code for code in sorted(everything)
                   if code not in self.cmap and code not in not_supplied and not is_format(code)]
        self.assertEqual(missing, [], "every orthography's characters, both files'")

    def test_sources_add_up_to_required(self):
        supplied = sorted(code for source in self.sources for code in codes_of(source["code_points"]))
        self.assertEqual(supplied, sorted(codes_of(self.info["required"])), "each character from one source")
        for source in self.info["fonts"]:
            self.assertEqual(len(codes_of(source["code_points"])), source["count"], source["family"])
            self.assertEqual(len(source["sha256"]), 64, source["family"])
            if source["family"] in NOTO_RELEASES:
                self.assertTrue(source["file"].startswith(NOTO_RELEASES[source["family"]]), source["file"])
            elif source["family"].startswith(u"Noto"):
                self.assertIn(u"/blob/", source["file"], "pinned by its repository's commit")
            else:
                self.assertTrue(source["file"].startswith(RELEASES), "pinned by its release: %s" % source["file"])
        for address, digest in self.info["archives"].items():
            self.assertTrue(address.startswith(RELEASES + tuple(NOTO_RELEASES.values())), address)
            self.assertEqual(len(digest), 64, address)
        for label, row in self.files.items():  # (each subset in one of the five)
            mine = [source for source in self.info["fonts"] if source["font"] == label]
            self.assertEqual(len(mine), row["sources"], label)
            self.assertLess(sum(source["glyphs"] for source in mine), MAX_GLYPHS, label)
            if label in self.present:
                self.assertEqual(set(code for source in mine for code in codes_of(source["code_points"])) - self.cmaps[label],
                                 set(), label)
        self.assertEqual(set(source["font"] for source in self.info["fonts"]), set(self.files))

    def test_each_source_whole_in_one_font_but_one(self):
        """Each source is whole in one font, but the one of ELSEWHERE: Unicodia Funky is cut in two
        subsets, its four combining parentheses in the Essential font and the rest where it was. The
        second subset is its source's in every other respect."""
        places = {}
        for source in self.sources:
            places.setdefault(source["family"], []).append((source["font"], source["subset"]))
        self.assertEqual(sorted(family for family, found in places.items() if len(found) > 1), sorted(ELSEWHERE))
        self.assertEqual(self.info["elsewhere"], dict((family, list(found)) for family, found in ELSEWHERE.items()))
        for family, (label, listed) in ELSEWHERE.items():
            self.assertEqual(sorted(places[family]), sorted([(label, u"elsewhere"), (u"Extended General", u"own")]))
            second = [s for s in self.sources if s["family"] == family and s["subset"] == u"elsewhere"][0]
            own = [s for s in self.sources if s["family"] == family and s["subset"] == u"own"][0]
            self.assertEqual(codes_of(second["code_points"]), codes_of(listed), family)
            self.assertEqual(codes_of(own["code_points"]) & codes_of(listed), set())
            self.assertEqual([second[key] for key in ("file", "sha256", "version", "copyright", "layout")],
                             [own[key] for key in ("file", "sha256", "version", "copyright", "layout")],
                             "one source: the same file, pin, license, and kind of layout")
            self.assertEqual(sorted(codes_of(listed) - self.cmaps[label]), [], "drawn by the font they went to")
            self.assertEqual(sorted(codes_of(listed) & self.cmaps[own["font"]]), [], "and by it alone")
        self.assertEqual(set(source["subset"] for source in self.info["fonts"]), set([u"own", u"elsewhere", u"name"]))

    def test_other_sources_last_resort_only(self):
        """Every character comes from a Noto font but those listed in OTHER_SOURCES, which no Noto font
        of the pinned sources has; those fonts keep their character map alone, but a script's own font
        (SCRIPT_FONTS), which keeps its layout."""
        found = {}  # {family: its subsets' rows} (Unicodia Funky has two, see ELSEWHERE)
        for source in self.sources:
            if not source["family"].startswith(u"Noto ") or source["family"] in OTHER_SOURCES:
                found.setdefault(source["family"], []).append(source)
        self.assertEqual(sorted(found), sorted(OTHER_SOURCES))
        for family, rows in found.items():
            supplied = sorted(code for source in rows for code in codes_of(source["code_points"]))
            self.assertEqual(supplied, sorted(codes_of(OTHER_SOURCES[family])), family)
            for source in rows:
                if family in SCRIPT_FONTS:
                    self.assertEqual(source["layout"], u"every feature but the vertical ones", family)
                    self.assertGreater(source["glyphs"], source["count"], family)
                else:
                    self.assertEqual(source["layout"], u"none (character map only)", family)
                    self.assertGreater(source["glyphs"], source["count"], "%s: its characters and .notdef" % family)
                    self.assertLessEqual(source["glyphs"], source["count"] + 4, "%s: and the parts a few are made of" % family)
            self.assertEqual(sorted(source["font"] for source in rows),
                             [u"Essential"] if family == u"Andika"
                             else sorted([u"Extended General", ELSEWHERE[family][0]]) if family in ELSEWHERE
                             else [u"Extended General"], family)
        for family in OTHER_SOURCES:
            self.assertEqual([u"U+%04X" % code for code in sorted(codes_of(OTHER_SOURCES[family])) if code not in self.cmap], [])

    def test_no_source_is_a_bitmap_font(self):
        """Sixteen glyphs were a 16 by 16 bitmap's pixels (GNU Unifont) until outline fonts replaced
        them: no source is a bitmap font by its name, and each font of OTHER_SOURCES draws curves,
        which a bitmap's pixels never are."""
        for source in self.info["fonts"]:
            named = (source["family"] + u" " + source["file"]).lower()
            self.assertEqual([word for word in BITMAP_FONTS if word in named], [], source["family"])
        self.assertNotIn(u"unifont", self.info["sources"].lower())
        with io.open(LICENSE_FILE, encoding="utf-8") as handle:
            self.assertNotIn(u"unifont", handle.read().lower(), "its license left with it")
        for tables in self.fonts.values():
            for tag in ("EBDT", "EBLC", "CBDT", "CBLC", "sbix"):
                self.assertNotIn(tag, tables)
        for family, listed in sorted(OTHER_SOURCES.items()):
            curves = sum(self.curves(code) for code in codes_of(listed))
            self.assertGreater(curves, 0, "%s: outlines with curves" % family)
        self.assertGreater(self.curves(0x1AC1), 0, "a combining parenthesis is a curve")
        self.assertEqual(self.curves(0x2588), 0, "(a full block has none: the count tells them apart)")
        # Two sources whose outlines were changed on the way in: Daarage's cubic curves became quadratic
        # ones, and Noto Znamenny Musical Notation lost its color layers, not its outlines.
        self.assertGreater(sum(self.curves(code) for code in range(0x11380, 0x1138A)), 0, "Tulu-Tigalari letters")
        empty = [u"U+%04X" % code for code in range(0x1CF50, 0x1CFC4)
                 if not glyph_length(self.font_of(code), cmap_glyphs(self.font_of(code)["cmap"])[code])]
        self.assertEqual(empty, [], "every Znamenny sign has an outline of its own")

    def test_marks_meet_across_sources(self):
        """Each character comes from one source, and no source's positioning knows another's glyphs:
        Andika's letters took Noto Sans's marks at no anchor, and the four combining parentheses sat
        at one fixed place. The build carries their own anchors into Noto Sans's lookups: the letters
        are bases of the lookups that hold the acute and the dot below, and the parentheses are marks
        of lookups whose bases include a, H, and the dotted circle."""
        self.assertEqual(self.files[u"Essential"]["anchors_carried"], ANCHORS_CARRIED)
        self.assertEqual([self.files[label]["anchors_carried"] for label in LABELS[1:]], [{}, {}, {}, {}])
        glyphs = cmap_glyphs(self.tables["cmap"])
        to_base = attachments(self.tables["GPOS"], 4)
        for mark, letters in ((0x0301, ANCHORS_CARRIED[u"Andika"][u"bases"]), (0x0323, ANCHORS_CARRIED[u"Andika"][u"bases"])):
            bases = set().union(*[found for marks, found in to_base if glyphs[mark] in marks])
            self.assertEqual([u"U+%04X" % code for code in sorted(codes_of(letters)) if glyphs[code] not in bases], [],
                             "bases of U+%04X" % mark)
            self.assertIn(glyphs[0x61], bases, "the lookup that places it on Noto Sans's own letters")
        # The four combining parentheses (a second subset of Unicodia Funky, in this font for that):
        # marks of a mark-to-base lookup whose bases are Noto Sans's letters and dotted circle, and of
        # a mark-to-mark lookup whose bases are its other marks (one stands clear of an acute).
        to_mark = attachments(self.tables["GPOS"], 6)
        for mark in sorted(codes_of(ANCHORS_CARRIED[u"UnicodiaFunky"][u"marks"])):
            self.assertIn(mark, self.cmaps[u"Essential"])
            self.assertNotIn(mark, self.cmaps[u"Extended General"], "U+%04X: in one font" % mark)
            bases = set().union(*[found for marks, found in to_base if glyphs[mark] in marks])
            for letter in (0x61, 0x48, 0x25CC, 0x430, 0x3B1, 0x25B):
                self.assertIn(glyphs[letter], bases, "U+%04X on U+%04X" % (mark, letter))
            over = set().union(*[found for marks, found in to_mark if glyphs[mark] in marks])
            self.assertIn(glyphs[0x0301 if mark in (0x1AC1, 0x1AC2) else 0x0323], over, "U+%04X over another mark" % mark)
            self.assertEqual(glyph_class(self.tables["GDEF"], glyphs[mark]), 3, "U+%04X: a mark to the shaper" % mark)

    def test_static_truetype_named_apart(self):
        self.assertEqual(self.info["family"], fc.LIST_DISPLAY_NAME, "the five together, as the tools name them")
        self.assertEqual(self.info["units_per_em"], 1000, "every subset scaled to one em")
        families = []
        for label, tables in sorted(self.fonts.items()):
            for tag in ("glyf", "cmap", "name", "OS/2", "GSUB", "GPOS"):
                self.assertIn(tag, tables, label)
            for tag in ("fvar", "gvar", "COLR", "CPAL", "CFF ", "CFF2", "sbix", "SVG "):
                self.assertNotIn(tag, tables, "FontLab's Qt 5 needs a plain static font")
            for tag in ("fpgm", "prep", "cvt ", "DSIG", "MATH", "vhea", "vmtx", "kern"):
                self.assertNotIn(tag, tables, "nothing the tool does not use: no hinting, no vertical metrics")
            self.assertEqual(sorted(tables), sorted(self.files[label]["tables"]), label)
            self.assertEqual(struct.unpack(">H", tables["head"][18:20])[0], 1000, label)
            found = names(tables["name"])
            self.assertEqual(found[1], self.files[label]["family"])
            self.assertLessEqual(len(found[1]), GDI_FAMILY_LIMIT, "Windows, and so Qt, registers no longer family")
            self.assertEqual(found[4], self.files[label]["full_family"], "the full name of a Regular font is its family's")
            if found[1] != found[4]:  # (a family too long for Windows: the full one is the typographic family)
                self.assertEqual((found.get(16), found.get(17)), (found[4], u"Regular"), label)
            else:
                self.assertNotIn(16, found, label)
            # (FreeLang and what it holds; the fourth family's en dash is a hyphen in its label)
            self.assertEqual(found[4].replace(u"\N{EN DASH}", u"-"), fc.LIST_DISPLAY_NAME + u" " + label)
            self.assertEqual([c for c in found[6] if not u"!" <= c <= u"~"], [], "a PostScript name is ASCII")
            self.assertEqual(found[6], found[4].replace(u"\N{EN DASH}", u"").replace(u" ", u"") + u"-Regular")
            self.assertEqual(found[2], u"Regular")
            named = found[1] + found[4] + found[6]
            self.assertNotIn(u"Noto", named, "never mistaken for an installed Noto font")
            self.assertNotIn(u"Source", named, "nor uses the CJK fonts' Reserved Font Name")
            for reserved in (u"Andika", u"SIL", u"Kanchenjunga", u"Kedebideri", u"Padauk", u"Namkio", u"Deemawso",
                             u"BabelStone", u"Unicodia"):  # (Reserved Font Names, and Unicodia's name)
                self.assertNotIn(reserved.lower(), named.lower(), reserved)
            self.assertIn(u"Open Font License", found[13])
            families.append(found[1])
        self.assertEqual(len(set(families)), len(self.present), "a family each: Qt falls back from one to the next")
        self.assertEqual(self.files[u"Essential"]["family"], fc.LIST_FAMILY)

    def test_glyphs_fit_and_map_past_the_basic_plane(self):
        for label, tables in sorted(self.fonts.items()):
            glyphs = struct.unpack(">H", tables["maxp"][4:6])[0]
            self.assertLess(glyphs, MAX_GLYPHS, label)
            self.assertEqual(glyphs, self.files[label]["glyphs"], "language_font.json describes this build")
            formats = cmap_formats(tables["cmap"])
            self.assertIn(12, formats, "characters past U+FFFF (%s)" % label)
            self.assertIn(4, formats)
            self.assertEqual(formats, self.files[label]["cmap_formats"])
        for code in (0x12000, 0x13000, 0x17000, 0x1D400, 0x16F00):
            self.assertIn(code, self.cmaps[u"Extended General"], "U+%04X" % code)

    def test_within_both_limits(self):
        """A font holds 65,535 glyphs, and its lookups must lie within 65,535 bytes of their list: the
        build counts both for each font before merging it, stops past either, and warns from nine
        tenths on. language_font.json records what each font needs, counted here again from its
        tables; Noto Sans Duployan's lookups are why it has a font alone."""
        self.assertEqual(self.info["limits"], {u"glyphs": MAX_GLYPHS, u"lookup_bytes": MAX_LOOKUP_BYTES, u"warn_at": 0.9})
        for label in LABELS:
            row = self.files[label]
            mine = [source for source in self.info["fonts"] if source["font"] == label]
            for tag in ("GSUB", "GPOS"):
                sizes = [source["lookup_bytes"][tag] for source in mine if source["lookup_bytes"][tag]]
                self.assertEqual(row["lookup_bytes"][tag], sum(sizes) - 2 * (len(sizes) - 1) if sizes else 0,
                                 "%s %s: the sum of its sources'" % (label, tag))
                self.assertLessEqual(row["lookup_bytes"][tag], MAX_LOOKUP_BYTES, label)
                if label in self.present:
                    self.assertEqual(lookup_bytes(self.fonts[label][tag]), row["lookup_bytes"][tag], "%s %s" % (label, tag))
            self.assertEqual(row["lookup_bytes_left"], MAX_LOOKUP_BYTES - max(row["lookup_bytes"].values()), label)
            self.assertEqual(row["glyphs"], sum(source["glyphs"] for source in mine), label)
            near = row["glyphs"] >= 0.9 * MAX_GLYPHS or max(row["lookup_bytes"].values()) >= 0.9 * MAX_LOOKUP_BYTES
            self.assertEqual(bool(row["warnings"]), near, "%s: a warning from nine tenths of a limit on" % label)
        self.assertGreater(self.files[u"Essential"]["lookup_bytes_left"], 30000, "room again, without Noto Serif Tibetan")
        duployan = self.files[u"Extended Duployan"]
        self.assertGreater(duployan["lookup_bytes"]["GSUB"], 50000, "most of a table's reach, alone")
        self.assertEqual((duployan["sources"], duployan["optional"], duployan["own_layout"]), (2, True, True))

    def test_claims_its_writing_systems(self):
        """Qt 5 takes another family for a script whose writing system the font does not claim: each
        font claims what it draws."""
        pages = dict((label, struct.unpack(">L", tables["OS/2"][78:82])[0]) for label, tables in self.fonts.items())
        for name, bit in CODE_PAGE_BITS.items():
            label = u"CJK" if name in ("Japanese", "Chinese", "Korean") else u"Essential"
            self.assertTrue(pages[label] >> bit & 1, name)
        ranges = dict((label, struct.unpack(">4L", tables["OS/2"][42:58])) for label, tables in self.fonts.items())
        for bit, label in ((0, u"Essential"), (7, u"Essential"), (9, u"Essential"), (10, u"Essential"), (11, u"Essential"),
                           (13, u"Essential"), (15, u"Essential"), (24, u"Essential"), (26, u"Essential"), (56, u"CJK"),
                           (70, u"Extended Mongolian-Tibetan"), (81, u"Extended Mongolian-Tibetan"),
                           (71, u"Extended General"), (72, u"Essential"), (73, u"Essential"),
                           (74, u"Essential"), (80, u"Essential"), (0, u"CJK"), (0, u"Extended General")):
            self.assertTrue(ranges[label][bit // 32] >> (bit % 32) & 1, "Unicode range bit %d (%s)" % (bit, label))

    def test_one_line_for_the_five(self):
        """A row that mixes the fonts (a Latin name, a Korean autonym, a rare script's characters) sits
        on one line: the same ascent and descent in the five, measured once over what all five draw."""
        for label, tables in sorted(self.fonts.items()):
            ascent, descent, gap = struct.unpack(">hhh", tables["hhea"][4:10])
            self.assertEqual([ascent, descent], self.info["line"], label)
            self.assertEqual([ascent, descent], self.files[label]["line"], label)
            self.assertEqual(gap, 0, label)
            os2 = tables["OS/2"]
            win_ascent, win_descent = struct.unpack(">HH", os2[74:78])
            self.assertEqual((win_ascent, -win_descent), (ascent, descent), "Windows draws the same line")
            self.assertEqual(struct.unpack(">hhh", os2[68:74]), (ascent, descent, 0), "and the typographic one")
        self.assertTrue(self.info["shaping_checked"], "built with uharfbuzz: the line measured, the shaping checked")
        self.assertTrue(self.info["made_with"]["uharfbuzz"])
        self.assertLessEqual(self.files[u"Essential"]["shaping_differences"], 7, "no more than the seven known (docs/FONT-CHECK.md)")
        self.assertEqual([self.files[label]["shaping_differences"] for label in LABELS[1:]], [0, 0, 0, 0])
        self.assertEqual([self.files[label]["line"] for label in LABELS], [self.info["line"]] * 5, "an absent font's too")

    def test_small_enough(self):
        self.assertEqual(sorted(MAX_SIZES), sorted(self.files))
        for label, row in sorted(self.files.items()):
            self.assertLess(row["size"], MAX_SIZES[label], label)
            if label in self.present:
                self.assertEqual(os.path.getsize(os.path.join(FOLDER, row["file"])), row["size"],
                                 "language_font.json describes this build")

    def test_layout_kept_where_text_is_set(self):
        """A source keeps its layout only if it draws a language's name, other name, or orthography
        (running text); one that draws a character set's characters alone, shown one at a time, keeps
        its character map. The stated exception: Noto Sans Mongolian and Noto Sans Duployan, which the
        rule had cut, keep their layout whole in fonts of their own (Mongolian with Tibetan), so that
        their running text shapes; no other font's budget could afford them."""
        parts, _ = required_characters()
        in_text = parts["names"] | parts["other_names"] | parts["orthographies"]
        for source in self.sources:
            if source["layout"] != u"none (character map only)" and source["family"] not in OWN_LAYOUT:
                self.assertTrue(in_text & codes_of(source["code_points"]), source["family"])
        alone = dict((source["family"], source) for source in self.sources if source["layout"] == u"none (character map only)")
        for family in (u"Noto Sans Grantha", u"Noto Sans Soyombo", u"Noto Sans Math"):
            self.assertIn(family, alone)
        kept = dict((source["family"], source) for source in self.sources if source["layout"] != u"none (character map only)")
        for family in (u"Noto Sans", u"Noto Serif Tibetan", u"Noto Sans Devanagari", u"Noto Sans KR", u"Noto Sans Tai Tham"):
            self.assertIn(family, kept)
        for family, label in sorted(OWN_LAYOUT.items()):
            self.assertIn(family, kept, "its layout restored")
            self.assertEqual(kept[family]["font"], label, family)
            self.assertFalse(in_text & codes_of(kept[family]["code_points"]), "%s: the exception, not the rule" % family)
            self.assertTrue(self.files[label]["own_layout"], label)
            self.assertGreater(kept[family]["glyphs"], 10 * kept[family]["count"], "%s: the forms its letters join in" % family)
            self.assertGreater(kept[family]["lookup_bytes"]["GSUB"], 5000, family)
        self.assertEqual(kept[u"Noto Serif Tibetan"]["font"], u"Extended Mongolian-Tibetan")
        self.assertEqual(sorted(label for label in LABELS if self.files[label]["own_layout"]), sorted(set(OWN_LAYOUT.values())))
        self.assertEqual(self.files[u"Extended Mongolian-Tibetan"]["sources"], 3, "Tibetan, Mongolian, and its name's letters")

    def test_duployan_drawn_by_the_optional_font_alone(self):
        """The tools work without the Duployan font's file. With it, Duployan's characters are drawn
        by it; without it, by none of the others (Qt takes a system font, or shows boxes), and every
        other character is drawn as before."""
        label = u"Extended Duployan"
        self.assertEqual(self.files[label]["file"], fc.LIST_FONT_FALLBACKS[-1][0], "the last one fallen back to")
        duployan = set(code for source in self.sources if source["font"] == label for code in codes_of(source["code_points"]))
        self.assertEqual(len(duployan), 143)
        self.assertEqual(sorted(duployan - set(range(0x1BC00, 0x1BCA4))), [], "the Duployan block and its shorthand controls")
        others = set().union(*[self.cmaps[other] for other in self.present if other != label])
        self.assertEqual(sorted(duployan & others), [], "drawn by no other font")
        parts, _ = required_characters()
        self.assertEqual(sorted(duployan & (parts["names"] | parts["other_names"] | parts["orthographies"])), [],
                         "a character set's alone: no language's row needs the file")
        self.assertEqual(sorted(set().union(*parts.values()) - codes_of(NOT_SUPPLIED) - duployan - others), [],
                         "without the file, everything else is still drawn")
        if label in self.present:
            self.assertEqual(sorted(duployan - self.cmaps[label]), [], "with the file: drawn by it")
            self.assertEqual(sorted(self.cmaps[label] - duployan - self.names[label]), [], "and it draws nothing else but its name")
        else:
            self.assertEqual(self.absent, duployan)

    def test_license_beside_it(self):
        with io.open(LICENSE_FILE, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(u"SIL OPEN FONT LICENSE", text.upper())
        for source in self.info["fonts"]:
            self.assertIn(source["copyright"], text)
            self.assertIn(source["family"], text)


class FakeDatabase(object):
    """QFontDatabase's static calls, as Font Check makes them."""
    known, added, refuse = [], [], False  # (refuse: True for every file, or the file names refused)

    def families(self):
        return list(FakeDatabase.known)

    @staticmethod
    def addApplicationFont(path):
        if FakeDatabase.refuse is True or os.path.basename(path) in (FakeDatabase.refuse or ()):
            return -1
        FakeDatabase.added.append(path)
        return 6 + len(FakeDatabase.added)

    @staticmethod
    def addApplicationFontFromData(data):
        return -1

    @staticmethod
    def applicationFontFamilies(index):
        if not 7 <= index < 7 + len(FakeDatabase.added):
            return []
        name = os.path.basename(FakeDatabase.added[index - 7])
        return [dict(fc.LIST_FONT_FALLBACKS).get(name, fc.LIST_FAMILY)]


class FakeFont(object):
    substituted, inserted = {}, []  # (QFont's static substitutions: {family: [families]}, and each call made)

    @staticmethod
    def substitutes(family):
        return list(FakeFont.substituted.get(family, []))

    @staticmethod
    def insertSubstitutions(family, families):
        FakeFont.inserted.append((family, list(families)))
        FakeFont.substituted.setdefault(family, []).extend(families)

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
        FakeFont.substituted, FakeFont.inserted = {}, []
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
        """The five files, each once a session, and the four others given to Qt once as the first
        family's substitutes, in their order: a font of that one family then draws what it lacks
        from them. The fourth family is registered under its name with an en dash."""
        fallbacks = [family for _, family in fc.LIST_FONT_FALLBACKS]
        self.with_files([fc.LIST_FONT_FILE] + [name for name, _ in fc.LIST_FONT_FALLBACKS])
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual([os.path.basename(path) for path in FakeDatabase.added],
                         [fc.LIST_FONT_FILE] + [name for name, _ in fc.LIST_FONT_FALLBACKS])
        self.assertEqual(len(set(os.path.dirname(path) for path in FakeDatabase.added)), 1, "the five side by side")
        self.assertEqual(FakeFont.inserted, [(fc.LIST_FAMILY, fallbacks)])
        self.assertEqual(fallbacks, [u"FreeLang CJK", u"FreeLang Extended General",
                                     u"FreeLang Mongolian\N{EN DASH}Tibetan", u"FreeLang Extended Duployan"])
        for family in [fc.LIST_FAMILY] + fallbacks:  # (a longer one Qt never lists: GDI_FAMILIES of the build)
            self.assertLessEqual(len(family), GDI_FAMILY_LIMIT, family)
        self.assertEqual([row["full_family"] for row in info()["files"]][3], u"FreeLang Extended Mongolian\N{EN DASH}Tibetan",
                         "the owner's name for it, kept as its typographic family and full name")
        self.assertEqual([name for name, _ in fc.LIST_FONT_FALLBACKS],
                         ["FreeLang-CJK.ttf", "FreeLang-Extended-General.ttf", "FreeLang-Extended-Mongolian-Tibetan.ttf",
                          "FreeLang-Extended-Duployan.ttf"], "file names in ASCII: FontLab's Python 2.7 opens ANSI paths")
        FakeDatabase.known = [fc.LIST_FAMILY] + fallbacks
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual(len(FakeDatabase.added), 5, "already known to Qt: not added again")
        self.assertEqual(len(FakeFont.inserted), 1, "nor substituted again")
        self.assertEqual(fc.LIST_DISPLAY_NAME, u"FreeLang", "the name a tool shows for the five")
        self.assertEqual(fc.LIST_FAMILY, u"FreeLang Essential")
        for family in [fc.LIST_FAMILY] + fallbacks:  # (Diacritics leaves out of its chooser what starts so)
            self.assertTrue(family.startswith(fc.LIST_DISPLAY_NAME + u" "), family)

    def with_files(self, names):
        """Font Check finding its font in the test's folder, which holds files of these names (the fakes
        read none of them)."""
        for name in names:
            with open(os.path.join(self.folder, name), "wb") as handle:
                handle.write(b"font")
        found, folder = fc.list_font_path, self.folder
        fc.list_font_path = lambda here=None: os.path.join(folder, fc.LIST_FONT_FILE)
        self.addCleanup(setattr, fc, "list_font_path", found)

    def test_the_optional_font_registered_when_present(self):
        """The four fallback fonts are optional (here, the last). With its file beside the others it is
        registered and is the last substitute; without it the four others are registered as before,
        nothing is asked of Qt for it, and nothing raises."""
        optional = fc.LIST_FONT_FALLBACKS[-1]
        self.assertEqual([row["file"] for row in info()["files"] if row["optional"]],
                         [name for name, _ in fc.LIST_FONT_FALLBACKS])
        others = [fc.LIST_FONT_FILE] + [name for name, _ in fc.LIST_FONT_FALLBACKS[:-1]]
        self.with_files(others)
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual([os.path.basename(path) for path in FakeDatabase.added], others)
        self.assertEqual(FakeFont.inserted, [(fc.LIST_FAMILY, [family for _, family in fc.LIST_FONT_FALLBACKS[:-1]])])
        # The file arrives (an install with it) in a later session: registered, and the last substitute.
        FakeDatabase.known, FakeDatabase.added, FakeFont.substituted, FakeFont.inserted = [], [], {}, []
        self.with_files([optional[0]])
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual(os.path.basename(FakeDatabase.added[-1]), optional[0])
        self.assertEqual(FakeFont.inserted[0][1][-1], optional[1])
        self.assertEqual(len(FakeFont.inserted[0][1]), 4)

    def test_a_fallback_refused_or_missing_leaves_the_rest(self):
        """Without one of the fallback files, or with one Qt refuses, the first font is still the
        family: the characters of the other are left to the system's fonts, and nothing raises."""
        FakeDatabase.refuse = (fc.LIST_FONT_FALLBACKS[0][0],)
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual(FakeFont.inserted, [(fc.LIST_FAMILY, [family for _, family in fc.LIST_FONT_FALLBACKS[1:]
                                                               if os.path.isfile(os.path.join(FOLDER, dict(
                                                                   (f, n) for n, f in fc.LIST_FONT_FALLBACKS)[family]))])])
        FakeDatabase.known, FakeDatabase.added, FakeDatabase.refuse = [], [], [name for name, _ in fc.LIST_FONT_FALLBACKS]
        FakeFont.substituted, FakeFont.inserted = {}, []
        self.assertEqual(fc.register_list_font(FakeCore, FakeGui), fc.LIST_FAMILY)
        self.assertEqual(FakeFont.inserted, [], "no substitute: nothing inserted")

        class NoSubstitutions(object):  # (a Qt without the calls: the first font alone, no error)
            QFontDatabase = FakeDatabase
        FakeDatabase.known, FakeDatabase.added, FakeDatabase.refuse = [], [], False
        self.assertEqual(fc.register_list_font(FakeCore, NoSubstitutions), fc.LIST_FAMILY)

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

    def test_pictures_of_missing_characters_in_the_family(self):
        """The pictures showed boxes for Canadian syllabics in the interface font: they are drawn in
        the bundled one, which has every orthography's characters."""
        class Dialog(object):
            def __init__(self, family):
                self.list_family, self.dialog = family, FakeTree(FakeFont(points=9.0))

        method = fc.FontCheckDialog.picture_font
        method = getattr(method, "__func__", method)
        self.assertEqual(method(Dialog(fc.LIST_FAMILY)).family, fc.LIST_FAMILY)
        self.assertEqual(method(Dialog(None)).family, u"MS Shell Dlg 2", "without the file: the dialog's font, as before")


class TooltipFontTests(unittest.TestCase):
    """Tooltips showed boxes for an autonym and for the missing characters of scripts the interface
    font lacks (Canadian syllabics): their names and characters are set in the bundled font, which has
    them all but the characters of NOT_SUPPLIED."""

    @classmethod
    def setUpClass(cls):
        cls.cmap = set()  # (the files together: Qt falls back from the first to the others)
        for name in [fc.LIST_FONT_FILE] + [name for name, _ in fc.LIST_FONT_FALLBACKS]:
            if os.path.isfile(os.path.join(FOLDER, name)):
                cls.cmap.update(cmap_codes(read_tables(os.path.join(FOLDER, name))["cmap"]))
            else:  # (the optional font's file is not here: its characters, a character set's, are left to the system)
                found = info()
                label = [row["font"] for row in found["files"] if row["file"] == name and row["optional"]][0]
                for source in found["fonts"]:
                    if source["font"] == label:
                        cls.cmap.update(codes_of(source["code_points"]))

    def drawn(self, code):
        return code in self.cmap or code == 0x20 or is_format(code)

    def test_tooltip_names_the_family(self):
        html = fc.tip_html(u"Eastern Canadian Inuktitut", None, fc.LIST_FAMILY)
        self.assertEqual(html, u"<span style=\"font-family:'%s'\">Eastern Canadian Inuktitut</span>" % fc.LIST_FAMILY)
        self.assertIn(u"<td style=\"font-family:'%s'\">" % fc.LIST_FAMILY, fc.tip_html(u"x", 400, fc.LIST_FAMILY))
        self.assertNotIn(u"font-family", fc.tip_html(u"Check characters or select a row first."),
                         "a button's tooltip keeps Qt's own font")
        self.assertNotIn(u"font-family", fc.tip_html(u"x", 400, None), "without the file: Qt's own font, as before")

    def test_every_language_tooltip_drawn(self):
        """A font with no character at all: each language's tooltip names every one of its characters."""
        languages = fc.load_languages()  # (both orthography files)
        self.assertGreater(len(languages), 2000)
        font = fc.FontCharacters([])
        not_supplied = codes_of(NOT_SUPPLIED)
        shown, boxes = set(), set()
        for language in languages + fc.load_character_sets():
            for code in fc.code_points(fc.coverage_tip(fc.check_language(language, font))):
                shown.add(code)
                if not self.drawn(code) and code not in not_supplied:
                    boxes.add(code)
        self.assertEqual([u"U+%04X" % code for code in sorted(boxes)], [],
                         "every tooltip whole but for the characters no source font has")
        self.assertGreater(len(shown), 25000, "the Hangul syllables, ideographs, cuneiform, and hieroglyphs among them")
        inuktitut = [l for l in languages if l.iso == u"ike"][0]
        tip = fc.coverage_tip(fc.check_language(inuktitut, font))
        self.assertTrue(all(self.drawn(code) for code in fc.code_points(tip)), "the tooltip the owner saw as boxes")

    def test_other_names_and_families_drawn(self):
        families = fc.load_families(os.path.join(CHECKS, fc.FAMILIES_FILE))
        for name, _ in families.nodes:
            self.assertTrue(all(self.drawn(code) for code in fc.code_points(u"%s" % name)), name)
        names = [u"%s" % name for found in families.aliases.values() for name in found]
        self.assertGreater(len(names), 15000)
        broken = [name for name in names if not all(self.drawn(code) for code in fc.code_points(name))]
        self.assertEqual(broken, [], "the languages' other names, those in Chinese, Japanese, and Korean too")


if __name__ == "__main__":
    unittest.main()
