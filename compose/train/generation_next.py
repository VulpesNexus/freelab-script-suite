"""Glyph Compose's Glyph generation tab, its next scope (2026-11-24): the characters, their recipes, and the
figures they are placed by, added to compose/glyph_generation.json.

The groups, from Unicode's data (this interpreter's, Unicode 16 or later) and the research's next scope:
- superscript and subscript signs and letters (<super> and <sub> of one character, in the BMP), but the
  figures and the ordinal indicators, which Feature Code's Forms tab builds (its SUPERSCRIPT_FIGURES,
  SUBSCRIPT_FIGURES, ORDINAL_LETTERS), and the kanbun annotation marks (U+3192 to U+319F);
- signs made of letters: the trade mark, service mark, and telephone signs, the numero sign, the degree
  Celsius and Fahrenheit, care of and cada una (not the per mille sign: its third ring is a contour of %);
- circled figures, letters, kana, and ideographs (<circle>, in the BMP), not the circled Hangul, whose
  decompositions are conjoining jamo (positional forms, not letters);
- full-width forms (<wide>, but the ideographic space, built already) and half-width ones (<narrow>,
  U+FF61 to U+FF9F, the kana and their punctuation);
- small capitals (LATIN LETTER SMALL CAPITAL ..., of one capital), letters with bars (Ħ ħ đ Ŧ ŧ Ƶ ƶ Ɨ ɨ Ʉ ʉ
  Ƀ ƀ Ǥ ǥ Ł ł), and small kana (HIRAGANA and KATAKANA LETTER SMALL ...).

The figures come from the corpus (open-licensed fonts, one per family, as generation.py finds them): for
each font, the median of its own characters' measures per key, then the median over the fonts. Only those
medians and counts leave the fonts. The corpus is read in slices (each run well under two minutes), their
per-family records kept in a file of their own; the last run writes the table.

    python compose/train/generation_next.py --records RECORDS [--start N] [--count N] [--corpus DIR]
    python compose/train/generation_next.py --records RECORDS --write [--table compose/glyph_generation.json]

Python 3 with fonttools.
"""

import argparse
import collections
import io
import json
import math
import os
import statistics
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "features"))
import generation as gen  # noqa: E402  (the corpus, the boxes, the table's writer; it sets the paths)
import freelab_feature_code as fc  # noqa: E402  (what Feature Code builds: never offered twice)

gg = gen.gg
TABLE = gen.OUT
E, A, S = "exact", "accepted", "starting point"
KANA = ((0x3040, 0x30FF), (0x31F0, 0x31FF))
HAN = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))

# -- the characters ------------------------------------------------------------------------------------------

FEATURE_CODE_BUILDS = set(fc.SUPERSCRIPT_FIGURES) | set(fc.SUBSCRIPT_FIGURES) | set(c for _, c, _ in fc.ORDINAL_LETTERS)
KANBUN = range(0x3192, 0x31A0)  # (annotation ideographs: kanbun, left out)
SIGNS = (("2122", ["0054", "004D"]), ("2120", ["0053", "004D"]), ("2121", ["0054", "0045", "004C"]),
         ("2116", ["004E", "006F"]), ("2103", ["00B0", "0043"]), ("2109", ["00B0", "0046"]),
         ("2105", ["0063", "006F"]), ("2106", ["0063", "0075"]))
BARS = ("0126", "0127", "0111", "0166", "0167", "01B5", "01B6", "0197", "0268", "0244", "0289", "0243", "0180",
        "01E4", "01E5", "0141", "0142")
RINGS = ("25EF", "25CB", "20DD")  # the large circle, the white circle, the combining enclosing circle
# The strokes a bar crosses at its height: every one between the first and the last (Ħ's two stems, Ʉ's), the
# first (Ƀ's stem, ħ's and đ's ascender), or the last (Ǥ's right stem); a letter of one stroke there, any
BAR_STEMS = gg.BAR_STEMS


def hexed(code):
    return "%04X" % code


def decomposition(code):
    found = unicodedata.decomposition(chr(code)).split()
    return (found[0], found[1:]) if found and found[0].startswith("<") else (None, found)


def scripted():
    """[(code, base, "super" or "sub")] in code order."""
    found = []
    for code in range(0x00A0, 0x10000):
        tag, parts = decomposition(code)
        if tag not in ("<super>", "<sub>") or len(parts) != 1 or code in FEATURE_CODE_BUILDS or code in KANBUN:
            continue
        found.append((hexed(code), parts[0], tag[1:-1]))
    return found


def circled():
    """[(code, parts, class)]: class "figure" (one digit), "number" (two digits), "capital", "small", "kana",
    "ideograph"; the circled Hangul left out (conjoining jamo)."""
    found = []
    for code in range(0x2000, 0x10000):
        tag, parts = decomposition(code)
        if tag != "<circle>":
            continue
        codes = [int(p, 16) for p in parts]
        if any(0x1100 <= c <= 0x11FF for c in codes):
            continue
        if all(0x30 <= c <= 0x39 for c in codes):
            kind = "figure" if len(codes) == 1 else "number"
        elif len(codes) == 1 and 0x41 <= codes[0] <= 0x5A:
            kind = "capital"
        elif len(codes) == 1 and 0x61 <= codes[0] <= 0x7A:
            kind = "small"
        elif len(codes) == 1 and 0x30A0 <= codes[0] <= 0x30FF:
            kind = "kana"
        elif all(0x4E00 <= c <= 0x9FFF for c in codes):
            kind = "ideograph"
        else:
            continue
        found.append((hexed(code), parts, kind))
    return found


