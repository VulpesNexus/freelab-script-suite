"""Build Font Check's character sets that are not languages (checks/character_sets.json).

Font Check lists these sets beside the languages, each covered by a definition that can be cited:

- Unicode 17.0.0 (the Unicode Character Database, Unicode License V3): the assigned characters of
  some blocks (Blocks.txt, UnicodeData.txt) used in phonetics, mathematics, and for symbols; the
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
import urllib.request

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
GROUPS = ("Phonetics", "Mathematics", "Symbols and punctuation", "Notation", "Games and pictographs",
          "Foundries")  # (shown as "Character sets: foundries")
PHONETICS, MATHEMATICS, SYMBOLS, NOTATION, PICTOGRAPHS, FOUNDRY = range(6)
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
            with urllib.request.urlopen(url, timeout=120) as response, open(path, "wb") as handle:
                handle.write(response.read())
        if sha256_of(path) != digest:
            raise SystemExit("%s: SHA-256 %s, expected %s" % (path, sha256_of(path), digest))
        found[name] = path
    return found


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
            # Every script of Unicode, checkable as a set where no language's orthography is known: its
            # own characters (Scripts.txt), those it shares (ScriptExtensions.txt), and the version of
            # Unicode it was first encoded in (DerivedAge.txt).
            "scripts": {"unicode": UNICODE_VERSION, "group": SCRIPTS_GROUP,
                        "columns": ["name", "characters", "shared", "since"], "rows": scripts}}
    with open(args.out, "w", encoding="ascii", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=True, separators=(",", ":"))
        handle.write("\n")
    print("%d character sets and %d scripts written to %s (%d bytes)" % (
        len(rows), len(scripts), os.path.basename(args.out), os.path.getsize(args.out)))


if __name__ == "__main__":
    main()
