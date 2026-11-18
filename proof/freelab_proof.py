#FLM: Proof
# -*- coding: utf-8 -*-
"""FreeLab Proof, from FontLab's Scripts menu: a PDF proof of the current font, drawn from its own
outlines.

FontLab 9 has a Notepad panel for specimens and PDF proofs; FontLab 7 has none. Proof lays the
font's glyphs out as they are in FontLab (nothing exported, nothing installed): a summary of the font
(its names, metrics, features, and the languages it covers, as Font Check counts them), then a
character set, waterfalls, text in each script the font covers, kerning strings, spacing strings,
diacritics, and figures and punctuation, for the current master or each master, with a header and a
footer on each page. Kerning is applied as FontLab applies it (classes resolved). OpenType features are not: no
ligatures, no contextual or localized forms, no mark positioning; each character shows its own glyph.

Valid Python 2.7 (FontLab 7) and Python 3. Everything above the Qt line needs no Qt and no FontLab.
The drawing below it takes Qt's modules as arguments, so the same code draws in FontLab (PythonQt)
and offline (PySide6).
"""

from __future__ import absolute_import, division, print_function

import bisect
import json
import math
import os
import re
import sys
import time
import unicodedata

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
LANGUAGES_FILE = "language_coverage.json"  # Font Check's orthographies (from Hyperglot), beside this script once installed
PAGE_SIZES = (("A4", u"A4", (595.276, 841.89)), ("Letter", u"US Letter", (612.0, 792.0)))  # in points
MARGIN = 42.0  # points around a page's content
HEADER_ROOM = 22.0  # points between the margin and the content, for the header (and the footer)
SECTION_GAP = 18.0  # points above a section that starts on a page already begun
SECTION_ROOM = 0.3  # a section starts on the page begun when at least this share of the page is left
LABEL_WIDTH = 36.0  # points left of a waterfall's or a paragraph's lines, for their size
SECTIONS = (("charset", u"Character set"), ("waterfall", u"Waterfall"), ("text", u"Text"),
            ("kerning", u"Kerning strings"), ("spacing", u"Spacing strings"), ("diacritics", u"Diacritics"),
            ("figures", u"Figures and punctuation"))
TITLES = dict(SECTIONS, summary=u"Summary", about=u"About this proof", info=u"Font info", masters=u"Masters",
              coverage=u"Language coverage")
FONT_CHECK_FILE, FONT_CHECK_MODULE = "freelab_font_check.py", "freelab_font_check"
FEATURE_CODE_FILE, FEATURE_CODE_MODULE = "freelab_feature_code.py", "freelab_feature_code"
SETTINGS_FILE = u"proof.json"  # in FreeLab's settings folder (ak.state_dir()): the summary's two settings
# What the summary lists of the languages, after their counts (the dropdown's items, after "Summary lists:":
# capitalized, as every dropdown's in the label form, owner's image 271)
SUMMARY_LANGUAGES = (("covered", u"Covered languages"), ("reach", u"Covered languages and those within reach"),
                     ("none", u"No languages (counts only)"))
SUMMARY_TITLE_SIZE = 30  # points: the family's name, in the font itself
SUMMARY_TITLE_MIN = 12  # ... made smaller, down to this, for a name wider than the page
SUMMARY_COLUMNS = 5  # the languages' names, in columns
SUMMARY_NAME_SIZE = 6.5  # points: a language's name
SUMMARY_NAME_LEADING = 8.2  # points from a name's line to the next
SUMMARY_MIN_ROWS = 3  # rows of names at least under a heading at a page's foot
SUMMARY_METRIC_COLUMN = 64.0  # points: a column of the vertical metrics' table
WATERFALL_SIZES = (8, 9, 10, 11, 12, 14, 16, 18, 21, 24, 28, 32, 36, 48, 60, 72)
TEXT_SIZES = (9, 11, 14)
SIZE_RANGE = (4, 288)  # points: sizes typed outside this are left out
GRID_COLUMNS = 10  # glyphs per row of the character set
CELL_SHARE = 1.35  # a character set cell's height, of its width
STRING_SIZE = 18  # points: kerning and spacing strings
SHOWCASE_SIZE = 28  # points: diacritics, figures, and punctuation
MASTERS_SIZES = (28, 12)  # points: each master's line on the masters page
STRING_GAP = 0.6  # of the em, between two strings
LINE_SHARE = 1.25  # a line is at least this many times its size tall
SCOPE_LANGUAGES_TOP = 20  # languages the Proof dropdown lists to start with, the most spoken first
SCOPE_LANGUAGES_SLACK = 4  # ... and up to this many more, listed at once: an entry that opens so few says little
MORE_LANGUAGES = u"More languages\N{HORIZONTAL ELLIPSIS}"  # the dropdown's entry that lists the others
MORE = ("more", None)  # its scope: no proof's, the list filled out
MAX_SAMPLES = 6  # languages per script in the text section, the most spoken first
SCRIPT_MINIMUM = 5  # a script's letters the font needs before its letters stand in for its text
ALPHABET_MAX = 120  # characters at most, when a script's letters stand in for its text
WATERFALL_MIN = 120  # characters of sample text the waterfall wants (it is cut at the page's edge)
ALL_MASTERS = u"All masters"
NOTE = u"Kerning applied; OpenType features not applied"
KERNING_SETS = (("all", u"Every kerned pair"), ("common", u"Common pairs only"))
# The window's line while no font is open, on one line (ak.one_line; owner's image 278), "hooks to" as the
# shared NO_FONT_LINE
NO_FONT_LINE = u"No font is open. This window hooks to the next font you open, and lays out its proof at once."
NOT_AVAILABLE = u"n/a"  # a dropdown that lists the font's content, with no font (grayed: owner's images 289 and 290)
COLOR_MODES = (("window", u"As the window"), ("print", u"Print (black on white)"))
PRINT_COLORS = ((0, 0, 0), (255, 255, 255))  # (ink, paper)
DARK_COLORS = ((235, 235, 235), (30, 30, 30))  # the second choice beside a light window: light on dark
INFO_LABEL_WIDTH = 110.0  # points left of the font info's values, for their names
INFO_TEXT_MAX = 1200  # characters of one font info field shown (a license's whole text is cut)

# Sample texts, each used when the font covers its language (Hyperglot's base characters) and has
# every character of the text. The pangrams were written for FreeLab and are GPL-3 with the code:
# each holds every base letter Hyperglot lists for its language (tests/proof_tests.py lists any one
# missing), in a sentence a reader of the language finds plausible, foreign letters in names and
# loanwords. Kept from the public domain: the English pangram (in print since 1885), the opening line
# of Nguyen Du's Truyen Kieu (1820) for Vietnamese, and the Iroha (11th century), in hiragana and in
# katakana.
SAMPLES = (
    ("eng", "Latin", u"The quick brown fox jumps over the lazy dog."),
    ("spa", "Latin", u"¡Qué extraño! ¿Sabías que Félix, el joven pingüino, bebió zumo de kiwi y whisky con un ñandú "
                     u"en Panamá?"),
    ("por", "Latin", u"No sábado à noite, o avô Kiko lê Molière e ouve Niccolò Paganini, enquanto a avó Júlia, de "
                     u"pijama, põe gelo no whisky e faz um lanche de tâmaras e maçã: é a vida da família, sem luxo."),
    ("deu", "Latin", u"Jörg fährt mit Xaver zum quirligen Yachthafen, wo beide bei Kälte Punsch aus großen Krügen "
                     u"trinken."),
    ("fra", "Latin", u"Où dîne Lætitia\N{NO-BREAK SPACE}? À L’Haÿ-les-Roses, chez sa sœur Zoé, qui fête Noël "
                     u"et ses fiançailles avec Saül\N{NO-BREAK SPACE}: bœuf rôti, maïs, crêpes au goût exquis et "
                     u"whisky âgé, au jardin de son père."),
    ("ita", "Latin", u"Perché Fabrizio partì da Bogotá e andò a Córdoba, Medellín e Cancún? Laggiù c’è più quiete, e "
                     u"il mare si vede già da lì."),
    ("vie", "Latin", u"Trăm năm trong cõi người ta, chữ tài chữ mệnh khéo là ghét nhau."),
    ("tur", "Latin", u"Xavier ile Quentin, Wi-Fi şifresini hâlâ bulamayınca sükûnetle çay içip garajda millî maçı "
                     u"göz kırpmadan izlediler; doğrusu güzel bir geceydi."),
    ("pol", "Latin", u"W piątek Xawery przyjechał starym volvo do Łodzi na fajny quiz, zjadł gorący żurek, wypił "
                     u"herbatę z cytryną i chciał śpiewać do późna, choć słońce już zaszło."),
    ("nld", "Latin", u"Na de reünie in België fêteerde de naïeve zoöloog Max zijn gasten aan de Côte d’Azur op crème "
                     u"brûlée, pâté, whisky en een quiz. Wie wilde hem dáár naäpen? Ík niet, en jij óók niet; ú "
                     u"misschien?"),
    ("ron", "Latin", u"Vesel, șoferul de taxi Ștefan a băut un whisky cu gheață, a mâncat kiwi și a câștigat premiul "
                     u"unui quiz la New York, în fața jurnaliștilor."),
    ("hun", "Latin", u"Az őszülő, jókedvű Xavér egy pohár whiskyt ivott, és egy Quimby-dalt dúdolt, míg az utcán "
                     u"hűvös nyári szél fújt."),
    ("ces", "Latin", u"Ó, jak úžasné: Láďa, dobrý kuchař z Plzně, upekl v neděli quiche a žluťoučkou bábovku a "
                     u"uvařil guláš; Xénie mu zahrála píseň na flétnu a pak vypili půl lahve whisky."),
    ("swe", "Latin", u"Inför resan till Málaga åt Quentin müsli, drack whisky och köpte i Växjö två biljetter à "
                     u"femtio kronor till ett idéseminarium med Zoë."),
    ("isl", "Latin", u"Ýmsir gestir, þar á meðal Quentin, Zoe, Wolfgang og Cecilía, borðuðu lax, skyr, brauð og kæfu úti "
                     u"við fjörðinn hjá Pétri á sólríkum degi."),
    ("dan", "Latin", u"Quizværten Jørgen cyklede forbi Zoologisk Have med whisky, vaffelis og en xylofon på "
                     u"bagagebæreren."),
    ("hrv", "Latin", u"Max i Đuro gledali su u centru New Yorka film Quentina Tarantina, a navečer su zajedno uz "
                     u"hladno pivo jeli ražnjiće i burek sa špinatom."),
    ("cat", "Latin", u"Algú diu que la veïna, feliç després de l’òpera, va menjar kiwis i xocolata a la plaça, va "
                     u"beure cafè i whisky i també va cantar una cançó al pingüí del zoo, allà mateix."),
    ("lit", "Latin", u"Ryte Ąžuolas telefonu nuskenavo QR kodą, prisijungė prie Wi-Fi ir žaidė Xbox, o močiutė, "
                     u"grįžusi iš vaikų choro šventės, glostė katę, gėrė kavą su citrina ir valgė sūrį bei zefyrą."),
    ("rus", "Cyrillic", u"Шустрый ёжик вечером в цирке объелся пюре из фиников с хрустящей жимолостью, а эхо глухо "
                        u"вздыхало."),
    ("ukr", "Cyrillic", u"Юна ґава з’їла щедрий шматок цибулевого пирога, а їжак у фартусі пив чай із вишнями й "
                        u"хутко казав, що сьогодні в нього є свято."),
    ("ell", "Greek", u"Ο γέρος βοσκός ταΐζει τα ζώα, χαϊδεύει το ξανθό σκυλί, τρώει φρέσκο ψωμί και πίνει ζεστό τσάι "
                     u"του βουνού, που πραΰνει ήσυχα την αϋπνία του."),
    ("hye", "Armenian", u"Այդ օրը Երևանում փոքր աղջիկը ճաշին ժպտալով կերավ ձուկ, պանիր, չամիչ և ծիրան, խմեց զով թեյ, "
                        u"իսկ հայրը գինի էր խմում ու ռադիոյով լսում ֆուտբոլի հաշիվը։"),
    ("heb", "Hebrew", u"בקיץ, הילד הנבון שלך נסע עם אבא לחוף, ושם קיבל תפוח טעים וגזר מזקן חביב שהיה לו כלב צהוב."),
    ("jpn", "Hiragana", u"いろはにほへと ちりぬるを わかよたれそ つねならむ うゐのおくやま けふこえて あさきゆめみし ゑひもせす"),
    ("jpn", "Katakana", u"イロハニホヘト チリヌルヲ ワカヨタレソ ツネナラム ウヰノオクヤマ ケフコエテ アサキユメミシ ヱヒモセス"),
    ("kor", "Hangul", u"토요일 아침, 키 큰 여행자가 푸른 바다 앞 야자수 그늘에서 휴식을 즐겼다."),
)
# Scripts whose text needs no shaping (each character its own glyph, in order); the others (Arabic,
# the Indic scripts, Thai...) are left out of the text section, and said so.
TEXT_SCRIPTS = ("Latin", "Greek", "Cyrillic", "Armenian", "Georgian", "Hebrew", "Hiragana", "Katakana", "Hangul",
                "Kanji", "Chinese", "Hanja")
RTL_SCRIPTS = ("Hebrew",)
# The code points of the right-to-left scripts: the blocks Unicode gives a right-to-left bidirectional
# class (R or AL) by default (DerivedBidiClass.txt: Hebrew, Arabic, Syriac, Thaana, N'Ko, Samaritan,
# Mandaic, their presentation forms, and the historic and newer right-to-left scripts of plane 1:
# Phoenician, Kharoshthi, Old South Arabian, Avestan, Old Turkic, Old Hungarian, Hanifi Rohingya,
# Yezidi, Sogdian, Old Uyghur, Mende Kikakui, Adlam...), without the numbers in them, which a
# right-to-left text sets left to right (Arabic-Indic digits, the Rumi numerals). A table, not the
# interpreter's Unicode data: FontLab's Python 2.7 knows Unicode 5.2, and on its narrow build it cannot
# read a character past U+FFFF at all, so the direction would have depended on the interpreter.
RTL_RANGES = ((0x0590, 0x08FF), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFC), (0x10800, 0x10FFF), (0x1E800, 0x1EFFF))
RTL_NUMBER_RANGES = ((0x0600, 0x0605), (0x0660, 0x066C), (0x06DD, 0x06DD), (0x06F0, 0x06F9), (0x0890, 0x0891),
                     (0x08E2, 0x08E2), (0x10D30, 0x10D39), (0x10E60, 0x10E7E))
# Scripts written top to bottom (in columns, left to right) whose letters this proof sets horizontally,
# left to right, as Unicode encodes them and as FontLab shows them: their letters' code points. The
# proof says so (vertical_scripts); vertical setting is not done.
VERTICAL_SCRIPTS = ((u"Mongolian", ((0x1820, 0x18AA),)), (u"Phags-pa", ((0xA840, 0xA873),)))
UNSPACED_SCRIPTS = ("Hiragana", "Katakana", "Kanji", "Chinese", "Hanja")  # lines may break between any two characters
HAN_SCRIPTS = ("Kanji", "Chinese", "Hanja")


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the shared helpers."""
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


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

def grouped(number):
    """13932 as "13,932"."""
    return u"{:,}".format(number)


def counted(number, one, many=None):
    """"1 page", "2 pages": a count with its noun in the right number."""
    return u"%s %s" % (u"{:,}".format(number), one if number == 1 else (many or one + u"s"))


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


def _in_ranges(code, ranges):
    return any(low <= code <= high for low, high in ranges)


def is_rtl_code(code):
    """Whether a code point is of a right-to-left script (RTL_RANGES), its numbers apart."""
    return _in_ranges(code, RTL_RANGES) and not _in_ranges(code, RTL_NUMBER_RANGES)


def vertical_scripts(font):
    """The names of the scripts written top to bottom that the font has letters of (VERTICAL_SCRIPTS):
    the proof sets them horizontally, and says so."""
    codes = [code for code, name in font.cmap.items() if font.has(name)]
    return [script for script, ranges in VERTICAL_SCRIPTS if any(_in_ranges(code, ranges) for code in codes)]


def char_name(code):
    """A character's Unicode name, by the running Python's data: u"" where it has none (unnamed, newer
    than its Unicode, or past U+FFFF on a narrow build, where the character is two UTF-16 units)."""
    try:
        return unicodedata.name(char_of(code))
    except Exception:
        return u""


# A glyph's kind (letter, figure, mark, punctuation...) and a letter's script come from Unicode 17.0's
# general categories and the first words of the letters' names, kept in Font Check's character_sets.json
# ("categories", made by checks/train/character_sets.py from the pinned UnicodeData.txt), not from the
# running Python's data: FontLab's Python 2.7 knows Unicode 5.2, so letters encoded since (Adlam,
# Georgian's Mtavruli, Tai Yo) were unassigned there, and a Latin-only proof kept them as it keeps
# punctuation. (Its narrow build holds a character past U+FFFF as two UTF-16 units: its unicodedata
# reads such a pair as one character, 2.7.18 probed, but a loop over a text's characters splits it, so
# texts are read by code_points.)
# A sign that is no letter (a digit, a mark, a punctuation mark, a symbol) belongs to the script Unicode's
# Script property gives it (Scripts.txt, Unicode 17.0: the "scripts" of the same file, each script's own
# characters), Common and Inherited ones (the ASCII digits, common punctuation, combining accents) to every
# script. Live (ADLaM Display, 2026-11-15): a Latin-only proof kept Adlam's digits and its initial marks.
CATEGORIES_FILE = "character_sets.json"  # beside this script once installed, or in the repository's checks/
_CATEGORIES = []  # the table, read when first asked (categories_table): (lows, [(low, high, category, word)])
_SCRIPTS = []  # the scripts' own characters, read with it (scripts_table): (lows, [(low, high, script)])
_SCRIPT_WORDS = {}  # {script: the words Proof names its letters by}, made when first asked (script_words)


def categories_path():
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    for path in (os.path.join(here, CATEGORIES_FILE), os.path.join(here, os.pardir, "checks", CATEGORIES_FILE)):
        if os.path.isfile(path):
            return path
    return None


def load_unicode_tables(path=None):
    """(categories, scripts) of character_sets.json, each as (lows, rows) for bisection, or None without
    the file or the table: categories' rows (low, high, category, the first word of a letter's name or
    None), the scripts' (low, high, script's name), the script's own characters (Common and Inherited are
    no script there)."""
    path = path or categories_path()
    if not path:
        return None, None
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
    except Exception:
        return None, None
    categories = scripts = None
    try:
        words = [u"%s" % word for word in data["categories"]["words"]]
        rows = []
        for part in data["categories"]["runs"].split():
            fields = part.split(u":")
            low, _, high = fields[0].partition(u"-")
            low = int(low, 16)
            rows.append((low, int(high, 16) if high else low, u"%s" % fields[1],
                         words[int(fields[2])] if len(fields) > 2 else None))
        categories = ([row[0] for row in rows], rows)
    except Exception:
        pass
    try:
        rows = []
        for row in data["scripts"]["rows"]:
            for part in (row[1] or u"").split():
                low, _, high = part.partition(u"-")
                rows.append((int(low, 16), int(high or low, 16), u"%s" % row[0]))
        rows.sort()
        scripts = ([row[0] for row in rows], rows) if rows else None
    except Exception:
        pass
    return categories, scripts


def load_categories(path=None):
    """The table of general categories of character_sets.json (load_unicode_tables)."""
    return load_unicode_tables(path)[0]


def _read_tables():
    if not _CATEGORIES or not _SCRIPTS:
        categories, scripts = load_unicode_tables()
        if not _CATEGORIES:
            _CATEGORIES.append(categories)
        if not _SCRIPTS:
            _SCRIPTS.append(scripts)


def categories_table():
    _read_tables()
    return _CATEGORIES[0]


def scripts_table():
    _read_tables()
    return _SCRIPTS[0]


def _looked_up(table, code):
    """The row of a table (lows, rows) that holds code, or None."""
    if table is None:
        return None
    lows, rows = table
    at = bisect.bisect_right(lows, code) - 1
    return rows[at] if at >= 0 and code <= rows[at][1] else None


def code_script(code):
    """The script Unicode's Script property gives a code point, by its name (u"Adlam", u"Latin"); None for
    Common and Inherited (shared by every script), unassigned, or without the table."""
    row = _looked_up(scripts_table(), code)
    return row[2] if row is not None else None


def script_words(script):
    """The words Proof names a script's letters by (script_case: u"ADLAM"; u"CJK" for Han; u"HIRAGANA" and
    u"HENTAIGANA" for Hiragana), NOT_SCRIPTS left out; a script without letters, its name's first word in
    capitals. A frozenset."""
    if not _SCRIPT_WORDS:
        found = {}
        table = categories_table()
        for low, high, kind, word in (table[1] if table is not None else ()):
            if word and word not in NOT_SCRIPTS:
                name = code_script(low)
                if name is not None:
                    found.setdefault(name, set()).add(word)
        _SCRIPT_WORDS.update((name, frozenset(words)) for name, words in found.items())
        _SCRIPT_WORDS[None] = frozenset()  # (made)
    words = _SCRIPT_WORDS.get(script)
    if words is None:
        parts = (script or u"").replace(u"_", u" ").split()
        words = frozenset([parts[0].upper()]) if parts else frozenset()
    return words


def sign_scripts(code):
    """The script words (script_words) of a code point that is no letter (a digit, a mark, a punctuation
    mark, a symbol) whose Script property is one script's (Adlam's digits and initial marks); None for a
    letter (script_case says), for a sign every script shares (Common, Inherited: the ASCII digits, common
    punctuation), and without the table."""
    found = unicode_class(code) if code is not None else None
    if found is None or found[0].startswith(u"L"):
        return None
    script = code_script(code)
    return script_words(script) if script is not None else None


def unicode_class(code):
    """(general category, first word of a letter's name or None) of a code point, by the table (Unicode
    17.0); without it, by the running Python where it can read the character. None: unassigned, or
    unknown to the data at hand (never taken for punctuation or a symbol)."""
    table = categories_table()
    if table is not None:
        lows, rows = table
        at = bisect.bisect_right(lows, code) - 1
        if at >= 0 and code <= rows[at][1]:
            return rows[at][2], rows[at][3]
        return None
    try:
        kind = u"%s" % unicodedata.category(char_of(code))
    except Exception:  # (a narrow build's two units past U+FFFF)
        return None
    if kind == u"Cn":
        return None
    words = char_name(code).replace(u"-", u" ").split() if kind.startswith(u"L") else []
    return kind, (words[0] if words else None)


def category(code):
    """A code point's general category (unicode_class); u"Cn" when it is unassigned or unknown."""
    found = unicode_class(code)
    return found[0] if found is not None else u"Cn"