def wide_and_narrow():
    """([(code, base)] of <wide> but the ideographic space, [(code, base)] of <narrow> U+FF61 to U+FF9F)."""
    wide, narrow = [], []
    for code in range(0xFF00, 0x10000):
        tag, parts = decomposition(code)
        if tag == "<wide>" and len(parts) == 1:
            wide.append((hexed(code), parts[0]))
        elif tag == "<narrow>" and len(parts) == 1 and code <= 0xFF9F:
            narrow.append((hexed(code), parts[0]))
    return wide, narrow


def by_name(prefix, replace):
    """[(code, base)] of the characters whose name starts with prefix, their base named with replace done."""
    found = []
    for code in range(0x0100, 0x10000):
        name = unicodedata.name(chr(code), "")
        if not name.startswith(prefix):
            continue
        try:
            base = unicodedata.lookup(replace(name))
        except KeyError:
            continue
        found.append((hexed(code), hexed(ord(base))))
    return found


def small_capitals():
    """ᴀ ʙ ᴄ ... and ᴁ ɶ: LATIN LETTER SMALL CAPITAL X of the capital X (the Latin ones only)."""
    found = by_name("LATIN LETTER SMALL CAPITAL ", lambda name: (
        "LATIN CAPITAL LIGATURE OE" if name.endswith(" OE") else "LATIN CAPITAL LETTER " + name.split("CAPITAL ", 1)[1]))
    return [(code, base) for code, base in found if len(unicodedata.name(chr(int(base, 16))).split()) == 4]


def small_kana():
    found = by_name("HIRAGANA LETTER SMALL ", lambda name: name.replace("SMALL ", ""))
    found += by_name("KATAKANA LETTER SMALL ", lambda name: name.replace("SMALL ", ""))
    return sorted(found)


def bars():
    found = []
    for code in BARS:
        name = unicodedata.name(chr(int(code, 16)))
        base = name.replace(" WITH STROKE", "").replace(" BAR", "")
        found.append((code, hexed(ord(unicodedata.lookup(base)))))
    return found


def kana_kind(code):
    code = int(code, 16)
    return "hiragana" if code < 0x30A0 else "katakana" if code < 0x3100 else "extension"


def script_class(base):
    return "letter" if unicodedata.category(chr(int(base, 16))).startswith("L") else "sign"


def wide_class(base):
    ch = chr(int(base, 16))
    return "letter" if ch.isalpha() else "figure" if ch.isdigit() else "sign"


def narrow_class(base):
    code = int(base, 16)
    return "mark" if code in (0x3099, 0x309A) else "kana" if 0x30A0 <= code <= 0x30FF else "sign"


# -- the measures ---------------------------------------------------------------------------------------------

def em_width(m):
    for code in (0x3000, 0x4E00, 0x3042, 0x30A2):
        advance = m.advance(code)
        if advance:
            return advance
    return 1.0


def height(box):
    return box[3] - box[1]


def width(box):
    return box[2] - box[0]


def contours(m, code):
    """[(polygon, box)] of a character's outline, in ems."""
    name = m.name(code)
    if not name:
        return []
    return [(p, gg.box_of([p])) for p in gen.polygons(m, name) if gg.box_of([p]) is not None]


def joined(items):
    return gg.union([box for _, box in items])


def composite_of(m, code):
    """The glyphs a TrueType composite is made of (None for one of outlines, or a CFF font)."""
    name = m.name(code)
    font = m.font
    if not name or "glyf" not in font:
        return None
    glyph = font["glyf"][name]
    return [c.glyphName for c in glyph.components] if glyph.isComposite() else None


def scale_of(target, base):
    """The target's size over the base's: by height, by width for a flat sign (a minus, an equals sign)."""
    if height(base) < 0.5 * width(base):
        return width(target) / width(base) if width(base) > 0 else None
    return height(target) / height(base) if height(base) > 0 else None


def measure_scripts(m, cap, rec):
    for code, base, kind in SCRIPTED:
        tb, bb = m.box(int(code, 16)), m.box(int(base, 16))
        if tb is None or bb is None:
            continue
        scale = scale_of(tb, bb)
        if scale is None or not 0.2 < scale < 0.95:
            continue
        cls = script_class(base)
        rec["%s %s scale" % (kind, cls)].append(scale)
        rec["%s %s baseline/cap" % (kind, cls)].append((tb[1] - scale * bb[1]) / cap)
        ta, ba = m.advance(int(code, 16)), m.advance(int(base, 16))
        if ta and ba:
            rec["%s %s width" % (kind, cls)].append(ta / (scale * ba))
    figures = [(c, 0x30 + d, "super") for d, c in enumerate(fc.SUPERSCRIPT_FIGURES)] + \
              [(c, 0x30 + d, "sub") for d, c in enumerate(fc.SUBSCRIPT_FIGURES)]
    for code, base, kind in figures:  # (Feature Code's, to compare)
        tb, bb = m.box(code), m.box(base)
        if tb is None or bb is None or not height(bb):
            continue
        scale = height(tb) / height(bb)
        if 0.2 < scale < 0.95:
            rec["%s figure scale" % kind].append(scale)
            rec["%s figure baseline/cap" % kind].append((tb[1] - scale * bb[1]) / cap)


