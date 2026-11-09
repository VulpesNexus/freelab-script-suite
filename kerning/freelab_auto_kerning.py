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
import re
import time
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


def round_half_even(value):
    """round() as Python 3 does it (halves to even), under Python 2 too: the band edges of
    gap_profile must fall on the rows the training used."""
    floor = math.floor(value)
    if value - floor > 0.5 or (value - floor == 0.5 and floor % 2 == 1):
        floor += 1
    return int(floor)


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
        top = left.baseline - round_half_even(((low + (band + 1) * step) * em))
        bottom = left.baseline - round_half_even(((low + band * step) * em))
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
            features = 4 + len(SPACING_PAIRS) + 2 + PROFILE_BANDS  # pair_features' length
            _MODEL[path] = data if data.get("format") == 2 and len(data.get("features", [])) == features else None
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


KERNING_CHECK_FILE, KERNING_CHECK_MODULE = "freelab_kerning_check.py", "freelab_kerning_check"


def load_sibling(file_name, module_name):
    """A FreeLab script beside this one, loaded as a module without starting it (its main() not run);
    loaded again when its file changed (a reinstall)."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, file_name)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(module_name)
    if held is not None and hasattr(held, "main") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(module_name)
            module.__file__ = path
            sys.modules[module_name] = module
            with open(path, "rb") as handle:  # open() takes a unicode path through the wide Windows API
                source = handle.read()
            exec(compile(source, file_name, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)  # no half-loaded stub left behind
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def open_sibling_script(file_name, module_name):
    """Runs a FreeLab script beside this one (its main()); the error's text, or None."""
    try:
        load_sibling(file_name, module_name).main()
        return None
    except Exception as exc:
        return u"%s" % exc


def _property(widget, name):
    """A Qt property's value (PythonQt gives properties as attributes, some builds as methods)."""
    value = getattr(widget, name)
    return value() if callable(value) else value


def _keep_room_when_hidden(widget):
    """Hides the widget, keeping its room in the layout; False (and the widget shown, disabled) on a Qt
    without retainSizeWhenHidden."""
    QtCore, QtGui = _qt()
    try:
        policy = _property(widget, "sizePolicy")
        policy.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(policy)
        widget.setVisible(False)
        return True
    except Exception:
        widget.setEnabled(False)
        return False


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
        self.classes, self.members, self.class_flags = set(), {}, {}
        self.left_class, self.right_class = {}, {}
        try:
            for name, (members, side) in kerning.groups.items():
                name = _text(name)
                self.classes.add(name)
                self.class_flags[name] = str(side)
                self.members[name] = [_text(m) for m in members]
                for member in self.members[name]:
                    if side in CLASS_SIDES["left"]:
                        self.left_class.setdefault(member, name)
                    if side in CLASS_SIDES["right"]:
                        self.right_class.setdefault(member, name)
        except Exception:
            pass
        self.entries = set()  # ((left, is class), (right, is class)) of every explicit pair
        self.values = {}  # entry: its value
        try:
            for pair, value in kerning.items():
                entry = ((_text(pair.left.id), str(pair.left.mode) == "groupMode"),
                         (_text(pair.right.id), str(pair.right.mode) == "groupMode"))
                self.entries.add(entry)
                self.values[entry] = value
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

    def hidden(self, entry):
        """The glyph names of an entry that a class also bears: written as they are, FontLab would read
        them as the class (see write)."""
        return sorted(set(name for name, is_class in entry if not is_class and name in self.classes))

    def target(self, left, right):
        """(entry, remove when 0) for a pair: the entry that sets its value now, or else its classes'
        pair (or its glyphs' when it has none)."""
        found = self.candidates(left, right)
        for index, entry in enumerate(found):
            if entry in self.entries:
                below = any(other in self.entries for other in found[index + 1:])
                return entry, not below
        return found[-1], True

    def reach(self, entry):
        """How many glyph pairs an entry kerns."""
        return len(self.pairs(entry))

    def pairs(self, entry):
        """The glyph pairs an entry kerns: every member of a class side against every one of the other."""
        side = lambda name, is_class: self.members.get(name, []) if is_class else [name]
        return [(left, right) for left in side(*entry[0]) for right in side(*entry[1])]

    @staticmethod
    def describe(entry):
        name = lambda text, is_class: (u"class %s" % text) if is_class else text
        return u"%s \N{MULTIPLICATION SIGN} %s" % (name(*entry[0]), name(*entry[1]))

    def write(self, entry, value, remove):
        """Set the entry (0 removes it when remove). A glyph that shares a class's name (glyph j and
        class j) is named while that class is renamed out of the way, and the class renamed back:
        renaming a class keeps its pairs (checked in FontLab 7.2: pairs, classes, and the applied
        kerning identical after the round trip)."""
        renamed = []
        try:
            for name in self.hidden(entry):
                spare = name + u"__freelab"
                while spare in self.classes:
                    spare += u"_"
                self.kerning.renameGroup(name, spare)
                renamed.append((name, spare))
            # a side that is the renamed class itself (glyph o against class o) goes by its spare name
            spares = dict(renamed)
            key = tuple(spares.get(name, name) if is_class else name for name, is_class in entry)
            if value or not remove:
                self.kerning[key] = value
                self.entries.add(entry)
            elif entry in self.entries:
                self.kerning.remove(key)  # `del kerning[pair]` removes it but raises in PyCXX
                self.entries.discard(entry)
        finally:
            failed = []
            for name, spare in reversed(renamed):
                try:
                    self.kerning.renameGroup(spare, name)
                except Exception:
                    failed.append(u"%s (now %s)" % (name, spare))
            if failed:
                raise RuntimeError(u"FontLab did not rename these classes back: %s. Rename them in the Classes panel."
                                   % u", ".join(failed))

    def resolving(self, left, right):
        """The entry that sets a glyph pair's value now, or None."""
        for entry in self.candidates(left, right):
            if entry in self.entries:
                return entry
        return None


PROOF_CONTEXTS = (u"H", u"n", u"o")  # each line of a Glyph window proof: the pair between two of these


# The control characters a pair is proofed between, by its script: a straight capital, a straight and
# a round lowercase, as type designers proof (Walter Tracy's method); figures between zeros too.
PROOF_SCRIPTS = (("GREEK", u"\u0397\u03bd\u03bf"), ("CYRILLIC", u"\u041d\u043d\u043e"), ("ARMENIAN", u"\u0540\u0576\u0585"),
                 ("HEBREW", u"\u05d4\u05df\u05e1"), ("ARABIC", u"\u0627\u0646\u0647"), ("DIGIT", u"0Hn"))


def proof_contexts(package, names):
    """The glyph names to proof glyphs between, in the script of the first of them that is encoded
    (H, n, and o for Latin; Greek's Eta, nu, omicron; Cyrillic's En, en, o; zeros for figures): only
    those the font has, else Latin's, else the glyphs themselves."""
    import unicodedata
    controls = u"Hno"
    for name in names:
        glyph = package.findName(name)
        code = glyph.fgGlyph.unicode if glyph is not None else 0
        if code:
            title = unicodedata.name(unichr_(code), u"")
            for word, chars in PROOF_SCRIPTS:
                if word in title.split():
                    controls = chars
                    break
            break
    for chars in (controls, u"Hno"):
        found = []
        for ch in chars:
            glyph = package.findUnicode(ord(ch))
            if glyph is not None and not glyph.isNull and glyph.name not in found:
                found.append(glyph.name)
        if found:
            return found
    return list(names[:1])


def proof_text(left, right, contexts=PROOF_CONTEXTS):
    """FontLab text (glyph names after slashes) for a pair between two of each context glyph, a
    line each: /H/H/T/o/H/H, /n/n/T/o/n/n, ..."""
    lines = [u"/%s/%s/%s/%s/%s/%s" % (c, c, left, right, c, c) for c in contexts]
    return u"/space".join(lines)


GLYPH_TAB_ACTION = "actionOpen_Editor_Window"  # FontLab's Window > New Glyph Tab


def show_in_glyph_window(fontlab, text):
    """Opens a new Glyph tab (FontLab's own New Glyph Tab) and sets its text (FontLab's /glyphname
    syntax), as typing it would; the error's text, or None. requestContent alone sets the text of the
    active Glyph window only, and does nothing without one."""
    QtCore, QtGui = _qt()
    try:
        symbols = fontlab.fgSymbolList(text, True)
    except Exception as exc:
        return u"%s" % exc
    action = None
    main = AutoKerningDialog.main_window()
    if main is not None:
        for candidate in main.findChildren(QtGui.QAction):
            if candidate.objectName == GLYPH_TAB_ACTION:
                action = candidate
                break
    if action is None:
        return u"FontLab's New Glyph Tab command was not found"

    def fill():
        try:
            fontlab.flItems.requestContent(symbols, 0)
        except Exception:
            pass

    try:
        action.trigger()
        QtCore.QTimer.singleShot(150, fill)  # once the new tab is the active Glyph window
        return None
    except Exception as exc:
        return u"%s" % exc


def notify_changed(fontlab, package, title, glyphs=()):
    """FontLab told of a script's changes, as one step of its History, and its windows redrawn.

    The step records the whole font (notifyChangesApplied's third argument: its objects and theirs):
    a step that recorded only the glyphs it changed left the font's list of glyphs out, and undoing a
    later step then put back a list without the glyphs a script had added (and FontLab complained of
    the components it could not find). notifyPackageContentUpdated takes the font's fontgate id
    (fgPackage.id): given flPackage.id, PyCXX cannot pass it as an int. Without it, the Font window
    does not show glyphs a script added. The font is marked modified: a script's writes leave it
    unmarked, and FontLab would close it without asking to save."""
    for glyph in glyphs:
        try:
            glyph.update()
        except Exception:
            pass
    try:
        fontlab.flItems.notifyChangesApplied(title, package, True)
    except Exception:
        pass
    try:
        fontlab.flItems.notifyPackageContentUpdated(package.fgPackage.id)
    except Exception:
        pass
    try:
        package.setFlag(2, True)  # ofChanged
    except Exception:
        pass


def history_state(package):
    """The font's place in FontLab's History (it changes with each step, undo, and redo), or None."""
    try:
        return package.currentHistoryState()
    except Exception:
        return None


# Scripts > FreeLab, in the order a font is usually made, then dark mode, then FreeLab MCP's: FontLab
# lists a folder's scripts by file name and has no separators of its own.
MENU_GROUPS = (("Diacritics", "Auto Spacing", "CJK Spacing", "Auto Kerning", "Kerning Check", "Feature Code"),
               ("Toggle Dark Mode", "Dark Mode Settings"),
               ("Start MCP Listener", "Stop MCP Listener", "Start Listener", "Stop Listener"))  # (FreeLab MCP's, old names too)
MENU_TITLE, SCRIPTS_MENU = "FreeLab", "menuScripts"
MENU_ORDER_PROP = "freelab_menu_order"
MENU_HOOK_VERSION = 2  # the Scripts menu's property holds it: an older hook found there is replaced


def menu_order(texts, groups=MENU_GROUPS):
    """The texts in the groups' order, None between groups; any text no group names goes last."""
    order = []
    known = set(text for group in groups for text in group)
    rest = [text for text in texts if text not in known]
    for group in list(groups) + [tuple(rest)]:
        present = [text for text in group if text in texts]
        if present:
            if order:
                order.append(None)
            order.extend(present)
    return order


