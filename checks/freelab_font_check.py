#FLM: Font Check
# -*- coding: utf-8 -*-
"""FreeLab Font Check, from FontLab's Scripts menu.

Three lists for the current font, each read-only:

- Coverage: the languages its characters cover, nearly cover (the few characters missing named), or
  miss, by script, from Hyperglot's orthographies (checks/language_coverage.json, Apache License
  2.0). A letter the font lacks as one character counts when the font has its letter and marks and
  its anchors put them together (composed); the list says which. Missing letters that Diacritics can
  build are handed to it.
- Vertical metrics: the font's line metrics (typo, hhea, win, Use Typo Metrics) checked as Google
  Fonts' vertical metrics guidance asks, the glyphs Windows clips (beyond winAscent and winDescent,
  in any master, and by how much), and the values that guidance suggests. FreeLab does not write
  them: they are set in Font Info.
- Masters: what keeps masters from interpolating, glyph by glyph: contours, nodes and their types,
  start points, directions, components and their order, anchors, and glyphs some masters lack.

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
TABS = ("coverage", "metrics", "masters")
NEARLY_MISSING = 3  # a language missing at most this many base characters (and marks) is nearly covered
SCRIPT_MINIMUM = 5  # a font with fewer of a script's characters than this has none of it (its languages summed up)
LINE_SHARE = 1.2  # Google Fonts: typo (and hhea) ascender plus descender at 120% of the em for a new font
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
    for iso, name, autonym, script, status, validity, speakers, base, auxiliary, marks in data["orthographies"]:
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


LEVELS = (("nearly", u"Nearly covered"), ("covered", u"Covered"), ("missed", u"Missed"))


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
    nearly covered first); within each, the nearly covered languages first (the fewest missing first),
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

    def __init__(self, kind, severity, text, glyphs=None, value=None):
        self.kind, self.severity, self.text = kind, severity, text
        self.glyphs = glyphs or []
        self.value = value  # the units it is off by, or None


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
                                   u"points"))
    if m.use_typo is False:
        found.append(MetricFinding("settings", "problem", u"Use Typo Metrics is off: Windows spaces lines by "
                                   u"winAscent and winDescent, so raising them to stop clipping loosens the lines "
                                   u"too"))
    elif m.use_typo is None:
        found.append(MetricFinding("settings", "info", u"FontLab did not say whether Use Typo Metrics (OS/2 "
                                   u"fsSelection bit 7) is on: it should be"))
    for label, hhea, typo in ((u"ascender", m.hhea_ascender, m.typo_ascender),
                              (u"descender", m.hhea_descender, m.typo_descender),
                              (u"line gap", m.hhea_line_gap, m.typo_line_gap)):
        if hhea is not None and typo is not None and round_units(hhea) != round_units(typo):
            found.append(MetricFinding("settings", "advice", u"hhea %s (%d) and typo %s (%d) differ: macOS and Windows "
                                       u"space lines differently" % (label, hhea, label, typo)))
    for label, gap in ((u"typo", m.typo_line_gap), (u"hhea", m.hhea_line_gap)):
        if gap:
            found.append(MetricFinding("settings", "advice", u"The %s line gap is %d: applications add it above the "
                                       u"line, or share it above and below (browsers); 0 spaces lines alike "
                                       u"everywhere" % (label, gap), value=round_units(gap)))
    line = line_values(m)
    if line is not None:
        ascender, descender, gap = line
        share = (ascender - descender + gap) / upm
        if capitals and not LINE_RANGE[0] - 0.005 <= share <= LINE_RANGE[1] + 0.005:
            found.append(MetricFinding("settings", "advice", u"The line is %d%% of the em: Google Fonts asks 120%% to "
                                       u"130%% for Latin, Greek, and Cyrillic (%s)" % (
                                           round_units(share * 100), u"tighter lines may touch" if share < LINE_RANGE[0]
                                           else u"looser looks spaced out, unless taller scripts need it"),
                                       value=round_units(share * 100)))
        a_grave = [e for e in extents if e.code == 0xC0]
        tallest = max(a_grave, key=lambda e: e.top) if a_grave else None
        if tallest is not None and tallest.top > ascender:
            found.append(MetricFinding("settings", "advice", u"A grave reaches %d, above the line's ascender (%d): some "
                                       u"macOS applications then place the first line by it" % (
                                           round_units(tallest.top), ascender),
                                       [(tallest.master, tallest.name, round_units(tallest.top - ascender))]))
        if capitals and m.cap_height and descender:
            above = ascender - m.cap_height
            if abs(above + descender) > CENTER_TOLERANCE_SHARE * upm:
                found.append(MetricFinding("settings", "info", u"Capitals are not centered in the line: %d above the "
                                           u"cap height, %d below the baseline (Google Fonts' advice: equal, for "
                                           u"buttons and boxes)" % (round_units(above), round_units(-descender))))
        over = sorted((e for e in extents if e.top > ascender), key=lambda e: (-e.top, e.name))
        under = sorted((e for e in extents if e.bottom < descender), key=lambda e: (e.bottom, e.name))
        for kind, rows, edge in (("beyond-top", over, ascender), ("beyond-bottom", under, descender)):
            for e in rows[:BEYOND_SHOWN]:
                by = round_units(e.top - edge) if kind == "beyond-top" else round_units(edge - e.bottom)
                found.append(MetricFinding(kind, "info", u"%s: %d past it" % (e.name, by), [(e.master, e.name, by)], by))
    else:
        found.append(MetricFinding("settings", "advice", u"Neither typo nor hhea ascender and descender are set: "
                                   u"each application then spaces lines its own way"))
    bottom, top = family_extent(extents)
    if m.win_ascent and m.win_descent and top is not None and m.use_typo is not True:
        slack = max(m.win_ascent - top, m.win_descent + bottom)
        if slack > WIN_SLACK_SHARE * upm:
            found.append(MetricFinding("settings", "info", u"winAscent and winDescent reach %d past the ink: with Use "
                                       u"Typo Metrics off, Windows spaces lines that much looser than needed" % round_units(slack)))
    return found


class Suggestion(object):
    def __init__(self, key, label, now, value):
        self.key, self.label, self.now, self.value = key, label, now, value

    def changes(self):
        return self.now is None or self.now != self.value


SUGGESTED = (("typo_ascender", u"Typo ascender"), ("typo_descender", u"Typo descender"),
             ("typo_line_gap", u"Typo line gap"), ("hhea_ascender", u"hhea ascender"),
             ("hhea_descender", u"hhea descender"), ("hhea_line_gap", u"hhea line gap"),
             ("win_ascent", u"winAscent"), ("win_descent", u"winDescent"), ("use_typo", u"Use Typo Metrics"))
MODES = (("new", u"a new font (the line at"), ("keep", u"an update, keeping its line spacing"))


def suggest_metrics(m, extents, capitals=True, mode="new", share=LINE_SHARE, letters=None):
    """([Suggestion], [note]) of vertical metrics following Google Fonts' guidance.

    New font: the line share times the em, capitals centered in it (or the font's ascender and
    descender scaled to it), raised to clear A grave and lowered to clear the deepest descender of a
    to z (Greek, Cyrillic), line gaps of 0, hhea equal to typo, win at the ink's highest and lowest
    points in every master, Use Typo Metrics on; for a font of another script, the line also raised
    and lowered to clear its letters' ink (letters: their code points). Update: the line as it was (typo kept if Use Typo
    Metrics was on, else the old win values become typo), win and Use Typo Metrics as for a new font."""
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
            notes.append(u"Use Typo Metrics was on: the typo values keep the line as it was.")
        elif m.win_ascent and m.win_descent:
            ascender, descender, gap = m.win_ascent, -m.win_descent, 0
            notes.append(u"Use Typo Metrics was off: the old win values become the typo values, so Windows keeps "
                         u"the line as it was.")
        else:
            notes.append(u"Nothing to keep (neither typo nor win values are set): suggested as for a new font.")
    if ascender is None:
        line = share * upm
        cap = m.cap_height or tallest((0x48,)) or 0.7 * upm
        if capitals:
            ascender = round_units((line - cap) / 2.0 + cap)
            descender = ascender - round_units(line)
            notes.append(u"The line is %d%% of the em, capitals centered in it." % round_units(share * 100))
        else:
            high = m.ascender or top or 0.8 * upm
            low = m.descender or bottom or -0.2 * upm
            ascender = round_units(line * high / float(high - low))
            descender = ascender - round_units(line)
            notes.append(u"The line is %d%% of the em, shared as the font's ascender and descender are." %
                         round_units(share * 100))
        gap = 0
        a_grave = tallest((0xC0,))
        if a_grave is not None and a_grave > ascender:
            ascender = int(math.ceil(a_grave))
            notes.append(u"The ascender is raised to A grave's top (%d)." % ascender)
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
    components' glyph names in order, and its anchors' names."""

    def __init__(self, contours=(), components=(), anchors=()):
        self.contours = list(contours)
        self.components = list(components)
        self.anchors = list(anchors)


