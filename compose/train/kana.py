"""Where the open-licensed Japanese fonts put the dakuten and handakuten on their voiced kana (ga is ka with
a dakuten, pa is ha with a handakuten), for Glyph Compose to build them.

For each open-licensed font at hand with kana (one per family, SIL Open Font License or Apache License,
as kerning/train/dataset.py finds them, plus FreeLab's corpus folder), each voiced kana it has, the
voiced glyph's mark is found: the font's own dakuten (U+3099, else the spacing U+309B) or handakuten
(U+309A, U+309C) by its outlines, shape for shape, in the voiced glyph (or as a component of it); else
the voiced glyph's contours its letter has no contour of the same shape for, where they are a mark's
(1 to 4 small contours at the top right). Then, in shares of the em: the mark's ink center from the
right end (across) and the top (up) of its letter's ink as drawn in the voiced glyph (the voiced glyph
less its mark), and the mark's height. The medians of the fonts' medians, per letter and per kana set
(hiragana, katakana) and mark, from at least MIN_FONTS fonts, are mark_model.json's "kana".

    python compose/train/kana.py [--out <mark_model.json>] [--limit N]

Python 3 with fonttools. Only the measurements leave the fonts; the fonts are not copied.
"""

import argparse
import collections
import io
import json
import os
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import conventions  # noqa: E402  (the fonts at hand, outlines and their shapes; it sets the paths)

MODEL_FILE = os.path.join(HERE, os.pardir, "mark_model.json")
MIN_FONTS = 3
MARKS = {0x3099: ("dakuten", (0x3099, 0x309B)), 0x309A: ("handakuten", (0x309A, 0x309C))}
MARK_NAMES = {"dakuten": ("voicedcombkana", "voicedkana", "dakuten", "uni3099", "uni309B"),
              "handakuten": ("semivoicedcombkana", "semivoicedkana", "handakuten", "uni309A", "uni309C")}


def voiced():
    """{code: (base code, mark code)} of the voiced kana (hiragana and katakana)."""
    found = {}
    for code in range(0x3040, 0x3100):
        decomposed = unicodedata.normalize("NFD", chr(code))
        if len(decomposed) == 2 and ord(decomposed[1]) in MARKS:
            found[code] = (ord(decomposed[0]), ord(decomposed[1]))
    return found


def kana_set(code):
    return "hiragana" if code < 0x30A0 else "katakana"


def measure_font(path):
    """[(mark kind, base code, (across, up, height))] of a font's voiced kana, or [] for a font without kana."""
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    cmap = font.getBestCmap() or {}
    if 0x304B not in cmap and 0x30AB not in cmap:
        return []
    upm = float(font["head"].unitsPerEm)
    glyphset = font.getGlyphSet()
    glyf = font["glyf"] if "glyf" in font else None
    order = set(font.getGlyphOrder())
    tolerance = conventions.TOLERANCE * upm

    def contours(name):
        try:
            return conventions.contours_of(glyphset, name)
        except Exception:
            return []

    templates = {}
    for mark, (kind, codes) in MARKS.items():
        names = [cmap[c] for c in codes if c in cmap] + [n for n in MARK_NAMES[kind] if n in order]
        templates[kind] = [(n, contours(n)) for n in dict.fromkeys(names)]
    found = []
    for code, (base_code, mark) in sorted(voiced().items()):
        name, base = cmap.get(code), cmap.get(base_code)
        if not name or not base:
            continue
        kind = MARKS[mark][0]
        target, base_contours = contours(name), contours(base)
        if not target or not base_contours:
            continue
        mark_box, rest = None, None
        glyph = glyf[name] if glyf is not None else None
        if glyph is not None and glyph.isComposite():  # (ga of ka and the dakuten, as components)
            components = list(glyph.components)
            marks = [c for c in components if c.glyphName != base and getattr(c, "transform", None) is None]
            bases = [c for c in components if c.glyphName == base]
            if len(marks) == 1 and len(bases) == 1:
                mark_box = conventions.box_of(contours(marks[0].glyphName), marks[0].x, marks[0].y)
                rest = conventions.box_of(base_contours, bases[0].x, bases[0].y)
        if mark_box is None:
            for _, template in templates[kind]:
                moved = conventions.find_shape(target, template, tolerance) if template else None
                if moved is not None:
                    mark_box = conventions.box_of(template, *moved)
                    left = [c for c in target if not any(conventions.same_shape(c[0], t[0], tolerance) and
                                                         abs(c[1][0] - t[1][0] - moved[0]) <= tolerance and
                                                         abs(c[1][1] - t[1][1] - moved[1]) <= tolerance
                                                         for t in template)]
                    rest = conventions.box_of(left)
                    break
        if mark_box is None:  # the contours its letter has none of the same shape for
            extra = [c for c in target if not any(conventions.same_shape(c[0], b[0], tolerance) for b in base_contours)]
            kept = [c for c in target if c not in extra]
            if 1 <= len(extra) <= 4 and kept:
                box, rest = conventions.box_of(extra), conventions.box_of(kept)
                small = box[2] - box[0] < 0.4 * upm and box[3] - box[1] < 0.4 * upm
                if small and (box[0] + box[2]) / 2.0 > (rest[0] + rest[2]) / 2.0 and box[3] > (rest[1] + rest[3]) / 2.0:
                    mark_box = box
        if mark_box is None or rest is None:
            continue
        across = ((mark_box[0] + mark_box[2]) / 2.0 - rest[2]) / upm
        up = ((mark_box[1] + mark_box[3]) / 2.0 - rest[3]) / upm
        alone = conventions.box_of(base_contours)  # (how far the voiced glyph moved its letter: not modeled)
        moved = ((rest[2] - alone[2]) / upm, (rest[3] - alone[3]) / upm)
        found.append((kind, base_code, (round(across, 4), round(up, 4), round((mark_box[3] - mark_box[1]) / upm, 4)) +
                      tuple(round(m, 4) for m in moved)))
    return found


def model(per_font):
    """{"dakuten": {"304B": [across, up, height, fonts], "hiragana": [...], "katakana": [...]}, "handakuten": ...}"""
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for records in per_font:
        mine = collections.defaultdict(list)
        for kind, base, values in records:
            mine[(kind, u"%04X" % base)].append(values)
            mine[(kind, kana_set(base))].append(values)
        for (kind, key), values in mine.items():
            grouped[kind][key].append(tuple(statistics.median(v[i] for v in values) for i in range(3)))
    found = {}
    for kind, keys in grouped.items():
        for key, rows in keys.items():
            if len(rows) >= MIN_FONTS:
                found.setdefault(kind, {})[key] = [round(statistics.median(r[i] for r in rows), 4) for i in range(3)] + [len(rows)]
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=MODEL_FILE)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    per_font, families = [], []
    for path, family in conventions.fonts():
        try:
            records = measure_font(path)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc))
            continue
        if len(records) >= 10:
            per_font.append(records)
            families.append(family)
            print("%s: %d voiced kana measured" % (family, len(records)))
        if args.limit and len(per_font) >= args.limit:
            break
    found = model(per_font)
    found["fonts"] = len(per_font)
    with io.open(args.out, encoding="utf-8") as handle:
        data = json.load(handle)
    data["kana"] = found
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
    for kind in ("dakuten", "handakuten"):
        for key in ("hiragana", "katakana"):
            print(kind, key, found.get(kind, {}).get(key))
    print("%d families measured; wrote %s" % (len(per_font), os.path.basename(args.out)))


if __name__ == "__main__":
    main()
