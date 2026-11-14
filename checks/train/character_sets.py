"""Build Font Check's character sets that are not languages (checks/character_sets.json).

Font Check lists these sets beside the languages, each covered by a definition that can be cited:

- Unicode 17.0.0 (the Unicode Character Database, Unicode License V3): the assigned characters of
  some blocks (Blocks.txt, UnicodeData.txt) used in phonetics, mathematics, East Asian typesetting,
  and notations, and for symbols; the
  characters with the Math property (DerivedCoreProperties.txt; Unicode Technical Report #25); the
  currency symbols (general category Sc). Control and format characters (categories Cc and Cf) are
  left out of these: no glyph is drawn for them.
- Google Fonts' glyph sets (googlefonts/glyphsets, Apache License 2.0): the encoded characters of each
  set (its .nam file); the glyphs without a code point that a set also asks for are not checked.
- Adobe's Latin, Cyrillic, and Greek character sets (adobe-type-tools, MIT License): each set's
  characters, and its letter-and-mark sequences Unicode has no single character for.

checks/character_sets_LICENSE keeps the three notices.

    python checks/train/character_sets.py --download <folder> [--out <file.json>]

Python 3, no package needed. The sources are downloaded over HTTPS into the folder given (outside the
repository), at pinned versions, and checked against their SHA-256; files already there are reused.
"""

import argparse
import hashlib
import json
import os
import re
import tarfile
import unicodedata
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(HERE, os.pardir, "character_sets.json")
UNICODE_VERSION = "17.0.0"
GLYPHSETS_TAG = "v1.1.3"
SOURCES = {  # file name: (URL, SHA-256)
    "unicode-%s-Blocks.txt" % UNICODE_VERSION: (
        "https://www.unicode.org/Public/%s/ucd/Blocks.txt" % UNICODE_VERSION,
        "c0edefaf1a19771e830a82735472716af6bf3c3975f6c2a23ffbe2580fbbcb15"),
    "unicode-%s-UnicodeData.txt" % UNICODE_VERSION: (
        "https://www.unicode.org/Public/%s/ucd/UnicodeData.txt" % UNICODE_VERSION,
        "2e1efc1dcb59c575eedf5ccae60f95229f706ee6d031835247d843c11d96470c"),
    "unicode-%s-DerivedCoreProperties.txt" % UNICODE_VERSION: (
        "https://www.unicode.org/Public/%s/ucd/DerivedCoreProperties.txt" % UNICODE_VERSION,
        "24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08"),
    "unicode-%s-Scripts.txt" % UNICODE_VERSION: (  # (the file checks/train/orthographies.py pins too)
        "https://www.unicode.org/Public/%s/ucd/Scripts.txt" % UNICODE_VERSION,
        "9f5e50d3abaee7d6ce09480f325c706f485ae3240912527e651954d2d6b035bf"),
    "unicode-%s-ScriptExtensions.txt" % UNICODE_VERSION: (
        "https://www.unicode.org/Public/%s/ucd/ScriptExtensions.txt" % UNICODE_VERSION,
        "ec2107e58825a1586acee8e0911ce18260394ac8b87e535ca325f1ccbeb06bc6"),
    "unicode-%s-PropertyValueAliases.txt" % UNICODE_VERSION: (  # (ScriptExtensions.txt names scripts by code)
        "https://www.unicode.org/Public/%s/ucd/PropertyValueAliases.txt" % UNICODE_VERSION,
        "64e9a5f76f7a1e8b5a47d6a1f9a26522a251208f5276bdfa1559dac7cf2e827a"),
    "unicode-%s-DerivedAge.txt" % UNICODE_VERSION: (
        "https://www.unicode.org/Public/%s/ucd/DerivedAge.txt" % UNICODE_VERSION,
        "f8ecdf768bdc210f201abd271d9bc587825618a86a7046a8146cc816393f1998"),
    "unicode-%s-Unihan.zip" % UNICODE_VERSION: (  # (read: Unihan_IRGSources.txt, kIRG_VSource)
        "https://www.unicode.org/Public/%s/ucd/Unihan.zip" % UNICODE_VERSION,
        "f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e"),
    "glyphsets-%s.tar.gz" % GLYPHSETS_TAG: (
        "https://codeload.github.com/googlefonts/glyphsets/tar.gz/refs/tags/%s" % GLYPHSETS_TAG,
        "4d80e35548c9dbcf0a787fb936df86d5c2a14d1a359ed9c492f304d3c169c03a"),
    "adobe-latin-charsets-3b8b7fc.tar.gz": (
        "https://codeload.github.com/adobe-type-tools/adobe-latin-charsets/tar.gz/"
        "3b8b7fc2d0cbc6cb56c55d68634ea6ac4a7ac8ac",
        "bb5a7f6d902088dcfa03c8e1818f7c1e2c321fda0dc60b5887ced739b79a889d"),
    "adobe-cyrillic-charsets-bcad240.tar.gz": (
        "https://codeload.github.com/adobe-type-tools/adobe-cyrillic-charsets/tar.gz/"
        "bcad2402d81c7202daa29d39aaa1d7242f65e994",
        "39ae62833dc0a333d68945f7938f9dad82776ce0bc29a10fb390197487e5b7a6"),
    "adobe-greek-charsets-aed8bd7.tar.gz": (
        "https://codeload.github.com/adobe-type-tools/adobe-greek-charsets/tar.gz/"
        "aed8bd71a2e377895fda1fb0e2df54f7b49c685c",
        "9f2717cf99c22fdf1e7b7a9a223ff05573392663cb24111002298507e65d9919"),
}
GROUPS = ("Phonetics", "Mathematics", "Symbols and punctuation", "CJK symbols and forms",
          "Han repertoires", "Notation", "Games and pictographs", "Legacy",
          "Foundries")  # (shown as "Character sets: foundries")
