"""Build the learned method's training set from the open-licensed fonts installed on this computer.

For every installed font whose name table declares the SIL Open Font License or the Apache License,
and that kerns, this renders the glyphs Auto Kerning measures (FreeType, no hinting, at its 200 pixels
per em), measures every common pair with Auto Kerning's own code and native core, and reads the
kerning the font applies through HarfBuzz. Each script is measured on its own, with its own references
and common pairs: Latin's (kerning/common_pairs.txt), and kana's, Armenian's, and Georgian's
(kerning/script_pairs.txt), kana as palt sets them; train.py scores each script and trains on those
asked for. Right-to-left pairs (Hebrew, Thaana) are measured as they stand on screen, the left glyph
first, as Auto Kerning keeps them, and their kerning read from text typed in text order and shaped
right to left (rtl_kerning_of). Fonts of other licenses are never opened past their name table.

    python kerning/train/dataset.py [--out <file.npz>] [--limit <fonts>] [--scripts latin,armenian,georgian,kana]
        [--add-to <dataset.npz>]  (the scripts' rows added to an earlier training set, its rows kept)

Python 3 with fonttools, freetype-py, uharfbuzz, and numpy; the core DLL as Auto Kerning finds it
(or FREELAB_KERN_DLL). The output (default %LOCALAPPDATA%\\FreeLab\\kerning-train\\dataset.npz) holds
measurements of the fonts, not the fonts, and stays outside the repository.
"""

import argparse
import ctypes
import glob
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_auto_kerning as ak  # noqa: E402

SHAPING_FEATURES = {"kern": True, "liga": False, "clig": False, "dlig": False, "hlig": False, "calt": False}
MIN_KERNED_SHARE = 0.05  # a font kerning fewer of the common pairs than this has no kerning to learn from
FONT_DIRS = tuple(os.path.join(base, *parts) for base, parts in (
    (os.environ.get("WINDIR") or os.environ.get("SystemRoot"), ("Fonts",)),
    (os.environ.get("LOCALAPPDATA"), ("Microsoft", "Windows", "Fonts"))) if base)
CORPUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")  # open-licensed fonts fetched for the corpus
# Folders under the corpus read through (their subfolders too) for the scripts other than Latin only, so
# that Latin's training set stays the one the shipped model was checked on: google/fonts families
# fetched for those scripts (kerning-fonts, with its manifest.json), and the Noto fonts FreeLang is
# built from (language-font-sources, its subsets in work/ left out).
OTHER_SCRIPT_DIRS = ("kerning-fonts", "language-font-sources")
OPEN_LICENSES = (("open font license", "OFL"), ("scripts.sil.org/ofl", "OFL"), ("openfontlicense", "OFL"),
                 ("apache license", "Apache"), ("apache.org/licenses", "Apache"))


# Words of proprietary terms: a font whose license text has them is not open-licensed, even where it
# names an open license for some part of it (Segoe UI Historic's Apache-licensed Noto components).
PROPRIETARY = ("microsoft supplied font", "any other use is prohibited", "end user license agreement")


def license_of(font):
    text = " ".join(str(r) for r in font["name"].names if r.nameID in (13, 14)).lower()
    if any(marker in text for marker in PROPRIETARY):
        return None
    for marker, name in OPEN_LICENSES:
        if marker in text:
            return name
    return None


def family_of(font):
    name = font["name"]
    return str(name.getDebugName(16) or name.getDebugName(1) or "")


def font_files(scripts=("latin",)):
    """Every font file to look at: the installed fonts and the corpus folder's own, then, when a script
    other than Latin is asked for, OTHER_SCRIPT_DIRS' (see latin_measured)."""
    found = []
    for folder in FONT_DIRS + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf", "*.ttc", "*.otc"):
            found.extend(sorted(glob.glob(os.path.join(folder, pattern))))
    if any(script != "latin" for script in scripts):
        for name in OTHER_SCRIPT_DIRS:
            for root, folders, files in os.walk(os.path.join(CORPUS_DIR, name)):
                folders[:] = sorted(f for f in folders if f != "work")
                found.extend(os.path.join(root, f) for f in sorted(files) if f.lower().endswith((".ttf", ".otf", ".ttc", ".otc")))
    return found