def arrange_menu(menu):
    """Puts a FreeLab menu's actions in menu_order, with separators between the groups; nothing
    changes when they are in order already."""
    actions = list(menu.actions())
    current = [None if action.isSeparator() else action.text.replace(u"&", u"") for action in actions]
    by_text = dict((action.text.replace(u"&", u""), action) for action in actions if not action.isSeparator())
    wanted = menu_order([text for text in current if text is not None])
    if current == wanted:
        return False
    for action in actions:
        menu.removeAction(action)
    for text in wanted:
        if text is None:
            menu.addSeparator()
        else:
            menu.addAction(by_text[text])
    return True


def hook_menu_order():
    """Arranges Scripts > FreeLab each time the Scripts menu opens (FontLab builds the submenu anew on
    Refresh Scripts). Called at startup by FreeLab's block of FontLab's startup script, and by each
    FreeLab script as it opens.

    The handler finds arrange_menu in the module loaded last, and holds on to its own: Python 2
    empties a module's globals (to None) once nothing holds the module, and a script loaded again
    (after a reinstall) replaces it in sys.modules. The first hook held nothing, and stopped working
    silently after a reinstall."""
    QtCore, QtGui = _qt()
    main = AutoKerningDialog.main_window()
    if main is None:
        return False
    scripts = None
    for menu in main.findChildren(QtGui.QMenu):
        if menu.objectName == SCRIPTS_MENU:
            scripts = menu
            break
    if scripts is None:
        return False
    try:
        version = int(scripts.property(MENU_ORDER_PROP) or 0)
    except (TypeError, ValueError):
        version = 1  # the first hook set True
    if version >= MENU_HOOK_VERSION:
        return False
    holder = [sys.modules.get(__name__), arrange_menu]

    def shown():
        try:
            latest = sys.modules.get(__name__)
            arrange = getattr(latest, "arrange_menu", None) or holder[1]
            for action in scripts.actions():
                submenu = action.menu()
                if submenu is not None and action.text.replace(u"&", u"") == MENU_TITLE:
                    arrange(submenu)
        except Exception:
            pass  # a signal handler must not raise

    scripts.connect("aboutToShow()", shown)
    scripts.setProperty(MENU_ORDER_PROP, MENU_HOOK_VERSION)
    sys._freelab_menu_order = (shown, holder)  # kept: PythonQt drops a slot no Python object holds
    shown()
    return True


def plain_buttons(dialog):
    """No default button in a FreeLab dialog: Qt frames the default one in a light color dark mode
    leaves light (and Enter in a field would click it)."""
    QtCore, QtGui = _qt()
    try:
        for button in dialog.findChildren(QtGui.QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# What every FreeLab dialog shares: rich status lines, a log, grid lines, button states, the font's
# History watched, and previews whose neighbors can be clicked
# ---------------------------------------------------------------------------

def html(text):
    """Text made safe for a rich-text label."""
    return (u"%s" % text).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


def b(value):
    """A value in bold, in a status line."""
    return u"<b>%s</b>" % html(value)


def i(name):
    """A button's or a setting's name in italics, in a status line."""
    return u"<i>%s</i>" % html(name)


def rich(label):
    """The label shows rich text (bold values, italic names)."""
    QtCore, QtGui = _qt()
    try:
        label.setTextFormat(QtCore.Qt.RichText)
    except Exception:
        pass
    return label


SENTENCE_END = re.compile(u"([.!?]|\N{HORIZONTAL ELLIPSIS})((?:</[bi]>)?)\\s+(?=[A-Z<(\u00c0-\u024f])")


def sentences(text):
    """Rich text with a line per sentence (a status line's sentences each start a line)."""
    return SENTENCE_END.sub(lambda m: m.group(1) + m.group(2) + u"<br>", u"%s" % text).replace(u"\n", u"<br>")


def status_label(text=u"", plain=False):
    """A dialog's top line: rich text (or plain), wrapped, a line per sentence (its setText splits them)."""
    QtCore, QtGui = _qt()

    class StatusLabel(QtGui.QLabel):
        def setText(self, text):
            QtGui.QLabel.setText(self, SENTENCE_END.sub(lambda m: m.group(1) + m.group(2) + u"\n", u"%s" % text)
                                 if plain else sentences(text))

    label = StatusLabel()
    if not plain:
        rich(label)
    label.setWordWrap(True)
    label.setText(text)
    return label


DIALOG_SIZE = 1000  # pixels: each FreeLab window opens this wide and tall, or as near as the screen allows


def size_dialog(dialog):
    """1000 by 1000 pixels, or the most the screen's free area allows."""
    QtCore, QtGui = _qt()
    width = height = DIALOG_SIZE
    try:
        area = QtGui.QApplication.desktop().availableGeometry(dialog)
        width, height = min(width, area.width() - 40), min(height, area.height() - 60)
    except Exception:
        pass
    dialog.resize(width, height)


def room_below(window):
    """Pixels between a window's bottom edge (its frame's) and the bottom of its screen's free area."""
    QtCore, QtGui = _qt()
    try:
        area = QtGui.QApplication.desktop().availableGeometry(window)
        return max(0, area.bottom() - _property(window, "frameGeometry").bottom())
    except Exception:
        return 0


def section_row(item, tree):
    """A list's row heading a section: bold, with room above it."""
    QtCore, QtGui = _qt()
    try:
        bold = QtGui.QFont(tree.font)
        bold.setBold(True)
        item.setFont(0, bold)
        line = QtGui.QFontMetrics(bold).height()
        item.setSizeHint(0, QtCore.QSize(0, int(line * 2.1)))
        item.setTextAlignment(0, int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom))
    except Exception:
        pass
    return item


LOG_LINES = 4  # the log's height, in lines
LOG_KEPT = 200  # entries kept
LOG_COLORS = {"warning": ((224, 160, 40), (150, 95, 0)), "error": ((240, 96, 86), (190, 30, 20)),
              "done": ((120, 200, 120), (30, 120, 40))}  # (on a dark background, on a light one)


LOG_HEIGHT = []  # the log's height as last dragged, kept for the next window (pixels)


