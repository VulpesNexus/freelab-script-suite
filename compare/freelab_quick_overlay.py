#FLM: Quick Overlay
# -*- coding: utf-8 -*-
"""FreeLab Quick Overlay, from FontLab's Scripts menu.

FontLab's Overlay Fonts works again on the whole font of the window it is opened on at each change, in a time
that grows about as the square of that font's glyph count: about 15 s for one color step on a font of 11,697
glyphs, 0.3 s on 1,374, whatever the fonts overlaid on it (measured on 2026-11-25). Quick Overlay copies the
glyphs to compare (typed: characters, or /names) from the current font into a new, unsaved font named in its
family, with the glyphs their components draw, opens it, and opens Overlay Fonts on it with the family's
fonts added: the fonts are compared on those glyphs, and each change shows at once.

Valid Python 2.7 (FontLab 7) and Python 3.
"""

from __future__ import absolute_import, division, print_function

import json
import os
import sys

TITLE = u"FreeLab Quick Overlay"
STYLE = u"Quick Overlay"  # the new font's style: its family is the current font's, so Add Family Members lists them
PROMPT = u"Glyphs to compare (characters, or /names):"
FLAG_PROMPT = u"Choose flagged glyphs:"  # (not "And the glyphs flagged": the field above may be empty, image 171)
NO_FLAG = u"None"
NO_FLAG_IN_FONT = u"None (no glyph of the font is flagged)"
# FontLab's flags (its Flag menu: a glyph's mark, a hue plus one; 0 for none), named as FreeLab's lists name them
FLAG_COLORS = ((u"Red", 1), (u"Green", 121), (u"Cyan", 181), (u"Blue", 241), (u"Magenta", 301))
DEFAULT_TEXT = u"AaGg123"  # (Overlay Fonts' own sample)
SETTINGS_FILE = "quick_overlay.json"
OVERLAY_ACTION = "actionOverlay_Fonts"
OVERLAY_WINDOW = "ActionOverlay"
ADD_FAMILY_BUTTON = "buttonAddFamily"
OPEN_WAIT_MS = 300  # after the new font's window opens, before Overlay Fonts is opened on it
FIND_EVERY_MS = 100  # how often the dialog is looked for once asked for
FIND_FOR_MS = 8000
SCRIPT_WINDOW_PROP = "mcpScriptWindow"  # FreeLab MCP's convention: the dialog is a script's, not FontLab's question
METRICS = ("ascender_value", "descender_value", "xHeight_value", "capsHeight_value", "lineGap_value")

try:
    TEXT_TYPE = unicode  # noqa: F821 (Python 2)
except NameError:
    TEXT_TYPE = str


# ---------------------------------------------------------------------------
# The glyphs asked for (pure: tested without FontLab)
# ---------------------------------------------------------------------------

def parse_glyph_text(text):
    """[("name", glyph name) or ("code", code point)] of a text: "/name" names a glyph (up to a space or the next
    slash), any other character stands for its code point (a surrogate pair, as Python 2's narrow strings hold
    characters past U+FFFF, read as one), and spaces separate. "//" stands for the slash itself."""
    found = []
    text = text or u""
    i = 0
    while i < len(text):
        char = text[i]
        if char == u"/":
            if text[i + 1:i + 2] == u"/":
                found.append(("code", 0x2F))
                i += 2
                continue
            j = i + 1
            while j < len(text) and text[j] not in u" /\t\n":
                j += 1
            if j > i + 1:
                found.append(("name", text[i + 1:j]))
            i = j
            continue
        if char in u" \t\n\r":
            i += 1
            continue
        code = ord(char)
        if 0xD800 <= code < 0xDC00 and i + 1 < len(text) and 0xDC00 <= ord(text[i + 1]) < 0xE000:
            code = 0x10000 + ((code - 0xD800) << 10) + (ord(text[i + 1]) - 0xDC00)
            i += 1
        found.append(("code", code))
        i += 1
    return found


