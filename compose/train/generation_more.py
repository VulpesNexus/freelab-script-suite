"""Glyph Compose's Glyph generation tab, the scope the next one left (2026-11-27): the characters, their recipes,
and the figures they are placed by, added to compose/glyph_generation.json beside the next scope's.

The groups, from Unicode's data (this interpreter's, Unicode 16 or later):
- the circled Hangul (U+3260 to U+327E, <circle> of conjoining jamo): mapped to what fonts draw, the compatibility
  jamo (U+3131 on) for U+3260 to U+326D, the syllables the jamo compose for the others (two for U+327C and
  U+327D), and set in the font's ring as the circled kana and ideographs are;
- the parenthesized Hangul and ideographs (U+3200 to U+321E, U+3220 to U+3243, <compat>): the parentheses and the
  content scaled into a full-width cell, as the corpus's CJK families set them;
- the half-width Hangul (U+FFA0 to U+FFDC, <narrow> of the compatibility jamo: a second code point on the jamo's
  own glyph, as the corpus gives them) and signs (U+FFE8 to U+FFEE, in half a full-width cell);
- the kanbun annotation marks (U+3192 to U+319F, <super> of ideographs: the ideograph at its own size, as the
  corpus draws them);
- the per mille sign (U+2030), from the font's % where its contours split into a slash and two rings;
- and, measured only (no character of its own), how much thicker a drawn superscript or subscript letter's and a
  small capital's stems are than its source's scaled ones: whether a rule comes out for thickening them.

The figures come from the corpus (open-licensed fonts, one per family, as generation.py finds them): for each font,
the median of its own characters' measures per key, then the median over the fonts. Only those medians and counts
leave the fonts. The corpus is read in slices (each run well under two minutes), their per-family records kept in a
file of their own; the last run adds to the table (the next scope's entries and rules kept as they are).

    python compose/train/generation_more.py --records RECORDS [--start N] [--count N] [--corpus DIR]
    python compose/train/generation_more.py --records RECORDS --write [--table compose/glyph_generation.json]

Python 3 with fonttools.
"""

import argparse
import collections
import io
import json
import os
import statistics
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generation as gen  # noqa: E402  (the corpus, the boxes, the table's writer)
import generation_next as nx  # noqa: E402  (the next scope's measures, reused: circles, cells)

gg = gen.gg
TABLE = gen.OUT
A, S = "accepted", "starting point"
PERCENT, PERMILLE = "0025", "2030"


def hexed(code):
    return "%04X" % code


# -- the characters ------------------------------------------------------------------------------------------

def compatibility_jamo():
    """{conjoining jamo hex: compatibility jamo hex}: the compatibility jamo (U+3131 to U+318E) each decompose to
    one conjoining jamo (<compat> 1100 for U+3131); the first found for each is kept."""
    found = {}
    for code in range(0x3131, 0x318F):
        parts = unicodedata.decomposition(chr(code)).split()
        if len(parts) == 2 and parts[0] == "<compat>":
            found.setdefault(parts[1], hexed(code))
    return found


JAMO = compatibility_jamo()


def drawn_of(conjoining):
    """[hex] of what fonts draw for a run of conjoining jamo: one leading consonant alone its compatibility jamo
    (ㄱ for U+1100), else the syllables the jamo compose (가 for U+1100 U+1161, 참고 for five jamo)."""
    if len(conjoining) == 1:
        return [JAMO[conjoining[0]]]
    composed = unicodedata.normalize("NFC", u"".join(chr(int(p, 16)) for p in conjoining))
    if not all(0xAC00 <= ord(ch) <= 0xD7A3 for ch in composed):
        raise ValueError(conjoining)
    return [hexed(ord(ch)) for ch in composed]


def hangul_class(drawn):
    return "jamo" if 0x3131 <= int(drawn[0], 16) <= 0x318E else "syllable" if len(drawn) == 1 else "word"


def circled_hangul():
    """[(code, drawn parts, class)]: class "jamo" (U+3260 to U+326D), "syllable", or "word" (two syllables)."""
    found = []
    for code in range(0x3260, 0x3280):
        parts = unicodedata.decomposition(chr(code)).split()
        if not parts or parts[0] != "<circle>":
            continue
        drawn = drawn_of(parts[1:])
        found.append((hexed(code), drawn, hangul_class(drawn)))
    return found


