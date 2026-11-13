"""Check Feature Code's forms on real fonts, offline: for each open-licensed font given (SIL Open Font
License or Apache License, as kerning/train/dataset.py reads its license), make every form feature
its glyph names call for, as Feature Code would on a font with no features, compile the code into
a copy of the font (its own GSUB taken out) with fontTools' feaLib, and shape test strings with
HarfBuzz: fractions, case, small capitals, localized forms, figures, ordinals, and the stylistic
sets. Each check says what it shaped and what came out.

    python features/train/forms_check.py <font> [<font>...] [--keep <folder>]

Python 3 with fonttools and uharfbuzz. The compiled copies go to a temporary folder (or --keep's)
and are deleted after; the fonts themselves are only read.
"""

import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "kerning", "train"))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_feature_code as fc  # noqa: E402
import dataset  # noqa: E402  (the license check)


class ContourBoxes(object):
    """A pen that keeps each contour's box ((x0, y0, x1, y1), y up)."""

    def __init__(self):
        self.boxes, self.points = [], []

    def _add(self, *points):
        self.points.extend(points)

    def moveTo(self, pt):
        self._close()
        self.points = [pt]

    lineTo = _add

    def curveTo(self, *points):
        self._add(*points)

    def qCurveTo(self, *points):
        self._add(*[p for p in points if p is not None])

    def _close(self):
        if self.points:
            xs, ys = [p[0] for p in self.points], [p[1] for p in self.points]
            self.boxes.append((min(xs), min(ys), max(xs), max(ys)))
        self.points = []

    def closePath(self):
        self._close()

    endPath = closePath

    def addComponent(self, name, transform):
        raise NotImplementedError  # decomposed by the caller


