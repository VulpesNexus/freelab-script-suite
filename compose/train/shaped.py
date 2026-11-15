"""Where a font's marks land as HarfBuzz shapes text with it: all its means at once (anchors, forms it
substitutes, contextual positioning), so what is measured is what a reader sees.

Per font, in shares of the em (across: of the base's ink width, from its left):
- letters: for each letter of a script, where a sample mark of each side lands (above and below, and
  Hebrew's dagesh inside the letter, holam at its top left, shin dot at shin's top right): the mark's
  ink center across, and the gap between the mark's ink and the letter's (for the dagesh, its ink's
  middle as a share of the letter's height);
- reph (Devanagari, Bengali, Gujarati): where the reph (ra and virama before a consonant) lands on a
  few consonants;
- i-matra (Devanagari, Bengali, Gujarati): how far the i-matra the font picks before each consonant
  reaches into it, as a share of the consonant's advance (fonts with several i-matras only);
- ligatures (Arabic): where the font's mark-to-ligature anchors sit on its two-part ligatures, per
  part (the first part, read first, is on the right).

Used by anchors.py. Python 3 with uharfbuzz and fonttools.
"""

import statistics

import freelab_glyph_compose as dia  # (compose/, on the path anchors.py sets)

# A sample mark for each side a script's marks take (above, below, and Hebrew's others: see
# freelab_glyph_compose.MARK_CLASSES)
SAMPLE_MARKS = dia.SAMPLE_MARKS
SIDE_LETTERS = {("hebrew", "topright"): (0x05E9,)}  # a side sampled on these letters only (the shin dot on shin)
# The reph: ra, virama, and the consonants it is sampled on, per script
REPH = {"devanagari": (0x0930, 0x094D, (0x0915, 0x0916, 0x0917, 0x091C, 0x0924, 0x0928, 0x092A, 0x092E, 0x0938, 0x0939)),
        "bengali": (0x09B0, 0x09CD, (0x0995, 0x0996, 0x0997, 0x099C, 0x09A4, 0x09A8, 0x09AA, 0x09AE, 0x09B8, 0x09B9)),
        "gujarati": (0x0AB0, 0x0ACD, (0x0A95, 0x0A96, 0x0A97, 0x0A9C, 0x0AA4, 0x0AA8, 0x0AAA, 0x0AAE, 0x0AB8, 0x0AB9))}
REPH_CONSONANTS = REPH["devanagari"][2]
DEVANAGARI_CONSONANTS = tuple(range(0x0915, 0x093A)) + tuple(range(0x0958, 0x0960))
I_MATRA = 0x093F
# The pre-base i-matra and the consonants it goes before, per script
I_MATRAS = {"devanagari": (I_MATRA, DEVANAGARI_CONSONANTS),
            "bengali": (0x09BF, tuple(range(0x0995, 0x09BA)) + (0x09DC, 0x09DD, 0x09DF)),
            "gujarati": (0x0ABF, tuple(range(0x0A95, 0x0ABA)))}
FATHA, KASRA = 0x064E, 0x0650  # the marks that tell a ligature's top anchors from its bottom ones


class Placed(object):
    """A shaped glyph: its glyph id, pen position, advance, and ink box (font units, y up)."""

    def __init__(self, gid, pen, advance, box):
        self.gid, self.pen, self.advance = gid, pen, advance
        self.left, self.bottom, self.right, self.top = box

    @property
    def width(self):
        return self.right - self.left

    @property
    def center(self):
        return (self.left + self.right) / 2.0


class Shaper(object):
    def __init__(self, path):
        import uharfbuzz as hb
        self.hb = hb
        blob = hb.Blob.from_file_path(path)
        self.face = hb.Face(blob)
        self.font = hb.Font(self.face)
        self.upem = float(self.face.upem)

    def nominal(self, code):
        try:
            return self.font.get_nominal_glyph(code)
        except Exception:
            return None

    def shape(self, text):
        """[Placed] in visual order (left to right), or None if a glyph has no ink."""
        hb = self.hb
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {})
        placed, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            extents = self.font.get_glyph_extents(info.codepoint)
            if extents is None or extents.width == 0 or extents.height == 0:
                return None
            left = x + pos.x_offset + extents.x_bearing
            top = pos.y_offset + extents.y_bearing
            placed.append(Placed(info.codepoint, x, pos.x_advance, (left, top + extents.height, left + extents.width, top)))
            x += pos.x_advance
        return placed


def base_and_mark(placed, base_gid):
    """(base, mark) of two shaped glyphs: the base by its glyph id, else the one that advances."""
    if placed is None or len(placed) != 2:
        return None
    first, second = placed
    if first.gid == base_gid and second.gid != base_gid:
        return first, second
    if second.gid == base_gid and first.gid != base_gid:
        return second, first
    if (first.advance > 0) != (second.advance > 0):
        return (first, second) if first.advance > 0 else (second, first)
    return None


