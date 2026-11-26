#FLM: Family Audit
# -*- coding: utf-8 -*-
"""FreeLab Family Audit, from FontLab's Scripts menu.

The fonts of a family (or the masters of one font, or both) compared with one another, read-only:

- Glyph sets: the glyphs some sources lack, and the code points that differ (a glyph name with other code
  points in another source, a code point given to glyphs of other names).
- Compatibility: each glyph's structure across the sources (contour count, node count and node types per
  contour, contour directions, components, anchors): compatible, or what differs first. A glyph whose
  structures match is not promised to interpolate (start points, contour order, and shapes are not looked
  at): the count says how many match, no more.
- Metrics and info: version, units per em, vertical metrics, italic angle, family and style names, weight
  and width classes, a column per source.
- Kerning: the classes whose members differ, the entries only some sources kern, and those that tighten in
  one source and loosen in another.
- Features: the features (the prefix, and the Classes panel's classes) some sources lack, and the code that
  differs from the reference's, line by line (Font Compare's splitting and diff).

Then, optionally, *Assemble as masters*: a NEW font, a master per source, never a change to the sources.

The sources are the fonts open in FontLab (a font of several masters gives a source per master) and the font
files added with Add files..., opened in FontLab first. Valid Python 2.7 (FontLab 7) and Python 3. The
comparisons and the assembly's plan above the FontLab line need no Qt and no FontLab; the FontLab calls are
gathered in FontLabCalls, one method per call, each saying what it assumes.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
COMPARE_FILE, COMPARE_MODULE = "freelab_font_compare.py", "freelab_font_compare"
TOOL = u"Family Audit"
TITLE = u"FreeLab Family Audit"
TABS = ("glyphs", "compatibility", "metrics", "kerning", "features")
TAB_TITLES = (u"Glyph sets", u"Compatibility", u"Metrics and info", u"Kerning", u"Features")
ROWS_SHOWN = 1000  # rows of a group listed at most (the rest counted in its last row)
SIGN_TOLERANCE = 10  # units: a value tightens or loosens beyond this (Kerning Check's, between masters)
NAMES_SHOWN = 6  # glyph names a sentence lists at most ("a, b, c, and 4 more")
ELLIPSIS = u"\N{HORIZONTAL ELLIPSIS}"
DASH = u"\N{EN DASH}"  # a value a source does not have
TIMES = u"\N{MULTIPLICATION SIGN}"


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the dialogs' shared
    helpers come from it."""
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


def compare_module():
    """Font Compare beside this script, as a module (its window not opened): its reading of a glyph's
    layer, its features' splitting, and its line diff are this tool's too. Where the shared module cannot
    load it (the tests, from the repository's folders), the module found on the path."""
    try:
        return load_auto_kerning().load_sibling(COMPARE_FILE, COMPARE_MODULE)
    except Exception:
        import freelab_font_compare
        return freelab_font_compare


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

def grouped(number):
    """1234 as "1,234"."""
    return u"{:,}".format(int(number))


def counted(number, one, many=None):
    """"1 glyph", "2 glyphs", "13,956 glyphs": a count (thousands grouped) with its noun in the right number."""
    return u"%s %s" % (grouped(number), one if number == 1 else (many or one + u"s"))


def html(text):
    return (u"%s" % text).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


def bold(text):
    return u"<b>%s</b>" % html(text)


def italic(text):
    return u"<i>%s</i>" % html(text)


def listed(items, conjunction=u"and"):
    """"Regular", "Regular and Bold", "Regular, Bold, and Black" (the Oxford comma)."""
    items = [u"%s" % item for item in items]
    if len(items) < 2:
        return u"".join(items)
    if len(items) == 2:
        return u"%s %s %s" % (items[0], conjunction, items[1])
    return u"%s, %s %s" % (u", ".join(items[:-1]), conjunction, items[-1])


def names_text(names, most=NAMES_SHOWN):
    """Glyph names in a sentence: "a, b, and c"; "a, b, c, d, e, f, and 3 more"."""
    names = list(names)
    if len(names) <= most:
        return listed(names)
    return u"%s, and %s more" % (u", ".join(names[:most]), grouped(len(names) - most))


def code_text(code):
    return u"U+%04X" % code


def codes_text(codes):
    return u" ".join(code_text(c) for c in sorted(codes)) or u"none"


def tab_text(title, count=None):
    """A tab's title with its count of differences in parentheses, thousands grouped: "Compatibility
    (40)"; "(alike)" when nothing differs ("Metrics and info (alike)": a "(0)" over 20 fields alike read as
    nothing compared, owner's images 327 and 328); the title alone before an audit."""
    if count is None:
        return title
    return u"%s (%s)" % (title, grouped(count) if count else u"alike")


def by_value(pairs):
    """[(value, [labels])] of [(label, value)], in the order each value first comes."""
    found, order = {}, []
    for label, value in pairs:
        if value not in found:
            found[value] = []
            order.append(value)
        found[value].append(label)
    return [(value, found[value]) for value in order]


def number_text(value):
    """A value of the font info as the table shows it: a whole number without its decimals, "" for none."""
    if value is None or value == u"":
        return u""
    if isinstance(value, float) and value == int(value):
        return u"%d" % int(value)
    if isinstance(value, float):
        return (u"%.2f" % value).rstrip(u"0").rstrip(u".")
    return u"%s" % value


# ---------------------------------------------------------------------------
# The sources
# ---------------------------------------------------------------------------

FORMATS = ((u".vfc", u"VFC"), (u".vfj", u"VFJ"), (u".vfb", u"VFB"), (u".ufoz", u"UFOZ"), (u".ufo", u"UFO"),
           (u".glyphs", u"Glyphs"), (u".designspace", u"Designspace"), (u".otf", u"OTF"), (u".ttf", u"TTF"),
           (u".otc", u"OTC"), (u".ttc", u"TTC"), (u".woff2", u"WOFF2"), (u".woff", u"WOFF"), (u".pfb", u"PFB"),
           (u".pfa", u"PFA"))
# The files Add files... offers: every format FontLab 7 opens (a .ufo is a folder: any file in it picks it)
OPEN_FILTER = (u"Fonts (*.vfc *.vfj *.vfb *.ufoz *.glyphs *.designspace *.otf *.ttf *.otc *.ttc *.woff *.woff2 *.pfb "
               u"*.pfa);;UFO folders (*.plist *.glif);;All files (*)")


def file_format(path):
    """A font file's format as the sources' list names it ("VFC", "OTF", "UFO"), from its extension:
    "unsaved" for a font with no file, the extension itself for another."""
    path = (u"%s" % (path or u"")).rstrip(u"/\\")
    if not path:
        return u"unsaved"
    lower = path.lower()
    for extension, name in FORMATS:
        if lower.endswith(extension):
            return name
    extension = os.path.splitext(path)[1]
    return extension[1:].upper() if extension else u"folder"


def font_path_of(picked):
    """The font to open for a file picked in Add files...: the file itself, or the .ufo folder it is in
    (a .ufo is a folder, which a file dialog cannot pick: any file inside it stands for it)."""
    picked = u"%s" % picked
    parts = picked.replace(u"\\", u"/").split(u"/")
    for k in range(len(parts) - 1, 0, -1):
        if parts[k - 1].lower().endswith(u".ufo"):
            return os.path.normpath(u"/".join(parts[:k]))
    return picked


def same_path(a, b):
    """Two paths of one file, whatever their separators and case (FontLab mixes separators)."""
    if not a or not b:
        return False
    norm = lambda p: os.path.normcase(os.path.normpath((u"%s" % p).replace(u"/", os.sep).replace(u"\\", os.sep)))
    return norm(a) == norm(b)


def source_labels(entries):
    """Each source's name in the window, unique: entries [(font name, style, master, masters, file name)].
    A master of a font of several is named by its master, another source by its style (else its master,
    else its font); names that two sources share take the font's name, then the file's, in parentheses,
    then a number."""
    def base(entry):
        font, style, master, masters, file_name = entry
        if masters > 1:
            return master or style or font or u"?"
        return style or master or font or u"?"

    labels = [base(e) for e in entries]

    def twice(found):
        return set(label for label in found if found.count(label) > 1)

    shared = twice(labels)
    if shared:
        labels = [u"%s (%s)" % (label, e[0]) if label in shared and e[0] else label for label, e in zip(labels, entries)]
    shared = twice(labels)
    if shared:
        labels = [u"%s (%s)" % (base(e), u", ".join(part for part in (e[0], e[4]) if part)) if label in shared and e[4]
                  else label for label, e in zip(labels, entries)]
    shared = twice(labels)
    if shared:
        seen = {}
        numbered = []
        for label in labels:
            if label in shared:
                seen[label] = seen.get(label, 0) + 1
                numbered.append(u"%s %d" % (label, seen[label]))
            else:
                numbered.append(label)
        labels = numbered
    return labels


WEIGHT_WORDS = ((u"hairline", 100), (u"thin", 100), (u"extralight", 200), (u"ultralight", 200), (u"light", 300),
                (u"book", 400), (u"regular", 400), (u"normal", 400), (u"roman", 400), (u"plain", 400),
                (u"medium", 500), (u"semibold", 600), (u"demibold", 600), (u"demi", 600), (u"extrabold", 800),
                (u"ultrabold", 800), (u"bold", 700), (u"heavy", 900), (u"black", 900), (u"ultra", 900))
WIDTH_WORDS = ((u"ultracondensed", 1), (u"extracondensed", 2), (u"semicondensed", 4), (u"condensed", 3),
               (u"narrow", 3), (u"compressed", 2), (u"semiexpanded", 6), (u"extraexpanded", 8),
               (u"ultraexpanded", 9), (u"expanded", 7), (u"extended", 7), (u"wide", 7))
ITALIC_WORDS = (u"italic", u"oblique", u"slanted", u"kursiv")


def _squeezed(style):
    return u"".join(ch for ch in (u"%s" % (style or u"")).lower() if ch.isalpha())


def style_weight(style):
    """The weight class a style's name stands for (Bold 700, ExtraLight 200, Italic alone 400); None for
    a name that says nothing of it."""
    text = _squeezed(style)
    for word, value in WEIGHT_WORDS:
        if word in text:
            return value
    if not text or any(word in text for word in ITALIC_WORDS):
        return 400
    return None


def style_width(style):
    """The width class a style's name stands for (Condensed 3, Expanded 7), 5 when it names none."""
    text = _squeezed(style)
    for word, value in WIDTH_WORDS:
        if word in text:
            return value
    return 5


def is_italic(source):
    angle = (source.info or {}).get("italic_angle")
    try:
        if angle is not None and abs(float(angle)) > 0.01:
            return True
    except (TypeError, ValueError):
        pass
    return any(word in _squeezed(source.style or source.label) for word in ITALIC_WORDS)


def weight_of(source):
    """A source's weight class: its font's own (OS/2), else the one its style's name stands for."""
    value = (source.info or {}).get("weight_class")
    try:
        if value:
            return int(value)
    except (TypeError, ValueError):
        pass
    return style_weight(source.style or source.label)


def width_of(source):
    value = (source.info or {}).get("width_class")
    try:
        if value:
            return int(value)
    except (TypeError, ValueError):
        pass
    return style_width(source.style or source.label)


def default_reference(sources):
    """The source the others are compared with to start with: the upright one whose weight is nearest
    Regular's 400 (a style named Regular first), of the normal width; the first source on a tie."""
    if not sources:
        return None

    def rank(pair):
        index, s = pair
        weight = weight_of(s)
        named = _squeezed(s.style or s.label) in (u"regular", u"book", u"roman", u"normal", u"plain")
        return (is_italic(s), not named, abs((weight if weight is not None else 400) - 400), abs(width_of(s) - 5), index)

    return min(enumerate(sources), key=rank)[1].key


def default_ticks(entries, own_font=None):
    """The sources ticked to start with (entries: SourceEntry): the window's own font's masters and every
    font of its family; with no font of its own, the family most open fonts belong to."""
    family = None
    for e in entries:
        if own_font is not None and e.font_number == own_font:
            family = e.family
            break
    if family is None:
        counts = {}
        for e in entries:
            counts[e.family] = counts.get(e.family, 0) + 1
        if counts:
            family = max(sorted(counts), key=lambda name: counts[name])
    return set(e.key for e in entries if (own_font is not None and e.font_number == own_font) or e.family == family)


def match_opened(pending, opened):
    """Files asked to open (pending: their paths, in order) matched with the fonts that came in (opened:
    [(FontLab's number of the font, its path or "")]): by path first; a font without a path (one opened
    from a binary file may give none) taken for the first file still pending, but only once the fonts with
    paths are matched. Returns ([(path, font number)], [paths still pending], [font numbers left over])."""
    pending, matched, left = list(pending), [], []
    unnamed = []
    for number, path in opened:
        found = [p for p in pending if same_path(p, path)]
        if found:
            matched.append((found[0], number))
            pending.remove(found[0])
        elif path:
            left.append(number)
        else:
            unnamed.append(number)
    for number in unnamed:
        if pending:
            matched.append((pending.pop(0), number))
        else:
            left.append(number)
    return matched, pending, left


class SourceEntry(object):
    """A row of the sources' list: a master of an open font. key: (FontLab's number of the font, the
    master's name); family: the font's family name (the ticks to start with)."""

    def __init__(self, font_number, master, label=u"", font=u"", style=u"", masters=1, path=u"", glyphs=0,
                 version=u"", family=None, package=None):
        self.font_number, self.master = font_number, master
        self.key = (font_number, master)
        self.label, self.font, self.style, self.masters = label, font, style, masters
        self.path, self.glyphs, self.version = path, glyphs, version
        self.family = family if family is not None else font
        self.package = package  # (the FontLab font: never read by the logic, only by FontLabCalls)

    @property
    def format(self):
        return file_format(self.path)

    @property
    def file_name(self):
        return os.path.basename((u"%s" % (self.path or u"")).rstrip(u"/\\"))


class Source(object):
    """One source of the audit as read (plain data: read_source makes it from FontLab, the tests by hand).
    glyphs: [(name, [code points])] of the glyphs with a layer in its master, in its font's order;
    shapes: {glyph name: Structure, or None where it could not be read} (None: not read); info: {INFO_FIELDS
    key: value}; kerning: Kerning or None; features: [(tag, code)] (Font Compare's, the prefix first and
    the Classes panel's classes last) or None."""

    def __init__(self, key, label=u"", style=u"", master=u"", glyphs=(), shapes=None, info=None, kerning=None,
                 features=None, font=u"", masters=1, package=None):
        self.key, self.label, self.style, self.master = key, label, style, master
        self.glyphs = [(name, list(codes)) for name, codes in glyphs]
        self.shapes = shapes
        self.info = dict(info or {})
        self.kerning, self.features = kerning, features
        self.font, self.masters = font, masters
        self.package = package

    def names(self):
        return [name for name, _ in self.glyphs]


def family_order(sources, reference_key=None):
    """Every glyph name of the sources once: the reference's in its order, then each other source's own,
    in the order the sources come."""
    ordered = sorted(sources, key=lambda s: 0 if s.key == reference_key else 1)
    seen, order = set(), []
    for s in ordered:
        for name, _ in s.glyphs:
            if name not in seen:
                seen.add(name)
                order.append(name)
    return order


def reference_of(sources, reference_key):
    for s in sources:
        if s.key == reference_key:
            return s
    return sources[0] if sources else None


# ---------------------------------------------------------------------------
# Glyph sets
# ---------------------------------------------------------------------------

class CodeDifference(object):
    """A code point difference: subject (a glyph's name, or a code point's U+ text), kind ("glyph": a name
    with other code points; "code": a code point on glyphs of other names), and its sentence."""

    def __init__(self, subject, kind, text, names=()):
        self.subject, self.kind, self.text = subject, kind, text
        self.names = list(names)  # (the glyphs it is about: shown in a Glyph window)


class GlyphSets(object):
    """missing: [(source label, [names it lacks that another source has])], in the sources' order; codes:
    [CodeDifference]; total: the glyph names of every source."""

    def __init__(self, missing, codes, total):
        self.missing, self.codes, self.total = missing, codes, total

    def lacking(self):
        """The glyph names some source lacks."""
        found = set()
        for _, names in self.missing:
            found.update(names)
        return found


