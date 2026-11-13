"""Learn how CJK fonts trim their full-width glyphs, from the open-licensed fonts at hand (SIL Open
Font License and Apache License fonts only, as kerning/train/dataset.py finds them, plus FreeLab's own
corpus folder, %LOCALAPPDATA%\\FreeLab\\corpus, where OFL fonts from Google Fonts can be put).

For each font with a palt feature (proportional alternate widths), every kana, CJK punctuation mark,
full-width form, and Hangul syllable it adjusts is measured: its ink's sidebearings after the
adjustment, in shares of the em. halt (half widths) is read the same way for punctuation, and vpal
(proportional heights) for vertical text. The medians, per kind of glyph and per punctuation mark, are
cjk/palt_model.json: CJK Spacing trims a font's glyphs by them.

    python cjk/train/palt.py [--out <file.json>]

Python 3 with fonttools. Only the measurements leave the fonts; the fonts are not copied.
"""

import argparse
import glob
import io
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "kerning", "train"))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import dataset  # noqa: E402  (the corpus's folders and its license check)
from freelab_cjk_spacing import kind_of  # noqa: E402  (the kinds of glyph, as CJK Spacing groups them)

MODEL_FILE = os.path.join(HERE, os.pardir, "palt_model.json")
CORPUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")
MIN_FONTS = 2  # a median from fewer fonts than this is left out


def single_values(font, tag):
    """{glyph: (x placement, y placement, x advance, y advance)} of a GPOS feature's single
    adjustments (the first lookup that names a glyph wins, as shaping applies them)."""
    if "GPOS" not in font:
        return {}
    gpos = font["GPOS"].table
    indexes = []
    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag == tag:
            indexes.extend(record.Feature.LookupListIndex)
    found = {}
    for index in sorted(set(indexes)):
        lookup = gpos.LookupList.Lookup[index]
        for sub in lookup.SubTable:
            if lookup.LookupType == 9:
                sub = sub.ExtSubTable
            if getattr(sub, "LookupType", 1) != 1 and lookup.LookupType not in (1, 9):
                continue
            if not hasattr(sub, "Coverage"):
                continue
            glyphs = sub.Coverage.glyphs
            if sub.Format == 1:
                values = [sub.Value] * len(glyphs)
            else:
                values = sub.Value
            for glyph, value in zip(glyphs, values):
                if glyph in found or value is None:
                    continue
                found[glyph] = tuple(getattr(value, name, 0) or 0 for name in ("XPlacement", "YPlacement", "XAdvance", "YAdvance"))
    return found


def ink_boxes(font, names):
    from fontTools.pens.boundsPen import BoundsPen
    glyph_set = font.getGlyphSet()
    boxes = {}
    for name in names:
        pen = BoundsPen(glyph_set)
        try:
            glyph_set[name].draw(pen)
        except Exception:
            continue
        if pen.bounds:
            boxes[name] = pen.bounds
    return boxes


def fonts():
    from fontTools.ttLib import TTFont
    found = []
    for folder in tuple(dataset.FONT_DIRS) + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    font = TTFont(path, lazy=True)
                    if dataset.license_of(font) and "GPOS" in font and single_values(font, "palt"):
                        found.append((path, dataset.family_of(font)))
                except Exception:
                    continue
    return found


def measure(path):
    """{"palt": {kind or code: [(lsb, rsb)]}, "halt": {code: [(x placement, x advance)]},
    "vpal": {kind: [(top, bottom)]}} of one font, in shares of the em."""
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    upm = float(font["head"].unitsPerEm)
    cmap = font["cmap"].getBestCmap() or {}
    by_glyph = {}
    for code, name in cmap.items():
        if kind_of(code):
            by_glyph.setdefault(name, code)
    palt, halt, vpal = single_values(font, "palt"), single_values(font, "halt"), single_values(font, "vpal")
    boxes = ink_boxes(font, by_glyph)
    metrics = font["hmtx"].metrics
    vmetrics = font["vmtx"].metrics if "vmtx" in font else {}
    ascent = font["OS/2"].sTypoAscender if "OS/2" in font else upm * 0.88
    out = {"palt": {}, "halt": {}, "vpal": {}, "unchanged": {}}
    for name, code in by_glyph.items():
        kind = kind_of(code)
        box = boxes.get(name)
        if box is None:
            continue
        advance = metrics[name][0]
        left, bottom, right, top = box
        if name in palt:
            xpl, _, xadv, _ = palt[name]
            sides = ((left + xpl) / upm, (advance + xadv - (right + xpl)) / upm)
            out["palt"].setdefault(kind, []).append(sides)
            if kind == "punctuation":
                out["palt"].setdefault("U+%04X" % code, []).append(sides)
        else:
            out["unchanged"].setdefault(kind, []).append(1)
        if name in halt and kind == "punctuation":
            xpl, _, xadv, _ = halt[name]
            out["halt"].setdefault("U+%04X" % code, []).append((xpl / upm, xadv / upm))
        if name in vpal and name in vmetrics:
            _, ypl, _, yadv = vpal[name]
            height, tsb = vmetrics[name]
            top_line = top + tsb  # the vertical origin's y
            sides = ((top_line - top - ypl) / upm, (height + yadv - (top_line - bottom) + ypl) / upm)
            out["vpal"].setdefault(kind, []).append(sides)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    found, seen = [], set()
    for path, family in fonts():
        if family not in seen:  # a family installed twice counts once
            seen.add(family)
            found.append((path, family))
    print("%d families with palt" % len(found))
    per_font = []
    for path, family in found:
        try:
            per_font.append(measure(path))
            print("  %s" % family)
        except Exception as exc:
            print("  %s: %s" % (family, exc))
    model = {"format": 1, "fonts": len(per_font), "palt": {}, "halt": {}, "vpal": {}, "adjusted": {}}
    for table in ("palt", "halt", "vpal"):
        keys = set(key for data in per_font for key in data[table])
        for key in sorted(keys):
            medians = [(statistics.median(a for a, _ in data[table][key]), statistics.median(b for _, b in data[table][key]))
                       for data in per_font if data[table].get(key)]
            if len(medians) >= MIN_FONTS:
                model[table][key] = [round(statistics.median(a for a, _ in medians), 4),
                                     round(statistics.median(b for _, b in medians), 4)]
    for kind in ("hiragana", "small hiragana", "katakana", "small katakana", "punctuation", "hangul"):
        shares = []
        for data in per_font:
            adjusted, unchanged = len(data["palt"].get(kind, [])), len(data["unchanged"].get(kind, []))
            if adjusted + unchanged:
                shares.append(adjusted / float(adjusted + unchanged))
        if shares:
            model["adjusted"][kind] = round(statistics.median(shares), 3)
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print("wrote %s: %d palt keys, %d halt, %d vpal" % (os.path.basename(args.out), len(model["palt"]), len(model["halt"]),
                                                        len(model["vpal"])))


if __name__ == "__main__":
    main()