PHONETICS, MATHEMATICS, SYMBOLS, CJK, HAN, NOTATION, PICTOGRAPHS, LEGACY, FOUNDRY = range(9)
# The repertoires of ideographs a CJK font is made for, and those of the other writings in Han
# characters (Vietnam's Chu Nom, Zhuang's Sawndip, Japan's kokuji), by Unihan (Unicode 17.0.0): one set
# per national standard, list, or IRG source. What each is, as UAX #38 (revision 39, for Unicode
# 17.0.0) names it. Font Check's languages had the few thousand ideographs of Hyperglot's Chinese,
# Japanese, and Korean rows (Japanese: 1,958 of the 2,136 Joyo kanji; Korean: 755 hanja). No source
# here declares an orthography of Vietnamese or Zhuang in Han characters (Google's data has a file for
# vi_Hani with no characters; CLDR records Han as a secondary script of Vietnamese), so these are sets,
# not languages' rows. Each: (id, name, (Unihan field, the value or the values' prefixes it takes, or
# None for any), what UAX #38 says it is).
HAN_SETS = (  # (names spelled with escapes: the source stays ASCII)
    ("unihan-core2020", "Unihan Core 2020 (Unihan kUnihanCore2020)", ("kUnihanCore2020", None),
     "the minimal set of required ideographs for East Asia"),
    ("unihan-gb2312", "GB/T 2312-1980 (Unihan G0)", ("kIRG_GSource", ("G0-",)), "GB/T 2312-1980"),
    ("unihan-tgh", "T\N{LATIN SMALL LETTER O WITH MACRON}ngy\N{LATIN SMALL LETTER O WITH GRAVE}ng Gu\N{LATIN SMALL LETTER I WITH MACRON}"
                   "f\N{LATIN SMALL LETTER A WITH GRAVE}n H\N{LATIN SMALL LETTER A WITH GRAVE}nz\N{LATIN SMALL LETTER I WITH GRAVE}"
                   "bi\N{LATIN SMALL LETTER A WITH CARON}o, 2013 (Unihan kTGH)", ("kTGH", None),
     "the table of general standard Chinese characters"),
    ("unihan-big5", "Big Five (Unihan kBigFive)", ("kBigFive", None), "Big Five"),
    ("unihan-hkscs", "HKSCS-2008 and 2016 (Unihan H and HD)", ("kIRG_HSource", ("H-", "HD-")),
     "the Hong Kong Supplementary Character Set, 2008 and 2016"),
    ("unihan-joyo", "J\N{LATIN SMALL LETTER O WITH MACRON}y\N{LATIN SMALL LETTER O WITH MACRON} kanji, 2010 (Unihan kJoyoKanji)",
     ("kJoyoKanji", ("2010",)), "the J\N{LATIN SMALL LETTER O WITH MACRON}y\N{LATIN SMALL LETTER O WITH MACRON} Kanji table of 2010"),
    ("unihan-jinmeiyo", "Jinmei-y\N{LATIN SMALL LETTER O WITH MACRON} kanji (Unihan kJinmeiyoKanji)", ("kJinmeiyoKanji", None),
     "the Jinmei-y\N{LATIN SMALL LETTER O WITH MACRON} Kanji table"),
    ("unihan-jis0208", "JIS X 0208-1990 (Unihan J0)", ("kIRG_JSource", ("J0-",)), "JIS X 0208-1990"),
    # (kJIS0213 maps the ideographs JIS X 0213 adds to JIS X 0208: its levels 3 and 4, 3,695 of them)
    ("unihan-jis0213", "JIS X 0213:2004, levels 3 and 4 (Unihan kJIS0213)", ("kJIS0213", None),
     "the JIS X 0213:2004 mapping"),
    ("unihan-kokuji", "Japanese kokuji (Unihan JK)", ("kIRG_JSource", ("JK-",)), "the Japanese KOKUJI Collection"),
    ("unihan-ksx1001", "KS X 1001:2004 hanja (Unihan K0)", ("kIRG_KSource", ("K0-",)), "KS X 1001:2004"),
    ("unihan-koredu", "Basic education hanja, 2007 (Unihan kKoreanEducationHanja)", ("kKoreanEducationHanja", None),
     "the list of 1,800 basic ideographs for education in Hanmun"),
    ("unihan-korname", "Personal-name hanja (Unihan kKoreanName)", ("kKoreanName", None),
     "the list of ideographs for personal names"),
    ("unihan-sawndip", "Sawndip (Unihan GZ, GZA, GPGLG, and GLGYJ)", ("kIRG_GSource", ("GZ-", "GZA-", "GPGLG-", "GLGYJ-")),
     "the Ancient Zhuang Character Dictionary (1989) and the sources of Zhuang songs and texts"),
    ("unihan-v0", "TCVN 5773:1993 (Unihan V0)", ("kIRG_VSource", ("V0-",)), "the Vietnamese standard TCVN 5773:1993"),
    ("unihan-v1", "TCVN 6056:1995 (Unihan V1)", ("kIRG_VSource", ("V1-",)), "the Vietnamese standard TCVN 6056:1995"),
    ("unihan-v2", "VHN 01:1998 (Unihan V2)", ("kIRG_VSource", ("V2-",)), "VHN 01:1998"),
    ("unihan-v3", "VHN 02:1998 (Unihan V3)", ("kIRG_VSource", ("V3-",)), "VHN 02:1998"),
    ("unihan-v4", "H\N{LATIN SMALL LETTER A WITH ACUTE}n N\N{LATIN SMALL LETTER O WITH CIRCUMFLEX}m Coded Character "
                  "Repertoire (Unihan V4)", ("kIRG_VSource", ("V4-",)),
     "Kho Ch\N{LATIN SMALL LETTER U WITH HORN AND TILDE} H\N{LATIN SMALL LETTER A WITH ACUTE}n "
     "N\N{LATIN SMALL LETTER O WITH CIRCUMFLEX}m M\N{LATIN SMALL LETTER A WITH GRAVE} Ho\N{LATIN SMALL LETTER A WITH ACUTE} "
     "(the H\N{LATIN SMALL LETTER A WITH ACUTE}n N\N{LATIN SMALL LETTER O WITH CIRCUMFLEX}m Coded Character "
     "Repertoire), H\N{LATIN SMALL LETTER A WITH GRAVE} N\N{LATIN SMALL LETTER O WITH CIRCUMFLEX AND DOT BELOW}i, 2007"),
    ("unihan-vn", "Vietnamese extensions (Unihan VN)", ("kIRG_VSource", ("VN-",)),
     "the Vietnamese horizontal and vertical extensions"),
)
UNIHAN_PREFIX = "unihan-"  # (a set of Unihan's ideographs)
# Optional characters: listed in a set or a script's row, but not needed for it to be complete, since
# text does not store them (optional_codes says which). They are
# - the presentation forms of these three blocks, every character with a decomposition (the Latin,
#   Armenian, and Hebrew ligatures and pointed or wide letters; the Arabic contextual forms and
#   ligatures) and the Arabic tail fragment, a piece of legacy shaping with none: fonts draw them by
#   shaping now, from the plain letters text stores;
PRESENTATION_BLOCKS = ("Alphabetic Presentation Forms", "Arabic Presentation Forms-A", "Arabic Presentation Forms-B")
PRESENTATION_WITHOUT_DECOMPOSITION = (0xFE73,)  # ARABIC TAIL FRAGMENT
# - but for the characters of Arabic Presentation Forms-A still typed as signs in their own right, which
#   stay required: those Unicode classes as symbols or punctuation (the Arabic symbols U+FBB2 to U+FBC2,
#   the honorific ligatures, the Basmala, the ornate parentheses, the rial sign), and three ligatures it
#   classes as letters, U+FDF2 (Allah) and U+FDFA (an honorific: "sallallahou alayhe wasallam"), which
#   the pinned word counts show typed as signs (Unilex: Urdu 1,116 times, Hausa 4,583), and U+FDFB
#   (the honorific "jallajalalouhou"), of the same kind as U+FDFA;
IN_USE_LETTERS = (0xFDF2, 0xFDFA, 0xFDFB)
OPTIONAL_ABOUT = ("optional: {set id: its optional characters, as hexadecimal code points and ranges}, and each "
                  "script row's last column: characters the set or script holds but is complete without, since text "
                  "does not store them (presentation forms, which fonts draw by shaping from the plain letters; "
                  "compatibility ideographs and other characters normalization replaces by another). A Legacy set's "
                  "characters are all optional.")
