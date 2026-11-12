#FLM: Proof
# -*- coding: utf-8 -*-
"""FreeLab Proof, from FontLab's Scripts menu: a PDF proof of the current font, drawn from its own
outlines.

FontLab 9 has a Notepad panel for specimens and PDF proofs; FontLab 7 has none. Proof lays the
font's glyphs out as they are in FontLab (nothing exported, nothing installed): a character set,
waterfalls, text in each script the font covers, kerning strings, spacing strings, diacritics, and
figures and punctuation, for the current master or each master, with a header and a footer on each
page. Kerning is applied as FontLab applies it (classes resolved). OpenType features are not: no
ligatures, no contextual or localized forms, no mark positioning; each character shows its own glyph.

Valid Python 2.7 (FontLab 7) and Python 3. Everything above the Qt line needs no Qt and no FontLab.
The drawing below it takes Qt's modules as arguments, so the same code draws in FontLab (PythonQt)
and offline (PySide6).
"""

from __future__ import absolute_import, division, print_function

import json
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
TITLES = dict(SECTIONS, about=u"About this proof", info=u"Font info", masters=u"Masters")
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
SCOPE_LANGUAGES_MAX = 120  # languages offered in the Proof dropdown, the most spoken first
MAX_SAMPLES = 6  # languages per script in the text section, the most spoken first
SCRIPT_MINIMUM = 5  # a script's letters the font needs before its letters stand in for its text
ALPHABET_MAX = 120  # characters at most, when a script's letters stand in for its text
WATERFALL_MIN = 120  # characters of sample text the waterfall wants (it is cut at the page's edge)
ALL_MASTERS = u"All masters"
NOTE = u"Kerning applied; OpenType features not applied"
KERNING_SETS = (("all", u"every kerned pair"), ("common", u"common pairs only"))
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


def char_name(code):
    try:
        return unicodedata.name(char_of(code))
    except Exception:  # unnamed, or past U+FFFF on a narrow build
        return u""


def category(code):
    try:
        return unicodedata.category(char_of(code))
    except Exception:
        return u"Cn"


def script_case(code):
    """(script, case) of a letter, from its Unicode name: ("LATIN", "upper"), ("HEBREW", None);
    ("FIGURE", None) for a digit; None for anything else."""
    kind = category(code)
    if kind == u"Nd":
        return ("FIGURE", None)
    if not kind.startswith(u"L"):
        return None
    words = char_name(code).replace(u"-", u" ").split()
    if not words:
        return None
    case = "upper" if kind in (u"Lu", u"Lt") else ("lower" if kind == u"Ll" else None)
    return (words[0], case)


def base_char(code):
    """The letter an accented letter is built on (A for Aacute, l for lslash), or None."""
    text = char_of(code)
    decomposed = unicodedata.normalize("NFD", text)
    if len(decomposed) > 1 and not unicodedata.combining(decomposed[0]) and unicodedata.combining(decomposed[1]):
        return ord(decomposed[0])
    name = char_name(code)
    if u" WITH " in name:
        try:
            return ord(unicodedata.lookup(name.split(u" WITH ")[0]))
        except (KeyError, TypeError):
            return None
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
    kerning {(left, right): value}: glyph pairs, as they are seen (left glyph, right glyph);
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

    def kern(self, left, right):
        return self.kerning.get((left, right), 0)

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
    """([(name, x)], width) for a line of glyph names (None: a space), in font units. Right to left,
    the line is reversed first: kerning is read as the pairs are seen, left glyph then right glyph."""
    space = font.space() if space is None else space
    visual = list(reversed(line)) if rtl else list(line)
    placed, x, prev = [], 0.0, None
    for name in visual:
        if name is None:
            x += space
            prev = None
            continue
        if prev is not None and kerning:
            x += font.kern(prev, name)
        placed.append((name, x))
        x += font.width(name)
        prev = name
    return placed, x


