"""Learn how fonts space their straight and round references (H, O, l, n, o, zero; Armenian's vo and oh,
capital and small; Georgian's in and on, Mkhedruli and Mtavruli), from the open-licensed fonts at hand (SIL Open Font License and Apache License fonts only, as kerning/train/dataset.py finds
them, plus FreeLab's corpus folder, %LOCALAPPDATA%\\FreeLab\\corpus).

Auto Spacing spaces every other glyph against these references, as Walter Tracy's method does; a font
with nothing done yet has them unspaced. For each family (its first font found), each reference's
sidebearings are measured as shares of its height (the cap height for H, O, and zero; the x-height
for n and o; the straight reference's own height in Armenian and Georgian) and as shares of its own
ink's width; the measure that varies less across families is kept, with its median, where enough
families have the reference (MIN_FAMILIES; fewer for Armenian and Georgian, which few open fonts
have). The result is spacing/reference_model.json.

    python spacing/train/references.py [--out <file.json>]

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
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import dataset  # noqa: E402  (the corpus's folders and its license check)

MODEL_FILE = os.path.join(HERE, os.pardir, "reference_model.json")
CORPUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus")
REFERENCES = {"H": "H", "O": "H", "n": "x", "o": "x", "0": "H",  # each reference and the letter giving its height
              "l": "x",  # (a tuning letter beside n and o: spaced with them, or ll no longer agreed with nn and oo)
              "\N{ARMENIAN CAPITAL LETTER VO}": "\N{ARMENIAN CAPITAL LETTER VO}",
              "\N{ARMENIAN CAPITAL LETTER OH}": "\N{ARMENIAN CAPITAL LETTER VO}",
              "\N{ARMENIAN SMALL LETTER VO}": "\N{ARMENIAN SMALL LETTER VO}",
              "\N{ARMENIAN SMALL LETTER OH}": "\N{ARMENIAN SMALL LETTER VO}",
              "\N{GEORGIAN MTAVRULI CAPITAL LETTER IN}": "\N{GEORGIAN MTAVRULI CAPITAL LETTER IN}",
              "\N{GEORGIAN MTAVRULI CAPITAL LETTER ON}": "\N{GEORGIAN MTAVRULI CAPITAL LETTER IN}",
              "\N{GEORGIAN LETTER IN}": "\N{GEORGIAN LETTER IN}", "\N{GEORGIAN LETTER ON}": "\N{GEORGIAN LETTER IN}"}
MIN_FAMILIES = {"latin": 10, "other": 3}  # a reference measured in fewer families than this is left out
STYLE_WORDS = ("italic", "oblique", "bold", "black", "light", "thin", "condensed", "expanded", "mono", "code")


def measure(font):
    """{reference: (left / height, right / height, left / ink width, right / ink width)} of one font."""
    from fontTools.pens.boundsPen import BoundsPen
    cmap = font["cmap"].getBestCmap() or {}
    glyph_set = font.getGlyphSet()
    metrics = font["hmtx"].metrics

    def box(ch):
        name = cmap.get(ord(ch))
        if name is None:
            return None, None
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        return pen.bounds, metrics[name][0]

    heights = {}
    for ch in set(REFERENCES.values()):
        bounds, _ = box(ch)
        if bounds:
            heights[ch] = bounds[3] - max(bounds[1], 0)
    found = {}
    for ch, by in REFERENCES.items():
        bounds, advance = box(ch)
        height = heights.get(by)
        if not bounds or not height:
            continue
        left, right = bounds[0], advance - bounds[2]
        width = bounds[2] - bounds[0]
        if width > 0:
            found[ch] = (left / height, right / height, left / width, right / width)
    return found


def regular(family_fonts):
    """The family's plainest font: the first whose style names no weight, width, or slope."""
    for path, index, font in family_fonts:
        style = str(font["name"].getDebugName(2) or "").lower()
        if not any(word in style for word in STYLE_WORDS):
            return font
    return family_fonts[0][2]


def families():
    from fontTools.ttLib import TTCollection, TTFont
    by_family = {}
    for folder in tuple(dataset.FONT_DIRS) + (CORPUS_DIR,):
        for pattern in ("*.ttf", "*.otf", "*.ttc", "*.otc"):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                try:
                    collection = path.lower().endswith((".ttc", ".otc"))
                    fonts = TTCollection(path, lazy=True).fonts if collection else [TTFont(path, lazy=True)]
                except Exception:
                    continue
                for index, font in enumerate(fonts):
                    try:
                        if dataset.license_of(font):
                            name = dataset.family_of(font)
                            if any(word in name.lower() for word in ("mono", "code")):
                                continue  # one width for all: not spaced by eye
                            by_family.setdefault(name, []).append((path, index, font))
                    except Exception:
                        continue
    return by_family


def spread(values):
    """How much values vary: their interquartile range over their median."""
    values = sorted(values)
    if len(values) < 4 or not statistics.median(values):
        return float("inf")
    q1, q3 = values[len(values) // 4], values[(3 * len(values)) // 4]
    return abs((q3 - q1) / statistics.median(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=MODEL_FILE)
    args = parser.parse_args()
    measured = []
    for family, fonts in sorted(families().items()):
        try:
            found = measure(regular(fonts))
        except Exception:
            continue
        if ("H" in found and "n" in found) or any(ch in found for ch in REFERENCES if ord(ch) > 0x7F):
            measured.append(found)
    model = {"format": 1, "families": len(measured), "references": {}}
    for ch, by in REFERENCES.items():
        rows = [found[ch] for found in measured if ch in found]
        if len(rows) < MIN_FAMILIES["latin" if ord(ch) < 0x80 else "other"]:
            continue
        by_height = spread([r[0] for r in rows]) + spread([r[1] for r in rows])
        by_width = spread([r[2] for r in rows]) + spread([r[3] for r in rows])
        use = (0, 1, "height") if by_height <= by_width else (2, 3, "width")
        model["references"][ch] = {
            "by": use[2], "height_of": by, "left": round(statistics.median(r[use[0]] for r in rows), 4),
            "right": round(statistics.median(r[use[1]] for r in rows), 4),
            "spread": round(min(by_height, by_width), 3) if min(by_height, by_width) < float("inf") else None,
            "families": len(rows)}
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    print("%d families" % len(measured))
    for ch, row in sorted(model["references"].items()):
        print("  %s: %s" % (ch, row))


if __name__ == "__main__":
    main()
