# -*- coding: utf-8 -*-
"""The font info FreeLab keeps in step with its own writes: a helper module, no window of its own.

A tool that adds glyphs or code points (Glyph Compose and its Glyph generation tab, Font Builder,
Feature Code's forms) changes what the font covers, and the font info declares that coverage: the OS/2
Unicode ranges and code pages. FontLab 7's export writes them as the font info holds them, never
recalculated (live 2026-11-18: Bellefair's ranges set to Basic Latin alone were exported so). So the
tool updates them, along the rule the owner chose: a field changes only where the write itself changed
what it follows. A bit is set when the write brought its range or code page into the font, cleared when
the write took the last of it out, and every other bit is left as declared, hand-set ones included.
The Win ascent and descent are where Windows clips the glyphs: a glyph the write drew above or below
them raises them to its ink (never lowered). FontLab exports them from each master's Safe top and Safe
bottom, not from the font info's copy (ExportedInfo), so each master's own are raised, recorded, and
put back in that master (apply_win).

FontLab's History takes the Unicode ranges and code pages back with the write that changed them, and
redoes them (live 2026-11-18: they are the font's coding, fgPackage.coding, which a step of the whole
font records), but not the Win values (nor the other OS/2 metrics: found live by Font Check, and again
here). So the Win changes are kept for the session instead (record), and follow puts each one in step
with the glyphs again after an undo or a redo, unless it was changed by hand since (it is then left).

Valid Python 2.7 (FontLab 7) and Python 3 (the tests)."""

from __future__ import absolute_import, division, print_function

import bisect
import math
import sys
import unicodedata

INFO_UNICODE = "openTypeOS2UnicodeRanges"
INFO_PAGES = "openTypeOS2CodePageRanges"
INFO_WIN_ASCENT = "openTypeOS2WinAscent"
INFO_WIN_DESCENT = "openTypeOS2WinDescent"
NON_PLANE_0 = 57  # the Unicode range bit of every character past U+FFFF (with its own block's bit)
ASCII_LETTERS = frozenset(list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)))

