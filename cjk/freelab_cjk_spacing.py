#FLM: CJK Spacing
# -*- coding: utf-8 -*-
"""FreeLab CJK Spacing, from FontLab's Scripts menu.

Writes the OpenType code that sets a Japanese font's full-width kana and punctuation proportionally:

- palt (proportional alternate widths, which applications turn on for proportional Japanese text):
  each full-width kana, CJK punctuation mark, and full-width form is trimmed to its ink and the
  sidebearings the open-licensed CJK fonts give theirs (cjk/palt_model.json, measured by
  cjk/train/palt.py: about 0.07 em on each side for kana, each punctuation mark its own).
- halt (half widths, for punctuation set in half the em, as in tight headlines): each punctuation
  mark's half-width setting, as those fonts set it (an opening bracket keeps its right half, a comma
  its left).

- Hangul widths: none of the corpus's Korean fonts kerns Hangul or puts it in palt; they set every
  syllable at one width (0.9 em, the median) or give each its own, its sidebearings by its shape
  (cjk/hangul_model.json, measured by cjk/train/hangul.py). On request, the font's syllables are set
  either way: their outlines moved and their widths changed, in every master.

Shows each glyph's trim and the text set both ways before anything is written, and writes only the
glyphs you leave checked, between FreeLab's marker lines in palt and halt (the rest of each feature
kept).

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import os
import re
import sys

MODEL_FILE = "palt_model.json"
HANGUL_MODEL_FILE = "hangul_model.json"
HANGUL_MODES = (("leave", u"Leave as they are"), ("fixed", u"One width for all, ink centered"),
                ("proportional", u"Proportional, by syllable shape"))
HANGUL_SHAPES = (("vertical", u"Vowel beside (\uac00)"), ("vertical final", u"Vowel beside, final (\uac01)"),
                 ("horizontal", u"Vowel under (\uace0)"), ("horizontal final", u"Vowel under, final (\uace1)"),
                 ("mixed", u"Vowel beside and under (\uacfc)"), ("mixed final", u"Vowel beside and under, final (\uacfd)"))
HANGUL_TOLERANCE = 2  # a syllable moved and widened by less than this is left alone
KOREAN_SAMPLE = u"\ud55c\uae00 \uae00\uaf34\uc740 \uc774\ub807\uac8c \ubcf4\uc785\ub2c8\ub2e4."
FULL_WIDTH_SHARE = 0.9  # a glyph narrower than this share of the em is proportional already: left alone
TOLERANCE_UNITS = 4  # a trim smaller than this on both sides is not listed
BEGIN, END = u"# >>> FreeLab %s (made by FreeLab CJK Spacing)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
FEATURE_TITLES = {"palt": "Proportional Alternate Widths", "halt": "Alternate Half Widths"}
KINDS = ("hiragana", "small hiragana", "katakana", "small katakana", "punctuation")
KIND_LABELS = {"hiragana": "Hiragana", "small hiragana": "Small hiragana", "katakana": "Katakana",
               "small katakana": "Small katakana", "punctuation": "Punctuation and full-width forms",
               "hangul": "Hangul"}
SAMPLE = u"「カタカナ、ひらがな。」（テスト）"
SAMPLES = (("ja", u"Japanese", SAMPLE), ("ko", u"Korean", KOREAN_SAMPLE),
           ("zh-hans", u"Chinese (Simplified)", u"\N{LEFT CORNER BRACKET}\u7b80\u4f53\u4e2d\u6587\N{FULLWIDTH COMMA}"
                                              u"\u6807\u70b9\N{IDEOGRAPHIC FULL STOP}\N{RIGHT CORNER BRACKET}"
                                              u"\N{FULLWIDTH LEFT PARENTHESIS}\u6d4b\u8bd5\N{FULLWIDTH RIGHT PARENTHESIS}"),
           ("zh-hant", u"Chinese (Traditional)", u"\N{LEFT CORNER BRACKET}\u7e41\u9ad4\u4e2d\u6587\N{FULLWIDTH COMMA}"
                                                u"\u6a19\u9ede\N{IDEOGRAPHIC FULL STOP}\N{RIGHT CORNER BRACKET}"
                                                u"\N{FULLWIDTH LEFT PARENTHESIS}\u6e2c\u8a66\N{FULLWIDTH RIGHT PARENTHESIS}"))
# One sample per writing system the trims serve: kana and punctuation (Japanese), Hangul (Korean), and
# the hanzi forms of each Chinese standard, with the full-width punctuation palt trims. The one the
# font covers best is shown first; the field takes any text of one's own.


def best_sample(codes):
    """The index in SAMPLES of the sample the font covers most of (codes: the font's code points; its
    full-width punctuation counted too), the first on a tie."""
    def covered(text):
        return sum(1 for ch in text if not ch.isspace() and ord(ch) in codes)
    return max(range(len(SAMPLES)), key=lambda index: (covered(SAMPLES[index][2]), -index))
SMALL_KANA = set([0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3063, 0x3083, 0x3085, 0x3087, 0x308E, 0x3095, 0x3096,
                  0x30A1, 0x30A3, 0x30A5, 0x30A7, 0x30A9, 0x30C3, 0x30E3, 0x30E5, 0x30E7, 0x30EE, 0x30F5, 0x30F6])


def kind_of(code):
    """The kind of glyph a code point is, as palt groups them, or None."""
    if 0x3041 <= code <= 0x3096:
        return "small hiragana" if code in SMALL_KANA else "hiragana"
    if 0x30A1 <= code <= 0x30FA:
        return "small katakana" if code in SMALL_KANA else "katakana"
    if code in (0x30FC, 0x30FB, 0x309B, 0x309C):
        return "punctuation"
    if 0x3000 < code <= 0x303F or 0xFF01 <= code <= 0xFF60 or code in (0x2018, 0x2019, 0x201C, 0x201D):
        return "punctuation"
    if 0xAC00 <= code <= 0xD7A3:
        return "hangul"
    return None


VERTICAL_VOWELS = (0, 1, 2, 3, 4, 5, 6, 7, 20)  # a, ae, ya, yae, eo, e, yeo, ye, i: beside the initial
HORIZONTAL_VOWELS = (8, 12, 13, 17, 18)  # o, yo, u, yu, eu: under it; the others are both


def hangul_shape(code):
    """A Hangul syllable's shape: its vowel beside its initial ("vertical": 가), under it
    ("horizontal": 고), or both ("mixed": 과), with " final" for a final consonant (각)."""
    index = code - 0xAC00
    vowel, final = (index % 588) // 28, index % 28
    shape = "vertical" if vowel in VERTICAL_VOWELS else "horizontal" if vowel in HORIZONTAL_VOWELS else "mixed"
    return shape + (" final" if final else "")


def unichr_(code):
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def load_model(path=None, name=MODEL_FILE):
    """The CJK fonts' trims (palt_model.json beside this script), or another model there, or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), name)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class Trim(object):
    """A glyph's palt (and halt) adjustment: x placement and x advance, in font units."""

    def __init__(self, code, name, kind, advance, left, right):
        self.code, self.name, self.kind = code, name, kind
        self.advance, self.left, self.right = advance, left, right  # its ink's left and right edges
        self.palt = None  # (x placement, x advance) or None
        self.halt = None
        self.checked = True

    @property
    def char(self):
        return unichr_(self.code)

    def width_after(self):
        return self.advance + (self.palt[1] if self.palt else 0)