def letter_placements(shaper, cmap, script, codes):
    """{(side, code): (share across, gap)}: a sample mark's ink on each letter (composed into one
    glyph, as Latin's often are, says nothing and is left out); for the center (Hebrew's dagesh),
    (share across, the middle of the mark's ink as a share of the letter's height)."""
    found = {}
    for side, mark in sorted(SAMPLE_MARKS.get(script, {}).items()):
        if mark not in cmap:
            continue
        only = SIDE_LETTERS.get((script, side))
        for code in codes:
            if only and code not in only:
                continue
            pair = base_and_mark(shaper.shape(chr(code) + chr(mark)), shaper.nominal(code))
            if pair is None:
                continue
            base, mark_glyph = pair
            if base.width <= 0 or base.top <= base.bottom:
                continue
            share = (mark_glyph.center - base.left) / base.width
            if side == "center":
                found[(side, code)] = (share, ((mark_glyph.bottom + mark_glyph.top) / 2.0 - base.bottom) / (base.top - base.bottom))
                continue
            gap = (mark_glyph.bottom - base.top) if side.startswith("top") else (base.bottom - mark_glyph.top)
            found[(side, code)] = (share, gap / shaper.upem)
    return found


def reph_placement(shaper, cmap, script="devanagari"):
    """(share across, gap) of the reph's ink on a few consonants (medians), or None."""
    if script not in REPH:
        return None
    ra, virama, consonants = REPH[script]
    if ra not in cmap or virama not in cmap:
        return None
    shares, gaps = [], []
    for code in consonants:
        if code not in cmap:
            continue
        pair = base_and_mark(shaper.shape(chr(ra) + chr(virama) + chr(code)), shaper.nominal(code))
        if pair is None:
            continue
        base, reph = pair
        if base.width <= 0 or reph.advance > 0:
            continue  # a reph that advances is no mark: drawn in line, not attached
        shares.append((reph.center - base.left) / base.width)
        gaps.append((reph.bottom - base.top) / shaper.upem)
    if len(shares) < 3:
        return None
    return statistics.median(shares), statistics.median(gaps)


def i_matra_reach(shaper, cmap, script="devanagari", nominal=None):
    """{consonant: reach}: how far the i-matra picked before it reaches into it (its ink's right edge past
    the consonant's pen position), as a share of the consonant's advance; {} for a font with one
    i-matra for all. nominal, a dict: filled with {consonant: whether the pick is the font's nominal
    i-matra}."""
    if script not in I_MATRAS:
        return {}
    sign, consonants = I_MATRAS[script]
    if sign not in cmap:
        return {}
    found, picked = {}, set()
    for code in consonants:
        if code not in cmap:
            continue
        placed = shaper.shape(chr(code) + chr(sign))
        if placed is None or len(placed) != 2:
            continue
        matra, consonant = placed  # the i-matra is drawn first, left of its consonant
        if consonant.gid != shaper.nominal(code) or consonant.advance <= 0:
            continue
        picked.add(matra.gid)
        found[code] = (matra.right - consonant.pen) / float(consonant.advance)
        if nominal is not None:
            nominal[code] = matra.gid == shaper.nominal(sign)
    if len(picked) < 2:
        if nominal is not None:
            nominal.clear()
        return {}
    return found


def ligature_anchors(font):
    """{(side, part): [(share across, gap)]} of a fontTools TTFont's mark-to-ligature anchors on its
    two-part ligatures: top anchors (the class fatha attaches by) and bottom ones (kasra's)."""
    from fontTools.pens.boundsPen import BoundsPen
    if "GPOS" not in font:
        return {}
    cmap = font["cmap"].getBestCmap() or {}
    fatha, kasra = cmap.get(FATHA), cmap.get(KASRA)
    if fatha is None and kasra is None:
        return {}
    upm = float(font["head"].unitsPerEm)
    glyph_set = font.getGlyphSet()
    found = {}
    gpos = font["GPOS"].table
    for lookup in gpos.LookupList.Lookup:
        for sub in lookup.SubTable:
            kind = lookup.LookupType
            if kind == 9:
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if kind != 5:
                continue
            marks = list(sub.MarkCoverage.glyphs)
            sides = {}
            for glyph, side in ((fatha, "top"), (kasra, "bottom")):
                if glyph in marks:
                    sides[sub.MarkArray.MarkRecord[marks.index(glyph)].Class] = side
            if not sides:
                continue
            for lig, attach in zip(sub.LigatureCoverage.glyphs, sub.LigatureArray.LigatureAttach):
                if attach.ComponentCount != 2:
                    continue
                pen = BoundsPen(glyph_set)
                try:
                    glyph_set[lig].draw(pen)
                except Exception:
                    continue
                if not pen.bounds:
                    continue
                left, bottom, right, top = pen.bounds
                if right - left <= 0:
                    continue
                for part, component in enumerate(attach.ComponentRecord):
                    for cls, side in sides.items():
                        anchor = component.LigatureAnchor[cls] if cls < len(component.LigatureAnchor) else None
                        if anchor is None:
                            continue
                        gap = (anchor.YCoordinate - top) if side == "top" else (bottom - anchor.YCoordinate)
                        found.setdefault((side, part), []).append(((anchor.XCoordinate - left) / (right - left), gap / upm))
    return found


def median_pair(values):
    return (statistics.median(v[0] for v in values), statistics.median(v[1] for v in values))
