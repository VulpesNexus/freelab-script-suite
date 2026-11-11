"""Which characters fonts give stylistic alternates, from the open-licensed fonts of the corpus (SIL Open
Font License or Apache License, as kerning/train/dataset.py reads their name table).

For each family (one font per family), the single and alternate substitutions of its stylistic
features (ss01-ss20, cv01-cv99, salt) are read from GSUB, and each encoded glyph they replace is
counted once per family, with the feature kinds and the names its alternates take. The report
ranks the characters by how many families vary them: the list Feature Code suggests alternates
from. Run from the repository (Python 3, fontTools):

    python features/train/alternates.py [--fonts DIR] [--json OUT]
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "kerning", "train"))
import dataset  # noqa: E402  (the license check, the corpus folder)

STYLISTIC = ("salt",) + tuple("ss%02d" % n for n in range(1, 21)) + tuple("cv%02d" % n for n in range(1, 100))


def lookup_substitutions(gsub, index):
    """{input glyph: [output glyphs]} of a lookup's single and alternate substitutions (extensions opened)."""
    found = {}
    lookup = gsub.LookupList.Lookup[index]
    for sub in lookup.SubTable:
        kind = lookup.LookupType
        if kind == 7:
            kind, sub = sub.ExtSubTable.LookupType, sub.ExtSubTable
        if kind == 1:
            for source, target in sub.mapping.items():
                found.setdefault(source, []).append(target)
        elif kind == 3:
            for source, targets in sub.alternates.items():
                found.setdefault(source, []).extend(targets)
    return found


def font_alternates(path, index=0):
    """{character: (set of feature kinds, [alternate glyph names])} of one font, or None (no GSUB)."""
    from fontTools.ttLib import TTFont
    font = TTFont(path, fontNumber=index, lazy=True)
    if dataset.license_of(font) is None:
        return None, "not open-licensed"
    if "GSUB" not in font:
        return None, "no GSUB"
    gsub = font["GSUB"].table
    if gsub.FeatureList is None or gsub.LookupList is None:
        return None, "no features"
    reverse = {}
    for code, name in (font["cmap"].getBestCmap() or {}).items():
        reverse.setdefault(name, code)
    found = {}
    for record in gsub.FeatureList.FeatureRecord:
        tag = record.FeatureTag
        if tag not in STYLISTIC:
            continue
        kind = "ss" if tag.startswith("ss") else ("cv" if tag.startswith("cv") else "salt")
        for lookup_index in record.Feature.LookupListIndex:
            for source, targets in lookup_substitutions(gsub, lookup_index).items():
                code = reverse.get(source)
                if code is None:
                    continue
                kinds, names = found.setdefault(chr(code), (set(), []))
                kinds.add(kind)
                names.extend(t for t in targets if t not in names)
    return found, None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fonts", default=None, help="one folder (default: the corpus and the system's fonts)")
    parser.add_argument("--json")
    args = parser.parse_args()
    folders = [args.fonts] if args.fonts else list(dataset.FONT_DIRS) + [dataset.CORPUS_DIR]
    families, skipped, counts = {}, {}, {}
    from fontTools.ttLib import TTFont
    for folder in folders:
        for pattern in ("*.ttf", "*.otf"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    family = dataset.family_of(TTFont(path, lazy=True)) or os.path.basename(path)
                    if family in families:
                        continue
                    result, why = font_alternates(path)
                except Exception as exc:
                    result, why = None, "unreadable (%s)" % type(exc).__name__
                if result is None:
                    skipped[why] = skipped.get(why, 0) + 1
                    continue
                families[family] = len(result)
                for ch, (kinds, names) in result.items():
                    row = counts.setdefault(ch, {"families": 0, "kinds": {}, "examples": []})
                    row["families"] += 1
                    for kind in kinds:
                        row["kinds"][kind] = row["kinds"].get(kind, 0) + 1
                    if len(row["examples"]) < 6:
                        row["examples"].append(u"%s: %s" % (family, u" ".join(names[:3])))
    with_any = sum(1 for n in families.values() if n)
    print("%d families read (%d with stylistic alternates); skipped: %s" % (
        len(families), with_any, ", ".join("%s %d" % item for item in sorted(skipped.items()))))
    ranked = sorted(counts.items(), key=lambda item: (-item[1]["families"], item[0]))
    for ch, row in ranked[:60]:
        print("%s U+%04X %3d families  %s" % (ch, ord(ch), row["families"],
                                           " ".join("%s %d" % k for k in sorted(row["kinds"].items()))))
    if args.json:
        report = {"format": 1, "families": len(families), "with_alternates": with_any,
                  "characters": [{"char": ch, "families": row["families"], "kinds": row["kinds"],
                                  "examples": row["examples"]} for ch, row in ranked]}
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