# - and every canonical singleton, a character Unicode's normalization (NFC) replaces by another single
#   one, so that normalized text never holds it: the CJK compatibility ideographs (duplicates of unified
#   ones kept for round trips with older standards) and a few others (the Kelvin, Ohm, and angstrom
#   signs, two angle brackets, two spaces, two combining tone marks), but the Greek ones, which stay
#   required: the owner, "Let's include all Greek polytonic letters (oxia)": polytonic text keeps the
#   letters with oxia, the standalone oxia and varia, prosgegrammeni, the koronis, and the numeral sign
#   (each a character whose Unicode name says GREEK). The Ohm sign, a duplicate of capital omega whose
#   name does not, stays optional.
GREEK_KEPT = "GREEK"  # (a canonical singleton whose name holds this word stays required)
# A set whose characters are all optional is a Legacy set: the blocks of those characters, but the few
# each holds that text does use (a Hebrew mark; the Arabic signs above; twelve unified ideographs), which
# their scripts' rows count as required.
LEGACY_BLOCKS = PRESENTATION_BLOCKS + ("CJK Compatibility Ideographs", "CJK Compatibility Ideographs Supplement")
LEGACY_NOTES = {
    "Alphabetic Presentation Forms": "the Latin and Armenian ligatures and the Hebrew letters with points, wide "
                                     "letters, and ligature that older encodings stored as characters (but the "
                                     "Judeo-Spanish varika, a Hebrew mark in use); fonts draw these by shaping now, "
                                     "from the plain letters text stores.",
    "Arabic Presentation Forms-A": "the Arabic ligatures and contextual forms that older encodings stored as "
                                   "characters (but the symbols, honorifics, ornate parentheses, and rial sign typed in "
                                   "their own right, which the Arabic script counts as required); fonts draw these by "
                                   "shaping now, from the plain letters text stores.",
    "Arabic Presentation Forms-B": "the contextual forms of the Arabic letters (and a tail fragment) that older "
                                   "encodings stored as characters; fonts draw these by shaping now, from the plain "
                                   "letters text stores.",
    "CJK Compatibility Ideographs": "duplicates of unified ideographs kept for round trips with older standards, "
                                    "which normalization replaces by the unified ones (but the twelve unified "
                                    "ideographs of the block, which Han counts as required); fonts give such forms "
                                    "through variation sequences now.",
    "CJK Compatibility Ideographs Supplement": "duplicates of unified ideographs kept for round trips with older "
                                              "standards, which normalization replaces by the unified ones; fonts "
                                              "give such forms through variation sequences now.",
}
NO_GLYPH = ("Cc", "Cf")  # control and format characters: no glyph is drawn for them
NOT_CHARACTERS = ("Co", "Cs")  # private use and surrogates: assigned to no character
SCRIPTS_GROUP = "Scripts (Unicode)"  # the scripts' section in the Character sets tab
NO_SCRIPT = ("Common", "Inherited")  # Unicode's two values for characters of no one script
BLOCKS = (  # (group, Unicode block): its assigned characters
    (PHONETICS, "IPA Extensions"), (PHONETICS, "Phonetic Extensions"), (PHONETICS, "Phonetic Extensions Supplement"),
    (PHONETICS, "Spacing Modifier Letters"), (PHONETICS, "Modifier Tone Letters"),
    (MATHEMATICS, "Mathematical Operators"), (MATHEMATICS, "Supplemental Mathematical Operators"),
    (MATHEMATICS, "Miscellaneous Mathematical Symbols-A"), (MATHEMATICS, "Miscellaneous Mathematical Symbols-B"),
    (MATHEMATICS, "Mathematical Alphanumeric Symbols"), (MATHEMATICS, "Letterlike Symbols"),
    (MATHEMATICS, "Number Forms"), (MATHEMATICS, "Superscripts and Subscripts"), (MATHEMATICS, "Arrows"),
    (MATHEMATICS, "Supplemental Arrows-A"), (MATHEMATICS, "Supplemental Arrows-B"),
    (MATHEMATICS, "Miscellaneous Technical"),
    (SYMBOLS, "General Punctuation"), (SYMBOLS, "Currency Symbols"), (SYMBOLS, "Box Drawing"),
    (SYMBOLS, "Block Elements"), (SYMBOLS, "Geometric Shapes"), (SYMBOLS, "Miscellaneous Symbols"),
    (SYMBOLS, "Dingbats"),
    # Added after the survey of Unicode 17.0 (--survey): whole blocks a type designer may target whose
    # characters no language, script, or set above answered for (symbols, notation, games, pictographs),
    # and four blocks of scripts that are notations (Braille, SignWriting, Duployan shorthand, Greek music).
    (MATHEMATICS, "Supplemental Arrows-C"),
    (SYMBOLS, "Supplemental Punctuation"), (SYMBOLS, "Miscellaneous Symbols and Arrows"),
    (SYMBOLS, "Miscellaneous Symbols Supplement"), (SYMBOLS, "Geometric Shapes Extended"),
    (SYMBOLS, "Ornamental Dingbats"), (SYMBOLS, "Enclosed Alphanumerics"),
    (SYMBOLS, "Enclosed Alphanumeric Supplement"), (SYMBOLS, "Control Pictures"),
    (SYMBOLS, "Optical Character Recognition"), (SYMBOLS, "Symbols for Legacy Computing"),
    (SYMBOLS, "Symbols for Legacy Computing Supplement"), (SYMBOLS, "Alchemical Symbols"),
    (SYMBOLS, "Ancient Symbols"), (SYMBOLS, "Phaistos Disc"),
    (NOTATION, "Musical Symbols"), (NOTATION, "Byzantine Musical Symbols"),
    (NOTATION, "Znamenny Musical Notation"), (NOTATION, "Ancient Greek Musical Notation"),
    (NOTATION, "Braille Patterns"), (NOTATION, "Sutton SignWriting"), (NOTATION, "Duployan"),
    (NOTATION, "Counting Rod Numerals"), (NOTATION, "Mayan Numerals"), (NOTATION, "Kaktovik Numerals"),
    (NOTATION, "Indic Siyaq Numbers"), (NOTATION, "Ottoman Siyaq Numbers"),
    (NOTATION, "Tai Xuan Jing Symbols"), (NOTATION, "Yijing Hexagram Symbols"),
    (PICTOGRAPHS, "Chess Symbols"), (PICTOGRAPHS, "Playing Cards"), (PICTOGRAPHS, "Domino Tiles"),
    (PICTOGRAPHS, "Mahjong Tiles"), (PICTOGRAPHS, "Miscellaneous Symbols and Pictographs"),
    (PICTOGRAPHS, "Emoticons"), (PICTOGRAPHS, "Transport and Map Symbols"),
    (PICTOGRAPHS, "Supplemental Symbols and Pictographs"), (PICTOGRAPHS, "Symbols and Pictographs Extended-A"),
    # Added after a second survey (every block of Blocks.txt against the sets): the blocks whose
    # characters are no one script's own (Common or Inherited, which ScriptExtensions.txt may lend to
    # several scripts) and that no set held whole. The combining marks, which orthographies ask for
    # one by one; the East Asian symbols and compatibility forms, a group of their own; numbers and
    # marks several scripts share; and the Arabic mathematical alphabet, as its Latin counterpart.
    (PHONETICS, "Combining Diacritical Marks"), (PHONETICS, "Combining Diacritical Marks Extended"),
    (PHONETICS, "Combining Diacritical Marks Supplement"), (PHONETICS, "Combining Half Marks"),
    (MATHEMATICS, "Combining Diacritical Marks for Symbols"), (MATHEMATICS, "Arabic Mathematical Alphabetic Symbols"),
    (CJK, "CJK Symbols and Punctuation"), (CJK, "Ideographic Description Characters"), (CJK, "Kanbun"),
    (CJK, "CJK Strokes"), (CJK, "Enclosed CJK Letters and Months"), (CJK, "CJK Compatibility"),
    (CJK, "Enclosed Ideographic Supplement"), (CJK, "Vertical Forms"), (CJK, "CJK Compatibility Forms"),
    (CJK, "Small Form Variants"), (CJK, "Halfwidth and Fullwidth Forms"),
    (NOTATION, "Aegean Numbers"), (NOTATION, "Coptic Epact Numbers"), (NOTATION, "Common Indic Number Forms"),
    (NOTATION, "Vedic Extensions"),
)
GOOGLE = (  # (group, glyph set, name shown): the set's .nam file
    (PHONETICS, "GF_Phonetics_IPAStandard", "IPA (GF Phonetics IPA Standard)"),
    (PHONETICS, "GF_Phonetics_IPAHistorical", "IPA, historical (GF Phonetics IPA Historical)"),
    (PHONETICS, "GF_Phonetics_DisorderedSpeech", "GF Phonetics Disordered Speech"),
    (PHONETICS, "GF_Phonetics_APA", "GF Phonetics APA"),
    (PHONETICS, "GF_Phonetics_SinoExt", "GF Phonetics SinoExt"),
    (FOUNDRY, "GF_Latin_Kernel", "GF Latin Kernel"), (FOUNDRY, "GF_Latin_Core", "GF Latin Core"),
    (FOUNDRY, "GF_Latin_Plus", "GF Latin Plus"), (FOUNDRY, "GF_Latin_Vietnamese", "GF Latin Vietnamese"),
    (FOUNDRY, "GF_Latin_PriAfrican", "GF Latin PriAfrican"), (FOUNDRY, "GF_Latin_African", "GF Latin African"),
    (FOUNDRY, "GF_Latin_Beyond", "GF Latin Beyond"),
    (FOUNDRY, "GF_TransLatin_Arabic", "GF TransLatin Arabic"), (FOUNDRY, "GF_TransLatin_Pinyin", "GF TransLatin Pinyin"),
    (FOUNDRY, "GF_Cyrillic_Core", "GF Cyrillic Core"), (FOUNDRY, "GF_Cyrillic_Plus", "GF Cyrillic Plus"),
    (FOUNDRY, "GF_Cyrillic_Pro", "GF Cyrillic Pro"), (FOUNDRY, "GF_Cyrillic_Historical", "GF Cyrillic Historical"),
    (FOUNDRY, "GF_Greek_Core", "GF Greek Core"), (FOUNDRY, "GF_Greek_Plus", "GF Greek Plus"),
    (FOUNDRY, "GF_Greek_Pro", "GF Greek Pro"), (FOUNDRY, "GF_Greek_Archaic", "GF Greek Archaic"),
    (FOUNDRY, "GF_Greek_Coptic", "GF Greek Coptic"),
    (FOUNDRY, "GF_Arabic_Core", "GF Arabic Core"), (FOUNDRY, "GF_Arabic_Plus", "GF Arabic Plus"),
)
GOOGLE_PHONETICS_NOTE = " Google Fonts calls its phonetics sets a work in progress."
ADOBE = (  # (archive, name shown, the set's lists)
    ("adobe-latin-charsets-3b8b7fc.tar.gz", "Adobe Latin 1", ("adobe-latin-1.txt",)),
    ("adobe-latin-charsets-3b8b7fc.tar.gz", "Adobe Latin 2", ("adobe-latin-2.txt",)),
    ("adobe-latin-charsets-3b8b7fc.tar.gz", "Adobe Latin 3", ("adobe-latin-3.txt",)),
    ("adobe-latin-charsets-3b8b7fc.tar.gz", "Adobe Latin 4",
     ("adobe-latin-4-precomposed.txt", "adobe-latin-4-combined.txt")),
    ("adobe-latin-charsets-3b8b7fc.tar.gz", "Adobe Latin 5",
     ("adobe-latin-5-precomposed.txt", "adobe-latin-5-combined.txt")),
    ("adobe-cyrillic-charsets-bcad240.tar.gz", "Adobe Cyrillic 1", ("adobe-cyrillic-1.txt",)),
    ("adobe-cyrillic-charsets-bcad240.tar.gz", "Adobe Cyrillic 2", ("adobe-cyrillic-2.txt",)),
    ("adobe-cyrillic-charsets-bcad240.tar.gz", "Adobe Cyrillic 3",
     ("adobe-cyrillic-3-precomposed.txt", "adobe-cyrillic-3-combined.txt")),
    ("adobe-greek-charsets-aed8bd7.tar.gz", "Adobe Greek 1", ("adobe-greek-1.txt",)),
    ("adobe-greek-charsets-aed8bd7.tar.gz", "Adobe Greek 2", ("adobe-greek-2.txt",)),
)
HEX = re.compile(r"^[0-9A-Fa-f]{4,6}$")


