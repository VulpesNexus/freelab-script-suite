"""Learn how Korean fonts space Hangul, from the open-licensed fonts at hand (SIL Open Font License and
Apache License fonts only, as kerning/train/dataset.py finds them, plus FreeLab's corpus folder,
%LOCALAPPDATA%\\FreeLab\\corpus, where OFL fonts from Google Fonts were put).

None of the corpus's Korean fonts kerns Hangul or trims it in palt: they set every syllable at one
width (Noto Sans KR, IBM Plex Sans KR, Gothic A1...) or give each its own (Gowun Dodum, Jua, Dongle...).
For the first kind, the width is measured, as a share of the em; for the second, each syllable's
sidebearings, as shares of the em, per syllable shape: its vowel to the right of its initial (가),
under it (고), or both (과), with or without a final consonant (각). The medians are
cjk/hangul_model.json: CJK Spacing sets a font's Hangul by them.

    python cjk/train/hangul.py [--out <file.json>]

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
from freelab_cjk_spacing import hangul_shape  # noqa: E402  (the syllable shapes, as CJK Spacing groups them)

MODEL_FILE = os.path.join(HERE, os.pardir, "hangul_model.json")
CORPUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")
SAMPLE_STEP = 7  # every seventh syllable is measured (all shapes are many times over)


def measure(path):
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    upm = float(font["head"].unitsPerEm)
    cmap = font["cmap"].getBestCmap() or {}
    names = [(code, name) for code, name in sorted(cmap.items()) if 0xAC00 <= code <= 0xD7A3]
    if len(names) < 2000:
        return None
    metrics = font["hmtx"].metrics
    widths = set(metrics[name][0] for _, name in names)
    glyph_set = font.getGlyphSet()
    sides = {}
    for code, name in names[::SAMPLE_STEP]:
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        if not pen.bounds:
            continue
        left, _, right, _ = pen.bounds
        advance = metrics[name][0]
        sides.setdefault(hangul_shape(code), []).append((left / upm, (advance - right) / upm))
    return {"fixed": len(widths) <= 3, "width": statistics.median(metrics[n][0] for _, n in names) / upm, "sides": sides}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    from fontTools.ttLib import TTFont
    fixed, proportional, seen = [], [], set()
    for folder in tuple(dataset.FONT_DIRS) + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    font = TTFont(path, lazy=True)
                    family = dataset.family_of(font)
                    if family in seen or not dataset.license_of(font):
                        continue
                    measured = measure(path)
                except Exception:
                    continue
                if measured is None:
                    continue
                seen.add(family)
                (fixed if measured["fixed"] else proportional).append(measured)
                print("  %s: %s, median width %.3f em" % (family, "one width" if measured["fixed"] else "proportional",
                                                         measured["width"]))
    model = {"format": 1, "fixed_fonts": len(fixed), "proportional_fonts": len(proportional),
             "fixed_width": round(statistics.median(m["width"] for m in fixed), 4) if fixed else None,
             "proportional": {}}
    shapes = set(shape for m in proportional for shape in m["sides"])
    for shape in sorted(shapes):
        rows = [m["sides"][shape] for m in proportional if m["sides"].get(shape)]
        if len(rows) >= 2:
            model["proportional"][shape] = [round(statistics.median(statistics.median(a for a, _ in r) for r in rows), 4),
                                            round(statistics.median(statistics.median(b for _, b in r) for r in rows), 4)]
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, indent=1, sort_keys=True) + "\n")
    print("%d fonts at one width, %d proportional" % (len(fixed), len(proportional)))
    print(json.dumps(model, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
