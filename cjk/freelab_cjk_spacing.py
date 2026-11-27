#FLM: CJK Spacing
# -*- coding: utf-8 -*-
"""FreeLab CJK Spacing, from FontLab's Scripts menu.

Writes the OpenType code that sets a Japanese font's full-width kana and punctuation proportionally:

- palt (proportional alternate widths, which applications turn on for proportional Japanese text):
  each full-width kana, CJK punctuation mark, and full-width form is trimmed to its ink and the
  sidebearings the open-licensed CJK fonts give theirs (cjk/palt_model.json, measured by
  cjk/train/palt.py: about 0.07 em on each side for kana, each punctuation mark its own).
- halt (half widths, for punctuation set in half the em, as in tight headlines): each punctuation
  mark's half-width setting, as those fonts set it (an opening bracket keeps its right half, a comma
  its left).

- Hangul widths: none of the corpus's Korean fonts kerns Hangul or puts it in palt; they set every
  syllable at one width (0.9 em, the median) or give each its own, its sidebearings by its shape
  (cjk/hangul_model.json, measured by cjk/train/hangul.py). On request, the font's syllables are set
  either way: their outlines moved and their widths changed, in every master.

Shows each glyph's trim and the text set both ways before anything is written, and writes only the
glyphs you leave checked, between FreeLab's marker lines in palt and halt (the rest of each feature
kept).

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import os
import re
import sys

MODEL_FILE = "palt_model.json"
HANGUL_MODEL_FILE = "hangul_model.json"
HANGUL_MODES = (("leave", u"Leave as they are"), ("fixed", u"One width for all, ink centered"),
                ("proportional", u"Proportional, by syllable shape"))
HANGUL_SHAPES = (("vertical", u"Vowel beside (\uac00)"), ("vertical final", u"Vowel beside, final (\uac01)"),
                 ("horizontal", u"Vowel under (\uace0)"), ("horizontal final", u"Vowel under, final (\uace1)"),
                 ("mixed", u"Vowel beside and under (\uacfc)"), ("mixed final", u"Vowel beside and under, final (\uacfd)"))
HANGUL_TOLERANCE = 2  # a syllable moved and widened by less than this is left alone
FULL_WIDTH_SHARE = 0.9  # a glyph narrower than this share of the em is proportional already: left alone
TOLERANCE_UNITS = 4  # a trim smaller than this on both sides is not listed
BEGIN, END = u"# >>> FreeLab %s (made by FreeLab CJK Spacing)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
FEATURE_TITLES = {"palt": "Proportional Alternate Widths", "halt": "Alternate Half Widths"}
KINDS = ("hiragana", "small hiragana", "katakana", "small katakana", "punctuation")
KIND_LABELS = {"hiragana": "Hiragana", "small hiragana": "Small hiragana", "katakana": "Katakana",
               "small katakana": "Small katakana", "punctuation": "Punctuation and full-width forms",
               "hangul": "Hangul"}
# One sample per writing system the trims serve, each set with the full-width punctuation palt trims:
# the Iroha (Japanese, 11th century, public domain: every kana once), a Hangul pangram written for
# FreeLab (GPL-3 with the code: the 14 basic consonants and the 10 basic vowels; Proof has it too), and
# the opening lines of the Thousand Character Classic (public domain, no character twice: a pangram of
# hanzi cannot be) in each Chinese standard's forms. The one in the font's own writing is shown first
# (best_sample); the field takes any text of one's own.
SAMPLE = u"「いろはにほへと、ちりぬるを。わかよたれそ、つねならむ。うゐのおくやま、けふこえて。あさきゆめみし、ゑひもせす。」（いろはうた）"
SAMPLES = (("ja", u"Japanese", SAMPLE),
           ("ko", u"Korean", u"「토요일 아침, 키 큰 여행자가 푸른 바다 앞 야자수 그늘에서 휴식을 즐겼다.」"),
           ("zh-hans", u"Chinese (Simplified)", u"「天地玄黄，宇宙洪荒。日月盈昃，辰宿列张。寒来暑往，秋收冬藏。」（千字文）"),
           ("zh-hant", u"Chinese (Traditional)", u"「天地玄黃，宇宙洪荒。日月盈昃，辰宿列張。寒來暑往，秋收冬藏。」（千字文）"))
SAMPLE_SCRIPTS = {"ja": ((0x3041, 0x30FA),), "ko": ((0xAC00, 0xD7A3),),
                  "zh-hans": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF)), "zh-hant": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF))}
# What makes a font a CJK one (has_cjk): kana, Hangul, ideographs, bopomofo, CJK punctuation and full-width
# forms, as CJK Vertical counts them. Not the curly quotes palt trims where they are full width: a Latin font
# has them too, proportional, and counted, they kept CJK Spacing's ticks and sample usable over Bellefair
# (owner's images 379 and 380, live 2026-11-19).
CJK_RANGES = ((0x1100, 0x11FF), (0x2E80, 0x2FDF), (0x2FF0, 0x303F), (0x3040, 0x30FF), (0x3100, 0x31FF),
              (0x3200, 0x33FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xA960, 0xA97F), (0xAC00, 0xD7FF),
              (0xF900, 0xFAFF), (0xFE10, 0xFE1F), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF), (0x1B000, 0x1B16F),
              (0x20000, 0x323AF))


def has_cjk(codes):
    """Whether a font's code points include a CJK character (CJK_RANGES)."""
    return any(low <= code <= high for code in codes for low, high in CJK_RANGES)


# The writing a font is for, as its family name says it (a word of it: IBM Plex Sans JP, Noto Sans TC)
NAME_HINTS = {"JP": "ja", "JPN": "ja", "JAPANESE": "ja", "KR": "ko", "KOR": "ko", "KOREAN": "ko",
              "SC": "zh-hans", "CN": "zh-hans", "PRC": "zh-hans", "HANS": "zh-hans", "SIMPLIFIED": "zh-hans",
              "TC": "zh-hant", "HK": "zh-hant", "TW": "zh-hant", "HANT": "zh-hant", "TRADITIONAL": "zh-hant"}
# and as its OS/2 code page bits say it (one writing only: fonts set several, Noto Sans JP 17 and 18)
CODE_PAGE_HINTS = {17: "ja", 18: "zh-hans", 19: "ko", 20: "zh-hant", 21: "ko"}
MIN_SAMPLE_SHARE = 0.5  # a sample the font covers less than this share of is never picked for a hint
HANGUL_SYLLABLES, KANA = (0xAC00, 0xD7A3), (0x3041, 0x30FF)

# The long steps, named in the window's top row while they run (ak.busy_start: owner's image 179, no bar
# while listing; 183, none while writing), each with the share of the bar at which it ends
READ_STEP, HANGUL_STEP, LIST_STEP, PREVIEW_STEP = (u"Reading the font", u"Measuring Hangul", u"Listing",
                                                   u"Drawing the previews")
LIST_STEPS = ((READ_STEP, 0.55), (HANGUL_STEP, 0.75), (LIST_STEP, 0.95), (PREVIEW_STEP, 1.0))
UNDO_STEP, CODE_STEP, WIDTHS_STEP, UPDATE_STEP, COMPILE_STEP = (u"Opening an undo step", u"Writing the code",
                                                                u"Setting Hangul widths", u"Updating the font",
                                                                u"Compiling")
WRITE_STEPS = ((UNDO_STEP, 0.05), (CODE_STEP, 0.15), (WIDTHS_STEP, 0.8), (UPDATE_STEP, 0.9), (COMPILE_STEP, 1.0))
PUMP_EVERY = 50  # glyphs read between two calls to the progress (it lets events through at most every 0.1 s)
LIST_AGAIN = u"freelab:list-again"  # the status line's link once a listing was stopped
# The Cancel button's own line (ak.cancel_button): what a stop leaves (listing_stopped; Hangul measured: the
# syllables left as they are)
CANCEL_NOTE = u"A listing or a Hangul measuring stopped changes nothing in the font."


def bar_share(steps, label, part=0.0):
    """How far the bar is, 0 to 1, at this part (0 to 1) of the step of that label; None for a step that is
    not one of these steps."""
    start = 0.0
    for name, end in steps:
        if name == label:
            return start + (end - start) * min(max(float(part), 0.0), 1.0)
        start = end
    return None


def compile_on(writable, code):
    """Whether Compile after writing is clickable: only with the write button (owner's image 195), and only
    when the write would change feature code (code) for the compile to read."""
    return bool(writable and code)


def trims_status(trimmed, full, palt, halt, button, korean=u"", bold=lambda text: u"%s" % text,
                 italic=lambda text: u"%s" % text):
    """The status line under the font's: how many of the font's full-width kana and punctuation (full) get a
    trim (trimmed: palt of them in palt, halt in halt), right at 0, 1, and 2; button: the write button's name;
    korean: hangul_note's sentence. A count is bold with the noun it counts (owner's images 297 and 301: "2 of
    the 1,200 full-width kana and punctuation"); palt's and halt's numbers, with no noun of their own, alone."""
    number = lambda value: bold(u"{:,}".format(value))
    if not full:
        return u"No full-width kana or CJK punctuation: nothing to trim.%s" % korean
    if not trimmed:
        text = (u"The only full-width kana or punctuation mark needs no trim." if full == 1 else
                u"None of the %s needs a trim." % bold(u"{:,} full-width kana and punctuation".format(full)))
        return text + korean
    if full == 1:
        text = u"The only full-width kana or punctuation mark gets a trim"
    else:
        text = u"%s %s a trim" % (bold(u"{:,} of the {:,} full-width kana and punctuation".format(trimmed, full)),
                                  u"gets" if trimmed == 1 else u"get")
    return u"%s (palt: %s, halt: %s). Nothing is written until you click %s.%s" % (
        text, number(palt), number(halt), italic(button), korean)


def font_line(ak, package, master=None):
    """The top line's start, as every window's (ak.font_named): the font, its master, and how many masters it
    has where more than one (owner's images 223 and 238); u"" without a font. Shared with CJK Vertical."""
    if package is None:
        return u""
    masters = getattr(package, "mastersCount", None)
    if masters is None:
        try:
            masters = len(list(package.masters))
        except Exception:
            masters = 1
    return ak.font_named(getattr(package, "tfn", u""), master or getattr(package, "master", None), masters) + u"."


def head_join(ak, font, rest):
    """ak.head_join (the font's sentence, a blank line, what the tool found), or the two joined by a space where
    the shared module has none (an older one, a test's stand-in)."""
    join = getattr(ak, "head_join", None)
    if join is not None:
        return join(font, rest)
    return (u"%s %s" % (font or u"", rest or u"")).strip()


def stopped_line(what=u"Listing"):
    """The status line once the user stopped the work (the top row's Esc, Close, a tool, an arrow): nothing is
    listed, and a link lists it again (the window has no button of its own for it)."""
    return u'%s was stopped: nothing is listed. <a href="%s">List again</a>' % (what, LIST_AGAIN)


def sample_share(index, codes):
    """The share of the sample's characters the font has."""
    chars = [ord(ch) for ch in SAMPLES[index][2] if not ch.isspace()]
    return round(sum(1 for code in chars if code in codes) / float(len(chars) or 1), 3)


def writing_hints(family=u"", code_pages=()):
    """The sample keys the font's family name points to (its words), else those of its code page bits when
    they point to one writing only: [] when neither says."""
    words = re.split(r"[^A-Za-z0-9]+", u"%s" % (family or u""))
    named = []
    for word in words:
        key = NAME_HINTS.get(word.upper())
        if key is not None and key not in named:
            named.append(key)
    if named:
        return named
    paged = sorted(set(CODE_PAGE_HINTS[bit] for bit in (code_pages or ()) if bit in CODE_PAGE_HINTS))
    return paged if len(paged) == 1 else []


