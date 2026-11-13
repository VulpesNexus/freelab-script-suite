"""Measure how open-licensed fonts draw their small figures, for Feature Code's figure builds: for each
font of the corpus (SIL Open Font License or Apache License, as kerning/train/dataset.py reads its
license) with lining default figures, its numerators, denominators, superiors, inferiors (by its GSUB
numr, dnom, sups, subs, and sinf features, else by the glyph names' suffixes), its Unicode superscript
and subscript figures, and its ordinal indicators, each measured against the figure or letter it is a
small form of:

- scale: the form's ink height over the figure's;
- baseline: where the figure's baseline lands once scaled (the form's lowest point less the scaled
  figure's), over the cap height;
- top: the form's highest point over the cap height;
- advance: the form's advance width over the figure's, and over the scaled figure's;
- weight: the form's ink width over the scaled figure's (above 1: drawn wider than a plain scaling).

Each font gives the median of its figures; the report gives the median of the fonts, one font per
family (its first file), with the quartiles.

    python features/train/figure_forms.py [--fonts <folder>] [--json <file>]

Python 3 with fonttools. The fonts are only read; the output is numbers, printed (and to --json).
"""

import argparse
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "kerning", "train"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import dataset  # noqa: E402  (the license check, the corpus folder)

KINDS = (("numr", ("numr", "numerator")), ("dnom", ("dnom", "denominator")), ("sups", ("sups", "superior")),
         ("subs", ("subs", "inferior", "inf")), ("sinf", ("sinf",)))
SUPERSCRIPT = {0x30: 0x2070, 0x31: 0xB9, 0x32: 0xB2, 0x33: 0xB3, 0x34: 0x2074, 0x35: 0x2075, 0x36: 0x2076,
               0x37: 0x2077, 0x38: 0x2078, 0x39: 0x2079}
SUBSCRIPT = dict((0x30 + n, 0x2080 + n) for n in range(10))
MEASURES = ("scale", "baseline", "top", "advance", "scaled_advance", "weight")


def bounds_of(glyphs, name):
    from fontTools.pens.boundsPen import BoundsPen
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    return pen.bounds


def letter_bounds(glyphs, name):
    """An ordinal indicator's letter, without the bar under it: the box of its contours but the flat
    ones at the bottom."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.boundsPen import BoundsPen
    pen = DecomposingRecordingPen(glyphs)
    glyphs[name].draw(pen)
    contours, current = [], []
    for operator, operands in pen.value:
        current.append((operator, operands))
        if operator in ("closePath", "endPath"):
            contours.append(current)
            current = []
    boxes = []
    for contour in contours:
        box = BoundsPen(glyphs)
        for operator, operands in contour:
            getattr(box, operator)(*operands)
        if box.bounds:
            boxes.append(box.bounds)
    if not boxes:
        return None
    whole = max(b[3] for b in boxes) - min(b[1] for b in boxes)
    kept = [b for b in boxes if (b[3] - b[1]) > 0.25 * whole or b[1] > min(c[1] for c in boxes) + 0.1 * whole]
    if not kept:
        return None
    return (min(b[0] for b in kept), min(b[1] for b in kept), max(b[2] for b in kept), max(b[3] for b in kept))


def single_maps(font, tag):
    """{glyph: its substitute} of a GSUB feature's single substitutions."""
    found = {}
    if "GSUB" not in font:
        return found
    table = font["GSUB"].table
    if not table.FeatureList or not table.LookupList:
        return found
    for record in table.FeatureList.FeatureRecord:
        if record.FeatureTag != tag:
            continue
        for index in record.Feature.LookupListIndex:
            lookup = table.LookupList.Lookup[index]
            for subtable in lookup.SubTable:
                if lookup.LookupType == 7:
                    subtable = subtable.ExtSubTable
                mapping = getattr(subtable, "mapping", None)
                if mapping and getattr(subtable, "LookupType", lookup.LookupType) == 1:
                    for source, target in mapping.items():
                        found.setdefault(source, target)
    return found


def measure(glyphs, advances, cap, figure, form, form_box=None, figure_box=None):
    fig, box = figure_box or bounds_of(glyphs, figure), form_box or bounds_of(glyphs, form)
    if not fig or not box or fig[3] - fig[1] <= 0 or fig[2] - fig[0] <= 0:
        return None
    scale = (box[3] - box[1]) / float(fig[3] - fig[1])
    if not 0.2 < scale < 0.95:
        return None
    return {"scale": scale, "baseline": (box[1] - scale * fig[1]) / cap, "top": box[3] / cap,
            "advance": advances[form] / float(advances[figure]),
            "scaled_advance": advances[form] / (scale * advances[figure]),
            "weight": (box[2] - box[0]) / (scale * (fig[2] - fig[0]))}


def median_of(rows):
    return dict((key, statistics.median(row[key] for row in rows)) for key in MEASURES) if rows else None


