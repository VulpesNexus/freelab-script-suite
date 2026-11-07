#FLM: Auto Kerning
# -*- coding: utf-8 -*-
"""FreeLab auto kerning, from FontLab's Scripts menu.

Suggests kerning for the Latin pairs of the current font's current master, by two methods and
FontLab's own, shows them beside the kerning the font has and how far they agree, and writes only
the pairs you approve.

- halfkern's method (https://github.com/behdad/halfkern, Copyright 2022 Google LLC, Apache License
  2.0): every glyph gets an envelope, a halo around its ink; a pair moves until the overlap of the
  two envelopes falls within a band taken from pairs the designer spaced (ll, nn, oo, and others).
- Contour distance, after Matthew Skala's description of Tsukurimashou's kerning (freetype-devel,
  June 2012): the average inverse cube of the distances between the two glyphs' facing contours,
  their angles limited, held within a band taken from the same pairs.
- FontLab's own autokern (flPackage.autoKern), asked for the listed pairs only.

Both methods are measured by FreeLab's native core (kerning/native/freelab_kern.c). The font's
existing kerning acts as a model: each method's tightenings and loosenings are scaled to match it.

Valid Python 2.7 (FontLab 7) and Python 3. The core below needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys

VERSION = "0.2.0"
KERN_VERSION = 2  # FREELAB_KERN_VERSION in kerning/native/freelab_kern.c
EM_PIXELS = 200  # rendering size, pixels per em (halfkern renders at 100; finer steps here)
HALO_SHARE = 0.1  # the envelope's halo, as a share of the em (halfkern's starting kernel)
PAD_SHARE = 0.3  # room around each glyph image for the halo and the search, as a share of the em
TUNING = (u"l", u"n", u"o")  # spaced right by the designer: the halo and the lowercase band come from them
# Each kind of pair is held to the spacing the designer gave its own kind: references set with each
# other with no kerning (HH, HO, OH, OO for capitals; Hn or Oo across cases). halfkern takes one band
# from lowercase alone, which loosened straight capitals (HH, MN) the designer had spaced as wanted.
REFERENCES = {"upper": (u"H", u"O"), "lower": TUNING, "figure": (u"0", u"8")}
CONTOUR_SLOPE = 0.6  # a contour moves at most this many pixels across per row (its angle limit)
CONTOUR_FLOOR = 1.0  # gaps narrower than this many pixels count as this narrow
MIN_GAP_SHARE = 0.02  # contour distance never tightens a pair's ink closer than this share of the em
METHODS = (("halfkern", "halfkern"), ("contour", "Contour"), ("fontlab", "FontLab"))
DEFAULT_FACTORS = {"halfkern": (0.5, 1.0),  # halfkern applies half of a tightening
                   "contour": (1.0, 1.0)}
TIGHTEN, LOOSEN = DEFAULT_FACTORS["halfkern"]
FACTOR_RANGE = (0.1, 1.5)  # a factor fitted to the font's kerning stays within this
MODELS_MIN = 3  # fewer existing pairs than this: the method's default factors
TOLERANCE_UNITS = 20  # a suggestion this close to the current value is not listed (about 2% of the em)
SHOW = (("all", "Everything"), ("letters", "Letters"), ("punctuation", "Letters and punctuation"), ("figures", "Figures"))
PAIRS = (("all", "All pairs"), ("common", "Common pairs"))
SOURCES = (("average", "Average of halfkern and Contour"), ("halfkern", "halfkern"), ("contour", "Contour"),
           ("fontlab", "FontLab"))
ORDERS = (("change", "Largest change first"), ("agreement", "Best agreement first"), ("common", "Most common first"),
          ("alphabet", "Alphabetical"))
PREVIEW_SIZE = 40  # pixels per em in the dialog's preview
PREVIEW_ROW = 50  # pixels between the preview's lines
COMMON_PAIRS_FILE = "common_pairs.txt"  # beside this script
LETTERS = u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
FIGURES = u"0123456789"
PUNCTUATION = u".,:;!?'\"-()[]{}/&*‘’“”«»–—"


def common_pairs(path=None):
    """{pair: rank} from common_pairs.txt (andre-fuchs/kerning-pairs, MIT): pairs common in text and
    kerned in fonts, most relevant first. Empty when the file is missing."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), COMMON_PAIRS_FILE)
    ranks = {}
    try:
        import io
        with io.open(path, encoding="utf-8") as handle:
            for line in handle:
                pair = line.rstrip(u"\n")
                if len(pair) == 2 and not pair.startswith(u"#") and pair not in ranks:
                    ranks[pair] = len(ranks)
    except (IOError, OSError):
        pass
    return ranks


