#FLM: Kerning Check
# -*- coding: utf-8 -*-
"""FreeLab kerning check, from FontLab's Scripts menu (or Auto Kerning's Check kerning button).

Three lists for the current font, each to review before anything changes:

- Collisions: kerned pairs whose ink comes closer than a minimum distance at the kerning FontLab
  applies (classes included), each with the value that keeps the minimum, written as a pair of its
  own when ticked.
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
PROGRESS_EVERY = 25  # pairs, entries, or glyphs between two calls to the progress (it lets events through at
# most every 0.1 s: owner's images 176 to 180; every 2000 pairs held the window seconds at a time)
DRAW_STEP, CHECK_STEP, CLEANUP_STEP = u"Drawing the glyphs", u"Checking pairs", u"Checking entries"
COMPARE_STEP, WRITE_STEP, REMOVE_STEP = u"Comparing masters", u"Writing fixes", u"Removing entries"
# The settings row reads as a sentence, its period after the last dropdown (owner's image 243): "List
# kerned pairs whose ink comes within 20 units and that many units closer than without the accent (e.g.,
# Ťo vs. To)." / "... within 20 units of each other, accented or not."
COLLISION_MODES = (("relative", u"and that many units closer than without the accent "
                                u"(e.g., \N{LATIN CAPITAL LETTER T WITH CARON}o vs. To)"),
                   ("absolute", u"of each other, accented or not"))
PAIR_SETS = (("all", u"kerned pairs"), ("common", u"common kerned pairs"))
TABS = ("collisions", "cleanup", "masters")


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


def counted(number, one, many=None):
    """"1 pair", "2 pairs", "13,932 pairs": a count (its thousands set apart) with its noun in the right
    number."""
    return u"%s %s" % (u"{:,}".format(int(number)), one if number == 1 else (many or one + u"s"))


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


def find_collisions(kerning, closest_at, minimum, relative=True, progress=None, variant_of=None, only=None):
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
    only: glyph names; when given, only the pairs with one of them are measured (see tight_pairs).
    progress(done, total) may return False to stop."""
    variant_of = variant_of or (lambda glyph, key: glyph.startswith(key))
    tight = tight_pairs(kerning, only)
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


def tight_pairs(kerning, only=None):
    """[(glyph pair, value)] of the pairs kerned tighter than zero, kerning applied, sorted; only those
    with a glyph of only (names) when given."""
    plain = kerning.plain or {}
    return sorted((pair, round_units(value)) for pair, value in plain.items() if value is not None and value < 0
                  and (only is None or pair[0] in only or pair[1] in only))


def entry_glyphs(kerning, entry):
    """The glyph names an entry names or kerns: a glyph side's name, a class side's members."""
    found = set()
    for name, is_class in entry:
        if is_class:
            found.update(kerning.members.get(name, []))
        else:
            found.add(name)
    return found


def involves(kerning, entry, only):
    """Whether an entry kerns (or names) one of the glyphs of only; True when only is None."""
    return only is None or bool(entry_glyphs(kerning, entry) & set(only))


def limited_cleanup(kerning, found, only):
    """The cleanup findings whose entries kern or name a glyph of only (all of them when only is None).
    The entries are judged with the whole kerning (find_cleanup), then limited: an entry is listed the
    same, limited or not."""
    return [c for c in found if involves(kerning, c.entry, only)]


LIMIT_SHOWN = 24  # glyphs named in the line saying the lists are limited; the others stand as an ellipsis


def limit_line(texts, reason=None, shown=LIMIT_SHOWN):
    """The line over the lists while they are limited to some glyphs: "Pairs with the 12 glyphs
    Glyph Compose built: ..." (reason: what the caller did, "Glyph Compose built"), or "Pairs with these 12
    glyphs: ..."; texts are the glyphs' characters or names."""
    count = len(texts)
    listed = u" ".join(texts[:shown]) + (u" \N{HORIZONTAL ELLIPSIS}" if count > shown else u"")
    if reason:
        what = (u"the glyph %s" % reason) if count == 1 else (u"the %d glyphs %s" % (count, reason))
    else:
        what = u"this glyph" if count == 1 else u"these %d glyphs" % count
    return u"Pairs with %s: %s" % (what, listed)


def glyph_names(glyphs):
    """Glyph names from what a caller hands over: names, or glyphs (anything with a name)."""
    found = []
    for glyph in glyphs or ():
        name = getattr(glyph, "name", glyph)
        if name is None:
            continue
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        name = u"%s" % name
        if name and name not in found:
            found.append(name)
    return found


class Cleanup(object):
    """An entry worth removing (checked: it changes nothing, or names what is gone) or looking at."""

    def __init__(self, entry, value, kind, reason, checked):
        self.entry, self.value, self.kind, self.reason, self.checked = entry, value, kind, reason, checked


# (each kind's count: its noun, one and many, bold with the count, then what follows the noun: convention 18)
CLEANUP_COUNTS = {"missing": (u"entry", u"entries", u" naming what is gone"),
                  "overridden": (u"entry", u"entries", u" overridden everywhere"),
                  "redundant": (u"entry", u"entries", u" changing nothing"),
                  "tiny": (u"tiny value", u"tiny values", u"")}
CLEANUP_KINDS = (("missing", "Names what is gone"), ("overridden", "Overridden everywhere"),
                 ("redundant", "Changes nothing"), ("tiny", "Tiny value"))


def find_cleanup(kerning, glyph_exists, tiny=TINY_UNITS, progress=None):
    """Entries that change nothing, name a class with no members or a glyph the font lacks, or are
    smaller than tiny units; the first two kinds checked for removal. The entries are judged most
    specific first, each as if the ones found before it were removed already: an exception equal to
    its class's value is listed, and the class's entry it then falls back on is not. progress(done,
    total), where given, every PROGRESS_EVERY entries (it may raise to stop)."""
    describe = kerning.describe
    found = []
    present = set(kerning.entries)
    specific_first = sorted(kerning.entries, key=lambda e: (int(e[0][1]) + int(e[1][1]), int(e[0][1]), e))
    for done, entry in enumerate(specific_first):
        if progress is not None and done % PROGRESS_EVERY == 0:
            progress(done, len(specific_first))
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
        elif value and abs(value) < tiny and all(abs(below - value) < tiny for below in fallbacks if below is not None):
            # (tiny, and its pairs as near without it: an exception of -4 to a class pair of -32 keeps its pairs
            # apart, and removing it brought their collisions back, whose fixes were tiny values again: owner's
            # images 338 and 339)
            found.append(Cleanup(entry, value, "tiny", u"smaller than %s" % counted(tiny, u"unit"), False))
    order = dict((kind, index) for index, (kind, _) in enumerate(CLEANUP_KINDS))
    found.sort(key=lambda c: (order[c.kind], describe(c.entry)))
    return found


def cleanup_status(listed, entries, counts, limited=u"", bold=lambda text: u"%s" % text):
    """The Cleanup list's status line: "3 of 120 entries listed: 2 entries changing nothing, 1 tiny value."
    (counts: {kind: how many}; limited: " with these 12 glyphs" while the lists are limited); with nothing
    listed, "No entries listed." (owner's image 190: "0 of 0 entries listed: none."). Each count bold with
    its noun ("**3 of 120 entries**", "**2 entries** changing nothing": owner's images 297 and 301)."""
    if not listed:
        return u"No entries listed."
    return u"%s%s listed: %s." % (
        bold(u"%s of %s" % (u"{:,}".format(listed), counted(entries, u"entry", u"entries"))), limited,
        u", ".join(bold(counted(counts[kind], CLEANUP_COUNTS[kind][0], CLEANUP_COUNTS[kind][1])) + CLEANUP_COUNTS[kind][2]
                   for kind, _ in CLEANUP_KINDS if kind in counts))


