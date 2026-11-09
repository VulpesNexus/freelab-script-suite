"""Learn where fonts put their marks, from the open-licensed fonts installed on this computer (SIL Open
Font License and Apache License fonts only, as kerning/train/dataset.py finds them).

Every accented letter a TrueType font builds as a composite of its letter and its marks (Unicode's
canonical decomposition, component by component, no scaled components) is measured, in shares of
the em: each mark's gap to the ink below it (the letter's, or the mark under it in a stack) or above
it, its center's offset from the center of the letter's top (or bottom) fifth as a share of the
letter's width, its height against the same mark alone, and how far the whole glyph reaches above the
font's ascender or below its descender. The medians, per mark, case, and letter, are
diacritics/mark_model.json: Diacritics places marks by them in a font with no composites of its
own to learn from.

    python diacritics/train/marks.py [--out <file.json>] [--limit N]

Python 3 with fonttools. Only the measurements leave the fonts; the fonts are not copied.
"""

import argparse
import io
import json
import os
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "kerning", "train"))
sys.path.insert(0, os.path.join(HERE, os.pardir))
import dataset  # noqa: E402  (the corpus: open-licensed fonts installed here)
import freelab_diacritics as ac  # noqa: E402  (the marks' names and sides)

MODEL_FILE = os.path.join(HERE, os.pardir, "mark_model.json")
RANGES = ((0x00C0, 0x0250), (0x1E00, 0x1F00))
MIN_FONTS = 5  # a median from fewer fonts than this is left out
DOTLESS = {"i": 0x0131, "j": 0x0237}


def fonts():
    """(path, index, family) of the open-licensed TrueType fonts with composite glyphs."""
    import glob
    from fontTools.ttLib import TTCollection, TTFont
    found = []
    for folder in dataset.FONT_DIRS:
        for pattern in ("*.ttf", "*.ttc"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    collection = path.lower().endswith(".ttc")
                    members = TTCollection(path, lazy=True).fonts if collection else [TTFont(path, lazy=True)]
                except Exception:
                    continue
                for index, font in enumerate(members):
                    try:
                        if dataset.license_of(font) and "glyf" in font:
                            found.append((path, index, dataset.family_of(font)))
                    except Exception:
                        continue
    return found


def ink(glyf, name):
    """(xMin, yMin, xMax, yMax, top band center, bottom band center, bottom band right) of a glyph's
    points (components decomposed), or None for an empty glyph."""
    glyph = glyf[name]
    coordinates, _, _ = glyph.getCoordinates(glyf)
    points = list(coordinates)
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    band = (y1 - y0) * ac.BAND_SHARE
    top = [x for x, y in points if y >= y1 - band]
    bottom = [x for x, y in points if y <= y0 + band]
    return (x0, y0, x1, y1, (min(top) + max(top)) / 2.0, (min(bottom) + max(bottom)) / 2.0, max(bottom))


def measure_font(path, index):
    """The records of one font: (mark root, side, case, base character, place in its stack, gap, offset
    share, height share against the mark alone, reach above the ascender or below the descender), all
    in shares of the em but the offset (a share of the letter's width)."""
    from fontTools.ttLib import TTCollection, TTFont
    font = TTCollection(path).fonts[index] if path.lower().endswith(".ttc") else TTFont(path)
    upm = float(font["head"].unitsPerEm)
    glyf = font["glyf"]
    cmap = font["cmap"].getBestCmap() or {}
    ascender, descender = font["hhea"].ascent, font["hhea"].descent
    alone = {}  # mark root, case: the mark's height when it is the only one
    found = []
    for low, high in RANGES:
        for code in range(low, high):
            name = cmap.get(code)
            ch = chr(code)
            decomposed = unicodedata.normalize("NFD", ch)
            if name is None or len(decomposed) < 2 or not decomposed[0].isalpha():
                continue
            glyph = glyf[name]
            if not glyph.isComposite() or len(glyph.components) != len(decomposed):
                continue
            components = glyph.components
            base_names = [cmap.get(ord(decomposed[0]))]
            if decomposed[0] in DOTLESS:
                base_names.append(cmap.get(DOTLESS[decomposed[0]]))
            if components[0].glyphName not in base_names or any(
                    getattr(c, "transform", None) is not None for c in components):
                continue
            base = ink(glyf, components[0].glyphName)
            if base is None or base[2] - base[0] <= 0:
                continue
            case = "upper" if ch.isupper() else "lower"
            width = float(base[2] - base[0])
            top, bottom = base[3], base[1]
            glyph_top, glyph_bottom = base[3], base[1]
            stack = {"above": 0, "below": 0}
            previous = {"above": None, "below": None}
            for component, mark in zip(components[1:], decomposed[1:]):
                root = ac.MARKS.get(ord(mark))
                if root is None:
                    break
                side = ac.side_of(ord(mark))
                mark_ink = ink(glyf, component.glyphName)
                if mark_ink is None:
                    break
                x0, y0, x1, y1 = (mark_ink[0] + component.x, mark_ink[1] + component.y,
                                  mark_ink[2] + component.x, mark_ink[3] + component.y)
                center = (x0 + x1) / 2.0
                height = (y1 - y0) / upm
                if side == "above":
                    gap = (y0 - top) / upm
                    offset = (center - base[4]) / width
                    top = y1
                elif side == "below":
                    reference = base[6] - (x1 - x0) / 2.0 if root == "ogonek" else base[5]
                    gap = (bottom - y1) / upm
                    offset = (center - reference) / width
                    bottom = y0
                else:
                    continue
                glyph_top, glyph_bottom = max(glyph_top, y1), min(glyph_bottom, y0)
                place = stack[side]
                stack[side] += 1
                if len(decomposed) == 2:
                    alone.setdefault((root, case), []).append(height)
                found.append([root, side, case, decomposed[0], place, gap, offset, height,
                              (glyph_top - ascender) / upm, (descender - glyph_bottom) / upm, previous[side], height])
                previous[side] = root
    # each mark's height in a stack, against the same mark alone in the same font and case
    alone = dict((key, statistics.median(values)) for key, values in alone.items())
    for record in found:
        single = alone.get((record[0], record[2]))
        record[7] = record[7] / single if single else None
    return found


def median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 4) if values else None


