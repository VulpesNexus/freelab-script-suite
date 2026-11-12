# -*- coding: utf-8 -*-
"""FreeLab Feature Code's Stylistic alternates tab (loaded by freelab_feature_code.py; not a script of its own).

Suggested alternates: the characters fonts give stylistic alternates most (features/alternates_model.json,
from features/train/alternates.py: which characters the corpus's open-licensed fonts vary in ssXX, cvXX,
and salt), those the font has listed with how many families vary them and the alternates it has already.
A checked one gets a starting copy, X.ss01 (the next free set), its outlines as they are, to redraw; the
Forms tab writes its stylistic set.

Variants that take turns: for a handwriting font, each letter in scope gets copies X.alt1, X.alt2... made
by a few smooth changes of the whole glyph (a slight rotation, uneven scaling, a slant, a baseline shift),
at one of three strengths, from a seed (the same seed makes the same variants). No node jitter: moving
nodes one by one breaks smooth curves and reads as noise, not handwriting. The first tab's Alternates
that take turns then writes the calt code that cycles them (X.alt1 is the form its convention reads).
Valid Python 2.7 (FontLab) and 3 (tests).
"""
from __future__ import absolute_import, division, print_function

import json
import os
import random
import unicodedata
import zlib

MODEL_FILE = "alternates_model.json"
SUGGESTED_MAX = 40  # characters listed, the most varied first
# (key, label, rotation in degrees, scale change, slant in degrees, baseline shift in em): the most each
# change may reach; each variant draws its own within them. Subtle stays within what readers take for
# one hand (about the ranges tools for handwriting fonts use at their lowest settings).
STRENGTHS = (("subtle", u"Subtle", 0.8, 0.02, 1.0, 0.005),
             ("moderate", u"Moderate", 1.5, 0.04, 2.0, 0.01),
             ("bold", u"Bold", 3.0, 0.07, 4.0, 0.02))
SCOPES = (("lower", u"Lowercase letters"), ("upper", u"Capitals"), ("both", u"Capitals and lowercase"))
SET_SUFFIX = u".ss%02d"
VARIANT_SUFFIX = u".alt%d"


def load_model(path=None):
    """The model's [(character, families varying it)], families read, families with alternates; or None."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILE)
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        return [(c, int(n)) for c, n in data["characters"]], data.get("families"), data.get("with_alternates")
    except Exception:
        return None


def suggestions(model_rows, cmap, names, most=SUGGESTED_MAX):
    """[(character, glyph, families, [its alternates in the font])] for the model's characters the font
    has (cmap: {code point: glyph}), the most varied first. Its alternates: glyphs named after it with
    a stylistic suffix (a.ss01, a.cv01, a.salt, a.alt, a.alt1)."""
    found = []
    for ch, families in model_rows:
        glyph = cmap.get(ord(ch))
        if not glyph:
            continue
        prefix = glyph + u"."
        alternates = sorted(n for n in names if n.startswith(prefix) and stylistic_suffix(n[len(prefix):]))
        found.append((ch, glyph, families, alternates))
        if len(found) >= most:
            break
    return found


def stylistic_suffix(suffix):
    head = suffix.split(u".")[0]
    return head.startswith((u"ss", u"cv", u"salt", u"alt")) or head.isdigit()


def package_id(package):
    """FontLab's own number for an open font (fgPackage.id), the same through every Python wrapper of it
    (two reads of currentPackage give different wrappers); None where it cannot be read. Two unsaved fonts
    of one name share a font_key, not this."""
    try:
        return package.fgPackage.id
    except Exception:
        return None


def free_set_name(glyph, names):
    """glyph's next stylistic set name the font does not have: a.ss01, else a.ss02..."""
    for number in range(1, 21):
        name = glyph + SET_SUFFIX % number
        if name not in names:
            return name
    return None


def in_scope(ch, scope):
    """Whether a letter is in a variants' scope (lowercase, capitals, or both)."""
    kind = unicodedata.category(ch)
    if not kind.startswith(u"L"):
        return False
    if scope == "lower":
        return kind == u"Ll"
    if scope == "upper":
        return kind in (u"Lu", u"Lt")
    return kind in (u"Ll", u"Lu", u"Lt")


