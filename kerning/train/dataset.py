"""Build the learned method's training set from the open-licensed fonts installed on this computer.

For every installed font whose name table declares the SIL Open Font License or the Apache License,
and that kerns, this renders the Latin glyphs Auto Kerning measures (FreeType, no hinting, at its
200 pixels per em), measures every common pair with Auto Kerning's own code and native core, and
reads the kerning the font applies through HarfBuzz. Fonts of other licenses are never opened past
their name table.

    python kerning/train/dataset.py [--out <file.npz>] [--limit <fonts>]

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


def open_fonts():
    """(path, index, family, license) of the open-licensed, kerned fonts with l, n, and o."""
    from fontTools.ttLib import TTCollection, TTFont
    found = []
    for folder in FONT_DIRS + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf", "*.ttc", "*.otc"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
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
                        if not all(ord(c) in cmap for c in u"lnoHO"):
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
    and baseline rules as FontLabGlyphs."""

    def __init__(self, path, index, chars, em=ak.EM_PIXELS):
        import freetype
        self.face = freetype.Face(path, index)
        self.face.set_pixel_sizes(em, em)
        self.em, self.pad = em, int(np.ceil(ak.PAD_SHARE * em))
        flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING
        self.bitmaps = {}
        top = bottom = 0
        for ch in chars:
            if not self.face.get_char_index(ord(ch)):
                continue
            self.face.load_char(ch, flags)
            slot = self.face.glyph
            bitmap = slot.bitmap
            if bitmap.width == 0 or bitmap.rows == 0:
                continue
            rows = np.array(bitmap.buffer, dtype=np.uint8).reshape(bitmap.rows, bitmap.pitch)[:, :bitmap.width]
            self.bitmaps[ch] = (rows, slot.bitmap_left, slot.bitmap_top, slot.advance.x / 64.0)
            top, bottom = max(top, slot.bitmap_top), min(bottom, slot.bitmap_top - bitmap.rows)
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


def kerning_of(path, index, pairs):
    """The kerning the font applies to each pair (font units), as HarfBuzz shapes it: Latin, English,
    left to right, with ligatures and contextual alternates off (an fi ligature's advance is not
    kerning)."""
    import uharfbuzz as hb
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path), index))

    def advance(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.direction, buf.script, buf.language = "ltr", "Latn", "en"
        hb.shape(font, buf, SHAPING_FEATURES)
        return sum(p.x_advance for p in buf.glyph_positions)

    singles = {}
    for pair in pairs:
        for ch in pair:
            if ch not in singles:
                singles[ch] = advance(ch)
    return dict((pair, advance(pair) - singles[pair[0]] - singles[pair[1]]) for pair in pairs), font.face.upem


def measure_font(core, path, index, common):
    chars = ak.latin_characters()
    glyphs = FreeTypeGlyphs(path, index, chars)
    present = [ch for ch in chars if ch in glyphs.bitmaps]
    if not all(ch in present for ch in ak.TUNING + (u"H", u"O")):
        return None
    tools = ak.make_bands(core, glyphs.image, present, glyphs.em, glyphs.pad)
    pairs = [p for p in common if p[0] in present and p[1] in present and ak.pair_kinds(p[0], p[1]) is not None]
    kerning, upm = kerning_of(path, index, pairs)
    spacing = ak.font_spacing(core, lambda ch: glyphs.image(ch) if ch in present else None, glyphs.em)
    rows, targets, names = [], [], []
    for pair in pairs:
        left, right = glyphs.image(pair[0]), glyphs.image(pair[1])
        halo, contour = ak.measure_pair(tools, pair[0], pair[1], left, right, glyphs.em, float(glyphs.pad))
        features = ak.pair_features(core, pair[0], pair[1], left, right, glyphs.em, spacing, halo, contour)
        rows.append([np.nan if v is None else v for v in features])
        targets.append(kerning[pair] / float(upm))
        names.append(pair)
    return np.array(rows, dtype=np.float32), np.array(targets, dtype=np.float32), names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(ak.state_dir(), "kerning-train", "dataset.npz"))
    parser.add_argument("--limit", type=int, default=0, help="at most this many fonts (0: all)")
    args = parser.parse_args()
    core = ak.Core()
    common = list(ak.common_pairs(os.path.join(HERE, os.pardir, ak.COMMON_PAIRS_FILE)))
    fonts = open_fonts()
    if args.limit:
        fonts = fonts[:args.limit]
    print("%d open-licensed kerned fonts" % len(fonts), flush=True)
    xs, ys, groups, pairs, sources, font_rows = [], [], [], [], [], []
    families, seen, skipped = {}, set(), {"unkerned": 0, "duplicate": 0}
    started = time.time()
    for number, (path, index, family, licence) in enumerate(fonts, 1):
        try:
            result = measure_font(core, path, index, common)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc), flush=True)
            continue
        if result is None:
            continue
        x, y, names = result
        if (y != 0).mean() < MIN_KERNED_SHARE:
            skipped["unkerned"] += 1
            continue
        design = (tuple(names[:60]), np.round(y[:60], 4).tobytes(), np.round(np.nan_to_num(x[:60]), 3).tobytes())
        if design in seen:  # the same Latin under another name (Noto's scripts) or a copy of a file
            skipped["duplicate"] += 1
            continue
        seen.add(design)
        group = families.setdefault(family, len(families))
        xs.append(x)
        ys.append(y)
        groups.append(np.full(len(y), group, dtype=np.int32))
        font_rows.append(np.full(len(y), len(sources), dtype=np.int32))  # the row's font, in `fonts`
        pairs += names
        sources.append("%s#%d %s" % (os.path.basename(path), index, licence))
        if number % 20 == 0:
            print("%d of %d fonts, %.0f s" % (number, len(fonts), time.time() - started), flush=True)
    folder = os.path.dirname(args.out)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    np.savez_compressed(args.out, x=np.concatenate(xs), y=np.concatenate(ys), group=np.concatenate(groups),
                        font=np.concatenate(font_rows), pair=np.array(pairs), fonts=np.array(sources))
    print("wrote %s: %d pairs from %d fonts in %d families (%.0f s; left out: %d barely kerned, %d duplicates)"
          % (args.out, sum(len(y) for y in ys), len(sources), len(families), time.time() - started,
             skipped["unkerned"], skipped["duplicate"]))


if __name__ == "__main__":
    main()
