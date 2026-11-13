"""Build Font Check's font, FreeLang, five files in checks/language_font (FreeLang-Essential.ttf,
FreeLang-CJK.ttf, FreeLang-Extended-General.ttf, FreeLang-Extended-Mongolian-Tibetan.ttf, and
FreeLang-Extended-Duployan.ttf: the table FONTS, where a sixth would be one more entry): every
character its lists, tooltips, and pictures of missing characters show, from Noto fonts and, for the
characters and scripts no Noto font has, Andika, Unicodia Funky, Kanchenjunga, Kedebideri, Daarage,
Padauk Book, Shafarik, and BabelStone Pseudographica (all under the SIL Open Font License 1.1),
subset, merged, and renamed. Each source goes whole into one of the five (group_of), but the one
listed in ELSEWHERE, a few of whose characters go into another font; each character is in one of
them, and the five share one line. A source keeps its layout only if a language's text draws from it
(SET_ONLY), but in a font that is its sources' own (Tibetan and Mongolian, Duployan), where they keep
it whole. The build stops, naming the font and its heaviest sources, when a font would pass a limit
(check_limits: 65,535 glyphs, and layout lookups within 65,535 bytes).

The lists show each language as "Name (autonym)" under its script's heading ("Cyrillic (92)"), the
characters it misses ("ß", "Ǎ ǎ +1", a mark on a dotted circle), the character sets and their
characters, and in tooltips the languages' other names. Drawn in the dialog's font, Qt 5 took each
character the font lacks from another font, and some lists looked uneven (Cyrillic autonyms spaced
wide, rare scripts as boxes). With this one font as their family, every character comes from one
family of designs. What it must draw is checks/font_characters.json (checks/train/orthographies.py
--characters writes it from the data files): the names, the other names, the orthographies' base,
auxiliary, and mark characters, and the character sets'. Every one of them a Noto font has is bundled,
the Hangul syllables, ideographs, cuneiform signs, and hieroglyphs included. What no Noto font has
comes from the sources of EXTRA, looked in last (Noto Emoji, then Andika, then Unicodia Funky, each
an outline font: no source is a bitmap's pixels); language_font.json lists what each source supplies,
and the characters no source has. Andika's letters meet Noto Sans's marks through their own anchors,
carried into Noto Sans's lookups (carry_anchors), and so do Unicodia Funky's four combining
parentheses, which are in the Essential font for that (ELSEWHERE). The fonts added on 2026-11-13 (ADDED,
LAST_RESORT) are looked in after the earlier ones, so a character an earlier build drew keeps its source.

    python checks/train/language_font.py [--cache <folder>] [--dry-run] [--fresh] [--repin]
    python checks/train/language_font.py --stage subsets [--seconds 400]   (as many runs as it asks for)
    python checks/train/language_font.py --stage merge --font "Extended General"   (one font, kept in the work folder)
    python checks/train/language_font.py --stage merge   (the fonts not merged yet, then the five written)

Python 3 with fontTools and uharfbuzz (pip install uharfbuzz, in a virtual environment): HarfBuzz
measures the ink the line must hold and checks that the merged font shapes every text as its source
font does. Without it the font is still built, but its line is not set and nothing is checked
(language_font.json then says "shaping_checked": false): do not ship that build. The same sources give
the same bytes with the same fontTools and uharfbuzz (fontTools packs layout tables through HarfBuzz
when it is installed); language_font.json records both versions.

The fonts come over HTTPS into the cache folder (default %LOCALAPPDATA%\\FreeLab\\corpus\\
language-font-sources), outside the repository: Noto's static TrueType fonts from notofonts.github.io
(the notofonts organization's released files), and Noto Sans JP, KR, and SC and Noto Emoji from
google/fonts (variable TrueType builds, instanced at Regular), each repository at a pinned commit;
the others from their release archives on GitHub at pinned versions or from Unicodia's repository at a
pinned commit (RELEASES). A file or an archive whose SHA-256 is not the one language_font.json
recorded stops the build (--repin accepts new sources). Each font's name table must declare the SIL
Open Font License, and its license must reserve no name FreeLang uses. Each subset is kept in the cache
folder's work folder with its recipe, and made again only when the recipe changes (or with --fresh),
so a build can be made in several short runs. Run it through the machine guard: the CJK fonts are large.

After checks/font_characters.json changes: --stage plan (who supplies what, and what no source has),
then --stage subsets until it says every subset is made, then --stage merge (a font at a time with
--font, each its own command, then once without: a merge is kept in the work folder until its subsets
change); no --repin unless a source was added or a pin moved. The tests' lists
(tests/language_font_tests.py: NOT_SUPPLIED, OTHER_SOURCES) then say what changed. The merge ends with
a table of the fonts (sources, characters, glyphs, lookup bytes, size), which language_font.json
records. When a font nears a limit (it says so from WARN_AT on), move its source with the most lookup
bytes, or the most glyphs, to a font of its own: one entry in FONTS that names the source.
"""

import argparse
import collections
import hashlib
import json
import os
import sys
import time
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import fontTools
from fontTools import subset
from fontTools import unicodedata as ucd
from fontTools.merge import Merger
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
LANGUAGES_FILES = (os.path.join(CHECKS, "language_coverage.json"), os.path.join(CHECKS, "language_orthographies.json"))
FAMILIES_FILE = os.path.join(CHECKS, "language_families.json")
SETS_FILE = os.path.join(CHECKS, "character_sets.json")
CHARACTERS_FILE = os.path.join(CHECKS, "font_characters.json")  # checks/train/orthographies.py --characters
PARTS = ("names", "other_names", "orthographies", "sets")
OUT_DIR = os.path.join(CHECKS, "language_font")
LICENSE_FILE, INFO_FILE = "FreeLang_LICENSE", "language_font.json"
FAMILY = "FreeLang"  # the fonts together, as the tools name them to the user
# The fonts, a table: adding one is one entry. One font cannot hold it all: with every script's layout
# the sources bring 68,943 glyphs (a font holds 65,535) and 4,563 substitution lookups (a GSUB table
# about half as many: each must lie within 65,535 bytes of the table's list). Each source goes whole
# into one font (group_of; ELSEWHERE is the one exception); Font Check registers the fonts and has Qt
# fall back from the first to the others, in this order.
#   label: what the font is called in language_font.json and on the command line (--font), in ASCII;
#     its family is "FreeLang " and the label, but for a character ASCII lacks (Diacritics hides the
#     families that start with "FreeLang ").
#   sources: the source fonts it holds, named (they are taken first), or a rule of RULES, tried in the
#     table's order for every source no font names.
#   own_layout: True where the font is its named sources' own, so that their running text shapes: they
#     keep their layout whole, whatever the rule of SET_ONLY says. This is an exception to that rule,
#     for Noto Serif Tibetan and Noto Sans Mongolian together (Tibetan's lookups are half of what a
#     table can reach, and Mongolian's letters join) and for Noto Sans Duployan alone (9,522 glyphs and
#     most of a table's reach): no other font's budget could afford them.
#   optional: True for a font the tools work without (Font Check skips a fallback file that is not
#     there); the build makes it like the others.
Font = collections.namedtuple("Font", "label family file postscript sources own_layout optional")
# The fourth font's family name, held here alone: its joining character is the owner's choice, an en
# dash (U+2013), written as an escape; another would be this one line, and the same name in
# LIST_FONT_FALLBACKS of checks/freelab_font_check.py, which the tests compare with it. The font's
# own copy of its name's characters follows this (NAME_SUBSETS). The label, the file name, and the
# PostScript name stay ASCII: a PostScript name must be, and FontLab's Python 2.7 opens paths through
# the ANSI code page.
MONGOLIAN_TIBETAN = "FreeLang Extended Mongolian\N{EN DASH}Tibetan"
# Windows names a font's family in at most 31 characters (GDI's LOGFONT face name, LF_FACESIZE 32 with
# its terminator), and Qt 5 registers an application font through GDI under its legacy family name
# (name ID 1), cut to that length: a longer name matches nothing, and Qt never lists the family (seen
# in FontLab 7.2 on 2026-11-13, where "FreeLang Extended Mongolian-Tibetan", 35 characters, was absent
# and Mongolian came from Mongolian Baiti). A family past the limit keeps its full name as the
# typographic family (name IDs 16 and 17, which DirectWrite and macOS show) and full name (ID 4), and
# takes the shorter one here as its legacy family, the name Qt and Font Check know it by.
GDI_FAMILY_LIMIT = 31
GDI_FAMILIES = {MONGOLIAN_TIBETAN: "FreeLang Mongolian\N{EN DASH}Tibetan"}


def gdi_family(family):
    """The family name Windows and Qt know a font by (name ID 1): its family, or GDI_FAMILIES's shorter one."""
    name = GDI_FAMILIES.get(family, family)
    if len(name) > GDI_FAMILY_LIMIT:
        raise SystemExit("%r: %d characters, past the %d of a Windows family name (GDI_FAMILIES)" % (
            name, len(name), GDI_FAMILY_LIMIT))
    return name


# Essential is the one file the repository holds; the other four are optional, published beside each
# release (README.md says where they go), and Qt takes their characters from the system's fonts without them.
FONTS = (
    Font("Essential", "FreeLang Essential", "FreeLang-Essential.ttf", "FreeLangEssential-Regular",
         "recommended", False, False),
    Font("CJK", "FreeLang CJK", "FreeLang-CJK.ttf", "FreeLangCJK-Regular", "cjk", False, True),
    Font("Extended General", "FreeLang Extended General", "FreeLang-Extended-General.ttf",
         "FreeLangExtendedGeneral-Regular", "rest", False, True),
    Font("Extended Mongolian-Tibetan", MONGOLIAN_TIBETAN, "FreeLang-Extended-Mongolian-Tibetan.ttf",
         "FreeLangExtendedMongolianTibetan-Regular", ("NotoSansMongolian", "NotoSerifTibetan"), True, True),
    Font("Extended Duployan", "FreeLang Extended Duployan", "FreeLang-Extended-Duployan.ttf",
         "FreeLangExtendedDuployan-Regular", ("NotoSansDuployan",), True, True),
)
NAMES_USED = " ".join(name for font in FONTS for name in (font.family, font.postscript))  # (no source may reserve any of it)
# The two limits of a font, checked for each before it is merged (check_limits). Its glyph indices are
# 16 bits wide. Its layout lookups are reached by 16-bit offsets, the lookups from their list and each
# lookup's subtables from the lookup: lookup_bytes counts the list laid out the plainest way that
# always packs (each lookup followed by its subtables' extension records, which reach the subtables
# themselves by 32-bit offsets), for GSUB and for GPOS, and the larger must stay within 65,535. A table
# a little past that may still pack another way (the Essential font of the three-font build did, at
# 66,480); the build refuses it all the same, since a table that does not pack fails only
# after minutes, and room is what the table of fonts is for. From WARN_AT of a limit on, the build says so.
MAX_GLYPHS = 65535
MAX_LOOKUP_BYTES = 65535
WARN_AT = 0.9
# Unicode's Recommended Scripts (UAX #31, Unicode Identifiers and Syntax, revision 43 for Unicode 17.0,
# Table 5, https://www.unicode.org/reports/tr31/tr31-43.html#Table_Recommended_Scripts), by their ISO
# 15924 codes, Common and Inherited aside: the scripts "in widespread modern customary use". The ones
# written with Chinese characters, Hangul, and kana are the CJK font's; the fonts of the others are the
# Essential font's, with the general punctuation, digits, currency signs, and combining marks that
# Noto Sans draws, but Tibetan's, which FONTS names for a font of its own; every other source is the
# Extended General font's. (Bopomofo is not in the table: it is in the CJK font because Noto Sans SC,
# a source of that font, draws it.)
RECOMMENDED = ("Arab", "Armn", "Beng", "Cyrl", "Deva", "Ethi", "Geor", "Grek", "Gujr", "Guru", "Hani",
               "Hang", "Hebr", "Hira", "Knda", "Kana", "Khmr", "Laoo", "Latn", "Mlym", "Mymr", "Orya", "Sinh",
               "Taml", "Telu", "Thaa", "Thai", "Tibt")
CJK_SCRIPTS = ("Hani", "Hang", "Hira", "Kana", "Bopo")
VERSION = "2.100"
UNITS_PER_EM = 1000  # every source's today; one drawn on another em is scaled to it
RECIPE = 2  # of a subset: raise it when subset_font changes what it makes
MERGE_RECIPE = 1  # of a merged font kept in the work folder: raise it when the merge changes what it makes
RAW_URL = "https://raw.githubusercontent.com/%s/%s/%s"
NOTO = ("notofonts/notofonts.github.io", "4cf78353cd1668040ba8efa13029cd910fcdf9e2")  # main on 2026-11-09
GOOGLE = ("google/fonts", "c30b221beb0c1da59d563feb91ec8656a1fa972a")  # main on 2026-11-11
CACHE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus", "language-font-sources")