def latin_measured(path):
    """Whether a font's Latin is measured: not for the fonts of OTHER_SCRIPT_DIRS."""
    folders = [os.path.normcase(os.path.join(CORPUS_DIR, name)) + os.sep for name in OTHER_SCRIPT_DIRS]
    return not any(os.path.normcase(path).startswith(folder) for folder in folders)


def open_fonts(scripts=("latin",)):
    """(path, index, family, license) of the open-licensed, kerned fonts with l, n, o, H, and O, or
    with another of the scripts' tuning letters."""
    from fontTools.ttLib import TTCollection, TTFont
    found = []
    for path in font_files(scripts):
        try:
            collection = path.lower().endswith((".ttc", ".otc"))
            fonts = TTCollection(path, lazy=True).fonts if collection else [TTFont(path, lazy=True)]
        except Exception:
            continue
        for index, font in enumerate(fonts):
            try:
                licence = license_of(font)
                if licence is None:
                    continue
                cmap = font["cmap"].getBestCmap() or {}
                tunings = [u"lnoHO" if script == "latin" else u"".join(ak.SCRIPT_TUNING[script]) for script in scripts]
                if not any(all(ord(c) in cmap for c in tuning) for tuning in tunings):
                    continue
                kerned = ("GPOS" in font and any(r.FeatureTag == "kern" for r in font["GPOS"].table.FeatureList.FeatureRecord)) \
                    or "kern" in font
                if kerned:
                    found.append((path, index, family_of(font), licence))
            except Exception:
                continue
    return found


class FreeTypeGlyphs(object):
    """Auto Kerning's glyph images, rendered by FreeType instead of Qt: the same sizes, padding,
    and baseline rules as FontLabGlyphs. adjustments {character: (x placement, x advance)}, in font
    units, set glyphs as a feature does (kana as palt sets them), as FontLabGlyphs' do."""

    def __init__(self, path, index, chars, em=ak.EM_PIXELS, adjustments=None):
        import freetype
        self.face = freetype.Face(path, index)
        self.face.set_pixel_sizes(em, em)
        self.em, self.pad = em, int(np.ceil(ak.PAD_SHARE * em))
        scale = em / float(self.face.units_per_EM)
        flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING
        self.bitmaps = {}
        top = bottom = 0
        for ch in chars:
            if not self.face.get_char_index(ord(ch)):
                continue
            placement, extra = (adjustments or {}).get(ch, (0, 0))
            matrix, shift = freetype.Matrix(0x10000, 0, 0, 0x10000), freetype.Vector(int(round(placement * scale * 64)), 0)
            self.face.set_transform(matrix, shift)  # the ink moved by the placement, to a 64th of a pixel
            self.face.load_char(ch, flags)
            slot = self.face.glyph
            bitmap = slot.bitmap
            if bitmap.width == 0 or bitmap.rows == 0:
                continue
            rows = np.array(bitmap.buffer, dtype=np.uint8).reshape(bitmap.rows, bitmap.pitch)[:, :bitmap.width]
            self.bitmaps[ch] = (rows, slot.bitmap_left, slot.bitmap_top, slot.advance.x / 64.0 + extra * scale)
            top, bottom = max(top, slot.bitmap_top), min(bottom, slot.bitmap_top - bitmap.rows)
        self.face.set_transform(freetype.Matrix(0x10000, 0, 0, 0x10000), freetype.Vector(0, 0))
        self.ascent, self.descent = top + 1, -bottom + 1
        self.images = {}

    def image(self, ch):
        if ch in self.images:
            return self.images[ch]
        rows, left, top, advance = self.bitmaps[ch]
        h, w = rows.shape
        origin_x = self.pad + max(0, -left) + 1
        width = origin_x + max(0, left + w) + 1 + self.pad
        height = self.ascent + self.descent + 2 * self.pad
        baseline = self.pad + self.ascent
        canvas = np.zeros((height, width), dtype=np.uint8)
        canvas[baseline - top:baseline - top + h, origin_x + left:origin_x + left + w] = rows
        coverage = (ctypes.c_uint8 * canvas.size).from_buffer_copy(canvas.tobytes())
        glyph = ak.Glyph(ch, coverage, width, height, width, origin_x, ak.round_units(advance), baseline)
        self.images[ch] = glyph
        return glyph