def audit_glyph_sets(sources, reference_key=None):
    order = family_order(sources, reference_key)
    present = dict((s.key, set(s.names())) for s in sources)
    missing = []
    for s in sources:
        lacks = [name for name in order if name not in present[s.key]]
        if lacks:
            missing.append((s.label, lacks))
    codes_by = dict((s.key, dict((name, tuple(sorted(set(codes)))) for name, codes in s.glyphs)) for s in sources)
    found = []
    for name in order:
        seen = [(s.label, codes_by[s.key][name]) for s in sources if name in codes_by[s.key]]
        groups = by_value(seen)
        if len(groups) > 1:
            text = u"; ".join(u"%s in %s" % (codes_text(codes), listed(labels)) for codes, labels in groups)
            found.append(CodeDifference(name, "glyph", text, [name]))
    names_at = {}  # code point: [(label, the glyph names given it there)]
    for s in sources:
        own = {}
        for name, codes in s.glyphs:
            for code in set(codes):
                own.setdefault(code, []).append(name)
        for code, names in own.items():
            names_at.setdefault(code, []).append((s.label, tuple(names)))
    for code in sorted(names_at):
        groups = by_value(names_at[code])
        if len(groups) > 1:
            text = u"; ".join(u"%s in %s" % (u", ".join(names), listed(labels)) for names, labels in groups)
            glyphs = []
            for names, _ in groups:
                glyphs.extend(n for n in names if n not in glyphs)
            found.append(CodeDifference(code_text(code), "code", text, glyphs))
    return GlyphSets(missing, found, len(order))


def glyph_sets_line(report, sources):
    """The Glyph sets tab's status line, its counts in bold with their nouns."""
    if report is None:
        return u""
    lacking = len(report.lacking())
    if not lacking and not report.codes:
        return u"The %s have the same %s, with the same code points." % (
            bold(counted(len(sources), u"source")), bold(counted(report.total, u"glyph")))
    parts = []
    if lacking:
        parts.append(u"%s %s missing from some sources" % (
            bold(u"%s of %s" % (grouped(lacking), counted(report.total, u"glyph"))), u"is" if lacking == 1 else u"are"))
    if report.codes:
        parts.append(u"%s %s" % (bold(counted(len(report.codes), u"code point mapping")),
                                 u"differs" if len(report.codes) == 1 else u"differ"))
    return sentence(u"; ".join(parts))


def sentence(text):
    """text with its first letter capitalized (one inside a tag left as it is) and a period."""
    if text and not text.startswith(u"<"):
        text = text[:1].upper() + text[1:]
    return text + u"." if text else text


# ---------------------------------------------------------------------------
# Compatibility: each glyph's structure, as interpolation needs it alike
# ---------------------------------------------------------------------------

NODE_KINDS = {u"on": u"o", u"line": u"o", u"move": u"o", u"curve": u"c", u"qcurve": u"q", u"off": u"x",
              u"offcurve": u"x"}
KIND_NAMES = {u"o": u"on", u"c": u"curve", u"q": u"qcurve", u"x": u"off"}
# The kinds of difference, in the order they are looked for (the first found is the glyph's)
COMPAT_KINDS = ("contours", "components", "nodes", "types", "direction", "anchors", "unread")
COMPAT_GROUPS = {"contours": u"Contour counts differ", "components": u"Components differ",
                 "nodes": u"Node counts differ", "types": u"Node types differ",
                 "direction": u"Contour directions differ", "anchors": u"Anchors differ",
                 "unread": u"Could not be read"}


def node_kind(node_type):
    text = (u"%s" % node_type).lower()
    return NODE_KINDS.get(text, text[:1] or u"?")


def direction(points):
    """1 for a contour that runs counterclockwise (y up), -1 clockwise, 0 for one with no area: the sign of
    its area, every point counted (off-curve points too)."""
    area = 0.0
    count = len(points)
    for k in range(count):
        x0, y0 = float(points[k][0]), float(points[k][1])
        x1, y1 = float(points[(k + 1) % count][0]), float(points[(k + 1) % count][1])
        area += x0 * y1 - x1 * y0
    return 1 if area > 1e-6 else (-1 if area < -1e-6 else 0)


class Structure(object):
    """A glyph's layer as interpolation looks at it: contours [(node kinds, one letter a node: o on, c
    curve, q qcurve, x off), direction)], components [glyph names, in order], anchors [names, sorted]."""

    def __init__(self, contours=(), components=(), anchors=()):
        self.contours = [(u"%s" % kinds, int(turn)) for kinds, turn in contours]
        self.components = [u"%s" % name for name in components]
        self.anchors = sorted(u"%s" % name for name in anchors)


def structure_of(contours, components=(), anchors=()):
    """The Structure of a layer read as Font Compare reads it: contours [[(x, y, type)]], components
    [(glyph name, matrix)] or [glyph name], anchors [(name, x, y)] or [name]."""
    shaped = [(u"".join(node_kind(p[2] if len(p) > 2 else u"on") for p in c), direction(c)) for c in contours]
    names = [c[0] if isinstance(c, (tuple, list)) else c for c in components]
    pins = [a[0] if isinstance(a, (tuple, list)) else a for a in anchors]
    return Structure(shaped, names, pins)


def compare_structures(a, b, label_a, label_b):
    """(kind, sentence) of the first way two structures differ (COMPAT_KINDS' order), or None when they
    match."""
    if len(a.contours) != len(b.contours):
        return "contours", u"%s in %s, %d in %s" % (counted(len(a.contours), u"contour"), label_a, len(b.contours), label_b)
    if a.components != b.components:
        if sorted(a.components) == sorted(b.components):
            return "components", u"components in another order in %s" % label_b
        return "components", u"components %s in %s, %s in %s" % (
            u", ".join(a.components) or u"none", label_a, u", ".join(b.components) or u"none", label_b)
    for number, ((kinds_a, _), (kinds_b, _)) in enumerate(zip(a.contours, b.contours), 1):
        if len(kinds_a) != len(kinds_b):
            return "nodes", u"contour %d: %s in %s, %d in %s" % (number, counted(len(kinds_a), u"node"), label_a,
                                                                 len(kinds_b), label_b)
    for number, ((kinds_a, _), (kinds_b, _)) in enumerate(zip(a.contours, b.contours), 1):
        if kinds_a != kinds_b:
            at = next(k for k, (p, q) in enumerate(zip(kinds_a, kinds_b)) if p != q)
            return "types", u"contour %d, node %d: %s in %s, %s in %s" % (
                number, at + 1, KIND_NAMES.get(kinds_a[at], kinds_a[at]), label_a,
                KIND_NAMES.get(kinds_b[at], kinds_b[at]), label_b)
    for number, ((_, turn_a), (_, turn_b)) in enumerate(zip(a.contours, b.contours), 1):
        if turn_a and turn_b and turn_a != turn_b:
            return "direction", u"contour %d runs the other way in %s" % (number, label_b)
    if a.anchors != b.anchors:
        only_a = [n for n in a.anchors if n not in b.anchors]
        only_b = [n for n in b.anchors if n not in a.anchors]
        parts = []
        if only_a:
            parts.append(u"%s %s only in %s" % (u"anchor" if len(only_a) == 1 else u"anchors", listed(only_a), label_a))
        if only_b:
            parts.append(u"%s %s only in %s" % (u"anchor" if len(only_b) == 1 else u"anchors", listed(only_b), label_b))
        return "anchors", u"; ".join(parts) or u"anchors differ"
    return None


class GlyphCompat(object):
    """A glyph compared across the sources that have it: kind (a COMPAT_KINDS key, or None: compatible),
    the sentence of its first difference, and the source it was found in."""

    def __init__(self, name, kind=None, text=u"", against=u"", sources=()):
        self.name, self.kind, self.text, self.against = name, kind, text, against
        self.sources = list(sources)  # (the labels of the sources that have it)


class Compatibility(object):
    """results: [GlyphCompat] of the glyphs in at least two sources, in the family's order; single: the
    glyphs in one source only (nothing to compare them with)."""

    def __init__(self, results, single):
        self.results, self.single = results, single

    def compatible(self):
        return [r for r in self.results if r.kind is None]

    def incompatible(self):
        return [r for r in self.results if r.kind is not None]

    def by_kind(self):
        found = {}
        for r in self.incompatible():
            found.setdefault(r.kind, []).append(r)
        return found


def audit_compatibility(sources, reference_key=None):
    """Each glyph in at least two sources compared, each source with the reference (or, where the
    reference lacks it, with the first source that has it): compatible, or the first difference found."""
    base_first = sorted(sources, key=lambda s: 0 if s.key == reference_key else 1)
    order = family_order(sources, reference_key)
    results, single = [], []
    for name in order:
        having = [s for s in base_first if s.shapes is not None and name in s.shapes]
        if len(having) < 2:
            single.append(name)
            continue
        base = having[0]
        labels = [s.label for s in having]
        if base.shapes[name] is None:
            results.append(GlyphCompat(name, "unread", u"not read in %s" % base.label, base.label, labels))
            continue
        found = None
        for other in having[1:]:
            if other.shapes[name] is None:
                found = GlyphCompat(name, "unread", u"not read in %s" % other.label, other.label, labels)
                break
            difference = compare_structures(base.shapes[name], other.shapes[name], base.label, other.label)
            if difference is not None:
                found = GlyphCompat(name, difference[0], difference[1], other.label, labels)
                break
        results.append(found or GlyphCompat(name, None, u"", u"", labels))
    return Compatibility(results, single)


def compatibility_line(report):
    """The Compatibility tab's status line: how many glyphs match in structure, and no promise more."""
    if report is None:
        return u""
    total = len(report.results)
    if not total:
        return u"No glyph is in two sources: there is nothing to compare."
    good = len(report.compatible())
    return (u"%s match in structure (contours, nodes, components, and anchors). That is needed for them to "
            u"interpolate, but does not promise it: start points, contour order, and shapes are not compared."
            % bold(u"%s of %s" % (grouped(good), counted(total, u"glyph"))))


# ---------------------------------------------------------------------------
# Metrics and info
# ---------------------------------------------------------------------------

# (key, label, kind): "family" should be the same in every source of a family, "style" may differ by style
INFO_FIELDS = (("family", u"Family name", "family"), ("style", u"Style name", "style"), ("version", u"Version", "family"),
               ("upm", u"Units per em", "family"), ("ascender", u"Ascender", "family"),
               ("descender", u"Descender", "family"), ("x_height", u"x-height", "style"),
               ("cap_height", u"Cap height", "style"), ("line_gap", u"Line gap", "family"),
               ("typo_ascender", u"Typo ascender", "family"), ("typo_descender", u"Typo descender", "family"),
               ("typo_line_gap", u"Typo line gap", "family"), ("hhea_ascender", u"hhea ascender", "family"),
               ("hhea_descender", u"hhea descender", "family"), ("hhea_line_gap", u"hhea line gap", "family"),
               ("win_ascent", u"winAscent", "family"), ("win_descent", u"winDescent", "family"),
               ("italic_angle", u"Italic angle", "style"), ("weight_class", u"Weight class", "style"),
               ("width_class", u"Width class", "style"))
INFO_GROUPS = (("mismatch", u"Should match, but differ"), ("style", u"Differ by style"), ("same", u"Alike"))


class InfoRow(object):
    """A field of the font info across the sources: key, label, its group (INFO_GROUPS' key), and
    values [(source label, text)] ("" for a value a source does not give)."""

    def __init__(self, key, label, group, values):
        self.key, self.label, self.group, self.values = key, label, group, values


def audit_info(sources):
    rows = []
    for key, label, kind in INFO_FIELDS:
        values = [(s.label, number_text((s.info or {}).get(key))) for s in sources]
        if not any(text for _, text in values):
            continue  # (no source gives it: not listed)
        differs = len(set(text for _, text in values)) > 1
        rows.append(InfoRow(key, label, ("mismatch" if kind == "family" else "style") if differs else "same", values))
    return rows


def info_line(rows):
    if rows is None:
        return u""
    mismatch = [r for r in rows if r.group == "mismatch"]
    style = [r for r in rows if r.group == "style"]
    if not mismatch and not style:
        return u"%s %s alike in every source." % (bold(counted(len(rows), u"field")), u"is" if len(rows) == 1 else u"are")
    parts = []
    if mismatch:
        parts.append(u"%s that should match across a family %s (%s)" % (
            bold(counted(len(mismatch), u"field")), u"differs" if len(mismatch) == 1 else u"differ",
            u", ".join(r.label for r in mismatch)))
    if style:
        parts.append(u"%s %s by style" % (bold(counted(len(style), u"field")), u"differs" if len(style) == 1 else u"differ"))
    return sentence(u"; ".join(parts))


# ---------------------------------------------------------------------------
# Kerning
# ---------------------------------------------------------------------------

class Kerning(object):
    """A source's kerning as plain data: classes {name: (side, [members])} (side: FontLab's KernLeft,
    KernRight, or KernBothSide), values {entry: value}, an entry ((left, is class), (right, is class))."""

    def __init__(self, classes=None, values=None):
        self.classes = dict((name, (side, list(members))) for name, (side, members) in (classes or {}).items())
        self.values = dict(values or {})


def kerning_of(font_kerning):
    """Kerning from the shared module's FontKerning (a master's kerning as FontLab gives it)."""
    classes = dict((name, (font_kerning.class_flags.get(name), list(font_kerning.members.get(name, []))))
                   for name in font_kerning.classes)
    return Kerning(classes, dict((entry, font_kerning.values.get(entry)) for entry in font_kerning.entries))


def describe_entry(entry):
    side = lambda name, is_class: (u"class %s" % name) if is_class else name
    return u"%s %s %s" % (side(*entry[0]), TIMES, side(*entry[1]))


def round_units(value):
    import math
    return int(math.floor(float(value) + 0.5))


class KernFinding(object):
    """A kerning difference: kind ("none": a source with no kerning; "class": a class missing from some
    sources or with other members; "missing": an entry only some sources kern; "sign": an entry that
    tightens in one source and loosens in another), its subject, values [(label, text)], and why."""

    def __init__(self, kind, subject, values, reason, names=()):
        self.kind, self.subject, self.values, self.reason = kind, subject, values, reason
        self.names = list(names)


# (kind, its group's title, its noun and plural, what the status line says of them)
KERN_GROUPS = (("none", u"Sources without kerning", u"source", None, u"without kerning"),
               ("class", u"Classes that differ", u"class", u"classes", u"with members that differ"),
               ("missing", u"Kerned in some sources only", u"entry", u"entries", u"kerned in some sources only"),
               ("sign", u"Tightening in one, loosening in another", u"entry", u"entries",
                u"tightening in one source and loosening in another"))


def audit_kerning(sources, reference_key=None, tolerance=SIGN_TOLERANCE):
    """[KernFinding] across the sources' kerning (a source whose kerning was not read is left out; one
    with none is said once, and left out of the rest, which would list its every entry)."""
    found = []
    read = [s for s in sorted(sources, key=lambda s: 0 if s.key == reference_key else 1) if s.kerning is not None]
    kerned = []
    for s in read:
        if not s.kerning.values and not s.kerning.classes:
            found.append(KernFinding("none", s.label, [(s.label, DASH)], u"no kerning"))
        else:
            kerned.append(s)
    if len(kerned) < 2:
        return found
    names = ordered_union(sorted(s.kerning.classes) for s in kerned)
    for name in names:
        sets = [(s.label, s.kerning.classes[name][1] if name in s.kerning.classes else None) for s in kerned]
        present = [(label, members) for label, members in sets if members is not None]
        if len(set(frozenset(m) for _, m in present)) < 2 and len(present) == len(sets):
            continue
        values = [(label, DASH if members is None else counted(len(members), u"glyph")) for label, members in sets]
        reasons = []
        lacking = [label for label, members in sets if members is None]
        if lacking:
            reasons.append(u"not in %s" % listed(lacking))
        base_label, base = present[0]
        for label, members in present[1:]:
            lacks = [m for m in base if m not in members]
            adds = [m for m in members if m not in base]
            if lacks:
                reasons.append(u"%s lacks %s" % (label, names_text(lacks)))
            if adds:
                reasons.append(u"%s adds %s" % (label, names_text(adds)))
        found.append(KernFinding("class", u"class %s" % name, values, u"; ".join(reasons), base))
    entries = ordered_union(sorted(s.kerning.values, key=describe_entry) for s in kerned)
    for entry in entries:
        values = [(s.label, round_units(s.kerning.values[entry]) if entry in s.kerning.values and
                   s.kerning.values[entry] is not None else None) for s in kerned]
        shown = [(label, DASH if value is None else u"%d" % value) for label, value in values]
        glyphs = [name for name, is_class in entry if not is_class]
        lacking = [label for label, value in values if value is None]
        known = [value for _, value in values if value is not None]
        if lacking:
            found.append(KernFinding("missing", describe_entry(entry), shown, u"not kerned in %s" % listed(lacking), glyphs))
        elif min(known) < -tolerance and max(known) > tolerance:
            found.append(KernFinding("sign", describe_entry(entry), shown,
                                     u"tightens in one source, loosens in another: an instance between them may "
                                     u"collide", glyphs))
    return found


