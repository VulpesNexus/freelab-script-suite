"""Find ClearType's colored fringes left in a screenshot of dark mode, and show where they are.

    python tools/find_fringes.py shot.png [more.png ...] [--out sheet.png] [--top 24] [--scale 5]

ClearType draws a stroke's two sides in opposite hues (orange and blue). On a light interface the eye reads
them as sharpness; left in a picture dark mode has mapped, they read as colored edges around text. Looking for
them by eye over a whole window misses most. This counts, for each pixel, the pixels of the opposite hue within
three pixels along its row (both clearly colored), sums the counts over squares of the picture, and writes a
sheet of the worst squares, enlarged, each with its place in the screenshot and its score, worst first. The
same squares are printed. A square with intended colors side by side (a color bar, the hinting preview, which
shows ClearType on purpose) scores too: the sheet is for looking at, the scores for comparing two builds of
the same screen.

Needs Pillow and numpy. Nothing here runs inside FontLab.
"""

import argparse
import os
import sys

MIN_SPREAD = 30  # max - min of a pixel's channels: clearly colored
REACH = 3  # pixels along the row, each way
OPPOSITE_COS = -0.5  # the two pixels' hues, as vectors off gray
CELL = 32  # the side of a square, in pixels of the screenshot


def fringe_map(rgb):
    """For an (h, w, 3) array: an (h, w) array of how many opposite-hue neighbors each colored pixel has."""
    import numpy as np
    values = rgb.astype(np.float32)
    off_gray = values - values.mean(axis=2, keepdims=True)
    colored = (values.max(axis=2) - values.min(axis=2)) >= MIN_SPREAD
    norm = np.sqrt((off_gray ** 2).sum(axis=2))
    norm[norm == 0] = 1.0
    unit = off_gray / norm[:, :, None]
    count = np.zeros(colored.shape, dtype=np.int32)
    for d in range(1, REACH + 1):
        cos = (unit[:, d:, :] * unit[:, :-d, :]).sum(axis=2)
        both = colored[:, d:] & colored[:, :-d] & (cos <= OPPOSITE_COS)
        count[:, d:] += both
        count[:, :-d] += both
    return count


def worst_cells(count, top):
    """[(score, x, y)] of the squares with the most fringe pairs, worst first."""
    import numpy as np
    h, w = count.shape
    rows, cols = h // CELL, w // CELL
    cells = count[:rows * CELL, :cols * CELL].reshape(rows, CELL, cols, CELL).sum(axis=(1, 3))
    order = np.argsort(cells, axis=None)[::-1][:top]
    found = []
    for index in order:
        y, x = divmod(int(index), cols)
        if cells[y, x] > 0:
            found.append((int(cells[y, x]), x * CELL, y * CELL))
    return found


def sheet(image, cells, scale, margin=8):
    """One picture of the squares, enlarged (with a margin of their surroundings), in rows of six."""
    from PIL import Image, ImageDraw
    side = (CELL + 2 * margin) * scale
    per_row = 6
    rows = (len(cells) + per_row - 1) // per_row
    out = Image.new("RGB", (per_row * (side + 6) + 6, max(1, rows) * (side + 22) + 6), (90, 0, 0))
    draw = ImageDraw.Draw(out)
    for n, (score, x, y) in enumerate(cells):
        box = (max(0, x - margin), max(0, y - margin), min(image.width, x + CELL + margin), min(image.height, y + CELL + margin))
        part = image.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.NEAREST)
        left, top = 6 + (n % per_row) * (side + 6), 6 + (n // per_row) * (side + 22)
        out.paste(part, (left, top + 16))
        draw.text((left, top), "%d at %d,%d" % (score, x, y), fill=(255, 255, 255))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pictures", nargs="+")
    parser.add_argument("--out", help="the sheet to write (default: beside the first picture, .fringes.png)")
    parser.add_argument("--top", type=int, default=24, help="how many squares to show for each picture")
    parser.add_argument("--scale", type=int, default=5)
    args = parser.parse_args()
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        sys.exit("find_fringes needs Pillow and numpy (%s)" % exc)
    sheets = []
    for path in args.pictures:
        image = Image.open(path).convert("RGB")
        count = fringe_map(np.asarray(image))
        cells = worst_cells(count, args.top)
        print("%s: %d fringe pairs in all, %d squares with some" % (os.path.basename(path), int(count.sum()) // 2, int((count.reshape(-1) > 0).sum() > 0) and len(cells)))
        for score, x, y in cells:
            print("  %5d at %d,%d" % (score, x, y))
        sheets.append(sheet(image, cells, args.scale))
    out = args.out or os.path.splitext(args.pictures[0])[0] + ".fringes.png"
    total = Image.new("RGB", (max(s.width for s in sheets), sum(s.height for s in sheets)), (90, 0, 0))
    y = 0
    for s in sheets:
        total.paste(s, (0, y))
        y += s.height
    total.save(out)
    print("sheet: %s" % out)


if __name__ == "__main__":
    main()