def font_info(font):
    """FontInfo of a compiled font: names, code points, widths, bounds, and the a's and g's contours."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    names = font.getGlyphOrder()
    codes = {}
    for code, name in sorted(font.getBestCmap().items()):
        codes.setdefault(name, []).append(code)
    glyphs = font.getGlyphSet()
    widths = dict((name, font["hmtx"][name][0]) for name in names)
    bounds, contours = {}, {}
    for name in names:
        stem = name.split(".")[0]
        char = None
        if codes.get(stem):
            char = chr(codes[stem][0])
        if not char or (char not in fc.DIGITS and char not in ("a", "g")):
            continue
        pen = BoundsPen(glyphs)
        glyphs[name].draw(pen)
        if pen.bounds:
            bounds[name] = pen.bounds
        if char in ("a", "g"):
            recording = DecomposingRecordingPen(glyphs)
            glyphs[name].draw(recording)
            boxes = ContourBoxes()
            recording.replay(boxes)
            boxes._close()
            contours[name] = boxes.boxes
    return fc.FontInfo(names, codes, widths, bounds, contours)


def feature_file(features, systems):
    text = fc.prefix_text(u"", systems)
    for feature in features:
        if feature.on:
            text += fc.forms_feature_text(feature.tag, None, feature.lines())
    return text


def shaper(path):
    import uharfbuzz as hb
    with open(path, "rb") as handle:
        face = hb.Face(handle.read())
    font = hb.Font(face)

    def shape(text, features=None, language=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        if language:
            buf.language = language
        hb.shape(font, buf, dict((tag, True) for tag in (features or ())))
        return [font.glyph_to_string(info.codepoint) for info in buf.glyph_infos]

    return shape


def checks(info, by_tag):
    """[(what, text, features, language, expected glyphs)] for the forms this font has."""
    found = []
    g = info.glyph_of.get

    def form(name, *suffixes):
        return info.form(name, suffixes) if name else None

    one, two = g(u"1"), g(u"2")
    if "frac" in by_tag and one and two:
        numerator = form(one, *fc.NUMR_SUFFIXES) or fc.superior_of(info, one)
        bar = info.glyph(0x2044) or info.glyph(0x2F)
        found.append(("frac: 1/2", u"1/2", ["frac"], None, [numerator, bar, form(two, *fc.DNOM_SUFFIXES)]))
        found.append(("frac: 12/25", u"12/25", ["frac"], None,
                      [numerator, form(two, *fc.NUMR_SUFFIXES) or fc.superior_of(info, two), bar,
                       form(two, *fc.DNOM_SUFFIXES), form(g(u"5"), *fc.DNOM_SUFFIXES)]))
    if "case" in by_tag:
        paren = form(g(u"("), "case")
        if paren:
            found.append(("case: (H)", u"(H)", ["case"], None, [paren, g(u"H"), form(g(u")"), "case")]))
            found.append(("case, Romanian text: (H)", u"(H)", ["case"], "ro", [paren, g(u"H"), form(g(u")"), "case")]))
        hyphen = form(g(u"-"), "case")
        if hyphen:
            found.append(("case: A-B", u"A-B", ["case"], None, [g(u"A"), hyphen, g(u"B")]))
    if "smcp" in by_tag:
        found.append(("smcp: a", u"a", ["smcp"], None, [form(g(u"a"), "smcp", "sc")]))
    if "c2sc" in by_tag:
        found.append(("c2sc: A", u"A", ["c2sc"], None, [form(g(u"a"), "sc", "smcp", "c2sc") or form(g(u"A"), "c2sc", "sc")]))
    locl = by_tag.get("locl")
    languages = set(rule.data["language"] for rule in locl.rules) if locl else set()
    if "ROM" in languages:
        found.append(("locl ROM: s cedilla", u"\N{LATIN SMALL LETTER S WITH CEDILLA}", [], "ro", [info.glyph(0x219)]))
        found.append(("locl, other language: s cedilla", u"\N{LATIN SMALL LETTER S WITH CEDILLA}", [], "tr",
                      [info.glyph(0x15F)]))
    if "TRK" in languages:
        turkish = [name for name in fc.TURKISH_I_FORMS if name in info.has][0]
        found.append(("locl TRK: i", u"i", [], "tr", [turkish]))
        found.append(("locl AZE: i", u"i", [], "az", [turkish]))
        small = [name for name in fc.TURKISH_SMALL_I if name in info.has]
        if small and "smcp" in by_tag:
            found.append(("locl TRK + smcp: i", u"i", ["smcp"], "tr", [small[0]]))
    if "CAT" in languages:
        cat = "periodcentered.loclCAT" if "periodcentered.loclCAT" in info.has else None
        if cat:
            found.append(("locl CAT: l\N{MIDDLE DOT}l", u"l\N{MIDDLE DOT}l", [], "ca", [g(u"l"), cat, g(u"l")]))
            found.append(("locl, other language: l\N{MIDDLE DOT}l", u"l\N{MIDDLE DOT}l", [], "es",
                          [g(u"l"), g(u"\N{MIDDLE DOT}"), g(u"l")]))
    if "NLD" in languages:
        lig = [rule for rule in locl.rules if rule.data["language"] == "NLD" and rule.data["kind"] == "ligature"
               and rule.glyphs[0] == g(u"\N{LATIN SMALL LETTER I WITH ACUTE}")]
        ctx = [rule for rule in locl.rules if rule.data["language"] == "NLD" and rule.data["kind"] == "context"
               and rule.glyphs[1] == g(u"j")]
        if lig:
            found.append(("locl NLD: \N{LATIN SMALL LETTER I WITH ACUTE}j", u"\N{LATIN SMALL LETTER I WITH ACUTE}j", [],
                          "nl", [lig[0].glyphs[-1]]))
        elif ctx:
            found.append(("locl NLD: \N{LATIN SMALL LETTER I WITH ACUTE}j", u"\N{LATIN SMALL LETTER I WITH ACUTE}j", [],
                          "nl", [g(u"\N{LATIN SMALL LETTER I WITH ACUTE}"), ctx[0].glyphs[-1]]))
    if "BGR" in languages:
        de = g(u"\N{CYRILLIC SMALL LETTER DE}")
        bulgarian = info.form(de, ("loclBGR",)) if de else None
        if bulgarian:
            found.append(("locl BGR: Cyrillic de", u"\N{CYRILLIC SMALL LETTER DE}", [], "bg", [bulgarian]))
            found.append(("locl, Russian: Cyrillic de", u"\N{CYRILLIC SMALL LETTER DE}", [], "ru", [de]))
    for tag in ("ss01", "ss02"):
        feature = by_tag.get(tag)
        if feature:
            rule = feature.rules[0]
            char = info.char_of(rule.glyphs[0])
            if char and info.codes.get(rule.glyphs[0]):
                found.append(("%s: %s" % (tag, char), char, [tag], None, [rule.glyphs[1]]))
    if "tnum" in by_tag and one:
        target = [rule.glyphs[1] for rule in by_tag["tnum"].rules if not rule.warning and rule.glyphs[0] == one]
        if target:
            found.append(("tnum: 1", u"1", ["tnum"], None, target))
    if "onum" in by_tag and one:
        target = [rule.glyphs[1] for rule in by_tag["onum"].rules if rule.glyphs[0] == one]
        if target:
            found.append(("onum: 1", u"1", ["onum"], None, target))
            tab = [rule.glyphs[1] for rule in by_tag.get("tnum", fc.FormFeature("", [], None)).rules
                   if not rule.warning and rule.glyphs[0] == target[0]]
            if tab:
                found.append(("onum + tnum: 1", u"1", ["onum", "tnum"], None, tab))
    if "sups" in by_tag and two:
        found.append(("sups: 2", u"2", ["sups"], None, [fc.superior_of(info, two)]))
    if "sinf" in by_tag and two:
        found.append(("sinf: H2O", u"H2O", ["sinf"], None, [g(u"H"), form(two, *fc.SINF_SUFFIXES) or
                                                         fc.unicode_forms(info, "<sub>").get(two), g(u"O")]))
    if "ordn" in by_tag and one:
        feminine = form(g(u"a"), "ordn") or info.glyph(0xAA)
        found.append(("ordn: 1a", u"1a", ["ordn"], None, [one, feminine]))
        found.append(("ordn: 1.o", u"1.o", ["ordn"], None, [one, g(u"."), form(g(u"o"), "ordn") or info.glyph(0xBA)]))
        found.append(("ordn: a alone", u"a", ["ordn"], None, [g(u"a")]))
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fonts", nargs="+")
    parser.add_argument("--keep", help="a folder to keep the compiled copies in")
    args = parser.parse_args()
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.ttLib import TTFont
    work = args.keep or tempfile.mkdtemp(prefix="freelab-forms-")
    failed = total = 0
    try:
        for path in args.fonts:
            font = TTFont(path)
            license_name = dataset.license_of(font)
            print("== %s (%s)" % (os.path.basename(path), license_name or "not open-licensed: skipped"))
            if not license_name:
                continue
            info = font_info(font)
            features, default = fc.form_features(info, {})
            by_tag = dict((feature.tag, feature) for feature in features)
            locl = by_tag.get("locl")
            systems = fc.language_systems(locl)
            print("default figures: %s (by %s)" % (fc.describe_style(*default[:2]), default[2]))
            print("features: %s" % ", ".join("%s (%d)" % (f.tag, len(f.rules)) for f in features))
            for feature in features:
                if feature.tag in fc.SET_TAGS:
                    print("  %s name suggested: %s" % (feature.tag, feature.name))
            for name in sorted(info.contours):
                story = fc.story(info.char_of(name), info.contours[name])
                if story:
                    print("  %s: %s-story (%d contours)" % (name, story, len(info.contours[name])))
            warnings = [rule for feature in features for rule in feature.rules if rule.warning]
            for rule in warnings:
                print("  warning: %s" % rule.note)
            texts = fc.forms_texts(features, {})
            problems = fc.forms_check(features, texts, systems, info.names)
            if problems:
                print("  parser: %s" % problems)
                failed += 1
            code = feature_file(features, systems)
            if "GSUB" in font:
                del font["GSUB"]
            addOpenTypeFeaturesFromString(font, code)
            out = os.path.join(work, os.path.basename(path))
            font.save(out)
            shape = shaper(out)
            for what, text, tags, language, expected in checks(info, by_tag):
                total += 1
                got = shape(text, tags, language)
                ok = got == expected and None not in expected
                failed += not ok
                print("  %s  %-34s %s%s" % ("ok  " if ok else "FAIL", what, " ".join(got),
                                            "" if ok else "   (expected %s)" % " ".join(str(e) for e in expected)))
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
    print("\n%d checks, %d failed" % (total, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