def script_case(code):
    """(script, case) of a letter, its script the first word of its Unicode name: ("LATIN", "upper"),
    ("HEBREW", None), ("SHAVIAN", None); ("FIGURE", None) for a digit; None for anything else."""
    found = unicode_class(code)
    if found is None:
        return None
    kind, word = found
    if kind == u"Nd":
        return ("FIGURE", None)
    if not kind.startswith(u"L") or not word:
        return None
    case = "upper" if kind in (u"Lu", u"Lt") else ("lower" if kind == u"Ll" else None)
    return (word, case)


def unknown_code(code):
    """Whether a code point is unassigned or unknown (unicode_class): no letter, figure, or punctuation
    mark a scope can be said to keep."""
    return code is not None and unicode_class(code) is None


def base_char(code):
    """The letter an accented letter is built on (A for Aacute, l for lslash), or None."""
    text = char_of(code)
    decomposed = code_points(unicodedata.normalize("NFD", text))  # (code points: a narrow build's pairs read as one)

    def combining(code):
        try:
            return unicodedata.combining(char_of(code))
        except Exception:
            return 0
    if len(decomposed) > 1 and not combining(decomposed[0]) and combining(decomposed[1]):
        return decomposed[0]
    name = char_name(code)
    if u" WITH " in name:
        try:
            found = code_points(unicodedata.lookup(name.split(u" WITH ")[0]))
        except (KeyError, TypeError):
            return None
        return found[0] if len(found) == 1 else None
    return None


# The letters a glyph is proofed between, by its script and case: a straight one and a round one,
# as type designers proof (H and O, n and o); figures between H and zero.
CONTROLS = {
    ("LATIN", "upper"): (u"H", u"O"), ("LATIN", "lower"): (u"n", u"o"),
    ("GREEK", "upper"): (u"\N{GREEK CAPITAL LETTER ETA}", u"\N{GREEK CAPITAL LETTER OMICRON}"),
    ("GREEK", "lower"): (u"\N{GREEK SMALL LETTER NU}", u"\N{GREEK SMALL LETTER OMICRON}"),
    ("CYRILLIC", "upper"): (u"\N{CYRILLIC CAPITAL LETTER EN}", u"\N{CYRILLIC CAPITAL LETTER O}"),
    ("CYRILLIC", "lower"): (u"\N{CYRILLIC SMALL LETTER EN}", u"\N{CYRILLIC SMALL LETTER O}"),
    ("ARMENIAN", "upper"): (u"\N{ARMENIAN CAPITAL LETTER HO}", u"\N{ARMENIAN CAPITAL LETTER OH}"),
    ("ARMENIAN", "lower"): (u"\N{ARMENIAN SMALL LETTER NOW}", u"\N{ARMENIAN SMALL LETTER OH}"),
    ("GEORGIAN", "upper"): (char_of(0x1C98), char_of(0x1C9D)),  # Mtavruli in and on (Unicode 11)
    ("GEORGIAN", None): (u"\N{GEORGIAN LETTER IN}", u"\N{GEORGIAN LETTER ON}"),
    ("HEBREW", None): (u"\N{HEBREW LETTER HE}", u"\N{HEBREW LETTER SAMEKH}"),
    ("HIRAGANA", None): (u"\N{KATAKANA LETTER RO}", u"\N{HIRAGANA LETTER NO}"),
    ("KATAKANA", None): (u"\N{KATAKANA LETTER RO}", u"\N{HIRAGANA LETTER NO}"),
    ("FIGURE", None): (u"H", u"0"),
}
SCRIPT_LABELS = {"LATIN": u"Latin", "GREEK": u"Greek", "CYRILLIC": u"Cyrillic", "ARMENIAN": u"Armenian",
                 "GEORGIAN": u"Georgian", "HEBREW": u"Hebrew", "HIRAGANA": u"Hiragana", "KATAKANA": u"Katakana"}
SPACED_SCRIPTS = ("LATIN", "GREEK", "CYRILLIC", "ARMENIAN", "GEORGIAN", "HEBREW", "HIRAGANA", "KATAKANA", "FIGURE")
# First words of letters' Unicode names that name no script (MODIFIER LETTER CIRCUMFLEX ACCENT, CARON,
# FEMININE ORDINAL INDICATOR, MICRO SIGN, FULLWIDTH LATIN CAPITAL LETTER A, DOUBLE-STRUCK CAPITAL C...):
# a proof scope keeps such letters as it keeps symbols, and never offers them as a script of their own
NOT_SCRIPTS = frozenset(("ALEF", "ANGSTROM", "BET", "BLACK", "CARON", "DALET", "DOUBLE", "EULER", "FEMININE",
                         "FULLWIDTH", "GIMEL", "HALFWIDTH", "IDEOGRAPHIC", "INFORMATION", "KELVIN", "MASCULINE",
                         "MASU", "MATHEMATICAL", "MICRO", "MODIFIER", "OHM", "PLANCK", "ROMAN", "SCRIPT",
                         "SUBSCRIPT", "SUPERSCRIPT", "TURNED", "VEDIC", "VERTICAL"))
CASE_LABELS = {"upper": u"capitals", "lower": u"lowercase", None: u"letters"}


# ---------------------------------------------------------------------------
# One master of the font, as the proof reads it
# ---------------------------------------------------------------------------

class ProofFont(object):
    """What a proof reads of one master: the glyphs in the font's order, their code points, their
    advance widths, and the kerning FontLab applies (classes resolved).

    advance(name): the glyph's advance width in this master, or None where it has no layer here;
    kerning {(first, second): value}: FontLab's kerning keys, glyph pairs in text order: the left
    glyph first, but a right-to-left pair's right glyph first (the one typed first: FontLab 7 keeps
    Hebrew kerning so, as a compiled font kerns it; see Auto Kerning's kerning_key);
    ink(name): (xmin, xmax) of the glyph's outline, or None (zero-width glyphs are centered by it)."""

    def __init__(self, family, master, upm, glyphs, codes, advance, kerning=None, ascender=None, descender=None,
                 ink=None, colored=None):
        self.family, self.master = family, master
        self.upm = float(upm or 1000)
        self.glyphs = list(glyphs)
        self.known = set(self.glyphs)
        self.codes = codes or {}
        self.cmap = {}
        for name in self.glyphs:
            for code in self.codes.get(name, ()):
                self.cmap.setdefault(code, name)
        self._advance = advance
        self.widths = {}
        self.kerning = dict((pair, value) for pair, value in (kerning or {}).items() if value)
        self.ascender = float(ascender) if ascender else 0.8 * self.upm
        self.descender = float(descender) if descender else -0.2 * self.upm
        if self.ascender - self.descender <= 0:
            self.ascender, self.descender = 0.8 * self.upm, -0.2 * self.upm
        self._ink = ink
        self._colored = colored

    def advance(self, name):
        if name not in self.widths:
            try:
                value = self._advance(name) if callable(self._advance) else self._advance.get(name)
            except Exception:
                value = None
            self.widths[name] = float(value) if value is not None else None
        return self.widths[name]

    def has(self, name):
        return name in self.known and self.advance(name) is not None

    def width(self, name):
        return self.advance(name) or 0.0

    def colored(self, name):
        """Drawn in colors of its own (a color font's emoji)."""
        try:
            return bool(self._colored(name)) if self._colored is not None else False
        except Exception:
            return False

    def textual(self, name):
        """In the font, with ink, and drawn in one ink: a letter, figure, or mark of punctuation a text
        sets (an emoji font's blank keycap figures and its color punctuation are not)."""
        if not self.has(name) or self.colored(name):
            return False
        return self._ink is None or self.ink(name) is not None

    def kern(self, first, second):
        """The kerning between two glyphs that follow each other in text (first typed first, whatever
        the direction they are set in)."""
        return self.kerning.get((first, second), 0)

    def direction(self, name):
        """"rtl" for a glyph of a right-to-left script (Hebrew, Thaana, Arabic...: its character's, or
        its base glyph's for an unencoded one such as yod.alt; see is_rtl_code), else None: a glyph of
        a left-to-right script, a mark of punctuation, a space, an unencoded glyph (a pair takes the
        direction of its right-to-left glyph, if it has one)."""
        code = self.code_of(name)
        if code is None:
            stem = name.split(u".")[0].split(u"_")[0]
            code = self.code_of(stem) if stem in self.codes else None
        return "rtl" if code is not None and is_rtl_code(code) else None

    def rtl_pair(self, first, second):
        """Whether a kerned pair is set right to left: either glyph of a right-to-left script (a mark of
        punctuation takes its partner's direction), as Auto Kerning's screen_of_key reads a key."""
        return "rtl" in (self.direction(first), self.direction(second))

    def ink(self, name):
        try:
            return self._ink(name) if self._ink is not None else None
        except Exception:
            return None

    def code_of(self, name):
        codes = self.codes.get(name) or ()
        return codes[0] if codes else None

    def name_of(self, char):
        codes = code_points(char)
        return self.cmap.get(codes[0]) if len(codes) == 1 else None

    def space(self):
        """The width of a space (the font's own, or a quarter of the em)."""
        name = self.cmap.get(0x20)
        return self.width(name) if self.has(name) else self.upm * 0.25

    def sequence(self, text):
        """The text as glyph names, None for each space; None when the font lacks a character."""
        found = []
        for code in code_points(text):
            if code == 0x20:
                found.append(None)
                continue
            name = self.cmap.get(code)
            if name is None or not self.has(name):
                return None
            found.append(name)
        return found

    def kind_of(self, name):
        """(script, case) of a glyph, by its code point or else by its name's base glyph's (a.sc, f_i)."""
        code = self.code_of(name)
        if code is None:
            stem = name.split(u".")[0].split(u"_")[0]
            if stem in self.codes:
                code = self.code_of(stem)
        return script_case(code) if code is not None else None

    def controls(self, kind):
        """(straight, round) glyph names to proof a glyph of this kind between, or None. A kind the
        table lacks, or controls the font lacks, fall back to Latin's (n and o, then H and O)."""
        if kind is None:
            tries = [("LATIN", "lower"), ("LATIN", "upper")]
        elif kind[1] == "upper":
            tries = [kind, (kind[0], None), ("LATIN", "upper"), (kind[0], "lower"), ("LATIN", "lower")]
        else:
            tries = [kind, (kind[0], None), (kind[0], "lower"), ("LATIN", "lower"), ("LATIN", "upper")]
        for key in tries:
            chars = CONTROLS.get(key)
            if chars is None:
                continue
            names = [self.name_of(ch) for ch in chars]
            if all(self.has(name) for name in names):
                return tuple(names)
        return None


# ---------------------------------------------------------------------------
# Lines: glyphs placed with their kerning, lines broken to a width
# ---------------------------------------------------------------------------

def place(font, line, rtl=False, kerning=True, space=None):
    """([(name, x)], width) for a line of glyph names (None: a space) in reading order, in font units,
    placed from the left. Right to left, the line is reversed first, its first glyph at the right; its
    pairs are still kerned in text order, as the font's kerning keeps them (a right-to-left pair's
    right glyph first): the glyph at the right of each pair is the first of its key."""
    space = font.space() if space is None else space
    visual = list(reversed(line)) if rtl else list(line)
    placed, x, prev = [], 0.0, None
    for name in visual:
        if name is None:
            x += space
            prev = None
            continue
        if prev is not None and kerning:
            x += font.kern(name, prev) if rtl else font.kern(prev, name)
        placed.append((name, x))
        x += font.width(name)
        prev = name
    return placed, x


def _token_width(font, names, prev, kerning):
    """The width of names (in reading order) after prev: each pair kerned in text order, either way."""
    width = 0.0
    for name in names:
        if prev is not None and kerning:
            width += font.kern(prev, name)
        width += font.width(name)
        prev = name
    return width, prev


def wrap(font, tokens, room, rtl=False, kerning=True, space=None):
    """Tokens [(names, spaced)] broken into lines no wider than room (font units), each a list of
    glyph names with None for a space, in reading order. spaced: a space before the token (else it
    joins the one before, kerned). A token too wide for a line of its own is broken between its glyphs."""
    space = font.space() if space is None else space
    lines, line, x, prev = [], [], 0.0, None
    queue = list(reversed([(list(names), spaced) for names, spaced in tokens if names]))
    while queue:
        names, spaced = queue.pop()
        gap = space if (line and spaced) else 0.0
        width, last = _token_width(font, names, None if gap or not line else prev, kerning)
        if line and x + gap + width > room:
            lines.append(line)
            line, x, prev = [], 0.0, None
            queue.append((names, spaced))
            continue
        if not line and width > room and len(names) > 1:
            queue.extend(reversed([([name], False) for name in names]))
            continue
        if gap:
            line.append(None)
        line.extend(names)
        x += gap + width
        prev = last
    if line:
        lines.append(line)
    return lines


def clip(font, line, room, rtl=False):
    """A line placed and cut at room font units (its start kept: the right end, right to left)."""
    placed, width = place(font, line, rtl)
    if width <= room:
        return placed, width
    if rtl:
        shift = width - room
        kept = [(name, x - shift) for name, x in placed if x - shift >= 0]
    else:
        kept = [(name, x) for name, x in placed if x + font.width(name) <= room]
    return kept, (max(x + font.width(name) for name, x in kept) if kept else 0.0)


def tokens_of(sequence, unspaced=False):
    """A text's glyph names (None: a space) as tokens for wrap: a word each, or (unspaced) a glyph
    each, joined to the one before unless a space comes between."""
    tokens, word, spaced = [], [], False
    for name in sequence:
        if name is None:
            if word:
                tokens.append((word, spaced))
            word, spaced = [], True
            continue
        if unspaced:
            tokens.append(([name], spaced))
            spaced = False
        else:
            word.append(name)
    if word:
        tokens.append((word, spaced))
    return tokens


def line_height(font, size):
    return size * max(LINE_SHARE, (font.ascender - font.descender) / font.upm * 1.15)


def baseline_in(font, size, height):
    """Points from a line's top to its baseline: the font's ascender and descender centered in it."""
    span = (font.ascender - font.descender) / font.upm * size
    return (height - span) / 2.0 + font.ascender / font.upm * size


def format_size(size):
    return (u"%.1f" % size).rstrip(u"0").rstrip(u".")


def parse_sizes(text, default):
    """Point sizes typed as "8, 9 10.5": the valid ones, in order, each once (default when none)."""
    found = []
    for match in re.findall(r"\d+(?:[.,]\d+)?", text or u""):
        size = float(match.replace(u",", u"."))
        if SIZE_RANGE[0] <= size <= SIZE_RANGE[1] and size not in found:
            found.append(size)
    return tuple(found) if found else tuple(default)


# ---------------------------------------------------------------------------
# Pages: what to draw where, in points from the page's top left
# ---------------------------------------------------------------------------

CHAR_SHARE = 0.55  # of the size: a character's width, generously, in the window's typeface (a line too long is elided)


def text_lines(text, width, size):
    """Text broken at spaces into lines of about width points at size points."""
    most = max(10, int(width / (size * CHAR_SHARE)))
    lines, line = [], u""
    for word in text.split(u" "):
        if line and len(line) + 1 + len(word) > most:
            lines.append(line)
            line = word
        else:
            line = word if not line else line + u" " + word
    lines.append(line)
    return lines


class Item(object):
    """Something on a page. Kinds: "glyphs" (x, baseline, size in points per em, upm, master, placed:
    [(name, x in font units)] from the left, rtl: set right to left), "text" (x, y, width, height, text, size, style: plain, bold, or quiet;
    align: left, center, or right), "line" (x1, y1, x2, y2), "frame" (x, y, width, height)."""

    def __init__(self, kind, **values):
        self.kind = kind
        for key, value in values.items():
            setattr(self, key, value)


class Page(object):
    def __init__(self, master):
        self.master = master
        self.sections = []  # the keys of the sections on it, in order
        self.items = []

    def runs(self):
        """The glyph names of each line of glyphs on the page, in text order: a right-to-left line's
        from its right end (FontLab 7's Glyph window sets typed Hebrew left to right, in that order, and
        kerns it by the font's keys, which are in that order too)."""
        found = []
        for item in self.items:
            if item.kind == "glyphs":
                names = [name for name, _ in item.placed]
                found.append(list(reversed(names)) if getattr(item, "rtl", False) else names)
        return found


class Layout(object):
    """Items laid out down the pages, a new page when one is full."""

    def __init__(self, size=None, margin=MARGIN):
        self.page_width, self.page_height = size or PAGE_SIZES[0][2]
        self.margin = margin
        self.left, self.right = margin, self.page_width - margin
        self.top, self.bottom = margin + HEADER_ROOM, self.page_height - margin - HEADER_ROOM
        self.pages, self.page, self.y = [], None, 0.0
        self.section = self.master = None

    def width(self):
        return self.right - self.left

    def new_page(self):
        self.page = Page(self.master)
        if self.section is not None:
            self.page.sections.append(self.section)
        self.pages.append(self.page)
        self.y = self.top

    def begin(self, section, master):
        """A section: on a new page for a new master, or when little of the page is left."""
        changed = master != self.master
        self.section, self.master = section, master
        if self.page is None or changed or self.bottom - self.y < SECTION_ROOM * (self.bottom - self.top):
            self.new_page()
        else:
            self.y += SECTION_GAP
            self.page.sections.append(section)

    def need(self, height):
        if self.page is None or (self.y + height > self.bottom and self.y > self.top):
            self.new_page()

    def add(self, kind, **values):
        self.page.items.append(Item(kind, **values))

    def text(self, text, size=8, style="plain", gap=0.0, keep=0.0):
        """Text, broken into lines of the page's width; keep: room wanted under its first line too (a
        heading is not left alone at a page's foot)."""
        height = size * 1.6
        for index, line in enumerate(text_lines(text, self.width(), size)):
            self.need((gap if not index else 0.0) + height + (keep if not index else 0.0))
            if not index and self.y > self.top:
                self.y += gap
            self.add("text", x=self.left, y=self.y, width=self.width(), height=height, text=line, size=size,
                     style=style, align="left")
            self.y += height

    def heading(self, text):
        self.text(text, 13, "bold", gap=4.0, keep=40.0)

    def field(self, label, text, size=8, label_width=INFO_LABEL_WIDTH):
        """A named value: its name on its first line's left, the value broken into lines beside it
        (each line of the value a paragraph)."""
        height = size * 1.6
        first = True
        for paragraph in text.split(u"\n"):
            if not paragraph.strip():
                continue
            for line in text_lines(paragraph.strip(), self.width() - label_width, size):
                self.need(height)
                if first:
                    self.add("text", x=self.left, y=self.y, width=label_width - 6.0, height=height, text=label,
                             size=size, style="quiet", align="left")
                    first = False
                self.add("text", x=self.left + label_width, y=self.y, width=self.width() - label_width, height=height,
                         text=line, size=size, style="plain", align="left")
                self.y += height

    def glyphs(self, font, placed, width, size, label=None, indent=0.0, align="left", rtl=False, collide=False):
        """A line of glyphs at size points per em (placed and width in font units); rtl: a line set
        right to left (its text order is from its right end: Page.runs); collide: its glyphs whose ink
        overlaps a neighbor's drawn in red (Renderer.colliding)."""
        height = line_height(font, size)
        self.need(height)
        x = self.left + indent
        if align == "right":
            x += max(0.0, self.right - x - width * size / font.upm)
        if label:
            self.add("text", x=self.left, y=self.y, width=indent - 4.0, height=height, text=label, size=7,
                     style="quiet", align="left")
        self.add("glyphs", x=x, baseline=self.y + baseline_in(font, size, height), size=size, upm=font.upm,
                 master=font.master, placed=placed, rtl=rtl, collide=bool(collide))
        self.y += height

    def lines(self, font, tokens, size, rtl=False, kerning=True, space=None, label=None, indent=0.0, collide=False):
        """Tokens broken into lines of the page's width and laid out (label: on the first line); right to
        left, each line set flush right, its first token at the right."""
        room = (self.width() - indent) * font.upm / size
        for index, line in enumerate(wrap(font, tokens, room, rtl, kerning, space)):
            placed, width = place(font, line, rtl, kerning, space)
            self.glyphs(font, placed, width, size, label if index == 0 else None, indent, "right" if rtl else "left",
                        rtl, collide)

    def finish(self, title, date, note=NOTE):
        """A header (the font, the master, the date) and a footer (the sections, the note, the page
        number) on each page."""
        count = len(self.pages)
        head, foot = self.margin + 4.0, self.page_height - self.margin - 12.0
        third = self.width() / 3.0
        for number, page in enumerate(self.pages, 1):
            master = page.master if page.master == ALL_MASTERS else (u"Master %s" % page.master if page.master else u"")
            sections = u", ".join(TITLES.get(key, key) for key in page.sections)
            frame = [
                Item("text", x=self.left, y=head, width=third, height=12.0, text=title, size=8, style="bold", align="left"),
                Item("text", x=self.left + third, y=head, width=third, height=12.0, text=master, size=8, style="plain",
                     align="center"),
                Item("text", x=self.right - third, y=head, width=third, height=12.0, text=date, size=8, style="quiet",
                     align="right"),
                Item("line", x1=self.left, y1=head + 15.0, x2=self.right, y2=head + 15.0),
                Item("line", x1=self.left, y1=foot - 3.0, x2=self.right, y2=foot - 3.0),
                Item("text", x=self.left, y=foot, width=third, height=12.0, text=sections, size=7, style="quiet",
                     align="left"),
                Item("text", x=self.left + third, y=foot, width=third, height=12.0, text=note, size=7, style="quiet",
                     align="center"),
                Item("text", x=self.right - third, y=foot, width=third, height=12.0,
                     text=u"Page %d of %d" % (number, count), size=7, style="quiet", align="right"),
            ]
            page.items = frame + page.items


# ---------------------------------------------------------------------------
# Languages and sample text
# ---------------------------------------------------------------------------

class Language(object):
    def __init__(self, iso, name, script, speakers, base, auxiliary=None):
        self.iso, self.name, self.script, self.speakers, self.base = iso, name, script, speakers or 0, base
        self.auxiliary = auxiliary or []


