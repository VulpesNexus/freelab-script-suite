# -*- coding: utf-8 -*-
"""FreeLab Feature Code's Stylistic alternates tab (loaded by freelab_feature_code.py; not a script of its own).

Suggestions: the characters fonts give stylistic alternates most (features/alternates_model.json,
from features/train/alternates.py: which characters the corpus's open-licensed fonts vary in ssXX, cvXX,
and salt), those the font has listed with how many families vary them and the alternates it has already.
A ticked one gets a copy to redraw by hand, X.ss01 (the next free set), its outlines as they are; the
Forms tab writes its stylistic set. That is one job, the variants below another: neither is a step of
the other (the builder needs no copy made first), and the window says so under each heading. The two
jobs are two parts of a splitter (its handle right under the list), and their buttons (Tick all, Tick
none; Make copies to redraw, Build variants) are in the window's bottom row, shown with this tab.

Variants that take turns: each glyph in scope (a letter's, a figure's, or a punctuation mark's: what
the first tab's turns take) gets copies X.alt1, X.alt2... made by a few smooth
changes of the whole glyph (a slight rotation, uneven scaling, a slant, a baseline shift), at one of
three strengths, from a seed (the same seed makes the same variants). No node jitter: moving nodes one
by one breaks smooth curves and reads as noise, not handwriting. Every change is made about the glyph's
own ink (its box's center), none against the x-height or the baseline, so a period or a hyphen is
changed in proportion as a letter is: a 100-unit period's edge moves 1 unit under the Subtle scale and
under 1 under its rotation and slant, and the baseline shift, a share of the em (5 units of 1,000), is
the change that shows on it; its advance width stays, as a tabular figure's does. The first tab's
Alternates that take turns then writes the calt code that cycles them (X.alt1 is the form its
convention reads).

With "Also build variants from existing alternates" (grayed out, and counted as unticked, while no
glyph in scope has an alternate to build from), a glyph's variants are spread over its designs in turn:
the glyph itself and the alternates the font has of it (W.ss01, W.2, W.salt, and the variants built
before, W.alt1: designs_of; image 269, the option stayed grayed out after a build of variants).
Variant 1 is a changed copy of the glyph, variant 2 of its first alternate, and around again, each of
one design, never a blend. A variant of an alternate carries that alternate's name (W.ss01.alt2), so its
origin reads from its name and no two variants share a number; the first tab cycles it with the glyph's
other variants (W, W.alt1, W.ss01.alt2), so a repeated glyph changes design as well as detail.

Variants this tab built and nobody changed since are its own (own_variants: each one's outlines as the
build left them, and the strength and seed it was built with, kept for the window's life). Built again
with another strength or seed, they are replaced in place, as one step of FontLab's History
(image 270: a new seed could not rebuild what was just built); with the same, they are left as they are.

The list has two groups (image 302): Suggestions, the copies' glyphs, and Selected glyphs, the
glyphs the Glyphs dropdown picks for the variants, all ticked (a new pick replaces the last; a glyph
unticked there is out of the build and the previews). The pick is the ticked suggestions (at first, kept
in step as they are ticked), those that often stand doubled in text, characters typed in a box, a script
the font has (Latin first), a case of letters, or every letter, figure, and punctuation mark (a pick of
more than SELECTED_MOST glyphs is not listed: one click could not build them). Make copies to redraw acts
on the ticked suggestions, Build N variants on the ticked selected glyphs; Tick all and Untick all on
both groups. Scripts and cases are read from the model's tables (features/train/
scripts.py and kinds.py), not asked of the running Python. The button and the line under it say how
many variants of which glyphs a click builds (the line in the paragraph over the settings,
image 245); a build that would pass what a font holds (65,535
glyphs), what one click builds (BUILD_MOST), or the time one click may take (SECONDS_MOST, at the
pace of the session's last build) is refused before anything is made, in a sentence that says what
to choose instead. A long build shows its progress in the window's top row.
Valid Python 2.7 (FontLab) and 3 (tests).
"""
from __future__ import absolute_import, division, print_function

import bisect
import json
import os
import random
import re
import time
import unicodedata
import zlib

MODEL_FILE = "alternates_model.json"
SUGGESTED_MAX = 40  # characters listed, the most varied first
ICON_SIZE = 36  # pixels: a row's pictures, as in the window's other lists (they set the rows' height)
# (key, label, rotation in degrees, scale change, slant in degrees, baseline shift in em): the most each
# change may reach; each variant draws its own within them. Subtle stays within what readers take for
# one hand (about the ranges tools for handwriting fonts use at their lowest settings).
STRENGTHS = (("subtle", u"Subtle", 0.8, 0.02, 1.0, 0.005),
             ("moderate", u"Moderate", 1.5, 0.04, 2.0, 0.01),
             ("bold", u"Bold", 3.0, 0.07, 4.0, 0.02))
# The builder's scopes, narrowest first; a scope per script of the font goes after SCRIPTS_AFTER
# (scopes_for), keyed SCRIPT_SCOPE and the script's name. A scope's name is its name alone ("Everything",
# not "Every letter, figure, and punctuation mark"; "Often doubled", the first tab's words for the same
# glyphs): what it holds is said in the box's What's This.
SCOPES = (("checked", u"The ticked suggestions"), ("doubled", u"Often doubled"),
          ("typed", u"These glyphs"), ("lower", u"Lowercase letters"), ("upper", u"Capitals"),
          ("both", u"Capitals and lowercase"), ("all", u"Everything"))
SCRIPT_SCOPE, SCRIPTS_AFTER, FIRST_SCRIPT = u"script:", "typed", u"Latin"
# What the box beside the scopes says while These glyphs is picked (and only then: grayed out, it is
# empty). It takes characters typed one after another, spaces or not (its What's This gives an example;
# the gray example "lest" read as a word). A field's placeholder ends with an ellipsis (image 309).
TYPED_HINT = u"Type characters\N{HORIZONTAL ELLIPSIS}"
NO_FONT_FIELD = u"n/a"  # (what the field says, grayed out, while the window has no font)
# The list's two groups (image 302): the suggestions, which Make copies to redraw copies, and the
# glyphs the Glyphs dropdown picks, which Build N variants builds. Each group row is bold, its count in
# parentheses, and closes as every grouped list's; a row's group is told by its group row's key.
SUGGESTIONS_GROUP, SELECTED_GROUP = u"Suggestions", u"Selected glyphs"
LIST_HEADING = u"Glyphs for alternates"  # (it was "Suggested alternates": the list holds both groups now)
SUGGESTIONS_KEY, SELECTED_KEY = u"\tsuggestions", u"\tselected"
NO_DATA = u"\N{EN DASH}"  # a cell that means nothing for its row (no count of a glyph the model lacks)
ROW_PICTURES = 120  # the selected glyphs drawn as the list is made; the rest when their row is clicked
ROW_PICTURE_TIP = u"Click the row to draw it."
DESIGNS_LABEL = u"Also build variants from existing alternates."
DESIGNS_WHAT = (u"Spreads a glyph's variants over its designs in turn: the glyph and the alternates the font has of "
                u"it (W.ss01, W.2, W.salt, and variants built before, such as W.alt1). Variant 1 is a changed copy of "
                u"the glyph, variant 2 of its first alternate, and around again; each is a copy of one design, never "
                u"a blend. A variant of an alternate is named after it (W.ss01.alt2), and the first tab cycles it "
                u"with the glyph's other variants (W, W.alt1, W.ss01.alt2), so a repeated glyph changes design as "
                u"well as detail. Unticked, every variant is a copy of the glyph itself.")
DESIGNS_NONE = (u"Grayed out: no glyph in scope has an alternate to build from (a glyph named after it with a set, a "
                u"number, .salt, or .alt, such as W.ss01, W.2, or W.alt1), so every variant is a copy of the glyph "
                u"itself. Your choice is kept for glyphs that have some.")
NAMED_MOST = 8  # characters named in the line that says what a click builds; alternates drawn in the preview
LONG_BUILD = 200  # variants: a build this large says that it may take a bit
# The words for it (2026-11-14), and nothing more: the sentence once gave a time at the last
# build's pace and said that the window's top line shows the progress
LONG_BUILD_WORDS = u"A build this large may take a bit."
LINKED_MOST = 12  # built variants named in the log, each a link drawn from its outlines; more: counted only
PREVIEW_HEIGHT = 100  # pixels: the em in the previews
SET_SUFFIX = u".ss%02d"
VARIANT_SUFFIX = u".alt%d"
# What one click may build. A font holds 65,535 glyphs (its glyph numbers are 16 bits). The first tab's
# turns serve 6,000 variants at most (by position, 8 bytes of GSUB each, of the 48,000 it allows:
# freelab_feature_code's TURN_BYTES_MAX), so more could not all take turns. On fakes of 24,000 and
# 37,000 glyphs, fontTools compiled the code for 6,000 variants in 0.1 to 0.2 s (a GSUB of 12 KB in
# the font's order, 59 KB in a shuffled one); for 19,939 variants it wrote 120 KB, twice what a
# table's offsets reach, which FontLab's compiler does not work around. FontLab's own pace is not
# known before a first build, so the time limit applies from the pace of the session's last build of
# PACE_FROM variants or more.
GLYPHS_MOST = 65535
BUILD_MOST = 6000
# The glyphs a pick lists at most (Selected glyphs): a click builds BUILD_MOST variants at most, one a
# glyph at least, so a larger pick could never be built in one click; listed, a whole CJK font's tens of
# thousands of rows would take seconds at each pick
SELECTED_MOST = BUILD_MOST
SECONDS_MOST = 600
PACE_FROM = 20
# An alternate's suffix the builder builds from: a set, a character variant, salt, alt (its own variants,
# X.alt1, among them), calt, or a number (what freelab_feature_code's DESIGN_VARIANT reads back, so the
# first tab cycles every variant built). One suffix only: a variant of a variant (W.alt1.alt3) is not built from.
DESIGN_SUFFIX = re.compile(r"^(?:(?:ss|cv)[0-9]{2}|salt|c?alt[0-9]*|[0-9]+)$")
VARIANT_OF = re.compile(r"^(?:[^.]+\.)?alt([0-9]+)$")  # after the glyph's name: alt2 (W.alt2), ss01.alt2 (W.ss01.alt2)


