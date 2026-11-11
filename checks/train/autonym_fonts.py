"""Build Font Check's autonym font (checks/autonym_fonts/FreeLabAutonyms.ttf): the characters of the
languages' autonyms that FontLab's Qt cannot draw from the fonts installed on this computer, taken from
Noto fonts (SIL Open Font License 1.1), subset, merged, and renamed "FreeLab Autonyms".

Font Check lists languages as "Name (autonym)" from checks/language_coverage.json. Qt 5 on Windows
draws a character its font lacks from a fallback font, but it does not search every installed font:
it tries the dialog's font, the families it always tries (Arial, MS UI Gothic, Gulim, SimSun, PMingLiU,
Arial Unicode MS, Segoe UI Emoji, Segoe UI Symbol, and the UI fonts), then the fonts declaring the writing
system of the character's script (OS/2 Unicode ranges). Scripts Qt has no writing system for
(Canadian syllabics, Tifinagh, Vai, Tai Viet, Tai Tham, Ethiopic, Cherokee, ...) fall back on every
family in turn, up to 255 of them, and on a computer with many fonts the one that has the character
is often past that: those autonyms showed as boxes although Windows has Ebrima and Gadugi. So a
character counts as drawn when one of the always-tried families has it, or when its script has a Qt
writing system and an installed static font that has it declares that writing system; every other
autonym character goes in the bundled font, which Font Check puts first among the fallbacks.

    python checks/train/autonym_fonts.py [--cache <folder>] [--fresh] [--dry-run]

Python 3 with fontTools (uharfbuzz, when present, checks that the merged font shapes the autonyms as
the source fonts do). The Noto fonts come from notofonts.github.io at a pinned commit, over HTTPS,
into the cache folder (default %LOCALAPPDATA%\\FreeLab\\corpus\\autonym-sources), outside the
repository; each one's name table must declare the SIL Open Font License, and the folder's license
must be the OFL with no Reserved Font Name. The characters needed are kept in autonym_fonts.json
("required"), so a later run on another computer adds to them rather than dropping any (--fresh
starts again from this computer's fonts alone).
"""

import argparse
import collections
import glob
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request

from fontTools import subset
from fontTools import unicodedata as ucd
from fontTools.merge import Merger
from fontTools.ttLib import TTCollection, TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
LANGUAGES_FILE = os.path.join(CHECKS, "language_coverage.json")
OUT_DIR = os.path.join(CHECKS, "autonym_fonts")
FONT_FILE, LICENSE_FILE, INFO_FILE = "FreeLabAutonyms.ttf", "FreeLabAutonyms_LICENSE", "autonym_fonts.json"
FAMILY, POSTSCRIPT_NAME = "FreeLab Autonyms", "FreeLabAutonyms-Regular"
VERSION = "1.000"
NOTO_REPO = "notofonts/notofonts.github.io"
NOTO_COMMIT = "4cf78353cd1668040ba8efa13029cd910fcdf9e2"  # main on 2026-11-09
RAW_URL = "https://raw.githubusercontent.com/%s/%s/%s"
NOTO_LICENSE = "fonts/LICENSE"  # the OFL 1.1 every font in the folder is under, with no Reserved Font Name
CACHE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus", "autonym-sources")
FONT_DIRS = tuple(os.path.join(base, *parts) for base, parts in (
    (os.environ.get("WINDIR") or os.environ.get("SystemRoot"), ("Fonts",)),
    (os.environ.get("LOCALAPPDATA"), ("Microsoft", "Windows", "Fonts"))) if base)

# The families Qt 5 on Windows always tries for a character the widget's font lacks: the UI fonts
# (the dialog's own, in English and Japanese Windows), the style hint's, and QWindowsFontDatabase's
# extraTryFontsForFamily list (Arial, MS UI Gothic, Gulim, SimSun, PMingLiU, Arial Unicode MS, Segoe UI
# Emoji, Segoe UI Symbol; Yu Gothic UI first on Japanese Windows).
ALWAYS_TRIED = ("Segoe UI", "Tahoma", "Microsoft Sans Serif", "MS Shell Dlg", "Yu Gothic UI", "Meiryo UI",
                "Arial", "MS UI Gothic", "Gulim", "SimSun", "PMingLiU", "Arial Unicode MS",
                "Segoe UI Emoji", "Segoe UI Symbol")
