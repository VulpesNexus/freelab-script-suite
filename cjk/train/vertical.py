"""Learn how CJK fonts set their glyphs vertically, from the open-licensed fonts at hand (SIL Open Font
License and Apache License fonts only, as kerning/train/dataset.py finds them, its corpus folders
included: %LOCALAPPDATA%\\FreeLab\\corpus, where OFL fonts from Google Fonts were put).

For each font with a vert feature, every character it gives a vertical form (a single substitution of
its encoded glyph) is measured: how the vertical form was made from the horizontal glyph (turned a
quarter clockwise about the em's center, moved, or drawn anew), how far it sits from where that turn
or move alone would put it, in shares of the em, and where its ink's center sits in its square. vrt2 is compared with vert (the same forms, or
more: the proportional glyphs turned too), vpal is measured on each glyph as vertical text sets it
(its vertical form where it has one), and the vertical metrics: the advance height, where the vertical
origin sits against the typographic ascender, and vhea's ascender and descender.

The medians, per character, are cjk/vertical_model.json, with the characters the Unicode Character
Database's VerticalOrientation.txt (UAX #50) marks Tu or Tr (transformed typographically, upright or
turned): CJK Vertical builds and writes a font's vertical forms by them.

    python cjk/train/vertical.py [--ucd <VerticalOrientation.txt>] [--out <file.json>]

Python 3 with fonttools. Only the measurements leave the fonts; the fonts are not copied.
"""

import argparse
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
from palt import single_values  # noqa: E402

MODEL_FILE = os.path.join(HERE, os.pardir, "vertical_model.json")
UCD_FILE = os.path.join(dataset.CORPUS_DIR, "character_sets", "unicode-17.0.0-VerticalOrientation.txt")
MIN_FONTS = 3  # a character fewer fonts than this give a vertical form is left out
SNAP = 4.0  # outline points compared on a grid of this many units
MATCH = 0.9  # share of points that must fall together for a turn or a move


def vertical_orientation(path):
    """{code: "U", "R", "Tu", or "Tr"} from VerticalOrientation.txt (each code point it lists)."""
    found = {}
    with io.open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#")[0].strip()
            if not line:
                continue
            codes, value = [part.strip() for part in line.split(";")]
            first, _, last = codes.partition("..")
            for code in range(int(first, 16), int(last or first, 16) + 1):
                found[code] = value
    return found


def single_substitutions(font, tag):
    """{glyph: glyph} of a GSUB feature's single substitutions (the first lookup that names a glyph wins)."""
    if "GSUB" not in font or font["GSUB"].table.FeatureList is None:
        return {}
    gsub = font["GSUB"].table
    indexes = []
    for record in gsub.FeatureList.FeatureRecord:
        if record.FeatureTag == tag:
            indexes.extend(record.Feature.LookupListIndex)
    found = {}
    for index in sorted(set(indexes)):
        lookup = gsub.LookupList.Lookup[index]
        for sub in lookup.SubTable:
            kind = lookup.LookupType
            if kind == 7:
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if kind != 1:
                continue
            for source, target in sub.mapping.items():
                found.setdefault(source, target)
    return found


def points_of(glyph_set, name):
    """Every point of a glyph's outline (components drawn out), or None."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    pen = DecomposingRecordingPen(glyph_set)
    try:
        glyph_set[name].draw(pen)
    except Exception:
        return None
    points = [pt for _, args in pen.value for pt in args if isinstance(pt, tuple)]
    return points or None


def box_of(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def near_share(a, b):
    """The share of a's points that b has too, on the grid."""
    grid = set((round(x / SNAP), round(y / SNAP)) for x, y in b)
    near = 0
    for x, y in a:
        gx, gy = round(x / SNAP), round(y / SNAP)
        if any((gx + i, gy + j) in grid for i in (-1, 0, 1) for j in (-1, 0, 1)):
            near += 1
    return near / float(len(a) or 1)


def matches(a, b):
    """Whether two lists of points are one outline: about as many points, nearly all of each in the other
    (a point or two more or fewer: an overlap removed, a start point added)."""
    if abs(len(a) - len(b)) > max(2, 0.1 * max(len(a), len(b))):
        return False
    return near_share(a, b) >= MATCH and near_share(b, a) >= MATCH


