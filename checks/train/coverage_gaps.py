"""Write docs/COVERAGE-GAPS.md and checks/coverage_gaps.json: what Unicode's own data describes that Font
Check does not check, each with the reason, and the fonts to consider for what FreeLang cannot draw.

The owner (2026-11-14): "If we're checking Unicode databases, we can cast the widest possible net and
look for anything we are currently missing that can be added or at the very least acknowledged as
something we are aware of." Every Unicode block, Unihan source, sequence kind (named sequences,
standardized variants, emoji sequences, ideographic variation sequences), shaping property, and CLDR
data kind is compared with what the data files hold (checks/character_sets.json, the orthography
files, checks/font_characters.json, checks/language_font/language_font.json). What is added lives in
those files; what is acknowledged is written here, counted from the pinned data, so that the page
cannot drift: --check exits 1 when the files on disk differ from what the data gives now.

    python checks/train/coverage_gaps.py --download <folder> [--check]

The folder is character_sets.py's (its pinned Unicode files, and Unihan); the files this script reads
besides are pinned in EXTRA_SOURCES, downloaded there over HTTPS and checked against their SHA-256.
Python 3, no package needed.
"""

import argparse
import collections
import json
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
REPO = os.path.normpath(os.path.join(CHECKS, os.pardir))
DOC_FILE = os.path.join(REPO, "docs", "COVERAGE-GAPS.md")
JSON_FILE = os.path.join(CHECKS, "coverage_gaps.json")
sys.path.insert(0, HERE)
import character_sets  # noqa: E402