class Log(object):
    """A few lines under a dialog's list: what each action did, done in green, warnings in amber,
    errors in red, newest first. The dialog's top line keeps to what the list shows. Its bottom edge
    drags to make it taller (widget: the log and that edge, to put in a layout)."""

    def __init__(self):
        QtCore, QtGui = _qt()
        view = self.view = QtGui.QTextEdit()
        view.setReadOnly(True)
        # Left to the palette: dark mode's mapping of text views left its scroll bar light
        view.setProperty(LEAVE_ALONE_PROP, True)
        self.line = QtGui.QFontMetrics(view.font).lineSpacing()
        view.setFixedHeight(LOG_HEIGHT[0] if LOG_HEIGHT else int(self.line * LOG_LINES + 12))
        view.setWhatsThis(u"What this window did, newest first: done in green, warnings in amber, errors in red. "
                          u"Drag its bottom edge to make it taller: the window's bottom edge moves with it.")
        self.entries = []
        self.widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(self.widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(view)
        grip = self.grip = QtGui.QFrame()
        grip.setFixedHeight(6)
        grip.setCursor(QtCore.Qt.SizeVerCursor)
        grip.setToolTip(u"Drag to make the log and the window taller or shorter")
        box.addWidget(grip)
        log = self

        class Drag(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == 2:  # MouseButtonPress
                        window = log.view.window()
                        log.start = (event.globalPos().y(), _property(log.view, "height"), window,
                                     _property(window, "height"), room_below(window))
                        return True
                    if kind == 5 and getattr(log, "start", None):  # MouseMove, the button held
                        y, height, window, window_height, room = log.start
                        wanted = max(int(log.line * 2 + 12), min(int(log.line * 40), height + event.globalPos().y() - y))
                        # The window's bottom edge moves with the log's, as far as the screen goes (the
                        # list keeps its height); past it, the log takes the list's room.
                        grown = window_height + min(wanted - height, room)
                        if wanted < _property(log.view, "height"):
                            log.view.setFixedHeight(wanted)
                            window.resize(_property(window, "width"), grown)
                        else:
                            window.resize(_property(window, "width"), grown)
                            log.view.setFixedHeight(wanted)
                        del LOG_HEIGHT[:]
                        LOG_HEIGHT.append(wanted)
                        return True
                    if kind == 3:  # MouseButtonRelease
                        log.start = None
                        return True
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.start = None
        self.drag = Drag()
        grip.installEventFilter(self.drag)

    def add(self, text, level="info"):
        """text is rich text already (html(), b(), and i() make its parts)."""
        QtCore, QtGui = _qt()
        try:
            stamp = time.strftime("%H:%M")
            color = LOG_COLORS.get(level)
            if color is not None:
                base = self.view.palette.color(QtGui.QPalette.Base)
                rgb = color[0] if base.lightness() < 128 else color[1]
                text = u'<span style="color:#%02x%02x%02x">%s</span>' % (rgb[0], rgb[1], rgb[2], text)
            self.entries.insert(0, u"%s&nbsp; %s" % (stamp, text))
            del self.entries[LOG_KEPT:]
            self.view.setHtml(u"<br>".join(self.entries))
        except Exception:
            pass

    def clear(self):
        self.entries = []
        self.view.clear()


GRID_SHEETS = {"table": u"QTableView { gridline-color: rgba(128, 128, 128, 128); }",
               "tree": u"QTreeView::item { border-right: 1px solid rgba(128, 128, 128, 128); "
                       u"border-bottom: 1px solid rgba(128, 128, 128, 128); } "
                       u"QTreeView::item:selected { background: palette(highlight); color: palette(highlighted-text); }"}
# (a stylesheet's item rule takes the items' drawing over: without its selected rule, a selected row
# showed no highlight)


def grid_lines(view):
    """Lines between a list's cells: a mid gray at half strength, over either palette."""
    try:
        view.setStyleSheet(GRID_SHEETS["table" if view.inherits("QTableView") else "tree"])
    except Exception:
        pass


def flat_combo(box):
    """A combo box inside a list's cell: no frame of its own."""
    try:
        box.setFrame(False)
    except Exception:
        pass
    return box


def enable(button, on):
    """A button clickable only when it would do something."""
    try:
        if bool(_property(button, "enabled")) != bool(on):
            button.setEnabled(bool(on))
    except Exception:
        pass


def checks_of(items, checked):
    """(any checked, any unchecked) over checkable items: whether Check none and Check all would do
    anything."""
    some_on = some_off = False
    for item in items:
        if checked(item):
            some_on = True
        else:
            some_off = True
        if some_on and some_off:
            break
    return some_on, some_off


HISTORY_POLL_MS = 700  # how often an open dialog looks whether the font's History moved


def history_mark(package):
    return (font_key(package), history_state(package)) if package is not None else None


def watch_history(owner):
    """While owner's dialog is shown, calls owner.history_moved() when the font's place in FontLab's
    History differs from owner.seen_history: an undo, a redo, or an edit made in FontLab meanwhile.
    The owner sets seen_history (history_mark) after its own analysis and writes. Keep the timer."""
    QtCore, QtGui = _qt()
    timer = QtCore.QTimer()
    timer.setInterval(HISTORY_POLL_MS)

    def tick():
        try:
            if not _property(owner.dialog, "visible") or getattr(owner, "busy", False):
                return
            package, seen = getattr(owner, "package", None), getattr(owner, "seen_history", None)
            if package is None or seen is None:
                return
            now = history_mark(package)
            if now != seen:
                owner.seen_history = now
                owner.history_moved()
        except Exception:
            pass  # a timer's handler must not raise

    timer.connect("timeout()", tick)
    timer.start()
    return timer


class ClickRegions(object):
    """Spans of a widget's picture (a label's pixmap, or a button's icon, drawn centered) that can be
    clicked: each (left, right, key) across the picture, in its pixels. A click on one calls
    on_click(key) instead of the widget's own click; the pointer becomes a hand over one."""

    def __init__(self, widget, on_click, tip=u""):
        QtCore, QtGui = _qt()
        self.widget, self.on_click, self.tip = widget, on_click, tip
        self.regions, self.size = [], (0, 0)
        regions = self

        class Filter(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind in (2, 3, 4):  # MouseButtonPress, -Release, -DblClick
                        key = regions.hit(event)
                        if key is not None:
                            if kind == 3:
                                QtCore.QTimer.singleShot(0, lambda: regions.on_click(key))
                            return True  # the widget's own click does not happen
                    elif kind == 5:  # MouseMove
                        over = regions.hit(event) is not None
                        obj.setCursor(QtCore.Qt.PointingHandCursor if over else QtCore.Qt.ArrowCursor)
                        obj.setToolTip(regions.tip if over else (obj.property("freelabTip") or u""))
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.filter = Filter()
        try:
            widget.setMouseTracking(True)
            widget.setProperty("freelabTip", _property(widget, "toolTip"))
            widget.installEventFilter(self.filter)
        except Exception:
            pass

    def set(self, regions, size):
        self.regions, self.size = list(regions), (size.width(), size.height()) if hasattr(size, "width") else size

    def hit(self, event):
        if not self.regions:
            return None
        try:
            pos = event.pos()
            x, y = pos.x(), pos.y()
            rect = _property(self.widget, "rect")
        except Exception:
            return None
        width, height = self.size
        x -= (rect.width() - width) / 2.0
        y -= (rect.height() - height) / 2.0
        if not 0 <= y <= height:
            return None
        for x0, x1, key in self.regions:
            if x0 <= x < x1:
                return key
        return None


# FontLab's flags (its Flag menu: the glyph's mark, a hue plus one; 0 for none), as the lists offer them
FLAG_COLORS = ((u"Red", 1), (u"Green", 121), (u"Cyan", 181), (u"Blue", 241), (u"Magenta", 301), (u"None", 0))


FLAG_TINT = 80  # the alpha of a flagged row's tint: its flag's color, readable under either palette's text
FLAG_ROLE = 0x0100 + 77  # Qt.UserRole + 77: a cell's flag colors (a list's stylesheet item rule hides BackgroundRole)
FLAG_BAR = 3  # pixels: the opaque bar of a flag's color along a flagged cell's bottom, shown over a selected row too


def flag_colors_text(marks):
    """A cell's flag colors as stored in FLAG_ROLE: one per glyph of the row, "#rrggbb" or "" for none,
    joined by commas (a pair's left and right halves); None when no glyph is flagged."""
    if not any(marks):
        return None
    return u",".join(flag_color(m).name() if m else u"" for m in marks)


def flag_segments(text, left, width):
    """[(x, width, "#rrggbb")] of a cell's flagged parts: the cell split evenly among the row's glyphs."""
    names = (text or u"").split(u",")
    found = []
    for k, name in enumerate(names):
        x0 = left + width * k // len(names)
        x1 = left + width * (k + 1) // len(names)
        if name:
            found.append((x0, x1 - x0, name))
    return found


def separator():
    """A thin line between a window's top text and its fields: a mid gray at half strength, as the
    lists' cell lines."""
    QtCore, QtGui = _qt()
    line = QtGui.QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(u"QFrame { border: none; background: rgba(128, 128, 128, 128); }")
    return line


def flag_color(mark, alpha=255):
    """The color FontLab shows for a flag (glyph.mark: a hue plus one)."""
    QtCore, QtGui = _qt()
    color = QtGui.QColor()
    color.setHsv((int(mark) - 1) % 360, 190, 235, alpha)
    return color


def flag_menu(view, owner, names_of_selection, names_of_row=None, column=0):
    """A list's flags: see FlagMenu. Keep what it returns."""
    return FlagMenu(view, owner, names_of_selection, names_of_row, column)


class FlagMenu(object):
    """A right-click menu on a list: the selected row's glyphs flagged in FontLab, as its Flag menu
    does, to find them again later (the Font window shows the flag; Select > Same Flag gathers them),
    and the next or previous flagged row (F3, Shift+F3). With names_of_row (a tree's item, or a
    table's row number, to its glyphs' names), each row whose glyph has a flag shows its color in
    the given column: a tint, and a bar along the bottom that a selected row shows too; a pair's
    cell split in two, each glyph's flag on its own half. Read again whenever the list is filled or
    its items replaced. names_of_selection() gives the selected row's glyphs; owner has package,
    fontlab, log, dialog, and seen_history."""

    def __init__(self, view, owner, names_of_selection, names_of_row=None, column=0):
        QtCore, QtGui = _qt()
        self.view, self.owner, self.column = view, owner, column
        self.names_of_selection, self.names_of_row = names_of_selection, names_of_row
        self.due = False
        self.refreshing = False
        self.cache = {}  # glyph name: its flag, until the list is filled again or a flag is set here
        self.table = view.inherits("QTableWidget")
        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        view.connect("customContextMenuRequested(QPoint)", self.show)
        self.shortcuts = []
        for keys, step in (("F3", 1), ("Shift+F3", -1)):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(keys), view)
            shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
            shortcut.connect("activated()", (lambda step: lambda: self.go(step))(step))
            self.shortcuts.append(shortcut)
        if names_of_row is not None:
            role, bar, tint, segments = FLAG_ROLE, FLAG_BAR, FLAG_TINT, flag_segments

            class Tint(QtGui.QStyledItemDelegate):  # (what it uses held here: a dropped module's globals turn None)
                def paint(self, painter, option, index):
                    parts = []
                    try:
                        rect = option.rect
                        parts = segments(index.data(role), rect.left(), rect.width())
                        for x, width, name in parts:
                            color = QtGui.QColor(name)
                            color.setAlpha(tint)
                            painter.fillRect(QtCore.QRect(x, rect.top(), width, rect.height()), color)
                    except Exception:
                        parts = []
                    QtGui.QStyledItemDelegate.paint(self, painter, option, index)
                    try:  # over the row as drawn: a selected row's highlight covers the tint, not the bar
                        for x, width, name in parts:
                            painter.fillRect(QtCore.QRect(x, rect.bottom() - bar + 1, width, bar), QtGui.QColor(name))
                    except Exception:
                        pass

            self.delegate = Tint(view)
            view.setItemDelegateForColumn(column, self.delegate)
            model = view.model()
            model.connect("rowsInserted(QModelIndex,int,int)", lambda *args: self.soon(True))
            model.connect("modelReset()", lambda: self.soon(True))
            # (a list filled again with as many rows replaces its items: Auto Kerning's order and filters)
            model.connect("dataChanged(QModelIndex,QModelIndex)", lambda *args: self.soon())

    # -- the rows --------------------------------------------------------------------

    def rows(self):
        """[(a tree's item or a table's row, the glyphs' names)], in the list's order."""
        found = []
        if self.names_of_row is None:
            return found
        if self.table:
            for row in range(_property(self.view, "rowCount")):
                found.append((row, self.names_safely(row)))
            return found
        pending = [self.view.topLevelItem(i) for i in range(_property(self.view, "topLevelItemCount"))][::-1]
        while pending:
            item = pending.pop()
            found.append((item, self.names_safely(item)))
            pending.extend(item.child(i) for i in reversed(range(item.childCount())))
        return found

    def names_safely(self, handle):
        try:
            return [n for n in (self.names_of_row(handle) or []) if n]
        except Exception:
            return []

    def marks(self, names, cache):
        package = self.owner.package
        found = []
        for name in names:
            if name not in cache:
                glyph = package.findName(name) if package is not None else None
                try:
                    cache[name] = int(glyph.mark) if glyph is not None and not glyph.isNull else 0
                except Exception:
                    cache[name] = 0
            found.append(cache[name])
        return found

    def soon(self, filled=False):
        QtCore, QtGui = _qt()
        if self.refreshing:
            return  # its own tints
        if filled:
            self.cache = {}  # filled again (an undo, another font): flags read anew
        if not self.due:
            self.due = True
            QtCore.QTimer.singleShot(0, self.refresh)

    def refresh(self):
        """Each row's cell tinted with the flag of its first flagged glyph, or plain."""
        QtCore, QtGui = _qt()
        self.due = False
        if self.names_of_row is None:
            return
        blocked = self.view.signalsBlocked()
        self.view.blockSignals(True)  # a tint is no edit: the dialog's itemChanged must not hear it
        self.refreshing = True
        try:
            for handle, names in self.rows():
                text = flag_colors_text(self.marks(names, self.cache))
                if self.table:
                    item = self.view.item(handle, self.column)
                    if item is not None and item.data(FLAG_ROLE) != text:
                        item.setData(FLAG_ROLE, text)
                elif handle.data(self.column, FLAG_ROLE) != text:
                    handle.setData(self.column, FLAG_ROLE, text)
        except Exception:
            pass  # a list emptied meanwhile
        finally:
            self.refreshing = False
            self.view.blockSignals(blocked)
        self.view.viewport().update()

    def go(self, step):
        """The next (step 1) or previous (-1) row with a flagged glyph selected, around the list's end."""
        rows = [(handle, any(self.marks(names, self.cache))) for handle, names in self.rows()]
        if not any(flagged for _, flagged in rows):
            try:
                self.owner.log.add(u"No row of this list has a flagged glyph.", "warning")
            except Exception:
                pass
            return
        if self.table:
            current = _property(self.view, "currentRow")
            at = current if current >= 0 else -1
        else:
            item = _property(self.view, "currentItem")
            at = next((i for i, (handle, _) in enumerate(rows) if item is not None and handle is item), -1)
        count = len(rows)
        for k in range(1, count + 1):
            i = (at + step * k) % count
            handle, flagged = rows[i]
            if flagged:
                if self.table:
                    self.view.selectRow(handle)
                    self.view.scrollToItem(self.view.item(handle, 0))
                else:
                    self.view.setCurrentItem(handle)
                    self.view.scrollToItem(handle)
                return

    # -- the menu --------------------------------------------------------------------

    def show(self, pos):
        QtCore, QtGui = _qt()
        try:
            owner = self.owner
            names = [n for n in (self.names_of_selection() or []) if n]
            menu = QtGui.QMenu(owner.dialog)
            actions = []
            if names and owner.package is not None:
                title = menu.addAction(u"Flag %s in FontLab" % u" and ".join(names))
                title.setEnabled(False)
                for label, value in FLAG_COLORS:
                    action = menu.addAction(label)
                    if value:
                        pixmap = QtGui.QPixmap(12, 12)
                        pixmap.fill(flag_color(value))
                        action.setIcon(QtGui.QIcon(pixmap))
                    actions.append((action, label, value))
                menu.addSeparator()
            following = menu.addAction(u"Next flagged row\tF3")
            previous = menu.addAction(u"Previous flagged row\tShift+F3")
            view = self.view
            where = view.viewport().mapToGlobal(pos) if hasattr(view, "viewport") else view.mapToGlobal(pos)
            picked = menu.exec_(where)
            if picked is None:
                return
            if picked.text == following.text:
                self.go(1)
                return
            if picked.text == previous.text:
                self.go(-1)
                return
            for action, label, value in actions:
                if action.text == picked.text:
                    flag_glyphs(owner, names, label, value)
                    break
        except Exception as exc:
            try:
                self.owner.log.add(u"Flagging did not work: %s" % html(exc), "error")
            except Exception:
                pass


def flag_glyphs(owner, names, label, value):
    """The glyphs flagged (or unflagged) in FontLab, as one step of its History; the owner's lists'
    tints read again."""
    package = owner.package
    glyphs = []
    for name in names:
        glyph = package.findName(name)
        if glyph is not None and not glyph.isNull:
            glyph.mark = value
            glyphs.append(glyph)
    if not glyphs:
        return
    notify_changed(owner.fontlab, package, u"FreeLab flag", glyphs)
    owner.seen_history = history_mark(package)  # its own step: nothing to read again
    menus = getattr(owner, "flagging", None)
    for menu in (menus if isinstance(menus, list) else [menus]):
        if isinstance(menu, FlagMenu):
            menu.cache = {}
            menu.refresh()
    if value:
        owner.log.add(u"Flagged %s %s in FontLab (Select &gt; Same Flag gathers them again; F3 goes to the next "
                      u"flagged row here)." % (b(u", ".join(g.name for g in glyphs)), html(label.lower())), "done")
    else:
        owner.log.add(u"Took the flag off %s." % b(u", ".join(g.name for g in glyphs)), "done")


def open_auto_kerning_at(left, right):
    """Auto Kerning, opened (or brought forward) on the pair of the glyphs named left and right; the
    error's text, or None."""
    held = getattr(sys, "_freelab_auto_kerning", None)
    try:
        if held is None or not _property(held.dialog, "visible"):
            main(focus=(left, right))
        else:
            held.dialog.raise_()
            held.dialog.activateWindow()
            held.focus_pair(left, right)
        return None
    except Exception as exc:
        return u"%s" % exc


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
        self.checked = None  # the user's check in the list; None until the list shows it

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
    references_signature = u" ".join(glyphs.signatures[n] for n in reference_names) + u" upm %s" % glyphs.upm
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
# Suggested kerning classes
# ---------------------------------------------------------------------------

CLASS_MODEL_FILE = "class_model.json"  # beside this script: kerning/train/classes.py counts it from the corpus
MERGE_RATE = 0.5  # two base letters may share a class when at least this share of the corpus's families class them so
CLASS_SIDES_LABELS = {"first": "First in a pair (the glyph's right side)", "second": "Second in a pair (the glyph's left side)"}
CLASS_FLAGS = {"first": "KernLeft", "second": "KernRight"}  # FontLab's flags: KernLeft classes come first in pairs
CLASS_PREFIX = {"first": "kern1_", "second": "kern2_"}
CLASS_COLUMNS = ("Class", "Glyphs", "Outcome", "May need pairs of their own")
CLASS_EXCEPTIONS_LABEL = "Pairs too close with their class's value (each given a value of its own when written)"
EXCEPTION_ROLE_BASE = 100000  # a row's data at or above this: a pair too close (its index above it), not a class

_CLASS_MODEL = {}


def class_model(path=None):
    """{side: {(a, b): share of families classing them together}} from class_model.json, or None."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), CLASS_MODEL_FILE)
    if path not in _CLASS_MODEL:
        import io
        import json
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            model = None
            if data.get("format") == 1:
                model = {}
                for side, rows in data["sides"].items():
                    rates = model[side] = {}
                    for pair, together, apart in rows:
                        if together + apart <= 0:
                            continue
                        rates[(pair[0], pair[1])] = rates[(pair[1], pair[0])] = together / float(together + apart)
            _CLASS_MODEL[path] = model
        except (IOError, OSError, ValueError, KeyError, TypeError):
            _CLASS_MODEL[path] = None
    return _CLASS_MODEL[path]


def class_characters():
    """The characters classes are suggested for: Latin letters to Latin Extended-B, figures, punctuation."""
    import unicodedata
    letters = [unichr_(code) for code in range(0x41, 0x250) if unicodedata.category(unichr_(code)).startswith("L")]
    return letters + [ch for ch in FIGURES + PUNCTUATION]


def unichr_(code):
    """A code point's character; the replacement character past U+FFFF on a narrow Python 2 (FontLab
    7's), which has none of them as one character."""
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def base_letter(ch):
    """The letter a character is built on (A for À, L for Ŀ), or the character itself."""
    import unicodedata
    decomposed = unicodedata.normalize("NFKD", ch)
    return decomposed[0] if decomposed and decomposed[0].isalpha() and ch.isalpha() else ch


SIGNATURE_PARTNERS = {"first": u"HOonvTAy.", "second": u"HOonvTLrf"}  # what a side is kerned against, as seen beside it
SIGNATURE_TOLERANCE = 0.02  # two sides kern alike when every partner's kerning differs by at most this share of the em
SIGNATURE_MIN = 3  # partners both sides need, measured, to be compared
DIFFERS_NOTE = 0.03  # a member kerning this much differently from its class's first glyph is named (an exception may be due)


def kind_character(ch):
    """The character whose kind (capital, lowercase, figure) sets a pair's references: its base letter."""
    base = base_letter(ch)
    if base in LETTERS + FIGURES:
        return base
    if ch.isalpha():  # a letter of its own (o with stroke, dotless i): its case's references
        return u"H" if ch.isupper() else u"n"
    return ch


def side_signature(tools, image_of, names, ch, side, em, reach):
    """How a side kerns: for each partner of SIGNATURE_PARTNERS the font has, the average of halfkern's
    and contour distance's raw kerning of the pair (the side facing the partner), as a share of the em;
    None where neither measures it."""
    found = []
    for partner in SIGNATURE_PARTNERS[side]:
        if partner not in names:
            found.append(None)
            continue
        left, right = (ch, partner) if side == "first" else (partner, ch)
        if pair_kinds(kind_character(left), kind_character(right)) is None:
            found.append(None)
            continue
        halo, contour = measure_pair(tools, kind_character(left), kind_character(right), image_of(left), image_of(right),
                                     em, reach)
        values = [v for v in (halo, contour) if v is not None]
        found.append(sum(values) / len(values) / float(em) if values else None)
    return found


def signature_gap(one, other):
    """The largest difference between two signatures' measured partners, or None with too few."""
    both = [abs(a - b) for a, b in zip(one or [], other or []) if a is not None and b is not None]
    return max(both) if len(both) >= SIGNATURE_MIN else None


def loosest_difference(one, other):
    """(other minus one, partner index) where other kerns loosest next to one (its accent or part reaching
    toward that partner), or None with too few partners. Where other measures tighter, the methods read
    air beside an accent the partner does not reach (an accent above T's bar): a class value leaves
    that pair a little loose, never colliding, so it is not counted."""
    both = [(b - a, index) for index, (a, b) in enumerate(zip(one or [], other or [])) if a is not None and b is not None]
    if len(both) < SIGNATURE_MIN:
        return None
    return max(both, key=lambda found: (found[0], -found[1]))


def signatures_match(one, other, tolerance=SIGNATURE_TOLERANCE):
    gap = signature_gap(one, other)
    return gap is not None and gap <= tolerance


def suggest_classes(names, signature_of, model):
    """{side: [[character, ...], ...]} classes for the characters of names ({character: glyph name}).
    An accented letter joins its base where most of the corpus's families class the two together on
    that side (model, from class_model), or, for a pair the corpus has not seen, where the two kern
    alike in this font. Base letters share a class where most families class them so and every two
    of them kern alike here. signature_of(character, side) gives a side_signature, or None."""
    result = {}
    for side in ("first", "second"):
        signatures = {}

        def signature(ch):
            if ch not in signatures:
                signatures[ch] = signature_of(ch, side)
            return signatures[ch]

        rates = (model or {}).get(side, {})
        groups, loners = {}, set()  # base: [members]; letters kept apart from their base
        for ch in sorted(names):
            base = base_letter(ch)
            if base == ch or base not in names:
                groups.setdefault(ch, [ch])
                continue
            rate = rates.get((base, ch))
            joins = rate >= MERGE_RATE if rate is not None else signatures_match(signature(base), signature(ch))
            if joins:
                groups.setdefault(base, [base]).append(ch)
            else:
                groups[ch] = [ch]
                loners.add(ch)
        bases = sorted(b for b in groups if b not in loners)
        candidates = sorted(((rates.get((a, b), 0.0), a, b) for i, a in enumerate(bases) for b in bases[i + 1:]
                             if rates.get((a, b), 0.0) >= MERGE_RATE), reverse=True)
        joined = dict((base, [base]) for base in groups)  # base: the bases of its class (one shared list)
        for rate, a, b in candidates:
            if joined[a] is joined[b]:
                continue
            together = joined[a] + joined[b]
            if all(signatures_match(signature(x), signature(y)) for i, x in enumerate(together) for y in together[i + 1:]):
                for base in together:
                    joined[base] = together
        classes, seen = [], set()
        for base in sorted(groups):
            key = id(joined[base])
            if key in seen:
                continue
            seen.add(key)
            members = []
            for member_base in sorted(joined[base], key=lambda b: (b not in LETTERS, b)):
                members.extend(groups[member_base])
            if len(members) > 1:
                classes.append(members)
        result[side] = classes
    return result


class ClassPlan(object):
    """One suggested class against the font's classes: action "new" (a class to make), "add" (glyphs
    to add to an existing class), "same" (the font has it), or "overlap" (members in several classes,
    or a class that kerns both sides: left as it is)."""

    def __init__(self, side, members, names, kerning, differs=None):
        self.side, self.members = side, members
        self.differs = differs or []  # (character, units, partner): members kerning unlike the first one (units
        # below zero: the member kerns that much tighter than the first one beside the partner)
        self.glyphs = [names[ch] for ch in members]
        lookup = kerning.left_class if side == "first" else kerning.right_class
        found = sorted(set(lookup[g] for g in self.glyphs if g in lookup))
        self.existing, self.adding = None, []
        self.name = None
        if not found:
            self.action = "new"
            self.name = class_name(kerning, CLASS_PREFIX[side] + self.glyphs[0])
            self.adding = list(self.glyphs)
        elif len(found) > 1:
            self.action, self.reason = "overlap", u"its glyphs are in %d classes: %s" % (len(found), u", ".join(found))
            self.existing = found
        else:
            self.existing = found[0]
            self.adding = [g for g in self.glyphs if g not in kerning.members.get(self.existing, [])]
            if not self.adding:
                self.action = "same"
            elif kerning.class_flags.get(self.existing) == "KernBothSide":
                self.action, self.reason = "overlap", u"class %s kerns both sides" % self.existing
            else:
                self.action = "add"

    def describe(self):
        text = self.describe_action()
        if self.differs:
            text += u" \N{EM DASH} may need pairs of their own: " + self.describe_differs()
        return text

    def pair_text(self, ch, partner):
        return ch + partner if self.side == "first" else partner + ch

    def describe_differs(self):
        """Each member kerning unlike the first one, as the pair where it differs most (an e acute beside
        T: "...T 52 units looser than eT")."""
        return u"; ".join(u"%s %d units %s than %s" % (self.pair_text(ch, partner), abs(units),
                                                      u"tighter" if units < 0 else u"looser",
                                                      self.pair_text(self.members[0], partner))
                          for ch, units, partner in self.differs)

    def characters(self, glyphs):
        """The characters of some of this plan's glyphs, in its order."""
        return [ch for ch, glyph in zip(self.members, self.glyphs) if glyph in glyphs]

    def columns(self):
        """(class, glyphs, what happens) as the classes dialog lists them."""
        glyphs = u" ".join(self.members)
        if self.action == "new":
            return self.name, glyphs, u"New class."
        if self.action == "add":
            staying = [ch for ch, glyph in zip(self.members, self.glyphs) if glyph not in self.adding]
            return self.existing, u" ".join(self.characters(self.adding)), (
                u"Added to the class" + (u" (with %s)" % u" ".join(staying) if staying else u"") + u".")
        if self.action == "same":
            return self.existing, glyphs, u"Nothing: the font has this class already."
        existing = u", ".join(self.existing) if isinstance(self.existing, list) else (self.existing or u"")
        return existing, glyphs, u"Left as it is: " + self.reason.rstrip(u".") + u"."

    def key(self):
        """What this plan does, comparable across two workings-out (lists made tuples: hashable)."""
        existing = tuple(self.existing) if isinstance(self.existing, list) else self.existing
        return (self.side, tuple(self.members), self.action, self.name, existing, tuple(self.adding))

    def describe_action(self):
        glyphs = u" ".join(self.members)
        if self.action == "new":
            return u"New class %s: %s" % (self.name, glyphs)
        if self.action == "add":
            return u"Add %s to class %s" % (u" ".join(self.adding), self.existing)
        if self.action == "same":
            return u"Class %s already: %s" % (self.existing, glyphs)
        return u"%s: left as it is (%s)" % (glyphs, self.reason)


def class_name(kerning, wanted):
    name, number = wanted, 2
    while name in kerning.classes:
        name, number = u"%s%d" % (wanted, number), number + 1
    return name


def plan_classes(suggested, names, kerning, signature_of=None, upm=1000.0):
    """The suggestions against the font's classes; with signature_of, each notes the members that kern
    unlike its first glyph by DIFFERS_NOTE or more (in font units)."""
    plans = []
    for side in ("first", "second"):
        for members in suggested.get(side, []):
            differs = []
            if signature_of is not None:
                first = signature_of(members[0], side)
                for ch in members[1:]:
                    found = loosest_difference(first, signature_of(ch, side))
                    if found is not None and found[0] >= DIFFERS_NOTE:
                        differs.append((ch, int(round(found[0] * upm)), SIGNATURE_PARTNERS[side][found[1]]))
            plans.append(ClassPlan(side, members, names, kerning, differs))
    return plans


class NotedException(object):
    """A glyph pair a class's value brings too close (a noted member beside its partner), and the
    value of its own that loosens it by the measured difference."""

    def __init__(self, plan_index, pair, text, current, value):
        self.plan_index, self.pair, self.text = plan_index, pair, text
        self.current, self.value = current, value

    def entry(self):
        return ((self.pair[0], False), (self.pair[1], False))


def noted_exceptions(kerning, plans, names):
    """The noted pairs (ClassPlan.differs) that take their class's tightening now: the member kerns
    beside the partner exactly as the class's first glyph does, below zero. Each gets that value
    loosened by the measured difference, never past zero (an accent that collides unkerned is a
    matter of spacing). kerning is a FontKerning; names maps characters to glyph names."""
    found = []
    for index, plan in enumerate(plans):
        first = names.get(plan.members[0])
        for ch, units, partner in plan.differs:
            member, other = names.get(ch), names.get(partner)
            if not (first and member and other):
                continue
            pair = (member, other) if plan.side == "first" else (other, member)
            base = (first, other) if plan.side == "first" else (other, first)
            current = kerning.current(*pair)
            if current >= 0 or current != kerning.current(*base):
                continue
            value = min(0, current + units)
            if value != current:
                found.append(NotedException(index, pair, plan.pair_text(ch, partner), current, value))
    return found


def write_exceptions(kerning, exceptions):
    """Each exception as a glyph pair of its own (0 kept as an entry: it overrides the class); the
    number written."""
    written = 0
    for exception in exceptions:
        kerning.write(exception.entry(), exception.value, False)
        written += 1
    return written


def own_values(kerning, plans):
    """{(left, right): value} of the glyph pairs whose value comes from an entry naming a glyph a plan
    puts in a class: a member's own kerning, which the class's pairs must not override."""
    found = {}
    for plan in plans:
        at = 0 if plan.side == "first" else 1
        members = plan.glyphs[1:] if plan.action == "new" else plan.adding
        for member in members:
            for entry in kerning.entries:
                if entry[at] != (member, False):
                    continue
                other_name, other_is_class = entry[1 - at]
                others = kerning.members.get(other_name, []) if other_is_class else [other_name]
                for other in others:
                    pair = (member, other) if at == 0 else (other, member)
                    if kerning.resolving(*pair) == entry:
                        found[pair] = kerning.values.get(entry)
    return found


def apply_class_plans(kerning, plans, move_base_kerning=True):
    """Make the "new" classes and extend the "add" ones (kerning: a FontKerning). With
    move_base_kerning, a new class takes over the explicit pairs of its first glyph on its side (its
    members then share them); they are removed from that glyph. A member whose own entry set a pair
    that a class entry would now override gets that value back as a glyph pair. Returns (classes
    made, extended, pairs moved, own values kept)."""
    made = extended = moved = 0
    own = own_values(kerning, plans)
    groups = kerning.kerning.groups
    for plan in plans:
        if plan.action == "new":
            groups[plan.name] = (list(plan.glyphs), CLASS_FLAGS[plan.side])
            kerning.classes.add(plan.name)
            kerning.members[plan.name] = list(plan.glyphs)
            kerning.class_flags[plan.name] = CLASS_FLAGS[plan.side]
            made += 1
            if move_base_kerning:
                base = (plan.glyphs[0], False)
                at = 0 if plan.side == "first" else 1
                for entry in sorted(e for e in kerning.entries if e[at] == base):
                    value = kerning.values.get(entry)
                    if value is None:
                        continue
                    moved_to = ((plan.name, True), entry[1]) if at == 0 else (entry[0], (plan.name, True))
                    if moved_to in kerning.entries:
                        continue
                    kerning.write(moved_to, value, False)
                    kerning.values[moved_to] = value
                    kerning.write(entry, 0, True)
                    kerning.values.pop(entry, None)
                    moved += 1
        elif plan.action == "add":
            members = kerning.members[plan.existing] + [g for g in plan.adding if g not in kerning.members[plan.existing]]
            groups[plan.existing] = (members, kerning.class_flags[plan.existing])
            kerning.members[plan.existing] = members
            extended += 1
    after = FontKerning(kerning.kerning)
    kept = 0
    for (left, right), value in sorted(own.items()):
        if value is not None and after.current(left, right) != round_units(value):
            after.write(((left, False), (right, False)), value, False)
            kept += 1
    return made, extended, moved, kept


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
SIDE_ALPHA = 110  # the H's on either side of a preview's pair, dimmed: the pair is what to look at
RELATED_SHOWN = 30  # glyph pairs named under the preview's note; the rest are counted, all in its tooltip
PICKED_ROOM = 8888  # the widest count the "picked by hand" filter keeps room for
PALETTE_EVENTS = (38, 39)  # QEvent ApplicationPaletteChange, PaletteChange: dark mode switched
COLUMN_CHOICES = {1: "current", 2: "halfkern", 3: "contour", 4: "learned", 5: "fontlab"}  # double-clicked cells

HELP = u"""<b>FreeLab Auto Kerning</b><br>
Suggests kerning for the font's Latin pairs and writes only the pairs you check.<br><br>
<b>The list</b>: each method's value beside the font's current one. Check the pairs to write;
pairs the font kerns already start unchecked.<br>
<b>Choosing a value for one pair</b>: click a preview below the list, double-click a value in the
list, or press Ctrl and its number (1 Now, 2 Average, 3 halfkern, 4 Contour, 5 FreeLab, 6 FontLab)
while the list has the focus. A pair picked by hand is tinted; Backspace or Reset pair gives it the
suggested value again. Restore suggestions puts every check and pick back as the list first came.<br>
<b>Keys in the list</b>: arrows move, a letter jumps to the pairs starting with it, Space checks or
unchecks the pair, Ctrl+1 to Ctrl+6 pick, Backspace resets.<br>
<b>The H's around a pair</b>: click one, in any preview, to go to its pair with the pair's glyph
beside it (H and T for HTo).<br>
<b>The pair's name</b>: double-click it to open the pair in a Glyph window.<br>
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
        self.font_kerning, self.kerning_read = None, 0.0
        self.busy = self.refilter_again = False
        self.common = common_pairs()
        # FontLab's main window as its parent: a parentless dialog counts as a main window of its own,
        # and kept FontLab running, the dialog alone on screen, after FontLab's window was closed.
        dialog = self.dialog = QtGui.QDialog(self.main_window()) if self.main_window() is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Kerning")
        dialog.setWhatsThis(HELP)
        size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = status_label(self.font_line())
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(separator())
        self.log = Log()
        self.seen_history, self.first_pass, self.pinned = None, True, set()
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
        self.include_kerned = QtGui.QCheckBox("Include existing kerned pairs")
        self.include_kerned.setWhatsThis("Also lists the pairs the font kerns already, through its classes too, "
                                          "and the pairs written here since. They start unchecked.")
        row.addWidget(self.include_kerned)
        self.only_picked = QtGui.QCheckBox(u"Only pairs picked by hand (%d)" % PICKED_ROOM)
        self.only_picked.setWhatsThis("Lists only the pairs whose value you picked yourself.")
        # Its room is kept from the start, so the window does not grow when the first pair is picked
        self.only_picked.setMinimumWidth(_property(self.only_picked, "sizeHint").width())
        self.picked_room_kept = _keep_room_when_hidden(self.only_picked)
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
                                u"Double-click a value to use it for that pair, or press Ctrl+1 to Ctrl+6; Space "
                                u"checks the pair; Backspace gives it the suggested value again. Double-click a "
                                u"pair's name to open it in a Glyph window.")
        grid_lines(self.table)
        layout.addWidget(self.table, 1)
        note_row = QtGui.QHBoxLayout()
        self.preview_note = QtGui.QLabel("Select a pair to compare the methods; click one to use it for that pair.")
        self.preview_note.setWordWrap(True)
        note_row.addWidget(self.preview_note, 1)
        self.reset_button = QtGui.QPushButton("Reset pair")
        self.reset_button.setToolTip("Give this pair the suggested value again")
        self.reset_button.setWhatsThis("Gives the selected pair the value of the source chosen above, undoing a pick.")
        self.reset_button.setEnabled(False)
        note_row.addWidget(self.reset_button)
        self.glyph_window_button = QtGui.QPushButton(u"Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected pair in a Glyph window, between H's, n's, and o's, "
                                              u"to look at it (and edit it) with FontLab's own tools.")
        self.glyph_window_button.setEnabled(False)
        note_row.addWidget(self.glyph_window_button)
        layout.addLayout(note_row)
        self.related = QtGui.QLabel(u"")
        self.related.setWordWrap(True)
        self.related.setWhatsThis("The glyph pairs the selected pair's entry kerns: writing it changes all of them.")
        self.related.setVisible(False)
        layout.addWidget(self.related)
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
            button.setToolTip(u"%s: click to use it for this pair (Ctrl+%d in the list)" % (label, number + 1))
            button.setWhatsThis(u"The pair as %s sets it, between two H's. Click to use it for this pair." % label)
            button.setEnabled(False)
            self.choice_group.addButton(button, number)
            self.choice_buttons[key] = button
            grid.addWidget(button, number // 2, number % 2)
            _keep_room_when_hidden(button)  # drawn once a pair is selected
        self.neighbors = dict((key, ClickRegions(button, self.focus_neighbor,
                                                 u"Click to go to this H's pair with the glyph beside it"))
                              for key, button in self.choice_buttons.items())
        layout.addLayout(grid)
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check new pairs")
        self.all_button.setWhatsThis("Checks every listed pair the font does not kern yet.")
        self.none_button = QtGui.QPushButton("Check none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis("Puts every check and every value picked by hand back as the list first "
                                         "came, after the last analysis.")
        self.classes_button = QtGui.QPushButton(u"Suggest classes…")
        self.classes_button.setWhatsThis("Suggests kerning classes for this master, from the open-licensed fonts FreeLab "
                                         "learned from and this font's own outlines, to review before any is made.")
        self.class_dialog = None
        self.check_button = QtGui.QPushButton(u"Check kerning…")
        self.check_button.setWhatsThis(u"Opens Kerning Check: pairs whose kerning makes them collide, entries that "
                                       u"do nothing or name what is gone, and differences between masters.")
        self.apply_button = QtGui.QPushButton("Write checked pairs")
        self.apply_button.setWhatsThis("Writes the Suggested value of every checked pair to the current master, "
                                       "where the pair's value comes from: see Kerning classes in the help.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button, self.classes_button, self.check_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.apply_button.setEnabled(False)
        self.analyze_button.connect("clicked()", self.run)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.buttons_due = False
        self.table.connect("itemChanged(QTableWidgetItem*)", lambda item: self.update_buttons_soon())
        self.apply_button.connect("clicked()", self.write)
        self.classes_button.connect("clicked()", self.suggest_classes)
        self.close_button.connect("clicked()", dialog.close)
        self.reset_button.connect("clicked()", self.reset)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.check_button.connect("clicked()", self.open_kerning_check)
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
        self.watcher = self.watch_palette()
        self.history_timer = watch_history(self)
        self.flagging = flag_menu(self.table, self, lambda: [self.suggestions[self.selected].left,
                                                              self.suggestions[self.selected].right]
                                  if self.selected is not None else [],
                                  lambda row: [self.suggestions[row].left, self.suggestions[row].right]
                                  if row < len(self.suggestions) else [])
        self.focus = None  # a pair to go to once the analysis is done (opened from another script)
        plain_buttons(dialog)
        self.update_buttons()

    def suggest_classes(self):
        if self.class_dialog is None:
            self.class_dialog = ClassDialog(self)  # kept: PythonQt deletes a dialog with no Python reference
        self.class_dialog.show()

    def show_in_glyph_window(self):
        if self.selected is None or self.package is None:
            return
        s = self.suggestions[self.selected]
        error = show_in_glyph_window(self.fontlab, proof_text(s.left, s.right, proof_contexts(self.package, [s.left, s.right])))
        if error:
            self.log.add(u"FontLab did not open the pair: %s" % html(error), "error")

    def open_kerning_check(self):
        """Kerning Check, the script beside this one, on the same font."""
        error = open_sibling_script(KERNING_CHECK_FILE, KERNING_CHECK_MODULE)
        if error:
            self.log.add(u"Kerning Check did not open: %s" % html(error), "error")

    def make_keys(self):
        """The list's keys: Ctrl+1 to Ctrl+6 pick (a plain number or letter jumps to the pairs starting
        with it, as in any list), Backspace resets, Space checks. Only while the list has the focus."""
        QtCore, QtGui = _qt()
        made = []
        try:
            actions = [("Ctrl+%d" % (number + 1), (lambda key=key: self.choose(key))) for number, (key, _) in enumerate(CHOICES)]
            actions += [("Backspace", self.reset), ("Delete", self.reset), ("Space", self.toggle_check)]
            for sequence, action in actions:
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), self.table)
                shortcut.setContext(QtCore.Qt.WidgetShortcut)
                shortcut.connect("activated()", action)
                made.append(shortcut)  # kept: PythonQt deletes what Python no longer holds
        except Exception:
            pass  # no shortcuts: the buttons and double-clicks still work
        return made

    @staticmethod
    def main_window():
        QtCore, QtGui = _qt()
        try:
            for widget in QtGui.QApplication.topLevelWidgets():
                if widget.objectName == "MainWindow":
                    return widget
        except Exception:
            pass
        return None

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
            return u"No font is open. Open one, then click %s." % i("Analyze")
        return u"%s, master %s. Latin letters, figures, and punctuation." % (b(self.package.tfn), b(self.master))

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
        self.status.setText(u"%s: %s of %s\N{HORIZONTAL ELLIPSIS}" % (what, b(done), b(total)))
        QtGui.QApplication.processEvents()
        return not self.stop

    def run(self):
        """Analyze the font that is current now (another may have been opened since the dialog was)."""
        if self.busy:
            return  # a click while measuring or asking FontLab: the work under way finishes first
        self.busy = True
        try:
            self.run_once()
        finally:
            self.busy = False
            self.analyze_button.setEnabled(True)
            if self.refilter_again:
                self.refilter_again = False
                self.refilter()
            self.seen_history = history_mark(self.package)
            if self.focus is not None and self.analysis is not None:
                focus, self.focus = self.focus, None
                self.focus_pair(*focus)

    def run_once(self):
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
            self.status.setText(self.font_line())
            self.log.add(html(message[:1].upper() + message[1:]), "error")
            return
        if result is None:
            self.status.setText(self.font_line())
            self.log.add(u"Stopped.", "warning")
            return
        self.harvest_checks()
        if self.analysis is not None:  # the same font and master: its picks and checks carry over
            before = dict(((old.left, old.right), old) for old in self.analysis.suggestions)
            for new in result.suggestions:
                old = before.get((new.left, new.right))
                if old is not None:
                    new.override, new.checked = old.override, old.checked
        self.analysis = result
        self.refresh_kerning()
        self.refilter(inside_run=True)

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
        wanted = bool(count) or self.only_picked.checked
        if self.picked_room_kept:
            self.only_picked.setVisible(wanted)
        else:  # (a Qt without retainSizeWhenHidden: shown throughout, usable while a pair is picked)
            self.only_picked.setEnabled(wanted)

    def refilter(self, inside_run=False):
        """The list: pairs either method would change by the tolerance or more, whatever source writes
        (choosing another source changes only what is written, not the list or its order)."""
        if self.analysis is None:
            return
        if self.busy and not inside_run:
            self.refilter_again = True  # a setting changed while FontLab was asked: done after
            return
        if not inside_run:
            self.busy = True
            try:
                return self.refilter(inside_run=True)
            finally:
                self.busy = False
                if self.refilter_again:
                    self.refilter_again = False
                    self.refilter()
        self.harvest_checks()
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
                      if (s.left, s.right) in self.pinned
                      or (self.shown(s) and (include or not s.current)
                          and (not common_only or s.left_char + s.right_char in self.common)
                          and (differs(s, "halfkern") or differs(s, "contour") or differs(s, "average")))]
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
        work = (u"%s pairs: %s measured, %s unchanged since the last analysis" % (
                    b(len(analysis.suggestions)), b(analysis.measured), b(analysis.reused))
                if analysis.reused else u"%s pairs measured" % b(len(analysis.suggestions)))
        what = (u"%s listed, picked by hand" % b(len(listed)) if picked_only
                else u"%s listed" % b(len(listed)))
        self.status.setText(u"%s, master %s. %s; %s.<br>%s."
                            % (b(self.package.tfn), b(self.master), work, what, html("; ".join(summary))))
        if self.first_pass:
            self.first_pass = False
            self.log.add(u"Analyzed %s, master %s: %s pairs listed." % (b(self.package.tfn), b(self.master), b(len(listed))))
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
            checked = s.checked if s.checked is not None else not s.current  # the designer's pairs: opt in
            pair.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            table.setItem(row, 0, pair)
            for column in range(1, len(self.COLUMNS)):
                item = QtGui.QTableWidgetItem()
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row, column, item)
            self.fill_row(row, s, source)
        self.select()
        self.update_buttons()

    def target_text(self, s):
        """Where the pair's value is written, for its tooltip and the line under the list."""
        if self.font_kerning is None:
            return u""
        entry = self.font_kerning.target(s.left, s.right)[0]
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

    def harvest_checks(self):
        """The list's checks, kept on its suggestions before the list is filled again (rows read anew)."""
        QtCore, QtGui = _qt()
        for row in range(min(self.table.rowCount, len(self.suggestions))):
            item = self.table.item(row, 0)
            if item is not None:
                self.suggestions[row].checked = item.checkState() == QtCore.Qt.Checked

    def check_all(self, on):
        """Check every new pair, or uncheck everything; pairs the font kerns are checked one by one."""
        QtCore, QtGui = _qt()
        for row in range(self.table.rowCount):
            checked = on and not self.suggestions[row].current
            self.table.item(row, 0).setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        self.update_buttons()

    def row_checked(self, row):
        QtCore, QtGui = _qt()
        item = self.table.item(row, 0)
        return item is not None and item.checkState() == QtCore.Qt.Checked

    def update_buttons_soon(self):
        """Once, after the changes under way (filling the list changes every row)."""
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        self.buttons_due = False
        rows = range(min(self.table.rowCount, len(self.suggestions)))
        checked = [self.row_checked(row) for row in rows]
        enable(self.all_button, any(not on and not self.suggestions[row].current for row, on in zip(rows, checked)))
        enable(self.none_button, any(checked))
        enable(self.apply_button, any(checked))
        enable(self.restore_button, self.edited())
        enable(self.classes_button, self.package is not None)
        enable(self.check_button, self.package is not None)

    def edited(self):
        """Whether a check or a value differs from how the list first came."""
        if self.analysis is None:
            return False
        self.harvest_checks()
        return any(s.override or (s.checked is not None and s.checked != (not s.current))
                   for s in self.analysis.suggestions)

    def restore(self):
        """Every check and pick back as the list first came after the last analysis."""
        if self.analysis is None:
            return
        for s in self.analysis.suggestions:
            s.override, s.checked = None, None
        self.update_picked()
        self.fill_table()
        self.log.add(u"Checks and values restored as suggested.")

    def focus_neighbor(self, key):
        """An H beside a preview's pair clicked: its pair with the glyph beside it."""
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        if key == "before":
            self.focus_pair(u"H", s.left)
        else:
            self.focus_pair(s.right, u"H")

    def focus_pair(self, left, right):
        """The pair of the glyphs named left and right, selected in the list: listed whatever the
        filters (it stays listed until the next analysis), and measured first when it was not."""
        if self.analysis is None or self.package is None:
            self.focus = (left, right)
            return
        found = [s for s in self.analysis.suggestions if (s.left, s.right) == (left, right)]
        if not found:
            s = self.measure_one(left, right)
            if s is None:
                self.log.add(u"The pair %s %s could not be measured: Auto Kerning measures pairs of encoded "
                             u"glyphs." % (b(left), b(right)), "warning")
                return
            self.analysis.suggestions.append(s)
            found = [s]
        self.pinned.add((left, right))
        self.refilter()
        for row, s in enumerate(self.suggestions):
            if (s.left, s.right) == (left, right):
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 0))
                self.table.setFocus()
                return

    def measure_one(self, left, right):
        """A suggestion for one pair outside the analysis (an accented letter's), its values scaled
        by the analysis's factors."""
        package = self.package
        chars = []
        for name in (left, right):
            glyph = package.findName(name)
            code = glyph.fgGlyph.unicode if glyph is not None else 0
            if not code:
                return None
            chars.append(unichr_(code))
        wanted = list(TUNING) + [ch for chars_ in REFERENCES.values() for ch in chars_] + chars
        try:
            result = analyze(package, self.master, characters=u"".join(sorted(set(wanted))), cache_file="")
        except Exception:
            return None
        for s in result.suggestions if result is not None else []:
            if (s.left, s.right) == (left, right):
                for method, units in s.raw.items():
                    tighten, loosen = self.analysis.factors.get(method, DEFAULT_FACTORS[method])
                    s.values[method] = round_units(units * (tighten if units < 0 else loosen))
                return s
        return None

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the current values read again."""
        if self.analysis is None or self.package is None:
            return
        self.refresh_kerning()
        changed = 0
        for s in self.analysis.suggestions:
            now = self.font_kerning.current(s.left, s.right)
            if now != s.current:
                s.current = now
                changed += 1
        if changed:
            self.harvest_checks()
            for row, s in enumerate(self.suggestions):
                self.fill_row(row, s, self.source_key())
            self.select()
            self.log.add(u"The font's History moved (an undo, a redo, or an edit): %s read again. Click %s "
                         u"if outlines changed." % (b(counted(changed, u"current value")), i("Analyze")))

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
            self.glyph_window_button.setEnabled(False)
            self.preview_note.setText("Select a pair to compare the methods; click one to use it for that pair.")
            self.related.setVisible(False)
            for button in self.choice_buttons.values():
                button.setEnabled(False)
                button.setIcon(_qt()[1].QIcon())
                button.setVisible(False)
            return
        for button in self.choice_buttons.values():
            button.setVisible(True)
        self.selected = rows[0].row()
        if self.package is not None and time.time() - self.kerning_read > 1.0:
            self.refresh_kerning()
        self.show_preview(self.suggestions[self.selected])

    def refresh_kerning(self):
        self.font_kerning, self.kerning_read = FontKerning(self.package.kerning(self.master)), time.time()

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
        """A method's value double-clicked: that value for the pair; the Suggested one: reset; the
        pair's name: the pair in a Glyph window."""
        if row >= len(self.suggestions):
            return
        self.table.selectRow(row)
        self.selected = row
        if column == 0:
            self.show_in_glyph_window()
        elif column in COLUMN_CHOICES:
            self.choose(COLUMN_CHOICES[column])
        elif column == len(self.COLUMNS) - 1:
            self.reset()

    def show_related(self, s):
        """Under the note, the glyph pairs the pair's entry kerns, when there are others."""
        pairs = self.font_kerning.pairs(self.font_kerning.target(s.left, s.right)[0]) if self.font_kerning else []
        if len(pairs) < 2:
            self.related.setVisible(False)
            return
        names = [u"%s %s" % pair for pair in pairs if pair != (s.left, s.right)]
        shown = u", ".join(names[:RELATED_SHOWN])
        if len(names) > RELATED_SHOWN:
            shown += u", and %d more" % (len(names) - RELATED_SHOWN)
        self.related.setText(u"Also kerns: %s." % shown)
        self.related.setToolTip(u"\n".join(names))
        self.related.setVisible(True)

    def watch_palette(self):
        """Dark mode switched while the dialog is open: its buttons restyled and its previews redrawn in
        the new text color (a stylesheet's look and a drawn picture keep the old colors otherwise)."""
        QtCore, QtGui = _qt()
        dialog = self

        class PaletteWatcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() in PALETTE_EVENTS and not dialog.repainting:
                        dialog.repainting = True
                        QtCore.QTimer.singleShot(0, dialog.restyle)
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.repainting = False
        try:
            watcher = PaletteWatcher()
            self.dialog.installEventFilter(watcher)
            return watcher
        except Exception:
            return None

    def restyle(self):
        try:
            for button in self.choice_buttons.values():
                button.setStyleSheet(u"")
                button.setStyleSheet(CHOICE_SHEET)  # polished again from the new palette
            self.refresh_values()  # the tints and the previews, in the new colors
        finally:
            self.repainting = False

    def show_preview(self, s):
        """Each choice's button: the pair between two H's as that method sets it, its name and value
        beside it (all in one picture, drawn in the dialog's text color), and the one the pair takes
        checked."""
        QtCore, QtGui = _qt()
        source = self.source_key()
        chosen = s.override or source
        self.reset_button.setEnabled(bool(s.override))
        self.glyph_window_button.setEnabled(True)
        picked = (u"Picked by hand: %s. " % dict(CHOICES)[s.override]) if s.override else u""
        target = self.target_text(s)
        self.preview_note.setText(u"%sThe pair %s: %s" % (picked, s.left_char + s.right_char, target[:1].lower() + target[1:]))
        self.show_related(s)
        palette = self.dialog.palette
        text = palette.color(QtGui.QPalette.WindowText)  # (FontLab 7's PythonQt lacks the placeholder text role)
        scale = float(PREVIEW_SIZE) / float(self.package.upm)
        paths = []  # (layer, path, role): the pair between two H's, when the font has an H
        for name, role in (("H", "side"), (s.left, "left"), (s.right, "right"), ("H", "side")):
            glyph = self.package.findName(name)
            layer = glyph.getLayerByName(self.master) if glyph is not None and not glyph.isNull else None
            if layer is not None:
                paths.append((layer, layer_path(layer), role))
        strip = int(sum(layer.advanceWidth for layer, _, _ in paths) * scale) + PREVIEW_SIZE
        font = QtGui.QFont(self.dialog.font)
        for number, (key, label) in enumerate(CHOICES):
            button, kern = self.choice_buttons[key], s.value(key)
            button.setEnabled(kern is not None)
            button.setChecked(key == chosen)
            pixmap = QtGui.QPixmap(strip + PREVIEW_TEXT_WIDTH, int(PREVIEW_SIZE * 1.35))
            pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter(pixmap)
            spans = []
            try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
                if kern is not None:
                    spans = self.paint_pair(painter, paths, scale, kern, text)
                self.paint_label(painter, font, text, strip, pixmap.height(), label,
                                 u"\N{EN DASH}" if kern is None else str(kern), number + 1)
            finally:
                painter.end()
            button.setIcon(QtGui.QIcon(pixmap))
            button.setIconSize(pixmap.size())
            self.neighbors[key].set(spans, pixmap.size())

    @staticmethod
    def paint_pair(painter, paths, scale, kern, color):
        """Draws the pair between its H's; the H's spans across the picture, (left, right, "before" or
        "after"), to be clicked."""
        QtCore, QtGui = _qt()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        x = float(PREVIEW_SIZE) / 2
        spans, seen_pair = [], False
        for layer, path, role in paths:
            painter.save()
            painter.translate(x, PREVIEW_SIZE * 1.05)
            painter.scale(scale, -scale)
            ink = QtGui.QColor(color)
            if role == "side":
                ink.setAlpha(SIDE_ALPHA)  # the H's: dimmed
            painter.fillPath(path, QtGui.QBrush(ink))
            painter.restore()
            advance = layer.advanceWidth * scale + (kern * scale if role == "left" else 0)
            if role == "side":
                spans.append((x, x + layer.advanceWidth * scale, "after" if seen_pair else "before"))
            else:
                seen_pair = True
            x += advance
        return spans

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
        painter.drawText(QtCore.QRect(left, top + 2 * line, PREVIEW_TEXT_WIDTH, line), flags, u"Ctrl+%d" % key)

    def write(self):
        """Each checked pair's value, written where it applies (FontKerning.target). Pairs sharing an
        entry (a class pair) with other checked pairs get the value of the most common of them, even
        when that one keeps its current value; ties go to the first in alphabetical order."""
        QtCore, QtGui = _qt()
        if self.busy:
            return
        self.harvest_checks()
        source = self.source_key()
        kerning = FontKerning(self.package.kerning(self.master))
        plans = {}
        for s in self.suggestions:
            if not s.checked:
                continue
            value = s.to_write(source)
            if value is None:
                continue
            target = kerning.target(s.left, s.right)
            plans.setdefault(target[0], []).append(((self.rank(s), s.left_char, s.right_char), s, value, target[1]))
        shared = classes = entries = 0
        written, error = [], None
        try:
            for entry, wanted in sorted(plans.items()):
                wanted.sort(key=lambda plan: plan[0])
                _, first, value, remove = wanted[0]
                if len(set(plan[2] for plan in wanted)) > 1:
                    shared += len(wanted) - 1
                if value == first.current:
                    continue  # the commonest pair keeps its value: the entry stays as it is
                kerning.write(entry, value, remove)
                entries += 1
                if kerning.reach(entry) > 1:
                    classes += 1
                written.extend(plan[1] for plan in wanted)
        except Exception as exc:  # what was written stays written, and is reported
            error = exc
        self.after_writing(self.package)
        self.refresh_kerning()
        for s in self.analysis.suggestions:
            s.current = self.font_kerning.current(s.left, s.right)
        for s in written:
            s.override = None
        lines = [u"Wrote %d entries for %d pairs to master %s%s." % (
            entries, len(written), self.master,
            u" (%d of them kerning class pairs, which kern their classes' other glyphs too)" % classes if classes else u"")]
        if shared:
            lines.append(u"%d pairs shared an entry with a commoner pair and took its value." % shared)
        self.update_picked()
        self.fill_table()
        self.log.add(html(u" ".join(lines)), "done" if entries else "info")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % html(error), "error")
        self.seen_history = history_mark(self.package)

    def after_writing(self, package):
        """FontLab told of the change, and the font marked modified: a script's kerning writes leave it
        unmarked, and FontLab would close it without asking to save."""
        notify_changed(self.fontlab, package, u"FreeLab Auto Kerning")