def measure_letter_signs(m, cap, rec):
    """™ ℠ ℡: letters scaled side by side; № N and a raised o; ℃ ℉ the degree sign and a letter; ℅ ℆ a
    letter over another about a slash."""
    for code, parts in SIGNS:
        number = int(code, 16)
        tb = m.box(number)
        boxes = [m.box(int(p, 16)) for p in parts]
        if tb is None or any(b is None for b in boxes):
            continue
        if code in ("2122", "2120", "2121"):
            tallest = max(height(b) for b in boxes)
            scale = height(tb) / tallest
            if not 0.2 < scale < 1.05:
                continue
            gap = (width(tb) - scale * sum(width(b) for b in boxes)) / (len(boxes) - 1)
            advances = [m.advance(int(p, 16)) for p in parts]
            rec[code + " scale"].append(scale)
            rec[code + " top/cap"].append(tb[3] / cap)
            rec[code + " bottom/cap"].append(tb[1] / cap)
            rec[code + " gap"].append(gap)
            rec[code + " left"].append(tb[0] - scale * boxes[0][0])
            if advances[-1] and m.advance(number):
                rec[code + " right"].append((m.advance(number) - tb[2]) - scale * (advances[-1] - boxes[-1][2]))
            # How much narrower than scaled its first letter is (℡ is drawn condensed at full height): the
            # leftmost contour against the first letter scaled (T, S: one contour each), and the gap between the
            # letters' inks once all are as narrow
            shapes = sorted(contours(m, number), key=lambda s: s[1][0])
            if shapes and width(boxes[0]):
                squeeze = width(shapes[0][1]) / (scale * width(boxes[0]))
                if 0.3 < squeeze < 1.2:
                    rec[code + " squeeze"].append(squeeze)
                    rec[code + " squeezed gap"].append(
                        (width(tb) - squeeze * scale * sum(width(b) for b in boxes)) / (len(boxes) - 1))
            continue
        shapes = contours(m, number)
        if len(shapes) < 2:
            continue
        if code == "2116":
            tall = [s for s in shapes if height(s[1]) >= 0.75 * height(tb)]
            small = [s for s in shapes if height(s[1]) < 0.75 * height(tb)]
            if not tall or not small:
                continue
            letter, rest = joined(tall), joined(small)
            under = [s for s in small if height(s[1]) < 0.35 * height(rest) and width(s[1]) > 2 * height(s[1])
                     and s[1][3] < rest[1] + 0.4 * height(rest)]
            ring = joined([s for s in small if s not in under])
            if ring is None or not height(ring):
                continue
            n_box, o_box = boxes
            rec["2116 N scale"].append(height(letter) / height(n_box))
            rec["2116 N width"].append(width(letter) / width(n_box))
            rec["2116 o scale"].append(height(ring) / height(o_box))
            rec["2116 o top/cap"].append(ring[3] / cap)
            rec["2116 gap"].append(ring[0] - letter[2])
            rec["2116 underline"].append(1.0 if under else 0.0)
            if m.advance(number):
                rec["2116 right"].append(m.advance(number) - rest[2])
            if under:
                line = joined(under)
                hyphen = m.box(0x2D)
                rec["2116 underline width/o"].append(width(line) / width(ring))
                rec["2116 underline gap"].append(ring[1] - line[3])
                if hyphen is not None and height(hyphen):
                    rec["2116 underline/hyphen"].append(height(line) / height(hyphen))
            continue
        if code in ("2103", "2109"):
            middle = (tb[0] + tb[2]) / 2.0
            degree = [s for s in shapes if s[1][1] > 0.35 * cap and s[1][2] < middle]
            letter = [s for s in shapes if s not in degree]
            if not degree or not letter:
                continue
            ring, rest = joined(degree), joined(letter)
            deg_box, letter_box = boxes
            deg_advance = m.advance(0xB0)
            rec[code + " letter scale"].append(height(rest) / height(letter_box))
            rec[code + " degree scale"].append(width(ring) / width(deg_box))
            rec[code + " degree top - letter top"].append(ring[3] - rest[3])
            rec[code + " gap"].append(rest[0] - ring[2])
            if deg_advance:
                natural = (deg_advance - deg_box[2]) + letter_box[0]
                rec[code + " gap - advances"].append((rest[0] - ring[2]) - natural)
            continue
        # ℅ ℆: the slash the tallest contour, the letter over it above the middle, the other under it
        tallest = max(shapes, key=lambda s: height(s[1]))
        if height(tallest[1]) < 0.6 * height(tb):
            continue
        middle = (tb[1] + tb[3]) / 2.0
        upper = [s for s in shapes if s is not tallest and (s[1][1] + s[1][3]) / 2.0 > middle]
        lower = [s for s in shapes if s is not tallest and (s[1][1] + s[1][3]) / 2.0 <= middle]
        if not upper or not lower:
            continue
        up, low = joined(upper), joined(lower)
        rec[code + " upper scale"].append(height(up) / height(boxes[0]))
        rec[code + " upper top/cap"].append(up[3] / cap)
        rec[code + " lower scale"].append(height(low) / height(boxes[1]))
        rec[code + " lower bottom/cap"].append(low[1] / cap)