def font_measures(path):
    from fontTools.ttLib import TTFont
    font = TTFont(path, lazy=True)
    if dataset.license_of(font) is None:
        return None, "not open-licensed"
    cmap = font["cmap"].getBestCmap() or {}
    figures = [cmap.get(0x30 + n) for n in range(10)]
    if not all(figures):
        return None, "no figures"
    glyphs = font.getGlyphSet()
    advances = dict((name, metric[0]) for name, metric in font["hmtx"].metrics.items())
    cap = getattr(font["OS/2"], "sCapHeight", 0) or 0
    if cap <= 0 and cmap.get(0x48):
        cap = (bounds_of(glyphs, cmap[0x48]) or (0, 0, 0, 0))[3]
    if cap <= 0:
        return None, "no cap height"
    zero, eight = bounds_of(glyphs, figures[0]), bounds_of(glyphs, figures[8])
    if not zero or not eight or zero[3] < 0.85 * eight[3]:
        return None, "oldstyle default figures"
    order = font.getGlyphOrder()
    names = set(order)
    result = {"cap_over_figure": cap / float(statistics.median(bounds_of(glyphs, f)[3] for f in figures))}
    for kind, suffixes in KINDS:
        mapping = single_maps(font, kind)
        rows = []
        for figure in figures:
            form = mapping.get(figure)
            if form is None:
                for suffix in suffixes:
                    if figure + "." + suffix in names:
                        form = figure + "." + suffix
                        break
            if form is not None and form != figure:
                row = measure(glyphs, advances, cap, figure, form)
                if row:
                    rows.append(row)
        if len(rows) >= 5:
            result[kind] = median_of(rows)
    for kind, table in (("superscript", SUPERSCRIPT), ("subscript", SUBSCRIPT)):
        rows = []
        for code, form_code in table.items():
            if cmap.get(form_code) and cmap.get(code):
                row = measure(glyphs, advances, cap, cmap[code], cmap[form_code])
                if row:
                    rows.append(row)
        if len(rows) >= 3:
            result[kind] = median_of(rows)
    rows = []
    for letter, indicator in ((0x61, 0xAA), (0x6F, 0xBA)):
        if cmap.get(letter) and cmap.get(indicator):
            box = letter_bounds(glyphs, cmap[indicator])
            row = measure(glyphs, advances, cap, cmap[letter], cmap[indicator], form_box=box) if box else None
            if row:
                rows.append(row)
    if rows:
        result["ordinal"] = median_of(rows)
    numr, sups = single_maps(font, "numr"), single_maps(font, "sups")
    shared = [f for f in figures if numr.get(f) and numr.get(f) == sups.get(f)]
    result["numr_is_sups"] = bool(shared) and len(shared) >= 5
    return result, None


def quartiles(values):
    values = sorted(values)
    if len(values) < 4:
        return values[0], statistics.median(values), values[-1]
    q = statistics.quantiles(values, n=4)
    return q[0], q[1], q[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fonts", default=dataset.CORPUS_DIR)
    parser.add_argument("--json")
    args = parser.parse_args()
    families, skipped = {}, {}
    for pattern in ("*.ttf", "*.otf"):
        for path in sorted(glob.glob(os.path.join(args.fonts, pattern))):
            try:
                from fontTools.ttLib import TTFont
                family = dataset.family_of(TTFont(path, lazy=True)) or os.path.basename(path)
                if family in families:
                    continue
                result, why = font_measures(path)
            except Exception as exc:
                result, why = None, "unreadable (%s)" % type(exc).__name__
            if result is None:
                skipped[why] = skipped.get(why, 0) + 1
                continue
            families[family] = result
    print("%d families measured; skipped: %s" % (len(families), ", ".join("%s %d" % item for item in sorted(skipped.items()))))
    report = {"families": len(families)}
    kinds = [kind for kind, _ in KINDS] + ["superscript", "subscript", "ordinal"]
    for kind in kinds:
        rows = [result[kind] for result in families.values() if kind in result]
        if not rows:
            continue
        report[kind] = {"fonts": len(rows)}
        line = ["%-12s %3d fonts" % (kind, len(rows))]
        for key in MEASURES:
            low, mid, high = quartiles([row[key] for row in rows])
            report[kind][key] = [round(low, 3), round(mid, 3), round(high, 3)]
            line.append("%s %.3f (%.3f-%.3f)" % (key, mid, low, high))
        print("  ".join(line))
    both = [result for result in families.values() if "numr" in result]
    report["numr_is_sups"] = [sum(1 for result in both if result["numr_is_sups"]), len(both)]
    print("numr glyphs are the sups glyphs in %d of %d" % tuple(report["numr_is_sups"]))
    report["cap_over_figure"] = round(statistics.median(result["cap_over_figure"] for result in families.values()), 3)
    print("cap height over figure height: %.3f" % report["cap_over_figure"])
    if args.json:
        with open(args.json, "w", newline="") as handle:
            json.dump(report, handle, indent=1, sort_keys=True)
            handle.write("\n")


if __name__ == "__main__":
    main()
