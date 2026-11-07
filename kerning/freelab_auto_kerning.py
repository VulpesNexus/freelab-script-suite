#FLM: Auto Kerning
# -*- coding: utf-8 -*-
"""FreeLab auto kerning, from FontLab's Scripts menu.

Suggests kerning for the Latin pairs of the current font's current master, shows each beside the
kerning the font has, and writes only the pairs you approve. The method is halfkern's
(https://github.com/behdad/halfkern, Copyright 2022 Google LLC, Apache License 2.0), measured by
FreeLab's own native core (kerning/native/freelab_kern.c): every glyph gets an envelope, a halo
around its ink; a pair moves until the overlap of the two envelopes falls within a band taken from
the font's own ll, nn, and oo. Tightenings are applied at half strength, as halfkern does, or at the
strength the font's existing kerning shows (its pairs act as models).

Valid Python 2.7 (FontLab 7) and Python 3. The core below needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys

VERSION = "0.1.0"
KERN_VERSION = 1  # FREELAB_KERN_VERSION in kerning/native/freelab_kern.c
EM_PIXELS = 200  # rendering size, pixels per em (halfkern renders at 100; finer steps here)
HALO_SHARE = 0.1  # the envelope's halo, as a share of the em (halfkern's starting kernel)
PAD_SHARE = 0.3  # room around each glyph image for the halo and the search, as a share of the em
TUNING = (u"l", u"n", u"o")  # spaced right by the designer: the halo and the lowercase band come from them
# Each kind of pair is held to the spacing the designer gave its own kind: references set with each
# other with no kerning (HH, HO, OH, OO for capitals; Hn or Oo across cases). halfkern takes one band
# from lowercase alone, which loosened straight capitals (HH, MN) the designer had spaced as wanted.
REFERENCES = {"upper": (u"H", u"O"), "lower": TUNING, "figure": (u"0", u"8")}
TIGHTEN = 0.5  # halfkern applies half of a tightening
LOOSEN = 1.0
FACTOR_RANGE = (0.1, 1.5)  # a factor fitted to the font's kerning stays within this
MODELS_MIN = 3  # fewer existing pairs than this: halfkern's factors
TOLERANCE_UNITS = 20  # a suggestion this close to the current value is not listed (about 2% of the em)
SHOW = (("letters", "Letters"), ("punctuation", "Letters and punctuation"), ("figures", "Figures"), ("all", "Everything"))
PREVIEW_SIZE = 64  # pixels per em in the dialog's preview
LETTERS = u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
FIGURES = u"0123456789"
PUNCTUATION = u".,:;!?'\"-()[]{}/&*‘’“”«»–—"


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


class Glyph(object):
    """One glyph's coverage image: `coverage` holds height rows of `stride` bytes; the glyph's origin
    is at column origin_x, on the same baseline row in every image; advance in whole pixels."""

    def __init__(self, name, coverage, width, height, stride, origin_x, advance):
        self.name, self.coverage = name, coverage
        self.width, self.height, self.stride = width, height, stride
        self.origin_x, self.advance = origin_x, advance
        self._envelopes = {}

    def envelope(self, core, bias):
        if bias not in self._envelopes:
            self._envelopes[bias] = core.envelope(self, bias)
        return self._envelopes[bias]


def base_offset(left, right):
    """The left image's column in the right one's pixels, the pair set with no kerning."""
    return right.origin_x - left.advance - left.origin_x


class Band(object):
    def __init__(self, bias, low, high):
        self.bias, self.low, self.high = bias, low, high


def first_bias(em):
    width = int(round(2 * HALO_SHARE * em))
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
    """The band of the references set with each other with no kerning, or None without them."""
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
    """The pair's kerning in pixels (negative is tighter; not yet scaled), refined between whole
    steps where the overlap crosses the band, or None when no step within reach does."""
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


def to_units(pixels, em, upm, tighten=TIGHTEN, loosen=LOOSEN):
    value = pixels * upm / em
    value *= tighten if value < 0 else loosen
    return int(round(value))


def fit_factors(samples):
    """The tightening and loosening factors that best turn raw suggestions (units, unscaled) into
    the designer's kerning, from (raw, designer) pairs; halfkern's where too few pairs show one."""
    factors = []
    for sign, default in ((-1, TIGHTEN), (1, LOOSEN)):
        chosen = [(raw, value) for raw, value in samples if raw * sign > 0 and value * sign > 0]
        if len(chosen) < MODELS_MIN:
            factors.append(default)
            continue
        factor = sum(raw * value for raw, value in chosen) / sum(raw * raw for raw, _ in chosen)
        factors.append(min(FACTOR_RANGE[1], max(FACTOR_RANGE[0], factor)))
    return tuple(factors)


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
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.translate(origin_x, baseline)
        painter.scale(scale, -scale)
        painter.fillPath(path, QtGui.QBrush(QtGui.QColor(0, 0, 0, 255)))
        painter.end()
        stride = image.bytesPerLine()
        address = ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))
        coverage = (ctypes.c_uint8 * (stride * height)).from_buffer_copy(ctypes.string_at(address, stride * height))
        advance = int(round(self.advances[name] * scale))
        glyph = Glyph(name, coverage, width, height, stride, origin_x, advance)
        self.images[name] = glyph
        return glyph


def current_kerning(kerning, left, right):
    try:
        value = kerning.get((left, right))
    except Exception:
        return 0
    return int(round(value or 0))


class Suggestion(object):
    def __init__(self, left_char, right_char, left, right, current, raw, value):
        self.left_char, self.right_char = left_char, right_char
        self.left, self.right = left, right
        self.current, self.raw, self.value = current, raw, value


def analyze(package, master, characters=None, em=EM_PIXELS, progress=None, core=None):
    """Suggestions for every pair of the characters (Latin by default) the font has, with the
    factors fitted to its existing kerning. progress(done, total) may return False to stop."""
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
    bands = {}
    for left_kind in references:
        for right_kind in references:
            bands[(left_kind, right_kind)] = (reference_band(core, references[left_kind], references[right_kind], band.bias)
                                              or band)
    kerning = package.kerning(master)
    raw, total, done = [], len(chars) * len(chars), 0
    for left_char, left in chars:
        left_glyph = glyphs.image(left)
        for right_char, right in chars:
            done += 1
            if progress is not None and done % 200 == 0 and progress(done, total) is False:
                return None
            kinds = pair_kinds(left_char, right_char)
            if kinds is None:
                continue
            pixels = suggest_pixels(core, left_glyph, glyphs.image(right), bands[kinds])
            if pixels is None:
                continue
            units = pixels * glyphs.upm / em
            raw.append((left_char, right_char, left, right, current_kerning(kerning, left, right), units))
    tighten, loosen = fit_factors([(units, current) for _, _, _, _, current, units in raw if current])
    suggestions = []
    for left_char, right_char, left, right, current, units in raw:
        value = int(round(units * (tighten if units < 0 else loosen)))
        suggestions.append(Suggestion(left_char, right_char, left, right, current, units, value))
    return suggestions, (tighten, loosen), band


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

class AutoKerningDialog(object):
    COLUMNS = ("Pair", "Current", "Suggested", "Change")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.package = fontlab.flWorkspace.instance().currentPackage
        if self.package is None or self.package.isNull:
            raise RuntimeError("open a font first")
        self.master = self.package.master
        self.suggestions, self.stop = [], False
        dialog = self.dialog = QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Kerning")
        dialog.resize(560, 640)
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
        self.show_kind = QtGui.QComboBox()
        for _, label in SHOW:
            self.show_kind.addItem(label)
        row.addWidget(self.show_kind)
        row.addStretch(1)
        self.analyze_button = QtGui.QPushButton("Analyze")
        row.addWidget(self.analyze_button)
        layout.addLayout(row)
        self.table = QtGui.QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(self.table.fontMetrics().height + 6)
        layout.addWidget(self.table, 1)
        self.preview = QtGui.QLabel()
        self.preview.setMinimumHeight(2 * PREVIEW_SIZE + 44)
        layout.addWidget(self.preview)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
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
        self.table.connect("itemSelectionChanged()", self.show_preview)
        self.tolerance.connect("valueChanged(int)", lambda value: self.refilter())
        self.show_kind.connect("currentIndexChanged(int)", lambda index: self.refilter())
        self.all_suggestions, self.factors = [], (TIGHTEN, LOOSEN)

    def show(self):
        self.dialog.show()
        self.dialog.raise_()

    def progress(self, done, total):
        QtCore, QtGui = _qt()
        self.status.setText("Measuring pairs: %d of %d" % (done, total))
        QtGui.QApplication.processEvents()
        return not self.stop

    def run(self):
        QtCore, QtGui = _qt()
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
        self.all_suggestions, self.factors, _band = result
        self.refilter()

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

    def refilter(self):
        if not self.all_suggestions:
            return
        tighten, loosen = self.factors
        tolerance = self.tolerance.value
        listed = [s for s in self.all_suggestions if abs(s.value - s.current) >= tolerance and self.shown(s)]
        listed.sort(key=lambda s: -abs(s.value - s.current))
        self.suggestions = listed
        models = "from the font's kerning" if (tighten, loosen) != (TIGHTEN, LOOSEN) else "halfkern's (too few pairs in the font)"
        self.status.setText("%d pairs measured; %d listed differ by %d units or more. Tightenings at %.0f%%, loosenings at %.0f%%, %s."
                            % (len(self.all_suggestions), len(listed), tolerance, tighten * 100, loosen * 100, models))
        self.fill_table()

    def fill_table(self):
        QtCore, QtGui = _qt()
        table = self.table
        table.setRowCount(len(self.suggestions))
        for row, s in enumerate(self.suggestions):
            pair = QtGui.QTableWidgetItem(s.left_char + s.right_char)
            pair.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            pair.setCheckState(QtCore.Qt.Checked)
            pair.setToolTip("%s %s" % (s.left, s.right))
            table.setItem(row, 0, pair)
            for column, value in ((1, s.current), (2, s.value), (3, s.value - s.current)):
                item = QtGui.QTableWidgetItem("%+d" % value if column == 3 else str(value))
                item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row, column, item)
        table.resizeColumnsToContents()
        self.apply_button.setEnabled(bool(self.suggestions))

    def check_all(self, on):
        QtCore, QtGui = _qt()
        for row in range(self.table.rowCount):
            self.table.item(row, 0).setCheckState(QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)

    def show_preview(self):
        """The selected pair as it is set now and as suggested, in the dialog's own colors."""
        QtCore, QtGui = _qt()
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        s = self.suggestions[rows[0].row()]
        width, height = max(300, self.preview.width), 2 * PREVIEW_SIZE + 40
        pixmap = QtGui.QPixmap(width, height)
        palette = self.dialog.palette
        pixmap.fill(palette.color(QtGui.QPalette.Base))
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        upm = float(self.package.upm)
        scale = float(PREVIEW_SIZE) / upm
        names = [self.package.findName(n) for n in ("H", s.left, s.right, "H")]
        for line, (label, kern) in enumerate((("Now", s.current), ("Suggested", s.value))):
            painter.setPen(palette.color(QtGui.QPalette.Text))
            painter.drawText(8, 22 + line * (PREVIEW_SIZE + 12), label)
            x = 100.0
            for index, glyph in enumerate(names):
                if glyph is None or glyph.isNull:
                    continue
                layer = glyph.getLayerByName(self.master)
                painter.save()
                painter.translate(x, PREVIEW_SIZE * 0.85 + 8 + line * (PREVIEW_SIZE + 12))
                painter.scale(scale, -scale)
                painter.fillPath(layer_path(layer), QtGui.QBrush(palette.color(QtGui.QPalette.Text)))
                painter.restore()
                x += layer.advanceWidth * scale + (kern * scale if index == 1 else 0)
        painter.end()
        self.preview.setPixmap(pixmap)

    def write(self):
        QtCore, QtGui = _qt()
        kerning = self.package.kerning(self.master)
        written = 0
        for row, s in enumerate(self.suggestions):
            if self.table.item(row, 0).checkState() != QtCore.Qt.Checked:
                continue
            if s.value:
                kerning[(s.left, s.right)] = s.value
            else:
                try:
                    del kerning[(s.left, s.right)]
                except Exception:
                    pass
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