def ring_of(shapes):
    """(outer box, inner box, the other contours) of a circled glyph, or None: the outer ring the contour of
    the largest box, the inner the largest inside it about the same center."""
    if len(shapes) < 3:
        return None
    area = lambda box: width(box) * height(box)  # noqa: E731
    outer = max(shapes, key=lambda s: area(s[1]))
    ob = outer[1]
    cx, cy, diameter = (ob[0] + ob[2]) / 2.0, (ob[1] + ob[3]) / 2.0, height(ob)
    inside = [s for s in shapes if s is not outer and s[1][0] >= ob[0] and s[1][2] <= ob[2] and s[1][1] >= ob[1]
              and s[1][3] <= ob[3] and abs((s[1][0] + s[1][2]) / 2.0 - cx) < 0.1 * diameter
              and abs((s[1][1] + s[1][3]) / 2.0 - cy) < 0.1 * diameter and area(s[1]) > 0.45 * area(ob)]
    if not inside:
        return None
    inner = max(inside, key=lambda s: area(s[1]))
    rest = [s for s in shapes if s is not outer and s is not inner]
    return (ob, inner[1], rest) if rest else None


def measure_circled(m, cap, cjk, rec, has):
    kind = "cjk" if cjk else "latin"
    own = {}  # (the font's own rings: how a circled glyph's compares)
    for ring in RINGS[:2]:
        box = m.box(int(ring, 16))
        if box is not None and height(box):
            own[ring] = (box, None)
    for code, parts, cls in CIRCLED:
        number = int(code, 16)
        if m.name(number) is None:
            continue
        found = ring_of(contours(m, number))
        bases = [m.box(int(p, 16)) for p in parts]
        if found is None or any(b is None for b in bases):
            continue
        outer, inner, rest = found
        content = joined(rest)
        if content is None or not height(content):
            continue
        key = "circled %s %s " % (kind, cls)
        diameter = height(outer)
        advance = m.advance(number)
        rec[key + "diameter"].append(diameter)
        rec[key + "round"].append(width(outer) / diameter)
        rec[key + "center"].append((outer[1] + outer[3]) / 2.0)
        rec[key + "thickness"].append((diameter - height(inner)) / 2.0)
        if advance:
            rec[key + "advance"].append(advance)
            rec[key + "side"].append((advance - width(outer)) / 2.0)
        tallest = max(height(b) for b in bases)
        rec[key + "scale"].append(height(content) / tallest)
        rec[key + "content/inner"].append(height(content) / height(inner))
        if len(bases) > 1:
            scale = height(content) / tallest
            rec[key + "squeeze"].append(width(content) / (scale * sum(width(b) for b in bases)))
        rec[key + "content x"].append(((content[0] + content[2]) - (outer[0] + outer[2])) / 2.0 / diameter)
        rec[key + "content y"].append(((content[1] + content[3]) - (outer[1] + outer[3])) / 2.0 / diameter)
        for ring, (box, _) in own.items():
            rec[key + "diameter/" + ring].append(diameter / height(box))
        parts_of = composite_of(m, number)
        if parts_of is not None:
            names = dict((m.name(int(r, 16)), r) for r in RINGS if m.name(int(r, 16)))
            rec[key + "ring component"].append(1.0 if any(n in names or "circle" in n.lower() for n in parts_of) else 0.0)


def measure_cells(m, rec, pairs, group, classify):
    """Full-width and half-width forms, small kana: the form's advance over the em's width, its size over
    its base's (across and up), where its ink's center sits across its advance, and how far its ink's center
    is raised from its base's (in ems)."""
    em = em_width(m)
    for code, base in pairs:
        tb, bb = m.box(int(code, 16)), m.box(int(base, 16))
        advance = m.advance(int(code, 16))
        if tb is None or bb is None or not advance:
            continue
        cls = classify(code, base)
        for key in ("%s %s " % (group, cls), "%s %s " % (group, code)):
            rec[key + "advance/em"].append(advance / em)
            if width(bb) > 0:
                rec[key + "across"].append(width(tb) / width(bb))
            if height(bb) > 0:
                rec[key + "up"].append(height(tb) / height(bb))
            rec[key + "x share"].append((tb[0] + tb[2]) / 2.0 / advance)
            rec[key + "raised"].append((tb[1] + tb[3]) / 2.0 - (bb[1] + bb[3]) / 2.0)
            base_advance = m.advance(int(base, 16))
            if base_advance:
                rec[key + "base x share"].append((bb[0] + bb[2]) / 2.0 / base_advance)
                rec[key + "x shift"].append((tb[0] + tb[2]) / 2.0 - (bb[0] + bb[2]) / 2.0)
            rec[key + "bottom shift"].append(tb[1] - bb[1])
        if abs(width(tb) - width(bb)) < 0.005 and abs(height(tb) - height(bb)) < 0.005:
            rec["%s %s same ink" % (group, cls)].append(1.0)
        else:
            rec["%s %s same ink" % (group, cls)].append(0.0)