# The scripts Qt 5 has a writing system for, and the OS/2 ulUnicodeRange bit it reads as a font
# supporting it (qplatformfontdatabase.cpp, requiredUnicodeBits); CJK as the Unicode ranges say.
WRITING_SYSTEM_BITS = {
    "Latn": 0, "Grek": 7, "Cyrl": 9, "Armn": 10, "Hebr": 11, "Arab": 13, "Nkoo": 14, "Deva": 15, "Beng": 16,
    "Guru": 17, "Gujr": 18, "Orya": 19, "Taml": 20, "Telu": 21, "Knda": 22, "Mlym": 23, "Thai": 24, "Laoo": 25,
    "Geor": 26, "Hang": 56, "Hani": 59, "Hira": 49, "Tibt": 70, "Syrc": 71, "Thaa": 72, "Sinh": 73, "Mymr": 74,
    "Ogam": 78, "Runr": 79, "Khmr": 80,
}
NOT_A_SCRIPT = ("Zyyy", "Zinh", "Zzzz")  # common and inherited characters take their neighbors' script
LAST_RESORT = ("last resort",)  # fonts that map everything to a placeholder draw nothing readable

# The Noto family (notofonts.github.io/fonts/<family>/unhinted/ttf/<family>-Regular.ttf) for each script.
SOURCES = {
    "Latn": "NotoSans", "Grek": "NotoSans", "Cyrl": "NotoSans", "Armn": "NotoSansArmenian",
    "Hebr": "NotoSansHebrew", "Arab": "NotoSansArabic", "Syrc": "NotoSansSyriac", "Thaa": "NotoSansThaana",
    "Nkoo": "NotoSansNKo", "Deva": "NotoSansDevanagari", "Beng": "NotoSansBengali", "Guru": "NotoSansGurmukhi",
    "Gujr": "NotoSansGujarati", "Orya": "NotoSansOriya", "Taml": "NotoSansTamil", "Telu": "NotoSansTelugu",
    "Knda": "NotoSansKannada", "Mlym": "NotoSansMalayalam", "Sinh": "NotoSansSinhala", "Thai": "NotoSansThai",
    "Laoo": "NotoSansLao", "Tibt": "NotoSerifTibetan", "Mymr": "NotoSansMyanmar", "Geor": "NotoSansGeorgian",
    "Khmr": "NotoSansKhmer", "Ethi": "NotoSansEthiopic", "Cher": "NotoSansCherokee",
    "Cans": "NotoSansCanadianAboriginal", "Tfng": "NotoSansTifinagh", "Vaii": "NotoSansVai",
    "Tavt": "NotoSansTaiViet", "Lana": "NotoSansTaiTham", "Bamu": "NotoSansBamum", "Bugi": "NotoSansBuginese",
    "Hano": "NotoSansHanunoo", "Kali": "NotoSansKayahLi", "Yiii": "NotoSansYi", "Avst": "NotoSansAvestan",
    "Egyp": "NotoSansEgyptianHieroglyphs", "Xsux": "NotoSansCuneiform", "Ogam": "NotoSansOgham",
    "Runr": "NotoSansRunic", "Copt": "NotoSansCoptic", "Goth": "NotoSansGothic", "Mong": "NotoSansMongolian",
    "Olck": "NotoSansOlChiki", "Adlm": "NotoSansAdlam", "Talu": "NotoSansNewTaiLue", "Tale": "NotoSansTaiLe",
    "Bali": "NotoSansBalinese", "Java": "NotoSansJavanese", "Sund": "NotoSansSundanese",
}
OPEN_FONT_LICENSE = ("open font license", "scripts.sil.org/ofl", "openfontlicense")  # as kerning/train/dataset.py
PROPRIETARY = ("microsoft supplied font", "any other use is prohibited", "end user license agreement")