def suggest(trim, model, upm, tolerance=TOLERANCE_UNITS):
    """The trim's palt and halt adjustments, by the model: its ink kept, its sidebearings the corpus's
    (the mark's own where the corpus has it, else its kind's). A glyph that is not full width, or whose
    trim is within the tolerance, gets none."""
    if trim.advance < FULL_WIDTH_SHARE * upm or trim.right <= trim.left:
        return trim
    sides = model.get("palt", {}).get(u"U+%04X" % trim.code) or model.get("palt", {}).get(trim.kind)
    if sides:
        placement = int(round(sides[0] * upm - trim.left))
        advance = int(round((trim.right - trim.left) + (sides[0] + sides[1]) * upm - trim.advance))
        if abs(placement) >= tolerance or abs(advance + placement) >= tolerance:
            trim.palt = (placement, advance)
    half = model.get("halt", {}).get(u"U+%04X" % trim.code)
    if half and trim.kind == "punctuation":
        trim.halt = (int(round(half[0] * upm)), int(round(half[1] * upm)))
    return trim


def plan(glyphs, model, upm):
    """Trims for the font's glyphs: glyphs [(code, name, advance, ink left, ink right)]."""
    trims, seen = [], set()
    for code, name, advance, left, right in sorted(glyphs):
        kind = kind_of(code)
        if kind not in KINDS or name in seen:
            continue
        seen.add(name)
        trim = suggest(Trim(code, name, kind, advance, left, right), model, upm)
        if trim.palt or trim.halt:
            trims.append(trim)
    return trims