# The OS/2 table's Unicode ranges (OpenType 1.9), by bit: the blocks of each. A bit is set when the
# font has a character in one of its blocks (as fontTools' recalcUnicodeRanges sets it).
UNICODE_RANGES = (
    ((u"Basic Latin", 0x0000, 0x007F),),  # 0
    ((u"Latin-1 Supplement", 0x0080, 0x00FF),),  # 1
    ((u"Latin Extended-A", 0x0100, 0x017F),),  # 2
    ((u"Latin Extended-B", 0x0180, 0x024F),),  # 3
    (  # 4
        (u"IPA Extensions", 0x0250, 0x02AF),
        (u"Phonetic Extensions", 0x1D00, 0x1D7F),
        (u"Phonetic Extensions Supplement", 0x1D80, 0x1DBF),
    ),
    ((u"Spacing Modifier Letters", 0x02B0, 0x02FF), (u"Modifier Tone Letters", 0xA700, 0xA71F)),  # 5
    (  # 6
        (u"Combining Diacritical Marks", 0x0300, 0x036F),
        (u"Combining Diacritical Marks Supplement", 0x1DC0, 0x1DFF),
    ),
    ((u"Greek and Coptic", 0x0370, 0x03FF),),  # 7
    ((u"Coptic", 0x2C80, 0x2CFF),),  # 8
    (  # 9
        (u"Cyrillic", 0x0400, 0x04FF),
        (u"Cyrillic Supplement", 0x0500, 0x052F),
        (u"Cyrillic Extended-A", 0x2DE0, 0x2DFF),
        (u"Cyrillic Extended-B", 0xA640, 0xA69F),
    ),
    ((u"Armenian", 0x0530, 0x058F),),  # 10
    ((u"Hebrew", 0x0590, 0x05FF),),  # 11
    ((u"Vai", 0xA500, 0xA63F),),  # 12
    ((u"Arabic", 0x0600, 0x06FF), (u"Arabic Supplement", 0x0750, 0x077F)),  # 13
    ((u"NKo", 0x07C0, 0x07FF),),  # 14
    ((u"Devanagari", 0x0900, 0x097F),),  # 15
    ((u"Bengali", 0x0980, 0x09FF),),  # 16
    ((u"Gurmukhi", 0x0A00, 0x0A7F),),  # 17
    ((u"Gujarati", 0x0A80, 0x0AFF),),  # 18
    ((u"Oriya", 0x0B00, 0x0B7F),),  # 19
    ((u"Tamil", 0x0B80, 0x0BFF),),  # 20
    ((u"Telugu", 0x0C00, 0x0C7F),),  # 21
    ((u"Kannada", 0x0C80, 0x0CFF),),  # 22
    ((u"Malayalam", 0x0D00, 0x0D7F),),  # 23
    ((u"Thai", 0x0E00, 0x0E7F),),  # 24
    ((u"Lao", 0x0E80, 0x0EFF),),  # 25
    ((u"Georgian", 0x10A0, 0x10FF), (u"Georgian Supplement", 0x2D00, 0x2D2F)),  # 26
    ((u"Balinese", 0x1B00, 0x1B7F),),  # 27
    ((u"Hangul Jamo", 0x1100, 0x11FF),),  # 28
    (  # 29
        (u"Latin Extended Additional", 0x1E00, 0x1EFF),
        (u"Latin Extended-C", 0x2C60, 0x2C7F),
        (u"Latin Extended-D", 0xA720, 0xA7FF),
    ),
    ((u"Greek Extended", 0x1F00, 0x1FFF),),  # 30
    ((u"General Punctuation", 0x2000, 0x206F), (u"Supplemental Punctuation", 0x2E00, 0x2E7F)),  # 31
    ((u"Superscripts And Subscripts", 0x2070, 0x209F),),  # 32
    ((u"Currency Symbols", 0x20A0, 0x20CF),),  # 33
    ((u"Combining Diacritical Marks For Symbols", 0x20D0, 0x20FF),),  # 34
    ((u"Letterlike Symbols", 0x2100, 0x214F),),  # 35
    ((u"Number Forms", 0x2150, 0x218F),),  # 36
    (  # 37
        (u"Arrows", 0x2190, 0x21FF),
        (u"Supplemental Arrows-A", 0x27F0, 0x27FF),
        (u"Supplemental Arrows-B", 0x2900, 0x297F),
        (u"Miscellaneous Symbols and Arrows", 0x2B00, 0x2BFF),
    ),
    (  # 38
        (u"Mathematical Operators", 0x2200, 0x22FF),
        (u"Supplemental Mathematical Operators", 0x2A00, 0x2AFF),
        (u"Miscellaneous Mathematical Symbols-A", 0x27C0, 0x27EF),
        (u"Miscellaneous Mathematical Symbols-B", 0x2980, 0x29FF),
    ),
    ((u"Miscellaneous Technical", 0x2300, 0x23FF),),  # 39
    ((u"Control Pictures", 0x2400, 0x243F),),  # 40
    ((u"Optical Character Recognition", 0x2440, 0x245F),),  # 41
    ((u"Enclosed Alphanumerics", 0x2460, 0x24FF),),  # 42
    ((u"Box Drawing", 0x2500, 0x257F),),  # 43
    ((u"Block Elements", 0x2580, 0x259F),),  # 44
    ((u"Geometric Shapes", 0x25A0, 0x25FF),),  # 45
    ((u"Miscellaneous Symbols", 0x2600, 0x26FF),),  # 46
    ((u"Dingbats", 0x2700, 0x27BF),),  # 47
    ((u"CJK Symbols And Punctuation", 0x3000, 0x303F),),  # 48
    ((u"Hiragana", 0x3040, 0x309F),),  # 49
    ((u"Katakana", 0x30A0, 0x30FF), (u"Katakana Phonetic Extensions", 0x31F0, 0x31FF)),  # 50
    ((u"Bopomofo", 0x3100, 0x312F), (u"Bopomofo Extended", 0x31A0, 0x31BF)),  # 51
    ((u"Hangul Compatibility Jamo", 0x3130, 0x318F),),  # 52
    ((u"Phags-pa", 0xA840, 0xA87F),),  # 53
    ((u"Enclosed CJK Letters And Months", 0x3200, 0x32FF),),  # 54
    ((u"CJK Compatibility", 0x3300, 0x33FF),),  # 55
    ((u"Hangul Syllables", 0xAC00, 0xD7AF),),  # 56
    ((u"Non-Plane 0", 0xD800, 0xDFFF),),  # 57
    ((u"Phoenician", 0x10900, 0x1091F),),  # 58
    (  # 59
        (u"CJK Unified Ideographs", 0x4E00, 0x9FFF),
        (u"CJK Radicals Supplement", 0x2E80, 0x2EFF),
        (u"Kangxi Radicals", 0x2F00, 0x2FDF),
        (u"Ideographic Description Characters", 0x2FF0, 0x2FFF),
        (u"CJK Unified Ideographs Extension A", 0x3400, 0x4DBF),
        (u"CJK Unified Ideographs Extension B", 0x20000, 0x2A6DF),
        (u"Kanbun", 0x3190, 0x319F),
    ),
    ((u"Private Use Area (plane 0)", 0xE000, 0xF8FF),),  # 60
    (  # 61
        (u"CJK Strokes", 0x31C0, 0x31EF),
        (u"CJK Compatibility Ideographs", 0xF900, 0xFAFF),
        (u"CJK Compatibility Ideographs Supplement", 0x2F800, 0x2FA1F),
    ),
    ((u"Alphabetic Presentation Forms", 0xFB00, 0xFB4F),),  # 62
    ((u"Arabic Presentation Forms-A", 0xFB50, 0xFDFF),),  # 63
    ((u"Combining Half Marks", 0xFE20, 0xFE2F),),  # 64
    ((u"Vertical Forms", 0xFE10, 0xFE1F), (u"CJK Compatibility Forms", 0xFE30, 0xFE4F)),  # 65
    ((u"Small Form Variants", 0xFE50, 0xFE6F),),  # 66
    ((u"Arabic Presentation Forms-B", 0xFE70, 0xFEFF),),  # 67
    ((u"Halfwidth And Fullwidth Forms", 0xFF00, 0xFFEF),),  # 68
    ((u"Specials", 0xFFF0, 0xFFFF),),  # 69
    ((u"Tibetan", 0x0F00, 0x0FFF),),  # 70
    ((u"Syriac", 0x0700, 0x074F),),  # 71
    ((u"Thaana", 0x0780, 0x07BF),),  # 72
    ((u"Sinhala", 0x0D80, 0x0DFF),),  # 73
    ((u"Myanmar", 0x1000, 0x109F),),  # 74
    (  # 75
        (u"Ethiopic", 0x1200, 0x137F),
        (u"Ethiopic Supplement", 0x1380, 0x139F),
        (u"Ethiopic Extended", 0x2D80, 0x2DDF),
    ),
    ((u"Cherokee", 0x13A0, 0x13FF),),  # 76
    ((u"Unified Canadian Aboriginal Syllabics", 0x1400, 0x167F),),  # 77
    ((u"Ogham", 0x1680, 0x169F),),  # 78
    ((u"Runic", 0x16A0, 0x16FF),),  # 79
    ((u"Khmer", 0x1780, 0x17FF), (u"Khmer Symbols", 0x19E0, 0x19FF)),  # 80
    ((u"Mongolian", 0x1800, 0x18AF),),  # 81
    ((u"Braille Patterns", 0x2800, 0x28FF),),  # 82
    ((u"Yi Syllables", 0xA000, 0xA48F), (u"Yi Radicals", 0xA490, 0xA4CF)),  # 83
    (  # 84
        (u"Tagalog", 0x1700, 0x171F),
        (u"Hanunoo", 0x1720, 0x173F),
        (u"Buhid", 0x1740, 0x175F),
        (u"Tagbanwa", 0x1760, 0x177F),
    ),
    ((u"Old Italic", 0x10300, 0x1032F),),  # 85
    ((u"Gothic", 0x10330, 0x1034F),),  # 86
    ((u"Deseret", 0x10400, 0x1044F),),  # 87
    (  # 88
        (u"Byzantine Musical Symbols", 0x1D000, 0x1D0FF),
        (u"Musical Symbols", 0x1D100, 0x1D1FF),
        (u"Ancient Greek Musical Notation", 0x1D200, 0x1D24F),
    ),
    ((u"Mathematical Alphanumeric Symbols", 0x1D400, 0x1D7FF),),  # 89
    ((u"Private Use (plane 15)", 0xF0000, 0xFFFFD), (u"Private Use (plane 16)", 0x100000, 0x10FFFD)),  # 90
    ((u"Variation Selectors", 0xFE00, 0xFE0F), (u"Variation Selectors Supplement", 0xE0100, 0xE01EF)),  # 91
    ((u"Tags", 0xE0000, 0xE007F),),  # 92
    ((u"Limbu", 0x1900, 0x194F),),  # 93
    ((u"Tai Le", 0x1950, 0x197F),),  # 94
    ((u"New Tai Lue", 0x1980, 0x19DF),),  # 95
    ((u"Buginese", 0x1A00, 0x1A1F),),  # 96
    ((u"Glagolitic", 0x2C00, 0x2C5F),),  # 97
    ((u"Tifinagh", 0x2D30, 0x2D7F),),  # 98
    ((u"Yijing Hexagram Symbols", 0x4DC0, 0x4DFF),),  # 99
    ((u"Syloti Nagri", 0xA800, 0xA82F),),  # 100
    (  # 101
        (u"Linear B Syllabary", 0x10000, 0x1007F),
        (u"Linear B Ideograms", 0x10080, 0x100FF),
        (u"Aegean Numbers", 0x10100, 0x1013F),
    ),
    ((u"Ancient Greek Numbers", 0x10140, 0x1018F),),  # 102
    ((u"Ugaritic", 0x10380, 0x1039F),),  # 103
    ((u"Old Persian", 0x103A0, 0x103DF),),  # 104
    ((u"Shavian", 0x10450, 0x1047F),),  # 105
    ((u"Osmanya", 0x10480, 0x104AF),),  # 106
    ((u"Cypriot Syllabary", 0x10800, 0x1083F),),  # 107
    ((u"Kharoshthi", 0x10A00, 0x10A5F),),  # 108
    ((u"Tai Xuan Jing Symbols", 0x1D300, 0x1D35F),),  # 109
    ((u"Cuneiform", 0x12000, 0x123FF), (u"Cuneiform Numbers and Punctuation", 0x12400, 0x1247F)),  # 110
    ((u"Counting Rod Numerals", 0x1D360, 0x1D37F),),  # 111
    ((u"Sundanese", 0x1B80, 0x1BBF),),  # 112
    ((u"Lepcha", 0x1C00, 0x1C4F),),  # 113
    ((u"Ol Chiki", 0x1C50, 0x1C7F),),  # 114
    ((u"Saurashtra", 0xA880, 0xA8DF),),  # 115
    ((u"Kayah Li", 0xA900, 0xA92F),),  # 116
    ((u"Rejang", 0xA930, 0xA95F),),  # 117
    ((u"Cham", 0xAA00, 0xAA5F),),  # 118
    ((u"Ancient Symbols", 0x10190, 0x101CF),),  # 119
    ((u"Phaistos Disc", 0x101D0, 0x101FF),),  # 120
    ((u"Carian", 0x102A0, 0x102DF), (u"Lycian", 0x10280, 0x1029F), (u"Lydian", 0x10920, 0x1093F)),  # 121
    ((u"Domino Tiles", 0x1F030, 0x1F09F), (u"Mahjong Tiles", 0x1F000, 0x1F02F)),  # 122
)