def parenthesized():
    """[(code, drawn content, class)] of U+3200 to U+3243 (<compat> ( ... )): "jamo", "syllable", "word", or
    "ideograph"."""
    found = []
    for code in list(range(0x3200, 0x321F)) + list(range(0x3220, 0x3244)):
        parts = unicodedata.decomposition(chr(code)).split()
        if not parts or parts[0] != "<compat>" or parts[1] != "0028" or parts[-1] != "0029":
            continue
        inner = parts[2:-1]
        if all(0x1100 <= int(p, 16) <= 0x11FF for p in inner):
            drawn = drawn_of(inner)
            found.append((hexed(code), drawn, hangul_class(drawn)))
        elif len(inner) == 1 and 0x4E00 <= int(inner[0], 16) <= 0x9FFF:
            found.append((hexed(code), inner, "ideograph"))
    return found


def half_width():
    """([(code, compatibility jamo)] of U+FFA1 to U+FFDC, [(code, sign)] of U+FFE8 to U+FFEE); U+FFA0, the
    half-width filler, is an empty glyph of half a cell (its own way)."""
    hangul, signs = [], []
    for code in range(0xFFA1, 0xFFEF):
        parts = unicodedata.decomposition(chr(code)).split()
        if len(parts) != 2 or parts[0] != "<narrow>":
            continue
        (hangul if code <= 0xFFDC else signs).append((hexed(code), parts[1]))
    return hangul, signs


def kanbun():
    return [(hexed(code), unicodedata.decomposition(chr(code)).split()[1]) for code in nx.KANBUN]


def script_letters():
    """[(code, base, kind)] of the superscript and subscript letters (the next scope's, by its classes)."""
    return [(code, base, kind) for code, base, kind in nx.SCRIPTED if nx.script_class(base) == "letter"]


CIRCLED_HANGUL = circled_hangul()
PARENTHESIZED = parenthesized()
HALF_HANGUL, HALF_SIGNS = half_width()
KANBUN = kanbun()


# -- the measures ---------------------------------------------------------------------------------------------

def width(box):
    return box[2] - box[0]


def height(box):
    return box[3] - box[1]


def measure_circled(m, cap, rec, codes):
    """The circled Hangul as the next scope measured the circled kana: nx.measure_circled over this list."""
    kept = nx.CIRCLED
    nx.CIRCLED = CIRCLED_HANGUL
    try:
        nx.measure_circled(m, cap, True, rec, codes)
    finally:
        nx.CIRCLED = kept


def measure_parenthesized(m, rec):
    """A parenthesized character's left parenthesis its contour reaching furthest left, its right one furthest
    right (each tall and narrow), the rest its content: their size against ( and the content's characters, where
    they sit in the cell (a share of the advance across, ems up), and the advance against the em's width."""
    em = nx.em_width(m)
    paren = m.box(0x28)
    for code, parts, cls in PARENTHESIZED:
        number = int(code, 16)
        shapes = nx.contours(m, number)
        tb, advance = m.box(number), m.advance(number)
        bases = [m.box(int(p, 16)) for p in parts]
        if len(shapes) < 3 or tb is None or not advance or any(b is None for b in bases):
            continue
        left = min(shapes, key=lambda s: s[1][0])
        right = max(shapes, key=lambda s: s[1][2])
        if left is right or any(height(s[1]) < 0.5 * height(tb) or width(s[1]) > 0.3 * width(tb) for s in (left, right)):
            continue
        rest = [s for s in shapes if s is not left and s is not right]
        content = nx.joined(rest)
        # (between the parentheses: within their outer edges, its middle between theirs; a syllable's bar may reach
        # into a curved parenthesis's box, as Noto Sans KR's 가 does in U+320E)
        if content is None or content[0] < left[1][0] or content[2] > right[1][2] or \
                not (left[1][0] + left[1][2]) / 2.0 < (content[0] + content[2]) / 2.0 < (right[1][0] + right[1][2]) / 2.0:
            continue
        key = "paren %s " % cls
        rec[key + "advance/em"].append(advance / em)
        tallest = max(height(b) for b in bases)
        scale = height(content) / tallest
        rec[key + "scale"].append(scale)
        if len(bases) > 1:
            rec[key + "squeeze"].append(width(content) / (scale * sum(width(b) for b in bases)))
        rec[key + "content x share"].append((content[0] + content[2]) / 2.0 / advance)
        rec[key + "content y"].append((content[1] + content[3]) / 2.0)
        rec[key + "left x share"].append((left[1][0] + left[1][2]) / 2.0 / advance)
        rec[key + "right x share"].append((right[1][0] + right[1][2]) / 2.0 / advance)
        rec[key + "paren y"].append((left[1][1] + left[1][3] + right[1][1] + right[1][3]) / 4.0)
        if paren is not None and height(paren) and width(paren):
            rec[key + "paren up"].append((height(left[1]) + height(right[1])) / 2.0 / height(paren))
            rec[key + "paren across"].append((width(left[1]) + width(right[1])) / 2.0 / width(paren))


