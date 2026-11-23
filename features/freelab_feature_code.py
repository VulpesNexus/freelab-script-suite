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
- Alternates that take turns (calt): for a handwriting font, a letter, a figure, or a punctuation
  mark repeated within a few characters takes its next alternate (l, l.2, l, l.2...), so doubled and
  nearby characters do not look stamped. The nearest earlier form of the same character decides, and
  each looks back among its own kind only (letters among letters, figures among figures, punctuation
  marks among punctuation marks): a space, or a character of another kind, ends the look back. Its
  code sits in calt between FreeLab's own marker lines, and the rest of calt is kept. The characters
  that double most in text (ll, ee, ss, 00) are listed first; where more are checked than rules by
  character can serve in a font (a whole alphabet of built variants), each takes the form after the
  character before it instead, in a few rules on classes.
- Forms (the window's second tab): the features a font's glyph names call for. case (.case), locl
  (Romanian and Moldavian S and T with a comma below, by the font's code points; Catalan l.l; Dutch
  ij with acutes; the Turkic dotted i; any .loclXXX glyph, its language from the suffix and its
  script from the glyph's character; the language systems it needs go in the prefix), frac, numr,
  and dnom, sups, subs, and sinf, ordn, smcp and c2sc, lnum, onum, pnum, and tnum (the default
  figures' style read from their widths, ink, and forms; a tabular set whose figures differ in width
  is a warning row), and ss01 to ss20 and cv01 to cv99 with names. Each feature is a check box, each
  of its substitutions one more; a feature the font's code has by hand starts unchecked, as does one
  FontLab's automatic code already makes the same way. Each sits in its feature between FreeLab's
  marker lines; FontLab's automatic code for that feature is replaced and the feature handed back.
- Figure forms to build (under the forms): the numerators, denominators, superiors, inferiors, Unicode
  superscript and subscript figures, and ordinal indicators the font lacks, each a component of its
  figure (or a, o) scaled and moved as the open-licensed corpus places them (or as the font's own small
  figures), named as the font names its forms; built in one History step, then read as forms.

Shows the code before anything is written, checked by fontTools' feature parser.

Valid Python 2.7 (FontLab 7) and Python 3. The code generation below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import bisect
import json
import os
import re
import sys
import unicodedata

CHOICES = (("liga", "Standard (liga)"), ("dlig", "Discretionary (dlig)"), ("off", "Off"))
FEATURE_TITLES = {"liga": "Standard Ligatures", "dlig": "Discretionary Ligatures", "calt": "Contextual Alternates"}
BEGIN, END = u"# >>> FreeLab %s (made by FreeLab Feature Code)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
LISTS_EVERY_ALTERNATE = ("aalt", "salt")  # features that list alternates as a menu, not giving them a job
DEFAULT_LOOK_BACK = 2  # characters between a character and its earlier form, at most
TURN_RULES_MAX = 800  # rules of characters taking turns by character (a table each in the font); more: by position
TURN_BYTES_MAX = 48000  # bytes of GSUB the turns by position may need at most (its offsets reach 65,535)
CLASS_LINE_GLYPHS = 16  # glyph names to a line in a long class
DOUBLES_FILE = "alternates_model.json"  # beside this script: its "doubles", how often each character stands doubled in text
DOUBLES_OF = 300000  # the doubles are counted of this many pairs of characters
DOUBLE_OFTEN = 100  # a character doubled this often (ff: 300, jj: 141, 99: 112; ww: 20) is one that doubles in text
TURN_PICTURES = 120  # the characters whose cycles are drawn as the list is made; the rest when clicked
# What takes turns, each kind looking back among its own: the model's "kinds" names them so, and the
# classes of the code are named after them
LETTERS, FIGURES, PUNCTUATION = u"letters", u"figures", u"punctuation"
KINDS = (LETTERS, FIGURES, PUNCTUATION)
CATEGORY_KINDS = {u"L": LETTERS, u"N": FIGURES, u"P": PUNCTUATION}  # by a general category's first letter
TURN_PICTURE_TIP = u"Click the row to draw its forms."
ALTERNATE_SUFFIX = re.compile(r"^(?P<base>[^.]+)\.(?:(?P<number>[2-9])|alt(?P<alt>[0-9]*)|calt(?P<calt>[0-9]*))$")
# A variant built from one of a glyph's alternates (freelab_alternates.py: W.ss01.alt2, of W.ss01): the
# alternate's suffix is a stylistic one (a set, a character variant, salt, alt, calt, or a number), so
# a.sc.alt1, a small capital's alternate, stays out of a's turn
DESIGN_VARIANT = re.compile(r"^(?P<base>[^.]+)\.(?P<design>(?:ss|cv)[0-9]{2}|salt|c?alt[0-9]*|[0-9]+)\.alt(?P<alt>[0-9]+)$"
                            r"(?P<number>)(?P<calt>)")


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
        self.fixed = False  # the font's own code has its rule (font_owned): left where it is, never moved


def rules_of(text, tag):
    """[(input glyphs, output glyph, the feature it is in, FreeLab's)] of the simple ligature rules (sub a b
    by a_b;) of a feature's code given under tag (ligature_statements): the feature each rule stands in
    (another feature's code given under the tag stays that feature's: Codex review 7), and whether
    FreeLab may manage it (managed_rule)."""
    return [(rule[0], rule[1], rule[4] or tag, managed_rule(text, rule, tag)) for rule in ligature_statements(text)]


def font_outputs(text, tag):
    """{glyph: the feature it is in} of the outputs of the font's own substitutions in a feature's code
    given under tag: every "sub ... by X;" whatever its input (classes, named classes, escaped names,
    contexts), but those FreeLab manages (managed_rule: its own block's, FontLab's automatic plain ones)."""
    rules = ligature_statements(text)
    managed = set(rule[2] for rule in rules if managed_rule(text, rule, tag))
    found, stack, statement = {}, [], []
    for token in code_tokens(text):
        word = token[0]
        if word == u"{":
            words = [t[0] for t in statement]
            stack.append(words[1] if len(words) > 1 and words[0] == u"feature" else None)
            statement = []
        elif word == u"}":
            if stack:
                stack.pop()
            statement = []
        elif word == u";":
            words = [t[0] for t in statement]
            if words and words[0] in (u"sub", u"substitute") and u"by" in words and statement[0][1] not in managed:
                outputs = words[words.index(u"by") + 1:]
                glyph = outputs[0].strip(u"[]").lstrip(u"\\") if len(outputs) == 1 else u""
                if glyph and not glyph.startswith(u"@"):
                    features = [name for name in stack if name]
                    found.setdefault(glyph, features[-1] if features else tag)
            statement = []
        else:
            statement.append(token)
    return found


def ligatures(names, features, chars=None, model=None):
    """Every ligature of a font: the rules of its liga and dlig, then each glyph whose name joins
    glyphs of the font with _ (f_f_t: f f t; l_l.dlig: l l), in the feature its suffix names; with no
    suffix, in the one most of the corpus's families put it in (model: {characters: [liga families,
    dlig families]}, chars: {glyph: its character}), else dlig. features maps a tag to its code."""
    names = set(names)
    chars, counts_of = chars or {}, (model or {}).get("ligatures", {})
    found, seen = [], {}
    owned = {}  # {glyph: feature} of every output the font's own code makes, whatever its rule's input
    for tag in ("liga", "dlig"):
        text = features.get(tag)
        for parts, glyph, where, managed in rules_of(text, tag):
            if (parts, glyph) not in seen:
                seen[(parts, glyph)] = Ligature(glyph, parts, where, why=u"the font's own %s" % where)
                found.append(seen[(parts, glyph)])
            if not managed:  # (the font's own rule: left where it is, never moved, never written again)
                seen[(parts, glyph)].fixed = True
                seen[(parts, glyph)].now = seen[(parts, glyph)].choice = where
        for glyph, where in font_outputs(text, tag).items():
            owned.setdefault(glyph, where)
    # Codex review 8: a rule FreeLab does not read as a plain ligature (sub f [i i.alt] by f_i; a named class,
    # an escaped name, a context) still makes its output: that ligature is the font's, never written again
    for lig in found:
        if lig.glyph in owned and not lig.fixed:
            lig.fixed = True
            lig.now = lig.choice = owned[lig.glyph]
    made = set(glyph for _, glyph in seen)
    for name in sorted(names):
        stem, _, suffix = name.partition(u".")
        parts = stem.split(u"_")
        if name in made or len(parts) < 2 or not all(part in names for part in parts):
            continue
        if suffix in (u"liga", u"dlig") or (not suffix and name in owned):
            if name in owned:  # (the font's own rule makes it: shown where it is, left to the font)
                lig = Ligature(name, parts, owned[name], owned[name], u"the font's own %s (a rule of its own that "
                                                                      u"FreeLab does not rewrite)" % owned[name])
                lig.fixed = True
            else:
                lig = Ligature(name, parts, None, suffix, u"its name's .%s" % suffix)
            found.append(lig)
            continue
        if suffix:
            continue  # a form of a ligature (.sc, .ss01, .case) or a localized one (.loclNLD): its own feature's
        key = u"".join(chars.get(part) or u"\0" for part in parts)
        if u"\0" not in key and all(unicodedata.category(c).startswith(u"M") for c in key):
            continue  # marks stacked (tildecomb_acutecomb): ccmp's, not a ligature to set
        counts = counts_of.get(key) if u"\0" not in key else None
        if counts:
            choice = "liga" if counts[0] >= counts[1] else "dlig"
            total = counts[0] + counts[1]
            why = (u"the 1 corpus family with it puts it in %s" % choice) if total == 1 else (
                u"%d of the %d corpus families with it put it in %s" % (max(counts), total, choice))
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


# ---------------------------------------------------------------------------
# Feature code read by its tokens, never by lines (Codex reviews 4 to 6): a feature's braces, FreeLab's
# own blocks, FontLab's automatic code, and the substitutions FreeLab manages are found as statements and
# comments with their places in the text, wherever they stand on their lines. Feature Code, CJK Spacing,
# and CJK Vertical all write through these (the CJK tools load this script for them).
# ---------------------------------------------------------------------------

class FeatureCodeUnreadable(ValueError):
    """A feature's code FreeLab cannot read safely (its braces not found, or FreeLab's own markers not in
    pairs): nothing is written to it, and the font's code is never made again from nothing (which would
    drop the designer's rules)."""

    def __init__(self, tag, why=None):
        ValueError.__init__(self, u"%s: %s" % (tag, why or u"FreeLab cannot find where the feature's code begins "
                                                         u"and ends"))
        self.tag = tag


class _NothingWritten(Exception):
    """Raised inside FeatureCodeDialog.write when the font's code changed after the write began: nothing is set."""


def fea_tokens(text):
    """[(token, start, end)] of feature code, every one: comments (from # to the line's end) and quoted
    strings too (FEA_STATEMENT_TOKEN)."""
    return [(m.group(0), m.start(), m.end()) for m in FEA_STATEMENT_TOKEN.finditer(text or u"")]


def code_tokens(text):
    """[(token, start, end)] of feature code, its comments and quoted strings left out."""
    return [token for token in fea_tokens(text) if not token[0].startswith((u"#", u'"'))]


def same_code(a, b):
    """Whether two pieces of feature code say the same: the same tokens, comments (FreeLab's markers among them)
    and quoted strings included, whatever the spaces and line breaks around them and inside comments. FontLab may
    hand code back spaced otherwise than it was written; compared as raw text, a write offered "Update the code"
    at once, and the next one wrote the features again unchanged (owner's images 341, 363, and 365). A quoted
    string is compared as it is: its spaces are its text (a stylistic set's name, "Alternate  A", is not
    "Alternate A": adversarial review 11)."""
    def tokens(text):
        return [token if token.startswith(u'"') else re.sub(u"\\s+", u" ", token).strip()
                for token, _, _ in fea_tokens(text or u"")]
    return tokens(a) == tokens(b)


def comment_tokens(text):
    """[(comment, start, end)] of feature code's comments, each stripped, wherever it stands on its line."""
    return [(token.strip(), start, end) for token, start, end in fea_tokens(text) if token.startswith(u"#")]


def block_spans(text, begin, end, tag=u""):
    """[(start, end)] of FreeLab's blocks in text: a begin marker, then the end marker after it, each a
    comment wherever it stands (after code on its line too: "sub b by b.case; # <<< FreeLab forms" had
    been missed, and the block taken to run to the end of the text, the font's rules after it lost). A
    marker without its pair, or a block opened inside another, raises FeatureCodeUnreadable: what is
    FreeLab's cannot be told from what is not."""
    spans, opened = [], None
    for comment, start, stop in comment_tokens(text):
        if comment == begin:
            if opened is not None:
                raise FeatureCodeUnreadable(tag, u"FreeLab's block opens twice before it closes")
            opened = start
        elif comment == end:
            if opened is None:
                raise FeatureCodeUnreadable(tag, u"FreeLab's block closes without opening")
            spans.append((opened, stop))
            opened = None
    if opened is not None:
        raise FeatureCodeUnreadable(tag, u"FreeLab's block opens without closing")
    return spans


def without_blocks(text, begin, end, tag=u"", strict=True):
    """text without FreeLab's blocks (block_spans): each from its begin marker (the code before it on its
    line kept) to its end marker, and the line break after it where the block began its line. strict
    False (a reader's view): text as it is where the markers do not pair."""
    text = text or u""
    try:
        spans = block_spans(text, begin, end, tag)
    except FeatureCodeUnreadable:
        if strict:
            raise
        return text
    for start, stop in reversed(spans):
        line_start = text.rfind(u"\n", 0, start) + 1
        if not text[line_start:start].strip():
            start = line_start
            if text[stop:stop + 2] == u"\r\n":
                stop += 2
            elif text[stop:stop + 1] == u"\n":
                stop += 1
        text = text[:start] + text[stop:]
    return text


def block_text(text, begin, end):
    """What FreeLab's first block holds, between its markers (block_spans), or None (none, or markers not
    in pairs)."""
    try:
        spans = block_spans(text or u"", begin, end)
    except FeatureCodeUnreadable:
        return None
    if not spans:
        return None
    inner = text[spans[0][0]:spans[0][1]]
    first = inner.find(u"\n")
    if first < 0:
        return u""
    body = inner[first + 1:]
    cut = body.rfind(u"#")  # (the end marker: the span's last comment)
    body = body[:cut] if cut >= 0 else body
    return body if not body.strip() or body.endswith(u"\n") else body + u"\n"


def automatic_spans(text):
    """([(marker start, marker end, close start)], whether one is left open) of FontLab's automatic code:
    a "#> feature" comment, and the next "#<" comment, wherever they stand."""
    found, opened = [], None
    for comment, start, stop in comment_tokens(text):
        if opened is None and comment.startswith(FONTLAB_AUTO):
            opened = (start, stop)
        elif opened is not None and comment.startswith(u"#<"):
            found.append((opened[0], opened[1], start))
            opened = None
    return found, opened is not None


def handed_back(text, drop=False, tag=u""):
    """text with FontLab's automatic code handed back ("#> feature" becomes "#/> feature": FontLab no
    longer rewrites it); drop: what it held taken out too (FreeLab's block makes the same feature), its
    closing comment kept. A marker left open raises FeatureCodeUnreadable where its code would be dropped."""
    text = text or u""
    spans, open_left = automatic_spans(text)
    if drop and open_left:
        raise FeatureCodeUnreadable(tag, u"FontLab's automatic code opens without closing")
    for start, stop, close in reversed(spans):
        marker = text[start:stop].replace(FONTLAB_AUTO, FONTLAB_HANDED, 1)
        middle = u"\n" if drop else text[stop:close]
        text = text[:start] + marker + middle + text[close:]
    if open_left:  # (only handed back: what it holds is kept)
        at = text.rfind(FONTLAB_AUTO)
        text = text[:at] + FONTLAB_HANDED + text[at + len(FONTLAB_AUTO):]
    return text


def own_code(text, begin, end):
    """A reader's view of the font's own code in a feature: FreeLab's blocks taken out (as far as their
    markers pair) and what FontLab's automatic code holds (FreeLab's block replaces it), by tokens."""
    text = without_blocks(text, begin, end, strict=False)
    spans, _ = automatic_spans(text)
    for start, stop, close in reversed(spans):
        text = text[:stop] + u"\n" + text[close:]
    return text


def declares_features(tokens):
    """Whether code tokens declare a feature (a "feature" statement)."""
    start = True
    for token, _, _ in tokens:
        if start and token == u"feature":
            return True
        start = token in (u";", u"{", u"}")
    return False


def braces_balance(tokens):
    """Whether code tokens' braces close as they open, every one."""
    depth = 0
    for token, _, _ in tokens:
        depth += 1 if token == u"{" else -1 if token == u"}" else 0
        if depth < 0:
            return False
    return depth == 0


def feature_bounds(text, tag):
    """(where the code inside the feature's braces begins, where its closing brace is) as offsets in
    text, found by statements, not lines (Codex review 5: "feature locl { ... } locl;" on one line, a
    closing brace after the last rule, or a feature's keyword, tag, and brace on lines of their own, had
    no closing line, and the font's own code was made again from nothing, its rules lost); comments and
    strings skipped. "missing" where text has no such feature, None where its braces do not match."""
    tokens = code_tokens(text)
    start = True
    for i, (token, _, _) in enumerate(tokens):
        if start and token == u"feature" and i + 1 < len(tokens) and tokens[i + 1][0] == tag:
            at = i + 2
            if at < len(tokens) and tokens[at][0] == u"useExtension":
                at += 1
            if at >= len(tokens) or tokens[at][0] != u"{":
                return None
            depth = 0
            for j in range(at, len(tokens)):
                if tokens[j][0] == u"{":
                    depth += 1
                elif tokens[j][0] == u"}":
                    depth -= 1
                    if depth == 0:
                        if j + 2 < len(tokens) and tokens[j + 1][0] == tag and tokens[j + 2][0] == u";":
                            return tokens[at][2], tokens[j][1]
                        return None
            return None
        start = token in (u";", u"{", u"}")
    return "missing"


def insert_block(text, tag, block, first=False, title=None, blank=False, scoped=False):
    """text with block (lines) inside the feature tag's braces: before its closing brace, or first
    (after its opening brace, and the comments right after it, FreeLab's markers and FontLab's excepted);
    a brace that shares its line with code gets a line break beside it, the code itself kept as typed.
    Where text has no such feature: no code at all, the feature made (title: its comment line; blank: a
    blank line before its closing brace, as the ligature features had); other features only (Codex review
    6: the block went after them, at the top level, in no feature), the feature made after them, whole;
    code with no feature around it, its braces balanced, taken for the feature's body, the block at its
    end. Anything else (braces that do not match) raises FeatureCodeUnreadable. scoped: the block goes
    where the feature's default scope ends, before its first script, language, or lookupflag statement
    (scope_change), not after it, where its rules would take that scope."""
    text = text or u""
    bounds = feature_bounds(text, tag)
    tokens = code_tokens(text)
    if bounds == "missing" and not tokens:
        head = text.rstrip(u"\r\n") + u"\n" if text.strip() else u""
        text = head + u"feature %s {\n# %s\n%s} %s;" % (tag, title or tag, u"\n" if blank else u"", tag)
        bounds = feature_bounds(text, tag)
    elif bounds == "missing":
        if not braces_balance(tokens):
            raise FeatureCodeUnreadable(tag, u"its code's braces do not match")
        if not block:
            return text
        lines = u"\n".join(block)
        if declares_features(tokens):  # (another feature's code: this one made after it, whole)
            return text.rstrip(u"\r\n") + u"\nfeature %s {\n# %s\n%s%s\n} %s;" % (
                tag, title or tag, u"\n" if blank else u"", lines, tag)
        if first:
            return lines + u"\n" + text
        at = scope_change(text, None) if scoped else None
        if at is not None:
            return text_before(text, at, lines)
        return text.rstrip(u"\r\n") + u"\n" + lines  # (the feature's body)
    if not isinstance(bounds, tuple):
        raise FeatureCodeUnreadable(tag)
    opening, closing = bounds
    if not block:
        return text
    lines = u"\n".join(block)
    if first:
        end = text.find(u"\n", opening)
        rest = text[opening:end if end >= 0 else len(text)].strip()
        if 0 <= end < closing and (not rest or rest.startswith(u"#")):  # the brace ends its line
            while True:  # (past the comments that follow it)
                after = text.find(u"\n", end + 1)
                if after < 0 or after > closing:
                    break
                line = text[end + 1:after].strip()
                if not line.startswith(u"#") or line.startswith((u"#>", u"#/>", u"#<", u"# >>>")):
                    break
                end = after
            return text[:end + 1] + lines + u"\n" + text[end + 1:]
        return text[:opening] + u"\n" + lines + u"\n" + text[opening:]
    at = scope_change(text, tag) if scoped else None
    return text_before(text, closing if at is None else at, lines)


def text_before(text, at, lines):
    """text with lines before offset at: on the lines before it where what is there begins its line, else
    on lines of their own between the code and it (the code as typed)."""
    line_start = text.rfind(u"\n", 0, at) + 1
    if not text[line_start:at].strip():
        return text[:line_start] + lines + u"\n" + text[line_start:]
    return text[:at] + u"\n" + lines + u"\n" + text[at:]


def scope_change(text, tag):
    """Where the first script, language, lookupflag, or lookup statement of the feature tag stands right in
    it (its offset), or None: past it, a rule applies only so. tag None: a body with no feature around it."""
    tokens = code_tokens(text)
    if tag is not None:
        bounds = feature_bounds(text, tag)
        if not isinstance(bounds, tuple):
            return None
        tokens = [t for t in tokens if bounds[0] <= t[1] < bounds[1]]
    depth, start = 0, True
    for word, begin, _ in tokens:
        if depth == 0 and start and (word in SCOPING or word == u"lookup"):
            return begin  # (a lookup, referred to or defined there, may carry its lookupflag on: Codex review 8)
        depth += 1 if word == u"{" else -1 if word == u"}" else 0
        start = word in (u";", u"{", u"}")
    return None


GLYPH_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")
SCOPING = (u"script", u"language", u"lookupflag")  # statements after which a rule applies only so


def ligature_statements(text):
    """[(parts, glyph, start, end, feature, movable)] of feature code's simple ligature substitutions (sub f
    i by f_i; substitute too), found by statements wherever they stand (Codex review 6: read by whole lines,
    a compact "feature liga { sub f i by f_i; } liga;" was not seen). feature: the tag of the feature it
    stands in (None in a body with no feature around it; Codex review 7: another feature's rule had been
    taken for the one the text was given as). movable: the rule stands right in its feature, outside any
    lookup block, before any script, language, or lookupflag statement of its feature."""
    found, stack, statement, scoped = [], [], [], False
    for token in code_tokens(text):
        word = token[0]
        if word == u"{":
            words = [t[0] for t in statement]
            kind = words[0] if words else u""
            stack.append((kind if kind in (u"feature", u"lookup") else u"other",
                          words[1] if kind == u"feature" and len(words) > 1 else None))
            if kind == u"feature":
                scoped = False
            elif kind == u"lookup":
                scoped = True  # (past a lookup, its lookupflag may hold: Codex review 8)
            statement = []
        elif word == u"}":
            if stack:
                stack.pop()
            statement = []
        elif word == u";":
            words = [t[0] for t in statement]
            if words and (words[0] in SCOPING or words[0] == u"lookup"):
                scoped = True
            if words and words[0] in (u"sub", u"substitute") and u"by" in words:
                at = words.index(u"by")
                parts, outputs = words[1:at], words[at + 1:]
                if len(parts) >= 2 and len(outputs) == 1 and all(GLYPH_NAME.match(w) for w in parts + outputs):
                    kinds = [kind for kind, _ in stack]
                    feature = [name for kind, name in stack if kind == u"feature"]
                    movable = (not stack or kinds[-1] == u"feature") and u"lookup" not in kinds and \
                        u"other" not in kinds and not scoped
                    found.append((tuple(parts), outputs[0], statement[0][1], token[2],
                                  feature[-1] if feature else None, movable))
            statement = []
        else:
            statement.append(token)
    return found


def managed_rule(text, rule, tag):
    """Whether FreeLab manages a ligature rule (one of ligature_statements' of text, the code given under
    tag), or the font's own code has it. FreeLab never moves or takes out a rule the font's code wrote
    (Codex review 7: moved, it took the scope of where it went, and the next write lost it): it manages
    only the rules of its own block, and those of FontLab's automatic code in the feature of that tag,
    right in it (FontLab writes that code again from the glyph names; FreeLab's block replaces it)."""
    parts, glyph, start, stop, feature, movable = rule
    if (feature or tag) != tag:
        return False  # (another feature's: the font's)
    try:
        if any(begin <= start < end for begin, end in block_spans(text, BEGIN % "ligatures", END % "ligatures")):
            return True
    except FeatureCodeUnreadable:
        return False
    spans, _ = automatic_spans(text)
    return movable and any(marker_end <= start < close for _, marker_end, close in spans)


def remove_statements(text, spans):
    """text without the statements at spans [(start, end)]: a line left blank by them goes too."""
    for start, stop in sorted(spans, reverse=True):
        line_start = text.rfind(u"\n", 0, start) + 1
        line_end = text.find(u"\n", stop)
        line_end = len(text) if line_end < 0 else line_end
        if not (text[line_start:start] + text[stop:line_end]).strip():
            text = text[:line_start] + text[line_end + 1:]
        else:
            text = text[:start] + text[stop:]
    return text


def feature_text(tag, old, rules, block_name, managed=None):
    """A feature's code with FreeLab's block of rules in place: an older FreeLab block taken out, FontLab's
    automatic block handed back to you ("#/> feature") with the managed rules taken out of it (by default
    the block's own: FreeLab writes them now), everything else kept as it is, the font's own rules too.
    The block goes where the feature's default scope ends (before its first script, language, or
    lookupflag statement, else before its closing brace: Codex review 7, a rule written after a
    lookupflag took it). rules and managed: [(parts, glyph)]. Raises FeatureCodeUnreadable where the code
    cannot be read safely (readable: before and after, on a write that only takes a block out too)."""
    managed = set((tuple(parts), glyph) for parts, glyph in (rules if managed is None else managed))
    begin, end = BEGIN % block_name, END % block_name
    readable(old, tag)
    text = without_blocks(old, begin, end, tag)
    spans, _ = automatic_spans(text)
    taken = [(start, stop) for parts, glyph, start, stop, feature, movable in ligature_statements(text)
             if (parts, glyph) in managed and movable and (feature or tag) == tag
             and any(marker_end <= start < close for _, marker_end, close in spans)]
    text = handed_back(remove_statements(text, taken)).rstrip(u"\r\n")
    if not rules:
        if not code_tokens(text):  # (no code: the feature, empty, as a new one was)
            return insert_block(text, tag, [], title=FEATURE_TITLES.get(tag, tag), blank=True) + u"\n"
        readable(text, tag)
        return text + u"\n"
    block = [begin] + [u"  %s" % rule for rule in rule_lines(rules)] + [end]
    return insert_block(text, tag, block, title=FEATURE_TITLES.get(tag, tag), blank=True, scoped=True) + u"\n"


def readable(text, tag):
    """Raises FeatureCodeUnreadable unless a feature's code can be read safely: no code, the feature with
    its braces matched, another feature's code with its braces balanced, or a body with its braces
    balanced (Codex review 7: a write that only took FreeLab's block out had written back an unclosed
    "lookup Own {")."""
    bounds = feature_bounds(text, tag)
    if bounds is None or (bounds == "missing" and not braces_balance(code_tokens(text))):
        raise FeatureCodeUnreadable(tag, u"its code's braces do not match")


def refused_words(tags):
    """The sentence for features FreeLab leaves as they are (FeatureCodeUnreadable), or empty."""
    if not tags:
        return u""
    one = len(tags) == 1
    return (u"FreeLab leaves %s as %s: it cannot find where %s code begins and ends (the feature's braces), "
            u"so nothing of FreeLab's goes in. Check %s code in FontLab's Features panel." % (
                describe_list(sorted(set(tags))), u"it is" if one else u"they are",
                u"that feature's" if one else u"each one's", u"its" if one else u"their"))


def stuck_words(glyphs):
    """The sentence for ligatures set to another feature than the one the font's own code puts them in."""
    if not glyphs:
        return u""
    one = len(glyphs) == 1
    return (u"FreeLab does not move %s: the font's own code has %s rule, and FreeLab never moves or takes out "
            u"a rule the font wrote. %s where %s: move %s in FontLab's Features panel." % (
                describe_list(sorted(set(glyphs))), u"its" if one else u"each one's", u"It stays" if one else
                u"They stay", u"it is" if one else u"they are", u"it" if one else u"them"))


def ligature_texts(found, texts, refused=None, stuck=None):
    """{tag: new code} for liga and dlig: FreeLab's ligatures (those not the font's own: fixed) written in
    the block of the feature each is set to (none for Off), FontLab's automatic rules of them taken out.
    A feature is rewritten only where something of it changes. refused: as forms_texts' (a feature whose
    code FreeLab cannot read: neither is written). The font's own rules are never moved or written again
    (Codex review 7); stuck, when given, gets those set to another feature than theirs."""
    free = [lig for lig in found if not getattr(lig, "fixed", False)]
    if stuck is not None:
        stuck.extend(lig.glyph for lig in found if getattr(lig, "fixed", False) and lig.choice != lig.now)
    managed = [(lig.parts, lig.glyph) for lig in free]
    new = {}
    for tag in ("liga", "dlig"):
        rules = [(lig.parts, lig.glyph) for lig in free if lig.choice == tag]
        old = texts.get(tag)
        if rules or any(lig.now == tag for lig in free) or (BEGIN % "ligatures") in (old or u""):
            try:
                new[tag] = feature_text(tag, old, rules, "ligatures", managed)
            except FeatureCodeUnreadable:
                if refused is not None:
                    refused.append(tag)
                return {}  # (a rule moved out of one and not into the other would be lost: neither written)
    return new


def rule_lines(rules):
    """Ligature rules, longest first (a font's ffi before its ff), then alphabetical."""
    return [u"sub %s by %s;" % (u" ".join(parts), glyph)
            for parts, glyph in sorted(rules, key=lambda rule: (-len(rule[0]), rule[0], rule[1]))]


# ---------------------------------------------------------------------------
# Alternates that take turns
# ---------------------------------------------------------------------------

def load_kinds(path=None):
    """([each range's first code point], [(first, last, kind)]) of the model's "kinds": which characters
    are letters, figures, and punctuation marks (features/train/kinds.py: Unicode's general categories
    L, N, and P to U+FFFF, as ranges); None where the file or the table is missing."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), DOUBLES_FILE)
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        rows = []
        for kind in KINDS:
            for part in data["kinds"][kind].split():
                first, _, last = part.partition(u"-")
                rows.append((int(first, 16), int(last or first, 16), kind))
        rows.sort()
        return [row[0] for row in rows], rows
    except Exception:
        return None


_KINDS = []  # the kinds' table, read once (load_kinds), when a character's kind is first asked


def char_kind(ch, table=None):
    """What a character is, for taking turns: LETTERS, FIGURES, PUNCTUATION, or None (a space, a symbol, a
    combining mark, a character past U+FFFF). Read from the model's table, not asked of this Python:
    FontLab's Python 2.7 knows Unicode 5.2, where the section sign is a symbol and the letters encoded
    since are unassigned, so a font's list would differ between FontLab and the tests. Only without
    the table (a file missing beside the script) does unicodedata answer."""
    if not ch or len(ch) != 1 or ord(ch) > 0xFFFF:
        return None
    if table is None:
        if not _KINDS:
            _KINDS.append(load_kinds() or ())
        table = _KINDS[0]
    if not table:
        return CATEGORY_KINDS.get(unicodedata.category(ch)[:1])
    starts, rows = table
    at = bisect.bisect_right(starts, ord(ch)) - 1
    return rows[at][2] if at >= 0 and ord(ch) <= rows[at][1] else None


def glyph_kinds(names, codes):
    """{kind: [the font's glyphs of that kind]}, for KINDS: a glyph that is a character of the kind, or
    whose name's stem (before its first period) is one, or joins characters of the one kind with _
    (a.sc, f_f_t, nine.alt1, one.tf, hyphen.case, period_period_period). codes: {glyph: its code
    point}. What may stand between a character and its earlier form; a character that takes turns is
    always among its own kind's glyphs, whatever its name."""
    def kind_of(name):
        code = codes.get(name)
        return char_kind(unichr_(code)) if code else None

    found = dict((kind, []) for kind in KINDS)
    for name in names:
        stem = name.split(u".")[0]
        kind = kind_of(name) or kind_of(stem)
        if kind is None and stem:
            kinds = set(kind_of(part) for part in stem.split(u"_") if part)
            kind = kinds.pop() if len(kinds) == 1 else None
        if kind is not None:
            found[kind].append(name)
    return found


def alternate_sets(names, takes_turns):
    """{glyph: [its alternates, in order]}: X.2, X.3...; X.alt, X.alt1, X.alt2...; X.calt1...; and a
    variant the Stylistic alternates tab built from one of X's alternates, named after it (X.ss01.alt2:
    a changed copy of X.ss01, in X's turn), while the font has that alternate. takes_turns(glyph)
    says whether a glyph is one whose alternates may take turns (a letter's, a figure's, or a
    punctuation mark's)."""
    names = set(names)
    found = {}
    for name in names:
        match = ALTERNATE_SUFFIX.match(name)
        if not match:
            match = DESIGN_VARIANT.match(name)
            if not match or u"%s.%s" % (match.group("base"), match.group("design")) not in names:
                continue
        if match.group("base") not in names or not takes_turns(match.group("base")):
            continue
        number = match.group("number") or match.group("alt") or match.group("calt") or u"1"
        found.setdefault(match.group("base"), []).append((int(number), name))
    return dict((base, [name for _, name in sorted(forms)]) for base, forms in found.items())


def turn_rules(sets, look_back=DEFAULT_LOOK_BACK):
    """How many rules taking turns by character needs: per character, one per form and distance, less
    the last distance's rule for its last alternate."""
    return sum((len(forms) + 1) * (look_back + 1) - 1 for forms in sets.values())


def turn_bytes(sets):
    """The most room taking turns by position needs in the font's GSUB table, in bytes: per step of the
    turn, a substitution of each character that has it (4 bytes each) and the two lists of glyphs its
    rule reads (2 bytes a glyph each, where the compiler finds no ranges to shorten them)."""
    deepest = max([len(forms) for forms in sets.values()] or [0])
    return sum(8 * sum(1 for forms in sets.values() if len(forms) >= step) for step in range(1, deepest + 1))


def turn_mode(sets, look_back=DEFAULT_LOOK_BACK):
    """How the characters take turns: "letter" (by character: each looks back for its own earlier form)
    while that takes TURN_RULES_MAX rules at most, else "position" (each takes the form after the
    character before it), whose code grows with the alternates' count, not with characters times forms
    times distances; "none" for no character."""
    if not sets:
        return "none"
    return "letter" if turn_rules(sets, look_back) <= TURN_RULES_MAX else "position"


def coverage_bytes(glyphs, order):
    """The room a list of glyphs needs in GSUB, in bytes: 2 a glyph, or 6 a run of glyphs that follow
    one another in the font (order: {glyph: its number in the font}), whichever is less (the two forms
    a compiler writes such a list in)."""
    numbers = sorted(order[glyph] for glyph in glyphs if glyph in order)
    runs = sum(1 for at, number in enumerate(numbers) if not at or number != numbers[at - 1] + 1)
    return min(2 * len(numbers), 6 * runs)


def context_bytes(sets, letters, others, order, mode):
    """The room the turns' rules need for the glyphs that may stand before a glyph taking turns: per kind
    with such a glyph, the class its rules read (by position, @..._turn_0: the kind's glyphs but the
    alternates cycled; by glyph, the kind's every glyph). turn_bytes does not count it: a few
    thousand bytes for an alphabet, but more than a table's offsets reach for the ideographs of a CJK
    font whose glyphs do not follow one another (fontTools itself stopped at 48,000 letters in a
    font of 65,000 glyphs in a shuffled order; in the font's order, 17,900 glyphs took 12 KB in all)."""
    others = others or {}
    kind_of = dict((glyph, kind) for kind in KINDS[1:] for glyph in others.get(kind, ()))
    total = 0
    for kind in KINDS:
        bases = [base for base in sets if kind_of.get(base, LETTERS) == kind]
        if not bases:
            continue
        around = set(glyph for glyph in letters if glyph not in kind_of) if kind == LETTERS else set(others[kind])
        around.update(bases)
        cycled = set(form for base in bases for form in sets[base])
        total += coverage_bytes(around - cycled if mode == "position" else around | cycled, order)
    return total


def turn_problem(sets, look_back=DEFAULT_LOOK_BACK, context=0):
    """Why the characters' turns cannot be written (their tables would not fit the offsets of GSUB,
    which the compiler FontLab uses does not work around), or None. context: context_bytes, the room
    of the glyphs that may stand before, where the caller knows the font's glyph order."""
    mode = turn_mode(sets, look_back)
    if mode == "position" and turn_bytes(sets) > TURN_BYTES_MAX:
        return (u"%s taking turns need more room than one feature's tables have (about %s of %s bytes): "
                u"untick some glyphs" % (counted(len(sets), u"glyph"), grouped(turn_bytes(sets) + context),
                                          grouped(TURN_BYTES_MAX)))
    if mode != "none" and context + (turn_bytes(sets) if mode == "position" else 0) > TURN_BYTES_MAX:
        return (u"the glyphs that may stand before a glyph taking turns need more room than one feature's tables "
                u"have (about %s of %s bytes with the turns, in this font's glyph order): the turns cannot be "
                u"written for a font this large unless those glyphs follow one another in the font" % (
                    grouped(context + (turn_bytes(sets) if mode == "position" else 0)), grouped(TURN_BYTES_MAX)))
    return None


def class_lines(name, glyphs, indent=u""):
    """A glyph class's definition, a few names to a line (a font's every letter on one line is slow to
    show and to scroll)."""
    if len(glyphs) <= CLASS_LINE_GLYPHS:
        return [u"%s%s = [%s];" % (indent, name, u" ".join(glyphs))]
    lines = [u"%s%s = [" % (indent, name)]
    for start in range(0, len(glyphs), CLASS_LINE_GLYPHS):
        lines.append(u"%s  %s" % (indent, u" ".join(glyphs[start:start + CLASS_LINE_GLYPHS])))
    lines.append(u"%s];" % indent)
    return lines


def cycle_code(sets, letters, look_back=DEFAULT_LOOK_BACK, class_prefix=u"FreeLab", mode=None, others=None):
    """calt code for characters whose alternates take turns. letters: every letter glyph of the font
    (alternates and ligatures of letters included), what may stand between and before a letter.
    others: {FIGURES: the font's figure glyphs, PUNCTUATION: its punctuation glyphs} (glyph_kinds), what
    may stand between and before a figure and a punctuation mark; a glyph in neither is a letter's.

    Each kind looks back among its own only, in rules and classes of its own: 1001 and 99 vary their
    figures, ... and !! and -- their marks, and a letter's turns are what they were before figures
    and punctuation took turns (a hyphen, an apostrophe, or a figure between two letters still ends the
    look back, so each word starts afresh). One class of every kind would have made l'l and e-e vary
    where they did not, and, by position, a word after an opening quotation mark start on its first
    alternate. The letters' classes keep their names (@FreeLab_letters, @FreeLab_turn_1), so the code a
    font has for its letters is the code written again.

    By character (mode "letter": what turn_mode picks while the rules are few): a character whose
    nearest earlier form (within look_back glyphs of its kind between) is form i takes form i + 1 (back
    to the character after its last alternate). One class of the kind serves every rule: the nearest
    form wins because a character's rules are written nearest first, and its last alternate's rule
    stops the look back there (an "ignore"), so no class of "the letters but this one's forms" is
    needed per letter (4,400 names times 1,100 letters made 56 MB of code, and a list of glyphs of its
    own per rule in the font).

    By position (mode "position"): a character takes the form after the form of the character of its
    kind before it, whichever that is (the character itself after a plain one, or after a form it has
    no next of). One rule per kind and step of the turn, on classes: a few thousand bytes for a whole
    alphabet where by character takes a table per character, form, and distance, more than GSUB's
    16-bit offsets reach; FontLab's compiler stops there ("coverage section too large")."""
    if not sets:
        return []
    mode = mode or turn_mode(sets, look_back)
    name = u"%s_take_turns" % class_prefix
    others = others or {}
    kind_of = dict((glyph, kind) for kind in KINDS[1:] for glyph in others.get(kind, ()))
    lines, rules = [], []
    for kind in KINDS:
        bases = sorted(base for base in sets if kind_of.get(base, LETTERS) == kind)
        if not bases:
            continue
        around = set(glyph for glyph in letters if glyph not in kind_of) if kind == LETTERS else set(others[kind])
        if mode == "position":
            stem = class_prefix if kind == LETTERS else u"%s_%s" % (class_prefix, kind)
            cycled = set(form for base in bases for form in sets[base])
            deepest = max(len(sets[base]) for base in bases)
            lines.extend(class_lines(u"@%s_turn_0" % stem, [glyph for glyph in sorted(around | set(bases))
                                                            if glyph not in cycled]))
            last = None
            for step in range(1, deepest + 1):
                having = [base for base in bases if len(sets[base]) >= step]
                if having != last:  # (the characters with this step: named once while they stay the same)
                    source = u"@%s_%s_%d" % (class_prefix, kind, step)
                    lines.extend(class_lines(source, having))
                    last = having
                lines.extend(class_lines(u"@%s_turn_%d" % (stem, step), [sets[base][step - 1] for base in having]))
                rules.append(u"  sub @%s_turn_%d %s' by @%s_turn_%d;" % (stem, step - 1, source, stem, step))
            continue
        between_class = u"@%s_%s" % (class_prefix, kind)
        lines.extend(class_lines(between_class, sorted(around | set(bases) | set(f for b in bases for f in sets[b]))))
        for base in bases:
            forms = [base] + list(sets[base])
            for between in range(look_back + 1):
                gap = u"".join(u"%s " % between_class for _ in range(between))
                for index, earlier in enumerate(forms):
                    if index + 1 < len(forms):
                        rules.append(u"  sub %s %s%s' by %s;" % (earlier, gap, base, forms[index + 1]))
                    elif between < look_back:  # back to the character, which it is: farther forms not looked at
                        rules.append(u"  ignore sub %s %s%s';" % (earlier, gap, base))
    return lines + [u"lookup %s {" % name] + rules + [u"} %s;" % name]


def used_in(names, texts):
    """{glyph: [tags]} of the glyphs the font's code names already (outside FreeLab's blocks): an
    alternate the designer gave a job (a standalone I) is not one to take turns."""
    found = {}
    for tag, text in sorted(texts.items()):
        if tag in LISTS_EVERY_ALTERNATE:
            continue
        kept = strip_block(text, "alternates")
        tokens = set(re.findall(r"[A-Za-z0-9_.]+", u"\n".join(line.split(u"#")[0] for line in kept.splitlines())))
        for name in names:
            if name in tokens:
                found.setdefault(name, []).append(tag)
    return found


def load_doubles(path=None):
    """{character: how often it stands doubled in text, of DOUBLES_OF pairs of characters}, from the
    model's "doubles" (features/train/doubles.py: the totals of andre-fuchs/kerning-pairs, the most
    among its 24 languages; letters, figures, and punctuation marks); empty where the file or the list
    is missing."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), DOUBLES_FILE)
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        return dict((u"%s" % ch, int(count)) for ch, count in data.get("doubles") or [])
    except Exception:
        return {}


def load_typed_doubles(path=None):
    """The punctuation marks doubled by convention, a set, from the model's "doubles_typed"
    (features/train/doubles.py: those whose double or triple Unicode encodes as one character, the
    period, the exclamation and question marks, the prime; and TeX's -- and ''); empty where the file
    or the list is missing."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), DOUBLES_FILE)
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
        return set(u"%s" % ch for ch in data.get("doubles_typed") or [])
    except Exception:
        return set()


def double_count(ch, doubles):
    """How often a character stands doubled in text; a capital as often as its small letter (text set
    in capitals doubles the same letters)."""
    if not ch:
        return 0
    return max(doubles.get(ch, 0), doubles.get(small(ch), 0))


def small(ch):
    """A capital's small letter, where that letter's capital is this one. Python 2 (FontLab's) lowers the
    dotted capital I to a plain i, and Python 3 to two characters: neither is the letter that doubles."""
    lower = ch.lower()
    return lower if lower.upper() == ch or lower == ch else ch


def doubles_often(ch, doubles, pairs=None, typed=None):
    """Whether a character often stands doubled in text: counted DOUBLE_OFTEN times or more; else, a
    letter or a figure whose pair is among Auto Kerning's common pairs (pairs: {pair: rank}, which also
    has kana, Armenian, and Georgian), and a punctuation mark doubled by convention (typed:
    load_typed_doubles). The common pairs do not speak for punctuation: they hold what fonts kern, and
    their doubled marks are the markup of the text counted (}}, {{, )), //, and two backslashes), as is
    the mark the counts double most (}}, 85); no mark is counted DOUBLE_OFTEN times (.. 72, -- 47, !!
    under 1)."""
    if not ch:
        return False
    if double_count(ch, doubles) >= DOUBLE_OFTEN:
        return True
    if char_kind(ch) == PUNCTUATION:
        return ch in (typed or ())
    return ch + ch in (pairs or {}) or small(ch) * 2 in (pairs or {})


def turn_order(bases, chars, doubles, pairs=None, typed=None):
    """The characters with alternates, those that double most in text first: the often doubled ones by
    their count (then by their pair's rank among the common pairs), then the rest by their count, then
    by name. chars: {glyph: its character}."""
    pairs = pairs or {}

    def key(base):
        ch = chars.get(base) or u""
        rank = min(pairs.get(ch + ch, len(pairs)), pairs.get(small(ch) * 2, len(pairs))) if ch else len(pairs)
        return (0 if doubles_often(ch, doubles, pairs, typed) else 1, -double_count(ch, doubles), rank, base)

    return sorted(bases, key=key)


def double_words(ch, doubles, pairs=None, typed=None):
    """(a list cell's word, its tooltip) for how often a character stands doubled in text."""
    if not ch:
        return u"", u""
    count = double_count(ch, doubles)
    pair = ch + ch
    counted_so = u"%s: about %d of every %s pairs of characters in text, in the language that doubles it most." % (
        pair, count, grouped(DOUBLES_OF))  # ("about 1 of every 300,000 pairs": the same words for any count)
    if count >= DOUBLE_OFTEN:
        return u"Often", counted_so
    if doubles_often(ch, doubles, pairs, typed):
        if char_kind(ch) == PUNCTUATION:
            return u"Often", u"%s is a mark doubled by convention (as ..., !!, ??, --, and '' are)." % pair
        return u"Often", u"%s is among the pairs common in text." % pair
    if count:
        return u"Seldom", counted_so
    return u"Seldom", u"%s was not found among the pairs counted in text." % pair


def grouped(number):
    """300000 as 300,000."""
    digits = u"%d" % number
    parts = []
    while len(digits) > 3:
        parts.insert(0, digits[-3:])
        digits = digits[:-3]
    return u",".join([digits] + parts)


def first_turns(sets, order, often, taken, look_back=DEFAULT_LOOK_BACK):
    """The characters that start checked to take turns: every one whose alternates have no other job
    (taken: those that have one), while they all fit turns by character; else only those that often
    stand doubled in text (often), which need the turns most, and the rest are a check away."""
    free = [base for base in order if base not in taken]
    if turn_mode(dict((base, sets[base]) for base in free), look_back) != "position":
        return set(free)
    chosen = [base for base in free if base in often]
    return set(chosen) if chosen else set(free)


def turns_written(sets, calt):
    """The characters taking turns in the font's calt already (those with an alternate named in FreeLab's
    block of it): they start checked, so the font's own code is what the window first shows."""
    block = freelab_block("calt", calt, "alternates")
    if not block:
        return set()
    tokens = set(re.findall(r"[A-Za-z0-9_.\-]+", block))
    return set(base for base, forms in sets.items() if any(form in tokens for form in forms))


def plain(text):
    """A note as a list's cell shows it: a cell draws markup as typed (<i>Glyphs</i>), so the tags go and
    the escaped characters come back."""
    text = re.sub(r"</?[A-Za-z][A-Za-z0-9]*\s*/?>", u"", u"%s" % (text or u""))
    return text.replace(u"&lt;", u"<").replace(u"&gt;", u">").replace(u"&amp;", u"&")


def calt_text(old, code_lines):
    """calt's code with FreeLab's alternates block (code_lines) in it, the rest kept."""
    kept = feature_text("calt", old, [], "alternates")
    if not code_lines:
        return kept
    # (before the feature's closing brace found by statements: the first "} calt;" in the text, a comment's
    # included, was taken for it)
    block = [BEGIN % "alternates"] + [u"  " + line for line in code_lines] + [END % "alternates"]
    return insert_block(kept.rstrip(u"\n"), "calt", block) + u"\n"


def freelab_block(tag, text, block_name):
    """FreeLab's block of a feature's code, alone in a feature of its own (what check_code checks:
    the rest of the code may name classes FontLab keeps outside it), or None."""
    inner = block_text(text, BEGIN % block_name, END % block_name)  # (its markers found as comments)
    if inner is None:
        return None
    return u"feature %s {\n%s} %s;\n" % (tag, inner, tag)


def own_code_refusal(ak, package, texts, prefix=None, names=None):
    """Why the code must not be written (the shared feature_code_refusal: the new errors it would bring
    the font, by Feature Check), or None, as there: also when the shared module predates it."""
    refusal = getattr(ak, "feature_code_refusal", None)
    if refusal is None:
        return None
    try:
        return refusal(package, texts, prefix, names)
    except Exception:
        return None


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
# Forms: case, locl, fractions and figures, small capitals, stylistic sets
# ---------------------------------------------------------------------------

FORMS = "forms"  # FreeLab's block in each form feature
EMPTIED_UNDO = u"; Edit > Undo puts it back"  # (said of a form left empty, when FontLab's History recorded the build)
LANGUAGES_BLOCK = "languages"  # and in the prefix, the language systems locl needs
FORM_TITLES = {
    "locl": u"Localized Forms", "case": u"Case-Sensitive Forms", "frac": u"Fractions", "numr": u"Numerators",
    "dnom": u"Denominators", "sups": u"Superscript", "subs": u"Subscript", "sinf": u"Scientific Inferiors",
    "ordn": u"Ordinals", "smcp": u"Small Capitals", "c2sc": u"Small Capitals From Capitals",
    "lnum": u"Lining Figures", "onum": u"Oldstyle Figures", "pnum": u"Proportional Figures",
    "tnum": u"Tabular Figures"}
SET_TAGS = tuple(u"ss%02d" % n for n in range(1, 21)) + tuple(u"cv%02d" % n for n in range(1, 100))
FORM_ORDER = ("aalt", "locl", "case", "frac", "numr", "dnom", "sups", "subs", "sinf", "ordn", "smcp", "c2sc",
              "lnum", "onum", "pnum", "tnum") + SET_TAGS  # (locl first: the forms it makes are the ones the others see)
FORM_TITLES["aalt"] = u"Access All Alternates"
# Features whose alternates aalt gathers (one glyph for another): what InDesign and Illustrator offer as
# a selected character's alternates, in place and in their Glyphs panel. Contextual features (frac,
# ordn), locl (one language's), and ligatures are not alternates.
ALTERNATE_FEATURES = ("case", "smcp", "c2sc", "pcap", "c2pc", "unic", "lnum", "onum", "pnum", "tnum", "zero",
                      "sups", "subs", "sinf", "numr", "dnom", "salt", "swsh", "cswh", "titl", "hist", "ornm",
                      "nalt") + SET_TAGS
# An ASCII character and the spacing accent drawn for text that look alike: each offered as the other's
# alternate (the character stays: a search still finds the tilde typed).
ASCII_VARIANTS = ((0x7E, 0x2DC, u"tilde"), (0x5E, 0x2C6, u"circumflex"), (0x60, 0x2CB, u"grave accent"),
                  (0x22, 0x2DD, u"double acute"), (0x27, 0x2B9, u"prime"))
for _tag in SET_TAGS:
    FORM_TITLES[_tag] = (u"Stylistic Set %d" if _tag.startswith(u"ss") else u"Character Variant %d") % int(_tag[2:])
LOCL_SUFFIX = re.compile(r"^locl([A-Z]{3,})$")
LANGUAGE_ALIASES = {"VIET": "VIT"}  # (Glyphs' suffix for Vietnamese; VIT is its OpenType tag)
UNI_NAME = re.compile(r"^(?:uni([0-9A-F]{4})|u([0-9A-F]{4,6}))$")
LANGUAGE_NAMES = {
    "AZE": u"Azerbaijani", "BEL": u"Belarusian", "BGR": u"Bulgarian", "BSH": u"Bashkir", "CAT": u"Catalan",
    "CHU": u"Chuvash", "CRT": u"Crimean Tatar", "CSY": u"Czech", "DAN": u"Danish", "DEU": u"German",
    "ELL": u"Greek", "ESP": u"Spanish", "FRA": u"French", "GAG": u"Gagauz", "GUA": u"Guarani", "HIN": u"Hindi",
    "IPPH": u"Phonetic", "ISL": u"Icelandic", "ITA": u"Italian", "KAZ": u"Kazakh", "KOK": u"Konkani",
    "KSM": u"Kildin Sami", "KUR": u"Kurdish", "LSM": u"Lule Sami", "MAH": u"Marshallese", "MAR": u"Marathi",
    "MKD": u"Macedonian", "MOL": u"Moldavian", "NAV": u"Navajo", "NEP": u"Nepali", "NLD": u"Dutch",
    "NSM": u"Northern Sami", "PLK": u"Polish", "PTG": u"Portuguese", "ROM": u"Romanian", "RUS": u"Russian",
    "SAN": u"Sanskrit", "SKS": u"Skolt Sami", "SRB": u"Serbian", "SVE": u"Swedish", "TAT": u"Tatar",
    "TKM": u"Turkmen", "TRK": u"Turkish", "UKR": u"Ukrainian", "VIT": u"Vietnamese"}
LANGUAGE_SCRIPT = {"BEL": "cyrl", "BGR": "cyrl", "CHU": "cyrl", "MKD": "cyrl", "RUS": "cyrl", "SRB": "cyrl",
                   "UKR": "cyrl", "ELL": "grek", "HIN": "dev2", "MAR": "dev2", "NEP": "dev2", "SAN": "dev2",
                   "KOK": "dev2"}  # the script of a language whose form is no letter (a middle dot)
SCRIPT_TAGS = (("LATIN", ("latn",)), ("CYRILLIC", ("cyrl",)), ("GREEK", ("grek",)), ("ARMENIAN", ("armn",)),
               ("GEORGIAN", ("geor",)), ("HEBREW", ("hebr",)), ("ARABIC", ("arab",)), ("DEVANAGARI", ("dev2", "deva")),
               ("BENGALI", ("bng2", "beng")), ("GURMUKHI", ("gur2", "guru")), ("GUJARATI", ("gjr2", "gujr")),
               ("TAMIL", ("tml2", "taml")), ("TELUGU", ("tel2", "telu")), ("KANNADA", ("knd2", "knda")),
               ("MALAYALAM", ("mlm2", "mlym")), ("THAI", ("thai",)), ("KHMER", ("khmr",)), ("LAO", ("lao ",)))
TURKIC_I = ("TRK", "AZE", "CRT", "KAZ", "TAT", "BSH", "GAG")  # dotted i stays dotted in capitals and small capitals
ROMANIAN = ("ROM", "MOL")  # S and T take a comma below, where the text has the cedilla's code point
CEDILLA_LANGUAGES = {0x015E: ("TRK", "AZE", "CRT", "GAG", "KAZ", "TAT", "TKM", "KUR"),
                     0x015F: ("TRK", "AZE", "CRT", "GAG", "KAZ", "TAT", "TKM", "KUR"),
                     0x0162: ("GAG",), 0x0163: ("GAG",)}  # the languages that write these with a cedilla
COMMA_BELOW = ((0x015E, 0x0218), (0x015F, 0x0219), (0x0162, 0x021A), (0x0163, 0x021B))  # (cedilla, comma below)
CEDILLA_NAMES = {0x015E: ("Scedilla", "uni015E"), 0x015F: ("scedilla", "uni015F"), 0x0162: ("Tcedilla", "uni0162"),
                 0x0163: ("tcedilla", "uni0163")}  # (an unencoded glyph by these names: the cedilla form)
DUTCH_J = (("j", 0xED, ("jacute", "uni006A0301", "j_acutecomb", "jacute.loclNLD")),
           ("J", 0xCD, ("Jacute", "uni004A0301", "J_acutecomb", "Jacute.loclNLD")))
TURKISH_I_FORMS = ("i.loclTRK", "idotaccent", "i.loclAZE")
TURKISH_SMALL_I = ("i.sc.loclTRK", "i.loclTRK.sc", "Idotaccent.sc", "idotaccent.sc", "uni0130.sc", "i.smcp.loclTRK",
                   "i.loclTRK.smcp", "idotaccent.smcp")
NUMR_SUFFIXES, DNOM_SUFFIXES = ("numr", "numerator"), ("dnom", "denominator")
SUPS_SUFFIXES, SUBS_SUFFIXES = ("sups", "superior"), ("subs", "inferior", "inf", "sinf")
SINF_SUFFIXES = ("sinf", "inferior", "inf", "subs")
NOT_SUPERSCRIPT = (0xAA, 0xBA)  # ordinal indicators: ordn's
# Figure suffixes: (spacing, style), None where it is the default figures': .tf tabular lining, .lf
# proportional lining, .osf proportional oldstyle, .tosf tabular oldstyle (Glyphs' names); .tnum,
# .pnum, .lnum, and .onum change one of the two
FIGURE_SUFFIXES = (("tf", ("tab", "lin")), ("tlf", ("tab", "lin")), ("lf", ("prop", "lin")), ("plf", ("prop", "lin")),
                   ("osf", ("prop", "old")), ("posf", ("prop", "old")), ("tosf", ("tab", "old")),
                   ("tnum", ("tab", None)), ("pnum", ("prop", None)), ("lnum", (None, "lin")), ("onum", (None, "old")))
SPACING_WORDS = {"tab": u"tabular", "prop": u"proportional"}
STYLE_WORDS = {"lin": u"lining", "old": u"oldstyle"}
DIGITS = u"0123456789"


def char_name(char):
    try:
        return unicodedata.name(char)
    except (ValueError, TypeError):
        return u""


def scripts_of(char, language=None):
    """The OpenType script tags of a character (two for the Indic scripts: the new shaper's and the old
    one's); for a character of no script (a middle dot), the language's, else latn."""
    words = char_name(char).split() if char else []
    for word, tags in SCRIPT_TAGS:
        if word in words[:2]:
            return tags
    return (LANGUAGE_SCRIPT.get(language, "latn"),)


def forms_index(names):
    """{suffix: {base: form}}: each glyph named as another glyph of the font plus one more suffix,
    wherever that suffix stands (a.sc.ss01 is a.sc's ss01 and a.ss01's sc)."""
    have = set(names)
    found = {}
    for name in sorted(have):
        parts = name.split(u".")
        if len(parts) < 2 or not parts[0]:
            continue
        for index in range(1, len(parts)):
            base = u".".join(parts[:index] + parts[index + 1:])
            if base in have and parts[index]:
                found.setdefault(parts[index], {}).setdefault(base, name)
    return found


class FontInfo(object):
    """What the form builders read of a font: its glyph names, their code points, and where known
    their advance widths, ink bounds ((x0, y0, x1, y1), y up), and contours' boxes (for a set's name)."""

    def __init__(self, names, codes=None, widths=None, bounds=None, contours=None):
        self.names = [name for name in names if name]
        self.has = set(self.names)
        self.codes = {}
        for name, value in (codes or {}).items():
            values = list(value) if isinstance(value, (list, tuple)) else [value]
            values = [v for v in values if v]
            if values and name in self.has:
                self.codes[name] = values
        self.glyph_of = {}  # character: the first glyph (in the font's order) that has it
        for name in self.names:
            for code in self.codes.get(name, ()):
                self.glyph_of.setdefault(unichr_(code), name)
        self.index = forms_index(self.names)
        self.widths, self.bounds, self.contours = widths or {}, bounds or {}, contours or {}

    def char_of(self, name):
        """A glyph's character: its own code point, else its name's first part's (a.sc: a), or None."""
        codes = self.codes.get(name)
        if codes:
            return unichr_(codes[0])
        stem = name.split(u".")[0]
        if stem != name and self.codes.get(stem):
            return unichr_(self.codes[stem][0])
        match = UNI_NAME.match(stem)
        if match:
            return unichr_(int(match.group(1) or match.group(2), 16))
        return None

    def glyph(self, code):
        return self.glyph_of.get(unichr_(code))

    def form(self, base, suffixes):
        """base's form by the first of the suffixes it has (base.suffix, or the suffix among base's own)."""
        for suffix in suffixes:
            form = self.index.get(suffix, {}).get(base)
            if form:
                return form
        return None

    def figures(self):
        """The default figures' glyphs, 0 to 9 (None where the font has none)."""
        return [self.glyph_of.get(digit) for digit in DIGITS]


class FormRule(object):
    """One row of a form feature: a substitution, or a warning to review (never written)."""

    def __init__(self, key, glyphs, source, target, note=u"", line=None, warning=False, on=True, **data):
        self.key, self.glyphs, self.source, self.target = key, list(glyphs), source, target
        self.note, self.line, self.warning = note, line, warning
        self.on = self.first_on = on and not warning
        self.data = data


class FormFeature(object):
    """A form feature the font's glyphs call for: its rows, the code their checked ones make, and how
    it stands in the font now (kind: "none", "fontlab" for FontLab's automatic code only, "freelab", or
    "hand")."""

    def __init__(self, tag, rules, make, note=u"", name=None):
        self.tag, self.rules, self.make, self.note = tag, rules, make, note
        self.name = self.first_name = name  # a set's name (ssNN, cvNN), or None
        self.hand_name = None  # a name the font's code gives the set already
        self.kind, self.kind_note = "none", u""
        self.on = self.first_on = True

    def title(self):
        return FORM_TITLES.get(self.tag, self.tag)

    def checked(self):
        return [rule for rule in self.rules if rule.on and not rule.warning]

    def lines(self):
        """The code of FreeLab's block, from the checked rows (none: no block)."""
        rules = self.checked()
        if not rules:
            return []
        lines = []
        if self.tag in SET_TAGS and self.name and not self.hand_name:
            lines.extend(name_lines(self.tag, self.name))
        return lines + self.make(rules, self)


def lookup_lines(name, lines):
    return [u"lookup %s {" % name] + [u"  " + line for line in lines] + [u"} %s;" % name]


def make_singles(rules, feature):
    """One lookup of the rows' single substitutions."""
    return lookup_lines(u"FreeLab_%s" % feature.tag, [rule.line for rule in rules])


def single_rules(pairs):
    """Rows for [(source, target, note)]."""
    return [FormRule(source, [source, target], source, target, note, u"sub %s by %s;" % (source, target))
            for source, target, note in pairs]


def fea_string(text):
    """text as a feature file's name string: quotes and backslashes and non-ASCII as Windows escapes."""
    out = []
    for char in text:
        code = ord(char)
        if 32 <= code < 127 and char not in u'"\\':
            out.append(char)
        else:
            out.append(u"\\%04X" % code)  # (a narrow Python's characters past U+FFFF are its surrogate pairs already)
    return u"".join(out)


def name_lines(tag, name):
    """A stylistic set's or a character variant's name, as its feature gives it to applications."""
    if tag.startswith(u"ss"):
        return [u'featureNames { name "%s"; };' % fea_string(name)]
    return [u"cvParameters {", u'  FeatUILabelNameID { name "%s"; };' % fea_string(name), u"};"]


# -- Case-sensitive forms ------------------------------------------------------------

def case_feature(info):
    pairs = [(base, form, u"") for base, form in sorted(info.index.get("case", {}).items())
             if u".case" not in u"." + base + u"."]
    if not pairs:
        return None
    return FormFeature("case", single_rules(pairs), make_singles,
                       u"Capitals' forms of punctuation and marks (on for text in capitals, in apps that switch "
                       u"it on with All Caps).")


# -- Localized forms -----------------------------------------------------------------

def language_label(tag):
    return u"%s %s" % (tag, LANGUAGE_NAMES.get(tag, u""))


def suffix_languages(tag):
    """The OpenType language tags a .loclXXX suffix names: one (VIET read as VIT), or several known
    ones run together (loclMARNEP: MAR and NEP)."""
    tag = LANGUAGE_ALIASES.get(tag, tag)
    if len(tag) > 4 and len(tag) % 3 == 0:
        parts = [tag[i:i + 3] for i in range(0, len(tag), 3)]
        if all(part in LANGUAGE_NAMES for part in parts):
            return parts
    return [tag] if len(tag) <= 4 else []


def locl_rule(info, language, kind, line, glyphs, source, target, note=u""):
    """A locl row: its language, kind (a lookup each), and scripts (from its first glyph's character)."""
    char = info.char_of(glyphs[0]) if glyphs else None
    scripts = scripts_of(char, language)
    return FormRule(u"%s %s %s" % (language, u" ".join(glyphs[:-1]), glyphs[-1]), glyphs,
                    u"%s: %s" % (language, source), target, note, line, language=language, kind=kind,
                    scripts=scripts)




def own_languages(text):
    """{(script, language)} a feature's own code sets with its script and language statements (outside
    FreeLab's block, and outside FontLab's automatic code, which FreeLab's block replaces). A feature
    sets a language once: the feature compiler stops at a second "language CAT;" under the same script
    (owner's report 153: Bellefair's own locl sets CAT, MOL, and ROM, and FreeLab's block beside it set
    CAT again, "language-specific behavior already specified")."""
    # (FreeLab's block and FontLab's automatic code found as comments wherever they stand: own_code)
    kept = [own_code(text, BEGIN % FORMS, END % FORMS)]
    # Read by statements, not by lines (Codex review 4: "script latn; language CAT; sub ...;" on one line,
    # a tag on the line after its keyword, or two language statements on one line, were missed, and
    # CAT was set again): comments and quoted strings skipped, a keyword counted only where a statement
    # starts (after ;, {, or }), its tag the next word wherever it stands
    found, script, start, want = set(), "DFLT", True, None
    for match in FEA_STATEMENT_TOKEN.finditer(u"\n".join(kept)):
        token = match.group(0)
        if token.startswith((u"#", u'"')):
            continue
        if want is not None:
            if token not in (u";", u"{", u"}"):
                tag = token.strip()
                if want == "script":
                    script = tag
                elif tag != "dflt":
                    found.add((script, tag))
            want = None
        elif start and token in (u"script", u"language"):
            want = token
        start = token in (u";", u"{", u"}")
    return found


# A feature's code as tokens: a comment, a quoted string, a statement's end or a brace, or a word (a run of
# anything else but white space)
FEA_STATEMENT_TOKEN = re.compile(u'#[^\\n]*|"[^"]*"?|[;{}]|[^\\s;{}#"]+')


def locl_feature(info, taken=()):
    """The locl rows the font's glyphs call for. taken: the (script, language) pairs the font's own locl
    code sets already (own_languages): a row of one is shown, never written (FreeLab's block cannot set
    that language again), its rule left to the font's code."""
    rules, handled = [], set()

    # Romanian and Moldavian: S and T with a comma below, where the text has the cedilla's code point
    for cedilla_code, comma_code in COMMA_BELOW:
        cedilla, comma = info.glyph(cedilla_code), info.glyph(comma_code)
        if cedilla and comma and cedilla != comma:
            for language in ROMANIAN:
                rules.append(locl_rule(info, language, "single", u"sub %s by %s;" % (cedilla, comma), [cedilla, comma],
                                       cedilla, comma, u"U+%04X, written with a cedilla elsewhere, takes the comma "
                                       u"below (U+%04X)" % (cedilla_code, comma_code)))
        elif cedilla and cedilla == comma:
            # One glyph for both code points (an old Romanian encoding): the cedilla's languages take
            # the font's unencoded cedilla form, where it has one
            own = [name for name in CEDILLA_NAMES[cedilla_code] if name in info.has and name not in info.codes]
            if own:
                for language in CEDILLA_LANGUAGES[cedilla_code]:
                    rules.append(locl_rule(info, language, "single", u"sub %s by %s;" % (cedilla, own[0]),
                                           [cedilla, own[0]], cedilla, own[0],
                                           u"%s has both U+%04X and U+%04X: this language takes the cedilla" % (
                                               cedilla, cedilla_code, comma_code)))

    # Catalan: l·l, with the font's own middle dot between two l's, or as ŀl
    dot, small_l, cap_l = info.glyph(0xB7), info.glyph(0x6C), info.glyph(0x4C)
    if dot and small_l and u"periodcentered.loclCAT" in info.has:
        cat_dot = u"periodcentered.loclCAT"
        handled.add(cat_dot)
        rules.append(locl_rule(info, "CAT", "context", u"sub %s %s' %s by %s;" % (small_l, dot, small_l, cat_dot),
                               [small_l, dot, small_l, cat_dot], u"%s %s %s" % (small_l, dot, small_l), cat_dot,
                               u"the middle dot of l·l"))
        if cap_l:
            cap_dot = info.form(cat_dot, ("case",)) or cat_dot
            rules.append(locl_rule(info, "CAT", "context", u"sub %s %s' %s by %s;" % (cap_l, dot, cap_l, cap_dot),
                                   [cap_l, dot, cap_l, cap_dot], u"%s %s %s" % (cap_l, dot, cap_l), cap_dot,
                                   u"the middle dot of L·L"))
    elif dot and small_l and info.glyph(0x140):
        ldot = info.glyph(0x140)
        rules.append(locl_rule(info, "CAT", "context", u"sub %s' %s' %s by %s;" % (small_l, dot, small_l, ldot),
                               [small_l, dot, small_l, ldot], u"%s %s %s" % (small_l, dot, small_l),
                               u"%s %s" % (ldot, small_l), u"l·l set as ŀl (U+0140), the font having no "
                               u"periodcentered.loclCAT"))
        if cap_l and info.glyph(0x13F):
            cap_ldot = info.glyph(0x13F)
            rules.append(locl_rule(info, "CAT", "context", u"sub %s' %s' %s by %s;" % (cap_l, dot, cap_l, cap_ldot),
                                   [cap_l, dot, cap_l, cap_ldot], u"%s %s %s" % (cap_l, dot, cap_l),
                                   u"%s %s" % (cap_ldot, cap_l), u"L·L set as ĿL (U+013F)"))

    # Dutch: í j takes an acute on its j too (íj, ÍJ)
    for letter, acute_code, candidates in DUTCH_J:
        plain, acute = info.glyph_of.get(letter), info.glyph(acute_code)
        accented = [name for name in candidates if name in info.has]
        if plain and acute and accented:
            handled.add(accented[0])
            rules.append(locl_rule(info, "NLD", "context", u"sub %s %s' by %s;" % (acute, plain, accented[0]),
                                   [acute, plain, accented[0]], u"%s %s" % (acute, plain), accented[0],
                                   u"the digraph ij stressed: both letters take the acute"))

    # Turkic languages: i keeps its dot in capitals and small capitals
    small_i = info.glyph(0x69)
    turkish = [name for name in TURKISH_I_FORMS if name in info.has]
    if small_i and turkish:
        handled.add(turkish[0])
        small_cap = [name for name in TURKISH_SMALL_I if name in info.has]
        note = (u"i stays dotted in capitals and small capitals (%s in smcp)" % small_cap[0]) if small_cap else \
            u"i stays dotted in capitals (the font has no small capital İ: in small capitals it stays as it is)"
        for language in TURKIC_I:
            rules.append(locl_rule(info, language, "single", u"sub %s by %s;" % (small_i, turkish[0]),
                                   [small_i, turkish[0]], small_i, turkish[0], note))

    # Any other glyph named .loclXXX: the language from its name, the script from its base's character
    for name in sorted(info.names):
        parts = name.split(u".")
        match = LOCL_SUFFIX.match(parts[-1]) if len(parts) > 1 else None
        if not match or name in handled or not parts[0]:
            continue
        base = u".".join(parts[:-1])
        for language in suffix_languages(match.group(1)):
            note = u"" if language in LANGUAGE_NAMES else u"%s: a language tag FreeLab does not know; check it" % language
            if base in info.has:
                rules.append(locl_rule(info, language, "single", u"sub %s by %s;" % (base, name), [base, name], base,
                                       name, note))
                rules[-1].data["own"] = True
            elif u"." not in base and u"_" in base and all(part in info.has for part in base.split(u"_")):
                parts_of = base.split(u"_")
                rules.append(locl_rule(info, language, "ligature", u"sub %s by %s;" % (u" ".join(parts_of), name),
                                       parts_of + [name], u" ".join(parts_of), name,
                                       note or u"a ligature of the language"))
    # The font's own .loclXXX form of a glyph wins over a convention's for the same glyph and language
    # (one lookup cannot take two substitutions of one glyph)
    own = set((rule.data["language"], rule.glyphs[0]) for rule in rules if rule.data.get("own"))
    rules = [rule for rule in rules if rule.data.get("own") or rule.data["kind"] != "single"
             or (rule.data["language"], rule.glyphs[0]) not in own]
    if not rules:
        return None
    taken = set((script.strip(), language) for script, language in taken)
    left = set()
    for rule in rules:
        if all((script.strip(), rule.data["language"]) in taken for script in rule.data["scripts"]):
            left.add(rule.data["language"])
            rule.warning, rule.on, rule.first_on = True, False, False
            rule.note = u"; ".join(text for text in (rule.note, u"the font's own code sets %s already (a feature "
                                                     u"sets a language once): add this rule there if it lacks "
                                                     u"it" % rule.data["language"]) if text)
    feature = FormFeature("locl", rules, make_locl,
                          u"Forms of a language, for text tagged with it (on unless turned off); the prefix "
                          u"declares each language")
    feature.taken, feature.left = taken, sorted(left)
    return feature


LOCL_KINDS = ("ligature", "single", "context")  # a lookup each (a lookup holds one kind of rule)


def make_locl(rules, feature):
    """locl's block: a script statement each, then a language statement and its lookups each, every
    language once, and none the font's own code sets already (feature.taken: set again, it stops the
    compiler)."""
    taken = getattr(feature, "taken", None) or set()
    groups = {}
    for rule in rules:
        for script in rule.data["scripts"]:
            if (script.strip(), rule.data["language"]) in taken:
                continue
            groups.setdefault(script, {}).setdefault(rule.data["language"], {}).setdefault(
                rule.data["kind"], []).append(rule.line)
    lines = []
    for script in sorted(groups):
        lines.append(u"script %s;" % script)
        for language in sorted(groups[script]):
            lines.append(u"language %s;" % language)
            for kind in LOCL_KINDS:
                found = groups[script][language].get(kind)
                if found:
                    lines.extend(lookup_lines(u"FreeLab_locl_%s_%s_%s" % (script.strip(), language, kind), found))
    return lines


def language_systems(feature):
    """{(script, language)} the checked locl rows need declared, with each script's default."""
    found = set()
    if feature is None or not feature.on:
        return found
    for rule in feature.checked():
        for script in rule.data["scripts"]:
            found.add((script, rule.data["language"]))
            found.add((script, "dflt"))
    return found


LANGUAGE_SYSTEM = re.compile(r"^\s*languagesystem\s+(\S+)\s+(\S+)\s*;")


def prefix_text(old, systems):
    """The prefix with FreeLab's block of the language systems it lacks: after its own last
    languagesystem line (with DFLT dflt first where it has none, which declaring one more would drop)."""
    begin, end = BEGIN % LANGUAGES_BLOCK, END % LANGUAGES_BLOCK
    kept, inside, have, last, found = [], False, set(), None, False
    for line in (old or u"").splitlines():
        stripped = line.strip()
        if stripped == begin:
            inside = found = True
            continue
        if stripped == end:
            inside = False
            continue
        if inside:
            continue
        match = LANGUAGE_SYSTEM.match(line.split(u"#")[0])
        if match:
            have.add((match.group(1), match.group(2)))
            last = len(kept)
        kept.append(line)
    wanted = sorted(systems - have, key=lambda pair: (pair[0] != "DFLT", pair[0], pair[1] != "dflt", pair[1]))
    if wanted and not have:
        wanted = [("DFLT", "dflt")] + [pair for pair in wanted if pair != ("DFLT", "dflt")]
    if not wanted and not found:
        return old or u""  # nothing to add or take out: the prefix as it is
    if not wanted:
        text = u"\n".join(kept)
    else:
        block = [begin] + [u"languagesystem %s %s;" % pair for pair in wanted] + [end]
        at = 0 if last is None else last + 1
        text = u"\n".join(kept[:at] + block + kept[at:])
    return text + u"\n" if text and not text.endswith(u"\n") else text


# -- Fractions, numerators, denominators -------------------------------------------------

def figure_variants(info, figure):
    """A figure's other forms by style (.tf, .osf...): what fractions and ordinals also take."""
    found = []
    for suffix, _ in FIGURE_SUFFIXES:
        form = info.form(figure, (suffix,))
        if form and form not in found:
            found.append(form)
    return found


def superior_of(info, base):
    """A glyph's superior form: by suffix, else the Unicode superscript character the font has."""
    form = info.form(base, SUPS_SUFFIXES)
    if form:
        return form
    return unicode_forms(info, "<super>").get(base)


def unicode_forms(info, kind):
    """{base glyph: the glyph of its superscript (kind <super>) or subscript (<sub>) character}."""
    cache = info.__dict__.setdefault("_unicode_forms", {})
    if kind in cache:
        return cache[kind]
    found = cache[kind] = {}
    for name in info.names:
        for code in info.codes.get(name, ()):
            if code in NOT_SUPERSCRIPT:
                continue
            parts = unicodedata.decomposition(unichr_(code)).split()
            if len(parts) == 2 and parts[0] == kind:
                base = info.glyph(int(parts[1], 16))
                if base and base != name:
                    found.setdefault(base, name)
    return found


def fraction_features(info):
    """frac, numr, and dnom (None for each the font cannot make). A figure's numerator is its .numr
    form, else, in frac only, its superior; its denominator its .dnom form. The figures' other forms
    (.tf, .osf...) take the same."""
    slash, fraction = info.glyph(0x2F), info.glyph(0x2044)
    numerators, denominators, parts = [], [], []
    for figure in info.figures():
        if not figure:
            continue
        sources = [figure] + figure_variants(info, figure)
        numerator, denominator = info.form(figure, NUMR_SUFFIXES), info.form(figure, DNOM_SUFFIXES)
        if numerator:
            numerators.append(FormRule(figure, [figure, numerator], figure, numerator, u"", sources=sources,
                                       target_glyph=numerator))
        if denominator:
            denominators.append(FormRule(figure, [figure, denominator], figure, denominator, u"", sources=sources,
                                         target_glyph=denominator))
        note = u""
        if denominator and not numerator:
            numerator, note = superior_of(info, figure), u"its superior as the numerator"
        if numerator and denominator:
            parts.append(FormRule(figure, [figure, numerator, denominator], figure, u"%s / %s" % (numerator, denominator),
                                  note, sources=sources, numerator=numerator, denominator=denominator))
    frac = numr = dnom = None
    if parts and (slash or fraction):
        rules = []
        if slash and fraction:
            rules.append(FormRule(u"divider", [slash, fraction], slash, fraction, u"the slash becomes the fraction bar",
                                  u"sub %s by %s;" % (slash, fraction), divider=True))
        frac = FormFeature("frac", rules + parts, make_frac,
                           u"For the text a user selects as a fraction (1/2): figures before the bar become "
                           u"numerators, figures after it denominators%s" % (
                               u"" if fraction else u"; the font has no fraction bar (U+2044): the slash divides"))
        frac.data = {"slash": slash, "fraction": fraction}
    if numerators:
        numr = FormFeature("numr", numerators, make_figure_class, u"Numerators, for fractions the frac feature does "
                                                                 u"not make (off unless turned on)")
    if denominators:
        dnom = FormFeature("dnom", denominators, make_figure_class, u"Denominators (off unless turned on)")
    return frac, numr, dnom


def class_pairs(rules, target_key):
    """Two parallel glyph classes: each row's sources, and its target as often."""
    sources, targets = [], []
    for rule in rules:
        for source in rule.data["sources"]:
            if source not in sources:
                sources.append(source)
                targets.append(rule.data[target_key])
    return sources, targets


def make_figure_class(rules, feature):
    sources, targets = class_pairs(rules, "target_glyph")
    return lookup_lines(u"FreeLab_%s" % feature.tag, [u"sub [%s] by [%s];" % (u" ".join(sources), u" ".join(targets))])


def make_frac(rules, feature):
    divider = [rule for rule in rules if rule.data.get("divider")]
    figures = [rule for rule in rules if not rule.data.get("divider")]
    if not figures:
        return []
    sources, numerators = class_pairs(figures, "numerator")
    unique_numerators, denominators = [], []
    for rule in figures:
        if rule.data["numerator"] not in unique_numerators:
            unique_numerators.append(rule.data["numerator"])
            denominators.append(rule.data["denominator"])
    slash, fraction = feature.data["slash"], feature.data["fraction"]
    bars = [fraction] if (divider and fraction) else [name for name in (fraction, slash) if name]
    lines = []
    if divider:
        lines.extend(lookup_lines(u"FreeLab_frac_bar", [divider[0].line]))
    lines.extend(lookup_lines(u"FreeLab_frac_numerators", [u"sub [%s] by [%s];" % (u" ".join(sources),
                                                                                  u" ".join(numerators))]))
    lines.extend(lookup_lines(u"FreeLab_frac_denominators", [u"sub [%s] [%s]' by [%s];" % (
        u" ".join(bars + denominators), u" ".join(unique_numerators), u" ".join(denominators))]))
    return lines


# -- Superscripts, subscripts, scientific inferiors, ordinals ---------------------------------

def scripted_feature(info, tag, suffixes, kind, note):
    pairs, seen = [], set()
    for suffix in suffixes:
        for base, form in sorted(info.index.get(suffix, {}).items()):
            if base not in seen and not any(u"." + s + u"." in u"." + base + u"." for s in suffixes):
                seen.add(base)
                pairs.append((base, form, u""))
    for base, form in sorted(unicode_forms(info, kind).items()):
        if base not in seen:
            seen.add(base)
            pairs.append((base, form, u"its Unicode %s character" % (u"superscript" if kind == "<super>" else u"subscript")))
    if not pairs:
        return None
    return FormFeature(tag, single_rules(pairs), make_singles, note)


def ordinal_feature(info):
    """ordn: after figures (and a period, as in 1.\N{MASCULINE ORDINAL INDICATOR}), a and o become the
    ordinal indicators (or their .ordn forms), and the letters with .ordn forms theirs, one after
    another (1er, 2nd)."""
    pairs = []
    for letter, indicator_code in ((u"a", 0xAA), (u"o", 0xBA)):
        small = info.glyph_of.get(letter)
        target = (info.form(small, ("ordn",)) if small else None) or info.glyph(indicator_code)
        for char in (letter, letter.upper()):
            glyph = info.glyph_of.get(char)
            if target and glyph and glyph != target:
                pairs.append((glyph, target, True))
    done = set(source for source, _, _ in pairs)
    for base, form in sorted(info.index.get("ordn", {}).items()):
        if base not in done and u".ordn" not in u"." + base:
            pairs.append((base, form, False))
    figures = []
    for figure in info.figures():
        if figure:
            figures.extend([figure] + figure_variants(info, figure))
    if not pairs or not figures:
        return None
    rules = [FormRule(source, [source, target], source, target, u"after a figure", None, target_glyph=target,
                      sources=[source], indicator=indicator) for source, target, indicator in pairs]
    feature = FormFeature("ordn", rules, make_ordinals,
                          u"Ordinals: after figures, a and o become the ordinal indicators, and letters with an "
                          u".ordn form take it (off unless turned on)")
    feature.data = {"figures": figures, "period": info.glyph(0x2E)}
    return feature


def make_ordinals(rules, feature):
    sources, targets = class_pairs(rules, "target_glyph")
    figures = u"[%s]" % u" ".join(feature.data["figures"])
    lines = [u"sub %s [%s]' by [%s];" % (figures, u" ".join(sources), u" ".join(targets))]
    if feature.data["period"]:
        lines.append(u"sub %s %s [%s]' by [%s];" % (figures, feature.data["period"], u" ".join(sources),
                                                   u" ".join(targets)))
    chained = [rule for rule in rules if not rule.data["indicator"]]
    if chained:  # 1ere, 2nd: each letter after an ordinal letter too
        lines.append(u"sub [%s] [%s]' by [%s];" % (
            u" ".join(sorted(set(rule.data["target_glyph"] for rule in chained))),
            u" ".join(rule.data["sources"][0] for rule in chained),
            u" ".join(rule.data["target_glyph"] for rule in chained)))
    return lookup_lines(u"FreeLab_ordn", lines)


# -- Small capitals ------------------------------------------------------------------------

SMALL_CAP_SUFFIXES = ("sc", "smcp", "c2sc")


def is_small_cap(name):
    return any(part in SMALL_CAP_SUFFIXES for part in name.split(u".")[1:])


def renamed(info, name, char):
    """name with its first part the glyph of char (A.ss01, a: a.ss01), or None."""
    glyph = info.glyph_of.get(char) if char else None
    if not glyph:
        return None
    parts = name.split(u".")
    return u".".join([glyph] + parts[1:])


def small_cap_features(info):
    """smcp (lowercase to small capitals) and c2sc (capitals to small capitals), from .sc, .smcp, and
    .c2sc forms: a.sc for a in smcp and for A in c2sc; A.sc likewise; a caseless glyph's (a figure's,
    a sign's) in both."""
    smcp, c2sc = [], []
    for name in info.names:
        if is_small_cap(name) or not name.split(u".")[0]:
            continue
        char = info.char_of(name)
        if not char:
            continue
        category = unicodedata.category(char)
        if category == "Ll":
            form = info.form(name, ("smcp", "sc"))
            note = u""
            if not form:
                upper = char.upper()
                other = renamed(info, name, upper) if len(upper) == 1 else None
                form = info.form(other, ("sc", "smcp", "c2sc")) if other else None
                if not form and other:
                    lower = renamed(info, other, upper.lower())
                    form = info.form(lower, ("smcp", "sc")) if lower and lower != name else None
                note = u"its capital's small capital" if form else u""
            if not form and name in TURKISH_I_FORMS:
                found = [n for n in TURKISH_SMALL_I if n in info.has]
                form, note = (found[0], u"the dotted small capital İ") if found else (None, u"")
            if form:
                smcp.append((name, form, note))
        elif category in ("Lu", "Lt"):
            form = info.form(name, ("c2sc", "sc"))
            note = u""
            if not form and char == unichr_(0x130):  # (Python 2 lowers it to a plain i: asked first)
                found = [n for n in TURKISH_SMALL_I if n in info.has]
                form, note = (found[0], u"the dotted small capital i") if found else (None, u"")
            if not form:
                lower = char.lower()
                other = renamed(info, name, lower) if len(lower) == 1 else None
                form = info.form(other, ("sc", "smcp", "c2sc")) if other else None
                note = u"its lowercase letter's small capital" if form else u""
            if form:
                c2sc.append((name, form, note))
        else:
            form = info.form(name, ("sc", "smcp", "c2sc"))
            if form:
                smcp.append((name, form, u"caseless: in both"))
                c2sc.append((name, form, u"caseless: in both"))
    found = []
    for tag, pairs, note in (("smcp", smcp, u"Lowercase letters as small capitals (off unless turned on)"),
                             ("c2sc", c2sc, u"Capitals as small capitals (off unless turned on)")):
        found.append(FormFeature(tag, single_rules(sorted(pairs)), make_singles, note) if pairs else None)
    return found


# -- Figures: tabular, proportional, lining, oldstyle ----------------------------------------------

def figure_style(info):
    """(spacing, style, why) of the default figures: spacing from their widths where known (one width:
    tabular), else from their forms' suffixes; style from their height where known (0 lower than 8:
    oldstyle), else from the suffixes."""
    figures = [f for f in info.figures() if f]
    specs = set()
    for figure in figures:
        for suffix, spec in FIGURE_SUFFIXES:
            if info.form(figure, (suffix,)):
                specs.add(spec)
    why = []
    measured = measured_spacing(info, figures)
    widths = [info.widths.get(f) for f in figures]
    if measured:
        spacing = measured
        why.append(u"their widths")
    elif any(s[0] == "tab" for s in specs) and not any(s[0] == "prop" for s in specs):
        spacing = "prop"
        why.append(u"the tabular forms")
    elif any(s[0] == "prop" for s in specs) and not any(s[0] == "tab" for s in specs):
        spacing = "tab"
        why.append(u"the proportional forms")
    else:
        spacing = "prop"
    style = measured_style(info, info.glyph_of.get(u"0"), info.glyph_of.get(u"8"))
    if style:
        why.append(u"the height of 0 and 8")
    elif any(s[1] == "old" for s in specs) and not any(s[1] == "lin" for s in specs):
        style = "lin"
        why.append(u"the oldstyle forms")
    elif any(s[1] == "lin" for s in specs) and not any(s[1] == "old" for s in specs):
        style = "old"
        why.append(u"the lining forms")
    else:
        full = set(s for s in specs if None not in s)
        missing = [s for s in (("prop", "lin"), ("tab", "lin"), ("prop", "old"), ("tab", "old")) if s not in full]
        style = missing[0][1] if len(missing) == 1 else "lin"
        if len(missing) == 1:
            spacing = missing[0][0] if not widths or None in widths else spacing
            why.append(u"the forms the font has")
    return spacing, style, u" and ".join(why) if why else u"no sign: taken as the usual"


def figure_rank(info, base):
    """A glyph's place among the figures (0 to 9), past them for any other."""
    char = info.char_of(base)
    return DIGITS.index(char) if char and char in DIGITS else len(DIGITS)


TABULAR_SHARE = 0.7  # the share of a set's figures with one width for it to be a tabular set (the rest: warnings)


def measured_spacing(info, glyphs):
    """"tab" where most of the glyphs (figures) share one advance width, "prop" where they do not,
    None where fewer than five widths are known."""
    widths = [int(round(info.widths[g])) for g in glyphs if g and info.widths.get(g) is not None]
    if len(widths) < 5:
        return None
    common = max(widths.count(width) for width in set(widths))
    return "tab" if common >= TABULAR_SHARE * len(widths) else "prop"


def measured_style(info, zero, eight):
    """"old" where 0 is lower than 8 (an x-height zero), "lin" where not, None where their ink is not
    known."""
    zero, eight = info.bounds.get(zero), info.bounds.get(eight)
    if not zero or not eight or eight[3] <= 0:
        return None
    return "old" if zero[3] < 0.85 * eight[3] else "lin"


def describe_style(spacing, style):
    return u"%s %s" % (SPACING_WORDS[spacing], STYLE_WORDS[style])


def figure_sets(info, default):
    """{(spacing, style): {base: glyph}}: every base glyph's forms by figure spacing and style (the
    defaults under the default's, other glyphs with figure suffixes too: a tabular period)."""
    sets = {}
    bases = set()
    specs = {}
    for suffix, spec in FIGURE_SUFFIXES:
        forms = info.index.get(suffix, {})
        bases.update(forms.keys())
        # A suffix that names one of the two (.onum: oldstyle) takes the other from its own figures where
        # their widths or ink are known, else from the default figures
        figures = [forms.get(f) for f in info.figures()]
        spacing = spec[0] or measured_spacing(info, figures) or default[0]
        style = spec[1] or measured_style(info, figures[0], figures[8]) or default[1]
        specs[suffix] = (spacing, style)
    for base in sorted(bases):
        if any(u"." + suffix + u"." in u"." + base + u"." for suffix, _ in FIGURE_SUFFIXES):
            continue
        sets.setdefault(default, {})[base] = base
        for suffix, _ in FIGURE_SUFFIXES:
            form = info.form(base, (suffix,))
            if form:
                sets.setdefault(specs[suffix], {}).setdefault(base, form)
    return sets


def tabular_warnings(info, sets, default):
    """Rows for each tabular set whose figures do not share one width: the ones apart from the most
    common width (only where widths are known)."""
    rules = []
    for spec in (("tab", "lin"), ("tab", "old")):
        forms = sets.get(spec, {})
        figures = [forms.get(f) for f in info.figures() if f and forms.get(f)]
        widths = dict((g, info.widths.get(g)) for g in figures if info.widths.get(g) is not None)
        if len(widths) < 2:
            continue
        counts = {}
        for width in widths.values():
            counts[int(round(width))] = counts.get(int(round(width)), 0) + 1
        common = max(sorted(counts), key=lambda w: counts[w])
        apart = [g for g in figures if g in widths and int(round(widths[g])) != common]
        if apart:
            what = u"default figures" if spec == default else u"%s figures" % describe_style(*spec)
            for glyph in apart:
                rules.append(FormRule(u"width " + glyph, [glyph], glyph,
                                      u"%s wide" % counted(int(round(widths[glyph])), u"unit"),
                                      u"The %s are tabular, but %s is not %s wide like the others: review it "
                                      u"(nothing is changed here)" % (what, glyph, counted(common, u"unit")),
                                      warning=True))
    return rules


def figure_features(info):
    """lnum, onum, pnum, and tnum (None for each the font's forms do not call for), and the default
    figures' (spacing, style, why)."""
    default = figure_style(info)
    spec = default[:2]
    sets = figure_sets(info, spec)
    found = {}
    for tag, changes in (("lnum", ("style", "old", "lin")), ("onum", ("style", "lin", "old")),
                         ("pnum", ("spacing", "tab", "prop")), ("tnum", ("spacing", "prop", "tab"))):
        part, start, end = changes
        pairs = []
        for (spacing, style), forms in sorted(sets.items()):
            if (spacing if part == "spacing" else style) != start:
                continue
            target_spec = (end, style) if part == "spacing" else (spacing, end)
            if part == "style" and target_spec not in sets:
                # No figures of that style at this spacing: the other spacing's (oldstyle figures that are
                # proportional only, for tabular default figures), as the style is what was asked for
                target_spec = ("prop" if spacing == "tab" else "tab", end)
            targets = sets.get(target_spec, {})
            for base, glyph in sorted(forms.items(), key=lambda item: (figure_rank(info, item[0]), item[0])):
                target = targets.get(base)
                if target and target != glyph:
                    pairs.append((glyph, target, u"%s to %s" % (describe_style(spacing, style),
                                                                describe_style(*target_spec))))
        rules = single_rules(pairs)
        if tag == "tnum":
            rules += tabular_warnings(info, sets, spec)
        found[tag] = FormFeature(tag, rules, make_singles, u"The default figures are %s (by %s)." % (
            describe_style(*spec), default[2])) if pairs or (tag == "tnum" and rules) else None
    return found, default


# -- Stylistic sets and character variants ---------------------------------------------------

def base_letter(char):
    """A character without its marks (á: a)."""
    decomposed = unicodedata.normalize("NFD", char) if char else u""
    return decomposed[0] if decomposed else char


def story(char, boxes):
    """'single' or 'double' for an a or a g drawn as one or two stories, from its contours' boxes
    ((x0, y0, x1, y1), y up), or None: a g of three contours has two bowls; an a's counter reaching
    near its top is a single bowl's."""
    if not boxes or char not in (u"a", u"g"):
        return None
    if char == u"g":
        return {2: "single", 3: "double"}.get(len(boxes))
    outer = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    height = outer[3] - outer[1]
    inner = [b for b in boxes if b is not outer and b[0] >= outer[0] and b[2] <= outer[2] and b[1] >= outer[1]
             and b[3] <= outer[3]]
    if not inner or height <= 0:
        return None
    top = max(b[3] for b in inner)
    return "single" if (top - outer[1]) / float(height) > 0.7 else "double"


def describe_list(items):
    items = list(items)
    if len(items) <= 1:
        return u"".join(items)
    if len(items) == 2:
        return u"%s and %s" % tuple(items)
    return u"%s, and %s" % (u", ".join(items[:-1]), items[-1])


def char_label(char):
    if char.isalnum():
        return char
    return char_name(char).lower() or char


def suggest_set_name(info, pairs):
    """A stylistic set's name from what it changes (pairs: [(glyph, its alternate)]): Single-story a
    where the outlines tell (an a or a g of the other story), else Alternate a and g, Alternate
    figures, Alternate capitals..."""
    chars = []
    for source, _ in pairs:
        char = info.char_of(source)
        letter = base_letter(char) if char else None
        if letter and letter not in chars:
            chars.append(letter)
    if not chars:
        return u"Alternates"
    if all(char in (u"a", u"g") for char in chars):
        changed = []
        for char in chars:
            base = info.glyph_of.get(char)
            targets = [target for source, target in pairs if source == base]
            old = story(char, info.contours.get(base))
            new = story(char, info.contours.get(targets[0])) if targets else None
            if old and new and old != new:
                changed.append((new, char))
        if len(changed) == len(chars) and len(set(kind for kind, _ in changed)) == 1:
            return u"%s-story %s" % (changed[0][0].capitalize(), describe_list([char for _, char in changed]))
    if len(chars) <= 3:
        return u"Alternate %s" % describe_list([char_label(char) for char in chars])
    if all(char in DIGITS for char in chars):
        return u"Alternate figures"
    if all(unicodedata.category(char) == "Lu" for char in chars):
        return u"Alternate capitals"
    if all(unicodedata.category(char) == "Ll" for char in chars):
        return u"Alternate lowercase"
    chars.sort(key=lambda char: (not (u"A" <= char <= u"z" and char.isalpha()), char))
    return u"Alternate %s, and others" % u", ".join(char_label(char) for char in chars[:3])


def hand_name(text):
    """The name the font's own code (outside FreeLab's block) gives a set, or None."""
    kept = strip_block(text, FORMS)
    match = re.search(r'(?:featureNames|FeatUILabelNameID)\s*\{[^}]*?name\s+(?:[0-9]+\s+)*"([^"]*)"', kept or u"")
    return match.group(1) if match else None


def set_features(info, texts):
    """ss01 to ss20 and cv01 to cv99, from the glyphs named with them, each with a suggested name."""
    found = []
    for tag in SET_TAGS:
        pairs = [(base, form) for base, form in sorted(info.index.get(tag, {}).items())
                 if u"." + tag + u"." not in u"." + base + u"."]
        if not pairs:
            continue
        feature = FormFeature(tag, single_rules([(base, form, u"") for base, form in pairs]), make_singles,
                              u"A set of alternates users switch on as a whole (off unless turned on)"
                              if tag.startswith(u"ss") else u"A glyph's alternate (off unless turned on)",
                              suggest_set_name(info, pairs))
        feature.hand_name = hand_name(texts.get(tag))
        if feature.hand_name:
            feature.name = feature.first_name = feature.hand_name
        found.append(feature)
    return found


# -- Access All Alternates --------------------------------------------------------------

ALTERNATE_CODE = re.compile(r"^\s*sub(?:stitute)?\s+\S+\s+(?:by|from)\s+\S", re.M)


def has_alternates(text):
    """Whether a feature's code substitutes a glyph (or a class) by another, or from a set."""
    return bool(text and ALTERNATE_CODE.search(text))


def aalt_feature(info, texts, made):
    """aalt from the font's alternate features (each referred to: "feature case;"), those FreeLab writes
    as they are checked when written, and each ASCII character with the spacing accent the font draws
    like it (and the other way round). made: the other form features; texts: the font's features."""
    rows = []
    tags = [tag for tag in ALTERNATE_FEATURES
            if has_alternates(texts.get(tag)) or any(f.tag == tag for f in made if f is not None)]
    for tag in tags:
        rows.append(FormRule(u"feature " + tag, [], tag, tag, u"its alternates (%s)" % FORM_TITLES.get(tag, tag),
                             u"feature %s;" % tag, kind="feature"))
    for ascii_code, accent_code, label in ASCII_VARIANTS:
        ascii_glyph, accent = info.glyph(ascii_code), info.glyph(accent_code)
        if ascii_glyph and accent and ascii_glyph != accent:
            note = u"the %s typed as %s, offered as the %s, and back" % (label, unichr_(ascii_code), unichr_(accent_code))
            rows.append(FormRule(ascii_glyph, [ascii_glyph, accent], ascii_glyph, accent, note,
                                 u"sub %s from [%s];" % (ascii_glyph, accent), kind="ascii"))
            rows.append(FormRule(accent, [accent, ascii_glyph], accent, ascii_glyph, u"", u"sub %s from [%s];" % (
                accent, ascii_glyph), kind="ascii"))
    if not rows:
        return None
    others = [f for f in made if f is not None]

    def make_aalt(rules, feature):
        """aalt's statements, a feature referred to only while it has code: the font's own, or FreeLab's
        checked (else the compiler stops at a feature with no rules)."""
        lines = []
        for rule in rules:
            if rule.data.get("kind") == "feature":
                tag = rule.source
                written = any(f.tag == tag and f.on and f.checked() for f in others)
                own = has_alternates(strip_block(texts.get(tag), FORMS))
                if not (written or own):
                    continue
            lines.append(rule.line)
        return lines

    return FormFeature("aalt", rows, make_aalt,
                       # (plain text: a note is a list cell's, and a list cell shows markup as typed)
                       u"What InDesign and Illustrator offer as a selected character's alternates (in place and in "
                       u"their Glyphs panel): every one-for-one alternate of the font's features, and the "
                       u"ASCII characters' look-alike accents")


def aalt_first(features):
    """The font's features with aalt first (the feature compiler takes aalt only before the others; a
    feature FontLab adds goes last): each taken out and put back in order. True when they moved."""
    keys = list(features.keys())
    if u"aalt" not in keys or keys[0] == u"aalt":
        return False
    saved = [(tag, features.get_feature(tag)) for tag in keys]
    try:
        for tag in keys:
            features.remove(tag)
        for tag, text in [item for item in saved if item[0] == u"aalt"] + [item for item in saved if item[0] != u"aalt"]:
            features.set_feature(tag, text)
    except Exception:
        have = set(features.keys())
        for tag, text in saved:  # nothing lost: whatever is missing put back
            if tag not in have:
                features.set_feature(tag, text)
        raise
    return True


# -- The features in the font ------------------------------------------------------------------

def strip_block(text, block_name):
    """text without FreeLab's blocks of that name (a reader's view: without_blocks, as far as their
    markers pair)."""
    return without_blocks(text, BEGIN % block_name, END % block_name, strict=False)


def feature_kind(text):
    """How a feature stands in the font's code: "none" (no code), "fontlab" (FontLab's automatic code
    only), "freelab" (FreeLab's forms block, and nothing by hand), or "hand" (code of the designer's:
    outside both, or in a block handed back from FontLab)."""
    if not text or not text.strip():
        return "none"
    # By tokens (Codex review 6): FreeLab's markers and FontLab's are comments wherever they stand; markers
    # that do not pair make the code the designer's (nothing of it is taken for FreeLab's)
    try:
        freelab = bool(block_spans(text, BEGIN % FORMS, END % FORMS))
    except FeatureCodeUnreadable:
        return "hand"
    rest = without_blocks(text, BEGIN % FORMS, END % FORMS)
    spans, open_left = automatic_spans(rest)
    fontlab = bool(spans) or open_left
    words = [token[0] for token in code_tokens(own_code(rest, BEGIN % FORMS, END % FORMS))]
    at = 0
    while at < len(words):  # (the feature's own "feature tag {" and "} tag;" are no one's code)
        if words[at] == u"feature" and at + 2 < len(words) and words[at + 2] == u"{":
            at += 3
        elif words[at] == u"}" and at + 2 < len(words) and words[at + 2] == u";":
            at += 3
        else:
            return "hand"
    if freelab:
        return "freelab"
    return "fontlab" if fontlab else "none"


SINGLE = re.compile(r"^\s*sub(?:stitute)?\s+([A-Za-z0-9_.\-]+)\s+by\s+([A-Za-z0-9_.\-]+)\s*;")


def automatic_singles(text):
    """{(source, target)} of the single substitutions in FontLab's automatic block."""
    found, automatic = set(), False
    for line in (text or u"").splitlines():
        stripped = line.strip()
        if stripped.startswith(FONTLAB_AUTO):
            automatic = True
        elif stripped.startswith(u"#<"):
            automatic = False
        elif automatic:
            match = SINGLE.match(line)
            if match:
                found.add((match.group(1), match.group(2)))
    return found


def covered(feature, text):
    """Whether FontLab's automatic code already makes every checked row's substitution, and FreeLab's
    code would add nothing else (no context, no name)."""
    rules = feature.checked()
    if feature.make is not make_singles or (feature.tag in SET_TAGS and feature.name):
        return False
    have = automatic_singles(text)
    return bool(rules) and all(SINGLE.match(rule.line) and SINGLE.match(rule.line).groups() in have for rule in rules)


def form_features(info, texts):
    """Every form feature the font's glyphs call for, in FORM_ORDER, each with how it stands in the font
    and its first check: on, but off where the font's code has the feature by hand, or where FontLab's
    automatic code does the same; a feature whose FreeLab block is all that is left (its glyphs gone)
    is listed with no rows, to take the block out."""
    made = [locl_feature(info, own_languages(texts.get("locl"))), case_feature(info)]
    made.extend(fraction_features(info))
    made.append(scripted_feature(info, "sups", SUPS_SUFFIXES, "<super>", u"Superscripts (off unless turned on)"))
    made.append(scripted_feature(info, "subs", SUBS_SUFFIXES, "<sub>", u"Subscripts (off unless turned on)"))
    made.append(scripted_feature(info, "sinf", SINF_SUFFIXES, "<sub>",
                                 u"Scientific inferiors, as in H2O (off unless turned on)"))
    made.append(ordinal_feature(info))
    made.extend(small_cap_features(info))
    figures, default = figure_features(info)
    made.extend(figures[tag] for tag in ("lnum", "onum", "pnum", "tnum"))
    made.extend(set_features(info, texts))
    made.append(aalt_feature(info, texts, made))
    by_tag = dict((feature.tag, feature) for feature in made if feature is not None)
    for tag, text in texts.items():
        if tag not in by_tag and (BEGIN % FORMS) in (text or u""):
            by_tag[tag] = FormFeature(tag, [], make_singles, u"FreeLab's code is in the font, but its glyphs are "
                                                              u"gone: writing takes it out")
    order = list(FORM_ORDER) + sorted(tag for tag in by_tag if tag not in FORM_ORDER)
    found = []
    for tag in order:
        feature = by_tag.get(tag)
        if feature is None:
            continue
        text = texts.get(tag)
        feature.kind = feature_kind(text)
        if feature.kind == "hand":
            feature.on = False
            feature.kind_note = (u"The font's code has its own %s: left alone unless you tick it (FreeLab's block "
                                 u"then goes in beside it, the rest kept)." % tag)
        elif feature.kind == "fontlab" and covered(feature, text):
            feature.on = False
            feature.kind_note = (u"FontLab makes this feature automatically, and its code does the same: left to "
                                 u"it. Ticked, FreeLab's code replaces FontLab's (handed back from it).")
        elif feature.kind == "fontlab":
            feature.kind_note = (u"FontLab makes this feature automatically: FreeLab's code replaces its code, "
                                 u"and the feature is handed back from FontLab (no longer rewritten by it).")
        elif feature.kind == "freelab":
            feature.kind_note = u"FreeLab's code is in the font: written again as shown."
        if feature.tag != "locl" and feature.kind == "hand" and re.search(  # (locl's block sets its own)
                r"^\s*(script|language)\s", strip_block(text, FORMS), re.M):
            feature.kind_note += (u" Its code sets languages: FreeLab's block, at its end, would apply to the last "
                                  u"one only.")
        left = getattr(feature, "left", None)
        if left:  # (locl: the languages the font's own code sets, which FreeLab's block cannot set again)
            feature.kind_note = (feature.kind_note + u" " if feature.kind_note else u"") + (
                u"Its code sets %s already, and a feature sets a language once: %s rows are left to it." % (
                    describe_list(left), u"that language's" if len(left) == 1 else u"those languages'"))
        feature.first_on = feature.on
        found.append(feature)
    return found, default


def forms_feature_text(tag, old, lines):
    """A feature's code with FreeLab's forms block (lines) in place: an older block taken out, FontLab's
    automatic code replaced (its "#> feature" line handed back as "#/> feature", what it held dropped:
    FreeLab's block makes the same feature), the rest kept. The block goes first where it names a set
    (featureNames lead a feature), else before the feature's closing line. No lines: the block out,
    the rest as it was."""
    begin, end = BEGIN % FORMS, END % FORMS
    # FreeLab's older block and FontLab's automatic code found by their comments wherever they stand (an end
    # marker after code on its line had been missed, and the font's code after it taken out with the block);
    # markers that do not pair raise FeatureCodeUnreadable, even to take a block out
    readable(old, tag)  # (before and after, taking a block out too: Codex review 7)
    text = without_blocks(old, begin, end, tag)
    if lines:
        text = handed_back(text, drop=True, tag=tag)
    text = text.rstrip(u"\r\n")
    if not lines:
        if not code_tokens(text):  # (no code: the feature, empty, as a new one was)
            return insert_block(text, tag, [], title=FORM_TITLES.get(tag, tag)) + u"\n"
        readable(text, tag)
        return text + u"\n"
    # The feature's braces found by statements (insert_block): the font's own code is never made again
    # from nothing (FeatureCodeUnreadable where they cannot be found)
    block = [begin] + [u"  " + line for line in lines] + [end]
    return insert_block(text, tag, block, first=lines[0].startswith((u"featureNames", u"cvParameters")),
                        title=FORM_TITLES.get(tag, tag)) + u"\n"


def forms_texts(features, texts, refused=None):
    """{tag: new code} for each form feature checked, and each unchecked one whose FreeLab block is in
    the font (taken out); only where the code changes. refused: a list the tags of the features whose
    code FreeLab cannot read go in (FeatureCodeUnreadable: nothing written to them)."""
    new = {}
    for feature in features:
        old = texts.get(feature.tag)
        try:
            if feature.on:
                text = forms_feature_text(feature.tag, old, feature.lines())
            elif (BEGIN % FORMS) in (old or u""):
                text = forms_feature_text(feature.tag, old, [])
            else:
                continue
        except FeatureCodeUnreadable:
            if refused is not None:
                refused.append(feature.tag)
            continue
        if text != old:
            new[feature.tag] = text
    return new


def forms_check(features, texts, systems, names, cache=None):
    """{tag: fontTools' complaint} about FreeLab's block of each feature to write (checked alone,
    after the language systems it needs). cache: {code: complaint}, kept between calls for one font
    (a block checked once is not parsed again as other choices change)."""
    problems = {}
    cache = {} if cache is None else cache
    head = u"".join(u"languagesystem %s %s;\n" % pair for pair in
                    sorted(systems | set([("DFLT", "dflt")]), key=lambda p: (p[0] != "DFLT", p[0], p[1] != "dflt", p[1])))
    for feature in features:
        text = texts.get(feature.tag)
        block = freelab_block(feature.tag, text, FORMS) if text else None
        if block and feature.tag == "aalt":  # (the features it refers to are checked with their own code)
            block = u"\n".join(line for line in block.splitlines() if not re.match(r"^\s*feature\s+\w+\s*;", line))
        if block:
            code = head + block
            if code not in cache:
                cache[code] = check_code(code, names)
            if cache[code]:
                problems[feature.tag] = cache[code]
    return problems


# ---------------------------------------------------------------------------
# Figure forms to build: the numerators, denominators, superiors, inferiors, Unicode superscript and
# subscript figures, and ordinal indicators the font lacks, each planned as a component of its figure
# (or letter), scaled and moved
# ---------------------------------------------------------------------------

DIGIT_WORDS = (u"zero", u"one", u"two", u"three", u"four", u"five", u"six", u"seven", u"eight", u"nine")
SUPERSCRIPT_FIGURES = (0x2070, 0xB9, 0xB2, 0xB3, 0x2074, 0x2075, 0x2076, 0x2077, 0x2078, 0x2079)  # 0 to 9
SUBSCRIPT_FIGURES = tuple(range(0x2080, 0x208A))
ORDINAL_LETTERS = ((u"a", 0xAA, u"ordfeminine"), (u"o", 0xBA, u"ordmasculine"))
LINING_SUFFIXES = ("lf", "tf", "plf", "tlf", "lnum")  # scaled instead of oldstyle default figures
SMALL_SETS = ("numr", "dnom", "sups", "subs", "ordn")  # each with its own scale, baseline, and width
SMALL_SET_TITLES = {"numr": u"Numerators", "dnom": u"Denominators", "sups": u"Superiors and superscripts",
                    "subs": u"Inferiors and subscripts", "ordn": u"Ordinal indicators"}
SET_SUFFIXES = {"numr": NUMR_SUFFIXES, "dnom": DNOM_SUFFIXES, "sups": SUPS_SUFFIXES, "subs": SUBS_SUFFIXES}
# The build list's sections: (group, the set whose settings it takes, title)
SMALL_GROUPS = (
    ("numr", "numr", u"Numerators"), ("dnom", "dnom", u"Denominators"), ("sups", "sups", u"Superiors"),
    ("superscript", "sups", u"Superscript figures (\N{SUPERSCRIPT ONE}\N{SUPERSCRIPT TWO}\N{SUPERSCRIPT THREE}"
                            u"\N{SUPERSCRIPT FOUR}\N{HORIZONTAL ELLIPSIS})"),
    ("subs", "subs", u"Inferiors"),
    ("subscript", "subs", u"Subscript figures (\N{SUBSCRIPT ZERO}\N{SUBSCRIPT ONE}\N{SUBSCRIPT TWO}"
                          u"\N{HORIZONTAL ELLIPSIS})"),
    ("ordn", "ordn", u"Ordinal indicators (\N{FEMININE ORDINAL INDICATOR} \N{MASCULINE ORDINAL INDICATOR})"))
# The medians of 182 open-licensed families (features/train/figure_forms.py, 2026-11-11). Scale: a form's
# ink height over its figure's (numerators and denominators 0.57 in 49 families, superiors 0.59 in 68,
# Unicode superscript figures 0.59 in 143, inferiors 0.59 in 63; the letters of the ordinal indicators
# 0.66 of a and o in 164). Width: its advance over the scaled figure's (1.12: a little more room around
# the small figure than scaling gives).
CORPUS_SCALE = {"numr": 0.57, "dnom": 0.57, "sups": 0.59, "subs": 0.59, "ordn": 0.66}
CORPUS_WIDTH = {"numr": 1.12, "dnom": 1.12, "sups": 1.12, "subs": 1.11, "ordn": 1.07}
# Where they sit: a numerator's top at the figures' top (1.01 of the cap height in the corpus), a
# denominator on the baseline, a superior's baseline at 0.51 of the cap height, an inferior's at -0.17,
# an ordinal indicator's top at 1.01 of it
SUPS_BASELINE, SUBS_BASELINE, ORDINAL_TOP = 0.51, -0.17, 1.01
# A whole drawn set another set is moved from (unscaled) rather than scaling the figures, by preference
DRAWN_SOURCES = {"numr": ("dnom", "sups", "subs"), "dnom": ("numr", "subs", "sups"),
                 "sups": ("numr", "dnom", "subs"), "subs": ("dnom", "numr", "sups")}


def median(values):
    values = sorted(values)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2.0


class SmallForm(object):
    """A figure form (or ordinal indicator) the font lacks: its glyph name, its section of the list
    (group), the set whose settings it takes, the glyph it is scaled from (base: the figure, its lining
    form, or a letter), the figure or letter it is a form of, and its code point (a Unicode
    character's), or None."""

    def __init__(self, name, group, set_key, base, code=None, figure=None):
        self.name, self.group, self.set_key, self.base, self.code = name, group, set_key, base, code
        self.figure = figure or base
        self.on = self.first_on = True


class Placement(object):
    """How a planned glyph is made: its parts [(glyph, sx, sy, dx, dy)], its advance width, and how:
    "scaled" from its figure, "moved" from a drawn form of another set, or "copied" from its own set's
    form of the figure (a Unicode superscript figure from the .sups one)."""

    def __init__(self, parts, width, how, source):
        self.parts, self.width, self.how, self.source = parts, width, how, source


def small_suffix(info, suffixes):
    """The suffix the font names a set's figures with (the one most of its figures have), else the
    first one (numr, dnom, sups, subs)."""
    counts = [sum(1 for figure in info.figures() if figure and figure in info.index.get(suffix, {}))
              for suffix in suffixes]
    best = max(counts) if counts else 0
    return suffixes[counts.index(best)] if best else suffixes[0]


def encoded_name(info, code, digit, styles):
    """A Unicode figure's glyph name: as the font names its others (styles: (codes, ending); a font
    with onesuperior gets foursuperior, and fourinferior), else uniXXXX; None where the name is taken
    (by a glyph without the code point: not built beside it)."""
    ending = None
    for codes, word in styles:
        if any(info.glyph(other) == DIGIT_WORDS[n] + word for n, other in enumerate(codes)):
            ending = styles[0][1]
            break
    name = DIGIT_WORDS[digit] + ending if ending else u"uni%04X" % code
    return None if name in info.has else name


def scaling_source(info, figure):
    """The glyph a figure's small forms are scaled from: the figure, or its lining form where the default
    figures are oldstyle (small figures are lining in the corpus)."""
    if measured_style(info, info.glyph_of.get(u"0"), info.glyph_of.get(u"8")) == "old":
        lining = info.form(figure, LINING_SUFFIXES)
        if lining:
            return lining
    return figure


def missing_small_forms(info):
    """[SmallForm] of what the font lacks, section by section: each figure's numerator and denominator
    (no .numr, .dnom form); its superior and inferior (no .sups or .subs form and no Unicode character
    the features take instead); the Unicode superscript and subscript figures; and the ordinal
    indicators. Names follow the font's: its suffix for the set (one.numerator: two.numerator), its
    names for the Unicode figures (twosuperior: foursuperior), else .numr, .dnom, .sups, .subs, and
    uniXXXX."""
    found = []
    figures = [(digit, figure) for digit, figure in enumerate(info.figures()) if figure]
    for set_key in ("numr", "dnom", "sups", "subs"):
        suffixes = SET_SUFFIXES[set_key]
        suffix = small_suffix(info, suffixes)
        encoded = unicode_forms(info, "<super>" if set_key == "sups" else "<sub>") if set_key in ("sups", "subs") else {}
        for digit, figure in figures:
            name = u"%s.%s" % (figure, suffix)
            if not info.form(figure, suffixes) and not encoded.get(figure) and name not in info.has:
                found.append(SmallForm(name, set_key, set_key, scaling_source(info, figure), figure=figure))
        if set_key in ("sups", "subs"):
            codes = SUPERSCRIPT_FIGURES if set_key == "sups" else SUBSCRIPT_FIGURES
            styles = ((SUPERSCRIPT_FIGURES, u"superior"),) if set_key == "sups" else \
                ((SUBSCRIPT_FIGURES, u"inferior"), (SUPERSCRIPT_FIGURES, u"superior"))
            for digit, figure in figures:
                name = encoded_name(info, codes[digit], digit, styles) if info.glyph(codes[digit]) is None else None
                if name:
                    found.append(SmallForm(name, "superscript" if set_key == "sups" else "subscript", set_key,
                                           scaling_source(info, figure), codes[digit], figure))
    for letter, code, name in ORDINAL_LETTERS:
        base = info.glyph_of.get(letter)
        if base and info.glyph(code) is None and name not in info.has:
            found.append(SmallForm(name, "ordn", "ordn", base, code))
    return found


def form_measure(info, form, figure):
    """(scale, baseline, width) of a drawn small form against its figure: its ink height over the
    figure's, where the figure's baseline lands once scaled (the form's lowest point less the scaled
    figure's), and its advance over the scaled figure's (None where a width is not known); None where
    their ink is not known."""
    fig, box = info.bounds.get(figure), info.bounds.get(form)
    if not fig or not box or fig[3] - fig[1] <= 0:
        return None
    scale = (box[3] - box[1]) / float(fig[3] - fig[1])
    if not 0.2 < scale < 0.95:
        return None
    advance, figure_advance = info.widths.get(form), info.widths.get(figure)
    width = advance / (scale * figure_advance) if advance and figure_advance else None
    return scale, box[1] - scale * fig[1], width


def set_members(info, set_key):
    """[(figure, form)]: the font's drawn forms of a set (a superior or inferior set takes in the
    Unicode superscript or subscript figures)."""
    found = []
    codes = {"sups": SUPERSCRIPT_FIGURES, "subs": SUBSCRIPT_FIGURES}.get(set_key)
    for digit, figure in enumerate(info.figures()):
        if not figure:
            continue
        form = info.form(figure, SET_SUFFIXES[set_key])
        if form:
            found.append((figure, form))
        if codes and info.glyph(codes[digit]):
            found.append((figure, info.glyph(codes[digit])))
    return found


def figure_top(info):
    """The figures' top (the median of their ink tops), or None where their ink is not known."""
    tops = [info.bounds[name][3] for name in (scaling_source(info, f) for f in info.figures() if f)
            if info.bounds.get(name)]
    return median(tops)


# Stroke weight kept while scaling: scaling a figure to 60% thins its strokes to 60%; most fonts' drawn small
# figures have ink about 7% wider than scaling gives (the corpus's figure forms). A form built with STROKE_WEIGHT
# above 100 is made of outlines (not components), offset outward until its strokes are that share of the
# scaled ones: the same offset on both sides of each stroke, so it keeps its place.
STROKE_WEIGHT = 107  # percent of the scaled strokes
STROKE_READ_BACK = 0.6  # units: a node counts as moved past this, and as kept within this of where it was put
# (FontLab may round a node to whole units)
MITER_LIMIT = 2.0  # a sharp corner moves at most this many times the offset


def place_node(node, x, y):
    """Moves a node, through its position where it has one. FontLab keeps a node's x and y set from a
    script, and its contour's path follows, but the shape's own outline does not (its bounding box
    stayed where it was: seen live on a detached layer, 2026-11-13), so forms built with thicker strokes
    looked as scaled. Set through position, the shape follows."""
    if hasattr(node, "position"):
        try:
            from PythonQt import QtCore
            node.position = QtCore.QPointF(x, y)
            return
        except Exception:
            pass
    node.x, node.y = x, y


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def shape_matrix(shape):
    """(m11, m12, m21, m22, dx, dy) of a shape's transform (a value it does not give: the identity's)."""
    try:
        transform = shape.transform
    except Exception:
        return IDENTITY
    values = []
    for name, default in zip(("m11", "m12", "m21", "m22", "dx", "dy"), IDENTITY):
        try:
            values.append(float(getattr(transform, name)()))
        except Exception:
            values.append(default)
    return tuple(values)


def mapped(matrix, x, y):
    """A point through a matrix (m11, m12, m21, m22, dx, dy), as QTransform maps it."""
    m11, m12, m21, m22, dx, dy = matrix
    return (m11 * x + m21 * y + dx, m12 * x + m22 * y + dy)


def compose(matrix, move):
    """matrix, then move (sx, sy, dx, dy: a scale and an offset), as one matrix."""
    m11, m12, m21, m22, dx, dy = matrix
    sx, sy, mx, my = move
    return (sx * m11, sy * m12, sx * m21, sy * m22, sx * dx + mx, sy * dy + my)


def wanted_points(places, points):
    """[(x, y, moved, on-curve)] of a contour's nodes as offset (places [(x, y)]; points [(x, y, on)]
    as they were): moved where a node goes past STROKE_READ_BACK."""
    return [(x, y, abs(x - p[0]) > STROKE_READ_BACK or abs(y - p[1]) > STROKE_READ_BACK, p[2])
            for (x, y), p in zip(places, points)]


def shape_box(shape):
    """(left, bottom, right, top) of what FontLab draws of a shape (its boundingBox), or None."""
    try:
        rect = shape.boundingBox
        rect = rect() if callable(rect) else rect
        box = (float(rect.left()), float(rect.top()), float(rect.right()), float(rect.bottom()))
    except Exception:
        return None
    return box if box[2] > box[0] and box[3] > box[1] else None  # (font units grow upward: top() is the lowest)


DRAWN_SLACK = 1.0  # units: a drawn box this near the nodes' (FontLab may round a node to whole units)


def drawn_box_kept(box, outlines, slack=DRAWN_SLACK):
    """Whether FontLab draws a shape as its nodes were put: its drawn box (shape_box) holds the box of
    the on-curve nodes wanted and lies within the box of them all (a curve stays inside its handles),
    each within slack, in the coordinates of one of outlines ([[(x, y, moved, on)]] a contour: the
    form's, or the shape's own, which a box may be told in). None where the box is not known. A shape
    whose outline did not follow its nodes is drawn at its box before the offset: smaller by the
    offset all around."""
    if box is None:
        return None
    for outline in outlines:
        points = [point for contour in outline for point in contour]
        if not points:
            continue
        ons = [point for point in points if point[3]] or points
        inner = (min(p[0] for p in ons), min(p[1] for p in ons), max(p[0] for p in ons), max(p[1] for p in ons))
        outer = (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points),
                 max(p[1] for p in points))
        holds = box[0] <= inner[0] + slack and box[1] <= inner[1] + slack and \
            box[2] >= inner[2] - slack and box[3] >= inner[3] - slack
        within = box[0] >= outer[0] - slack and box[1] >= outer[1] - slack and \
            box[2] <= outer[2] + slack and box[3] <= outer[3] + slack
        if holds and within:
            return True
    return False


def refresh_shape(shape):
    """A shape whose contours were written told to draw them anew (its ink box reset, then updated):
    each call only where FontLab has it, and none may stop the build."""
    for name in ("resetInkBox", "update"):
        method = getattr(shape, name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass


def update_layer(layer):
    """A layer whose shapes were replaced told to measure itself again (flObject.update). Live
    (2026-11-14, IBM Plex Sans JP): zero.sups built again at 130% and 160% had its new shape's box
    grow (41.9 to 280.0, then 35.0 to 294.0), while the layer's own box, what FontLab measures and
    draws of the glyph, stayed the 100% one (48.9 to 266.1) until layer.update() was called."""
    try:
        layer.update()
    except Exception:
        pass


def offset_contour(points, distance, right=True):
    """A closed contour's points [(x, y, on-curve)] moved outward by distance (inward when negative):
    each on-curve point along the bisector of the normals of its two neighbors' directions (a corner
    moves further, up to MITER_LIMIT times), each handle with its on-curve point (the one it leaves or
    reaches), so curves keep their directions. right: the outside is right of the contour's direction
    (PostScript's counterclockwise outer contours, y up); else left. Returns [(x, y)]."""
    import math
    count = len(points)
    ons = [i for i, point in enumerate(points) if point[2]]
    if not ons or not distance:
        return [(x, y) for x, y, _ in points]

    def away(i, step):
        x, y = points[i][0], points[i][1]
        for k in range(1, count):
            q = points[(i + step * k) % count]
            dx, dy = q[0] - x, q[1] - y
            length = math.hypot(dx, dy)
            if length > 1e-6:
                return dx / length * step, dy / length * step
        return None

    def normal(d):
        return (d[1], -d[0]) if right else (-d[1], d[0])

    moves = {}
    for i in ons:
        din, dout = away(i, -1), away(i, 1)
        if din is None or dout is None:
            moves[i] = (0.0, 0.0)
            continue
        nin, nout = normal(din), normal(dout)
        bx, by = nin[0] + nout[0], nin[1] + nout[1]
        length = math.hypot(bx, by)
        if length < 1e-6:
            bx, by = nin
        else:
            bx, by = bx / length, by / length
        cos_half = max(bx * nin[0] + by * nin[1], 1.0 / MITER_LIMIT)
        moves[i] = (bx * distance / cos_half, by * distance / cos_half)
    moved = []
    for i, (x, y, on) in enumerate(points):
        if on:
            dx, dy = moves[i]
        else:  # a handle: with the on-curve point it is nearer along the contour (it leaves or reaches it)
            back = next(k for k in range(1, count + 1) if points[(i - k) % count][2])
            ahead = next(k for k in range(1, count + 1) if points[(i + k) % count][2])
            dx, dy = moves[(i - back) % count] if back <= ahead else moves[(i + ahead) % count]
        moved.append((x + dx, y + dy))
    return moved


def signed_area(points):
    """A closed contour's area by its points (positive: counterclockwise, y up), its handles counted as
    corners: enough to tell its direction."""
    total = 0.0
    for i in range(len(points)):
        x0, y0 = points[i][0], points[i][1]
        x1, y1 = points[(i + 1) % len(points)][0], points[(i + 1) % len(points)][1]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def stem_width(contains, box, steps=400):
    """The stroke width of a figure across its middle (its vertical strokes): the median length of the
    runs inside it on a line at half its height. contains(x, y): inside; box: (left, bottom, right, top)."""
    left, bottom, right, top = box
    y = (bottom + top) / 2.0
    step = max((right - left) / float(steps), 0.5)
    runs, start, x = [], None, left - step
    while x <= right + step:
        inside = contains(x, y)
        if inside and start is None:
            start = x
        elif not inside and start is not None:
            runs.append(x - start)
            start = None
        x += step
    if not runs:
        return None
    runs.sort()
    return runs[len(runs) // 2]


def small_settings(info, cap, upm=1000):
    """{set: {"scale", "baseline", "width", "why", "top_of"}}: each set's first settings. Scale and width
    are the medians of the font's own drawn forms of the set where it has some, else of its other small
    figures, else the corpus's. The baseline (where the scaled figure's baseline goes, in font units) is
    the font's own where it has some; else a numerator's top is the figures' top, a denominator sits on
    the baseline, superiors and inferiors where the corpus puts them, and an ordinal indicator's top at
    the font's other indicator's top, else where the corpus puts it. top_of: the height whose scaled top
    stays put when the scale changes (numerators and ordinal indicators), else None."""
    top = figure_top(info)
    cap = cap if cap and cap > 0 else (top or 0.7 * upm)
    top = top or cap
    measured = {}
    for set_key in ("numr", "dnom", "sups", "subs"):
        measured[set_key] = [m for m in (form_measure(info, form, scaling_source(info, figure))
                                         for figure, form in set_members(info, set_key)) if m]
    every = [m for set_key in ("numr", "dnom", "sups", "subs") for m in measured[set_key]]
    settings = {}
    for set_key in ("numr", "dnom", "sups", "subs"):
        own = measured[set_key]
        widths = [m[2] for m in (own or every) if m[2]]
        if own:
            scale, baseline = median(m[0] for m in own), median(m[1] for m in own)
            why = u"As the font's %s." % counted(len(own), u"drawn form")
        else:
            scale = median(m[0] for m in every) if every else CORPUS_SCALE[set_key]
            baseline = {"numr": top * (1 - scale), "dnom": 0.0, "sups": SUPS_BASELINE * cap,
                        "subs": SUBS_BASELINE * cap}[set_key]
            why = (u"Sized as the font's other small figures, placed as most open-licensed fonts." if every else
                   u"As most open-licensed fonts.")
        settings[set_key] = {"scale": round(scale, 2), "baseline": int(round(baseline)),
                             "width": round(median(widths), 2) if widths else CORPUS_WIDTH[set_key], "why": why,
                             "top_of": top if set_key == "numr" else None}
    letters = [info.bounds.get(info.glyph_of.get(letter)) for letter, _, _ in ORDINAL_LETTERS]
    letter_top = max([box[3] for box in letters if box] or [0.5 * cap])
    drawn = [info.bounds.get(info.glyph(code)) for _, code, _ in ORDINAL_LETTERS]
    drawn = [box[3] for box in drawn if box]
    scale = CORPUS_SCALE["ordn"]
    settings["ordn"] = {"scale": scale, "baseline": int(round((max(drawn) if drawn else ORDINAL_TOP * cap) -
                                                             scale * letter_top)),
                        "width": CORPUS_WIDTH["ordn"], "top_of": letter_top,
                        "why": u"Top at the font's other indicator's, sized as most open-licensed fonts." if drawn else
                        u"As most open-licensed fonts."}
    return settings


def rescaled_baseline(setting, scale):
    """A set's baseline once its scale changes: where its top stays put (numerators, ordinal
    indicators), moved to keep it there; else as it was."""
    top_of = setting.get("top_of")
    if not top_of:
        return setting["baseline"]
    return int(round(setting["baseline"] + (setting["scale"] - scale) * top_of))


def complete_sets(info):
    """{set: {figure: form}} of the font's drawn sets (by suffix) that have all ten figures."""
    found = {}
    figures = [f for f in info.figures() if f]
    for set_key, suffixes in SET_SUFFIXES.items():
        forms = dict((f, info.form(f, suffixes)) for f in figures)
        if len(figures) == len(DIGITS) and all(forms.values()):
            found[set_key] = forms
    return found


def plan_small_forms(info, forms, settings, advance=None):
    """{name: Placement, or None where it cannot be placed (its glyph's width unknown)} of each form. A
    Unicode figure takes its set's form of the figure where the font has it or it is checked to be built
    too (a copy, in place); a form of a set the font lacks a figure of is moved from a whole drawn set
    of another (unscaled); else it is its figure scaled, moved to its set's baseline, and centered in
    its width. advance: a glyph's advance width (the current master's measured ones by default)."""
    advance = advance or info.widths.get
    complete = complete_sets(info)
    planned = dict(((form.set_key, form.figure), form.name) for form in forms
                   if form.on and form.group in ("sups", "subs"))
    plans = {}
    for form in sorted(forms, key=lambda f: f.group in ("superscript", "subscript")):  # (sets first: copied after)
        plans[form.name] = place_small_form(info, form, settings[form.set_key], complete, planned, plans, advance)
    return plans


def place_small_form(info, form, setting, complete, planned, plans, advance):
    if form.group in ("superscript", "subscript"):
        own = info.form(form.figure, SET_SUFFIXES[form.set_key])
        if own and advance(own):
            return Placement([(own, 1.0, 1.0, 0, 0)], advance(own), "copied", own)
        own = planned.get((form.set_key, form.figure))
        if own and plans.get(own) is not None:
            return Placement([(own, 1.0, 1.0, 0, 0)], plans[own].width, "copied", own)
    for other in DRAWN_SOURCES.get(form.set_key, ()):
        drawn = complete.get(other, {}).get(form.figure)
        measure = form_measure(info, drawn, scaling_source(info, form.figure)) if drawn else None
        if measure and advance(drawn):
            return Placement([(drawn, 1.0, 1.0, 0, int(round(setting["baseline"] - measure[1])))], advance(drawn),
                             "moved", drawn)
    width = advance(form.base)
    if not width:
        return None
    scale = setting["scale"]
    new = int(round(width * scale * setting["width"]))
    return Placement([(form.base, scale, scale, int(round((new - width * scale) / 2.0)), int(setting["baseline"]))],
                     new, "scaled", form.base)


def flat_parts(plans, name, depth=4):
    """A plan's parts down to glyphs of the font: a part that is another planned glyph replaced by
    that one's parts, moved with it (to draw a glyph before it is built)."""
    plan = plans.get(name)
    if plan is None:
        return []
    found = []
    for glyph, sx, sy, dx, dy in plan.parts:
        if glyph in plans and depth:
            for inner, isx, isy, idx, idy in flat_parts(plans, glyph, depth - 1):
                found.append((inner, sx * isx, sy * isy, sx * idx + dx, sy * idy + dy))
        else:
            found.append((glyph, sx, sy, dx, dy))
    return found


def moved_words(dy):
    return u"on the baseline" if not dy else u"%s %s" % (u"raised" if dy > 0 else u"lowered", counted(abs(dy), u"unit"))


def describe_placement(plan):
    """A build row's words for how its glyph is made."""
    if plan is None:
        return u"its figure's width could not be read: not built"
    glyph, sx, _, _, dy = plan.parts[0]
    if plan.how == "copied":
        return u"%s, in place" % glyph
    if plan.how == "moved":
        return u"%s (drawn), %s" % (glyph, u"in place" if not dy else moved_words(dy))
    return u"%s at %d%%, %s, width %d" % (glyph, int(round(sx * 100)), moved_words(dy), plan.width)


SMALL_NOTES = {"scaled": u"scaled: a start to draw over (scaling thins its strokes)",
               "moved": u"a drawn small figure, moved", "copied": u"its set's glyph, with the code point"}
BUILT_NOTE = u"built here before (a build replaces it once its settings change)"  # a cell note: no period


def offset_words(offsets):
    """How far Strokes moved each side of a stroke, for the log: " (each side moved out 1.8 units)", or
    " (each side moved out 6.6 to 7.6 units)" where the sets' scales differ; empty without offsets."""
    values = sorted(set(round(value, 1) for value in offsets))
    if not values:
        return u""

    def number(value):
        return u"%d" % value if value == int(value) else u"%.1f" % value

    span = number(values[0]) if len(values) == 1 else u"%s to %s" % (number(values[0]), number(values[-1]))
    return u" (each side moved out %s %s)" % (span, u"unit" if values[-1] == 1 else u"units")


def suggested_words(why):
    """The Suggested button's What's This and tooltip (rich text): what a click does, then where the
    picked set's suggestion comes from (why: small_settings' sentence; None before a font is read).
    That sentence stood in the settings row, beside the button."""
    text = (u"Puts the picked set's scale, baseline, and width back as first suggested, and <i>Strokes</i> back at "
            u"%d%% (for every set)." % STROKE_WEIGHT)
    if why:
        why = (u"%s" % why).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")
        text += u" This set's suggestion: %s" % (why[:1].lower() + why[1:])
    return text


def build_label(count):
    """The build button's words for this many ticked figure forms (named for its section: it sits in the
    window's bottom row, owner's images 258 and 260)."""
    return u"Build %s" % counted(count, u"ticked figure form") if count else u"Build ticked figure forms"


GROUP_HOWS = (("scaled", u"scaled from %s", u"scaled from %s"), ("moved", u"moved from a drawn small figure",
                                                                 u"moved from drawn small figures"),
              ("copied", u"a copy of its set's glyph", u"copies of their set's glyphs"))


def group_note(forms, plans, ours=()):
    """A build list's group row's note (a cell's: no period), what its rows say in short: how many are
    made each way, what they are scaled from, their code points' span, and how many were built here
    before ("10 scaled from the figures; U+2070 to U+2079; 3 built here before")."""
    parts = []
    for how, one, many in GROUP_HOWS:
        made = [form for form in forms if getattr(plans.get(form.name), "how", None) == how]
        if not made:
            continue
        words = one if len(made) == 1 else many
        if how == "scaled":  # (the ordinal indicators' from a and o, the rest from their figures)
            letters = [form.base for form in made if form.group == "ordn"]
            words %= describe_list(sorted(set(letters))) if letters else (
                u"its figure" if len(made) == 1 else u"their figures")
        parts.append(u"%d %s" % (len(made), words))
    unplanned = sum(1 for form in forms if plans.get(form.name) is None)
    if unplanned:
        parts.append(u"%d not built (%s width could not be read)" % (
            unplanned, u"its figure's" if unplanned == 1 else u"their figures'"))
    codes = sorted(form.code for form in forms if form.code)
    if codes:
        parts.append(u"U+%04X" % codes[0] if len(codes) == 1 else u"U+%04X to U+%04X" % (codes[0], codes[-1]))
    built = sum(1 for form in forms if form.name in ours)
    if built:
        parts.append(u"%d built here before" % built)
    return u"; ".join(parts)


BUILD_WHAT = (u"Adds the ticked figure forms to the font, as shown (scaled forms with their strokes kept as <i>Strokes</i> "
              u"says), in one step of FontLab's History. The font is read again: the forms above take them. What it "
              u"built stays listed while nobody changes it: a build then replaces it with the settings shown (a glyph "
              u"drawn over is left alone).")


def build_words(count, unchanged):
    """The build button's What's This and tooltip: what it does, and, grayed out (count: the ticked figure
    forms a build would make or change), why: the ticked ones (unchanged of them) are as built here with
    these very settings, or none is ticked."""
    if count:
        return BUILD_WHAT
    if unchanged:
        return BUILD_WHAT + (u" Grayed out: %s, so a build would change nothing. Change a setting, or tick other "
                             u"figure forms, to build again." % (
                                 u"the figure form ticked was built here with these very settings" if unchanged == 1
                                 else u"the %s ticked were built here with these very settings" % counted(
                                     unchanged, u"figure form")))
    return BUILD_WHAT + u" Grayed out: no figure form that can be built is ticked."


def without_glyphs(info, names):
    """info as if the font lacked those glyphs (the figure forms this window built: listed again, so a
    build can replace them), their widths and ink kept for whatever else reads them."""
    gone = set(names)
    if not gone:
        return info
    return FontInfo([name for name in info.names if name not in gone],
                    dict((name, codes) for name, codes in info.codes.items() if name not in gone),
                    info.widths, info.bounds, info.contours)


def layer_print(layer):
    """What a built layer is, to tell later whether anything changed it since it was built: its width
    and its shapes (a component's glyph and transform; an outline's transform and nodes), in whole
    units (FontLab may round a node). Raises where FontLab does not say."""
    parts = []
    for shape in layer.shapes:
        matrix = tuple(int(round(value * 1000)) for value in shape_matrix(shape))
        if getattr(shape, "isComponent", False):
            parts.append((u"component", u"%s" % shape.shapeData.componentGlyph, matrix))
        else:
            parts.append((u"outline", matrix, tuple(tuple((int(round(n.x)), int(round(n.y))) for n in c.nodes())
                                                    for c in shape.contours if c is not None)))
    return int(round(float(layer.advanceWidth))), tuple(parts)


def plan_signature(plan, strokes):
    """What a planned form is built from (how, its parts, its width, and Strokes for a scaled one): a
    form built with the same signature is built as it would be again."""
    if plan is None:
        return None
    parts = tuple((u"%s" % name, round(sx, 4), round(sy, 4), int(round(dx)), int(round(dy)))
                  for name, sx, sy, dx, dy in plan.parts)
    return plan.how, parts, int(round(plan.width)), (int(strokes) if plan.how == "scaled" else None)


def dependent_forms(forms, plans, ours, rebuilt):
    """The names of the forms this window built (ours) made from a form built again (rebuilt), at any
    depth, in the forms' order: they are built again with it (a component keeps the glyph it points to
    as it was when it was made)."""
    names, found = set(rebuilt), []
    grew = True
    while grew:
        grew = False
        for form in forms:
            if form.name in names or form.name not in ours:
                continue
            parts = getattr(plans.get(form.name), "parts", None) or ()
            if any(u"%s" % part[0] in names for part in parts):
                names.add(form.name)
                found.append(form.name)
                grew = True
    return [form.name for form in forms if form.name in found]


# ---------------------------------------------------------------------------
# The Code box's colors (syntax highlighting): what each part of a line of feature code is
# ---------------------------------------------------------------------------

FEA_KEYWORDS = frozenset(u"""feature lookup sub substitute rsub reversesub ignore pos position enum enumerate by from
lookupflag languagesystem script language include exclude_dflt include_dflt required table featureNames
cvParameters name parameters subtable useExtension markClass anchor anchorDef valueRecordDef NULL RightToLeft
IgnoreBaseGlyphs IgnoreLigatures IgnoreMarks MarkAttachmentType UseMarkFilteringSet FeatUILabelNameID
FeatUITooltipTextNameID SampleTextNameID ParamUILabelNameID Character""".split())
# The words after these name a tag or a lookup (languagesystem: a script and a language)
FEA_NAMED_AFTER = {u"feature": 1, u"script": 1, u"language": 1, u"languagesystem": 2, u"lookup": 1}
FEA_TOKEN = re.compile(u"#.*|\"[^\"]*\"?|\\[[^\\]]*\\]?|@[A-Za-z0-9_.\\-]+|[{};]|"
                       u"-?[0-9]+(?:\\.[0-9]+)?(?![A-Za-z0-9_.])|[A-Za-z0-9_.\\\\\\-]+")
FEA_KINDS = ("keyword", "tag", "class", "list", "comment", "number", "string")
# (r, g, b) on a dark background, on a light one: each kind plain to read on either (as LOG_COLORS)
FEA_COLORS = {"keyword": ((110, 170, 240), (20, 70, 190)), "tag": ((90, 205, 185), (0, 120, 130)),
              "class": ((205, 150, 225), (130, 40, 150)), "list": ((225, 200, 140), (130, 90, 20)),
              "comment": ((125, 180, 105), (40, 120, 40)), "number": ((190, 220, 160), (20, 120, 80)),
              "string": ((230, 150, 120), (170, 50, 30))}
# Past this many lines the code is shown plain: Qt asks the highlighter for every line each time the
# code is made again (a click), and a CJK font's classes of thousands of glyphs run to thousands of
# lines, where a reply for each would hold up every click
HIGHLIGHT_LINES = 2000


def fea_spans(line, in_list=False):
    """The colored parts of a line of feature code: ([(start, length, kind)], whether a glyph list
    ([...]) is still open at its end). in_list: one was open at the end of the line before (a long
    class runs over several lines: its lines are the list's color). Keywords, the tag or name after
    feature, script, language, languagesystem, lookup, and a closing brace; glyph classes (@name),
    glyph lists as a whole, comments, numbers, and strings. Glyph names stay the text's color."""
    spans, at = [], 0
    if in_list:
        end = line.find(u"]")
        if end < 0:
            return ([(0, len(line), "list")] if line else []), True
        spans.append((0, end + 1, "list"))
        at = end + 1
    named, still_open = 0, False
    for match in FEA_TOKEN.finditer(line, at):
        token, start = match.group(0), match.start()
        first = token[:1]
        if first == u"#":
            spans.append((start, len(token), "comment"))
        elif first == u'"':
            spans.append((start, len(token), "string"))
        elif first == u"[":
            spans.append((start, len(token), "list"))
            still_open = not token.endswith(u"]")
        elif first == u"@":
            spans.append((start, len(token), "class"))
        elif token in (u"{", u";"):
            named = 0
        elif token == u"}":
            named = 1  # (} liga;)
        elif named:
            spans.append((start, len(token), "tag"))
            named -= 1
        elif token in FEA_KEYWORDS:
            spans.append((start, len(token), "keyword"))
            named = FEA_NAMED_AFTER.get(token, 0)
        elif first.isdigit() or (first == u"-" and token[1:2].isdigit()):
            if re.match(u"^-?[0-9]+(?:\\.[0-9]+)?$", token):
                spans.append((start, len(token), "number"))
    return spans, still_open


def fea_color(kind, dark):
    """A kind's (r, g, b) on a dark background (dark) or a light one."""
    return FEA_COLORS[kind][0 if dark else 1]


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 36
# A list's row is as high as its picture (ICON_SIZE and the style's few pixels around it). A row with no
# picture was one line of text high: in the Forms list, a feature's row and its plain rows stood crammed
# among rows more than twice as high. Every row of that list is given this height (pixels), which a
# picture fits in, so its rows are even and none is taller than the window's other lists' rows.
ROW_HEIGHT = ICON_SIZE + 4
TIP_WIDTH = 520  # pixels: a tooltip's text at most (Font Check's width)
TIP_CHARACTER = 7  # pixels: about a character's width (a tooltip's text is not measured)


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


UNWRAP_DEPTH = 4  # components inside components followed this deep


def unwrapped(package, master, name, sx, sy, dx, dy):
    """A scaled part (name, sx, sy, dx, dy) whose glyph is one component only replaced by the glyph it
    points to, the transforms combined: FontLab 7 refused a whole layer (setGlyphComponents made none)
    whose scaled component pointed to such a glyph (Diacritics' finding). Unscaled parts as given."""
    if sx == 1.0 and sy == 1.0:
        return name, sx, sy, dx, dy
    for _ in range(UNWRAP_DEPTH):
        try:
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            shapes = list(layer.shapes) if layer is not None else []
            if len(shapes) != 1 or not shapes[0].isComponent:
                break
            inner = shapes[0].transform
            if abs(inner.m12()) > 1e-6 or abs(inner.m21()) > 1e-6:
                break  # rotated or slanted inside: kept whole
            inner_name = shapes[0].shapeData.componentGlyph
            if not inner_name:
                break
            name, dx, dy = inner_name, sx * inner.dx() + dx, sy * inner.dy() + dy
            sx, sy = sx * inner.m11(), sy * inner.m22()
        except Exception:
            break
    return name, sx, sy, dx, dy


def is_empty(glyph):
    """A glyph with nothing drawn in any layer (or none at all)."""
    if glyph is None:
        return True
    try:
        return not any(layer.shapes for layer in glyph.layers)
    except Exception:
        return False


def counted(number, one, many=None):
    """"1 glyph", "2 glyphs", "13,932 glyphs" (thousands set apart, as the shared module's)."""
    return u"%s %s" % (grouped(number), one if number == 1 else (many or one + u"s"))


def tip_html(text, rich=False):
    """A tooltip as rich text: Qt wraps rich text, and shows plain text on one line however long (a long
    note's tooltip ran past the screen's edge). text: plain, escaped here (rich: rich text already).
    One whose longest line would pass TIP_WIDTH pixels is laid out in a one-cell table that wide (Qt's
    rich text takes a width from nothing else): Font Check's manner."""
    text = u"%s" % (text or u"")
    if not text:
        return u""
    lines = (plain(text.replace(u"<br>", u"\n")) if rich else text).split(u"\n")
    if not rich:
        text = text.replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;").replace(u"\n", u"<br>")
    if max(len(line) for line in lines) * TIP_CHARACTER > TIP_WIDTH:
        return u"<table width=\"%d\" cellspacing=\"0\" cellpadding=\"0\"><tr><td>%s</td></tr></table>" % (TIP_WIDTH, text)
    return u"<span>%s</span>" % text


NO_FONT_PROP = "freelabNoFont"  # ak.NO_FONT_PROP: a control ak.no_font_states grayed, its window having no font


def set_enabled(widget, on):
    """A control grayed out, or not, whatever its container's state. Auto Kerning's enable() sets a
    state only when it differs from the one the widget reports, and a widget reports its container's
    too: while the window is busy (its lists' part disabled), a button to gray out read as grayed
    out already, was left alone, and came back clickable with its container (Build checked glyphs,
    after a build that left nothing to build). A control the shared module grayed for want of a font
    stays grayed (as ak.enable keeps it: it gives it back with a font)."""
    try:
        if on and widget.property(NO_FONT_PROP):
            return
    except Exception:
        pass
    try:
        widget.setEnabled(bool(on))
    except Exception:
        pass  # a signal's handler must not raise


def say(label, text):
    """A note's text, the note hidden while it says nothing: an empty label still took a line, a gap
    between a heading and what it heads (owner's images 197 and 198)."""
    try:
        label.setText(text)
        label.setVisible(bool((u"%s" % (text or u"")).strip()))
    except Exception:
        pass


def describe(widget, text, tip=False):
    """A control's What's This (rich text), and its tooltip too when asked; the widget."""
    try:
        widget.setWhatsThis(text)
        if tip:
            widget.setToolTip(tip_html(text, True))
    except Exception:
        pass
    return widget


def label_of(QtGui, text, what):
    """A setting's label with the What's This of the control beside it. A widget with none answers
    with its nearest container's, shown in that container's middle: a right-click on the label
    Strokes showed the text of the part's splitter over the Suggested button."""
    return describe(QtGui.QLabel(text), what)


def describe_handles(splitter, text):
    """A splitter's hint on its handles (the spaces dragged), not on the splitter: on the splitter, every
    label and blank space inside it answered a right-click with it (label_of)."""
    try:
        for index in range(1, splitter.count()):
            describe(splitter.handle(index), text, True)
    except Exception:
        pass


def place_cell_widgets(view):
    """The widgets a list shows in its cells (setItemWidget: the ligatures' feature boxes) put where
    their cells are now, at once: Qt places one where its cell is when it is set, and moves it after a
    column's width changes only once it lays the list out again, later (owner's image 221: the boxes
    stood over the next column while the font was read). True when the list was laid out."""
    for name in ("doItemsLayout", "updateGeometries"):
        try:
            getattr(view, name)()
            return True
        except Exception:
            continue
    return False


def fit_combo(QtGui, combo):
    """A dropdown as wide as its widest item, never stretched across its row (owner's image 239); the
    combo."""
    try:
        combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
    except Exception:
        pass
    return combo


FORM_SOURCE_MOST = 220  # pixels: the Forms list's first column grows this far for its rows' glyph names


def form_column_width(indentation, texts, measure=None, most=FORM_SOURCE_MOST):
    """The least width of the Forms list's first column for a feature's rows to show whole: a row's
    indent (under its feature's), its check box, and the longest of texts (measure: a text's width in
    pixels; about TIP_CHARACTER a character without), up to most."""
    widest = 0
    for text in texts:
        width = 0
        if measure is not None:
            try:
                width = int(measure(u"%s" % text))
            except Exception:
                width = 0
        if not width > 0:
            width = len(u"%s" % text) * TIP_CHARACTER
        widest = max(widest, width)
    try:
        indent = int(indentation)
    except Exception:
        indent = 0
    return (indent if indent > 0 else 20) * 2 + 24 + min(widest, most) + 12


def even_row(QtCore, item, height=ROW_HEIGHT):
    """A list's row at least ROW_HEIGHT high, picture or not (through its first cell's size hint)."""
    try:
        item.setSizeHint(0, QtCore.QSize(0, height))
    except Exception:
        pass
    return item


def look_back_suffix(value):
    """What follows the look back's number in its box: " glyph" after 1, " glyphs" otherwise."""
    return u" " + counted(value, u"glyph").split(u" ", 1)[1]


def units_suffix(value):
    """What follows a number of font units in its box: " unit" after 1 and -1, " units" otherwise."""
    return u" " + counted(abs(int(value)), u"unit").split(u" ", 1)[1]


HELP = u"""<b>FreeLab Feature Code</b><br>
Writes the OpenType code for the font's ligatures, for alternates that take turns, and for the forms
its glyph names call for. The code is shown under the tabs, in <i>Code preview</i> (in colors: keywords, tags,
classes, glyph lists, numbers, and comments), and checked, before anything is written: it is in the font only
once <i>Write the code</i> is clicked.<br><br>
<b>Ligatures and alternates</b> (the first tab):<br>
<b>Ligatures</b>: each ligature with what it replaces, set to <i>Standard</i> (liga, on unless a user turns
it off), <i>Discretionary</i> (dlig, off unless a user turns it on), or <i>Off</i>. A ligature the font's code and
name do not place starts where most of the open-licensed fonts FreeLab learned from put it (f_i in
liga, c_t in dlig); its feature's tooltip says why. Applications let users switch
both: in InDesign and Illustrator, the <i>Ligatures</i> and <i>Discretionary Ligatures</i> options; on the web,
font-variant-ligatures. A feature written here is handed back from FontLab's automatic features (its
"#&gt; feature" line becomes "#/&gt; feature"), so FontLab no longer rewrites it; the rest of its
code is kept. A ligature whose rule the font's own code writes stays where it is: FreeLab never moves or
takes out a rule the font wrote (set to another feature, the window says so); it moves only its own rules
and FontLab's automatic ones.<br>
<b>Alternates that take turns</b> (calt, on unless turned off): a glyph (a letter's, a figure's, or a
punctuation mark's) repeated within the look back set takes its next alternate (X.2, X.3, or X.alt1...), so
repeated glyphs vary as handwriting does (<i>ll</i>, <i>1001</i>, <i>...</i>, <i>!!</i>). The nearest earlier
form decides; each looks back among its own kind, so a space, or punctuation between letters, ends the
look back. Ligatures come first: where liga makes l_l of <i>ll</i>, the alternates take turns around
it. Ticked glyphs take turns: <i>Tick all</i>, <i>Untick all</i>, and <i>Tick often doubled</i>, in the bottom
row, tick them at once.<br><br>
<b>Forms</b> (the second tab): one row per feature, its substitutions under it (click its arrow):
case (.case), locl (Romanian and Moldavian <i>S</i> and <i>T</i> with a comma below, Catalan
<i>l\N{MIDDLE DOT}l</i>, Dutch <i>\N{LATIN SMALL LETTER I WITH ACUTE}j</i>, the Turkic dotted <i>i</i>, and any
.loclXXX glyph), frac, numr, and dnom
(.numr, .dnom), sups, subs, and sinf, ordn, smcp and c2sc (.sc, .smcp, .c2sc), lnum, onum, pnum, and
tnum (.tf, .lf, .osf, .tosf...), and the stylistic sets (.ss01 to .ss20, each with a name you can edit)
and character variants (.cv01...). Tick a feature to write it, and its rows to keep them in it. A
feature the font's code has by hand starts unticked, as does one FontLab's automatic code already
makes the same way; a warning row (figures of a tabular set that do not share one width) is for you
to review, and changes nothing.<br>
<b>Figure forms to build</b> (under the forms): the numerators, denominators, superiors, inferiors,
Unicode superscript and subscript figures, and ordinal indicators the font lacks, each made of its
figure (or <i>a</i> or <i>o</i>) as a component, scaled and raised or lowered as most open-licensed fonts place
them (or as the font's own small figures, where it has some). Pick a set in the settings row to change
its scale, baseline, and width; <i>Strokes</i>, one value for every set, is the strokes kept (outlines thickened
evenly; 100%: components); <i>Suggested</i>, at the row's end, puts the four back. A built form is a start
to refine.
<i>Build ticked figure forms</i> (in the bottom row) adds them in one step of FontLab's History; the font is
read again, and the forms above take them. What it built stays listed: change a setting and build again to
replace it (a glyph drawn over since is left alone).<br><br>
<b>Stylistic alternates</b> (the third tab) holds two separate jobs, and its list two groups.
<i>Suggestions</i>: the glyphs fonts most often give a stylistic alternate; <i>Make copies to redraw</i>
gives each ticked one a copy named for a stylistic set (a.ss01), to redraw by hand. <b>Variants that take
turns</b>: computed copies of the glyphs ticked in the list's <i>Selected glyphs</i> group, which the
<i>Glyphs</i> dropdown fills (the ticked suggestions, a script, a case, the glyphs typed...), each changed a
little as a whole (X.alt1, X.alt2...), which the first tab then cycles; they need no copy made first.
<i>Build N variants</i> builds them. <i>Also build variants from existing alternates</i> spreads a
glyph's variants over the glyph and the alternates the font has of it, variants built before included
(W.ss01.alt2 is a changed copy of W.ss01). Variants built here and left as they were are replaced in place
when <i>Strength</i> or <i>Seed</i> changes and you build again.<br><br>
The code is made again as you change the choices. Pick a ligature's feature in its box; drag between the parts to give one more room;
double-click a ligature, a glyph, or a form to see it in a <i>Glyph</i> window. The bottom row holds the buttons
of the tab shown, then <i>Restore suggestions</i>, which puts the choices back as they first came; at the
right, <i>Compile after writing</i>, <i>Write the code</i> beside it, the tab's builds, and <i>Close</i>.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""

TABS = (u"Ligatures and alternates", u"Forms", u"Stylistic alternates")
ALTERNATES_TAB = 2  # the third tab's index (its page is the tab's own module: freelab_alternates.py)
# The part under the tabs: "Code preview", not "Code" (owner's image 299: people must see that the code
# shown is not in the font yet, and that Write the code writes it)
CODE_HEADING = u"Code preview"
# The buttons that tick the glyphs taking turns, in the window's bottom row while the first tab is shown, in
# the suite's order (Tick all, Untick all, then the tool's own): (key, label, what it does)
TURN_CHECKS = (("all", u"Tick all", u"Ticks every glyph of <i>Alternates that take turns</i> whose alternates have no "
                                    u"other job in the font's code."),
               ("none", u"Untick all", u"Unticks every glyph of <i>Alternates that take turns</i>: none takes turns."),
               ("often", u"Tick often doubled", u"Ticks the glyphs of <i>Alternates that take turns</i> that often "
                                                u"stand doubled in text (ll, ee, ss, tt; 00 and 99; marks doubled by "
                                                u"convention, such as ..., !!, and --), and only them: those whose "
                                                u"alternates matter most."))
TURN_CHECK_LABELS = dict((key, label) for key, label, _ in TURN_CHECKS)
STYLISTIC_TAB = 2  # the Stylistic alternates tab's place, which builds variants that take turns
# What Alternates that take turns says where the font has none: where they are built, named as the tab
# is (a link that opens it)
NO_TURNS = (u"The font has no alternates to take turns (glyphs named X.2, X.alt1, or X.calt1). Build them on the "
            u"<a href=\"tab:%d\"><i>%s</i></a> tab, under <i>Variants that take turns</i>, or draw them and name "
            u"them so." % (STYLISTIC_TAB, TABS[STYLISTIC_TAB]))
FORM_ICON_WIDTH = 3  # a form row's picture: this many icons wide

# The check boxes of a list whose pictures dark mode leaves alone (LEAVE_ALONE_PROP): the style drew
# them nearly invisible on a dark palette, so a stylesheet draws them from the palette instead
CHECK_FRAME = u"rgb(140, 140, 146)"  # an unchecked box's frame: a mid gray, plain on either background
CHECK_MARK_SCALE = 3  # the check mark is drawn this many times the box's size (sharp on a scaled display)
CHECK_SHEET_MARK = u"/* FreeLab check boxes */"
TABLE_PROP = "freelabTable"  # (the shared module's: a list in FreeLab's table layout)


def check_box_sheet(size, mark=None, fill=u"palette(highlight)", frame=CHECK_FRAME, selected_frame=u"white"):
    """Stylesheet rules for a list's check boxes: unchecked, a box framed in a mid gray on the row's own
    background; checked, a box filled with fill (the list's highlight color), with the check mark
    (mark: an image file's path; None: filled only). On a selected row (the same highlight) each box
    is framed in selected_frame (the highlighted text's color), so it still stands out."""
    image = u' image: url("%s");' % mark.replace(u"\\", u"/") if mark else u""
    return (u"%s QTreeView::indicator { width: %dpx; height: %dpx; border: 1px solid %s; border-radius: 2px; "
            u"background: transparent; } "
            u"QTreeView::indicator:checked { border: 1px solid %s; background: %s;%s } "
            u"QTreeView::indicator:indeterminate { background: %s; } "
            u"QTreeView::indicator:selected { border: 1px solid %s; }" % (CHECK_SHEET_MARK, size, size, frame, fill, fill,
                                                                        image, frame, selected_frame))


def check_mark_file(QtCore, QtGui, color, size):
    """A check mark in color (r, g, b) for a box of size pixels, drawn larger and saved as a PNG in
    FreeLab's folder of the temporary files (once per color and size): its path, or None."""
    temporary = u"%s" % QtCore.QDir.tempPath()
    if not temporary or not os.path.isabs(temporary):
        return None
    folder = os.path.join(temporary, u"FreeLab")
    path = os.path.join(folder, u"check-%02x%02x%02x-%d.png" % (color[0], color[1], color[2], size))
    if os.path.isfile(path):
        return path
    if not os.path.isdir(folder):
        os.makedirs(folder)
    side = size * CHECK_MARK_SCALE
    pixmap = QtGui.QPixmap(side, side)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    try:  # ended whatever happens: a painter left open on a freed pixmap aborts FontLab
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        pen = QtGui.QPen(QtGui.QColor(color[0], color[1], color[2]))
        pen.setWidthF(side * 0.15)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        tick = QtGui.QPainterPath()
        tick.moveTo(side * 0.2, side * 0.52)
        tick.lineTo(side * 0.42, side * 0.74)
        tick.lineTo(side * 0.8, side * 0.28)
        painter.drawPath(tick)
    finally:
        painter.end()
    return path if pixmap.save(path, "PNG") else None


def style_check_boxes(QtCore, QtGui, tree, base):
    """The list's check boxes drawn in its palette's colors (base: its own stylesheet, kept before them).
    A list in FreeLab's table layout (the shared module's table_layout) draws its own, and writes them
    again on each switch: left to it (written here too, its old colors came back after a switch)."""
    try:
        if tree.property(TABLE_PROP) is not None:
            return
    except Exception:
        pass

    def color_of(palette, role, default):
        try:
            color = palette.color(role)
            return (int(color.red()), int(color.green()), int(color.blue()))
        except Exception:
            return default

    try:
        palette = tree.palette() if callable(tree.palette) else tree.palette
    except Exception:
        palette = None
    rgb = color_of(palette, QtGui.QPalette.HighlightedText, (255, 255, 255))
    fill = u"rgb(%d, %d, %d)" % color_of(palette, QtGui.QPalette.Highlight, (48, 140, 198))
    try:
        size = int(tree.style().pixelMetric(QtGui.QStyle.PM_IndicatorWidth))
    except Exception:
        size = 13
    size = max(11, min(24, size or 13))
    try:
        mark = check_mark_file(QtCore, QtGui, rgb, size)
    except Exception:
        mark = None
    tree.setStyleSheet(u"")  # (polished again: the palette's colors read anew)
    tree.setStyleSheet((base + u" " if base else u"") + check_box_sheet(size, mark, fill, CHECK_FRAME,
                                                                      u"rgb(%d, %d, %d)" % rgb))


def watch_check_boxes(dialog, trees, also=None):
    """The trees' check boxes drawn plain to see in either palette, and drawn again when dark mode
    switches (also: called then too, after the first drawing: the Code box's colors); the watcher to
    keep a reference to (None where it could not be made)."""
    QtCore, QtGui = _qt()
    bases = []
    for tree in trees:
        sheet = tree.styleSheet() if callable(tree.styleSheet) else tree.styleSheet
        sheet = u"%s" % (sheet or u"")
        bases.append(sheet.split(CHECK_SHEET_MARK)[0].strip())

    def restyle(first=False):
        for tree, base in zip(trees, bases):
            try:
                style_check_boxes(QtCore, QtGui, tree, base)
            except Exception:
                pass
        if also is not None and not first:
            try:
                also()
            except Exception:
                pass

    restyle(True)

    class CheckWatcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
        def eventFilter(self, obj, event):
            try:
                if event.type() in (38, 39):  # the palette changed: dark mode switched
                    self.start()
            except Exception:
                pass  # an event filter must never raise
            return False

    try:
        watcher = CheckWatcher(dialog)  # (its parent the window: Qt deletes it with it)
        watcher.setSingleShot(True)
        watcher.setInterval(0)
        watcher.connect("timeout()", restyle)
        dialog.installEventFilter(watcher)
        return watcher
    except Exception:
        return None


class Highlighting(object):
    """The Code box's highlighter and the document it colors: attached while the code is short enough
    (HIGHLIGHT_LINES), detached past it (the code then shows plain), its colors read again when dark
    mode switches (refresh)."""

    def __init__(self, highlighter, document, formats):
        self.highlighter, self.document, self.formats, self.attached = highlighter, document, formats, True

    def detach(self):
        if self.attached:
            try:
                self.highlighter.setDocument(None)
                self.attached = False
            except Exception:
                pass

    def attach(self):
        if not self.attached:
            try:
                self.highlighter.setDocument(self.document)  # (Qt colors it once the window answers again)
                self.attached = True
            except Exception:
                pass

    def refresh(self):
        """The colors taken from the box's palette again (dark mode switched), and the code recolored."""
        self.formats.clear()
        if self.attached:
            try:
                self.highlighter.rehighlight()
            except Exception:
                pass


def make_highlighter(edit):
    """The Code box's syntax highlighting (fea_spans' kinds in colors plain to read on the box's
    palette, dark or light), or None where PythonQt cannot make it: the box then stays plain text.
    PythonQt lets a Python class override a Qt virtual (the check boxes' watcher overrides a timer's
    eventFilter); highlightBlock is QSyntaxHighlighter's, called by Qt for each line it shows."""
    QtCore, QtGui = _qt()
    formats = {}  # kind: QTextCharFormat, made from the palette at the first line colored after a switch

    def palette_formats():
        if not formats:
            try:
                palette = edit.palette() if callable(edit.palette) else edit.palette
                dark = palette.color(QtGui.QPalette.Base).lightness() < 128
            except Exception:
                dark = False
            for kind in FEA_KINDS:
                rgb = fea_color(kind, dark)
                made = QtGui.QTextCharFormat()
                made.setForeground(QtGui.QBrush(QtGui.QColor(rgb[0], rgb[1], rgb[2])))
                formats[kind] = made
        return formats

    class FeaHighlighter(QtGui.QSyntaxHighlighter):
        def highlightBlock(self, text):
            try:
                spans, still_open = fea_spans(u"%s" % (text or u""), self.previousBlockState() == 1)
                kinds = palette_formats()
                for start, length, kind in spans:
                    self.setFormat(start, length, kinds[kind])
                self.setCurrentBlockState(1 if still_open else 0)  # (1: a glyph list runs on to the next line)
            except Exception:
                pass  # a virtual Qt calls must never raise

    try:
        document = edit.document() if callable(edit.document) else edit.document
        highlighter = FeaHighlighter(document)
        # PythonQt chose QSyntaxHighlighter(QObject *parent), which colors no document unless the parent
        # is a text box: live, the code stayed plain until the document was set (2026-11-14)
        highlighter.setDocument(document)
        return Highlighting(highlighter, document, formats)
    except Exception:
        return None


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
        # The header, as every tool's (owner's images 217, 222, 223): the top line (the font, or the no-font
        # line) first, where the tools button and the busy bar join it (add_tools_button takes the layout's
        # first row), then the status lines under it, then the header's separator, then the tabs. The tab
        # bar stood first: the busy bar ran into it.
        self.top_line = self.ak.status_label()
        describe(self.top_line, u"The font this window works on, and its current master (whose outlines the lists "
                                u"draw and the figure forms are measured in). While the font is read, glyphs are "
                                u"built, or the code is written, a bar in its place says what is under way: the tools "
                                u"menu, the arrows, <i>Close</i>, and Esc stop a read, and wait for a build or a write.")
        layout.addWidget(self.top_line)
        self.status = self.ak.status_label()
        self.status.setWordWrap(True)
        describe(self.status, u"What the font has (its ligatures, the glyphs whose alternates take turns, its form "
                              u"features) and whether the code shown can be written; after a read you stopped, a "
                              u"link that reads the font again.")
        try:  # (its link after a read stopped by the user reads the font again: read_stopped)
            self.status.setOpenExternalLinks(False)
            self.status.connect("linkActivated(QString)", self.link_activated)
        except Exception:
            pass
        layout.addWidget(self.status)
        layout.addWidget(self.ak.header_separator())
        self.log = self.ak.Log()
        # The glyphs a line names are links, drawn from the font's own outlines (the interface's fonts
        # lack many characters: they came out as empty boxes), and a click opens one in a Glyph tab
        self.log.follow(self.log_source)
        self.seen_history, self.first_choices, self.first_checks = None, [], []

        # The lists (on two tabs) and the code share the height in a splitter: drag between them to see
        # more of one
        self.splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter, 1)
        top = self.part(QtGui, 3)
        # A tab bar over plain pages: a QTabWidget's themed page drew its buttons with light frames in dark mode
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        for label in TABS:
            self.tabs.addTab(label)
        self.tabs.setTabToolTip(0, u"Ligatures (liga, dlig) and alternates that take turns (calt)")
        self.tabs.setTabToolTip(1, u"Forms: case, locl, fractions and figures, small capitals, stylistic sets")
        self.tabs.setTabToolTip(2, u"Alternates fonts commonly offer, as copies to redraw; variants that take turns")
        describe(self.tabs, u"The window's three tabs: <i>Ligatures and alternates</i> (liga, dlig, and calt), "
                            u"<i>Forms</i> (case, locl, fractions and figures, small capitals, stylistic sets, and the "
                            u"figure forms to build), and <i>Stylistic alternates</i> (copies to redraw, and variants "
                            u"that take turns). <i>%s</i>, under them, is the same whichever tab is open." % CODE_HEADING)
        top.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        top.addWidget(self.pages, 1)

        self.lists = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.lists.setChildrenCollapsible(False)
        self.pages.addWidget(self.lists)
        # The turns' part is made first and the ligatures' put above it: Qt lists a window's widgets in the
        # order they were made, and the shared module grays a Tick button whose first list shown has no
        # check box (update_states). The ligatures' list has none: listed first, it grayed the bottom row's
        # Tick all, Untick all, and Tick often doubled on the first tab.
        part = self.part(QtGui, 1, self.lists)
        turns = (u"The glyphs with alternates (named X.2, X.alt1, or X.calt1: a letter's, a figure's, or a "
                 u"punctuation mark's), and their cycle: the forms they take in turn. Ticked glyphs take turns. Those "
                 u"that often stand doubled in text (ll, ee, ss, tt, 00, and 99: counted in the text of 24 languages, "
                 u"and in kana, Armenian, and Georgian text; and the marks doubled by convention: ..., !!, ??, --, "
                 u"and '') come first; where the font has more glyphs with alternates than rules by glyph can serve, "
                 u"only those start ticked. <i>Tick all</i>, <i>Untick all</i>, and <i>Tick often doubled</i>, in the "
                 u"bottom row, tick them at once.")
        # (a line over the heading: it read as a caption of the list above, owner's image 234)
        part.addWidget(self.ak.separator())
        part.addWidget(describe(self.heading(QtGui, u"Alternates that take turns"), turns))
        row = QtGui.QHBoxLayout()
        what = (u"How many glyphs of its kind may stand between a glyph and its earlier form, at most, for it to take "
                u"the next alternate (0: only side by side). A letter looks back over letters, a figure over figures, "
                u"a punctuation mark over punctuation marks; anything else between ends the look back.")
        row.addWidget(label_of(QtGui, u"Look back:", what))
        self.look_back = QtGui.QSpinBox()
        self.look_back.setRange(0, 6)
        self.look_back.setValue(DEFAULT_LOOK_BACK)
        self.look_back.setSuffix(look_back_suffix(DEFAULT_LOOK_BACK))
        self.look_back.setWhatsThis(what)
        row.addWidget(self.look_back)
        row.addStretch(1)
        part.addLayout(row)
        # Its Tick buttons go in the window's bottom row (bottom_row), shown with the first tab
        self.turn_buttons = []
        for key, label, what in TURN_CHECKS:
            button = QtGui.QPushButton(label)
            button.setWhatsThis(what)
            button.connect("clicked()", lambda key=key: self.check_turns(key))
            self.turn_buttons.append(button)
        self.turn_label = QtGui.QLabel(u"")  # how the ticked glyphs take turns: by glyph, or by position
        self.turn_label.setWordWrap(True)
        self.ak.rich(self.turn_label)
        describe(self.turn_label, u"How the ticked glyphs take turns: by glyph (each looks back for its own earlier "
                                  u"form) while that takes few enough rules, else by position (each takes the form "
                                  u"after the form of the glyph of its kind before it). Where the font has no "
                                  u"alternates, where to build them: click the tab's name to open it.")
        try:  # (its link to the Stylistic alternates tab opens the tab, not a browser)
            self.turn_label.setOpenExternalLinks(False)
            self.turn_label.connect("linkActivated(QString)", self.link_activated)
        except Exception:
            pass
        part.addWidget(self.turn_label)
        self.turn_label.setVisible(False)  # (shown with something to say: say)
        self.alternate_tree = QtGui.QTreeWidget()
        self.alternate_tree.setColumnCount(4)
        self.alternate_tree.setHeaderLabels(["Glyph", "Cycle", "Doubled in text", "Note"])
        self.alternate_tree.setRootIsDecorated(False)
        self.alternate_tree.setIconSize(QtCore.QSize(ICON_SIZE * 3, ICON_SIZE))
        self.alternate_tree.setWhatsThis(turns)
        self.alternate_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.table_layout(self.alternate_tree)
        part.addWidget(self.alternate_tree, 1)

        part = self.part(QtGui, 2, self.lists, at=0)  # (above the turns: see the turns' part)
        what = (u"Each ligature, what it replaces, and the feature it goes in (pick it to change it). Standard "
                u"ligatures are on unless a user turns them off; discretionary ones off unless turned on.")
        part.addWidget(describe(self.heading(QtGui, u"Ligatures"), what))
        self.ligature_tree = QtGui.QTreeWidget()
        self.ligature_tree.setColumnCount(3)
        self.ligature_tree.setHeaderLabels(["Ligature", "Replaces", "Feature"])
        self.ligature_tree.setRootIsDecorated(False)
        self.ligature_tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.ligature_tree.setWhatsThis(what)
        self.ligature_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        self.ak.table_layout(self.ligature_tree)
        part.addWidget(self.ligature_tree, 1)

        forms_page = QtGui.QWidget()
        box = QtGui.QVBoxLayout(forms_page)
        box.setContentsMargins(0, 0, 0, 0)
        self.forms_label = QtGui.QLabel(u"")
        self.forms_label.setWordWrap(True)
        describe(self.forms_label, u"What the default figures are (tabular or proportional, lining or oldstyle) and "
                                   u"how that was read: the figure features (lnum, onum, pnum, and tnum) are written "
                                   u"from it.")
        box.addWidget(self.forms_label)
        self.forms_label.setVisible(False)  # (shown with something to say: say)
        self.forms_parts = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.forms_parts.setChildrenCollapsible(False)
        box.addWidget(self.forms_parts, 1)
        forms_box = self.part(QtGui, 3, self.forms_parts)
        self.forms_tree = QtGui.QTreeWidget()
        self.forms_tree.setColumnCount(3)
        self.forms_tree.setHeaderLabels(["Feature", "Becomes", "Note"])
        self.forms_tree.setRootIsDecorated(True)
        self.forms_tree.setIconSize(QtCore.QSize(ICON_SIZE * FORM_ICON_WIDTH, ICON_SIZE))
        try:  # a note stays on its row's one line, cut at its end; its cell's tooltip has it whole
            self.forms_tree.setWordWrap(False)
            self.forms_tree.setTextElideMode(QtCore.Qt.ElideRight)
        except Exception:
            pass
        self.forms_tree.setWhatsThis(u"The form features the font's glyph names call for, each with its substitutions "
                                     u"under it (click its arrow). A ticked feature is written, with its ticked "
                                     u"rows; a set's name (the Becomes column of its row) is what applications show, "
                                     u"and you can edit it. Amber rows are warnings to review: they change nothing. "
                                     u"A note too long for its column is whole in its cell's tooltip.")
        self.forms_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.table_layout(self.forms_tree)
        forms_box.addWidget(self.forms_tree, 1)
        self.small_forms, self.small_plans, self.small_info = [], {}, None
        self.small_setup, self.small_first, self.small_set_index = {}, {}, 0
        # The figure forms this window built, by font: {font key: {glyph: {what it was built as (layer_print,
        # every master): the plan it was built from (plan_signature)}}}. A glyph still as one of its builds
        # left it is this tool's to replace (small_ours, read with the font); one edited since is the user's.
        self.built, self.small_ours, self.stems = {}, {}, {}
        self.build_part(QtCore, QtGui, self.part(QtGui, 2, self.forms_parts))
        self.pages.addWidget(forms_page)
        self.alternates = None
        try:  # the Stylistic alternates tab (freelab_alternates.py, beside this script)
            module = self.ak.load_sibling("freelab_alternates.py", "freelab_alternates")
            self.alternates = module.AlternatesPage(self)
            self.pages.addWidget(self.alternates.widget)
        except Exception as exc:
            missing = QtGui.QLabel(u"The Stylistic alternates tab could not be made (%s): reinstall FreeLab." % exc)
            missing.setWordWrap(True)
            self.pages.addWidget(missing)

        part = self.part(QtGui, 1)  # (a quarter at first: the tabs above hold two parts each, live)
        what = (u"The code to be written, feature by feature, not in the font yet: <i>Write the code</i> writes it. "
                u"FreeLab's blocks between their marker lines, the rest "
                u"of each feature as it is; the prefix's language systems first where locl needs some. Keywords, "
                u"tags, glyph classes (@name), glyph lists ([...]), numbers, and comments (#...) are in colors of "
                u"their own; code of more than %s lines is shown plain." % grouped(HIGHLIGHT_LINES))
        # (a line over the heading: it follows a list or the previews of whichever tab is shown, owner's
        # images 234 and 269)
        part.addWidget(self.ak.separator())
        # "Code preview" (owner's image 299: "Code" read as if it were the font's own), the same in every tool
        # that writes feature code
        part.addWidget(describe(self.heading(QtGui, CODE_HEADING), what))
        self.code = QtGui.QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setWhatsThis(what)
        part.addWidget(self.code, 1)
        self.code_text = None  # (what the box shows: not set again unchanged, which would color it again)
        try:  # its colors; without them (a PythonQt that cannot subclass the highlighter) the code shows plain
            self.highlighting = make_highlighter(self.code)
        except Exception:
            self.highlighting = None
        splitters = [self.splitter, self.lists, self.forms_parts]
        if self.alternates is not None and getattr(self.alternates, "parts", None) is not None:
            splitters.append(self.alternates.parts)  # (the third tab's: owner's image 259, it had none)
        for splitter in splitters:  # (once their parts are in)
            describe_handles(splitter, u"Drag the space between two parts up or down to give one more room.")

        layout.addWidget(self.log.widget)
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every ligature's feature, every glyph's, form's, and figure form's "
                                         u"tick, every set's name, and the build settings back as they first came.")
        self.write_button = QtGui.QPushButton("Write the code")
        self.write_button.setWhatsThis(u"Writes the features as shown (liga, dlig, calt, and the ticked forms) to the "
                                       u"font, and the language systems locl needs to its prefix (<i>Update the code</i>: "
                                       u"FreeLab's code is in them already, and changes).")
        self.close_button = QtGui.QPushButton("Close")
        self.close_button.setWhatsThis(u"Closes the window. What was written or built stays in the font; choices "
                                       u"not written are not kept.")
        self.compile_box = self.ak.compile_box()
        layout.addLayout(self.bottom_row(QtGui))
        self.restore_button.connect("clicked()", self.restore)
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", self.ak.close_slot(self))  # (never the window itself: see let_go)
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.look_back.connect("valueChanged(int)", lambda value: self.look_back_changed(value))
        self.ligature_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.alternate_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.alternate_tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.make_code())
        self.alternate_tree.connect("currentItemChanged(QTreeWidgetItem*,QTreeWidgetItem*)",
                                    lambda current, previous: self.turn_picked(current))
        self.forms_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.forms_tree.connect("itemChanged(QTreeWidgetItem*,int)", self.form_checked)
        self.forms_tree.connect("itemExpanded(QTreeWidgetItem*)", self.form_expanded)
        self.package = None
        self.combos = []  # each ligature's feature box, by its index in found (held: PythonQt deletes what Python does not)
        self.name_edits = {}  # each set's name box, by its tag (held likewise)
        self.names, self.letters, self.found, self.sets = [], [], [], {}
        self.others = {}  # the font's figure and punctuation glyphs (glyph_kinds), as self.letters is its letters'
        self.chars, self.often, self.taken = {}, set(), set()  # the glyphs' characters; those often doubled; those with a job
        self.doubles, self.typed = load_doubles(), load_typed_doubles()
        try:  # Auto Kerning's common pairs: the doubled letters of kana, Armenian, and Georgian text among them
            self.pairs = self.ak.common_pairs()
        except Exception:
            self.pairs = {}
        self.busy = False
        self.forms, self.figures, self.checked_code = [], None, {}
        self.texts, self.prefix = {}, u""
        self.ligature_model = load_ligature_model()
        self.ak.add_tools_button(dialog, "Feature Code", getattr(self, "log", None))  # (the other font tools, a click away)
        self.ak.plain_buttons(dialog)
        self.history_timer = self.ak.watch_history(self)
        self.flagging = [self.ak.flag_menu(self.ligature_tree, self, lambda: self.selected_names(self.ligature_tree),
                                           lambda item: self.item_names(self.ligature_tree, item)),
                         self.ak.flag_menu(self.alternate_tree, self, lambda: self.selected_names(self.alternate_tree),
                                           lambda item: self.item_names(self.alternate_tree, item)),
                         self.ak.flag_menu(self.forms_tree, self, lambda: self.selected_names(self.forms_tree),
                                           lambda item: self.item_names(self.forms_tree, item))]
        try:  # the lists' check boxes plain to see in either palette (their pictures stay unmapped)
            trees = [self.alternate_tree, self.forms_tree, self.small_tree]
            if self.alternates is not None:
                trees.append(self.alternates.tree)
            self.check_watcher = watch_check_boxes(
                dialog, trees, (lambda: self.highlighting.refresh()) if self.highlighting is not None else None)
        except Exception:
            self.check_watcher = None

    def bottom_row(self, QtGui):
        """The window's bottom row, as every tool's (owner's images 258, 260, 264): at the left the buttons
        that tick the shown tab's list (the turns' Tick all, Untick all, and Tick often doubled; the third
        tab's Tick all and Untick all), then Restore suggestions; at the right Compile after writing, Write
        the code (or Update the code) right beside it (the tick is about that button: owner's image 298),
        then the shown tab's builds (Build ticked figure forms; Make copies to redraw and Build N variants),
        and Close. Every tab's buttons are in it, those of the tab shown visible (show_tab_buttons): no
        button is left between a list and its splitter handle."""
        row = QtGui.QHBoxLayout()
        left, right = self.tab_buttons()
        for buttons in left:
            for button in buttons:
                row.addWidget(button)
        row.addWidget(self.restore_button)
        row.addStretch(1)
        row.addWidget(self.compile_box)
        row.addWidget(self.write_button)
        for buttons in right:
            for button in buttons:
                row.addWidget(button)
        row.addWidget(self.close_button)
        self.show_tab_buttons(0)
        return row

    def tab_buttons(self):
        """([each tab's buttons for the left of the bottom row], [each tab's for its right]), by tab."""
        page_left, page_right = [], []
        if self.alternates is not None:
            try:
                page_left, page_right = self.alternates.bottom_buttons()
            except Exception:
                page_left, page_right = [], []
        return [list(self.turn_buttons), [], list(page_left)], [[], [self.build_button], list(page_right)]

    def show_tab_buttons(self, index):
        """The bottom row's buttons of the tab shown (by its index), the other tabs' hidden first (the row
        never holds two tabs' buttons at once: owner's image 284, the window grew to fit both)."""
        left, right = self.tab_buttons()
        groups = [list(buttons) + list(right[number]) for number, buttons in enumerate(left)]
        show_only = getattr(self.ak, "show_only", None)
        if show_only is not None:
            show_only(groups, index)
            return
        for number in sorted(range(len(groups)), key=lambda n: n == index):
            for button in groups[number]:
                try:
                    button.setVisible(number == index)
                except Exception:
                    pass

    QUIET_HANDLE = 1  # pixels: a splitter's handle this thin draws no dots (Fusion), and Qt still takes drags 5 wide

    def quiet_handle(self, quiet):
        """The handle between the tabs and the code drawn as nothing while the third tab is shown, still
        dragged where it was (the pointer shows it): under that tab's two previews, the dotted handle met
        the line between them (the review of November 23, image 11). The handle is made one pixel thin,
        which Fusion draws no dots for, and Qt then takes drags on five pixels around it; given its own
        width back with another tab, and the shape Qt cut it to for the thin one taken off (Qt leaves that
        mask on a handle made wide again: only a sliver of it would draw and take the mouse). Never raises."""
        try:
            if getattr(self, "handle_width", None) is None:
                width = getattr(self.splitter, "handleWidth", None)
                self.handle_width = int(width() if callable(width) else width)
            wanted = self.QUIET_HANDLE if quiet else self.handle_width
            now = getattr(self.splitter, "handleWidth", None)
            if int(now() if callable(now) else now) == wanted:
                return
            self.splitter.setHandleWidth(wanted)
            if not quiet:
                for index in range(1, self.splitter.count()):
                    handle = self.splitter.handle(index)
                    handle.clearMask()
                    handle.setContentsMargins(0, 0, 0, 0)
        except Exception:
            pass

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        self.show_tab_buttons(index)
        self.quiet_handle(self.alternates is not None and index == ALTERNATES_TAB)
        share = getattr(self.ak, "share_splitters", None)
        if share is not None:
            share(self.dialog)  # (a tab hidden at first show: its splitters sized in their shares as it shows)

    def link_activated(self, link):
        """A link of a label clicked: "tab:2" opens that tab (the tab bar's signal shows its page); "read:"
        reads the font again (after a read stopped)."""
        try:
            link = u"%s" % link
            if link.startswith(u"tab:"):
                index = int(link[4:])
                self.tabs.setCurrentIndex(index)
                self.switch_page(index)  # (shown whether or not the bar's signal comes: it was the current tab)
            elif link.startswith(u"read:"):  # (the top line's, after a read stopped: read_stopped)
                self.run()
        except Exception:
            pass  # a signal's handler must not raise

    def selected_names(self, tree):
        QtCore, QtGui = _qt()
        items = tree.selectedItems()
        if not items:
            return []
        return self.item_names(tree, items[0])

    def item_names(self, tree, item):
        """A row's glyphs (a ligature; a glyph and its forms; a form's glyphs): their flags shown."""
        QtCore, QtGui = _qt()
        if tree is self.ligature_tree:
            index = int(item.data(0, QtCore.Qt.UserRole))
            return [self.found[index].glyph] if 0 <= index < len(self.found) else []
        if tree is self.forms_tree:
            rule = self.form_rule(item)
            return list(rule.glyphs) if rule is not None else []
        base = u"%s" % item.data(0, QtCore.Qt.UserRole)
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
        package = self.ak.window_font(self, workspace)  # this window's font
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def log_source(self):
        """(fontlab, the font the window shows, its current master), for the log's glyph links."""
        package = getattr(self, "package", None)
        return self.fontlab, package, package.master if package is not None else None

    def set_busy(self, on, what=u"", stoppable=True):
        """Long work under way (or over), in the window's top row (ak.busy_start: what, the step's name, and
        a bar; owner's image 180): while it runs, no click or key reaches the window or FontLab but the tools
        menu's, the arrows', Close's, and Esc, which stop it at its next step when stoppable (a read), and are
        done once it is over (a write: never stopped half way). The lists take no clicks meanwhile, the
        buttons under them do nothing (each action checks busy), and ak.watch_history waits on busy too."""
        was, self.busy = self.busy, bool(on)
        try:
            self.splitter.setEnabled(not on)
        except Exception:
            pass
        if on and not was:
            self.ak.busy_start(self, what, stoppable=stoppable)
        elif was and not on:
            self.ak.busy_end(self)

    def progress(self, what, done=None, total=None, force=False, stoppable=True):
        """Long work's progress in the window's top row (what: "Building variants"; done of total, when
        counted), the window redrawn at most every 0.1 s (ak.busy_progress). Raises ak.Stopped when the user
        asked the work to stop, unless stoppable is False (a write)."""
        self.ak.busy_progress(self, what, (float(done) / total) if total else None, force=force, stoppable=stoppable)

    def run(self):
        """The font read again, unless long work is under way (a click the window answered meanwhile). A read
        stopped by the user (the tools menu, an arrow, Close, Esc) leaves nothing listed and nothing to
        write (read_stopped)."""
        if self.busy:
            return
        self.set_busy(True, u"Reading the font")
        stopped = False
        try:
            self.read_font()
        except self.ak.Stopped:
            stopped = True
        finally:
            self.set_busy(False)
            try:  # (the ligatures' rows shown again whatever stopped the read: read_font hides them as it fills)
                self.ak.quiet_list(self.ligature_tree, False)
            except Exception:
                pass
        if stopped:
            self.read_stopped()

    def read_stopped(self):
        """A read stopped by the user: what it listed so far let go, nothing listed and nothing to write or
        build (no font read: the shared module grays what acts on one), the top line saying so, with a link
        that reads the font again (link_activated). Never raises."""
        for tree in (self.ligature_tree, self.alternate_tree, self.forms_tree):
            try:
                tree.blockSignals(False)  # (a stop inside a filling: its signals held)
                tree.clear()
            except Exception:
                pass
        self.combos, self.name_edits = [], {}
        read = self.package
        self.package = None
        try:
            self.empty_views()
            self.show_font_line(read)  # (the top line still names the font: owner's image 224)
            self.status.setText(u"Reading the font was stopped: nothing is listed. <a href=\"read:\">Read it</a>")
            self.log.add(u"Reading the font was stopped: nothing is listed.", "warning")
        except Exception:
            pass

    def empty_views(self):
        """Nothing of a font stays (its code, its turns' line, the third tab's list), and nothing that acts
        on a font takes a click: the turns' buttons and look back, the build's settings (no font, or a read
        stopped)."""
        say(self.forms_label, u"")
        self.forms, self.figures = [], None
        self.names, self.letters, self.found, self.sets, self.others = [], [], [], {}, {}
        self.chars, self.often, self.taken, self.texts, self.prefix = {}, set(), set(), {}, u""
        self.first_choices, self.first_checks = [], []
        self.show_code(u"")
        self.show_turns({})
        self.small_forms, self.small_plans, self.small_info = [], {}, None
        self.show_small_forms()
        if self.alternates is not None:
            try:
                self.alternates.fill()
            except Exception:
                pass

    def read_font(self):
        QtCore, QtGui = _qt()
        kept = self.small_state()  # (the builds' checks and settings, kept for the same font)
        turns = self.turn_state()  # (and the characters checked to take turns)
        package = self.package = self.current_font()
        if kept is not None and (package is None or self.ak.font_key(package) != kept[0]):
            kept = None
        if turns is not None and (package is None or self.ak.font_key(package) != turns[0]):
            turns = None
        self.small_kept = kept
        self.ligature_tree.clear()  # (its boxes go with its rows)
        self.combos = []
        self.alternate_tree.clear()
        self.forms_tree.clear()
        self.name_edits = {}
        self.forms, self.figures = [], None
        self.write_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        if package is None:
            # (the window takes the next font opened: ak.fonts_tick, then font_changed)
            self.show_font_line()
            self.status.setText(u"")
            self.empty_views()
            return
        self.show_font_line()  # (the font named from the start, whatever happens next: owner's image 224)
        glyphs = list(package.fgPackage.glyphs)
        self.names = [g.name for g in glyphs]
        codes = dict((g.name, self.ak.main_code(g)) for g in glyphs)  # (not a radical it is encoded at too)
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        try:
            self.prefix = features.get_prefix() or u""
        except Exception:
            self.prefix = u""

        def takes_turns(name):  # a letter's, a figure's, or a punctuation mark's glyph
            code = codes.get(name)
            return bool(code) and char_kind(unichr_(code)) is not None

        self.progress(u"Reading the font", force=True)
        kinds = glyph_kinds(self.names, codes)
        self.letters = kinds[LETTERS]
        self.others = dict((kind, kinds[kind]) for kind in KINDS[1:])
        self.found = ligatures(self.names, self.texts,
                               dict((name, unichr_(code)) for name, code in codes.items() if code), self.ligature_model)
        self.sets = alternate_sets(self.names, takes_turns)
        bold = QtGui.QFont(self.ligature_tree.font)
        bold.setBold(True)
        self.ligature_tree.blockSignals(True)
        # Owner's image 221: while the rest of the font was read, the Feature column's boxes stood over the
        # Replaces column. Each box is placed where its cell is when it is set, and the first two columns
        # were sized to their contents after the boxes were in: the boxes kept their old place until Qt laid
        # the list out again, after the read. So the rows come first, the columns are sized to them, and
        # only then are the boxes set, the list laid out at once (place_cell_widgets); the list's rows stay
        # hidden meanwhile (ak.quiet_list: the window repaints during the read).
        quiet = getattr(self.ak, "quiet_list", None)
        if quiet is not None:
            quiet(self.ligature_tree, True)
        items = []
        for index, lig in enumerate(self.found):
            item = QtGui.QTreeWidgetItem([lig.glyph, u" ".join(lig.parts), u""])
            item.setFont(0, bold)
            item.setData(0, QtCore.Qt.UserRole, index)
            icon = self.picture([lig.glyph])
            if icon is not None:
                item.setIcon(0, self.ak.icon_of(icon))
            item.setToolTip(1, u"Now: %s." % (dict(CHOICES)[lig.now] if lig.now else u"in no feature"))
            item.setToolTip(2, u"Its feature. First set by %s." % (lig.why or u"default"))
            self.ligature_tree.addTopLevelItem(item)
            items.append(item)
        self.ligature_tree.resizeColumnToContents(0)
        self.ligature_tree.resizeColumnToContents(1)
        for lig, item in zip(self.found, items):
            combo = self.ak.flat_combo(QtGui.QComboBox())
            for _, label in CHOICES:
                combo.addItem(label)
            # (its own What's This: without one, a right-click answered with the list's)
            describe(combo, u"The feature this ligature goes in: <i>Standard</i> (liga), <i>Discretionary</i> "
                            u"(dlig), or <i>Off</i> (neither). First set by %s." % self.ak.html(lig.why or u"default"), True)
            combo.connect("currentIndexChanged(int)", lambda choice, lig=lig: self.choose(lig, choice))
            self.ligature_tree.setItemWidget(item, 2, combo)
            self.combos.append(combo)
            self.show_choice(item, lig)
        place_cell_widgets(self.ligature_tree)
        if quiet is not None:
            quiet(self.ligature_tree, False)  # (before the read's next step, which a stop may end)
        self.first_choices = [lig.choice for lig in self.found]
        self.ligature_tree.blockSignals(False)
        self.alternate_tree.blockSignals(True)
        used = used_in([name for forms in self.sets.values() for name in forms], self.texts)
        self.chars = dict((base, unichr_(codes[base])) for base in self.sets if codes.get(base))
        self.often = set(base for base in self.sets if self.doubled(self.chars.get(base)))
        self.taken = set(base for base in self.sets if any(name in used for name in self.sets[base]))
        order = turn_order(self.sets, self.chars, self.doubles, self.pairs, self.typed)
        first = first_turns(self.sets, order, self.often, self.taken, self.look_back.value) | \
            turns_written(self.sets, self.texts.get("calt"))
        checks = dict((base, base in first) for base in order)
        if turns is not None:  # the same font read again (after a build, a write, an undo): its checks kept
            checks.update((base, on) for base, on in turns[1].items() if base in checks and base not in self.taken)
        for row, base in enumerate(order):
            forms = [base] + self.sets[base]
            jobs = [u"%s in %s" % (name, u", ".join(used[name])) for name in self.sets[base] if name in used]
            note = (u"The font's code uses %s already: left out, so as not to undo it." % u"; ".join(jobs)) if jobs else u""
            doubled, how_often = double_words(self.chars.get(base), self.doubles, self.pairs, self.typed)
            item = QtGui.QTreeWidgetItem([base, u", ".join(forms), doubled, note])
            item.setFont(0, bold)
            item.setData(0, QtCore.Qt.UserRole, base)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if checks[base] else QtCore.Qt.Unchecked)
            item.setToolTip(2, tip_html(how_often))
            item.setToolTip(3, tip_html(note))
            if row < TURN_PICTURES:  # (a picture per row of a whole alphabet took seconds: the rest when clicked)
                icon = self.picture(forms)
                if icon is not None:
                    item.setIcon(1, self.ak.icon_of(icon))
            else:
                item.setToolTip(1, TURN_PICTURE_TIP)
            self.alternate_tree.addTopLevelItem(item)
            if row % 50 == 49:
                self.progress(u"Listing the glyphs with alternates", row + 1, len(order))
        self.alternate_tree.blockSignals(False)
        self.first_checks = [base in first for base in order]  # (what Restore suggestions puts back)
        for column in (0, 1, 2):  # (the ligatures' columns were sized before their boxes were set)
            self.alternate_tree.resizeColumnToContents(column)
        self.checked_code = {}
        self.progress(u"Reading the forms", force=True)
        self.read_forms(glyphs)
        self.make_code()
        if self.alternates is not None:
            try:
                self.alternates.fill()
            except Exception as exc:
                self.log.add(u"The Stylistic alternates tab could not be read: %s" % self.ak.html(exc), "error")
        place_cell_widgets(self.ligature_tree)  # (and again once the whole font is read: the window may have moved)
        self.seen_history = self.ak.history_mark(package)

    # -- forms --------------------------------------------------------------------------

    def read_forms(self, glyphs):
        """The form features of the font, in their tree: a row per feature, its rules under it."""
        QtCore, QtGui = _qt()
        codes = {}
        for glyph in glyphs:
            values = []
            try:
                values = [code for code in (glyph.unicodes or []) if code]
            except Exception:
                values = []
            if not values and glyph.unicode:
                values = [glyph.unicode]
            codes[glyph.name] = values
        info = FontInfo(self.names, codes, *self.measures(codes))
        try:
            self.forms, self.figures = form_features(info, self.texts)
        except Exception as exc:  # a font the builders did not foresee: the ligatures still work
            self.forms, self.figures = [], None
            self.log.add(u"The forms could not be read: %s" % self.ak.html(exc), "error")
        self.read_small_forms(info)
        tree = self.forms_tree
        tree.blockSignals(True)
        for feature in self.forms:
            # (plain: a list's cell shows markup as typed, "<i>Glyphs</i>")
            item = QtGui.QTreeWidgetItem([feature.tag, u"", plain(u" ".join(t for t in (feature.kind_note, feature.note) if t))])
            self.ak.section_row(item, tree)
            even_row(QtCore, item)  # (a feature's row as high as the rows with pictures, not a heading's line)
            item.setData(0, QtCore.Qt.UserRole, feature.tag)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if feature.on else QtCore.Qt.Unchecked)
            item.setToolTip(0, u"%s (%s): %s." % (feature.title(), feature.tag, counted(len(feature.rules), u"row")))
            item.setToolTip(2, tip_html(item.text(2)))  # (the note whole, wrapped: its cell cuts it at the column's edge)
            if feature.tag not in SET_TAGS:
                item.setText(1, u"%s (%d)" % (feature.title(), len(feature.rules)))
            tree.addTopLevelItem(item)
            for rule in feature.rules:
                child = QtGui.QTreeWidgetItem([rule.source, rule.target, plain(rule.note)])
                even_row(QtCore, child)  # (with a picture or without: "its alternates (Superscript)" has none)
                child.setData(0, QtCore.Qt.UserRole, u"%s\t%s" % (feature.tag, rule.key))
                child.setToolTip(2, tip_html(plain(rule.note)))
                if rule.warning:
                    child.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    self.warning_colors(child)
                else:
                    child.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    child.setCheckState(0, QtCore.Qt.Checked if rule.on else QtCore.Qt.Unchecked)
                item.addChild(child)
            if feature.tag in SET_TAGS:
                edit = QtGui.QLineEdit(feature.name or u"")
                edit.setFrame(False)
                if feature.hand_name:
                    edit.setReadOnly(True)
                    describe(edit, u"The name the font's own code gives this set: edit it there.", True)
                else:
                    describe(edit, u"The set's name, as applications show it (suggested from what it changes): "
                                   u"edit it as you like.", True)
                edit.connect("textEdited(QString)", lambda text, feature=feature: self.rename(feature, text))
                tree.setItemWidget(item, 1, edit)
                self.name_edits[feature.tag] = edit
        tree.blockSignals(False)
        tree.resizeColumnToContents(0)
        try:  # room for an open feature's rows: sized while they are closed, the column cut their check boxes
            sources = [rule.source for feature in self.forms for rule in feature.rules]
            try:
                measure = QtGui.QFontMetrics(tree.font).width
            except Exception:
                measure = None
            least = form_column_width(tree.indentation, sources, measure)
            if tree.columnWidth(0) < least:
                tree.setColumnWidth(0, least)
        except Exception:
            pass
        tree.setColumnWidth(1, max(tree.columnWidth(1), ICON_SIZE * FORM_ICON_WIDTH + 160))
        if self.figures:
            say(self.forms_label, u"The default figures are %s (by %s). %s" % (
                self.ak.b(describe_style(*self.figures[:2])), self.ak.html(self.figures[2]),
                u"Click a feature's arrow for its rows." if self.forms else u""))
        if not self.forms:
            say(self.forms_label, u"No glyph is named for a form feature (.case, .sc, .numr, .ss01...): "
                                  u"nothing to write here.")

    def measures(self, codes):
        """(widths, bounds, contours) the form builders use: the advance widths and ink of the figures and
        their forms, the Unicode superscript and subscript figures, a, o, and the ordinal indicators, and
        the contours' boxes of a, g, and their alternates (read in the current master; any that cannot be
        read are left out)."""
        widths, bounds, contours = {}, {}, {}
        master = self.package.master
        wanted = []
        small = set(unichr_(code) for code in SUPERSCRIPT_FIGURES + SUBSCRIPT_FIGURES + (0xAA, 0xBA))
        for name in self.names:
            stem = name.split(u".")[0]
            code = codes.get(stem) or codes.get(name)
            char = unichr_(code[0]) if code else None
            if char and (char in DIGITS or char in (u"a", u"g", u"o") or char in small):
                wanted.append((name, char))
        for name, char in wanted:
            try:
                glyph = self.package.findName(name)
                layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
                if layer is None:
                    continue
                widths[name] = layer.advanceWidth
                path = self.ak.layer_path(layer)
                rect = path.boundingRect()
                bounds[name] = (rect.left(), rect.top(), rect.right(), rect.bottom())  # font units grow upward
                if char in (u"a", u"g"):
                    contours[name] = self.contour_boxes(layer)
            except Exception:
                continue
        return widths, bounds, contours

    def contour_boxes(self, layer):
        boxes = []
        for shape in layer.shapes:
            transform = shape.transform
            for contour in shape.contours:
                if contour is None:
                    continue
                rect = transform.map(contour.path()).boundingRect()
                boxes.append((rect.left(), rect.top(), rect.right(), rect.bottom()))
        return boxes

    def warning_colors(self, item):
        QtCore, QtGui = _qt()
        try:
            base = self.forms_tree.palette.color(QtGui.QPalette.Base)
            rgb = self.ak.LOG_COLORS["warning"][0 if base.lightness() < 128 else 1]
            for column in range(3):
                item.setForeground(column, QtGui.QBrush(QtGui.QColor(rgb[0], rgb[1], rgb[2])))
        except Exception:
            pass

    def form_rule(self, item):
        """The rule of a form's row, or None (a feature's row)."""
        QtCore, QtGui = _qt()
        key = u"%s" % item.data(0, QtCore.Qt.UserRole)
        tag, _, rule_key = key.partition(u"\t")
        feature = self.form_feature(tag)
        if feature is None or not rule_key:
            return None
        for rule in feature.rules:
            if rule.key == rule_key:
                return rule
        return None

    def form_feature(self, tag):
        for feature in self.forms:
            if feature.tag == tag:
                return feature
        return None

    def form_checked(self, item, column):
        """A feature's or a row's check changed."""
        QtCore, QtGui = _qt()
        if column != 0:
            return
        on = item.checkState(0) == QtCore.Qt.Checked
        rule = self.form_rule(item)
        if rule is not None:
            if rule.on != on:
                rule.on = on
                self.make_code()
            return
        feature = self.form_feature(u"%s" % item.data(0, QtCore.Qt.UserRole))
        if feature is not None and feature.on != on:
            feature.on = on
            self.make_code()

    def form_expanded(self, item):
        """A feature opened: its rows' pictures drawn now (not for every row of the font at once)."""
        QtCore, QtGui = _qt()
        if item.data(1, QtCore.Qt.UserRole):
            return
        self.forms_tree.blockSignals(True)
        try:
            item.setData(1, QtCore.Qt.UserRole, True)
            for index in range(item.childCount()):
                child = item.child(index)
                rule = self.form_rule(child)
                icon = self.picture(rule.glyphs[:FORM_ICON_WIDTH]) if rule is not None else None
                if icon is not None:
                    child.setIcon(1, self.ak.icon_of(icon))
        except Exception:
            pass
        finally:
            self.forms_tree.blockSignals(False)

    def rename(self, feature, text):
        name = u"%s" % text
        if name.strip() != (feature.name or u"").strip():
            feature.name = name.strip() or None
            self.make_code()

    def form_state(self):
        """The forms' choices, to keep across a fresh look at the font."""
        return dict((feature.tag, (feature.on, feature.name, dict((rule.key, rule.on) for rule in feature.rules)))
                    for feature in self.forms)

    def apply_form_state(self, state):
        QtCore, QtGui = _qt()
        for feature in self.forms:
            kept = state.get(feature.tag)
            if kept is None:
                continue
            feature.on = kept[0]
            if not feature.hand_name:
                feature.name = kept[1]
            for rule in feature.rules:
                if rule.key in kept[2] and not rule.warning:
                    rule.on = kept[2][rule.key]
        self.show_forms()

    def show_forms(self):
        """Every form row's check and every set's name as the model has them (rows found again by walking
        the tree)."""
        QtCore, QtGui = _qt()
        tree = self.forms_tree
        tree.blockSignals(True)
        try:
            for row in range(tree.topLevelItemCount):
                item = tree.topLevelItem(row)
                feature = self.form_feature(u"%s" % item.data(0, QtCore.Qt.UserRole))
                if feature is None:
                    continue
                item.setCheckState(0, QtCore.Qt.Checked if feature.on else QtCore.Qt.Unchecked)
                for index in range(item.childCount()):
                    child = item.child(index)
                    rule = self.form_rule(child)
                    if rule is not None and not rule.warning:
                        child.setCheckState(0, QtCore.Qt.Checked if rule.on else QtCore.Qt.Unchecked)
                edit = self.name_edits.get(feature.tag)
                if edit is not None and (u"%s" % edit.text) != (feature.name or u""):
                    edit.setText(feature.name or u"")
        finally:
            tree.blockSignals(False)

    def forms_changed(self):
        return any(feature.on != feature.first_on or feature.name != feature.first_name
                   or any(rule.on != rule.first_on for rule in feature.rules) for feature in self.forms)

    def locl(self):
        for feature in self.forms:
            if feature.tag == "locl":
                return feature
        return None

    def new_prefix(self):
        """The prefix with the language systems the checked locl rows need, or None where it stays."""
        systems = language_systems(self.locl())
        if not systems and (BEGIN % LANGUAGES_BLOCK) not in self.prefix:
            return None
        text = prefix_text(self.prefix, systems)
        return text if text != self.prefix else None

    # -- figure forms to build ----------------------------------------------------------

    def build_part(self, QtCore, QtGui, part):
        """The Forms tab's lower part: the figure forms the font lacks, their settings, and the build."""
        listed = (u"The figure forms the font lacks, by set (click a set's arrow): each glyph, what it would be made "
                  u"of, drawn beside its figure, and its code point. Ticked ones are built (<i>Build ticked figure "
                  u"forms</i>, in the bottom row).")
        part.addWidget(self.ak.separator())  # (a line over the heading: not a caption of the list above, image 234)
        part.addWidget(describe(self.heading(QtGui, u"Figure forms to build"), listed))
        self.small_label = QtGui.QLabel(u"")
        self.small_label.setWordWrap(True)
        describe(self.small_label, u"How many figure forms the font lacks, and how each is made: of its figure, scaled "
                                   u"and moved (its strokes kept as <i>Strokes</i> says), or of a drawn small figure "
                                   u"where the font has a whole set of them.")
        part.addWidget(self.small_label)
        self.small_label.setVisible(False)  # (an empty line under the heading, owner's image 197: say)
        # One row for every setting. Scale, Baseline at, and Width are the picked set's; Strokes is one value
        # for every set (it stood alone under the list, which said so by its place only: its What's This says
        # it now); Suggested, last, puts the four back.
        row = QtGui.QHBoxLayout()
        what = u"The set whose settings the boxes beside show and change (clicking a row picks its set)."
        # (label form, the same in every tool: a noun naming the setting, a colon, the control; owner's image 271)
        row.addWidget(label_of(QtGui, u"Set:", what))
        self.small_set = QtGui.QComboBox()
        for key in SMALL_SETS:
            self.small_set.addItem(SMALL_SET_TITLES[key])
        self.small_set.setWhatsThis(what)
        fit_combo(QtGui, self.small_set)
        row.addWidget(self.small_set)
        what = (u"The size of the set's glyphs, of their figure's (or letter's). Numerators and ordinal indicators "
                u"keep their top where it is; the others their baseline.")
        row.addWidget(label_of(QtGui, u"Scale:", what))
        self.small_scale = QtGui.QSpinBox()
        self.small_scale.setRange(20, 95)
        self.small_scale.setSuffix(u"%")
        self.small_scale.setWhatsThis(what)
        row.addWidget(self.small_scale)
        what = u"Where the scaled figure's baseline goes, in font units above the font's baseline (below it, negative)."
        row.addWidget(label_of(QtGui, u"Baseline:", what))
        self.small_baseline = QtGui.QSpinBox()
        self.small_baseline.setRange(-3000, 3000)
        self.small_baseline.setSuffix(units_suffix(0))  # (follows its number: show_baseline_suffix)
        self.small_baseline.setWhatsThis(what)
        row.addWidget(self.small_baseline)
        what = (u"The advance width, of the scaled figure's: above 100%, a little more room around the small figure "
                u"(most open-licensed fonts give them 112%).")
        row.addWidget(label_of(QtGui, u"Width:", what))
        self.small_width = QtGui.QSpinBox()
        self.small_width.setRange(50, 200)
        self.small_width.setSuffix(u"%")
        self.small_width.setWhatsThis(what)
        row.addWidget(self.small_width)
        what = (u"For every set, not only the one picked: how thick the built forms' strokes are, as a share of "
                u"their scaled figure's. Scaling a figure to 60%% thins its strokes to 60%%; drawn small figures are "
                u"about 7%% bolder than scaled ones (the corpus's fonts), hence %d%%. Above 100%%, each scaled form is "
                u"made of outlines (not components), offset outward evenly on both sides of each stroke; 100%%: "
                u"components, scaled, as they are. <i>Suggested</i>, after it, puts it back at %d%% too." % (
                    STROKE_WEIGHT, STROKE_WEIGHT))
        row.addWidget(label_of(QtGui, u"Strokes:", what))
        self.stroke_box = QtGui.QSpinBox()
        self.stroke_box.setRange(100, 160)
        self.stroke_box.setSuffix(u"%")
        self.stroke_box.setValue(STROKE_WEIGHT)
        self.stroke_box.setWhatsThis(what)
        row.addWidget(self.stroke_box)
        # (planned again: the open sections' pictures show the strokes, and the build's count follows)
        self.stroke_box.connect("valueChanged(int)", lambda value: self.replan())
        # Suggested last: it puts back every setting before it, Strokes too (owner's report 158: changing
        # Strokes did not make it clickable, as it stood before Strokes and left it as it was)
        self.small_reset = QtGui.QPushButton(u"Suggested")
        describe(self.small_reset, suggested_words(None), True)  # (where the suggestion comes from: small_set_picked)
        row.addWidget(self.small_reset)
        row.addStretch(1)
        part.addLayout(row)
        self.small_tree = QtGui.QTreeWidget()
        self.small_tree.setColumnCount(3)
        self.small_tree.setHeaderLabels(["Glyph", "Made of", "Note"])
        self.small_tree.setRootIsDecorated(True)
        self.small_tree.setIconSize(QtCore.QSize(ICON_SIZE * 2, ICON_SIZE))
        self.small_tree.setWhatsThis(listed)
        self.small_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.table_layout(self.small_tree)
        part.addWidget(self.small_tree, 1)  # (the last of its part: the splitter's handle right under its frame)
        # The build goes in the window's bottom row (bottom_row), shown with the Forms tab: under the list,
        # it stood between the list and the splitter's handle (owner's image 258)
        self.build_button = QtGui.QPushButton(build_label(0))
        describe(self.build_button, build_words(0, 0), True)  # (why it is grayed out: update_small_buttons)
        self.build_button.setEnabled(False)
        self.small_set.connect("currentIndexChanged(int)", self.small_set_picked)
        self.small_scale.connect("valueChanged(int)", lambda value: self.small_setting("scale", value))
        self.small_baseline.connect("valueChanged(int)", lambda value: self.small_setting("baseline", value))
        self.small_baseline.connect("valueChanged(int)", lambda value: self.show_baseline_suffix())
        self.small_width.connect("valueChanged(int)", lambda value: self.small_setting("width", value))
        self.small_reset.connect("clicked()", self.small_suggested)
        self.small_tree.connect("itemChanged(QTreeWidgetItem*,int)", self.small_checked)
        self.small_tree.connect("itemExpanded(QTreeWidgetItem*)", self.small_expanded)
        self.small_tree.connect("itemClicked(QTreeWidgetItem*,int)", self.small_clicked)
        self.build_button.connect("clicked()", self.build_small_forms)

    def small_state(self):
        """(the font's key, {name: checked}, the settings) of the builds, or None before a font is read."""
        if getattr(self, "package", None) is None or not self.small_setup:
            return None
        try:
            key = self.ak.font_key(self.package)
        except Exception:
            return None
        return key, dict((form.name, form.on) for form in self.small_forms), \
            dict((set_key, dict(setting)) for set_key, setting in self.small_setup.items())

    def drawn_in_ink(self, name):
        """A glyph a figure form can be scaled from: outlines in the current master, in one ink (an emoji
        font's blank keycap figures and its color glyphs are not)."""
        try:
            glyph = self.package.findName(name)
            layer = glyph.getLayerByName(self.package.master) if glyph is not None and not glyph.isNull else None
            if layer is None or self.ak.is_picture_layer(layer) or self.ak.layer_parts(layer) is not None:
                return False
            return not self.ak.layer_path(layer, False).isEmpty()
        except Exception:
            return True  # (unknown: left to the builder, as before)

    def read_small_forms(self, info):
        """The figure forms the font lacks, and their first settings (those kept from the last read of
        the same font where there are some)."""
        self.small_info = info
        cap = None
        try:
            cap = float(self.package.capsHeight_value)
        except Exception:
            cap = None
        try:
            upm = float(self.package.upm)
        except Exception:
            upm = 1000.0
        # The forms this window built and nobody changed since are listed again, as if the font lacked
        # them: a build replaces them (the owner: the button grayed out after a build, where it should
        # stay and replace what it made once a value changes)
        self.stems = {}  # (the figures' strokes measured again: the font may have changed)
        self.small_ours = self.own_built(self.package) if self.package is not None else {}
        info = self.small_info = without_glyphs(info, self.small_ours)
        try:
            self.small_forms = [form for form in missing_small_forms(info) if self.drawn_in_ink(form.base)]
            self.small_first = small_settings(info, cap, upm)
        except Exception as exc:  # a font the builders did not foresee: the rest still works
            self.small_forms, self.small_first = [], {}
            self.log.add(u"The figure forms to build could not be read: %s" % self.ak.html(exc), "error")
        self.small_setup = dict((key, dict(setting)) for key, setting in self.small_first.items())
        kept = getattr(self, "small_kept", None)
        if kept is not None:
            for form in self.small_forms:
                form.on = kept[1].get(form.name, form.on)
            for key, setting in kept[2].items():
                if key in self.small_setup:
                    self.small_setup[key].update((k, setting[k]) for k in ("scale", "baseline", "width"))
        self.show_small_forms()

    def small_form(self, name):
        for form in self.small_forms:
            if form.name == name:
                return form
        return None

    def show_small_forms(self):
        """The build list made again: a section per set the font lacks forms of, a row per form."""
        QtCore, QtGui = _qt()
        tree = self.small_tree
        tree.blockSignals(True)
        try:
            tree.clear()
            for group, set_key, title in SMALL_GROUPS:
                forms = [form for form in self.small_forms if form.group == group]
                if not forms:
                    continue
                item = QtGui.QTreeWidgetItem([title, u"", u""])
                self.ak.section_row(item, tree)
                item.setData(0, QtCore.Qt.UserRole, group)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if any(form.on for form in forms) else QtCore.Qt.Unchecked)
                tree.addTopLevelItem(item)
                # (not spanned: its count and note stand in the other columns, as every other list's groups'
                # do; spanned, a folded group showed nothing there, owner's report 159. Its title is whole:
                # the first column is sized to it below.)
                for form in forms:
                    child = QtGui.QTreeWidgetItem([form.name, u"", u""])
                    child.setData(0, QtCore.Qt.UserRole, u"\t" + form.name)
                    child.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                    child.setCheckState(0, QtCore.Qt.Checked if form.on else QtCore.Qt.Unchecked)
                    item.addChild(child)
            tree.resizeColumnToContents(0)
            try:  # room for a row's indent, its check box, and its picture at least
                least = tree.indentation * 2 + 24 + tree.iconSize.width() + 40
                if tree.columnWidth(0) < least:
                    tree.setColumnWidth(0, least)
            except Exception:
                pass
        finally:
            tree.blockSignals(False)
        if self.package is None:
            say(self.small_label, u"")
        elif self.small_forms:
            say(self.small_label,
                u"%s Each is made of its figure (or <i>a</i> or <i>o</i>), scaled and moved, or of "
                u"a drawn small figure where the font has a whole set of them. Scaling alone thins the strokes (a "
                u"figure at 60%% has stems 60%% as thick); with <i>Strokes</i> above 100%%, the form is made of "
                u"outlines thickened evenly to that share of the scaled strokes (drawn small figures are about 7%% "
                u"bolder than scaled ones: 107%%), at 100%% of components. A start to refine, not a drawing. Built, the "
                u"features above take them." % self.small_counts())
        elif self.small_info is not None and not any(self.small_info.figures()):
            say(self.small_label, u"The font has no figures 0 to 9 to build small forms of.")
        else:
            say(self.small_label, u"The font has every figure form FreeLab builds: numerators, denominators, "
                                  u"superiors, inferiors, their Unicode characters, and the ordinal indicators.")
        self.small_set_picked(self.small_set_index)
        self.replan()

    def small_counts(self):
        """The build list's first sentence: what the font lacks, and what this window built before
        (listed again: a build replaces it once its settings change)."""
        b = self.ak.b
        ours = sum(1 for form in self.small_forms if form.name in self.small_ours)
        lacking = len(self.small_forms) - ours
        words = (u"The font lacks %s." % b(counted(lacking, u"figure form"))) if lacking else u""
        if ours:
            one = ours == 1
            words += (u" " if words else u"") + u"%s %s built here before: a build replaces %s once %s settings " \
                u"change." % (b(counted(ours, u"figure form")), u"was" if one else u"were", u"it" if one else u"them",
                              u"its" if one else u"their")
        return words

    def replan(self):
        """The forms planned again (a check or a setting changed): each row's words, and the pictures of
        the open sections."""
        QtCore, QtGui = _qt()
        try:
            self.small_plans = plan_small_forms(self.small_info, self.small_forms, self.small_setup) \
                if self.small_info is not None and self.small_forms else {}
        except Exception as exc:
            self.small_plans = {}
            self.log.add(u"The figure forms could not be planned: %s" % self.ak.html(exc), "error")
        tree = self.small_tree
        tree.blockSignals(True)
        try:
            for row in range(tree.topLevelItemCount):
                item = tree.topLevelItem(row)
                group = u"%s" % item.data(0, QtCore.Qt.UserRole)
                on = sum(1 for form in self.small_forms if form.group == group and form.on)
                total = sum(1 for form in self.small_forms if form.group == group)
                item.setText(1, u"%s of %s ticked" % (grouped(on), counted(total, u"glyph")))
                note = group_note([form for form in self.small_forms if form.group == group], self.small_plans,
                                  self.small_ours)
                item.setText(2, note)
                item.setToolTip(2, note)
                for index in range(item.childCount()):
                    child = item.child(index)
                    form = self.small_form((u"%s" % child.data(0, QtCore.Qt.UserRole))[1:])
                    if form is not None:
                        plan = self.small_plans.get(form.name)
                        words = describe_placement(plan)
                        child.setText(1, words)
                        child.setToolTip(1, words)
                        note = u"; ".join(text for text in (
                            u"U+%04X %s" % (form.code, unichr_(form.code)) if form.code else u"",
                            SMALL_NOTES.get(plan.how if plan is not None else None, u""),
                            BUILT_NOTE if form.name in self.small_ours else u"") if text)
                        child.setText(2, note)
                        child.setToolTip(2, note)
                if item.data(1, QtCore.Qt.UserRole):
                    self.small_pictures(item)
        finally:
            tree.blockSignals(False)
        self.update_small_buttons()

    def small_expanded(self, item):
        """A set opened: its rows' pictures drawn now."""
        QtCore, QtGui = _qt()
        self.small_tree.blockSignals(True)
        try:
            item.setData(1, QtCore.Qt.UserRole, True)
            self.small_pictures(item)
        except Exception:
            pass
        finally:
            self.small_tree.blockSignals(False)

    def small_pictures(self, item):
        QtCore, QtGui = _qt()
        for index in range(item.childCount()):
            child = item.child(index)
            form = self.small_form((u"%s" % child.data(0, QtCore.Qt.UserRole))[1:])
            icon = self.planned_picture(form) if form is not None else None
            if icon is not None:
                child.setIcon(1, self.ak.icon_of(icon))

    def planned_picture(self, form):
        """The figure (or letter) and the glyph planned of it, side by side as the font would set them, in
        the dialog's text color; None where a part cannot be drawn."""
        QtCore, QtGui = _qt()
        plan = self.small_plans.get(form.name)
        if plan is None:
            return None
        master = self.package.master

        def layer_of(name):
            glyph = self.package.findName(name)
            return glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None

        figure = layer_of(form.figure)
        parts = []
        for name, sx, sy, dx, dy in flat_parts(self.small_plans, form.name):
            layer = layer_of(name)
            if layer is None:
                return None
            parts.append((self.ak.layer_path(layer), sx, sy, dx, dy))
        if figure is None or not parts:
            return None
        # Strokes above 100% on a scaled form: its outline drawn with a pen as wide as both sides' offset,
        # which grows every stroke by the offset on each side, as the build does (the picture showed the
        # scaled figure whatever Strokes said)
        pen_width = 0.0
        weight = self.strokes_value() / 100.0
        if plan.how == "scaled" and weight > 1.0:
            try:
                stem = self.figure_stem(self.package, master)
                pen_width = 2.0 * stem * abs(plan.parts[0][1]) * (weight - 1.0) / 2.0 if stem else 0.0
            except Exception:
                pen_width = 0.0
        scale = ICON_SIZE * 0.75 / float(self.package.upm)
        gap = ICON_SIZE * 0.2
        width = int((figure.advanceWidth + plan.width) * scale + gap * 2)
        pixmap = QtGui.QPixmap(max(width, 4), ICON_SIZE)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.save()
            painter.translate(0.0, ICON_SIZE * 0.78)
            painter.scale(scale, -scale)
            painter.fillPath(self.ak.layer_path(figure), QtGui.QBrush(color))
            painter.restore()
            painter.save()
            painter.translate(figure.advanceWidth * scale + gap, ICON_SIZE * 0.78)
            painter.scale(scale, -scale)
            for path, sx, sy, dx, dy in parts:
                placed = QtGui.QTransform(sx, 0.0, 0.0, sy, float(dx), float(dy)).map(path)
                painter.fillPath(placed, QtGui.QBrush(color))
                if pen_width > 0:
                    pen = QtGui.QPen(color)
                    pen.setWidthF(pen_width)
                    pen.setJoinStyle(QtCore.Qt.MiterJoin)
                    painter.strokePath(placed, pen)
            painter.restore()
        finally:
            painter.end()
        return self.ak.inked(pixmap, color)  # (in one color: redrawn in the new one when dark mode switches)

    def small_checked(self, item, column):
        """A row's or a set's check changed (a set's checks all its rows)."""
        QtCore, QtGui = _qt()
        if column != 0:
            return
        on = item.checkState(0) == QtCore.Qt.Checked
        key = u"%s" % item.data(0, QtCore.Qt.UserRole)
        if key.startswith(u"\t"):
            form = self.small_form(key[1:])
            if form is None or form.on == on:
                return
            form.on = on
        else:
            for form in self.small_forms:
                if form.group == key:
                    form.on = on
        self.show_small_checks()
        self.replan()

    def show_small_checks(self):
        """Every build row's check as the model has it (rows found again by walking the tree)."""
        QtCore, QtGui = _qt()
        tree = self.small_tree
        tree.blockSignals(True)
        try:
            for row in range(tree.topLevelItemCount):
                item = tree.topLevelItem(row)
                group = u"%s" % item.data(0, QtCore.Qt.UserRole)
                ons = [form.on for form in self.small_forms if form.group == group]
                item.setCheckState(0, QtCore.Qt.Checked if any(ons) else QtCore.Qt.Unchecked)
                for index in range(item.childCount()):
                    child = item.child(index)
                    form = self.small_form((u"%s" % child.data(0, QtCore.Qt.UserRole))[1:])
                    if form is not None:
                        child.setCheckState(0, QtCore.Qt.Checked if form.on else QtCore.Qt.Unchecked)
        finally:
            tree.blockSignals(False)

    def small_clicked(self, item, column):
        """A row clicked: its set's settings shown."""
        QtCore, QtGui = _qt()
        key = u"%s" % item.data(0, QtCore.Qt.UserRole)
        form = self.small_form(key[1:]) if key.startswith(u"\t") else None
        set_key = form.set_key if form is not None else dict((g, s) for g, s, _ in SMALL_GROUPS).get(key)
        if set_key in SMALL_SETS and SMALL_SETS.index(set_key) != self.small_set_index:
            self.small_set.blockSignals(True)
            self.small_set.setCurrentIndex(SMALL_SETS.index(set_key))
            self.small_set.blockSignals(False)
            self.small_set_picked(SMALL_SETS.index(set_key))

    def figure_stem(self, package, master):
        """The font's figure stroke in a master (its zero's, else its one's), measured once."""
        QtCore = _qt()[0]
        if master in self.stems:
            return self.stems[master]
        found = None
        figures = self.small_info.figures() if self.small_info is not None else []
        names = [name for name in figures[:2] if name] + [u"zero", u"one"]
        for name in names:
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            if layer is None:
                continue
            path = self.ak.layer_path(layer)
            rect = path.boundingRect()
            if rect.isEmpty():
                continue
            found = stem_width(lambda x, y: path.contains(QtCore.QPointF(x, y)),
                               (rect.left(), rect.top(), rect.right(), rect.bottom()))
            if found:
                break
        self.stems[master] = found
        return found

    def stroke_copies(self, package, master, plan, weight):
        """What a scaled form's layer in a master is made of when its strokes are kept: [(source layer,
        (sx, sy, dx, dy), offset)], its parts' outlines scaled and placed as planned, then offset outward
        so their strokes are weight times the scaled ones; None when a part is made of components or the
        figure's stroke cannot be measured (the form is then made of components). Nothing is added here."""
        stem = self.figure_stem(package, master)
        if not stem:
            self.stroke_trouble = u"the figures' stroke could not be measured"
            return None
        copies = []
        for part in plan.parts:
            name, sx, sy, dx, dy = unwrapped(package, master, *part)
            source = package.findName(name)
            source_layer = source.getLayerByName(master) if source is not None else None
            if source_layer is None:
                self.stroke_trouble = u"%s has no layer in the master %s" % (name, master)
                return None
            if any(shape.isComponent for shape in source_layer.shapes):
                self.stroke_trouble = u"%s is made of components" % name
                return None
            distance = stem * abs(sx) * (weight - 1.0) / 2.0
            copies.append((source_layer, (sx, sy, float(round(dx)), float(round(dy))), distance))
        return copies

    def add_stroke_copies(self, layer, copies, width):
        """layer (empty, the new form's) made of the copies stroke_copies listed, offset. Returns what
        was done, as counts: [contours, nodes, on-curve nodes, nodes given a new place, those of them
        found there afterwards, shapes FontLab draws as they were before the offset].

        The owner saw no difference at 130% while the log said the strokes were thickened, and the nodes
        read back were where they had been put. Seen live (2026-11-13): a node's x and y set from a
        script are kept, and its contour's path follows, but the shape's own outline, what FontLab draws
        (its bounding box), does not; that is why the forms looked as scaled. So the outline is no
        longer moved node by node inside a shape FontLab has drawn already: each contour is cloned, its
        nodes put at their offset places while the clone belongs to no shape, and the clones are given
        to a new shape at once (flShape.addContours, which Font Check's master fixes proved live to
        redraw), the shape then updated. Where FontLab cannot make a shape from a script, the old way
        is taken (a copy of the shape, its nodes moved), the shape updated after. Either way the
        outline is read back twice, its nodes and its drawn box (flShape.boundingBox), so a form that
        FontLab draws as before is reported, not called thickened."""
        counts = [0, 0, 0, 0, 0, 0]
        for source_layer, move, distance in copies:
            for shape in source_layer.shapes:
                written = self.write_offset_shape(layer, shape, move, distance)
                if written is None:
                    continue
                at, wanted, own, done = written
                counts = [a + b for a, b in zip(counts, done + [0, 0])]
                try:  # read back through new objects, not the ones written through
                    again = layer.shapes[at]
                    matrix = shape_matrix(again)
                    read = [[mapped(matrix, n.x, n.y) for n in c.nodes()] for c in again.contours if c is not None]
                except Exception:
                    again, read = None, []
                moved = found = 0
                for index, places in enumerate(wanted):
                    now = read[index] if index < len(read) and len(read[index]) == len(places) else None
                    for number, (x, y, shifted, _) in enumerate(places):
                        if not shifted:
                            continue
                        moved += 1
                        if now is not None and abs(now[number][0] - x) <= STROKE_READ_BACK and \
                                abs(now[number][1] - y) <= STROKE_READ_BACK:
                            found += 1
                counts[3] += moved
                counts[4] += found
                if moved and found == moved and drawn_box_kept(shape_box(again), (wanted, own)) is False:
                    counts[5] += 1  # (its nodes read as put, and FontLab draws it as it was: what the owner saw)
        layer.advanceWidth = float(width)
        update_layer(layer)
        return counts

    def write_offset_shape(self, layer, shape, move, distance):
        """A copy of shape added to layer, scaled and placed by move (sx, sy, dx, dy), its strokes offset
        by distance (in the form's units): (its index among the layer's shapes, its nodes as wanted, in
        the form's units [[(x, y, moved)]] a contour, the same in the copy's own units (what its drawn box
        may be told in), [contours, nodes, on-curve nodes, 0]), or None for a shape without contours."""
        contours = [c for c in shape.contours if c is not None]
        if not contours:
            return None
        matrix = compose(shape_matrix(shape), move)
        points = [[mapped(matrix, n.x, n.y) + (u"%s" % n.type == u"on",) for n in c.nodes()] for c in contours]
        biggest = max(points, key=lambda pts: abs(signed_area(pts)))
        right = signed_area(biggest) > 0  # its outer contour counterclockwise (y up): the outside is right
        places = [offset_contour(pts, distance, right) for pts in points]
        done = [len(points), sum(len(pts) for pts in points), sum(1 for pts in points for p in pts if p[2]), 0]
        wanted = [wanted_points(contour_places, pts) for contour_places, pts in zip(places, points)]
        new = None
        try:  # a new shape, given its contours with their nodes already in place
            # (flContour.clone() copies the nodes: live, 2026-11-14, the figure's own zero kept its nodes and
            # its box after its clones' nodes were moved, in two fonts and five builds)
            clones = [contour.clone() for contour in contours]
            for clone, contour_places in zip(clones, places):
                nodes = clone.nodes()
                if len(nodes) != len(contour_places):
                    raise ValueError(u"a cloned contour has other nodes")
                for node, (x, y) in zip(nodes, contour_places):
                    place_node(node, x, y)
                # (the clones are the figure's contours, unscaled: where their nodes did not take their
                # places, the shape would be the figure at full size, so the old way is taken instead)
                if any(abs(node.x - x) > STROKE_READ_BACK or abs(node.y - y) > STROKE_READ_BACK
                       for node, (x, y) in zip(clone.nodes(), contour_places)):
                    raise ValueError(u"a cloned contour's nodes did not move")
            new = self.fontlab.flShape()
            new.addContours(clones, True)
        except Exception:
            new = None
        if new is not None:
            layer.addShape(new)
            at = len(layer.shapes) - 1
            refresh_shape(layer.shapes[at])
            return at, wanted, wanted, done
        # The old way: a copy of the shape, placed by its transform, its nodes moved where they are
        QtGui = _qt()[1]
        layer.addShape(shape.cloneTopLevel() if hasattr(shape, "cloneTopLevel") else shape.clone())
        at = len(layer.shapes) - 1
        copy = layer.shapes[at]
        copy.applyTransform(QtGui.QTransform(move[0], 0.0, 0.0, move[1], move[2], move[3]))
        own_matrix = shape_matrix(copy)
        local = (abs(own_matrix[0] * own_matrix[3] - own_matrix[1] * own_matrix[2]) ** 0.5) or 1.0
        copied = [c for c in copy.contours if c is not None]
        own_points = [[(n.x, n.y, u"%s" % n.type == u"on") for n in c.nodes()] for c in copied]
        own_right = signed_area(max(own_points, key=lambda pts: abs(signed_area(pts)))) > 0 if own_points else right
        own = []
        for contour, pts in zip(copied, own_points):
            nodes = contour.nodes()
            contour_places = offset_contour(pts, distance / local, own_right)  # (the offset in the contours' own units)
            for node, (x, y) in zip(nodes, contour_places):
                place_node(node, x, y)
            if hasattr(contour, "update"):
                contour.update()
            own.append(wanted_points(contour_places, pts))
        refresh_shape(copy)
        wanted = [[mapped(own_matrix, x, y) + (shifted, on) for x, y, shifted, on in contour] for contour in own]
        return at, wanted, own, done

    def small_set_picked(self, index):
        """A set picked in the settings row: its settings shown in the boxes (signals held: showing them
        changes nothing)."""
        self.small_set_index = index if 0 <= index < len(SMALL_SETS) else 0
        setting = self.small_setup.get(SMALL_SETS[self.small_set_index])
        boxes = (self.small_scale, self.small_baseline, self.small_width)
        for box in boxes:
            box.blockSignals(True)
        try:
            if setting is not None:
                self.small_scale.setValue(int(round(setting["scale"] * 100)))
                self.small_baseline.setValue(int(setting["baseline"]))
                self.small_width.setValue(int(round(setting["width"] * 100)))
            # (where the set's suggestion comes from, in the button's tooltip and What's This)
            first = self.small_first.get(SMALL_SETS[self.small_set_index]) or setting or {}
            describe(self.small_reset, suggested_words(first.get("why")), True)
        finally:
            for box in boxes:
                box.blockSignals(False)
        self.show_baseline_suffix()

    def show_baseline_suffix(self):
        """The baseline box's word follows its number ("1 unit", "-1 unit", "2 units"), however the
        number came (typed, or set with the box's signals held)."""
        try:
            self.small_baseline.setSuffix(units_suffix(self.small_baseline.value))
        except Exception:
            pass  # a signal's handler must not raise

    def small_setting(self, key, value):
        """A setting of the picked set changed in its box."""
        setting = self.small_setup.get(SMALL_SETS[self.small_set_index])
        if setting is None:
            return
        if key == "scale":
            scale = value / 100.0
            if abs(scale - setting["scale"]) < 1e-9:
                return
            baseline = rescaled_baseline(setting, scale)
            setting["scale"] = scale
            if baseline != setting["baseline"]:
                setting["baseline"] = baseline
                self.small_baseline.blockSignals(True)
                self.small_baseline.setValue(baseline)
                self.small_baseline.blockSignals(False)
                self.show_baseline_suffix()
        elif key == "baseline":
            setting["baseline"] = int(value)
        else:
            setting["width"] = value / 100.0
        self.replan()

    def sync_small_settings(self):
        """The settings as the boxes show them, read at the click that builds: a value typed and not yet
        entered is taken (interpretText, as Enter does), and the picked set's settings and the plans follow
        the boxes where a change did not reach them (owner's report: 100 typed in Strokes over 130, then
        Build without Enter, built at 130). Strokes itself is read from its box as the build starts."""
        boxes = (("scale", "small_scale"), ("baseline", "small_baseline"), ("width", "small_width"))
        for _, name in boxes + ((None, "stroke_box"),):
            box = getattr(self, name, None)
            try:
                box.interpretText()  # (its valueChanged, where the text differs: the settings follow)
            except Exception:
                pass
        setting = self.small_setup.get(SMALL_SETS[self.small_set_index]) if 0 <= self.small_set_index < len(
            SMALL_SETS) else None
        if setting is None:
            return
        for key, name in boxes:
            value = getattr(getattr(self, name, None), "value", None)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue  # (no number: a box that is not there, or not read)
            value = int(value)
            now = setting.get(key)
            shown = int(round(now * 100)) if key in ("scale", "width") and now is not None else now
            if shown != value:
                self.small_setting(key, value)  # (planned again)

    def small_suggested(self):
        """The picked set's settings back as first suggested, and Strokes back at STROKE_WEIGHT."""
        set_key = SMALL_SETS[self.small_set_index]
        if set_key in self.small_first:
            self.small_setup[set_key] = dict(self.small_first[set_key])
            self.small_set_picked(self.small_set_index)
        if self.strokes_value() != STROKE_WEIGHT:
            self.stroke_box.blockSignals(True)  # (planned once, below)
            try:
                self.stroke_box.setValue(STROKE_WEIGHT)
            finally:
                self.stroke_box.blockSignals(False)
        self.replan()

    def small_changed(self):
        if hasattr(self, "stroke_box") and self.stroke_box.value != STROKE_WEIGHT:
            return True
        return any(form.on != form.first_on for form in self.small_forms) or any(
            self.small_setup.get(key, {}).get(k) != setting.get(k) for key, setting in self.small_first.items()
            for k in ("scale", "baseline", "width"))

    def update_small_buttons(self):
        unchanged = self.unchanged_forms()
        count = sum(1 for form in self.small_forms if form.on and self.small_plans.get(form.name) is not None
                    and form.name not in unchanged)
        self.build_button.setText(build_label(count))
        # (set_enabled, not Auto Kerning's enable: this runs while the font is read after a build or an
        # undo, the lists' part disabled meanwhile, and the button stayed clickable with nothing to build.)
        # Only with something a build would make or change (owner's report 160: it stayed clickable when
        # every checked glyph was as built here, and a click only said "Nothing changed since the last
        # build"); its tooltip and What's This then say why it is grayed out.
        set_enabled(self.build_button, count > 0)
        describe(self.build_button, build_words(count, len(unchanged)), True)
        set_enabled(self.restore_button, self.restorable())
        # The settings act on the forms listed: none listed (no font, or nothing to build), none to set.
        # Suggested only where it would put something back: the picked set's three, or Strokes.
        listed = bool(self.small_forms)
        for box in (self.small_set, self.small_scale, self.small_baseline, self.small_width, self.stroke_box):
            set_enabled(box, listed)
        set_key = SMALL_SETS[self.small_set_index] if 0 <= self.small_set_index < len(SMALL_SETS) else None
        first, now = self.small_first.get(set_key), self.small_setup.get(set_key)
        set_enabled(self.small_reset, listed and ((first is not None and now is not None and any(
            first.get(k) != now.get(k) for k in ("scale", "baseline", "width"))) or self.strokes_value() != STROKE_WEIGHT))

    def build_masters(self, package):
        """The masters a build makes layers in (every master; the current one where none is listed)."""
        try:
            masters = list(package.masters)
        except Exception:
            masters = []
        return masters or [package.master]

    def glyph_print(self, package, name, masters):
        """What a glyph is in each master (layer_print), or None where it is not in the font or FontLab
        does not say."""
        glyph = package.findName(name)
        if glyph is None:
            return None
        try:
            found = []
            for master in masters:
                layer = glyph.getLayerByName(master)
                if layer is not None:
                    found.append((u"%s" % master, layer_print(layer)))
            return tuple(found) or None
        except Exception:
            return None

    def own_built(self, package):
        """{glyph: the plan it was built from (plan_signature)} of the figure forms this window built in
        this font that are still as one of its builds left them (an undo may bring back an earlier one).
        A glyph drawn over, or changed any other way, is no longer listed: it is the user's, and never
        replaced."""
        try:
            records = self.built.get(self.ak.font_key(package), {})
        except Exception:
            return {}
        found, masters = {}, self.build_masters(package)
        for name, prints in records.items():
            now = self.glyph_print(package, name, masters)
            if now is not None and now in prints:
                found[name] = prints[now]
        return found

    def strokes_value(self):
        return self.stroke_box.value if hasattr(self, "stroke_box") else STROKE_WEIGHT

    def unchanged_forms(self):
        """The checked forms this window built whose plan and Strokes are what they were built with: a
        build would make them as they are."""
        strokes = self.strokes_value()
        return set(form.name for form in self.small_forms if form.on and form.name in self.small_ours and
                   self.small_ours[form.name] == plan_signature(self.small_plans.get(form.name), strokes))

    def restorable(self):
        if self.package is None:  # (no font: the last font's settings are nothing to restore)
            return False
        return [lig.choice for lig in self.found] != self.first_choices or self.alternate_checks() != self.first_checks \
            or self.forms_changed() or self.small_changed()

    def has_code(self, package, code):
        try:
            return package.findUnicode(code) is not None
        except Exception:
            return False

    def build_small_forms(self):
        """The checked figure forms added to the font as planned (components, or outlines with their strokes
        kept when Strokes is above 100% and every master allows it), in every master
        (placed by the current master's measures; widths from each master's own glyphs), as one step of
        FontLab's History; a code point set once its glyph's layers are made."""
        QtCore, QtGui = _qt()
        if self.package is None or self.small_info is None or self.busy:
            return
        self.sync_small_settings()  # (what the boxes show now, typed and not yet entered included)
        chosen = [form for form in self.small_forms if form.on]
        if not chosen:
            return
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed since the list was made: here is this one's. Nothing was built.", "warning")
            return
        # What this window built and nobody changed since, asked of the font now (not as the list was read);
        # of it, what these settings would make as it is: left as it is, and said
        ours = self.own_built(package)
        strokes = self.strokes_value()
        signatures = dict((form.name, plan_signature(self.small_plans.get(form.name), strokes)) for form in chosen)
        same = [form.name for form in chosen if form.name in ours and ours[form.name] == signatures[form.name]]
        chosen = [form for form in chosen if form.name not in same]
        # What this window built from a form built again is built again with it: a component keeps the
        # glyph it points to as it was when it was made (live: uni2070, a component of zero.sups, kept
        # zero.sups' 100% outline after zero.sups was built again at 130% and 160%)
        following = dependent_forms(self.small_forms, self.small_plans, ours, [form.name for form in chosen])
        same = [name for name in same if name not in following]
        chosen += [form for form in self.small_forms if form.name in following and form not in chosen]
        signatures.update((name, plan_signature(self.small_plans.get(name), strokes)) for name in following)
        if not chosen:
            self.log.add(u"Nothing changed since the last build: the ticked figure forms are as these settings make "
                         u"them, so none was built again. Change a setting, or tick other figure forms, to build again.")
            return
        fontlab = self.fontlab
        masters = self.build_masters(package)
        plans = {}

        def plans_of(master):
            if master not in plans:
                def advance(name):
                    glyph = package.findName(name)
                    layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
                    return layer.advanceWidth if layer is not None else None
                plans[master] = plan_small_forms(self.small_info, self.small_forms, self.small_setup, advance)
            return plans[master]

        made, skipped, failed, error, touched, thickened, replaced = [], [], [], None, [], [], []
        # forms whose thicker strokes FontLab did not keep, and what was done to them (add_stroke_copies' counts);
        # how far the kept strokes' sides moved in the current master (asked: the form's under way)
        unkept, lost, offsets, asked = [], [0, 0, 0, 0, 0, 0], [], []
        unstroked = []  # [(form, why)]: scaled forms Strokes above 100% could not thicken (made of components)
        self.stems = {}
        # (a form built again: its glyph is changed)
        if not self.ak.begin_write(fontlab, package, u"FreeLab Feature Code", self.log, coverage=True):
            return  # (nothing built: the reason in the log; coverage: the font info follows the forms' code points)
        # The window's top row counts the forms built (there was no progress at all); a write, one step of
        # FontLab's History: never stopped half way, what was clicked meanwhile done once it is over
        self.set_busy(True, u"Building the figure forms", stoppable=False)
        try:
            for master in masters:
                plans_of(master)  # (each master planned before anything is added)
            ordered = sorted(chosen, key=lambda f: f.group in ("superscript", "subscript"))
            for at, form in enumerate(ordered):
                self.progress(u"Building the figure forms", at, len(ordered), stoppable=False)
                # A glyph of the name, or with the code point, that is not one this window built and left
                # alone since is the font's: made meanwhile, or drawn over. Never replaced.
                again = form.name in ours and package.findName(form.name) is not None
                if not again and (package.findName(form.name) is not None or
                                  (form.code and self.has_code(package, form.code))):
                    skipped.append(form.name)
                    continue
                usable = [(master, plans_of(master).get(form.name)) for master in masters]
                usable = [(master, plan) for master, plan in usable if plan is not None and
                          all(package.findName(part[0]) is not None for part in plan.parts)]
                if not usable:  # (asked before anything is added or taken out)
                    failed.append((form.name, u"its figure has no width in any master"))
                    continue
                # (a scaled form only: a copied or moved one is the same as its drawn or built glyph; and
                # outlines in every master or in none, so the masters stay compatible)
                weight = strokes / 100.0
                outlines = {}
                if weight > 1.0 and all(plan.how == "scaled" for _, plan in usable):
                    for master, plan in usable:
                        self.stroke_trouble = None
                        copies = self.stroke_copies(package, master, plan, weight)
                        if copies is None:
                            outlines = {}
                            # (said, not left to "Scaling thins strokes": owner's report 156 saw no
                            # difference between 100% and 130%, and the log never said why)
                            unstroked.append((form.name, self.stroke_trouble or u"FontLab did not say why"))
                            break
                        outlines[master] = copies
                if again:  # its layers emptied, then made anew: the glyph, its code point, and what uses it stay
                    glyph = package.findName(form.name)
                    for master in masters:
                        layer = glyph.getLayerByName(master)
                        if layer is not None:
                            layer.removeAllShapes()
                else:
                    new = fontlab.flGlyph()
                    new.name = form.name
                    # (its code point set once its layers are made: given before, FontLab kept none of them)
                    package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
                    glyph = package.findName(form.name)
                    if glyph is None:
                        raise RuntimeError(u"FontLab did not add %s" % form.name)
                placed = False
                del asked[:]
                done = [0, 0, 0, 0, 0, 0]  # contours, nodes, on-curve, moved, found where put, drawn as before
                for master, plan in usable:
                    layer = glyph.getLayerByName(master, True)
                    if master in outlines:
                        counts = self.add_stroke_copies(layer, outlines[master], plan.width)
                        done = [a + b for a, b in zip(done, counts)]
                        if master == package.master:  # (how far each side moved, for the log)
                            asked.extend(distance for _, _, distance in outlines[master])
                        placed = True
                        continue
                    components = []
                    for part in plan.parts:
                        name, sx, sy, dx, dy = unwrapped(package, master, *part)
                        component = fontlab.GlyphComponent(name)
                        component.transform = QtGui.QTransform(sx, 0.0, 0.0, sy, float(round(dx)), float(round(dy)))
                        components.append(component)
                    layer.setGlyphComponents(components, float(plan.width), package, False)
                    update_layer(layer)
                    placed = True
                if not placed or is_empty(package.findName(form.name)):
                    if again:  # (this window's own glyph, left empty: said, and Edit > Undo puts it back)
                        touched.append(glyph)
                        failed.append((form.name, u"FontLab did not keep its new components, and it is empty" +
                                       EMPTIED_UNDO))
                        continue
                    failed.append((form.name, u"FontLab did not keep its components"))
                    package.deleteGlyph(package.findName(form.name))
                    continue
                if form.code and not again:
                    package.findName(form.name).fgGlyph.unicode = form.code
                touched.append(glyph)
                made.append(form.name)
                if again:
                    replaced.append(form.name)
                if outlines:
                    # Thickened only where FontLab has every moved node where it was put, and draws the
                    # outline where they are. An offset under a unit (thin strokes at 101%) moves no node
                    # far enough to tell: taken as kept.
                    far = any(distance >= 1.0 for copies in outlines.values() for _, _, distance in copies)
                    if (done[3] and done[4] == done[3] and not done[5]) or not far:
                        thickened.append(form.name)
                        offsets.extend(asked)
                    else:
                        unkept.append(form.name)
                        lost = [a + b for a, b in zip(lost, done)]
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
        finally:
            self.set_busy(False)
        status = self.ak.notify_changed(fontlab, package, u"FreeLab Feature Code", touched, coverage=True)
        if not status.recorded:  # (no Undo to promise)
            failed = [(name, why.replace(EMPTIED_UNDO, u"")) for name, why in failed]
        try:  # what each glyph is now, and from what it was built: a later build may replace it
            records = self.built.setdefault(self.ak.font_key(package), {})
            for name in made:
                now = self.glyph_print(package, name, masters)
                if now is not None:
                    records.setdefault(name, {})[now] = signatures.get(name)
        except Exception:
            pass
        b = self.ak.b
        if made:
            one = len(made) == 1
            kept = sorted(set(thickened))
            new = [name for name in made if name not in replaced]
            words = []
            if new:
                words.append(u"Built %s: %s. %s at the end of the font." % (
                    b(counted(len(new), u"glyph")), self.ak.glyph_name_links(new),
                    u"It is" if len(new) == 1 else u"They are"))
            if replaced:  # (the glyphs this window built before, made again with the settings shown)
                words.append(u"Replaced %s built here before, with the settings shown: %s." % (
                    b(counted(len(replaced), u"glyph")), self.ak.glyph_name_links(replaced)))
            words.append(status.undo(u"<i>Edit &gt; Undo</i> takes %s back." % (u"it" if one else u"them")))
            words.append(u"Made of outlines, strokes at %d%% of the scaled ones%s: %s." % (
                strokes, offset_words(offsets), self.ak.glyph_name_links(kept)) if kept else
                u"Scaling thins strokes: draw over what was scaled.")
            if new:
                words.append(u"The forms above take %s now: tick their features and write the code." % (
                    u"it" if len(new) == 1 else u"them"))
            if same:
                words.append(u"%s, as built before with these settings, %s left as %s." % (
                    b(counted(len(same), u"glyph")), u"was" if len(same) == 1 else u"were",
                    u"it was" if len(same) == 1 else u"they were"))
            self.log.add(u" ".join(word for word in words if word), "done")
        else:
            self.log.add(u"Built none.")
        status.report(self.log)
        if unkept:  # (said, not assumed: the outlines were read back after they were written)
            # (each count bold with its noun; "40 on-curve" and the like, whose noun is the nodes', bold alone)
            drawn = (u", %s drawn as before" % b(counted(lost[5], u"shape"))) if lost[5] else u""
            self.log.add(u"FontLab did not keep the thicker strokes of %s: %s. Read back, %s as scaled (%s in %s, "
                         u"%s on-curve, %s given a new place, %s found there%s): draw over %s." % (
                             b(counted(len(unkept), u"glyph")), self.ak.glyph_name_links(sorted(unkept)),
                             u"its outline was" if len(unkept) == 1 else u"their outlines were",
                             b(counted(lost[1], u"node")), b(counted(lost[0], u"contour")), b(grouped(lost[2])),
                             b(grouped(lost[3])), b(grouped(lost[4])), drawn,
                             u"it" if len(unkept) == 1 else u"them"), "warning")
        unstroked = [(name, why) for name, why in unstroked if name in made]
        if unstroked:  # (Strokes above 100% that was not applied: said, with why)
            one = len(unstroked) == 1
            self.log.add(u"<i>Strokes</i> at %d%% could not thicken %s: %s. %s made of components, scaled (%s "
                         u"thinned), because %s." % (
                             strokes, b(counted(len(unstroked), u"glyph")),
                             self.ak.glyph_name_links([name for name, _ in unstroked]),
                             u"It is" if one else u"They are", u"its strokes" if one else u"their strokes",
                             self.ak.html(describe_list(sorted(set(why for _, why in unstroked))))), "warning")
        if skipped:
            self.log.add(u"%s had been made or changed meanwhile and %s left as %s." % (
                self.ak.glyph_name_links(skipped), u"was" if len(skipped) == 1 else u"were",
                u"it was" if len(skipped) == 1 else u"they were"), "warning")
        for name, why in failed:
            self.log.add(u"%s was not built: %s." % (b(name), self.ak.html(why)), "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        forms, choices = self.form_state(), self.choice_state()
        self.run()
        self.apply_choices(choices)
        self.apply_form_state(forms)
        self.make_code()

    # -- the rest -----------------------------------------------------------------------

    def part(self, QtGui, stretch, splitter=None, at=None):
        """A part of a splitter (the dialog's, unless another is given): its layout, to fill (stretch:
        its share of the height at first; at: its place among the parts, else the last)."""
        splitter = splitter if splitter is not None else self.splitter
        widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        if at is None:
            splitter.addWidget(widget)
        else:
            splitter.insertWidget(at, widget)
        splitter.setStretchFactor(splitter.indexOf(widget), stretch)
        widget.setProperty("freelabShare", stretch)  # (ak.share_splitters: the heights at first show, in these shares)
        return box

    def show_choice(self, item, lig):
        """A ligature's feature shown in its row's box (signals held: showing it is no choice)."""
        QtCore, QtGui = _qt()
        index = int(item.data(0, QtCore.Qt.UserRole))
        if not 0 <= index < len(self.combos):
            return
        combo = self.combos[index]
        combo.blockSignals(True)
        combo.setCurrentIndex([key for key, _ in CHOICES].index(lig.choice))
        combo.blockSignals(False)

    def choose(self, lig, choice):
        """A ligature's feature chosen in its box."""
        key = CHOICES[choice][0]
        if key != lig.choice:
            lig.choice = key
            self.make_code()

    def alternate_checks(self):
        QtCore, QtGui = _qt()
        return [self.alternate_tree.topLevelItem(row).checkState(0) == QtCore.Qt.Checked
                for row in range(self.alternate_tree.topLevelItemCount)]

    def restore(self):
        """The features, checks, names, and build settings as they first came."""
        QtCore, QtGui = _qt()
        if self.busy:
            return
        for row, (lig, choice) in enumerate(zip(self.found, self.first_choices)):
            lig.choice = choice
            self.show_choice(self.ligature_tree.topLevelItem(row), lig)
        self.alternate_tree.blockSignals(True)
        for row, on in enumerate(self.first_checks):
            self.alternate_tree.topLevelItem(row).setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.alternate_tree.blockSignals(False)
        for feature in self.forms:
            feature.on, feature.name = feature.first_on, feature.first_name
            for rule in feature.rules:
                rule.on = rule.first_on
        self.show_forms()
        for form in self.small_forms:
            form.on = form.first_on
        if hasattr(self, "stroke_box"):
            self.stroke_box.setValue(STROKE_WEIGHT)
        self.small_setup = dict((key, dict(setting)) for key, setting in self.small_first.items())
        self.show_small_checks()
        self.small_set_picked(self.small_set_index)
        self.replan()
        self.make_code()
        self.log.add(u"Choices restored as suggested.")

    def double_clicked(self, item, column):
        """A ligature's glyphs, a character's forms, or a form's glyphs in a Glyph window."""
        QtCore, QtGui = _qt()
        tree = item.treeWidget()
        if column == 2 and tree is self.ligature_tree:
            return
        if tree is self.ligature_tree:
            lig = self.found[int(item.data(0, QtCore.Qt.UserRole))]
            text = u"".join(u"/" + name for name in lig.parts) + u"/space/" + lig.glyph
        elif tree is self.forms_tree:
            rule = self.form_rule(item)
            if rule is None:
                return  # a feature's row: its arrow opens it
            text = u"".join(u"/" + name for name in rule.glyphs)
        else:
            base = u"%s" % item.data(0, QtCore.Qt.UserRole)
            text = u"".join(u"/" + name for name in [base] * 4)
        error = self.ak.show_in_glyph_window(self.fontlab, text)
        if error:
            self.log.add(u"FontLab did not open them: %s" % self.ak.html(error), "error")

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (the shared
        module's fonts_tick, from a timer): the three tabs read again for the new font, as when the window
        opens (the checks and settings of another font are not carried over: read_font keeps them for
        the same font only), or emptied, the no-font line shown and nothing that acts on a font
        clickable. Nothing escapes: a timer's call must not raise."""
        try:
            self.run()
        except Exception as exc:
            try:
                self.log.add(u"The font could not be read: %s" % self.ak.html(exc), "error")
            except Exception:
                pass

    def choice_state(self):
        """{(glyph, its parts): its choice} of the ligatures FreeLab writes, to keep across a fresh look at
        the same font (a write, a build, an undo): read again, a ligature named f_i whose rule a write took
        out (Off) was offered again as its name suggests, and the next write put it back (Codex review 8)."""
        try:
            key = self.ak.font_key(self.package)
        except Exception:
            key = None
        return key, dict(((lig.glyph, lig.parts), lig.choice) for lig in self.found if not lig.fixed)

    def apply_choices(self, state):
        """The choices kept (choice_state) given back where the same font has the same ligature, FreeLab's
        to write (the font's own stay where its code has them)."""
        key, choices = state
        try:
            if key is None or self.package is None or self.ak.font_key(self.package) != key:
                return
        except Exception:
            return
        for row, lig in enumerate(self.found):
            kept = choices.get((lig.glyph, lig.parts))
            if kept is not None and not lig.fixed and kept != lig.choice:
                lig.choice = kept
                self.show_choice(self.ligature_tree.topLevelItem(row), lig)

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again, the choices kept where they still apply."""
        choices = self.choice_state()
        forms = self.form_state()
        self.run()
        self.apply_choices(choices)
        self.apply_form_state(forms)
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
        return self.ak.inked(pixmap, color)  # (in one color: redrawn in the new one when dark mode switches)

    def cycling(self):
        QtCore, QtGui = _qt()
        chosen = {}
        for row in range(self.alternate_tree.topLevelItemCount):
            item = self.alternate_tree.topLevelItem(row)
            base = u"%s" % item.data(0, QtCore.Qt.UserRole)
            if item.checkState(0) == QtCore.Qt.Checked and base in self.sets:
                chosen[base] = self.sets[base]
        return chosen

    def turn_state(self):
        """(the font's key, {glyph: checked to take turns}), or None before a font is read."""
        QtCore, QtGui = _qt()
        if getattr(self, "package", None) is None:
            return None
        try:
            key = self.ak.font_key(self.package)
            tree = self.alternate_tree
            return key, dict((u"%s" % tree.topLevelItem(row).data(0, QtCore.Qt.UserRole),
                              tree.topLevelItem(row).checkState(0) == QtCore.Qt.Checked)
                             for row in range(tree.topLevelItemCount))
        except Exception:
            return None

    def doubled(self, ch):
        """Whether a character often stands doubled in text (the Stylistic alternates tab's scope asks)."""
        return doubles_often(ch, self.doubles, self.pairs, self.typed)

    def kind(self, ch):
        """A character's kind, for taking turns (letters, figures, punctuation), or None (the Stylistic
        alternates tab asks, so both tabs take the same characters)."""
        return char_kind(ch)

    def look_back_changed(self, value):
        """The look back set: its box's word follows its number (1 character, 2 characters), and the
        code is made again."""
        try:
            self.look_back.setSuffix(look_back_suffix(int(value)))
        except Exception:
            pass  # a signal's handler must not raise
        self.make_code()

    def check_turns(self, key):
        """The characters taking turns checked at once: those often doubled in text, all, or none (one
        whose alternates have another job in the font's code stays unchecked)."""
        QtCore, QtGui = _qt()
        if self.busy or self.package is None:
            return
        tree = self.alternate_tree

        def wanted(item):
            base = u"%s" % item.data(0, QtCore.Qt.UserRole)
            return base not in self.taken and (key == "all" or (key == "often" and base in self.often))

        tree.blockSignals(True)
        try:  # (the log told how many it checked and unchecked, hidden ones said: owner's report 118)
            self.ak.check_rows([tree.topLevelItem(row) for row in range(tree.topLevelItemCount)], wanted,
                               log=self.log, command=dict((k, label) for k, label, _ in TURN_CHECKS)[key],
                               noun=u"glyph")
        finally:
            tree.blockSignals(False)
        self.make_code()

    def turn_picked(self, item):
        """A character's row clicked: its forms drawn, where the list was too long to draw every row's."""
        try:
            QtCore, QtGui = _qt()
            if item is None or self.package is None or self.busy:
                return
            base = u"%s" % item.data(0, QtCore.Qt.UserRole)
            if base in self.sets and (u"%s" % item.toolTip(1)) == TURN_PICTURE_TIP:
                icon = self.picture([base] + self.sets[base])
                if icon is not None:
                    item.setIcon(1, self.ak.icon_of(icon))
                item.setToolTip(1, u"")
        except Exception:
            pass  # a signal's handler must not raise

    def show_turns(self, cycling):
        """How the checked characters take turns, said under the look back, and the check buttons' states."""
        look_back = self.look_back.value
        mode = turn_mode(cycling, look_back)
        if mode == "position":
            deepest = {}  # (a rule per kind and step of the turn)
            for base, forms in cycling.items():
                kind = char_kind(self.chars.get(base)) or LETTERS
                deepest[kind] = max(deepest.get(kind, 0), len(forms))
            text = (u"%s ticked: more than rules by glyph can serve in a font (%s; %s at most). They "
                    u"take turns %s instead: each takes the form after the form of the glyph of its kind "
                    u"before it, in %s, and the look back does not apply. Tick fewer glyphs (%s) for each to "
                    u"look back for its own earlier form." % (
                        self.ak.b(counted(len(cycling), u"glyph")),
                        self.ak.b(counted(turn_rules(cycling, look_back), u"rule")),
                        self.ak.b(grouped(TURN_RULES_MAX)), self.ak.b(u"by position"),
                        self.ak.b(counted(sum(deepest.values()), u"rule")), self.ak.i(TURN_CHECK_LABELS["often"])))
        elif mode == "letter":
            text = (u"%s ticked, taking turns %s: each looks back among its own kind (letters, figures, or "
                    u"punctuation marks) for its own earlier form (%s)." % (
                        self.ak.b(counted(len(cycling), u"glyph")), self.ak.b(u"by glyph"),
                        self.ak.b(counted(turn_rules(cycling, look_back), u"rule"))))
        elif self.package is None:
            text = u""
        elif self.sets:
            text = u"No glyph is ticked to take turns."
        else:  # (the section said nothing, and the owner looked for a minute for where they are made)
            text = NO_TURNS
        say(self.turn_label, text)
        set_enabled(self.look_back, bool(self.sets))  # (no glyph with alternates: no look back to set)
        free = [base for base in self.sets if base not in self.taken]
        often = set(base for base in free if base in self.often)
        states = {"often": bool(often) and set(cycling) != often, "all": len(cycling) < len(free), "none": bool(cycling)}
        for (key, _, _), button in zip(TURN_CHECKS, self.turn_buttons):
            set_enabled(button, states[key])  # (also set while the font is read: update_small_buttons)

    def turn_trouble(self, cycling):
        """Why the checked glyphs' turns cannot be written, or None (turn_problem, with the room of the
        glyphs that may stand before them counted in the font's own glyph order)."""
        look_back = self.look_back.value
        mode = turn_mode(cycling, look_back)
        if mode == "none":
            return None
        order = dict((name, number) for number, name in enumerate(self.names))
        return turn_problem(cycling, look_back, context_bytes(cycling, self.letters, self.others, order, mode))

    def new_texts(self):
        """{tag: its new code} for liga, dlig, and calt (only those with something of FreeLab's, or
        with rules FreeLab takes over), and for the form features that change."""
        refused = self.refused = []  # (features whose braces FreeLab cannot find: left as they are, and said)
        self.stuck = []  # (ligatures whose rule FreeLab cannot move: left where they are, and said)
        texts = ligature_texts(self.found, self.texts, refused, self.stuck)
        cycling = self.cycling()
        if cycling or (BEGIN % "alternates") in (self.texts.get("calt") or u""):
            fits = cycling and not self.turn_trouble(cycling)  # (code that cannot compile is not made)
            try:
                texts["calt"] = calt_text(self.texts.get("calt"),
                                          cycle_code(cycling, self.letters, self.look_back.value, others=self.others)
                                          if fits else [])
            except FeatureCodeUnreadable:
                refused.append("calt")
        texts.update(forms_texts(self.forms, self.texts, refused))
        return texts

    def show_code(self, text):
        """The Code box's text, colored while it has HIGHLIGHT_LINES lines at most, plain past that; left
        alone when it is the text shown already (each click makes the code again, and Qt would color every
        line of it again)."""
        if text == self.code_text:
            return
        self.code_text = text
        highlighting = self.highlighting
        long_code = text.count(u"\n") + 1 > HIGHLIGHT_LINES
        if highlighting is not None and long_code:
            highlighting.detach()  # (before the text: none of its lines is colored)
        self.code.setPlainText(text)
        if highlighting is not None and not long_code:
            highlighting.attach()  # (after it, where it was detached: colored once, not twice)

    def tags_shown(self, texts):
        return [tag for tag in ("liga", "dlig", "calt") if tag in texts] + \
            [feature.tag for feature in self.forms if feature.tag in texts]

    def update_buttons(self):
        """Every control's state set again from what is listed: the code's (Write the code, Restore suggestions,
        the turns' buttons and Look back: make_code), the forms' builds, and the Stylistic alternates tab's.
        The shared no_font_states calls it once it gives the controls back with the font, after the read had
        set them: without it, everything came back clickable (live 2026-11-19, Bellefair: Write the code beside
        "The font has this code already", Make copies to redraw with nothing ticked). Never raises."""
        if self.package is None or self.busy:
            return
        for step in (self.make_code, self.update_small_buttons,
                     getattr(self.alternates, "update_buttons", None) if self.alternates is not None else None):
            if step is None:
                continue
            try:
                step()
            except Exception:
                pass

    def make_code(self):
        if self.package is None:
            return
        texts = self.new_texts()
        prefix = self.new_prefix()
        shown, problems = [], []
        cycling = self.cycling()
        problem = self.turn_trouble(cycling)
        if problem:
            problems.append(u"calt: %s" % problem)
        self.show_turns(cycling)
        if prefix is not None:
            shown.append(u"# The prefix (before the features)\n" + prefix)
        for tag in ("liga", "dlig", "calt"):
            if tag in texts:
                shown.append(texts[tag])
                block = freelab_block(tag, texts[tag], "alternates" if tag == "calt" else "ligatures")
                problem = check_code(block, self.names) if block else None
                if problem:
                    problems.append(u"%s: %s" % (tag, problem))
        form_texts = dict((tag, text) for tag, text in texts.items() if tag not in ("liga", "dlig", "calt"))
        for feature in self.forms:
            if feature.tag in form_texts:
                shown.append(form_texts[feature.tag])
        for tag, problem in sorted(forms_check(self.forms, form_texts, language_systems(self.locl()),
                                               self.names, self.checked_code).items()):
            problems.append(u"%s: %s" % (tag, problem))
        self.show_code(u"\n".join(shown))
        present = any((BEGIN % kind) in (self.texts.get(tag) or u"")
                      for tag, kind in (("liga", "ligatures"), ("dlig", "ligatures"), ("calt", "alternates"))) or \
            any((BEGIN % FORMS) in (text or u"") for text in self.texts.values())
        changes = bool(texts and any(not same_code(texts[tag], self.texts.get(tag)) for tag in texts)) or \
            prefix is not None
        self.write_button.setText(u"Update the code" if present else u"Write the code")
        set_enabled(self.write_button, changes and not problems)
        set_enabled(self.restore_button, self.restorable())
        counts = dict((key, sum(1 for lig in self.found if lig.choice == key)) for key, _ in CHOICES)
        b = self.ak.b
        checked = [feature.tag for feature in self.forms if feature.on and feature.checked()]
        self.show_font_line()
        # (under the top line, which names the font: the status lines, results first, then what stops a write)
        if not self.forms:  # (never "0 of 0 form features": owner's wording rule)
            forms = u"none"
        elif not checked:
            forms = u"%s, none ticked" % b(counted(len(self.forms), u"form feature"))
        else:
            forms = u"%s ticked (%s)" % (b(u"%s of %s" % (grouped(len(checked)), counted(len(self.forms), u"form feature"))),
                                         self.ak.html(u", ".join(checked)))
        # (a count bold with its noun; a number inside the parentheses, whose noun is outside, bold alone:
        # owner's images 297 and 301)
        self.status.setText(u"%s (%s standard, %s discretionary, %s off); %s with alternates taking turns. "
                            u"Forms: %s.%s%s%s%s" % (
                                b(counted(len(self.found), u"ligature")), b(grouped(counts["liga"])),
                                b(grouped(counts["dlig"])), b(grouped(counts["off"])),
                                b(counted(len(cycling), u"glyph")), forms,
                                u" The font has this code already." if not changes and (texts or self.forms) else u"",
                                (u" " + self.ak.html(refused_words(self.refused))) if getattr(self, "refused", None) else u"",
                                (u" " + self.ak.html(stuck_words(self.stuck))) if getattr(self, "stuck", None) else u"",
                                (u" The code has problems, so nothing can be written: " +
                                 self.ak.html(u"; ".join(problems))) if problems else u""))

    def show_font_line(self, package=None):
        """The top line: the font and its current master (ak.font_named, the same in every tool), the font
        given or the window's; the no-font line without one. Never raises."""
        package = package if package is not None else self.package
        try:
            if package is None:
                text = self.ak.no_font_line() if hasattr(self.ak, "no_font_line") else \
                    getattr(self.ak, "NO_FONT_LINE", None) or u"No font is open."
            else:
                try:
                    masters = len(list(package.masters))
                except Exception:
                    masters = 1
                text = self.ak.font_named(package.tfn, package.master, masters)
            self.top_line.setText(text)
        except Exception:
            pass

    def code_changed(self, features, tags):
        """Whether the font's code differs from the code read with the list: a feature of tags, or the prefix
        (one that cannot be read counts as unchanged, as it reads as the one read)."""
        try:
            prefix_now = features.get_prefix() or u""
        except Exception:
            prefix_now = self.prefix
        keys = features.keys()
        return prefix_now != self.prefix or \
            any((features.get_feature(tag) if tag in keys else None) != self.texts.get(tag) for tag in tags)

    def write(self):
        if self.package is None or self.busy:
            return
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(self.package):
            self.run()
            self.log.add(u"The font changed: here is this one's code. Nothing was written.", "warning")
            return
        features = self.package.fgPackage.features
        texts = self.new_texts()
        prefix = self.new_prefix()
        tags = set(("liga", "dlig", "calt")) | set(texts)
        stale = u"The features changed since they were read: here they are again. Nothing was written."
        if self.code_changed(features, tags):
            self.run()
            self.log.add(stale, "warning")
            return
        refusal = own_code_refusal(self.ak, self.package, dict((tag, texts[tag]) for tag in self.tags_shown(texts)),
                                   prefix, self.names)
        if refusal:
            link = getattr(self.ak, "tool_link", None)  # (a link that opens it in the window's place: image 220)
            self.log.add(u"Nothing was written: %s. %s lists every finding." % (
                self.ak.html(refusal), link(u"Feature Check") if link is not None else u"<i>Feature Check</i>"),
                "error")
            return
        # The feature code is the font's own state, but the step records the whole font, its glyphs too, which
        # have no state of their own in a font opened afresh: undone, FontLab printed a problem with each
        # glyph built from components (owner's image 336, a kerning write's)
        if not self.ak.begin_write(self.fontlab, self.package, u"FreeLab Feature Code", self.log):
            return
        written, error, skipped, changed = [], None, None, False
        # (the window's top row says what is under way; a write is never stopped half way)
        self.set_busy(True, u"Writing the code", stoppable=False)
        try:
            self.progress(u"Writing the code", force=True, stoppable=False)
            # The features compared with the font again after the bar's last event pump, and nothing lets events
            # through from here to the last setter: a queued callback that changed a feature after the first
            # comparison (set_busy and the bar let events through) would otherwise be overwritten with the code
            # composed before it (adversarial review 10)
            changed = self.code_changed(features, tags)
            if changed:
                raise _NothingWritten()
            if prefix is not None:
                setter = getattr(features, "set_prefix", None)
                try:
                    if setter is None:
                        raise AttributeError(u"this FontLab cannot write the prefix from a script")
                    setter(prefix)
                    written.append(u"the prefix")
                except Exception as exc:
                    # Without its languages declared, locl's rows would drop the other features for those
                    # languages: locl waits until the prefix has them
                    skipped = exc
                    texts.pop("locl", None)
            for tag in self.tags_shown(texts):
                if tag in self.texts and same_code(texts[tag], self.texts.get(tag)):
                    continue  # (the same code: not written again, nor named as written)
                features.set_feature(tag, texts[tag])
                written.append(tag)
            if u"aalt" in written and aalt_first(features):
                written[written.index(u"aalt")] = u"aalt (first among the features)"
        except _NothingWritten:
            pass
        except Exception as exc:
            error = exc
        finally:
            self.set_busy(False)
        if changed:  # (nothing written: the font's code, as it is now, read again)
            self.run()
            self.log.add(stale, "warning")
            return
        # (the feature code only, no glyph added; begun with begin_write above)
        status = self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Feature Code", added=False)
        forms, choices = self.form_state(), self.choice_state()
        self.run()
        self.apply_choices(choices)  # (Off included: Codex review 8, the font read again set it back as named)
        self.apply_form_state(forms)
        self.make_code()
        them = u"it" if len(written) == 1 else u"them"
        self.log.add(u"Wrote %s%s.%s" % (
            self.ak.b(u", ".join(written)), status.undo(u"; <i>Edit &gt; Undo</i> takes %s back" % them),
            self.ak.compiled_note(self.compile_box, self.log)) if written else u"Wrote nothing.",
            "done" if written else "info")
        status.report(self.log)
        if self.refused:
            self.log.add(self.ak.html(refused_words(self.refused)), "warning")
        if self.stuck:
            self.log.add(self.ak.html(stuck_words(self.stuck)), "warning")
        if skipped is not None:
            self.log.add(u"locl was not written: the prefix could not be (%s). Add these lines to the prefix in "
                         u"FontLab's <i>Features</i> panel, then write again: %s" % (
                             self.ak.html(skipped), self.ak.html(u" ".join(u"languagesystem %s %s;" % pair for pair in
                                                                           sorted(language_systems(self.locl()))))),
                         "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("Feature Code"):
            return
    except Exception:
        pass
    try:
        dialog = FeatureCodeDialog()
    except Exception as exc:
        print("FreeLab Feature Code: %s" % exc)
        return
    sys._freelab_feature_code = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("Feature Code", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_feature_code":
    main()