def measure_small_capitals(m, x_height, rec):
    for code, base in SMALL_CAPITALS:
        tb, bb = m.box(int(code, 16)), m.box(int(base, 16))
        if tb is None or bb is None or not height(bb):
            continue
        scale = height(tb) / height(bb)
        if not 0.4 < scale < 0.95:
            continue
        rec["smallcap scale"].append(scale)
        rec["smallcap top/x-height"].append(tb[3] / x_height)
        rec["smallcap bottom"].append(tb[1])
        ta, ba = m.advance(int(code, 16)), m.advance(int(base, 16))
        if ta and ba:
            rec["smallcap width"].append(ta / (scale * ba))


GRID = 200  # cells per em, for the bars


def cells(polygons, dx=0):
    found = set()
    box = gg.box_of(polygons)
    if box is None:
        return found
    for row in range(int(math.floor(box[1] * GRID)) - 1, int(math.ceil(box[3] * GRID)) + 1):
        for start, end in gg.strokes(polygons, "y", (row + 0.5) / GRID):
            for column in range(int(round((start + dx) * GRID)), int(round((end + dx) * GRID))):
                found.add((row, column))
    return found


def measure_bars(m, cap, x_height, rec):
    """A letter with a bar against its letter: the letter's cells laid where they cover the most of the barred
    one's, the cells left over are the bar (horizontal: the rows most of them are in; Ł ł: their long axis)."""
    hyphen = m.box(0x2D)
    for code, base in BAR_PAIRS:
        target, letter = [p for p, _ in contours(m, int(code, 16))], [p for p, _ in contours(m, int(base, 16))]
        bb = m.box(int(base, 16))
        if not target or not letter or bb is None:
            continue
        own = cells(target)
        best = None
        for shift in range(-int(0.2 * GRID), int(0.2 * GRID) + 1, 2):
            moved = set((r, c + shift) for r, c in cells(letter))
            overlap = len(own & moved)
            if best is None or overlap > best[0]:
                best = (overlap, shift, moved)
        _, shift, moved = best
        extra = own - moved
        if len(extra) < 20:
            continue
        if code in ("0141", "0142"):  # (a slash: its long axis)
            xs = [c / float(GRID) for _, c in extra]
            ys = [r / float(GRID) for r, _ in extra]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            sxx = sum((x - mx) ** 2 for x in xs)
            syy = sum((y - my) ** 2 for y in ys)
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            angle = 0.5 * math.degrees(math.atan2(2 * sxy, sxx - syy))
            along = [(x - mx) * math.cos(math.radians(angle)) + (y - my) * math.sin(math.radians(angle))
                     for x, y in zip(xs, ys)]
            rec[code + " angle"].append(angle)
            rec[code + " length"].append(max(along) - min(along))
            rec[code + " center/height"].append(my / height(bb))
            stem = gg.strokes(letter, "y", my)
            if stem:
                rec[code + " center - stem"].append(mx - (stem[0][0] + stem[0][1]) / 2.0 - shift / float(GRID))
            continue
        rows = collections.Counter(r for r, _ in extra)
        peak = max(rows.values())
        top_row = max(rows, key=lambda r: rows[r])
        block = [top_row]
        while rows.get(block[-1] + 1, 0) >= 0.5 * peak:
            block.append(block[-1] + 1)
        while rows.get(block[0] - 1, 0) >= 0.5 * peak:
            block.insert(0, block[0] - 1)
        thick = len(block) / float(GRID)
        y = (block[0] + block[-1] + 1) / 2.0 / GRID
        bar = [c for r, c in extra if r in block]  # (the bar where the letter has no ink: beside its stems)
        stems = [(a + shift / float(GRID), b + shift / float(GRID)) for a, b in gg.strokes(letter, "y", y)]
        if not stems or not bar:
            continue
        crossed = BAR_STEMS.get(code, "first")  # (the stroke the bar crosses: one, or all between the first and last)
        stem = (stems[0][0], stems[-1][1]) if crossed == "all" else stems[0] if crossed == "first" else stems[-1]
        left, right = min(min(bar) / float(GRID), stem[0]), max((max(bar) + 1) / float(GRID), stem[1])
        rec[code + " height share"].append((y - bb[1]) / height(bb))
        rec[code + " y/cap"].append(y / cap)
        if x_height:
            rec[code + " y/x-height"].append(y / x_height)
        rec[code + " left overhang"].append(stem[0] - left)
        rec[code + " right overhang"].append(right - stem[1])
        rec[code + " stems"].append(float(len(stems)))
        if hyphen is not None and height(hyphen):
            rec[code + " thickness/hyphen"].append(thick / height(hyphen))


