#FLM: Feature Code
# -*- coding: utf-8 -*-
"""FreeLab feature code, from FontLab's Scripts menu.

Two kinds of OpenType code a font's glyph names alone do not settle:

- Ligatures: every ligature of the font (its own rules in liga and dlig, and every glyph whose name
  joins others with _), each set to Standard (liga: on unless turned off), Discretionary (dlig: off
  unless turned on), or Off. Rules are written longest first; the features' other rules are kept.
  FontLab regenerates the code between its "#> feature" and "#< feature" lines when it updates its
  automatic features (on compiling or exporting, with Update on Compile): a feature written here has
  that first line turned into "#/> feature", FontLab's own way to hand a feature back to you.
- Alternates that take turns (calt): for a handwriting font, a letter repeated within a few letters
  takes its next alternate (l, l.2, l, l.2...), so doubled and nearby letters do not look stamped. The
  nearest earlier form of the same letter decides; spaces and punctuation end the look back. Its code
  sits in calt between FreeLab's own marker lines, and the rest of calt is kept.

Shows the code before anything is written, checked by fontTools' feature parser.

Valid Python 2.7 (FontLab 7) and Python 3. The code generation below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import os
import re
import sys
import unicodedata

CHOICES = (("liga", "Standard (liga)"), ("dlig", "Discretionary (dlig)"), ("off", "Off"))
FEATURE_TITLES = {"liga": "Standard Ligatures", "dlig": "Discretionary Ligatures", "calt": "Contextual Alternates"}
BEGIN, END = u"# >>> FreeLab %s (made by FreeLab Feature Code)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
LISTS_EVERY_ALTERNATE = ("aalt", "salt")  # features that list alternates as a menu, not giving them a job
DEFAULT_LOOK_BACK = 2  # letters between a letter and its earlier form, at most
ALTERNATE_SUFFIX = re.compile(r"^(?P<base>[^.]+)\.(?:(?P<number>[2-9])|alt(?P<alt>[0-9]*)|calt(?P<calt>[0-9]*))$")
RULE = re.compile(r"^\s*sub(?:stitute)?\s+(?P<input>[A-Za-z0-9_.\- ]+?)\s+by\s+(?P<output>[A-Za-z0-9_.\-]+)\s*;\s*(?:#.*)?$")


def unichr_(code):
    """A code point's character; the replacement character past U+FFFF on a narrow Python 2 (FontLab
    7's), which has none of them as one character (no letter is that far up in the blocks used here)."""
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


# ---------------------------------------------------------------------------
# Ligatures
# ---------------------------------------------------------------------------

class Ligature(object):
    """A ligature glyph, the glyphs it replaces, and the feature it is in now and is set to."""

    def __init__(self, glyph, parts, now, choice=None, why=None):
        self.glyph, self.parts, self.now = glyph, tuple(parts), now  # now: "liga", "dlig", or None
        self.choice = choice or now or "dlig"
        self.why = why  # what set its first choice, for its tooltip


def rules_of(text):
    """[(input glyphs, output glyph)] of a feature's simple ligature rules (sub a b by a_b;)."""
    found = []
    for line in (text or u"").splitlines():
        match = RULE.match(line)
        if match:
            parts = match.group("input").split()
            if len(parts) > 1:
                found.append((tuple(parts), match.group("output")))
    return found