def state_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser(u"~"), u".local", u"state")
    return os.path.join(base, u"FreeLab")


def kern_library_path():
    return os.environ.get("FREELAB_KERN_DLL") or os.path.join(state_dir(), u"bin", u"freelab_kern-v%d.dll" % KERN_VERSION)


class Core(object):
    """The native measuring core (freelab_kern-v<version>.dll)."""

    def __init__(self, path=None):
        import ctypes
        self.ctypes = ctypes
        path = path or kern_library_path()
        if not os.path.isfile(path):
            raise RuntimeError("the auto kerning library is missing: %s (tools/install-fontlab.ps1 builds it)" % path)
        lib = ctypes.CDLL(path)
        if lib.freelab_kern_version() != KERN_VERSION:
            raise RuntimeError("the auto kerning library is another version")
        p, i, d = ctypes.c_void_p, ctypes.c_int, ctypes.c_double
        lib.freelab_kern_scratch_size.restype = ctypes.c_int64
        lib.freelab_kern_scratch_size.argtypes = [i, i]
        lib.freelab_kern_envelope.argtypes = [p, i, i, i, i, p, p]
        lib.freelab_kern_overlap.restype = d
        lib.freelab_kern_overlap.argtypes = [p, i, p, i, i, i, i]
        lib.freelab_kern_pair.argtypes = [p, i, p, i, i, i, i, d, d, i, ctypes.POINTER(i), ctypes.POINTER(d)]
        lib.freelab_kern_profiles.argtypes = [p, i, i, i, p, p]
        lib.freelab_kern_extend.argtypes = [p, i, d, i]
        lib.freelab_kern_extend.restype = None
        lib.freelab_kern_contour_measure.restype = d
        lib.freelab_kern_contour_measure.argtypes = [p, p, i, d, d]
        lib.freelab_kern_closest.restype = d
        lib.freelab_kern_closest.argtypes = [p, p, i, d]
        lib.freelab_kern_contour_pair.argtypes = [p, p, i, d, d, d, d, d, ctypes.POINTER(d)]
        self.lib = lib
        self._scratch = None

    def envelope(self, glyph, bias):
        ctypes = self.ctypes
        size = self.lib.freelab_kern_scratch_size(glyph.width, glyph.height)
        if self._scratch is None or len(self._scratch) < size:
            self._scratch = (ctypes.c_uint8 * size)()
        out = (ctypes.c_uint8 * (glyph.width * glyph.height))()
        if not self.lib.freelab_kern_envelope(glyph.coverage, glyph.width, glyph.height, glyph.stride, bias, out, self._scratch):
            return None
        return out

    def overlap(self, left, left_env, right, right_env, offset):
        return self.lib.freelab_kern_overlap(left_env, left.width, right_env, right.width, left.height, offset, 0)

    def pair(self, left, left_env, right, right_env, offset, bias, low, high):
        ctypes = self.ctypes
        kern, s = ctypes.c_int(), ctypes.c_double()
        if not self.lib.freelab_kern_pair(left_env, left.width, right_env, right.width, left.height, offset, bias,
                                          low, high, 0, ctypes.byref(kern), ctypes.byref(s)):
            return None
        return kern.value, s.value

    def contours(self, glyph, slope):
        """(raw left, raw right, limited left, limited right) edge profiles, a value per row."""
        ctypes = self.ctypes
        h = glyph.height
        left, right = (ctypes.c_double * h)(), (ctypes.c_double * h)()
        self.lib.freelab_kern_profiles(glyph.coverage, glyph.width, h, glyph.stride, left, right)
        limited_left, limited_right = (ctypes.c_double * h)(*left), (ctypes.c_double * h)(*right)
        self.lib.freelab_kern_extend(limited_left, h, slope, 0)
        self.lib.freelab_kern_extend(limited_right, h, slope, 1)
        return left, right, limited_left, limited_right

    def contour_measure(self, right_of_left, left_of_right, h, offset, floor):
        return self.lib.freelab_kern_contour_measure(right_of_left, left_of_right, h, offset, floor)

    def closest(self, right_of_left, left_of_right, h, offset):
        return self.lib.freelab_kern_closest(right_of_left, left_of_right, h, offset)

    def contour_pair(self, right_of_left, left_of_right, h, offset, reach, floor, low, high):
        kern = self.ctypes.c_double()
        if not self.lib.freelab_kern_contour_pair(right_of_left, left_of_right, h, offset, reach, floor, low, high,
                                                  self.ctypes.byref(kern)):
            return None
        return kern.value


