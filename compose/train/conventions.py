"""Which mark the open-licensed fonts draw on each letter Glyph Compose builds, against Unicode's
canonical decomposition (Unicode decomposes Latvian's k with a comma below with a cedilla, and the
Czech and Slovak d, t, l with an apostrophe-like caron with a caron).

For every letter of Glyph Compose's sets that decomposes into a letter and marks, in every open-licensed
font at hand (one per family, SIL Open Font License or Apache License, as kerning/train/dataset.py
finds them, plus FreeLab's corpus folder), each mark is told apart:
- in a composite glyph, by its components' code points and names (uni0326, commaaccentcomb,
  caroncomb.alt, quoteright, commaaccentrotate), and where they sit (a comma at the top right of a
  stem is a vertical caron, a comma above is turned when rotated);
- in a glyph of outlines, by finding the outlines of one of the font's mark glyphs in it, shape for
  shape (the same points, moved), and where they sit.
It prints, per letter, Unicode's mark, the mark most fonts draw, and how many fonts draw it; and the
median placement of the marks fonts draw for Unicode's (the vertical caron's gap to the stem and height,
the turned comma's gap above the letter and offset), which freelab_glyph_compose.py's CONVENTIONS and
VERTICAL_CARON carry.

    python compose/train/conventions.py [--limit N] [--json <file>]

Python 3 with fonttools. Only the counts and measurements leave the fonts; the fonts are not copied.
"""

import argparse
import collections
import glob
import io
import json
import os
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "kerning", "train"))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import dataset  # noqa: E402  (the corpus's folders and its license check)
import freelab_glyph_compose as ac  # noqa: E402  (the marks, the sets)

TOLERANCE = 0.004  # of the em: two outlines within this of each other, point for point, are the same shape
BAND = ac.BAND_SHARE

# A mark glyph's identity by its code point: the marks Unicode encodes, their spacing forms, and the
# glyphs fonts draw for a comma below, a vertical caron, or a turned comma
CODE_IDENTITY = dict((code, root) for code, root in ac.MARKS.items())
CODE_IDENTITY.update(dict((spacing, ac.MARKS[code]) for code, spacing in ac.SPACING_MARKS.items()))
CODE_IDENTITY.update({0x0326: "comma", 0xF6C3: "comma", 0x002C: "comma", 0x2019: "comma", 0x02BC: "comma",
                      0x0315: "comma", 0x0027: "comma", 0x0312: "turnedcomma", 0x02BB: "turnedcomma",
                      0x2018: "turnedcomma", 0x0327: "cedilla", 0x00B8: "cedilla", 0x0384: "acute", 0x1FFD: "acute",
                      0x1FEF: "grave", 0x0385: "dieresistonos", 0x00B0: "ring"})
NAME_PREFIXES = ((("caroncomb.alt", "caron.alt", "uni030c.alt", "caronvertical", "caroncommaaccent", "caronslovak",
                   "caron.salt", "caroncomb.salt", "caronalt", "caronright"), "caronvertical"),
                 (("commaaccentrotate", "commaturned", "uni0312", "quoteleft", "uni02bb"), "turnedcomma"),
                 (("commaaccent", "commabelow", "uni0326", "unif6c3", "quoteright", "uni02bc", "uni0315",
                   "commaaboveright", "apostrophe", "comma"), "comma"),
                 (("cedilla", "uni0327", "uni00b8"), "cedilla"),
                 (("tonos", "oxia"), "acute"), (("varia",), "grave"), (("brevecomb-cy", "breve-cy"), "breve"))
# The marks tell apart by where they sit once found (a comma below, beside a stem's top, or above)
PLACED = {"comma": {"below": "commaaccent", "beside": "caronvertical", "above": "commaabove"},
          "turnedcomma": {"below": "commaturnedbelow", "beside": "commaturnedabove", "above": "commaturnedabove"},
          "caronvertical": {"below": "commaaccent", "beside": "caronvertical", "above": "caronvertical"}}
WATCHED = {"commaaccent", "caronvertical", "commaturnedabove"}  # the identities whose placements are measured


def name_identity(name):
    """A mark glyph's identity by its name (comma, turnedcomma, caronvertical, cedilla, acute...), or None."""
    low = name.lower()
    for prefixes, identity in NAME_PREFIXES:
        if low.startswith(prefixes):
            return identity
    root = ac.mark_key(name)
    if root in ac.MARKS.values():
        return root
    if low.startswith("uni") and len(low) >= 7:
        try:
            return CODE_IDENTITY.get(int(low[3:7], 16))
        except ValueError:
            return None
    return None


