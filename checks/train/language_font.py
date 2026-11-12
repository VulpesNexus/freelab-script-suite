"""Build Font Check's language list font (checks/language_font/FreeLabLanguages.ttf): every character
the Coverage tab's languages list shows, from Noto fonts (SIL Open Font License 1.1), subset, merged,
and renamed "FreeLab Languages".

The list shows each language as "Name (autonym)" under its script's heading ("Cyrillic (92)"), and
within reach, the characters it misses ("ß", "Ǎ ǎ +1", a mark on a dotted circle). Drawn in the dialog's
font, Qt 5 took each character the font lacks from another font, and some lists looked uneven
(Cyrillic autonyms spaced wide, rare scripts as boxes). With this one font as the list's family, every
character comes from the same design: the language names and autonyms, the script names, the digits
and punctuation, and the characters of every orthography's base, auxiliary, and mark lists (the
Missing column), except the ideographs and Hangul syllables that only that column can show (over
14,000: they would make the font several megabytes; the system's CJK fonts draw those).

    python checks/train/language_font.py [--cache <folder>] [--dry-run]

Python 3 with fontTools (uharfbuzz, when present, checks that the merged font shapes the texts as the
source fonts do). The fonts come over HTTPS into the cache folder (default
%LOCALAPPDATA%\\FreeLab\\corpus\\language-font-sources), outside the repository: Noto's static fonts
from notofonts.github.io, and Noto Sans JP, KR, SC, and TC from google/fonts (variable, instanced at
Regular), each at a pinned commit. Each font's name table must declare the SIL Open Font License, and
its license must reserve no name FreeLab Languages uses. Run it through the machine guard: the CJK
fonts are large.
"""

import argparse
import collections
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

from fontTools import subset
from fontTools import unicodedata as ucd
from fontTools.merge import Merger
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
LANGUAGES_FILE = os.path.join(CHECKS, "language_coverage.json")
OUT_DIR = os.path.join(CHECKS, "language_font")
FONT_FILE, LICENSE_FILE, INFO_FILE = "FreeLabLanguages.ttf", "FreeLabLanguages_LICENSE", "language_font.json"
FAMILY, POSTSCRIPT_NAME = "FreeLab Languages", "FreeLabLanguages-Regular"
VERSION = "1.000"
RAW_URL = "https://raw.githubusercontent.com/%s/%s/%s"
NOTO = ("notofonts/notofonts.github.io", "4cf78353cd1668040ba8efa13029cd910fcdf9e2")  # main on 2026-11-09
GOOGLE = ("google/fonts", "c30b221beb0c1da59d563feb91ec8656a1fa972a")  # main on 2026-11-11
CACHE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus", "language-font-sources")

# What the list shows besides the data: the column headings, a heading's count in parentheses, "+N"
# past the missing characters shown, a mark on a dotted circle, and Qt's ellipsis for elided text; the
# rest of ASCII and common punctuation for good measure.
UI_TEXT = (u"".join(chr(c) for c in range(0x20, 0x7F)) + u"\N{NO-BREAK SPACE}\N{MIDDLE DOT}\N{HORIZONTAL ELLIPSIS}"
           u"\N{DOTTED CIRCLE}\N{EN DASH}\N{EM DASH}\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
           u"\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}\N{BULLET}")
# Scripts whose characters are left to the system when only the Missing column can show them (a
# language within reach of a font): Chinese's and Japanese's ideographs, Korean's 11,172 syllables, and
# the cuneiform signs and hieroglyphs of Akkadian, Sumerian, and Ancient Egyptian (historical languages,
# listed only on request): about 1.4 MB of outlines. Their autonyms' characters are bundled.
MISSING_ONLY_LEFT_OUT = ("Hani", "Xsux", "Egyp")
HANGUL_SYLLABLES = (0xAC00, 0xD7A3)  # (Korean's jamo are bundled: a hundred of them)
NOT_A_SCRIPT = ("Zyyy", "Zinh", "Zzzz")

