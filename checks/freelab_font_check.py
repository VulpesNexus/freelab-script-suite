#FLM: Font Check
# -*- coding: utf-8 -*-
"""FreeLab Font Check, from FontLab's Scripts menu.

Three views of the current font; nothing in the font changes until a button that writes is clicked
(Write suggested values, Fix), each write one step of FontLab's History:

- Coverage: the scripts the font has, each with a bar of its languages covered, within reach (the
  few characters missing named), and missed, from Hyperglot's orthographies
  (checks/language_coverage.json, Apache License 2.0); the characters to add, ranked by the languages
  each completes, with a live count of the languages a checked set completes; the languages, found by
  name. A letter the font lacks as one character counts when the font has its letter and marks and
  its anchors put them together (composed). Missing letters that Diacritics can build are handed to it.
- Vertical metrics: a diagram of the font's tallest and deepest glyphs on its line metrics (typo,
  hhea, win), the ink Windows clips in red; the values now and as Google Fonts' vertical metrics
  guidance suggests; its checks, passed or not; the glyphs Windows clips (beyond winAscent and
  winDescent, in any master, and by how much). Write suggested values sets the font info's typo,
  hhea, and win values and Use Typo Metrics (never the masters' own metrics).
- Masters: what keeps masters from interpolating, glyph by glyph: contours, nodes and their types,
  start points, directions, components and their order, anchors, and glyphs some masters lack; the
  glyph drawn in two masters, the contour at fault highlighted. Fix sets right what needs no
  designer (the contours' order, directions, start points, the components' order) in the masters
  other than the reference.

Valid Python 2.7 (FontLab 7) and Python 3. The checks above the Qt line need no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys
import unicodedata

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
DIACRITICS_FILE, DIACRITICS_MODULE = "freelab_diacritics.py", "freelab_diacritics"
LANGUAGES_FILE = "language_coverage.json"  # beside this script: checks/train/languages.py makes it from Hyperglot
LIST_FONT_FILE = "FreeLabLanguages.ttf"  # beside this script, or in language_font/: checks/train/language_font.py makes it
LIST_FONT_FOLDER = "language_font"
LIST_FAMILY = "FreeLab Languages"  # its family: Noto subsets (OFL) of every character the languages list shows
LIST_SCALE = 1.25  # the languages list's text, this many times the dialog's (easier to read)
TABS = ("coverage", "metrics", "masters")
NEARLY_MISSING = 3  # a language missing at most this many base characters (and marks) is within reach
SCRIPT_MINIMUM = 5  # a font with fewer of a script's characters than this has none of it (its languages summed up)
LINE_SHARE = 1.2  # Google Fonts: typo (and hhea) ascender plus descender at 120% of the em, suggested to start with
LINE_RANGE = (1.2, 1.3)  # ... and between 120% and 130% for Latin, Greek, and Cyrillic fonts
CENTER_TOLERANCE_SHARE = 0.02  # capitals count as centered in the line within this share of the em
WIN_SLACK_SHARE = 0.05  # winAscent or winDescent this share of the em past the ink is looser than needed
BEYOND_SHOWN = 40  # glyphs listed as reaching past the line's ascender or descender, the farthest first
CAPPED_SCRIPTS = ("Latin", "Greek", "Cyrillic")
START_MIN_SPREAD = 0.01  # a contour's start point is compared once its nodes are this far from the reference's (normalized)
START_GAIN = 0.25  # ... and counts as moved when another start fits at most this share of that distance
DIRECTION_SHARE = 0.05  # a contour's area at least this share of its box's has a plain direction
PROGRESS_EVERY = 200  # glyphs between two looks at the event loop


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the dialogs' shared
    helpers come from it."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "FontKerning") and getattr(held, "_freelab_stamp", None) == stamp:
        return held  # (loaded again after a reinstall)
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(AUTO_KERNING_MODULE)
            module.__file__ = path
            sys.modules[AUTO_KERNING_MODULE] = module
            with open(path, "rb") as handle:  # open() takes a unicode path through the wide Windows API
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


def sentence(text):
    """A tooltip's or a check's text with a period at the end of each line that lacks one."""
    lines = []
    for line in (text or u"").split(u"\n"):
        stripped = line.rstrip()
        if stripped and stripped[-1] not in u".!?:\N{HORIZONTAL ELLIPSIS}":
            stripped += u"."
        lines.append(stripped)
    return u"\n".join(lines)


def counted(number, one, many=None):
    """"1 glyph", "2 glyphs": a count with its noun in the right number."""
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


def round_units(value):
    return int(math.floor(value + 0.5))


def char_of(code):
    """A code point's character (two UTF-16 units past U+FFFF on a narrow Python 2, FontLab 7's)."""
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return (b"\\U%08x" % code).decode("unicode-escape")


def code_points(text):
    """The code points of a text, a pair of UTF-16 surrogates read as one (a narrow Python 2)."""
    found, at = [], 0
    while at < len(text):
        code = ord(text[at])
        if 0xD800 <= code < 0xDC00 and at + 1 < len(text) and 0xDC00 <= ord(text[at + 1]) < 0xE000:
            found.append(0x10000 + ((code - 0xD800) << 10) + ord(text[at + 1]) - 0xDC00)
            at += 2
        else:
            found.append(code)
            at += 1
    return found


def is_mark(code):
    try:
        return unicodedata.category(char_of(code)).startswith(u"M")
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Coverage: the languages a font's characters cover
# ---------------------------------------------------------------------------

class Language(object):
    """One orthography of a language (Hyperglot's): base characters (required), auxiliary ones (loan
    words, names), and the marks it needs on their own. Characters are texts: one character, or a
    letter and combining marks Unicode has no single character for."""

    def __init__(self, iso, name, autonym, script, status, validity, speakers, base, auxiliary, marks):
        self.iso, self.name, self.autonym, self.script = iso, name, autonym, script
        self.status, self.validity, self.speakers = status, validity, speakers
        self.base, self.auxiliary, self.marks = base, auxiliary, marks

    def label(self):
        if self.autonym and self.autonym != self.name:
            return u"%s (%s)" % (self.name, self.autonym)
        return self.name


_LANGUAGES = {}


def languages_path():
    return os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), LANGUAGES_FILE)


def list_font_path(here=None):
    """The bundled languages list font: beside this script once installed (the installer copies files
    flat), else in language_font/ (the repository); None when neither has it."""
    if here is None:
        here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    for path in (os.path.join(here, LIST_FONT_FILE), os.path.join(here, LIST_FONT_FOLDER, LIST_FONT_FILE)):
        if os.path.isfile(path):
            return path
    return None


def scaled_size(point_size, pixel_size, scale=LIST_SCALE):
    """("point", size) or ("pixel", size): a font's size times scale, in the unit it was given in (a
    QFont has a point size, or -1 and a pixel size)."""
    if point_size is not None and point_size > 0:
        return "point", round(point_size * scale * 4) / 4.0  # (quarter points)
    if pixel_size is not None and pixel_size > 0:
        return "pixel", int(round(pixel_size * scale))
    return None, None


def load_languages(path=None):
    """The orthographies of language_coverage.json, as Languages (read once per file version)."""
    import json
    path = path or languages_path()
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = _LANGUAGES.get(path)
    if held is not None and held[0] == stamp:
        return held[1]
    with open(path, "rb") as handle:
        data = json.loads(handle.read().decode("utf-8"))
    texts = data["texts"]
    statuses = data.get("status", {})
    found = []
    # An orthography without an autonym of its own takes another one's of the same language (Japanese in
    # hiragana: its kanji one, 日本語), one of the same script family first: Hyperglot gives some only once.
    families = {u"Hiragana": u"japanese", u"Katakana": u"japanese", u"Kanji": u"japanese"}
    named = {}
    for iso, name, autonym, script, _, _, _, _, _, _ in data["orthographies"]:
        if autonym:
            named.setdefault((iso, families.get(script, script)), autonym)
            named.setdefault((iso, None), autonym)
    for iso, name, autonym, script, status, validity, speakers, base, auxiliary, marks in data["orthographies"]:
        if not autonym:
            autonym = named.get((iso, families.get(script, script))) or named.get((iso, None)) or u""
        found.append(Language(iso, name, autonym, script, statuses.get(status, status), validity, speakers,
                              texts[base].split(u" ") if texts[base] else [],
                              texts[auxiliary].split(u" ") if texts[auxiliary] else [], marks))
    _LANGUAGES[path] = (stamp, found)
    return found


class FontCharacters(object):
    """What coverage reads of a font: its code points, and attaches(letter's code point, mark's code
    point): whether its anchors put that mark on that letter (None: letters are never composed)."""

    def __init__(self, codes, attaches=None):
        self.codes = set(codes)
        self.attaches = attaches
        self.known = {}  # character: what support() said (languages share most of theirs)

    def support(self, item):
        if item not in self.known:
            self.known[item] = support(item, self)
        return self.known[item]


HAVE, COMPOSED, PARTS, MISSING = "have", "composed", "parts", "missing"


def support(item, font):
    """How a font has one of a language's characters: HAVE (its own glyph), COMPOSED (its letter and
    marks, which its anchors put together), PARTS (its letter and marks, but no anchors that join
    them), or MISSING. A letter with two marks may stand on a letter with one (e with macron, then
    acute)."""
    codes = code_points(item)
    if len(codes) == 1 and codes[0] in font.codes:
        return HAVE, None
    composed = code_points(unicodedata.normalize("NFC", item))
    if len(composed) == 1 and composed[0] in font.codes:
        return HAVE, None  # (listed decomposed)
    parts = code_points(unicodedata.normalize("NFD", item))
    if len(parts) < 2 or not all(is_mark(code) for code in parts[1:]):
        return MISSING, None
    for size in range(len(parts) - 1, 0, -1):
        base = code_points(unicodedata.normalize("NFC", u"".join(char_of(code) for code in parts[:size])))
        if len(base) == 1 and base[0] in font.codes:
            base, marks = base[0], parts[size:]
            break
    else:
        return MISSING, None
    if not all(code in font.codes for code in marks):
        return MISSING, None
    recipe = (base, tuple(marks))
    if font.attaches is not None and all(font.attaches(base, code) for code in marks):
        return COMPOSED, recipe
    return PARTS, recipe


class Coverage(object):
    """How a font covers a language: level is "covered", "nearly", or "missed"."""

    def __init__(self, language, missing, auxiliary_missing, marks_missing, composed, parts, level):
        self.language = language
        self.missing, self.auxiliary_missing, self.marks_missing = missing, auxiliary_missing, marks_missing
        self.composed = composed  # [(character, (letter, marks))]: counted, made of the font's letter and marks
        self.parts = parts  # missing characters whose letter and marks the font has, without anchors joining them
        self.level = level

    def base_missing(self):
        return len(self.missing) + len(self.marks_missing)

    def all_missing(self):
        """Every missing character: base, marks, auxiliary."""
        return self.missing + self.marks_missing + self.auxiliary_missing


LEVELS = (("nearly", u"Within reach"), ("covered", u"Covered"), ("missed", u"Missed"))


def check_language(language, font, nearly=NEARLY_MISSING):
    missing, auxiliary_missing, composed, parts = [], [], [], []
    for items, into in ((language.base, missing), (language.auxiliary, auxiliary_missing)):
        for item in items:
            how, recipe = font.support(item)
            if how == COMPOSED:
                composed.append((item, recipe))
            elif how != HAVE:
                into.append(item)
                if how == PARTS:
                    parts.append(item)
    marks_missing = [char_of(code) for code in code_points(language.marks or u"") if code not in font.codes]
    short = len(missing) + len(marks_missing)
    level = "covered" if not short and not auxiliary_missing else "nearly" if short <= nearly else "missed"
    return Coverage(language, missing, auxiliary_missing, marks_missing, composed, parts, level)


class ScriptCoverage(object):
    def __init__(self, script, results, present):
        self.script, self.results, self.present = script, results, present  # present: the font has the script

    def count(self, level):
        return sum(1 for r in self.results if r.level == level)


def coverage_order(result):
    order = dict((level, index) for index, (level, _) in enumerate(LEVELS))
    language = result.language
    if result.level == "nearly":
        rest = (result.base_missing(), len(result.auxiliary_missing))
    elif result.level == "missed":
        rest = (result.base_missing(), 0)
    else:
        rest = (0, 0)
    return (order[result.level], rest, -(language.speakers or 0), language.name)


def coverage(languages, font, nearly=NEARLY_MISSING, historical=False):
    """[ScriptCoverage], the scripts the font has first (those with the most languages covered or
    within reach first); within each, the languages within reach first (the fewest missing first),
    then the covered ones, then the missed ones, the most spoken first."""
    by_script = {}
    for language in languages:
        if language.status == "historical" and not historical:
            continue
        by_script.setdefault(language.script, []).append(check_language(language, font, nearly))
    found = []
    for script, results in by_script.items():
        letters = set()
        for r in results:
            for item in r.language.base:
                codes = code_points(item)
                if len(codes) == 1:
                    letters.add(codes[0])
        if script != "Latin":
            letters -= set(range(0x80))
        have = len(letters & font.codes)
        present = any(r.level == "covered" for r in results) or (have and have >= min(SCRIPT_MINIMUM, len(letters)))
        found.append(ScriptCoverage(script, sorted(results, key=coverage_order), present))
    found.sort(key=lambda s: (not s.present, -(s.count("covered") + s.count("nearly")), s.script))
    return found


def buildable_candidates(results, ranges):
    """The missing characters of the given coverages a letter-and-marks builder may make: single
    characters in the ranges [(low, high)] that decompose into a letter and marks (in order, once)."""
    found = []
    for r in results:
        for item in r.missing + r.auxiliary_missing:
            codes = code_points(item)
            if len(codes) == 1 and 0x0300 <= codes[0] < 0x0370 and item not in found:
                found.append(item)  # a combining mark: Diacritics makes it of the mark it comes from (macron below of the macron)
                continue
            if len(codes) != 1 or not any(low <= codes[0] < high for low, high in ranges):
                continue
            parts = code_points(unicodedata.normalize("NFD", item))
            if len(parts) > 1 and all(is_mark(code) for code in parts[1:]) and item not in found:
                found.append(item)
    return found


# ---------------------------------------------------------------------------
# Vertical metrics
# ---------------------------------------------------------------------------

class VerticalMetrics(object):
    """A font's vertical metrics as Font Info keeps them (None: not set, or not readable). use_typo:
    OS/2 fsSelection bit 7, Use Typo Metrics."""

    FIELDS = ("upm", "ascender", "descender", "x_height", "cap_height", "line_gap",
              "typo_ascender", "typo_descender", "typo_line_gap", "hhea_ascender", "hhea_descender", "hhea_line_gap",
              "win_ascent", "win_descent", "use_typo")

    def __init__(self, **values):
        for field in self.FIELDS:
            setattr(self, field, values.get(field))


class Extent(object):
    """A glyph's ink, top to bottom, in one master."""

    def __init__(self, name, code, master, bottom, top):
        self.name, self.code, self.master, self.bottom, self.top = name, code, master, bottom, top


class MetricFinding(object):
    """One thing the metrics check found: kind (its group), severity ("problem", "advice", or "info"),
    a sentence, and the glyphs it names [(master, glyph, units)]."""

    def __init__(self, kind, severity, text, glyphs=None, value=None, check=None):
        self.kind, self.severity, self.text = kind, severity, text
        self.glyphs = glyphs or []
        self.value = value  # the units it is off by, or None
        self.check = check or kind  # which check found it (CHECKS)


METRIC_GROUPS = (("clip-top", u"Clipped at the top on Windows (above winAscent)"),
                 ("clip-bottom", u"Clipped at the bottom on Windows (below winDescent)"),
                 ("settings", u"Line metrics"),
                 ("beyond-top", u"Reaching above the line's ascender (may touch the line above)"),
                 ("beyond-bottom", u"Reaching below the line's descender (may touch the line below)"))

LOWERCASE_DEPTH = tuple(range(0x61, 0x7B)) + tuple(range(0x3B1, 0x3CA)) + tuple(range(0x430, 0x450))  # a-z, alpha-omega, a-ya
CAPITALS = tuple(range(0x41, 0x5B)) + tuple(range(0x391, 0x3AA)) + tuple(range(0x410, 0x430))


CAPITAL_BLOCKS = ((0x41, 0x250), (0x370, 0x530), (0x1E00, 0x2000))  # Latin, Greek, Cyrillic (and their extensions)


def is_letter(code):
    try:
        return unicodedata.category(char_of(code)).startswith(u"L")
    except (TypeError, ValueError):
        return False


def other_letters(codes):
    """The font's letters outside the scripts with capitals (Arabic, Devanagari, Han...)."""
    return set(code for code in codes if code >= 0x41 and is_letter(code)
               and not any(low <= code < high for low, high in CAPITAL_BLOCKS))


def has_capitals(codes):
    """Whether the font's main script has capitals (Latin, Greek, Cyrillic: as many of its letters are
    theirs as any other script's): Google Fonts' advice on line height and centered capitals applies."""
    if sum(1 for code in CAPITALS if code in codes) < SCRIPT_MINIMUM:
        return False
    ours = sum(1 for code in codes if is_letter(code) and any(low <= code < high for low, high in CAPITAL_BLOCKS))
    return ours >= len(other_letters(codes))


def family_extent(extents):
    """(lowest bottom, highest top) of every glyph in every master, or (None, None)."""
    if not extents:
        return None, None
    return min(e.bottom for e in extents), max(e.top for e in extents)


def line_values(m):
    """(ascender, descender, line gap) of the line as Windows (with Use Typo Metrics) and macOS space
    it: typo where set, else hhea."""
    if m.typo_ascender or m.typo_descender:
        return m.typo_ascender or 0, m.typo_descender or 0, m.typo_line_gap or 0
    if m.hhea_ascender or m.hhea_descender:
        return m.hhea_ascender or 0, m.hhea_descender or 0, m.hhea_line_gap or 0
    return None


def check_metrics(m, extents, capitals=True):
    """[MetricFinding] of the font's vertical metrics, as Google Fonts' vertical metrics guidance asks
    (see docs/FONT-CHECK.md): no glyph clipped by winAscent or winDescent, Use Typo Metrics on, hhea
    equal to typo, line gaps of 0, the line 120% to 130% of the em (capitals' scripts), the line's
    ascender above A grave, capitals centered in the line."""
    upm = float(m.upm or 1000)
    found = []
    if m.win_ascent and m.win_descent:
        for e in sorted(extents, key=lambda e: (-e.top, e.name, e.master)):
            if e.top > m.win_ascent:
                found.append(MetricFinding("clip-top", "problem", u"%s reaches %d, %d above winAscent (%d)" % (
                    e.name, round_units(e.top), round_units(e.top - m.win_ascent), m.win_ascent),
                    [(e.master, e.name, round_units(e.top - m.win_ascent))], round_units(e.top - m.win_ascent)))
        for e in sorted(extents, key=lambda e: (e.bottom, e.name, e.master)):
            if e.bottom < -m.win_descent:
                found.append(MetricFinding("clip-bottom", "problem", u"%s reaches %d, %d below winDescent (%d)" % (
                    e.name, round_units(e.bottom), round_units(-m.win_descent - e.bottom), m.win_descent),
                    [(e.master, e.name, round_units(-m.win_descent - e.bottom))], round_units(-m.win_descent - e.bottom)))
    else:
        found.append(MetricFinding("settings", "advice", u"winAscent and winDescent are not set: Windows clips "
                                   u"what reaches past them, so they should reach the font's highest and lowest "
                                   u"points", check="win-unset"))
    if m.use_typo is False:
        found.append(MetricFinding("settings", "problem", u"Use Typo Metrics is off: Windows spaces lines by "
                                   u"winAscent and winDescent, so raising them to stop clipping loosens the lines "
                                   u"too", check="use-typo"))
    elif m.use_typo is None:
        found.append(MetricFinding("settings", "info", u"FontLab did not say whether Use Typo Metrics (OS/2 "
                                   u"fsSelection bit 7) is on: it should be", check="use-typo"))
    for label, hhea, typo in ((u"ascender", m.hhea_ascender, m.typo_ascender),
                              (u"descender", m.hhea_descender, m.typo_descender),
                              (u"line gap", m.hhea_line_gap, m.typo_line_gap)):
        if hhea is not None and typo is not None and round_units(hhea) != round_units(typo):
            found.append(MetricFinding("settings", "advice", u"hhea %s (%d) and typo %s (%d) differ: macOS and Windows "
                                       u"space lines differently" % (label, hhea, label, typo), check="match"))
    for label, gap in ((u"typo", m.typo_line_gap), (u"hhea", m.hhea_line_gap)):
        if gap:
            found.append(MetricFinding("settings", "advice", u"The %s line gap is %d: applications add it above the "
                                       u"line, or share it above and below (browsers); 0 spaces lines alike "
                                       u"everywhere" % (label, gap), value=round_units(gap), check="gap"))
    line = line_values(m)
    if line is not None:
        ascender, descender, gap = line
        share = (ascender - descender + gap) / upm
        if capitals and not LINE_RANGE[0] - 0.005 <= share <= LINE_RANGE[1] + 0.005:
            found.append(MetricFinding("settings", "advice", u"The line is %d%% of the em: Google Fonts asks 120%% to "
                                       u"130%% for Latin, Greek, and Cyrillic (%s)" % (
                                           round_units(share * 100), u"tighter lines may touch" if share < LINE_RANGE[0]
                                           else u"looser looks spaced out, unless taller scripts need it"),
                                       value=round_units(share * 100), check="share"))
        a_grave = [e for e in extents if e.code == 0xC0]
        tallest = max(a_grave, key=lambda e: e.top) if a_grave else None
        if tallest is not None and tallest.top > ascender:
            found.append(MetricFinding("settings", "advice", u"\N{LATIN CAPITAL LETTER A WITH GRAVE} reaches %d, above "
                                       u"the line's ascender (%d): some "
                                       u"macOS applications then place the first line by it" % (
                                           round_units(tallest.top), ascender),
                                       [(tallest.master, tallest.name, round_units(tallest.top - ascender))],
                                       check="agrave"))
        if capitals and m.cap_height and descender:
            above = ascender - m.cap_height
            if abs(above + descender) > CENTER_TOLERANCE_SHARE * upm:
                found.append(MetricFinding("settings", "info", u"Capitals are not centered in the line: %d above the "
                                           u"cap height, %d below the baseline (Google Fonts' advice: equal, for "
                                           u"buttons and boxes)" % (round_units(above), round_units(-descender)),
                                           check="center"))
        over = sorted((e for e in extents if e.top > ascender), key=lambda e: (-e.top, e.name))
        under = sorted((e for e in extents if e.bottom < descender), key=lambda e: (e.bottom, e.name))
        for kind, rows, edge in (("beyond-top", over, ascender), ("beyond-bottom", under, descender)):
            for e in rows[:BEYOND_SHOWN]:
                by = round_units(e.top - edge) if kind == "beyond-top" else round_units(edge - e.bottom)
                found.append(MetricFinding(kind, "info", u"%s: %d past it" % (e.name, by), [(e.master, e.name, by)], by,
                                           check="beyond"))
    else:
        found.append(MetricFinding("settings", "advice", u"Neither typo nor hhea ascender and descender are set: "
                                   u"each application then spaces lines its own way", check="unset"))
    bottom, top = family_extent(extents)
    if m.win_ascent and m.win_descent and top is not None and m.use_typo is not True:
        slack = max(m.win_ascent - top, m.win_descent + bottom)
        if slack > WIN_SLACK_SHARE * upm:
            found.append(MetricFinding("settings", "info", u"winAscent and winDescent reach %d past the ink: with Use "
                                       u"Typo Metrics off, Windows spaces lines that much looser than needed" %
                                       round_units(slack), check="slack"))
    return found


class Suggestion(object):
    def __init__(self, key, label, now, value):
        self.key, self.label, self.now, self.value = key, label, now, value

    def changes(self):
        if self.now is None and self.value == 0 and self.key in ZERO_READS_UNSET:
            return False  # (0 reads as not set: written, it would read as not set again)
        return self.now is None or self.now != self.value