def ligatures(names, features, chars=None, model=None):
    """Every ligature of a font: the rules of its liga and dlig, then each glyph whose name joins
    glyphs of the font with _ (f_f_t: f f t; l_l.dlig: l l), in the feature its suffix names; with no
    suffix, in the one most of the corpus's families put it in (model: {characters: [liga families,
    dlig families]}, chars: {glyph: its character}), else dlig. features maps a tag to its code."""
    names = set(names)
    chars, counts_of = chars or {}, (model or {}).get("ligatures", {})
    found, seen = [], set()
    for tag in ("liga", "dlig"):
        for parts, glyph in rules_of(features.get(tag)):
            if (parts, glyph) not in seen:
                seen.add((parts, glyph))
                found.append(Ligature(glyph, parts, tag, why=u"the font's own %s" % tag))
    made = set(glyph for _, glyph in seen)
    for name in sorted(names):
        stem, _, suffix = name.partition(u".")
        parts = stem.split(u"_")
        if name in made or len(parts) < 2 or not all(part in names for part in parts):
            continue
        if suffix in (u"liga", u"dlig"):
            found.append(Ligature(name, parts, None, suffix, u"its name's .%s" % suffix))
            continue
        key = u"".join(chars.get(part) or u"\0" for part in parts)
        counts = counts_of.get(key) if u"\0" not in key else None
        if counts:
            choice = "liga" if counts[0] >= counts[1] else "dlig"
            why = u"%d of the %d corpus families with it put it in %s" % (
                max(counts), counts[0] + counts[1], choice)
            found.append(Ligature(name, parts, None, choice, why))
        else:
            found.append(Ligature(name, parts, None, "dlig", u"no corpus family has it: discretionary, to be safe"))
    return found


LIGATURE_MODEL_FILE = "ligature_model.json"


def load_ligature_model(path=None):
    """The corpus's ligature counts (ligature_model.json beside this script), or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), LIGATURE_MODEL_FILE)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


def feature_text(tag, old, rules, block_name, managed=None):
    """A feature's code with FreeLab's block of rules in place: the old code kept but for the managed
    rules (by default the block's own, wherever they were) and an older FreeLab block, FontLab's
    automatic block handed back to you ("#/> feature"), and the block before the feature's closing
    line. rules and managed: [(parts, glyph)]."""
    managed = set(u"%s %s" % (u" ".join(parts), glyph) for parts, glyph in (rules if managed is None else managed))
    begin, end = BEGIN % block_name, END % block_name
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
        match = RULE.match(line)
        if match and u"%s %s" % (u" ".join(match.group("input").split()), match.group("output")) in managed:
            continue  # written in FreeLab's block now
        if stripped.startswith(FONTLAB_AUTO):
            line = line.replace(FONTLAB_AUTO, FONTLAB_HANDED, 1)
        kept.append(line)
    block = [begin] + [u"  %s" % rule for rule in rule_lines(rules)] + [end]
    closing = None
    for index in range(len(kept) - 1, -1, -1):
        if re.match(r"^\s*}\s*%s\s*;" % re.escape(tag), kept[index]):
            closing = index
            break
    if closing is None:  # a new feature
        kept = [u"feature %s {" % tag, u"# %s" % FEATURE_TITLES.get(tag, tag), u""]
        closing = len(kept)
        kept.append(u"} %s;" % tag)
    if not rules:
        block = []
    return u"\n".join(kept[:closing] + block + kept[closing:]) + u"\n"


def ligature_texts(found, texts):
    """{tag: new code} for liga and dlig: every ligature's rule taken out of both, and put back in the
    one it is set to (none for Off). A feature is rewritten only where something of it changes."""
    managed = [(lig.parts, lig.glyph) for lig in found]
    new = {}
    for tag in ("liga", "dlig"):
        rules = [(lig.parts, lig.glyph) for lig in found if lig.choice == tag]
        old = texts.get(tag)
        if rules or any(lig.now == tag for lig in found) or (BEGIN % "ligatures") in (old or u""):
            new[tag] = feature_text(tag, old, rules, "ligatures", managed)
    return new


def rule_lines(rules):
    """Ligature rules, longest first (a font's ffi before its ff), then alphabetical."""
    return [u"sub %s by %s;" % (u" ".join(parts), glyph)
            for parts, glyph in sorted(rules, key=lambda rule: (-len(rule[0]), rule[0], rule[1]))]


# ---------------------------------------------------------------------------
# Alternates that take turns
# ---------------------------------------------------------------------------

def alternate_sets(names, is_letter):
    """{letter glyph: [its alternates, in order]}: X.2, X.3...; X.alt, X.alt1, X.alt2...; X.calt1...
    is_letter(glyph) says whether a glyph is a letter's."""
    names = set(names)
    found = {}
    for name in names:
        match = ALTERNATE_SUFFIX.match(name)
        if not match or match.group("base") not in names or not is_letter(match.group("base")):
            continue
        number = match.group("number") or match.group("alt") or match.group("calt") or u"1"
        found.setdefault(match.group("base"), []).append((int(number), name))
    return dict((base, [name for _, name in sorted(forms)]) for base, forms in found.items())


def cycle_code(sets, letters, look_back=DEFAULT_LOOK_BACK, class_prefix=u"FreeLab"):
    """calt code: a letter whose nearest earlier form (within look_back letters between) is form i
    takes form i + 1 (back to the letter after its last alternate). letters: every letter glyph of
    the font (alternates and ligatures of letters included), what may stand between."""
    lines = []
    for base in sorted(sets):
        forms = [base] + list(sets[base])
        gap = sorted(set(letters) - set(forms))
        gap_class = u"@%s_gap_%s" % (class_prefix, safe_name(base))
        lines.append(u"%s = [%s];" % (gap_class, u" ".join(gap)))
    lines.append(u"lookup %s_take_turns {" % class_prefix)
    for base in sorted(sets):
        forms = [base] + list(sets[base])
        gap_class = u"@%s_gap_%s" % (class_prefix, safe_name(base))
        for index, earlier in enumerate(forms):
            following = forms[(index + 1) % len(forms)]
            if following == base:
                continue  # back to the letter: it already is
            for between in range(look_back + 1):
                lines.append(u"  sub %s %s%s' by %s;" % (earlier, u"".join(u"%s " % gap_class for _ in range(between)),
                                                        base, following))
    lines.append(u"} %s_take_turns;" % class_prefix)
    return lines


def used_in(names, texts):
    """{glyph: [tags]} of the glyphs the font's code names already (outside FreeLab's blocks): an
    alternate the designer gave a job (a standalone I) is not one to take turns."""
    found = {}
    for tag, text in sorted(texts.items()):
        if tag in LISTS_EVERY_ALTERNATE:
            continue
        kept = feature_text(tag, text, [], "alternates") if (BEGIN % "alternates") in (text or u"") else (text or u"")
        tokens = set(re.findall(r"[A-Za-z0-9_.]+", u"\n".join(line.split(u"#")[0] for line in kept.splitlines())))
        for name in names:
            if name in tokens:
                found.setdefault(name, []).append(tag)
    return found


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9_]", u"_", name)


def calt_text(old, code_lines):
    """calt's code with FreeLab's alternates block (code_lines) in it, the rest kept."""
    return feature_text("calt", old, [], "alternates").replace(
        u"} calt;", u"\n".join([BEGIN % "alternates"] + [u"  " + line for line in code_lines] + [END % "alternates", u"} calt;"]), 1) \
        if code_lines else feature_text("calt", old, [], "alternates")


def freelab_block(tag, text, block_name):
    """FreeLab's block of a feature's code, alone in a feature of its own (what check_code checks:
    the rest of the code may name classes FontLab keeps outside it), or None."""
    begin, end = BEGIN % block_name, END % block_name
    lines = (text or u"").splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == begin]
    ends = [i for i, line in enumerate(lines) if line.strip() == end]
    if not starts or not ends:
        return None
    return u"\n".join([u"feature %s {" % tag] + lines[starts[0] + 1:ends[0]] + [u"} %s;" % tag]) + u"\n"