V = character_sets.UNICODE_VERSION
UCD = "https://www.unicode.org/Public/%s/" % V
EXTRA_SOURCES = {  # file name: (URL, SHA-256): Unicode's data files (Unicode License V3)
    "unicode-%s-NamedSequences.txt" % V: (UCD + "ucd/NamedSequences.txt",
                                          "0cd1c928edac72ea1369187599727c4f0d92367316b4c5ee5140475ab9298be0"),
    "unicode-%s-StandardizedVariants.txt" % V: (UCD + "ucd/StandardizedVariants.txt",
                                                "f55100b2fb11d3d75a37b8c1ab752192dbd1c4b12328c5ec6b38e3807c0ca597"),
    "unicode-%s-emoji-data.txt" % V: (UCD + "ucd/emoji/emoji-data.txt",
                                      "2cb2bb9455cda83e8481541ecf5b6dfda66a3bb89efa3fa7c5297eccf607b72b"),
    "unicode-%s-emoji-variation-sequences.txt" % V: (UCD + "ucd/emoji/emoji-variation-sequences.txt",
                                                     "bb3d09ef03f206012c7532dd52dc0a21c9efddba0135ea4cf0d9201b8b9bba7e"),
    "unicode-%s-emoji-sequences.txt" % V: (UCD + "emoji/emoji-sequences.txt",
                                           "12cc8267dc33cbd11ed32bcf6fc5dc2ad9c7a77bae1bdfba2f41b1b9b3ead8dd"),
    "unicode-%s-emoji-zwj-sequences.txt" % V: (UCD + "emoji/emoji-zwj-sequences.txt",
                                               "5b25441daed2322b068c5e70cda522946a4f0274df864445a1965a92e5fc5cad"),
    "unicode-%s-IndicSyllabicCategory.txt" % V: (UCD + "ucd/IndicSyllabicCategory.txt",
                                                 "3fc122f4cf58b0c19268d5f810263b04ab4e1e67743386ec0e0ada9c76aec5be"),
    "unicode-%s-ArabicShaping.txt" % V: (UCD + "ucd/ArabicShaping.txt",
                                         "39afa01e680e27d0fd10b67a9b27be13fbaa3d0efecfb5be45991de9a0d267d0"),
    # The Ideographic Variation Database's registry of 2025-07-14 (Unicode's IVD; read for its counts)
    "ivd-2025-07-14-IVD_Sequences.txt": ("https://www.unicode.org/ivd/data/2025-07-14/IVD_Sequences.txt",
                                         "0052165369b6c8783d19b041f0a70537a69d718d577b9df180453be9d8c10a87"),
}
CLDR_ZIP = "cldr-common-49.zip"  # (checks/train/orthographies.py's pin, in the folder "orthographies" beside)
# The Unihan sources and fields not made sets (checks/train/character_sets.py's HAN_SETS), each with why.
UNIHAN_LEFT = (
    ("kIRG_GSource", "G sources other than G0 and the Zhuang ones", "the dictionaries and lists China gave the IRG: "
     "a record of where an ideograph was found, not a repertoire a font is made for"),
    ("kIRG_JSource", "J sources other than J0 and JK (JIS X 0212, JIS X 0213's replacements, the vendors' and "
     "Moji Joho lists)", "JIS X 0213, the current standard, is a set (kJIS0213); the Moji Joho list (38,070) is "
     "an administrative register of name variants"),
    ("kIRG_KSource", "K sources other than K0 (KS X 1002, KS X 1027, the history database)",
     "supplementary standards of rare and historical hanja"),
    ("kIRG_KPSource", "KP sources (KPS 9566-97, KPS 10721-2000)", "North Korea's standards: no font is known to "
     "target them apart from KS X 1001"),
    ("kIRG_TSource", "T sources other than Big Five's planes (CNS 11643 planes 3 to 19)",
     "the rare ideographs of Taiwan's full standard, beyond Big Five"),
    ("kIRG_MSource", "M sources (Macao)", "348 ideographs, most of them HKSCS's too"),
    ("kIRG_SSource", "S source (the SAT Taisho Daizokyo)", "a Buddhist canon's ideographs"),
    ("kIRG_UKSource", "UK source", "the ideographs the United Kingdom submitted from scholarly texts"),
    ("kIRG_USource", "U source (the UTC)", "ideographs the UTC submitted"),
    ("kCantonese", "Cantonese readings", "a reading for nearly every ideograph: no list of Cantonese-specific "
     "characters (HKSCS, a set, holds those Hong Kong encodes)"),
    ("kZhuang", "Standard Zhuang readings", "readings of the Sawndip ideographs, which are a set"),
)
# Writings in Han characters, and Han-derived scripts: what the data holds of each, and why not more.
HAN_WRITINGS = (
    ("Chu Nom (Vietnamese)", "added", "six sets, one per Vietnamese source of the IRG (Unihan V0 to V4, VN)"),
    ("Sawndip (Zhuang)", "added", "one set: Unihan's GZ, GZA, GPGLG, and GLGYJ sources"),
    ("Japanese kokuji", "added", "one set: Unihan's JK source, the Japanese KOKUJI Collection"),
    ("Cantonese characters", "added in part", "HKSCS-2008 and 2016 is a set; no source lists Cantonese-specific "
     "characters as such"),
    ("Taiwanese Hokkien and Hakka characters", "acknowledged", "Taiwan's Ministry of Education lists recommended "
     "characters, but no pinned source with a license checked here holds them; most are in Big Five"),
    ("Korean gukja", "acknowledged", "no Unihan field or source marks them"),
    ("Bai characters", "acknowledged", "no source describes them; most are not encoded"),
    ("Jurchen, Khitan Large Script", "acknowledged", "not encoded in Unicode (the Script Encoding Initiative lists "
     "them)"),
    ("Tangut, Nushu, Khitan Small Script", "checked", "scripts of their own, checked as sets under Scripts (Unicode)"),
)
# The fonts the build looked at and left out, or that earlier work dismissed, looked at again on
# 2026-11-14 (the owner: "worth going back over fonts we have already dismissed prior").
RECONSIDERED = (
    ("GNU Unifont 18.0.01 (Unifoundry)", "taken", "dual-licensed (GPL 2 or later with the font embedding exception, "
     "and the SIL OFL 1.1, since 13.0.04): FreeLang takes it under the OFL, for the characters no outline font "
     "under a license FreeLang can take draws; its glyphs are a 16 by 16 grid of pixels"),
    ("Jigmo 2025-09-12 (Kamichi Koichi, GlyphWiki)", "replaced", "CC0 1.0 (its LICENSE.txt), a Mincho design: it drew "
     "the ideographs of the Han repertoires that Noto Sans JP, KR, and SC lack until Plangothic, which draws every one "
     "of them, took its place"),
    ("NewGardiner 3.09 (Mark-Jan Nederhof)", "taken", "SIL OFL 1.1 (its OFL.txt; its copyright record says so): the core "
     "signs of Egyptian Hieroglyphs Extended-A; it leaves out the non-core ones, which its maker calls unverified"),
    ("Plangothic V2.9.5795 (P1 6.400, P2 3.179; the Plangothic Project)", "taken", "SIL OFL 1.1 (its name records "
     "and LICENSE-OFL.txt; the names Plangothic and \N{CJK UNIFIED IDEOGRAPH-904D}\N{CJK UNIFIED IDEOGRAPH-9ED1} "
     "reserved): a gothic design on Source Han Sans CN, as Noto Sans SC is, for Extension B to J; it draws all of "
     "the 15,520 characters Jigmo supplied, and replaced it"),
    ("Plangothic P2's other characters (Tangut's additions of Unicode 16 and 17, Tai Yo, a few Syriac and Arabic)",
     "taken", "264 characters no source drew, or only Unifont's pixels, in the FreeLang+ General font; under the "
     "glyph names of Noto's fonts (lowko-taiyo, malayalamnga-syriac), its Tai Yo seemingly Noto Serif Tai Yo's, "
     "which states no license of its own: taken under Plangothic's OFL, the owner's decision of 2026-11-14"),
    ("BabelStone Tangut Wenhai 1.002", "not needed", "OFL 1.1, of 2016: none of Tangut's Unicode 16 and 17 additions, "
     "which Plangothic P2 draws"),
    ("Tangut Yinchuan (as BabelStone's page lists it)", "still left out", "\"Copyright Prof. Jing Yongshi\", no license named"),
    ("Noto Serif Tai Yo 1.030 (as Language Tools and Unicodia bundle it)", "still left out", "no copyright, license, or "
     "designer record and no license file; notofonts.github.io issue 81, which offers it to Noto, is still open"),
    ("Catrinity 2.250", "not needed", "OFL 1.1; every character it drew that FreeLang lacked now has a source"),
    ("Fairfax HD", "not needed", "OFL 1.1, a monospaced font drawn on a pixel grid"),
    ("JuliaMono 0.63.2, Charis 7.000", "not needed", "OFL 1.1; nothing FreeLang lacks"),
    ("Symbola (later versions), Everson Mono, Code2000", "still left out", "not free licenses"),
    ("The font Unicodia bundles for Syriac Supplement", "still left out", "its license forbids commercial use (as "
     "read on 2026-11-13); Unifont draws the eleven characters"),
)
# Fonts to consider for what FreeLang cannot draw: a font no FreeLang file can merge, or one too large
# for the five files. Each license read from the font's own files on 2026-11-14. (RESOURCE_FOR: the
# rows of Font Check, by their ids, whose tooltips could name each.)
RESOURCE_FOR = {"Plangothic P1, Plangothic P2": ["script:Han"],
                "Noto Color Emoji": ["block-1f300", "block-1f600", "block-1f680", "block-1f900", "block-1fa70"]}