def measure_font(font, only=None):
    """{key: this font's median} and the codes of the new scope it has (and those it makes of components);
    only "signs": the signs made of letters alone (a measure added later, over the records)."""
    m = gen.Measured(font)
    h, x = m.box(0x48), m.box(0x78)
    cap, x_height = (h[3] if h else None), (x[3] if x else None)
    codes = set(m.cmap)
    cjk = any(lo <= c <= hi for c in codes for lo, hi in KANA + HAN)
    rec = collections.defaultdict(list)
    if only == "signs":
        if cap:
            measure_letter_signs(m, cap, rec)
        return dict((key, statistics.median(values)) for key, values in rec.items() if values), None, None, cjk
    if cap:
        measure_scripts(m, cap, rec)
        measure_letter_signs(m, cap, rec)
        measure_circled(m, cap, cjk, rec, codes)
        if x_height:
            measure_small_capitals(m, x_height, rec)
        measure_bars(m, cap, x_height, rec)
    if cjk:
        measure_cells(m, rec, WIDE, "wide", lambda code, base: wide_class(base))
        measure_cells(m, rec, NARROW, "narrow", lambda code, base: narrow_class(base))
        measure_cells(m, rec, SMALL_KANA, "smallkana", lambda code, base: kana_kind(code))
    found = dict((key, statistics.median(values)) for key, values in rec.items() if values)
    have, built = [], []
    for code in EVERY:
        if int(code, 16) in codes:
            have.append(code)
            if composite_of(m, int(code, 16)):
                built.append(code)
    return found, have, built, cjk


# -- the slices, and the table -----------------------------------------------------------------------------------

def measure_slice(corpus, start, count, records_path, only=None):
    """The fonts of files[start:start + count] measured into the records (one per family: a family recorded
    already is skipped; with only, measured again for those keys alone, the keys added to its record)."""
    from fontTools.ttLib import TTFont
    records = read_json(records_path) or {"families": {}}
    files = gen.font_files(corpus)
    began = time.time()
    done, again = 0, set()
    for path in files[start:start + count]:
        try:
            font = TTFont(path, lazy=True)
            if gen.license_of(font) is None:
                continue
            name = font["name"]
            family = str(name.getDebugName(16) or name.getDebugName(1) or "")
            if not family or (family in records["families"]) != bool(only) or family in again:
                continue
            found, have, built, cjk = measure_font(font, only)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc))
            continue
        if only:
            records["families"][family]["measures"].update(found)
            again.add(family)
        else:
            records["families"][family] = {"measures": found, "has": have, "built": built, "cjk": cjk}
        done += 1
    write_json(records_path, records)
    print("%d families measured in %.0f s (files %d to %d of %d); %d in the records" % (
        done, time.time() - began, start, min(start + count, len(files)) - 1, len(files), len(records["families"])))


def read_json(path):
    if not path or not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, data):
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def layout_of(records):
    """{key: {"n", "median", "q1", "q3"}} over the families (each its own median first)."""
    values = collections.defaultdict(list)
    for family in records["families"].values():
        for key, value in family["measures"].items():
            values[key].append(value)
    return dict((key, gen.stats(found)) for key, found in sorted(values.items()))


def median(layout, key, default=None, least=3):
    found = layout.get(key)
    return found["median"] if found and found["n"] >= least else default


def counted_of(layout, key):
    found = layout.get(key)
    return found["n"] if found else 0


def rounded(value, places=3):
    return None if value is None else round(value, places)