def ordered_union(lists):
    """The items of several lists, each once, in the order they first come."""
    seen, found = set(), []
    for items in lists:
        for item in items:
            if item not in seen:
                seen.add(item)
                found.append(item)
    return found


def kerning_line(findings, sources):
    if findings is None:
        return u""
    unread = [s for s in sources if s.kerning is None]
    tail = u" The kerning of %s could not be read." % listed([bold(s.label) for s in unread]) if unread else u""
    if not findings:
        return u"The %s kern the same entries, with the same signs, and their classes hold the same glyphs.%s" % (
            bold(counted(len(sources), u"source")), tail)
    counts = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    parts = [u"%s %s" % (bold(counted(counts[kind], noun, many)), phrase)
             for kind, _, noun, many, phrase in KERN_GROUPS if counts.get(kind)]
    return sentence(listed(parts)) + tail


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

class FeatureState(object):
    """A feature in one source: its label, kind (only_a: the source lacks it; differs; same: as the
    reference's), the Difference column's text, and the lines that differ (Font Compare's line_diff)."""

    def __init__(self, label, kind, text, rows=(), code=None):
        self.label, self.kind, self.text, self.rows, self.code = label, kind, text, list(rows), code


class FeatureFinding(object):
    """A feature across the sources: tag (or Font Compare's PREFIX or CLASSES), kind ("missing": some
    source lacks it; "differs": some has other code; "same"), the source it is compared with, and a
    FeatureState per other source."""

    def __init__(self, tag, kind, base, states):
        self.tag, self.kind, self.base, self.states = tag, kind, base, states


def audit_features(sources, reference_key=None, fcmp=None):
    """[FeatureFinding] of the sources' features (sources whose features were not read left out), each
    source's code compared with the reference's (or the first source that has it), as Font Compare
    compares two fonts' (its code_lines and line_diff)."""
    fcmp = fcmp or compare_module()
    read = [s for s in sorted(sources, key=lambda s: 0 if s.key == reference_key else 1) if s.features is not None]
    if len(read) < 2:
        return []
    by_source = dict((s.key, dict(s.features)) for s in read)
    tags = []
    for s in read:
        tags.extend(t for t, _ in s.features if t not in tags)
    tags.sort(key=lambda t: {fcmp.PREFIX: 0, fcmp.CLASSES: 2}.get(t, 1))  # (a stable sort: the fonts' order kept)
    found = []
    for tag in tags:
        having = [s for s in read if tag in by_source[s.key]]
        base = having[0]
        base_code = by_source[base.key][tag]
        states = []
        for s in read:
            if s is base:
                continue
            code = by_source[s.key].get(tag)
            if code is None:
                rows = [(u"-", line) for line in fcmp.code_lines(base_code)]
                states.append(FeatureState(s.label, "only_a", u"not in %s" % s.label, rows))
                continue
            rows = fcmp.line_diff(base_code, code)
            kind = "differs" if rows else "same"
            text = fcmp.feature_state(fcmp.FeatureDifference(tag, kind, base_code, code, rows), (base.label, s.label))
            states.append(FeatureState(s.label, kind, text, rows, code))
        kinds = set(state.kind for state in states)
        kind = "missing" if "only_a" in kinds else ("differs" if "differs" in kinds else "same")
        found.append(FeatureFinding(tag, kind, base.label, states))
    return found


FEATURE_GROUPS = (("missing", u"Missing from some sources"), ("differs", u"Code that differs"), ("same", u"Alike"))


def features_line(findings, sources):
    if findings is None:
        return u""
    if not findings:
        return u"The sources have no feature code." if sources else u""
    missing = sum(1 for f in findings if f.kind == "missing")
    differs = sum(1 for f in findings if f.kind == "differs")
    if not missing and not differs:
        return u"%s %s alike in every source." % (bold(counted(len(findings), u"feature")),
                                                  u"is" if len(findings) == 1 else u"are")
    parts = []
    if missing:
        parts.append(u"%s missing from some sources" % bold(counted(missing, u"feature")))
    if differs:
        parts.append(u"%s with code that differs" % bold(counted(differs, u"feature")))
    return sentence(u"; ".join(parts))


# ---------------------------------------------------------------------------
# The audit, whole
# ---------------------------------------------------------------------------

class Audit(object):
    """Every tab's findings for the sources (keys: the sources' keys, in order) and the reference."""

    def __init__(self, sources, reference_key, fcmp=None):
        self.keys = [s.key for s in sources]
        self.labels = [s.label for s in sources]
        self.reference = reference_key
        self.glyph_sets = audit_glyph_sets(sources, reference_key)
        self.compatibility = audit_compatibility(sources, reference_key)
        self.info = audit_info(sources)
        self.kerning = audit_kerning(sources, reference_key)
        self.features = audit_features(sources, reference_key, fcmp)

    def counts(self):
        """{tab key: the count its tab shows}: what differs."""
        return {"glyphs": len(self.glyph_sets.lacking()) + len(self.glyph_sets.codes),
                "compatibility": len(self.compatibility.incompatible()),
                "metrics": sum(1 for r in self.info if r.group != "same"),
                "kerning": len(self.kerning),
                "features": sum(1 for f in self.features if f.kind != "same")}


# ---------------------------------------------------------------------------
# Assemble as masters: the plan (which layer goes where, what stays empty, what is not carried over)
# ---------------------------------------------------------------------------

class Axis(object):
    """An axis of the new font: its name, tag, and each master's location on it {master: value}."""

    def __init__(self, name, tag, locations):
        self.name, self.tag, self.locations = name, tag, dict(locations)

    @property
    def range(self):
        values = list(self.locations.values())
        return min(values), max(values)


class AssemblyPlan(object):
    """What Assemble as masters makes: masters [(master name, source key)] (the reference's first: the
    default master); order: the glyphs, the reference's order first; layers {glyph: [masters that get its
    layer]}; empty [(master, [glyphs left empty there])]; codes {glyph: [code points]}; axes [Axis];
    notes: what is not carried over, known before the font is made."""

    def __init__(self):
        self.masters, self.order, self.layers, self.empty, self.codes, self.axes, self.notes = [], [], {}, [], {}, [], []
        self.reference = self.matched = None  # (matched: (glyphs that matched in structure at the audit, compared))


def axes_of(sources, masters):
    """The axes of the new font: Weight (wght) when the sources' weight classes differ, Width (wdth) when
    their width classes do, each master located at its source's class; none when they are alike.
    masters: {source key: master name}."""
    found = []
    for name, tag, read in ((u"Weight", u"wght", weight_of), (u"Width", u"wdth", width_of)):
        values = dict((masters[s.key], read(s)) for s in sources)
        if any(v is None for v in values.values()):
            values = dict((k, v if v is not None else 400) for k, v in values.items())
        if len(set(values.values())) > 1:
            found.append(Axis(name, tag, values))
    return found


def plan_assembly(sources, reference_key, compatibility=None):
    """The AssemblyPlan for the sources (Source, read with their kerning, features, and info; their shapes
    are not needed), the reference's master first. compatibility: the audit's, for the note on how many
    glyphs matched (never a promise that they interpolate)."""
    plan = AssemblyPlan()
    ordered = sorted(sources, key=lambda s: 0 if s.key == reference_key else 1)
    reference = ordered[0]
    plan.reference = reference.key
    plan.masters = [(s.label, s.key) for s in ordered]
    masters = dict((s.key, s.label) for s in ordered)
    plan.order = family_order(ordered, reference.key)
    present = dict((s.key, set(s.names())) for s in ordered)
    for name in plan.order:
        plan.layers[name] = [masters[s.key] for s in ordered if name in present[s.key]]
    for s in ordered:
        lacks = [name for name in plan.order if name not in present[s.key]]
        if lacks:
            plan.empty.append((masters[s.key], lacks))
    conflicts = []
    codes_of = dict((s.key, dict(s.glyphs)) for s in ordered)
    for name in plan.order:
        having = [s for s in ordered if name in codes_of[s.key]]
        plan.codes[name] = sorted(set(codes_of[having[0].key][name]))
        if len(set(tuple(sorted(set(codes_of[s.key][name]))) for s in having)) > 1:
            conflicts.append(name)
    if conflicts:
        plan.notes.append(u"Code points that differ between the sources: the %s of %s kept (%s)." % (
            u"glyph's" if len(conflicts) == 1 else u"glyphs'", reference.label, names_text(conflicts)))
    plan.axes = axes_of(ordered, masters)
    if plan.axes:
        where = u"%s axis" % plan.axes[0].name.lower() if len(plan.axes) == 1 else u"axes"
        spots = by_value([(name, tuple(axis.locations[name] for axis in plan.axes)) for name, _ in plan.masters])
        for spot, names in spots:
            if len(names) > 1:
                plan.notes.append(u"%s share one location on the %s: an italic, or another style, needs an axis of "
                                  u"its own, which FreeLab does not set." % (listed(names), where))
    upms = by_value([(s.label, number_text((s.info or {}).get("upm"))) for s in ordered])
    if len(upms) > 1:
        plan.notes.append(u"The sources have other units per em (%s): every layer is copied unscaled, at its own "
                          u"source's." % u"; ".join(u"%s in %s" % (upm or u"unknown", listed(labels)) for upm, labels in upms))
    if reference.features is not None:
        others = [s for s in ordered[1:] if s.features and dict(s.features) != dict(reference.features)]
        if others:
            plan.notes.append(u"Feature code, its classes, and the font info come from %s alone: %s %s other code, "
                              u"not carried over." % (reference.label, listed([s.label for s in others]),
                                                      u"has" if len(others) == 1 else u"have"))
    if compatibility is not None and compatibility.results:
        plan.matched = (len(compatibility.compatible()), len(compatibility.results))
    return plan


def component_order(components):
    """Glyph names in an order where a glyph comes after the glyphs its components draw (components:
    {glyph: [component glyph names]}): FontLab builds a component from its glyph as it is then, and one
    made before its glyph was drawn stayed empty. A loop is broken where it closes."""
    order, state = [], {}

    def visit(name, depth=0):
        if state.get(name) or depth > 64:
            return
        state[name] = 1  # (on the way: a loop back to it stops here)
        for base in components.get(name, ()):
            if base in components:
                visit(base, depth + 1)
        state[name] = 2
        order.append(name)

    for name in components:
        visit(name)
    return order


# ---------------------------------------------------------------------------
# FontLab: every call in one place, one method a call, each saying what it assumes. "Proven" names a
# call FreeLab or FreeLab MCP has run live in FontLab 7.2 (FreeLab MCP's docs/FONTLAB7-API.md); "Assumed"
# one documented or seen in dir() but not yet run: docs/FAMILY-AUDIT.md lists how to check each.
# ---------------------------------------------------------------------------