# The code pages, by bit, as OpenType names them: (bit, name, Python codec, script). A code page is
# declared when the font has every letter it encodes of its script, and A to Z both cases (each code
# page holds ASCII): its letters (Unicode category L) whose Unicode name begins with the script, the
# compatibility forms left out (fi and fl, Arabic presentation forms: decomposition "<...>").
SINGLE_BYTE_PAGES = (
    (0, u"Latin 1 (1252)", "cp1252", "LATIN"),
    (1, u"Latin 2 (1250)", "cp1250", "LATIN"),
    (2, u"Cyrillic (1251)", "cp1251", "CYRILLIC"),
    (3, u"Greek (1253)", "cp1253", "GREEK"),
    (4, u"Turkish (1254)", "cp1254", "LATIN"),
    (5, u"Hebrew (1255)", "cp1255", "HEBREW"),
    (6, u"Arabic (1256)", "cp1256", "ARABIC"),
    (7, u"Baltic (1257)", "cp1257", "LATIN"),
    (8, u"Vietnamese (1258)", "cp1258", "LATIN"),
    (16, u"Thai (874)", "cp874", "THAI"),
)
# Letters of these code pages that no alphabet needs: the florin sign (a letter by its Unicode category),
# and the Yiddish digraphs Unicode encodes as ligatures (װ ױ ײ, in 1255)
NOT_REQUIRED = frozenset((0x0192, 0x05F0, 0x05F1, 0x05F2))
# The East Asian code pages, by their national standard's first level, the characters in everyday use
# (the full code pages hold thousands more rare ideographs, which few fonts draw): (bit, name, codec,
# [(first row, last row)] of the standard's 94 x 94 table, read as EUC bytes)
CJK_PAGES = (
    (17, u"Japanese, JIS (932)", "euc_jp", ((4, 5), (16, 47))),  # JIS X 0208's kana and level 1 kanji
    (18, u"Chinese Simplified (936)", "gb2312", ((16, 55),)),  # GB 2312's level 1 hanzi
    (19, u"Korean Wansung (949)", "euc_kr", ((16, 40),)),  # KS X 1001's 2,350 Hangul syllables
)
BIG5_PAGE = (20, u"Chinese Traditional (950)", "big5", (0xA440, 0xC67E))  # Big5's 5,401 frequently used hanzi
JOHAB_PAGE = (21, u"Korean Johab (1361)", (0xAC00, 0xD7A3))  # every Hangul syllable, 11,172
# The code page bits never set or cleared here, left as declared: Macintosh Roman (29), OEM character set
# (30), Symbol (31), the MS-DOS code pages (48 to 63), and the bits OpenType reserves. Of 188 fonts of
# FreeLab's corpus (Google Fonts), the MS-DOS pages are declared by few and Macintosh Roman by fewer
# than draw it: set from coverage, they would make the font info say what makers of fonts leave unsaid.