def font_class_suggestions(package, master, core=None, em=EM_PIXELS, model=None):
    """(plans, names): the classes suggested for a master, planned against its own classes."""
    glyphs = FontLabGlyphs(package, master, em)
    found = [(ch, name) for ch, name in font_glyphs(package, class_characters()) if glyphs.add(name)]
    names = dict(found)
    for ch in TUNING:
        if ch not in names:
            raise ValueError(u"this font has no “%s”: "
                             u"its spacing is what glyphs are compared by." % ch)
    image_of = lambda ch: glyphs.image(names[ch])
    tools = make_bands(core or Core(), image_of, names, em, glyphs.pad)
    signatures = {}

    def signature_of(ch, side):
        if (ch, side) not in signatures:
            signatures[(ch, side)] = side_signature(tools, image_of, names, ch, side, em, float(glyphs.pad))
        return signatures[(ch, side)]

    suggested = suggest_classes(names, signature_of, model if model is not None else class_model())
    return plan_classes(suggested, names, FontKerning(package.kerning(master)), signature_of, glyphs.upm), names


class ClassDialog(object):
    """Suggested kerning classes for the current master: review, check, and create."""

    def __init__(self, owner):
        QtCore, QtGui = _qt()
        self.owner = owner
        parent = owner.dialog
        dialog = self.dialog = QtGui.QDialog(parent)
        dialog.setWindowTitle("FreeLab Kerning Classes")
        dialog.setWhatsThis(CLASS_HELP)
        size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = status_label(plain=True)  # (its text names glyphs, which rich text could misread)
        layout.addWidget(self.status)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(CLASS_COLUMNS))
        self.tree.setHeaderLabels(list(CLASS_COLUMNS))
        self.tree.setWhatsThis(u"Each class suggested for this master: checked ones are made (or extended) when you click "
                               u"Create checked classes. Gray ones are shown for reference and left as they are. "
                               u"<i>May need pairs of their own</i> names the members that need looser kerning than the "
                               u"class's first glyph (an accent reaching toward the neighbor), at the pair where they "
                               u"differ most: the class's value would bring them too close there, so check those pairs "
                               u"after kerning the class.")
        layout.addWidget(self.tree, 1)
        self.move = QtGui.QCheckBox("Move each new class's first glyph's pairs into the class.")
        self.move.setChecked(True)
        self.move.setWhatsThis(u"A new class made from A, \N{LATIN CAPITAL LETTER A WITH GRAVE}, ... takes over A's own pairs on "
                               u"that side, so every member kerns as A does. Without it, the class starts with no kerning.")
        layout.addWidget(self.move)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.apply_button = QtGui.QPushButton("Create checked classes")
        self.exceptions_button = QtGui.QPushButton("Write checked pairs")
        self.exceptions_button.setWhatsThis(u"Gives each checked pair of <i>Pairs too close with their class's "
                                            u"value</i> the value shown, as a pair of its own: the class kerns "
                                            u"its other glyphs as before.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.exceptions_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.apply_button.connect("clicked()", self.apply)
        self.exceptions_button.connect("clicked()", self.write_exceptions)
        self.close_button.connect("clicked()", dialog.close)
        self.plans, self.names, self.exceptions = [], {}, []
        plain_buttons(dialog)

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)

    def run(self):
        QtCore, QtGui = _qt()
        package = self.owner.current_font()
        master = package.master if package is not None else None
        self.package, self.master, self.plans, self.exceptions = package, master, [], []
        self.tree.clear()
        self.apply_button.setEnabled(False)
        self.exceptions_button.setEnabled(False)
        if package is None:
            self.status.setText(u"No font is open. Open one, then run Auto Kerning again.")
            return
        if class_model() is None:
            self.status.setText(u"The class model (%s) is missing beside the script: reinstall FreeLab." % CLASS_MODEL_FILE)
            return
        self.status.setText(u"Comparing the glyphs' sides\N{HORIZONTAL ELLIPSIS}")
        QtGui.QApplication.processEvents()
        try:
            self.plans, self.names = font_class_suggestions(package, master)
            self.exceptions = noted_exceptions(FontKerning(package.kerning(master)), self.plans, self.names)
        except Exception as exc:
            self.status.setText(u"%s" % exc)
            return
        self.fill()

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.clear()  # (items are found again by walking the tree, never kept: PythonQt deletes them here)
        counts = {}
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        for side in ("first", "second"):
            top = QtGui.QTreeWidgetItem([CLASS_SIDES_LABELS[side]])
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            section_row(top, self.tree)
            order = {"new": 0, "add": 0, "overlap": 1, "same": 2}  # what can be made first, what the font has last
            for index, plan in sorted(enumerate(self.plans), key=lambda pair: (order[pair[1].action], pair[0])):
                if plan.side != side:
                    continue
                counts[plan.action] = counts.get(plan.action, 0) + 1
                item = QtGui.QTreeWidgetItem(list(plan.columns()) + [plan.describe_differs()])
                item.setData(0, QtCore.Qt.UserRole, index)
                if plan.action in ("new", "add"):
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
                    item.setCheckState(0, QtCore.Qt.Checked)
                else:
                    item.setFlags(QtCore.Qt.ItemIsSelectable)  # shown, not made: drawn disabled
                tip = u"%s\nGlyphs: %s" % (plan.describe(), u" ".join(plan.glyphs))  # (plain: members may be < or &)
                for column in range(len(CLASS_COLUMNS)):
                    item.setToolTip(column, tip)
                for column in (0, 1):  # the class and its letters stand out
                    item.setFont(column, bold)
                top.addChild(item)
            top.setExpanded(True)
        if self.exceptions:
            top = QtGui.QTreeWidgetItem([CLASS_EXCEPTIONS_LABEL])
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            section_row(top, self.tree)
            for index, exception in enumerate(self.exceptions):
                plan = self.plans[exception.plan_index]
                class_name = plan.existing if isinstance(plan.existing, (type(u""), str)) else u""
                item = QtGui.QTreeWidgetItem([class_name, exception.text,
                                              u"Its own value: %d \N{RIGHTWARDS ARROW} %d" % (exception.current, exception.value),
                                              u", ".join(d for d in plan.describe_differs().split(u"; ")
                                                         if d.startswith(exception.text + u" "))])
                item.setData(0, QtCore.Qt.UserRole, EXCEPTION_ROLE_BASE + index)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
                item.setCheckState(0, QtCore.Qt.Checked)
                tip = (u"%s %s now takes %d from its class; written as a pair of its own, it gets %d (an estimate: "
                       u"look at it after writing)." % (exception.pair[0], exception.pair[1], exception.current,
                                                        exception.value))
                for column in range(len(CLASS_COLUMNS)):
                    item.setToolTip(column, tip)
                for column in (0, 1):
                    item.setFont(column, bold)
                top.addChild(item)
            top.setExpanded(True)
        self.exceptions_button.setEnabled(bool(self.exceptions))
        for column in range(len(CLASS_COLUMNS) - 1):
            self.tree.resizeColumnToContents(column)
        plural = lambda count, one, many: u"%d %s" % (count, one if count == 1 else many)
        self.status.setText(u"%s, master %s: %s, %s, %s, %s (they overlap its classes). Nothing is changed until you "
                            u"create them." % (self.package.tfn, self.master,
                                               plural(counts.get("new", 0), u"new class", u"new classes"),
                                               plural(counts.get("add", 0), u"class to extend", u"classes to extend"),
                                               plural(counts.get("same", 0), u"the font has already", u"the font has already"),
                                               plural(counts.get("overlap", 0), u"left as it is", u"left as they are")))
        self.apply_button.setEnabled(bool(counts.get("new") or counts.get("add")))

    def items(self, exceptions=False):
        """The rows of suggested classes, or of pairs too close (exceptions True)."""
        QtCore, QtGui = _qt()
        found = []
        for top_index in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(top_index)
            for child in range(top.childCount()):
                item = top.child(child)
                if (int(item.data(0, QtCore.Qt.UserRole)) >= EXCEPTION_ROLE_BASE) == exceptions:
                    found.append(item)
        return found

    def write_exceptions(self):
        """The checked pairs too close, each written as a pair of its own."""
        QtCore, QtGui = _qt()
        chosen = [self.exceptions[int(item.data(0, QtCore.Qt.UserRole)) - EXCEPTION_ROLE_BASE]
                  for item in self.items(exceptions=True) if item.checkState(0) == QtCore.Qt.Checked]
        if not chosen:
            return
        package, master = self.package, self.master
        current = self.owner.current_font()
        if current is None or font_key(current) != font_key(package) or current.master != master:
            self.run()
            self.status.setText(u"The font or master changed since these pairs were measured: here are this one's. "
                                + self.status.text)
            return
        kerning = FontKerning(package.kerning(master))
        stale = [e for e in chosen if kerning.current(*e.pair) != e.current]
        error, written = None, 0
        try:
            written = write_exceptions(kerning, [e for e in chosen if e not in stale])
        except Exception as exc:  # what was written stays written, and is reported
            error = exc
        self.owner.after_writing(package)
        self.run()
        notes = [u"Wrote %d pairs of their own." % written]
        if stale:
            notes.append(u"%d pairs had changed since they were measured and were left as they are." % len(stale))
        if error is not None:
            notes.append(u"Stopped by an error: %s" % error)
        notes.append(u"Writing goes straight into the open font: close it without saving to take it back.")
        self.status.setText(u" ".join(notes) + u" " + self.status.text)

    def check_all(self, on):
        QtCore, QtGui = _qt()
        for item in self.items() + self.items(exceptions=True):
            if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)

    def apply(self):
        QtCore, QtGui = _qt()
        chosen = []
        for item in self.items():
            if item.flags() & QtCore.Qt.ItemIsUserCheckable and item.checkState(0) == QtCore.Qt.Checked:
                chosen.append(self.plans[int(item.data(0, QtCore.Qt.UserRole))])
        if not chosen:
            return
        package, master = self.package, self.master
        current = self.owner.current_font()
        if current is None or font_key(current) != font_key(package) or current.master != master:
            self.run()
            self.status.setText(u"The font or master changed since these suggestions: here are this one's. Review them "
                                u"before creating any. " + self.status.text)
            return
        fresh, _ = font_class_suggestions(package, master)  # the font as it is now: names free, classes as listed
        wanted = set(plan.key() for plan in chosen)
        chosen = [plan for plan in fresh if plan.key() in wanted]
        if len(chosen) != len(wanted):
            self.plans = fresh
            self.fill()
            self.status.setText(u"The font's classes changed since these suggestions: they are worked out again. Review "
                                u"them before creating any. " + self.status.text)
            return
        error = None
        made = extended = moved = kept = 0
        try:
            made, extended, moved, kept = apply_class_plans(FontKerning(package.kerning(master)), chosen, self.move.checked)
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
        self.owner.after_writing(package)
        self.run()
        notes = [u"Made %d classes and extended %d%s." % (made, extended, u", and moved %d pairs into them" % moved
                                                           if moved else u"")]
        if kept:
            notes.append(u"%d glyph pairs kept their own value as an exception." % kept)
        if error is not None:
            notes.append(u"Stopped by an error: %s" % error)
        notes.append(u"Writing goes straight into the open font: close it without saving to take it back.")
        self.status.setText(u" ".join(notes) + u" " + self.status.text)
        if self.owner.package is not None and font_key(self.owner.package) == font_key(package):
            self.owner.run()  # Auto Kerning reads the classes again