# What the lists show besides the data: the column headings, a heading's count in parentheses, "+N"
# past the missing characters shown, a mark on a dotted circle, and Qt's ellipsis for elided text; the
# rest of ASCII and common punctuation for good measure.
UI_TEXT = (u"".join(chr(c) for c in range(0x20, 0x7F)) + u"\N{NO-BREAK SPACE}\N{MIDDLE DOT}\N{HORIZONTAL ELLIPSIS}"
           u"\N{DOTTED CIRCLE}\N{EN DASH}\N{EM DASH}\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
           u"\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}\N{BULLET}")
NOT_A_SCRIPT = ("Zyyy", "Zinh", "Zzzz")

# The fonts of each script, first that has the character: Noto's static fonts (notofonts.github.io/
# fonts/<family>/unhinted/ttf/<family>-Regular.ttf), or google/fonts' CJK ones (ofl/<folder>/<file>).
STATIC = {
    "Latn": ("NotoSans", "NotoSerif"), "Grek": ("NotoSans", "NotoSerif"), "Cyrl": ("NotoSans", "NotoSerif"),
    "Armn": "NotoSansArmenian", "Hebr": "NotoSansHebrew",
    "Arab": ("NotoSansArabic", "NotoNaskhArabic", "NotoKufiArabic"),
    "Syrc": "NotoSansSyriac", "Thaa": "NotoSansThaana",
    "Nkoo": "NotoSansNKo", "Deva": "NotoSansDevanagari", "Beng": "NotoSansBengali", "Guru": "NotoSansGurmukhi",
    "Gujr": "NotoSansGujarati", "Orya": "NotoSansOriya", "Taml": ("NotoSansTamil", "NotoSansTamilSupplement"),
    "Telu": "NotoSansTelugu",
    "Knda": "NotoSansKannada", "Mlym": "NotoSansMalayalam", "Sinh": "NotoSansSinhala", "Thai": "NotoSansThai",
    "Laoo": "NotoSansLao", "Tibt": "NotoSerifTibetan", "Mymr": "NotoSansMyanmar", "Geor": "NotoSansGeorgian",
    "Khmr": "NotoSansKhmer", "Ethi": "NotoSansEthiopic", "Cher": "NotoSansCherokee",
    "Cans": "NotoSansCanadianAboriginal", "Tfng": "NotoSansTifinagh", "Vaii": "NotoSansVai",
    "Tavt": "NotoSansTaiViet", "Lana": "NotoSansTaiTham", "Bamu": "NotoSansBamum", "Bugi": "NotoSansBuginese",
    "Hano": "NotoSansHanunoo", "Kali": "NotoSansKayahLi", "Yiii": "NotoSansYi", "Avst": "NotoSansAvestan",
    "Egyp": "NotoSansEgyptianHieroglyphs", "Xsux": "NotoSansCuneiform", "Lina": "NotoSansLinearA",
    "Linb": "NotoSansLinearB", "Cakm": "NotoSansChakma", "Sarb": "NotoSansOldSouthArabian",
    "Copt": "NotoSansCoptic", "Ogam": "NotoSansOgham", "Runr": "NotoSansRunic", "Goth": "NotoSansGothic",
    "Mong": "NotoSansMongolian", "Olck": "NotoSansOlChiki", "Adlm": "NotoSansAdlam", "Talu": "NotoSansNewTaiLue",
    "Tale": "NotoSansTaiLe", "Bali": "NotoSansBalinese", "Java": "NotoSansJavanese", "Sund": "NotoSansSundanese",
    # The scripts of the second orthography file (checks/language_orthographies.json):
    "Plrd": "NotoSansMiao", "Tnsa": "NotoSansTangsa", "Osge": "NotoSansOsage", "Tang": "NotoSerifTangut",
    "Hmnp": "NotoSerifNPHmong", "Hung": "NotoSansOldHungarian", "Limb": "NotoSansLimbu",
    "Sylo": "NotoSansSylotiNagri", "Rohg": "NotoSansHanifiRohingya", "Sunu": "NotoSansSunuwar",
    "Toto": "NotoSerifToto", "Hluw": "NotoSansAnatolianHieroglyphs", "Ital": "NotoSansOldItalic",
    "Nbat": "NotoSansNabataean", "Mroo": "NotoSansMro", "Lydi": "NotoSansLydian", "Palm": "NotoSansPalmyrene",
    "Nagm": "NotoSansNagMundari", "Armi": "NotoSansImperialAramaic", "Elym": "NotoSansElymaic",
    "Lyci": "NotoSansLycian", "Ugar": "NotoSansUgaritic", "Samr": "NotoSansSamaritan",
    "Phli": "NotoSansInscriptionalPahlavi", "Ougr": "NotoSerifOldUyghur", "Prti": "NotoSansInscriptionalParthian",
    "Medf": "NotoSansMedefaidrin", "Cari": "NotoSansCarian", "Narb": "NotoSansOldNorthArabian",
    "Mani": "NotoSansManichaean", "Wcho": "NotoSansWancho", "Newa": "NotoSansNewa",
    # A script no Noto font draws (Noto's own overview of its coverage lists it as unsupported): the
    # font made for it, under the same license. Kirat Rai: SIL's Kanchenjunga (see RELEASES).
    "Krai": "Kanchenjunga",
}
# The scripts added on 2026-11-13, when checks/font_characters.json took in every script of at most
# 300 characters and every symbol and notation block of at most 256: their fonts are looked in after
# every font above (candidates), so a character an earlier build drew keeps its source, and no font
# here takes a character an earlier font has. Noto's font where there is one; for the scripts no Noto
# font draws, the font made for the script (see RELEASES): SIL's Kedebideri (Beria Erfe), Daarage
# (Tulu-Tigalari), and Unicodia Funky (Garay, Gurung Khema, Ol Onal, Sidetic, and Tolong Siki).
ADDED = {
    "Aghb": "NotoSansCaucasianAlbanian", "Ahom": "NotoSerifAhom", "Bass": "NotoSansBassaVah",
    "Batk": "NotoSansBatak", "Bhks": "NotoSansBhaiksuki", "Brah": "NotoSansBrahmi", "Buhd": "NotoSansBuhid",
    "Cham": "NotoSansCham", "Chrs": "NotoSansChorasmian", "Cpmn": "NotoSansCyproMinoan",
    "Cprt": "NotoSansCypriot", "Diak": "NotoSerifDivesAkuru", "Dogr": "NotoSerifDogra",
    "Dsrt": "NotoSansDeseret", "Dupl": "NotoSansDuployan", "Elba": "NotoSansElbasan",
    "Glag": "NotoSansGlagolitic", "Gong": "NotoSansGunjalaGondi", "Gonm": "NotoSansMasaramGondi",
    "Gran": "NotoSansGrantha", "Hatr": "NotoSansHatran", "Hmng": "NotoSansPahawhHmong",
    "Kawi": "NotoSansKawi", "Khar": "NotoSansKharoshthi", "Khoj": "NotoSansKhojki", "Kthi": "NotoSansKaithi",
    "Lepc": "NotoSansLepcha", "Lisu": "NotoSansLisu", "Mahj": "NotoSansMahajani", "Maka": "NotoSerifMakasar",
    "Mand": "NotoSansMandaic", "Marc": "NotoSansMarchen", "Mend": "NotoSansMendeKikakui",
    "Merc": "NotoSansMeroitic", "Mero": "NotoSansMeroitic", "Modi": "NotoSansModi",
    "Mtei": "NotoSansMeeteiMayek", "Mult": "NotoSansMultani", "Nand": "NotoSansNandinagari",
    "Orkh": "NotoSansOldTurkic", "Osma": "NotoSansOsmanya", "Pauc": "NotoSansPauCinHau",
    "Perm": "NotoSansOldPermic", "Phag": "NotoSansPhagsPa", "Phlp": "NotoSansPsalterPahlavi",
    "Phnx": "NotoSansPhoenician", "Rjng": "NotoSansRejang", "Saur": "NotoSansSaurashtra",
    "Shaw": "NotoSansShavian", "Shrd": "NotoSansSharada", "Sidd": "NotoSansSiddham",
    "Sind": "NotoSansKhudawadi", "Sogd": "NotoSansSogdian", "Sogo": "NotoSansOldSogdian",
    "Sora": "NotoSansSoraSompeng", "Soyo": "NotoSansSoyombo", "Tagb": "NotoSansTagbanwa",
    "Takr": "NotoSansTakri", "Tglg": "NotoSansTagalog", "Tirh": "NotoSansTirhuta", "Todr": "NotoSerifTodhri",
    "Vith": "NotoSansVithkuqi", "Wara": "NotoSansWarangCiti", "Xpeo": "NotoSansOldPersian",
    "Yezi": "NotoSerifYezidi", "Zanb": "NotoSansZanabazarSquare",
    "Berf": "Kedebideri", "Tutg": "Daarage",
    "Gara": "UnicodiaFunky", "Gukh": "UnicodiaFunky", "Onao": "UnicodiaFunky", "Sidt": "UnicodiaFunky",
    "Tols": "UnicodiaFunky",
}
# Noto's fonts of notations and numbers that are no script's, added with them and looked in after them.
# Then two fonts that each have one character no font above has: Noto Serif Khojki (U+11241, which Noto
# Sans Khojki lacks) and Noto Sans Syriac Western (the combining dot U+1DFA).
ADDED_LAST = ("NotoZnamennyMusicalNotation", "NotoSansMayanNumerals", "NotoSerifOttomanSiyaq",
              "NotoSerifKhojki", "NotoSansSyriacWestern")
CJK = {  # google/fonts' variable TrueType fonts: the CJK ones, and Noto Emoji (see EXTRA)
    "NotoSansJP": ("notosansjp", "NotoSansJP[wght].ttf"), "NotoSansKR": ("notosanskr", "NotoSansKR[wght].ttf"),
    "NotoSansSC": ("notosanssc", "NotoSansSC[wght].ttf"), "NotoEmoji": ("notoemoji", "NotoEmoji[wght].ttf"),
}
CJK_ORDER = {"Hani": ("NotoSansJP", "NotoSansSC", "NotoSansKR"), "Hira": ("NotoSansJP",),
             "Kana": ("NotoSansJP",), "Hang": ("NotoSansKR",), "Bopo": ("NotoSansSC",)}
# An ideograph is drawn as the writing of its rows draws it (the Chinese orthographies, Japanese's
# kanji, Korean's hanja), the most rows first; one no row has (an other name's), in CJK_ORDER's order.
HANI_FONT = {"Chinese": "NotoSansSC", "Kanji": "NotoSansJP", "Hanja": "NotoSansKR"}
# For what no script's font has: punctuation, and the character sets' symbols (mathematical
# alphanumerics and operators, arrows, technical symbols, box drawing, dingbats, music).
GENERAL = ("NotoSans", "NotoSansMath", "NotoSansSymbols", "NotoSansSymbols2", "NotoSansMono", "NotoSerif",
           "NotoMusic", "NotoSansJP", "NotoSansSC", "NotoSansKR")
# Last, any other font listed here: a sign that belongs to no script's texts (the baht sign in a
# character set is in the Thai font alone).
LAST = ("NotoSansIndicSiyaqNumbers",)
# After every font above, for what none of them has, in this order; a font here never takes a
# character an earlier font draws. Noto Emoji (the monochrome font) has the emoji of the technical
# and dingbat blocks. Andika (SIL's sans serif) has the Latin and Cyrillic letters of Unicode 16 that
# Noto Sans and Noto Serif 2.015 lack. Unicodia Funky (the font Unicodia, a Unicode browser, fills
# Noto's gaps with; its author contributes scripts to Noto) has the rest: four combining parentheses,
# two Garay signs, and ten symbols of Unicode 17, drawn as outlines on Noto's own measures (its dotted
# circle and mark heights are Noto's). It has Andika's eight letters too, in a serif design, which is
# why Andika is looked in first. Until 2026-11-13 the sixteen came from GNU Unifont, a bitmap's pixels.
EXTRA = ("NotoEmoji", "Andika", "UnicodiaFunky")
# After those, since 2026-11-13, for what none of them has either, three fonts that each draw a few
# characters alone (their character map is enough): Padauk Book (SIL's Myanmar font: the twenty digits
# of Myanmar Extended-C), Shafarik (a font for Glagolitic and old Cyrillic: the two Glagolitic letters
# of Unicode 14, which Noto Sans Glagolitic lacks), and BabelStone Pseudographica (a font of box
# drawing and terminal graphics, drawn as outlines: the arrows and legacy computing symbols of
# Unicode 16).
LAST_RESORT = ("Padauk", "Shafarik", "BabelStonePseudographica")
# The sources outside the two pinned repositories, each a release pinned by its version or a file of a
# repository at a pinned commit: {family: ((URL, member of that archive or None) of the font, the same
# of its license)}.
ANDIKA = "https://github.com/silnrsi/font-andika/releases/download/v7.000/Andika-7.000.zip"
UNICODIA = "https://raw.githubusercontent.com/Mercury13/unicodia/df2b09c61e8fdc06f96fc6d6b194427f61bb2e38/Fonts/"  # main on 2026-11-13
KANCHENJUNGA = "https://github.com/silnrsi/font-kanchenjunga/releases/download/v2.001/Kanchenjunga-2.001.zip"
KEDEBIDERI = "https://github.com/silnrsi/font-kedebideri/releases/download/v3.001/Kedebideri-3.001.zip"
PADAUK = "https://github.com/silnrsi/font-padauk/releases/download/v6.000/PadaukBook-6.000.zip"
DIVES_AKURU = ("https://github.com/notofonts/dives-akuru/releases/download/NotoSerifDivesAkuru-v1.001/"
               "NotoSerifDivesAkuru-v1.001.zip")