class Incompatibility(object):
    def __init__(self, glyph, master, contour, kind, text):
        self.glyph, self.master, self.contour, self.kind, self.text = glyph, master, contour, kind, text


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


def node_kind(kind):
    return {u"on": u"on-curve", u"off": u"off-curve", u"curve": u"curve", u"line": u"line"}.get(u"%s" % kind, u"%s" % kind)


def compare_glyph(name, outlines):
    """[Incompatibility] of one glyph across masters [(master, Outline or None)], each master compared
    with the first that has the glyph (None: the master lacks it)."""
    found = []
    present = [(master, outline) for master, outline in outlines if outline is not None]
    if not present:
        return found
    reference_master, reference = present[0]
    for master, outline in outlines:
        if outline is None:
            found.append(Incompatibility(name, master, None, "missing", u"Missing in this master"))
    for master, outline in present[1:]:
        found.extend(compare_outline(name, reference_master, reference, master, outline))
    return found


def compare_outline(name, reference_master, reference, master, outline):
    found = []
    ref = reference_master

    def add(contour, kind, text):
        found.append(Incompatibility(name, master, contour, kind, text))

    if len(outline.contours) != len(reference.contours):
        add(None, "contours", u"%s, %d in %s" % (counted(len(outline.contours), u"contour"), len(reference.contours), ref))
    else:
        sizes, wanted = [len(c.nodes) for c in outline.contours], [len(c.nodes) for c in reference.contours]
        reordered = sizes != wanted and sorted(sizes) == sorted(wanted)
        if reordered:
            add(None, "order", u"Contours in another order than in %s (their node counts: %s; %s in %s)" % (
                ref, u" ".join(u"%d" % s for s in sizes), u" ".join(u"%d" % s for s in wanted), ref))
        for at, (contour, other) in enumerate(zip(outline.contours, reference.contours)):
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
            turned = (contour.closed and other.closed and clear_area(contour) and clear_area(other)
                      and (area > 0) != (other_area > 0))
            if types != wanted_types:
                if turned and rotation_of(types[::-1], wanted_types) is not None:
                    add(number, "direction", u"Runs %s, %s in %s (reversed: its node types match the other way "
                                             u"round)" % (turning(area), turning(other_area), ref))
                    continue
                index = next(i for i in range(len(types)) if types[i] != wanted_types[i])
                add(number, "types", u"Node %d is %s, %s in %s" % (index + 1, node_kind(types[index]),
                                                                    node_kind(wanted_types[index]), ref))
                continue
            if turned:
                add(number, "direction", u"Runs %s, %s in %s" % (turning(area), turning(other_area), ref))
                continue
            shift = start_shift(other, contour)
            if shift:
                add(number, "start", u"Start point %s from where %s's would match" % (
                    counted(abs(shift), u"node") + (u" on" if shift > 0 else u" back"), ref))
    if outline.components != reference.components:
        if sorted(outline.components) == sorted(reference.components):
            add(None, "components", u"Components in another order: %s; %s in %s" % (
                u", ".join(outline.components), u", ".join(reference.components), ref))
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
    contours, components = [], []
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
    return Outline(contours, components, anchor_names(layer))