CLASS_HELP = u"""<b>FreeLab Kerning Classes</b><br>
Suggests kerning classes for this master: glyphs that kern alike, on the side that faces the pair.<br><br>
<b>How</b>: an accented letter joins its base letter where most of the open-licensed fonts FreeLab
learned from class the two together on that side. Base letters share a class where most of those
fonts class them so (n with m and h, o with c, e, and q) and every two of them kern alike in this
font.<br>
<b>May need pairs of their own</b>: members that need kerning looser than the class's first glyph by
3% of the em or more, each at the pair where it differs most (an e with an accent beside T: the accent
stops it from tucking under T's bar as far as e does). The class's value will not fit that pair.<br>
<b>Pairs too close with their class's value</b>: the noted pairs the class tightens now, each with a
value of its own: the class's, loosened by the difference measured (never past 0). <i>Write checked
pairs</i> writes them as glyph pairs, which the class's value no longer reaches.<br>
<b>Sides</b>: <i>First in a pair</i> classes group glyphs by their right side (FontLab's left, or 1st,
classes); <i>second in a pair</i> by their left side.<br>
<b>The font's classes come first</b>: a suggestion makes a class only where none of its glyphs has one
on that side, or adds glyphs to the one class they share. Suggestions overlapping several classes,
or a class that kerns both sides, are shown and left as they are.<br><br>
Click this help's ? button, then any control, for what it does."""



def main(focus=None):
    """Opens Auto Kerning; focus: a pair of glyph names to select once the font is analyzed."""
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
    dialog.focus = focus
    hook_menu_order()
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_auto_kerning":
    main()