RELEASES = {
    "Andika": ((ANDIKA, "Andika-7.000/Andika-Regular.ttf"), (ANDIKA, "Andika-7.000/OFL.txt")),
    "Kanchenjunga": ((KANCHENJUNGA, "Kanchenjunga-2.001/Kanchenjunga-Regular.ttf"), (KANCHENJUNGA, "Kanchenjunga-2.001/OFL.txt")),
    "UnicodiaFunky": ((UNICODIA + "UnicodiaFunky.ttf", None), (UNICODIA + "LICENSE-Funky", None)),
    "Kedebideri": ((KEDEBIDERI, "Kedebideri-3.001/Kedebideri-Regular.ttf"), (KEDEBIDERI, "Kedebideri-3.001/OFL.txt")),
    "Daarage": ((UNICODIA + "UnicodiaDaarage.otf", None), (UNICODIA + "LICENSE-Daarage", None)),
    "Padauk": ((PADAUK, "PadaukBook-6.000/PadaukBook-Regular.ttf"), (PADAUK, "PadaukBook-6.000/OFL.txt")),
    "Shafarik": ((UNICODIA + "Shafarik-Regular.ttf", None), (UNICODIA + "LICENSE-Shafarik", None)),
    "BabelStonePseudographica": ((UNICODIA + "BabelStonePseudographica.ttf", None), (UNICODIA + "LICENSE-BabelStone", None)),
    # Noto Serif Dives Akuru 2.000, the version of the pinned commit, draws 49 of the script's 72
    # characters; 1.001 draws them all, and is taken whole from the project's own release.
    "NotoSerifDivesAkuru": ((DIVES_AKURU, "NotoSerifDivesAkuru/unhinted/ttf/NotoSerifDivesAkuru-Regular.ttf"), (DIVES_AKURU, "../OFL.txt")),
}
# Fonts whose license file is a notice that names the SIL Open Font License without carrying its text
# (the text is in the other sources' files), and whose name table declares the license and its version
# in the copyright record, having no license record.
LICENSE_NOTICE = ("UnicodiaFunky",)
# Fonts whose name table declares nothing (no copyright record, no license record): their license is
# the file their repository ships beside them, the SIL Open Font License 1.1 whole under their
# copyright line, which is read from that file's first line; {family: the name it is listed under}
# (Daarage's name records are its maker's working title).
LICENSE_BESIDE = {"Daarage": "Daarage"}
# Fonts drawn with cubic curves (a CFF table): their outlines are converted to TrueType's quadratic
# ones (quadratic_outlines). Every other source has TrueType outlines, and none else is converted.
CUBIC = ("Daarage",)
# Fonts that color parts of their glyphs (COLR and CPAL tables: Znamenny notation's red signs) over
# plain outlines that draw the whole glyph in one color: the color tables are dropped, and the glyphs
# are drawn as a program without color fonts draws them. No other source may have a color table.
ONE_COLOR = ("NotoZnamennyMusicalNotation",)
# The one exception to "each source whole in one font": {source: (the label of another font of FONTS,
# the characters that go there)}. The source is then cut in two subsets, its own and a second one, named
# "<source>@<label>" (part_key), which is merged into that other font and is in every other respect
# its source's (the same file, pin, license, and kind of layout: base_family). Unicodia Funky's four
# combining parentheses (U+1AC1 to U+1AC4, Combining Diacritical Marks Extended) are marks of Latin
# phonetic text: in the Essential font their anchors are carried onto Noto Sans's letters, dotted
# circle, and other marks (ANCHORED), which the rest of Unicodia Funky, in the Extended General font,
# has no use for.
ELSEWHERE = {"UnicodiaFunky": ("Essential", "1AC1-1AC4")}
PART = "@"
# The one exception to "each character in one font": every font but the one that holds FIRST also has
# the characters of its own family name (the letters, the space, the fourth font's joining character),
# so that its name drawn in itself, as a font list draws it, shows whole. They are a second subset of
# FIRST (Noto Sans, the design of the Essential font's Latin), named like ELSEWHERE's ("NotoSans@<label>"),
# with the character map alone (no kerning: it would cost every font lookups for a name). The first
# font comes first where Qt falls back, so running text still takes these characters from it. build()
# lists the subsets here.
NAME_SUBSETS = set()
# The fonts of EXTRA whose letters take Noto Sans's marks, and whose marks sit on Noto Sans's letters
# and dotted circle: their own anchors are carried into Noto Sans's lookups after the merge
# (carry_anchors), since each character comes from one source and no source's positioning knows another's
# glyphs. Only what is in Noto Sans's font is carried (Andika, and Unicodia Funky's part of ELSEWHERE).
ANCHORED = ("Andika", "UnicodiaFunky")
FIRST = "NotoSans"  # merged first: its space, .notdef, and Latin set the font's defaults
HOST_SCRIPTS = ("Latn", "Grek", "Cyrl")  # what it draws: the scripts whose guests' anchors are carried (meets_host)
# Layout kept per source. A font that draws names, autonyms, and orthographies keeps every feature but
# the vertical ones (the tool sets no vertical text): conjuncts, reordering, marks' positions, contextual
# forms, as the first builds kept them. A font listed here draws isolated characters only (a character
# set's symbols, signs in a row): its character map is enough, and its features would bring variants
# nothing reaches (the mathematical font's sizes and script styles, the hieroglyphs' and signs' joined forms).
# The fonts of EXTRA too: their letters' marks come from other fonts, which their positioning does not
# know (see ANCHORED for what is carried instead), and their alternates (Andika's small capitals and
# character variants) are reached by nothing.
CMAP_ONLY = ("NotoSansMath", "NotoSansSymbols", "NotoSansSymbols2", "NotoSansMono", "NotoMusic",
             "NotoSansCuneiform", "NotoSansEgyptianHieroglyphs", "NotoSansAnatolianHieroglyphs", "NotoSerifTangut",
             "NotoZnamennyMusicalNotation", "NotoSansMayanNumerals") + EXTRA + LAST_RESORT
# The rule for every other source, in the fonts alike: it keeps its layout only if some character
# it supplies is in a language's name, autonym, other name, or orthography (the names, other_names, and
# orthographies parts of checks/font_characters.json, and the data files' texts), since only those are
# ever set as running text. A source whose characters are a character set's alone (a script's or a
# block's: shown one at a time, in a list cell, a tooltip, or a picture) keeps its character map alone:
# build() lists those here. Without the rule the Extended General font cannot be written: a GSUB
# table's lookups must lie within 65,535 bytes of its list, and those of its sources would need about
# 62,800 (as counted when the font was one of three). One at a time, a character is drawn the same with or without its font's layout. The
# exception is a font of FONTS with own_layout: its named sources keep their layout whole (Noto Sans
# Mongolian and Noto Sans Duployan, which the rule cut to their character maps while they shared a font).
SET_ONLY = set()
# A text or two of each source that keeps its layout by that exception, as code points: no language's
# text draws from it, so the data files give the shaping check (shaping_differences) nothing to shape
# with it. Mongolian: the script's name in itself, its letters joined, and a letter with a variation
# selector. Duployan: letters and vowels that join and reorder.
SAMPLES = {"NotoSansMongolian": ("182E 1823 1829 182D 1823 182F", "182A 1822 1834 1822 182D", "182D 180B 1820"),
           "NotoSansDuployan": ("1BC02 1BC41 1BC1A 1BC46 1BC04", "1BC1B 1BC53 1BC0A 1BC5B 1BC06", "1BC14 1BC47 1BC07 1BC9D 1BC41")}
VERTICAL = ("vert", "vrt2", "vkna", "vhal", "vpal", "valt", "vkrn", "vchw")
OPEN_FONT_LICENSE = ("open font license", "scripts.sil.org/ofl", "openfontlicense")  # as kerning/train/dataset.py
PROPRIETARY = ("microsoft supplied font", "any other use is prohibited", "end user license agreement")
# OS/2 code page bits Qt 5 reads as writing systems (Latin 1, 2, Turkish, Baltic, Vietnamese; Cyrillic;
# Greek; Hebrew; Arabic; Thai; Japanese; Chinese; Korean): a list font must claim each script it draws,
# or Qt takes another family for that script's runs.
CODE_PAGES = {"Latn": (0, 1, 4, 7, 8), "Cyrl": (2,), "Grek": (3,), "Hebr": (5,), "Arab": (6,), "Thai": (16,),
              "Hira": (17,), "Kana": (17,), "Hani": (18, 20), "Hang": (19,)}


def say(text):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.flush()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:  # LF, as the repository keeps
        handle.write(text)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def codes_of(text):
    """The code points of hexadecimal code points and ranges ("0041-005A 00DF")."""
    codes = set()
    for part in text.split():
        low, _, high = part.partition("-")
        codes.update(range(int(low, 16), int(high or low, 16) + 1))
    return codes


def ranges_of(codes):
    """Code points as hexadecimal ranges, as checks/font_characters.json writes them."""
    parts, codes = [], sorted(codes)
    at = 0
    while at < len(codes):
        end = at
        while end + 1 < len(codes) and codes[end + 1] == codes[end] + 1:
            end += 1
        parts.append("%04X" % codes[at] if end == at else "%04X-%04X" % (codes[at], codes[end]))
        at = end + 1
    return " ".join(parts)


# ---------------------------------------------------------------------------
# What the lists show
# ---------------------------------------------------------------------------

def specific_script(text):
    """The script most of a text's own characters are in (None for punctuation alone)."""
    found = collections.Counter(ucd.script(c) for c in text)
    for script, _ in found.most_common():
        if script not in NOT_A_SCRIPT:
            return script
    return None


def shown_texts():
    """What the lists and tooltips show, from the data files: the rows' labels (names, autonyms, and
    the script, group, family, set, and source headings: [(text, writing)], the writing a row's script
    heading), the other names a tooltip shows, and the orthographies' lists ([(text, items, writing)]:
    each item a character or a letter and its marks, a mark alone on a dotted circle)."""
    labels, others, lists = [], [], []
    for path in LANGUAGES_FILES:
        data = load(path)
        for row in data["orthographies"]:
            name, autonym, script, base, auxiliary, marks = row[1], row[2], row[3], row[7], row[8], row[9]
            labels += [(name, script), (autonym, script), (script, script)]
            for text in (data["texts"][base], data["texts"][auxiliary]):
                lists.append((text, text.split(), script))
            lists.append((marks, [u"\N{DOTTED CIRCLE}" + m for m in marks if m != u" "], script))
        labels += [(row[1], None) for row in data.get("sources", ())]
    families = load(FAMILIES_FILE)
    labels += [(name, None) for name, _ in families["nodes"]]
    for found in families["aliases"].values():
        others += found
    sets = load(SETS_FILE)
    labels += [(group, None) for group in sets["groups"]] + [(row[1], None) for row in sets["sets"]]
    return labels, others, lists


def list_characters(labels, others, lists):
    """{code point: Counter of scripts} for every character of the texts, each common or inherited
    character voting for the script of the text it is in (its marks shaped by that script's font), and
    {ideograph: Counter of CJK fonts} from the writing of its rows (HANI_FONT)."""
    votes, ideographs = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)

    def vote(text, writing):
        owner = specific_script(text) or "Latn"
        for character in text:
            own = ucd.script(character)
            votes[ord(character)][owner if own in NOT_A_SCRIPT else own] += 1
            if own == "Hani" and writing in HANI_FONT:
                ideographs[ord(character)][HANI_FONT[writing]] += 1

    for text, _, writing in lists:
        vote(text.replace(u" ", u""), writing)
    for text, writing in labels:
        vote(text, writing)
    for text in others + [UI_TEXT]:
        vote(text, None)
    return dict(votes), dict(ideographs)


def required_characters():
    """{part: its code points} of checks/font_characters.json, and every one of them."""
    data = load(CHARACTERS_FILE)
    parts = collections.OrderedDict((part, codes_of(data[part])) for part in PARTS)
    return parts, set().union(*parts.values())