def unichr_(code):
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)


def range_name(bit):
    """A Unicode range bit's name: its first block's (u"Latin Extended-A")."""
    try:
        return UNICODE_RANGES[bit][0][0]
    except IndexError:
        return u"bit %d" % bit


def page_name(bit):
    for page in SINGLE_BYTE_PAGES + CJK_PAGES + (BIG5_PAGE,):
        if page[0] == bit:
            return page[1]
    if bit == JOHAB_PAGE[0]:
        return JOHAB_PAGE[1]
    return u"bit %d" % bit


_STARTS = []
_BLOCKS = []


def _block_index():
    if not _STARTS:
        blocks = sorted((low, high, bit) for bit, ranges in enumerate(UNICODE_RANGES) for _name, low, high in ranges)
        _BLOCKS.extend(blocks)
        _STARTS.extend(low for low, _high, _bit in blocks)
    return _STARTS, _BLOCKS


def unicode_bits(codes):
    """The Unicode range bits of these code points."""
    starts, blocks = _block_index()
    bits = set()
    for code in codes:
        if code > 0xFFFF:
            bits.add(NON_PLANE_0)
        at = bisect.bisect_right(starts, code) - 1
        if at >= 0:
            low, high, bit = blocks[at]
            if low <= code <= high:
                bits.add(bit)
    return bits