class FontLabCalls(object):
    """The FontLab calls of the audit and the assembly. Tests replace it with a fake."""

    def __init__(self, fontlab, ak=None, fcmp=None):
        self.fontlab, self.ak, self.fcmp = fontlab, ak, fcmp
        self.held = []  # (the glyphs and anchors Python made for the new font, held: see new_glyph)

    def qt(self):
        from PythonQt import QtCore, QtGui
        return QtCore, QtGui

    # -- reading ---------------------------------------------------------------

    def open_packages(self):
        """Proven: flWorkspace.instance().packages() lists the open fonts as flObjects, fontlab.flPackage(item)
        wraps each (never flPackage() with no argument: that makes a font). Fonts with no glyphs (FontLab's
        placeholder with no font open) left out."""
        found = []
        for item in list(self.fontlab.flWorkspace.instance().packages() or []):
            try:
                package = self.fontlab.flPackage(item)
                if package is None or package.isNull or not package.glyphsCount:
                    continue
                found.append(package)
            except Exception:
                continue
        return found

    @staticmethod
    def font_number(package):
        """Proven: fgPackage.id, FontLab's number of an open font, the same through every wrapper."""
        try:
            return package.fgPackage.id
        except Exception:
            return None

    @staticmethod
    def masters(package):
        """Proven: flPackage.masters, a list of the masters' names (master: the current one's)."""
        try:
            found = [u"%s" % name for name in package.masters]
        except Exception:
            found = []
        if not found:
            try:
                found = [u"%s" % package.master]
            except Exception:
                found = []
        return found

    @staticmethod
    def names(package):
        """(family, style) of a font. The family is flPackage.tfn (FontLab's family name: live, the typographic
        family), else fgPackage.info.familyName: for a variable TTF that is its name ID 1 (live, 2026-11-19:
        NotoSansJP[wght].ttf gave "Noto Sans JP Thin" there and "Noto Sans JP" in tfn, so it was taken for another
        family than its own static instance). The style is fgPackage.info.styleName (its typographic subfamily,
        "Thin" there), else flPackage.tsn."""
        family = style = u""
        try:
            family = u"%s" % (package.tfn or u"")
        except Exception:
            pass
        try:
            info = package.fgPackage.info
            family = family or u"%s" % (getattr(info, "familyName", None) or u"")
            style = u"%s" % (getattr(info, "styleName", None) or u"")
        except Exception:
            pass
        try:
            style = style or u"%s" % (package.tsn or u"")
        except Exception:
            pass
        return family.strip(), style.strip()

    @staticmethod
    def path(package):
        """Proven: flPackage.path (mixed separators; empty for an unsaved font)."""
        try:
            return u"%s" % (package.path or u"")
        except Exception:
            return u""

    @staticmethod
    def version(package):
        """Proven: flPackage.versionMajor and versionMinor: "1.002"."""
        try:
            return u"%d.%03d" % (int(package.versionMajor), int(package.versionMinor))
        except Exception:
            return u""

    def glyph_list(self, package):
        """Proven: fgPackage.glyphs, each with name and unicodes (every code point: Font Compare's glyph_codes)."""
        return [(u"%s" % fg.name, self.fcmp.glyph_codes(fg)) for fg in package.fgPackage.glyphs]

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

    def structure(self, name, layer):
        """A layer's Structure, as Font Compare's read_layer reads it (proven: shapes, isComponent,
        shapeData.componentGlyph, contours, nodes(), node.type, anchors and their names). None when it
        cannot be read."""
        data = self.fcmp.read_layer(name, [], layer)
        if data is None:
            return None
        return structure_of(data.contours, data.components, data.anchors)

    def kerning(self, package, master):
        """Proven: flPackage.kerning(master), read through the shared module's FontKerning (its items, and
        groups with their members and sides)."""
        return kerning_of(self.ak.FontKerning(package.kerning(master)))

    def features(self, package):
        """Proven: fgPackage.features (keys, get_feature, get_prefix) and getAllGroups' feature classes,
        through Font Compare's features_of."""
        return self.fcmp.CompareDialog.features_of(package)

    def info(self, package, master):
        """{INFO_FIELDS key: value} of a source. The font info's OpenType values are fgPackage.info's UFO
        names (Font Check reads them so; italicAngle, openTypeOS2WeightClass, and openTypeOS2WidthClass
        assumed alike). The line metrics (ascender_value, descender_value, xHeight_value, capsHeight_value,
        lineGap_value: Font Check's) are the CURRENT master's: for another master of the font they are left
        out (None), FontLab giving no other master's to a script that does not switch masters, which this
        tool never does to a source."""
        found = {}
        family, style = self.names(package)
        if len(self.masters(package)) > 1:
            style = master  # (a master of a font of several stands for a style)
        found["family"], found["style"] = family or None, style or None
        found["version"] = self.version(package) or None

        def value(obj, attribute):
            try:
                read = getattr(obj, attribute)
                read = read() if callable(read) else read
                return float(read) if read is not None and read != u"" else None
            except Exception:
                return None

        found["upm"] = value(package, "upm")
        try:
            current = u"%s" % package.master
        except Exception:
            current = None
        if current == master or len(self.masters(package)) < 2:
            for key, attribute in (("ascender", "ascender_value"), ("descender", "descender_value"),
                                   ("x_height", "xHeight_value"), ("cap_height", "capsHeight_value"),
                                   ("line_gap", "lineGap_value")):
                found[key] = value(package, attribute)
        try:
            info = package.fgPackage.info
        except Exception:
            info = None
        several = len(self.masters(package)) > 1
        for key, attribute in INFO_ATTRIBUTES:
            if several and key in MASTER_INFO:
                found[key] = None  # (the font's, not each master's: its master's name tells instead, style_weight)
                continue
            found[key] = value(info, attribute) if info is not None else None
        for key, attribute in COVERAGE_ATTRIBUTES:  # (bit lists, live 2026-11-18: [0L, 1L, 4L])
            try:
                found[key] = [int(bit) for bit in (getattr(info, attribute) or [])]
            except Exception:
                found[key] = None
        return found

    def font_info_module(self):
        """The shared module that keeps the font info's coverage in step (freelab_font_info, through Auto
        Kerning's font_info), or None."""
        try:
            return self.ak.font_info()
        except Exception:
            return None

    # -- opening ---------------------------------------------------------------

    def request_font(self, path):
        """Proven: fontlab.flItems.requestLoadingFont(path) opens a font file in FontLab, in the background
        (the font is listed among the open fonts later); it may wait on a modal question first (Cardo's
        Coordinates Rounding)."""
        self.fontlab.flItems.requestLoadingFont(path)

    # -- the new font ----------------------------------------------------------

    def new_package(self):
        """Proven: fontlab.flPackage() with no argument makes a new, empty font, added to FontLab's
        workspace as the current one (FreeLab never closes it: closing the current font crashed FontLab)."""
        return self.fontlab.flPackage()

    @staticmethod
    def rename_master(package, old, new):
        """Live (2026-11-24, Sarabun Regular and Bold assembled): flPackage.renameMaster(old name, new name)."""
        package.renameMaster(old, new)

    @staticmethod
    def add_master(package, name):
        """Live (2026-11-18): flPackage.addMaster(string master_name, bool create_glyphs, flPackage source,
        string source_layer_name, bool copy_metrics, bool create_missing_glyphs[, flLocation location]). The
        source must be a font (None was refused: "flPackage expected"): the new font itself, nothing copied."""
        package.addMaster(name, False, package, u"", False, False)

    @staticmethod
    def set_current_master(package, name):
        """Live (2026-11-18): flPackage.setMaster(name[, notify]) (assigning flPackage.master is refused:
        "attribute 'master' of 'flPackage' objects is not writable"); the line metrics then read and write
        that master's."""
        package.setMaster(name)

    def new_glyph(self, package, name):
        """Proven: fontlab.flGlyph(), its name set, flPackage.addGlyph() (FontLab adds a copy, without
        layers), then flPackage.findName(name) for the font's own glyph, on which layers are made. The
        Python-made glyph is held (Glyph Compose's new_glyph: a closing crash's suspect)."""
        there = package.findName(name)
        if there is not None and not there.isNull:
            return there  # (a new font comes with its .notdef: added again, it was there twice, live)
        made = self.fontlab.flGlyph()
        made.name = name
        self.held.append(made)
        package.addGlyph(made)
        glyph = package.findName(name)
        return glyph if glyph is not None and not glyph.isNull else None

    @staticmethod
    def init_layer(package, layer):
        """Live (2026-11-18): a new glyph's new layer given its (empty) components at once, as Font Builder
        does: without it, setting the glyph's code point crashed FontLab (fgGlyph.unicode = 32 on a glyph
        whose layer was only made and given a width; with this call first, unicode and unicodes both held)."""
        layer.setGlyphComponents([], float(package.upm) / 2.0, package, False)

    @staticmethod
    def new_layer(glyph, master):
        """Proven: flGlyph.getLayerByName(master, True) makes the layer when the glyph has none there."""
        return glyph.getLayerByName(master, True)

    @staticmethod
    def components(layer):
        """[(glyph name, QTransform)] of a layer's components, in order. Proven: flLayer.shapes,
        flShape.isComponent, shapeData.componentGlyph, transform."""
        parts = []
        for shape in list(layer.shapes):
            try:
                if bool(shape.isComponent):
                    parts.append((u"%s" % shape.shapeData.componentGlyph, shape.transform))
            except Exception:
                continue
        return parts

    def copy_contours(self, layer, target):
        """A layer's own contours (not its components: set_components) copied to target, shape by shape;
        returns how many shapes. Proven: flShape.contours, flContour.clone() (a copy of its nodes),
        fontlab.flShape(), flShape.addContours(contours, True), flLayer.addShape (Feature Code's figure
        forms). Assumed: a new shape's transform is settable (the source shape's is copied: its contours
        are in its own coordinates). Nothing of a source is shared with the new font (a shape added as it
        is would share its data with the source's)."""
        count = 0
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
            count += 1
        return count

    def set_components(self, package, target, parts, width):
        """Proven: fontlab.GlyphComponent(name) with its transform, then flLayer.setGlyphComponents(list,
        width, package, False) (it builds a component only where its glyph has a layer in that master).
        Live (2026-11-26): it replaces every shape of the layer, contours added before it included, so the
        layer's contours are copied after it (copy_contours: both stay)."""
        made = []
        for name, transform in parts:
            component = self.fontlab.GlyphComponent(name)
            component.transform = transform
            made.append(component)
        target.setGlyphComponents(made, float(width), package, False)

    def copy_anchors(self, layer, target):
        """Proven: flLayer.anchors (an anchor's name and point), fontlab.flPinPoint(QPointF), its name set,
        flLayer.addAnchor(pin) (FontLab keeps the very pin: held here too)."""
        QtCore = self.qt()[0]
        count = 0
        for anchor in list(layer.anchors):
            point = anchor.point
            pin = self.fontlab.flPinPoint(QtCore.QPointF(float(point.x()), float(point.y())))
            pin.name = u"%s" % anchor.name
            self.held.append(pin)
            target.addAnchor(pin)
            count += 1
        return count

    @staticmethod
    def width(layer):
        """Proven: flLayer.advanceWidth."""
        return float(layer.advanceWidth)

    @staticmethod
    def set_width(target, width):
        """Proven: flLayer.advanceWidth is settable (whole units kept)."""
        target.advanceWidth = float(width)

    @staticmethod
    def find_glyph(package, name):
        """The font's glyph of that name, looked up NOW: a glyph object kept while more glyphs were added
        points into storage FontLab has moved since (live, 2026-11-18: setting the code points of glyphs
        kept from their adding crashed FontLab; Glyph Compose looks its glyphs up again too). None
        without one."""
        glyph = package.findName(name)
        return glyph if glyph is not None and not glyph.isNull else None

    @staticmethod
    def set_codes(glyph, codes):
        """Live (2026-11-18): fgGlyph.unicode, then fgGlyph.unicodes for more than one, on a glyph looked up
        again (find_glyph) whose layers were set up by init_layer (without it FontLab crashed here)."""
        codes = [int(c) for c in codes]
        glyph.fgGlyph.unicode = codes[0]
        if len(codes) > 1:
            glyph.fgGlyph.unicodes = codes

    @staticmethod
    def update_glyph(glyph):
        """Proven: flGlyph.update() (layer values set in bulk were kept only after it)."""
        glyph.update()

    @staticmethod
    def target_kerning(package, master):
        """Proven: flPackage.kerning(master), an fgKerning."""
        return package.kerning(master)

    @staticmethod
    def set_kerning_class(kerning, name, members, side):
        """Proven: fgKerning.groups[name] = (members, side) makes a kerning class (side KernLeft, KernRight,
        or KernBothSide)."""
        kerning.groups[name] = (list(members), side)

    def write_kerning(self, kerning, entries):
        """Proven: the shared module's FontKerning.write (kerning[(left, right)] = value, a glyph named
        like a class written with the class renamed out of the way). Returns the entries not written."""
        writer = self.ak.FontKerning(kerning)
        failed = []
        for entry, value in entries:
            try:
                writer.write(entry, round_units(value), False)
            except Exception:
                failed.append(entry)
        return failed

    @staticmethod
    def set_prefix(package, text):
        """Live (2026-11-24, Sarabun Regular and Bold assembled): fgPackage.features.set_prefix(text); get_prefix() read the
        text back."""
        package.fgPackage.features.set_prefix(text)

    @staticmethod
    def set_feature(package, tag, code):
        """Proven: fgPackage.features.set_feature(tag, code) (a new tag goes last)."""
        package.fgPackage.features.set_feature(tag, code)

    @staticmethod
    def set_upm(package, upm):
        """Live (2026-11-24, Sarabun Regular and Bold assembled): flPackage.setUpm(units, False), Font Builder's call (False:
        the glyphs not scaled; the new font has none yet); upm read back."""
        package.setUpm(int(upm), False)

    @staticmethod
    def set_info(package, attribute, value):
        """Live (2026-11-24, Sarabun Regular and Bold assembled): fgPackage.info's UFO-named attributes are settable (the family
        name, the copyright, the designer, the typo, win, and hhea values read back)."""
        setattr(package.fgPackage.info, attribute, value)

    @staticmethod
    def set_version(package, major, minor):
        """Live (2026-11-24): flPackage.versionMajor and versionMinor are settable (2 and 5 read back)."""
        package.versionMajor, package.versionMinor = int(major), int(minor)

    @staticmethod
    def set_metric(package, attribute, value):
        """Live (2026-11-24): flPackage's line metrics (ascender_value, descender_value, xHeight_value,
        capsHeight_value, lineGap_value) are settable, and are the current master's: xHeight_value set to 510
        with Bold current read 500 with Regular current."""
        setattr(package, attribute, float(value))

    def add_axis(self, package, name, tag, minimum, default, maximum):
        """Live (2026-11-18): fontlab.flAxis() with settable name, tag, shortName, minimal (not minimum),
        default, and maximum, then flPackage.addAxis(axis), which gives back the axis' name."""
        axis = self.fontlab.flAxis()
        axis.name, axis.tag, axis.shortName = name, tag, tag
        for attribute, value in (("minimal", minimum), ("maximum", maximum), ("default", default)):
            try:
                setattr(axis, attribute, float(value))
            except Exception:
                pass
        package.addAxis(axis)
        return axis

    def set_location(self, package, master, location):
        """Live (2026-11-18): flPackage.setLocation(flLocation location[, string master_name]), the location
        made as fontlab.flLocation({axis name: value}) (a plain dict refused: "flLocation expected"); read back,
        str(flPackage.location(master)) says "<flLocation weight=700>"."""
        package.setLocation(self.fontlab.flLocation(dict(location)), master)

    @staticmethod
    def set_names(package, family, style):
        """Live (2026-11-24): a new font's flPackage.tfn reads "Unnamed", its ffn "Unnamed Regular", and its
        psn "Unnamed-Regular", whatever fgPackage.info.familyName is set to, and its Font window's tab is
        titled by them (title_name(): the ffn, or "tfn: master" once it has several masters): the assembled
        Sarabun came up as "Unnamed: Bold" (the owner, 2026-11-24). All four are settable; set before the
        window opens, since a tab already open kept its title when ffn was set after."""
        package.tfn, package.tsn = family, style
        package.ffn = u"%s %s" % (family, style)
        package.psn = u"%s-%s" % (family.replace(u" ", u""), style.replace(u" ", u""))

    def show_package(self, package):
        """Live (2026-11-24, Sarabun Regular and Bold assembled): fontlab.flItems.notifyPackageAdded(package) opens the new
        font's Font window, as a tab of the main window (Font Builder's call)."""
        self.fontlab.flItems.notifyPackageAdded(package)

    def glyphs_shown(self, package):
        """Proven: fontlab.flItems.notifyPackageContentUpdated(fgPackage.id): the Font window lists glyphs a
        script added."""
        self.fontlab.flItems.notifyPackageContentUpdated(package.fgPackage.id)

    @staticmethod
    def rebuild_maps(package):
        """Proven: fgPackage.rebuildMaps(): findUnicode sees the code points a script set."""
        package.fgPackage.rebuildMaps()

    @staticmethod
    def mark_modified(package):
        """Proven: flPackage.setFlag(2, True) marks the font modified (FontLab asks before closing it)."""
        package.setFlag(2, True)


# The font info read and, for the reference, written to the new font: (INFO_FIELDS key, fgPackage.info name)
INFO_ATTRIBUTES = (("typo_ascender", "openTypeOS2TypoAscender"), ("typo_descender", "openTypeOS2TypoDescender"),
                   ("typo_line_gap", "openTypeOS2TypoLineGap"), ("hhea_ascender", "openTypeHheaAscender"),
                   ("hhea_descender", "openTypeHheaDescender"), ("hhea_line_gap", "openTypeHheaLineGap"),
                   ("win_ascent", "openTypeOS2WinAscent"), ("win_descent", "openTypeOS2WinDescent"),
                   ("italic_angle", "italicAngle"), ("weight_class", "openTypeOS2WeightClass"),
                   ("width_class", "openTypeOS2WidthClass"))
# What the new font takes from the reference's font info, as text (fgPackage.info names); its line metrics
# go to each master from that master's source (MASTER_METRICS)
INFO_TEXTS = ("copyright", "trademark", "openTypeNameDesigner", "openTypeNameDesignerURL", "openTypeNameManufacturer",
              "openTypeNameManufacturerURL", "openTypeNameLicense", "openTypeNameLicenseURL", "openTypeOS2VendorID")
MASTER_METRICS = (("ascender", "ascender_value"), ("descender", "descender_value"), ("x_height", "xHeight_value"),
                  ("cap_height", "capsHeight_value"), ("line_gap", "lineGap_value"))
MASTER_INFO = ("italic_angle", "weight_class", "width_class")  # each master's own: not written as the font's
# The coverage the font info declares, read from each source: (Source.info key, fgPackage.info name)
COVERAGE_ATTRIBUTES = (("unicode_ranges", "openTypeOS2UnicodeRanges"), ("code_pages", "openTypeOS2CodePageRanges"))
WIN_KEYS = (("win_ascent", "openTypeOS2WinAscent"), ("win_descent", "openTypeOS2WinDescent"))


def assembled_coverage(module, reference, plan):
    """[(fgPackage.info name, bits)] the new font declares: the reference's Unicode ranges and code pages,
    with those the new font's code points complete or no longer reach set or cleared, as a FreeLab tool
    updates them after a write (freelab_font_info's changed_bits: the reference's own choices kept). Where
    the reference's could not be read, what the new font's code points cover."""
    if module is None:
        return []
    before_codes = set(code for codes in dict(reference.glyphs or {}).values() for code in codes)
    after_codes = set(code for codes in plan.codes.values() for code in codes)
    before, after = module.coverage(before_codes), module.coverage(after_codes)
    found = []
    info = reference.info or {}
    for key, attribute in COVERAGE_ATTRIBUTES:
        declared = info.get(key)
        if declared is None:
            found.append((attribute, sorted(after[attribute])))
            continue
        bits = set(declared)
        for bit, on in module.changed_bits(bits, before[attribute], after[attribute]).items():
            if attribute == module.INFO_PAGES and bit not in module.managed_pages():
                continue
            (bits.add if on else bits.discard)(bit)
        found.append((attribute, sorted(bits)))
    return found


def assembled_win(sources):
    """[(fgPackage.info name, value)]: the largest Win ascent and descent of the sources, each source's
    covering its own glyphs (the Win values are the whole font's: one for every master)."""
    found = []
    for key, attribute in WIN_KEYS:
        values = [s.info.get(key) for s in sources if s.info and s.info.get(key) is not None]
        if values:
            found.append((attribute, max(values)))
    return found