def next_rules(layout):
    """The figures the recipes are placed by, from the corpus's medians (each with how many families).
    Superscript and subscript signs take Feature Code's figures' scale, baseline, and width (the corpus's signs
    measure within a few hundredths of its figures: ⁺ is set beside the ¹ Feature Code builds); letters their
    own scale and width, on the figures' baseline (the corpus's letters are larger than its figures, as the
    ordinal indicators are)."""
    rules = {}
    scripts = {}
    for kind, set_key, baseline in (("super", "sups", fc.SUPS_BASELINE), ("sub", "subs", fc.SUBS_BASELINE)):
        for cls in ("letter", "sign", "figure"):
            key = "%s %s " % (kind, cls)
            measured = {"scale": rounded(median(layout, key + "scale")),
                        "baseline": rounded(median(layout, key + "baseline/cap")),
                        "width": rounded(median(layout, key + "width")), "families": counted_of(layout, key + "scale")}
            if cls == "sign":
                rule = {"scale": fc.CORPUS_SCALE[set_key], "baseline": baseline, "width": fc.CORPUS_WIDTH[set_key]}
            elif cls == "letter":
                rule = {"scale": rounded(measured["scale"], 2), "baseline": baseline,
                        "width": rounded(measured["width"], 2)}
            else:  # (Feature Code's own: measured here only to compare)
                rule = {}
            rule.update(families=measured["families"], measured=measured)
            scripts["%s %s" % (kind, cls)] = rule
    rules["scripts"] = scripts
    signs = {}
    for code, _ in SIGNS:
        signs[code] = dict((key[len(code) + 1:], rounded(value["median"], 4)) for key, value in layout.items()
                           if key.startswith(code + " ") and value["n"] >= 3)
        signs[code]["families"] = max([value["n"] for key, value in layout.items() if key.startswith(code + " ")] or [0])
    rules["signs"] = signs
    # ℃ and ℉: the degree sign and the letter at their own size (the corpus's medians: 1.00 both), their inks
    # this far apart (a row's gap, in ems)
    rules["rows"] = dict((code, signs[code]["gap"]) for code in ("2103", "2109") if "gap" in signs.get(code, {}))
    circles = {}
    for kind in ("latin", "cjk"):
        for cls in ("figure", "number", "capital", "small", "kana", "ideograph"):
            key = "circled %s %s " % (kind, cls)
            if counted_of(layout, key + "diameter") < 3:
                continue
            circles["%s %s" % (kind, cls)] = dict(
                (name, rounded(median(layout, key + name), 4)) for name in (
                    "diameter", "center", "thickness", "side", "advance", "scale", "content/inner", "squeeze",
                    "content x", "content y", "diameter/25EF", "diameter/25CB", "ring component", "round")
                if median(layout, key + name) is not None)
            circles["%s %s" % (kind, cls)]["families"] = counted_of(layout, key + "diameter")
    rules["circled"] = circles
    cells = {}
    for group, measured, classes, pairs in (("fullwidth", "wide", ("letter", "figure", "sign"), WIDE),
                                            ("halfwidth", "narrow", ("kana", "sign", "mark"), NARROW),
                                            ("smallkana", "smallkana", ("hiragana", "katakana", "extension"),
                                             SMALL_KANA)):
        found = {}
        for cls in classes + tuple(code for code, _ in pairs):
            key = "%s %s " % (measured, cls)
            if counted_of(layout, key + "advance/em") < 3:
                continue
            found[cls] = dict((name, rounded(median(layout, key + name), 4)) for name in (
                "advance/em", "across", "up", "x share", "raised", "x shift", "bottom shift")
                if median(layout, key + name) is not None)
            found[cls]["families"] = counted_of(layout, key + "advance/em")
            same = layout.get("%s %s same ink" % (measured, cls))
            if same:
                found[cls]["same ink"] = rounded(same["median"], 3)
        cells[group] = found
    rules["cells"] = cells
    rules["smallcaps"] = {"scale": rounded(median(layout, "smallcap scale")),
                          "top/x-height": rounded(median(layout, "smallcap top/x-height")),
                          "width": rounded(median(layout, "smallcap width")),
                          "families": counted_of(layout, "smallcap scale")}
    found = {}
    for code, _ in BAR_PAIRS:
        own = dict((key[len(code) + 1:], rounded(value["median"], 4)) for key, value in layout.items()
                   if key.startswith(code + " ") and value["n"] >= 3)
        if own:
            own["families"] = max(value["n"] for key, value in layout.items() if key.startswith(code + " "))
            found[code] = own
    # A slash's thickness is not measured (its cells are a band at an angle): the other bars' median against
    # their hyphen
    thick = statistics.median(own["thickness/hyphen"] for own in found.values() if "thickness/hyphen" in own)
    for code in ("0141", "0142"):
        if code in found:
            found[code]["thickness/hyphen"] = round(thick, 4)
    rules["bars"] = found
    return rules


GROUPS = (("scripts", u"Superscript and subscript signs and letters"), ("signs", u"Signs made of letters"),
          ("circled", u"Circled figures and letters"), ("fullwidth", u"Full-width forms"),
          ("smallcaps", u"Small capitals"), ("bars", u"Letters with bars"), ("smallkana", u"Small kana"),
          ("halfwidth", u"Half-width forms"))


def ways_of(group, code, parts):
    """A character's ways, in order (the first the font can take is used)."""
    if group == "scripts":
        base, kind = parts
        return [{"op": "form", "of": base, "forms": "sups" if kind == "super" else "subs", "confidence": A},
                {"op": "script", "of": base, "kind": kind, "confidence": S}]
    if group == "signs":
        if code in ("2122", "2120", "2121"):
            return [{"op": "scaled", "of": parts, "rule": code, "confidence": S}]
        if code == "2116":
            return [{"op": "numero", "of": parts, "confidence": S}]
        if code in ("2103", "2109"):  # (the degree sign and the letter at their own size: how most fonts draw them)
            return [{"op": "row", "of": parts, "pair": code, "confidence": A}]
        return [{"op": "over", "of": parts, "confidence": S}]
    if group == "circled":
        content, cls = parts
        way = {"op": "circle", "of": content, "class": cls, "confidence": S}
        if cls in ("kana", "ideograph"):
            way["only"] = "cjk"
        return [way]
    if group in ("fullwidth", "halfwidth"):
        ways = [{"op": "cell", "of": parts, "cell": group, "confidence": S, "only": "cjk"}]
        if parts == "3099":
            ways.append({"op": "cell", "of": "309B", "cell": group, "confidence": S, "only": "cjk"})
        if parts == "309A":
            ways.append({"op": "cell", "of": "309C", "cell": group, "confidence": S, "only": "cjk"})
        return ways
    if group == "smallkana":
        return [{"op": "cell", "of": parts, "cell": group, "confidence": S, "only": "cjk"}]
    if group == "smallcaps":
        lower = hexed(ord(chr(int(parts, 16)).lower())) if chr(int(parts, 16)).lower() != chr(int(parts, 16)) else parts
        return [{"op": "form", "of": lower, "forms": "smcp", "confidence": A},
                {"op": "form", "of": parts, "forms": "c2sc", "confidence": A},
                {"op": "smallcap", "of": parts, "confidence": S}]
    if group == "bars":
        return [{"op": "bar", "of": parts, "rule": code, "confidence": S}]
    raise ValueError(group)