class Glyph(object):
    """One glyph's coverage image: `coverage` holds height rows of `stride` bytes; the glyph's origin
    is at column origin_x, on the same baseline row in every image; advance in whole pixels."""

    def __init__(self, name, coverage, width, height, stride, origin_x, advance):
        self.name, self.coverage = name, coverage
        self.width, self.height, self.stride = width, height, stride
        self.origin_x, self.advance = origin_x, advance
        self._envelopes = {}
        self._contours = None

    def envelope(self, core, bias):
        if bias not in self._envelopes:
            self._envelopes[bias] = core.envelope(self, bias)
        return self._envelopes[bias]

    def contours(self, core):
        if self._contours is None:
            self._contours = core.contours(self, CONTOUR_SLOPE)
        return self._contours


def base_offset(left, right):
    """The left image's column in the right one's pixels, the pair set with no kerning."""
    return right.origin_x - left.advance - left.origin_x


class Band(object):
    def __init__(self, bias, low, high):
        self.bias, self.low, self.high = bias, low, high


def first_bias(em):
    width = round_units(2 * HALO_SHARE * em)
    if width % 2 == 0:
        width += 1
    return width // 2


def calibrate(core, tuning, em, max_bias=None):
    """The halo and the overlap band, from the tuning glyphs set with themselves (ll, nn, oo):
    the halo grows until their overlaps are within a factor of two, as halfkern's does."""
    bias = first_bias(em)
    limit = max_bias or em
    while bias <= limit:
        overlaps = []
        for glyph in tuning:
            env = glyph.envelope(core, bias)
            if env is None:
                raise ValueError("%s has no solid ink to measure from" % glyph.name)
            overlaps.append(core.overlap(glyph, env, glyph, env, base_offset(glyph, glyph)))
        low, high = min(overlaps), max(overlaps)
        if low > high / 2:
            return Band(bias, low, high)
        bias += 1
    raise ValueError("no halo makes ll, nn, and oo agree")


def category(ch):
    if ch in LETTERS:
        return "upper" if ch.isupper() else "lower"
    if ch in FIGURES:
        return "figure"
    return "punctuation"


def reference_band(core, lefts, rights, bias):
    """The halfkern band of the references set with each other with no kerning, or None without them."""
    overlaps = []
    for left in lefts:
        for right in rights:
            left_env, right_env = left.envelope(core, bias), right.envelope(core, bias)
            if left_env is None or right_env is None:
                continue
            overlaps.append(core.overlap(left, left_env, right, right_env, base_offset(left, right)))
    if not overlaps:
        return None
    return Band(bias, min(overlaps), max(overlaps))


def contour_band(core, lefts, rights):
    """The contour-distance band of the references set with each other with no kerning, or None."""
    measures = []
    for left in lefts:
        for right in rights:
            _, _, _, right_of_left = left.contours(core)
            _, _, left_of_right, _ = right.contours(core)
            measures.append(core.contour_measure(right_of_left, left_of_right, left.height, base_offset(left, right),
                                                 CONTOUR_FLOOR))
    if not measures:
        return None
    return Band(None, min(measures), max(measures))


def pair_kinds(left_char, right_char):
    """The kinds whose band the pair follows: punctuation takes its partner's; None for two marks
    of punctuation (no text sets them side by side often enough to kern)."""
    left, right = category(left_char), category(right_char)
    if left == "punctuation" and right == "punctuation":
        return None
    if left == "punctuation":
        left = right
    if right == "punctuation":
        right = left
    return left, right


def suggest_pixels(core, left, right, band):
    """halfkern: the pair's kerning in pixels (negative is tighter; not yet scaled), refined between
    whole steps where the overlap crosses the band, or None when no step within reach does."""
    left_env, right_env = left.envelope(core, band.bias), right.envelope(core, band.bias)
    if left_env is None or right_env is None:
        return None
    offset = base_offset(left, right)
    found = core.pair(left, left_env, right, right_env, offset, band.bias, band.low, band.high)
    if found is None:
        return None
    kern, s = found
    if kern == 0:
        return 0.0
    before = kern + 1 if kern < 0 else kern - 1  # the step before the band was reached
    s_before = core.overlap(left, left_env, right, right_env, offset - before)
    target = band.low if kern < 0 else band.high
    if s == s_before:
        return float(kern)
    share = (target - s_before) / (s - s_before)  # where the overlap crosses the band, between the steps
    share = min(1.0, max(0.0, share))
    return before + (kern - before) * share