# ---------------------------------------------------------------------------
# The Noto fonts
# ---------------------------------------------------------------------------

def license_of(font, records=(13, 14)):
    """"OFL" when the font's name table declares the SIL Open Font License (as kerning/train/dataset.py
    reads it) in its license records (or the records given), else None."""
    text = " ".join(str(r) for r in font["name"].names if r.nameID in records).lower()
    if any(marker in text for marker in PROPRIETARY):
        return None
    return "OFL" if any(marker in text for marker in OPEN_FONT_LICENSE) else None


def fetch(repo, relative, folder):
    """A file of a repository at its pinned commit, downloaded once into folder."""
    name, commit = repo
    path = os.path.join(folder, name.replace("/", "_") + "-" + commit[:12], *relative.split("/"))
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = RAW_URL % (name, commit, relative.replace("[", "%5B").replace("]", "%5D"))
        say("downloading %s" % url)
        with urllib.request.urlopen(url, timeout=300) as response:
            data = response.read()
        with open(path + ".part", "wb") as handle:
            handle.write(data)
        os.replace(path + ".part", path)
    return path


def release_path(url, folder):
    """Where a release's file is kept in folder: under its host and path."""
    parts = urllib.parse.urlsplit(url)
    return os.path.join(folder, parts.netloc, *parts.path.strip("/").split("/"))


def fetch_release(url, member, folder):
    """A release's file at its URL, downloaded once into folder, or a member of that archive (.zip,
    .tar.gz), taken out once beside it."""
    path = release_path(url, folder)
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        say("downloading %s" % url)
        with urllib.request.urlopen(url, timeout=600) as response:
            data = response.read()
        with open(path + ".part", "wb") as handle:
            handle.write(data)
        os.replace(path + ".part", path)
    if member is None:
        return path
    out = os.path.join(path + ".files", *member.split("/"))
    if not os.path.isfile(out):
        if path.endswith(".zip"):
            with zipfile.ZipFile(path) as archive:
                data = archive.read(member)
        else:
            with tarfile.open(path) as archive:
                data = archive.extractfile(member).read()
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out + ".part", "wb") as handle:
            handle.write(data)
        os.replace(out + ".part", out)
    return out


def reserved_names(text):
    """The Reserved Font Names an OFL notice declares ("with Reserved Font Name 'Source'", "with
    Reserved Font Names "Andika" and "SIL"")."""
    found = []
    for line in text.splitlines():
        lower = line.lower()
        if "reserved font name" in lower and "with reserved font name" in lower:
            tail = line[lower.index("with reserved font name") + len("with reserved font name"):]
            if tail[:1] in ("s", "S"):
                tail = tail[1:]
            for part in tail.replace(" and ", ",").split(","):
                part = part.strip().strip(".").strip().strip("'\"\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}")
                if part:
                    found.append(part)
    return found


def checked_license(path, notice=False):
    """A source's license file: the SIL Open Font License 1.1 (or, for a font of LICENSE_NOTICE, a
    notice that names the license; its version is then read from the font), reserving no name used."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read().replace("\r\n", "\n")
    if "SIL OPEN FONT LICENSE" not in text.upper() or not (notice or "Version 1.1" in text):
        raise SystemExit("%s is not the SIL Open Font License 1.1" % path)
    for name in reserved_names(text):
        if name.lower() in NAMES_USED.lower():
            raise SystemExit("%s reserves %r, which %s would use" % (path, name, FAMILY))
    return text


def source_url(family):
    """Where a source font is, at its repository's pinned commit or in its pinned release (a member of
    an archive after "#")."""
    if family in RELEASES:
        url, member = RELEASES[family][0]
        return url + ("#" + member if member else "")
    if family in CJK:
        return "https://github.com/%s/blob/%s/" % GOOGLE + "ofl/%s/%s" % CJK[family]
    return "https://github.com/%s/blob/%s/" % NOTO + "fonts/%s/unhinted/ttf/%s-Regular.ttf" % (family, family)


def source_font(family, folder):
    """(path, TTFont, license path) of a source font, its license checked."""
    if family in RELEASES:
        (url, member), (license_url, license_member) = RELEASES[family]
        path = fetch_release(url, member, folder)
        license_path = fetch_release(license_url, license_member, folder)
    elif family in CJK:
        directory, name = CJK[family]
        path = fetch(GOOGLE, "ofl/%s/%s" % (directory, name), folder)
        license_path = fetch(GOOGLE, "ofl/%s/OFL.txt" % directory, folder)
    else:
        path = fetch(NOTO, "fonts/%s/unhinted/ttf/%s-Regular.ttf" % (family, family), folder)
        license_path = fetch(NOTO, "fonts/LICENSE", folder)
    notice = family in LICENSE_NOTICE
    text = checked_license(license_path, notice)
    font = TTFont(path, lazy=True)
    if notice:  # (no license record: the copyright record names the license and its version)
        if license_of(font, (0,)) != "OFL" or "open font license 1.1" not in str(font["name"].getDebugName(0)).lower():
            raise SystemExit("%s does not declare the SIL Open Font License 1.1 in its copyright record" % path)
    elif family in LICENSE_BESIDE:  # (nothing declared in the font: the file beside it is its license)
        if license_of(font, (0, 13, 14)) is not None or any(marker in str(font["name"]).lower() for marker in PROPRIETARY):
            raise SystemExit("%s declares a license of its own: read it, and take it out of LICENSE_BESIDE" % path)
        if not copyright_of(family, font, text):
            raise SystemExit("%s does not open with a copyright line" % license_path)
    elif license_of(font) != "OFL":
        raise SystemExit("%s does not declare the SIL Open Font License in its name table" % path)
    for name in reserved_names(str(font["name"].getDebugName(0) or "")):
        if name.lower() in NAMES_USED.lower():
            raise SystemExit("%s reserves %r, which %s would use" % (path, name, FAMILY))
    for table in ("COLR", "CFF2", "CFF ", "EBDT", "EBLC", "CBDT", "sbix"):  # (no color, no curves to convert, no bitmap)
        if table in font and not (table == "CFF " and family in CUBIC) and not (table == "COLR" and family in ONE_COLOR):
            raise SystemExit("%s has a %s table: the list font is plain TrueType" % (path, table))
    return path, font, license_path


def copyright_of(family, font, license_text=None):
    """A source's copyright line: its name table's copyright record on one line (Unicodia Funky's is
    two), or, for a font that declares nothing (LICENSE_BESIDE), the first line of its license file."""
    if family in LICENSE_BESIDE:
        first = (license_text or "").lstrip(chr(0xFEFF)).strip().splitlines()[:1]
        return first[0].strip() if first and first[0].lower().startswith("copyright") else ""
    return " ".join(str(font["name"].getDebugName(0) or "").split())


def archives_of(families, folder):
    """{URL: SHA-256} of the release archives the families' fonts and licenses were taken out of."""
    found = collections.OrderedDict()
    for family in families:
        for url, member in RELEASES.get(family, ()):
            if member is not None and url not in found:
                found[url] = sha256(release_path(url, folder))
    return found


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def recorded_pins():
    """{source file or release archive: SHA-256} as language_font.json recorded them at the last build."""
    path = os.path.join(OUT_DIR, INFO_FILE)
    if not os.path.isfile(path):
        return {}
    info = load(path)
    pins = dict((source["file"], source["sha256"]) for source in info.get("fonts", ()))
    pins.update(info.get("archives", {}))
    return pins


# ---------------------------------------------------------------------------
# Building the font
# ---------------------------------------------------------------------------

def candidates(code, votes, ideographs):
    """The fonts to look in for a character: its scripts' (most voted first; its own script when no
    text has it; then its script extensions'), then the general ones, then every other one, then
    EXTRA's."""
    scripts = [s for s, _ in sorted(votes.get(code, {}).items(), key=lambda kv: (-kv[1], kv[0]))]
    own = ucd.script(chr(code))
    if own not in NOT_A_SCRIPT and own not in scripts:
        scripts.append(own)
    scripts += sorted(ucd.script_extension(chr(code)) - set(scripts))
    # (a character of a script added later comes from that script's font: no earlier font was that
    # script's, so no earlier build's choice changes, and Grantha's signs are not taken from Tamil's font)
    found = [ADDED[own]] if own in ADDED else []
    for script in scripts:
        static = STATIC.get(script, ())
        cjk = CJK_ORDER.get(script, ())
        if script == "Hani":
            rows = ideographs.get(code, {})
            cjk = tuple(sorted(cjk, key=lambda family: -rows.get(family, 0)))  # (stable: CJK_ORDER among equals)
        for family in ((static,) if isinstance(static, str) else static) + cjk:
            if family not in found:
                found.append(family)
    found += [f for f in GENERAL if f not in found]
    others = sorted(set(f for static in STATIC.values() for f in ((static,) if isinstance(static, str) else static)),
                    key=lambda family: (family in RELEASES, family))  # (Noto's first: a script's own font from elsewhere last)
    found += [f for f in others + list(LAST) if f not in found]
    # The fonts added later (ADDED), after every font above: the character's scripts' own, then Noto's
    # notation fonts, then any other Noto font among them. A font from elsewhere is looked in for its
    # own script alone (Kedebideri has Latin letters too, and Unicodia Funky most of what Noto lacks).
    added = [ADDED[script] for script in scripts if script in ADDED]
    added += list(ADDED_LAST) + sorted(set(f for f in ADDED.values() if f not in RELEASES))
    for family in added + list(EXTRA) + list(LAST_RESORT):
        if family not in found:
            found.append(family)
    return found


def plan(wanted, votes, ideographs, folder):
    """{Noto family: [code points it supplies]} (FIRST first), the characters no source has, and the
    sources opened."""
    by_family, unplaced, opened, cmaps = collections.OrderedDict(((FIRST, []),)), [], {}, {}

    def cmap_of(family):
        if family not in opened:
            try:
                opened[family] = source_font(family, folder)
                cmaps[family] = set(opened[family][1].getBestCmap())
            except urllib.error.HTTPError as exc:
                if exc.code != 404:  # (a server's passing error: a build without the source would differ)
                    raise SystemExit("cannot fetch %s (HTTP %d): run the build again" % (family, exc.code))
                say("cannot use %s: not at the pinned commit (%s)" % (family, exc))  # (the same at every build)
                opened[family], cmaps[family] = None, set()
            except (OSError, ValueError, urllib.error.URLError) as exc:
                # (a timeout, a broken connection, a file cut short: never a smaller font written as if whole)
                raise SystemExit("cannot use %s: %s; run the build again" % (family, exc))
        return cmaps[family]

    for code in wanted:
        for family in candidates(code, votes, ideographs):
            if code in cmap_of(family):
                # (who supplies a character is settled here, before any font is thought of: a source's
                # part that goes elsewhere, see ELSEWHERE, is a second subset of the same source)
                by_family.setdefault(part_key(family, code), []).append(code)
                break
        else:
            unplaced.append(code)
    # (each subset with its font: a source's second subset has its source's file and license)
    return by_family, unplaced, dict((key, opened[base_family(key)]) for key in by_family)


def part_key(family, code):
    """The subset a source's character goes into: the source's own, or, for a character ELSEWHERE
    names, its second subset ("<source>@<label of the other font>")."""
    label, listed = ELSEWHERE.get(family, (None, ""))
    return family + PART + label if code in codes_of(listed) else family


def base_family(family):
    """The source a subset is cut from: a second subset (ELSEWHERE) is its source's."""
    return family.partition(PART)[0]


def cmap_only(family):
    """Whether a subset keeps its character map alone: one of a font of CMAP_ONLY, or of a source no
    language's text draws from (SET_ONLY)."""
    return base_family(family) in CMAP_ONLY or family in SET_ONLY or family in NAME_SUBSETS


def name_subsets(by_family, opened):
    """Adds to the plan each font's copy of its family name's characters (NAME_SUBSETS), a second
    subset of FIRST; a name with a character FIRST does not supply stops the build."""
    home = group_of(FIRST)
    for font in FONTS:
        if font.label == home:
            continue
        codes = sorted(set(ord(c) for c in font.family))
        lacking = [code for code in codes if code not in by_family[FIRST]]
        if lacking:
            raise SystemExit("%s: its family name has %s, which %s does not supply" % (font.file, ranges_of(lacking), FIRST))
        key = FIRST + PART + font.label
        by_family[key], opened[key] = codes, opened[FIRST]
        NAME_SUBSETS.add(key)


def recommended_source(family):
    """Whether a source is the Essential font's by its rule: the first font, the fonts STATIC gives
    the Recommended Scripts, and Andika, whose Latin and Cyrillic letters take Noto Sans's marks
    (ANCHORED). (A source a font of FONTS names is that font's before any rule: Noto Serif Tibetan.)"""
    essential = set((FIRST, "NotoSerif", "Andika"))
    for script in RECOMMENDED:
        static = STATIC.get(script, ())
        essential.update((static,) if isinstance(static, str) else static)
    return family in essential