def contours_of(glyphset, name):
    """[(points relative to its box's corner, box)] of a glyph's contours, components decomposed."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    pen = DecomposingRecordingPen(glyphset)
    glyphset[name].draw(pen)
    found, points = [], []
    for operator, args in pen.value:
        if operator == "moveTo":
            points = list(args)
        elif operator in ("lineTo", "qCurveTo", "curveTo"):
            points.extend(p for p in args if p is not None)
        elif operator in ("closePath", "endPath"):
            if points:
                xs, ys = [p[0] for p in points], [p[1] for p in points]
                box = (min(xs), min(ys), max(xs), max(ys))
                found.append((tuple((x - box[0], y - box[1]) for x, y in points), box))
            points = []
    return found


def same_shape(a, b, tolerance):
    return len(a) == len(b) and all(abs(p[0] - q[0]) <= tolerance and abs(p[1] - q[1]) <= tolerance for p, q in zip(a, b))


def find_shape(target, template, tolerance):
    """(dx, dy) moving the template's contours onto contours of the target, all of them, or None."""
    if not template:
        return None
    first_shape, first_box = template[0]
    for shape, box in target:
        if not same_shape(shape, first_shape, tolerance):
            continue
        dx, dy = box[0] - first_box[0], box[1] - first_box[1]
        if all(any(same_shape(s, t_shape, tolerance) and abs(b[0] - (t_box[0] + dx)) <= tolerance
                   and abs(b[1] - (t_box[1] + dy)) <= tolerance for s, b in target)
               for t_shape, t_box in template[1:]):
            return dx, dy
    return None


def box_of(contours, dx=0.0, dy=0.0):
    if not contours:
        return None
    return (min(c[1][0] for c in contours) + dx, min(c[1][1] for c in contours) + dy,
            max(c[1][2] for c in contours) + dx, max(c[1][3] for c in contours) + dy)


FLAT_STEPS = 16  # each curve flattened into this many lines


def segments_of(glyphset, name):
    """[((x0, y0), (x1, y1))] of a glyph's outline, curves flattened (components decomposed)."""
    from fontTools.pens.basePen import BasePen

    class Flattening(BasePen):
        def __init__(self):
            BasePen.__init__(self, glyphset)
            self.found, self.start = [], None

        def _moveTo(self, p):
            self.start = p

        def _lineTo(self, p):
            self.found.append((self._getCurrentPoint(), p))

        def _curveToOne(self, p1, p2, p3):
            p0 = self._getCurrentPoint()
            last = p0
            for i in range(1, FLAT_STEPS + 1):
                t = i / float(FLAT_STEPS)
                u = 1 - t
                q = tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, p1, p2, p3))
                self.found.append((last, q))
                last = q

        def _qCurveToOne(self, p1, p2):
            p0 = self._getCurrentPoint()
            last = p0
            for i in range(1, FLAT_STEPS + 1):
                t = i / float(FLAT_STEPS)
                u = 1 - t
                q = tuple(u * u * a + 2 * u * t * b + t * t * c for a, b, c in zip(p0, p1, p2))
                self.found.append((last, q))
                last = q

        def _closePath(self):
            current = self._getCurrentPoint()
            if self.start is not None and current != self.start:
                self.found.append((current, self.start))

    pen = Flattening()
    glyphset[name].draw(pen)
    return pen.found


def band_xs(segments, y0, y1):
    """The x of the outline's ink between y0 and y1 (as FontLab's outline cut to that band reaches)."""
    xs = []
    for (ax, ay), (bx, by) in segments:
        for px, py in ((ax, ay), (bx, by)):
            if y0 <= py <= y1:
                xs.append(px)
        for y in (y0, y1):
            if (ay - y) * (by - y) < 0:
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
    return xs


def ink_of(glyphset, name):
    """(left, bottom, right, top, top band center, bottom band center, bottom band right, top band right) of a
    glyph's outline, its bands cut as Glyph Compose cuts them in FontLab (the outline's top and bottom fifth,
    curves and all: not its points, whose off-curve handles reach past the ink), or None for an empty glyph."""
    segments = segments_of(glyphset, name)
    if not segments:
        return None
    xs = [p[0] for s in segments for p in s]
    ys = [p[1] for s in segments for p in s]
    left, bottom, right, top = min(xs), min(ys), max(xs), max(ys)
    band = (top - bottom) * BAND
    upper = band_xs(segments, top - band, top + 1) or [left, right]
    lower = band_xs(segments, bottom - 1, bottom + band) or [left, right]
    return (left, bottom, right, top, (min(upper) + max(upper)) / 2.0, (min(lower) + max(lower)) / 2.0, max(lower),
            max(upper))


def band_of(glyphset, name):
    """(top band center, top band right, bottom band center) of a glyph's outline."""
    found = ink_of(glyphset, name)
    return found[4], found[7], found[5]