# The font of each script: Noto's static fonts (notofonts.github.io/fonts/<family>/unhinted/ttf/
# <family>-Regular.ttf), or google/fonts' CJK ones (ofl/<folder>/<file>), first that has the character.
STATIC = {
    "Latn": "NotoSans", "Grek": "NotoSans", "Cyrl": "NotoSans", "Armn": "NotoSansArmenian",
    "Hebr": "NotoSansHebrew", "Arab": "NotoSansArabic", "Syrc": "NotoSansSyriac", "Thaa": "NotoSansThaana",
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
}
CJK = {
    "NotoSansJP": ("notosansjp", "NotoSansJP[wght].ttf"), "NotoSansKR": ("notosanskr", "NotoSansKR[wght].ttf"),
    "NotoSansSC": ("notosanssc", "NotoSansSC[wght].ttf"), "NotoSansTC": ("notosanstc", "NotoSansTC[wght].ttf"),
}
CJK_ORDER = {"Hani": ("NotoSansJP", "NotoSansSC", "NotoSansTC", "NotoSansKR"), "Hira": ("NotoSansJP",),
             "Kana": ("NotoSansJP",), "Hang": ("NotoSansKR",), "Bopo": ("NotoSansTC",)}
GENERAL = ("NotoSans", "NotoSansSymbols", "NotoSansSymbols2")  # for punctuation no script's font has
FIRST = "NotoSans"  # merged first: its space, .notdef, and Latin set the font's defaults
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


# ---------------------------------------------------------------------------
# What the list shows
# ---------------------------------------------------------------------------

def specific_script(text):
    """The script most of a text's own characters are in (None for punctuation alone)."""
    found = collections.Counter(ucd.script(c) for c in text)
    for script, _ in found.most_common():
        if script not in NOT_A_SCRIPT:
            return script
    return None


def list_characters(path=LANGUAGES_FILE):
    """{code point: Counter of scripts} for every character the list can show, each common or inherited
    character voting for the script of the text it is in (its marks shaped by that script's font), and
    {code point: True} for those only the Missing column shows."""
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    texts = data["texts"]
    votes, missing_only = collections.defaultdict(collections.Counter), {}
    shown = []
    for iso, name, autonym, script, _, _, _, base, auxiliary, marks in data["orthographies"]:
        shown += [name, autonym, script]
        for text in (texts[base], texts[auxiliary], marks):
            for item in text.split():
                owner = specific_script(text) or "Latn"
                for character in item:
                    own = ucd.script(character)
                    votes[ord(character)][owner if own in NOT_A_SCRIPT else own] += 1
                    missing_only.setdefault(ord(character), True)
    for text in shown + [UI_TEXT]:
        owner = specific_script(text) or "Latn"
        for character in text:
            own = ucd.script(character)
            votes[ord(character)][owner if own in NOT_A_SCRIPT else own] += 1
            missing_only[ord(character)] = False
    return votes, missing_only


def wanted_characters(votes, missing_only):
    """The characters to bundle, and those left to the system (Missing column only, ideographs and
    Hangul syllables)."""
    wanted, left = [], []
    for code in sorted(votes):
        if missing_only[code] and (ucd.script(chr(code)) in MISSING_ONLY_LEFT_OUT
                                   or HANGUL_SYLLABLES[0] <= code <= HANGUL_SYLLABLES[1]):
            left.append(code)
        else:
            wanted.append(code)
    return wanted, left


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


def reserved_names(text):
    """The Reserved Font Names an OFL notice declares ("with Reserved Font Name 'Source'")."""
    found = []
    for line in text.splitlines():
        lower = line.lower()
        if "reserved font name" in lower and "with reserved font name" in lower:
            tail = line[lower.index("with reserved font name") + len("with reserved font name"):]
            for part in tail.replace(" and ", ",").split(","):
                part = part.strip().strip(".").strip().strip("'\"\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}")
                if part:
                    found.append(part)
    return found