def measure_permille(m, rec):
    """The per mille sign against the percent sign: whether % splits into a slash and two rings (gg.ring_split, as
    the tab splits it), and ‰ into a slash and three; then how far apart ‰'s two lower rings are (their inks' gap,
    in ems and against the ring's width), their size against %'s lower ring, and the advance."""
    percent = gen.polygons(m, m.name(0x25)) if m.name(0x25) else []
    if percent:
        split, _ = gg.ring_split(percent, 2)
        rec["percent splits"].append(1.0 if split else 0.0)
    else:
        split = None
    if not m.name(0x2030):
        return
    permille = gen.polygons(m, m.name(0x2030))
    found, _ = gg.ring_split(permille, 3)
    rec["permille splits"].append(1.0 if found else 0.0)
    if not found:
        return
    _, rings = found
    second, third = [gg.box_of([permille[outer]]) for outer, _ in rings[1:]]
    gap = third[0] - second[2]
    rec["permille gap"].append(gap)
    if width(second):
        rec["permille gap/ring"].append(gap / width(second))
        rec["permille third/second"].append(width(third) / width(second))
    if split:
        lower = gg.box_of([percent[split[1][1][0]]])
        if width(lower):
            rec["permille ring/percent ring"].append(width(second) / width(lower))
        pa, ma = m.advance(0x25), m.advance(0x2030)
        if pa and ma:
            rec["permille advance - percent advance"].append(ma - pa)
            rec["permille advance - percent advance - step"].append(ma - pa - (width(second) + gap))


def stem_ratio(m, code, base, scale):
    """How thick a drawn small form's stems are against its source's scaled ones (gg.stem_width, as the tab reads
    them), or None."""
    target, source = gen.polygons(m, m.name(int(code, 16))), gen.polygons(m, m.name(int(base, 16)))
    a, b = gg.stem_width(target), gg.stem_width(source)
    return a / (scale * b) if a and b and scale else None


def measure_strokes(m, x_height, rec):
    """Superscript and subscript letters and small capitals drawn in the font (not composites: those are scaled
    by construction): their stems against their source's scaled to their size (by ink height)."""
    for code, base, kind in SCRIPT_LETTERS:
        tb, bb = m.box(int(code, 16)), m.box(int(base, 16))
        if tb is None or bb is None or not height(bb) or nx.composite_of(m, int(code, 16)):
            continue
        scale = height(tb) / height(bb)
        if 0.2 < scale < 0.95:
            ratio = stem_ratio(m, code, base, scale)
            if ratio and 0.5 < ratio < 2.5:
                rec["strokes %s letter" % kind].append(ratio)
                rec["strokes script letter"].append(ratio)
    for code, base in nx.SMALL_CAPITALS:
        tb, bb = m.box(int(code, 16)), m.box(int(base, 16))
        if tb is None or bb is None or not height(bb) or nx.composite_of(m, int(code, 16)):
            continue
        scale = height(tb) / height(bb)
        if 0.4 < scale < 0.95:
            ratio = stem_ratio(m, code, base, scale)
            if ratio and 0.5 < ratio < 2.5:
                rec["strokes smallcap"].append(ratio)