class HangulChange(object):
    """A Hangul syllable set anew: its outline moved by shift, its width made advance."""

    def __init__(self, code, name, shape, shift, advance, old_advance):
        self.code, self.name, self.shape = code, name, shape
        self.shift, self.advance, self.old_advance = shift, advance, old_advance


def half_up(value):
    """Rounded half up, as both Pythons do it alike (Python 3's round goes to the even number)."""
    import math
    return int(math.floor(value + 0.5))


def hangul_change(code, name, advance, left, right, mode, model, upm, width=None):
    """A syllable's change for a mode ("fixed": one width, its ink centered; "proportional": the
    corpus's sidebearings for its shape), or None when it stays within the tolerance."""
    shape = hangul_shape(code)
    ink = right - left
    if mode == "fixed":
        new_advance = half_up(width if width else (model.get("fixed_width") or 0.9) * upm)
        new_left = (new_advance - ink) / 2.0
    elif mode == "proportional":
        sides = model.get("proportional", {}).get(shape)
        if not sides:
            return None
        new_left = sides[0] * upm
        new_advance = ink + (sides[0] + sides[1]) * upm
    else:
        return None
    shift = half_up(new_left - left)
    new_advance = half_up(new_advance)
    if abs(shift) < HANGUL_TOLERANCE and abs(new_advance - advance) < HANGUL_TOLERANCE:
        return None
    return HangulChange(code, name, shape, shift, new_advance, advance)


def value_rule(name, value):
    return u"pos %s <%d 0 %d 0>;" % (name, value[0], value[1])


def feature_text(tag, old, rules):
    """A feature's code with FreeLab's block of rules in place before its closing line: an older
    FreeLab block taken out, the rest kept, FontLab's automatic block handed back ("#/> feature")."""
    begin, end = BEGIN % tag, END % tag
    kept, inside = [], False
    for line in (old or u"").splitlines():
        stripped = line.strip()
        if stripped == begin:
            inside = True
            continue
        if stripped == end:
            inside = False
            continue
        if inside:
            continue
        if stripped.startswith(FONTLAB_AUTO):
            line = line.replace(FONTLAB_AUTO, FONTLAB_HANDED, 1)
        kept.append(line)
    closing = None
    for index in range(len(kept) - 1, -1, -1):
        if re.match(r"^\s*}\s*%s\s*;" % re.escape(tag), kept[index]):
            closing = index
            break
    if closing is None:
        kept = [u"feature %s {" % tag, u"# %s" % FEATURE_TITLES.get(tag, tag), u""]
        closing = len(kept)
        kept.append(u"} %s;" % tag)
    block = [begin] + [u"  %s" % rule for rule in rules] + [end] if rules else []
    return u"\n".join(kept[:closing] + block + kept[closing:]) + u"\n"


def texts_for(trims, old_texts, palt_on=True, halt_on=True):
    """{tag: new code} for palt and halt from the checked trims."""
    chosen = [t for t in trims if t.checked]
    new = {}
    for tag, on, value in (("palt", palt_on, lambda t: t.palt), ("halt", halt_on, lambda t: t.halt)):
        rules = [value_rule(t.name, value(t)) for t in chosen if value(t)] if on else []
        old = old_texts.get(tag)
        if rules or (BEGIN % tag) in (old or u""):  # (an empty feature is not made; an old block is taken out)
            new[tag] = feature_text(tag, old, rules)
    return new