ZERO_READS_UNSET = ("typo_ascender", "typo_descender", "hhea_ascender", "hhea_descender", "win_ascent", "win_descent")


SUGGESTED = (("typo_ascender", u"Typo ascender"), ("typo_descender", u"Typo descender"),
             ("typo_line_gap", u"Typo line gap"), ("hhea_ascender", u"hhea ascender"),
             ("hhea_descender", u"hhea descender"), ("hhea_line_gap", u"hhea line gap"),
             ("win_ascent", u"winAscent"), ("win_descent", u"winDescent"), ("use_typo", u"Use Typo Metrics"))
MODES = (("share", u"Line spacing at a share of the em"), ("keep", u"Keep the font's current line spacing"))
# (the designer's choice: a line spacing to suggest, or, for an update of a released font, the one it has)


def suggest_metrics(m, extents, capitals=True, mode="share", share=LINE_SHARE, letters=None):
    """([Suggestion], [note]) of vertical metrics following Google Fonts' guidance.

    "share": the line spacing at the share of the em set, capitals centered in it (or the font's
    ascender and descender scaled to it), raised to clear A grave and lowered to clear the deepest
    descender of a to z (Greek, Cyrillic), line gaps of 0, hhea equal to typo, win at the ink's
    highest and lowest points in every master, Use Typo Metrics on; for a font of another script, the
    line also raised and lowered to clear its letters' ink (letters: their code points). "keep" (an
    update of a released font): the font's current line spacing (typo kept if Use Typo Metrics was
    on, else the old win values become typo), win and Use Typo Metrics as for "share"."""
    upm = float(m.upm or 1000)
    notes = []
    bottom, top = family_extent(extents)

    def tallest(codes):
        found = [e.top for e in extents if e.code in codes]
        return max(found) if found else None

    def deepest(codes):
        found = [e.bottom for e in extents if e.code in codes]
        return min(found) if found else None

    ascender = descender = gap = None
    if mode == "keep":
        if m.use_typo is True and (m.typo_ascender or m.typo_descender):
            ascender, descender, gap = m.typo_ascender, m.typo_descender, m.typo_line_gap or 0
            notes.append(u"Use Typo Metrics was on: the typo values keep the font's line spacing.")
        elif m.win_ascent and m.win_descent:
            ascender, descender, gap = m.win_ascent, -m.win_descent, 0
            notes.append(u"Use Typo Metrics was off: the old win values become the typo values, so Windows keeps "
                         u"the font's line spacing.")
        else:
            notes.append(u"The font has no line spacing to keep (neither typo nor win values are set): suggested "
                         u"at the share of the em set.")
    if ascender is None:
        line = share * upm
        cap = m.cap_height or tallest((0x48,)) or 0.7 * upm
        if capitals:
            ascender = round_units((line - cap) / 2.0 + cap)
            descender = ascender - round_units(line)
            notes.append(u"The line spacing is %d%% of the em, capitals centered in it." % round_units(share * 100))
        else:
            high = m.ascender or top or 0.8 * upm
            low = m.descender or bottom or -0.2 * upm
            ascender = round_units(line * high / float(high - low))
            descender = ascender - round_units(line)
            notes.append(u"The line spacing is %d%% of the em, shared as the font's ascender and descender are." %
                         round_units(share * 100))
        gap = 0
        a_grave = tallest((0xC0,))
        if a_grave is not None and a_grave > ascender:
            ascender = int(math.ceil(a_grave))
            notes.append(u"The ascender is raised to the top of \N{LATIN CAPITAL LETTER A WITH GRAVE} (%d)." % ascender)
        low = deepest(LOWERCASE_DEPTH) if capitals else None
        if low is not None and low < descender:
            descender = int(math.floor(low))
            notes.append(u"The descender is lowered to the deepest lowercase descender (%d)." % descender)
        if not capitals and letters:
            high, low = tallest(letters), deepest(letters)
            if high is not None and high > ascender:
                ascender = int(math.ceil(high))
                notes.append(u"The ascender is raised to the tallest letter (%d)." % ascender)
            if low is not None and low < descender:
                descender = int(math.floor(low))
                notes.append(u"The descender is lowered to the deepest letter (%d)." % descender)
    values = {"typo_ascender": ascender, "typo_descender": descender, "typo_line_gap": gap,
              "hhea_ascender": ascender, "hhea_descender": descender, "hhea_line_gap": gap,
              "win_ascent": int(math.ceil(top)) if top is not None else m.win_ascent,
              "win_descent": int(math.ceil(-bottom)) if bottom is not None else m.win_descent,
              "use_typo": True}
    if top is not None:
        notes.append(u"winAscent and winDescent reach the highest and lowest ink of every glyph in every master.")
    return [Suggestion(key, label, getattr(m, key), values[key]) for key, label in SUGGESTED], notes


def suggestion_text(s):
    if s.key == "use_typo":
        return u"on" if s.value else u"off"
    return u"%d" % s.value if s.value is not None else u"\N{EN DASH}"


def now_text(s):
    if s.now is None:
        return u"not set"
    if s.key == "use_typo":
        return u"on" if s.now else u"off"
    return u"%d" % round_units(s.now)


# ---------------------------------------------------------------------------
# Masters: interpolation compatibility
# ---------------------------------------------------------------------------

class Contour(object):
    def __init__(self, nodes, closed=True):
        self.nodes = list(nodes)  # [(x, y, type)], in the master's coordinates
        self.closed = closed

    def types(self):
        return [node[2] for node in self.nodes]

    def area(self):
        """Twice the signed area of its polygon (all nodes): above 0 counterclockwise (y up)."""
        nodes, total = self.nodes, 0.0
        for at in range(len(nodes)):
            x0, y0 = nodes[at][0], nodes[at][1]
            x1, y1 = nodes[(at + 1) % len(nodes)][0], nodes[(at + 1) % len(nodes)][1]
            total += x0 * y1 - x1 * y0
        return total


class Outline(object):
    """What interpolation needs of a glyph in one master: its contours (components apart), its
    components' glyph names in order, and its anchors' names. blocks: how many of the contours each
    of its shapes holds, in order (None: not known; contours are reordered within their shape only)."""

    def __init__(self, contours=(), components=(), anchors=(), blocks=None):
        self.contours = list(contours)
        self.components = list(components)
        self.anchors = list(anchors)
        self.blocks = list(blocks) if blocks is not None else None


class Incompatibility(object):
    """A difference from the reference master; fixable: Font Check can set it right (the contours'
    order, a direction, a start point, the components' order), else it needs the designer."""

    def __init__(self, glyph, master, contour, kind, text, fixable=False):
        self.glyph, self.master, self.contour, self.kind, self.text = glyph, master, contour, kind, text
        self.fixable = fixable


def normalized(nodes):
    if not nodes:
        return []
    xs, ys = [n[0] for n in nodes], [n[1] for n in nodes]
    cx, cy = sum(xs) / float(len(xs)), sum(ys) / float(len(ys))
    size = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    return [((x - cx) / size, (y - cy) / size) for x, y in zip(xs, ys)]


def start_shift(reference, contour):
    """How many nodes on the contour's start point sits from where the reference's would match (0:
    where it should). Compared at the same node types only, shapes centered and scaled to their size.
    (Fitting each start to the reference by a stretch and a slant first found fewer moved starts on
    the corpus, at as many false alarms: docs/FONT-CHECK.md.)"""
    count = len(contour.nodes)
    if count < 3 or count != len(reference.nodes):
        return 0
    types, wanted = contour.types(), reference.types()
    a, b = normalized(reference.nodes), normalized(contour.nodes)

    def cost(shift):
        return sum((a[at][0] - b[(at + shift) % count][0]) ** 2 + (a[at][1] - b[(at + shift) % count][1]) ** 2
                   for at in range(count)) / float(count)

    here = cost(0)
    if here < START_MIN_SPREAD:
        return 0
    best, best_cost = 0, here
    for shift in range(1, count):
        if all(types[(at + shift) % count] == wanted[at] for at in range(count)):
            c = cost(shift)
            if c < best_cost:
                best, best_cost = shift, c
    if best and best_cost <= START_GAIN * here:
        return best if best <= count // 2 else best - count
    return 0


def turning(area):
    return u"counterclockwise" if area > 0 else u"clockwise"


def clear_area(contour):
    """Whether a contour's direction is plain: its signed area at least DIRECTION_SHARE of its box's
    (a figure eight's halves cancel out, and its direction means little)."""
    xs, ys = [n[0] for n in contour.nodes], [n[1] for n in contour.nodes]
    box = (max(xs) - min(xs)) * (max(ys) - min(ys)) if xs else 0
    return box > 0 and abs(contour.area()) / 2.0 >= DIRECTION_SHARE * box


def rotation_of(types, wanted):
    """The shift that turns one cyclic list of node types into the other, or None."""
    count = len(types)
    if count != len(wanted):
        return None
    for shift in range(count):
        if all(types[(at + shift) % count] == wanted[at] for at in range(count)):
            return shift
    return None


def is_off_curve(kind):
    return u"%s" % kind in (u"off", u"offcurve")


def turned_over(contour, other):
    """Whether two closed contours run opposite ways (their directions plain: clear_area)."""
    return bool(contour.closed and other.closed and clear_area(contour) and clear_area(other)
                and (contour.area() > 0) != (other.area() > 0))


def signed_shift(shift, count):
    """A start's shift as nodes on (above 0) or back (below 0), the shorter way round."""
    shift %= count
    return shift if shift <= count // 2 else shift - count


def best_rotation(reference, contour):
    """The start (nodes on, or back below 0) at which the contour's node types match the
    reference's and its points fit them best (centered and scaled to its size), or None when no
    start makes the types match."""
    count = len(contour.nodes)
    if count != len(reference.nodes) or not count:
        return None
    types, wanted = contour.types(), reference.types()
    a, b = normalized(reference.nodes), normalized(contour.nodes)
    best, best_cost = None, None
    for shift in range(count):
        if all(types[(at + shift) % count] == wanted[at] for at in range(count)):
            cost = sum((a[at][0] - b[(at + shift) % count][0]) ** 2 + (a[at][1] - b[(at + shift) % count][1]) ** 2
                       for at in range(count))
            if best_cost is None or cost < best_cost - 1e-12:
                best, best_cost = shift, cost
    return None if best is None else signed_shift(best, count)


def reversed_contour(contour):
    """A contour run the other way, its first node kept first (as FontLab's flContour.reverse())."""
    nodes = contour.nodes
    return Contour(nodes[:1] + nodes[:0:-1], contour.closed)


def rotated_contour(contour, index):
    """A contour whose first node is its node index (as FontLab's flContour.setStartPoint(index))."""
    return Contour(contour.nodes[index:] + contour.nodes[:index], contour.closed)


def contour_fix(reference, contour):
    """(reverse, start) that make a contour match the reference's: reverse it (FontLab keeps its first
    node first), then make its node start (an index, 0: as it is) the first; None when no such fix
    makes them compatible (other node counts or types, an open contour's start, or a start that
    would fall on an off-curve node: FontLab moves the start onto on-curve nodes only)."""
    count = len(contour.nodes)
    if contour.closed != reference.closed or count != len(reference.nodes) or not count:
        return None
    reverse = turned_over(contour, reference)
    model = reversed_contour(contour) if reverse else contour
    if model.types() == reference.types():
        shift = start_shift(reference, model)
    else:
        shift = best_rotation(reference, model)
        if shift is None:
            return None
    index = shift % count
    if index and (not contour.closed or is_off_curve(model.nodes[index][2])):
        return None
    return reverse, index


def matching_cost(reference, contour, reference_box, box):
    """How unlike two contours are, for putting a master's contours in the reference's order: not at
    all comparable (other node counts), else where they sit and how large they are in their glyph's
    box, plus one when their node types match in no direction and from no start."""
    if len(contour.nodes) != len(reference.nodes) or not contour.nodes:
        return None

    def place(c, outline_box):
        left, bottom, size = outline_box
        xs, ys = [n[0] for n in c.nodes], [n[1] for n in c.nodes]
        return ((sum(xs) / float(len(xs)) - left) / size, (sum(ys) / float(len(ys)) - bottom) / size,
                (max(xs) - min(xs)) / size, (max(ys) - min(ys)) / size)

    a, b = place(reference, reference_box), place(contour, box)
    cost = math.hypot(a[0] - b[0], a[1] - b[1]) + abs(a[2] - b[2]) + abs(a[3] - b[3])
    types, wanted = contour.types(), reference.types()
    if rotation_of(types, wanted) is None and rotation_of(types[::-1], wanted) is None:
        cost += 1.0
    return cost


def outline_box(contours):
    """(left, bottom, size) of contours' nodes: size the larger of width and height (1 when none)."""
    xs = [n[0] for c in contours for n in c.nodes]
    ys = [n[1] for c in contours for n in c.nodes]
    if not xs:
        return 0.0, 0.0, 1.0
    return min(xs), min(ys), float(max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0)