# How each script is shaped to read the kerning a font applies: HarfBuzz's script and language, and
# the features turned on besides kern (kana as palt sets them: their kerning is set for it).
SCRIPT_SHAPING = {"latin": ("Latn", "en", {}), "kana": ("Kana", "ja", {"palt": True}), "armenian": ("Armn", "hy", {}),
                  "georgian": ("Geor", "ka", {}), "cyrillic": ("Cyrl", "ru", {}), "greek": ("Grek", "el", {}),
                  "devanagari": ("Deva", "hi", {}), "hebrew": ("Hebr", "he", {}), "thaana": ("Thaa", "dv", {})}


def kerning_of(path, index, pairs, script="latin"):
    """The kerning the font applies to each pair (font units), as HarfBuzz shapes it: Latin, English,
    left to right (or the script's own, SCRIPT_SHAPING), with ligatures and contextual alternates off
    (an fi ligature's advance is not kerning). A right-to-left script's pairs, (left, right) on screen
    as Auto Kerning keeps them, are typed in text order and shaped right to left (rtl_kerning_of)."""
    import uharfbuzz as hb
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path), index))
    tag, language, extra = SCRIPT_SHAPING[script]
    features = dict(SHAPING_FEATURES, **extra)
    if script in ak.RTL_SCRIPTS:
        return rtl_kerning_of(font, pairs, tag, language, features), font.face.upem

    def advance(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction, buf.script, buf.language = "ltr", tag, language
        hb.shape(font, buf, features)
        return sum(p.x_advance for p in buf.glyph_positions)

    singles = {}
    for pair in pairs:
        for ch in pair:
            if ch not in singles:
                singles[ch] = advance(ch)
    return dict((pair, advance(pair) - singles[pair[0]] - singles[pair[1]]) for pair in pairs), font.face.upem


def rtl_kerning_of(font, pairs, tag, language, features):
    """How much nearer the right glyph sits to the left one on screen (font units, negative tighter),
    for each pair (left, right) of a right-to-left script: typed in text order (ak.text_order: the
    right glyph first, brackets as their mirror) and shaped right to left with kern on and off, the
    change in the distance from the left glyph's position to the right one's. A right-to-left font
    kerns a pair on the first glyph's placement and advance (<-30 0 -30 0>), so its total advance
    alone, as kerning_of reads a left-to-right pair, would miss the placement: the positions are read
    instead. A pair that does not shape to two glyphs is read as unkerned."""
    import uharfbuzz as hb

    def placed(text, kern):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction, buf.script, buf.language = "rtl", tag, language
        hb.shape(font, buf, dict(features, kern=kern))
        out, x = [], 0
        for pos in buf.glyph_positions:  # (on screen, left to right)
            out.append(x + pos.x_offset)
            x += pos.x_advance
        return out

    found = {}
    for pair in pairs:
        text = ak.text_order(pair[0], pair[1])
        on, off = placed(text, True), placed(text, False)
        found[pair] = (on[1] - on[0]) - (off[1] - off[0]) if len(on) == 2 and len(off) == 2 else 0
    return found


def palt_of(path, index):
    """{character: (x placement, x advance)} of the font's palt, in font units (CJK Spacing's reading)."""
    from fontTools.ttLib import TTFont
    sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "cjk", "train"))
    import palt  # noqa: E402  (cjk/train/palt.py: single adjustments of a GPOS feature)
    font = TTFont(path, fontNumber=index, lazy=True)
    values = palt.single_values(font, "palt")
    found = {}
    for code, name in (font["cmap"].getBestCmap() or {}).items():
        if name in values and code <= 0xFFFF:
            found[chr(code)] = (values[name][0], values[name][2])
    return found


