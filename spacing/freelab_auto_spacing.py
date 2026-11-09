#FLM: Auto Spacing
# -*- coding: utf-8 -*-
"""FreeLab auto spacing, from FontLab's Scripts menu.

Suggests sidebearings for the drawn Latin letters of the current master, so that each sits beside the
font's straight references (H for capitals, n for lowercase) as the references sit beside each other,
measured by Auto Kerning's two methods (halfkern's and contour distance). Shows each glyph between
its references as it is and as suggested, and changes only the glyphs you leave checked. Glyphs
built from components follow the letters they are built on.

The references themselves (H, O, l, n, o, 0, 8) are the designer's: they set the spacing, as in
Walter Tracy's method, and are never changed.

Valid Python 2.7 (FontLab 7) and Python 3. The suggestions below the Qt line need no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
SPACING_REFERENCES = {"upper": u"H", "lower": u"n", "figure": u"0"}  # each kind's straight reference
FIXED = u"HOlno08"  # the references and tuning glyphs of the methods: never changed
TOLERANCE_UNITS = 6  # a side whose suggestion is closer than this to its sidebearing is left out
GROUPS = (("letters", "Letters"), ("figures", "Letters and figures"), ("all", "Letters, figures, and punctuation"))
PREVIEW_SIZE = 80  # pixels per em in the previews
SIDE_ALPHA = 110  # the references beside the glyph, dimmed


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the measuring comes from it."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "measure_pair") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(AUTO_KERNING_MODULE)
            module.__file__ = path
            sys.modules[AUTO_KERNING_MODULE] = module
            with open(path, "rb") as handle:  # open() takes a unicode path through the wide Windows API
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


def counted(number, one, many=None):
    """"1 pair", "2 pairs": a count with its noun in the right number."""
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


def round_units(value):
    return int(math.floor(value + 0.5))


# ---------------------------------------------------------------------------
# The suggestions
# ---------------------------------------------------------------------------

class Spacing(object):
    """One glyph's sidebearings now and the change suggested for each side (font units, None where
    neither method measures it)."""

    def __init__(self, char, name, kind, left, right, advance):
        self.char, self.name, self.kind = char, name, kind
        self.left, self.right, self.advance = left, right, advance  # sidebearings and width now
        self.left_change = self.right_change = None
        self.checked = True

    def changes(self, tolerance=0):
        """(left, right) changes, 0 for a side within the tolerance or unmeasured."""
        pick = lambda change: change if change is not None and abs(change) >= tolerance else 0
        return pick(self.left_change), pick(self.right_change)

    def listed(self, tolerance):
        return any(self.changes(tolerance))


def reference_for(kind_char, category):
    """A character's straight reference, by the kind of its base letter: H, n, or 0; n for
    punctuation (set among lowercase most)."""
    return SPACING_REFERENCES.get(category(kind_char), SPACING_REFERENCES["lower"])


def suggest_spacing(glyphs, measure, kind_of, category):
    """Each Spacing's suggested changes: its right side as the pair (glyph, reference) asks (the
    kerning that pair would want is what its right sidebearing lacks), its left side as (reference,
    glyph) asks. measure(left char, right char) gives that kerning in font units, or None;
    kind_of(char) the character whose kind sets its references (its base letter)."""
    for g in glyphs:
        reference = reference_for(kind_of(g.char), category)
        g.right_change = measure(g.char, reference)
        g.left_change = measure(reference, g.char)
    return glyphs


REFERENCE_MODEL_FILE = "reference_model.json"
UNSPACED_SHARE = 0.005  # a reference side closer to its ink than this share of the em counts as unspaced
UNSPACED_RATIO = 3.0  # and so does one side more than this many times the other


def load_reference_model(path=None):
    """How the corpus spaces the references (reference_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), REFERENCE_MODEL_FILE)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


def unspaced(left, right, upm):
    """Whether a reference's sidebearings look not spaced yet: a side at its ink, or lopsided."""
    low, high = min(left, right), max(left, right)
    return low < UNSPACED_SHARE * upm or high > UNSPACED_RATIO * max(low, 1.0)