# ---------------------------------------------------------------------------
# The dialog (Qt)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


HELP = u"""<b>FreeLab Font Check</b><br>
Three lists for the current font. Nothing in the font changes.<br><br>
<b>Coverage</b>: the languages its characters cover, nearly cover, or miss, by script, from
Hyperglot's orthographies. A language is covered when the font has its base and auxiliary characters
(auxiliary: loan words and names) and the marks it needs; nearly covered when it misses at most the
number of base characters you set, or only auxiliary ones. A letter the font lacks as one character
counts when the font has its letter and marks and their anchors place the mark (the list says it is
composed). Double-click a language (or click <i>Show in Glyph window</i>) to see its missing characters
in a Glyph window; <i>Build with Diacritics</i> opens Diacritics on the ones it can build.<br>
<b>Vertical metrics</b>: the glyphs Windows clips (beyond winAscent or winDescent, in any master, and
by how much), the line metrics checked as Google Fonts' guidance asks, and the values it suggests.
FreeLab does not write them: set them in <i>File &gt; Font Info</i>.<br>
<b>Masters</b>: what keeps the masters from interpolating, glyph by glyph: glyphs a master lacks, contour
and node counts, node types, contour order, start points and directions, components and their order,
and anchors (a font with one master has nothing to compare).<br><br>
Each list is checked as its tab is first shown, and again after an undo or an edit in FontLab.
Click this help's ? button, then any control, for what it does."""


class Tab(object):
    """One list: its settings row, its tree, its status, its buttons."""

    def __init__(self, ak, QtGui, columns):
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.settings = QtGui.QHBoxLayout()
        self.layout.addLayout(self.settings)
        self.line = ak.separator()
        self.layout.addWidget(self.line)
        self.status = ak.status_label()
        self.layout.addWidget(self.status)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(columns))
        self.tree.setHeaderLabels(list(columns))
        self.layout.addWidget(self.tree, 1)
        self.buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(self.buttons)
        self.findings = []  # what each row's index (its data) refers to


PREVIEW_HEIGHT = 230  # pixels: a glyph preview's height
PREVIEW_LINES = (("win", (220, 70, 60)), ("line", (60, 120, 220)), ("cap", (128, 128, 128)),
                 ("x", (128, 128, 128)), ("base", (128, 128, 128)))
HIGHLIGHT = (230, 120, 20)  # the contour a Masters row names, and its start point