def strength_of(key):
    return next((row for row in STRENGTHS if row[0] == key), STRENGTHS[0])


def variant_params(glyph, number, strength, seed):
    """(rotation degrees, x scale, y scale, slant degrees, baseline shift in em) of glyph's variant number:
    each drawn within the strength's reach, from the seed (the same seed, the same variants; Python 2 and
    3 alike: the generator is seeded with a CRC of the text, not Python's hash)."""
    _, _, rotation, scale, slant, rise = strength_of(strength)
    key = (u"%s|%s|%d|%s" % (seed, glyph, number, strength)).encode("utf-8")
    rng = random.Random(zlib.crc32(key) & 0xFFFFFFFF)
    pick = lambda reach: rng.uniform(-reach, reach)
    return (round(pick(rotation), 3), round(1.0 + pick(scale), 4), round(1.0 + pick(scale), 4),
            round(pick(slant), 3), round(pick(rise), 5))


def variant_matrix(params, cx, cy, upm):
    """The affine matrix (a, b, c, d, e, f: x' = a x + c y + e, y' = b x + d y + f) of a variant's
    changes about the ink's center (cx, cy): scaled, slanted, rotated, then raised."""
    import math
    rotation, sx, sy, slant, rise = params
    r = math.radians(rotation)
    k = math.tan(math.radians(slant))
    cos, sin = math.cos(r), math.sin(r)
    # scale, then slant (x += k y), then rotate
    a0, b0, c0, d0 = sx, 0.0, k * sy, sy
    a, b = cos * a0 - sin * b0, sin * a0 + cos * b0
    c, d = cos * c0 - sin * d0, sin * c0 + cos * d0
    e = cx - (a * cx + c * cy)
    f = cy - (b * cx + d * cy) + rise * upm
    return a, b, c, d, e, f


# ---------------------------------------------------------------------------
# The tab (Qt and FontLab: in FontLab only)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


