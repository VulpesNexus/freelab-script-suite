"""Learn which ligatures fonts make standard and which discretionary, from the open-licensed fonts at
hand (SIL Open Font License and Apache License fonts only, as kerning/train/dataset.py finds them,
plus FreeLab's corpus folder, %LOCALAPPDATA%\\FreeLab\\corpus).

For each family (its first font found), every ligature its liga, clig, dlig, and hlig features make
from encoded characters is counted under the feature it is in: f f i in liga, c t in dlig. The counts,
per character sequence found in at least three families, are features/ligature_model.json: Feature
Code sets a ligature whose feature the font does not settle by them (liga when more families have it
there than in dlig).

    python features/train/ligatures.py [--out <file.json>]

Python 3 with fonttools. Only the counts leave the fonts; the fonts are not copied.
"""

import argparse
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "kerning", "train"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import dataset  # noqa: E402  (the corpus's folders and its license check)

MODEL_FILE = os.path.join(HERE, os.pardir, "ligature_model.json")
CORPUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")
FEATURES = {"liga": "liga", "clig": "liga", "dlig": "dlig", "hlig": "dlig"}  # counted as standard or discretionary
MIN_FAMILIES = 3


def ligatures_of(font):
    """{(character sequence, "liga" or "dlig")} a font's ligature features make from encoded glyphs."""
    if "GSUB" not in font:
        return set()
    cmap = font["cmap"].getBestCmap() or {}
    char_of = {}
    for code, name in sorted(cmap.items()):
        char_of.setdefault(name, chr(code))
    gsub = font["GSUB"].table
    if gsub.FeatureList is None or gsub.LookupList is None:
        return set()
    found = set()
    for record in gsub.FeatureList.FeatureRecord:
        kind = FEATURES.get(record.FeatureTag)
        if kind is None:
            continue
        for index in record.Feature.LookupListIndex:
            lookup = gsub.LookupList.Lookup[index]
            for sub in lookup.SubTable:
                if lookup.LookupType == 7:
                    sub = sub.ExtSubTable
                if getattr(sub, "LookupType", lookup.LookupType) != 4 or not hasattr(sub, "ligatures"):
                    continue
                for first, entries in sub.ligatures.items():
                    for entry in entries:
                        names = [first] + list(entry.Component)
                        if all(name in char_of for name in names):
                            found.add(("".join(char_of[name] for name in names), kind))
    return found


def families():
    from fontTools.ttLib import TTCollection, TTFont
    seen = {}
    for folder in tuple(dataset.FONT_DIRS) + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf", "*.ttc", "*.otc"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    collection = path.lower().endswith((".ttc", ".otc"))
                    fonts = TTCollection(path, lazy=True).fonts if collection else [TTFont(path, lazy=True)]
                except Exception:
                    continue
                for font in fonts:
                    try:
                        family = dataset.family_of(font)
                        if family in seen or not dataset.license_of(font):
                            continue
                        seen[family] = ligatures_of(font)
                    except Exception:
                        continue
    return seen


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    found = families()
    counts = {}
    for family, ligatures in found.items():
        for chars, kind in ligatures:
            counts.setdefault(chars, {"liga": 0, "dlig": 0})[kind] += 1
    kept = dict((chars, [c["liga"], c["dlig"]]) for chars, c in counts.items() if c["liga"] + c["dlig"] >= MIN_FAMILIES)
    model = {"format": 1, "families": len(found),
             "with_ligatures": sum(1 for ligatures in found.values() if ligatures),
             "note": "character sequence: [families with it in liga or clig, families with it in dlig or hlig]",
             "ligatures": kept}
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, indent=0, sort_keys=True, ensure_ascii=True) + "\n")
    print("%d families, %d with ligatures, %d sequences kept" % (len(found), model["with_ligatures"], len(kept)))
    for chars, (liga, dlig) in sorted(kept.items(), key=lambda item: -sum(item[1]))[:30]:
        print("  %s: liga %d, dlig %d" % (chars.encode("unicode_escape").decode("ascii"), liga, dlig))


if __name__ == "__main__":
    main()