def center_of(box):
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def similar(a, b, slack=0.2, units=40):
    return abs(a - b) <= max(units, slack * max(a, b))


TRANSFORMS = (
    ("moved", lambda cx, cy, x, y: (x, y)),
    ("rotated", lambda cx, cy, x, y: (cx + (y - cy), cy - (x - cx))),  # a quarter clockwise
    ("rotated flipped", lambda cx, cy, x, y: (cx - (y - cy), cy - (x - cx))),  # then mirrored across
    ("rotated ccw", lambda cx, cy, x, y: (cx - (y - cy), cy + (x - cx))))


def how_made(source, target, center, orientation=None):
    """How a vertical form was made from its glyph, and how far its ink's center sits from where that
    alone puts it: ("moved", dx, dy); ("rotated", dx, dy) turned a quarter clockwise about center (the
    em's); ("rotated flipped", ...) turned, then mirrored across; ("rotated ccw", ...); ("same", 0, 0)
    for a copy. A form drawn anew is taken by its ink's box: as wide as the glyph is tall and as tall as
    it is wide, turned; of the same size, moved; where both hold (a square mark), the character's
    Vertical_Orientation decides (orientation: "R" or "Tr" turned, else moved); its how then ends in
    " drawn".
    ("redrawn", 0, 0) where neither holds."""
    cx, cy = center
    tbox = box_of(target)
    tcenter = center_of(tbox)
    for how, turn in TRANSFORMS:
        turned = [turn(cx, cy, x, y) for x, y in source]
        scenter = center_of(box_of(turned))
        dx, dy = tcenter[0] - scenter[0], tcenter[1] - scenter[1]
        if matches([(x + dx, y + dy) for x, y in turned], target):
            if how == "moved" and abs(dx) < 1 and abs(dy) < 1:
                return "same", 0.0, 0.0
            return how, dx, dy
    sbox = box_of(source)
    sw, sh, tw, th = sbox[2] - sbox[0], sbox[3] - sbox[1], tbox[2] - tbox[0], tbox[3] - tbox[1]
    same, swapped = similar(sw, tw) and similar(sh, th), similar(sw, th) and similar(sh, tw)
    if same and swapped:
        how = "rotated" if orientation in ("R", "Tr") else "moved"
    elif same or swapped:
        how = "moved" if same else "rotated"
    else:
        return "redrawn", 0.0, 0.0
    turn = dict(TRANSFORMS)[how]
    scenter = center_of(box_of([turn(cx, cy, x, y) for x, y in source]))
    return how + " drawn", tcenter[0] - scenter[0], tcenter[1] - scenter[1]


def vertical_box(font, name, glyph_box, upm):
    """(origin y, advance height) of a glyph in vertical text: VORG's origin (CFF), else vmtx's top
    sidebearing over the ink, else the typographic ascender and the em."""
    ascender = font["OS/2"].sTypoAscender if "OS/2" in font else upm * 0.88
    height = upm
    if "vmtx" in font and name in font["vmtx"].metrics:
        height, tsb = font["vmtx"].metrics[name]
        if "VORG" in font:
            vorg = font["VORG"]
            return vorg.VOriginRecords.get(name, vorg.defaultVertOriginY), height
        if glyph_box is not None:
            return tsb + glyph_box[3], height
    return ascender, height