def best_sample(codes, family=u"", code_pages=()):
    """The index in SAMPLES of the sample in the font's own writing: the one its family name or its code page
    bits name (writing_hints), where it covers at least MIN_SAMPLE_SHARE of it; else Korean for a font with
    Hangul syllables, Japanese for one with kana, and Chinese otherwise, Simplified or Traditional as it covers
    them; the sample it covers best where it has none of these (a font of punctuation alone). Kana alone
    cannot say Japanese: the Chinese fonts carry kana too (GB 2312 and Big5 have it; IBM Plex Sans JP's
    covers the Traditional sample as fully as the Iroha, which put the Traditional sample first for it).
    A font with no CJK character at all (has_cjk: a Latin font) gets the first: its comma and period made the
    Korean sample the one it covered best (owner's image 359)."""
    codes = set(codes)
    if not has_cjk(codes):
        return 0
    keys = [key for key, _, _ in SAMPLES]

    def covered(key):
        return key in keys and sample_share(keys.index(key), codes) >= MIN_SAMPLE_SHARE

    for key in writing_hints(family, code_pages):
        if covered(key):
            return keys.index(key)
    if any(HANGUL_SYLLABLES[0] <= code <= HANGUL_SYLLABLES[1] for code in codes) and covered("ko"):
        return keys.index("ko")
    if any(KANA[0] <= code <= KANA[1] for code in codes) and covered("ja"):
        return keys.index("ja")
    chinese = [keys.index(key) for key in ("zh-hans", "zh-hant") if covered(key)]
    if chinese:
        return max(chinese, key=lambda index: (sample_share(index, codes), -index))

    def score(index):
        own = sum(1 for code in codes for low, high in SAMPLE_SCRIPTS.get(keys[index], ()) if low <= code <= high)
        return (sample_share(index, codes), own, -index)
    return max(range(len(SAMPLES)), key=score)


# What a font lacks that makes a sample show only its punctuation, by the sample's key (its Sample: item)
SAMPLE_LACKS = {"ja": u"no kana", "ko": u"no Hangul", "zh-hans": u"no ideographs", "zh-hant": u"no ideographs"}


def offered_samples(samples, codes):
    """Which samples (samples: (key, label, text) as SAMPLES) a font is offered: those it has a character of
    in the sample's own writing (SAMPLE_SCRIPTS: kana for Japanese, Hangul syllables for Korean, ideographs
    for Chinese). Without one, a sample's previews held its punctuation alone (owner's image 304: the Korean
    sample showed 「 , . in a Japanese font with no Hangul). A font with none of any (punctuation alone) is
    offered every sample: its punctuation is all there is to see, in any of them. [True or False] per sample."""
    codes = set(codes)
    offered = []
    for key, _, text in samples:
        ranges = SAMPLE_SCRIPTS.get(key, ())
        offered.append(any(ord(ch) in codes and any(low <= ord(ch) <= high for low, high in ranges) for ch in text))
    return offered if any(offered) else [True] * len(offered)


def sample_label(sample, offered):
    """A sample's item in the Sample: dropdown: its name, and what the font lacks for it where it is not
    offered (grayed): "Korean (no Hangul in the font)", "Chinese (Simplified, no ideographs in the font)"."""
    key, label = sample[0], sample[1]
    lacks = SAMPLE_LACKS.get(key)
    if offered or not lacks:
        return label
    if label.endswith(u")"):  # (one pair of parentheses: never "Chinese (Simplified) (no ...)")
        return u"%s, %s in the font)" % (label[:-1], lacks)
    return u"%s (%s in the font)" % (label, lacks)