SCRIPT_LETTERS = script_letters()
EVERY = [c for c, _, _ in CIRCLED_HANGUL] + [c for c, _, _ in PARENTHESIZED] + ["FFA0"] + \
    [c for c, _ in HALF_HANGUL + HALF_SIGNS + KANBUN] + [PERMILLE]


def measure_font(font):
    """{key: this font's median}, the codes of this scope it has, those it makes of components, and whether it has
    kana, Hangul, or ideographs."""
    m = gen.Measured(font)
    h, x = m.box(0x48), m.box(0x78)
    cap, x_height = (h[3] if h else None), (x[3] if x else None)
    codes = set(m.cmap)
    cjk = any(lo <= c <= hi for c in codes for lo, hi in nx.KANA + nx.HAN + ((0xAC00, 0xD7A3),))
    rec = collections.defaultdict(list)
    measure_permille(m, rec)
    if x_height:
        measure_strokes(m, x_height, rec)
    if cjk:
        measure_circled(m, cap or 0.7, rec, codes)
        measure_parenthesized(m, rec)
        nx.measure_cells(m, rec, HALF_HANGUL + HALF_SIGNS, "narrow",
                         lambda code, base: "hangul" if int(code, 16) <= 0xFFDC else "symbol")
        nx.measure_cells(m, rec, KANBUN, "kanbun", lambda code, base: "mark")
        # (whether the font gives a half-width jamo the compatibility jamo's own glyph, and the half-width filler
        # the Hangul filler's: a second code point, no glyph of its own)
        for code, base in HALF_HANGUL + [("FFA0", "3164")] + KANBUN:
            if m.name(int(code, 16)) and m.name(int(base, 16)):
                key = "kanbun" if code in dict(KANBUN) else "narrow filler" if code == "FFA0" else "narrow hangul"
                rec[key + " shared"].append(1.0 if m.name(int(code, 16)) == m.name(int(base, 16)) else 0.0)
                if code == "FFA0" and m.advance(0x3164):
                    rec["narrow filler advance/3164"].append(m.advance(0xFFA0) / m.advance(0x3164))
    found = dict((key, statistics.median(values)) for key, values in rec.items() if values)
    have, built = [], []
    for code in EVERY:
        if int(code, 16) in codes:
            have.append(code)
            if nx.composite_of(m, int(code, 16)):
                built.append(code)
    return found, have, built, cjk


# -- the slices, and the table -----------------------------------------------------------------------------------

def measure_slice(corpus, start, count, records_path):
    """The fonts of files[start:start + count] measured into the records (one per family: a family recorded
    already is skipped)."""
    from fontTools.ttLib import TTFont
    records = nx.read_json(records_path) or {"families": {}}
    files = gen.font_files(corpus)
    began = time.time()
    done = 0
    for path in files[start:start + count]:
        try:
            font = TTFont(path, lazy=True)
            if gen.license_of(font) is None:
                continue
            name = font["name"]
            family = str(name.getDebugName(16) or name.getDebugName(1) or "")
            if not family or family in records["families"]:
                continue
            found, have, built, cjk = measure_font(font)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc))
            continue
        records["families"][family] = {"measures": found, "has": have, "built": built, "cjk": cjk}
        done += 1
    nx.write_json(records_path, records)
    print("%d families measured in %.0f s (files %d to %d of %d); %d in the records" % (
        done, time.time() - began, start, min(start + count, len(files)) - 1, len(files), len(records["families"])))


def figures(layout, prefix, names, least=3):
    """{name: median} of the keys prefix + name measured in at least least families, and "families"."""
    found = dict((name, nx.rounded(nx.median(layout, prefix + name, least=least), 4)) for name in names
                 if nx.median(layout, prefix + name, least=least) is not None)
    if found:
        found["families"] = max(nx.counted_of(layout, prefix + name) for name in names)
    return found


CIRCLE_NAMES = ("diameter", "center", "thickness", "side", "advance", "scale", "content/inner", "squeeze",
                "content x", "content y", "diameter/25EF", "diameter/25CB", "ring component", "round")