def measure(font, orientation=None):
    """One font's measurements: {"vert": {code: (how, dx, dy)}, "vrt2": {...}, "vpal": {code: (top,
    bottom)}, "metrics": {...}}, in shares of the em."""
    upm = float(font["head"].unitsPerEm)
    cmap = font["cmap"].getBestCmap() or {}
    glyph_set = font.getGlyphSet()
    vert, vrt2 = single_substitutions(font, "vert"), single_substitutions(font, "vrt2")
    vpal = single_values(font, "vpal")
    hmtx = font["hmtx"].metrics
    ascender = font["OS/2"].sTypoAscender if "OS/2" in font else upm * 0.88
    out = {"vert": {}, "vrt2": {}, "vrt2_more": {}, "vpal": {}, "metrics": {}, "has": set(cmap)}
    for code, name in sorted(cmap.items()):
        target = vert.get(name)
        if target is None or target == name:
            continue
        source_points, target_points = points_of(glyph_set, name), points_of(glyph_set, target)
        if not source_points or not target_points:
            out["vert"][code] = ("redrawn", 0.0, 0.0, None)  # (a space, or nothing to compare)
            continue
        origin, height = vertical_box(font, name, box_of(source_points), upm)
        center = (hmtx[name][0] / 2.0, origin - height / 2.0)
        how, dx, dy = how_made(source_points, target_points, center, (orientation or {}).get(code))
        # where the form's ink sits in its square: its center, in shares of the advance across and of the
        # advance height up from the square's bottom
        tcenter = center_of(box_of(target_points))
        place = (round(tcenter[0] / float(hmtx[name][0] or upm), 4), round((tcenter[1] - (origin - height)) / height, 4))
        out["vert"][code] = (how, round(dx / upm, 4), round(dy / upm, 4), place)
    for code, name in cmap.items():
        target = vrt2.get(name)
        if target is not None and target != name:
            if code in out["vert"] or vert.get(name):
                out["vrt2"][code] = vert.get(name) == target
            else:
                out["vrt2_more"][code] = True
    # vpal, on the glyph vertical text sets (the vertical form where the font has one)
    for code, name in cmap.items():
        if not kind_of(code) or kind_of(code) == "hangul":
            continue
        shown = vert.get(name) or name
        if shown not in vpal:
            continue
        points = points_of(glyph_set, shown)
        if not points:
            continue
        box = box_of(points)
        origin, height = vertical_box(font, shown, box, upm)
        _, ypl, _, yadv = vpal[shown]
        top, bottom = (origin - box[3] - ypl) / upm, (height + yadv - (origin - box[1]) + ypl) / upm
        out["vpal"][code] = (round(top, 4), round(bottom, 4))
    # vertical metrics: the ideographs' (and kana's) advance height and origin, vhea's lines
    heights, origins = [], []
    for code, name in cmap.items():
        if 0x4E00 <= code <= 0x9FFF or 0x3041 <= code <= 0x30FA:
            points = points_of(glyph_set, name) if len(heights) < 400 else None
            if points:
                origin, height = vertical_box(font, name, box_of(points), upm)
                heights.append(height / upm)
                origins.append((origin - ascender) / upm)
    if heights:
        out["metrics"]["advance_height"] = statistics.median(heights)
        out["metrics"]["origin_over_ascender"] = statistics.median(origins)
    for latin in ("A", "a"):
        name = cmap.get(ord(latin))
        if name and "vmtx" in font and name in font["vmtx"].metrics:
            out["metrics"]["latin_advance_height"] = font["vmtx"].metrics[name][0] / upm
            break
    if "vhea" in font:
        vhea = font["vhea"]
        out["metrics"]["vhea_ascent"] = vhea.ascent / upm
        out["metrics"]["vhea_descent"] = vhea.descent / upm
        out["metrics"]["vhea_line_gap"] = vhea.lineGap / upm
    out["metrics"]["vrt2"] = 1.0 if vrt2 else 0.0
    out["metrics"]["vrt2_turns_more"] = 1.0 if len(out["vrt2_more"]) >= 10 else 0.0
    # vrt2's turned proportional glyphs: how they are turned (about the em's square), their widths and heights
    out["turned"] = {}
    vmtx = font["vmtx"].metrics if "vmtx" in font else {}
    if out["metrics"]["vrt2_turns_more"]:
        center = (upm / 2.0, ascender - upm / 2.0)
        for code in out["vrt2_more"]:
            name = cmap[code]
            target = vrt2[name]
            source_points, target_points = points_of(glyph_set, name), points_of(glyph_set, target)
            if not source_points or not target_points or not hmtx[name][0]:
                continue
            how, dx, dy = how_made(source_points, target_points, center, "R")
            height = vmtx[target][0] / float(hmtx[name][0]) if target in vmtx else None
            out["turned"][code] = (how, round(dx / upm, 4), round(dy / upm, 4), hmtx[target][0] / upm, height)
    out["vkrn"] = dict(((a, b), value / upm) for (a, b), value in pair_codes(font, cmap, vert).items())
    return out