def shown_whole(label, pixmap, QtCore):
    """A preview's picture (pixmap, as last drawn) shown whole in its label as the window is resized: scaled down
    where the label is now smaller, as drawn otherwise, until it is drawn again for its new size (debounced:
    a drag of the window's edge restarts the wait at each step, and meanwhile the label cut the centered
    lines' ends off, owner's image 356). Never raises."""
    if pixmap is None:
        return
    try:
        width, height = (int(_value(label, name)) for name in ("width", "height"))
        if width > 0 and height > 0 and (pixmap.width() > width or pixmap.height() > height):
            label.setPixmap(pixmap.scaled(width, height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            label.setPixmap(pixmap)
    except Exception:
        pass


def _value(obj, name):
    """A Qt property as PythonQt gives it: an attribute, or a method in some builds."""
    value = getattr(obj, name)
    return value() if callable(value) else value


def offer_samples(combo, samples, offered, QtCore):
    """The Sample: dropdown's items named and grayed as offered_samples says (a grayed item cannot be
    picked: its flags, Qt.UserRole - 1 of the dropdown's model, set to none; given back unset). Never
    raises."""
    for index, sample in enumerate(samples):
        on = offered[index] if index < len(offered) else True
        try:
            combo.setItemText(index, sample_label(sample, on))
            combo.setItemData(index, None if on else 0, QtCore.Qt.UserRole - 1)
        except Exception:
            pass


def font_hints(package):
    """(family name, OS/2 code page bits) of a FontLab font, for best_sample: ("", ()) where it has none."""
    try:
        info = package.fgPackage.info
    except Exception:
        return u"", ()
    family = u""
    for field in ("openTypeNamePreferredFamilyName", "familyName"):
        try:
            family = getattr(info, field, None) or u""
        except Exception:
            family = u""
        if family:
            break
    if not family:
        try:
            family = package.tfn or u""
        except Exception:
            family = u""
    try:
        pages = tuple(int(bit) for bit in (info.openTypeOS2CodePageRanges or ()))
    except Exception:
        pages = ()
    return u"%s" % family, pages


CJK_RANGES = ((0x3000, 0x30FF), (0x3100, 0x31FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7A3),
              (0xF900, 0xFAFF), (0xFF00, 0xFFEF), (0x1100, 0x11FF), (0x3130, 0x318F))


def sample_misses(codes, text):
    """The font's CJK characters (sorted) when the sample text shows none of them, else []: the
    preview would be empty, so the log names them."""
    codes = set(codes)
    if any(ord(ch) in codes for ch in text if not ch.isspace()):
        return []
    return [unichr_(code) for code in sorted(codes) if any(low <= code <= high for low, high in CJK_RANGES)]


def counted_chars(number):
    return counted(number, u"CJK character")


# Kinsoku, as Japanese sets lines: never first on a line (closing marks, small kana, the long vowel
# mark), never last (opening marks)
NO_LINE_START = set(u"、。，．・：；？！）」』】〕〉》｝］ー々ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ,.:;?!)]}")
NO_LINE_END = set(u"「『（【〔〈《｛［([{")


def break_lines(chars, widths, room):
    """A sample's lines: [(start, end)] ranges of its characters, each line no wider than room
    (widths: each character's, in the same unit), unless one character alone is. A line breaks after
    a space where it has one (Korean), else between any two characters but not before a closing mark
    or a small kana, nor after an opening mark; the spaces a break leaves at a line's start are dropped."""
    lines, start, count = [], 0, len(chars)
    while start < count:
        while start < count and chars[start] == u" ":
            start += 1
        if start >= count:
            break
        width, end = 0.0, start
        while end < count and (end == start or width + widths[end] <= room):
            width += widths[end]
            end += 1
        if end < count:
            spaces = [k for k in range(end, start, -1) if chars[k - 1] == u" "]
            fits = [k for k in range(end, start, -1)
                    if chars[k] not in NO_LINE_START and chars[k - 1] not in NO_LINE_END]
            end = spaces[0] if spaces else (fits[0] if fits else end)
        stop = end
        while stop > start and chars[stop - 1] == u" ":
            stop -= 1
        lines.append((start, stop))
        start = end
    return lines


SMALL_KANA = set([0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3063, 0x3083, 0x3085, 0x3087, 0x308E, 0x3095, 0x3096,
                  0x30A1, 0x30A3, 0x30A5, 0x30A7, 0x30A9, 0x30C3, 0x30E3, 0x30E5, 0x30E7, 0x30EE, 0x30F5, 0x30F6])


def kind_of(code):
    """The kind of glyph a code point is, as palt groups them, or None."""
    if 0x3041 <= code <= 0x3096:
        return "small hiragana" if code in SMALL_KANA else "hiragana"
    if 0x30A1 <= code <= 0x30FA:
        return "small katakana" if code in SMALL_KANA else "katakana"
    if code in (0x30FC, 0x30FB, 0x309B, 0x309C):
        return "punctuation"
    if 0x3000 < code <= 0x303F or 0xFF01 <= code <= 0xFF60 or code in (0x2018, 0x2019, 0x201C, 0x201D):
        return "punctuation"
    if 0xAC00 <= code <= 0xD7A3:
        return "hangul"
    return None


VERTICAL_VOWELS = (0, 1, 2, 3, 4, 5, 6, 7, 20)  # a, ae, ya, yae, eo, e, yeo, ye, i: beside the initial
HORIZONTAL_VOWELS = (8, 12, 13, 17, 18)  # o, yo, u, yu, eu: under it; the others are both


def hangul_shape(code):
    """A Hangul syllable's shape: its vowel beside its initial ("vertical": 가), under it
    ("horizontal": 고), or both ("mixed": 과), with " final" for a final consonant (각)."""
    index = code - 0xAC00
    vowel, final = (index % 588) // 28, index % 28
    shape = "vertical" if vowel in VERTICAL_VOWELS else "horizontal" if vowel in HORIZONTAL_VOWELS else "mixed"
    return shape + (" final" if final else "")


def all_codes(glyphs):
    """{code point: glyph name} of every code point of each glyph (fgGlyph.unicodes; unicode alone gives
    the first, and a CJK font encodes 日 at the Kangxi radical U+2F47 first: IBM Plex Sans JP's 日 月 玄
    黄 辰 went missing from the samples). The first glyph at a code point wins, as in a cmap."""
    found = {}
    for glyph in glyphs:
        try:
            codes = [int(code) for code in (glyph.unicodes or [])]
        except Exception:
            codes = []
        if not codes and getattr(glyph, "unicode", None):
            codes = [int(glyph.unicode)]
        for code in codes:
            found.setdefault(code, u"%s" % glyph.name)
    return found


def unichr_(code):
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def load_model(path=None, name=MODEL_FILE):
    """The CJK fonts' trims (palt_model.json beside this script), or another model there, or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), name)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class Trim(object):
    """A glyph's palt (and halt) adjustment: x placement and x advance, in font units."""

    def __init__(self, code, name, kind, advance, left, right):
        self.code, self.name, self.kind = code, name, kind
        self.advance, self.left, self.right = advance, left, right  # its ink's left and right edges
        self.palt = None  # (x placement, x advance) or None
        self.halt = None
        self.checked = True

    @property
    def char(self):
        return unichr_(self.code)

    def width_after(self):
        return self.advance + (self.palt[1] if self.palt else 0)


def suggest(trim, model, upm, tolerance=TOLERANCE_UNITS):
    """The trim's palt and halt adjustments, by the model: its ink kept, its sidebearings the corpus's
    (the mark's own where the corpus has it, else its kind's). A glyph that is not full width, or whose
    trim is within the tolerance, gets none."""
    if trim.advance < FULL_WIDTH_SHARE * upm or trim.right <= trim.left:
        return trim
    sides = model.get("palt", {}).get(u"U+%04X" % trim.code) or model.get("palt", {}).get(trim.kind)
    if sides:
        placement = int(round(sides[0] * upm - trim.left))
        advance = int(round((trim.right - trim.left) + (sides[0] + sides[1]) * upm - trim.advance))
        if abs(placement) >= tolerance or abs(advance + placement) >= tolerance:
            trim.palt = (placement, advance)
    half = model.get("halt", {}).get(u"U+%04X" % trim.code)
    if half and trim.kind == "punctuation":
        trim.halt = (int(round(half[0] * upm)), int(round(half[1] * upm)))
    return trim


def plan(glyphs, model, upm):
    """Trims for the font's glyphs: glyphs [(code, name, advance, ink left, ink right)]."""
    trims, seen = [], set()
    for code, name, advance, left, right in sorted(glyphs):
        kind = kind_of(code)
        if kind not in KINDS or name in seen:
            continue
        seen.add(name)
        trim = suggest(Trim(code, name, kind, advance, left, right), model, upm)
        if trim.palt or trim.halt:
            trims.append(trim)
    return trims


class HangulChange(object):
    """A Hangul syllable set anew: its outline moved by shift, its width made advance."""

    def __init__(self, code, name, shape, shift, advance, old_advance):
        self.code, self.name, self.shape = code, name, shape
        self.shift, self.advance, self.old_advance = shift, advance, old_advance


def half_up(value):
    """Rounded half up, as both Pythons do it alike (Python 3's round goes to the even number)."""
    import math
    return int(math.floor(value + 0.5))


def hangul_change(code, name, advance, left, right, mode, model, upm, width=None):
    """A syllable's change for a mode ("fixed": one width, its ink centered; "proportional": the
    corpus's sidebearings for its shape), or None when it stays within the tolerance."""
    shape = hangul_shape(code)
    ink = right - left
    if mode == "fixed":
        new_advance = half_up(width if width else (model.get("fixed_width") or 0.9) * upm)
        new_left = (new_advance - ink) / 2.0
    elif mode == "proportional":
        sides = model.get("proportional", {}).get(shape)
        if not sides:
            return None
        new_left = sides[0] * upm
        new_advance = ink + (sides[0] + sides[1]) * upm
    else:
        return None
    shift = half_up(new_left - left)
    new_advance = half_up(new_advance)
    if abs(shift) < HANGUL_TOLERANCE and abs(new_advance - advance) < HANGUL_TOLERANCE:
        return None
    return HangulChange(code, name, shape, shift, new_advance, advance)


def value_rule(name, value):
    return u"pos %s <%d 0 %d 0>;" % (name, value[0], value[1])


def feature_text(tag, old, rules):
    """A feature's code with FreeLab's block of rules in place before its closing brace: an older FreeLab
    block taken out, the rest kept, FontLab's automatic block handed back ("#/> feature"); or None where
    FreeLab cannot read the code safely (its own markers not in pairs, or the feature's braces not found):
    nothing is written then. Read by tokens, as Feature Code reads every feature (feature_code: Codex
    reviews 5 and 6, an end marker after code on its line, a feature on one line, another feature's code
    given for this one)."""
    fc = feature_code_or_none()
    if fc is None:  # (no reader: nothing written; the window says why: feature_code_problem)
        return None
    begin, end = BEGIN % tag, END % tag
    block = [begin] + [u"  %s" % rule for rule in rules] + [end] if rules else []
    try:
        fc.readable(old, tag)  # (taking a block out too: Codex review 7)
        text = fc.handed_back(fc.without_blocks(old, begin, end, tag)).rstrip(u"\r\n")
        if not block and fc.code_tokens(text):
            fc.readable(text, tag)
            return text + u"\n"
        return fc.insert_block(text, tag, block, title=FEATURE_TITLES.get(tag, tag), blank=True) + u"\n"
    except fc.FeatureCodeUnreadable:
        return None


def feature_code_or_none():
    """Feature Code's reader (feature_code), or None where it cannot be loaded (missing, or broken): its
    error kept for feature_code_problem. Codex review 7: a missing script raised out of the windows'
    button updates and writes."""
    try:
        module = feature_code()
        missing = [name for name in READER_API if not callable(getattr(module, name, None))]
        unreadable = getattr(module, "FeatureCodeUnreadable", None)
        if not isinstance(unreadable, type) or not issubclass(unreadable, Exception):
            missing.append(u"FeatureCodeUnreadable")
        if missing:  # (an older or incomplete script loads, then fails: Codex review 8, no readable in it)
            raise ImportError(u"an older or incomplete one, without %s" % u", ".join(missing))
    except Exception as exc:
        FEATURE_CODE_ERROR[:] = [u"%s" % exc]
        return None
    del FEATURE_CODE_ERROR[:]
    return module


# What CJK Spacing and CJK Vertical call of Feature Code's reader: a script without one of them is unavailable
READER_API = ("readable", "without_blocks", "handed_back", "code_tokens", "insert_block", "block_text",
              "feature_bounds")


FEATURE_CODE_ERROR = []  # (the last failure to load Feature Code's reader)


def feature_code_problem(tool):
    """What the window says, its write grayed out, where Feature Code's reader cannot be loaded; else empty."""
    if feature_code_or_none() is not None:
        return u""
    return (u"%s cannot read the font's feature code: FreeLab's Feature Code script (freelab_feature_code.py), "
            u"which it reads and writes code with, is missing or broken (%s). Reinstall FreeLab; nothing is "
            u"written until then." % (tool, FEATURE_CODE_ERROR[0] if FEATURE_CODE_ERROR else u"not found"))


VERTICAL_FILE, VERTICAL_MODULE = "freelab_cjk_vertical.py", "freelab_cjk_vertical"


def preview_note(text, names, bold=lambda text: text, escape=lambda text: text):
    """CJK Vertical's note on what the previews show of a sample the font lacks some of (its preview_note),
    for this window's previews too (owner's image 360), said in the log (LacksNote); u"" where CJK Vertical
    cannot be loaded."""
    try:
        here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
        path = os.path.join(here, VERTICAL_FILE)
        held = sys.modules.get(VERTICAL_MODULE)
        if held is None or not callable(getattr(held, "preview_note", None)):
            if not os.path.isfile(path):
                return u""
            old = os.environ.get("FREELAB_NO_AUTOSTART")
            os.environ["FREELAB_NO_AUTOSTART"] = "1"
            try:
                if sys.version_info[0] == 2:
                    import imp
                    held = imp.new_module(VERTICAL_MODULE)
                    held.__file__ = path
                    with open(path, "rb") as handle:
                        source = handle.read()
                    exec(compile(source, VERTICAL_FILE, "exec", 0, True), held.__dict__)
                else:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(VERTICAL_MODULE, path)
                    held = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(held)
                sys.modules[VERTICAL_MODULE] = held
            finally:
                if old is None:
                    os.environ.pop("FREELAB_NO_AUTOSTART", None)
                else:
                    os.environ["FREELAB_NO_AUTOSTART"] = old
        return held.preview_note(text, names, bold, escape)
    except Exception:
        return u""


NOTE_PAUSE = 700  # milliseconds of a pause in the typing before the log says what a typed sample lacks


class LacksNote(object):
    """The previews' note (preview_note) in the window's log: it was a quiet line between the previews and
    the Code preview while the log under it stayed empty (the owner, of both CJK windows: "Shouldn't we
    have this line in the log instead?"). Said as it first applies, and again only when its words change
    or another font is read: a refresh that leaves them as they are (a tick, a resize, the History read
    again) says nothing. While the sample is typed into, it waits for a pause in the typing (NOTE_PAUSE),
    as Font Check's search does: each keystroke would add a line. Shared by CJK Spacing and CJK Vertical;
    ak: the shared module (font_key); parent: the window, the timer's parent (Qt deletes it with it)."""

    def __init__(self, ak, log, parent=None):
        self.ak, self.log, self.said, self.waiting, self.timer = ak, log, None, None, None
        if parent is None:
            return  # (no timer: said at once)
        try:
            QtCore = _qt()[0]
            timer = QtCore.QTimer(parent)
            timer.setSingleShot(True)
            timer.setInterval(NOTE_PAUSE)
            timer.connect("timeout()", self.paused)
            self.timer = timer
        except Exception:
            self.timer = None

    def show(self, package, words, typed=False):
        """words: preview_note's for the font package (None: no font), u"" where it has every character
        of the sample; typed: the sample was typed into, so said once the typing pauses."""
        try:
            font = self.ak.font_key(package) if package is not None else None
        except Exception:
            font = None
        self.waiting = (font, words or u"")
        if typed and self.timer is not None:
            self.timer.start()  # (from this keystroke again)
        else:
            self.now()

    def paused(self):
        try:
            self.now()
        except Exception:
            pass  # a timer's handler must not raise

    def now(self):
        """What waits said now: the pause over, a sample chosen in Sample:, or a refresh of the previews.
        A note gone (u"") says nothing, but the same words coming back later are said again."""
        if self.timer is not None:
            try:
                self.timer.stop()
            except Exception:
                pass
        waiting, self.waiting = self.waiting, None
        if waiting is None or waiting == self.said:
            return
        self.said = waiting
        if waiting[1]:
            self.log.add(waiting[1])  # (rich text: its counts bold, as preview_note makes them)


FEATURE_CODE_FILE, FEATURE_CODE_MODULE = "freelab_feature_code.py", "freelab_feature_code"


def hold_module(module):
    """A FreeLab module kept alive once a newer copy replaces it in sys.modules (a reinstall in the same FontLab
    session), in the list freelab_auto_kerning's hold_module keeps in sys, which this script need not load to
    use: Python 2.7 empties a module's globals when the module object is freed, and a window of the old copy
    still open then ran its slots with every global None (adversarial review 3: these loaders let it go)."""
    if module is None:
        return
    held = getattr(sys, "_freelab_held_modules", None)
    if held is None:
        held = sys._freelab_held_modules = []
    if not any(m is module for m in held):
        held.append(module)


hold_module(sys.modules.get(__name__))  # (this copy: the windows it serves keep working after a reinstall)


def feature_code():
    """Feature Code as a module (its main() not run): its reading of feature code by tokens, which CJK
    Spacing and CJK Vertical write through too. Beside this script once installed, in the repository's
    features folder before; loaded again when its file changed."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    paths = [os.path.join(here, FEATURE_CODE_FILE), os.path.join(here, os.pardir, "features", FEATURE_CODE_FILE)]
    path = next((path for path in paths if os.path.isfile(path)), paths[0])
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(FEATURE_CODE_MODULE)
    if held is not None and hasattr(held, "without_blocks") and getattr(held, "_freelab_stamp", stamp) == stamp:
        return held
    hold_module(held)  # (a Feature Code window of the copy replaced keeps its globals)
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(FEATURE_CODE_MODULE)
            module.__file__ = path
            sys.modules[FEATURE_CODE_MODULE] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, FEATURE_CODE_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(FEATURE_CODE_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[FEATURE_CODE_MODULE] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(FEATURE_CODE_MODULE, None)
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def expand_ranges(text):
    """The glyph names of a class's members, a range among them (uni3041-uni3045, or cid00010-cid00012:
    the same name with a number counting up, as the feature syntax allows) spelled out."""
    import re
    names = []
    for token in text.split():
        match = re.match(u"^(uni|u)([0-9A-Fa-f]{4,6})-(uni|u)([0-9A-Fa-f]{4,6})$", token) or             re.match(u"^(.*?)([0-9]+)-(.*?)([0-9]+)$", token)
        if match and match.group(1) == match.group(3) and not token.startswith(u"@"):
            prefix, first, last = match.group(1), match.group(2), match.group(4)
            base = 16 if prefix in (u"uni", u"u") and match.re.pattern.startswith(u"^(uni") else 10
            try:
                start, end = int(first, base), int(last, base)
            except ValueError:
                names.append(token)
                continue
            if 0 <= end - start <= 5000 and len(first) == len(last):
                form = (u"%%0%dX" if base == 16 else u"%%0%dd") % len(first)
                names.extend(prefix + form % number for number in range(start, end + 1))
                continue
        names.append(token)
    return names


# ---------------------------------------------------------------------------
# The font's own feature code, as the compiler reads it: CJK Spacing's and CJK Vertical's one reader (CJK
# Vertical loads this module). A glyph the font's own code gives a single value in a feature must get no
# second one from FreeLab: the compiler refuses it ("Duplicate single positioning glyph with different
# values"). Live (IBM Plex Sans JP, 2026-11-15): its palt is "pos @palt -500;", the class defined in the
# prefix, and a reader of the feature's own text alone let FreeLab add uni3001 to it.
# ---------------------------------------------------------------------------

CLASS_DEFINITION = re.compile(u"(@[A-Za-z0-9_.\\-]+)\\s*=\\s*\\[([^\\]]*)\\]")
GLYPH_TOKEN = u"(\\[[^\\]]*\\]|@[A-Za-z0-9_.\\-]+|[A-Za-z_.\\\\][A-Za-z0-9_.\\-\\\\]*)"  # a [list], a @class, a glyph
# A single position: its glyphs, then one value, a record (<-10 0 -20 0>) or a number (format A: the advance
# along the feature's direction); nothing after it (a pair, or a contextual rule, has more)
SINGLE_POSITION = re.compile(u"^\\s*(?:enum\\s+)?pos(?:ition)?\\s+" + GLYPH_TOKEN + u"\\s*(<[^>]*>|-?[0-9]+)\\s*$")
POSITION_KEYWORDS = (u"cursive", u"base", u"mark", u"ligature")  # (pos cursive ...: attachments, no single values)
LOOKUP_BLOCK = re.compile(u"lookup\\s+([A-Za-z0-9_.\\-]+)(?:\\s+useExtension)?\\s*\\{(.*?)\\}\\s*\\1\\s*;", re.S)
LOOKUP_USE = re.compile(u"^\\s*lookup\\s+([A-Za-z0-9_.\\-]+)\\s*$")


def without_comments(text):
    return re.sub(u"#[^\\n]*", u"", text or u"")


def code_classes(text):
    """{@name: [members]} of the classes a feature code (or the prefix) defines (ranges spelled out)."""
    found = {}
    for match in CLASS_DEFINITION.finditer(without_comments(text)):
        found[match.group(1)] = expand_ranges(match.group(2))
    return found


def class_members(token, classes, depth=0):
    """The glyphs a token names: a glyph, a [list], or a @class (classes: {@name: [members]})."""
    token = token.strip()
    if token.startswith(u"[") and token.endswith(u"]"):
        return [g for part in expand_ranges(token[1:-1]) for g in class_members(part, classes, depth + 1)]
    if token.startswith(u"@"):
        if depth > 8:
            return []
        return [g for part in classes.get(token, []) for g in class_members(part, classes, depth + 1)]
    return [token]


def code_lookups(text):
    """{name: body} of the named lookups a feature code (or the prefix) defines."""
    return dict((m.group(1), m.group(2)) for m in LOOKUP_BLOCK.finditer(without_comments(text)))


def feature_statements(tag, text, lookups=None, begin=BEGIN, end=END, depth=0):
    """The statements of a feature's own code (outside FreeLab's block, begin and end % tag), each with
    what opens a block before it on its line taken off (lookup X { sub a by b;), and a lookup the code
    names (lookup X;), defined there or in the prefix (lookups: {name: body}), read as its rules."""
    first, last = begin % tag, end % tag
    known = dict(lookups or {})
    known.update(code_lookups(text))
    # (FreeLab's block found by its markers as comments, wherever they stand: Feature Code's without_blocks;
    # markers not in pairs leave the text whole, every rule in it taken for the font's)
    try:
        text = feature_code_or_none().without_blocks(text, first, last, tag, strict=False)
    except Exception:
        pass  # (no Feature Code beside it: the text whole)
    for line in (text or u"").splitlines():
        for statement in without_comments(line).split(u";"):
            statement = statement.split(u"{")[-1].split(u"}")[-1]
            use = LOOKUP_USE.match(statement)
            if use and use.group(1) in known and depth < 4:
                for inner in feature_statements(tag, known[use.group(1)], known, begin, end, depth + 1):
                    yield inner
                continue
            yield statement


def single_positions(tag, text, classes=None, lookups=None, begin=BEGIN, end=END):
    """[(glyph, value)] of the single positions a feature's own code gives (pos a <-10 0 -20 0>; pos [a b]
    <...>; pos @class -500; position, enum pos), the value as written ("<-10 0 -20 0>", "-500"): the
    classes the code defines, the font's (classes: {@name: [members]}, its prefix's and its class list's),
    and those of the lookups it names (lookups: the prefix's, {name: body}) read too."""
    known = dict(classes or {})
    for body in (lookups or {}).values():
        known.update(code_classes(body))
    known.update(code_classes(text))
    found = []
    for statement in feature_statements(tag, text, lookups, begin, end):
        match = SINGLE_POSITION.match(statement)
        if match and match.group(1) not in POSITION_KEYWORDS:
            found.extend((glyph, match.group(2)) for glyph in class_members(match.group(1), known))
    return found


def font_positioned(tag, text, classes=None, lookups=None, begin=BEGIN, end=END):
    """The glyphs a feature's own code gives a single value (single_positions): FreeLab writes none for
    them. A pair or a contextual rule is not a single value."""
    return set(glyph for glyph, _ in single_positions(tag, text, classes, lookups, begin, end))


def read_prefix(features):
    """The font's feature prefix (its classes and lookups, which the features name), or None unread."""
    try:
        return features.get_prefix()
    except Exception:
        return None


def font_classes(package, prefix):
    """{@name: [members]} of the font's classes: FontLab's own feature classes (its class list) and those
    its prefix defines."""
    classes = {}
    try:
        for group in package.getAllGroups():
            if not group[0]:  # (a kerning class has True)
                classes[u"@%s" % group[1]] = [u"%s" % name for name in group[4]]
    except Exception:
        pass
    try:
        classes.update(code_classes(prefix))
    except Exception:
        pass
    return classes


def texts_for(trims, old_texts, palt_on=True, halt_on=True, kept=None, classes=None, lookups=None, refused=None):
    """{tag: new code} for palt and halt from the checked trims. Glyphs the feature's own code positions
    already (font_positioned: the font's classes and the prefix's lookups read too) keep it (no second
    value); kept, when given, gets {tag: [their names]}; refused, when given, the tags of the features
    whose braces FreeLab cannot find (left as they are)."""
    chosen = [t for t in trims if t.checked]
    new = {}
    for tag, on, value in (("palt", palt_on, lambda t: t.palt), ("halt", halt_on, lambda t: t.halt)):
        own = font_positioned(tag, old_texts.get(tag), classes, lookups)
        if kept is not None and on:
            kept[tag] = [t.name for t in chosen if value(t) and t.name in own]
        rules = [value_rule(t.name, value(t)) for t in chosen if value(t) and t.name not in own] if on else []
        old = old_texts.get(tag)
        if rules or (BEGIN % tag) in (old or u""):  # (an empty feature is not made; an old block is taken out)
            text = feature_text(tag, old, rules)
            if text is None:
                if refused is not None:
                    refused.append(tag)
                continue
            new[tag] = text
    return new


def refused_words(tags):
    """The log's sentence for features left as they are (feature_text found no braces), or empty."""
    if not tags:
        return u""
    one = len(tags) == 1
    return (u"FreeLab leaves %s as %s: it cannot find where %s code begins and ends (the feature's braces), so "
            u"nothing of FreeLab's goes in. Check %s code in FontLab's <i>Features</i> panel." % (
                u" and ".join(sorted(set(tags))), u"it is" if one else u"they are",
                u"that feature's" if one else u"each one's", u"its" if one else u"their"))


KEPT_SHOWN = 30  # glyphs the line on those the font's own code positions names at most (the rest an ellipsis)


def kept_names(names, link):
    """The glyphs the font's own palt or halt code positions already, as the log names them: each glyph's name a
    link (ak.glyph_name_link), with a space between, the first KEPT_SHOWN only, then an ellipsis."""
    shown = u" ".join(link(name) for name in names[:KEPT_SHOWN])
    return shown + (u" \N{HORIZONTAL ELLIPSIS}" if len(names) > KEPT_SHOWN else u"")


UNCOMPARED = object()


def changed_features(features, texts, tags, prefix=UNCOMPARED):
    """What differs in the font from the code read with the list (texts: {tag: code}, a feature the font
    lacked then left out; prefix, when given: read_prefix's then): the tags, and "prefix". A write composed
    from that code would undo an edit made since (Feature Code's check before it writes). A feature that
    cannot be read counts as changed."""
    try:
        present = set(features.keys())
    except Exception:
        return list(tags)
    changed = []
    for tag in tags:
        try:
            now = features.get_feature(tag) if tag in present else None
        except Exception:
            changed.append(tag)
            continue
        if now != texts.get(tag):
            changed.append(tag)
    if prefix is not UNCOMPARED and read_prefix(features) != prefix:
        changed.append(u"prefix")
    return changed


def block_of(tag, text):
    """FreeLab's block of a feature, alone in a feature of its own (for the parser's check), or None."""
    fc = feature_code_or_none()
    inner = fc.block_text(text, BEGIN % tag, END % tag) if fc is not None else None  # (markers as comments)
    if inner is None:
        return None
    return u"feature %s {\n%s} %s;\n" % (tag, inner, tag)


CODE_PREVIEW_HEADING = u"Code preview"  # (not "Code": it is not written yet, owner's images 299 and 305)
NO_CODE = u"# No code to write: what is ticked changes none of the font's feature code."
# (a font the list is empty for has nothing ticked: owner's image 29, 2026-11-24)
NO_CODE_EMPTY = u"# No code to write: this font has nothing to tick here."
CODE_PREVIEW_WHAT = (u"The code the write button would write, as the ticks and options stand: palt and halt "
                     u"whole, FreeLab's block between its marker lines, the rest of each feature as it is (a feature "
                     u"the font has as shown already is left out: nothing to write). Nothing is written until you click "
                     u"the button.")


def preview_code(new, old_texts, tags, also=(), empty=False):
    """The Code preview's text (owner's image 305: CJK Spacing and CJK Vertical wrote code and showed none):
    the code the write button would write, feature by feature in tags' order, each whole as it would stand in
    the font (new: {tag: feature code}; those the same as the font's, old_texts, left out: not written), else
    NO_CODE. also: comment lines for what the write changes besides code (Hangul widths, glyphs built), each
    one under the code. empty: the list has no row to tick, said in place of NO_CODE."""
    shown = [new[tag].rstrip(u"\r\n") for tag in tags if tag in new and new[tag] != old_texts.get(tag)]
    notes = [u"# %s" % line for line in also if line]
    if not shown:
        return u"\n".join([NO_CODE_EMPTY if empty else NO_CODE] + notes)
    return u"\n\n".join(shown) + (u"\n\n" + u"\n".join(notes) if notes else u"") + u"\n"


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 32
PREVIEW_EM = 44  # pixels per em, the sample's previews at most
SMALLEST_PREVIEW_EM = 20  # and at least (a long text of one's own takes more lines)
SAMPLE_LINES = 3  # the lines a sample is set in, where the em allows (owner's image 303: the Iroha in three)


LINE_STEP = 1.25  # a preview's line height, in ems (picture)
PREVIEW_LEAST_HEIGHT = int(SMALLEST_PREVIEW_EM * LINE_STEP * SAMPLE_LINES) + 8  # a preview made as short as it can be


def fitted_em(em, tall, lines=SAMPLE_LINES, smallest=SMALLEST_PREVIEW_EM):
    """em, made no larger than SAMPLE_LINES lines fit in a preview tall pixels high (picture's lines are
    LINE_STEP ems apart), never under smallest; em as it is when the height is not known (tall None)."""
    if not tall:
        return em
    return max(smallest, min(em, int((tall - 8) / (LINE_STEP * lines))))


def preview_em(chars, ems, room, lines=SAMPLE_LINES, largest=PREVIEW_EM, smallest=SMALLEST_PREVIEW_EM):
    """The previews' em, in pixels: the largest from largest down to smallest at which the sample (chars, each
    ems wide at an em of 1 pixel: its advance over the em, as it is set now) breaks into lines of room pixels
    (break_lines, kinsoku kept) no more than lines of them: owner's image 303, the Iroha at 44 pixels took four
    lines in the window's usual width, a lone character on the last. Derived from the previews' width and the
    sample's length, so a wider window sets it larger (to largest), a narrower one smaller. smallest where
    none fits; largest without room (Qt does not say) or text."""
    if not room or not chars:
        return largest
    total = float(sum(ems)) or 1.0
    em = int(min(largest, max(smallest, room * lines / total)))  # (no em above this fills fewer lines)
    while em > smallest:
        if len(break_lines(chars, [width * em for width in ems], room)) <= lines:
            return em
        em -= 1
    return smallest


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: the dialogs' shared helpers."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "load_sibling") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    hold_module(held)  # (the windows of the copy replaced keep their globals)
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


HIGHLIGHT_LINES = 2000  # (Feature Code's, where its script does not say: past this, the code is shown plain)


def splitter_part(QtGui, splitter, stretch):
    """A pane of a splitter (Feature Code's part): its layout, no margins, so the splitter's handle sits right
    against the frame above it (owner's images 258 and 318); stretch: its share of the height at first."""
    widget = QtGui.QWidget()
    box = QtGui.QVBoxLayout(widget)
    box.setContentsMargins(0, 0, 0, 0)
    splitter.addWidget(widget)
    splitter.setStretchFactor(splitter.indexOf(widget), stretch)
    widget.setProperty("freelabShare", stretch)  # (ak.share_splitters: the heights at first show, in these shares)
    return box


class CodePreview(object):
    """The Code preview, as Feature Code shows its code (owner's image 305): a pane of the window's splitter,
    a separator first (under the handle, before the heading: owner's images 288 and 318), the bold heading,
    then the code, read-only, colored by Feature Code's highlighter (fc: its module, or None: plain). Shared by
    CJK Spacing and CJK Vertical."""

    def __init__(self, ak, fc, splitter, what, stretch=2):
        QtCore, QtGui = _qt()
        part = splitter_part(QtGui, splitter, stretch)
        part.addWidget(ak.separator())
        self.heading = QtGui.QLabel(CODE_PREVIEW_HEADING)
        font = QtGui.QFont(self.heading.font)
        font.setBold(True)
        self.heading.setFont(font)
        self.heading.setWhatsThis(what)
        part.addWidget(self.heading)
        self.code = QtGui.QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setWhatsThis(what)
        part.addWidget(self.code, 1)
        self.text = None
        self.lines = getattr(fc, "HIGHLIGHT_LINES", HIGHLIGHT_LINES)
        try:  # its colors; without them (no Feature Code, or a PythonQt that cannot subclass the highlighter) plain
            self.highlighting = fc.make_highlighter(self.code) if fc is not None else None
        except Exception:
            self.highlighting = None

    def show(self, text):
        """The code shown, colored while it has self.lines lines at most, plain past that; left alone when it
        is the text shown already (Qt would color every line again: Feature Code's show_code). Never raises."""
        text = u"%s" % (text or u"")
        if text == self.text:
            return
        self.text = text
        highlighting = self.highlighting
        long_code = text.count(u"\n") + 1 > self.lines
        try:
            if highlighting is not None and long_code:
                highlighting.detach()  # (before the text: none of its lines is colored)
            self.code.setPlainText(text)
            if highlighting is not None and not long_code:
                highlighting.attach()  # (after it, where it was detached: colored once, not twice)
        except Exception:
            pass

    def refresh(self):
        """The colors read again from the palette (dark mode switched)."""
        if self.highlighting is not None:
            try:
                self.highlighting.refresh()
            except Exception:
                pass


def counted(number, one, many=None):
    """u"1 syllable", u"11,172 syllables": the word follows the number, grouped by thousands (ak.counted)."""
    return u"%s %s" % (format(int(number), ","), one if number == 1 else (many or one + u"s"))


def transform_values(t):
    """A shape's QTransform as six numbers (m11, m12, m21, m22, dx, dy)."""
    return tuple(float(v) for v in (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy()))


def put_back_layer(layer, shapes, saved, QtGui):
    """A syllable's layer whose write raised put back as saved ((each shape's transform values, the width)):
    each shape's transform and the width set again, read back: whether all are as they were."""
    values, width = saved
    for shape, own in zip(shapes, values):
        try:
            if any(abs(a - b) > 1e-6 for a, b in zip(transform_values(shape.transform), own)):
                shape.transform = QtGui.QTransform(*own)
        except Exception:
            pass  # (read back below)
    try:
        if abs(float(layer.advanceWidth) - width) > 1e-6:
            layer.advanceWidth = width
    except Exception:
        pass
    try:
        return (all(max(abs(a - b) for a, b in zip(transform_values(shape.transform), own)) <= 0.01
                    for shape, own in zip(shapes, values))
                and abs(float(layer.advanceWidth) - width) <= 0.5)
    except Exception:
        return False


def hangul_note(count, where, bold=lambda text: text):
    """The status line's sentence about the font's Hangul syllables (count of them; where: the setting
    to look under, as shown; bold: how the count is set off), u"" for a font without any. It follows
    the count: "1 Hangul syllable ... its width", "2 Hangul syllables ... their widths"."""
    if not count:
        return u""
    return (u" Its %s: none of the corpus's Korean fonts kerns or trims Hangul; choose how to set %s under %s." % (
        bold(counted(count, u"Hangul syllable")), u"its width" if count == 1 else u"their widths", where))


HELP = u"""<b>FreeLab CJK Spacing</b><br>
Writes palt (proportional widths) and halt (half widths) for the font's full-width kana and
punctuation, so that applications can set Japanese proportionally. Nothing is written until you
click <i>Write the code</i> (<i>Update the code</i> once FreeLab's code is in the font).<br><br>
<b>The list</b>: each full-width kana and punctuation mark, grouped, with its trim: how far its ink
moves (x placement) and how much its width changes (x advance), trimmed to its ink and the
sidebearings the open-licensed CJK fonts give theirs (about 0.07 em on each side for kana; each
punctuation mark its own: a comma keeps its left, an opening bracket its right). Ticked glyphs are
written.<br>
<b>The previews</b>: the sample text set as it is, and with palt, in the font's glyphs, in three
lines where the window's width allows (the text set smaller to fit, as small as 20 pixels to the em):
the Iroha (every kana once), a Hangul pangram, or the opening of the Thousand Character Classic in
Simplified or Traditional Chinese, each with full-width punctuation. A sample in a writing the font
has none of is grayed. Type your own sample.<br>
<b>Code preview</b>: the code the write button would write, as the ticks and options stand
(nothing is written yet).<br>
<b>Hangul</b> stays out of palt, as the corpus's Korean fonts leave it: <i>Hangul</i> sets the
syllables' widths instead (one width for all, or each by its shape), in every master; it is grayed
for a font with no Hangul syllables.<br>
Drag the space between two parts (the list, the previews, the code) to give one more room.<br>
<i>Restore suggestions</i> puts every tick back as the list first came.<br><br>
Click this help's button, then anything in the window, for what it does (or right-click it: <i>What's This?</i>)."""


class CJKSpacingDialog(object):
    COLUMNS = ("Glyph", "Name", "Width", "palt", "Width after", "halt")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab CJK Spacing")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        self.status.connect("linkActivated(QString)", self.status_link)  # (List again, once a listing was stopped)
        layout.addWidget(self.status)
        layout.addWidget(ak.header_separator())  # (always shown, as every window's: owner's images 222 and 223)
        self.log = ak.Log()
        row = QtGui.QHBoxLayout()
        self.palt_box = QtGui.QCheckBox("Proportional widths (palt)")
        self.palt_box.setChecked(True)
        self.palt_box.setWhatsThis(u"Writes palt: kana and punctuation trimmed to their ink and the corpus's sidebearings.")
        self.halt_box = QtGui.QCheckBox("Half-width punctuation (halt)")
        self.halt_box.setChecked(True)
        self.halt_box.setWhatsThis(u"Writes halt: each punctuation mark set in half the em, as the corpus's fonts set it.")
        row.addWidget(self.palt_box)
        row.addWidget(self.halt_box)
        self.hangul_label = QtGui.QLabel(u"Hangul:")  # (the shared module's caption: grayed with its dropdown)
        row.addWidget(self.hangul_label)
        self.hangul_box = QtGui.QComboBox()
        for _, label in HANGUL_MODES:
            self.hangul_box.addItem(label)
        self.hangul_box.setWhatsThis(u"How the font's Hangul syllables are set: as they are; all at one width (the font's "
                                     u"own where its syllables share one, else the corpus's 0.9 em), each one's ink "
                                     u"centered; or proportionally, each with the sidebearings the corpus's proportional "
                                     u"Korean fonts give its shape. Their outlines move and their widths change, in every "
                                     u"master. Grayed for a font with no Hangul syllables: it sets nothing else (Korean "
                                     u"punctuation is palt's and halt's, as Japanese).")
        row.addWidget(self.hangul_box)
        row.addStretch(1)
        layout.addLayout(row)
        # The list, the sample's previews, and the Code preview share the height in a splitter, as Feature Code's
        # lists and code: drag a handle to see more of one (owner's image 310: the list had none over the previews)
        self.splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter, 1)
        list_part = splitter_part(QtGui, self.splitter, 3)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.table_layout(self.tree)
        self.tree.setWhatsThis(u"Each full-width kana and punctuation mark with its trims: palt's x placement and x "
                               u"advance, the width after, and halt's. Ticked glyphs are written. Double-click one "
                               u"to see it in a <i>Glyph</i> window.")
        list_part.addWidget(self.tree, 1)  # (the last of its pane: the handle right under its frame)
        preview_part = splitter_part(QtGui, self.splitter, 2)
        sample_row = QtGui.QHBoxLayout()
        self.sample_label = QtGui.QLabel(u"Sample:")
        sample_row.addWidget(self.sample_label)
        self.sample_box = QtGui.QComboBox()
        for _, label, _ in SAMPLES:
            self.sample_box.addItem(label)
        self.sample_box.setWhatsThis(u"A sample per writing system (the one in the font's own writing is chosen as it "
                                     u"is read; one in a writing the font has none of, which would show its punctuation "
                                     u"alone, is grayed); the field beside it takes text of your own.")
        sample_row.addWidget(self.sample_box)
        self.sample = QtGui.QLineEdit(SAMPLE)
        self.sample.setWhatsThis(u"The text the previews set, as it is and with palt: the chosen sample, or text of "
                                 u"your own.")
        sample_row.addWidget(self.sample, 1)
        preview_part.addLayout(sample_row)
        self.previews, self.preview_captions = [], []
        # The captions and the line between the previews: shown only while a sample is drawn (draw_previews, the
        # review of November 23: no caption or line over nothing)
        self.preview_parts, self.previews_drawn = [], False
        for number, caption in enumerate((u"Now", u"With palt")):
            if number:
                self.preview_parts.append(ak.separator())
                preview_part.addWidget(self.preview_parts[-1])  # (between two previews stacked)
            title = ak.preview_caption(caption)  # (smaller, in the quiet text color: every tool's previews' captions)
            preview_part.addWidget(title)
            self.preview_captions.append(title)
            self.preview_parts.append(title)
            label = QtGui.QLabel()
            label.setProperty(ak.LEAVE_ALONE_PROP, True)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumHeight(int(PREVIEW_EM * 1.9))
            try:  # its picture never holds the window wider: the sample is broken into lines to fit it
                label.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Preferred)
            except Exception:
                pass
            label.setToolTip(caption)
            preview_part.addWidget(label)
            self.previews.append((label, caption))
        ak.preview_filled(self.preview_parts, False)  # (nothing drawn yet)
        # What the previews show of the sample where the font lacks some of it, as CJK Vertical's (image 360): said
        # in the log, no longer in a line under the previews (LacksNote)
        self.lacks_note = LacksNote(ak, self.log, dialog)
        preview_part.addStretch(1)  # (a taller pane: the previews stay under the sample row)
        # The Code preview, last, as Feature Code's code under its lists (owner's image 305)
        self.code_preview = CodePreview(ak, feature_code_or_none(), self.splitter, CODE_PREVIEW_WHAT)
        try:  # (the splitter's hint on its handles, as Feature Code's: not on every label inside it)
            feature_code_or_none().describe_handles(self.splitter, u"Drag the space between two parts up or down to "
                                                                   u"give one more room.")
        except Exception:
            pass
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Tick all")
        self.all_button.setWhatsThis(u"Ticks every row of the list.")
        self.none_button = QtGui.QPushButton("Untick all")
        self.none_button.setWhatsThis(u"Unticks every row of the list.")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every tick back as the list first came.")
        self.write_button = QtGui.QPushButton("Write the code")
        self.write_button.setWhatsThis(u"Writes palt and halt for the ticked glyphs, between FreeLab's marker lines (the "
                                       u"code <i>Code preview</i> shows); the rest of each feature is kept. It also sets "
                                       u"the Hangul widths chosen under <i>Hangul</i>, in every master. Named <i>Update "
                                       u"the code</i> once FreeLab's code is in the font, and <i>Set Hangul widths</i> "
                                       u"when only those change. <i>Edit &gt; Undo</i> takes it back.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.compile_box = ak.compile_box()
        # (the compile tick, then the button it is about, then Close: owner's image 298)
        for widget in self.bottom_right():
            buttons.addWidget(widget)
        ak.cancel_button(self, buttons, self.close_button, CANCEL_NOTE)  # (right before Close)
        layout.addLayout(buttons)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        self.palt_box.connect("toggled(bool)", lambda on: self.toggled())
        self.halt_box.connect("toggled(bool)", lambda on: self.toggled())
        self.sample.connect("textChanged(QString)", lambda text: self.draw_previews(typed=True))
        self.sample_box.connect("activated(int)", lambda index: self.sample_chosen(SAMPLES[index][2]))
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window(item))
        self.package = None
        self.trims, self.first_checks, self.texts, self.names = [], [], {}, []
        self.prefix, self.classes, self.lookups = None, {}, {}  # (read with the code: the font's own positions)
        self.seen_history, self.busy, self.buttons_due = None, False, False
        self.model = load_model()
        self.hangul_model = load_model(name=HANGUL_MODEL_FILE)
        self.hangul_glyphs, self.hangul, self.hangul_checks, self.hangul_width = [], [], {}, None
        self.hangul_box.connect("currentIndexChanged(int)", lambda index: self.plan_hangul())
        ak.add_tools_button(dialog, "CJK Spacing", getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.history_timer = ak.watch_history(self)
        self.flagging = ak.flag_menu(self.tree, self, self.flag_names, self.row_names)
        self.preview_width, self.watchers = None, []
        self.watch_previews()
        try:  # the check boxes drawn plain to see in either palette (the list's pictures stay unmapped), and the
            # Code preview's colors read again when dark mode switches
            fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            self.watchers.append(fc.watch_check_boxes(self.dialog, [self.tree], self.code_preview.refresh))
        except Exception:
            pass

    def bottom_right(self):
        """The bottom row's right group, in the suite's order (owner's image 298): the compile tick, the write
        button it is about, then Close."""
        return [self.compile_box, self.write_button, self.close_button]

    def watch_previews(self):
        """The previews set again when their width changes (their lines break to fit it)."""
        QtCore, QtGui = _qt()
        owner = self

        class Watcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize
                        owner.fit_previews()  # (whole meanwhile: shown_whole)
                        owner.redraw_timer.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        try:
            # (parents given: Qt deletes them with the window, never PythonQt at a random moment)
            self.redraw_timer = QtCore.QTimer(self.dialog)
            self.redraw_timer.setSingleShot(True)
            self.redraw_timer.setInterval(80)
            self.redraw_timer.connect("timeout()", self.previews_resized)
            for label, _ in self.previews:  # (each: the layout sizes one after the other, the second after the first's event)
                watcher = Watcher(label)
                label.installEventFilter(watcher)
                self.watchers.append(watcher)
        except Exception:
            pass

    def previews_resized(self):
        if self.preview_room() != self.preview_width or self.preview_tall() != getattr(self, "preview_height", None):
            self.draw_previews()

    def fit_previews(self):
        """Each preview's last picture shown whole at the previews' size now (shown_whole), while a resize waits
        for the previews to be drawn again."""
        QtCore = _qt()[0]
        for (label, caption), pixmap in zip(self.previews, getattr(self, "preview_pixmaps", [])):
            shown_whole(label, pixmap, QtCore)

    def flag_names(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return []
        return self.row_names(items[0])

    def row_names(self, item):
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return [self.trims[index].name] if 0 <= index < len(self.trims) else []

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

    def step(self, steps, label, part=0.0, stoppable=True):
        """The work at this part (0 to 1) of the step of that label, in the window's top row (ak.busy_progress:
        events let through, the user's Stop asked raises ak.Stopped where stoppable)."""
        self.ak.busy_progress(self, label, bar_share(steps, label, part), stoppable=stoppable)

    def run(self):
        """The list read again for this window's font, under the window's top-row progress (owner's image
        179: none while listing), stoppable: the list then left empty, the status line's link lists it
        again."""
        if self.busy:
            return
        self.busy = True
        # (the previews' pictures hidden while the font is read: the window repaints meanwhile, and the old
        # pictures, laid out for the list's height before it was filled, were drawn over each other and the
        # log, live)
        self.previews_shown(False)
        self.ak.busy_start(self, READ_STEP)
        try:
            self.read_font()
        except self.ak.Stopped:
            self.listing_stopped()
        finally:
            self.ak.busy_end(self)
            self.busy = False
            self.previews_shown(self.package is not None)
        self.update_buttons()

    def previews_shown(self, on):
        self.pictures_shown = bool(on)  # (draw_previews shows the captions and the line only with the pictures)
        widgets = []
        for entry in getattr(self, "previews", []):  # ((picture label, caption) pairs)
            widgets.extend(entry if isinstance(entry, (list, tuple)) else [entry])
        for widget in widgets:
            try:
                widget.setVisible(bool(on))
            except Exception:
                pass
        # (the captions and the line between: with the pictures, and only where draw_previews drew a sample)
        self.parts_filled(on and getattr(self, "previews_drawn", False))

    def parts_filled(self, filled):
        """The captions and the line between the previews shown or hidden (ak.preview_filled): shown only while
        a sample is drawn, the review of November 23. Nothing to do before they are built."""
        parts = getattr(self, "preview_parts", None)
        if parts:
            self.ak.preview_filled(parts, filled)

    def listing_stopped(self, what=u"Listing"):
        """The work stopped by the user: nothing listed (a list half read would offer half the trims), the
        status line saying so, with a link to list again; the History seen (not read again for it)."""
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.trims, self.hangul, self.first_checks = [], [], []
        self.status.setText(head_join(self.ak, font_line(self.ak, self.package), stopped_line(what)))
        self.seen_history = self.ak.history_mark(self.package)

    def status_link(self, target):
        """A link of the status line clicked: List again (a listing stopped)."""
        try:
            if u"%s" % target == LIST_AGAIN:
                self.run()
        except Exception as exc:  # (a slot must never raise)
            try:
                self.log.add(self.ak.html(exc), "error")
            except Exception:
                pass

    def read_font(self):
        QtCore, QtGui = _qt()
        ak = self.ak
        kept = dict((t.name, t.checked) for t in self.trims)
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.trims, self.hangul_glyphs, self.hangul = [], [], []  # (the last font's Hangul never grays this one's box)
        package = self.package = self.current_font()
        self.show_font_parts(package is not None)
        if package is None:
            self.status.setText(ak.no_font_line())
            self.update_buttons()
            return
        if not self.model:  # (the font line kept, the reason in the log: owner's image 224)
            self.status.setText(head_join(ak, font_line(ak, package), u"Could not list the trims: the log says why."))
            self.log.add(u"The corpus's trims (palt_model.json) are missing beside this script: reinstall FreeLab.", "error")
            return
        master = package.master
        glyphs, hangul = [], 0
        every = list(package.fgPackage.glyphs)
        for number, fg in enumerate(every):
            if number % PUMP_EVERY == 0:
                self.step(LIST_STEPS, READ_STEP, number / float(len(every)))
            codes = self.ak.glyph_codes(fg)  # (the one of its code points that is a kind: not a radical it is encoded at too)
            code = next((c for c in codes if kind_of(c)), codes[0] if codes else None)
            kind = kind_of(code) if code else None
            if kind == "hangul":
                hangul += 1
                self.hangul_glyphs.append((code, fg.name))
            if kind not in KINDS:
                continue
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() <= 0:
                continue
            glyphs.append((code, fg.name, layer.advanceWidth, box.left(), box.right()))
        self.names = [g.name for g in package.fgPackage.glyphs]
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        self.prefix = read_prefix(features)  # (its classes and lookups: palt's and halt's own code may name them)
        self.classes = font_classes(package, self.prefix)
        try:
            self.lookups = code_lookups(self.prefix) if self.prefix is not None else {}
        except Exception:
            self.lookups = {}
        self.trims = plan(glyphs, self.model, float(package.upm))
        for t in self.trims:
            t.checked = kept.get(t.name, t.checked)
        codes = set(all_codes(package.fgPackage.glyphs))
        offered = offered_samples(SAMPLES, codes)  # (a sample in a writing the font lacks grayed: owner's image 304)
        offer_samples(self.sample_box, SAMPLES, offered, QtCore)
        if u"%s" % self.sample.text in [text for _, _, text in SAMPLES]:  # (text of one's own is kept)
            index = best_sample(codes, *font_hints(package))
            index = index if offered[index] else offered.index(True)
            self.sample_box.setCurrentIndex(index)
            self.sample.setText(SAMPLES[index][2])
        self.note_font(package)
        self.hangul_shown()
        self.hangul = []
        if hangul and HANGUL_MODES[self.hangul_box.currentIndex][0] != "leave":
            self.measure_hangul(progress=lambda part: self.step(LIST_STEPS, HANGUL_STEP, part))
        self.step(LIST_STEPS, LIST_STEP)
        self.fill(lambda part: self.step(LIST_STEPS, LIST_STEP, part))
        self.first_checks = [True for _ in self.trims]
        self.update_buttons()  # (fill compared the checks with the last font's)
        b = ak.b
        full = sum(1 for g in glyphs if g[2] >= FULL_WIDTH_SHARE * package.upm)
        korean = hangul_note(hangul, ak.i(u"Hangul"), b)  # (the control's name, without its caption's colon)
        self.status.setText(head_join(ak, font_line(ak, package, master), trims_status(
            len(self.trims), full, sum(1 for t in self.trims if t.palt), sum(1 for t in self.trims if t.halt),
            self.write_button.text, korean, b, ak.i)))
        self.seen_history = ak.history_mark(package)
        self.cjk = has_cjk(codes)
        self.cjk_states(self.cjk)
        self.step(LIST_STEPS, PREVIEW_STEP)
        self.draw_previews()

    def cjk_states(self, cjk):
        """The ticks and the sample grayed for a font with no kana, Hangul, or CJK punctuation: nothing they act
        on or show (owner's images 379 and 380; a Latin font's comma and period were offered the Korean sample,
        image 359)."""
        for name in ("palt_box", "halt_box", "sample_box", "sample"):
            widget = getattr(self, name, None)
            if widget is None:
                continue
            try:
                self.ak.enable(widget, cjk)
            except Exception:
                pass

    # -- Hangul -----------------------------------------------------------------------

    def hangul_mode(self):
        return HANGUL_MODES[self.hangul_box.currentIndex][0]

    def hangul_shown(self):
        """Hangul: clickable only for a font with Hangul syllables (its caption grayed with it, the shared
        module's caption_states), and set back to leaving them where there are none: it sets nothing else.
        Owner's image 304: clickable over a Japanese font with none, the read had grayed it, then the shared
        no_font_states gave it back with the font (its update_buttons, called then, did not set it)."""
        box = getattr(self, "hangul_box", None)
        if box is None:
            return
        has = bool(getattr(self, "package", None) is not None and getattr(self, "hangul_glyphs", None))
        if not has and box.currentIndex != 0:
            box.blockSignals(True)
            box.setCurrentIndex(0)  # (leave as they are)
            box.blockSignals(False)
        self.ak.enable(box, has)

    def measure_hangul(self, master=None, progress=None):
        """The changes the chosen Hangul mode makes to the master's syllables (and the width it sets).
        progress(part), where given, every PUMP_EVERY syllables (the top row's: it may raise ak.Stopped)."""
        package = self.package
        master = master or package.master
        mode = self.hangul_mode()
        upm = float(package.upm)
        measured = []
        for count, (code, name) in enumerate(self.hangul_glyphs):
            if progress is not None and count % PUMP_EVERY == 0:
                progress(count / float(len(self.hangul_glyphs)))
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() > 0:
                measured.append((code, name, layer.advanceWidth, box.left(), box.right()))
        widths = sorted(set(int(round(m[2])) for m in measured))
        width = None
        if mode == "fixed":
            width = widths[len(widths) // 2] if 0 < len(widths) <= 3 else (self.hangul_model.get("fixed_width") or 0.9) * upm
        self.hangul_width = width
        changes = [hangul_change(code, name, advance, left, right, mode, self.hangul_model, upm, width)
                   for code, name, advance, left, right in measured]
        changes = [c for c in changes if c is not None]
        if master == package.master:
            self.hangul = changes
        return changes

    def plan_hangul(self):
        """The Hangul setting changed: the syllables measured for it (a Korean font's 11,172 take a while: under
        the window's top-row progress, stoppable, the setting then put back to leaving them)."""
        if self.package is None or self.busy:
            return
        self.hangul = []
        if self.hangul_glyphs and self.hangul_mode() != "leave":
            self.busy = True
            self.ak.busy_start(self, HANGUL_STEP)
            try:
                self.measure_hangul(progress=lambda part: self.ak.busy_progress(self, None, part))
            except self.ak.Stopped:
                self.hangul = []
                self.hangul_box.blockSignals(True)
                self.hangul_box.setCurrentIndex(0)  # (leave as they are: what the list shows)
                self.hangul_box.blockSignals(False)
                self.log.add(u"Measuring Hangul was stopped: the syllables are left as they are.", "warning")
            finally:
                self.ak.busy_end(self)
                self.busy = False
            if self.hangul_mode() == "leave":
                self.fill()
                self.draw_previews()
                return
            self.log.add(u"Hangul, %s: %s would change%s." % (
                self.ak.html(HANGUL_MODES[self.hangul_box.currentIndex][1].lower()),
                self.ak.b(counted(len(self.hangul), u"syllable")),
                u" (one width: %s)" % self.ak.b(counted(self.hangul_width, u"unit")) if self.hangul_width else u""))
        self.fill()
        self.draw_previews()

    def toggled(self):
        """palt or halt switched: the list shows what is written now (counts, columns), the previews too."""
        try:
            self.harvest()
            self.fill()
            self.draw_previews()
        except Exception as exc:
            self.log.add(u"Could not show the change: %s" % self.ak.html(exc), "error")
        self.update_buttons()

    def fill(self, progress=None):
        """The list made from the trims (and the Hangul rows); progress(part), where given, every PUMP_EVERY
        rows (each draws its glyph: the top row's progress, it may raise ak.Stopped)."""
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        try:
            self.fill_rows(QtCore, QtGui, progress)
        finally:
            self.tree.blockSignals(False)
        self.update_buttons()

    def fill_rows(self, QtCore, QtGui, progress):
        self.tree.clear()
        listed = 0
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        palt_on, halt_on = self.palt_box.checked, self.halt_box.checked
        try:
            dimmed = QtGui.QBrush(self.dialog.palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text))
        except Exception:
            dimmed = None
        for kind in KINDS:
            members = [(index, t) for index, t in enumerate(self.trims) if t.kind == kind]
            if not members:
                continue
            written = sum(1 for _, t in members if (t.palt and palt_on) or (t.halt and halt_on))
            off = [tag for tag, on in ((u"palt", palt_on), (u"halt", halt_on)) if not on]
            heading = u"%s (%d)" % (KIND_LABELS[kind], len(members)) if not off else u"%s (%d of %d trimmed: %s off)" % (
                KIND_LABELS[kind], written, len(members), u" and ".join(off))
            top = QtGui.QTreeWidgetItem([heading])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for index, t in members:
                if progress is not None and listed % PUMP_EVERY == 0:
                    progress(listed / float(len(self.trims)))
                listed += 1
                item = QtGui.QTreeWidgetItem([t.char, t.name, u"%d" % t.advance,
                                              u"%+d, %+d" % t.palt if t.palt else u"\N{EN DASH}",
                                              u"%d" % t.width_after(),
                                              u"%+d, %+d" % t.halt if t.halt else u"\N{EN DASH}"])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if t.checked else QtCore.Qt.Unchecked)
                item.setToolTip(3, u"x placement, x advance: the ink moves by the first, the width changes by the second.")
                for column in range(2, len(self.COLUMNS)):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                if dimmed is not None:  # what is not written, as off
                    for column in ((3, 4) if not palt_on else ()) + ((5,) if not halt_on else ()):
                        item.setForeground(column, dimmed)
                icon = self.picture([(t.name, 0, 0)], ICON_SIZE)
                if icon is not None:
                    item.setIcon(0, self.ak.icon_of(icon))
                top.addChild(item)
            top.setExpanded(True)
        if self.hangul:
            top = QtGui.QTreeWidgetItem([u"Hangul (%s)" % counted(len(self.hangul), u"syllable")])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for number, (shape, label) in enumerate(HANGUL_SHAPES):
                members = [c for c in self.hangul if c.shape == shape]
                if not members:
                    continue
                middle = lambda values: sorted(values)[len(values) // 2]
                item = QtGui.QTreeWidgetItem([label, counted(len(members), u"syllable"),
                                              u"%d" % middle([c.old_advance for c in members]),
                                              u"moved %+d" % middle([c.shift for c in members]),
                                              u"%d" % middle([c.advance for c in members]), u""])
                item.setData(0, QtCore.Qt.UserRole, -10 - number)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if self.hangul_checks.get(shape, True) else QtCore.Qt.Unchecked)
                item.setToolTip(3, u"The median move of their outlines, and (next) their median width after.")
                for column in range(2, len(self.COLUMNS)):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                top.addChild(item)
            top.setExpanded(True)
        for column in range(len(self.COLUMNS)):
            self.tree.resizeColumnToContents(column)

    def items(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.trims):
                self.trims[index].checked = item.checkState(0) == QtCore.Qt.Checked
            elif index <= -10:
                self.hangul_checks[HANGUL_SHAPES[-10 - index][0]] = item.checkState(0) == QtCore.Qt.Checked

    def hangul_chosen(self):
        return [c for c in self.hangul if self.hangul_checks.get(c.shape, True)]

    def check_all(self, on):
        """Tick all, Untick all: every row, the log told how many it ticked or unticked, and how many
        of them were in closed groups (owner's report 118)."""
        self.tree.blockSignals(True)
        try:
            self.ak.check_rows(self.items(), on, log=self.log, command=u"Tick all" if on else u"Untick all",
                               noun=u"glyph", hidden_text=(u"in a closed group", u"in closed groups"))
        finally:
            self.tree.blockSignals(False)
        self.changed()

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
        checks = [t.checked for t in self.trims]
        ak.enable(self.all_button, not all(checks) if checks else False)
        ak.enable(self.none_button, any(checks))
        ak.enable(self.restore_button, checks != self.first_checks)
        new = texts_for(self.trims, self.texts, self.palt_box.checked, self.halt_box.checked, None, self.classes,
                        self.lookups) if self.package else {}
        present = any((BEGIN % tag) in (self.texts.get(tag) or u"") for tag in ("palt", "halt"))
        changes = any(new[tag] != self.texts.get(tag) for tag in new)
        widths = bool(self.hangul_chosen())
        what = (u"Update the code" if present else u"Write the code") if changes else u""
        self.write_button.setText(u"%s and Hangul widths" % what if what and widths else what or
                                  (u"Set Hangul widths" if widths else u"Write the code"))
        problem = feature_code_problem(u"CJK Spacing")
        writable = bool((changes or widths) and not problem)
        ak.enable(self.write_button, writable)
        # Compile after writing, grayed with the button (owner's image 195: checked and clickable beside a
        # grayed Write the code), and while only Hangul widths would be set: no code to compile
        ak.enable(self.compile_box, compile_on(writable, changes))
        if problem and problem != getattr(self, "problem_said", None):
            self.log.add(self.ak.html(problem), "error")  # (once, while it lasts)
        self.problem_said = problem
        self.hangul_shown()  # (the shared no_font_states calls this once it gives the controls back)
        # (and the ticks and the sample grayed again for a font with no CJK: no_font_states gave them back after
        # the read had grayed them, live 2026-11-19 over Bellefair)
        self.cjk_states(self.package is not None and getattr(self, "cjk", True))
        self.show_code(new, widths)
        self.draw_previews()

    def show_code(self, new, widths=False):
        """The Code preview: the code a write would write now (preview_code), the Hangul widths it sets besides
        said under it; empty with no font."""
        preview = getattr(self, "code_preview", None)
        if preview is None:
            return
        if self.package is None:
            preview.show(u"")
            return
        chosen = self.hangul_chosen() if widths else []
        also = [u"And the widths of %s, set on their glyphs in every master (no code)." % counted(
            len(chosen), u"Hangul syllable")] if chosen else []
        preview.show(preview_code(new, self.texts, ("palt", "halt"), also,
                                  empty=not self.trims and not self.hangul_glyphs))

    def restore(self):
        for t, on in zip(self.trims, self.first_checks):
            t.checked = on
        self.fill()
        self.log.add(u"Ticks restored as suggested.")

    def history_moved(self):
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick):
        read anew, or the list emptied and the no-font line shown."""
        self.run()

    def show_font_parts(self, on):
        """With no font open, what has nothing to act on is hidden (the sample and its previews) or
        grayed out (the features to write, the Hangul setting, compiling)."""
        for widget in [self.sample_label, self.sample_box, self.sample]:
            widget.setVisible(on)
        self.previews_shown(on and not getattr(self, "busy", False))  # (shown once the read is over: run)
        for widget in (self.palt_box, self.halt_box):
            self.ak.enable(widget, on)
        if not on:  # (with a font, update_buttons sets it with the button: compile_on)
            self.ak.enable(self.compile_box, False)
        if not on:
            self.ak.enable(self.hangul_box, False)  # (a font's Hangul sets it again as it is read)

    # -- pictures ------------------------------------------------------------------

    def layer_of(self, name):
        glyph = self.package.findName(name)
        return glyph.getLayerByName(self.package.master) if glyph is not None and not glyph.isNull else None

    def picture(self, placed, size, rows=None):
        """Glyphs [(name, x placement, x advance change)] set in a row (or rows: lists of them, one line
        each, under one another), in the dialog's text color."""
        QtCore, QtGui = _qt()
        lines = []
        for row in (rows if rows is not None else [placed]):
            layers = []
            for item in row:
                layer = self.layer_of(item[0])
                if layer is not None:
                    layers.append((layer, item[1], item[2]))
            lines.append(layers)
        if not any(lines):
            return None
        upm = float(self.package.upm)
        scale = size / upm
        total = max(sum(layer.advanceWidth + advance for layer, _, advance in layers) for layers in lines)
        step = size * LINE_STEP
        pixmap = QtGui.QPixmap(max(int(total * scale) + 8, 4), int(step * len(lines)))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        colored = False
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            for number, layers in enumerate(lines):
                x = 4.0
                for layer, placement, advance in layers:
                    painter.save()
                    painter.translate(x + placement * scale, size * 1.0 + step * number)
                    painter.scale(scale, -scale)
                    parts = self.ak.layer_parts(layer)
                    colored = colored or bool(parts)
                    self.ak.fill_glyph(painter, self.ak.layer_path(layer), QtGui.QBrush(color), parts)
                    painter.restore()
                    x += (layer.advanceWidth + advance) * scale
        finally:
            painter.end()
        # (in one color: redrawn in the new one when dark mode switches; a color font's glyphs keep theirs)
        return pixmap if colored else self.ak.inked(pixmap, color)

    def note_font(self, package):
        """Said once per font and sample: a color font's glyphs, and a sample that shows none of the
        font's CJK characters (its preview stays empty)."""
        key = (self.ak.font_key(package), u"%s" % self.sample.text)
        if key == getattr(self, "noted_font", None):
            return
        first = getattr(self, "noted_font", (None,))[0] != key[0]
        self.noted_font = key
        note = self.ak.color_note(package) if first else u""
        if note:
            self.log.add(note)
        codes = set(all_codes(package.fgPackage.glyphs))
        missed = sample_misses(codes, u"%s" % self.sample.text)
        if missed:
            shown = u" ".join(missed[:12]) + (u" …" if len(missed) > 12 else u"")
            self.log.add(u"The sample shows none of the font's %s (%s): type text of your own with them in the "
                         u"%s field to see them set." % (
                             self.ak.b(counted_chars(len(missed))), self.ak.html(shown), self.ak.i(u"Sample")),
                         "warning")

    def preview_tall(self):
        """The first preview's height in pixels (None where Qt does not say, or before it is laid out)."""
        try:
            height = int(self.ak._property(self.previews[0][0], "height"))
            return height if height > PREVIEW_LEAST_HEIGHT // 2 else None
        except Exception:
            return None

    def preview_room(self):
        """The previews' width in pixels, for their lines (None where Qt does not say)."""
        try:
            width = int(self.ak._property(self.previews[0][0], "width"))
            return width - 12 if width > 2 * PREVIEW_EM else None
        except Exception:
            return None

    def sample_chosen(self, text):
        """A sample chosen in Sample: set in the field (its textChanged draws the previews), and what the font
        lacks of it said in the log at once: a choice, not typing (LacksNote)."""
        self.sample.setText(text)
        lacks = getattr(self, "lacks_note", None)
        if lacks is not None:
            lacks.now()

    def draw_previews(self, typed=False):
        """The previews set again, and what the font lacks of the sample said in the log (LacksNote); typed:
        the sample was typed into (its textChanged), the log's note waiting for a pause in the typing."""
        lacks = getattr(self, "lacks_note", None)
        if self.package is None:
            self.previews_drawn = False  # (no font: nothing drawn, no caption or line over nothing)
            self.parts_filled(False)
            if lacks is not None:
                lacks.show(None, u"")  # (a font read next says its note again)
            return
        by_code = dict((t.code, t) for t in self.trims if t.checked and t.palt)
        by_code.update((c.code, c) for c in self.hangul_chosen())
        names = all_codes(self.package.fgPackage.glyphs)
        text = u"%s" % self.sample.text
        room = self.preview_width = self.preview_room()
        upm = float(self.package.upm) or 1000.0
        advances = {}
        palt_on = self.palt_box.checked
        try:
            self.preview_captions[1].setText(u"With palt" if palt_on else u"With palt (off: palt is not written)")
        except Exception:
            pass
        sets = []  # (each preview's glyphs placed, its characters, and each one's width in ems)
        for index in range(len(self.previews)):
            placed, chars, ems = [], [], []
            for ch in text:
                name = names.get(ord(ch))
                if name is None:
                    continue
                trim = by_code.get(ord(ch)) if index == 1 else None
                if trim is not None and not palt_on and not isinstance(trim, HangulChange):
                    trim = None  # (palt not written; Hangul widths are)
                if isinstance(trim, HangulChange):
                    placed.append((name, trim.shift, trim.advance - trim.old_advance))
                else:
                    placed.append((name, trim.palt[0], trim.palt[1]) if trim else (name, 0, 0))
                if name not in advances:
                    layer = self.layer_of(name)
                    advances[name] = layer.advanceWidth if layer is not None else 0
                chars.append(ch)
                ems.append((advances[name] + placed[-1][2]) / upm)
            sets.append((placed, chars, ems))
        # One em for both, the largest that sets the sample as it is now (the wider) in three lines of the
        # previews' width (owner's image 303), so the two compare glyph for glyph
        em = preview_em(sets[0][1], sets[0][2], room) if sets else PREVIEW_EM
        tall = self.preview_height = self.preview_tall()
        em = fitted_em(em, tall)  # (and no taller than the previews' part: a list above it showed one row, live)
        self.preview_size = em
        self.preview_pixmaps = []  # (as drawn: fit_previews shows them whole while a resize waits)
        for (label, caption), (placed, chars, ems) in zip(self.previews, sets):
            widths = [width * em for width in ems]
            rows = [placed[start:end] for start, end in break_lines(chars, widths, room)] if room else None
            pixmap = self.picture(placed, em, rows) if placed else None
            self.preview_pixmaps.append(pixmap)
            if pixmap is None:
                label.clear()
            else:
                label.setPixmap(pixmap)
                try:  # its lines sized to its height (fitted_em): it may be made as short as the smallest text needs
                    label.setMinimumHeight(PREVIEW_LEAST_HEIGHT)
                except Exception:
                    pass
        # (the captions and the line between only over a sample drawn: an empty sample, or one the font has none
        # of, draws nothing; while the font is read, the pictures are hidden, and run shows them with these)
        self.previews_drawn = any(pixmap is not None for pixmap in self.preview_pixmaps)
        self.parts_filled(self.previews_drawn and getattr(self, "pictures_shown", True))
        if lacks is not None:  # (counts bold with their nouns: owner's images 297 and 301)
            lacks.show(self.package, preview_note(text, names, self.ak.b, self.ak.html), typed)

    def show_in_glyph_window(self, item):
        QtCore, QtGui = _qt()
        index = int(item.data(0, QtCore.Qt.UserRole))
        if not 0 <= index < len(self.trims):
            return
        name = self.trims[index].name
        error = self.ak.show_in_glyph_window(self.fontlab, u"/%s/%s/%s" % (name, name, name))
        if error:
            self.log.add(self.ak.error_sentence(u"FontLab did not open the glyph", error), "error")

    # -- writing --------------------------------------------------------------------

    def write(self):
        if self.package is None:
            return
        problem = feature_code_problem(u"CJK Spacing")
        if problem:  # (nothing written: no reader)
            self.log.add(self.ak.html(problem), "error")
            return
        self.harvest()
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed since the list was read: it is listed again. Nothing was written.", "warning")
            return
        features = package.fgPackage.features
        kept, refused = {}, []
        new = texts_for(self.trims, self.texts, self.palt_box.checked, self.halt_box.checked, kept, self.classes,
                        self.lookups, refused)
        if refused:
            self.log.add(refused_words(refused), "warning")  # (rich: its tags are this tool's own, palt and halt)
        for tag, names in sorted(kept.items()):
            if names:
                self.log.add(u"%s %s positioned by the font's own %s code already: %s, not FreeLab's trim "
                             u"(two values for one glyph do not compile): %s." % (
                                 self.ak.b(counted(len(names), u"glyph")), u"is" if len(names) == 1 else u"are", tag,
                                 u"it keeps its value" if len(names) == 1 else u"they keep theirs",
                                 kept_names(names, self.ak.glyph_name_link)),
                             "warning")
        fc = None
        try:
            fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
        except Exception:
            pass
        problems = []
        for tag, text in new.items():
            block = block_of(tag, text)
            problem = fc.check_code(block, self.names) if (fc is not None and block) else None
            if problem:
                problems.append(u"%s: %s" % (tag, problem))
        if problems:
            self.log.add(u"The code has problems, so nothing was written: %s" % self.ak.html(u"; ".join(problems)), "error")
            return
        # Under the window's top-row progress (owner's image 183: several seconds with none), never stoppable:
        # one step of FontLab's History, never half written (a click on Close, a tool, or an arrow is done
        # once it is over). Begun before the code is checked: busy_start lets events through once
        self.busy = True
        self.ak.busy_start(self, CODE_STEP, stoppable=False)
        outcome = None
        try:
            outcome = self.write_parts(package, features, new)
        finally:
            asked_to_stop = self.ak.busy_stopping(self)  # (Esc, Close, a tool, an arrow, during the write)
            self.ak.busy_end(self)
            self.busy = False
        if outcome is None:
            return  # (nothing written: said in the log)
        if outcome == "changed":
            if asked_to_stop:  # (what was clicked is done now: the list is not read again under it)
                self.listing_stopped(u"Reading the font again")
                self.update_buttons()
            else:
                self.run()
            self.log.add(u"The feature code (%s) changed since the list was read: here is the list again, to check "
                         u"before writing. Nothing was written." % self.ak.html(self.ak.joined(self.changed_parts)),
                         "warning")
            return
        written, syllables, status, error, compiled = outcome
        undo = getattr(status, "recorded", True)  # (Undo promised only when FontLab's History recorded the write)
        if asked_to_stop:  # (what was clicked is done now: the list is not read again under it)
            self.listing_stopped(u"Reading the font again")
            self.update_buttons()
        else:
            self.run()
        if written:
            them = u"it" if len(written) == 1 else u"them"
            self.log.add(u"Wrote %s%s.%s" % (
                self.ak.b(u" and ".join(written)), u"; <i>Edit &gt; Undo</i> takes %s back" % them if undo else u"",
                compiled), "done")
        failed = getattr(self, "hangul_failed", None)
        if syllables:
            self.log.add(u"Set %s %s; the font's kerning of Hangul, if any, was set for the old widths.%s" % (
                self.ak.b(counted(syllables, u"syllable width", u"syllable widths")),
                u"in every master" if error is None else u"before it stopped (the others are as they were)",
                u" <i>Edit &gt; Undo</i> takes it back." if undo else u""), "done")
        if not written and not syllables and not (failed is not None and not failed[2]):
            self.log.add(u"Wrote nothing.")
        if not getattr(status, "ok", True):
            self.log.add(status.message(), "error")
        if error is not None:
            self.log.add(self.ak.error_sentence(u"Stopped by an error", error), "error")
        if failed is not None:
            name, master, back = failed
            link = self.ak.glyph_name_link(name)
            if back:
                self.log.add(u"The syllable being set when it stopped was put back as it was: %s (master %s)." % (
                    link, self.ak.html(master)), "info")
            else:
                self.log.add(u"The syllable being set when it stopped could not be put back, and stays as FontLab left "
                             u"it: %s (master %s).%s" % (link, self.ak.html(master),
                                                         u" <i>Edit &gt; Undo</i> takes it back." if undo else u""),
                             "warning")

    def write_parts(self, package, features, new):
        """The write itself, under the top row's progress (write): None when nothing was written (said in
        the log), "changed" when the font's code changed since the list was read (self.changed_parts: what),
        else (features written, syllables set, notify_changed's status, an error or None, the compile's
        note)."""
        # The code written is composed from the code read with the list: an edit made since (before the
        # History watcher saw it, or one that leaves the History where it was) would be replaced. Checked
        # last, with nothing between it and the write that lets events through (no progress until the code
        # is written)
        # (the prefix and the font's classes too: the font's own positions were read through them)
        changed = changed_features(features, self.texts, ("palt", "halt"), self.prefix)
        if u"prefix" not in changed and font_classes(package, self.prefix) != self.classes:
            changed.append(u"classes")
        if changed:
            self.changed_parts = changed
            return "changed"
        refusal = getattr(self.ak, "feature_code_refusal", lambda *a, **k: None)(
            package, dict((tag, new[tag]) for tag in ("palt", "halt") if tag in new and new[tag] != self.texts.get(tag)))
        if refusal:  # (Feature Check: the code would bring an error the font's code does not have)
            self.log.add(u"Nothing was written: %s. %s lists every finding." % (  # (a link: owner's image 220)
                self.ak.html(refusal), self.ak.tool_link(u"Feature Check")), "error")
            return None
        written, error, syllables = [], None, 0
        self.hangul_written, self.hangul_failed = 0, None  # (write_hangul's, kept as it goes)
        shapes = set(c.shape for c in self.hangul_chosen())
        try:
            self.ak.before_changes(self.fontlab, package, u"FreeLab CJK Spacing")
        except getattr(self.ak, "HistoryError", ()) as exc:  # (nothing written: Undo could not take it back)
            self.log.add(u"%s" % (exc,), "error")
            return None
        try:
            for tag in ("palt", "halt"):
                if tag in new and new[tag] != self.texts.get(tag):
                    features.set_feature(tag, new[tag])
                    written.append(tag)
            if shapes:
                self.step(WRITE_STEPS, WIDTHS_STEP, 0.0, False)
                syllables = self.write_hangul(package, shapes,
                                              lambda part: self.step(WRITE_STEPS, WIDTHS_STEP, part, False))
        except Exception as exc:
            error = exc
            syllables = self.hangul_written  # (those set before the error: said, not lost)
        self.step(WRITE_STEPS, UPDATE_STEP, 0.0, False)
        status = self.ak.notify_changed(self.fontlab, package, u"FreeLab CJK Spacing")
        compiled = u""
        if written:
            self.step(WRITE_STEPS, COMPILE_STEP, 0.0, False)
            compiled = self.ak.compiled_note(self.compile_box, self.log)
        return written, syllables, status, error, compiled

    def write_hangul(self, package, shapes, progress=None):
        """Each chosen syllable set anew in every master (each measured on its own): its shapes moved
        (components and outlines alike, by their transforms) and its width changed. How many changed.
        progress(part), where given, as the masters are measured and set (the write's: never stops).

        A shape's move or the width that raised left the layer half set and the count lost: the log could say
        "Wrote nothing" over the syllables already set (rest review 2, finding 3). So the count is kept as it
        goes (self.hangul_written, read by the caller when this raises), each layer's shapes and width are saved
        before it is set, and a layer whose write raised is put back, read back, and named (self.hangul_failed:
        (glyph name, master, whether it was put back))."""
        QtCore, QtGui = _qt()
        self.hangul_written, self.hangul_failed = 0, None
        masters = list(package.masters) or [package.master]
        for number, master in enumerate(masters):
            share = lambda part: progress((number + part) / float(len(masters))) if progress is not None else None
            changes = self.measure_hangul(master, lambda part: share(part * 0.5))
            for count, change in enumerate(changes):
                if count % PUMP_EVERY == 0:
                    share(0.5 + 0.5 * count / float(len(changes)))
                if change.shape not in shapes:
                    continue
                glyph = package.findName(change.name)
                layer = glyph.getLayerByName(master) if glyph is not None else None
                if layer is None:
                    continue
                own = list(layer.shapes)
                saved = [transform_values(shape.transform) for shape in own], float(layer.advanceWidth)
                try:
                    for shape in own:
                        t = shape.transform
                        shape.transform = QtGui.QTransform(t.m11(), t.m12(), t.m21(), t.m22(), t.dx() + change.shift,
                                                           t.dy())
                    layer.advanceWidth = change.advance
                except Exception:
                    self.hangul_failed = (change.name, master, put_back_layer(layer, own, saved, QtGui))
                    try:
                        glyph.update()
                    except Exception:
                        pass
                    raise
                try:
                    glyph.update()
                except Exception:
                    pass
                self.hangul_written += 1
        return self.hangul_written

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("CJK Spacing"):
            return
    except Exception:
        pass
    try:
        dialog = CJKSpacingDialog()
    except Exception as exc:
        print("FreeLab CJK Spacing: %s" % exc)
        return
    sys._freelab_cjk_spacing = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("CJK Spacing", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_cjk_spacing":
    main()