def members():
    """[(group, code, parts)] of the next scope, group by group."""
    found = [("scripts", code, (base, kind)) for code, base, kind in SCRIPTED]
    found += [("signs", code, parts) for code, parts in SIGNS]
    found += [("circled", code, (parts, cls)) for code, parts, cls in CIRCLED]
    found += [("fullwidth", code, base) for code, base in WIDE]
    found += [("smallcaps", code, base) for code, base in SMALL_CAPITALS]
    found += [("bars", code, base) for code, base in BAR_PAIRS]
    found += [("smallkana", code, base) for code, base in SMALL_KANA]
    found += [("halfwidth", code, base) for code, base in NARROW]
    return found


GLYPH_NAMES = os.path.join(HERE, os.pardir, "glyph_names.json")
AGL_NAMES = {"2122": u"trademark"}  # (the Adobe Glyph List's, where Glyphs' list is not at hand)


def write(records_path, table_path):
    records = read_json(records_path)
    layout = layout_of(records)
    table = read_json(table_path)
    names = (read_json(GLYPH_NAMES) or {}).get("names", {})
    have = collections.Counter(code for f in records["families"].values() for code in f["has"])
    built = collections.Counter(code for f in records["families"].values() for code in f["built"])
    ids = set(group for group, _ in GROUPS)
    table["entries"] = [e for e in table["entries"] if e["group"] not in ids]
    table["groups"] = [g for g in table["groups"] if g["id"] not in ids]
    known = set(e["code"] for e in table["entries"])
    entries = []
    for group, code, parts in members():
        if code in known:
            continue  # (a character the table builds already keeps its recipe: Đ is a duplicate of Ð)
        ways = ways_of(group, code, parts)
        entries.append({"code": code, "group": group, "unicode_name": unicodedata.name(chr(int(code, 16))),
                        "glyph_name": names.get(code) or AGL_NAMES.get(code) or u"uni" + code, "ways": ways,
                        "research_confidence": ways[0]["confidence"], "families": have[code],
                        "deriving": built[code], "most": None})
    for group, title in GROUPS:
        count = sum(1 for e in entries if e["group"] == group)
        if count:
            table["groups"].append({"id": group, "title": title, "count": count})
    table["entries"] += entries
    table["characters"] = gen.characters(table["entries"])
    for e in entries:  # (the parts a circle or a sign is made of, named for the notes too)
        for way in e["ways"]:
            for part in way["of"] if isinstance(way["of"], list) else [way["of"]]:
                table["characters"].setdefault(part, {"category": unicodedata.category(chr(int(part, 16))),
                                                      "name": gen.unicode_name(part)})
    rules = next_rules(layout)
    table["rules"].setdefault("rows", {}).update(rules.pop("rows"))  # (the first scope's rows kept)
    table["rules"].update(rules)
    table["next_scope"] = {"families": len(records["families"]),
                           "cjk_families": sum(1 for f in records["families"].values() if f["cjk"]),
                           "unicode": unicodedata.unidata_version}
    # (the medians the rules come from, but each cell character's own: those are in the rules already)
    table["next_layout"] = dict((key, value) for key, value in layout.items()
                                if not (key.split()[0] in ("wide", "narrow", "smallkana") and len(key.split()[1]) == 4
                                        and all(c in "0123456789ABCDEF" for c in key.split()[1])))
    gen.write_table(table, table_path)
    print("%d characters added in %d groups, from %d families (%d with CJK); Unicode %s" % (
        len(entries), len(GROUPS), len(records["families"]), table["next_scope"]["cjk_families"],
        unicodedata.unidata_version))


SCRIPTED = scripted()
CIRCLED = circled()
WIDE, NARROW = wide_and_narrow()
SMALL_CAPITALS = small_capitals()
SMALL_KANA = small_kana()
BAR_PAIRS = bars()
EVERY = [code for _, code, _ in members()]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--records", required=True, help="the per-family records (kept between the slices)")
    parser.add_argument("--corpus", default=gen.CORPUS)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--write", action="store_true", help="write the table from the records")
    parser.add_argument("--table", default=TABLE)
    parser.add_argument("--list", action="store_true", help="say how many characters each group holds")
    parser.add_argument("--only", choices=("signs",), help="measure again only these, over the families recorded")
    args = parser.parse_args()
    if args.list:
        for group, title in GROUPS:
            print(group, sum(1 for g, _, _ in members() if g == group))
        print("font files:", len(gen.font_files(args.corpus)))
        return
    if args.write:
        write(args.records, args.table)
        return
    measure_slice(args.corpus, args.start, args.count, args.records, args.only)


if __name__ == "__main__":
    main()