def say(text):
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.flush()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:  # LF, as the repository keeps
        handle.write(text)


# ---------------------------------------------------------------------------
# The autonyms' characters and the installed fonts
# ---------------------------------------------------------------------------

def autonym_characters(path=LANGUAGES_FILE):
    """{code point: {scripts of the runs it is in}} for every character of the autonyms, a common or
    inherited character (space, punctuation, a combining mark) given the script of the run around it,
    as Qt itemizes text; and {code point: [languages]}."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    scripts, languages = collections.defaultdict(set), collections.defaultdict(list)
    for row in data["orthographies"]:
        name, autonym = row[1], row[2]
        if not autonym:
            continue
        own = [ucd.script(c) for c in autonym]
        for at, character in enumerate(autonym):
            script = own[at]
            if script in NOT_A_SCRIPT:
                before = [s for s in own[:at] if s not in NOT_A_SCRIPT]
                after = [s for s in own[at + 1:] if s not in NOT_A_SCRIPT]
                script = before[-1] if before else (after[0] if after else "Zyyy")
            scripts[ord(character)].add(script)
            if name not in languages[ord(character)]:
                languages[ord(character)].append(name)
    return scripts, languages


InstalledFont = collections.namedtuple("InstalledFont", "path family codes ranges variable")


def unicode_ranges(font):
    os2 = font["OS/2"] if "OS/2" in font else None
    if os2 is None:
        return set()
    bits = set()
    for word, value in enumerate((os2.ulUnicodeRange1, os2.ulUnicodeRange2, os2.ulUnicodeRange3, os2.ulUnicodeRange4)):
        bits.update(word * 32 + bit for bit in range(32) if value >> bit & 1)
    return bits


def installed_fonts(folders=FONT_DIRS):
    """The fonts installed (Windows' and the user's): family, code points, Unicode range bits, and
    whether variable. Symbol-encoded cmaps and Last Resort fonts map no readable character."""
    found = []
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(folder, "*"))):
            lower = path.lower()
            if not lower.endswith((".ttf", ".otf", ".ttc", ".otc")):
                continue
            try:
                fonts = TTCollection(path, lazy=True).fonts if lower.endswith(("c",)) else [TTFont(path, lazy=True)]
            except Exception:
                continue
            for font in fonts:
                try:
                    family = str(font["name"].getDebugName(1) or "")
                    if any(word in family.lower() for word in LAST_RESORT):
                        continue
                    codes = set()
                    for table in font["cmap"].tables:
                        if table.isUnicode() and not (table.platformID == 3 and table.platEncID == 0):
                            codes.update(table.cmap)
                    found.append(InstalledFont(path, family, codes, unicode_ranges(font), "fvar" in font))
                except Exception:
                    continue
    return found


def drawn_by_system(code, scripts, fonts):
    """Whether Qt draws the character from an installed font (see the module's note), and from which."""
    always = set(f.lower() for f in ALWAYS_TRIED)
    for font in fonts:
        if code in font.codes and font.family.lower() in always:
            return font.family
    for script in scripts:
        bit = WRITING_SYSTEM_BITS.get(script)
        if bit is None:
            return None  # one run in a script Qt has no writing system for is enough to miss it
    for font in fonts:
        if code in font.codes and not font.variable and all(WRITING_SYSTEM_BITS[s] in font.ranges for s in scripts):
            return font.family
    return None


def required_characters(scripts, fonts):
    return sorted(code for code in scripts if drawn_by_system(code, scripts[code], fonts) is None)


# ---------------------------------------------------------------------------
# The Noto fonts
# ---------------------------------------------------------------------------

def license_of(font):
    """"OFL" when the font's name table declares the SIL Open Font License (as kerning/train/dataset.py
    reads it), else None."""
    text = " ".join(str(r) for r in font["name"].names if r.nameID in (13, 14)).lower()
    if any(marker in text for marker in PROPRIETARY):
        return None
    return "OFL" if any(marker in text for marker in OPEN_FONT_LICENSE) else None


def fetch(relative, folder):
    """A file of notofonts.github.io at the pinned commit, downloaded once into folder."""
    path = os.path.join(folder, NOTO_COMMIT[:12], *relative.split("/"))
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        url = RAW_URL % (NOTO_REPO, NOTO_COMMIT, relative)
        say("downloading %s" % url)
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        with open(path + ".part", "wb") as handle:
            handle.write(data)
        os.replace(path + ".part", path)
    return path


def noto_license(folder):
    path = fetch(NOTO_LICENSE, folder)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if "SIL OPEN FONT LICENSE Version 1.1" not in text or "with Reserved Font Name" in text:
        raise SystemExit("%s is not the SIL Open Font License 1.1 without a Reserved Font Name" % NOTO_LICENSE)
    return text


def source_font(family, folder):
    path = fetch("fonts/%s/unhinted/ttf/%s-Regular.ttf" % (family, family), folder)
    font = TTFont(path)
    if license_of(font) != "OFL":
        raise SystemExit("%s does not declare the SIL Open Font License in its name table" % path)
    for table in ("fvar", "COLR", "CFF2"):
        if table in font:
            raise SystemExit("%s has a %s table: FontLab's Qt needs a static TrueType font" % (path, table))
    return path, font


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# ---------------------------------------------------------------------------
# Building the font
# ---------------------------------------------------------------------------

def plan(required, scripts, folder):
    """{Noto family: [code points it supplies]}: each character from its script's font, or from the
    first other source that has it; and the characters no source has."""
    by_family, unplaced = collections.OrderedDict(), []
    opened = {}

    def font_of(family):
        if family not in opened:
            try:
                opened[family] = source_font(family, folder)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                say("cannot use %s: %s" % (family, exc))
                opened[family] = None
        return opened[family]

    for code in required:
        candidates = [SOURCES[s] for s in sorted(scripts.get(code, ())) if s in SOURCES]
        candidates += [f for f in opened if f not in candidates and opened[f] is not None]
        for family in candidates:
            found = font_of(family)
            if found is not None and code in found[1].getBestCmap():
                by_family.setdefault(family, []).append(code)
                break
        else:
            unplaced.append(code)
    return by_family, unplaced, dict((f, v) for f, v in opened.items() if v is not None)


def subset_font(path, codes, out, space=False):
    options = subset.Options()
    options.layout_features = ["*"]  # the shaping (Tai Tham's reordering, marks' positions) kept
    options.hinting = False
    options.notdef_outline = True
    options.glyph_names = False
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.drop_tables += ["DSIG", "STAT", "meta", "vhea", "vmtx", "gasp"]  # (no vertical text; merging needs the same tables)
    font = subset.load_font(path, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(set(codes) | ({0x20} if space else set())))
    subsetter.subset(font)
    font.save(out)
    return out


def rename(font, copyrights, stamp):
    """The merged font named FreeLab Autonyms, so it never stands for an installed Noto font."""
    name = font["name"]
    name.names = []
    records = {
        0: "; ".join(copyrights),
        1: FAMILY, 2: "Regular", 3: "%s;%s" % (VERSION, POSTSCRIPT_NAME), 4: FAMILY,
        5: "Version %s; subset of Noto fonts (notofonts.github.io %s)" % (VERSION, NOTO_COMMIT[:7]),
        6: POSTSCRIPT_NAME,
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is "
            "available with a FAQ at: https://openfontlicense.org",
        14: "https://openfontlicense.org",
    }
    for name_id, text in sorted(records.items()):
        name.setName(text, name_id, 3, 1, 0x409)
        name.setName(text, name_id, 1, 0, 0)
    font["head"].fontRevision = float(VERSION)
    font.recalcTimestamp = False  # (the same bytes from the same sources: dated as the latest source, not the build)
    font["head"].created = font["head"].modified = stamp
    font["OS/2"].achVendID = "NONE"
    font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0b1100001) | 0b1000000  # Regular only
    font["head"].macStyle = 0
    font["post"].formatType = 3.0  # no glyph names: smaller
    font["post"].extraNames, font["post"].mapping = [], {}
    font["OS/2"].recalcUnicodeRanges(font)
    font["OS/2"].ulCodePageRange1, font["OS/2"].ulCodePageRange2 = 1, 0  # Latin 1 (its space): no CJK code page claimed