def collision_status(found, tight, minimum, relative=True, common=False, limited=u"", bold=lambda text: u"%s" % text):
    """The Collisions list's status line: found pairs listed of tight kerned tighter (than zero), minimum
    units the distance set, relative the mode (closer than without the accent); common: only common pairs;
    limited: " with these 12 glyphs" while the lists are limited. Right at 0, 1, and 2 (owner's image 229:
    "None of the 0 pairs kerned tighter comes within 41 units")."""
    noun = u"common pair" if common else u"pair"
    distance = bold(counted(minimum, u"unit"))
    what = (u"within %s, and that many units closer than without the accent" % distance if relative
            else u"within %s of each other" % distance)
    if not tight:
        return u"No %s%s is kerned tighter: nothing to check." % (noun, limited)
    if tight == 1:
        return u"The only %s%s kerned tighter %s %s%s." % (noun, limited, u"comes" if found else u"does not come", what,
                                                         u", kerning applied" if found else u"")
    if not found:
        return u"None of the %s%s kerned tighter comes %s." % (bold(counted(tight, noun)), limited, what)
    # (the count bold with its noun: "**2 of the 1,438 pairs**", owner's images 297 and 301)
    return u"%s%s kerned tighter %s %s, kerning applied." % (
        bold(u"%s of the %s" % (u"{:,}".format(found), counted(tight, noun))), limited,
        u"comes" if found == 1 else u"come", what)


def masters_status(found, masters, limited_lists=False, limited=u"", bold=lambda text: u"%s" % text):
    """The Masters list's status line: found differences between masters (a count); limited_lists: the
    lists limited to some glyphs (limited: " with these 12 glyphs"). Each count bold with its noun
    ("between **3 masters**", not "between **3** masters": owner's images 297 and 301)."""
    differences, between = bold(counted(found, u"difference")), bold(counted(masters, u"master"))
    if not limited_lists:
        return (u"%s between %s." % (differences, between) if found
                else u"The %s kern the same entries, with the same signs." % between)
    return (u"%s between %s, in the entries and classes%s." % (differences, between, limited) if found
            else u"The %s kern the entries%s the same, with the same signs, and their classes hold the same "
                 u"glyphs." % (between, limited))


AUTOMATIC_KINDS = ("missing", "overridden", "redundant")  # ticked for removal: they change nothing


def still_removable(kerning, chosen, glyph_exists, tiny=TINY_UNITS, progress=None):
    """(the cleanup findings chosen that may still go, the number left) judged again on the kerning as
    it is now: an entry whose value changed is left, and so is one that changed nothing at the check
    but would change something now (an exception equal to its class pair's value, that value edited
    since). The others may go in any order: find_cleanup judged each as if the ones found before it
    were removed, and keeping some of those changes nothing either."""
    fresh = dict((c.entry, c.kind) for c in find_cleanup(kerning, glyph_exists, tiny, progress))
    found, stale = [], 0
    for c in chosen:
        if c.entry not in kerning.entries or round_units(kerning.values.get(c.entry) or 0) != c.value:
            stale += 1
        elif c.kind in AUTOMATIC_KINDS and fresh.get(c.entry) not in AUTOMATIC_KINDS:
            stale += 1
        else:
            found.append(c)
    return found, stale


def value_without(kerning, entry, left, right):
    """The kerning a glyph pair would get without one entry: the next entry that applies to it."""
    for candidate in kerning.candidates(left, right):
        if candidate != entry and candidate in kerning.entries:
            return round_units(kerning.values.get(candidate) or 0)
    return 0


class MasterDifference(object):
    def __init__(self, kind, subject, values, reason, entry=None):
        self.kind, self.subject, self.values, self.reason = kind, subject, values, reason  # values: [(master, text)]
        self.entry = entry  # the entry, or the class's name


def compare_masters(kernings, tolerance=SIGN_TOLERANCE, only=None):
    """[(master, kerning)] compared: entries kerned in some masters only, entries tightening in one
    master and loosening in another, and classes whose members differ. only: glyph names; when given,
    only the entries kerning one of them (in any master) and the classes holding one."""
    masters = [master for master, _ in kernings]
    found = []
    if len(kernings) < 2:
        return found
    entries = set()
    for _, kerning in kernings:
        entries |= set(kerning.entries)
    describe = kernings[0][1].describe
    if only is not None:
        entries = set(entry for entry in entries if any(involves(k, entry, only) for _, k in kernings))
    for entry in sorted(entries):
        values = [(master, round_units(k.values[entry]) if entry in k.entries else None) for master, k in kernings]
        present = [master for master, value in values if value is not None]
        known = [value for _, value in values if value is not None]
        shown = [(master, u"\N{EN DASH}" if value is None else u"%d" % value) for master, value in values]
        if len(present) < len(masters):
            missing = [master for master in masters if master not in present]
            found.append(MasterDifference("missing", describe(entry), shown, u"not kerned in %s" % u", ".join(missing),
                                          entry))
        elif min(known) < -tolerance and max(known) > tolerance:
            found.append(MasterDifference("sign", describe(entry), shown,
                                          u"tightens in one master, loosens in another: an instance between them "
                                          u"may collide", entry))
    names = set()
    for _, kerning in kernings:
        names |= set(kerning.classes)
    for name in sorted(names):
        sets = [(master, frozenset(k.members.get(name, [])) if name in k.classes else None) for master, k in kernings]
        if only is not None and not any(members and members & set(only) for _, members in sets):
            continue
        if len(set(members for _, members in sets)) > 1:
            shown = [(master, u"\N{EN DASH}" if members is None else u" ".join(sorted(members))) for master, members in sets]
            found.append(MasterDifference("class", u"class %s" % name, shown, u"its members differ between masters", name))
    return found


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def _main_code(fg):
    """The one code point a glyph stands for (Auto Kerning's main_code: U+65E5 for a glyph FontLab gives the
    Kangxi radical U+2F47 first), or its unicode where Auto Kerning is not loaded."""
    shared = sys.modules.get(AUTO_KERNING_MODULE)
    main = getattr(shared, "main_code", None)
    return main(fg) if main is not None else fg.unicode


def glyph_text(package, name):
    """A glyph's character when it has one, else its name."""
    try:
        glyph = package.findName(name)
        # (flGlyph has no unicode of its own; main_code: not a Kangxi radical FontLab may give first)
        code = _main_code(glyph.fgGlyph) if glyph is not None else None
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


def screen_pair(ak, package, first, second, chars=None):
    """The glyph pair on screen, (left, right), of a kerning key: a right-to-left key is kept in text
    order, its right glyph first (Auto Kerning's screen_of_key), whatever the font's other scripts: each
    pair by its own glyphs. A glyph's direction is its character's, or its base glyph's for an unencoded
    form (uni0628.fina, yod.alt: Auto Kerning's direction_char), so that a key of two contextual forms
    of a right-to-left script is measured as it stands. chars: {name: character or None}, filled as
    glyphs are looked up (a check of thousands of pairs asks FontLab once per glyph)."""
    chars = {} if chars is None else chars
    for name in (first, second):
        if name not in chars:
            chars[name] = ak.direction_char(package, name)
    return ak.screen_of_key(chars[first], chars[second], first, second)


def pair_text(package, left, right, ak=None):
    """A glyph pair's characters as a reader sees them (a right-to-left pair set right to left, see
    Auto Kerning's pair_label), or its glyphs' names."""
    a, b = glyph_text(package, left), glyph_text(package, right)
    if len(a) == 1 and len(b) == 1:  # (left and right are a kerning key: a right-to-left one is in text order)
        return ak.pair_label(*ak.screen_of_key(a, b, a, b)) if ak is not None else a + b
    return u"%s %s" % (a, b)