def read_source(calls, entry, shapes=True, progress=None):
    """A Source of a sources' list entry (SourceEntry, its package open in FontLab): the glyphs with a
    layer in its master, their structures (shapes: True), its kerning, features, and info. progress(part)
    is called as the glyphs are read (part: 0 to 1). Anything that cannot be read is None."""
    package = entry.package
    glyphs, found = [], {} if shapes else None
    listed_glyphs = calls.glyph_list(package)
    total = float(len(listed_glyphs) or 1)
    several = entry.masters > 1
    for done, (name, codes) in enumerate(listed_glyphs):
        if progress is not None and done % 50 == 0:
            progress(done / total)
        layer = None
        if shapes or several:
            try:
                layer = calls.layer(package, name, entry.master)
            except Exception:
                layer = None
            if layer is None and several:
                continue  # (no layer in this master: a glyph it lacks)
        glyphs.append((name, codes))
        if shapes:
            try:
                found[name] = calls.structure(name, layer) if layer is not None else None
            except Exception:
                found[name] = None
    try:
        kerning = calls.kerning(package, entry.master)
    except Exception:
        kerning = None
    try:
        features = calls.features(package)
    except Exception:
        features = None
    try:
        info = calls.info(package, entry.master)
    except Exception:
        info = {}
    return Source(entry.key, entry.label, entry.style, entry.master, glyphs, found, info, kerning, features,
                  entry.font, entry.masters, package)


class AssembleError(Exception):
    """The new font could not be made as planned (no font, or not its masters). package: the new font
    when FontLab made one (left as it is, never closed: closing the current font crashed FontLab)."""

    def __init__(self, text, package=None):
        Exception.__init__(self, text)
        self.package = package


class Failures(object):
    """What could not be carried over, by kind: one line a kind, its items listed in short (a call FontLab
    refuses for every glyph is one line, not thousands), with the first error FontLab gave."""

    def __init__(self):
        self.order, self.items, self.errors = [], {}, {}

    def add(self, what, item, error=None):
        if what not in self.items:
            self.order.append(what)
            self.items[what] = []
        self.items[what].append(item)
        if error is not None and what not in self.errors:
            self.errors[what] = u"%s" % error

    def attempt(self, what, item, call, *args):
        """call(*args)'s result, or None with the failure noted under what."""
        try:
            return call(*args)
        except Exception as exc:
            self.add(what, item, exc)
            return None

    def lines(self):
        found = []
        for what in self.order:
            error = self.errors.get(what)
            found.append(u"%s%s: %s." % (what, u" (FontLab: %s)" % error if error else u"", names_text(self.items[what])))
        return found


def build_font(calls, plan, sources, progress=None):
    """Makes the new font of an AssemblyPlan through calls (FontLabCalls), from the sources ({key: Source,
    each with its package}). Returns (the new font, [what was not carried over]): the plan's notes, then
    what FontLab refused. The sources are only read. Raises AssembleError when FontLab makes no font, or
    not its masters (nothing placed in it then)."""
    failed = Failures()
    say = (lambda what, part=0.0: progress(what, part)) if progress is not None else (lambda what, part=0.0: None)
    say(u"Making the new font")
    package = calls.new_package()
    if package is None:
        raise AssembleError(u"FontLab made no new font")
    names = [name for name, _ in plan.masters]
    reference = sources[plan.reference]
    upm = (reference.info or {}).get("upm")
    if upm:
        failed.attempt(u"Units per em not set", number_text(upm), calls.set_upm, package, upm)
    try:
        existing = calls.masters(package)
        if existing:
            if existing[0] != names[0]:
                calls.rename_master(package, existing[0], names[0])
        else:
            calls.add_master(package, names[0])
        for name in names[1:]:
            calls.add_master(package, name)
        made = calls.masters(package)
    except Exception as exc:
        raise AssembleError(u"FontLab did not make its masters (%s)" % exc, package)
    lost = [name for name in names if name not in made]
    if lost:
        raise AssembleError(u"FontLab did not make the masters %s" % listed(lost), package)
    family = u"%s" % ((reference.info or {}).get("family") or u"")
    if family:  # (before its window opens: the window's tab is titled by these names)
        failed.attempt(u"Font not named", family, calls.set_names, package, family, names[0])
    failed.attempt(u"Font window not opened", u"the new font", calls.show_package, package)
    source_of = dict((name, sources[key]) for name, key in plan.masters)

    # Every glyph, with a layer in every master: a component is made only where its glyph has a layer
    glyphs = {}
    total = float(len(plan.order) or 1)
    for done, name in enumerate(plan.order):
        if done % 50 == 0:
            say(u"Adding the glyphs", done / total)
        glyph = failed.attempt(u"Glyphs not added", name, calls.new_glyph, package, name)
        if glyph is None:
            if name not in failed.items.get(u"Glyphs not added", []):
                failed.add(u"Glyphs not added", name)
            continue
        glyphs[name] = True  # (never the glyph object itself: looked up again at each use, fresh())
        for master in names:
            layer = failed.attempt(u"Layers not made", u"%s (%s)" % (name, master), calls.new_layer, glyph, master)
            if layer is not None:
                failed.attempt(u"Layers not made", u"%s (%s)" % (name, master), calls.init_layer, package, layer)

    def fresh(name):
        """The new font's glyph of that name, looked up now (find_glyph: a kept one crashed FontLab)."""
        return failed.attempt(u"Glyphs not found again", name, calls.find_glyph, package, name)

    # Each layer from its master's source: outlines, anchors, and width; a layer with components once the
    # glyphs they draw are drawn (component_order)
    composites = {}  # glyph: {master: (source layer, its components, width)}

    def copy(name, master, layer, target, width):
        where = u"%s (%s)" % (name, master)
        failed.attempt(u"Outlines not copied", where, calls.copy_contours, layer, target)
        failed.attempt(u"Anchors not copied", where, calls.copy_anchors, layer, target)
        failed.attempt(u"Widths not set", where, calls.set_width, target, width)

    for done, name in enumerate(plan.order):
        if done % 50 == 0:
            say(u"Copying the layers", done / total)
        glyph = fresh(name) if name in glyphs else None
        if glyph is None:
            continue
        for master in plan.layers.get(name, []):
            source = source_of[master]
            where = u"%s (%s)" % (name, master)
            layer = failed.attempt(u"Not read from their sources, left empty", where, calls.layer, source.package, name,
                                   source.master)
            if layer is None:
                if where not in failed.items.get(u"Not read from their sources, left empty", []):
                    failed.add(u"Not read from their sources, left empty", where)
                continue
            target = failed.attempt(u"Layers not made", where, calls.new_layer, glyph, master)
            if target is None:
                continue
            width = failed.attempt(u"Widths not read", where, calls.width, layer) or 0.0
            parts = failed.attempt(u"Components not read", where, calls.components, layer) or []
            if parts:
                composites.setdefault(name, {})[master] = (layer, parts, width)
            else:
                copy(name, master, layer, target, width)
    order = component_order(dict((name, sorted(set(base for _, parts, _ in layers.values() for base, _ in parts)))
                                 for name, layers in composites.items()))
    for name in order:
        for master in [m for m in names if m in composites[name]]:
            layer, parts, width = composites[name][master]
            glyph = fresh(name)
            if glyph is None:
                continue
            target = failed.attempt(u"Layers not made", u"%s (%s)" % (name, master), calls.new_layer, glyph, master)
            if target is None:
                continue
            failed.attempt(u"Components not made", u"%s (%s)" % (name, master), calls.set_components, package, target,
                           parts, width)
            copy(name, master, layer, target, width)
    for name in plan.order:
        glyph = fresh(name) if name in glyphs else None
        if glyph is None:
            continue
        if plan.codes.get(name):
            failed.attempt(u"Code points not set", name, calls.set_codes, glyph, plan.codes[name])
        failed.attempt(u"Glyphs not redrawn", name, calls.update_glyph, glyph)

    # Kerning, each master its source's: its classes, then its entries
    say(u"Copying the kerning", 0.0)
    for master, key in plan.masters:
        source = sources[key]
        if source.kerning is None:
            failed.add(u"Kerning not read, its master left without", master)
            continue
        if not source.kerning.values and not source.kerning.classes:
            continue
        kerning = failed.attempt(u"Kerning not copied", master, calls.target_kerning, package, master)
        if kerning is None:
            continue
        for name, (side, members) in sorted(source.kerning.classes.items()):
            failed.attempt(u"Kerning classes not made", u"%s (%s)" % (name, master), calls.set_kerning_class, kerning,
                           name, members, side)
        entries = sorted(((entry, value) for entry, value in source.kerning.values.items() if value is not None),
                         key=lambda pair: describe_entry(pair[0]))
        refused = failed.attempt(u"Kerning not copied", master, calls.write_kerning, kerning, entries) or []
        for entry in refused:
            failed.add(u"Kerning entries not written", u"%s (%s)" % (describe_entry(entry), master))

    # The reference's feature code (its Classes panel's classes as code, first in the prefix) and font info
    say(u"Writing the features and the font info", 0.0)
    fcmp = calls.fcmp
    prefix_tag = getattr(fcmp, "PREFIX", u"Prefix")
    classes_tag = getattr(fcmp, "CLASSES", u"Classes")
    features = list(reference.features or [])
    by_tag = dict(features)
    prefix = u"\n\n".join(part for part in (by_tag.get(classes_tag), by_tag.get(prefix_tag)) if part)
    notes = list(plan.notes)
    if by_tag.get(classes_tag):
        notes.append(u"The Classes panel's feature classes of %s are written as code, first in the prefix." %
                     reference.label)
    if prefix:
        failed.attempt(u"Prefix not written", u"the prefix", calls.set_prefix, package, prefix)
    for tag, code in features:
        if tag not in (prefix_tag, classes_tag):
            failed.attempt(u"Features not written", tag, calls.set_feature, package, tag, code)
    info = reference.info or {}
    if info.get("family"):
        failed.attempt(u"Font info not set", u"the family name", calls.set_info, package, "familyName", info["family"])
    version = u"%s" % (info.get("version") or u"")
    if u"." in version:
        major, minor = version.split(u".", 1)
        try:
            failed.attempt(u"Font info not set", u"the version", calls.set_version, package, int(major), int(minor))
        except ValueError:
            failed.add(u"Font info not set", u"the version")
    for key, attribute in INFO_ATTRIBUTES:
        if key in MASTER_INFO or info.get(key) is None:
            continue  # (each master's own: not one value for the whole font)
        failed.attempt(u"Font info not set", attribute, calls.set_info, package, attribute, info[key])
    texts = getattr(reference, "texts", None) or {}
    for attribute in INFO_TEXTS:
        if texts.get(attribute):
            failed.attempt(u"Font info not set", attribute, calls.set_info, package, attribute, texts[attribute])
    # What the font covers, as FreeLab's tools keep it after their writes: the reference's, updated for the
    # glyphs the other sources bring; and Win values that clip none of the masters' glyphs
    module = getattr(calls, "font_info_module", lambda: None)()
    for attribute, bits in assembled_coverage(module, reference, plan):
        failed.attempt(u"Font info not set", attribute, calls.set_info, package, attribute, bits)
    used = [sources[key] for _, key in plan.masters]
    for attribute, value in assembled_win(used):
        key = dict((a, k) for k, a in WIN_KEYS)[attribute]
        if value != info.get(key):
            failed.attempt(u"Font info not set", attribute, calls.set_info, package, attribute, value)
            notes.append(u"The %s is %s, the largest of the sources' (%s's is %s), so that no master's glyphs are "
                         u"clipped." % (u"Win ascent" if key == "win_ascent" else u"Win descent", number_text(value),
                                        reference.label, number_text(info.get(key)) if info.get(key) is not None
                                        else u"not set"))
    unmeasured = []
    for master, key in plan.masters:
        values = [(attribute, (sources[key].info or {}).get(field)) for field, attribute in MASTER_METRICS]
        values = [(attribute, value) for attribute, value in values if value is not None]
        if not values:
            unmeasured.append(master)
            continue
        unswitched = u"Masters not made current, their line metrics not set"
        failed.attempt(unswitched, master, calls.set_current_master, package, master)
        if master in failed.items.get(unswitched, []):
            continue
        for attribute, value in values:
            failed.attempt(u"Line metrics not set", u"%s (%s)" % (attribute, master), calls.set_metric, package,
                           attribute, value)
    if unmeasured:
        notes.append(u"The line metrics of %s were not read (FontLab gives a script its font's current master's only): "
                     u"set them in Font Info." % listed(unmeasured))
    failed.attempt(u"Masters not made current", names[0], calls.set_current_master, package, names[0])

    # The axes, where the sources' weight or width classes differ, and each master's location on them
    placed = []
    for axis in plan.axes:
        low, high = axis.range
        if failed.attempt(u"Axes not made", axis.name, calls.add_axis, package, axis.name, axis.tag, low,
                          axis.locations.get(names[0], low), high) is not None:
            placed.append(axis)
    if placed:
        for master in names:
            location = dict((axis.name, axis.locations[master]) for axis in placed)
            failed.attempt(u"Masters not placed on the axes", master, calls.set_location, package, master, location)
    failed.attempt(u"Code points not mapped", u"the new font", calls.rebuild_maps, package)
    failed.attempt(u"Font window not told of the glyphs", u"the new font", calls.glyphs_shown, package)
    failed.attempt(u"Font not marked modified", u"the new font", calls.mark_modified, package)
    say(u"Writing the features and the font info", 1.0)
    return package, notes + failed.lines()


# ---------------------------------------------------------------------------
# The window (Qt)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def _prop(obj, name):
    """A Qt property's value: an attribute in PythonQt (a method in some builds)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


HELP = u"""<b>FreeLab Family Audit</b><br>
The fonts of a family compared with one another, before they become masters of one font. Nothing in any
of them changes.<br><br>
<i>Sources</i>: the fonts open in FontLab, a row for each master of a font of several; tick those to compare.
<i>Add files\N{HORIZONTAL ELLIPSIS}</i> opens font files in FontLab first, in any format it opens (FontLab
projects, UFO, Glyphs, designspace, OpenType, TrueType, WOFF, Type 1), and ticks them once they are in (a font of
another family is left unticked, and the log says so). The
<i>Reference</i> is the source the others are compared with (to start with, the upright one nearest Regular).
<i>Compare</i> compares the ticked sources.<br><br>
<i>Glyph sets</i>: the glyphs each source lacks, and the code points that differ. <i>Compatibility</i>: each
glyph's contours, nodes, components, and anchors across the sources, compatible or the first thing that
differs. <i>Metrics and info</i>: the
font info a column per source. <i>Kerning</i>: classes that differ, entries only some sources kern, and
entries whose sign flips. <i>Features</i>: features some sources lack, and code that differs from the
reference's.<br><br>
<i>Assemble as masters</i> makes a new font with a master per ticked source (named by its style), each
glyph's layers copied from the sources by name, in the reference's glyph order, with its feature code,
classes, and font info, and each master's kerning and line metrics; a glyph a source lacks is left empty in its
master. Weight
and width axes are set where the sources' classes differ. The sources do not change; to take it back, close
the new font without saving. Click this help's button, then anything in the window, for what it does (or right-click it: <i>What's This?</i>)."""

NO_FONT_LINE = (u"No font is open. This window hooks to the next font you open, or click <i>Add "
                u"files\N{HORIZONTAL ELLIPSIS}</i> to open a family's fonts.")
READ_STEP, COMPARE_STEP = u"Reading the sources", u"Comparing"
# The Cancel button's own line (ak.cancel_button): what a stop leaves (compare: the audit before it kept;
# Assemble as masters never stops)
CANCEL_NOTE = u"A comparison stopped changes no font: the tabs show the one before it."
OPEN_WAIT_MS, OPEN_TRIES = 500, 120  # FontLab opens a font in the background: looked for twice a second, a minute
SOURCE_COLUMNS = (u"Source", u"File", u"Format", u"Masters", u"Glyphs", u"Version")
GLYPH_COLUMNS = (u"Glyph", u"Difference")
COMPAT_COLUMNS = (u"Glyph", u"First difference", u"Sources")
KERN_COLUMNS = (u"Entry or class", u"Values", u"Why")
FEATURE_COLUMNS = (u"Feature", u"Difference")


def sources_line(ticked, total, reference=None):
    """The top line's account of the sources: "<b>3 of 5 sources</b> ticked (reference <b>Regular</b>)"."""
    text = u"%s ticked" % bold(u"%s of %s" % (grouped(ticked), counted(total, u"source")))
    if reference:
        text += u" (reference %s)" % bold(reference)
    return text