def merge(paths, out, copyrights, stamp):
    """One font from the subsets (one per source font) when fontTools can merge them; else None."""
    try:
        merged = Merger().merge(paths)
    except Exception as exc:
        say("merging failed (%s): one font per source instead" % exc)
        return None
    rename(merged, copyrights, stamp)
    merged.save(out)
    return out


def shaping_differences(sources, merged_path, texts):
    """The texts the merged font shapes otherwise than its source font does (uharfbuzz), or None
    without uharfbuzz."""
    try:
        import uharfbuzz as hb
    except ImportError:
        return None

    def shape(path, text):
        with open(path, "rb") as handle:
            face = hb.Face(handle.read())
        font = hb.Font(face)
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        return [(p.x_advance, p.x_offset, p.y_offset) for p in buf.glyph_positions], \
            [i.cluster for i in buf.glyph_infos], [i.codepoint == 0 for i in buf.glyph_infos]

    different = []
    for family, text in texts:
        if shape(sources[family], text) != shape(merged_path, text):
            different.append((family, text))
    return different


def build(args):
    scripts, languages = autonym_characters()
    say("%d autonym characters" % len(scripts))
    fonts = installed_fonts()
    say("%d installed fonts read" % len(fonts))
    required = set(required_characters(scripts, fonts))
    info_path = os.path.join(OUT_DIR, INFO_FILE)
    if not args.fresh and os.path.isfile(info_path):
        with open(info_path, encoding="utf-8") as handle:
            required |= set(int(c, 16) for c in json.load(handle).get("required", "").split())
    required = sorted(c for c in required if c in scripts)
    say("%d characters Qt cannot draw from the installed fonts" % len(required))
    if args.dry_run:
        for code in required:
            say("U+%04X %s %s" % (code, ",".join(sorted(scripts[code])), ", ".join(languages[code][:3])))
        return 0
    os.makedirs(args.cache, exist_ok=True)
    license_text = noto_license(args.cache)
    by_family, unplaced, opened = plan(required, scripts, args.cache)
    work = os.path.join(args.cache, "work")
    os.makedirs(work, exist_ok=True)
    subsets, copyrights, sources = [], [], []
    for family, codes in by_family.items():
        path, font = opened[family]
        out = subset_font(path, codes, os.path.join(work, family + "-subset.ttf"), space=not subsets)  # (one space)
        subsets.append(out)
        copyright = str(font["name"].getDebugName(0) or "").strip()
        if copyright and copyright not in copyrights:
            copyrights.append(copyright)
        used_scripts = sorted(set(s for c in codes for s in scripts[c]))
        sources.append(collections.OrderedDict((
            ("family", str(font["name"].getDebugName(1))),
            ("file", "fonts/%s/unhinted/ttf/%s" % (family, os.path.basename(path))),
            ("version", str(font["name"].getDebugName(5))),
            ("copyright", copyright),
            ("sha256", sha256(path)),
            ("scripts", used_scripts),
            ("characters", "".join(chr(c) for c in codes)),
            ("code_points", " ".join("%04X" % c for c in codes)),
        )))
    upms = set(TTFont(p, lazy=True)["head"].unitsPerEm for p in subsets)
    if len(upms) > 1:
        from fontTools.ttLib.scaleUpem import scale_upem
        for p in subsets:
            font = TTFont(p)
            if font["head"].unitsPerEm != 1000:
                scale_upem(font, 1000)
                font.save(p)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, FONT_FILE)
    files = []
    stamp = max(opened[f][1]["head"].modified for f in by_family)
    if merge(subsets, out, copyrights, stamp):
        files.append(FONT_FILE)
    else:
        raise SystemExit("fontTools could not merge the subsets; see the message above")
    merged = TTFont(out)
    cmap = merged.getBestCmap()
    missing = [c for c in required if c not in cmap and c not in unplaced]
    if missing:
        raise SystemExit("the merged font lacks %s" % " ".join("U+%04X" % c for c in missing))
    texts = []
    for family, codes in by_family.items():
        wanted = set(codes)
        for row_text in sorted(set(t for c in codes for t in autonyms_with(c))):
            if any(ord(ch) in wanted for ch in row_text):
                texts.append((family, row_text))
    different = shaping_differences(dict((f, opened[f][0]) for f in by_family), out,
                                     [(f, word) for f, t in texts for word in run_of(t, set(by_family[f])).split()])
    if different:
        say("shaped otherwise by the merged font: %s" % ", ".join(t for _, t in different))
    write_text(os.path.join(OUT_DIR, LICENSE_FILE), license_notice(sources, license_text))
    size = os.path.getsize(out)
    info = collections.OrderedDict((
        ("family", FAMILY),
        ("file", FONT_FILE),
        ("license", "SIL Open Font License 1.1 (%s)" % LICENSE_FILE),
        ("made_by", "checks/train/autonym_fonts.py"),
        ("source", "https://github.com/%s at %s (fonts/<family>/unhinted/ttf)" % (NOTO_REPO, NOTO_COMMIT)),
        ("why", "the autonym characters FontLab's Qt 5 does not draw from the installed Windows fonts: "
                "none of the families it always tries has them, and their script has no Qt writing "
                "system (or no installed static font declaring it has them)"),
        ("size", size),
        ("shaping_checked", different is not None),
        ("required", " ".join("%04X" % c for c in required)),  # (tests/autonym_tests.py checks the font has each)
        ("not_covered", " ".join("%04X" % c for c in unplaced)),
        ("sources", sources),
    ))
    write_text(info_path, json.dumps(info, ensure_ascii=False, indent=1) + "\n")
    say("%s: %d bytes, %d glyphs, from %d fonts" % (FONT_FILE, size, len(merged.getGlyphOrder()), len(sources)))
    if unplaced:
        say("no source has: %s" % " ".join("U+%04X" % c for c in unplaced))
    return 0