def reference_changes(char, left, right, width, heights, model):
    """(left change, right change) bringing a reference to the corpus's spacing: its sidebearings as
    shares of its height (heights: {"H": cap height, "x": x-height}) or of its ink's width, as the
    model measures them; None where the model or the height is missing."""
    row = model.get("references", {}).get(char)
    if not row:
        return None
    base = width if row["by"] == "width" else heights.get(row["height_of"])
    if not base:
        return None
    return round_units(row["left"] * base - left), round_units(row["right"] * base - right)


def composite_moves(composites, changes):
    """How each composite follows the glyphs it is built on: {composite name: (shift of its other
    components, change of its width)}. composites maps a composite to its base component's glyph
    (the first component) and its other components' glyphs; changes maps a changed glyph to its
    (left, right) changes. A composite built on a changed glyph keeps its accents over it (they move
    by the base's left change) and takes the base's width change. One whose other components changed
    too (a ligature of two changed letters) is left out (None): it needs a look. A composite built on
    a composite that follows (an accent over e circumflex) follows it in turn."""
    changes = dict(changes)
    moves = {}
    while True:
        added = False
        for name, (base, others) in sorted(composites.items()):
            if name in moves or base not in changes:
                continue
            if any(other in changes for other in others):
                moves[name] = None
                continue
            left, right = changes[base]
            moves[name] = (left, left + right)
            changes[name] = (left, right)  # it moved as its base did: what is built on it follows
            added = True
        if not added:
            return moves


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def component_glyph(shape):
    """The glyph a component shape is built from, or None for a drawn shape."""
    try:
        if not shape.isComponent:
            return None
        data = shape.shapeData
        return data.componentGlyph or None
    except Exception:
        return None


def ink_sides(layer):
    """(left sidebearing, right sidebearing, width) of a layer, from its ink's bounds."""
    box = layer.boundingBox
    return box.left(), layer.advanceWidth - box.right(), layer.advanceWidth


HELP = u"""<b>FreeLab Auto Spacing</b><br>
Suggests sidebearings for the drawn Latin letters of this master, so that each sits beside its
straight reference (H for capitals, n for lowercase, 0 for figures) as the references sit beside each
other. Changes only the glyphs you leave checked.<br><br>
<b>How</b>: Auto Kerning's two methods measure the pair of the glyph and its reference on each side
(T beside H, H beside T); the kerning they would want there, averaged, is what that sidebearing
lacks. A side measured within the tolerance is left as it is.<br>
<b>The references are yours</b>: H, O, l, n, o, 0, and 8 set the spacing (as in Walter Tracy's
method: space H and n, then O and o, by eye) and are never changed. Glyphs built from components
are not spaced: they follow the letters they are built on, their accents kept over them.<br>
<b>After spacing</b>: the font's kerning was set for the old sidebearings. Run Auto Kerning again,
with <i>Include existing kerned pairs</i>, to see which pairs now want other values.<br>
<b>Preview</b>: the selected glyph between its references, as it is (left) and as suggested
(right). Click a reference beside it to open that pair in Auto Kerning; double-click a glyph's name
to open it in a Glyph window.<br>
<b>Restore suggestions</b> puts the checks back as the list first came.<br><br>
Click this help's ? button, then any control, for what it does."""