def check_code(text, names):
    """fontTools' parser's complaint about feature code (glyph names checked against the font's), or
    None; None too where fontTools is not there."""
    try:
        import io
        from fontTools.feaLib.parser import Parser
    except Exception:
        return None
    try:
        Parser(io.StringIO(text), glyphNames=set(names)).parse()
        return None
    except Exception as exc:
        return u"%s" % exc


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 36


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: its helpers (outlines, dialogs)."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "layer_path") and getattr(held, "_freelab_stamp", None) == stamp:
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


HELP = u"""<b>FreeLab Feature Code</b><br>
Writes the OpenType code for the font's ligatures, and for alternates that take turns. The code is
shown, and checked, before anything is written.<br><br>
<b>Ligatures</b>: each ligature with what it replaces, set to Standard (liga, on unless a user turns
it off), Discretionary (dlig, off unless a user turns it on), or Off. A ligature the font's code and
name do not place starts where most of the open-licensed fonts FreeLab learned from put it (f_i in
liga, c_t in dlig); its feature's tooltip says why. Applications let users switch
both: in InDesign and Illustrator, the Ligatures and Discretionary Ligatures options; on the web,
font-variant-ligatures. A feature written here is handed back from FontLab's automatic features (its
"#> feature" line becomes "#/> feature"), so FontLab no longer rewrites it on export; the rest of its
code is kept.<br>
<b>Alternates that take turns</b> (calt, on unless turned off): a letter repeated within the letters
set takes its next alternate (X.2, X.3, or X.alt1...), so repeated letters vary as handwriting does.
The nearest earlier form decides; a space or punctuation ends the look back. Ligatures come first:
where liga makes l_l of ll, the alternates take turns around it.<br><br>
The code is made again as you change the choices. Click a ligature's feature to change it;
double-click a ligature or a letter to see it in a Glyph window. <i>Restore suggestions</i> puts the
choices back as they first came.<br><br>
Click this help's ? button, then any control, for what it does."""


