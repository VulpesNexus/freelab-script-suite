#FLM: Kerning Check
# -*- coding: utf-8 -*-
"""FreeLab kerning check, from FontLab's Scripts menu (or Auto Kerning's Check kerning button).

Three lists for the current font, each to review before anything changes:

- Collisions: kerned pairs whose ink comes closer than a minimum distance at the kerning FontLab
  applies (classes included), each with the value that keeps the minimum, written as a pair of its
  own when checked.
- Cleanup: entries that change nothing (equal to what the pair would get without them, or overridden
  for every pair they cover), entries naming a class or glyph that is gone, and tiny values.
- Masters: entries kerned in some masters only, entries whose sign flips between masters (an
  instance between them may collide), and classes whose members differ between masters.

Valid Python 2.7 (FontLab 7) and Python 3. The checks below the Qt line need no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import sys

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
MIN_DISTANCE_SHARE = 0.02  # a kerned pair's ink closer than this share of the em is listed (contour distance's floor)
TINY_UNITS = 5  # entries smaller than this (font units) are listed for cleanup, unchecked
SIGN_TOLERANCE = 10  # a value counts as tightening or loosening beyond this many units, between masters
PROGRESS_EVERY = 2000  # pairs between two looks at the event loop while checking
COLLISION_MODES = (("relative", "closer than their base letter beside the same glyph"), ("absolute", "closer than that, absolutely"))


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the measuring and the
    kerning model come from it."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "FontKerning") and getattr(held, "_freelab_stamp", None) == stamp:
        return held  # (loaded again after a reinstall)
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


def round_units(value):
    return int(math.floor(value + 0.5))


# ---------------------------------------------------------------------------
# The checks (kerning is a FontKerning of freelab_auto_kerning, or one like it)
# ---------------------------------------------------------------------------

class Collision(object):
    """A kerned glyph pair whose ink comes within gap units, and the value that sets it apart as wanted
    (reference: the class's first pair and its gap, when compared with it)."""

    def __init__(self, left, right, value, gap, fix, entry, reference=None, reference_gap=None):
        self.left, self.right = left, right
        self.value, self.gap, self.fix = value, gap, fix
        self.entry = entry  # what sets the value now (an entry of the kerning), or None
        self.reference, self.reference_gap = reference, reference_gap
        # the glyph compared with its key glyph: the one whose accent or part comes too close
        self.variant = None if reference is None else (left if reference[0] != left else right)

    def pair(self):
        return self.left, self.right


def key_glyph(kerning, name):
    """The glyph a class is named after (class T: T), or else its first member: its key glyph."""
    members = kerning.members.get(name, [])
    return name if name in members else (members[0] if members else None)


def references(kerning, entry, left, right, variant_of):
    """The pairs a class's value was set by eye on, for one of its glyph pairs: on each class side
    where the pair's glyph is a variant of the class's key glyph (Tcaron of T), the key glyph beside
    the same partner (Tcaron o: T o)."""
    found = []
    for at, (name, is_class) in enumerate(entry):
        member = (left, right)[at]
        if not is_class:
            continue
        key = key_glyph(kerning, name)
        if key is None or key == member or not variant_of(member, key):
            continue
        found.append((key, right) if at == 0 else (left, key))
    return found


def find_collisions(kerning, closest_at, minimum, relative=True, progress=None, variant_of=None):
    """Kerned pairs (tighter than zero) whose ink comes too close, closest first. closest_at(left,
    right, value) gives the narrowest gap between the pair's ink at that kerning, in font units
    (below zero where they overlap), or None where it cannot tell.

    relative: a pair is listed when a class's value brings its ink within minimum units, and at least
    minimum units closer than its key glyph beside the same partner (references): an accent or a part
    the key glyph lacks (Tcaron o against T o). Its fix sets it as far apart as that pair. Fonts whose letters touch or overlap on
    purpose (joined crossbars) are judged by their own pairs this way, and members unlike their key
    glyph (a class of math signs) are not compared. variant_of(glyph, key) says whether a glyph is
    built on another (by default: its name starts with the other's).
    Not relative: a pair is listed when its ink comes closer than minimum units; its fix keeps them.
    progress(done, total) may return False to stop."""
    variant_of = variant_of or (lambda glyph, key: glyph.startswith(key))
    plain = kerning.plain or {}
    tight = sorted((pair, round_units(value)) for pair, value in plain.items() if value is not None and value < 0)
    found = []
    for done, ((left, right), value) in enumerate(tight):
        if progress is not None and done % PROGRESS_EVERY == 0 and progress(done, len(tight)) is False:
            return None
        entry = kerning.resolving(left, right)
        reference = reference_gap = None
        if relative:
            if entry is None:
                continue
            pairs = references(kerning, entry, left, right, variant_of)
            if not pairs:
                continue  # a pair of its own (the designer's), a key glyph, or a member unlike its key glyph
            gap = closest_at(left, right, value)
            if gap is None:
                continue
            gaps = [(closest_at(a, b, value), (a, b)) for a, b in pairs]
            gaps = [(g, pair) for g, pair in gaps if g is not None]
            if not gaps:
                continue
            reference_gap, reference = max(gaps)
            wanted, limit = reference_gap, min(reference_gap - minimum, minimum)  # closer, and close
        else:
            wanted = limit = minimum
            gap = closest_at(left, right, value)
        if gap is None or gap >= limit:
            continue
        fix = min(0, value + int(math.ceil(wanted - gap)))
        found.append(Collision(left, right, value, gap, fix, entry, reference, reference_gap))
    if relative:
        found.sort(key=lambda c: (c.gap - c.reference_gap, c.left, c.right))
    else:
        found.sort(key=lambda c: (c.gap, c.left, c.right))
    return found


class Cleanup(object):
    """An entry worth removing (checked: it changes nothing, or names what is gone) or looking at."""

    def __init__(self, entry, value, kind, reason, checked):
        self.entry, self.value, self.kind, self.reason, self.checked = entry, value, kind, reason, checked


CLEANUP_KINDS = (("missing", "Names what is gone"), ("overridden", "Overridden everywhere"),
                 ("redundant", "Changes nothing"), ("tiny", "Tiny value"))


def find_cleanup(kerning, glyph_exists, tiny=TINY_UNITS):
    """Entries that change nothing, name a class with no members or a glyph the font lacks, or are
    smaller than tiny units; the first two kinds checked for removal. The entries are judged most
    specific first, each as if the ones found before it were removed already: an exception equal to
    its class's value is listed, and the class's entry it then falls back on is not."""
    describe = kerning.describe
    found = []
    present = set(kerning.entries)
    specific_first = sorted(kerning.entries, key=lambda e: (int(e[0][1]) + int(e[1][1]), int(e[0][1]), e))
    for entry in specific_first:
        value = round_units(kerning.values.get(entry) or 0)
        missing = [name for name, is_class in entry
                   if (is_class and not kerning.members.get(name)) or (not is_class and not glyph_exists(name))]
        if missing:
            found.append(Cleanup(entry, value, "missing", u"%s: no such %s" % (
                u", ".join(missing), u"class or glyph" if len(missing) > 1 else
                (u"class (or it has no members)" if dict(entry).get(missing[0]) else u"glyph")), True))
            present.discard(entry)
            continue
        governed, fallbacks = 0, set()
        for left, right in kerning.pairs(entry):
            candidates = kerning.candidates(left, right)
            if entry not in candidates:  # (a glyph in two classes on a side: its other class is the one read)
                governed += 1
                fallbacks.add(None)
                continue
            index = candidates.index(entry)
            if any(other in present for other in candidates[:index]):
                continue  # a more specific entry sets this pair
            governed += 1
            below = next((other for other in candidates[index + 1:] if other in present), None)
            fallbacks.add(round_units(kerning.values.get(below) or 0) if below is not None else 0)
        if not governed or fallbacks == set([value]):
            present.discard(entry)  # listed for removal: the entries judged after it go without it
        if not governed:
            found.append(Cleanup(entry, value, "overridden", u"every pair it covers has a value of its own", True))
        elif fallbacks == set([value]):
            below_text = u"the class pair's value" if value else u"no kerning"
            found.append(Cleanup(entry, value, "redundant", u"its pairs get %s (%d) without it" % (below_text, value), True))
        elif value and abs(value) < tiny:
            found.append(Cleanup(entry, value, "tiny", u"smaller than %d units" % tiny, False))
    order = dict((kind, index) for index, (kind, _) in enumerate(CLEANUP_KINDS))
    found.sort(key=lambda c: (order[c.kind], describe(c.entry)))
    return found


class MasterDifference(object):
    def __init__(self, kind, subject, values, reason):
        self.kind, self.subject, self.values, self.reason = kind, subject, values, reason  # values: [(master, text)]


def compare_masters(kernings, tolerance=SIGN_TOLERANCE):
    """[(master, kerning)] compared: entries kerned in some masters only, entries tightening in one
    master and loosening in another, and classes whose members differ."""
    masters = [master for master, _ in kernings]
    found = []
    if len(kernings) < 2:
        return found
    entries = set()
    for _, kerning in kernings:
        entries |= set(kerning.entries)
    describe = kernings[0][1].describe
    for entry in sorted(entries):
        values = [(master, round_units(k.values[entry]) if entry in k.entries else None) for master, k in kernings]
        present = [master for master, value in values if value is not None]
        known = [value for _, value in values if value is not None]
        shown = [(master, u"\N{EN DASH}" if value is None else u"%d" % value) for master, value in values]
        if len(present) < len(masters):
            missing = [master for master in masters if master not in present]
            found.append(MasterDifference("missing", describe(entry), shown, u"not kerned in %s" % u", ".join(missing)))
        elif min(known) < -tolerance and max(known) > tolerance:
            found.append(MasterDifference("sign", describe(entry), shown,
                                          u"tightens in one master, loosens in another: an instance between them "
                                          u"may collide"))
    names = set()
    for _, kerning in kernings:
        names |= set(kerning.classes)
    for name in sorted(names):
        sets = [(master, frozenset(k.members.get(name, [])) if name in k.classes else None) for master, k in kernings]
        if len(set(members for _, members in sets)) > 1:
            shown = [(master, u"\N{EN DASH}" if members is None else u" ".join(sorted(members))) for master, members in sets]
            found.append(MasterDifference("class", u"class %s" % name, shown, u"its members differ between masters"))
    return found


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def glyph_text(package, name):
    """A glyph's character when it has one, else its name."""
    try:
        glyph = package.findName(name)
        code = glyph.fgGlyph.unicode if glyph is not None else None  # (flGlyph has no unicode of its own)
        if code:
            try:
                return unichr(code)  # noqa: F821 (Python 2)
            except NameError:
                return chr(code)
    except Exception:
        pass
    return name


def is_variant(name, key, char_of):
    """Whether glyph name is a variant of glyph key (an accented or barred letter, an alternate): its
    name without suffix is the key's, or, a letter itself, it is built on the key's letter or named
    after it. Ligatures (f_f_t) and other characters (the won sign, after w) are not.
    char_of(glyph name) gives its character, or None."""
    import unicodedata
    stem = name.split(u".")[0]
    if stem == key:
        return True  # an alternate (j.2 of j)
    if u"_" in stem or not stem.startswith(key):
        return False
    char, key_char = char_of(name), char_of(key)
    if char is None:
        return True  # unencoded, named after the key (Tcaron.sc of T: as named)
    if not unicodedata.category(char).startswith(u"L"):
        return False
    decomposed = unicodedata.normalize("NFKD", char)
    return key_char is None or decomposed[:1] == key_char or decomposed[:1] == char  # (barred letters do not decompose)


def pair_text(package, left, right):
    a, b = glyph_text(package, left), glyph_text(package, right)
    return a + b if len(a) == 1 and len(b) == 1 else u"%s %s" % (a, b)


class InkDistances(object):
    """The narrowest gap between two glyphs' ink at some kerning, from Auto Kerning's measuring."""

    def __init__(self, ak, package, master, names):
        self.ak = ak
        self.glyphs = ak.FontLabGlyphs(package, master, ak.EM_PIXELS)
        self.known = set(name for name in names if self.glyphs.add(name))
        self.core = ak.Core()
        self.units_per_pixel = self.glyphs.upm / float(ak.EM_PIXELS)

    def closest_at(self, left, right, value):
        if left not in self.known or right not in self.known:
            return None
        ak = self.ak
        a, b = self.glyphs.image(left), self.glyphs.image(right)
        _, raw_right_of_left, _, _ = a.contours(self.core)
        raw_left_of_right, _, _, _ = b.contours(self.core)
        offset = ak.base_offset(a, b) - value / self.units_per_pixel
        gap = self.core.closest(raw_right_of_left, raw_left_of_right, a.height, offset)
        return None if gap > 1e8 else gap * self.units_per_pixel


HELP = u"""<b>FreeLab Kerning Check</b><br>
Three lists for the current font's kerning. Nothing changes until you click a list's button.<br><br>
<b>Collisions</b>: kerned pairs whose ink comes closer than the distance you set, at the kerning
FontLab applies (kerning classes included). The fix is the value that keeps that distance; written,
it is a pair of its own, so the class kerns its other glyphs as before.<br>
<b>Cleanup</b>: entries that change nothing (their pairs get the same value without them, or each
pair they cover has a value of its own), entries naming a class or glyph that is gone (checked), and
values smaller than the size you set (unchecked: look at them first).<br>
<b>Masters</b>: entries some masters kern and others do not, entries tightening in one master and
loosening in another, and classes whose members differ between masters.<br><br>
Select a row and click <i>Show in Glyph window</i> to look at the pair with FontLab's own tools.
Click this help's ? button, then any control, for what it does."""


class Tab(object):
    """One list: its settings row, its tree, its status, its action button."""

    def __init__(self, QtGui, columns, action):
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.settings = QtGui.QHBoxLayout()
        self.layout.addLayout(self.settings)
        self.status = QtGui.QLabel(u"")
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(columns))
        self.tree.setHeaderLabels(list(columns))
        self.tree.setRootIsDecorated(False)
        self.layout.addWidget(self.tree, 1)
        self.buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(self.buttons)
        self.action = QtGui.QPushButton(action) if action else None
        self.findings = []