def measure_font(core, path, index, common, script="latin"):
    """(features, kerning as shares of the em, pairs) of the common pairs of a script the font has,
    or None without the script's tuning letters (or Latin's H and O)."""
    chars = ak.script_characters(script)
    adjustments = palt_of(path, index) if script == "kana" else None
    glyphs = FreeTypeGlyphs(path, index, chars, adjustments=adjustments)
    present = [ch for ch in chars if ch in glyphs.bitmaps]
    if not all(ch in present for ch in ak.SCRIPT_TUNING[script] + ((u"H", u"O") if script == "latin" else ())):
        return None
    if script == "kana":  # full-width kana that palt leaves full width are not kerned by Auto Kerning: left out
        upm = float(glyphs.face.units_per_EM)
        adjusted = adjustments or {}
        widths = dict((ch, glyphs.bitmaps[ch][3] * upm / glyphs.em - adjusted.get(ch, (0, 0))[1])
                      for ch in present if ch in ak.KANA_LETTERS)  # (without palt's change)
        if ak.kana_setting(widths, upm, adjusted) is None:
            return None
    tools = ak.make_bands(core, glyphs.image, present, glyphs.em, glyphs.pad, script)
    pairs = [p for p in common if p[0] in present and p[1] in present and ak.pair_kinds(p[0], p[1]) is not None]
    kerning, upm = kerning_of(path, index, pairs, script)
    spacing = ak.font_spacing(core, lambda ch: glyphs.image(ch) if ch in present else None, glyphs.em, script)
    rows, targets, names = [], [], []
    for pair in pairs:
        left, right = glyphs.image(pair[0]), glyphs.image(pair[1])
        halo, contour = ak.measure_pair(tools, pair[0], pair[1], left, right, glyphs.em, float(glyphs.pad))
        features = ak.pair_features(core, pair[0], pair[1], left, right, glyphs.em, spacing, halo, contour)
        rows.append([np.nan if v is None else v for v in features])
        targets.append(kerning[pair] / float(upm))
        names.append(pair)
    return np.array(rows, dtype=np.float32), np.array(targets, dtype=np.float32), names