def _decoded(data, codec):
    """The one character these bytes are in the codec, or None."""
    try:
        text = bytearray(data).decode(codec)
    except (UnicodeDecodeError, LookupError, ValueError):
        return None
    return text if len(text) == 1 else None


def _required(chars, script=None):
    """The code points of these characters a font needs: letters (of the script, when one is named), not
    compatibility forms, not NOT_REQUIRED."""
    found = set()
    for ch in chars:
        if ch is None or not unicodedata.category(ch).startswith("L"):
            continue
        code = ord(ch)
        if code in NOT_REQUIRED or unicodedata.decomposition(ch).startswith("<"):
            continue
        if script is not None and not unicodedata.name(ch, u"").startswith(script + " "):
            continue
        found.add(code)
    return found


_PAGES = []


def page_letters():
    """[(bit, frozenset of the code points the code page needs)], read from Python's codecs once."""
    if _PAGES:
        return _PAGES
    pages = []
    for bit, _name, codec, script in SINGLE_BYTE_PAGES:
        chars = [_decoded([byte], codec) for byte in range(0x80, 0x100)]
        pages.append((bit, frozenset(_required(chars, script) | ASCII_LETTERS)))
    for bit, _name, codec, rows in CJK_PAGES:
        chars = [_decoded([0xA0 + row, 0xA0 + cell], codec)
                 for first, last in rows for row in range(first, last + 1) for cell in range(1, 95)]
        pages.append((bit, frozenset(_required(chars) | ASCII_LETTERS)))
    bit, _name, codec, (first, last) = BIG5_PAGE
    chars = [_decoded([lead, trail], codec) for lead in range(first >> 8, (last >> 8) + 1)
             for trail in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)) if first <= (lead << 8 | trail) <= last]
    pages.append((bit, frozenset(_required(chars) | ASCII_LETTERS)))
    bit, _name, (first, last) = JOHAB_PAGE
    pages.append((bit, frozenset(set(range(first, last + 1)) | ASCII_LETTERS)))
    _PAGES.extend(pages)
    return _PAGES


def managed_pages():
    """The code page bits FreeLab sets and clears."""
    return set(bit for bit, _letters in page_letters())


def code_page_bits(codes):
    """The code page bits these code points complete."""
    have = codes if isinstance(codes, (set, frozenset)) else set(codes)
    return set(bit for bit, letters in page_letters() if letters <= have)


def coverage(codes):
    """{field: the bits these code points give it}."""
    codes = frozenset(codes)
    return {INFO_UNICODE: unicode_bits(codes), INFO_PAGES: code_page_bits(codes)}


def changed_bits(declared, before, after):
    """The bits a write changed, from the coverage before and after it: {bit: True to set, False to clear}.
    A bit the write brought into coverage is set, one it took out of coverage cleared, wherever the
    declared bits differ; every other bit stays as declared."""
    declared = set(declared)
    changes = {}
    for bit in set(after) - set(before):
        if bit not in declared:
            changes[bit] = True
    for bit in set(before) - set(after):
        if bit in declared:
            changes[bit] = False
    return changes


def font_codes(package):
    """Every code point of the font's glyphs (their unicodes, else their unicode). About 0.9 seconds for
    BIZ UDPGothic's 13,932 glyphs, live 2026-11-18: read only around the writes that ask for it."""
    codes = set()
    for fg in package.fgPackage.glyphs:
        try:
            more = [int(code) for code in (fg.unicodes or []) if code]
        except Exception:
            more = []
        if not more:
            try:
                more = [int(fg.unicode)] if fg.unicode else []
            except Exception:
                more = []
        codes.update(more)
    return frozenset(codes)


def _bits(info, field):
    try:
        return set(int(bit) for bit in (getattr(info, field) or []))
    except Exception:
        return set()


def _number(info, field):
    try:
        value = getattr(info, field)
        return None if value is None else int(round(float(value)))
    except Exception:
        return None


class Change(object):
    """One field FreeLab updated: its name, the bits set and cleared (a range or code page field), or the
    value before and after (a Win field), with the master it was set in where the font has several (master:
    its name, or None)."""

    def __init__(self, field, added=(), removed=(), before=None, after=None, master=None):
        self.field, self.added, self.removed = field, sorted(added), sorted(removed)
        self.before, self.after, self.master = before, after, master

    def text(self):
        if self.field in (INFO_UNICODE, INFO_PAGES):
            name = range_name if self.field == INFO_UNICODE else page_name
            parts = []
            if self.added:
                parts.append(u"added %s" % u", ".join(name(bit) for bit in self.added))
            if self.removed:
                parts.append(u"removed %s" % u", ".join(name(bit) for bit in self.removed))
            return u"%s (%s)" % (u"Unicode ranges" if self.field == INFO_UNICODE else u"code pages", u"; ".join(parts))
        label = u"Win ascent" if self.field == INFO_WIN_ASCENT else u"Win descent"
        if self.master is not None:
            label = u"%s of %s" % (label, self.master)
        return u"%s (%s to %s)" % (label, self.before, self.after)