def assignment(cost):
    """The cheapest one-to-one assignment of rows to columns of a square cost matrix (Kuhn and
    Munkres' method, O(n^3)): [column of each row]."""
    n = len(cost)
    infinite = float("inf")
    u, v, p, way = [0.0] * (n + 1), [0.0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for row in range(1, n + 1):
        p[0], j0 = row, 0
        least, used = [infinite] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], infinite, 0
            for j in range(1, n + 1):
                if not used[j]:
                    here = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if here < least[j]:
                        least[j], way[j] = here, j0
                    if least[j] < delta:
                        delta, j1 = least[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    least[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    found = [0] * n
    for j in range(1, n + 1):
        found[p[j] - 1] = j - 1
    return found


UNMATCHED = 1e6  # the cost of pairing contours of other node counts: never chosen when another way exists


def match_contours(reference, contours):
    """A master's contours in the reference's order: [the master's contour at each of the reference's
    places], matched by node count (required), node types, and where they sit and how large they are
    in the glyph; None when no matching pairs every contour with one of its node count."""
    if len(reference) != len(contours):
        return None
    if not contours:
        return []
    reference_box, box = outline_box(reference), outline_box(contours)
    costs = []
    for at, r in enumerate(reference):
        row = []
        for k, c in enumerate(contours):
            cost = matching_cost(r, c, reference_box, box)
            row.append(UNMATCHED if cost is None else cost + 1e-9 * abs(at - k))  # (ties: kept in place)
        costs.append(row)
    order = assignment(costs)
    if any(costs[at][k] >= UNMATCHED for at, k in enumerate(order)):
        return None
    return order


def within_blocks(order, blocks):
    """Whether a reordering keeps every contour in its own shape (blocks: contours per shape; None:
    one shape)."""
    if blocks is None:
        return True
    owner, start = {}, 0
    for number, size in enumerate(blocks):
        for k in range(start, start + size):
            owner[k] = number
        start += size
    return all(k in owner and at in owner and owner[k] == owner[at] for at, k in enumerate(order))


def component_order(reference, components):
    """The master's components in the reference's order: [the master's component at each of the
    reference's places], the same names taken in turn; None when they are in that order already, or
    are not the same components."""
    if components == reference or sorted(components) != sorted(reference):
        return None
    used, order = set(), []
    for name in reference:
        k = next(k for k, other in enumerate(components) if other == name and k not in used)
        used.add(k)
        order.append(k)
    return order


def moved_text(shift):
    return counted(abs(shift), u"node") + (u" on" if shift > 0 else u" back")


def node_kind(kind):
    return {u"on": u"on-curve", u"off": u"off-curve", u"curve": u"curve", u"line": u"line"}.get(u"%s" % kind, u"%s" % kind)


def compare_glyph(name, outlines):
    """[Incompatibility] of one glyph across masters [(master, Outline or None)], each master compared
    with the first that has the glyph (None: the master lacks it)."""
    found = []
    present = [(master, outline) for master, outline in outlines if outline is not None]
    if len(present) < 2:
        # In one master only: a glyph that does not vary (FontLab gives a variable font's glyphs layers only
        # in the masters where they differ; .notdef, spaces, and joiners have the default's alone)
        return found
    reference_master, reference = present[0]
    for master, outline in outlines:
        if outline is None:
            found.append(Incompatibility(name, master, None, "missing", u"No layer in this master, though %d have "
                                                                          u"one" % len(present)))
    for master, outline in present[1:]:
        found.extend(compare_outline(name, reference_master, reference, master, outline))
    return found


def compare_outline(name, reference_master, reference, master, outline):
    found = []
    ref = reference_master

    def add(contour, kind, text, fixable=False):
        found.append(Incompatibility(name, master, contour, kind, text, fixable() if callable(fixable) else fixable))

    if len(outline.contours) != len(reference.contours):
        add(None, "contours", u"%s, %d in %s" % (counted(len(outline.contours), u"contour"), len(reference.contours), ref))
    else:
        sizes, wanted = [len(c.nodes) for c in outline.contours], [len(c.nodes) for c in reference.contours]
        reordered = sizes != wanted and sorted(sizes) == sorted(wanted)
        pairs = list(enumerate(zip(outline.contours, reference.contours)))
        if reordered:
            order = match_contours(reference.contours, outline.contours)
            add(None, "order", u"Contours in another order than in %s (their node counts: %s; %s in %s)" % (
                ref, u" ".join(u"%d" % s for s in sizes), u" ".join(u"%d" % s for s in wanted), ref),
                order is not None and within_blocks(order, outline.blocks))
            if order is not None:  # each contour compared with its match in the reference
                place = dict((k, at) for at, k in enumerate(order))
                pairs = [(k, (outline.contours[k], reference.contours[place[k]])) for k in range(len(order))]
        for at, (contour, other) in pairs:
            number = at + 1
            if contour.closed != other.closed:
                add(number, "open", u"%s here, %s in %s" % (u"Closed" if contour.closed else u"Open",
                                                            u"closed" if other.closed else u"open", ref))
            if len(contour.nodes) != len(other.nodes):
                if not reordered:
                    add(number, "nodes", u"%s, %d in %s" % (counted(len(contour.nodes), u"node"), len(other.nodes), ref))
                continue
            types, wanted_types = contour.types(), other.types()
            area, other_area = contour.area(), other.area()
            turned = turned_over(contour, other)
            fixable = lambda contour=contour, other=other: contour_fix(other, contour) is not None  # (asked once found)
            if types != wanted_types:
                if turned and rotation_of(types[::-1], wanted_types) is not None:
                    add(number, "direction", u"Runs %s, %s in %s (reversed: its node types match the other way "
                                             u"round)" % (turning(area), turning(other_area), ref), fixable)
                    continue
                shift = best_rotation(other, contour) if contour.closed and other.closed and not turned else None
                if shift:
                    add(number, "start", u"Start point %s from where %s's would match (its node types match from "
                                         u"there)" % (moved_text(shift), ref), fixable)
                    continue
                index = next(i for i in range(len(types)) if types[i] != wanted_types[i])
                add(number, "types", u"Node %d is %s, %s in %s" % (index + 1, node_kind(types[index]),
                                                                    node_kind(wanted_types[index]), ref))
                continue
            if turned:
                add(number, "direction", u"Runs %s, %s in %s" % (turning(area), turning(other_area), ref), fixable)
                continue
            shift = start_shift(other, contour)
            if shift:
                add(number, "start", u"Start point %s from where %s's would match" % (moved_text(shift), ref), fixable)
    if outline.components != reference.components:
        if sorted(outline.components) == sorted(reference.components):
            add(None, "components", u"Components in another order: %s; %s in %s" % (
                u", ".join(outline.components), u", ".join(reference.components), ref), True)
        else:
            add(None, "components", u"Components %s; %s in %s" % (
                u", ".join(outline.components) or u"none", u", ".join(reference.components) or u"none", ref))
    lacks = [a for a in reference.anchors if a not in outline.anchors]
    extra = [a for a in outline.anchors if a not in reference.anchors]
    if lacks or extra:
        parts = []
        if lacks:
            parts.append(u"lacks %s %s" % (u"anchor" if len(lacks) == 1 else u"anchors", u", ".join(lacks)))
        if extra:
            parts.append(u"has %s %s that %s lacks" % (u"anchor" if len(extra) == 1 else u"anchors", u", ".join(extra), ref))
        add(None, "anchors", (u"; ".join(parts))[:1].upper() + (u"; ".join(parts))[1:])
    return found


MASTER_KINDS = (("missing", (u"glyph missing in a master", u"glyphs missing in a master")),
                ("contours", (u"contour count", u"contour counts")), ("order", (u"contour order", u"contour orders")),
                ("open", (u"contour open in one master", u"contours open in one master")),
                ("nodes", (u"node count", u"node counts")), ("types", (u"node type", u"node types")),
                ("direction", (u"direction", u"directions")), ("start", (u"start point", u"start points")),
                ("components", (u"component list", u"component lists")), ("anchors", (u"anchor set", u"anchor sets")))


class FixPlan(object):
    """What Font Check sets right in a glyph's layer in one master to match the reference master:
    order (the master's contour at each of the reference's places; None: kept), contours [(place
    after the order, reverse, start index, node count)]: reverse the contour (its first node kept
    first), then make its node start the first; components (the master's component at each of the
    reference's places; None: kept) and the reference's component names."""

    def __init__(self, order=None, contours=(), components=None, names=()):
        self.order, self.contours, self.components, self.names = order, list(contours), components, list(names)

    def empty(self):
        return self.order is None and not self.contours and self.components is None


def plan_fixes(reference, outline):
    """The FixPlan that makes a master's outline match the reference's as far as it can without the
    designer: its contours in the reference's order (matched by node count, node types, and place, and
    kept within their shapes), each contour's direction and start point, its components' order.
    Everything else (contour and node counts, node types, open contours, components, anchors) is left
    as it is."""
    plan = FixPlan()
    if len(outline.contours) == len(reference.contours):
        contours = list(outline.contours)
        sizes, wanted = [len(c.nodes) for c in contours], [len(c.nodes) for c in reference.contours]
        if sizes != wanted and sorted(sizes) == sorted(wanted):
            order = match_contours(reference.contours, contours)
            if order is not None and within_blocks(order, outline.blocks):
                plan.order = order if order != list(range(len(order))) else None
                contours = [outline.contours[k] for k in order]
            else:
                contours = None
        for at, (contour, other) in enumerate(zip(contours or [], reference.contours)):
            fix = contour_fix(other, contour)
            if fix is not None and (fix[0] or fix[1]):
                plan.contours.append((at, fix[0], fix[1], len(contour.nodes)))
    plan.components = component_order(reference.components, outline.components)
    if plan.components is not None:
        plan.names = list(reference.components)
    return plan


def apply_plan(outline, plan):
    """The Outline a FixPlan makes of a master's outline (what FontLab should read back)."""
    contours = [outline.contours[k] for k in plan.order] if plan.order is not None else list(outline.contours)
    for at, reverse, index, _ in plan.contours:
        contour = reversed_contour(contours[at]) if reverse else contours[at]
        contours[at] = rotated_contour(contour, index) if index else contour
    components = [outline.components[k] for k in plan.components] if plan.components is not None else outline.components
    return Outline(contours, components, outline.anchors, outline.blocks)


def plan_steps(plan, reference_master):
    """What a FixPlan does, in short phrases: "contours put in Regular's order", "contour 2 reversed,
    its start point moved 1 node on"."""
    steps = []
    if plan.order is not None:
        steps.append(u"contours put in %s's order" % reference_master)
    for at, reverse, index, count in plan.contours:
        moved = u"start point moved %s" % moved_text(signed_shift(index, count)) if index else u""
        if reverse:
            steps.append(u"contour %d reversed" % (at + 1) + (u", its " + moved if moved else u""))
        else:
            steps.append(u"contour %d's %s" % (at + 1, moved))
    if plan.components is not None:
        steps.append(u"components put in %s's order" % reference_master)
    return steps


def same_outline(one, other, tolerance=0.5):
    """Whether two outlines have the same contours (open or closed, nodes, their types and places,
    within tolerance units) and components, in the same order."""
    if one is None or other is None or len(one.contours) != len(other.contours) or one.components != other.components:
        return False
    for a, b in zip(one.contours, other.contours):
        if a.closed != b.closed or len(a.nodes) != len(b.nodes):
            return False
        for p, q in zip(a.nodes, b.nodes):
            if u"%s" % p[2] != u"%s" % q[2] or abs(p[0] - q[0]) > tolerance or abs(p[1] - q[1]) > tolerance:
                return False
    return True


FIX_WORDS = {"order": u"the contours' order", "direction": u"the direction", "start": u"the start point",
             "components": u"the components' order"}
DESIGNER_WORDS = {"missing": u"the missing layer (add it)", "contours": u"the contour count (add or remove contours)",
                  "order": u"the contours' order (their shapes or node types do not allow it: reorder them by hand)",
                  "open": u"the open contour (open or close it)", "nodes": u"the node count (add or remove nodes)",
                  "types": u"the node types (make them match)",
                  "direction": u"the direction (reversed, the node types still differ)",
                  "start": u"the start point (it would fall on an off-curve node, or the contour is open)",
                  "components": u"the components (add or remove them)", "anchors": u"the anchors (add or remove them)"}
FIX_LABELS = {"all": u"Fixable", "some": u"Partly fixable", "none": u"Needs the designer"}


def fix_state(problems):
    """"all", "some", or "none": how many of a glyph's problems Font Check can fix."""
    fixable = [f for f in problems if f.fixable]
    return "none" if not fixable else "all" if len(fixable) == len(problems) else "some"


def word_list(words):
    """"a", "a and b", "a, b, and c"."""
    if len(words) < 3:
        return u" and ".join(words)
    return u", ".join(words[:-1]) + u", and " + words[-1]


def fix_sentence(problems):
    """What Fix sets right of a glyph's problems and what needs the designer, in one sentence."""
    fixes, left = [], []
    for kind, _ in MASTER_KINDS:
        if any(f.kind == kind and f.fixable for f in problems):
            fixes.append(FIX_WORDS[kind])
        if any(f.kind == kind and not f.fixable for f in problems):
            left.append(DESIGNER_WORDS[kind])
    if not fixes and not left:
        return u""
    if not left:
        return u"Fix sets %s right." % word_list(fixes)
    rest = u"%s %s the designer" % (word_list(left), u"needs" if len(left) == 1 else u"need")
    if not fixes:
        return u"Needs the designer: %s." % word_list(left)
    return u"Fix sets %s right; %s." % (word_list(fixes), rest)


# ---------------------------------------------------------------------------
# Vertical metrics written: the fields of FontLab's font info (fgPackage.info) each suggestion sets
# ---------------------------------------------------------------------------

INFO_FIELDS = (("typo_ascender", "openTypeOS2TypoAscender"), ("typo_descender", "openTypeOS2TypoDescender"),
               ("typo_line_gap", "openTypeOS2TypoLineGap"), ("hhea_ascender", "openTypeHheaAscender"),
               ("hhea_descender", "openTypeHheaDescender"), ("hhea_line_gap", "openTypeHheaLineGap"),
               ("win_ascent", "openTypeOS2WinAscent"), ("win_descent", "openTypeOS2WinDescent"))
USE_TYPO_BIT = 7  # OS/2 fsSelection: Use Typo Metrics


def metric_writes(suggestions):
    """[Suggestion] of the suggested values that differ from the font's and can be written (font info
    fields and Use Typo Metrics; the masters' own metrics are not among them)."""
    fields = dict(INFO_FIELDS)
    return [s for s in suggestions if s.value is not None and s.changes() and (s.key in fields or s.key == "use_typo")]


def selection_with(bits, on, bit=USE_TYPO_BIT):
    """OS/2 fsSelection's bits (a list of bit numbers, as FontLab keeps them) with bit set or cleared."""
    found = set(int(b) for b in bits or [])
    if on:
        found.add(bit)
    else:
        found.discard(bit)
    return sorted(found)


def write_text(s):
    """A value written, for the log: "Typo ascender 800 → 965"."""
    return u"%s %s \N{RIGHTWARDS ARROW} %s" % (s.label, now_text(s), suggestion_text(s))


# ---------------------------------------------------------------------------
# What the dialog shows: characters to add ranked by the languages they complete, the languages a
# set of characters completes, the metrics diagram's lines, the masters' problems by glyph
# ---------------------------------------------------------------------------

DOTTED_CIRCLE = u"\N{DOTTED CIRCLE}"


def shown_text(item):
    """A character as shown: a mark alone stands on a dotted circle."""
    codes = code_points(item)
    if codes and is_mark(codes[0]):
        return DOTTED_CIRCLE + item
    return item


def code_label(item):
    """"U+0159", or "U+006E U+0308" for a letter and marks Unicode has no single character for."""
    return u" ".join(u"U+%04X" % code for code in code_points(item))


def unicode_name(code):
    try:
        return u"%s" % unicodedata.name(char_of(code))
    except (TypeError, ValueError):
        return u""


def mark_name(code):
    name = unicode_name(code)
    if name.startswith(u"COMBINING "):
        name = name[len(u"COMBINING "):]
    return name.lower() or u"U+%04X" % code


CASE_WORDS = ((u" SMALL LETTER ", False), (u" CAPITAL LETTER ", True), (u" LETTER ", None))


def short_name(item):
    """A character's Unicode name, short: "r with caron", "R with caron", "capital eng", "peh",
    "combining acute accent"; a letter and marks with no single character, "n with diaeresis"."""
    codes = code_points(item)
    if not codes:
        return u""
    if len(codes) > 1:
        base = short_name(char_of(codes[0]))
        return base + (u" and " if u" with " in base else u" with ") + u" and ".join(mark_name(c) for c in codes[1:])
    name = unicode_name(codes[0])
    if not name:
        return code_label(item)
    if not name.startswith(u"MODIFIER"):
        for word, capital in CASE_WORDS:
            at = name.find(word)
            if at > 0:
                rest = name[at + len(word):].lower()
                if capital:
                    head, _, tail = rest.partition(u" ")
                    if len(head) == 1:
                        return head.upper() + (u" " + tail if tail else u"")
                    return u"capital " + rest
                return rest
    return name.lower()


def case_partner(item):
    """The other case of a one-character letter (Ə for ə), or None."""
    codes = code_points(item)
    if len(codes) != 1:
        return None
    for other in (item.upper(), item.lower()):
        if other != item and len(code_points(other)) == 1:
            return other
    return None


def base_needs(r):
    """A language's missing base characters and marks."""
    return r.missing + r.marks_missing


def needs(r):
    """What a language within reach lacks to be complete: its missing base characters and marks (as
    Hyperglot's support asks), or, when it misses only auxiliary characters (loan words, names), those."""
    return base_needs(r) or r.auxiliary_missing


def language_rank(r):
    return (len(needs(r)), -(r.language.speakers or 0), r.language.name)


class AddRow(object):
    """A row of "Add these": a missing character (a capital and its small letter together when both
    are missing), the languages within reach that need it, and those it completes on its own."""

    def __init__(self, items, needing, completing):
        self.items, self.needing, self.completing = items, needing, completing

    def text(self):
        return u" ".join(shown_text(item) for item in self.items)

    def key(self):
        return u" ".join(self.items)

    def auxiliary(self):
        """Whether the languages need it only as an auxiliary character (loan words, names)."""
        return all(item not in base_needs(r) for r in self.needing for item in self.items)


def add_rows(results):
    """[AddRow] of what the languages within reach (level "nearly") need (needs: their missing base
    characters and marks, or their auxiliary ones when they miss only those), ranked by the languages
    each completes on its own, then by the languages that need it, then by code point. A capital and
    its small letter both missing make one row (a language needs them together)."""
    needing, order = {}, []
    for r in results:
        if r.level != "nearly":
            continue
        for item in needs(r):
            if item not in needing:
                needing[item] = []
                order.append(item)
            if r not in needing[item]:
                needing[item].append(r)
    rows, placed = [], set()
    for item in sorted(order, key=code_points):
        if item in placed:
            continue
        items = [item]
        partner = case_partner(item)
        if partner is not None and partner in needing and partner not in placed:
            items = sorted([item, partner], key=lambda c: (c != c.upper(), code_points(c)))  # the capital first
        placed.update(items)
        languages = []
        for one in items:
            languages.extend(r for r in needing[one] if r not in languages)
        own = set(items)
        completing = [r for r in languages if set(needs(r)) <= own]
        rows.append(AddRow(items, sorted(languages, key=language_rank), sorted(completing, key=language_rank)))
    rows.sort(key=lambda row: (-len(row.completing), -len(row.needing), code_points(row.items[0])))
    return rows


def languages_gained(results, checked):
    """The languages within reach whose needs are all in checked (a set of characters): sets, not
    sums, so a language needing two characters counts once, with both."""
    checked = set(checked)
    return [r for r in results if r.level == "nearly" and needs(r) and set(needs(r)) <= checked]


def gain_text(checked_count, gained, bold=None):
    """The live line over "Add these": "With 6 characters checked: +14 languages (Latin)" (bold: how
    the count gained is set in rich text)."""
    if not checked_count:
        return u"Check characters to see how many languages they complete."
    scripts, order = {}, []
    for r in gained:
        if r.language.script not in scripts:
            scripts[r.language.script] = 0
            order.append(r.language.script)
        scripts[r.language.script] += 1
    head = u"With %s checked: " % counted(checked_count, u"character")
    if not gained:
        return head + u"no language is complete yet"
    if len(order) == 1:
        where = order[0]
    else:
        where = u", ".join(u"%s %d" % (script, scripts[script]) for script in
                           sorted(order, key=lambda s: (-scripts[s], s)))
    count = u"+%s" % counted(len(gained), u"language")
    return head + u"%s (%s)" % (bold(count) if bold else count, where)


CHECK_BUTTONS = (("all", u"Check all"), ("none", u"Check none"), ("buildable", u"Check only what Diacritics can build"))


def checks_for(rows, checked, buildable):
    """What each check button over "Add these" would leave checked, {key: set of characters}, None
    for a button that would change nothing (it is grayed out): "all" adds every row listed to the
    checks, "none" clears them, "buildable" checks the rows listed with a character Diacritics can
    build (buildable), and nothing else. rows: the AddRows listed; checked: the characters checked."""
    checked, buildable = set(checked), set(buildable or ())
    listed = set(item for row in rows for item in row.items)
    can = set(item for row in rows if any(c in buildable for c in row.items) for item in row.items)
    found = {"all": checked | listed, "none": set(), "buildable": can}
    return dict((key, None if value == checked or (key == "buildable" and not can) else value)
                for key, value in found.items())


def compact_missing(r, shown=2):
    """A language's missing characters, compact: "ß", or "Ǎ ǎ +1" (its base characters and marks, or
    its auxiliary ones when it misses only those)."""
    items = needs(r)
    text = u" ".join(shown_text(item) for item in items[:shown])
    if len(items) > shown:
        text += u" +%d" % (len(items) - shown)
    return text


def script_text(s):
    """A script's summary: "275 of 569 languages · 99 within reach"."""
    total = len(s.results)
    text = u"%d of %s" % (s.count("covered"), counted(total, u"language"))
    if s.count("nearly"):
        text += u" \N{MIDDLE DOT} %d within reach" % s.count("nearly")
    return text


def bar_widths(counts, width):
    """Pixel widths of a bar's segments, in proportion to counts, summing to width; a segment with a
    count is at least a pixel wide."""
    total = float(sum(counts))
    if total <= 0 or width <= 0:
        return [0] * len(counts)
    widths = [int(round(width * c / total)) if c else 0 for c in counts]
    widths = [max(1, w) if c else 0 for w, c in zip(widths, counts)]
    while sum(widths) != width:
        step = 1 if sum(widths) < width else -1
        at = max(range(len(widths)), key=lambda k: (widths[k] if step < 0 else counts[k], k))
        if step < 0 and widths[at] <= 1:
            break
        widths[at] += step
    return widths


class DiagramLine(object):
    """A horizontal line of the metrics diagram: its value in font units, the fields it stands for
    (several when they are equal), and its kind: "win", "line" (typo, hhea), "guide" (cap height,
    x-height, baseline), or "suggested"."""

    def __init__(self, value, names, kind):
        self.value, self.names, self.kind = value, list(names), kind

    def label(self):
        return u"%s %d" % (merge_names(self.names), self.value)


DIAGRAM_FIELDS = (("win_ascent", u"winAscent", "win", 1), ("typo_ascender", u"typo ascender", "line", 1),
                  ("hhea_ascender", u"hhea ascender", "line", 1), ("cap_height", u"cap height", "guide", 1),
                  ("x_height", u"x-height", "guide", 1), (None, u"baseline", "guide", 1),
                  ("typo_descender", u"typo descender", "line", 1), ("hhea_descender", u"hhea descender", "line", 1),
                  ("win_descent", u"winDescent", "win", -1))
KIND_ORDER = ("win", "line", "guide")


def merge_names(names):
    """Names of equal values as one label: "typo and hhea ascender", "winAscent, typo ascender"."""
    groups, order = {}, []
    for name in names:
        head, _, tail = name.rpartition(u" ")
        key = tail if head else name
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(head if head else None)
    parts = []
    for key in order:
        heads = groups[key]
        if len(heads) == 1 or None in heads:
            parts.extend((h + u" " + key) if h else key for h in heads)
        else:
            joined = heads[0] + u" and " + heads[1] if len(heads) == 2 else \
                u", ".join(heads[:-1]) + u", and " + heads[-1]
            parts.append(joined + u" " + key)
    return u", ".join(parts)


def diagram_lines(m, suggestions=()):
    """[DiagramLine], highest first: the font's values (equal ones one line, every name kept), then the
    suggested values that differ from them, dashed in the diagram."""
    found = {}
    for key, name, kind, sign in DIAGRAM_FIELDS:
        value = 0 if key is None else getattr(m, key, None)
        if value is None or (key is not None and not value and kind != "line"):
            continue
        value = round_units(sign * value)
        line = found.get(value)
        if line is None:
            found[value] = DiagramLine(value, [name], kind)
        else:
            line.names.append(name)
            if KIND_ORDER.index(kind) < KIND_ORDER.index(line.kind):
                line.kind = kind
    lines = sorted(found.values(), key=lambda l: -l.value)
    shown = {}
    for s in suggestions:
        if s.key not in ("typo_ascender", "hhea_ascender", "typo_descender", "hhea_descender", "win_ascent",
                         "win_descent") or s.value is None or not s.changes():
            continue
        value = -s.value if s.key == "win_descent" else s.value
        name = dict((k, n) for k, n, _, _ in DIAGRAM_FIELDS)[s.key]
        if value in shown:
            shown[value].names.append(name)
        else:
            shown[value] = DiagramLine(value, [name], "suggested")
    return lines + sorted(shown.values(), key=lambda l: -l.value)


def spread_labels(wanted, gap, low=None, high=None):
    """Positions for labels wanted at the given positions (any order; the result in the same order),
    at least gap apart, each as near its own as the others allow, within low and high when given."""
    order = sorted(range(len(wanted)), key=lambda k: wanted[k])
    clusters = []  # [start position, [indexes]]
    for k in order:
        clusters.append([float(wanted[k]), [k]])
        while len(clusters) > 1:
            (start_a, a), (start_b, b) = clusters[-2], clusters[-1]
            if start_a + gap * len(a) <= start_b:
                break
            members = a + b
            mean = sum(wanted[i] for i in members) / float(len(members))
            clusters[-2:] = [[mean - gap * (len(members) - 1) / 2.0, members]]
    placed = {}
    for start, members in clusters:
        for n, k in enumerate(members):
            placed[k] = start + gap * n
    positions = [placed[k] for k in range(len(wanted))]
    if low is not None or high is not None:
        ranked = sorted(range(len(wanted)), key=lambda k: positions[k])
        if low is not None:
            floor = low
            for k in ranked:
                positions[k] = max(positions[k], floor)
                floor = positions[k] + gap
        if high is not None:
            ceiling = high
            for k in reversed(ranked):
                positions[k] = min(positions[k], ceiling)
                ceiling = positions[k] - gap
    return positions


def extreme_glyphs(extents, count=3):
    """(tallest, deepest): the glyphs whose ink reaches highest and lowest, count of each, each in the
    master where it reaches farthest, a glyph in one list only (the tallest first, the deepest first)."""
    top, bottom = {}, {}
    for e in extents:
        if e.name not in top or e.top > top[e.name].top:
            top[e.name] = e
        if e.name not in bottom or e.bottom < bottom[e.name].bottom:
            bottom[e.name] = e
    tallest = sorted(top.values(), key=lambda e: (-e.top, e.name))[:count]
    taken = set(e.name for e in tallest)
    deepest = [e for e in sorted(bottom.values(), key=lambda e: (e.bottom, e.name)) if e.name not in taken][:count]
    return tallest, deepest


class Clipped(object):
    """A glyph Windows clips in a master: by how much above winAscent and below winDescent (0: not)."""

    def __init__(self, extent, above, below):
        self.extent, self.above, self.below = extent, above, below

    def worst(self):
        return max(self.above, self.below)


def clipped_glyphs(m, extents, master=None):
    """[Clipped], the worst first: in the master given, or each glyph once, in its worst master."""
    if not (m.win_ascent and m.win_descent):
        return []
    found = {}
    for e in extents:
        if master is not None and e.master != master:
            continue
        above = max(0, round_units(e.top - m.win_ascent))
        below = max(0, round_units(-m.win_descent - e.bottom))
        if not above and not below:
            continue
        clipped = Clipped(e, above, below)
        key = e.name if master is None else (e.name, e.master)
        if key not in found or clipped.worst() > found[key].worst():
            found[key] = clipped
    return sorted(found.values(), key=lambda c: (-c.worst(), c.extent.name, c.extent.master))


class CheckLine(object):
    """A line of the metrics checks: state "ok", "warn", or "info", a short sentence, its tooltip, and
    the glyphs it is about (clicking it selects them among the clipped glyphs)."""

    def __init__(self, state, text, tip=u"", glyphs=()):
        self.state, self.text, self.tip, self.glyphs = state, text, tip, list(glyphs)


def check_lines(m, extents, findings, capitals=True):
    """[CheckLine] of check_metrics' findings, one short sentence each, and the checks passed (so the
    user sees what was checked): problems first, then advice, then what passed."""
    by = {}
    for f in findings:
        by.setdefault(f.check, []).append(f)

    def tip(check):
        return u"\n".join(f.text for f in by.get(check, []))

    warn, info, ok = [], [], []
    if m.win_ascent and m.win_descent:
        for side, word in (("above", u"at the top"), ("below", u"at the bottom")):
            worst = {}
            for e in extents:
                over = round_units(e.top - m.win_ascent if side == "above" else -m.win_descent - e.bottom)
                if over > worst.get(e.name, 0):
                    worst[e.name] = over
            rows = sorted(worst.items(), key=lambda item: (-item[1], item[0]))
            if rows:
                warn.append(CheckLine("warn", u"Windows clips %s %s, up to %d units (%s)" % (
                    counted(len(rows), u"glyph"), word, rows[0][1], rows[0][0]),
                    u"Windows cuts off what reaches %s %s (%d): %s." % (
                        side, u"winAscent" if side == "above" else u"winDescent",
                        m.win_ascent if side == "above" else m.win_descent,
                        u", ".join(u"%s %d" % row for row in rows[:20]) +
                        (u"\N{HORIZONTAL ELLIPSIS}" if len(rows) > 20 else u"")),
                    [name for name, _ in rows]))
        if not any(line.glyphs for line in warn):
            ok.append(CheckLine("ok", u"Windows clips no glyph", u"winAscent (%d) and winDescent (%d) reach past the "
                                u"ink of every glyph in every master." % (m.win_ascent, m.win_descent)))
    else:
        warn.append(CheckLine("warn", u"winAscent and winDescent are not set", tip("win-unset")))
    if m.use_typo is True:
        ok.append(CheckLine("ok", u"Use Typo Metrics is on", u"Windows spaces lines by the typo values."))
    elif m.use_typo is False:
        warn.append(CheckLine("warn", u"Use Typo Metrics is off: Windows spaces lines by winAscent and winDescent",
                              tip("use-typo")))
    else:
        info.append(CheckLine("info", u"FontLab did not say whether Use Typo Metrics is on", tip("use-typo")))
    hhea = (m.hhea_ascender, m.hhea_descender, m.hhea_line_gap)
    if by.get("match"):
        warn.append(CheckLine("warn", u"hhea and typo values differ: macOS and Windows space lines differently",
                              tip("match")))
    elif all(value is None for value in hhea):
        info.append(CheckLine("info", u"The hhea values are not set in Font Info",
                              u"FontLab's export then writes values of its own (which, unproven)."))
    elif line_values(m) is not None:
        ok.append(CheckLine("ok", u"hhea and typo values match", u"macOS and Windows space lines alike."))
    gaps = [(label, gap) for label, gap in ((u"typo", m.typo_line_gap), (u"hhea", m.hhea_line_gap)) if gap]
    if gaps:
        values = sorted(set(round_units(gap) for _, gap in gaps))
        warn.append(CheckLine("warn", (u"Line gap %d: set it to 0 and add it to the ascender and descender" % values[0])
                              if len(values) == 1 else (u"Line gaps %s: set them to 0 and add them to the ascender "
                                                        u"and descender" % u" and ".join(u"%d" % v for v in values)),
                              tip("gap")))
    elif m.typo_line_gap is not None or m.hhea_line_gap is not None:
        ok.append(CheckLine("ok", u"Line gaps are 0", u"Applications space lines alike."))
    line = line_values(m)
    if line is None:
        warn.append(CheckLine("warn", u"Neither typo nor hhea ascender and descender are set", tip("unset")))
    else:
        ascender, descender, gap = line
        share = round_units((ascender - descender + gap) * 100.0 / float(m.upm or 1000))
        if by.get("share"):
            warn.append(CheckLine("warn", u"The line is %d%% of the em: Google Fonts asks 120%% to 130%%" % share,
                                  tip("share")))
        elif capitals:
            ok.append(CheckLine("ok", u"The line is %d%% of the em" % share, u"Google Fonts asks 120% to 130% for "
                                u"Latin, Greek, and Cyrillic."))
        if by.get("agrave"):
            f = by["agrave"][0]
            warn.append(CheckLine("warn", u"\N{LATIN CAPITAL LETTER A WITH GRAVE} reaches above the line's ascender, "
                                  u"by %d" % f.glyphs[0][2],
                                  f.text, [f.glyphs[0][1]]))
        elif any(e.code == 0xC0 for e in extents):
            ok.append(CheckLine("ok", u"\N{LATIN CAPITAL LETTER A WITH GRAVE} stays under the line's ascender",
                                u"Some macOS applications place the first line by the top of "
                                u"\N{LATIN CAPITAL LETTER A WITH GRAVE}."))
        if by.get("center"):
            info.append(CheckLine("info", u"Capitals are not centered in the line", tip("center")))
        elif capitals and m.cap_height:
            ok.append(CheckLine("ok", u"Capitals are centered in the line", u"As much room above the cap height as "
                                u"below the baseline."))
        for kind, word in (("beyond-top", u"above the line's ascender"), ("beyond-bottom", u"below the line's descender")):
            rows = [f for f in by.get("beyond", []) if f.kind == kind]
            if rows:
                more = u"" if len(rows) < BEYOND_SHOWN else u" (the farthest %d)" % BEYOND_SHOWN
                info.append(CheckLine("info", u"%s reach %s%s" % (counted(len(rows), u"glyph"), word, more),
                                      u"They may touch the line %s at the font's own line spacing (tall marks often "
                                      u"do): %s." % (u"above" if kind == "beyond-top" else u"below",
                                                     u", ".join(u"%s %d" % (f.glyphs[0][1], f.value) for f in rows)),
                                      [f.glyphs[0][1] for f in rows]))
    if by.get("slack"):
        info.append(CheckLine("info", u"winAscent and winDescent reach well past the ink", tip("slack")))
    return warn + info + ok


MASTER_WEIGHT = {"missing": 3, "contours": 3, "order": 3, "open": 3, "nodes": 3, "types": 3, "direction": 2,
                 "start": 2, "components": 2, "anchors": 1}
PROBLEM_CHIPS = (("missing", u"No layer"), ("contours", u"Contour counts"), ("order", u"Contour order"),
                 ("open", u"Open contours"), ("nodes", u"Node counts"), ("types", u"Node types"),
                 ("direction", u"Directions"), ("start", u"Start points"), ("components", u"Components"),
                 ("anchors", u"Anchors"))


def problem_counts(found):
    """[(kind, chip label, glyphs with it)] in PROBLEM_CHIPS' order, the kinds found only."""
    glyphs = {}
    for f in found:
        glyphs.setdefault(f.kind, set()).add(f.glyph)
    return [(kind, label, len(glyphs[kind])) for kind, label in PROBLEM_CHIPS if kind in glyphs]


def glyph_problems(found, kinds=None):
    """[(glyph, [Incompatibility])] of the problems of the given kinds (None: all), the worst glyphs
    first (the gravest problem, then the most problems), then by name."""
    by, order = {}, []
    for f in found:
        if kinds is not None and f.kind not in kinds:
            continue
        if f.glyph not in by:
            by[f.glyph] = []
            order.append(f.glyph)
        by[f.glyph].append(f)
    order.sort(key=lambda g: (-max(MASTER_WEIGHT.get(f.kind, 1) for f in by[g]), -len(by[g]), g))
    return [(g, by[g]) for g in order]


def master_states(problems, masters, reference):
    """One state per master, in order, for a glyph's problems: "reference", "missing", "grave" (it
    cannot interpolate), "minor" (it interpolates, oddly: directions, start points, components,
    anchors), or "ok"."""
    states = []
    for master in masters:
        mine = [f for f in problems if f.master == master]
        if master == reference:
            states.append("reference")
        elif any(f.kind == "missing" for f in mine):
            states.append("missing")
        elif any(MASTER_WEIGHT.get(f.kind, 1) >= 3 for f in mine):
            states.append("grave")
        elif mine:
            states.append("minor")
        else:
            states.append("ok")
    return states


def problem_sentence(problems):
    """A master's problems with a glyph, one sentence each: "Contour 2: 12 nodes, 14 in Regular."."""
    lines = []
    for f in problems:
        text = (u"Contour %d: %s%s" % (f.contour, f.text[:1].lower(), f.text[1:])) if f.contour else f.text
        lines.append(text + (u"" if text.endswith(u".") else u"."))
    return u" ".join(lines)


# ---------------------------------------------------------------------------
# FontLab: reading the font (every call guarded: only those noted in docs/FONT-CHECK.md are proven)
# ---------------------------------------------------------------------------

def glyph_codes(fg):
    """A fontgate glyph's code points (its unicodes, else its unicode)."""
    try:
        codes = [int(code) for code in (fg.unicodes or []) if code]
    except Exception:
        codes = []
    if not codes:
        try:
            codes = [int(fg.unicode)] if fg.unicode else []
        except Exception:
            codes = []
    return codes


def anchor_names(layer):
    names = []
    try:
        for anchor in layer.anchors:
            names.append(u"%s" % anchor.name)
    except Exception:
        pass
    return names


def read_metrics(package):
    """The current master's dimensions (flPackage) and the font's OpenType line metrics (fgFontInfo)."""
    def value(obj, name):
        try:
            found = getattr(obj, name)
            found = found() if callable(found) else found
            return float(found) if found is not None else None
        except Exception:
            return None

    info = None
    try:
        info = package.fgPackage.info
    except Exception:
        pass
    use_typo = None
    try:
        bits = [int(bit) for bit in (info.openTypeOS2Selection or [])]
        use_typo = 7 in bits
    except Exception:
        pass

    def set_or_none(found):
        return found if found else None  # (an ascender or descender of 0: not set)

    return VerticalMetrics(
        upm=value(package, "upm"), ascender=value(package, "ascender_value"), descender=value(package, "descender_value"),
        x_height=value(package, "xHeight_value"), cap_height=value(package, "capsHeight_value"),
        line_gap=value(package, "lineGap_value"),
        typo_ascender=set_or_none(value(info, "openTypeOS2TypoAscender")),
        typo_descender=set_or_none(value(info, "openTypeOS2TypoDescender")),
        typo_line_gap=value(info, "openTypeOS2TypoLineGap"),
        hhea_ascender=set_or_none(value(info, "openTypeHheaAscender")),
        hhea_descender=set_or_none(value(info, "openTypeHheaDescender")),
        hhea_line_gap=value(info, "openTypeHheaLineGap"),
        win_ascent=set_or_none(value(info, "openTypeOS2WinAscent")),
        win_descent=set_or_none(value(info, "openTypeOS2WinDescent")),
        use_typo=use_typo)


def read_outline(layer):
    """A layer's Outline: contours of its own shapes (their transforms applied), its components' glyph
    names, its anchors' names; None when it cannot be read."""
    contours, components, blocks = [], [], []
    try:
        shapes = list(layer.shapes)
    except Exception:
        return None
    for shape in shapes:
        try:
            component = bool(shape.isComponent)
        except Exception:
            component = False
        if component:
            try:
                components.append(u"%s" % shape.shapeData.componentGlyph)
            except Exception:
                components.append(u"?")
            continue
        try:
            t = shape.transform
            matrix = (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy())
        except Exception:
            matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        a, b, c, d, dx, dy = matrix
        held = 0
        for contour in shape.contours:
            if contour is None:  # FontLab lists an empty contour as None in some glyphs
                continue
            nodes = []
            for node in contour.nodes():
                x, y = float(node.x), float(node.y)
                nodes.append((a * x + c * y + dx, b * x + d * y + dy, u"%s" % node.type))
            try:
                closed = bool(contour.closed)
            except Exception:
                closed = True
            contours.append(Contour(nodes, closed))
            held += 1
        blocks.append(held)
    return Outline(contours, components, anchor_names(layer), blocks)


# ---------------------------------------------------------------------------
# FontLab: fixing the masters (proven live on 2026-11-11: flContour.reverse(), setStartPoint() with an
# on-curve node's index, clone(), flShape.clearContours() and addContours(clones, True); not proven:
# flLayer.reorderShapes(), used for the components' order, and flShapeData.id)
# ---------------------------------------------------------------------------

class FixError(Exception):
    pass


def is_component(shape):
    try:
        return bool(shape.isComponent)
    except Exception:
        return False


def own_shapes(layer):
    """[(shape, [its contours, None for an empty one])] of a layer's shapes that are not components,
    in order (read_outline's)."""
    return [(shape, list(shape.contours)) for shape in list(layer.shapes) if not is_component(shape)]


def shape_ids(layer):
    """The ids of the shape data of a layer's own shapes (two masters sharing one would change
    together), as texts; empty when FontLab does not say."""
    found = set()
    try:
        shapes = list(layer.shapes)
    except Exception:
        return found
    for shape in shapes:
        if is_component(shape):
            continue
        try:
            ident = shape.shapeData.id
            if ident:
                found.add(u"%s" % ident)
        except Exception:
            pass
    return found


def shape_signature(shape):
    """What tells a layer's shapes apart when their order is read back: a component's glyph and
    offset, or a shape's contours' node counts."""
    if is_component(shape):
        try:
            name = u"%s" % shape.shapeData.componentGlyph
        except Exception:
            name = u"?"
        try:
            t = shape.transform
            offset = (round_units(t.dx()), round_units(t.dy()))
        except Exception:
            offset = None
        return ("component", name, offset)
    try:
        return ("shape", tuple(len(c.nodes()) for c in shape.contours if c is not None))
    except Exception:
        return ("shape", None)


def permutation_to(current, target):
    """[the place in current of what goes at each place of target] (equal items taken in turn)."""
    used, order = set(), []
    for item in target:
        k = next(k for k, other in enumerate(current) if other == item and k not in used)
        used.add(k)
        order.append(k)
    return order


def inverse(order):
    found = [0] * len(order)
    for at, k in enumerate(order):
        found[k] = at
    return found


def reorder_components(layer, names):
    """The layer's components put in the order of names (the reference's), its other shapes kept in
    place, by flLayer.reorderShapes (unproven: its argument's meaning is read back, the indexes taken
    either way, then the shapes themselves); FixError when the order did not change as wanted."""
    signatures = [shape_signature(shape) for shape in list(layer.shapes)]
    places = [at for at, s in enumerate(signatures) if s[0] == "component"]
    order = component_order(list(names), [signatures[at][1] for at in places])
    if order is None:
        return
    target = list(signatures)
    for place, k in zip(places, order):
        target[place] = signatures[places[k]]
    for attempt in ("take", "put", "shapes"):
        shapes = list(layer.shapes)
        current = [shape_signature(shape) for shape in shapes]
        if current == target:
            return
        try:
            take = permutation_to(current, target)
        except StopIteration:
            raise FixError(u"FontLab changed the layer's shapes")
        argument = take if attempt == "take" else inverse(take) if attempt == "put" else [shapes[k] for k in take]
        try:
            layer.reorderShapes(argument)
        except Exception:
            pass
    if [shape_signature(shape) for shape in list(layer.shapes)] != target:
        raise FixError(u"FontLab did not reorder the components")


def apply_fix(layer, plan):
    """A FixPlan carried out on a FontLab layer (FixError, or FontLab's own error, when a step
    failed: the steps before it are done)."""
    if plan.order is not None:
        start = 0
        for shape, contours in own_shapes(layer):
            present = [c for c in contours if c is not None]
            wanted = [plan.order[k] - start for k in range(start, start + len(present))]
            if any(not 0 <= k < len(present) for k in wanted):
                raise FixError(u"its contours would move from one shape to another")
            if wanted != list(range(len(present))):
                if len(present) != len(contours):
                    raise FixError(u"a shape lists an empty contour")
                clones = [present[k].clone() for k in wanted]
                shape.clearContours()
                shape.addContours(clones, True)
            start += len(present)
    if plan.contours:
        flat = [c for _, contours in own_shapes(layer) for c in contours if c is not None]
        for at, reverse, index, _ in plan.contours:
            contour = flat[at]
            if reverse:
                contour.reverse()
            if index and contour.setStartPoint(index) is False:
                raise FixError(u"FontLab did not move the start point of contour %d" % (at + 1))
    if plan.components is not None:
        reorder_components(layer, plan.names)
    for shape, _ in own_shapes(layer):
        try:
            shape.update()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# The dialog (Qt)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def _prop(obj, name):
    """A Qt property's value: an attribute in PythonQt (a method in some builds)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


def register_list_font(QtCore, QtGui):
    """FreeLab Languages registered with Qt once per FontLab session; its family, or None (no file, or
    Qt refused it). In the dialog's font, Qt 5 took each character it lacks from another font: rare
    scripts' autonyms showed as boxes and some Cyrillic ones spaced wide. The bundled font has every
    character the languages list shows (checks/language_font), so the list is drawn in one design."""
    if LIST_FAMILY in [u"%s" % f for f in QtGui.QFontDatabase().families()]:
        return LIST_FAMILY
    path = list_font_path()
    if path is None:
        return None
    if isinstance(path, bytes):  # (Python 2: the file system's encoding, for Qt's unicode path)
        path = path.decode(sys.getfilesystemencoding() or "mbcs")
    added = QtGui.QFontDatabase.addApplicationFont(path)
    if added < 0:  # (a path Qt could not open: the font's bytes instead)
        with open(path, "rb") as handle:
            added = QtGui.QFontDatabase.addApplicationFontFromData(QtCore.QByteArray(handle.read()))
    if added < 0:
        return None
    families = [u"%s" % f for f in QtGui.QFontDatabase.applicationFontFamilies(added)]
    return families[0] if families else None


HELP = u"""<b>FreeLab Font Check</b><br>
Three views of the current font. Nothing in the font changes until you click <i>Write suggested
values</i> or <i>Fix</i>. A fix is one step of <i>Edit &gt; Undo</i>; the font info written is not in FontLab's
History: <i>Put back old values</i> takes it back.<br><br>
<b>Coverage</b>: the scripts the font has, each with a bar (covered, within reach, missed) from
Hyperglot's orthographies; click one to see only its languages. At the left, the characters to add,
ranked by the languages each completes on its own: check some (or all, none, or only those
<i>Diacritics</i> can build), and the line above the list says how many languages they complete
together. At the right, the languages: find one by name, or show only
the covered, within reach, or missed ones; selecting one marks the characters it needs at the left.
A letter the font lacks as one character counts when its anchors compose it from the font's letter and
mark (the language says <i>composed</i>).<br>
<b>Vertical metrics</b>: the font's tallest and deepest glyphs drawn on its line metrics (winAscent,
typo and hhea, cap height, x-height), the ink Windows clips in red, the suggested values dashed; the
values now and suggested, for the line spacing you set (a share of the em), or keeping the font's
current line spacing for an update of a released font; the checks Google Fonts' guidance asks for;
the glyphs Windows clips. <i>Write suggested values</i> sets the font's typo, hhea, and win values and <i>Use Typo Metrics</i>
(those that differ); the masters' ascender, descender, x-height, and cap height, which FontLab draws
with, are left as they are.<br>
<b>Masters</b>: the glyphs that keep the masters from interpolating, worst first, a mark per master;
the selected glyph drawn in the master compared with and in another, the contour at fault highlighted
and its nodes numbered. <i>Fix</i> sets right, in the other masters, the contours' order, directions,
start points, and the components' order; contour and node counts, node types, missing layers, and
anchors need the designer. The master compared with never changes.<br><br>
Each view is checked as its tab is first shown, and again after an undo or an edit in FontLab. Click
this help's <i>?</i> button, then any control, for what it does."""

AMBER = (230, 150, 30)  # within reach, warnings
RED = (222, 64, 52)  # clipped ink, masters that cannot interpolate
GREEN = (64, 168, 92)  # passed checks
GRAY = (128, 128, 128)
LINE_ALPHA = 128  # the lists' lines: a mid gray at half strength
QUIET_ALPHA = 150  # passed checks, secondary text
CHAR_ICON = (64, 36)  # pixels: a missing character's picture (a capital and its small letter fit)
BAR_SIZE = (150, 14)  # a script's bar
DOT_SIZE = 14  # a language's state
STATE_SIZE = 16  # a check's icon
THUMB_SIZE = 32  # a glyph's picture in the Masters list
MARK_SIZE = 10  # a master's mark
CLIP_TILE = (92, 112)  # a clipped glyph: its picture, then its name and its overflow under it
COLUMN_MAX = 230  # pixels: a list's middle column at most
DIAGRAM_GAP = 0.1  # of the em, between the diagram's glyphs
DIAGRAM_NAME_MIN = 64  # pixels: room for a glyph's name under it in the diagram (longer ones elided)
SCRIPT_SHEET = (u"QTreeView::item:selected { background: rgba(128, 128, 128, 70); color: palette(text); } "
                u"QTreeView { selection-background-color: rgba(128, 128, 128, 70); }")
# (the script clicked shows in a faint gray: its bar's covered part is in the highlight color)
CHIP_SHEET = (u"QToolButton { background: transparent; color: rgba(128, 128, 128, 255); "
              u"border: 1px solid rgba(128, 128, 128, 110); border-radius: 10px; padding: 2px 10px; } "
              u"QToolButton:hover { color: palette(window-text); border: 1px solid rgba(128, 128, 128, 200); } "
              u"QToolButton:checked { color: palette(highlighted-text); background: palette(highlight); "
              u"border: 1px solid palette(highlight); } "
              u"QToolButton:checked:hover { border: 1px solid palette(window-text); } "
              u"QToolButton:disabled { color: rgba(128, 128, 128, 110); }")
# FreeLab's chips (as Font Compare's): flat, a kind shown filled in the highlight color, a kind hidden
# as a gray outline, over either palette, set on each chip (never on the dialog, whose fields dark
# mode then maps) and left alone by dark mode, as Auto Kerning's TAB_SHEET is. Windows' own style
# drew a checked tool button light whatever the palette: mapped, it came out garbled, white in dark mode.
LANGUAGE_FILTERS = ((None, u"All"), ("covered", u"Covered"), ("nearly", u"Within reach"), ("missed", u"Missed"))
STATE_LABELS = {"covered": u"Covered", "nearly": u"Within reach", "missed": u"Missed"}


def qcolor(rgb, alpha=255):
    QtCore, QtGui = _qt()
    return QtGui.QColor(rgb[0], rgb[1], rgb[2], alpha)


def faded(color, alpha):
    QtCore, QtGui = _qt()
    found = QtGui.QColor(color)
    found.setAlpha(alpha)
    return found


def level_color(level, colors):
    return {"covered": colors["highlight"], "nearly": qcolor(AMBER)}.get(level) or qcolor(GRAY, LINE_ALPHA)


def new_pixmap(width, height):
    QtCore, QtGui = _qt()
    pixmap = QtGui.QPixmap(max(1, int(width)), max(1, int(height)))
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    return pixmap


def text_width(font, text):
    QtCore, QtGui = _qt()
    return QtGui.QFontMetrics(font).width(text)


def elided(font, text, width):
    """text cut to fit width pixels, an ellipsis at its end."""
    if text_width(font, text) <= width:
        return text
    while text and text_width(font, text + u"\N{HORIZONTAL ELLIPSIS}") > width:
        text = text[:-1]
    return text + u"\N{HORIZONTAL ELLIPSIS}" if text else u""


def ink_box(path):
    """(left, bottom, right, top) of a glyph's ink in font units, or None (no ink)."""
    if path is None or path.isEmpty():
        return None
    rect = path.boundingRect()  # font units grow upward: the rect's top() is the ink's bottom
    return rect.left(), rect.top(), rect.right(), rect.bottom()


def bar_pixmap(counts, colors, size=BAR_SIZE):
    """A script's bar: covered, within reach, and missed languages, in proportion."""
    QtCore, QtGui = _qt()
    width, height = size
    pixmap = new_pixmap(width, height)
    painter = QtGui.QPainter(pixmap)
    try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
        x = 0
        top, thick = height // 2 - 4, 8
        for level, w in zip(("covered", "nearly", "missed"), bar_widths(counts, width)):
            if w:
                painter.fillRect(QtCore.QRect(x, top, w, thick), level_color(level, colors))
                x += w
    finally:
        painter.end()
    return pixmap


def dot_pixmap(color, size=DOT_SIZE):
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(size, size)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(color))
        painter.drawEllipse(QtCore.QRectF(size / 2.0 - 4.5, size / 2.0 - 4.5, 9.0, 9.0))
    finally:
        painter.end()
    return pixmap