# The rules a font of FONTS may name as its sources: each says whether a source no font names is its.
RULES = collections.OrderedDict((
    ("cjk", lambda family: family in CJK and family != "NotoEmoji"),  # the three fonts of Chinese, Japanese, and Korean
    ("recommended", recommended_source),
    ("rest", lambda family: True),  # (the last font with a rule in FONTS: every other source)
))


def font_of(label):
    """The entry of FONTS with a label."""
    found = [font for font in FONTS if font.label == label]
    if not found:
        raise SystemExit("no font of FONTS is labeled %r" % label)
    return found[0]


def group_of(family):
    """The label of the font of FONTS a subset goes into: the one ELSEWHERE names for a source's
    second subset; else the font that names its source; else the first font, in the table's order,
    whose rule (RULES) takes it."""
    if PART in family:
        return font_of(family.partition(PART)[2]).label
    for font in FONTS:
        if not isinstance(font.sources, str) and family in font.sources:
            return font.label
    for font in FONTS:
        if isinstance(font.sources, str) and RULES[font.sources](family):
            return font.label
    raise SystemExit("no font of FONTS takes %s: give one the rule \"rest\"" % family)


def own_layout(family):
    """Whether a source keeps its layout whole by FONTS (a font that is its named sources' own)."""
    return any(font.own_layout and not isinstance(font.sources, str) and family in font.sources for font in FONTS)


def sources_rule(font):
    """How language_font.json says which sources a font of FONTS holds."""
    if not isinstance(font.sources, str):
        return "named: " + ", ".join(font.sources)
    return {"cjk": "the fonts of Chinese, Japanese, and Korean",
            "recommended": "the first font, the fonts of Unicode's Recommended Scripts, and Andika, but those another font names",
            "rest": "every other source"}[font.sources]


def lookup_bytes(font):
    """{"GSUB": bytes, "GPOS": bytes}: what a font's lookup lists need within reach of 16-bit offsets
    when laid out the plainest way that always packs (see MAX_LOOKUP_BYTES): the count and the
    lookups' offsets, then each lookup (its type, flag, subtable count and offsets, and its mark
    filtering set where it has one) followed by one extension record of eight bytes per subtable.
    Merged tables need the sum of their sources' (less the two bytes of each count but one)."""
    found = collections.OrderedDict()
    for tag in ("GSUB", "GPOS"):
        size = 0
        if tag in font and font[tag].table.LookupList is not None and font[tag].table.LookupList.Lookup:
            size = 2
            for lookup in font[tag].table.LookupList.Lookup:
                size += 2 + 6 + (2 if lookup.LookupFlag & 0x10 else 0) + (2 + 8) * len(lookup.SubTable)
        found[tag] = size
    return found


def merged_lookup_bytes(rows):
    """{"GSUB": bytes, "GPOS": bytes} of a font merged from sources (their rows of language_font.json)."""
    found = collections.OrderedDict()
    for tag in ("GSUB", "GPOS"):
        sizes = [row["lookup_bytes"][tag] for row in rows if row["lookup_bytes"][tag]]
        found[tag] = sum(sizes) - 2 * (len(sizes) - 1) if sizes else 0
    return found