def resolve(tokens, names, by_code):
    """(the font's glyph names asked for, in order, each once; what the font lacks, as typed) of parsed tokens:
    names is the font's set of glyph names, by_code {code point: glyph name}."""
    chosen, missing = [], []
    for kind, value in tokens:
        if kind == "name":
            name = value if value in names else None
            shown = u"/" + value
        else:
            name = by_code.get(value)
            shown = TEXT_TYPE(u"U+%04X" % value)
        if name is None:
            if shown not in missing:
                missing.append(shown)
        elif name not in chosen:
            chosen.append(name)
    return chosen, missing


def flag_name(mark):
    """A flag's name: FontLab's own colors by name, any other mark by its hue."""
    for name, value in FLAG_COLORS:
        if value == mark:
            return name
    return u"Hue %d" % ((int(mark) - 1) % 360)


def flag_choices(marks):
    """[(mark, label, count)] of the flags among a font's glyphs' marks (0: none, left out): FontLab's own colors
    in its menu's order, then other hues by hue; the label says how many glyphs ("Red (12 glyphs)")."""
    counts = {}
    for mark in marks:
        if mark:
            counts[mark] = counts.get(mark, 0) + 1
    order = dict((value, i) for i, (_, value) in enumerate(FLAG_COLORS))
    found = []
    for mark in sorted(counts, key=lambda m: (order.get(m, len(FLAG_COLORS)), m)):
        count = counts[mark]
        found.append((mark, u"%s (%d glyph%s)" % (flag_name(mark), count, u"" if count == 1 else u"s"), count))
    return found


def flagged(glyph_marks, mark):
    """The names of the glyphs flagged mark, in the font's order (none for 0)."""
    if not mark:
        return []
    return [name for name, value in glyph_marks if value == mark]


def with_components(chosen, components_of, limit=64):
    """The glyphs to copy: those chosen, and the glyphs their components draw (FontLab builds a component from
    its glyph, which must be in the font), each after the glyphs it draws from (component_order: a component
    made before its glyph was drawn stayed empty). components_of(name) gives a glyph's component glyph
    names, or [] (an unknown glyph). A loop is broken where it closes."""
    order, state = [], {}

    def visit(name, depth):
        if state.get(name) or depth > limit:
            return
        state[name] = 1
        for base in components_of(name) or ():
            visit(base, depth + 1)
        state[name] = 2
        order.append(name)

    for name in chosen:
        visit(name, 0)
    return order


# ---------------------------------------------------------------------------
# FontLab: every call in one place, each saying what it assumes ("Proven": run live in FontLab 7.2 by FreeLab,
# Family Audit's Assemble as masters among them, whose calls these are)
# ---------------------------------------------------------------------------