def model(per_font):
    """The medians of the fonts' medians (each font counts once), where enough fonts show them."""
    def per(key_of, value_at, keep=lambda r: True):
        grouped = {}
        for records in per_font:
            mine = {}
            for r in records:
                if keep(r):
                    mine.setdefault(key_of(r), []).append(r[value_at])
            for key, values in mine.items():
                m = median(values)
                if m is not None:
                    grouped.setdefault(key, []).append(m)
        return dict((key, median(values)) for key, values in grouped.items() if len(values) >= MIN_FONTS)

    first = lambda r: r[4] == 0
    stacked = lambda r: r[4] > 0
    return {
        "format": 1,
        "fonts": len(per_font),
        # the gap of a mark to the letter's ink, per mark and case, and per side and case
        "gap": dict(("%s %s" % k, v) for k, v in per(lambda r: (r[0], r[2]), 5, first).items()),
        "side_gap": dict(("%s %s" % k, v) for k, v in per(lambda r: (r[1], r[2]), 5, first).items()),
        # the gap between two stacked marks, per side and case; and a stacked mark's height against it alone
        "stack_gap": dict(("%s %s" % k, v) for k, v in per(lambda r: (r[1], r[2]), 5, stacked).items()),
        # a mark's height, per mark and case (alone on its letter): the size of a mark drafted from punctuation
        "height": dict(("%s %s" % k, v) for k, v in per(lambda r: (r[0], r[2]), 11, first).items()),
        "stack_height": dict(("%s %s" % k, v) for k, v in per(lambda r: (r[1], r[2]), 7, stacked).items()),
        # a mark stacked on another, per pair and case: its gap to the one under it (below zero: beside
        # it more than on it, as Vietnamese sets an acute by a circumflex) and its offset
        "pair_gap": dict(("%s+%s %s" % k, v) for k, v in per(lambda r: (r[10], r[0], r[2]), 5, stacked).items()),
        "pair_offset": dict(("%s+%s %s" % k, v) for k, v in per(lambda r: (r[10], r[0], r[2]), 6, stacked).items()),
        # a mark's center off the center of the letter's top (bottom) fifth, a share of its width
        "offset": dict(("%s %s %s" % k, v) for k, v in per(lambda r: (r[3], r[1], r[0] if r[0] in ("ogonek", "horn") else "*"), 6, first).items()),
        "side_offset": dict(("%s %s" % k, v) for k, v in per(lambda r: (r[1], r[2]), 6, first).items()),
        # how far an accented glyph reaches past the ascender (above) or the descender (below), per case
        # and stack depth: what fonts let marks take of the line's room
        "reach": dict(("%s %d" % k, v) for k, v in per(lambda r: (r[2], min(r[4], 1)), 8,
                                                         lambda r: r[1] == "above").items()),
        "reach_below": dict(("%s %d" % k, v) for k, v in per(lambda r: (r[2], min(r[4], 1)), 9,
                                                               lambda r: r[1] == "below").items()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=MODEL_FILE)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    found = fonts()
    families, per_font = set(), []
    for path, index, family in found:
        if args.limit and len(per_font) >= args.limit:
            break
        if family in families:
            continue  # one font per family: a family's weights place marks alike
        try:
            records = measure_font(path, index)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc))
            continue
        if len(records) >= 20:
            families.add(family)
            per_font.append(records)
    result = model(per_font)
    text = json.dumps(result, indent=1, sort_keys=True)
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")
    print("%d families measured; wrote %s" % (len(per_font), os.path.basename(args.out)))


if __name__ == "__main__":
    main()