def changes_text(changes):
    """The fields changed, for a log line (plain text: the caller escapes it)."""
    return u"; ".join(change.text() for change in changes)


def _record(font):
    """The session's record of the Win values FreeLab raised in this font's info (FontLab's History does
    not take them back): {"win": {field: {master: (the value before FreeLab's first raise, the value it
    left, glyph names)}}}, each master's own (master: None for a font info with no masters to switch, a
    test's fake). The range and code page bits are not recorded: the History takes them back itself."""
    held = getattr(sys, "_freelab_font_info", None)
    if held is None:
        held = sys._freelab_font_info = {}
    return held.setdefault(font, {"win": {}})


def recorded(font):
    held = getattr(sys, "_freelab_font_info", None) or {}
    entry = held.get(font)
    return bool(entry and entry["win"])


def _write_bits(info, field, bits):
    setattr(info, field, sorted(bits))


def apply_bits(info, font, before, after):
    """The range and code page bits a write changed (before, after: coverage()), set in the font info
    before the write's History step records the font, so that Edit > Undo takes them back with the
    glyphs (font: unused, kept for the callers). [Change]."""
    changes = []
    for field in (INFO_UNICODE, INFO_PAGES):
        declared = _bits(info, field)
        bits = changed_bits(declared, before[field], after[field])
        if field == INFO_PAGES:
            managed = managed_pages()
            bits = dict((bit, on) for bit, on in bits.items() if bit in managed)
        if not bits:
            continue
        new = set(declared)
        for bit, on in bits.items():
            (new.add if on else new.discard)(bit)
        _write_bits(info, field, new)
        kept = _bits(info, field)
        bits = dict((bit, on) for bit, on in bits.items() if (bit in kept) == on)  # (what FontLab kept)
        added = [bit for bit, on in bits.items() if on]
        removed = [bit for bit, on in bits.items() if not on]
        if added or removed:
            changes.append(Change(field, added, removed))
    return changes


# Where FontLab 7 keeps the vertical metrics its export writes (live 2026-11-27, Karantina and Rubik, OpenType TT):
# the typo ascender, descender, and line gap are each master's own Ascender, Descender, and Line gap (Font Info's
# Font Dimensions, the lines it draws); the Win ascent and descent are its Safe top and Safe bottom; the hhea values
# are the typo ones unless Font Info's Other Values > Custom hhea linespacing is on, then each master's own.
# flPackage.info, the font's model, reads and writes them for the current master; fgPackage.info holds a copy
# that the export overwrites: typo, hhea, and Win values written there alone were exported as the master's.
# fsSelection (Use Typo Metrics), the Unicode ranges, and the code pages are exported from fgPackage.info.
TYPO_FIELDS = ("openTypeOS2TypoAscender", "openTypeOS2TypoDescender", "openTypeOS2TypoLineGap")
HHEA_FIELDS = ("openTypeHheaAscender", "openTypeHheaDescender", "openTypeHheaLineGap")
MASTER_FIELDS = TYPO_FIELDS + HHEA_FIELDS + (INFO_WIN_ASCENT, INFO_WIN_DESCENT)
CUSTOM_HHEA = "hhea_use_custom"


def custom_hhea(package):
    """Whether Font Info's Custom hhea linespacing is on: fgPackage.info's flags (a font that never had it set
    holds none, live: Rubik; it reads off, as the export takes it)."""
    try:
        flags = package.fgPackage.info.dict.flags.asDict()
    except Exception:
        return False
    return isinstance(flags, dict) and flags.get(CUSTOM_HHEA) is True