def load_model(path=None):
    """The model's [(character, families varying it)], families read, families with alternates; or None."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILE)
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        return [(c, int(n)) for c, n in data["characters"]], data.get("families"), data.get("with_alternates")
    except Exception:
        return None


def suggestions(model_rows, cmap, names, most=SUGGESTED_MAX, index=None):
    """[(character, glyph, families, [its alternates in the font])] for the model's characters the font
    has (cmap: {code point: glyph}), the most varied first. Its alternates: glyphs named after it with
    a stylistic suffix (a.ss01, a.cv01, a.salt, a.alt, a.alt1). index: alternates_index(names), where
    the caller holds it (a glyph named without a period is read from it, not from every name again)."""
    found = []
    for ch, families in model_rows:
        glyph = cmap.get(ord(ch))
        if not glyph:
            continue
        if index is not None and u"." not in glyph:
            found.append((ch, glyph, families, list(index.get(glyph, ()))))
            continue
        found.append((ch, glyph, families, alternates_of(glyph, names)))
        if len(found) >= most:
            break
    return found


def stylistic_suffix(suffix):
    head = suffix.split(u".")[0]
    return head.startswith((u"ss", u"cv", u"salt", u"alt", u"calt")) or head.isdigit()


def alternates_of(glyph, names):
    """A glyph's alternates in the font, in order: the glyphs named after it with a stylistic suffix
    (u.01, u.ss01, u.alt1)."""
    prefix = glyph + u"."
    return sorted(n for n in names if n.startswith(prefix) and stylistic_suffix(n[len(prefix):]))


def alternates_index(names):
    """{glyph: [its alternates, in order]} for every glyph of the font at once (alternates_of, glyph
    by glyph, reads every name each time: too slow for a whole font's glyphs)."""
    found = {}
    for name in names:
        stem, dot, rest = name.partition(u".")
        if dot and stem and stylistic_suffix(rest):
            found.setdefault(stem, []).append(name)
    for forms in found.values():
        forms.sort()
    return found


def designs_of(glyph, alternates):
    """The designs the font has of a glyph, what its variants can be built from: the glyph, then the
    alternates it has (alternates: alternates_of), each named with one suffix (W.ss01, W.2, W.salt,
    W.alt, and the builder's own variants, W.alt1: image 269, the option stayed grayed out in
    a font whose alternates were all built here). Not a variant of an alternate (W.ss01.alt2): a variant
    of it would be a third generation, drifting from the drawing."""
    start = len(glyph) + 1
    return [glyph] + [name for name in alternates if DESIGN_SUFFIX.match(name[start:])]


def designs_in(glyphs, index):
    """Whether any of the glyphs has an alternate to build from (designs_of; index: alternates_index)."""
    return any(len(designs_of(glyph, index.get(glyph, ()))) > 1 for glyph in glyphs)


def variant_numbers(glyph, alternates):
    """{number: name} of the variants the font has of a glyph, built from the glyph (W.alt2) or from
    one of its alternates (W.ss01.alt2): a number is given once, whatever the design."""
    start = len(glyph) + 1
    found = {}
    for name in alternates:
        match = VARIANT_OF.match(name[start:])
        if match:
            found.setdefault(int(match.group(1)), name)
    return found


def variant_source(name, number):
    """The design a variant was built from, read from its name: W.ss01.alt2 (number 2) from W.ss01."""
    suffix = VARIANT_SUFFIX % number
    return name[:-len(suffix)] if name.endswith(suffix) else None


def variants_planned(glyphs, count, names, designs=False, index=None, ours=None, settings=None):
    """[(glyph, [(the variant to build, its number, the glyph it is built from)])] for the glyphs in
    scope: numbers 1 to count, less those the font has already (left as they are). Each is built
    from the glyph (X.alt1); with designs, from the glyph's designs in turn (designs_of: number 1 from
    the glyph, 2 from its first alternate, and around again), a variant of an alternate named after it
    (X.ss01.alt2). index: alternates_index(names), where the caller holds it. ours: {variant: the
    settings it was built with} of the variants this tab built and nobody changed since (own_variants);
    one of them whose settings are not settings (a strength and a seed) is planned again, under its own
    name and from its own design, to be replaced in place (image 270)."""
    index = alternates_index(names) if index is None else index
    ours = ours or {}
    plan = []
    for glyph in glyphs:
        alternates = index.get(glyph, ())
        taken = variant_numbers(glyph, alternates)
        sources = designs_of(glyph, alternates) if designs else [glyph]
        todo = []
        for number in range(1, count + 1):
            held = taken.get(number)
            if held is not None:
                source = variant_source(held, number)
                if held in ours and ours[held] != settings and source is not None and source in names:
                    todo.append((held, number, source))
                continue
            source = sources[(number - 1) % len(sources)]
            name = source + VARIANT_SUFFIX % number
            if name not in names:
                todo.append((name, number, source))
        plan.append((glyph, todo))
    return plan


def grouped(number):
    """65535 as 65,535."""
    digits = u"%d" % number
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    return u",".join([digits] + parts)


def counted(number, one, many=None):
    return u"%s %s" % (grouped(number), one if number == 1 else (many or one + u"s"))


def bold(text):
    """A count in bold with its noun (images 297 and 301: one rule for every status line, note,
    and log line), as the shared module's b()."""
    return u"<b>%s</b>" % text


def html(text):
    """Text shown as it is in a rich-text line (a glyph's name with &, <, or >)."""
    return (u"%s" % text).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


def group_title(title, count):
    """A group row's words: its name and its count in parentheses, as every grouped list's ("Suggestions (12)")."""
    return u"%s (%s)" % (title, grouped(count))


def duration(seconds):
    """A build's time in words: "1 minute", "12 minutes" (a minute at least: a guess from one pace)."""
    return counted(max(1, int(round(seconds / 60.0))), u"minute")


def build_problem(new, font_glyphs, pace=None):
    """Why a click may not build this many variants, as a sentence that says what to choose instead,
    or None: the font would pass the glyphs a font can hold; more than one click builds (BUILD_MOST);
    or longer than one click may take (SECONDS_MOST), at the pace of the last build (seconds a variant,
    None before one was timed). Its counts are bold (rich text: the line and the log show it so)."""
    if new and font_glyphs + new > GLYPHS_MOST:
        return (u"Nothing can be built: the font has %s, this build would add %s, and a font holds %s at most. "
                u"Choose fewer glyphs (a script, a case, or the glyphs that often double in text) or fewer "
                u"variants each." % (bold(counted(font_glyphs, u"glyph")), bold(counted(new, u"glyph")),
                                    bold(counted(GLYPHS_MOST, u"glyph"))))
    if new > BUILD_MOST:
        return (u"Nothing can be built: %s is more than one click builds (%s at most: more could not all take "
                u"turns in the first tab's code). Choose fewer glyphs (a script, a case, or the glyphs that "
                u"often double in text) or fewer variants each." % (
                    bold(counted(new, u"variant")), bold(grouped(BUILD_MOST))))
    if pace and new * pace > SECONDS_MOST:
        return (u"Nothing can be built: %s would take about %s at the last build's pace, and one click builds "
                u"for %s at most. Choose fewer glyphs or fewer variants each." % (
                    bold(counted(new, u"variant")), bold(duration(new * pace)), bold(duration(SECONDS_MOST))))
    return None


def scope_problem(count):
    """Why a pick of count glyphs is not listed, nor built, or None: past SELECTED_MOST, one click could
    not build a variant of each."""
    if count <= SELECTED_MOST:
        return None
    return (u"Nothing can be built: %s are picked, and one click builds %s at most (more could not all take "
            u"turns in the first tab's code), so they are not listed. Choose fewer glyphs (a script, a case, or "
            u"the glyphs that often double in text)." % (bold(counted(count, u"glyph")),
                                                         bold(counted(BUILD_MOST, u"variant"))))


def build_words(plan, count, scope, designs=False, problem=None, pace=None, again=0, listed=0):
    """(the build button's label, the line over the settings) for a plan (variants_planned): how many
    variants of which glyphs a click builds, said before the click; how many of them come from the
    font's alternates (designs: that option is on); how many of them replace variants built here with
    other settings (again); the problem's sentence in place of the count where the build is refused
    (build_problem); a sentence that a long build may take a bit (pace: what build_problem measures by,
    the line no longer says a time). listed: the glyphs Selected glyphs lists (a plan of none, with some
    listed: every one of them unticked). The line is rich text, each count bold with its noun."""
    glyphs = [glyph for glyph, _ in plan]
    new = sum(len(variants) for _, variants in plan)
    if not glyphs:
        if listed:
            return u"Build variants", (u"Every glyph of <i>%s</i> is unticked: tick some in the list above, or pick "
                                       u"other glyphs here." % SELECTED_GROUP)
        why = {"checked": u"No suggestion ticked in the list above can take turns (a letter's, a figure's, or a "
                          u"punctuation mark's): tick some, or pick other glyphs here.",
               "typed": u"Type the characters of the glyphs to vary in the box (the glyphs of letters, figures, and "
                        u"punctuation marks the font has are taken).",
               "doubled": u"The font has no glyph that often stands doubled in text.",
               "all": u"The font has no glyph that can take turns (a letter's, a figure's, or a punctuation mark's)."}.get(
                   scope, u"The font has no such letters.")
        return u"Build variants", why
    if problem:
        return u"Build variants", problem
    named = html(u", ".join(glyphs[:NAMED_MOST]) + (u"\N{HORIZONTAL ELLIPSIS}" if len(glyphs) > NAMED_MOST else u""))
    kept = len(glyphs) * count - new
    line = u"%s (%s): %s to build" % (bold(counted(len(glyphs), u"glyph")), named,
                                      bold(counted(new, u"variant")) if new else u"no variant")
    if designs and new:
        line += u" (%s from the font's alternates)" % bold(grouped(
            sum(1 for glyph, variants in plan for _, _, source in variants if source != glyph)))
    if again:  # (variants built here with another strength or seed: replaced in place)
        line += u", %s built here before with other settings, replaced in place" % (
            u"it" if new == 1 else (u"all of them" if again == new else u"%s of them" % bold(grouped(again))))
    if kept:
        line += u"; %s the font has already %s left as %s" % (
            bold(counted(kept, u"variant")), u"is" if kept == 1 else u"are", u"it is" if kept == 1 else u"they are")
    line += u"."
    if new >= LONG_BUILD:  # (the words, nothing more: the top line's count needs no announcing)
        line += u" " + LONG_BUILD_WORDS
    return (u"Build %s" % counted(new, u"variant")) if new else u"Build variants", line


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


def ranges_table(ranges):
    """([each range's first code point], [(first, last, label)]) of {label: "0041-005A 0061-007A 00AA"}:
    the form the model keeps its tables in (a script's or a case's code points), ready for looked_up."""
    rows = []
    for label, text in ranges.items():
        for part in text.split():
            first, _, last = part.partition(u"-")
            rows.append((int(first, 16), int(last or first, 16), u"%s" % label))
    rows.sort()
    return [row[0] for row in rows], rows


def load_tables(path=None):
    """{"scripts": table, "cases": table} of the model (features/train/scripts.py: Unicode's Script
    property; features/train/kinds.py: lower and upper case), each as ranges_table makes it, or None
    where the file or the table is missing. FontLab's Python 2.7 knows Unicode 5.2 and no scripts, so
    neither is asked of the Python that runs: a font's scopes are the same in FontLab and in the tests."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILE)
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
    except Exception:
        data = {}
    found = {}
    for key in ("scripts", "cases"):
        try:
            found[key] = ranges_table(data[key])
        except Exception:
            found[key] = None
    return found


_TABLES = []  # the model's tables, read once (load_tables), when a script or a case is first asked


def tables():
    if not _TABLES:
        _TABLES.append(load_tables())
    return _TABLES[0]


def looked_up(ch, table):
    """A character's label in a table of ranges (its script, its case), or None."""
    if not table or not ch or len(ch) != 1:
        return None
    starts, rows = table
    at = bisect.bisect_right(starts, ord(ch)) - 1
    return rows[at][2] if at >= 0 and ord(ch) <= rows[at][1] else None


def script_of(ch, table=None):
    """A character's script by Unicode's name for it (Latin, Cyrillic, Han), or None: a figure, most
    punctuation marks, and anything else that belongs to no one script."""
    return looked_up(ch, tables()["scripts"] if table is None else table)


def in_scope(ch, scope, cases=None):
    """Whether a character is in a case's scope of variants (lowercase letters, capitals, or both), by
    the model's table of cases; only without it (a file missing beside the script) does unicodedata
    answer, as the running Python knows the character."""
    cases = tables()["cases"] if cases is None else cases
    if cases:
        case = looked_up(ch, cases)
        return case is not None and (scope == "both" or case == scope)
    kind = unicodedata.category(ch)
    if not kind.startswith(u"L"):
        return False
    if scope == "lower":
        return kind == u"Ll"
    if scope == "upper":
        return kind in (u"Lu", u"Lt")
    return kind in (u"Ll", u"Lu", u"Lt")


def font_scripts(chars, table=None):
    """The scripts of a font's characters (chars: those of the glyphs that can take turns), the first
    of them FIRST_SCRIPT where the font has it, then the script with the most glyphs first."""
    counts = {}
    for ch in chars:
        script = script_of(ch, table)
        if script:
            counts[script] = counts.get(script, 0) + 1
    return sorted(counts, key=lambda script: (script != FIRST_SCRIPT, -counts[script], script))


def scopes_for(scripts):
    """[(key, label)] of the builder's scopes for a font with these scripts: SCOPES, with a scope per
    script (Latin glyphs, Cyrillic glyphs) after the glyphs typed, before the cases."""
    rows = []
    for key, label in SCOPES:
        rows.append((key, label))
        if key == SCRIPTS_AFTER:
            rows.extend((SCRIPT_SCOPE + script, u"%s glyphs" % script) for script in scripts)
    return rows


BASELINE_MOST = 500  # units: the Baseline field's reach at most


def strength_of(key):
    return next((row for row in STRENGTHS if row[0] == key), STRENGTHS[0])


def variant_params(glyph, number, strength, seed, baseline=0, upm=1000.0):
    """(rotation degrees, x scale, y scale, slant degrees, baseline shift in em) of glyph's variant number:
    each drawn within the strength's reach, from the seed (the same seed, the same variants; Python 2 and
    3 alike: the generator is seeded with a CRC of the text, not Python's hash). baseline: that many units at
    most more up or down (image 366; 0: the variants are as before it existed), the variants taking
    turns up and down (variant_lift)."""
    _, _, rotation, scale, slant, rise = strength_of(strength)
    key = (u"%s|%s|%d|%s" % (seed, glyph, number, strength)).encode("utf-8")
    rng = random.Random(zlib.crc32(key) & 0xFFFFFFFF)
    pick = lambda reach: rng.uniform(-reach, reach)
    params = (round(pick(rotation), 3), round(1.0 + pick(scale), 4), round(1.0 + pick(scale), 4),
              round(pick(slant), 3), round(pick(rise), 5))
    if baseline:
        lift = variant_lift(glyph, number, strength, seed, float(baseline), rng)
        params = params[:4] + (round(params[4] + lift / float(upm or 1000.0), 5),)
    return params


BASELINE_LEAST = 1 / 3.0  # of the Baseline reach: the least a variant moves, so each move shows


def variant_lift(glyph, number, strength, seed, reach, rng):
    """Units a variant moves up (or down, negative) within reach: the variants take turns, one up and the next
    down, the first's way drawn from the seed and the glyph (so that glyphs side by side do not all start the
    same way), each move between a third of the reach and all of it, drawn from the variant's own generator.
    Drawn each on its own, up or down, a run of variants could go further down at each one: Q's four at seed 6
    went up 496 units, then down 116, 229, and 353 (images 238 and 239, 2026-11-27: "they would
    rather jump up and down alternatively")."""
    first = zlib.crc32((u"%s|%s|%s|first" % (seed, glyph, strength)).encode("utf-8")) & 1
    up = (number % 2 == 1) == bool(first)
    size = rng.uniform(BASELINE_LEAST * reach, reach)
    return size if up else -size


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


def to_char(code):
    """A code point's character, or None (FontLab's Python is a narrow build: none above U+FFFF)."""
    try:
        return unichr(code)  # noqa: F821 (Python 2, FontLab's)
    except NameError:
        return chr(code)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# The tab (Qt and FontLab: in FontLab only)
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def has_designs(cmap, index, takes_turns):
    """Whether the font has an alternate a variant can be built from: a design beside the glyph
    (designs_of) of a letter, a figure, or a punctuation mark. cmap: {code point: glyph}; index:
    alternates_index(names); takes_turns(character)."""
    for code, glyph in cmap.items():
        if u"." in glyph or glyph not in index or not takes_turns(to_char(code)):
            continue
        if len(designs_of(glyph, index[glyph])) > 1:
            return True
    return False


def set_enabled(widget, on):
    """A control grayed out, or not, whatever its container's state. Auto Kerning's enable() sets a
    state only when it differs from the one the widget reports, and a widget reports its container's
    too: this tab's buttons are set while the font is read after a build, the window's lists
    disabled meanwhile, so a button to gray out read as grayed out already and came back clickable."""
    try:
        widget.setEnabled(bool(on))
    except Exception:
        pass


TIP_WIDTH, TIP_CHARACTER = 520, 7  # pixels: a tooltip's text at most (Font Check's width); about a character's


def tip_html(text):
    """A tooltip of rich text, which Qt wraps (plain text is shown on one line however long): in a
    one-cell table TIP_WIDTH wide when it would pass that (Qt's rich text takes a width from nothing
    else), as the dialog's own tooltips and Font Check's."""
    if len(re.sub(u"<[^>]*>", u"", text)) * TIP_CHARACTER > TIP_WIDTH:
        return u"<table width=\"%d\" cellspacing=\"0\" cellpadding=\"0\"><tr><td>%s</td></tr></table>" % (TIP_WIDTH, text)
    return u"<span>%s</span>" % text


def describe(widget, text, tip=False):
    """A control's What's This (rich text), and its tooltip too when asked; the widget."""
    try:
        widget.setWhatsThis(text)
        if tip:
            widget.setToolTip(tip_html(text))
    except Exception:
        pass
    return widget


def say(label, text):
    """A note's text, the note hidden while it says nothing: an empty label still took a line, a gap under
    the heading (image 198) and above the code's splitter handle (image 196)."""
    try:
        label.setText(text)
        label.setVisible(bool((u"%s" % (text or u"")).strip()))
    except Exception:
        pass


LIST_NOTE_MOST = 375  # characters: what the list's note may hold to stay on two lines at the window's first size


def list_note(varied, families, copy_button):
    """The note over the list, which fits two lines in a window of the size it opens at (the review of
    November 23, image 7: it ran to a third line for its last word; two lines held 400 characters there,
    so it keeps under LIST_NOTE_MOST). varied: how many families have alternates (bold alone: its noun
    is the next count's); families: the corpus's families, counted (bold with its noun: image 301);
    copy_button: the button's name, in italics."""
    return (u"<i>%s</i>: the glyphs fonts most often give a stylistic alternate (counted in %s of %s), those this "
            u"font has. To draw one by hand, tick a glyph, then click %s: it gets a copy named for a stylistic set "
            u"(a.ss01). <i>%s</i>: the glyphs <i>Variants that take turns</i> builds (picked by its <i>Glyphs</i> "
            u"dropdown), with no such copy." % (SUGGESTIONS_GROUP, varied, families, copy_button, SELECTED_GROUP))


def label_of(QtGui, text, what):
    """A setting's label with the What's This of the control beside it: a widget with none answers a
    right-click with its nearest container's, shown in that container's middle, over another control."""
    return describe(QtGui.QLabel(text), what)


def fit_combo(QtGui, combo):
    """A dropdown as wide as its widest item, never stretched across its row (image 239)."""
    try:
        combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
    except Exception:
        pass
    return combo


class AlternatesPage(object):
    """The tab's widgets and actions; owner: the Feature Code dialog (package, master, log, ak, run)."""

    def __init__(self, owner):
        QtCore, QtGui = _qt()
        self.owner, self.ak = owner, owner.ak
        self.model = load_model()
        # Two parts in a splitter, as the window's other tabs (image 259: this tab had no handle):
        # the suggestions' list, whose frame the handle is right under, then the variants
        self.parts = self.widget = QtGui.QSplitter(QtCore.Qt.Vertical)
        try:
            self.parts.setChildrenCollapsible(False)
        except Exception:
            pass
        layout = self.part(QtGui, 3)  # (the list the larger share: it held two rows at first, live)
        listed = (u"Two groups (click a group's arrow to close or open it). <i>%s</i>: the glyphs fonts most often "
                  u"give a stylistic alternate (counted in the open-licensed fonts of FreeLab's corpus: in how many "
                  u"families an ssXX, cvXX, or salt feature varies the character), those this font has, with the "
                  u"alternates it has already; to draw an alternate by hand, tick a glyph, then click <i>Make copies "
                  u"to redraw</i> (in the bottom row). <i>%s</i>: the glyphs the <i>Glyphs</i> dropdown below picks "
                  u"(at first the ticked suggestions), all ticked; <i>Build N variants</i> builds the variants of "
                  u"those ticked (untick one to leave it out). A column that means nothing for a row shows "
                  u"%s." % (SUGGESTIONS_GROUP, SELECTED_GROUP, NO_DATA))
        # (every label has a What's This of its own: one without answers with its container's: label_of). The
        # list holds both jobs' glyphs (image 302), so its heading names neither alone.
        layout.addWidget(describe(owner.heading(QtGui, LIST_HEADING), listed))
        self.note = QtGui.QLabel(u"")
        self.note.setWordWrap(True)
        describe(self.note, listed)
        layout.addWidget(self.note)
        self.note.setVisible(False)  # (shown with something to say: say)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels([u"Unicode", u"Glyph", u"Fonts with alternates", u"Current alternates"])
        self.tree.setRootIsDecorated(True)  # (its two groups close and open by their arrows)
        # Its rows as tall as the window's other lists': theirs are set by their pictures, and this list
        # drew none (text alone made rows half as high). Each row draws its glyph and its alternates.
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE * 3, ICON_SIZE))
        self.tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        self.tree.setWhatsThis(listed)
        self.ak.table_layout(self.tree)
        layout.addWidget(self.tree, 1)  # (the last of its part: the splitter's handle right under its frame)
        # The list's buttons and the two jobs' go in the window's bottom row (bottom_buttons), shown with
        # this tab: under the list, they stood between it and the next part (images 258 and 260)
        self.all_button = QtGui.QPushButton(u"Tick all")
        self.all_button.setWhatsThis(u"Ticks every glyph of the list, in both groups (with <i>The ticked suggestions</i> "
                                     u"picked, <i>%s</i> follows the suggestions)." % SELECTED_GROUP)
        self.none_button = QtGui.QPushButton(u"Untick all")
        self.none_button.setWhatsThis(u"Unticks every glyph of the list, in both groups: nothing to copy or build.")
        self.copy_button = QtGui.QPushButton(u"Make copies to redraw")
        self.copy_button.setWhatsThis(u"Adds a copy of each glyph ticked in <i>Suggestions</i>, named for the "
                                      u"next free stylistic set (a.ss01), its outlines as they are, to redraw by hand as "
                                      u"the alternate. The <i>Forms</i> tab then writes the set's feature. The variants "
                                      u"need no such copy. <i>Edit &gt; Undo</i> takes it back.")
        layout = self.part(QtGui, 2)
        try:  # a line between the two jobs: neither is a step of the other (and the heading no caption of the list)
            layout.addWidget(self.ak.separator())
        except Exception:
            pass
        what = (u"Computed copies of each glyph ticked in <i>Selected glyphs</i> (a letter's, a figure's, or a "
                u"punctuation mark's), changed a little as a whole (a slight rotation, uneven scaling, a slant, a baseline shift), named X.alt1, "
                u"X.alt2...: the first tab's <i>Alternates that take turns</i> then cycles them, so repeated glyphs "
                u"differ. They need no copy to redraw made first. The same seed makes the same variants; variants "
                u"built here are built again in place with another strength or seed.")
        # (no "(handwriting)" after it: image 244)
        layout.addWidget(describe(owner.heading(QtGui, u"Variants that take turns"), what))
        hint = describe(QtGui.QLabel(what), what)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        # What a click builds, or why nothing can be: with the paragraph over the settings, not under them
        # (image 245)
        self.scope_note = QtGui.QLabel(u"")
        self.scope_note.setWordWrap(True)
        describe(self.scope_note, u"What a click on <i>Build variants</i> would make: how many variants, of which "
                                  u"glyphs, how many replace variants built here with other settings, and how many "
                                  u"the font has already; or why nothing can be built, and what to choose instead.")
        layout.addWidget(self.scope_note)
        self.scope_note.setVisible(False)  # (shown with something to say: say)
        settings = QtGui.QHBoxLayout()
        what = (u"The glyphs that get variants, listed in the list's <i>Selected glyphs</i> group, all ticked (a new "
                u"pick replaces the last; untick a glyph there to leave it out): <i>The ticked suggestions</i>, those "
                u"ticked in <i>Suggestions</i> (a letter's, a figure's, or a punctuation mark's), kept in step as you "
                u"tick them; <i>Often doubled</i>, the glyphs that often stand doubled in "
                u"text (ll, ee, ss, tt; 00 and 99; marks doubled by convention, such as ..., !!, and --), whose "
                u"variants matter most; <i>These glyphs</i>, the glyphs of the characters typed in the box; every glyph "
                u"of one of the font's scripts (Latin, Cyrillic, and so on: letters, not figures or shared "
                u"punctuation); every lowercase letter, capital, or both; or <i>Everything</i>, every letter, "
                u"figure, and punctuation mark of the font. The line over these settings says how many glyphs "
                u"that is; a build too large for one click is refused there, before anything is made (a pick of "
                u"more than %s is not listed: one click could not build them all)." % grouped(SELECTED_MOST))
        # (label form, the same in every tool: a noun naming the setting, a colon, the control; image 271)
        settings.addWidget(label_of(QtGui, u"Glyphs:", what))
        self.scope_box = QtGui.QComboBox()
        self.scope_rows = scopes_for(())  # (the font's scripts join them once a font is read: show_scopes)
        for _, label in self.scope_rows:
            self.scope_box.addItem(label)
        self.scope_box.setCurrentIndex(0)
        self.scope_box.setWhatsThis(what)
        fit_combo(QtGui, self.scope_box)
        settings.addWidget(self.scope_box)
        self.letters_edit = QtGui.QLineEdit()
        self.letters_edit.setMaximumWidth(180)  # (room for TYPED_HINT, shown while its scope is picked: update_buttons)
        self.letters_edit.setWhatsThis(u"With <i>These glyphs</i>: the characters of the glyphs to vary, typed one "
                                       u"after another, with spaces or without (a g 0 !). The glyphs of the letters, "
                                       u"figures, and punctuation marks the font has are taken, and listed in "
                                       u"<i>Selected glyphs</i> as you type; anything else is passed over. Grayed out "
                                       u"with any other choice of <i>Glyphs</i>.")
        settings.addWidget(self.letters_edit)
        what = (u"How many variants each glyph ticked in <i>Selected glyphs</i> gets (X.alt1 to X.alt4 at most). One the font has already "
                u"is left as it is, and not built again (one built here with another strength or seed is built again "
                u"in place).")
        settings.addWidget(label_of(QtGui, u"Variants each:", what))
        self.count_box = QtGui.QSpinBox()
        self.count_box.setRange(1, 4)
        self.count_box.setValue(2)
        self.count_box.setWhatsThis(what)
        settings.addWidget(self.count_box)
        what = (u"How far each change may go: <i>Subtle</i> (within 0.8\N{DEGREE SIGN} of rotation, 2% of scale, "
                u"1\N{DEGREE SIGN} of slant, 0.5% of the em of baseline), <i>Moderate</i> (1.5\N{DEGREE SIGN}, 4%, "
                u"2\N{DEGREE SIGN}, 1%), or <i>Bold</i> (3\N{DEGREE SIGN}, 7%, 4\N{DEGREE SIGN}, 2%), to experiment "
                u"with. Changed after a build, the next <i>Build variants</i> builds the variants built here again "
                u"in place.")
        settings.addWidget(label_of(QtGui, u"Strength:", what))
        self.strength_box = QtGui.QComboBox()
        for _, label, rotation, scale, slant, rise in STRENGTHS:
            self.strength_box.addItem(label)
        self.strength_box.setWhatsThis(what)
        fit_combo(QtGui, self.strength_box)
        settings.addWidget(self.strength_box)
        what = (u"The number the variants' changes are drawn from: the same seed, strength, and glyph make the same "
                u"variant again; another seed, other variants. The preview at the right shows them before a build. "
                u"Changed after a build, the next <i>Build variants</i> builds the variants built here again in "
                u"place.")
        settings.addWidget(label_of(QtGui, u"Seed:", what))
        self.seed_box = QtGui.QSpinBox()
        self.seed_box.setRange(1, 9999)
        self.seed_box.setValue(1)
        self.seed_box.setWhatsThis(what)
        settings.addWidget(self.seed_box)
        what = (u"How far each variant may move up or down besides the strength's own shift: up to this many units, "
                u"at least a third as far. The variants take turns, one up and the next down, so each differs from "
                u"the one before; the first one's way and each move are drawn from the seed (the same seed, the "
                u"same moves). 0: none more.")
        settings.addWidget(label_of(QtGui, u"Baseline: \u00b1", what))
        self.baseline_box = QtGui.QSpinBox()
        self.baseline_box.setRange(0, BASELINE_MOST)
        self.baseline_box.setValue(0)
        # ("1 unit", "2 units": a fixed " units" read "1 units"; as Font Compare's threshold)
        counted_suffix = getattr(self.ak, "counted_suffix", None)
        if counted_suffix is not None:
            self.suffix_slot = counted_suffix(self.baseline_box, u"unit")
        else:
            self.baseline_box.setSuffix(u" units")
        self.baseline_box.setWhatsThis(what)
        settings.addWidget(self.baseline_box)
        self.designs_box = QtGui.QCheckBox(DESIGNS_LABEL)
        describe(self.designs_box, DESIGNS_WHAT)
        self.designs = False  # whether the font has an alternate to build from (has_designs), once read: fill()
        settings.addWidget(self.designs_box)
        settings.addStretch(1)
        layout.addLayout(settings)
        self.build_button = QtGui.QPushButton(u"Build variants")
        self.build_button.setWhatsThis(u"Adds the variants of the glyphs ticked in <i>Selected glyphs</i> (X.alt1 and "
                                       u"on; one the font "
                                       u"has already is left as it is, one built here with another strength or seed is "
                                       u"built again in place): its label and the line over the settings say how many, "
                                       u"of which glyphs. <i>Edit &gt; Undo</i> takes them back.")
        # Two previews side by side, a line between them (image 269): what the font has of the
        # glyph, and what would be built. Their captions are a preview's (ak.preview_caption: smaller, quiet;
        # image 246).
        previews = QtGui.QHBoxLayout()
        self.existing_caption, self.existing = self.caption_label(QtGui), QtGui.QLabel()
        self.preview_caption, self.preview = self.caption_label(QtGui), QtGui.QLabel()
        sides = ((self.existing_caption, self.existing,
                  u"The selected glyph (else the first ticked in <i>Selected glyphs</i>; nothing while none is) "
                  u"and the alternates the font has of it already, built variants among them."),
                 (self.preview_caption, self.preview,
                  u"The same glyph's variants as they would be built with these settings, each drawn from the "
                  u"design it is a copy of (a variant named W.ss01.alt2 is made of W.ss01); one the font has "
                  u"already is not built again, and is shown at the left, unless it was built here with another "
                  u"strength or seed: then it is built again, and shown here as it would be."))
        self.preview_line = None
        for at, (caption, picture, what) in enumerate(sides):
            if at:
                try:
                    self.preview_line = self.ak.separator(vertical=True)
                    previews.addWidget(self.preview_line)
                except Exception:
                    self.preview_line = None
            box = QtGui.QVBoxLayout()
            caption.setWordWrap(True)
            describe(caption, what)  # (the picture's own: its caption names the glyphs drawn)
            box.addWidget(caption)
            picture.setProperty(self.ak.LEAVE_ALONE_PROP, True)
            picture.setAlignment(QtCore.Qt.AlignCenter)
            picture.setMinimumHeight(PREVIEW_HEIGHT + 10)
            picture.setWhatsThis(what)
            box.addWidget(picture, 1)
            previews.addLayout(box, 1)
            caption.setVisible(False)  # (shown with a glyph drawn: draw_preview)
        # The previews take the part's spare height, drawn or empty (image 287: hidden, they left it to
        # the heading and the paragraph, which Qt spread into blank bands above and below the paragraph); the
        # part's foot is always the previews, right over the splitter's handle under it (convention 21)
        layout.addLayout(previews, 1)
        self.cmap, self.names = {}, set()  # the font's characters and names, as fill() read them
        self.index, self.in_scopes = {}, {}  # its alternates by glyph (alternates_index); each scope's glyphs, listed once
        self.codes, self.counts, self.found, self.icons = {}, {}, [], {}  # (fill: each glyph's code point, the
        # model's count by character, the suggestions, the rows' pictures drawn once a read)
        # Selected glyphs: the glyphs the last pick listed, those of them unticked, the pick they came from,
        # and how many the pick had (more than SELECTED_MOST: none listed)
        self.selected, self.selected_off, self.picked, self.pick_count = [], set(), None, 0
        self.refill_due = False  # (a refill asked from a row's tick: made on the next turn of the event loop)
        self.pace = None  # seconds a variant, from the session's last build of PACE_FROM or more
        # The variants this tab built, by font: {font key: {variant: (what it was as built, every master:
        # owner.glyph_print; (strength, seed))}}; those still as built are its own (own_variants, read with
        # the font: self.ours), replaced in place by a build with other settings
        self.built, self.ours = {}, {}
        self.slots = [lambda *args: self.make_copies(), lambda *args: self.build_variants(),
                      lambda *args: (self.draw_preview(), self.update_buttons()),
                      lambda *args: self.row_ticked(*args),
                      lambda *args: self.check_all(True), lambda *args: self.check_all(False),
                      lambda *args: self.picked_again(), lambda *args: self.row_picked(),
                      lambda: self.refill_now()]
        self.copy_button.connect("clicked()", self.slots[0])
        self.build_button.connect("clicked()", self.slots[1])
        self.all_button.connect("clicked()", self.slots[4])
        self.none_button.connect("clicked()", self.slots[5])
        self.scope_box.connect("currentIndexChanged(int)", self.slots[6])
        self.strength_box.connect("currentIndexChanged(int)", self.slots[2])
        for box in (self.count_box, self.seed_box, self.baseline_box):
            box.connect("valueChanged(int)", self.slots[2])
        self.designs_box.connect("toggled(bool)", self.slots[2])
        self.letters_edit.connect("textChanged(QString)", self.slots[6])
        self.tree.connect("itemSelectionChanged()", self.slots[7])
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", self.slots[3])

    def part(self, QtGui, stretch):
        """A part of the tab's splitter: its layout, to fill (stretch: its share of the height at first)."""
        widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        self.parts.addWidget(widget)
        try:
            self.parts.setStretchFactor(self.parts.indexOf(widget), stretch)
            widget.setProperty("freelabShare", stretch)  # (ak.share_splitters: the heights at first show)
        except Exception:
            pass
        return box

    def caption_label(self, QtGui):
        """A preview's caption (ak.preview_caption where the shared module has it)."""
        label = QtGui.QLabel(u"")
        make = getattr(self.ak, "preview_caption", None)
        if make is not None:
            try:
                make(label=label)
            except Exception:
                pass
        return label

    def bottom_buttons(self):
        """([the buttons for the left of the window's bottom row], [those for its right]): the list's Tick all
        and Untick all; the two jobs' Make copies to redraw and Build variants."""
        return [self.all_button, self.none_button], [self.copy_button, self.build_button]

    # -- reading ----------------------------------------------------------

    def font_maps(self):
        package = self.owner.package
        cmap, names = {}, set()
        for g in package.fgPackage.glyphs:
            names.add(u"%s" % g.name)
        cmap = self.ak.glyph_code_map(package.fgPackage.glyphs)  # (every code point of each glyph)
        return cmap, names

    def fill(self):
        """The list for the font open now: its suggestions, and the glyphs the Glyphs dropdown picks."""
        package = self.owner.package
        # The ticks kept for the same font read again (after a build, a copy, an undo): they went with the
        # list, and a new seed for the variants just built took ticking the glyphs again (image 270);
        # so are the selected glyphs unticked
        try:
            key = self.ak.font_key(package) if package is not None else None
        except Exception:
            key = None
        same = key is not None and key == getattr(self, "filled_key", None)
        ticked = set(self.checked_glyphs()) if same else set()
        if not same:
            self.selected_off, self.picked = set(), None
        self.filled_key = key
        self.cmap, self.names, self.codes, self.counts, self.found, self.icons = {}, set(), {}, {}, [], {}
        self.index, self.in_scopes, self.designs, self.ours = {}, {}, False, {}
        if package is not None:
            self.ours = self.own_variants(package)  # (read once per read of the font: each one's outlines are asked)
        if package is None:
            say(self.note, u"")
            self.show_scopes(())
            self.show_rows(ticked)
            self.draw_preview()
            self.update_buttons()
            return
        cmap, names = self.cmap, self.names = self.font_maps()
        for code, glyph in sorted(cmap.items()):
            self.codes.setdefault(glyph, code)  # (a glyph's first code point)
        self.index = alternates_index(names)
        self.designs = has_designs(cmap, self.index, self.takes_turns)
        self.show_scopes(font_scripts(ch for ch in (to_char(code) for code, glyph in cmap.items() if u"." not in glyph)
                                      if self.takes_turns(ch)))
        b = self.ak.b
        if self.model is None:  # (the variants still work: the suggestions alone are missing)
            say(self.note, u"The model (%s) is missing beside the script: reinstall FreeLab for the suggestions."
                % MODEL_FILE)
        else:
            rows, families, varied = self.model
            self.counts = dict(rows)
            self.found = suggestions(rows, cmap, names, index=self.index)
            if self.found:
                say(self.note, list_note(b(grouped(varied or 0)),
                                         b(counted(families or 0, u"open-licensed family", u"open-licensed families")),
                                         self.ak.i(u"Make copies to redraw")))
            else:  # (an empty list said nothing of why it was empty)
                say(self.note, u"The font has none of the glyphs fonts most often give a stylistic alternate: nothing "
                               u"to copy here. <i>%s</i>, the glyphs the variants below are built of, is another "
                               u"job." % SELECTED_GROUP)
        self.show_rows(ticked)
        for column in range(3):
            self.tree.resizeColumnToContents(column)
        self.draw_preview()
        self.update_buttons()

    # -- the list: Suggestions and Selected glyphs (image 302) ----------

    def group_rows(self, key):
        """The rows of a group of the list (SUGGESTIONS_KEY or SELECTED_KEY), in order."""
        QtCore = _qt()[0]
        try:
            for row in range(self.tree.topLevelItemCount):
                group = self.tree.topLevelItem(row)
                if u"%s" % group.data(0, QtCore.Qt.UserRole) == key:
                    return [group.child(at) for at in range(group.childCount())]
        except Exception:
            pass
        return []

    def group_of(self, item):
        """The key of a row's group, or None (a group's own row)."""
        QtCore = _qt()[0]
        try:
            parent = item.parent()
            return None if parent is None else u"%s" % parent.data(0, QtCore.Qt.UserRole)
        except Exception:
            return None

    def picture_of(self, names):
        """A row's picture of glyphs side by side (the dialog's picture, in its text color), drawn once a
        read; None where it cannot be drawn."""
        names = tuple(names)
        if names not in self.icons:
            picture = getattr(self.owner, "picture", None)
            icon = None
            try:
                drawn = picture(list(names)) if picture is not None and names else None
                if drawn is not None:  # (noted in its color: redrawn in the new one when dark mode switches)
                    QtGui = _qt()[1]
                    make = getattr(getattr(self.owner, "ak", None), "icon_of", None) or QtGui.QIcon
                    icon = make(drawn)
            except Exception:
                icon = None  # a row without its picture still reads
            self.icons[names] = icon
        return self.icons[names]

    def draw_row(self, item, glyph):
        """A row's pictures: its glyph's, and its alternates' (those the font has)."""
        QtCore = _qt()[0]
        alternates = list(self.index.get(glyph, ()))
        for column, drawn in ((1, [glyph]), (3, alternates)):
            icon = self.picture_of(drawn) if drawn else None
            if icon is not None:
                try:
                    item.setIcon(column, icon)
                except Exception:
                    pass
        try:
            item.setData(1, QtCore.Qt.UserRole, False)
            item.setToolTip(1, u"")
        except Exception:
            pass

    def add_group(self, QtCore, QtGui, key, title, count):
        """A group row, bold, its count in parentheses, as every grouped list's (no tick box: Tick all and
        Untick all tick its rows)."""
        item = QtGui.QTreeWidgetItem([group_title(title, count)])
        item.setData(0, QtCore.Qt.UserRole, key)
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        self.tree.addTopLevelItem(item)
        try:
            item.setFirstColumnSpanned(True)
        except Exception:
            pass
        self.ak.section_row(item, self.tree)
        return item

    def add_row(self, QtCore, QtGui, group, ch, glyph, families, alternates, on, drawn=True):
        """A glyph's row in a group: its character, its name (drawn), how many families vary it (NO_DATA
        where the model does not count it), and its alternates in the font (drawn)."""
        item = QtGui.QTreeWidgetItem([ch or NO_DATA, glyph, u"%d" % families if families is not None else NO_DATA,
                                      u" ".join(alternates) or NO_DATA])
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        item.setData(0, QtCore.Qt.UserRole, glyph)
        item.setTextAlignment(2, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
        group.addChild(item)
        if drawn:
            self.draw_row(item, glyph)
        else:  # (a whole script's rows drawn at once took seconds: the rest when clicked)
            item.setData(1, QtCore.Qt.UserRole, True)
            item.setToolTip(1, ROW_PICTURE_TIP)
        return item

    def show_rows(self, ticked=None):
        """The list made again: Suggestions (ticked: the suggestions to tick; else those ticked now), then
        Selected glyphs, the glyphs the dropdown picks (characters_in_scope), all ticked but those unticked
        since the pick (a new pick replaces the last, its glyphs all ticked). A group closed stays closed,
        the row selected stays selected, and the list keeps its place. Nothing with no font."""
        QtCore, QtGui = _qt()
        tree = self.tree
        if ticked is None:
            ticked = set(self.checked_glyphs())
        closed, chosen = set(), None
        try:
            for row in range(tree.topLevelItemCount):
                group = tree.topLevelItem(row)
                if not group.isExpanded():
                    closed.add(u"%s" % group.data(0, QtCore.Qt.UserRole))
            items = tree.selectedItems()
            if items:
                chosen = (self.group_of(items[0]), u"%s" % items[0].data(0, QtCore.Qt.UserRole))
        except Exception:
            pass
        try:
            place = tree.verticalScrollBar().value
        except Exception:
            place = None
        scope = self.scope()
        if scope != self.picked:  # (a new pick: its glyphs all ticked)
            self.selected_off, self.picked = set(), scope
        tree.blockSignals(True)  # (a row's first tick is no change to answer)
        try:
            tree.clear()
            self.selected, self.pick_count = [], 0
            if self.owner.package is None:
                return
            group = self.add_group(QtCore, QtGui, SUGGESTIONS_KEY, SUGGESTIONS_GROUP, len(self.found))
            for ch, glyph, count, alternates in self.found:
                self.add_row(QtCore, QtGui, group, ch, glyph, count, alternates, glyph in ticked)
            group.setExpanded(SUGGESTIONS_KEY not in closed)
            picked = self.characters_in_scope([glyph for _, glyph, _, _ in self.found if glyph in ticked])[0]
            self.pick_count = len(picked)
            if scope_problem(len(picked)) is None:
                self.selected = list(picked)
            group = self.add_group(QtCore, QtGui, SELECTED_KEY, SELECTED_GROUP, len(picked))
            for at, glyph in enumerate(self.selected):
                code = self.codes.get(glyph)
                ch = to_char(code) if code is not None else None
                self.add_row(QtCore, QtGui, group, ch, glyph, self.counts.get(ch), self.index.get(glyph, ()),
                             glyph not in self.selected_off, at < ROW_PICTURES)
            group.setExpanded(SELECTED_KEY not in closed)
            if chosen is not None:  # (the row selected before, selected again: the previews show it still)
                for item in self.group_rows(chosen[0]):
                    if u"%s" % item.data(0, QtCore.Qt.UserRole) == chosen[1]:
                        item.setSelected(True)
                        break
        finally:
            tree.blockSignals(False)
            if place is not None:
                try:
                    tree.verticalScrollBar().setValue(place)
                except Exception:
                    pass

    def picked_again(self):
        """The Glyphs dropdown or the typed characters changed: Selected glyphs lists the new pick."""
        try:
            if getattr(self.owner, "busy", False):
                return
            self.show_rows()
            self.draw_preview()
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def row_ticked(self, item=None, column=0):
        """A row's tick changed. In Selected glyphs: in or out of the build and the previews. In Suggestions:
        Selected glyphs follows while it lists the ticked suggestions, made again on the next turn of the
        event loop (never inside Qt's own signal, whose row the list's remaking deletes)."""
        try:
            QtCore = _qt()[0]
            key = self.group_of(item) if item is not None else None
            if key is None:
                return
            glyph = u"%s" % item.data(0, QtCore.Qt.UserRole)
            on = item.checkState(0) == QtCore.Qt.Checked
            if on:
                self.selected_off.discard(glyph)
            elif key == SELECTED_KEY:
                self.selected_off.add(glyph)
            if key == SUGGESTIONS_KEY and self.scope() == "checked":
                self.refill_later()
                return
            self.draw_preview()
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def refill_later(self):
        """show_rows on the next turn of the event loop (once, however many ticks ask meanwhile)."""
        if self.refill_due:
            return
        self.refill_due = True
        try:
            _qt()[0].QTimer.singleShot(0, self.slots[8])
        except Exception:
            self.refill_now()

    def refill_now(self):
        self.refill_due = False
        self.picked_again()

    def row_picked(self):
        """A row selected: drawn, where the list was too long to draw every row; the previews show it."""
        try:
            QtCore = _qt()[0]
            for item in self.tree.selectedItems():
                if item.data(1, QtCore.Qt.UserRole):
                    self.tree.blockSignals(True)  # (a picture set is no tick to answer)
                    try:
                        self.draw_row(item, u"%s" % item.data(0, QtCore.Qt.UserRole))
                    finally:
                        self.tree.blockSignals(False)
            self.draw_preview()
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def show_scopes(self, scripts):
        """The scope box's choices for the font read: a scope per script it has among them; the scope
        picked before stays picked where the font still has it."""
        key = self.scope()
        self.scope_rows = scopes_for(scripts)
        keys = [row[0] for row in self.scope_rows]
        box = self.scope_box
        box.blockSignals(True)
        try:
            box.clear()
            for _, label in self.scope_rows:
                box.addItem(label)
            box.setCurrentIndex(keys.index(key) if key in keys else 0)
        finally:
            box.blockSignals(False)

    def checked_glyphs(self):
        """The suggestions ticked (Make copies to redraw copies them; The ticked suggestions picks them)."""
        QtCore = _qt()[0]
        return [u"%s" % item.data(0, QtCore.Qt.UserRole) for item in self.group_rows(SUGGESTIONS_KEY)
                if item.checkState(0) == QtCore.Qt.Checked]

    def build_glyphs(self):
        """The glyphs ticked in Selected glyphs, in its order: those Build N variants builds, and the previews
        show."""
        return [glyph for glyph in self.selected if glyph not in self.selected_off]

    def check_all(self, on):
        """Every row of both groups ticked, or none (Tick all, Untick all); the previews and the build's count
        follow. While Selected glyphs lists the ticked suggestions, it follows them (its rows are not ticked
        twice)."""
        try:
            if getattr(self.owner, "busy", False):
                return
            follows = self.scope() == "checked"
            rows = self.group_rows(SUGGESTIONS_KEY) + ([] if follows else self.group_rows(SELECTED_KEY))
            self.tree.blockSignals(True)  # (one answer for the whole list, not one a row)
            try:  # (the log told how many it ticked or unticked, hidden ones said: report 118)
                self.ak.check_rows(rows, on, log=self.owner.log, command=u"Tick all" if on else u"Untick all",
                                   noun=u"glyph", hidden_text=(u"in a closed group", u"in closed groups"))
            finally:
                self.tree.blockSignals(False)
            if on:
                self.selected_off = set()
            elif not follows:
                self.selected_off = set(self.selected)
            if follows:
                self.show_rows()
            self.draw_preview()
            self.update_buttons()
        except Exception:
            pass  # a signal's handler must not raise

    def strength(self):
        return STRENGTHS[max(0, self.strength_box.currentIndex)][0]

    def scope(self):
        rows = self.scope_rows
        return rows[min(max(0, self.scope_box.currentIndex), len(rows) - 1)][0]

    def from_designs(self, glyphs=None):
        """Whether variants are built from the alternates the font has of a glyph too: the check box, where
        a glyph in scope (glyphs; else the scope's) has an alternate to build from. Without one the box is
        grayed out and counts as unticked, its tick left as the user set it (for other glyphs, or once an
        alternate is drawn or built)."""
        if not self.designs_box.checked:
            return False
        if glyphs is None:
            glyphs = self.build_glyphs() if self.owner.package is not None else []
        return designs_in(glyphs, self.index)

    def settings(self):
        """What a variant is built with besides its glyph, number, and design: (strength, seed), and the
        baseline's reach where it is not 0 (strength, seed, baseline)."""
        baseline = int(getattr(getattr(self, "baseline_box", None), "value", 0) or 0)
        return (self.strength(), int(self.seed_box.value)) + ((baseline,) if baseline else ())

    def plan(self, glyphs, names):
        """variants_planned for these glyphs with the settings shown: the variants this tab built with
        other settings (self.ours) planned again, to be replaced in place."""
        return variants_planned(glyphs, self.count_box.value, names, self.from_designs(glyphs), self.index,
                                self.ours, self.settings())

    def own_variants(self, package):
        """{variant: (strength, seed)} of the variants this tab built in this font that are still as a build
        left them (a glyph drawn over, or changed any other way, is the user's: never replaced). Asked of
        the dialog's glyph_print (each master's outlines and width); {} where it has none."""
        prints = getattr(self.owner, "glyph_print", None)
        if prints is None:
            return {}
        try:
            records = self.built.get(self.ak.font_key(package), {})
            masters = self.masters(package)
        except Exception:
            return {}
        found = {}
        for name, (built, settings) in records.items():
            try:
                if built is not None and prints(package, name, masters) == built:
                    found[name] = settings
            except Exception:
                continue
        return found

    def masters(self, package):
        get = getattr(self.owner, "build_masters", None)
        if get is not None:
            return get(package)
        try:
            return list(package.masters) or [package.master]
        except Exception:
            return [package.master]

    # -- making -----------------------------------------------------------

    def copy_glyph(self, source, name, matrix_of=None, replace=False):
        """A new glyph name, made of copies of source's shapes in every master that draws it (each changed by
        matrix_of(that master's layer), when given), with source's widths; the new glyph, or None (the current
        master does not draw it, or the font has a glyph of that name now: nothing is added). replace: the
        glyph name the font has (a variant built here) made again so, its layers emptied first (its name,
        and what uses it, stay); None where the font has no glyph of that name."""
        QtCore, QtGui = _qt()
        package, fontlab = self.owner.package, self.owner.fontlab
        glyph = package.findName(source)
        if glyph is None:
            return None
        # The name is asked of the font itself, at the moment of writing: the names read when the list was
        # made may be out of date, and FontLab would add a second glyph of the same name
        existing = package.findName(name)
        if (existing is not None) != bool(replace):
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
        if replace:
            made = existing
            for master in masters:
                layer = made.getLayerByName(master)
                if layer is not None:
                    layer.removeAllShapes()
        else:
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

    def problem(self, new, again, names):
        """build_problem for new variants, again of which replace variants built here (they add no glyph to
        the font, but take their time and their share of one click)."""
        return build_problem(new - again, len(names)) or build_problem(new, 0, self.pace)

    def update_buttons(self):
        """Each button grayed out when it has nothing to do (Make copies to redraw by the ticked suggestions,
        Build N variants by the ticked selected glyphs); the build button and the line over the settings say
        what a click builds."""
        try:
            QtCore = _qt()[0]
            has_font = self.owner.package is not None
            checked = self.checked_glyphs()
            set_enabled(self.copy_button, has_font and bool(checked))
            # Tick all and Untick all (both groups) grayed out when they would change nothing
            rows = self.group_rows(SUGGESTIONS_KEY) + self.group_rows(SELECTED_KEY)
            ticks = [item.checkState(0) == QtCore.Qt.Checked for item in rows]
            set_enabled(self.all_button, has_font and not all(ticks))
            set_enabled(self.none_button, has_font and any(ticks))
            typed = self.scope() == "typed"
            set_enabled(self.letters_edit, has_font and typed)
            set_enabled(self.scope_box, has_font)  # (no font: no glyph to pick, and no script to list)
            try:  # its words say what to type while it is used; grayed out, nothing, or n/a with no font
                self.letters_edit.setPlaceholderText(
                    (TYPED_HINT if typed else u"") if has_font else NO_FONT_FIELD)
            except Exception:
                pass
            glyphs, names = (self.build_glyphs(), self.names) if has_font else ([], set())
            # Grayed out while no glyph to build has an alternate to build from (it would change nothing), and
            # why; usable once one has, the variants built here among them (image 269)
            usable = has_font and designs_in(glyphs, self.index)
            set_enabled(self.designs_box, usable)
            if has_font and not usable:
                describe(self.designs_box, u"%s %s" % (DESIGNS_NONE, DESIGNS_WHAT), True)
            else:
                describe(self.designs_box, DESIGNS_WHAT)
                self.designs_box.setToolTip(u"")
            # How many, how strong, and from what seed say nothing while no glyph is to build (no font, or
            # nothing ticked or typed): grayed out until there is one, as the button is
            for box in (self.count_box, self.strength_box, self.seed_box, self.baseline_box):
                set_enabled(box, bool(glyphs))
            count, designs = self.count_box.value, self.from_designs(glyphs)
            plan = self.plan(glyphs, names)
            new = sum(len(variants) for _, variants in plan)
            again = sum(1 for _, variants in plan for name, _, _ in variants if name in names)
            # (refused here, before anything is made; a pick too large to list, first)
            problem = scope_problem(self.pick_count) or self.problem(new, again, names)
            label, line = build_words(plan, count, self.scope(), designs, problem, self.pace, again, len(self.selected))
            if not glyphs and self.pick_count > SELECTED_MOST:
                line = problem
            self.build_button.setText(label)
            say(self.scope_note, line if has_font else u"")
            set_enabled(self.build_button, has_font and new > 0 and not problem)
        except Exception:
            pass

    def make_copies(self):
        owner = self.owner
        package = owner.package
        chosen = self.checked_glyphs()
        if package is None or not chosen or getattr(owner, "busy", False) or not self.same_font():
            return
        cmap, names = self.font_maps()
        # (the font recorded first, for Undo to go back to; nothing is copied when FontLab could not record it)
        if not self.ak.begin_write(owner.fontlab, package, u"FreeLab Feature Code", owner.log):
            return
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
        status = self.ak.notify_changed(self.owner.fontlab, package, u"FreeLab Feature Code", touched)
        if made:
            one = len(made) == 1
            self.owner.log.add(u"Made %s: %s. Once drawn, the <i>Forms</i> tab writes %s%s." % (
                                   self.ak.b(self.ak.counted(len(made), u"copy to redraw", u"copies to redraw")),
                                   self.ak.glyph_name_links(made), u"its set" if one else u"their sets",
                                   status.undo(u"; <i>Edit &gt; Undo</i> takes %s back" % (u"it" if one else u"them"))),
                               "done")
        status.report(self.owner.log)
        if error is not None:
            self.owner.log.add(self.ak.error_sentence(u"Stopped by an error", error), "error")
        self.owner.run()

    def takes_turns(self, ch):
        """Whether a character is one the first tab's turns take: a letter, a figure, or a punctuation
        mark, as the dialog tells them (the same characters in both tabs, whatever the Python)."""
        return bool(ch) and len(ch) == 1 and self.owner.kind(ch) is not None

    def characters_in_scope(self, ticked=None):
        """(the glyphs the Glyphs dropdown picks, the font's names): the letters, figures, and punctuation
        marks ticked in Suggestions (ticked: those, where the list is being made again), those that often
        stand doubled in text, those typed in the box, a script's, a case's letters, or all of them; what
        Selected glyphs lists. The font as fill() read it (read once per font, not at every click), and a
        scope of the whole font listed once per font too."""
        cmap, names = self.cmap, self.names
        scope = self.scope()
        if scope == "checked":
            codes = self.codes or dict((glyph, code) for code, glyph in cmap.items())
            return [glyph for glyph in (self.checked_glyphs() if ticked is None else ticked)
                    if glyph in codes and self.takes_turns(to_char(codes[glyph])) and u"." not in glyph], names
        if scope == "typed":
            found = []
            for ch in u"%s" % self.letters_edit.text:
                glyph = cmap.get(ord(ch))
                if glyph and u"." not in glyph and self.takes_turns(ch) and glyph not in found:
                    found.append(glyph)
            return found, names
        if scope in self.in_scopes:
            return self.in_scopes[scope], names
        script = scope[len(SCRIPT_SCOPE):] if scope.startswith(SCRIPT_SCOPE) else None
        found = []
        for code, glyph in sorted(cmap.items()):
            ch = to_char(code)
            if not ch or u"." in glyph or not self.takes_turns(ch):  # (no character in scope above U+FFFF)
                continue
            if scope == "doubled":
                wanted = self.owner.doubled(ch)
            elif scope == "all":
                wanted = True
            elif script is not None:
                wanted = script_of(ch) == script
            else:
                wanted = in_scope(ch, scope)
            if wanted:
                found.append(glyph)
        self.in_scopes[scope] = found
        return found, names

    def build_variants(self):
        """The variants of the glyphs ticked in Selected glyphs added to the font, and those this tab built with
        other settings made again in place (image 270), as one step of its History; the window's top
        row counts them meanwhile (ak.busy_*: a write, never stopped half way)."""
        owner = self.owner
        package = owner.package
        if package is None or getattr(owner, "busy", False) or not self.same_font():
            return
        package = owner.package
        glyphs, names = self.build_glyphs(), self.names
        self.ours = self.own_variants(package)  # (asked of the font now: one drawn over since is the user's)
        count, settings, designs = self.count_box.value, self.settings(), self.from_designs(glyphs)
        strength, seed = settings[0], settings[1]
        baseline = settings[2] if len(settings) > 2 else 0
        plan = self.plan(glyphs, names)
        new = sum(len(variants) for _, variants in plan)
        problem = self.problem(new, sum(1 for _, variants in plan for name, _, _ in variants if name in names), names)
        if problem:  # (the button is grayed out with this sentence over it; a click that got through is refused too)
            owner.log.add(problem, "warning")  # (its own markup: bold counts, no text of the font's)
            return
        # (variants built before are changed in place: the font recorded first, for Undo to go back to)
        if not self.ak.begin_write(owner.fontlab, package, u"FreeLab Feature Code", owner.log):
            return
        upm = float(package.upm)
        made, kept, touched, built, replaced, others, error = 0, 0, [], [], [], 0, None
        built_of = set()  # (the glyphs given new variants)
        started = time.time()
        # (the window's top row counts them; a write, one step of FontLab's History: never stopped half way)
        owner.set_busy(True, u"Building variants", stoppable=False)
        try:
            for index, (glyph, variants) in enumerate(plan):
                owner.progress(u"Building variants", index, len(plan), stoppable=False)
                layer = package.findName(glyph).getLayerByName(package.master)
                if layer is None or not len(layer.shapes):
                    continue
                kept += count - len(variants)  # (those the font has already: left as they are)
                for name, number, source in variants:
                    again = name in self.ours and name in names
                    if package.findName(name) is not None and not again:  # (added since the list was read: left)
                        kept += 1
                        continue
                    params = variant_params(glyph, number, strength, seed, baseline, upm)

                    def matrix_of(master_layer, params=params):  # (around each master's own center)
                        center = master_layer.boundingBox.center()
                        return variant_matrix(params, center.x(), center.y(), upm)
                    # (a copy of one design: the glyph, or an alternate; a variant built here, made again in place)
                    made_glyph = self.copy_glyph(source, name, matrix_of, replace=again)
                    if made_glyph is not None:
                        touched.append(made_glyph)
                        (replaced if again else built).append(name)
                        made += 1
                        others += source != glyph and not again
                        if not again:
                            built_of.add(glyph)
            if touched:
                owner.progress(u"Adding the variants to FontLab's History", force=True, stoppable=False)
        except Exception as exc:
            error = exc
        finally:
            owner.set_busy(False)
        status = self.ak.notify_changed(self.owner.fontlab, package, u"FreeLab Feature Code", touched)
        self.record(package, built + replaced, settings)
        if made >= PACE_FROM:  # (what the next build's time is told from)
            self.pace = (time.time() - started) / made
        words = []
        if built:
            # (a few are named, each a link the log draws from its outlines; a whole alphabet's are counted)
            named = (u": %s" % self.ak.glyph_name_links(built)) if len(built) <= LINKED_MOST else u""
            words.append(u"Built %s of %s%s (%s, seed %d%s)." % (
                self.ak.b(self.ak.counted(len(built), u"variant")),
                self.ak.b(self.ak.counted(len(built_of), u"glyph")), named, strength,
                seed, (u", %s from the font's alternates" % self.ak.b(grouped(others))) if designs else u""))
        if replaced:
            named = (u": %s" % self.ak.glyph_name_links(replaced)) if len(replaced) <= LINKED_MOST else u""
            words.append(u"Built %s again in place%s (%s, seed %d): %s built here before with other settings." % (
                self.ak.b(self.ak.counted(len(replaced), u"variant")), named, strength, seed,
                u"it was" if len(replaced) == 1 else u"they were"))
        if made:
            words.append(u"The first tab's <i>Alternates that take turns</i> lists them, the glyphs that double most in "
                         u"text first: tick those to cycle, then write the code%s." % status.undo(
                             u"; <i>Edit &gt; Undo</i> takes %s back" % (u"it" if made == 1 else u"them")))
            self.owner.log.add(u" ".join(words), "done")
        status.report(self.owner.log)
        if kept:
            self.owner.log.add(u"%s the font has already, left as %s." % (
                self.ak.b(self.ak.counted(kept, u"variant")), u"it is" if kept == 1 else u"they are"), "warning")
        if error is not None:
            self.owner.log.add(self.ak.error_sentence(u"Stopped by an error", error), "error")
        self.owner.run()

    def record(self, package, names, settings):
        """The variants just built noted as this tab's (own_variants): what each is now, in every master,
        and the settings it was built with. Never raises."""
        prints = getattr(self.owner, "glyph_print", None)
        if prints is None or not names:
            return
        try:
            records = self.built.setdefault(self.ak.font_key(package), {})
            masters = self.masters(package)
        except Exception:
            return
        for name in names:
            try:
                records[name] = (prints(package, name, masters), settings)
            except Exception:
                records.pop(name, None)

    # -- preview ----------------------------------------------------------

    def preview_glyph(self):
        """The glyph the previews show: the selected row's (not one unticked in Selected glyphs: unticked, it
        is out of the preview as of the build), else the first glyph ticked in Selected glyphs, else none
        (image 296: with These glyphs and nothing typed, the previews showed a)."""
        QtCore, QtGui = _qt()
        for item in self.tree.selectedItems():
            key = self.group_of(item)
            glyph = u"%s" % item.data(0, QtCore.Qt.UserRole)
            if key is None or (key == SELECTED_KEY and glyph in self.selected_off):
                continue
            return glyph
        glyphs = self.build_glyphs()
        return glyphs[0] if glyphs else None

    def row_pixmap(self, shapes, upm):
        """Outlines side by side ((path, advance) each), in the dialog's text color."""
        QtCore, QtGui = _qt()
        scale = PREVIEW_HEIGHT / upm
        width = int(sum(advance for _, advance in shapes) * scale + 40)
        pixmap = QtGui.QPixmap(max(width, 10), PREVIEW_HEIGHT + 30)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.owner.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended whatever happens: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            x = 20.0
            for shape, advance in shapes:
                painter.save()
                painter.translate(x, PREVIEW_HEIGHT * 0.85)
                painter.scale(scale, -scale)
                painter.fillPath(shape, QtGui.QBrush(color))
                painter.restore()
                x += advance * scale
        finally:
            painter.end()
        inked = getattr(getattr(self.owner, "ak", None), "inked", None)  # (redrawn in the new color on a switch)
        return inked(pixmap, color) if inked is not None else pixmap

    def preview_parts(self, glyph):
        """What the two previews show of a glyph: ([the glyph and the font's alternates of it, as (name,
        None)], [the variants a build would add, as (name, number, the glyph it is a copy of)], how
        many more alternates the font has than are shown); a variant the font has already is among
        the first, not built again, unless this tab built it with other settings (then it is among both:
        as it is, and as it would be built again)."""
        names = self.names
        existing = [glyph] + alternates_of(glyph, names)
        planned = variants_planned([glyph], self.count_box.value, names, self.from_designs([glyph]),
                                   {glyph: existing[1:]}, self.ours, self.settings())[0][1]
        shown = existing[:NAMED_MOST + 1]
        return [(name, None) for name in shown], planned, len(existing) - len(shown)

    def show_previews(self, existing, planned):
        """The previews' captions shown while there is a glyph to draw (the right one's says when nothing is
        to build), else hidden; the pictures emptied when they have nothing to show, never hidden: they hold
        the part's spare height (image 287, blank bands between the heading and its paragraph while
        they were hidden), and the part ends with them, right over the splitter's handle under it. The line
        between them shows with the captions, only while a glyph is drawn (the shared preview_filled: with a
        font, the shared module showed it over two empty previews). Never raises."""
        for caption, picture, on in ((self.existing_caption, self.existing, existing),
                                     (self.preview_caption, self.preview, planned)):
            try:
                if not on:
                    picture.clear()
                picture.setVisible(True)
                if not existing:
                    caption.setText(u"")
                caption.setVisible(bool(existing))
            except Exception:
                pass
        # (the captions and the line between the previews: nothing shown over nothing, as in every tool)
        filled = getattr(self.ak, "preview_filled", None)
        if filled is not None:
            filled([self.existing_caption, self.preview_caption, self.preview_line], bool(existing))
        elif self.preview_line is not None:
            try:
                self.preview_line.setVisible(bool(existing))
            except Exception:
                pass

    def draw_preview(self):
        """The previews drawn again: at the left the letter with the alternates the font has of it, at
        the right its variants as they would be built."""
        QtCore, QtGui = _qt()
        try:
            package = self.owner.package
            glyph = self.preview_glyph() if package is not None else None
            found = package.findName(glyph) if glyph else None
            layer = found.getLayerByName(package.master) if found is not None else None
            if layer is None:
                self.show_previews(False, False)
                return
            upm = float(package.upm)
            existing, planned, more = self.preview_parts(glyph)
            shapes = []
            for name, _ in existing:
                other = package.findName(name)
                other_layer = other.getLayerByName(package.master) if other is not None else None
                if other_layer is not None:
                    shapes.append((self.ak.layer_path(other_layer), float(other_layer.advanceWidth) or upm * 0.6))
            self.existing.setPixmap(self.row_pixmap(shapes, upm))
            self.show_previews(True, bool(planned))
            self.existing_caption.setText(u"In the font: %s%s" % (
                u", ".join(name for name, _ in existing),
                (u", and %s" % counted(more, u"other")) if more else u""))
            shapes = []
            for name, number, source in planned:  # (each drawn from the design it would be a copy of)
                design = package.findName(source)
                design_layer = design.getLayerByName(package.master) if design is not None else None
                if design_layer is None:
                    continue
                center = design_layer.boundingBox.center()
                a, b, c, d, e, f = variant_matrix(variant_params(glyph, number, self.strength(), self.seed_box.value,
                                                                 self.baseline_box.value, upm),
                                                  center.x(), center.y(), upm)
                shapes.append((QtGui.QTransform(a, b, c, d, e, f).map(self.ak.layer_path(design_layer)),
                               float(design_layer.advanceWidth) or upm * 0.6))
            if planned:
                self.preview.setPixmap(self.row_pixmap(shapes, upm))
                self.preview_caption.setText(u"To build (%s, seed %d): %s" % (
                    strength_of(self.strength())[1], self.seed_box.value, u", ".join(row[0] for row in planned)))
            else:
                self.preview.clear()
                self.preview_caption.setText(u"Nothing to build of %s: the font has %s already (see left)." % (
                    glyph, u"this variant" if self.count_box.value == 1 else u"these variants"))
        except Exception:
            self.show_previews(False, False)
            for label in (self.existing, self.preview):
                try:
                    label.clear()
                except Exception:
                    pass