def assemble_text(count):
    """The committing button: "Assemble 3 sources as masters"."""
    return u"Assemble %s as masters" % counted(count, u"source") if count > 1 else u"Assemble as masters"


def assembly_lines(plan, report, error=None, made=True):
    """The log's lines of Assemble as masters [(rich text, level)], the newest last: what was made (or why
    nothing was), the glyphs left empty in each master, the axes, how many glyphs matched at the audit (no
    promise of interpolation), then what was not carried over (warnings)."""
    if error is not None:
        if made:
            return [(u"The new font was left unfinished: %s. Close it without saving; the sources are as they were."
                     % html(error), "error")]
        return [(u"No new font was made: %s. The sources are as they were." % html(error), "error")]
    lines = []
    empty = sum(len(names) for _, names in plan.empty)
    text = u"Made a new font with %s (%s) and %s" % (bold(counted(len(plan.masters), u"master")),
                                                    html(listed([name for name, _ in plan.masters])),
                                                    bold(counted(len(plan.order), u"glyph")))
    if empty:
        text += u"; %s %s left empty where a source lacks %s" % (
            bold(counted(empty, u"layer")), u"is" if empty == 1 else u"are", u"its glyph" if empty == 1 else u"their glyphs")
    lines.append((text + u". Nothing in the sources changed; close the new font without saving to take it back.",
                  "done"))
    for master, names in plan.empty:
        # (each glyph's name in italics, as every log names a glyph; no link: the glyph is the new font's, and a
        # link opens the glyph of this window's font)
        lines.append((u"Left empty in %s: %s." % (bold(master), names_text([italic(name) for name in names])), "info"))
    if plan.axes:
        lines.append((u"Axes: %s." % html(listed([u"%s (%s)" % (axis.name, u", ".join(
            u"%s %s" % (name, number_text(axis.locations[name])) for name, _ in plan.masters)) for axis in plan.axes])),
                      "info"))
    else:
        lines.append((u"No axis: the sources' weight and width classes are alike.", "info"))
    if plan.matched is not None:
        lines.append((u"At the audit, %s matched in structure: that is needed to interpolate, not a promise of it." %
                      bold(u"%s of %s" % (grouped(plan.matched[0]), counted(plan.matched[1], u"glyph"))), "info"))
    for line in report:
        lines.append((html(line), "warning"))
    return lines


class SourceWatch(object):
    """An audited font's History watched (the shared watch_history takes one font per owner, as Font
    Compare's second font's)."""

    def __init__(self, owner, package):
        self.owner, self.package = owner, package
        try:
            self.seen_history = owner.ak.history_mark(package)
        except Exception:
            self.seen_history = None  # (not watched: watch_history waits for a mark)
        self.timer = None

    @property
    def dialog(self):
        return self.owner.dialog

    @property
    def busy(self):
        return self.owner.busy

    def history_moved(self):
        self.owner.source_moved(self)


