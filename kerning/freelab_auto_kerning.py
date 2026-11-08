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
METHODS = (("halfkern", "halfkern"), ("contour", "Contour"), ("learned", "FreeLab"), ("fontlab", "FontLab"))  # "learned": FreeLab's own
MEASURED = ("halfkern", "contour", "learned")  # computed here, cached, and scaled to the font's kerning
DEFAULT_FACTORS = {"halfkern": (0.5, 1.0),  # halfkern applies half of a tightening
                   "contour": (1.0, 1.0),
                   "learned": (1.0, 1.0)}
TIGHTEN, LOOSEN = DEFAULT_FACTORS["halfkern"]
FACTOR_RANGE = (0.1, 1.5)  # a factor fitted to the font's kerning stays within this
MODELS_MIN = 3  # fewer existing pairs than this: the method's default factors
TOLERANCE_UNITS = 20  # a suggestion this close to the current value is not listed (about 2% of the em)
SHOW = (("all", "Everything"), ("letters", "Letters"), ("punctuation", "Letters and punctuation"), ("figures", "Figures"))
PAIRS = (("all", "All pairs"), ("common", "Common pairs"))
SOURCES = (("average", "Average of halfkern and Contour"), ("halfkern", "halfkern"), ("contour", "Contour"),
           ("learned", "FreeLab"), ("fontlab", "FontLab"))
ORDERS = (("change", "Largest change first"), ("agreement", "Best agreement first"), ("common", "Most common first"),
          ("alphabet", "Alphabetical"))
PREVIEW_SIZE = 64  # pixels per em in the dialog's preview
COMMON_PAIRS_FILE = "common_pairs.txt"  # beside this script
CACHE_VERSION = 1  # raise when the measuring changes in a way the settings below do not show
# The learned method's features: the gap between a pair's facing edges in height bands, from below
# the baseline to above the capitals (shares of the em), besides both methods' readings.
PROFILE_BANDS = 16
BAND_RANGE = (-0.25, 1.0)
GAP_CAP = 0.6  # gaps wider than this share of the em count as this wide
KIND_CODES = {"upper": 0, "lower": 1, "figure": 2, "punctuation": 3}
SPACING_PAIRS = (u"nn", u"oo", u"HH")  # the font's own spacing, as features
LEARNED_MODEL_FILE = "learned_model.json"  # beside this script: trees trained by kerning/train/train.py
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


def method_fingerprint(model=None):
    """What the measuring depends on: a cache made with other settings (or another learned model)
    is not reused."""
    trained = (model or {}).get("info", {})
    return u"%d %d %d %r %r %r %r %r %r %r" % (CACHE_VERSION, KERN_VERSION, EM_PIXELS, HALO_SHARE, PAD_SHARE, CONTOUR_SLOPE,
                                             CONTOUR_FLOOR, MIN_GAP_SHARE, sorted(REFERENCES.items()),
                                             (trained.get("trained"), trained.get("pairs")) if model else None)


def cache_path(font_key, master):
    """The cache file of one font's master: named by a hash, so no path or name is stored in it."""
    import hashlib
    digest = hashlib.sha1((u"%s|%s" % (font_key, master)).encode("utf-8")).hexdigest()[:20]
    return os.path.join(state_dir(), u"kerning-cache", u"%s.json" % digest)


def load_cache(path):
    import io
    import json
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (IOError, OSError, ValueError):
        return None


def save_cache(path, data):
    import io
    import json
    try:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        text = json.dumps(data, sort_keys=True)
        if not isinstance(text, type(u"")):
            text = text.decode("utf-8")
        with io.open(path + u".new", "w", encoding="utf-8") as handle:
            handle.write(text)
        if os.path.exists(path):
            os.remove(path)
        os.rename(path + u".new", path)
    except (IOError, OSError):
        pass  # no cache: the next run measures everything again


def path_signature(path, advance):
    """A glyph's outline and width, hashed: a pair is measured again when either glyph's changes."""
    import hashlib
    digest = hashlib.sha1((u"%.2f;" % advance).encode("ascii"))
    for index in range(path.elementCount()):
        element = path.elementAt(index)
        digest.update((u"%d %.2f %.2f;" % (element.type, element.x, element.y)).encode("ascii"))
    return digest.hexdigest()[:16]


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

    def __init__(self, name, coverage, width, height, stride, origin_x, advance, baseline=None):
        self.name, self.coverage = name, coverage
        self.width, self.height, self.stride = width, height, stride
        self.origin_x, self.advance = origin_x, advance
        self.baseline = baseline  # the baseline's row (every image shares it)
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