def where(mark, base, top_right, upm):
    """"below", "beside" (a stem's top right), or "above": where a mark's box sits by the letter's."""
    middle = (mark[1] + mark[3]) / 2.0
    if mark[3] <= base[1] + 0.05 * upm or middle < (base[1] + base[3]) / 2.0 - 0.1 * upm and mark[1] < base[1]:
        return "below"
    if mark[1] < base[3] - 0.04 * upm and mark[0] >= top_right - 0.04 * upm:
        return "beside"
    return "above"


def fonts(limit=0):
    """(path, family) of the open-licensed fonts at hand, one per family."""
    from fontTools.ttLib import TTFont
    found, families = [], set()
    for folder in tuple(dataset.FONT_DIRS) + (dataset.CORPUS_DIR,):
        for path in sorted(glob.glob(os.path.join(folder, "*.ttf")) + glob.glob(os.path.join(folder, "*.otf"))):
            try:
                font = TTFont(path, lazy=True)
                if not dataset.license_of(font):
                    continue
                family = dataset.family_of(font)
            except Exception:
                continue
            if family in families:
                continue
            families.add(family)
            found.append((path, family))
            if limit and len(found) >= limit:
                return found
    return found


def letters():
    """The letters of Glyph Compose's sets that decompose into a letter and marks."""
    found = []
    for low, high in dict((key, ranges) for key, _, ranges in ac.SETS)["all"]:
        for code in range(low, high):
            ch = chr(code)
            decomposed = unicodedata.normalize("NFD", ch)
            if len(decomposed) >= 2 and unicodedata.category(ch).startswith("L") and decomposed[0].isalpha():
                found.append(code)
    return found