class ExportedInfo(object):
    """A font's info as FontLab's export reads it, in place of fgPackage.info: its typo, hhea, and Win values
    read from the current master (flPackage.info; the hhea values as the typo ones while Custom hhea
    linespacing is off; the Win values the masters' largest, the whole font's) and written to every master,
    each made current quietly (setMaster(name, False)) and the current one made current again, and into
    fgPackage.info too (its copy, which FreeLab's other reads see); any other field read and written in
    fgPackage.info. A package without flPackage.info (a test's fake) has fgPackage.info stand for it."""

    def __init__(self, package):
        object.__setattr__(self, "_package", package)

    def _fg(self):
        return self._package.fgPackage.info

    def _model(self):
        try:
            return self._package.info
        except Exception:
            return None

    def masters(self):
        try:
            return [u"%s" % name for name in self._package.masters]
        except Exception:
            return []

    def _each(self, act):
        """[(master, act(master))] with each master current in turn (the current one alone where they cannot
        be switched), the current one made current again."""
        package = self._package
        try:
            current = u"%s" % package.master
        except Exception:
            current = None
        names = self.masters()
        if current is None or len(names) < 2 or self._model() is None:
            return [(current, act(current))]
        found = []
        try:
            for name in names:
                package.setMaster(name, False)
                found.append((name, act(name)))
        finally:
            try:
                package.setMaster(current, False)
            except Exception:
                pass
        return found

    def _read(self, field):
        model = self._model()
        if model is None or field not in MASTER_FIELDS:
            return getattr(self._fg(), field)
        if field in HHEA_FIELDS and not custom_hhea(self._package):
            field = TYPO_FIELDS[HHEA_FIELDS.index(field)]
        return getattr(model, field)

    def master_values(self, field):
        """{master: value} of a master field (the current master's alone where they cannot be switched)."""
        def read(_master):
            try:
                return self._read(field)
            except Exception:
                return None
        return dict(self._each(read))

    def set_master_values(self, field, values):
        """A master field set per master ({master: value}; masters not named are left)."""
        model = self._model()

        def write(master):
            if master in values:
                setattr(model if model is not None else self._fg(), field, _model_number(values[master], model))
        self._each(write)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in (INFO_WIN_ASCENT, INFO_WIN_DESCENT) and self._model() is not None:
            found = [value for value in self.master_values(name).values() if value is not None]
            return max(found) if found else None
        return self._read(name)

    def __setattr__(self, name, value):
        model = self._model()
        if model is not None and name in MASTER_FIELDS:
            self._each(lambda _master: setattr(model, name, _model_number(value, model)))
        try:
            setattr(self._fg(), name, value)
        except Exception:
            if model is None or name not in MASTER_FIELDS:
                raise


def _model_number(value, model):
    """flPackage.info keeps the typo and Win values as whole numbers; a fake's stand-in takes them as given."""
    if model is None or value is None:
        return value
    return int(round(float(value)))


def win_needed(extents):
    """The Win ascent and descent these glyphs need: (the highest ink's top, the lowest ink's bottom as a
    positive depth), rounded outward; None where no glyph has ink. extents: [(bottom, top)]."""
    tops = [top for _bottom, top in extents]
    bottoms = [bottom for bottom, _top in extents]
    ascent = int(math.ceil(max(tops))) if tops else None
    descent = int(math.ceil(-min(bottoms))) if bottoms else None
    return ascent, descent


# The Win values are each master's own: FontLab exports a master's Safe top and Safe bottom as that master's
# Win ascent and descent (live 2026-11-27), so each is read, raised, recorded, and put back in its own master.
# Read and written as one value (the masters' largest, written to every master), a font whose masters held
# 900 and 1100 was not raised for ink at 1000, which then clipped in the first; and ink at 1200 raised both
# to 1200, recorded 1100 as the value before, and an undo then left 1100 in the first master, its own 900
# lost (rest review 1, finding 1). A font info with no masters to switch (fgPackage.info, a test's fake) holds
# one value, under the master None.

def _win_values(info, field):
    """{master: value} of a Win field (whole numbers, None where unreadable), and whether they are per master
    (info is ExportedInfo); else {None: the one value}."""
    if getattr(type(info), "master_values", None) is not None:
        found = {}
        for master, value in info.master_values(field).items():
            try:
                found[master] = None if value is None else int(round(float(value)))
            except Exception:
                found[master] = None
        return found, True
    return {None: _number(info, field)}, False


def _set_win(info, field, values, per_master):
    """Win values written ({master: value}: each into its own master; masters not named are left)."""
    if per_master:
        info.set_master_values(field, dict((master, float(value)) for master, value in values.items()))
    else:
        for value in values.values():
            setattr(info, field, float(value))


def _extents_of(extents, master):
    """The ink a master's Win values must cover: extents a dict ({master: [(bottom, top)]}, each master's own
    layers), or a list ([(bottom, top)] of every master layer: each master then covers them all, never
    clipping a master's ink, if raising a master past its own)."""
    if isinstance(extents, dict):
        if master is None:
            return [extent for found in extents.values() for extent in found]
        return list(extents.get(master, ()))
    return list(extents or ())


def _in_order(info, masters):
    """The masters named (keys of a dict), in the font's order (for the log), any it does not list after."""
    try:
        order = list(info.masters()) if getattr(type(info), "masters", None) is not None else []
    except Exception:
        order = []
    first = [master for master in order if master in masters]
    return first + sorted((master for master in masters if master not in first),
                          key=lambda name: (name is None, u"%s" % name))


