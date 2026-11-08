"""Learn which characters fonts put in the same kerning class, from the open-licensed fonts installed
on this computer (the corpus of dataset.py: SIL Open Font License and Apache License fonts only).

For every family, the kerning classes of its first font that kerns by classes (GPOS pair adjustment
by class, format 2) are read, each glyph taken as the character the font maps to it. Two characters
are counted together on a side when a subtable puts them in one class, and apart when it puts them in
two. "first" is the first glyph of a pair (its right side faces the pair), "second" the second glyph
(its left side). The result, kerning/class_model.json, holds for every pair of characters seen in
enough families how many put them together and apart; Auto Kerning's class suggestions take it as a
prior and check each class against the font's own outlines.

    python kerning/train/classes.py [--exclude <file name part>] [--out <file.json>]

Python 3 with fonttools. Only the counts leave the fonts; the fonts are not copied.
"""

import argparse
import io
import json
import os
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dataset  # noqa: E402  (its corpus: open-licensed, kerned fonts with l, n, and o)

MODEL_FILE = os.path.join(HERE, os.pardir, "class_model.json")
MIN_FAMILIES = 5  # pairs of characters seen in fewer families than this are left out
MIN_RATE = 0.2  # nor pairs fewer of their families class together: Auto Kerning reads them as never together
# (a letter and its base, A and Á, are kept at any rate: Auto Kerning tells "rarely" from "never seen")
SIDES = ("first", "second")


def wanted(ch):
    """Latin letters (Basic Latin to Latin Extended-B), figures, and Auto Kerning's punctuation."""
    code = ord(ch)
    if ch in dataset.ak.PUNCTUATION or ch in dataset.ak.FIGURES:
        return True
    return 0x41 <= code <= 0x24F and unicodedata.category(ch).startswith("L")


def related(a, b):
    """A letter and the letter it is built on (A and Á, L and Ŀ)."""
    return dataset.ak.base_letter(a) == b or dataset.ak.base_letter(b) == a


def class_kerning(font):
    """For each side, the classes of every class-kerning subtable of the font's kern feature, as sets
    of glyph names (class 0, "every other glyph", left out)."""
    if "GPOS" not in font:
        return None
    table = font["GPOS"].table
    lookups = set()
    for record in table.FeatureList.FeatureRecord:
        if record.FeatureTag == "kern":
            lookups.update(record.Feature.LookupListIndex)
    found = {"first": [], "second": []}
    for index in sorted(lookups):
        lookup = table.LookupList.Lookup[index]
        for subtable in lookup.SubTable:
            if lookup.LookupType == 9:  # extension
                subtable = subtable.ExtSubTable
            if getattr(subtable, "LookupType", lookup.LookupType) != 2 or subtable.Format != 2:
                continue
            for side, classdef in (("first", subtable.ClassDef1), ("second", subtable.ClassDef2)):
                classes = {}
                for glyph, number in (classdef.classDefs if classdef else {}).items():
                    if number:
                        classes.setdefault(number, set()).add(glyph)
                if side == "first":  # ClassDef1 covers only glyphs of the coverage
                    covered = set(subtable.Coverage.glyphs)
                    classes = dict((n, members & covered) for n, members in classes.items())
                found[side].append([members for members in classes.values() if members])
    return found if any(found.values()) else None


def family_counts(font):
    """{side: {(a, b): together}} for one font: together True when a subtable classes a and b
    together, False when one classes them apart (together wins)."""
    classes = class_kerning(font)
    if classes is None:
        return None
    cmap = font["cmap"].getBestCmap() or {}
    character = {}
    for code, glyph in cmap.items():
        ch = chr(code)
        if wanted(ch):
            character.setdefault(glyph, ch)
    counts = {}
    for side in SIDES:
        seen = counts.setdefault(side, {})
        for subtable in classes[side]:
            located = {}
            for number, members in enumerate(subtable):
                for glyph in members:
                    if glyph in character:
                        located[character[glyph]] = number
            chars = sorted(located)
            for i, a in enumerate(chars):
                for b in chars[i + 1:]:
                    together = located[a] == located[b]
                    seen[(a, b)] = seen.get((a, b), False) or together
    return counts


def main():
    from fontTools.ttLib import TTCollection, TTFont
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude", default="", help="leave out the fonts whose file name contains this")
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    started = time.time()
    totals = dict((side, {}) for side in SIDES)
    families_done, used = set(), 0
    for path, index, family, licence in dataset.open_fonts():
        if family in families_done or (args.exclude and args.exclude.lower() in os.path.basename(path).lower()):
            continue
        try:
            collection = path.lower().endswith((".ttc", ".otc"))
            font = TTCollection(path).fonts[index] if collection else TTFont(path)
            counts = family_counts(font)
        except Exception as exc:
            print("skipped %s: %s" % (os.path.basename(path), exc), flush=True)
            continue
        if not counts:
            continue  # kerned by pairs alone: another font of the family may class
        families_done.add(family)
        used += 1
        for side in SIDES:
            for pair, together in counts[side].items():
                entry = totals[side].setdefault(pair, [0, 0])
                entry[0 if together else 1] += 1
    model = {"format": 1, "sides": {}, "info": {
        "built": time.strftime("%Y-%m-%d"), "families": used, "min families": MIN_FAMILIES, "min rate": MIN_RATE,
        "licenses": "SIL Open Font License and Apache License fonts only",
        "sides": "first: the first glyph of a pair (its right side); second: the second glyph (its left side)"}}
    for side in SIDES:
        model["sides"][side] = sorted([a + b, together, apart] for (a, b), (together, apart) in totals[side].items()
                                      if together + apart >= MIN_FAMILIES
                                      and (together >= MIN_RATE * (together + apart) or related(a, b)))
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(model, handle, ensure_ascii=False, separators=(",", ":"))
    print("%d families kern by classes; %s (%.0f s)" % (used, ", ".join(
        "%s side: %d pairs of characters" % (side, len(model["sides"][side])) for side in SIDES), time.time() - started))


if __name__ == "__main__":
    main()