def state_pixmap(state, colors, size=STATE_SIZE):
    """A check's icon, drawn: a green check (passed), an amber warning sign, or a gray dot (to know)."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(size, size)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        s = float(size)
        if state == "ok":
            pen = QtGui.QPen(qcolor(GREEN))
            pen.setWidthF(2.2)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            path = QtGui.QPainterPath()
            path.moveTo(s * 0.2, s * 0.55)
            path.lineTo(s * 0.42, s * 0.76)
            path.lineTo(s * 0.82, s * 0.26)
            painter.drawPath(path)
        elif state == "warn":
            path = QtGui.QPainterPath()
            path.moveTo(s * 0.5, s * 0.08)
            path.lineTo(s * 0.96, s * 0.9)
            path.lineTo(s * 0.04, s * 0.9)
            path.closeSubpath()
            painter.fillPath(path, QtGui.QBrush(qcolor(AMBER)))
            dark = QtGui.QColor(50, 34, 0)
            painter.fillRect(QtCore.QRectF(s * 0.44, s * 0.34, s * 0.12, s * 0.3), dark)
            painter.fillRect(QtCore.QRectF(s * 0.44, s * 0.7, s * 0.12, s * 0.11), dark)
        else:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(qcolor(GRAY, 170)))
            painter.drawEllipse(QtCore.QRectF(s * 0.3, s * 0.3, s * 0.4, s * 0.4))
    finally:
        painter.end()
    return pixmap


def character_pixmap(text, color, font, size=CHAR_ICON):
    """Characters the font lacks, drawn in a reference font (the dialog's, with Qt's fallback for the
    scripts it lacks) in the text color, centered, made smaller to fit."""
    QtCore, QtGui = _qt()
    width, height = size
    face = QtGui.QFont(font)
    face.setPixelSize(int(height * 0.62))
    path = QtGui.QPainterPath()
    path.addText(QtCore.QPointF(0, 0), face, text)
    pixmap = new_pixmap(width, height)
    rect = path.boundingRect()
    box_width, box_height = rect.right() - rect.left(), rect.bottom() - rect.top()
    if not box_width > 0 or not box_height > 0:
        return pixmap
    scale = min(1.0, (width - 6) / float(box_width), (height - 4) / float(box_height))
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.translate(width / 2.0, height / 2.0)
        painter.scale(scale, scale)
        painter.translate(-(rect.left() + rect.right()) / 2.0, -(rect.top() + rect.bottom()) / 2.0)
        painter.fillPath(path, QtGui.QBrush(color))
    finally:
        painter.end()
    return pixmap


def glyph_thumb(path, color, width=THUMB_SIZE, height=THUMB_SIZE):
    """A glyph's ink fitted in a box of the list's picture size (font units up), centered."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(width, height)
    box = ink_box(path)
    if box is None:
        return pixmap
    left, bottom, right, top = box
    scale = min((width - 6) / float(max(right - left, 1.0)), (height - 6) / float(max(top - bottom, 1.0)))
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.translate(width / 2.0 - (left + right) / 2.0 * scale, height / 2.0 + (bottom + top) / 2.0 * scale)
        painter.scale(scale, -scale)
        painter.fillPath(path, QtGui.QBrush(color))
    finally:
        painter.end()
    return pixmap


def marks_pixmap(states, colors, box=None, size=MARK_SIZE):
    """A mark per master, in order: a ring for the master compared with, a faint dot where all is
    well, red where the glyph cannot interpolate (a dashed square: no layer), amber where it
    interpolates oddly; in a box of the list's picture size, at its left, centered up and down."""
    QtCore, QtGui = _qt()
    step = size + 4
    width, height = box or (max(1, len(states)) * step, size + 4)
    pixmap = new_pixmap(width, height)
    top = (height - size) / 2.0
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for at, state in enumerate(states):
            rect = QtCore.QRectF(at * step + 2, top, size, size)
            if state == "reference":
                pen = QtGui.QPen(colors["text"])
                pen.setWidthF(1.5)
                painter.setPen(pen)
                painter.setBrush(QtGui.QBrush())
                painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
            elif state == "missing":
                pen = QtGui.QPen(qcolor(RED), 1.5, QtCore.Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(QtGui.QBrush())
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
            elif state in ("grave", "minor"):
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QBrush(qcolor(RED if state == "grave" else AMBER)))
                painter.drawEllipse(rect)
            else:
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QBrush(qcolor(GRAY, 90)))
                painter.drawEllipse(rect.adjusted(2.5, 2.5, -2.5, -2.5))
    finally:
        painter.end()
    return pixmap


class Picture(object):
    """A glyph to draw: its path (font units), ink box, advance, caption, a second caption line (its
    master), and whether it is the one selected."""

    def __init__(self, name, path, advance, master=u"", selected=False):
        self.name, self.path, self.advance, self.master, self.selected = name, path, advance, master, selected
        self.box = ink_box(path)


def fill_beyond(painter, path, ink, red, rects):
    """A glyph's ink in its color, and in red inside the given rectangles (the device's clipped parts)."""
    QtCore, QtGui = _qt()
    painter.fillPath(path, QtGui.QBrush(ink))
    for rect in rects:
        painter.save()
        painter.setClipRect(rect)
        painter.fillPath(path, QtGui.QBrush(red))
        painter.restore()