def suggest_contour_pixels(core, left, right, band, reach, min_gap):
    """Contour distance: the pair's kerning in pixels, or None when the band is out of reach. A
    tightening stops where the raw contours come within min_gap pixels (unless the pair is set
    closer than that already)."""
    _, raw_right_of_left, _, right_of_left = left.contours(core)
    raw_left_of_right, _, left_of_right, _ = right.contours(core)
    offset = base_offset(left, right)
    kern = core.contour_pair(right_of_left, left_of_right, left.height, offset, reach, CONTOUR_FLOOR, band.low, band.high)
    if kern is None:
        return None
    if kern < 0:
        closest = core.closest(raw_right_of_left, raw_left_of_right, left.height, offset - kern)
        if closest < min_gap:
            kern = min(0.0, kern + (min_gap - closest))
    return kern


def round_units(value):
    """Halves up, the same in Python 2.7 (which rounds them away from zero) and 3 (to even)."""
    return int(math.floor(value + 0.5))


def to_units(pixels, em, upm, tighten=TIGHTEN, loosen=LOOSEN):
    value = pixels * upm / em
    value *= tighten if value < 0 else loosen
    return round_units(value)


def fit_factors(samples, defaults=(TIGHTEN, LOOSEN)):
    """The tightening and loosening factors that best turn raw suggestions (units, unscaled) into
    the designer's kerning, from (raw, designer) pairs; the defaults where too few pairs show one."""
    factors = []
    for sign, default in zip((-1, 1), defaults):
        chosen = [(raw, value) for raw, value in samples if raw * sign > 0 and value * sign > 0]
        if len(chosen) < MODELS_MIN:
            factors.append(default)
            continue
        factor = sum(raw * value for raw, value in chosen) / sum(raw * raw for raw, _ in chosen)
        factors.append(min(FACTOR_RANGE[1], max(FACTOR_RANGE[0], factor)))
    return tuple(factors)


def spread(values):
    """How far the methods' values lie apart (0 with one or none)."""
    known = [v for v in values if v is not None]
    return max(known) - min(known) if len(known) > 1 else 0


def average(values):
    known = [v for v in values if v is not None]
    return round_units(sum(known) / len(known)) if known else None


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def latin_characters():
    return LETTERS + FIGURES + PUNCTUATION


def font_glyphs(package, characters):
    """(character, glyph name) for the characters the font has, in that order."""
    found = []
    for ch in characters:
        glyph = package.findUnicode(ord(ch))
        if glyph is not None and not glyph.isNull:
            found.append((ch, glyph.name))
    return found


def layer_path(layer):
    QtCore, QtGui = _qt()
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)
    for shape in layer.shapes:
        transform = shape.transform
        for contour in shape.contours:
            if contour is None:  # FontLab lists an empty contour as None in some glyphs
                continue
            path.addPath(transform.map(contour.path()))
    return path


class FontLabGlyphs(object):
    """Glyph images of one master, rendered with Qt from FontLab's outlines."""

    def __init__(self, package, master, em=EM_PIXELS):
        import ctypes
        self.ctypes = ctypes
        self.package, self.master, self.em = package, master, em
        self.upm = float(package.upm)
        self.scale = em / self.upm
        self.pad = int(math.ceil(PAD_SHARE * em))
        self.paths, self.advances = {}, {}
        self.top = self.bottom = 0.0
        self.images = {}

    def add(self, name):
        glyph = self.package.findName(name)
        layer = glyph.getLayerByName(self.master) if glyph is not None else None
        if layer is None:
            return False
        path = layer_path(layer)
        if path.isEmpty():
            return False
        rect = path.boundingRect()
        self.paths[name], self.advances[name] = path, layer.advanceWidth
        self.top = max(self.top, rect.bottom())  # font units grow upward: the rect's bottom is the ink's top
        self.bottom = min(self.bottom, rect.top())
        return True

    def image(self, name):
        """The Glyph for name; every image shares one height and baseline (call after every add)."""
        if name in self.images:
            return self.images[name]
        QtCore, QtGui = _qt()
        ctypes = self.ctypes
        path, scale = self.paths[name], self.scale
        rect = path.boundingRect()
        ascent = int(math.ceil(self.top * scale)) + 1
        descent = int(math.ceil(-self.bottom * scale)) + 1
        origin_x = self.pad + int(math.ceil(max(0.0, -rect.left() * scale))) + 1
        width = origin_x + int(math.ceil(max(0.0, rect.right()) * scale)) + 1 + self.pad
        height = ascent + descent + 2 * self.pad
        baseline = self.pad + ascent
        image = QtGui.QImage(width, height, QtGui.QImage.Format_Alpha8)
        image.fill(0)
        painter = QtGui.QPainter(image)
        try:  # ended before anything else can fail: a painter left open on a freed image aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(origin_x, baseline)
            painter.scale(scale, -scale)
            painter.fillPath(path, QtGui.QBrush(QtGui.QColor(0, 0, 0, 255)))
        finally:
            painter.end()
        stride = image.bytesPerLine()
        address = ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))
        coverage = (ctypes.c_uint8 * (stride * height)).from_buffer_copy(ctypes.string_at(address, stride * height))
        advance = round_units(self.advances[name] * scale)
        glyph = Glyph(name, coverage, width, height, stride, origin_x, advance)
        self.images[name] = glyph
        return glyph