class QuickOverlayCalls(object):
    def __init__(self, fontlab):
        self.fontlab = fontlab
        self.held = []  # (glyphs and anchors Python made for the new font, held: Glyph Compose's new_glyph)

    def current_font(self):
        """Proven: flWorkspace.instance().currentPackage, the current font (a placeholder of one glyph or none
        when no font is open: None then)."""
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

    @staticmethod
    def master(package):
        """Proven: flPackage.master, the current master's name."""
        return u"%s" % package.master

    @staticmethod
    def family(package):
        """Proven: flPackage.tfn, FontLab's family name (Family Audit's names)."""
        return (u"%s" % (package.tfn or u"")).strip()

    @staticmethod
    def glyph_map(package):
        """({glyph names}, {code point: glyph name}). Proven: fgPackage.glyphs, each with name, unicodes, and
        unicode (Font Compare's glyph_codes)."""
        names, by_code = set(), {}
        for fg in package.fgPackage.glyphs:
            name = u"%s" % fg.name
            names.add(name)
            codes = []
            try:
                codes = [int(code) for code in (fg.unicodes or []) if code]
            except Exception:
                pass
            if not codes:
                try:
                    codes = [int(fg.unicode)] if fg.unicode else []
                except Exception:
                    codes = []
            for code in codes:
                by_code.setdefault(code, name)
        return names, by_code

    @staticmethod
    def glyph_marks(package):
        """[(glyph name, flag)] in the font's order. Live (2026-11-26): fgGlyph.mark reads the flag FontLab's Flag
        menu sets (flGlyph.mark, set to 1 and 241 on two glyphs, read back through fgPackage.glyphs; 3 ms for
        11,697 glyphs)."""
        found = []
        for fg in package.fgPackage.glyphs:
            try:
                mark = int(fg.mark)
            except Exception:
                mark = 0
            found.append((u"%s" % fg.name, mark))
        return found

    @staticmethod
    def layer(package, name, master):
        """Proven: flPackage.findName(name), then flGlyph.getLayerByName(master); None without either."""
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            return None
        layer = glyph.getLayerByName(master)
        if layer is None or getattr(layer, "isNull", False):
            return None
        return layer

    @staticmethod
    def components(layer):
        """[(glyph name, QTransform)] of a layer's components. Proven: flLayer.shapes, flShape.isComponent,
        shapeData.componentGlyph, transform."""
        parts = []
        for shape in list(layer.shapes):
            try:
                if bool(shape.isComponent):
                    parts.append((u"%s" % shape.shapeData.componentGlyph, shape.transform))
            except Exception:
                continue
        return parts

    @staticmethod
    def width(layer):
        """Proven: flLayer.advanceWidth."""
        return float(layer.advanceWidth)

    @staticmethod
    def metric(package, attribute):
        """Proven: flPackage's line metrics (ascender_value and the others), the current master's."""
        return float(getattr(package, attribute))

    def new_package(self):
        """Proven: fontlab.flPackage() with no argument makes a new, empty font, added to FontLab's workspace
        as the current one (never closed by a script: closing the current font crashed FontLab)."""
        return self.fontlab.flPackage()

    @staticmethod
    def masters(package):
        """Proven: flPackage.masters, the masters' names."""
        try:
            return [u"%s" % name for name in package.masters]
        except Exception:
            return []

    @staticmethod
    def rename_master(package, old, new):
        """Live (2026-11-24): flPackage.renameMaster(old name, new name)."""
        package.renameMaster(old, new)

    @staticmethod
    def set_upm(package, upm):
        """Live (2026-11-24): flPackage.setUpm(units, False) on a font with no glyphs yet."""
        package.setUpm(int(upm), False)

    @staticmethod
    def upm(package):
        """Proven: flPackage.upm."""
        return int(package.upm)

    @staticmethod
    def set_names(package, family, style):
        """Live (2026-11-24): flPackage.tfn, tsn, ffn, and psn, settable, set before the window opens (its tab is
        titled by them)."""
        package.tfn, package.tsn = family, style
        package.ffn = u"%s %s" % (family, style)
        package.psn = u"%s-%s" % (family.replace(u" ", u""), style.replace(u" ", u""))

    @staticmethod
    def set_info_family(package, family, style):
        """Live (2026-11-24): fgPackage.info's familyName is settable (styleName assumed alike)."""
        package.fgPackage.info.familyName = family
        try:
            package.fgPackage.info.styleName = style
        except Exception:
            pass

    def show_package(self, package):
        """Live (2026-11-24): fontlab.flItems.notifyPackageAdded(package) opens the new font's Font window, as a
        tab of the main window."""
        self.fontlab.flItems.notifyPackageAdded(package)

    def new_glyph(self, package, name):
        """Proven: fontlab.flGlyph(), its name set, flPackage.addGlyph() (a copy is added), then
        flPackage.findName(name). A new font comes with its .notdef: that one is used."""
        there = package.findName(name)
        if there is not None and not there.isNull:
            return there
        made = self.fontlab.flGlyph()
        made.name = name
        self.held.append(made)
        package.addGlyph(made)
        glyph = package.findName(name)
        return glyph if glyph is not None and not glyph.isNull else None

    @staticmethod
    def new_layer(glyph, master):
        """Proven: flGlyph.getLayerByName(master, True) makes the layer when the glyph has none there."""
        return glyph.getLayerByName(master, True)

    @staticmethod
    def init_layer(package, layer):
        """Live (2026-11-18): a new layer given its (empty) components at once: without it, setting the glyph's
        code point crashed FontLab."""
        layer.setGlyphComponents([], float(package.upm) / 2.0, package, False)

    def copy_contours(self, layer, target):
        """Proven: flShape.contours, flContour.clone(), fontlab.flShape(), addContours(contours, True), the
        shape's transform copied, flLayer.addShape. Nothing of the source is shared with the new font."""
        for shape in list(layer.shapes):
            try:
                if bool(shape.isComponent):
                    continue
            except Exception:
                pass
            contours = [c.clone() for c in shape.contours if c is not None]
            if not contours:
                continue
            new = self.fontlab.flShape()
            new.addContours(contours, True)
            try:
                new.transform = shape.transform
            except Exception:
                pass
            target.addShape(new)

    def copy_anchors(self, layer, target):
        """Proven: flLayer.anchors, fontlab.flPinPoint(QPointF), its name, flLayer.addAnchor (the pin held)."""
        from PythonQt import QtCore
        for anchor in list(layer.anchors):
            point = anchor.point
            pin = self.fontlab.flPinPoint(QtCore.QPointF(float(point.x()), float(point.y())))
            pin.name = u"%s" % anchor.name
            self.held.append(pin)
            target.addAnchor(pin)

    def set_components(self, package, target, parts, width):
        """Proven: fontlab.GlyphComponent(name) with its transform, then flLayer.setGlyphComponents(list, width,
        package, False)."""
        made = []
        for name, transform in parts:
            component = self.fontlab.GlyphComponent(name)
            component.transform = transform
            made.append(component)
        target.setGlyphComponents(made, float(width), package, False)

    @staticmethod
    def set_width(target, width):
        """Proven: flLayer.advanceWidth is settable."""
        target.advanceWidth = float(width)

    @staticmethod
    def find_glyph(package, name):
        """The font's glyph of that name, looked up now (a glyph kept while more were added crashed FontLab)."""
        glyph = package.findName(name)
        return glyph if glyph is not None and not glyph.isNull else None

    @staticmethod
    def set_codes(glyph, codes):
        """Live (2026-11-18): fgGlyph.unicode, then unicodes for more than one, on a glyph looked up again."""
        codes = [int(c) for c in codes]
        glyph.fgGlyph.unicode = codes[0]
        if len(codes) > 1:
            glyph.fgGlyph.unicodes = codes

    @staticmethod
    def codes_of(package, name):
        """The code points of the source's glyph (glyph_map's reading)."""
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            return []
        fg = glyph.fgGlyph
        try:
            codes = [int(code) for code in (fg.unicodes or []) if code]
        except Exception:
            codes = []
        if not codes:
            try:
                codes = [int(fg.unicode)] if fg.unicode else []
            except Exception:
                codes = []
        return codes

    @staticmethod
    def update_glyph(glyph):
        """Proven: flGlyph.update()."""
        glyph.update()

    @staticmethod
    def set_metric(package, attribute, value):
        """Live (2026-11-24): flPackage's line metrics are settable (the current master's)."""
        setattr(package, attribute, float(value))

    @staticmethod
    def rebuild_maps(package):
        """Proven: fgPackage.rebuildMaps()."""
        package.fgPackage.rebuildMaps()

    def glyphs_shown(self, package):
        """Proven: fontlab.flItems.notifyPackageContentUpdated(fgPackage.id)."""
        self.fontlab.flItems.notifyPackageContentUpdated(package.fgPackage.id)