def block_of(tag, text):
    """FreeLab's block of a feature, alone in a feature of its own (for the parser's check), or None."""
    begin, end = BEGIN % tag, END % tag
    lines = (text or u"").splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == begin]
    ends = [i for i, line in enumerate(lines) if line.strip() == end]
    if not starts or not ends:
        return None
    return u"\n".join([u"feature %s {" % tag] + lines[starts[0] + 1:ends[0]] + [u"} %s;" % tag]) + u"\n"


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 32
PREVIEW_EM = 44  # pixels per em, the sample's previews


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: the dialogs' shared helpers."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "load_sibling") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(AUTO_KERNING_MODULE)
            module.__file__ = path
            sys.modules[AUTO_KERNING_MODULE] = module
            with open(path, "rb") as handle:
                source = handle.read()
            exec(compile(source, AUTO_KERNING_FILE, "exec", 0, True), module.__dict__)
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(AUTO_KERNING_MODULE, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[AUTO_KERNING_MODULE] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(AUTO_KERNING_MODULE, None)
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def counted(number, one, many=None):
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


HELP = u"""<b>FreeLab CJK Spacing</b><br>
Writes palt (proportional widths) and halt (half widths) for the font's full-width kana and
punctuation, so that applications can set Japanese proportionally. Nothing is written until you
click <i>Write the code</i>.<br><br>
<b>The list</b>: each full-width kana and punctuation mark, grouped, with its trim: how far its ink
moves (x placement) and how much its width changes (x advance), trimmed to its ink and the
sidebearings the open-licensed CJK fonts give theirs (about 0.07 em on each side for kana; each
punctuation mark its own: a comma keeps its left, an opening bracket its right). Checked glyphs are
written.<br>
<b>The previews</b>: the sample text set as it is, and with palt, in the font's glyphs. Type your own
sample.<br>
<b>Hangul</b> stays full width, as the corpus's Korean fonts leave it in palt: proportional Korean
comes from kerning (<i>Auto Kerning</i>, once it measures Hangul).<br>
<i>Restore suggestions</i> puts every check back as the list first came.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""


class CJKSpacingDialog(object):
    COLUMNS = ("Glyph", "Name", "Width", "palt", "Width after", "halt")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab CJK Spacing")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(ak.separator())
        self.log = ak.Log()
        row = QtGui.QHBoxLayout()
        self.palt_box = QtGui.QCheckBox("Proportional widths (palt)")
        self.palt_box.setChecked(True)
        self.palt_box.setWhatsThis(u"Writes palt: kana and punctuation trimmed to their ink and the corpus's sidebearings.")
        self.halt_box = QtGui.QCheckBox("Half-width punctuation (halt)")
        self.halt_box.setChecked(True)
        self.halt_box.setWhatsThis(u"Writes halt: each punctuation mark set in half the em, as the corpus's fonts set it.")
        row.addWidget(self.palt_box)
        row.addWidget(self.halt_box)
        row.addWidget(QtGui.QLabel(u"Hangul:"))
        self.hangul_box = QtGui.QComboBox()
        for _, label in HANGUL_MODES:
            self.hangul_box.addItem(label)
        self.hangul_box.setWhatsThis(u"How the font's Hangul syllables are set: as they are; all at one width (the font's "
                                     u"own where its syllables share one, else the corpus's 0.9 em), each one's ink "
                                     u"centered; or proportionally, each with the sidebearings the corpus's proportional "
                                     u"Korean fonts give its shape. Their outlines move and their widths change, in every "
                                     u"master.")
        row.addWidget(self.hangul_box)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.grid_lines(self.tree)
        self.tree.setWhatsThis(u"Each full-width kana and punctuation mark with its trims: palt's x placement and x "
                               u"advance, the width after, and halt's. Checked glyphs are written. Double-click one "
                               u"to see it in a <i>Glyph</i> window.")
        layout.addWidget(self.tree, 1)
        sample_row = QtGui.QHBoxLayout()
        sample_row.addWidget(QtGui.QLabel(u"Sample:"))
        self.sample_box = QtGui.QComboBox()
        for _, label, _ in SAMPLES:
            self.sample_box.addItem(label)
        self.sample_box.setWhatsThis(u"A sample per writing system (the one the font covers best is chosen as it is "
                                     u"read); the field beside it takes text of your own.")
        sample_row.addWidget(self.sample_box)
        self.sample = QtGui.QLineEdit(SAMPLE)
        self.sample.setWhatsThis(u"The text the previews set, as it is and with palt.")
        sample_row.addWidget(self.sample, 1)
        layout.addLayout(sample_row)
        self.previews = []
        for caption in (u"Now", u"With palt"):
            label = QtGui.QLabel()
            label.setProperty(ak.LEAVE_ALONE_PROP, True)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumHeight(int(PREVIEW_EM * 1.9))
            label.setToolTip(caption)
            layout.addWidget(label)
            self.previews.append((label, caption))
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every check back as the list first came.")
        self.write_button = QtGui.QPushButton("Write the code")
        self.write_button.setWhatsThis(u"Writes palt and halt for the checked glyphs, between FreeLab's marker lines; the "
                                       u"rest of each feature is kept. <i>Edit &gt; Undo</i> takes it back.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.write_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", dialog.close)
        self.palt_box.connect("toggled(bool)", lambda on: self.update_buttons())
        self.halt_box.connect("toggled(bool)", lambda on: self.update_buttons())
        self.sample.connect("textChanged(QString)", lambda text: self.draw_previews())
        self.sample_box.connect("activated(int)", lambda index: self.sample.setText(SAMPLES[index][2]))
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window(item))
        self.package = None
        self.trims, self.first_checks, self.texts, self.names = [], [], {}, []
        self.seen_history, self.busy, self.buttons_due = None, False, False
        self.model = load_model()
        self.hangul_model = load_model(name=HANGUL_MODEL_FILE)
        self.hangul_glyphs, self.hangul, self.hangul_checks, self.hangul_width = [], [], {}, None
        self.hangul_box.connect("currentIndexChanged(int)", lambda index: self.plan_hangul())
        ak.add_tools_button(dialog, "CJK Spacing", getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.history_timer = ak.watch_history(self)
        self.flagging = ak.flag_menu(self.tree, self, self.flag_names, self.row_names)

    def flag_names(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return []
        return self.row_names(items[0])

    def row_names(self, item):
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return [self.trims[index].name] if 0 <= index < len(self.trims) else []

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = workspace.currentPackage
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def run(self):
        QtCore, QtGui = _qt()
        ak = self.ak
        kept = dict((t.name, t.checked) for t in self.trims)
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.trims = []
        package = self.package = self.current_font()
        if package is None:
            self.status.setText(u"No font is open. Open one, then run <i>CJK Spacing</i> again.")
            self.update_buttons()
            return
        if not self.model:
            self.status.setText(u"")
            self.log.add(u"The corpus's trims (palt_model.json) are missing beside this script: reinstall FreeLab.", "error")
            return
        master = package.master
        glyphs, hangul = [], 0
        self.hangul_glyphs = []
        for fg in package.fgPackage.glyphs:
            code = fg.unicode
            kind = kind_of(code) if code else None
            if kind == "hangul":
                hangul += 1
                self.hangul_glyphs.append((code, fg.name))
            if kind not in KINDS:
                continue
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() <= 0:
                continue
            glyphs.append((code, fg.name, layer.advanceWidth, box.left(), box.right()))
        self.names = [g.name for g in package.fgPackage.glyphs]
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        self.trims = plan(glyphs, self.model, float(package.upm))
        for t in self.trims:
            t.checked = kept.get(t.name, t.checked)
        if u"%s" % self.sample.text in [text for _, _, text in SAMPLES]:  # (text of one's own is kept)
            index = best_sample(set(fg.unicode for fg in package.fgPackage.glyphs if fg.unicode))
            self.sample_box.setCurrentIndex(index)
            self.sample.setText(SAMPLES[index][2])
        self.hangul_box.setEnabled(bool(hangul))
        self.hangul = []
        if hangul and HANGUL_MODES[self.hangul_box.currentIndex][0] != "leave":
            self.measure_hangul()
        self.fill()
        self.first_checks = [True for _ in self.trims]
        b = ak.b
        full = sum(1 for g in glyphs if g[2] >= FULL_WIDTH_SHARE * package.upm)
        korean = (u" Its %s Hangul syllables: none of the corpus's Korean fonts kerns or trims Hangul; choose how to "
                  u"set their widths under %s." % (b(hangul), ak.i(u"Hangul:"))) if hangul else u""
        if not full:
            self.status.setText(u"%s, master %s, has no full-width kana or CJK punctuation: nothing to trim.%s" % (
                b(package.tfn), b(master), korean))
        else:
            self.status.setText(u"%s, master %s: %s of the %s full-width kana and punctuation %s a trim (palt: %s, halt: "
                                u"%s). Nothing is written until you click %s.%s" % (
                                    b(package.tfn), b(master), b(len(self.trims)), b(full),
                                    u"gets" if len(self.trims) == 1 else u"get",
                                    b(sum(1 for t in self.trims if t.palt)), b(sum(1 for t in self.trims if t.halt)),
                                    ak.i(self.write_button.text), korean))
        self.seen_history = ak.history_mark(package)
        self.draw_previews()

    # -- Hangul -----------------------------------------------------------------------

    def hangul_mode(self):
        return HANGUL_MODES[self.hangul_box.currentIndex][0]

    def measure_hangul(self, master=None):
        """The changes the chosen Hangul mode makes to the master's syllables (and the width it sets)."""
        QtCore, QtGui = _qt()
        package = self.package
        master = master or package.master
        mode = self.hangul_mode()
        upm = float(package.upm)
        measured = []
        for count, (code, name) in enumerate(self.hangul_glyphs):
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() > 0:
                measured.append((code, name, layer.advanceWidth, box.left(), box.right()))
            if count % 1000 == 999:
                self.status.setText(u"Measuring Hangul: %s of %s\N{HORIZONTAL ELLIPSIS}" % (
                    self.ak.b(count + 1), self.ak.b(len(self.hangul_glyphs))))
                QtGui.QApplication.processEvents()
        widths = sorted(set(int(round(m[2])) for m in measured))
        width = None
        if mode == "fixed":
            width = widths[len(widths) // 2] if 0 < len(widths) <= 3 else (self.hangul_model.get("fixed_width") or 0.9) * upm
        self.hangul_width = width
        changes = [hangul_change(code, name, advance, left, right, mode, self.hangul_model, upm, width)
                   for code, name, advance, left, right in measured]
        changes = [c for c in changes if c is not None]
        if master == package.master:
            self.hangul = changes
        return changes

    def plan_hangul(self):
        if self.package is None:
            return
        self.hangul = []
        if self.hangul_glyphs and self.hangul_mode() != "leave":
            self.measure_hangul()
            self.log.add(u"Hangul, %s: %s would change%s." % (
                self.ak.html(HANGUL_MODES[self.hangul_box.currentIndex][1].lower()),
                self.ak.b(counted(len(self.hangul), u"syllable")),
                u" (one width: %d units)" % self.hangul_width if self.hangul_width else u""))
        self.fill()
        self.draw_previews()

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        for kind in KINDS:
            members = [(index, t) for index, t in enumerate(self.trims) if t.kind == kind]
            if not members:
                continue
            top = QtGui.QTreeWidgetItem([u"%s (%d)" % (KIND_LABELS[kind], len(members))])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for index, t in members:
                item = QtGui.QTreeWidgetItem([t.char, t.name, u"%d" % t.advance,
                                              u"%+d, %+d" % t.palt if t.palt else u"\N{EN DASH}",
                                              u"%d" % t.width_after(),
                                              u"%+d, %+d" % t.halt if t.halt else u"\N{EN DASH}"])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if t.checked else QtCore.Qt.Unchecked)
                item.setToolTip(3, u"x placement, x advance: the ink moves by the first, the width changes by the second.")
                for column in range(2, len(self.COLUMNS)):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                icon = self.picture([(t.name, 0, 0)], ICON_SIZE)
                if icon is not None:
                    item.setIcon(0, QtGui.QIcon(icon))
                top.addChild(item)
            top.setExpanded(True)
        if self.hangul:
            top = QtGui.QTreeWidgetItem([u"Hangul (%s)" % counted(len(self.hangul), u"syllable")])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for number, (shape, label) in enumerate(HANGUL_SHAPES):
                members = [c for c in self.hangul if c.shape == shape]
                if not members:
                    continue
                middle = lambda values: sorted(values)[len(values) // 2]
                item = QtGui.QTreeWidgetItem([label, counted(len(members), u"syllable"),
                                              u"%d" % middle([c.old_advance for c in members]),
                                              u"moved %+d" % middle([c.shift for c in members]),
                                              u"%d" % middle([c.advance for c in members]), u""])
                item.setData(0, QtCore.Qt.UserRole, -10 - number)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if self.hangul_checks.get(shape, True) else QtCore.Qt.Unchecked)
                item.setToolTip(3, u"The median move of their outlines, and (next) their median width after.")
                for column in range(2, len(self.COLUMNS)):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                top.addChild(item)
            top.setExpanded(True)
        for column in range(len(self.COLUMNS)):
            self.tree.resizeColumnToContents(column)
        self.tree.blockSignals(False)
        self.update_buttons()

    def items(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.trims):
                self.trims[index].checked = item.checkState(0) == QtCore.Qt.Checked
            elif index <= -10:
                self.hangul_checks[HANGUL_SHAPES[-10 - index][0]] = item.checkState(0) == QtCore.Qt.Checked

    def hangul_chosen(self):
        return [c for c in self.hangul if self.hangul_checks.get(c.shape, True)]

    def check_all(self, on):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        for item in self.items():
            item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.changed()

    def changed(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        QtCore, QtGui = _qt()
        self.buttons_due = False
        ak = self.ak
        self.harvest()
        checks = [t.checked for t in self.trims]
        ak.enable(self.all_button, not all(checks) if checks else False)
        ak.enable(self.none_button, any(checks))
        ak.enable(self.restore_button, checks != self.first_checks)
        new = texts_for(self.trims, self.texts, self.palt_box.checked, self.halt_box.checked) if self.package else {}
        present = any((BEGIN % tag) in (self.texts.get(tag) or u"") for tag in ("palt", "halt"))
        changes = any(new[tag] != self.texts.get(tag) for tag in new)
        widths = bool(self.hangul_chosen())
        what = (u"Update the code" if present else u"Write the code") if changes else u""
        self.write_button.setText(u"%s and Hangul widths" % what if what and widths else what or
                                  (u"Set Hangul widths" if widths else u"Write the code"))
        ak.enable(self.write_button, changes or widths)
        self.draw_previews()

    def restore(self):
        for t, on in zip(self.trims, self.first_checks):
            t.checked = on
        self.fill()
        self.log.add(u"Checks restored as suggested.")

    def history_moved(self):
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()

    # -- pictures ------------------------------------------------------------------

    def picture(self, placed, size, width=None):
        """Glyphs [(name, x placement, x advance change)] set in a row, in the dialog's text color."""
        QtCore, QtGui = _qt()
        master = self.package.master
        layers = []
        for name, placement, advance in placed:
            glyph = self.package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            if layer is not None:
                layers.append((layer, placement, advance))
        if not layers:
            return None
        upm = float(self.package.upm)
        scale = size / upm
        total = sum(layer.advanceWidth + advance for layer, _, advance in layers)
        pixmap = QtGui.QPixmap(max(int(total * scale) + 8, 4), int(size * 1.25))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            x = 4.0
            for layer, placement, advance in layers:
                painter.save()
                painter.translate(x + placement * scale, size * 1.0)
                painter.scale(scale, -scale)
                painter.fillPath(self.ak.layer_path(layer), QtGui.QBrush(color))
                painter.restore()
                x += (layer.advanceWidth + advance) * scale
        finally:
            painter.end()
        return pixmap

    def draw_previews(self):
        if self.package is None:
            return
        by_code = dict((t.code, t) for t in self.trims if t.checked and t.palt)
        by_code.update((c.code, c) for c in self.hangul_chosen())
        names = dict((g.unicode, g.name) for g in self.package.fgPackage.glyphs if g.unicode)
        text = u"%s" % self.sample.text
        for (label, caption), trimmed in zip(self.previews, (False, True)):
            placed = []
            for ch in text:
                name = names.get(ord(ch))
                if name is None:
                    continue
                trim = by_code.get(ord(ch)) if trimmed else None
                if isinstance(trim, HangulChange):
                    placed.append((name, trim.shift, trim.advance - trim.old_advance))
                else:
                    placed.append((name, trim.palt[0], trim.palt[1]) if trim else (name, 0, 0))
            pixmap = self.picture(placed, PREVIEW_EM) if placed else None
            if pixmap is None:
                label.clear()
            else:
                label.setPixmap(pixmap)

    def show_in_glyph_window(self, item):
        QtCore, QtGui = _qt()
        index = int(item.data(0, QtCore.Qt.UserRole))
        if not 0 <= index < len(self.trims):
            return
        name = self.trims[index].name
        error = self.ak.show_in_glyph_window(self.fontlab, u"/%s/%s/%s" % (name, name, name))
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % self.ak.html(error), "error")

    # -- writing --------------------------------------------------------------------

    def write(self):
        if self.package is None:
            return
        self.harvest()
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed: here is this one's list. Nothing was written.", "warning")
            return
        features = package.fgPackage.features
        new = texts_for(self.trims, self.texts, self.palt_box.checked, self.halt_box.checked)
        fc = None
        try:
            fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
        except Exception:
            pass
        problems = []
        for tag, text in new.items():
            block = block_of(tag, text)
            problem = fc.check_code(block, self.names) if (fc is not None and block) else None
            if problem:
                problems.append(u"%s: %s" % (tag, problem))
        if problems:
            self.log.add(u"The code has problems, so nothing was written: %s" % self.ak.html(u"; ".join(problems)), "error")
            return
        written, error, syllables = [], None, 0
        shapes = set(c.shape for c in self.hangul_chosen())
        try:
            for tag in ("palt", "halt"):
                if tag in new and new[tag] != self.texts.get(tag):
                    features.set_feature(tag, new[tag])
                    written.append(tag)
            if shapes:
                syllables = self.write_hangul(package, shapes)
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.fontlab, package, u"FreeLab CJK Spacing")
        self.run()
        if written:
            them = u"it" if len(written) == 1 else u"them"
            self.log.add(u"Wrote %s. Compile the features in FontLab's <i>Features</i> panel to try %s; <i>Edit &gt; "
                         u"Undo</i> takes %s back." % (self.ak.b(u" and ".join(written)), them, them), "done")
        if syllables:
            self.log.add(u"Set %s in every master; the font's kerning of Hangul, if any, was set for the old widths. "
                         u"<i>Edit &gt; Undo</i> takes it back." % self.ak.b(counted(syllables, u"syllable width", u"syllable widths")),
                         "done")
        if not written and not syllables:
            self.log.add(u"Wrote nothing.")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")

    def write_hangul(self, package, shapes):
        """Each chosen syllable set anew in every master (each measured on its own): its shapes moved
        (components and outlines alike, by their transforms) and its width changed. How many changed."""
        QtCore, QtGui = _qt()
        done = 0
        for master in list(package.masters) or [package.master]:
            for change in self.measure_hangul(master):
                if change.shape not in shapes:
                    continue
                glyph = package.findName(change.name)
                layer = glyph.getLayerByName(master) if glyph is not None else None
                if layer is None:
                    continue
                for shape in layer.shapes:
                    t = shape.transform
                    shape.transform = QtGui.QTransform(t.m11(), t.m12(), t.m21(), t.m22(), t.dx() + change.shift, t.dy())
                layer.advanceWidth = change.advance
                try:
                    glyph.update()
                except Exception:
                    pass
                done += 1
        return done

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    held = getattr(sys, "_freelab_cjk_spacing", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = CJKSpacingDialog()
    except Exception as exc:
        print("FreeLab CJK Spacing: %s" % exc)
        return
    sys._freelab_cjk_spacing = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_cjk_spacing":
    main()
