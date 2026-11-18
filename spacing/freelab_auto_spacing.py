#FLM: Auto Spacing
# -*- coding: utf-8 -*-
"""FreeLab auto spacing, from FontLab's Scripts menu.

Suggests sidebearings for the drawn letters of the current master (Latin, Armenian, Georgian, and
proportional kana), so that each sits beside the font's straight references (H for capitals, n for
lowercase; their own in the other scripts) as the references sit beside each other, measured by Auto
Kerning's two methods (halfkern's and contour distance). Shows each glyph between
its references as it is and as suggested, and changes only the glyphs you leave ticked. Glyphs
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
# The other scripts' straight references by kind (Auto Kerning's SCRIPT_CONTROLS), and the round
# reference each straight one is proofed with
SCRIPT_SPACING_REFERENCES = {"armenian": {"upper": u"\N{ARMENIAN CAPITAL LETTER VO}", "lower": u"\N{ARMENIAN SMALL LETTER VO}"},
                             "georgian": {"upper": u"Ი", "lower": u"\N{GEORGIAN LETTER IN}"},
                             "kana": {"kana": u"\N{KATAKANA LETTER RO}"},
                             "cyrillic": {"upper": u"\N{CYRILLIC CAPITAL LETTER EN}", "lower": u"\N{CYRILLIC SMALL LETTER EN}"},
                             "greek": {"upper": u"\N{GREEK CAPITAL LETTER ETA}", "lower": u"\N{GREEK SMALL LETTER ETA}"},
                             "devanagari": {"lower": u"\N{DEVANAGARI LETTER NA}"},
                             "hebrew": {"lower": u"\N{HEBREW LETTER HE}"},
                             "thaana": {"lower": u"\N{THAANA LETTER NOONU}"}}
ROUND_REFERENCES = {u"H": u"O", u"n": u"o", u"0": u"8", u"\N{ARMENIAN CAPITAL LETTER VO}": u"\N{ARMENIAN CAPITAL LETTER OH}",
                    u"\N{ARMENIAN SMALL LETTER VO}": u"\N{ARMENIAN SMALL LETTER OH}",
                    u"Ი": u"Ო",
                    u"\N{GEORGIAN LETTER IN}": u"\N{GEORGIAN LETTER ON}", u"\N{KATAKANA LETTER RO}": u"\N{HIRAGANA LETTER NO}",
                    u"\N{CYRILLIC CAPITAL LETTER EN}": u"\N{CYRILLIC CAPITAL LETTER O}",
                    u"\N{CYRILLIC SMALL LETTER EN}": u"\N{CYRILLIC SMALL LETTER O}",
                    u"\N{GREEK CAPITAL LETTER ETA}": u"\N{GREEK CAPITAL LETTER OMICRON}",
                    u"\N{GREEK SMALL LETTER ETA}": u"\N{GREEK SMALL LETTER OMICRON}",
                    u"\N{DEVANAGARI LETTER NA}": u"\N{DEVANAGARI LETTER TTHA}",
                    u"\N{HEBREW LETTER HE}": u"\N{HEBREW LETTER SAMEKH}",
                    u"\N{THAANA LETTER NOONU}": u"\N{THAANA LETTER MEEMU}"}
FIXED = u"HOlno08"  # the references and tuning glyphs of the methods: never changed (the other scripts' too, below)
TOLERANCE_UNITS = 6  # a side whose suggestion is closer than this to its sidebearing is left out
GROUPS = (("letters", "Letters"), ("figures", "Letters and figures"), ("all", "Letters, figures, and punctuation"),
          ("everything", "Everything"))  # (other scripts and symbols too, by case)
DEFAULT_GROUP = "everything"  # the dropdown's choice as the window opens (owner's report 143)
PREVIEW_SIZE = 80  # pixels per em in the previews
PREVIEW_HEIGHT, PREVIEW_BASELINE = 1.35, 1.05  # a preview's height and its baseline's depth, in ems (its caption over it)
APPLY_BUTTON = u"Space ticked glyphs"  # (Tick, not Check, for check boxes: owner's image 261)
SETTLE_PASSES = 6  # an analysis measures each change again, with it made, at most this many times
SETTLE_SHARE = 0.002  # a side has settled when measuring it again asks less than this share of the em more
KERNING_BUTTON = u"Check kerning of these glyphs\N{HORIZONTAL ELLIPSIS}"  # Kerning Check on the glyphs just spaced
APPLY_PASSES = 3  # Space ticked glyphs writes, measures again, and writes what is still off, at most this many times
SIDE_ALPHA = 110  # the references beside the glyph, dimmed
# The long steps, named in the window's top row while they run (ak.busy_start), and the share of the bar
# measuring takes before the list is filled; within it, how far each part of the measuring goes
MEASURE_STEP, DRAW_STEP, SETTLE_STEP = u"Measuring", u"Drawing the glyphs", u"Measuring with the changes made"
COMPOSITES_STEP, LIST_STEP, SPACE_STEP = u"Finding the glyphs built from components", u"Listing", u"Spacing"
FOLLOW_STEP, UPDATE_STEP = u"Moving the glyphs built on them", u"Updating the font"
MEASURE_SHARE = 0.9
MEASURE_PARTS = ((DRAW_STEP, 0.0, 0.15), (MEASURE_STEP, 0.15, 0.5), (SETTLE_STEP, 0.5, 0.9), (COMPOSITES_STEP, 0.9, 1.0))
PUMP_EVERY = 50  # glyphs read between two calls to the progress (it lets events through at most every 0.1 s)


def stopped_text(what, measured=False):
    """The status line once the user stopped the work (what: "Measuring", "Listing")."""
    return u"%s was stopped: nothing is listed. %s" % (
        what, u"Change the tolerance, or click <i>Analyze</i>, to list the glyphs." if measured
        else u"Click <i>Analyze</i> to measure the glyphs.")


FAILED_TEXT = u"Could not space this font: the log says why."  # the status line under the font's when it fails


def spacing_status(listed, drawn, tolerance, passes=1, bold=lambda text: u"%s" % text, italic=lambda text: u"%s" % text):
    """The status line under the font's, once the glyphs are measured: how many of the drawn glyphs are
    listed (right at 0, 1, and 2), and how many passes the measuring took where more than one."""
    off = u"a side %s or more from the suggestion" % bold(counted(tolerance, u"unit"))
    if not drawn:
        return u"No drawn glyph of this choice to space."
    if drawn == 1:
        text = u"The only drawn glyph %s %s." % (u"has" if listed else u"does not have", off)
    elif not listed:
        text = u"None of the %s has %s." % (bold(counted(drawn, u"drawn glyph")), off)
    else:  # (the count bold with its noun, "of" included: "1,200 of 13,932 drawn glyphs", round 3's rule)
        text = u"%s %s %s." % (bold(u"%s of %s" % (u"{:,}".format(listed), counted(drawn, u"drawn glyph"))),
                               u"has" if listed == 1 else u"have", off)
    if listed:
        text += u" Nothing changes until you click %s." % italic(APPLY_BUTTON)
    if passes > 1:
        text += (u" Each change was measured again with it made, until the changes settled (%s): halfkern "
                 u"closes half of a tightening at a time, so one measure leaves part of it."
                 % bold(counted(passes, u"pass", u"passes")))
    return text


class CannotSpace(ValueError):
    """The font itself stops the analysis (its references missing, or set so that nothing can be measured
    from them): Analyze would fail the same way until the font changes (owner's image 253: its buttons
    grayed meanwhile)."""


def references_failed_text(tuning, reason):
    """The log's words when the font's l, n, and o (tuning: their characters) give nothing to measure
    by (owner's image 218: "No halo makes ll, nn, oo agree", which said nothing to the user): what Auto
    Spacing tried, why it failed for this font, and what to do (Analyze is grayed meanwhile: the window
    measures again by itself as the font changes). reason: the measuring's own message."""
    letters = list(tuning)
    named = u", ".join(letters[:-1]) + (u", and " if len(letters) > 2 else u" and ") + letters[-1] if len(letters) > 1 \
        else u"".join(letters)
    pairs = u", ".join(ch + ch for ch in letters)
    if u"no solid ink" in (u"%s" % reason):
        why = (u"one of them has no stroke thick enough to measure from (a hairline or an empty glyph), so nothing "
               u"could be spaced")
    else:
        why = (u"these pairs sit too differently apart in this font (one far tighter or looser than the others), so no "
               u"one measure fits all of them, and nothing could be spaced")
    return (u"Auto Spacing measures every glyph against %s, each set beside itself (%s): %s. Space %s by eye first "
            u"(their spacing sets every other glyph's); this window measures the font again as it changes." % (
                named, pairs, why, named))


def measure_part(step, part):
    """Where a part of the measuring (step: one of MEASURE_PARTS', part 0 to 1 of it) lies in the whole."""
    for name, start, end in MEASURE_PARTS:
        if name == step:
            return start + (end - start) * min(max(float(part), 0.0), 1.0)
    return None


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


def default_group():
    """The dropdown's index as the window opens: DEFAULT_GROUP's."""
    return [key for key, _ in GROUPS].index(DEFAULT_GROUP)


def counted(number, one, many=None):
    """"1 pair", "2 pairs", "13,932 glyphs": a count (its thousands set apart) with its noun in the right
    number."""
    return u"%s %s" % (u"{:,}".format(int(number)), one if number == 1 else (many or one + u"s"))


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


def reference_for(kind_char, category, script_of=None):
    """A character's straight reference, by the kind of its base letter: H, n, or 0; n for
    punctuation (set among lowercase most). With script_of, a letter of another script Auto Kerning
    knows takes its script's own: Armenian vo, Georgian in, kana RO, Cyrillic en, Greek eta,
    Devanagari na, Hebrew he, and Thaana noonu."""
    script = script_of(kind_char) if script_of is not None else None
    if script in SCRIPT_SPACING_REFERENCES:
        own = SCRIPT_SPACING_REFERENCES[script]
        return own.get(category(kind_char)) or list(own.values())[0]
    return SPACING_REFERENCES.get(category(kind_char), SPACING_REFERENCES["lower"])


def fixed_characters(ak):
    """The references and tuning letters of every script: never changed."""
    found = set(FIXED)
    for script, _ in ak.SCRIPTS:
        found.update(ak.SCRIPT_TUNING[script])
        for chars in ak.SCRIPT_REFERENCES[script].values():
            found.update(chars)
    return found


def suggest_spacing(glyphs, measure, kind_of, category, script_of=None, progress=None):
    """Each Spacing's suggested changes: its right side as the pair (glyph, reference) asks (the
    kerning that pair would want is what its right sidebearing lacks), its left side as (reference,
    glyph) asks. measure(left char, right char) gives that kerning in font units, or None;
    kind_of(char) the character whose kind sets its references (its base letter); script_of, the
    script of a letter, for the other scripts' own references (see reference_for). progress(part),
    where given, is told how far it is (0 to 1) before each glyph (it may raise to stop)."""
    for number, g in enumerate(glyphs):
        if progress is not None:
            progress(number / float(len(glyphs)))
        reference = reference_for(kind_of(g.char), category, script_of)
        g.right_change = measure(g.char, reference)
        g.left_change = measure(reference, g.char)
    return glyphs


def settle_spacing(glyphs, measure_at, kind_of, category, script_of=None, settle=2, passes=SETTLE_PASSES,
                   progress=None):
    """Each Spacing's changes (from suggest_spacing) measured again with them made, until they settle;
    the passes measured (1 when nothing needed another).

    One measure does not land where the methods want a side: halfkern closes half of a tightening at
    a time (Auto Kerning's DEFAULT_FACTORS), and the measuring is not linear (bands, pixels), so a
    glyph spaced once asks for more when measured again; spacing the checked glyphs took several
    clicks, each listing fewer glyphs. Here each pass measures the sides still moving with the
    changes so far made: measure_at(moved) gives a measure as suggest_spacing's, with the glyphs set
    as moved says ({glyph name: (left change, right change)}). A side settles when the next step is
    under settle units, or when it overshoots (its sign flips: half of it is taken, the target lying
    between), or when it can no longer be measured (it keeps what it had). progress(part), where
    given, is told how far the passes are (0 to 1, as if each ran) before each glyph measured again
    (it may raise to stop)."""
    moving = {}
    for g in glyphs:
        for side in ("left", "right"):
            change = getattr(g, side + "_change")
            if change is not None and abs(change) >= settle:
                moving[(g.name, side)] = change  # its last step
    done = 1
    while moving and done < passes:
        moved = dict((g.name, (g.left_change or 0, g.right_change or 0)) for g in glyphs
                     if g.left_change or g.right_change)
        if progress is not None:
            progress((done - 1) / float(passes - 1))
        measure = measure_at(moved)
        done += 1
        still = {}
        for number, g in enumerate(glyphs):
            sides = [side for side in ("left", "right") if (g.name, side) in moving]
            if not sides:
                continue
            if progress is not None:
                progress((done - 2 + number / float(len(glyphs))) / float(passes - 1))
            reference = reference_for(kind_of(g.char), category, script_of)
            for side in sides:
                step = measure(reference, g.char) if side == "left" else measure(g.char, reference)
                if step is None:
                    continue
                last = moving[(g.name, side)]
                settled = abs(step) < settle
                if step * last < 0:
                    step = int(step / 2.0)  # overshot: the target lies between (toward zero)
                    settled = True
                setattr(g, side + "_change", getattr(g, side + "_change") + step)
                if not settled:
                    still[(g.name, side)] = step
        moving = still
    return done


def apply_note(passes, again, tolerance, references_first=0, bold=lambda text: u"%s" % text):
    """What a click on Space ticked glyphs took, for the log: passes writes, again glyphs spaced again
    after the first (still a side tolerance units or more off when measured again), and how many glyphs
    were measured again against references spaced first. Empty when one pass did it all. bold: the log's
    (ak.b), each count bold with its noun (round 3's rule); its text holds no markup of its own."""
    notes = []
    if references_first:
        notes.append(u"The references were spaced first, and the other %s measured against them again: their "
                     u"changes differ from the list's." % bold(counted(references_first, u"glyph")))
    if passes > 1:
        notes.append(u"It took %s: measured again after spacing, %s still had a side %s or more off, and %s "
                     u"spaced again (the measuring's pixels round each change a little)." % (
                         bold(counted(passes, u"pass", u"passes")), bold(counted(again, u"glyph")),
                         bold(counted(tolerance, u"unit")), u"was" if again == 1 else u"were"))
    return u" ".join(notes)


REFERENCE_MODEL_FILE = "reference_model.json"
UNSPACED_SHARE = 0.005  # a reference side closer to its ink than this share of the em counts as unspaced
# Each script's straight references (looked at for unspaced sides) and all its references (spaced
# from the corpus when a straight one looks unspaced): Latin's, Armenian's, Georgian's. Latin's l with
# them: every glyph is measured against l, n, and o (ll, nn, oo), and n and o spaced without l left ll
# far from them, so nothing could be spaced after (owner's image 335).
REFERENCE_GROUPS = ((u"Hn", u"HOlno0"),
                    (u"Ոո",
                     u"ՈՕո"
                     u"օ"),
                    (u"Იი", u"ᲘᲝიო"))
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


def references_to_space(sides, upm, groups=REFERENCE_GROUPS):
    """The references to space from the corpus, by script: all of a script's (those in sides, {char:
    (name, left, right, width)}) where one of its straight references looks unspaced."""
    found = []
    for straight, every in groups:
        if any(unspaced(sides[ch][1], sides[ch][2], upm) for ch in straight if ch in sides):
            found.extend(ch for ch in every if ch in sides)
    return found


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


def unspaced_line(references, families, bold=lambda text: u"%s" % text, italic=lambda text: u"%s" % text):
    """The log's warning when the font's references look unspaced: they come first, unticked, spaced from
    the corpus; its families counted in bold with their noun ("**412 open-licensed families**", round 3's
    rule: the number alone was bold)."""
    families = int(families or 0)
    return (u"This font's references look unspaced (a side at its ink, or one side three times the other): %s come "
            u"first, unticked, spaced as %s %s theirs. If the font is not spaced yet, tick them, space them, then "
            u"click %s: the other glyphs are measured against them. A font tight on purpose leaves them unticked." % (
                bold(u", ".join(references)), bold(counted(families, u"open-licensed family", u"open-licensed families")),
                u"spaces" if families == 1 else u"space", italic(u"Analyze")))


def composites_text(following, left_out, bold=lambda text: u"%s" % text):
    """The note under the list: how many glyphs built from components follow the listed glyphs, and
    how many built on two of them are left as they are; empty (the note hidden) when neither: "0 glyphs
    built from components follow the listed glyphs" said nothing worth a line (owner's image 188).
    bold: the status line's (ak.b): the count bold with its noun, a number with no noun bold alone
    (round 3's rule: "**3 glyphs** built from components follow ...; **2** built on two of them")."""
    if not following and not left_out:
        return u""
    if following:
        text = u"%s built from components %s the listed glyphs" % (
            bold(counted(following, u"glyph")), u"follows" if following == 1 else u"follow")
    else:
        text = u"No glyph built from components follows the listed glyphs"
    if left_out:
        text += u"; %s built on two of them %s left as %s" % (bold(u"{:,}".format(left_out)),
                                                             u"is" if left_out == 1 else u"are",
                                                             u"it is" if left_out == 1 else u"they are")
    return text + u"."


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
Suggests sidebearings for the drawn glyphs of this master, so that each sits beside its
straight reference (H for capitals, n for lowercase, 0 for figures) as the references sit beside each
other. Changes only the glyphs you leave ticked.<br><br>
<b>Scripts</b>: Latin; Armenian, against its own vo (capital and small) and oh; Georgian, against
its own in and on (Mkhedruli, and Mtavruli where the font has them); kana where they are
proportional already, against RO, NO, and I (full-width kana are set proportionally by palt: <i>CJK
Spacing</i>). A script whose references the font lacks is spaced by case against H and n.<br><br>
<b>How</b>: <i>Auto Kerning</i>'s two methods measure the pair of the glyph and its reference on each side
(T beside H, H beside T); the kerning they would want there, averaged, is what that sidebearing
lacks. A side measured within the tolerance is left as it is.<br>
<b>The references are yours</b>: H, O, l, n, o, 0, and 8 set the spacing (as in Walter Tracy's
method: space H and n, then O and o, by eye) and are never changed, nor are the other scripts'. Glyphs built from components
are not spaced: they follow the glyphs they are built on, their accents kept over them.<br>
<b>One click</b>: each suggestion is measured again with its change made, until it settles (halfkern
closes half of a tightening at a time, so one measure leaves part of it), and the list shows where
each glyph ends up. If you tick references, they are spaced first and the other glyphs measured
against them again. After writing, the glyphs are measured again, and any still off by the tolerance
are spaced again in the same step; the log says how many passes it took.<br>
<b>When it cannot space a font</b>: every glyph is measured against l, n, and o; a font whose l, n,
and o sit too differently apart (or that lacks them) gives nothing to measure by. The log says why,
<i>Analyze</i> stays grayed, and the window measures the font again as it changes.<br>
<b>After spacing</b>: the font's kerning was set for the old sidebearings. <i>Check kerning of these
glyphs</i> opens <i>Kerning Check</i> on the glyphs just spaced (collisions and cleanup for them alone);
run <i>Auto Kerning</i> again, with <i>Include existing kerned pairs</i>, to see which pairs now want
other values.<br>
<b>Preview</b>: the selected glyph between its references, as it is (left) and as suggested
(right). Click a reference beside it to open that pair in <i>Auto Kerning</i>; double-click a glyph's name
to open it in a <i>Glyph</i> window.<br>
<i>Restore suggestions</i> puts the ticks back as the list first came.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""


class AutoSpacingDialog(object):
    # As the other tools' lists: the glyph drawn from the font beside its character, its name, its code point
    COLUMNS = ("Glyph", "Name", "Unicode", "Left now", "Left change", "Right now", "Right change", "Width")
    NUMBERS = (3, 4, 5, 6, 7)  # the columns of numbers, right-aligned

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = load_auto_kerning()
        main = self.ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Spacing")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        layout = self.ak.window_layout(dialog)  # (its content scrolls on a small screen)
        # The header, as every window's: the font line and the status (one label, a line per sentence), the
        # note on the glyphs built from components (owner: no text under the controls), then the header's line
        self.status = self.ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.composites_note = self.ak.status_label()
        self.composites_note.setWordWrap(True)
        layout.addWidget(self.composites_note)
        layout.addWidget(self.ak.header_separator())
        self.log = self.ak.Log()
        # (the glyphs a line names drawn as the font draws them; clicked, one opens in a Glyph window:
        # spaced glyphs have left the list)
        self.log.follow(lambda: (self.fontlab, self.package, self.master))
        self.log.link_handler = self.log_link  # (a glyph clicked: opened between its references)
        self.seen_history, self.first_checks = None, {}
        # One row, left-aligned: "Show: [Everything]  List changes of at least [6 units].  [x] Glyphs built from
        # components follow ...  [Analyze]" (owner's images 254 and 262: the tick above the list, Analyze inline)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Show:"))
        self.group = QtGui.QComboBox()
        for _, label in GROUPS:
            self.group.addItem(label)
        self.group.setCurrentIndex(default_group())  # (Everything: owner's report 143; set before it is heard)
        self.group.setWhatsThis(u"Which glyphs to space. Figures are often tabular (one width for all): leave them "
                                u"out unless they are proportional. <i>Everything</i>: every glyph with a character (other "
                                u"scripts' letters by their case, symbols beside n).")
        row.addWidget(self.group)
        row.addWidget(QtGui.QLabel("List changes of at least"))
        self.tolerance = QtGui.QSpinBox()
        self.tolerance.setRange(1, 100)
        self.tolerance.setValue(TOLERANCE_UNITS)
        self.suffix_slot = self.ak.counted_suffix(self.tolerance, u"unit")  # ("1 unit", "2 units")
        self.tolerance.setWhatsThis(u"A side is changed only when the suggestion differs from it by at least this "
                                    u"much; a glyph is listed when one of its sides is.")
        row.addWidget(self.tolerance)
        self.ak.sentence_end(row)
        self.follow = QtGui.QCheckBox("Glyphs built from components follow the glyphs they are built on.")
        self.follow.setChecked(True)
        self.follow.setWhatsThis(u"\N{LATIN SMALL LETTER E WITH ACUTE} built from e and an acute keeps its acute "
                                 u"over the e and takes e's change of width. Without it, its e moves under the "
                                 u"acute (the e's outline moves) and its width stays. A glyph whose diacritics then "
                                 u"stick out further past its width (a horn on a tighter O) follows all the same, "
                                 u"and the log names it, to check its diacritics.")
        row.addWidget(self.follow)
        self.analyze_button = QtGui.QPushButton("Analyze")
        self.analyze_button.setWhatsThis(u"Measures the current master's glyphs again.")
        row.addWidget(self.analyze_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setWhatsThis(u"Each glyph's sidebearings now and the change suggested for each side (below 0: "
                               u"closer to its neighbors), and its width after. Ticked glyphs are changed. "
                               u"Double-click a glyph or its name to open it in a <i>Glyph</i> window.")
        self.tree.setIconSize(QtCore.QSize(*self.ak.glyph_icon_size()))
        self.tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        self.ak.table_layout(self.tree, stretch=1)  # (the names take the room the numbers leave)
        layout.addWidget(self.tree, 1)
        # The previews side by side, each under its caption (the shared preview_caption), a line between them
        previews = QtGui.QHBoxLayout()
        self.preview_now, self.preview_after = QtGui.QLabel(), QtGui.QLabel()
        self.preview_captions = []
        for number, (label, caption, tip) in enumerate(((self.preview_now, u"Now", u"The glyph as it is"),
                                                        (self.preview_after, u"Suggested", u"As suggested"))):
            if number:
                previews.addWidget(self.ak.separator(vertical=True))
            column = QtGui.QVBoxLayout()
            title = self.ak.preview_caption(caption)
            title.setAlignment(QtCore.Qt.AlignCenter)
            column.addWidget(title)
            self.preview_captions.append(title)
            label.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
            label.setToolTip(tip)
            label.setMinimumHeight(int(PREVIEW_SIZE * PREVIEW_HEIGHT))
            label.setAlignment(QtCore.Qt.AlignCenter)
            column.addWidget(label, 1)
            previews.addLayout(column, 1)
        self.neighbors = [self.ak.ClickRegions(label, self.open_pair, u"Click to open this pair in <i>Auto Kerning</i>.")
                          for label in (self.preview_now, self.preview_after)]
        layout.addLayout(previews)
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Tick all")
        self.none_button = QtGui.QPushButton("Tick none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts the ticks back as the list first came after the analysis.")
        self.glyph_window_button = QtGui.QPushButton("Show in Glyph window")
        self.kerning_button = QtGui.QPushButton(KERNING_BUTTON)
        self.kerning_button.setWhatsThis(u"Opens <i>Kerning Check</i> on the glyphs the last <i>%s</i> "
                                         u"changed (and those built on them that followed): their kerning was set for "
                                         u"the old spacing, and its collisions and cleanup are listed for them alone."
                                         % APPLY_BUTTON)
        self.spaced = []  # the glyphs the last spacing changed: their kerning is checked on request
        self.apply_button = QtGui.QPushButton(APPLY_BUTTON)
        self.apply_button.setWhatsThis(u"Changes the sidebearings of the ticked glyphs in the current master (their "
                                       u"outlines move, their widths change), and the glyphs built on them.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button, self.glyph_window_button,
                       self.kerning_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.analyze_button.connect("clicked()", self.run)
        self.group.connect("currentIndexChanged(int)", lambda index: self.run())
        self.tolerance.connect("valueChanged(int)", lambda value: self.refill())
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons_soon())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.apply_button.connect("clicked()", self.apply)
        self.kerning_button.connect("clicked()", self.check_kerning)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        self.tree.connect("itemSelectionChanged()", self.select)
        self.package = self.master = None
        self.settle_passes = 1
        self.spacings, self.listed, self.composites = [], [], {}
        self.busy = self.buttons_due = False
        self.reference_model = load_reference_model()
        self.flagging = self.ak.flag_menu(self.tree, self, lambda: [self.selected().name] if self.selected() else [],
                                          self.row_names)
        self.unspaced_references = []
        self.history_timer = self.ak.watch_history(self)
        self.ak.add_tools_button(dialog, "Auto Spacing", getattr(self, "log", None))  # (the other font tools, a click away)
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
        package = self.ak.window_font(self, workspace)  # this window's font
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def characters(self, pump=None):
        """The characters to space, by the dropdown's choice; pump(), where given, called every
        PUMP_EVERY glyphs of the font read (the progress: it may raise to stop)."""
        ak = self.ak
        group = GROUPS[self.group.currentIndex][0]
        letters = [ch for ch in ak.class_characters() if ch.isalpha()]
        # every other script Auto Kerning knows (kana only where proportional): its letters, as listed there
        # (Cyrillic, Greek, Devanagari, Hebrew, and Thaana were left out until 2026-11-14, live)
        others = getattr(ak, "SCRIPT_LETTERS", None) or {"armenian": ak.ARMENIAN_LETTERS, "georgian": ak.GEORGIAN_LETTERS,
                                                         "kana": ak.KANA_LETTERS}
        seen = set(letters)
        for script, _ in ak.SCRIPTS:
            if script != "latin" and script in others:
                letters += [ch for ch in others[script] if ch not in seen]
                seen.update(others[script])
        chosen = letters + (list(ak.FIGURES) if group in ("figures", "all") else [])
        if group == "all":
            marks = getattr(ak, "SCRIPT_PUNCTUATION", None) or {"armenian": ak.ARMENIAN_PUNCTUATION}
            chosen += list(ak.PUNCTUATION)
            for script, _ in ak.SCRIPTS:
                if script not in ("latin", "kana") and script in marks:
                    chosen += [ch for ch in marks[script] if ch not in chosen]
        if group == "everything" and self.package is not None:
            import unicodedata
            taken = set(chosen)  # (a list searched for each of a CJK font's thousands of glyphs took seconds)
            for number, fg in enumerate(self.package.fgPackage.glyphs):
                if pump is not None and number % PUMP_EVERY == 0:
                    pump()
                code = ak.main_code(fg)  # (an ideograph, not the Kangxi radical FontLab may give first)
                if not code or code > sys.maxunicode:
                    continue  # (past U+FFFF, FontLab's narrow Python has no single character for it)
                ch = ak.unichr_(code)
                if unicodedata.category(ch)[0] in "LNPS" and ch not in taken:
                    chosen.append(ch)  # each spaced against its case's reference (H, n, or 0; n for symbols)
                    taken.add(ch)
        return chosen

    def run(self):
        """The current master measured and listed, under the window's top-row progress (owner's image 178:
        "Measuring..." held the window until Windows called it Not Responding); stoppable, the list then
        left empty."""
        if self.busy:
            return
        self.busy = True
        self.tree.clear()
        self.spacings, self.listed = [], []
        self.ak.enable(self.apply_button, False)
        self.composites_note.setText(u"")  # (the last font's, until this one is measured)
        self.composites_note.setVisible(False)
        self.failed = False  # (measured anew: Analyze given back, until the font stops it again)
        started = False
        try:
            package = self.package = self.current_font()
            self.master = package.master if package is not None else None
            if package is None:
                self.status.setText(self.ak.no_font_line())
                return
            self.status.setText(self.font_line())  # (the step is named in the top row meanwhile)
            self.ak.busy_start(self, MEASURE_STEP)
            started = True
            self.spacings, self.composites = self.measure(
                package, self.master, progress=lambda what, part: self.ak.busy_progress(
                    self, what, None if part is None else part * MEASURE_SHARE))
            self.first_checks = dict((s.name, s.checked) for s in self.spacings)
            self.ak.busy_progress(self, LIST_STEP, MEASURE_SHARE)
            self.fill(lambda part: self.ak.busy_progress(self, None, MEASURE_SHARE + part * (1.0 - MEASURE_SHARE)))
        except self.ak.Stopped:
            self.stopped(u"Measuring")
            return
        except Exception as exc:
            # The font line kept, the reason in the log (owner's image 224); where the font itself stops the
            # analysis, Analyze and what feeds it grayed until the font changes (owner's image 253)
            message = u"%s" % exc
            self.failed = isinstance(exc, CannotSpace)
            self.status.setText(u"%s %s" % (self.font_line(), FAILED_TEXT))
            self.log.add(self.ak.html(message[:1].upper() + message[1:]), "error")
            return
        finally:
            if started:
                self.ak.busy_end(self)
            self.busy = False
            self.seen_history = self.ak.history_mark(self.package)
            self.update_buttons()  # (no font, or nothing measured: the settings grayed out)
        if self.unspaced_references:
            self.log.add(unspaced_line(self.unspaced_references, self.reference_model.get("families", 0), self.ak.b,
                                       self.ak.i), "warning")

    def measure(self, package, master, only=None, progress=None):
        """(spacings, composites) of the master: the drawn glyphs' suggestions, each measured again with
        its change made until it settles (settle_spacing), and the composites {name: (base glyph, other
        components' glyphs)}. only: glyph names; when given, only their suggestions (no reference rows,
        no composites). progress(step, part), where given, is told the step and how far the whole is (0
        to 1, or None to leave the bar), often enough to keep the window answering (it may raise
        ak.Stopped)."""
        ak = self.ak
        step = (lambda name, part: progress(name, measure_part(name, part))) if progress is not None else \
            (lambda name, part: None)
        step(DRAW_STEP, 0.0)
        em = ak.EM_PIXELS
        glyphs = ak.FontLabGlyphs(package, master, em)
        wanted = self.characters(lambda: step(DRAW_STEP, 0.0))
        wanted_set = set(wanted)  # (a list searched for each of a CJK font's thousands of glyphs: slow)
        fixed = fixed_characters(ak)
        every = ak.font_glyphs(package, sorted(fixed) + wanted)
        found = []
        for number, (ch, name) in enumerate(every):
            if number % PUMP_EVERY == 0:
                step(DRAW_STEP, number / float(len(every)))
            if glyphs.add(name):
                found.append((ch, name))
        names = dict(found)
        upm = glyphs.upm
        scripts = [script for script, _ in ak.SCRIPTS if all(ch in names for ch in ak.SCRIPT_TUNING[script])
                   and (script != "kana" or self.kana_proportional(package, master, names, upm))]
        if not scripts:  # (Latin's l, n, and o named: most fonts have them)
            raise CannotSpace(ak.missing_references(package, ak.TUNING, [ch for ch in ak.TUNING if ch not in names],
                                                    u"Auto Spacing", u"their spacing is what the others are measured by"))
        image_of = lambda ch: glyphs.image(names[ch])
        core = ak.Core()
        self.settle_passes = 1
        tools = {}
        for script in scripts:
            try:
                tools[script] = ak.make_bands(core, image_of, names, em, glyphs.pad, script)
            except ValueError as exc:
                if script == "latin":  # (said in plain words: owner's image 218)
                    raise CannotSpace(references_failed_text(ak.SCRIPT_TUNING["latin"], exc))
                # (no halo makes its tuning letters agree: its letters are spaced by case against H and n)
        scripts = [script for script in scripts if script in tools]
        reach = float(glyphs.pad)
        tighten, loosen = ak.DEFAULT_FACTORS["halfkern"]
        self.scripts = scripts
        kind_of = self.kind_of

        def measuring(images):
            """The kerning a pair of characters wants (font units), with the glyphs as images draws them."""
            def measure(left, right):
                if left not in names or right not in names:
                    return None
                kind_left, kind_right = kind_of(left), kind_of(right)
                if kind_left is None or kind_right is None or ak.pair_kinds(kind_left, kind_right) is None:
                    return None
                script = ak.script_of(kind_left if ak.category(kind_left) != "punctuation" else kind_right) or "latin"
                if script not in tools:
                    return None
                halo, contour = ak.measure_pair(tools[script], kind_left, kind_right, images.image(names[left]),
                                                images.image(names[right]), em, reach)
                values = []
                if halo is not None:
                    units = halo * upm / em
                    values.append(units * (tighten if units < 0 else loosen))
                if contour is not None:
                    values.append(contour * upm / em)
                return round_units(sum(values) / len(values)) if values else None
            return measure

        measure = measuring(glyphs)
        fixed_names = set(name for ch, name in found if ch in fixed)

        def measure_at(moved):
            """The measuring with glyphs moved ({name: (left change, right change)}): drawn again, their
            outlines shifted by the left change and their widths changed by both, as spacing does."""
            again = ak.FontLabGlyphs(package, master, em, dict((name, (left, left + right))
                                                               for name, (left, right) in moved.items()))
            for number, name in enumerate(sorted(fixed_names | set(moved))):
                if number % PUMP_EVERY == 0 and progress is not None:
                    progress(SETTLE_STEP, None)  # (the window answers; the bar stays where the pass is)
                again.add(name)
            again.top, again.bottom = glyphs.top, glyphs.bottom  # (the same height and baseline as the bands')
            return measuring(again)

        spacings, composites = [], {}
        seen = set()
        for number, (ch, name) in enumerate(found):
            if number % PUMP_EVERY == 0:
                step(MEASURE_STEP, 0.0)
            if name in seen or ch in fixed or kind_of(ch) is None:
                continue
            seen.add(name)
            layer = package.findName(name).getLayerByName(master)
            parts = [component_glyph(shape) for shape in layer.shapes]
            if parts and all(parts):
                composites[name] = (parts[0], parts[1:])  # built from components: follows them
                continue
            if ch not in wanted_set or (only is not None and name not in only):
                continue
            left, right, width = ink_sides(layer)
            spacings.append(Spacing(ch, name, ak.category(kind_of(ch)), left, right, width))
        suggest_spacing(spacings, measure, kind_of, ak.category, ak.script_of, lambda part: step(MEASURE_STEP, part))
        self.settle_passes = settle_spacing(spacings, measure_at, kind_of, ak.category, ak.script_of,
                                            max(1, round_units(SETTLE_SHARE * upm)),
                                            progress=lambda part: step(SETTLE_STEP, part))
        if only is not None:
            return spacings, {}
        self.unspaced_references = self.space_references(package, master, names, spacings)
        # every composite of the font, not only those of the characters measured (alternates, ligatures)
        every = list(package.fgPackage.glyphs)
        for number, fg in enumerate(every):
            if number % PUMP_EVERY == 0:
                step(COMPOSITES_STEP, number / float(len(every)))
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

    def kind_of(self, ch):
        """The character whose kind sets ch's references (Auto Kerning's kind_character), in a script
        this font is measured in; a letter of another script by its case (H or n), as before; None
        for a kana when the font's kana are not measured (full width: CJK Spacing's palt sets them)."""
        ak = self.ak
        kind = ak.kind_character(ch)
        script = ak.script_of(kind)
        if script is None or script in getattr(self, "scripts", ("latin",)):
            return kind
        if script == "kana":
            return None
        return u"H" if ak.category(ch) == "upper" else u"n"

    def kana_proportional(self, package, master, names, upm):
        """Whether the font's kana are proportional already (their widths their own): only then are
        they spaced here. Full-width kana are set proportionally by palt (CJK Spacing)."""
        ak = self.ak
        advances = {}
        for ch in ak.KANA_LETTERS:
            if ch in names:
                layer = package.findName(names[ch]).getLayerByName(master)
                if layer is not None:
                    advances[names[ch]] = layer.advanceWidth
        return ak.kana_setting(advances, upm, {}) == "proportional"

    def space_references(self, package, master, names, spacings):
        """Where the references (H and n) look unspaced, a row for each reference from the corpus's
        spacing, put first and unchecked: a font tight on purpose looks the same (its letters touch),
        so spacing them is the designer's choice. The references' characters, or []."""
        model = self.reference_model
        if not model:
            return []
        upm = float(package.upm)
        sides, heights = {}, {}
        for ch in (u"H", u"x", u"O", u"l", u"n", u"o", u"0") + tuple(ch for _, group in REFERENCE_GROUPS[1:] for ch in group):
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
            elif ord(ch) > 0x7F:
                heights[ch] = box.height()  # (the other scripts' straight references give their own heights)
        ak = self.ak
        found = []
        for ch in references_to_space(sides, upm):
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

    def fill(self, progress=None):
        """The list made from the spacings within the tolerance; progress(part), where given, every
        PUMP_EVERY rows (a CJK font's Everything lists thousands; it may raise ak.Stopped)."""
        QtCore, QtGui = _qt()
        self.harvest()
        self.tree.clear()
        tolerance = self.tolerance.value
        self.listed = [s for s in self.spacings if s.listed(tolerance)]
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        for index, s in enumerate(self.listed):
            if progress is not None and index % PUMP_EVERY == 0:
                progress(index / float(len(self.listed)))
            item = QtGui.QTreeWidgetItem(self.row_texts(s, tolerance))
            item.setData(0, QtCore.Qt.UserRole, index)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if s.checked else QtCore.Qt.Unchecked)
            item.setFont(0, bold)
            if self.package is not None and index < self.ak.GLYPH_ICON_ROWS:
                icon = self.ak.glyph_icon(self.package, self.master, [s.name], color)
                if icon is not None:
                    item.setIcon(0, icon)
            for column in self.NUMBERS:
                item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
            self.tree.addTopLevelItem(item)
        self.ak.fit_columns(self.tree, self.NUMBERS)
        self.update_buttons()
        if self.package is not None:
            changes = dict((s.name, s.changes(tolerance)) for s in self.listed)
            moves = composite_moves(self.composites, changes)
            following = sum(1 for move in moves.values() if move is not None)
            left_out = sum(1 for m in moves.values() if m is None)
            note = composites_text(following, left_out, self.ak.b) if self.listed else u""  # (nothing listed: nothing follows)
            self.composites_note.setText(note)
            self.composites_note.setVisible(bool(note))
            self.status.setText(u"%s %s" % (self.font_line(), spacing_status(
                len(self.listed), len(self.spacings), tolerance, getattr(self, "settle_passes", 1), self.ak.b, self.ak.i)))
        self.select()

    def font_line(self):
        """The top line's start, as every window's (ak.font_named): the font, its master, and how many masters
        it has where more than one."""
        package = self.package
        if package is None:
            return u""
        return self.ak.font_named(getattr(package, "tfn", u""), self.master, getattr(package, "mastersCount", 1)) + u"."

    def refill(self):
        """The list filtered again (the tolerance changed), under the window's top-row progress; stopped,
        the list is left empty until the tolerance changes again or Analyze is clicked."""
        if self.busy:
            return
        self.busy = True
        self.ak.busy_start(self, LIST_STEP)
        try:
            self.fill(lambda part: self.ak.busy_progress(self, None, part))
        except self.ak.Stopped:
            self.stopped(u"Listing", measured=True)
        finally:
            self.ak.busy_end(self)
            self.busy = False
            self.update_buttons()

    def stopped(self, what, measured=False):
        """The work stopped by the user (the top row's Esc, Close, a tool, an arrow): the list left
        empty, and the status line says so."""
        self.tree.clear()
        self.listed = []
        if not measured:
            self.spacings = []
        self.composites_note.setText(u"")
        self.composites_note.setVisible(False)
        self.status.setText((u"%s %s" % (self.font_line(), stopped_text(what, measured))).strip())

    def row_texts(self, s, tolerance):
        """A row's cells: the glyph's character, its name (a reference says so), its code point, its
        sidebearings now and the changes, its width after."""
        left, right = s.changes(tolerance)
        sign = lambda value: u"%+d" % value if value else u"0"
        code = self.ak.code_point(s.char) if s.char else 0
        return [s.char, s.name + (u" (reference)" if getattr(s, "reference", False) else u""), self.ak.unicode_label(code),
                u"%d" % round_units(s.left), sign(left), u"%d" % round_units(s.right), sign(right),
                u"%d" % round_units(s.advance + left + right)]

    def harvest(self):
        QtCore, QtGui = _qt()
        for row in range(self.tree.topLevelItemCount):
            item = self.tree.topLevelItem(row)
            index = int(item.data(0, QtCore.Qt.UserRole))
            if index < len(self.listed):
                self.listed[index].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        """Tick all or Tick none, the log saying how many glyphs it changed (the shared check_rows)."""
        items = [self.tree.topLevelItem(row) for row in range(self.tree.topLevelItemCount)]
        self.ak.check_rows(items, bool(on), self.log, u"Tick all" if on else u"Tick none", u"glyph")
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
        self.ak.enable(self.kerning_button, bool(self.spaced) and not self.busy)
        self.ak.enable(self.follow, bool(items))  # nothing listed: nothing for it to act on
        # No font: nothing to pick glyphs from; nothing measured: no list for the tolerance to filter. The font
        # itself stopping the analysis (CannotSpace): Analyze and the choice that only feeds it grayed, nothing
        # they could do, until the font changes (owner's image 253; run measures again as it does)
        failed = getattr(self, "failed", False)
        self.ak.enable(self.group, self.package is not None and not self.busy and not failed)
        self.ak.enable(self.tolerance, bool(self.spacings))
        self.ak.enable(self.analyze_button, not self.busy and not failed and
                       (self.package is not None or self.ak.fonts_open(self.fontlab)))

    def check_kerning(self):
        """Kerning Check on the glyphs the last spacing changed."""
        if not self.spaced:
            return
        error = self.ak.open_kerning_check(self.spaced, u"Auto Spacing spaced", caller=self.dialog)
        if error:
            self.log.add(u"<i>Kerning Check</i> did not open: %s" % self.ak.html(error), "error")

    def restore(self):
        """The checks back as the list first came after the analysis (set on the rows themselves: filling
        the list reads its checks first)."""
        QtCore, QtGui = _qt()
        for s in self.spacings:
            s.checked = self.first_checks.get(s.name, s.checked)
        self.tree.blockSignals(True)
        for row in range(self.tree.topLevelItemCount):
            item = self.tree.topLevelItem(row)
            index = int(item.data(0, QtCore.Qt.UserRole))
            if index < len(self.listed):
                item.setCheckState(0, QtCore.Qt.Checked if self.listed[index].checked else QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.refill()
        self.log.add(u"Ticks restored as suggested.")

    def double_clicked(self, item, column):
        if column in (0, 1):  # the glyph or its name
            self.show_in_glyph_window()

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick):
        measured anew, or the list emptied and the no-font line shown."""
        self.spaced = []
        self.run()

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
        error = self.ak.open_auto_kerning_at(*((reference, s.name) if side == "before" else (s.name, reference)),
                                             caller=self.dialog)
        if error:
            self.log.add(u"<i>Auto Kerning</i> did not open: %s" % self.ak.html(error), "error")

    def selected(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return None
        index = int(items[0].data(0, QtCore.Qt.UserRole))
        return self.listed[index] if index < len(self.listed) else None

    def row_names(self, item):
        """The glyph of a row (none for a section's heading): its flag shown."""
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return [self.listed[index].name] if 0 <= index < len(self.listed) else []

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
        for label, regions, (l, r) in zip((self.preview_now, self.preview_after), self.neighbors,
                                           ((0, 0), (left, right))):
            pixmap, spans = self.picture(s, l, r)
            label.setPixmap(pixmap)
            regions.set(spans, pixmap.size())

    def picture(self, s, left, right):
        """(picture, spans): the glyph between two of its references on each side, its sidebearings
        changed by left and right, in the dialog's text color, the references dimmed; the references'
        spans across the picture, (left, right, (side, name)), to be clicked. Its caption is the label
        over it (preview_captions: the shared preview_caption)."""
        QtCore, QtGui = _qt()
        ak = self.ak
        reference = reference_for(self.kind_of(s.char) or s.char, ak.category, ak.script_of)
        reference_glyph = ak.font_glyphs(self.package, [reference])
        sequence = []
        for ch, name in reference_glyph * 2 + [(s.char, s.name)] + reference_glyph * 2:
            layer = self.package.findName(name).getLayerByName(self.master)
            if layer is not None:
                sequence.append((layer, ak.layer_path(layer), name == s.name))
        scale = float(PREVIEW_SIZE) / float(self.package.upm)
        width = int(sum(layer.advanceWidth for layer, _, _ in sequence) * scale + (left + right) * scale) + PREVIEW_SIZE
        height = int(PREVIEW_SIZE * PREVIEW_HEIGHT)
        pixmap = QtGui.QPixmap(max(width, 10), height)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        spans, seen = [], False
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            x = float(PREVIEW_SIZE) / 2
            for layer, path, is_glyph in sequence:
                if is_glyph:
                    seen = True
                else:
                    spans.append((x, x + layer.advanceWidth * scale, ("after" if seen else "before", reference_glyph[0][1])))
                painter.save()
                painter.translate(x + (left * scale if is_glyph else 0), PREVIEW_SIZE * PREVIEW_BASELINE)
                painter.scale(scale, -scale)
                ink = QtGui.QColor(color)
                if not is_glyph:
                    ink.setAlpha(SIDE_ALPHA)
                painter.fillPath(path, QtGui.QBrush(ink))
                painter.restore()
                x += layer.advanceWidth * scale + ((left + right) * scale if is_glyph else 0)
        finally:
            painter.end()
        return ak.inked(pixmap, color), spans  # (one color at two strengths: redrawn in the new one on a switch)

    def context_text(self, name, char):
        """FontLab text for a glyph between two of its references on each side (its straight one, then
        its round one: /n/n/a/n/n, /o/o/a/o/o), a line each; the glyph alone where they cannot be read."""
        ak = self.ak
        try:
            reference = reference_for(self.kind_of(char) or char, ak.category, ak.script_of) if char else u"n"
            names = [found for _, found in ak.font_glyphs(self.package, [reference, ROUND_REFERENCES.get(reference, u"O")])]
        except Exception:
            names = []
        return u"/space".join(u"/%s/%s/%s/%s/%s" % (r, r, name, r, r) for r in names) or u"/%s" % name

    def show_in_glyph_window(self):
        s = self.selected()
        if s is None:
            return
        error = self.ak.show_in_glyph_window(self.fontlab, self.context_text(s.name, s.char))
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % self.ak.html(error), "error")

    def log_link(self, target):
        """A glyph named in the log clicked: opened between its references in a Glyph window, as Show in
        Glyph window opens a row's (a composite whose diacritics the log says to check is seen beside
        its neighbors); False for a link left to the log (a glyph the font no longer has)."""
        ak = self.ak
        name = ak.glyph_of_link(self.package, target) if self.package is not None else None
        if not name:
            return False
        try:
            code = ak.main_code(self.package.findName(name).fgGlyph)
            char = ak.unichr_(code) if code else None
        except Exception:
            char = None
        error = ak.show_in_glyph_window(self.fontlab, self.context_text(name, char))
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % ak.html(error), "error")
        return None

    # -- changing the font ----------------------------------------------

    def apply(self):
        """The checked glyphs spaced, as one step of the History. The references among them first, the
        others then measured against them again; after writing, the glyphs are measured again and those
        still a side the tolerance or more off are spaced again (APPLY_PASSES at most): one click lands
        where the next analysis would ask nothing more."""
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
        references = [s for s in chosen if getattr(s, "reference", False)]
        others = [s for s in chosen if not getattr(s, "reference", False)]
        totals, stale, error, moved = {}, 0, None, []
        passes, again, measured_again, unread = 0, 0, 0, False
        if not self.ak.begin_write(self.fontlab, self.package, u"FreeLab Auto Spacing", self.log):
            return  # (nothing written: the reason in the log)
        self.busy = True
        # Under the window's top-row progress, never stoppable: one step of the History, never half written
        # (a click on Close, a tool, or an arrow is done once it is over)
        batches = [references, others] if references and others else [chosen]
        units = len(batches) * APPLY_PASSES * 2 + 2  # (each write and each measuring again; following; the step)
        self.write_span = (0, units)
        self.ak.busy_start(self, SPACE_STEP, stoppable=False)
        try:
            try:
                written = []
                for number, batch in enumerate(batches):
                    last = number == len(batches) - 1
                    if number:  # the references were spaced: the others measured against them as they are now
                        if not self.reads_back(written):
                            unread = True
                            break
                        self.write_span = (number * APPLY_PASSES * 2 - 1, units)
                        batch = self.measured_again(batch, tolerance)
                        measured_again = len(others)
                    for attempt in range(APPLY_PASSES):
                        self.write_span = ((number * APPLY_PASSES + attempt) * 2, units)
                        self.write_progress(SPACE_STEP, 0.0)
                        written, stale_now = self.write_spacings(batch, tolerance, totals)
                        stale += stale_now
                        if last:
                            passes = attempt + 1
                        if not written or attempt == APPLY_PASSES - 1 or not last:
                            break  # (the references are written once: they are not measured, but spaced from the corpus)
                        if not self.reads_back(written):
                            unread = True
                            break
                        self.write_span = ((number * APPLY_PASSES + attempt) * 2 + 1, units)
                        batch = self.measured_again([s for s, _, _ in written], tolerance)
                        if not batch:
                            break
                        if last and attempt == 0:
                            again = len(batch)
                if self.follow.checked:
                    self.write_span = (units - 2, units)
                    self.write_progress(FOLLOW_STEP, 0.0)
                    moved = self.follow_composites(totals)
            except CannotSpace:
                pass  # (the font can no longer be measured: the analysis after the write says so, once; it was
                # said twice, the second time as an error, owner's image 335)
            except Exception as exc:  # what was changed stays changed, and is reported
                error = exc
            finally:
                self.busy = False
            self.write_span = (units - 1, units)
            self.write_progress(UPDATE_STEP, 0.0)
            status = self.after_writing()
            asked_to_stop = self.ak.busy_stopping(self)  # (Esc, Close, a tool, an arrow, during the write)
        finally:
            self.ak.busy_end(self)
        ak = self.ak
        self.spaced = sorted(totals) + sorted(name for name in moved if name not in totals)
        lines = [u"Spaced %s%s." % (ak.b(counted(len(totals), u"glyph")),
                                    u", and %s built on them followed" % ak.b(counted(len(moved), u"glyph"))
                                    if self.follow.checked and totals else u"")]
        note = apply_note(passes, again, tolerance, measured_again if not unread else 0, ak.b)  # (rich: counts bold)
        if note:
            lines.append(note)
        if totals:
            lines.append(u"The kerning was set for the old spacing: click %s to see whether pairs with these glyphs now "
                         u"collide, or run %s again with <i>Include existing kerned pairs</i>." % (
                             ak.i(KERNING_BUTTON), ak.tool_link(u"Auto Kerning")))  # (a link: owner's image 220)
        lines.append(status.undo(u"<i>Edit &gt; Undo</i> (or the <i>History</i> panel) takes it back."))
        self.log.add(u" ".join(line for line in lines if line), "done" if totals else "info")
        status.report(self.log)
        overhang = self.overhang_line() if self.follow.checked else u""
        if overhang:
            self.log.add(overhang, "warning")
        if unread:
            self.log.add(u"FontLab did not give the new outlines back at once, so the glyphs could not be measured again "
                         u"before the step ended: the list shows what is left, to space with another click.", "warning")
        if stale:
            self.log.add(u"%s had changed since the analysis and %s left as %s." % (
                ak.b(counted(stale, u"glyph")), u"was" if stale == 1 else u"were", u"it was" if stale == 1 else u"they were"),
                "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % ak.html(error), "error")
        if asked_to_stop:  # (what was clicked is done now: the glyphs are not measured again under it)
            self.stopped(u"Measuring again")
            self.seen_history = ak.history_mark(self.package)  # (this write's own step: not measured again for it)
            self.update_buttons()
            return
        self.run()

    def write_progress(self, what=None, part=None):
        """The write's progress in the window's top row (part: 0 to 1 of the unit of work under way, out of
        write_span's), never stoppable: the write is one step of FontLab's History."""
        done, units = getattr(self, "write_span", (0, 1))
        self.ak.busy_progress(self, what, None if part is None else (done + min(max(part, 0.0), 1.0)) / float(units),
                              stoppable=False)

    def write_spacings(self, rows, tolerance, totals):
        """Each row's changes written (its outline moved by the left change, its width changed by both),
        added up in totals {name: (left, right)}. ([(row, left, right) written], rows edited since they
        were measured: left as they are)."""
        QtCore, QtGui = _qt()
        package, master = self.package, self.master
        written, stale = [], 0
        for number, s in enumerate(rows):
            if number % PUMP_EVERY == 0:
                self.write_progress(None, number / float(len(rows)))
            glyph = package.findName(s.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            left_now, right_now, width_now = ink_sides(layer)
            if abs(left_now - s.left) > 0.5 or abs(right_now - s.right) > 0.5:
                stale += 1  # edited since the analysis: measured again next time
                continue
            left, right = s.changes(tolerance)
            if not left and not right:
                continue
            if left:
                shift = QtGui.QTransform()
                shift.translate(left, 0)
                layer.applyTransform(shift)  # the outline's nodes move (checked in FontLab 7.2)
            layer.advanceWidth = width_now + left + right
            before = totals.get(s.name, (0, 0))
            totals[s.name] = (before[0] + left, before[1] + right)
            written.append((s, left, right))
            self.touched(glyph)
        return written, stale

    def reads_back(self, written):
        """Whether the glyphs just written read back as written (their ink's sides moved by the changes):
        only then can they be measured again before the History step ends."""
        package, master = self.package, self.master
        for s, left, right in written:
            glyph = package.findName(s.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                return False
            left_now, right_now, _ = ink_sides(layer)
            if abs(left_now - (s.left + left)) > 0.5 or abs(right_now - (s.right + right)) > 0.5:
                return False
        return True

    def measured_again(self, rows, tolerance):
        """The rows' glyphs measured again as they are now: those with a side tolerance units or more
        off, as new rows."""
        spacings, _ = self.measure(self.package, self.master, only=set(s.name for s in rows),
                                   progress=lambda what, part: self.write_progress(
                                       SETTLE_STEP, None if part is None else part / measure_part(COMPOSITES_STEP, 0.0)))
        return [s for s in spacings if s.listed(tolerance)]

    def follow_composites(self, totals):
        """The composites built on the glyphs spaced, moved with them (totals: each glyph's changes in
        all); the names of those moved. One whose marks then stick out past its width (or before its
        start) further than they did, by more than OVERHANG_SHARE of the em (a horn on a tighter O, a
        vertical caron on d), follows all the same (its letter's outline moved under its marks already)
        and is kept in self.overhanging, to name: its marks may meet the next letter."""
        QtCore, QtGui = _qt()
        package, master = self.package, self.master
        moved, self.overhanging = [], []
        reach = OVERHANG_SHARE * float(package.upm)

        def component_box(name):  # (a component's glyph's box, in its own units)
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            return layer.boundingBox if layer is not None else None

        moves = list(composite_moves(self.composites, totals).items())
        for number, (name, move) in enumerate(moves):
            if number % PUMP_EVERY == 0:
                self.write_progress(None, number / float(len(moves)))
            if move is None:
                continue
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            shift, width_change = move
            if mark_overhang(layer, shift, width_change, component_box) > reach:
                self.overhanging.append(name)  # followed all the same, and named in the log, to check
            for shape in layer.shapes[1:]:  # the accents: kept over the base, whose outline moved
                t = shape.transform  # moved in the layer's units, whatever the component's scale or mirroring
                shape.transform = QtGui.QTransform(t.m11(), t.m12(), t.m21(), t.m22(), t.dx() + shift, t.dy())
            layer.advanceWidth = layer.advanceWidth + width_change
            self.touched(glyph)
            moved.append(name)
        return moved

    def overhang_line(self):
        """The log's warning naming the composites whose marks now stick out further (follow_composites),
        or u""."""
        names = getattr(self, "overhanging", [])
        if not names:
            return u""
        one = len(names) == 1  # (named by glyph, not by character: the interface's fonts lack many, shown as boxes)
        return (u"Check the diacritics of %s: %s followed %s base glyph, and %s diacritics now stick out further past %s width "
                u"(or before %s start), toward the next glyph: %s." % (
                    self.ak.b(counted(len(names), u"glyph")), u"it" if one else u"they", u"its" if one else u"their",
                    u"its" if one else u"their", u"its" if one else u"their", u"its" if one else u"their",
                    self.ak.glyph_name_links(names)))

    def touched(self, glyph):
        try:
            glyph.update()
        except Exception:
            pass

    def after_writing(self, glyphs=()):
        """notify_changed's WriteStatus."""
        return self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Auto Spacing", glyphs)

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


OVERHANG_SHARE = 0.01  # of the em: how much further a composite's marks may stick out once it follows its letter


def mapped_span(box, transform):
    """(left, right) of a box (a QRectF) once placed by a transform (a QTransform: x' = m11 x + m21 y +
    dx), its four corners mapped."""
    xs = [float(transform.m11()) * x + float(transform.m21()) * y + float(transform.dx())
          for x in (float(box.left()), float(box.right())) for y in (float(box.top()), float(box.bottom()))]
    return min(xs), max(xs)


def shape_span(shape, component_box=None):
    """(left, right) of what a layer's shape draws, in the layer's units, or None. A component: its
    glyph's own box (component_box(name), in that glyph's units) placed by the component's transform.
    A zero-width mark is drawn left of its origin (circumflexbelowcomb at about -300 to -100), so its
    box in its own units read as the layer's put it far before the composite's start: ucircumflexbelow
    was named as sticking out though its mark sat well inside its 451 units (owner's images 144/146).
    Else, or when that cannot be read, the shape's own box."""
    name = component_glyph(shape) if component_box is not None else None
    if name:
        try:
            box = component_box(name)
            if box is not None:
                return mapped_span(box, shape.transform)
        except Exception:
            pass
    try:
        box = shape.boundingBox
        box = box() if callable(box) else box
        return float(box.left()), float(box.right())
    except Exception:
        return None


def mark_overhang(layer, shift, width_change, component_box=None):
    """How much further a composite's marks (its components after the first) would stick out past its
    width, or before its start, once its letter's move is followed (shift: the outline's move across;
    width_change: the advance's), in units; 0 when they would not. Each side is weighed against itself:
    a mark already out on the left does not hide one growing out on the right. component_box(name): a
    component's glyph's box in its own units (shape_span)."""
    right_before = left_before = right_after = left_after = 0.0
    width = float(layer.advanceWidth)
    for shape in list(layer.shapes)[1:]:
        span = shape_span(shape, component_box)
        if span is None:
            continue
        left, right = span
        right_before = max(right_before, right - width)
        left_before = max(left_before, -left)
        right_after = max(right_after, right + shift - (width + width_change))
        left_after = max(left_after, -(left + shift))
    return max(0.0, right_after - right_before, left_after - left_before)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("Auto Spacing"):
            return
    except Exception:
        pass
    try:
        dialog = AutoSpacingDialog()
    except Exception as exc:
        print("FreeLab Auto Spacing: %s" % exc)
        return
    sys._freelab_auto_spacing = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("Auto Spacing", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_auto_spacing":
    main()