class FeatureCodeDialog(object):
    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = load_auto_kerning()
        main = self.ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Feature Code")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = self.ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = self.ak.Log()
        self.seen_history, self.first_choices, self.first_checks = None, [], []

        layout.addWidget(self.heading(QtGui, u"Ligatures"))
        self.ligature_tree = QtGui.QTreeWidget()
        self.ligature_tree.setColumnCount(3)
        self.ligature_tree.setHeaderLabels(["Ligature", "Replaces", "Feature"])
        self.ligature_tree.setRootIsDecorated(False)
        self.ligature_tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.ligature_tree.setWhatsThis(u"Each ligature, what it replaces, and the feature it goes in (click it to "
                                        u"change it). Standard ligatures are on unless a user turns them off; "
                                        u"discretionary ones off unless turned on.")
        self.ligature_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        self.ak.grid_lines(self.ligature_tree)
        layout.addWidget(self.ligature_tree, 2)

        layout.addWidget(self.heading(QtGui, u"Alternates that take turns"))
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Look back over at most"))
        self.look_back = QtGui.QSpinBox()
        self.look_back.setRange(0, 6)
        self.look_back.setValue(DEFAULT_LOOK_BACK)
        self.look_back.setSuffix(" letters")
        self.look_back.setWhatsThis(u"How many letters may stand between a letter and its earlier form for it to take "
                                    u"the next alternate (0: only side by side).")
        row.addWidget(self.look_back)
        row.addStretch(1)
        layout.addLayout(row)
        self.alternate_tree = QtGui.QTreeWidget()
        self.alternate_tree.setColumnCount(3)
        self.alternate_tree.setHeaderLabels(["Letter", "Cycle", "Note"])
        self.alternate_tree.setRootIsDecorated(False)
        self.alternate_tree.setIconSize(QtCore.QSize(ICON_SIZE * 3, ICON_SIZE))
        self.alternate_tree.setWhatsThis(u"The letters with alternates (named X.2, X.alt1, or X.calt1), and their "
                                         u"cycle: the forms they take in turn. Checked letters take turns.")
        self.alternate_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.grid_lines(self.alternate_tree)
        layout.addWidget(self.alternate_tree, 1)

        layout.addWidget(self.heading(QtGui, u"The code"))
        self.code = QtGui.QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setWhatsThis(u"The code to be written, feature by feature: FreeLab's blocks between their "
                               u"marker lines, the rest of each feature as it is.")
        layout.addWidget(self.code, 2)

        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every ligature's feature and every letter's check back as they first came.")
        self.write_button = QtGui.QPushButton("Write the code")
        self.write_button.setWhatsThis(u"Writes liga, dlig, and calt as shown to the font's features (Update the code: "
                                       u"FreeLab's code is in them already, and changes).")
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        buttons.addWidget(self.write_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.restore_button.connect("clicked()", self.restore)
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", dialog.close)
        self.look_back.connect("valueChanged(int)", lambda value: self.make_code())
        self.ligature_tree.connect("itemClicked(QTreeWidgetItem*,int)", self.feature_clicked)
        self.ligature_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.alternate_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.alternate_tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.make_code())
        self.package = None
        self.names, self.letters, self.found, self.sets = [], [], [], {}
        self.texts, self.prefix = {}, u""
        self.ligature_model = load_ligature_model()
        self.ak.plain_buttons(dialog)
        self.history_timer = self.ak.watch_history(self)
        self.flagging = [self.ak.flag_menu(self.ligature_tree, self, lambda: self.selected_names(self.ligature_tree),
                                           lambda item: self.item_names(self.ligature_tree, item)),
                         self.ak.flag_menu(self.alternate_tree, self, lambda: self.selected_names(self.alternate_tree),
                                           lambda item: self.item_names(self.alternate_tree, item))]

    def selected_names(self, tree):
        QtCore, QtGui = _qt()
        items = tree.selectedItems()
        if not items:
            return []
        return self.item_names(tree, items[0])

    def item_names(self, tree, item):
        """A row's glyphs (a ligature; a glyph and its forms): their flags shown."""
        QtCore, QtGui = _qt()
        items = [item]
        if tree is self.ligature_tree:
            index = int(items[0].data(0, QtCore.Qt.UserRole))
            return [self.found[index].glyph] if 0 <= index < len(self.found) else []
        base = u"%s" % items[0].data(0, QtCore.Qt.UserRole)
        return [base] + list(self.sets.get(base, []))

    @staticmethod
    def heading(QtGui, text):
        label = QtGui.QLabel(text)
        font = QtGui.QFont(label.font)
        font.setBold(True)
        label.setFont(font)
        return label

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
        package = self.package = self.current_font()
        self.ligature_tree.clear()
        self.alternate_tree.clear()
        self.write_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        if package is None:
            self.status.setText(u"No font is open. Open one, then run Feature Code again.")
            return
        glyphs = list(package.fgPackage.glyphs)
        self.names = [g.name for g in glyphs]
        codes = dict((g.name, g.unicode) for g in glyphs)
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        try:
            self.prefix = features.get_prefix() or u""
        except Exception:
            self.prefix = u""

        def is_letter(name):
            code = codes.get(name)
            return bool(code) and unicodedata.category(unichr_(code)).startswith(u"L")

        def letter_like(name):
            stem = name.split(u".")[0]
            return all(is_letter(part) for part in stem.split(u"_") if part) if stem else False

        self.letters = [name for name in self.names if letter_like(name)]
        self.found = ligatures(self.names, self.texts,
                               dict((name, unichr_(code)) for name, code in codes.items() if code), self.ligature_model)
        self.sets = alternate_sets(self.names, is_letter)
        bold = QtGui.QFont(self.ligature_tree.font)
        bold.setBold(True)
        self.ligature_tree.blockSignals(True)
        for index, lig in enumerate(self.found):
            item = QtGui.QTreeWidgetItem([lig.glyph, u" ".join(lig.parts), u""])
            item.setFont(0, bold)
            item.setData(0, QtCore.Qt.UserRole, index)
            icon = self.picture([lig.glyph])
            if icon is not None:
                item.setIcon(0, QtGui.QIcon(icon))
            item.setToolTip(1, u"Now: %s." % (dict(CHOICES)[lig.now] if lig.now else u"in no feature"))
            item.setToolTip(2, u"Click to choose its feature. First set by %s." % (lig.why or u"default"))
            self.ligature_tree.addTopLevelItem(item)
            self.show_choice(item, lig)
        self.first_choices = [lig.choice for lig in self.found]
        self.ligature_tree.blockSignals(False)
        self.alternate_tree.blockSignals(True)
        used = used_in([name for forms in self.sets.values() for name in forms], self.texts)
        for base in sorted(self.sets):
            forms = [base] + self.sets[base]
            jobs = [u"%s in %s" % (name, u", ".join(used[name])) for name in self.sets[base] if name in used]
            note = (u"The font's code uses %s already: left out, so as not to undo it." % u"; ".join(jobs)) if jobs else u""
            item = QtGui.QTreeWidgetItem([base, u", ".join(forms), note])
            item.setFont(0, bold)
            item.setData(0, QtCore.Qt.UserRole, base)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Unchecked if jobs else QtCore.Qt.Checked)
            item.setToolTip(2, note)
            icon = self.picture(forms)
            if icon is not None:
                item.setIcon(1, QtGui.QIcon(icon))
            self.alternate_tree.addTopLevelItem(item)
        self.alternate_tree.blockSignals(False)
        self.first_checks = self.alternate_checks()
        for tree in (self.ligature_tree, self.alternate_tree):
            tree.resizeColumnToContents(0)
            tree.resizeColumnToContents(1)
        self.make_code()
        self.seen_history = self.ak.history_mark(package)

    @staticmethod
    def show_choice(item, lig):
        item.setText(2, u"%s  \N{BLACK DOWN-POINTING SMALL TRIANGLE}" % dict(CHOICES)[lig.choice])

    def feature_clicked(self, item, column):
        """A ligature's feature clicked: a menu of the three, its own checked."""
        QtCore, QtGui = _qt()
        if column != 2:
            return
        index = int(item.data(0, QtCore.Qt.UserRole))
        lig = self.found[index]
        menu = QtGui.QMenu(self.dialog)
        actions = []
        for key, label in CHOICES:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(key == lig.choice)
            actions.append((action, key))
        rect = self.ligature_tree.visualItemRect(item)
        left = self.ligature_tree.header().sectionPosition(2)
        where = self.ligature_tree.viewport().mapToGlobal(QtCore.QPoint(left, rect.bottom()))
        picked = menu.exec_(where)
        for action, key in actions:
            if picked is not None and action.text == picked.text and key != lig.choice:
                lig.choice = key
                self.show_choice(item, lig)
                self.make_code()
                break

    def alternate_checks(self):
        QtCore, QtGui = _qt()
        return [self.alternate_tree.topLevelItem(row).checkState(0) == QtCore.Qt.Checked
                for row in range(self.alternate_tree.topLevelItemCount)]

    def restore(self):
        """The features and checks as they first came."""
        QtCore, QtGui = _qt()
        for row, (lig, choice) in enumerate(zip(self.found, self.first_choices)):
            lig.choice = choice
            self.show_choice(self.ligature_tree.topLevelItem(row), lig)
        self.alternate_tree.blockSignals(True)
        for row, on in enumerate(self.first_checks):
            self.alternate_tree.topLevelItem(row).setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.alternate_tree.blockSignals(False)
        self.make_code()
        self.log.add(u"Choices restored as suggested.")

    def double_clicked(self, item, column):
        """A ligature's glyphs, or a letter's forms, in a Glyph window, as the features set them."""
        QtCore, QtGui = _qt()
        if column == 2 and item.treeWidget() is self.ligature_tree:
            return
        if item.treeWidget() is self.ligature_tree:
            lig = self.found[int(item.data(0, QtCore.Qt.UserRole))]
            text = u"".join(u"/" + name for name in lig.parts) + u"/space/" + lig.glyph
        else:
            base = u"%s" % item.data(0, QtCore.Qt.UserRole)
            text = u"".join(u"/" + name for name in [base] * 4)
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open them: %s" % self.ak.html(error), "error")

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again, the choices kept where they still apply."""
        choices = dict((lig.glyph, lig.choice) for lig in self.found)
        self.run()
        for row, lig in enumerate(self.found):
            if lig.glyph in choices and choices[lig.glyph] != lig.choice:
                lig.choice = choices[lig.glyph]
                self.show_choice(self.ligature_tree.topLevelItem(row), lig)
        self.make_code()
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")

    def picture(self, names):
        """Glyphs side by side, in the dialog's text color."""
        QtCore, QtGui = _qt()
        master = self.package.master
        layers = []
        for name in names:
            glyph = self.package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            if layer is not None:
                layers.append(layer)
        if not layers:
            return None
        scale = ICON_SIZE * 0.75 / float(self.package.upm)
        gap = ICON_SIZE * 0.2
        width = int(sum(layer.advanceWidth for layer in layers) * scale + gap * len(layers))
        pixmap = QtGui.QPixmap(max(width, 4), ICON_SIZE)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            x = 0.0
            for layer in layers:
                painter.save()
                painter.translate(x, ICON_SIZE * 0.78)
                painter.scale(scale, -scale)
                painter.fillPath(self.ak.layer_path(layer), QtGui.QBrush(color))
                painter.restore()
                x += layer.advanceWidth * scale + gap
        finally:
            painter.end()
        return pixmap

    def cycling(self):
        QtCore, QtGui = _qt()
        chosen = {}
        for row in range(self.alternate_tree.topLevelItemCount):
            item = self.alternate_tree.topLevelItem(row)
            base = u"%s" % item.data(0, QtCore.Qt.UserRole)
            if item.checkState(0) == QtCore.Qt.Checked and base in self.sets:
                chosen[base] = self.sets[base]
        return chosen

    def new_texts(self):
        """{tag: its new code} for liga, dlig, and calt (only those with something of FreeLab's, or
        with rules FreeLab takes over)."""
        texts = ligature_texts(self.found, self.texts)
        cycling = self.cycling()
        if cycling or (BEGIN % "alternates") in (self.texts.get("calt") or u""):
            texts["calt"] = calt_text(self.texts.get("calt"),
                                      cycle_code(cycling, self.letters, self.look_back.value) if cycling else [])
        return texts

    def make_code(self):
        if self.package is None:
            return
        texts = self.new_texts()
        shown, problems = [], []
        for tag in ("liga", "dlig", "calt"):
            if tag in texts:
                shown.append(texts[tag])
                block = freelab_block(tag, texts[tag], "alternates" if tag == "calt" else "ligatures")
                problem = check_code(block, self.names) if block else None
                if problem:
                    problems.append(u"%s: %s" % (tag, problem))
        self.code.setPlainText(u"\n".join(shown))
        present = any((BEGIN % kind) in (self.texts.get(tag) or u"")
                      for tag, kind in (("liga", "ligatures"), ("dlig", "ligatures"), ("calt", "alternates")))
        changes = any(texts[tag] != self.texts.get(tag) for tag in texts)
        self.write_button.setText(u"Update the code" if present else u"Write the code")
        self.ak.enable(self.write_button, bool(texts) and changes and not problems)
        self.ak.enable(self.restore_button, [lig.choice for lig in self.found] != self.first_choices
                       or self.alternate_checks() != self.first_checks)
        counts = dict((key, sum(1 for lig in self.found if lig.choice == key)) for key, _ in CHOICES)
        b = self.ak.b
        self.status.setText(u"%s: %s (%s standard, %s discretionary, %s off); %s with alternates taking turns.%s%s" % (
            b(self.package.tfn), b(counted(len(self.found), u"ligature")), b(counts["liga"]), b(counts["dlig"]),
            b(counts["off"]), b(counted(len(self.cycling()), u"letter")),
            u" The font has this code already." if texts and not changes else u"",
            (u" The code has problems, so nothing can be written: " + self.ak.html(u"; ".join(problems))) if problems else u""))

    def write(self):
        if self.package is None:
            return
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(self.package):
            self.run()
            self.log.add(u"The font changed: here is this one's code. Nothing was written.", "warning")
            return
        features = self.package.fgPackage.features
        if any((features.get_feature(tag) if tag in features.keys() else None) != self.texts.get(tag)
               for tag in ("liga", "dlig", "calt")):
            self.run()
            self.log.add(u"The features changed since they were read: here they are again. Nothing was written.",
                         "warning")
            return
        texts = self.new_texts()
        written, error = [], None
        try:
            for tag in ("liga", "dlig", "calt"):
                if tag in texts:
                    features.set_feature(tag, texts[tag])
                    written.append(tag)
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Feature Code")
        self.run()
        self.log.add(u"Wrote %s. Compile the features in FontLab's Features panel to try them; Edit &gt; Undo takes "
                     u"them back." % self.ak.b(u", ".join(written)) if written else u"Wrote nothing.",
                     "done" if written else "info")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    held = getattr(sys, "_freelab_feature_code", None)
    if held is not None:
        try:
            held.dialog.close()
        except Exception:
            pass
    try:
        dialog = FeatureCodeDialog()
    except Exception as exc:
        print("FreeLab Feature Code: %s" % exc)
        return
    sys._freelab_feature_code = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_feature_code":
    main()