def diagram_pixmap(width, height, lines, pictures, line, upm, win, colors, font):
    """The Vertical metrics diagram: the pictures (the tallest and deepest glyphs) on one baseline, the
    metrics' lines across, labeled at the right edge (suggested ones dashed in the highlight color),
    the ink past winAscent and winDescent in red, the line's height as a bracket at the left."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(width, height)
    text, highlight = colors["text"], colors["highlight"]
    metrics = QtGui.QFontMetrics(font)
    line_height = metrics.height()
    small = QtGui.QFont(font)
    bold = QtGui.QFont(font)
    bold.setBold(True)
    labels = [l.label() for l in lines]
    label_room = max([text_width(font, t) for t in labels] + [40]) + 16
    share_text = u"%d%%" % round_units((line[0] - line[1] + line[2]) * 100.0 / upm) if line else u""
    bracket_room = (max(text_width(bold, share_text), text_width(font, u"of the em")) + 22) if line else 8
    caption_room = 2 * line_height + 6
    pictures = [p for p in pictures if p.box is not None]
    values = [l.value for l in lines] + [0]
    if line:
        values += [line[0] + line[2], line[1]]
    for p in pictures:
        values += [p.box[1], p.box[3]]
    high, low = max(values), min(values)
    span = max(high - low, upm * 0.5)
    high, low = high + span * 0.04, low - span * 0.04
    names = [min(text_width(font, p.name), DIAGRAM_NAME_MIN) + 8 for p in pictures]  # (longer ones elided)
    room_x = width - label_room - bracket_room - 16
    room_y = height - caption_room - line_height - 10  # (a line at the top for the legend)
    if names and sum(names) + 14.0 * (len(names) - 1) > room_x:
        # the names alone wider than the room (a narrow window): each gets its share, elided, rather
        # than no scale fitting at all and the diagram coming out empty
        share = max(8.0, (room_x - 14.0 * (len(names) - 1)) / len(names))
        names = [min(n, share) for n in names]

    def slots(scale):
        """Each picture's width in pixels: its ink, or its name when wider; and the gap between."""
        gap = max(14.0, DIAGRAM_GAP * upm * scale)
        return [max((p.box[2] - p.box[0]) * scale, n) for p, n in zip(pictures, names)], gap

    def fits(scale):
        widths, gap = slots(scale)
        return sum(widths) + gap * max(0, len(widths) - 1) <= room_x

    scale = room_y / float(high - low)
    if not fits(scale):  # the largest scale at which the pictures fit across
        small_scale, large_scale = 0.0, scale
        for _ in range(30):
            middle = (small_scale + large_scale) / 2.0
            small_scale, large_scale = (middle, large_scale) if fits(middle) else (small_scale, middle)
        scale = small_scale
    if scale <= 0:
        return pixmap
    widths, gap = slots(scale)
    row = sum(widths) + gap * max(0, len(widths) - 1)
    spare = room_y - (high - low) * scale  # (the pictures and their names centered up and down)
    y0 = line_height + 6 + spare / 2.0 + high * scale  # the baseline, in pixels
    caption_top = y0 - low * scale + 4

    def y_of(value):
        return y0 - value * scale

    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setFont(font)
        left_edge, right_edge = bracket_room, width - label_room
        # the glyphs, centered between the bracket and the labels
        x = left_edge + (right_edge - left_edge - row) / 2.0
        red = qcolor(RED)
        clip_rects = []
        if win:
            clip_rects = [QtCore.QRectF(0, -1, width, y_of(win[0]) + 1),
                          QtCore.QRectF(0, y_of(-win[1]), width, height - y_of(-win[1]) + 1)]
        placed = []
        for p, slot in zip(pictures, widths):
            offset = (slot / scale - (p.box[2] - p.box[0])) / 2.0 - p.box[0]  # the ink centered in its slot
            painter.save()
            painter.translate(x + offset * scale, y0)
            painter.scale(scale, -scale)
            ink = highlight if p.selected else faded(text, 215)
            if clip_rects:
                inverse = []
                for rect in clip_rects:  # the clip rectangles in the glyph's own coordinates
                    top_units = (y0 - rect.top()) / scale
                    bottom_units = (y0 - rect.bottom()) / scale
                    inverse.append(QtCore.QRectF(-10.0 * upm, bottom_units, 20.0 * upm, top_units - bottom_units))
                fill_beyond(painter, p.path, ink, red, inverse)
            else:
                painter.fillPath(p.path, QtGui.QBrush(ink))
            painter.restore()
            placed.append((x, slot, p))
            x += slot + gap
        if any(l.kind == "suggested" for l in lines):  # the legend
            painter.setPen(QtGui.QPen(highlight, 1.4, QtCore.Qt.DashLine))
            painter.drawLine(QtCore.QPointF(right_edge + 10, line_height / 2.0 + 2),
                             QtCore.QPointF(right_edge + 34, line_height / 2.0 + 2))
            painter.setPen(highlight)
            painter.drawText(QtCore.QRectF(right_edge + 40, 2, label_room - 40, line_height),
                             int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter), u"suggested")
        # the lines and their labels
        wanted = [y_of(l.value) for l in lines]
        at = spread_labels(wanted, line_height, low=line_height * 1.5 + 4, high=height - line_height / 2.0)
        for l, y, label_y, label in zip(lines, wanted, at, labels):
            suggested = l.kind == "suggested"
            if suggested:
                pen = QtGui.QPen(highlight, 1.4, QtCore.Qt.DashLine)
            else:
                pen = QtGui.QPen(qcolor(GRAY, 200 if l.value == 0 else LINE_ALPHA + 20))
                pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(left_edge - 6, y), QtCore.QPointF(right_edge + 2, y))
            if abs(label_y - y) > 1.5:
                painter.drawLine(QtCore.QPointF(right_edge + 2, y), QtCore.QPointF(right_edge + 8, label_y))
            painter.setPen(highlight if suggested else text)
            painter.drawText(QtCore.QRectF(right_edge + 10, label_y - line_height / 2.0, label_room - 10, line_height),
                             int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter), label)
        # the line's height, as a bracket
        if line:
            top, bottom = y_of(line[0] + line[2]), y_of(line[1])
            bx = bracket_room - 10
            pen = QtGui.QPen(text)
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(bx, top), QtCore.QPointF(bx, bottom))
            painter.drawLine(QtCore.QPointF(bx, top), QtCore.QPointF(bx + 5, top))
            painter.drawLine(QtCore.QPointF(bx, bottom), QtCore.QPointF(bx + 5, bottom))
            middle = (top + bottom) / 2.0
            painter.setFont(bold)
            painter.drawText(QtCore.QRectF(0, middle - line_height, bx - 4, line_height),
                             int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter), share_text)
            painter.setFont(small)
            painter.drawText(QtCore.QRectF(0, middle, bx - 4, line_height),
                             int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter), u"of the em")
        # the glyphs' names under them
        painter.setFont(font)
        for x_at, slot, p in placed:
            column = slot + gap - 4
            rect = QtCore.QRectF(x_at + slot / 2.0 - column / 2.0, caption_top, column, line_height)
            painter.setPen(highlight if p.selected else text)
            painter.drawText(rect, int(QtCore.Qt.AlignCenter), elided(font, p.name, int(column)))
            if p.master:
                painter.setPen(faded(text, QUIET_ALPHA))
                painter.drawText(rect.translated(0, line_height), int(QtCore.Qt.AlignCenter),
                                 elided(font, p.master, int(column)))
    finally:
        painter.end()
    return pixmap


def clip_tile(picture, win, over, colors, font, size=CLIP_TILE):
    """A clipped glyph: its ink fitted with winAscent and winDescent as lines, the part Windows cuts
    off in red, its name and the overflow in units under it."""
    QtCore, QtGui = _qt()
    width, height = size
    pixmap = new_pixmap(width, height)
    line_height = QtGui.QFontMetrics(font).height()
    room = height - 2 * line_height - 8
    box = picture.box
    if box is None:
        return pixmap
    high, low = max(box[3], win[0]), min(box[1], -win[1])
    scale = min((room - 4) / float(max(1.0, high - low)), (width - 10) / float(max(1.0, box[2] - box[0])))
    y0 = 4 + (room - 4 - (high - low) * scale) / 2.0 + high * scale
    x0 = width / 2.0 - (box[0] + box[2]) / 2.0 * scale
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        pen = QtGui.QPen(qcolor(GRAY, LINE_ALPHA + 40))
        painter.setPen(pen)
        for value in (win[0], -win[1], 0):
            y = y0 - value * scale
            painter.drawLine(QtCore.QPointF(2, y), QtCore.QPointF(width - 2, y))
        painter.save()
        painter.translate(x0, y0)
        painter.scale(scale, -scale)
        span = 10.0 * max(1.0, high - low)
        fill_beyond(painter, picture.path, faded(colors["text"], 215), qcolor(RED),
                    [QtCore.QRectF(-span, win[0], 2 * span, span), QtCore.QRectF(-span, -win[1] - span, 2 * span, span)])
        painter.restore()
        painter.setFont(font)
        painter.setPen(colors["text"])
        painter.drawText(QtCore.QRectF(0, room + 2, width, line_height), int(QtCore.Qt.AlignCenter),
                         elided(font, picture.name, width - 4))
        bold = QtGui.QFont(font)
        bold.setBold(True)
        painter.setFont(bold)
        painter.setPen(qcolor(RED))
        painter.drawText(QtCore.QRectF(0, room + 2 + line_height, width, line_height), int(QtCore.Qt.AlignCenter), over)
    finally:
        painter.end()
    return pixmap


class Side(object):
    """One half of the Masters comparison: a master's caption, the glyph's path and outline there (None:
    no layer), its anchors [(name, x, y)], the contours to highlight (numbered from 1), and the anchors
    to highlight."""

    def __init__(self, caption, path=None, outline=None, anchors=(), contours=(), marked_anchors=(), numbered=False):
        self.caption, self.path, self.outline = caption, path, outline
        self.anchors, self.contours, self.marked_anchors = list(anchors), set(contours), set(marked_anchors)
        self.numbered = numbered  # every contour's number at its start point
        self.box = ink_box(path)


def comparison_pixmap(width, height, sides, colors, font):
    """The Masters comparison: a glyph in two masters side by side at one scale, the contour at fault
    in the highlight color with its nodes numbered (its start point a ring), anchors as small crosses
    with their names; a master with no layer as a dashed empty frame."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(width, height)
    text, highlight = colors["text"], colors["highlight"]
    line_height = QtGui.QFontMetrics(font).height()
    small = QtGui.QFont(font)
    try:
        small.setPixelSize(max(9, int(line_height * 0.72)))
    except Exception:
        pass
    boxes = [s.box for s in sides if s.box is not None]
    points = [(x, y) for s in sides for _, x, y in s.anchors]
    xs = [b[0] for b in boxes] + [b[2] for b in boxes] + [p[0] for p in points]
    ys = [b[1] for b in boxes] + [b[3] for b in boxes] + [p[1] for p in points]
    if not xs:
        xs, ys = [0, 500], [0, 700]
    left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)
    half = width / float(max(1, len(sides)))
    room_y = height - line_height - 30
    scale = min((half - 40) / float(max(1.0, right - left)), room_y / float(max(1.0, top - bottom)))
    if scale <= 0:
        return pixmap
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for index, side in enumerate(sides):
            x0 = index * half + half / 2.0 - (left + right) / 2.0 * scale
            y0 = 12 + room_y / 2.0 + (bottom + top) / 2.0 * scale
            painter.setFont(font)
            painter.setPen(text)
            painter.drawText(QtCore.QRectF(index * half, height - line_height - 6, half, line_height),
                             int(QtCore.Qt.AlignCenter), elided(font, side.caption, int(half) - 8))
            if side.path is None:
                pen = QtGui.QPen(qcolor(GRAY, 200), 1.2, QtCore.Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(QtGui.QBrush())
                frame = QtCore.QRectF(x0 + left * scale, y0 - top * scale, (right - left) * scale, (top - bottom) * scale)
                painter.drawRect(frame)
                painter.setPen(faded(text, QUIET_ALPHA))
                painter.drawText(frame, int(QtCore.Qt.AlignCenter), u"No layer")
                continue
            painter.setPen(QtGui.QPen(qcolor(GRAY, LINE_ALPHA)))
            painter.drawLine(QtCore.QPointF(index * half + 8, y0), QtCore.QPointF((index + 1) * half - 8, y0))
            painter.save()
            painter.translate(x0, y0)
            painter.scale(scale, -scale)
            painter.fillPath(side.path, QtGui.QBrush(faded(text, 110 if side.contours else 200)))
            painter.restore()

            def at(x, y):
                return QtCore.QPointF(x0 + x * scale, y0 - y * scale)

            contours = side.outline.contours if side.outline is not None else []
            for number, contour in enumerate(contours, 1):
                nodes = contour.nodes
                if not nodes:
                    continue
                marked = number in side.contours
                if marked:
                    pen = QtGui.QPen(highlight)
                    pen.setWidthF(2.0)
                    painter.setPen(pen)
                    painter.setBrush(QtGui.QBrush())
                    for k in range(len(nodes) if contour.closed else len(nodes) - 1):
                        a, b = nodes[k], nodes[(k + 1) % len(nodes)]
                        painter.drawLine(at(a[0], a[1]), at(b[0], b[1]))
                    painter.setFont(small)
                    for k, node in enumerate(nodes):
                        point = at(node[0], node[1])
                        on = u"%s" % node[2] not in (u"off", u"offcurve")
                        painter.setPen(QtGui.QPen(highlight, 1.2))
                        painter.setBrush(QtGui.QBrush(highlight if on else colors["base"]))
                        r = 3.0 if on else 2.5
                        painter.drawEllipse(point, r, r)
                        if k == 0:
                            painter.setBrush(QtGui.QBrush())
                            painter.drawEllipse(point, 6.5, 6.5)
                        painter.setPen(text)
                        painter.drawText(QtCore.QRectF(point.x() + 5, point.y() - line_height, 40, line_height),
                                         int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom), u"%d" % (k + 1))
                elif side.numbered:
                    painter.setFont(small)
                    painter.setPen(text)
                    point = at(nodes[0][0], nodes[0][1])
                    painter.drawText(QtCore.QRectF(point.x() + 4, point.y() - line_height, 40, line_height),
                                     int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom), u"%d" % number)
            painter.setFont(small)
            for name, x, y in side.anchors:
                point = at(x, y)
                color = highlight if name in side.marked_anchors else faded(text, 200)
                pen = QtGui.QPen(color)
                pen.setWidthF(1.4)
                painter.setPen(pen)
                painter.drawLine(QtCore.QPointF(point.x() - 5, point.y() - 5), QtCore.QPointF(point.x() + 5, point.y() + 5))
                painter.drawLine(QtCore.QPointF(point.x() - 5, point.y() + 5), QtCore.QPointF(point.x() + 5, point.y() - 5))
                painter.drawText(QtCore.QRectF(point.x() + 7, point.y(), 120, line_height),
                                 int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop), name)
        if len(sides) > 1:
            painter.setPen(QtGui.QPen(qcolor(GRAY, LINE_ALPHA)))
            for index in range(1, len(sides)):
                painter.drawLine(QtCore.QPointF(index * half, 8), QtCore.QPointF(index * half, height - 8))
    finally:
        painter.end()
    return pixmap


def anchor_points(layer):
    """[(name, x, y)] of a layer's anchors (flPinPoint.point, as Diacritics reads it)."""
    found = []
    try:
        for anchor in layer.anchors:
            try:
                point = anchor.point
                found.append((u"%s" % anchor.name, float(point.x()), float(point.y())))
            except Exception:
                pass
    except Exception:
        pass
    return found


def row_languages_text(row, shown=4):
    """The languages column of a row of "Add these": the languages it completes, or, when it completes
    none on its own, the languages needing it with what else they miss."""
    if row.completing:
        names = [r.language.name for r in row.completing]
    else:
        names = [u"%s (with %s)" % (r.language.name, u" ".join(shown_text(i) for i in needs(r) if i not in row.items))
                 for r in row.needing]
    text = u", ".join(names[:shown])
    if len(names) > shown:
        text += u", +%d" % (len(names) - shown)
    return text


def row_tip(row, buildable=False):
    lines = [u"%s: %s" % (code_label(item), short_name(item)) for item in row.items]
    if row.auxiliary():
        lines.append(u"Auxiliary: these languages use it in loan words and names, and miss nothing else.")
    if row.completing:
        lines.append(u"Completes on its own: %s." % u", ".join(r.language.label() for r in row.completing))
    others = [r for r in row.needing if r not in row.completing]
    if others:
        lines.append(u"Needed, with other characters, by: %s." % u", ".join(
            u"%s (with %s)" % (r.language.label(), u" ".join(shown_text(i) for i in needs(r) if i not in row.items))
            for r in others))
    parts = [item for item in row.items if any(item in r.parts for r in row.needing)]
    if parts:
        lines.append(u"The font has the letter and marks of %s, but no anchors joining them." % u" ".join(parts))
    if buildable:
        lines.append(u"Diacritics can build it from the font's letters and marks.")
    return u"\n".join(lines)


def language_matches(r, text):
    """Whether a language's name, autonym, or code holds the text searched (any case)."""
    if not text:
        return True
    text = text.lower()
    language = r.language
    return any(text in (u"%s" % value).lower() for value in (language.name, language.autonym or u"", language.iso))


def coverage_tip(r):
    lines = [u"%s, %s script: %s (Hyperglot: %s, %s)." % (r.language.label(), r.language.script,
                                                           STATE_LABELS[r.level].lower(), r.language.status,
                                                           r.language.validity)]
    if r.missing:
        lines.append(u"Base characters missing: %s" % u" ".join(r.missing))
    if r.marks_missing:
        lines.append(u"Marks missing: %s" % u" ".join(DOTTED_CIRCLE + m for m in r.marks_missing))
    if r.auxiliary_missing:
        lines.append(u"Auxiliary characters missing (loan words, names): %s" % u" ".join(r.auxiliary_missing))
    if r.composed:
        lines.append(u"Composed from the font's letters and marks (its anchors): %s" % u" ".join(c for c, _ in r.composed))
    if r.parts:
        lines.append(u"The font has the letters and marks of %s, but no anchors joining them" % u" ".join(r.parts))
    return u"\n".join(lines)


def language_note(r):
    """The second column of a language: its missing characters when within reach, "composed" when
    covered thanks to the anchors."""
    if r.level == "nearly":
        return compact_missing(r)
    if r.level == "covered" and r.composed:
        return u"composed"
    return u""


class Tab(object):
    """A page: its settings row, a line, its status, then what it shows."""

    def __init__(self, ak, QtGui):
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.settings = QtGui.QHBoxLayout()
        self.layout.addLayout(self.settings)
        self.line = ak.separator()
        self.layout.addWidget(self.line)
        self.status = ak.status_label()
        self.layout.addWidget(self.status)
        self.findings = []