RESOURCES = (
    ("Plangothic P1, Plangothic P2", "The Plangothic Project", "SIL OFL 1.1",
     "https://github.com/Fitzgerald-Porthmouth-Koenigsegg/Plangothic_Project",
     "with Noto Sans SC, JP, or KR (or Source Han Sans), every ideograph of Unicode 17.0 (103,351, and the "
     "compatibility ideographs), of which FreeLang holds only the Han repertoires' and the orthographies'",
     "install both beside FreeLang; too large for one of its files (65,535 glyphs at most); they leave most of "
     "the URO and Extension A to Source Han Sans"),
    ("Noto Color Emoji", "Google", "SIL OFL 1.1", "https://github.com/googlefonts/noto-emoji",
     "all 1,219 characters with the Emoji_Presentation property in color, the 14 newest among them (FreeLang draws "
     "those as Unifont's pixels), and 2,564 emoji sequences (ZWJ, flags, keycaps, skin tones) as ligatures",
     "a color font (COLR version 1, SVG): its outlines are color layers, so no plain glyph can be taken from it"),
)
NUMBER = lambda value: "{:,}".format(value)


def lines_of(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#")[0].strip()
            if line:
                yield [part.strip() for part in line.split(";")]


def codes_of(text):
    return character_sets.codes_of(text)


def span_codes(span):
    low, _, high = span.partition("..")
    return range(int(low, 16), int(high or low, 16) + 1)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def gather(files, folder):
    """Everything the page says, counted: a dict of plain values (lists, numbers, strings)."""
    text = character_sets.text_of(files["unicode-%s-UnicodeData.txt" % V])
    category = character_sets.categories(text)
    names = dict((int(line.split(";")[0], 16), line.split(";")[1]) for line in text.splitlines() if ";" in line)
    blocks = character_sets.blocks(character_sets.text_of(files["unicode-%s-Blocks.txt" % V]))
    script_of = character_sets.property_map(character_sets.text_of(files["unicode-%s-Scripts.txt" % V]))
    sets = load(os.path.join(CHECKS, "character_sets.json"))
    in_sets = set()
    for row in sets["sets"]:
        in_sets |= codes_of(row[4])
    own = set()
    for row in sets["scripts"]["rows"]:
        own |= codes_of(row[1])
    info = load(os.path.join(CHECKS, "language_font", "language_font.json"))
    drawn = set()
    for source in info["fonts"]:
        drawn |= codes_of(source["code_points"])
    found = collections.OrderedDict()
    # Blocks no set holds whole and no script owns whole
    rows = []
    for name, (low, high) in blocks.items():
        assigned = [code for code in range(low, high + 1) if code in category and category[code] not in ("Co", "Cs")]
        if not assigned:
            continue
        glyphs = [code for code in assigned if category[code] not in ("Cc", "Cf")]
        if glyphs and all(code in in_sets for code in glyphs):
            continue
        if glyphs and all(code in own for code in glyphs):
            continue
        rest = [code for code in glyphs if code not in in_sets and code not in own]
        if glyphs and not rest:
            continue  # (held whole by sets and scripts together)
        if not glyphs:
            why = "control or format characters: no glyph is drawn for them"
        elif all(names.get(code, "").startswith("VARIATION SELECTOR") for code in rest):
            why = "variation selectors: a font maps them in its cmap's format 14, which Font Check does not read"
        elif all(category[code] == "Cf" or category[code].startswith("M") for code in rest):
            why = "marks no set or script holds"
        else:
            why = "characters no set or script holds"
        rows.append([name, len(assigned), len(rest) if glyphs else 0, why])
    found["blocks"] = rows
    found["blocks_counted"] = len(blocks)
    # The Han repertoires added, and FreeLang's coverage of them
    han = [row for row in sets["sets"] if row[0].startswith(character_sets.UNIHAN_PREFIX)]
    found["han_sets"] = [[row[1], len(codes_of(row[4])), len(codes_of(row[4]) & drawn)] for row in han]
    fields = character_sets.unihan_fields(files, set(field for field, _, _ in UNIHAN_LEFT))
    found["unihan_left"] = [[label, NUMBER(len(fields[field])), why] for field, label, why in UNIHAN_LEFT]
    han_row = [row for row in sets["scripts"]["rows"] if row[0] == "Han"][0]
    han_codes = codes_of(han_row[1])
    found["han_row"] = [len(han_codes), len(han_codes & drawn)]
    # Sequences
    named = collections.Counter()
    for parts in lines_of(os.path.join(folder, "unicode-%s-NamedSequences.txt" % V)):
        named[script_of.get(int(parts[1].split()[0], 16), "Common").replace("_", " ")] += 1
    found["named"] = sorted(named.items(), key=lambda item: (-item[1], item[0]))
    variants = collections.Counter()
    for parts in lines_of(os.path.join(folder, "unicode-%s-StandardizedVariants.txt" % V)):
        variants[script_of.get(int(parts[0].split()[0], 16), "Common").replace("_", " ")] += 1
    found["variants"] = sorted(variants.items(), key=lambda item: (-item[1], item[0]))
    found["emoji_variation"] = sum(1 for _ in lines_of(os.path.join(folder, "unicode-%s-emoji-variation-sequences.txt" % V)))
    emoji = collections.Counter(parts[1] for parts in lines_of(os.path.join(folder, "unicode-%s-emoji-sequences.txt" % V)))
    emoji.update(parts[1] for parts in lines_of(os.path.join(folder, "unicode-%s-emoji-zwj-sequences.txt" % V)))
    found["emoji_sequences"] = sorted((kind, count) for kind, count in emoji.items() if kind != "Basic_Emoji")
    emoji_codes = set()
    for parts in lines_of(os.path.join(folder, "unicode-%s-emoji-data.txt" % V)):
        if parts[1] == "Emoji":
            emoji_codes.update(span_codes(parts[0]))
    found["emoji_characters"] = [len(emoji_codes), len(emoji_codes & in_sets), len(emoji_codes & drawn)]
    ivd = collections.Counter()
    with open(os.path.join(folder, "ivd-2025-07-14-IVD_Sequences.txt"), encoding="utf-8") as handle:
        for line in handle:
            if line.strip() and not line.startswith("#"):
                ivd[line.split(";")[1].strip()] += 1
    found["ivd"] = sorted(ivd.items(), key=lambda item: (-item[1], item[0]))
    # Shaping
    joining = collections.Counter(parts[2] for parts in lines_of(os.path.join(folder, "unicode-%s-ArabicShaping.txt" % V)))
    found["joining"] = sum(count for kind, count in joining.items() if kind in ("D", "R", "L", "C"))
    syllabic = collections.Counter()
    for parts in lines_of(os.path.join(folder, "unicode-%s-IndicSyllabicCategory.txt" % V)):
        syllabic[parts[1]] += len(span_codes(parts[0]))
    found["syllabic"] = sum(syllabic.values())
    # CLDR: what its locale files say that the orthographies do not take
    with zipfile.ZipFile(os.path.join(os.path.dirname(folder), "orthographies", CLDR_ZIP)) as archive:
        kinds, regional = collections.Counter(), 0
        for member in archive.namelist():
            if not (member.startswith("common/main/") and member.endswith(".xml")):
                continue
            stem = member[len("common/main/"):-4]
            if stem.count("_") and not (stem.count("_") == 1 and len(stem.split("_")[1]) == 4):
                regional += 1
                continue
            data = archive.read(member).decode("utf-8")
            for kind in ("punctuation", "numbers"):
                if 'exemplarCharacters type="%s"' % kind in data:
                    kinds[kind] += 1
        found["cldr"] = [kinds["punctuation"], kinds["numbers"], regional]
    # What FreeLang cannot draw, and what Unifont's pixels draw
    found["not_drawn"] = sorted(info.get("not_covered_blocks", {}).items())
    found["pixels"] = sorted([source["family"], source["code_points"]] for source in info["fonts"]
                             if source["family"] in ("Unifont", "Unifont Upper"))
    return found


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return out


def page(found):
    out = ["# Coverage gaps: what Font Check knows of and does not check", "",
           "Unicode's own data, compared with what Font Check checks (languages, character sets, scripts, "
           "sequences, marks): what was added, and what is acknowledged with the reason it is not checked. "
           "*checks/train/coverage_gaps.py* writes this page and *checks/coverage_gaps.json* from the pinned "
           "data (Unicode %s, Unihan, CLDR 49, the Ideographic Variation Database of 2025-07-14); its *--check* "
           "fails when they differ from what the data gives, so the counts cannot drift. The sources are "
           "registered in [SOURCES.md](SOURCES.md)." % V, ""]
    out += ["## Summary", ""]
    out += table(("What", "Decision", "Count"), [
        ("Han repertoires (national standards, lists, and Unihan's other writings)", "added: sets",
         "%d sets" % len(found["han_sets"])),
        ("Unicode blocks no set or script holds whole", "acknowledged", "%d of %d blocks" % (len(found["blocks"]),
                                                                                         found["blocks_counted"])),
        ("Unihan sources and fields not made sets", "acknowledged", "%d" % len(found["unihan_left"])),
        ("Named sequences", "acknowledged", NUMBER(sum(count for _, count in found["named"]))),
        ("Standardized variation sequences", "acknowledged", NUMBER(sum(count for _, count in found["variants"]))),
        ("Emoji variation sequences", "acknowledged", NUMBER(found["emoji_variation"])),
        ("Emoji sequences (keycaps, flags, tags, modifiers, ZWJ)", "acknowledged",
         NUMBER(sum(count for _, count in found["emoji_sequences"]))),
        ("Ideographic variation sequences", "acknowledged", NUMBER(sum(count for _, count in found["ivd"]))),
        ("Joining and Indic syllable shaping", "acknowledged", "%s joining and %s Indic characters" % (
            NUMBER(found["joining"]), NUMBER(found["syllabic"]))),
        ("CLDR's punctuation and number exemplars, regional locales", "acknowledged",
         "%d, %d, and %d locale files" % tuple(found["cldr"])),
        ("Characters FreeLang draws as Unifont's pixels", "added: font source",
         NUMBER(sum(len(codes_of(codes)) for _, codes in found["pixels"]))),
    ])
    out += ["", "## Han repertoires", "",
            "Font Check's languages had the ideographs of Hyperglot's Chinese, Japanese, and Korean rows (a few "
            "thousand). Each repertoire below is a character set under *Han repertoires*, from Unihan's fields as "
            "UAX #38 (revision 39) defines them; FreeLang draws each whole, Plangothic supplying what Noto Sans JP, KR, "
            "and SC lack. The Han script itself (%s ideographs) cannot be drawn whole: a font holds 65,535 glyphs "
            "at most, and FreeLang draws %s of them." % (NUMBER(found["han_row"][0]), NUMBER(found["han_row"][1])), ""]
    out += table(("Set", "Ideographs", "Drawn by FreeLang"), [(name, NUMBER(count), NUMBER(drawn))
                                                             for name, count, drawn in found["han_sets"]])
    out += ["", "Writings in Han characters, and scripts derived from them:", ""]
    out += table(("Writing", "Decision", "What and why"), HAN_WRITINGS)
    out += ["", "Unihan's sources and fields left as they are:", ""]
    out += table(("Unihan", "Ideographs", "Why not a set"), [(label, count, why) for label, count, why in found["unihan_left"]])
    out += ["", "## Unicode blocks", "",
            "The blocks whose characters no character set holds whole and no script owns whole (the others are "
            "either a set, under its group, or a script's, under *Scripts (Unicode)*). Private-use and surrogate "
            "blocks hold no characters.", ""]
    out += table(("Block", "Assigned", "Held by nothing", "Why"), [(name, NUMBER(count), NUMBER(rest), why)
                                                                   for name, count, rest, why in found["blocks"]])
    out += ["", "## Sequences", "",
            "Font Check reads a font's character map and the anchors that join a letter and its marks. A sequence "
            "that a font draws through its layout (a ligature, a contextual form, a variation sequence in its "
            "cmap's format 14) is not checked: that would need shaping, which Font Check does not do. An "
            "orthography's letter-and-mark clusters are checked, as before.", ""]
    out += ["- **Named sequences** (*NamedSequences.txt*), by script: " + ", ".join(
        "%s %d" % item for item in found["named"]) + ". The Latin ones are letters with marks, checked where an "
        "orthography lists them; the Tamil, Khmer, and other Indic ones are syllables a font forms by shaping."]
    out += ["- **Standardized variation sequences** (*StandardizedVariants.txt*), by script of the base: " + ", ".join(
        "%s %d" % item for item in found["variants"]) + "."]
    out += ["- **Emoji**: %s emoji variation sequences; the sequences " % NUMBER(found["emoji_variation"]) + ", ".join(
        "%s %s" % (kind.replace("_", " "), NUMBER(count)) for kind, count in found["emoji_sequences"]) +
        ". Of the %s characters with the Emoji property, %s are in a character set and FreeLang draws %s." % tuple(
            NUMBER(value) for value in found["emoji_characters"])]
    out += ["- **Ideographic variation sequences** (the IVD of 2025-07-14), by collection: " + ", ".join(
        "%s %s" % (name, NUMBER(count)) for name, count in found["ivd"]) + "."]
    out += ["", "## Shaping", "",
            "Font Check checks characters, not how a font shapes them: the %s characters that join (*ArabicShaping.txt*: "
            "Arabic, Syriac, N'Ko, Mandaic, Manichaean, and others) and the %s characters an Indic syllable is built "
            "of (*IndicSyllabicCategory.txt*) are checked one by one, and their contextual forms, conjuncts, and "
            "reordering are a font's layout, which only shaping can test." % (NUMBER(found["joining"]), NUMBER(found["syllabic"])), ""]
    out += ["## CLDR", "",
            "The orthographies take each locale's main and auxiliary exemplars. CLDR 49 also gives punctuation "
            "exemplars in %d locale files and number exemplars in %d, which no language's row asks for (a font "
            "for a language would need its quotation marks), and %d regional or variant locale files are not "
            "read. CLDR's keyboards and its seed locales are not in the pinned archive." % tuple(found["cldr"]), ""]
    out += ["## What FreeLang draws as pixels, and what it cannot draw", "",
            "GNU Unifont draws, as a 16 by 16 grid of pixels, the characters no outline font under a license "
            "FreeLang can take has: " + "; ".join("%s, %s characters (%s)" % (family, NUMBER(len(codes_of(codes))), codes)
                                                  for family, codes in found["pixels"]) +
            ". Until 2026-11-14 it drew 133, of which Plangothic P2 now draws 119 as outlines. No source at all has %s "
            "characters: %s: the signs NewGardiner leaves out as non-core (unverified, its maker says). Tangut's "
            "additions of Unicode 16 and 17 had none until Plangothic P2." % (
                NUMBER(sum(count for _, count in found["not_drawn"])),
                ", ".join("%s %s" % (block, NUMBER(count)) for block, count in found["not_drawn"]) or "none"), ""]
    out += ["## Fonts to consider for what FreeLang cannot draw", "",
            "Fonts a designer working on these characters can install beside FreeLang. They are not part of "
            "FreeLang and are not distributed with FreeLab; each license was read from the font's own files.", ""]
    out += table(("Font", "Maker", "License", "Where", "What it draws that FreeLang does not", "Caution"), RESOURCES)
    out += ["", "## Fonts looked at again", "",
            "The fonts the build left out, or that earlier work dismissed, read again on 2026-11-14.", ""]
    out += table(("Font", "Now", "Why"), RECONSIDERED)
    return "\n".join(out) + "\n"


def known(found):
    """What Font Check could name when a search finds no language or set: [name, other names, why]."""
    entries = [[writing, [], why] for writing, decision, why in HAN_WRITINGS if decision == "acknowledged"]
    entries += [["Emoji sequences", ["ZWJ sequences", "flags", "keycaps", "skin tones"],
                 "a font draws them through its layout (ligatures), which Font Check does not shape"],
                ["Ideographic variation sequences", ["IVD", "variation selectors"],
                 "a font maps them in its cmap's format 14, which Font Check does not read"],
                ["Standardized variation sequences", ["variation selectors"],
                 "a font maps them in its cmap's format 14, which Font Check does not read"]]
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", required=True, help="character_sets.py's folder of pinned sources")
    parser.add_argument("--check", action="store_true", help="write nothing: exit 1 when the files differ")
    args = parser.parse_args()
    args.download = os.path.normpath(args.download)  # (a trailing slash would put CLDR's folder inside it)
    files = character_sets.download(args.download)
    for name, (url, digest) in EXTRA_SOURCES.items():
        path = os.path.join(args.download, name)
        if not os.path.isfile(path):
            character_sets.download_one(url, path)
        if character_sets.sha256_of(path) != digest:
            raise SystemExit("%s: SHA-256 %s, expected %s" % (path, character_sets.sha256_of(path), digest))
    found = gather(files, args.download)
    doc = page(found)
    data = json.dumps(collections.OrderedDict((
        ("about", "Written by checks/train/coverage_gaps.py: what Font Check knows of and does not check "
                  "(known: [name, other names, why]), and fonts to consider for what FreeLang cannot draw "
                  "(resources: [font, maker, license, page, what, caution, the ids of the sets and scripts it is "
                  "for]); docs/COVERAGE-GAPS.md says more."),
        ("known", known(found)),
        ("resources", [list(row) + [RESOURCE_FOR.get(row[0], [])] for row in RESOURCES]),
    )), ensure_ascii=True, separators=(",", ":")) + "\n"
    if args.check:
        stale = [path for path, text in ((DOC_FILE, doc), (JSON_FILE, data))
                 if not os.path.isfile(path) or open(path, encoding="utf-8", newline="").read() != text]
        if stale:
            print("stale: %s (run without --check)" % ", ".join(os.path.relpath(path, REPO) for path in stale))
            return 1
        print("up to date")
        return 0
    for path, text in ((DOC_FILE, doc), (JSON_FILE, data)):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print("%s and %s written" % (os.path.relpath(DOC_FILE, REPO), os.path.relpath(JSON_FILE, REPO)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