class InkDistances(object):
    """The narrowest gap between two glyphs' ink at some kerning, from Auto Kerning's measuring."""

    def __init__(self, ak, package, master, names, progress=None):
        """progress(done, total), where given, every PROGRESS_EVERY glyphs drawn (it may raise to stop)."""
        self.ak = ak
        self.glyphs = ak.FontLabGlyphs(package, master, ak.EM_PIXELS)
        self.known = set()
        names = list(names)
        for done, name in enumerate(names):
            if progress is not None and done % PROGRESS_EVERY == 0:
                progress(done, len(names))
            if self.glyphs.add(name):
                self.known.add(name)
        self.core = ak.Core()
        self.units_per_pixel = self.glyphs.upm / float(ak.EM_PIXELS)
        self.package, self.chars = package, {}

    def closest_at(self, left, right, value):
        """At the pair's kerning value: (left, right) is a kerning key, measured as it stands on screen
        (a right-to-left key, in text order, the other way round)."""
        if left not in self.known or right not in self.known:
            return None
        ak = self.ak
        left, right = screen_pair(ak, self.package, left, right, self.chars)
        a, b = self.glyphs.image(left), self.glyphs.image(right)
        _, raw_right_of_left, _, _ = a.contours(self.core)
        raw_left_of_right, _, _, _ = b.contours(self.core)
        offset = ak.base_offset(a, b) - value / self.units_per_pixel
        gap = self.core.closest(raw_right_of_left, raw_left_of_right, a.height, offset)
        return None if gap > 1e8 else gap * self.units_per_pixel


# The Collisions list's columns: the pair (drawn from the font beside its characters), its glyphs' names,
# then its numbers and where its value comes from
COLLISION_COLUMNS = (u"Pair", u"Glyphs", u"Kerning", u"Distance", u"Fix", u"Set by", u"Compared with")
NUMBER_COLUMNS = (u"Kerning", u"Distance", u"Fix", u"Value")  # columns of numbers (add_row right-aligns their cells)


ACTIONS = {"collisions": (u"Write ticked fixes", u"Write %s", (u"ticked fix", u"ticked fixes")),
           "cleanup": (u"Clean up ticked entries", u"Clean up %s", (u"ticked entry", u"ticked entries"))}
# (Tick, not Check, for check boxes: owner's image 261, "Check" being the verb of the buttons that run checks)
TICK_ALL, TICK_NONE = u"Tick all", u"Tick none"


def action_text(key, count):
    """A list's button, with the count of its ticked rows: "Clean up 3 ticked entries"."""
    none, some, nouns = ACTIONS[key]
    return some % counted(count, *nouns) if count else none


HELP = u"""<b>FreeLab Kerning Check</b><br>
Three lists for the current font's kerning. Nothing changes until you click a list's button.<br><br>
<b>Collisions</b>: kerned pairs whose ink comes closer than the distance you set, at the kerning
FontLab applies (kerning classes included), all of them or only those common in text. The fix is
the value that keeps that distance; written, it is a pair of its own, so the class kerns its other
glyphs as before. If a fix looks off, drag the <i>Adjusted</i> preview's right glyph left or right
(or click it and press <i>Left</i> or <i>Right</i>, with <i>Shift</i> for 10 units): the fix follows.<br>
<b>Cleanup</b>: entries that change nothing (their pairs get the same value without them, or each
pair they cover has a value of its own), entries naming a class or glyph that is gone (ticked), and
values smaller than the size you set (unticked: look at them first).<br>
<b>Masters</b>: entries some masters kern and others do not, entries tightening in one master and
loosening in another, and classes whose members differ between masters (a font with one master has
nothing to compare).<br><br>
<b>Opened from another script</b> (<i>Glyph Compose</i> after building or moving diacritics, <i>Auto Spacing</i>
after spacing): the lists hold only the pairs and entries with the glyphs it changed, as the line over
them says; <i>Show all</i> lists the whole font's.<br><br>
Each list is checked as its tab is first shown, and again after an undo or an edit in FontLab; the line
under the font's name says what the list shown holds.
Double-click a row's pair (or select it and click <i>Show in Glyph window</i>) to look at it with
FontLab's own tools. <i>Tick all</i> and <i>Tick none</i> tick or untick a whole list;
<i>Restore suggestions</i> puts its ticks back as it first came.
Click this help's <i>?</i> button, then any control, for what it does."""


class TabStatus(object):
    """A list's status line, shown in the window's header, under its font line, while the list's tab is
    shown (owner's image 229: the result line sat under the settings row, the only window whose text
    was under its controls). setText as a label's: the text is kept, and shown when the tab is."""

    def __init__(self, line, shown):
        self.line, self.shown, self.text = line, shown, u""

    def setText(self, text):
        self.text = u"%s" % text
        try:
            if self.shown(self):
                self.line.setText(self.text)
        except Exception:
            pass


def hint_height(widget):
    """A widget's size hint's height (0 where it cannot be read)."""
    try:
        hint = widget.sizeHint
        hint = hint() if callable(hint) else hint
        return max(0, int(hint.height()))
    except Exception:
        return 0


def level_rows(boxes):
    """Rows of controls (each a widget whose layout holds a row) made as tall as one another, so a table
    under them stays where it is as tabs are switched (owner's images 285 and 286: the Masters tab's row,
    a button alone, was a few pixels shorter than Cleanup's, whose spin box is taller, and its table moved
    up): each row's least height the tallest size hint of the controls in any of them, hidden ones too.
    Read when called (after the window's styles). The height set, or 0. Never raises."""
    tallest = 0
    for box in boxes:
        try:
            layout = box.layout()
            for index in range(int(layout.count())):
                widget = layout.itemAt(index).widget()
                if widget is not None:
                    tallest = max(tallest, hint_height(widget))
        except Exception:
            continue
    if tallest:
        for box in boxes:
            try:
                box.setMinimumHeight(tallest)
            except Exception:
                pass
    return tallest


class Tab(object):
    """One list: its settings row, its tree, its status (in the window's header), its action button."""

    def __init__(self, QtGui, columns, action, status):
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.layout.setContentsMargins(0, 0, 0, 0)  # (the list's frame level with the log's, owner's image 268)
        # (its settings row in a widget of its own: as tall as the other tabs' rows, level_rows)
        self.settings_box = QtGui.QWidget()
        self.settings = QtGui.QHBoxLayout(self.settings_box)
        self.settings.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.settings_box)
        self.status = status  # (TabStatus: in the window's header, rich text, a line per sentence)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(columns))
        self.tree.setHeaderLabels(list(columns))
        self.tree.setRootIsDecorated(False)
        self.layout.addWidget(self.tree, 1)
        # (its buttons sit in the window's bottom row, as every tool's: bottom_row; shown with its page)
        self.action = QtGui.QPushButton(action) if action else None
        self.restore = QtGui.QPushButton("Restore suggestions") if action else None
        self.check_all = QtGui.QPushButton(TICK_ALL) if action else None
        self.check_none = QtGui.QPushButton(TICK_NONE) if action else None
        if self.restore is not None:
            self.restore.setWhatsThis(u"Puts this list's ticks back as it first came.")
            self.check_all.setWhatsThis(u"Ticks every row of this list.")
            self.check_none.setWhatsThis(u"Unticks every row of this list.")
        self.findings, self.first_checks = [], []