_AUTONYMS = []


def autonyms_with(code):
    if not _AUTONYMS:
        with open(LANGUAGES_FILE, encoding="utf-8") as handle:
            _AUTONYMS.extend(sorted(set(row[2] for row in json.load(handle)["orthographies"] if row[2])))
    return [a for a in _AUTONYMS if chr(code) in a]


def run_of(text, codes):
    """The part of an autonym the bundled font draws: from its first bundled character to its last
    (compared word by word: the merged font's space is another source's, and Qt takes the dialog font's)."""
    at = [i for i, ch in enumerate(text) if ord(ch) in codes]
    return text[at[0]:at[-1] + 1]


def license_notice(sources, license_text):
    lines = ["%s (%s) is made of subsets of these fonts, merged and renamed by checks/train/autonym_fonts.py:" % (FONT_FILE, FAMILY), ""]
    for source in sources:
        lines.append("- %s, %s: %s" % (source["family"], source["version"], source["copyright"]))
    lines += ["", "They come from https://github.com/%s (commit %s), and are licensed under the SIL Open Font" % (NOTO_REPO, NOTO_COMMIT),
              "License, Version 1.1, as is %s. Their license, as that repository ships it, follows." % FONT_FILE, "", ""]
    return "\n".join(lines) + license_text.replace("\r\n", "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache", default=CACHE_DIR, help="where the Noto fonts are downloaded (outside the repository)")
    parser.add_argument("--fresh", action="store_true", help="ignore the characters autonym_fonts.json already lists")
    parser.add_argument("--dry-run", action="store_true", help="list the characters needed, build nothing")
    return build(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