def apply_win(info, font, extents, names):
    """Each master's Win ascent and descent raised to the ink of the glyphs the write drew (extents: their
    master layers' [(bottom, top)], or {master: [(bottom, top)]}: _extents_of), never lowered, and never set
    where they are not (0 or none); recorded per master with the glyphs' names. Glyphs whose ink is within a
    value FreeLab raised before but past the value before that raise are recorded with it too, though the
    write raises nothing: they rely on the raise, and a follow must not lower it under them once the glyphs
    it was raised for are gone (adversarial review 5: A raised 900 to 1000, B built to 950 was not recorded,
    and A undone took the value back to 900, under B). [Change]."""
    changes = []
    record = _record(font)["win"]
    for index, field in enumerate((INFO_WIN_ASCENT, INFO_WIN_DESCENT)):
        values, per_master = _win_values(info, field)
        held = record.setdefault(field, {})
        if not isinstance(held, dict):  # (an earlier FreeLab's one value, recorded this session: not per master)
            held = record[field] = {}
        raise_to = {}
        for master, now in values.items():
            need = win_needed(_extents_of(extents, master))[index]
            # (0 reads as not set, as Font Check takes it: a value made from these glyphs alone would clip the others)
            if need is None or not now:
                continue
            if need <= now:
                first, left, earlier = held.get(master, (None, None, ()))
                if left is not None and left == now and need > first:  # (FreeLab's raise, as it left it)
                    held[master] = (first, left, tuple(sorted(set(earlier) | set(names))))
                continue
            raise_to[master] = need
        if raise_to:
            _set_win(info, field, raise_to, per_master)
            kept = _win_values(info, field)[0]
            for master in _in_order(info, raise_to):
                need, now = raise_to[master], values[master]
                if kept.get(master) != need:
                    continue
                first, _left, earlier = held.get(master, (now, now, ()))
                held[master] = (first, need, tuple(sorted(set(earlier) | set(names))))
                changes.append(Change(field, before=now, after=need, master=master if len(values) > 1 else None))
        if not held:
            del record[field]
    return changes


def follow(info, font, extent_of):
    """After an undo or a redo: each Win value FreeLab raised this session put in step, in its own master,
    with the glyphs it was raised for, as they are now (extent_of(names): their master layers' extents, a list
    or a dict as apply_win takes them), unless it was changed by hand since FreeLab left it (it is then left,
    and forgotten). [Change]."""
    held = getattr(sys, "_freelab_font_info", None) or {}
    entry = held.get(font)
    if not entry:
        return []
    changes, measured = [], {}  # (measured: extent_of's reading of each list of names, read once for every master)
    for index, field in enumerate((INFO_WIN_ASCENT, INFO_WIN_DESCENT)):
        if field not in entry["win"]:
            continue
        raised = entry["win"][field]
        if not isinstance(raised, dict):  # (an earlier FreeLab's one value, recorded this session: forgotten)
            del entry["win"][field]
            continue
        values, per_master = _win_values(info, field)
        put = {}
        for master in _in_order(info, raised):
            first, left, names = raised[master]
            if values.get(master) != left:
                del raised[master]
                continue
            if names not in measured:
                measured[names] = extent_of(names)
            need = win_needed(_extents_of(measured[names], master))[index]
            want = max(first, need) if need is not None else first
            if want != left:
                put[master] = (first, left, want, names)
        if put:
            _set_win(info, field, dict((master, found[2]) for master, found in put.items()), per_master)
            for master in _in_order(info, put):
                first, left, want, names = put[master]
                raised[master] = (first, want, names)
                changes.append(Change(field, before=left, after=want, master=master if len(values) > 1 else None))
        if not raised:
            del entry["win"][field]
    return changes


def note_mark(font, count, state, wrote=False):
    """Where the font stands (its glyph count, its place in FontLab's History) once a write or a follow
    is done; wrote: a write whose glyphs the font info follows (its place is then one an undo goes back
    past, and a redo forward past). Every such place is kept: each undo or redo across any of them is
    followed, not only across the last (adversarial review 6: a second undo, below the last write, left the
    value the first undo had put back)."""
    held = getattr(sys, "_freelab_font_info", None) or {}
    entry = held.get(font)
    if not entry:
        return
    if wrote and state is not None:
        entry.setdefault("writes", set()).add(state)
    entry["mark"] = (count, state)


def needs_follow(font, count, state):
    """Whether the glyphs may have changed what FreeLab's updates follow since note_mark: the glyph count
    differs, or the History moved back or forward across any of FreeLab's writes the font info follows
    (note_mark). Cheap; follow reads the glyphs recorded."""
    if not recorded(font):
        return False
    entry = sys._freelab_font_info[font]
    mark = entry.get("mark")
    if mark is None or mark[0] != count:
        return True
    before = mark[1]
    if state is None or before is None or not entry.get("writes"):
        return state != before
    return any((state >= written) != (before >= written) for written in entry["writes"])


def forget(font=None):
    """The session's record dropped (a font closed, or all of them: the tests)."""
    held = getattr(sys, "_freelab_font_info", None)
    if held is None:
        return
    if font is None:
        held.clear()
    else:
        held.pop(font, None)


def main():
    """A helper module: no window (load_sibling keeps a module that has a main)."""