def gap_profile(core, left, right, em):
    """The narrowest gap between the pair's facing ink (no kerning) in each height band, as a share
    of the em (at most GAP_CAP), or None in a band where either glyph has no ink."""
    _, raw_right_of_left, _, _ = left.contours(core)
    raw_left_of_right, _, _, _ = right.contours(core)
    offset = base_offset(left, right)
    low, high = BAND_RANGE
    step = (high - low) / PROFILE_BANDS
    gaps = []
    for band in range(PROFILE_BANDS):
        top = left.baseline - int(round((low + (band + 1) * step) * em))
        bottom = left.baseline - int(round((low + band * step) * em))
        narrowest = None
        for row in range(max(0, top), min(left.height, bottom)):
            if raw_right_of_left[row] < -1e8 or raw_left_of_right[row] > 1e8:
                continue
            gap = raw_left_of_right[row] - (raw_right_of_left[row] + offset)
            if narrowest is None or gap < narrowest:
                narrowest = gap
        gaps.append(None if narrowest is None else min(GAP_CAP, narrowest / em))
    return gaps


def closest_gap(core, left, right, em):
    """The narrowest gap between the two glyphs' ink, no kerning, as a share of the em (or None)."""
    _, raw_right_of_left, _, _ = left.contours(core)
    raw_left_of_right, _, _, _ = right.contours(core)
    gap = core.closest(raw_right_of_left, raw_left_of_right, left.height, base_offset(left, right))
    return None if gap > 1e8 else gap / em


def font_spacing(core, glyph_of, em):
    """The font's own spacing: the narrowest gaps of nn, oo, and HH (None for a pair it lacks)."""
    spacing = []
    for pair in SPACING_PAIRS:
        left, right = glyph_of(pair[0]), glyph_of(pair[1])
        spacing.append(closest_gap(core, left, right, em) if left is not None and right is not None else None)
    return spacing


def pair_features(core, left_char, right_char, left, right, em, spacing, halo_pixels, contour_pixels):
    """The learned method's inputs for a pair: both methods' readings, the pair's kinds, the font's
    spacing, the advances, and the gap profile; all in shares of the em, None where unknown."""
    return ([None if halo_pixels is None else halo_pixels / em, None if contour_pixels is None else contour_pixels / em,
             KIND_CODES[category(left_char)], KIND_CODES[category(right_char)]] + list(spacing)
            + [left.advance / em, right.advance / em] + gap_profile(core, left, right, em))


_MODEL = {}


