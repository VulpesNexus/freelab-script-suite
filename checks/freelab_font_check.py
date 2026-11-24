#FLM: Font Check
# -*- coding: utf-8 -*-
"""FreeLab Font Check, from FontLab's Scripts menu.

Three views of the current font; nothing in the font changes until a button that writes is clicked
(Write suggested values, Fix), each write one step of FontLab's History:

- Coverage: the scripts, each with a bar of its languages covered, within reach (the few characters
  missing named), started, and missed, from Hyperglot's orthographies
  (checks/language_coverage.json, Apache License 2.0) and, for the languages Hyperglot does not
  describe, those of Google Fonts' language data, Unicode CLDR, SIL's Locale Data Repository,
  Unilex, An Crubadan, the Universal Declaration of Human Rights, and Language Tools' keyboard
  layouts (checks/language_orthographies.json: each language's tooltip names its sources, and says
  so when its characters were inferred from counting text or read from a keyboard layout, which
  also gives some languages a second script); the languages and scripts known that no
  source describes, counted and listed as not yet covered; every script of Unicode checked as a set
  of its own (checks/character_sets.json: its whole repertoire, for a script no language here is
  written in); a set of the user's own, pasted, checked
  as a character set; the characters to add, ranked by the languages
  each completes, with a live count of the languages a checked set completes, and, in a tab of their
  own, those the selected language, character set, or family misses; the languages by script, the
  character sets that are no languages, and the languages by family (Glottolog's classification and
  other names, checks/language_families.json, CC BY 4.0), found by any of their names. A letter the
  font lacks as one character counts when the font has its letter and marks and its anchors put them
  together (composed). Missing letters that Glyph Compose can build are handed to it.
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
import time
import unicodedata

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
DIACRITICS_FILE, DIACRITICS_MODULE = "freelab_glyph_compose.py", "freelab_glyph_compose"
LANGUAGES_FILE = "language_coverage.json"  # beside this script: checks/train/languages.py makes it from Hyperglot
ORTHOGRAPHIES_FILE = "language_orthographies.json"  # beside this script: checks/train/orthographies.py makes it
# (the languages Hyperglot does not describe, from Google Fonts' language data, CLDR, SIL's SLDR, Unilex,
# An Crubadan, the Universal Declaration of Human Rights, and Language Tools' keyboard layouts; each row names
# its sources, and says whether its characters were declared, inferred from counting text, or read from a layout)
LIST_FONT_FILE = "FreeLang-Essential.ttf"  # beside this script, or in language_font/: checks/train/language_font.py makes it
LIST_FONT_FOLDER = "language_font"
LIST_FAMILY = "FreeLang Essential"  # its family: Noto subsets (OFL) of every character the languages list shows
# The bundled font is five files (one font holds 65,535 glyphs at most, and its layout a limited
# number of lookups): the first above, for Latin, Greek, Cyrillic, and the other scripts in common use,
# and four that Qt falls back to for what the first lacks (register_list_font), beside it: (file,
# family), in the order they are fallen back to. The four are optional, published beside each release
# rather than kept in the repository: without one, its characters come from the system's fonts. Every
# family starts with LIST_DISPLAY_NAME and a space or a plus (the last three are FreeLang+), which is
# how Glyph Compose leaves them out of its font chooser. Each fits the 31 characters of a Windows family
# name, past which Qt never lists a font (checks/train/language_font.py, GDI_FAMILY_LIMIT). The fourth
# has an en dash (U+2013), written as an escape: this file stays ASCII there, as its file name does,
# which spells the plus "Plus".
LIST_FONT_FALLBACKS = (("FreeLang-CJK.ttf", u"FreeLang CJK"),
                       ("FreeLangPlus-General.ttf", u"FreeLang+ General"),
                       ("FreeLangPlus-Mongolian-Tibetan.ttf", u"FreeLang+ Mongolian\N{EN DASH}Tibetan"),
                       ("FreeLangPlus-Duployan.ttf", u"FreeLang+ Duployan"))
# The fallback families register_list_font gave Qt (a frozenset), or None before it ran (every file
# assumed, as in the tests that never register): names_characters reads it
LIST_FALLBACKS_DRAWN = None
LIST_DISPLAY_NAME = "FreeLang"  # what a tool calls the five together where it names the font to the user
LIST_SCALE = 1.25  # the languages list's text, this many times the dialog's (easier to read)
SETS_FILE = "character_sets.json"  # beside this script: checks/train/character_sets.py makes it (sets that are no languages)
FAMILIES_FILE = "language_families.json"  # beside this script: checks/train/families.py makes it from Glottolog
# (the languages' families and branches, their other names, and the languages Hyperglot does not describe)
FLOAT_MOST = 200  # characters of a selected language, set, or family listed in its own tab beyond those the
# high-value list already has, at most (and of those it sends to a Glyph window)
UNLISTED_SHOWN = 6  # languages Hyperglot does not describe that a search names, at most
# Where a language Font Check cannot check yet is proposed: FreeLab's repository, shown as text and opened on a
# click where Qt can. The one place this address is written (the repository is private until its release).
REPOSITORY = u"https://github.com/VulpesNexus/freelab-script-suite"
ISSUES_ADDRESS = REPOSITORY + u"/issues"
CUSTOM_SETS_FILE = u"font_check_sets.json"  # in FreeLab's settings folder (ak.state_dir()): the sets a user saved
CUSTOM_GROUP = u"Your sets"  # their section in the Character sets tab
PASTED_KEY, PASTED_NAME = u"custom-pasted", u"Pasted characters"
TABS = ("coverage", "metrics", "masters")
NOT_AVAILABLE = u"n/a"  # a dropdown of the font's masters with no font: grayed (owner's image 289), never empty
# The fields' placeholders end with an ellipsis, not a period (owner's image 309); a single word stays as it is
SEARCH_PLACEHOLDER = u"Find a language, a character set, or a family\N{HORIZONTAL ELLIPSIS}"
PASTE_PLACEHOLDER = u"Paste text or characters to check as a set of your own\N{HORIZONTAL ELLIPSIS}"
NAME_PLACEHOLDER = u"Name"
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
PROGRESS_EVERY = 25  # glyphs between two moves of the top row's bar (it lets events through at most every 0.1 s)


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
    """"1 glyph", "2 glyphs", "13,932 glyphs": a count (thousands set apart) with its noun in the right
    number."""
    return u"%s %s" % (u"{0:,}".format(int(number)), one if number == 1 else (many or one + u"s"))


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


# The marks the orthographies list (their marks column, made with Unicode 17), noted as each data file is
# read: FontLab's Python has Unicode 5.2, to which a mark encoded since (Kuvi's U+0C3C, Shina's U+08FF) is
# unassigned, so a letter with it could never count as composed there.
DATA_MARKS = set()


def is_mark(code):
    """Whether a code point is a combining mark: one the data lists as a mark, or by the runtime's
    Unicode data."""
    if code in DATA_MARKS:
        return True
    try:
        return unicodedata.category(char_of(code)).startswith(u"M")
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Coverage: the languages a font's characters cover
# ---------------------------------------------------------------------------

HYPERGLOT, DECLARED, INFERRED = u"Hyperglot", "declared", "inferred"
# A third kind of evidence: a keyboard layout (Language Tools'), the characters its keys and rules type.
# Neither declared nor counted; the check box of the languages inferred from text holds these too.
KEYBOARD = "keyboard"
UNDECLARED = (INFERRED, KEYBOARD)
NOT_GIVEN = u"not given"  # the status of a language whose source gives none: counted with the living ones


class Language(object):
    """One orthography of a language (Hyperglot's): base characters (required), auxiliary ones (loan
    words, names), and the marks it needs on their own. Characters are texts: one character, or a
    letter and combining marks Unicode has no single character for."""

    def __init__(self, iso, name, autonym, script, status, validity, speakers, base, auxiliary, marks,
                 kind="language", definition=u""):
        self.iso, self.name, self.autonym, self.script = iso, name, autonym, script
        self.status, self.validity, self.speakers = status, validity, speakers
        self.base, self.auxiliary, self.marks = base, auxiliary, marks
        # A character set that is no language (IPA, a Unicode block, a foundry's set) is checked as one:
        # kind "set", its group as its script, every character a base one, and the definition it is cited by.
        self.kind, self.definition = kind, definition
        self.aliases = ()  # its other names (Glottolog's): a search finds it by any, the list shows its one name
        self.folded = None  # what a search looks through, made when first searched
        # Where its characters come from, and what kind of evidence that is: "declared" (a person or a
        # maintained project states them: Hyperglot, Google's data, CLDR, SLDR), "inferred" (the letters
        # a text uses, counted), or "keyboard" (what a keyboard layout types). license: the source's,
        # for the tooltip.
        self.source, self.evidence, self.license = HYPERGLOT, DECLARED, u""
        # An inferred orthography: every source it rests on, as (the source's name, the letters it
        # counted or 0, what those are: "text", "words", or u""), the best-ranked first.
        self.rests = ()
        # A character set's optional characters (code points): those it holds but is complete without,
        # since text does not store them (presentation forms, compatibility characters). They never
        # decide its level; optional_count: how many of its base characters are optional. Unlike a
        # language's auxiliary characters, which keep it from being covered.
        self.optional, self.optional_count = frozenset(), 0

    def required_size(self):
        """How many of its base characters it needs (its optional ones left out)."""
        return self.size() - self.optional_count

    def label(self):
        if self.autonym and self.autonym != self.name:
            return u"%s (%s)" % (self.name, self.autonym)
        return self.name

    def size(self):
        """How many base characters it has (a script's set counts its ranges: it makes no list)."""
        return len(self.base)

    def own_names(self):
        """What the list shows or stands for: its name, autonym, and code (a set's group too)."""
        values = [self.name, self.autonym or u"", self.iso]
        if self.kind == "set":
            values.append(self.script)
        return [u"%s" % value for value in values if value]

    def search_text(self):
        """Its own names, then its other names, folded, a line each: one text for a search to look
        through at each keystroke (829 languages and some 17,000 other names)."""
        if self.folded is None:
            self.folded = (fold(u"\n".join(self.own_names())), fold(u"\n".join(self.aliases)))
        return self.folded


_FOLDS = {}  # short texts folded before: a search folds the text typed and each family's name at every row
FOLDS_KEPT, FOLD_LENGTH = 20000, 80


def fold(text):
    """A text to search or compare: any case, its diacritics set aside (francais finds French by its
    autonym). A short text is folded once and kept: with some 2,500 languages a keystroke folded
    25,000 texts, most of its time."""
    text = u"%s" % (text or u"")
    found = _FOLDS.get(text)
    if found is None:
        folded = unicodedata.normalize("NFD", text).lower()
        found = u"".join(c for c in folded if not unicodedata.category(c).startswith(u"M"))
        if len(text) <= FOLD_LENGTH:  # (not the joined names of a language: those are kept on the language)
            if len(_FOLDS) >= FOLDS_KEPT:
                _FOLDS.clear()
            _FOLDS[text] = found
    return found


def session_cache():
    """The data files parsed, kept for FontLab's session: FontLab runs this script anew each time the
    tool is opened, so a cache of the module's own lasted one window, and every opening parsed the
    files again (1.5 MB of JSON: seconds under Python 2.7). What is held on sys is plain data only
    (json's dicts, lists, and texts, by file and file date), never objects of this script's classes:
    each opening defines its classes anew, and an object of the first opening's ScriptSet or
    Uncovered failed every isinstance of the second (Han checked as a list of 103,351 characters, the
    scripts' lines gone, a not-covered language selected as a coverage). Each opening makes its
    objects from that data, once (_LANGUAGES)."""
    held = getattr(sys, "_freelab_font_check_files", None)
    if not isinstance(held, dict):
        held = {}
        sys._freelab_font_check_files = held
    if getattr(sys, "_freelab_font_check_data", None) is not None:
        sys._freelab_font_check_data = None  # (an earlier version's cache of objects: its memory freed)
    return held


_FILES = session_cache()  # {path: (date, parsed data)}, for the session
_LANGUAGES = {}  # this opening's objects made from _FILES, by file (and what else made them)


def read_data(path, stamp):
    """The parsed JSON of a data file at a date, parsed once per session (session_cache)."""
    import json
    held = _FILES.get(path)
    if held is not None and held[0] == stamp:
        return held[1]
    with open(path, "rb") as handle:
        data = json.loads(handle.read().decode("utf-8"))
    _FILES[path] = (stamp, data)
    return data


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


def orthographies_path():
    return os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), ORTHOGRAPHIES_FILE)


def load_languages(path=None, more=None):
    """The orthographies of language_coverage.json (Hyperglot's), then those of more: the languages
    Hyperglot does not describe (language_orthographies.json beside the script when path is not
    given; None with a path given, False for Hyperglot's alone), as Languages. Each file is read once
    per version; a second file that is missing or unreadable leaves Hyperglot's languages alone."""
    if more is None and path is None:
        more = orthographies_path()
    found = load_orthographies(path or languages_path())
    if more:
        try:
            others = load_orthographies(more)
        except (OSError, IOError, ValueError, KeyError, IndexError, TypeError):
            others = []
        if others:
            # (Hyperglot first: a second source only fills in a language it lacks, or, a declared source or
            # a keyboard layout, a script it does not give the language in: Javanese in Javanese beside its
            # Latin, Manipuri in Meetei Mayek beside its Bengali; never a counted text)
            known = set(language.iso for language in found)
            written = set((language.iso, language.script) for language in found)
            key = (path or languages_path(), more)
            held = _LANGUAGES.get(key)
            if held is None or held[0] is not found or held[1] is not others:
                _LANGUAGES[key] = (found, others, found + [
                    one for one in others if one.iso not in known
                    or (one.evidence != INFERRED and (one.iso, one.script) not in written)])
            return _LANGUAGES[key][2]
    return found


def load_orthographies(path):
    """The orthographies of one data file, as Languages (read once per file version). A file of the
    second kind names each row's source and evidence (columns 11 and 12); Hyperglot's has neither.
    Each row's marks are noted as marks (DATA_MARKS)."""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = _LANGUAGES.get(path)
    if held is not None and held[0] == stamp:
        return held[1]
    data = read_data(path, stamp)
    texts = data["texts"]
    statuses = data.get("status", {})
    sources, evidences = data.get("sources") or (), data.get("evidence") or {}
    lists = {}  # a list of characters split once (orthographies share them)

    def characters(index):
        if index not in lists:
            lists[index] = texts[index].split(u" ") if texts[index] else []
        return lists[index]

    found = []
    # An orthography without an autonym of its own takes another one's of the same language (Japanese in
    # hiragana: its kanji one, 日本語), one of the same script family first: Hyperglot gives some only once.
    families = {u"Hiragana": u"japanese", u"Katakana": u"japanese", u"Kanji": u"japanese"}
    named = {}
    for row in data["orthographies"]:
        iso, autonym, script = row[0], row[2], row[3]
        if autonym:
            named.setdefault((iso, families.get(script, script)), autonym)
            named.setdefault((iso, None), autonym)
    for row in data["orthographies"]:
        iso, name, autonym, script, status, validity, speakers, base, auxiliary, marks = row[:10]
        if not autonym:
            autonym = named.get((iso, families.get(script, script))) or named.get((iso, None)) or u""
        language = Language(iso, name, autonym, script, statuses.get(status, status) or NOT_GIVEN, validity, speakers,
                            characters(base), characters(auxiliary), marks)
        if marks:
            DATA_MARKS.update(code_points(marks))
        if len(row) > 11:
            try:
                language.source, language.license = u"%s" % sources[row[10]][1], u"%s" % sources[row[10]][2]
            except (IndexError, TypeError):
                language.source = u"another source"
            evidence = evidences.get(row[11], row[11])
            language.evidence = evidence if evidence in UNDECLARED else DECLARED
        if len(row) > 12:
            try:
                language.rests = tuple((u"%s" % sources[index][1], int(letters),
                                        u"%s" % (sources[index][3] if len(sources[index]) > 3 else u""))
                                       for index, letters in row[12])
            except (IndexError, TypeError, ValueError):
                language.rests = ()
        found.append(language)
    _LANGUAGES[path] = (stamp, found)
    return found


def sets_path():
    return os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), SETS_FILE)


def load_character_sets(path=None):
    """The character sets of character_sets.json (IPA, mathematics, Unicode blocks, foundries' sets), as
    Languages of kind "set" (read once per file version); none without the file."""
    path = path or sets_path()
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return []
    held = _LANGUAGES.get(path)
    if held is not None and held[0] == stamp:
        return held[1]
    data = read_data(path, stamp)
    groups = data["groups"]
    optional = data.get("optional") or {}  # {set id: its optional characters, as ranges} (a file made before: none)
    found = []
    for key, name, group, definition, characters, sequences in data["sets"]:
        if not sequences.strip() and sum(high - low + 1 for low, high in ranges_of(characters)) >= RANGED_FROM:
            # (a large set of single characters, kept as ranges and checked on them: the Han repertoires')
            found.append(RangedSet(u"%s" % key, u"%s" % name, u"%s" % groups[group], characters, u"",
                                   optional.get(key, u""), u"%s" % definition))
            continue
        items = []
        for part in characters.split():
            low, _, high = part.partition(u"-")
            items.extend(char_of(code) for code in range(int(low, 16), int(high or low, 16) + 1))
        for sequence in sequences.split():  # a letter and marks with no single character: "0047+0303"
            items.append(unicodedata.normalize("NFC", u"".join(char_of(int(code, 16)) for code in sequence.split(u"+"))))
        one = Language(u"%s" % key, u"%s" % name, u"", u"%s" % groups[group], u"set", u"", 0, items, [], u"",
                       kind="set", definition=u"%s" % definition)
        held = optional_codes(optional.get(key, u""))
        if held:
            one.optional = held
            one.optional_count = sum(1 for item in items if len(code_points(item)) == 1 and code_points(item)[0] in held)
        found.append(one)
    try:  # every script of Unicode, as a set (a file made before has none; one made before optional characters, 4 columns)
        scripts = data.get("scripts") or {}
        group, version = u"%s" % (scripts.get("group") or SCRIPTS_GROUP), u"%s" % (scripts.get("unicode") or u"")
        found.extend(ScriptSet(u"%s" % row[0], row[1], row[2], u"%s" % row[3], group, version,
                               row[4] if len(row) > 4 else u"")
                     for row in scripts.get("rows", ()))
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        pass
    _LANGUAGES[path] = (stamp, found)
    return found


SCRIPTS_GROUP = u"Scripts (Unicode)"  # the scripts' section in the Character sets tab (the data file names it too)
LEGACY_GROUP = u"Legacy"  # the wholly optional sets' section (the data file names it): left out of the counts
SCRIPT_COMPOSE_MOST = 2000  # a script missing more characters than this is not searched for letters the anchors compose
WANTED_MOST = 2000  # the missing characters of one language or set looked at for the selection's own tab, at most


def ranges_of(text):
    """[(low, high)] of "20-7E A0 152-153": code points as hexadecimal ranges."""
    found = []
    for part in (text or u"").split():
        low, _, high = part.partition(u"-")
        found.append((int(low, 16), int(high or low, 16)))
    return found


def count_in_ranges(codes, ranges):
    """How many of the code points fall in the ranges [(low, high)] (sorted, apart: a data file's), by
    bisection: a Han repertoire has some 4,000 ranges, and a scan of them for each code was felt."""
    if not codes or not ranges:
        return 0
    import bisect
    lows = [low for low, _ in ranges]
    found = 0
    for code in codes:
        at = bisect.bisect_right(lows, code) - 1
        if at >= 0 and code <= ranges[at][1]:
            found += 1
    return found


def optional_codes(text):
    """The code points of "FB00-FB06 212A" as a frozenset (none for u"")."""
    return frozenset(code for low, high in ranges_of(text) for code in range(low, high + 1))


# What the tooltips call the optional characters, said once
OPTIONAL_WHAT = u"presentation forms and compatibility characters, which text does not store"


class CodeItems(object):
    """Code points that read as a list of characters, each character made when it is read: a
    script's missing characters (Han: about 100,000) cost nothing until some are listed, and a slice
    makes only its own. It adds to a list or to another of its kind, as the lists of missing
    characters are added."""

    def __init__(self, codes):
        self.codes = list(codes)
        self.held = None  # its code points as a set, made when first asked whether it holds a character

    def __len__(self):
        return len(self.codes)

    def __iter__(self):
        return (char_of(code) for code in self.codes)

    def __getitem__(self, at):
        if isinstance(at, slice):
            return [char_of(code) for code in self.codes[at]]
        return char_of(self.codes[at])

    def __contains__(self, item):
        if self.held is None:
            self.held = set(self.codes)
        try:
            codes = code_points(item)
        except TypeError:
            return False
        return len(codes) == 1 and codes[0] in self.held

    def __add__(self, other):
        if not other:
            return self
        if isinstance(other, CodeItems):
            return CodeItems(self.codes + other.codes)
        return list(self) + list(other)

    def __radd__(self, other):
        if not other:
            return self
        return list(other) + list(self)

    def __eq__(self, other):
        if isinstance(other, CodeItems):
            return self.codes == other.codes
        return list(self) == other

    def __ne__(self, other):
        return not self == other

    __hash__ = None


class RangedSet(Language):
    """A character set kept as ranges and checked on them (check_script): its base characters (own)
    and auxiliary ones (shared), made into characters only when asked for. A script of Unicode is one
    (ScriptSet: Han has about 100,000 characters), and so is a large set of single characters, the Han
    repertoires' (Unihan Core 2020: 20,720): made into 90,000 characters and checked one by one, they
    were most of an opening's time, and a list of 20,000 read for each of a selection's 200 rows froze
    it for a second where Han's own selection took 30 ms."""

    def __init__(self, iso, name, group, own, shared=u"", optional=u"", definition=u""):
        self.own_ranges, self.shared_ranges = ranges_of(own), ranges_of(shared)
        self.own_count = sum(high - low + 1 for low, high in self.own_ranges)
        self.shared_count = sum(high - low + 1 for low, high in self.shared_ranges)
        self.lists = {}
        Language.__init__(self, iso, name, u"", group, u"set", u"", 0, None, None, u"", kind="set",
                          definition=definition)
        # Its optional characters (Arabic's presentation forms, Han's compatibility ideographs), among its own
        # and its shared ones: they never decide its level (check_script)
        self.optional = optional_codes(optional)
        self.optional_own = count_in_ranges(self.optional, self.own_ranges)
        self.optional_shared = count_in_ranges(self.optional, self.shared_ranges)
        self.optional_count = self.optional_own

    def size(self):
        return self.own_count

    def items(self, key, ranges):
        if key not in self.lists:
            self.lists[key] = [char_of(code) for low, high in ranges for code in range(low, high + 1)]
        return self.lists[key]

    # (Language sets both in its constructor: a ranged set's are made from its ranges, when asked for)
    base = property(lambda self: self.items("base", self.own_ranges), lambda self, value: None)
    auxiliary = property(lambda self: self.items("auxiliary", self.shared_ranges), lambda self, value: None)


RANGED_FROM = 1000  # characters: a set of single characters this large or larger is kept as ranges (RangedSet)


class ScriptSet(RangedSet):
    """A script of Unicode checked as a character set, for a font to be measured against a script no
    language here is written in (and against any other): its own characters (Unicode's Script
    property: letters, marks, digits, punctuation) are its base characters, and those Unicode says it
    shares with other scripts (Script_Extensions) its auxiliary ones. Both are kept as ranges, and
    made into characters only when asked for (Han has about 100,000)."""

    def __init__(self, name, own, shared, since=u"", group=SCRIPTS_GROUP, version=u"", optional=u""):
        RangedSet.__init__(self, u"script:%s" % name, name, group, own, shared, optional)
        self.since, self.unicode = since, version
        self.definition = (
            u"A script of Unicode%s: its own characters (letters, marks, digits, and punctuation, by Unicode's Script "
            u"property) are the measure, and the characters Unicode says it shares with other scripts "
            u"(Script_Extensions) count as auxiliary ones. Control and format characters are left out.%s%s" % (
                u" %s" % version if version else u"",
                u" Its %s, are listed as optional: it is complete without them." % OPTIONAL_WHAT if self.optional else u"",
                u" Encoded since Unicode %s." % since if since else u""))


COVERAGE_GAPS_FILE = "coverage_gaps.json"  # beside this script: checks/train/coverage_gaps.py makes it (optional)


class CoverageGaps(object):
    """What Font Check knows of and does not check (known: [(name, other names, why)]), and fonts to
    consider for what FreeLang cannot draw (resources: [(font, maker, license, page, what, caution,
    the ids of the sets and scripts it is for)]), from coverage_gaps.json; empty without the file."""

    def __init__(self, known=(), resources=()):
        self.known = [(u"%s" % row[0], [u"%s" % other for other in row[1]], u"%s" % row[2])
                      for row in known if len(row) >= 3]
        self.resources = [row for row in resources if len(row) >= 7]

    def known_matches(self, text):
        """[(name, why)] of the known gaps a search names: the text is a whole name or other name, or,
        from three characters on, part of one; the whole ones first."""
        text = fold(text).strip()
        if not text:
            return []
        found = []
        for name, others, why in self.known:
            names = [fold(name)] + [fold(other) for other in others]
            if text in names:
                found.append((0, name, why))
            elif len(text) >= 3 and any(text in one for one in names):
                found.append((1, name, why))
        return [(name, why) for _, name, why in sorted(found, key=lambda one: one[0])]

    def fonts_for(self, key):
        """[(font, license)] of the fonts to consider for the set or script of this id."""
        return [(u"%s" % row[0], u"%s" % row[2]) for row in self.resources if key in (row[6] or ())]


def load_coverage_gaps(path=None):
    """The CoverageGaps of coverage_gaps.json (read once per file version); an empty one without the file
    or for a file that cannot be read: Font Check checks as before, and says nothing of gaps."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), COVERAGE_GAPS_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return CoverageGaps()
    held = _LANGUAGES.get(path)
    if held is not None and held[0] == stamp:
        return held[1]
    try:
        data = read_data(path, stamp)
        found = CoverageGaps(data.get("known") or (), data.get("resources") or ())
    except (OSError, IOError, ValueError, KeyError, TypeError, AttributeError):
        found = CoverageGaps()
    _LANGUAGES[path] = (stamp, found)
    return found


def known_line(found):
    """What a search says of the gaps it names that Font Check knows of and does not check (found:
    CoverageGaps.known_matches): each, and why."""
    if not found:
        return u""
    return u" ".join(u"Font Check knows of %s, which it does not check: %s." % (name, why) for name, why in found)


def fonts_sentence(fonts):
    """A set's or a script's tooltip naming the fonts to consider for what FreeLang does not draw of it
    (fonts: [(font, license)]): never shipped with FreeLab, each a separate download."""
    if not fonts:
        return u""
    return u"Fonts to consider for the rest: %s." % u"; ".join(
        u"%s (%s, a separate download)" % (font, license_) for font, license_ in fonts)


SPACES_FILE = "space_conventions.json"  # beside this script: checks/train/spaces.py makes it from CLDR 49
# The spaces typesetting needs: the two no-break spaces (a row of the high-value list where a language the font
# covers or nearly covers groups its numbers with one), and the others a font is expected to have (a note)
NO_BREAK_SPACES = (0x00A0, 0x202F)
OTHER_SPACES = ((0x2007, u"figure"), (0x2009, u"thin"), (0x200A, u"hair"), (0x2002, u"en"), (0x2003, u"em"))
SPACE_WORDS = {0x00A0: u"no-break", 0x202F: u"narrow no-break"}


def masters_status(failing, glyphs, masters, reference, unread=0, b=lambda text: text):
    """The Masters view's status line: failing glyphs of glyphs that do not interpolate, of masters compared
    with the reference master; unread: glyph layers that could not be read. Each count bold with its noun
    ("**12 of the 2,000 glyphs**", "all **4 masters**": owner's images 297 and 301)."""
    if failing:
        text = u"%s %s interpolate, compared with %s." % (
            b(u"%s of the %s" % (u"{0:,}".format(failing), counted(glyphs, u"glyph"))),
            u"does not" if failing == 1 else u"do not", b(reference))
    else:
        text = (u"The %s %s in %s, compared with %s: contours, nodes, start points, directions, components, and "
                u"anchors." % (b(counted(glyphs, u"glyph")), u"matches" if glyphs == 1 else u"match",
                               u"both masters" if masters == 2
                               else u"all %s" % b(counted(masters, u"master")), b(reference)))
    if unread:
        text += u" %s could not be read." % b(counted(unread, u"glyph layer"))
    return text


def spaces_path():
    return os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), SPACES_FILE)


def space_conventions(path=None):
    """{code point: the ISO 639-3 codes of the languages that group thousands with that space} (CLDR), {}
    without the file."""
    path = path or spaces_path()
    try:
        data = read_data(path, os.path.getmtime(path))
    except (OSError, IOError, ValueError):
        return {}
    return dict((int(code, 16), set(isos)) for code, isos in (data.get("spaces") or {}).items())


def space_rows(results, has, conventions):
    """[AddRow] of the no-break spaces the font lacks (has(code): whether it has it) that languages it covers
    or nearly covers set in their numbers ("12 345": CLDR's grouping separator), each needed by those
    languages; it completes none (their letters decide that)."""
    rows = []
    for code in NO_BREAK_SPACES:
        if has(code):
            continue
        isos = conventions.get(code, ())
        needing = [r for r in results if r.level in ("covered", "nearly") and r.language.kind == "language"
                   and r.language.iso in isos]
        if needing:
            row = AddRow([char_of(code)], sorted(needing, key=language_rank), [])
            row.spacing = True
            rows.append(row)
    return rows


SPACES_LINK = u"freelab-spaces:"  # a log link's target: Glyph Compose opened on these spaces (hexadecimal, "-" between)


def spaces_link(codes):
    """The link of the spaces line (spaces_note): its target names the spaces, which Font Check's log hands
    to Glyph Compose (log_link, build_spaces) as its Build button hands glyphs over."""
    return u"%s%s" % (SPACES_LINK, u"-".join(u"%04X" % code for code in codes))


def linked_spaces(target):
    """The characters a spaces link names (spaces_link), or None for another link."""
    target = u"%s" % target
    if not target.startswith(SPACES_LINK):
        return None
    found = []
    for part in target[len(SPACES_LINK):].split(u"-"):
        try:
            found.append(char_of(int(part, 16)))
        except ValueError:
            continue
    return found


def spaces_note(has, listed=()):
    """The line the log gives the spaces the font lacks that no row lists (u"" for none): the no-break
    spaces first, then the figure, thin, hair, en, and em spaces. Glyph Compose named in it is a link
    that opens it with these spaces listed and ticked on its Glyph generation tab (owner's image 313: the
    tool's link opened it on its first tab, with nothing done)."""
    lacking = [(code, SPACE_WORDS[code]) for code in NO_BREAK_SPACES if not has(code) and code not in listed]
    lacking += [(code, word) for code, word in OTHER_SPACES if not has(code)]
    if not lacking:
        return u""
    one = len(lacking) == 1
    names = [u"%s (U+%04X)" % (word, code) for code, word in lacking]
    link = u'<a href="%s"><i>Glyph Compose</i></a>' % spaces_link([code for code, _ in lacking])
    return (u"The font lacks %s %s: %s. %s builds %s (empty glyphs of the right width): click it to list %s on "
            u"its <i>Glyph generation</i> tab, ticked." % (
                u"this" if one else u"these", u"space" if one else u"spaces", u", ".join(names), link,
                u"it" if one else u"them", u"it" if one else u"them"))


DECLARE_BUTTON = u"Declare coverage"  # the Coverage tab's button that sets the font info to what the font covers
# Build with Glyph Compose: the rows handed over start ticked there (Recipe.checked), and a build that leaves
# none of them to build opens Font Check again in that window's place (Glyph Compose's back_to_font_check)
HANDOFF_HELP = (u"Opens <i>Glyph Compose</i> on the ticked glyphs of the tab of glyphs shown that it can build from "
                u"the font's glyphs, listed alone and ticked: glyphs with diacritics on its <i>Diacritics</i> tab, "
                u"other glyphs (spaces, dashes, quotes...) on its <i>Glyph generation</i> tab. It opens on the tab "
                u"with more, and its log says what the other holds. Nothing is made until you click <i>Build ticked "
                u"glyphs</i> there; once every glyph handed over is built, <i>Font Check</i> opens again in its place.")
DECLARE_LINK = u"freelab-declare-coverage:"  # a log link's target: the font info set to declare what the font covers
COVERAGE_KEYS = (("unicode_ranges", "openTypeOS2UnicodeRanges", u"Unicode ranges"),
                 ("code_pages", "openTypeOS2CodePageRanges", u"code pages"))


def declared_coverage(module, ranges, pages, codes):
    """What the font info would declare to say what the font covers, by the rules FreeLab's tools keep it
    with after their writes (freelab_font_info: a Unicode range with a character of it, a code page with
    every letter of it; the code pages FreeLab leaves alone kept as declared): {key: (now, new)} of the
    fields that differ, empty when it says so already."""
    measured = module.coverage(codes)
    managed = module.managed_pages()
    new = {"unicode_ranges": sorted(measured[module.INFO_UNICODE]),
           "code_pages": sorted(set(bit for bit in pages if bit not in managed) | measured[module.INFO_PAGES])}
    now = {"unicode_ranges": sorted(set(ranges)), "code_pages": sorted(set(pages))}
    return dict((key, (now[key], new[key])) for key in new if now[key] != new[key])


def coverage_differences(module, differences):
    """The fields that differ, for the log (plain text): "Unicode ranges (not declared: Hangul Syllables;
    declared without a glyph: Arabic); code pages (not declared: Korean Wansung (949))"."""
    parts = []
    for key, _attribute, label in COVERAGE_KEYS:
        if key not in differences:
            continue
        now, new = differences[key]
        name = module.range_name if key == "unicode_ranges" else module.page_name
        words = []
        missing = [bit for bit in new if bit not in now]
        extra = [bit for bit in now if bit not in new]
        if missing:
            words.append(u"not declared: %s" % u", ".join(name(bit) for bit in missing))
        if extra:
            words.append(u"declared, %s: %s" % (u"without a glyph of it" if key == "unicode_ranges" else u"not complete",
                                                u", ".join(name(bit) for bit in extra)))
        parts.append(u"%s (%s)" % (label, u"; ".join(words)))
    return u"; ".join(parts)


def declared_note(module, differences, html):
    """The log's line when the font info's coverage differs from the font's glyphs, naming the Coverage tab's
    button that declares it (u"" when it does not differ)."""
    if not differences:
        return u""
    # (the button, in the bottom row, rather than a link the log alone showed: owner's image 372)
    return (u"The font info's coverage differs from the glyphs: %s. <i>%s</i> declares what the font covers "
            u"(<i>Edit &gt; Undo</i> takes it back)." % (html(coverage_differences(module, differences)), DECLARE_BUTTON))


def families_path():
    return os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), FAMILIES_FILE)


class Families(object):
    """Glottolog's classification of the languages (checks/train/families.py makes the file): for each
    ISO 639-3 code, the family and branches above the language; its other names; and the languages
    with a code that Hyperglot does not describe, for a search to say why one is not listed."""

    def __init__(self, nodes=(), places=None, aliases=None, unlisted=(), isolates=u"", counts=None):
        self.nodes, self.places, self.aliases = list(nodes), places or {}, aliases or {}
        # unlisted: [[code, name, [other names], its family's node or -1 (a file made before: no fourth)]]
        self.unlisted, self.isolates = list(unlisted), isolates
        self.paths, self.unlisted_folded = {}, None
        self.counts = counts or {}  # what the file counts: Glottolog's languages, those with a code, ...
        self.by_family = None  # {family's name: [Uncovered]}, made when first asked

    def uncovered(self):
        """{family's name: [Uncovered]}: the languages known and not described, under the family
        each belongs to (UNCLASSIFIED for those Glottolog files under none), A to Z; {} for a file
        that does not say (made before the families of these languages were kept)."""
        if self.by_family is None:
            found = {}
            for row in self.unlisted:
                if len(row) < 4:
                    continue
                try:
                    family = u"%s" % self.nodes[row[3]][0] if row[3] >= 0 else UNCLASSIFIED
                except (IndexError, TypeError):
                    family = UNCLASSIFIED
                found.setdefault(family, []).append(Uncovered(u"%s" % row[0], u"%s" % row[1], row[2], family))
            for entries in found.values():
                entries.sort(key=lambda one: (fold(one.name), one.iso))
            self.by_family = found
        return self.by_family

    def path(self, iso):
        """The names of the family and branches above a language, the family first; () for a code
        Glottolog does not classify."""
        if iso not in self.paths:
            names, at = [], self.places.get(iso, -1)
            while 0 <= at < len(self.nodes) and len(names) < 64:  # (64: no loop, whatever the file holds)
                names.append(u"%s" % self.nodes[at][0])
                at = self.nodes[at][1]
            self.paths[iso] = tuple(reversed(names))
        return self.paths[iso]

    def unlisted_matches(self, text):
        """[(code, name, the other name it was found by or None)] of the languages Hyperglot does not
        describe that a search names: the text is its code or its name, or, from three characters on,
        part of its name or of one of its other names; those whose own name fits best first."""
        text = fold(text).strip()
        if not text:
            return []
        if self.unlisted_folded is None:  # (its other names a line each, a line break at each end: a whole one is found so)
            self.unlisted_folded = [(u"%s" % row[0], fold(row[1]), u"\n%s\n" % fold(u"\n".join(row[2])))
                                    for row in self.unlisted]
        whole = u"\n%s\n" % text
        found = []
        for index, (iso, name, others) in enumerate(self.unlisted_folded):
            if text == iso or text == name:
                rank, alias = (0 if text == iso else 1), None
            elif len(text) < 3:
                continue
            elif whole in others:  # (Kung, a whole other name of several Ju languages: before Kungarakany)
                rank, alias = 2, next((other for other in self.unlisted[index][2] if text == fold(other)), None)
            elif text in name:
                rank, alias = (3 if name.startswith(text) else 4), None
            elif text in others:
                rank, alias = 5, next((other for other in self.unlisted[index][2] if text in fold(other)), None)
            else:
                continue
            found.append((rank, name, u"%s" % iso, u"%s" % self.unlisted[index][1], alias))
        return [(iso, name, alias) for _, _, iso, name, alias in sorted(found, key=lambda one: one[:3])]


def load_families(path=None):
    """The Families of language_families.json (read once per file version); None without the file:
    the languages are then listed without families and found by their own names only."""
    path = path or families_path()
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return None
    held = _LANGUAGES.get(path)
    if held is not None and held[0] == stamp:
        return held[1]
    data = read_data(path, stamp)
    found = Families(data["nodes"], data["languages"], data.get("aliases"), data.get("unlisted", ()),
                     u"%s" % data.get("isolates", u""), data.get("counts"))
    _LANGUAGES[path] = (stamp, found)
    return found


class KnownScripts(object):
    """What the orthographies file says of the scripts beyond its rows: how many scripts Unicode
    has, which of them no orthography here is written in (known, not yet covered), and, for
    languages no source gives characters for, the scripts a source says they are written in."""

    def __init__(self, known=0, not_covered=(), of_languages=None, unicode=u""):
        self.known, self.not_covered, self.unicode = known, [u"%s" % name for name in not_covered], unicode
        self.of_languages = of_languages or {}  # ISO 639-3 code: [scripts' names]


def load_known_scripts(path=None):
    """The KnownScripts of language_orthographies.json (read once per file version); an empty one
    without the file or for a file that does not say."""
    path = path or orthographies_path()
    key = (path, "scripts")
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return KnownScripts()
    held = _LANGUAGES.get(key)
    if held is not None and held[0] == stamp:
        return held[1]
    try:
        said = read_data(path, stamp).get("scripts") or {}
        of_languages = {}
        for script, codes in sorted((said.get("of_other_languages") or {}).items()):
            for iso in codes.split():
                of_languages.setdefault(u"%s" % iso, []).append(u"%s" % script)
        found = KnownScripts(int(said.get("known") or 0), said.get("not_covered") or (), of_languages,
                             u"%s" % (said.get("unicode") or u""))
    except (OSError, IOError, ValueError, KeyError, TypeError, AttributeError):
        found = KnownScripts()
    _LANGUAGES[key] = (stamp, found)
    return found


def name_languages(languages, families):
    """Each language given its other names (Glottolog's, by its code), for a search; none without the
    families file."""
    for language in languages:
        aliases = tuple(families.aliases.get(language.iso, ())) if families is not None else ()
        if tuple(language.aliases) != aliases:
            language.aliases, language.folded = aliases, None
    return languages


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


def normal_form(form, text):
    """unicodedata.normalize, but a text with a code point past U+FFFF is left as it is, on every
    Python: FontLab's narrow Python 2 normalizes none of them, and the counts must be the same there
    as in the tests."""
    if any(code > 0xFFFF for code in code_points(text)):
        return text
    return unicodedata.normalize(form, text)


def support(item, font):
    """How a font has one of a language's characters: HAVE (its own glyph), COMPOSED (its letter and
    marks, which its anchors put together), PARTS (its letter and marks, but no anchors that join
    them), or MISSING. A letter with two marks may stand on a letter with one (e with macron, then
    acute). A single character is had by its own code point only, never through another one it is
    canonically the same as (the letters with oxia through those with tonos, the ohm sign through
    omega, a compatibility ideograph through its unified one): only a sequence of a letter and marks
    is had by the character it composes to."""
    codes = code_points(item)
    if len(codes) == 1 and codes[0] in font.codes:
        return HAVE, None
    if len(codes) > 1:
        composed = code_points(normal_form("NFC", item))
        if len(composed) == 1 and composed[0] in font.codes:
            return HAVE, None  # (listed decomposed)
    parts = code_points(normal_form("NFD", item))
    if len(parts) < 2 or not all(is_mark(code) for code in parts[1:]):
        return MISSING, None
    for size in range(len(parts) - 1, 0, -1):
        base = code_points(normal_form("NFC", u"".join(char_of(code) for code in parts[:size])))
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
    """How a font covers a language: level is "covered", "nearly" (within reach), "started" (the font
    has at least one of its characters, but it is not within reach), or "missed" (it has none)."""

    def __init__(self, language, missing, auxiliary_missing, marks_missing, composed, parts, level, have=0,
                 optional_missing=None):
        self.language = language
        self.missing, self.auxiliary_missing, self.marks_missing = missing, auxiliary_missing, marks_missing
        self.composed = composed  # [(character, (letter, marks))]: counted, made of the font's letter and marks
        self.parts = parts  # missing characters whose letter and marks the font has, without anchors joining them
        self.level = level
        self.have = have  # how many of its characters (base, auxiliary, marks) the font has or composes
        self.found_by = None  # the other name a search found it by (set as the list is filled), or None
        # A set's optional characters the font lacks (presentation forms, compatibility characters): listed and
        # counted, never in the level, the languages gained, or the high-value glyphs (needs() leaves them out)
        self.optional_missing = optional_missing if optional_missing is not None else []

    def base_missing(self):
        return len(self.missing) + len(self.marks_missing)

    def all_missing(self):
        """Every missing character: base, marks, auxiliary, then the optional ones."""
        return self.missing + self.marks_missing + self.auxiliary_missing + self.optional_missing


LEVELS = (("nearly", u"Within reach"), ("covered", u"Covered"), ("started", u"Started"), ("missed", u"Missed"))
BAR_LEVELS = ("covered", "nearly", "started", "missed")  # a bar's segments, in order: green, amber, red, gray


def check_language(language, font, nearly=NEARLY_MISSING):
    """A language or a character set checked. A set's optional characters (language.optional) are
    looked for and counted apart (optional_missing), and never decide its level or what it has: a set
    is covered without them, and one wholly optional (the Legacy group's) is always covered, its row
    saying how many of them the font lacks. Its level says whether text set in the font needs anything
    more, which a presentation form or a compatibility character never is."""
    missing, auxiliary_missing, composed, parts, optional_missing = [], [], [], [], []
    optional = language.optional
    for items, into in ((language.base, missing), (language.auxiliary, auxiliary_missing)):
        for item in items:
            how, recipe = font.support(item)
            if how == COMPOSED:
                composed.append((item, recipe))
            elif how != HAVE:
                codes = code_points(item) if optional else ()
                if len(codes) == 1 and codes[0] in optional:
                    optional_missing.append(item)
                    continue
                into.append(item)
                if how == PARTS:
                    parts.append(item)
    marks = code_points(language.marks or u"")
    marks_missing = [char_of(code) for code in marks if code not in font.codes]
    short = len(missing) + len(marks_missing)
    have = (len(language.base) - language.optional_count - len(missing) + len(language.auxiliary)
            - len(auxiliary_missing) + len(marks) - len(marks_missing))
    # Below the threshold of "within reach", one character or more is a start (red); none at all, gray.
    level = ("covered" if not short and not auxiliary_missing else "nearly" if short <= nearly
             else "started" if have > 0 else "missed")
    return Coverage(language, missing, auxiliary_missing, marks_missing, composed, parts, level, have, optional_missing)


def check_script(script, font, nearly=NEARLY_MISSING):
    """A ScriptSet (or another RangedSet) checked as check_language checks a set, on its ranges: no character is made but
    the missing ones that may be composed. Its own characters missing are the base ones missing, the
    shared ones the auxiliary ones; a letter the font's anchors compose counts, looked for when the
    font has some of the script and misses at most SCRIPT_COMPOSE_MOST of it (Han's ideographs and
    Hangul's syllables decompose into no letter and marks)."""
    codes = font.codes
    missing = [code for low, high in script.own_ranges for code in range(low, high + 1) if code not in codes]
    shared = [code for low, high in script.shared_ranges for code in range(low, high + 1) if code not in codes]
    optional_missing = []
    if script.optional:  # (its optional characters: counted apart, never in its level)
        optional = script.optional
        optional_missing = [code for code in missing + shared if code in optional]
        missing = [code for code in missing if code not in optional]
        shared = [code for code in shared if code not in optional]
    own_count = script.own_count - script.optional_own  # (the own characters it needs)
    composed, parts = [], []
    if len(missing) < own_count and len(missing) <= SCRIPT_COMPOSE_MOST:
        kept = []
        for code in missing:
            item = char_of(code)
            how, recipe = font.support(item)
            if how == COMPOSED:
                composed.append((item, recipe))
            elif how != HAVE:
                kept.append(code)
                if how == PARTS:
                    parts.append(item)
        missing = kept
    have = own_count - len(missing) + script.shared_count - script.optional_shared - len(shared)
    # Started or missed by its own characters alone: the shared ones (U+00B7, a Latin font has it) are
    # other scripts' too, and made Han and Carian "started" in a font with none of theirs. They still
    # count in have, and as the auxiliary ones missing.
    level = ("covered" if not missing and not shared else "nearly" if len(missing) <= nearly
             else "started" if len(missing) < own_count else "missed")
    return Coverage(script, CodeItems(missing), CodeItems(shared), [], composed, parts, level, have,
                    CodeItems(optional_missing))


def check_entry(one, font, nearly=NEARLY_MISSING):
    """A language or a character set checked; a script's set, or another set kept as ranges, by its ranges."""
    if isinstance(one, RangedSet):
        return check_script(one, font, nearly)
    return check_language(one, font, nearly)


def level_counts(results):
    """How many of the coverages are at each level, in a bar's order (BAR_LEVELS)."""
    counts = dict((level, 0) for level in BAR_LEVELS)
    for r in results:
        counts[r.level] = counts.get(r.level, 0) + 1
    return [counts[level] for level in BAR_LEVELS]


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
    elif result.level in ("started", "missed"):
        rest = (result.base_missing(), 0)
    else:
        rest = (0, 0)
    return (order[result.level], rest, -(language.speakers or 0), language.name)


HIGH_VALUE = "high-value"  # the Display choice that keeps the languages of high value (is_high_value), not a status
STATUS_FILTERS = (("current", u"Living and constructed", ("living", "constructed", NOT_GIVEN)),
                  ("living", u"Living only", ("living", NOT_GIVEN)),
                  ("historical", u"Historical only", ("historical",)),
                  ("high", u"High-value only", HIGH_VALUE),
                  ("all", u"All languages", None))
# The Display dropdown (it was named Languages, and each of its choices said "languages" again). Hyperglot's
# status of a language: living, historical (no native speakers left: Latin, Ancient Greek), or constructed
# (Esperanto). The other sources say less: historical where Google's data says so, constructed where Glottolog
# files the language under Artificial Language, and no status otherwise (NOT_GIVEN), which counts with the
# living ones. None keeps every status; HIGH_VALUE keeps the orthographies high_value_languages.json lists
# (checks/train/high_value.py: CLDR's modern coverage, official status, or a million people who read and write
# the language); the dialog starts with STATUS_START, and coverage() without a choice keeps the first one's.
STATUS_START = "all"
STATUS_TITLES = {"living": u"Living languages", "historical": u"Historical languages",
                 "constructed": u"Constructed languages", NOT_GIVEN: u"Languages of no given status"}
LESSER_TITLE = u"Other languages"  # the heading of the languages High-value only leaves out, in a search
HIGH_VALUE_FILE = "high_value_languages.json"  # beside this script: checks/train/high_value.py makes it from CLDR
_HIGH_VALUE = {}  # {path: (its date, its table)}: made once per file version


def high_value_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), HIGH_VALUE_FILE)


def high_value_orthographies(path=None):
    """{(ISO 639-3 code, script label): its reasons} of the orthographies of high value; {} without the
    file (High-value only then keeps none, and says so)."""
    path = path or high_value_path()
    try:
        stamp = os.path.getmtime(path)
        held = _HIGH_VALUE.get(path)
        if held is None or held[0] != stamp:
            data = read_data(path, stamp)
            held = _HIGH_VALUE[path] = (stamp, dict(((u"%s" % row[0], u"%s" % row[1]), tuple(row[2]))
                                                    for row in data["orthographies"]))
        return held[1]
    except (OSError, IOError, ValueError, KeyError, IndexError, TypeError):
        return {}


def is_high_value(language, table=None):
    """Whether a language's orthography is of high value (high_value_orthographies)."""
    table = high_value_orthographies() if table is None else table
    return (language.iso, language.script) in table


def kept_by(language, statuses, table=None):
    """Whether the Display choice (STATUS_FILTERS' third part: statuses, HIGH_VALUE, or None for all)
    keeps a language."""
    if statuses is None:
        return True
    if statuses == HIGH_VALUE:
        return is_high_value(language, table)
    return language.status in statuses
# The check box of the languages no source declares, and the heading of those it leaves out, in a
# search. It was "Languages inferred from text"; the keyboard layouts are no source's declaration
# either, so it holds them too (one check box more would crowd the settings row for 41 rows).
INFERRED_TITLE = u"Languages from texts and keyboards"


def chosen_languages(languages, inferred=True):
    """(the languages checked, those set aside): every language, or, with inferred off, only those
    whose characters a source declares; the ones inferred from counting a text and those read from
    a keyboard layout are set aside (a search still finds them, under a heading that says why they
    are not listed)."""
    if inferred:
        return list(languages), []
    return ([language for language in languages if language.evidence not in UNDECLARED],
            [language for language in languages if language.evidence in UNDECLARED])


def inferred_sentence(counted_in, aside=0, bold=None):
    """What the Coverage view's top line says of the languages inferred from a text or read from a
    keyboard layout: how many of the languages covered or within reach are (counted_in), or how many
    the check box sets aside (aside); nothing when there are none. Whole sentences, in the count's
    number; bold: what makes a count bold."""
    bold = bold or (lambda text: text)
    if counted_in:
        return (u" Of those covered or within reach, %s %s inferred from text or read from a keyboard layout, "
                u"not declared by a source (%s)." % (
                    bold(u"%d" % counted_in), u"is" if counted_in == 1 else u"are",
                    u"its row says so" if counted_in == 1 else u"their rows say so"))
    if aside:
        return u" %s from texts and keyboards %s left out." % (bold(counted(aside, u"language")),
                                                               u"is" if aside == 1 else u"are")
    return u""


def left_title(language, statuses=None):
    """The heading a language left out of the lists comes under, in a search (statuses: the Display
    choice's; a language High-value only leaves out comes under LESSER_TITLE, whatever its status)."""
    if language.evidence in UNDECLARED:
        return INFERRED_TITLE
    if statuses == HIGH_VALUE:
        return LESSER_TITLE
    return STATUS_TITLES.get(language.status, u"%s" % language.status)


# The scripts' groups: one per script of Unicode. Hyperglot labels some orthographies with names that
# are no script of their own: Cree, Inuktitut Syllabics, and Ojibwe Syllabics are written in Unicode's
# Canadian Aboriginal script, which Hyperglot itself calls Canadian Syllabics; Chinese, Hanja, and Kanji
# are all Han. Each became a script of its own in the list (Plains Cree alone under Cree, Inuktitut alone
# under Inuktitut Syllabics). A language keeps its own label (language.script: what its row's tooltip
# says, what tells two orthographies apart); the lists, the bars, and the counts go by its group. The other
# labels are one per Unicode script already, under another name than Unicode's at most (Burmese for
# Myanmar, Ge'ez for Ethiopic, Modern Yi for Yi): those are left as they are.
SCRIPT_GROUPS = {u"Cree": u"Canadian Syllabics", u"Inuktitut Syllabics": u"Canadian Syllabics",
                 u"Ojibwe Syllabics": u"Canadian Syllabics",
                 u"Chinese": u"Han", u"Hanja": u"Han", u"Kanji": u"Han"}


def script_group(label):
    """The group (one per Unicode script) a script's label is listed under: itself, or the one
    SCRIPT_GROUPS names."""
    return SCRIPT_GROUPS.get(label, label)


def coverage(languages, font, nearly=NEARLY_MISSING, historical=False, statuses=None):
    """[ScriptCoverage], the scripts the font has first (those with the most languages covered or
    within reach first); within each, the languages within reach first (the fewest missing first),
    then the covered ones, then the missed ones, the most spoken first. statuses: the statuses kept
    (None: living and constructed, and historical too when historical is set). A script is a group of
    labels, one per Unicode script (script_group)."""
    if statuses is None and not historical:
        statuses = STATUS_FILTERS[0][2]
    by_script = {}
    for language in languages:
        if not kept_by(language, statuses):
            continue
        by_script.setdefault(script_group(language.script), []).append(check_language(language, font, nearly))
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


def left_out(languages, font, nearly=NEARLY_MISSING, statuses=None, aside=()):
    """[Coverage] of the languages a choice of statuses leaves out of coverage(), and of those set
    aside (aside: the inferred ones, with their check box off): a search still finds them, under a
    heading that says why they are not listed."""
    found = [] if statuses is None else [language for language in languages if not kept_by(language, statuses)]
    return [check_language(language, font, nearly) for language in found + list(aside)]


SORTS = (("reach", u"Within reach first"), ("most", u"Most covered first"), ("least", u"Least covered first"),
         ("az", u"A to Z"), ("za", u"Z to A"))


def name_key(result):
    """A language's name to sort by: any case, its diacritics set aside (an O with a dieresis with the O's)."""
    name = unicodedata.normalize("NFD", u"%s" % result.language.name)
    return (u"".join(c for c in name if not unicodedata.category(c).startswith(u"M")).lower(), result.language.name)


def covered_key(result):
    """Covered, then within reach, then started, then missed; within each, the fewest characters
    missing first, the optional ones last of all (they only break a tie)."""
    return (BAR_LEVELS.index(result.level) if result.level in BAR_LEVELS else len(BAR_LEVELS),
            result.base_missing(), len(result.auxiliary_missing), len(result.optional_missing))


def sort_languages(results, sort="reach"):
    """The languages of one section in the order chosen (SORTS): "reach" is coverage()'s own (what
    is nearly there first); "most" and "least" go by coverage, the names in order within a tie; "az" and
    "za" by name."""
    if sort == "most":
        return sorted(results, key=lambda r: (covered_key(r), name_key(r)))
    if sort == "least":
        return sorted(results, key=lambda r: (tuple(-value for value in covered_key(r)), name_key(r)))
    if sort == "az":
        return sorted(results, key=name_key)
    if sort == "za":
        return sorted(results, key=name_key, reverse=True)
    return sorted(results, key=coverage_order)


def buildable_candidates(results, ranges):
    """The missing characters of the given coverages a letter-and-marks builder may make: single
    characters in the ranges [(low, high)] that decompose into a letter and marks, and the combining
    marks the languages need (in order, once)."""
    found = []
    for r in results:
        # (the first WANTED_MOST of each: what a selection's tab may list; a script's set may miss 100,000)
        for item in list(r.missing[:WANTED_MOST]) + list(r.auxiliary_missing[:WANTED_MOST]) + list(r.marks_missing):
            codes = code_points(item)
            if len(codes) == 1 and 0x0300 <= codes[0] < 0x0370 and item not in found:
                found.append(item)  # a combining mark: Glyph Compose makes it of the mark it comes from (macron below of the macron)
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


def in_masters(extents_or_count):
    """"in every master", or "in the single master" for a font with one (a count of masters, or the
    extents measured): a sentence about every master read wrong in a font that has only one."""
    try:
        count = int(extents_or_count)
    except (TypeError, ValueError):
        count = len(set(e.master for e in extents_or_count))
    return u"in the single master" if count == 1 else u"in every master"


def measured_text(masters):
    """The Vertical metrics tab's first line, for a font with that many masters."""
    return u"Every glyph measured %s." % in_masters(masters)


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
        notes.append(u"winAscent and winDescent reach the highest and lowest ink of every glyph %s." % in_masters(extents))
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
    # (no button is named "Fix": they are Fix ticked glyphs and Fix this, so the tool is named instead)
    if not left:
        return u"Font Check can set %s right." % word_list(fixes)
    rest = u"%s %s the designer" % (word_list(left), u"needs" if len(left) == 1 else u"need")
    if not fixes:
        return u"Needs the designer: %s." % word_list(left)
    return u"Font Check can set %s right; %s." % (word_list(fixes), rest)


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


def row_label(row):
    """A high-value row's Glyph column: its character's short name over its code points ("r with caron",
    "U+0158 U+0159": a capital and its small letter go by the small one's name). A character the runtime's
    Unicode data cannot name (FontLab's Python 2.7 has Unicode 5.2: U+A7CB is of 13.0) goes by its code
    points alone, once: the name's line had repeated them ("U+A7CB" over "U+A7CB")."""
    item = row.items[-1] if len(row.items) > 1 else row.items[0]
    name, codes = short_name(item), u" ".join(code_label(one) for one in row.items)
    if not name or name == code_label(item) or name == codes:
        return codes
    return u"%s\n%s" % (name, codes)


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
                        rest = head.upper() + (u" " + tail if tail else u"")
                    else:
                        rest = u"capital " + rest
                # The script's name goes, its style stays: CIRCLED LATIN SMALL LETTER A read "a" (live, the
                # first high-value row of Noto Sans, beside its capital)
                style = name_style(name[:at])
                return u"%s %s" % (style, rest) if style else rest
    return name.lower()


# Words before a script's name in a character's Unicode name that say how the letter is drawn (kept in its
# short name: "circled a", "full-width A"), as opposed to the script's own name (left out: "r with caron")
NAME_STYLES = {u"CIRCLED": u"circled", u"PARENTHESIZED": u"parenthesized", u"NEGATIVE": u"negative",
               u"SQUARED": u"squared", u"FULLWIDTH": u"full-width", u"HALFWIDTH": u"half-width",
               u"MATHEMATICAL": u"mathematical", u"BOLD": u"bold", u"ITALIC": u"italic", u"SANS-SERIF": u"sans-serif",
               u"DOUBLE-STRUCK": u"double-struck", u"MONOSPACE": u"monospace", u"FRAKTUR": u"fraktur",
               u"SCRIPT": u"script", u"TAG": u"tag", u"REGIONAL": u"regional", u"INDICATOR": u"indicator",
               u"SYMBOL": u"symbol", u"SUPERSCRIPT": u"superscript", u"SUBSCRIPT": u"subscript"}


def name_style(prefix):
    """The style words leading a name's part before its case word ("CIRCLED LATIN" gives "circled"), u"" for
    a script's name alone ("LATIN", "OLD ITALIC": a style word after a script's first word is the script's)."""
    words = []
    for word in prefix.split():
        if word not in NAME_STYLES:
            break
        words.append(NAME_STYLES[word])
    return u" ".join(words)


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
    """A row of a tab of characters: a missing character (a capital and its small letter together when both
    are missing), the languages within reach that need it, and those it completes on its own."""

    def __init__(self, items, needing, completing, optional=False):
        self.items, self.needing, self.completing = items, needing, completing
        self.spacing = False  # a no-break space the languages set in their numbers (space_rows)
        self.optional = optional  # a set's optional character (selection_rows: listed after the others, marked)

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
    rows = rows_of(needing, order)
    rows.sort(key=lambda row: (-len(row.completing), -len(row.needing), code_points(row.items[0])))
    return rows


def rows_of(needing, order):
    """[AddRow] of the characters in order, by code point, a capital with its small letter; needing:
    {character: the coverages that need it}."""
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
        # (the count first: a script's set may need 100,000 characters, which no row completes)
        completing = [r for r in languages if len(needs(r)) <= len(own) and set(needs(r)) <= own]
        rows.append(AddRow(items, sorted(languages, key=language_rank), sorted(completing, key=language_rank)))
    return rows


class Selection(object):
    """What is selected in the list at the right: a language, a character set, or a family (kind
    "language", "set", or "family"), its name, the coverages it stands for (one, or a family's
    languages), and a key that finds it again once the lists are filled anew."""

    def __init__(self, kind, name, results, key):
        self.kind, self.name, self.results, self.key = kind, name, list(results), key

    def wanted(self):
        """The characters it misses, in order, once each: what each of its languages not covered
        needs (the first WANTED_MOST of each: a script's set may miss 100,000, and its own tab lists a
        few hundred; count() counts them all)."""
        found, seen = [], set()
        for r in self.results:
            if r.level == "covered":
                continue
            for item in needs(r)[:WANTED_MOST]:
                if item not in seen:
                    seen.add(item)
                    found.append(item)
        return found

    def count(self):
        """How many characters it misses: wanted()'s, and those past WANTED_MOST of a large set."""
        beyond = sum(max(0, len(needs(r)) - WANTED_MOST) for r in self.results if r.level != "covered")
        return len(self.wanted()) + beyond

    def optional(self):
        """The optional characters it misses (a set's or a script's: presentation forms, compatibility
        characters), the first WANTED_MOST of each, in order, once each: never in wanted()."""
        found, seen = [], set()
        for r in self.results:
            for item in r.optional_missing[:WANTED_MOST]:
                if item not in seen:
                    seen.add(item)
                    found.append(item)
        return found

    def optional_count(self):
        """How many optional characters it misses, all of them."""
        return sum(len(r.optional_missing) for r in self.results)


def same_results(one, other):
    """Whether two lists hold the same coverages, the same objects in any order (a Selection made again
    from the rows of the same check: a family's, sorted otherwise)."""
    return len(one) == len(other) and set(id(r) for r in one) == set(id(r) for r in other)


def selection_of(r):
    """The Selection of one language or character set (None for None)."""
    if r is None:
        return None
    return Selection("set" if r.language.kind == "set" else "language", r.language.name, [r], language_key(r))


def selection_rows(rows, selection, most=FLOAT_MOST):
    """(rows, left): the rows of the selection's own tab, the missing characters of the language, set,
    or family selected and nothing else. Those the high-value list has come first, as they are there
    and in its order (their +N counts every language); the characters no row there has (a started or
    missed language's, a character set's, another script's) get rows of their own after them, those
    that complete the most of the selection's languages first, then by code point, at most `most`
    characters of them (left: how many more it misses). A set's optional characters missing come last,
    marked optional (AddRow.optional), as many as `most` still allows. With nothing selected or missing,
    no rows."""
    wanted = selection.wanted() if selection is not None else []
    if not wanted:
        rows, left = [], 0
    else:
        rows, left = required_rows(rows, selection, wanted, most)
    optional = selection.optional() if selection is not None else []
    if optional:
        room = max(0, most - sum(len(row.items) for row in rows))  # (the required ones first: what is left of most)
        shown = optional[:room]
        rows = rows + [AddRow([item], [], [], True) for item in sorted(shown, key=code_points)]
        left += selection.optional_count() - len(shown)
    return rows, left


def required_rows(rows, selection, wanted, most):
    """selection_rows' rows of the characters a selection needs (wanted), and how many more it misses."""
    needed = set(wanted)
    own = [row for row in rows if needed & set(row.items)]
    listed = set(item for row in own for item in row.items)
    new = [item for item in wanted if item not in listed]
    needing = dict((item, []) for item in new)
    for r in selection.results:
        if r.level != "covered":
            for item in needs(r)[:WANTED_MOST]:
                if item in needing and r not in needing[item]:
                    needing[item].append(r)
    fresh = rows_of(needing, new)
    fresh.sort(key=lambda row: (-len(row.completing), -len(row.needing), code_points(row.items[0])))
    more, count = [], 0
    for row in fresh:
        if count + len(row.items) > most:
            break  # (whole rows: a capital stays with its small letter)
        more.append(row)
        count += len(row.items)
    return own + more, len(new) - count + selection.count() - len(wanted)


def selection_text(selection, left, b=None):
    """The line over the selection's own tab: whose missing characters it lists, how many, and how to
    unselect (b: how its name, and each count with its noun, are set in rich text: owner's images 297, 301)."""
    if selection is None:
        return u""
    c = b or (lambda text: text)
    name = c(selection.name)
    count = selection.count()
    if selection.kind == "family":
        short = sum(1 for r in selection.results if r.level != "covered")
        if not count:
            return u"%s: the font covers %s." % (name, u"its %s" % c(u"1 language") if len(selection.results) == 1 else
                                                 u"all its %s" % c(counted(len(selection.results), u"language")))
        text = u"%s: its %s not covered %s %s." % (
            name, c(counted(short, u"language")), u"misses" if short == 1 else u"miss", c(counted(count, u"glyph")))
    else:
        optional = selection.optional_count()  # (a set's optional glyphs: listed after the others, marked so)
        if not count and not optional:
            return u"%s misses nothing." % name
        if not optional:
            text = u"%s misses %s." % (name, c(counted(count, u"glyph")))
        elif not count:
            text = u"%s misses no glyph it needs, but %s (%s)." % (
                name, c(counted_grouped(optional, u"optional glyph")), OPTIONAL_WHAT)
        else:
            text = u"%s misses %s, and %s, listed after them." % (
                name, c(counted_grouped(count, u"glyph")), c(counted_grouped(optional, u"optional glyph")))
        count += optional
    if left:  # (numbers with no noun of their own: bold alone)
        text += u" %s %s not listed (the first %s are)." % (
            c(grouped(left)), u"more is" if left == 1 else u"more are", c(grouped(count - left)))
    return text + u" Click it again, or an empty part of its list, to unselect it."


def selection_title(selection):
    """The selection tab's caption: the selection's name and how many characters it misses, or what
    to do while nothing is selected."""
    if selection is None:
        return UNSELECTED_TITLE
    return u"%s (%s)" % (selection.name, grouped(selection.count() + selection.optional_count()))  # (all its tab lists)


# The grayed tab's caption: what to do, since the tab works on a family or a character set as well.
UNSELECTED_TITLE = u"Select language, character set, or family"


def value_title(count):
    """The high-value tab's caption, with its count of rows (None: not known yet, no count)."""
    if count is None:
        return u"High-value missing glyphs"
    return u"High-value missing glyphs (%s)" % grouped(count)  # (thousands grouped: image 231)


BUSY_STEPS = (u"Reading the language data", u"Reading the font", u"Checking the languages", u"Listing")
# The progress bar (the window's top row: ak.busy_start): the share of its length reached as each step
# ends. The first three are the Python side (about a third of a second in all); the listing is Qt's and
# takes most of the time.
BUSY_SHARES = (0.10, 0.20, 0.40, 1.0)
LIST_PARTS = (0.05, 0.75, 0.95)  # of the listing: the scripts listed, the list at the right, the glyphs to add
# The Cancel button's own line (ak.cancel_button): what a stop leaves (its stoppable work reads: the checks and
# the listing; Fix ticked glyphs never stops)
CANCEL_NOTE = u"A check or a listing stopped changes nothing in the font."


def busy_share(done, part=0.0):
    """How far the bar is, 0 to 1: `done` steps of BUSY_STEPS are over, and `part` (0 to 1) of the next."""
    done = max(0, min(int(done), len(BUSY_SHARES)))
    base = BUSY_SHARES[done - 1] if done else 0.0
    end = BUSY_SHARES[done] if done < len(BUSY_SHARES) else base
    return base + max(0.0, min(float(part), 1.0)) * (end - base)


def counted_sets(results):
    """The character sets the top line and the log's count count: the data's, but the scripts (counted
    apart), the user's own, and the Legacy group's (wholly optional, always covered: the owner, "they
    do not count towards the stats"; their rows still say what the font lacks of them)."""
    return [r for r in results if r.language.script not in (CUSTOM_GROUP, LEGACY_GROUP)
            and not isinstance(r.language, ScriptSet)]


def set_tally(results):
    """The character sets checked (Coverages), sorted as every count of them takes them, the one definition
    Font Check's top line, its log, the Character sets tab's caption, and Proof's summary share: (the sets
    counted, counted_sets; Unicode's scripts, each checked as a set and counted apart; the Legacy group's
    sets, listed and never counted; the user's own, listed and never counted). The tab lists all four (Noto
    Sans: 140 + 172 + 5 = 317 rows, against 33 of 140 sets covered)."""
    scripts = [r for r in results if isinstance(r.language, ScriptSet)]
    legacy = [r for r in results if r.language.script == LEGACY_GROUP and not isinstance(r.language, ScriptSet)]
    own = [r for r in results if r.language.script == CUSTOM_GROUP and not isinstance(r.language, ScriptSet)]
    return counted_sets(results), scripts, legacy, own


def sets_sentence(results, b=lambda text: text):
    """The top line's sentences of the character sets (b: bold): "33 character sets of 140 are covered
    (the 5 Legacy sets, wholly optional, are not counted). 0 scripts of Unicode's 172 are covered whole."
    u"" without sets."""
    counted_, scripts, legacy, _ = set_tally(results)
    text = u""
    if counted_:
        whole = sum(1 for r in counted_ if r.level == "covered")
        if whole:
            text += u" %s of %d %s covered" % (b(counted(whole, u"character set")), len(counted_),
                                               u"is" if whole == 1 else u"are")
        else:
            text += u" %s of %d is covered" % (b(u"No character set"), len(counted_))
        if legacy:
            text += (u" (the Legacy set, wholly optional, is not counted)" if len(legacy) == 1 else
                     u" (the %s, wholly optional, are not counted)" % b(counted(len(legacy), u"Legacy set")))
        text += u"."
    if scripts:  # (each script as a set: its whole repertoire, whatever languages are written in it)
        whole = sum(1 for r in scripts if r.level == "covered")
        if whole:
            text += u" %s of Unicode's %d %s covered whole." % (b(counted(whole, u"script")), len(scripts),
                                                                u"is" if whole == 1 else u"are")
        else:  # ("0 scripts … are" read as a plural left unmade, owner, 2026-11-16)
            text += u" %s of Unicode's %d is covered whole." % (b(u"No script"), len(scripts))
    return text


def sets_tab_tip(results):
    """The Character sets tab's tooltip: what its count is made of (set_tally), each part with its noun
    in its number, so that it adds up to the caption with the top line's counts in it."""
    counted_, scripts, legacy, own = set_tally(results)
    parts = []
    for count, one, many in ((len(counted_), u"character set counted in the line above",
                              u"character sets counted in the line above"),
                             (len(scripts), u"script of Unicode, checked as a set (counted apart)",
                              u"scripts of Unicode, each checked as a set (counted apart)"),
                             (len(legacy), u"Legacy set, wholly optional (not counted)",
                              u"Legacy sets, wholly optional (not counted)"),
                             (len(own), u"set of your own (not counted)", u"sets of your own (not counted)")):
        if count:
            parts.append(u"%s %s" % (grouped(count), one if count == 1 else many))
    if not parts:
        return u"No character set is listed."
    total = len(counted_) + len(scripts) + len(legacy) + len(own)
    listed = parts[0] if len(parts) == 1 else (u"%s and %s" % tuple(parts) if len(parts) == 2 else
                                               u"%s, and %s" % (u", ".join(parts[:-1]), parts[-1]))
    return u"%s %s: %s." % (grouped(total), u"row" if total == 1 else u"rows", listed)


def checked_sentence(languages, sets, scripts, seconds, b=lambda text: text):
    """The log's one line when a check is done: "Checked 2,492 languages, 99 character sets, and 172
    scripts in 0.4 s." (each count with its noun in the right number, b: bold, the two together; what
    there is none of is left out)."""
    parts = [b(u"%s %s" % (grouped(languages), u"language" if languages == 1 else u"languages"))]
    if sets:
        parts.append(b(u"%s %s" % (grouped(sets), u"character set" if sets == 1 else u"character sets")))
    if scripts:
        parts.append(b(u"%s %s" % (grouped(scripts), u"script" if scripts == 1 else u"scripts")))
    return u"Checked %s in %.1f s." % (word_list(parts), max(0.0, seconds))


def checking_text(count):
    """What the window says while the languages are checked: "Checking 2,494 languages"."""
    return u"Checking %s %s" % (grouped(count), u"language" if count == 1 else u"languages")


def pasted_characters(text):
    """The characters of a pasted text to check a font against, each once, in the order met: the
    text in NFC, a letter kept with the combining marks Unicode has no single character for; spaces,
    controls, and format characters are left out (no glyph is asked for them)."""
    found, seen, current = [], set(), []

    def flush():
        item = u"".join(current)
        if item and item not in seen:
            seen.add(item)
            found.append(item)
        del current[:]

    for code in code_points(unicodedata.normalize("NFC", u"%s" % (text or u""))):
        ch = char_of(code)
        try:
            category = unicodedata.category(ch)
        except (TypeError, ValueError):  # (past U+FFFF on a narrow Python 2: two units, no category asked)
            category = "Lo"
        if category in ("Zs", "Zl", "Zp", "Cc", "Cf", "Cs"):
            flush()
        elif category.startswith("M") and current and not is_mark(code_points(current[0])[0]):
            current.append(ch)
        else:
            flush()
            current.append(ch)
    flush()
    return found


def custom_set(key, name, text):
    """A set of the user's own (pasted text or characters), checked as any character set is: every
    character a base one, under the group CUSTOM_GROUP."""
    items = pasted_characters(text)
    return Language(u"%s" % key, u"%s" % name, u"", CUSTOM_GROUP, u"set", u"", 0, items, [], u"", kind="set",
                    definition=u"A set of your own: the %s of the text you gave (spaces left out)."
                               % (u"1 character" if len(items) == 1 else u"%s characters" % grouped(len(items))))


def custom_key(name):
    return u"custom:%s" % name


def load_custom_sets(path):
    """[(name, text)] of the sets a user saved (FreeLab's settings folder); none without the file
    or when it cannot be read."""
    import json
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        return [(u"%s" % one["name"], u"%s" % one["characters"]) for one in data["sets"]
                if one.get("name") and one.get("characters")]
    except (OSError, IOError, ValueError, KeyError, TypeError, AttributeError):
        return []


def save_custom_sets(path, sets):
    """The user's sets written to their file (its folder made when missing)."""
    import json
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    data = {"about": u"FreeLab Font Check: the character sets you saved", "sets": [
        {"name": name, "characters": text} for name, text in sets]}
    with open(path, "wb") as handle:
        handle.write(json.dumps(data, ensure_ascii=True, indent=1, sort_keys=True).encode("ascii"))


def with_custom_set(sets, name, text):
    """The user's sets with one saved under name (in the place of one so named already, else last)."""
    name = (u"%s" % (name or u"")).strip()
    kept = [(held, characters) for held, characters in sets if held != name]
    at = next((index for index, (held, _) in enumerate(sets) if held == name), len(kept))
    return kept[:at] + [(name, text)] + kept[at:]


def languages_gained(results, checked):
    """The languages not covered whose needs are all in checked (a set of characters): sets, not
    sums, so a language needing two characters counts once, with both. A missed language counts too
    once all it needs is checked (its characters are listed while it is selected)."""
    checked = set(checked)
    return [r for r in results if r.level != "covered" and needs(r) and len(needs(r)) <= len(checked)
            and set(needs(r)) <= checked]


def gain_text(checked_count, gained, bold=None):
    """The live line over the tabs of glyphs: "With 6 glyphs ticked: +14 languages (Latin)" (bold: how
    the count gained is set in rich text)."""
    if not checked_count:
        return u"Tick glyphs to see how many languages they complete."
    scripts, order = {}, []
    for r in gained:
        group = script_group(r.language.script)  # (as the scripts are listed: Cree under Canadian Syllabics)
        if group not in scripts:
            scripts[group] = 0
            order.append(group)
        scripts[group] += 1
    glyphs = counted(checked_count, u"glyph")  # (bold with its noun, as the count gained: owner's images 297, 301)
    head = u"With %s ticked: " % (bold(glyphs) if bold else glyphs)
    if not gained:
        return head + u"no language is complete yet"
    if len(order) == 1:
        where = order[0]
    else:
        where = u", ".join(u"%s %d" % (script, scripts[script]) for script in
                           sorted(order, key=lambda s: (-scripts[s], s)))
    count = u"+%s" % counted(len(gained), u"language")
    return head + u"%s (%s)" % (bold(count) if bold else count, where)


def build_caption(count):
    """The caption of the button that hands glyphs to Glyph Compose, for count glyphs it can build."""
    if not count:
        return u"Build with Glyph Compose"
    return u"Build %s with Glyph Compose" % (u"this glyph" if count == 1 else u"those glyphs")


def copy_caption(count):
    """The caption of the button that copies count glyphs as text."""
    if not count:
        return u"Copy glyphs"
    return u"Copy this glyph" if count == 1 else u"Copy those glyphs"


def build_tip(chars, font=lambda text: text):
    """The tooltip of the build button: how many glyphs, and which (rich text; font: how they are set)."""
    return u"Opens <i>Glyph Compose</i> on %s: %s." % (counted(len(chars), u"glyph"), font(html_text(u" ".join(chars))))


def copy_tip(chars, font=lambda text: text):
    """The tooltip of the copy button: how many glyphs, and which (rich text)."""
    return u"Copies %s as text: %s." % (counted(len(chars), u"glyph"), font(html_text(u" ".join(chars))))


def html_text(text):
    return u"%s" % text.replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


# ("Tick", not "Check": owner's image 261, Check is the verb of the button that runs the check)
CHECK_BUTTONS = (("all", u"Tick all"), ("none", u"Untick all"), ("buildable", u"Tick only what Glyph Compose can build"))


def checks_for(rows, checked, buildable):
    """What each check button over a tab of characters would leave checked, {key: set of characters}, None
    for a button that would change nothing (it is grayed out): "all" adds every row listed to the
    checks, "none" clears them, "buildable" checks the rows listed with a character Glyph Compose can
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


def coverage_text(counts):
    """A bar's summary, from its counts (BAR_LEVELS): "275 of 569 languages (99 within reach)"."""
    text = u"%d of %s" % (counts[0], counted(sum(counts), u"language"))
    if counts[1]:
        text += u" (%d within reach)" % counts[1]
    return text


def counts_tip(name, counts):
    """A bar's tooltip: "Latin: 275 covered, 99 within reach, 190 started, 5 missed"."""
    return u"%s: %d covered, %d within reach, %d started, %d missed." % ((name,) + tuple(counts))


def script_text(s):
    """A script's summary: "275 of 569 languages (99 within reach)"."""
    return coverage_text(level_counts(s.results))


def absent_caption(count):
    """The check box under the scripts, its caption a sentence with the count of the scripts it shows
    (None: not known yet, before the first check: no count is shown as a zero). A tick's caption that is a
    sentence ends with a period (owner's image 324); one that names a thing (a feature, a section) has none."""
    if count is None:
        return u"Show the scripts whose glyphs are fully missing from the font."
    return u"Show the %s whose glyphs are fully missing from the font." % counted(count, u"script")


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
    # (in whole units: glyphs a fraction of a unit apart reach as far, and go by name)
    tallest = sorted(top.values(), key=lambda e: (-round_units(e.top), e.name))[:count]
    taken = set(e.name for e in tallest)
    deepest = [e for e in sorted(bottom.values(), key=lambda e: (round_units(e.bottom), e.name))
               if e.name not in taken][:count]
    return tallest, deepest


def extreme_notes(extents):
    """{glyph name: its note in the diagram} for the glyph whose ink reaches highest and the one reaching
    lowest (each among extreme_glyphs' pictures: the first tallest, and the lowest, in the tallest or the
    first deepest): "highest", "lowest", "highest and lowest" for one glyph that is both, each with how
    many other glyphs reach the same value, in whole units ("highest (and 3 others)"). The owner's image
    215: the diagram did not say which glyph was which, nor that others reach as far."""
    top, bottom = {}, {}
    for e in extents:
        if e.name not in top or e.top > top[e.name].top:
            top[e.name] = e
        if e.name not in bottom or e.bottom < bottom[e.name].bottom:
            bottom[e.name] = e
    if not top:
        return {}
    # (as extreme_glyphs orders them; among the lowest, the highest glyph first when it is one of them:
    # one picture, one caption)
    highest = min(top.values(), key=lambda e: (-round_units(e.top), e.name))
    lowest = min(bottom.values(), key=lambda e: (round_units(e.bottom), e.name != highest.name, e.name))
    high, low = round_units(highest.top), round_units(lowest.bottom)

    def said(word, others):
        return word + (u" (and %s)" % counted(others, u"other") if others else u"")

    notes = {}
    for name, word, others in (
            (highest.name, u"highest", sum(1 for e in top.values() if round_units(e.top) == high) - 1),
            (lowest.name, u"lowest", sum(1 for e in bottom.values() if round_units(e.bottom) == low) - 1)):
        notes[name] = (notes[name] + u" and " if name in notes else u"") + said(word, others)
    return notes


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
                warn.append(CheckLine("warn", u"Windows clips %s %s, up to %s (%s)" % (
                    counted(len(rows), u"glyph"), word, counted(int(rows[0][1]), u"unit"), rows[0][0]),
                    u"Windows cuts off what reaches %s %s (%d): %s." % (
                        side, u"winAscent" if side == "above" else u"winDescent",
                        m.win_ascent if side == "above" else m.win_descent,
                        u", ".join(u"%s %d" % row for row in rows[:20]) +
                        (u"\N{HORIZONTAL ELLIPSIS}" if len(rows) > 20 else u"")),
                    [name for name, _ in rows]))
        if not any(line.glyphs for line in warn):
            ok.append(CheckLine("ok", u"Windows clips no glyph", u"winAscent (%d) and winDescent (%d) reach past the "
                                u"ink of every glyph %s." % (m.win_ascent, m.win_descent, in_masters(extents))))
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
                info.append(CheckLine("info", u"%s %s %s%s" % (counted(len(rows), u"glyph"),
                                                               u"reaches" if len(rows) == 1 else u"reach", word, more),
                                      u"They may touch the line %s at the font's own line spacing (tall diacritics often "
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
    """FreeLang registered with Qt once per FontLab session; its family, or None (no file, or
    Qt refused it). In the dialog's font, Qt 5 took each character it lacks from another font: rare
    scripts' autonyms showed as boxes and some Cyrillic ones spaced wide. The bundled font has every
    character the languages list shows (checks/language_font), so the list is drawn in one design.
    The font is five files: the first is the family every use names, and the others
    (LIST_FONT_FALLBACKS: CJK, the rarer scripts and symbols, Mongolian and Tibetan, and Duployan,
    which is optional) are registered beside it and given to Qt as its substitutes
    (QFont.insertSubstitutions, once), so a font of the first family draws what it lacks from them.
    One of them that is missing or refused leaves its characters to the system's fonts (boxes
    where Qt finds none); nothing here raises for it. The fallback families given to Qt are noted
    (LIST_FALLBACKS_DRAWN), so a tooltip names by code point what no registered file draws."""
    global LIST_FALLBACKS_DRAWN

    def add(path):
        """The first family of a font file added to Qt's application fonts, or None."""
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

    known = [u"%s" % f for f in QtGui.QFontDatabase().families()]
    LIST_FALLBACKS_DRAWN = frozenset()  # (until they are given to Qt below)
    if LIST_FAMILY in known:
        family = LIST_FAMILY
    else:
        path = list_font_path()
        if path is None:
            return None
        family = add(path)
        if family is None:
            return None
        known.append(family)
    try:  # (the other files, each once a session; then the substitutes, once)
        folder = os.path.dirname(list_font_path() or u"")
        fallbacks = []
        for file_name, fallback in LIST_FONT_FALLBACKS:
            if fallback not in known:
                path = os.path.join(folder, file_name)
                if not os.path.isfile(path) or add(path) is None:
                    continue
            fallbacks.append(u"%s" % fallback)
        present = [u"%s" % f for f in QtGui.QFont.substitutes(family)]
        missing = [f for f in fallbacks if f not in present]
        if missing:
            QtGui.QFont.insertSubstitutions(family, missing)
        LIST_FALLBACKS_DRAWN = frozenset(fallbacks)
    except Exception:
        pass
    return family


HELP = u"""<b>FreeLab Font Check</b><br>
Three views of the current font. Nothing in the font changes until you click <i>Write suggested
values</i>, <i>Fix ticked glyphs</i>, <i>Fix this</i>, or the Coverage tab's <i>Declare coverage</i> (the font info's Unicode ranges and code
pages set to what the glyphs cover, where they differ). A fix or a declaration is one step of <i>Edit &gt;
Undo</i>; the vertical metrics written are not in FontLab's History: <i>Put back old values</i> takes them back
(a value that was not set before stays as written).<br><br>
<b>Coverage</b>: the scripts, each with a bar of its languages covered
(green), within reach (amber), started (red: the font has some of their glyphs, too few to be
within reach), and missed (gray: it has none); click one to see only its languages. The languages'
characters come from Hyperglot, and, for those it does not describe, from Google Fonts' language data,
Unicode CLDR, SIL's Locale Data Repository, Unilex, An Cr&uacute;bad&aacute;n, and Language Tools' keyboard
layouts: a language's tooltip names its source. Where no source declares a language's characters,
they are inferred from counting a text (its row says <i>inferred</i>: rare letters may be missing),
or read from a keyboard layout (its row says <i>keyboard</i>: the characters its keys and rules
type). Untick <i>Languages from texts and keyboards</i> to leave both out. At the left, two
tabs of glyphs. <i>High-value missing glyphs</i> ranks the glyphs to add by the languages each
completes on its own: tick some (or all, none, or only those <i>Glyph Compose</i> can build), and the
line above says how many languages they complete together. The second tab is grayed, and reads
<i>Select language, character set, or family</i>, until a language, a character set (a script of Unicode
is one), or a family is selected at the right: it then lists what that one misses, and is
named after it; clicking the selected row again, or an empty part of its list, unselects it. Ticks
are shared by the two tabs, and the buttons under the log act on the tab shown; a double-click on a row opens its
glyph in a <i>Glyph</i> window. At the right, three tabs: <i>Languages</i>, under their scripts
(click a heading to close or open it); <i>Character sets</i> that are no languages (IPA, mathematics,
symbols, Unicode blocks, Google Fonts' and Adobe's sets), checked the same way, each one's tooltip
naming its definition, and, under <i>Scripts (Unicode)</i>, every script Unicode encodes, measured by
its whole repertoire; and <i>Families</i>, the languages under their families and branches as
Glottolog classifies them, each with a bar in the same colors. The search, the level, and the order
act on the tab shown: a search looks through every language, by its names and the other names
Glottolog records, says why a find is not listed otherwise, and names the languages no source
describes. Those are counted beside each family's bar and listed under its last node, <i>Not yet
covered</i>, and the scripts no orthography here is written in close the <i>Languages</i> tab, each
checked as a script and selected like a language: to
add a language, open an issue on FreeLab's repository with its characters and a source FreeLab can
reuse (under an open license, or in the public domain). A script Unicode
has not encoded cannot be checked. Meanwhile, paste
a language's alphabet or a text in it in the field of the <i>Character sets</i> tab: it is checked
as a set of your own, which <i>Save set</i> keeps on this computer. <i>Display</i>, at the top,
keeps every language (as the window opens), the living and constructed ones, the living ones only,
the historical ones only, or the high-value ones only.
A letter the font lacks as one glyph counts when its anchors compose it from the font's letter and
mark (the language says <i>composed</i>).<br>
<b>Vertical metrics</b>: the font's tallest and deepest glyphs drawn on its line metrics (winAscent,
typo and hhea, cap height, x-height), the ink Windows clips in red, the suggested values dashed; the
values now and suggested, for the line spacing you set (a share of the em), or keeping the font's
current line spacing for an update of a released font; the checks Google Fonts' guidance asks for;
the glyphs Windows clips. <i>Write suggested values</i> sets the font's typo, hhea, and win values and <i>Use Typo Metrics</i>
(those that differ); the masters' ascender, descender, x-height, and cap height, which FontLab draws
with, are left as they are.<br>
<b>Masters</b>: the glyphs that keep the masters from interpolating, worst first, a symbol per master;
the selected glyph drawn in the master compared with and in another, the contour at fault highlighted
and its nodes numbered. <i>Fix ticked glyphs</i> sets right, in the other masters, the contours' order, directions,
start points, and the components' order; contour and node counts, node types, missing layers, and
anchors need the designer. The master compared with never changes.<br><br>
Each view is checked as its tab is first shown, and again after an undo or an edit in FontLab. Click
this help's button, then anything in the window, for what it does (or right-click it: <i>What's This?</i>)."""

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
WIDE = 1400  # pixels: the dialog's width to start with (the other tools' 1000 cut the right list's last column)
SCREEN_MARGIN = 40  # pixels kept between the dialog's width and the screen's free area (as ak.size_dialog keeps)
LEFT_SHARE = 0.42  # the share of the width the characters' lists take to start with; the languages' the rest
BAR_COLUMN = BAR_SIZE[0] + 12  # pixels: the bar's column, whole
FAMILY_NAMES_MOST = int(COLUMN_MAX * 1.4 * LIST_SCALE)  # pixels of a family's name its bar makes room for (larger text)


def wide_width(screen=None, wanted=WIDE):
    """The width Font Check opens at: wanted, or the screen's free width less SCREEN_MARGIN when that
    is less (screen: that free width, None when it is not known)."""
    if screen is None or not screen > 0:
        return int(wanted)
    return int(min(wanted, screen - SCREEN_MARGIN))


def split_sizes(width, share=LEFT_SHARE):
    """(left, right): the widths the characters' lists and the languages' lists start with."""
    left = int(width * share)
    return left, int(width) - left


TAB_PAD = 30  # pixels a tab takes beside its text (ak.TAB_SHEET's padding and margin, and a little room)
TAB_LEAST = 1  # characters an elided tab keeps before its ellipsis, at least


def elided_text(text, width, measure):
    """text cut to fit width pixels (measure: a text's width), an ellipsis at its end; never less than
    TAB_LEAST characters and the ellipsis."""
    if measure(text) <= width:
        return text
    cut = text
    while len(cut) > TAB_LEAST and measure(cut.rstrip() + u"\N{HORIZONTAL ELLIPSIS}") > width:
        cut = cut[:-1]
    return cut.rstrip() + u"\N{HORIZONTAL ELLIPSIS}"


def tab_texts(texts, current, room, measure, pad=TAB_PAD):
    """The texts a tab bar of room pixels shows (texts: its tabs' whole names; current: the tab chosen):
    all whole when they fit; else the chosen tab's whole and the others elided with an ellipsis to share
    what it leaves, a short one kept whole when it fits in its share (the owner's report 125: the bar's
    scroll arrows hid a tab; an elided tab is whole again once chosen)."""
    texts = list(texts)
    widths = [measure(text) + pad for text in texts]
    if sum(widths) <= room or room <= 0 or not 0 <= current < len(texts):  # (0: not laid out yet)
        return texts
    others = sorted((index for index in range(len(texts)) if index != current), key=lambda index: widths[index])
    left = room - widths[current]
    shares = {}
    while others:  # (the narrowest first: whole when it fits in an equal share, its spare room to the others)
        fair = left / float(len(others))
        if widths[others[0]] <= fair:
            shares[others[0]] = widths[others[0]]
            left -= widths[others.pop(0)]
            continue
        for index in others:
            shares[index] = fair
        break
    return [text if index == current or widths[index] <= shares[index]
            else elided_text(text, shares[index] - pad, measure) for index, text in enumerate(texts)]


BAR_LEAST = 48  # pixels: the bar's column gives way to this before a name is cut (it was given none: report 127)
NAME_LEAST = 90  # pixels: a name's column is cut to this before the bar gives way further
COUNTS_LEAST = 120  # pixels: the families' long counts (their Languages column) give way to this first, elided
BAR_MARGIN = 6  # pixels between a bar and its column's edges
BAR_ROLE = 0x0100 + 78  # Qt.UserRole + 78: a row's bar counts, "covered,nearly,started,missed" (bar_delegate draws them)
COLUMN_KINDS = {"languages": "names", "sets": "names", "families": "bars"}  # how a list at the right shares its width


PINNED_FLOOR = 24  # pixels: what the other columns keep at least beside one dragged (the shared MIN_SECTION)


def column_widths(room, wanted, taker=0, giving=(), least=None, pinned=None):
    """The widths of a list's columns, filling room exactly (no gap at the right, nothing past it): each
    column as wide as it wants (wanted), a column the user dragged as they left it (pinned: {column:
    width}); the taker column is given what they leave. When that is less than the taker wants, the
    giving columns give way first, in their order, down to their least (least: {column: width}), then the
    taker down to its least, then the giving columns to nothing, in the reverse order (the families' list:
    its counts, then its bar, to their least; the names to theirs; the bar closed, then the counts), then
    the taker. A taker the user dragged gives its part to the first giving column that was not dragged,
    else to the last column not dragged."""
    pinned, least = dict(pinned or {}), dict(least or {})
    count = len(wanted)
    pinned = dict((column, width) for column, width in pinned.items() if 0 <= column < count)
    if taker in pinned:
        free = [column for column in giving if column not in pinned]
        free = free or [column for column in reversed(range(count)) if column not in pinned]
        taker = free[0] if free else None
    giving = [column for column in giving if column != taker and column not in pinned]
    # A column dragged never takes the room the others need at their least (owner's image 214: dragged
    # past the frame, it left every other column at nothing): the widest it keeps leaves the taker and
    # the giving columns their least (PINNED_FLOOR at least), the other columns as wide as they want
    # (they never give way), and a column dragged too its width (PINNED_FLOOR until it is capped itself).
    floors = [min(int(wanted[c]), max(int(least.get(c, 0)), PINNED_FLOOR)) for c in range(count)]
    capped = set()
    for column in sorted(pinned):
        others = 0
        for c in range(count):
            if c == column:
                continue
            if c in pinned:
                others += int(pinned[c]) if c in capped else PINNED_FLOOR
            elif c == taker or c in giving:
                others += floors[c]
            else:
                others += int(wanted[c])
        pinned[column] = max(PINNED_FLOOR, min(int(pinned[column]), int(room) - others))
        capped.add(column)
    if taker is None:
        return [int(pinned.get(column, wanted[column])) for column in range(count)]
    widths = [int(pinned.get(column, wanted[column])) for column in range(count)]

    def rest():
        return room - sum(widths[column] for column in range(count) if column != taker)

    for goal, floor, order in ((wanted[taker], least, giving), (least.get(taker, 0), {}, giving[::-1])):
        # (the giving columns down to their least while the taker lacks what it wants; then, while it lacks
        # its own least, down to nothing, the last to give way first)
        for column in order:
            short = goal - rest()
            if short <= 0:
                break
            widths[column] -= min(short, max(0, widths[column] - floor.get(column, 0)))
    widths[taker] = max(0, rest())
    return widths


def bar_counts(counts):
    """A row's bar counts as its cell holds them (BAR_ROLE): "covered,nearly,started,missed"."""
    return u",".join(u"%d" % count for count in counts)


DIAGRAM_GAP = 0.1  # of the em, between the diagram's glyphs
DIAGRAM_NAME_MIN = 64  # pixels: room for a glyph's name under it in the diagram (longer ones elided)
DIAGRAM_NOTE_MAX = 170  # pixels: room for a glyph's note under it at most ("highest (and 3 others)")
SCRIPT_SHEET = (u"QTreeView::item:selected { background: rgba(128, 128, 128, 70); color: palette(text); } "
                u"QTreeView { selection-background-color: rgba(128, 128, 128, 70); }")
# (the script clicked shows in a faint gray, which leaves its bar's four colors as they are)
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
LANGUAGE_FILTERS = ((None, u"All"), ("covered", u"Covered"), ("nearly", u"Within reach"), ("started", u"Started"),
                    ("missed", u"Missed"))
STATE_LABELS = {"covered": u"Covered", "nearly": u"Within reach", "started": u"Started", "missed": u"Missed"}
# Started: the font has at least one of the language's characters, but too few for it to be within
# reach (red); Missed: it has none (gray).
BRANCH_SHEET = u" QTreeView::branch { image: none; border-image: none; }"
ARROW_ZONE = 22  # pixels from a row's left edge: a press there, on a family's arrow, opens or closes it only
SEARCH_DELAY = 250  # milliseconds of a pause in the typing before a search lists its finds
SEARCH_OPENS = 3  # characters a search has from which it opens the families it lists


def qcolor(rgb, alpha=255):
    QtCore, QtGui = _qt()
    return QtGui.QColor(rgb[0], rgb[1], rgb[2], alpha)


def faded(color, alpha):
    QtCore, QtGui = _qt()
    found = QtGui.QColor(color)
    found.setAlpha(alpha)
    return found


LEVEL_RGB = {"covered": GREEN, "nearly": AMBER, "started": RED}  # (missed: a faint gray)


def level_color(level, colors=None):
    """A level's color, the window's one scheme (bars, dots, the Families tree): green covered, amber
    within reach, red started, gray missed. Mid tones, as the checks' icons: each reads on the dark
    interface and on the light one (the log's own green, amber, and red are text colors, a lighter
    and a darker one per palette). The highlight color stood for covered before: it is the selection's
    color, and means nothing else in FreeLab."""
    rgb = LEVEL_RGB.get(level)
    return qcolor(rgb) if rgb is not None else qcolor(GRAY, LINE_ALPHA)


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
    """A script's or a family's bar: its languages covered, within reach, started, and missed, in
    proportion (counts: in BAR_LEVELS' order)."""
    QtCore, QtGui = _qt()
    width, height = size
    pixmap = new_pixmap(width, height)
    painter = QtGui.QPainter(pixmap)
    try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
        x = 0
        top, thick = height // 2 - 4, 8
        for level, w in zip(BAR_LEVELS, bar_widths(counts, width)):
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


def arrow_pixmap(open_, color, size=DOT_SIZE):
    """A heading's arrow, drawn in the text color (the style's own is dark whatever the palette): it
    points down over a section shown, right beside one closed."""
    QtCore, QtGui = _qt()
    pixmap = new_pixmap(size, size)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        s = float(size)
        path = QtGui.QPainterPath()
        if open_:
            path.moveTo(s * 0.2, s * 0.34)
            path.lineTo(s * 0.8, s * 0.34)
            path.lineTo(s * 0.5, s * 0.72)
        else:
            path.moveTo(s * 0.34, s * 0.2)
            path.lineTo(s * 0.72, s * 0.5)
            path.lineTo(s * 0.34, s * 0.8)
        path.closeSubpath()
        painter.fillPath(path, QtGui.QBrush(color))
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


def character_pixmap(text, color, font, size=CHAR_ICON, background=None):
    """Characters the font lacks, drawn in a reference font (the dialog's, with Qt's fallback for the
    scripts it lacks) in the text color, centered, made smaller to fit; over a background color when
    one is given (a selected language's characters: the selection's color)."""
    QtCore, QtGui = _qt()
    width, height = size
    face = QtGui.QFont(font)
    face.setPixelSize(int(height * 0.62))
    path = QtGui.QPainterPath()
    path.addText(QtCore.QPointF(0, 0), face, text)
    pixmap = new_pixmap(width, height)
    if background is not None:
        pixmap.fill(background)
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
    master), a note under them (the diagram's "highest (and 3 others)": extreme_notes), and whether it
    is the one selected."""

    def __init__(self, name, path, advance, master=u"", selected=False, note=u""):
        self.name, self.path, self.advance, self.master, self.selected = name, path, advance, master, selected
        self.note = note
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
    pictures = [p for p in pictures if p.box is not None]
    noted = any(getattr(p, "note", u"") for p in pictures)
    caption_room = (3 if noted else 2) * line_height + 6  # (name, master, and the note: highest, lowest)
    values = [l.value for l in lines] + [0]
    if line:
        values += [line[0] + line[2], line[1]]
    for p in pictures:
        values += [p.box[1], p.box[3]]
    high, low = max(values), min(values)
    span = max(high - low, upm * 0.5)
    high, low = high + span * 0.04, low - span * 0.04
    # (longer names elided; a note, "highest (and 3 others)", kept whole up to DIAGRAM_NOTE_MAX)
    names = [max(min(text_width(font, p.name), DIAGRAM_NAME_MIN),
                 min(text_width(font, getattr(p, "note", u"")), DIAGRAM_NOTE_MAX) if getattr(p, "note", u"") else 0) + 8
             for p in pictures]
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
            lines_down = 1
            if p.master:
                painter.setPen(faded(text, QUIET_ALPHA))
                painter.drawText(rect.translated(0, line_height), int(QtCore.Qt.AlignCenter),
                                 elided(font, p.master, int(column)))
                lines_down = 2
            note = getattr(p, "note", u"")
            if note:  # (which glyph reaches highest, which lowest: owner's image 215)
                painter.setPen(faded(text, QUIET_ALPHA))
                painter.drawText(rect.translated(0, line_height * lines_down), int(QtCore.Qt.AlignCenter),
                                 elided(font, note, int(column)))
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
    """[(name, x, y)] of a layer's anchors (flPinPoint.point, as Glyph Compose reads it)."""
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


def others_text(r, row, shown=6):
    """What else a language needs beside a row's characters, the first few: one character, or six
    and "+54" (a missed language or a character set, listed while it is selected). Only the first few
    are made into text, and the rest counted: Han needs 103,351 characters, and making them all for
    each of a tab's 200 rows took half a minute. A script's characters (CodeItems, each once) are
    counted without being read at all."""
    wanted, own = needs(r), set(row.items)
    others = []
    for item in wanted:
        if item not in own:
            others.append(shown_text(item))
            if len(others) > shown:
                break
    text = u" ".join(others[:shown])
    if len(others) > shown:
        if isinstance(wanted, CodeItems):
            rest = len(wanted) - sum(1 for item in own if item in wanted)
        else:  # (a list may hold a character twice, a mark both a base character and a mark: counted as listed;
            # list.count, not a scan in Python: 200 rows of a set of 20,000 took a second)
            rest = len(wanted) - sum(wanted.count(item) for item in own)
        text += u" +%d" % (rest - shown)
    return text


def row_languages_text(row, shown=4):
    """The languages column of a row of characters: the languages it completes, or, when it completes
    none on its own, the languages needing it with what else they miss; "optional" for a set's
    optional character (the selection's own tab lists them last)."""
    if row.optional:
        return u"optional"
    if row.completing:
        names = [r.language.name for r in row.completing]
    else:
        names = [u"%s (with %s)" % (r.language.name, others_text(r, row)) for r in row.needing]
    text = u", ".join(names[:shown])
    if len(names) > shown:
        text += u", +%d" % (len(names) - shown)
    return text


def few_names(names, shown=None):
    """Names in a tooltip, the first `shown` of them and how many more: a glyph many languages need
    (a schwa) named hundreds, a wall of text the height of the screen."""
    shown = TIP_NAMES if shown is None else shown
    text = u", ".join(names[:shown])
    if len(names) > shown:
        text += u", and %s more" % grouped(len(names) - shown)
    return text


def row_tip(row, buildable=False, generated=False):
    """A glyph's row's tooltip: its code points and names, then a paragraph each (a blank line
    between two) for what it completes, what needs it with other glyphs, and what the font has of it."""
    paragraphs = [u"\n".join(u"%s: %s" % (code_label(item), short_name(item)) for item in row.items)]
    if row.optional:
        paragraphs.append(u"Optional: the set selected holds it and is complete without it (%s)." % OPTIONAL_WHAT)
    elif getattr(row, "spacing", False):
        paragraphs.append(u"Typesetting: these languages group the thousands of their numbers with it (12 345, in "
                          u"Unicode CLDR's conventions), and text set in them needs it.")
    elif row.auxiliary():
        paragraphs.append(u"Auxiliary: these languages use it in loan words, names, or rare spellings, and miss "
                          u"nothing else.")
    if row.completing:
        paragraphs.append(u"Completes on its own: %s." % few_names([r.language.label() for r in row.completing]))
    others = [r for r in row.needing if r not in row.completing]
    if others:
        paragraphs.append(u"Needed, with other glyphs, by: %s." % few_names(
            [u"%s (with %s)" % (r.language.label(), others_text(r, row)) for r in others[:TIP_NAMES]]
            + [u""] * max(0, len(others) - TIP_NAMES)))  # (only the names shown are made: others_text reads lists)
    parts = [item for item in row.items if any(item in r.parts for r in row.needing)]
    if parts:
        paragraphs.append(u"The font has the letter and marks of %s, but no anchors joining them." % u" ".join(parts))
    if buildable and generated:
        paragraphs.append(u"Glyph Compose can build it from the font's glyphs (its Glyph generation tab).")
    elif buildable:
        paragraphs.append(u"Glyph Compose can build it from the font's letters and marks.")
    return u"\n\n".join(paragraphs)


def language_matches(r, text):
    """Whether a search finds a language: its name, autonym, code, or one of its other names holds
    the text (any case, diacritics set aside); a character set's name, code, or group."""
    text = fold(text).strip()
    if not text:
        return True
    own, others = r.language.search_text()
    return text in own or text in others


def found_by(r, text):
    """The other name a search found a language by (Nama, for Khoekhoe), or None: no search, or a name
    the list shows holds the text."""
    text = fold(text).strip()
    if not text:
        return None
    own, others = r.language.search_text()
    if text in own or text not in others:
        return None
    for alias in r.language.aliases:
        if text in fold(alias):
            return u"%s" % alias
    return None


def language_key(r):
    """What tells a listed language from the others, whatever objects a new check made. Its autonym
    too: Hyperglot gives five languages two orthographies of one name and script, told apart by their
    autonyms only (Bassari, oniyan and oneyan; Ese Ejja, Kako, Kwak'wala, Koonzime)."""
    if r is None:
        return None
    language = r.language
    return (language.kind, language.iso, language.script, language.name, language.autonym or u"")


class Section(object):
    """A section of the languages list: its title, its languages in order, and, for one a search
    alone brings up, why it is not listed otherwise."""

    def __init__(self, title, results, why=u""):
        self.title, self.results, self.why = title, results, why

    def heading(self):
        text = u"%s (%d)" % (self.title, len(self.results))
        return u"%s: %s" % (text, self.why) if self.why else text


class RightView(object):
    """One list of a tab at the right (each tab has three, VIEW_MODES) and what it was filled with: its
    rows (Coverages, FamilyNodes, Uncovered, by the index each item holds), the label of each (what
    finds its item again), the closed headings and families whose rows wait, and the signature of what
    it was filled from (None: never filled). A list whose signature is still the one wanted is shown as
    it is: where it was scrolled to, its headings as they were opened."""

    def __init__(self, tree):
        self.tree, self.rows, self.labels, self.unfilled, self.signature = tree, [], [], {}, None
        self.script, self.used = None, 0  # (a script's list: the script it was last shown for, and when)


# Each tab's lists: every script's ("full"), the last three scripts chosen above (SCRIPT_MODES, the least
# recently shown given to a new script), and a search's finds ("search"), each kept as it was filled. The
# owner: "Clicking from one script to another can freeze up for a few seconds without visual feedback": one
# list for both, the whole Languages list (1,800 rows on Noto Sans) was made anew at each click between a
# script and All scripts, and back; with one script's list, Latin's 2,108 rows were made anew after a click
# on Cyrillic (live: 0.125 s the second time)
SCRIPT_MODES = ("script", "script 2", "script 3")
VIEW_MODES = ("full",) + SCRIPT_MODES + ("search",)
LISTING_BUSY_ROWS = 300  # rows a script's click makes at least for the progress bar to show meanwhile
LISTING_STEP_ROWS = 100  # rows made between two moves of that bar


def listing_text(tab, script):
    """What the top row's bar says while a click lists the tab at the right (script: None or u"" for All
    scripts); the top row adds the ellipsis (ak.busy_progress)."""
    if tab == "families":
        text = (u"Listing the families of the languages written in %s" % script if script
                else u"Listing the families of all scripts' languages")
    elif tab == "sets":
        text = u"Listing the character sets"
    else:
        text = u"Listing the languages written in %s" % script if script else u"Listing the languages of all scripts"
    return text


ABSENT_WHY = u"a script the font has none of"
OTHER_SCRIPT_WHY = u"not the script chosen above"
STATUS_WHY = u"left out by the Display choice above"
RIGHT_TABS = (("languages", u"Languages"), ("sets", u"Character sets"), ("families", u"Families"))
RIGHT_NOUNS = {"languages": (u"language", u"languages"), "sets": (u"character set", u"character sets"),
               "families": (u"language", u"languages")}
# The Families tab's last node: the languages Glottolog does not classify. It read "Not classified", which,
# among the families, read as the name of one (the owner: "Odd a family is listed as not classified since
# it's a family"): it is no family, and says what its languages are. Its one language was Minang (xrg), a
# code Glottolog 5.4 has no languoid for, which the families' train script now places beside Nyunga: with
# this data the node is never made (family_tree makes it for a language that lands there, and only then).
UNCLASSIFIED = u"Languages Glottolog does not classify"
UNCLASSIFIED_TIP = (u"No family: Glottolog 5.4 has no entry for these languages' ISO 639-3 codes, or files them under "
                    u"no family, so Font Check cannot place them in its tree. They are checked as any language is.")


def kept_rows(results, text, level, sort, counts):
    """The coverages a search and a level keep, in order, each told the other name it was found by;
    counts["hidden"] grows by the finds of a search the level holds back."""
    found = [r for r in results if language_matches(r, text)]
    kept = [r for r in found if level is None or r.level == level]
    if text:
        counts["hidden"] += len(found) - len(kept)
    for r in kept:
        r.found_by = found_by(r, text) if text else None
    return sort_languages(kept, sort)


def language_sections(scripts, shown, text=u"", level=None, sort="reach", others=(), statuses=None):
    """([Section], hidden): the Languages tab. scripts: every ScriptCoverage; shown: the names of the
    scripts listed (those the font has, or the one chosen); others: the coverages of the languages
    the choice of statuses leaves out. Without a text searched, the scripts shown. A search looks
    through every language, by its names and its other names: its finds in the other scripts and among
    the languages left out come under headings that say why they are not listed otherwise. level keeps
    one level only ("covered", "nearly", "started", "missed"); hidden counts the finds of a search it
    holds back."""
    text = (text or u"").strip()
    counts = {"hidden": 0}

    def rows(results):
        return kept_rows(results, text, level, sort, counts)

    shown = set(shown)
    sections = [Section(s.script, rows(s.results)) for s in scripts if s.script in shown]
    if text:
        sections += [Section(s.script, rows(s.results), OTHER_SCRIPT_WHY if s.present else ABSENT_WHY)
                     for s in scripts if s.script not in shown]
        titles = []
        for r in others:
            if left_title(r.language, statuses) not in titles:
                titles.append(left_title(r.language, statuses))
        sections += [Section(title, rows([r for r in others if left_title(r.language, statuses) == title]), STATUS_WHY)
                     for title in titles]
    return [section for section in sections if section.results], counts["hidden"]


def set_sections(sets, text=u"", level=None, sort="reach"):
    """([Section], hidden): the Character sets tab, the sets' coverages under their groups (phonetics,
    mathematics, symbols and punctuation, foundries), searched, filtered, and ordered as the
    languages are."""
    text = (text or u"").strip()
    counts = {"hidden": 0}
    groups = []
    for r in sets:
        if r.language.script not in groups:
            groups.append(r.language.script)
    sections = [Section(group, kept_rows([r for r in sets if r.language.script == group], text, level, sort, counts))
                for group in groups]
    return [section for section in sections if section.results], counts["hidden"]


class FamilyNode(object):
    """A family or one of its branches in the Families tab: its name, its place (the names from its
    family down to it, as Glottolog has them: what finds it again when the tree is made anew), the
    branches under it, and the languages right under it."""

    def __init__(self, name, path=()):
        self.name, self.path = name, tuple(path)
        self.children, self.results = [], []
        self.uncovered = []  # a family's languages that cannot be checked yet (Uncovered), listed under its last node

    def child(self, name):
        for one in self.children:
            if one.name == name:
                return one
        self.children.append(FamilyNode(name, self.path + (name,)))
        return self.children[-1]

    def all_results(self):
        """Every language under it, its branches' too."""
        found = list(self.results)
        for one in self.children:
            found.extend(one.all_results())
        return found


def family_matches(path, text):
    """Whether a search names one of the families or branches above a language."""
    text = fold(text).strip()
    return bool(text) and any(text in fold(name) for name in path)


# What Font Check knows of and cannot check yet: the languages Glottolog lists with an ISO 639-3 code
# that no source gives characters for, counted family by family and listed under each family's last
# node, and the scripts Unicode has that no orthography here is written in.
NOT_COVERED = u"Not yet covered"
SCRIPTS_NOT_COVERED = u"Scripts not yet covered"
# Scripts whose characters do not depend on the language written, so that no language's character list,
# and no count of languages, can ever rank a font for them: notations that transcribe other scripts or
# languages. The owner: for Braille and SignWriting, "'Not yet covered' fails at being a good description
# ... they can never be covered according to those criteria", and they are character sets, not languages.
# So they are not listed among the scripts not yet covered in the Languages tab: they are character sets
# (Notation, as Unicode blocks, and Scripts (Unicode)), and a search for one there points to them. Each
# with why, and its block's set. The other scripts not yet covered each wrote one or more languages, so a
# source could describe them: Duployan (the everyday script of Chinook Wawa and several Salishan
# languages; its block is a Notation set too, which answers another question), Bopomofo (a closed phonetic
# set for Mandarin and Taiwanese), Phags Pa, Zanabazar Square, and Soyombo. Mongolian was among them until
# SLDR's Mongolian in the Mongolian script was added to the data (filed under Peripheral Mongolian).
NOTATION_SCRIPTS = (
    (u"Braille", u"its 256 cells are the same code points whatever the language or contraction code",
     u"Braille Patterns (Unicode block)"),
    (u"SignWriting", u"its symbols are one set for every sign language", u"Sutton SignWriting (Unicode block)"),
)
CLOSING_TITLES = (SCRIPTS_NOT_COVERED,)  # the Languages tab's closing section: closed until asked for
SET_LINK = u"set:"  # a link in the line under the lists: the Character sets tab, searched for the set named


def notation_reason(name):
    """Why a script is a notation no language count ranks (NOTATION_SCRIPTS), or u"" for another."""
    return next((reason for script, reason, _ in NOTATION_SCRIPTS if script == name), u"")


def languages_not_covered(not_covered):
    """The scripts not yet covered that the Languages tab lists: those no orthography here is written
    in, but the notations (NOTATION_SCRIPTS), which are character sets."""
    return [name for name in not_covered if not notation_reason(name)]


def notation_line(text):
    """What a search of the Languages tab says of a notation it names (Braille, SignWriting): a
    character set, not a language's script, and where it is checked; u"" when it names none. As
    known_matches has it, the text is a whole name, or, from three characters on, part of one (a
    search for "e" names neither)."""
    text = fold(text).strip()

    def named(name):
        return text == name or (len(text) >= 3 and text in name)
    found = [(script, reason, block) for script, reason, block in NOTATION_SCRIPTS
             if text and (named(fold(script)) or named(fold(block)))]
    return u" ".join(
        u"%s is a notation, not a language's script (%s): it is checked as a character set, %s under Notation and "
        u"%s under Scripts (Unicode), in the Character sets tab." % (script, reason, block, script)
        for script, reason, block in found)
UNCOVERED_NAMED = 4  # languages a family's tooltip names of those it cannot check
UNCOVERED_OPEN = 50  # a search opens a family's Not yet covered node by itself up to this many languages
CONTRIBUTE = (u"These languages are known, but FreeLab has no data on how they are written. To add one, open an "
              u"issue on FreeLab's repository (%s) with the characters the language uses and a source FreeLab can reuse (under an open license, or in the public domain)."
              % ISSUES_ADDRESS)
CONTRIBUTE_SCRIPTS = (u"Unicode encodes these scripts, but FreeLab has no orthography written in them: each is "
                      u"checked as a script, its whole repertoire the measure. To add a "
                      u"language, open an issue on FreeLab's repository (%s) with the characters it uses and a "
                      u"source." % ISSUES_ADDRESS)
# What cannot be supported, stated with its date. The scripts named are those of Unicode's own list of
# scripts not yet encoded (unicode.org/standard/unsupported.html, read on 2026-11-13): none is added here.
AS_OF = u"November 2026"
NOT_ENCODED = (u"As of %s, a script Unicode has not encoded can be neither checked nor built, except through "
               u"private-use code points: Loma and Naxi Dongba among the scripts in use; Balti-A and Balti-B, Chola, "
               u"Landa, Maya hieroglyphs, Numidian, Book Pahlavi, Pyu, Ranjana, and Satavahana among the historic "
               u"ones (Unicode's own list of scripts not yet encoded)." % AS_OF)


def limits_text(not_covered, with_script):
    """What limits the languages not yet covered, from the data's own counts: those a source records
    a script for without giving characters, and those with no script on record; nothing when no
    language is left uncovered."""
    if not not_covered:
        return u""
    without = max(0, not_covered - with_script)
    if not_covered == 1:
        return (u"As of %s, 1 language is not covered: %s. The limit is the record itself, not the tool." % (
            AS_OF, u"a script is on record for it, but no source gives its characters" if with_script
            else u"no script is on record for it (it may have no written form, or no open description that can be "
                 u"cited)"))
    parts = []
    if with_script:
        parts.append(u"%s %s a script on record but no source that gives %s characters" % (
            grouped(with_script), u"has" if with_script == 1 else u"have", u"its" if with_script == 1 else u"their"))
    if without:
        parts.append(u"%s %s no script on record (many have no written form, or no open description that can be "
                     u"cited)" % (grouped(without), u"has" if without == 1 else u"have"))
    return u"As of %s, of the %s languages not covered, %s. The limit is the record itself, not the tool." % (
        AS_OF, grouped(not_covered), u", and ".join(parts))
# The character sets that are the nearest measure of a font for a language of a script whose own
# characters no source gives: the widest sets of the script that Font Check lists. Measured on the
# orthographies the data does have: Adobe Latin 5 holds every base character of 2,067 of the 2,084
# Latin ones (99%) and Google's Latin sets together of 1,989 (95%); Google's Cyrillic sets of 87 of
# 98 (Adobe Cyrillic 3 of 65); Google's Arabic sets of 44 of 78, and all but three at most of 71.
PROXY_SETS = {u"Latin": (u"Adobe Latin 5", u"GF Latin African", u"GF Latin Beyond"),
              u"Cyrillic": (u"GF Cyrillic Pro", u"Adobe Cyrillic 3"),
              u"Greek": (u"GF Greek Pro", u"Adobe Greek 2"),
              u"Arabic": (u"GF Arabic Plus",)}


class Uncovered(object):
    """A language known and not described: its ISO 639-3 code, its name and other names
    (Glottolog's), and the family it belongs to."""

    def __init__(self, iso, name, others=(), family=u""):
        self.iso, self.name, self.others, self.family = iso, name, tuple(others), family


class UncoveredNode(FamilyNode):
    """The last node under a family: the languages of the family that cannot be checked yet."""

    def __init__(self, path, entries):
        FamilyNode.__init__(self, NOT_COVERED, tuple(path) + (NOT_COVERED,))
        self.entries = list(entries)


def shows_uncovered(node):
    """Whether a family tree (its root) lists any language that cannot be checked yet."""
    if isinstance(node, UncoveredNode):
        return bool(node.entries)
    return any(shows_uncovered(child) for child in getattr(node, "children", ()))


def uncovered_count_text(count):
    """A family's last column: how many of its languages cannot be checked yet (nothing for none)."""
    return u"%d not yet covered" % count if count else u""


def uncovered_sentence(entries, shown=UNCOVERED_NAMED):
    """What a family's tooltip says of the languages it cannot check: a few names and the total."""
    if not entries:
        return u""
    names = [one.name for one in entries[:shown]]
    if len(entries) > shown:
        names.append(u"%d more" % (len(entries) - shown))
    if len(entries) == 1:
        return u"1 more language of it is known and cannot be checked yet (no source says how it is written): %s." % names[0]
    return (u"%d more languages of it are known and cannot be checked yet (no source says how they are written): %s."
            % (len(entries), word_list(names)))


def proxy_sentence(scripts):
    """What is said of a language no source gives characters for when a source records its script:
    the script, and the character sets that are the nearest measure of a font for it."""
    lines = []
    for script in scripts:
        sets = PROXY_SETS.get(script)
        if sets:
            lines.append(u"Recorded as written in %s: the character %s %s (in Character sets) %s the nearest measure." % (
                script, u"set" if len(sets) == 1 else u"sets", word_list(list(sets)), u"is" if len(sets) == 1 else u"are"))
        elif script_group(script) != script:  # (Chinese is listed under Han: the heading named as it is listed)
            lines.append(u"Recorded as written in %s: the languages listed under %s are the nearest measure."
                         % (script, script_group(script)))
        else:
            lines.append(u"Recorded as written in %s: the languages listed under that script are the nearest measure."
                         % script)
    return u"\n".join(lines)


def uncovered_tip(entry, scripts=()):
    """The tooltip of a language that cannot be checked: what it is, why it cannot be checked, the
    script a source records for it and what measures a font for it meanwhile, and its other names."""
    lines = [u"%s (%s)%s: known, not yet covered. None of Font Check's sources says which characters it is written "
             u"with, so no font can be checked for it." % (
                 entry.name, entry.iso, u", %s" % entry.family if entry.family else u"")]
    lines.append(proxy_sentence(scripts) if scripts else
                 u"No source here records a script for it: it may have no written form in use.")
    if entry.others:
        others = list(entry.others[:12]) + ([u"%d more" % (len(entry.others) - 12)] if len(entry.others) > 12 else [])
        lines.append(u"Also called: %s" % word_list(others))
    lines.append(u"To add it, open an issue on FreeLab's repository (%s) with the characters it uses and a source FreeLab can reuse (under an open license, or in the public domain)."
                 % ISSUES_ADDRESS)
    return u"\n\n".join(line for line in lines if line)  # (a blank line between two paragraphs)


def uncovered_matches(entry, text):
    """Whether a search (folded text) names a language that cannot be checked: its code or its name,
    or, from three characters on, part of its name or of one of its other names."""
    if text == entry.iso or text == fold(entry.name):
        return True
    if len(text) < 3:
        return False
    return text in fold(entry.name) or any(text in fold(other) for other in entry.others)


def scripts_section(not_covered, text=u""):
    """The scripts known and not yet covered that the Languages tab lists in its closing section:
    all of them, or those a search names."""
    text = fold(text).strip()
    return [name for name in not_covered if not text or text in fold(name)]


def coverage_counts_text(checked, known, scripts_covered, scripts_known, uncovered=None, notations=0):
    """The sentence that counts what Font Check can check of what is known; uncovered and notations:
    how the scripts no language here is written in divide (the Languages tab lists the first as not yet
    covered; the notations are character sets), so that the counts add up."""
    if not known:
        return u""
    text = u"Font Check can check %s of the %s languages Glottolog lists with an ISO 639-3 code" % (
        grouped(checked), grouped(known))
    if scripts_known:
        text += u", written in %d of Unicode's %d scripts" % (scripts_covered, scripts_known)
        if uncovered is not None and notations:
            text += u" (%d not yet covered, and %s checked as %s)" % (
                uncovered, u"1 notation" if notations == 1 else u"%d notations" % notations,
                u"a character set" if notations == 1 else u"character sets")
    return text + u"."


def family_tree(results, families, text=u"", level=None, sort="reach", uncovered=None):
    """(root FamilyNode, hidden): the Families tab, the coverages under Glottolog's families and
    branches. A search keeps the languages it finds and those of the families and branches it names;
    level keeps one level only (hidden: the finds of a search it holds back). A branch that holds a
    single branch is skipped and one that holds a single language gives way to it, so each node listed
    tells things apart; the languages Glottolog does not classify come under a last node,
    UNCLASSIFIED. Within a node, its branches first (ordered as sort says), then its languages."""
    text = (text or u"").strip()
    root, hidden = FamilyNode(u""), 0
    for r in results:
        path = families.path(r.language.iso) if families is not None else ()
        if text and not (language_matches(r, text) or family_matches(path, text)):
            continue
        if level is not None and r.level != level:
            hidden += 1 if text else 0
            continue
        r.found_by = found_by(r, text) if text and not family_matches(path, text) else None
        node = root
        for name in path or (UNCLASSIFIED,):
            node = node.child(name)
        node.results.append(r)

    def tidy(node, top):
        for one in node.children:
            tidy(one, False)
        kept = []
        for one in node.children:
            while len(one.children) == 1 and not one.results:  # a single branch under it: skipped
                one.children, one.results = one.children[0].children, one.children[0].results
            if not top and not one.children and len(one.results) == 1:
                node.results.append(one.results[0])  # a branch of one language: the language itself
            else:
                kept.append(one)
        node.children = kept
        node.results = sort_languages(node.results, sort)
        node.children.sort(key=lambda one: family_order(one, sort))
        if sort == "za":
            node.children.reverse()
        node.children.sort(key=lambda one: one.name == UNCLASSIFIED and top)  # (stable: that one last)

    tidy(root, True)
    if uncovered and level is None:
        # Under each family, last, the languages of it that cannot be checked yet (a level kept alone
        # leaves them out: they have none). A search keeps those it names, or all those of a family it
        # names; a family none of whose languages is described is listed for them alone.
        folded = fold(text).strip()
        for name in sorted(uncovered, key=fold):
            entries = uncovered[name]
            if folded and folded not in fold(name):
                entries = [one for one in entries if uncovered_matches(one, folded)]
            if not entries:
                continue
            top = next((one for one in root.children if one.name == name), None) or root.child(name)
            top.uncovered = list(entries)
            top.children.append(UncoveredNode(top.path, entries))
        root.children.sort(key=lambda one: family_order(one, sort))
        if sort == "za":
            root.children.reverse()
        root.children.sort(key=lambda one: one.name == UNCLASSIFIED)  # (stable: that one last)
    return root, hidden


def family_order(node, sort):
    """What a family's branches are ordered by: the most languages covered or within reach first (as
    the scripts are), the most or the least covered share first, or their names."""
    counts = level_counts(node.all_results())
    total = float(sum(counts)) or 1.0
    name = fold(node.name)
    if sort in ("az", "za"):
        return (name,)
    if sort == "most":
        return (-counts[0] / total, -counts[1] / total, name)
    if sort == "least":
        return (counts[0] / total, counts[1] / total, name)
    return (-(counts[0] + counts[1]), -sum(counts), name)


def family_tip(node):
    """A family's tooltip: its place in Glottolog's classification and its languages at each level."""
    if isinstance(node, UncoveredNode):
        return u"%s\n\n%s" % (uncovered_sentence(node.entries).replace(u" more language", u" language", 1), CONTRIBUTE)
    counts = level_counts(node.all_results())
    place = u" > ".join(node.path) if len(node.path) > 1 else u""
    paragraphs = [counts_tip(node.name, counts)]
    if node.path == (UNCLASSIFIED,):
        paragraphs.append(UNCLASSIFIED_TIP)
    if place:
        paragraphs.append(u"Glottolog: %s." % place)
    if node.uncovered:
        paragraphs.append(uncovered_sentence(node.uncovered))
    return u"\n\n".join(paragraphs)


def families_line(root, text=u"", hidden=0, level=None, classified=True):
    """The line under the Families tab: what a search found, or where the classification comes from.
    The families counted are those holding a language found: not Not classified, and not a family
    listed for its languages that cannot be checked alone."""
    text = (text or u"").strip()
    languages = len(root.all_results())
    unclassified = sum(len(one.all_results()) for one in root.children if one.name == UNCLASSIFIED)
    families = sum(1 for one in root.children if one.name != UNCLASSIFIED and one.all_results())
    if not classified:
        return u"The families file (language_families.json) is not installed: the languages are not classified."
    if not text:
        return u"Families and branches as Glottolog 5.4 classifies them (CC BY 4.0)."
    state = STATE_LABELS.get(level, u"").lower()
    if not languages:
        if hidden:
            return u"%s, but %s not %s: choose All to see %s." % (
                u"1 language matches" if hidden == 1 else u"%d languages match" % hidden,
                u"is" if hidden == 1 else u"are", state, u"it" if hidden == 1 else u"them")
        if any(one.uncovered for one in root.children):
            return u"No language that can be checked matches."  # (those that cannot are listed and named below)
        return u"No family or language matches."
    matches = u"1 language matches" if languages == 1 else u"%d languages match" % languages
    if not unclassified:
        line = u"%s in %s." % (matches, counted(families, u"family", u"families"))
    elif not families:
        line = u"%s, not classified." % matches
    else:
        line = u"%s: %d in %s, %d not classified." % (matches, languages - unclassified,
                                                      counted(families, u"family", u"families"), unclassified)
    if hidden:
        line += u" %s, but %s not %s: choose All to see %s." % (
            u"1 more matches" if hidden == 1 else u"%d more match" % hidden, u"is" if hidden == 1 else u"are",
            state, u"it" if hidden == 1 else u"them")
    return line


def unlisted_line(found, shown=UNLISTED_SHOWN):
    """What a search says of the languages it names that Hyperglot does not describe (found:
    Families.unlisted_matches): they exist, and Font Check has no orthography to check them by."""
    if not found:
        return u""
    names = [u"%s (%s%s)" % (name, iso, u", also %s" % alias if alias else u"") for iso, name, alias in found[:shown]]
    if len(found) == 1:
        return (u"Glottolog also lists %s, which none of Font Check's sources documents an orthography for: Font "
                u"Check cannot check it." % names[0])
    if len(found) > shown:
        names.append(u"%d more" % (len(found) - shown))
    return (u"Glottolog also lists %d languages that none of Font Check's sources documents an orthography for, "
            u"which Font Check cannot check: %s." % (len(found), word_list(names)))


def alias_line(results):
    """What a search says of the finds it made by another name than the one listed."""
    found = [r for r in results if r.found_by]
    if not found:
        return u""
    if len(found) == 1:
        return u"%s is found by its other name %s." % (found[0].language.name, found[0].found_by)
    return u"%d are found by another name: their tooltips say which." % len(found)


def languages_line(sections, text=u"", hidden=0, outside=0, left=0, level=None, nouns=RIGHT_NOUNS["languages"]):
    """The line under the Languages tab or the Character sets tab (nouns: what its rows are, one and
    many): what a search found, or what is not listed and why (whole sentences, each count with its
    noun and verb in the right number). outside: the languages of the scripts not listed; left: those
    the choice of statuses leaves out; hidden: finds the level holds back."""
    text = (text or u"").strip()
    one, many = nouns
    found = sum(len(s.results) for s in sections)
    lines = []
    if text:
        state = STATE_LABELS.get(level, u"").lower()
        if not found:
            if hidden:  # (every find held back: one sentence, not "none matches" then "1 more matches")
                lines.append(u"%s, but %s not %s: choose All to see %s." % (
                    u"1 %s matches" % one if hidden == 1 else u"%d %s match" % (hidden, many),
                    u"is" if hidden == 1 else u"are", state, u"it" if hidden == 1 else u"them"))
                hidden = 0
            else:
                lines.append(u"No %s matches." % one)
        else:
            lines.append(u"%s %s." % (counted(found, one, many), u"matches" if found == 1 else u"match"))
            by_alias = alias_line([r for s in sections for r in s.results])
            if by_alias:
                lines.append(by_alias)
        elsewhere = sum(len(s.results) for s in sections if s.why)
        if elsewhere:
            lines.append(u"%s under a heading that says why %s not listed otherwise." % (
                u"1 is" if elsewhere == 1 else u"%d are" % elsewhere, u"it is" if elsewhere == 1 else u"they are"))
        if hidden:
            lines.append(u"%s, but %s not %s: choose All to see %s." % (
                u"1 more matches" if hidden == 1 else u"%d more match" % hidden, u"is" if hidden == 1 else u"are",
                state, u"it" if hidden == 1 else u"them"))
    else:
        if outside:
            lines.append(u"%s of the scripts not listed here %s hidden: a search finds %s too." % (
                counted(outside, u"language"), u"is" if outside == 1 else u"are", u"it" if outside == 1 else u"them"))
        if left:
            lines.append(u"%s left out by the Display choice above: a search finds %s too." % (
                u"1 language is" if left == 1 else u"%d languages are" % left, u"it" if left == 1 else u"them"))
    return u" ".join(lines)


TIP_SHOWN = 60  # characters named in a tooltip's list, at most (a block may miss hundreds, Mandarin thousands)
TIP_NAMES = 30  # languages named in a glyph's tooltip, at most (a schwa is needed by hundreds)
# A tooltip that cuts a list of missing characters short says where they are all listed.
CUT_TIP = u"Select it to list its missing glyphs at the left."


def few(items, shown=TIP_SHOWN):
    if any(slow_to_shape(item) for item in items[:shown]):
        return few_codes(items) + SLOW_BY_CODE
    text = u" ".join(items[:shown])
    if len(items) > shown:
        text += u" and %s more" % grouped(len(items) - shown)
    return text


# Characters whose font lays them out too slowly for a tooltip: FreeLang+ Duployan (Noto Sans Duployan's
# layout) took 3.5 ms a character, every time Qt laid the tooltip out; its 60 characters in a script's
# tooltip froze FontLab for 5.9 s as Qt sized it (measured live 2026-11-14; the next slowest script, Adlam,
# 0.7 ms). A tooltip names these by code point.
SLOW_SHAPING = ((0x1BC00, 0x1BCAF),)  # Duployan, and the shorthand format controls after it
SLOW_BY_CODE = u" (by code point: Duployan's font is too slow to lay out in a tooltip)"


def slow_to_shape(item):
    """Whether a character (or a letter and marks) is one a tooltip names by code point (SLOW_SHAPING)."""
    return any(low <= code <= high for code in code_points(item) for low, high in SLOW_SHAPING)


# What "not yet covered" means, said where the scripts not yet covered are listed (the owner wondered how
# they had full previews, and was surprised to see Braille, SignWriting, and Mongolian among them): the
# script is encoded and drawn; what is missing is a language described in it.
NOT_COVERED_MEANS = (u"Not yet covered means that none of Font Check's sources describes a language written in the "
                     u"script, not that the script is unknown or cannot be drawn: Unicode encodes it, its glyphs are "
                     u"drawn in FreeLang (or the system's fonts, for the largest scripts), and the font is checked "
                     u"against its whole repertoire.")
NO_LANGUAGE_DATA = (u"No language data exists for it yet: none of Font Check's sources gives an orthography written "
                    u"in it, so the script's whole repertoire is the measure. Not yet covered means only that: the "
                    u"script itself is encoded and drawn.")


def few_of(items, shown=TIP_SHOWN):
    """few() of a list that may be long or made as it is read (a script's missing characters): only
    the ones shown are made."""
    first = items[:shown]
    if any(slow_to_shape(item) for item in first):
        return few_codes(items) + SLOW_BY_CODE
    text = u" ".join(shown_text(item) for item in first)
    if len(items) > shown:
        text += u" and %s more" % grouped(len(items) - shown)
    return text


# The bundled list font, which tooltips are set in, cannot hold all of Unicode: it draws a script's
# set whole up to this many characters of its own, a Unicode block's set up to that many, and a Han
# repertoire up to the third (checks/train/orthographies.py's SCRIPT_FONT_LIMIT, BLOCK_FONT_LIMIT, and
# UNIHAN_FONT_LIMIT: the tests keep them equal). Since 2026-11-14 that is every script but Han and
# every block (they were 300 and 256). The tooltip of a larger set names what is missing by code
# point, not by characters that would show as boxes. The bounds decide that alone: a tooltip makes its
# first 60 characters whatever the set's size.
NAMED_SCRIPT_MOST, NAMED_BLOCK_MOST, NAMED_UNIHAN_MOST = 12000, 1100, 25000
# Those bounds hold with the optional CJK and FreeLang+ General files, which draw most of a set past
# the first file's bounds: 300, 256, and no Han repertoire (all three bounds before 2026-11-14). A set
# is held to them when a file it needs did not register (fallbacks_needed; the tests check it against
# the files' character maps), so its tooltip lists code points rather than boxes.
NAMED_SCRIPT_FEW, NAMED_BLOCK_FEW, NAMED_UNIHAN_FEW = 300, 256, 0
CJK_FALLBACK, GENERAL_FALLBACK = LIST_FONT_FALLBACKS[0][1], LIST_FONT_FALLBACKS[1][1]
CJK_SCRIPTS = (u"Han", u"Hangul", u"Hiragana", u"Katakana", u"Bopomofo")
CJK_SHARING = (u"Latin", u"Tangut", u"Yi")  # scripts drawn by FreeLang+ General with characters of the CJK file
ESSENTIAL_SETS = (u"Ethiopic", u"block-fb50")  # past the first bounds, and drawn by the first file alone
BY_CODE = u", by code point (a set this large is not drawn by the list's font)"


def fallbacks_needed(language):
    """The optional files (their families) a large set's characters are drawn by: a Han repertoire, a
    CJK script or block the CJK file; Latin (its fullwidth letters), Tangut, and Yi (the CJK
    punctuation they share) that one and FreeLang+ General; any other the latter, but Ethiopic and
    Arabic Presentation Forms-A (the first file's)."""
    iso = u"%s" % language.iso
    name = u"%s" % language.name if isinstance(language, ScriptSet) else None
    if name in ESSENTIAL_SETS or iso in ESSENTIAL_SETS:
        return ()
    if iso.startswith(u"unihan-") or name in CJK_SCRIPTS or (iso.startswith(u"block-") and u"CJK" in language.name):
        return (CJK_FALLBACK,)
    if name in CJK_SHARING:
        return (CJK_FALLBACK, GENERAL_FALLBACK)
    return (GENERAL_FALLBACK,)


def names_characters(language):
    """Whether a set's tooltip names its missing characters themselves (the list font draws them)."""
    drawn = LIST_FALLBACKS_DRAWN
    whole = drawn is None or all(family in drawn for family in fallbacks_needed(language))
    if isinstance(language, ScriptSet):
        return language.own_count <= (NAMED_SCRIPT_MOST if whole else NAMED_SCRIPT_FEW)
    if (u"%s" % language.iso).startswith(u"block-"):
        return language.size() <= (NAMED_BLOCK_MOST if whole else NAMED_BLOCK_FEW)
    if (u"%s" % language.iso).startswith(u"unihan-"):
        return language.size() <= (NAMED_UNIHAN_MOST if whole else NAMED_UNIHAN_FEW)
    return True


def few_codes(items, runs=6, looked=2000):
    """The first of a long list of characters as code points, runs of them together: "U+2E80 to
    U+2E99, U+2E9B to U+2EF3, and 103,235 more" (only the first `looked` are read)."""
    spans = []
    for item in items[:looked]:
        codes = code_points(item)
        if len(codes) != 1:
            continue
        if spans and codes[0] == spans[-1][1] + 1:
            spans[-1][1] = codes[0]
        else:
            spans.append([codes[0], codes[0]])
    shown = spans[:runs]
    named = sum(high - low + 1 for low, high in shown)
    text = u", ".join(u"U+%04X" % low if low == high else u"U+%04X to U+%04X" % (low, high) for low, high in shown)
    if len(items) > named:
        text += u", and %s more" % grouped(len(items) - named)
    return text


def script_tip(r, no_language=False, fonts=()):
    """A script's tooltip (a ScriptSet's coverage): its state, how many of its own and of its shared
    characters the font has, what the measure is (and, for a script no orthography here is written in,
    that no language data exists yet), and the first characters missing (by code point for a script
    too large for the list's font to draw)."""
    script = r.language
    own_count = script.own_count - script.optional_own
    shared_count = script.shared_count - script.optional_shared
    parts = [u"%s of its %s" % (grouped(own_count - len(r.missing)), counted_grouped(own_count, u"character"))]
    if shared_count:
        parts.append(u"%s of the %s it shares with other scripts" % (
            grouped(shared_count - len(r.auxiliary_missing)), grouped(shared_count)))
    optional = script.optional_own + script.optional_shared
    if optional:
        parts.append(optional_part(optional, len(r.optional_missing)))
    lines = [u"%s: %s (the font has %s)." % (script.name, STATE_LABELS[r.level].lower(),
                                             u", and ".join(parts) if len(parts) == 2 else word_list(parts))]
    if no_language and notation_reason(script.name):
        lines.append(u"A notation, not a language's own script: %s. No count of languages can rank a font for it, "
                     u"so its whole repertoire is the measure." % notation_reason(script.name))
    elif no_language:
        lines.append(NO_LANGUAGE_DATA)
    lines.append(script.definition)
    if not names_characters(script):
        if r.missing:
            lines.append(u"Missing%s: %s" % (BY_CODE, few_codes(r.missing)))
        if r.auxiliary_missing:
            lines.append(u"Shared characters missing: %s" % few_codes(r.auxiliary_missing))
        if r.composed:
            lines.append(u"%s composed from the font's letters and marks (its anchors)" % (
                u"1 is" if len(r.composed) == 1 else u"%s are" % grouped(len(r.composed))))
        if r.parts:
            lines.append(u"The font has the letters and marks of %s, but no anchors joining them" % (
                u"1 more" if len(r.parts) == 1 else u"%s more" % grouped(len(r.parts))))
        if r.optional_missing:
            lines.append(u"%s: %s" % (OPTIONAL_MISSING, few_codes(r.optional_missing)))
        return paragraphs_of(lines, any(len(found) > TIP_SHOWN for found in
                                        (r.missing, r.auxiliary_missing, r.optional_missing)), fonts)
    if r.missing:
        lines.append(u"Missing: %s" % few_of(r.missing))
    if r.auxiliary_missing:
        lines.append(u"Shared characters missing: %s" % few_of(r.auxiliary_missing))
    if r.composed:
        lines.append(u"Composed from the font's letters and marks (its anchors): %s" % few([c for c, _ in r.composed]))
    if r.parts:
        lines.append(u"The font has the letters and marks of %s, but no anchors joining them" % few(r.parts))
    if r.optional_missing:
        lines.append(u"%s: %s" % (OPTIONAL_MISSING, few_of(r.optional_missing)))
    return paragraphs_of(lines, any(len(found) > TIP_SHOWN for found in
                                    (r.missing, r.auxiliary_missing, r.optional_missing)), fonts)


# The paragraph of a set's tooltip that names its optional characters missing (never "auxiliary": a
# language's auxiliary character keeps it from being covered, an optional one does not)
OPTIONAL_MISSING = u"Optional characters missing (%s)" % OPTIONAL_WHAT


def optional_part(total, missing):
    """What a set's tooltip says the font has of its optional characters: "0 of the 57 optional ones"."""
    return u"%s of the %s optional %s" % (grouped(total - missing), grouped(total), u"one" if total == 1 else u"ones")


def paragraphs_of(lines, cut=False, fonts=()):
    """A tooltip's paragraphs, a blank line between two (the owner: line jumps between paragraphs read
    better); fonts: the fonts to consider for what FreeLang lacks of a set (fonts_sentence); cut: a list
    of characters was cut short, and the last paragraph says where it is whole."""
    return u"\n\n".join([line for line in lines if line] + [fonts_sentence(fonts)] * bool(fonts)
                        + ([CUT_TIP] if cut else []))


def set_tip(r, no_language=False, fonts=()):
    """A character set's tooltip: its state, the definition it is cited by, what the font misses, and
    the fonts to consider for what FreeLang does not draw of it (coverage_gaps.json's resources)."""
    if isinstance(r.language, ScriptSet):
        return script_tip(r, no_language, fonts)
    language = r.language
    required, optional = language.required_size(), language.optional_count
    if optional and not required:  # (a Legacy set: wholly optional, complete whatever the font has of it)
        has = u"%s of its %s, all optional: it is complete without them" % (
            grouped(optional - len(r.optional_missing)), counted_grouped(optional, u"character"))
    else:
        has = u"%s of its %s" % (grouped(required - len(r.missing)), counted_grouped(required, u"character"))
        if optional:
            has = u"%s, and %s" % (has, optional_part(optional, len(r.optional_missing)))
    lines = [u"%s: %s (the font has %s)." % (language.name, STATE_LABELS[r.level].lower(), has), language.definition]
    drawn = names_characters(language)
    if r.missing and not drawn:
        lines.append(u"Missing%s: %s" % (BY_CODE, few_codes(r.missing)))
    elif r.missing:
        lines.append(u"Missing: %s" % few_of(r.missing))
    if r.composed:
        lines.append(u"Composed from the font's letters and marks (its anchors): %s" % few([c for c, _ in r.composed]))
    if r.parts:
        lines.append(u"The font has the letters and marks of %s, but no anchors joining them" % few(r.parts))
    if r.optional_missing:
        lines.append(u"%s%s: %s" % (OPTIONAL_MISSING, u"" if drawn else BY_CODE,
                                    few_of(r.optional_missing) if drawn else few_codes(r.optional_missing)))
    return paragraphs_of(lines, len(r.missing) > TIP_SHOWN or len(r.optional_missing) > TIP_SHOWN, fonts)


INFERRED_TIP = (u"Inferred from text: these are the letters a counted text uses, not an orthography someone "
                u"declared. Rare letters may be missing from it, and a foreign one may be in it.")
KEYBOARD_TIP = (u"From a keyboard layout (Language Tools, Apache License 2.0): the characters its keys and rules "
                u"produce, not an orthography someone declared. A layout that composes letters by rules may lack "
                u"some, and one may type letters the language does not use (in Latin, every letter from a to z).")


SHORT_TEXT = 3000  # letters: an orthography inferred from one text shorter than this is the weakest in the list
SHORT_TIP = (u"It rests on one short text: the weakest evidence in this list. A text this short shows a language's "
             u"common letters only.")


def grouped(number):
    """A count with its thousands apart: 1,412."""
    return u"{0:,}".format(int(number))


def amount_text(letters, kind):
    """How much text a source counted: "a text of 1,412 letters", "a word list of 23,512 letters";
    u"" for a source that gives no count."""
    if not letters or kind not in ("text", "words"):
        return u""
    return u"%s of %s %s" % (u"a text" if kind == "text" else u"a word list", grouped(letters),
                             u"letter" if letters == 1 else u"letters")


def rests_text(language):
    """The sources an orthography rests on, each with how much text it counted where it says:
    "Unilex word frequencies (a word list of 23,512 letters) and Google Fonts' sample text (a text of
    1,204 letters)"; its one source's name when the data says no more."""
    names = []
    for name, letters, kind in language.rests:
        amount = amount_text(letters, kind)
        names.append(u"%s (%s)" % (name, amount) if amount else name)
    return word_list(names) if names else language.source


def short_text(language):
    """Whether an orthography rests on one short text alone."""
    return (language.evidence == INFERRED and len(language.rests) == 1 and language.rests[0][2] == "text"
            and 0 < language.rests[0][1] < SHORT_TEXT)


def source_text(language):
    """Where a language's characters come from, for its tooltip: the source, then what the source
    says of the language (Hyperglot: its status and validity; another source: declared or inferred,
    its draft level where it gives one, and the status). An inferred one names every source it rests
    on, with how much text each counted, so a designer can weigh it."""
    if language.source == HYPERGLOT:
        return u"Hyperglot: %s, %s" % (language.status, language.validity)
    parts = [{INFERRED: u"inferred from text", KEYBOARD: u"from a keyboard layout"}.get(language.evidence, u"declared")]
    if language.validity and language.validity != u"generated":  # (generated: the source's name says so)
        parts.append(u"draft level %s" % language.validity)
    parts.append(u"status %s" % language.status)
    return u"%s: %s" % (rests_text(language), u", ".join(parts))


def also_listed(groups):
    """What a language's tooltip says of the other scripts it is listed under (Pontic Greek under
    Cyrillic and Greek, Sanskrit under Devanagari and Nandinagari): a second orthography, not a row
    listed twice by mistake."""
    if not groups:
        return u""
    return u"Also listed under %s: it has an orthography in %s too." % (
        word_list(list(groups)), u"that script" if len(groups) == 1 else u"each of those scripts")


def coverage_tip(r, path=(), no_language=False, also=(), fonts=()):
    """A language's tooltip (path: the family and branches above it, Glottolog's): its state, its
    script (and its source's finer label, when the list groups it under another: Cree under Canadian
    Syllabics), where its characters come from (and that they are inferred from a text, when they
    are), the other scripts it is also listed under (also), the other name a search found it by, and
    the characters missing or composed, each list cut at TIP_SHOWN (Mandarin misses thousands: a
    tooltip the height of the screen). A paragraph each, a blank line between two. no_language: a
    script listed among those no orthography is written in says so; fonts: a set's fonts to consider."""
    if r.language.kind == "set":
        return set_tip(r, no_language, fonts)
    label, group = r.language.script, script_group(r.language.script)
    lines = [u"%s, %s script%s: %s (%s)." % (r.language.label(), group, u" (%s)" % label if label != group else u"",
                                             STATE_LABELS[r.level].lower(), source_text(r.language))]
    if r.language.evidence == INFERRED:
        lines.append(INFERRED_TIP)
        if len(r.language.rests) > 1:
            lines.append(u"Each letter is one a source's count keeps and another source has too, or one frequent "
                         u"enough in a single source.")
        elif short_text(r.language):
            lines.append(SHORT_TIP)
    elif r.language.evidence == KEYBOARD:
        lines.append(KEYBOARD_TIP)
    lines.append(also_listed(also))
    if r.found_by:
        lines.append(u"Found by its other name %s." % r.found_by)
    if path:
        lines.append(u"Family: %s." % u" > ".join(path))
    if r.missing:
        lines.append(u"Base characters missing: %s" % few(r.missing))
    if r.marks_missing:
        lines.append(u"Marks missing: %s" % few([DOTTED_CIRCLE + m for m in r.marks_missing]))
    if r.auxiliary_missing:
        lines.append(u"Auxiliary characters missing (loan words, names, rare letters): %s" % few(r.auxiliary_missing))
    if r.composed:
        lines.append(u"Composed from the font's letters and marks (its anchors): %s" % few([c for c, _ in r.composed]))
    if r.parts:
        lines.append(u"The font has the letters and marks of %s, but no anchors joining them" % few(r.parts))
    return paragraphs_of(lines, any(len(found) > TIP_SHOWN for found in (r.missing, r.marks_missing,
                                                                          r.auxiliary_missing)))


def set_counts_note(r):
    """A character set's or a script's own note, its optional characters aside: what it misses of
    what it needs (counts, not characters: the list's font draws the languages' characters, not every
    symbol), u"" when it misses none."""
    if r.level == "covered":
        return u""
    if isinstance(r.language, ScriptSet):
        if not r.missing:  # (its own characters are all there: what it shares with other scripts is not)
            return u"%s shared missing" % grouped(len(r.auxiliary_missing))
        return u"%s of %s missing" % (grouped(len(r.missing)), grouped(r.language.required_size()))
    return u"%s of %s missing" % (grouped(len(r.missing)), grouped(r.language.required_size()))


def with_optional(note, optional):
    """A set's note with its optional glyphs missing: "4 optional glyphs missing" alone (it is covered,
    or misses nothing else), or after the rest, "158 of 168 missing (and 4 optional glyphs)"."""
    if not optional:
        return note
    if not note:
        return u"%s missing" % counted_grouped(optional, u"optional glyph")
    return u"%s (and %s)" % (note, counted_grouped(optional, u"optional glyph"))


def counted_grouped(number, one, many=None):
    """counted(), its number with its thousands apart: "1,002 optional glyphs"."""
    return u"%s %s" % (grouped(number), one if number == 1 else (many or one + u"s"))


def language_note(r):
    """The second column of a language: its missing characters when within reach, "composed" when
    covered thanks to the anchors, "inferred" when its characters were counted from a text,
    "keyboard" when they were read from a keyboard layout."""
    if r.language.kind == "set" and (r.level != "covered" or r.optional_missing):
        return with_optional(set_counts_note(r), len(r.optional_missing))
    if r.level == "nearly":
        return compact_missing(r)
    # (an inferred language, or one read from a keyboard layout, says so in the list itself, where it
    # shows no missing characters)
    words = ([u"composed"] if r.level == "covered" and r.composed else []) + (
        [u"inferred"] if r.language.evidence == INFERRED else [u"keyboard"] if r.language.evidence == KEYBOARD else [])
    return u", ".join(words)


# A tooltip's width follows the window's (the owner: tooltips were "stupidly compacted when there's ample
# space"): about half of it, between TIP_LEAST and TIP_MOST pixels, never wider than the window less
# TIP_MARGIN. It was a fixed 520 pixels. TIP_WIDTH stands when the window's width cannot be read.
TIP_SHARE, TIP_LEAST, TIP_MOST = 0.5, 360, 900
TIP_WIDTH = 520  # pixels: a tooltip's text at most, when the window's width cannot be read
TIP_MARGIN = 40  # pixels kept between a tooltip's width and the window's
TIP_NATURAL = 400  # pixels: a tooltip whose longest line is shorter is left to its own width
TIP_CHARACTER = 7  # pixels: a character's width, as tooltips are measured (twice that for a wide one)
# Wide characters (ideographs, kana, Hangul syllables, Tangut, fullwidth forms), estimated at two widths: a
# table of ranges, not the runtime's Unicode data (FontLab's Python has Unicode 5.2: the same text must get
# the same width under either interpreter).
WIDE_RANGES = ((0x1100, 0x115F), (0x2E80, 0x303E), (0x3041, 0x33FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
               (0xA000, 0xA4CF), (0xAC00, 0xD7A3), (0xF900, 0xFAFF), (0xFE30, 0xFE4F), (0xFF00, 0xFF60),
               (0xFFE0, 0xFFE6), (0x16FE0, 0x18CFF), (0x1B000, 0x1B2FF), (0x20000, 0x3FFFD))
TAG = None  # (made when first needed: a tag of rich text)


def tip_limit(window_width):
    """The width a tooltip's text may take, in pixels, for a window this wide (None: not known): about
    half of it, between TIP_LEAST and TIP_MOST, and never wider than the window less TIP_MARGIN."""
    try:
        width = int(window_width)
    except (TypeError, ValueError):
        return TIP_WIDTH
    if width <= 0:
        return TIP_WIDTH
    limit = max(TIP_LEAST, min(TIP_MOST, int(width * TIP_SHARE)))
    if width > TIP_MARGIN + 200:
        limit = min(limit, width - TIP_MARGIN)
    return limit


def line_width(line):
    """A line's width in pixels, estimated: TIP_CHARACTER a character, twice that for a wide one.
    Tooltips were measured in the dialog's font, which sent Qt looking through the system's fonts for
    every script that font lacks: Duployan's tooltip froze the window for seconds as it was measured."""
    width = 0
    for code in code_points(line):
        wide = any(low <= code <= high for low, high in WIDE_RANGES) if code >= 0x1100 else False
        width += 2 if wide else 1
    return width * TIP_CHARACTER


def plain_of(text):
    """Rich text without its tags, to measure."""
    global TAG
    if TAG is None:
        import re
        TAG = re.compile(u"<[^>]*>")
    return TAG.sub(u"", text).replace(u"&lt;", u"<").replace(u"&gt;", u">").replace(u"&amp;", u"&")


def tip_width(text, limit=TIP_WIDTH, measure=None, rich=False):
    """The width to give a tooltip: limit pixels when its longest line is wider, that line's width
    when it is wider than TIP_NATURAL (Qt wraps rich text a little past 80 characters of its own
    accord, narrower than the room a wide window leaves), None for a short one, left as it is.
    measure: a line's width in pixels (line_width, an estimate, when not given)."""
    widest = 0
    lines = [plain_of(line) if rich else line for line in (u"%s" % (text or u"")).replace(u"<br>", u"\n").split(u"\n")]
    # The longest line first, and no further once one is too wide: each row of each list has a tooltip,
    # and measuring every line of every one (some 10,000 at an opening) was part of the seconds it took.
    for line in sorted(lines, key=len, reverse=True):
        if widest > limit:
            break
        width = 0
        if measure is not None:
            try:
                width = int(measure(line))
            except Exception:
                width = 0
        if not width > 0:
            width = line_width(line)
        widest = max(widest, width)
    if widest > limit:
        return int(limit)
    return min(int(limit), int(widest) + 2 * TIP_CHARACTER) if widest > TIP_NATURAL else None


def tip_html(text, width=None, family=None, rich=False):
    """A tooltip as rich text: Qt wraps rich text, and shows plain text on one line however long (a
    tree row's tooltip ran thousands of pixels wide). text: plain, a line per line, escaped here
    (rich: rich text already). width: pixels its text is laid out in (a one-cell table: Qt's rich text
    takes a width from nothing else), None for a text short enough. family: the font its text is set
    in (the bundled FreeLang, for names and characters the interface font lacks)."""
    text = u"%s" % (text or u"")
    if not text:
        return u""
    if not rich:
        text = text.replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;").replace(u"\n", u"<br>")
    style = u" style=\"font-family:'%s'\"" % family.replace(u"'", u"") if family else u""
    if width:
        return (u"<table width=\"%d\" cellspacing=\"0\" cellpadding=\"0\"><tr><td%s>%s</td></tr></table>"
                % (int(width), style, text))
    return u"<span%s>%s</span>" % (style, text)


def hint_height(widget):
    """A widget's size hint's height (0 where it cannot be read)."""
    try:
        hint = widget.sizeHint
        hint = hint() if callable(hint) else hint
        return max(0, int(hint.height()))
    except Exception:
        return 0


def level_rows(boxes):
    """Rows of controls (each a widget whose layout holds a row) made as tall as one another, so what is
    under them stays where it is as tabs are switched (owner's images 285 and 286, in Kerning Check: a row
    of a button alone was a few pixels shorter than one with a spin box, and the table under it moved up):
    each row's least height the tallest size hint of the controls in any of them, hidden ones too. Read
    when called (after the window's styles). The height set, or 0. Never raises."""
    tallest = 0
    for box in boxes:
        try:
            layout = box.layout()
            for index in range(int(layout.count())):
                widget = layout.itemAt(index).widget()
                if widget is not None:
                    tallest = max(tallest, hint_height(widget))
        except Exception:
            continue
    if tallest:
        for box in boxes:
            try:
                box.setMinimumHeight(tallest)
            except Exception:
                pass
    return tallest


class Tab(object):
    """A page: its settings row, a line, then what it shows. Its status line stands in the window's
    header, under the top line (FontCheckDialog.show_tab_parts: the shown tab's only; the owner wanted
    every window's status there, never under its controls), and its buttons in the window's bottom row
    (actions: at the left; commit: at the right, before Close), shown with the tab."""

    def __init__(self, ak, QtGui):
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        # (its settings row in a widget of its own: as tall as the other tabs' rows, level_rows)
        self.settings_box = QtGui.QWidget()
        self.settings = QtGui.QHBoxLayout(self.settings_box)
        self.settings.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.settings_box)
        self.line = ak.separator()
        self.layout.addWidget(self.line)
        self.status = ak.status_label()  # (placed in the header by the dialog)
        self.actions = QtGui.QWidget()  # (the bottom row's left part, this tab's)
        self.actions_row = QtGui.QHBoxLayout(self.actions)
        self.actions_row.setContentsMargins(0, 0, 0, 0)
        self.commit = None  # (the bottom row's committing button, this tab's, if any)
        self.findings = []


class TabNames(object):
    """A tab bar that never scrolls: its tabs' whole names kept here, and shown elided (tab_texts) when
    the bar is too narrow for them all, the chosen tab's whole; fitted again as a tab is chosen and, on
    the next turn of the event loop, as the bar is resized. The bar ignores its names' width (it never
    widens the window: the window sizes the bar)."""

    def __init__(self, bar, texts):
        QtCore, QtGui = _qt()
        self.bar, self.texts = bar, [u"%s" % text for text in texts]
        try:
            bar.setUsesScrollButtons(False)
            bar.setElideMode(QtCore.Qt.ElideRight)  # (Qt's own, should the chosen tab alone pass the room)
            bar.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Fixed)
        except Exception:
            pass

        class Resized(QtCore.QTimer):  # (as FontCheckDialog.watch_resize: a timer stands for a QObject)
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize: fitted on the next turn, never inside Qt's layout
                        self.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.watch = Resized(bar)  # (its parent the bar: Qt deletes it with it)
        try:
            self.watch.setSingleShot(True)
            self.watch.setInterval(0)
            self.watch.connect("timeout()", self.fit)
            bar.installEventFilter(self.watch)
            bar.connect("currentChanged(int)", self.chosen)
        except Exception:
            pass

    def chosen(self, index):
        self.fit()

    def set_text(self, index, text):
        """A tab named anew (its whole name), and the names fitted."""
        if 0 <= index < len(self.texts):
            self.texts[index] = u"%s" % text
        self.fit()

    def room(self):
        return int(_prop(self.bar, "width"))

    def measure(self):
        QtCore, QtGui = _qt()
        metrics = QtGui.QFontMetrics(_prop(self.bar, "font"))
        return lambda text: int(metrics.width(text))

    def fit(self):
        """Each tab's name as tab_texts has it for the bar's width now. Never raises."""
        try:
            shown = tab_texts(self.texts, int(_prop(self.bar, "currentIndex")), self.room(), self.measure())
        except Exception:
            shown = self.texts
        for index, text in enumerate(shown):
            try:
                if u"%s" % self.bar.tabText(index) != text:
                    self.bar.setTabText(index, text)
            except Exception:
                pass


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
        self.diacritics = None  # Glyph Compose's module, loaded when first needed
        self.buildable = None  # the characters Glyph Compose can build, asked once per check
        self.generated = None  # those of them its Glyph generation tab builds (buildable_set)
        self.plan_font = None  # (package, Glyph Compose's module, its Font of the glyphs): made once per check
        self.scripts, self.results, self.rows, self.own_rows = [], [], [], []  # rows: the high-value list's;
        # own_rows: the selection's own tab's
        self.checked = set()  # characters checked, in either tab of characters
        self.other_results, self.set_results = [], []  # languages the Languages choice leaves out; character sets
        self.families = None  # Glottolog's families and other names (None without their file)
        self.selection = None  # the Selection: the language, character set, or family selected at the right
        self.left_tab, self.right_tab = "value", "languages"  # the tabs shown (their bars' signals say so)
        self.right_trees = {}
        self.right_rows = dict((key, []) for key, _ in RIGHT_TABS)  # each right tab's rows: Coverages, FamilyNodes
        self.closed = dict((key, set()) for key, _ in RIGHT_TABS)  # the headings closed, by title (never by item)
        self.scripts_open = False  # the Languages tab's closing section, Scripts not yet covered: closed until asked for
        self.unfilled = dict((key, {}) for key, _ in RIGHT_TABS)  # closed rows whose rows are not made yet:
        # a heading's title or a family's place, and the languages or the FamilyNode waiting
        self.row_tools = None  # the dots and the quiet color the rows are drawn with, made once per filling
        self.opened = set()  # the families opened, by their place: all closed to start with
        self.reveal = False  # the selected language's family opened as the Families tab is next filled
        self.pressed = None  # the selection's key when the mouse was pressed on its own row
        self.asked = set()  # the selections whose characters Glyph Compose was asked about
        self.script_filter = None
        self.list_family = None  # FreeLang once registered: the font of names and characters in tooltips
        self.tip_cache = {}  # the tooltips of the lists' rows made so far, for this check (right_tip)
        self.generation = 0  # one more at each check: what the lists at the right were filled from
        self.views = {}  # each right tab's lists (VIEW_MODES): every script's, one script's, a search's (build_coverage)
        self.groups_of = {}  # ISO 639-3 code: the scripts' groups its orthographies are listed under
        self.has_coverage = False  # a check has finished: the lists have something to search, sort, or select
        self.coverage_gaps = CoverageGaps()  # what Font Check knows of and does not check (read with the data)
        self.stepwise = False  # long work step by step, the window repainted in between: once it is shown (show)
        self.deferred = None  # the next step, kept for its timer
        self.known_scripts = KnownScripts()  # Unicode's scripts no orthography is written in, and scripts recorded
        self.font_found = None  # the font's FontCharacters as last read (a pasted set is checked against it)
        self.pasted_text = u""  # the text of the Character sets tab's field
        try:  # the sets the user saved (FreeLab's settings folder)
            self.custom_sets = load_custom_sets(os.path.join(ak.state_dir(), CUSTOM_SETS_FILE))
        except Exception:
            self.custom_sets = []
        self.metric_values, self.extents_found, self.suggestions, self.notes = None, [], [], []
        self.check_rows, self.clipped = [], []
        self.capitals, self.letters = True, None
        self.problems, self.glyph_names, self.compare_masters = [], [], []
        self.fixable_names = set()  # the glyphs listed with problems Fix sets right
        self.fix_unchecked, self.fix_basis = set(), None  # rows unchecked by hand (for this font and reference)
        self.pictures = {}  # (kind, key): an icon drawn (the characters to add)
        self.drawing_failed = False
        self.filters, self.redraws = [], {}
        # The lists at the right share their width themselves (size_columns): each one's kind, its columns
        # the user dragged, and the delegates that draw the families' bars, by list
        self.column_kinds, self.pinned_columns, self.column_trees = {}, {}, {}
        self.column_slots, self.delegates, self.sharing = [], [], False
        main = ak.AutoKerningDialog.main_window()
        dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        self.dialog = dialog
        dialog.setWindowTitle("FreeLab Font Check")
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)  # (as wide as the other tools until a font comes: widen, read_font)
        layout = ak.window_layout(dialog)  # (scrolls on a small screen)
        # The header, as every window's (owner's images 222, 223, 276): the top line, the shown tab's
        # status line under it, the header's line (shown even with no font), then the tabs
        self.font_label = ak.status_label()
        layout.addWidget(self.font_label)
        self.header_box = QtGui.QVBoxLayout()  # (the tabs' status lines: show_tab_parts)
        self.header_box.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.header_box)
        self.header_line = ak.header_separator()
        layout.addWidget(self.header_line)
        self.log = ak.Log()
        self.log.link_handler = self.log_link  # (the glyphs a line names, each opened on a click)
        # A tab bar over plain pages: a QTabWidget's themed page drew its buttons with light frames in dark mode
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setWhatsThis(u"The three views of the font: <i>Coverage</i> (the languages, character sets, and "
                               u"scripts its glyphs cover), <i>Vertical metrics</i> (its line metrics against its "
                               u"tallest and deepest glyphs), and <i>Masters</i> (what keeps its masters from "
                               u"interpolating). Each is checked as its tab is first shown.")
        layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.redraw_timer = QtCore.QTimer(dialog)  # (its parent the window: Qt deletes it with it)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(80)
        self.redraw_timer.connect("timeout()", self.redraw_now)
        self.build_coverage(QtCore, QtGui)
        self.build_metrics(QtCore, QtGui)
        self.build_masters(QtCore, QtGui)
        tab_helps = (u"The languages, character sets, and scripts the font's glyphs cover, and the glyphs each one "
                     u"misses. Checked as the tab is first shown.",
                     u"The font's line metrics against its tallest and deepest glyphs, and the values to write "
                     u"instead. Checked as the tab is first shown.",
                     u"What keeps the font's masters from interpolating: each glyph missing in a master, or whose "
                     u"contours, nodes, components, or anchors differ from the chosen master's, and the fixes that "
                     u"can be made. Checked as the tab is first shown.")
        for tab, label, text in zip((self.coverage, self.metrics, self.masters), ("Coverage", "Vertical metrics", "Masters"),
                                    tab_helps):
            index = self.tabs.addTab(label)
            self.tabs.setTabWhatsThis(index, text)  # (a right-click on a tab tells of it: owner's image 329)
            self.pages.addWidget(tab.widget)
            self.header_box.addWidget(tab.status)
        self.tab_names = {"window": TabNames(self.tabs, (u"Coverage", u"Vertical metrics", u"Masters")),
                          "left": TabNames(self.left_tabs, (value_title(None), selection_title(None))),
                          "right": TabNames(self.right_tabs, [label for _, label in RIGHT_TABS])}
        layout.addWidget(self.log.widget)
        # The bottom row, as every window's (owner's images 258 to 265, 279): at the left the shown tab's
        # buttons that act on its lists' ticks and rows, and Show in Glyph window; at the right the shown
        # tab's committing button, then Cancel and Close
        buttons = QtGui.QHBoxLayout()
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens a <i>Glyph</i> window on the ticked glyphs of the tab "
                                              u"shown, or, with none ticked, on the selected row's (FontLab shows "
                                              u"the ones the font lacks as placeholders), or on the selected glyph. "
                                              u"A double-click on a row opens that row's glyph alone.")
        self.close_button = QtGui.QPushButton("Close")
        self.close_button.setWhatsThis(u"Closes <i>Font Check</i>. Nothing is written by closing: what was written "
                                       u"to the font stays, and the sets you saved stay on this computer.")
        for tab in (self.coverage, self.metrics, self.masters):
            buttons.addWidget(tab.actions)
        buttons.addWidget(self.glyph_window_button)
        buttons.addStretch(1)
        for tab in (self.coverage, self.metrics, self.masters):
            if tab.commit is not None:
                buttons.addWidget(tab.commit)
        buttons.addWidget(self.close_button)
        ak.cancel_button(self, buttons, self.close_button, CANCEL_NOTE)  # (right before Close)
        layout.addLayout(buttons)
        self.show_tab_parts()
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        ak.add_tools_button(dialog, "Font Check", getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.level_settings()
        try:  # the check boxes drawn plain to see in either palette (the lists' pictures stay unmapped)
            fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            self.check_watcher = fc.watch_check_boxes(dialog, [self.add_tree, self.own_tree, self.glyph_tree])
        except Exception:
            self.check_watcher = None
        if self.read_font():
            # (two lists side by side: the shared 1000 pixels cut the right one's last column; with no font,
            # as wide as the other tools, widened when a font comes: font_changed, owner's image 279)
            self.widen(dialog)
        self.history_timer = ak.watch_history(self)
        self.flagging = [ak.flag_menu(self.glyph_tree, self, self.selected_glyphs, self.row_glyph),
                         ak.flag_menu(self.clipped_list, self, self.selected_glyphs)]
        self.update_buttons()

    def screen_width(self, dialog):
        """The width of the free area of the dialog's screen, as ak.size_dialog reads it; None when
        it cannot be read."""
        QtCore, QtGui = _qt()
        try:
            width = int(QtGui.QApplication.desktop().availableGeometry(dialog).width())
        except Exception:
            return None
        return width if width > 0 else None

    def widen(self, dialog):
        """Font Check opens wider than the other tools (WIDE, or what the screen allows), at the
        height the shared size gave it. It never narrows the dialog, and never raises."""
        try:
            width = wide_width(self.screen_width(dialog))
            now, height = int(_prop(dialog, "width")), int(_prop(dialog, "height"))
            if width > now and height > 0:
                dialog.resize(width, height)
        except Exception:
            pass

    def widen_for_font(self):
        """A font came to this window, opened without one at the other tools' size (owner's image 279: "maybe
        this window can stay the same size as the others? Then if a font is opened and the window hooks to
        it, window widens according to its content"): it widens as it would have opened with the font (widen),
        around its center, kept on the screen, as ak.widen_window does: never narrower, never once the owner
        gave a window its size by hand (this one since it opened, or every window this session: ak.note_size),
        nor while it is maximized, minimized, or hidden. The pixels it grew by; never raises."""
        try:
            ak, dialog = self.ak, self.dialog
            if not _prop(dialog, "visible") or _prop(dialog, "maximized") or _prop(dialog, "minimized"):
                return 0
            registry = getattr(ak, "_windows", None)
            if registry is not None and registry().get("size") is not None:
                return 0  # (a size given by hand this session: every window opens at it)
            size = (int(_prop(dialog, "width")), int(_prop(dialog, "height")))
            opened = getattr(self, "opened_size", None)
            if opened is not None and (abs(size[0] - opened[0]) > 2 or abs(size[1] - opened[1]) > 2):
                return 0  # (resized by hand: the owner's size stays)
            width = wide_width(self.screen_width(dialog))
            if width <= size[0]:
                return 0
            place = _prop(dialog, "pos")
            place = (int(place.x()), int(place.y()))
            area = ak.screen_area(dialog)
            frame = (0, 0)
            try:
                outer = _prop(dialog, "frameGeometry")
                frame = (max(0, int(outer.width()) - size[0]), max(0, int(outer.height()) - size[1]))
            except Exception:
                pass
            x, y = ak.centered_place(place, size, (width, size[1]), area, frame)
            dialog.resize(width, size[1])
            dialog.move(x, y)
            if opened is not None:
                self.opened_size = (width, size[1])  # (FreeLab's doing, not a size given by hand)
            return width - size[0]
        except Exception:
            return 0

    def size_columns(self, tree, kind):
        """A list at the right whose columns the user can drag (the owner's report 126: Qt's Stretch and
        ResizeToContents modes, set here before, cannot be dragged) and that shares its width itself
        (share_columns, column_widths): the names' column takes what the others leave (cut with an
        ellipsis, whole in its tooltip), the counts stay whole, the families' bar gives way to BAR_LEAST
        first and is drawn to its column's width (bar_delegate). A column dragged keeps its width; the
        names' column (or, when it is the one dragged, the bar's or the last one) takes up the rest, so
        the frame is never left with a gap. kind: COLUMN_KINDS'. Each call guarded."""
        QtCore, QtGui = _qt()
        self.column_kinds[id(tree)] = kind
        self.pinned_columns[id(tree)] = {}
        self.column_trees[id(tree)] = tree
        try:
            header = tree.header()
            header.setStretchLastSection(False)
            try:
                # (a drag stops at the shared least: dragged to nothing, a column could not be found again,
                # owner's image 214; column_widths may still close the bar's column in a narrow window)
                header.setMinimumSectionSize(int(getattr(self.ak, "MIN_SECTION", 24)))
            except Exception:
                pass
            for column in range(int(_prop(tree, "columnCount"))):
                header.setSectionResizeMode(column, QtGui.QHeaderView.Interactive)
            tree.setProperty("freelab_own_columns", True)  # (for the shared module: this list shares its own width)
        except Exception:
            pass
        owner = self

        def dragged(column, old, new):
            owner.column_dragged(tree, column, new)

        def moved(*args):
            owner.columns_soon(tree)

        slots = [dragged, moved]
        self.column_slots.extend(slots)  # (kept: PythonQt holds no reference to a connected function)
        try:
            tree.header().connect("sectionResized(int,int,int)", dragged)
            bar = tree.verticalScrollBar()
            bar.connect("rangeChanged(int,int)", moved)  # (rows made, opened, or closed)
            bar.connect("valueChanged(int)", moved)  # (other rows shown: their counts may be wider)
        except Exception:
            pass
        if kind == "bars":
            self.bar_delegate(tree)

    def column_dragged(self, tree, column, width):
        """A column resized: by the user's drag (a mouse button held) it keeps that width (pinned), and the
        others share what is left; by share_columns itself, nothing. Never raises."""
        try:
            if self.sharing:
                return
            QtCore, QtGui = _qt()
            if int(QtGui.QApplication.mouseButtons()) == 0:
                return
            self.pinned_columns.setdefault(id(tree), {})[int(column)] = int(width)
            self.columns_soon(tree)
        except Exception:
            pass

    def columns_soon(self, tree):
        """The list's columns shared again a moment later (redraw_now), never inside Qt's own resizing."""
        try:
            self.redraws[("columns", id(tree))] = True
            self.redraw_timer.start()
        except Exception:
            pass

    def share_columns(self, tree):
        """The list's columns given the widths column_widths finds for its viewport's width now, from what
        its rows shown want (Qt measures those, as its own ResizeToContents did). Never raises."""
        kind = self.column_kinds.get(id(tree))
        if kind is None:
            return
        try:
            room = int(_prop(tree.viewport(), "width"))
            count = int(_prop(tree, "columnCount"))
            header = tree.header()

            def wants(column):
                try:
                    head = int(header.sectionSizeHint(column))
                except Exception:
                    head = 0
                return max(int(tree.sizeHintForColumn(column)), head)

            wanted = [wants(column) for column in range(count)]
            if kind == "bars":
                wanted[0] = min(wanted[0], FAMILY_NAMES_MOST)
                wanted[1] = BAR_COLUMN
                # (the long counts give way first, elided, then the bar: live at 1,000 pixels the counts kept
                # their whole width, the names were cut to "Austr...", and the bars squeezed to 20 pixels)
                widths = column_widths(room, wanted, 0, (2, 1), {0: NAME_LEAST, 1: BAR_LEAST, 2: COUNTS_LEAST},
                                       self.pinned_columns.get(id(tree)))
            else:
                widths = column_widths(room, wanted, 0, (), {0: NAME_LEAST}, self.pinned_columns.get(id(tree)))
        except Exception:
            return
        self.sharing = True
        try:
            for column, width in enumerate(widths):
                if int(tree.columnWidth(column)) != width:
                    tree.setColumnWidth(column, width)
        except Exception:
            pass
        finally:
            self.sharing = False

    def bar_delegate(self, tree):
        """The families' bars drawn in their cells, as wide as their column less BAR_MARGIN each side, from
        the counts each row holds (BAR_ROLE): a picture of a set width was cut by a narrower column, and
        gone with a column of nothing (the owner's reports 127 and 131). What it uses is held here: a
        dropped module's globals turn None."""
        QtCore, QtGui = _qt()
        role, margin, levels, widths_of = BAR_ROLE, BAR_MARGIN, BAR_LEVELS, bar_widths
        colors = dict((level, level_color(level)) for level in BAR_LEVELS)  # (the same in either palette)

        class Bars(QtGui.QStyledItemDelegate):
            def paint(self, painter, option, index):
                QtGui.QStyledItemDelegate.paint(self, painter, option, index)
                try:
                    text = u"%s" % (index.data(role) or u"")
                    counts = [int(part) for part in text.split(u",")] if text else []
                    rect = option.rect
                    width = int(rect.width()) - 2 * margin
                    if len(counts) != len(levels) or width <= 0:
                        return
                    x, top = int(rect.left()) + margin, int(rect.top()) + int(rect.height()) // 2 - 4
                    for level, w in zip(levels, widths_of(counts, width)):
                        if w:
                            painter.fillRect(QtCore.QRect(x, top, w, 8), colors[level])
                            x += w
                except Exception:
                    pass  # a delegate's paint must never raise

        try:
            delegate = Bars(tree)  # (its parent the list: Qt deletes it with it)
            tree.setItemDelegateForColumn(1, delegate)
            self.delegates.append(delegate)
        except Exception:
            pass

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
        self.ak.table_layout(tree, grid=grid)  # (FreeLab's one table layout; grid lines or none)
        return tree

    @staticmethod
    def label_for(text, control):
        """The label of a control, with the control's own What's This: asked about, a label answered
        for the whole dialog, or not at all."""
        QtCore, QtGui = _qt()
        label = QtGui.QLabel(text)
        try:
            label.setWhatsThis(_prop(control, "whatsThis") or u"")
            label.setBuddy(control)
        except Exception:
            pass
        return label

    @staticmethod
    def heading(text):
        QtCore, QtGui = _qt()
        label = QtGui.QLabel(text)
        font = QtGui.QFont(_prop(label, "font"))
        font.setBold(True)
        label.setFont(font)
        return label

    def use_list_font(self, tree, scale=LIST_SCALE):
        """The languages list (its rows, section headings, and column headings) in FreeLang, at
        LIST_SCALE times the dialog's size: rows grow with it, and a section heading's bold font is made
        from the list's (section_row). Without the font file, or if Qt refuses it, the list keeps its
        family and is still enlarged; tooltips keep Qt's own font. This never raises. scale 1: a widget
        that shows names or characters of any script at the dialog's size (the glyphs' lists, whose
        Languages column drew Hadramautic's letters as boxes; the fields; the lines that name languages)."""
        try:
            QtCore, QtGui = _qt()
            font = QtGui.QFont(_prop(tree, "font"))
            family = register_list_font(QtCore, QtGui)
            if family:
                font.setFamily(family)
            if scale != 1:
                unit, size = scaled_size(font.pointSizeF(), font.pixelSize(), scale)
                if unit == "point":
                    font.setPointSizeF(size)
                elif unit == "pixel":
                    font.setPixelSize(size)
            tree.setFont(font)
        except Exception:
            pass

    def in_list_font(self, text):
        """Rich text (escaped already) set in FreeLang, for the log's lines that quote characters or a
        set's name: the log's own font drew boxes for scripts it lacks."""
        if not self.list_family:
            return text
        return u"<span style=\"font-family:'%s'\">%s</span>" % (self.list_family.replace(u"'", u""), text)

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

        found = Resized(widget)  # (its parent the widget it watches: Qt deletes it with it)
        widget.installEventFilter(found)
        self.filters.append(found)

    def watch_presses(self, tree):
        """list_pressed told of each mouse press on a list, and of a double-click's second press,
        before Qt handles it (the row under the mouse, None on the list's empty part); the press goes
        no further when it says so (a press on a family's arrow opens or closes it, and selects
        nothing)."""
        QtCore, QtGui = _qt()
        owner = self

        class Pressed(QtCore.QTimer):  # (as Resized: a timer stands for the QObject PythonQt cannot subclass)
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind in (2, 4):  # MouseButtonPress, MouseButtonDblClick
                        pos = event.pos()
                        return owner.list_pressed(tree, tree.itemAt(pos), pos, kind == 4) is True
                    if kind == 110:  # ToolTip: a row's tooltip is made now (show_tip)
                        return owner.show_tip(tree, event) is True
                except Exception:
                    pass  # an event filter must never raise
                return False

        found = Pressed(tree)  # (its parent the list: Qt deletes it with it)
        tree.viewport().installEventFilter(found)
        self.filters.append(found)

    def theme_changed(self):
        """Dark mode switched, either way (the shared module's theme_switched, once the pictures drawn in
        one palette color and the quiet rows are in the new colors): the pictures kept for the next
        filling dropped, and what is drawn in several colors drawn again (the diagram, the comparison,
        the checks' badges, the clipped glyphs, the masters' glyphs). Nothing is read again."""
        self.pictures = {}
        self.row_tools = None
        self.redraws = dict((key, True) for key in ("diagram", "comparison"))
        try:
            selected = self.selected_glyph()  # (filled again, the glyphs' list selects its first row)
        except Exception:
            selected = None
        for draw in (self.redraw_now, self.fill_checks, self.fill_clipped, self.fill_glyphs):
            try:
                draw()
            except Exception:
                pass  # (that view not filled yet: drawn when it is)
        try:
            for item in self.top_items(self.glyph_tree):
                if selected is not None and u"%s" % self.data_of(item, None) == selected:
                    self.glyph_tree.setCurrentItem(item)
                    break
        except Exception:
            pass

    def redraw_now(self):
        keys, self.redraws = list(self.redraws), {}
        for key in keys:
            try:
                if key == "diagram":
                    self.draw_diagram()
                elif key == "comparison":
                    self.draw_comparison()
                elif isinstance(key, tuple) and key[0] == "columns":
                    self.share_columns(self.column_trees[key[1]])
            except Exception:
                pass  # a timer's handler must not raise

    def build_coverage(self, QtCore, QtGui):
        ak = self.ak
        tab = self.coverage = Tab(ak, QtGui)
        self.nearly = QtGui.QSpinBox()
        self.nearly.setRange(0, 30)
        self.nearly.setValue(NEARLY_MISSING)
        ak.counted_suffix(self.nearly, u"glyph")  # ("1 glyph", "2 glyphs": the shared helper keeps it in step)
        self.nearly.setWhatsThis(u"A language missing at most this many glyphs for its base characters (and marks), or "
                                 u"only auxiliary ones, is within reach: its missing glyphs are listed at the left.")
        tab.settings.addWidget(self.label_for("Within reach: missing at most", self.nearly))
        tab.settings.addWidget(self.nearly)
        self.status_filter = QtGui.QComboBox()
        self.status_filter.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)  # (as wide as its widest item: image 239)
        for _, label, _ in STATUS_FILTERS:
            self.status_filter.addItem(label)
        self.status_filter.setCurrentIndex([key for key, _, _ in STATUS_FILTERS].index(STATUS_START))
        self.status_filter.setWhatsThis(u"Which languages are counted and listed: all of them to start with, by "
                                        u"their status (the living and constructed ones, Esperanto among them; the "
                                        u"living ones only; the historical ones only, with no native speakers left: "
                                        u"Latin, Ancient Greek), or the high-value ones only. Hyperglot gives each "
                                        u"language's status; a language from another source whose status is not given "
                                        u"counts with the living ones. <i>High-value only</i> keeps the languages "
                                        u"Unicode's CLDR targets at its modern level (those the major platforms ship "
                                        u"in), those official in a country or territory, and those at least a million "
                                        u"people read and write, in the scripts CLDR writes them in (about 300). A "
                                        u"search finds the languages left out too.")
        # (once its help is set: the label's too; "Display:" with its colon, as every caption: image 271)
        tab.settings.addWidget(self.label_for("Display:", self.status_filter))
        tab.settings.addWidget(self.status_filter)
        self.inferred_box = QtGui.QCheckBox(INFERRED_TITLE)
        self.inferred_box.setChecked(True)
        self.inferred_box.setWhatsThis(u"Counts and lists the languages whose characters no source declares. Most are "
                                       u"the letters a text in the language uses, counted (by SIL's tools, or from "
                                       u"Unilex's or An Cr\xfabad\xe1n's counts, the Universal Declaration of Human "
                                       u"Rights, or Google Fonts' sample texts), so a rare letter may be missing and a "
                                       u"foreign one present: their rows say <i>inferred</i>. Others are the "
                                       u"characters a keyboard layout of Language Tools types, so a letter its rules "
                                       u"do not spell out may be missing and a spare one present: their rows say "
                                       u"<i>keyboard</i>, and some are a second script of a language a source declares "
                                       u"in another. Their tooltips name the source. Unticked, only the languages a "
                                       u"source declares are counted (Hyperglot, Google Fonts' language data, Unicode "
                                       u"CLDR, SIL's Locale Data Repository); a search still finds the others.")
        tab.settings.addWidget(self.inferred_box)
        self.composing = QtGui.QCheckBox("Count letters its anchors compose.")
        self.composing.setChecked(True)
        self.composing.setWhatsThis(u"A letter with a diacritic the font lacks as one glyph counts as there when the "
                                    u"font has the letter and the combining mark, and the letter has an anchor the "
                                    u"mark attaches to (top and _top): applications compose it. Unticked, only the "
                                    u"font's own glyphs count.")
        tab.settings.addWidget(self.composing)
        self.coverage_button = QtGui.QPushButton("Check")
        self.coverage_button.setWhatsThis(u"Reads the font and checks its coverage again, with the settings of this "
                                          u"row: the languages, the character sets, and the scripts. The view is "
                                          u"also checked as it opens and after an undo or an edit in FontLab.")
        tab.settings.addWidget(self.coverage_button)
        tab.settings.addStretch(1)

        self.script_tree = self.tree(("Script", "", "Languages"), icon=BAR_SIZE, header=False, grid=False)
        # (after the table layout's rules, as BRANCH_SHEET is: replaced, they came back in front of it at
        # the first dark mode switch, and the list changed its look then)
        self.script_tree.setStyleSheet(u"%s %s" % (_prop(self.script_tree, "styleSheet") or u"", SCRIPT_SHEET))
        self.script_tree.setWhatsThis(u"The scripts the font has, the most languages covered first: each bar shows "
                                      u"its languages covered (green), within reach (amber), started (red: the font "
                                      u"has some of their glyphs, too few to be within reach), and missed (gray: "
                                      u"it has none). Click a script to see only its languages below.")
        # The lists stand on the second page of a stack; the first is blank, shown while the data is read
        # and the font checked (the window opened on empty lists and zero counts for seconds, as if broken),
        # the progress bar in the window's top row saying alone what is happening (it was said there, in a
        # centered line on this page, and in the top line: twice at once). set_busy shows one or the other.
        self.coverage_stack = QtGui.QStackedWidget()
        self.busy_label = QtGui.QLabel(u"")
        self.busy_label.setAlignment(QtCore.Qt.AlignCenter)
        try:
            font = QtGui.QFont(_prop(self.busy_label, "font"))
            font.setPointSizeF(font.pointSizeF() * 1.4 if font.pointSizeF() > 0 else 14.0)
            self.busy_label.setFont(font)
        except Exception:
            pass
        self.coverage_stack.addWidget(self.busy_label)
        content = QtGui.QWidget()
        content_layout = QtGui.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.coverage_stack.addWidget(content)
        self.coverage_stack.setCurrentIndex(1)
        # The check's progress is the window's own, in its top row (ak.busy_start: owner's images 174 and 180),
        # determinate over the four steps (BUSY_SHARES) and, within the listing, over the rows made; the
        # tools menu, the arrows, Close, and Esc stop it (coverage_stopped). It stood over the lists before.
        tab.layout.addWidget(self.coverage_stack, 1)
        # (the lists' halves a child of the page before the scripts' list, though laid out under it: the shared
        # module grays a Tick button when the first shown list it finds has nothing to tick, every list as near
        # to the bottom row's buttons; in the order Qt finds them, the glyphs' list shown comes first, then the
        # scripts' list, which has no ticks: ak.update_states)
        self.coverage_halves_made = QtGui.QSplitter(QtCore.Qt.Horizontal)
        try:
            self.coverage_halves_made.setParent(content)
        except Exception:
            pass
        content_layout.addWidget(self.script_tree)
        absent = QtGui.QHBoxLayout()
        self.show_absent = QtGui.QCheckBox(absent_caption(None))  # (its caption carries the count: fill_scripts)
        self.show_absent.setChecked(True)
        self.show_absent.setWhatsThis(u"Lists the scripts the font has none of (fewer than five of their letters) "
                                      u"too, and their languages below.")
        absent.addWidget(self.show_absent)
        absent.addStretch(1)
        content_layout.addLayout(absent)

        # (the lists' frames hug the splitter's handle: margins beside it set it in the middle of a gap, away
        # from the frames it sizes, owner's image 196)
        halves = self.coverage_halves_made
        left = QtGui.QWidget()
        box = QtGui.QVBoxLayout(left)
        box.setContentsMargins(0, 0, 0, 0)
        # Two tabs of characters: the high-value list, and the selection's own missing characters, which
        # moved to the top of the first list before, above the high-value rows. A tab bar over a stack, as
        # the window's own tabs (a QTabWidget's themed page drew light frames in dark mode).
        self.left_tabs = QtGui.QTabBar()
        self.left_tabs.setExpanding(False)
        self.left_tabs.addTab(value_title(None))  # (no count before the first check)
        self.left_tabs.addTab(selection_title(None))
        self.left_tabs.setTabEnabled(1, False)  # (grayed until a language, a set, or a family is selected)
        self.left_tabs.setWhatsThis(u"The glyphs to add. The first tab ranks what the languages within reach miss "
                                    u"by the languages each glyph completes. The second lists only the missing "
                                    u"glyphs of the language, character set (a script of Unicode is one), or "
                                    u"family selected at the right: it is grayed, and reads <i>%s</i>, until one "
                                    u"is selected, and is then named after it. A glyph ticked in "
                                    u"one tab is ticked in the other." % UNSELECTED_TITLE)
        try:  # (each tab says the same when pointed at)
            self.left_tabs.setTabToolTip(0, self.tip(u"What the languages within reach miss, ranked by the "
                                                     u"languages each glyph completes."))
            self.left_tabs.setTabToolTip(1, self.tip(u"The missing glyphs of the language, character set, script, or "
                                                     u"family selected at the right: select one there first."))
        except Exception:
            pass
        box.addWidget(self.left_tabs)
        self.gain_label = ak.status_label()
        box.addWidget(self.gain_label)
        self.own_label = ak.status_label()  # (whose characters the second tab lists, while it is shown)
        self.own_label.setVisible(False)
        box.addWidget(self.own_label)
        # (the buttons on the glyphs' ticks, and those that hand the ticked glyphs on, stand in the window's
        # bottom row, the tab's own, as every window's: owner's image 279)
        row = tab.actions_row
        self.check_buttons, self.check_slots = {}, []
        tips = {"all": u"Ticks every glyph listed in the tab of glyphs shown (the ticks of rows not listed are "
                       u"kept).",
                "none": u"Unticks every glyph, those not listed in the tab of glyphs shown too.",
                "buildable": u"Ticks the glyphs listed in the tab of glyphs shown that <i>Glyph Compose</i> can "
                             u"build from the font's glyphs (glyphs with diacritics, and the spaces, dashes, quotes, "
                             u"and other glyphs of its <i>Glyph generation</i> tab), and unticks the others."}
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
        self.left_pages = QtGui.QStackedWidget()
        self.add_tree = self.tree(("", "Glyph", "", "Languages"), icon=CHAR_ICON)
        self.add_tree.setWhatsThis(u"The glyphs the languages within reach miss, the ones completing the most "
                                   u"languages on their own first (+N: the languages it completes alone; a capital and "
                                   u"its small letter together). Tick some: the line above says how many languages "
                                   u"they complete together. A double-click on a row opens its glyph in a "
                                   u"<i>Glyph</i> window.")
        self.own_tree = self.tree(("", "Glyph", "", "Languages"), icon=CHAR_ICON)
        self.own_tree.setWhatsThis(u"The missing glyphs of the language, character set (a script of Unicode is one), "
                                   u"or family selected at the "
                                   u"right, and nothing else: those the first tab ranks come first, then the others "
                                   u"(the first 200; the line above counts the rest). Ticks are shared with the "
                                   u"first tab. A double-click on a row "
                                   u"opens its glyph in a <i>Glyph</i> window.")
        self.left_pages.addWidget(self.add_tree)
        self.left_pages.addWidget(self.own_tree)
        # In FreeLang, at the dialog's size: the Languages column names what else a language misses
        # ("Hadramautic (with" and six of its letters), which the interface font drew as boxes; the line
        # over the list and the tab's caption name a selection, a set of the user's own in any script.
        for widget in (self.add_tree, self.own_tree, self.own_label, self.gain_label, self.left_tabs):
            self.use_list_font(widget, 1)
        box.addWidget(self.left_pages, 1)
        self.diacritics_button = QtGui.QPushButton("Build with Glyph Compose")
        self.diacritics_button.setWhatsThis(HANDOFF_HELP)
        self.copy_chars_button = QtGui.QPushButton("Copy glyphs")
        self.copy_chars_button.setWhatsThis(u"Copies the ticked glyphs of the tab of glyphs shown (or the selected "
                                            u"row's) as text.")
        self.declare_button = QtGui.QPushButton(DECLARE_BUTTON)
        self.declare_button.setWhatsThis(u"Sets the font info's Unicode ranges and code pages to what the font's glyphs "
                                         u"cover, where they differ (the log says how). One step of FontLab's History: "
                                         u"<i>Edit &gt; Undo</i> takes it back. Usable only while they differ.")
        self.declare_button.setEnabled(False)
        self.declare_button.connect("clicked()", self.declare_coverage)
        row = tab.actions_row
        row.addWidget(self.diacritics_button)
        row.addWidget(self.copy_chars_button)
        row.addWidget(self.declare_button)
        right = QtGui.QWidget()
        box = QtGui.QVBoxLayout(right)
        box.setContentsMargins(0, 0, 0, 0)
        # Three tabs: the languages by script, the character sets that are no languages (they came under
        # the languages before), and the languages by family. Each has a list of its own, so each keeps
        # its place as the tabs are switched; the search, the level, and the order act on the tab shown.
        self.right_tabs = QtGui.QTabBar()
        self.right_tabs.setExpanding(False)
        for _, label in RIGHT_TABS:
            self.right_tabs.addTab(label)
        self.right_tabs.setWhatsThis(u"<i>Languages</i>: the languages, under their scripts. <i>Character sets</i>: "
                                     u"sets that are no languages (IPA, mathematics, symbols, Unicode blocks, Google "
                                     u"Fonts' and Adobe's sets), each one's tooltip naming its definition, and every "
                                     u"script of Unicode, measured by its whole repertoire. "
                                     u"<i>Families</i>: the languages under their families and branches, as Glottolog "
                                     u"classifies them, each with a bar in the scripts' colors. Each tab's caption "
                                     u"counts what it lists.")
        box.addWidget(self.right_tabs)
        row = QtGui.QHBoxLayout()
        self.search = QtGui.QLineEdit()
        try:
            self.search.setPlaceholderText(SEARCH_PLACEHOLDER)
        except Exception:
            pass
        try:  # (a cross in the field clears it at once, as the owner asked; PythonQt may lack the call)
            self.search.setClearButtonEnabled(True)
        except Exception:
            pass
        # A search waits for a pause in the typing (SEARCH_DELAY): each keystroke listed the tab anew, a
        # few seconds for every letter of a name in FontLab. Clearing the field shows the full list at once.
        self.search_timer = QtCore.QTimer(self.dialog)  # (its parent the window: Qt deletes it with it)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(SEARCH_DELAY)
        self.search_timer.connect("timeout()", self.search_paused)
        self.search.setWhatsThis(u"Shows, in the tab shown, the languages whose name, autonym, code, or other name "
                                 u"holds this text (Glottolog's other names: <i>Nama</i> finds Khoekhoe, and the row's "
                                 u"tooltip says which name it was found by), the character sets whose name does, or "
                                 u"the families and branches so named with their languages. Case and diacritics are "
                                 u"set aside. A search looks through every language: one of a script not listed, or "
                                 u"left out by <i>Display</i>, comes under a heading that says so, and a language "
                                 u"none of Font Check's sources describes is named under the list.")
        self.level_filter = QtGui.QComboBox()
        self.level_filter.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)  # (as wide as its widest item: image 239)
        for _, label in LANGUAGE_FILTERS:
            self.level_filter.addItem(label)
        self.level_filter.setWhatsThis(u"Shows every language, or only the covered ones, those within reach, those "
                                       u"started (the font has at least one of their glyphs, too few to be within "
                                       u"reach), or those missed (it has none).")
        self.sort_box = QtGui.QComboBox()
        self.sort_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)  # (as wide as its widest item: image 239)
        for _, label in SORTS:
            self.sort_box.addItem(label)
        self.sort_box.setWhatsThis(u"The order of the languages within each script or family: those within reach "
                                   u"first (the fewest glyphs missing first, then the covered ones, then the "
                                   u"others), the most covered first, the least covered first, or by name, A to Z or "
                                   u"Z to A. A family's branches follow the same order.")
        row.addWidget(self.search, 1)
        row.addWidget(self.level_filter)
        row.addWidget(self.sort_box)
        box.addLayout(row)
        self.right_pages = QtGui.QStackedWidget()
        self.language_tree = self.tree(("Language", "Missing"), icon=(DOT_SIZE, DOT_SIZE))
        self.set_tree = self.tree(("Character set", "Missing"), icon=(DOT_SIZE, DOT_SIZE))
        self.family_tree = self.tree(("Family", "", "Languages", "Not yet covered"), icon=BAR_SIZE)
        # Each tab has a second list for a search's finds: the full list stays as it is, behind it, so
        # clearing the search shows it again at once, where it was scrolled to, with nothing made anew
        # (it was made anew at each keystroke, some 2,600 rows: seconds in FontLab).
        # And three for the last scripts chosen above (VIEW_MODES): every script's list stays as it is too, so
        # clicking All scripts again shows it at once, and so does a script chosen lately
        made_trees = dict(((key, mode), self.tree(columns, icon=icon)) for key, columns, icon in (
            ("languages", ("Language", "Missing"), (DOT_SIZE, DOT_SIZE)),
            ("sets", ("Character set", "Missing"), (DOT_SIZE, DOT_SIZE)),
            ("families", ("Family", "", "Languages", "Not yet covered"), BAR_SIZE))
            for mode in SCRIPT_MODES + ("search",))
        searches = dict((key, made_trees[(key, "search")]) for key, _ in RIGHT_TABS)
        self.family_search_tree = searches["families"]
        colors = (u"A dot per row: covered (green), within reach (amber), started (red: the font has some of its "
                  u"glyphs), missed (gray: it has none). ")
        selecting = (u"Clicking a row opens the second tab of glyphs at the left on what it misses; clicking it "
                     u"again, or an empty part of this list, unselects it. A double-click shows its glyphs in "
                     u"a <i>Glyph</i> window. ")
        self.language_tree.setWhatsThis(colors + u"Within reach, a language shows the glyphs it misses. " + selecting
                                        + u"Click a script's heading to close or open it. The last heading, "
                                        u"<i>Scripts not yet covered</i>, lists the scripts Unicode encodes that no "
                                        u"language here is written in: each is checked as a script, by its whole "
                                        u"repertoire, and selects like a language.")
        self.set_tree.setWhatsThis(colors + u"A set that is not covered says how many of its characters are missing; "
                                   u"its tooltip names its definition. Optional characters (presentation forms and "
                                   u"compatibility characters, which text does not store) are counted apart: a set is "
                                   u"covered without them, and those of <i>Legacy</i> are all optional. Under <i>Scripts (Unicode)</i>, every script "
                                   u"Unicode encodes is a set: its own characters are the measure, and those it "
                                   u"shares with other scripts count as auxiliary ones (a large script, such as "
                                   u"Han, lists its first 200 missing glyphs and counts the rest). " + selecting
                                   + u"Click a heading to close or open it.")
        self.family_tree.setWhatsThis(u"The languages under their families and branches (Glottolog's classification), "
                                      u"each family with a bar of its languages covered (green), within reach "
                                      u"(amber), started (red), and missed (gray). Click a family's arrow, or "
                                      u"double-click its name, to open or close it; click its name to list what its "
                                      u"languages miss at the left. " + selecting)
        for key, tree in (("languages", self.language_tree), ("sets", self.set_tree), ("families", self.family_tree)):
            searches[key].setWhatsThis(u"%s A search lists its finds here; clearing the search shows the whole "
                                       u"list again, as it was." % _prop(tree, "whatsThis"))
            for mode in SCRIPT_MODES:  # (one place, shown in turn: one help, SCRIPT_MODES)
                made_trees[(key, mode)].setWhatsThis(u"%s This list shows the script chosen above; clicking <i>All "
                                                     u"scripts</i> shows every script's list again, as it was, and "
                                                     u"so does clicking one of the last three scripts chosen."
                                                     % _prop(tree, "whatsThis"))
            for one in [tree] + [made_trees[(key, mode)] for mode in SCRIPT_MODES] + [searches[key]]:
                self.use_list_font(one)
                try:
                    one.setIndentation(16)
                    one.setExpandsOnDoubleClick(False)  # (list_pressed opens and closes: once per double-click)
                    # The arrows are icons drawn in the text color (arrow_pixmap): the style's own branch marks,
                    # dark whatever the palette, are left out (on the list itself, never on the dialog).
                    one.setStyleSheet(u"%s%s" % (_prop(one, "styleSheet") or u"", BRANCH_SHEET))
                except Exception:
                    pass
                self.right_pages.addWidget(one)  # (in VIEW_MODES' order, len(VIEW_MODES) pages per tab)
            self.views[key] = dict([("full", RightView(tree)), ("search", RightView(searches[key]))]
                                   + [(mode, RightView(made_trees[(key, mode)])) for mode in SCRIPT_MODES])
            self.right_trees[key] = tree
        try:  # (registered by the lists above; asked again for its name: tooltips and pictures use it too)
            self.list_family = register_list_font(QtCore, QtGui)
        except Exception:
            self.list_family = None
        box.addWidget(self.right_pages, 1)
        # A set of the user's own, under the Character sets tab: text or characters pasted here are
        # checked as a set (its missing glyphs go to the left as any set's), and can be saved under a name
        # in FreeLab's settings folder. This is how a language no source describes is checked all the same.
        self.custom_row = QtGui.QWidget()
        row = QtGui.QHBoxLayout(self.custom_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.paste_field = QtGui.QLineEdit()
        self.name_field = QtGui.QLineEdit()
        try:
            self.paste_field.setPlaceholderText(PASTE_PLACEHOLDER)
            self.name_field.setPlaceholderText(NAME_PLACEHOLDER)  # (the owner's wording for both)
        except Exception:
            pass
        self.paste_field.setWhatsThis(u"Text or characters pasted here are checked as a character set of your own, "
                                      u"listed first under <i>Your sets</i> as <i>Pasted characters</i>: each "
                                      u"character once, spaces left out, a letter with a combining mark that has no "
                                      u"single character kept together. Its missing glyphs are listed at the left, "
                                      u"as any set's. Use it for a language no source describes: paste its alphabet "
                                      u"or a text in it.")
        self.name_field.setWhatsThis(u"The name the pasted characters are saved under by <i>Save set</i>: a set saved "
                                     u"under a name already used replaces that one.")
        self.save_set_button = QtGui.QPushButton("Save set")
        self.save_set_button.setWhatsThis(u"Saves the pasted characters as a set under the name given, in FreeLab's "
                                          u"settings folder on this computer (not in the font): it is listed under "
                                          u"<i>Your sets</i> each time <i>Font Check</i> opens.")
        self.remove_set_button = QtGui.QPushButton("Remove set")
        for button in (self.save_set_button, self.remove_set_button):  # (each writes your sets' file, outside the
            ak.mark_risky(button)  # font's History, and may replace or remove a set: FreeLab MCP's risky mode)
        self.remove_set_button.setWhatsThis(u"Removes the selected set of your own from the saved ones.")
        row.addWidget(self.paste_field, 3)
        row.addWidget(self.name_field, 1)
        row.addWidget(self.save_set_button)
        row.addWidget(self.remove_set_button)
        self.custom_row.setVisible(False)  # (shown with the Character sets tab)
        box.addWidget(self.custom_row)
        self.languages_note = QtGui.QLabel(u"")  # what a search found, or what is not listed and why
        self.languages_note.setWordWrap(True)
        self.languages_note.setVisible(False)
        try:  # (the repository's address in it is a link where Qt can open one, and is written out in any case)
            self.languages_note.setOpenExternalLinks(False)
            self.languages_note.connect("linkActivated(QString)", self.open_address)
        except Exception:
            pass
        box.addWidget(self.languages_note)
        # What is typed, pasted, or named there may be in any script (an autonym searched, an alphabet
        # pasted, another name a search found a language by): in FreeLang, at the dialog's size.
        for widget in (self.search, self.paste_field, self.name_field, self.languages_note):
            self.use_list_font(widget, 1)
        halves.addWidget(left)
        halves.addWidget(right)
        halves.setStretchFactor(0, 1)
        halves.setStretchFactor(1, 1)
        self.coverage_halves = halves
        try:  # (the languages' lists a little wider than the characters': Qt scales the two to the room there is)
            halves.setSizes(list(split_sizes(wide_width(self.screen_width(self.dialog)))))
        except Exception:
            pass
        # The lists at the right: the names' column takes what the others leave, and the counts are as
        # wide as their contents (at 1000 pixels the families' counts were cut: "95 of 177 la..."); the
        # user can drag any column (size_columns), and the families' bars are drawn to their column's width.
        for key, _ in RIGHT_TABS:
            for mode in VIEW_MODES:
                tree = self.views[key][mode].tree
                self.size_columns(tree, COLUMN_KINDS[key])
                self.watch_resize(tree, ("columns", id(tree)))  # (shared again as it is resized)
        # The shared module clears a list's selection on a click beside it (its empty part, the window's
        # background); these lists' selections feed the others (the script chosen, the selection's tab of
        # glyphs), and the lists at the right unselect on a click in their empty part themselves
        # (list_pressed): left to them, by the property the shared module reads (KEEP_SELECTION_PROP)
        for tree in [self.script_tree] + [self.views[key][mode].tree for key, _ in RIGHT_TABS
                                          for mode in VIEW_MODES]:
            try:
                tree.setProperty(getattr(ak, "KEEP_SELECTION_PROP", "freelab_keep_selection"), True)
            except Exception:
                pass
        content_layout.addWidget(halves, 1)
        # Nothing to show before the first check: the scripts' list and its check box come with it (item 12
        # of the owner's audit: what has nothing to show is hidden, what cannot act is grayed, update_buttons)
        self.script_tree.setVisible(False)
        self.show_absent.setVisible(False)

        self.coverage_button.connect("clicked()", self.check_coverage)
        self.script_tree.connect("itemSelectionChanged()", self.script_selected)
        self.show_absent.connect("toggled(bool)", lambda on: self.absent_toggled())
        self.list_slots = []  # (kept: PythonQt holds no reference to a connected lambda)

        def left_slots(key, tree):
            return (("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.add_checked()),
                    ("itemSelectionChanged()", lambda: self.characters_selected()),
                    ("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.character_double_clicked(key, item)))

        def right_slots(key, tree):
            # (each tab has two lists, the full one and a search's: only the one shown is heard; the other
            # signals as it is filled or its selection set, in the background)
            def shown():
                return self.right_trees.get(key) is tree

            return (("itemSelectionChanged()", lambda: shown() and self.right_selected(key)),
                    ("itemClicked(QTreeWidgetItem*,int)", lambda item, column: shown() and self.right_clicked(key)),
                    ("itemDoubleClicked(QTreeWidgetItem*,int)",
                     lambda item, column: shown() and self.right_double_clicked(key, item)),
                    ("itemExpanded(QTreeWidgetItem*)", lambda item: shown() and self.right_expanded(key, item, True)),
                    ("itemCollapsed(QTreeWidgetItem*)", lambda item: shown() and self.right_expanded(key, item, False)))

        for slots, trees in ((left_slots, (("value", self.add_tree), ("own", self.own_tree))),
                             (right_slots, [(key, self.views[key][mode].tree) for key, _ in RIGHT_TABS
                                            for mode in VIEW_MODES])):
            for key, tree in trees:
                for signal, slot in slots(key, tree):
                    tree.connect(signal, slot)
                    self.list_slots.append(slot)
                self.watch_presses(tree)
        self.left_tabs.connect("currentChanged(int)", self.left_tab_changed)
        self.right_tabs.connect("currentChanged(int)", self.right_tab_changed)
        self.search.connect("textChanged(QString)", lambda text: self.search_typed())
        self.level_filter.connect("currentIndexChanged(int)", lambda index: self.languages_changed())
        self.sort_box.connect("currentIndexChanged(int)", lambda index: self.languages_changed())
        self.status_filter.connect("currentIndexChanged(int)", lambda index: self.status_changed())
        self.inferred_box.connect("toggled(bool)", lambda on: self.status_changed())
        self.diacritics_button.connect("clicked()", self.build_with_diacritics)
        self.copy_chars_button.connect("clicked()", self.copy_characters)
        self.paste_field.connect("textChanged(QString)", lambda text: self.pasted_changed())
        self.name_field.connect("textChanged(QString)", lambda text: self.update_buttons())
        self.save_set_button.connect("clicked()", self.save_set)
        self.remove_set_button.connect("clicked()", self.remove_set)

    # -- the loading state, and the steps long work is done in ------------------

    def set_busy(self, on, message=u""):
        """Long work under way (or over), in the window's top row (ak.busy_start: the step's name and the
        bar, the tools menu, the arrows, Close, and Esc stopping it): the lists' area gives way to a blank
        page, and the controls that would do nothing meanwhile are grayed, through ak.enable (a control
        grayed for want of a font stays grayed: owner's image 203). busy also holds off the History's watch
        and a second check."""
        was, self.busy = self.busy, bool(on)
        try:
            self.coverage_stack.setCurrentIndex(0 if on else 1)
            for widget in (self.nearly, self.status_filter, self.inferred_box, self.composing, self.coverage_button,
                           self.tabs):
                self.ak.enable(widget, not on)
        except Exception:
            pass
        try:  # the view's line hidden meanwhile (the top row says what runs), shown again only with something to say
            # (shown empty, it left a blank line under the Coverage controls: owner's image 204)
            text = u"%s" % (_prop(self.coverage.status, "text") or u"")
            self.coverage.status.setHidden(bool(on) or not text.strip() or self.current_key() != "coverage")
        except Exception:
            pass
        if on and not was:
            self.ak.busy_start(self, message)
        elif on:
            self.say_busy(message)
        elif was:
            self.ak.busy_end(self)

    def progress_to(self, done, part=0.0):
        """The top row's bar moved: done steps of BUSY_STEPS are over, and this part (0 to 1) of the next
        one. Raises ak.Stopped when the user asked the check to stop."""
        self.ak.busy_progress(self, None, busy_share(done, part))

    def say_busy(self, message, done=None):
        """What is happening now, said once, in the top row (it was said in the top line and in the middle
        of the lists' area too, the owner: "'Listing...' appears twice"), the bar at done steps of
        BUSY_STEPS when given. Raises ak.Stopped when the user asked the check to stop."""
        self.ak.busy_progress(self, message or None, busy_share(done) if done is not None else None)

    def defer(self, function):
        """The next step of long work: from a zero timer in a window that is shown, so Qt repaints
        between two steps and the tool is never entered again from inside itself (only the top row's
        guard lets events through in a step, and no click or key: ak.busy_progress); at once otherwise
        (a window not shown has nothing to repaint)."""
        if not self.stepwise:
            function()
            return
        QtCore, QtGui = _qt()
        self.deferred = function  # (kept: PythonQt holds no reference to a timer's callable)
        QtCore.QTimer.singleShot(0, self.run_deferred)

    def run_deferred(self):
        try:
            function, self.deferred = self.deferred, None
            if function is not None:
                function()
        except Exception:
            pass  # a timer's handler must not raise

    def run_steps(self, steps, index=0):
        """One step of long work, then the next (defer): each step does its part and returns what the
        window says while the next one runs. A step that fails ends the work, and says why; a stop asked
        meanwhile (the tools menu, an arrow, Close, Esc: owner's image 174) is taken before the next step
        and at each of the listing's (coverage_stopped)."""
        try:
            self.ak.busy_progress(self)  # (asked between two steps: nothing more is done)
            message = steps[index]()
            if index + 1 < len(steps):
                self.say_busy(message, index + 1)
        except self.ak.Stopped:
            self.coverage_stopped()
            return
        except Exception as exc:
            self.set_busy(False)
            self.coverage.status.setText(u"")
            self.log.add(self.ak.html(exc), "error")
            return
        if index + 1 < len(steps):
            self.defer(lambda: self.run_steps(steps, index + 1))

    def coverage_stopped(self):
        """The coverage check stopped by the user: what it made is let go, the Coverage view as if it had
        not been checked (its lists empty), the log saying so; Check checks it anew, and so does the view
        shown again. Then the top row does what was clicked (ak.busy_end). Never raises."""
        try:
            self.clear_coverage()
        except Exception:
            pass
        self.stale.add("coverage")
        try:
            self.set_busy(False)
            self.log.add(u"The coverage check was stopped: nothing is listed. Click <i>Check</i> to check it again.",
                         "warning")
            self.update_buttons()
        except Exception:
            pass

    def open_address(self, address):
        """A click on the repository's address: opened in the browser where Qt can (FontLab's Python
        cannot be relied on to; the address stays written out either way). A notation's set's name: that
        set shown in the Character sets tab (show_set)."""
        try:
            if (u"%s" % address).startswith(SET_LINK):
                self.show_set((u"%s" % address)[len(SET_LINK):].replace(u"&amp;", u"&"))
                return
            QtCore, QtGui = _qt()
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(u"%s" % address))
        except Exception:
            pass  # a signal's handler must not raise

    def build_metrics(self, QtCore, QtGui):
        ak = self.ak
        tab = self.metrics = Tab(ak, QtGui)
        self.metrics_button = QtGui.QPushButton("Check")
        self.metrics_button.setWhatsThis(u"Measures the font's glyphs again, in every master, and checks its line "
                                         u"metrics against them. The view is also checked as its tab is first shown "
                                         u"and after an undo or an edit in FontLab.")
        self.measured_label = QtGui.QLabel(measured_text(2))  # (read_font says "the single master" for a font with one)
        # (it says what Check does: grayed with it, as a caption is with its control, owner's image 292)
        ak.caption(self.measured_label, self.metrics_button)
        tab.settings.addWidget(self.measured_label)
        tab.settings.addWidget(self.metrics_button)  # (inline after what it reads, as every run button: image 262)
        tab.settings.addStretch(1)
        self.diagram = self.picture_label((320, 200))
        self.diagram.setWhatsThis(u"The font's tallest and deepest glyphs, by ink across its masters, on one "
                                  u"baseline (the one reaching highest and the one reaching lowest captioned so, with "
                                  u"how many other glyphs reach as far), with its line metrics as lines (equal ones as one line): what Windows "
                                  u"clips (past winAscent or winDescent) in red, the line's height at the left as a "
                                  u"share of the em, the suggested values dashed in the highlight color. A glyph "
                                  u"selected among the clipped ones is drawn in it too.")
        tab.layout.addWidget(self.diagram, 1)
        # The values and the checks side by side, their headings on one line, the checks as tall as the
        # values (scrolled when they are more); under both, the line spacing's choice (the buttons stand in the
        # window's bottom row, as every window's: owner's images 258 to 265). The
        # checks stood right of all of it before, as tall as the buttons and the choice too, far from the
        # values (the owner's report 128).
        body = QtGui.QGridLayout()
        self.metrics_body = body
        self.values_tree = self.tree(("Value", "Now", "Suggested"))
        self.values_tree.setWhatsThis(u"The font's line metrics now and as suggested (in bold where they differ).")
        body.addWidget(self.values_tree, 0, 0)
        row = tab.actions_row  # (the window's bottom row, this tab's part: the write at its right, before Close)
        self.write_button = QtGui.QPushButton("Write suggested values")
        self.write_button.setWhatsThis(u"Writes the suggested values that differ into the font's info: the typo, hhea, "
                                       u"and win values and <i>Use Typo Metrics</i>, for the whole font, then checks again; "
                                       u"the log lists each value, old and new, and <i>Put back old values</i> puts back the "
                                       u"values it replaced (FontLab's <i>Edit &gt; Undo</i> does not cover the font info). "
                                       u"The masters' ascender, descender, x-height, and cap height (the metrics FontLab "
                                       u"draws with) are not changed.")
        self.copy_button = QtGui.QPushButton("Copy suggested values")
        self.copy_button.setWhatsThis(u"Copies the suggested values as text.")
        self.font_info_button = QtGui.QPushButton("Open Font Info")
        self.font_info_button.setWhatsThis(u"Opens FontLab's <i>Font Info</i>, where these values are set.")
        tab.commit = self.write_button
        self.put_back_button = QtGui.QPushButton("Put back old values")
        self.put_back_button.setWhatsThis(u"Puts back the font info values <i>Write suggested values</i> replaced "
                                          u"(FontLab's <i>Edit &gt; Undo</i> does not cover the font info), into the font "
                                          u"written to only. A value that was not set before stays as written (FreeLab "
                                          u"knows no way to unset one): the log names it; clear it in <i>Font Info</i>.")
        self.put_back_button.setEnabled(False)
        row.addWidget(self.put_back_button)
        row.addWidget(self.copy_button)
        row.addWidget(self.font_info_button)
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
        row.addSpacing(12)
        self.mode_keep = QtGui.QRadioButton("Keep the font's current line spacing")
        self.mode_keep.setToolTip(self.tip(u"For an update of a font already released: documents set in it do not reflow."))
        self.mode_keep.setWhatsThis(u"For an update of a font already released: keeps its current line spacing, so "
                                    u"documents set in it do not reflow (as Google Fonts asks). The typo values stay as "
                                    u"they are when <i>Use Typo Metrics</i> is on, or else take the old win values, which "
                                    u"Windows spaced lines by; the win values grow to the ink and <i>Use Typo Metrics</i> "
                                    u"is turned on.")
        row.addWidget(self.mode_keep)  # (both choices on one line: owner's image 345)
        row.addStretch(1)
        body.addLayout(row, 1, 0, 1, 2)
        # (its heading is its list's own header, on the line of the values' header)
        self.checks_tree = self.tree((u"Checks",), icon=(STATE_SIZE, STATE_SIZE), grid=False)
        self.checks_tree.setWhatsThis(u"What Google Fonts' vertical metrics guidance asks, one line each: a warning "
                                      u"where the font differs, a check where it does as asked. Click a line about "
                                      u"glyphs to name them in the log, each a link that opens it in a <i>Glyph</i> "
                                      u"window, and to select those Windows clips among the clipped glyphs. As tall as "
                                      u"the values beside it: scroll it when there are more lines.")
        try:  # (as tall as the values: their row's height, never its own list's)
            self.checks_tree.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Ignored)
        except Exception:
            pass
        body.addWidget(self.checks_tree, 0, 1)
        body.setColumnStretch(1, 1)
        tab.layout.addLayout(body)
        tab.layout.addWidget(ak.separator())  # (a heading after a table: never read as its caption, image 234)
        row = QtGui.QHBoxLayout()
        self.clipped_label = self.heading(u"Clipped on Windows")
        row.addWidget(self.clipped_label)
        row.addStretch(1)
        self.clip_master = QtGui.QComboBox()
        self.clip_master.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.clip_master.setWhatsThis(u"The clipped glyphs of every master (each in its worst one), or of one master.")
        self.clip_master_label = self.label_for(u"Master:", self.clip_master)
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
        self.reference = QtGui.QComboBox()
        self.reference.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)  # (as wide as its widest item: image 239)
        self.reference.setWhatsThis(u"The master each other master is compared with.")
        tab.settings.addWidget(self.label_for("Compare every master with", self.reference))
        tab.settings.addWidget(self.reference)
        ak.sentence_end(tab.settings)  # (a sentence with a verb ends with a period: owner's image 271)
        self.masters_button = QtGui.QPushButton("Compare masters")
        self.masters_button.setWhatsThis(u"Compares every master's glyphs with the chosen master's again, and lists "
                                         u"the glyphs that keep them from interpolating. Nothing in the font changes.")
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
            # (each chip's own text: it names its kind, so no two chips answer alike)
            chip.setWhatsThis(u"%s: shows or hides this kind of problem in the list (the count: glyphs with it). A "
                              u"glyph left with no kind shown is hidden." % label)
            chip.setVisible(False)
            chip.connect("toggled(bool)", lambda on: self.fill_glyphs())
            chips.addWidget(chip)
            self.chips.append((kind, label, chip))
        chips.addStretch(1)
        tab.layout.addLayout(chips)
        halves = QtGui.QSplitter(QtCore.Qt.Horizontal)
        left = QtGui.QWidget()
        box = QtGui.QVBoxLayout(left)
        box.setContentsMargins(0, 0, 0, 0)  # (the list's frame hugs the handle; the picture keeps its margin: owner's image 196)
        self.glyph_tree = self.tree(("Glyph", "Masters", "Fix"), icon=(THUMB_SIZE, THUMB_SIZE))
        self.glyph_tree.setWhatsThis(u"The glyphs that keep the masters from interpolating, the worst first, with a "
                                     u"symbol per master in order: a ring for the master compared with, red where the "
                                     u"glyph cannot interpolate (a dashed square: no layer), amber where it "
                                     u"interpolates oddly (direction, start point, components, anchors), a faint dot "
                                     u"where all is well. <i>Fix</i> says whether Font Check can set its problems "
                                     u"right (ticked to start) or they need the designer. Right-click to flag a glyph.")
        box.addWidget(self.glyph_tree, 1)
        # (in the window's bottom row, as every window's: Fix this at its left, the fix of the ticked glyphs at
        # its right, before Close)
        self.fix_checked_button = QtGui.QPushButton("Fix ticked glyphs")
        self.fix_checked_button.setWhatsThis(u"Sets right, in the ticked glyphs, what needs no designer: the contours' "
                                             u"order, directions, start points, and the components' order, in every "
                                             u"master but the one compared with (which never changes). One step of "
                                             u"<i>Edit &gt; Undo</i>; the masters are compared again and the log says "
                                             u"what was fixed. Contour and node counts, node types, missing layers, and "
                                             u"anchors are left to you.")
        self.fix_this_button = QtGui.QPushButton("Fix this")
        self.fix_this_button.setWhatsThis(u"Sets right what needs no designer in the selected glyph, as <i>Fix ticked "
                                          u"glyphs</i> does.")
        tab.actions_row.addWidget(self.fix_this_button)
        tab.commit = self.fix_checked_button
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
        self.compare_master = QtGui.QComboBox()
        self.compare_master.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.compare_master.setWhatsThis(u"The master drawn beside the one compared with (those with problems say "
                                         u"how many).")
        self.beside_label = self.label_for(u"Beside it:", self.compare_master)
        row.addWidget(self.beside_label)
        row.addWidget(self.compare_master)
        row.addStretch(1)
        box.addLayout(row)
        self.show_beside(False)  # (shown with a glyph drawn: draw_comparison)
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
        package = self.ak.window_font(self, workspace)  # this window's font
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def read_font(self):
        """The current font and master; False (and said so) when no font is open."""
        package = self.current_font()
        if package is not None and self.package is not None and self.package_id(package) != self.package_id(self.package):
            self.stale = set(TABS)
        self.package = package
        self.master = package.master if package is not None else None
        if package is None:
            self.font_label.setText(self.ak.no_font_line() if hasattr(self.ak, "no_font_line")
                                    else getattr(self.ak, "NO_FONT_LINE", u"No font is open. Open one, then click Check."))
            self.show_no_masters()
            self.update_buttons()
            return False
        b = self.ak.b
        masters = self.master_names()
        if hasattr(self.ak, "font_named"):  # (one rule in every window: the masters counted only when more than one)
            self.font_label.setText(u"%s." % self.ak.font_named(package.tfn, self.master, len(masters)))
        else:
            self.font_label.setText(u"%s, master %s (%s)." % (b(package.tfn), b(self.master),
                                                              b(counted(len(masters), u"master"))))
        self.tabs.setTabEnabled(TABS.index("masters"), len(masters) > 1)
        self.tabs.setTabToolTip(TABS.index("masters"), self.tip(
            u"" if len(masters) > 1 else u"This font has one master: nothing to compare."))
        self.measured_label.setText(measured_text(len(masters)))
        if [self.reference.itemText(index) for index in range(self.reference.count)] != masters:
            self.reference.clear()
            for name in masters:
                self.reference.addItem(name)
            default = self.default_master(masters)
            if default in masters:
                self.reference.setCurrentIndex(masters.index(default))
        return True

    def show_no_masters(self):
        """With no font, nothing that names its masters (owner's images 289 and 291): the master compared with
        reads a grayed "n/a" (no_font_states grays it), not an empty box before its period; the clipped
        glyphs' Master caption and dropdown are hidden (shown again once a check lists clipped glyphs of
        several masters: fill_clip_masters, fill_clipped). Never raises."""
        try:
            if [self.reference.itemText(index) for index in range(self.reference.count)] != [NOT_AVAILABLE]:
                self.reference.clear()
                self.reference.addItem(NOT_AVAILABLE)
        except Exception:
            pass
        for widget in (self.clip_master_label, self.clip_master):
            try:
                widget.setVisible(False)
            except Exception:
                pass

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
                "highlight": palette.color(QtGui.QPalette.Highlight),
                "highlighted": palette.color(QtGui.QPalette.HighlightedText)}

    def icon(self, draw, *args):
        """A QIcon of a picture drawn (an empty one, and a warning once per window, when drawing failed:
        the list is filled all the same)."""
        QtCore, QtGui = _qt()
        try:
            icon = QtGui.QIcon(draw(*args))
            # A picture in one color of the palette, noted in it: redrawn in the new one when dark mode
            # switches (the shared module's theme_switched); the others are drawn again (theme_changed)
            colors = [arg for arg in args if hasattr(arg, "red") and hasattr(arg, "alpha")]
            if draw in (character_pixmap, arrow_pixmap, glyph_thumb) and len(colors) == 1:
                icon = self.ak.inked(icon, colors[0])
            return icon
        except Exception as exc:
            if not self.drawing_failed:
                self.drawing_failed = True
                self.log.add(u"A picture could not be drawn: %s" % self.ak.html(exc), "warning")
            return QtGui.QIcon()

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
        self.buildable = self.plan_font = None
        self.asked = set()
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): checked again.")
        self.check(self.current_key())

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (the shared
        module's fonts_tick, from a timer): the views checked anew as at opening, the one shown now and
        the others when shown, or, with no font, emptied, the top line saying the window takes the next
        font opened. Nothing escapes (a timer's handler)."""
        try:
            self.stale = set(TABS)
            self.buildable = self.plan_font = None
            self.asked = set()
            if self.busy:
                return  # (the check under way reads the font as it goes on: the shared module asks again)
            had = self.package is not None
            if not self.read_font():
                self.show_fontless()
                return
            if not had:
                self.widen_for_font()  # (opened without a font, at the others' size: owner's image 279)
            self.check(self.current_key())
        except Exception as exc:
            try:
                self.log.add(u"The font could not be read again: %s" % self.ak.html(exc), "error")
            except Exception:
                pass

    def show_fontless(self):
        """Every view emptied: what was listed belonged to a font that is closed. The lists, pictures,
        and lines go, and what acts on them is grayed (update_buttons) until a font is read."""
        self.clear_coverage()
        self.clear_metrics()
        self.clear_masters()
        self.update_buttons()

    def emptied(self, steps):
        """Each step of emptying a view run, the lists' handlers held off; one that fails leaves the others."""
        was, self.filling = self.filling, True
        try:
            for step in steps:
                try:
                    step()
                except Exception:
                    pass
        finally:
            self.filling = was

    def clear_coverage(self):
        """The Coverage view as before any check: its findings let go, its lists and lines empty (a font
        closed, or a check stopped: coverage_stopped)."""
        self.scripts, self.results, self.other_results, self.set_results = [], [], [], []
        self.rows, self.own_rows, self.checked, self.selection = [], [], set(), None
        self.has_coverage, self.font_found, self.script_filter = False, None, None
        self.groups_of, self.tip_cache = {}, {}
        self.generation += 1
        self.coverage.findings = []
        self.emptied((
            lambda: self.script_tree.clear(), lambda: self.script_tree.setVisible(False),
            lambda: self.show_absent.setVisible(False),
            lambda: [view.tree.clear() for key in self.views for view in self.views[key].values()],
            lambda: self.add_tree.clear(), lambda: self.own_tree.clear(),
            lambda: self.tab_names["left"].set_text(0, value_title(None)),
            lambda: self.tab_names["left"].set_text(1, selection_title(None)),
            lambda: self.left_tabs.setTabEnabled(1, False), lambda: self.show_left("value"),
            lambda: [self.tab_names["right"].set_text(index, label) for index, (_, label) in enumerate(RIGHT_TABS)],
            lambda: self.gain_label.setText(u""), lambda: self.languages_note.setVisible(False),
            lambda: self.coverage.status.setText(u"")))
        was, self.filling = self.filling, True
        try:
            for key in sorted(self.views, key=lambda one: one == self.right_tab):  # (the tab shown last: its page)
                for view in self.views[key].values():
                    view.rows, view.labels, view.unfilled, view.signature = [], [], {}, None
                self.activate(key, "full")
        finally:
            self.filling = was

    def clear_metrics(self):
        """The Vertical metrics view as before any check (a font closed, or a check stopped)."""
        self.metric_values, self.extents_found, self.suggestions, self.notes = None, [], [], []
        self.check_rows, self.clipped = [], []
        self.metrics.findings = []
        self.emptied((lambda: self.values_tree.clear(), lambda: self.checks_tree.clear(),
                      lambda: self.clipped_list.clear(), lambda: self.diagram.clear(),
                      lambda: self.metrics.status.setText(u"")))

    def clear_masters(self):
        """The Masters view as before any comparison (a font closed, or a comparison stopped)."""
        self.problems, self.glyph_names, self.compare_masters = [], [], []
        self.fixable_names = set()
        self.masters.findings = []
        self.emptied((lambda: self.glyph_tree.clear(), lambda: self.comparison.clear(),
                      lambda: self.problem_label.setText(u""), lambda: self.compare_master.clear(),
                      lambda: self.show_beside(False),
                      lambda: [chip.setVisible(False) for _, _, chip in self.chips],
                      lambda: self.masters.status.setText(u"")))

    def show_tab_parts(self):
        """The shown tab's own parts, the others' hidden: its status line in the header (the others kept
        hidden as they are written, by the property that keeps a top line hidden while the busy bar
        stands in for it: ak.status_label), and its buttons in the bottom row. Never raises."""
        prop = getattr(self.ak, "BUSY_LINE_PROP", "freelabBusyLine")
        try:
            current = self.current_key()
        except Exception:
            current = TABS[0]
        for key in sorted(TABS, key=lambda k: k == current):  # (the others hidden first: owner's image 284)
            try:
                tab, mine = self.tab_of(key), key == current
                tab.status.setProperty(prop, None if mine else True)
                text = u"%s" % (_prop(tab.status, "text") or u"")
                tab.status.setHidden(not mine or not text.strip() or (key == "coverage" and self.busy))
                tab.actions.setVisible(mine)
                if tab.commit is not None:
                    tab.commit.setVisible(mine)
            except Exception:
                pass

    def level_settings(self):
        """The three tabs' settings rows as tall as one another (level_rows: what is under them never moves
        as a tab is shown), measured again at each switch, after the window's styles and a dark mode switch."""
        level_rows([tab.settings_box for tab in (getattr(self, key, None) for key in TABS)
                    if getattr(tab, "settings_box", None) is not None])

    def switch_page(self, index):
        QtCore, QtGui = _qt()
        self.level_settings()  # (before the page shows: owner's images 285 and 286)
        self.pages.setCurrentIndex(index)
        self.show_tab_parts()
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
        # (no count on the buttons: "Build 2 glyphs" read as two rows for one row selected, a capital and its
        # small letter; the count is in their tooltips, report 132)
        self.diacritics_button.setText(build_caption(len(buildable)))
        self.diacritics_button.setToolTip(self.tip(
            build_tip(buildable, self.in_list_font) if buildable else u"Tick glyphs or select a row first."
            if not chosen else u"<i>Glyph Compose</i> cannot build %s from the font's glyphs." % (
                u"this glyph" if len(chosen) == 1 else u"any of these glyphs"), rich=True))
        targets = self.check_targets() if self.package is not None else {}
        listed = self.shown_rows()
        can = any(item in (self.buildable or set()) for row in listed for item in row.items)
        idle = {"all": u"Every glyph listed is ticked.",
                "none": u"No glyph is ticked.",
                "buildable": u"Only what <i>Glyph Compose</i> can build is ticked." if can
                else u"<i>Glyph Compose</i> can build none of the glyphs listed."}
        for key, button in self.check_buttons.items():
            # (nothing listed: all three grayed, Check none too, though glyphs of another tab or check stay
            # checked: owner's image 206)
            on = bool(listed) and targets.get(key) is not None
            if not listed:
                idle[key] = u"No glyph is listed."
            ak.enable(button, on)
            button.setToolTip(self.tip(u"" if on else idle[key], rich=True))
        ak.enable(self.copy_chars_button, bool(chosen))
        self.copy_chars_button.setText(copy_caption(len(chosen)))
        self.copy_chars_button.setToolTip(self.tip(copy_tip(chosen, self.in_list_font) if chosen
                                                   else u"Tick glyphs or select a row first.", rich=True))
        ak.enable(self.copy_button, bool(self.suggestions))
        writes = metric_writes(self.suggestions) if self.package is not None else []
        ak.enable(self.write_button, bool(writes) and not self.busy)
        self.write_button.setText(u"Write %s" % counted(len(writes), u"suggested value") if writes
                                  else u"Write suggested values")
        self.write_button.setToolTip(self.tip(u"" if writes else u"The font's values are as suggested."
                                              if self.suggestions else u"Check the vertical metrics first."))
        fixing = self.checked_fix_glyphs() if self.package is not None else []
        ak.enable(self.fix_checked_button, bool(fixing) and not self.busy)
        self.fix_checked_button.setText(u"Fix %s" % counted(len(fixing), u"ticked glyph") if fixing
                                        else u"Fix ticked glyphs")
        self.fix_checked_button.setToolTip(self.tip(
            u"" if fixing else u"Tick glyphs Font Check can fix (their row says so)."
            if self.fixable_names else u"No glyph listed has a problem Font Check can fix."))
        name = self.selected_glyph() if self.package is not None else None
        ak.enable(self.fix_this_button, name in self.fixable_names and not self.busy)
        self.fix_this_button.setToolTip(self.tip(
            u"" if name in self.fixable_names else u"Select a glyph first." if name is None
            else u"This glyph's problems need the designer."))
        ak.enable(self.font_info_button, self.package is not None)
        ak.enable(self.glyph_window_button, self.package is not None and bool(self.glyph_window_text()))
        # (it may name a set of any script; rich: the window's name in italics)
        self.glyph_window_button.setToolTip(self.tip(self.glyph_window_tip(), True, rich=True))
        # The user's own sets: saved once there are characters and a name, removed when a saved one is selected
        pasted = bool(pasted_characters(self.pasted_text))
        named = bool((u"%s" % (_prop(self.name_field, "text") or u"")).strip())
        ak.enable(self.save_set_button, pasted and named)
        self.save_set_button.setToolTip(self.tip(
            u"" if pasted and named else u"Paste text or characters first." if not pasted else u"Give the set a name first."))
        ak.enable(self.remove_set_button, self.selected_custom() is not None)
        self.remove_set_button.setToolTip(self.tip(
            u"" if self.selected_custom() is not None else u"Select one of your saved sets first."))
        self.update_controls()

    def update_controls(self):
        """The owner's audit: what cannot act yet is grayed (the buttons above say why in their
        tooltips). Before a check has listed anything (no font open, or the first check under way),
        the search, the level, the order, the tabs of the lists, and the fields of a set of one's own
        have nothing to act on (the scripts' list and its check box are hidden until then: fill_scripts);
        the strategy of the vertical metrics acts once there are values to suggest; a choice of masters
        acts once there is more than one to choose (the masters to compare with, once compared)."""
        ak = self.ak
        ready = bool(self.has_coverage)
        for widget in (self.search, self.level_filter, self.sort_box, self.right_tabs, self.left_tabs,
                       self.paste_field, self.name_field):
            ak.enable(widget, ready)
        measured = self.metric_values is not None
        ak.enable(self.mode_share, measured)
        ak.enable(self.mode_keep, measured)
        ak.enable(self.share, measured and self.mode() == "share")
        for box, least in ((self.clip_master, 2), (self.compare_master, 1), (self.reference, 2)):
            try:
                count = int(_prop(box, "count") or 0)
            except Exception:
                count = 0
            ak.enable(box, count >= least)

    def glyph_window_tip(self):
        """What Show in Glyph window opens now, and what a double-click does instead: rich text (the window's
        name in italics, as in the button's first help), a line per sentence."""
        if self.package is None or self.current_key() != "coverage":
            return u""
        chosen = self.chosen_characters()
        checked = self.checked_listed()
        if checked:
            what = u"Opens the %s of this tab in a <i>Glyph</i> window." % (
                u"1 ticked glyph" if len(checked) == 1 else u"%s ticked glyphs" % grouped(len(checked)))
        elif chosen:
            what = u"Opens the selected row's %s in a <i>Glyph</i> window (no glyph is ticked)." % (
                u"glyph" if len(chosen) == 1 else u"glyphs")
        elif self.selection is not None and self.selection_glyph_text():
            what = u"Opens the glyphs %s misses in a <i>Glyph</i> window (no glyph is ticked, no row selected)." % (
                self.ak.html(self.selection.name))
        else:
            return u"Tick glyphs or select a row first. A double-click on a row opens that row's glyph alone."
        return what + u"<br>A double-click on a row opens that row's glyph alone, whatever is ticked."

    def tip(self, text, names=False, rich=False):
        """A tooltip's text for Qt: rich text, which Qt wraps (plain text ran on one line, thousands of
        pixels wide for a row naming dozens of languages), in a width that follows the window's when its
        longest line needs one. names: set in FreeLang, which has every name, autonym, and
        orthography character the lists show (the interface font drew boxes for some scripts). rich:
        the text is rich text already. Every tooltip of this window goes through here."""
        text = sentence(text) if not rich else u"%s" % (text or u"")
        if not text:
            return u""
        # Its width follows the window's (tip_limit), and its lines are estimated, not measured in a font
        # (line_width: Qt's search for the scripts the dialog's font lacks froze the window for seconds)
        return tip_html(text, tip_width(text, self.tip_limit(), None, rich), self.list_family if names else None, rich)

    def tip_limit(self):
        """The width tooltips may take now: about half the window's (tip_limit)."""
        try:
            return tip_limit(_prop(self.dialog, "width"))
        except Exception:
            return TIP_WIDTH

    def start(self, tab):
        """A view about to be checked; False when it cannot be (busy, no font)."""
        if self.busy or not self.read_font():
            return False
        tab.findings = []
        tab.status.setText(u"")
        return True

    def item(self, texts, data, tip=u"", names=False):
        """A list's row; its tooltip (plain text, a sentence per line) goes through tip(), names: in the
        languages' font."""
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        item.setData(0, QtCore.Qt.UserRole, data)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if callable(tip):
            return item  # (a row of a list at the right: its tooltip is made when it is asked for, show_tip)
        if tip:
            tip = self.tip(tip, names)
            for column in range(len(texts)):
                item.setToolTip(column, tip)
        return item

    # The rows of the lists at the right (some 2,600 languages, 270 sets, the families) have no tooltip
    # set on them: each one's text was made, measured in the dialog's font (which sent Qt looking for a
    # font for every script named), and set twice as the list was filled, for the few that are ever
    # read. It is made when Qt asks for the tooltip of the row under the mouse (watch_presses' filter).

    def later_tip(self, tab, row):
        """A row's tooltip as something to call when it is wanted (item() sets no tooltip then)."""
        return lambda: self.entry_tip(tab, row)

    def entry_tip(self, tab, row):
        """The tooltip's text of a row of a right tab: a language's or a set's coverage, a family, or
        a language that cannot be checked."""
        if isinstance(row, Coverage):
            language = row.language
            path = self.families.path(language.iso) if self.families is not None and language.kind != "set" else ()
            also = [] if language.kind == "set" else [
                group for group in self.groups_of.get(language.iso, ()) if group != script_group(language.script)]
            fonts = self.coverage_gaps.fonts_for(language.iso) if language.kind == "set" else []
            return coverage_tip(row, path, isinstance(language, ScriptSet)
                                and language.name in self.known_scripts.not_covered, also, fonts)
        if isinstance(row, Uncovered):
            return uncovered_tip(row, self.known_scripts.of_languages.get(row.iso, ()))
        if isinstance(row, FamilyNode):
            return family_tip(row)
        return u""

    def right_tip(self, tab, item):
        """The tooltip (rich text, as tip() makes it) of the row Qt hands over, used here and now;
        nothing for a heading or a row of an earlier filling (a heading's is set on it)."""
        if item is None or tab not in self.right_rows:
            return u""
        data = self.data_of(item, None)
        if data is None or (u"%s" % data)[:1] == u"#":
            return u""
        try:
            index = int(data)
        except (TypeError, ValueError):
            return u""
        rows = self.right_rows[tab]
        if not 0 <= index < len(rows):
            return u""
        # Made once per row, check, and width (a search's other name changes it): Qt asks again each time
        # the mouse rests on the row
        row = rows[index]
        key = (tab, id(row), getattr(row, "found_by", None), self.tip_limit())
        if key not in self.tip_cache:
            if len(self.tip_cache) > 2000:
                self.tip_cache.clear()
            self.tip_cache[key] = self.tip(self.entry_tip(tab, row), True)
        return self.tip_cache[key]

    def show_tip(self, tree, event):
        """Qt asks for a tooltip over a list at the right: the row's is made now and shown; False
        when the row has none to make (Qt then shows what is set on it, a heading's)."""
        tab = next((key for key, one in self.right_trees.items() if one is tree), None)
        if tab is None:
            return False
        QtCore, QtGui = _qt()
        try:
            where, pos = event.globalPos(), event.pos()
        except Exception:  # (an event PythonQt hands over without its positions)
            where = QtGui.QCursor.pos()
            pos = tree.viewport().mapFromGlobal(where)
        item = tree.itemAt(pos)
        text = self.right_tip(tab, item)
        if not text:
            return False
        try:  # (over the row alone: the tooltip goes as the mouse leaves it, as a row's own does)
            QtGui.QToolTip.showText(where, text, tree.viewport(), tree.visualItemRect(item))
        except Exception:
            QtGui.QToolTip.showText(where, text)
        return True

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
    def choice(box, choices):
        """The entry of choices a combo box shows (the first when it shows none)."""
        try:
            index = int(_prop(box, "currentIndex"))
        except Exception:
            index = 0
        return choices[index if 0 <= index < len(choices) else 0]

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
        last takes the rest, its text elided. Measured by the shared fit_rows: every row, the same in
        either theme (the "+N" column grew 6 pixels over a dark, light, dark round trip, live)."""
        self.ak.fit_rows(tree, range(len(widths)), most=list(widths))

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
        """The coverage checked, in four steps (the data files read, the font read, the languages
        checked, the lists filled): the window's top row says which one runs, and the window repaints
        between two (set_busy, run_steps). It opened on empty lists and zero counts for seconds. A stop
        leaves the view as if not checked (coverage_stopped)."""
        tab = self.coverage
        if not self.start(tab):
            if not self.busy:
                self.set_busy(False)  # (no font: the lists, empty, not the line that says what is read)
            return
        state = {"started": time.time()}  # (the log says how long the check took)
        self.set_busy(True, BUSY_STEPS[0])
        self.defer(lambda: self.run_steps([lambda: self.coverage_data(state), lambda: self.coverage_font(state),
                                           lambda: self.coverage_check(state), lambda: self.coverage_list(state)]))

    def coverage_data(self, state):
        """The first step: the data files (read once per FontLab session: session_cache)."""
        languages = load_languages()
        try:
            self.families = load_families()
        except Exception as exc:  # (the languages are listed all the same, without families or other names)
            self.families = None
            self.log.add(u"The languages' families and other names could not be read: %s" % self.ak.html(exc), "warning")
        name_languages(languages, self.families)
        try:
            self.known_scripts = load_known_scripts()
        except Exception:
            self.known_scripts = KnownScripts()
        try:  # (optional: without it, nothing is said of the gaps and the fonts to consider)
            self.coverage_gaps = load_coverage_gaps()
        except Exception:
            self.coverage_gaps = CoverageGaps()
        try:
            state["sets"] = self.custom_languages() + list(load_character_sets())
        except Exception as exc:  # (the languages are listed all the same)
            state["sets"] = self.custom_languages()
            self.log.add(u"The character sets could not be read: %s" % self.ak.html(exc), "warning")
        state["languages"] = languages
        return BUSY_STEPS[1]

    def coverage_font(self, state):
        """The second step: the font's code points, and the languages the settings keep."""
        state["font"] = self.font_found = self.font_characters()
        state["statuses"] = self.choice(self.status_filter, STATUS_FILTERS)[2]
        if state["statuses"] == HIGH_VALUE and not high_value_orthographies():
            self.log.add(u"The list of high-value languages (%s) could not be read: <i>High-value only</i> keeps no "
                         u"language. Reinstall FreeLab." % HIGH_VALUE_FILE, "warning")
        # (the languages inferred from a text: checked with the others, or set aside for a search to find)
        state["languages"], state["aside"] = chosen_languages(state["languages"], bool(self.inferred_box.checked))
        return checking_text(len(set(one.iso for one in state["languages"])))

    def coverage_check(self, state):
        """The third step: each language and character set checked against the font."""
        font, statuses, languages = state["font"], state["statuses"], state["languages"]
        scripts = coverage(languages, font, self.nearly.value, statuses is None, statuses)
        others = left_out(languages, font, self.nearly.value, statuses, state["aside"])
        sets = [check_entry(one, font, self.nearly.value) for one in state["sets"]]
        self.scripts = scripts
        self.results = [r for s in scripts for r in s.results]
        self.other_results, self.set_results = others, sets
        self.generation += 1  # (the lists at the right are filled anew from these)
        self.tip_cache = {}
        # The scripts' groups each language is listed under (Pontic Greek: Cyrillic and Greek), for its
        # tooltip to name the others
        groups_of = {}
        for one in state["languages"]:
            found = groups_of.setdefault(one.iso, [])
            if script_group(one.script) not in found:
                found.append(script_group(one.script))
        self.groups_of = groups_of
        self.coverage.findings = self.results
        self.buildable = self.plan_font = None
        self.asked = set()
        self.checked = set()
        self.pictures = {}  # (drawn again: the palette may have changed)
        if self.script_filter not in [s.script for s in scripts if s.present]:
            self.script_filter = None
        self.buildable_set()  # (Glyph Compose asked once: the rows' tooltips say what it can build)
        try:  # the spaces the font lacks that the high-value list does not show (space_rows lists the others)
            has = lambda code: code in font.codes
            listed = [code_points(row.items[0])[0] for row in space_rows(self.results, has, space_conventions())]
            self.say_spaces(spaces_note(has, listed))
        except Exception:
            pass
        self.say_declared(font.codes)
        self.say_kerning()
        return BUSY_STEPS[3]

    def say_kerning(self):
        """Once a window, after its first check: where the kerning is checked, a link that opens it (owner's
        image 391: Font Check checks the glyphs and the font info, not the kerning)."""
        if getattr(self, "kerning_said", False):
            return
        self.kerning_said = True
        link = getattr(self.ak, "tool_link", None)
        tool = link(u"Kerning Check") if link is not None else u"<i>Kerning Check</i>"
        self.log.add(u"To check the kerning (pairs that collide, entries that do nothing, masters that differ), open %s."
                     % tool)

    def coverage_now(self, codes):
        """{key: (declared, would declare)} of the font info's coverage fields that differ from the glyphs'
        code points (declared_coverage), or None where it cannot be read."""
        try:
            module = self.ak.font_info()
            info = self.package.fgPackage.info
            if module is None:
                return None
            ranges = [int(bit) for bit in (info.openTypeOS2UnicodeRanges or [])]
            pages = [int(bit) for bit in (info.openTypeOS2CodePageRanges or [])]
            return declared_coverage(module, ranges, pages, codes)
        except Exception:
            return None

    def say_declared(self, codes):
        """The line on the font info's coverage when it differs from the glyphs, logged once a font and again
        only when it changes (as say_spaces)."""
        differences = self.coverage_now(codes)
        try:
            font_key = self.package.fgPackage.path
        except Exception:
            font_key = None
        note = declared_note(self.ak.font_info(), differences, self.ak.html) if differences else u""
        try:
            self.declare_button.setEnabled(bool(differences))
        except Exception:
            pass
        said = (font_key, note)
        if note and said != getattr(self, "declared_said", None):
            self.log.add(note, "warning")
        self.declared_said = said

    def declare_coverage(self):
        """The font info's Unicode ranges and code pages set to what the glyphs cover (declared_coverage),
        one step of FontLab's History: unlike the vertical metrics, Edit > Undo takes them back (they are the
        font's coding, which the step records: live 2026-11-18)."""
        if self.busy or self.package is None or not self.same_font():
            return
        codes = set(code for _name, glyph_codes_ in self.glyphs() for code in glyph_codes_)
        differences = self.coverage_now(codes)
        if not differences:
            self.log.add(u"The font info declares what the font covers already: nothing to write.")
            return
        module = self.ak.font_info()
        if not self.begin_info_write(self.package, u"FreeLab Font Check: coverage declared"):
            return
        info = self.package.fgPackage.info
        fields = dict((key, attribute) for key, attribute, _label in COVERAGE_KEYS)
        done, failed = [], []
        for key in sorted(differences):
            now, new = differences[key]
            try:
                setattr(info, fields[key], list(new))
                kept = sorted(int(bit) for bit in (getattr(info, fields[key]) or []))
            except Exception as exc:
                failed.append(u"%s (%s)" % (key, exc))
                continue
            if kept != list(new):
                failed.append(u"%s (FontLab kept %s)" % (key, kept))
                continue
            done.append(key)
        status = self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Font Check: coverage declared",
                                        added=False)
        if done:
            self.log.add(u"Declared what the font covers in the font info, where it differed (%s).%s" % (
                self.ak.html(coverage_differences(module, dict((key, differences[key]) for key in done))),
                status.undo(u" <i>Edit &gt; Undo</i> takes it back.")), "done")
        status.report(self.log)
        if failed:
            self.log.add(u"Not written: %s." % self.ak.html(u"; ".join(failed)), "error")
        self.say_declared(codes)

    def say_spaces(self, note):
        """The line on the spaces the font lacks, logged once a font and again only when it changes,
        not at every check (the owner saw it repeated)."""
        try:
            font_key = self.package.fgPackage.path  # (a new wrapper at each read: its file names the font)
        except Exception:
            font_key = None
        said = (font_key, note)
        if note and said != getattr(self, "spaces_said", None):
            # (amber: something the font lacks, owner's image 242; Glyph Compose a link of its own, which opens
            # it on these spaces, never tool_links' plain one: owner's image 313)
            self.log.add(note, "warning")
        self.spaces_said = said

    def tool_links(self, text):
        """Rich text whose FreeLab tools named in italics (<i>Glyph Compose</i>) are links the log opens
        them by, in this window's place (ak.tool_link: owner's image 220). Never raises."""
        try:
            for title in getattr(self.ak, "FONT_TOOLS", ()):
                text = text.replace(u"<i>%s</i>" % self.ak.html(title), self.ak.tool_link(title))
        except Exception:
            pass
        return text

    def coverage_list(self, state):
        """The last step: the lists filled, the top line written, and the lists shown again."""
        tab, b = self.coverage, self.ak.b
        scripts, sets, aside = self.scripts, self.set_results, state["aside"]
        self.has_coverage = True  # (the lists' controls act from now on: update_controls)
        try:  # (the lists' page first: their columns are sized to it; of it nothing is painted before the end,
            # while the bar above it, which is painted at each call, moves with the rows made)
            self.coverage_stack.setCurrentIndex(1)
        except Exception:
            pass
        self.refill_coverage(lambda part: self.progress_to(len(BUSY_SHARES) - 1, part))
        present = [s for s in scripts if s.present]
        covered = sum(s.count("covered") for s in present)
        nearly = sum(s.count("nearly") for s in present)
        text = u"%s covered and %s within reach (missing at most %s), of the languages of %s the font has." % (
            b(counted(covered, u"language")), b(nearly), b(counted(self.nearly.value, u"base character")),
            b(counted(len(present), u"script")))
        composed = sum(1 for s in present for r in s.results if r.composed and r.level != "missed")
        if composed:
            text += u" %s count%s letters its anchors compose." % (b(counted(composed, u"language")),
                                                                    u"s" if composed == 1 else u"")
        text += inferred_sentence(sum(1 for s in present for r in s.results
                                      if r.level in ("covered", "nearly") and r.language.evidence in UNDECLARED),
                                  len(aside), b)
        listed, of_unicode = set_tally(sets)[:2]  # (the one count Proof gives too)
        text += sets_sentence(sets, b)
        tab.status.setText(text)
        self.set_busy(False)  # (the lists made: a stop asked now comes too late, and the check stands)
        self.log.add(checked_sentence(len(set(one.iso for one in state["languages"])), len(listed), len(of_unicode),
                                      time.time() - state.get("started", time.time()), b), "done")
        self.checked_now("coverage")

    def custom_languages(self):
        """The user's own sets as Languages of kind "set": the pasted characters first (when there
        are some), then the saved ones."""
        found = []
        if pasted_characters(self.pasted_text):
            found.append(custom_set(PASTED_KEY, PASTED_NAME, self.pasted_text))
        for name, text in self.custom_sets:
            one = custom_set(custom_key(name), name, text)
            if one.base:
                found.append(one)
        return found

    def custom_path(self):
        return os.path.join(self.ak.state_dir(), CUSTOM_SETS_FILE)

    def recheck_custom(self, select=None):
        """The user's own sets checked again against the font as it was last read, and the Character
        sets tab listed again; select: the key of the one to select, its missing glyphs at the left."""
        if self.font_found is None or self.busy:
            return
        own = [check_language(one, self.font_found, self.nearly.value) for one in self.custom_languages()]
        self.set_results = own + [r for r in self.set_results if r.language.script != CUSTOM_GROUP]
        self.generation += 1  # (the Character sets tab is filled anew)
        chosen = next((r for r in own if r.language.iso == select), None)
        if chosen is not None:
            self.closed["sets"].discard(CUSTOM_GROUP)
            self.select(selection_of(chosen))
        self.fill_right()
        self.update_buttons()

    def pasted_changed(self):
        """Text pasted or typed in the field of the Character sets tab: checked as a set of the
        user's own, and selected."""
        try:
            self.pasted_text = u"%s" % (_prop(self.paste_field, "text") or u"")
            self.recheck_custom(PASTED_KEY)
        except Exception:
            pass  # a signal's handler must not raise

    def save_set(self):
        """The pasted characters saved under the name given, in FreeLab's settings folder."""
        try:
            name = (u"%s" % (_prop(self.name_field, "text") or u"")).strip()
            if not name or not pasted_characters(self.pasted_text):
                return
            self.custom_sets = with_custom_set(self.custom_sets, name, self.pasted_text)
            save_custom_sets(self.custom_path(), self.custom_sets)
            self.log.add(u"Saved the set %s (%s) in FreeLab's settings folder." % (
                self.in_list_font(self.ak.b(self.ak.html(name))),
                self.ak.b(counted(len(pasted_characters(self.pasted_text)), u"character"))))
            self.recheck_custom(custom_key(name))
        except Exception as exc:
            self.log.add(u"The set could not be saved: %s" % self.ak.html(exc), "error")

    def selected_custom(self):
        """The name of the saved set of the user's own that is selected, or None."""
        key = self.selection.key if self.selection is not None else None
        if key and len(key) > 1 and (u"%s" % key[1]).startswith(u"custom:"):
            return (u"%s" % key[1])[len(u"custom:"):]
        return None

    def remove_set(self):
        """The selected saved set of the user's own removed from the saved ones."""
        try:
            name = self.selected_custom()
            if name is None:
                return
            self.custom_sets = [(held, text) for held, text in self.custom_sets if held != name]
            save_custom_sets(self.custom_path(), self.custom_sets)
            self.log.add(u"Removed the set %s from the saved ones." % self.in_list_font(self.ak.b(self.ak.html(name))))
            self.recheck_custom()
        except Exception as exc:
            self.log.add(u"The set could not be removed: %s" % self.ak.html(exc), "error")

    def shown_scripts(self):
        """The scripts listed: those the font has, and the others when asked."""
        return [s for s in self.scripts if s.present or self.show_absent.checked]

    def filtered_scripts(self):
        """The scripts whose languages are shown: the one clicked, or all those listed."""
        return [s for s in self.shown_scripts() if self.script_filter is None or s.script == self.script_filter]

    def refill_coverage(self, progress=None):
        """The Coverage view's lists filled. progress: told how far the filling is, 0 to 1 (a check's
        bar: the list at the right, which has the most rows, takes most of it)."""
        progress = progress or (lambda part: None)
        self.fill_scripts()
        progress(LIST_PARTS[0])
        self.fill_right(False, lambda part: progress(LIST_PARTS[0] + part * (LIST_PARTS[1] - LIST_PARTS[0])))
        # (first: it settles what stays selected, for the tabs of characters)
        progress(LIST_PARTS[1])
        self.fill_add()
        progress(LIST_PARTS[2])
        self.update_gain()
        self.update_buttons()

    def absent_toggled(self):
        """The scripts the font has none of shown or hidden: the lists filled again (the top row's bar
        meanwhile, when it makes many rows: listing). Never raises."""
        try:
            if self.filling or self.busy:
                return
            if not self.listing(self.refill_coverage, listing_text(self.right_tab, self.script_filter)):
                self.fill_add()  # (stopped in the list at the right: the glyphs' lists follow what it shows so far)
                self.update_gain()
                self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def languages_changed(self):
        """The search, the level, or the order changed: the tab shown at the right listed again (the top
        row's bar meanwhile, when it makes many rows: listing)."""
        if self.filling or self.busy:
            return
        self.listing(lambda progress: self.fill_right(progress=progress), listing_text(self.right_tab, self.script_filter))
        self.update_buttons()

    def status_changed(self):
        """Another choice of Display: the coverage is checked again with it."""
        if self.filling or self.package is None:
            return
        self.check_coverage()

    def fill_scripts(self):
        QtCore, QtGui = _qt()
        tree, colors = self.script_tree, self.colors()
        shown = self.shown_scripts()
        absent = [s for s in self.scripts if not s.present]
        self.filling = True
        try:
            tree.clear()
            counts = level_counts([r for s in shown for r in s.results])
            all_row = self.item((u"All scripts", u"", coverage_text(counts)), u"", counts_tip(u"All scripts", counts))
            all_row.setIcon(1, self.icon(bar_pixmap, counts, colors))
            tree.addTopLevelItem(all_row)
            selected = all_row
            for s in shown:
                counts = level_counts(s.results)
                item = self.item((s.script, u"", script_text(s)), s.script, counts_tip(s.script, counts))
                item.setIcon(1, self.icon(bar_pixmap, counts, colors))
                tree.addTopLevelItem(item)
                if s.script == self.script_filter:
                    selected = item
            tree.setCurrentItem(selected)
            self.fit_columns(tree, (220, BAR_SIZE[0] + 12))
            # Six rows at most, as tall as that in a window with room; a short window (a 480-pixel screen) may
            # take it down to two rows, scrolled, rather than be held taller than the screen by a fixed height
            full = self.rows_height(tree, min(len(shown) + 1, 6))
            tree.setMaximumHeight(full)
            tree.setMinimumHeight(min(full, self.rows_height(tree, 2)))
            tree.setVisible(True)  # (hidden until a check has something to list)
        finally:
            self.filling = False
        if absent:
            self.show_absent.setText(absent_caption(len(absent)))
        self.show_absent.setVisible(bool(absent))

    def script_selected(self):
        """A script's row clicked (or All scripts): the lists follow it. Each tab keeps every script's list
        and the chosen script's apart (VIEW_MODES), so going back to All scripts makes no row; a list made
        anew that makes many rows shows the top row's bar meanwhile (listing)."""
        if self.filling or self.busy:
            return
        item = self.selected_item(self.script_tree)
        if item is None:
            return
        key = u"%s" % self.data_of(item, u"")
        self.script_filter = key or None

        def work(progress):
            self.fill_right(False, progress=(lambda part: progress(part * 0.9)) if progress is not None else None)
            self.fill_add()
            self.update_gain()

        if not self.listing(work, listing_text(self.right_tab, key)):
            # (stopped in the list at the right: the glyphs' lists follow what it shows so far)
            self.fill_add()
            self.update_gain()
        self.update_buttons()

    def listing_rows(self):
        """How many rows the list at the right would make now: 0 when the list to show is kept as it was
        (its signature unchanged), else the rows of what it lists (the languages of the scripts shown, the
        sets, or the families at the top), an estimate for the progress bar."""
        try:
            tab, text = self.right_tab, self.searched()
            view = self.views[tab][self.view_mode(tab, text)]
            shown = [s.script for s in self.filtered_scripts()]
            signature = self.view_signature(tab, text, self.choice(self.level_filter, LANGUAGE_FILTERS)[0],
                                            self.choice(self.sort_box, SORTS)[0], shown)
            if view.signature == signature:
                return 0
            if tab == "sets":
                return len(self.set_results)
            results = [r for s in self.scripts if s.script in set(shown) for r in s.results]
            if tab == "families":  # (the families at the top: the others' rows wait until opened)
                path = self.families.path if self.families is not None else (lambda iso: ())
                return len(set((path(r.language.iso) or (UNCLASSIFIED,))[0] for r in results))
            return len(results)
        except Exception:
            return 0

    def listing(self, work, what):
        """work(progress) done, with the window's top-row bar (what: the step's name) while it makes many
        rows in the list at the right (LISTING_BUSY_ROWS: a few make none of it flicker), at once
        otherwise (progress None). The bar was the Coverage view's own (owner's images 174 and 180); the
        tools menu, the arrows, Close, and Esc stop it now: the list keeps the rows made so far, and is made
        anew the next time it is shown (fill_right). False when stopped."""
        if self.listing_rows() < LISTING_BUSY_ROWS:
            work(None)
            return True
        ak = self.ak
        self.busy = True
        ak.busy_start(self, what)
        try:
            work(lambda part: ak.busy_progress(self, None, part))
        except ak.Stopped:
            self.log.add(u"Listing stopped: the list shows the rows made so far.", "warning")
            return False
        finally:
            self.busy = False
            ak.busy_end(self)
        return True

    def picture_font(self):
        """The font the missing characters are drawn in: the dialog's, in FreeLang once it is
        registered (it has every orthography's characters but the ideographs, Hangul syllables,
        cuneiform signs, and hieroglyphs; the interface font drew boxes for Canadian syllabics and
        others). What it lacks, Qt takes from the system's fonts, as before."""
        QtCore, QtGui = _qt()
        font = QtGui.QFont(_prop(self.dialog, "font"))
        if self.list_family:
            try:
                font.setFamily(self.list_family)
            except Exception:
                pass
        return font

    def fill_characters(self, tree, rows):
        """A tab of characters filled with its rows: a check box, a picture, the name and code points,
        +N, and the languages; its checks from the characters checked (the two tabs share them)."""
        QtCore, QtGui = _qt()
        colors = self.colors()
        font = self.picture_font()
        buildable = self.buildable or set()
        self.filling = True
        self.ak.quiet_list(tree, True)
        try:
            tree.clear()
            bold = self.bold(tree)
            quiet = QtGui.QBrush(faded(colors["text"], QUIET_ALPHA))
            for index, row in enumerate(rows):
                plus = u"+%d" % len(row.completing)
                item = self.item((u"", row_label(row), plus,
                                  row_languages_text(row)), index,
                                 row_tip(row, any(i in buildable for i in row.items),
                                         all(i in (self.generated or ()) for i in row.items if i in buildable)),
                                 True)
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
            self.ak.quiet_list(tree, False)
            self.filling = False

    def fill_add(self):
        """The high-value list (what the languages within reach of the scripts shown miss, ranked), its
        tab's caption with the count of its rows, then the selection's own tab."""
        results = [r for s in self.filtered_scripts() for r in s.results]
        self.rows = add_rows(results)
        try:  # the no-break spaces the languages shown set in their numbers, ranked as the others
            codes = self.font_found.codes if getattr(self, "font_found", None) is not None else None
            if codes is not None:
                self.rows = sorted(self.rows + space_rows(results, lambda code: code in codes, space_conventions()),
                                   key=lambda row: (-len(row.completing), -len(row.needing), code_points(row.items[0])))
        except Exception:
            pass  # (the list without them: never without the rest)
        self.fill_characters(self.add_tree, self.rows)
        self.tab_names["left"].set_text(0, value_title(len(self.rows)))
        self.fill_own()

    def fill_own(self):
        """The selection's own tab: the missing characters of the language, character set, or family
        selected, named after it; grayed, and empty, with nothing selected."""
        self.own_rows, left = selection_rows(self.rows, self.selection)
        self.fill_characters(self.own_tree, self.own_rows)
        self.tab_names["left"].set_text(1, selection_title(self.selection))
        self.left_tabs.setTabEnabled(1, self.selection is not None)
        self.own_label.setText(selection_text(self.selection, left, self.ak.b))
        self.own_label.setVisible(self.selection is not None and self.left_tab == "own")

    def show_left(self, key):
        """The tab of characters shown: "value" (the high-value list) or "own" (the selection's)."""
        if key == "own" and self.selection is None:
            key = "value"
        self.left_tab = key
        index = 1 if key == "own" else 0
        self.left_tabs.setCurrentIndex(index)
        self.left_page(index)
        self.own_label.setVisible(self.selection is not None and key == "own")

    def left_page(self, index):
        """The tab of glyphs shown (0: the high-value list, 1: the selection's), its list first among the
        stack's children. The shared module grays Check all, Check none, and Check only (ak.update_states,
        every 300 ms) when the list nearest them has no check box, and the two lists are equally near: it
        took the first, and Qt's stack raises the list it shows, which puts it last. So after a selection's
        tab was shown, the high-value tab's buttons were grayed again within 300 ms of each click that
        enabled them, as long as the selection's list was empty (the owner's report 133)."""
        self.left_pages.setCurrentIndex(index)
        try:
            (self.own_tree if index == 1 else self.add_tree).lower()
        except Exception:
            pass

    def left_tab_changed(self, index):
        """The tab bar of characters clicked: its list shown; the buttons act on it."""
        try:
            self.left_tab = "own" if index == 1 and self.selection is not None else "value"
            self.left_page(1 if self.left_tab == "own" else 0)
            self.own_label.setVisible(self.selection is not None and self.left_tab == "own")
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def shown_rows(self):
        """The rows of the tab of characters shown."""
        return self.own_rows if self.left_tab == "own" else self.rows

    def shown_tree(self):
        return self.own_tree if self.left_tab == "own" else self.add_tree

    def characters_selected(self):
        if self.filling:
            return
        self.update_buttons()

    def sync_checks(self):
        """Each tab's check boxes set from the characters checked, in place (a character checked in
        one tab is checked in the other; the rows and the selection kept)."""
        QtCore, QtGui = _qt()
        self.filling = True  # (itemChanged must not read the checks back meanwhile)
        try:
            for tree, rows in ((self.add_tree, self.rows), (self.own_tree, self.own_rows)):
                for item in self.top_items(tree):
                    index = self.index_of(item)
                    if 0 <= index < len(rows):
                        item.setCheckState(0, QtCore.Qt.Checked if set(rows[index].items) <= self.checked
                                           else QtCore.Qt.Unchecked)
        finally:
            self.filling = False

    def add_checked(self):
        """The checks of the tab shown read again (a click on one), and the other tab's set alike."""
        QtCore, QtGui = _qt()
        if self.filling:
            return
        rows = self.shown_rows()
        for item in self.top_items(self.shown_tree()):
            index = self.index_of(item)
            if not 0 <= index < len(rows):
                continue
            self.row_checked(rows[index], item.checkState(0) == QtCore.Qt.Checked)
        self.sync_checks()
        self.update_gain()
        self.update_buttons()

    def row_checked(self, row, on):
        """A row's characters checked or unchecked (a capital with its small letter)."""
        if on:
            self.checked |= set(row.items)
        elif set(row.items) <= self.checked:  # (a row half checked through the other tab stays as it is)
            self.checked -= set(row.items)

    def check_targets(self):
        """checks_for of the rows of the tab shown (Glyph Compose asked once per check, as the rows'
        tooltips are)."""
        rows = self.shown_rows()
        buildable = self.buildable_set() if self.package is not None and rows else set()
        return checks_for(rows, self.checked, buildable)

    def set_checks(self, key):
        """A check button clicked: the checks set as it says for the tab shown, in place in both tabs."""
        self.search_now()  # (a search typed a moment ago lists its rows first: the button acts on them)
        target = self.check_targets().get(key)
        if target is None or self.filling:
            return
        self.checked = set(target)
        self.sync_checks()
        self.update_gain()
        self.update_buttons()

    def update_gain(self):
        pool = self.results
        if self.selection is not None and self.selection.kind != "set":
            # (languages a search or a family brought up: each counts once its characters are checked)
            pool = pool + [r for r in self.selection.results if r not in pool]
        gained = languages_gained(pool, self.checked)
        if not self.rows and not self.checked:
            self.gain_label.setText(u"No language within reach here: nothing to add." if self.results else u"")
        else:
            self.gain_label.setText(gain_text(len(self.checked), gained, self.ak.b))
        tip = u"\n".join(u"%s (%s)" % (r.language.label(), script_group(r.language.script)) for r in gained[:TIP_NAMES])
        if len(gained) > TIP_NAMES:
            tip += u"\nand %s more" % grouped(len(gained) - TIP_NAMES)
        self.gain_label.setToolTip(self.tip(tip, True))

    def selected_row(self):
        """The row selected in the tab of characters shown."""
        rows = self.shown_rows()
        index = self.index_of(self.selected_item(self.shown_tree()))
        return rows[index] if 0 <= index < len(rows) else None

    def checked_listed(self):
        """The checked characters the tab shown lists, by code point."""
        listed = set(item for row in self.shown_rows() for item in row.items)
        return [c for c in sorted(self.checked, key=code_points) if c in listed]

    # The lists at the right: three tabs (Languages, Character sets, Families), each a list of its own.
    # A row's data is its index in right_rows[tab] (a Coverage, or a FamilyNode); a heading's is "#" and
    # its title. Nothing keeps an item: what is selected, closed, or opened is held by key and found
    # again each time a list is filled.

    def searched(self):
        return (u"%s" % (_prop(self.search, "text") or u"")).strip()

    def arrow(self, open_):
        """A heading's arrow as an icon (drawn once per state and palette)."""
        key = ("arrow", bool(open_))
        if key not in self.pictures:
            self.pictures[key] = self.icon(arrow_pixmap, bool(open_), faded(self.colors()["text"], 200))
        return self.pictures[key]

    def heading_open(self, tab, title):
        """Whether a heading is shown open. Scripts not yet covered is closed until asked for, and open
        while a search runs unless closed by hand during it (as a family is): what is shown is what a
        click toggles."""
        if title in CLOSING_TITLES:
            if self.searched():
                return title not in self.closed[tab]
            return self.scripts_open
        return title not in self.closed[tab]

    def family_open(self, node):
        """Whether a family shows its branches and languages: closed to start with, opened by hand;
        while a search runs, every family it lists is open unless closed by hand meanwhile."""
        if self.search_opens() and not (isinstance(node, UncoveredNode) and len(node.entries) > UNCOVERED_OPEN):
            return node.path not in self.closed["families"]  # (a long Not yet covered list stays closed until asked for)
        return node.path in self.opened

    def search_opens(self):
        """Whether the search opens the families it lists: from SEARCH_OPENS characters on. A letter
        or two match most languages, and opening every family made some 4,300 rows (one letter, under
        the tests' fakes), against 240 left closed."""
        return len(self.searched()) >= SEARCH_OPENS

    def toggle_family(self, node, item):
        """A family opened or closed (item: its row, handed over by Qt and used here and now)."""
        open_ = not self.family_open(node)
        searching = self.search_opens() and not (isinstance(node, UncoveredNode) and len(node.entries) > UNCOVERED_OPEN)
        held, wanted = (self.closed["families"], not open_) if searching else (self.opened, open_)
        if wanted:
            held.add(node.path)
        else:
            held.discard(node.path)
        if open_:
            self.fill_under("families", node.path, item)  # (its rows, made now that they are to be seen)
        item.setExpanded(open_)
        item.setIcon(0, self.arrow(open_))
        self.view_kept("families")

    def toggle_heading(self, tab, title, item):
        """A script's or a group's heading opened or closed, kept by its title through refills, other
        orders, and searches."""
        open_ = not self.heading_open(tab, title)
        if title in CLOSING_TITLES:
            if not self.searched():
                self.scripts_open = open_
            elif open_:  # (during a search: closed by hand until the search ends)
                self.closed[tab].discard(title)
            else:
                self.closed[tab].add(title)
            if open_:
                self.fill_under(tab, title, item)
        elif open_:
            self.closed[tab].discard(title)
            self.fill_under(tab, title, item)  # (its rows, made now that they are to be seen)
        else:
            self.closed[tab].add(title)
        item.setExpanded(open_)
        item.setIcon(0, self.arrow(open_))
        self.view_kept(tab)

    def right_expanded(self, tab, item, open_):
        """Qt opened or closed a row (its own doing: a key, or a press on a branch): what is held by
        title or place follows, and the row's arrow (item: handed over by Qt, used here and now).
        Nothing while a list is filled, nor when the state held says so already (list_pressed's)."""
        try:
            if self.filling:
                return
            entry = self.right_entry(tab, item)
            if entry is None or entry[0] == "row":
                return
            kind, value = entry
            if kind == "heading" and self.heading_open(tab, value) != open_:
                self.toggle_heading(tab, value, item)
            elif kind == "node" and self.family_open(value) != open_:
                self.toggle_family(value, item)
        except Exception:
            pass  # a signal's handler must not raise

    def right_entry(self, tab, item):
        """What a row of a right tab is: ("heading", title), ("node", FamilyNode), ("row", Coverage),
        or None (no row, or one of an earlier filling)."""
        if item is None:
            return None
        data = self.data_of(item, None)
        if data is None:
            return None
        try:
            index = int(data)
        except (TypeError, ValueError):
            text = u"%s" % data
            return ("heading", text[1:]) if text.startswith(u"#") else None
        rows = self.right_rows[tab]
        if not 0 <= index < len(rows):
            return None
        if isinstance(rows[index], Uncovered):
            return None  # (a language that cannot be checked: a row to read, with nothing to select)
        return ("node" if isinstance(rows[index], FamilyNode) else "row", rows[index])

    @staticmethod
    def entry_selection(entry):
        """The Selection a row stands for: a language's or a set's, or a family's languages; None for
        a heading or no row."""
        if entry is None:
            return None
        kind, value = entry
        if kind == "row":
            return selection_of(value)
        if kind == "node" and not isinstance(value, UncoveredNode):  # (Not yet covered: nothing to check)
            return Selection("family", value.name, value.all_results(), ("family",) + value.path)
        return None

    def selected_entry(self, tab):
        """The row selected in a right tab, as right_entry gives it."""
        return self.right_entry(tab, self.selected_item(self.right_trees[tab]))

    # The rows of a closed heading or family are not made until it is opened: with some 2,500 languages,
    # the Families tab made a row for each one behind its closed families at every filling, and a closed
    # script kept thousands. What a closed row holds waits in self.unfilled (by title or by place, never by
    # item); the row Qt hands over when it is opened takes its rows then, here and now.

    def tools(self):
        """What a row is drawn with: a dot per level and the quiet text color (made once per filling)."""
        if self.row_tools is None:
            QtCore, QtGui = _qt()
            colors = self.colors()
            self.row_tools = (dict((key, self.icon(dot_pixmap, level_color(key, colors))) for key in BAR_LEVELS),
                              QtGui.QBrush(faded(colors["text"], QUIET_ALPHA)), colors)
        return self.row_tools

    @staticmethod
    def expandable(item):
        """A row whose rows are made later counts as one Qt may open (a key opens it as a press does)."""
        try:
            QtCore, QtGui = _qt()
            item.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.ShowIndicator)
        except Exception:
            pass

    def language_row(self, tab, r, parent, wanted=None, found=None, also=u"", select=False):
        """A language's or a character set's row, under parent (None: at the top). The row that is the
        selection (wanted: its key) is noted in found and made current (select: only marked selected,
        for a row made under a heading just opened: making it current would scroll to it)."""
        tree, rows = self.right_trees[tab], self.right_rows[tab]
        dots, quiet, _ = self.tools()
        texts = (r.language.label() + also, language_note(r)) if tab != "families" else \
            (r.language.label() + also, u"", language_note(r))
        item = self.item(texts, len(rows), self.later_tip(tab, r), True)
        item.setIcon(0, dots[r.level])
        if texts[-1] and (r.level == "covered" or (r.language.kind != "set" and r.level != "nearly")):
            item.setForeground(len(texts) - 1, quiet)  # ("composed", "inferred": said quietly; not what is missing)
        self.add_row(tab, r, texts[0])
        if parent is None:
            tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        if wanted is not None and language_key(r) == wanted and (found is None or found["selection"] is None):
            if found is not None:
                found["selection"] = selection_of(r)
            if select:
                item.setSelected(True)
            else:
                tree.setCurrentItem(item)  # (the row just made; the selection's handler is held off)
        return item

    def family_rows(self, tab, node, parent, wanted=None, found=None, select=False):
        """The rows of a family's branches and languages under parent (None: the families at the top).
        A branch that is open takes its rows at once; a closed one waits (self.unfilled), and what is
        selected under it is noted in found without a row."""
        tree, rows = self.right_trees[tab], self.right_rows[tab]
        quiet = self.tools()[1]
        # (the counts at the dialog's size, as the scripts' list has them: in the list's enlarged font they
        # stood out as larger than every other list's text, live; the names keep the list's size)
        counts_font = self.picture_font()
        for one in [one for one in node.children if not isinstance(one, UncoveredNode)]:
            counts_ = level_counts(one.all_results())
            open_ = self.family_open(one)
            label = u"%s (%d)" % (one.name, sum(counts_))
            item = self.item((label, u"", coverage_text(counts_),
                              uncovered_count_text(len(one.uncovered))), len(rows), self.later_tip(tab, one), True)
            item.setData(1, BAR_ROLE, bar_counts(counts_))  # (drawn to the column's width: bar_delegate)
            item.setForeground(3, quiet)  # (in gray: known, not yet covered)
            item.setFont(2, counts_font)
            item.setFont(3, counts_font)
            item.setIcon(0, self.arrow(open_))
            self.add_row(tab, one, label)
            if parent is None:
                tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            if wanted == ("family",) + one.path and (found is None or found["selection"] is None):
                if found is not None:
                    found["selection"] = self.entry_selection(("node", one))
                if select:
                    item.setSelected(True)
                else:
                    tree.setCurrentItem(item)
            if open_:
                self.family_rows(tab, one, item, wanted, found, select)
            else:
                self.unfilled[tab][one.path] = one
                self.expandable(item)
                if found is not None and found["selection"] is None and wanted is not None:
                    found["selection"] = self.held_selection(one, wanted)
            item.setExpanded(open_)  # (once its rows are under it)
        several = {}
        for r in node.results:
            several[r.language.iso] = several.get(r.language.iso, 0) + 1
        for r in node.results:  # (a language written in two scripts is listed twice: each says its script)
            self.language_row(tab, r, parent, wanted, found,
                              u", %s" % r.language.script if several[r.language.iso] > 1 else u"", select)
        for entry in getattr(node, "entries", ()):  # (under Not yet covered: a row to read each, in gray)
            scripts = self.known_scripts.of_languages.get(entry.iso, ())
            label = u"%s (%s)" % (entry.name, entry.iso)
            item = self.item((label, u"", u"", u", ".join(scripts)), len(rows), self.later_tip(tab, entry), True)
            item.setForeground(0, quiet)
            item.setForeground(3, quiet)
            self.add_row(tab, entry, label)
            if parent is None:
                tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
        for one in [one for one in node.children if isinstance(one, UncoveredNode)]:
            # A family's last node: its languages that cannot be checked yet, their rows made when it is opened
            open_ = self.family_open(one)
            label = u"%s (%d)" % (one.name, len(one.entries))
            item = self.item((label, u"", u"", u""), len(rows), self.later_tip(tab, one), True)
            item.setForeground(0, quiet)
            item.setIcon(0, self.arrow(open_))
            self.add_row(tab, one, label)
            if parent is None:
                tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            if open_:
                self.family_rows(tab, one, item, wanted, found, select)
            else:
                self.unfilled[tab][one.path] = one
                self.expandable(item)
            item.setExpanded(open_)

    def held_selection(self, node, wanted):
        """The Selection of key wanted among what a closed family holds (its languages, its branches,
        and theirs), or None: it stays selected though it has no row yet."""
        for r in node.results:
            if language_key(r) == wanted:
                return selection_of(r)
        for one in node.children:
            if wanted == ("family",) + one.path:
                return self.entry_selection(("node", one))
            held = self.held_selection(one, wanted)
            if held is not None:
                return held
        return None

    def fill_under(self, tab, key, item):
        """A heading or a family opened for the first time since the list was filled: its rows made
        under item, the row Qt handed over (used here and now); the selection's row among them is
        marked selected. Nothing when its rows are there already. The handlers are held off meanwhile."""
        waiting = self.unfilled.get(tab, {}).pop(key, None)
        if waiting is None:
            return
        wanted = self.selection.key if self.selection is not None else None
        was, self.filling = self.filling, True
        try:
            if isinstance(waiting, FamilyNode):
                self.family_rows(tab, waiting, item, wanted, None, True)
            elif key in CLOSING_TITLES:
                self.script_rows(tab, waiting, item, wanted, None, True)
            else:
                for r in waiting:
                    self.language_row(tab, r, item, wanted, None, u"", True)
        finally:
            self.filling = was

    def script_rows(self, tab, waiting, parent, wanted=None, found=None, select=False):
        """The rows of the scripts not yet covered, under their heading. waiting: (the scripts'
        coverages, the names of those without a set). A script is checked as a set of its whole
        repertoire: its row shows its level and what is missing, and selects like any other (its
        tooltip says that no language data exists yet). One without a set (a data file made before)
        is a row to read, in gray."""
        live, names = waiting
        for r in live:
            self.language_row(tab, r, parent, wanted, found, u"", select)
        quiet = self.tools()[1]
        for name in names:
            item = self.item((name, u""), u"script:%s" % name,
                             u"%s: a script Unicode encodes. No orthography here is written in it, so no language "
                             u"written in it can be checked yet.\n\n%s" % (name, CONTRIBUTE_SCRIPTS), True)
            item.setForeground(0, quiet)
            parent.addChild(item)

    def family_results(self, shown, searching):
        """The languages the Families tab classifies: those of the scripts listed; every language while
        a search runs, as the Languages tab searches."""
        if searching:
            return [r for s in self.scripts for r in s.results] + list(self.other_results)
        return [r for s in self.scripts if s.script in shown for r in s.results]

    # Each tab at the right has two lists, the full one and a search's (RightView). The one shown is
    # right_trees[tab], its rows right_rows[tab], what its closed rows hold unfilled[tab]: activate swaps
    # them. A list is filled anew only when what it shows would change (view_signature): a new check,
    # another level, order, script, or search, a heading opened or closed elsewhere. Otherwise it is shown as
    # it was, scrolled where it was, which also makes clearing a search instant.

    def activate(self, tab, mode):
        """One of a tab's lists (VIEW_MODES: every script's, the chosen script's, or a search's) made the
        one shown; its RightView. A script's list is marked as the chosen script's, shown now (view_mode)."""
        view = self.views[tab][mode]
        if mode in SCRIPT_MODES:
            self.view_clock = getattr(self, "view_clock", 0) + 1
            view.script, view.used = self.script_filter, self.view_clock
        self.right_trees[tab], self.right_rows[tab], self.unfilled[tab] = view.tree, view.rows, view.unfilled
        try:
            self.right_pages.setCurrentIndex([key for key, _ in RIGHT_TABS].index(tab) * len(VIEW_MODES)
                                             + VIEW_MODES.index(mode))
        except Exception:
            pass
        return view

    def view_mode(self, tab, text):
        """Which of a tab's lists shows now (VIEW_MODES): a search's finds; the chosen script's; every
        script's. The Character sets tab lists the same sets whatever the script: its full list always. A
        script's list is the one last shown for that script (kept as it was, unless what it shows changed
        since: its signature), else the one least recently shown (SCRIPT_MODES). Asks only: activate marks."""
        if text:
            return "search"
        if self.script_filter is None or tab == "sets":
            return "full"
        views = self.views[tab]
        for mode in SCRIPT_MODES:
            if views[mode].script == self.script_filter:
                return mode
        return min(SCRIPT_MODES, key=lambda mode: views[mode].used)

    def active_view(self, tab):
        """The RightView shown for a tab (None for none)."""
        tree = self.right_trees.get(tab)
        return next((view for view in self.views.get(tab, {}).values() if view.tree is tree), None)

    def view_signature(self, tab, text, level, sort, shown):
        """What a list at the right is filled from: the check, the choices, the search, and the
        headings and families opened or closed (by hand: their rows are then made or kept). Two equal
        signatures fill a list alike."""
        if tab == "families":
            state = frozenset(self.closed["families"]) if len(text) >= SEARCH_OPENS else frozenset(self.opened)
        elif text:
            state = frozenset(self.closed[tab])
        else:
            state = (frozenset(title for title in self.closed[tab] if title not in CLOSING_TITLES), self.scripts_open)
        if tab == "sets":  # (the same sets whatever the script chosen above: not made anew at a script's click)
            return (self.generation, level, sort, text, state)
        return (self.generation, level, sort, tuple(shown), self.script_filter, text, state)

    def view_kept(self, tab):
        """A heading or a family opened or closed by hand, in the list shown, which shows it so already:
        its signature follows, so that the list is not filled anew for it when it is shown again."""
        try:
            view = self.active_view(tab)
            if view is not None and view.signature is not None:
                view.signature = self.view_signature(
                    tab, self.searched(), self.choice(self.level_filter, LANGUAGE_FILTERS)[0],
                    self.choice(self.sort_box, SORTS)[0], [s.script for s in self.filtered_scripts()])
        except Exception:
            pass

    def listed_selection(self, tab, made, wanted, text, level):
        """The Selection of key wanted as a tab lists it (made: its sections, or its families' root),
        or None when it does not: what a refill would find, without making a row."""
        if wanted is None:
            return None
        if tab == "families":
            def walk(node):
                for r in node.results:
                    if language_key(r) == wanted:
                        return selection_of(r)
                for one in node.children:
                    if isinstance(one, UncoveredNode):
                        continue
                    if wanted == ("family",) + one.path:
                        return self.entry_selection(("node", one))
                    held = walk(one)
                    if held is not None:
                        return held
                return None
            return walk(made[0])
        for section in made[0]:
            for r in section.results:
                if language_key(r) == wanted:
                    return selection_of(r)
        if tab == "languages":
            for r in self.uncovered_scripts(text, level)[0]:
                if language_key(r) == wanted:
                    return selection_of(r)
        return None

    def row_key(self, row):
        """What a row of a right tab stands for, as a Selection's key: a language's or a set's, a
        family's place; None for the others."""
        if isinstance(row, Coverage):
            return language_key(row)
        if isinstance(row, FamilyNode) and not isinstance(row, UncoveredNode):
            return ("family",) + row.path
        return None

    def item_of(self, tab, key):
        """The item of the list shown whose row stands for key, found by its label (one call to Qt),
        or None (no row made for it: under a closed heading)."""
        QtCore, QtGui = _qt()
        view = self.active_view(tab)
        if view is None:
            return None
        index = next((k for k, row in enumerate(view.rows) if self.row_key(row) == key), None)
        if index is None or index >= len(view.labels):
            return None
        try:
            items = view.tree.findItems(view.labels[index], QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive, 0)
            for item in items:
                if self.index_of(item) == index:
                    return item
        except Exception:
            pass
        return None

    def select_row(self, tab, selection):
        """The list shown, kept as it was, made to show the selection: its row selected (and scrolled
        to) when it is another than the one selected there, or none selected. Its handlers are held off."""
        try:
            current = self.entry_selection(self.selected_entry(tab))
            wanted = selection.key if selection is not None else None
            if (current.key if current is not None else None) == wanted:
                return
            tree = self.right_trees[tab]
            was, self.filling = self.filling, True
            try:
                tree.clearSelection()
                item = self.item_of(tab, wanted) if wanted is not None else None
                if item is not None:
                    tree.setCurrentItem(item)
            finally:
                self.filling = was
        except Exception:
            pass

    def search_typed(self):
        """The search field edited: the search waits for a pause in the typing (SEARCH_DELAY); a field
        cleared (its cross, or the text deleted) shows the full list at once."""
        try:
            if self.searched():
                self.search_timer.start()
            else:
                self.search_timer.stop()
                self.languages_changed()
        except Exception:
            pass  # a signal's handler must not raise

    def search_paused(self):
        try:
            self.languages_changed()
        except Exception:
            pass  # a timer's handler must not raise

    def search_now(self):
        """A search still waiting for the pause in the typing (search_timer) done now, so a button clicked
        right after typing acts on the list the search makes, not the one before it."""
        try:
            waiting = self.search_timer.isActive()
        except Exception:
            waiting = False
        if waiting:
            self.search_timer.stop()
            self.search_paused()

    def add_row(self, tab, row, label):
        """A row noted in the list being filled: what its item's data indexes, and the label that
        finds its item again (select_row)."""
        self.right_rows[tab].append(row)
        view = self.active_view(tab)
        if view is not None and view.rows is self.right_rows[tab]:
            view.labels.append(label)

    def uncovered_scripts(self, text, level):
        """The coverages of the scripts no orthography here is written in (each script as a set), for
        the Languages tab's closing section: those a search names, of the level kept; and the names of
        those that have no set to check them by (a data file made before), when no level is kept. The
        notations (Braille, SignWriting) are character sets, not listed here (languages_not_covered)."""
        names = scripts_section(languages_not_covered(self.known_scripts.not_covered), text)
        by_name = dict((r.language.name, r) for r in self.set_results if isinstance(r.language, ScriptSet))
        live = [by_name[name] for name in names if name in by_name and (level is None or by_name[name].level == level)]
        return live, ([name for name in names if name not in by_name] if level is None else [])

    def fill_right(self, refill=True, progress=None):
        """The tab shown at the right filled: the languages under their scripts (with a text searched,
        every language that matches, those not listed otherwise under headings that say why), the
        character sets under their groups, or the languages under their families. The tabs' captions
        count what each lists. What is selected stays selected when the tab still lists it (found again
        by what it is: the rows are new); when it does not, the selection's tab of characters empties
        (refill: here; False when the caller fills the characters next). progress(part), when given: told
        how far the rows are made (it may raise ak.Stopped: the rows made so far stay, and what follows them
        is set as for a whole list, but the list is made anew the next time it is shown; then it is raised
        again)."""
        QtCore, QtGui = _qt()
        tab = self.right_tab
        level = self.choice(self.level_filter, LANGUAGE_FILTERS)[0]
        sort = self.choice(self.sort_box, SORTS)[0]
        text = self.searched()
        shown = [s.script for s in self.filtered_scripts()]
        # The tab's full list, or its search's: the other stays as it is behind it (activate)
        view = self.activate(tab, self.view_mode(tab, text))
        tree, colors = view.tree, self.colors()
        # Each tab's finds, for the captions; the tab shown last, since each tells its rows the other
        # name a search found them by.
        made = {}
        for key in [key for key, _ in RIGHT_TABS if key != tab] + [tab]:
            if key == "languages":
                made[key] = language_sections(self.scripts, shown, text, level, sort, self.other_results,
                                              self.choice(self.status_filter, STATUS_FILTERS)[2])
            elif key == "sets":
                made[key] = set_sections(self.set_results, text, level, sort)
            else:
                # (with one script chosen above, the languages that cannot be checked are left out: most have no
                # script recorded)
                uncovered = self.families.uncovered() if self.families is not None and self.script_filter is None else None
                made[key] = family_tree(self.family_results(shown, bool(text)), self.families, text, level, sort, uncovered)
        counts = {"languages": sum(len(s.results) for s in made["languages"][0]),
                  "sets": sum(len(s.results) for s in made["sets"][0]), "families": len(made["families"][0].children)}
        for index, (key, label) in enumerate(RIGHT_TABS):
            self.tab_names["right"].set_text(index, u"%s (%s)" % (label, grouped(counts[key])))
        try:  # (what the sets' count is made of: it adds up to the top line's counts, set_tally)
            index = [key for key, _ in RIGHT_TABS].index("sets")
            self.right_tabs.setTabToolTip(index, sets_tab_tip([r for s in made["sets"][0] for r in s.results]))
        except Exception:
            pass
        wanted = self.selection.key if self.selection is not None else None
        found = {"selection": None}
        if tab == "families" and self.reveal and self.selection is not None and not text:
            self.open_to(made["families"][0], wanted)
        self.reveal = False
        if not text:
            self.closed["families"].clear()  # (what was closed by hand during a search ends with it)
            for held in self.closed.values():
                for closing in CLOSING_TITLES:
                    held.discard(closing)
        signature = self.view_signature(tab, text, level, sort, shown)
        if view.signature == signature:
            # Filled from the same check, choices, and headings opened: shown as it is, where it was
            # scrolled to (the owner: switching tabs brought each list back to its top). The selection
            # goes with it where it lists it, as a refill would have found it.
            found["selection"] = self.listed_selection(tab, made[tab], wanted, text, level)
            self.select_row(tab, found["selection"])
            self.after_fill(tab, made, text, level, shown, found, refill)
            return
        view.signature = signature
        self.tip_cache = {}  # (keyed by the rows' identities: rows made anew may take an old one's)
        rows = self.right_rows[tab] = view.rows = []
        view.labels = []
        pending = self.unfilled[tab] = view.unfilled = {}
        self.row_tools = None  # (the rows' dots made anew: the palette may have changed)

        stopped = None
        self.filling = True
        self.ak.quiet_list(tree, True)
        try:
            tree.clear()
            if tab == "families":
                self.family_rows(tab, made[tab][0], None, wanted, found)
                self.share_columns(tree)
            else:
                sections = made[tab][0]
                headed = tab == "sets" or len(sections) > 1 or any(section.why for section in sections)
                every, done = max(1, sum(len(section.results) for section in sections)), 0
                for section in sections:
                    if progress is not None:  # (a check's bar: by the rows made so far)
                        progress(done / float(every))
                    done += len(section.results)
                    heading, open_ = None, True
                    if headed:
                        # (a heading that says why is long: whole in its tooltip when the list cuts it)
                        heading = self.item((section.heading(), u""), u"#%s" % section.title,
                                            section.heading() if section.why else u"", True)
                        heading.setFlags(QtCore.Qt.ItemIsEnabled)
                        open_ = self.heading_open(tab, section.title)
                        heading.setIcon(0, self.arrow(open_))
                        tree.addTopLevelItem(heading)
                        heading.setFirstColumnSpanned(True)
                        self.ak.section_row(heading, tree)
                    if open_:
                        for made_rows, r in enumerate(section.results):
                            if progress is not None and made_rows and made_rows % LISTING_STEP_ROWS == 0:
                                progress((done - len(section.results) + made_rows) / float(every))  # (one script: one section)
                            self.language_row(tab, r, heading, wanted, found)
                    else:  # (closed: its rows are made when it is opened; what is selected under it stays so)
                        pending[section.title] = section.results
                        self.expandable(heading)
                        if found["selection"] is None and wanted is not None:
                            held = [r for r in section.results if language_key(r) == wanted]
                            found["selection"] = selection_of(held[0]) if held else None
                    if heading is not None:
                        heading.setExpanded(open_)
                live, names = self.uncovered_scripts(text, level) if tab == "languages" else ([], [])
                live = sort_languages(live, sort)
                if live or names:
                    # The closing section: the scripts Unicode has that no orthography here is written in,
                    # each checked as a script (its whole repertoire), a row that selects like any other. Its
                    # tooltip says what "not yet covered" means (the owner wondered how they had previews)
                    title = u"%s (%d)" % (SCRIPTS_NOT_COVERED, len(live) + len(names))
                    heading = self.item((title, u""), u"#%s" % SCRIPTS_NOT_COVERED,
                                        u"%s\n\n%s\n\n%s" % (NOT_COVERED_MEANS, CONTRIBUTE_SCRIPTS, NOT_ENCODED), True)
                    heading.setFlags(QtCore.Qt.ItemIsEnabled)
                    open_ = self.heading_open(tab, SCRIPTS_NOT_COVERED)  # (closed until asked for; a search opens it)
                    heading.setIcon(0, self.arrow(open_))
                    tree.addTopLevelItem(heading)
                    heading.setFirstColumnSpanned(True)
                    self.ak.section_row(heading, tree)
                    if open_:
                        self.script_rows(tab, (live, names), heading, wanted, found)
                    else:
                        pending[SCRIPTS_NOT_COVERED] = (live, names)
                        self.expandable(heading)
                        if found["selection"] is None and wanted is not None:  # (selected, without a row for now)
                            held = [r for r in live if language_key(r) == wanted]
                            found["selection"] = selection_of(held[0]) if held else None
                    heading.setExpanded(open_)
                self.share_columns(tree)
        except self.ak.Stopped as exc:
            stopped = exc  # (by the user: listing)
            view.signature = None
        finally:
            self.ak.quiet_list(tree, False)
            self.filling = False
        self.after_fill(tab, made, text, level, shown, found, refill)
        if stopped is not None:
            raise stopped

    def after_fill(self, tab, made, text, level, shown, found, refill):
        """What follows the list at the right, filled or shown as it was: the line under it, and the
        selection kept (found["selection"]) or let go, the selection's tab of glyphs with it."""
        note = self.right_note(tab, made[tab], text, level, shown)
        self.languages_note.setText(self.note_html(note) if self.links_in(note) else note)
        self.languages_note.setVisible(bool(note))
        was, self.selection = self.selection, found["selection"]
        if was is not None and self.selection is None:
            self.show_left("value")
            if refill:
                self.fill_own()
                self.update_gain()
        elif self.selection is not None:
            # (kept through a new check, an undo's: the check forgot what Glyph Compose was asked, and the rows
            # of a started language, a set, or a family lost "Glyph Compose can build it". Asked once per check)
            self.ask_buildable(self.selection)

    def right_note(self, tab, made, text, level, shown):
        """The line under the list at the right: what a search found, what is not listed and why, and
        the languages a search names that Hyperglot does not describe."""
        lines = []
        if tab == "families":
            lines.append(families_line(made[0], text, made[1], level, self.families is not None))
        elif tab == "sets":
            lines.append(languages_line(made[0], text, made[1], 0, 0, level, RIGHT_NOUNS["sets"]))
        else:
            outside = sum(len(s.results) for s in self.scripts if s.script not in shown)
            lines.append(languages_line(made[0], text, made[1], outside, len(self.other_results), level))
        unlisted = self.families.unlisted_matches(text) if text and tab != "sets" and self.families is not None else []
        if unlisted:
            lines.append(unlisted_line(unlisted))
        if text and tab == "languages":  # (Braille and SignWriting: character sets, a link to them)
            lines.append(notation_line(text))
        if text:  # (what Font Check knows of and does not check: Korean gukja, emoji sequences, Jurchen)
            lines.append(known_line(self.coverage_gaps.known_matches(text)))
        if tab == "families" and self.families is not None and not text:
            # What can be checked of what is known, and how to add to it
            counts = self.families.counts
            not_covered = self.known_scripts.not_covered
            listed = languages_not_covered(not_covered)
            lines.append(coverage_counts_text(counts.get("described", 0), counts.get("glottolog_languages_with_iso", 0),
                                              self.known_scripts.known - len(not_covered), self.known_scripts.known,
                                              len(listed), len(not_covered) - len(listed)))
            if any(isinstance(r.language, ScriptSet) for r in self.set_results):
                lines.append(u"Every script of Unicode is checked as a set of its own, under Character sets.")
            # What limits the rest, with its date: the record itself (a script on record without characters, or none)
            lines.append(limits_text(len(self.families.unlisted),
                                     sum(1 for row in self.families.unlisted
                                         if (u"%s" % row[0]) in self.known_scripts.of_languages)))
        # ("These languages": those listed, so only when some are: not under a search that lists none)
        if unlisted or (tab == "families" and self.families is not None and self.families.uncovered()
                        and (not text or shows_uncovered(made[0]))):
            lines.append(CONTRIBUTE)
        return u" ".join(line for line in lines if line)

    def note_html(self, note):
        """The line under the list as rich text: "issue" in it a link to the repository's issues (opened on a
        click), the address no longer written out after it (the owner's image of November 23: the address in
        parentheses made the line run long). A tooltip, where nothing can be clicked, keeps the address
        written out (CONTRIBUTE as it is). An address the sentence does not introduce is a link as written."""
        text = self.ak.html(note)
        address = self.ak.html(ISSUES_ADDRESS)
        linked = text.replace(u"open an issue on FreeLab's repository (%s)" % address,
                              u"open an <a href=\"%s\">issue</a> on FreeLab's repository" % address)
        if linked == text:
            linked = text.replace(address, u'<a href="%s">%s</a>' % (address, address))
        text = linked
        for _, _, block in NOTATION_SCRIPTS:  # (a notation's set: a click shows it in the Character sets tab)
            name = self.ak.html(block)
            text = text.replace(name, u'<a href="%s%s">%s</a>' % (SET_LINK, name, name))
        return text

    def links_in(self, note):
        """Whether the line under the lists has links to make (note_html)."""
        return ISSUES_ADDRESS in note or any(block in note for _, _, block in NOTATION_SCRIPTS)

    def show_set(self, name):
        """A notation's set shown: the Character sets tab, searched for its name (a link in the line
        under the Languages tab, where a search for Braille or SignWriting finds no language)."""
        self.search.setText(name)  # (its signal waits for a pause: stopped, the tab is listed below at once)
        self.search_timer.stop()
        index = [key for key, _ in RIGHT_TABS].index("sets")
        self.right_tabs.setCurrentIndex(index)  # (its signal lists the tab: right_tab_changed)
        if self.right_tab != "sets":
            self.right_tab_changed(index)
        else:
            self.languages_changed()

    def open_to(self, root, key):
        """The families above the language selected opened, so the Families tab shows it."""
        def walk(node, above):
            if any(language_key(r) == key for r in node.results):
                return above
            for one in node.children:
                reached = walk(one, above + [one.path])
                if reached is not None:
                    return reached
            return None

        self.opened.update(walk(root, []) or [])

    def right_tab_changed(self, index):
        """Another tab at the right: its list shown, as it was when nothing it shows has changed since
        (scrolled where it was), else filled (the search, the level, and the order act on it); the
        selection goes with it when the tab lists it too."""
        try:
            if self.filling or self.busy or not 0 <= index < len(RIGHT_TABS):
                return
            self.right_tab = RIGHT_TABS[index][0]
            self.custom_row.setVisible(self.right_tab == "sets")  # (a set of the user's own is pasted there)
            self.reveal = True
            self.listing(lambda progress: self.fill_right(progress=progress),
                         listing_text(self.right_tab, self.script_filter))
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def right_selected(self, tab):
        """A right tab's selection changed (Qt's signal)."""
        if self.filling or tab != self.right_tab:
            return
        self.select(self.entry_selection(self.selected_entry(tab)))
        self.update_buttons()

    def select(self, selection):
        """A language, a character set, or a family selected (None: none): its missing characters fill
        the second tab of characters, which is shown and named after it; with none, that tab is grayed
        and the high-value list shown again. The same selection again changes nothing, unless it stands
        for other coverages (a new check made them): the pasted set edited, or a selected saved set saved
        again, keep their key while what they miss changes."""
        before = self.selection
        if (selection.key if selection is not None else None) == (before.key if before is not None else None) and (
                selection is None or same_results(selection.results, before.results)):
            self.selection = selection
            return
        self.selection = selection
        if selection is not None:
            self.ask_buildable(selection)
        self.fill_own()
        self.show_left("own" if selection is not None else "value")
        self.update_gain()

    def on_arrow(self, tree, item, pos):
        """Whether a press fell on a row's arrow (the first pixels of the row, where its icon is)."""
        if pos is None:
            return False
        try:
            return int(pos.x()) < int(tree.visualItemRect(item).left()) + ARROW_ZONE
        except Exception:
            return False

    def list_pressed(self, tree, item, pos=None, double=False):
        """A mouse press on a Coverage list, or a double-click's second press, heard before Qt handles
        it (item: the row under the mouse, None on the list's empty part); True: the press is used up.
        On the empty part the selection is cleared: Qt keeps a single selection whatever is clicked.
        A press on a heading opens or closes it, and nothing else: Qt does not see it (a double-click's
        second press does nothing more, so a click and a double-click both do it once). On a family, a
        press on its arrow opens or closes it
        and selects nothing; a double-click on its name does too. A press on the row selected already
        is remembered, for the click that follows to unselect it."""
        tab = next((key for key, one in self.right_trees.items() if one is tree), None)
        entry = self.right_entry(tab, item) if tab is not None else None
        if tab is None or entry is None:
            self.pressed = None if tab is not None else self.pressed
            if item is None and not double:
                tree.clearSelection()
                if tab == self.right_tab and self.selection is not None and self.selected_entry(tab) is None:
                    # (what was selected had no row: under a closed heading, its rows not made. Qt had
                    # nothing to unselect and sends no signal)
                    self.select(None)
                    self.update_buttons()
            return False
        kind, value = entry
        if kind == "heading":
            # Used up, the double-click's second press too: handed on, Qt made the heading its current
            # row and cleared the selection (the owner: a click on a group's arrow selected its heading),
            # and turned a double-click on a row it had not seen pressed into a press of its own.
            self.pressed = None
            if not double:
                self.toggle_heading(tab, value, item)
            return True
        if kind == "node" and isinstance(value, UncoveredNode):  # (as a heading: a press anywhere opens or closes it)
            self.pressed = None
            if not double:
                self.toggle_family(value, item)
            return True
        if kind == "node" and self.on_arrow(tree, item, pos):
            # (an arrow's press selects nothing, a double-click's second one neither: handed on, Qt, which
            # had not seen the first, took it for a press and selected the family)
            self.pressed = None
            self.toggle_family(value, item)
            return True
        if kind == "node" and double:
            self.pressed = None
            self.toggle_family(value, item)
            return False  # (a double-click on its name goes on to Qt, which saw the first press)
        selected = self.selection.key if self.selection is not None else None
        under = self.entry_selection(entry).key
        self.pressed = selected if selected is not None and selected == under and not double else None
        return False

    def right_clicked(self, tab):
        """A click on a right tab's list, after Qt selected its row: on the row that was selected
        already, it is unselected, and the selection's tab of characters grayed again."""
        try:
            before, self.pressed = self.pressed, None
            if before is not None and self.selection is not None and before == self.selection.key:
                self.right_trees[tab].clearSelection()
        except Exception:
            pass  # a signal's handler must not raise

    def right_double_clicked(self, tab, item):
        """A double-click on a language or a character set: its characters in a Glyph window. Its first
        click unselected a row selected already: the row Qt hands over is selected again first (used
        here and now). A family's double-click opens or closes it (list_pressed) and nothing else."""
        try:
            entry = self.right_entry(tab, item)
            if entry is None or entry[0] != "row":
                return
            if self.selected_entry(tab) is None:
                self.right_trees[tab].setCurrentItem(item)
            self.open_glyph_text(self.selection_glyph_text(selection_of(entry[1])))
        except Exception:
            pass  # a signal's handler must not raise

    def character_double_clicked(self, key, item):
        """A double-click on a character's row: that character in a Glyph window (a capital with its
        small letter), whatever is checked; Show in Glyph window is for the checked ones."""
        try:
            rows = self.own_rows if key == "own" else self.rows
            index = self.index_of(item)
            if 0 <= index < len(rows):
                self.open_glyph_text(u"".join(rows[index].items))
        except Exception:
            pass  # a signal's handler must not raise

    def selection_glyph_text(self, selection=None):
        """FontLab text of what a selection misses (and, for one language or set, what it composes):
        the first of them (a character set, or Chinese, may miss thousands)."""
        selection = selection if selection is not None else self.selection
        if selection is None:
            return u""
        if len(selection.results) == 1 and selection.kind != "family":
            r = selection.results[0]
            return u"".join((r.all_missing()[:FLOAT_MOST] + [c for c, _ in r.composed])[:FLOAT_MOST])
        return u"".join(selection.wanted()[:FLOAT_MOST])

    def diacritics_module(self):
        if self.diacritics is None:
            self.diacritics = self.ak.load_sibling(DIACRITICS_FILE, DIACRITICS_MODULE)
        return self.diacritics

    def buildable_set(self):
        """The missing characters of the languages within reach that Glyph Compose's own planning can build
        from the font's letters and marks (asked once per check)."""
        if self.buildable is not None:
            return self.buildable
        found = set()
        try:
            found = self.diacritics_plan([r for r in self.results if r.level == "nearly"])
        except Exception as exc:
            self.log.add(u"<i>Glyph Compose</i> could not be asked: %s" % self.ak.html(exc), "warning")
        try:  # and what its Glyph generation tab builds of other glyphs (spaces, dashes, quotes...)
            self.generated = set(self.diacritics_module().generation_characters(self.ak, self.package))
        except Exception:
            self.generated = set()  # (an older Glyph Compose, or none: its rows say nothing of it)
        found = set(found) | self.generated
        self.buildable = found
        return found

    def diacritics_plan(self, results):
        """The missing characters of the coverages given that Glyph Compose's planning can build."""
        dm = self.diacritics_module()
        ranges = [pair for _, _, pairs in dm.SETS for pair in pairs]
        candidates = buildable_candidates(results, ranges)
        if not candidates:
            return set()
        # (Glyph Compose's Font of every glyph, made once per check and font: each new selection asked again
        # made it anew. A check forgets it, as it forgets what was asked: the glyphs may have changed)
        held = self.plan_font
        if held is None or held[0] is not self.package or held[1] is not dm:
            fgs = list(self.package.fgPackage.glyphs)
            held = self.plan_font = (self.package, dm, dm.Font([u"%s" % g.name for g in fgs],
                                                               # (every code point of each glyph, the first
                                                               # glyph at one last: Font's map keeps it)
                                                               list(reversed([(u"%s" % g.name, code) for g in fgs
                                                                              for code in glyph_codes(g)]))))
        return set(recipe.char for recipe in dm.plan(held[2], candidates) if not recipe.missing)

    def ask_buildable(self, selection):
        """Glyph Compose asked about a selection's characters too, once per check: the first asking covers
        the languages within reach only, and a started or missed language's, a character set's, or a
        family's rows are listed while it is selected."""
        results = [r for r in selection.results if r.level != "covered" and not (r.level == "nearly" and r in self.results)]
        if self.package is None or selection.key in self.asked or not results:
            return
        self.asked.add(selection.key)
        try:
            self.buildable = set(self.buildable_set()) | self.diacritics_plan(results)
        except Exception:
            pass  # (its rows say nothing of Glyph Compose then)

    def chosen_characters(self):
        """What the buttons act on: the checked characters the tab shown lists, or, with none of them
        checked, the selected row's."""
        checked = self.checked_listed()
        if checked:
            return checked
        row = self.selected_row()
        return sorted(row.items, key=code_points) if row is not None else []

    def buildable_checked(self):
        """The chosen characters Glyph Compose can build."""
        if self.package is None:
            return []
        can = self.buildable_set()
        return [c for c in self.chosen_characters() if c in can]

    def build_with_diacritics(self):
        QtCore, QtGui = _qt()
        chars = self.buildable_checked()
        if not chars:
            return
        if not self.checked_listed():  # built from the selected row: its check follows
            for item in self.shown_tree().selectedItems():
                if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                    item.setCheckState(0, QtCore.Qt.Checked)
        i = lambda text: self.in_list_font(self.ak.i(text))  # (letters named in a message: italics, in FreeLang)
        try:
            dm = self.diacritics_module()
            with self.ak.opening_from(self.dialog):  # (on this window's font, in its place)
                try:
                    dm.main(characters=chars)  # a Glyph Compose that lists the letters given only
                    self.log.add(self.tool_links(u"<i>Glyph Compose</i> lists %s, ticked: review them there, then "
                                                 u"build." % i(u" ".join(chars))), "done")
                except TypeError:
                    dm.main()  # (a Glyph Compose that takes no letters lists every one it can build)
                    self.log.add(self.tool_links(u"<i>Glyph Compose</i> lists every glyph with diacritics it can "
                                                 u"build, %s among them." % i(u" ".join(chars))), "done")
        except Exception as exc:
            self.log.add(self.tool_links(self.ak.error_sentence(u"<i>Glyph Compose</i> did not open", exc)), "error")

    def build_spaces(self, chars):
        """The spaces the font lacks (the log's spaces line, its Glyph Compose clicked) handed to Glyph Compose
        as Build with Glyph Compose hands glyphs over: it opens on its Glyph generation tab, which lists them
        alone, ticked (owner's image 313: the plain link opened it on its first tab, with nothing done)."""
        try:
            dm = self.diacritics_module()
            with self.ak.opening_from(self.dialog):  # (on this window's font, in its place)
                dm.main(characters=list(chars))
            self.log.add(self.tool_links(u"<i>Glyph Compose</i> lists %s on its <i>Glyph generation</i> tab, ticked: "
                                         u"<i>Build ticked glyphs</i> adds %s." % (
                                             self.ak.b(counted(len(chars), u"space")),
                                             u"it" if len(chars) == 1 else u"them")), "done")
        except Exception as exc:
            self.log.add(self.tool_links(self.ak.error_sentence(u"<i>Glyph Compose</i> did not open", exc)), "error")

    def copy_characters(self):
        QtCore, QtGui = _qt()
        chars = self.chosen_characters()
        if not chars:
            return
        try:
            QtGui.QApplication.clipboard().setText(u" ".join(chars))
            self.log.add(u"Copied %s." % self.in_list_font(self.ak.i(u" ".join(chars))), "done")
        except Exception as exc:
            self.log.add(u"Could not copy: %s" % self.ak.html(exc), "error")

    # -- Vertical metrics ---------------------------------------------------------

    def extents(self, tab):
        """[Extent] of every glyph with ink, in every master; the top row's bar moved meanwhile (it raises
        ak.Stopped when the user asked to stop)."""
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
                    self.ak.busy_progress(self, None, done / float(total or 1))
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
        self.busy, stopped = True, False
        ak.busy_start(self, u"Measuring the glyphs")  # (the window's top row: stoppable, owner's image 180)
        try:
            m = read_metrics(self.package)
            if not m.upm:
                m.upm = float(self.package.upm)
            extents = self.extents(tab)
            codes = set(code for name, glyph_codes_ in self.glyphs() for code in glyph_codes_)
            capitals = has_capitals(codes)
            findings = check_metrics(m, extents, capitals)
        except ak.Stopped:
            stopped = True
        except Exception as exc:
            tab.status.setText(u"")
            self.log.add(ak.html(exc), "error")
            return
        finally:
            self.busy = False
            ak.busy_end(self)
        if stopped:  # (as if not checked: the view empty, checked again when shown or on Check)
            self.clear_metrics()
            self.stale.add("metrics")
            self.log.add(u"The vertical metrics check was stopped: nothing is listed. Click <i>Check</i> to check "
                         u"them again.", "warning")
            self.update_buttons()
            return
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
        several = len(self.master_names())
        text = u"%s clipped on Windows, %s, %s." % (
            b(counted(clipped, u"glyph")), b(counted(warnings, u"warning")),
            u"in the font's single master" if several == 1 else u"across %s" % b(counted(several, u"master")))
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
            notes = extreme_notes(self.extents_found)  # (the highest and the lowest, said so: owner's image 215)
            for p in pictures:
                if p is not None:
                    p.note = notes.get(p.name, u"")
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
        """A check about glyphs: those glyphs selected among the clipped ones, and named in the log, each a
        link that opens it in a Glyph window (the owner's report 137: a glyph reaching below the line's
        descender is not clipped, so the click selected nothing, and the line did not say which glyph)."""
        if self.filling:
            return
        index = self.index_of(self.selected_item(self.checks_tree))
        if not 0 <= index < len(self.check_rows) or not self.check_rows[index].glyphs:
            return
        line = self.check_rows[index]
        try:
            self.log.add(u"%s: %s." % (self.ak.html(line.text), self.ak.glyph_name_links(line.glyphs)))
        except Exception:
            pass
        names = set(line.glyphs)
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
            item.setToolTip(self.tip(u"%s%s: %s." % (c.extent.name, u" in %s" % c.extent.master if several else u"",
                                                     u" and ".join(sides))))
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

    def package_id(self, package):
        """(fontgate id, font key) of an open font: the key alone (its path, or its family name while
        unsaved) is the same for two unsaved fonts of one name; the id (fgPackage.id) tells open fonts
        apart, the same through every Python wrapper of one font (found live), whereas the wrappers
        themselves differ at each read."""
        try:
            number = int(package.fgPackage.id)
        except Exception:
            number = None
        return (number, self.ak.font_key(package))

    def same_font(self):
        """True while the font checked is still the current one; else the view is checked again."""
        current = self.current_font()
        if current is not None and self.package is not None and self.package_id(current) == self.package_id(self.package):
            return True
        self.log.add(u"The font changed since the check: checked again. Nothing was written.", "warning")
        self.stale = set(TABS)
        self.check(self.current_key())
        return False

    def begin_info_write(self, package, title):
        """before_changes for a write to the font info (begin_write: False, said in the log, when nothing may
        be written). The font info is the font's own state, but the step notify_changed makes records the
        whole font, its glyphs too, which have no state of their own in a font opened afresh: undoing such a
        step made FontLab print "We have a problem with the component 'P' in glyph 'Rho:Regular'" for each
        glyph built from components (owner's image 336, a kerning write's)."""
        return self.ak.begin_write(self.fontlab, package, title, self.log)

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
        if not self.begin_info_write(self.package, u"FreeLab Font Check: vertical metrics"):
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
            # (the font info only: the font's own state, which needs no before_changes, and no glyph added)
            self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Font Check: vertical metrics",
                                   added=False).report(self.log)
        if done:
            # (font, old values, keys written, keys that were unset before: no way to unset one is known, labels)
            unset = [s.key for s in done if s.key != "use_typo" and s.key in old and old[s.key] is None]
            self.put_back = (self.package_id(self.package), old, [s.key for s in done], unset,
                             dict((s.key, s.label) for s in done))
            self.log.add(u"Wrote %s into the font info: %s. FontLab's <i>Edit &gt; Undo</i> does not take the font "
                         u"info back: <i>Put back old values</i> does%s." % (
                             b(counted(len(done), u"value")), self.ak.html(u"; ".join(write_text(s) for s in done)),
                             u" (except a value that was not set before: it stays as written)" if unset else u""), "done")
        self.update_put_back()
        if failed:
            self.log.add(u"Not written: %s." % self.ak.html(u"; ".join(failed)), "error")
        self.check_vertical()

    def update_put_back(self):
        """Put back old values: clickable while the font written to is the one checked."""
        held = getattr(self, "put_back", None)
        self.ak.enable(self.put_back_button, bool(held) and self.package is not None
                       and self.package_id(self.package) == held[0])

    def put_back_values(self):
        """The font info as it was before the last write (FontLab's History does not cover it), into the
        font written to only, while it is the current one. A value that was not set before stays as
        written (no way to unset a font info value is known): the log names it. A value FontLab refused
        to take back stays held, for another click."""
        held = getattr(self, "put_back", None)
        if not held:
            return
        current = self.current_font()
        if current is None or self.package_id(current) != held[0]:
            self.log.add(u"The font written to is not the current one: nothing was put back.", "warning")
            self.update_put_back()
            return
        ident, old, keys, unset, labels = held
        if not self.begin_info_write(current, u"FreeLab Font Check: vertical metrics put back"):
            return
        fields = dict(INFO_FIELDS)
        info = current.fgPackage.info
        restored, failed, left, kept = [], [], [], []
        for key in keys:
            label = labels.get(key, key)
            if key in unset:
                try:
                    now = getattr(info, fields[key])
                    now = u"%d" % round_units(float(now)) if now is not None else u"nothing"
                except Exception:
                    now = u"?"
                left.append(u"%s was not set before; set to %s now: clear it in Font Info if you want it unset" % (label, now))
                continue
            if key not in old:
                left.append(u"%s (its old value could not be read)" % label)
                continue
            try:
                if key == "use_typo":
                    info.openTypeOS2Selection = old[key]
                else:
                    setattr(info, fields[key], float(old[key]))
                restored.append(key)
            except Exception as exc:
                failed.append(u"%s (%s)" % (label, exc))
                kept.append(key)
        self.put_back = (ident, old, kept, [], labels) if kept else None
        if restored or failed:
            self.ak.notify_changed(self.fontlab, current, u"FreeLab Font Check: vertical metrics put back",
                                   added=False).report(self.log)
        b = self.ak.b
        if restored:
            self.log.add(u"Put back %s as %s." % (b(counted(len(restored), u"value")),
                                                  u"it was" if len(restored) == 1 else u"they were"), "done")
        if left:
            self.log.add(u"Not put back: %s." % self.ak.html(u"; ".join(left)), "warning")
        if failed:
            self.log.add(u"Not put back (FontLab refused; <i>Put back old values</i> tries again): %s." % self.ak.html(
                u"; ".join(failed)), "warning")
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
        self.busy, stopped = True, False
        ak.busy_start(self, u"Comparing the masters")  # (the window's top row: stoppable, owner's image 180)
        found, unread = [], []
        try:
            glyphs = self.glyphs()
            for done, (name, _) in enumerate(glyphs):
                if done % PROGRESS_EVERY == 0:
                    ak.busy_progress(self, None, done / float(len(glyphs) or 1))
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
        except ak.Stopped:
            stopped = True
        except Exception as exc:
            tab.status.setText(u"")
            self.log.add(ak.html(exc), "error")
            return
        finally:
            self.busy = False
            ak.busy_end(self)
        if stopped:  # (as if not compared: the view empty, compared again when shown or on Compare masters)
            self.clear_masters()
            self.stale.add("masters")
            self.log.add(u"The masters' comparison was stopped: nothing is listed. Click <i>Compare masters</i> to "
                         u"compare them again.", "warning")
            self.update_buttons()
            return
        self.problems = tab.findings = found
        self.fill_chips()
        self.fill_glyphs()
        text = masters_status(len(set(f.glyph for f in found)), len(glyphs), len(masters), reference, len(unread), b)
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
        self.ak.quiet_list(tree, True)
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
            self.ak.quiet_list(tree, False)
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

    def show_beside(self, on):
        """The choice of the master drawn beside the one compared with, shown only while a glyph is drawn:
        "Beside it" stood under an empty frame, with no font or nothing compared (owner's image 211)."""
        for widget in (self.beside_label, self.compare_master):
            try:
                widget.setVisible(bool(on))
            except Exception:
                pass

    def draw_comparison(self):
        if self.filling:
            return
        name = self.selected_glyph()
        if name is None or self.package is None:
            self.comparison.clear()
            self.problem_label.setText(u"")
            self.show_beside(False)
            return
        self.show_beside(bool(self.compare_masters))
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
        done, failed, touched = [], [], []  # (done and failed: the log's rich text, each glyph's name a link)
        link, html = ak.glyph_name_link, ak.html
        if not ak.begin_write(self.fontlab, self.package, u"FreeLab Font Check: masters", self.log):
            return  # (nothing fixed: the reason in the log)
        self.busy = True
        # (the top row's bar for many glyphs; a write, one step of FontLab's History: never stopped half way,
        # what was clicked meanwhile done once it is over)
        ak.busy_start(self, u"Fixing the glyphs", stoppable=False)
        try:
            for at, name in enumerate(names):
                ak.busy_progress(self, None, at / float(len(names)), stoppable=False)
                glyph = self.package.findName(name)
                reference_layer = self.layer(name, reference)
                original = read_outline(reference_layer) if reference_layer is not None else None
                if glyph is None or original is None:
                    failed.append(u"%s: no layer in %s to match" % (link(name), html(reference)))
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
                            link(name), html(master), html(reference)))
                        continue
                    if glyph not in touched:
                        touched.append(glyph)
                    try:
                        apply_fix(layer, plan)
                    except Exception as exc:
                        failed.append(u"%s in %s: %s" % (link(name), html(master), html(exc)))
                        continue
                    if same_outline(read_outline(layer), apply_plan(outline, plan)):
                        done.append(u"%s in %s (%s)" % (link(name), html(master), html(u"; ".join(plan_steps(plan, reference)))))
                    else:
                        failed.append(u"%s in %s: it did not read back as planned (%s), look at it" % (
                            link(name), html(master), html(u"; ".join(plan_steps(plan, reference)))))
                if not same_outline(read_outline(reference_layer), original):
                    failed.append(u"%s in %s: the master compared with changed too (a shared element?)" % (
                        link(name), html(reference)))
        except Exception as exc:
            failed.append(html(u"%s" % exc))
        finally:
            self.busy = False
            ak.busy_end(self)
        status = ak.WriteStatus()
        if touched:
            status = ak.notify_changed(self.fontlab, self.package, u"FreeLab Font Check: masters", touched, added=False)
        undo = status.undo(u" <i>Edit &gt; Undo</i> takes %s back." % (u"it" if len(touched) == 1 else u"them")
                           if touched else u"")
        if done:
            shown = done[:20] + ([u"%d more" % (len(done) - 20)] if len(done) > 20 else [])
            self.log.add(u"Fixed %s: %s.%s" % (b(counted(len(done), u"glyph layer")), u"; ".join(shown), undo),
                         "done")
        if failed:
            self.log.add(u"Not fixed: %s.%s" % (u"; ".join(failed[:20]), u"" if done else undo), "error")
        if not done and not failed:
            self.log.add(u"Nothing to fix: the masters already match where Font Check can set them right.")
        status.report(self.log)
        selected = self.selected_glyph()
        self.stale.add("metrics")
        self.check_masters()
        after = [f for f in self.problems if (f.glyph, f.master, f.kind, f.contour) not in before]
        elsewhere = sorted(set(f.glyph for f in after if f.glyph not in names))
        if elsewhere:
            self.log.add(u"New problems in %s since the fix (a shared element changed with it?): %s." % (
                b(counted(len(elsewhere), u"other glyph")), u", ".join(link(g) for g in elsewhere[:20])), "warning")
        left = sorted(set(f.glyph for f in self.problems if f.glyph in names))
        designer = [g for g in left if g not in self.fixable_names]
        if designer:
            self.log.add(u"%s still %s problems that need the designer: %s." % (
                b(counted(len(designer), u"glyph")), u"has" if len(designer) == 1 else u"have",
                u", ".join(link(g) for g in designer[:20])), "warning")  # (what the font still does wrong: amber)
        unfixed = [g for g in left if g in self.fixable_names]
        if unfixed:
            self.log.add(u"%s still %s problems Font Check can set right: %s. Look at %s in a <i>Glyph</i> window." % (
                b(counted(len(unfixed), u"glyph")), u"has" if len(unfixed) == 1 else u"have",
                u", ".join(link(g) for g in unfixed[:20]), u"it" if len(unfixed) == 1 else u"them"), "warning")
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
        """FontLab text for what the button opens: in Coverage, the checked characters of the tab shown,
        or the selected row's, or, with neither, the missing characters of what is selected at the right
        (FontLab shows the ones the font has not as placeholders); else a glyph between the font's H's
        (n's, o's). A double-click on a row opens that row alone (character_double_clicked)."""
        if self.package is None:
            return u""
        key = self.current_key()
        if key == "coverage":
            chosen = self.chosen_characters()
            return u"".join(chosen) if chosen else self.selection_glyph_text()
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
        self.open_glyph_text(self.glyph_window_text())

    def log_link(self, target):
        """A glyph named in a log line clicked: opened in a Glyph window; the spaces line's Glyph Compose
        clicked: opened on those spaces (build_spaces). A link this window does not take is left to the log
        (False)."""
        if u"%s" % target == DECLARE_LINK:
            if self.package is not None:
                self.declare_coverage()
            return True
        spaces = linked_spaces(target)
        if spaces is not None:
            if self.package is None or not spaces:
                return True  # (no font: nothing to build them in; the link is this window's all the same)
            self.build_spaces(spaces)
            return True
        name = self.ak.linked_glyph_name(u"%s" % target)
        if not name or self.package is None:
            return False
        if self.ak.glyph_of_link(self.package, u"%s" % target) is None:  # (taken out since the line was written)
            self.log.add(u"The font does not have that glyph now.", "warning")
            return True
        self.open_glyph_text(u"/%s" % name)
        return True

    def open_glyph_text(self, text):
        """A Glyph window opened on a text (FontLab's own syntax); a failure goes to the log."""
        if self.package is None or not text:
            return
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open a <i>Glyph</i> window: %s" % self.ak.html(error), "error")

    def show(self):
        QtCore, QtGui = _qt()
        self.stepwise = True  # (a window shown: long work goes step by step, the window repainted in between)
        if self.package is not None:
            # It opens on a blank page, not on empty lists; the check starts from a zero timer, once the window
            # is shown and painted, its first step's name and bar in the window's top row (set_busy)
            try:
                self.coverage_stack.setCurrentIndex(0)
            except Exception:
                pass
        self.dialog.show()
        self.dialog.raise_()
        if self.package is not None:
            self.opening = lambda: self.check(self.current_key())  # (kept: checked as it opens)
            QtCore.QTimer.singleShot(0, self.opening)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("Font Check"):
            return
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
    try:
        dialog.ak.take_window("Font Check", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_font_check":
    main()