CELL_NAMES = ("advance/em", "across", "up", "x share", "raised", "x shift", "bottom shift")
PAREN_NAMES = ("advance/em", "scale", "squeeze", "content x share", "content y", "left x share", "right x share",
               "paren y", "paren up", "paren across")
CLEAR_STROKES = {"families": 20, "q1": 1.03, "spread": 0.15}  # (a rule is clear: enough families, nearly all
# thicker than scaled, and their middle half no wider than this)


def more_rules(layout, records=None):
    """The figures the recipes are placed by, from the corpus's medians (each with how many families)."""
    rules = {"circled": {}, "cells": {"halfwidth": {}}, "parenthesized": {}}
    for cls in ("jamo", "syllable", "word"):
        found = figures(layout, "circled cjk %s " % cls, CIRCLE_NAMES)
        if found:
            found["families"] = nx.counted_of(layout, "circled cjk %s diameter" % cls)
            rules["circled"]["cjk %s" % cls] = found
    for cls in ("jamo", "syllable", "word", "ideograph"):
        found = figures(layout, "paren %s " % cls, PAREN_NAMES)
        if found:
            rules["parenthesized"][cls] = found
    # (the half-width signs' cells; the half-width jamo are their compatibility jamo's own glyph in every family
    # measured, and the kanbun marks their ideograph at its own size: their medians stay in more_layout)
    for cls in ("symbol",) + tuple(code for code, _ in HALF_SIGNS):
        found = figures(layout, "narrow %s " % cls, CELL_NAMES)
        if found:
            found["families"] = nx.counted_of(layout, "narrow %s advance/em" % cls)
            rules["cells"]["halfwidth"][cls] = found
    permille = figures(layout, "permille ", ("gap", "gap/ring", "third/second", "ring/percent ring",
                                             "advance - percent advance", "advance - percent advance - step"))
    for key in ("percent splits", "permille splits"):
        if key in layout:
            permille[key.split()[0] + " splits"] = layout[key]["median"]
            permille[key.split()[0] + " measured"] = layout[key]["n"]
    rules["permille"] = permille
    strokes = {}
    for key in ("script letter", "super letter", "sub letter", "smallcap"):
        found = layout.get("strokes " + key)
        if found:
            clear = found["n"] >= CLEAR_STROKES["families"] and found["q1"] >= CLEAR_STROKES["q1"] and \
                found["q3"] - found["q1"] <= CLEAR_STROKES["spread"]
            strokes[key] = dict(found, clear=clear)
            if records:  # (how many families lie within a tenth of the median)
                values = [f["measures"]["strokes " + key] for f in records["families"].values()
                          if "strokes " + key in f["measures"]]
                strokes[key]["near"] = sum(1 for v in values if abs(v - found["median"]) <= 0.1 * found["median"])
    rules["strokes"] = strokes
    return rules


GROUPS = (("parenthesized", u"Parenthesized Hangul and ideographs"), ("kanbun", u"Kanbun annotation marks"))
AGL_NAMES = {"2030": u"perthousand"}  # (the Adobe Glyph List's: Glyphs' list names no character here)
ONLY = {"jamo": "jamo", "syllable": "hangul", "word": "hangul", "ideograph": "han"}


def members():
    """[(group, code, way list)] of this scope."""
    found = []
    for code, drawn, cls in CIRCLED_HANGUL:
        found.append(("circled", code, [{"op": "circle", "of": drawn, "class": cls, "confidence": S,
                                         "only": ONLY[cls]}]))
    for code, drawn, cls in PARENTHESIZED:
        found.append(("parenthesized", code, [{"op": "paren", "of": drawn, "class": cls, "confidence": S,
                                               "only": ONLY[cls]}]))
    # The half-width filler: an empty glyph as wide as the Hangul filler (the median of the 5 families with both),
    # else as a jamo; the half-width jamo: a second code point on the compatibility jamo's own glyph, as 12 of the 14
    # families with them give it (the corpus wins over a narrowed cell: only Unifont and Plangothic P2 draw them half
    # as wide)
    found.append(("halfwidth", "FFA0", [{"op": "width", "advance_of": "3164", "confidence": A, "only": "jamo"},
                                        {"op": "width", "advance_of": "3131", "confidence": S, "only": "jamo"}]))
    for code, base in HALF_HANGUL:
        found.append(("halfwidth", code, [{"op": "shared", "of": base, "confidence": A, "only": "jamo"}]))
    for code, base in HALF_SIGNS:
        found.append(("halfwidth", code, [{"op": "cell", "of": base, "cell": "halfwidth", "confidence": S,
                                          "only": "cjk"}]))
    # The kanbun marks: their ideograph at its own size and place in a full-width cell, as the corpus draws them
    for code, base in KANBUN:
        found.append(("kanbun", code, [{"op": "copy", "of": base, "confidence": S, "only": "han"}]))
    found.append(("punctuation", PERMILLE, [{"op": "permille", "of": PERCENT, "confidence": S}]))
    return found