def sha256_of(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def download(folder):
    """{file name: path} of the pinned sources, fetched into folder when not there yet, each checked."""
    os.makedirs(folder, exist_ok=True)
    found = {}
    for name, (url, digest) in sorted(SOURCES.items()):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            download_one(url, path)
        if sha256_of(path) != digest:
            raise SystemExit("%s: SHA-256 %s, expected %s" % (path, sha256_of(path), digest))
        found[name] = path
    return found


def download_one(url, path):
    """A file fetched over HTTPS, with a generic User-Agent, written whole or not at all."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; fetch)"})
    with urllib.request.urlopen(request, timeout=300) as response:
        data = response.read()
    with open(path + ".part", "wb") as handle:
        handle.write(data)
    os.replace(path + ".part", path)


def text_of(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def members(path, suffix):
    """{base name: text} of an archive's files whose path ends with suffix (nothing in it is run)."""
    found = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith(suffix):
                found[member.name.rsplit("/", 1)[-1]] = archive.extractfile(member).read().decode("utf-8")
    return found


def categories(unicode_data):
    """{code point: general category} of the assigned characters (ranges given by their ends filled in)."""
    found, first = {}, None
    for line in unicode_data.splitlines():
        fields = line.split(";")
        if len(fields) < 3:
            continue
        code = int(fields[0], 16)
        if fields[1].endswith(", First>"):
            first = code
        elif fields[1].endswith(", Last>"):
            for inside in range(first, code + 1):
                found[inside] = fields[2]
        else:
            found[code] = fields[2]
    return found


def decompositions(unicode_data):
    """{code point: its decomposition field ("<isolated> 0627", "6ED1")} of the characters that have one."""
    found = {}
    for line in unicode_data.splitlines():
        fields = line.split(";")
        if len(fields) > 5 and fields[5]:
            found[int(fields[0], 16)] = fields[5]
    return found


def optional_codes(files, category=None):
    """(the optional characters, the characters of the presentation blocks kept required as signs in use):
    see PRESENTATION_BLOCKS and the notes above it."""
    text = text_of(files["unicode-%s-UnicodeData.txt" % UNICODE_VERSION])
    category = category or categories(text)
    decomposed = decompositions(text)
    spans = blocks(text_of(files["unicode-%s-Blocks.txt" % UNICODE_VERSION]))
    drawn = lambda code: code in category and category[code] not in NO_GLYPH + NOT_CHARACTERS
    optional, in_use = set(), set()
    for name in PRESENTATION_BLOCKS:
        low, high = spans[name]
        for code in range(low, high + 1):
            if not drawn(code):
                continue
            if name == "Arabic Presentation Forms-A" and (category[code][0] in "SP" or code in IN_USE_LETTERS):
                in_use.add(code)
            elif code in decomposed or code in PRESENTATION_WITHOUT_DECOMPOSITION:
                optional.add(code)
    names = dict((int(line.split(";")[0], 16), line.split(";")[1]) for line in text.splitlines() if ";" in line)
    for code, mapping in decomposed.items():  # (the canonical singletons, but the Greek ones)
        if (not mapping.startswith("<") and len(mapping.split()) == 1 and drawn(code)
                and GREEK_KEPT not in names.get(code, "").split()):
            optional.add(code)
    return optional, in_use


def unihan_fields(files, wanted):
    """{Unihan field: {code point: value}} of the fields wanted, from every file of Unihan.zip."""
    found = dict((field, {}) for field in wanted)
    with zipfile.ZipFile(files["unicode-%s-Unihan.zip" % UNICODE_VERSION]) as archive:
        for name in sorted(archive.namelist()):
            for line in archive.read(name).decode("utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) == 3 and parts[1] in found:
                    found[parts[1]][int(parts[0][2:], 16)] = parts[2]
    for field, values in found.items():
        if not values:
            raise SystemExit("Unihan has no field %s" % field)
    return found


def legacy_codes(path=OUT_FILE):
    """The characters of the Legacy sets of a data file (presentation forms, compatibility ideographs),
    for the orthographies' train scripts. A missing file stops the build: the languages would keep
    presentation forms, and their data would drift from what is committed with no error."""
    if not os.path.isfile(path):
        raise SystemExit("%s is missing: restore it (git checkout) or build it with character_sets.py first" % path)
    with open(path, encoding="ascii") as handle:
        data = json.load(handle)
    if "Legacy" not in data["groups"]:
        return set()
    legacy = data["groups"].index("Legacy")
    return set(code for row in data["sets"] if row[2] == legacy for code in codes_of(row[4]))


def without_legacy(items, legacy, split):
    """An orthography's characters with each Legacy character replaced by what normalization (NFKC)
    makes of it, split into characters by split (an isolated alef: the alef), each once: a source that
    lists a presentation form names the letter, which is what text stores and a font is checked for."""
    found = []
    for item in items:
        pieces = split(unicodedata.normalize("NFKC", item)) if any(ord(ch) in legacy for ch in item) else [item]
        for piece in pieces:
            if piece and piece not in found and not any(ord(ch) in legacy for ch in piece):
                found.append(piece)
    return found


def optional_of(codes, optional):
    """A row's optional characters, as ranges ("" when none)."""
    return ranges_text(set(codes) & optional)


def blocks(text):
    found = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if line:
            span, name = [part.strip() for part in line.split(";")]
            low, high = span.split("..")
            found[name] = (int(low, 16), int(high, 16))
    return found


def property_codes(text, wanted):
    """The code points with a property in a UCD file of "code or range ; property" lines."""
    found = set()
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        span, name = [part.strip() for part in line.split(";")[:2]]
        if name != wanted:
            continue
        low, _, high = span.partition("..")
        found.update(range(int(low, 16), int(high or low, 16) + 1))
    return found


def property_map(text):
    """{code point: value} of a UCD file of "code or range ; value" lines."""
    found = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        span, value = [part.strip() for part in line.split(";")[:2]]
        low, _, high = span.partition("..")
        for code in range(int(low, 16), int(high or low, 16) + 1):
            found[code] = value
    return found


def script_aliases(text):
    """{"Latn": "Latin"}: the scripts' long names by their codes (PropertyValueAliases.txt, "sc" lines)."""
    found = {}
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("#")[0].split(";")]
        if len(parts) >= 3 and parts[0] == "sc":
            found[parts[1]] = parts[2]
    return found


def version_of(age):
    return tuple(int(part) for part in age.split("."))


def build_scripts(files, category=None):
    """[[name, its own characters, the characters it shares, the Unicode version it was first encoded
    in]] for every script of Scripts.txt but Common and Inherited, A to Z.

    A script's own characters are those whose Script property is the script: its letters, marks,
    digits, and punctuation. Common and Inherited characters belong to no one script; those Unicode
    assigns to the scripts that use them (ScriptExtensions.txt: the danda to Devanagari and 20 other
    scripts, the kana marks to Hiragana and Katakana) are the script's shared characters, with the few
    characters of another script it is also written with. A Common or Inherited character without
    Script_Extensions (the digits 0 to 9, the comma, a space) is no script's. Control and format
    characters are left out, as everywhere."""
    category = category or categories(text_of(files["unicode-%s-UnicodeData.txt" % UNICODE_VERSION]))
    script_of = property_map(text_of(files["unicode-%s-Scripts.txt" % UNICODE_VERSION]))
    names = script_aliases(text_of(files["unicode-%s-PropertyValueAliases.txt" % UNICODE_VERSION]))
    extended = property_map(text_of(files["unicode-%s-ScriptExtensions.txt" % UNICODE_VERSION]))
    age = property_map(text_of(files["unicode-%s-DerivedAge.txt" % UNICODE_VERSION]))
    drawn = lambda code: category.get(code) is not None and category[code] not in NO_GLYPH + NOT_CHARACTERS
    own, shared = {}, {}
    for code, script in script_of.items():
        if script not in NO_SCRIPT and drawn(code):
            own.setdefault(script, set()).add(code)
    for code, codes in extended.items():
        if drawn(code):
            for script in (names[one] for one in codes.split()):
                if script_of.get(code) != script:
                    shared.setdefault(script, set()).add(code)
    rows = []
    for script in sorted(own):
        since = min(version_of(age[code]) for code in own[script])
        rows.append([script.replace("_", " "), ranges_text(own[script]), ranges_text(shared.get(script, ())),
                     "%d.%d" % since[:2]])
    return rows


def codes_of(ranges):
    found = set()
    for part in ranges.split():
        low, _, high = part.partition("-")
        found.update(range(int(low, 16), int(high or low, 16) + 1))
    return found


CATEGORY_GROUPS = (("L", "Letters"), ("M", "Marks"), ("N", "Numbers"), ("P", "Punctuation"), ("S", "Symbols"),
                   ("Z", "Separators"), ("Cf", "Format characters"), ("Cc", "Control characters"))


def survey(files, rows, scripts, old_sets=None):
    """Unicode's assigned characters against what Font Check holds, from the data files beside this
    folder as they are: (the lines of a Markdown table by general category, the blocks holding the
    characters nothing answers for as [(count, of the block's characters, name)], the blocks no
    character set touches, the totals). Private-use code points and surrogates are no characters."""
    category = categories(text_of(files["unicode-%s-UnicodeData.txt" % UNICODE_VERSION]))
    block_spans = blocks(text_of(files["unicode-%s-Blocks.txt" % UNICODE_VERSION]))
    assigned = set(code for code, kind in category.items() if kind not in NOT_CHARACTERS)
    orthographies = set()
    for name in ("language_coverage.json", "language_orthographies.json"):
        with open(os.path.join(HERE, os.pardir, name), encoding="utf-8") as handle:
            data = json.load(handle)
        for row in data["orthographies"]:
            for index in row[7:9]:
                orthographies.update(ord(ch) for ch in data["texts"][index] if ch != " ")
            orthographies.update(ord(ch) for ch in row[9])
    in_sets = set()
    for row in rows:
        in_sets |= codes_of(row[4])
        in_sets.update(int(code, 16) for sequence in row[5].split() for code in sequence.split("+"))
    in_scripts = set()
    for row in scripts:
        in_scripts |= codes_of(row[1]) | codes_of(row[2])
    orthographies &= assigned
    held = orthographies | in_sets | in_scripts
    lines = ["| General category | Assigned | In an orthography | In a character set | In a script's set | In none |",
             "| --- | --- | --- | --- | --- | --- |"]
    number = lambda value: "{:,}".format(value)
    for prefix, title in CATEGORY_GROUPS + (("", "All"),):
        of_group = set(code for code in assigned if category[code].startswith(prefix))
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            title, number(len(of_group)), number(len(of_group & orthographies)), number(len(of_group & in_sets)),
            number(len(of_group & in_scripts)), number(len(of_group - held))))
    rest, untouched = [], []
    for name, (low, high) in block_spans.items():
        codes = set(range(low, high + 1)) & assigned
        if codes - held:
            rest.append((len(codes - held), len(codes), name))
        if codes and not codes & in_sets:
            untouched.append((len(codes), name, len(codes & in_scripts), len(codes & orthographies)))
    totals = {"assigned": len(assigned), "orthographies": len(orthographies), "sets": len(in_sets & assigned),
              "scripts": len(in_scripts), "none": len(assigned - held), "blocks": len(block_spans),
              "block_sets": sum(1 for row in rows if row[0].startswith("block-"))}
    if old_sets is not None:  # (the sets of a file made before: what the blocks added answer for)
        before = set()
        for row in old_sets:
            before |= codes_of(row[4])
        totals["none_before_blocks"] = len(assigned - (orthographies | before | in_scripts))
        totals["none_before_scripts"] = len(assigned - (orthographies | before))
    return lines, sorted(rest, reverse=True), sorted(untouched, reverse=True), totals