class KerningCheckDialog(object):
    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = load_auto_kerning()
        main = self.ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Kerning Check")
        dialog.setWhatsThis(HELP)
        dialog.resize(820, 640)
        layout = QtGui.QVBoxLayout(dialog)
        self.font_label = QtGui.QLabel(u"")
        self.font_label.setWordWrap(True)
        layout.addWidget(self.font_label)
        self.tabs = QtGui.QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.collisions = Tab(QtGui, ("Pair", "Kerning", "Distance", "Fix", "Set by", "Compared with"),
                              "Write checked fixes")
        tab = self.collisions
        tab.settings.addWidget(QtGui.QLabel("List pairs"))
        self.minimum = QtGui.QSpinBox()
        self.minimum.setRange(-200, 400)
        self.minimum.setSuffix(" units")
        self.minimum.setWhatsThis("How much closer than their class's first pair (or, by the absolute measure, how "
                                  "close) a pair's ink must come to be listed.")
        tab.settings.addWidget(self.minimum)
        self.mode = QtGui.QComboBox()
        for _, label in COLLISION_MODES:
            self.mode.addItem(label)
        self.mode.setWhatsThis(u"<i>Closer than their class's first pair</i>: a class's value brings an accented "
                               u"or wider member closer than the pair the value was set on "
                               u"(\N{LATIN CAPITAL LETTER T WITH CARON}o against To). This suits any font, also one "
                               u"whose letters join on "
                               u"purpose. <i>Closer than that, absolutely</i>: any kerned pair whose ink comes "
                               u"closer than the distance set (0: pairs that touch).")
        tab.settings.addWidget(self.mode)
        self.collisions_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(self.collisions_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"The pairs whose ink comes too close, closest first: their kerning now, the "
                              u"narrowest distance between their ink with it, the value that keeps the distance "
                              u"you set, and the entry the kerning comes from.")
        tab.action.setWhatsThis(u"Writes each checked pair's fix as a pair of its own (the class it takes its value "
                                u"from kerns its other glyphs as before).")

        self.cleanup = Tab(QtGui, ("Entry", "Value", "Why"), "Remove checked entries")
        tab = self.cleanup
        tab.settings.addWidget(QtGui.QLabel("Values smaller than"))
        self.tiny = QtGui.QSpinBox()
        self.tiny.setRange(0, 50)
        self.tiny.setValue(TINY_UNITS)
        self.tiny.setSuffix(" units")
        self.tiny.setWhatsThis("Entries smaller than this are listed too, unchecked (0: none).")
        tab.settings.addWidget(self.tiny)
        self.cleanup_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(self.cleanup_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"Entries that change nothing or name what is gone (checked), and tiny values "
                              u"(unchecked).")
        tab.action.setWhatsThis(u"Removes the checked entries from the current master.")

        self.masters = Tab(QtGui, ("Entry or class", "Values", "Why"), None)
        tab = self.masters
        self.masters_button = QtGui.QPushButton("Compare masters")
        tab.settings.addWidget(self.masters_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"Differences between the font's masters: entries kerned in some only, entries "
                              u"whose sign flips, classes whose members differ.")

        for tab, label in ((self.collisions, "Collisions"), (self.cleanup, "Cleanup"), (self.masters, "Masters")):
            if tab.action is not None:
                tab.buttons.addStretch(1)
                tab.buttons.addWidget(tab.action)
                tab.action.setEnabled(False)
            self.tabs.addTab(tab.widget, label)

        buttons = QtGui.QHBoxLayout()
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected row's pair in a Glyph window, between H's, n's, "
                                              u"and o's.")
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.glyph_window_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.collisions_button.connect("clicked()", self.check_collisions)
        self.cleanup_button.connect("clicked()", self.check_cleanup)
        self.masters_button.connect("clicked()", self.check_masters)
        self.collisions.action.connect("clicked()", self.write_fixes)
        self.cleanup.action.connect("clicked()", self.remove_entries)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.close_button.connect("clicked()", dialog.close)
        self.package = self.master = None
        self.busy = False
        self.read_font()

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

    def read_font(self):
        """The current font and master; False (and said so) when no font is open."""
        self.package = self.current_font()
        self.master = self.package.master if self.package is not None else None
        if self.package is None:
            self.font_label.setText(u"No font is open. Open one, then click Check.")
            return False
        upm = float(self.package.upm)
        if not self.minimum.value and not getattr(self, "minimum_set", False):
            self.minimum.setValue(round_units(MIN_DISTANCE_SHARE * upm))
            self.minimum_set = True
        self.font_label.setText(u"%s, master %s (%d masters)." % (self.package.tfn, self.master, self.package.mastersCount))
        return True

    def kerning(self, master=None):
        return self.ak.FontKerning(self.package.kerning(master or self.master))

    def same_font(self):
        """True while the font and master are the ones checked; else the lists are cleared."""
        current = self.current_font()
        if (current is not None and self.package is not None and self.ak.font_key(current) == self.ak.font_key(self.package)
                and current.master == self.master):
            return True
        for tab in (self.collisions, self.cleanup, self.masters):
            tab.tree.clear()
            tab.findings = []
            if tab.action is not None:
                tab.action.setEnabled(False)
        self.read_font()
        self.font_label.setText(self.font_label.text + u" The font or master changed: check again.")
        return False

    def progress(self, tab, done, total, what):
        QtCore, QtGui = _qt()
        tab.status.setText(u"%s %d of %d\N{HORIZONTAL ELLIPSIS}" % (what, done, total))
        QtGui.QApplication.processEvents()
        return True

    def after_writing(self):
        try:
            self.fontlab.flItems.notifyPackageContentUpdated(self.package.id)
        except Exception:
            pass
        try:
            self.package.setFlag(2, True)  # ofChanged: a script's kerning writes leave the font unmarked
        except Exception:
            pass

    # -- the lists ---------------------------------------------------------

    @staticmethod
    def add_row(tab, index, texts, checkable, checked, tip=u"", parent=None):
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        item.setData(0, QtCore.Qt.UserRole, index)
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if checkable:
            item.setFlags(flags | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        else:
            item.setFlags(flags)
        bold = QtGui.QFont(tab.tree.font)
        bold.setBold(True)
        item.setFont(0, bold)
        for column in range(len(texts)):
            item.setToolTip(column, tip)
        for column in range(1, len(texts)):
            if texts[column].lstrip(u"-").isdigit() or texts[column] == u"\N{EN DASH}":  # numbers only
                item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
        if parent is not None:
            parent.addChild(item)
        else:
            tab.tree.addTopLevelItem(item)

    @staticmethod
    def add_group(tab, texts):
        """A row grouping others: checking it checks them all."""
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        item.setData(0, QtCore.Qt.UserRole, -1)
        tristate = getattr(QtCore.Qt, "ItemIsAutoTristate", None) or QtCore.Qt.ItemIsTristate  # (Qt 5.6 and later)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable | tristate)
        item.setCheckState(0, QtCore.Qt.Checked)
        bold = QtGui.QFont(tab.tree.font)
        bold.setBold(True)
        item.setFont(0, bold)
        tab.tree.addTopLevelItem(item)
        return item

    @staticmethod
    def rows(tab):
        """Every row with a finding, in groups or not."""
        QtCore, QtGui = _qt()
        found = []
        for row in range(tab.tree.topLevelItemCount):
            item = tab.tree.topLevelItem(row)
            if int(item.data(0, QtCore.Qt.UserRole)) >= 0:
                found.append(item)
            for child in range(item.childCount()):
                found.append(item.child(child))
        return found

    @staticmethod
    def checked(tab):
        QtCore, QtGui = _qt()
        return [tab.findings[int(item.data(0, QtCore.Qt.UserRole))] for item in KerningCheckDialog.rows(tab)
                if item.checkState(0) == QtCore.Qt.Checked]

    @staticmethod
    def resize(tab):
        QtCore, QtGui = _qt()
        for column in range(tab.tree.columnCount - 1):
            tab.tree.resizeColumnToContents(column)
        # the first column holds the rows inside collapsed groups too, which the resize does not measure
        room = QtGui.QFontMetrics(tab.tree.font).width(u"MMMMMM") + 3 * tab.tree.indentation
        if tab.tree.columnWidth(0) < room:
            tab.tree.setColumnWidth(0, room)

    def check_collisions(self):
        if self.busy or not self.read_font():
            return
        QtCore, QtGui = _qt()
        tab = self.collisions
        self.busy = True
        tab.tree.clear()
        tab.findings = []
        tab.action.setEnabled(False)
        try:
            kerning = self.kerning()
            if kerning.plain is None:
                tab.status.setText(u"FontLab did not give this master's kerning with its classes applied.")
                return
            names = set(name for pair in kerning.plain for name in pair)
            tab.status.setText(u"Drawing %d glyphs\N{HORIZONTAL ELLIPSIS}" % len(names))
            QtGui.QApplication.processEvents()
            ink = InkDistances(self.ak, self.package, self.master, names)
            minimum = self.minimum.value
            relative = COLLISION_MODES[self.mode.currentIndex][0] == "relative"
            chars = {}

            def char_of(name):
                if name not in chars:
                    text = glyph_text(self.package, name)
                    chars[name] = text if len(text) == 1 and text != name else None
                return chars[name]

            found = find_collisions(kerning, ink.closest_at, minimum, relative,
                                    lambda done, total: self.progress(tab, done, total, u"Checking pair"),
                                    lambda name, key: is_variant(name, key, char_of))
        except Exception as exc:
            tab.status.setText(u"%s" % exc)
            return
        finally:
            self.busy = False
        tab.findings = found = found or []
        tab.tree.setRootIsDecorated(True)
        groups, order = {}, []  # the glyph that collides (its accent, its bar): its pairs together
        for index, c in enumerate(found):
            key = c.variant or c.left
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(index)
        parents = {}
        for key in order:
            if len(groups[key]) > 1:
                parents[key] = self.add_group(tab, (u"%s \N{EM DASH} %d pairs" % (glyph_text(self.package, key),
                                                                               len(groups[key])),))
                parents[key].setFirstColumnSpanned(True)
        for index, c in enumerate(found):
            where = kerning.describe(c.entry) if c.entry is not None else u""
            if c.reference is not None:
                compared = u"%s: %d" % (pair_text(self.package, *c.reference), round_units(c.reference_gap))
                tip = (u"%s %s: %d now, its ink %d units apart, %d units closer than %s %s at the same value; %d sets it "
                       u"as far apart." % (c.left, c.right, c.value, round_units(c.gap),
                                           round_units(c.reference_gap - c.gap), c.reference[0], c.reference[1], c.fix))
            else:
                compared = u""
                tip = u"%s %s: %d now, its ink %d units apart; %d keeps %d units." % (
                    c.left, c.right, c.value, round_units(c.gap), c.fix, minimum)
            self.add_row(tab, index, (pair_text(self.package, c.left, c.right), u"%d" % c.value,
                                      u"%d" % round_units(c.gap), u"%d" % c.fix, where, compared), True, True, tip,
                         parents.get(c.variant or c.left))
        self.resize(tab)
        tab.action.setEnabled(bool(found))
        tight = sum(1 for value in kerning.plain.values() if value is not None and value < 0)
        what = (u"within %d units, and that much closer than their base letter beside the same glyph" % minimum if relative
                else u"closer than %d units" % minimum)
        tab.status.setText(u"%d of the %d pairs kerned tighter come %s, kerning applied." % (len(found), tight, what)
                           if found else u"None of the %d pairs kerned tighter comes %s." % (tight, what))

    def write_fixes(self):
        if self.busy or not self.same_font():
            return
        tab = self.collisions
        chosen = self.checked(tab)
        if not chosen:
            return
        kerning = self.kerning()
        written, stale, error = 0, 0, None
        try:
            for c in chosen:
                if kerning.current(c.left, c.right) != c.value:
                    stale += 1  # changed since the check
                    continue
                kerning.write(((c.left, False), (c.right, False)), c.fix, False)
                written += 1
        except Exception as exc:
            error = exc
        self.after_writing()
        self.check_collisions()
        notes = [u"Wrote %d pairs of their own." % written]
        if stale:
            notes.append(u"%d pairs had changed since the check and were left as they are." % stale)
        if error is not None:
            notes.append(u"Stopped by an error: %s" % error)
        notes.append(u"Close the font without saving to take it back.")
        tab.status.setText(u" ".join(notes) + u" " + tab.status.text)

    def check_cleanup(self):
        if self.busy or not self.read_font():
            return
        tab = self.cleanup
        tab.tree.clear()
        tab.action.setEnabled(False)
        package = self.package
        kerning = self.kerning()

        def glyph_exists(name):
            glyph = package.findName(name)
            return glyph is not None and not glyph.isNull

        found = find_cleanup(kerning, glyph_exists, self.tiny.value)
        tab.findings = found
        kinds = dict(CLEANUP_KINDS)
        for index, c in enumerate(found):
            self.add_row(tab, index, (kerning.describe(c.entry), u"%d" % c.value, u"%s: %s" % (kinds[c.kind], c.reason)),
                         True, c.checked)
        self.resize(tab)
        tab.action.setEnabled(bool(found))
        counts = {}
        for c in found:
            counts[c.kind] = counts.get(c.kind, 0) + 1
        tab.status.setText(u"%d of %d entries listed: %s." % (
            len(found), len(kerning.entries), u", ".join(u"%d %s" % (counts[kind], label.lower())
                                                       for kind, label in CLEANUP_KINDS if kind in counts) or u"none"))

    def remove_entries(self):
        if self.busy or not self.same_font():
            return
        tab = self.cleanup
        chosen = self.checked(tab)
        if not chosen:
            return
        kerning = self.kerning()
        removed, stale, error = 0, 0, None
        try:
            for c in chosen:
                if c.entry not in kerning.entries or round_units(kerning.values.get(c.entry) or 0) != c.value:
                    stale += 1
                    continue
                kerning.write(c.entry, 0, True)
                removed += 1
        except Exception as exc:
            error = exc
        self.after_writing()
        self.check_cleanup()
        notes = [u"Removed %d entries." % removed]
        if stale:
            notes.append(u"%d had changed since the check and were left as they are." % stale)
        if error is not None:
            notes.append(u"Stopped by an error: %s" % error)
        notes.append(u"Close the font without saving to take it back.")
        tab.status.setText(u" ".join(notes) + u" " + tab.status.text)

    def check_masters(self):
        if self.busy or not self.read_font():
            return
        tab = self.masters
        tab.tree.clear()
        masters = list(self.package.masters)
        if len(masters) < 2:
            tab.findings = []
            tab.status.setText(u"This font has one master: nothing to compare.")
            return
        found = compare_masters([(master, self.kerning(master)) for master in masters])
        tab.findings = found
        for index, d in enumerate(found):
            self.add_row(tab, index, (d.subject, u"; ".join(u"%s %s" % pair for pair in d.values), d.reason), False, False)
        self.resize(tab)
        tab.status.setText(u"%d differences between %d masters." % (len(found), len(masters)) if found
                           else u"The %d masters kern the same entries, with the same signs." % len(masters))

    # -- looking at a pair ----------------------------------------------

    def selected_pair(self):
        """The glyph pair of the selected row (an entry's first pair), or None."""
        QtCore, QtGui = _qt()
        tab = (self.collisions, self.cleanup, self.masters)[self.tabs.currentIndex]
        items = tab.tree.selectedItems()
        if not items or not tab.findings:
            return None
        item = items[0]
        if int(item.data(0, QtCore.Qt.UserRole)) < 0:  # a group: its first pair
            if not item.childCount():
                return None
            item = item.child(0)
        finding = tab.findings[int(item.data(0, QtCore.Qt.UserRole))]
        if isinstance(finding, Collision):
            return finding.pair()
        if isinstance(finding, Cleanup):
            pairs = self.kerning().pairs(finding.entry)
            return pairs[0] if pairs else None
        return None

    def show_in_glyph_window(self):
        if self.package is None:
            return
        pair = self.selected_pair()
        if pair is None:
            return
        contexts = [c for c in self.ak.PROOF_CONTEXTS if self.package.findName(c) is not None]
        error = self.ak.show_in_glyph_window(self.fontlab, self.ak.proof_text(pair[0], pair[1], contexts or [pair[0]]))
        if error:
            self.font_label.setText(u"FontLab did not open the pair: %s" % error)

    def show(self):
        self.dialog.show()
        self.dialog.raise_()


def main():
    held = getattr(sys, "_freelab_kerning_check", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = KerningCheckDialog()
    except Exception as exc:
        print("FreeLab Kerning Check: %s" % exc)
        return
    sys._freelab_kerning_check = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_kerning_check":
    main()