class AlternatesPage(object):
    """The tab's widgets and actions; owner: the Feature Code dialog (package, master, log, ak, run)."""

    def __init__(self, owner):
        QtCore, QtGui = _qt()
        self.owner, self.ak = owner, owner.ak
        self.model = load_model()
        self.widget = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(owner.heading(QtGui, u"Suggested alternates"))
        self.note = QtGui.QLabel(u"")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels([u"Character", u"Glyph", u"Fonts varying it", u"Its alternates in the font"])
        self.tree.setRootIsDecorated(False)
        self.tree.setWhatsThis(u"The characters fonts give stylistic alternates most (counted in the open-licensed "
                               u"fonts of FreeLab's corpus: in how many families an ssXX, cvXX, or salt feature varies "
                               u"it), those this font has, with the alternates it has already. Check one, then "
                               u"<i>Make starting copies</i>: it gets a copy to redraw, named for a stylistic set.")
        self.ak.grid_lines(self.tree)
        layout.addWidget(self.tree, 2)
        row = QtGui.QHBoxLayout()
        row.addStretch(1)
        self.copy_button = QtGui.QPushButton(u"Make starting copies")
        self.copy_button.setWhatsThis(u"Adds a copy of each checked character's glyph, named for the next free stylistic "
                                      u"set (a.ss01), its outlines as they are, to redraw as the alternate. The "
                                      u"<i>Forms</i> tab then writes the set's feature. <i>Edit &gt; Undo</i> takes it back.")
        row.addWidget(self.copy_button)
        layout.addLayout(row)
        layout.addWidget(owner.heading(QtGui, u"Variants that take turns (handwriting)"))
        hint = QtGui.QLabel(u"Copies of each letter changed a little as a whole (a slight rotation, uneven scaling, a "
                            u"slant, a baseline shift), named X.alt1, X.alt2...: the first tab's <i>Alternates that take "
                            u"turns</i> then cycles them, so repeated letters differ. The same seed makes the same "
                            u"variants.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        settings = QtGui.QHBoxLayout()
        settings.addWidget(QtGui.QLabel(u"Letters"))
        self.scope_box = QtGui.QComboBox()
        for _, label in SCOPES:
            self.scope_box.addItem(label)
        self.scope_box.setCurrentIndex(2)
        settings.addWidget(self.scope_box)
        settings.addWidget(QtGui.QLabel(u"Variants each"))
        self.count_box = QtGui.QSpinBox()
        self.count_box.setRange(1, 4)
        self.count_box.setValue(2)
        settings.addWidget(self.count_box)
        settings.addWidget(QtGui.QLabel(u"Strength"))
        self.strength_box = QtGui.QComboBox()
        for _, label, rotation, scale, slant, rise in STRENGTHS:
            self.strength_box.addItem(label)
        self.strength_box.setWhatsThis(u"How far each change may go: <i>Subtle</i> (within 0.8\N{DEGREE SIGN} of "
                                       u"rotation, 2% of scale, 1\N{DEGREE SIGN} of slant, 0.5% of the em of baseline), "
                                       u"<i>Moderate</i> (1.5\N{DEGREE SIGN}, 4%, 2\N{DEGREE SIGN}, 1%), or <i>Bold</i> "
                                       u"(3\N{DEGREE SIGN}, 7%, 4\N{DEGREE SIGN}, 2%), to experiment with.")
        settings.addWidget(self.strength_box)
        settings.addWidget(QtGui.QLabel(u"Seed"))
        self.seed_box = QtGui.QSpinBox()
        self.seed_box.setRange(1, 9999)
        self.seed_box.setValue(1)
        settings.addWidget(self.seed_box)
        settings.addStretch(1)
        self.build_button = QtGui.QPushButton(u"Build variants")
        self.build_button.setWhatsThis(u"Adds the variants of every letter in scope the font has (X.alt1 and on; one it "
                                       u"has already is left as it is). <i>Edit &gt; Undo</i> takes them back.")
        settings.addWidget(self.build_button)
        layout.addLayout(settings)
        self.preview = QtGui.QLabel()
        self.preview.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setMinimumHeight(110)
        self.preview.setWhatsThis(u"The selected letter (else a) and its variants as they would be built.")
        layout.addWidget(self.preview, 1)
        self.slots = [lambda *args: self.make_copies(), lambda *args: self.build_variants(),
                      lambda *args: (self.draw_preview(), self.update_buttons()),
                      lambda *args: self.update_buttons()]
        self.copy_button.connect("clicked()", self.slots[0])
        self.build_button.connect("clicked()", self.slots[1])
        for box in (self.scope_box, self.strength_box):
            box.connect("currentIndexChanged(int)", self.slots[2])
        for box in (self.count_box, self.seed_box):
            box.connect("valueChanged(int)", self.slots[2])
        self.tree.connect("itemSelectionChanged()", self.slots[2])
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", self.slots[3])

    # -- reading ----------------------------------------------------------

    def font_maps(self):
        package = self.owner.package
        cmap, names = {}, set()
        for g in package.fgPackage.glyphs:
            names.add(u"%s" % g.name)
            if g.unicode:
                cmap.setdefault(g.unicode, u"%s" % g.name)
        return cmap, names

    def fill(self):
        """The suggestions for the font open now."""
        QtCore, QtGui = _qt()
        self.tree.clear()
        package = self.owner.package
        if package is None or self.model is None:
            self.note.setText(u"" if package is None else
                              u"The model (%s) is missing beside the script: reinstall FreeLab." % MODEL_FILE)
            self.update_buttons()
            return
        rows, families, varied = self.model
        cmap, names = self.font_maps()
        found = suggestions(rows, cmap, names)
        self.note.setText(u"The characters fonts vary most in their stylistic sets (of %s open-licensed families, %s "
                          u"have alternates), those this font has. Check one, then click %s." % (
                              self.ak.b(families), self.ak.b(varied), self.ak.i(u"Make starting copies")))
        for ch, glyph, count, alternates in found:
            item = QtGui.QTreeWidgetItem([ch, glyph, u"%d" % count, u" ".join(alternates) or u"\N{EN DASH}"])
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Unchecked)
            item.setData(0, QtCore.Qt.UserRole, glyph)
            item.setTextAlignment(2, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
            self.tree.addTopLevelItem(item)
        for column in range(3):
            self.tree.resizeColumnToContents(column)
        self.draw_preview()
        self.update_buttons()

    def checked_glyphs(self):
        QtCore = _qt()[0]
        found = []
        for row in range(self.tree.topLevelItemCount):
            item = self.tree.topLevelItem(row)
            if item.checkState(0) == QtCore.Qt.Checked:
                found.append(u"%s" % item.data(0, QtCore.Qt.UserRole))
        return found

    def strength(self):
        return STRENGTHS[max(0, self.strength_box.currentIndex)][0]

    def scope(self):
        return SCOPES[max(0, self.scope_box.currentIndex)][0]

    # -- making -----------------------------------------------------------

    def copy_glyph(self, source, name, matrix_of=None):
        """A new glyph name, made of copies of source's shapes in every master that draws it (each changed by
        matrix_of(that master's layer), when given), with source's widths; the new glyph, or None (the current
        master does not draw it: nothing is added)."""
        QtCore, QtGui = _qt()
        package, fontlab = self.owner.package, self.owner.fontlab
        glyph = package.findName(source)
        if glyph is None:
            return None
        try:
            masters = list(package.masters) or [package.master]
        except Exception:
            masters = [package.master]
        if package.master not in masters:
            masters.append(package.master)
        layers = []
        for master in masters:
            layer = glyph.getLayerByName(master)
            if layer is not None and len(layer.shapes):
                layers.append((master, layer))
        if package.master not in [master for master, _ in layers]:
            return None
        new = fontlab.flGlyph()
        new.name = name
        package.addGlyph(new)
        made = package.findName(name)
        for master, layer in layers:
            target = made.getLayerByName(master, True)
            for shape in layer.shapes:
                target.addShape(shape.cloneTopLevel() if hasattr(shape, "cloneTopLevel") else shape.clone())
            matrix = matrix_of(layer) if matrix_of is not None else None
            if matrix is not None:
                a, b, c, d, e, f = matrix
                transform = QtGui.QTransform(a, b, c, d, e, f)
                for shape in target.shapes:
                    shape.applyTransform(transform)
            target.advanceWidth = layer.advanceWidth
        return made

    def same_font(self):
        """True when the font open now is the one the tab was filled from; else the dialog is filled again
        for it, with a note, and nothing is made."""
        owner = self.owner
        current = owner.current_font()
        if current is not None and owner.package is not None and \
                self.ak.font_key(current) == self.ak.font_key(owner.package) and \
                package_id(current) == package_id(owner.package):
            return True
        owner.run()
        owner.log.add(u"The font changed since the list was made: here is this one's. Nothing was made.", "warning")
        return False

    def update_buttons(self):
        """Each button grayed out when it has nothing to do."""
        try:
            has_font = self.owner.package is not None
            self.ak.enable(self.copy_button, has_font and bool(self.checked_glyphs()))
            self.ak.enable(self.build_button, has_font and bool(self.letters_in_scope()[0]))
        except Exception:
            pass

    def make_copies(self):
        package = self.owner.package
        chosen = self.checked_glyphs()
        if package is None or not chosen or not self.same_font():
            return
        cmap, names = self.font_maps()
        made, touched, error = [], [], None
        try:
            for glyph in chosen:
                name = free_set_name(glyph, names)
                if name is None:
                    continue
                new = self.copy_glyph(glyph, name)
                if new is not None:
                    names.add(name)
                    made.append(name)
                    touched.append(new)
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.owner.fontlab, package, u"FreeLab Feature Code", touched)
        if made:
            self.owner.log.add(u"Made %s to redraw: %s. Once drawn, the <i>Forms</i> tab writes their sets; "
                               u"<i>Edit &gt; Undo</i> takes them back." % (
                                   self.ak.b(self.ak.counted(len(made), u"starting copy", u"starting copies")),
                                   self.ak.html(u" ".join(made))), "done")
        if error is not None:
            self.owner.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        self.owner.run()

    def letters_in_scope(self):
        cmap, names = self.font_maps()
        scope = self.scope()
        found = []
        for code, glyph in sorted(cmap.items()):
            try:
                ch = unichr(code)  # noqa: F821 (Python 2, FontLab's)
            except NameError:
                ch = chr(code)
            except ValueError:  # (FontLab's Python is a narrow build: no unichr above U+FFFF; no letters there in scope)
                continue
            if u"." not in glyph and in_scope(ch, scope):
                found.append(glyph)
        return found, names

    def build_variants(self):
        package = self.owner.package
        if package is None or not self.same_font():
            return
        package = self.owner.package
        glyphs, names = self.letters_in_scope()
        count, strength, seed = self.count_box.value, self.strength(), self.seed_box.value
        upm = float(package.upm)
        made, kept, touched, error = 0, [], [], None
        try:
            for glyph in glyphs:
                layer = package.findName(glyph).getLayerByName(self.owner.package.master)
                if layer is None or not len(layer.shapes):
                    continue
                for number in range(1, count + 1):
                    name = glyph + VARIANT_SUFFIX % number
                    if name in names:
                        kept.append(name)
                        continue
                    params = variant_params(glyph, number, strength, seed)

                    def matrix_of(master_layer, params=params):  # (around each master's own center)
                        center = master_layer.boundingBox.center()
                        return variant_matrix(params, center.x(), center.y(), upm)
                    new = self.copy_glyph(glyph, name, matrix_of)
                    if new is not None:
                        names.add(name)
                        touched.append(new)
                        made += 1
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.owner.fontlab, package, u"FreeLab Feature Code", touched)
        if made:
            self.owner.log.add(u"Built %s (%s, seed %d). Check them under <i>Alternates that take turns</i> on the first "
                               u"tab, then write the code; <i>Edit &gt; Undo</i> takes them back." % (
                                   self.ak.b(self.ak.counted(made, u"variant")), strength, seed), "done")
        if kept:
            self.owner.log.add(u"%s the font has already, left as they are." % self.ak.b(
                self.ak.counted(len(kept), u"variant")), "warning")
        if error is not None:
            self.owner.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        self.owner.run()

    # -- preview ----------------------------------------------------------

    def draw_preview(self):
        """The selected letter (else a, else the first in scope) and its variants, in the dialog's colors."""
        QtCore, QtGui = _qt()
        try:
            package = self.owner.package
            if package is None:
                self.preview.clear()
                return
            items = self.tree.selectedItems()
            glyph = u"%s" % items[0].data(0, QtCore.Qt.UserRole) if items else None
            if glyph is None:
                letters, _ = self.letters_in_scope()
                glyph = u"a" if u"a" in letters else (letters[0] if letters else None)
            layer = package.findName(glyph).getLayerByName(self.owner.package.master) if glyph else None
            if layer is None:
                self.preview.clear()
                return
            path = self.ak.layer_path(layer)
            box = layer.boundingBox
            cx, cy = box.center().x(), box.center().y()
            upm = float(package.upm)
            shapes = [path]
            for number in range(1, self.count_box.value + 1):
                a, b, c, d, e, f = variant_matrix(variant_params(glyph, number, self.strength(), self.seed_box.value),
                                                  cx, cy, upm)
                shapes.append(QtGui.QTransform(a, b, c, d, e, f).map(path))
            height = 100
            scale = height / upm
            advance = float(layer.advanceWidth) or upm * 0.6
            width = int(advance * scale * len(shapes) + 40)
            pixmap = QtGui.QPixmap(max(width, 10), height + 30)
            pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            color = self.owner.dialog.palette.color(QtGui.QPalette.WindowText)
            painter = QtGui.QPainter(pixmap)
            try:
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                for index, shape in enumerate(shapes):
                    painter.save()
                    painter.translate(20 + index * advance * scale, height * 0.85)
                    painter.scale(scale, -scale)
                    painter.fillPath(shape, QtGui.QBrush(color))
                    painter.restore()
            finally:
                painter.end()
            self.preview.setPixmap(pixmap)
        except Exception:
            self.preview.clear()