def nam_codes(text):
    return set(int(line.split()[0], 16) for line in text.splitlines() if line.startswith("0x"))


def adobe_items(text):
    """(code points, sequences) of an Adobe list: a tab-separated table whose first column is a code
    point, or several joined by commas (a letter and marks with no single character)."""
    codes, sequences = set(), []
    for line in text.splitlines()[1:]:
        parts = [part.strip() for part in line.split("\t")[0].split(",")]
        if not parts or not all(HEX.match(part) for part in parts):
            continue
        if len(parts) == 1:
            codes.add(int(parts[0], 16))
        else:
            sequence = tuple(int(part, 16) for part in parts)
            if sequence not in sequences:
                sequences.append(sequence)
    return codes, sequences


def ranges_text(codes):
    """"20-7E A0 152-153": sorted code points as hexadecimal ranges."""
    parts, codes = [], sorted(codes)
    at = 0
    while at < len(codes):
        end = at
        while end + 1 < len(codes) and codes[end + 1] == codes[end] + 1:
            end += 1
        parts.append("%X" % codes[at] if end == at else "%X-%X" % (codes[at], codes[end]))
        at = end + 1
    return " ".join(parts)


def build(files):
    category = categories(text_of(files["unicode-%s-UnicodeData.txt" % UNICODE_VERSION]))
    block_spans = blocks(text_of(files["unicode-%s-Blocks.txt" % UNICODE_VERSION]))
    drawn = lambda code: code in category and category[code] not in NO_GLYPH
    unicode_note = "Unicode %s" % UNICODE_VERSION
    rows = []  # [id, name, group, definition, code points, sequences]

    def add(key, name, group, definition, codes, sequences=()):
        if not codes and not sequences:
            raise SystemExit("%s: no character" % name)
        rows.append([key, name, group, definition, ranges_text(codes),
                     " ".join("+".join("%04X" % code for code in sequence) for sequence in sequences)])

    math = property_codes(text_of(files["unicode-%s-DerivedCoreProperties.txt" % UNICODE_VERSION]), "Math")
    google = members(files["glyphsets-%s.tar.gz" % GLYPHSETS_TAG], ".nam")
    google = dict((name, text) for name, text in google.items())
    adobe = dict((archive, members(files[archive], ".txt")) for archive in set(row[0] for row in ADOBE))
    for group in range(len(GROUPS)):
        for wanted, key, name in GOOGLE:
            if wanted == group:
                note = GOOGLE_PHONETICS_NOTE if group == PHONETICS else ""
                add(key.lower().replace("_", "-"), name, group,
                    "Google Fonts glyph set %s (googlefonts/glyphsets %s): its encoded characters; the glyphs "
                    "without a code point it also asks for are not checked.%s" % (key, GLYPHSETS_TAG.lstrip("v"), note),
                    nam_codes(google[key + ".nam"]))
        if group == MATHEMATICS:
            add("unicode-math", "Mathematics (Unicode's Math property)", group,
                "%s, the characters with the Math property (DerivedCoreProperties.txt; Unicode Technical Report "
                "#25, Unicode Support for Mathematics)." % unicode_note, set(code for code in math if drawn(code)))
        if group == SYMBOLS:
            add("unicode-sc", "Currency symbols (Unicode category Sc)", group,
                "%s, the characters of general category Sc (Symbol, currency), in any block." % unicode_note,
                set(code for code, kind in category.items() if kind == "Sc"))
        for wanted, block in BLOCKS:
            if wanted == group:
                low, high = block_spans[block]
                add("block-%04x" % low, "%s (Unicode block)" % block, group,
                    "%s, the block %s (U+%04X to U+%04X): its assigned characters, control and format characters "
                    "left out." % (unicode_note, block, low, high),
                    set(code for code in range(low, high + 1) if drawn(code)))
        if group == HAN:
            fields = unihan_fields(files, set(field for _, _, (field, _), _ in HAN_SETS))
            low_planes = [block_spans[name] for name in ("CJK Unified Ideographs", "CJK Unified Ideographs Extension A")]
            for key, name, (field, values), what in HAN_SETS:
                codes = set(code for code, value in fields[field].items()
                            if values is None or any(value == one or value.startswith(one) for one in values))
                past = sum(1 for one in codes if not any(low <= one <= high for low, high in low_planes))
                add(key, name, group,
                    "%s, Unihan (%s%s): the %s ideographs of %s, as UAX #38 names it; %s of them past CJK Unified "
                    "Ideographs and Extension A (Extension B and later)." % (
                        unicode_note, field, " " + ", ".join(one.rstrip("-") for one in values) if values else "",
                        "{:,}".format(len(codes)), what, "{:,}".format(past)), codes)
        if group == LEGACY:
            optional, _ = optional_codes(files, category)
            for block in LEGACY_BLOCKS:
                low, high = block_spans[block]
                add("block-%04x" % low, "%s (Unicode block)" % block, group,
                    "%s, the block %s (U+%04X to U+%04X), every character optional: %s" % (
                        unicode_note, block, low, high, LEGACY_NOTES[block]),
                    set(code for code in range(low, high + 1) if code in optional))
        if group == FOUNDRY:
            for archive, name, lists in ADOBE:
                codes, sequences = set(), []
                for one in lists:
                    more, joined = adobe_items(adobe[archive][one])
                    codes |= more
                    sequences += [s for s in joined if s not in sequences]
                add(name.lower().replace(" ", "-"), name, group,
                    "%s (adobe-type-tools/%s, %s): its characters%s. Adobe calls these sets informative, not "
                    "normative." % (name, archive.rsplit("-", 1)[0], ", ".join(lists),
                                    ", and its letters with marks that have no single character" if sequences else ""),
                    codes, sequences)
    return rows