class AutoSpacingDialog(object):
    COLUMNS = ("Glyph", "Left now", "Left change", "Right now", "Right change", "Width")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = load_auto_kerning()
        main = self.ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Spacing")
        dialog.setWhatsThis(HELP)
        dialog.resize(720, 760)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = self.ak.rich(QtGui.QLabel(u""))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = self.ak.Log()
        self.seen_history, self.first_checks = None, {}
        row = QtGui.QHBoxLayout()
        self.group = QtGui.QComboBox()
        for _, label in GROUPS:
            self.group.addItem(label)
        self.group.setWhatsThis(u"Which glyphs to space. Figures are often tabular (one width for all): leave them "
                                u"out unless they are proportional.")
        row.addWidget(self.group)
        row.addWidget(QtGui.QLabel("List changes of at least"))
        self.tolerance = QtGui.QSpinBox()
        self.tolerance.setRange(1, 100)
        self.tolerance.setValue(TOLERANCE_UNITS)
        self.tolerance.setSuffix(" units")
        self.tolerance.setWhatsThis(u"A side is changed only when the suggestion differs from it by at least this "
                                    u"much; a glyph is listed when one of its sides is.")
        row.addWidget(self.tolerance)
        row.addStretch(1)
        self.analyze_button = QtGui.QPushButton("Analyze")
        self.analyze_button.setWhatsThis(u"Measures the current master's glyphs again.")
        row.addWidget(self.analyze_button)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setWhatsThis(u"Each glyph's sidebearings now and the change suggested for each side (below 0: "
                               u"closer to its neighbors), and its width after. Checked glyphs are changed. "
                               u"Double-click a glyph's name to open it in a Glyph window.")
        self.ak.grid_lines(self.tree)
        layout.addWidget(self.tree, 1)
        self.composites_note = QtGui.QLabel(u"")
        self.composites_note.setWordWrap(True)
        layout.addWidget(self.composites_note)
        previews = QtGui.QHBoxLayout()
        self.preview_now, self.preview_after = QtGui.QLabel(), QtGui.QLabel()
        for label, tip in ((self.preview_now, u"The glyph as it is"), (self.preview_after, u"As suggested")):
            label.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
            label.setToolTip(tip)
            label.setMinimumHeight(int(PREVIEW_SIZE * 1.6))
            label.setAlignment(QtCore.Qt.AlignCenter)
            previews.addWidget(label, 1)
        self.neighbors = [self.ak.ClickRegions(label, self.open_pair, u"Click to open this pair in Auto Kerning")
                          for label in (self.preview_now, self.preview_after)]
        layout.addLayout(previews)
        self.follow = QtGui.QCheckBox("Glyphs built from components follow the letters they are built on")
        self.follow.setChecked(True)
        self.follow.setWhatsThis(u"\N{LATIN SMALL LETTER E WITH ACUTE} built from e and an acute keeps its acute "
                                 u"over the e and takes e's change of width. Without it, its e moves under the "
                                 u"acute (the e's outline moves) and its width stays.")
        layout.addWidget(self.follow)
        layout.addWidget(self.log.view)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts the checks back as the list first came after the analysis.")
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.apply_button = QtGui.QPushButton("Space checked glyphs")
        self.apply_button.setWhatsThis(u"Changes the sidebearings of the checked glyphs in the current master (their "
                                       u"outlines move, their widths change), and the glyphs built on them.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button, self.glyph_window_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.analyze_button.connect("clicked()", self.run)
        self.group.connect("currentIndexChanged(int)", lambda index: self.run())
        self.tolerance.connect("valueChanged(int)", lambda value: self.fill())
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons_soon())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.apply_button.connect("clicked()", self.apply)
        self.close_button.connect("clicked()", dialog.close)
        self.tree.connect("itemSelectionChanged()", self.select)
        self.package = self.master = None
        self.spacings, self.listed, self.composites = [], [], {}
        self.busy = self.buttons_due = False
        self.reference_model = load_reference_model()
        self.unspaced_references = []
        self.history_timer = self.ak.watch_history(self)
        self.ak.plain_buttons(dialog)
        self.update_buttons()

    # -- the font ------------------------------------------------------------

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

    def characters(self):
        ak = self.ak
        group = GROUPS[self.group.currentIndex][0]
        letters = [ch for ch in ak.class_characters() if ch.isalpha()]
        chosen = letters + (list(ak.FIGURES) if group in ("figures", "all") else [])
        if group == "all":
            chosen += list(ak.PUNCTUATION)
        return chosen

    def run(self):
        if self.busy:
            return
        QtCore, QtGui = _qt()
        ak = self.ak
        self.busy = True
        self.tree.clear()
        self.spacings, self.listed = [], []
        self.apply_button.setEnabled(False)
        try:
            package = self.package = self.current_font()
            self.master = package.master if package is not None else None
            if package is None:
                self.status.setText(u"No font is open. Open one, then click %s." % self.ak.i("Analyze"))
                return
            self.status.setText(u"Measuring\N{HORIZONTAL ELLIPSIS}")
            QtGui.QApplication.processEvents()
            self.spacings, self.composites = self.measure(package, self.master)
        except Exception as exc:
            message = u"%s" % exc
            self.status.setText(u"")
            self.log.add(self.ak.html(message[:1].upper() + message[1:]), "error")
            return
        finally:
            self.busy = False
            self.seen_history = self.ak.history_mark(self.package)
        self.first_checks = dict((s.name, s.checked) for s in self.spacings)
        self.fill()
        if self.unspaced_references:
            self.log.add(u"This font's references look unspaced (a side at its ink, or one side three times the other): "
                         u"%s come first, unchecked, spaced as %s open-licensed families space theirs. If the font is not "
                         u"spaced yet, check them, space them, then click %s: the other glyphs are measured against them. "
                         u"A font tight on purpose leaves them unchecked." % (
                             self.ak.b(u", ".join(self.unspaced_references)),
                             self.ak.b(self.reference_model.get("families", 0)), self.ak.i(u"Analyze")), "warning")

    def measure(self, package, master):
        """(spacings, composites) of the master: the drawn glyphs' suggestions, and the composites
        {name: (base glyph, other components' glyphs)}."""
        ak = self.ak
        em = ak.EM_PIXELS
        glyphs = ak.FontLabGlyphs(package, master, em)
        wanted = self.characters()
        references = set(SPACING_REFERENCES.values()) | set(ak.TUNING) | set(u"HO08")
        found = [(ch, name) for ch, name in ak.font_glyphs(package, list(references) + wanted) if glyphs.add(name)]
        names = dict(found)
        for ch in ak.TUNING:
            if ch not in names:
                raise ValueError(u"this font has no \N{LEFT DOUBLE QUOTATION MARK}%s\N{RIGHT DOUBLE QUOTATION MARK}: "
                                 u"its spacing is what the others are measured by." % ch)
        image_of = lambda ch: glyphs.image(names[ch])
        tools = ak.make_bands(ak.Core(), image_of, names, em, glyphs.pad)
        reach = float(glyphs.pad)
        upm = glyphs.upm
        tighten, loosen = ak.DEFAULT_FACTORS["halfkern"]

        def measure(left, right):
            if left not in names or right not in names:
                return None
            kind_left, kind_right = ak.kind_character(left), ak.kind_character(right)
            if ak.pair_kinds(kind_left, kind_right) is None:
                return None
            halo, contour = ak.measure_pair(tools, kind_left, kind_right, image_of(left), image_of(right), em, reach)
            values = []
            if halo is not None:
                units = halo * upm / em
                values.append(units * (tighten if units < 0 else loosen))
            if contour is not None:
                values.append(contour * upm / em)
            return round_units(sum(values) / len(values)) if values else None

        spacings, composites = [], {}
        seen = set()
        for ch, name in found:
            if name in seen or ch in FIXED:
                continue
            seen.add(name)
            layer = package.findName(name).getLayerByName(master)
            parts = [component_glyph(shape) for shape in layer.shapes]
            if parts and all(parts):
                composites[name] = (parts[0], parts[1:])  # built from components: follows them
                continue
            if ch not in wanted:
                continue
            left, right, width = ink_sides(layer)
            spacings.append(Spacing(ch, name, ak.category(ak.kind_character(ch)), left, right, width))
        suggest_spacing(spacings, measure, ak.kind_character, ak.category)
        self.unspaced_references = self.space_references(package, master, names, spacings)
        # every composite of the font, not only those of the characters measured (alternates, ligatures)
        for fg in package.fgPackage.glyphs:
            name = fg.name
            if name in composites or name in seen:
                continue
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            parts = [component_glyph(shape) for shape in layer.shapes]
            if parts and all(parts):
                composites[name] = (parts[0], parts[1:])
        return spacings, composites

    def space_references(self, package, master, names, spacings):
        """Where the references (H and n) look unspaced, a row for each reference from the corpus's
        spacing, put first and unchecked: a font tight on purpose looks the same (its letters touch),
        so spacing them is the designer's choice. The references' characters, or []."""
        model = self.reference_model
        if not model:
            return []
        upm = float(package.upm)
        sides, heights = {}, {}
        for ch in (u"H", u"x", u"O", u"n", u"o", u"0"):
            name = names.get(ch) or (package.findUnicode(ord(ch)).name if package.findUnicode(ord(ch)) is not None else None)
            glyph = package.findName(name) if name else None
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() <= 0:
                continue
            left, right, width = ink_sides(layer)
            sides[ch] = (name, left, right, width)
            if ch in (u"H", u"x", u"n"):
                heights.setdefault(u"x" if ch == u"n" else ch, box.height())  # (n's height where there is no x)
        if not any(unspaced(sides[ch][1], sides[ch][2], upm) for ch in (u"H", u"n") if ch in sides):
            return []
        ak = self.ak
        found = []
        for ch in (u"H", u"O", u"n", u"o", u"0"):
            if ch not in sides:
                continue
            name, left, right, width = sides[ch]
            changes = reference_changes(ch, left, right, width - left - right, heights, model)  # (its ink's width)
            if changes is None:
                continue
            s = Spacing(ch, name, ak.category(ch), left, right, width)
            s.left_change, s.right_change = changes
            s.reference = True
            s.checked = False
            spacings.insert(len(found), s)
            found.append(ch)
        return found

    # -- the list ---------------------------------------------------------

    def fill(self):
        QtCore, QtGui = _qt()
        self.harvest()
        self.tree.clear()
        tolerance = self.tolerance.value
        self.listed = [s for s in self.spacings if s.listed(tolerance)]
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        sign = lambda value: u"%+d" % value if value else u"0"
        for index, s in enumerate(self.listed):
            left, right = s.changes(tolerance)
            item = QtGui.QTreeWidgetItem([u"%s  %s%s" % (s.char, s.name, u" (reference)" if getattr(s, "reference", False) else u""),
                                          u"%d" % round_units(s.left), sign(left),
                                          u"%d" % round_units(s.right), sign(right),
                                          u"%d" % round_units(s.advance + left + right)])
            item.setData(0, QtCore.Qt.UserRole, index)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if s.checked else QtCore.Qt.Unchecked)
            item.setFont(0, bold)
            for column in range(1, len(self.COLUMNS)):
                item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
            self.tree.addTopLevelItem(item)
        for column in range(len(self.COLUMNS)):
            self.tree.resizeColumnToContents(column)
        self.update_buttons()
        if self.package is not None:
            changes = dict((s.name, s.changes(tolerance)) for s in self.listed)
            moves = composite_moves(self.composites, changes)
            following = sum(1 for move in moves.values() if move is not None)
            left_out = sum(1 for m in moves.values() if m is None)
            self.composites_note.setText(u"%s built from components %s the listed letters%s." % (
                counted(following, u"glyph"), u"follows" if following == 1 else u"follow",
                u"; %d built on two of them %s left as %s" % (left_out, u"is" if left_out == 1 else u"are",
                                                             u"it is" if left_out == 1 else u"they are")
                if any(m is None for m in moves.values()) else u""))
            ak = self.ak
            self.status.setText(u"%s, master %s: %s of %s %s a side %s or more from the suggestion. Nothing changes "
                                u"until you click %s."
                                % (ak.b(self.package.tfn), ak.b(self.master), ak.b(len(self.listed)),
                                   ak.b(counted(len(self.spacings), u"drawn glyph")),
                                   u"has" if len(self.listed) == 1 else u"have", ak.b(counted(tolerance, u"unit")),
                                   ak.i(u"Space checked glyphs")))
        self.select()

    def harvest(self):
        QtCore, QtGui = _qt()
        for row in range(self.tree.topLevelItemCount):
            item = self.tree.topLevelItem(row)
            index = int(item.data(0, QtCore.Qt.UserRole))
            if index < len(self.listed):
                self.listed[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        QtCore, QtGui = _qt()
        for row in range(self.tree.topLevelItemCount):
            self.tree.topLevelItem(row).setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.update_buttons()

    def update_buttons_soon(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        QtCore, QtGui = _qt()
        self.buttons_due = False
        items = [self.tree.topLevelItem(row) for row in range(self.tree.topLevelItemCount)]
        some_on, some_off = self.ak.checks_of(items, lambda item: item.checkState(0) == QtCore.Qt.Checked)
        self.ak.enable(self.all_button, some_off)
        self.ak.enable(self.none_button, some_on)
        self.ak.enable(self.apply_button, some_on and not self.busy)
        self.harvest()
        self.ak.enable(self.restore_button, any(self.first_checks.get(s.name, s.checked) != s.checked for s in self.listed))
        self.ak.enable(self.glyph_window_button, self.selected() is not None)

    def restore(self):
        """The checks back as the list first came after the analysis."""
        for s in self.spacings:
            s.checked = self.first_checks.get(s.name, s.checked)
        self.fill()
        self.log.add(u"Checks restored as suggested.")

    def double_clicked(self, item, column):
        if column == 0:
            self.show_in_glyph_window()

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the glyphs measured again, as they are now."""
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): measured again.")
        self.run()

    def open_pair(self, key):
        """A reference beside the glyph clicked: that pair in Auto Kerning."""
        s = self.selected()
        if s is None:
            return
        side, reference = key
        error = self.ak.open_auto_kerning_at(*((reference, s.name) if side == "before" else (s.name, reference)))
        if error:
            self.log.add(u"Auto Kerning did not open: %s" % self.ak.html(error), "error")

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.listed[index] if index < len(self.listed) else None

    # -- the previews -----------------------------------------------------

    def select(self):
        s = self.selected()
        self.ak.enable(self.glyph_window_button, s is not None)
        if s is None or self.package is None:
            self.preview_now.clear()
            self.preview_after.clear()
            for regions in self.neighbors:
                regions.set([], (0, 0))
            return
        left, right = s.changes(self.tolerance.value)
        for label, regions, (l, r, text) in zip((self.preview_now, self.preview_after), self.neighbors,
                                                 ((0, 0, u"Now"), (left, right, u"Suggested"))):
            pixmap, spans = self.picture(s, l, r, text)
            label.setPixmap(pixmap)
            regions.set(spans, pixmap.size())

    def picture(self, s, left, right, label):
        """(picture, spans): the glyph between two of its references on each side, its sidebearings
        changed by left and right, in the dialog's text color, the references dimmed; the references'
        spans across the picture, (left, right, (side, name)), to be clicked."""
        QtCore, QtGui = _qt()
        ak = self.ak
        reference = reference_for(ak.kind_character(s.char), ak.category)
        reference_glyph = ak.font_glyphs(self.package, [reference])
        sequence = []
        for ch, name in reference_glyph * 2 + [(s.char, s.name)] + reference_glyph * 2:
            layer = self.package.findName(name).getLayerByName(self.master)
            if layer is not None:
                sequence.append((layer, ak.layer_path(layer), name == s.name))
        scale = float(PREVIEW_SIZE) / float(self.package.upm)
        width = int(sum(layer.advanceWidth for layer, _, _ in sequence) * scale + (left + right) * scale) + PREVIEW_SIZE
        height = int(PREVIEW_SIZE * 1.6)
        pixmap = QtGui.QPixmap(max(width, 10), height)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        spans, seen = [], False
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setPen(color)
            painter.drawText(QtCore.QRect(0, 0, width, int(PREVIEW_SIZE * 0.35)), int(QtCore.Qt.AlignCenter), label)
            x = float(PREVIEW_SIZE) / 2
            for layer, path, is_glyph in sequence:
                if is_glyph:
                    seen = True
                else:
                    spans.append((x, x + layer.advanceWidth * scale, ("after" if seen else "before", reference_glyph[0][1])))
                painter.save()
                painter.translate(x + (left * scale if is_glyph else 0), PREVIEW_SIZE * 1.3)
                painter.scale(scale, -scale)
                ink = QtGui.QColor(color)
                if not is_glyph:
                    ink.setAlpha(SIDE_ALPHA)
                painter.fillPath(path, QtGui.QBrush(ink))
                painter.restore()
                x += layer.advanceWidth * scale + ((left + right) * scale if is_glyph else 0)
        finally:
            painter.end()
        return pixmap, spans

    def show_in_glyph_window(self):
        s = self.selected()
        if s is None:
            return
        ak = self.ak
        reference = reference_for(ak.kind_character(s.char), ak.category)
        names = [name for _, name in ak.font_glyphs(self.package, [reference, u"o" if reference == u"n" else u"O"])]
        text = u"/space".join(u"/%s/%s/%s/%s/%s" % (r, r, s.name, r, r) for r in names) or u"/%s" % s.name
        error = ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % ak.html(error), "error")

    # -- changing the font ----------------------------------------------

    def apply(self):
        QtCore, QtGui = _qt()
        if self.busy or self.package is None:
            return
        self.harvest()
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(self.package) or current.master != self.master:
            self.run()
            self.log.add(u"The font or master changed since the analysis: here is this one's. Nothing was spaced.",
                         "warning")
            return
        tolerance = self.tolerance.value
        chosen = [s for s in self.listed if s.checked]
        if not chosen:
            return
        package, master = self.package, self.master
        changed, stale, error = {}, 0, None
        try:
            for s in chosen:
                glyph = package.findName(s.name)
                layer = glyph.getLayerByName(master) if glyph is not None else None
                if layer is None:
                    continue
                left_now, right_now, width_now = ink_sides(layer)
                if abs(left_now - s.left) > 0.5 or abs(right_now - s.right) > 0.5:
                    stale += 1  # edited since the analysis: measured again next time
                    continue
                left, right = s.changes(tolerance)
                if left:
                    shift = QtGui.QTransform()
                    shift.translate(left, 0)
                    layer.applyTransform(shift)  # the outline's nodes move (checked in FontLab 7.2)
                layer.advanceWidth = width_now + left + right
                changed[s.name] = (left, right)
                self.touched(glyph)
            moved = 0
            if self.follow.checked:
                for name, move in composite_moves(self.composites, changed).items():
                    if move is None:
                        continue
                    glyph = package.findName(name)
                    layer = glyph.getLayerByName(master) if glyph is not None else None
                    if layer is None:
                        continue
                    shift, width_change = move
                    for shape in layer.shapes[1:]:  # the accents: kept over the base, whose outline moved
                        transform = QtGui.QTransform(shape.transform)
                        transform.translate(shift, 0)
                        shape.transform = transform
                    layer.advanceWidth = layer.advanceWidth + width_change
                    self.touched(glyph)
                    moved += 1
        except Exception as exc:  # what was changed stays changed, and is reported
            error = exc
        self.after_writing()
        ak = self.ak
        self.log.add(u"Spaced %s%s. The kerning was set for the old spacing: run Auto Kerning again. Edit &gt; "
                     u"Undo (or the History panel) takes it back." % (
                         ak.b(counted(len(changed), u"glyph")),
                         u", and %s built on them followed" % ak.b(counted(moved, u"glyph")) if self.follow.checked and changed else u""),
                     "done" if changed else "info")
        if stale:
            self.log.add(u"%s had changed since the analysis and %s left as %s." % (
                ak.b(counted(stale, u"glyph")), u"was" if stale == 1 else u"were", u"it was" if stale == 1 else u"they were"),
                "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % ak.html(error), "error")
        self.run()

    def touched(self, glyph):
        try:
            glyph.update()
        except Exception:
            pass

    def after_writing(self, glyphs=()):
        self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Auto Spacing", glyphs)

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    held = getattr(sys, "_freelab_auto_spacing", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = AutoSpacingDialog()
    except Exception as exc:
        print("FreeLab Auto Spacing: %s" % exc)
        return
    sys._freelab_auto_spacing = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_auto_spacing":
    main()