def measure_font(path):
    """{code: [identity per mark, or "joined", or None]}, and the watched marks' placements [(identity,
    letter, values)]."""
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    upm = float(font["head"].unitsPerEm)
    cmap = font.getBestCmap() or {}
    glyphset = font.getGlyphSet()
    glyf = font["glyf"] if "glyf" in font else None
    reverse = {}
    for code, name in cmap.items():
        reverse.setdefault(name, code)

    def identity(name):
        code = reverse.get(name)
        return (CODE_IDENTITY.get(code) if code is not None else None) or name_identity(name)

    templates = collections.defaultdict(list)  # identity: [contours of each mark glyph of it]
    for name in font.getGlyphOrder():
        found = identity(name)
        if found and reverse.get(name) not in (0x0027,) and (reverse.get(name) is None or reverse.get(name) in CODE_IDENTITY):
            try:
                contours = contours_of(glyphset, name)
            except Exception:
                continue
            if contours and len(contours) <= 4:
                templates[found].append((name, contours))
    cache = {}

    def contours(name):
        if name not in cache:
            try:
                cache[name] = contours_of(glyphset, name)
            except Exception:
                cache[name] = []
        return cache[name]

    results, placed = {}, []
    tolerance = TOLERANCE * upm
    for code in letters():
        name = cmap.get(code)
        if name is None:
            continue
        ch = chr(code)
        decomposed = unicodedata.normalize("NFD", ch)
        base_char, marks = decomposed[0], [ord(c) for c in decomposed[1:]]
        base_names = [cmap.get(ord(base_char))] + ([cmap.get(0x0131)] if base_char == "i" else []) + \
            ([cmap.get(0x0237)] if base_char == "j" else [])
        base_names = [n for n in base_names if n]
        if not base_names:
            continue
        found = [None] * len(marks)
        boxes = [None] * len(marks)
        glyph = glyf[name] if glyf is not None else None
        base_name, base_dx, base_dy = base_names[0], 0.0, 0.0
        if glyph is not None and glyph.isComposite():
            components = list(glyph.components)
            bases = [c for c in components if c.glyphName in base_names]
            others = [c for c in components if c.glyphName not in base_names]
            if bases:
                base_name, base_dx, base_dy = bases[0].glyphName, bases[0].x, bases[0].y
            if not bases or len(others) != len(marks):
                results[code] = ["joined"] * len(marks) if bases else [None] * len(marks)
                continue
            base_box = box_of(contours(base_name), base_dx, base_dy)
            if base_box is None:
                continue
            top_center, top_right, bottom_center = band_of(glyphset, base_name)
            wanted = [ac.MARKS.get(m) for m in marks]
            ids = []
            for c in others:
                kind = identity(c.glyphName)
                transform = getattr(c, "transform", None)
                turned = transform is not None and transform[0][0] < 0 and transform[1][1] < 0
                if turned and kind in ("comma", "turnedcomma"):
                    kind = "turnedcomma" if kind == "comma" else "comma"
                box = box_of(contours(c.glyphName), c.x, c.y) if not transform else None
                if kind in PLACED and box is not None:
                    kind = PLACED[kind][where(box, base_box, top_right + base_dx, upm)]
                ids.append((kind, box))
            left = list(range(len(ids)))
            for at, want in enumerate(wanted):  # each mark of the decomposition to a component like it, else in order
                pick = next((k for k in left if ids[k][0] == want), None)
                if pick is None:
                    pick = next((k for k in left if ids[k][0] not in wanted), left[0])
                left.remove(pick)
                found[at], boxes[at] = ids[pick][0] or u"?" + others[pick].glyphName, ids[pick][1]
        else:
            target = contours(name)
            base_box = box_of(contours(base_name))
            if not target or base_box is None:
                continue
            top_center, top_right, bottom_center = band_of(glyphset, base_name)
            wanted = [ac.MARKS.get(m) for m in marks]
            for at, mark in enumerate(marks):
                want = wanted[at]
                # (another mark of the letter's own is not this one: ố's acute is not its circumflex)
                order = [want] + sorted(k for k in templates if k != want and k not in wanted)
                for kind in order:
                    hit = None
                    for template_name, template in templates.get(kind, ()):
                        moved = find_shape(target, template, tolerance)
                        if moved is not None:
                            hit = box_of(template, *moved)
                            break
                    if hit is not None:
                        if kind in PLACED:
                            kind = PLACED[kind][where(hit, base_box, top_right, upm)]
                        found[at], boxes[at] = kind, hit
                        break
        results[code] = found
        base_box = box_of(contours(base_name), base_dx, base_dy)
        if base_box is None:
            continue
        width = float(base_box[2] - base_box[0]) or 1.0
        for kind, box in zip(found, boxes):
            if kind not in WATCHED or box is None:
                continue
            height = (box[3] - box[1]) / upm
            if kind == "caronvertical":
                values = ((box[0] - (top_right + base_dx)) / upm, (box[3] - base_box[3]) / upm, height)
            elif kind == "commaturnedabove":
                values = ((box[1] - base_box[3]) / upm, ((box[0] + box[2]) / 2.0 - (top_center + base_dx)) / width, height)
            else:
                values = ((base_box[1] - box[3]) / upm, ((box[0] + box[2]) / 2.0 - (bottom_center + base_dx)) / width, height)
            placed.append((kind, base_char, values))
    return results, placed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    counts = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # code: at: identity
    placements = collections.defaultdict(lambda: collections.defaultdict(list))  # identity: letter: [per-font medians]
    measured = 0
    for path, family in fonts(args.limit):
        try:
            results, placed = measure_font(path)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc))
            continue
        if not results:
            continue
        measured += 1
        for code, found in results.items():
            for at, kind in enumerate(found):
                counts[code][at][kind or "unknown"] += 1
        mine = collections.defaultdict(list)
        for kind, letter, values in placed:
            mine[(kind, letter)].append(values)
            mine[(kind, "*")].append(values)
        for (kind, letter), values in mine.items():
            placements[kind][letter].append(tuple(statistics.median(v[i] for v in values) for i in range(3)))
    print("%d families measured" % measured)
    table = []
    for code in sorted(counts):
        decomposed = unicodedata.normalize("NFD", chr(code))
        for at, counter in sorted(counts[code].items()):
            unicode_mark = ac.MARKS.get(ord(decomposed[1 + at]), "U+%04X" % ord(decomposed[1 + at]))
            known = dict((k, v) for k, v in counter.items() if k not in ("unknown", "joined") and not k.startswith("?"))
            total = sum(known.values())
            if not total:
                continue
            top, top_count = max(known.items(), key=lambda item: item[1])
            row = {"code": "%04X" % code, "letter": chr(code), "unicode": unicode_mark, "fonts_mark": top,
                   "fonts": top_count, "of": total, "share": round(top_count / float(total), 3),
                   "unicode_count": known.get(unicode_mark, 0), "counts": dict(counter)}
            table.append(row)
            if top != unicode_mark:
                print("%s U+%s  Unicode: %-12s fonts: %-18s %d of %d (%.0f%%)  [%s]" % (
                    chr(code), row["code"], unicode_mark, top, top_count, total, 100.0 * top_count / total,
                    ", ".join("%s %d" % kv for kv in sorted(counter.items(), key=lambda kv: -kv[1])[:6])))
    print()
    summary = {}
    for kind, letters_found in sorted(placements.items()):
        for letter, rows in sorted(letters_found.items()):
            if len(rows) < 3:
                continue
            medians = [round(statistics.median(r[i] for r in rows), 4) for i in range(3)]
            summary.setdefault(kind, {})[letter] = medians + [len(rows)]
            print("%s %s: %s from %d fonts" % (kind, letter, medians, len(rows)))
    if args.json:
        with io.open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"families": measured, "table": table, "placements": summary}, indent=1,
                                    ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