class Failures(object):
    """What FontLab refused, by kind: each call tried, its failure noted, the copy going on."""

    def __init__(self):
        self.items = {}

    def attempt(self, kind, what, call, *args):
        try:
            return call(*args)
        except Exception:
            self.items.setdefault(kind, []).append(what)
            return None

    def lines(self):
        return [u"%s: %s." % (kind, u", ".join(TEXT_TYPE(w) for w in whats[:12]) + (u" and %d more" % (len(whats) - 12)
                                                                                    if len(whats) > 12 else u""))
                for kind, whats in sorted(self.items.items())]


def build_overlay_font(calls, source, names):
    """A new font holding the glyphs names (in order: with_components), copied from source's current master,
    named in its family with STYLE, its window opened. Returns (the new font, [what FontLab refused])."""
    failed = Failures()
    master = calls.master(source)
    family = calls.family(source)
    package = calls.new_package()
    if package is None:
        raise RuntimeError(u"FontLab made no new font")
    failed.attempt(u"Units per em not set", u"the font", calls.set_upm, package, calls.upm(source))
    made = calls.masters(package)
    if made and made[0] != master:
        failed.attempt(u"Master not named", master, calls.rename_master, package, made[0], master)
    failed.attempt(u"Font not named", family, calls.set_names, package, family, STYLE)
    failed.attempt(u"Font not named", family, calls.set_info_family, package, family, STYLE)
    failed.attempt(u"Font window not opened", u"the new font", calls.show_package, package)
    master = (calls.masters(package) or [master])[0]
    for name in names:
        glyph = failed.attempt(u"Glyphs not added", name, calls.new_glyph, package, name)
        if glyph is None:
            continue
        layer = failed.attempt(u"Layers not made", name, calls.new_layer, glyph, master)
        if layer is not None:
            failed.attempt(u"Layers not made", name, calls.init_layer, package, layer)
    source_master = calls.master(source)
    for name in names:  # (in component order: a glyph after those its components draw)
        layer = failed.attempt(u"Not read", name, calls.layer, source, name, source_master)
        glyph = failed.attempt(u"Glyphs not found again", name, calls.find_glyph, package, name)
        if layer is None or glyph is None:
            continue
        target = failed.attempt(u"Layers not made", name, calls.new_layer, glyph, master)
        if target is None:
            continue
        width = failed.attempt(u"Widths not read", name, calls.width, layer) or 0.0
        parts = failed.attempt(u"Components not read", name, calls.components, layer) or []
        if parts:
            failed.attempt(u"Components not made", name, calls.set_components, package, target, parts, width)
        failed.attempt(u"Outlines not copied", name, calls.copy_contours, layer, target)
        failed.attempt(u"Anchors not copied", name, calls.copy_anchors, layer, target)
        failed.attempt(u"Widths not set", name, calls.set_width, target, width)
    for name in names:
        glyph = failed.attempt(u"Glyphs not found again", name, calls.find_glyph, package, name)
        if glyph is None:
            continue
        codes = failed.attempt(u"Code points not read", name, calls.codes_of, source, name) or []
        if codes:
            glyph = failed.attempt(u"Glyphs not found again", name, calls.find_glyph, package, name)
            if glyph is not None:
                failed.attempt(u"Code points not set", name, calls.set_codes, glyph, codes)
        glyph = failed.attempt(u"Glyphs not found again", name, calls.find_glyph, package, name)
        if glyph is not None:
            failed.attempt(u"Glyphs not redrawn", name, calls.update_glyph, glyph)
    for attribute in METRICS:
        value = failed.attempt(u"Line metrics not read", attribute, calls.metric, source, attribute)
        if value is not None:
            failed.attempt(u"Line metrics not set", attribute, calls.set_metric, package, attribute, value)
    failed.attempt(u"Code points not mapped", u"the new font", calls.rebuild_maps, package)
    failed.attempt(u"Font window not told of the glyphs", u"the new font", calls.glyphs_shown, package)
    return package, failed.lines()