def pair_values(font, tag):
    """{(first glyph, second glyph): the first's y advance change} of a GPOS feature's pair adjustments
    (glyph pairs and class pairs; the first lookup that names a pair wins)."""
    if "GPOS" not in font or font["GPOS"].table.FeatureList is None:
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
            kind = lookup.LookupType
            if kind == 9:
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if kind != 2:
                continue
            if sub.Format == 1:
                for first, pair_set in zip(sub.Coverage.glyphs, sub.PairSet):
                    for record in pair_set.PairValueRecord:
                        found.setdefault((first, record.SecondGlyph), getattr(record.Value1, "YAdvance", 0) or 0)
            else:
                second_classes = {}
                for glyph, number in sub.ClassDef2.classDefs.items():
                    second_classes.setdefault(number, []).append(glyph)
                first_classes = sub.ClassDef1.classDefs
                for first in sub.Coverage.glyphs:
                    row = sub.Class1Record[first_classes.get(first, 0)]
                    for number, record in enumerate(row.Class2Record):
                        value = getattr(record.Value1, "YAdvance", 0) or 0
                        if value:
                            for second in second_classes.get(number, ()):
                                found.setdefault((first, second), value)
    return found


# Where a CJK font encodes a glyph a second time (radicals, compatibility ideographs), as the shared
# module's main_code has them
DUPLICATE_RANGES = ((0x2E80, 0x2EFF), (0x2F00, 0x2FDF), (0xF900, 0xFAFF), (0x2F800, 0x2FA1F))


def is_duplicate(code):
    return any(low <= code <= high for low, high in DUPLICATE_RANGES)


def pair_codes(font, cmap, vert):
    """{(first code, second code): value} of a font's vkrn, each glyph read as the character it sets
    (itself, or the character whose vertical form it is): a glyph encoded twice by the character it stands
    for, not a radical or compatibility duplicate of it (日 by U+65E5, not the Kangxi radical U+2F47)."""
    reverse = {}
    for code, name in sorted(cmap.items(), key=lambda item: (is_duplicate(item[0]), item[0])):
        reverse.setdefault(name, code)
    for source, target in vert.items():
        if source in reverse:
            reverse.setdefault(target, reverse[source])
    found = {}
    for (first, second), value in pair_values(font, "vkrn").items():
        if first in reverse and second in reverse and value:
            found.setdefault((reverse[first], reverse[second]), value)
    return found


class SamplingPen(object):
    """Points along a glyph's outline, its curves sampled (components drawn through the glyph set)."""

    def __init__(self, glyph_set, steps=8):
        from fontTools.pens.basePen import BasePen
        owner = self

        class Pen(BasePen):
            def _moveTo(self, pt):
                owner.points.append(pt)

            def _lineTo(self, pt):
                start = self._getCurrentPoint()
                for i in range(1, steps + 1):
                    t = i / float(steps)
                    owner.points.append((start[0] + (pt[0] - start[0]) * t, start[1] + (pt[1] - start[1]) * t))

            def _curveToOne(self, p1, p2, p3):
                p0 = self._getCurrentPoint()
                for i in range(1, steps + 1):
                    t = i / float(steps)
                    u = 1 - t
                    owner.points.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d
                                              for a, b, c, d in zip(p0, p1, p2, p3)))

            def _qCurveToOne(self, p1, p2):
                p0 = self._getCurrentPoint()
                for i in range(1, steps + 1):
                    t = i / float(steps)
                    u = 1 - t
                    owner.points.append(tuple(u * u * a + 2 * u * t * b + t * t * c for a, b, c in zip(p0, p1, p2)))

        self.points = []
        self.pen = Pen(glyph_set)