def current_kerning(kerning, left, right):
    try:
        value = kerning.get((left, right))
    except Exception:
        return 0
    return round_units(value or 0)


def fontlab_autokern(package, master, left, right):
    """FontLab's own autokern for the pair: flPackage.autoKern returns it (as text or a number)
    without writing it. None when it gives nothing."""
    try:
        value = package.autoKern(package.findName(left), package.findName(right), master)
        return round_units(float(value))
    except Exception:
        return None


class Suggestion(object):
    def __init__(self, left_char, right_char, left, right, current):
        self.left_char, self.right_char = left_char, right_char
        self.left, self.right = left, right
        self.current = current
        self.raw = {}  # method: units before its factors
        self.values = {}  # method: units to write; "fontlab" once asked
        self.override = None  # a method chosen for this pair alone

    def value(self, source):
        if source == "average":
            return average([self.values.get("halfkern"), self.values.get("contour")])
        if source == "current":
            return self.current
        return self.values.get(source)

    def to_write(self, source):
        """The value written: the pair's own choice, or the dialog's source."""
        return self.value(self.override or source)

    def spread(self):
        return spread([self.values.get(method) for method, _ in METHODS])


class Analysis(object):
    def __init__(self, suggestions, factors, bands):
        self.suggestions, self.factors, self.bands = suggestions, factors, bands


def analyze(package, master, characters=None, em=EM_PIXELS, progress=None, core=None):
    """Suggestions by both methods for every pair of the characters (Latin by default) the font has,
    each method's factors fitted to its existing kerning. progress(done, total) may return False to stop."""
    core = core or Core()
    glyphs = FontLabGlyphs(package, master, em)
    chars = [(ch, name) for ch, name in font_glyphs(package, characters or latin_characters()) if glyphs.add(name)]
    names = dict(chars)
    tuning = []
    for ch in TUNING:
        if ch not in names:
            raise ValueError("the font has no %s, which sets the spacing the kerning follows" % ch)
        tuning.append(glyphs.image(names[ch]))
    band = calibrate(core, tuning, em, max_bias=glyphs.pad)
    references = dict((kind, [glyphs.image(names[ch]) for ch in chars_ if ch in names])
                      for kind, chars_ in REFERENCES.items())
    halo_bands, contour_bands = {}, {}
    for left_kind in references:
        for right_kind in references:
            lefts, rights = references[left_kind], references[right_kind]
            halo_bands[(left_kind, right_kind)] = reference_band(core, lefts, rights, band.bias) or band
            contour_bands[(left_kind, right_kind)] = (contour_band(core, lefts, rights)
                                                      or contour_band(core, tuning, tuning))
    reach, min_gap = float(glyphs.pad), MIN_GAP_SHARE * em
    kerning = package.kerning(master)
    suggestions, total, done = [], len(chars) * len(chars), 0
    for left_char, left in chars:
        left_glyph = glyphs.image(left)
        for right_char, right in chars:
            done += 1
            if progress is not None and done % 200 == 0 and progress(done, total) is False:
                return None
            kinds = pair_kinds(left_char, right_char)
            if kinds is None:
                continue
            right_glyph = glyphs.image(right)
            s = Suggestion(left_char, right_char, left, right, current_kerning(kerning, left, right))
            halo = suggest_pixels(core, left_glyph, right_glyph, halo_bands[kinds])
            contour = suggest_contour_pixels(core, left_glyph, right_glyph, contour_bands[kinds], reach, min_gap)
            for method, pixels in (("halfkern", halo), ("contour", contour)):
                if pixels is not None:
                    s.raw[method] = pixels * glyphs.upm / em
            if s.raw:
                suggestions.append(s)
    factors = {}
    for method in ("halfkern", "contour"):
        samples = [(s.raw[method], s.current) for s in suggestions if s.current and method in s.raw]
        factors[method] = fit_factors(samples, DEFAULT_FACTORS[method])
        tighten, loosen = factors[method]
        for s in suggestions:
            if method in s.raw:
                units = s.raw[method]
                s.values[method] = round_units(units * (tighten if units < 0 else loosen))
    return Analysis(suggestions, factors, (halo_bands, contour_bands))


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