# ---------------------------------------------------------------------------
# Settings, the dialog, and Overlay Fonts opened on the new font
# ---------------------------------------------------------------------------

def settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "FreeLab", SETTINGS_FILE)


def load_settings():
    """{"text": the glyphs typed last, "flag": the flag chosen last (0: none)}."""
    try:
        with open(settings_path(), "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        if isinstance(data, dict):
            text = data.get("text")  # (left empty on purpose: a flag's glyphs alone)
            return {"text": DEFAULT_TEXT if text is None else text, "flag": int(data.get("flag") or 0)}
    except Exception:
        pass
    return {"text": DEFAULT_TEXT, "flag": 0}


def save_settings(data):
    path = settings_path()
    try:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        temp = path + ".tmp"
        with open(temp, "wb") as handle:
            handle.write(json.dumps(data).encode("utf-8"))
        if os.path.exists(path):
            os.remove(path)
        os.rename(temp, path)
    except Exception:
        pass  # (remembered next time, or not: the overlay is made either way)


def main_window():
    try:
        from PythonQt.QtGui import QApplication
        for widget in QApplication.topLevelWidgets():
            if widget.objectName == "MainWindow":
                return widget
    except Exception:
        pass
    return None


def held():
    """Objects kept for the session: dialogs and timers PythonQt would delete with their last reference."""
    found = getattr(sys, "_freelab_quick_overlay_held", None)
    if found is None:
        found = sys._freelab_quick_overlay_held = []
    return found


def flag_icon(mark):
    """A small square of a flag's color, as FontLab shows the flag (Auto Kerning's flag_color)."""
    from PythonQt.QtGui import QColor, QPixmap, QIcon
    color = QColor()
    color.setHsv((int(mark) - 1) % 360, 190, 235)
    pixmap = QPixmap(12, 12)
    pixmap.fill(color)
    return QIcon(pixmap)


def note_text(family):
    """The dialog's note, in rich text as the other tools say what they work on (the owner's image 171): the font's
    family in bold, FontLab's command in italics."""
    name = (family or u"").replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")
    return (u"<i>Overlay Fonts</i> opened on a new font holding only these glyphs of %s, with its family's fonts "
            u"added: each change then shows at once (on the whole font, FontLab works again on every glyph)."
            % (u"<b>%s</b>" % name if name else u"the current font"))


def can_overlay(text, flag_index):
    """Whether there is anything to overlay: glyphs typed, or a flag chosen (its index in the dropdown, past None)."""
    return bool((text or u"").strip()) or flag_index > 0


def ask_glyphs(family, choices):
    """(the glyphs typed, the flag chosen or 0) of the dialog, or None on Cancel. choices: flag_choices of the
    font's glyphs."""
    from PythonQt.QtGui import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox
    from PythonQt.QtCore import Qt
    settings = load_settings()
    main = main_window()
    dialog = QDialog(main) if main is not None else QDialog()
    held().append(dialog)
    dialog.setWindowTitle(TITLE)
    dialog.setProperty(SCRIPT_WINDOW_PROP, True)
    flags = int(dialog.windowFlags()) if callable(dialog.windowFlags) else int(dialog.windowFlags)
    dialog.setWindowFlags(Qt.WindowFlags(flags & ~int(Qt.WindowContextHelpButtonHint)))
    layout = QVBoxLayout(dialog)
    note = QLabel(note_text(family))
    note.setTextFormat(Qt.RichText)
    note.setWordWrap(True)
    layout.addWidget(note)
    layout.addWidget(QLabel(PROMPT))
    field = QLineEdit(settings.get("text", DEFAULT_TEXT))
    field.selectAll()
    layout.addWidget(field)
    layout.addWidget(QLabel(FLAG_PROMPT))
    combo = QComboBox()
    combo.addItem(NO_FLAG if choices else NO_FLAG_IN_FONT, 0)
    for mark, label, _count in choices:
        combo.addItem(flag_icon(mark), label, mark)
    combo.setEnabled(bool(choices))
    remembered = int(settings.get("flag") or 0)
    for index, (mark, _label, _count) in enumerate(choices):
        if mark == remembered:
            combo.setCurrentIndex(index + 1)
    layout.addWidget(combo)
    row = QHBoxLayout()
    row.addStretch(1)
    ok, cancel = QPushButton(u"Overlay"), QPushButton(u"Cancel")
    ok.setDefault(True)
    row.addWidget(ok)
    row.addWidget(cancel)
    layout.addLayout(row)
    ok.connect("clicked()", dialog.accept)
    cancel.connect("clicked()", dialog.reject)

    def update_ok(*_args):  # (nothing typed and no flag chosen: nothing to overlay, the owner's image 172)
        try:
            index = combo.currentIndex() if callable(combo.currentIndex) else combo.currentIndex
            ok.setEnabled(can_overlay(u"%s" % field.text, index))
        except Exception:
            pass  # a slot must not raise

    held().append(update_ok)  # (held: PythonQt drops a slot no Python object holds)
    field.connect("textChanged(QString)", update_ok)
    combo.connect("currentIndexChanged(int)", update_ok)
    update_ok()
    dialog.setMinimumWidth(420)
    accepted = dialog.exec_()
    text = u"%s" % field.text
    index = combo.currentIndex() if callable(combo.currentIndex) else combo.currentIndex
    mark = choices[index - 1][0] if 0 < index <= len(choices) else 0
    try:
        dialog.hide()
    except Exception:
        pass
    return (text, mark) if accepted else None


def open_overlay_with_family():
    """Overlay Fonts opened on the current font (FontLab's own command, triggered once this script has returned:
    its dialog is modal), then its Add Family Members pressed once the dialog shows. Never raises."""
    from PythonQt import QtCore, QtGui
    main = main_window()
    if main is None:
        return False
    actions = [a for a in main.findChildren(QtGui.QAction)
               if a.objectName == OVERLAY_ACTION and u"%s" % (a.text or u"") != u"Overlay"]
    if not actions:
        actions = [a for a in main.findChildren(QtGui.QAction) if a.objectName == OVERLAY_ACTION]
    if not actions:
        return False
    action = actions[0]
    state = {"waited": 0, "pressed": False}
    timer = QtCore.QTimer(main)
    held().append(timer)

    def look():
        """A timer's slot, run inside the dialog's own event loop: nothing may escape it."""
        try:
            state["waited"] += FIND_EVERY_MS
            for widget in QtGui.QApplication.topLevelWidgets():
                if widget.isVisible() and widget.metaObject().className() == OVERLAY_WINDOW:
                    for button in widget.findChildren(QtGui.QAbstractButton):
                        if button.objectName == ADD_FAMILY_BUTTON and not state["pressed"]:
                            state["pressed"] = True
                            button.click()
                    timer.stop()
                    return
            if state["waited"] >= FIND_FOR_MS:
                timer.stop()
        except Exception:
            try:
                timer.stop()
            except Exception:
                pass

    timer.setInterval(FIND_EVERY_MS)
    timer.connect("timeout()", look)
    held().append(look)
    timer.start()
    QtCore.QTimer.singleShot(OPEN_WAIT_MS, action.trigger)
    return True


def say(line):
    """A line in FontLab's Output panel (escaped to ASCII where Python 2's console refuses a character)."""
    try:
        print(line)
    except Exception:
        print(line.encode("ascii", "backslashreplace").decode("ascii") if isinstance(line, TEXT_TYPE) else repr(line))


def run():
    import fontlab
    calls = QuickOverlayCalls(fontlab)
    source = calls.current_font()
    if source is None:
        say(u"FreeLab Quick Overlay: no font is open.")
        return None
    family = calls.family(source)
    marks = calls.glyph_marks(source)
    answer = ask_glyphs(family, flag_choices([mark for _, mark in marks]))
    if answer is None:
        return None
    text, mark = answer
    save_settings({"text": text, "flag": mark})
    names, by_code = calls.glyph_map(source)
    chosen, missing = resolve(parse_glyph_text(text), names, by_code)
    for name in flagged(marks, mark):
        if name not in chosen:
            chosen.append(name)
    if not chosen:
        say(u"FreeLab Quick Overlay: %s has none of the glyphs asked for (%s)." % (family, u", ".join(missing)))
        return None
    master = calls.master(source)

    def components_of(name):
        layer = calls.layer(source, name, master)
        return [base for base, _ in calls.components(layer)] if layer is not None else []

    order = [name for name in with_components(chosen, components_of) if name in names]
    package, refused = build_overlay_font(calls, source, order)
    lines = [u"FreeLab Quick Overlay: %d glyph%s of %s (%s) in a new font, %s %s." % (
        len(order), u"" if len(order) == 1 else u"s", family, master, family, STYLE)]
    if missing:
        lines.append(u"Not in the font: %s." % u", ".join(missing))
    lines.extend(refused)
    for line in lines:
        say(line)
    if not open_overlay_with_family():
        say(u"FreeLab Quick Overlay: Overlay Fonts could not be opened (FontLab's command was not found).")
    return package


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_quick_overlay":
    run()
