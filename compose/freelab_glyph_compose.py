#FLM: Glyph Compose
# -*- coding: utf-8 -*-
"""FreeLab Glyph Compose, from FontLab's Scripts menu (Diacritics until 2026-11-16).

Its Diacritics tab (this module):

Builds the letters with diacritics a font lacks (Latin, Greek, Cyrillic, and the voiced kana: ga is ka
with a dakuten), as glyphs of components (the base letter and its marks), in every master. Shows each one before anything is made, lets each
mark be moved and scaled by hand, and makes only the ones you leave checked. It needs no groundwork in
the font: no anchors, no accented glyphs to learn from, no .case marks, not even marks.

- What can be built: every character of the chosen Unicode blocks that decomposes into a letter and
  marks (Unicode's canonical decomposition: a caron over a is U+01CE). Each mark is the font's own
  (its .case form for capitals, where there is one), else its twin above for a mark below (a dot below
  from the dot accent), else a draft made of the font's punctuation (a dot accent of the period, a
  dieresis of two, a caron of an upside-down circumflex accent ^), sized as marks are in the
  open-licensed fonts FreeLab learned from. i and j take their dotless forms under a mark above. Where
  most fonts draw another mark than Unicode's decomposition names (CONVENTIONS: Latvian's comma below
  for a cedilla, the vertical caron of d, t, l, and L), that mark.
- Where the marks go: as the font's own accented glyphs place theirs, where it has some (their gap to
  the ink, and their offset from the center of the letter's top or bottom fifth, as a share of its
  width, pooled per case so that all marks agree); else as the open-licensed fonts place them
  (diacritics/mark_model.json, kept per letter: over b's bowl, not its stem). Marks stack the way
  those fonts stack them: an acute beside a circumflex, as Vietnamese does, a macron over a
  dieresis.
- Room above and below: a glyph must stay clear of the lines above and below at a 120% line spacing.
  A stack that would not is made compact: the gaps between its marks closed, then its marks made
  smaller (to 70% at most); a glyph that still does not fit is listed unchecked, to draw by hand.
- Greek capitals take their tonos at their left, as Greek sets them, the glyph made wider for it.
- Names: Glyphs' names for the characters (glyph_names.json, from glyphsLib's GlyphData.xml, MIT
  License), else the letter's name and the marks' (adotbelow).

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys
import time
import unicodedata

# Combining marks: the root of their glyph names (acute, acutecomb, acute.case, acutecomb.case)
MARKS = {0x0300: "grave", 0x0301: "acute", 0x0302: "circumflex", 0x0303: "tilde", 0x0304: "macron",
         0x0306: "breve", 0x0307: "dotaccent", 0x0308: "dieresis", 0x0309: "hookabove", 0x030A: "ring",
         0x030B: "hungarumlaut", 0x030C: "caron", 0x030F: "dblgrave", 0x0311: "breveinverted", 0x031B: "horn",
         0x0323: "dotbelow", 0x0324: "dieresisbelow", 0x0325: "ringbelow", 0x0326: "commaaccent",
         0x0327: "cedilla", 0x0328: "ogonek", 0x032D: "circumflexbelow", 0x032E: "brevebelow",
         0x0330: "tildebelow", 0x0331: "macronbelow", 0x0313: "commaabove", 0x0314: "commareversedabove",
         0x0342: "perispomeni", 0x0345: "ypogegrammeni", 0x0312: "commaturnedabove",
         0x0315: "caronvertical",  # (the comma above right: the apostrophe-like caron of d, t, l, and L)
         0x032C: "caronbelow", 0x032F: "breveinvertedbelow", 0x0316: "gravebelow", 0x0317: "acutebelow",
         0x0320: "minusbelow", 0x0332: "lowline", 0x030D: "verticallineabove", 0x0329: "verticallinebelow",
         0x031F: "plusbelow", 0x0310: "candrabindu",
         0x3099: "dakuten", 0x309A: "handakuten"}  # (the kana voicing marks)
SPACING_MARKS = {0x0300: 0x0060, 0x0301: 0x00B4, 0x0302: 0x02C6, 0x0303: 0x02DC, 0x0304: 0x00AF, 0x0306: 0x02D8,
                 0x0307: 0x02D9, 0x0308: 0x00A8, 0x030A: 0x02DA, 0x030B: 0x02DD, 0x030C: 0x02C7, 0x0327: 0x00B8,
                 0x0328: 0x02DB, 0x0313: 0x1FBF, 0x0314: 0x1FFE, 0x0342: 0x1FC0,
                 0x0345: 0x037A, 0x3099: 0x309B, 0x309A: 0x309C}  # each combining mark's spacing form, by its code point
# Other names fonts give a mark's glyph (for capitals, each with .case first), and other code points it is
# encoded at (Adobe's comma below at U+F6C3)
MARK_ALIASES = {"caronvertical": ("caroncomb.alt", "caron.alt", "caronverticalcomb", "caronvertical", "caroncommaaccent",
                                  "caronslovak", "uni030C.alt", "commaaboverightcomb", "uni0315"),
                "commaturnedabove": ("commaturnedabovecomb", "commaturnedabove", "commaaccentrotate", "uni0312"),
                "commaaccent": ("commaaccentcomb", "commaaccent", "commabelowcomb", "uni0326"),
                "dakuten": ("voicedcombkana", "dakutenkanacomb", "dakuten-kana", "dakuten", "uni3099", "voicedkana",
                            "uni309B"),
                "handakuten": ("semivoicedcombkana", "handakutenkanacomb", "handakuten-kana", "handakuten", "uni309A",
                               "semivoicedkana", "uni309C")}
MARK_CODES = {"commaaccent": (0xF6C3,)}
# Letters whose mark fonts draw otherwise than Unicode's decomposition says, as most of the open-licensed
# fonts do (diacritics/train/conventions.py, 433 families: the share of the fonts telling): Latvian's and
# Livonian's G, K, L, N, R, and D take a comma below for Unicode's cedilla (224 of 232 fonts for G to 11 of
# 18 for d; Marshallese draws a cedilla on L and N, Latvian is the more common), Latvian's small g a turned
# comma above (155 of 180); Czech and Slovak d, t, l, and L the vertical caron, an apostrophe-like mark
# right of the stem's top (190 of 214 for d, 168 of 210 for t, 200 of 220 for l, 200 of 225 for L).
# {letter: {Unicode's mark: the fonts' mark}}
COMMA_BELOW = {0x0327: 0x0326}
CONVENTIONS = dict([(code, COMMA_BELOW) for code in (0x0122, 0x0136, 0x0137, 0x013B, 0x013C, 0x0145, 0x0146,
                                                     0x0156, 0x0157, 0x1E10, 0x1E11)] +
                   [(0x0123, {0x0327: 0x0312})] + [(code, {0x030C: 0x0315}) for code in (0x010F, 0x0165, 0x013E, 0x013D)])
CONVENTION_NOTES = {(0x0327, 0x0326): u"the comma below fonts draw for Unicode's cedilla",
                    (0x0327, 0x0312): u"the turned comma above fonts draw for Unicode's cedilla",
                    (0x030C, 0x0315): u"the vertical caron fonts draw for Unicode's caron"}
# The vertical caron: its ink's left this far right of the stem's top (the right end of the letter's top
# fifth), its top this far over the letter's top, in shares of the em, per letter (the corpus's medians:
# 190 fonts for d, 168 for t, 200 each for l and L), and its height (when drafted)
VERTICAL_CARON = {u"d": (0.048, 0.0), u"l": (0.048, 0.0), u"t": (0.042, 0.1008), u"L": (0.091, 0.0), None: (0.053, 0.0)}
VERTICAL_CARON_HEIGHT = 0.198
# Where the kana's voicing marks go when the model says nothing (diacritics/train/kana.py, 42 families): the
# mark's ink center from the right end and the top of its letter's ink, in shares of the em, per kana set
KANA_PLACES = {("dakuten", "hiragana"): (-0.0493, -0.0645), ("dakuten", "katakana"): (-0.0365, -0.0253),
               ("handakuten", "hiragana"): (-0.0828, -0.031), ("handakuten", "katakana"): (-0.0742, -0.001)}
KANA_HEIGHT = {"dakuten": 0.215, "handakuten": 0.214}
# A script's own forms of a mark, looked for first: (names, spacing code point). Greek's acute is its
# tonos, steeper; Cyrillic's short i takes a breve of its own in many fonts.
SCRIPT_MARKS = {("greek", "acute"): (("tonos", "oxia"), 0x0384), ("greek", "grave"): (("varia",), 0x1FEF),
                ("cyrillic", "breve"): (("brevecomb-cy", "breve-cy"), None)}
# Two marks Greek draws as one: the font's glyph for both (by name or code point), or its two marks
# set over each other (the tonos between the dialytika's dots), side by side (a breathing and its
# accent, the breathing first), or one on the other (the perispomeni over a breathing).
JOINED_MARKS = {("greek", (0x0308, 0x0301)): ("dieresistonos", 0x0385, "over"),
                ("greek", (0x0308, 0x0300)): ("dialytikavaria", 0x1FED, "over"),
                ("greek", (0x0308, 0x0342)): ("dialytikaperispomeni", 0x1FC1, "stacked"),
                ("greek", (0x0313, 0x0301)): ("psilioxia", 0x1FCE, "beside"),
                ("greek", (0x0313, 0x0300)): ("psilivaria", 0x1FCD, "beside"),
                ("greek", (0x0313, 0x0342)): ("psiliperispomeni", 0x1FCF, "stacked"),
                ("greek", (0x0314, 0x0301)): ("dasiaoxia", 0x1FDE, "beside"),
                ("greek", (0x0314, 0x0300)): ("dasiavaria", 0x1FDD, "beside"),
                ("greek", (0x0314, 0x0342)): ("dasiaperispomeni", 0x1FDF, "stacked")}
JOINED_GAP_SHARE = 0.025  # the gap between two joined marks, side by side or one on the other, as a share of the em
# A Greek capital's iota subscript is written after it (the prosgegrammeni, an adscript): its glyph,
# by code point or name, else the iota.
ADSCRIPT = ((0x1FBE,), ("prosgegrammeni", "iotaadscript"), 0x03B9)
ADSCRIPT_GAP_SHARE = 0.03  # between a capital and its adscript, as a share of the em
# Greek capitals carry these at their left, not above (Ά, Ἀ): the glyph made wider for them.
LEFT_OF_CAPITALS = (0x0301, 0x0300, 0x0313, 0x0314, 0x0342)
LEFT_GAP_SHARE = 0.03  # the gap between a mark at a capital's left and the capital, as a share of the em
BORROWED = {"dotbelow": "dotaccent", "dieresisbelow": "dieresis", "ringbelow": "ring", "macronbelow": "macron",
            "tildebelow": "tilde", "brevebelow": "breve", "circumflexbelow": "circumflex",
            "commaaccent": "comma", "caronbelow": "caron", "breveinvertedbelow": "breveinverted",
            "gravebelow": "grave", "acutebelow": "acute", "minusbelow": "macron",
            "verticallinebelow": "verticallineabove"}  # a mark below the font lacks: its twin above (or the comma), moved under
FLIPPED_TWINS = {"breveinverted": "breve", "breveinvertedbelow": "breve"}  # a mark of another, upside down
# Upside down is a half turn (both scales negative), never a mirror (one negative): a mirrored component's
# contours run the other way, and where it overlaps another part a renderer filling by nonzero winding
# (every TrueType rasterizer) shows a hole. A half turn keeps the direction. It is also the better shape:
# a caron's thick stroke is its left one and a circumflex's its right one, which a half turn gives and a
# mirror does not, and a slanted (italic) mark keeps its slant.
HALF_TURN = (-1.0, -1.0)
# A mark the font lacks altogether, drafted from its punctuation: (code points, how many side by side,
# upside down: True or "turned", both a half turn). Marks below draft from their twins above.
DRAFTS = {"dotaccent": ((0x002E,), 1, False), "dieresis": ((0x002E,), 2, False), "macron": ((0x002D, 0x2013), 1, False),
          "ring": ((0x00B0,), 1, False), "tilde": ((0x007E,), 1, False), "circumflex": ((0x005E,), 1, False),
          "caron": ((0x005E,), 1, True), "grave": ((0x0060,), 1, False), "acute": ((0x00B4,), 1, False),
          "hungarumlaut": ((0x00B4,), 2, False), "dblgrave": ((0x0060,), 2, False), "commaaccent": ((0x002C,), 1, False),
          "cedilla": ((0x002C,), 1, False), "commaabove": ((0x2019, 0x0027), 1, False),
          "commareversedabove": ((0x2018,), 1, False), "perispomeni": ((0x007E,), 1, False),
          # the vertical caron of an apostrophe (or the comma); the turned comma of a modifier turned comma or a
          # left quote, else the comma turned about; the kana's marks of a double quote and the degree sign
          "caronvertical": ((0x2019, 0x02BC, 0x002C), 1, False),
          "commaturnedabove": (((0x02BB, 0x2018), 1, False), ((0x002C,), 1, "turned")),
          "dakuten": ((0x201D, 0x0022), 1, False), "handakuten": ((0x00B0, 0x02DA), 1, False),
          # the inverted breve of the breve flipped; a vertical line of the straight quote (or the bar); the low
          # line of the underscore; the plus below of the plus sign; candrabindu of the breve (its dot left out)
          "breveinverted": ((0x02D8,), 1, True), "verticallineabove": ((0x0027, 0x007C), 1, False),
          "lowline": ((0x005F,), 1, False), "plusbelow": ((0x002B,), 1, False), "candrabindu": ((0x02D8,), 1, False)}


def draft_ways(root):
    """The ways a mark is drafted, in order: [(code points, how many, flipped)]."""
    found = DRAFTS.get(root)
    if not found:
        return []
    return list(found) if isinstance(found[0][0], tuple) else [found]


DRAFT_NAMES = {0x2019: u"quoteright", 0x02BC: u"the modifier apostrophe", 0x002C: u"the comma",
               0x02BB: u"the modifier turned comma", 0x2018: u"quoteleft", 0x201D: u"quotedblright",
               0x0022: u"the double quote", 0x00B0: u"the degree sign"}  # (drafts named after what they are made of)
DRAFT_SPACING = 0.5  # two drafted dots apart by this share of a dot's width
DOTLESS = {u"i": (u"\u0131", ("dotlessi", "idotless")), u"j": (u"\u0237", ("dotlessj", "jdotless", "uni0237")),
           u"\u0456": (u"\u0131", ("dotlessi", "idotless")),  # Cyrillic i and je: the Latin dotless forms
           u"\u0458": (u"\u0237", ("dotlessj", "jdotless", "uni0237"))}
# A font with no dotless i or j: each made of its i or j without its dot (read_dotless), where the dot can be
# told. {the dotless letter's code point: (the letter it is made of, its code point)}
DOTLESS_LETTERS = {0x0131: (u"i", 0x0069), 0x0237: (u"j", 0x006A)}
SETS =(("latin", "Latin-1, Latin Extended-A and -B", ((0x00C0, 0x0250),)),
        ("additional", "Latin Extended Additional (Vietnamese, and more)", ((0x1E00, 0x1F00),)),
        ("greek", "Greek", ((0x0370, 0x0400),)),
        ("polytonic", "Greek Extended (polytonic)", ((0x1F00, 0x2000),)),
        ("cyrillic", "Cyrillic", ((0x0400, 0x0530),)),
        ("kana", "Kana with dakuten (Japanese)", ((0x3040, 0x3100),)),
        ("all", "All", ((0x00C0, 0x0250), (0x1E00, 0x1F00), (0x0370, 0x0400), (0x1F00, 0x2000), (0x0400, 0x0530),
                        (0x3040, 0x3100))))
LISTED_SCRIPTS = ("greek", "cyrillic", "kana")  # listed only when the font has letters of them
NAMES_FILE = "glyph_names.json"
BAND_SHARE = 0.2  # the top or bottom share of a letter's ink whose center a mark centers on
DEFAULT_GAP_SHARE = 0.05  # a mark's gap to its letter, as a share of the em, with no model and no example
LEADING = 1.2  # the line spacing a glyph must fit, as a share of the em (applications' automatic leading)
MIN_SCALE = 0.7  # marks are made no smaller than this to fit
CLOSED_GAPS = 0.4  # a compact stack keeps this share of its gaps
OWN_EXAMPLES = 3  # a font's own placements count once it shows this many on a side, in a case
MODEL_FILE = "mark_model.json"


def side_of(code):
    """Where a combining mark goes: "above", "below", "right" (the horn), "topright" (the vertical caron, by
    the stem's top), or "kana" (a voicing mark, at a kana's top right)."""
    if code == 0x031B:
        return "right"
    if code == 0x0315:
        return "topright"
    if code in (0x3099, 0x309A):
        return "kana"
    if code == 0x0345:  # the iota subscript (its combining class, 240, is its own)
        return "below"
    return "below" if unicodedata.combining(unichr_(code)) in (202, 220) else "above"


# Mark roots as words, for what is written (a hook above, not a hookabove)
MARK_WORDS = {"hookabove": u"hook above", "hungarumlaut": u"double acute", "dotaccent": u"dot above",
              "dotbelow": u"dot below", "commaaccent": u"comma below", "dblgrave": u"double grave",
              "breveinverted": u"inverted breve", "dieresisbelow": u"dieresis below", "ringbelow": u"ring below",
              "circumflexbelow": u"circumflex below", "brevebelow": u"breve below", "tildebelow": u"tilde below",
              "macronbelow": u"macron below", "commaabove": u"psili (comma above)",
              "commareversedabove": u"dasia (reversed comma above)", "ypogegrammeni": u"ypogegrammeni (iota subscript)",
              "caronvertical": u"vertical caron", "commaturnedabove": u"turned comma above",
              "dieresistonos": u"dialytika with tonos", "dialytikavaria": u"dialytika with varia",
              "dialytikaperispomeni": u"dialytika with perispomeni", "psilioxia": u"psili with oxia",
              "psilivaria": u"psili with varia", "psiliperispomeni": u"psili with perispomeni",
              "dasiaoxia": u"dasia with oxia", "dasiavaria": u"dasia with varia",
              "dasiaperispomeni": u"dasia with perispomeni", "prosgegrammeni": u"prosgegrammeni (iota adscript)"}


def mark_word(root):
    return MARK_WORDS.get(root, root)


def article(word):
    """ "a" or "an" before a word, by its sound: an acute, an ogonek, an umlaut, an hour, an ypogegrammeni;
    a hook, a horn, a ring, a cedilla, a unit, a U+0312, a one, a eu-."""
    import re
    w = (word or u"").strip().lower()
    if not w:
        return u"a"
    if w.startswith((u"hour", u"honest", u"honor", u"heir")):
        return u"an"
    if w.startswith((u"one", u"once", u"eu", u"ewe", u"u+", u"uni", u"use", u"usu", u"uti", u"ubi", u"ura",
                     u"ure", u"uri", u"uro")):
        return u"a"
    if re.match(u"^u[bcdfgjklmnpqrstvwxz][aeiou]", w) and not w.startswith((u"un", u"up", u"ut")):
        return u"a"  # a unit, a usual (you-): not an umlaut, an upsilon, an unsure
    if re.match(u"^y[bcdfghjklmnpqrstvwxz]", w):
        return u"an"  # an ypogegrammeni, an ytterbium
    if w[0] in u"aeiou":
        return u"an"
    if len(w) == 1 or not w[1].isalpha():  # a letter by its name: an F, an S, a K
        return u"an" if w[0] in u"fhlmnrsx" else u"a"
    return u"a"


def with_article(word):
    return u"%s %s" % (article(word), word)


def listed(words, joiner=u"and"):
    """Words in a list: a, b, and c (an Oxford comma), a and b, or a (joiner: "or" for a, b, or c)."""
    words = list(words)
    if len(words) <= 1:
        return u"".join(words)
    if len(words) == 2:
        return u"%s %s %s" % (words[0], joiner, words[1])
    return u"%s, %s %s" % (u", ".join(words[:-1]), joiner, words[-1])


def unichr_(code):
    """A code point's character; the replacement character past U+FFFF on a narrow Python 2 (FontLab
    7's), which has none of them as one character (no letter is that far up in the blocks used here)."""
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def case_of(ch):
    """"upper" or "lower"; Greek's capitals with an iota adscript (titlecase letters) are capitals."""
    return "upper" if ch.isupper() or unicodedata.category(ch) == "Lt" else "lower"


def script_of(ch):
    """"greek", "cyrillic", "kana" (hiragana and katakana), or "latin", by the character's Unicode name."""
    name = unicodedata.name(ch, u"")
    if name.startswith(u"GREEK"):
        return "greek"
    if name.startswith(u"CYRILLIC"):
        return "cyrillic"
    if name.startswith((u"HIRAGANA", u"KATAKANA")):
        return "kana"
    return "latin"


def kana_set(code):
    """ "hiragana" or "katakana"."""
    return "hiragana" if code < 0x30A0 else "katakana"


# Scripts whose marks the font's mark features attach (anchors): each one's code point ranges.
ANCHOR_SCRIPTS = (("latin", ((0x0041, 0x0250), (0x0300, 0x0370), (0x1E00, 0x1F00))),
                  ("greek", ((0x0370, 0x0400), (0x1F00, 0x2000))),
                  ("cyrillic", ((0x0400, 0x0530),)),
                  ("hebrew", ((0x0590, 0x0600), (0xFB1D, 0xFB50))),
                  ("arabic", ((0x0600, 0x0700), (0x0750, 0x0780), (0x08A0, 0x0900), (0xFB50, 0xFE00), (0xFE70, 0xFF00))),
                  ("devanagari", ((0x0900, 0x0980), (0xA8E0, 0xA900))),
                  ("bengali", ((0x0980, 0x0A00),)),
                  ("gujarati", ((0x0A80, 0x0B00),)),
                  ("tamil", ((0x0B80, 0x0C00),)),
                  ("thai", ((0x0E00, 0x0E80),)),
                  ("lao", ((0x0E80, 0x0F00),)),
                  ("myanmar", ((0x1000, 0x10A0),)),
                  ("khmer", ((0x1780, 0x1800), (0x19E0, 0x1A00))))


def anchor_script(code):
    """The script of a code point, among ANCHOR_SCRIPTS, or None."""
    for script, ranges in ANCHOR_SCRIPTS:
        for low, high in ranges:
            if low <= code < high:
                return script
    return None


_NAMES = {}


def glyph_names(path=None):
    """{code point: Glyphs' name} (glyph_names.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), NAMES_FILE)
    if path not in _NAMES:
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            _NAMES[path] = dict((int(code, 16), name) for code, name in data.get("names", {}).items())
        except (IOError, OSError, ValueError):
            _NAMES[path] = {}
    return _NAMES[path]


def other_case(case):
    return "lower" if case == "upper" else "upper"


def font_codes(ak, glyphs):
    """[(glyph, code point)] of every code point of each glyph, the first glyph at a code point last so
    that Font's map keeps it (a glyph encoded at a radical too is found by its ideograph)."""
    pairs = [(u"%s" % g.name, code) for g in glyphs for code in ak.glyph_codes(g)]
    return list(reversed(pairs))


class Font(object):
    """What the planning reads of a font: its glyph names, their code points, and which glyphs are
    empty (a character with an empty glyph is planned again, under that glyph's name)."""

    def __init__(self, names, unicodes, empty=()):
        self.names = set(names)
        self.by_code = dict((code, name) for name, code in unicodes if code)
        self.empty = set(empty)
        # {0x0131 or 0x0237: Dotless} where the font has no dotless i or j and its i or j was read for one
        # (read_dotless, in FontLab); none read (Font Check's planning), the letters fall back to i and j
        self.dotless = {}

    def glyph_for(self, ch):
        return self.by_code.get(ord(ch))

    def drawn(self, code):
        """The glyph at a code point unless it is empty, else None. A CID-keyed font keeps a glyph for each
        character of its collection, drawn or not: 07LightNovelPOP's U+0306 is an empty glyph, and Ĕ was
        offered as E + uni0306, a breve nobody would see, its preview left blank (owner's image 184)."""
        name = self.by_code.get(code)
        return name if name is not None and name not in self.empty else None

    def usable(self, name):
        """Whether a glyph of that name is there and not empty (a mark found by its name)."""
        return name in self.names and name not in self.empty


class Mark(object):
    """A mark of a recipe: its root (acute), side, and the components it is made of, [(glyph, x scale,
    y scale, x, y)] in the mark's own place (one, the mark glyph, unless drafted); with what it stands
    in for (a borrowed twin, a draft)."""

    def __init__(self, root, side, parts, note=None, joined=False):
        self.root, self.side, self.parts, self.note = root, side, parts, note
        self.joined = joined  # its parts set over each other, centered (a dialytika with tonos), not side by side
        self.convention = None  # why it is not the mark Unicode's decomposition names (a comma below for a cedilla)

    @property
    def glyph(self):
        return self.parts[0][0]

    def label(self):
        names = [part[0] for part in self.parts]
        text = names[0] if len(set(names)) == 1 and len(names) == 1 else u" ".join(names)
        if len(names) > 1 and len(set(names)) == 1:
            text = u"%s \N{MULTIPLICATION SIGN}%d" % (names[0], len(names))
        if self.parts[0][1] < 0 and self.parts[0][2] < 0:
            text += u" turned upside down"
        elif self.parts[0][2] < 0:
            text += u" mirrored upside down"
        elif self.parts[0][1] < 0:
            text += u" mirrored"
        notes = [n for n in (self.note, self.convention) if n]
        return text + (u" (%s)" % u"; ".join(notes) if notes else u"")


class Recipe(object):
    """A character to build: its base glyph and Marks, or why it cannot."""

    def __init__(self, char, name=None, base=None, marks=None, missing=None):
        self.char, self.name, self.base = char, name, base
        self.marks = marks or []
        self.missing = missing  # what the font lacks, or None
        self.checked = True
        self.refill = False  # its glyph is in the font, empty: filled under its own name
        self.existing = None  # the font's own drawn glyph, listed to be rebuilt (never checked at first)
        self.standalone = False  # a combining mark made as a glyph of its own (placed as on base, centered at 0)
        self.notes = []  # what placing it took (marks made smaller, too tall)
        self.adjust = {}  # mark index: [dx, dy, x scale, y scale], set by hand (about the mark's center)
        self.touches = u""  # after a placement was applied from another letter: how close a mark comes
        self.far = u""  # its marks the hand left far off (far_note), as its row last said
        self.applied = None  # its adjust when it was last applied to the related letters (not again until moved)
        # Whether it is made compact to fit a 120% line (place). It follows the dialog's choice while its
        # placement is the suggestion; once placed by hand it keeps the one it was placed under, since the
        # hand's changes are measured from that suggestion.
        self.compact = True
        self.cell = u""  # its row's Built from text, as last written (a search looks through it)
        # Its dotless i or j where the font has none (Dotless): made here first, the font's dotless i itself,
        # or kept dotted (said in amber); with the note its row says of it, and whether it is that glyph's row
        self.dotless, self.base_note, self.dotless_row = None, u"", False

    @property
    def code(self):
        return ord(self.char)

    def describe(self):
        if self.missing:
            return u"needs %s" % self.missing
        if self.dotless_row:
            return u"%s without its dot" % self.dotless.source
        if self.standalone:
            return u"%s (a combining mark: placed as on %s, then centered on the origin, zero width)" % (
                self.marks[0].label(), self.base)
        return u" + ".join([self.base] + [mark.label() for mark in self.marks])


def find_mark(font, root, case, script="latin"):
    """A mark glyph of the font by its root (its .case form for capitals first; the script's own form
    first, Greek's tonos for an acute; the names other fonts give it, uni0326 or caroncomb.alt), or None.
    An empty glyph is passed over (Font.drawn): the next name or code point is tried, as for one the font
    lacks (a CID-keyed font's acutecomb is empty, its acute U+00B4 drawn)."""
    codes = [code for code, mark_root in MARKS.items() if mark_root == root]
    names = [root + "comb", root] + [u"uni%04X" % code for code in codes] + list(MARK_ALIASES.get(root, ()))
    candidates = []
    for name in names:
        candidates += ([name + ".case"] if case == "upper" else []) + [name]
    own, own_code = SCRIPT_MARKS.get((script, root), ((), None))
    first = []
    for name in own:
        first += ([name + ".case"] if case == "upper" else []) + [name]
    for candidate in first + candidates:
        if font.usable(candidate):
            return candidate
    if own_code and font.drawn(own_code):
        return font.drawn(own_code)
    for code in codes:
        for found_code in (code, SPACING_MARKS.get(code)):
            found = font.drawn(found_code) if found_code else None
            if found:
                return found
    for found_code in MARK_CODES.get(root, ()):
        if font.drawn(found_code):
            return font.drawn(found_code)
    return None


def make_mark(font, code, case, script="latin"):
    """The Mark for a combining mark: the font's own, its twin above (for a mark below), or a draft
    from the font's punctuation; or None."""
    root = MARKS.get(code)
    if root is None:
        return None
    side = side_of(code)
    glyph = find_mark(font, root, case, script)
    if glyph:
        return Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)])
    twin = BORROWED.get(root)
    if twin:
        glyph = find_mark(font, twin, case) or (font.drawn(0x002C) if twin == "comma" else None)
        if glyph:
            return Mark(root, side, [(glyph, 1.0, 1.0, 0.0, 0.0)], u"for %s" % mark_word(root))
    flipped = FLIPPED_TWINS.get(root)  # an inverted breve: the font's breve, upside down
    if flipped:
        glyph = find_mark(font, flipped, case)
        if glyph:
            return Mark(root, side, [(glyph,) + HALF_TURN + (0.0, 0.0)], u"for %s, of the %s upside down" % (
                mark_word(root), mark_word(flipped)))
    draft_root = root if root in DRAFTS else twin if twin in DRAFTS else None
    for codes, count, flipped in draft_ways(draft_root):
        found = next((c for c in codes if font.drawn(c)), None)
        if found is None:
            continue
        sx, sy = HALF_TURN if flipped else (1.0, 1.0)
        parts = [(font.drawn(found), sx, sy, 0.0, 0.0) for _ in range(count)]
        source = DRAFT_NAMES.get(found)
        note = u"draft for %s" % mark_word(root) + (u", of %s" % source if source else u"")
        return Mark(root, side, parts, note)
    return None


# The scripts whose letters the font has can be listed to be rebuilt (Latin, Greek, Cyrillic): not kana,
# whose voiced forms fonts draw as letters of their own.
REBUILT_SCRIPTS = ("latin", "greek", "cyrillic")


STANDALONE_ON = (u"o", u"n", u"x")  # the letter a combining mark is placed on to be drawn alone (its height)


def mark_recipe(font, ch):
    """A Recipe for a combining mark the font lacks, made as a glyph of its own from what its letters'
    marks come from (its twin above for a mark below, or punctuation): placed as on o, then centered on
    the glyph's origin, zero width (standalone)."""
    code = ord(ch)
    mark = make_mark(font, code, "lower")
    letter = next((font.drawn(ord(c)) for c in STANDALONE_ON if font.drawn(ord(c))), None)
    if mark is None:
        return Recipe(ch, missing=u"%s or a glyph to draft it from" % with_article(mark_word(MARKS.get(code))))
    if letter is None:
        return Recipe(ch, missing=u"a letter to place it on (o, n, or x)")
    name = glyph_name(font, u"", [], code, plain=True)  # (uniXXXX where the font has the name, unencoded)
    recipe = Recipe(ch, name, letter, [mark])
    recipe.standalone = True
    return recipe


def standalone_parts(parts, ink_of):
    """A standalone mark's parts: the letter it was placed on taken out, the mark centered on x = 0."""
    marks = parts[1:]
    box = parts_box(marks, ink_of)
    if box is None:
        return marks
    shift = -(box[0] + box[2]) / 2.0
    return [(glyph, sx, sy, x + shift, y) for glyph, sx, sy, x, y in marks]


def plan(font, characters, include_existing=False, also=()):
    """A Recipe for each character the font lacks that decomposes into a letter and marks; with
    include_existing, also for those it has (Latin, Greek, Cyrillic), to be rebuilt, unchecked; also: the
    characters among those listed so whatever the box says (one clicked to show its glyph)."""
    recipes = []
    for ch in characters:
        existing = font.by_code.get(ord(ch))
        drawn = bool(existing) and existing not in font.empty
        if unicodedata.category(ch) == "Mn" and ord(ch) in MARKS and ord(ch) not in (0x3099, 0x309A):
            if not drawn:
                recipes.append(mark_recipe(font, ch))
            continue
        if not unicodedata.category(ch).startswith("L"):
            continue
        if drawn and not ((include_existing or ch in also) and script_of(ch) in REBUILT_SCRIPTS):
            continue
        if ord(ch) in DOTLESS_LETTERS and not drawn:  # the dotless i or j, made of i or j without its dot
            row = dotless_row(font, ch)
            if row is not None:
                recipes.append(row)
            continue
        decomposed = unicodedata.normalize("NFD", ch)
        if len(decomposed) < 2:
            continue
        base_char, unicode_codes = decomposed[0], [ord(c) for c in decomposed[1:]]
        convention = CONVENTIONS.get(ord(ch), {})
        codes = [convention.get(code, code) for code in unicode_codes]  # the mark fonts draw (Latvian's comma below)
        base = font.drawn(ord(base_char))  # (an empty glyph is no letter to build on)
        if base is None:
            if not drawn:
                recipes.append(Recipe(ch, missing=u"its letter %s" % base_char))
            continue
        name_base = base
        dotless, base_note = None, u""
        if base_char in DOTLESS and any(side_of(code) == "above" for code in codes):
            dotless_char, dotless_names = DOTLESS[base_char]
            own = font.drawn(ord(dotless_char)) or next((n for n in dotless_names if font.usable(n)), None)
            # None: the font's own; else as read_dotless found its i or j (none read: the dotted letter, unsaid)
            dotless = None if own else font.dotless.get(ord(dotless_char))
            base = own or (dotless.name if dotless is not None and dotless.kind == "made" else base)
            if dotless is not None:
                base_note = dotless_note(dotless, base, sum(1 for code in codes if side_of(code) == "above"))
        marks, lacking = [], []
        script, case = script_of(ch), case_of(ch)
        steps, at = [], 0  # each mark's code point, or a pair of them Greek joins
        while at < len(codes):
            pair = tuple(codes[at:at + 2])
            if len(pair) == 2 and (script, pair) in JOINED_MARKS:
                steps.append(pair)
                at += 2
            else:
                steps.append(codes[at])
                at += 1
        for step in steps:
            if isinstance(step, tuple):
                mark = joined_mark(font, script, case, step)
                if mark is None:
                    lacking.append(mark_word(JOINED_MARKS[(script, step)][0]))
                    continue
                left = all(code in LEFT_OF_CAPITALS + (0x0313, 0x0314) for code in step)
            elif step == 0x0345 and script == "greek" and case == "upper":
                mark = adscript_mark(font)
                if mark is None:
                    lacking.append(mark_word(u"prosgegrammeni"))
                    continue
                left = False
            else:
                mark = make_mark(font, step, case, script)
                if mark is None:
                    word = mark_word(MARKS.get(step)) if step in MARKS else u"U+%04X" % step
                    if step not in unicode_codes:  # (fonts draw it for Unicode's: said so)
                        original = next((c for c, by in convention.items() if by == step), None)
                        word += u" (fonts draw it for Unicode's %s)" % mark_word(MARKS.get(original, u"mark"))
                    lacking.append(word)
                    continue
                left = step in LEFT_OF_CAPITALS
                if step not in unicode_codes:  # a mark fonts draw for Unicode's: said why
                    original = next((c for c, by in convention.items() if by == step), None)
                    mark.convention = CONVENTION_NOTES.get((original, step))
            if script == "greek" and case == "upper" and left:
                mark.side = "left"
            marks.append(mark)
        if lacking:
            if not drawn:  # (a letter the font has, which could not be rebuilt: not listed)
                recipes.append(Recipe(ch, missing=listed(with_article(word) for word in lacking)))
            continue
        name = existing or glyph_name(font, name_base, [mark.root for mark in marks], ord(ch),
                                      plain=script == "kana")
        recipe = Recipe(ch, name, base, marks)
        recipe.dotless, recipe.base_note = dotless, base_note
        recipe.refill = bool(existing) and not drawn
        if drawn:
            recipe.existing, recipe.checked = existing, False
        recipes.append(recipe)
    return recipes


def joined_mark(font, script, case, codes):
    """The Mark for two marks Greek joins: the font's glyph for both, else its two marks joined (over
    each other, side by side, or one on the other); None when it lacks one."""
    name, code, how = JOINED_MARKS[(script, codes)]
    names = [name, glyph_names().get(code)]
    if case == "upper":
        names = [n + u".case" for n in names if n] + names
    glyph = next((n for n in names if n and font.usable(n)), None) or font.drawn(code)
    if glyph:
        return Mark(name, "above", [(glyph, 1.0, 1.0, 0.0, 0.0)])
    parts = [make_mark(font, c, case, script) for c in codes]
    if any(part is None for part in parts):
        return None
    note = {"over": u"its marks set over each other", "beside": u"its marks side by side",
            "stacked": u"one mark on the other"}[how]
    return Mark(name, "above", [part.parts[0] for part in parts], note, joined=how)


def adscript_mark(font):
    """The Mark of a Greek capital's iota adscript, after the letter: the font's prosgegrammeni, or its
    iota; None when it has neither."""
    codes, names, iota = ADSCRIPT
    glyph = next((font.drawn(c) for c in codes if font.drawn(c)), None)
    glyph = glyph or next((n for n in names if font.usable(n)), None) or font.drawn(iota)
    if glyph is None:
        return None
    return Mark("prosgegrammeni", "adscript", [(glyph, 1.0, 1.0, 0.0, 0.0)],
                None if glyph != font.drawn(iota) else u"the iota, as an adscript")


# -- the dotless i and j a font lacks (the owner's decision of 2026-11-24) ----------------------------------
# Until then a font with no dotless i had its accented i built on the dotted i, the dot under the accent, and
# nothing said so. Now its i is read in every master (read_dotless): two contours, one clearly the dot, make
# the dotless i of the other (made here first, as a part: record_parts); one contour is an i drawn without a
# dot, used as it is; anything else is not taken apart, and the glyphs stay on the dotted i, said in amber.

class Dotless(object):
    """What a font with no dotless i (or j) has to build its accented i on: kind "made" (its i without its
    dot: contour dot, by numbered_contours' count, made into glyph name), "own" (its i has no dot: used as it
    is), or "refused" (reason, a clause: the dotted i is used, said in amber). code: the dotless letter's code
    point; letter: "i" or "j"; source: the font's glyph of that letter (None where it has none)."""

    def __init__(self, kind, code, dot=None, reason=u""):
        self.kind, self.code, self.dot, self.reason = kind, code, dot, reason
        self.letter = DOTLESS_LETTERS[code][0]
        self.source, self.name = None, None


def dot_index(boxes):
    """Which of a letter's two contours is its dot (its index in boxes, [(left, bottom, right, top)] as
    drawn), or None where that is not clear. The dot is the higher one, its center above the other's top
    (a dot that overlaps its stem's top still counts; one whose center comes down beside the stem does not:
    a head serif, a stem in two pieces), it is the smaller (its box's area), and the two meet across (a dot
    beside the stem is not over it). Where the highest and the smallest disagree, or the two overlap so
    that neither is clearly over the other, it is not guessed. A j's tail makes its body's box wider and
    taller: its dot is still the higher and smaller one."""
    if len(boxes) != 2 or any(box is None for box in boxes):
        return None
    centers = [(box[1] + box[3]) / 2.0 for box in boxes]
    if centers[0] == centers[1]:
        return None
    dot = 0 if centers[0] > centers[1] else 1
    high, low = boxes[dot], boxes[1 - dot]
    area = lambda box: max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])  # noqa: E731
    if not area(high) < area(low):
        return None  # the higher is not the smaller
    if not centers[dot] > low[3]:
        return None  # not clearly over the other
    if not (high[0] < low[2] and high[2] > low[0]):
        return None  # beside it, not over it
    return dot


def dotless_verdict(code, readings):
    """A Dotless of a letter's readings, one per master it is drawn in: its contours' boxes (dot_index's),
    or None for a master where it is made of components. Every master must agree: the same count, and the
    same contour clearly its dot. Reasons are clauses for the row's note and the log."""
    letter = DOTLESS_LETTERS[code][0]
    lacks = u"the font has no dotless %s, and its %s" % (letter, letter)
    if any(boxes is None for boxes in readings):
        return Dotless("refused", code, reason=u"%s is made of components" % lacks)
    counts = set(len(boxes) for boxes in readings)
    if not counts:
        return Dotless("refused", code, reason=u"%s has no outline" % lacks)
    if len(counts) > 1:
        return Dotless("refused", code, reason=u"%s differs from master to master" % lacks)
    count = counts.pop()
    if count == 1:
        return Dotless("own", code)
    if count != 2:
        return Dotless("refused", code, reason=u"%s has %s" % (lacks, counted(count, u"contour")))
    dots = set(dot_index(boxes) for boxes in readings)
    if len(dots) > 1:
        return Dotless("refused", code, reason=u"%s differs from master to master" % lacks)
    dot = dots.pop()
    if dot is None:
        return Dotless("refused", code, reason=u"the font has no dotless %s, and neither contour of its %s is "
                                                u"clearly the dot" % (letter, letter))
    return Dotless("made", code, dot)


def dotless_note(dotless, base, above=1):
    """A row's note of the glyph it is built on, where the font has no dotless i (or j): the one made here,
    the font's i used as it is (no dot: nothing collides, said plainly), or the dotted i kept (an amber
    note, kept_dotted, as a collision's: the dot stays under the diacritics above, which number above). The
    advice to draw the dotless letter follows a semicolon, as a note of its own: in parentheses it would
    close twice at the end of the row's cell, itself in parentheses."""
    if dotless.kind == "made":
        return u"%s is %s without its dot, built here first" % (dotless.name, dotless.source)
    if dotless.kind == "own":
        return u"on %s itself: the font's %s has no dot" % (base, dotless.letter)
    return u"the dot of %s stays under the %s: %s; draw U+%04X" % (
        base, u"diacritic" if above == 1 else u"diacritics", dotless.reason, dotless.code)


def kept_dotted(recipe):
    """Whether a recipe is built on a dotted i or j its font has no dotless form for and could not take
    apart (an amber note, as a collision's)."""
    return recipe.dotless is not None and recipe.dotless.kind == "refused"


def made_dotless(recipe):
    """The Dotless a recipe's base is made from (its own glyph's, for the dotless letter's row), or None."""
    return recipe.dotless if recipe.dotless is not None and recipe.dotless.kind == "made" else None


def dotless_row(font, ch):
    """The row of the dotless i or j itself (U+0131, U+0237) where the font lacks it and its i or j can be
    taken apart (read_dotless): its glyph drawn as that letter without its dot. None otherwise: the rows
    built on it say what the font lacks."""
    dotless = font.dotless.get(ord(ch))
    if dotless is None or dotless.kind != "made":
        return None
    recipe = Recipe(ch, dotless.name, dotless.name)
    recipe.dotless, recipe.dotless_row = dotless, True
    return recipe


def made_dotless_text(name, source, masters=1, named=None):
    """The log's line for a dotless glyph a build made; named: how a glyph's name is written (the log's
    ak.glyph_name_link: in italics, opened on a click), as it is by default."""
    named = named or (lambda text: text)
    return u"Made %s from %s without its dot%s: the font had none." % (
        named(name), named(source), u" in every master" if masters > 1 else u"")


def dot_kept_lines(recipes, bold=None, links=None):
    """The log's warnings after a build for the glyphs built on a dotted i or j (kept_dotted), one per
    letter and reason, as the lines on glyphs built with a diacritic too close are written (log_touches)."""
    bold = bold or (lambda text: text)
    links = links or (lambda chars: u" ".join(chars))
    groups, order = {}, []
    for r in recipes:
        if not kept_dotted(r):
            continue
        key = (r.base, r.dotless.reason, r.dotless.code)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r.char)
    lines = []
    for base, reason, code in order:
        chars = groups[(base, reason, code)]
        lines.append(u"%s built on %s with its dot: %s. Draw U+%04X, then rebuild %s: %s." % (
            bold(counted(len(chars), u"glyph")), base, reason, code, u"it" if len(chars) == 1 else u"them",
            links(chars)))
    return lines


def scripts_present(codes):
    """The scripts of LISTED_SCRIPTS the font has letters of (by their code points)."""
    found = set()
    for code in codes:
        if (0x0370 <= code < 0x0530 or 0x3040 <= code < 0x3100) and unicodedata.category(unichr_(code)).startswith(u"L"):
            found.add(script_of(unichr_(code)))
    return found


def glyph_name(font, base, roots, code, names=None, plain=False):
    """Glyphs' name for the character (iishort-cy, Alphatonos), else the base glyph's name and the
    marks' (adotbelow, acircumflexacute), but for plain (kana: uni304C, as kana fonts name them); uniXXXX
    when taken."""
    for name in ((names if names is not None else glyph_names()).get(code), None if plain else base + u"".join(roots)):
        if name and name not in font.names:
            return name
    return u"uni%04X" % code


class Ink(object):
    """A glyph's ink, in font units: its box, and the center of its top and bottom fifths (where marks
    center), and the right end of its bottom fifth (where an ogonek hangs)."""

    def __init__(self, left, bottom, right, top, top_center=None, bottom_center=None, bottom_right=None, advance=0,
                 top_right=None):
        self.left, self.bottom, self.right, self.top = left, bottom, right, top
        self.top_center = (left + right) / 2.0 if top_center is None else top_center
        self.bottom_center = (left + right) / 2.0 if bottom_center is None else bottom_center
        self.bottom_right = right if bottom_right is None else bottom_right
        self.top_right = right if top_right is None else top_right  # the right end of its top fifth (d's stem)
        self.advance = advance

    @property
    def center(self):
        return (self.left + self.right) / 2.0

    @property
    def width(self):
        return self.right - self.left


ALIAS_ROOTS = dict((alias, root) for root, aliases in MARK_ALIASES.items() for alias in aliases)


def mark_key(name):
    """The root of a mark glyph's name: acutecomb.case and acute are both acute; caroncomb.alt is the
    vertical caron, uni0326 the comma below."""
    whole = name[:-5] if name.endswith(".case") else name
    if whole in ALIAS_ROOTS:
        return ALIAS_ROOTS[whole]
    root = name.split(".")[0]
    if root in ALIAS_ROOTS:
        return ALIAS_ROOTS[root]
    if root.startswith(u"uni") and len(root) == 7:
        try:
            return MARKS.get(int(root[3:], 16), root)
        except ValueError:
            return root
    return root[:-4] if root.endswith("comb") else root


def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2.0


def load_model(path=None):
    """The open-licensed fonts' mark placements (mark_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), MODEL_FILE)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class Metrics(object):
    """A master's vertical metrics, in font units: the room a glyph has at a 120% line spacing reaches
    up to where the line above's descenders come down, and down to where the line below's tallest
    letters come up."""

    def __init__(self, upm, ascender, descender, caps=None):
        self.upm = float(upm)
        self.top = LEADING * self.upm + min(descender, 0)
        self.bottom = max(ascender, caps or 0) - LEADING * self.upm


class Placement(object):
    """Where marks go: learned from the font's own composites where it has them (per mark and case,
    else pooled per side and case), else from the open-licensed fonts (the model)."""

    def __init__(self, upm, model=None):
        self.upm = float(upm)
        self.model = model or {}
        self.seen = {}  # (mark root, case): [(gap, offset share)]
        self.sides = {}  # (side, case): [(gap, offset share)]

    def learn(self, composites, ink_of, case_of_glyph):
        """composites: [(base glyph, [(mark glyph, dx, dy[, root, side])])], each mark moved as far from
        the base as it sits in the composite (learned_marks), with the root and side of the character's
        own mark where given (else the glyph's: a borrowed macron would count as one above); ink_of(name)
        gives an Ink (or None); case_of_glyph(name) "upper" or "lower". Only each composite's first mark
        on a side counts."""
        for base, marks in composites:
            base_ink = ink_of(base)
            if base_ink is None or base_ink.width <= 0:
                continue
            case = case_of_glyph(base)
            done = set()
            for entry in marks:
                mark, dx, dy = entry[:3]
                root = entry[3] if len(entry) > 3 else mark_key(mark)
                side = entry[4] if len(entry) > 4 else mark_side(mark)
                ink = ink_of(mark)
                if ink is None or side in done or side in ("right", "topright", "kana", "left"):
                    continue
                done.add(side)
                if side == "above":
                    found = (ink.bottom + dy - base_ink.top, (ink.center + dx - base_ink.top_center) / base_ink.width)
                else:
                    reference = base_ink.bottom_right - ink.width / 2.0 if root == "ogonek" else base_ink.bottom_center
                    found = (base_ink.bottom - (ink.top + dy), (ink.center + dx - reference) / base_ink.width)
                self.seen.setdefault((root, case), []).append(found)
                self.sides.setdefault((side, case), []).append(found)

    def model_value(self, table, *keys):
        found = self.model.get(table, {})
        for key in keys:
            if key in found:
                return found[key]
        return None

    def own_scale(self, side, case):
        """How far the font's own gaps run from the model's on a side (1 without examples)."""
        own = median([g for g, _ in self.sides.get((side, case), [])]) if len(self.sides.get((side, case), [])) >= OWN_EXAMPLES else None
        model = self.model_value("side_gap", u"%s %s" % (side, case))
        if own is None or not model:
            return 1.0
        return min(2.0, max(0.5, own / (model * self.upm)))

    def gap(self, root, side, case, previous=None):
        """The gap of a mark to what is under (above: its letter, or the mark it stacks on) it."""
        if previous is not None:
            pair = self.model_value("pair_gap", u"%s+%s %s" % (previous, root, case), u"%s+%s %s" % (previous, root, other_case(case)))
            if pair is None:
                pair = self.model_value("stack_gap", u"%s %s" % (side, case), u"%s lower" % side)
            return (pair if pair is not None else DEFAULT_GAP_SHARE / 2) * self.upm * self.own_scale(side, case)
        own = self.seen.get((root, case), [])
        if len(own) >= 2:
            return median([g for g, _ in own])
        model = self.model_value("gap", u"%s %s" % (root, case), u"%s %s" % (root, other_case(case)))
        if model is not None:
            return model * self.upm * self.own_scale(side, case)
        pooled = self.sides.get((side, case), [])
        if pooled:
            return median([g for g, _ in pooled])
        return DEFAULT_GAP_SHARE * self.upm

    def offset(self, letter, root, side, case, previous=None):
        """A mark's center off the center of its letter's top (bottom) fifth, as a share of the
        letter's width: the font's habit on that side and case (all marks pooled, so they agree), or
        the model's, plus how far this letter's marks sit from that habit in the model (over b's
        bowl), or the model's offset for a mark on another (an acute by a circumflex)."""
        if previous is not None:
            pair = self.model_value("pair_offset", u"%s+%s %s" % (previous, root, case),
                                    u"%s+%s %s" % (previous, root, other_case(case)))
            return pair or 0.0
        habit_model = self.model_value("side_offset", u"%s %s" % (side, case)) or 0.0
        own = self.sides.get((side, case), [])
        habit = median([o for _, o in own]) if len(own) >= OWN_EXAMPLES else habit_model
        return habit + self.letter_shift(letter, root, side, case)

    def letter_shift(self, letter, root, side, case):
        """How far the model's fonts set marks off their habit on this very letter, as a share of its
        width (over b's bowl, right of l's stem), or 0."""
        habit_model = self.model_value("side_offset", u"%s %s" % (side, case)) or 0.0
        key = root if root in ("ogonek", "horn") else u"*"
        letter_offset = self.model_value("offset", u"%s %s %s" % (letter, side, key))
        return (letter_offset - habit_model) if letter_offset is not None else 0.0

    def height(self, root, case):
        """A mark's usual height in the model, in font units, or None."""
        value = self.model_value("height", u"%s %s" % (root, case), u"%s %s" % (root, other_case(case)))
        if not value and root == "caronvertical":
            value = VERTICAL_CARON_HEIGHT
        if root in KANA_HEIGHT:
            rows = [row for row in self.model.get("kana", {}).get(root, {}).values() if isinstance(row, list)]
            value = median([row[2] for row in rows]) or KANA_HEIGHT[root]
        return value * self.upm if value else None

    def kana_place(self, root, code):
        """(across, up) of a kana's voicing mark: its ink's center from the right end and the top of the
        letter's ink, in font units, as the corpus's fonts set it on that letter (else on its kana set)."""
        table = self.model.get("kana", {}).get(root, {})
        row = table.get(u"%04X" % code) or table.get(kana_set(code))
        across, up = (row[0], row[1]) if row else KANA_PLACES.get((root, kana_set(code)), (-0.05, -0.04))
        return across * self.upm, up * self.upm


def learnable(code, parts):
    """Whether a composite shows where marks go: its character decomposes into a letter and the marks
    its components are (an e acute of e and acute), not a fraction, a guillemet, or a middle dot."""
    return learned_marks(code, parts) is not None


def learned_marks(code, parts):
    """A learnable composite's marks as Placement.learn takes them, [(mark glyph, dx, dy, root, side)], or
    None: each moved as far from its letter as the components are (the base component's own move taken
    off), with the root and side of the character's own mark (a macron borrowed for a macron below is a
    mark below; a mark at a Greek capital's left is "left", on no side learned). parts: [(glyph, dx, dy)]."""
    if not code:
        return None
    ch = unichr_(code)
    decomposed = unicodedata.normalize("NFD", ch)
    if len(decomposed) != len(parts) or not decomposed[0].isalpha():
        return None
    convention = CONVENTIONS.get(code, {})
    left = script_of(ch) == "greek" and case_of(ch) == "upper"
    base_dx, base_dy = parts[0][1], parts[0][2]
    found = []
    for (glyph, dx, dy), mark in zip(parts[1:], decomposed[1:]):
        mark_code = convention.get(ord(mark), ord(mark))
        root = MARKS.get(mark_code)  # (G, K, L, N, R with a comma below decompose
        roots = (root, BORROWED.get(root))  # with a cedilla: Unicode's names for them predate the comma)
        if root is None or mark_key(glyph) not in roots:
            return None
        side = "left" if left and ord(mark) in LEFT_OF_CAPITALS else side_of(mark_code)
        found.append((glyph, dx - base_dx, dy - base_dy, root, side))
    return found


def mark_side(name):
    """Where a mark glyph goes, by its root's combining mark."""
    root = mark_key(name)
    for code, mark_root in MARKS.items():
        if mark_root == root:
            return side_of(code)
    if root in ("comma", "quotesinglbase", "period"):
        return "below"
    return "above"


def mark_ink(mark, ink_of, placement, case):
    """A Mark's parts laid out side by side (a drafted dieresis's two dots), drafts sized as the model's
    marks are; its box as an Ink, and its parts [(glyph, x scale, y scale, x, y)]."""
    laid, x = [], 0.0
    inks = [ink_of(part[0]) for part in mark.parts]
    if any(ink is None for ink in inks):
        return None, None
    scale = 1.0
    if mark.note and mark.note.startswith(u"draft"):
        wanted = placement.height(mark.root, case)
        ink = inks[0]
        if wanted and ink.top - ink.bottom > 0:
            scale = min(1.5, max(0.3, wanted / float(ink.top - ink.bottom)))
    gap = JOINED_GAP_SHARE * placement.upm
    for (glyph, sx, sy, _, _), ink in zip(mark.parts, inks):
        sx, sy = sx * scale, sy * scale
        if mark.joined == "stacked" and laid:  # on the first: centered over it
            first, (_, fsx, fsy, fx, fy) = inks[0], laid[0]
            center = fx + fsx * (first.left + first.right) / 2.0
            laid.append((glyph, sx, sy, center - sx * (ink.left + ink.right) / 2.0,
                         fy + fsy * first.top + gap - sy * ink.bottom))
            continue
        if mark.joined == "beside" and laid:  # after the first, a little apart, their bottoms level
            first, (_, fsx, fsy, fx, fy) = inks[0], laid[0]
            laid.append((glyph, sx, sy, fx + fsx * first.right + gap - sx * ink.left,
                         fy + fsy * first.bottom - sy * ink.bottom))
            continue
        if mark.joined in (True, "over"):  # over each other: centered on the first, their bottoms level
            first = inks[0]
            center = laid[0][3] + laid[0][1] * (first.left + first.right) / 2.0 if laid else sx * (first.left + first.right) / 2.0
            laid.append((glyph, sx, sy, center - sx * (ink.left + ink.right) / 2.0, sy * (first.bottom - ink.bottom)))
            continue
        left = min(sx * ink.left, sx * ink.right)
        laid.append((glyph, sx, sy, x - left, 0.0))
        x += abs(sx) * ink.width * (1 + DRAFT_SPACING)
    boxes = []
    for (glyph, sx, sy, dx, dy), ink in zip(laid, inks):
        xs = (sx * ink.left + dx, sx * ink.right + dx)
        ys = (sy * ink.bottom + dy, sy * ink.top + dy)
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    box = Ink(min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return box, laid


def layout(recipe, ink_of, placement, letter, gap_share=1.0, stack_share=1.0, scale=1.0):
    """[(glyph, x scale, y scale, x, y)] of a recipe at given shares of its gaps and mark scale, its
    ink's (top, bottom), and how much wider it is than its letter (a mark at a Greek capital's left)."""
    base = ink_of(recipe.base)
    case = case_of(recipe.char)
    parts = [(recipe.base, 1.0, 1.0, 0.0, 0.0)]
    top, bottom = base.top, base.bottom
    previous = {"above": None, "below": None}
    left_edge = base.left
    adscript = 0
    for mark in recipe.marks:
        box, laid = mark_ink(mark, ink_of, placement, case)
        if box is None:
            return None, None, None, 0
        side = mark.side
        if side == "adscript":  # after a Greek capital, on the baseline
            gap = ADSCRIPT_GAP_SHARE * placement.upm
            start = base.advance + gap
            for glyph, sx, sy, x, yy in laid:
                parts.append((glyph, sx, sy, round(x - box.left + start), round(yy - box.bottom + base.bottom)))
            adscript = gap + box.width + max(base.left, 0)
            continue
        if side == "left":  # at a capital's left, its top level with the capital's (Greek)
            gap = LEFT_GAP_SHARE * placement.upm * gap_share
            height = (box.top - box.bottom) * scale
            right = left_edge - gap
            for glyph, sx, sy, x, yy in laid:
                px = (x - box.left) * scale + right - box.width * scale
                py = (yy - box.bottom) * scale + base.top - height
                parts.append((glyph, sx * scale, sy * scale, round(px), round(py)))
            left_edge = right - box.width * scale
            continue
        if side == "right":  # the horn: at the top right, overlapping the letter a little
            dx = base.right - placement.upm * 0.02 - box.left
            dy = base.top - (box.top - box.bottom) * 0.6 - box.bottom
            parts.extend((g, sx, sy, x + dx, y + dy) for g, sx, sy, x, y in laid)
            top = max(top, box.top + dy)
            continue
        if side in ("topright", "kana"):  # beside the stem's top (the vertical caron), or a kana's top right
            if side == "topright":
                gx, gy = VERTICAL_CARON.get(letter) or VERTICAL_CARON[None]
                left_x, top_y = base.top_right + gx * placement.upm, base.top + gy * placement.upm
            else:
                across, up = placement.kana_place(mark.root, ord(letter[:1] or u" "))
                left_x = base.right + across - box.width * scale / 2.0
                top_y = base.top + up + (box.top - box.bottom) * scale / 2.0
            for glyph, sx, sy, x, yy in laid:  # scaled about its top left, its box's top left there
                px = (x - box.left) * scale + left_x
                py = (yy - box.top) * scale + top_y
                parts.append((glyph, sx * scale, sy * scale, round(px), round(py)))
            top = max(top, top_y)
            continue
        stacked = previous[side]
        gap = placement.gap(mark.root, side, case, stacked) * (stack_share if stacked else gap_share)
        offset = placement.offset(letter, mark.root, side, case, stacked) * base.width
        # the mark made smaller about its edge nearest the letter
        height = (box.top - box.bottom) * scale
        if side == "above":
            target_x = base.top_center + offset
            y = top + gap
            dy_edge, top = y, y + height
        else:
            reference = base.bottom_right - box.width * scale / 2.0 if mark.root == "ogonek" else base.bottom_center
            target_x = reference + offset
            y = bottom - gap - height
            dy_edge, bottom = y, y
        for glyph, sx, sy, x, yy in laid:
            # the part scaled about the mark's bottom left, then moved: its center on target_x, its bottom on y
            px = (x - box.left) * scale + target_x - box.width * scale / 2.0
            py = (yy - box.bottom) * scale + dy_edge
            parts.append((glyph, sx * scale, sy * scale, round(px), round(py)))
        previous[side] = mark.root
    widen = max(0, int(round(base.left - left_edge)))
    if widen:  # everything moves right, so the mark keeps the letter's left sidebearing
        parts = [(glyph, sx, sy, x + widen, y) for glyph, sx, sy, x, y in parts]
    return parts, top, bottom, widen + int(round(adscript))


def placement_key(recipe, index):
    """What makes two recipes' marks the same for a placement made by hand: the mark's glyphs (and
    whether each is flipped: an inverted breve is no breve), its side, its place among the marks on that
    side (a circumflex alone, or under an acute), and the letter's case (capitals take their marks
    higher than lowercase letters do)."""
    mark = recipe.marks[index]
    same_side = [m for m in recipe.marks if m.side == mark.side]
    return (part_signs(mark), mark.side, same_side.index(mark), case_of(recipe.char))


def related_marks(recipes, recipe, index):
    """[(another recipe, its mark's index)]: the buildable recipes with the same mark (placement_key), the
    one a placement made by hand on recipe's mark index most likely suits too (a circumflex raised on
    C suits the other capitals with a circumflex)."""
    key = placement_key(recipe, index)
    found = []
    for other in recipes:
        if other is recipe or other.missing:
            continue
        for at in range(len(other.marks)):
            if placement_key(other, at) == key:
                found.append((other, at))
                break
    return found


def part_signs(mark):
    """A mark's glyphs, each with whether it is flipped across and up and down (a caron drafted from an
    upside-down circumflex is not the circumflex drafted the right way up)."""
    return tuple((part[0], part[1] < 0, part[2] < 0) for part in mark.parts)


def mark_signature(mark):
    return (part_signs(mark), mark.side)


def same_mark_recipes(recipes, signature):
    """(alone, combined): the buildable recipes with the mark of that signature (its glyphs, their flips, and side), in
    list order, either case; alone: it is their only mark; combined: it is one of their marks (a
    macron with an acute). The letters to look at after placing the mark on one."""
    alone, combined = [], []
    for other in recipes:
        if other.missing:
            continue
        signatures = [mark_signature(mark) for mark in other.marks]
        if signature in signatures:
            (alone if len(signatures) == 1 else combined).append(other)
    return alone, combined


# Lining up marks: every mark above (or below) of a group set with its edge nearest the letter (a mark
# above: its bottom) at the same height as the reference's. A group: the same side, the same case, and
# letters of the same height (their ink tops, for marks above, within LINE_UP_HEIGHT_SHARE of the em of
# the reference letter's; bottoms for marks below): h's circumflex is not set as low as e's.
LINE_UP_SIDES = ("above", "below")
LINE_UP_ATTACHED = ("cedilla", "ogonek", "horn")  # joined to the letter: their own place, never lined up
LINE_UP_HEIGHT_SHARE = 0.06


def placed_mark_box(recipe, index, ink_of, placement, metrics):
    """(left, bottom, right, top) of a recipe's mark index as placed now (its hand changes too), or None."""
    checked = recipe.checked
    try:
        parts, _ = place(recipe, ink_of, placement, metrics)
    finally:
        recipe.checked = checked
    if parts is None:
        return None
    ranges = mark_ranges(recipe)
    if index >= len(ranges):
        return None
    first, last = ranges[index]
    return parts_box(parts[first:last], ink_of)


# Marks joined to their letter line up only with their own kind, by the edge fonts keep level (the
# corpus's 140 Latin fonts: ogonek bottoms level across A, E, I, U in half of them exactly, three in four
# within 6/1000 of the em; true cedillas (C, S, T) within 5; horn tops on O and U level; the vertical
# caron's top level on d, l, t, and the capital L's set 37/1000 lower, its own group by case)
ATTACHED_EDGES = {"ogonek": "bottom", "cedilla": "bottom", "horn": "top", "vertical caron": "top"}


def attached_kind(mark):
    """"ogonek", "cedilla" (a true one, not the comma fonts draw for it), "horn", "vertical caron", or None."""
    if mark.root == "ogonek":
        return "ogonek"
    if mark.root == "cedilla" and not mark.convention:
        return "cedilla"
    if mark.side == "right" or mark.root == "horn":
        return "horn"
    if mark.side == "topright":
        return "vertical caron"
    return None


def line_up_exclusion(recipe, index):
    """Why a recipe's mark is never lined up with others, or None: placed by a rule of its own."""
    mark = recipe.marks[index]
    if attached_kind(mark):
        return u"joined to its letter (ogonek, cedilla, horn, vertical caron): each lines up with its own kind"
    if mark.side not in LINE_UP_SIDES:
        return u"placed beside or on its letter (horn, vertical caron, Greek capitals' diacritics, kana)"
    if mark.root in LINE_UP_ATTACHED:
        return u"attached to its letter (cedilla, ogonek)"
    if mark.convention:
        return u"a shape of its own on this letter (%s)" % mark.convention
    if mark.joined:
        return u"made of marks set together"
    if len([m for m in recipe.marks if m.side == mark.side]) > 1:
        return u"stacked with another diacritic on the same side"
    return None


def line_up_plan(recipes, recipe, index, ink_of, placement, metrics, upm):
    """(line, moves, left_out): the height the reference mark's near edge sits at; [(other, its mark's
    index, how far it moves up)] for the marks of its group; [(other, why)] for the same side and case
    left as they are (their own rule, stacked, or on a taller or shorter letter)."""
    mark = recipe.marks[index]
    kind = attached_kind(mark)
    if kind is not None:
        return line_up_attached(recipes, recipe, index, kind, ink_of, placement, metrics)
    box = placed_mark_box(recipe, index, ink_of, placement, metrics)
    base = ink_of(recipe.base)
    if box is None or base is None or line_up_exclusion(recipe, index):
        return None, [], []
    above = mark.side == "above"
    line = box[1] if above else box[3]
    reach = base.top if above else base.bottom
    case = case_of(recipe.char)
    moves, left_out = [], []
    for other in recipes:
        if other is recipe or other.missing or case_of(other.char) != case:
            continue
        at = next((i for i, m in enumerate(other.marks) if m.side == mark.side), None)
        if at is None:
            continue
        why = line_up_exclusion(other, at)
        other_base = ink_of(other.base)
        if why is None and other_base is not None:
            other_reach = other_base.top if above else other_base.bottom
            if abs(other_reach - reach) > LINE_UP_HEIGHT_SHARE * upm:
                why = u"a %s letter" % ((u"taller" if other_reach > reach else u"shorter") if above else
                                        (u"deeper" if other_reach < reach else u"shallower"))
        if why is None:
            other_box = placed_mark_box(other, at, ink_of, placement, metrics)
            if other_box is None:
                why = u"not placed"
            else:
                rise = line - (other_box[1] if above else other_box[3])
                if abs(rise) >= 0.5:
                    moves.append((other, at, rise))
                continue
        left_out.append((other, why))
    return line, moves, left_out


def shift_words(dx, dy):
    """u"12 right, 8 down": how far the suggested mark sits from the current one."""
    words = []
    if dx:
        words.append(u"%d %s" % (abs(dx), u"right" if dx > 0 else u"left"))
    if dy:
        words.append(u"%d %s" % (abs(dy), u"up" if dy > 0 else u"down"))
    return u", ".join(words) or u"in place"


def anchors_sentence(count, bold=None):
    """The Mark anchors tab's top line: how many glyphs get anchors ("none gets anchors", "1 gets anchors",
    "2 get anchors")."""
    bold = bold or (lambda text: text)
    if not count:
        return u"none gets anchors"
    return u"%s %s anchors" % (bold(count), u"gets" if count == 1 else u"get")


def anchors_status(script, bases, marks, others, getting, fonts, left_out, masters, bold=None, italic=None):
    """The Mark anchors tab's status lines, under the window's top line (which names the font and master,
    owner's image 265): the script, its bases and marks (others: "2 ligatures" and the like), how many get
    anchors and whose placements they follow, the letters left out, and what a font of several masters
    (masters: True) leaves to FontLab."""
    bold = bold or (lambda text: text)
    italic = italic or (lambda text: text)
    text = u"%s: %s and %s%s; %s, placed as %s." % (
        bold(script), bold(counted(bases, u"base")), bold(counted(marks, u"mark")),
        u"".join(u", %s" % bold(other) for other in others), anchors_sentence(getting, bold),
        corpus_sentence(fonts, script, bold))
    if left_out:
        text += u" %s that %s no marks (in Unicode's letters and the corpus's fonts) %s left out." % (
            bold(counted(left_out, u"letter")), u"takes" if left_out == 1 else u"take", u"is" if left_out == 1 else u"are")
    if masters:
        text += (u" With several masters, the mark and mkmk code is left to FontLab's automatic features (they read "
                 u"the anchors of each master).")
    if getting:
        text += u" Nothing changes until you click %s." % italic(ADD_TICKED_ANCHORS)
    return text


def corpus_sentence(fonts, script, bold=None):
    """The Mark anchors tab's top line: whose placements the anchors follow, in the fonts' number."""
    bold = bold or (lambda text: text)
    if not fonts:  # (none of the script's measured: Latin's stand in, anchor_row; never "0 of the corpus's fonts")
        return u"the corpus's Latin fonts place theirs (none of its %s fonts was measured)" % script
    if fonts == 1:
        return u"the corpus's %s %s font places its own" % (bold(1), script)
    return u"%s of the corpus's %s fonts place theirs" % (bold(fonts), script)


def units_up(value):
    """A length in whole units, rounded up ("1 unit", "12 units"): what is left over is never said as 0."""
    whole = int(value)
    return counted(whole + (1 if value > whole else 0), u"unit")


def propagated_text(count, put_back, on, bold=None):
    """What Apply to related letters says it did, without its list of letters: count letters took the
    selected glyph's placement (on: its character), put_back of them only by going back to the
    suggestion (the selected glyph's mark was reset)."""
    bold = bold or (lambda text: text)
    letters = bold(counted(count, u"letter"))
    if put_back == count:
        return u"Put the diacritics of %s back as suggested, as on %s" % (letters, on)
    text = u"Placed the diacritics of %s as on %s" % (letters, on)
    if put_back:
        text += u" (%s put back as suggested)" % put_back
    return text


def row_text(built, refill=False, shift=None, existing=False, notes=()):
    """A row's Built from cell: what the glyph is built from, then its data in parentheses (a glyph of
    the font to fill, how a glyph the font has compares with the suggestion, what placing it took), as
    one would write it by hand: "A + gravecomb (suggested: 25 right, 4 up)". No period: a cell. What
    moves is the diacritic, in a tool about diacritics: "mark" went without saying (the owner's report of
    2026-11-15)."""
    data = []
    if refill:
        data.append(u"its glyph is in the font, empty: filled when built")
    if existing:
        data.append(u"placed as suggested" if shift == (0, 0) else
                    (u"suggested: %s" % shift_words(*shift)) if shift else
                    u"drawn, not built of components: compare by eye")
    data += list(notes)
    return built + (u" (%s)" % u"; ".join(data) if data else u"")


def suggested_caption(shift):
    """The editor's caption under the suggestion beside a glyph the font has: "Suggested (11 right, 46
    down)", "Suggested (the same)", or "Suggested" (drawn, compared by eye)."""
    if shift == (0, 0):
        return u"Suggested (the same)"
    return u"Suggested (%s)" % shift_words(*shift) if shift else u"Suggested"


# The list's sections, as the owner named them on 2026-11-15 (data in parentheses: what a check does)
CAN_BE_BUILT = u"Can be built"
EXISTING_OTHERWISE = u"Existing glyphs with suggestions (tick to rebuild)"
EXISTING_AS_SUGGESTED = u"Existing glyphs that match suggestions (tick to rebuild)"
JUST_BUILT = u"Built in this window (tick to rebuild)"  # the list's section of the glyphs built in this window
LACKING = u"Need a mark or letter the font lacks"


def list_sections(recipes, shift_of, just_built=()):
    """[(title, [recipe indexes])] of the letters list's sections, in order (empty ones included): those
    that can be built; the font's own glyphs, placed otherwise than suggested and as suggested; those just
    built here (just_built: their characters), kept in view after a build, unchecked, so that what is done
    afterward (Correct mirrored components, a placement applied, marks lined up) reaches them: they left
    the list once built, and nothing could be set right on them (the owner's report of 2026-11-14); and
    those that need a mark or letter the font lacks. shift_of(recipe): existing_shift."""
    groups = [(CAN_BE_BUILT, []), (EXISTING_OTHERWISE, []), (EXISTING_AS_SUGGESTED, []), (JUST_BUILT, []),
              (LACKING, [])]
    for index, r in enumerate(recipes):
        if r.missing:
            at = 4
        elif not r.existing:
            at = 0
        elif r.char in just_built:
            at = 3
        else:
            at = 2 if shift_of(r) == (0, 0) else 1
        groups[at][1].append(index)
    return groups


# The scripts listed only when the font has letters of them, as running text names them: "kana" is a common
# noun in English, lowercase as "hiragana" (owner's image 247)
SCRIPT_WORDS = {"greek": u"Greek", "cyrillic": u"Cyrillic", "kana": u"kana"}


def letters_status(buildable, lacking, details=(), room=(), absent=(), bold=None, italic=None):
    """The Letters with diacritics tab's status lines, under the window's top line (which names the font
    and master, owner's image 265): how many glyphs can be built (details: how their marks were found),
    how many need a mark or letter the font lacks, the room sentences, and the scripts the font has no
    letters of (absent: LISTED_SCRIPTS' keys). Every count right at 0, 1, and 2 (owner's image 247:
    "0 glyphs can be built")."""
    bold = bold or (lambda text: text)
    italic = italic or (lambda text: text)
    if buildable:
        text = u"%s can be built%s" % (bold(counted(buildable, u"glyph")),
                                       (u" (%s)" % u", ".join(details)) if details else u"")
        if lacking:
            text += u"; %s %s a mark or letter the font lacks" % (
                bold(counted(lacking, u"other")), u"needs" if lacking == 1 else u"need")
    elif lacking:
        text = u"No glyph can be built: %s %s a mark or letter the font lacks" % (
            bold(counted(lacking, u"glyph")), u"needs" if lacking == 1 else u"need")
    else:
        text = u"No glyph can be built"
    text += u"." + u"".join(u" " + sentence for sentence in room)
    if buildable:
        text += u" Nothing is made until you click %s." % italic(BUILD_TICKED)
    if absent:
        words = sorted((SCRIPT_WORDS.get(key, key.capitalize()) for key in absent), key=lambda word: word.lower())
        text += u" The font has no %s letters: theirs are not listed." % listed(words, u"or")
    return text


def preview_parts(selected, editable, related):
    """{widget's attribute: whether it is shown} of the letters tab's preview: the reference (heading,
    chooser, picture, note), the line over its heading, and the line beside it while a row is selected; the editor and its
    three buttons while the selected glyph can be drawn and placed; the strip of letters with the same
    diacritic while it holds letters. Nothing selected: none of them (they only showed empty). Compact
    diacritics to fit the line sits with the preview, left of Reset diacritics, while a row is selected."""
    return {"reference_title": selected, "reference_font": selected, "reference": selected,
            "reference_note": selected, "reference_line": selected, "lower_line": selected, "hint": selected, "compact_box": selected, "editor": editable,
            "reset_marks_button": editable,
            "propagate_button": editable, "line_up_button": editable, "strip_label": related and selected,
            "strip_area": related and selected}


def reset_text(marks):
    """Reset diacritics' text: "Reset diacritic" for a glyph with one."""
    return u"Reset diacritic" if marks == 1 else u"Reset diacritics"


def propagate_text(targets):
    """Apply to related letters' text, with how many where there are some."""
    return u"Apply to %s" % counted(targets, u"related letter") if targets else u"Apply to related letters"


def line_up_text(kind, side):
    """Line up diacritics' text: by the kind of an attached diacritic (ogonek, cedilla, horn, vertical caron), else
    by the side of the selected one (above, below), else plain (no diacritic to line up)."""
    if side is None:
        return u"Line up diacritics"
    return u"Line up %ss" % kind if kind else u"Line up diacritics %s" % side


ATTACHED_KINDS = ("ogonek", "cedilla", "horn", "vertical caron")


def room_texts():
    """{button: every text it takes}: the editor's buttons keep the width of their widest (keep_preview_room),
    so that what stands beside them never moves when the selected row changes their texts (the owner's report
    of 2026-11-16: Compact diacritics to fit the line moved 33 pixels right on a row that cannot be built)."""
    return {"reset_marks_button": [reset_text(n) for n in (1, 2)],
            "propagate_button": [propagate_text(n) for n in (0, 1, 888)],
            "line_up_button": [line_up_text(None, None)] + [line_up_text(None, side) for side in ("above", "below")] +
                              [line_up_text(kind, "above") for kind in ATTACHED_KINDS]}


# The preview's parts that keep their room when hidden, so that what stays shown never moves: selecting a
# glyph that cannot be built hid the editor and the strip, and Compact diacritics to fit the line jumped up
# (the owner's report of 2026-11-16). The editor's three buttons give theirs up (ROOM_RELEASED): with them
# hidden, the box sits alone on its line, and goes to its right end (owner's image 184), as a box alone does
ROOM_KEPT = ("editor", "strip_label", "strip_area")
ROOM_RELEASED = ("reset_marks_button", "propagate_button", "line_up_button")

PROGRESS_EVERY = 200  # glyphs read between two words to the window's progress (busy_progress lets events through)
PROGRESS_ROWS = 20  # rows drawn between two (each row's picture places its glyph)
STOPPED_READING = (u"Stopped while reading the font: nothing is listed. Pick another character set, or tick or untick "
                   u"a box above the list, to read it again.")
# The code points whose glyphs are read for emptiness (Font.drawn): the letters built here and the marks,
# spacing marks, and punctuation they are built of (drafts take ’ ” ‘ – of General Punctuation), the kana,
# and Adobe's comma below
EMPTY_READ_BELOW = 0x2070
MARK_CODES_READ = (0xF6C3,)


def show_count(label, text):
    """A search's count beside its field, hidden while it says nothing: an empty label still took its room
    and the row's spacing, so the field ended short of the other rows' right edge (owner's image 185)."""
    label.setText(text)
    try:
        label.setVisible(bool(text))
    except Exception:
        pass


# What Font Check hands over is kept for the session, by font (FontLab's number of it): a window opened
# again on that font (from another tool, by the arrows, from the menu) lists it as the window it handed it to
# did, with the checks it had last (owner's report 186: going to another window and back, the list Font Check
# sent was gone, as each window is made anew). Until Font Check hands that font something else, or the font
# is closed. Kept on sys: this module is loaded again for each window.
HANDED_OVER = "_freelab_compose_handed"


def hand_over_memory():
    """{font number: {"characters": [...], "checks": {character: checked}}}, for the session."""
    store = getattr(sys, HANDED_OVER, None)
    if not isinstance(store, dict):
        store = {}
        setattr(sys, HANDED_OVER, store)
    return store


def kept_hand_over(store, font_id, characters, open_ids):
    """The characters a window opened on font_id lists as Font Check's: characters when Font Check hands
    them over (kept for that font, its checks forgotten: a new list), else those kept for the font, or None.
    open_ids: the open fonts' numbers (None where FontLab cannot tell): what was kept for a font no longer
    open is forgotten."""
    if open_ids is not None:
        for key in list(store):
            if key not in open_ids:
                del store[key]
    if characters is not None:
        if font_id is not None:
            store[font_id] = {"characters": list(characters), "checks": {}}
        return list(characters)
    kept = store.get(font_id) if font_id is not None else None
    return list(kept["characters"]) if kept else None


def opening_font(ak):
    """(FontLab's number of the font a window being opened will work on, as window_font chooses it: the
    calling window's font, else the one FontLab shows; the open fonts' numbers). (None, []) with no font
    open, (None, None) where FontLab cannot tell."""
    try:
        import fontlab
        workspace = fontlab.flWorkspace.instance()
        open_ids = ak.open_font_ids(workspace)
        if not open_ids:
            return None, open_ids
        calling = ak.calling_font()
        if calling in open_ids:
            return calling, open_ids
        return ak._font_id(workspace.currentPackage), open_ids
    except Exception:
        return None, None


class NotStopped(Exception):
    """Stands for the shared module's Stopped where it has none (never raised)."""


def list_controls(font, rows, searching):
    """{what: whether it is clickable} of the controls over a list, with no font (font False) or no row
    (rows: how many the list holds, shown or not): the choices that make the list (the character set,
    Also list existing glyphs; the script and Write the feature code)
    need a font; the search field needs rows, or a text in it to take out (searching)."""
    return {"choices": bool(font), "search": bool(rows) or bool(searching)}


def no_font_line(ak):
    """The top line with no font open: the shared one (windows take the next font opened), else plainly."""
    if hasattr(ak, "no_font_line"):
        return ak.no_font_line()  # (while other fonts are open, why this window has none)
    return getattr(ak, "NO_FONT_LINE", None) or u"No font is open."


def font_line(ak, package):
    """The window's top line: the font and its master as every FreeLab window names them (the shared
    font_named: "(of 3 masters)" only with more than one), or the no-font line with no font."""
    if package is None:
        return no_font_line(ak)
    try:
        masters = int(getattr(package, "mastersCount", 1) or 1)
    except Exception:
        masters = 1
    name, master = u"%s" % package.tfn, getattr(package, "master", None)
    named = getattr(ak, "font_named", None)
    if named is not None:
        return named(name, master, masters)
    bold = getattr(ak, "b", None) or (lambda text: u"<b>%s</b>" % text)
    return bold(name) + (u", master %s" % bold(master) if master else u"")


def tool_named(ak, title):
    """A FreeLab tool named in a log line: an italic link the log opens it by (the shared tool_link, owner's
    image 220), else its name in italics."""
    link = getattr(ak, "tool_link", None)
    return link(title) if link is not None else u"<i>%s</i>" % title


def fit_to_contents(box):
    """A dropdown as wide as its widest choice, never stretched across its row (owner's image 239)."""
    try:
        QtGui = _qt()[1]
        box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
    except Exception:
        pass
    return box


def keeps_check(recipe, was_there, built_now):
    """Whether a row read again keeps the check it had: a glyph to build does; a glyph of the font does
    when it was one before (its check, given by hand to rebuild it, stays: a glyph listed to show it and
    checked stays listed, checked) and it was not built or rebuilt since (built_now: the characters the
    build before this reading made). A glyph built since comes unchecked, so that a later build does not
    rebuild it over edits made in between. A glyph to build that was the font's (an undo took back the
    build) takes the plan's check, not the one it had as the font's glyph: built, undone, and built again,
    20 letters were listed under Can be built unchecked, and silently skipped."""
    if not recipe.existing:
        return not was_there
    return bool(was_there) and recipe.char not in built_now


def section_title(text):
    """A section row's title without its count: "Can be built (12)" is "Can be built"."""
    return text.rsplit(u" (", 1)[0] if text.endswith(u")") else text


def component_marks(layer):
    """[(glyph name, x scale, y scale, x, y)] of a layer's mark components: those after the first (its
    letter), or all of them where the letter is drawn as outlines of the layer's own."""
    found, drawn = [], False
    for shape in layer.shapes:
        try:
            if not shape.isComponent:
                drawn = True
                continue
            name = shape.shapeData.componentGlyph
            t = shape.transform
            found.append((u"%s" % name, t.m11(), t.m22(), t.dx(), t.dy()))
        except Exception:
            continue
    return found if drawn else found[1:]


def line_up_attached(recipes, recipe, index, kind, ink_of, placement, metrics):
    """line_up_plan for a mark joined to its letter: the same kind on letters of the same case, its far
    edge (ATTACHED_EDGES) level with the reference's; a letter where it is stacked with another mark on
    its side is left out."""
    box = placed_mark_box(recipe, index, ink_of, placement, metrics)
    if box is None:
        return None, [], []
    bottom = ATTACHED_EDGES[kind] == "bottom"
    line = box[1] if bottom else box[3]
    case = case_of(recipe.char)
    moves, left_out = [], []
    for other in recipes:
        if other is recipe or other.missing or case_of(other.char) != case:
            continue
        at = next((i for i, m in enumerate(other.marks) if attached_kind(m) == kind), None)
        if at is None:
            continue
        side = other.marks[at].side
        if len([m for m in other.marks if m.side == side]) > 1:
            left_out.append((other, u"stacked with another diacritic on the same side"))
            continue
        other_box = placed_mark_box(other, at, ink_of, placement, metrics)
        if other_box is None:
            left_out.append((other, u"not placed"))
            continue
        rise = line - (other_box[1] if bottom else other_box[3])
        if abs(rise) >= 0.5:
            moves.append((other, at, rise))
    return line, moves, left_out


def mark_ranges(recipe):
    """(first, last + 1) of each mark's parts among a placed recipe's parts (the letter is the first)."""
    ranges, start = [], 1
    for mark in recipe.marks:
        ranges.append((start, start + len(mark.parts)))
        start += len(mark.parts)
    return ranges


def parts_box(parts, ink_of):
    """(left, bottom, right, top) of placed parts' ink, or None."""
    boxes = []
    for glyph, sx, sy, x, y in parts:
        ink = ink_of(glyph)
        if ink is None:
            continue
        xs, ys = (sx * ink.left + x, sx * ink.right + x), (sy * ink.bottom + y, sy * ink.top + y)
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def adjusted(recipe, parts, ink_of):
    """The placed parts with the recipe's marks moved and scaled by hand (recipe.adjust): each mark
    scaled about its own center, then moved."""
    if not recipe.adjust or parts is None:
        return parts
    parts = list(parts)
    for index, (first, last) in enumerate(mark_ranges(recipe)):
        change = recipe.adjust.get(index)
        if not change or last > len(parts):
            continue
        dx, dy, kx, ky = change
        box = parts_box(parts[first:last], ink_of)
        if box is None:
            continue
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        for at in range(first, last):
            glyph, sx, sy, x, y = parts[at]
            parts[at] = (glyph, sx * kx, sy * ky, cx + (x - cx) * kx + dx, cy + (y - cy) * ky + dy)
    return parts


# Compact diacritics to fit the line: the key its choice is remembered by (glyph_compose.json), and its help
COMPACT_KEY = "compact_diacritics"
COMPACT_HELP = (u"Fits the diacritics of a glyph too tall for a 120%% line: the gaps of its stack closed just enough, "
                u"and, where that is not enough, its diacritics made smaller, down to %d%%; its row says what it took. "
                u"The letter is never changed, and a letter that reaches past the line by itself (a descender) does "
                u"not count. Unticked (as at first), a glyph too tall says by how much, for you to fix by hand. A "
                u"glyph whose diacritics you placed by hand keeps them either way, and its row says whether they "
                u"fit. Nothing changes in the font until you build (a glyph the font has is only compared with "
                u"the other suggestion). The choice is remembered." % round(MIN_SCALE * 100))

# What a row's notes say of the room of a 120% line (the top line counts the rows by them)
COMPACT_NOTE = u"gaps closed"  # how a note of a glyph made compact begins
STILL_NOTE = u"still"  # how a note of a glyph too tall even compact begins
TOO_TALL_NOTE = u"too tall for a 120% line"  # in the note of a glyph that does not fit


def is_compact_note(note):
    """Whether a row's note says the glyph was made compact ("gap closed ...", "gaps closed ...")."""
    return note.startswith(COMPACT_NOTE) or note.startswith(u"gap closed")


def compact_note(gaps, diacritics, percent=None):
    """A row's note of what compacting took, its words following the counts: "gap closed to fit a 120%
    line" for a glyph with one gap, "gaps closed and diacritics at 85% to fit a 120% line"."""
    closed = u"gap closed" if gaps == 1 else COMPACT_NOTE
    if percent is None:
        return u"%s to fit a 120%% line" % closed
    return u"%s and %s at %d%% to fit a 120%% line" % (closed, u"diacritic" if diacritics == 1 else u"diacritics",
                                                      percent)


def hand_note(count):
    """A row's note of the diacritics the hand moved or scaled: "diacritic placed by hand" for one."""
    return u"diacritic placed by hand" if count == 1 else HAND_NOTE


def room_counts(recipes):
    """(made compact, too tall even so, too tall as placed) among recipes, by their notes: what the top
    line says of the room of a 120% line. The third counts only where compacting is switched off."""
    compact = still = tall = 0
    for recipe in recipes:
        notes = list(recipe.notes)
        compact += 1 if any(is_compact_note(note) for note in notes) else 0
        still += 1 if any(note.startswith(STILL_NOTE) for note in notes) else 0
        tall += 1 if any(TOO_TALL_NOTE in note and not note.startswith(STILL_NOTE) for note in notes) else 0
    return compact, still, tall


def compact_text(on, kept, count=None, bold=None):
    """The log's line when Compact diacritics to fit the line is switched: what the suggestions are now
    (count: the glyphs made compact, switched on; too tall as placed, switched off), and how many glyphs
    placed by hand keep what was set. It names the box first: it began "Glyphs are no longer made compact",
    which, after the log's time cut short, the owner read as "9 Glyphs" (2026-11-16). Counts bold with their
    nouns (bold: the shared module's b; owner's images 297 and 301)."""
    bold = bold or (lambda text: text)
    box = u"<i>Compact diacritics to fit the line</i>"
    one = count == 1
    if on:
        text = (u"%s on: glyphs too tall for a 120%% line are made compact." % box if count is None else
                u"%s on: no glyph is too tall for a 120%% line." % box if not count else
                u"%s on: %s too tall for a 120%% line %s made compact." % (box, bold(counted(count, u"glyph")),
                                                                       u"is" if one else u"are"))
    else:
        text = (u"%s off: diacritics keep their own gaps and size, and the rows say which glyphs are too tall for a "
                u"120%% line." % box if count is None else
                u"%s off: diacritics keep their own gaps and size, and every glyph fits a 120%% line." % box
                if not count else
                u"%s off: diacritics keep their own gaps and size, and %s %s too tall for a 120%% line (%s by how "
                u"much)." % (box, bold(counted(count, u"glyph")), u"is" if one else u"are",
                             u"its row says" if one else u"their rows say"))
    if kept:
        text += u" %s placed by hand %s what you set." % (bold(counted(kept, u"glyph")),
                                                           u"keeps" if kept == 1 else u"keep")
    return text


def room_details(compact, still, tall, bold=None):
    """The top line's sentences about the room of a 120% line, in glyphs, each following its number ("42
    glyphs that were too tall for a 120% line were made compact.": the owner's words, 2026-11-16; it said
    "42 made compact to fit a 120% line" among the other counts before)."""
    bold = bold or (lambda text: text)
    found = []
    if compact:
        found.append(u"%s that %s too tall for a 120%% line %s made compact." % (
            bold(counted(compact, u"glyph")), u"was" if compact == 1 else u"were", u"was" if compact == 1 else u"were"))
    if still:
        found.append(u"%s %s too tall even when compact: %s left unticked." % (
            bold(counted(still, u"glyph")), u"is" if still == 1 else u"are", u"it is" if still == 1 else u"they are"))
    if tall:
        found.append(u"%s %s too tall for a 120%% line as placed." % (bold(counted(tall, u"glyph")),
                                                                     u"is" if tall == 1 else u"are"))
    return found


GAP_STEPS = 12  # halvings of the gaps' range that find how far a stack's gaps are closed (to 0.6/4096 of them)


def room_limits(metrics, base):
    """(top, bottom) a glyph's marks must keep within: the room of a 120% line (metrics), or the letter's
    own ink where the letter itself reaches past it. A letter's descender can come lower than the line
    below's tallest letters come up (y's -240 against Noto Sans's -131, its ascender set at 1069): the
    marks are not to blame for that, and nothing done to them mends it. ӯ was counted 109 units too tall,
    and its macron made 70% (the owner's report of 2026-11-15: "big on N and small on Y")."""
    return max(metrics.top, base.top), min(metrics.bottom, base.bottom)


def place(recipe, ink_of, placement, metrics=None, letter=None):
    """The recipe's components [(glyph, x scale, y scale, x, y)] and width (its letter's): each mark
    placed by the Placement, and, where its marks would reach past the room a 120% line spacing leaves
    (metrics; room_limits), made compact, by no more than it needs: its stack's gaps closed just enough to
    fit, down to CLOSED_GAPS of them, and only where that is not enough, its marks made smaller too, to
    the largest whole percent that fits, down to MIN_SCALE. Closing every gap to CLOSED_GAPS at once set
    Ӛ's dieresis 46 units down where 12 were needed (the owner's report of 2026-11-15). recipe.notes says
    what it took, and whether it still does not fit. A recipe whose compact is False (Compact diacritics
    to fit the line, switched off) is left as placed, and its note says it is too tall. A recipe whose
    marks were placed by hand is measured as placed: its notes say whether that fits (finished)."""
    letter = letter or unicodedata.normalize("NFD", recipe.char)[0]
    base = ink_of(recipe.base)
    recipe.notes = []
    was_checked = recipe.checked  # (a glyph placed by hand is judged by what was set: finished)
    if base is None:  # its letter not drawn (in this master): nothing to place
        return None, 0
    parts, top, bottom, widen = layout(recipe, ink_of, placement, letter)
    if parts is None:
        return None, base.advance
    if metrics is None:
        return finished(recipe, parts, ink_of), base.advance + widen
    # (the words follow the counts: each diacritic above, below, or at a capital's left keeps a gap; all
    # but a horn and an adscript are made smaller)
    gaps = sum(1 for mark in recipe.marks if mark.side in ("above", "below", "left"))
    smaller = sum(1 for mark in recipe.marks if mark.side not in ("right", "adscript"))
    finish = lambda laid_parts: finished(recipe, laid_parts, ink_of, metrics, base, was_checked)
    limit_top, limit_bottom = room_limits(metrics, base)

    def fits(laid):
        return laid[1] <= limit_top and laid[2] >= limit_bottom

    def over(laid):
        return max(laid[1] - limit_top, limit_bottom - laid[2])
    if fits((parts, top, bottom)):
        return finish(parts), base.advance + widen
    if not getattr(recipe, "compact", True):
        # Left as placed, its marks at their own gaps and size: the note says by how much it is too tall, and
        # the glyph stays checked (whoever switched compacting off means to see to it by hand)
        recipe.notes.append(u"%s %s" % (units_up(over((parts, top, bottom))), TOO_TALL_NOTE))
        return finish(parts), base.advance + widen
    laid = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS)
    if fits(laid):  # the gaps closed just enough: the most of them that fits
        low, high = CLOSED_GAPS, 1.0
        for _ in range(GAP_STEPS):
            middle = (low + high) / 2.0
            tried = layout(recipe, ink_of, placement, letter, middle, middle)
            if fits(tried):
                low, laid = middle, tried
            else:
                high = middle
        note = compact_note(gaps, smaller)
    else:  # closed, and the marks made smaller: the largest whole percent that fits
        low = int(round(MIN_SCALE * 100))
        laid = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS, low / 100.0)
        if fits(laid):
            high = 100
            while high - low > 1:
                middle = (low + high) // 2
                tried = layout(recipe, ink_of, placement, letter, CLOSED_GAPS, CLOSED_GAPS, middle / 100.0)
                if fits(tried):
                    low, laid = middle, tried
                else:
                    high = middle
        note = compact_note(gaps, smaller, low)
    parts, top, bottom, widen = laid
    recipe.notes.append(note)
    if not fits(laid):
        recipe.notes.append(u"%s %s %s: needs a shorter letter or marks drawn for it" % (
            STILL_NOTE, units_up(over(laid)), TOO_TALL_NOTE))
        recipe.checked = False
    return finish(parts), base.advance + widen


HAND_NOTE = u"diacritics placed by hand"  # the note of a glyph whose marks the hand moved or scaled (hand_note)


def finished(recipe, parts, ink_of, metrics=None, base=None, was_checked=None):
    """The placed parts with the hand's changes, and a note of them. A glyph placed by hand keeps what was
    set whichever way Compact diacritics to fit the line is switched, so its notes are of what was set,
    not of the suggestion under it: whether it fits, and by how much it does not. Its row said "gaps closed
    and marks at 70%" with the box unticked (the owner's report of 2026-11-15). Its check follows what was
    set too (was_checked: its check before placing): the suggestion under it, too tall even compact, no
    longer unchecks it with its reason wiped from the row; only what was set, too tall while compacting is
    on, unchecks it, as a suggestion too tall even compact is, its row saying by how much."""
    if not recipe.adjust:
        return parts
    placed = adjusted(recipe, parts, ink_of)
    recipe.notes = []
    if was_checked is not None:
        recipe.checked = was_checked
    box = parts_box(placed, ink_of) if metrics is not None and base is not None and placed else None
    if box is not None:
        limit_top, limit_bottom = room_limits(metrics, base)
        over = max(box[3] - limit_top, limit_bottom - box[1])
        if over > 0:
            recipe.notes.append(u"%s %s" % (units_up(over), TOO_TALL_NOTE))
            if getattr(recipe, "compact", True):
                recipe.checked = False
    recipe.notes.append(hand_note(len(recipe.adjust)))
    return placed


# ---------------------------------------------------------------------------
# Mirrored components, the limits a built glyph can reach, searching the lists, and what a font handed
# over leaves out
# ---------------------------------------------------------------------------

def reverses_direction(sx, sy, shear_x=0.0, shear_y=0.0):
    """Whether a component transformed so is mirrored (its matrix's determinant negative): its contours
    then run the other way, and a renderer filling by nonzero winding shows a hole where it overlaps a
    part that is not. A half turn (both scales negative) is not."""
    return sx * sy - shear_x * shear_y < 0


def reversal_note(parts, ink_of):
    """A note for a row whose placed parts [(glyph, x scale, y scale, x, y)] have a mirrored one, or u"":
    which glyph, whether its box meets another part's, and what to do."""
    boxes = [parts_box([part], ink_of) for part in parts]
    for at, part in enumerate(parts):
        if not reverses_direction(part[1], part[2]):
            continue
        box = boxes[at]
        meets = box is not None and any(
            other is not None and box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]
            for index, other in enumerate(boxes) if index != at)
        if meets:
            return (u"%s is mirrored and overlaps another part: renderers show a hole there (decompose the glyph and "
                    u"remove overlap, or correct the contour direction)" % part[0])
        return (u"%s is mirrored, its contours reversed: a hole would show where it overlapped another part "
                u"(correct the contour direction)" % part[0])
    return u""


MIRRORED_ADVICE = (u"A mirrored component's contours run the other way: where it overlaps another part, renderers "
                   u"show a hole. Decompose the glyph and remove overlap, or correct the contour direction.")


def mirrored_text(count, bold=None):
    """The log's line about glyphs built with a mirrored component, without their list."""
    bold = bold or (lambda text: text)
    return u"%s built with a mirrored component" % bold(counted(count, u"glyph"))


def mirrored_components(layer):
    """The glyph names of a layer's components whose transform is mirrored (reverses_direction)."""
    found = []
    for shape in layer.shapes:
        try:
            if not shape.isComponent:
                continue
            t = shape.transform
            if reverses_direction(t.m11(), t.m22(), t.m21(), t.m12()):
                found.append(u"%s" % shape.shapeData.componentGlyph)
        except Exception:
            continue
    return found


LINE_NAME = u"120% line"  # the room LEADING leaves, among the lines drawn in the editors
# The lines drawn in the editors, as Font Check's Vertical metrics names them: (the field of its
# VerticalMetrics, the name drawn, its sign, what clips past it). Two kinds. A limit is a line past which
# something real happens: Windows clips past winAscent and winDescent, macOS past the hhea values, and
# past the room of a 120% line the glyph meets the line above or below (LINE_NAME). Only a limit turns
# amber when a mark crosses it. The font's ascender and descender and the typo values are reference
# lines: every accented capital rises over the ascender, and a mark below comes under the descender,
# with no harm done, so they are drawn and never tinted.
WINDOWS, MACOS = u"Windows", u"macOS"
LIMIT_FIELDS = (("win_ascent", u"winAscent", 1, WINDOWS), ("typo_ascender", u"typo ascender", 1, None),
                ("hhea_ascender", u"hhea ascender", 1, MACOS), ("ascender", u"font ascender", 1, None),
                ("descender", u"font descender", 1, None), ("typo_descender", u"typo descender", 1, None),
                ("hhea_descender", u"hhea descender", 1, MACOS), ("win_descent", u"winDescent", -1, WINDOWS))
WARNING_RGB = (217, 161, 59)  # amber, the suite's warning color (the strip's letters to look at too)


def limit_values(read, metrics=None):
    """[(name, units, what happens past it)] of the lines: read(field) gives a font value or None
    (LIMIT_FIELDS; a value of 0 is not set), metrics (a Metrics) the room of a 120% line. The third is
    WINDOWS or MACOS (it clips there), LINE_NAME (the next line is met there), or None (a reference line)."""
    found = []
    for field, name, sign, clips in LIMIT_FIELDS:
        try:
            value = read(field)
        except Exception:
            value = None
        if value:
            found.append((name, sign * float(value), clips))
    if metrics is not None:
        found += [(LINE_NAME, metrics.top, LINE_NAME), (LINE_NAME, metrics.bottom, LINE_NAME)]
    return found


def limit_note(reasons, above):
    """What a limit's label says happens past it, or u"" for a reference line: "Windows clips above",
    "Windows and macOS clip below", "meets the line above"."""
    side = u"above" if above else u"below"
    who = [name for name in (WINDOWS, MACOS) if name in reasons]
    notes = []
    if who:
        notes.append(u"%s %s %s" % (u" and ".join(who), u"clips" if len(who) == 1 else u"clip", side))
    if LINE_NAME in reasons:
        notes.append(u"meets the line %s" % side)
    return u"; ".join(notes)


def limit_lines(values, merge=None):
    """[(units, label, whether it is a limit)], highest first, of the lines [(name, units, what happens
    past it)]: those at the same height (rounded) are one line, labeled once with every name (merge joins
    names as Font Check does: "typo and hhea ascender"; without it, commas), the height, and, for a limit,
    what happens past it in parentheses ("winAscent 1160 (Windows clips above)"). A reference line and a
    limit at the same height are one limit."""
    found, reasons, order = {}, {}, []
    for entry in values:
        name, value = entry[0], entry[1]
        if value is None:
            continue
        key = int(round(value))
        if key not in found:
            found[key], reasons[key] = [], []
            order.append(key)
        if name not in found[key]:
            found[key].append(name)
        if len(entry) > 2 and entry[2] and entry[2] not in reasons[key]:
            reasons[key].append(entry[2])
    join = merge or (lambda names: u", ".join(names))
    lines = []
    for key in sorted(order, reverse=True):
        note = limit_note(reasons[key], key > 0)
        lines.append((key, u"%s %d" % (join(found[key]), key) + (u" (%s)" % note if note else u""), bool(note)))
    return lines


def crossed_limits(limits, boxes):
    """The indexes of the limits a mark crosses, among the lines [(units, label, whether it is a limit)]:
    boxes are the marks' (left, bottom, right, top); a limit over the baseline is crossed by a top above
    it, one under it by a bottom below. A reference line is never crossed: nothing clips there. (A line
    given without its kind, an older scene's room, counts as a limit.)"""
    hit = set()
    for at, line in enumerate(limits):
        value = line[0]
        if len(line) > 2 and not line[2]:
            continue
        for _, bottom, _, top in boxes:
            if (value > 0 and top > value) or (value < 0 and bottom < value):
                hit.add(at)
    return hit


DETACH_SHARE = 0.25  # of the em: a mark moved by hand this far from its letter and its other marks is off it


def box_distance(box, other):
    """How far apart two boxes (left, bottom, right, top) are, in units: 0 where they touch or overlap."""
    dx = max(0.0, other[0] - box[2], box[0] - other[2])
    dy = max(0.0, other[1] - box[3], box[1] - other[3])
    return (dx * dx + dy * dy) ** 0.5


def far_marks(parts, ranges, indexes, ink_of, limits, upm, advance):
    """{mark index: [(kind, data)]} of the marks among indexes (those moved by hand) that a placement
    left far off, the glyph placed as parts: ("outside", None), past what the editor opens to show (an
    em past the font's lines and the glyph's advance); ("clipped", the line's label), over a line where
    Windows or macOS clips (winAscent, winDescent, the hhea values: a 120% line met is the row's own
    note); ("detached", units), farther than DETACH_SHARE of the em from its letter and its other marks.
    A placement applied to 18 letters sent each mark 6,675 units right and 4,551 up, and the log said it
    in green as done (the owner's report of 2026-11-14)."""
    found = {}
    letter = parts_box(parts[:1], ink_of)
    heights = [line[0] for line in limits or ()] + [0.0] + ([letter[1], letter[3]] if letter else [])
    top, bottom = max(heights), min(heights)
    reach = VIEW_REACH * upm
    for index in indexes:
        if not 0 <= index < len(ranges):
            continue
        first, last = ranges[index]
        box = parts_box(parts[first:last], ink_of)
        if box is None:
            continue
        reasons = []
        if box[1] > top + reach or box[3] < bottom - reach or box[2] < -reach or box[0] > finite(advance) + reach:
            reasons.append(("outside", None))
        for line in limits or ():
            if len(line) > 2 and line[2] and u"clip" in line[1] and crossed_limits([line], [box]):
                reasons.append(("clipped", line[1]))
        others = parts_box([part for at, part in enumerate(parts) if not first <= at < last], ink_of)
        if others is not None:
            apart = box_distance(box, others)
            if apart > DETACH_SHARE * upm:
                reasons.append(("detached", apart))
        if reasons:
            found[index] = reasons
    return found


def far_words(kind, data):
    """A far-off mark's reason as a row's note says it: "a mark outside the view", "a mark past winAscent
    1160 (Windows clips above)", "a mark away from its letter (6,700 units)"."""
    if kind == "outside":
        return u"a diacritic outside the view"
    if kind == "clipped":
        return u"a diacritic past %s" % data
    return u"a diacritic away from its letter (%s units)" % grouped(data)


def far_note(found):
    """A row's note about its marks left far off (far_marks' result), each reason once; u"" for none."""
    words = []
    for index in sorted(found):
        for kind, data in found[index]:
            text = far_words(kind, data)
            if text not in words:
                words.append(text)
    return u"; ".join(words)


def far_lines(far, links, bold=None, upm=1000.0):
    """The log's warnings about letters whose marks were left far off: far is [(character, far_marks'
    result)]; one line per reason, naming its letters (links: how a list of characters is written). upm:
    the font's em, which the distance said is a share of (512 units in an em of 2048)."""
    bold = bold or (lambda text: text)
    by_reason, order = {}, []
    for char, found in far:
        for index in sorted(found):
            for kind, data in found[index]:
                key = (kind, data if kind == "clipped" else None)
                if key not in by_reason:
                    by_reason[key] = []
                    order.append(key)
                if char not in by_reason[key]:
                    by_reason[key].append(char)
    lines = []
    for kind, data in order:
        chars = by_reason[(kind, data)]
        one = len(chars) == 1
        what = {"outside": u"a diacritic outside the view (over an em past the font's lines)",
                "clipped": u"a diacritic past %s" % data,
                "detached": u"a diacritic away from its letter (over %s units)" % grouped(DETACH_SHARE * finite(upm, 1000.0))}[kind]
        lines.append(u"%s now %s %s: %s. Look at %s; <i>Reset diacritics</i> on %s row puts %s back." % (
            bold(counted(len(chars), u"letter")), u"has" if one else u"have", what, links(chars),
            u"it" if one else u"them", u"its" if one else u"a", u"it"))
    return lines


# ---------------------------------------------------------------------------
# A mark moved by hand: how far it can go, how its move is written, and where it shows
# ---------------------------------------------------------------------------

# How far a mark (or an anchor) can be moved by hand, either way, in font units. TrueType writes a
# component's offset and every coordinate in 16 bits (-32768 to 32767), and the largest em OpenType allows
# is 16384 units: a mark placed anywhere in such an em and moved this far still lands on coordinates the
# format can hold. Nothing a designer means is farther; a move within it stays exactly as it was made.
HAND_REACH = 16000.0
SCALE_REACH = (0.1, 10.0)  # a mark scaled by hand: no smaller, no larger
VIEW_REACH = 1.0  # of the em: the editor zooms out to hold a mark this far past its limits, no farther
EDGE_MARGIN = 9  # pixels: how far inside the editor's edge the arrow of a mark outside the view is drawn


def finite(value, fallback=0.0):
    """value as a float, or fallback where it is no finite number (infinite, not a number, no number)."""
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    if value != value or value in (float("inf"), float("-inf")):
        return fallback
    return value


def within_reach(value):
    """A move by hand kept within HAND_REACH either way (a value that is no finite number: no move)."""
    return max(-HAND_REACH, min(HAND_REACH, finite(value)))


def clamped_adjust(change):
    """[dx, dy, x scale, y scale] of a hand's change kept to what a font can hold: the move within
    HAND_REACH, the scales within SCALE_REACH; values within those bounds as they are."""
    dx, dy, kx, ky = change
    low, high = SCALE_REACH
    return [within_reach(dx), within_reach(dy), max(low, min(high, finite(kx, 1.0))),
            max(low, min(high, finite(ky, 1.0)))]


def whole_units(value):
    """A length as a whole number of units, halves rounded away from zero (the same on Python 2 and 3)."""
    value = finite(value)
    whole = int(abs(value) + 0.5)
    return -whole if value < 0 else whole


def grouped(value):
    """A whole number of units with its thousands grouped: 950, 1,200, -12,345."""
    whole = whole_units(value)
    digits, groups = u"%d" % abs(whole), []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    return (u"-" if whole < 0 else u"") + u",".join([digits] + groups)


def moved_words(dx, dy):
    """u"12 right, 1,250 up": how far a mark was moved by hand, in whole units; u"" when not moved."""
    dx, dy = whole_units(dx), whole_units(dy)
    words = []
    if dx:
        words.append(u"%s %s" % (grouped(abs(dx)), u"right" if dx > 0 else u"left"))
    if dy:
        words.append(u"%s %s" % (grouped(abs(dy)), u"up" if dy > 0 else u"down"))
    return u", ".join(words)


def outside_view(box, width, height, margin=EDGE_MARGIN):
    """Where a mark lies when none of it shows in a view width by height pixels: box is its (left, top,
    right, bottom) on screen. None when any of it shows; else (x, y, across, down): the point just inside
    the view's edge nearest the mark, and the direction to it (-1, 0, or 1 each way), for an arrow."""
    left, top, right, bottom = [finite(value) for value in box]
    across = -1 if right < 0 else (1 if left > width else 0)
    down = -1 if bottom < 0 else (1 if top > height else 0)
    if not across and not down:
        return None
    x = min(max((left + right) / 2.0, margin), max(width - margin, margin))
    y = min(max((top + bottom) / 2.0, margin), max(height - margin, margin))
    if across:
        x = margin if across < 0 else max(width - margin, margin)
    if down:
        y = margin if down < 0 else max(height - margin, margin)
    return x, y, across, down


def view_bounds(top, bottom, box_top, box_bottom, upm, margin):
    """(top, bottom) of what an editor shows, in font units: its lines' own (top, bottom), opened to hold
    the glyph's ink (box_top, box_bottom, with a margin), but no farther than VIEW_REACH past them. A mark
    moved farther is outside the view (the editor draws an arrow for it) and the glyph keeps its size."""
    reach = VIEW_REACH * upm
    return (max(top, min(finite(box_top, top - margin) + margin, top + reach)),
            min(bottom, max(finite(box_bottom, bottom + margin) - margin, bottom - reach)))


def mark_line(label, change, outside=False):
    """The line under the editor for the selected mark: what it is, how far the hand moved it (whole units,
    thousands grouped) and scaled it, whether it lies outside the view, and what the keys do."""
    dx, dy, kx, ky = clamped_adjust(change)
    words = moved_words(dx, dy)
    moved = u", moved %s" % words if words else u""
    sized = u", at %d%% \N{MULTIPLICATION SIGN} %d%%" % (whole_units(kx * 100), whole_units(ky * 100)) \
        if (kx != 1 or ky != 1) else u""
    where = u" (outside the view: the arrow at the edge points to it)" if outside else u""
    return (u"%s%s%s%s. Arrows move it (<i>Shift</i>: 10 units); its frame scales it; <i>Backspace</i> puts it "
            u"back." % (label, moved, sized, where))


# The list's buttons and the committing actions, with "Tick" for what sets check boxes ("Check" is the verb
# of the buttons that run checks: owner's image 261)
TICK_ALL = u"Tick all"
TICK_NONE = u"Untick all"
TICK_HIGH_VALUE = u"Tick high-value glyphs"
BUILD_TICKED = u"Build ticked glyphs"
ADD_TICKED_ANCHORS = u"Add ticked anchors"


def build_text(checked, hidden):
    """The Build button's text: "Build ticked glyphs", always. It builds every ticked glyph, shown or not; how
    many of those a search hides is said beside the search field (search_count): said on the button, "Build 12
    ticked glyphs (5 not shown)" made the window wider as a filter was ticked (owner's images 331 and 332)."""
    return BUILD_TICKED


def checks_text(on, changed, checked, hidden, bold=None, noun=u"glyph"):
    """The log's line for Tick all (on) or Untick all: how many rows it changed, and how many are ticked
    now in all, those a search hides included, saying so (the owner's report of 2026-11-16: neither button
    left a line). changed: the rows the click ticked or unticked; checked: the rows ticked now, shown or
    not; hidden: of those, the ones a search hides. "Ticked 30 glyphs (42 ticked in all, 12 of them not
    shown)", "Unticked 1 glyph (none ticked now)". The numbers in parentheses bold alone (owner's images 297 and
    301: a number with no noun of its own)."""
    bold = bold or (lambda text: text)
    number = lambda n: bold(u"%d" % n)  # noqa: E731
    if not changed:  # (never "Ticked 0 glyphs": as the shared check_line says it)
        return u"<i>%s</i> changed nothing." % (TICK_ALL if on else TICK_NONE)
    done = u"%s %s" % (u"Ticked" if on else u"Unticked", bold(counted(changed, noun)))
    if not checked:
        return u"%s (none ticked now)." % done
    if not hidden:
        return u"%s (%s ticked in all)." % (done, number(checked))
    if on or hidden < checked:
        return u"%s (%s ticked in all, %s of them not shown)." % (done, number(checked), number(hidden))
    return u"%s (%s still ticked, not shown: a search hides %s)." % (done, number(hidden), u"it" if hidden == 1 else u"them")


def anchors_button_text(checked, hidden):
    """The Mark anchors tab's write button's text, as build_text: it adds the anchors of every ticked
    glyph, shown or not, so it says how many of those a search hides: "Add ticked anchors", "Add anchors
    to 12 ticked glyphs (5 not shown)"; now always the first, the count beside the search field (build_text)."""
    return ADD_TICKED_ANCHORS


# ---------------------------------------------------------------------------
# A mirrored component set right: the glyph it points to mirrored into a glyph of its own, its contours
# reversed, and the component pointed there, no longer mirrored
# ---------------------------------------------------------------------------

MIRROR_SUFFIXES = {"x": u".mirrored", "y": u".flipped"}  # a corrected glyph's name: left to right, upside down


def mirror_axis(m11, m12, m21, m22):
    """The mirror a mirrored component's transform holds: "y" (upside down) when it only turns y over,
    else "x" (left to right). Any mirrored transform is a proper one after one mirror; this picks the
    mirror that leaves the proper one plainest."""
    return "y" if m22 < 0 <= m11 and not m12 and not m21 else "x"


def mirror_of(axis, advance, bottom, top):
    """(x scale, y scale, dx, dy) of the mirror a corrected glyph is made by: left to right about the
    middle of its advance width, or upside down about the middle of its ink, so that the corrected glyph
    stands where its source does (whole units, as outlines are)."""
    if axis == "y":
        return 1.0, -1.0, 0.0, float(whole_units(finite(bottom) + finite(top)))
    return -1.0, 1.0, float(whole_units(advance)), 0.0


def without_mirror(transform, mirror):
    """(m11, m12, m21, m22, dx, dy) of the component of a corrected glyph that draws what a mirrored
    component drew: transform is the mirrored component's (Qt's order: x' = m11 x + m21 y + dx,
    y' = m12 x + m22 y + dy), mirror the corrected glyph's (mirror_of). The mirror is its own inverse, so
    the component's transform is the old one after the mirror; its determinant is positive."""
    m11, m12, m21, m22, dx, dy = transform
    sx, sy, tx, ty = mirror
    return (m11 * sx, m12 * sx, m21 * sy, m22 * sy, dx + m11 * tx + m21 * ty, dy + m12 * tx + m22 * ty)


def corrected_name(source, axis, taken):
    """The name of the corrected glyph of source mirrored along axis (caron.flipped, comma.mirrored), with
    a number where that name is another glyph's (taken(name) tells)."""
    name = source + MIRROR_SUFFIXES[axis]
    at = 2
    while taken(name):
        name = u"%s%s%d" % (source, MIRROR_SUFFIXES[axis], at)
        at += 1
    return name


def corrected_text(count, made, bold=None):
    """The log's line about mirrored components set right, without its lists: in how many glyphs, and how
    many corrected glyphs were added for them."""
    bold = bold or (lambda text: text)
    text = u"Corrected the mirrored components of %s" % bold(counted(count, u"glyph"))
    if made:
        text += u" (%s added, mirrored with %s contours reversed)" % (
            bold(counted(made, u"glyph")), u"its" if made == 1 else u"their")
    return text


def correct_button_text(count):
    """The button that sets mirrored components right: of how many listed glyphs."""
    if not count:
        return u"Correct mirrored components"
    return u"Correct mirrored components of %s" % counted(count, u"glyph")


def ascii_lower(text):
    """A text with its A to Z in lowercase and nothing else changed: FontLab's Python knows Unicode 5.2,
    so lower() would differ from Python 3's for newer letters, and a search must not."""
    return u"".join(unichr_(ord(c) + 32) if u"A" <= c <= u"Z" else c for c in (text or u""))


def row_matches(query, name, char, code, parts=()):
    """Whether a row is found by a search, by its glyph alone, never by the text of its notes: its
    character is the query, or its Unicode value is (U+0105, u+105, 0105, 105), or its glyph name holds
    the query (A to Z in any case), or the name of a glyph it is built from does (parts: its letter's and
    marks' glyph names). One character typed is that character: the glyph, the letters with diacritics
    built on it (h: h with a circumflex, with a dot above), and its unencoded forms (h.sc), not every name or note that holds the letter
    (typing h found all 70 rows of a list, by "has bottom, top already" in their notes: the owner's report
    of 2026-11-14). An empty query finds every row."""
    query = (query or u"").strip()
    if not query:
        return True
    composed = unicodedata.normalize("NFC", query)
    if char and composed == char:
        return True
    if len(composed) == 1 or single_code(composed) is not None:
        # (both decomposed: u with diaeresis finds u with diaeresis and macron, e with circumflex e with
        # circumflex and acute; the query composed against the row decomposed found neither)
        if char and unicodedata.normalize("NFD", char).startswith(unicodedata.normalize("NFD", composed)):
            return True
        name = u"%s" % (name or u"")
        return name == composed or name.startswith(composed + u".")
    low = ascii_lower(query)
    if any(low in ascii_lower(text) for text in [name] + list(parts or ()) if text):
        return True
    digits = low[2:] if low.startswith(u"u+") else low
    if code and digits and len(digits) <= 6 and all(c in u"0123456789abcdef" for c in digits):
        return int(digits, 16) == code
    return False


def search_count(shown, total, query, noun=u"glyph", filtered=False, ticked_hidden=0):
    """What stands beside a search field: nothing without a query or a filter (filtered: List only
    high-value glyphs), else "3 of 341 glyphs shown." (a sentence, with its period: owner's image 332), and
    how many of the rows hidden are ticked, which the tab's button writes too: "3 of 341 glyphs shown (5
    ticked among those hidden)." (build_text)."""
    if not (query or u"").strip() and not filtered:
        return u""
    if ticked_hidden:
        return u"%d of %s shown (%d ticked among those hidden)." % (shown, counted(total, noun), ticked_hidden)
    return u"%d of %s shown." % (shown, counted(total, noun))


FIND_A_GLYPH = u"Find a glyph…"  # (a placeholder ends with an ellipsis: owner's image 309)
VALUE_ONLY_LABEL = u"List only high-value glyphs."
VALUE_ONLY_HELP = (u"Shows only the glyphs <i>Font Check</i> lists under <i>High-value missing glyphs</i> for this font "
                   u"(the missing glyphs of the languages already within reach, which they complete), as <i>Tick "
                   u"high-value glyphs</i> reads them; rows not shown keep their ticks. Grayed until <i>Font Check</i>'s "
                   u"data has been read.")


VALUE_BUTTON_HELP = (u"Ticks the glyphs <i>Font Check</i> lists under <i>High-value missing glyphs</i> for this font "
                     u"(the missing glyphs of the languages already within reach, which they complete), and unticks "
                     u"the others shown. <i>Font Check</i>'s own settings count where its window is open, else those "
                     u"it starts with. Grayed until <i>Font Check</i>'s data has been read, and when a click would "
                     u"change no tick.")


def high_value_text(count, bold=None):
    """The log's line for Tick high-value glyphs (either tab)."""
    bold = bold or (lambda text: text)
    return (u"Ticked %s <i>Font Check</i> lists as high-value (%s complete languages already within reach), and no "
            u"other shown." % (bold(counted(count, u"glyph")), u"it helps" if count == 1 else u"they help"))


def value_filter(box, wanted):
    """The characters a list shows while List only high-value glyphs is ticked (Font Check's high-value set), or
    None: the box unticked, absent, or the set not known (then nothing is hidden for it)."""
    try:
        on = box is not None and bool(_property(box, "checked"))
    except Exception:
        on = False
    return set(wanted) if on and wanted is not None else None


LEFT_OUT_ORDER = ("built", "have", "script", "unbuildable", "several")


def on_circle(ch):
    """A character as a line of text shows it: a mark alone on a dotted circle (as Font Check shows one), so
    that it is not drawn on the parenthesis before it or on nothing: the top line read "the font has it
    already ()" for a combining mark (the owner's report of 2026-11-16)."""
    try:
        if ch and unicodedata.category(ch[0]).startswith(u"M"):
            return unichr_(DOTTED_CIRCLE) + ch
    except (TypeError, ValueError):
        pass
    return ch


def single_code(text):
    """The code point of a text that is one character, or None. A character past U+FFFF is two code
    units (a surrogate pair) on a narrow Python 2 (FontLab 7's) and one on Python 3: one character on both.
    Half a pair alone is no character."""
    if len(text) == 1:
        return None if 0xD800 <= ord(text) < 0xE000 else ord(text)
    if len(text) == 2 and 0xD800 <= ord(text[0]) < 0xDC00 and 0xDC00 <= ord(text[1]) < 0xE000:
        return 0x10000 + ((ord(text[0]) - 0xD800) << 10) + (ord(text[1]) - 0xDC00)
    return None


def left_out_given(given, recipes, font, absent_scripts=(), built=()):
    """[(reason, [characters])] of the characters handed over (Font Check's) that the list has no row
    for, in LEFT_OUT_ORDER: "built" (built in this window: a combining mark has no row once the font has
    it, and the top line said "the font has it already" just after building it, which read as Font Check
    having handed over a glyph the font had: the owner's report of 2026-11-16), "have" (the font has its
    glyph already: there all along), "script" (a script the font has no letters of), "unbuildable" (no
    letter with marks, and no combining mark, that Glyph Compose builds), "several" (not one character).
    built: the characters built in this window."""
    listed_chars = set(r.char for r in recipes)
    found = dict((reason, []) for reason in LEFT_OUT_ORDER)
    for item in given:
        if item in listed_chars:
            continue
        code = single_code(item)
        if code is None:
            reason = "several"
        elif font.by_code.get(code) and font.by_code[code] not in font.empty:
            reason = "built" if item in built else "have"
        elif code > 0xFFFF:  # (two code units on FontLab's Python: no script of Unicode's names, the same on both)
            reason = "unbuildable"
        elif script_of(item) in absent_scripts:
            reason = "script"
        else:
            reason = "unbuildable"
        if item not in found[reason]:
            found[reason].append(item)
    return [(reason, found[reason]) for reason in LEFT_OUT_ORDER if found[reason]]


def left_out_sentence(total, left_out, names=None, bold=None):
    """The top line's sentence about the characters handed over that are not listed (left_out_given), or
    u"" when each has its row: how many, and why, each named (names: how a list of characters is
    written; plainly, without it). Whole sentences for one glyph and for several. bold: the shared module's
    b, for the counts ("Of the **6 glyphs** Font Check handed over, **5** are not listed": owner's images 297
    and 301)."""
    names = names or (lambda chars: u" ".join(chars))
    bold = bold or (lambda text: text)
    number = lambda n: bold(u"%d" % n)  # noqa: E731
    count = sum(len(chars) for _, chars in left_out)
    if not count:
        return u""
    sole = count == 1

    def are(n, one, many):
        return (u"it %s" % one) if sole else (u"%s %s" % (number(1), one)) if n == 1 else (u"%s %s" % (number(n), many))

    reasons = []
    for reason, chars in left_out:
        n = len(chars)
        text = {"built": u"it was built here" if sole else u"%s %s built here" % (number(n), u"was" if n == 1 else u"were"),
                "have": u"the font has it already" if sole else u"the font has %s already" % number(n),
                "script": are(n, u"is of a script the font has no letters of", u"are of a script the font has no "
                                                                                  u"letters of"),
                "unbuildable": are(n, u"is not built from a letter and marks", u"are not built from a letter and marks"),
                "several": are(n, u"is not one character", u"are not one character each")}[reason]
        reasons.append(u"%s (%s)" % (text, names(chars)))
    if total == 1:
        head = u"The glyph Font Check handed over is not listed"
    elif count == total:
        head = u"None of the %s Font Check handed over is listed" % bold(counted(total, u"glyph"))
    else:
        head = u"Of the %s Font Check handed over, %s not listed" % (
            bold(counted(total, u"glyph")), u"%s is" % number(1) if sole else u"%s are" % number(count))
    return u"%s: %s." % (head, listed(reasons))


def settled_clusters(clusters, holds, has=None):
    """(kept, reduced, dropped): the reference's examples as a font can draw them. Each cluster (a
    letter and its combining marks) is composed (Unicode has one character for many: U+1EA4 for A with
    a circumflex and an acute), and one character the font has (has(text); every one, without it) is
    drawn as designed; what stays a letter and marks is kept when holds(text) says the font sets the
    marks on the letter, else tried again without its last mark, down to one mark, else left out: a
    mark the font does not attach is drawn beside the letter, which shows nothing. reduced: how many
    lost a mark; dropped: how many were left out. Twice the same example is shown once."""
    kept, reduced, dropped = [], 0, 0
    for cluster in clusters:
        letter, marks = cluster[:1], cluster[1:]
        if not marks:
            if cluster and cluster not in kept:
                kept.append(cluster)
            continue
        found = None
        for count in range(len(marks), 0, -1):
            written = letter + marks[:count]
            composed = unicodedata.normalize("NFC", written)
            for text in [composed] + ([written] if written != composed else []):
                if has is not None and not has(text):
                    continue
                if len(text) == 1 or holds(text):
                    found = text
                break  # (the first form the font has is the one drawn: the other would be shaped the same)
            if found is not None:
                break
        if found is None:
            dropped += 1
            continue
        if count < len(marks):
            reduced += 1
        if found not in kept:
            kept.append(found)
    return kept, reduced, dropped


CLUSTER_SLACK = 0.2  # of the em: a cluster's ink may reach this far past its letter's (a horn, a wide tilde)
CLUSTER_ADVANCE = 0.02  # of the em: a cluster this much wider than its letter gave a mark room beside it


def ink_holds(letter, cluster, em, letter_advance=None, cluster_advance=None):
    """Whether a cluster drawn in a font keeps its marks on its letter: letter and cluster are the
    (left, right) of their ink, drawn from the same origin; the advances, where known, tell a mark
    given room of its own beside the letter (a font that does not attach it)."""
    if letter_advance is not None and cluster_advance is not None \
            and cluster_advance > letter_advance + CLUSTER_ADVANCE * em:
        return False
    slack = CLUSTER_SLACK * em
    return cluster[0] >= letter[0] - slack and cluster[1] <= letter[1] + slack


def reference_note(text, family, chosen, reduced=0, dropped=0, names=None):
    """The line under a reference: what is drawn and in which font (the chosen one, or the one drawn in
    its place), and the examples shown with a mark fewer or left out (settled_clusters). names: {family:
    the name it goes by} (FreeLab's own font is several families falling back to one another: one name)."""
    names = names or {}
    family, chosen = names.get(family, family), names.get(chosen, chosen)
    note = (u"%s in %s." % (text, family)) if family == chosen or not chosen else (
        u"%s lacks %s: shown in %s." % (chosen, text, family))
    if reduced:
        note += u" %s does not stack these marks: %s shown with a mark fewer." % (
            family, u"1 example is" if reduced == 1 else u"%d examples are" % reduced)
    if dropped:
        note += u" %s left out: %s would set its mark beside the letter." % (
            u"1 example is" if dropped == 1 else u"%d examples are" % dropped, family)
    return note


REFERENCE_RECENT = 5  # the fonts picked last, listed at the top of the reference font's chooser


def reference_rows(default, families, recent=(), shown=None):
    """The reference font chooser's rows, [(label, family)]: FreeLab's own font first, as the default,
    then the fonts picked recently (recent, latest first: those still installed), set apart by a
    separator ((None, None)), then the installed families; without the bundled font or a recent pick, the
    families alone. The usual choices are thus at the top, where the list opens, not among a couple of
    thousand installed fonts. A family that is not installed is never a row: a pick saved before whose
    font is gone since was listed and chosen, drawing nothing of its own (the owner's report of
    2026-11-14: FreeLang's old family name). shown: the name FreeLab's font goes by (it is several
    fonts, one falling back to the next: its other families, named after it, are not choices of their
    own)."""
    def own(family):  # (FreeLang's families: "FreeLang CJK", "FreeLang+ General", ...)
        return family == default or bool(shown and family[:len(shown) + 1] in (shown + u" ", shown + u"+"))
    names = [family for family in families if not own(family)]
    installed = set(names)
    top = [family for family in recent if family in installed and not own(family)][:REFERENCE_RECENT]
    rows = ([(u"%s (default)" % (shown or default), default)] if default else []) + [(family, family) for family in top]
    if rows:
        rows.append((None, None))
    return rows + [(family, family) for family in names]


def installed_pick(saved, recent, families):
    """(pick, recent) of a saved reference font and the fonts picked recently, as the installed families
    allow: a family that is not installed any more is dropped (the pick becomes None); the pick heads the
    recent ones. families empty (Qt could not list them): kept as saved, nothing being known."""
    recent = [family for family in (recent or []) if family]
    if saved and saved not in recent:
        recent.insert(0, saved)
    if not families:
        return saved, recent[:REFERENCE_RECENT]
    installed = set(families)
    return (saved if saved in installed else None), [family for family in recent if family in installed][:REFERENCE_RECENT]


def gone_reference_text(family, default_name=None):
    """The log's line about a reference font picked before that is not installed any more."""
    used = (u"%s, the default, is used again" % default_name) if default_name else \
        u"the installed font with the most of these characters is used"
    return u"The reference font picked before, %s, is not installed any more: the pick is forgotten, and %s." % (
        family, used)


def high_value_characters(fc, codes, attaches=None, nearly=None, statuses=None, inferred=True):
    """The characters Font Check lists under High-value missing glyphs for a font with these code
    points: what the languages within reach, of the scripts the font has, miss. Computed by Font Check's
    own functions (fc: its module), in the order its Coverage view calls them; attaches, nearly,
    statuses, and inferred are its settings (its defaults when not given)."""
    languages, _ = fc.chosen_languages(fc.load_languages(), inferred)
    font = fc.FontCharacters(codes, attaches)
    reach = fc.NEARLY_MISSING if nearly is None else nearly
    scripts = fc.coverage(languages, font, reach, statuses is None, statuses)
    results = [r for s in scripts if s.present for r in s.results]
    return set(item for row in fc.add_rows(results) for item in row.items)


# ---------------------------------------------------------------------------
# Centers: snapping a dragged mark, and carrying a placement to related letters
# ---------------------------------------------------------------------------

SNAP_PIXELS = 5  # a dragged mark's center snaps to its letter's center within this many pixels
CENTERED = 0.5  # font units: a mark this close to a center is centered on it


def letter_centers(ink, x, side):
    """[(x, label)] of the centers a mark of a side centers on, its letter's ink at x: the ink box's
    center, and the center of its topmost ink (lowest, for a mark below) where that differs (a, r, G);
    [] for a mark set beside its letter."""
    if ink is None or side not in ("above", "below"):
        return []
    edge = ink.top_center if side == "above" else ink.bottom_center
    if abs(edge - ink.center) < CENTERED:
        return [(x + ink.center, u"center")]
    return [(x + ink.center, u"box center"), (x + edge, u"top center" if side == "above" else u"bottom center")]


def snap(value, targets, tolerance):
    """(x, label) of the nearest of targets [(x, label)] within tolerance of value, or (None, None)."""
    best = None
    for x, label in targets:
        if abs(x - value) <= tolerance and (best is None or abs(x - value) < abs(best[0] - value)):
            best = (x, label)
    return best if best is not None else (None, None)


def mark_center(recipe, index, ink_of, placement, metrics=None):
    """(placed parts, the center across of the recipe's mark index), as it would be built."""
    checked, notes = recipe.checked, list(recipe.notes)
    try:
        parts, _ = place(recipe, ink_of, placement, metrics)
    finally:
        recipe.checked, recipe.notes = checked, notes
    if parts is None:
        return None, None
    first, last = mark_ranges(recipe)[index]
    box = parts_box(parts[first:last], ink_of)
    return parts, ((box[0] + box[2]) / 2.0 if box else None)


def carried_adjust(source, index, target, at, ink_of, placement, metrics=None):
    """The hand's change of source's mark index, for target's mark at (the same mark: related_marks):
    its rise and scale as they are; across, a mark the hand centered on a center of its letter (its box's,
    or its top's) centered on the same center of the target's letter, else the mark's offset from its
    letter's center carried in font units (centered stays centered on a wider letter), each letter
    keeping its own shift where fonts set marks off center on it (over b's bowl, right of l's stem). A
    mark beside its letter, stacked on another, or an ogonek takes the change as it is."""
    change = list(source.adjust.get(index, [0.0, 0.0, 1.0, 1.0]))
    mark = source.marks[index]
    same_side = [m for m in source.marks if m.side == mark.side]
    if mark.side not in ("above", "below") or mark.root == "ogonek" or same_side.index(mark) or abs(change[0]) < CENTERED:
        return change
    parts, center = mark_center(source, index, ink_of, placement, metrics)
    base_ink = ink_of(source.base)
    if center is None or base_ink is None:
        return change
    letter = unicodedata.normalize("NFD", source.char)[0]
    case = case_of(source.char)
    centers = letter_centers(base_ink, parts[0][3], mark.side)
    kind = next((label for x, label in centers if abs(center - x) <= CENTERED), None)
    saved = target.adjust.pop(at, None)
    try:
        target_parts, target_center = mark_center(target, at, ink_of, placement, metrics)
    finally:
        if saved is not None:
            target.adjust[at] = saved
    target_ink = ink_of(target.base)
    if target_center is None or target_ink is None:
        return change
    target_letter = unicodedata.normalize("NFD", target.char)[0]
    target_centers = dict((label, x) for x, label in letter_centers(target_ink, target_parts[0][3], mark.side))
    edge_label = u"top center" if mark.side == "above" else u"bottom center"
    if kind is not None:  # centered: on the same center of the target's letter (one center: both are it)
        wanted = target_centers.get(kind if kind != u"center" else edge_label, target_centers.get(u"center"))
        if wanted is None:
            wanted = target_centers.get(u"center")
    else:
        edge = dict((label, x) for x, label in centers)
        source_edge = edge.get(edge_label, edge.get(u"center"))
        target_edge = target_centers.get(edge_label, target_centers.get(u"center"))
        shift = placement.letter_shift(letter, mark.root, mark.side, case) * base_ink.width
        target_shift = placement.letter_shift(target_letter, mark.root, mark.side, case) * target_ink.width
        wanted = target_edge + target_shift + (center - source_edge - shift)
    return [round(wanted - target_center, 2), change[1], change[2], change[3]]


# ---------------------------------------------------------------------------
# Mark anchors (scripts whose marks the font's mark features attach)
# ---------------------------------------------------------------------------

ANCHOR_MODEL_FILE = "anchor_model.json"
ANCHOR_BLOCK = "anchors"
ANCHOR_BEGIN, ANCHOR_END = u"# >>> FreeLab %s (made by FreeLab Glyph Compose)", u"# <<< FreeLab %s"
# The opening line blocks had when the tool was called Diacritics: such a block is FreeLab's too, replaced
# by the next write (fonts keep it until then)
OLD_ANCHOR_BEGINS = (u"# >>> FreeLab %s (made by FreeLab Diacritics)",)
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
MARK_FEATURES = {"mark": "Mark Positioning", "mkmk": "Mark to Mark Positioning",
                 "ccmp": "Glyph Composition/Decomposition", "pres": "Pre-base Substitutions"}
CODE_FEATURES = ("ccmp", "pres", "mark", "mkmk")  # the features the Mark anchors tab writes, in this order
DEFAULT_ANCHOR = {"base_gap": 0.0, "base_offset": 0.0, "mark_gap": 0.06, "mark_offset": 0.0, "mark_to_mark": 0.01}


def load_anchor_model(path=None):
    """The corpus's anchor placements (anchor_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), ANCHOR_MODEL_FILE)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class AnchorGlyph(object):
    stacks = False  # a base whose precomposed letters stack marks (composed_sides)
    elsewhere = False  # anchors to add in another master than the one planned (AnchorPage.run)

    """A base or a mark of a script, with the anchors to add ({name: (x, y)}) and those it has."""

    def __init__(self, name, code, role, ink, existing=None, parts=0):
        self.name, self.code, self.role, self.ink = name, code, role, ink  # ink: an Ink
        self.parts = parts  # a ligature's letters
        self.existing = dict(existing or {})
        self.anchors = {}  # name: (x, y), the ones to add
        self.adjust = {}  # name: [dx, dy], moved by hand
        self.side = None  # a mark's side: "top" or "bottom"
        # a mark's attaching point for its side ({side: (x, y)}), where its _top (or _bottom, _ogonek, ...)
        # is or would be: the preview hangs it there, a mark the font attaches by anchors of its own too
        self.hang = {}
        self.checked = True

    def placed(self):
        """{name: (x, y)} of every anchor it will have: its own and those to add, as moved by hand."""
        found = {}
        for name, (x, y) in list(self.existing.items()) + list(self.anchors.items()):
            dx, dy = self.adjust.get(name, (0, 0))
            found[name] = (round(x + dx), round(y + dy))
        return found

    def moved(self):
        """The names of the anchors it has that were moved by hand (to move when written)."""
        return sorted(name for name in self.existing if name not in self.anchors and name in self.adjust)

    def pending(self):
        """Whether writing it would change the font: anchors to add (here or in another master), or its own
        moved."""
        return bool(self.anchors) or bool(self.moved()) or self.elsewhere


MIN_ROW_FONTS = 3  # a script's anchor medians from fewer fonts than this give way to Latin's


def anchor_row(model, script, side):
    row = dict(DEFAULT_ANCHOR)
    anchors = model.get("anchors", {})
    found = anchors.get(u"%s %s" % (script, side))
    if not found or found.get("fonts", 0) < MIN_ROW_FONTS:
        found = anchors.get(u"latin %s" % side)
    row.update(found or {})
    return row


_ROOTS = []
COMPOSED_SCRIPTS = ("latin", "greek", "cyrillic")  # Unicode precomposes their letters with marks widely


def composing_roots():
    """The code points Unicode composes letters with marks on: the first of each canonical
    decomposition (the Basic Multilingual Plane's) whose rest are marks, all the way down (a for the
    letters with dieresis and macron, not a with dieresis), and the dotless i and j that take marks above."""
    if not _ROOTS:
        found = set([0x0131, 0x0237])
        for code in range(0x00C0, 0xFFFF):
            if 0xD800 <= code < 0xE000:
                continue
            ch = unichr_(code)
            decomposition = unicodedata.decomposition(ch)
            if not decomposition or decomposition.startswith(u"<"):
                continue
            parts = unicodedata.normalize("NFD", ch)
            if len(parts) > 1 and all(unicodedata.category(c).startswith("M") for c in parts[1:]):
                found.add(ord(parts[0]))
        _ROOTS.append(found)
    return _ROOTS[0]


def base_letters(script, model):
    """The code points of a script's letters that take marks, or None (any letter): those Unicode
    composes with marks, and those the corpus's fonts of the script attach marks to (save letters
    Unicode has precomposed: their marks are built in)."""
    roots = set(code for code in composing_roots() if anchor_script(code) == script)
    corpus = set()
    for text in model.get("bases", {}).get(script, ()):
        code = int(text, 16)
        if code <= 0xFFFF and unicodedata.normalize("NFD", unichr_(code)) == unichr_(code):
            corpus.add(code)
    if not corpus and script not in COMPOSED_SCRIPTS:
        return None  # a few compositions (Myanmar's) do not say which of its letters take marks
    found = roots | corpus
    return found or None


def mark_side_of(ink, x_height):
    """Where a mark goes, by its ink: above when its middle is at least halfway up the x-height."""
    return "top" if (ink.bottom + ink.top) / 2.0 >= 0.5 * x_height else "bottom"


# Marks that attach elsewhere than over or under the letter's middle, by code point, as most of the
# corpus's Hebrew fonts set them (27 of its 30 Hebrew families attach their points): the dagesh (and
# mapiq) inside the letter; the holam and the sin dot at its top left, the shin dot at shin's top right;
# of the cantillation marks (10 families have them), pashta and telisha qetana at the top left, yetiv
# and dehi at the bottom right.
MARK_CLASSES = {0x05BC: "center", 0x05B9: "topleft", 0x05BA: "topleft", 0x05C2: "topleft", 0x05C1: "topright",
                0x0599: "topleft", 0x05A9: "topleft", 0x059A: "bottomright", 0x05AD: "bottomright"}
SIDE_FAMILY = {"topleft": "top", "topright": "top", "bottomright": "bottom", "center": "center",
               "ogonek": "bottom", "horn": "top"}
# Latin's marks that attach at a letter's side, with anchors of their own (as most fonts name them): the
# ogonek at the bottom right, the horn at the top right
SIDE_MARKS = {0x0328: "ogonek", 0x031B: "horn"}
MARK_CLASSES.update(SIDE_MARKS)
_SIDES = {}


def composed_sides():
    """{base code point: (set of anchors its precomposed letters need, whether it stacks marks)} for the
    letters Unicode composes with marks: top for marks above, bottom for marks below, ogonek and horn
    for theirs; it stacks when one of its letters has two marks on one side (Vietnamese \u1ea5).
    B: top and bottom (\u1e02, \u1e04, \u1e06); a letter with none is no base."""
    if not _SIDES:
        for code in range(0x00C0, 0xFFFF):
            if 0xD800 <= code < 0xE000:
                continue
            decomposed = unicodedata.normalize("NFD", unichr_(code))
            if len(decomposed) < 2 or not all(unicodedata.combining(c) or ord(c) in SIDE_MARKS for c in decomposed[1:]):
                continue
            entry = _SIDES.setdefault(ord(decomposed[0]), [set(), False])
            counts = {}
            for c in decomposed[1:]:
                mark = ord(c)
                where = SIDE_MARKS.get(mark) or {"above": "top", "topright": "top", "below": "bottom"}.get(side_of(mark))
                if where is None:
                    continue
                entry[0].add(where)
                counts[where] = counts.get(where, 0) + 1
            if any(n > 1 for n in counts.values()):
                entry[1] = True
        for dotless in (0x0131, 0x0237):  # the dotless i and j take the marks above i and j take
            _SIDES[dotless] = [set(["top"]), False]
    return _SIDES


def side_point(side, ink, upm):
    """A base's ogonek (its ink's bottom right, on the baseline) or horn anchor (its ink's top right)."""
    if side == "ogonek":
        return ink.right, max(ink.bottom, 0)
    return ink.right, ink.top - 0.04 * upm


def base_group(g):
    """The section of the Bases a letter of a precomposed script is listed in, by the anchors it takes.
    Letters whose precomposed forms stack marks (Vietnamese's) have no section of their own: marks stack
    on each other by the marks' anchors, and such a letter takes the anchors any letter does (its
    preview shows a stack)."""
    sides = set(g.anchors) | set(g.existing)
    if sides & set(SIDE_MARKS.values()):
        return u"With side marks too (ogonek, horn)"
    if u"top" in sides and u"bottom" in sides:
        return u"Marks above and below"
    if u"top" in sides:
        return u"Marks above only"
    if u"bottom" in sides:
        return u"Marks below only"
    return u"Other letters"


BASE_GROUP_ORDER = (u"Marks above and below", u"Marks above only", u"Marks below only",
                    u"With side marks too (ogonek, horn)", u"Other letters")


def own_anchors(existing, role, classes):
    """The anchors of a glyph's own that the marks attach by, {name: (x, y)}: a mark's attaching anchors
    (_top), and the anchors named after a side a mark attaches to (classes: top, bottom, the corners, a
    font's own _above; a ligature's top_1). Any other anchor a glyph carries is not the marks' to use: it
    says nothing of where they go, so it is neither counted nor named in the glyph's row."""
    kept = {}
    for name, point in (existing or {}).items():
        if name.startswith(u"_"):
            used = role in ("mark", "reph")
        else:
            stem, _, part = name.rpartition(u"_")
            used = name in classes or (role == "ligature" and part.isdigit() and stem in classes)
        if used:
            kept[name] = point
    return kept
SIDE_BASES = {"topright": (0x05E9,)}  # a side only these letters (and their forms) take: the shin dot's, shin
# Where a mark of each side goes, as the anchor list says it
ANCHOR_SIDE_WORDS = {"top": u"above", "bottom": u"below", "topleft": u"above at the left",
                     "topright": u"above at the right", "bottomright": u"below at the right", "center": u"inside",
                     "ogonek": u"at the bottom right", "horn": u"at the top right"}


def anchor_side(code, ink, x_height):
    """Where a mark goes: its class (MARK_CLASSES), else above or below by its ink (top, bottom)."""
    return MARK_CLASSES.get(code) or mark_side_of(ink, x_height)


LETTER_HEIGHT_FROM_SCRIPT = ("latin",)  # per-letter placement across only: heights by the script's rule
# The marks whose landing on each letter the corpus's per-letter placements are (diacritics/train/shaped.py
# samples them), per script and side: a base's anchor is set so that this mark lands there, the others
# then sitting as their own anchors say (Thai's right-aligned)
DOUBLE_MARKS = frozenset(list(range(0x035C, 0x0363)) + [0x1DCD, 0x1DFC])  # combining marks over or under two letters
SAMPLE_MARKS = {"latin": {"top": 0x0301, "bottom": 0x0323}, "greek": {"top": 0x0301},
                "cyrillic": {"top": 0x0301, "bottom": 0x0323},
                "hebrew": {"top": 0x05BF, "bottom": 0x05B7, "center": 0x05BC, "topleft": 0x05B9, "topright": 0x05C1},
                "arabic": {"top": 0x064E, "bottom": 0x0650}, "devanagari": {"top": 0x0902, "bottom": 0x0941},
                "bengali": {"top": 0x0981, "bottom": 0x09C1}, "gujarati": {"top": 0x0A82, "bottom": 0x0AC1},
                "tamil": {"top": 0x0BCD}, "thai": {"top": 0x0E48, "bottom": 0x0E38},
                "lao": {"top": 0x0EC8, "bottom": 0x0EB8}, "myanmar": {"top": 0x1036, "bottom": 0x102F},
                "khmer": {"top": 0x17B7, "bottom": 0x17BB}}
# The marks the Mark anchors tab draws on a letter's anchors in Latin, Greek, and Cyrillic, the first the font
# has of each side: diacritics a reader knows (a circumflex above, an acute stacked on it where marks
# stack; a dot below; the ogonek; the horn)
REPRESENTATIVE_MARKS = {"top": (0x0302, 0x0301, 0x0300, 0x0308, 0x0304, 0x0303, 0x030C, 0x0306, 0x030A, 0x0307),
                        "bottom": (0x0323, 0x0331, 0x0326, 0x0325, 0x032D, 0x0324, 0x0330),
                        "ogonek": (0x0328,), "horn": (0x031B,)}


# A combining mark's twin on the other side (a comma below's is the turned comma above, as Latvian's ģ
# draws it): what the reference draws for a mark glyph whose ink sits on the other side than its code
# point's (Bellefair's uni0326.salt, a comma above, was drawn in the reference as U+0326, below: the
# owner's report of 2026-11-16)
OTHER_SIDE_TWINS = dict([(0x0326, 0x0312), (0x0323, 0x0307), (0x0331, 0x0304), (0x032D, 0x0302), (0x032E, 0x0306),
                         (0x0330, 0x0303), (0x0324, 0x0308), (0x0325, 0x030A), (0x032C, 0x030C), (0x0329, 0x030D),
                         (0x0332, 0x0305), (0x0316, 0x0300), (0x0317, 0x0301)])
OTHER_SIDE_TWINS.update(dict((above, below) for below, above in list(OTHER_SIDE_TWINS.items())))
DIACRITICAL_BLOCKS = ((0x0300, 0x036F), (0x1AB0, 0x1AFF), (0x1DC0, 0x1DFF), (0x20D0, 0x20FF), (0xFE20, 0xFE2F))


def reference_code(code, side):
    """The character the reference draws for a mark glyph of that code point whose ink is on side ("top",
    "bottom"; its anchors' side): its own, else, where a combining diacritic's glyph sits on the other side
    than Unicode's (an alternate form, uni0326.salt drawn above), its twin of that side (OTHER_SIDE_TWINS),
    else None (none drawn). Other scripts' marks keep theirs (Thai's below vowels are no Latin class)."""
    if not code or side not in ("top", "bottom") or not any(low <= code <= high for low, high in DIACRITICAL_BLOCKS):
        return code
    unicode_side = side_of(code)
    if (side == "top") == (unicode_side in ("above", "topright", "right")):
        return code
    twin = OTHER_SIDE_TWINS.get(code)
    return twin if twin is not None and side_of(twin) != unicode_side else None


def letter_row(model, script, side, code):
    """(share across, gap) where the corpus's fonts land a mark on this letter (shaped.py), or None; for
    the center (a dagesh), (share across, share up) of the letter's ink."""
    if not code:
        return None
    entry = model.get("letters", {}).get(u"%s %s" % (script, side), {}).get(u"%04X" % code)
    if not entry or len(entry) < 3 or entry[2] < MIN_ROW_FONTS:
        return None
    return entry[0], entry[1]


def side_row(model, script, side):
    """The median, over the script's letters, of where the corpus's fonts land a mark of this side (for a
    letter the corpus has too little of), or None."""
    rows = [entry for entry in model.get("letters", {}).get(u"%s %s" % (script, side), {}).values()
            if len(entry) >= 3 and entry[2] >= MIN_ROW_FONTS]
    if not rows:
        return None
    return median([entry[0] for entry in rows]), median([entry[1] for entry in rows])


# Scripts whose ra and virama before a consonant make a reph over it: (ra, virama, a consonant to show it on)
REPH_SCRIPTS = {"devanagari": (0x0930, 0x094D, 0x0915), "bengali": (0x09B0, 0x09CD, 0x0995),
                "gujarati": (0x0AB0, 0x0ACD, 0x0A95)}


def reph_row(model, script):
    """{"share", "gap", "fonts"}: where the corpus's fonts of a script land the reph, or None."""
    found = model.get("reph") or {}
    if "share" in found:  # (the first models: Devanagari's only)
        return found if script == "devanagari" else None
    return found.get(script)


def ligature_point(model, script, side, ink, part, parts, upm):
    """Where a ligature's part takes a mark (part 1 is read first: the right one, in Arabic): two-part
    ligatures as the corpus's set theirs, others split evenly."""
    learned = model.get("ligature", {}).get(side)
    if parts == 2 and learned and len(learned) == 2:
        share, gap = learned[part - 1]
    else:
        share, gap = 1.0 - (part - 0.5) / parts, anchor_row(model, script, side)["base_gap"]
    x = ink.left + share * ink.width
    return (x, ink.top + gap * upm) if side == "top" else (x, ink.bottom - gap * upm)


def base_point(model, script, side, code, ink, upm, widths):
    """(x, y) of a base's anchor of a side: where the corpus's fonts land a mark on this letter (the mark's
    ink there, so the anchor sits as far off it as the mark's own anchor sits off the mark's ink), else by
    the script's rule: over (under) the center of the ink's top (bottom) fifth; a corner's at the ink's
    left or right end; the center's in the middle of the ink, as the script's letters take it."""
    family = SIDE_FAMILY.get(side, side)
    learned = letter_row(model, script, side, code)
    if family == "center":
        learned = learned or side_row(model, script, side)
        share, up = learned if learned is not None else (0.5, 0.5)
        return ink.left + share * ink.width, ink.bottom + up * (ink.top - ink.bottom)
    row = anchor_row(model, script, family)
    if side != family:  # a corner (the holam's): the mark's own anchor is under (over) its ink's center
        learned = learned or side_row(model, script, side)
        share, gap = learned if learned is not None else (1.0 if side.endswith(u"right") else 0.0, None)
        lift = (gap - row["mark_gap"]) * upm if gap is not None else row["base_gap"] * upm
        x = ink.left + share * ink.width
        return (x, ink.top + lift) if family == "top" else (x, ink.bottom - lift)
    if learned is not None:  # the mark's ink lands there: its own anchor sits mark_offset and mark_gap off it
        share, gap = learned
        x = ink.left + share * ink.width + row["mark_offset"] * widths.get(side, 0.0)
        # (Latin's heights: its script's rule, which landed marks closer, by a leave-one-font-out test)
        lift = (gap - row["mark_gap"]) * upm if script not in LETTER_HEIGHT_FROM_SCRIPT else row["base_gap"] * upm
        return (x, ink.top + lift) if side == "top" else (x, ink.bottom - lift)
    if side == "top":
        return ink.top_center + row["base_offset"] * ink.width, ink.top + row["base_gap"] * upm
    return ink.bottom_center + row["base_offset"] * ink.width, ink.bottom - row["base_gap"] * upm


def plan_anchors(glyphs, model, script, upm, x_height):
    """AnchorGlyphs with their anchors to add: bases get top and bottom, each mark the anchor it
    attaches by (_top or _bottom) and the one the next mark attaches to (top or bottom), a ligature
    top_1, bottom_1, top_2, and so on (one pair per letter it joins), a reph _reph and every base a
    reph anchor. Marks of other classes (MARK_CLASSES: Hebrew's dagesh, center; its holam, topleft) take
    that anchor alone, and the bases one for it (shin alone a topright, for the shin dot). A mark with an
    attaching anchor (_x) of its own takes no other. glyphs: [(name,
    code, "base", "mark", "ligature" or "reph", Ink, {existing anchor: (x, y)}[, letters joined])].
    Anchors the glyph has already are kept as they are. A base's anchor sits where the corpus's fonts
    land a mark on that letter (shaped.py, all their means at once: a Thai mark beside po pla's
    ascender), else by its script's rule (base_point); a mark's under (over) its ink's center."""
    upm = float(upm)
    planned = []
    rows = [tuple(entry) + (0,) * (6 - len(entry)) for entry in glyphs]
    marks, sampled = {}, {}
    samples = SAMPLE_MARKS.get(script, {})
    for name, code, role, ink, existing, parts in rows:  # marks first: their sides and widths place the bases'
        if role == "mark" and ink is not None and ink.width > 0:
            side = anchor_side(code, ink, x_height)
            marks.setdefault(side, []).append(ink.width)
            if code == samples.get(side) and u"." not in name:  # the mark whose landing the letters' placements are
                sampled[side] = ink.width
    widths = dict((side, sampled.get(side, median(found))) for side, found in marks.items())
    special = sorted(side for side in marks if side in SIDE_FAMILY)  # the sides besides top and bottom the marks take
    has_reph = any(row[2] == "reph" for row in rows)
    reph = reph_row(model, script)
    # The sides marks attach to: the planned ones, and those of the font's own attaching anchors (_above)
    classes = set([u"top", u"bottom", u"reph"]) | set(SIDE_FAMILY) | set(
        anchor[1:] for row in rows if row[2] in ("mark", "reph") for anchor in (row[4] or {}) if anchor.startswith(u"_"))
    for name, code, role, ink, existing, parts in rows:
        if ink is None or ink.width <= 0:
            continue
        g = AnchorGlyph(name, code, role, ink, own_anchors(existing, role, classes), parts)
        if role == "base":
            composed = composed_sides().get(code) if script in COMPOSED_SCRIPTS and code else None
            if composed is not None:
                # top and bottom, as any letter: combining marks go on letters Unicode has no precomposed
                # form for (a dot below p or x, in transliterations), which is what they are for. The side
                # anchors only where its precomposed letters need them (a: ogonek; o and u: horn too).
                g.stacks = composed[1]
                sides = ["top", "bottom"]
                sides += [side for side in sorted(composed[0]) if side in SIDE_MARKS.values()]
            else:
                sides = ["top", "bottom"] + [s for s in special if s not in SIDE_MARKS.values()
                                             and (s not in SIDE_BASES or code in SIDE_BASES[s])]
            for side in sides:
                if side in SIDE_MARKS.values():
                    point = side_point(side, ink, upm)
                else:
                    point = base_point(model, script, side, code, ink, upm, widths)
                if side not in g.existing:
                    g.anchors[side] = (round(point[0]), round(point[1]))
            if has_reph and reph and "reph" not in g.existing:
                g.anchors[u"reph"] = (round(ink.left + reph["share"] * ink.width), round(ink.top + reph["gap"] * upm))
        elif role == "ligature":
            for part in range(1, max(parts, 2) + 1):
                for side in ("top", "bottom"):
                    anchor = u"%s_%d" % (side, part)
                    if anchor not in g.existing:
                        x, y = ligature_point(model, script, side, ink, part, max(parts, 2), upm)
                        g.anchors[anchor] = (round(x), round(y))
        elif role == "reph":
            g.side = u"reph"
            if u"_reph" not in g.existing:  # the reph's ink lands at the base's reph anchor, its bottom center there
                g.anchors[u"_reph"] = (round(ink.center), round(ink.bottom))
        else:
            side = g.side = anchor_side(code, ink, x_height)
            family = SIDE_FAMILY.get(side, side)
            points = []
            if family == "center":  # its ink's center meets the base's center anchor
                points.append((u"_" + side, (ink.center, (ink.bottom + ink.top) / 2.0)))
            elif side == "ogonek":  # its top right meets the letter's bottom right
                points.append((u"_ogonek", (ink.right, ink.top)))
            elif side == "horn":  # its bottom left meets the letter's top right
                points.append((u"_horn", (ink.left, ink.bottom)))
            elif side != family:  # at a letter's corner: centered on its ink; nothing stacks on it
                row = anchor_row(model, script, family)
                gap = row["mark_gap"] * upm
                points.append((u"_" + side, (ink.center, ink.bottom - gap if family == "top" else ink.top + gap)))
            else:
                row = anchor_row(model, script, side)
                x = ink.center + row["mark_offset"] * ink.width
                if side == "top":
                    points += [(u"_top", (x, ink.bottom - row["mark_gap"] * upm)),
                               (u"top", (x, ink.top + row["mark_to_mark"] * upm))]
                else:
                    points += [(u"_bottom", (x, ink.top + row["mark_gap"] * upm)),
                               (u"bottom", (x, ink.bottom - row["mark_to_mark"] * upm))]
            # A mark attached already by an anchor of its own (a horn's _topright, an ogonek's _bottom) takes no
            # other: in two mark classes, fontTools' compiler refuses it
            attached = any(name.startswith(u"_") for name in g.existing)
            g.hang = dict((anchor[1:], (round(point[0]), round(point[1]))) for anchor, point in points
                          if anchor.startswith(u"_"))
            g.hang.update((name[1:], point) for name, point in g.existing.items() if name[1:] in g.hang)
            for anchor, point in points:
                if anchor not in g.existing and not (attached and anchor.startswith(u"_")):
                    g.anchors[anchor] = (round(point[0]), round(point[1]))
        if g.anchors:
            planned.append(g)
        else:
            g.checked = False
            planned.append(g)
    return planned


# Thai: the corpus's convention (25 of its 27 Thai families): a tone mark after a mark above takes its
# smaller form; yo ying, tho than, do chada, to patak, ru, and lu their forms without the part a vowel
# below would meet; lo chula its shorter form under a mark above. (Their narrower marks for po pla's
# ascender are left out: anchors set each mark beside it already.)
THAI_ABOVE = (0x0E31, 0x0E34, 0x0E35, 0x0E36, 0x0E37, 0x0E47, 0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C, 0x0E4D, 0x0E4E)
THAI_BELOW = (0x0E38, 0x0E39, 0x0E3A)
THAI_TONES = (0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C)
THAI_SHORTENED = ((0x0E0D, ("less", "short")), (0x0E10, ("less", "short")), (0x0E0E, ("short", "less")),
                  (0x0E0F, ("short", "less")), (0x0E24, ("short",)), (0x0E26, ("short",)))
THAI_LO_CHULA = 0x0E2C
I_MATRA = 0x093F
DEVANAGARI_CONSONANTS = tuple(range(0x0915, 0x093A))
# The pre-base i-matra and the consonants it goes before, per script: several fonts draw it in lengths
# whose hook reaches into the consonant (Devanagari's, 30 fonts; Gujarati's, 11 of the corpus's 12
# Gujarati families; Bengali's, 6 of 11, for its longer consonants)
I_MATRAS = {"devanagari": (I_MATRA, DEVANAGARI_CONSONANTS),
            "bengali": (0x09BF, tuple(range(0x0995, 0x09BA)) + (0x09DC, 0x09DD, 0x09DF)),
            "gujarati": (0x0ABF, tuple(range(0x0A95, 0x0ABA)))}
NOMINAL_SHARE = 0.5  # a consonant most of the corpus's fonts keep their nominal i-matra before gets no rule
LIGATURE_FORMS = (u"<isolated>", u"<final>", u"<initial>", u"<medial>")
# Glyphs' names for the letters whose forms the rules look for (GlyphData.xml, MIT License: see
# GlyphData_LICENSE): a form is found by its letter's font name, this one (or with another common tag
# of its script: iMatra-gujr for iMatra-gujarati), or uniXXXX, case and hyphens aside (yoYing-thai.less,
# yoYingthai.less, uni0E0D.less)
NICE_NAMES = {0x0E0D: u"yoYing-thai", 0x0E0E: u"doChada-thai", 0x0E0F: u"toPatak-thai", 0x0E10: u"thoThan-thai",
              0x0E24: u"ru-thai", 0x0E26: u"lu-thai", 0x0E2C: u"loChula-thai", 0x0E48: u"maiEk-thai",
              0x0E49: u"maiTho-thai", 0x0E4A: u"maiTri-thai", 0x0E4B: u"maiChattawa-thai", 0x0E4C: u"thanthakhat-thai",
              0x093F: u"iMatra-deva", 0x09BF: u"iMatra-beng", 0x0ABF: u"iMatra-gujarati"}
# The tags fonts name a script's glyphs with (Glyphs' first: -hb, -deva, -beng, -gujarati, -tamil)
SCRIPT_TAGS = {"hebrew": (u"hb", u"hebr", u"hebrew"), "devanagari": (u"deva", u"dv", u"dev", u"devanagari"),
               "bengali": (u"beng", u"bn", u"bng", u"bengali", u"bangla"),
               "gujarati": (u"gujarati", u"gujr", u"gj", u"guj"), "tamil": (u"tamil", u"taml", u"tml"),
               "thai": (u"thai",)}


def _plain(name):
    return name.lower().replace(u"-", u"")


def nice_names(code):
    """Glyphs' name for a code point (NICE_NAMES, else glyph_names.json), and the same with each other
    common tag of its script (iMatra-gujarati, iMatra-gujr, iMatra-gj, iMatra-guj)."""
    nice = NICE_NAMES.get(code) or glyph_names().get(code)
    if not nice:
        return []
    found = [nice]
    stem, dash, tag = nice.rpartition(u"-")
    if dash:
        for tags in SCRIPT_TAGS.values():
            if tag in tags:
                found += [u"%s-%s" % (stem, other) for other in tags if other != tag]
    return found


def forms_of(names, base, code):
    """{suffix: glyph name} of the font's forms of a letter: glyphs named after it, a period, and a suffix."""
    stems = set(_plain(stem) for stem in [base, u"uni%04X" % code] + nice_names(code) if stem)
    found = {}
    for name in sorted(names):
        stem, dot, suffix = name.partition(u".")
        if dot and suffix and _plain(stem) in stems:
            found.setdefault(suffix, name)
    return found


class Rule(object):
    """A substitution the Mark anchors tab writes: its feature, the form it puts in (name), its line of
    code, when it applies (text), and a sample to draw in the reference font."""
    role = "rule"

    def __init__(self, feature, name, line, text, sample=u""):
        self.feature, self.name, self.line, self.text, self.sample = feature, name, line, text, sample
        self.code, self.parts, self.checked, self.side, self.ink = 0, 0, True, None, None
        self.anchors, self.existing, self.adjust = {}, {}, {}

    def placed(self):
        return {}

    def pending(self):
        """No anchors to write (its line is written with the code, when checked)."""
        return False


def thai_rules(names_by_code, names):
    """Rules for the Thai forms the font has (by its glyphs' names: uni0E48.small, maiek-thai.small)."""
    def form(code, suffixes):
        base = names_by_code.get(code)
        forms = forms_of(names, base, code) if base else {}
        for suffix in suffixes:
            if suffix in forms:
                return forms[suffix]
        return None
    found = []
    below = [names_by_code[c] for c in THAI_BELOW if c in names_by_code]
    above = [names_by_code[c] for c in THAI_ABOVE if c in names_by_code]
    if below:
        for code, suffixes in THAI_SHORTENED:
            short = form(code, suffixes)
            if short:
                found.append(Rule("ccmp", short, u"sub %s' [%s] by %s;" % (names_by_code[code], u" ".join(below), short),
                                  u"before a vowel below", unichr_(code) + unichr_(THAI_BELOW[0])))
    if above:
        for code in THAI_TONES:
            small = form(code, ("small",))
            if small:
                found.append(Rule("ccmp", small, u"sub [%s] %s' by %s;" % (u" ".join(above), names_by_code[code], small),
                                  u"after a mark above", u"\u0E01\u0E34" + unichr_(code)))
        short = form(THAI_LO_CHULA, ("short",))
        if short:
            found.append(Rule("ccmp", short, u"sub %s' [%s] by %s;" % (names_by_code[THAI_LO_CHULA], u" ".join(above), short),
                              u"under a mark above", unichr_(THAI_LO_CHULA) + u"\u0E48"))
    return found


def i_matra_variants(names, nominal, code):
    """The font's other i-matras: glyphs named after the nominal one (uni093F.01, iMatra-deva.a03, gjmI.alt02),
    or its name with other digits (MatraI3.gj for MatraI.gj, ivowelsign2gujr for ivowelsigngujr; not for a
    uniXXXX name, whose digits are its code point); none joined with another glyph (_)."""
    import re
    found = set(forms_of(names, nominal, code).values())
    if not re.match(u"^uni[0-9A-Fa-f]{4}", nominal):
        key = re.sub(u"[0-9]+", u"", nominal.lower())
        found.update(n for n in names if n != nominal and re.sub(u"[0-9]+", u"", n.lower()) == key)
    return sorted(n for n in found if u"_" not in n and n != nominal)


def i_matra_rules(names_by_code, names, reach_of, advance_of, model, script="devanagari"):
    """Rules picking, before each consonant, the i-matra whose hook reaches into it as far as the
    corpus's fonts reach into that consonant (a share of its advance), among the font's i-matras
    (i_matra_variants); none before a consonant most of those fonts keep their nominal i-matra before
    (Bengali's shorter consonants). reach_of(name): how far a glyph's ink reaches past its advance;
    advance_of(name): its advance; both None for a glyph not drawn."""
    matra, consonants = I_MATRAS.get(script, (None, ()))
    nominal = names_by_code.get(matra) if matra else None
    if not nominal:
        return []
    encoded = set(names_by_code.values())
    candidates = [nominal] + [n for n in i_matra_variants(names, nominal, matra) if n not in encoded]
    if len(candidates) < 2:
        return []
    reaches = dict((n, reach_of(n)) for n in candidates)
    reaches = dict((n, r) for n, r in reaches.items() if r is not None)
    if nominal not in reaches or len(reaches) < 2:
        return []
    groups = {}
    for code in consonants:
        consonant, learned = names_by_code.get(code), model.get("i_matra", {}).get(u"%04X" % code)
        advance = advance_of(consonant) if consonant else None
        if not consonant or not learned or not advance or (len(learned) > 2 and learned[2] > NOMINAL_SHARE):
            continue
        target = learned[0] * advance
        best = min(sorted(reaches), key=lambda n: abs(reaches[n] - target))
        if best != nominal:
            groups.setdefault(best, []).append((code, consonant))
    found = []
    for variant in sorted(groups):
        members = groups[variant]
        found.append(Rule("pres", variant, u"sub %s' [%s] by %s;" % (nominal, u" ".join(n for _, n in members), variant),
                          u"before %s" % u" ".join(unichr_(c) for c, _ in members),
                          unichr_(members[0][0]) + unichr_(matra)))
    return found


def ligature_parts(name, code, arabic_names):
    """How many letters an Arabic ligature glyph joins (0 for none): by its Unicode decomposition
    (lam with alef, U+FEFB, joins 2), its uniXXXXYYYY name, or its name's parts (lam_alef-ar: lam-ar and
    alef-ar, among the font's Arabic letters)."""
    if code:
        decomposition = unicodedata.decomposition(unichr_(code))
        if not decomposition.startswith(LIGATURE_FORMS):
            return 0
        letters = [p for p in decomposition.split()[1:]
                   if unicodedata.category(unichr_(int(p, 16))).startswith(u"L")]
        return len(letters) if len(letters) >= 2 else 0
    stem = name.split(u".")[0]
    if stem.startswith(u"uni") and len(stem) >= 11 and (len(stem) - 3) % 4 == 0:
        try:
            codes = [int(stem[i:i + 4], 16) for i in range(3, len(stem), 4)]
        except ValueError:
            codes = []
        if codes and all(anchor_script(c) == "arabic" and unicodedata.category(unichr_(c)).startswith(u"L") for c in codes):
            return len(codes)
        return 0
    if u"_" not in stem:
        return 0
    parts = stem.split(u"_")
    suffix = u""
    for mark in (u"-ar", u"-arab"):
        if parts[-1].endswith(mark):
            suffix = mark
    named = [part if (not suffix or part.endswith(suffix)) else part + suffix for part in parts]
    return len(named) if len(named) >= 2 and all(part in arabic_names for part in named) else 0


def name_script(name):
    """The reph script a glyph's name names, by its tag (Reph.bn, gjReph, rephdeva, reph-gujarati) or its
    code points (uni09B009CD), or None."""
    import re
    lowered = name.lower()
    codes = re.findall(u"(?:uni|u)([0-9a-f]{4})", lowered)
    for code in codes:
        script = anchor_script(int(code, 16))
        if script:
            return script
    words = [w for w in re.split(u"[._-]", lowered) if w]
    for script, tags in sorted(SCRIPT_TAGS.items()):
        for word in words:
            core = word.replace(u"reph", u"") if u"reph" in word else word
            if core in tags:
                return script
    return None


def is_reph(name, script=None):
    """A reph's glyph (rephdeva, Reph.dv, dvReph, uni0930094D.rphf, Reph.bn, gjReph, reph-gujarati, and ra and
    virama by their code points, uni09B009CD), not one joined with a matra, a vowel sign, or a bindu
    (bSignIiReph, ivowelsignrephgujr, gjmII_Reph), nor Marathi's eyelash ra; of the given script, when given, unless its name names another."""
    import re
    lowered = name.lower()
    named = name_script(name)
    if script is not None and named is not None and named != script:
        return False
    if lowered.endswith(u".rphf"):
        return True
    stem = lowered.split(u".")[0]
    for ra, virama, _ in REPH_SCRIPTS.values():
        if stem == u"uni%04x%04x" % (ra, virama):
            return True
    if u"reph" not in stem or any(w in lowered for w in (u"matra", u"anusvara", u"bindu", u"candra", u"eyelash", u"sign",
                                                         u"vowel", u"mark")):
        return False
    tags = set(tag for tags in SCRIPT_TAGS.values() for tag in tags)
    # joined with something else (gjmII_Reph: the ii-matra and the reph), not a script tag (bn_reph) or an alternate's
    return all(u"reph" in part or part.split(u"-")[0] in tags or re.match(u"^alt[0-9]*$", part)
               for part in stem.split(u"_"))


def mark_code(glyphs):
    """{"mark": [lines], "mkmk": [lines]} attaching the marks to the bases and to each other, from every
    anchor the glyphs will have (only checked glyphs, and glyphs with anchors of their own)."""
    marks = [g for g in glyphs if g.role in ("mark", "reph") and (g.checked or g.existing)]
    bases = [g for g in glyphs if g.role == "base" and (g.checked or g.existing)]
    ligatures = [g for g in glyphs if g.role == "ligature" and (g.checked or g.existing)]
    classes = {}
    lines = {"mark": [], "mkmk": []}
    for g in sorted(marks, key=lambda g: g.name):
        for name, (x, y) in sorted(g.placed().items()):
            if name.startswith(u"_"):
                side = name[1:]
                classes.setdefault(side, []).append(g.name)
                lines["mark"].append(u"markClass %s <anchor %d %d> @MC_%s;" % (g.name, x, y, side))
    for g in sorted(bases, key=lambda g: g.name):
        placed = g.placed()
        attach = [u"<anchor %d %d> mark @MC_%s" % (placed[side][0], placed[side][1], side)
                  for side in sorted(classes) if side in placed]
        if attach:
            lines["mark"].append(u"pos base %s %s;" % (g.name, u" ".join(attach)))
    for g in sorted(ligatures, key=lambda g: g.name):
        placed = g.placed()
        components = []
        for part in range(1, max(g.parts, 2) + 1):
            attach = [u"<anchor %d %d> mark @MC_%s" % (placed[u"%s_%d" % (side, part)][0], placed[u"%s_%d" % (side, part)][1], side)
                      for side in sorted(classes) if side != u"reph" and u"%s_%d" % (side, part) in placed]
            components.append(u" ".join(attach) if attach else u"<anchor NULL>")
        if any(c != u"<anchor NULL>" for c in components):
            lines["mark"].append(u"pos ligature %s %s;" % (g.name, u" ligComponent ".join(components)))
    for g in sorted(marks, key=lambda g: g.name):
        if g.role == "reph":
            continue  # nothing attaches to the reph
        placed = g.placed()
        attach = [u"<anchor %d %d> mark @MC_%s" % (placed[side][0], placed[side][1], side)
                  for side in sorted(classes) if side in placed]
        if attach:
            lines["mkmk"].append(u"pos mark %s %s;" % (g.name, u" ".join(attach)))
    return lines


def freelab_feature(tag, old, lines, block=ANCHOR_BLOCK, titles=MARK_FEATURES):
    """A feature's code with FreeLab's block (lines) before its closing line: an older FreeLab block
    taken out, the rest kept, FontLab's automatic block handed back ("#/> feature")."""
    import re
    begin, end = ANCHOR_BEGIN % block, ANCHOR_END % block
    begins = [begin] + [old_begin % block for old_begin in OLD_ANCHOR_BEGINS]
    kept, inside = [], False
    for line in (old or u"").splitlines():
        stripped = line.strip()
        if stripped in begins:
            inside = True
            continue
        if stripped == end:
            inside = False
            continue
        if inside:
            continue
        if stripped.startswith(FONTLAB_AUTO):
            line = line.replace(FONTLAB_AUTO, FONTLAB_HANDED, 1)
        kept.append(line)
    closing = None
    for index in range(len(kept) - 1, -1, -1):
        if re.match(r"^\s*}\s*%s\s*;" % re.escape(tag), kept[index]):
            closing = index
            break
    if closing is None:
        kept = [u"feature %s {" % tag, u"# %s" % titles.get(tag, tag), u""]
        closing = len(kept)
        kept.append(u"} %s;" % tag)
    body = [begin] + [u"  %s" % line for line in lines] + [end] if lines else []
    return u"\n".join(kept[:closing] + body + kept[closing:]) + u"\n"


def mark_texts(glyphs, old_texts):
    """{tag: new code} for mark and mkmk, and the substitutions' features (ccmp, pres) (a feature with
    nothing of FreeLab's and nothing to add is left out)."""
    lines = mark_code(glyphs)
    for rule in glyphs:
        if rule.role == "rule":
            lines.setdefault(rule.feature, [])
            if rule.checked:
                lines[rule.feature].append(rule.line)
    new = {}
    for tag in CODE_FEATURES:
        old = old_texts.get(tag)
        if lines.get(tag) or any((opening % ANCHOR_BLOCK) in (old or u"")
                                 for opening in (ANCHOR_BEGIN,) + OLD_ANCHOR_BEGINS):
            new[tag] = freelab_feature(tag, old, lines.get(tag, []))
    return new


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
# Font Check, asked for its bundled font, its reading of the vertical metrics, and its high-value list
FONT_CHECK_FILE, FONT_CHECK_MODULE = "freelab_font_check.py", "freelab_font_check"
ICON_SIZE = 40  # pixels high, each row's picture
PREVIEW_SIZE = 150  # pixels per em, the selected glyph's picture


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: its helpers (outlines, Glyph windows, dialogs)."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "layer_path") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(AUTO_KERNING_MODULE)
            module.__file__ = path
            sys.modules[AUTO_KERNING_MODULE] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, AUTO_KERNING_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(AUTO_KERNING_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[AUTO_KERNING_MODULE] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(AUTO_KERNING_MODULE, None)
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def counted(number, one, many=None):
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


class FontLabInk(object):
    """The ink of a master's glyphs (components drawn), measured once each."""

    def __init__(self, ak, package, master, virtual=None):
        self.ak, self.package, self.master = ak, package, master
        self.found, self.paths = {}, {}
        # {name: (glyph, contour)}: a glyph a build will make (a dotless i), not in the font yet, drawn as that
        # glyph without that contour (numbered_contours' count), so that its rows show it before it is made
        self.virtual = dict(virtual or {})

    def path(self, name):
        if name not in self.paths:
            glyph, dot = self.package.findName(name), None
            if (glyph is None or glyph.isNull) and name in self.virtual:
                source, dot = self.virtual[name]
                glyph = self.package.findName(source)
            layer = glyph.getLayerByName(self.master) if glyph is not None and not glyph.isNull else None
            drawn = layer if dot is None or layer is None else WithoutContour(layer, dot)
            self.paths[name] = (self.ak.layer_path(drawn), layer.advanceWidth) if layer is not None else (None, 0)
        return self.paths[name]

    def __call__(self, name):
        if name not in self.found:
            QtCore, QtGui = _qt()
            path, advance = self.path(name)
            if path is None or path.isEmpty():
                self.found[name] = None
            else:
                box = path.boundingRect()  # font units, y up: top() is the ink's lowest y
                left, bottom, right, top = box.left(), box.top(), box.right(), box.bottom()
                band = (top - bottom) * BAND_SHARE

                def part(y0, y1):
                    piece = path.intersected(_rect(QtCore, left - 1, y0, right - left + 2, y1 - y0)).boundingRect()
                    return piece if piece.width() > 0 else None

                upper, lower = part(top - band, top + 1), part(bottom - 1, bottom + band)
                self.found[name] = Ink(left, bottom, right, top,
                                       upper.center().x() if upper else None, lower.center().x() if lower else None,
                                       lower.right() if lower else None, advance, upper.right() if upper else None)
        return self.found[name]


def _rect(QtCore, x, y, w, h):
    QtGui = _qt()[1]
    path = QtGui.QPainterPath()
    path.addRect(QtCore.QRectF(x, y, w, h))
    return path


def is_empty(glyph):
    """True for a glyph with no layer, or none with shapes (an earlier FreeLab build left 257 such)."""
    try:
        return not any(layer.shapes for layer in glyph.layers)
    except Exception:
        return False


UNWRAP_DEPTH = 4  # components inside components followed this deep
TOUCH_SHARE = 0.012  # of the em: a mark placed from another letter this close to its letter or another mark is named


def touch_units(upm):
    """TOUCH_SHARE of this em in whole units, as the log names it (1,000 when the em is unknown): the log
    said 12 units whatever the font's em, while the test measures TOUCH_SHARE of the font's own."""
    try:
        upm = float(upm)
    except (TypeError, ValueError):
        upm = 1000.0
    if not upm > 0:
        upm = 1000.0
    return int(round(TOUCH_SHARE * upm))


# The marks drawn joined to their letter: touching it is how they should sit, and standing clear of it is
# the fault (the vertical caron, lined up with its own kind too, stands beside its letter like any mark)
TOUCHING_KINDS = ("ogonek", "cedilla", "horn")
APART = u"does not touch its letter"  # in a note: a joined mark standing clear of its letter


def touches_letter(mark):
    """Whether a mark is one drawn joined to its letter (an ogonek, a true cedilla, a horn)."""
    return attached_kind(mark) in TOUCHING_KINDS


def touch_note(recipe, measures, gap):
    """A note for the first of a recipe's marks that sits wrong, or u"": measures has, for each mark,
    whether it (overlaps its letter, comes within gap of it, overlaps another mark, comes within gap of
    one). A mark above or below must stand clear of its letter; one that joins it (TOUCHING_KINDS) must
    touch it, so the two are judged the opposite way. Either kind must stand clear of the other marks."""
    for mark, (on_letter, by_letter, on_mark, by_mark) in zip(recipe.marks, measures):
        label = mark.label()
        if touches_letter(mark):
            if not on_letter:
                return u"%s %s (%s joins it)" % (label, APART, with_article(attached_kind(mark)))
            if on_mark:
                return u"%s overlaps another mark" % label
            if by_mark:
                return u"%s comes within %s of another mark" % (label, counted(int(round(gap)), u"unit"))
            continue
        if on_letter or on_mark:
            return u"%s overlaps its letter or another mark" % label
        if by_letter or by_mark:
            return u"%s comes within %s of its letter or another mark" % (label, counted(int(round(gap)), u"unit"))
    return u""


def unwrapped(package, master, name, sx, sy, dx, dy):
    """A part scaled or flipped, (name, sx, sy, dx, dy), with a glyph that is one component only (an
    asciicircum that is a circumflex component) replaced by the glyph it points to, the transforms
    combined: FontLab 7 refused a whole layer (setGlyphComponents made none) whose component was
    scaled and flipped and pointed to such a glyph. Parts not scaled, and glyphs of their own, as given."""
    if sx == 1.0 and sy == 1.0:
        return name, sx, sy, dx, dy
    for _ in range(UNWRAP_DEPTH):
        try:
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            shapes = list(layer.shapes) if layer is not None else []
            if len(shapes) != 1 or not shapes[0].isComponent:
                break
            inner = shapes[0].transform
            if abs(inner.m12()) > 1e-6 or abs(inner.m21()) > 1e-6:
                break  # rotated or slanted inside: kept whole
            inner_name = shapes[0].shapeData.componentGlyph
            if not inner_name:
                break
            # outer (sx, sy, dx, dy) after inner (m11, m22, idx, idy): x -> sx * (m11 * x + idx) + dx
            name, dx, dy = inner_name, sx * inner.dx() + dx, sy * inner.dy() + dy
            sx, sy = sx * inner.m11(), sy * inner.m22()
        except Exception:
            break
    return name, sx, sy, dx, dy


# -- mirrored components set right (FontLab) -------------------------------------------------------------
# A component cannot be reversed where it stands: its contours are its glyph's. So the glyph it points to
# is mirrored into a glyph of its own, its contours reversed (corrected_glyph), and the component points
# there with what is left of its transform, which mirrors nothing (without_mirror). The letter stays a
# glyph of components and draws what it drew; the corrected glyph is made once and used by every letter
# that needs it. (Decomposing the mark into each letter would also fill the hole, but would leave as many
# copies to keep alike as there are letters, and no composites.)
# Used of FontLab, proven live (see the notes in .local): flGlyph, addGlyph, deleteGlyph, getLayerByName,
# layer.shapes, addShape, removeAllShapes, setGlyphComponents, a shape's clone, contours, and transform,
# flContour.clockwise, reverse(), and nodes() with each node's x and y read. Not proven: flLayer's
# applyTransform and writing a node's x and y, the two ways tried to mirror outlines. Whatever they do is
# measured afterward (every node against the mirror of the source's, each contour's direction against the
# source's), and a glyph that does not measure right is taken out again and said so: nothing is trusted
# to have worked.

class MirrorError(Exception):
    """Why a mirrored component could not be set right (said in the log). written: whether the glyph's
    shapes were taken out and put back meanwhile."""
    written = False


def layer_points(layer):
    """[(x, y)] of every node of a layer as drawn (through its shape's transform), or None where FontLab
    does not give them: what tells whether outlines were mirrored. Their box cannot: a mirror about the
    middle of the ink leaves the box where it was."""
    found = []
    try:
        for shape in layer.shapes:
            m11, m12, m21, m22, dx, dy = transform_values(shape.transform)
            for contour in shape.contours:
                if contour is None:  # (FontLab lists an empty contour as None)
                    continue
                for node in contour.nodes():
                    x, y = float(node.x), float(node.y)
                    found.append((m11 * x + m21 * y + dx, m12 * x + m22 * y + dy))
    except Exception:
        return None
    return found


def mirrored_points(points, mirror):
    sx, sy, tx, ty = mirror
    return [(sx * x + tx, sy * y + ty) for x, y in points]


def same_points(points, others, slack=0.51):
    """Whether two lists of points hold the same points, in any order, each within slack; two that are
    not known (None) are taken to: the caller measures something else too."""
    if points is None or others is None:
        return points is None and others is None
    if len(points) != len(others):
        return False
    # Each point matched with one of the others within slack, not paired by sorting both lists: FontLab rounds
    # coordinates to whole units, which reorders points whose x differ by under a unit (458.3 and 458.45 both
    # 458, then sorted by y), and a sorted pairing set points 800 units apart (the live pass of 2026-11-16)
    buckets = {}
    for at, (x, y) in enumerate(others):
        buckets.setdefault((int(math.floor(x)), int(math.floor(y))), []).append(at)
    used = set()
    for x, y in points:
        found = None
        for bx in (int(math.floor(x)) - 1, int(math.floor(x)), int(math.floor(x)) + 1):
            for by in (int(math.floor(y)) - 1, int(math.floor(y)), int(math.floor(y)) + 1):
                for at in buckets.get((bx, by), ()):
                    if at not in used and abs(others[at][0] - x) <= slack and abs(others[at][1] - y) <= slack:
                        found = at
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is None:
            return False
        used.add(found)
    return True


def same_points_in_order(points, others, slack=0.51):
    """Whether two lists of points are the same, point by point in order (node by node, contour by contour),
    each within slack (FontLab's whole-unit rounding); None as same_points takes it."""
    if points is None or others is None:
        return points is None and others is None
    return len(points) == len(others) and all(abs(a[0] - b[0]) <= slack and abs(a[1] - b[1]) <= slack
                                              for a, b in zip(points, others))


def font_glyph(package, name):
    """The font's glyph of a name, or None."""
    glyph = package.findName(name) if name else None
    if glyph is None or getattr(glyph, "isNull", False):
        return None
    return glyph


def transform_values(transform):
    """(m11, m12, m21, m22, dx, dy) of a QTransform."""
    return (transform.m11(), transform.m12(), transform.m21(), transform.m22(), transform.dx(), transform.dy())


def is_mirror(values):
    """Whether a transform's (m11, m12, m21, m22, ...) mirror (reverses_direction)."""
    return reverses_direction(values[0], values[3], values[2], values[1])


def shape_is_component(shape):
    try:
        return bool(shape.isComponent)
    except Exception:
        return False


def shape_copy(shape):
    return shape.cloneTopLevel() if hasattr(shape, "cloneTopLevel") else shape.clone()


def layer_box(ak, layer):
    """(left, bottom, right, top) of a layer's ink, or None."""
    path = ak.layer_path(layer) if layer is not None else None
    if path is None or path.isEmpty():
        return None
    box = path.boundingRect()  # font units, y up: top() is the ink's lowest y
    return box.left(), box.top(), box.right(), box.bottom()


def same_box(box, other, slack=1.0):
    return box is not None and other is not None and all(abs(a - b) <= slack for a, b in zip(box, other))


def drawn_clockwise(shape, contour):
    """Whether a contour runs clockwise as it is drawn: as it is kept, turned over where its shape's own
    transform mirrors."""
    return bool(contour.clockwise) != is_mirror(transform_values(shape.transform))


def source_mirror(ak, package, master, source, axis):
    """The mirror (mirror_of) a source glyph's corrected glyph is made by in a master, from the source's
    advance width and ink there; None where it is not drawn."""
    glyph = font_glyph(package, source)
    layer = glyph.getLayerByName(master) if glyph is not None else None
    box = layer_box(ak, layer)
    if box is None:
        return None
    return mirror_of(axis, layer.advanceWidth, box[1], box[3])


def is_corrected(ak, package, masters, source, name, axis):
    """Whether the font's glyph of that name is source's corrected glyph: outlines of its own, their nodes
    the mirror of the source's, in every master the source is drawn in."""
    glyph = font_glyph(package, name)
    if glyph is None:
        return False
    drawn = 0
    for master in masters:
        mirror = source_mirror(ak, package, master, source, axis)
        if mirror is None:
            continue
        layer = glyph.getLayerByName(master)
        if layer is None or any(shape_is_component(shape) for shape in layer.shapes):
            return False
        points = layer_points(font_glyph(package, source).getLayerByName(master))
        if points is None or not same_points(layer_points(layer), mirrored_points(points, mirror)):
            return False
        drawn += 1
    return drawn > 0


def mirror_outlines(layer, mirror, before, wanted):
    """A new layer's outlines mirrored where they stand, by whichever way FontLab takes: the layer's
    applyTransform, else its nodes moved one by one. before and wanted are its nodes (layer_points) as
    they are and as the mirror puts them: read back after each way, MirrorError when neither did it. (A
    shape given a mirroring transform would draw the same, but a component of such a glyph is one more
    thing FontLab might take either way: the outlines themselves are mirrored, or nothing is.)"""
    QtCore, QtGui = _qt()
    sx, sy, tx, ty = mirror
    if before is None:
        raise MirrorError(u"FontLab did not give its nodes")
    try:
        layer.applyTransform(QtGui.QTransform(sx, 0.0, 0.0, sy, tx, ty))
    except Exception:
        pass
    now = layer_points(layer)
    if same_points(now, wanted):
        return
    plain = all(max(abs(a - b) for a, b in zip(transform_values(shape.transform), (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))) < 1e-6
                for shape in layer.shapes)
    if same_points(now, before) and plain:  # nothing moved: each node, then (its shapes place nothing)
        try:
            for shape in layer.shapes:
                for contour in shape.contours:
                    for node in (contour.nodes() if contour is not None else ()):
                        x, y = sx * float(node.x) + tx, sy * float(node.y) + ty
                        # through its position where it has one: FontLab keeps a node's x and y set from
                        # a script, but the shape's outline follows only its position (seen live, 2026-11-13)
                        if hasattr(node, "position"):
                            node.position = QtCore.QPointF(x, y)
                        else:
                            node.x, node.y = x, y
        except Exception:
            pass
        if same_points(layer_points(layer), wanted):
            return
    raise MirrorError(u"FontLab did not mirror its outlines")


HELD_GLYPHS = "_freelab_made_glyphs"  # on sys: {font's id: [every flGlyph Python made for it]}


def new_glyph(fontlab, package, name):
    """A new flGlyph of that name, held for the rest of the session (sys.HELD_GLYPHS, per font): two
    FontLab crashes on closing a font (2026-11-16) found a glyph gone from the font's list of glyph
    objects, and one suspect is PythonQt deleting the Python-made flGlyph once nothing held it while
    FontLab kept it. Held until the cause is known; the font is added to by the caller (addGlyph)."""
    new = fontlab.flGlyph()
    new.name = name
    try:
        key = package.fgPackage.id
    except Exception:
        key = None
    held = getattr(sys, HELD_GLYPHS, None)
    if held is None:
        held = {}
        setattr(sys, HELD_GLYPHS, held)
    held.setdefault(key, []).append(new)
    return new


def make_corrected(fontlab, ak, package, masters, source, axis, name):
    """source mirrored along axis into a new glyph of that name, in every master it is drawn in, each
    contour then set to run as the source's does (a mirror alone leaves it reversed: that is the fault
    being set right). MirrorError, and the glyph taken out again, where anything does not measure right."""
    origin = font_glyph(package, source)
    if origin is None:
        raise MirrorError(u"%s is not in the font" % source)
    new = new_glyph(fontlab, package, name)
    package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
    glyph = font_glyph(package, name)
    if glyph is None:
        raise MirrorError(u"FontLab did not add %s" % name)
    try:
        drawn = 0
        for master in masters:
            layer_from = origin.getLayerByName(master)
            shapes = list(layer_from.shapes) if layer_from is not None else []
            before = layer_box(ak, layer_from)
            if not shapes or before is None:
                continue
            if any(shape_is_component(shape) for shape in shapes):
                raise MirrorError(u"%s is itself made of components in master %s: decompose it first" % (source, master))
            mirror = mirror_of(axis, layer_from.advanceWidth, before[1], before[3])
            layer = glyph.getLayerByName(master, True)
            # (made through setGlyphComponents first, with no component: a new glyph whose layer was only
            # made by getLayerByName crashed FontLab when its fgGlyph was read, live 2026-11-16)
            layer.setGlyphComponents([], float(layer_from.advanceWidth), package, False)
            for shape in shapes:
                layer.addShape(shape_copy(shape))
            layer.advanceWidth = float(layer_from.advanceWidth)
            points = layer_points(layer_from)
            wanted = mirrored_points(points, mirror)
            mirror_outlines(layer, mirror, points, wanted)
            for shape, shape_from in zip(list(layer.shapes), shapes):
                for contour, contour_from in zip(list(shape.contours), list(shape_from.contours)):
                    if contour is None or contour_from is None:  # (FontLab lists an empty contour as None)
                        continue
                    if drawn_clockwise(shape, contour) != drawn_clockwise(shape_from, contour_from):
                        contour.reverse()
                    if drawn_clockwise(shape, contour) != drawn_clockwise(shape_from, contour_from):
                        raise MirrorError(u"FontLab did not reverse a contour of %s" % name)
            if not same_points(layer_points(layer), wanted):
                raise MirrorError(u"the outlines of %s moved when its contours were reversed" % name)
            # The source's advance, set again: the layer's applyTransform mirrored it too (live 2026-11-16,
            # Varela Round's quoteright: 238 read back as -238)
            layer.advanceWidth = float(layer_from.advanceWidth)
            if abs(float(layer.advanceWidth) - float(layer_from.advanceWidth)) > 0.5:
                raise MirrorError(u"FontLab did not keep the advance of %s" % name)
            drawn += 1
        if not drawn:
            raise MirrorError(u"%s has no outline" % source)
    except Exception as exc:
        try:
            package.deleteGlyph(font_glyph(package, name))
        except Exception:
            pass
        if isinstance(exc, MirrorError):
            raise
        raise MirrorError(u"%s" % exc)
    return glyph


def corrected_glyph(fontlab, ak, package, masters, source, axis):
    """(name, the glyph added or None): source's corrected glyph along axis, the font's own where it has
    it already (made by an earlier run: is_corrected), else made now under the first free name. Every
    numbered name is tried too (caron.flipped2, caron.flipped3): where caron.flipped is another glyph, an
    earlier run made caron.flipped2, which is used again rather than one more made at each run."""
    def taken(candidate):  # (a glyph of that name that is not source's corrected glyph)
        return font_glyph(package, candidate) is not None and not is_corrected(ak, package, masters, source,
                                                                               candidate, axis)
    name = corrected_name(source, axis, taken)
    if font_glyph(package, name) is not None:
        return name, None
    return name, make_corrected(fontlab, ak, package, masters, source, axis, name)


# -- the dotless i and j a font lacks, made of its i and j (FontLab) -----------------------------------------
# Read and written with the calls the corrected glyphs above use (getLayerByName, shapes, contours, a
# contour's nodes() and their x and y, a shape's transform and clone, addGlyph, setGlyphComponents with no
# component first, addShape, advanceWidth, deleteGlyph, fgGlyph.unicode), and two that Glyph generation's
# stretched dashes use, live 2026-11-14: a contour's clone() and flShape().addContours(clones, True). Not
# proven live here yet; whatever FontLab does is read back node by node, and a glyph that does not measure
# right is taken out again and said so.

def numbered_contours(shapes):
    """[(shape's index, contour, its number)] of a layer's contours in order, every shape's (FontLab lists
    an empty contour as None: not counted). The number is what Dotless.dot and dot_index count."""
    found = []
    for at, shape in enumerate(shapes):
        for contour in shape.contours:
            if contour is not None:
                found.append((at, contour, len(found)))
    return found


def contour_points(shape, contour):
    """[(x, y)] of a contour's nodes as drawn, through its shape's transform (as layer_points reads them)."""
    m11, m12, m21, m22, dx, dy = transform_values(shape.transform)
    return [(m11 * x + m21 * y + dx, m12 * x + m22 * y + dy)
            for x, y in [(float(node.x), float(node.y)) for node in contour.nodes()]]


def contour_boxes(layer):
    """[(left, bottom, right, top)] of each contour of a layer as drawn, from its nodes (None for one with
    none), in numbered_contours' order; None where the layer holds a component (its glyph's contours are
    not this glyph's to take apart); [] where it draws nothing."""
    shapes = list(layer.shapes)
    if any(shape_is_component(shape) for shape in shapes):
        return None
    boxes = []
    for at, contour, _ in numbered_contours(shapes):
        points = contour_points(shapes[at], contour)
        xs, ys = [x for x, _ in points], [y for _, y in points]
        boxes.append((min(xs), min(ys), max(xs), max(ys)) if points else None)
    return boxes


class WithoutContour(object):
    """A layer seen without one of its contours (numbered_contours' count), as Auto Kerning's layer_path
    reads a layer (its shapes, each with its transform and contours): the dotless glyph a build will make,
    drawn before it is made."""

    def __init__(self, layer, dot):
        self.advanceWidth = layer.advanceWidth
        shapes = list(layer.shapes)
        numbered = numbered_contours(shapes)
        self.shapes = [_Contours(shape.transform, [contour for at_, contour, number in numbered
                                                   if at_ == at and number != dot])
                       for at, shape in enumerate(shapes)]


class _Contours(object):
    isComponent = False

    def __init__(self, transform, contours):
        self.transform, self.contours = transform, contours


def read_dotless(package, masters, font):
    """{0x0131 or 0x0237: Dotless} for the dotless letters the font lacks (neither the code point drawn
    nor a glyph of the names fonts give it): what its i or j, read in every master it is drawn in, can give.
    A dotless letter whose code point is the font's, empty, is refused (an empty glyph is never built on)."""
    found = {}
    for code in sorted(DOTLESS_LETTERS):
        letter, letter_code = DOTLESS_LETTERS[code]
        names = DOTLESS[letter][1]
        if font.drawn(code) or any(font.usable(name) for name in names):
            continue
        if font.by_code.get(code):
            found[code] = Dotless("refused", code, reason=u"the font's dotless %s is empty" % letter)
            continue
        source = font.drawn(letter_code)
        glyph = font_glyph(package, source) if source else None
        if glyph is None:
            found[code] = Dotless("refused", code, reason=u"the font has no dotless %s, and no %s to make one of" % (
                letter, letter))
            continue
        readings = []
        for master in masters:
            layer = glyph.getLayerByName(master)
            boxes = contour_boxes(layer) if layer is not None else []
            if boxes != []:  # (a master it is not drawn in is left out, as a build leaves it)
                readings.append(boxes)
        dotless = dotless_verdict(code, readings)
        dotless.source = source
        if dotless.kind == "made":
            dotless.name = next((name for name in names + (u"uni%04X" % code,) if name not in font.names), None)
            if dotless.name is None:
                dotless = Dotless("refused", code, reason=u"the font has no dotless %s, and its names are other "
                                                          u"glyphs' (%s)" % (letter, listed(names + (u"uni%04X" % code,))))
                dotless.source = source
        found[code] = dotless
    return found


class DotlessError(Exception):
    """Why a dotless i or j could not be made of the font's i or j (said in the log)."""


def make_dotless(fontlab, ak, package, masters, dotless):
    """dotless's glyph (kind "made") made of its letter without its dot, in every master the letter is
    drawn in: the other contours copied (a shape without the dot whole, its transform kept; the dot's own
    shape as a new shape of clones of its other contours), the letter's advance width kept, so its
    sidebearings too. Made as a new glyph is everywhere here: its layers through setGlyphComponents with no
    component first (a layer made by getLayerByName alone crashed FontLab, live 2026-11-16), the code point
    set last, once every layer is made (given before, FontLab kept none of the layers made on it, live
    2026-11-11), the glyph looked up again by name. Each master is read again first (still two contours,
    the same one clearly the dot) and read back node by node after; DotlessError, and the glyph taken out
    again, where anything does not measure right. The glyph made."""
    origin = font_glyph(package, dotless.source)
    if origin is None:
        raise DotlessError(u"%s is not in the font" % dotless.source)
    if font_glyph(package, dotless.name) is not None:
        raise DotlessError(u"%s is in the font already" % dotless.name)
    new = new_glyph(fontlab, package, dotless.name)
    package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
    glyph = font_glyph(package, dotless.name)
    if glyph is None:
        raise DotlessError(u"FontLab did not add %s" % dotless.name)
    try:
        drawn = 0
        for master in masters:
            layer_from = origin.getLayerByName(master)
            boxes = contour_boxes(layer_from) if layer_from is not None else []
            if boxes == []:
                continue  # (not drawn in this master: no layer made, as a build makes none)
            if boxes is None or dot_index(boxes) != dotless.dot:
                raise DotlessError(u"%s changed in master %s since the list was made" % (dotless.source, master))
            shapes = list(layer_from.shapes)
            numbered = numbered_contours(shapes)
            wanted = [point for at, contour, number in numbered if number != dotless.dot
                      for point in contour_points(shapes[at], contour)]
            width = float(layer_from.advanceWidth)
            layer = glyph.getLayerByName(master, True)
            layer.setGlyphComponents([], width, package, False)
            for at, shape in enumerate(shapes):
                own = [(contour, number) for at_, contour, number in numbered if at_ == at]
                kept = [contour for contour, number in own if number != dotless.dot]
                if len(kept) == len(own):
                    layer.addShape(shape_copy(shape))
                elif kept:  # (the dot shares this shape: its other contours in a shape of their own)
                    piece = fontlab.flShape()
                    piece.addContours([contour.clone() for contour in kept], True)
                    layer.addShape(piece)
            layer.advanceWidth = width
            if not same_points(layer_points(layer), wanted):
                raise DotlessError(u"FontLab did not copy the outlines of %s in master %s" % (dotless.source, master))
            if abs(float(layer.advanceWidth) - width) > 0.5:
                raise DotlessError(u"FontLab did not keep the advance of %s in master %s" % (dotless.name, master))
            drawn += 1
        if not drawn:
            raise DotlessError(u"%s has no outline" % dotless.source)
        font_glyph(package, dotless.name).fgGlyph.unicode = dotless.code
    except Exception as exc:
        try:
            package.deleteGlyph(font_glyph(package, dotless.name))
        except Exception:
            pass
        if isinstance(exc, DotlessError):
            raise
        raise DotlessError(u"%s" % exc)
    return font_glyph(package, dotless.name)


def relink_plan(ak, package, master, glyph, corrected):
    """(layer, its shapes, [None for an outline of its own, else (glyph, transform) of a component], how
    many components are set right) of a glyph's mirrored components in a master pointed to their
    corrected glyphs, or None where nothing in it is mirrored; nothing is written. MirrorError where one
    cannot be set right."""
    layer = glyph.getLayerByName(master)
    shapes = list(layer.shapes) if layer is not None else []
    planned, changed = [], 0
    for shape in shapes:
        if not shape_is_component(shape):
            planned.append(None)
            continue
        source = u"%s" % shape.shapeData.componentGlyph
        values = transform_values(shape.transform)
        if is_mirror(values):
            axis = mirror_axis(*values[:4])
            name = corrected(source, axis)
            mirror = source_mirror(ak, package, master, source, axis)
            if mirror is None:
                raise MirrorError(u"%s has no outline in master %s" % (source, master))
            source, values = name, without_mirror(values, mirror)
            changed += 1
        planned.append((source, values))
    return (layer, shapes, planned, changed) if changed else None


def relink_mirrored(fontlab, ak, package, masters, glyph, corrected, before_write=None):
    """A glyph's mirrored components pointed to their corrected glyphs, in every master or in none:
    corrected(source, axis) gives the corrected glyph's name (or raises MirrorError). Every master is
    planned first (relink_plan), and nothing is written unless all of them can be: one master set right
    and another left mirrored would no longer match, and the glyph would not interpolate. Each layer's
    components are written again in their order, its own outlines kept after them; where FontLab keeps
    nothing, or the picture is not the same afterward, every master written is put back and MirrorError
    raised. How many were set right."""
    QtCore, QtGui = _qt()
    plans = []
    for master in masters:
        plan_ = relink_plan(ak, package, master, glyph, corrected)
        if plan_ is not None:
            layer, shapes, planned, changed = plan_
            components = []
            for source, values in [step for step in planned if step is not None]:
                component = fontlab.GlyphComponent(source)
                component.transform = QtGui.QTransform(*values)
                components.append(component)
            plans.append((master, layer, shapes, planned, changed, components))
    if not plans:
        return 0
    if before_write is not None:  # (every master planned: the parts it points to recorded before it changes)
        before_write()
    written = []  # (layer, its shapes as they were, its width) of each master taken apart so far
    for master, layer, shapes, planned, changed, components in plans:
        before, points = layer_box(ak, layer), layer_points(layer)
        width = float(layer.advanceWidth)
        written.append((layer, [shape_copy(shape) for shape in shapes], width))
        own = [shape_copy(shape) for shape, step in zip(shapes, planned) if step is None]
        layer.removeAllShapes()
        good, problem = False, u""
        try:
            layer.setGlyphComponents(components, width, package, False)
            for shape in own:
                layer.addShape(shape)
            # read back: something is drawn, it is drawn where it was (its box, and each of its nodes as its
            # shapes place them), and nothing in it is mirrored any more
            good = (bool(list(layer.shapes)) and same_box(layer_box(ak, layer), before)
                    and same_points(layer_points(layer), points) and not mirrored_components(layer))
        except Exception as exc:
            problem = u" (%s)" % exc
        if not good:  # every master as it was
            for layer_, originals, width_ in written:
                layer_.removeAllShapes()
                for shape in originals:
                    layer_.addShape(shape)
                layer_.advanceWidth = width_
            error = MirrorError(u"FontLab did not keep the new components in master %s%s: left as it was in every "
                                u"master" % (master, problem))
            error.written = True  # (its shapes were taken out and put back: a change to record all the same)
            raise error
    return sum(plan_[4] for plan_ in plans)


def component_parts(layer):
    """[(glyph, dx, dy)] of a layer made only of components, each only moved, or None (a component
    scaled, flipped, rotated, or slanted: its ink is not its glyph's as measured, so it shows nothing)."""
    parts = []
    for shape in layer.shapes:
        try:
            if not shape.isComponent:
                return None
            transform = shape.transform
            if (abs(transform.m11() - 1) > 1e-6 or abs(transform.m22() - 1) > 1e-6 or abs(transform.m12()) > 1e-6
                    or abs(transform.m21()) > 1e-6):
                return None
            parts.append((shape.shapeData.componentGlyph, transform.dx(), transform.dy()))
        except Exception:
            return None
    return parts or None


HELP = u"""<b>FreeLab Glyph Compose</b><br>
Builds the glyphs this font lacks from the glyphs it has. Two tabs: <i>Diacritics</i> (the letters with
diacritics, and the anchors of scripts whose marks attach) and <i>Glyph generation</i> (spaces, dashes,
punctuation, look-alike letters, ligature letters, fractions, arrows, turned and reversed letters, superscript and
subscript signs and letters, signs made of letters (the trade mark and numero signs), circled figures and letters,
full-width and half-width forms, small capitals, letters with bars, small kana, squared words and abbreviations,
Kangxi radicals, telegraph symbols, Roman numerals, and parenthesized and numbered forms). Nothing
is made until you click <i>Build ticked glyphs</i> (on <i>Mark anchors</i>: <i>Add ticked anchors</i>).<br><br>
<b>Diacritics</b> builds the letters with diacritics this font lacks (Latin, Greek, Cyrillic, and the voiced
kana) from its letters and marks, as glyphs of components, placing each diacritic as the font's own accented
glyphs place theirs (no anchors needed).<br>
<b>The list</b>: each glyph that can be built, drawn as it would be, with the glyphs it is
built from. Capitals take a mark's .case form where the font has one; i and j take their dotless
forms under a mark above (a font with none has them made of its i and j without their dot, where the dot
can be told; else the row says that the dot stays, and the log warns of it at the build). A mark the font lacks is borrowed (a dot below from the dot accent) or
drafted from its punctuation, and the list says so. Glyphs that cannot be built say what the
font lacks (select one to see it in the reference font). Where fonts draw another mark than Unicode's
decomposition names (Latvian's comma below for a cedilla, the vertical caron of d, t, l, and L), that mark is
used, and the row says why. Double-click a row to open its glyph (or, not built yet, its letter) in a
<i>Glyph</i> window.<br>
<b>The editor</b> (under the list): the selected glyph between its letter and a letter the font has
with the same base (double-click that one to go to its row; double-click the glyph to open it). Click a diacritic
to select it; drag it, or press the arrow keys (<i>Shift</i>: 10 units), to move it; drag a corner or a side of its
frame to scale it (<i>Shift</i> on a corner: in proportion); <i>Tab</i> selects the next diacritic, <i>Backspace</i>
puts the selected one back. Dragged, a diacritic's center snaps to the letter's box center or top center (bottom
center, for a diacritic below), a guide drawn; <i>Alt</i>: no snapping. Your changes stay with the glyph as
you go down the list, and are built. The faint dashed lines are the font's lines, each named at one end. A
limit says in parentheses what happens past it (Windows clips past winAscent and winDescent, macOS past the
hhea values, and past the room of a 120% line the glyph meets the next line), and turns amber when a diacritic
crosses it; the font's ascender and descender and the typo values are drawn for reference and never do.<br>
<b>Room</b>: <i>Compact diacritics to fit the line</i> (beside the preview, unticked at first) makes the diacritics
of a glyph too tall for a 120% line compact, by no more than it needs (its gaps closed just enough, and only then
its diacritics made smaller); glyphs you placed by hand keep what you set.<br>
<b>Finding glyphs</b>: type in <i>Find a glyph</i> to show only the rows with that text in their name or in
what they are built from, that character, or that Unicode value; the others keep their ticks, and <i>Build
ticked glyphs</i> builds them too (the count beside the field says how many ticked ones are hidden). <i>Tick
high-value glyphs</i> ticks those <i>Font Check</i> lists as completing languages already within reach, and
unticks the others shown.<br>
<b>Reference</b>: the character in another font, to compare: {reference} at first,
or one you pick (its entry at the top of the list takes the pick back).<br>
<b>Mirrored components</b>: a component mirrored one way has its contours reversed, and shows a hole where it
overlaps another part. Glyph Compose builds none; <i>Correct mirrored components</i> sets right those the listed
glyphs of the font have.<br>
<i>Restore suggestions</i> puts every tick and every diacritic back as the list first came.<br>
<b>Masters</b>: each glyph is built in every master, each measured on its own; diacritics moved by hand
move by as much in every master.<br><br>
<b>Glyph generation</b> lists the characters the font lacks that it can make of glyphs it has: each with
its recipe, a picture, and how sure the recipe is (<i>exact</i>: no design in it; <i>accepted</i>: how
fonts commonly build it; <i>starting point</i>: a draft to draw over, never a finished glyph; <i>likely usable
as it is</i>: a turned or reversed letter of a monoline design). Ticked
rows are built in every master; <i>Edit &gt; Undo</i> takes them back (in two steps when some of them are made of
others built with them, as the log says).<br><br>
Click this help's button, then anything in the window, for what it does (or right-click it: <i>What's This?</i>)."""

LINES_HELP = (u"The faint dashed lines are the font's lines, named at one end (equal ones share a line). A limit "
              u"says in parentheses what happens past it: Windows clips past winAscent and winDescent, macOS past "
              u"the hhea values, and past the room of a 120% line the glyph meets the next line; a limit a diacritic "
              u"crosses turns amber. The font's ascender and descender and its typo values are reference lines: "
              u"drawn, never amber.")
TOP_TABS = (u"Diacritics", u"Glyph generation")
# What Glyph generation builds: its table's groups (freelab_glyph_generation.py), the CJK ones included
GENERATED_KINDS = (u"spaces, dashes, punctuation, look-alike letters, ligature letters, fractions, arrows, turned and "
                   u"reversed letters, superscript and subscript signs and letters, signs made of letters (the trade "
                   u"mark and numero signs), circled figures and letters, full-width and half-width forms, small "
                   u"capitals, letters with bars, small kana, squared words and abbreviations, Kangxi radicals, "
                   u"telegraph symbols, Roman numerals, and parenthesized and numbered forms")
TAB_KEYS = ("letters", "anchors", "generation")  # the three tabs with a list: their status lines and bottom-row parts
TOP_TABS_HELP = (u"<i>Diacritics</i> builds the letters with diacritics the font lacks, and places the anchors of "
                 u"scripts whose marks attach. <i>Glyph generation</i> builds other glyphs the font lacks from the "
                 u"glyphs it has: %s." % GENERATED_KINDS)
TOP_TAB_HELPS = (u"Letters with diacritics, and mark anchors.",
                 u"%s%s, made of the glyphs the font has." % (GENERATED_KINDS[0].upper(), GENERATED_KINDS[1:]))
GENERATION_FILE, GENERATION_MODULE = "freelab_glyph_generation.py", "freelab_glyph_generation"  # (its tab)
TABS_HELP = (u"<i>Letters with diacritics</i> builds the letters the font lacks from its letters and marks. "
             u"<i>Mark anchors</i> places anchors, and writes the mark features, for scripts whose marks are "
             u"attached instead.")
TAB_HELPS = (u"The letters with diacritics the font lacks, built from its letters and marks as glyphs of components.",
             u"Anchors and mark features for scripts whose marks are attached, not built (Khmer, Thai, Arabic, "
             u"Hebrew, Devanagari, Bengali, Gujarati, Tamil, and the combining marks of any script).")
STRIP_HELP = (u"The letters with the same diacritic as the selected glyph (on the same side, capitals and "
              u"lowercase): click one to select it and see how the diacritic sits on it, after placing it by hand or "
              u"applying it to related letters.")
REFERENCE_NOTE_HELP = (u"Which font the reference is drawn in: the one chosen, or, where that one lacks the "
                       u"character, the font drawn in its place.")
HINT_HELP = (u"What is selected in the picture: the diacritic, how far it was moved and scaled by hand, and whether it "
             u"lies outside the picture; else what a click there does.")
CORRECT_HELP = (u"Sets right the mirrored components of the font's glyphs listed and shown (under <i>Also list "
                u"existing glyphs</i> and <i>Built in this window</i>). A component mirrored one way (scaled by a "
                u"negative number across or up, not both) has its contours reversed, so renderers leave a hole "
                u"where it overlaps another part. The glyph it points to is mirrored into a glyph of its own with "
                u"its contours reversed (<i>caron.flipped</i> upside down, <i>comma.mirrored</i> left to right), "
                u"made once for every glyph that needs it, and the component points there, no longer mirrored: "
                u"the glyph looks as it did. In every master; <i>Edit &gt; Undo</i> takes it back (in two steps "
                u"when glyphs are added, as the log says). A glyph left as it is keeps the note in its row.")
REFERENCE_SLICE = 40  # entries of the reference font's chooser given their own font per turn of the event loop
OWN_WRITE_SECONDS = 3.0  # a History step FontLab records this soon after the dialog's own write is that write's
REVEALED_WAIT_MS = 700  # a row selected: the glyph listed to show it goes this long after (past a double-click)


def existing_glyphs(package, names):
    """The font's glyphs of these names (those it has; each once), for begin_write: every glyph a write's
    step records (notify_changed's glyphs, touched) must have a state of its own before it, or FontLab's
    Undo has nothing to put it back to. Glyph Compose recorded only the font (and the glyphs given a second
    code point) before its writes, and its steps recorded the glyphs they touched, the font's own among
    them, with no state of theirs before: undoing them made FontLab print "We have a problem with the
    component 'dotlessi' in glyph 'i:Regular'" for such glyphs (the owner's report of 2026-11-16; the
    cause is read from the History's rules, docs/FONTLAB7-API.md of FreeLab MCP, not proven live)."""
    found, seen = [], set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            glyph = package.findName(name)
        except Exception:
            glyph = None
        if glyph is not None and not getattr(glyph, "isNull", False):
            found.append(glyph)
    return found


PARTS_TITLE = u"FreeLab Glyph Compose (parts)"  # (the History step of the glyphs a write adds that others are made of)


def record_parts(ak, fontlab, package, parts, title=PARTS_TITLE):
    """The glyphs a write adds that others of the same write are made of (corrected glyphs for mirrored parts,
    a glyph built here first), recorded as a History step of their own before any glyph made of them is
    written: notify_changed's WriteStatus, or None (no such glyph: no step). One step holding both made
    FontLab's Undo take the parts out first and print "Component 'R.mirrored' referenced in glyph
    'uni042F:Black' does not exist in the font"; in a step of their own (the coordinator's probe C, Rubik,
    2026-11-16), every Undo and Redo was clean: the first Undo takes the glyphs made of them back, the
    second the parts."""
    if not parts:
        return None
    return ak.notify_changed(fontlab, package, title, list(parts))


def parts_step_text(names, named=None):
    """The log's line for a write recorded in two steps (record_parts); named: how a glyph's name is
    written (the log's ak.glyph_name_link), as it is by default."""
    names = [name for name in names if name]
    named = named or (lambda text: text)
    one = len(names) == 1
    return (u"This takes two steps of <i>Edit &gt; Undo</i>: %s %s added in a step of %s own first, so that FontLab's "
            u"Undo never takes out a glyph that others still point to." % (
                u", ".join(named(name) for name in names), u"was" if one else u"were", u"its" if one else u"their"))


def undo_words(status, text):
    """text, a promise of Undo, unless notify_changed's WriteStatus says FontLab's History did not record
    the write (u"" then)."""
    return text if getattr(status, "recorded", True) else u""


def report_write(status, log):
    """notify_changed's failure, if any (not recorded in the History, the font not marked modified),
    added to the log as an error; and the font info updated to match the write, if it was."""
    if status is not None and not getattr(status, "ok", True):
        log.add(status.message(), "error")
    report_info = getattr(status, "report_info", None)
    if report_info is not None:
        report_info(log)


def fit_tree_columns(tree, count):
    """A list's first `count` columns fitted to the rows it shows (Qt measures only those): with every
    section closed, to the headings alone (live 2026-11-14, Noto Sans with Also list existing glyphs
    ticked: Glyph 40 pixels, its pictures and names cut off once Existing glyphs was opened). Called
    again as a section opens."""
    try:
        tree.doItemsLayout()
    except Exception:
        pass
    for column in range(count):
        tree.resizeColumnToContents(column)


def helped(widget, text):
    """A widget given its What's This text, and returned: a label beside a control carries the control's
    text, so that a right click on either says the same (a label without one showed the whole dialog's)."""
    try:
        widget.setWhatsThis(text)
    except Exception:
        pass
    return widget


def heading_line(ak):
    """The line between a tab's list and the Reference heading under it (owner's images 234, 288, and 318: a
    heading after a table gets a separator, so that it never reads as the table's caption), in a holder of its
    own: the tab shows and hides the holder with the heading (nothing selected: no heading, no line), the shared
    module the line with the font."""
    QtCore, QtGui = _qt()
    holder = QtGui.QWidget()
    box = QtGui.QVBoxLayout(holder)
    box.setContentsMargins(0, 0, 0, 0)
    box.addWidget(ak.separator())
    return holder


def row_height(widgets):
    """The height of the tallest of these controls as Qt sizes them (a dropdown, a field, a spin box), or 0
    where none can tell: the least height of every options row above a tab's list, so that each list starts
    at the same height whatever its row holds (brief 23, owner's images 285 and 286)."""
    found = 0
    for widget in widgets:
        try:
            found = max(found, int(_property(widget, "sizeHint").height()))
        except Exception:
            continue
    return found


def bundled_family_text(ak):
    """How the texts name the font FreeLab bundles for references: by its family name, read from Font
    Check's constant (never written here: renaming the font there renames it here), in italics; plainly
    where Font Check cannot be read."""
    try:
        module = ak.load_sibling(FONT_CHECK_FILE, FONT_CHECK_MODULE)
        family = getattr(module, "LIST_DISPLAY_NAME", None) or module.LIST_FAMILY  # (the name it goes by)
        if family:
            return u"FreeLab's own <i>%s</i>" % family
    except Exception:
        pass
    return u"FreeLab's own font"


TOOL_TITLE = "Glyph Compose"  # its entry in Scripts > FreeLab, and its name in the tools button
EDITOR_HEIGHT = 300  # pixels, the editor's least height
STRIP_HEIGHT = 34  # pixels, the strip of letters with the same diacritic
REFERENCE_WIDTH = 170  # pixels, the reference's column
HANDLE = 4  # half the side of a frame's handle, in pixels
GLYPH_HIT = 4  # pixels around a glyph's ink that still count as on it (glyph_at)
SETTINGS_FILE = "glyph_compose.json"  # in FreeLab's state folder: the reference font chosen, and the like
OLD_SETTINGS_FILES = ("diacritics.json",)  # the same settings under the tool's earlier name: read once, then gone
NEIGHBOR_ALPHA = 110  # the letters beside the edited glyph, dimmed
# Families known for many Latin, Greek, and Cyrillic letters: the reference is the installed one with
# the most of the listed characters (all installed families would take minutes to look through).
REFERENCE_FAMILIES = ("Noto Sans", "Noto Serif", "Gentium Plus", "Gentium Book Plus", "Charis SIL", "Andika",
                      "DejaVu Sans", "Segoe UI", "Arial", "Times New Roman", "Calibri", "Cambria", "Tahoma",
                      "Verdana", "Open Sans", "Roboto", "Source Sans 3", "Source Serif 4", "IBM Plex Sans")


def settings_path(ak):
    return os.path.join(ak.state_dir(), SETTINGS_FILE)


def read_settings(ak):
    """The window's settings; where there are none yet, those saved under the tool's earlier name
    (OLD_SETTINGS_FILES), moved to the new file once and the old file removed, so that the choices made
    in Diacritics (its reference font, Compact diacritics) carry over."""
    import io
    import json

    def read(path):
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (IOError, OSError, ValueError):
            return None

    data = read(settings_path(ak))
    if data is not None:
        return data
    for name in OLD_SETTINGS_FILES:
        old = os.path.join(ak.state_dir(), name)
        data = read(old)
        if data is None:
            continue
        write_settings(ak, data)
        if read(settings_path(ak)) == data:  # (the old file goes only once the new one holds the same)
            try:
                os.remove(old)
            except OSError:
                pass
        return data
    return {}


def write_settings(ak, data):
    import io
    import json
    try:
        folder = os.path.dirname(settings_path(ak))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(settings_path(ak), "w", encoding="utf-8") as handle:
            handle.write(u"%s" % json.dumps(data, indent=1, sort_keys=True))
    except (IOError, OSError):
        pass


def has_character(family, code):
    """Whether an installed font family itself has a character: QRawFont reads the family's own font
    (QFontMetrics.inFontUcs4 answers for Windows' fallback fonts too, and drew another font's glyph
    as the chosen one's); where it cannot, the answer is no."""
    QtCore, QtGui = _qt()
    font = QtGui.QFont(family)
    try:
        if u"%s" % QtGui.QFontInfo(font).family() != u"%s" % family:
            return False  # not installed: Qt picked another
    except Exception:
        pass
    try:
        raw = QtGui.QRawFont.fromFont(font)
        valid = raw.isValid
        if valid() if callable(valid) else valid:
            return bool(raw.supportsCharacter(code))
    except Exception:
        pass
    return False


# Families with other scripts' letters and marks (Windows' own, then Google's Noto): a reference for them
SCRIPT_FAMILIES = {"arabic": ("Noto Naskh Arabic", "Noto Sans Arabic", "Segoe UI", "Arial", "Tahoma"),
                   "hebrew": ("Noto Serif Hebrew", "Noto Sans Hebrew", "Frank Ruhl Libre", "David", "Segoe UI", "Arial",
                              "Tahoma"),
                   "bengali": ("Noto Sans Bengali", "Noto Serif Bengali", "Hind Siliguri", "Nirmala UI", "Vrinda"),
                   "gujarati": ("Noto Sans Gujarati", "Noto Serif Gujarati", "Hind Vadodara", "Nirmala UI", "Shruti"),
                   "tamil": ("Noto Sans Tamil", "Noto Serif Tamil", "Hind Madurai", "Nirmala UI", "Latha"),
                   "devanagari": ("Noto Sans Devanagari", "Noto Serif Devanagari", "Nirmala UI", "Mangal"),
                   "thai": ("Noto Sans Thai", "Noto Serif Thai", "Leelawadee UI", "Tahoma"),
                   "lao": ("Noto Sans Lao", "Leelawadee UI"),
                   "khmer": ("Noto Sans Khmer", "Noto Serif Khmer", "Khmer UI", "Leelawadee UI"),
                   "myanmar": ("Noto Sans Myanmar", "Myanmar Text"),
                   "kana": ("Noto Sans JP", "Noto Serif JP", "BIZ UDPGothic", "Yu Gothic", "Meiryo", "MS Gothic")}
DOTTED_CIRCLE = 0x25CC  # what a mark is drawn on without a letter


def script_families(script):
    return SCRIPT_FAMILIES.get(script, ())


REFERENCE_MARGIN = 4.0  # pixels kept clear around the reference's ink


def reference_fit(top, bottom, width, area_width, area_height, baseline, margin=REFERENCE_MARGIN):
    """(scale, baseline) that fit a text's ink in the reference's picture: top and bottom are its ink's
    extent from the baseline (y down: top is negative above it), width its ink's width, all in pixels at
    the drawing size. The text keeps its size and its baseline where every reference has it while it
    fits; it is moved up or down only as far as its ink needs, and made smaller only when it is taller or
    wider than the picture. The picture used to keep 1.15 of the size over the baseline and 0.45 under it
    whatever was drawn: a font whose ink rises higher, or reaches lower (a stacked capital, a tall mark,
    a font with long descenders), was cut off at the picture's edge."""
    top, bottom, width = finite(top), finite(bottom), max(0.0, finite(width))
    scale = 1.0
    if width > 0:
        scale = min(scale, area_width * 0.92 / width)
    if bottom - top > 0:
        scale = min(scale, (area_height - 2.0 * margin) / (bottom - top))
    low = margin - top * scale  # the highest the baseline may sit: the ink's top at the margin
    high = area_height - margin - bottom * scale  # the lowest: its bottom at the margin
    return scale, min(max(baseline, low), max(high, low))


def reference_picture(text, family, palette):
    """text drawn in a font family, centered in the reference column, in the dialog's text color, fitted
    to its ink (reference_fit)."""
    QtCore, QtGui = _qt()
    font = QtGui.QFont(family)
    size = int(REFERENCE_WIDTH * 0.62)
    font.setPixelSize(size)
    path = QtGui.QPainterPath()
    # Filled as text is: by nonzero winding. A QPainterPath fills by the even-odd rule unless told, which
    # punched a hole wherever two of the text's glyphs overlapped (a mark on a letter, a mark on a mark).
    path.setFillRule(QtCore.Qt.WindingFill)
    path.addText(QtCore.QPointF(0, 0), font, text)
    box = path.boundingRect()
    # Its edges too, dashed, as the font's own preview beside it has them: a space, or a glyph of no ink, showed
    # nothing at all (owner's image 353). The advance is Qt's for the text in that font.
    try:
        metrics = QtGui.QFontMetricsF(font)
        measure = getattr(metrics, "horizontalAdvance", None) or metrics.width  # (Qt before 5.11 has width only)
        advance = float(measure(text))
    except Exception:
        advance = None
    left, right = box.left(), box.right()
    if advance is not None and advance > 0:
        left, right = min(left, 0.0) if box.width() > 0 else 0.0, max(right, advance) if box.width() > 0 else advance
    top, bottom = (box.top(), box.bottom()) if box.height() > 0 else (-size * 0.7, 0.0)
    height = int(size * 1.6)
    scale, baseline = reference_fit(top, bottom, right - left, REFERENCE_WIDTH, height, size * 1.15)
    pixmap = QtGui.QPixmap(REFERENCE_WIDTH, height)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    try:  # ended before anything else can fail
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.translate(REFERENCE_WIDTH / 2.0, baseline)
        painter.scale(scale, scale)
        painter.translate(-left - (right - left) / 2.0, 0)
        color = palette.color(QtGui.QPalette.WindowText)
        painter.fillPath(path, QtGui.QBrush(color))
        if advance is not None and advance > 0:
            edge = QtGui.QColor(color)
            edge.setAlpha(140)
            pen = QtGui.QPen(edge, 1.0 / max(scale, 0.001), QtCore.Qt.DashLine)
            painter.setPen(pen)
            reach = (height / max(scale, 0.001))
            for x in (0.0, advance):
                painter.drawLine(QtCore.QPointF(x, -reach), QtCore.QPointF(x, reach))
    finally:
        painter.end()
    return pixmap


def cluster_holds(family, text):
    """Whether a font family draws a letter with combining marks with the marks on the letter (ink_holds):
    the cluster's ink against the letter's alone, both as Qt shapes them in that font, and their advances
    where Qt gives them. FontLab has no shaper to ask; what Qt draws is what the reference would show."""
    QtCore, QtGui = _qt()
    font = QtGui.QFont(family)
    size = int(REFERENCE_WIDTH * 0.62)
    font.setPixelSize(size)

    def ink(drawn):
        path = QtGui.QPainterPath()
        path.addText(QtCore.QPointF(0, 0), font, drawn)
        box = path.boundingRect()
        return box.left(), box.right()

    advances = [None, None]
    try:
        metrics = QtGui.QFontMetricsF(font)
        measure = getattr(metrics, "horizontalAdvance", None) or metrics.width  # (Qt before 5.11 has width only)
        advances = [float(measure(text[:1])), float(measure(text))]
    except Exception:
        advances = [None, None]
    return ink_holds(ink(text[:1]), ink(text), float(size), advances[0], advances[1])


def joined_path(ink, parts):
    """The parts [(glyph, x scale, y scale, x, y)] as one path in font units, filled by nonzero winding,
    each outline transformed as its component would be: what a renderer draws of a glyph of components
    kept as they are. A mirrored part's contours come out reversed, as in the font, so a hole drawn here
    is a hole that would ship."""
    QtCore, QtGui = _qt()
    whole = QtGui.QPainterPath()
    whole.setFillRule(QtCore.Qt.WindingFill)
    for glyph, sx, sy, dx, dy in parts:
        path = ink.path(glyph)[0]
        if path is not None:
            whole.addPath(QtGui.QTransform(sx, 0.0, 0.0, sy, dx, dy).map(path))
    return whole


# The editor's texts, laid out so that no two overlap at any size and with any font's lines (the owner's
# report of 2026-11-14: the caption under the glyphs was drawn over the names of the lines below them)
SNAP_BAND = 14  # pixels at the editor's top: the name of the center a dragged mark snapped to
LABEL_HEIGHT = 12  # pixels, a line's name
LABEL_GAP = 2  # pixels kept between two names, up and down
LABEL_SPACE = 8  # pixels kept between two names side by side
CAPTION_HEIGHT = 16  # pixels, a caption under a glyph (Current, Suggested)
CAPTION_SCALE = 0.9  # a caption's size, of the editor's font's (the shared preview_caption's), in the quiet color
EDGE_PAD = 12  # pixels kept around the picture


def text_width(metrics, text):
    """A text's width in pixels by a QFontMetrics (horizontalAdvance from Qt 5.11, width before), or by
    7 pixels a character where it cannot be measured (a test's stand-in)."""
    try:
        measure = getattr(metrics, "horizontalAdvance", None) or metrics.width
        return float(measure(text))
    except Exception:
        return 7.0 * len(text or u"")


def split_caption(text):
    """(head, tail) of a caption whose detail is in parentheses ("Suggested", "(13 right, 8 down)"); (text,
    None) for one without."""
    at = text.find(u" (")
    if at > 0 and text.endswith(u")"):
        return text[:at], text[at + 1:]
    return text, None


def _spread(items, width):
    """items [(center, width)] in order, laid side by side: each as near its center as the others leave it,
    LABEL_SPACE apart, within the editor; [left]."""
    lefts = [min(max(finite(c) - w / 2.0, 4.0), max(width - 4.0 - w, 4.0)) for c, w in items]
    for k in range(1, len(items)):  # (pushed right, then back left where the right edge is passed)
        lefts[k] = max(lefts[k], lefts[k - 1] + items[k - 1][1] + LABEL_SPACE)
    for k in range(len(items) - 1, -1, -1):
        edge = width - 4.0 if k == len(items) - 1 else lefts[k + 1] - LABEL_SPACE
        lefts[k] = max(4.0, min(lefts[k], edge - items[k][1]))
    return lefts


def _clash(placed):
    return any(row == other_row and left < other + other_wide + LABEL_SPACE and other < left + wide + LABEL_SPACE
               for k, (_, _, left, wide, row) in enumerate(placed) for (_, _, other, other_wide, other_row) in placed[:k])


def caption_layout(spans, width, row_height=CAPTION_HEIGHT):
    """[(span index, piece, left, width, row)] of captions under glyphs, spans [(center, text width, head
    width, tail width)] (head and tail: split_caption's, None for a caption that has no tail): each whole
    and centered under its glyph where all fit so on one row; else the captions stay on one row, those with
    a detail in parentheses split, the detail on the row under its head ("Current" beside "Suggested", "(13
    right, 8 down)" under "Suggested": the owner's report of 2026-11-16, where the whole of the second went
    to a row of its own), the heads moved apart, side by side, as little as keeps them LABEL_SPACE apart.
    Only where even so they cannot fit the editor does a caption go a row down. Piece: "whole", "head", or
    "tail". The rows' count is max(row) + 1."""
    spans = [tuple(span) + (None, None) if len(span) == 2 else tuple(span) for span in spans]
    room = max(1.0, width - 8.0)
    whole = [(finite(center), max(1.0, min(finite(wide), room))) for center, wide, _, _ in spans]
    placed = [(k, "whole", left, whole[k][1], 0) for k, left in
              enumerate([min(max(c - w / 2.0, 4.0), max(width - 4.0 - w, 4.0)) for c, w in whole])]
    if not _clash(placed):
        return placed
    heads = [(c, max(1.0, min(finite(head if tail is not None else wide), room)))
             for (c, _), (_, wide, head, tail) in zip(whole, spans)]
    order = sorted(range(len(spans)), key=lambda k: heads[k][0])
    lefts = dict(zip(order, _spread([heads[k] for k in order], width)))
    placed = [(k, "head" if spans[k][3] is not None else "whole", lefts[k], heads[k][1], 0) for k in range(len(spans))]
    tails = [k for k in order if spans[k][3] is not None]
    tail_items = [(lefts[k] + heads[k][1] / 2.0, max(1.0, min(finite(spans[k][3]), room))) for k in tails]
    placed += [(k, "tail", left, item[1], 1) for k, left, item in zip(tails, _spread(tail_items, width), tail_items)]
    while _clash(placed):  # (an editor too narrow for them side by side: the last that clashes goes down a row)
        for k in range(len(placed) - 1, 0, -1):
            index, piece, left, wide, row = placed[k]
            if any(row == r and left < o + ow + LABEL_SPACE and o < left + wide + LABEL_SPACE
                   for _, _, o, ow, r in placed[:k]):
                placed[k] = (index, piece, left, wide, row + 1)
                break
    return placed


def label_layout(wanted, width, low, high, height=LABEL_HEIGHT):
    """[(left, top, width) or None] of the lines' names, wanted [(y of the line, whether the name goes
    over it, text width)], in the order they are drawn: each at the left or the right end of its line,
    over it (a line above the baseline) or under it, as it was; where both ends are taken by names drawn
    before (lines a few pixels apart), on the other side of its line, else moved away from it by the
    least that leaves it clear. No two names overlap, and none leaves [low, high] (the band of the
    snapped center's name above, the captions below). None: no room left for it (an editor too small)."""
    placed, found = [], []
    step = height + LABEL_GAP
    for y, over, wide in wanted:
        y = finite(y)
        wide = max(1.0, min(finite(wide), width - 8.0))
        first = y - height - 1 if over else y + 1
        second = y + 1 if over else y - height - 1
        away = -1 if over else 1  # (moved off the line: up for a name over it, down for one under it)
        tops = [first, second]
        for k in range(1, int(max(0.0, high - low) / step) + 2):
            tops += [first + away * k * step, second - away * k * step]
        choice = None
        for top in tops:
            if top < low or top + height > high:
                continue
            for left in (4.0, width - 4.0 - wide):
                if not any(left < x + w + LABEL_SPACE and x < left + wide + LABEL_SPACE and
                           top < t + height + LABEL_GAP and t < top + height + LABEL_GAP for x, t, w in placed):
                    choice = (left, top, wide)
                    break
            if choice is not None:
                break
        if choice is not None:
            placed.append(choice)
        found.append(choice)
    return found


def editor_pads(captions_rows):
    """(top, bottom) pixels the editor keeps clear of its picture's lines: the snapped center's name and
    a line's name over the top line; a line's name under the bottom line, and the captions' rows."""
    return (SNAP_BAND + LABEL_HEIGHT + LABEL_GAP,
            max(EDGE_PAD, LABEL_HEIGHT + LABEL_GAP) + captions_rows * CAPTION_HEIGHT + (2 if captions_rows else 0))


def make_editor(owner):
    """The mark editor: a widget drawing the selected glyph between its neighbors, its marks clickable,
    movable, and scalable (PythonQt subclasses Qt widgets in Python; the class is made once Qt is in)."""
    QtCore, QtGui = _qt()

    class MarkEditor(QtGui.QWidget):
        def __init__(self):
            QtGui.QWidget.__init__(self)
            self.setFocusPolicy(QtCore.Qt.StrongFocus)
            self.setMouseTracking(True)
            self.setMinimumHeight(EDITOR_HEIGHT)
            self.scene = None  # set by the dialog: see AccentsDialog.scene
            self.selected = None  # the index of the selected mark
            self.drag = None
            self.view = None  # (scale, x of the origin, y of the baseline)
            # While a mark is dragged, the view stays as it was at the press (kept here: scale, x of the
            # origin, y of the baseline). The scene is made again at every move and its top follows the mark,
            # so a view refitted during a drag shrank as the mark rose; the pointer's pixels, divided by
            # that ever smaller scale, sent the mark farther at every move, without end (numbers of three
            # hundred digits, then infinity, once the pointer was farther from the press than the editor
            # is high: owner's report of 2026-11-13).
            self.held = None
            self.snapped = None  # (x in the editor's units, label) of the center a dragged mark snapped to
            self.went = False  # the last press went to a neighbor's row: its double-click opens nothing

        # -- geometry --------------------------------------------------------

        def geometry(self):
            scene = self.scene
            if self.held is not None:  # a drag is on: the view of its press
                self.view = self.held
                return self.view
            rect = _property(self, "rect")
            width, height = rect.width(), rect.height()
            total = sum(advance for _, advance, _ in scene["glyphs"]) or scene["upm"]
            top, bottom = scene["top"], scene["bottom"]
            # The lines' names and the captions get bands of their own (editor_pads), the glyphs the rest:
            # a caption at the bottom edge was drawn over the names of the lines under the glyphs
            captions = [(role, text) for _, _, role in scene["glyphs"]
                        for text in [scene.get("captions", {}).get(role)] if text]
            rows = 1 if captions else 0
            for _ in range(2):  # (two captions too wide for their glyphs take a second row)
                pad_top, pad_bottom = editor_pads(rows)
                room = max(1.0, height - pad_top - pad_bottom)
                scale = max(1e-6, min((width - 2.0 * EDGE_PAD) / total, room / float(top - bottom)))
                x0 = (width - total * scale) / 2.0
                y0 = pad_top + top * scale + (room - (top - bottom) * scale) / 2.0
                layout = self.caption_places(captions, scale, x0, width)
                needed = (max(at[4] for at in layout) + 1) if layout else 0
                if needed <= rows:
                    break
                rows = needed
            self.captions_at = layout
            self.caption_band = (rows * CAPTION_HEIGHT + 2) if rows else 0
            self.view = (scale, x0, y0)
            return scale, x0, y0

        def caption_font(self):
            """The captions' font: the editor's a tenth smaller, as the shared preview_caption makes every
            preview's caption ("Now", "Current", "Suggested": brief, owner's image 246)."""
            font = QtGui.QFont(_property(self, "font"))
            try:
                font.setPointSizeF(font.pointSizeF() * CAPTION_SCALE)
            except Exception:
                pass
            return font

        def caption_places(self, captions, scale, x0, width):
            """[(role, text, left, width, row)] of the captions, under their glyphs (caption_layout): a
            caption split there is two, its head and, a row down, its detail in parentheses."""
            try:
                metrics = QtGui.QFontMetrics(self.caption_font())  # (measured in the font they are drawn in)
            except Exception:
                metrics = None
            spans, pieces = [], []
            for role, text in captions:
                start = self.origin_of(role) or 0.0
                advance = next((a for _, a, r in self.scene["glyphs"] if r == role), 0.0)
                head, tail = split_caption(text)
                pieces.append({"whole": text, "head": head, "tail": tail})
                spans.append((x0 + (start + advance / 2.0) * scale, text_width(metrics, text) + 4.0,
                              text_width(metrics, head) + 4.0, text_width(metrics, tail) + 4.0 if tail else None))
            return [(captions[k][0], pieces[k][piece], left, wide, row)
                    for k, piece, left, wide, row in caption_layout(spans, width)]

        def origin_of(self, role):
            x = 0.0
            for _, advance, glyph_role in self.scene["glyphs"]:
                if glyph_role == role:
                    return x
                x += advance
            return None

        def to_screen(self, x, y):
            scale, x0, y0 = self.view
            return x0 + x * scale, y0 - y * scale

        def to_units(self, sx, sy):
            scale, x0, y0 = self.view
            return (sx - x0) / scale, (y0 - sy) / scale

        def mark_boxes(self):
            """[(index, (left, bottom, right, top))] of the edited glyph's marks, in the editor's units."""
            scene = self.scene
            origin = self.origin_of("new") or 0.0
            found = []
            for index, (first, last) in enumerate(scene["ranges"]):
                box = parts_box(scene["parts"][first:last], scene["ink"])
                if box is not None:
                    found.append((index, (box[0] + origin, box[1], box[2] + origin, box[3])))
            return found

        def screen_box(self, box):
            left, top = self.to_screen(box[0], box[3])
            right, bottom = self.to_screen(box[2], box[1])
            return left, top, right, bottom

        def outside(self):
            """{mark index: (x, y, across, down)} of the marks none of which shows in the editor
            (outside_view): where each one's arrow is drawn, and which way it points. {} when the editor's
            size cannot be read."""
            found = {}
            try:
                if self.scene is None:
                    return found
                rect = _property(self, "rect")
                width, height = rect.width(), rect.height()
                self.geometry()  # (the view as it will be painted: the scene may be newer than the last paint)
                for index, box in self.mark_boxes():
                    where = outside_view(self.screen_box(box), width, height)
                    if where is not None:
                        found[index] = where
            except Exception:
                return {}
            return found

        def handles(self, box):
            """{handle: (x, y)} on screen: corners tl, tr, br, bl and sides t, r, b, l."""
            left, top, right, bottom = self.screen_box(box)
            middle_x, middle_y = (left + right) / 2.0, (top + bottom) / 2.0
            return {"tl": (left, top), "tr": (right, top), "br": (right, bottom), "bl": (left, bottom),
                    "t": (middle_x, top), "r": (right, middle_y), "b": (middle_x, bottom), "l": (left, middle_y)}

        def hit(self, x, y):
            """("handle", name) of the selected mark, ("mark", index), ("glyph", role), or None."""
            if self.scene is None or self.view is None:
                return None
            boxes = dict(self.mark_boxes())
            if self.selected in boxes and not self.scene.get("move_only"):
                for name, (hx, hy) in self.handles(boxes[self.selected]).items():
                    if abs(x - hx) <= HANDLE + 2 and abs(y - hy) <= HANDLE + 2:
                        return ("handle", name)
            for index, box in sorted(boxes.items(), key=lambda item: item[0] != self.selected):
                left, top, right, bottom = self.screen_box(box)
                if left - 3 <= x <= right + 3 and top - 3 <= y <= bottom + 3:
                    return ("mark", index)
            for index, (ax, ay, _, _) in sorted(self.outside().items(), key=lambda item: item[0] != self.selected):
                if abs(x - ax) <= EDGE_MARGIN + 3 and abs(y - ay) <= EDGE_MARGIN + 3:
                    return ("mark", index)  # the arrow of a mark outside the view: a click selects the mark
            role = self.glyph_at(x, y)
            return ("glyph", role) if role is not None and role != "new" else None

        def glyph_at(self, x, y):
            """The role of the glyph whose ink is under (x, y) on screen, a few pixels around it counted; None
            for none. Its ink's box, not its advance's column from the top of the editor to its bottom: the
            letter after the edited one answered clicks far past it (owner's image 333)."""
            start = 0.0
            for parts, advance, role in self.scene["glyphs"]:
                box = parts_box(parts, self.scene["ink"])
                if box is not None:
                    left, top, right, bottom = self.screen_box((box[0] + start, box[1], box[2] + start, box[3]))
                    if left - GLYPH_HIT <= x <= right + GLYPH_HIT and top - GLYPH_HIT <= y <= bottom + GLYPH_HIT:
                        return role
                start += advance
            return None

        # -- drawing ---------------------------------------------------------

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            try:  # a paint handler must not raise, and its painter must end
                if self.scene is not None:
                    self.paint(painter)
            except Exception:
                pass
            finally:
                painter.end()

        def paint(self, painter):
            scene = self.scene
            scale, x0, y0 = self.geometry()
            palette = _property(self, "palette")
            text = palette.color(QtGui.QPalette.WindowText)
            highlight = palette.color(QtGui.QPalette.Highlight)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            faint = QtGui.QColor(text)
            faint.setAlpha(60)
            width = _property(self, "rect").width()
            painter.setPen(QtGui.QPen(faint, 1))
            painter.drawLine(QtCore.QPointF(0, y0), QtCore.QPointF(width, y0))
            painter.save()  # (its small font and dashed pens end with it)
            try:
                self.paint_limits(painter, scene, faint, width, scale, y0)
            except Exception:
                pass  # the glyph is drawn all the same
            finally:
                painter.restore()
            x = 0.0
            for parts, advance, role in scene["glyphs"]:
                ink = QtGui.QColor(text)
                if role != "new":
                    ink.setAlpha(NEIGHBOR_ALPHA)
                chosen = None  # (first, last) of the selected mark's parts
                if role == "new" and self.selected is not None and self.selected < len(scene["ranges"]):
                    chosen = scene["ranges"][self.selected]
                whole = lit = None
                if not scene.get("separate"):
                    # A glyph of components: drawn as one outline filled by nonzero winding, as a renderer
                    # draws it (a mirrored part overlapping another shows its hole here too). Glyphs set
                    # together by anchors (the Mark anchors tab's) are each drawn alone, as text is.
                    try:
                        whole = joined_path(scene["ink"], parts)
                        if chosen is not None:  # the selected mark's ink, where the glyph has ink
                            lit = whole.intersected(joined_path(scene["ink"], parts[chosen[0]:chosen[1]]))
                    except Exception:
                        whole = lit = None
                if whole is not None:
                    painter.save()
                    painter.translate(x0 + x * scale, y0)
                    painter.scale(scale, -scale)
                    painter.fillPath(whole, QtGui.QBrush(ink))
                    if lit is not None:
                        painter.fillPath(lit, QtGui.QBrush(highlight))
                    painter.restore()
                for at, (glyph, sx, sy, dx, dy) in enumerate(parts if whole is None else ()):
                    path = scene["ink"].path(glyph)[0]
                    if path is None:
                        continue
                    color = highlight if chosen is not None and chosen[0] <= at < chosen[1] else ink
                    painter.save()
                    painter.translate(x0 + (x + dx) * scale, y0 - dy * scale)
                    painter.scale(scale * sx, -scale * sy)
                    painter.fillPath(path, QtGui.QBrush(color))
                    painter.restore()
                x += advance
            # The captions in their band under the glyphs and the lines' names (geometry made it)
            height = _property(self, "rect").height()
            band = getattr(self, "caption_band", 0)
            placed_captions = getattr(self, "captions_at", None) or ()
            if placed_captions:  # (smaller, in the quiet text color: as every preview's caption)
                painter.save()
                painter.setFont(self.caption_font())
                painter.setPen(QtGui.QPen(palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText)))
                for _, caption, left, wide, row in placed_captions:
                    painter.drawText(QtCore.QRectF(left, height - band + 1 + row * CAPTION_HEIGHT, wide,
                                                   CAPTION_HEIGHT), int(QtCore.Qt.AlignCenter), caption)
                painter.restore()
            if self.snapped is not None and self.drag is not None:  # the center the dragged mark snapped to
                guide = QtGui.QColor(highlight)
                guide.setAlpha(170)
                sx = x0 + self.snapped[0] * scale
                painter.setPen(QtGui.QPen(guide, 1))
                painter.drawLine(QtCore.QPointF(sx, 0), QtCore.QPointF(sx, _property(self, "rect").height()))
                painter.drawText(QtCore.QPointF(sx + 4, 12), self.snapped[1])
            boxes = dict(self.mark_boxes())
            if self.selected in boxes:
                left, top, right, bottom = self.screen_box(boxes[self.selected])
                painter.setPen(QtGui.QPen(highlight, 1, QtCore.Qt.DashLine))
                painter.setBrush(QtGui.QBrush())
                painter.drawRect(QtCore.QRectF(left, top, right - left, bottom - top))
                painter.setPen(QtGui.QPen(highlight, 1))
                painter.setBrush(QtGui.QBrush(palette.color(QtGui.QPalette.Base)))
                for hx, hy in ([] if scene.get("move_only") else self.handles(boxes[self.selected]).values()):
                    painter.drawRect(QtCore.QRectF(hx - HANDLE, hy - HANDLE, 2 * HANDLE, 2 * HANDLE))
            # A mark none of which shows (moved past what the view opens to hold): an arrow at the edge
            # nearest it, pointing to it, in the highlight color when it is the selected one
            for index, (ax, ay, across, down) in self.outside().items():
                arrow = QtGui.QPainterPath()
                reach, half = EDGE_MARGIN - 2.0, (EDGE_MARGIN - 2.0) * 0.7
                # its tip toward the mark, its base square to that direction
                tip = (ax + across * reach, ay + down * reach)
                side = (-down * half, across * half)
                arrow.moveTo(QtCore.QPointF(tip[0], tip[1]))
                arrow.lineTo(QtCore.QPointF(ax - across * reach + side[0], ay - down * reach + side[1]))
                arrow.lineTo(QtCore.QPointF(ax - across * reach - side[0], ay - down * reach - side[1]))
                arrow.closeSubpath()
                painter.fillPath(arrow, QtGui.QBrush(highlight if index == self.selected else text))

        def paint_limits(self, painter, scene, faint, width, scale, y0):
            """The font's lines (scene["limits"]: [(units, label, whether it is a limit)]; an older
            scene's "room" alone), as thin dashed lines in the faint text color, each named small at one
            end. A limit a mark crosses (Windows or macOS clips there, or the next line is met) is drawn
            in amber; a reference line (the font's ascender and descender, the typo values) never is."""
            limits = scene.get("limits")
            if limits is None:
                limits = [(value, u"", True) for value in scene.get("room", ())]
            if not limits:
                return
            crossed = crossed_limits(limits, [box for _, box in self.mark_boxes()])
            amber = QtGui.QColor(*scene.get("warning", WARNING_RGB))
            amber.setAlpha(190)
            small = None
            try:
                small = QtGui.QFont(_property(self, "font"))
                if small.pointSizeF() > 0:
                    small.setPointSizeF(max(6.0, small.pointSizeF() * 0.8))
            except Exception:
                small = None
            # Each name over its line (a line above the baseline) or under it, at either end, never over
            # another name or a caption (label_layout), measured in the small font it is drawn in
            try:
                metrics = QtGui.QFontMetrics(small) if small is not None else None
            except Exception:
                metrics = None
            place_of = self.name_places(limits, width, scale, y0, metrics)
            for at, line in enumerate(limits):
                value, label = line[0], line[1]
                y = y0 - value * scale
                color = amber if at in crossed else faint
                painter.setPen(QtGui.QPen(color, 1, QtCore.Qt.DashLine))
                painter.drawLine(QtCore.QPointF(0, y), QtCore.QPointF(width, y))
                place = place_of.get(at)
                if not label or small is None or place is None:
                    continue  # (no room left for its name: the line is drawn all the same)
                try:
                    named = QtGui.QColor(color)
                    named.setAlpha(min(255, named.alpha() + 70))
                    painter.setFont(small)
                    painter.setPen(QtGui.QPen(named))
                    left, top, wide = place
                    painter.drawText(QtCore.QRectF(left, top, wide, LABEL_HEIGHT),
                                     int(QtCore.Qt.AlignLeft) | int(QtCore.Qt.AlignVCenter), label)
                except Exception:
                    small = None  # (the lines are drawn all the same)

        def name_places(self, limits, width, scale, y0, metrics=None):
            """{line's index: (left, top, width)} of the lines' names (label_layout), between the snapped
            center's band and the captions' (geometry's caption_band); a name with no room left has none."""
            named = [(at, line) for at, line in enumerate(limits) if line[1]]
            height = _property(self, "rect").height()
            places = label_layout([(y0 - line[0] * scale, line[0] > 0, text_width(metrics, line[1]) + 2.0)
                                   for _, line in named], width, SNAP_BAND,
                                  height - getattr(self, "caption_band", 0) - 1)
            return dict((at, place) for (at, _), place in zip(named, places) if place is not None)

        # -- the mouse and the keys ---------------------------------------------

        def mousePressEvent(self, event):
            try:
                if event.button() != QtCore.Qt.LeftButton:
                    return
                self.setFocus()
                self.went = False
                pos = event.pos()
                found = self.hit(pos.x(), pos.y())
                if found is None:
                    self.select(None)
                    return
                kind, what = found
                if kind == "glyph":
                    # A letter beside the edited glyph: a double-click goes to its row (mouseDoubleClickEvent),
                    # never one click, which went there on a misclick (owner's image 333)
                    self.select(None)
                    return
                if kind == "mark":
                    self.select(what)
                    box = dict(self.mark_boxes()).get(what)
                    center = (box[0] + box[2]) / 2.0 if box else None
                    self.drag = ("move", pos.x(), pos.y(), list(owner.adjust_of(what)), center)
                else:
                    box = dict(self.mark_boxes())[self.selected]
                    self.drag = ("scale", pos.x(), pos.y(), list(owner.adjust_of(self.selected)), (what, box))
                self.held = tuple(self.view)  # the view as it is now, for the whole drag (see self.held)
            except Exception:
                pass

        def left_held(self, event):
            """Whether the left button is down, as a move event tells; True where it does not tell."""
            try:
                return bool(int(event.buttons()) & int(QtCore.Qt.LeftButton))
            except Exception:
                return True

        def end_drag(self):
            """A drag over, wherever the pointer is when the button is let go (Qt sends the release to the
            widget the press went to, outside it too), or when a move comes with no button held (a release
            another window took): the mark's place is final, its row and the buttons follow, and the view
            is fitted again."""
            dragged, self.drag, self.held = self.drag, None, None
            try:
                if dragged is not None and self.selected is not None:
                    owner.set_adjust(self.selected, owner.adjust_of(self.selected), final=True)
            except Exception:
                pass
            self.snapped = None
            if dragged is not None:
                self.update()

        def mouseMoveEvent(self, event):
            try:
                pos = event.pos()
                if self.drag is not None and not self.left_held(event):
                    self.end_drag()  # its release was lost: the drag ends here, not at the next click
                if self.drag is None:
                    found = self.hit(pos.x(), pos.y())
                    shapes = {"tl": QtCore.Qt.SizeFDiagCursor, "br": QtCore.Qt.SizeFDiagCursor,
                              "tr": QtCore.Qt.SizeBDiagCursor, "bl": QtCore.Qt.SizeBDiagCursor,
                              "t": QtCore.Qt.SizeVerCursor, "b": QtCore.Qt.SizeVerCursor,
                              "l": QtCore.Qt.SizeHorCursor, "r": QtCore.Qt.SizeHorCursor}
                    if found is not None and found[0] == "handle":
                        self.setCursor(shapes[found[1]])
                    elif found is not None and found[0] == "mark":
                        self.setCursor(QtCore.Qt.SizeAllCursor)
                    elif (found is not None and found[0] == "glyph" and getattr(owner, "neighbor_char", None) is not None
                          and owner.neighbor_char(found[1])):
                        self.setCursor(QtCore.Qt.PointingHandCursor)  # a click goes to that letter's row
                    else:  # (nothing, or the plain letter beside it: a click does nothing there)
                        self.setCursor(QtCore.Qt.ArrowCursor)
                    return
                kind, x, y, start, extra = self.drag
                # the scale the drag began at, never one refitted since: pixels become units the same way
                # from the press to the release, however far the pointer goes
                scale = (self.held if self.held is not None else self.view)[0]
                if not scale > 0:
                    return
                shift = bool(int(event.modifiers()) & int(QtCore.Qt.ShiftModifier))
                if kind == "move":
                    dx, dy = (pos.x() - x) / scale, -(pos.y() - y) / scale
                    if shift:  # along one axis
                        if abs(dx) > abs(dy):
                            dy = 0.0
                        else:
                            dx = 0.0
                    alt = bool(int(event.modifiers()) & int(QtCore.Qt.AltModifier))
                    self.snapped = None
                    targets = getattr(owner, "snap_targets", None)
                    if extra is not None and targets is not None and not alt and not (shift and dx == 0.0):
                        origin = self.origin_of("new") or 0.0
                        found = targets(self.selected)
                        at, label = snap(extra + dx, [(x + origin, text) for x, text in found], SNAP_PIXELS / scale)
                        if at is not None:  # its center on the letter's, the guide drawn while it holds
                            dx += at - (extra + dx)
                            self.snapped = (at, label)
                    owner.set_adjust(self.selected, [start[0] + dx, start[1] + dy, start[2], start[3]], final=False)
                else:
                    handle, box = extra
                    owner.set_adjust(self.selected, self.scaled(handle, box, start, pos, shift), final=False)
            except Exception:
                pass

        def scaled(self, handle, box, start, pos, shift):
            """The adjustment for a frame's handle dragged to pos: the opposite corner or side stays."""
            left, bottom, right, top = box
            view_scale, x0, y0 = self.held if self.held is not None else self.view  # (the press's view)
            ux, uy = (pos.x() - x0) / view_scale, (y0 - pos.y()) / view_scale
            kx = ky = 1.0
            fixed_x = right if "l" in handle else left
            fixed_y = bottom if "t" in handle else top
            if "l" in handle or "r" in handle:
                moving = left if "l" in handle else right
                kx = (ux - fixed_x) / (moving - fixed_x) if moving != fixed_x else 1.0
            if "t" in handle or "b" in handle:
                moving = top if "t" in handle else bottom
                ky = (uy - fixed_y) / (moving - fixed_y) if moving != fixed_y else 1.0
            if shift and len(handle) == 2:
                kx = ky = max(kx, ky)
            low, high = SCALE_REACH
            kx, ky = min(high, max(low, kx)), min(high, max(low, ky))
            # the box's center now, and after: the fixed side stays where it is
            cx, cy = (left + right) / 2.0, (bottom + top) / 2.0
            new_cx = fixed_x + (cx - fixed_x) * kx if ("l" in handle or "r" in handle) else cx
            new_cy = fixed_y + (cy - fixed_y) * ky if ("t" in handle or "b" in handle) else cy
            return [start[0] + new_cx - cx, start[1] + new_cy - cy, start[2] * kx, start[3] * ky]

        def mouseReleaseEvent(self, event):
            try:
                self.end_drag()
            except Exception:
                self.drag = self.held = None

        def mouseDoubleClickEvent(self, event):
            """A double-click on the letter with diacritics beside the edited glyph goes to its row and its
            preview (neighbor_clicked: the plain letter before it has no marks to place, and goes nowhere); on
            the edited glyph or one of its marks, opens it in a Glyph window (Letters with diacritics: the
            built glyph, else its letter). Elsewhere nothing: both took one click, or a click beside the
            glyphs, and a misclick went somewhere (owner's image 333)."""
            try:
                if event.button() != QtCore.Qt.LeftButton:
                    return
                x, y = event.pos().x(), event.pos().y()
                found = self.hit(x, y)
                self.drag = self.held = None
                if found is not None and found[0] == "glyph":
                    go = getattr(owner, "neighbor_clicked", None)
                    if go is not None:
                        go(found[1])
                    return
                if found is None and self.glyph_at(x, y) != "new":
                    return
                opened = getattr(owner, "editor_double_clicked", None) or getattr(owner, "show_in_glyph_window", None)
                if opened is not None:
                    opened()
            except Exception:
                pass

        def keyPressEvent(self, event):
            try:
                key = event.key()
                shift = bool(int(event.modifiers()) & int(QtCore.Qt.ShiftModifier))
                step = 10.0 if shift else 1.0
                moves = {QtCore.Qt.Key_Left: (-step, 0), QtCore.Qt.Key_Right: (step, 0),
                         QtCore.Qt.Key_Up: (0, step), QtCore.Qt.Key_Down: (0, -step)}
                count = len(self.scene["ranges"]) if self.scene else 0
                if key in moves and self.selected is not None:
                    dx, dy = moves[key]
                    change = list(owner.adjust_of(self.selected))
                    owner.set_adjust(self.selected, [change[0] + dx, change[1] + dy, change[2], change[3]], final=True)
                elif key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab) and count:
                    current = -1 if self.selected is None else self.selected
                    self.select((current + (1 if key == QtCore.Qt.Key_Tab else -1)) % count)
                elif key in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete) and self.selected is not None:
                    owner.set_adjust(self.selected, [0.0, 0.0, 1.0, 1.0], final=True)
                elif key == QtCore.Qt.Key_Escape:
                    self.select(None)
                else:
                    event.ignore()
                    return
                event.accept()
            except Exception:
                pass

        def focusNextPrevChild(self, forward):
            return False  # Tab selects the next mark instead of the next control

        def select(self, index):
            self.selected = index
            owner.mark_selected(index)
            self.update()

    return MarkEditor()


ANCHOR_HELP_NOTE = (u"Moving the sample mark moves the selected glyph's anchor: a base's anchor where the mark should "
                    u"sit, a mark's own so it sits as shown.")


def anchor_cells(g):
    """(Anchors to add, Note): the Mark anchors list's two text cells for a row (an AnchorGlyph or a Rule),
    as short notes: no period, pieces of data apart by commas and semicolons, a feature in parentheses."""
    if g.role == "rule":
        return g.line, u"%s (%s)" % (g.text[:1].upper() + g.text[1:], g.feature)
    placed = g.placed()
    anchors = u", ".join([u"%s %d %d" % (name, placed[name][0], placed[name][1]) for name in sorted(g.anchors)] +
                         [u"%s moved to %d %d" % (name, placed[name][0], placed[name][1]) for name in g.moved()])
    notes = []
    if g.role == "ligature":
        notes.append(u"joins %d letters" % max(g.parts, 2))
    if g.role == "reph":
        notes.append(u"the reph: every base gets its anchor")
    if g.existing:
        notes.append(u"has %s already" % u", ".join(sorted(g.existing)))
    if g.adjust:
        notes.append(u"moved by hand")
    if g.elsewhere:
        notes.append(u"anchors to add in another master")
    if g.role == "mark" and g.side:
        notes.insert(0, ANCHOR_SIDE_WORDS.get(g.side, g.side))
    return anchors, u"; ".join(notes)


class AnchorPage(object):
    """The Mark anchors tab: anchors for a script's bases and marks, and the mark and mkmk code that
    attaches them, for scripts whose marks the font's features place (Khmer, Thai, Arabic, Hebrew,
    Devanagari, Bengali, Gujarati, Tamil, and the combining marks of any script)."""
    COLUMNS = ("Glyph", "Name", "Anchors to add", "Note")

    def __init__(self, owner):
        QtCore, QtGui = _qt()
        self.owner, self.ak, self.fontlab = owner, owner.ak, owner.fontlab
        ak = self.ak
        self.widget = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        self.status.setWhatsThis(u"What the list holds for this font, master, and script: its bases and marks, how "
                                 u"many get anchors, and whose placements the anchors follow.")
        add_status = getattr(owner, "add_status", None)  # (under the window's top line: owner's image 265)
        if add_status is not None:
            add_status(self.status, "anchors")
        else:
            layout.addWidget(self.status)
        row = QtGui.QHBoxLayout()
        script_help = u"The script whose bases and marks get anchors: those the font has marks of."
        self.script_label = helped(QtGui.QLabel(u"Script:"), script_help)
        row.addWidget(self.script_label)
        self.script_box = QtGui.QComboBox()
        self.script_box.setWhatsThis(script_help)
        row.addWidget(self.script_box)
        self.script_name = QtGui.QLabel(u"")  # in its place when the font has marks of one script only
        bold = QtGui.QFont(self.script_name.font)
        bold.setBold(True)
        self.script_name.setFont(bold)
        self.script_name.setWhatsThis(u"The script whose bases and marks get anchors: the only one the font has marks of.")
        self.script_name.hide()
        row.addWidget(self.script_name)
        fit_to_contents(self.script_box)
        # Write the feature code: the compile tick of Add ticked anchors, beside it at the bottom row's right
        # (brief 4); in this row, it stood after an empty slot where the script's name was (owner's image 248)
        self.code_box = QtGui.QCheckBox(u"Write the feature code.")
        self.code_box.setChecked(True)
        self.code_box.setWhatsThis(u"Also writes the mark and mkmk features that attach the marks by these anchors "
                                   u"(and the ticked substitutions: ccmp, pres), between FreeLab's marker lines. "
                                   u"Grayed and unticked in a font with more than one master.")
        row.addStretch(1)
        self.search, self.search_label = owner.search_field(
            FIND_A_GLYPH, u"Shows only the glyphs whose name holds this text, whose character it is (a "
                             u"character typed alone finds that glyph and its forms, such as <i>h.sc</i>), or whose "
                             u"Unicode value it is (<i>U+0E48</i>, <i>0E48</i>); anchors and notes are not searched. "
                             u"Rows not shown keep their ticks; <i>Tick all</i> and <i>Untick all</i> act on the "
                             u"rows shown.")
        row.addWidget(self.search_label)  # (left of the field: the field ends at the rows' right edge, owner's image 185)
        row.addWidget(self.search)
        layout.addLayout(row)
        self.options_row = row  # (as tall as the other tabs' rows, its dropdown hidden or not: line_up_rows)
        self.hidden = set()  # the rows a search hides, by their glyph's place in self.glyphs
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)
        ak.table_layout(self.tree)
        self.tree.setWhatsThis(u"The script's bases (top and bottom anchors) and marks (the anchor each attaches by, "
                               u"and the one the next mark attaches to). Anchors a glyph has already are kept, and "
                               u"its row names those the marks attach by. Ticked glyphs get theirs.")
        layout.addWidget(self.tree, 3)
        self.lower_line = heading_line(ak)  # (over the Reference heading: owner's images 234, 288, and 318)
        layout.addWidget(self.lower_line)
        lower = QtGui.QHBoxLayout()
        reference_help = (u"The selected glyph's letter carrying the sample marks at once (below, above, and, "
                          u"where marks stack, a second mark above), then with each side mark; or the "
                          u"selected mark on the sample letter, alone and with another mark on it. In the "
                          u"reference font (its own marks placed by its own features), to compare. An "
                          u"example the font cannot draw with its marks on the letter is shown with one "
                          u"mark fewer, or left out, and the line under the picture says so.")
        # (the first tab's reference section, its choice shown here too: one for every tab)
        (reference, self.reference_title, self.reference_font, self.reference, self.reference_note,
         self.reference_line) = owner.reference_section(
            reference_help, REFERENCE_NOTE_HELP + u" It also says which examples are shown with a mark fewer or "
                                                  u"left out.")
        lower.addLayout(reference)
        lower.addWidget(self.reference_line)  # (owner's image 251)
        editing = QtGui.QVBoxLayout()
        self.editor = make_editor(self)
        self.editor.setProperty(ak.LEAVE_ALONE_PROP, True)
        self.editor.setWhatsThis(u"The selected glyph with a mark attached by its anchors. " + ANCHOR_HELP_NOTE +
                                 u" Drag the mark or press the arrow keys (<i>Shift</i>: 10 units). A mark is drawn "
                                 u"with another mark on it too: moving that one moves the anchor the next mark "
                                 u"attaches to (mark to mark). A letter that stacks marks (Vietnamese's, Thai's) is "
                                 u"drawn with a second mark on its mark above, which follows the first. " + LINES_HELP +
                                 u" A mark moved out of the picture is shown by an arrow at the edge.")
        editing.addWidget(self.editor, 1)
        lower.addLayout(editing, 1)
        hint_row = QtGui.QHBoxLayout()
        self.hint = helped(QtGui.QLabel(ANCHOR_HELP_NOTE), u"What moving the sample mark does, and, once a mark is "
                           u"selected, where the anchor it moves stands.")
        self.hint.setWordWrap(True)
        hint_row.addWidget(self.hint, 1)
        self.reset_button = QtGui.QPushButton(u"Reset anchors")
        self.reset_button.setWhatsThis(u"Puts the selected glyph's anchors back where they were suggested.")
        hint_row.addWidget(self.reset_button)
        editing.addLayout(hint_row)
        layout.addLayout(lower, 2)
        self.all_button = helped(QtGui.QPushButton(TICK_ALL), u"Ticks every glyph shown that has anchors to "
                                 u"add (rows a search hides keep their ticks).")
        self.none_button = helped(QtGui.QPushButton(TICK_NONE), u"Unticks every glyph shown, so that it gets no "
                                  u"anchor (rows a search hides keep their ticks).")
        self.restore_button = QtGui.QPushButton(u"Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every tick and every anchor moved by hand back as the list first came.")
        self.write_button = QtGui.QPushButton(ADD_TICKED_ANCHORS)
        self.write_button.setWhatsThis(u"Adds the ticked glyphs' anchors in every master, each measured on its own, and "
                                       u"writes the mark and mkmk code when asked. <i>Edit &gt; Undo</i> takes it back.")
        bottom = getattr(owner, "bottom_row", None)  # (the window's bottom row: brief 4)
        if bottom is not None:
            left, right = bottom("anchors")
        else:
            left = right = QtGui.QHBoxLayout()
            layout.addLayout(left)
        for button in (self.all_button, self.none_button, self.restore_button):
            left.addWidget(button)
        right.addWidget(self.code_box)
        right.addWidget(self.write_button)
        self.script_box.connect("currentIndexChanged(int)", lambda index: self.run(keep_script=True))
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.reset_button.connect("clicked()", self.reset_anchors)
        self.write_button.connect("clicked()", self.write)
        self.code_box.connect("toggled(bool)", lambda on: self.update_buttons())
        self.tree.connect("itemSelectionChanged()", self.select)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        self.search.connect("textChanged(QString)", lambda text: self.searched())
        self.glyphs, self.first_checks, self.texts, self.names = [], {}, {}, []
        self.package = self.master = None
        self.model = load_anchor_model()
        self.ink = None
        self.buttons_due = False
        self.loading = False
        self.scripts = []
        self.show_scripts()  # (until the list is read: no script, nothing selected, nothing shown empty)
        self.show_preview(False, False)

    # -- the font --------------------------------------------------------------------

    def scripts_present(self, package):
        """The scripts the font has marks of, in ANCHOR_SCRIPTS' order."""
        found = set()
        main_code = self.ak.main_code  # (the code a glyph stands for: not a radical FontLab gives first)
        for fg in package.fgPackage.glyphs:
            code = main_code(fg)
            if code and unicodedata.category(unichr_(code)) in ("Mn", "Me"):
                script = anchor_script(code)
                if script:
                    found.add(script)
        return [script for script, _ in ANCHOR_SCRIPTS if script in found]

    def collect(self, package, master, script, ink):
        """[(name, code, role, Ink, existing anchors)] of the script's bases and marks: encoded letters that
        take marks (base_letters) and marks, and their unencoded forms (beh-ar.init, ka-khmer.sub, i.2) by
        the name before the period."""
        roles = {}
        takes_marks = base_letters(script, self.model)
        self.left_out = 0
        # (the code each glyph stands for, read once: not a Kangxi radical FontLab may give first)
        codes = dict((fg.name, self.ak.main_code(fg)) for fg in package.fgPackage.glyphs)
        arabic_names = set(name for name, code in codes.items() if code and anchor_script(code) == "arabic")
        for fg in package.fgPackage.glyphs:
            code = codes.get(fg.name)
            if code and anchor_script(code) == script:
                category = unicodedata.category(unichr_(code))
                if code in DOUBLE_MARKS:
                    continue  # (a mark across two letters, never one letter's: owner's image 354, a CJK font's
                    # one Latin mark, U+0361, drawn as the sample over every letter and placing their anchors)
                if category in ("Mn", "Me"):
                    roles[fg.name] = ("mark", code, 0)
                elif category.startswith("L"):
                    parts = ligature_parts(fg.name, code, arabic_names) if script == "arabic" else 0
                    if parts:
                        roles[fg.name] = ("ligature", code, parts)
                        continue
                    if takes_marks is not None and code not in takes_marks:
                        self.left_out += 1
                        continue
                    roles[fg.name] = ("base", code, 0)
        found = []
        for fg in package.fgPackage.glyphs:
            code = codes.get(fg.name)
            role = roles.get(fg.name) or (roles.get(fg.name.split(u".")[0]) if not code else None)
            if role is None and not code:
                if script == "arabic":
                    parts = ligature_parts(fg.name, 0, arabic_names)
                    role = ("ligature", 0, parts) if parts else None
                elif script in REPH_SCRIPTS and is_reph(fg.name, script):
                    role = ("reph", 0, 0)
            if role is None:
                continue
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            existing = {}
            try:
                for anchor in layer.anchors:
                    existing[u"%s" % anchor.name] = (anchor.point.x(), anchor.point.y())
            except Exception:
                pass
            found.append((fg.name, code or role[1], role[0], ink(fg.name), existing, role[2]))
        return found

    def rules_for(self, script, ink):
        """The substitutions the font's own forms allow (Thai's smaller and shortened forms, the i-matras
        of Devanagari, Bengali, and Gujarati), as Rules."""
        package = self.package
        names_by_code = self.ak.glyph_code_map(package.fgPackage.glyphs)  # (every code point of each glyph)
        names = set(fg.name for fg in package.fgPackage.glyphs)
        if script == "thai":
            return thai_rules(names_by_code, names)
        if script in I_MATRAS:
            def reach_of(name):
                found = ink(name)
                advance = ink.path(name)[1]
                return found.right - advance if found is not None else None

            def advance_of(name):
                return ink.path(name)[1] or None
            return i_matra_rules(names_by_code, names, reach_of, advance_of, self.model, script)
        return []

    def plan_for(self, master):
        package = self.package
        ink = FontLabInk(self.ak, package, master)
        x_height = getattr(package, "xHeight_value", 0) or 0.5 * package.upm
        script = self.script()
        return plan_anchors(self.collect(package, master, script, ink), self.model, script, package.upm, x_height), ink

    def script(self):
        return self.scripts[self.script_box.currentIndex] if self.scripts and self.script_box.currentIndex >= 0 else "latin"

    def run(self, keep_script=False):
        QtCore, QtGui = _qt()
        if self.loading:
            return
        kept = dict((g.name, (g.checked, dict(g.adjust))) for g in self.glyphs)
        old_key = self.owner.package_key(self.package)
        package = self.package = self.owner.current_font()
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.glyphs = []
        say_font = getattr(self.owner, "say_font", None)  # (the window's top line: this font, or none)
        if say_font is not None:
            say_font(package)
        if package is None:
            self.scripts = []
            self.show_scripts()
            self.status.setText(u"")  # (the window's top line says there is no font, beside the "?")
            self.select()  # (nothing selected: the preview's parts hidden, the buttons grayed)
            return
        self.master = package.master
        self.anchors_stopped = False
        owner = self.owner
        work = getattr(owner, "work_begin", None)
        stopped = owner.stopped_error() if work is not None else NotStopped
        try:  # (read in the window's top row, stoppable: owner's image 176)
            if work is not None:
                work(u"Reading the font's marks")
            self.read_marks(package, keep_script, kept, old_key)
        except stopped:
            self.tree.clear()
            self.glyphs = []
            self.status.setText(u"Stopped while reading the font's marks: nothing is listed. Come back to this tab "
                                u"to read them again.")
            owner.log.add(u"Stopped reading the font's marks: nothing is listed.")
            self.anchors_stopped = True
            self.select()
        finally:
            if work is not None:
                owner.work_end()

    def read_marks(self, package, keep_script, kept, old_key):
        """run's work, in the window's top row: the font's scripts, each master's plan, the list."""
        ak = self.ak
        progress = getattr(self.owner, "work_progress", lambda *args, **kwargs: None)
        if not keep_script:
            self.loading = True
            self.scripts = self.scripts_present(package)
            self.script_box.clear()
            for script in self.scripts:
                self.script_box.addItem(script.capitalize())
            self.show_scripts()
            self.loading = False
        if not self.scripts:  # (the top line names the font)
            self.status.setText(u"The font has no combining marks (Unicode's nonspacing marks): nothing to attach.")
            self.select()
            return
        masters = list(package.masters)
        progress(u"Placing the anchors", 0.2)
        self.glyphs, self.ink = self.plan_for(self.master)
        left_out = getattr(self, "left_out", 0)
        elsewhere = set()  # the glyphs with anchors to add in another master (Bold lacking what Regular has)
        for at, master in enumerate(masters):
            progress(None, 0.2 + 0.6 * at / float(len(masters) or 1))
            if master != self.master:
                elsewhere.update(g.name for g in self.plan_for(master)[0] if g.anchors)
        progress(u"Listing the glyphs", 0.8)
        self.left_out = left_out
        self.glyphs = self.glyphs + self.rules_for(self.script(), self.ink)
        for g in self.glyphs:
            if g.role != "rule" and g.name in elsewhere:
                g.elsewhere = g.checked = True
        if old_key is not None and self.owner.package_key(package) == old_key:  # the same font: checks and moves carry over
            for g in self.glyphs:
                if g.name in kept:
                    g.checked, g.adjust = kept[g.name][0], kept[g.name][1]
        self.first_checks = dict((g.name, g.checked) for g in self.glyphs)
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        self.names = [g.name for g in package.fgPackage.glyphs]
        self.code_box.setChecked(package.mastersCount == 1 and self.code_box.checked)
        ak.enable(self.code_box, package.mastersCount == 1)  # (never over the grayed state of a window with no font)
        self.fill()
        bases = [g for g in self.glyphs if g.role == "base"]
        marks = [g for g in self.glyphs if g.role in ("mark", "reph")]
        others = [counted(n, one, many) for n, one, many in (
            (sum(1 for g in self.glyphs if g.role == "ligature"), u"ligature", None),
            (sum(1 for g in self.glyphs if g.role == "rule"), u"substitution", None)) if n]
        b = ak.b
        rows = self.model.get("anchors", {}).get(u"%s top" % self.script(), {})
        left_out = getattr(self, "left_out", 0)
        getting = sum(1 for g in self.glyphs if g.anchors or getattr(g, "elsewhere", False))
        fonts = rows.get("fonts", 0)
        self.status.setText(anchors_status(self.script().capitalize(), len(bases), len(marks), others, getting,
                                           fonts, left_out, package.mastersCount > 1, b, ak.i))
        # The list is new and nothing in it is selected: the preview as such (it kept the reference
        # heading, its chooser, and the editor over an empty area, or a glyph no longer selected)
        self.select()

    def show_scripts(self):
        """The script's chooser where the font has marks of several scripts, its name alone for one, and
        neither (nor the Script: label) for none or no font."""
        count = len(getattr(self, "scripts", None) or [])
        self.script_label.setVisible(count > 0)
        self.script_box.setVisible(count > 1)
        self.script_name.setVisible(count == 1)
        self.script_name.setText(self.scripts[0].capitalize() if count == 1 else u"")

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        for roles, title in ((("base",), u"Bases"), (("ligature",), u"Ligatures"), (("mark", "reph"), u"Marks"),
                             (("rule",), u"Substitutions")):
            members = [(index, g) for index, g in enumerate(self.glyphs) if g.role in roles]
            if not members:
                continue
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (title, len(members))])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            parents = {}
            if roles == ("base",) and self.script() in COMPOSED_SCRIPTS:  # by the marks each takes
                groups = {}
                for index, g in members:
                    groups.setdefault(base_group(g), []).append(index)
                for label in BASE_GROUP_ORDER:
                    if label in groups:
                        section = QtGui.QTreeWidgetItem([u"%s (%d)" % (label, len(groups[label]))])
                        section.setData(0, QtCore.Qt.UserRole, -1)
                        top.addChild(section)
                        section.setFirstColumnSpanned(True)
                        self.ak.section_row(section, self.tree)
                        section.setExpanded(True)
                        for index in groups[label]:
                            parents[index] = section
            for index, g in members:
                item = QtGui.QTreeWidgetItem([unichr_(g.code) if g.code else u"", g.name, u"", u""])
                item.setData(0, QtCore.Qt.UserRole, index)
                chars = getattr(self.owner, "char_font", None)  # (in FreeLang: owner's images 316 and 317)
                item.setFont(0, chars(bold, unichr_(g.code) if g.code else u"") if chars is not None else bold)
                if g.anchors or g.existing or g.role == "rule" or g.elsewhere:  # (its own anchors can be moved and written)
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(0, QtCore.Qt.Checked if g.checked else QtCore.Qt.Unchecked)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.refresh_item(item, g)
                parents.get(index, top).addChild(item)
            top.setExpanded(True)
        fit_tree_columns(self.tree, len(self.COLUMNS) - 1)
        self.tree.blockSignals(False)
        self.apply_search()  # (and the buttons)

    def searched(self):
        try:  # (a signal's handler: nothing may escape to Qt)
            self.apply_search()
        except Exception as exc:
            self.owner.log.add(u"Could not search the list: %s" % self.ak.html(exc), "error")

    def apply_search(self):
        """The rows the search field's text does not find hidden (their checks kept: a row is hidden, not
        taken out), a section with none left hidden with them; the count beside the field."""
        QtCore, QtGui = _qt()
        self.hidden = set()
        if getattr(self, "search", None) is None:
            self.update_buttons()
            return
        query = u"%s" % (_property(self.search, "text") or u"")
        total = [0, 0]  # rows shown, rows

        def visit(item):
            """Whether the row, or a row under it, is shown."""
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.glyphs):
                g = self.glyphs[index]
                # the glyph only: never its anchors or its note ("has bottom, top already" held every letter)
                found = row_matches(query, g.name, unichr_(g.code) if getattr(g, "code", 0) else u"",
                                    getattr(g, "code", 0))
                total[1] += 1
                total[0] += 1 if found else 0
                if not found:
                    self.hidden.add(index)
            else:
                found = any([visit(item.child(child)) for child in range(item.childCount())])
            item.setHidden(not found)
            return found

        try:
            for row in range(self.tree.topLevelItemCount):
                visit(self.tree.topLevelItem(row))
            self.count_args = (total[0], total[1], query, False)  # (update_buttons adds the ticks hidden)
            show_count(self.search_label, search_count(total[0], total[1], query))
        except Exception as exc:  # (rows that cannot be hidden: every one counts as shown, and the list still fills)
            self.hidden = set()
            show_count(self.search_label, u"")
            if not getattr(self, "search_failed", False):  # said once, not at every keystroke
                self.search_failed = True
                self.owner.log.add(u"The search could not hide rows: %s" % self.ak.html(exc), "error")
        self.update_buttons()

    def refresh_item(self, item, g):
        QtCore, QtGui = _qt()
        anchors, note = anchor_cells(g)
        item.setText(2, anchors)
        item.setText(3, note)
        g.cell = u"%s %s" % (anchors, note)
        icon = self.owner_picture(g)
        if icon is not None:
            item.setIcon(0, self.ak.icon_of(icon))  # (in one color: redrawn in the new one when dark mode switches)

    def owner_picture(self, g):
        """The glyph alone, in the dialog's text color."""
        QtCore, QtGui = _qt()
        path, advance = self.ink.path(g.name)
        if path is None:
            return None
        size = ICON_SIZE
        scale = float(size) / float(self.package.upm)
        box = path.boundingRect()
        pixmap = QtGui.QPixmap(max(int(max(advance, box.right()) * scale - min(0, box.left()) * scale) + 8, 8), int(size * 1.45))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pixmap)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(4 - min(0, box.left()) * scale, size * 1.1)
            painter.scale(scale, -scale)
            color = self.owner.dialog.palette.color(QtGui.QPalette.WindowText)
            painter.fillPath(path, QtGui.QBrush(color))
        finally:
            painter.end()
        return self.ak.inked(pixmap, color)

    def items(self):
        """Every row under the top sections, at any depth (the Bases' own sections and their letters)."""
        found = []
        pending = [self.tree.topLevelItem(row) for row in range(self.tree.topLevelItemCount)]
        while pending:
            item = pending.pop(0)
            for child in range(item.childCount()):
                found.append(item.child(child))
                pending.append(item.child(child))
        return found

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.glyphs) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                self.glyphs[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        """The rows shown checked or unchecked, and the log says how many (checks_text): the glyphs (and rules)
        whose check changed, read from the list before and after, never its rows: "Checked 80 glyphs (78 checked
        in all)" counted rows that are no glyph's (live 2026-11-16)."""
        QtCore, QtGui = _qt()
        hidden = getattr(self, "hidden", ())
        state = QtCore.Qt.Checked if on else QtCore.Qt.Unchecked
        self.harvest()
        before = set(index for index, g in enumerate(self.glyphs) if g.checked)
        self.tree.blockSignals(True)
        try:
            for item in self.items():
                if item.flags() & QtCore.Qt.ItemIsUserCheckable and int(item.data(0, QtCore.Qt.UserRole)) not in hidden:
                    if item.checkState(0) != state:  # (the rows shown only)
                        item.setCheckState(0, state)
        finally:
            self.tree.blockSignals(False)
        self.update_buttons()
        self.harvest()
        checked = [index for index, g in enumerate(self.glyphs) if g.checked]
        changed = len(set(checked) - before) if on else len(before - set(checked))
        noun = u"row" if any(g.role == "rule" for g in self.glyphs) else u"glyph"  # (substitutions are no glyphs)
        self.owner.log.add(checks_text(on, changed, len(checked), sum(1 for index in checked if index in hidden),
                                       self.ak.b, noun))

    def changed(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        QtCore, QtGui = _qt()
        self.buttons_due = False
        ak = self.ak
        self.harvest()
        hidden = getattr(self, "hidden", ())
        checkable = [g for index, g in enumerate(self.glyphs)
                     if (g.anchors or getattr(g, "elsewhere", False)) and index not in hidden]  # (the rows shown)
        ak.enable(self.all_button, any(not g.checked for g in checkable))
        ak.enable(self.none_button, any(g.checked for g in checkable))
        ak.enable(self.write_button, any(g.checked and (g.pending() or g.role == "rule") for g in self.glyphs))
        # it writes every checked glyph, those a search hides too: the count beside the search says how many are
        # not shown (build_text)
        writing = [index for index, g in enumerate(self.glyphs) if g.checked and g.pending() and g.role != "rule"]
        self.write_button.setText(anchors_button_text(len(writing), 0))
        args = getattr(self, "count_args", None)
        if args is not None and getattr(self, "search_label", None) is not None:
            show_count(self.search_label, search_count(args[0], args[1], args[2], filtered=args[3],
                                                       ticked_hidden=sum(1 for index in writing if index in hidden)))
        ak.enable(self.restore_button, any(g.adjust or self.first_checks.get(g.name, g.checked) != g.checked
                                           for g in self.glyphs))
        g = self.selected()
        ak.enable(self.reset_button, g is not None and bool(g.adjust))
        # Write the feature code: for a font of one master with a list to write; the search, with rows
        package = getattr(self, "package", None)
        search = getattr(self, "search", None)
        controls = list_controls(package is not None and bool(self.glyphs), len(self.glyphs),
                                 search is not None and bool(u"%s" % (_property(search, "text") or u"")))
        try:
            one_master = package is not None and package.mastersCount == 1
        except Exception:
            one_master = False
        ak.enable(getattr(self, "code_box", None), controls["choices"] and one_master)
        ak.enable(search, controls["search"])

    def restore(self):
        for g in self.glyphs:
            g.adjust = {}
            g.checked = self.first_checks.get(g.name, g.checked)
        self.fill()
        self.select()
        self.owner.log.add(u"Anchor ticks and positions restored as suggested.")

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.glyphs[index] if 0 <= index < len(self.glyphs) else None

    def row_names(self, item):
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return [self.glyphs[index].name] if 0 <= index < len(self.glyphs) else []

    # -- the editor: a sample mark attached ---------------------------------------------

    def samples(self, g):
        """The glyphs drawn with g: for a base, a mark above and one below (and the reph); for a
        ligature, a mark above and one below on each of its letters (anchor top_1, bottom_1, ...); for
        a mark (the reph), a base."""
        if g.role in ("base", "ligature"):
            found = []
            sides = ["top", "bottom"]
            if g.role == "base":  # and the other sides its marks take (Hebrew's dagesh, holam), and the reph
                sides += sorted(set(m.side for m in self.glyphs if m.role == "mark" and m.side in SIDE_FAMILY
                                    and m.side in g.placed())) + ["reph"]
            for side in sides:
                mark = self.sample_mark(side)
                if g.role == "ligature":
                    found.extend((u"%s_%d" % (side, part), mark) for part in range(1, max(g.parts, 2) + 1))
                else:
                    found.append((side, mark))
            return found
        if g.role == "rule":
            return []
        side = self.attach_side(g)
        base = next((b for b in self.glyphs if b.role == "base" and b.code and side in b.placed()), None)
        return [(side, base)]

    def hang_point(self, m, side):
        """Where a mark hangs on a letter's anchor of that side: its own attaching anchor (_top), else
        where that anchor would be (AnchorGlyph.hang: a mark the font attaches by anchors of its own,
        Noto Sans's _t.cyrillicbreve, is drawn as it would sit on the anchor shown), else None."""
        if m is None:
            return None
        return m.placed().get(u"_" + side) or (m.hang.get(side) if side == m.side else None)

    def sample_mark(self, side):
        """The mark drawn on a letter's anchor of that side: a representative one, as a reader knows it
        (REPRESENTATIVE_MARKS in Latin, Greek, and Cyrillic: a circumflex above, a dot below, the ogonek,
        the horn), then the script's sample, then any of that side, those encoded and unsuffixed first.
        It used to be the first mark in the font's order with an anchor _top of its own, which in a font
        whose marks attach by anchors of other names was an odd one (Noto Sans's U+031A, a right angle,
        over every letter, and no mark below or ogonek at all: the owner's report of 2026-11-15)."""
        marks = [m for m in self.glyphs if m.role in ("mark", "reph") and m.side == side
                 and self.hang_point(m, side) is not None]
        if not marks:
            return None
        try:
            script = self.script()
        except Exception:
            script = None
        wanted = list(REPRESENTATIVE_MARKS.get(side, ())) if script in COMPOSED_SCRIPTS else []
        sample = SAMPLE_MARKS.get(script, {}).get(side)
        if sample:
            wanted.append(sample)
        for code in wanted:
            found = [m for m in marks if m.code == code]
            if found:
                return sorted(found, key=lambda m: u"." in m.name)[0]
        plain = [m for m in marks if m.code and u"." not in m.name]
        return (plain or marks)[0]

    def shows_stack(self, g):
        """Whether a base is drawn with a second mark on its mark above: a letter whose precomposed forms
        stack marks (Vietnamese's), and any letter of a script that composes none (Thai's tone over a vowel)."""
        if g.role != "base":
            return False
        if g.stacks:
            return True
        try:
            return self.script() not in COMPOSED_SCRIPTS
        except Exception:
            return False

    def stack_mark(self, under):
        """The mark drawn on another to show marks stacking (mark to mark), or None when that one has no
        anchor for the next: a mark of the same side, the script's sample first (an acute on a circumflex),
        else the same mark again."""
        side = under.side
        if under.role != "mark" or side not in ("top", "bottom") or side not in under.placed():
            return None
        choices = [m for m in self.glyphs if m.role == "mark" and m.side == side and self.hang_point(m, side) is not None]
        if not choices:
            return None
        try:
            sample = SAMPLE_MARKS.get(self.script(), {}).get(side)
        except Exception:
            sample = None
        others = [m for m in choices if m is not under]
        return next((m for m in others if m.code == sample), None) or (others[0] if others else choices[0])

    def attach_side(self, g):
        """The side a mark (the reph) attaches by: its class's, else that of an attaching anchor of its own
        that a letter has (an ogonek kept on its _bottom gets no _ogonek; Noto Sans's comma below hangs on
        its _m.uni0326, which letters have), else its class's again, hung where its anchor would be
        (hang_point). A mark whose own anchors no letter has was drawn alone on a dotted circle (Noto
        Sans's U+0326, by its _b.uni0326, while U+0309 sat on A: the owner's report of 2026-11-15)."""
        placed = g.placed()
        if g.side is None or (u"_" + g.side) in placed:
            return g.side
        own = sorted(name[1:] for name in placed if name.startswith(u"_"))
        letters = [b.placed() for b in self.glyphs if b.role == "base" and b.code]
        for name in own:
            if any(name in anchors for anchors in letters):
                return name
        if g.side in g.hang:
            return g.side
        return own[0] if own else g.side

    def show_preview(self, selected, placed):
        """The preview's parts shown only where they show something: the reference (heading, chooser,
        picture, note) while a row is selected, the editor, the line under it, and Reset anchors while the
        selected glyph is drawn with a mark (placed). Nothing selected: none (they showed empty)."""
        for widget, on in ((self.reference_title, selected), (self.reference_font, selected), (self.reference, selected),
                           (self.reference_note, selected), (getattr(self, "reference_line", None), selected),
                           (getattr(self, "lower_line", None), selected),
                           (self.editor, placed), (self.hint, placed), (self.reset_button, placed)):
            if widget is not None:
                widget.setVisible(on)

    def select(self):
        try:
            g = self.selected()
            self.editor.selected = None
            self.editor.scene = self.scene(g) if g is not None else None
            self.show_preview(g is not None, self.editor.scene is not None)
            self.editor.update()
            self.hint.setText(ANCHOR_HELP_NOTE)
            self.draw_reference(g)
            self.update_buttons()
        except Exception as exc:  # (a slot's: nothing may escape to Qt)
            self.owner.log.add(u"Could not show that glyph: %s" % self.ak.html(exc), "error")

    def reference_text(self, g):
        """The characters the reference draws for g: for a base, its letter carrying the sample marks
        below and above at once (and, where marks stack on it, a second mark on the one above: Vietnamese's
        circumflex and acute over a dot below), then with each side mark (ogonek, horn); for a mark, the
        sample letter with it, then with another mark on it; none for a glyph of no character."""
        if g is None:
            return u""
        if g.role == "rule":
            return g.sample
        if g.role == "reph":
            ra, virama, consonant = REPH_SCRIPTS.get(self.script(), REPH_SCRIPTS["devanagari"])
            return unichr_(ra) + unichr_(virama) + unichr_(consonant)
        if not g.code:
            return u""
        if g.role == "ligature":
            return unichr_(g.code)
        code = self.ref_code
        if g.role == "base":
            placed = g.placed()
            # (only the sides the letter has an anchor for: the reference shows what the list says it takes)
            marks = [(side, m) for side, m in self.samples(g) if m is not None and code(m) and side in placed]
            if not marks:
                return unichr_(g.code)
            letter = unichr_(g.code)
            by_side = dict(marks)
            stack = [by_side[side] for side in ("bottom", "top") if side in by_side]  # (below first, as Unicode orders them)
            upper = self.stack_mark(by_side["top"]) if "top" in by_side and self.shows_stack(g) else None
            if upper is not None and code(upper):
                stack.append(upper)
            clusters = [letter + u"".join(unichr_(code(m)) for m in stack)] if stack else []
            clusters += [letter + unichr_(code(m)) for side, m in marks if side not in ("top", "bottom")]
            return u" ".join(clusters)
        if not code(g):  # (a mark drawn on the other side than its code point's, with no twin there)
            return u""
        side, base = self.samples(g)[0]
        letter = unichr_(base.code) if base is not None and base.code else unichr_(DOTTED_CIRCLE)
        text = letter + unichr_(code(g))
        upper = self.stack_mark(g)
        if upper is not None and code(upper):  # and with a mark on it: mark to mark
            text += u" " + letter + unichr_(code(g)) + unichr_(code(upper))
        return text

    def ref_code(self, m):
        """The character the reference draws for a mark glyph (reference_code: its own, else its twin of
        the side its ink is on), or None."""
        return reference_code(m.code, SIDE_FAMILY.get(m.side, m.side)) if m is not None else None

    def draw_reference(self, g):
        text = self.reference_text(g)
        if not text:
            self.reference.clear()
            if g is not None and g.code and g.role == "mark":
                self.reference_note.setText(u"%s is drawn %s, where U+%04X goes %s: no reference." % (
                    g.name, u"above" if SIDE_FAMILY.get(g.side, g.side) == "top" else u"below", g.code,
                    side_of(g.code)))
            else:
                self.reference_note.setText(u"" if g is None else u"%s is no character's glyph: no reference." % g.name)
            return
        family = chosen = None
        # Composed first (one character where Unicode has one: drawn as designed), else as written
        for wanted in (unicodedata.normalize("NFC", text), text):
            codes = [ord(c) for c in wanted if c != u" "]
            family, chosen = self.owner.reference_family(codes, script_families(self.script()))
            if family is not None:
                break
        if family is None:
            self.reference.clear()
            self.reference_note.setText(u"No reference font has %s." % text)
            return
        reduced = dropped = 0
        if g.role in ("base", "mark"):  # letters with marks: only what the font sets on the letter
            def holds(cluster):
                try:
                    return cluster_holds(family, cluster)
                except Exception:
                    return True  # (not measurable: drawn as before)
            def has(cluster):
                return all(has_character(family, ord(c)) for c in cluster)
            kept, reduced, dropped = settled_clusters(text.split(u" "), holds, has)
            text = u" ".join(kept)
        if not text:
            self.reference.clear()
            names = getattr(self.owner, "font_names", None) or {}
            self.reference_note.setText(u"%s does not set these marks on their letter: no reference." % names.get(family, family))
            return
        self.reference.setPixmap(reference_picture(text, family, self.owner.dialog.palette))
        self.reference_note.setText(reference_note(text, family, chosen, reduced, dropped,
                                                   names=getattr(self.owner, "font_names", None)))

    def scene(self, g):
        placed = g.placed()
        parts, ranges, self.edits = [], [], []
        if g.role == "rule":
            parts.append((g.name, 1.0, 1.0, 0.0, 0.0))
            advance = self.ink.path(g.name)[1]
        elif g.role in ("base", "ligature"):
            parts.append((g.name, 1.0, 1.0, 0.0, 0.0))
            for side, mark in self.samples(g):
                own = self.hang_point(mark, side.split(u"_")[0])
                if own is None or side not in placed:
                    continue
                dx, dy = placed[side][0] - own[0], placed[side][1] - own[1]
                parts.append((mark.name, 1.0, 1.0, dx, dy))
                ranges.append((len(parts) - 1, len(parts)))
                self.edits.append((g, side, 1))
                upper = self.stack_mark(mark) if side == "top" and self.shows_stack(g) else None
                if upper is not None:
                    # A second mark on the first, by the marks' own anchors: shown, not moved from here (it
                    # follows the first; its place is the first mark's anchor, moved on that mark's row)
                    on, by = mark.placed()[side], self.hang_point(upper, side)
                    parts.append((upper.name, 1.0, 1.0, dx + on[0] - by[0], dy + on[1] - by[1]))
            advance = self.ink.path(g.name)[1]
        else:
            side, base = self.samples(g)[0]
            target = base.placed().get(side) if base is not None else None
            own = placed.get(u"_" + side)
            hung = own is None  # (hung where its anchor would be: there is no anchor of its own to move)
            if hung:
                own = self.hang_point(g, side)
            if target is None or own is None:
                return None
            dx, dy = target[0] - own[0], target[1] - own[1]
            parts = [(base.name, 1.0, 1.0, 0.0, 0.0), (g.name, 1.0, 1.0, dx, dy)]
            ranges = [] if hung else [(1, 2)]
            if not hung:
                self.edits.append((g, u"_" + side, -1))
            upper = self.stack_mark(g) if side == g.side else None
            if upper is not None:
                # Another mark on it, hung on the anchor the next mark attaches to (mark to mark): dragging
                # that one moves this anchor
                on, by = placed[side], self.hang_point(upper, side)
                parts.append((upper.name, 1.0, 1.0, dx + on[0] - by[0], dy + on[1] - by[1]))
                ranges.append((2, 3))
                self.edits.append((g, side, 1))
            advance = self.ink.path(base.name)[1]
        box = parts_box(parts, self.ink)
        if box is None:
            return None
        upm = float(self.package.upm)
        owner = getattr(self, "owner", None)
        limits = getattr(owner, "limits", None)
        # (the view opens to hold a mark moved by hand, up to VIEW_REACH: farther, the mark is outside it)
        top, bottom = view_bounds(upm * 0.85, -upm * 0.3, box[3], box[1], upm, upm * 0.05)
        return {"glyphs": [(parts, max(advance, min(box[2], advance + upm) - min(0, max(box[0], -upm))), "new")],
                "parts": parts, "ranges": ranges,
                "ink": self.ink, "upm": upm, "top": top,
                "bottom": bottom, "room": (), "letters": (None, None), "move_only": True,
                # the font's limits, as on the first tab; its glyphs each drawn alone (marks attached, not components)
                "limits": limits(self.package) if limits is not None else [], "separate": True,
                "warning": getattr(owner, "warning_rgb", WARNING_RGB)}

    def adjust_of(self, index):
        if index is None or index >= len(getattr(self, "edits", [])):
            return [0.0, 0.0, 1.0, 1.0]
        g, name, sign = self.edits[index]
        dx, dy = g.adjust.get(name, (0, 0))
        return [sign * dx, sign * dy, 1.0, 1.0]

    def snap_targets(self, index):
        """[(x, label)] the dragged sample mark's center snaps to, as on the Letters tab: its letter's box
        center and top (or bottom) center, for anchors above and below."""
        scene = self.editor.scene
        if scene is None or index is None or index >= len(getattr(self, "edits", [])):
            return []
        name = self.edits[index][1].lstrip(u"_")
        side = "above" if name.startswith(u"top") else ("below" if name.startswith(u"bottom") else None)
        base = scene["parts"][0]
        letter = scene["ink"](base[0])
        if side is None or letter is None:
            return []
        return letter_centers(letter, base[3], side)

    def set_adjust(self, index, change, final):
        """The sample mark moved: the selected glyph's anchor moved with it (a mark's own the other way)."""
        if index is None or index >= len(getattr(self, "edits", [])):
            return
        g, name, sign = self.edits[index]
        before = g.adjust.get(name)
        dragged = getattr(self, "dragged_from", None)  # (g, name, its adjustment as the drag began)
        if dragged is None or dragged[0] is not g or dragged[1] != name:
            dragged = self.dragged_from = (g, name, list(before) if before else None)
        # (kept within what a font can hold: HAND_REACH)
        dx, dy = round(within_reach(change[0] * sign), 1), round(within_reach(change[1] * sign), 1)
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            g.adjust.pop(name, None)
        else:
            g.adjust[name] = [dx, dy]
        moved = g.adjust.get(name) != dragged[2]
        if final:
            self.dragged_from = None
        try:
            selected = self.editor.selected
            self.editor.scene = self.scene(self.selected())
            self.editor.selected = selected
            self.editor.update()
            self.mark_selected(index)
        finally:  # (whatever the picture did: a finished move reaches its row and the buttons)
            if final:
                try:
                    Qt = _qt()[0].Qt
                    for item in self.items():
                        index_ = int(item.data(0, Qt.UserRole))
                        if 0 <= index_ < len(self.glyphs) and self.glyphs[index_] is g:
                            self.tree.blockSignals(True)
                            self.refresh_item(item, g)
                            if moved and g.pending() and item.flags() & Qt.ItemIsUserCheckable:
                                item.setCheckState(0, Qt.Checked)  # moved by hand: to be written (a click alone leaves it)
                            self.tree.blockSignals(False)
                finally:
                    self.update_buttons()

    def mark_selected(self, index):
        if index is None or index >= len(getattr(self, "edits", [])):
            self.hint.setText(ANCHOR_HELP_NOTE)
            return
        g, name, sign = self.edits[index]
        x, y = g.placed().get(name, (0, 0))
        outside = index in self.editor.outside() if hasattr(self.editor, "outside") else False
        self.hint.setText(u"%s's %s anchor: x %s, y %s%s. Drag the mark or press the arrow keys (<i>Shift</i>: 10 "
                          u"units); <i>Backspace</i> puts it back." % (
                              self.ak.html(g.name), self.ak.html(name), grouped(x), grouped(y),
                              u" (the mark is outside the view: the arrow at the edge points to it)" if outside else u""))

    def reset_anchors(self):
        """The selected glyph's anchors back where they were placed (or are), its row and the editor too."""
        QtCore, QtGui = _qt()
        g = self.selected()
        if g is None:
            return
        g.adjust = {}
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.glyphs) and self.glyphs[index] is g:
                self.tree.blockSignals(True)
                self.refresh_item(item, g)
                self.tree.blockSignals(False)
        self.select()  # the editor drawn again (the list's refill alone left the mark where it was dragged)
        self.update_buttons()

    def show_in_glyph_window(self):
        g = self.selected()
        if g is None or self.package is None:
            return
        error = self.ak.show_in_glyph_window(self.fontlab, u"/%s" % g.name)
        if error:
            self.owner.log.add(self.ak.error_sentence(u"FontLab did not open the glyph", error), "error")

    # -- writing -----------------------------------------------------------------------

    def write(self):
        """Add checked anchors, in the window's top row (owner's image 176): a write, never stopped half way
        (one step of FontLab's History); what was clicked meanwhile is done once it is over."""
        owner = self.owner
        work = getattr(owner, "work_begin", None)
        if work is not None:
            work(u"Adding the anchors", stoppable=False)
        try:
            self.write_now()
        finally:
            if work is not None:
                owner.work_end()

    def write_now(self):
        QtCore, QtGui = _qt()
        self.harvest()
        package = self.package
        if package is None:
            return
        current = self.owner.current_font()
        key = self.owner.package_key(current)
        if key is None or key != self.owner.package_key(package):
            self.run()
            self.owner.log.add(u"The font changed: here is this one's list. Nothing was added.", "warning")
            return
        chosen = dict((g.name, g) for g in self.glyphs if g.checked and g.pending())
        if not chosen and not any(g.checked for g in self.glyphs if g.role == "rule"):
            return
        new_texts = mark_texts(self.glyphs, self.texts) if self.code_box.checked else {}
        if new_texts:
            fc = None
            try:
                fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            except Exception:
                pass
            if fc is not None:
                problem = fc.check_code(u"languagesystem DFLT dflt;\n" + u"".join(new_texts.get(t, u"") for t in CODE_FEATURES),
                                        self.names)
                if problem:
                    self.owner.log.add(u"The mark code has problems, so nothing was written: %s" % self.ak.html(problem), "error")
                    return
            # (Feature Check: the whole font's code with it, which the block alone does not show)
            changed = dict((t, new_texts[t]) for t in CODE_FEATURES if t in new_texts and new_texts[t] != self.texts.get(t))
            refusal = getattr(self.ak, "feature_code_refusal", lambda *a, **k: None)(package, changed, None, self.names)
            if refusal:
                self.owner.log.add(u"Nothing was written: %s. <i>Feature Check</i> lists every finding." %
                                   self.ak.html(refusal), "error")
                return
        added, moved, touched, error = 0, 0, [], None
        written = set()  # (glyph, anchor) written in a master, as moved by hand
        coded = []  # the features whose code was written (a text the font has already is not)
        # The dialog's own write: the History's next step is not an edit made in FontLab (end_write). This
        # tab did not say so, and its step was logged as "The font's History moved" (the owner's report)
        if not self.owner.begin_write(package, existing_glyphs(package, list(chosen))):
            return  # (nothing added: the reason in the log)
        progress = getattr(self.owner, "work_progress", lambda *args, **kwargs: None)
        masters = list(package.masters) or [self.master]
        try:
            for at, master in enumerate(masters):
                progress(None, at / float(len(masters)), stoppable=False)
                planned = dict((g.name, g) for g in self.plan_for(master)[0])
                for name, g in chosen.items():
                    here = planned.get(name)
                    if here is None:
                        continue
                    here.adjust = g.adjust
                    glyph = package.findName(name)
                    layer = glyph.getLayerByName(master) if glyph is not None else None
                    if layer is None:
                        continue
                    counts = (added, moved)
                    for anchor_name in sorted(here.anchors):
                        if layer.findAnchor(anchor_name) is not None:
                            continue
                        x, y = here.placed()[anchor_name]
                        pin = self.fontlab.flPinPoint(QtCore.QPointF(float(x), float(y)))
                        pin.name = anchor_name
                        layer.addAnchor(pin)
                        added += 1
                        written.add((name, anchor_name))
                    for anchor_name in here.moved():  # its own anchors moved by hand (flPinPoint.point, proven)
                        anchor = layer.findAnchor(anchor_name)
                        if anchor is None:
                            continue
                        x, y = here.placed()[anchor_name]
                        anchor.point = QtCore.QPointF(float(x), float(y))
                        moved += 1
                        written.add((name, anchor_name))
                    if glyph not in touched and (added, moved) != counts:
                        touched.append(glyph)  # (a glyph whose anchors were all there already is not counted)
            features = package.fgPackage.features if new_texts else None
            for tag in CODE_FEATURES:
                if tag in new_texts and new_texts[tag] != self.texts.get(tag):
                    features.set_feature(tag, new_texts[tag])
                    coded.append(tag)
        except Exception as exc:
            error = exc
        for name, anchor_name in written:  # the font has these moves now (read again below): only those not written stay
            chosen[name].adjust.pop(anchor_name, None)
        wrote = bool(written) or bool(coded)
        status = None
        try:
            if wrote:  # (a write of nothing makes no History step, which the watch would read as FontLab's)
                status = self.ak.notify_changed(self.fontlab, package, u"FreeLab Glyph Compose anchors", touched)
        finally:
            self.owner.end_write(package, wrote)
        if wrote:
            self.owner.log.add(u"Added %s%s to %s%s.%s" % (
                self.ak.b(counted(added, u"anchor")), (u" and moved %s" % self.ak.b(moved)) if moved else u"",
                self.ak.b(counted(len(touched), u"glyph")),
                u", and wrote the %s code" % u", ".join(coded) if coded else u"",
                undo_words(status, u" <i>Edit &gt; Undo</i> takes it back.")), "done")
            report_write(status, self.owner.log)
        elif error is None:
            self.owner.log.add(u"Nothing was added: the ticked glyphs have their anchors in every master already%s." % (
                u", and the font has the mark code as written" if new_texts else u""))
        if error is not None:
            self.owner.log.add(self.ak.error_sentence(u"Stopped by an error", error), "error")
        self.run(keep_script=True)


# The Cancel button's own line (ak.cancel_button): what a stop leaves, as the stop's log lines say
CANCEL_NOTE = u"A reading stopped changes nothing in the font, and a build stopped while it reads the masters builds nothing."


class AccentsDialog(object):
    COLUMNS = ("Glyph", "Name", "Built from")

    def __init__(self, characters=None, hand_over_key=None):
        """characters: letters handed over (Font Check's missing ones), listed first as their own set;
        hand_over_key: the font they are kept for this session (hand_over_memory), whose checks the lists
        take back."""
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        # What Font Check hands over: letters with diacritics for the Diacritics tab, the characters of
        # Glyph generation's table for that tab (handed_over)
        self.given, self.generation_given = handed_over([c for c in (characters or []) if c],
                                                        generation_table(ak))
        self.hand_over_key = hand_over_key
        kept = hand_over_memory().get(hand_over_key) if hand_over_key is not None else None
        # (the checks the lists had in the window before, taken back once each list is first read)
        self.kept_checks = dict(kept["checks"]) if kept and kept.get("checks") else None
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Glyph Compose")
        dialog.setWhatsThis(HELP.replace(u"{reference}", bundled_family_text(ak)))
        self.ak.size_dialog(dialog)
        outer = ak.window_layout(dialog)  # (scrolls on a small screen)
        # Tab bars over plain pages (a QTabWidget's themed page frames its buttons in light colors in dark
        # mode): the window's two (Diacritics, Glyph generation), and Diacritics' own two under the first
        self.top_tabs = QtGui.QTabBar()
        self.top_tabs.setExpanding(False)
        self.top_tabs.setWhatsThis(TOP_TABS_HELP)
        for label in TOP_TABS:
            self.top_tabs.addTab(label)
        try:
            for index, text in enumerate(TOP_TAB_HELPS):
                self.top_tabs.setTabToolTip(index, text)
                self.top_tabs.setTabWhatsThis(index, text)
        except Exception:
            pass
        # The window's header, as every FreeLab window's (owner's images 217, 222, 223): the top line first (the
        # font and its master, or the no-font line; add_tools_button puts the help, the arrows, and the tools menu
        # at the end of its row, and the busy bar takes its place while the window works), then the shown tab's
        # status lines (add_status), then the header's line, and only then the tabs. With the tabs on the first
        # row, the busy bar crashed into them (owner's image 217).
        self.top_line = ak.status_label()
        self.top_line.setWhatsThis(u"The font and master this window works on (or, with no font, why it lists "
                                   u"nothing: it hooks to the next font you open).")
        outer.addWidget(self.top_line)
        status_holder = QtGui.QWidget()  # (a widget: add_tools_button puts it under the top line, in its column)
        status_holder.setProperty(getattr(ak, "HEAD_PART_PROP", "freelabHeadPart"), True)
        self.status_box = QtGui.QVBoxLayout(status_holder)  # (each tab's status lines, those of the tab shown: show_tab_parts)
        self.status_box.setContentsMargins(0, 0, 0, 0)
        self.status_box.setSpacing(0)
        outer.addWidget(status_holder)
        self.status_holders = {}
        outer.addWidget(ak.header_separator())
        tabs_row = QtGui.QHBoxLayout()
        tabs_row.setContentsMargins(0, 0, 0, 0)
        tabs_row.addWidget(self.top_tabs)
        tabs_row.addStretch(1)
        outer.addLayout(tabs_row)
        # The bottom row's parts, one per tab (only the shown tab's shown: show_tab_parts): at the left the
        # buttons that act on the list's ticks and rows, at the right the committing action (the anchors' compile
        # tick before theirs), then Close (owner's image 265: the buttons stood under the list, not at the bottom)
        self.bottom_parts = {}
        for key in TAB_KEYS:
            parts = []
            for side in range(2):
                holder = QtGui.QWidget()
                row = QtGui.QHBoxLayout(holder)
                row.setContentsMargins(0, 0, 0, 0)
                parts.append((holder, row))
            self.bottom_parts[key] = parts
        self.top_pages = QtGui.QStackedWidget()
        outer.addWidget(self.top_pages, 1)
        diacritics_page = QtGui.QWidget()
        diacritics_layout = QtGui.QVBoxLayout(diacritics_page)
        diacritics_layout.setContentsMargins(0, 0, 0, 0)
        self.top_pages.addWidget(diacritics_page)
        self.generation_page = QtGui.QWidget()  # (its tab's widgets made as it is first shown: generation_tab)
        self.generation_layout = QtGui.QVBoxLayout(self.generation_page)
        self.generation_layout.setContentsMargins(0, 0, 0, 0)
        self.top_pages.addWidget(self.generation_page)
        self.generation = None
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setWhatsThis(TABS_HELP)
        diacritics_layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        diacritics_layout.addWidget(self.pages, 1)
        letters_page = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(letters_page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.pages.addWidget(letters_page)
        self.tabs.addTab(u"Letters with diacritics")
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        self.status.setWhatsThis(u"What the list holds for this font and master: how many glyphs can be built, how "
                                 u"their marks were found, how many do not fit a 120% line, and how many need a "
                                 u"mark or letter the font lacks.")
        self.add_status(self.status, "letters")  # (under the top line: owner's image 265)
        self.log = ak.Log()
        self.log.link_handler = lambda target: self.log_link(target)
        self.log.follow(lambda: (self.fontlab, self.package, self.master))  # the glyphs a line names, as the font draws them
        row = QtGui.QHBoxLayout()
        set_help = u"The Unicode blocks whose missing letters with diacritics are listed."
        row.addWidget(helped(QtGui.QLabel("Character set:"), set_help))
        self.set_box = QtGui.QComboBox()
        if self.given:
            self.set_box.addItem(u"From Font Check (%s)" % ak.counted(len(self.given), u"glyph"))
        for _, label, _ in SETS:
            self.set_box.addItem(label)
        self.set_box.setCurrentIndex(0 if self.given else len(SETS) - 1)
        self.set_box.setWhatsThis(set_help)
        fit_to_contents(self.set_box)  # (as wide as its widest choice, never stretched: owner's image 239)
        row.addWidget(self.set_box)
        self.existing_box = QtGui.QCheckBox(u"Also list existing glyphs.")
        self.existing_box.setWhatsThis(u"Also lists the letters with diacritics the font already has (Latin, Greek, "
                                       u"and Cyrillic), in a section of their own, unticked: each shown beside its "
                                       u"glyph as the font has it, to compare. Placements applied to related letters "
                                       u"and diacritics lined up reach them too, so a font can be made consistent; only "
                                       u"those you tick are rebuilt (their glyphs' outlines in each master replaced "
                                       u"by the letter and marks as components; <i>Edit &gt; Undo</i> takes it back). "
                                       u"The glyphs built in this window stay listed either way, under <i>Built in "
                                       u"this window</i>, until it closes.")
        row.addWidget(self.existing_box)
        self.value_only_box = QtGui.QCheckBox(VALUE_ONLY_LABEL)  # (beside the other choice of what is listed)
        self.value_only_box.setWhatsThis(VALUE_ONLY_HELP)
        row.addWidget(self.value_only_box)
        self.settings = read_settings(ak)
        # Off unless switched on (the owner's choice of 2026-11-15); its own key, so that a choice saved for
        # the box as it was (on at first, every gap closed at once) is not taken for this one
        self.compact = self.settings.get(COMPACT_KEY) is True
        self.compact_box = QtGui.QCheckBox(u"Compact diacritics to fit the line.")
        self.compact_box.setChecked(self.compact)
        self.compact_box.setWhatsThis(COMPACT_HELP)
        row.addStretch(1)
        self.reference_boxes = []  # the reference font's chooser on each tab: one choice, shown in both
        self.hidden = set()  # the rows a search hides, by their recipe's place in self.recipes
        self.shown_existing = set()  # the font's own glyphs listed to show them (go_to_char), the box off
        self.just_built = set()  # the glyphs built here, listed after the build (JUST_BUILT)
        self.open_sections, self.list_scroll = {}, None  # the list as the user left it (remember_list)
        self.own_write = None  # (when, History mark) of a write FontLab had not recorded yet (end_write)
        self.search, self.search_label = self.search_field(
            FIND_A_GLYPH, u"Shows only the glyphs whose name, or the name of a glyph they are built from, "
                             u"holds this text, whose character it is (a letter typed alone also finds the "
                             u"letters with diacritics built on it), or whose Unicode value it is (<i>U+0105</i>, "
                             u"<i>0105</i>); notes are not searched. Rows not shown keep their ticks; <i>Tick "
                             u"all</i>, <i>Untick all</i>, and <i>Tick high-value glyphs</i> act on the rows "
                             u"shown.")
        row.addWidget(self.search_label)  # (left of the field: the field ends at the rows' right edge, owner's image 185)
        row.addWidget(self.search)
        layout.addLayout(row)
        self.options_row = row  # (as tall as the other tabs' rows: line_up_rows)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.table_layout(self.tree)
        self.tree.setWhatsThis(u"The letters with diacritics this font lacks: those that can be built (ticked ones "
                               u"are built), and, at the end, those that need a mark the font does not have. "
                               u"Select a row to see its letter in the reference font. Double-click a row to open its "
                               u"glyph (or, not built yet, its letter) in a <i>Glyph</i> window.")
        layout.addWidget(self.tree, 3)
        # The letters with the same diacritic as the selected one: a strip under the list to go from one
        # to the next (Ĉ placed by hand, then Â, Ê, ĉ...), as FontLab's glyph strip does.
        strip_row = QtGui.QHBoxLayout()
        self.strip_label = helped(QtGui.QLabel(u"Same diacritic:"), STRIP_HELP)
        strip_row.addWidget(self.strip_label)
        self.strip_area = QtGui.QScrollArea()
        self.strip_area.setWidgetResizable(True)
        self.strip_area.setFrameShape(QtGui.QFrame.NoFrame)
        self.strip_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.strip_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.strip_area.setFixedHeight(STRIP_HEIGHT)
        strip = QtGui.QWidget()
        self.strip_layout = QtGui.QHBoxLayout(strip)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(2)
        self.strip_layout.addStretch(1)
        self.strip_area.setWidget(strip)
        helped(strip, STRIP_HELP)
        self.strip_area.setWhatsThis(STRIP_HELP)
        strip_row.addWidget(self.strip_area, 1)
        layout.addLayout(strip_row)
        self.strip_buttons, self.strip_slots = [], []
        self.lower_line = heading_line(ak)  # (over the Reference heading: owner's images 234, 288, and 318)
        layout.addWidget(self.lower_line)

        lower = QtGui.QHBoxLayout()
        (reference, self.reference_title, self.reference_font, self.reference, self.reference_note,
         self.reference_line) = self.reference_section(
            u"The selected glyph's character in the reference font, to compare.", REFERENCE_NOTE_HELP)
        lower.addLayout(reference)
        lower.addWidget(self.reference_line)  # (a line between the reference and the preview: owner's image 251)
        editing = QtGui.QVBoxLayout()
        self.editor = make_editor(self)
        self.editor.setProperty(ak.LEAVE_ALONE_PROP, True)  # dark mode leaves what it draws alone
        self.editor.setWhatsThis(u"The selected glyph as it would be built, between its letter and a letter the font "
                                 u"has with the same base (double-click that one to go to its row: it is listed, "
                                 u"unticked, until you go on to another letter, unless you tick it). Double-click the "
                                 u"glyph to open it (or, not built yet, its letter) in a <i>Glyph</i> window. Click a "
                                 u"diacritic to select it; drag it or press the arrow keys to move it; drag its frame "
                                 u"to scale it; <i>Tab</i> selects the next diacritic, <i>Backspace</i> puts it back. "
                                 u"Dragged, a diacritic's center snaps to the letter's box center or top center "
                                 u"(bottom center, for a diacritic below), a guide drawn; <i>Alt</i>: no snapping. "
                                 + LINES_HELP + u" The glyph is drawn as a renderer fills it, its "
                                 u"components kept: a hole shown here would show in the font. A diacritic moved out of "
                                 u"the picture is shown by an arrow at the edge: click the arrow to select it.")
        editing.addWidget(self.editor, 1)
        hint_row = QtGui.QHBoxLayout()
        self.hint = helped(QtGui.QLabel(u"Click a diacritic to move or scale it."), HINT_HELP)
        self.hint.setWordWrap(True)
        hint_row.addWidget(self.hint, 1)
        # (with the preview it changes, left of Reset diacritics: the owner's report of 2026-11-15)
        hint_row.addWidget(self.compact_box)
        self.reset_marks_button = QtGui.QPushButton(u"Reset diacritics")
        self.reset_marks_button.setWhatsThis(u"Puts this glyph's diacritics back where they were suggested.")
        hint_row.addWidget(self.reset_marks_button)
        self.propagate_button = QtGui.QPushButton(u"Apply to related letters")
        self.propagate_button.setWhatsThis(u"Moves and scales the same diacritic on the related letters as on this "
                                           u"one: the same mark, on the same side and at the same place in its "
                                           u"stack, over letters of the same case (a circumflex raised on <i>C</i>: "
                                           u"every capital with a circumflex). Across, a diacritic snapped to a "
                                           u"center is centered on each letter; else its offset from the letter's "
                                           u"center is carried, each letter keeping where fonts set diacritics on it "
                                           u"(right of <i>l</i>'s stem). Grayed once applied, until the diacritic is "
                                           u"moved again; after <i>Reset diacritics</i> here, it puts the related "
                                           u"letters back too. Letters where the diacritic then comes within %.1f%% "
                                           u"of the em of its letter or another diacritic are named in the log and in "
                                           u"their row (an ogonek, a cedilla, or a horn: where it does not touch its "
                                           u"letter)." % (TOUCH_SHARE * 100))
        hint_row.addWidget(self.propagate_button)
        self.line_up_button = QtGui.QPushButton(u"Line up diacritics")
        self.line_up_button.setWhatsThis(u"Sets every diacritic above (or below) of the same group at the same height "
                                         u"as this glyph's: its bottom (a diacritic below: its top) level with this "
                                         u"one's. A group: the same side, the same case, and letters of the same height "
                                         u"(within %d%% of the em: h's circumflex is not set as low as e's). Diacritics "
                                         u"placed by a rule of their own (cedilla, ogonek, horn, the vertical caron, "
                                         u"conventions), stacked diacritics, and taller or shorter letters are left as "
                                         u"they are and named in the log. Each moved diacritic counts as moved by hand: "
                                         u"<i>Reset diacritics</i> on a row puts it back." % round(LINE_UP_HEIGHT_SHARE * 100))
        hint_row.addWidget(self.line_up_button)
        editing.addLayout(hint_row)
        lower.addLayout(editing, 1)
        layout.addLayout(lower, 2)

        self.all_button = helped(QtGui.QPushButton(TICK_ALL), u"Ticks every glyph shown that can be built (rows "
                                 u"a search hides keep their ticks).")
        self.none_button = helped(QtGui.QPushButton(TICK_NONE), u"Unticks every glyph shown (rows a search hides "
                                  u"keep their ticks).")
        self.value_button = QtGui.QPushButton(TICK_HIGH_VALUE)
        self.value_button.setWhatsThis(VALUE_BUTTON_HELP)
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every tick, and every diacritic moved by hand, back as the list first came.")
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected glyph in a <i>Glyph</i> window, between its "
                                              u"script's control glyphs (H, n, and o for Latin; only a glyph the font "
                                              u"has: build it first).")
        self.build_button = QtGui.QPushButton(BUILD_TICKED)
        self.build_button.setWhatsThis(u"Adds each ticked glyph to the font, with its Unicode value, built from its "
                                       u"letter and marks as components, in every master. Every ticked glyph is "
                                       u"built, those a search hides too: the count beside the search field says "
                                       u"how many of them are hidden. <i>Edit &gt; Undo</i> takes them back (in two "
                                       u"steps when some of them are made of others built with them, as the log "
                                       u"says).")
        # ("Check" here runs a check, in Kerning Check: not a tick)
        self.kerning_button = QtGui.QPushButton(u"Check kerning of these glyphs")
        self.kerning_button.setWhatsThis(u"Opens <i>Kerning Check</i> on the pairs with the glyphs built here (since "
                                         u"this dialog opened): collisions their diacritics may cause, kerning to clean "
                                         u"up.")
        self.correct_button = QtGui.QPushButton(correct_button_text(0))
        self.correct_button.setWhatsThis(CORRECT_HELP)
        self.close_button = helped(QtGui.QPushButton("Close"), u"Closes this window. Nothing is built by closing; "
                                   u"ticks and diacritics moved by hand are not kept.")
        left, right = self.bottom_row("letters")
        for button in (self.all_button, self.none_button, self.value_button, self.restore_button,
                       self.glyph_window_button, self.kerning_button, self.correct_button):
            left.addWidget(button)
        right.addWidget(self.build_button)
        self.anchors = AnchorPage(self)
        self.pages.addWidget(self.anchors.widget)
        self.tabs.addTab(u"Mark anchors")
        self.tabs.setTabToolTip(0, TAB_HELPS[0])
        self.tabs.setTabToolTip(1, TAB_HELPS[1])
        try:  # each tab's own help, where the tab bar takes one per tab
            self.tabs.setTabWhatsThis(0, TAB_HELPS[0])
            self.tabs.setTabWhatsThis(1, TAB_HELPS[1])
        except Exception:
            pass
        outer.addWidget(self.log.widget)
        # The bottom row (owner's image 265 and brief 4): each tab's left part, a stretch, each tab's right part,
        # then Close; the shown tab's parts only (show_tab_parts)
        closing = QtGui.QHBoxLayout()
        for key in TAB_KEYS:
            closing.addWidget(self.bottom_parts[key][0][0])
        closing.addStretch(1)
        for key in TAB_KEYS:
            closing.addWidget(self.bottom_parts[key][1][0])
        closing.addWidget(self.close_button)
        try:
            ak.cancel_button(self, closing, self.close_button, CANCEL_NOTE)  # (right before Close)
        except Exception:
            pass  # (an older shared module without it: the window as before)
        outer.addLayout(closing)
        self.anchors_read = False
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.top_tabs.connect("currentChanged(int)", self.switch_top_page)
        self.set_box.connect("currentIndexChanged(int)", lambda index: self.run())
        self.existing_box.connect("toggled(bool)", lambda on: self.run())
        self.value_only_box.connect("toggled(bool)", lambda on: self.searched())
        self.compact_box.connect("toggled(bool)", lambda on: self.compact_toggled())
        self.correct_button.connect("clicked()", self.correct_mirrored)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.value_button.connect("clicked()", self.check_high_value)
        self.search.connect("textChanged(QString)", lambda text: self.searched())
        self.restore_button.connect("clicked()", self.restore)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.kerning_button.connect("clicked()", self.check_kerning)
        self.reset_marks_button.connect("clicked()", self.reset_marks)
        self.propagate_button.connect("clicked()", self.propagate)
        self.line_up_button.connect("clicked()", self.line_up)
        self.build_button.connect("clicked()", self.build)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        self.tree.connect("itemSelectionChanged()", self.select)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.list_checked())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        # a section opened later (Existing glyphs is closed at first) fits the columns to its rows too: they
        # were fitted to the rows then shown, the headings alone when every section was closed
        self.tree.connect("itemExpanded(QTreeWidgetItem*)",
                          lambda item: fit_tree_columns(self.tree, len(self.COLUMNS) - 1))
        self.package = self.master = None
        self.built_names, self.built_font = [], None  # the glyphs built here, and their font's key
        self.recipes, self.inks, self.placements = [], {}, {}
        self.first_checks, self.seen_history, self.buttons_due, self.busy = {}, None, False, False
        self.held_font = None  # the font read once while a mark is dragged (font_read)
        self.choosing_reference = False
        self.reference_history = []
        family = self.settings.get("reference")
        if family:
            self.reference_history.append(family)
        self.high_value, self.high_value_key, self.high_value_due = None, None, False
        self.left_out, self.left_out_said, self.limit_cache = [], None, {}
        self.reference_default, self.reference_list, self.reference_chosen = None, [], u""
        try:
            self.setup_reference()
        except Exception as exc:  # (the dialog opens all the same: references fall back as they do)
            self.log.add(u"The reference font's list could not be made: %s" % ak.html(exc), "error")
        self.model = load_model()
        ak.add_tools_button(dialog, TOOL_TITLE, getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        try:  # the check boxes drawn plain to see in either palette (the lists' pictures stay unmapped)
            fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            self.check_watcher = fc.watch_check_boxes(dialog, [self.tree, self.anchors.tree])
        except Exception:
            self.check_watcher = None
        self.history_timer = ak.watch_history(self)
        self.flagging = [ak.flag_menu(self.tree, self, self.flag_names, self.row_names),
                         ak.flag_menu(self.anchors.tree, self, lambda: [self.anchors.selected().name]
                                      if self.anchors.selected() is not None else [], self.anchors.row_names)]
        self.keep_preview_room()
        self.show_preview_parts(None)  # (nothing listed yet, nothing selected: nothing shown empty)
        self.update_buttons()
        self.show_tab_parts()  # (the first tab's status lines and bottom row)
        self.line_up_rows()  # (Letters with diacritics' and Mark anchors' rows as tall: brief 23)
        if self.generation_given:  # (Font Check handed over glyphs Glyph generation builds)
            self.say_handed_over()
            if len(self.generation_given) >= len(self.given):
                self.top_tabs.setCurrentIndex(1)  # (the tab with more: switch_top_page makes it)

    # -- what both tabs share: a search field, the reference font's chooser, the font's limits --------

    def search_field(self, placeholder, help_text):
        """(a search field, the label of its count), as Font Check's: rows are filtered as the text is typed."""
        QtCore, QtGui = _qt()
        field = QtGui.QLineEdit()
        try:
            field.setPlaceholderText(placeholder)
        except Exception:
            pass
        field.setMaximumWidth(220)
        field.setWhatsThis(help_text)
        count = helped(QtGui.QLabel(u""), help_text)  # (its count carries the field's help)
        count.setVisible(False)  # (shown while it counts: show_count)
        # Its text's width where the row has room (the stretch before it gives way first), never a least width
        # of its own: shown, "98 of 576 glyphs shown" made the window wider (owner's images 307 and 308)
        try:
            count.setMinimumWidth(1)
        except Exception:
            pass
        return field, count

    def reference_box(self):
        """A chooser of the reference font (one per tab, showing the same choice), filled by setup_reference.
        A plain combo box, each entry carrying its own font (set_reference_fonts), not a QFontComboBox:
        that one fills itself from the installed fonts into a list of plain texts, which can hold neither
        an entry of another name ("... (default)") nor a separator, and fills itself again when a font is
        registered, as the bundled one is here."""
        QtCore, QtGui = _qt()
        box = QtGui.QComboBox()
        box.setMaximumWidth(REFERENCE_WIDTH)
        box.setWhatsThis(u"The font the reference is drawn in, on both tabs: %s at first, listed at the top with "
                         u"the fonts you picked last, over a line that sets them apart from the installed fonts "
                         u"(picking the first takes another pick back). Each font's name is written in that "
                         u"font. A pick whose font is no longer installed is forgotten, and the log says so. A "
                         u"character the font lacks is drawn in a font picked before, or in a font known for wide "
                         u"coverage, and the line under the picture says which." % bundled_family_text(self.ak))
        self.reference_boxes.append(box)
        return box

    def setup_reference(self):
        """The bundled font registered with Qt (by Font Check's own function, so the family is there
        without Font Check having been opened), the choosers filled, and the choice shown: the one saved,
        else the bundled font."""
        QtCore, QtGui = _qt()
        self.reference_default, shown = None, None
        self.freelang, self.font_names = [], {}
        try:
            fc = self.ak.load_sibling(FONT_CHECK_FILE, FONT_CHECK_MODULE)
            self.reference_default = fc.register_list_font(QtCore, QtGui) or None
            shown = getattr(fc, "LIST_DISPLAY_NAME", None)  # (the font's name; its families fall back to one another)
            if self.reference_default:
                # every FreeLang family, in Font Check's order: the fallback for a character the chosen font lacks
                self.freelang = [self.reference_default] + [family for _, family in getattr(fc, "LIST_FONT_FALLBACKS", ())]
                if shown:
                    self.font_names = dict((family, shown) for family in self.freelang)
        except Exception:
            self.reference_default = None  # (no bundled font: the installed fonts alone, as before)
        try:
            families = [u"%s" % name for name in QtGui.QFontDatabase().families()]
        except Exception:
            families = []
        self.reference_families, self.reference_shown = families, shown
        # A pick saved before whose font is gone since (a family renamed, a font uninstalled) is neither
        # listed nor chosen: the default stands, the pick is forgotten, and the log says so once
        saved = self.settings.get("reference")
        pick, recent = installed_pick(saved, self.settings.get("recent_references"), families)
        if saved and pick is None:
            self.settings.pop("reference", None)
            self.log.add(gone_reference_text(self.ak.html(saved), self.ak.html(shown or self.reference_default)
                                             if self.reference_default else None), "warning")
        if (saved and pick is None) or recent != list(self.settings.get("recent_references") or []):
            if recent:
                self.settings["recent_references"] = recent
            else:
                self.settings.pop("recent_references", None)
            if families:  # (what Qt could not list is not rewritten)
                write_settings(self.ak, self.settings)
        self.reference_recent = recent
        # the fonts picked before stand in, latest first, where the chosen one lacks a character
        self.reference_history = list(recent)
        self.reference_list = reference_rows(self.reference_default, families, recent, shown)
        self.reference_chosen = pick or self.reference_default or u""
        self.fill_reference_boxes()
        for box in self.reference_boxes:
            self.connect_reference_box(box)
        self.show_reference_choice()
        self.reference_fonts_at = 0
        self.reference_ready = True  # (a chooser made later, Glyph generation's, is filled as it is made)
        try:
            QtCore.QTimer.singleShot(0, self.set_reference_fonts)  # each name in its own font, once the dialog shows
        except Exception:
            pass  # (the names stay in the dialog's font)

    def connect_reference_box(self, box):
        slot = (lambda source: lambda index: self.reference_picked(source))(box)
        self.reference_slots = getattr(self, "reference_slots", []) + [slot]  # (kept: PythonQt holds no reference)
        box.connect("currentIndexChanged(int)", slot)

    def late_reference_box(self, box):
        """A chooser made once the others were filled (Glyph generation's, made as its tab is first shown):
        filled, connected, on the chosen font, and its names given their own fonts (from the first row again,
        for every chooser: a slice still to come goes on from there)."""
        QtCore, QtGui = _qt()
        self.fill_reference_boxes([box])
        self.connect_reference_box(box)
        self.show_reference_choice()
        running = getattr(self, "reference_fonts_at", 0) < len(getattr(self, "reference_list", ()))
        self.reference_fonts_at = 0
        if not running:
            try:
                QtCore.QTimer.singleShot(0, self.set_reference_fonts)
            except Exception:
                pass

    def reference_section(self, help_text, note_help):
        """A tab's reference column, the same on every tab (owner's images 250 and 251): the Reference heading,
        the reference font's chooser (one choice for all tabs), the picture, and the caption under it that
        says which font draws it (a preview's caption). Returns (its layout, heading, chooser, picture,
        caption, the line that sets it apart from the preview at its right: put after it)."""
        QtCore, QtGui = _qt()
        ak = self.ak
        column = QtGui.QVBoxLayout()
        title = helped(QtGui.QLabel(u"Reference"), help_text)
        bold = QtGui.QFont(_property(title, "font"))
        bold.setBold(True)
        title.setFont(bold)
        column.addWidget(title)
        box = self.reference_box()
        if getattr(self, "reference_ready", False):
            self.late_reference_box(box)
        column.addWidget(box)
        picture = QtGui.QLabel()
        picture.setProperty(ak.LEAVE_ALONE_PROP, True)
        picture.setAlignment(QtCore.Qt.AlignCenter)
        picture.setFixedWidth(REFERENCE_WIDTH)
        picture.setMinimumHeight(EDITOR_HEIGHT - 60)
        picture.setWhatsThis(help_text)
        column.addWidget(picture, 1)
        note = QtGui.QLabel(u"")
        caption = getattr(ak, "preview_caption", None)
        if caption is not None:
            note = caption(label=note) or note  # (0.9 size, quiet: as every preview's caption)
        note = helped(note, note_help)
        note.setWordWrap(True)
        note.setFixedWidth(REFERENCE_WIDTH)
        column.addWidget(note)
        # The line in a holder of its own: the shared module shows and hides its separators with the font, so
        # the reference hidden (nothing selected) hides the holder, never the line
        line = QtGui.QWidget()
        holder = QtGui.QHBoxLayout(line)
        holder.setContentsMargins(0, 0, 0, 0)
        holder.addWidget(ak.separator(vertical=True))
        return column, title, box, picture, note, line

    def fill_reference_boxes(self, boxes=None):
        """The choosers (boxes: those, else all) filled with reference_list's rows (no signal: nothing is picked)."""
        for box in (self.reference_boxes if boxes is None else boxes):
            box.blockSignals(True)
            try:
                box.clear()
                for at, (label, _) in enumerate(self.reference_list):
                    if label is None:
                        box.insertSeparator(at)
                    else:
                        box.addItem(label)
            finally:
                box.blockSignals(False)

    def refresh_reference_rows(self):
        """The choosers' rows made again for the fonts picked recently (a pick moved to the top), the
        choice shown, and each name given its own font again. Done after the pick's own signal, from the
        event loop: a combo box is not refilled inside its own currentIndexChanged."""
        try:  # (a timer's slot: nothing may escape to Qt)
            QtCore, QtGui = _qt()
            self.reference_due = False
            rows = reference_rows(self.reference_default, getattr(self, "reference_families", []),
                                  self.reference_recent, getattr(self, "reference_shown", None))
            if rows == self.reference_list:
                return
            # (a slice still to come of the old list's starts over; a finished one is started again: the
            # refill took every row's font)
            running = getattr(self, "reference_fonts_at", 0) < len(self.reference_list)
            self.reference_list = rows
            self.fill_reference_boxes()
            self.show_reference_choice()
            self.reference_fonts_at = 0
            if not running:
                QtCore.QTimer.singleShot(0, self.set_reference_fonts)
        except Exception as exc:
            self.log.add(u"The reference font's list could not be made again: %s" % self.ak.html(exc), "error")

    def writes_latin(self, family, database):
        """Whether a family has Latin letters, as Qt's font database tells: one that has none (a symbol
        font) keeps the dialog's font in the chooser, since its own would make its name unreadable (a
        QFontComboBox does the same). Where Qt does not tell: taken to have them."""
        try:
            QtCore, QtGui = _qt()
            latin = int(QtGui.QFontDatabase.Latin)
            return latin in [int(system) for system in database.writingSystems(family)]
        except Exception:
            return True

    def set_reference_fonts(self):
        """Each entry of the reference font's choosers written in its own family, as a QFontComboBox
        previews its fonts: a combo box draws an item in the font its Qt.FontRole holds. A slice of
        REFERENCE_SLICE families per turn of the event loop, so that several hundred installed fonts never
        hold the dialog up; the bundled font's entry first, as it is the first row."""
        try:  # (a timer's slot: nothing may escape to Qt)
            QtCore, QtGui = _qt()
            rows, start = self.reference_list, self.reference_fonts_at
            end = min(len(rows), start + REFERENCE_SLICE)
            database = QtGui.QFontDatabase()
            for at in range(start, end):
                family = rows[at][1]
                if family is None or not self.writes_latin(family, database):
                    continue
                for box in self.reference_boxes:
                    font = QtGui.QFont(_property(box, "font"))  # the chooser's own size and weight
                    font.setFamily(family)
                    box.setItemData(at, font, QtCore.Qt.FontRole)
            self.reference_fonts_at = end
            if end < len(rows):
                QtCore.QTimer.singleShot(0, self.set_reference_fonts)
        except Exception:
            self.reference_fonts_at = len(getattr(self, "reference_list", ()))  # (stopped: plain names from here on)

    def show_reference_choice(self):
        """Both choosers on the chosen family's row (no signal: nothing was picked)."""
        rows = [family for _, family in self.reference_list]
        index = rows.index(self.reference_chosen) if self.reference_chosen in rows else -1
        self.choosing_reference = True
        try:
            for box in self.reference_boxes:
                box.blockSignals(True)
                box.setCurrentIndex(index)
                box.blockSignals(False)
        finally:
            self.choosing_reference = False

    def reference_picked(self, box):
        """A family picked in either tab's chooser: the reference font for both, remembered; the bundled
        font's row takes a saved pick back (the default is not saved, so it stays the default)."""
        try:  # (a signal's handler: nothing may escape to Qt)
            if self.choosing_reference:
                return
            index = int(_property(box, "currentIndex"))
            if not 0 <= index < len(self.reference_list) or self.reference_list[index][1] is None:
                return
            self.set_reference(self.reference_list[index][1])
        except Exception as exc:
            self.log.add(u"Could not change the reference font: %s" % self.ak.html(exc), "error")

    def set_reference(self, family):
        self.reference_chosen = family
        if family == self.reference_default:
            self.settings.pop("reference", None)
        else:
            if family in self.reference_history:
                self.reference_history.remove(family)
            self.reference_history.insert(0, family)  # the fonts picked before: the fallbacks, latest first
            self.settings["reference"] = family
            recent = [family] + [other for other in getattr(self, "reference_recent", []) if other != family]
            self.reference_recent = recent[:REFERENCE_RECENT]
            self.settings["recent_references"] = list(self.reference_recent)
        write_settings(self.ak, self.settings)
        self.show_reference_choice()
        self.reference_changed()
        # A font picked among the installed ones joins the top of the list (the list is made again once
        # this pick's signal is over); one there already stays where it is, the list unchanged under it
        top = [row[1] for row in self.reference_list[:(self.reference_list.index((None, None))
                                                       if (None, None) in self.reference_list else 0)]]
        if family != self.reference_default and family not in top and not getattr(self, "reference_due", False):
            self.reference_due = True
            try:
                QtCore, QtGui = _qt()
                QtCore.QTimer.singleShot(0, self.refresh_reference_rows)
            except Exception:
                self.refresh_reference_rows()

    def limits(self, package):
        """[(units, label)] of the limits the editors draw (limit_lines): the font's ascender and
        descender, its typo, hhea, and win values as Font Check's Vertical metrics reads them, and the
        room of a 120% line; read once per font and master."""
        key = (self.package_key(package), getattr(package, "master", None))
        cache = getattr(self, "limit_cache", None)
        if cache is None:
            cache = self.limit_cache = {}
        if key not in cache:
            read, merge = None, None
            try:
                fc = self.ak.load_sibling(FONT_CHECK_FILE, FONT_CHECK_MODULE)
                values = fc.read_metrics(package)
                read, merge = (lambda field: getattr(values, field, None)), fc.merge_names
            except Exception:  # (without Font Check: the font's own ascender and descender)
                fields = {"ascender": "ascender_value", "descender": "descender_value"}
                read = lambda field: getattr(package, fields[field]) if field in fields else None  # noqa: E731
            try:
                cache[key] = limit_lines(limit_values(read, self.metrics(package)), merge)
            except Exception:
                cache[key] = []
        return cache[key]

    @property
    def warning_rgb(self):
        """Amber, as the log writes its warnings in this palette (a lighter one on dark, a darker one on light)."""
        try:
            QtCore, QtGui = _qt()
            pair = self.ak.LOG_COLORS["warning"]
            dark = self.dialog.palette.color(QtGui.QPalette.Window).lightness() < 128
            return tuple(pair[0] if dark else pair[1])
        except Exception:
            return WARNING_RGB

    def flag_names(self):
        """The selected glyph, or its letter while it is not built."""
        r = self.selected()
        if r is None:
            return []
        return [r.name] if self.in_font(r) else [r.base] if r.base else []

    def row_names(self, item):
        """A row's glyph, if the font has it (its flag shown); none for a section's heading."""
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        if not 0 <= index < len(self.recipes):
            return []
        r = self.recipes[index]
        return [r.name] if self.package is not None and r.name and self.package.findName(r.name) is not None else []

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = self.ak.window_font(self, workspace)  # this window's font
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def package_key(self, package):
        """The font's key (Auto Kerning's font_key) with FontLab's id of it (two unsaved fonts of one name
        share the key; PythonQt wraps each read of a font anew, so the wrapper tells nothing), or None for
        no font or one closed since."""
        try:
            if package is None:
                return None
            return self.ak.font_key(package), getattr(getattr(package, "fgPackage", None), "id", None)
        except Exception:
            return None

    def font_read(self):
        """The open font as font() reads it: the read held while a mark is dragged (set_adjust), else read now."""
        held = getattr(self, "held_font", None)
        return held if held is not None else self.font(self.package)

    def font(self, package, progress=None):
        """The font as the planning reads it; its empty glyphs among those built here, and among those
        the marks are taken from (a mark, its spacing form, the punctuation a draft is made of, a glyph
        named as a mark): an empty one is never built on (Font.drawn). progress(share): told as it goes."""
        glyphs = list(package.fgPackage.glyphs)
        empty = []
        total = float(len(glyphs) or 1)
        for at, g in enumerate(glyphs):
            if progress is not None and not at % PROGRESS_EVERY:
                progress(at / total)
            code = self.ak.main_code(g)  # (the code it stands for: not a radical FontLab gives first)
            if (code and (code < EMPTY_READ_BELOW or 0x3040 <= code < 0x3100 or code in MARK_CODES_READ)) or (
                    not code and u"comb" in (u"%s" % g.name)):
                glyph = package.findName(g.name)
                if glyph is not None and is_empty(glyph):
                    empty.append(g.name)
        found = Font([g.name for g in glyphs], font_codes(self.ak, glyphs), empty)
        try:  # (the dotless i and j the font lacks: made of its i and j where their dot can be told, else said)
            found.dotless = read_dotless(package, list(package.masters) or [self.master], found)
        except Exception:
            found.dotless = {}  # (unread: the letters stay on the dotted i, as before it was read)
        self.dotless_found = found.dotless
        return found

    def dotless_virtual(self):
        """FontLabInk's virtual glyphs: the dotless glyphs a build would make, as the font was last read."""
        return dict((d.name, (d.source, d.dot)) for d in getattr(self, "dotless_found", {}).values()
                    if d.kind == "made")

    def characters(self):
        index = self.set_box.currentIndex
        if self.given:
            if index == 0:  # (single characters: what is handed over as several is named in the top line)
                return [item for item in self.given if len(item) == 1]
            index -= 1
        ranges = SETS[index][2]
        return [unichr_(code) for low, high in ranges for code in range(low, high)]

    def learn(self, package, master, progress=None):
        """The master's ink and where its composites put their marks. progress(share): told as it goes."""
        ink = FontLabInk(self.ak, package, master, self.dotless_virtual())
        placement = Placement(float(package.upm), self.model)
        composites = []
        glyphs = list(package.fgPackage.glyphs)
        total = float(len(glyphs) or 1)
        for at, fg in enumerate(glyphs):
            if progress is not None and not at % PROGRESS_EVERY:
                progress(at / total)
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            parts = component_parts(layer) if layer is not None else None
            marks = learned_marks(self.ak.main_code(fg), parts) if parts and len(parts) > 1 else None
            if marks is not None:
                composites.append((parts[0][0], marks))
        by_name = dict((g.name, self.ak.main_code(g)) for g in package.fgPackage.glyphs)  # (not a radical first)

        def glyph_case(name):
            code = by_name.get(name)
            return case_of(unichr_(code)) if code else ("upper" if name[:1].isupper() else "lower")

        placement.learn(composites, ink, glyph_case)
        return ink, placement

    def metrics(self, package):
        try:
            return Metrics(package.upm, package.ascender_value, package.descender_value, package.capsHeight_value)
        except Exception:
            return None

    # -- the window's top line, and its long work in the top row ----------------------------------------

    def show_top_line(self, text):
        """The window's top line (its first row, beside the "?"): the font and master (font_line), or the
        no-font line. Never raises."""
        try:
            self.top_line.setText(text)
        except Exception:
            pass

    def say_font(self, package):
        """The top line names the font every tab works on (or says there is none), before a tab reads it: it
        stays so when the reading fails (brief 2; the error goes to the log)."""
        self.show_top_line(font_line(getattr(self, "ak", None), package))

    def add_status(self, label, key):
        """A tab's status lines (key: TAB_KEYS'), under the window's top line, shown while the tab is
        (show_tab_parts): what sat under the tabs moved under the font line (owner's image 265)."""
        QtCore, QtGui = _qt()
        holder = QtGui.QWidget()
        box = QtGui.QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(label)
        self.status_box.addWidget(holder)
        self.status_holders[key] = holder
        holder.setVisible(key == self.shown_tab())

    def bottom_row(self, key):
        """(left, right): the layouts of a tab's parts of the window's bottom row (key: TAB_KEYS')."""
        parts = self.bottom_parts[key]
        return parts[0][1], parts[1][1]

    def shown_tab(self):
        """The key (TAB_KEYS') of the tab shown: Letters with diacritics, Mark anchors, or Glyph generation."""
        try:
            if int(_property(self.top_tabs, "currentIndex")) == 1:
                return "generation"
            return "anchors" if int(_property(self.tabs, "currentIndex")) == 1 else "letters"
        except Exception:
            return "letters"

    def show_tab_parts(self):
        """The shown tab's status lines and bottom-row parts shown, the other tabs' hidden (brief 4). Never raises."""
        try:
            shown = self.shown_tab()
            groups = {}
            for key, holder in getattr(self, "status_holders", {}).items():
                groups.setdefault(key, []).append(holder)
            for key, parts in getattr(self, "bottom_parts", {}).items():
                groups.setdefault(key, []).extend(holder for holder, _ in parts)
            show_only = getattr(getattr(self, "ak", None), "show_only", None)
            if show_only is not None:
                show_only(groups, shown)  # (hidden first: owner's image 284)
            else:
                for key in sorted(groups, key=lambda k: k == shown):
                    for holder in groups[key]:
                        holder.setVisible(key == shown)
        except Exception:
            pass

    def stopped_error(self):
        """The shared module's Stopped (busy_progress raises it when the user asks the work to stop)."""
        return getattr(getattr(self, "ak", None), "Stopped", None) or NotStopped

    def work_begin(self, what, stoppable=True):  # (work_stoppable: what Cancel was last told, work_progress)
        """Long work begins (owner's images 176 to 183): its step and a bar in the window's top row, the
        window held from clicks and keys meanwhile (but the tools menu, the arrows, Close, and Esc, which stop
        it); self.busy holds the font's watches. Work begun inside other work (a build reads the font again
        once it is done) goes on in the same bar. Always matched by work_end, in a finally."""
        depth = getattr(self, "work_depth", 0)
        self.work_depth = depth + 1
        self.busy = True
        if depth:
            self.work_progress(what, None, stoppable)
            return
        self.work_stoppable = bool(stoppable)
        start = getattr(getattr(self, "ak", None), "busy_start", None)
        if start is not None:
            try:
                start(self, what, stoppable=stoppable)
            except Exception:
                pass  # (the work goes on without its bar: work_end still ends it)

    def work_progress(self, what=None, part=None, stoppable=True):
        """The work at a step (what: its name, or None to keep it; part: 0 to 1, or None): raises Stopped
        when the user asked it to stop, unless stoppable is False (a write to the font). Nothing outside work."""
        if not getattr(self, "work_depth", 0):
            return
        progress = getattr(getattr(self, "ak", None), "busy_progress", None)
        # (Cancel follows the step: a build reads the masters, which can stop, then writes, which cannot)
        follow = getattr(getattr(self, "ak", None), "busy_stoppable", None)
        if follow is not None and getattr(self, "work_stoppable", None) != bool(stoppable):
            self.work_stoppable = bool(stoppable)
            try:
                follow(self, stoppable)
            except Exception:
                pass
        if progress is not None:
            progress(self, what, part, stoppable=stoppable)

    def work_part(self, low, high, stoppable=True):
        """progress(share) for a loop that is the stretch from low to high of the work's bar."""
        return lambda share: self.work_progress(None, low + (high - low) * share, stoppable)

    def work_end(self):
        """Work over (done, failed, or stopped): the top row as it was, and what was clicked meanwhile done."""
        depth = max(getattr(self, "work_depth", 0) - 1, 0)
        self.work_depth = depth
        if depth:
            return
        self.busy = False
        end = getattr(getattr(self, "ak", None), "busy_end", None)
        if end is not None:
            end(self)

    def has_font(self):
        """Whether the window works on a font (the shared module grays its controls while not)."""
        return getattr(self, "package", None) is not None

    # -- the list ----------------------------------------------------------------

    def run(self):
        """The list read from the font (in the window's top row, stoppable: owner's image 176). A read asked
        while one goes on is done once it is over."""
        if getattr(self, "reading", False):
            self.read_again = True
            return
        self.reading, self.read_again = True, False
        try:
            self.read_list()
        finally:
            self.reading = False
        if self.read_again:
            self.read_again = False
            try:
                QtCore, QtGui = _qt()
                QtCore.QTimer.singleShot(0, self.run)
            except Exception:
                pass

    def read_list(self):
        QtCore, QtGui = _qt()
        kept = dict((r.char, (r.checked, dict(r.adjust), r.applied, r.compact, bool(r.existing))) for r in self.recipes)
        built_now, self.built_now = set(getattr(self, "built_now", ())), set()  # (what the build before this made)
        self.shift_cache = {}
        self.held_font = None
        old_key = self.package_key(self.package)
        self.remember_list()  # (the sections opened and where the list is scrolled, for the same font)
        self.tree.clear()
        self.recipes = []
        enable = getattr(getattr(self, "ak", None), "enable", None)
        (enable or (lambda button, on: button.setEnabled(on)))(self.build_button, False)
        package = self.package = self.current_font()
        self.master = package.master if package is not None else None
        same_font = old_key is not None and self.package_key(package) == old_key
        if not same_font:
            self.shown_existing = set()  # (the glyphs listed to show them were another font's)
            self.just_built = set()  # (and those built here)
            self.open_sections, self.list_scroll = {}, None
        self.say_font(package)  # (the font, or the no-font line, beside the "?": brief 1 and 2)
        if package is None:
            self.status.setText(u"")  # (the top line says why: the tab's own lines have nothing to say)
            self.select()  # (nothing selected: the preview's parts hidden, as with a list)
            return
        stopped = self.stopped_error()
        try:
            self.work_begin(u"Reading the font")
            self.read_font(package, same_font, kept, built_now)
        except stopped:  # (the user asked it to stop: nothing is listed, and the line says how to read it again)
            self.tree.clear()
            self.recipes = []
            self.status.setText(STOPPED_READING)
            self.log.add(u"Stopped reading the font: nothing is listed.")
            self.select()
        finally:
            self.work_end()

    def read_font(self, package, same_font, kept, built_now):
        """read_list's work, in the window's top row (work_begin): the font read, the list planned, filled."""
        try:
            font = self.font(package, self.work_part(0.0, 0.35))
            self.work_progress(u"Planning the glyphs", 0.35)
            present = scripts_present(font.by_code)
            wanted = [ch for ch in self.characters() if script_of(ch) not in LISTED_SCRIPTS or script_of(ch) in present]
            self.absent = sorted(set(script_of(ch) for ch in self.characters()
                                     if script_of(ch) in LISTED_SCRIPTS and script_of(ch) not in present))
            # the font's own glyphs listed whatever the box says: one clicked to show it, and those just built
            # (they stay in view, unchecked, so that what is done after a build reaches them)
            also = set(getattr(self, "shown_existing", ())) | set(getattr(self, "just_built", ()))
            self.recipes = plan(font, wanted, self.existing_box.checked, also)
            self.sync_compact()
            # What Font Check handed over and the list has no row for: said in the top line, never silently
            self.left_out = []
            if self.given and self.set_box.currentIndex == 0:
                self.left_out = left_out_given(self.given, self.recipes, font,
                                               [script for script in LISTED_SCRIPTS if script not in present],
                                               set(getattr(self, "just_built", ())))
            self.limit_cache = {}
            self.inks, self.placements = {}, {}
            self.work_progress(u"Reading where its marks go", 0.4)
            self.inks[self.master], self.placements[self.master] = self.learn(package, self.master,
                                                                              self.work_part(0.4, 0.75))
        except self.stopped_error():
            raise
        except Exception as exc:
            self.status.setText(u"")
            self.log.add(self.ak.html(exc), "error")
            self.recipes = []
            self.select()
            return
        self.work_progress(u"Listing the glyphs", 0.75)
        self.fill(self.work_part(0.75, 0.9 if same_font else 1.0))
        self.first_checks = dict((r.char, r.checked) for r in self.recipes)
        if same_font:  # the hand's changes and checks carry over (an undo, another set)
            for r in self.recipes:
                if r.char in kept:
                    checked, r.adjust, r.applied, compact, was_there = kept[r.char]
                    if r.adjust:  # placed by hand: under the compacting it was placed with
                        r.compact = compact
                    if keeps_check(r, was_there, built_now):
                        r.checked = checked
            self.fill(self.work_part(0.9, 1.0))
        elif self.take_kept_checks([r for r in self.recipes if not r.missing], lambda r: r.char):
            self.set_item_checks()  # (Font Check's list, as the window before left its checks)
        self.seen_history = self.ak.history_mark(package)
        own = getattr(self, "own_write", None)
        if own is not None and own[1] != self.seen_history:
            self.own_write = None  # (the late step of the write is read now: a move after it is not the write's)
        self.choose_reference()
        self.select()  # the preview and the strip as the list is now (after an undo in FontLab: read again)
        if same_font:
            self.restore_scroll()  # (read again: the list stays where it was scrolled)
        self.say_left_out()
        self.ask_high_value_soon()

    # -- the list kept in place across a refill ------------------------------------------------

    def remember_list(self):
        """Which sections are open and where the list is scrolled, read from the list as it is (an empty
        list tells nothing: what was read before stands): a refill (compacting switched, the font read
        again) keeps them. Ticking Compact glyphs to fit the line scrolled the list back to the selected
        row each time (the owner's report of 2026-11-14)."""
        if self.remember_sections():
            try:
                self.list_scroll = (int(_property(self.tree.verticalScrollBar(), "value")),
                                    int(_property(self.tree.horizontalScrollBar(), "value")))
            except Exception:
                pass

    def remember_sections(self):
        """Which sections are open, read from the list as it is (fill opens them so again); whether the
        list had any."""
        try:
            sections = getattr(self, "open_sections", None)
            if sections is None:
                sections = self.open_sections = {}
            count = self.tree.topLevelItemCount
            for row in range(count):
                top = self.tree.topLevelItem(row)
                sections[section_title(u"%s" % top.text(0))] = bool(top.isExpanded())
            return count > 0
        except Exception:
            return False  # (a list that cannot tell: refilled as it first comes)

    def restore_scroll(self):
        """The list scrolled back to where remember_list found it (selecting a row scrolls to it). The
        list is laid out first: a refilled list lays its rows out later, and its scroll bar would hold
        the empty list's range until then."""
        try:
            at = getattr(self, "list_scroll", None)
            if at is not None:
                try:
                    self.tree.doItemsLayout()
                except Exception:
                    pass
                self.tree.verticalScrollBar().setValue(at[0])
                self.tree.horizontalScrollBar().setValue(at[1])
        except Exception:
            pass

    def fill(self, progress=None):
        """The list made of the recipes (each row's picture drawn); progress(share): told as it goes."""
        QtCore, QtGui = _qt()
        self.remember_sections()  # (opened and closed as they were)
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        try:
            dimmed = QtGui.QBrush(self.dialog.palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text))
        except Exception:
            dimmed = None
        groups = list_sections(self.recipes, self.existing_shift, getattr(self, "just_built", ()))
        buildable, lacking = groups[0][1], groups[-1][1]
        try:  # (the list's signals given back whatever happens: the work may be stopped as rows are drawn)
            self.fill_rows(groups, bold, dimmed, progress)
        finally:
            self.tree.blockSignals(False)
        fit_tree_columns(self.tree, len(self.COLUMNS) - 1)
        self.fill_status(buildable, lacking)

    def fill_rows(self, groups, bold, dimmed, progress=None):
        """fill's rows, section by section (progress(share): told every PROGRESS_ROWS rows)."""
        QtCore, QtGui = _qt()
        sections = getattr(self, "open_sections", None) or {}
        total, done = float(sum(len(indexes) for _, indexes in groups) or 1), 0
        for title, indexes in groups:
            if not indexes:
                continue
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (title, len(indexes))])
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            top.setData(0, QtCore.Qt.UserRole, -1)
            for index in indexes:
                if progress is not None and not done % PROGRESS_ROWS:
                    progress(done / total)
                done += 1
                r = self.recipes[index]
                item = QtGui.QTreeWidgetItem([r.char, r.name or u"", u""])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, self.char_font(bold, r.char))  # (in FreeLang: owner's images 316 and 317)
                item.setToolTip(0, u"U+%04X %s" % (r.code, unicodedata.name(r.char, u"")))
                if r.missing:  # selectable (its reference letter shown), not checkable, its text dimmed
                    r.cell = r.describe()
                    item.setText(2, r.cell)  # (a short note in a cell: no period)
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    if dimmed is not None:
                        for column in range(len(self.COLUMNS)):
                            item.setForeground(column, dimmed)
                else:
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    self.refresh_item(item, r, first=True)
                    item.setCheckState(0, QtCore.Qt.Checked if r.checked else QtCore.Qt.Unchecked)
                top.addChild(item)
            # as the user left it; at first, the glyphs to build and those just built open
            top.setExpanded(sections.get(title, title in (groups[0][0], JUST_BUILT)))

    def fill_status(self, buildable, lacking):
        """The tab's top line on the list as filled; the search applied (and the buttons)."""
        ak = self.ak
        notes = lambda index, start: any((m.note or u"").startswith(start) for m in self.recipes[index].marks)
        borrowed = sum(1 for index in buildable if notes(index, u"for "))
        drafted = sum(1 for index in buildable if notes(index, u"draft"))
        b = ak.b
        details = [text % b(counted(count, u"glyph")) for count, text in (
            (borrowed, u"%s with a mark below borrowed from above"),
            (drafted, u"%s with a mark drafted from punctuation")) if count]  # (counts in glyphs: the owner's report)
        room = room_details(*room_counts([self.recipes[index] for index in buildable]), bold=b)
        self.status.setText(letters_status(len(buildable), len(lacking), details, room, getattr(self, "absent", None),
                                           b, ak.i) + self.left_out_text())
        self.apply_search()  # (and the buttons)

    def left_out_text(self, names=None):
        """The sentence about the glyphs Font Check handed over that the list has no row for (u"" when
        each has one, or another set is chosen), after a space; names: how their characters are written."""
        left_out = getattr(self, "left_out", None)
        if not left_out:
            return u""
        bold = names or (lambda chars: u" ".join(self.ak.b(on_circle(ch)) for ch in chars))
        return u" " + left_out_sentence(len(self.given), left_out, bold, self.ak.b)

    def say_left_out(self):
        """The same sentence in the log, its glyphs the font has as links (a click opens or lists one);
        once per answer, not at every reading of the font."""
        left_out = getattr(self, "left_out", None)
        have = dict(left_out or []).get("have", [])
        built = dict(left_out or []).get("built", [])

        def names(chars):
            if chars and (chars[0] in have or chars[0] in built):
                return self.ak.glyph_links(chars)  # (the log draws a linked glyph as the font has it)
            return self.ak.html(u" ".join(on_circle(ch) for ch in chars))
        text = self.left_out_text(names).strip()
        if text and text != getattr(self, "left_out_said", None):  # (built here only: no warning, the build's outcome)
            self.log.add(text, "info" if all(reason == "built" for reason, _ in left_out) else "warning")
        self.left_out_said = text or None

    def searched(self):
        try:  # (a signal's handler: nothing may escape to Qt)
            if not self.drop_revealed():  # (a new search: a glyph listed to show it goes, unless checked)
                self.apply_search()
        except Exception as exc:
            self.log.add(u"Could not search the list: %s" % self.ak.html(exc), "error")

    def list_checked(self):
        """A row's check changed (or another of its cells): the buttons follow, and a glyph listed to show
        it goes, unless checked or selected."""
        try:  # (a signal's handler: nothing may escape to Qt)
            self.update_buttons_soon()
        except Exception:
            pass
        self.went_on()

    def went_on(self):
        """The user went on (a check changed): the glyphs listed to show them go, but for one checked or
        selected (drop_revealed_soon). Never raises."""
        try:
            if getattr(self, "shown_existing", None):
                self.drop_revealed_soon(self.selected())
        except Exception:
            pass

    def apply_search(self):
        """The rows the search field's text does not find hidden (their checks kept: a row is hidden, not
        taken out), a section with none left hidden with them; the count beside the field."""
        QtCore, QtGui = _qt()
        self.hidden = set()
        if getattr(self, "search", None) is None:
            self.update_buttons()
            return
        query = u"%s" % (_property(self.search, "text") or u"")
        wanted = value_filter(getattr(self, "value_only_box", None), getattr(self, "high_value", None))
        shown = total = 0
        try:
            for row in range(self.tree.topLevelItemCount):
                top = self.tree.topLevelItem(row)
                found_here = 0
                for child in range(top.childCount()):
                    item = top.child(child)
                    index = int(item.data(0, QtCore.Qt.UserRole))
                    if not 0 <= index < len(self.recipes):
                        continue
                    r = self.recipes[index]
                    # (the glyphs it is built from, not its notes: what placing it took, how it compares)
                    found = row_matches(query, r.name, r.char, r.code, [r.base or u""] + [
                        part[0] for mark in r.marks for part in mark.parts]) and (wanted is None or r.char in wanted)
                    total += 1
                    found_here += 1 if found else 0
                    if not found:
                        self.hidden.add(index)
                    item.setHidden(not found)
                shown += found_here
                top.setHidden(not found_here)
            self.count_args = (shown, total, query, wanted is not None)  # (update_buttons adds the ticks hidden)
            show_count(self.search_label, search_count(shown, total, query, filtered=wanted is not None))
        except Exception as exc:  # (rows that cannot be hidden: every one counts as shown, and the list still fills)
            self.hidden = set()
            show_count(self.search_label, u"")
            if not getattr(self, "search_failed", False):  # said once, not at every keystroke
                self.search_failed = True
                self.log.add(u"The search could not hide rows: %s" % self.ak.html(exc), "error")
        self.update_buttons()

    def refresh_item(self, item, r, first=False):
        """A row's picture and what it is built from, as the recipe is now."""
        QtCore, QtGui = _qt()
        checked = r.checked
        icon = self.picture(r, ICON_SIZE)  # (placing it notes what it took)
        if not first:
            r.checked = checked  # a mark moved by hand does not uncheck the glyph
        if icon is not None:
            item.setIcon(0, self.ak.icon_of(icon))
        r.far = far_note(self.far_reasons(r))  # (a mark the hand left far off: said in its row too)
        # (its dotless i first: made here, the font's i as it is, or the dot kept under the diacritic, the last
        # an amber note as a collision's: kept_dotted)
        notes = ([r.base_note] if r.base_note else []) + list(r.notes) + ([r.touches] if r.touches else []) + (
            [r.far] if r.far else []) + self.reversal_notes(r)
        r.cell = row_text(r.describe(), r.refill, self.existing_shift(r) if r.existing else None, bool(r.existing), notes)
        item.setText(2, r.cell)
        item.setToolTip(2, (u"; ".join(notes) + u".") if notes else u"")

    def far_reasons(self, r):
        """far_marks for a recipe's marks moved by hand, as placed now: {} when none is far off, or when
        it cannot be told."""
        try:
            ink, placement = self.inks.get(self.master), self.placements.get(self.master)
            if ink is None or placement is None or r.missing or not r.adjust or r.standalone:
                return {}
            checked = r.checked
            parts, width = place(r, ink, placement, self.metrics(self.package))
            r.checked = checked
            if parts is None:
                return {}
            return far_marks(parts, mark_ranges(r), sorted(r.adjust), ink, self.limits(self.package),
                             float(self.package.upm), width)
        except Exception:
            return {}

    def log_far(self, recipes):
        """The letters among recipes whose marks were left far off, named in the log as warnings (far_lines);
        whether there were any."""
        far = [(r.char, found) for r in recipes for found in [self.far_reasons(r)] if found]
        try:
            upm = float(self.package.upm)
        except Exception:
            upm = 1000.0
        for line in far_lines(far, self.ak.glyph_links, self.ak.b, upm):
            self.log.add(line, "warning")
        return bool(far)

    def reversal_notes(self, r):
        """Notes for a row about mirrored components (reversal_note): one it would be built with (its
        parts as its picture placed them, each glyph that is one component replaced by the glyph it
        points to, as the build does: that is where a mirror may come from), and, for a glyph the font
        has, one its own glyph is made of."""
        found = []
        r.mirrored = []  # the mirrored components of its glyph in the font (Correct mirrored components)
        try:
            ink = self.inks.get(self.master)
            parts = getattr(r, "placed_parts", None)
            parts = [unwrapped(self.package, self.master, *part) for part in parts] if parts else None
            name = next((part[0] for part in parts or () if reverses_direction(part[1], part[2])), None)
            if name:  # (build puts a corrected glyph in its place, and warns where it could not)
                found.append(u"%s is mirrored: built with a glyph of its own in its place, mirrored with its "
                             u"contours reversed" % name)
            if r.existing:
                glyph = self.package.findName(r.existing)
                layer = glyph.getLayerByName(self.master) if glyph is not None else None
                mirrored = mirrored_components(layer) if layer is not None else []
                if mirrored:
                    r.mirrored = list(mirrored)
                    found.append(u"its glyph in the font has %s mirrored (%s): where it overlaps another part, "
                                 u"renderers show a hole, which Correct mirrored components sets right" % (
                                     u"a component" if len(mirrored) == 1 else u"components", u", ".join(mirrored)))
        except Exception:
            pass
        return found

    def correctable(self):
        """The listed glyphs of the font with mirrored components, among the rows shown: what Correct
        mirrored components sets right."""
        hidden = getattr(self, "hidden", ())
        return [r for index, r in enumerate(self.recipes)
                if r.existing and getattr(r, "mirrored", None) and index not in hidden]

    def corrector(self, package, masters, made, touched):
        """corrected(source, axis) for one run (a build, or Correct mirrored components): the name of
        source's corrected glyph, made at its first need (its name added to made, its glyph to touched) and
        used again after; a source that could not be corrected raises the same MirrorError each time."""
        found = {}

        def corrected(source, axis):
            key = (source, axis)
            if key not in found:
                try:
                    name, glyph = corrected_glyph(self.fontlab, self.ak, package, masters, source, axis)
                    if glyph is not None:
                        made.append(name)
                        touched.append(glyph)
                    found[key] = name
                except MirrorError as exc:
                    found[key] = exc
                except Exception as exc:
                    found[key] = MirrorError(u"%s" % exc)
            if isinstance(found[key], MirrorError):
                raise found[key]
            return found[key]
        return corrected

    def correct_mirrored(self):
        """The mirrored components of the listed glyphs of the font set right (relink_mirrored), in every
        master, as one step of the History; each glyph left as it was is named with why. In the window's
        top row, never stopped half way (a write)."""
        try:  # (a signal's handler: nothing may escape to Qt)
            self.work_begin(u"Correcting the mirrored components", stoppable=False)
            try:
                self.correct_mirrored_now()
            finally:
                self.work_end()
        except Exception as exc:
            self.log.add(u"Could not correct the mirrored components: %s" % self.ak.html(exc), "error")

    def correct_mirrored_now(self):
        try:
            package = self.package
            targets = self.correctable()
            if package is None or not targets:
                return
            key = self.package_key(self.current_font())
            if key is None or key != self.package_key(package):
                self.run()
                self.log.add(u"The font changed since the list was made: here is this one's. Nothing was corrected.",
                             "warning")
                return
            masters = list(package.masters) or [self.master]
            made, touched, done, failed, used, asked = [], [], [], [], set(), []
            corrected = self.corrector(package, masters, made, touched)

            def counting(source, axis):
                name = corrected(source, axis)
                asked.append(name)
                return name
            if not self.begin_write(package, existing_glyphs(package, [r.existing for r in targets])):
                return  # (nothing corrected: the reason in the log)
            status, parts, parts_status, second = None, [], None, False
            recorded_parts = {"parts": None, "status": None}

            def ensure_parts():  # (once, just before the first letter is written: a refusal records no step)
                if recorded_parts["parts"] is None:
                    recorded_parts["parts"] = list(touched)
                    recorded_parts["status"] = record_parts(self.ak, self.fontlab, package, recorded_parts["parts"],
                                                            u"FreeLab Glyph Compose mirrored components (parts)")
            try:
                # The corrected glyphs first, in a step of their own (record_parts), before any letter is pointed to
                # them: undone in one step with the letters, FontLab printed that the letters' components did not exist
                for r in targets:
                    glyph = font_glyph(package, r.existing)
                    for master in (masters if glyph is not None else []):
                        try:
                            relink_plan(self.ak, package, master, glyph, counting)  # (plans only: nothing written)
                        except MirrorError:
                            pass  # (said by the letter's own correction below)
                self.correct_targets(package, masters, targets, counting, asked, used, touched, done, failed,
                                     ensure_parts)
                parts, parts_status = recorded_parts["parts"] or [], recorded_parts["status"]
                unused = [name for name in made if name not in used]  # made for a glyph then left as it was
                for name in unused:
                    try:
                        package.deleteGlyph(font_glyph(package, name))
                    except Exception:
                        pass
                touched = [glyph for glyph in touched if u"%s" % getattr(glyph, "name", u"") not in unused]
                made = [name for name in made if name in used]
                later = [glyph for glyph in touched if all(glyph is not part for part in parts)]
                second = bool(parts) and bool(later or unused)
                if later or (parts and unused) or (touched and not parts):
                    status = self.ak.notify_changed(self.fontlab, package, u"FreeLab Glyph Compose mirrored components",
                                                    later if parts else touched)
            finally:
                self.end_write(package, bool(touched) or bool(parts))
            if parts and second:
                self.log.add(parts_step_text([u"%s" % getattr(glyph, "name", u"") for glyph in parts],
                                             self.ak.glyph_name_link))
            report_write(parts_status, self.log)
            b, html = self.ak.b, self.ak.html
            if done:
                self.log.add(corrected_text(len(done), len(made), b) + u": %s%s. The letters stay glyphs of "
                             u"components and look as they did%s." % (
                                 self.ak.glyph_links(done),
                                 (u"; added: %s" % self.ak.glyph_names_linked(made, word=None)) if made else u"",
                                 undo_words(status, u"; <i>Edit &gt; Undo</i> takes it back")),
                             "done")
            report_write(status, self.log)
            for char, why in failed:
                self.log.add(u"%s keeps a mirrored component: %s." % (b(char), html(why)), "warning")
            self.run()
        except Exception as exc:
            self.log.add(u"Could not correct the mirrored components: %s" % self.ak.html(exc), "error")

    def correct_targets(self, package, masters, targets, counting, asked, used, touched, done, failed, before_write=None):
        """Each target's mirrored components set right (relink_mirrored), in every master or none: the
        letters set right added to done, those left as they were to failed with why, the glyphs written to
        touched, and the corrected glyphs they point to now to used."""
        for at, r in enumerate(targets):
            self.work_progress(None, at / float(len(targets)), stoppable=False)
            glyph = font_glyph(package, r.existing)
            if glyph is None:
                continue
            changed, why, written = 0, None, False
            del asked[:]
            try:  # (every master or none: masters that differ would not interpolate)
                changed = relink_mirrored(self.fontlab, self.ak, package, masters, glyph, counting, before_write)
                used.update(asked)  # (the corrected glyphs a letter now points to)
            except MirrorError as exc:
                why, written = u"%s" % exc, exc.written
            except Exception as exc:
                why, written = u"%s" % exc, True
            if changed or written:
                touched.append(glyph)  # (its shapes were written, or taken out and put back)
            if changed:
                done.append(r.char)
            if why:
                failed.append((r.char, why))

    def recipe_items(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def item_of(self, recipe):
        QtCore, QtGui = _qt()
        for item in self.recipe_items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.recipes) and self.recipes[index] is recipe:
                return item
        return None

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.recipe_items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.recipes) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                self.recipes[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def shown_items(self):
        """[(item, its recipe's index)] of the checkable rows a search leaves shown (all of them without one)."""
        QtCore, QtGui = _qt()
        hidden = getattr(self, "hidden", ())
        found = []
        for item in self.recipe_items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if item.flags() & QtCore.Qt.ItemIsUserCheckable and index not in hidden:
                found.append((item, index))
        return found

    def checked_by_all(self):
        """[(item, index)] of the rows Check all checks: those shown, but a glyph the font has only once Also
        list existing glyphs is on (one listed to show it, go_to_char, is checked by hand)."""
        box = getattr(self, "existing_box", None)
        wide = box is None or bool(_property(box, "checked"))
        return [(item, index) for item, index in self.shown_items()
                if wide or not (0 <= index < len(self.recipes) and self.recipes[index].existing)]

    def check_all(self, on):
        """Every row shown checked (checked_by_all) or unchecked (rows a search hides keep their checks),
        and the log says how many, and how many are checked in all, those a search hides included."""
        QtCore, QtGui = _qt()
        state = QtCore.Qt.Checked if on else QtCore.Qt.Unchecked
        changed = 0
        self.tree.blockSignals(True)
        try:
            for item, _ in (self.checked_by_all() if on else self.shown_items()):
                if item.checkState(0) != state:
                    changed += 1
                    item.setCheckState(0, state)
        finally:
            self.tree.blockSignals(False)
        self.update_buttons()
        try:
            self.harvest()  # (the checks as the list now has them, for the count)
        except Exception:
            pass
        hidden = getattr(self, "hidden", ())
        checked = [index for index, r in enumerate(self.recipes) if r.checked and not r.missing]
        self.log.add(checks_text(on, changed, len(checked), sum(1 for index in checked if index in hidden), self.ak.b))
        self.went_on()  # (checks changed: a glyph listed to show it goes)

    # -- Compact diacritics to fit the line --------------------------------------------------

    def sync_compact(self, recipes=None):
        """Each recipe still placed as suggested follows the dialog's choice of compacting. One placed by
        hand keeps the choice it was placed under: the hand's changes are measured from that suggestion,
        so its marks stay where they were set. Put back as suggested, it follows the dialog again."""
        compact = getattr(self, "compact", True)
        for r in (self.recipes if recipes is None else recipes):
            if not r.adjust:
                r.compact = compact

    def compact_toggled(self):
        """Compact diacritics to fit the line, switched: the rows still placed as suggested take the other
        suggestion (their checks as the list first gives them, unless changed by hand); the rows placed by
        hand keep what was set. Nothing changes in the font."""
        try:  # (a signal's handler: nothing may escape to Qt)
            QtCore, QtGui = _qt()
            self.harvest()
            self.compact = bool(_property(self.compact_box, "checked"))
            self.settings[COMPACT_KEY] = self.compact
            write_settings(self.ak, self.settings)
            self.shift_cache = {}
            if not self.recipes:  # (no font, or nothing listed: the choice is kept for the next list)
                return
            by_hand = dict((r.char, r.checked) for r in self.recipes
                           if self.first_checks.get(r.char, r.checked) != r.checked)  # checks changed by hand
            kept = [r for r in self.recipes if r.adjust and not r.missing]
            for r in self.recipes:
                if r.missing or r.adjust:
                    continue
                r.compact = self.compact
                if r.char not in by_hand and not r.existing:
                    r.checked = True  # as the list first comes (placing it unchecks one too tall even compact)
            selected = self.selected()
            self.remember_list()  # (the list stays where it is: selecting the row again scrolls to it)
            self.fill()
            for r in self.recipes:
                if r.char in by_hand:
                    if r.checked != by_hand[r.char] and not r.missing:
                        r.checked = by_hand[r.char]
                        item = self.item_of(r)
                        if item is not None:
                            self.tree.blockSignals(True)
                            item.setCheckState(0, QtCore.Qt.Checked if r.checked else QtCore.Qt.Unchecked)
                            self.tree.blockSignals(False)
                elif not r.adjust:
                    self.first_checks[r.char] = r.checked  # the suggestion now
            if selected is not None:
                self.select_recipe(selected)
            self.select()
            self.restore_scroll()
            to_build = list_sections(self.recipes, self.existing_shift, getattr(self, "just_built", ()))[0][1]
            compact, _, tall = room_counts([self.recipes[index] for index in to_build])  # (as the top line counts)
            self.log.add(compact_text(self.compact, len(kept), compact if self.compact else tall, self.ak.b))
        except Exception as exc:
            self.log.add(u"Could not switch compacting: %s" % self.ak.html(exc), "error")

    # -- the high-value glyphs: Font Check's list of them, for this font ---------------------

    def font_check_settings(self, fc):
        """(nearly, statuses, inferred, composing) as Font Check's window has them, when it is open; else
        as it starts (within reach: its NEARLY_MISSING; every language; inferred ones and composed letters
        counted)."""
        nearly, statuses, inferred, composing = fc.NEARLY_MISSING, None, True, True
        try:
            window = getattr(sys, "_freelab_font_check", None)
            if window is not None and window.dialog.visible:
                nearly = int(window.nearly.value)
                statuses = window.choice(window.status_filter, fc.STATUS_FILTERS)[2]
                inferred, composing = bool(window.inferred_box.checked), bool(window.composing.checked)
        except Exception:
            pass
        return nearly, statuses, inferred, composing

    def read_high_value(self):
        """The characters Font Check lists as high-value missing glyphs for this font (a set), or None
        when its data cannot be read (said once in the log)."""
        package = self.package
        try:
            fc = self.ak.load_sibling(FONT_CHECK_FILE, FONT_CHECK_MODULE)
            nearly, statuses, inferred, composing = self.font_check_settings(fc)
            names, codes = {}, set()
            for fg in package.fgPackage.glyphs:
                for code in fc.glyph_codes(fg):
                    codes.add(code)
                    names.setdefault(code, u"%s" % fg.name)
            anchors, master = {}, self.master

            def anchors_of(code):  # (as Font Check reads them: a letter its anchors compose counts as there)
                if code not in anchors:
                    glyph = package.findName(names[code]) if code in names else None
                    layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
                    anchors[code] = set(fc.anchor_names(layer)) if layer is not None else set()
                return anchors[code]

            def attaches(base, mark):
                return bool(set(name[1:] for name in anchors_of(mark) if name.startswith(u"_")) & anchors_of(base))

            return high_value_characters(fc, codes, attaches if composing else None, nearly, statuses, inferred)
        except Exception as exc:
            if not getattr(self, "high_value_failed", False):
                self.high_value_failed = True
                self.log.add(u"<i>Font Check</i>'s high-value glyphs could not be read: %s" % self.ak.html(exc), "warning")
            return None

    def high_value_stamp(self):
        """What the high-value set was read for: the font, and how many glyphs it has (a build adds some)."""
        try:
            return self.package_key(self.package), self.package.glyphsCount
        except Exception:
            return None

    def ask_high_value_soon(self):
        """Font Check asked once the list is shown (its languages take a moment to read), and again only
        when the font or its glyph count changed."""
        QtCore, QtGui = _qt()
        if self.package is None or getattr(self, "high_value_due", False):
            return
        if getattr(self, "high_value_key", None) == self.high_value_stamp() and self.high_value_key is not None:
            return
        self.high_value_due = True
        QtCore.QTimer.singleShot(0, self.ask_high_value)

    def ask_high_value(self):
        try:  # (a timer's slot: nothing may escape to Qt)
            self.high_value_due = False
            if self.package is None:
                return
            self.high_value = self.read_high_value()
            self.high_value_key = self.high_value_stamp()
            if value_filter(getattr(self, "value_only_box", None), self.high_value) is not None:
                self.apply_search()  # (List only high-value glyphs ticked: the list follows the set read now)
            self.update_buttons()
            generation = getattr(self, "generation", None)
            if generation:  # (Glyph generation's tab reads the same set: its buttons and its filter follow)
                generation.high_value_read()
        except Exception:
            self.high_value = None

    def high_value_checks(self):
        """{recipe index: whether Check only high-value glyphs would check it}, for the rows shown; {} when
        Font Check's set is not known or none of them is in it."""
        wanted = getattr(self, "high_value", None)
        if not wanted:
            return {}
        found = dict((index, self.recipes[index].char in wanted) for _, index in self.shown_items())
        return found if any(found.values()) else {}

    def check_high_value(self):
        """The rows shown checked where Font Check lists their glyph as high-value, unchecked elsewhere."""
        QtCore, QtGui = _qt()
        try:  # (a signal's handler: nothing may escape to Qt)
            wanted = self.high_value_checks()
            if not wanted:
                return
            self.tree.blockSignals(True)
            try:
                for item, index in self.shown_items():
                    item.setCheckState(0, QtCore.Qt.Checked if wanted.get(index) else QtCore.Qt.Unchecked)
            finally:
                self.tree.blockSignals(False)
            self.update_buttons()
            self.went_on()  # (checks changed: a glyph listed to show it goes)
            self.log.add(high_value_text(sum(1 for on in wanted.values() if on), self.ak.b))
        except Exception as exc:
            self.log.add(u"Could not tick the high-value glyphs: %s" % self.ak.html(exc), "error")

    def update_buttons_soon(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        QtCore, QtGui = _qt()
        self.buttons_due = False
        ak = self.ak
        items = [item for item in self.recipe_items() if item.flags() & QtCore.Qt.ItemIsUserCheckable]
        some_on, _ = ak.checks_of(items, lambda item: item.checkState(0) == QtCore.Qt.Checked)
        shown = self.shown_items()  # (Check all and Check none act on the rows a search leaves shown)
        shown_on, _ = ak.checks_of([item for item, _ in shown], lambda item: item.checkState(0) == QtCore.Qt.Checked)
        _, shown_off = ak.checks_of([item for item, _ in self.checked_by_all()],
                                    lambda item: item.checkState(0) == QtCore.Qt.Checked)
        ak.enable(self.all_button, shown_off)
        ak.enable(self.none_button, shown_on)
        ak.enable(self.build_button, some_on and self.package is not None)
        # with no font, the choices that make the list do nothing; with no row, the search finds nothing
        search = getattr(self, "search", None)
        controls = list_controls(self.package is not None, len(self.recipes),
                                 search is not None and bool(u"%s" % (_property(search, "text") or u"")))
        for widget in (getattr(self, "set_box", None), getattr(self, "existing_box", None),
                       getattr(self, "compact_box", None)):
            ak.enable(widget, controls["choices"])
        ak.enable(search, controls["search"])
        self.harvest()
        if getattr(self, "hand_over_key", None) is not None:  # (Font Check's list's checks, kept for the session)
            self.remember_checks([(r.char, r.checked) for r in self.recipes if not r.missing])
        # Build builds every checked glyph, those a search hides too: the count beside the search says how many
        # are not shown (search_count; on the button, it made the window wider: owner's images 331 and 332)
        hidden = getattr(self, "hidden", ())
        buildable = [(index, r) for index, r in enumerate(self.recipes) if not r.missing and r.checked]
        self.build_button.setText(build_text(len(buildable), 0))
        args = getattr(self, "count_args", None)
        if args is not None and getattr(self, "search_label", None) is not None:
            show_count(self.search_label, search_count(args[0], args[1], args[2], filtered=args[3],
                                                       ticked_hidden=sum(1 for index, _ in buildable if index in hidden)))
        correctable = self.correctable()
        ak.enable(self.correct_button, bool(correctable) and self.package is not None)
        self.correct_button.setText(correct_button_text(len(correctable)))
        wanted = self.high_value_checks()  # (grayed when it would change nothing, as the others are)
        ak.enable(self.value_button, any(self.recipes[index].checked != on for index, on in wanted.items()))
        box = getattr(self, "value_only_box", None)  # (once Font Check's set is known; ticked, it can be unticked)
        ak.enable(box, box is not None and (getattr(self, "high_value", None) is not None and self.package is not None
                                            or bool(_property(box, "checked"))))
        ak.enable(self.restore_button, any(r.adjust or self.first_checks.get(r.char, r.checked) != r.checked
                                           for r in self.recipes))
        r = self.selected()
        ak.enable(self.glyph_window_button, r is not None and self.glyph_to_show(r) is not None)
        ak.enable(self.reset_marks_button, r is not None and bool(r.adjust))
        targets = self.propagation_targets(r) if r is not None and not r.missing else []
        # Grayed once applied, until the mark is moved again; never while a related letter holds a placement
        # this glyph's mark, back at the suggestion, does not (a reset here can then be applied to them)
        ak.enable(self.propagate_button, self.can_propagate(r, targets))
        built = self.kerning_names()
        ak.enable(self.kerning_button, bool(built))
        self.kerning_button.setText(u"Check kerning of this glyph" if len(built) == 1 else u"Check kerning of these glyphs")
        self.propagate_button.setText(propagate_text(len(set(id(t) for t, _, _ in targets))))
        self.reset_marks_button.setText(reset_text(len(r.marks) if r is not None else 0))
        index = self.line_up_index(r)
        ak.enable(self.line_up_button, index is not None)
        kind = attached_kind(r.marks[index]) if index is not None else None
        self.line_up_button.setText(line_up_text(kind, r.marks[index].side if index is not None else None))

    def line_up_index(self, r):
        """The mark of r to line others up with: the one selected in the editor, else its first above or
        below; None when it has none that can be (its own rule, stacked)."""
        if r is None or r.missing:
            return None
        chosen = self.editor.selected
        order = ([chosen] if chosen is not None and chosen < len(r.marks) else []) + list(range(len(r.marks)))
        for index in order:
            if line_up_exclusion(r, index) is None or attached_kind(r.marks[index]):
                return index
        return None

    def line_up(self):
        """Every mark of the selected one's group set at its height (line_up_plan); the others named."""
        r = self.selected()
        index = self.line_up_index(r)
        ink, placement = self.inks.get(self.master), self.placements.get(self.master)
        if index is None or ink is None or placement is None:
            return
        b, html = self.ak.b, self.ak.html
        try:
            line, moves, left_out = line_up_plan(self.recipes, r, index, ink, placement, self.metrics(self.package),
                                                 float(self.package.upm))
        except Exception as exc:
            self.log.add(u"Could not line up the diacritics: %s" % html(exc), "error")
            return
        if line is None:
            return
        side = r.marks[index].side
        kind = attached_kind(r.marks[index])
        edge = (ATTACHED_EDGES[kind] if kind else (u"bottom" if side == "above" else u"top"))
        if kind:
            side = u"(%ss)" % kind
        group = u"capitals" if case_of(r.char) == "upper" else u"lowercase letters"
        for other, at, rise in moves:
            change = list(other.adjust.get(at, [0.0, 0.0, 1.0, 1.0]))
            change[1] += rise
            other.adjust[at] = change
        close = []
        for other, _, _ in moves:
            other.touches = self.closeness(other)
            if other.touches:
                close.append((other.char, other.touches))
            item = self.item_of(other)
            if item is not None:
                self.tree.blockSignals(True)
                self.refresh_item(item, other)
                self.tree.blockSignals(False)
        if moves:
            far = [other for other, _, _ in moves if self.far_reasons(other)]  # (lined up with a mark far off)
            self.log.add(u"Lined up the diacritics %s of %s with %s's %s (its %s at %s): %s." % (
                side, b(counted(len(moves), group[:-1] if len(moves) == 1 else group)), b(r.char),
                html(r.marks[index].root), edge, b(int(round(line))),
                self.ak.glyph_links([other.char for other, _, _ in moves])), "warning" if far else "done")
            self.log_far(far)
        else:
            self.log.add(u"The diacritics %s of the %s like %s already sit at its height." % (side, group, b(r.char)))
        by_reason = {}
        for other, why in left_out:
            by_reason.setdefault(why, []).append(other.char)
        for why, chars in sorted(by_reason.items()):
            self.log.add(u"Left as they are, %s: %s." % (why, self.ak.glyph_links(chars)), "warning")
        self.log_touches(close, "now")
        self.select()
        self.update_buttons()

    def restore(self):
        """Every check and every mark as the list first came."""
        for r in self.recipes:
            r.adjust, r.applied = {}, None
            r.checked = self.first_checks.get(r.char, r.checked)
        self.sync_compact()
        for r in self.recipes:  # measured again as suggested: an overlap from a moved mark is gone with it
            r.touches = self.closeness(r) if not r.missing else u""
        self.remember_list()
        self.fill()
        self.select()
        self.restore_scroll()
        self.log.add(u"Ticks and diacritics restored as suggested.")

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.recipes[index] if 0 <= index < len(self.recipes) else None

    def in_font(self, r):
        glyph = self.package.findName(r.name) if self.package is not None and r.name else None
        return glyph is not None and not is_empty(glyph)

    def say_handed_over(self):
        """The log's line on what Font Check handed over to each tab, when it handed over to both, or to
        Glyph generation alone."""
        b = self.ak.b
        others = counted(len(self.generation_given), u"other glyph")
        if self.given:
            letters = counted(len(self.given), u"letter with diacritics", u"letters with diacritics")
            here = u"Glyph generation" if len(self.generation_given) >= len(self.given) else u"Diacritics"
            why = u"as many on each" if len(self.generation_given) == len(self.given) else u"the tab with more"
            self.log.add(u"From %s: %s on the <i>Diacritics</i> tab and %s on <i>Glyph generation</i> (shown "
                         u"first: <i>%s</i>, %s)." % (tool_named(self.ak, FONT_CHECK_TITLE), b(letters), b(others),
                                                      here, why))
        else:
            self.log.add(u"From %s: %s, on <i>Glyph generation</i>." % (tool_named(self.ak, FONT_CHECK_TITLE), b(others)))

    # -- what Font Check handed over, kept for the session (hand_over_memory: owner's report 186) ----------

    def lists_hand_over(self, tab):
        """Whether a tab lists what Font Check handed over now: the Diacritics tab on From Font Check
        ("letters"), Glyph generation's List on From Font Check ("others")."""
        if tab == "letters":
            return bool(getattr(self, "given", None)) and _property(self.set_box, "currentIndex") == 0
        generation = getattr(self, "generation", None)
        return bool(getattr(self, "generation_given", None)) and bool(generation) and \
            generation.listed_codes() is not None

    def take_kept_checks(self, rows, char_of, tab="letters"):
        """The checks the window before left on Font Check's list, given to a tab's rows (rows: those that
        can be built; char_of(row): its character) as the tab first reads it, once; True when one changed. A
        window opened on another font than the list's takes none."""
        kept = getattr(self, "kept_checks", None)
        taken = getattr(self, "kept_taken", None)
        if taken is None:
            taken = self.kept_taken = set()
        if not kept or tab in taken or not self.lists_hand_over(tab):
            return False
        font_id = getattr(self, "font_id", None)
        if font_id is not None and font_id != getattr(self, "hand_over_key", None):
            return False
        taken.add(tab)
        changed = False
        for row in rows:
            on = kept.get(char_of(row))
            if on is not None and bool(on) != bool(row.checked):
                row.checked = bool(on)
                changed = True
        return changed

    def remember_checks(self, pairs, tab="letters"):
        """[(character, checked)] of a tab's rows kept with Font Check's list for the session, those it
        handed over only; not before the tab has taken the checks kept (the suggestions it shows first would
        overwrite them). Never raises."""
        try:
            key = getattr(self, "hand_over_key", None)
            kept = hand_over_memory().get(key) if key is not None else None
            if kept is None or not self.lists_hand_over(tab):
                return
            if getattr(self, "kept_checks", None) and tab not in (getattr(self, "kept_taken", None) or ()):
                return
            given = set(getattr(self, "given", None) or ()) | set(getattr(self, "generation_given", None) or ())
            kept.setdefault("checks", {}).update((ch, bool(on)) for ch, on in pairs if ch in given)
        except Exception:
            pass

    def set_item_checks(self):
        """The list's check boxes as the recipes' checks are now (no signal), and the buttons."""
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        try:
            for item in self.recipe_items():
                index = int(item.data(0, QtCore.Qt.UserRole))
                if 0 <= index < len(self.recipes) and item.flags() & QtCore.Qt.ItemIsUserCheckable:
                    item.setCheckState(0, QtCore.Qt.Checked if self.recipes[index].checked else QtCore.Qt.Unchecked)
        finally:
            self.tree.blockSignals(False)
        self.update_buttons()

    def hand_over_state(self):
        """(whether the window still lists what Font Check handed over, the glyphs handed over still to be
        built): the Diacritics tab on From Font Check (where it was handed letters), Glyph generation's List
        on From Font Check (where it was handed others; a tab not opened yet lists them so), and the handed
        glyphs a tab can still build that the font lacks. (False, []) for a window opened from the menu."""
        given, others = list(getattr(self, "given", None) or []), list(getattr(self, "generation_given", None) or [])
        if not given and not others:
            return False, []
        showing = not given or _property(self.set_box, "currentIndex") == 0
        left = [r.char for r in self.recipes if r.char in given and not r.missing and not r.existing]
        generation = getattr(self, "generation", None)
        if others:
            if generation:
                showing = showing and generation.listed_codes() is not None
                left += [r.char for r in generation.rows if r.char in others and r.layout is not None and not r.existing]
            else:  # (its tab not opened yet: what the font still lacks of them is left)
                left += [ch for ch in others if self.package is None or self.package.findUnicode(ord(ch)) is None]
        return showing, left

    def back_to_font_check(self, failed=False):
        """After a build from Font Check's hand-over: Font Check opened again in this window's place (the
        owner's report of 2026-11-16: back to it once its glyphs are built), when the window still lists
        what was handed over, nothing of it is left to build, and nothing failed (else the window stays, its
        log saying what is left). Font Check reads the font afresh, the glyphs built no longer missing.
        Whether it was asked to."""
        try:
            showing, left = self.hand_over_state()
            if not back_to_font_check_due(showing, left, failed):
                return False
            QtCore, QtGui = _qt()
            QtCore.QTimer.singleShot(0, lambda: self.ak.open_tool(FONT_CHECK_TITLE, self.dialog))
            return True
        except Exception:
            return False

    def line_up_rows(self):
        """Every tab's options row over its list made as tall as the tallest of them (brief 23, owner's images
        285 and 286: switching tabs never moves the list): the Mark anchors row keeps its dropdown's height with
        the dropdown hidden (a font with marks of one script, or none), and Glyph generation's widths row, where
        the Diacritics tab has its own tab bar, is as tall as that bar. Each row only ever made taller (a strut
        per height). Never raises."""
        try:
            anchors = getattr(self, "anchors", None)
            generation = self.generation if getattr(self, "generation", None) else None
            rows = [getattr(self, "options_row", None), getattr(anchors, "options_row", None)]
            controls = [getattr(self, "set_box", None), getattr(self, "search", None),
                        getattr(anchors, "script_box", None), getattr(anchors, "search", None)]
            if generation is not None:
                rows.append(getattr(generation, "options_row", None))
                controls += [getattr(generation, "search", None), getattr(generation, "list_box", None)]
                controls += list((getattr(generation, "spins", None) or {}).values())
            height = row_height([control for control in controls if control is not None])
            if not height:
                return
            struts = self.__dict__.setdefault("row_struts", {})

            def raise_to(row, wanted):
                if row is not None and struts.get(id(row), 0) < wanted:
                    row.addStrut(int(wanted))
                    struts[id(row)] = wanted
            for row in rows:
                raise_to(row, height)
            if generation is not None:
                bar = row_height([self.tabs])
                top = max(bar, height)
                raise_to(getattr(generation, "settings_row", None), top)
                if bar and bar < top:
                    self.tabs.setMinimumHeight(int(top))
        except Exception:
            pass

    def switch_top_page(self, index):
        """Diacritics or Glyph generation shown; Glyph generation's tab made, and its list read, as it is
        first shown (its module loaded then: where it cannot be, the tab says why)."""
        QtCore, QtGui = _qt()
        self.top_pages.setCurrentIndex(index)
        self.show_tab_parts()
        if index != 1 or self.generation is not None:
            self.line_up_rows()
            return
        try:
            module = self.generation_module = self.ak.load_sibling(GENERATION_FILE, GENERATION_MODULE)  # (held)
            self.generation = module.GenerationPage(self, _Globals(globals()))
            self.generation_layout.addWidget(self.generation.widget, 1)
            QtCore.QTimer.singleShot(0, self.generation.run)  # (read as the tab is first shown)
        except Exception as exc:
            self.generation = False  # (not tried again: the tab keeps its message)
            note = QtGui.QLabel(u"Glyph generation could not be opened: %s. Reinstall FreeLab." % self.ak.html(exc))
            note.setWordWrap(True)
            note.setWhatsThis(u"Why this tab is empty: its part of FreeLab could not be loaded.")
            self.generation_layout.addWidget(note)
            self.generation_layout.addStretch(1)
        self.show_tab_parts()  # (the new tab's status lines and buttons, made just now)
        self.line_up_rows()  # (its rows as tall as the Diacritics tab's: brief 23)

    def switch_page(self, index):
        QtCore, QtGui = _qt()
        self.pages.setCurrentIndex(index)
        self.show_tab_parts()
        self.line_up_rows()  # (sized once the window is up: brief 23)
        if index == 1 and (not self.anchors_read or getattr(self.anchors, "anchors_stopped", False)):
            self.anchors_read = True
            # read as the tab is first shown (and again when its reading was stopped: it says so)
            QtCore.QTimer.singleShot(0, self.anchors.run)

    # -- the dialog's own writes, told apart from the History moving in FontLab -----------------------

    def begin_write(self, package, glyphs=(), coverage=False):
        """Before a write to the font (Build, Correct mirrored components, Add anchors, Build checked
        glyphs on Glyph generation): the History watch held (watch_history skips while busy), the font
        recorded where Undo needs it (before_changes; glyphs: those whose own properties the write
        changes, such as their code points, recorded too: recorded with the font alone, a code point
        added stayed on Undo, live 2026-11-16), and where the History stands then noted. True when the
        write may go ahead; False, with the reason in the log, when FontLab's History could not record
        the font first: nothing may be written then (Undo could not take it back). coverage: a write that
        adds glyphs or code points (the builds): the font info is updated to match it (Auto Kerning's
        notify_changed)."""
        self.busy = True
        try:
            self.ak.before_changes(self.fontlab, package, u"FreeLab Glyph Compose", list(glyphs), coverage)
        except getattr(self.ak, "HistoryError", Exception) as exc:
            self.busy = False
            self.log.add(u"%s" % (exc,), "error")
            return False
        self.write_from = self.history_of(package)
        return True

    def history_of(self, package):
        """Where the font stands in FontLab's History (Auto Kerning's history_mark), or None."""
        try:
            return self.ak.history_mark(package)
        except Exception:
            return None

    def end_write(self, package, wrote=True):
        """After a write: the History as it stands now is this dialog's own (seen_history), so that the
        watch does not read the write as an edit made in FontLab. Where FontLab has not recorded the
        step yet (the History still where it stood before), the next move within OWN_WRITE_SECONDS is
        taken to be it. Every write goes through here; Add anchors once did not, and its own step was
        logged as "The font's History moved" (the owner's report of 2026-11-14). wrote: whether anything
        was written (a write of nothing makes no step, and an undo just after it would go unsaid)."""
        try:
            now = self.history_of(package)
            self.seen_history = now
            self.own_write = (time.time(), now) if wrote and now is not None and now == getattr(self, "write_from", None) \
                else None
        finally:
            self.busy = False

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (Auto Kerning's
        fonts_tick calls it): both tabs read as at opening, the new font afresh (run: nothing of the old
        font's checks, moves, glyphs shown, or glyphs built carries over), or the no-font state shown."""
        try:  # (what Font Check handed over for a font closed since is forgotten: hand_over_memory)
            kept_hand_over(hand_over_memory(), None, None, self.ak.open_font_ids(self.fontlab.flWorkspace.instance()))
        except Exception:
            pass
        try:  # (a timer's call: nothing may escape to Qt)
            self.held_font, self.own_write = None, None
            self.run()
            if getattr(self, "anchors_read", False):
                self.anchors.run()  # (the new font's scripts, not the old one's choice)
            if getattr(self, "generation", None):
                self.generation.run(same_font=False)
        except Exception as exc:
            self.log.add(u"Could not read the font: %s" % self.ak.html(exc), "error")

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again (checks and marks moved by hand
        kept). The step of this dialog's own write, recorded late by FontLab, is read again quietly."""
        own, self.own_write = getattr(self, "own_write", None), None
        if own is None or not 0 <= time.time() - own[0] < OWN_WRITE_SECONDS:
            self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()
        if self.anchors_read:
            self.anchors.run(keep_script=True)
        if getattr(self, "generation", None):
            self.generation.run()

    # -- the editor ----------------------------------------------------------------

    def strip_signature(self, r):
        """The mark the strip follows: kept while going through the strip's own letters (a letter with
        two marks keeps the strip on the mark it was reached by), else the selected or first mark."""
        kept = getattr(self, "strip_kept", None)
        if kept is not None and r is not None and any(mark_signature(m) == kept for m in r.marks):
            return kept
        if r is None or r.missing or not r.marks:
            return None
        chosen = self.editor.selected
        mark = r.marks[chosen] if chosen is not None and chosen < len(r.marks) else r.marks[0]
        return mark_signature(mark)

    def fill_strip(self, r):
        """The related letters' buttons (made once, reused: a button made here is never deleted): those
        with the mark alone, then, after a bar, those with it among other marks."""
        QtCore, QtGui = _qt()
        signature = self.strip_signature(r)
        self.strip_kept = signature
        alone, combined = same_mark_recipes(self.recipes, signature) if signature else ([], [])
        related = alone + ([None] if alone and combined else []) + combined
        while len(self.strip_buttons) < len(related):
            button = QtGui.QToolButton()
            button.setAutoRaise(True)
            helped(button, STRIP_HELP)  # (each letter's button says what the strip is: not the whole dialog's help)
            button.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its colors set here, from the dialog's palette
            font = QtGui.QFont(button.font)
            font.setPointSizeF(font.pointSizeF() * 1.3)
            button.setFont(font)
            index = len(self.strip_buttons)
            slot = (lambda at: lambda *args: self.strip_clicked(at))(index)
            self.strip_slots.append(slot)
            button.connect("clicked()", slot)
            self.strip_layout.insertWidget(index, button)
            self.strip_buttons.append(button)
        self.strip_recipes = related
        palette = self.dialog.palette
        accent = palette.color(QtGui.QPalette.Highlight).name()
        text = palette.color(QtGui.QPalette.WindowText).name()
        quiet = palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText).name()
        warn = u"#d9a13b"
        for at, button in enumerate(self.strip_buttons):
            if at >= len(related):
                button.hide()
                continue
            other = related[at]
            if other is None:  # the bar between letters with the mark alone and with it among others
                button.setText(u"|")
                button.setToolTip(u"After the bar: letters with this diacritic among others.")
                button.setStyleSheet(u"QToolButton { border: none; color: %s; }" % quiet)
                button.setEnabled(False)
                button.show()
                continue
            self.ak.enable(button, True)  # (through enable: never over the grayed state of a window with no font)
            button.setText(other.char)
            far = getattr(other, "far", u"")
            dotted = kept_dotted(other)  # (the dot of i kept under the diacritic: a collision too)
            state = ([u"moved by hand"] if other.adjust else []) + ([other.base_note] if dotted else []) + (
                [other.touches] if other.touches else []) + ([far] if far else [])  # (amber: too close, apart, far)
            button.setToolTip(u"%s: %s%s" % (other.name, other.describe(),
                                             (u" (%s)" % u"; ".join(state)) if state else u""))
            color = text if other is not r else accent
            if other.touches or far or dotted:
                color = warn
            border = (u"border: none; border-bottom: 2px solid %s;" % accent) if other is r else u"border: none;"
            weight = u"font-weight: bold;" if other.adjust or other is r else u""
            button.setStyleSheet(u"QToolButton { %s color: %s; %s padding: 1px 3px; }" % (border, color, weight))
            button.show()
        self.strip_label.setEnabled(bool(related))
        current = related.index(r) if r in related else -1
        if current >= 0:
            self.strip_area.ensureWidgetVisible(self.strip_buttons[current])
        return bool(related)  # (the strip is shown only with letters in it: show_preview_parts)

    def strip_clicked(self, at):
        try:
            related = getattr(self, "strip_recipes", [])
            if 0 <= at < len(related) and related[at] is not None:
                item = self.item_of(related[at])
                if item is not None:
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
        except Exception as exc:
            self.log.add(u"Could not select that letter: %s" % self.ak.html(exc), "error")

    def existing_shift(self, r):
        """(dx, dy) from the font's mark to the suggested one, rounded (0, 0: placed as suggested), for a
        listed glyph the font has, built of components; None when it is drawn (compared by eye)."""
        cache = getattr(self, "shift_cache", None)
        if cache is None:
            cache = self.shift_cache = {}
        key = (r.char, repr(sorted(r.adjust.items())), getattr(r, "compact", True))
        if key in cache:
            return cache[key]
        result = None
        ink, placement = self.inks.get(self.master), self.placements.get(self.master)
        try:
            glyph = self.package.findName(r.existing) if r.existing else None
            layer = glyph.getLayerByName(self.master) if glyph is not None else None
            marks = component_marks(layer) if layer is not None else []
            if marks and ink is not None and placement is not None and r.marks:
                current = parts_box(marks, ink)
                suggested = None
                ranges = mark_ranges(r)
                checked = r.checked
                parts, _ = place(r, ink, placement, self.metrics(self.package))
                r.checked = checked
                if parts is not None:
                    suggested = parts_box(parts[ranges[0][0]:ranges[-1][1]], ink)
                if current is not None and suggested is not None:
                    above = r.marks[0].side != "below"
                    dx = round((suggested[0] + suggested[2]) / 2.0 - (current[0] + current[2]) / 2.0)
                    dy = round((suggested[1] - current[1]) if above else (suggested[3] - current[3]))
                    result = (int(dx), int(dy))
        except Exception:
            result = None
        cache[key] = result
        return result

    def keep_preview_room(self):
        """The parts of ROOM_KEPT keep their room when hidden (QSizePolicy's retainSizeWhenHidden, as Auto
        Kerning's _keep_room_when_hidden sets it, without its fallback of disabling the widget): Compact
        diacritics to fit the line and the line beside it stay where they are, whatever is selected."""
        for name in ROOM_KEPT:
            widget = getattr(self, name, None)
            if widget is not None:
                try:
                    policy = _property(widget, "sizePolicy")
                    policy.setRetainSizeWhenHidden(True)
                    widget.setSizePolicy(policy)
                except Exception:
                    pass  # (an older Qt: the parts move as before)
        # The buttons beside the box as wide as their widest text: their texts change with the row selected
        # ("Apply to 3 related letters", "Line up diacritics above"), and their room kept while hidden was the
        # width of the text they last had, so the box still moved 33 pixels (live, 2026-11-16)
        for name, texts in room_texts().items():
            button = getattr(self, name, None)
            if button is None:
                continue
            try:
                shown = _property(button, "text")
                widths = []
                for text in texts:
                    button.setText(text)
                    widths.append(int(_property(button, "sizeHint").width()))
                button.setText(shown)
                button.setMinimumWidth(max(widths))
            except Exception:
                pass

    def show_preview_parts(self, r, placed=True, related=True):
        """The preview's parts shown only where they show something (the owner's report of 2026-11-14:
        "Same diacritic:" and the Reference heading over an empty area, with no glyph selected): the
        reference, its chooser, and the line under the editor once a row is selected; the editor and its
        buttons for a glyph it can draw (placed); the strip of letters with the same diacritic when it has
        letters (related). preview_parts says which."""
        shown = preview_parts(r is not None, r is not None and not r.missing and placed, related)
        for name, on in shown.items():
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(on)

    def select(self):
        r = self.selected()
        self.editor.selected = None
        related = self.fill_strip(r)
        if r is None or r.missing:
            self.editor.scene = None
            self.editor.update()
            self.show_preview_parts(r, related=related)
            self.hint.setText(u"Select a glyph that can be built to place its diacritics." if r is None else
                              u"%s %s." % (r.char, r.describe()))
            self.draw_reference(r)
            self.update_buttons()
            if r is not None and r.char not in getattr(self, "shown_existing", ()):
                self.drop_revealed_soon(r, REVEALED_WAIT_MS)  # (moved on: a glyph listed to show it goes)
            return
        self.editor.scene = self.scene(r)
        self.editor.update()
        self.show_preview_parts(r, self.editor.scene is not None, related)
        self.hint.setText(u"Click a diacritic to move or scale it." if self.editor.scene is not None else
                          u"%s %s." % (r.char, r.describe()))
        self.draw_reference(r)
        self.update_buttons()
        if r.char not in getattr(self, "shown_existing", ()):  # moved on: a glyph listed to show it goes
            self.drop_revealed_soon(r, REVEALED_WAIT_MS)

    def scene(self, recipe):
        """What the editor draws: the recipe placed, between its letter and a sibling; its marks' ranges;
        the room of a 120% line."""
        ink = self.inks.get(self.master)
        placement = self.placements.get(self.master)
        if ink is None or ink(recipe.base) is None:
            return None
        checked = recipe.checked
        parts, width = place(recipe, ink, placement, self.metrics(self.package))
        recipe.checked = checked
        if parts is None:
            return None
        glyphs, captions = [], {}
        base_char = unicodedata.normalize("NFD", recipe.char)[0]
        letter = self.font_read().glyph_for(base_char)
        if recipe.existing and ink.path(recipe.existing)[0] is not None:  # the font's own, to compare
            glyphs.append(([(recipe.existing, 1.0, 1.0, 0.0, 0.0)], ink.path(recipe.existing)[1], "existing"))
            shift = self.existing_shift(recipe)
            captions = {"existing": u"Current", "new": suggested_caption(shift)}
        elif letter:
            glyphs.append(([(letter, 1.0, 1.0, 0.0, 0.0)], ink.path(letter)[1], "before"))
        glyphs.append((parts, width, "new"))
        sibling, sibling_char = self.sibling(recipe)
        if sibling:
            glyphs.append(([(sibling, 1.0, 1.0, 0.0, 0.0)], ink.path(sibling)[1], "after"))
        metrics = self.metrics(self.package)
        upm = float(self.package.upm)
        top = (metrics.top if metrics else upm) + upm * 0.05
        bottom = (metrics.bottom if metrics else -0.3 * upm) - upm * 0.05
        limits = self.limits(self.package)
        # The lines near the glyph are kept in view (a winAscent set far off would shrink the glyph for a line)
        near = [line[0] for line in limits if -0.6 * upm <= line[0] <= 1.5 * upm]
        if near:
            top, bottom = max(top, max(near) + upm * 0.05), min(bottom, min(near) - upm * 0.05)
        # ... and the glyph's own ink, a mark moved by hand too, as far as VIEW_REACH past those: a mark
        # moved farther is outside the view (an arrow at the edge), and the glyph keeps its size
        box = parts_box(parts, ink)
        top, bottom = view_bounds(top, bottom, max(box[3], 0), box[1], upm, upm * 0.05)
        return {"glyphs": glyphs, "parts": parts, "ranges": mark_ranges(recipe), "ink": ink, "upm": upm,
                "top": top, "bottom": bottom, "room": (metrics.top, metrics.bottom) if metrics else (),
                "limits": limits or None, "warning": self.warning_rgb,  # (no limits read: the room's two lines)
                "letters": (letter, sibling), "chars": {"after": sibling_char}, "captions": captions}

    def adjust_of(self, index):
        r = self.selected()
        return list(r.adjust.get(index, [0.0, 0.0, 1.0, 1.0])) if r is not None else [0.0, 0.0, 1.0, 1.0]

    def snap_targets(self, index):
        """[(x, label)] of the centers the selected glyph's mark index snaps to while dragged, in the glyph's
        units: its letter's ink box center and top (bottom) center."""
        r, scene = self.selected(), self.editor.scene
        if r is None or scene is None or index is None or index >= len(r.marks):
            return []
        base = scene["parts"][0]
        return letter_centers(scene["ink"](base[0]), base[3], r.marks[index].side)

    def set_adjust(self, index, change, final):
        """A mark moved or scaled by hand: drawn at once; its row's picture redrawn when done."""
        r = self.selected()
        if r is None or index is None:
            return
        # Kept to what a font can hold (HAND_REACH, SCALE_REACH), and to finite numbers: a move that was
        # not one once stopped everything after it (the line under the picture kept the last number it
        # could write, and the buttons never heard the mark had moved, Reset diacritic staying grayed)
        dx, dy, kx, ky = clamped_adjust(change)
        started = getattr(self, "adjust_from", None)  # (r, index, its adjustment as the move began)
        if started is None or started[0] is not r or started[1] != index:
            started = self.adjust_from = (r, index, list(r.adjust[index]) if index in r.adjust else None)
        if abs(dx) < 0.01 and abs(dy) < 0.01 and abs(kx - 1) < 1e-4 and abs(ky - 1) < 1e-4:
            r.adjust.pop(index, None)
        else:
            r.adjust[index] = [round(dx, 2), round(dy, 2), round(kx, 4), round(ky, 4)]
        self.sync_compact([r])
        moved = final and r.adjust.get(index) != started[2]
        if final:
            self.held_font = None
            self.adjust_from = None
            if moved and not r.missing:
                r.checked = True  # moved or scaled by hand: to be built (the owner's report of 2026-11-16)
        elif getattr(self, "held_font", None) is None:  # the font read once for the whole drag, not at every move
            self.held_font = self.font(self.package)
        try:
            self.editor.scene = self.scene(r)
            self.editor.update()
            self.mark_selected(index)
        finally:  # (whatever the picture did: a finished move reaches its row and the buttons)
            if final:
                try:
                    item = self.item_of(r)
                    if item is not None:
                        self.tree.blockSignals(True)
                        self.refresh_item(item, r)
                        if moved and r.checked and item.flags() & _qt()[0].Qt.ItemIsUserCheckable:
                            item.setCheckState(0, _qt()[0].Qt.Checked)  # (so that Build checked glyphs builds it)
                        self.tree.blockSignals(False)
                finally:
                    self.update_buttons()

    def mark_selected(self, index):
        r = self.selected()
        if r is None or index is None or index >= len(r.marks):
            self.hint.setText(u"Click a diacritic to move or scale it.")
            return
        self.hint.setText(mark_line(self.ak.html(r.marks[index].label()), self.adjust_of(index),
                                    index in self.editor.outside() if hasattr(self.editor, "outside") else False))

    # -- a placement made by hand, applied to the related letters ---------------------

    def propagation_targets(self, r):
        """[(recipe, its mark index, the selected recipe's mark index or None)] Apply to related letters
        would change: for each of the selected recipe's marks moved by hand, the same mark of every
        related letter (its index given); for each of its marks at the suggestion, the same mark of the
        related letters that hold a placement made by hand (None: theirs is put back too, so a reset
        here can be applied to them)."""
        found = []
        for index in range(len(r.marks)):
            moved = index in r.adjust
            for other, at in related_marks(self.recipes, r, index):
                if moved:
                    found.append((other, at, index))
                elif at in other.adjust:
                    found.append((other, at, None))
        return found

    @staticmethod
    def can_propagate(r, targets):
        """Whether Apply to related letters would do something: there are letters to change, and the
        placement was not applied already (unless some still hold a placement to put back)."""
        return bool(targets) and (r.applied != r.adjust or any(index is None for _, _, index in targets))

    def propagate(self):
        """The selected letter's diacritics, as moved and scaled by hand, given to the related letters
        (those back at the suggestion put the related letters' back too); those whose mark then comes too
        close to their letter or another mark named."""
        r = self.selected()
        if r is None or r.missing:
            return
        targets = self.propagation_targets(r)
        if not targets:
            return
        ink, placement = self.inks.get(self.master), self.placements.get(self.master)
        metrics = self.metrics(self.package)
        touched, close, put_back = [], [], []
        for other, at, index in targets:
            if index is None:  # this glyph's mark is at the suggestion: so is theirs now
                other.adjust.pop(at, None)
                other.applied = None
                if other not in put_back:
                    put_back.append(other)
            else:
                change = r.adjust[index]
                try:  # its offset from its letter's center, not the change as it is (centered stays centered)
                    other.adjust[at] = carried_adjust(r, index, other, at, ink, placement, metrics) \
                        if ink is not None and placement is not None else list(change)
                except Exception:
                    other.adjust[at] = list(change)
            if other not in touched:
                touched.append(other)
        r.applied = dict((key, list(value)) for key, value in r.adjust.items())
        self.sync_compact(touched)  # (one put back as suggested follows the dialog's compacting again)
        for other in touched:
            other.touches = self.closeness(other)
            if other.touches:
                close.append((other.char, other.touches))
            item = self.item_of(other)
            if item is not None:
                self.tree.blockSignals(True)
                self.refresh_item(item, other)
                self.tree.blockSignals(False)
        b = self.ak.b
        # Done, in green, only where every mark landed within reach: one left far off (outside the view,
        # past a clipping line, away from its letter) makes the line a warning, its letters named after it
        far = [t for t in touched if self.far_reasons(t)]
        self.log.add(propagated_text(len(touched), sum(1 for t in touched if t in put_back and not any(
            other is t and index is not None for other, _, index in targets)), b(r.char), b)
            + u": %s." % self.ak.glyph_links([t.char for t in touched]), "warning" if far else "done")
        self.log_far(far)
        self.log_touches(close, "")
        self.fill_strip(r)
        self.update_buttons()

    def closeness(self, recipe):
        """How the recipe's marks sit, placed, against its letter and each other: u"" when all is as it
        should be, else a note for its row (touch_note: a mark too close, or a mark that joins its letter
        and does not touch it)."""
        QtCore, QtGui = _qt()
        ink = self.inks.get(self.master)
        placement = self.placements.get(self.master)
        if ink is None or placement is None or recipe.standalone:  # (a mark made alone has no letter to meet)
            return u""
        try:
            checked = recipe.checked
            parts, _ = place(recipe, ink, placement, self.metrics(self.package))
            recipe.checked = checked
            if parts is None:
                return u""
            gap = TOUCH_SHARE * float(self.package.upm)

            def path_of(chosen):
                whole = QtGui.QPainterPath()
                for glyph, sx, sy, x, y in chosen:
                    path = ink.path(glyph)[0]
                    if path is not None:
                        whole.addPath(QtGui.QTransform(sx, 0.0, 0.0, sy, x, y).map(path))
                return whole

            ranges = mark_ranges(recipe)
            letter = path_of([parts[0]])
            measures = []
            for index, (first, last) in enumerate(ranges):
                mark = path_of(parts[first:last])
                others = path_of([part for at, (f, l) in enumerate(ranges) if at != index for part in parts[f:l]])
                stroker = QtGui.QPainterPathStroker()
                stroker.setWidth(2.0 * gap)
                near = stroker.createStroke(mark)
                measures.append((mark.intersects(letter), near.intersects(letter),
                                 mark.intersects(others), near.intersects(others)))
            return touch_note(recipe, measures, gap)
        except Exception:
            return u""

    def log_touches(self, noted, how):
        """The letters whose marks need a look, named in the log: noted is [(character, its closeness
        note)]; how, what was done to them ("now": marks lined up; "": a placement applied; "built").
        Marks too close and joined marks off their letter are two lines: they are opposite faults."""
        b, links = self.ak.b, self.ak.glyph_links
        close = [char for char, note in noted if note and APART not in note]
        apart = [char for char, note in noted if note and APART in note]
        # (the gap closeness measures, in the font's own em: a fixed "12 units" was wrong past an em of 1,000)
        units = counted(touch_units(getattr(getattr(self, "package", None), "upm", None)), u"unit")
        if close:
            one = len(close) == 1
            if how == "built":
                text = u"%s built with a diacritic within %s of %s letter or another diacritic: %s. Look at %s." % (
                    b(counted(len(close), u"glyph")), units, u"its" if one else u"their", links(close),
                    u"it" if one else u"them")
            else:
                text = u"%s %s%s within %s of %s letter or another diacritic: %s. Look at %s." % (
                    b(counted(len(close), u"letter")), u"now " if how == "now" else u"", u"comes" if one else u"come",
                    units, u"its" if one else u"their", links(close), u"it" if one else u"them")
            self.log.add(text, "warning")
        if apart:
            one = len(apart) == 1
            if how == "built":
                text = u"%s built with a diacritic that joins its letter (ogonek, cedilla, horn) and does not touch it: %s. " \
                       u"Look at %s." % (b(counted(len(apart), u"glyph")), links(apart), u"it" if one else u"them")
            else:
                text = u"%s %s%s a diacritic that joins its letter (ogonek, cedilla, horn) and does not touch it: %s. " \
                       u"Look at %s." % (b(counted(len(apart), u"letter")), u"now " if how == "now" else u"",
                                         u"has" if one else u"have", links(apart), u"it" if one else u"them")
            self.log.add(text, "warning")

    def reset_marks(self):
        r = self.selected()
        if r is None:
            return
        r.adjust, r.applied = {}, None
        r.touches = u""
        self.sync_compact([r])
        self.select()
        item = self.item_of(r)
        if item is not None:
            self.tree.blockSignals(True)
            self.refresh_item(item, r)
            self.tree.blockSignals(False)
        self.update_buttons()

    def neighbor_char(self, role):
        """The character of a letter drawn beside the edited glyph that a click goes to: the letter with
        diacritics of its own after it (the sibling), or None (the plain letter before it has no marks to
        place, and the font's own form of the glyph is the glyph's)."""
        scene = self.editor.scene
        if scene is None or role != "after":
            return None
        return scene.get("chars", {}).get(role) or None

    def neighbor_clicked(self, role):
        """A letter beside the edited glyph clicked: its row and its preview shown, once the click is
        over (the list may be read again, which is not for a mouse handler to do); whether it goes."""
        ch = self.neighbor_char(role)
        if ch is None:
            return False
        QtCore, QtGui = _qt()
        self.neighbor_due = ch
        QtCore.QTimer.singleShot(0, self.go_to_neighbor)
        return True

    def go_to_neighbor(self):
        ch, self.neighbor_due = getattr(self, "neighbor_due", None), None
        try:
            if ch:
                self.go_to_char(ch)
        except Exception as exc:  # (a timer's slot: nothing may escape to Qt)
            self.log.add(u"Could not show %s: %s" % (self.ak.b(ch), self.ak.html(exc)), "error")

    def select_recipe(self, recipe):
        """recipe's row selected (its section opened) and shown."""
        item = self.item_of(recipe)
        if item is None:
            return False
        parent = item.parent()
        if parent is not None:
            parent.setExpanded(True)
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        return True

    def recipe_of(self, ch):
        """The listed recipe of a character, or None."""
        return next((r for r in self.recipes if r.char == ch), None) if ch else None

    def font_glyph(self, ch):
        """The name of the font's glyph for a character, or None."""
        try:
            glyph = self.package.findUnicode(ord(ch)) if self.package is not None else None
            if glyph is None or getattr(glyph, "isNull", False):
                return None
            return u"%s" % glyph.name
        except Exception:
            return None

    def listable(self, ch):
        """Whether Also list existing glyphs would list a character the font has: one of the chosen set that
        can be rebuilt from the font's letter and marks."""
        try:
            if script_of(ch) not in REBUILT_SCRIPTS or ch not in self.characters():
                return False
            found = plan(self.font_read(), [ch], True)
            return bool(found) and not found[0].missing
        except Exception:
            return False

    def go_to_char(self, ch):
        """A character's row selected and its preview shown; one the list does not have, because the font
        has its glyph (built since, or there all along), is listed on its own (unchecked), or, where Also
        list existing glyphs would not list it, opened in a Glyph window. The box itself is left as it is:
        switched on, it would list every glyph the font has, and Check all would then check them all to be
        rebuilt. What was done: "selected", "listed", "opened", or None (said in the log)."""
        b = self.ak.b
        ch = unicodedata.normalize("NFC", ch) if ch else ch  # (a letter named decomposed is the same letter)
        if not ch or len(ch) != 1:
            self.log.add(u"%s is no single character: nothing to show." % b(ch or u""), "warning")
            return None
        try:
            if _property(self.tabs, "currentIndex") != 0:
                self.tabs.setCurrentIndex(0)  # (the log is under every tab: the list is on the first)
            if _property(getattr(self, "top_tabs", self.tabs), "currentIndex") != 0:
                self.top_tabs.setCurrentIndex(0)
        except Exception:
            pass
        if self.select_recipe_of(ch):
            return "selected"
        name = self.font_glyph(ch)
        if name is None:
            self.log.add(u"%s is not in the list, and the font has no glyph for it." % b(ch), "warning")
            return None
        if not self.existing_box.checked and self.listable(ch):
            # this one listed; one listed so before goes again, unless it was checked (moved on: another letter)
            self.shown_existing = self.kept_revealed() | set([ch])
            self.run()
            if self.select_recipe_of(ch):
                self.log.add(u"%s is in the font (%s): listed to show it, unticked, and selected (%s stays "
                             u"off). It leaves the list again once you go on to another letter, search, or "
                             u"tick a glyph, unless you tick it." % (
                                 b(ch), self.ak.glyph_name_link(name), self.ak.i(u"Also list existing glyphs")))
                return "listed"
        error = self.open_glyph(name)
        if error is None:
            self.log.add(u"%s is in the font (%s) and not in the list: opened in a <i>Glyph</i> window." % (
                b(ch), self.ak.glyph_name_link(name)))
            return "opened"
        return None

    def select_recipe_of(self, ch):
        other = self.recipe_of(ch)
        return other is not None and self.select_recipe(other)

    # -- a glyph of the font listed to show it (go_to_char) leaves the list once the user goes on -----

    def kept_revealed(self):
        """The characters listed to show them (go_to_char) that stay listed: those checked since."""
        try:
            self.harvest()
        except Exception:
            pass  # (the checks as last read)
        shown = set(getattr(self, "shown_existing", ()))
        return set(r.char for r in self.recipes if r.char in shown and r.existing and (r.checked or r.adjust))

    def revealed_to_drop(self, keep=None):
        """The rows listed to show them that go when the user goes on: unchecked, with no mark moved by
        hand (it would be lost with the row), not built since (those stay, JUST_BUILT), and not keep (the
        row selected)."""
        shown = set(getattr(self, "shown_existing", ())) - set(getattr(self, "just_built", ()))
        if not shown:
            return []
        return [r for r in self.recipes if r.char in shown and r.existing and not r.checked and not r.adjust
                and r is not keep]

    def drop_revealed(self, keep=None):
        """The rows listed to show them (go_to_char) taken out again once the user goes on (another letter
        selected, a search, a check), but for those checked since and keep: each stayed in the list for
        good (the owner's report of 2026-11-14). The list keeps its place; keep stays selected. Whether
        rows went."""
        try:
            self.harvest()
        except Exception:
            pass
        gone = self.revealed_to_drop(keep)
        if not gone:
            return False
        self.shown_existing = set(getattr(self, "shown_existing", ())) - set(r.char for r in gone)
        box = getattr(self, "existing_box", None)
        if box is not None and _property(box, "checked"):
            return False  # (listed all the same: every glyph the font has is)
        selected = self.selected()
        self.remember_list()
        self.recipes = [r for r in self.recipes if r not in gone]
        self.fill()
        if selected is not None and selected not in gone:
            self.select_recipe(selected)
        self.select()
        self.restore_scroll()
        return True

    def drop_revealed_soon(self, keep=None, wait=0):
        """drop_revealed once the event that called for it is over (the list is not refilled from inside
        its own signals), wait milliseconds later: a row selected by a click waits past a double-click's
        second click (REVEALED_WAIT_MS), which a refilled list would otherwise give to another row. The
        row selected then stays (keep is only whether to ask)."""
        if not self.revealed_to_drop(keep) or getattr(self, "drop_due", False):
            return
        QtCore, QtGui = _qt()
        self.drop_due = True

        def drop():
            try:  # (a timer's slot: nothing may escape to Qt)
                self.drop_due = False
                self.drop_revealed(self.selected())
            except Exception as exc:
                self.log.add(u"Could not take the glyph shown out of the list again: %s" % self.ak.html(exc), "error")
        self.drop_slot = drop  # (kept: PythonQt holds no reference)
        QtCore.QTimer.singleShot(int(wait), drop)

    def log_link(self, target):
        """A glyph named in the log clicked: its row selected (the log lists letters to look at); one built
        since, which left the list, is listed again or opened (go_to_char). A glyph named by its name
        (ak.glyph_name_link: a dotless i made, a corrected glyph added) is left to the log, which opens it in
        a Glyph window (False)."""
        try:
            if self.ak.linked_glyph_name(u"%s" % target):
                return False
            ch = self.ak.linked_char(target)
            if not ch:
                self.log.add(u"That link names no glyph (%s)." % self.ak.html(target), "warning")
                return
            self.go_to_char(ch)
        except Exception as exc:  # (a signal's handler: nothing may escape to Qt)
            self.log.add(u"Could not follow that link: %s" % self.ak.html(exc), "error")

    def picture(self, recipe, size):
        """The recipe drawn as it would be built, in the dialog's text color."""
        QtCore, QtGui = _qt()
        ink = self.inks.get(self.master)
        placement = self.placements.get(self.master)
        if ink is None or ink(recipe.base) is None:
            return None
        parts, width = place(recipe, ink, placement, self.metrics(self.package))
        recipe.placed_parts = parts  # (its row's notes look at them: reversal_notes)
        if parts is None:
            return None
        scale = float(size) / float(self.package.upm)
        pixmap = QtGui.QPixmap(max(int(width * scale) + size // 3, 4), int(size * 1.45))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        try:  # one outline filled by nonzero winding, as a renderer draws components kept as they are
            whole = joined_path(ink, parts)
        except Exception:
            whole = None  # (each part filled alone, as before)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            if whole is not None:
                painter.translate(size / 6.0, size * 1.1)
                painter.scale(scale, -scale)
                painter.fillPath(whole, QtGui.QBrush(color))
            for name, sx, sy, dx, dy in (parts if whole is None else ()):
                path = ink.path(name)[0]
                if path is None:
                    continue
                painter.save()
                painter.translate(size / 6.0 + dx * scale, size * 1.1 - dy * scale)
                painter.scale(scale * sx, -scale * sy)
                painter.fillPath(path, QtGui.QBrush(color))
                painter.restore()
        finally:
            painter.end()
        return self.ak.inked(pixmap, color)  # (in one color: redrawn in the new one when dark mode switches)

    def sibling(self, recipe):
        """(glyph, character) of a letter the font has with the same base and a diacritic, to compare (á
        beside a new ǎ), or (None, None); never the glyph itself (one listed as existing)."""
        base_char = unicodedata.normalize("NFD", recipe.char)[0]
        font = self.font_read()
        for code in sorted(font.by_code):
            ch = unichr_(code)
            decomposed = unicodedata.normalize("NFD", ch)
            if len(decomposed) > 1 and decomposed[0] == base_char and ch != recipe.char and font.drawn(code):
                return font.by_code[code], ch  # (an empty glyph shows nothing to compare: a CID-keyed font's)
        return None, None

    # -- the reference -------------------------------------------------------------

    def choose_reference(self):
        """The reference font: the one chosen before, else the font FreeLab bundles (the default, not
        saved: it stays the default); without the bundled font, the installed font with the most of the
        listed characters (found once, and remembered)."""
        QtCore, QtGui = _qt()
        family = self.settings.get("reference") or getattr(self, "reference_default", None)
        if not family:
            chars = [r.code for r in self.recipes][:400]
            if not chars:
                return
            self.work_progress(u"Finding the installed font with the most of these characters")  # (in the top row)
            best, best_count = None, -1
            try:
                installed = set(u"%s" % name for name in QtGui.QFontDatabase().families())
                for name in [f for f in REFERENCE_FAMILIES if f in installed]:
                    metrics = QtGui.QFontMetrics(QtGui.QFont(name))
                    count = sum(1 for code in chars if metrics.inFontUcs4(code))
                    if count > best_count:
                        best, best_count = name, count
            except Exception:
                best = None
            family = best
            if family:
                self.settings["reference"] = family
                write_settings(self.ak, self.settings)
        if family:
            self.reference_chosen = family
            self.show_reference_choice()
        self.draw_reference(self.selected())

    def char_family(self, text):
        """The first FreeLang family (Font Check's order: Essential, CJK, the + fonts) that draws every
        character of text, or None (no FreeLang, or none of its fonts has them all). Each family's font read
        once (QRawFont), each text's answer kept. Never raises."""
        cache = self.__dict__.setdefault("char_families", {})
        if text in cache:
            return cache[text]
        found = None
        try:
            QtCore, QtGui = _qt()
            raws = self.__dict__.setdefault("freelang_raws", {})
            codes = [ord(ch) for ch in text]
            for family in list(getattr(self, "freelang", None) or ()):
                raw = raws.get(family)
                if raw is None:
                    raw = False
                    try:
                        made = QtGui.QRawFont.fromFont(QtGui.QFont(family))
                        valid = made.isValid
                        raw = made if (valid() if callable(valid) else valid) else False
                    except Exception:
                        pass
                    raws[family] = raw
                if raw and codes and all(raw.supportsCharacter(code) for code in codes):
                    found = family
                    break
        except Exception:
            found = None
        cache[text] = found
        return found

    def char_font(self, base, text):
        """base (a list row's font) in the FreeLang family that draws text (char_family), else base itself.
        The lists drew their characters in the dialog's font, and Qt's Windows fallback (MS Gothic, which
        lacks them) drew ㏞, ㏟, and ㏿ as boxes, though FreeLang CJK has all three (owner's images 316 and
        317): every list of the suite draws its characters in FreeLang, as Font Check's do."""
        family = self.char_family(text) if text else None
        if not family:
            return base
        try:
            QtCore, QtGui = _qt()
            font = QtGui.QFont(base)
            font.setFamily(family)
            return font
        except Exception:
            return base

    def char_html(self, text):
        """text for a caption (rich text), in the FreeLang family that draws it, else as it is: "Noto Sans
        lacks ㏞" drew ㏞ in the dialog's font, a box (owner's images 316 and 317)."""
        family = self.char_family(text) if text else None
        if not family:
            return text  # (as before: the caption stays plain text)
        return u"<span style=\"font-family: '%s'\">%s</span>" % (family.replace(u"'", u""), self.ak.html(text))

    def reference_family(self, codes, more=()):
        """(family, chosen): the first of the chosen reference font, FreeLab's own fonts (FreeLang: the
        catch-all, drawing every character Font Check shows but a few), those picked before, and the known
        families (more: a script's) that has every one of the code points, or None; and the chosen one."""
        chosen = getattr(self, "reference_chosen", u"") or u""
        candidates = ([chosen] if chosen else []) + list(getattr(self, "freelang", ())) + self.reference_history \
            + list(REFERENCE_FAMILIES) + list(more)
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if all(has_character(candidate, code) for code in codes):
                return candidate, chosen
        return None, chosen

    def reference_changed(self):
        """Both tabs' references drawn again in the font now chosen."""
        self.draw_reference(self.selected())
        if self.anchors_read:
            self.anchors.draw_reference(self.anchors.selected())
        generation = getattr(self, "generation", None)
        if generation:  # (Glyph generation's reference, in the same font)
            generation.draw_reference(generation.selected())

    def theme_changed(self):
        """Dark mode switched, either way (the shared module's theme_switched, once the rows' pictures and
        grayed-out rows are in the new colors): what is drawn here in colors read when it was drawn,
        again: the strip's buttons, the editors' scenes (their amber warnings), and both tabs'
        references. Nothing else of the selection changes."""
        try:
            r = self.selected()
            self.fill_strip(r)
            if r is not None and not r.missing:
                self.editor.scene = self.scene(r)
            self.editor.update()
            self.reference_changed()
            if getattr(self, "anchors_read", False):
                g = self.anchors.selected()
                self.anchors.editor.scene = self.anchors.scene(g) if g is not None else None
                self.anchors.editor.update()
            generation = getattr(self, "generation", None)
            if generation:  # (its preview: a varied glyph's is drawn in two colors, not inked)
                generation.select()
        except Exception:
            pass  # (the next selection draws them anyway)

    def draw_reference(self, r):
        QtCore, QtGui = _qt()
        if r is None or self.package is None:
            self.reference.clear()
            self.reference_note.setText(u"")
            return
        family, chosen = self.reference_family([r.code], script_families(script_of(r.char)))
        if family is None:
            self.reference.clear()
            self.reference_note.setText(u"No reference font has %s." % r.char)
            return
        self.reference.setPixmap(reference_picture(r.char, family, self.dialog.palette))
        # (its character in FreeLang, where the caption names it: owner's images 316 and 317)
        self.reference_note.setText(reference_note(self.char_html(r.char), family, chosen,
                                                   names=getattr(self, "font_names", None)))

    # -- the Glyph window ----------------------------------------------------------

    def glyph_to_show(self, r):
        """The glyph a row opens in a Glyph window: the built one, else its letter (or None)."""
        if r is None or self.package is None:
            return None
        if self.in_font(r):
            return r.name
        try:
            if r.base:
                if self.package.findName(r.base) is not None:
                    return r.base
                made = made_dotless(r)  # (a dotless i not made yet: the i it is made of)
                return made.source if made is not None and self.package.findName(made.source) is not None else None
            glyph = self.package.findUnicode(ord(unicodedata.normalize("NFD", r.char)[0]))  # (a row that cannot be built)
            return glyph.name if glyph is not None and not glyph.isNull else None
        except Exception:
            return None

    def show_in_glyph_window(self):
        """The selected row's glyph between H's, n's, and o's in a Glyph window: the built glyph, else
        its letter."""
        r = self.selected()
        name = self.glyph_to_show(r)
        if name is None:
            return
        if name != r.name:
            self.log.add(u"%s is not in the font yet: its letter %s opened instead." % (self.ak.b(r.char),
                                                                                      self.ak.glyph_name_link(name)))
        self.open_glyph(name)

    def open_glyph(self, name):
        """A glyph of the font between H's, n's, and o's in a Glyph window; the error (said in the log), or
        None."""
        contexts = self.ak.proof_contexts(self.package, [name])
        text = u"/space".join(u"/%s/%s/%s/%s/%s" % (c, c, name, c, c) for c in contexts)
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(self.ak.error_sentence(u"FontLab did not open the glyph", error), "error")
        return error or None

    def editor_double_clicked(self):
        self.show_in_glyph_window()

    # -- Kerning Check on the glyphs built here ------------------------------------

    def kerning_names(self):
        """The glyphs built here that the font (the same one) still has."""
        if self.package is None or not self.built_names:
            return []
        try:
            if self.package_key(self.package) != self.built_font:
                return []
            return [name for name in self.built_names if self.package.findName(name) is not None]
        except Exception:
            return []

    def check_kerning(self):
        """Kerning Check, its lists limited to the pairs with the glyphs built here."""
        names = self.kerning_names()
        if not names:
            return
        try:
            module = self.ak.load_sibling("freelab_kerning_check.py", "freelab_kerning_check")
            with self.ak.opening_from(self.dialog):  # (on this window's font, in its place)
                try:
                    module.main(glyphs=names, reason=u"Glyph Compose built")
                except TypeError:  # (a Kerning Check that takes no glyphs: all its pairs)
                    module.main()
        except Exception as exc:
            self.log.add(self.ak.error_sentence(u"<i>Kerning Check</i> did not open", exc), "error")

    # -- building -----------------------------------------------------------------

    def build(self):
        """Build checked glyphs, in the window's top row (owner's image 176): the other masters read first,
        which can be stopped (nothing is built then); the write never is (one step of FontLab's History)."""
        if self.package is None:
            return
        try:
            self.work_begin(u"Reading the masters")
            try:
                self.build_now()
            finally:
                self.work_end()
        except self.stopped_error():
            self.log.add(u"Stopped before anything was built: nothing was built.")

    def build_now(self):
        QtCore, QtGui = _qt()
        if self.package is None:
            return
        self.harvest()
        chosen = [r for r in self.recipes if not r.missing and r.checked]
        if not chosen:
            return
        package = self.package
        current = self.current_font()
        key = self.package_key(current)
        if key is None or key != self.package_key(package):
            self.run()
            self.log.add(u"The font changed since the list was made: here is this one's. Nothing was built.", "warning")
            return
        masters = list(package.masters) or [self.master]
        metrics = self.metrics(package)
        unread = [master for master in masters if master not in self.inks]
        for at, master in enumerate(unread):  # (stoppable: nothing is written yet)
            self.work_progress(u"Reading master %s" % master, at / float(len(unread)))
            self.inks[master], self.placements[master] = self.learn(
                package, master, self.work_part(at / float(len(unread)), (at + 1) / float(len(unread))))
        self.work_progress(u"Building", 0.0, stoppable=False)
        fontlab = self.fontlab
        made, skipped, failed, error, touched, rebuilt, partial = [], [], [], None, [], [], []
        mirrored = []  # the glyphs built with a mirrored component
        set_right, helpers = [], []  # those built with a corrected glyph in a mirrored one's place, and the glyphs added
        used = set()  # the corrected glyphs a glyph built points to
        corrected = self.corrector(package, masters, helpers, touched)
        # The dotless i and j made of the font's i and j (the glyphs built on them, or their own rows ticked):
        # parts as the corrected glyphs are, made first and recorded in a step of their own before any glyph
        # made of them (record_parts); their names, {name: why} of those that could not be made, and the
        # names a glyph built ended up using (those used by none are taken out again)
        dotless_made, dotless_failed, dotless_used = [], {}, set()
        changing = None  # the glyph whose layers are being changed, for touched should an error stop the build
        if not self.begin_write(package, existing_glyphs(package, [r.name for r in chosen]), coverage=True):
            return  # (nothing built: the reason in the log)
        # The corrected glyphs the letters' mirrored parts point to are made first and recorded as a step of
        # their own, before any letter made of them is written (record_parts: FontLab's Undo of one step holding
        # both printed that the letters' components did not exist, live 2026-11-16)
        recorded_parts = {"parts": None, "status": None}

        def ensure_parts():  # (once, just before the first change to a letter: a build refused records no step)
            if recorded_parts["parts"] is None:
                recorded_parts["parts"] = list(touched)
                recorded_parts["status"] = record_parts(self.ak, fontlab, package, recorded_parts["parts"])
        try:
            self.make_dotless(chosen, masters, dotless_made, dotless_failed, touched)
            self.make_helpers(chosen, masters, metrics, corrected)
        except Exception as exc:
            error = exc
        try:
            for at, r in enumerate(chosen if error is None else []):
                self.work_progress(None, at / float(len(chosen)), stoppable=False)  # (a write: never stopped half way)
                dotless = made_dotless(r)
                if dotless is not None and dotless.name in dotless_failed:  # (never built on a glyph not made)
                    # (each reason rich text for the log: the dotless glyph's name a link, the reason escaped)
                    failed.append((r.char, u"%s could not be made: %s" % (self.ak.glyph_name_link(dotless.name),
                                                                          self.ak.html(dotless_failed[dotless.name]))))
                    continue
                if r.dotless_row:  # the dotless glyph itself: made with the parts, or made meanwhile
                    if dotless.name in dotless_made:
                        made.append(r.char)
                        dotless_used.add(dotless.name)
                        self.note_built(package, r.name)
                    else:
                        skipped.append(r.char)
                    continue
                glyph = package.findName(r.name)
                if glyph is not None and not is_empty(glyph) and not r.existing:
                    skipped.append(r.char)  # made meanwhile
                    continue
                added = glyph is None
                if glyph is None and package.findUnicode(r.code) is not None:
                    skipped.append(r.char)
                    continue
                ensure_parts()
                if glyph is None:
                    new = new_glyph(fontlab, package, r.name)
                    # (its code point set once its layers are made: given before, FontLab kept none of the
                    # layers made on it, live in Tsukimi Rounded 2026-11-11)
                    package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
                    glyph = package.findName(r.name)
                    if glyph is None:
                        raise RuntimeError(u"FontLab did not add %s" % r.name)
                placed, kept_by, refused = False, [], []  # masters with its components kept, and refused
                planned, unfixed = [], set()  # (master, its parts, width); mirrors not set right in some master
                for master in masters:
                    ink, placement = self.inks[master], self.placements[master]
                    if ink(r.base) is None:
                        continue  # not drawn in this master
                    checked = r.checked
                    parts, width = place(r, ink, placement, metrics)
                    r.checked = checked
                    if parts is None:
                        continue
                    placed = True
                    if r.standalone:
                        parts, width = standalone_parts(parts, ink), 0
                    found = []  # (glyph, transform, None or (mirror's key, corrected glyph, its transform))
                    for part in parts:
                        name, sx, sy, dx, dy = unwrapped(package, master, *part)
                        values = (sx, 0.0, 0.0, sy, float(round(dx)), float(round(dy)))
                        fix = None
                        if reverses_direction(sx, sy):
                            # A glyph it is drafted from is itself a mirrored component: a mirror is never
                            # written. Its corrected glyph (mirrored, its contours reversed) takes its place;
                            # where that cannot be made, the mirrored component is written and named.
                            key = (name, mirror_axis(*values[:4]))
                            try:
                                helper = corrected(*key)
                                mirror = source_mirror(self.ak, package, master, name, key[1])
                                if mirror is None:
                                    raise MirrorError(u"%s has no outline in master %s" % (name, master))
                                fix = (key, helper, without_mirror(values, mirror))
                            except MirrorError:
                                unfixed.add(key)
                                fix = (key, None, None)
                        found.append((name, values, fix))
                    planned.append((master, found, width))
                for master, found, width in planned:
                    components, helping = [], []  # (and the corrected glyphs they point to)
                    for name, values, fix in found:
                        if fix is not None:
                            key, helper, proper = fix
                            # set right in every master or in none: masters whose components differ would
                            # not interpolate
                            if key in unfixed:
                                if r.char not in mirrored:
                                    mirrored.append(r.char)
                            else:
                                name, values = helper, proper
                                helping.append(helper)
                                if r.char not in set_right:
                                    set_right.append(r.char)
                        component = fontlab.GlyphComponent(name)
                        component.transform = QtGui.QTransform(*values)
                        components.append(component)
                    layer = glyph.getLayerByName(master, True)
                    own, own_width = [], 0.0
                    changing = glyph
                    if r.existing:  # rebuilt: its outlines and components in this master replaced
                        own = [shape.cloneTopLevel() if hasattr(shape, "cloneTopLevel") else shape.clone()
                               for shape in layer.shapes]
                        own_width = float(layer.advanceWidth)
                        width = max(float(width), own_width)  # its own advance kept when wider (a vertical caron's room)
                        layer.removeAllShapes()
                    try:
                        layer.setGlyphComponents(components, float(width), package, False)
                    finally:
                        if layer.shapes:
                            kept_by.append(master)
                            used.update(helping)
                        else:  # FontLab kept none of the components (see unwrapped): its own shapes put back
                            refused.append(master)
                            for shape in own:
                                layer.addShape(shape)
                            if own:
                                layer.advanceWidth = own_width
                if not kept_by:
                    # Nothing of it drawn: said why, and a glyph added for it taken out again (one the
                    # font had is left as it was)
                    why = self.why_empty(r, masters, placed)
                    failed.append((r.char, self.ak.html(why + (u"; it is left as it was" if r.existing else u""))))
                    if added:
                        package.deleteGlyph(package.findName(r.name))
                    elif refused:
                        touched.append(glyph)  # (its shapes taken out and put back)
                    changing = None
                    continue
                if added:
                    package.findName(r.name).fgGlyph.unicode = r.code
                touched.append(glyph)
                changing = None
                if refused:
                    partial.append((r.char, r.existing, refused))
                (rebuilt if r.existing else made).append(r.char)
                if dotless is not None:
                    dotless_used.add(dotless.name)
                self.note_built(package, r.name)
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
            if changing is not None:
                touched.append(changing)
        # A corrected glyph made for a glyph that was then not built (or built with the mirrored component
        # in every master) is used by nothing: taken out again, as Correct mirrored components does
        # A dotless glyph made for glyphs none of which was then built (its own row unticked) is taken out too
        unused = [name for name in helpers if name not in used] + [name for name in dotless_made
                                                                   if name not in dotless_used]
        for name in unused:
            try:
                package.deleteGlyph(font_glyph(package, name))
            except Exception:
                pass
        touched = [glyph for glyph in touched if u"%s" % getattr(glyph, "name", u"") not in unused]
        helpers = [name for name in helpers if name in used]
        dotless_made = [name for name in dotless_made if name in dotless_used]
        status = None
        parts, parts_status = recorded_parts["parts"] or [], recorded_parts["status"]
        later = [glyph for glyph in touched if all(glyph is not part for part in parts)]
        try:
            # (nothing changed, every glyph refused: no History step of nothing, live 2026-11-16; parts taken out
            # again after their own step: a step that records it)
            second = bool(parts) and bool(later or unused)
            if later or (parts and unused) or (touched and not parts):
                status = self.ak.notify_changed(fontlab, package, u"FreeLab Glyph Compose", later if parts else touched,
                                                coverage=True)
        finally:
            self.end_write(package, bool(touched) or bool(parts))
        if parts and second:
            self.log.add(parts_step_text([u"%s" % getattr(glyph, "name", u"") for glyph in parts], self.ak.glyph_name_link))
        report_write(parts_status, self.log)
        b = self.ak.b
        if made:
            one = len(made) == 1
            self.log.add(u"Built %s: %s. %s at the end of the font%s. "
                         u"<i>Check kerning of %s</i> looks at %s pairs." % (
                             b(counted(len(made), u"glyph")), self.ak.html(u"".join(made)), u"It is" if one else u"They are",
                             undo_words(status, u"; <i>Edit &gt; Undo</i> takes %s back" % (u"it" if one else u"them")),
                             u"this glyph" if len(self.built_names) == 1 else u"these glyphs",
                             u"its" if len(self.built_names) == 1 else u"their"), "done")
        elif not rebuilt:
            self.log.add(u"Built none.")
        if rebuilt:
            self.log.add(u"Rebuilt %s from %s letter and marks, in place: %s.%s" % (
                b(counted(len(rebuilt), u"glyph")), u"its" if len(rebuilt) == 1 else u"their",
                self.ak.html(u"".join(rebuilt)),
                undo_words(status, u" <i>Edit &gt; Undo</i> takes %s back." % (u"it" if len(rebuilt) == 1 else u"them"))),
                "done")
        sources = dict((made_dotless(r).name, made_dotless(r).source) for r in chosen if made_dotless(r) is not None)
        for name in dotless_made:
            self.log.add(made_dotless_text(name, sources.get(name, u""), len(masters), self.ak.glyph_name_link), "done")
        report_write(status, self.log)
        # Built on a dotted i the font could not take apart: named in amber, as a diacritic too close is
        for line in dot_kept_lines([r for r in chosen if r.char in made or r.char in rebuilt], b, self.ak.glyph_links):
            self.log.add(line, "warning")
        close = []
        for r in chosen:  # built in spite of a mark too close: named, to look at
            if r.char in made or r.char in rebuilt:
                try:
                    note = self.closeness(r)
                    if note:
                        close.append((r.char, note))
                except Exception:
                    pass
        self.log_touches(close, "built")
        set_right = [char for char in set_right if char in made or char in rebuilt]
        if set_right or helpers:
            one = len(helpers) == 1
            self.log.add(u"%s built with a corrected glyph in the place of a mirrored one: %s%s." % (
                b(counted(len(set_right), u"glyph")), self.ak.glyph_links(set_right),
                (u" (%s added, mirrored with %s contours reversed, so that no hole shows where it overlaps: %s)" % (
                    b(counted(len(helpers), u"glyph")), u"its" if one else u"their",
                    self.ak.glyph_names_linked(helpers, word=None)))
                if helpers else u""), "done")
        mirrored = [char for char in mirrored if char in made or char in rebuilt]
        if mirrored:
            self.log.add(mirrored_text(len(mirrored), b) + u": %s. %s" % (self.ak.glyph_links(mirrored), MIRRORED_ADVICE),
                         "warning")
        if skipped:
            self.log.add(u"%s had been made meanwhile and %s left as %s." % (
                b(u"".join(skipped)), u"was" if len(skipped) == 1 else u"were",
                u"it was" if len(skipped) == 1 else u"they were"), "warning")
        for char, why in failed:  # (why: rich text already)
            self.log.add(u"%s was not built: %s." % (b(char), why), "warning")
        for char, was_there, left in partial:  # refused in some masters only
            where = self.ak.html(u"%s %s" % (u"master" if len(left) == 1 else u"masters", listed(left)))
            if was_there:
                self.log.add(u"%s was not rebuilt in %s: FontLab did not keep its components there, and its own "
                             u"shapes were put back." % (b(char), where), "warning")
            else:
                self.log.add(u"%s was built with %s left empty: FontLab did not keep its components there." % (
                    b(char), where), "warning")
        if error is not None:
            self.log.add(self.ak.error_sentence(u"Stopped by an error", error), "error")
        # The glyphs built stay listed (under JUST_BUILT, unchecked): the font has them now, and the list
        # would otherwise drop them, out of reach of what is set right after a build
        self.just_built = set(getattr(self, "just_built", ())) | set(made) | set(rebuilt)
        self.built_now = set(made) | set(rebuilt)  # (they come back unchecked: keeps_check)
        # (one listed to show it and built is listed as built now, not to leave once the user goes on)
        self.shown_existing = set(getattr(self, "shown_existing", ())) - self.built_now
        self.run()
        if getattr(self, "generation", None):  # (Glyph generation's list reads the font again too)
            self.generation.run()
        if made or rebuilt:  # (from Font Check's hand-over, all of it built: back to Font Check)
            self.back_to_font_check(bool(failed or skipped or partial or mirrored) or error is not None)

    def note_built(self, package, name):
        """A glyph built (or rebuilt) for Check kerning of these glyphs, which looks at those of this font."""
        key = self.package_key(package)
        if self.built_font != key:
            self.built_names, self.built_font = [], key
        if name not in self.built_names:
            self.built_names.append(name)

    def make_dotless(self, chosen, masters, made, failed, touched):
        """The dotless glyphs the chosen glyphs are built on, or are (their own rows), where the font has none
        (made_dotless), made now of its i and j (make_dotless), before any glyph is written: each glyph made
        added to touched, so that it is recorded with the parts (record_parts), a new prerequisite in a step of
        its own before the glyphs made of it; its name to made, or to failed with why. One the font has by now
        (made meanwhile) is built on as it is."""
        wanted = []
        for r in chosen:
            dotless = made_dotless(r)
            if dotless is not None and all(dotless.name != other.name for other in wanted):
                wanted.append(dotless)
        for dotless in wanted:
            if font_glyph(self.package, dotless.name) is not None:
                continue
            try:
                touched.append(make_dotless(self.fontlab, self.ak, self.package, masters, dotless))
                made.append(dotless.name)
            except DotlessError as exc:
                failed[dotless.name] = u"%s" % exc

    def make_helpers(self, chosen, masters, metrics, corrected):
        """The corrected glyphs the chosen letters' mirrored parts will point to, made now (corrected: the
        build's), as the build plans each letter, before any letter is written (record_parts). A letter the
        build will skip (made meanwhile) is passed over; what cannot be made is said by the letter's build."""
        package, wanted = self.package, {}  # ((source, axis): whether every master it is planned in can be set right)
        for r in chosen:
            glyph = package.findName(r.name)
            if glyph is not None and not is_empty(glyph) and not r.existing:
                continue
            if glyph is None and package.findUnicode(r.code) is not None:
                continue
            for master in masters:
                ink, placement = self.inks[master], self.placements[master]
                if ink(r.base) is None:
                    continue
                checked = r.checked
                parts, width = place(r, ink, placement, metrics)
                r.checked = checked
                if parts is None:
                    continue
                if r.standalone:
                    parts, width = standalone_parts(parts, ink), 0
                for part in parts:
                    name, sx, sy, dx, dy = unwrapped(package, master, *part)
                    if reverses_direction(sx, sy):
                        key = (name, mirror_axis(sx, 0.0, 0.0, sy))
                        # (set right only where every master can be, as the build does: else unused, never made)
                        wanted[key] = wanted.get(key, True) and source_mirror(self.ak, package, master, *key) is not None
        for key, every in wanted.items():
            if every:
                try:
                    corrected(*key)
                except MirrorError:
                    pass  # (the letter's build writes the mirrored component and says so)

    def why_empty(self, r, masters, placed):
        """Why a recipe came out with nothing drawn: the first of its glyphs with no outline, master by
        master, else FontLab not keeping its components."""
        if placed:
            return u"FontLab did not keep its components (%s)" % u" + ".join(
                [r.base] + [part[0] for mark in r.marks for part in mark.parts])
        for master in masters:
            ink = self.inks[master]
            for name in [r.base] + [part[0] for mark in r.marks for part in mark.parts]:
                if ink(name) is None:
                    return u"%s has no outline in master %s" % (name, master)
        return u"its diacritic could not be placed" if len(r.marks) == 1 else u"its diacritics could not be placed"

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


FONT_CHECK_TITLE = u"Font Check"  # (its entry in Scripts > FreeLab: ak.open_tool opens it in this window's place)


def back_to_font_check_due(showing, left, failed):
    """Whether a build from Font Check's hand-over goes back to Font Check: the window still lists what was
    handed over (showing), none of it is left to build (left), and the build failed nowhere."""
    return bool(showing) and not left and not failed


def generation_table(ak):
    """The characters of Glyph generation's table, or none where its module cannot be loaded."""
    try:
        module = ak.load_sibling(GENERATION_FILE, GENERATION_MODULE)
        return set(module.unichr_(int(e["code"], 16)) for e in module.load_data().get("entries") or [])
    except Exception:
        return set()


def handed_over(chars, table):
    """(for the Diacritics tab, for Glyph generation) of the characters Font Check hands over: one that
    decomposes into a letter and marks is the Diacritics tab's (ά too, which Glyph generation would only
    copy), another of Glyph generation's table is that tab's, and the rest the Diacritics tab's (it says
    what it cannot build)."""
    letters, others = [], []
    for ch in chars:
        decomposed = unicodedata.normalize("NFD", ch) if len(ch) == 1 else ch
        (others if ch in table and len(decomposed) == 1 else letters).append(ch)
    return letters, others


def generation_characters(ak, package):
    """The characters Glyph generation can build in the font, in its current master, that are not drafts
    (a starting point counts only where the font's design makes it likely usable): what Font Check counts
    as buildable."""
    module = ak.load_sibling(GENERATION_FILE, GENERATION_MODULE)
    fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
    codes = ak.glyph_code_map(package.fgPackage.glyphs)
    font = module.FontLabFont(ak, fc, package, package.master, codes)
    rows = module.Planner(module.load_data(), font).plan()
    return set(r.char for r in rows if r.layout is not None and r.sureness != "starting point")


class _Globals(object):
    """This module's names as attributes, for the Glyph generation tab (FontLab runs a script under a name
    of its own, so the module cannot be found in sys.modules by __name__)."""

    def __init__(self, names):
        self.__dict__ = names


def _property(widget, name):
    """A Qt property's value (PythonQt gives properties as attributes, some builds as methods)."""
    value = getattr(widget, name)
    return value() if callable(value) else value


def main(characters=None):
    """Opens Glyph Compose; characters (Font Check's missing letters) are listed as a set of their own."""
    try:  # this font's window shows it already: brought forward as it is
        if characters is None and load_auto_kerning().raise_open(TOOL_TITLE):
            return
    except Exception:
        pass
    key = None
    try:  # (what Font Check handed over for this font this session, when it hands nothing now: hand_over_memory)
        key, open_ids = opening_font(load_auto_kerning())
        characters = kept_hand_over(hand_over_memory(), key, characters, open_ids)
    except Exception:
        pass
    try:
        dialog = AccentsDialog(characters, key if characters else None)
    except Exception as exc:
        print("FreeLab Glyph Compose: %s" % exc)
        return
    sys._freelab_glyph_compose = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window(TOOL_TITLE, dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_glyph_compose":
    main()
