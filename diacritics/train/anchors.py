"""Learn where fonts put their mark anchors, from the open-licensed fonts at hand (SIL Open Font License
and Apache License fonts only, as kerning/train/dataset.py finds them, plus FreeLab's corpus folder,
%LOCALAPPDATA%\\FreeLab\\corpus, where OFL fonts from Google Fonts were put).

Scripts whose marks are not precomposed (Khmer, Thai, Arabic, Devanagari, and the combining marks of
any script) are set by the font's mark features: a mark's anchor meets its base's. For each font, each
mark-to-base attachment of those scripts is measured, in shares of the em: how far above the base's
ink top (below its ink bottom) the base's anchor sits, and how far across from the center of the
base's top (bottom) fifth, as a share of its width; how far below the mark's ink (above, for marks
below) the mark's anchor sits; and, for mark-to-mark, how far above a mark's ink its own anchor sits.
The medians, per script and side, are diacritics/anchor_model.json: Diacritics places anchors by them.
Then it shapes text with each font (diacritics/train/shaped.py, through HarfBuzz): where a sample mark
lands on each letter, the reph on a consonant, how far the i-matra picked before each consonant reaches
into it, and where two-part ligatures' marks attach; the medians, from at least MIN_FONTS fonts each, are
the model's "letters", "reph", "i_matra", and "ligature".
It also counts, per script, the letters each font attaches marks to (its encoded glyph or a form of
it named after it, beh-ar.init): the letters at least BASE_SHARE of the fonts having them attach marks
to are the script's bases, the letters Diacritics gives anchors to where Unicode composes none.

    python diacritics/train/anchors.py [--out <file.json>]

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
import freelab_diacritics as dia  # noqa: E402  (the scripts' ranges)
import shaped  # noqa: E402  (beside this file: where marks land as HarfBuzz shapes them)

MODEL_FILE = os.path.join(HERE, os.pardir, "anchor_model.json")
CORPUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")
MIN_FONTS = 2
BASE_SHARE = 0.5  # of the fonts having a letter, those attaching marks to it, for it to be a base
MIN_LETTER_FONTS = 3  # a letter's own placement, from at least this many fonts
BAND = 0.2  # the share of a base's ink, at its top or bottom, whose center an anchor is measured from


POSITIONING = ("mark", "abvm", "blwm")  # Indic fonts (Devanagari, Khmer) attach marks in abvm and blwm


def lookups(font, tags, kind):
    gpos = font["GPOS"].table
    found, seen = [], set()
    for record in gpos.FeatureList.FeatureRecord:
        if record.FeatureTag not in tags:
            continue
        for index in record.Feature.LookupListIndex:
            if index in seen:
                continue
            seen.add(index)
            lookup = gpos.LookupList.Lookup[index]
            for sub in lookup.SubTable:
                if lookup.LookupType == 9:
                    sub = sub.ExtSubTable
                if getattr(sub, "LookupType", lookup.LookupType) == kind:
                    found.append(sub)
    return found


def inks(font, names):
    """{glyph: (left, bottom, right, top, top band center, bottom band center)} in font units."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    glyph_set = font.getGlyphSet()
    found = {}
    for name in names:
        pen = BoundsPen(glyph_set)
        try:
            glyph_set[name].draw(pen)
        except Exception:
            continue
        if not pen.bounds:
            continue
        left, bottom, right, top = pen.bounds
        found[name] = (left, bottom, right, top, band_center(glyph_set, name, top - (top - bottom) * BAND, top),
                       band_center(glyph_set, name, bottom, bottom + (top - bottom) * BAND))
    return found