class FamilyAuditDialog(object):
    def __init__(self):
        self.failed = None
        self.dialog = None
        try:
            self.build()
        except Exception as exc:  # a half-built dialog crashed FontLab: never raised from here
            self.failed = exc

    # -- building ------------------------------------------------------------

    def build(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        self.fcmp = compare_module()
        self.calls = FontLabCalls(fontlab, ak, self.fcmp)
        self.busy = self.filling = False
        self.package = None  # this window's own font (the window model's)
        self.entries, self.ticked = [], set()  # the sources' list, and the keys ticked
        self.reference = None  # the key chosen in Reference
        self.reference_keys = []  # the dropdown's rows
        self.audit, self.audited = None, None  # the last audit, and (its keys, its reference)
        self.sources = {}  # the Sources of the last audit, by key
        self.pending, self.open_tries = [], 0  # files asked to open, not in yet
        self.rows = dict((key, []) for key in TABS)  # each tab's rows' data, by the index items keep
        self.name_sets = {}  # each audited source's glyph names, as a set (names_of)
        self.watches, self.moved = [], False  # the audited fonts' History watched; whether one moved since
        self.filters, self.made_fonts = [], []
        main = ak.AutoKerningDialog.main_window()
        dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        self.dialog = dialog
        dialog.setWindowTitle(TITLE)
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = ak.window_layout(dialog)  # (its content scrolls on a small screen)
        if hasattr(ak, "one_line"):
            ak.one_line(NO_FONT_LINE)
        # The header (owner's images 222, 223, 229): the top line, the shown tab's status line, the line
        self.font_label = ak.status_label()
        self.font_label.setWordWrap(True)
        layout.addWidget(self.font_label)
        self.status_line = ak.status_label()
        self.status_line.setWordWrap(True)
        layout.addWidget(self.status_line)
        layout.addWidget(ak.header_separator())

        # The options, Compare at their end (owner's image 262)
        options = QtGui.QHBoxLayout()
        self.add_button = QtGui.QPushButton(u"Add files\N{HORIZONTAL ELLIPSIS}")
        self.add_button.setWhatsThis(u"Opens font files in FontLab (several at once), in any format FontLab opens: "
                                     u"FontLab projects (.vfc, .vfj, .vfb), UFO (pick any file inside a .ufo folder), "
                                     u".ufoz, Glyphs, designspace, OpenType and TrueType (.otf, .ttf, .otc, .ttc), WOFF, "
                                     u"and Type 1 (.pfb, .pfa). Each font of this family is ticked as a source once "
                                     u"FontLab has opened it, and a font of another family is left unticked; the log "
                                     u"says which. A font of several masters gives a source per master.")
        self.add_button.setProperty(getattr(ak, "WITHOUT_FONT_PROP", "freelabWithoutFont"), True)
        options.addWidget(self.add_button)
        options.addSpacing(8)
        options.addWidget(QtGui.QLabel(u"Reference:"))
        self.reference_box = QtGui.QComboBox()
        try:
            self.reference_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        except Exception:
            pass
        self.reference_box.setWhatsThis(u"The source the others are compared with, and whose glyph order, feature "
                                        u"code, classes, and font info a new font assembled as masters takes; its "
                                        u"master comes first. To start with, the upright source whose weight is "
                                        u"nearest Regular's.")
        options.addWidget(self.reference_box)
        self.compare_button = QtGui.QPushButton(u"Compare")
        self.compare_button.setWhatsThis(u"Compares the ticked sources: their glyph sets, each glyph's structure, "
                                         u"their font info, kerning, and features. Nothing changes in them.")
        options.addWidget(self.compare_button)
        options.addStretch(1)
        layout.addLayout(options)

        # The sources over the results, in a splitter: [sources] [handle] [line] [tabs]
        self.splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter, 1)
        top = self.part(QtGui, self.splitter, 1)
        self.source_tree = self.tree(SOURCE_COLUMNS, numbers=(3, 4))
        self.source_tree.setWhatsThis(u"The fonts open in FontLab, a row for each master of a font of several: its "
                                      u"name in this window (its style, or its master), its file, the file's format, "
                                      u"its font's masters, its glyphs, and its version. Tick the sources to compare.")
        self.source_tree.setRootIsDecorated(False)  # (no groups: its ticks at the left edge)
        top.addWidget(self.source_tree, 1)  # (the part's last: its handle right under its frame)
        lower = self.part(QtGui, self.splitter, 3)
        lower.addWidget(ak.separator())  # (the first thing under the handle: convention 21)
        self.tabs = QtGui.QTabBar()  # (over plain pages: a QTabWidget's page drew light frames in dark mode)
        self.tabs.setExpanding(False)
        for title in TAB_TITLES:
            self.tabs.addTab(title)
        lower.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        lower.addWidget(self.pages, 1)
        self.trees = {}
        icon = getattr(ak, "glyph_icon_size", None)
        self.trees["glyphs"] = self.tree(GLYPH_COLUMNS, icon=icon(1) if icon else None)
        self.trees["glyphs"].setWhatsThis(u"The glyphs each source lacks (a group a source, counted), and the code points "
                                          u"that differ: a glyph with other code points in another source, or a code "
                                          u"point given to glyphs of other names. Double-click a glyph to open it in a "
                                          u"<i>Glyph</i> window.")
        self.trees["compatibility"] = self.tree(COMPAT_COLUMNS, icon=icon(1) if icon else None)
        self.trees["compatibility"].setWhatsThis(
            u"Each glyph in two sources or more, grouped by the first thing that differs, compared in this order: "
            u"contour counts, components, node counts, node types, contour directions, anchors. <i>Compatible</i> "
            u"glyphs match in all of them: needed to interpolate, not a promise of it (start points, contour order, "
            u"and the shapes themselves are not compared). Double-click a glyph to open it in a <i>Glyph</i> window.")
        self.trees["metrics"] = self.tree((u"Field",))
        self.trees["metrics"].setWhatsThis(u"The font info, a column per source: the fields that should match across "
                                           u"a family but differ first, then those that differ by style, then those "
                                           u"alike. A source's line metrics are its font's current master's: another "
                                           u"master's are left blank.")
        self.trees["kerning"] = self.tree(KERN_COLUMNS)
        self.trees["kerning"].setWhatsThis(u"The kerning classes whose members differ (against the reference's), the "
                                           u"entries only some sources kern, and those that tighten in one source and "
                                           u"loosen in another; a source without kerning is said once.")
        for key in ("glyphs", "compatibility", "metrics", "kerning"):
            self.pages.addWidget(self.trees[key])
        features = QtGui.QSplitter(QtCore.Qt.Horizontal)
        features.setChildrenCollapsible(False)
        self.trees["features"] = self.tree(FEATURE_COLUMNS)
        self.trees["features"].setWhatsThis(u"The features some sources lack, and those whose code differs from the "
                                            u"reference's (<i>Prefix</i>: the code before the features; <i>Classes</i>: "
                                            u"the Classes panel's), a row under each for each source. Select a source's "
                                            u"row to see its lines that differ.")
        features.addWidget(self.trees["features"])
        self.diff_view = QtGui.QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setProperty(ak.LEAVE_ALONE_PROP, True)  # (as the log: the palette's colors, its tints drawn)
        self.diff_view.setWhatsThis(u"The selected source's code of the feature against the reference's: lines only in "
                                    u"the reference on red, after a minus; lines only in that source on green, after a "
                                    u"plus; three lines around each change.")
        features.addWidget(self.diff_view)
        features.setStretchFactor(0, 2)
        features.setStretchFactor(1, 3)
        self.feature_split = features
        self.pages.addWidget(features)
        for splitter in (self.splitter, features):
            self.describe_handles(splitter)
        self.log = ak.Log()
        layout.addWidget(self.log.widget)

        # The bottom row (owner's images 255 and 298): the sources' ticks and Show in Glyph window at the left;
        # the committing action, then Cancel and Close, at the right
        buttons = QtGui.QHBoxLayout()
        self.tick_all = QtGui.QPushButton(u"Tick all")
        self.tick_all.setWhatsThis(u"Ticks every source.")
        self.tick_none = QtGui.QPushButton(u"Untick all")
        self.tick_none.setWhatsThis(u"Unticks every source.")
        self.glyph_window_button = QtGui.QPushButton(u"Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected row's glyphs in a <i>Glyph</i> window of this "
                                              u"window's font (<i>Glyph sets</i> and <i>Compatibility</i>).")
        self.assemble_button = QtGui.QPushButton(assemble_text(0))
        self.assemble_button.setWhatsThis(
            u"Makes a new font, a master per audited source (named by its style, the reference's first): each glyph's "
            u"layers copied from the sources by name, in the reference's glyph order; the reference's feature code, "
            u"classes, and font info; each master's kerning and line metrics from its source. A glyph a source lacks "
            u"is left empty in its master, and listed in the log with whatever could not be carried over. Weight and "
            u"width axes are set where the sources' classes differ. The sources do not change; to take it back, "
            u"close the new font without saving.")
        self.close_button = QtGui.QPushButton(u"Close")
        for button in (self.tick_all, self.tick_none, self.glyph_window_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.assemble_button)
        buttons.addWidget(self.close_button)
        ak.cancel_button(self, buttons, self.close_button, CANCEL_NOTE)  # (right before Close)
        layout.addLayout(buttons)

        self.add_button.connect("clicked()", self.add_files)
        self.compare_button.connect("clicked()", self.compare)
        self.assemble_button.connect("clicked()", self.assemble)
        self.tick_all.connect("clicked()", lambda: self.tick_every(True))
        self.tick_none.connect("clicked()", lambda: self.tick_every(False))
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.close_button.connect("clicked()", ak.close_slot(self))  # (never the window itself: see let_go)
        self.source_tree.connect("itemChanged(QTreeWidgetItem*,int)", self.source_ticked)
        self.reference_slot = lambda index: self.reference_chosen(index)
        self.reference_box.connect("activated(int)", self.reference_slot)
        self.tabs.connect("currentChanged(int)", self.switch_page)
        for key in ("glyphs", "compatibility"):
            self.trees[key].connect("itemDoubleClicked(QTreeWidgetItem*,int)",
                                    lambda item, column: self.show_in_glyph_window())
            self.trees[key].connect("itemSelectionChanged()", self.update_buttons)
        self.trees["features"].connect("itemSelectionChanged()", self.feature_selected)
        self.watch_activation()
        ak.add_tools_button(dialog, TOOL, self.log)  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.read_fonts()
        self.restore_last()
        self.update_buttons()

    def remember_last(self):
        """The audit shown kept for the FontLab session (sys._freelab_family_audit_last), with each audited
        font's place in its History: restore_last shows it again in the next Family Audit window."""
        try:
            marks = dict((s.key, self.ak.history_mark(s.package)) for s in self.sources.values() if s.package is not None)
            sys._freelab_family_audit_last = {"audit": self.audit, "audited": self.audited, "sources": self.sources,
                                              "marks": marks}
        except Exception:
            sys._freelab_family_audit_last = None

    def restore_last(self):
        """The last audit of the session shown again, its sources ticked, when every one of them is still open
        and none changed since (each font's History where it was): the window reopened (after another tool,
        or closed) kept nothing (owner's image 330). Otherwise nothing is shown. Whether it was shown."""
        last = getattr(sys, "_freelab_family_audit_last", None)
        if not last or self.audit is not None or self.busy:
            return False
        try:
            keys, reference = last["audited"]
            open_keys = set(e.key for e in self.entries)
            if any(key not in open_keys for key in keys):
                return False
            for key, mark in last["marks"].items():
                source = last["sources"].get(key)
                if source is None or source.package is None or self.ak.history_mark(source.package) != mark:
                    return False
        except Exception:
            return False
        self.audit, self.audited, self.sources = last["audit"], (list(keys), reference), dict(last["sources"])
        self.ticked, self.reference = set(keys), reference
        self.fill_sources()
        self.fill_reference()
        self.watch_sources(list(self.sources.values()))
        self.fill_tabs()
        self.say_top()
        self.log.add(u"The last comparison is shown again (%s, reference %s): no source changed since." %
                     (bold(counted(len(keys), u"source")), bold(reference_of(list(self.sources.values()), reference).label)))
        return True

    def part(self, QtGui, splitter, stretch):
        """A part of a splitter: its layout, to fill (stretch: its share of the height at first)."""
        widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(widget)
        try:
            splitter.setStretchFactor(splitter.indexOf(widget), stretch)
        except Exception:
            pass
        return box

    @staticmethod
    def describe_handles(splitter):
        """The splitter's handles say what dragging them does (on the handles, not the splitter: every
        label inside it would answer a right-click with it)."""
        try:
            for index in range(1, splitter.count()):
                splitter.handle(index).setWhatsThis(u"Drag to give one part more room.")
        except Exception:
            pass

    def tree(self, columns, icon=None, numbers=()):
        """A list in FreeLab's layout: grouped rows, grid lines, its columns filling it."""
        QtCore, QtGui = _qt()
        tree = QtGui.QTreeWidget()
        tree.setColumnCount(len(columns))
        tree.setHeaderLabels(list(columns))
        if icon is not None:
            try:
                tree.setIconSize(QtCore.QSize(icon[0], icon[1]))
            except Exception:
                pass
        self.ak.table_layout(tree, numbers=numbers)
        return tree

    def watch_activation(self):
        """The sources' list follows the fonts FontLab has open: read again as the window becomes the active
        one (a font opened or closed in FontLab meanwhile)."""
        QtCore, QtGui = _qt()
        owner = self

        class Watch(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 24 and not owner.busy and not owner.filling:  # WindowActivate
                        owner.read_fonts()
                except Exception:
                    pass  # an event filter must never raise
                return False

        found = Watch(self.dialog)  # (its parent the window: Qt deletes it with it)
        self.dialog.installEventFilter(found)
        self.filters.append(found)

    # -- the fonts ---------------------------------------------------------

    def current_font(self):
        """This window's own font (the window model's: ak.window_font), or None."""
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = self.ak.window_font(self, workspace)
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def has_font(self):
        """Whether there is anything to compare (ak.window_has_font): a font open, this window's or
        another's. Without one, the shared module grays the controls but Add files... Never raises."""
        try:
            return bool(self.entries)
        except Exception:
            return True

    def list_entries(self):
        """SourceEntry of every master of every open font, labels unique (source_labels)."""
        calls, entries = self.calls, []
        for package in calls.open_packages():
            number = calls.font_number(package)
            family, style = calls.names(package)
            masters = calls.masters(package)
            path = calls.path(package)
            try:
                glyphs = int(package.glyphsCount)
            except Exception:
                glyphs = 0
            for master in masters:
                # (a master of a font of several stands for a style: its name is its style's)
                entry = SourceEntry(number, master, u"", family, master if len(masters) > 1 else style, len(masters),
                                    path, glyphs, calls.version(package), family, package)
                try:  # (its weight, width, and angle: the reference to start with, default_reference)
                    entry.info = calls.info(package, master)
                except Exception:
                    entry.info = {}
                entries.append(entry)
        labels = source_labels([(e.font, e.style, e.master, e.masters, e.file_name) for e in entries])
        for entry, label in zip(entries, labels):
            entry.label = label
        return entries

    def read_fonts(self):
        """The sources' list read again from the fonts open now: ticks kept, new fonts of the window's
        family (or files added here) ticked, the reference kept while it is ticked."""
        if self.busy:
            return
        self.package = self.current_font()
        try:
            entries = self.list_entries()
        except Exception as exc:
            entries = []
            self.log.add(u"The open fonts could not be read: %s" % self.ak.html(exc), "error")
        known = set(e.key for e in self.entries)
        own = self.calls.font_number(self.package) if self.package is not None else None
        if not self.entries and not self.ticked:
            self.ticked = default_ticks(entries, own)
        else:
            fresh = [e for e in entries if e.key not in known]
            starting = default_ticks(entries, own)
            self.ticked = set(k for k in self.ticked if k in set(e.key for e in entries))
            self.ticked.update(e.key for e in fresh if e.key in starting)
        self.entries = entries
        self.fill_sources()
        self.look_for_opened()
        self.fill_reference()
        self.say_top()
        self.update_buttons()

    def font_changed(self):
        """This window's font was closed, or a font opened for a window without one (fonts_tick)."""
        self.read_fonts()

    def fill_sources(self):
        QtCore, QtGui = _qt()
        tree = self.source_tree
        self.filling = True
        try:
            tree.blockSignals(True)
            tree.clear()
            for index, e in enumerate(self.entries):
                texts = [e.label, e.file_name or u"unsaved", e.format, u"%d" % e.masters, grouped(e.glyphs),
                         e.version or DASH]
                item = QtGui.QTreeWidgetItem(texts)
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if e.key in self.ticked else QtCore.Qt.Unchecked)
                tip = u"%s: master %s of %s (%s)" % (e.label, e.master, e.font or u"its font", e.path or u"unsaved")
                for column in range(len(texts)):
                    item.setToolTip(column, self.ak.html(tip))
                for column in (3, 4):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                tree.addTopLevelItem(item)
        finally:
            try:
                tree.blockSignals(False)
            except Exception:
                pass
            self.filling = False
        try:
            self.ak.fit_rows(tree, range(len(SOURCE_COLUMNS) - 1))
        except Exception:
            pass

    def ticked_entries(self):
        return [e for e in self.entries if e.key in self.ticked]

    def fill_reference(self):
        """The Reference dropdown: the ticked sources (a grayed "n/a" with none); the choice kept while it is
        ticked, else the default (default_reference)."""
        ticked = self.ticked_entries()
        keys = [e.key for e in ticked]
        if self.reference not in keys:
            stand_ins = [Source(e.key, e.label, e.style, e.master, info=getattr(e, "info", None)) for e in ticked]
            self.reference = default_reference(stand_ins)
        self.reference_keys = keys
        box = self.reference_box
        self.filling = True
        try:
            box.blockSignals(True)
            box.clear()
            if not ticked:
                box.addItem(u"n/a")
            for e in ticked:
                box.addItem(e.label)
            if self.reference in keys:
                box.setCurrentIndex(keys.index(self.reference))
        finally:
            try:
                box.blockSignals(False)
            except Exception:
                pass
            self.filling = False

    def reference_label(self):
        for e in self.entries:
            if e.key == self.reference:
                return e.label
        return None

    def say_top(self):
        """The top line: this window's font, the sources ticked, and the reference (convention 1: the
        font named first); with no font open, the no-font line."""
        if not self.entries:
            self.font_label.setText(self.ak.no_font_line(NO_FONT_LINE))
            self.status_line.setText(u"")
            return
        text = sources_line(len(self.ticked_entries()), len(self.entries), self.reference_label())
        if self.package is not None:
            text = u"%s: %s" % (self.ak.font_named(self.package.tfn), text)
        self.font_label.setText(text + u".")
        self.show_status()

    def source_ticked(self, item, column):
        """A source's tick changed by the user."""
        QtCore, QtGui = _qt()
        if self.filling or column != 0:
            return
        try:
            entry = self.entries[int(item.data(0, QtCore.Qt.UserRole))]
            on = item.checkState(0) == QtCore.Qt.Checked
        except Exception:
            return
        self.set_tick(entry.key, on)

    def set_tick(self, key, on):
        if on:
            self.ticked.add(key)
        else:
            self.ticked.discard(key)
        self.fill_reference()
        self.say_top()
        self.update_buttons()

    def tick_every(self, on):
        """Tick all, Untick all: every source (the shared check_rows: the log says how many)."""
        try:
            items = [self.source_tree.topLevelItem(k) for k in range(int(_prop(self.source_tree, "topLevelItemCount")))]
        except Exception:
            items = []
        self.filling = True
        try:
            self.ak.check_rows(items, bool(on), self.log, u"Tick all" if on else u"Untick all", u"source")
        finally:
            self.filling = False
        self.ticked = set(e.key for e in self.entries) if on else set()
        self.fill_reference()
        self.say_top()
        self.update_buttons()

    def reference_chosen(self, index):
        if self.filling or not 0 <= index < len(self.reference_keys):
            return
        self.reference = self.reference_keys[index]
        self.say_top()
        if self.audit is not None:
            self.log.add(u"Reference: %s. Click %s to compare with it." % (self.ak.b(self.reference_label()),
                                                                          self.ak.i(u"Compare")))
        self.update_buttons()

    # -- adding files ------------------------------------------------------

    def add_files(self):
        """Add files...: font files picked (several at once) opened in FontLab, each ticked once it is in
        (look_for_opened); a file open already is ticked at once."""
        QtCore, QtGui = _qt()
        picked = QtGui.QFileDialog.getOpenFileNames(self.dialog, u"Add font files to the audit",
                                                    getattr(self, "last_folder", u"") or u"", OPEN_FILTER)
        if isinstance(picked, tuple) and len(picked) == 2 and isinstance(picked[0], (list, tuple)):
            picked = picked[0]  # (PyQt's form: the files and the filter chosen; PythonQt's two files are two strings,
            # which this read as one path character by character: Font Builder's image 376)
        elif not isinstance(picked, (list, tuple)):
            picked = [picked] if picked else []
        paths = []
        for path in list(picked or []):
            path = font_path_of(path)
            if path and path not in paths:
                paths.append(path)
        if not paths:
            return
        self.last_folder = os.path.dirname(paths[-1])
        self.open_paths(paths)

    def open_paths(self, paths):
        """Each path opened in FontLab (the ones open already ticked), then looked for until it is in. A file
        FontLab 7.2 crashes on is asked about first: a fixed copy opened instead, or skipped (the shared
        crash_checked_paths)."""
        self.read_fonts()
        closed = []
        for path in paths:
            if not self.tick_open(path):
                closed.append(path)
        def coming(path):  # (being opened: asked for before, not in yet)
            return any(same_path(p, path) for p in self.pending)
        closed = [path for path in closed if not (coming(path) and self.say_coming(path))]
        checked = self.ak.crash_checked_paths(closed, self.dialog, self.log, lambda copy: coming(copy) or any(
            same_path(e.path, copy) for e in self.entries))  # (a copy on its way is not asked about, nor written again)
        for path, picked in checked:
            if path != picked and self.tick_open(path):
                continue  # (its fixed copy, opened earlier)
            if coming(path):  # (Codex, 2026-11-19: picked again while it loaded, it was asked for twice)
                self.say_coming(path)
                continue
            try:
                self.calls.request_font(path)
            except Exception as exc:
                self.log.add(u"FontLab did not open %s: %s" % (self.ak.i(os.path.basename(path)), self.ak.html(exc)),
                             "error")
                continue
            self.pending.append(path)
            self.log.add(u"Opening %s in FontLab%s" % (self.ak.i(os.path.basename(path)), ELLIPSIS))
        self.known_fonts = set(e.font_number for e in self.entries) | getattr(self, "known_fonts", set())
        self.fill_sources()
        self.fill_reference()
        self.say_top()
        self.update_buttons()
        if self.pending:
            self.open_tries = 0
            self.start_open_timer()

    def say_coming(self, path):
        """A file picked again while FontLab opens it, said (it is ticked once it is in); True."""
        self.log.add(u"%s is being opened already: ticked once it is in." % self.ak.i(os.path.basename(path)))
        return True

    def tick_open(self, path):
        """The sources open from path ticked, and said; whether there were any."""
        there = [e for e in self.entries if same_path(e.path, path)]
        for e in there:
            self.ticked.add(e.key)
        if there:
            self.log.add(u"%s is open already: ticked." % self.ak.i(os.path.basename(path)))
        return bool(there)

    def start_open_timer(self):
        QtCore, QtGui = _qt()
        timer = getattr(self, "open_timer", None)
        if timer is None:
            timer = self.open_timer = QtCore.QTimer(self.dialog)  # (its parent the window: Qt deletes it with it)
            timer.setSingleShot(True)
            timer.setInterval(OPEN_WAIT_MS)
            timer.connect("timeout()", self.open_tick)
        timer.start()

    def open_tick(self):
        """The files being opened looked for again (until OPEN_TRIES)."""
        try:
            if not self.pending:
                return
            self.read_fonts()
            if not self.pending:
                return
            self.open_tries += 1
            if self.open_tries < OPEN_TRIES:
                self.start_open_timer()
                return
            for path in self.pending:
                self.log.add(u"%s did not open (or FontLab is waiting for an answer in a dialog)." %
                             self.ak.i(os.path.basename(path)), "warning")
            self.pending = []
        except Exception:
            pass  # a timer's handler must not raise

    def look_for_opened(self):
        """The fonts that came in since files were asked to open, matched with them (match_opened), ticked,
        and said."""
        if not self.pending:
            self.known_fonts = set(e.font_number for e in self.entries)
            return
        known = getattr(self, "known_fonts", set())
        numbers, paths = [], {}
        for e in self.entries:
            if e.font_number not in known and e.font_number not in paths:
                numbers.append(e.font_number)
                paths[e.font_number] = e.path
        matched, self.pending, _ = match_opened(self.pending, [(n, paths[n]) for n in numbers])
        for path, number in matched:
            family = self.audited_family()  # (the files ticked so far say it, in a window without a font)
            opened = [e for e in self.entries if e.font_number == number]
            labels = listed([self.ak.b(e.label) for e in opened])
            other = [e.family for e in opened if family is not None and e.family != family]
            if other:
                # (another family's font, added by mistake or for a look: not compared with this family unless
                # ticked by hand; it was ticked with it, owner's image 344)
                self.log.add(u"Opened %s in FontLab as %s, of another family (%s): left unticked; tick it to compare "
                             u"it with %s all the same." % (self.ak.i(os.path.basename(path)), labels,
                                                            self.ak.html(other[0] or u"no family name"),
                                                            self.ak.b(family)), "warning")
                continue
            self.ticked.update(e.key for e in opened)
            self.log.add(u"Opened %s in FontLab: ticked as %s." % (self.ak.i(os.path.basename(path)), labels), "done")
        self.known_fonts = set(e.font_number for e in self.entries)
        if matched:
            self.fill_sources()
            self.bring_forward()

    def audited_family(self):
        """The family the window audits: its own font's, else the one most ticked sources belong to; None
        when nothing tells (no font of its own, nothing ticked)."""
        own = self.calls.font_number(self.package) if self.package is not None else None
        for e in self.entries:
            if own is not None and e.font_number == own:
                return e.family
        counts = {}
        for e in self.entries:
            if e.key in self.ticked:
                counts[e.family] = counts.get(e.family, 0) + 1
        return max(sorted(counts), key=lambda name: counts[name]) if counts else None

    def bring_forward(self):
        """This window back in front: FontLab activates a font's window as it opens it."""
        try:
            self.dialog.raise_()
            self.dialog.activateWindow()
        except Exception:
            pass

    # -- comparing ---------------------------------------------------------

    def progress(self, what, part=0.0, stoppable=True):
        self.ak.busy_progress(self, what, part, stoppable=stoppable)

    def compare(self):
        """The ticked sources read and compared: every tab filled."""
        if self.busy:
            return
        self.read_fonts()
        chosen = self.ticked_entries()
        if len(chosen) < 2:
            self.log.add(u"Tick at least two sources to compare.", "warning")
            return
        reference = self.reference if self.reference in [e.key for e in chosen] else chosen[0].key
        self.busy = True
        self.update_buttons()
        self.ak.busy_start(self, READ_STEP)
        sources = []
        try:
            for index, entry in enumerate(chosen):
                share = 0.9 / len(chosen)
                self.progress(u"%s (%s)" % (READ_STEP, entry.label), index * share)
                sources.append(read_source(self.calls, entry, True,
                                           lambda part, index=index: self.progress(None, (index + part) * share)))
            self.progress(COMPARE_STEP, 0.92)
            audit = Audit(sources, reference, self.fcmp)
            self.progress(COMPARE_STEP, 1.0, stoppable=False)
        except self.ak.Stopped:
            audit = None
            self.log.add(u"The comparison was stopped: the tabs show the one before it.", "warning")
        except Exception as exc:
            audit = None
            self.log.add(u"The comparison stopped on an error: %s" % self.ak.html(exc), "error")
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if audit is not None:
            self.audit = audit
            self.audited = ([s.key for s in sources], reference)
            self.sources = dict((s.key, s) for s in sources)
            self.watch_sources(sources)
            self.remember_last()
            self.fill_tabs()
            unread = [s.label for s in sources if s.shapes is not None and any(v is None for v in s.shapes.values())]
            self.log.add(u"Compared %s (reference %s)." % (bold(counted(len(sources), u"source")),
                                                           bold(reference_of(sources, reference).label)), "done")
            if unread:
                self.log.add(u"Some glyphs of %s could not be read: <i>Compatibility</i> lists them." %
                             listed([bold(label) for label in unread]), "warning")
            missing = [s.label for s in sources if s.kerning is None or s.features is None]
            if missing:
                self.log.add(u"The kerning or the features of %s could not be read." % listed([bold(label) for label in missing]),
                             "warning")
        self.say_top()
        self.update_buttons()

    def watch_sources(self, sources):
        """The audited fonts' History watched from now on (the earlier audit's watches stopped): an undo,
        a redo, or an edit in one of them says the audit is out of date (source_moved)."""
        for watch in self.watches:
            try:
                watch.timer.stop()
            except Exception:
                pass
        self.watches, self.moved, seen = [], False, set()
        for s in sources:
            if s.package is None:
                continue
            number = self.calls.font_number(s.package)
            number = number if number is not None else id(s.package)
            if number in seen:
                continue  # (two masters of one font: one History)
            seen.add(number)
            watch = SourceWatch(self, s.package)
            try:
                watch.timer = self.ak.watch_history(watch)
            except Exception:
                watch.timer = None
            self.watches.append(watch)

    def source_moved(self, watch):
        """An audited font's History moved (an undo, a redo, an edit, or the font closed): said once, in
        the log and the status line, until the next audit (Assemble reads the sources afresh anyway)."""
        if self.moved:
            return
        self.moved = True
        self.log.add(u"A source changed since the audit (an undo, a redo, an edit, or the font closed): click %s to "
                     u"compare again." % italic(u"Compare"), "warning")
        self.show_status()

    def stale(self):
        """Whether the ticked sources or the reference changed since the audit shown."""
        if self.audited is None:
            return True
        return (set(self.audited[0]) != set(e.key for e in self.ticked_entries()) or
                self.audited[1] != self.reference)

    # -- the tabs ------------------------------------------------------------

    def current_key(self):
        try:
            index = int(_prop(self.tabs, "currentIndex"))
        except Exception:
            index = 0
        return TABS[index] if 0 <= index < len(TABS) else TABS[0]

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        self.show_status()
        self.update_buttons()

    def status_of(self, key):
        """A tab's status line (the window's second line while it is shown)."""
        audit = self.audit
        if audit is None:
            if len(self.ticked_entries()) < 2:
                return u"Tick at least two sources, then click %s." % italic(u"Compare") if self.entries else u""
            return u"Click %s to compare the ticked sources." % italic(u"Compare")
        sources = [self.sources[k] for k in audit.keys]
        text = {"glyphs": lambda: glyph_sets_line(audit.glyph_sets, sources),
                "compatibility": lambda: compatibility_line(audit.compatibility),
                "metrics": lambda: info_line(audit.info),
                "kerning": lambda: kerning_line(audit.kerning, sources),
                "features": lambda: features_line(audit.features, sources)}[key]()
        if self.stale():
            text += u" The ticks or the reference changed since: click %s to compare again." % italic(u"Compare")
        elif self.moved:
            text += u" A source changed since: click %s to compare again." % italic(u"Compare")
        return text

    def show_status(self):
        """The shown tab's status line, as tall as the tallest tab's: a tab whose line took one line more than
        another's moved the sources and the results down as the tabs switched (owner's images 370 and 371)."""
        try:
            label = self.status_line
            shown = self.status_of(self.current_key()) if self.entries else u""
            label.setText(shown)
            label.setMinimumHeight(self.tallest_status(label) if shown and self.audit is not None else 0)
        except Exception:
            pass

    def tallest_status(self, label):
        """The height (pixels) of the tallest tab's status line at the label's width: each one set on the label
        and measured (heightForWidth, its blank line above included), the shown one set last by show_status.
        0 where Qt does not say. Never raises."""
        shown = u"%s" % _prop(label, "text")
        tallest = 0
        try:
            width = int(_prop(label, "width"))
            for key in TABS:
                label.setText(self.status_of(key))
                tallest = max(tallest, int(label.heightForWidth(width)))
        except Exception:
            tallest = 0
        try:
            label.setText(self.status_of(self.current_key()))
        except Exception:
            pass
        return tallest if shown else 0

    def group(self, tree, title, count, noun, many=None, expanded=True):
        """A row heading a group of rows, with its count: "Missing from Bold (12 glyphs)"."""
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem([u"%s (%s)" % (title, counted(count, noun, many))])
        item.setData(0, QtCore.Qt.UserRole, -1)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        tree.addTopLevelItem(item)
        try:
            item.setFirstColumnSpanned(True)
        except Exception:
            pass
        self.ak.section_row(item, tree)
        item.setExpanded(expanded)
        return item

    def row(self, key, parent, texts, data, tip=u"", icon=None):
        """A row under a group, keeping data (its glyphs, its finding) for the tab's buttons."""
        QtCore, QtGui = _qt()
        rows = self.rows[key]
        item = QtGui.QTreeWidgetItem([u"%s" % t for t in texts])
        item.setData(0, QtCore.Qt.UserRole, len(rows))
        rows.append(data)
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        if icon is not None:
            item.setIcon(0, icon)
        if tip:
            for column in range(len(texts)):
                item.setToolTip(column, self.ak.html(tip))
        parent.addChild(item)
        return item

    def more_row(self, key, parent, left):
        """The last row of a group cut at ROWS_SHOWN: how many more."""
        if left > 0:
            self.row(key, parent, (u"and %s more" % grouped(left), u""), None)

    def icon_of(self, name):
        """A row's picture of its glyph, from the reference (else the first source that has it); None past
        the shared module's GLYPH_ICON_ROWS, or when it cannot be drawn."""
        QtCore, QtGui = _qt()
        drawn = getattr(self, "icons_drawn", 0)
        if drawn >= getattr(self.ak, "GLYPH_ICON_ROWS", 0) or self.audit is None:
            return None
        self.icons_drawn = drawn + 1
        keys = [self.audit.reference] + [k for k in self.audit.keys if k != self.audit.reference]
        for key in keys:
            source = self.sources.get(key)
            if source is not None and source.package is not None and name in self.names_of(key):
                try:
                    color = _prop(self.dialog, "palette").color(QtGui.QPalette.WindowText)
                    return self.ak.glyph_icon(source.package, source.master, [name], color)
                except Exception:
                    return None
        return None

    def names_of(self, key):
        """The glyph names of an audited source, as a set (made once an audit)."""
        held = self.name_sets.get(key)
        if held is None:
            source = self.sources.get(key)
            held = self.name_sets[key] = set(source.names()) if source is not None else set()
        return held

    def fill_tabs(self):
        self.icons_drawn = 0
        self.name_sets = {}
        for key in TABS:
            self.rows[key] = []
            tree = self.trees[key]
            try:
                tree.blockSignals(True)
                tree.clear()
            except Exception:
                pass
            try:
                getattr(self, "fill_" + key)(tree)
            finally:
                try:
                    tree.blockSignals(False)
                except Exception:
                    pass
            try:
                self.ak.fit_rows(tree, range(max(1, int(_prop(tree, "columnCount")) - 1)))
            except Exception:
                pass
        self.diff_view.clear()
        counts = self.audit.counts()
        for index, key in enumerate(TABS):
            try:
                self.tabs.setTabText(index, tab_text(TAB_TITLES[index], counts[key]))
            except Exception:
                pass
        self.show_status()

    def fill_glyphs(self, tree):
        report = self.audit.glyph_sets
        for label, names in report.missing:
            parent = self.group(tree, u"Missing from %s" % label, len(names), u"glyph")
            for name in names[:ROWS_SHOWN]:
                having = [self.sources[k].label for k in self.audit.keys if name in self.names_of(k)]
                self.row("glyphs", parent, (name, u"in %s" % listed(having)), [name],
                         u"%s: in %s, not in %s" % (name, listed(having), label), self.icon_of(name))
            self.more_row("glyphs", parent, len(names) - ROWS_SHOWN)
        if report.codes:
            parent = self.group(tree, u"Code points that differ", len(report.codes), u"mapping")
            for d in report.codes[:ROWS_SHOWN]:
                self.row("glyphs", parent, (d.subject, d.text), d.names, u"%s: %s" % (d.subject, d.text),
                         self.icon_of(d.names[0]) if d.names else None)
            self.more_row("glyphs", parent, len(report.codes) - ROWS_SHOWN)

    def fill_compatibility(self, tree):
        report = self.audit.compatibility
        groups = report.by_kind()
        for kind in COMPAT_KINDS:
            found = groups.get(kind)
            if not found:
                continue
            parent = self.group(tree, COMPAT_GROUPS[kind], len(found), u"glyph")
            for r in found[:ROWS_SHOWN]:
                self.row("compatibility", parent, (r.name, r.text, listed(r.sources)), [r.name],
                         u"%s: %s" % (r.name, r.text), self.icon_of(r.name))
            self.more_row("compatibility", parent, len(found) - ROWS_SHOWN)
        good = report.compatible()
        if good:
            parent = self.group(tree, u"Compatible", len(good), u"glyph", expanded=False)
            for r in good[:ROWS_SHOWN]:
                self.row("compatibility", parent, (r.name, u"", listed(r.sources)), [r.name])
            self.more_row("compatibility", parent, len(good) - ROWS_SHOWN)

    def fill_metrics(self, tree):
        labels = [self.sources[k].label for k in self.audit.keys]
        try:
            tree.setColumnCount(1 + len(labels))
            tree.setHeaderLabels([u"Field"] + labels)
        except Exception:
            pass
        rows = self.audit.info
        for group, title in INFO_GROUPS:
            found = [r for r in rows if r.group == group]
            if not found:
                continue
            parent = self.group(tree, title, len(found), u"field", expanded=group != "same")
            for r in found:
                self.row("metrics", parent, [r.label] + [text or DASH for _, text in r.values], r,
                         u"%s: %s" % (r.label, u"; ".join(u"%s %s" % (label, text or DASH) for label, text in r.values)))

    def fill_kerning(self, tree):
        findings = self.audit.kerning
        for kind, title, noun, many, _ in KERN_GROUPS:
            found = [f for f in findings if f.kind == kind]
            if not found:
                continue
            parent = self.group(tree, title, len(found), noun, many)
            for f in found[:ROWS_SHOWN]:
                values = u"; ".join(u"%s %s" % pair for pair in f.values)
                self.row("kerning", parent, (f.subject, values, f.reason), f, u"%s: %s (%s)" % (f.subject, f.reason, values))
            self.more_row("kerning", parent, len(found) - ROWS_SHOWN)

    def fill_features(self, tree):
        findings = self.audit.features
        for kind, title in FEATURE_GROUPS:
            found = [f for f in findings if f.kind == kind]
            if not found:
                continue
            parent = self.group(tree, title, len(found), u"feature", expanded=kind != "same")
            for f in found:
                states = [s for s in f.states if s.kind != "same"]
                text = u"; ".join(u"%s: %s" % (s.label, s.text) for s in states) or u"alike"
                item = self.row("features", parent, (f.tag, text), (f, None), u"%s, against %s: %s" % (f.tag, f.base, text))
                for state in states:
                    self.row("features", item, (state.label, state.text), (f, state),
                             u"%s in %s, against %s: %s" % (f.tag, state.label, f.base, state.text))

    # -- rows ------------------------------------------------------------------

    def selected_data(self, key):
        QtCore = _qt()[0]
        try:
            items = self.trees[key].selectedItems()
            if not items:
                return None
            index = int(items[0].data(0, QtCore.Qt.UserRole))
        except Exception:
            return None
        rows = self.rows.get(key, [])
        return rows[index] if 0 <= index < len(rows) else None

    def selected_glyphs(self):
        key = self.current_key()
        if key not in ("glyphs", "compatibility"):
            return []
        return list(self.selected_data(key) or [])

    def show_in_glyph_window(self):
        names = self.selected_glyphs()
        if not names:
            return
        error = self.ak.show_in_glyph_window(self.fontlab, u"".join(u"/%s" % name for name in names), self)
        if error:
            self.log.add(u"FontLab did not open %s: %s" % (self.ak.html(listed(names)), self.ak.html(error)), "error")

    def code_colors(self):
        """(base, text) as (red, green, blue) for the diff's HTML (Font Compare's colors)."""
        QtCore, QtGui = _qt()
        palette = _prop(self.diff_view, "palette")
        rgb = lambda c: (c.red(), c.green(), c.blue())
        try:
            group = QtGui.QPalette.Active
            return rgb(palette.color(group, QtGui.QPalette.Base)), rgb(palette.color(group, QtGui.QPalette.Text))
        except Exception:
            return rgb(palette.color(QtGui.QPalette.Base)), rgb(palette.color(QtGui.QPalette.Text))

    def feature_selected(self):
        """The selected source's lines of a feature that differ from the reference's (a feature's own row:
        its first source that differs)."""
        data = self.selected_data("features")
        if not data:
            self.diff_view.clear()
            return
        finding, state = data
        if state is None:
            states = [s for s in finding.states if s.kind != "same"]
            state = states[0] if states else None
        if state is None:
            self.diff_view.clear()
            return
        try:
            base, text = self.code_colors()
            self.diff_view.setHtml(self.fcmp.diff_html(state.rows, (finding.base, state.label), base, text))
        except Exception as exc:
            self.diff_view.setPlainText(u"%s" % exc)

    def theme_changed(self):
        """Dark mode switched: the feature's differences drawn again in the new colors."""
        try:
            self.feature_selected()
        except Exception:
            pass

    # -- assembling --------------------------------------------------------

    def assemble(self):
        """Assemble as masters: the audited sources read again (their glyphs, kerning, features, and info,
        as they are now), planned (plan_assembly), and made into a new font (build_font)."""
        if self.busy or self.audit is None or self.stale():
            return
        chosen = [e for e in self.entries if e.key in set(self.audit.keys)]
        if len(chosen) < 2:
            return
        self.busy = True
        self.update_buttons()
        self.ak.busy_start(self, READ_STEP, stoppable=False)
        package, report, error, plan = None, [], None, None
        try:
            sources = []
            for index, entry in enumerate(chosen):
                self.progress(u"%s (%s)" % (READ_STEP, entry.label), 0.2 * index / len(chosen), stoppable=False)
                source = read_source(self.calls, entry, False)
                source.texts = self.info_texts(entry.package)
                sources.append(source)
            plan = plan_assembly(sources, self.audit.reference, self.audit.compatibility)
            package, report = build_font(self.calls, plan, dict((s.key, s) for s in sources),
                                         lambda what, part: self.progress(what, 0.2 + 0.8 * part, stoppable=False))
        except AssembleError as exc:
            package, error = exc.package, u"%s" % exc
        except Exception as exc:
            error = u"%s" % exc
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if package is not None:
            self.made_fonts.append(package)  # (held for the session)
        for text, level in assembly_lines(plan, report, error, package is not None):
            self.log.add(text, level)
        self.update_buttons()

    @staticmethod
    def info_texts(package):
        """The reference's font info as text (INFO_TEXTS), for the new font. Assumed: fgPackage.info's
        UFO-named attributes (as Proof reads them)."""
        found = {}
        try:
            info = package.fgPackage.info
        except Exception:
            return found
        for attribute in INFO_TEXTS:
            try:
                value = getattr(info, attribute, None)
                if value is not None and not callable(value) and u"%s" % value:
                    found[attribute] = value
            except Exception:
                continue
        return found

    # -- buttons ---------------------------------------------------------------

    def update_buttons(self):
        """Each button clickable only when it would do something (ak.enable keeps the no-font graying)."""
        ak = self.ak
        ticked = len(self.ticked_entries())
        ak.enable(self.compare_button, not self.busy and ticked >= 2)
        ak.enable(self.reference_box, not self.busy and ticked >= 1)
        ak.enable(self.tick_all, not self.busy and ticked < len(self.entries))
        ak.enable(self.tick_none, not self.busy and ticked > 0)
        ak.enable(self.add_button, not self.busy)
        ready = self.audit is not None and not self.stale() and not self.busy
        ak.enable(self.assemble_button, ready)
        try:
            text = assemble_text(len(self.audit.keys) if ready else 0)
            if _prop(self.assemble_button, "text") != text:
                self.assemble_button.setText(text)
        except Exception:
            pass
        ak.enable(self.glyph_window_button, not self.busy and bool(self.selected_glyphs()))
        if self.audit is None:
            for index, title in enumerate(TAB_TITLES):
                try:
                    self.tabs.setTabText(index, title)
                except Exception:
                    pass

    def show(self):
        self.dialog.show()
        self.dialog.raise_()


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open(TOOL):
            return
    except Exception:
        pass
    dialog = FamilyAuditDialog()
    sys._freelab_family_audit = dialog  # kept, even half-built: PythonQt deletes a dialog with no Python reference
    if dialog.failed is not None:
        print("FreeLab Family Audit: %s" % dialog.failed)
        try:
            dialog.dialog.close()
        except Exception:
            pass
        return
    try:
        dialog.ak.hook_menu_order()
    except Exception:
        pass
    try:
        dialog.ak.take_window(TOOL, dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_family_audit":
    main()