def ink_bands(glyph_set, name, width, bands):
    """[(y min, y max) or None] of a glyph's ink in each of bands equal bands of [0, width] across."""
    sampler = SamplingPen(glyph_set)
    try:
        glyph_set[name].draw(sampler.pen)
    except Exception:
        return None
    found = [None] * bands
    for x, y in sampler.points:
        index = int(x * bands // width)
        if 0 <= index < bands:
            low, high = found[index] or (y, y)
            found[index] = (min(low, y), max(high, y))
    return found if any(found) else None


VKRN_CAPS = (0.15, 0.2, 0.25, 0.3, 0.4)  # the white counted per band at most, tried: the best fit is kept
MIN_VKRN_FONTS = 5  # a pair is kerned where at least this many fonts kern it


def vkrn_samples(family, path, index, pairs):
    """For one font that kerns vertically: per cap, [(the font's usual white minus the pair's, the
    pair's vkrn)] over the pairs it has both glyphs of (0 where it does not kern a pair), in font units,
    with the em."""
    import freelab_cjk_vertical as cv
    font = load(path, index)
    try:
        upm = float(font["head"].unitsPerEm)
        cmap = font["cmap"].getBestCmap() or {}
        vert = single_substitutions(font, "vert")
        vpal = single_values(font, "vpal")
        values = pair_codes(font, cmap, vert)
        glyph_set = font.getGlyphSet()
        placed = {}
        for code in set(c for pair in pairs for c in pair):
            name = cmap.get(code)
            if not name:
                continue
            shown = vert.get(name) or name
            bands = ink_bands(glyph_set, shown, upm, cv.VKRN_BANDS)
            if bands is None:
                continue
            box = (0, min(b[0] for b in bands if b), 0, max(b[1] for b in bands if b))
            origin, height = vertical_box(font, shown, box, upm)
            value = vpal.get(shown)
            placed[code] = cv.placed_profile(bands, origin, height, (value[1], value[3]) if value else (0, 0))
        samples = {}
        for cap in VKRN_CAPS:
            gaps = dict((pair, cv.pair_gap(placed[pair[0]], placed[pair[1]], cap * upm)) for pair in pairs
                        if pair[0] in placed and pair[1] in placed)
            gaps = dict((pair, gap) for pair, gap in gaps.items() if gap is not None)
            if not gaps:
                continue
            scores = cv.gap_scores(gaps)
            samples[cap] = [(scores[pair], values.get(pair, 0.0) / upm) for pair in gaps]
        return samples
    finally:
        font.close()


def fit_vkrn(per_font_samples):
    """The cap and factor that predict the fonts' vkrn best: per cap, the factor from a pair's score (how
    much whiter than the font's usual it is, in the font's own spread: gap_scores) to its value, least
    squares through 0 over the pairs the fonts kern (the many they leave at 0 would shrink it to
    nothing), the cap with the best correlation over every pair; with the median error on the pairs
    they kern (shares of the em)."""
    best = None
    for cap in VKRN_CAPS:
        points = [p for samples in per_font_samples for p in samples.get(cap, [])]
        if not points:
            continue
        kerned = [(x, y) for x, y in points if y]
        sxx = sum(x * x for x, _ in kerned)
        sxy = sum(x * y for x, y in kerned)
        if not sxx:
            continue
        factor = sxy / sxx
        mx, my = statistics.mean(x for x, _ in points), statistics.mean(y for _, y in points)
        sx = sum((x - mx) ** 2 for x, _ in points) ** 0.5
        sy = sum((y - my) ** 2 for _, y in points) ** 0.5
        r = sum((x - mx) * (y - my) for x, y in points) / (sx * sy) if sx and sy else 0.0
        errors = [abs(factor * x - y) for x, y in points if y]
        entry = {"cap": cap, "factor": round(factor, 4), "r": round(r, 3),
                 "error": round(statistics.median(errors), 4) if errors else None, "samples": len(points)}
        if best is None or r > best["r"]:
            best = entry
    return best


def fonts():
    """(family, path, index in a collection or None) of the open-licensed fonts with vert, one per family."""
    from fontTools.ttLib import TTCollection, TTFont
    found, seen = [], set()
    for path in dataset.font_files(("latin", "kana")):
        try:
            collection = path.lower().endswith((".ttc", ".otc"))
            members = TTCollection(path, lazy=True).fonts if collection else [TTFont(path, lazy=True)]
        except Exception:
            continue
        for index, font in enumerate(members):
            try:
                if not dataset.license_of(font) or "GSUB" not in font or font["GSUB"].table.FeatureList is None:
                    continue
                tags = set(r.FeatureTag for r in font["GSUB"].table.FeatureList.FeatureRecord)
                family = dataset.family_of(font)
                if "vert" in tags and family not in seen:
                    seen.add(family)
                    found.append((family, path, index if collection else None))
            except Exception:
                continue
    return found


def load(path, index):
    from fontTools.ttLib import TTFont
    return TTFont(path, fontNumber=index) if index is not None else TTFont(path)


# The kinds of making that count as one: turned (any way, exactly or drawn anew), or moved
FAMILY = {"rotated": "rotated", "rotated flipped": "rotated", "rotated ccw": "rotated", "rotated drawn": "rotated",
          "moved": "moved", "moved drawn": "moved"}


def median_pair(values):
    return [round(statistics.median(a for a, _ in values), 4), round(statistics.median(b for _, b in values), 4)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ucd", default=UCD_FILE)
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    orientation = vertical_orientation(args.ucd)
    per_font = []
    for family, path, index in fonts():
        try:
            font = load(path, index)
            per_font.append(measure(font, orientation))
            per_font[-1]["file"] = (family, path, index)
            # (kept small: the ideographs and Hangul syllables, which no font gives a vertical form, left out)
            per_font[-1]["has"] = set(code for code in per_font[-1]["has"]
                                      if not (0x3400 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7A3 or code >= 0x20000))
            font.close()
            print("  %s: %d vertical forms" % (family, len(per_font[-1]["vert"])))
        except Exception as exc:
            print("  %s: %s" % (family, exc))
    print("%d families with vert" % len(per_font))
    model = {"format": 1, "fonts": len(per_font), "vert": {}, "vpal": {}, "metrics": {}, "vrt2_more": {},
             "orientation": {},
             "source": "Measured from open-licensed fonts (SIL OFL, Apache) by cjk/train/vertical.py; orientation: "
                       "Unicode Character Database 17.0.0, VerticalOrientation.txt (Unicode License V3)."}
    codes = set(code for data in per_font for code in data["vert"])
    for code in sorted(codes):
        made = [data["vert"][code] for data in per_font if code in data["vert"]]
        if len(made) < MIN_FONTS:
            continue
        families = {}
        for how, dx, dy, place in made:
            families.setdefault(FAMILY.get(how, how), []).append((how, dx, dy, place))
        family = max(sorted(families), key=lambda key: len(families[key]))
        votes = families[family]
        having = sum(1 for data in per_font if code in data["has"])  # (the fonts with the character at all)
        entry = {"fonts": len(made), "agree": round(len(votes) / float(len(made)), 3),
                 "share": round(len(made) / float(having or 1), 3),
                 "exact": round(sum(1 for how, _, _, _ in votes if not how.endswith(" drawn")) / float(len(made)), 3)}
        if family == "rotated":  # (which turn: the one the fonts that turn it exactly use most)
            exact = [how for how, _, _, _ in votes if how in ("rotated", "rotated flipped", "rotated ccw")]
            entry["how"] = max(sorted(set(exact)), key=exact.count) if exact else "rotated"
        else:
            entry["how"] = family
        if family in ("rotated", "moved"):
            entry["move"] = median_pair([(dx, dy) for _, dx, dy, _ in votes])
            places = [place for _, _, _, place in votes if place is not None]
            if places:
                entry["place"] = median_pair(places)
        vrt2 = [data["vrt2"][code] for data in per_font if code in data["vrt2"]]
        if vrt2:
            entry["vrt2"] = round(sum(1 for same in vrt2 if same) / float(len(vrt2)), 3)
        model["vert"]["U+%04X" % code] = entry
    # The orientation of each character with a form, and of every one transformed (Tu, Tr)
    for code, value in sorted(orientation.items()):
        if value in ("Tu", "Tr") or "U+%04X" % code in model["vert"]:
            model["orientation"]["U+%04X" % code] = value
    vpal_codes = set(code for data in per_font for code in data["vpal"])
    by_kind = {}
    for code in sorted(vpal_codes):
        values = [data["vpal"][code] for data in per_font if code in data["vpal"]]
        by_kind.setdefault(kind_of(code), []).extend(values)
        if len(values) >= MIN_FONTS:
            model["vpal"]["U+%04X" % code] = median_pair(values)
    for kind, values in sorted(by_kind.items()):
        if len(values) >= MIN_FONTS:
            model["vpal"][kind] = median_pair(values)
    keys = set(key for data in per_font for key in data["metrics"])
    for key in sorted(keys):
        values = [data["metrics"][key] for data in per_font if key in data["metrics"]]
        model["metrics"][key] = round(statistics.median(values) if not key.startswith("vrt2") else
                                      sum(values) / float(len(values)), 4)
    more = {}
    for data in per_font:
        for code in data["vrt2_more"]:
            more[code] = more.get(code, 0) + 1
    model["vrt2_more"] = dict(("U+%04X" % code, round(count / float(len(per_font)), 3))
                              for code, count in sorted(more.items()) if count >= MIN_FONTS)
    # vrt2's turned proportional glyphs, among the fonts that turn them: which characters (the share of
    # those fonts with the character that turn it), how, and their width and height
    turning = [data for data in per_font if data["metrics"].get("vrt2_turns_more")]
    entries = [entry for data in turning for entry in data["turned"].values()]
    if turning and entries:
        codes = {}
        for code in set(c for data in turning for c in data["turned"]):
            having = sum(1 for data in turning if code in data["has"])
            count = sum(1 for data in turning if code in data["turned"])
            if count >= MIN_FONTS:
                codes["U+%04X" % code] = round(count / float(having or 1), 3)
        hows = [FAMILY.get(how, how) for how, _, _, _, _ in entries]
        exact = [how for how, _, _, _, _ in entries if how in ("rotated", "rotated flipped", "rotated ccw")]
        model["turned"] = {
            "fonts": len(turning), "codes": codes,
            "agree": round(hows.count("rotated") / float(len(hows)), 3),
            "how": max(sorted(set(exact)), key=exact.count) if exact else "rotated",
            "move": median_pair([(dx, dy) for how, dx, dy, _, _ in entries if FAMILY.get(how) == "rotated"]),
            "advance": round(statistics.median(advance for _, _, _, advance, _ in entries), 4),
            "height": round(statistics.median(h for _, _, _, _, h in entries if h), 4)}
        print("turned: %d fonts, %d characters" % (len(turning), len(codes)))
    # vkrn: the pairs the fonts kern, and how a pair's white predicts their values
    counts = {}
    for data in per_font:
        for pair in data["vkrn"]:
            counts[pair] = counts.get(pair, 0) + 1
    pairs = sorted(pair for pair, count in counts.items() if count >= MIN_VKRN_FONTS)
    kerning = [data for data in per_font if sum(1 for pair in data["vkrn"] if pair in counts and counts[pair] >= MIN_VKRN_FONTS) >= 10]
    samples, values = [], []
    for data in kerning:
        try:
            samples.append(vkrn_samples(data["file"][0], data["file"][1], data["file"][2], pairs))
        except Exception as exc:
            print("  vkrn %s: %s" % (data["file"][0], exc))
        values.extend(abs(value) for pair, value in data["vkrn"].items() if pair in counts and counts[pair] >= MIN_VKRN_FONTS)
    fit = fit_vkrn(samples) if samples else None
    if values:
        values.sort()
        # The pairs' values the tool writes: each the median of the fonts that kern it (shares of the em).
        # The fit of the white between a pair (geometry) is kept for the record: too weak to use.
        table = {}
        for pair in pairs:
            found = [data["vkrn"][pair] for data in per_font if pair in data["vkrn"]]
            table["%04X %04X" % pair] = [round(statistics.median(found), 4), len(found)]
        model["vkrn"] = {"fonts": len(kerning), "values": table, "geometry": fit,
                         "threshold": round(values[len(values) // 4], 4), "most": round(values[int(len(values) * 0.95)], 4)}
        fit = fit or {}
        print("vkrn: %d fonts, %d pairs; the white between a pair: cap %s, factor %s, r %s, median error %s em" % (
            len(kerning), len(pairs), fit.get("cap"), fit.get("factor"), fit.get("r"), fit.get("error")))
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print("wrote %s: %d vertical forms, %d vpal keys" % (os.path.basename(args.out), len(model["vert"]), len(model["vpal"])))


if __name__ == "__main__":
    main()