def check_limits(font, rows):
    """Stops the build when a font of FONTS would pass a limit (MAX_GLYPHS, MAX_LOOKUP_BYTES), with a
    sentence that names the font and its heaviest sources: fontTools would otherwise work for minutes
    on a table that cannot be packed, and stop without one. Returns the font's glyphs, its lookup
    bytes, and the warnings to say and record (a limit reached to WARN_AT or more)."""
    glyphs, lookups = sum(row["glyphs"] for row in rows), merged_lookup_bytes(rows)
    heaviest_glyphs = sorted(rows, key=lambda row: -row["glyphs"])[:3]
    warnings = []
    remedy = "move one to a font of its own (an entry of FONTS that names it)"
    if glyphs > MAX_GLYPHS:
        raise SystemExit("%s would hold %d glyphs, and a font holds %d at most. Its heaviest sources: %s. Not built: %s." % (
            font.file, glyphs, MAX_GLYPHS, ", ".join("%s (%d glyphs)" % (row["family"], row["glyphs"]) for row in heaviest_glyphs), remedy))
    if glyphs >= WARN_AT * MAX_GLYPHS:
        warnings.append("%s holds %d glyphs, %d%% of the %d a font holds. Its heaviest sources: %s." % (
            font.file, glyphs, 100 * glyphs // MAX_GLYPHS, MAX_GLYPHS,
            ", ".join("%s (%d glyphs)" % (row["family"], row["glyphs"]) for row in heaviest_glyphs)))
    for tag, size in lookups.items():
        heaviest = ", ".join("%s (%d bytes)" % (row["family"], row["lookup_bytes"][tag])
                             for row in sorted(rows, key=lambda row: -row["lookup_bytes"][tag])[:3] if row["lookup_bytes"][tag])
        if size > MAX_LOOKUP_BYTES:
            raise SystemExit("%s would need %d bytes for its %s lookups, and a table reaches %d. Its heaviest sources: %s. "
                             "Not built: %s." % (font.file, size, tag, MAX_LOOKUP_BYTES, heaviest, remedy))
        if size >= WARN_AT * MAX_LOOKUP_BYTES:
            warnings.append("%s needs %d bytes for its %s lookups, %d%% of the %d a table reaches. Its heaviest sources: %s." % (
                font.file, size, tag, 100 * size // MAX_LOOKUP_BYTES, MAX_LOOKUP_BYTES, heaviest))
    return glyphs, lookups, warnings


def layout_kept(font, family):
    """The layout features a source keeps (see CMAP_ONLY), and how language_font.json says it."""
    if cmap_only(family):
        return [], "none (character map only)"
    tags = set()
    for table in ("GSUB", "GPOS"):
        if table in font and font[table].table.FeatureList is not None:
            tags.update(record.FeatureTag for record in font[table].table.FeatureList.FeatureRecord)
    return sorted(tags - set(VERTICAL)), "every feature but the vertical ones"


# ---------------------------------------------------------------------------
# Marks across sources
# ---------------------------------------------------------------------------

ATTACHMENTS = {4: ("MarkCoverage", "MarkArray", "BaseCoverage", "BaseArray", "BaseRecord", "BaseAnchor"),
               6: ("Mark1Coverage", "Mark1Array", "Mark2Coverage", "Mark2Array", "Mark2Record", "Mark2Anchor")}


def attachment_subtables(font):
    """[(lookup, subtable, type)] of a font's mark-to-base (4) and mark-to-mark (6) positioning."""
    found = []
    if "GPOS" not in font or font["GPOS"].table.LookupList is None:
        return found
    for lookup in font["GPOS"].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            if sub.LookupType == 9:
                sub = sub.ExtSubTable
            if sub.LookupType in ATTACHMENTS:
                found.append((lookup, sub, sub.LookupType))
    return found


def attachment_parts(sub, kind):
    """A subtable's marks {glyph: (class, (x, y))} and bases {glyph: {class: (x, y)}}."""
    marks_at, array, bases_at, base_array, record, anchor = ATTACHMENTS[kind]
    marks = dict((glyph, (r.Class, (r.MarkAnchor.XCoordinate, r.MarkAnchor.YCoordinate)))
                 for glyph, r in zip(getattr(sub, marks_at).glyphs, getattr(sub, array).MarkRecord))
    bases = {}
    for glyph, r in zip(getattr(sub, bases_at).glyphs, getattr(getattr(sub, base_array), record)):
        bases[glyph] = dict((cls, (a.XCoordinate, a.YCoordinate)) for cls, a in enumerate(getattr(r, anchor)) if a is not None)
    return marks, bases


def mark_classes(font, marks, scale=1.0):
    """{class: {character: (anchor x, anchor y, ink's middle x, ink's bottom, ink's top)}} of a
    subtable's marks: a class is known by its marks' characters (the acute's class is the marks
    above), which is how it is found again in another font, and where a mark's anchor lies from its
    ink says how that font places the class (see convention_shift)."""
    from fontTools.pens.boundsPen import BoundsPen
    characters = collections.defaultdict(set)
    for code, name in font.getBestCmap().items():
        characters[name].add(code)
    glyph_set, classes = font.getGlyphSet(), collections.defaultdict(dict)
    for glyph, (cls, (x, y)) in sorted(marks.items()):
        if glyph not in characters:
            continue
        pen = BoundsPen(glyph_set)
        glyph_set[glyph].draw(pen)
        if pen.bounds is None:
            continue
        left, bottom, right, top = pen.bounds
        for code in characters[glyph]:
            classes[cls][code] = tuple(v * scale for v in (x, y, (left + right) / 2.0, bottom, top))
    return classes


def convention_shift(theirs, ours):
    """What to add to an anchor of one font's class for it to mean the same in another font's: the
    two fonts put a mark's anchor at different places from its ink (Andika's marks below hang from
    0.049 em under the baseline, Noto Sans's from the baseline), so an anchor carried as it is would
    set every mark off by that much. Measured on the marks both classes have (the middle one of the
    differences, on each axis): an anchor's place from the ink's middle across, and from the ink's
    edge nearest the letter up and down."""
    def place(mark, both):
        x, y, middle, bottom, top = mark
        side = "above" if y <= bottom else "below" if y >= top else "inside"
        if both is None:
            return side
        return x - middle, y - (bottom if both == "above" else top if both == "below" else (bottom + top) / 2.0)

    across, up = [], []
    for code in sorted(set(theirs) & set(ours)):
        side = place(theirs[code], None)
        side = side if side == place(ours[code], None) else "inside"
        (their_x, their_y), (our_x, our_y) = place(theirs[code], side), place(ours[code], side)
        across.append(our_x - their_x)
        up.append(our_y - their_y)
    return sorted(across)[len(across) // 2], sorted(up)[len(up) // 2]


def source_anchors(font, codes):
    """What a source font's own positioning says of codes, in UNITS_PER_EM: [(code, "mark" or "base",
    type, that class's marks (mark_classes), (x, y))]."""
    cmap, scale = font.getBestCmap(), float(UNITS_PER_EM) / font["head"].unitsPerEm
    found = []
    for _, sub, kind in attachment_subtables(font):
        marks, bases = attachment_parts(sub, kind)
        classes = mark_classes(font, marks, scale)
        for code in codes:
            name = cmap.get(code)
            if name in marks:
                cls, (x, y) = marks[name]
                found.append((code, "mark", kind, classes[cls], (x * scale, y * scale)))
            for cls, (x, y) in sorted(bases.get(name, {}).items()):
                found.append((code, "base", kind, classes[cls], (x * scale, y * scale)))
    return found


def meets_host(code):
    """Whether a guest's character is one whose anchors are carried into the host's lookups: a letter
    or a mark of the host's scripts (Latin, Greek, Cyrillic), or a mark of no script in particular.
    A letter or a mark of another script (Unicodia Funky's Garay, Gurung Khema, Ol Onal, and Sidetic,
    or its Sharada vowel signs) is none of Noto Sans's business, and a symbol is no base of a mark."""
    character = chr(code)
    if not ucd.category(character).startswith(("L", "M")):
        return False
    own, extensions = ucd.script(character), ucd.script_extension(character)
    if own in NOT_A_SCRIPT:
        return extensions <= set(NOT_A_SCRIPT) or bool(extensions & set(HOST_SCRIPTS))
    return own in HOST_SCRIPTS


def carry_anchors(merged, host_glyphs, guests):
    """Adds the guests' letters and marks ({family: source_anchors' list}) to the host's mark-to-base
    and mark-to-mark lookups in the merged font (the host: FIRST, whose glyphs are host_glyphs), each
    with its own source's anchor: a guest's letter becomes a base of the host's class of marks its
    source attaches there, and a guest's mark joins the host's class its source puts it in, the
    anchor moved by what the two fonts' conventions differ (convention_shift). Classes are matched by
    the marks' characters, and only where most of them agree (a class one font splits otherwise is
    left alone). Returns {family: {"marks": characters, "bases": characters}}, as ranges."""
    from fontTools.misc.roundTools import otRound
    from fontTools.ttLib.tables import otTables as ot
    cmap = merged.getBestCmap()
    hosts = []  # [(lookup, subtable, type, {class: its marks (mark_classes)})] of the host's own subtables
    for lookup, sub, kind in attachment_subtables(merged):
        marks, _ = attachment_parts(sub, kind)
        if not marks or not set(marks) <= host_glyphs:
            continue
        hosts.append((lookup, sub, kind, mark_classes(merged, marks)))
    host_marks = dict((kind, set(code for _, _, k, classes in hosts if k == kind for ours in classes.values() for code in ours))
                      for kind in ATTACHMENTS)

    def agree(theirs, ours, kind):
        """How many marks two classes share, when that is most of what both fonts have of either."""
        shared = len(set(theirs) & set(ours))
        return shared if shared and 2 * shared > len(set(theirs) & host_marks[kind]) else 0

    def anchor_of(point):
        anchor = ot.Anchor()
        anchor.Format, anchor.XCoordinate, anchor.YCoordinate = 1, point[0], point[1]
        return anchor

    def moved(point, theirs, ours):
        across, up = convention_shift(theirs, ours)
        return otRound(point[0] + across), otRound(point[1] + up)

    gdef = merged["GDEF"].table
    done = collections.OrderedDict()
    added = collections.defaultdict(lambda: (dict(), dict()))  # {subtable index: (marks, bases) to add}
    for family, found in guests.items():
        done[family] = {"marks": set(), "bases": set()}
        for code, role, kind, theirs, point in found:
            glyph = cmap.get(code)
            if glyph is None or glyph in host_glyphs:
                continue
            # (the most marks shared first, then the earliest subtable: -at sorts it last, to be taken first)
            best = [(agree(theirs, ours, kind), -at, cls) for at, (_, _, k, classes) in enumerate(hosts) if k == kind
                    for cls, ours in sorted(classes.items())]
            best = sorted(b for b in best if b[0])
            if role == "mark" and best:  # (one class: where most of its source's class is)
                _, at, cls = best[-1]
                if glyph not in added[-at][0]:
                    added[-at][0][glyph] = (cls, moved(point, theirs, hosts[-at][3][cls]))
                    done[family]["marks"].add(code)
            elif role == "base":  # (every class of the host's that its source's class answers to)
                for _, at, cls in best:
                    added[-at][1].setdefault(glyph, {}).setdefault(cls, moved(point, theirs, hosts[-at][3][cls]))
                    done[family]["bases"].add(code)
    for at, (new_marks, new_bases) in sorted(added.items()):
        lookup, sub, kind, _ = hosts[at]
        marks_at, array, bases_at, base_array, record, anchor = ATTACHMENTS[kind]
        rows = list(zip(getattr(sub, marks_at).glyphs, getattr(sub, array).MarkRecord))
        for glyph, (cls, point) in sorted(new_marks.items()):
            row = ot.MarkRecord()
            row.Class, row.MarkAnchor = cls, anchor_of(point)
            rows.append((glyph, row))
        rows.sort(key=lambda pair: merged.getGlyphID(pair[0]))  # (a coverage table is in glyph order)
        getattr(sub, marks_at).glyphs = [glyph for glyph, _ in rows]
        getattr(sub, array).MarkRecord = [row for _, row in rows]
        rows = list(zip(getattr(sub, bases_at).glyphs, getattr(getattr(sub, base_array), record)))
        for glyph, anchors in sorted(new_bases.items()):
            row = getattr(ot, record)()
            setattr(row, anchor, [anchor_of(anchors[cls]) if cls in anchors else None for cls in range(sub.ClassCount)])
            rows.append((glyph, row))
        rows.sort(key=lambda pair: merged.getGlyphID(pair[0]))
        getattr(sub, bases_at).glyphs = [glyph for glyph, _ in rows]
        setattr(getattr(sub, base_array), record, [row for _, row in rows])
        # A lookup that looks only at a set of marks (or at one attachment class) must see the new ones.
        seen = sorted(set(new_marks) | (set(new_bases) if kind == 6 else set()))
        if lookup.LookupFlag & 0x10 and seen:
            coverage = gdef.MarkGlyphSetsDef.Coverage[lookup.MarkFilteringSet]
            coverage.glyphs = sorted(set(coverage.glyphs) | set(seen), key=merged.getGlyphID)
        if lookup.LookupFlag >> 8 and seen:
            for glyph in seen:
                gdef.MarkAttachClassDef.classDefs.setdefault(glyph, lookup.LookupFlag >> 8)
    for at, (new_marks, new_bases) in added.items():
        for glyph in new_marks:
            gdef.GlyphClassDef.classDefs[glyph] = 3
        if hosts[at][2] == 4:
            for glyph in new_bases:
                gdef.GlyphClassDef.classDefs.setdefault(glyph, 1)
    return collections.OrderedDict((family, collections.OrderedDict(
        (role, ranges_of(codes)) for role, codes in sorted(parts.items()))) for family, parts in done.items())


def quadratic_outlines(font, tolerance=1.0):
    """A font's cubic outlines (CFF) as TrueType's quadratic ones, each curve within tolerance font
    units of the one drawn (fontTools' cu2qu, as its otf2ttf does it), the contours' direction turned
    as TrueType fills them; the font is then a TrueType font like the others (glyf, loca, maxp 1.0)."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable
    order, glyph_set = font.getGlyphOrder(), font.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphOrder, glyf.glyphs = order, {}
    for name in order:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, tolerance, reverse_direction=True))
        glyf[name] = pen.glyph()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf
    del font["CFF "]
    for name in order:  # (a left side bearing is its outline's left edge)
        glyph = glyf[name]
        glyph.recalcBounds(glyf)
        font["hmtx"][name] = (font["hmtx"][name][0], getattr(glyph, "xMin", 0) if glyph.numberOfContours else 0)
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    maxp.maxZones, maxp.maxTwilightPoints, maxp.maxStorage = 1, 0, 0
    maxp.maxFunctionDefs = maxp.maxInstructionDefs = maxp.maxStackElements = maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = max([len(g.components) for g in glyf.glyphs.values() if hasattr(g, "components")] or [0])
    maxp.maxPoints = maxp.maxContours = maxp.maxCompositePoints = maxp.maxCompositeContours = 0  # (recalculated at saving)
    maxp.maxComponentDepth = 0
    font["post"].formatType = 3.0
    font["post"].extraNames, font["post"].mapping = [], {}
    font.sfntVersion = "\x00\x01\x00\x00"


def subset_font(path, family, codes, out):
    """The font cut down to codes (their shaping kept, see layout_kept), unhinted, static (a variable
    font instanced at Regular, weight 400), and scaled to UNITS_PER_EM. Every source has TrueType
    outlines (source_font refuses the others) but those of CUBIC, whose curves are converted
    (quadratic_outlines): no other outline is. Returns how its layout was kept."""
    options = subset.Options()
    options.hinting = False
    options.notdef_outline = True
    options.glyph_names = False
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.drop_tables += ["DSIG", "STAT", "meta", "vhea", "vmtx", "gasp", "VORG", "BASE", "JSTF", "MATH"]
    if base_family(family) in CUBIC:  # (Daarage's old-style kerning and its tables for Apple's layout: nothing here reads them)
        options.drop_tables += ["kern", "lcar", "prop"]
    if base_family(family) in ONE_COLOR:
        options.drop_tables += ["COLR", "CPAL"]
    font = subset.load_font(path, options)
    options.layout_features, kept = layout_kept(font, family)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(codes))
    subsetter.subset(font)
    if "CFF " in font:
        quadratic_outlines(font)
    if "fvar" in font:
        from fontTools.varLib import instancer
        regular = dict((axis.axisTag, min(max(400, axis.minValue), axis.maxValue) if axis.axisTag == "wght"
                        else axis.defaultValue) for axis in font["fvar"].axes)  # (the CJK fonts' default is Thin)
        font = instancer.instantiateVariableFont(font, regular)
    font.save(out)
    if font["head"].unitsPerEm != UNITS_PER_EM:
        from fontTools.ttLib.scaleUpem import scale_upem
        font = TTFont(out)
        scale_upem(font, UNITS_PER_EM)
        font.save(out)
    return kept


def harfbuzz_version():
    """uharfbuzz's version, or None without it. fontTools packs a subset's layout tables through
    HarfBuzz when it is there, so the bytes of a build depend on it."""
    try:
        import uharfbuzz
    except ImportError:
        return None
    return str(uharfbuzz.__version__)


def subset_recipe(family, source_hash, codes):
    """What a kept subset was made from: the same recipe gives the same subset."""
    return collections.OrderedDict((
        ("recipe", RECIPE), ("family", family), ("source", source_hash),
        ("characters", hashlib.sha256(ranges_of(codes).encode("ascii")).hexdigest()),
        ("layout", "none" if cmap_only(family) else "all but " + " ".join(VERTICAL)),
        ("units_per_em", UNITS_PER_EM), ("fontTools", fontTools.version), ("uharfbuzz", harfbuzz_version())))


def ink_extent(font, texts):
    """The highest and lowest ink, in font units, of the texts shaped (uharfbuzz), or None."""
    try:
        import uharfbuzz as hb
    except ImportError:
        return None
    from fontTools.pens.boundsPen import BoundsPen
    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()
    with open(font.reader.file.name, "rb") as handle:
        hb_font = hb.Font(hb.Face(handle.read()))
    top, bottom, worst = 0, 0, {}
    bounds = {}
    for text in texts:
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(hb_font, buf, {})
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = order[info.codepoint]
            if name not in bounds:
                pen = BoundsPen(glyph_set)
                glyph_set[name].draw(pen)
                bounds[name] = pen.bounds
            if bounds[name] is None:
                continue
            high, low = bounds[name][3] + pos.y_offset, bounds[name][1] + pos.y_offset
            if high > top:
                top, worst["top"] = high, text
            if low < bottom:
                bottom, worst["bottom"] = low, text
    return top, bottom, worst


def set_names(font, copyrights, stamp, family, postscript_name):
    """Named as one of FreeLang's fonts, so it never stands for an installed Noto font."""
    name = font["name"]
    name.names = []
    records = {
        0: "; ".join(copyrights),
        1: gdi_family(family), 2: "Regular", 3: "%s;%s" % (VERSION, postscript_name), 4: family,
        5: "Version %s; subsets of Noto fonts and other open-licensed fonts" % VERSION,
        6: postscript_name,
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is "
            "available with a FAQ at: https://openfontlicense.org",
        14: "https://openfontlicense.org",
    }
    if gdi_family(family) != family:  # (the full name as the typographic family: GDI_FAMILIES)
        records[16], records[17] = family, "Regular"
    if any(ord(c) > 0x7E for c in postscript_name):
        raise SystemExit("%r: a PostScript name is ASCII" % postscript_name)
    try:  # (Macintosh records, in Mac Roman, which has the en dash of the fourth family's name: none at
        # all for a font one of whose records the encoding cannot hold, since half a set would name the
        # font without its family)
        macintosh = [text.encode("mac_roman") for text in records.values()] != []
    except UnicodeEncodeError:
        macintosh = False
    for name_id, text in sorted(records.items()):
        name.setName(text, name_id, 3, 1, 0x409)  # (Windows, UTF-16: what Qt and Windows read)
        if macintosh:
            name.setName(text, name_id, 1, 0, 0)
    font.recalcTimestamp = False  # (the same bytes from the same sources: dated as the latest source)
    font["head"].created = font["head"].modified = stamp
    font["head"].fontRevision = float(VERSION)
    font["head"].macStyle = 0
    font["OS/2"].achVendID = "NONE"
    font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0b1100001) | 0b1000000  # Regular only
    font["post"].formatType = 3.0  # no glyph names: smaller
    font["post"].extraNames, font["post"].mapping = [], {}


def set_coverage(font, scripts):
    """OS/2 Unicode ranges from the cmap, and the code pages of the scripts drawn (see CODE_PAGES)."""
    os2 = font["OS/2"]
    os2.recalcUnicodeRanges(font)
    bits = set()
    for script in scripts:
        bits.update(CODE_PAGES.get(script, ()))
    os2.ulCodePageRange1 = sum(1 << b for b in bits)
    os2.ulCodePageRange2 = 0


def set_line(font, top, bottom):
    """The line's metrics from the ink of what the list shows: nothing it draws is cut."""
    upm = font["head"].unitsPerEm
    ascent, descent = int(max(top, 0.9 * upm)), int(max(-bottom, 0.25 * upm))
    os2, hhea = font["OS/2"], font["hhea"]
    os2.usWinAscent, os2.usWinDescent = ascent, descent
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ascent, -descent, 0
    hhea.ascent, hhea.descent, hhea.lineGap = ascent, -descent, 0
    os2.fsSelection |= 1 << 7  # Use Typo Metrics: the same line everywhere
    return ascent, descent


def shaping_differences(sources, merged_path, runs):
    """The runs the merged font shapes otherwise than their source font (uharfbuzz), or None without it."""
    try:
        import uharfbuzz as hb
    except ImportError:
        return None
    faces = {}

    def font_of(path):
        if path not in faces:
            with open(path, "rb") as handle:
                faces[path] = hb.Font(hb.Face(handle.read()))
        return faces[path]

    def shape(path, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font_of(path), buf, {})
        return [(p.x_advance, p.x_offset, p.y_offset) for p in buf.glyph_positions], \
            [i.cluster for i in buf.glyph_infos], [i.codepoint == 0 for i in buf.glyph_infos]

    return [(family, text) for family, text in runs if shape(sources[family], text) != shape(merged_path, text)]


def notdef_texts(merged_path, texts):
    try:
        import uharfbuzz as hb
    except ImportError:
        return None
    with open(merged_path, "rb") as handle:
        font = hb.Font(hb.Face(handle.read()))
    bad = []
    for text in texts:
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        if any(i.codepoint == 0 for i in buf.glyph_infos):
            bad.append(text)
    return bad


def script_runs(text):
    """A text cut as Qt itemizes it: runs of one script, a common or inherited character (punctuation,
    a mark, a dotted circle) joining the run around it; spaces left out."""
    runs, current, script, pending = [], u"", None, u""
    for character in text:
        own = ucd.script(character)
        if character == u" ":
            if current:
                runs.append(current)
            current, script, pending = u"", None, u""
        elif own in NOT_A_SCRIPT:
            if script is None:
                pending += character
            else:
                current += character
        elif script is None or own == script:
            current, script, pending = (current or pending) + character, own, u""
        else:
            runs.append(current)
            current, script = character, own
    if current or pending:
        runs.append(current or pending)
    return runs


def blocks_of(codes):
    """{Unicode block: how many of the code points}, in code point order."""
    found = collections.OrderedDict()
    for code in sorted(codes):
        block = ucd.block(chr(code))
        found[block] = found.get(block, 0) + 1
    return found


def cmap_formats(font):
    return sorted(set(table.format for table in font["cmap"].tables))


def build(args):
    parts, required = required_characters()
    labels, others, lists = shown_texts()
    votes, ideographs = list_characters(labels, others, lists)
    wanted = sorted(required | set(votes))
    say("%d characters to draw (%s; %d more in the data files' texts)" % (
        len(required), ", ".join("%s %d" % (part, len(codes)) for part, codes in parts.items()),
        len(wanted) - len(required)))
    if args.dry_run:
        print(collections.Counter(ucd.script(chr(c)) for c in wanted).most_common())
        return 0
    os.makedirs(args.cache, exist_ok=True)
    by_family, unplaced, opened = plan(wanted, votes, ideographs, args.cache)
    for family in [f for f, codes in by_family.items() if not codes]:
        del by_family[family]
    in_text = set(votes).union(*[parts[part] for part in PARTS if part != "sets"])
    SET_ONLY.update(f for f, codes in by_family.items()
                    if base_family(f) not in CMAP_ONLY and not in_text.intersection(codes) and not own_layout(f))
    for family in by_family:
        group_of(family)  # (stops here when no font of FONTS takes a source)
    name_subsets(by_family, opened)  # (after who supplies what is settled: these are copies)
    pins, hashes = recorded_pins(), {}
    for family in by_family:
        hashes[family] = sha256(opened[family][0])
        address = source_url(base_family(family))
        if address not in pins and not args.repin:  # (a source no build recorded: its bytes are taken on --repin alone)
            raise SystemExit("%s is a source %s has no record of (SHA-256 %s): --repin records it" % (
                opened[family][0], INFO_FILE, hashes[family]))
        if pins.get(address, hashes[family]) != hashes[family] and not args.repin:
            raise SystemExit("%s is not the file %s recorded (SHA-256 %s, recorded %s): --repin accepts it" % (
                opened[family][0], INFO_FILE, hashes[family], pins[address]))
    archives = archives_of([base_family(family) for family in by_family], args.cache)
    for url, found in archives.items():
        if url not in pins and not args.repin:
            raise SystemExit("%s is an archive %s has no record of (SHA-256 %s): --repin records it" % (
                url, INFO_FILE, found))
        if pins.get(url, found) != found and not args.repin:
            raise SystemExit("%s is not the archive %s recorded (SHA-256 %s, recorded %s): --repin accepts it" % (
                url, INFO_FILE, found, pins[url]))
    if args.stage == "plan":
        for family, codes in by_family.items():
            say("%s: %d characters (%s%s)" % (
                family, len(codes), group_of(family),
                ", its family name's characters, copied" if family in NAME_SUBSETS
                else ", character map only: no language's text" if family in SET_ONLY
                else ", its layout kept whole: the font is its own" if own_layout(family) else ""))
        say("no source has %d: %s" % (len(unplaced), ranges_of(unplaced)))
        return 0
    work = os.path.join(args.cache, "work")
    os.makedirs(work, exist_ok=True)
    started, waiting = time.time(), []
    subsets, copyrights, sources, licenses = [], [], [], []
    supplied = {}
    for family, codes in by_family.items():
        path, font, license_path = opened[family]
        supplied[family] = set(codes) | ({0x20} if not subsets else set())  # (each character once: no duplicates
        # to resolve, which fontTools does through locl features that reached other scripts' text)
        out = os.path.join(work, family + "-subset.ttf")
        subsets.append(out)
        recipe = subset_recipe(family, hashes[family], supplied[family])
        kept = layout_kept(font, family)[1]
        # (--fresh makes the subsets again, but at the merge stage, where it makes the merges again)
        fresh = (not args.fresh or args.stage == "merge") and os.path.isfile(out) and os.path.isfile(out + ".json") \
            and load(out + ".json") == recipe
        if not fresh:
            if args.stage == "merge" or (args.seconds and time.time() - started > args.seconds):
                waiting.append(family)
                continue
            if os.path.isfile(out + ".json"):
                os.remove(out + ".json")
            subset_font(path, family, supplied[family], out)
            write_text(out + ".json", json.dumps(recipe) + "\n")
        with open(license_path, encoding="utf-8") as handle:
            copyright = copyright_of(base_family(family), font, handle.read())
        if copyright and copyright not in copyrights:
            copyrights.append(copyright)
        if license_path not in licenses:
            licenses.append(license_path)
        made = TTFont(out)
        sources.append(collections.OrderedDict((
            ("family", LICENSE_BESIDE.get(base_family(family))
             or str(font["name"].getDebugName(16) or font["name"].getDebugName(1))),  # (not "Noto Sans JP Thin")
            ("font", group_of(family)),  # (which font of FONTS it is in; a source of ELSEWHERE has two rows)
            # ("own": the source's subset; "elsewhere": its second one, ELSEWHERE; "name": a font's copy
            # of its family name's characters, NAME_SUBSETS, which another row supplies)
            ("subset", "name" if family in NAME_SUBSETS else "elsewhere" if PART in family else "own"),
            ("file", source_url(base_family(family))),
            ("version", str(font["name"].getDebugName(5))),
            ("copyright", copyright),
            ("sha256", hashes[family]),
            ("layout", kept),
            ("scripts", sorted(set(ucd.script(chr(c)) for c in codes) - set(NOT_A_SCRIPT))),
            ("count", len(codes)),
            ("glyphs", made["maxp"].numGlyphs),
            ("lookup_bytes", lookup_bytes(made)),  # (what its lookups need of a table's reach: check_limits)
            ("bytes", os.path.getsize(out)),
            ("code_points", ranges_of(codes)),
        )))
        made.close()
        say("%s: %d characters, %d glyphs, %d bytes%s" % (
            family, len(codes), sources[-1]["glyphs"], sources[-1]["bytes"], " (kept)" if fresh else ""))
    if waiting:
        say("%d subsets still to make (%s): run --stage subsets again" % (len(waiting), ", ".join(waiting)))
        return 3
    if args.stage == "subsets":
        say("every subset is made: run --stage merge")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    line_texts = sorted(set(text for text, _ in labels if text))
    # (each run of one script shaped by itself, as Qt itemizes a row: a whole "Tibetan (autonym)" would
    # be shaped as Latin text, its stacks unformed and deeper than they are drawn)
    line_runs = sorted(set(run for text in line_texts for run in script_runs(text)))
    texts = sorted(set(line_texts) | set(others) | set(item for _, items, _ in lists for item in items) - set((u"",)))
    source_of = dict((c, f) for f, codes in by_family.items() if f not in NAME_SUBSETS for c in codes)
    runs = set()
    for text in texts:
        for run in script_runs(text):
            owners = [source_of.get(ord(c)) for c in run if ucd.script(c) not in NOT_A_SCRIPT] or [source_of.get(ord(run[0]))]
            family = owners[0]
            if family is not None and all(ord(c) in supplied[family] for c in run):
                runs.add((family, run))
    for family, samples in SAMPLES.items():  # (the sources that keep their layout with no language's text to shape)
        for sample in samples:
            text = u"".join(chr(int(code, 16)) for code in sample.split())
            if family in supplied and all(ord(c) in supplied[family] for c in text):
                runs.add((family, text))
    left_set = set(unplaced)
    # Each font of FONTS merged from its sources' subsets, named, and kept in the work folder with what
    # it was made from: a font at a time with --font (a merge whose lookups HarfBuzz does not pack at
    # once takes minutes, and each is then a command of its own), or every one not made yet.
    if args.font:
        font_of(args.font)
    limits = {}
    for spec in FONTS:  # (every font's limits before any is merged)
        rows = [source for source, f in zip(sources, by_family) if group_of(f) == spec.label]
        if not rows:
            raise SystemExit("%s has no source: take its entry out of FONTS" % spec.file)
        limits[spec.label] = check_limits(spec, rows)
        for warning in limits[spec.label][2]:
            say("warning: " + warning)
    made, waiting = [], []
    for spec in FONTS:
        members = [f for f in by_family if group_of(f) == spec.label]
        rows = [source for source, f in zip(sources, by_family) if f in members]
        glyphs, lookups, warnings = limits[spec.label]
        codes = set(c for f in members for c in supplied[f])
        # (the texts the line is measured on, which the subsets do not show: names may change while every
        # subset stays the same, and a kept font's extent is then measured again)
        runs_digest = hashlib.sha256("\n".join(sorted(run for run in line_runs if all(ord(c) in codes for c in run)))
                                     .encode("utf-8")).hexdigest()
        out = os.path.join(work, spec.file)
        recipe = merge_recipe(spec, [os.path.join(work, f + "-subset.ttf") for f in members])
        again = args.fresh and args.font in (None, spec.label)
        kept = not again and os.path.isfile(out) and os.path.isfile(out + ".json") and load(out + ".json")["recipe"] == recipe
        if not kept and args.font not in (None, spec.label):
            waiting.append(spec.label)
            continue
        if not kept:
            started = time.time()
            if os.path.isfile(out + ".json"):
                os.remove(out + ".json")
            merged = Merger().merge([os.path.join(work, f + "-subset.ttf") for f in members])
            carried = collections.OrderedDict()
            if FIRST in members:
                # (the merged font's first glyphs are FIRST's, under their own names: the host of the carried
                # anchors; a guest in another font is out of its reach)
                host_glyphs = set(merged.getGlyphOrder()[:rows[0]["glyphs"]])
                carried = carry_anchors(merged, host_glyphs, collections.OrderedDict(
                    (base_family(family), source_anchors(opened[family][1], [c for c in by_family[family] if meets_host(c)]))
                    for family in members if base_family(family) in ANCHORED))
                for family, roles in carried.items():
                    say("%s: anchors carried into %s's lookups for marks %s and bases %s" % (
                        family, FIRST, roles["marks"] or "(none)", roles["bases"] or "(none)"))
            own = []
            for row in rows:
                if row["copyright"] and row["copyright"] not in own:
                    own.append(row["copyright"])
            set_names(merged, own, max(opened[f][1]["head"].modified for f in members), spec.family, spec.postscript)
            set_coverage(merged, set(ucd.script(chr(c)) for c in codes))
            merged.save(out)
            del merged
            extent = ink_extent(TTFont(out), [run for run in line_runs if all(ord(c) in codes for c in run)])
            write_text(out + ".json", json.dumps(collections.OrderedDict((
                ("recipe", recipe), ("carried", carried), ("extent", extent), ("runs", runs_digest),
                ("seconds", round(time.time() - started, 1)))), ensure_ascii=False) + "\n")
        state = load(out + ".json")
        if state.get("runs") != runs_digest:  # (a kept font, but the names it draws changed: measured again, not merged)
            state["extent"] = ink_extent(TTFont(out), [run for run in line_runs if all(ord(c) in codes for c in run)])
            state["runs"] = runs_digest
            write_text(out + ".json", json.dumps(state, ensure_ascii=False) + "\n")
        say("%s: merged from %s%s" % (spec.file, "1 subset" if len(members) == 1 else "%d subsets" % len(members),
                                      " (kept)" if kept else " in %s s" % state["seconds"]))
        made.append((spec, members, rows, codes, state["carried"], state["extent"], lookups, warnings))
    if args.font:
        say("%s is merged; still to merge: %s. Then run --stage merge without --font." % (
            font_of(args.font).file, ", ".join(waiting) or "nothing"))
        return 0
    # The fonts written beside one another, on one line: the same ascent and descent in all of them.
    line, extents = None, [entry[5] for entry in made]
    measured = all(extent is not None for extent in extents)
    if measured:
        highest, lowest = max(extents, key=lambda e: e[0]), min(extents, key=lambda e: e[1])
    for spec, members, rows, codes, carried, extent, lookups, warnings in made:
        out = os.path.join(OUT_DIR, spec.file)
        font = TTFont(os.path.join(work, spec.file))
        font.recalcTimestamp = False
        if measured:
            line = set_line(font, highest[0], lowest[1])  # (the same in every font: a mixed row sits on one line)
        font.save(out + ".part")
        font.close()
        os.replace(out + ".part", out)
    if measured:
        say("line: ascent %d, descent %d (highest: %s; lowest: %s)" % (
            line[0], line[1], highest[2].get("top"), lowest[2].get("bottom")))
    for name in sorted(os.listdir(OUT_DIR)):  # (a font file of an earlier table, FreeLang-Extended.ttf: not left behind)
        if name.startswith(FAMILY + "-") and name.endswith(".ttf") and name not in [font.file for font in FONTS]:
            os.remove(os.path.join(OUT_DIR, name))
            say("removed %s, which no entry of FONTS names" % name)
    files, drawn, checked = [], set(), True
    for spec, members, rows, codes, carried, extent, lookups, warnings in made:
        label, family_name, file_name = spec.label, spec.family, spec.file
        out = os.path.join(OUT_DIR, file_name)
        merged = TTFont(out)
        cmap = merged.getBestCmap()
        missing = sorted(codes - set(cmap))
        if missing:
            raise SystemExit("%s lacks %s" % (file_name, ranges_of(missing)))
        drawn.update(cmap)
        if max(codes) > 0xFFFF and 12 not in cmap_formats(merged):
            raise SystemExit("%s: no format 12 character map: nothing past U+FFFF would be drawn" % file_name)
        for table in ("fvar", "gvar", "CFF ", "CFF2", "fpgm", "prep", "cvt ", "COLR", "CPAL", "kern"):
            if table in merged:
                raise SystemExit("%s has a %s table: it must be static, unhinted TrueType" % (file_name, table))
        different = shaping_differences(dict((f, os.path.join(work, f + "-subset.ttf")) for f in members), out,
                                        sorted(run for run in runs if run[0] in members))
        if different:
            say("shaped otherwise by %s (%d): %s" % (file_name, len(different), ", ".join(
                "%s [%s]" % (t, " ".join("%04X" % ord(c) for c in t)) for _, t in different[:40])))
        boxes = notdef_texts(out, [t for t in texts if all(ord(c) in codes for c in t)])
        if boxes:
            say("drawn with a box by %s (%d): %s" % (file_name, len(boxes), ", ".join(boxes[:40])))
        checked = checked and different is not None
        packed = lookup_bytes(merged)  # (as merged: no more than the sum of its sources', which check_limits counted)
        if len(merged.getGlyphOrder()) > sum(row["glyphs"] for row in rows) or any(packed[tag] > lookups[tag] for tag in packed):
            raise SystemExit("%s: %d glyphs and lookups of %r bytes as merged, more than the sum of its sources' "
                             "(%d, %r): check_limits counts too little" % (
                                 file_name, len(merged.getGlyphOrder()), dict(packed),
                                 sum(row["glyphs"] for row in rows), dict(lookups)))
        files.append(collections.OrderedDict((
            # (family: the name Qt and Font Check know it by, gdi_family; full_family: its own, name ID 4)
            ("font", label), ("family", gdi_family(family_name)), ("full_family", family_name),
            ("file", file_name), ("optional", spec.optional),
            ("holds", sources_rule(spec)), ("own_layout", spec.own_layout),
            ("size", os.path.getsize(out)),
            ("glyphs", len(merged.getGlyphOrder())), ("characters", len(codes)), ("sources", len(members)),
            ("lookup_bytes", packed),  # (of the MAX_LOOKUP_BYTES a table reaches: see lookup_bytes)
            ("lookup_bytes_left", MAX_LOOKUP_BYTES - max(packed.values())),
            # (its copy of its family name's characters, NAME_SUBSETS: [characters, glyphs], counted above too)
            ("name_subset", [[row["count"], row["glyphs"]] for row in rows if row["subset"] == "name"][:1]),
            ("warnings", warnings),  # (a limit reached to WARN_AT or more)
            ("scripts", sorted(set(ucd.script(chr(c)) for c in codes) - set(NOT_A_SCRIPT))),
            ("tables", sorted(tag for tag in merged.keys() if tag != "GlyphOrder")),
            ("cmap_formats", cmap_formats(merged)),
            ("line", [merged["hhea"].ascent, merged["hhea"].descent]),
            ("shaping_differences", len(different or [])),
            # (the letters and marks of the sources of ANCHORED that Noto Sans's mark lookups now hold)
            ("anchors_carried", carried),
        )))
        merged.close()
    missing = [c for c in wanted if c not in drawn and c not in left_set]
    if missing:
        raise SystemExit("the fonts lack %s" % ranges_of(missing))
    say("%-36s %7s %10s %6s %6s %6s %10s" % ("font", "sources", "characters", "glyphs", "GSUB", "GPOS", "bytes"))
    for row in files:
        say("%-36s %7d %10d %6d %6d %6d %10d%s" % (
            row["family"], row["sources"], row["characters"], row["glyphs"], row["lookup_bytes"]["GSUB"],
            row["lookup_bytes"]["GPOS"], row["size"], " (optional)" if row["optional"] else ""))
    say("%-36s %7d %10d %6d %6s %6s %10d (lookup bytes: of %d a table reaches; glyphs: of %d a font holds)" % (
        "all", sum(row["sources"] for row in files), sum(row["characters"] for row in files),
        sum(row["glyphs"] for row in files), "", "", sum(row["size"] for row in files), MAX_LOOKUP_BYTES, MAX_GLYPHS))
    say("(of them, each font's copy of its family name's characters: %s)" % "; ".join(
        "%s %d characters, %d glyphs" % (row["font"], row["name_subset"][0][0], row["name_subset"][0][1])
        for row in files if row["name_subset"]))
    write_text(os.path.join(OUT_DIR, LICENSE_FILE), license_notice(sources, licenses))
    covered = set(wanted) - left_set
    info = collections.OrderedDict((
        ("family", FAMILY),
        ("files", files),  # (the fonts: Font Check registers them, and Qt falls back from the first)
        ("limits", collections.OrderedDict((("glyphs", MAX_GLYPHS), ("lookup_bytes", MAX_LOOKUP_BYTES), ("warn_at", WARN_AT)))),
        # (the sources cut in two subsets, ELSEWHERE: {source: [the other font, the characters there]})
        ("elsewhere", collections.OrderedDict((family, list(found)) for family, found in sorted(ELSEWHERE.items()))),
        ("name_subsets", "every font but %s also holds the characters of its own family name, copied from %s with "
                         "the character map alone (the rows of fonts whose subset is \"name\"): the one exception "
                         "to each character in one font" % (group_of(FIRST), FIRST)),
        ("version", VERSION),
        ("license", "SIL Open Font License 1.1 (%s)" % LICENSE_FILE),
        ("made_by", "checks/train/language_font.py"),
        ("made_with", collections.OrderedDict((("fontTools", fontTools.version), ("uharfbuzz", harfbuzz_version())))),
        ("sources", "https://github.com/%s at %s (static Noto fonts); https://github.com/%s at %s (Noto Sans "
                    "JP, KR, SC, and Noto Emoji: the variable TrueType builds, instanced at Regular); Noto Serif "
                    "Dives Akuru 1.001 from its project's release (%s); for the characters and scripts no Noto "
                    "font has, pinned releases of SIL's Andika 7.000 (%s), Kanchenjunga 2.001 (%s), Kedebideri "
                    "3.001 (%s), and Padauk Book 6.000 (%s), and files of Unicodia's repository at a pinned commit "
                    "(%s): Unicodia Funky 3.1.3, Daarage, Shafarik, and BabelStone Pseudographica 16.0.0"
                    % (NOTO + GOOGLE + (DIVES_AKURU, ANDIKA, KANCHENJUNGA, KEDEBIDERI, PADAUK, UNICODIA))),
        ("archives", archives),  # (the release archives opened: {URL: SHA-256})
        ("covers", "every character of checks/font_characters.json a source font has, each in one of the "
                   "fonts: the names, autonyms, and headings, the languages' other names, the "
                   "orthographies' base, auxiliary, and mark characters, and the character sets' (not_covered "
                   "lists the others)"),
        ("units_per_em", UNITS_PER_EM),
        ("line", [line[0], -line[1]] if line else None),  # (ascent and descent, the same in every font)
        ("shaping_checked", checked),
        ("counts", collections.OrderedDict(
            [("all", [len(required), len(required & covered)])]
            + [(part, [len(codes), len(codes & covered)]) for part, codes in parts.items()])),  # [asked, drawn]
        ("required", ranges_of(covered)),  # (tests/language_font_tests.py)
        ("not_covered", ranges_of(unplaced)),
        ("not_covered_blocks", blocks_of(unplaced)),
        ("fonts", sources),
    ))
    write_text(os.path.join(OUT_DIR, INFO_FILE), json.dumps(info, ensure_ascii=False, indent=1) + "\n")
    if unplaced:
        say("no source has %d: %s" % (len(unplaced), ranges_of(unplaced)))
    return 0


def merge_recipe(font, subsets):
    """What a merged font kept in the work folder was made from: the same recipe gives the same font."""
    digest = hashlib.sha256()
    for path in subsets:
        digest.update(sha256(path).encode("ascii"))
    recipe = collections.OrderedDict((
        ("recipe", MERGE_RECIPE), ("version", VERSION), ("family", font.family), ("postscript", font.postscript),
        ("subsets", digest.hexdigest()), ("count", len(subsets)),
        ("fontTools", fontTools.version), ("uharfbuzz", harfbuzz_version())))
    if gdi_family(font.family) != font.family:  # (a font named otherwise for Windows: GDI_FAMILIES)
        recipe["gdi_family"] = gdi_family(font.family)
    return recipe


def license_notice(sources, licenses):
    lines = ["The fonts of %s (%s) are made of subsets of these fonts, merged and renamed by" % (
        FAMILY, "; ".join("%s, %s" % (font.file, font.family) for font in FONTS)),
        "checks/train/language_font.py (each source font is in the font named after it):", ""]
    places = collections.OrderedDict()  # (a source cut in two subsets is one font, in two of the fonts)
    for source in sources:
        places.setdefault((source["family"], source["version"], source["copyright"]), []).append(source["font"])
    for (family, version, copyright), fonts in places.items():
        lines.append("- %s, %s (in %s): %s" % (family, version, ", ".join(fonts), copyright))
    lines += ["", "They are licensed under the SIL Open Font License, Version 1.1, as are the fonts made of them. Their licenses, as",
              "their repositories and releases ship them (notofonts.github.io's fonts/LICENSE, google/fonts' OFL.txt, the",
              "OFL.txt of each release, and Unicodia's Fonts/LICENSE files for the fonts taken from its repository), follow."]
    if any(source["family"] == "Daarage" for source in sources):
        lines += ["", "Daarage's name records declare no license: its license is the file Unicodia ships beside it",
                  "(Fonts/LICENSE-Daarage), among the texts below, whole, under its copyright line."]
    if any(source["family"] == "UnicodiaFunky" for source in sources):
        lines += ["", "UnicodiaFunky's license file (Unicodia's Fonts/LICENSE-Funky) is a notice, not the license's text: it",
                  "places the font under the SIL Open Font License (version 1.1, by the font's copyright record), its",
                  "author's own glyphs under no condition at all, and names whose glyphs the others are. It is among the",
                  "texts below, whole."]
    lines.append("")
    texts = []
    for path in licenses:
        with open(path, encoding="utf-8") as handle:
            text = handle.read().replace("\r\n", "\n").strip() + "\n"
        if text not in texts:
            texts.append(text)
    return "\n".join(lines) + "\n" + "\n\n".join(("-" * 72 + "\n\n" + t) for t in texts)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache", default=CACHE_DIR, help="where the Noto fonts are downloaded (outside the repository)")
    parser.add_argument("--dry-run", action="store_true", help="count the characters, build nothing")
    parser.add_argument("--stage", choices=("plan", "subsets", "merge"),
                        help="plan: say which font supplies how many characters; subsets: make the subsets "
                             "not made yet; merge: merge the subsets made (default: everything)")
    parser.add_argument("--seconds", type=float, default=0,
                        help="start no new subset after this long (exit code 3 when some are left)")
    parser.add_argument("--font", metavar="LABEL",
                        help="with --stage merge: merge this font of FONTS alone (\"Essential\", \"Extended General\"), "
                             "keep it in the work folder, and write nothing")
    parser.add_argument("--fresh", action="store_true",
                        help="make every subset again (with --stage merge: every merge, or the one of --font)")
    parser.add_argument("--repin", action="store_true", help="accept sources whose SHA-256 language_font.json does not record")
    return build(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