def write(records_path, table_path):
    records = nx.read_json(records_path)
    layout = nx.layout_of(records)
    table = nx.read_json(table_path)
    have = collections.Counter(code for f in records["families"].values() for code in f["has"])
    built = collections.Counter(code for f in records["families"].values() for code in f["built"])
    mine = set(code for _, code, _ in members())
    table["entries"] = [e for e in table["entries"] if e["code"] not in mine]
    ids = set(group for group, _ in GROUPS)
    table["groups"] = [g for g in table["groups"] if g["id"] not in ids]
    entries = []
    for group, code, ways in members():
        name = unicodedata.name(chr(int(code, 16)), u"")
        entries.append({"code": code, "group": group, "unicode_name": name,
                        "glyph_name": AGL_NAMES.get(code) or u"uni" + code, "ways": ways,
                        "research_confidence": ways[0]["confidence"], "families": have[code],
                        "deriving": built[code], "most": None})
    table["entries"] += entries
    for group, title in GROUPS:
        table["groups"].append({"id": group, "title": title, "count": 0})
    for group in table["groups"]:
        group["count"] = sum(1 for e in table["entries"] if e["group"] == group["id"])
    table["characters"] = gen.characters(table["entries"])
    for e in table["entries"]:  # (the parts a way is made of, named for the notes too: as generation_next does)
        for way in e["ways"]:
            named = way["of"] if isinstance(way.get("of"), list) else [way["of"]] if way.get("of") else []
            for part in named + ([way["advance_of"]] if way.get("advance_of") not in (None, "figure") else []):
                table["characters"].setdefault(part, {"category": unicodedata.category(chr(int(part, 16))),
                                                      "name": gen.unicode_name(part)})
    rules = more_rules(layout, records)
    table["rules"]["circled"].update(rules["circled"])
    for group, found in rules["cells"].items():
        table["rules"]["cells"].setdefault(group, {}).update(found)
    for key in ("parenthesized", "permille", "strokes"):
        table["rules"][key] = rules[key]
    table["more_scope"] = {"families": len(records["families"]),
                           "cjk_families": sum(1 for f in records["families"].values() if f["cjk"]),
                           "unicode": unicodedata.unidata_version}
    table["more_layout"] = dict((key, value) for key, value in layout.items()
                                if not (key.split()[0] in ("narrow", "kanbun") and len(key.split()[1]) == 4))
    gen.write_table(table, table_path)
    print("%d characters added, from %d families (%d with kana, Hangul, or ideographs); Unicode %s" % (
        len(entries), len(records["families"]), table["more_scope"]["cjk_families"], unicodedata.unidata_version))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--records", required=True, help="the per-family records (kept between the slices)")
    parser.add_argument("--corpus", default=gen.CORPUS)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--write", action="store_true", help="write the table from the records")
    parser.add_argument("--table", default=TABLE)
    parser.add_argument("--list", action="store_true", help="say how many characters each group holds")
    args = parser.parse_args()
    if args.list:
        print(collections.Counter(group for group, _, _ in members()))
        print("font files:", len(gen.font_files(args.corpus)))
        return
    if args.write:
        write(args.records, args.table)
        return
    measure_slice(args.corpus, args.start, args.count, args.records)


if __name__ == "__main__":
    main()