def band_center(glyph_set, name, low, high):
    """The center across of a glyph's on-curve and off-curve points within a band of heights (a cheap
    stand-in for its ink's), or None."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    pen = DecomposingRecordingPen(glyph_set)
    try:
        glyph_set[name].draw(pen)
    except Exception:
        return None
    xs = [point[0] for _, points in pen.value for point in points if point is not None and low <= point[1] <= high]
    return (min(xs) + max(xs)) / 2.0 if xs else None


def attached_letters(font, subs, script_of):
    """{script: (letters it has, letters it attaches marks to)}: code points, a letter attached when its
    glyph, or a glyph named after it (its name before a period), is a base of a mark attachment."""
    import unicodedata
    cmap = font["cmap"].getBestCmap() or {}
    attached_names = set()
    for sub in subs:
        for base, record in zip(sub.BaseCoverage.glyphs, sub.BaseArray.BaseRecord):
            if any(anchor is not None for anchor in record.BaseAnchor):
                attached_names.add(base)
                attached_names.add(base.split(".")[0])
    found = {}
    for code, name in cmap.items():
        script = script_of.get(name)
        if not script or not unicodedata.category(chr(code)).startswith("L"):
            continue
        has, attached = found.setdefault(script, (set(), set()))
        has.add(code)
        if name in attached_names:
            attached.add(code)
    return found


def measure(path):
    """{(script, side): {"base_gap": [], "base_offset": [], "mark_gap": [], "mark_offset": [],
    "mark_top": []}} of one font, in shares of the em (offsets across: of the base's width), and
    attached_letters'."""
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    if "GPOS" not in font:
        return {}, {}
    upm = float(font["head"].unitsPerEm)
    cmap = font["cmap"].getBestCmap() or {}
    script_of = {}
    for code, name in cmap.items():
        script = dia.anchor_script(code)
        if script:
            script_of.setdefault(name, script)
    if not script_of:
        return {}, {}
    out = {}
    subs = lookups(font, POSITIONING, 4)
    letters = attached_letters(font, subs, script_of)
    names = set()
    for sub in subs:
        names.update(sub.MarkCoverage.glyphs)
        names.update(sub.BaseCoverage.glyphs)
    ink = inks(font, [n for n in names if n in script_of])
    for sub in subs:
        marks = sub.MarkCoverage.glyphs
        bases = sub.BaseCoverage.glyphs
        for mark, record in zip(marks, sub.MarkArray.MarkRecord):
            if mark not in script_of or mark not in ink:
                continue
            anchor = record.MarkAnchor
            m_left, m_bottom, m_right, m_top = ink[mark][:4]
            mark_center_y = (m_bottom + m_top) / 2.0
            side = "top" if mark_center_y > anchor.YCoordinate else "bottom"
            script = script_of[mark]
            data = out.setdefault((script, side), {"base_gap": [], "base_offset": [], "mark_gap": [], "mark_offset": []})
            gap = (m_bottom - anchor.YCoordinate) if side == "top" else (anchor.YCoordinate - m_top)
            data["mark_gap"].append(gap / upm)
            width = m_right - m_left
            if width > 0:
                data["mark_offset"].append((anchor.XCoordinate - (m_left + m_right) / 2.0) / width)
            for base, base_record in zip(bases, sub.BaseArray.BaseRecord):
                if script_of.get(base) != script or base not in ink:
                    continue
                base_anchor = base_record.BaseAnchor[record.Class]
                if base_anchor is None:
                    continue
                b_left, b_bottom, b_right, b_top, top_center, bottom_center = ink[base]
                width = b_right - b_left
                if side == "top":
                    data["base_gap"].append((base_anchor.YCoordinate - b_top) / upm)
                    center = top_center if top_center is not None else (b_left + b_right) / 2.0
                else:
                    data["base_gap"].append((b_bottom - base_anchor.YCoordinate) / upm)
                    center = bottom_center if bottom_center is not None else (b_left + b_right) / 2.0
                if width > 0:
                    data["base_offset"].append((base_anchor.XCoordinate - center) / width)
    for sub in lookups(font, ("mkmk",) + POSITIONING, 6):
        for mark2, record in zip(sub.Mark2Coverage.glyphs, sub.Mark2Array.Mark2Record):
            if mark2 not in script_of:
                continue
            ink2 = ink.get(mark2) or inks(font, [mark2]).get(mark2)
            if ink2 is None:
                continue
            for anchor in record.Mark2Anchor:
                if anchor is None:
                    continue
                side = "top" if anchor.YCoordinate > (ink2[1] + ink2[3]) / 2.0 else "bottom"
                data = out.setdefault((script_of[mark2], side), {"base_gap": [], "base_offset": [], "mark_gap": [], "mark_offset": []})
                edge = ink2[3] if side == "top" else ink2[1]
                data.setdefault("mark_to_mark", []).append(abs(anchor.YCoordinate - edge) / upm)
    return out, letters


def measure_shaped(path):
    """shaped.py's measures of one font: {"letters": {(script, side, code): (share, gap)}, "reph": (share,
    gap) or None, "i_matra": {code: reach}, "ligatures": {(side, part): [(share, gap)]}}."""
    import unicodedata
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    cmap = font["cmap"].getBestCmap() or {}
    shaper = shaped.Shaper(path)
    by_script = {}
    for code in cmap:
        script = dia.anchor_script(code)
        if script and unicodedata.category(chr(code)).startswith("L"):
            by_script.setdefault(script, []).append(code)
    letters = {}
    for script, codes in by_script.items():
        for (side, code), value in shaped.letter_placements(shaper, cmap, script, sorted(codes)).items():
            letters[(script, side, code)] = value
    return {"letters": letters, "reph": shaped.reph_placement(shaper, cmap),
            "i_matra": shaped.i_matra_reach(shaper, cmap), "ligatures": shaped.ligature_anchors(font)}


def fonts():
    from fontTools.ttLib import TTFont
    found, seen = [], set()
    for folder in tuple(dataset.FONT_DIRS) + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    font = TTFont(path, lazy=True)
                    family = dataset.family_of(font)
                    if family in seen or not dataset.license_of(font) or "GPOS" not in font:
                        continue
                    if not any(record.FeatureTag in POSITIONING for record in font["GPOS"].table.FeatureList.FeatureRecord):
                        continue
                    cmap = font["cmap"].getBestCmap() or {}
                    if not any(dia.anchor_script(code) for code in cmap):
                        continue
                    seen.add(family)
                    found.append((path, family))
                except Exception:
                    continue
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    per_font, letter_counts = [], {}
    landed, rephs, i_matras, ligatures = {}, [], {}, {}
    for path, family in fonts():
        try:
            measured, letters = measure(path)
        except Exception as exc:
            print("  %s: %s" % (family, exc))
            continue
        try:
            found = measure_shaped(path)
        except Exception as exc:
            print("  %s: not shaped: %s" % (family, exc))
            found = {"letters": {}, "reph": None, "i_matra": {}, "ligatures": {}}
        for key, value in found["letters"].items():
            landed.setdefault(key, []).append(value)
        if found["reph"] is not None:
            rephs.append(found["reph"])
        for code, reach in found["i_matra"].items():
            i_matras.setdefault(code, []).append(reach)
        for key, values in found["ligatures"].items():
            ligatures.setdefault(key, []).append(shaped.median_pair(values))
        for script, (has, attached) in letters.items():
            if not attached:
                continue  # marks of other scripts only: says nothing of this one's letters
            counts = letter_counts.setdefault(script, {})
            for code in has:
                count = counts.setdefault(code, [0, 0])
                count[0] += 1
                count[1] += code in attached
        if measured:
            per_font.append((family, measured))
            print("  %s: %s" % (family, ", ".join(sorted("%s %s" % key for key in measured))))
    model = {"format": 1, "fonts": len(per_font), "anchors": {}}
    keys = set(key for _, measured in per_font for key in measured)
    for script, side in sorted(keys):
        row, families = {}, 0
        for name in ("base_gap", "base_offset", "mark_gap", "mark_offset", "mark_to_mark"):
            medians = [statistics.median(m[(script, side)][name]) for _, m in per_font
                       if (script, side) in m and m[(script, side)].get(name)]
            if len(medians) >= MIN_FONTS:
                row[name] = round(statistics.median(medians), 4)
                families = max(families, len(medians))
        if row:
            row["fonts"] = families
            model["anchors"]["%s %s" % (script, side)] = row
    model["letters"] = {}
    for (script, side, code), values in sorted(landed.items()):
        if len(values) >= MIN_LETTER_FONTS:
            share, gap = shaped.median_pair(values)
            model["letters"].setdefault("%s %s" % (script, side), {})["%04X" % code] = [
                round(share, 3), round(gap, 4), len(values)]
    if len(rephs) >= MIN_FONTS:
        share, gap = shaped.median_pair(rephs)
        model["reph"] = {"share": round(share, 3), "gap": round(gap, 4), "fonts": len(rephs)}
    model["i_matra"] = dict(("%04X" % code, [round(statistics.median(values), 3), len(values)])
                            for code, values in sorted(i_matras.items()) if len(values) >= MIN_FONTS)
    model["ligature"] = {}
    for side in ("top", "bottom"):
        parts = [ligatures.get((side, part), []) for part in (0, 1)]
        if all(len(values) >= MIN_FONTS for values in parts):
            model["ligature"][side] = [[round(v, 4) for v in shaped.median_pair(values)] for values in parts]
            model["ligature"]["fonts"] = max(model["ligature"].get("fonts", 0), min(len(values) for values in parts))
    model["bases"] = {}
    for script, counts in sorted(letter_counts.items()):
        bases = sorted(code for code, (having, attaching) in counts.items()
                       if having >= MIN_FONTS and attaching >= BASE_SHARE * having)
        if bases:
            model["bases"][script] = ["%04X" % code for code in bases]
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print("%d fonts measured; letters placed: %s; reph from %d fonts; i-matra for %d consonants; ligatures: %s" % (
        len(per_font), dict((key, len(value)) for key, value in model["letters"].items()), len(rephs),
        len(model["i_matra"]), model["ligature"]))
    for key, row in sorted(model["anchors"].items()):
        print("  %s: %s" % (key, row))


if __name__ == "__main__":
    main()