OVERRIDES = (("", "Write values from (above)"), ("average", "Average of halfkern and Contour"), ("halfkern", "halfkern"),
             ("contour", "Contour"), ("fontlab", "FontLab"), ("current", "Keep the current kerning"))


class AutoKerningDialog(object):
    COLUMNS = ("Pair", "Current", "halfkern", "Contour", "FontLab", "Spread", "Write")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.package = fontlab.flWorkspace.instance().currentPackage
        if self.package is None or self.package.isNull:
            raise RuntimeError("open a font first")
        self.master = self.package.master
        self.analysis, self.suggestions, self.stop, self.selected = None, [], False, None
        self.common = common_pairs()
        dialog = self.dialog = QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Kerning")
        dialog.resize(680, 820)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = QtGui.QLabel("%s, master %s. Latin letters, figures, and punctuation." % (self.package.tfn, self.master))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("List changes of at least"))
        self.tolerance = QtGui.QSpinBox()
        self.tolerance.setRange(1, 200)
        self.tolerance.setValue(TOLERANCE_UNITS)
        self.tolerance.setSuffix(" units")
        row.addWidget(self.tolerance)
        row.addWidget(QtGui.QLabel("Show"))
        self.show_kind = self.combo(SHOW)
        row.addWidget(self.show_kind)
        self.pairs = self.combo(PAIRS)
        self.pairs.setToolTip("Common pairs: frequent in the text of 24 languages and kerned in fonts "
                              "(andre-fuchs/kerning-pairs), worth kerning even in a font kerned in part")
        if not self.common:
            self.pairs.setEnabled(False)
        row.addWidget(self.pairs)
        row.addStretch(1)
        self.analyze_button = QtGui.QPushButton("Analyze")
        row.addWidget(self.analyze_button)
        layout.addLayout(row)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Write values from"))
        self.source = self.combo(SOURCES)
        row.addWidget(self.source)
        self.order = self.combo(ORDERS)
        row.addWidget(self.order)
        # Pairs the font kerns already are the designer's choices (a j tucked under the letter before
        # it, which the methods do not model): hidden unless asked for, and never checked for writing.
        self.include_kerned = QtGui.QCheckBox("Include pairs the font kerns")
        row.addWidget(self.include_kerned)
        row.addStretch(1)
        layout.addLayout(row)
        self.table = QtGui.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(QtGui.QFontMetrics(self.table.font).height() + 6)  # PythonQt has no widget.fontMetrics()
        self.table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Stretch)  # the columns share the width
        layout.addWidget(self.table, 1)
        preview_row = QtGui.QHBoxLayout()
        self.preview = QtGui.QLabel()
        self.preview.setMinimumHeight(5 * PREVIEW_ROW + 12)
        preview_row.addWidget(self.preview, 1)
        choice = QtGui.QVBoxLayout()
        choice.addWidget(QtGui.QLabel("This pair uses"))
        self.override = self.combo(OVERRIDES)
        self.override.setEnabled(False)
        choice.addWidget(self.override)
        choice.addStretch(1)
        preview_row.addLayout(choice)
        layout.addLayout(preview_row)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check new pairs")
        self.none_button = QtGui.QPushButton("Check none")
        self.apply_button = QtGui.QPushButton("Write checked pairs")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.apply_button.setEnabled(False)
        self.analyze_button.connect("clicked()", self.run)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.apply_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", dialog.close)
        self.table.connect("itemSelectionChanged()", self.select)
        for widget in (self.show_kind, self.pairs, self.order):
            widget.connect("currentIndexChanged(int)", lambda index: self.refilter())
        self.tolerance.connect("valueChanged(int)", lambda value: self.refilter())
        self.include_kerned.connect("toggled(bool)", lambda on: self.refilter())
        self.source.connect("currentIndexChanged(int)", lambda index: self.refresh_values())  # the list stays as it is
        self.override.connect("currentIndexChanged(int)", lambda index: self.choose(index))

    @staticmethod
    def combo(choices):
        QtCore, QtGui = _qt()
        box = QtGui.QComboBox()
        for _, label in choices:
            box.addItem(label)
        return box

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)  # analyzed as it opens, once it is drawn

    def progress(self, done, total, what="Measuring pairs"):
        QtCore, QtGui = _qt()
        self.status.setText("%s: %d of %d" % (what, done, total))
        QtGui.QApplication.processEvents()
        return not self.stop

    def run(self):
        self.analyze_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        try:
            result = analyze(self.package, self.master, progress=self.progress)
        except Exception as exc:
            self.status.setText("Could not analyze: %s" % exc)
            return
        finally:
            self.analyze_button.setEnabled(True)
        if result is None:
            self.status.setText("Stopped.")
            return
        self.analysis = result
        self.refilter()

    def source_key(self):
        return SOURCES[self.source.currentIndex][0]

    def shown(self, suggestion):
        kind = SHOW[self.show_kind.currentIndex][0]
        kinds = (category(suggestion.left_char), category(suggestion.right_char))
        if kind == "letters":
            return all(k in ("upper", "lower") for k in kinds)
        if kind == "punctuation":
            return all(k in ("upper", "lower", "punctuation") for k in kinds)
        if kind == "figures":
            return "figure" in kinds
        return True

    def rank(self, suggestion):
        return self.common.get(suggestion.left_char + suggestion.right_char, len(self.common))

    def ask_fontlab(self, suggestions):
        """FontLab's own value for the pairs not asked yet (a call per pair)."""
        missing = [s for s in suggestions if "fontlab" not in s.values]
        for index, s in enumerate(missing):
            s.values["fontlab"] = fontlab_autokern(self.package, self.master, s.left, s.right)
            if index % 50 == 0:
                self.progress(index, len(missing), "Asking FontLab")

    def refilter(self):
        """The list: pairs either method would change by the tolerance or more, whatever source writes
        (choosing another source changes only what is written, not the list or its order)."""
        if self.analysis is None:
            return
        tolerance = self.tolerance.value
        include = self.include_kerned.checked
        common_only = PAIRS[self.pairs.currentIndex][0] == "common"

        def differs(s, key):
            value = s.value(key)
            return value is not None and abs(value - s.current) >= tolerance

        listed = [s for s in self.analysis.suggestions
                  if self.shown(s) and (include or not s.current)
                  and (not common_only or s.left_char + s.right_char in self.common)
                  and (differs(s, "halfkern") or differs(s, "contour") or differs(s, "average"))]
        self.ask_fontlab(listed)
        order = ORDERS[self.order.currentIndex][0]
        change = lambda s: -abs((s.value("average") or 0) - s.current)
        if order == "agreement":
            listed.sort(key=lambda s: (s.spread(), change(s)))
        elif order == "common":
            listed.sort(key=lambda s: (self.rank(s), change(s)))
        elif order == "alphabet":
            listed.sort(key=lambda s: (s.left_char, s.right_char))
        else:
            listed.sort(key=change)
        self.suggestions = listed
        summary = []
        for method in ("halfkern", "contour"):
            tighten, loosen = self.analysis.factors[method]
            fitted = (tighten, loosen) != DEFAULT_FACTORS[method]
            summary.append("%s tightens at %.0f%%%s" % (dict(METHODS)[method], tighten * 100,
                                                       " (from the font's kerning)" if fitted else ""))
        self.status.setText("%d pairs measured; %d listed, where a method changes them by %d units or more.\n%s."
                            % (len(self.analysis.suggestions), len(listed), tolerance, "; ".join(summary)))
        self.fill_table()

    def fill_table(self):
        QtCore, QtGui = _qt()
        table = self.table
        table.setRowCount(len(self.suggestions))
        source = self.source_key()
        for row, s in enumerate(self.suggestions):
            pair = QtGui.QTableWidgetItem(s.left_char + s.right_char)
            pair.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            pair.setCheckState(QtCore.Qt.Unchecked if s.current else QtCore.Qt.Checked)  # the designer's pairs: opt in
            pair.setToolTip("%s %s" % (s.left, s.right))
            table.setItem(row, 0, pair)
            for column in range(1, len(self.COLUMNS)):
                item = QtGui.QTableWidgetItem()
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row, column, item)
            self.fill_row(row, s, source)
        self.apply_button.setEnabled(bool(self.suggestions))
        self.select()

    def fill_row(self, row, s, source):
        QtCore, QtGui = _qt()
        cells = (s.current, s.values.get("halfkern"), s.values.get("contour"), s.values.get("fontlab"),
                 s.spread(), s.to_write(source))
        for column, value in enumerate(cells, 1):
            text = u"\u2013" if value is None else str(value)
            if column == len(self.COLUMNS) - 1 and s.override:
                text = u"%s (%s)" % (text, dict(OVERRIDES)[s.override].split(" ")[0].lower())  # chosen for this pair
            self.table.item(row, column).setText(text)

    def refresh_values(self):
        """Another source: only the Write column and the preview change."""
        source = self.source_key()
        for row, s in enumerate(self.suggestions):
            self.fill_row(row, s, source)
        self.select()

    def check_all(self, on):
        """Check every new pair, or uncheck everything; pairs the font kerns are checked one by one."""
        QtCore, QtGui = _qt()
        for row in range(self.table.rowCount):
            checked = on and not self.suggestions[row].current
            self.table.item(row, 0).setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)

    def select(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self.suggestions):
            self.selected = None
            self.preview.clear()
            self.override.setEnabled(False)
            return
        self.selected = rows[0].row()
        s = self.suggestions[self.selected]
        keys = [key for key, _ in OVERRIDES]
        self.override.blockSignals(True)
        self.override.setCurrentIndex(keys.index(s.override or ""))
        self.override.blockSignals(False)
        self.override.setEnabled(True)
        self.show_preview(s)

    def choose(self, index):
        """This pair's own source, from the preview's choice."""
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        s.override = OVERRIDES[index][0] or None
        self.fill_row(self.selected, s, self.source_key())
        self.show_preview(s)

    def show_preview(self, s):
        """The pair between two H's: as set now, by each method, and as it will be written."""
        QtCore, QtGui = _qt()
        source = self.source_key()
        lines = [("Now", s.current), ("halfkern", s.values.get("halfkern")), ("Contour", s.values.get("contour")),
                 ("FontLab", s.values.get("fontlab")), ("Written", s.to_write(source))]
        width, height = max(320, self.preview.width), len(lines) * PREVIEW_ROW + 12
        palette = self.dialog.palette
        text = palette.color(QtGui.QPalette.Text)
        faint = QtGui.QColor(text)
        faint.setAlpha(150)  # PythonQt in FontLab 7 has no QPalette.PlaceholderText (asking for it crashed FontLab)
        scale = float(PREVIEW_SIZE) / float(self.package.upm)
        glyphs = [self.package.findName(n) for n in ("H", s.left, s.right, "H")]
        paths = [(glyph.getLayerByName(self.master), layer_path(glyph.getLayerByName(self.master)))
                 for glyph in glyphs if glyph is not None and not glyph.isNull]
        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(palette.color(QtGui.QPalette.Base))
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            self.paint_preview(painter, lines, paths, scale, text, faint)
        finally:
            painter.end()
        self.preview.setPixmap(pixmap)

    @staticmethod
    def paint_preview(painter, lines, paths, scale, text, faint):
        QtCore, QtGui = _qt()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for line, (label, kern) in enumerate(lines):
            top = 6 + line * PREVIEW_ROW
            painter.setPen(text)
            painter.drawText(8, top + PREVIEW_ROW // 2, label)
            painter.setPen(faint)
            painter.drawText(8, top + PREVIEW_ROW // 2 + 16, u"\u2013" if kern is None else str(kern))
            if kern is None:
                continue
            x = 110.0
            for index, (layer, path) in enumerate(paths):
                painter.save()
                painter.translate(x, top + PREVIEW_SIZE * 0.95)
                painter.scale(scale, -scale)
                painter.fillPath(path, QtGui.QBrush(text))
                painter.restore()
                x += layer.advanceWidth * scale + (kern * scale if index == 1 else 0)

    def write(self):
        QtCore, QtGui = _qt()
        source = self.source_key()
        kerning = self.package.kerning(self.master)
        written = 0
        for row, s in enumerate(self.suggestions):
            if self.table.item(row, 0).checkState() != QtCore.Qt.Checked:
                continue
            value = s.to_write(source)
            if value is None or value == s.current:
                continue
            if value:
                kerning[(s.left, s.right)] = value
            elif kerning.get((s.left, s.right)) is not None:
                kerning.remove((s.left, s.right))  # `del kerning[pair]` removes it but raises in PyCXX
            written += 1
        try:
            self.fontlab.flItems.notifyPackageContentUpdated(self.package.id)
        except Exception:
            pass
        self.status.setText("Wrote %d pairs to master %s." % (written, self.master))


def main():
    held = getattr(sys, "_freelab_auto_kerning", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = AutoKerningDialog()
    except Exception as exc:
        print("FreeLab Auto Kerning: %s" % exc)
        return
    sys._freelab_auto_kerning = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_auto_kerning":
    main()