class FontCheckDialog(object):
    def __init__(self):
        self.failed = None
        self.dialog = None
        try:
            self.build()
        except Exception as exc:  # a half-built dialog crashed FontLab: never raised from here
            self.failed = exc

    # -- building ------------------------------------------------------------

    def build(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        self.package = self.master = None
        self.busy = self.filling = False
        self.seen_history, self.stale = None, set(TABS)
        self.diacritics = None  # Diacritics' module, loaded when first needed
        self.buildable = None  # the characters Diacritics can build, asked once per check
        self.scripts, self.results, self.rows, self.language_rows = [], [], [], []
        self.checked = set()  # characters checked in "Add these"
        self.script_filter = None
        self.coverage_focus = "add"
        self.metric_values, self.extents_found, self.suggestions, self.notes = None, [], [], []
        self.check_rows, self.clipped = [], []
        self.capitals, self.letters = True, None
        self.problems, self.glyph_names, self.compare_masters = [], [], []
        self.fixable_names = set()  # the glyphs listed with problems Fix sets right
        self.fix_unchecked, self.fix_basis = set(), None  # rows unchecked by hand (for this font and reference)
        self.pictures = {}  # (kind, key): an icon drawn (the characters to add)
        self.drawing_failed = False
        self.filters, self.redraws = [], {}
        main = ak.AutoKerningDialog.main_window()
        dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        self.dialog = dialog
        dialog.setWindowTitle("FreeLab Font Check")
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.font_label = ak.status_label()
        layout.addWidget(self.font_label)
        self.log = ak.Log()
        # A tab bar over plain pages: a QTabWidget's themed page drew its buttons with light frames in dark mode
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.redraw_timer = QtCore.QTimer()
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(80)
        self.redraw_timer.connect("timeout()", self.redraw_now)
        self.build_coverage(QtCore, QtGui)
        self.build_metrics(QtCore, QtGui)
        self.build_masters(QtCore, QtGui)
        for tab, label in ((self.coverage, "Coverage"), (self.metrics, "Vertical metrics"), (self.masters, "Masters")):
            self.tabs.addTab(label)
            self.pages.addWidget(tab.widget)
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens a <i>Glyph</i> window: a language's missing characters (FontLab's "
                                              u"placeholders) and the ones it composes, the checked characters, or the "
                                              u"selected glyph.")
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.glyph_window_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.close_button.connect("clicked()", dialog.close)
        ak.add_tools_button(dialog, "Font Check", getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        try:  # the check boxes drawn plain to see in either palette (the lists' pictures stay unmapped)
            fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            self.check_watcher = fc.watch_check_boxes(dialog, [self.add_tree, self.glyph_tree])
        except Exception:
            self.check_watcher = None
        self.read_font()
        self.history_timer = ak.watch_history(self)
        self.flagging = [ak.flag_menu(self.glyph_tree, self, self.selected_glyphs, self.row_glyph),
                         ak.flag_menu(self.clipped_list, self, self.selected_glyphs)]
        self.update_buttons()

    def tree(self, columns, icon=None, header=True, grid=True):
        """A list: no root decoration, no horizontal scrolling (long texts elided, whole in tooltips),
        pictures of the given size (its viewport left alone by dark mode: they are drawn in the
        dialog's colors)."""
        QtCore, QtGui = _qt()
        tree = QtGui.QTreeWidget()
        tree.setColumnCount(len(columns))
        tree.setHeaderLabels(list(columns))
        tree.setRootIsDecorated(False)
        try:
            tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        except Exception:
            pass
        if not header:
            try:
                tree.setHeaderHidden(True)
            except Exception:
                pass
        if icon is not None:
            tree.setIconSize(QtCore.QSize(icon[0], icon[1]))
            tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # (the whole list: on its viewport alone, dark mode
            # mapped the list and its pictures with it; its scroll bars are FreeLab's flat ones)
        if grid:
            self.ak.grid_lines(tree)
        return tree

    @staticmethod
    def heading(text):
        QtCore, QtGui = _qt()
        label = QtGui.QLabel(text)
        font = QtGui.QFont(_prop(label, "font"))
        font.setBold(True)
        label.setFont(font)
        return label

    def use_list_font(self, tree):
        """The languages list (its rows, section headings, and column headings) in FreeLab Languages, at
        LIST_SCALE times the dialog's size: rows grow with it, and a section heading's bold font is made
        from the list's (section_row). Without the font file, or if Qt refuses it, the list keeps its
        family and is still enlarged; tooltips keep Qt's own font. This never raises."""
        try:
            QtCore, QtGui = _qt()
            font = QtGui.QFont(_prop(tree, "font"))
            family = register_list_font(QtCore, QtGui)
            if family:
                font.setFamily(family)
            unit, size = scaled_size(font.pointSizeF(), font.pixelSize())
            if unit == "point":
                font.setPointSizeF(size)
            elif unit == "pixel":
                font.setPixelSize(size)
            tree.setFont(font)
        except Exception:
            pass

    def picture_label(self, minimum):
        """A label showing a picture drawn to its size (redrawn as it is resized)."""
        QtCore, QtGui = _qt()
        label = QtGui.QLabel()
        label.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
        label.setAlignment(QtCore.Qt.AlignCenter)
        try:
            label.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)  # (its picture never sizes it)
        except Exception:
            pass
        label.setMinimumSize(minimum[0], minimum[1])
        return label

    def watch_resize(self, widget, key):
        """The picture of widget drawn again (redraw_now's key) a moment after it is resized."""
        QtCore, QtGui = _qt()
        owner = self

        class Resized(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize
                        owner.redraws[key] = True
                        owner.redraw_timer.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        found = Resized()
        widget.installEventFilter(found)
        self.filters.append(found)

    def redraw_now(self):
        keys, self.redraws = list(self.redraws), {}
        for key in keys:
            try:
                if key == "diagram":
                    self.draw_diagram()
                elif key == "comparison":
                    self.draw_comparison()
            except Exception:
                pass  # a timer's handler must not raise

    def build_coverage(self, QtCore, QtGui):
        ak = self.ak
        tab = self.coverage = Tab(ak, QtGui)
        tab.settings.addWidget(QtGui.QLabel("Within reach: missing at most"))
        self.nearly = QtGui.QSpinBox()
        self.nearly.setRange(0, 30)
        self.nearly.setValue(NEARLY_MISSING)
        self.nearly.setSuffix(" characters")
        self.nearly.setWhatsThis(u"A language missing at most this many of its base characters (and marks), or "
                                 u"only auxiliary ones, is within reach: its missing characters are listed at the left.")
        tab.settings.addWidget(self.nearly)
        self.historical = QtGui.QCheckBox("Historical languages")
        self.historical.setWhatsThis(u"Lists languages no one speaks natively any more (Latin, Ancient Greek) too.")
        tab.settings.addWidget(self.historical)
        self.composing = QtGui.QCheckBox("Count letters its anchors compose")
        self.composing.setChecked(True)
        self.composing.setWhatsThis(u"A letter with a mark the font lacks as one character counts as there when the "
                                    u"font has the letter and the combining mark, and the letter has an anchor the "
                                    u"mark attaches to (top and _top): applications compose it. Unchecked, only the "
                                    u"font's own characters count.")
        tab.settings.addWidget(self.composing)
        self.coverage_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(self.coverage_button)
        tab.settings.addStretch(1)

        self.script_tree = self.tree(("Script", "", "Languages"), icon=BAR_SIZE, header=False, grid=False)
        self.script_tree.setStyleSheet(SCRIPT_SHEET)
        self.script_tree.setWhatsThis(u"The scripts the font has, the most languages covered first: each bar shows "
                                      u"its languages covered (the highlight color), within reach (amber), and missed "
                                      u"(gray). Click a script to see only its languages below.")
        tab.layout.addWidget(self.script_tree)
        absent = QtGui.QHBoxLayout()
        self.absent_label = QtGui.QLabel(u"")
        self.show_absent = QtGui.QCheckBox("Show them")
        self.show_absent.setWhatsThis(u"Lists the scripts the font has none of (fewer than five of their letters) too.")
        absent.addWidget(self.absent_label)
        absent.addWidget(self.show_absent)
        absent.addStretch(1)
        tab.layout.addLayout(absent)

        halves = QtGui.QSplitter(QtCore.Qt.Horizontal)
        left = QtGui.QWidget()
        box = QtGui.QVBoxLayout(left)
        box.setContentsMargins(0, 0, 4, 0)
        box.addWidget(self.heading(u"Add these to reach more languages"))
        self.gain_label = ak.status_label()
        box.addWidget(self.gain_label)
        row = QtGui.QHBoxLayout()
        self.check_buttons, self.check_slots = {}, []
        tips = {"all": u"Checks every character listed below (the checks of other scripts' rows are kept).",
                "none": u"Unchecks every character, those of other scripts' rows too.",
                "buildable": u"Checks the characters listed that <i>Diacritics</i> can build from the font's letters "
                             u"and marks, and unchecks the others."}
        def clicked(key):
            return lambda: self.set_checks(key)  # (no argument PythonQt could fill)

        for key, label in CHECK_BUTTONS:
            button = QtGui.QPushButton(label)
            button.setWhatsThis(tips[key])
            slot = clicked(key)
            button.connect("clicked()", slot)
            self.check_slots.append(slot)
            row.addWidget(button)
            self.check_buttons[key] = button
        row.addStretch(1)
        box.addLayout(row)
        self.add_tree = self.tree(("", "Character", "", "Languages"), icon=CHAR_ICON)
        self.add_tree.setWhatsThis(u"The characters the languages within reach miss, the ones completing the most "
                                   u"languages on their own first (+N: the languages it completes alone; a capital and "
                                   u"its small letter together). Check some: the line above says how many languages "
                                   u"they complete together.")
        box.addWidget(self.add_tree, 1)
        row = QtGui.QHBoxLayout()
        self.diacritics_button = QtGui.QPushButton("Build with Diacritics")
        self.diacritics_button.setWhatsThis(u"Opens <i>Diacritics</i> on the checked characters it can build from the font's "
                                            u"letters and marks (you check them there before anything is made).")
        self.copy_chars_button = QtGui.QPushButton("Copy characters")
        self.copy_chars_button.setWhatsThis(u"Copies the checked characters (or the selected row's) as text.")
        row.addWidget(self.diacritics_button)
        row.addWidget(self.copy_chars_button)
        row.addStretch(1)
        box.addLayout(row)
        right = QtGui.QWidget()
        box = QtGui.QVBoxLayout(right)
        box.setContentsMargins(4, 0, 0, 0)
        box.addWidget(self.heading(u"Languages"))
        row = QtGui.QHBoxLayout()
        self.search = QtGui.QLineEdit()
        try:
            self.search.setPlaceholderText(u"Find a language")
        except Exception:
            pass
        self.search.setWhatsThis(u"Shows the languages whose name, autonym, or code holds this text.")
        self.level_filter = QtGui.QComboBox()
        for _, label in LANGUAGE_FILTERS:
            self.level_filter.addItem(label)
        self.level_filter.setWhatsThis(u"Shows every language, or only the covered, within reach, or missed ones.")
        row.addWidget(self.search, 1)
        row.addWidget(self.level_filter)
        box.addLayout(row)
        self.language_tree = self.tree(("Language", "Missing"), icon=(DOT_SIZE, DOT_SIZE))
        self.use_list_font(self.language_tree)
        self.language_tree.setWhatsThis(u"A dot per language: covered (the highlight color), within reach (amber), "
                                        u"missed (gray); within reach, the characters it misses. Selecting one marks "
                                        u"them in the list at the left; double-click shows them in a <i>Glyph</i> window.")
        box.addWidget(self.language_tree, 1)
        halves.addWidget(left)
        halves.addWidget(right)
        halves.setStretchFactor(0, 1)
        halves.setStretchFactor(1, 1)
        tab.layout.addWidget(halves, 1)

        self.coverage_button.connect("clicked()", self.check_coverage)
        self.nearly.connect("valueChanged(int)", lambda value: self.nearly.setSuffix(
            u" character" if value == 1 else u" characters"))
        self.script_tree.connect("itemSelectionChanged()", self.script_selected)
        self.show_absent.connect("toggled(bool)", lambda on: self.refill_coverage())
        self.add_tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.add_checked())
        self.add_tree.connect("itemSelectionChanged()", lambda: self.coverage_selected("add"))
        self.add_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        self.language_tree.connect("itemSelectionChanged()", lambda: self.coverage_selected("languages"))
        self.language_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)",
                                   lambda item, column: self.show_in_glyph_window())
        self.search.connect("textChanged(QString)", lambda text: self.fill_languages())
        self.level_filter.connect("currentIndexChanged(int)", lambda index: self.fill_languages())
        self.diacritics_button.connect("clicked()", self.build_with_diacritics)
        self.copy_chars_button.connect("clicked()", self.copy_characters)

    def build_metrics(self, QtCore, QtGui):
        ak = self.ak
        tab = self.metrics = Tab(ak, QtGui)
        self.metrics_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(QtGui.QLabel(u"Every glyph measured in every master."))
        tab.settings.addStretch(1)
        tab.settings.addWidget(self.metrics_button)
        self.diagram = self.picture_label((320, 200))
        self.diagram.setWhatsThis(u"The font's tallest and deepest glyphs, by ink across its masters, on one "
                                  u"baseline, with its line metrics as lines (equal ones as one line): what Windows "
                                  u"clips (past winAscent or winDescent) in red, the line's height at the left as a "
                                  u"share of the em, the suggested values dashed in the highlight color. A glyph "
                                  u"selected among the clipped ones is drawn in it too.")
        tab.layout.addWidget(self.diagram, 1)
        body = QtGui.QHBoxLayout()
        side = QtGui.QVBoxLayout()
        self.values_tree = self.tree(("Value", "Now", "Suggested"))
        self.values_tree.setWhatsThis(u"The font's line metrics now and as suggested (in bold where they differ).")
        side.addWidget(self.values_tree)
        row = QtGui.QHBoxLayout()
        self.write_button = QtGui.QPushButton("Write suggested values")
        self.write_button.setWhatsThis(u"Writes the suggested values that differ into the font's info: the typo, hhea, "
                                       u"and win values and <i>Use Typo Metrics</i>, for the whole font, then checks again; "
                                       u"the log lists each value, old and new, and <i>Put back old values</i> undoes it "
                                       u"(FontLab's <i>Edit &gt; Undo</i> does not cover the font info). "
                                       u"The masters' ascender, descender, x-height, and cap height (the metrics FontLab "
                                       u"draws with) are not changed.")
        self.copy_button = QtGui.QPushButton("Copy suggested values")
        self.copy_button.setWhatsThis(u"Copies the suggested values as text.")
        self.font_info_button = QtGui.QPushButton("Open Font Info")
        self.font_info_button.setWhatsThis(u"Opens FontLab's <i>Font Info</i>, where these values are set.")
        row.addWidget(self.write_button)
        self.put_back_button = QtGui.QPushButton("Put back old values")
        self.put_back_button.setWhatsThis(u"Puts the font info back as it was before <i>Write suggested values</i>: "
                                          u"FontLab's <i>Edit &gt; Undo</i> does not cover the font info.")
        self.put_back_button.setEnabled(False)
        row.addWidget(self.put_back_button)
        row.addWidget(self.copy_button)
        row.addWidget(self.font_info_button)
        row.addStretch(1)
        side.addLayout(row)
        row = QtGui.QHBoxLayout()
        self.mode_share = QtGui.QRadioButton("Line spacing")
        self.mode_share.setChecked(True)
        self.mode_share.setWhatsThis(u"Suggests your font's line spacing (ascender plus descender) at the share of the em "
                                     u"set, capitals centered in it, clear of <i>\N{LATIN CAPITAL LETTER A WITH GRAVE}</i> "
                                     u"and the deepest descender, line gaps of 0, hhea equal to typo, win at the ink's "
                                     u"extremes, and <i>Use Typo Metrics</i> on.")
        self.share = QtGui.QSpinBox()
        self.share.setRange(100, 200)
        self.share.setValue(int(LINE_SHARE * 100))
        self.share.setSuffix("% of the em")
        self.share.setWhatsThis(u"The line spacing to suggest (ascender plus descender) as a share of the em: Google "
                                u"Fonts asks 120% to 130% for Latin, Greek, and Cyrillic; tall scripts may need more.")
        row.addWidget(self.mode_share)
        row.addWidget(self.share)
        row.addStretch(1)
        side.addLayout(row)
        self.mode_keep = QtGui.QRadioButton("Keep the font's current line spacing")
        self.mode_keep.setToolTip(u"For an update of a font already released: documents set in it do not reflow.")
        self.mode_keep.setWhatsThis(u"For an update of a font already released: keeps its current line spacing, so "
                                    u"documents set in it do not reflow (as Google Fonts asks). The typo values stay as "
                                    u"they are when <i>Use Typo Metrics</i> is on, or else take the old win values, which "
                                    u"Windows spaced lines by; the win values grow to the ink and <i>Use Typo Metrics</i> "
                                    u"is turned on.")
        side.addWidget(self.mode_keep)
        side.addStretch(1)
        body.addLayout(side)
        side = QtGui.QVBoxLayout()
        side.addWidget(self.heading(u"Checks"))
        self.checks_tree = self.tree(("Check",), icon=(STATE_SIZE, STATE_SIZE), header=False, grid=False)
        self.checks_tree.setWhatsThis(u"What Google Fonts' vertical metrics guidance asks, one line each: a warning "
                                      u"where the font differs, a check where it does as asked. Click a line about "
                                      u"glyphs to select them among the clipped glyphs.")
        side.addWidget(self.checks_tree, 1)
        body.addLayout(side, 1)
        tab.layout.addLayout(body)
        row = QtGui.QHBoxLayout()
        self.clipped_label = self.heading(u"Clipped on Windows")
        row.addWidget(self.clipped_label)
        row.addStretch(1)
        self.clip_master_label = QtGui.QLabel(u"Master")
        self.clip_master = QtGui.QComboBox()
        self.clip_master.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.clip_master.setWhatsThis(u"The clipped glyphs of every master (each in its worst one), or of one master.")
        row.addWidget(self.clip_master_label)
        row.addWidget(self.clip_master)
        tab.layout.addLayout(row)
        self.clipped_list = QtGui.QListWidget()
        try:
            self.clipped_list.setViewMode(QtGui.QListView.IconMode)
            self.clipped_list.setMovement(QtGui.QListView.Static)
            self.clipped_list.setResizeMode(QtGui.QListView.Adjust)
            self.clipped_list.setWrapping(True)
            self.clipped_list.setSpacing(2)
        except Exception:
            pass
        self.clipped_list.setIconSize(QtCore.QSize(CLIP_TILE[0], CLIP_TILE[1]))
        self.clipped_list.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.clipped_list.setProperty(ak.LEAVE_ALONE_PROP, True)
        self.clipped_list.setFixedHeight(CLIP_TILE[1] + 28)
        self.clipped_list.setWhatsThis(u"The glyphs Windows clips, the worst first: the part cut off in red, by how "
                                       u"many units under it. Double-click one to open it in a <i>Glyph</i> window; right-click "
                                       u"to flag it.")
        tab.layout.addWidget(self.clipped_list)

        self.metrics_button.connect("clicked()", self.check_vertical)
        self.mode_share.connect("toggled(bool)", lambda on: self.mode_changed())
        self.share.connect("valueChanged(int)", lambda value: self.suggest())
        self.write_button.connect("clicked()", self.write_suggestions)
        self.put_back_button.connect("clicked()", self.put_back_values)
        self.copy_button.connect("clicked()", self.copy_suggestions)
        self.font_info_button.connect("clicked()", self.open_font_info)
        self.checks_tree.connect("itemSelectionChanged()", self.check_selected)
        self.clip_master.connect("currentIndexChanged(int)", lambda index: self.fill_clipped())
        self.clipped_list.connect("itemSelectionChanged()", self.clip_selected)
        self.clipped_list.connect("itemDoubleClicked(QListWidgetItem*)", lambda item: self.show_in_glyph_window())
        self.watch_resize(self.diagram, "diagram")

    def build_masters(self, QtCore, QtGui):
        ak = self.ak
        tab = self.masters = Tab(ak, QtGui)
        tab.settings.addWidget(QtGui.QLabel("Compare every master with"))
        self.reference = QtGui.QComboBox()
        self.reference.setWhatsThis(u"The master each other master is compared with.")
        tab.settings.addWidget(self.reference)
        self.masters_button = QtGui.QPushButton("Compare masters")
        tab.settings.addWidget(self.masters_button)
        tab.settings.addStretch(1)
        chips = QtGui.QHBoxLayout()
        self.chips = []
        for kind, label in PROBLEM_CHIPS:
            chip = QtGui.QToolButton()
            chip.setCheckable(True)
            chip.setChecked(True)
            chip.setText(label)
            chip.setProperty(ak.LEAVE_ALONE_PROP, True)  # (drawn by CHIP_SHEET in the palette's colors)
            chip.setStyleSheet(CHIP_SHEET)
            chip.setWhatsThis(u"Shows or hides this kind of problem in the list (the count: glyphs with it). A glyph "
                              u"left with no kind shown is hidden.")
            chip.setVisible(False)
            chip.connect("toggled(bool)", lambda on: self.fill_glyphs())
            chips.addWidget(chip)
            self.chips.append((kind, label, chip))
        chips.addStretch(1)
        tab.layout.addLayout(chips)
        halves = QtGui.QSplitter(QtCore.Qt.Horizontal)
        left = QtGui.QWidget()
        box = QtGui.QVBoxLayout(left)
        box.setContentsMargins(0, 0, 4, 0)
        self.glyph_tree = self.tree(("Glyph", "Masters", "Fix"), icon=(THUMB_SIZE, THUMB_SIZE))
        self.glyph_tree.setWhatsThis(u"The glyphs that keep the masters from interpolating, the worst first, with a "
                                     u"mark per master in order: a ring for the master compared with, red where the "
                                     u"glyph cannot interpolate (a dashed square: no layer), amber where it "
                                     u"interpolates oddly (direction, start point, components, anchors), a faint dot "
                                     u"where all is well. <i>Fix</i> says whether Font Check can set its problems "
                                     u"right (checked to start) or they need the designer. Right-click to flag a glyph.")
        box.addWidget(self.glyph_tree, 1)
        row = QtGui.QHBoxLayout()
        self.fix_checked_button = QtGui.QPushButton("Fix checked")
        self.fix_checked_button.setWhatsThis(u"Sets right, in the checked glyphs, what needs no designer: the contours' "
                                             u"order, directions, start points, and the components' order, in every "
                                             u"master but the one compared with (which never changes). One step of "
                                             u"<i>Edit &gt; Undo</i>; the masters are compared again and the log says "
                                             u"what was fixed. Contour and node counts, node types, missing layers, and "
                                             u"anchors are left to you.")
        self.fix_this_button = QtGui.QPushButton("Fix this")
        self.fix_this_button.setWhatsThis(u"Sets right what needs no designer in the selected glyph, as <i>Fix checked</i> "
                                          u"does.")
        row.addWidget(self.fix_checked_button)
        row.addWidget(self.fix_this_button)
        row.addStretch(1)
        box.addLayout(row)
        halves.addWidget(left)
        right = QtGui.QWidget()
        box = QtGui.QVBoxLayout(right)
        box.setContentsMargins(4, 0, 0, 0)
        self.comparison = self.picture_label((320, 260))
        self.comparison.setWhatsThis(u"The selected glyph in the master compared with and in the master chosen below, "
                                     u"at one scale: the contour at fault in the highlight color, its nodes numbered "
                                     u"(its start point ringed), anchors as crosses (those one master lacks in the "
                                     u"highlight color). A master with no layer shows a dashed empty frame.")
        box.addWidget(self.comparison, 1)
        self.problem_label = ak.status_label()
        box.addWidget(self.problem_label)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(u"Beside it"))
        self.compare_master = QtGui.QComboBox()
        self.compare_master.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.compare_master.setWhatsThis(u"The master drawn beside the one compared with (those with problems say "
                                         u"how many).")
        row.addWidget(self.compare_master)
        row.addStretch(1)
        box.addLayout(row)
        halves.addWidget(right)
        halves.setStretchFactor(0, 2)
        halves.setStretchFactor(1, 3)
        tab.layout.addWidget(halves, 1)
        self.masters_button.connect("clicked()", self.check_masters)
        self.glyph_tree.connect("itemSelectionChanged()", self.glyph_selected)
        self.glyph_tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.fix_checks_changed())
        self.fix_checked_button.connect("clicked()", self.fix_checked)
        self.fix_this_button.connect("clicked()", self.fix_selected)
        self.glyph_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        self.compare_master.connect("currentIndexChanged(int)", lambda index: self.draw_comparison())
        self.watch_resize(self.comparison, "comparison")

    # -- the font ------------------------------------------------------------

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = workspace.currentPackage
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def read_font(self):
        """The current font and master; False (and said so) when no font is open."""
        package = self.current_font()
        if package is not None and self.package is not None and self.ak.font_key(package) != self.ak.font_key(self.package):
            self.stale = set(TABS)
        self.package = package
        self.master = package.master if package is not None else None
        if package is None:
            self.font_label.setText(u"No font is open. Open one, then click %s." % self.ak.i("Check"))
            self.update_buttons()
            return False
        b = self.ak.b
        masters = self.master_names()
        self.font_label.setText(u"%s, master %s (%s)." % (b(package.tfn), b(self.master), b(counted(len(masters), u"master"))))
        self.tabs.setTabEnabled(TABS.index("masters"), len(masters) > 1)
        self.tabs.setTabToolTip(TABS.index("masters"), u"" if len(masters) > 1 else u"This font has one master: nothing to compare.")
        if [self.reference.itemText(index) for index in range(self.reference.count)] != masters:
            self.reference.clear()
            for name in masters:
                self.reference.addItem(name)
            default = self.default_master(masters)
            if default in masters:
                self.reference.setCurrentIndex(masters.index(default))
        return True

    def master_names(self):
        try:
            return [u"%s" % name for name in self.package.masters]
        except Exception:
            return [self.master] if self.master else []

    def default_master(self, masters):
        try:
            name = u"%s" % self.package.defaultMaster
            if name in masters:
                return name
        except Exception:
            pass
        return masters[0] if masters else None

    def glyphs(self):
        """[(name, code points)] of the font's glyphs."""
        found = []
        for fg in self.package.fgPackage.glyphs:
            found.append((u"%s" % fg.name, glyph_codes(fg)))
        return found

    def layer(self, name, master):
        glyph = self.package.findName(name)
        if glyph is None or glyph.isNull:
            return None
        layer = glyph.getLayerByName(master)
        if layer is not None and getattr(layer, "isNull", False):
            return None
        return layer

    def picture(self, name, master, selected=False, caption_master=False):
        """A Picture of a glyph in a master, or None (no such layer)."""
        layer = self.layer(name, master)
        if layer is None:
            return None
        return Picture(name, self.ak.layer_path(layer), layer.advanceWidth, master if caption_master else u"", selected)

    def colors(self):
        QtCore, QtGui = _qt()
        palette = _prop(self.dialog, "palette")
        return {"text": palette.color(QtGui.QPalette.WindowText), "base": palette.color(QtGui.QPalette.Window),
                "highlight": palette.color(QtGui.QPalette.Highlight)}

    def icon(self, draw, *args):
        """A QIcon of a picture drawn (an empty one, and a warning once per window, when drawing failed:
        the list is filled all the same)."""
        QtCore, QtGui = _qt()
        try:
            return QtGui.QIcon(draw(*args))
        except Exception as exc:
            if not self.drawing_failed:
                self.drawing_failed = True
                self.log.add(u"A picture could not be drawn: %s" % self.ak.html(exc), "warning")
            return QtGui.QIcon()

    def progress(self, tab, done, total, what):
        QtCore, QtGui = _qt()
        tab.status.setText(u"%s %s of %s\N{HORIZONTAL ELLIPSIS}" % (what, self.ak.b(done), self.ak.b(total)))
        QtGui.QApplication.processEvents()

    # -- the tabs, buttons, and the History ---------------------------------

    def tab_of(self, key):
        return getattr(self, key)

    def current_key(self):
        return TABS[self.tabs.currentIndex]

    def check(self, key):
        {"coverage": self.check_coverage, "metrics": self.check_vertical, "masters": self.check_masters}[key]()

    def checked_now(self, key):
        self.stale.discard(key)
        self.seen_history = self.ak.history_mark(self.package)
        self.update_buttons()

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the view shown is checked again, the others when shown."""
        self.stale = set(TABS)
        self.buildable = None
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): checked again.")
        self.check(self.current_key())

    def switch_page(self, index):
        QtCore, QtGui = _qt()
        self.pages.setCurrentIndex(index)
        self.update_buttons()
        key = TABS[index]
        if key in self.stale and self.package is not None:
            QtCore.QTimer.singleShot(0, lambda: self.check(key))  # checked as it is first shown
        else:
            self.redraws.update({"diagram": True, "comparison": True})  # (its size may have changed while hidden)
            self.redraw_timer.start()

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        ak = self.ak
        chosen = self.chosen_characters() if self.package is not None else []
        buildable = self.buildable_checked() if chosen else []
        ak.enable(self.diacritics_button, bool(buildable))
        self.diacritics_button.setText(u"Build %s with Diacritics" % counted(len(buildable), u"letter") if buildable
                                       else u"Build with Diacritics")
        self.diacritics_button.setToolTip(
            u"" if buildable else u"Check characters or select a row first." if not chosen else
            u"<i>Diacritics</i> cannot build %s from the font's letters and marks." % (
                u"this character" if len(chosen) == 1 else u"any of these characters"))
        targets = self.check_targets() if self.package is not None else {}
        can = any(item in (self.buildable or set()) for row in self.rows for item in row.items)
        idle = {"all": u"Every character listed is checked." if self.rows else u"No character is listed.",
                "none": u"No character is checked.",
                "buildable": u"Only what <i>Diacritics</i> can build is checked." if can
                else u"<i>Diacritics</i> can build none of the characters listed."}
        for key, button in self.check_buttons.items():
            on = targets.get(key) is not None
            ak.enable(button, on)
            button.setToolTip(u"" if on else idle[key])
        ak.enable(self.copy_chars_button, bool(chosen))
        self.copy_chars_button.setText(u"Copy %s" % counted(len(chosen), u"character") if chosen else u"Copy characters")
        ak.enable(self.copy_button, bool(self.suggestions))
        writes = metric_writes(self.suggestions) if self.package is not None else []
        ak.enable(self.write_button, bool(writes) and not self.busy)
        self.write_button.setText(u"Write %s" % counted(len(writes), u"suggested value") if writes
                                  else u"Write suggested values")
        self.write_button.setToolTip(u"" if writes else u"The font's values are as suggested." if self.suggestions
                                     else u"Check the vertical metrics first.")
        fixing = self.checked_fix_glyphs() if self.package is not None else []
        ak.enable(self.fix_checked_button, bool(fixing) and not self.busy)
        self.fix_checked_button.setText(u"Fix %s" % counted(len(fixing), u"checked glyph") if fixing else u"Fix checked")
        self.fix_checked_button.setToolTip(u"" if fixing else u"Check glyphs Font Check can fix (their row says so)."
                                           if self.fixable_names else u"No glyph listed has a problem Font Check can fix.")
        name = self.selected_glyph() if self.package is not None else None
        ak.enable(self.fix_this_button, name in self.fixable_names and not self.busy)
        self.fix_this_button.setToolTip(u"" if name in self.fixable_names else u"Select a glyph first." if name is None
                                        else u"This glyph's problems need the designer.")
        ak.enable(self.font_info_button, self.package is not None)
        ak.enable(self.glyph_window_button, self.package is not None and bool(self.glyph_window_text()))

    def start(self, tab):
        """A view about to be checked; False when it cannot be (busy, no font)."""
        if self.busy or not self.read_font():
            return False
        tab.findings = []
        tab.status.setText(u"")
        return True

    @staticmethod
    def item(texts, data, tip=u""):
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        item.setData(0, QtCore.Qt.UserRole, data)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if tip:
            for column in range(len(texts)):
                item.setToolTip(column, sentence(tip))
        return item

    @staticmethod
    def data_of(item, default=-1):
        QtCore, QtGui = _qt()
        if item is None:
            return default
        data = item.data(0, QtCore.Qt.UserRole)
        return default if data is None else data

    @staticmethod
    def index_of(item):
        try:
            return int(FontCheckDialog.data_of(item))
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def top_items(tree):
        return [tree.topLevelItem(i) for i in range(_prop(tree, "topLevelItemCount"))]

    @staticmethod
    def selected_item(view):
        try:
            items = view.selectedItems()
        except Exception:
            return None
        return items[0] if items else None

    def bold(self, tree):
        QtCore, QtGui = _qt()
        font = QtGui.QFont(_prop(tree, "font"))
        font.setBold(True)
        return font

    @staticmethod
    def rows_height(tree, rows, header=False):
        """Pixels for a list to show rows rows (and its header) without scrolling."""
        QtCore, QtGui = _qt()
        line = QtGui.QFontMetrics(_prop(tree, "font")).height() + 6
        try:
            found = int(tree.sizeHintForRow(0))
            line = found if found > 0 else line
        except Exception:
            pass
        extra = line + 2 if header else 0
        return int(rows * line + extra + 6)

    def fit_columns(self, tree, widths):
        """Each column but the last sized to its contents, at most the given width (None: as is); the
        last takes the rest, its text elided."""
        for column, most in enumerate(widths):
            tree.resizeColumnToContents(column)
            if most is not None and tree.columnWidth(column) > most:
                tree.setColumnWidth(column, most)

    # -- Coverage ------------------------------------------------------------

    def font_characters(self):
        """The font's FontCharacters: its code points, and its anchors in the current master (read as
        letters and marks are asked about)."""
        master = self.master
        codes = set()
        names = {}
        for name, glyph_codes_ in self.glyphs():
            for code in glyph_codes_:
                codes.add(code)
                names.setdefault(code, name)
        anchors = {}

        def anchors_of(code):
            if code not in anchors:
                layer = self.layer(names[code], master) if code in names else None
                anchors[code] = set(anchor_names(layer)) if layer is not None else set()
            return anchors[code]

        def attaches(base, mark):
            marks = set(name[1:] for name in anchors_of(mark) if name.startswith(u"_"))
            return bool(marks & anchors_of(base))

        return FontCharacters(codes, attaches if self.composing.checked else None)

    def check_coverage(self):
        tab = self.coverage
        if not self.start(tab):
            return
        QtCore, QtGui = _qt()
        ak, b = self.ak, self.ak.b
        self.busy = True
        try:
            tab.status.setText(u"Reading the font\N{HORIZONTAL ELLIPSIS}")
            QtGui.QApplication.processEvents()
            languages = load_languages()
            font = self.font_characters()
            scripts = coverage(languages, font, self.nearly.value, self.historical.checked)
        except Exception as exc:
            tab.status.setText(u"")
            self.log.add(ak.html(exc), "error")
            return
        finally:
            self.busy = False
        self.scripts = scripts
        self.results = [r for s in scripts for r in s.results]
        tab.findings = self.results
        self.buildable = None
        self.checked = set()
        self.pictures = {}  # (drawn again: the palette may have changed)
        if self.script_filter not in [s.script for s in scripts if s.present]:
            self.script_filter = None
        self.buildable_set()  # (Diacritics asked once: the rows' tooltips say what it can build)
        self.refill_coverage()
        present = [s for s in scripts if s.present]
        covered = sum(s.count("covered") for s in present)
        nearly = sum(s.count("nearly") for s in present)
        text = u"%s covered and %s within reach (missing at most %s), of the languages of %s the font has." % (
            b(counted(covered, u"language")), b(nearly), counted(self.nearly.value, u"base character"),
            b(counted(len(present), u"script")))
        composed = sum(1 for s in present for r in s.results if r.composed and r.level != "missed")
        if composed:
            text += u" %s count%s letters its anchors compose." % (b(counted(composed, u"language")),
                                                                    u"s" if composed == 1 else u"")
        tab.status.setText(text)
        self.checked_now("coverage")

    def shown_scripts(self):
        """The scripts listed: those the font has, and the others when asked."""
        return [s for s in self.scripts if s.present or self.show_absent.checked]

    def filtered_scripts(self):
        """The scripts whose languages are shown: the one clicked, or all those listed."""
        return [s for s in self.shown_scripts() if self.script_filter is None or s.script == self.script_filter]

    def refill_coverage(self):
        self.fill_scripts()
        self.fill_add()
        self.fill_languages()
        self.update_gain()
        self.update_buttons()

    def fill_scripts(self):
        QtCore, QtGui = _qt()
        tree, colors = self.script_tree, self.colors()
        shown = self.shown_scripts()
        absent = [s for s in self.scripts if not s.present]
        self.filling = True
        try:
            tree.clear()
            counts = [sum(s.count(level) for s in shown) for level in ("covered", "nearly", "missed")]
            all_row = self.item((u"All scripts", u"", u"%d of %s" % (counts[0], counted(sum(counts), u"language")) +
                                 (u" \N{MIDDLE DOT} %d within reach" % counts[1] if counts[1] else u"")), u"")
            all_row.setIcon(1, self.icon(bar_pixmap, counts, colors))
            tree.addTopLevelItem(all_row)
            selected = all_row
            for s in shown:
                counts = [s.count("covered"), s.count("nearly"), s.count("missed")]
                item = self.item((s.script, u"", script_text(s)), s.script,
                                 u"%s: %d covered, %d within reach, %d missed." % (s.script, counts[0], counts[1], counts[2]))
                item.setIcon(1, self.icon(bar_pixmap, counts, colors))
                tree.addTopLevelItem(item)
                if s.script == self.script_filter:
                    selected = item
            tree.setCurrentItem(selected)
            self.fit_columns(tree, (220, BAR_SIZE[0] + 12))
            tree.setFixedHeight(self.rows_height(tree, min(len(shown) + 1, 6)))
        finally:
            self.filling = False
        if absent:
            self.absent_label.setText(u"%s the font has none of." % counted(len(absent), u"other script"))
        self.absent_label.setVisible(bool(absent))
        self.show_absent.setVisible(bool(absent))

    def script_selected(self):
        if self.filling:
            return
        item = self.selected_item(self.script_tree)
        if item is None:
            return
        key = u"%s" % self.data_of(item, u"")
        self.script_filter = key or None
        self.fill_add()
        self.fill_languages()
        self.update_gain()
        self.update_buttons()

    def fill_add(self):
        QtCore, QtGui = _qt()
        tree, colors = self.add_tree, self.colors()
        results = [r for s in self.filtered_scripts() for r in s.results]
        self.rows = add_rows(results)
        font = _prop(self.dialog, "font")
        buildable = self.buildable or set()
        self.filling = True
        tree.setUpdatesEnabled(False)
        try:
            tree.clear()
            bold = self.bold(tree)
            quiet = QtGui.QBrush(faded(colors["text"], QUIET_ALPHA))
            for index, row in enumerate(self.rows):
                name = short_name(row.items[-1]) if len(row.items) > 1 else short_name(row.items[0])
                plus = u"+%d" % len(row.completing)
                item = self.item((u"", u"%s\n%s" % (name, u" ".join(code_label(i) for i in row.items)), plus,
                                  row_languages_text(row)), index,
                                 row_tip(row, any(i in buildable for i in row.items)))
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if set(row.items) <= self.checked else QtCore.Qt.Unchecked)
                key = ("char", row.text())
                if key not in self.pictures:
                    self.pictures[key] = self.icon(character_pixmap, row.text(), colors["text"], font)
                item.setIcon(0, self.pictures[key])
                item.setFont(2, bold)
                item.setTextAlignment(2, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                if not row.completing:
                    item.setForeground(2, quiet)
                    item.setForeground(3, quiet)
                tree.addTopLevelItem(item)
            self.fit_columns(tree, (None, COLUMN_MAX, None))
        finally:
            tree.setUpdatesEnabled(True)
            self.filling = False

    def add_checked(self):
        """The checks of "Add these" read again (a click on one)."""
        QtCore, QtGui = _qt()
        if self.filling:
            return
        for item in self.top_items(self.add_tree):
            index = self.index_of(item)
            if not 0 <= index < len(self.rows):
                continue
            items = set(self.rows[index].items)
            if item.checkState(0) == QtCore.Qt.Checked:
                self.checked |= items
            else:
                self.checked -= items
        self.update_gain()
        self.update_buttons()

    def check_targets(self):
        """checks_for of the rows listed (Diacritics asked once per check, as the rows' tooltips are)."""
        buildable = self.buildable_set() if self.package is not None and self.rows else set()
        return checks_for(self.rows, self.checked, buildable)

    def set_checks(self, key):
        """A check button clicked: the checks of "Add these" set as it says, in place (the rows,
        their marks, and the selection kept)."""
        QtCore, QtGui = _qt()
        target = self.check_targets().get(key)
        if target is None or self.filling:
            return
        self.checked = set(target)
        self.filling = True  # (itemChanged must not read the checks back meanwhile)
        try:
            for item in self.top_items(self.add_tree):
                index = self.index_of(item)
                if 0 <= index < len(self.rows):
                    item.setCheckState(0, QtCore.Qt.Checked if set(self.rows[index].items) <= self.checked
                                       else QtCore.Qt.Unchecked)
        finally:
            self.filling = False
        self.update_gain()
        self.update_buttons()

    def update_gain(self):
        gained = languages_gained(self.results, self.checked)
        if not self.rows and not self.checked:
            self.gain_label.setText(u"No language within reach here: nothing to add." if self.results else u"")
        else:
            self.gain_label.setText(gain_text(len(self.checked), gained, self.ak.b))
        tip = u"\n".join(u"%s (%s)" % (r.language.label(), r.language.script) for r in gained[:40])
        self.gain_label.setToolTip(sentence(tip))

    def selected_row(self):
        item = self.selected_item(self.add_tree)
        index = self.index_of(item)
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def selected_language(self):
        item = self.selected_item(self.language_tree)
        index = self.index_of(item)
        return self.language_rows[index] if 0 <= index < len(self.language_rows) else None

    def fill_languages(self):
        QtCore, QtGui = _qt()
        tree, colors = self.language_tree, self.colors()
        level = LANGUAGE_FILTERS[max(0, self.level_filter.currentIndex)][0]
        text = u"%s" % (_prop(self.search, "text") or u"")
        scripts = self.filtered_scripts()
        dots = dict((key, self.icon(dot_pixmap, level_color(key, colors))) for key in ("covered", "nearly", "missed"))
        self.language_rows = []
        self.filling = True
        tree.setUpdatesEnabled(False)
        try:
            tree.clear()
            for s in scripts:
                rows = [r for r in s.results if (level is None or r.level == level) and language_matches(r, text)]
                if not rows:
                    continue
                if len(scripts) > 1:
                    heading = self.item((u"%s (%d)" % (s.script, len(rows)), u""), -1)
                    heading.setFlags(QtCore.Qt.ItemIsEnabled)
                    tree.addTopLevelItem(heading)
                    heading.setFirstColumnSpanned(True)
                    self.ak.section_row(heading, tree)
                for r in rows:
                    item = self.item((r.language.label(), language_note(r)), len(self.language_rows), coverage_tip(r))
                    item.setIcon(0, dots[r.level])
                    if r.level == "covered" and r.composed:
                        item.setForeground(1, QtGui.QBrush(faded(colors["text"], QUIET_ALPHA)))
                    tree.addTopLevelItem(item)
                    self.language_rows.append(r)
            self.fit_columns(tree, (int(COLUMN_MAX * 1.4 * LIST_SCALE),))  # (its larger text)
        finally:
            tree.setUpdatesEnabled(True)
            self.filling = False
        self.mark_needed(None)

    def coverage_selected(self, which):
        if self.filling:
            return
        self.coverage_focus = which
        if which == "languages":
            self.mark_needed(self.selected_language())
        self.update_buttons()

    def mark_needed(self, r):
        """The characters a language needs, marked in "Add these" (bold, tinted; the first scrolled to);
        none when r is None."""
        QtCore, QtGui = _qt()
        needed = set(needs(r)) if r is not None else set()
        tree = self.add_tree
        tint = QtGui.QBrush(faded(self.colors()["highlight"], 70))
        plain, bold = QtGui.QFont(_prop(tree, "font")), self.bold(tree)
        first = None
        blocked = tree.signalsBlocked()
        tree.blockSignals(True)  # (a tint is no check: itemChanged must not hear it)
        try:
            for item in self.top_items(tree):
                index = self.index_of(item)
                if not 0 <= index < len(self.rows):
                    continue
                marked = bool(needed & set(self.rows[index].items))
                for column in (1, 3):
                    item.setFont(column, bold if marked else plain)
                for column in range(4):
                    item.setBackground(column, tint if marked else QtGui.QBrush())
                if marked and first is None:
                    first = item
        finally:
            tree.blockSignals(blocked)
        tree.viewport().update()
        if first is not None:
            tree.scrollToItem(first)

    def diacritics_module(self):
        if self.diacritics is None:
            self.diacritics = self.ak.load_sibling(DIACRITICS_FILE, DIACRITICS_MODULE)
        return self.diacritics

    def buildable_set(self):
        """The missing characters of the languages within reach that Diacritics' own planning can build
        from the font's letters and marks (asked once per check)."""
        if self.buildable is not None:
            return self.buildable
        found = set()
        try:
            dm = self.diacritics_module()
            ranges = [pair for _, _, pairs in dm.SETS for pair in pairs]
            candidates = buildable_candidates([r for r in self.results if r.level == "nearly"], ranges)
            if candidates:
                fgs = list(self.package.fgPackage.glyphs)
                font = dm.Font([u"%s" % g.name for g in fgs], [(u"%s" % g.name, g.unicode) for g in fgs])
                found = set(recipe.char for recipe in dm.plan(font, candidates) if not recipe.missing)
        except Exception as exc:
            self.log.add(u"<i>Diacritics</i> could not be asked: %s" % self.ak.html(exc), "warning")
        self.buildable = found
        return found

    def chosen_characters(self):
        """The checked characters, or, with none checked, the selected row's."""
        if self.checked:
            return sorted(self.checked, key=code_points)
        row = self.selected_row()
        return sorted(row.items, key=code_points) if row is not None else []

    def buildable_checked(self):
        """The chosen characters Diacritics can build."""
        if self.package is None:
            return []
        can = self.buildable_set()
        return [c for c in self.chosen_characters() if c in can]

    def build_with_diacritics(self):
        QtCore, QtGui = _qt()
        chars = self.buildable_checked()
        if not chars:
            return
        if not self.checked:  # built from the selected row: its check follows
            for item in self.add_tree.selectedItems():
                if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                    item.setCheckState(0, QtCore.Qt.Checked)
        i = self.ak.i  # (letters named in a message are in italics)
        try:
            dm = self.diacritics_module()
            try:
                dm.main(characters=chars)  # a Diacritics that lists the letters given only
                self.log.add(u"<i>Diacritics</i> lists %s: check them there, then build." % i(u" ".join(chars)), "done")
            except TypeError:
                dm.main()  # (a Diacritics that takes no letters lists every one it can build)
                self.log.add(u"<i>Diacritics</i> lists every letter with diacritics it can build, %s among them." % i(
                    u" ".join(chars)), "done")
        except Exception as exc:
            self.log.add(u"<i>Diacritics</i> did not open: %s" % self.ak.html(exc), "error")

    def copy_characters(self):
        QtCore, QtGui = _qt()
        chars = self.chosen_characters()
        if not chars:
            return
        try:
            QtGui.QApplication.clipboard().setText(u" ".join(chars))
            self.log.add(u"Copied %s." % self.ak.i(u" ".join(chars)), "done")
        except Exception as exc:
            self.log.add(u"Could not copy: %s" % self.ak.html(exc), "error")

    # -- Vertical metrics ---------------------------------------------------------

    def extents(self, tab):
        """[Extent] of every glyph with ink, in every master."""
        found = []
        glyphs = self.glyphs()
        masters = self.master_names()
        total = len(glyphs) * len(masters)
        done = 0
        for name, codes in glyphs:
            glyph = self.package.findName(name)
            if glyph is None or glyph.isNull:
                continue
            for master in masters:
                done += 1
                if done % PROGRESS_EVERY == 0:
                    self.progress(tab, done, total, u"Measuring glyph")
                layer = glyph.getLayerByName(master)
                if layer is None:
                    continue
                path = self.ak.layer_path(layer)
                if path.isEmpty():
                    continue
                rect = path.boundingRect()  # font units grow upward: the rect's bottom is the ink's top
                found.append(Extent(name, codes[0] if codes else None, master, rect.top(), rect.bottom()))
        return found

    def check_vertical(self):
        tab = self.metrics
        if not self.start(tab):
            return
        ak, b = self.ak, self.ak.b
        self.busy = True
        try:
            m = read_metrics(self.package)
            if not m.upm:
                m.upm = float(self.package.upm)
            extents = self.extents(tab)
            codes = set(code for name, glyph_codes_ in self.glyphs() for code in glyph_codes_)
            capitals = has_capitals(codes)
            findings = check_metrics(m, extents, capitals)
        except Exception as exc:
            tab.status.setText(u"")
            self.log.add(ak.html(exc), "error")
            return
        finally:
            self.busy = False
        self.metric_values, self.extents_found, self.capitals = m, extents, capitals
        self.letters = None if capitals else other_letters(codes)
        tab.findings = findings
        self.check_rows = check_lines(m, extents, findings, capitals)
        self.suggest()
        self.fill_checks()
        self.fill_clip_masters()
        self.fill_clipped()
        clipped = len(clipped_glyphs(m, extents))
        warnings = sum(1 for line in self.check_rows if line.state == "warn")
        text = u"%s clipped on Windows, %s, across %s." % (
            b(counted(clipped, u"glyph")), b(counted(warnings, u"warning")), b(counted(len(self.master_names()), u"master")))
        writes = metric_writes(self.suggestions)
        if writes:
            text += u" %s %s the font: %s writes %s (%s takes %s back)." % (
                b(counted(len(writes), u"suggested value")), u"differs from" if len(writes) == 1 else u"differ from",
                ak.i("Write suggested values"), u"it" if len(writes) == 1 else u"them", ak.i("Put back old values"),
                u"it" if len(writes) == 1 else u"them")
        else:
            text += u" The font's values are as suggested."
        tab.status.setText(text)
        self.checked_now("metrics")

    def mode(self):
        return "share" if self.mode_share.checked else "keep"

    def mode_changed(self):
        """The strategy chosen: the share of the em asked for only to suggest a line spacing."""
        self.ak.enable(self.share, self.mode() == "share")
        self.suggest()

    def suggest(self):
        """The suggested values for the strategy chosen: the table and the diagram drawn again."""
        m = self.metric_values
        if m is None:
            return
        try:
            self.suggestions, self.notes = suggest_metrics(m, self.extents_found, self.capitals, self.mode(),
                                                           self.share.value / 100.0, self.letters)
        except Exception as exc:
            self.log.add(self.ak.html(exc), "error")
            return
        self.fill_values()
        self.draw_diagram()
        self.update_buttons()

    def fill_values(self):
        QtCore, QtGui = _qt()
        tree = self.values_tree
        tree.clear()
        bold = self.bold(tree)
        notes = u"\n".join(self.notes)
        for s in self.suggestions:
            item = self.item((s.label, now_text(s), suggestion_text(s)), -1,
                             u"%s: %s now, %s suggested.\n%s" % (s.label, now_text(s), suggestion_text(s), notes))
            for column in (1, 2):
                item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
            if s.changes():
                item.setFont(2, bold)
            tree.addTopLevelItem(item)
        tree.setFixedHeight(self.rows_height(tree, len(self.suggestions), header=True))
        plain = _prop(tree, "font")
        widths = [max([text_width(bold, u"%s" % row[column]) for row in
                       [(s.label, now_text(s), suggestion_text(s)) for s in self.suggestions]] +
                      [text_width(plain, (u"Value", u"Now", u"Suggested")[column])]) + 16 for column in range(3)]
        for column, width in enumerate(widths):
            tree.setColumnWidth(column, width)
        tree.setFixedWidth(sum(widths) + 8)

    def draw_diagram(self):
        m = self.metric_values
        if m is None or self.package is None:
            self.diagram.clear()
            return
        try:
            tallest, deepest = extreme_glyphs(self.extents_found)
            several = len(self.master_names()) > 1
            pictures = [self.picture(e.name, e.master, caption_master=several) for e in tallest + deepest]
            chosen = self.selected_clip()
            if chosen is not None and (chosen.extent.name, chosen.extent.master) not in \
                    [(e.name, e.master) for e in tallest + deepest]:
                pictures.append(self.picture(chosen.extent.name, chosen.extent.master, True, several))
            elif chosen is not None:
                for p, e in zip(pictures, tallest + deepest):
                    if p is not None and (e.name, e.master) == (chosen.extent.name, chosen.extent.master):
                        p.selected = True
            pictures = [p for p in pictures if p is not None]
            win = (m.win_ascent, m.win_descent) if m.win_ascent and m.win_descent else None
            width = int(_prop(self.diagram, "width") or 0) or 600
            height = int(_prop(self.diagram, "height") or 0) or 500
            pixmap = diagram_pixmap(width, height, diagram_lines(m, self.suggestions), pictures, line_values(m),
                                    float(m.upm or 1000), win, self.colors(), _prop(self.dialog, "font"))
            self.diagram.setPixmap(pixmap)
        except Exception as exc:
            self.diagram.clear()
            self.log.add(u"The diagram could not be drawn: %s" % self.ak.html(exc), "warning")

    def fill_checks(self):
        QtCore, QtGui = _qt()
        tree, colors = self.checks_tree, self.colors()
        icons = dict((state, self.icon(state_pixmap, state, colors)) for state in ("ok", "warn", "info"))
        quiet = QtGui.QBrush(faded(colors["text"], QUIET_ALPHA))
        self.filling = True
        try:
            tree.clear()
            for index, line in enumerate(self.check_rows):
                item = self.item((sentence(line.text),), index, line.tip)
                item.setIcon(0, icons[line.state])
                if line.state == "ok":
                    item.setForeground(0, quiet)
                tree.addTopLevelItem(item)
        finally:
            self.filling = False

    def check_selected(self):
        """A check about glyphs: those glyphs selected among the clipped ones."""
        if self.filling:
            return
        index = self.index_of(self.selected_item(self.checks_tree))
        if not 0 <= index < len(self.check_rows) or not self.check_rows[index].glyphs:
            return
        names = set(self.check_rows[index].glyphs)
        if self.clip_master.currentIndex > 0:
            self.clip_master.setCurrentIndex(0)  # every master's
        first = None
        view = self.clipped_list
        view.clearSelection()
        for row in range(_prop(view, "count")):
            item = view.item(row)
            at = self.index_of_list(item)
            if 0 <= at < len(self.clipped) and self.clipped[at].extent.name in names:
                item.setSelected(True)
                if first is None:
                    first = item
        if first is not None:
            view.scrollToItem(first)

    def fill_clip_masters(self):
        masters = self.master_names()
        wanted = [u"All masters"] + masters
        if [self.clip_master.itemText(i) for i in range(self.clip_master.count)] != wanted:
            self.filling = True
            try:
                self.clip_master.clear()
                for name in wanted:
                    self.clip_master.addItem(name)
            finally:
                self.filling = False
        several = len(masters) > 1
        self.clip_master.setVisible(several)
        self.clip_master_label.setVisible(several)

    def fill_clipped(self):
        QtCore, QtGui = _qt()
        if self.filling:
            return
        m, view = self.metric_values, self.clipped_list
        view.clear()
        if m is None:
            return
        index = self.clip_master.currentIndex
        masters = self.master_names()
        master = masters[index - 1] if 0 < index <= len(masters) else None
        self.clipped = clipped_glyphs(m, self.extents_found, master)
        colors, font = self.colors(), _prop(self.dialog, "font")
        several = len(masters) > 1
        for at, c in enumerate(self.clipped):
            picture = self.picture(c.extent.name, c.extent.master)
            if picture is None:
                continue
            over = u"+%d" % c.worst()
            item = QtGui.QListWidgetItem(self.icon(clip_tile, picture, (m.win_ascent, m.win_descent), over, colors, font),
                                         u"")
            item.setData(QtCore.Qt.UserRole, at)
            sides = []
            if c.above:
                sides.append(u"%d above winAscent" % c.above)
            if c.below:
                sides.append(u"%d below winDescent" % c.below)
            item.setToolTip(u"%s%s: %s." % (c.extent.name, u" in %s" % c.extent.master if several else u"",
                                            u" and ".join(sides)))
            view.addItem(item)
        self.clipped_label.setText(u"Clipped on Windows: %s" % counted(len(self.clipped), u"glyph")
                                   if self.clipped else u"Clipped on Windows: none")
        view.setVisible(bool(self.clipped))
        several = several and bool(clipped_glyphs(m, self.extents_found))
        self.clip_master.setVisible(several)
        self.clip_master_label.setVisible(several)

    @staticmethod
    def index_of_list(item):
        QtCore, QtGui = _qt()
        try:
            data = item.data(QtCore.Qt.UserRole)
            return int(data) if data is not None else -1
        except (TypeError, ValueError):
            return -1

    def selected_clips(self):
        try:
            items = self.clipped_list.selectedItems()
        except Exception:
            return []
        found = []
        for item in items:
            at = self.index_of_list(item)
            if 0 <= at < len(self.clipped):
                found.append(self.clipped[at])
        return found

    def selected_clip(self):
        found = self.selected_clips()
        return found[0] if len(found) == 1 else None

    def clip_selected(self):
        self.draw_diagram()
        self.update_buttons()

    def copy_suggestions(self):
        QtCore, QtGui = _qt()
        if not self.suggestions:
            return
        text = u"\n".join(u"%s: %s" % (s.label, suggestion_text(s)) for s in self.suggestions)
        try:
            QtGui.QApplication.clipboard().setText(text)
            self.log.add(u"Copied the suggested values.", "done")
        except Exception as exc:
            self.log.add(u"Could not copy: %s" % self.ak.html(exc), "error")

    def same_font(self):
        """True while the font checked is still the current one; else the view is checked again."""
        current = self.current_font()
        if current is not None and self.package is not None and self.ak.font_key(current) == self.ak.font_key(self.package):
            return True
        self.log.add(u"The font changed since the check: checked again. Nothing was written.", "warning")
        self.stale = set(TABS)
        self.check(self.current_key())
        return False

    def write_suggestions(self):
        """The suggested values that differ written into the font info (fgPackage.info: font-wide), the old
        ones kept for Put back old values (FontLab's History does not cover the font info: found live); the
        view checked again."""
        b = self.ak.b
        if self.busy or self.package is None or self.metric_values is None or not self.same_font():
            return
        writes = metric_writes(self.suggestions)
        if not writes:
            self.log.add(u"The font's values are as suggested: nothing to write.")
            return
        fields = dict(INFO_FIELDS)
        done, failed = [], []
        self.busy = True
        try:
            info = self.package.fgPackage.info
            old = {}  # the values before, to put back (FontLab's History does not cover the font info)
            for key, field in INFO_FIELDS:
                try:
                    old[key] = getattr(info, field)
                except Exception:
                    pass
            try:
                old["use_typo"] = list(info.openTypeOS2Selection or [])
            except Exception:
                pass
            for s in writes:
                try:
                    if s.key == "use_typo":
                        info.openTypeOS2Selection = selection_with(info.openTypeOS2Selection, bool(s.value))
                    else:
                        setattr(info, fields[s.key], float(s.value))
                except Exception as exc:
                    failed.append(u"%s (%s)" % (s.label, exc))
                    continue
                done.append(s)
            info = self.package.fgPackage.info  # read again: what FontLab kept
            for s in list(done):
                try:
                    if s.key == "use_typo":
                        now = USE_TYPO_BIT in [int(bit) for bit in (info.openTypeOS2Selection or [])]
                        kept = now == bool(s.value)
                    else:
                        now = getattr(info, fields[s.key])
                        kept = now is not None and round_units(float(now)) == round_units(s.value)
                except Exception as exc:
                    now, kept = exc, False
                if not kept:
                    done.remove(s)
                    failed.append(u"%s (FontLab kept %s)" % (s.label, u"nothing" if now is None else now))
        except Exception as exc:
            failed.append(u"%s" % exc)
        finally:
            self.busy = False
        if done or failed:
            self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Font Check: vertical metrics")
        if done:
            self.put_back = (self.ak.font_key(self.package), old, [s.key for s in done])
            self.log.add(u"Wrote %s into the font info: %s. FontLab's <i>Edit &gt; Undo</i> does not take the font "
                         u"info back: <i>Put back old values</i> does." % (
                             b(counted(len(done), u"value")), self.ak.html(u"; ".join(write_text(s) for s in done))), "done")
        self.update_put_back()
        if failed:
            self.log.add(u"Not written: %s." % self.ak.html(u"; ".join(failed)), "error")
        self.check_vertical()

    def update_put_back(self):
        """Put back old values: clickable while the font written to is the one checked."""
        held = getattr(self, "put_back", None)
        self.ak.enable(self.put_back_button, bool(held) and self.package is not None
                       and self.ak.font_key(self.package) == held[0])

    def put_back_values(self):
        """The font info as it was before the last write (FontLab's History does not cover it)."""
        held = getattr(self, "put_back", None)
        if not held or self.package is None or self.ak.font_key(self.package) != held[0]:
            return
        _, old, keys = held
        fields = dict(INFO_FIELDS)
        info = self.package.fgPackage.info
        restored, failed = [], []
        for key in keys:
            if key not in old:
                failed.append(key)
                continue
            try:
                if key == "use_typo":
                    info.openTypeOS2Selection = old[key]
                elif old[key] is not None:
                    setattr(info, fields[key], float(old[key]))
                else:
                    failed.append(key)  # (an unset value cannot be unset again: left as written)
                    continue
                restored.append(key)
            except Exception as exc:
                failed.append(u"%s (%s)" % (key, exc))
        self.put_back = None
        self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Font Check: vertical metrics put back")
        b = self.ak.b
        if restored:
            self.log.add(u"Put back %s as they were." % b(counted(len(restored), u"value")), "done")
        if failed:
            self.log.add(u"Not put back: %s." % self.ak.html(u", ".join(failed)), "warning")
        self.check_vertical()
        self.update_put_back()

    def open_font_info(self):
        try:
            self.fontlab.flItems.requestFontInfoDlg()
        except Exception as exc:
            self.log.add(u"FontLab did not open <i>Font Info</i>: %s. Open it from the <i>File</i> menu." % self.ak.html(exc), "warning")

    # -- Masters -------------------------------------------------------------------

    def reference_name(self):
        masters = self.master_names()
        return self.reference.currentText if self.reference.currentIndex >= 0 else (masters[0] if masters else None)

    def check_masters(self):
        tab = self.masters
        if not self.start(tab):
            return
        ak, b = self.ak, self.ak.b
        masters = self.master_names()
        if len(masters) < 2:
            self.problems = []
            self.fill_chips()
            self.fill_glyphs()
            tab.status.setText(u"This font has one master: nothing to compare.")
            self.checked_now("masters")
            return
        reference = self.reference_name()
        basis = (ak.font_key(self.package), reference)
        if basis != self.fix_basis:  # another font or reference: every fixable row checked again
            self.fix_basis, self.fix_unchecked = basis, set()
        order = [reference] + [m for m in masters if m != reference]
        self.busy = True
        found, unread = [], []
        try:
            glyphs = self.glyphs()
            for done, (name, _) in enumerate(glyphs):
                if done % PROGRESS_EVERY == 0:
                    self.progress(tab, done, len(glyphs), u"Comparing glyph")
                glyph = self.package.findName(name)
                if glyph is None or glyph.isNull:
                    continue
                outlines = []
                for master in order:
                    layer = glyph.getLayerByName(master)
                    if layer is not None and getattr(layer, "isNull", False):
                        layer = None
                    outline = read_outline(layer) if layer is not None else None
                    if layer is not None and outline is None:
                        unread.append(name)
                    outlines.append((master, outline))
                found.extend(compare_glyph(name, outlines))
        except Exception as exc:
            tab.status.setText(u"")
            self.log.add(ak.html(exc), "error")
            return
        finally:
            self.busy = False
        self.problems = tab.findings = found
        self.fill_chips()
        self.fill_glyphs()
        names = set(f.glyph for f in found)
        if found:
            text = u"%s of the %s glyphs %s interpolate, compared with %s." % (
                b(len(names)), b(len(glyphs)), u"does not" if len(names) == 1 else u"do not", b(reference))
        else:
            text = u"The %s glyphs match in all %s masters, compared with %s: contours, nodes, start points, " \
                   u"directions, components, and anchors." % (b(len(glyphs)), b(len(masters)), b(reference))
        if unread:
            text += u" %s could not be read." % b(counted(len(unread), u"glyph layer"))
        tab.status.setText(text)
        self.checked_now("masters")

    def fill_chips(self):
        counts = dict((kind, count) for kind, _, count in problem_counts(self.problems))
        for kind, label, chip in self.chips:
            count = counts.get(kind, 0)
            chip.setText(u"%s %d" % (label, count))
            chip.setChecked(True)
            chip.setVisible(bool(count))

    def kinds_on(self):
        return set(kind for kind, _, chip in self.chips if _prop(chip, "checked"))

    def fill_glyphs(self):
        QtCore, QtGui = _qt()
        tree, colors = self.glyph_tree, self.colors()
        masters = self.master_names()
        reference = self.reference_name()
        rows = glyph_problems(self.problems, self.kinds_on())
        self.glyph_names = [name for name, _ in rows]
        self.fixable_names = set(name for name, problems in rows if fix_state(problems) != "none")
        icon = (max(THUMB_SIZE, (MARK_SIZE + 4) * len(masters)), THUMB_SIZE)
        tree.setIconSize(QtCore.QSize(icon[0], icon[1]))
        quiet = QtGui.QBrush(faded(colors["text"], QUIET_ALPHA))
        self.filling = True
        tree.setUpdatesEnabled(False)
        try:
            tree.clear()
            for name, problems in rows:
                states = master_states(problems, masters, reference)
                tip = u"\n".join(u"%s: %s" % (master, problem_sentence([f for f in problems if f.master == master]))
                                 for master in masters if any(f.master == master for f in problems))
                state = fix_state(problems)
                item = self.item((name, u"", FIX_LABELS[state]), name, tip + u"\n" + fix_sentence(problems))
                if state != "none":
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(0, QtCore.Qt.Unchecked if name in self.fix_unchecked else QtCore.Qt.Checked)
                else:
                    item.setForeground(2, quiet)
                for master in [reference] + masters:
                    layer = self.layer(name, master)
                    if layer is not None:
                        item.setIcon(0, self.icon(glyph_thumb, self.ak.layer_path(layer), colors["text"], icon[0], icon[1]))
                        break
                item.setIcon(1, self.icon(marks_pixmap, states, colors, icon))
                tree.addTopLevelItem(item)
            self.fit_columns(tree, (COLUMN_MAX, None))
        finally:
            tree.setUpdatesEnabled(True)
            self.filling = False
        items = self.top_items(tree)
        if items:
            tree.setCurrentItem(items[0])
        else:
            self.glyph_selected()

    def selected_glyph(self):
        item = self.selected_item(self.glyph_tree)
        if item is None:
            return None
        name = self.data_of(item, None)
        return u"%s" % name if name is not None and u"%s" % name in self.glyph_names else None

    def row_glyph(self, item):
        name = self.data_of(item, None)
        return [u"%s" % name] if name is not None and u"%s" % name in self.glyph_names else []

    def glyph_selected(self):
        if self.filling:
            return
        name = self.selected_glyph()
        reference = self.reference_name()
        masters = [m for m in self.master_names() if m != reference]
        problems = [f for f in self.problems if f.glyph == name] if name else []
        self.filling = True
        try:
            self.compare_master.clear()
            self.compare_masters = masters
            first = None
            for at, master in enumerate(masters):
                count = sum(1 for f in problems if f.master == master)
                self.compare_master.addItem(u"%s (%s)" % (master, counted(count, u"problem")) if count else master)
                if count and first is None:
                    first = at
            if masters:
                self.compare_master.setCurrentIndex(first or 0)
        finally:
            self.filling = False
        self.draw_comparison()
        self.update_buttons()

    def draw_comparison(self):
        if self.filling:
            return
        name = self.selected_glyph()
        if name is None or self.package is None:
            self.comparison.clear()
            self.problem_label.setText(u"")
            return
        reference = self.reference_name()
        index = self.compare_master.currentIndex
        master = self.compare_masters[index] if 0 <= index < len(self.compare_masters) else None
        problems = [f for f in self.problems if f.glyph == name and f.master == master]
        try:
            contours = set(f.contour for f in problems if f.contour)
            numbered = any(f.kind in ("contours", "order") for f in problems)
            marked = set()
            sides = []
            layers = [(reference, self.layer(name, reference))] + ([(master, self.layer(name, master))] if master else [])
            anchors = [anchor_points(layer) if layer is not None else [] for _, layer in layers]
            if any(f.kind == "anchors" for f in problems) and len(anchors) == 2:
                one, other = set(a[0] for a in anchors[0]), set(a[0] for a in anchors[1])
                marked = one ^ other
            for (who, layer), points in zip(layers, anchors):
                caption = u"%s (compared with)" % who if who == reference else who
                if layer is None:
                    sides.append(Side(caption))
                    continue
                sides.append(Side(caption, self.ak.layer_path(layer), read_outline(layer), points, contours, marked,
                                  numbered))
            width = int(_prop(self.comparison, "width") or 0) or 600
            height = int(_prop(self.comparison, "height") or 0) or 400
            self.comparison.setPixmap(comparison_pixmap(width, height, sides, self.colors(), _prop(self.dialog, "font")))
        except Exception as exc:
            self.comparison.clear()
            self.log.add(u"The comparison could not be drawn: %s" % self.ak.html(exc), "warning")
        if problems:
            self.problem_label.setText(u"%s in %s: %s %s" % (self.ak.b(name), self.ak.b(master),
                                                             self.ak.html(problem_sentence(problems)),
                                                             self.ak.html(fix_sentence(problems))))
        elif master:
            self.problem_label.setText(u"%s in %s interpolates with %s." % (self.ak.b(name), self.ak.b(master),
                                                                           self.ak.b(reference)))
        else:
            self.problem_label.setText(u"")

    def fix_checks_changed(self):
        """A row's check clicked: kept by name (the list is filled again as chips are toggled)."""
        QtCore, QtGui = _qt()
        if self.filling:
            return
        for item in self.top_items(self.glyph_tree):
            name = self.data_of(item, None)
            name = u"%s" % name if name is not None else None
            if name in self.fixable_names:
                if item.checkState(0) == QtCore.Qt.Checked:
                    self.fix_unchecked.discard(name)
                else:
                    self.fix_unchecked.add(name)
        self.update_buttons()

    def checked_fix_glyphs(self):
        """The glyphs listed, fixable, and checked."""
        QtCore, QtGui = _qt()
        found = []
        for item in self.top_items(self.glyph_tree):
            name = self.data_of(item, None)
            name = u"%s" % name if name is not None else None
            if name in self.fixable_names and item.checkState(0) == QtCore.Qt.Checked:
                found.append(name)
        return found

    def fix_checked(self):
        self.fix_glyphs(self.checked_fix_glyphs())

    def fix_selected(self):
        name = self.selected_glyph()
        if name in self.fixable_names:
            self.fix_glyphs([name])

    def fix_glyphs(self, names):
        """What needs no designer set right in the glyphs named, in every master but the reference
        (which never changes), as one step of FontLab's History; the masters compared again."""
        ak, b = self.ak, self.ak.b
        if self.busy or not names or self.package is None or not self.same_font():
            return
        reference = self.reference_name()
        masters = [m for m in self.master_names() if m != reference]
        before = set((f.glyph, f.master, f.kind, f.contour) for f in self.problems)
        done, failed, touched = [], [], []
        self.busy = True
        try:
            for name in names:
                glyph = self.package.findName(name)
                reference_layer = self.layer(name, reference)
                original = read_outline(reference_layer) if reference_layer is not None else None
                if glyph is None or original is None:
                    failed.append(u"%s: no layer in %s to match" % (name, reference))
                    continue
                shared = shape_ids(reference_layer)
                for master in masters:
                    layer = self.layer(name, master)
                    outline = read_outline(layer) if layer is not None else None
                    if outline is None:
                        continue
                    plan = plan_fixes(original, outline)
                    if plan.empty():
                        continue
                    if shared & shape_ids(layer):
                        failed.append(u"%s in %s: its shapes are shared with %s, which would change too" % (
                            name, master, reference))
                        continue
                    if glyph not in touched:
                        touched.append(glyph)
                    try:
                        apply_fix(layer, plan)
                    except Exception as exc:
                        failed.append(u"%s in %s: %s" % (name, master, exc))
                        continue
                    if same_outline(read_outline(layer), apply_plan(outline, plan)):
                        done.append(u"%s in %s (%s)" % (name, master, u"; ".join(plan_steps(plan, reference))))
                    else:
                        failed.append(u"%s in %s: it did not read back as planned (%s), look at it" % (
                            name, master, u"; ".join(plan_steps(plan, reference))))
                if not same_outline(read_outline(reference_layer), original):
                    failed.append(u"%s in %s: the master compared with changed too (a shared element?)" % (name, reference))
        except Exception as exc:
            failed.append(u"%s" % exc)
        finally:
            self.busy = False
        if touched:
            ak.notify_changed(self.fontlab, self.package, u"FreeLab Font Check: masters", touched)
        undo = u" <i>Edit &gt; Undo</i> takes %s back." % (u"it" if len(touched) == 1 else u"them") if touched else u""
        if done:
            shown = done[:20] + ([u"%d more" % (len(done) - 20)] if len(done) > 20 else [])
            self.log.add(u"Fixed %s: %s.%s" % (b(counted(len(done), u"glyph layer")), ak.html(u"; ".join(shown)), undo),
                         "done")
        if failed:
            self.log.add(u"Not fixed: %s.%s" % (ak.html(u"; ".join(failed[:20])), u"" if done else undo), "error")
        if not done and not failed:
            self.log.add(u"Nothing to fix: the masters already match where Font Check can set them right.")
        selected = self.selected_glyph()
        self.stale.add("metrics")
        self.check_masters()
        after = [f for f in self.problems if (f.glyph, f.master, f.kind, f.contour) not in before]
        elsewhere = sorted(set(f.glyph for f in after if f.glyph not in names))
        if elsewhere:
            self.log.add(u"New problems in %s since the fix (a shared element changed with it?): %s." % (
                counted(len(elsewhere), u"other glyph"), ak.html(u", ".join(elsewhere[:20]))), "warning")
        left = sorted(set(f.glyph for f in self.problems if f.glyph in names))
        designer = [g for g in left if g not in self.fixable_names]
        if designer:
            self.log.add(u"%s still %s problems that need the designer: %s." % (
                b(counted(len(designer), u"glyph")), u"has" if len(designer) == 1 else u"have",
                ak.html(u", ".join(designer[:20]))))
        unfixed = [g for g in left if g in self.fixable_names]
        if unfixed:
            self.log.add(u"%s still %s problems Fix sets right: %s. Look at %s in a <i>Glyph</i> window." % (
                b(counted(len(unfixed), u"glyph")), u"has" if len(unfixed) == 1 else u"have",
                ak.html(u", ".join(unfixed[:20])), u"it" if len(unfixed) == 1 else u"them"), "warning")
        for item in self.top_items(self.glyph_tree):
            if selected is not None and u"%s" % self.data_of(item, u"") == selected:
                self.glyph_tree.setCurrentItem(item)
                break

    # -- the Glyph window --------------------------------------------------------

    def selected_glyphs(self):
        """The glyphs selected in the view shown (flags, the Glyph window)."""
        key = self.current_key()
        if key == "metrics":
            return [c.extent.name for c in self.selected_clips()]
        if key == "masters":
            name = self.selected_glyph()
            return [name] if name else []
        return []

    def glyph_window_text(self):
        """FontLab text for what is selected: a language's missing characters (FontLab shows the ones the
        font has not as placeholders) and the ones it composes, the checked characters, or a glyph
        between the font's H's (n's, o's)."""
        if self.package is None:
            return u""
        key = self.current_key()
        if key == "coverage":
            language = self.selected_language()
            if language is not None and (self.coverage_focus == "languages" or not self.checked):
                return u"".join(language.all_missing() + [c for c, _ in language.composed])
            if self.checked:
                return u"".join(sorted(self.checked, key=code_points))
            row = self.selected_row()
            return u"".join(row.items) if row is not None else u""
        names = self.selected_glyphs()
        if not names:
            return u""
        if len(names) > 1:
            return u"".join(u"/%s" % name for name in names)
        try:
            contexts = self.ak.proof_contexts(self.package, names[:1])
        except Exception:
            contexts = []
        context = contexts[0] if contexts else None
        if context and context != names[0]:
            return u"/%s/%s/%s/%s/%s" % (context, context, names[0], context, context)
        return u"/%s" % names[0]

    def show_in_glyph_window(self):
        if self.package is None:
            return
        text = self.glyph_window_text()
        if not text:
            return
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open a <i>Glyph</i> window: %s" % self.ak.html(error), "error")

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        if self.package is not None:
            QtCore.QTimer.singleShot(50, lambda: self.check(self.current_key()))  # checked as it opens


def main():
    held = getattr(sys, "_freelab_font_check", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    dialog = FontCheckDialog()
    sys._freelab_font_check = dialog  # kept, even half-built: PythonQt deletes a dialog with no Python reference
    if dialog.failed is not None:
        print("FreeLab Font Check: %s" % dialog.failed)
        try:
            dialog.dialog.close()
        except Exception:
            pass
        return
    try:
        dialog.ak.hook_menu_order()
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_font_check":
    main()