def languages_path():
    """Font Check's language data: beside this script (installed), or in the repository's checks/."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    for path in (os.path.join(here, LANGUAGES_FILE), os.path.join(here, os.pardir, "checks", LANGUAGES_FILE)):
        if os.path.isfile(path):
            return path
    return None


def load_languages(path=None):
    """The orthographies of language_coverage.json as Languages ([] when the file is missing)."""
    path = path or languages_path()
    if not path:
        return []
    with open(path, "rb") as handle:
        data = json.loads(handle.read().decode("utf-8"))
    texts = data["texts"]
    found = []
    for row in data["orthographies"]:
        iso, name, _autonym, script, _status, _validity, speakers, base = row[:8]
        auxiliary = row[8] if len(row) > 8 else None
        found.append(Language(iso, name, script, speakers, texts[base].split(u" ") if texts[base] else [],
                              texts[auxiliary].split(u" ") if auxiliary is not None and texts[auxiliary] else []))
    return found


def has_character(codes, text):
    """Whether the font has a character (one, or a letter and marks: composed, or all its parts)."""
    points = code_points(text)
    if all(code in codes for code in points):
        return True
    composed = code_points(unicodedata.normalize("NFC", text))
    return len(composed) == 1 and composed[0] in codes


class SampleGroup(object):
    """A script's sample text: [(language, text)]; rtl (Hebrew); unspaced (lines break anywhere);
    alphabet (the script's letters stand in: no sample text fits the font)."""

    def __init__(self, script, entries, alphabet=False):
        self.script, self.entries, self.alphabet = script, entries, alphabet
        self.rtl = script in RTL_SCRIPTS
        self.unspaced = alphabet or script in UNSPACED_SCRIPTS

    def text(self):
        return u" ".join(text for _, text in self.entries)

    def label(self):
        return u"%s: %s" % (self.script, u", ".join(language for language, _ in self.entries))


def choose_samples(font, languages, samples=SAMPLES, most=MAX_SAMPLES):
    """([SampleGroup], scripts left out): for each script the font covers a language of, the sample
    texts of the languages it covers whose characters it all has, the most spoken first; where none
    fits, the letters of the language it covers best. Scripts that need shaping are left out."""
    codes = set(code for code, name in font.cmap.items() if font.has(name))
    covered, best, left_out = {}, {}, set()
    for language in languages:
        present = [ch for ch in language.base if has_character(codes, ch)]
        if language.base and len(present) == len(language.base):
            covered[(language.iso, language.script)] = language
            if language.script not in TEXT_SCRIPTS:
                left_out.add(language.script)
        if language.script in TEXT_SCRIPTS and len(present) >= SCRIPT_MINIMUM:
            score = (len(present) / float(len(language.base)), language.speakers)
            if language.script not in best or score > best[language.script][0]:
                best[language.script] = (score, language, present)
    texts = {}
    for iso, script, text in samples:
        language = covered.get((iso, script))
        if language is None or font.sequence(text) is None:
            continue
        texts.setdefault(script, []).append((language.speakers, language.name, text))
    groups = []
    for script in TEXT_SCRIPTS:
        if script in texts:
            chosen = sorted(texts[script], key=lambda entry: -entry[0])[:most]
            groups.append(SampleGroup(script, [(name, text) for _, name, text in chosen]))
        elif script in best:
            if script in HAN_SCRIPTS and any(group.script in HAN_SCRIPTS for group in groups):
                continue  # the ideographs once (Japanese, Chinese, and Korean share them)
            _, language, present = best[script]
            letters = u"".join(ch for ch in present if len(code_points(ch)) == 1)[:ALPHABET_MAX]
            if letters:
                groups.append(SampleGroup(script, [(u"letters of %s" % language.name, letters)], alphabet=True))
    return groups, sorted(left_out)


def thin_scripts(font, languages, groups):
    """[(script, characters)] of the scripts the font has some letters of, but too few for any sample
    text or for its letters to stand in (no group): the proof shows none of them, and says so."""
    codes = set(code for code, name in font.cmap.items() if font.has(name))
    shown = set(group.script for group in groups)
    if any(group.script in HAN_SCRIPTS for group in groups):
        shown.update(HAN_SCRIPTS)
    found = {}
    for language in languages:
        if language.script in shown or language.script not in TEXT_SCRIPTS:
            continue
        present = found.setdefault(language.script, [])
        for ch in language.base:  # its script's letters only (keycap figures, Latin letters a Cyrillic orthography lists)
            first = (code_points(ch) or [None])[0]  # (a narrow build's pair of units read as one code point)
            kind = script_case(first) if first is not None else None
            if (ch not in present and category(first).startswith(u"L") and kind is not None
                    and kind[0] == (u"%s" % language.script).upper() and has_character(codes, ch)):
                present.append(ch)
    return [(script, u"".join(found[script])) for script in TEXT_SCRIPTS if found.get(script)]


def waterfall_line(font, groups):
    """(glyph names with None for spaces, rtl) for the waterfall: sample text of the first script,
    else the font's letters, else its encoded glyphs."""
    if groups:
        group = groups[0]
        text = group.text()
        while len(text) < WATERFALL_MIN and group.entries:
            text = text + u" " + group.text()
        sequence = font.sequence(text)
        if sequence:
            return sequence, group.rtl
    letters = [name for code, name in sorted(font.cmap.items())
               if category(code).startswith(u"L") and font.has(name)]
    if not letters:
        letters = [name for code, name in sorted(font.cmap.items()) if font.has(name) and code > 0x20]
    return letters[:WATERFALL_MIN], False


# ---------------------------------------------------------------------------
# Strings: kerning, spacing, diacritics, and figures and punctuation
# ---------------------------------------------------------------------------

def font_order(font):
    order = dict((name, index) for index, name in enumerate(font.glyphs))
    return lambda name: (order.get(name, len(order)), name)


def kerning_strings(font, keep=None):
    """[(first, [(second, value, names)])]: every kerned pair, grouped by its first glyph (in the font's
    order), each between control letters as HH?HOHO and nn?nono have it: two straight ones of the
    first glyph's kind before, a straight and a round one of the second glyph's twice after. A pair is
    the font's kerning key, in text order, and so are its names: the first glyph is the left one, or
    the right one of a right-to-left pair (font.rtl_pair), whose string is set right to left
    (section_kerning) and reads HH?HOHO from the right. keep(first, second): the pairs to list (all
    by default)."""
    groups = {}
    for (left, right), value in font.kerning.items():
        if not value or not font.has(left) or not font.has(right):
            continue
        if keep is not None and not keep(left, right):
            continue
        groups.setdefault(left, []).append((right, value))
    order = font_order(font)
    found = []
    for left in sorted(groups, key=order):
        strings = []
        for right, value in sorted(groups[left], key=lambda pair: order(pair[0])):
            left_kind, right_kind = font.kind_of(left), font.kind_of(right)
            before = font.controls(left_kind or right_kind)
            after = font.controls(right_kind or left_kind)
            names = ([before[0], before[0]] if before else []) + [left, right] + (list(after) * 2 if after else [])
            strings.append((right, value, names))
        found.append((left, strings))
    return found


def spacing_strings(font):
    """[(label, [(name, names)])]: each encoded letter and figure (Latin, Greek, Cyrillic, Armenian,
    Georgian, Hebrew, kana) between control letters of its kind, HHxHOxOO and nnxnoxoo, grouped by
    script and case. Modifier letters (superscript and subscript letters) are left out."""
    groups, labels = {}, []
    for name in font.glyphs:
        code = font.code_of(name)
        kind = script_case(code) if code is not None else None
        if kind is None or kind[0] not in SPACED_SCRIPTS or not font.textual(name) or category(code) == u"Lm":
            continue
        controls = font.controls(kind)
        if controls is None:
            names = [name]
        else:
            straight, round_ = controls
            names = [straight, straight, name, straight, round_, name, round_, round_]
        key = kind if kind[0] != "FIGURE" else ("FIGURE", None)
        if key not in groups:
            groups[key] = []
            labels.append(key)
        groups[key].append((name, names))
    found = []
    for key in labels:
        label = u"Figures" if key[0] == "FIGURE" else u"%s %s" % (SCRIPT_LABELS.get(key[0], key[0].title()),
                                                                  CASE_LABELS.get(key[1], u"letters"))
        found.append((label, groups[key]))
    return found


def diacritic_groups(font):
    """[(base name or None, [names])]: the letters with marks the font has, each after the letter it
    is built on (Aacute after A, lslash after l), by the base's code point; then the marks (combining
    ones, and spacing accents)."""
    groups = {}
    for name in font.glyphs:
        code = font.code_of(name)
        if code is None or not category(code).startswith(u"L") or not font.has(name):
            continue
        base = base_char(code)
        if base is not None:
            groups.setdefault(base, []).append((code, name))
    found = []
    for base in sorted(groups):
        base_name = font.cmap.get(base)
        found.append((base_name if font.has(base_name) else None, [name for _, name in sorted(groups[base])]))
    return found


def marks_of(font):
    """(combining marks, spacing accents and modifiers) the font has, by code point."""
    combining, spacing = [], []
    for code, name in sorted(font.cmap.items()):
        if not font.has(name):
            continue
        kind = category(code)
        if kind == u"Mn":
            combining.append(name)
        elif kind == u"Sk":
            spacing.append(name)
    return combining, spacing


def between(names, control):
    """H0H1H2H: each glyph between two of control (None: the glyphs alone)."""
    if control is None:
        return list(names)
    found = [control]
    for name in names:
        found += [name, control]
    return found


def figure_rows(font):
    """[(label, tokens)] for the figures and punctuation section: figures alone, their alternates
    (zero.osf, one.tf...), figures between capitals and lowercase, fractions and other numbers,
    punctuation alone and between letters, and symbols."""
    by_kind = {}
    for code, name in sorted(font.cmap.items()):
        if font.has(name) and code > 0x20:
            by_kind.setdefault(category(code), []).append(name)
    digits = [name for name in by_kind.get(u"Nd", []) if font.textual(name)]
    marks = [name for kind in (u"Pc", u"Pd", u"Ps", u"Pe", u"Pi", u"Pf", u"Po") for name in by_kind.get(kind, [])]
    punctuation = [name for name in marks if font.textual(name)]
    # a color font's emoji coded as figures or punctuation (‼, 〰) are shown with its symbols
    symbols = [name for name in by_kind.get(u"Nd", []) + marks if font.colored(name)]
    symbols += [name for kind in (u"Sc", u"Sm", u"So") for name in by_kind.get(kind, [])]
    upper, lower = font.controls(("LATIN", "upper")), font.controls(("LATIN", "lower"))
    capital = upper[0] if upper else None
    small = lower[0] if lower else None
    rows = []

    def glued(names):  # one run, broken anywhere
        return [([name], False) for name in names]

    def apart(names):  # each glyph on its own
        return [([name], True) for name in names]

    if digits:
        rows.append((u"Figures", glued(digits)))
        alternates = {}
        for digit in digits:
            for name in font.glyphs:
                if name.startswith(digit + u".") and font.has(name):
                    alternates.setdefault(name[len(digit):], []).append(name)
        for suffix in sorted(alternates):
            rows.append((u"Figures %s" % suffix, glued(alternates[suffix])))
        if capital:
            rows.append((u"Figures between capitals", glued(between(digits, capital))))
        if small:
            rows.append((u"Figures between lowercase", glued(between(digits, small))))
    if by_kind.get(u"No"):
        rows.append((u"Fractions, superiors, and other numbers", apart(by_kind[u"No"])))
    if punctuation:
        rows.append((u"Punctuation", apart(punctuation)))
        if capital:
            rows.append((u"Punctuation between capitals", glued(between(punctuation, capital))))
        if small:
            rows.append((u"Punctuation between lowercase", glued(between(punctuation, small))))
    if symbols:
        rows.append((u"Symbols", apart(symbols)))
    return rows


# ---------------------------------------------------------------------------
# Font info
# ---------------------------------------------------------------------------

# The font info rows, each with the attribute names tried in turn on FontLab's font info (the first
# with a value wins). None of the names is proven in FontLab 7 yet: one it lacks is skipped.
INFO_FIELDS = (
    (u"Family", ("familyName", "openTypeNamePreferredFamilyName", "styleMapFamilyName")),
    (u"Style", ("styleName", "openTypeNamePreferredSubfamilyName", "styleMapStyleName")),
    (u"Version", ("openTypeNameVersion", "version")),  # (after versionMajor and versionMinor)
    (u"Designer", ("openTypeNameDesigner", "designer")),
    (u"Designer URL", ("openTypeNameDesignerURL", "designerURL")),
    (u"Manufacturer", ("openTypeNameManufacturer", "manufacturer")),
    (u"Manufacturer URL", ("openTypeNameManufacturerURL", "manufacturerURL")),
    (u"Vendor ID", ("openTypeOS2VendorID", "vendorID")),
    (u"Copyright", ("copyright",)),
    (u"Trademark", ("trademark",)),
    (u"License", ("openTypeNameLicense", "license")),
    (u"License URL", ("openTypeNameLicenseURL", "licenseURL")),
    (u"Description", ("openTypeNameDescription", "description")),
    (u"Created", ("openTypeHeadCreated", "created", "creationDate")),
    (u"Modified", ("openTypeHeadModified", "modified", "modificationDate")),
)
INFO_DATES = (u"Created", u"Modified")
MAC_EPOCH = 2082844800  # seconds from 1904-01-01 (OpenType's head dates count from it) to 1970-01-01


def info_text(value):
    """A font info value as text ("" when empty): a list's items joined, a whole float as an integer,
    each line's spaces made single; a method (not a value) is never called."""
    import numbers
    if value is None or isinstance(value, bool) or callable(value):
        return u""
    if isinstance(value, (list, tuple)):
        return u", ".join(text for text in (info_text(item) for item in value) if text)
    if isinstance(value, float) and value == int(value):
        value = int(value)
    if isinstance(value, bytes):
        text = value.decode("utf-8", "replace")
    elif isinstance(value, numbers.Number):
        text = u"%s" % value
    else:
        try:
            text = u"%s" % (value,)
        except Exception:
            return u""
    lines = (u" ".join(line.split()) for line in text.replace(u"\r\n", u"\n").replace(u"\r", u"\n").split(u"\n"))
    return u"\n".join(line for line in lines if line)


def info_date(value):
    """A date of the font info as text: seconds (from 1970, or from 1904 as OpenType counts them) as
    a day, a QDate or QDateTime by its own text, else the value as it reads."""
    import numbers
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        seconds = float(value)
        if seconds > 2.5e9:  # past 2049 from 1970: counted from 1904
            seconds -= MAC_EPOCH
        if seconds <= 0:
            return u""
        try:
            return u"%s" % time.strftime("%Y-%m-%d", time.gmtime(seconds))
        except Exception:
            return u""
    kind = type(value).__name__
    if kind.startswith("QDate"):
        try:
            return info_text(value.toString("yyyy-MM-dd hh:mm" if kind == "QDateTime" else "yyyy-MM-dd"))
        except Exception:
            return u""
    return info_text(value)


def info_rows(info, name=None, upm=None, masters=()):
    """[(label, text)] of a font's info, the empty fields left out: info is FontLab's font info (or
    any object with such attributes, or None); name, upm, and masters are the font's own."""
    def read(attribute):
        try:
            return getattr(info, attribute, None)
        except Exception:
            return None

    def first(names, form):
        for attribute in names:
            text = form(read(attribute))
            if text:
                return text
        return u""

    found = []
    for label, names in INFO_FIELDS:
        text = u""
        if label == u"Version":
            major, minor = read("versionMajor"), read("versionMinor")
            try:
                if major is not None and minor is not None and not callable(major) and not callable(minor):
                    text = u"%d.%03d" % (int(major), int(minor))
            except (TypeError, ValueError):
                text = u""
        text = text or first(names, info_date if label in INFO_DATES else info_text)
        if text:
            found.append((label, text))
        if label == u"Style" and info_text(name):
            found.append((u"Font name", info_text(name)))
    if info_text(upm):
        found.append((u"Units per em", info_text(upm)))
    if masters:
        found.append((u"Masters", u"%s (%d)" % (u", ".join(info_text(m) for m in masters), len(masters))))
    cut = []
    for label, text in found:
        if len(text) > INFO_TEXT_MAX:
            rest = len(text) - INFO_TEXT_MAX
            text = text[:INFO_TEXT_MAX].rstrip() + u"\N{HORIZONTAL ELLIPSIS} (%s more)" % counted(rest, u"character")
        cut.append((label, text))
    return cut


# ---------------------------------------------------------------------------
# The summary: what the proof's first page says of the font
# ---------------------------------------------------------------------------

# OpenType's names of the features a font's code commonly defines (ss01 to ss20 and cv01 to cv99 are
# named by their number: feature_title)
FEATURE_NAMES = {
    "aalt": u"Access All Alternates", "abvm": u"Above-Base Mark Positioning", "blwm": u"Below-Base Mark Positioning",
    "c2pc": u"Petite Capitals From Capitals", "c2sc": u"Small Capitals From Capitals", "calt": u"Contextual Alternates",
    "case": u"Case-Sensitive Forms", "ccmp": u"Glyph Composition and Decomposition", "clig": u"Contextual Ligatures",
    "cpsp": u"Capital Spacing", "cswh": u"Contextual Swash", "curs": u"Cursive Positioning", "dist": u"Distances",
    "dlig": u"Discretionary Ligatures", "dnom": u"Denominators", "fina": u"Terminal Forms", "frac": u"Fractions",
    "fwid": u"Full Widths", "halt": u"Alternate Half Widths", "hist": u"Historical Forms",
    "hlig": u"Historical Ligatures", "hwid": u"Half Widths", "init": u"Initial Forms", "isol": u"Isolated Forms",
    "kern": u"Kerning", "liga": u"Standard Ligatures", "lnum": u"Lining Figures", "locl": u"Localized Forms",
    "mark": u"Mark Positioning", "medi": u"Medial Forms", "mkmk": u"Mark to Mark Positioning",
    "nalt": u"Alternate Annotation Forms", "numr": u"Numerators", "onum": u"Oldstyle Figures", "ordn": u"Ordinals",
    "ornm": u"Ornaments", "palt": u"Proportional Alternate Widths", "pcap": u"Petite Capitals",
    "pnum": u"Proportional Figures", "pwid": u"Proportional Widths", "rlig": u"Required Ligatures",
    "salt": u"Stylistic Alternates", "sinf": u"Scientific Inferiors", "size": u"Optical Size",
    "smcp": u"Small Capitals", "subs": u"Subscript", "sups": u"Superscript", "swsh": u"Swash", "titl": u"Titling",
    "tnum": u"Tabular Figures", "unic": u"Unicase", "vert": u"Vertical Writing", "vkrn": u"Vertical Kerning",
    "vpal": u"Proportional Alternate Vertical Metrics", "vrt2": u"Vertical Alternates and Rotation",
    "zero": u"Slashed Zero"}
METRIC_HEADER = (u"Ascender", u"Descender", u"Line gap")
NOT_SET = u"not set"
INFERRED_KEY = (u"(inferred): the letters a counted text uses, not an orthography a source declares; rare letters may "
                u"be missing from it.")
KEYBOARD_KEY = (u"(keyboard): the characters a keyboard layout types, not an orthography a source declares; it may "
                u"lack some letters.")
EVIDENCE_KEYS = ((u"inferred", INFERRED_KEY), (u"keyboard", KEYBOARD_KEY))
APPLIED = (u"Kerning, as FontLab applies it (classes resolved); no OpenType features (no ligatures, alternates, or mark "
           u"positioning: each character shows its own glyph)")


def feature_title(tag):
    """OpenType's name of a feature ("Standard Ligatures", "Stylistic Set 3"), or u"" for a tag it does
    not register (or one this table lacks)."""
    tag = u"%s" % tag
    match = re.match(u"^(ss|cv)([0-9]{2})$", tag)
    if match and int(match.group(2)) >= 1 and (match.group(1) == u"cv" or int(match.group(2)) <= 20):
        return (u"Stylistic Set %d" if match.group(1) == u"ss" else u"Character Variant %d") % int(match.group(2))
    return FEATURE_NAMES.get(tag, u"")


def features_text(features):
    """The features of a font's code in one text: features [(tag, the name the code gives it or u"")],
    in the code's order; each tag with OpenType's name and the code's own, in parentheses."""
    parts = []
    for tag, name in features:
        words = u": ".join(text for text in (feature_title(tag), info_text(name)) if text)
        parts.append(u"%s (%s)" % (tag, words) if words else u"%s" % tag)
    if not parts:
        return u"none in the font's code"
    return u"%s: %s" % (counted(len(parts), u"feature"), u", ".join(parts))


def kerning_text(pairs, master, entries=None, classes=None):
    """A master's kerning in one line: its pairs of glyphs with the classes resolved, then the entries
    and classes they come from, where FontLab gives them."""
    if not pairs:  # (a count right at 0: never "0 kerned pairs", owner's image 228)
        return u"No kerned pairs in master %s" % master
    text = u"%s in master %s, classes resolved" % (counted(pairs, u"kerned pair"), master)
    if entries is not None and classes is not None:
        text += u" (%s, %s)" % (counted(entries, u"entry", u"entries"), counted(classes, u"class", u"classes"))
    return text


def units(value):
    """A metric in font units, rounded (halves up, whatever the Python); "not set" for None."""
    if value is None:
        return NOT_SET
    return u"%d" % int(math.floor(float(value) + 0.5))


def metric_rows(metrics, master=u""):
    """[(label, [ascender, descender, line gap])] as texts, for the summary's table: the master's own
    dimensions, then the font's typo, hhea, and Windows values (metrics: Font Check's read_metrics, or
    any object with its fields; Windows has no line gap)."""
    rows = ((u"Master %s" % master if master else u"Master", ("ascender", "descender", "line_gap")),
            (u"Typo", ("typo_ascender", "typo_descender", "typo_line_gap")),
            (u"hhea", ("hhea_ascender", "hhea_descender", "hhea_line_gap")),
            (u"Windows", ("win_ascent", "win_descent", None)))
    return [(label, [units(getattr(metrics, field, None)) if field else u"" for field in fields])
            for label, fields in rows]


def metric_notes(metrics):
    """[(label, text)] under the summary's table: the x-height and the cap height, and whether Use Typo
    Metrics is set, each where the font says."""
    found = []
    heights = [u"%s %s" % (label, units(getattr(metrics, field)))
               for label, field in ((u"x-height", "x_height"), (u"cap height", "cap_height"))
               if getattr(metrics, field, None) is not None]
    if heights:
        found.append((u"Heights", u", ".join(heights)))
    if getattr(metrics, "use_typo", None) is not None:
        found.append((u"Use Typo Metrics", u"on" if metrics.use_typo else u"off"))
    return found


def summary_rows(info, name, master, masters, proofed, glyphs, encoded, scope=u""):
    """[(label, text)] of the summary's first block: the font (its family and style names, as its info
    gives them, else its name in FontLab), the master proofed and the others, the version and dates the
    font records, its units per em, and its counts of glyphs and of encoded characters. info: info_rows'
    rows (or None); proofed: the masters the proof shows; scope: what the proof is limited to, if anything."""
    known = dict(info or ())
    rows = []
    font = u" ".join(text for text in (known.get(u"Family", u""), known.get(u"Style", u"")) if text) or info_text(name)
    if font:
        rows.append((u"Font", font))
    masters = [u"%s" % one for one in masters or ()]
    proofed = [u"%s" % one for one in proofed or ()]
    if len(proofed) > 1:
        rows.append((u"Masters", u"%s (all %d proofed)" % (u", ".join(proofed), len(proofed))))
    elif master:
        others = [one for one in masters if one != master]
        if not others:
            rows.append((u"Master", u"%s (the font's only master)" % master))
        else:
            rows.append((u"Master", u"%s (%s: %s)" % (master, u"the font's other master" if len(others) == 1
                                                      else u"the font's other masters", u", ".join(others))))
    dates = u", ".join(u"%s %s" % (word, known[label]) for word, label in ((u"created", u"Created"),
                                                                           (u"modified", u"Modified")) if known.get(label))
    if known.get(u"Version"):
        rows.append((u"Version", u"%s (%s)" % (known[u"Version"], dates) if dates else known[u"Version"]))
    elif dates:
        rows.append((u"Dates", dates))
    if known.get(u"Units per em"):
        rows.append((u"Units per em", known[u"Units per em"]))
    rows.append((u"Glyphs", u"%s (%s)" % (counted(glyphs, u"glyph"), counted(encoded, u"encoded character"))))
    if scope:
        rows.append((u"Proof of", scope))
    return rows


class ScriptSummary(object):
    """A script the font has, on the summary: text ("275 of 569 languages (99 within reach)", Font
    Check's own words), and its languages covered and within reach, each A to Z as
    (name, its mark: u"inferred" from a text, u"keyboard" from a keyboard layout, u"" declared by a source
    (True stands for u"inferred"), what it lacks: u"" when covered, "2 missing", "12 auxiliary missing")."""

    def __init__(self, script, text, covered=(), reach=()):
        self.script, self.text, self.covered, self.reach = script, text, list(covered), list(reach)


class CoverageSummary(object):
    """What the summary says of the languages: scripts [ScriptSummary]; sets: the names of the character
    sets covered, of set_count checked; within: the characters a language within reach lacks at most;
    composed: the languages covered thanks to letters the anchors compose (None: letters are not
    composed); sources [(source's name, languages covered it gives)], the most first; dated: the day
    the data files were last changed (u"": not known); script_sets: (Unicode's scripts covered whole, of
    those checked), counted apart from the sets as Font Check counts them; legacy: the Legacy sets left out
    of the counts."""

    def __init__(self, scripts=(), sets=(), set_count=0, within=3, composed=None, sources=(), dated=u"",
                 script_sets=(0, 0), legacy=0):
        self.scripts, self.sets, self.set_count = list(scripts), list(sets), set_count
        self.within, self.composed, self.sources, self.dated = within, composed, list(sources), dated
        self.script_sets, self.legacy = tuple(script_sets), legacy

    def covered(self):
        return sum(len(script.covered) for script in self.scripts)

    def reach(self):
        return sum(len(script.reach) for script in self.scripts)

    def inferred(self):
        return sum(1 for script in self.scripts for _, inferred, _ in script.covered if inferred)

    def sentence(self):
        """The counts in one sentence, in their numbers."""
        if not self.scripts:
            return u"The font has none of the scripts whose languages Font Check checks."
        return u"%s covered and %d within reach, of the languages of %s the font has." % (
            counted(self.covered(), u"language"), self.reach(), counted(len(self.scripts), u"script"))

    def notes(self):
        """The small print, a paragraph each: how the languages are counted, how many rest on a counted
        text, and where the data comes from, with its date: a coverage claim on a proof is a claim."""
        found = [u"Counted as Font Check counts them: a language is covered when the font has every one of its base "
                 u"and auxiliary characters and its marks, and within reach when it lacks at most %s (or auxiliary "
                 u"characters alone)." % counted(self.within, u"base character or mark", u"base characters or marks")]
        if self.composed is not None:
            found[0] += u" A letter the font's anchors compose from its letter and marks counts as there"
            found[0] += u" (%s covered %s on such letters)." % (counted(self.composed, u"language"),
                                                                 u"relies" if self.composed == 1 else u"rely")
        inferred = self.inferred()
        if inferred:  # (Font Check's own words for the languages no source declares)
            found.append(u"Of the languages covered, %s inferred from text or read from a keyboard layout, not declared "
                         u"by a source." % (u"1 is" if inferred == 1 else u"{:,} are".format(inferred)))
        if self.sources:
            text = u"Language data, as Font Check holds it: %s." % u"; ".join(
                u"%s from %s" % (counted(count, u"language"), name) for name, count in self.sources)
            if self.dated:
                text += u" Data files last changed %s." % self.dated
            found.append(text)
        return found


def data_date(fc):
    """The day Font Check's data files were last changed (the newest of them), or u""."""
    stamps = []
    for name in ("languages_path", "orthographies_path", "sets_path"):
        try:
            stamps.append(os.path.getmtime(getattr(fc, name)()))
        except Exception:
            continue
    return u"%s" % time.strftime("%Y-%m-%d", time.localtime(max(stamps))) if stamps else u""


def coverage_summary(fc, codes, attaches=None):
    """The CoverageSummary of a font with these code points, computed by Font Check's own functions
    (fc: its module), in the order its Coverage view calls them and with the settings its window
    starts with: every language (the inferred ones too), within reach at its NEARLY_MISSING, and
    attaches(letter's code point, mark's code point) for the letters the font's anchors compose (None:
    none are). The scripts are those the font has; the character sets, the ones it lists as covered,
    but the Legacy group's, which are not counted."""
    languages, _ = fc.chosen_languages(fc.load_languages(), True)
    font = fc.FontCharacters(codes, attaches)
    within = fc.NEARLY_MISSING
    scripts, sources, composed = [], {}, 0
    for found in fc.coverage(languages, font, within, True, None):
        if not found.present:
            continue
        covered, reach = [], []
        for r in sorted(found.results, key=fc.name_key):
            mark = evidence_mark(fc, r.language.evidence)  # (keyboard layouts too: no source declares them)
            if r.level == "covered":
                covered.append((u"%s" % r.language.name, mark, u""))
                source = u"%s" % r.language.source
                sources[source] = sources.get(source, 0) + 1
                composed += 1 if r.composed else 0
            elif r.level == "nearly":
                # what it lacks, as Font Check's needs() says: base characters and marks, or, with all
                # of those there, its auxiliary characters (any number of them: said so)
                lacks = u"%d missing" if fc.base_needs(r) else u"%d auxiliary missing"
                reach.append((u"%s" % r.language.name, mark, lacks % len(fc.needs(r))))
        scripts.append(ScriptSummary(u"%s" % found.script, fc.script_text(found), covered, reach))
    # The sets counted as Font Check counts them (its set_tally, one definition for both): the scripts of
    # Unicode apart (a script checked as a set, by its ranges, as Font Check checks it), the Legacy sets,
    # wholly optional and always covered, not at all (the owner). Live on Noto Sans, Proof said "33 of 312"
    # (the scripts counted among the sets) where Font Check said 33 of 140
    check = getattr(fc, "check_entry", fc.check_language)
    results = [check(one, font, within) for one in fc.load_character_sets()]
    if hasattr(fc, "set_tally"):
        sets, of_unicode, legacy = fc.set_tally(results)[:3]
    else:  # (an older Font Check)
        legacy_group = getattr(fc, "LEGACY_GROUP", u"Legacy")
        sets, of_unicode, legacy = [r for r in results if r.language.script != legacy_group], [], []
    return CoverageSummary(scripts, [u"%s" % r.language.name for r in sets if r.level == "covered"], len(sets), within,
                           composed if attaches is not None else None,
                           sorted(sources.items(), key=lambda one: (-one[1], one[0])), data_date(fc),
                           script_sets=(sum(1 for r in of_unicode if r.level == "covered"), len(of_unicode)),
                           legacy=len(legacy))


def evidence_mark(fc, evidence):
    """What Font Check's list says beside a language no source declares: u"inferred" (its characters
    counted from a text) or u"keyboard" (read from a keyboard layout); u"" for a declared one. Font
    Check's UNDECLARED names both kinds (an older Font Check without it knew the inferred alone)."""
    inferred = getattr(fc, "INFERRED", "inferred")
    undeclared = getattr(fc, "UNDECLARED", (inferred,))
    if evidence not in undeclared:
        return u""
    return u"keyboard" if evidence == getattr(fc, "KEYBOARD", "keyboard") else u"inferred"


def mark_word(mark):
    """An entry's mark as the word the summary shows (True, from older callers, is u"inferred")."""
    return u"inferred" if mark is True else (u"%s" % mark if mark else u"")


def language_names(entries):
    """The texts of a script's languages on the summary: each name, with "(inferred)" or "(keyboard)"
    as Font Check marks a language no source declares, and, within reach, how many it lacks."""
    found = []
    for name, mark, lacks in entries:
        notes = ([mark_word(mark)] if mark else []) + ([lacks] if lacks else [])
        found.append(u"%s (%s)" % (name, u", ".join(notes)) if notes else name)
    return found


class Summary(object):
    """What the proof's first page says of the font. title: the family's name, set in the font itself
    (font: the ProofFont it is set in, None: the proof's first); rows [(label, text)] (summary_rows);
    metrics and metric_notes (metric_rows, metric_notes; None: not read); features: features_text's (u"":
    not read); kerning: kerning_text's; coverage: a CoverageSummary (None: Font Check's data is not
    there, and the page leaves the languages out); languages: a key of SUMMARY_LANGUAGES."""

    def __init__(self, title=u"", rows=(), metrics=None, metric_notes=(), features=u"", kerning=u"", coverage=None,
                 languages="covered", font=None):
        self.title, self.rows, self.font = title, list(rows), font
        self.metrics, self.metric_notes = metrics, list(metric_notes)
        self.features, self.kerning, self.coverage, self.languages = features, kerning, coverage, languages


# ---------------------------------------------------------------------------
# The sections
# ---------------------------------------------------------------------------

class Options(object):
    """What a proof shows: sections (keys of SECTIONS), the page size (a key of PAGE_SIZES), the
    waterfall's and the text's sizes, keep(left, right): the kerned pairs to list (None: all), and
    collisions: the glyphs of the kerning and spacing strings whose ink overlaps a neighbor's drawn in red
    (owner's image 348; off at first: a script font's letters may overlap on purpose)."""

    def __init__(self, sections=None, page="A4", waterfall=WATERFALL_SIZES, text_sizes=TEXT_SIZES, keep=None,
                 collisions=False):
        self.sections = set(sections if sections is not None else [key for key, _ in SECTIONS])
        self.page = page
        self.waterfall, self.text_sizes = tuple(waterfall), tuple(text_sizes)
        self.keep = keep
        self.collisions = bool(collisions)


def page_size(key):
    for name, _, size in PAGE_SIZES:
        if name == key:
            return size
    return PAGE_SIZES[0][2]


def section_charset(layout, font):
    layout.heading(TITLES["charset"])
    layout.text(u"%s, in the font's order, each with its name and code point." % counted(len(font.glyphs), u"glyph"),
                style="quiet")
    if not font.glyphs:
        layout.text(u"The font has no glyphs.")
        return
    cell = layout.width() / GRID_COLUMNS
    height = cell * CELL_SHARE
    labels = 16.0
    area = height - labels - 4.0
    span = (font.ascender - font.descender) / font.upm
    size = min(area / span, cell * 0.8)
    for start in range(0, len(font.glyphs), GRID_COLUMNS):
        layout.need(height)
        y = layout.y
        for column, name in enumerate(font.glyphs[start:start + GRID_COLUMNS]):
            x = layout.left + column * cell
            layout.add("frame", x=x, y=y, width=cell, height=height)
            if font.has(name):
                advance = font.width(name)
                scale = size
                if advance * scale / font.upm > cell * 0.9:
                    scale = cell * 0.9 * font.upm / advance
                if advance > 0:
                    left = x + (cell - advance * scale / font.upm) / 2.0
                else:
                    ink = font.ink(name)
                    middle = (ink[0] + ink[1]) / 2.0 if ink else 0.0
                    left = x + cell / 2.0 - middle * scale / font.upm
                top = y + 2.0 + (area - span * scale) / 2.0
                layout.add("glyphs", x=left, baseline=top + font.ascender / font.upm * scale, size=scale, upm=font.upm,
                           master=font.master, placed=[(name, 0.0)])
                code = font.code_of(name)
                below = u"U+%04X" % code if code is not None else u""
            else:
                below = u"no layer"
            layout.add("text", x=x + 1.0, y=y + height - labels, width=cell - 2.0, height=8.0, text=name, size=6,
                       style="plain", align="center")
            layout.add("text", x=x + 1.0, y=y + height - labels + 7.5, width=cell - 2.0, height=8.0, text=below, size=6,
                       style="quiet", align="center")
        layout.y += height


def section_waterfall(layout, font, line, rtl, sizes):
    layout.heading(TITLES["waterfall"])
    layout.text(u"Sizes in points, kerning applied.", style="quiet")
    if not line:
        layout.text(u"The font has no glyphs to set.")
        return
    for size in sizes:
        room = (layout.width() - LABEL_WIDTH) * font.upm / size
        placed, width = clip(font, line, room, rtl)
        layout.glyphs(font, placed, width, size, u"%s pt" % format_size(size), LABEL_WIDTH, "right" if rtl else "left",
                      rtl)


def section_text(layout, font, groups, sizes, left_out):
    layout.heading(TITLES["text"])
    layout.text(u"Sample text in each script the font covers, at %s points, kerning applied; no OpenType "
                u"features (each character shows its own glyph)." % u", ".join(format_size(s) for s in sizes),
                style="quiet")
    if left_out:
        layout.text(u"No text for %s: %s shaping (joining, reordering, or mark positioning), which this proof does "
                    u"not do." % (u", ".join(left_out), u"it needs" if len(left_out) == 1 else u"they need"),
                    style="quiet")
    if not groups:
        layout.text(u"The font covers none of the languages Font Check knows in a script set without shaping.")
        return
    for group in groups:
        layout.text(group.label(), 9, "bold", gap=6.0, keep=30.0)
        sequence = font.sequence(group.text()) or []
        tokens = tokens_of(sequence, group.unspaced)
        for size in sizes:
            layout.lines(font, tokens, size, group.rtl, True, None, u"%s pt" % format_size(size), LABEL_WIDTH)
            layout.y += size * 0.4


COLLISIONS_NOTE = u" Glyphs whose ink overlaps the next glyph's are drawn in red."
COLLISIONS_LABEL = u"Draw colliding glyphs in red."  # (the tick: a sentence, with its period)


def section_kerning(layout, font, keep=None, size=STRING_SIZE, collisions=False):
    layout.heading(TITLES["kerning"])
    groups = kerning_strings(font, keep)
    total = sum(len(strings) for _, strings in groups)
    which = u"common kerned pair" if keep is not None else u"kerned pair"
    layout.text(u"%s, grouped by first glyph, between control letters (HH?HOHO, nn?nono), kerning applied "
                u"(classes resolved). Right-to-left pairs are set right to left, as they read: their first "
                u"glyph is the right one.%s" % (counted(total, which), COLLISIONS_NOTE if collisions else u""),
                style="quiet")
    if not groups:
        layout.text(u"No %s in this master." % (which + u"s"))
        return
    space = font.upm * STRING_GAP
    for first, strings in groups:
        layout.text(u"%s (%s)" % (first, counted(len(strings), u"pair")), 8, "bold", gap=4.0,
                    keep=line_height(font, size))
        for rtl, tokens in direction_runs(font, first, strings):
            layout.lines(font, tokens, size, rtl, space=space, collide=collisions)


def direction_runs(font, first, strings):
    """A group's strings ([(second, value, names)]) as [(rtl, tokens)]: the strings that follow each
    other in one direction, one run each (a mark of punctuation may kern with letters of both)."""
    runs = []
    for second, _, names in strings:
        rtl = font.rtl_pair(first, second)
        if not runs or runs[-1][0] != rtl:
            runs.append((rtl, []))
        runs[-1][1].append((names, True))
    return runs


def section_spacing(layout, font, size=STRING_SIZE, collisions=False):
    layout.heading(TITLES["spacing"])
    groups = spacing_strings(font)
    layout.text(u"Each letter and figure between control letters (HHxHOxOO, nnxnoxoo), set without kerning: the "
                u"sidebearings alone.%s" % (COLLISIONS_NOTE if collisions else u""), style="quiet")
    if not groups:
        layout.text(u"The font has no encoded letters or figures of the scripts spaced here.")
        return
    space = font.upm * STRING_GAP
    for label, strings in groups:
        layout.text(u"%s (%s)" % (label, counted(len(strings), u"glyph")), 8, "bold", gap=4.0, keep=line_height(font, size))
        rtl = font.direction(strings[0][0]) == "rtl"  # (Hebrew's read from the right, as its kerning strings)
        layout.lines(font, [(names, True) for _, names in strings], size, rtl, kerning=False, space=space,
                     collide=collisions)


def section_diacritics(layout, font, size=SHOWCASE_SIZE):
    layout.heading(TITLES["diacritics"])
    groups = diacritic_groups(font)
    combining, spacing = marks_of(font)
    layout.text(u"%s, each group after the letter it is built on, kerning applied; marks are not positioned "
                u"(no mark feature)." % counted(sum(len(names) for _, names in groups), u"letter with diacritics",
                                                u"letters with diacritics"), style="quiet")
    space = font.upm * STRING_GAP
    if groups:
        layout.lines(font, [(([base] if base else []) + names, True) for base, names in groups], size, space=space)
    else:
        layout.text(u"The font has no letters with diacritics.")
    circle = font.cmap.get(0x25CC)
    circle = circle if font.has(circle) else None
    if combining:
        layout.text(u"Combining marks%s" % (u", on the dotted circle" if circle else u""), 8, "bold", gap=6.0,
                    keep=line_height(font, size))
        layout.lines(font, [(([circle] if circle else []) + [name], True) for name in combining], size, space=space)
    if spacing:
        layout.text(u"Spacing accents and modifiers", 8, "bold", gap=6.0, keep=line_height(font, size))
        layout.lines(font, [([name], True) for name in spacing], size, space=space)


def section_figures(layout, font, size=SHOWCASE_SIZE):
    layout.heading(TITLES["figures"])
    rows = figure_rows(font)
    layout.text(u"Kerning applied.", style="quiet")
    if not rows:
        layout.text(u"The font has no encoded figures, punctuation, or symbols.")
        return
    space = font.upm * STRING_GAP
    for label, tokens in rows:
        layout.text(label, 8, "bold", gap=6.0, keep=line_height(font, size))
        layout.lines(font, tokens, size, space=space)


def section_info(layout, rows):
    layout.heading(TITLES["info"])
    layout.text(u"As FontLab's font info gives it; empty fields are left out.", style="quiet")
    if not rows:
        layout.text(u"FontLab gave none of the font's info.")
        return
    for label, text in rows:
        layout.field(label, text)


def summary_table(layout, header, rows, label_width=INFO_LABEL_WIDTH, column=SUMMARY_METRIC_COLUMN, size=8):
    """A small table, kept on one page: a quiet header, then each row's label and its cells, the cells
    set flush right under their headings."""
    height = size * 1.45
    layout.need(height * (len(rows) + 1))
    for index, (label, cells) in enumerate([(u"", header)] + list(rows)):
        if label:
            layout.add("text", x=layout.left, y=layout.y, width=label_width - 6.0, height=height, text=label,
                       size=size, style="quiet", align="left")
        for at, cell in enumerate(cells):
            if cell:  # (Windows has no line gap: its cell stays empty)
                layout.add("text", x=layout.left + label_width + at * column, y=layout.y, width=column - 10.0,
                           height=height, text=cell, size=size, style="plain" if index else "quiet", align="right")
        layout.y += height


def summary_names(layout, names, columns=SUMMARY_COLUMNS, size=SUMMARY_NAME_SIZE, leading=SUMMARY_NAME_LEADING):
    """Names in columns, read down each column and then across; a list longer than the page's room goes
    on over the following pages (down the columns of each page in turn), never cut."""
    width = layout.width() / columns
    at = 0
    while at < len(names):
        rest = -(-(len(names) - at) // columns)  # the rows the names left would take
        layout.need(leading * min(SUMMARY_MIN_ROWS, rest))
        room = max(1, int((layout.bottom - layout.y) // leading))
        block = names[at:at + room * columns]
        rows = -(-len(block) // columns)
        for index, name in enumerate(block):
            column, row = divmod(index, rows)
            layout.add("text", x=layout.left + column * width, y=layout.y + row * leading, width=width - 6.0,
                       height=leading, text=name, size=size, style="plain", align="left")
        layout.y += rows * leading
        at += len(block)


def set_fields(coverage):
    """[(label, text)] of the character sets on the summary, counted as Font Check's top line counts them
    (its set_tally): "33 of 140 covered (the 5 Legacy sets, wholly optional, not counted): IPA, …", and
    Unicode's scripts apart, "0 of 172 covered whole"."""
    found = []
    if coverage.set_count:
        text = u"%d of %d covered" % (len(coverage.sets), coverage.set_count)
        legacy = getattr(coverage, "legacy", 0)
        if legacy:
            text += (u" (the Legacy set, wholly optional, not counted)" if legacy == 1 else
                     u" (the %d Legacy sets, wholly optional, not counted)" % legacy)
        found.append((u"Character sets", text + (u": %s" % u", ".join(coverage.sets) if coverage.sets else u"")))
    whole, checked = getattr(coverage, "script_sets", (0, 0))
    if checked:
        found.append((u"Scripts (Unicode)", u"%d of %d covered whole" % (whole, checked)))
    return found


def summary_languages(layout, coverage, mode):
    """The languages' counts, script by script, the character sets covered, and the small print; then
    (mode "covered" or "reach") the languages themselves under their scripts, A to Z."""
    layout.text(u"Language coverage", 9, "bold", gap=8.0, keep=40.0)
    layout.text(coverage.sentence())
    for script in coverage.scripts:
        layout.field(script.script, script.text)
    for label, text in set_fields(coverage):
        layout.field(label, text)
    for index, note in enumerate(coverage.notes()):
        layout.text(note, SUMMARY_NAME_SIZE, "quiet", gap=0.0 if index else 3.0)
    if mode not in ("covered", "reach"):
        return
    lists = []
    for script in coverage.scripts:
        if script.covered:
            lists.append((u"%s, covered (%d)" % (script.script, len(script.covered)), language_names(script.covered)))
        if mode == "reach" and script.reach:
            lists.append((u"%s, within reach (%d)" % (script.script, len(script.reach)),
                          language_names(script.reach)))
    marked = set(mark_word(mark) for script in coverage.scripts
                 for _, mark, _ in script.covered + (script.reach if mode == "reach" else []) if mark)
    first = True
    for word, key in EVIDENCE_KEYS:  # a key for each mark the lists show
        if lists and word in marked:
            layout.text(key, SUMMARY_NAME_SIZE, "quiet", gap=6.0 if first else 0.0, keep=40.0)
            first = False
    for heading, names in lists:
        layout.text(heading, 8, "bold", gap=5.0, keep=SUMMARY_NAME_LEADING * SUMMARY_MIN_ROWS)
        summary_names(layout, names)


VERTICAL_NOTE = u"%s (written top to bottom: set here horizontally, left to right, as encoded; vertical setting is not done)"


def section_summary(layout, font, summary, date, left_out=(), vertical=()):
    """The summary: the family's name in the font itself, then, in the labels' typeface, the font and
    the proof, its vertical metrics, its OpenType features and kerning, and the languages it covers.
    vertical: the scripts written top to bottom the proof sets horizontally (vertical_scripts)."""
    title_font = summary.font or font
    title = summary.title or font.family
    sequence = title_font.sequence(title) if title else None
    if sequence:
        placed, width = place(title_font, sequence)
        size = float(SUMMARY_TITLE_SIZE)
        if width * size / title_font.upm > layout.width():  # a long name: smaller, down to a size still a title
            size = max(float(SUMMARY_TITLE_MIN), layout.width() * title_font.upm / width)
            placed, width = clip(title_font, sequence, layout.width() * title_font.upm / size)
        layout.glyphs(title_font, placed, width, size)
        layout.y += 4.0
    else:  # the font lacks a character of its own name: the labels' typeface says it
        layout.text(title, 16, "bold", keep=30.0)
    rows = list(summary.rows)
    rows.append((u"Proofed", u"%s, with FreeLab Proof, from the font's own outlines in FontLab" % date))
    rows.append((u"Applied", APPLIED))
    if left_out:
        rows.append((u"No text for", u"%s (shaping is not done)" % u", ".join(left_out)))
    if vertical:
        rows.append((u"Set horizontally", VERTICAL_NOTE % u", ".join(vertical)))
    for label, text in rows:
        layout.field(label, text)
    if summary.metrics:
        layout.text(u"Vertical metrics", 9, "bold", gap=8.0, keep=70.0)
        summary_table(layout, METRIC_HEADER, summary.metrics)
        for label, text in summary.metric_notes:
            layout.field(label, text)
    if summary.features or summary.kerning:
        layout.text(u"OpenType", 9, "bold", gap=8.0, keep=30.0)
        if summary.features:
            layout.field(u"Features", summary.features)
        if summary.kerning:
            layout.field(u"Kerning", summary.kerning)
    # (the languages and scripts covered close the proof, section_coverage: the summary's start keeps to
    # the font's technical data, its info following, before the glyphs)


def section_masters(layout, fonts, line, rtl):
    layout.heading(TITLES["masters"])
    layout.text(u"The same text in each master, kerning applied.", style="quiet")
    for font in fonts:
        layout.text(font.master, 8, "bold", gap=6.0, keep=line_height(font, MASTERS_SIZES[0]))
        for size in MASTERS_SIZES:
            room = layout.width() * font.upm / size
            placed, width = clip(font, line, room, rtl)
            layout.glyphs(font, placed, width, size, align="right" if rtl else "left", rtl=rtl)


class Proof(object):
    """A laid-out proof: its pages, and what it counted."""

    def __init__(self, pages, masters, kerned, left_out, groups):
        self.pages, self.masters, self.kerned = pages, masters, kerned
        self.left_out, self.groups = left_out, groups

    def section_pages(self):
        """{section key: pages it is on}."""
        counts = {}
        for page in self.pages:
            for key in set(page.sections):
                counts[key] = counts.get(key, 0) + 1
        return counts


def encoded_code(font, name):
    """A glyph's code point, or for an unencoded one (a.ss01) its base's (a's), or None."""
    code = font.code_of(name)
    if code is None and u"." in name:
        by_name = getattr(font, "_by_name", None)
        if by_name is None:
            by_name = font._by_name = dict((n, c) for c, n in font.cmap.items())
        code = by_name.get(name.split(u".")[0])
    return code


def glyph_script(font, name):
    """The script word of a glyph (u"LATIN", u"CYRILLIC"), for an encoded letter or an unencoded form of
    one (a.ss01: a's); None for figures, punctuation, symbols, letters whose name names no script
    (NOT_SCRIPTS), and the rest."""
    code = encoded_code(font, name)
    if code is None:
        return None
    kind = script_case(code)
    return kind[0] if kind and kind[0] != "FIGURE" and kind[0] not in NOT_SCRIPTS else None


def scope_names(font, scope, languages=()):
    """The glyph names a proof scope keeps: ("script", word): that script's letters; ("language", Language):
    its base and auxiliary letters; with every glyph that is no letter (figures, punctuation, symbols, an
    unencoded glyph of none) but those Unicode's Script property gives another script (sign_scripts:
    Adlam's digits leave a Latin proof; a language's script is that of its letters). A glyph of a code
    point Unicode does not assign (unknown_code) is no glyph of either kind: left out, unless the language
    lists it."""
    kind, value = scope
    wanted = set()
    if kind == "language":
        for chars in (value.base, getattr(value, "auxiliary", None) or []):
            for ch in chars:
                wanted.update(code_points(ch))  # (a narrow build's pair of units read as one code point)
        words = set(found[0] for found in (script_case(code) for code in wanted) if found and found[0] != "FIGURE")
    else:
        words = set([value])
    kept = set()
    for name in font.glyphs:
        code = encoded_code(font, name)
        if kind == "language" and code in wanted:
            kept.add(name)
            continue
        script = glyph_script(font, name)
        if script is None:
            if unknown_code(code):
                continue
            signs = sign_scripts(code)
            if signs is None or signs & words:
                kept.add(name)
        elif kind == "script" and script == value:
            kept.add(name)
    return kept


def restricted(font, names):
    """A copy of a ProofFont that has only names (its kerning between them too)."""
    keep = [name for name in font.glyphs if name in names]
    codes = dict((name, font.codes.get(name, ())) for name in keep)
    kerning = dict((pair, value) for pair, value in font.kerning.items() if pair[0] in names and pair[1] in names)
    return ProofFont(font.family, font.master, font.upm, keep, codes, font._advance, kerning, font.ascender,
                     font.descender, font._ink, font._colored)


def covered_languages(font, languages):
    """The languages the font has every base character of, the most spoken first (Hyperglot's speakers):
    those a proof can set text in."""
    codes = set(code for code, name in font.cmap.items() if font.has(name))
    covered = [language for language in languages
               if language.base and all(has_character(codes, ch) for ch in language.base)]
    covered.sort(key=lambda language: -(language.speakers or 0))
    return covered


def scope_label(scope):
    """A proof scope as the dropdown and the summary name it: "Latin only", "Spanish (Latin)"; u"" for none."""
    if scope is None or scope == MORE:
        return u""
    if scope[0] == "script":
        return u"%s only" % SCRIPT_LABELS.get(scope[1], scope[1].title())
    return u"%s (%s)" % (scope[1].name, scope[1].script)


def same_scope(one, other):
    """Whether two scopes are the same script, or the same language in the same script."""
    if one is None or other is None or one[0] != other[0] or one == MORE:
        return False
    if one[0] == "script":
        return one[1] == other[1]
    return (one[1].iso, one[1].script) == (other[1].iso, other[1].script)


def split_languages(covered, expanded=True, kept=None):
    """(the most spoken languages, listed first, the others, whether the others are listed): the most
    spoken SCOPE_LANGUAGES_TOP first, then the others, all of them (the owner asked why they waited
    behind More languages...: the dropdown opens as a list of LONG_CHOICES rows, scrolled, and a name's
    first letters typed find it). A short list is one block (SCOPE_LANGUAGES_SLACK). expanded and kept
    are no longer needed: every language is listed."""
    if len(covered) <= SCOPE_LANGUAGES_TOP + SCOPE_LANGUAGES_SLACK:
        return list(covered), [], True
    return list(covered[:SCOPE_LANGUAGES_TOP]), list(covered[SCOPE_LANGUAGES_TOP:]), True


def scope_rows(scripts, covered, expanded=False, kept=None):
    """The Proof dropdown's rows, [(text, scope)]: every script (scope None); each script the font has
    letters of; then, after a separator (text None), the languages it covers, the most spoken first, a
    sensible number of them; then the others after a second separator, A to Z (a long list is found by
    eye or by typing a name's first letters). More languages... (scope MORE) is left for a list that
    holds the others back (split_languages no longer does)."""
    rows = [(u"Every script", None)]
    rows += [(scope_label(("script", word)), ("script", word)) for word in scripts]
    if not covered:
        return rows
    first, rest, listed = split_languages(covered, expanded, kept)
    rows.append((None, None))
    rows += [(scope_label(("language", one)), ("language", one)) for one in first]
    if rest and not listed:
        rows.append((MORE_LANGUAGES, MORE))
    elif rest:
        rows.append((None, None))
        rest.sort(key=lambda one: ((u"%s" % one.name).lower(), u"%s" % one.script))
        rows += [(scope_label(("language", one)), ("language", one)) for one in rest]
    return rows


def scope_help(covered, rest, listed):
    """The Proof dropdown's What's This, with the counts: covered, the languages the font covers; rest,
    those not among the most spoken; listed: whether the dropdown lists them."""
    text = (u"What the proof covers: every script the font has, one of them (its letters, with the figures, "
            u"punctuation, and symbols), or, after the line, one language the font covers (its letters; the text "
            u"section shows its sample alone). ")
    if not covered:
        text += (u"No language is listed: the font has every base character of none of the languages Hyperglot "
                 u"describes. ")
    else:
        text += u"The font has every base character of %s Hyperglot describes" % counted(covered, u"language")
        if not rest:
            text += u": it is listed. " if covered == 1 else u": all are listed, the most spoken first. "
        elif listed:
            text += u": the %d most spoken come first, then the %s, A to Z. " % (
                covered - rest, u"other one" if rest == 1 else u"other %s" % u"{:,}".format(rest))
        else:
            text += u": the %d most spoken are listed, and <i>More languages\N{HORIZONTAL ELLIPSIS}</i> lists %s " \
                    u"after them, A to Z. " % (covered - rest, u"the other one" if rest == 1
                                               else u"the other %s" % u"{:,}".format(rest))
    return text + (u"Languages within reach are not offered: a language's text is set only when the font has all its "
                   u"base characters, and <i>Font Check</i> lists what the others lack.")


def settings_path(ak):
    return os.path.join(ak.state_dir(), SETTINGS_FILE)


def read_settings(ak):
    """The settings kept from one FontLab session to the next ({} when there are none yet)."""
    import io
    try:
        with io.open(settings_path(ak), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def write_settings(ak, data):
    import io
    try:
        folder = os.path.dirname(settings_path(ak))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(settings_path(ak), "w", encoding="utf-8") as handle:
            handle.write(u"%s" % json.dumps(data, indent=1, sort_keys=True))
    except (IOError, OSError):
        pass


def build_proof(fonts, options=None, languages=(), date=None, info=None, summary=None):
    """The pages of a proof of fonts (a ProofFont per master, the first the one the text is chosen
    for): the summary (a Summary; None: an about block in its place), the font's info (info:
    [(label, text)], None for none), the masters side by side (several masters), then each master's
    sections."""
    options = options or Options()
    date = date or time.strftime("%Y-%m-%d")
    layout = Layout(page_size(options.page))
    first = fonts[0]
    groups, left_out = choose_samples(first, languages)
    vertical = vertical_scripts(first)
    line, rtl = waterfall_line(first, groups)
    label = ALL_MASTERS if len(fonts) > 1 else first.master
    kerned = []
    for font in fonts:
        kerned.append(sum(1 for (left, right), value in font.kerning.items()
                          if value and (options.keep is None or options.keep(left, right))))
    if summary is not None:  # (it says what the about block says, and more)
        layout.begin("summary", label)
        section_summary(layout, first, summary, date, left_out, vertical)
    else:
        layout.begin("about", label)
        layout.text(first.family, 16, "bold", keep=30.0)
        masters = u", ".join(font.master for font in fonts)
        layout.text(u"%s; %s: %s." % (counted(len(first.glyphs), u"glyph"), counted(len(fonts), u"master"), masters))
        layout.text(u"Drawn from the font's own outlines. Kerning applied as FontLab applies it, classes resolved "
                    u"(%s). OpenType features not applied: no ligatures, no contextual or localized forms, no mark "
                    u"positioning; each character shows its own glyph." % u", ".join(
                        u"%s %s" % (counted(count, u"kerned pair"), u"in " + font.master)
                        for count, font in zip(kerned, fonts)))
        if left_out:
            layout.text(u"No text for %s: shaping is not done." % u", ".join(left_out))
        if vertical:
            layout.text(u"Set horizontally: %s." % (VERTICAL_NOTE % u", ".join(vertical)))
        layout.text(u"Made with FreeLab Proof, %s." % date, style="quiet")
    if info is not None:  # (with the about block: which font, which version, before any glyph)
        layout.begin("info", label)
        section_info(layout, info)
    if len(fonts) > 1 and line:
        layout.begin("masters", label)
        section_masters(layout, fonts, line, rtl)
    builders = {
        "charset": lambda font: section_charset(layout, font),
        "waterfall": lambda font: section_waterfall(layout, font, line, rtl, options.waterfall),
        "text": lambda font: section_text(layout, font, groups, options.text_sizes, left_out),
        "kerning": lambda font: section_kerning(layout, font, options.keep, collisions=options.collisions),
        "spacing": lambda font: section_spacing(layout, font, collisions=options.collisions),
        "diacritics": lambda font: section_diacritics(layout, font),
        "figures": lambda font: section_figures(layout, font),
    }
    for font in fonts:
        for key, _ in SECTIONS:
            if key in options.sections:
                layout.begin(key, font.master)
                builders[key](font)
    if summary is not None and summary.coverage is not None:  # the summary's coverage, at the very end
        layout.begin("coverage", label)
        summary_languages(layout, summary.coverage, summary.languages)
    layout.finish(first.family, date)
    return Proof(layout.pages, [font.master for font in fonts], kerned, left_out, groups)


def common_filter(common, codes, ak=None):
    """keep(left, right) for the pairs common in text: common {two characters: rank} (Auto Kerning's
    common_pairs, in text order), codes {glyph name: code points}; unencoded glyphs are never common.
    (left, right) is a kerning key, in text order too, a right-to-left pair's right glyph first (as
    FontLab keeps it); with Auto Kerning (ak), a bracket there is looked up as typed (the ")" glyph
    first in a Hebrew pair is an opening parenthesis typed "(")."""
    def text_of(name):
        found = codes.get(name)
        return char_of(found[0]) if found else None

    def keep(left, right):
        a, b = text_of(left), text_of(right)
        if a is None or b is None:
            return False
        return (ak.text_order(*ak.screen_of_key(a, b, a, b)) if ak is not None else a + b) in common

    return keep


def kerning_note(kerned, masters, b):
    """What the top line says of the kerning applied: each master's kerned pairs counted, in bold, "no
    kerned pairs" at 0 (owner's image 228: "0 kerned pairs"); the master named only when several are."""
    if not any(kerned):
        return u"No kerned pairs to apply"
    if len(masters) == 1:
        return u"Kerning applied (%s, classes resolved)" % b(counted(kerned[0], u"kerned pair"))
    parts = [(u"%s in %s" % (b(counted(count, u"kerned pair")), b(master)) if count else
              u"no kerned pairs in %s" % b(master)) for count, master in zip(kerned, masters)]
    return u"Kerning applied (%s, classes resolved)" % u", ".join(parts)


def status_line(named, proof, size, ak):
    """The window's top line once a proof is laid out (rich text): named (the font and master, in bold:
    ProofDialog.font_named), its pages counted in bold, each section's pages after its tick box's name in
    italics (a number in parentheses with no noun of its own: bold alone, the suite's one rule for counts),
    then what is applied."""
    text = u"%s: %s (%s)." % (named, ak.b(counted(len(proof.pages), u"page")), size)
    counts = proof.section_pages()
    parts = [u"%s (%s)" % (ak.i(title), ak.b(grouped(counts[key])))
             for key, title in ((("summary", TITLES["summary"]),) + SECTIONS) if key in counts]
    if parts:
        text += u" Pages per section: %s." % u", ".join(parts)
    text += u" %s; OpenType features not applied." % kerning_note(proof.kerned, proof.masters, ak.b)
    if proof.left_out:
        text += u" No text for %s: %s shaping." % (ak.html(u", ".join(proof.left_out)),
                                                  u"it needs" if len(proof.left_out) == 1 else u"they need")
    return text


def pdf_name(family, master, date):
    """A file name for the proof: "Family Regular proof 2026-11-11.pdf", without the characters
    Windows forbids."""
    name = u"%s %s proof %s.pdf" % (family or u"Font", master or u"", date)
    name = re.sub(u"[\\\\/:*?\"<>|\x00-\x1f]+", u" ", name)
    return re.sub(u"\\s+", u" ", name).strip()


# ---------------------------------------------------------------------------
# Drawing (Qt's modules handed in: PythonQt in FontLab, PySide6 offline)
# ---------------------------------------------------------------------------

def _flag(owner, group, name):
    """A Qt enum value: PythonQt names it on its class (Qt.AlignLeft), PySide6 in its enum too."""
    try:
        return getattr(owner, name)
    except AttributeError:
        return getattr(getattr(owner, group), name)


ALIGNS = {"left": "AlignLeft", "center": "AlignHCenter", "right": "AlignRight"}


def page_colors(mode, ink=None, paper=None):
    """(ink, paper) as (red, green, blue) for the pages, the PDF's and the preview's alike: the
    window's text and background colors for "window" (when given), else black on white."""
    if mode == "window" and ink is not None and paper is not None:
        return tuple(int(c) for c in ink[:3]), tuple(int(c) for c in paper[:3])
    return PRINT_COLORS


def colors_label(mode, ink, paper):
    """How the colors read, for the log: "black on white", or "the window's: light on dark"."""
    if (tuple(ink), tuple(paper)) == PRINT_COLORS:
        return u"black on white"
    light = lambda rgb: 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] >= 128
    return u"the window's: %s on %s" % (u"light" if light(ink) else u"dark", u"light" if light(paper) else u"dark")


COLLISION_ON_LIGHT = (205, 25, 20)  # the red of a collision on light paper (Options.collisions)
COLLISION_ON_DARK = (240, 96, 86)  # ... and on dark paper (the log's error red)


def colliding_indexes(placed, overlaps):
    """The indexes of the glyphs of a line ([(name, x)] in font units, in the order set) whose ink overlaps
    their neighbor's: overlaps(first, second, offset) says whether the second glyph's ink, offset units
    right of the first's origin, overlaps the first's. Only neighbors: a space between them keeps them
    apart anyway."""
    found = set()
    for index in range(len(placed) - 1):
        (first, x1), (second, x2) = placed[index], placed[index + 1]
        if overlaps(first, second, x2 - x1):
            found.update((index, index + 1))
    return found


def ink_overlaps(first, second, offset):
    """Whether two glyphs' outlines (QPainterPaths in font units, None for none) overlap, the second offset
    units right of the first: their boxes first, then their filled areas (a touch along an edge is no
    overlap). False when either cannot be read."""
    if first is None or second is None:
        return False
    try:
        box_a, box_b = first.boundingRect(), second.boundingRect()
        if box_a.isEmpty() or box_b.isEmpty() or box_b.left() + offset >= box_a.right() \
                or box_b.right() + offset <= box_a.left():
            return False
        return bool(first.intersects(second.translated(offset, 0)))
    except Exception:
        return False


class Renderer(object):
    """Draws a page's items with a QPainter, scale device pixels per point. path_of(master, name):
    a glyph's QPainterPath in font units, y up (None: nothing to draw). parts_of(master, name): a color
    glyph's [(QPainterPath, QColor)], drawn in its own colors whatever the ink (None: the ink)."""

    def __init__(self, QtCore, QtGui, path_of, family=u"", ink=None, parts_of=None):
        self.QtCore, self.QtGui = QtCore, QtGui
        self.path_of = path_of
        self.parts_of = parts_of
        self.family = family
        self.ink = QtGui.QColor(ink) if ink is not None else QtGui.QColor(0, 0, 0)
        # The red of a collision (Options.collisions), as the log's errors: a lighter one on dark paper
        light_ink = self.ink.lightness() > 127 if hasattr(self.ink, "lightness") else False
        self.alert = QtGui.QColor(*(COLLISION_ON_DARK if light_ink else COLLISION_ON_LIGHT))
        self.overlaps = {}  # (master, first, second, offset): whether their ink overlaps (colliding)
        self.quiet = QtGui.QColor(self.ink)
        self.quiet.setAlpha(150)
        self.rule = QtGui.QColor(self.ink)
        self.rule.setAlpha(90)
        self.fonts = {}
        Qt = QtCore.Qt
        self.aligns = dict((key, int(_flag(Qt, "AlignmentFlag", name)) | int(_flag(Qt, "AlignmentFlag", "AlignVCenter")))
                           for key, name in ALIGNS.items())
        self.elide = _flag(Qt, "TextElideMode", "ElideRight")
        self.no_brush = _flag(Qt, "BrushStyle", "NoBrush")
        self.antialiasing = _flag(QtGui.QPainter, "RenderHint", "Antialiasing")

    def font(self, pixels, bold):
        key = (pixels, bold)
        if key not in self.fonts:
            font = self.QtGui.QFont(self.family) if self.family else self.QtGui.QFont()
            font.setPixelSize(pixels)
            font.setBold(bold)
            self.fonts[key] = font
        return self.fonts[key]

    def colliding(self, item):
        """The indexes in a line of glyphs (item.placed) of the glyphs whose ink overlaps the next one's or
        the one before's (colliding_indexes), each pair's answer kept for the proof (the same pairs come
        back on every page of strings)."""
        def overlaps(first, second, offset, master=item.master):
            key = (master, first, second, round(offset, 1))
            if key not in self.overlaps:
                self.overlaps[key] = ink_overlaps(self.path_of(master, first), self.path_of(master, second), offset)
            return self.overlaps[key]
        return colliding_indexes(item.placed, overlaps)

    def draw(self, painter, page, scale):
        QtCore, QtGui = self.QtCore, self.QtGui
        painter.setRenderHint(self.antialiasing, True)
        brush = QtGui.QBrush(self.ink)
        rule = QtGui.QPen(self.rule)
        rule.setWidthF(max(1.0, 0.5 * scale))
        alert = QtGui.QBrush(self.alert)
        for item in page.items:
            if item.kind == "glyphs":
                factor = item.size / item.upm * scale
                red = self.colliding(item) if getattr(item, "collide", False) else ()
                for index, (name, x) in enumerate(item.placed):
                    path = self.path_of(item.master, name)
                    if path is None:
                        continue
                    painter.save()
                    painter.translate(item.x * scale + x * factor, item.baseline * scale)
                    painter.scale(factor, -factor)
                    parts = self.parts_of(item.master, name) if self.parts_of is not None else None
                    if parts:  # a color glyph: as the font draws it, on any paper
                        for part, color in parts:
                            painter.fillPath(part, QtGui.QBrush(color))
                    else:
                        painter.fillPath(path, alert if index in red else brush)
                    painter.restore()
            elif item.kind == "text":
                font = self.font(max(1, int(round(item.size * scale))), item.style == "bold")
                rect = QtCore.QRect(int(round(item.x * scale)), int(round(item.y * scale)),
                                    int(round(item.width * scale)), int(round(item.height * scale)))
                text = QtGui.QFontMetrics(font).elidedText(item.text, self.elide, rect.width())
                painter.setFont(font)
                painter.setPen(self.quiet if item.style == "quiet" else self.ink)
                painter.drawText(rect, self.aligns.get(item.align, self.aligns["left"]), text)
            elif item.kind == "line":
                painter.setPen(rule)
                painter.drawLine(QtCore.QLineF(item.x1 * scale, item.y1 * scale, item.x2 * scale, item.y2 * scale))
            elif item.kind == "frame":
                painter.setPen(rule)
                painter.setBrush(QtGui.QBrush(self.no_brush))
                painter.drawRect(QtCore.QRectF(item.x * scale, item.y * scale, item.width * scale, item.height * scale))


PDF_RESOLUTION = 600  # dots per inch the PDF's coordinates are given in (its outlines stay vectors)


def write_pdf(QtCore, QtGui, path, pages, renderer, page_key="A4", title=u"", progress=None, paper=None):
    """Writes the pages to a PDF file, each filled with paper first (a QColor; None: left white);
    progress(done, total) after each page. Raises when the file cannot be written."""
    writer = QtGui.QPdfWriter(path)
    try:
        writer.setPageSize(getattr(QtGui.QPagedPaintDevice, page_key))  # Qt 5 (FontLab 7's)
    except Exception:
        page_id = _flag(QtGui.QPageSize, "PageSizeId", page_key)
        writer.setPageSize(QtGui.QPageSize(page_id))  # Qt 6
    try:
        writer.setPageMargins(QtCore.QMarginsF(0, 0, 0, 0))
    except Exception:
        pass
    writer.setResolution(PDF_RESOLUTION)
    for setter, value in (("setTitle", title), ("setCreator", u"FreeLab Proof")):
        try:
            getattr(writer, setter)(value)
        except Exception:
            pass
    painter = QtGui.QPainter(writer)
    try:  # ended whatever happens: a painter left open on a freed device aborts FontLab
        if not painter.isActive():
            raise IOError(u"Qt could not open %s for writing" % path)
        scale = PDF_RESOLUTION / 72.0
        width, height = page_size(page_key)
        for index, page in enumerate(pages):
            if index:
                writer.newPage()
            if paper is not None:  # (a little past the page's edges: no white hairline at them)
                painter.fillRect(QtCore.QRectF(-scale, -scale, (width + 2) * scale, (height + 2) * scale), paper)
            renderer.draw(painter, page, scale)
            if progress is not None:
                progress(index + 1, len(pages))
    finally:
        painter.end()
    return writer


def fit_scale(size, page_points):
    """Pixels per point for a page to fit size (width, height in pixels) whole."""
    return max(0.01, min(size[0] / float(page_points[0]), size[1] / float(page_points[1])))


# The preview's zoom (the Zoom dropdown, Ctrl+wheel, Ctrl+plus and Ctrl+minus over the page): the page
# fitted whole, or a share of its printed size on a screen at 96 pixels an inch (100%: as large as the
# printed page). Past ZOOM_MOST_PIXELS device pixels, a page is drawn coarser rather than larger.
ZOOMS = ((None, u"Fit page"), (0.5, u"50%"), (0.75, u"75%"), (1.0, u"100%"), (1.5, u"150%"), (2.0, u"200%"),
         (3.0, u"300%"), (4.0, u"400%"))
SCREEN_POINT = 96.0 / 72.0  # pixels a point at 100%
ZOOM_MOST_PIXELS = 36000000  # a zoomed page's device pixels at most (about 140 MB as a picture)


def zoom_scale(zoom, size, page_points):
    """Pixels per point of the preview: the page fitted to size (width, height in pixels) for zoom
    None, else zoom times its printed size (SCREEN_POINT pixels a point at 1.0)."""
    return fit_scale(size, page_points) if zoom is None else max(0.01, float(zoom) * SCREEN_POINT)


def next_zoom(index, step, fitted):
    """The zoom's index in ZOOMS after a step (1: larger, -1: smaller) from index; from Fit page, the
    first zoom past the fitted one (fitted: its zoom, as a share of the printed size) that way; back to
    Fit page past the smallest zoom. The same index where there is none further."""
    zooms = [zoom for zoom, _ in ZOOMS]
    current = zooms[index] if 0 <= index < len(zooms) else None
    if current is None:
        found = [i for i, zoom in enumerate(zooms) if zoom is not None and (zoom > fitted + 1e-6 if step > 0
                                                                              else zoom < fitted - 1e-6)]
        if not found:
            return index
        return found[0] if step > 0 else found[-1]
    at = index + (1 if step > 0 else -1)
    if at < 0 or at >= len(zooms):
        return index
    return at


LEAVE_ALONE_PROP = "freelabLeaveAlone"  # (dark mode's and the shared module's name)


def leave_list_alone(combo):
    """A dropdown's list (a window of its own, which no flag on the box reaches) left as Qt draws it from
    the palette: dark mode's mapping of lists gave its light text ClearType's colored fringes."""
    try:
        view = combo.view()
        view.setProperty(LEAVE_ALONE_PROP, True)
        return view
    except Exception:
        return None


KEY_PRESS, WHEEL, SHORTCUT_OVERRIDE = 6, 31, 51  # QEvent's types
CONTROL_MODIFIER = 0x04000000
ZOOM_KEYS = {0x2B: 1, 0x3D: 1, 0x2D: -1, 0x30: "fit"}  # Qt.Key_Plus, Key_Equal, Key_Minus, Key_0


# The keys Proof zooms with, as FontLab's own View actions have them (Ctrl++ and Ctrl+= zoom in, Ctrl+- out,
# Ctrl+0 fits): application-wide shortcuts, which Qt matches before any widget sees the key wherever the
# key goes (live pass: each Ctrl+plus ran FontLab's actionZoomIn, and Proof never saw it). While Proof is
# the active window, FontLab's actions give those keys up (take_zoom_keys); they get them back whenever
# Proof stops being active, hides, or closes (give_back_zoom_keys), and a later Proof gives back what one
# left taken (a window that went away without the events).
ZOOM_SEQUENCES = (u"Ctrl++", u"Ctrl+=", u"Ctrl+-", u"Ctrl+0")
TAKEN_KEYS = "_freelab_proof_zoom_keys"  # on sys: [(action's objectName, its shortcuts as they were)]


def take_zoom_keys(QtGui, main):
    """FontLab's actions under main (its main window) that have one of ZOOM_SEQUENCES left without it, what
    they had noted on sys (TAKEN_KEYS) first; True when any was. Keys taken already: left as they are."""
    if main is None or getattr(sys, TAKEN_KEYS, None):
        return False
    taken = []
    for action in main.findChildren(QtGui.QAction):
        try:
            keys = [u"%s" % sequence.toString() for sequence in action.shortcuts()]
            if not any(key in ZOOM_SEQUENCES for key in keys) or not action.objectName:
                continue
            taken.append((u"%s" % action.objectName, keys))
            setattr(sys, TAKEN_KEYS, taken)  # (noted before it changes: given back whatever happens next)
            action.setShortcuts([QtGui.QKeySequence(key) for key in keys if key not in ZOOM_SEQUENCES])
        except Exception:
            continue
    return bool(taken)


def give_back_zoom_keys(QtGui, main):
    """The shortcuts take_zoom_keys took, given back to the actions of those names (found again under main:
    none is held meanwhile), each only where it still has none of them (FontLab's or the user's change
    since is kept); nothing noted afterwards. True when any was."""
    taken = getattr(sys, TAKEN_KEYS, None) or []
    if not taken:
        return False
    try:
        delattr(sys, TAKEN_KEYS)
    except Exception:
        pass
    if main is None:
        return False
    names = dict(taken)
    given = False
    for action in main.findChildren(QtGui.QAction):
        try:
            keys = names.get(u"%s" % action.objectName)
            now = [u"%s" % sequence.toString() for sequence in action.shortcuts()]
            if keys is None or any(key in ZOOM_SEQUENCES for key in now):
                continue
            action.setShortcuts([QtGui.QKeySequence(key) for key in keys])
            given = True
        except Exception:
            continue
    return given


def event_number(event, name):
    """An event's type, key, or modifiers as a number, whether PythonQt gives it as a method or a value, an
    int or a Qt enum or flags; None where it cannot be read."""
    value = getattr(event, name, None)
    try:
        value = value() if callable(value) else value
        return int(value)
    except Exception:
        return None


def wheel_steps(event):
    """1 (a wheel turned away: zoom in), -1, or 0, from its angle delta (a method or a value), its pixel
    delta, or the older delta()."""
    for name in ("angleDelta", "pixelDelta"):
        point = getattr(event, name, None)
        try:
            point = point() if callable(point) else point
            y = point.y() if callable(getattr(point, "y", None)) else point.y
            if y:
                return 1 if y > 0 else -1
        except Exception:
            continue
    delta = event_number(event, "delta")
    return (1 if delta > 0 else -1) if delta else 0


def page_turn(steps, value, low, high):
    """The page the wheel goes to over the preview, from where its scroll bar stands (value, between low and
    high: low == high when the page is shown whole): -1 (the page before) turned up at the top, 1 turned down
    at the bottom, else 0 (the page scrolls, or the wheel did not turn)."""
    if steps > 0 and value <= low:
        return -1
    if steps < 0 and value >= high:
        return 1
    return 0


def zoom_command(event, QtCore=None):
    """What a key or wheel event asks of the preview's zoom with Ctrl held: 1, -1 (0 for a wheel event with
    no turn), "fit" (Ctrl+0), or None (no Ctrl, another key, another event). The modifiers read from the
    event, else from Qt's (an event that gives none)."""
    kind = event_number(event, "type")
    if kind not in (KEY_PRESS, WHEEL, SHORTCUT_OVERRIDE):
        return None
    held = event_number(event, "modifiers")
    if held is None and QtCore is not None:
        try:
            held = int(QtCore.QCoreApplication.instance().keyboardModifiers())
        except Exception:
            held = None
    if held is None or not held & CONTROL_MODIFIER:
        return None
    if kind == WHEEL:
        return wheel_steps(event)
    return ZOOM_KEYS.get(event_number(event, "key"))


def page_pixmap(QtCore, QtGui, page, renderer, size, page_points, paper, ratio=1.0, zoom=None):
    """A page drawn into a pixmap that fits size (width, height in pixels) whole, or at zoom (a share of
    its printed size: zoom_scale), on paper; ratio: device pixels per pixel (a scaled display: drawn that
    much finer, so it stays crisp), lowered where the page would pass ZOOM_MOST_PIXELS."""
    ratio = max(1.0, float(ratio or 1.0))
    base = zoom_scale(zoom, size, page_points)
    pixels = page_points[0] * page_points[1] * (base * ratio) ** 2
    if pixels > ZOOM_MOST_PIXELS:  # (coarser, never larger: the device pixels first, then the page's)
        ratio = max(1.0, ratio * (ZOOM_MOST_PIXELS / pixels) ** 0.5)
        pixels = page_points[0] * page_points[1] * (base * ratio) ** 2
        if pixels > ZOOM_MOST_PIXELS:
            base *= (ZOOM_MOST_PIXELS / pixels) ** 0.5
    scale = base * ratio
    width, height = max(1, int(page_points[0] * scale)), max(1, int(page_points[1] * scale))
    pixmap = QtGui.QPixmap(width, height)
    pixmap.fill(paper)
    painter = QtGui.QPainter(pixmap)
    try:
        renderer.draw(painter, page, scale)
        painter.setPen(renderer.rule)
        painter.setBrush(QtGui.QBrush(renderer.no_brush))
        painter.drawRect(0, 0, width - 1, height - 1)
    finally:
        painter.end()
    if ratio != 1.0:
        try:
            pixmap.setDevicePixelRatio(ratio)
        except Exception:  # (a Qt without it: drawn again at the window's pixels, or it would show too large)
            return page_pixmap(QtCore, QtGui, page, renderer, size, page_points, paper, zoom=zoom)
    return pixmap


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


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


def documents_folder(QtCore):
    try:
        found = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
        if found:
            return u"%s" % found
    except Exception:
        pass
    return os.path.join(os.path.expanduser(u"~"), u"Documents")


HELP = u"""<b>FreeLab Proof</b><br>
A PDF proof of the current font, drawn from its own outlines in FontLab: nothing is exported or
installed, and the font is not changed.<br><br>
Pick the sections: the <b>character set</b> (every glyph with its name and code point),
<b>waterfalls</b> and <b>text</b> at the sizes typed (sample text in each script the font covers,
from Font Check's language data), <b>kerning strings</b> (every kerned pair, or the common ones,
between control letters: HH?HOHO, nn?nono), <b>spacing strings</b> (each letter as HHxHOxOO or
nnxnoxoo, without kerning; <i>Draw colliding glyphs in red</i> marks the glyphs of both whose ink
overlaps the next one's), <b>diacritics</b>, and <b>figures and punctuation</b>; for the current
master, or for each master (with a page of the masters side by side). The proof opens on a
<b>summary</b>: the family's name in the font itself, the font and the master proofed, its vertical
metrics, and its OpenType features and kerning. The font's info follows (names, version, designer,
license, dates), then the glyphs; the scripts and languages it covers, as <i>Font Check</i> counts
them, close the proof (<i>Summary lists</i>: the covered languages, those within reach too, or the
counts alone).<br><br>
<i>Proof</i> limits the proof to one script, or to one language the font covers: the most spoken
come first, then the others, A to Z (type a name's first letters to find it).<br><br>
Kerning is applied as FontLab applies it, classes resolved. OpenType features are not: no ligatures,
no contextual or localized forms, no mark positioning, so each character shows its own glyph, and
scripts that need shaping (Arabic, the Indic scripts, Thai) get no text. Hebrew is set right to left,
its kerning strings too, each pair kerned as the font keeps it (its right glyph first).<br><br>
<i>Colors</i>: the PDF in this window's colors (light on dark in dark mode), or black on white for
printing; the page beside the list shows the PDF as it will be.<br><br>
The list shows the pages; select one to see it. <i>Save PDF</i> writes them all, <i>Open PDF</i> opens
the file saved. <i>Show in Glyph window</i> opens the page's lines in FontLab.
Click this help's <i>?</i> button, then any control, for what it does."""

DEFAULT_KERNING_SET = "all"


class ProofDialog(object):
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
        self.busy = False
        self.seen_history = None
        self.fonts, self.paths, self.font_glyphs, self.color_parts = {}, {}, None, {}
        self.proof = None
        self.page_options = Options()  # the settings the proof shown was laid out with
        self.saved = None
        self.gone_said = False  # the log said the PDF saved last is not there anymore
        self.info = None  # the font's info rows, read once per font
        self.facts = None  # what the summary reads of the font beyond its info (font_facts), once per font read
        self.kerning_counts = {}  # master: (kerning entries, classes), as its kerning was read
        self.facts_said = set()  # what the log said the summary leaves out, each once
        self.common = None  # {two characters: rank}, read when first needed
        self.languages = None
        self.keep = []  # Python references to the slots and filters PythonQt does not hold
        main = ak.AutoKerningDialog.main_window()
        try:
            give_back_zoom_keys(QtGui, main)  # (left taken by a window that went away without saying so)
        except Exception:
            pass
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Proof")
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        if hasattr(ak, "one_line"):
            ak.one_line(NO_FONT_LINE)  # (a no-font line: its two sentences on one line, owner's image 278)
        self.font_label = ak.status_label()
        layout.addWidget(self.font_label)
        # (the header's line: shown with no font too, the grayed controls under it)
        layout.addWidget(ak.header_separator() if hasattr(ak, "header_separator") else ak.separator())

        self.settings = read_settings(ak)  # the summary's two settings, kept between FontLab sessions
        self.captions = {}  # each control's caption (a label), by the control's name here: it shows the control's help

        def captioned(into, name, caption, control, tip, stretch=0):
            """A control after its caption, in the label form (owner's image 271: "Page: [A4]"): the help is
            the control's; the caption (ak.caption) shows it on a right-click, and grays with the control."""
            label = self.captions[name] = QtGui.QLabel(caption)
            control.setWhatsThis(tip)
            if hasattr(ak, "caption"):
                ak.caption(label, control)
            into.addWidget(label)
            into.addWidget(control, stretch)
            return control

        row = QtGui.QHBoxLayout()
        self.masters_box = captioned(row, "masters", "Masters:", QtGui.QComboBox(),
                                     u"The current master only, or each master in turn (each starting on a new "
                                     u"page, after a page of the masters side by side).")
        row.addSpacing(12)
        self.page_box = QtGui.QComboBox()
        for _, label, _ in PAGE_SIZES:
            self.page_box.addItem(label)
        captioned(row, "page", "Page:", self.page_box, u"The PDF's page size, portrait.")
        row.addSpacing(12)
        self.pairs_box = QtGui.QComboBox()
        for _, label in KERNING_SETS:
            self.pairs_box.addItem(label)
        captioned(row, "pairs", "Kerning strings:", self.pairs_box,
                  u"Every kerned pair (a font with class kerning can have tens of thousands: the PDF grows with them), "
                  u"or only the pairs common in text (the list <i>Auto Kerning</i>'s <i>Common pairs</i> uses).")
        row.addSpacing(12)
        self.scope_box = captioned(row, "scope", "Proof:", QtGui.QComboBox(), scope_help(0, 0, True))
        self.scopes = [None]
        self.scope_kept = None  # the scope chosen last (the dropdown is filled again around it)
        self.scope_expanded = False  # More languages... was chosen: the dropdown lists every covered language
        self.scope_box.addItem(u"Every script")
        row.addSpacing(12)
        self.colors_box = QtGui.QComboBox()
        for _, label in COLOR_MODES:
            self.colors_box.addItem(label)
        captioned(row, "colors", "Colors:", self.colors_box,
                  u"The PDF's colors: this window's (its text on its background, light on dark in dark mode), or "
                  u"black on white, for printing. The page shown beside the list is the PDF as it will be.")
        row.addSpacing(12)
        self.zoom_box = QtGui.QComboBox()
        for _, label in ZOOMS:
            self.zoom_box.addItem(label)
        captioned(row, "zoom", "Zoom:", self.zoom_box,
                  u"The page shown beside the list: whole (<i>Fit page</i>), or at a share of its printed size "
                  u"(100%: as large as printed), scrolled. <i>Ctrl</i> with the mouse wheel over the page, or "
                  u"<i>Ctrl+plus</i> and <i>Ctrl+minus</i> in this window, zoom in and out; <i>Ctrl+0</i> fits it "
                  u"again (in this window, not FontLab's view). The PDF is the same at every zoom.")
        row.addStretch(1)
        layout.addLayout(row)
        # Their lists open as windows of their own, which dark mode took for one of FontLab's lists and
        # mapped: light text with ClearType's colored fringes, on the Proof dropdown that opens over the
        # page (owner's report 162). Drawn from the dark palette, as the boxes are, they are left alone.
        for box in (self.masters_box, self.page_box, self.pairs_box, self.scope_box, self.colors_box, self.zoom_box):
            leave_list_alone(box)

        checks = QtGui.QHBoxLayout()
        self.summary_box = QtGui.QCheckBox(TITLES["summary"])
        self.summary_box.setChecked(self.settings.get("summary") is not False)
        self.summary_box.setWhatsThis(u"The proof's first page: the family's name in the font itself, then the font and "
                                      u"the master proofed, the version and dates the font records, its units per em, "
                                      u"its counts of glyphs and of encoded characters, its vertical metrics, its "
                                      u"OpenType features and kerning, and the scripts and languages it covers, as "
                                      u"<i>Font Check</i> counts them, with the data's sources. Unticked, a few lines "
                                      u"about the proof take its place. Kept from one FontLab session to the next.")
        checks.addWidget(self.summary_box)
        self.section_boxes = {}
        tips = {"charset": u"Every glyph in a grid, in the font's order, with its name and code point.",
                "waterfall": u"A line of sample text at each waterfall size.",
                "text": u"A few lines of sample text in each script the font covers, at each text size.",
                "kerning": u"Every kerned pair between control letters (HH?HOHO, nn?nono), grouped by first glyph "
                           u"(the right one in a right-to-left pair, set right to left).",
                "spacing": u"Each letter and figure between control letters (HHxHOxOO, nnxnoxoo), without kerning.",
                "diacritics": u"The letters with diacritics, each after its base letter, and the marks.",
                "figures": u"Figures and their alternates, punctuation, and symbols, alone and between letters."}
        for key, label in SECTIONS:
            box = QtGui.QCheckBox(label)
            box.setChecked(True)
            box.setWhatsThis(tips[key])
            checks.addWidget(box)
            self.section_boxes[key] = box
        checks.addSpacing(12)
        # (owner's image 348: off at first, a script font's letters may overlap on purpose)
        self.collisions_box = QtGui.QCheckBox(COLLISIONS_LABEL)
        self.collisions_box.setChecked(bool(self.settings.get("collisions")))
        self.collisions_box.setWhatsThis(u"Draws in red, in <i>Kerning strings</i> and <i>Spacing strings</i>, the glyphs "
                                         u"whose ink overlaps the next glyph's, kerning applied (the kerning strings) "
                                         u"or not (the spacing strings), in the preview and in the PDF. Off at first: "
                                         u"the letters of a script font may join on purpose. Kept from one FontLab "
                                         u"session to the next.")
        checks.addWidget(self.collisions_box)
        checks.addStretch(1)
        layout.addLayout(checks)

        sizes = QtGui.QHBoxLayout()
        self.languages_box = QtGui.QComboBox()
        for _, label in SUMMARY_LANGUAGES:
            self.languages_box.addItem(label)
        leave_list_alone(self.languages_box)  # (its list as the other dropdowns' lists: see above)
        keys = [key for key, _ in SUMMARY_LANGUAGES]
        if self.settings.get("summary_languages") in keys:
            self.languages_box.setCurrentIndex(keys.index(self.settings.get("summary_languages")))
        captioned(sizes, "languages", "Summary lists:", self.languages_box,
                  u"What the summary lists after the counts of each script's languages: the languages the font covers "
                  u"(under their scripts, A to Z, in five columns of small type; some 435 fill a page, and a longer "
                  u"list goes on over the following pages, never cut: a font with the Latin of Western and Central "
                  u"Europe covers nearly a thousand languages, about four pages), those and the languages within "
                  u"reach (each with how many characters it lacks), or none: the counts alone. They close the proof, "
                  u"on its <i>Language coverage</i> pages: a choice here shows the first of them. Kept from one "
                  u"FontLab session to the next.")
        sizes.addSpacing(12)
        self.waterfall_edit = captioned(
            sizes, "waterfall", "Waterfall sizes:", QtGui.QLineEdit(u" ".join(format_size(s) for s in WATERFALL_SIZES)),
            u"The waterfall's point sizes, a line of sample text at each: typed, separated by spaces or commas (%d to "
            u"%d points)." % SIZE_RANGE, 2)
        sizes.addSpacing(12)
        self.text_edit = captioned(
            sizes, "text", "Text sizes:", QtGui.QLineEdit(u" ".join(format_size(s) for s in TEXT_SIZES)),
            u"The point sizes the text section sets each script's sample text at: typed, separated by spaces or "
            u"commas (%d to %d points)." % SIZE_RANGE, 1)
        layout.addLayout(sizes)

        splitter = self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.page_list = QtGui.QListWidget()
        self.page_list.setProperty(ak.KEEP_SELECTION_PROP, True)  # (the pages' navigator: a page is always shown)
        ak.table_layout(self.page_list, grid=False)  # (as every FreeLab list: a list of names, no grid)
        self.page_list.setWhatsThis(u"The proof's pages: select one to see it. Double-click one to open its lines in a "
                                    u"<i>Glyph</i> window.")
        self.preview = QtGui.QLabel()
        self.preview.setProperty(ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn page alone
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setMinimumSize(200, 200)
        try:  # its picture never holds the window larger: it is drawn to fit the label
            self.preview.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)
        except Exception:
            pass
        shown = (u"The selected page as the PDF will be (in the colors <i>Colors</i> says): at <i>Fit page</i>, the "
                 u"whole page as large as the room here allows (drag the line beside the list, or make the window "
                 u"larger, to see it larger); zoomed (<i>Zoom</i>, or <i>Ctrl</i> with the mouse wheel), scrolled.")
        self.preview.setWhatsThis(shown)
        # The page in a scroll area: whole at Fit page, scrolled when zoomed (the label as large as the page)
        self.preview_area = QtGui.QScrollArea()
        self.preview_area.setProperty(ak.LEAVE_ALONE_PROP, True)  # (drawn from the palette; the page as drawn)
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_area.setFocusPolicy(QtCore.Qt.StrongFocus)  # (clicked, it takes Ctrl+plus and Ctrl+minus)
        self.preview_area.setWhatsThis(shown)
        self.preview_area.setWidget(self.preview)
        splitter.addWidget(self.page_list)
        splitter.addWidget(self.preview_area)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        try:
            splitter.setChildrenCollapsible(False)
            splitter.setSizes([180, 820])  # the room to the page
        except Exception:
            pass
        layout.addWidget(splitter, 1)
        self.log = ak.Log()
        layout.addWidget(self.log.widget)

        buttons = QtGui.QHBoxLayout()
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected page's lines of glyphs in a <i>Glyph</i> window.")
        self.restore_button = QtGui.QPushButton("Restore defaults")
        self.restore_button.setWhatsThis(u"Puts the sections, sizes, and choices back as the window first came.")
        self.save_button = QtGui.QPushButton(u"Save PDF\N{HORIZONTAL ELLIPSIS}")
        self.save_button.setWhatsThis(u"Writes every page to a PDF file you name (in <i>Documents</i> at first).")
        self.open_button = QtGui.QPushButton("Open PDF")
        self.open_button.setWhatsThis(u"Opens the PDF saved last in the application Windows opens PDF files with.")
        self.close_button = QtGui.QPushButton("Close")
        self.close_button.setWhatsThis(u"Closes this window. Nothing is written to the font; a PDF saved stays where "
                                       u"it was saved.")
        buttons.addWidget(self.glyph_window_button)
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        # (their parent the window: Qt deletes them with it, never PythonQt at a random moment)
        self.rebuild_timer = QtCore.QTimer(dialog)
        self.rebuild_timer.setSingleShot(True)
        self.rebuild_timer.setInterval(300)
        self.rebuild_timer.connect("timeout()", self.rebuild)
        self.preview_timer = QtCore.QTimer(dialog)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.connect("timeout()", self.show_page)
        self.saved_timer = QtCore.QTimer(dialog)  # (the window activated: the PDF saved last looked for again)
        self.saved_timer.setSingleShot(True)
        self.saved_timer.setInterval(0)
        self.saved_timer.connect("timeout()", self.update_buttons)
        self.colors_box.connect("currentIndexChanged(int)", lambda index: self.preview_timer.start())
        self.zoom_box.connect("currentIndexChanged(int)", lambda index: self.show_page())
        later = self.rebuild_timer.start
        for box in self.section_boxes.values():
            box.connect("toggled(bool)", lambda on: later())
        for box in (self.masters_box, self.page_box, self.pairs_box):
            box.connect("currentIndexChanged(int)", lambda index: later())
        self.scope_box.connect("currentIndexChanged(int)", self.scope_chosen)
        self.summary_box.connect("toggled(bool)", lambda on: self.summary_changed("summary"))
        self.collisions_box.connect("toggled(bool)", lambda on: self.summary_changed("collisions"))
        self.languages_box.connect("currentIndexChanged(int)", lambda index: self.summary_changed("summary_languages"))
        for edit in (self.waterfall_edit, self.text_edit):
            edit.connect("editingFinished()", later)
        self.page_list.connect("currentRowChanged(int)", lambda row: self.show_page())
        self.page_list.connect("itemDoubleClicked(QListWidgetItem*)", lambda item: self.show_in_glyph_window())
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.restore_button.connect("clicked()", self.restore_defaults)
        self.save_button.connect("clicked()", self.save_pdf)
        self.open_button.connect("clicked()", self.open_pdf)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        self.watch_size()
        ak.add_tools_button(dialog, "Proof", self.log)  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.read_font()
        self.history_timer = ak.watch_history(self)
        self.update_buttons()

    def watch_size(self):
        """The preview drawn again when it is resized, or when dark mode switches; the PDF saved last
        looked for again when the window is activated (it may have been moved or deleted meanwhile)."""
        QtCore, QtGui = _qt()
        owner = self
        palette_events = tuple(getattr(self.ak, "PALETTE_EVENTS", (38, 39)))

        class Watcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event_number(event, "type")
                    if kind == 14 or kind in palette_events:  # Resize, palette changes
                        if owner.zoom() is None or obj is owner.dialog or kind != 14:
                            owner.preview_timer.start()  # (zoomed, the page's size is its own: the label follows it)
                    elif kind == 24:  # WindowActivate
                        if obj is owner.dialog:
                            owner.zoom_keys(True)
                        if owner.saved:
                            owner.saved_timer.start()
                    elif kind in (25, 18, 19) and obj is owner.dialog:  # WindowDeactivate, Hide, Close
                        owner.zoom_keys(False)
                    elif kind in (KEY_PRESS, WHEEL, SHORTCUT_OVERRIDE):  # Ctrl+plus, Ctrl+minus, Ctrl+0, the wheel
                        return bool(owner.zoom_event(event))
                except Exception:
                    pass  # an event filter must never raise
                return False

        try:
            watcher = Watcher(self.dialog)  # (its parent the window: Qt deletes it with it)
            self.preview.installEventFilter(watcher)
            self.dialog.installEventFilter(watcher)
            self.preview_area.installEventFilter(watcher)  # (its keys, once clicked)
            self.preview_area.viewport().installEventFilter(watcher)  # (its resizes and the wheel over the page)
            self.keep.append(watcher)
        except Exception:
            pass

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
        """The current font and master (the cached glyphs dropped); False (and said so) when no font is open."""
        self.package = self.current_font()
        self.fonts, self.paths, self.font_glyphs, self.info, self.color_parts = {}, {}, None, None, {}
        self.facts, self.kerning_counts = None, {}
        if self.package is None:
            self.master = None
            self.proof = None
            self.page_list.clear()
            self.preview.clear()
            self.no_font_choices()
            self.font_label.setText(self.ak.no_font_line(NO_FONT_LINE) if hasattr(self.ak, "no_font_line")
                                    else NO_FONT_LINE)
            return False
        self.master = self.package.master
        masters = self.masters()
        index = self.masters_box.currentIndex
        self.masters_box.blockSignals(True)
        try:
            self.masters_box.clear()
            self.masters_box.addItem(u"Current master (%s)" % self.master)
            if len(masters) > 1:
                self.masters_box.addItem(u"All %d masters" % len(masters))
            self.masters_box.setCurrentIndex(index if 0 <= index < self.masters_box.count else 0)
        finally:
            self.masters_box.blockSignals(False)
        return True

    def no_font_choices(self):
        """The dropdowns that list the font's content, with no font (owner's images 289 and 290: an empty
        dropdown said nothing): Masters shows a grayed "n/a" (no_font_states grays it), and Proof its first
        choice, Every script, the last font's scripts and languages gone (the choice kept for the next
        font: scope_kept). Filled again as a font is read."""
        for box, item in ((self.masters_box, NOT_AVAILABLE), (self.scope_box, u"Every script")):
            box.blockSignals(True)
            try:
                box.clear()
                box.addItem(item)
                box.setCurrentIndex(0)
            finally:
                box.blockSignals(False)
        self.scopes = [None]
        self.scopes_font = None  # (the next font's scopes made anew, even the same font opened again)
        try:
            self.scope_box.setWhatsThis(scope_help(0, 0, True))
        except Exception:
            pass

    def masters(self):
        try:
            return [u"%s" % master for master in self.package.masters]
        except Exception:
            return [self.master]

    def same_font(self):
        current = self.current_font()
        return (current is not None and self.package is not None
                and self.ak.font_key(current) == self.ak.font_key(self.package) and current.master == self.master)

    def glyph_list(self):
        """(names in the font's order, {name: code points}), read once per font."""
        if self.font_glyphs is None:
            names, codes = [], {}
            for fg in self.package.fgPackage.glyphs:
                name = u"%s" % fg.name
                names.append(name)
                codes[name] = glyph_codes(fg)
            self.font_glyphs = (names, codes)
        return self.font_glyphs

    def layer(self, master, name):
        glyph = self.package.findName(name)
        if glyph is None or glyph.isNull:
            return None
        return glyph.getLayerByName(master)

    def path(self, master, name):
        """A glyph's outline in a master, as a QPainterPath (None: no layer), kept."""
        key = (master, name)
        if key not in self.paths:
            try:
                layer = self.layer(master, name)
                self.paths[key] = self.ak.layer_path(layer) if layer is not None else None
            except Exception:
                self.paths[key] = None
        return self.paths[key]

    def parts(self, master, name):
        """A color glyph's parts in their own colors (ak.layer_parts), or None, kept."""
        key = (master, name)
        if key not in self.color_parts:
            try:
                layer = self.layer(master, name)
                self.color_parts[key] = self.ak.layer_parts(layer) if layer is not None else None
            except Exception:
                self.color_parts[key] = None
        return self.color_parts[key]

    def colored(self, master, name):
        """Drawn in colors of its own: color layers (COLR), or a picture (SVG or bitmap)."""
        if self.parts(master, name) is not None:
            return True
        layer = self.layer(master, name)
        return layer is not None and self.ak.is_picture_layer(layer)

    def ink(self, master, name):
        path = self.path(master, name)
        if path is None or path.isEmpty():
            return None
        rect = path.boundingRect()
        return rect.left(), rect.right()

    def kerning_of(self, master):
        """{(left, right): value} as FontLab applies it, classes resolved; pairs of its own only (and said
        so) when FontLab does not resolve them."""
        kerning = self.ak.FontKerning(self.package.kerning(master))
        self.kerning_counts[master] = (len(kerning.values), len(kerning.classes))  # (for the summary's one line)
        if kerning.plain is not None:
            return dict(kerning.plain)
        self.log.add(u"FontLab did not give master %s's kerning with its classes applied: only pairs of glyphs are "
                     u"set." % self.ak.b(master), "warning")
        return dict(((entry[0][0], entry[1][0]), value) for entry, value in kerning.values.items()
                    if not entry[0][1] and not entry[1][1])

    def proof_font(self, master):
        if master in self.fonts:
            return self.fonts[master]
        names, codes = self.glyph_list()
        package = self.package

        def advance(name):
            layer = self.layer(master, name)
            return layer.advanceWidth if layer is not None else None

        def metric(name):
            try:
                value = getattr(package, name)
                return float(value() if callable(value) else value)
            except Exception:
                return None

        try:
            kerning = self.kerning_of(master)
        except Exception as exc:
            kerning = {}
            self.log.add(u"Could not read master %s's kerning: %s" % (self.ak.b(master), self.ak.html(exc)), "warning")
        family = u"%s" % (getattr(package, "tfn", None) or u"Font")
        font = ProofFont(family, master, package.upm, names, codes, advance, kerning,
                         metric("ascender_value"), metric("descender_value"), lambda name: self.ink(master, name),
                         lambda name: self.colored(master, name))
        self.fonts[master] = font
        return font

    def load_languages(self):
        if self.languages is None:
            try:
                self.languages = load_languages()
            except Exception as exc:
                self.languages = []
                self.log.add(u"Font Check's language data could not be read (%s): the text section uses the font's "
                             u"letters." % self.ak.html(exc), "warning")
            if not self.languages:
                self.log.add(u"%s is not beside this script: the text section uses the font's letters. Reinstall FreeLab."
                             % self.ak.i(LANGUAGES_FILE), "warning")
        return self.languages

    def font_info(self):
        """The font's info rows (read once per font; [] and said so when FontLab gives none)."""
        if self.info is None:
            package = self.package
            try:
                info = package.fgPackage.info
            except Exception:
                info = None
            try:
                self.info = info_rows(info, getattr(package, "tfn", None), getattr(package, "upm", None), self.masters())
            except Exception as exc:
                self.info = []
                self.log.add(u"The font's info could not be read: %s" % self.ak.html(exc), "warning")
        return self.info

    def font_check(self):
        """Font Check beside this script, as a module (its window not opened): its coverage and its
        reading of the vertical metrics."""
        return self.ak.load_sibling(FONT_CHECK_FILE, FONT_CHECK_MODULE)

    def say_once(self, key, text):
        """A warning the log gives once per window (a font read again at each edit would repeat it)."""
        if key not in self.facts_said:
            self.facts_said.add(key)
            self.log.add(text, "warning")

    def read_coverage(self, fc):
        """The CoverageSummary of the font as it is now: its code points, and its anchors in the current
        master for the letters they compose (read as Font Check reads them, when a language asks)."""
        package, master = self.package, self.master
        names_of, codes = {}, set()
        names, glyph_codes_ = self.glyph_list()
        for name in names:
            for code in glyph_codes_.get(name, ()):
                codes.add(code)
                names_of.setdefault(code, name)
        anchors = {}

        def anchors_of(code):
            if code not in anchors:
                layer = self.layer(master, names_of[code]) if code in names_of else None
                anchors[code] = set(fc.anchor_names(layer)) if layer is not None else set()
            return anchors[code]

        def attaches(base, mark):
            return bool(set(name[1:] for name in anchors_of(mark) if name.startswith(u"_")) & anchors_of(base))

        return coverage_summary(fc, codes, attaches)

    def read_features(self):
        """[(tag, the name the code gives the feature or u"")] of the font's feature code, in its order."""
        features = self.package.fgPackage.features
        tags = [u"%s" % tag for tag in features.keys()]
        own = None
        try:  # the name a stylistic set's own code gives it (featureNames), as Feature Code reads it
            own = self.ak.load_sibling(FEATURE_CODE_FILE, FEATURE_CODE_MODULE).hand_name
        except Exception:
            pass
        found = []
        for tag in tags:
            name = None
            if own is not None and re.match(u"^(ss|cv)[0-9]{2}$", tag):
                try:
                    name = own(u"%s" % (features.get_feature(tag) or u""))
                except Exception:
                    name = None
            found.append((tag, name or u""))
        return found

    def font_facts(self):
        """What the summary reads of the font beyond its info, once per font read (never as a page is
        drawn): {"coverage": a CoverageSummary or None, "metrics": Font Check's, or None, "features":
        [(tag, name)] or None}. What cannot be read is left out, and the log says why once."""
        if self.facts is not None:
            return self.facts
        facts = self.facts = {"coverage": None, "metrics": None, "features": None}
        html = self.ak.html
        fc = None
        try:
            fc = self.font_check()
        except Exception as exc:
            self.say_once("font check", u"<i>Font Check</i> is not beside this script (%s): the summary leaves the "
                                        u"languages the font covers and its vertical metrics out. Reinstall FreeLab."
                          % html(exc))
        if fc is not None:
            try:
                facts["coverage"] = self.read_coverage(fc)
            except Exception as exc:
                self.say_once("coverage", u"<i>Font Check</i>'s language data could not be read (%s): the summary "
                                          u"leaves the languages the font covers out. Reinstall FreeLab." % html(exc))
            try:
                facts["metrics"] = fc.read_metrics(self.package)
            except Exception as exc:
                self.say_once("metrics", u"The font's vertical metrics could not be read (%s): the summary leaves "
                                         u"them out." % html(exc))
        try:
            facts["features"] = self.read_features()
        except Exception as exc:
            self.say_once("features", u"The font's features could not be read (%s): the summary leaves them out."
                          % html(exc))
        return facts

    def summary(self, font, proofed, scope=None):
        """The Summary of the font (None with its check box off): font is the first master's ProofFont,
        whole (not limited to the scope); proofed: the masters the proof shows."""
        if not self.summary_box.isChecked():
            return None
        facts = self.font_facts()
        package = self.package
        names, codes = self.glyph_list()
        encoded = len(set(code for name in names for code in codes.get(name, ())))
        rows = summary_rows(self.font_info(), getattr(package, "tfn", None), font.master, self.masters(), proofed,
                            len(names), encoded, scope_label(scope))
        metrics = facts["metrics"]
        counts = self.kerning_counts.get(font.master) or (None, None)
        mode = SUMMARY_LANGUAGES[max(0, min(self.languages_box.currentIndex, len(SUMMARY_LANGUAGES) - 1))][0]
        return Summary(font.family, rows, metric_rows(metrics, font.master) if metrics is not None else None,
                       metric_notes(metrics) if metrics is not None else (),
                       features_text(facts["features"]) if facts["features"] is not None else u"",
                       kerning_text(len(font.kerning), font.master, counts[0], counts[1]),
                       facts["coverage"], mode, font)

    def summary_changed(self, key=None):
        """The summary's check box ("summary") or its list's choice ("summary_languages") changed: kept for
        the next session, and the proof laid out again. The file is read again and only that key is
        changed: another Proof window (another font's) may have set the other one since this window read
        the file. key None: both. A choice of Summary lists shows the first Language coverage page once
        the proof is laid out (the owner: "Changing summary lists doesn't appear to change what is shown on
        the proof": the lists close the proof, and the page shown stayed the one before)."""
        if key == "summary_languages":
            self.show_section = "coverage"
        try:
            mode = SUMMARY_LANGUAGES[max(0, min(self.languages_box.currentIndex, len(SUMMARY_LANGUAGES) - 1))][0]
            values = {"summary": bool(self.summary_box.isChecked()), "summary_languages": mode,
                      "collisions": bool(self.collisions_box.isChecked())}
            settings = read_settings(self.ak)
            for name in ([key] if key in values else list(values)):
                settings[name] = values[name]
            self.settings = settings
            write_settings(self.ak, settings)
        except Exception:
            pass  # a signal's handler must not raise
        self.rebuild_timer.start()

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick): the
        font read anew and its proof laid out, or the pages emptied and the no-font line shown."""
        self.package = None
        self.history_moved()

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again and the proof laid out again."""
        self.fonts, self.paths, self.font_glyphs, self.info, self.color_parts = {}, {}, None, None, {}
        self.facts, self.kerning_counts = None, {}
        self.rebuild()

    # -- the proof ------------------------------------------------------------

    def options(self):
        sections = [key for key, _ in SECTIONS if self.section_boxes[key].isChecked()]
        page = PAGE_SIZES[max(0, self.page_box.currentIndex)][0]
        keep = None
        if KERNING_SETS[max(0, self.pairs_box.currentIndex)][0] == "common":
            if self.common is None:
                try:
                    self.common = self.ak.common_pairs()
                except Exception as exc:
                    self.common = {}
                    self.log.add(u"The common pairs could not be read: %s" % self.ak.html(exc), "warning")
            keep = common_filter(self.common, self.glyph_list()[1], self.ak)
        return Options(sections, page, parse_sizes(self.waterfall_edit.text, WATERFALL_SIZES),
                       parse_sizes(self.text_edit.text, TEXT_SIZES), keep, bool(self.collisions_box.isChecked()))

    def note_font(self, font, options):
        """Said once per font: a color font's glyphs, and scripts the font has letters of that its text
        section cannot show (too few letters for any sample)."""
        key = self.ak.font_key(self.package)
        if key == getattr(self, "noted_font", None):
            return
        self.noted_font = key
        note = self.ak.color_note(self.package)
        if note:
            self.log.add(note)
        if "text" not in options.sections:
            return
        try:
            languages = self.load_languages()
            groups, _ = choose_samples(font, languages)
            for script, characters in thin_scripts(font, languages, groups):
                self.log.add(u"The font has %s of %s (%s), too few for a sample text or for its letters to stand in: "
                             u"the text section shows none of them." % (
                                 self.ak.b(counted(len(characters), u"letter")), self.ak.b(script),
                                 self.ak.html(u" ".join(characters[:12]) + (u" …" if len(characters) > 12 else u""))),
                             "warning")
        except Exception as exc:
            self.log.add(u"The sample texts could not be checked: %s" % self.ak.html(exc), "warning")

    def fill_scopes(self, font, languages, again=False):
        """The scopes the font offers (made once per font; again: now, More languages... was chosen): its
        scripts with letters, then the languages it covers whole (every base character), the most spoken
        first, a sensible number of them, and an entry that lists the others; the choice kept where it
        still is. The dropdown's help and its caption's give the counts."""
        key = self.ak.font_key(self.package)
        if getattr(self, "scopes_font", None) == key and not again:
            return
        self.scopes_font = key
        current = self.scope_kept
        counts = {}
        for name in font.glyphs:
            script = glyph_script(font, name)
            if script is not None and font.has(name):
                counts[script] = counts.get(script, 0) + 1
        scripts = sorted((word for word, n in counts.items() if n >= SCRIPT_MINIMUM), key=lambda word: -counts[word])
        covered = self.scope_languages = covered_languages(font, languages)
        rows = scope_rows(scripts, covered, self.scope_expanded, current)
        _, rest, listed = split_languages(covered, self.scope_expanded, current)
        self.scope_box.blockSignals(True)
        try:
            self.scope_box.clear()
            self.scopes = []
            for text, scope in rows:
                if text is None:
                    self.scope_box.insertSeparator(self.scope_box.count)
                else:
                    self.scope_box.addItem(text)
                self.scopes.append(scope)  # (None at a separator's place too)
            index = 0
            for at, scope in enumerate(self.scopes):
                if same_scope(scope, current):
                    index = at
            self.scope_box.setCurrentIndex(index)
            if not index:
                self.scope_kept = None  # (the font read now lacks it: every script again)
            # (its caption shows the dropdown's help: ak.caption)
            self.scope_box.setWhatsThis(scope_help(len(covered), len(rest), listed))
        finally:
            self.scope_box.blockSignals(False)

    def scope_chosen(self, index=None):
        """A choice in the Proof dropdown: the proof laid out again for it; More languages... lists the
        other languages instead, the choice before it kept, and opens the dropdown again to pick one."""
        try:
            at = self.scope_box.currentIndex
            scope = self.scopes[at] if 0 <= at < len(self.scopes) else None
            if scope == MORE:
                QtCore, QtGui = _qt()
                self.scope_expanded = True
                if self.fonts and self.languages is not None:
                    font = self.fonts.get(self.master) or list(self.fonts.values())[0]
                    self.fill_scopes(font, self.languages, again=True)
                opener = lambda: self.scope_box.showPopup()
                self.keep.append(opener)
                QtCore.QTimer.singleShot(0, opener)  # (once this choice is done with: the list, longer now)
                return
            self.scope_kept = scope
        except Exception:
            pass  # a signal's handler must not raise
        self.rebuild_timer.start()

    def rebuild(self):
        """The proof laid out again from the settings (the font read where it changed)."""
        QtCore, QtGui = _qt()
        if self.busy:
            self.rebuild_timer.start()
            return
        if self.package is None or not self.same_font():
            if not self.read_font():
                self.update_buttons()
                return
        ak = self.ak
        self.busy = True
        self.update_buttons()
        row = max(0, self.page_list.currentRow)
        stopped = False
        # The window's top row says what runs (ak.busy_start: the tools menu, the arrows, Close, and Esc stop
        # it); it said "Laying out the proof" in the top line before, the window painted once
        ak.busy_start(self, u"Reading the font")
        try:
            masters = self.masters() if self.masters_box.currentIndex == 1 else [self.master]
            fonts = []
            for master in masters:
                ak.busy_progress(self, None, 0.6 * len(fonts) / float(len(masters)))
                fonts.append(self.proof_font(master))
            ak.busy_progress(self, u"Laying out the pages", 0.6)
            options = self.options()
            languages = self.load_languages()
            self.fill_scopes(fonts[0], languages)
            scope = self.scopes[max(0, self.scope_box.currentIndex)] if self.scopes else None
            if scope == MORE:  # (the entry that fills the list out is no scope)
                scope = None
            summary = self.summary(fonts[0], masters, scope)  # (of the whole font, whatever the scope)
            if scope is not None:
                names = scope_names(fonts[0], scope)
                fonts = [restricted(font, names) for font in fonts]
                if scope[0] == "language":
                    languages = [scope[1]]
                else:  # the languages written in that script (all of them, where none is named so: Han)
                    same = [language for language in languages if (u"%s" % language.script).upper() == scope[1]]
                    languages = same or languages
            ak.busy_progress(self, None, 0.8)
            proof = build_proof(fonts, options, languages, info=self.font_info(), summary=summary)
            ak.busy_progress(self, None, 1.0, stoppable=False)  # (laid out: shown, a stop asked now comes too late)
            self.proof = proof
            self.page_options = options
            self.note_font(fonts[0], options)
        except ak.Stopped:  # (by the user: the pages shown stay those of before)
            stopped = True
        except Exception as exc:
            self.proof = None
            self.log.add(u"The proof could not be laid out: %s" % self.ak.html(exc), "error")
        finally:
            self.busy = False
            ak.busy_end(self)
        if stopped:
            self.log.add(u"Laying out the proof was stopped: the pages shown are those of before.", "warning")
            self.status()
            self.update_buttons()
            return
        wanted, self.show_section = getattr(self, "show_section", None), None
        if wanted is not None and self.proof is not None:  # (a setting that changes pages further on: shown)
            row = next((number for number, page in enumerate(self.proof.pages) if wanted in page.sections), row)
        self.fill_pages(row)
        self.status()
        self.seen_history = self.ak.history_mark(self.package)
        self.update_buttons()

    def fill_pages(self, row=0):
        self.page_list.blockSignals(True)
        try:
            self.page_list.clear()
            if self.proof is not None:
                several = len(self.proof.masters) > 1
                for number, page in enumerate(self.proof.pages, 1):
                    text = u"%d   %s" % (number, u", ".join(TITLES.get(key, key) for key in page.sections))
                    if several and page.master != ALL_MASTERS:
                        text += u" (%s)" % page.master  # (a page's master: data beside its sections)
                    self.page_list.addItem(text)
                self.page_list.setCurrentRow(min(row, len(self.proof.pages) - 1))
                self.ak.fit_list_width(self.page_list)  # (as wide as its longest page: it scrolled sideways for 2 pixels)
        finally:
            self.page_list.blockSignals(False)
        self.show_page()

    def font_named(self, masters=None):
        """The top line's start (ak.font_named, the same in every tool): the font in bold, then the master
        proofed, or all of them."""
        ak = self.ak
        count = len(self.masters())
        if masters is not None and len(masters) > 1:
            return u"%s, all %s" % (ak.b(self.package.tfn), ak.b(counted(len(masters), u"master")))
        master = masters[0] if masters else self.master
        if hasattr(ak, "font_named"):
            return ak.font_named(self.package.tfn, master, count)
        return u"%s, master %s" % (ak.b(self.package.tfn), ak.b(master))

    def status(self):
        if self.proof is None:  # (the top line still says which font: owner's image 224)
            self.font_label.setText(u"%s: no proof (see the log)." % self.font_named())
            return
        size = dict((key, label) for key, label, _ in PAGE_SIZES).get(self.page_options.page, u"")
        self.font_label.setText(status_line(self.font_named(self.proof.masters), self.proof, size, self.ak))

    def selected_page(self):
        if self.proof is None:
            return None
        row = self.page_list.currentRow
        return self.proof.pages[row] if 0 <= row < len(self.proof.pages) else None

    def color_mode(self):
        return COLOR_MODES[max(0, min(self.colors_box.currentIndex, len(COLOR_MODES) - 1))][0]

    def colors(self):
        """(ink, paper) as (red, green, blue), for the preview and the PDF alike: the window's text and
        background colors, or black on white."""
        QtCore, QtGui = _qt()
        mode = self.color_mode()
        try:
            palette = self.ak._property(self.dialog, "palette")
            rgb = lambda color: (color.red(), color.green(), color.blue())
            ink, paper = rgb(palette.color(QtGui.QPalette.Text)), rgb(palette.color(QtGui.QPalette.Base))
        except Exception:
            return page_colors("print")
        dark_window = 0.299 * paper[0] + 0.587 * paper[1] + 0.114 * paper[2] < 128
        # the second choice is the other of the two: black on white beside a dark window, light on dark
        # beside a light one (black on white twice said nothing)
        try:
            self.colors_box.setItemText(1, u"Print (black on white)" if dark_window else u"Dark (white on black)")
        except Exception:
            pass
        if mode == "window":
            return page_colors(mode, ink, paper)
        return PRINT_COLORS if dark_window else DARK_COLORS

    def pixel_ratio(self):
        """Device pixels per pixel of the preview (above 1 on a scaled display), 1 where Qt does not say."""
        for name in ("devicePixelRatioF", "devicePixelRatio"):
            try:
                value = getattr(self.preview, name)
                return max(1.0, float(value() if callable(value) else value))
            except Exception:
                continue
        return 1.0

    def zoom(self):
        """The preview's zoom (ZOOMS): None to fit the page, else a share of its printed size."""
        try:
            index = int(self.zoom_box.currentIndex)
        except Exception:
            index = 0
        return ZOOMS[index][0] if 0 <= index < len(ZOOMS) else None

    def room(self):
        """(width, height) in pixels the page fits at Fit page: the scroll area's view, less a margin."""
        view = self.preview_area.viewport()
        return (max(60, self.ak._property(view, "width") - 4), max(60, self.ak._property(view, "height") - 4))

    def zoom_step(self, step):
        """The zoom one step larger (1) or smaller (-1), from Fit page too (the next past the fitted size)."""
        size = page_size(self.page_options.page) if self.page_options is not None else page_size("A4")
        fitted = fit_scale(self.room(), size) / SCREEN_POINT
        index = next_zoom(int(self.zoom_box.currentIndex), step, fitted)
        if index != int(self.zoom_box.currentIndex):
            self.zoom_box.setCurrentIndex(index)  # (its signal draws the page)
            return True
        return False

    def zoom_keys(self, take):
        """FontLab's zoom shortcuts taken while this window is active (take), given back otherwise
        (take_zoom_keys, give_back_zoom_keys)."""
        QtGui = _qt()[1]
        try:
            main = self.ak.AutoKerningDialog.main_window()
        except Exception:
            main = None
        try:
            if take:
                take_zoom_keys(QtGui, main)
            else:
                give_back_zoom_keys(QtGui, main)
        except Exception:
            pass

    def zoom_event(self, event):
        """Ctrl with the mouse wheel over the page, Ctrl+plus, Ctrl+minus, or Ctrl+0 in the window (zoom_command):
        zoomed, and True (the event taken); anything else False (left to Qt: the wheel alone scrolls). Live
        pass: the keys did nothing, FontLab's own View zoom shortcuts (Ctrl+plus, Ctrl+minus, Ctrl+0) took
        them first, as they took Ctrl+Z. So the window takes them at Qt's ShortcutOverride, which comes before
        any shortcut is looked up (accepted, Qt sends the key as a plain key press), and zooms on the key press."""
        command = zoom_command(event, _qt()[0])
        if command is None and event_number(event, "type") == WHEEL and self.selected_page() is not None:
            return self.wheel_page(event)
        if command is None or self.selected_page() is None:
            return False
        try:
            event.accept()
        except Exception:
            pass
        if event_number(event, "type") == SHORTCUT_OVERRIDE:
            return True  # (the key press that follows zooms)
        if command == "fit":
            self.zoom_box.setCurrentIndex(0)
        elif command:
            self.zoom_step(command)
        return True

    def wheel_page(self, event):
        """The wheel alone over the page: past its top or its bottom, the page before or after (owner's image 347),
        shown from its bottom or its top, as a PDF viewer goes on; elsewhere the page scrolls (False: left to
        Qt). True once the page turned."""
        QtCore = _qt()[0]
        try:
            bar = self.preview_area.verticalScrollBar()
            turn = page_turn(wheel_steps(event), int(bar.value), int(bar.minimum), int(bar.maximum))
            row = int(self.page_list.currentRow) if not callable(self.page_list.currentRow) else \
                int(self.page_list.currentRow())
            count = int(self.page_list.count) if not callable(self.page_list.count) else int(self.page_list.count())
        except Exception:
            return False
        if not turn or not 0 <= row + turn < count:
            return False
        self.page_list.setCurrentRow(row + turn)

        def to_edge(bar=bar, turn=turn):
            try:
                bar.setValue(int(bar.minimum) if turn > 0 else int(bar.maximum))
            except Exception:
                pass
        self.keep.append(to_edge)
        del self.keep[:-40]
        QtCore.QTimer.singleShot(60, to_edge)  # (once the new page is laid out: its scroll range is its own)
        try:
            event.accept()
        except Exception:
            pass
        return True

    def show_page(self):
        QtCore, QtGui = _qt()
        page = self.selected_page()
        if page is None:
            self.preview.clear()
            self.update_buttons()
            return
        try:
            ink, paper = self.colors()
            renderer = Renderer(QtCore, QtGui, self.path, self.ak._property(self.dialog, "font").family(),
                                QtGui.QColor(*ink), self.parts)
            zoom = self.zoom()
            pixmap = page_pixmap(QtCore, QtGui, page, renderer, self.room(), page_size(self.page_options.page),
                                 QtGui.QColor(*paper), self.pixel_ratio(), zoom)
            if zoom is None:
                self.preview.setMinimumSize(200, 200)  # (the room's size: the page fitted to it)
            else:  # the label as large as the page: the area scrolls it
                ratio = self.pixel_ratio_of(pixmap)
                self.preview.setMinimumSize(int(pixmap.width() / ratio) + 2, int(pixmap.height() / ratio) + 2)
            self.preview.setPixmap(pixmap)
        except Exception as exc:
            self.preview.clear()
            self.log.add(u"The page could not be drawn: %s" % self.ak.html(exc), "error")
        self.update_buttons()

    @staticmethod
    def pixel_ratio_of(pixmap):
        for name in ("devicePixelRatioF", "devicePixelRatio"):
            try:
                value = getattr(pixmap, name)
                return max(1.0, float(value() if callable(value) else value))
            except Exception:
                continue
        return 1.0

    # -- buttons --------------------------------------------------------------

    def defaults_changed(self):
        sections = [self.section_boxes[key].isChecked() for key, _ in SECTIONS]
        return (not all(sections) or self.page_box.currentIndex != 0 or self.pairs_box.currentIndex != 0
                or self.masters_box.currentIndex != 0 or self.colors_box.currentIndex != 0
                or self.scope_box.currentIndex > 0 or self.scope_expanded
                or not self.summary_box.isChecked() or self.languages_box.currentIndex != 0
                or self.collisions_box.isChecked()
                or parse_sizes(self.waterfall_edit.text, ()) != tuple(float(s) for s in WATERFALL_SIZES)
                or parse_sizes(self.text_edit.text, ()) != tuple(float(s) for s in TEXT_SIZES))

    def update_buttons(self):
        enable = self.ak.enable
        ready = self.proof is not None and bool(self.proof.pages) and not self.busy
        enable(self.save_button, ready)
        enable(self.open_button, self.saved_there())
        has_font = self.package is not None
        # (nothing to list without the summary page; the captions gray with their controls: ak.caption)
        enable(self.languages_box, has_font and bool(self.summary_box.isChecked()))
        # (it marks the kerning and spacing strings: grayed while neither section is ticked)
        enable(self.collisions_box, has_font and any(self.section_boxes[key].isChecked() for key in ("kerning", "spacing")))
        # No font: no masters and no scripts or languages to choose from, no pages to look at (owner's image
        # 282: ak.no_font_states grays every other control meanwhile, Close and the tools aside)
        for box in (self.masters_box, self.scope_box):
            enable(box, has_font)
        enable(self.page_list, self.proof is not None and bool(self.proof.pages))
        page = self.selected_page()
        enable(self.glyph_window_button, ready and page is not None and bool(page.runs()))
        try:
            enable(self.restore_button, self.defaults_changed())
        except Exception:
            enable(self.restore_button, True)

    def saved_there(self):
        """Whether the PDF saved last is still where it was saved; the log says once when it is not
        (moved or deleted since)."""
        if not self.saved:
            return False
        if os.path.isfile(self.saved):
            self.gone_said = False
            return True
        if not self.gone_said:
            self.gone_said = True
            self.log.add(u"The PDF saved last, %s, is not there anymore: it was moved or deleted. Save it again to "
                         u"open it." % self.ak.i(self.saved), "warning")
        return False

    def restore_defaults(self):
        for box in self.section_boxes.values():
            box.setChecked(True)
        self.page_box.setCurrentIndex(0)
        self.pairs_box.setCurrentIndex(0)
        self.masters_box.setCurrentIndex(0)
        self.colors_box.setCurrentIndex(0)
        self.scope_box.setCurrentIndex(0)
        self.scope_kept, self.scope_expanded = None, False
        self.scopes_font = None  # (the dropdown filled again, short, as the proof is laid out)
        self.summary_box.setChecked(True)
        self.collisions_box.setChecked(False)
        self.languages_box.setCurrentIndex(0)
        self.waterfall_edit.setText(u" ".join(format_size(s) for s in WATERFALL_SIZES))
        self.text_edit.setText(u" ".join(format_size(s) for s in TEXT_SIZES))
        self.rebuild_timer.start()
        self.log.add(u"Settings restored to the defaults.")

    def settle(self):
        """Settings changed a moment ago and still waiting on the rebuild timer (sizes typed, then a button
        clicked) laid out now, so the button acts on the proof they make, not the one before them."""
        try:
            waiting = self.rebuild_timer.isActive()
        except Exception:
            waiting = False
        if waiting and not self.busy:
            self.rebuild_timer.stop()
            self.rebuild()

    def show_in_glyph_window(self):
        self.settle()
        page = self.selected_page()
        if page is None or self.package is None:
            return
        runs = [run for run in page.runs() if run][:40]
        if not runs:
            return
        text = u"/space".join(u"".join(u"/" + name for name in run) for run in runs)
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open the page: %s" % self.ak.html(error), "error")

    def save_pdf(self):
        QtCore, QtGui = _qt()
        self.settle()
        if self.busy or self.proof is None:
            return
        if not self.same_font():
            self.rebuild()
            if self.proof is None:
                return
        folder = SAVE_FOLDER[0] if SAVE_FOLDER else documents_folder(QtCore)
        date = time.strftime("%Y-%m-%d")
        master = self.master if len(self.proof.masters) == 1 else u""
        suggested = os.path.join(folder, pdf_name(self.package.tfn, master, date))
        chosen = QtGui.QFileDialog.getSaveFileName(self.dialog, u"Save the proof as PDF", suggested,
                                                   u"PDF files (*.pdf)")
        if isinstance(chosen, (tuple, list)):
            chosen = chosen[0] if chosen else u""
        path = u"%s" % (chosen or u"")
        if not path:
            return
        if not path.lower().endswith(u".pdf"):
            path += u".pdf"
        del SAVE_FOLDER[:]
        SAVE_FOLDER.append(os.path.dirname(path))
        self.busy = True
        self.update_buttons()
        b = self.ak.b
        pages = self.proof.pages
        # The pages written in the window's top row (owner's image 180), never stopped half way: a PDF half
        # written is no PDF (what was clicked meanwhile is done once it is whole)
        self.ak.busy_start(self, u"Writing the PDF", stoppable=False)
        try:
            def progress(done, total):
                self.ak.busy_progress(self, u"Writing page %d of %d" % (done, total),
                                      done / float(total or 1), stoppable=False)

            ink, paper = self.colors()
            renderer = Renderer(QtCore, QtGui, self.path, self.ak._property(self.dialog, "font").family(),
                                QtGui.QColor(*ink), self.parts)
            write_pdf(QtCore, QtGui, path, pages, renderer, self.page_options.page,
                      u"%s proof" % self.package.tfn, progress, None if paper == PRINT_COLORS[1] else QtGui.QColor(*paper))
            self.saved = path
            self.gone_said = False
            self.log.add(u"Saved %s to %s, in %s." % (b(counted(len(pages), u"page")), self.ak.i(os.path.basename(path)),
                                                      colors_label(self.color_mode(), ink, paper)), "done")
        except Exception as exc:
            self.log.add(u"The PDF could not be written: %s" % self.ak.html(exc), "error")
        finally:
            self.busy = False
            self.ak.busy_end(self)
            self.status()
            self.update_buttons()

    def open_pdf(self):
        QtCore, QtGui = _qt()
        if not self.saved_there():  # (the log says why; the button grays out)
            self.update_buttons()
            return
        try:
            opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.saved))
        except Exception as exc:
            opened = False
            self.log.add(u"Windows did not open the PDF: %s" % self.ak.html(exc), "error")
            return
        if not opened:
            self.log.add(u"Windows did not open the PDF: no application opens PDF files?", "warning")

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        if self.package is not None:
            QtCore.QTimer.singleShot(50, self.rebuild)  # laid out as it opens


SAVE_FOLDER = []  # the folder a PDF was last saved in, while FontLab runs


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("Proof"):
            return
    except Exception:
        pass
    dialog = ProofDialog()
    sys._freelab_proof = dialog  # kept, even half-built: PythonQt deletes a dialog with no Python reference
    if dialog.failed is not None:
        print("FreeLab Proof: %s" % dialog.failed)
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
        dialog.ak.take_window("Proof", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_proof":
    main()