class FontCheckDialog(object):
    def __init__(self):
        self.failed = None
        self.dialog = None
        try:
            self.build()
        except Exception as exc:  # a half-built dialog crashed FontLab: never raised from here
            self.failed = exc

    def build(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        self.package = self.master = None
        self.busy = False
        self.seen_history, self.stale = None, set(TABS)
        self.diacritics = None  # Diacritics' module, loaded when first needed
        self.buildable = {}  # language key: [characters Diacritics can build]
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
        previews = QtGui.QHBoxLayout()
        self.previews = []
        for _ in range(2):
            label = QtGui.QLabel()
            label.setProperty(ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumHeight(PREVIEW_HEIGHT)
            previews.addWidget(label, 1)
            self.previews.append(label)
        self.previews[0].setWhatsThis(u"Vertical metrics: the selected glyph in its master, with winAscent and "
                                      u"winDescent (red), the line's ascender and descender (blue), the cap height, "
                                      u"x-height, and baseline (gray).<br>Masters: the glyph in the master compared "
                                      u"with, the row's contour in orange, its start point dotted.")
        self.previews[1].setWhatsThis(u"Masters: the glyph in the row's master, the row's contour in orange, its start "
                                      u"point dotted.")
        layout.addLayout(previews)

        # Coverage
        self.coverage = Tab(ak, QtGui, ("Language", "Coverage", "Missing", "Speakers"))
        tab = self.coverage
        tab.settings.addWidget(QtGui.QLabel("Nearly covered: missing at most"))
        self.nearly = QtGui.QSpinBox()
        self.nearly.setRange(0, 30)
        self.nearly.setValue(NEARLY_MISSING)
        self.nearly.setSuffix(" base characters")
        self.nearly.setWhatsThis(u"A language missing at most this many of its base characters (and marks), or "
                                 u"only auxiliary ones, is nearly covered: it is listed first, with what it misses.")
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
        tab.tree.setWhatsThis(u"The languages of each script, the nearly covered ones first (with the characters "
                              u"they miss), then the covered ones, then the missed ones, the most spoken first. "
                              u"Scripts the font has none of come last, folded.")
        self.diacritics_button = QtGui.QPushButton("Build with Diacritics")
        self.diacritics_button.setWhatsThis(u"Opens Diacritics, which builds the selected language's missing letters "
                                            u"with diacritics from the font's letters and marks (you check them there "
                                            u"before anything is made).")
        tab.buttons.addStretch(1)
        tab.buttons.addWidget(self.diacritics_button)

        # Vertical metrics
        self.metrics = Tab(ak, QtGui, ("Check", "Master", "Value", "Suggested"))
        tab = self.metrics
        tab.settings.addWidget(QtGui.QLabel("Suggest values for"))
        self.mode = QtGui.QComboBox()
        for _, label in MODES:
            self.mode.addItem(label)
        self.mode.setWhatsThis(u"<i>A new font</i>: the line at the share of the em you set, capitals centered "
                               u"in it, clear of A grave and the deepest descender.<br><i>An update</i>: the line "
                               u"spacing of the released font kept (Google Fonts asks that documents do not "
                               u"reflow), only win values and Use Typo Metrics changed.")
        tab.settings.addWidget(self.mode)
        self.share = QtGui.QSpinBox()
        self.share.setRange(100, 200)
        self.share.setValue(int(LINE_SHARE * 100))
        self.share.setSuffix("% of the em)")
        self.share.setWhatsThis(u"The line's height (ascender plus descender) for a new font: Google Fonts asks "
                                u"120% to 130% for Latin, Greek, and Cyrillic; tall scripts may need more.")
        tab.settings.addWidget(self.share)
        self.metrics_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(self.metrics_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"The glyphs Windows clips, the line metrics checked, the glyphs reaching past the "
                              u"line, and the suggested values.")
        self.copy_button = QtGui.QPushButton("Copy suggested values")
        self.copy_button.setWhatsThis(u"Copies the suggested values as text, to set them in Font Info.")
        self.font_info_button = QtGui.QPushButton("Open Font Info")
        self.font_info_button.setWhatsThis(u"Opens FontLab's Font Info, where these values are set.")
        tab.buttons.addStretch(1)
        tab.buttons.addWidget(self.copy_button)
        tab.buttons.addWidget(self.font_info_button)

        # Masters
        self.masters = Tab(ak, QtGui, ("Glyph", "Master", "Contour", "Problem"))
        tab = self.masters
        tab.settings.addWidget(QtGui.QLabel("Compare every master with"))
        self.reference = QtGui.QComboBox()
        self.reference.setWhatsThis(u"The master each other master is compared with.")
        tab.settings.addWidget(self.reference)
        self.masters_button = QtGui.QPushButton("Compare masters")
        tab.settings.addWidget(self.masters_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"Each difference that keeps a glyph from interpolating: the glyph, the master, the "
                              u"contour (numbered from 1), and what differs from the master compared with.")

        for tab, label in ((self.coverage, "Coverage"), (self.metrics, "Vertical metrics"), (self.masters, "Masters")):
            ak.grid_lines(tab.tree)
            self.tabs.addTab(label)
            self.pages.addWidget(tab.widget)
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected row in a Glyph window: a language's missing "
                                              u"characters, or a glyph.")
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.glyph_window_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.coverage_button.connect("clicked()", self.check_coverage)
        self.metrics_button.connect("clicked()", self.check_vertical)
        self.masters_button.connect("clicked()", self.check_masters)
        self.diacritics_button.connect("clicked()", self.build_with_diacritics)
        self.copy_button.connect("clicked()", self.copy_suggestions)
        self.font_info_button.connect("clicked()", self.open_font_info)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        for tab in (self.coverage, self.metrics, self.masters):
            tab.tree.connect("itemSelectionChanged()", self.selection_changed)
            tab.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window())
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.close_button.connect("clicked()", dialog.close)
        ak.plain_buttons(dialog)
        self.read_font()
        self.history_timer = ak.watch_history(self)
        self.flagging = [ak.flag_menu(tab.tree, self, self.selected_glyphs, (lambda tab: lambda item: self.row_glyphs(tab, item))(tab))
                         for tab in (self.metrics, self.masters)]
        self.update_buttons()

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
        return glyph.getLayerByName(master)

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
        """An undo, a redo, or an edit in FontLab: the list shown is checked again, the others when shown."""
        self.stale = set(TABS)
        self.buildable = {}
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): checked again.")
        self.check(self.current_key())

    def switch_page(self, index):
        QtCore, QtGui = _qt()
        self.pages.setCurrentIndex(index)
        self.selection_changed()
        key = TABS[index]
        if key in self.stale and self.package is not None:
            QtCore.QTimer.singleShot(0, lambda: self.check(key))  # checked as it is first shown

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        ak = self.ak
        finding = self.selected_finding()
        ak.enable(self.diacritics_button, isinstance(finding, Coverage) and bool(self.buildable_for(finding, False)))
        ak.enable(self.copy_button, bool(getattr(self, "suggestions", None)))
        ak.enable(self.font_info_button, self.package is not None)
        ak.enable(self.glyph_window_button, self.package is not None and bool(self.glyph_window_text()))

    def selection_changed(self):
        finding = self.selected_finding()
        if isinstance(finding, Coverage) and self.package is not None:
            self.buildable_for(finding)  # (Diacritics asked once per language)
        self.update_previews()
        self.update_buttons()

    # -- rows ------------------------------------------------------------

    @staticmethod
    def add_row(tab, index, texts, parent=None, tip=u"", bold=True):
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        item.setData(0, QtCore.Qt.UserRole, index)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if bold:
            font = QtGui.QFont(tab.tree.font)
            font.setBold(True)
            item.setFont(0, font)
        for column in range(len(texts)):
            if tip:
                item.setToolTip(column, tip)
            if column and (texts[column].replace(u",", u"").lstrip(u"-").isdigit() or texts[column] == u"\N{EN DASH}"):
                item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
        if parent is not None:
            parent.addChild(item)
        else:
            tab.tree.addTopLevelItem(item)
        return item

    def add_group(self, tab, text, expanded=True):
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem([text])
        item.setData(0, QtCore.Qt.UserRole, -1)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        tab.tree.addTopLevelItem(item)
        item.setFirstColumnSpanned(True)
        self.ak.section_row(item, tab.tree)
        item.setExpanded(expanded)
        return item

    @staticmethod
    def resize(tab):
        for column in range(tab.tree.columnCount - 1):
            tab.tree.resizeColumnToContents(column)

    def start(self, tab):
        """A list about to be checked: emptied; False when it cannot be (busy, no font)."""
        if self.busy or not self.read_font():
            return False
        tab.tree.clear()
        tab.findings = []
        tab.status.setText(u"")
        return True

    def selected_finding(self):
        """The finding of the selected row, or None (a group's heading)."""
        QtCore, QtGui = _qt()
        try:
            tab = self.tab_of(self.current_key())
            items = tab.tree.selectedItems()
        except Exception:
            return None
        if not items:
            return None
        data = items[0].data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return tab.findings[index] if 0 <= index < len(tab.findings) else None

    def row_glyphs(self, tab, item):
        """The glyphs of a row (its flags shown)."""
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        if not 0 <= index < len(tab.findings):
            return []
        return self.finding_glyphs(tab.findings[index])

    @staticmethod
    def finding_glyphs(finding):
        if isinstance(finding, MetricFinding):
            return [name for _, name, _ in finding.glyphs]
        if isinstance(finding, Incompatibility):
            return [finding.glyph]
        return []

    def selected_glyphs(self):
        return self.finding_glyphs(self.selected_finding())

    # -- Coverage ------------------------------------------------------------

    def font_characters(self):
        """The font's FontCharacters: its code points, and its anchors in the current master (read as
        letters and marks are asked about)."""
        package, master = self.package, self.master
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
        self.buildable = {}
        tab.tree.setRootIsDecorated(True)
        tab.tree.setUpdatesEnabled(False)
        try:
            lacking = []
            for s in scripts:
                if not s.present:
                    lacking.append(s.script)
                summary = u", ".join(u"%d %s" % (s.count(level), label.lower()) for level, label in LEVELS if s.count(level))
                group = self.add_group(tab, u"%s \N{EM DASH} %s" % (s.script, summary), expanded=s.present)
                for r in s.results:
                    tab.findings.append(r)
                    self.add_row(tab, len(tab.findings) - 1, self.coverage_texts(r), group, self.coverage_tip(r))
        finally:
            tab.tree.setUpdatesEnabled(True)
        self.resize(tab)
        present = [s for s in scripts if s.present]
        totals = dict((level, sum(s.count(level) for s in present)) for level, _ in LEVELS)
        composed = sum(1 for s in present for r in s.results if r.composed and r.level != "missed")
        text = u"%s covered, %s nearly covered (at most %s missing, or auxiliary ones only), %s missed, of the " \
               u"languages of %s the font has (%s)." % (
                   b(counted(totals["covered"], u"language")), b(totals["nearly"]),
                   b(counted(self.nearly.value, u"base character")), b(totals["missed"]),
                   b(counted(len(present), u"script")), u", ".join(s.script for s in present) or u"none")
        if composed:
            text += u" %s of them count%s letters the font composes with its anchors (marked composed)." % (
                b(composed), u"s" if composed == 1 else u"")
        if lacking:
            text += u" %s the font has none of come%s last, folded." % (
                b(counted(len(lacking), u"script")), u"s" if len(lacking) == 1 else u"")
        tab.status.setText(text)
        self.checked_now("coverage")

    @staticmethod
    def coverage_texts(r):
        language = r.language
        if r.level == "covered":
            state = u"Covered (%d composed)" % len(r.composed) if r.composed else u"Covered"
        elif r.level == "nearly":
            state = u"Nearly: %s missing" % counted(r.base_missing() + len(r.auxiliary_missing), u"character")
        else:
            state = u"Missed: %d missing" % r.base_missing()
        missing = u" ".join(r.missing + r.marks_missing)
        if r.auxiliary_missing:
            aux = u" ".join(r.auxiliary_missing[:40]) + (u" \N{HORIZONTAL ELLIPSIS}" if len(r.auxiliary_missing) > 40 else u"")
            missing = (missing + u"  \N{MIDDLE DOT}  " if missing else u"") + u"auxiliary: " + aux
        if r.level == "missed" and len(missing) > 120:
            missing = missing[:120] + u" \N{HORIZONTAL ELLIPSIS}"
        speakers = u"{:,}".format(language.speakers) if language.speakers else u"\N{EN DASH}"
        return (language.label(), state, missing, speakers)

    @staticmethod
    def coverage_tip(r):
        lines = [u"%s, %s script (Hyperglot: %s, %s)." % (r.language.label(), r.language.script, r.language.status,
                                                           r.language.validity)]
        if r.missing:
            lines.append(u"Base characters missing: %s" % u" ".join(r.missing))
        if r.marks_missing:
            lines.append(u"Marks missing: %s" % u" ".join(u"\N{DOTTED CIRCLE}" + m for m in r.marks_missing))
        if r.auxiliary_missing:
            lines.append(u"Auxiliary characters missing: %s" % u" ".join(r.auxiliary_missing))
        if r.composed:
            lines.append(u"Composed from the font's letters and marks (its anchors): %s" % u" ".join(c for c, _ in r.composed))
        if r.parts:
            lines.append(u"The font has the letters and marks of %s, but no anchors joining them" % u" ".join(r.parts))
        return u"\n".join(lines)

    def diacritics_module(self):
        if self.diacritics is None:
            self.diacritics = self.ak.load_sibling(DIACRITICS_FILE, DIACRITICS_MODULE)
        return self.diacritics

    def buildable_for(self, r, compute=True):
        """The missing letters of a language Diacritics can build (its own planning asked), or []."""
        key = (r.language.iso, r.language.script)
        if key in self.buildable or not compute:
            return self.buildable.get(key, [])
        found = []
        try:
            dm = self.diacritics_module()
            ranges = [pair for _, _, pairs in dm.SETS for pair in pairs]
            candidates = buildable_candidates([r], ranges)
            if candidates:
                fgs = list(self.package.fgPackage.glyphs)
                font = dm.Font([u"%s" % g.name for g in fgs], [(u"%s" % g.name, g.unicode) for g in fgs])
                found = [recipe.char for recipe in dm.plan(font, candidates) if not recipe.missing]
        except Exception as exc:
            self.log.add(u"Diacritics could not be asked: %s" % self.ak.html(exc), "warning")
        self.buildable[key] = found
        return found

    def build_with_diacritics(self):
        finding = self.selected_finding()
        if not isinstance(finding, Coverage) or self.package is None:
            return
        chars = self.buildable_for(finding)
        if not chars:
            return
        b = self.ak.b
        try:
            dm = self.diacritics_module()
            try:
                dm.main(characters=chars)  # a Diacritics that lists the letters given only
                self.log.add(u"Diacritics lists %s for %s: check them there, then build." % (
                    b(u" ".join(chars)), b(finding.language.name)), "done")
            except TypeError:
                dm.main()  # (a Diacritics that takes no letters lists every one it can build)
                self.log.add(u"Diacritics lists every letter with diacritics it can build, %s among them." % b(
                    u" ".join(chars)), "done")
        except Exception as exc:
            self.log.add(u"Diacritics did not open: %s" % self.ak.html(exc), "error")

    # -- Vertical metrics ---------------------------------------------------------

    def extents(self, tab):
        """[Extent] of every glyph with ink, in every master."""
        QtCore, QtGui = _qt()
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
        QtCore, QtGui = _qt()
        ak, b = self.ak, self.ak.b
        self.busy = True
        self.suggestions = []
        try:
            m = read_metrics(self.package)
            if not m.upm:
                m.upm = float(self.package.upm)
            extents = self.extents(tab)
            codes = set(code for name, glyph_codes_ in self.glyphs() for code in glyph_codes_)
            capitals = has_capitals(codes)
            findings = check_metrics(m, extents, capitals)
            mode = MODES[self.mode.currentIndex][0]
            suggestions, notes = suggest_metrics(m, extents, capitals, mode, self.share.value / 100.0,
                                                 None if capitals else other_letters(codes))
        except Exception as exc:
            tab.status.setText(u"")
            self.log.add(ak.html(exc), "error")
            return
        finally:
            self.busy = False
        self.metric_values, self.extent_of = m, dict(((e.master, e.name), e) for e in extents)
        self.suggestions = suggestions
        tab.tree.setRootIsDecorated(True)
        groups = dict(METRIC_GROUPS)
        for kind, title in METRIC_GROUPS:
            rows = [f for f in findings if f.kind == kind]
            if not rows:
                continue
            if kind == "settings":
                group = self.add_group(tab, title)
            else:
                glyphs = len(set(name for f in rows for _, name, _ in f.glyphs))
                more = u"" if len(rows) < BEYOND_SHOWN or not kind.startswith(u"beyond") else u", the farthest %d" % BEYOND_SHOWN
                group = self.add_group(tab, u"%s: %s%s" % (title, counted(glyphs, u"glyph"), more),
                                       expanded=kind.startswith(u"clip"))
            for f in rows:
                tab.findings.append(f)
                master = f.glyphs[0][0] if f.glyphs else u""
                units = u"%d" % f.value if f.value is not None else u""
                self.add_row(tab, len(tab.findings) - 1, (f.text, master, units, u""), group, f.text,
                             bold=f.severity == "problem")
        group = self.add_group(tab, u"Suggested values (%s)" % (u"a new font, the line at %d%% of the em" % self.share.value
                                                                if mode == "new" else u"an update, its line spacing kept"))
        for s in suggestions:
            tab.findings.append(s)
            self.add_row(tab, len(tab.findings) - 1, (s.label, u"", now_text(s), suggestion_text(s)), group,
                         u"%s: %s now, %s suggested." % (s.label, now_text(s), suggestion_text(s)), bold=s.changes())
        self.resize(tab)
        clipped = len(set(name for f in findings if f.kind.startswith(u"clip") for _, name, _ in f.glyphs))
        advice = sum(1 for f in findings if f.kind == "settings" and f.severity != "info")
        bottom, top = family_extent(extents)
        text = u"%s clipped on Windows, %s about the line metrics, across %s." % (
            b(counted(clipped, u"glyph")), b(counted(advice, u"remark")), b(counted(len(self.master_names()), u"master")))
        if top is not None:
            text += u" The ink reaches from %s to %s." % (b(round_units(bottom)), b(round_units(top)))
        changed = [s for s in suggestions if s.changes()]
        text += u" %s FreeLab does not write the suggested values: set them in %s (%s copies them)." % (
            u" ".join(notes), ak.i("File > Font Info"), ak.i("Copy suggested values")) if changed else \
            u" The font's values are as suggested."
        tab.status.setText(text)
        self.checked_now("metrics")

    def copy_suggestions(self):
        QtCore, QtGui = _qt()
        suggestions = getattr(self, "suggestions", None) or []
        if not suggestions:
            return
        text = u"\n".join(u"%s: %s" % (s.label, suggestion_text(s)) for s in suggestions)
        try:
            QtGui.QApplication.clipboard().setText(text)
            self.log.add(u"Copied the suggested values.", "done")
        except Exception as exc:
            self.log.add(u"Could not copy: %s" % self.ak.html(exc), "error")

    def open_font_info(self):
        try:
            self.fontlab.flItems.requestFontInfoDlg()
        except Exception as exc:
            self.log.add(u"FontLab did not open Font Info: %s. Open it from the File menu." % self.ak.html(exc), "warning")

    # -- Masters -------------------------------------------------------------------

    def check_masters(self):
        tab = self.masters
        if not self.start(tab):
            return
        QtCore, QtGui = _qt()
        ak, b = self.ak, self.ak.b
        masters = self.master_names()
        if len(masters) < 2:
            tab.status.setText(u"This font has one master: nothing to compare.")
            self.checked_now("masters")
            return
        reference = self.reference.currentText if self.reference.currentIndex >= 0 else masters[0]
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
        tab.findings = found
        tab.tree.setRootIsDecorated(True)
        by_glyph, names = {}, []
        for index, f in enumerate(found):
            if f.glyph not in by_glyph:
                by_glyph[f.glyph] = []
                names.append(f.glyph)
            by_glyph[f.glyph].append(index)
        tab.tree.setUpdatesEnabled(False)
        try:
            for name in names:
                indexes = by_glyph[name]
                parent = None
                if len(indexes) > 1:
                    parent = self.add_group(tab, u"%s \N{EM DASH} %s" % (name, counted(len(indexes), u"problem")))
                for index in indexes:
                    f = found[index]
                    self.add_row(tab, index, (f.glyph, f.master, u"%d" % f.contour if f.contour else u"", f.text),
                                 parent, u"%s in %s: %s." % (f.glyph, f.master, f.text))
        finally:
            tab.tree.setUpdatesEnabled(True)
        self.resize(tab)
        kinds = {}
        for f in found:
            kinds[f.kind] = kinds.get(f.kind, 0) + 1
        if found:
            text = u"%s of the %s glyphs %s interpolate (differing: %s), compared with %s." % (
                b(len(names)), b(len(glyphs)), u"does not" if len(names) == 1 else u"do not",
                u", ".join(counted(kinds[kind], *labels) for kind, labels in MASTER_KINDS if kind in kinds), b(reference))
        else:
            text = u"The %s glyphs match in all %s masters, compared with %s: contours, nodes, start points, " \
                   u"directions, components, and anchors." % (b(len(glyphs)), b(len(masters)), b(reference))
        if unread:
            text += u" %s could not be read." % b(counted(len(unread), u"glyph layer"))
        tab.status.setText(text)
        self.checked_now("masters")

    # -- previews and the Glyph window --------------------------------------------

    def update_previews(self):
        finding = self.selected_finding() if self.package is not None else None
        shown = []
        try:
            if isinstance(finding, MetricFinding) and finding.glyphs:
                master, name, _ = finding.glyphs[0]
                shown = [self.metrics_picture(name, master)]
            elif isinstance(finding, Incompatibility):
                reference = self.reference.currentText
                shown = [self.outline_picture(finding.glyph, reference, finding.contour),
                         self.outline_picture(finding.glyph, finding.master, finding.contour)]
        except Exception:
            shown = []
        for index, label in enumerate(self.previews):
            if index < len(shown) and shown[index] is not None:
                label.setPixmap(shown[index])
            else:
                label.clear()

    def colors(self):
        QtCore, QtGui = _qt()
        return self.dialog.palette.color(QtGui.QPalette.WindowText)

    def metrics_picture(self, name, master):
        """The glyph with the font's vertical metrics as lines."""
        QtCore, QtGui = _qt()
        layer = self.layer(name, master)
        if layer is None:
            return None
        path = self.ak.layer_path(layer)
        m = getattr(self, "metric_values", None)
        lines = []
        if m is not None:
            if m.win_ascent:
                lines.append(("win", m.win_ascent, u"winAscent"))
            if m.win_descent:
                lines.append(("win", -m.win_descent, u"winDescent"))
            line = line_values(m)
            if line is not None:
                lines += [("line", line[0], u"ascender"), ("line", line[1], u"descender")]
            if m.cap_height:
                lines.append(("cap", m.cap_height, u"cap height"))
            if m.x_height:
                lines.append(("x", m.x_height, u"x-height"))
        lines.append(("base", 0, u"baseline"))
        return self.draw(path, layer.advanceWidth, lines, u"%s, %s" % (name, master))

    def outline_picture(self, name, master, contour):
        layer = self.layer(name, master)
        if layer is None:
            return None
        return self.draw(self.ak.layer_path(layer), layer.advanceWidth, [("base", 0, u"")], u"%s, %s" % (name, master),
                         layer, contour)

    def draw(self, path, advance, lines, caption, layer=None, contour=None):
        """A glyph's ink in the dialog's text color, lines across it, a contour highlighted."""
        QtCore, QtGui = _qt()
        color = self.colors()
        font = self.dialog.font
        rect = path.boundingRect()
        low = min([rect.top(), 0.0] + [y for _, y, _ in lines])
        high = max([rect.bottom(), 0.0] + [y for _, y, _ in lines])
        caption_height = QtGui.QFontMetrics(font).height()
        room = PREVIEW_HEIGHT - caption_height - 16
        scale = room / float(max(1.0, high - low))
        left = min(rect.left(), 0.0)
        right = max(rect.right(), float(advance or 0))
        label_width = QtGui.QFontMetrics(font).width(u"winDescent") + 8
        width = int((right - left) * scale) + 2 * label_width + 16
        pixmap = QtGui.QPixmap(max(width, 120), PREVIEW_HEIGHT)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setFont(font)
            x0 = label_width + 8 - left * scale
            y0 = 8 + high * scale

            for kind, y, text in lines:
                rgb = dict(PREVIEW_LINES)[kind]
                pen = QtGui.QPen(QtGui.QColor(rgb[0], rgb[1], rgb[2], 200))
                pen.setWidth(1)
                painter.setPen(pen)
                at = int(y0 - y * scale)
                painter.drawLine(0, at, pixmap.width(), at)
                if text:
                    painter.drawText(QtCore.QRect(0, at - caption_height, label_width, caption_height),
                                     int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom), text)
            painter.save()
            painter.translate(x0, y0)
            painter.scale(scale, -scale)
            ink = QtGui.QColor(color)
            ink.setAlpha(190)
            painter.fillPath(path, QtGui.QBrush(ink))
            if layer is not None and contour:
                outline = read_outline(layer)
                if outline is not None and 0 < contour <= len(outline.contours):
                    nodes = outline.contours[contour - 1].nodes
                    pen = QtGui.QPen(QtGui.QColor(HIGHLIGHT[0], HIGHLIGHT[1], HIGHLIGHT[2]))
                    pen.setWidthF(2.0 / scale)
                    painter.setPen(pen)
                    for at in range(len(nodes)):
                        a, b = nodes[at], nodes[(at + 1) % len(nodes)]
                        painter.drawLine(QtCore.QPointF(a[0], a[1]), QtCore.QPointF(b[0], b[1]))
                    if nodes:
                        painter.setBrush(QtGui.QBrush(QtGui.QColor(HIGHLIGHT[0], HIGHLIGHT[1], HIGHLIGHT[2])))
                        painter.drawEllipse(QtCore.QPointF(nodes[0][0], nodes[0][1]), 5.0 / scale, 5.0 / scale)
            painter.restore()
            painter.setPen(color)
            painter.drawText(QtCore.QRect(0, PREVIEW_HEIGHT - caption_height, pixmap.width(), caption_height),
                             int(QtCore.Qt.AlignCenter), caption)
        finally:
            painter.end()
        return pixmap

    def glyph_window_text(self):
        """FontLab text for the selected row: a language's missing characters (the ones the font has
        not, shown as such), or a glyph between the font's H's (n's, o's)."""
        finding = self.selected_finding() if self.package is not None else None
        if isinstance(finding, Coverage):
            return u"".join(finding.all_missing() + [c for c, _ in finding.composed])
        names = self.finding_glyphs(finding) if finding is not None else []
        if not names:
            return u""
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
            self.log.add(u"FontLab did not open a Glyph window: %s" % self.ak.html(error), "error")

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