class KerningCheckDialog(object):
    def __init__(self, glyphs=None, reason=None):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = load_auto_kerning()
        main = self.ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Kerning Check")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        layout = self.ak.window_layout(dialog)  # (its content scrolls on a small screen)
        # The header, as every window's (owner's images 222, 223, 229): the font line (the top row), the
        # shown list's status line, the line while the lists are limited, then the header's separator,
        # then the tabs
        self.font_label = self.ak.status_label()
        self.font_label.setWordWrap(True)
        layout.addWidget(self.font_label)
        self.status_line = self.ak.status_label()  # (the shown list's: TabStatus)
        self.status_line.setWordWrap(True)
        layout.addWidget(self.status_line)
        # The lists limited to some glyphs (another script's, after it changed them), and a way out
        names = glyph_names(glyphs)
        self.only, self.only_reason = (set(names) if names else None), reason
        self.only_order = names
        limit_row = QtGui.QHBoxLayout()
        self.limit_label = QtGui.QLabel(u"")
        self.ak.rich(self.limit_label)
        self.limit_label.setWordWrap(True)
        self.limit_label.setWhatsThis(u"The lists show only the pairs and entries with these glyphs: those another "
                                      u"script just changed. <i>Show all</i> lists the whole font's.")
        self.show_all_button = QtGui.QPushButton("Show all")
        self.show_all_button.setWhatsThis(u"Lists every pair and entry of the font again, not only those with these glyphs.")
        limit_row.addWidget(self.limit_label, 1)
        limit_row.addWidget(self.show_all_button)
        self.limit_widget = QtGui.QWidget()
        self.limit_widget.setLayout(limit_row)
        limit_row.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.limit_widget)
        self.limit_widget.setVisible(False)
        layout.addWidget(self.ak.header_separator())  # (between the header and the tabs: owner's images 222 and 223)
        self.log = self.ak.Log()
        self.seen_history, self.stale, self.buttons_due = None, set(TABS), False
        # A tab bar over plain pages: a QTabWidget's themed page drew its buttons with light frames in dark mode
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        layout.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        layout.addWidget(self.pages, 1)
        # The previews side by side, each under its caption (the shared preview_caption), a line between two
        previews = QtGui.QHBoxLayout()
        self.previews, self.preview_captions = [], []
        for number in range(3):
            if number:
                previews.addWidget(self.ak.separator(vertical=True))
            column = QtGui.QVBoxLayout()
            caption = self.ak.preview_caption()
            caption.setAlignment(QtCore.Qt.AlignCenter)
            column.addWidget(caption)
            self.preview_captions.append(caption)
            label = QtGui.QLabel()
            label.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setWordWrap(False)  # (its hint while no pair is selected stays on one line, owner's request)
            label.setMinimumHeight(int(self.ak.PAIR_PREVIEW_EM * 1.7))
            label.setWhatsThis(u"The selected pair as it is set now and adjusted: with its fix (<i>Collisions</i>), or "
                               u"without its entry (<i>Cleanup</i>), beside its base pair; its glyphs are drawn see-through, "
                               u"so where their ink overlaps it is denser.")
            column.addWidget(label, 1)
            previews.addLayout(column, 1)
            self.previews.append(label)
        layout.addLayout(previews)
        self.adjust_width = None
        self.adjusting = self.ak.PairDrag(self.previews[1], self.adjusted_value,
                                          lambda value: self.set_fix(self.adjustable(), value),
                                          lambda step: self.ak.select_next_row(self.current_tab().tree, step),
                                          self.units_scale)

        shown = lambda status: self.current_tab().status is status
        self.collisions = Tab(QtGui, COLLISION_COLUMNS, action_text("collisions", 0), TabStatus(self.status_line, shown))
        tab = self.collisions
        # A sentence the controls complete, its period after the last dropdown, then Check (owner's image 243)
        tab.settings.addWidget(QtGui.QLabel("List"))
        self.pair_set = QtGui.QComboBox()
        for _, label in PAIR_SETS:
            self.pair_set.addItem(label)
        self.pair_set.setWhatsThis(u"All kerned pairs, or only those common in text (frequent in 24 languages and "
                                   u"kerned in fonts: the list <i>Auto Kerning</i>'s <i>Common pairs</i> uses).")
        tab.settings.addWidget(self.pair_set)
        self.common = None  # {two characters: rank}, read when first needed
        tab.settings.addWidget(QtGui.QLabel("whose ink comes within"))
        self.minimum = QtGui.QSpinBox()
        self.minimum.setRange(-200, 400)
        self.suffix_slots = [self.ak.counted_suffix(self.minimum, u"unit")]  # ("1 unit", "2 units")
        self.minimum.setWhatsThis("The narrowest distance between the two glyphs' ink, at the kerning FontLab applies, "
                                  "for a pair to be listed (0: pairs that touch; below 0: pairs that overlap by "
                                  "more than that).")
        tab.settings.addWidget(self.minimum)
        self.mode = QtGui.QComboBox()
        for _, label in COLLISION_MODES:
            self.mode.addItem(label)
        self.mode.setWhatsThis(u"How both glyphs' ink is measured: the narrowest horizontal distance between them, "
                               u"row by row, at the pair's kerning.<br><i>And that many units closer than without "
                               u"the accent</i>: a pair is listed when its ink comes within the distance set, and "
                               u"also comes closer by at least as many units than the same pair without the accent "
                               u"or stroke, at the same value (\N{LATIN CAPITAL LETTER T WITH CARON}o against To, "
                               u"\N{LATIN CAPITAL LETTER T WITH STROKE}o against To): what a class's value does to "
                               u"an accented or wider member. It suits any font, also one whose letters touch on "
                               u"purpose.<br><i>Of each other, accented or not</i>: every kerned pair whose ink "
                               u"comes within the distance set.")
        tab.settings.addWidget(self.mode)
        self.ak.sentence_end(tab.settings)
        self.collisions_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(self.collisions_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"The pairs whose ink comes too close, closest first: their kerning now, the "
                              u"narrowest distance between their ink with it, the value that keeps the distance "
                              u"you set, and the entry the kerning comes from.")
        tab.action.setWhatsThis(u"Writes each ticked pair's fix as a pair of its own (the class it takes its value "
                                u"from kerns its other glyphs as before).")

        self.cleanup = Tab(QtGui, ("Entry", "Value", "Why"), action_text("cleanup", 0), TabStatus(self.status_line, shown))
        tab = self.cleanup
        tab.settings.addWidget(QtGui.QLabel("Also list values smaller than"))
        self.tiny = QtGui.QSpinBox()
        self.tiny.setRange(0, 50)
        self.tiny.setValue(TINY_UNITS)
        self.suffix_slots.append(self.ak.counted_suffix(self.tiny, u"unit"))
        self.tiny.setWhatsThis("Entries smaller than this are listed too, unticked (0: none).")
        tab.settings.addWidget(self.tiny)
        self.ak.sentence_end(tab.settings)
        self.cleanup_button = QtGui.QPushButton("Check")
        tab.settings.addWidget(self.cleanup_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"Entries that change nothing or name what is gone (ticked), and tiny values "
                              u"(unticked).")
        tab.action.setWhatsThis(u"Cleans up: removes the ticked entries from the current master.")

        self.masters = Tab(QtGui, ("Entry or class", "Values", "Why"), None, TabStatus(self.status_line, shown))
        tab = self.masters
        self.masters_button = QtGui.QPushButton("Compare masters")
        tab.settings.addWidget(self.masters_button)
        tab.settings.addStretch(1)
        tab.tree.setWhatsThis(u"Differences between the font's masters: entries kerned in some only, entries "
                              u"whose sign flips, classes whose members differ.")

        for tab, label in ((self.collisions, "Collisions"), (self.cleanup, "Cleanup"), (self.masters, "Masters")):
            self.ak.table_layout(tab.tree)
            if tab is not self.masters:  # (as the other tools' lists: each row's pair drawn from the font)
                tab.tree.setIconSize(QtCore.QSize(*self.ak.glyph_icon_size(2)))
                tab.tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
            if tab.action is not None:
                for button in (tab.check_all, tab.check_none, tab.restore, tab.action):
                    self.ak.enable(button, False)
            self.tabs.addTab(label)
            self.pages.addWidget(tab.widget)
        layout.addWidget(self.log.widget)

        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected row's pair in a <i>Glyph</i> window, between H's, n's, "
                                              u"and o's.")
        self.close_button = QtGui.QPushButton("Close")
        layout.addLayout(self.bottom_row(QtGui))

        self.collisions_button.connect("clicked()", self.check_collisions)
        self.cleanup_button.connect("clicked()", self.check_cleanup)
        self.masters_button.connect("clicked()", self.check_masters)
        self.collisions.action.connect("clicked()", self.write_fixes)
        self.cleanup.action.connect("clicked()", self.remove_entries)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        for tab in (self.collisions, self.cleanup, self.masters):
            tab.tree.connect("itemSelectionChanged()", self.update_previews)
            tab.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons_soon())
            tab.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
            if tab.restore is not None:
                tab.restore.connect("clicked()", lambda tab=tab: self.restore(tab))
                tab.check_all.connect("clicked()", lambda tab=tab: self.check_every(tab, True))
                tab.check_none.connect("clicked()", lambda tab=tab: self.check_every(tab, False))
        self.show_all_button.connect("clicked()", self.show_all)
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        self.package = self.master = None
        self.chars = {}  # {glyph name: its character or None}, for screen_pair
        self.busy = False
        self.ak.add_tools_button(dialog, "Kerning Check", getattr(self, "log", None))  # (the other font tools, a click away)
        self.ak.plain_buttons(dialog)
        self.level_settings()
        self.read_font()
        self.show_limit()
        self.history_timer = self.ak.watch_history(self)
        self.flagging = [self.ak.flag_menu(tab.tree, self, lambda: list(self.selected_pair() or []),
                                           (lambda tab: lambda item: self.row_names(tab, item))(tab))
                         for tab in (self.collisions, self.cleanup, self.masters)]
        self.update_buttons()

    # -- the font ------------------------------------------------------------

    def current_font(self):
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None
        except Exception:
            pass
        package = self.ak.window_font(self, workspace)  # this window's font
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def read_font(self):
        """The current font and master; False (and said so) when no font is open."""
        self.package = self.current_font()
        self.master = self.package.master if self.package is not None else None
        self.chars = {}  # {glyph name: its character or None}, for screen_pair (read again with the font)
        if self.package is None:
            self.font_label.setText(self.ak.no_font_line())
            self.update_buttons_soon()  # (its settings grayed out)
            return False
        self.update_buttons_soon()  # (its settings back on)
        upm = float(self.package.upm)
        if not self.minimum.value and not getattr(self, "minimum_set", False):
            self.minimum.setValue(round_units(MIN_DISTANCE_SHARE * upm))
            self.minimum_set = True
        count = self.package.mastersCount
        # (the masters counted only when more than one, as every window's: owner's images 223 and 238)
        self.font_label.setText(self.ak.font_named(self.package.tfn, self.master, count) + u".")
        self.tabs.setTabEnabled(2, count > 1)
        self.tabs.setTabToolTip(2, u"" if count > 1 else u"This font has one master: nothing to compare.")
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
        self.read_font()
        self.update_buttons()
        self.log.add(u"The font or master changed since the check: check again.", "warning")
        return False

    def progress(self, what, done, total, stoppable=True):
        """The work at done of total, in the window's top row (ak.busy_progress: the window answers, the
        user's input held off; the step's name kept, the bar moving); raises ak.Stopped where stoppable and
        the user asked it to stop (the tools menu, an arrow, Close, Esc). True, for find_collisions'."""
        self.ak.busy_progress(self, what, float(done) / total if total else None, stoppable=stoppable)
        return True

    def stopped(self, tab, what=u"The check"):
        """A list's work stopped by the user: the list left empty, its status line saying so."""
        tab.tree.clear()
        tab.findings, tab.first_checks = [], []
        tab.status.setText(u"%s was stopped: nothing is listed. Click <i>%s</i> to check again." % (
            what, u"Compare masters" if tab is getattr(self, "masters", None) else u"Check"))
        self.update_previews()
        self.update_buttons()

    def begin_writing(self):
        """before_changes for a kerning write (begin_write: False, said in the log, when nothing may be
        written): the step records the whole font, its glyphs too, which have no state of their own in a font
        opened afresh, and undoing it made FontLab print "We have a problem with the component 'P' in glyph
        'Rho:Regular'" for each glyph built from components (owner's image 336)."""
        return self.ak.begin_write(self.fontlab, self.package, u"FreeLab Kerning Check", self.log)

    def after_writing(self):
        """notify_changed's WriteStatus (kerning only, no glyph added; begun by begin_writing)."""
        return self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Kerning Check", added=False)

    # -- the lists limited to some glyphs ------------------------------------

    def show_limit(self):
        """The line over the lists while they are limited to some glyphs, with Show all; hidden when not."""
        try:
            if self.only is None:
                self.limit_widget.setVisible(False)
                return
            texts = [glyph_text(self.package, name) if self.package is not None else name for name in self.only_order]
            self.limit_label.setText(self.ak.html(limit_line(texts, self.only_reason)))
            self.limit_widget.setVisible(True)
        except Exception:
            pass  # (the line is a courtesy: the lists stay limited, and Show all still works)

    def limit_to(self, glyphs, reason=None):
        """The lists limited to the pairs and entries with these glyphs (None: every one), checked again."""
        names = glyph_names(glyphs)
        self.only, self.only_order, self.only_reason = (set(names) if names else None), names, reason
        self.show_limit()
        self.stale = set(TABS)
        if self.package is not None or self.read_font():
            self.check(TABS[self.tabs.currentIndex])

    def show_all(self):
        """Show all: the limit dropped, every pair and entry of the font listed again."""
        if self.only is None:
            return
        self.limit_to(None)
        self.log.add(u"Every pair and entry of the font listed again, not only those with the glyphs given.")

    def limited(self):
        """" with these 12 glyphs", for a status line while the lists are limited; else nothing."""
        if self.only is None:
            return u""
        return u" with %s" % (u"this glyph" if len(self.only) == 1 else u"these %d glyphs" % len(self.only))

    # -- buttons, the History, the tabs -------------------------------------

    def tab_of(self, key):
        return getattr(self, key)

    def current_tab(self):
        return self.tab_of(TABS[self.tabs.currentIndex])

    def update_buttons_soon(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        QtCore, QtGui = _qt()
        self.buttons_due = False
        for key, tab in (("collisions", self.collisions), ("cleanup", self.cleanup)):
            rows = self.rows(tab)
            checks = [item.checkState(0) == QtCore.Qt.Checked for item in rows]
            some_on, some_off = self.ak.checks_of(checks, bool)
            self.ak.enable(tab.action, some_on and not self.busy)
            self.ak.enable(tab.check_all, some_off and not self.busy)
            self.ak.enable(tab.check_none, some_on and not self.busy)
            try:
                text = action_text(key, sum(1 for on in checks if on))
                if tab.action.text != text:
                    tab.action.setText(text)
            except Exception:
                pass
            self.ak.enable(tab.restore, checks != tab.first_checks[:len(checks)] or len(checks) != len(tab.first_checks))
        finding = self.selected_finding() if self.package is not None else None
        self.ak.enable(self.glyph_window_button, isinstance(finding, (Collision, Cleanup)))
        # No font: nothing to check, and the settings set nothing; Check reads a font once one is open
        has_font = self.package is not None
        can_read = not self.busy and (has_font or self.ak.fonts_open(self.fontlab))
        for button in (self.collisions_button, self.cleanup_button, self.masters_button):
            self.ak.enable(button, can_read)
        for widget in (self.pair_set, self.minimum, self.mode, self.tiny):
            self.ak.enable(widget, has_font)

    def first_checks_of(self, tab):
        QtCore, QtGui = _qt()
        tab.first_checks = [item.checkState(0) == QtCore.Qt.Checked for item in self.rows(tab)]

    def check_every(self, tab, on):
        """Tick all, or Tick none: every row of the list (a group's row follows its rows), the rows of
        closed groups too, which the log says (the shared check_rows)."""
        self.ak.check_rows(self.rows(tab), bool(on), self.log, TICK_ALL if on else TICK_NONE,
                           u"pair" if tab is self.collisions else u"entry", None if tab is self.collisions else u"entries",
                           (u"in a closed group", u"in closed groups"))
        self.update_buttons()

    def restore(self, tab):
        QtCore, QtGui = _qt()
        for item, on in zip(self.rows(tab), tab.first_checks):
            item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.update_buttons()
        self.log.add(u"Ticks restored as suggested.")

    def double_clicked(self, item, column):
        if column in (0, 1) and self.tabs.currentIndex == 0 or column == 0:  # the pair, or its glyphs' names
            self.show_in_glyph_window()

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick): the
        lists emptied and the font read again, the list shown checked for the new font."""
        for tab in (self.collisions, self.cleanup, self.masters):
            tab.tree.clear()
            tab.findings, tab.first_checks = [], []
            tab.status.setText(u"")
        self.stale = set(TABS)
        if self.read_font():
            self.check(TABS[self.tabs.currentIndex])
        self.update_previews()
        self.update_buttons()

    def check(self, key):
        {"collisions": self.check_collisions, "cleanup": self.check_cleanup, "masters": self.check_masters}[key]()

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the list shown is checked again, the others when shown."""
        self.stale = set(TABS)
        key = TABS[self.tabs.currentIndex]
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): checked again.")
        self.check(key)

    # -- the lists ---------------------------------------------------------

    def pair_icon(self, pair, value, row):
        """A row's picture of its pair at a kerning value (the first GLYPH_ICON_ROWS rows), or None."""
        QtCore, QtGui = _qt()
        if pair is None or row >= self.ak.GLYPH_ICON_ROWS or self.package is None:
            return None
        pair = screen_pair(self.ak, self.package, pair[0], pair[1], self.chars)  # (drawn as on screen)
        return self.ak.glyph_icon(self.package, self.master, list(pair), self.dialog.palette.color(QtGui.QPalette.WindowText),
                                  value)

    @staticmethod
    def add_row(tab, index, texts, checkable, checked, tip=u"", parent=None, icon=None):
        QtCore, QtGui = _qt()
        item = QtGui.QTreeWidgetItem(list(texts))
        if icon is not None:
            item.setIcon(0, icon)
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
        # every row measured, those of closed groups too: sized while the groups were closed, the names
        # were cut once one was opened (the shared fit_rows)
        # (its headers centered by it, as every list's: owner's report 141)
        ak = load_auto_kerning()
        ak.fit_rows(tab.tree, range(tab.tree.columnCount - 1))
        # the first column holds the rows inside collapsed groups too, which the resize does not measure
        room = QtGui.QFontMetrics(tab.tree.font).width(u"MMMMMM") + 3 * tab.tree.indentation
        if tab.tree.columnWidth(0) < room:
            tab.tree.setColumnWidth(0, room)
            ak.note_wants(tab.tree, {0: room})
            ak.share_columns(tab.tree, after_fit=True)

    def check_collisions(self):
        if self.busy or not self.read_font():
            return
        tab = self.collisions
        self.busy = True
        tab.tree.clear()
        tab.findings = []
        self.ak.enable(tab.action, False)
        # Under the window's top-row progress, stoppable (owner's images 176 to 180: every long step there)
        self.ak.busy_start(self, DRAW_STEP)
        try:
            kerning = self.kerning()
            if kerning.plain is None:
                tab.status.setText(u"FontLab did not give this master's kerning with its classes applied.")
                return
            only = self.only
            if only is None:
                names = set(name for pair in kerning.plain for name in pair)
            else:  # the pairs with the glyphs given, and the key glyphs they are compared with
                names = set(name for pair, _ in tight_pairs(kerning, only) for name in pair)
                names.update(key for key in (key_glyph(kerning, name) for name in kerning.classes) if key)
            ink = InkDistances(self.ak, self.package, self.master, names,
                               lambda done, total: self.progress(DRAW_STEP, done, total))
            minimum = self.minimum.value
            relative = COLLISION_MODES[self.mode.currentIndex][0] == "relative"
            chars = {}

            def char_of(name):
                if name not in chars:
                    text = glyph_text(self.package, name)
                    chars[name] = text if len(text) == 1 and text != name else None
                return chars[name]

            common_only = PAIR_SETS[self.pair_set.currentIndex][0] == "common"
            if common_only and self.common is None:
                self.common = self.ak.common_pairs()

            def common(left, right):  # (a kerning key; the common pairs are as typed, mirrored brackets their own)
                a, b = char_of(left), char_of(right)
                return a is not None and b is not None and self.ak.text_order(*self.ak.screen_of_key(a, b, a, b)) in self.common

            found = find_collisions(kerning, ink.closest_at, minimum, relative,
                                    lambda done, total: self.progress(CHECK_STEP, done, total),
                                    lambda name, key: is_variant(name, key, char_of), only)
            if common_only:
                found = [c for c in (found or []) if common(c.left, c.right)]
        except self.ak.Stopped:
            found = self  # (said once busy is over: stopped)
        except Exception as exc:
            tab.status.setText(u"The check failed: the log says why.")  # (the font line stays: owner's image 224)
            self.log.add(self.ak.html(exc), "error")
            return
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if found is self:
            self.stopped(tab)
            return
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
                parents[key] = self.add_group(tab, (u"%s (%s)" % (glyph_text(self.package, key),
                                                                  counted(len(groups[key]), u"pair")),))
                parents[key].setFirstColumnSpanned(True)  # (a row as the others: its text level with its arrow)
        for index, c in enumerate(found):
            where = kerning.describe(c.entry) if c.entry is not None else u""
            if c.reference is not None:
                compared = u"%s: %d" % (pair_text(self.package, c.reference[0], c.reference[1], self.ak), round_units(c.reference_gap))
                tip = (u"%s %s: %d now, its ink %s apart, %s closer than %s %s at the same value; %d sets it "
                       u"as far apart." % (c.left, c.right, c.value, counted(round_units(c.gap), u"unit"),
                                           counted(round_units(c.reference_gap - c.gap), u"unit"),
                                           c.reference[0], c.reference[1], c.fix))
            else:
                compared = u""
                tip = u"%s %s: %d now, its ink %s apart; %d keeps %s." % (
                    c.left, c.right, c.value, counted(round_units(c.gap), u"unit"), c.fix, counted(minimum, u"unit"))
            self.add_row(tab, index, (pair_text(self.package, c.left, c.right, self.ak), u"%s %s" % (c.left, c.right),
                                      u"%d" % c.value, u"%d" % round_units(c.gap), u"%d" % c.fix, where, compared),
                         True, True, tip, parents.get(c.variant or c.left), self.pair_icon((c.left, c.right), c.value, index))
        self.resize(tab)
        self.update_previews()  # (refilled: nothing selected now, the pictures' room says what it is for)
        self.checked_now(tab, "collisions")
        tight = sum(1 for pair, _ in tight_pairs(kerning, self.only) if not common_only or common(*pair))
        tab.status.setText(collision_status(len(found), tight, minimum, relative, common_only, self.limited(), self.ak.b))

    def write_fixes(self):
        if self.busy or not self.same_font():
            return
        tab = self.collisions
        chosen = self.checked(tab)
        if not chosen:
            return
        if not self.begin_writing():
            return
        kerning = self.kerning()
        written, stale, error = 0, 0, None
        # Under the window's top-row progress, never stoppable: one step of FontLab's History, never half written
        self.busy = True
        self.ak.busy_start(self, WRITE_STEP, stoppable=False)
        try:
            try:
                for done, c in enumerate(chosen):
                    if done % PROGRESS_EVERY == 0:
                        self.progress(WRITE_STEP, done, len(chosen), stoppable=False)
                    if kerning.current(c.left, c.right) != c.value:
                        stale += 1  # changed since the check
                        continue
                    kerning.write(((c.left, False), (c.right, False)), c.fix, False)
                    written += 1
            except Exception as exc:
                error = exc
            status = self.after_writing()
            asked_to_stop = self.ak.busy_stopping(self)  # (Esc, Close, a tool, an arrow, during the write)
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if asked_to_stop:  # (what was clicked is done now: not checked again under it)
            self.stopped(tab, u"Checking again")
            self.seen_history = self.ak.history_mark(self.package)
        else:
            self.check_collisions()
        b = self.ak.b
        self.log.add(u"Wrote %s of %s own%s." % (
            b(counted(written, u"pair")), u"its" if written == 1 else u"their",
            status.undo(u" (<i>Edit &gt; Undo</i> takes %s back)" % (u"it" if written == 1 else u"them"))),
            "done" if written else "info")
        status.report(self.log)
        if stale:
            self.log.add(u"%s had changed since the check and %s left as %s." % (
                b(counted(stale, u"pair")), u"was" if stale == 1 else u"were", u"it was" if stale == 1 else u"they were"),
                "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")

    def check_cleanup(self):
        if self.busy or not self.read_font():
            return
        tab = self.cleanup
        tab.tree.clear()
        tab.findings = []
        self.ak.enable(tab.action, False)
        self.busy = True
        self.ak.busy_start(self, CLEANUP_STEP)  # (the window's top row, stoppable)
        try:
            kerning = self.kerning()
            found = limited_cleanup(kerning, find_cleanup(kerning, self.glyph_exists, self.tiny.value,
                                                          lambda done, total: self.progress(CLEANUP_STEP, done, total)),
                                    self.only)
        except self.ak.Stopped:
            found = None
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if found is None:
            self.stopped(tab)
            return
        tab.findings = found
        kinds = dict(CLEANUP_KINDS)
        for index, c in enumerate(found):
            first = kerning.first_pair(c.entry) if index < self.ak.GLYPH_ICON_ROWS else None  # (not every class x class pair)
            self.add_row(tab, index, (kerning.describe(c.entry), u"%d" % c.value, u"%s: %s" % (kinds[c.kind], c.reason)),
                         True, c.checked, icon=self.pair_icon(first, c.value, index))
        self.resize(tab)
        self.update_previews()  # (refilled: nothing selected now, the pictures' room says what it is for)
        self.checked_now(tab, "cleanup")
        counts = {}
        for c in found:
            counts[c.kind] = counts.get(c.kind, 0) + 1
        entries = sum(1 for entry in kerning.entries if involves(kerning, entry, self.only))
        tab.status.setText(cleanup_status(len(found), entries, counts, self.limited(), self.ak.b))

    def glyph_exists(self, name):
        glyph = self.package.findName(name)
        return glyph is not None and not glyph.isNull

    def remove_entries(self):
        if self.busy or not self.same_font():
            return
        tab = self.cleanup
        chosen = self.checked(tab)
        if not chosen:
            return
        if not self.begin_writing():
            return
        kerning = self.kerning()
        removed, stale, error = 0, 0, None
        # Under the window's top-row progress, never stoppable: one step of FontLab's History, never half written
        self.busy = True
        self.ak.busy_start(self, REMOVE_STEP, stoppable=False)
        try:
            try:
                chosen, stale = still_removable(kerning, chosen, self.glyph_exists, self.tiny.value,
                                                lambda done, total: self.progress(CLEANUP_STEP, done, total, False))
                for done, c in enumerate(chosen):
                    if done % PROGRESS_EVERY == 0:
                        self.progress(REMOVE_STEP, done, len(chosen), stoppable=False)
                    kerning.write(c.entry, 0, True)
                    removed += 1
            except Exception as exc:
                error = exc
            status = self.after_writing()
            asked_to_stop = self.ak.busy_stopping(self)  # (Esc, Close, a tool, an arrow, during the write)
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if asked_to_stop:  # (what was clicked is done now: not checked again under it)
            self.stopped(tab, u"Checking again")
            self.seen_history = self.ak.history_mark(self.package)
        else:
            self.check_cleanup()
        b = self.ak.b
        self.log.add(u"Removed %s%s." % (
            b(counted(removed, u"entry", u"entries")),
            status.undo(u" (<i>Edit &gt; Undo</i> puts %s back)" % (u"it" if removed == 1 else u"them"))),
            "done" if removed else "info")
        status.report(self.log)
        if stale:
            self.log.add(u"%s had changed since the check and %s left as %s." % (
                b(counted(stale, u"entry", u"entries")), u"was" if stale == 1 else u"were", u"it was" if stale == 1 else u"they were"),
                "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")

    def check_masters(self):
        if self.busy or not self.read_font():
            return
        tab = self.masters
        tab.tree.clear()
        masters = list(self.package.masters)
        self.checked_now(tab, "masters")
        if len(masters) < 2:
            tab.findings = []
            tab.status.setText(u"This font has one master: nothing to compare.")
            return
        self.busy = True
        self.ak.busy_start(self, COMPARE_STEP)  # (the window's top row, stoppable)
        try:
            kernings = []
            for done, master in enumerate(masters):
                self.progress(COMPARE_STEP, done, len(masters) + 1)
                kernings.append((master, self.kerning(master)))
            self.progress(COMPARE_STEP, len(masters), len(masters) + 1)
            found = compare_masters(kernings, only=self.only)
        except self.ak.Stopped:
            found = None
        finally:
            self.ak.busy_end(self)
            self.busy = False
        if found is None:
            self.stopped(tab, u"The comparison")
            return
        tab.findings = found
        for index, d in enumerate(found):
            self.add_row(tab, index, (d.subject, u"; ".join(u"%s %s" % pair for pair in d.values), d.reason), False, False)
        self.resize(tab)
        self.update_previews()  # (refilled: nothing selected now, the pictures' room says what it is for)
        tab.status.setText(masters_status(len(found), len(masters), self.only is not None, self.limited(), self.ak.b))

    # -- looking at a pair ----------------------------------------------

    def checked_now(self, tab, key):
        """A list just checked: its first checks kept (Restore suggestions), the History seen."""
        self.stale.discard(key)
        self.first_checks_of(tab)
        self.seen_history = self.ak.history_mark(self.package)
        self.update_buttons()

    def bottom_row(self, QtGui):
        """The window's bottom row, as every tool's (owner's report 152: they sat under each list, above
        the previews and the log): the list's own Tick all, Tick none, and Restore suggestions, then
        Show in Glyph window; at the right, the list's action, then Close. Every list's buttons are in
        it, those of the list shown visible (show_tab_buttons)."""
        row = QtGui.QHBoxLayout()
        tabs = (self.collisions, self.cleanup, self.masters)
        for tab in tabs:
            if tab.action is not None:
                for button in (tab.check_all, tab.check_none, tab.restore):
                    row.addWidget(button)
        row.addWidget(self.glyph_window_button)
        row.addStretch(1)
        for tab in tabs:
            if tab.action is not None:
                row.addWidget(tab.action)
        row.addWidget(self.close_button)
        self.show_tab_buttons(0)
        return row

    def show_tab_buttons(self, index):
        """The bottom row's buttons of the list shown (by its tab's index), the others' hidden first (the row
        never holds two lists' buttons at once: owner's image 284, the window grew to fit both)."""
        groups = [[tab.check_all, tab.check_none, tab.restore, tab.action] if tab.action is not None else []
                  for tab in (self.collisions, self.cleanup, self.masters)]
        show_only = getattr(getattr(self, "ak", None), "show_only", None)
        if show_only is not None:
            show_only(groups, index)
            return
        for number in sorted(range(len(groups)), key=lambda n: n == index):
            for button in groups[number]:
                button.setVisible(number == index)

    def show_tab_status(self, index):
        """The header's status line: the list's shown (by its tab's index), as its last check left it."""
        line = getattr(self, "status_line", None)
        status = getattr((self.collisions, self.cleanup, self.masters)[index], "status", None)
        if line is not None and status is not None:
            line.setText(getattr(status, "text", u""))

    def level_settings(self):
        """The three lists' settings rows as tall as one another (level_rows: a table never moves as its tab
        is shown), measured again at each switch, after the window's styles and a dark mode switch."""
        level_rows([getattr(tab, "settings_box", None) for tab in
                    (getattr(self, "collisions", None), getattr(self, "cleanup", None), getattr(self, "masters", None))
                    if getattr(tab, "settings_box", None) is not None])

    def switch_page(self, index):
        self.level_settings()  # (before the page shows: owner's images 285 and 286)
        self.pages.setCurrentIndex(index)
        self.show_tab_buttons(index)
        self.show_tab_status(index)
        self.update_previews()
        key = TABS[index]
        if key in self.stale and self.package is not None:
            _qt()[0].QTimer.singleShot(0, lambda: self.check(key))  # checked as it is first shown

    def selected_finding(self):
        """The finding of the selected row (a group's first one), or None."""
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
        return tab.findings[int(item.data(0, QtCore.Qt.UserRole))]

    def update_previews(self):
        """The selected pair drawn: now and with its fix, beside its base pair (Collisions); with and
        without its entry (Cleanup)."""
        finding = self.selected_finding() if self.package is not None else None
        shown = []
        try:
            if isinstance(finding, Collision):
                shown = [(finding.pair(), finding.value, u"Now: %d" % finding.value),
                         (finding.pair(), finding.fix, u"Adjusted: %d" % finding.fix)]
                if finding.reference is not None:
                    shown.append((finding.reference, finding.value, u"Base pair: %d" % finding.value))
            elif isinstance(finding, Cleanup):
                kerning = self.kerning()
                first = kerning.first_pair(finding.entry)
                if first is not None:
                    now = kerning.current(*first)
                    without = value_without(kerning, finding.entry, *first)
                    shown = [(first, now, u"Now: %d" % now), (first, without, u"Adjusted: %d" % without)]
        except Exception:
            shown = []
        self.adjust_width = None
        captions = getattr(self, "preview_captions", [])
        for index, label in enumerate(self.previews):
            if index < len(shown):
                pair, value, caption = shown[index]
                adjustable = index == 1 and isinstance(finding, Collision)
                picture = self.pair_picture(pair[0], pair[1], value, room=adjustable)
                if adjustable:
                    self.adjust_width = picture.width()  # kept while dragging: the left glyph stays put
                label.setPixmap(picture)
            else:
                caption = u""
                label.clear()
            if index < len(captions):  # (over the picture, quiet: the shared preview_caption)
                captions[index].setText(caption)
        if not shown:  # (the room the pictures take, said what it is for: it read as an empty band, live)
            self.previews[1].setText(self.preview_hint())
        self.update_buttons_soon()

    def preview_hint(self):
        """What the pictures' room shows while no pair is selected: nothing, as every other tool's previews
        (owner's image 337: "Select a pair to see it here..." was this window's alone)."""
        return u""

    # -- the Adjusted preview, dragged ---------------------------------------

    def adjustable(self):
        """The selected collision, while the Collisions list is shown: its fix can be adjusted."""
        finding = self.selected_finding() if self.package is not None else None
        return finding if isinstance(finding, Collision) and self.tabs.currentIndex == 0 else None

    def adjusted_value(self):
        """The selected collision's fix, which the Adjusted preview adjusts (None: nothing to adjust)."""
        finding = self.adjustable()
        return finding.fix if finding is not None else None

    def units_scale(self):
        """Preview pixels per font unit."""
        return float(self.ak.PAIR_PREVIEW_EM) / float(self.package.upm)

    def set_fix(self, finding, value):
        """A collision's fix set by hand: the Adjusted preview drawn again, its row's Fix shown and checked."""
        QtCore, QtGui = _qt()
        if finding is None or value == finding.fix:
            return
        finding.fix = value
        self.previews[1].setPixmap(self.pair_picture(finding.left, finding.right, value, width=self.adjust_width))
        self.preview_captions[1].setText(u"Adjusted: %d" % value)
        tab = self.collisions
        for item in self.rows(tab):
            if tab.findings[int(item.data(0, QtCore.Qt.UserRole))] is finding:
                item.setText(COLLISION_COLUMNS.index(u"Fix"), u"%d" % value)
                item.setCheckState(0, QtCore.Qt.Checked)
                break

    def pair_picture(self, left, right, value, room=False, width=None):
        """A glyph pair at a kerning value in the dialog's text color (see Auto Kerning's pair_pixmap); its
        caption is the label over it (preview_captions)."""
        QtCore, QtGui = _qt()
        left, right = screen_pair(self.ak, self.package, left, right, self.chars)  # (a kerning key, drawn as on screen)
        return self.ak.pair_pixmap(self.package, self.master, left, right, value, u"",
                                   self.dialog.palette.color(QtGui.QPalette.WindowText), self.dialog.font,
                                   room, width)

    def row_names(self, tab, item):
        """The glyphs of a row (none for a group's heading, a class, or an entry's class sides): their flags
        shown."""
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        if not 0 <= index < len(tab.findings):
            return []
        finding = tab.findings[index]
        if hasattr(finding, "pair"):
            return list(finding.pair() or [])
        entry = getattr(finding, "entry", None) or ()
        if not isinstance(entry, tuple):
            return []  # a class's name (Masters' class rows)
        return [u"%s" % name for name, is_class in entry if not is_class]  # ((name, is class), (name, is class))

    def selected_pair(self):
        """The glyph pair of the selected row (an entry's first pair), or None."""
        finding = self.selected_finding()
        if isinstance(finding, Collision):
            return finding.pair()
        if isinstance(finding, Cleanup):
            return self.kerning().first_pair(finding.entry)
        return None

    def show_in_glyph_window(self):
        if self.package is None:
            return
        pair = self.selected_pair()
        if pair is None:
            return
        contexts = self.ak.proof_contexts(self.package, list(pair))
        error = self.ak.show_in_glyph_window(self.fontlab, self.ak.proof_text(pair[0], pair[1], contexts))
        if error:
            self.log.add(u"FontLab did not open the pair: %s" % self.ak.html(error), "error")

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        if self.package is not None:
            QtCore.QTimer.singleShot(50, lambda: self.check(TABS[self.tabs.currentIndex]))  # checked as it opens


def main(glyphs=None, reason=None, **options):
    """Kerning Check on the current font. Another script that changed glyphs (built them, moved their
    marks, spaced them) passes their names (or the glyphs) as glyphs, and what it did as reason
    ("Glyph Compose built": "Pairs with the 12 glyphs Glyph Compose built: ..."): Collisions, Cleanup, and
    Masters then list only the pairs and entries with those glyphs, until Show all is clicked."""
    if reason is None:  # (a caller naming it otherwise: why=, source=, ...)
        reason = next((value for value in options.values() if isinstance(value, (type(u""), str))), None)
    try:  # this font's window shows it already: brought forward as it is
        if glyphs is None and load_auto_kerning().raise_open("Kerning Check"):
            return
    except Exception:
        pass
    try:
        dialog = KerningCheckDialog(glyphs, reason)
    except Exception as exc:
        print("FreeLab Kerning Check: %s" % exc)
        return
    sys._freelab_kerning_check = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("Kerning Check", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_kerning_check":
    main()