def learned_model(path=None):
    """The learned method's trees (learned_model.json beside this script), or None without them."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), LEARNED_MODEL_FILE)
    if path not in _MODEL:
        import io
        import json
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            _MODEL[path] = data if data.get("format") == 2 else None
        except (IOError, OSError, ValueError):
            _MODEL[path] = None
    return _MODEL[path]


def tree_sum(stage, features):
    """A stage's baseline plus its trees' leaves. A node is [feature, threshold, missing goes left,
    left, right, is leaf, value]; a feature at most the threshold goes left, as in scikit-learn."""
    total = stage["baseline"]
    for tree in stage["trees"]:
        node = tree[0]
        while not node[5]:
            value = features[node[0]]
            left = node[2] if value is None else value <= node[1]
            node = tree[node[3] if left else node[4]]
        total += node[6]
    return total


def predict(model, features):
    """The learned kerning of a pair, as a share of the em: 0 unless the classifier finds the pair
    kerned (its probability at least the model's cut), else the regressor's amount."""
    raw = tree_sum(model["classifier"], features)
    chance = 1.0 / (1.0 + math.exp(-raw)) if raw > -30 else 0.0
    if chance < model["cut"]:
        return 0.0
    return tree_sum(model["regressor"], features)


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
        self.paths, self.advances, self.signatures = {}, {}, {}
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
        self.signatures[name] = path_signature(path, layer.advanceWidth)
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
        glyph = Glyph(name, coverage, width, height, stride, origin_x, advance, baseline)
        self.images[name] = glyph
        return glyph


def current_kerning(kerning, left, right):
    """A glyph pair's own entry only: kerning classes are not looked at (see FontKerning)."""
    try:
        value = kerning.get((left, right))
    except Exception:
        return 0
    return round_units(value or 0)


CLASS_SIDES = {"left": ("KernLeft", "KernBothSide"), "right": ("KernRight", "KernBothSide")}


def _text(name):
    return name if not isinstance(name, bytes) else name.decode("utf-8", "replace")


class FontKerning(object):
    """A master's kerning as FontLab applies it, classes included, and where a pair's value goes.

    fgKerning.get((left, right)) reads a pair's own entry and misses class kerning. FontLab's
    getPlainPairsDict() resolves the classes. Writing kerning[(a, b)] takes a name that is also a
    class's as the class (a class may share its first glyph's name: class T holds T, Tcaron...), so
    a pair is written to the most specific entry that applies to it, or else to its classes'
    pair, and only where the names say what they mean.
    """

    def __init__(self, kerning):
        self.kerning = kerning
        self.plain = None
        try:
            self.plain = dict(((_text(left), _text(right)), value)
                              for (left, right), value in kerning.getPlainPairsDict().items())
        except Exception:
            pass
        self.classes, self.members = set(), {}
        self.left_class, self.right_class = {}, {}
        try:
            for name, (members, side) in kerning.groups.items():
                name = _text(name)
                self.classes.add(name)
                self.members[name] = [_text(m) for m in members]
                for member in self.members[name]:
                    if side in CLASS_SIDES["left"]:
                        self.left_class.setdefault(member, name)
                    if side in CLASS_SIDES["right"]:
                        self.right_class.setdefault(member, name)
        except Exception:
            pass
        self.entries = set()  # ((left, is class), (right, is class)) of every explicit pair
        try:
            for pair in kerning.keys():
                self.entries.add(((_text(pair.left.id), str(pair.left.mode) == "groupMode"),
                                  (_text(pair.right.id), str(pair.right.mode) == "groupMode")))
        except Exception:
            pass

    def current(self, left, right):
        if self.plain is None:
            return current_kerning(self.kerning, left, right)
        return round_units(self.plain.get((left, right)) or 0)

    def candidates(self, left, right):
        """The entries that could kern the pair, most specific first: glyphs, then classes."""
        left_class, right_class = self.left_class.get(left), self.right_class.get(right)
        found = [((left, False), (right, False))]
        if right_class:
            found.append(((left, False), (right_class, True)))
        if left_class:
            found.append(((left_class, True), (right, False)))
        if left_class and right_class:
            found.append(((left_class, True), (right_class, True)))
        return found

    def writable(self, entry):
        """A name written means a class exactly when a class has that name."""
        return all((name in self.classes) == is_class for name, is_class in entry)

    def target(self, left, right):
        """(entry, remove when 0) for a pair: the entry that sets its value now, or else its classes'
        pair (or its glyphs' when it has none); None when that entry cannot be named for writing."""
        found = self.candidates(left, right)
        for index, entry in enumerate(found):
            if entry in self.entries:
                below = any(other in self.entries for other in found[index + 1:])
                return (entry, not below) if self.writable(entry) else None
        return (found[-1], True) if self.writable(found[-1]) else None

    def reach(self, entry):
        """How many glyph pairs an entry kerns."""
        size = lambda name, is_class: len(self.members.get(name, ())) if is_class else 1
        return size(*entry[0]) * size(*entry[1])

    @staticmethod
    def describe(entry):
        name = lambda text, is_class: (u"class %s" % text) if is_class else text
        return u"%s \N{MULTIPLICATION SIGN} %s" % (name(*entry[0]), name(*entry[1]))

    def write(self, entry, value, remove):
        key = (entry[0][0], entry[1][0])
        if value or not remove:
            self.kerning[key] = value
            self.entries.add(entry)
        elif entry in self.entries:
            self.kerning.remove(key)  # `del kerning[pair]` removes it but raises in PyCXX
            self.entries.discard(entry)


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
    def __init__(self, suggestions, factors, bands, measured=0, reused=0, cache=None, cache_file=None):
        self.suggestions, self.factors, self.bands = suggestions, factors, bands
        self.measured, self.reused = measured, reused
        self.cache, self.cache_file = cache, cache_file

    def remember_fontlab(self):
        """Keep FontLab's values in the cache too (asked a pair at a time, they are slow)."""
        if self.cache is None or not self.cache_file:
            return
        pairs = self.cache.setdefault("pairs", {})
        for s in self.suggestions:
            if "fontlab" in s.values:
                entry = pairs.get(u"%s %s" % (s.left, s.right))
                if entry is not None:
                    entry[2] = s.values["fontlab"]  # [halfkern, contour, FontLab, learned]
        save_cache(self.cache_file, self.cache)


def make_bands(core, image_of, chars, em, max_bias):
    """Both methods' bands for each kind of pair, from the font's references; image_of(ch) gives the
    Glyph of a character in chars. Shared by Auto Kerning and the learned method's training."""
    tuning = [image_of(ch) for ch in TUNING]
    band = calibrate(core, tuning, em, max_bias=max_bias)
    references = dict((kind, [image_of(ch) for ch in refs if ch in chars]) for kind, refs in REFERENCES.items())
    halo_bands, contour_bands = {}, {}
    for left_kind in references:
        for right_kind in references:
            lefts, rights = references[left_kind], references[right_kind]
            halo_bands[(left_kind, right_kind)] = reference_band(core, lefts, rights, band.bias) or band
            contour_bands[(left_kind, right_kind)] = contour_band(core, lefts, rights) or contour_band(core, tuning, tuning)
    return {"core": core, "halo": halo_bands, "contour": contour_bands, "bias": band.bias}


def measure_pair(tools, left_char, right_char, left, right, em, reach):
    """(halfkern, contour distance) raw kerning of a pair in pixels, either None when out of reach."""
    kinds = pair_kinds(left_char, right_char)
    halo = suggest_pixels(tools["core"], left, right, tools["halo"][kinds])
    contour = suggest_contour_pixels(tools["core"], left, right, tools["contour"][kinds], reach, MIN_GAP_SHARE * em)
    return halo, contour


def font_key(package):
    return package.path or u"unsaved:%s" % package.tfn


def analyze(package, master, characters=None, em=EM_PIXELS, progress=None, core=None, cache_file=None):
    """Suggestions by both methods for every pair of the characters (Latin by default) the font has,
    each method's factors fitted to its existing kerning. Pairs whose glyphs are unchanged since the
    last analysis (the cache of this font's master) are not measured again; every pair is when a
    reference glyph changed. progress(done, total) may return False to stop."""
    glyphs = FontLabGlyphs(package, master, em)
    chars = [(ch, name) for ch, name in font_glyphs(package, characters or latin_characters()) if glyphs.add(name)]
    names = dict(chars)
    for ch in TUNING:
        if ch not in names:
            raise ValueError(u'this font has no \u201c%s\u201d. Auto Kerning needs l, n, and o: their spacing sets the kerning.' % ch)
    reference_names = sorted(set(names[ch] for chars_ in REFERENCES.values() for ch in chars_ if ch in names))
    references_signature = u" ".join(glyphs.signatures[n] for n in reference_names)
    cache_file = cache_file if cache_file is not None else cache_path(font_key(package), master)
    model = learned_model()
    old = load_cache(cache_file) or {}
    valid = old.get("method") == method_fingerprint(model) and old.get("references") == references_signature
    old_signatures = old.get("signatures", {}) if valid else {}
    old_pairs = old.get("pairs", {}) if valid else {}
    measuring = {}  # made only when a pair must be measured

    def tools():
        if not measuring:
            measuring.update(make_bands(core or Core(), lambda ch: glyphs.image(names[ch]), names, em, glyphs.pad))
            if model is not None:
                measuring["spacing"] = font_spacing(measuring["core"], lambda ch: glyphs.image(names[ch]) if ch in names else None, em)
        return measuring

    reach = float(glyphs.pad)
    kerning = FontKerning(package.kerning(master))
    suggestions, total, done, measured, reused = [], len(chars) * len(chars), 0, 0, 0
    pairs = {}
    for left_char, left in chars:
        for right_char, right in chars:
            done += 1
            if progress is not None and done % 200 == 0 and progress(done, total) is False:
                return None
            kinds = pair_kinds(left_char, right_char)
            if kinds is None:
                continue
            key = u"%s %s" % (left, right)
            entry = old_pairs.get(key)
            fresh = (entry is not None and old_signatures.get(left) == glyphs.signatures[left]
                     and old_signatures.get(right) == glyphs.signatures[right])
            if fresh:
                reused += 1
                entry = list(entry) + [None] * (4 - len(entry))
            else:
                t = tools()
                left_glyph, right_glyph = glyphs.image(left), glyphs.image(right)
                halo, contour = measure_pair(t, left_char, right_char, left_glyph, right_glyph, em, reach)
                learned = None
                if model is not None:
                    features = pair_features(t["core"], left_char, right_char, left_glyph, right_glyph, em, t["spacing"],
                                             halo, contour)
                    learned = predict(model, features) * glyphs.upm
                entry = [None if halo is None else halo * glyphs.upm / em,
                         None if contour is None else contour * glyphs.upm / em, None, learned]
                measured += 1
            pairs[key] = entry
            s = Suggestion(left_char, right_char, left, right, kerning.current(left, right))
            for method, units in ((MEASURED[0], entry[0]), (MEASURED[1], entry[1]), (MEASURED[2], entry[3])):
                if units is not None:
                    s.raw[method] = units
            if entry[2] is not None:
                s.values["fontlab"] = entry[2]
            if s.raw:
                suggestions.append(s)
    factors = {}
    for method in MEASURED:
        samples = [(s.raw[method], s.current) for s in suggestions if s.current and method in s.raw]
        factors[method] = fit_factors(samples, DEFAULT_FACTORS[method])
        tighten, loosen = factors[method]
        for s in suggestions:
            if method in s.raw:
                units = s.raw[method]
                s.values[method] = round_units(units * (tighten if units < 0 else loosen))
    cache = {"method": method_fingerprint(model), "references": references_signature,
             "signatures": dict((name, glyphs.signatures[name]) for _, name in chars), "pairs": pairs}
    if cache_file:
        save_cache(cache_file, cache)
    return Analysis(suggestions, factors, (measuring.get("halo"), measuring.get("contour")), measured, reused,
                    cache, cache_file)


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

# The preview's choices, a button each: clicking one picks it for the selected pair alone. Its
# number picks it from the keyboard while the list has the focus.
CHOICES = (("current", "Now"), ("average", "Average"), ("halfkern", "halfkern"), ("contour", "Contour"),
           ("learned", "FreeLab"), ("fontlab", "FontLab"))
LEAVE_ALONE_PROP = "freelabLeaveAlone"  # dark mode leaves the preview's pictures as they are drawn
CHOICE_SHEET = u"QToolButton:checked { border: 2px solid palette(highlight); border-radius: 3px; }"  # the pair's choice, plain to see
PREVIEW_TEXT_WIDTH = 92  # pixels beside a preview's glyphs for its method and value
PICKED_ALPHA = 70  # the tint of a row whose value was picked by hand: the highlight color, this opaque
COLUMN_CHOICES = {1: "current", 2: "halfkern", 3: "contour", 4: "learned", 5: "fontlab"}  # double-clicked cells

HELP = u"""<b>FreeLab Auto Kerning</b><br>
Suggests kerning for the font's Latin pairs and writes only the pairs you check.<br><br>
<b>The list</b>: each method's value beside the font's current one. Check the pairs to write;
pairs the font kerns already start unchecked.<br>
<b>Choosing a value for one pair</b>: click a preview below the list, double-click a value in the
list, or press its number (1 Now, 2 Average, 3 halfkern, 4 Contour, 5 FreeLab, 6 FontLab) while
the list has the focus. A pair picked by hand is tinted; Backspace or Reset gives it the suggested
value again.<br>
<b>Keys in the list</b>: arrows move, Space checks or unchecks the pair, 1 to 6 pick, Backspace resets.<br>
<b>Kerning classes</b>: a pair is written where its value comes from: its own pair, or else its
classes' pair, which kerns every glyph of both classes. The line under the list says which.<br><br>
Click this help's ? button, then any control, for what it does."""


class AutoKerningDialog(object):
    COLUMNS = ("Pair", "Current", "halfkern", "Contour", "FreeLab", "FontLab", "Spread", "Suggested")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.package = self.current_font()
        self.master = self.package.master if self.package is not None else None
        self.analysis, self.suggestions, self.stop, self.selected = None, [], False, None
        self.font_kerning = None
        self.common = common_pairs()
        dialog = self.dialog = QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Kerning")
        dialog.setWhatsThis(HELP)
        dialog.resize(760, 940)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = QtGui.QLabel(self.font_line())
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("List changes of at least"))
        self.tolerance = QtGui.QSpinBox()
        self.tolerance.setRange(1, 200)
        self.tolerance.setValue(TOLERANCE_UNITS)
        self.tolerance.setSuffix(" units")
        self.tolerance.setWhatsThis("A pair is listed when a method would change its kerning by at least this much.")
        row.addWidget(self.tolerance)
        row.addWidget(QtGui.QLabel("Show"))
        self.show_kind = self.combo(SHOW)
        self.show_kind.setWhatsThis("Which characters' pairs are listed.")
        row.addWidget(self.show_kind)
        self.pairs = self.combo(PAIRS)
        self.pairs.setToolTip("Common pairs: frequent in the text of 24 languages and kerned in fonts "
                              "(andre-fuchs/kerning-pairs), worth kerning even in a font kerned in part")
        self.pairs.setWhatsThis("All pairs, or only the pairs frequent in text and usually kerned.")
        if not self.common:
            self.pairs.setEnabled(False)
        row.addWidget(self.pairs)
        row.addStretch(1)
        self.analyze_button = QtGui.QPushButton("Analyze")
        self.analyze_button.setWhatsThis("Measures the font's current master again. Pairs whose glyphs have not "
                                         "changed since the last analysis are not measured again.")
        row.addWidget(self.analyze_button)
        layout.addLayout(row)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Suggested values from"))
        self.source = self.combo(SOURCES)
        self.source.setWhatsThis("The method whose values fill the Suggested column and are written, for every "
                                 "pair not picked by hand. Changing it does not change the list.")
        row.addWidget(self.source)
        self.order = self.combo(ORDERS)
        self.order.setWhatsThis("The order of the list.")
        row.addWidget(self.order)
        # Pairs the font kerns already are the designer's choices (a j tucked under the letter before
        # it, which the methods do not model): hidden unless asked for, and never checked for writing.
        self.include_kerned = QtGui.QCheckBox("Include pairs the font kerns")
        self.include_kerned.setWhatsThis("Also lists the pairs the font kerns already, its kerning classes "
                                          "included. They start unchecked.")
        row.addWidget(self.include_kerned)
        self.only_picked = QtGui.QCheckBox("Only pairs picked by hand")
        self.only_picked.setWhatsThis("Lists only the pairs whose value you picked yourself.")
        self.only_picked.setVisible(False)
        row.addWidget(self.only_picked)
        row.addStretch(1)
        layout.addLayout(row)
        self.table = QtGui.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(QtGui.QFontMetrics(self.table.font).height() + 6)  # PythonQt has no widget.fontMetrics()
        self.table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Stretch)  # the columns share the width
        self.table.setWhatsThis(u"The pairs, each method's value, and the value to write (Suggested). "
                                u"Double-click a value to use it for that pair, or press 1 to 6; Space checks "
                                u"the pair; Backspace gives it the suggested value again.")
        layout.addWidget(self.table, 1)
        note_row = QtGui.QHBoxLayout()
        self.preview_note = QtGui.QLabel("Select a pair to compare the methods; click one to use it for that pair.")
        self.preview_note.setWordWrap(True)
        note_row.addWidget(self.preview_note, 1)
        self.reset_button = QtGui.QPushButton("Reset")
        self.reset_button.setToolTip("Give this pair the suggested value again")
        self.reset_button.setWhatsThis("Gives the selected pair the value of the source chosen above, undoing a pick.")
        self.reset_button.setEnabled(False)
        note_row.addWidget(self.reset_button)
        layout.addLayout(note_row)
        grid = QtGui.QGridLayout()
        self.choice_group = QtGui.QButtonGroup(dialog)
        self.choice_buttons = {}
        for number, (key, label) in enumerate(CHOICES):
            button = QtGui.QToolButton()
            button.setCheckable(True)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)  # its method and value are in its picture
            button.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
            button.setProperty(LEAVE_ALONE_PROP, True)
            button.setStyleSheet(CHOICE_SHEET)
            button.setToolTip(u"%s: click to use it for this pair (key %d in the list)" % (label, number + 1))
            button.setWhatsThis(u"The pair as %s sets it, between two H's. Click to use it for this pair." % label)
            button.setEnabled(False)
            self.choice_group.addButton(button, number)
            self.choice_buttons[key] = button
            grid.addWidget(button, number // 2, number % 2)
        layout.addLayout(grid)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check new pairs")
        self.all_button.setWhatsThis("Checks every listed pair the font does not kern yet.")
        self.none_button = QtGui.QPushButton("Check none")
        self.apply_button = QtGui.QPushButton("Write checked pairs")
        self.apply_button.setWhatsThis("Writes the Suggested value of every checked pair to the current master, "
                                       "where the pair's value comes from: see Kerning classes in the help.")
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
        self.reset_button.connect("clicked()", self.reset)
        self.table.connect("itemSelectionChanged()", self.select)
        self.table.connect("cellDoubleClicked(int,int)", self.double_clicked)
        for widget in (self.show_kind, self.pairs, self.order):
            widget.connect("currentIndexChanged(int)", lambda index: self.refilter())
        self.tolerance.connect("valueChanged(int)", lambda value: self.refilter())
        self.include_kerned.connect("toggled(bool)", lambda on: self.refilter())
        self.only_picked.connect("toggled(bool)", lambda on: self.refilter())
        self.source.connect("currentIndexChanged(int)", lambda index: self.refresh_values())  # the list stays as it is
        self.choice_group.connect("buttonClicked(int)", lambda number: self.choose(CHOICES[number][0]))
        self.keys = self.make_keys()

    def make_keys(self):
        """The list's keys: 1 to 6 pick, Backspace resets, Space checks. Only while the list has the focus."""
        QtCore, QtGui = _qt()
        made = []
        try:
            actions = [(str(number + 1), (lambda key=key: self.choose(key))) for number, (key, _) in enumerate(CHOICES)]
            actions += [("Backspace", self.reset), ("Delete", self.reset), ("Space", self.toggle_check)]
            for sequence, action in actions:
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), self.table)
                shortcut.setContext(QtCore.Qt.WidgetShortcut)
                shortcut.connect("activated()", action)
                made.append(shortcut)  # kept: PythonQt deletes what Python no longer holds
        except Exception:
            pass  # no shortcuts: the buttons and double-clicks still work
        return made

    def current_font(self):
        """FontLab's current font, or None when no font is open (FontLab then hands an empty package)."""
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None  # nothing open: FontLab still hands a placeholder package with one glyph
        except Exception:
            pass
        package = workspace.currentPackage
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def font_line(self):
        if self.package is None:
            return u"No font is open. Open one, then click Analyze."
        return u"%s, master %s. Latin letters, figures, and punctuation." % (self.package.tfn, self.master)

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
        """Analyze the font that is current now (another may have been opened since the dialog was)."""
        package = self.current_font()
        if package is None:
            self.package, self.analysis, self.suggestions = None, None, []
            self.table.setRowCount(0)
            self.status.setText(self.font_line())
            return
        if self.package is None or font_key(package) != font_key(self.package) or package.master != self.master:
            self.analysis, self.suggestions = None, []
            self.table.setRowCount(0)
        self.package, self.master = package, package.master
        self.analyze_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        try:
            result = analyze(self.package, self.master, progress=self.progress)
        except Exception as exc:
            message = u"%s" % exc
            self.status.setText(u"%s\n%s" % (self.font_line(), message[:1].upper() + message[1:]))
            return
        finally:
            self.analyze_button.setEnabled(True)
        if result is None:
            self.status.setText("Stopped.")
            return
        self.analysis = result
        self.font_kerning = FontKerning(self.package.kerning(self.master))
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
        if missing:
            self.analysis.remember_fontlab()

    def picked_count(self):
        return sum(1 for s in self.analysis.suggestions if s.override) if self.analysis is not None else 0

    def update_picked(self):
        """The "picked by hand" filter, shown while a pair is picked (or while it is on)."""
        count = self.picked_count()
        self.only_picked.setText(u"Only pairs picked by hand (%d)" % count)
        self.only_picked.setVisible(bool(count) or self.only_picked.checked)

    def refilter(self):
        """The list: pairs either method would change by the tolerance or more, whatever source writes
        (choosing another source changes only what is written, not the list or its order)."""
        if self.analysis is None:
            return
        tolerance = self.tolerance.value
        include = self.include_kerned.checked
        common_only = PAIRS[self.pairs.currentIndex][0] == "common"
        picked_only = self.only_picked.checked

        def differs(s, key):
            value = s.value(key)
            return value is not None and abs(value - s.current) >= tolerance

        if picked_only:
            listed = [s for s in self.analysis.suggestions if s.override]
        else:
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
        for method in [m for m in MEASURED if any(m in s.raw for s in self.analysis.suggestions)]:
            tighten, loosen = self.analysis.factors[method]
            fitted = (tighten, loosen) != DEFAULT_FACTORS[method]
            summary.append("%s tightens at %.0f%%%s" % (dict(METHODS)[method], tighten * 100,
                                                       " (from the font's kerning)" if fitted else ""))
        analysis = self.analysis
        work = (u"%d pairs: %d measured, %d unchanged since the last analysis" % (len(analysis.suggestions), analysis.measured,
                                                                               analysis.reused)
                if analysis.reused else u"%d pairs measured" % len(analysis.suggestions))
        what = (u"%d listed, picked by hand" % len(listed) if picked_only
                else u"%d listed, where a method changes them by %d units or more" % (len(listed), tolerance))
        self.status.setText(u"%s, master %s. %s; %s.\n%s."
                            % (self.package.tfn, self.master, work, what, "; ".join(summary)))
        self.update_picked()
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
            table.setItem(row, 0, pair)
            for column in range(1, len(self.COLUMNS)):
                item = QtGui.QTableWidgetItem()
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row, column, item)
            self.fill_row(row, s, source)
        self.apply_button.setEnabled(bool(self.suggestions))
        self.select()

    def target_text(self, s):
        """Where the pair's value is written, for its tooltip and the line under the list."""
        if self.font_kerning is None:
            return u""
        target = self.font_kerning.target(s.left, s.right)
        if target is None:
            return u"Not written: its value comes from an entry FontLab's scripting cannot name."
        entry = target[0]
        reach = self.font_kerning.reach(entry)
        if reach > 1:
            return u"Writes to %s, which kerns %d glyph pairs." % (FontKerning.describe(entry), reach)
        return u"Writes to the pair %s alone." % FontKerning.describe(entry)

    def fill_row(self, row, s, source):
        QtCore, QtGui = _qt()
        cells = (s.current, s.values.get("halfkern"), s.values.get("contour"), s.values.get("learned"),
                 s.values.get("fontlab"), s.spread(), s.to_write(source))
        tint = QtGui.QColor(self.dialog.palette.color(QtGui.QPalette.Highlight))
        tint.setAlpha(PICKED_ALPHA)
        for column, value in enumerate(cells, 1):
            self.table.item(row, column).setText(u"\N{EN DASH}" if value is None else str(value))
        suggested = self.table.item(row, len(self.COLUMNS) - 1)
        font = QtGui.QFont(self.table.font)
        font.setBold(bool(s.override))
        suggested.setFont(font)
        suggested.setToolTip(u"Picked by hand: %s. Backspace or Reset gives it the suggested value."
                             % dict(CHOICES)[s.override] if s.override else u"")
        for column in range(len(self.COLUMNS)):
            self.table.item(row, column).setBackground(QtGui.QBrush(tint) if s.override else QtGui.QBrush())
        self.table.item(row, 0).setToolTip(u"%s %s. %s" % (s.left, s.right, self.target_text(s)))

    def refresh_values(self):
        """Another source: only the Suggested column and the preview change."""
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

    def toggle_check(self):
        QtCore, QtGui = _qt()
        if self.selected is None:
            return
        item = self.table.item(self.selected, 0)
        item.setCheckState(QtCore.Qt.Unchecked if item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked)

    def select(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self.suggestions):
            self.selected = None
            self.reset_button.setEnabled(False)
            self.preview_note.setText("Select a pair to compare the methods; click one to use it for that pair.")
            for button in self.choice_buttons.values():
                button.setEnabled(False)
                button.setIcon(_qt()[1].QIcon())
            return
        self.selected = rows[0].row()
        self.show_preview(self.suggestions[self.selected])

    def choose(self, key):
        """The method for the selected pair alone; the dialog's source again clears the choice."""
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        if s.value(key) is None:
            return
        s.override = None if key == self.source_key() else key
        self.fill_row(self.selected, s, self.source_key())
        self.show_preview(s)
        self.update_picked()

    def reset(self):
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        s.override = None
        self.fill_row(self.selected, s, self.source_key())
        self.show_preview(s)
        self.update_picked()

    def double_clicked(self, row, column):
        """A method's value double-clicked: that value for the pair; the Suggested one: reset."""
        if row >= len(self.suggestions):
            return
        self.table.selectRow(row)
        self.selected = row
        if column in COLUMN_CHOICES:
            self.choose(COLUMN_CHOICES[column])
        elif column == len(self.COLUMNS) - 1:
            self.reset()

    def show_preview(self, s):
        """Each choice's button: the pair between two H's as that method sets it, its name and value
        beside it (all in one picture, drawn in the dialog's text color), and the one the pair takes
        checked."""
        QtCore, QtGui = _qt()
        source = self.source_key()
        chosen = s.override or source
        self.reset_button.setEnabled(bool(s.override))
        picked = (u"Picked by hand: %s. " % dict(CHOICES)[s.override]) if s.override else u""
        self.preview_note.setText(u"%sThe pair %s: %s" % (picked, s.left_char + s.right_char, self.target_text(s)[:1].lower() + self.target_text(s)[1:]))
        palette = self.dialog.palette
        text = palette.color(QtGui.QPalette.WindowText)  # (FontLab 7's PythonQt lacks the placeholder text role)
        scale = float(PREVIEW_SIZE) / float(self.package.upm)
        glyphs = [self.package.findName(n) for n in ("H", s.left, s.right, "H")]
        paths = [(glyph.getLayerByName(self.master), layer_path(glyph.getLayerByName(self.master)))
                 for glyph in glyphs if glyph is not None and not glyph.isNull]
        strip = int(sum(layer.advanceWidth for layer, _ in paths) * scale) + PREVIEW_SIZE
        font = QtGui.QFont(self.dialog.font)
        for number, (key, label) in enumerate(CHOICES):
            button, kern = self.choice_buttons[key], s.value(key)
            button.setEnabled(kern is not None)
            button.setChecked(key == chosen)
            pixmap = QtGui.QPixmap(strip + PREVIEW_TEXT_WIDTH, int(PREVIEW_SIZE * 1.35))
            pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter(pixmap)
            try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
                if kern is not None:
                    self.paint_pair(painter, paths, scale, kern, text)
                self.paint_label(painter, font, text, strip, pixmap.height(), label,
                                 u"\N{EN DASH}" if kern is None else str(kern), number + 1)
            finally:
                painter.end()
            button.setIcon(QtGui.QIcon(pixmap))
            button.setIconSize(pixmap.size())

    @staticmethod
    def paint_pair(painter, paths, scale, kern, color):
        QtCore, QtGui = _qt()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        x = float(PREVIEW_SIZE) / 2
        for index, (layer, path) in enumerate(paths):
            painter.save()
            painter.translate(x, PREVIEW_SIZE * 1.05)
            painter.scale(scale, -scale)
            painter.fillPath(path, QtGui.QBrush(color))
            painter.restore()
            x += layer.advanceWidth * scale + (kern * scale if index == 1 else 0)

    @staticmethod
    def paint_label(painter, font, color, left, height, label, value, key):
        """The method's name (bold), its value, and its key, in the picture: a button's own text
        took other colors than the dialog's under some styles."""
        QtCore, QtGui = _qt()
        painter.setPen(color)
        bold = QtGui.QFont(font)
        bold.setBold(True)
        line = QtGui.QFontMetrics(font).height()
        top = (height - 3 * line) // 2
        flags = int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        painter.setFont(bold)
        painter.drawText(QtCore.QRect(left, top, PREVIEW_TEXT_WIDTH, line), flags, label)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(left, top + line, PREVIEW_TEXT_WIDTH, line), flags, value)
        faint = QtGui.QColor(color)
        faint.setAlpha(120)
        painter.setPen(faint)
        painter.drawText(QtCore.QRect(left, top + 2 * line, PREVIEW_TEXT_WIDTH, line), flags, u"key %d" % key)

    def write(self):
        """Each checked pair's value, written where it applies (FontKerning.target). Pairs sharing an
        entry (a class pair) with other checked pairs get the value of the most common of them."""
        QtCore, QtGui = _qt()
        source = self.source_key()
        kerning = FontKerning(self.package.kerning(self.master))
        plans, unnamed = {}, 0
        for row, s in enumerate(self.suggestions):
            if self.table.item(row, 0).checkState() != QtCore.Qt.Checked:
                continue
            value = s.to_write(source)
            if value is None or value == s.current:
                continue
            target = kerning.target(s.left, s.right)
            if target is None:
                unnamed += 1
                continue
            plans.setdefault(target[0], []).append((self.rank(s), s, value, target[1]))
        shared = classes = 0
        written = []
        for entry, wanted in plans.items():
            wanted.sort(key=lambda plan: plan[0])
            _, _, value, remove = wanted[0]
            if len(set(plan[2] for plan in wanted)) > 1:
                shared += len(wanted) - 1
            kerning.write(entry, value, remove)
            if kerning.reach(entry) > 1:
                classes += 1
            written.extend(plan[1] for plan in wanted)
        try:
            self.fontlab.flItems.notifyPackageContentUpdated(self.package.id)
        except Exception:
            pass
        self.font_kerning = FontKerning(self.package.kerning(self.master))
        for s in self.analysis.suggestions:
            s.current = self.font_kerning.current(s.left, s.right)
        for s in written:
            s.override = None
        lines = [u"Wrote %d entries for %d pairs to master %s%s." % (
            len(plans), len(written), self.master,
            u" (%d of them kerning class pairs, which kern their classes' other glyphs too)" % classes if classes else u"")]
        if shared:
            lines.append(u"%d pairs shared an entry with a commoner pair and took its value." % shared)
        if unnamed:
            lines.append(u"%d pairs were not written: their value comes from an entry FontLab's scripting cannot name." % unnamed)
        self.update_picked()
        self.fill_table()
        self.status.setText(u" ".join(lines))


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