def script_common_pairs(script):
    """A script's common pairs: Latin's from common_pairs.txt, the others' from script_pairs.txt."""
    if script == "latin":
        return list(ak.common_pairs(os.path.join(HERE, os.pardir, ak.COMMON_PAIRS_FILE)))
    every = ak.common_pairs(os.path.join(HERE, os.pardir, ak.SCRIPT_PAIRS_FILE))
    found = [pair for pair in sorted(every, key=every.get) if any(ak.script_of(ch) == script for ch in pair)]
    if script in ak.RTL_SCRIPTS:  # counted in text order: kept as on screen, the left glyph first
        found = [u"".join(ak.screen_order(pair)) for pair in found]
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(ak.state_dir(), "kerning-train", "dataset.npz"))
    parser.add_argument("--limit", type=int, default=0, help="at most this many fonts (0: all)")
    parser.add_argument("--scripts", default=",".join(key for key, _ in ak.SCRIPTS), help="the scripts measured, by Auto Kerning's names")
    parser.add_argument("--add-to", default="", help="a training set (made by this script, with its families) the "
                                                     "scripts' rows are added to, its own rows kept as they are")
    args = parser.parse_args()
    scripts = [script for script in args.scripts.split(",") if script]
    core = ak.Core()
    common = dict((script, script_common_pairs(script)) for script in scripts)
    fonts = open_fonts(scripts)
    if args.limit:
        fonts = fonts[:args.limit]
    print("%d open-licensed kerned fonts" % len(fonts), flush=True)
    xs, ys, groups, pairs, sources, font_rows, script_rows = [], [], [], [], [], [], []
    families, seen, skipped = {}, set(), {"unkerned": 0, "duplicate": 0}
    if args.add_to:  # (a script's number is its place in SCRIPTS: a set numbered otherwise is refused below)
        old = np.load(args.add_to)
        if [str(s) for s in old["scripts"]] != [key for key, _ in ak.SCRIPTS][:len(old["scripts"])]:
            raise SystemExit("%s numbers its scripts otherwise" % args.add_to)
        added = set(scripts) & set(str(old["scripts"][n]) for n in np.unique(old["script"]))
        if added:
            raise SystemExit("%s has %s already" % (args.add_to, ", ".join(sorted(added))))
        xs, ys, groups, font_rows, script_rows = [old["x"]], [old["y"]], [old["group"]], [old["font"]], [old["script"]]
        pairs, sources = [str(p) for p in old["pair"]], [str(s) for s in old["fonts"]]
        families = dict((str(name), number) for number, name in enumerate(old["families"]))
    started = time.time()
    for number, (path, index, family, licence) in enumerate(fonts, 1):
        source = None
        for script in scripts:
            if script == "latin" and not latin_measured(path):
                continue
            try:
                result = measure_font(core, path, index, common[script], script)
            except Exception as exc:
                print("skipped %s (%s): %s" % (os.path.basename(path), script, exc), flush=True)
                continue
            if result is None or not len(result[1]):
                continue
            x, y, names = result
            if (y != 0).mean() < MIN_KERNED_SHARE:
                skipped["unkerned"] += 1
                continue
            design = (script, tuple(names[:60]), np.round(y[:60], 4).tobytes(), np.round(np.nan_to_num(x[:60]), 3).tobytes())
            if design in seen:  # the same letters under another name (Noto's scripts) or a copy of a file
                skipped["duplicate"] += 1
                continue
            seen.add(design)
            if source is None:
                source = len(sources)
                sources.append("%s#%d %s" % (os.path.basename(path), index, licence))
            group = families.setdefault(family, len(families))
            xs.append(x)
            ys.append(y)
            groups.append(np.full(len(y), group, dtype=np.int32))
            font_rows.append(np.full(len(y), source, dtype=np.int32))  # the row's font, in `fonts`
            script_rows.append(np.full(len(y), [key for key, _ in ak.SCRIPTS].index(script), dtype=np.int32))
            pairs += names
        if number % 20 == 0:
            print("%d of %d fonts, %.0f s" % (number, len(fonts), time.time() - started), flush=True)
    folder = os.path.dirname(args.out)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    np.savez_compressed(args.out, x=np.concatenate(xs), y=np.concatenate(ys), group=np.concatenate(groups),
                        font=np.concatenate(font_rows), pair=np.array(pairs), fonts=np.array(sources),
                        script=np.concatenate(script_rows), scripts=np.array([key for key, _ in ak.SCRIPTS]),
                        families=np.array(sorted(families, key=families.get)))  # (group i's family name: families[i])
    counts = np.bincount(np.concatenate(script_rows), minlength=len(ak.SCRIPTS))
    print("wrote %s: %d pairs from %d fonts in %d families (%s; %.0f s; left out: %d barely kerned, %d duplicates)"
          % (args.out, sum(len(y) for y in ys), len(sources), len(families),
             ", ".join("%s %d" % (key, count) for (key, _), count in zip(ak.SCRIPTS, counts) if count),
             time.time() - started, skipped["unkerned"], skipped["duplicate"]))


if __name__ == "__main__":
    main()
