"""Add vertical metrics (vhea and vmtx, and VORG for a CFF font) to a font FontLab 7 exported.

FontLab 7's export writes no vhea, vmtx, or VORG table, whatever the font holds (docs/VERTICAL.md). CJK
Vertical's *Add vertical metrics to an exported font* runs this inside FontLab, and writes the FontLab
font's own values beside the exported font, as <font file>.vertical.json: the vertical origin (the
typographic ascender), vhea's ascender, descender, and line gap, and each glyph's advance height. Run on
its own, this script reads both and writes a copy of the font with the vertical tables, <name>.vert.<ext>,
beside it; the exported font is never changed.

    python add_vertical_metrics.py <exported font> [--values <json>] [--out <file>] [--force]

Each glyph's top sidebearing is the vertical origin less its ink's top; a glyph without ink gets 0. VORG
gives a CFF font's vertical origin (one default for all glyphs). Glyphs are matched by name, then by code
point where the export renamed one. The tables written are read back and checked.

Python 3 with fontTools, or FontLab 7's own Python 2.7, which ships fontTools 3.43 (CJK Vertical runs
add_tables() and check() there). With uharfbuzz, it also says how HarfBuzz sets a sample vertically.
"""

from __future__ import absolute_import, division, print_function

import argparse
import io
import json
import os
import sys

VALUES_SUFFIX = ".vertical.json"


def values_path(font_path):
    return font_path + VALUES_SUFFIX


def output_path(font_path):
    stem, ext = os.path.splitext(font_path)
    return stem + ".vert" + ext


def load_values(path):
    with io.open(path, encoding="utf-8") as handle:
        values = json.load(handle)
    if values.get("format") != 1:
        raise ValueError("%s: not a vertical metrics file of a known format" % path)
    return values


def heights_by_glyph(glyph_order, cmap, values):
    """{glyph: advance height} for the exported font's glyphs: by name from the values, else by a code point
    the values give the glyph (an export that renamed it), else the default (the em)."""
    heights, by_code = values.get("heights") or {}, {}
    for name, codes in (values.get("codes") or {}).items():
        for code in codes:
            by_code.setdefault(int(code), name)
    names_of = {}
    for code, name in cmap.items():
        names_of.setdefault(name, []).append(code)
    default = int(round(values.get("default_height") or values.get("upm") or 1000))
    found = {}
    for name in glyph_order:
        if name in heights:
            found[name] = int(round(heights[name]))
            continue
        source = next((by_code[code] for code in names_of.get(name, ()) if code in by_code), None)
        found[name] = int(round(heights[source])) if source in heights else default
    return found


def glyph_tops(font):
    """{glyph: (y min, y max)} of each glyph's ink, or None for a glyph without ink."""
    from fontTools.pens.boundsPen import BoundsPen
    glyph_set = font.getGlyphSet()
    found = {}
    for name in font.getGlyphOrder():
        pen = BoundsPen(glyph_set)
        try:
            glyph_set[name].draw(pen)
        except Exception:
            pen.bounds = None
        found[name] = (pen.bounds[1], pen.bounds[3]) if pen.bounds else None
    return found


def vertical_metrics(glyph_order, heights, inks, origin):
    """{glyph: (advance height, top sidebearing)}: the sidebearing from the vertical origin to the ink's
    top (0 for a glyph without ink)."""
    found = {}
    for name in glyph_order:
        ink = inks.get(name)
        found[name] = (heights[name], int(round(origin - ink[1])) if ink else 0)
    return found


def add_tables(font, values):
    """vhea and vmtx (and VORG for a CFF font) added to a fontTools TTFont from the values; the metrics, as
    {glyph: (advance height, top sidebearing)}."""
    from fontTools.ttLib import newTable
    glyph_order = font.getGlyphOrder()
    origin = float(values["origin"])
    heights = heights_by_glyph(glyph_order, font.getBestCmap() or {}, values)
    inks = glyph_tops(font)
    metrics = vertical_metrics(glyph_order, heights, inks, origin)
    vmtx = newTable("vmtx")
    vmtx.metrics = dict(metrics)
    font["vmtx"] = vmtx
    vhea = newTable("vhea")
    vhea.tableVersion = 0x00011000
    vhea.ascent = int(round(values["vhea"]["ascent"]))
    vhea.descent = int(round(values["vhea"]["descent"]))
    vhea.lineGap = int(round(values["vhea"].get("lineGap", 0)))
    vhea.advanceHeightMax = max(height for height, _ in metrics.values())
    inked = [(name, metrics[name], inks[name]) for name in glyph_order if inks.get(name)]
    vhea.minTopSideBearing = min([tsb for _, (_, tsb), _ in inked] or [0])
    vhea.minBottomSideBearing = min([height - tsb - int(round(ink[1] - ink[0])) for _, (height, tsb), ink in inked] or [0])
    vhea.yMaxExtent = max([tsb + int(round(ink[1] - ink[0])) for _, (_, tsb), ink in inked] or [0])
    vhea.caretSlopeRise, vhea.caretSlopeRun, vhea.caretOffset = 0, 1, 0
    vhea.reserved1 = vhea.reserved2 = vhea.reserved3 = vhea.reserved4 = 0
    vhea.metricDataFormat = 0
    vhea.numberOfVMetrics = len(glyph_order)  # (compiling vmtx sets it to the long metrics it keeps)
    font["vhea"] = vhea
    if "CFF " in font or "CFF2" in font:
        vorg = newTable("VORG")
        vorg.majorVersion, vorg.minorVersion = 1, 0
        vorg.defaultVertOriginY = int(round(origin))
        vorg.VOriginRecords = {}
        vorg.numVertOriginYMetrics = 0
        font["VORG"] = vorg
    return metrics