def checked_license(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read().replace("\r\n", "\n")
    if "SIL OPEN FONT LICENSE" not in text.upper() or "Version 1.1" not in text:
        raise SystemExit("%s is not the SIL Open Font License 1.1" % path)
    for name in reserved_names(text):
        if name.lower() in FAMILY.lower() or name.lower() in POSTSCRIPT_NAME.lower():
            raise SystemExit("%s reserves %r, which %s would use" % (path, name, FAMILY))
    return text


def source_font(family, folder):
    """(path, TTFont, license path) of a source font, its license checked."""
    if family in CJK:
        directory, name = CJK[family]
        path = fetch(GOOGLE, "ofl/%s/%s" % (directory, name), folder)
        license_path = fetch(GOOGLE, "ofl/%s/OFL.txt" % directory, folder)
    else:
        path = fetch(NOTO, "fonts/%s/unhinted/ttf/%s-Regular.ttf" % (family, family), folder)
        license_path = fetch(NOTO, "fonts/LICENSE", folder)
    checked_license(license_path)
    font = TTFont(path, lazy=True)
    if license_of(font) != "OFL":
        raise SystemExit("%s does not declare the SIL Open Font License in its name table" % path)
    for table in ("COLR", "CFF2", "CFF "):
        if table in font:
            raise SystemExit("%s has a %s table: the list font is plain TrueType" % (path, table))
    return path, font, license_path


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# ---------------------------------------------------------------------------
# Building the font
# ---------------------------------------------------------------------------

def candidates(code, votes):
    """The fonts to look in for a character: its scripts' (most voted first, then its script
    extensions'), then the general ones."""
    scripts = [s for s, _ in sorted(votes[code].items(), key=lambda kv: (-kv[1], kv[0]))]
    scripts += sorted(ucd.script_extension(chr(code)) - set(scripts))
    found = []
    for script in scripts:
        static = STATIC.get(script, ())
        for family in ((static,) if isinstance(static, str) else static) + CJK_ORDER.get(script, ()):
            if family not in found:
                found.append(family)
    return found + [f for f in GENERAL if f not in found]


def plan(wanted, votes, folder):
    """{Noto family: [code points it supplies]} (FIRST first), the characters no source has, and the
    sources opened."""
    by_family, unplaced, opened, cmaps = collections.OrderedDict(((FIRST, []),)), [], {}, {}

    def cmap_of(family):
        if family not in opened:
            try:
                opened[family] = source_font(family, folder)
                cmaps[family] = set(opened[family][1].getBestCmap())
            except (OSError, ValueError, urllib.error.URLError) as exc:
                say("cannot use %s: %s" % (family, exc))
                opened[family], cmaps[family] = None, set()
        return cmaps[family]

    for code in wanted:
        for family in candidates(code, votes):
            if code in cmap_of(family):
                by_family.setdefault(family, []).append(code)
                break
        else:
            unplaced.append(code)
    return by_family, unplaced, dict((f, v) for f, v in opened.items() if v is not None)


def subset_font(path, codes, out):
    """The font cut down to codes (their shaping kept), unhinted, static: a variable font instanced at
    Regular (weight 400)."""
    options = subset.Options()
    options.layout_features = ["*"]  # the shaping (conjuncts, reordering, marks' positions) kept
    options.hinting = False
    options.notdef_outline = True
    options.glyph_names = False
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.drop_tables += ["DSIG", "STAT", "meta", "vhea", "vmtx", "gasp", "VORG", "BASE", "JSTF", "MATH"]
    font = subset.load_font(path, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(codes))
    subsetter.subset(font)
    if "fvar" in font:
        from fontTools.varLib import instancer
        regular = dict((axis.axisTag, min(max(400, axis.minValue), axis.maxValue) if axis.axisTag == "wght"
                        else axis.defaultValue) for axis in font["fvar"].axes)  # (the CJK fonts' default is Thin)
        font = instancer.instantiateVariableFont(font, regular)
    font.save(out)
    return out


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


def set_names(font, copyrights, stamp):
    """Named FreeLab Languages, so it never stands for an installed Noto font."""
    name = font["name"]
    name.names = []
    records = {
        0: "; ".join(copyrights),
        1: FAMILY, 2: "Regular", 3: "%s;%s" % (VERSION, POSTSCRIPT_NAME), 4: FAMILY,
        5: "Version %s; subsets of Noto fonts" % VERSION,
        6: POSTSCRIPT_NAME,
        13: "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is "
            "available with a FAQ at: https://openfontlicense.org",
        14: "https://openfontlicense.org",
    }
    for name_id, text in sorted(records.items()):
        name.setName(text, name_id, 3, 1, 0x409)
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


def shown_texts():
    """The texts the list shows: "Name (autonym)", the script headings, and each character or
    letter-and-marks of the orthographies (with a dotted circle under a mark alone)."""
    with open(LANGUAGES_FILE, encoding="utf-8") as handle:
        data = json.load(handle)
    labels, items = set(), set()
    for iso, name, autonym, script, _, _, _, base, auxiliary, marks in data["orthographies"]:
        labels.add(u"%s (%s)" % (name, autonym) if autonym and autonym != name else name)
        labels.add(u"%s (92)" % script)
        for text in (data["texts"][base], data["texts"][auxiliary]):
            items.update(text.split())
        items.update(u"\N{DOTTED CIRCLE}" + m for m in marks)
    return sorted(labels), sorted(items)


def build(args):
    votes, missing_only = list_characters()
    wanted, left = wanted_characters(votes, missing_only)
    say("%d characters shown, %d bundled, %d left to the system (Missing column only)" % (
        len(votes), len(wanted), len(left)))
    if args.dry_run:
        print(collections.Counter(ucd.script(chr(c)) for c in wanted).most_common())
        return 0
    os.makedirs(args.cache, exist_ok=True)
    by_family, unplaced, opened = plan(wanted, votes, args.cache)
    work = os.path.join(args.cache, "work")
    os.makedirs(work, exist_ok=True)
    subsets, copyrights, sources, licenses = [], [], [], []
    supplied = {}
    for family, codes in by_family.items():
        path, font, license_path = opened[family]
        supplied[family] = set(codes) | ({0x20} if not subsets else set())  # (each character once: no duplicates
        # to resolve, which fontTools does through locl features that reached other scripts' text)
        out = subset_font(path, supplied[family], os.path.join(work, family + "-subset.ttf"))
        subsets.append(out)
        copyright = str(font["name"].getDebugName(0) or "").strip()
        if copyright and copyright not in copyrights:
            copyrights.append(copyright)
        if license_path not in licenses:
            licenses.append(license_path)
        sources.append(collections.OrderedDict((
            ("family", str(font["name"].getDebugName(16) or font["name"].getDebugName(1))),  # (not "Noto Sans JP Thin")
            ("file", "https://github.com/%s/blob/%s/" % (GOOGLE if family in CJK else NOTO)
             + ("ofl/%s/%s" % CJK[family] if family in CJK else "fonts/%s/unhinted/ttf/%s-Regular.ttf" % (family, family))),
            ("version", str(font["name"].getDebugName(5))),
            ("copyright", copyright),
            ("sha256", sha256(path)),
            ("scripts", sorted(set(ucd.script(chr(c)) for c in codes) - set(NOT_A_SCRIPT))),
            ("count", len(codes)),
            ("code_points", " ".join("%04X" % c for c in codes)),
        )))
        say("%s: %d characters, %d bytes" % (family, len(codes), os.path.getsize(out)))
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
    merged = Merger().merge(subsets)
    stamp = max(opened[f][1]["head"].modified for f in by_family)
    set_names(merged, copyrights, stamp)
    set_coverage(merged, set(ucd.script(chr(c)) for c in wanted))
    merged.save(out)
    labels, items = shown_texts()
    extent = ink_extent(TTFont(out), labels)
    if extent:
        top, bottom, worst = extent
        ascent, descent = set_line(merged, top, bottom)
        say("line: ascent %d, descent %d (highest: %s; lowest: %s)" % (ascent, descent, worst.get("top"), worst.get("bottom")))
        merged.save(out)
    merged = TTFont(out)
    cmap = merged.getBestCmap()
    missing = [c for c in wanted if c not in cmap and c not in unplaced]
    if missing:
        raise SystemExit("the merged font lacks %s" % " ".join("U+%04X" % c for c in missing))
    source_of = dict((c, f) for f, codes in by_family.items() for c in codes)
    runs = []
    for text in labels + items:
        for run in script_runs(text):
            owners = [source_of.get(ord(c)) for c in run if ucd.script(c) not in NOT_A_SCRIPT] or                 [source_of.get(ord(run[0]))]
            family = owners[0]
            if family is not None and all(ord(c) in supplied[family] for c in run):
                runs.append((family, run))
    different = shaping_differences(dict((f, os.path.join(work, f + "-subset.ttf")) for f in by_family), out, runs)
    if different:
        say("shaped otherwise by the merged font (%d): %s" % (len(different), ", ".join(t for _, t in different[:40])))
    left_set = set(left) | set(unplaced)
    boxes = notdef_texts(out, [t for t in labels + items if not any(ord(c) in left_set for c in t)])
    if boxes:
        say("drawn with a box (%d): %s" % (len(boxes), ", ".join(boxes[:40])))
    write_text(os.path.join(OUT_DIR, LICENSE_FILE), license_notice(sources, licenses))
    size = os.path.getsize(out)
    info = collections.OrderedDict((
        ("family", FAMILY),
        ("file", FONT_FILE),
        ("license", "SIL Open Font License 1.1 (%s)" % LICENSE_FILE),
        ("made_by", "checks/train/language_font.py"),
        ("sources", "https://github.com/%s at %s (static Noto fonts); https://github.com/%s at %s (Noto Sans "
                    "JP, KR, SC, TC, instanced at Regular)" % (NOTO + GOOGLE)),
        ("covers", "every character of the languages list: names, autonyms, script names, the list's "
                   "punctuation, and the orthographies' base, auxiliary, and mark characters (the Missing "
                   "column) but the ideographs, Hangul syllables, cuneiform signs, and hieroglyphs only that column shows"),
        ("size", size),
        ("glyphs", len(merged.getGlyphOrder())),
        ("line", [merged["hhea"].ascent, merged["hhea"].descent]),
        ("shaping_checked", different is not None),
        ("shaping_differences", len(different or [])),
        ("required", " ".join("%04X" % c for c in wanted if c not in unplaced)),  # (tests/language_font_tests.py)
        ("left_to_system", collections.OrderedDict(sorted(collections.Counter(
            ucd.script(chr(c)) for c in left).items()))),
        ("not_covered", " ".join("%04X" % c for c in unplaced)),
        ("fonts", sources),
    ))
    write_text(os.path.join(OUT_DIR, INFO_FILE), json.dumps(info, ensure_ascii=False, indent=1) + "\n")
    say("%s: %d bytes, %d glyphs, from %d fonts" % (FONT_FILE, size, info["glyphs"], len(sources)))
    if unplaced:
        say("no source has: %s" % " ".join("U+%04X" % c for c in unplaced))
    return 0


def license_notice(sources, licenses):
    lines = ["%s (%s) is made of subsets of these fonts, merged and renamed by checks/train/language_font.py:" % (FONT_FILE, FAMILY), ""]
    for source in sources:
        lines.append("- %s, %s: %s" % (source["family"], source["version"], source["copyright"]))
    lines += ["", "They are licensed under the SIL Open Font License, Version 1.1, as is %s. Their licenses, as their" % FONT_FILE,
              "repositories ship them (notofonts.github.io's fonts/LICENSE, google/fonts' OFL.txt), follow.", ""]
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
    return build(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