def _token_width(font, names, prev, kerning, rtl):
    width = 0.0
    for name in names:
        if prev is not None and kerning:
            width += font.kern(name, prev) if rtl else font.kern(prev, name)
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
        width, last = _token_width(font, names, None if gap or not line else prev, kerning, rtl)
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
    [(name, x in font units)]), "text" (x, y, width, height, text, size, style: plain, bold, or quiet;
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
        """The glyph names of each line of glyphs on the page."""
        return [[name for name, _ in item.placed] for item in self.items if item.kind == "glyphs"]


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

    def glyphs(self, font, placed, width, size, label=None, indent=0.0, align="left"):
        """A line of glyphs at size points per em (placed and width in font units)."""
        height = line_height(font, size)
        self.need(height)
        x = self.left + indent
        if align == "right":
            x += max(0.0, self.right - x - width * size / font.upm)
        if label:
            self.add("text", x=self.left, y=self.y, width=indent - 4.0, height=height, text=label, size=7,
                     style="quiet", align="left")
        self.add("glyphs", x=x, baseline=self.y + baseline_in(font, size, height), size=size, upm=font.upm,
                 master=font.master, placed=placed)
        self.y += height

    def lines(self, font, tokens, size, rtl=False, kerning=True, space=None, label=None, indent=0.0):
        """Tokens broken into lines of the page's width and laid out (label: on the first line)."""
        room = (self.width() - indent) * font.upm / size
        for index, line in enumerate(wrap(font, tokens, room, rtl, kerning, space)):
            placed, width = place(font, line, rtl, kerning, space)
            self.glyphs(font, placed, width, size, label if index == 0 else None, indent, "right" if rtl else "left")

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
            kind = script_case(ord(ch[0]))
            if (ch not in present and category(ord(ch[0])).startswith(u"L") and kind is not None
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
    """[(left, [(right, value, names)])]: every kerned pair, grouped by its left glyph (in the font's
    order), each between control letters as HH?HOHO and nn?nono have it: two straight ones of the
    left glyph's kind before, a straight and a round one of the right glyph's twice after.
    keep(left, right): the pairs to list (all by default)."""
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
# The sections
# ---------------------------------------------------------------------------

class Options(object):
    """What a proof shows: sections (keys of SECTIONS), the page size (a key of PAGE_SIZES), the
    waterfall's and the text's sizes, and keep(left, right): the kerned pairs to list (None: all)."""

    def __init__(self, sections=None, page="A4", waterfall=WATERFALL_SIZES, text_sizes=TEXT_SIZES, keep=None):
        self.sections = set(sections if sections is not None else [key for key, _ in SECTIONS])
        self.page = page
        self.waterfall, self.text_sizes = tuple(waterfall), tuple(text_sizes)
        self.keep = keep


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
        layout.glyphs(font, placed, width, size, u"%s pt" % format_size(size), LABEL_WIDTH, "right" if rtl else "left")


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


def section_kerning(layout, font, keep=None, size=STRING_SIZE):
    layout.heading(TITLES["kerning"])
    groups = kerning_strings(font, keep)
    total = sum(len(strings) for _, strings in groups)
    which = u"common kerned pair" if keep is not None else u"kerned pair"
    layout.text(u"%s, grouped by left glyph, between control letters (HH?HOHO, nn?nono), kerning applied "
                u"(classes resolved)." % counted(total, which), style="quiet")
    if not groups:
        layout.text(u"No %s in this master." % (which + u"s"))
        return
    space = font.upm * STRING_GAP
    for left, strings in groups:
        layout.text(u"%s (%s)" % (left, counted(len(strings), u"pair")), 8, "bold", gap=4.0, keep=line_height(font, size))
        layout.lines(font, [(names, True) for _, _, names in strings], size, space=space)


def section_spacing(layout, font, size=STRING_SIZE):
    layout.heading(TITLES["spacing"])
    groups = spacing_strings(font)
    layout.text(u"Each letter and figure between control letters (HHxHOxOO, nnxnoxoo), set without kerning: the "
                u"sidebearings alone.", style="quiet")
    if not groups:
        layout.text(u"The font has no encoded letters or figures of the scripts spaced here.")
        return
    space = font.upm * STRING_GAP
    for label, strings in groups:
        layout.text(u"%s (%s)" % (label, counted(len(strings), u"glyph")), 8, "bold", gap=4.0, keep=line_height(font, size))
        layout.lines(font, [(names, True) for _, names in strings], size, kerning=False, space=space)


def section_diacritics(layout, font, size=SHOWCASE_SIZE):
    layout.heading(TITLES["diacritics"])
    groups = diacritic_groups(font)
    combining, spacing = marks_of(font)
    layout.text(u"%s, each group after the letter it is built on, kerning applied; marks are not positioned "
                u"(no mark feature)." % counted(sum(len(names) for _, names in groups), u"letter with marks",
                                                u"letters with marks"), style="quiet")
    space = font.upm * STRING_GAP
    if groups:
        layout.lines(font, [(([base] if base else []) + names, True) for base, names in groups], size, space=space)
    else:
        layout.text(u"The font has no letters with marks.")
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


def section_masters(layout, fonts, line, rtl):
    layout.heading(TITLES["masters"])
    layout.text(u"The same text in each master, kerning applied.", style="quiet")
    for font in fonts:
        layout.text(font.master, 8, "bold", gap=6.0, keep=line_height(font, MASTERS_SIZES[0]))
        for size in MASTERS_SIZES:
            room = layout.width() * font.upm / size
            placed, width = clip(font, line, room, rtl)
            layout.glyphs(font, placed, width, size, align="right" if rtl else "left")


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
    its base and auxiliary letters; with every glyph that is no letter (figures, punctuation, symbols)."""
    kind, value = scope
    if kind == "language":
        wanted = set()
        for chars in (value.base, getattr(value, "auxiliary", None) or []):
            for ch in chars:
                for c in ch:
                    wanted.add(ord(c))
    kept = set()
    for name in font.glyphs:
        script = glyph_script(font, name)
        if script is None:
            kept.add(name)
        elif kind == "script" and script == value:
            kept.add(name)
        elif kind == "language" and encoded_code(font, name) in wanted:
            kept.add(name)
    return kept


def restricted(font, names):
    """A copy of a ProofFont that has only names (its kerning between them too)."""
    keep = [name for name in font.glyphs if name in names]
    codes = dict((name, font.codes.get(name, ())) for name in keep)
    kerning = dict((pair, value) for pair, value in font.kerning.items() if pair[0] in names and pair[1] in names)
    return ProofFont(font.family, font.master, font.upm, keep, codes, font._advance, kerning, font.ascender,
                     font.descender, font._ink, font._colored)


def build_proof(fonts, options=None, languages=(), date=None, info=None):
    """The pages of a proof of fonts (a ProofFont per master, the first the one the text is chosen
    for): an about block, the font's info (info: [(label, text)], None for none), the masters side by
    side (several masters), then each master's sections."""
    options = options or Options()
    date = date or time.strftime("%Y-%m-%d")
    layout = Layout(page_size(options.page))
    first = fonts[0]
    groups, left_out = choose_samples(first, languages)
    line, rtl = waterfall_line(first, groups)
    label = ALL_MASTERS if len(fonts) > 1 else first.master
    kerned = []
    for font in fonts:
        kerned.append(sum(1 for (left, right), value in font.kerning.items()
                          if value and (options.keep is None or options.keep(left, right))))
    layout.begin("about", label)
    layout.text(first.family, 16, "bold", keep=30.0)
    masters = u", ".join(font.master for font in fonts)
    layout.text(u"%s; %s: %s." % (counted(len(first.glyphs), u"glyph"), counted(len(fonts), u"master"), masters))
    layout.text(u"Drawn from the font's own outlines. Kerning applied as FontLab applies it, classes resolved "
                u"(%s). OpenType features not applied: no ligatures, no contextual or localized forms, no mark "
                u"positioning; each character shows its own glyph." % u", ".join(
                    u"%s %s" % (counted(count, u"kerned pair"), u"in " + font.master) for count, font in zip(kerned, fonts)))
    if left_out:
        layout.text(u"No text for %s: shaping is not done." % u", ".join(left_out))
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
        "kerning": lambda font: section_kerning(layout, font, options.keep),
        "spacing": lambda font: section_spacing(layout, font),
        "diacritics": lambda font: section_diacritics(layout, font),
        "figures": lambda font: section_figures(layout, font),
    }
    for font in fonts:
        for key, _ in SECTIONS:
            if key in options.sections:
                layout.begin(key, font.master)
                builders[key](font)
    layout.finish(first.family, date)
    return Proof(layout.pages, [font.master for font in fonts], kerned, left_out, groups)


def common_filter(common, codes):
    """keep(left, right) for the pairs common in text: common {two characters: rank} (Auto Kerning's
    common_pairs), codes {glyph name: code points}; unencoded glyphs are never common."""
    def text_of(name):
        found = codes.get(name)
        return char_of(found[0]) if found else None

    def keep(left, right):
        a, b = text_of(left), text_of(right)
        return a is not None and b is not None and (a + b) in common

    return keep


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

    def draw(self, painter, page, scale):
        QtCore, QtGui = self.QtCore, self.QtGui
        painter.setRenderHint(self.antialiasing, True)
        brush = QtGui.QBrush(self.ink)
        rule = QtGui.QPen(self.rule)
        rule.setWidthF(max(1.0, 0.5 * scale))
        for item in page.items:
            if item.kind == "glyphs":
                factor = item.size / item.upm * scale
                for name, x in item.placed:
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
                        painter.fillPath(path, brush)
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


def page_pixmap(QtCore, QtGui, page, renderer, size, page_points, paper, ratio=1.0):
    """A page drawn into a pixmap that fits size (width, height in pixels) whole, on paper; ratio:
    device pixels per pixel (a scaled display: drawn that much finer, so it stays crisp)."""
    ratio = max(1.0, float(ratio or 1.0))
    scale = fit_scale(size, page_points) * ratio
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
            return page_pixmap(QtCore, QtGui, page, renderer, size, page_points, paper)
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
nnxnoxoo, without kerning), <b>diacritics</b>, and <b>figures and punctuation</b>; for the current
master, or for each master (with a page of the masters side by side). The first page says what the
proof shows and gives the font's info (names, version, designer, license, dates).<br><br>
Kerning is applied as FontLab applies it, classes resolved. OpenType features are not: no ligatures,
no contextual or localized forms, no mark positioning, so each character shows its own glyph, and
scripts that need shaping (Arabic, the Indic scripts, Thai) get no text.<br><br>
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
        self.common = None  # {two characters: rank}, read when first needed
        self.languages = None
        self.keep = []  # Python references to the slots and filters PythonQt does not hold
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Proof")
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.font_label = ak.status_label()
        layout.addWidget(self.font_label)
        layout.addWidget(ak.separator())

        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Masters"))
        self.masters_box = QtGui.QComboBox()
        self.masters_box.setWhatsThis(u"The current master only, or each master in turn (each starting on a new "
                                      u"page, after a page of the masters side by side).")
        row.addWidget(self.masters_box)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Page"))
        self.page_box = QtGui.QComboBox()
        for _, label, _ in PAGE_SIZES:
            self.page_box.addItem(label)
        self.page_box.setWhatsThis(u"The PDF's page size, portrait.")
        row.addWidget(self.page_box)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Kerning strings for"))
        self.pairs_box = QtGui.QComboBox()
        for _, label in KERNING_SETS:
            self.pairs_box.addItem(label)
        self.pairs_box.setWhatsThis(u"Every kerned pair (a font with class kerning can have tens of thousands: the PDF "
                                    u"grows with them), or only the pairs common in text (the list <i>Auto Kerning</i>'s "
                                    u"<i>Common pairs</i> uses).")
        row.addWidget(self.pairs_box)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Proof"))
        self.scope_box = QtGui.QComboBox()
        self.scope_box.setWhatsThis(u"What the proof covers: every script the font has, one of them (its letters, with "
                                    u"the figures, punctuation, and symbols), or, after the line, one language the "
                                    u"font covers (its letters; the text section shows its sample alone).")
        self.scopes = [None]
        self.scope_box.addItem(u"Every script")
        row.addWidget(self.scope_box)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Colors"))
        self.colors_box = QtGui.QComboBox()
        for _, label in COLOR_MODES:
            self.colors_box.addItem(label)
        self.colors_box.setWhatsThis(u"The PDF's colors: this window's (its text on its background, light on dark in dark "
                                     u"mode), or black on white, for printing. The page shown beside the list is the PDF "
                                     u"as it will be.")
        row.addWidget(self.colors_box)
        row.addStretch(1)
        layout.addLayout(row)

        checks = QtGui.QHBoxLayout()
        self.section_boxes = {}
        tips = {"charset": u"Every glyph in a grid, in the font's order, with its name and code point.",
                "waterfall": u"A line of sample text at each waterfall size.",
                "text": u"A few lines of sample text in each script the font covers, at each text size.",
                "kerning": u"Every kerned pair between control letters (HH?HOHO, nn?nono), grouped by left glyph.",
                "spacing": u"Each letter and figure between control letters (HHxHOxOO, nnxnoxoo), without kerning.",
                "diacritics": u"The letters with marks, each after its base letter, and the marks.",
                "figures": u"Figures and their alternates, punctuation, and symbols, alone and between letters."}
        for key, label in SECTIONS:
            box = QtGui.QCheckBox(label)
            box.setChecked(True)
            box.setWhatsThis(tips[key])
            checks.addWidget(box)
            self.section_boxes[key] = box
        checks.addStretch(1)
        layout.addLayout(checks)

        sizes = QtGui.QHBoxLayout()
        sizes.addWidget(QtGui.QLabel("Waterfall sizes"))
        self.waterfall_edit = QtGui.QLineEdit(u" ".join(format_size(s) for s in WATERFALL_SIZES))
        self.waterfall_edit.setWhatsThis(u"Point sizes, separated by spaces or commas.")
        sizes.addWidget(self.waterfall_edit, 2)
        sizes.addSpacing(12)
        sizes.addWidget(QtGui.QLabel("Text sizes"))
        self.text_edit = QtGui.QLineEdit(u" ".join(format_size(s) for s in TEXT_SIZES))
        self.text_edit.setWhatsThis(u"Point sizes of the text section's paragraphs.")
        sizes.addWidget(self.text_edit, 1)
        layout.addLayout(sizes)

        splitter = self.splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)
        self.page_list = QtGui.QListWidget()
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
        self.preview.setWhatsThis(u"The selected page as the PDF will be (in the colors <i>Colors</i> says), the whole "
                                  u"page as large as the room here allows: drag the line beside the list, or make the "
                                  u"window larger, to see it larger.")
        splitter.addWidget(self.page_list)
        splitter.addWidget(self.preview)
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
        buttons.addWidget(self.glyph_window_button)
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.rebuild_timer = QtCore.QTimer()
        self.rebuild_timer.setSingleShot(True)
        self.rebuild_timer.setInterval(300)
        self.rebuild_timer.connect("timeout()", self.rebuild)
        self.preview_timer = QtCore.QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.connect("timeout()", self.show_page)
        self.saved_timer = QtCore.QTimer()  # (the window activated: the PDF saved last looked for again)
        self.saved_timer.setSingleShot(True)
        self.saved_timer.setInterval(0)
        self.saved_timer.connect("timeout()", self.update_buttons)
        self.colors_box.connect("currentIndexChanged(int)", lambda index: self.preview_timer.start())
        later = self.rebuild_timer.start
        for box in self.section_boxes.values():
            box.connect("toggled(bool)", lambda on: later())
        for box in (self.masters_box, self.page_box, self.pairs_box, self.scope_box):
            box.connect("currentIndexChanged(int)", lambda index: later())
        for edit in (self.waterfall_edit, self.text_edit):
            edit.connect("editingFinished()", later)
        self.page_list.connect("currentRowChanged(int)", lambda row: self.show_page())
        self.page_list.connect("itemDoubleClicked(QListWidgetItem*)", lambda item: self.show_in_glyph_window())
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.restore_button.connect("clicked()", self.restore_defaults)
        self.save_button.connect("clicked()", self.save_pdf)
        self.open_button.connect("clicked()", self.open_pdf)
        self.close_button.connect("clicked()", dialog.close)
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
                    kind = event.type()
                    if kind == 14 or kind in palette_events:  # Resize, palette changes
                        owner.preview_timer.start()
                    elif kind == 24 and owner.saved:  # WindowActivate
                        owner.saved_timer.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        try:
            watcher = Watcher()
            self.preview.installEventFilter(watcher)
            self.dialog.installEventFilter(watcher)
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
        package = workspace.currentPackage
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def read_font(self):
        """The current font and master (the cached glyphs dropped); False (and said so) when no font is open."""
        self.package = self.current_font()
        self.fonts, self.paths, self.font_glyphs, self.info, self.color_parts = {}, {}, None, None, {}
        if self.package is None:
            self.master = None
            self.proof = None
            self.page_list.clear()
            self.preview.clear()
            self.font_label.setText(u"No font is open. Open one: its proof is laid out at once.")
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

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again and the proof laid out again."""
        self.fonts, self.paths, self.font_glyphs, self.info, self.color_parts = {}, {}, None, None, {}
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
            keep = common_filter(self.common, self.glyph_list()[1])
        return Options(sections, page, parse_sizes(self.waterfall_edit.text, WATERFALL_SIZES),
                       parse_sizes(self.text_edit.text, TEXT_SIZES), keep)

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

    def fill_scopes(self, font, languages):
        """The scopes the font offers (made once per font): its scripts with letters, then the languages it
        covers whole (every base letter), the most spoken first; the choice kept where it still is."""
        key = self.ak.font_key(self.package)
        if getattr(self, "scopes_font", None) == key:
            return
        self.scopes_font = key
        current = self.scopes[max(0, self.scope_box.currentIndex)] if self.scopes else None
        counts = {}
        for name in font.glyphs:
            script = glyph_script(font, name)
            if script is not None and font.has(name):
                counts[script] = counts.get(script, 0) + 1
        scripts = sorted((word for word, n in counts.items() if n >= SCRIPT_MINIMUM), key=lambda word: -counts[word])
        codes = set(code for code, name in font.cmap.items() if font.has(name))
        covered = [language for language in languages
                   if language.base and all(has_character(codes, ch) for ch in language.base)]
        covered.sort(key=lambda language: -(language.speakers or 0))
        self.scope_box.blockSignals(True)
        try:
            self.scope_box.clear()
            self.scopes = [None]
            self.scope_box.addItem(u"Every script")
            for word in scripts:
                self.scopes.append(("script", word))
                self.scope_box.addItem(u"%s only" % SCRIPT_LABELS.get(word, word.title()))
            if covered:
                self.scope_box.insertSeparator(self.scope_box.count)
                self.scopes.append(None)  # (the separator's place)
                for language in covered[:SCOPE_LANGUAGES_MAX]:
                    self.scopes.append(("language", language))
                    self.scope_box.addItem(u"%s (%s)" % (language.name, language.script))
            index = 0
            for at, scope in enumerate(self.scopes):
                if scope is not None and current is not None and scope[0] == current[0] and (
                        scope[1] == current[1] if scope[0] == "script"
                        else (scope[1].iso, scope[1].script) == (current[1].iso, current[1].script)):
                    index = at
            self.scope_box.setCurrentIndex(index)
        finally:
            self.scope_box.blockSignals(False)

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
        self.busy = True
        self.update_buttons()
        row = max(0, self.page_list.currentRow)
        try:
            self.font_label.setText(u"Laying out the proof of %s\N{HORIZONTAL ELLIPSIS}" % self.ak.b(self.package.tfn))
            QtGui.QApplication.processEvents()
            masters = self.masters() if self.masters_box.currentIndex == 1 else [self.master]
            fonts = [self.proof_font(master) for master in masters]
            options = self.options()
            languages = self.load_languages()
            self.fill_scopes(fonts[0], languages)
            scope = self.scopes[max(0, self.scope_box.currentIndex)] if self.scopes else None
            if scope is not None:
                names = scope_names(fonts[0], scope)
                fonts = [restricted(font, names) for font in fonts]
                if scope[0] == "language":
                    languages = [scope[1]]
                else:  # the languages written in that script (all of them, where none is named so: Han)
                    same = [language for language in languages if (u"%s" % language.script).upper() == scope[1]]
                    languages = same or languages
            self.proof = build_proof(fonts, options, languages, info=self.font_info())
            self.page_options = options
            self.note_font(fonts[0], options)
        except Exception as exc:
            self.proof = None
            self.log.add(u"The proof could not be laid out: %s" % self.ak.html(exc), "error")
        finally:
            self.busy = False
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
                        text += u" \N{EM DASH} %s" % page.master
                    self.page_list.addItem(text)
                self.page_list.setCurrentRow(min(row, len(self.proof.pages) - 1))
        finally:
            self.page_list.blockSignals(False)
        self.show_page()

    def status(self):
        b = self.ak.b
        if self.proof is None:
            self.font_label.setText(u"%s: no proof (see the log)." % b(self.package.tfn))
            return
        counts = self.proof.section_pages()
        parts = [u"%s %d" % (title.lower(), counts[key]) for key, title in SECTIONS if key in counts]
        size = dict((key, label) for key, label, _ in PAGE_SIZES).get(self.page_options.page, u"")
        masters = self.proof.masters
        which = u"master %s" % b(masters[0]) if len(masters) == 1 else b(counted(len(masters), u"master"))
        text = u"%s, %s: %s (%s)." % (b(self.package.tfn), which, b(counted(len(self.proof.pages), u"page")), size)
        if parts:
            text += u" Pages per section: %s." % u", ".join(parts)
        pairs = u", ".join(u"%s in %s" % (counted(count, u"kerned pair"), master)
                           for count, master in zip(self.proof.kerned, masters))
        text += u" Kerning applied (%s, classes resolved); OpenType features not applied." % pairs
        if self.proof.left_out:
            text += u" No text for %s: it needs shaping." % u", ".join(self.proof.left_out)
        self.font_label.setText(text)

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
            size = (max(60, self.ak._property(self.preview, "width") - 2),
                    max(60, self.ak._property(self.preview, "height") - 2))
            self.preview.setPixmap(page_pixmap(QtCore, QtGui, page, renderer, size, page_size(self.page_options.page),
                                               QtGui.QColor(*paper), self.pixel_ratio()))
        except Exception as exc:
            self.preview.clear()
            self.log.add(u"The page could not be drawn: %s" % self.ak.html(exc), "error")
        self.update_buttons()

    # -- buttons --------------------------------------------------------------

    def defaults_changed(self):
        sections = [self.section_boxes[key].isChecked() for key, _ in SECTIONS]
        return (not all(sections) or self.page_box.currentIndex != 0 or self.pairs_box.currentIndex != 0
                or self.masters_box.currentIndex != 0 or self.colors_box.currentIndex != 0
                or self.scope_box.currentIndex > 0
                or parse_sizes(self.waterfall_edit.text, ()) != tuple(float(s) for s in WATERFALL_SIZES)
                or parse_sizes(self.text_edit.text, ()) != tuple(float(s) for s in TEXT_SIZES))

    def update_buttons(self):
        enable = self.ak.enable
        ready = self.proof is not None and bool(self.proof.pages) and not self.busy
        enable(self.save_button, ready)
        enable(self.open_button, self.saved_there())
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
        self.waterfall_edit.setText(u" ".join(format_size(s) for s in WATERFALL_SIZES))
        self.text_edit.setText(u" ".join(format_size(s) for s in TEXT_SIZES))
        self.rebuild_timer.start()
        self.log.add(u"Settings restored to the defaults.")

    def show_in_glyph_window(self):
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
        try:
            def progress(done, total):
                self.font_label.setText(u"Writing page %s of %s\N{HORIZONTAL ELLIPSIS}" % (b(done), b(total)))
                QtGui.QApplication.processEvents()

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
    held = getattr(sys, "_freelab_proof", None)
    if held is not None:
        try:
            held.dialog.close()
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
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_proof":
    main()