def check(path, values):
    """What is wrong with the vertical tables of the font at path, as a list (empty when all is well): each
    glyph's advance height and the vertical origin as the values give them, vhea's count of metrics."""
    from fontTools.ttLib import TTFont
    font = TTFont(path)
    problems = []
    for tag in ("vhea", "vmtx"):
        if tag not in font:
            problems.append("no %s table" % tag)
    if problems:
        return problems
    order = font.getGlyphOrder()
    heights = heights_by_glyph(order, font.getBestCmap() or {}, values)
    vmtx = font["vmtx"].metrics
    wrong = [name for name in order if name not in vmtx or vmtx[name][0] != heights[name]]
    if wrong:
        problems.append("%d glyphs with another advance height (%s)" % (len(wrong), ", ".join(wrong[:5])))
    if not 1 <= font["vhea"].numberOfVMetrics <= len(order):
        problems.append("vhea's numberOfVMetrics is %d for %d glyphs" % (font["vhea"].numberOfVMetrics, len(order)))
    if ("CFF " in font or "CFF2" in font):
        if "VORG" not in font:
            problems.append("a CFF font without VORG")
        elif font["VORG"].defaultVertOriginY != int(round(values["origin"])):
            problems.append("VORG's default origin is %d, not %d" % (font["VORG"].defaultVertOriginY, values["origin"]))
    return problems


def shaped_heights(path, text):
    """The y advances HarfBuzz gives the text set vertically (top to bottom) in the font at path, or None
    without uharfbuzz."""
    try:
        import uharfbuzz as hb
    except ImportError:
        return None
    with open(path, "rb") as handle:
        blob = hb.Blob(handle.read())
    font = hb.Font(hb.Face(blob))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    buf.direction = "ttb"
    hb.shape(font, buf, {})
    return [pos.y_advance for pos in buf.glyph_positions]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("font", help="the font FontLab exported (.otf or .ttf)")
    parser.add_argument("--values", help="CJK Vertical's values (default: <font>%s)" % VALUES_SUFFIX)
    parser.add_argument("--out", help="the font to write (default: <name>.vert.<ext> beside it)")
    parser.add_argument("--force", action="store_true", help="replace the output file if it exists")
    args = parser.parse_args(argv)
    from fontTools.ttLib import TTFont
    values_file = args.values or values_path(args.font)
    out = args.out or output_path(args.font)
    if os.path.abspath(out) == os.path.abspath(args.font):
        print("The output would replace the exported font: give another --out.")
        return 2
    if os.path.exists(out) and not args.force:
        print("%s exists: give --force to replace it, or another --out." % out)
        return 2
    values = load_values(values_file)
    font = TTFont(args.font)
    if font["head"].unitsPerEm != int(values.get("upm") or font["head"].unitsPerEm):
        print("The values are for an em of %s units, the font's is %s: export the font again, or write the values "
              "again." % (values.get("upm"), font["head"].unitsPerEm))
        return 2
    metrics = add_tables(font, values)
    font.save(out)
    problems = check(out, values)
    heights = sorted(set(height for height, _ in metrics.values()))
    print("Wrote %s: vhea and vmtx%s for %d glyphs (advance heights %s; vertical origin %s)." % (
        out, " and VORG" if "VORG" in font else "", len(metrics), ", ".join(str(h) for h in heights[:4]) +
        (" ..." if len(heights) > 4 else ""), int(round(float(values["origin"])))))
    sample = values.get("sample") or u"あいう"
    shaped = shaped_heights(out, sample)
    if shaped is not None:
        print("HarfBuzz sets %s vertically with y advances %s." % (sample, shaped))
    for problem in problems:
        print("Problem: %s" % problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