def sets_optional(rows, optional):
    """{set id: its optional characters as ranges}, for the sets Unicode defines (its blocks, the Math
    property, the currency symbols) that hold any. A foundry's set (Google's, Adobe's) is checked as its
    list says: Adobe Latin 1 asks for the fi and fl ligatures, and they stay required there."""
    found = {}
    for row in rows:
        if row[0].startswith(("block-", "unicode-", UNIHAN_PREFIX)):
            ranges = optional_of(codes_of(row[4]), optional)
            if ranges:
                found[row[0]] = ranges
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", required=True, help="a folder, outside the repository, for the pinned sources")
    parser.add_argument("--out", default=OUT_FILE)
    parser.add_argument("--survey", action="store_true",
                        help="write nothing: print Unicode's assigned characters against the orthographies, the "
                             "sets, and the scripts (the table of docs/FONT-CHECK.md)")
    parser.add_argument("--before", help="with --survey: a character_sets.json made before, to count what the "
                                         "sets added since answer for")
    args = parser.parse_args()
    files = download(args.download)
    rows, scripts = build(files), build_scripts(files)
    optional, in_use = optional_codes(files)
    if args.survey:
        old = None
        if args.before:
            with open(args.before, encoding="utf-8") as handle:
                old = json.load(handle)["sets"]
        lines, rest, untouched, totals = survey(files, rows, scripts, old)
        print("\n".join(lines))
        print("\ntotals: %s" % ", ".join("%s %d" % item for item in sorted(totals.items())))
        print("\nIn none, by block (%d blocks):" % len(rest))
        for count, of, name in rest:
            print("  %6d of %6d  %s" % (count, of, name))
        print("\nBlocks no character set touches (%d): characters, name, of which in a script's set, in an "
              "orthography" % len(untouched))
        for count, name, in_scripts, in_orthographies in untouched:
            print("  %6d  %s  (%d, %d)" % (count, name, in_scripts, in_orthographies))
        return
    data = {"source": "Unicode %s (Unicode License V3), googlefonts/glyphsets %s (Apache License 2.0), and Adobe's "
                      "Latin, Cyrillic, and Greek character sets (MIT License): see character_sets_LICENSE" % (
                          UNICODE_VERSION, GLYPHSETS_TAG.lstrip("v")),
            "columns": ["id", "name", "group", "definition", "characters", "sequences"],
            "groups": list(GROUPS),
            "sets": rows,  # characters: hexadecimal code points and ranges; sequences: code points joined by +
            # Optional characters (presentation forms, compatibility ideographs, canonical singletons): a
            # set or a script holds them, but is complete without them. Kept beside the sets' rows, not
            # in them, so that a reader of six columns reads this file as before.
            "optional_about": OPTIONAL_ABOUT,
            "optional": sets_optional(rows, optional),
            # Every script of Unicode, checkable as a set where no language's orthography is known: its
            # own characters (Scripts.txt), those it shares (ScriptExtensions.txt), the version of
            # Unicode it was first encoded in (DerivedAge.txt), and those of either that are optional.
            "scripts": {"unicode": UNICODE_VERSION, "group": SCRIPTS_GROUP,
                        "columns": ["name", "characters", "shared", "since", "optional"],
                        "rows": [row + [optional_of(codes_of(row[1]) | codes_of(row[2]), optional)] for row in scripts]}}
    with open(args.out, "w", encoding="ascii", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=True, separators=(",", ":"))
        handle.write("\n")
    print("%d character sets and %d scripts written to %s (%d bytes)" % (
        len(rows), len(scripts), os.path.basename(args.out), os.path.getsize(args.out)))
    print("%d optional characters, held by %d sets and %d scripts; %d of the presentation blocks' characters kept "
          "required as signs in use (%s)" % (
              len(optional), len(data["optional"]), sum(1 for row in data["scripts"]["rows"] if row[4]), len(in_use),
              ranges_text(in_use)))


if __name__ == "__main__":
    main()
