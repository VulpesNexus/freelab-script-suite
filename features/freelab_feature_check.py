#FLM: Feature Check
# -*- coding: utf-8 -*-
"""FreeLab Feature Check, from FontLab's Scripts menu: checks a font's OpenType feature code (any font,
made with FreeLab or not) for errors, code that does nothing, and what can be improved, and lists each
finding for review. A fix is offered where one exists; a fix counts as safe only when the font's
layout compiled with it is the same as without it (proven for each fix, not assumed), and the
Apply safe fixes automatically option applies those at each check.

FreeLab's scripts that write feature code (Feature Code, Glyph Compose, CJK Spacing, CJK Vertical)
check what they are about to write with check_change: code that would bring a new error is not
written.

The checks run on fontTools' feature compiler (feaLib), which FontLab 7 ships (3.43); FontLab itself
compiles with Adobe's compiler, so the window can also compile in FontLab and report what it says.

Valid Python 2.7 (FontLab 7) and Python 3. The checks below the Qt line need no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import bisect
import io
import os
import re
import sys

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
SETTINGS_FILE = "feature_check.json"
LAYOUT_TABLES = ("GSUB", "GPOS")
BUILT_TABLES = ("GDEF", "GPOS", "GSUB", "name", "BASE")  # what the checks build (not head, OS/2, hhea, vhea)
PAIRS_PROVEN_MAX = 3000000  # kerning pairs a proof expands at most; past that a kerning change is not proven
BUILD_RETRIES = 24  # parts taken out, one per compiler error, to find the next error
FONTLAB_AUTO, FONTLAB_HANDED = "#> feature", "#/> feature"  # FontLab's automatic code (as Feature Code reads it)
FEA_TOKEN = re.compile('#[^\\n]*|"[^"]*"?|[;{}]|[^\\s;{}#"]+')

ERROR, WARNING, ADVICE = "error", "warning", "advice"
SEVERITY_ORDER = {ERROR: 0, WARNING: 1, ADVICE: 2}

# The kinds of finding: (severity, the group's title in the list, one finding, several, what it means).
KINDS = {
    "syntax": (ERROR, "Syntax errors", "error", "errors",
               "Code the compiler cannot read: nothing of the font's features compiles until it is mended."),
    "missing-glyph": (ERROR, "Glyphs not in the font", "glyph", "glyphs",
                      "Names of glyphs the font does not have: the compiler stops at the first one."),
    "build": (ERROR, "Rules the compiler refuses", "rule", "rules",
              "Code that reads well but cannot be compiled as written."),
    "flag": (ERROR, "Lookup flags without their class", "flag", "flags",
             "A lookupflag that sets UseMarkFilteringSet (16) or a mark attachment type without naming the "
             "class it needs (FontLab writes these when it opens some fonts): fontTools refuses it, and the "
             "lookup's marks are not filtered as meant. Name the class (UseMarkFilteringSet @marks;) or drop "
             "the flag."),
    "aalt-lookups": (ERROR, "Lookups inside aalt", "feature", "features",
                     "FontLab writes the lookups of aalt inside the feature when it opens some fonts; neither its "
                     "own compiler nor fontTools takes a lookup there, so no feature compiles. The fix writes "
                     "their rules straight into aalt, which both take."),
    "overflow": (ERROR, "Tables too large", "table", "tables",
                 "A layout table larger than its offsets reach, even split up."),
    "conflict": (WARNING, "Glyphs given two ways in one lookup", "glyph", "glyphs",
                 "fontTools refuses these; Adobe's compiler (FontLab's) keeps the first rule and drops the others."),
    "language": (WARNING, "Languages without a languagesystem line", "language", "languages",
                 "A feature names a script or language the prefix does not declare: in text in that "
                 "language, the font's other features are missing."),
    "no-default": (WARNING, "No default language system", "line", "lines",
                   "The prefix declares language systems but not DFLT dflt: text in any script it does not "
                   "name gets no features."),
    "empty-class": (WARNING, "Empty classes", "class", "classes",
                    "A class with no glyph: a rule using it never applies."),
    "class-redefined": (WARNING, "Classes defined twice, differently", "class", "classes",
                        "A class defined again with other glyphs (in FontLab's classes and in the code, or twice in "
                        "the code): each rule uses the definition last read before it, which may not be the one "
                        "meant."),
    "aalt-order": (ADVICE, "aalt not first", "feature", "features",
                   "The specification asks for aalt before the other features."),
    "duplicate-rule": (ADVICE, "Rules written twice", "rule", "rules",
                       "The same rule again, in the same lookup: the second does nothing."),
    "identity": (ADVICE, "Substitutions that change nothing", "rule", "rules",
                 "A glyph substituted by itself."),
    "class-duplicates": (ADVICE, "Glyphs listed twice in a class", "class", "classes",
                         "A class that names a glyph more than once (a class whose glyphs pair with another "
                         "class's, as \"sub @a by @b;\" gives @b, needs its repeats: not listed)."),
    "class-repeated": (ADVICE, "Classes defined twice", "class", "classes",
                       "A class defined again in the code with the same glyphs: the second definition does nothing."),
    "unused-class": (ADVICE, "Classes never used", "class", "classes",
                     "A class defined in the code that no rule or other class uses."),
    "unused-lookup": (ADVICE, "Lookups never used", "lookup", "lookups",
                      "A lookup defined outside every feature that no feature or rule refers to: it is compiled "
                      "into the font and never applied."),
    "empty-lookup": (ADVICE, "Empty lookups", "lookup", "lookups", "A lookup with no rule."),
    "empty-feature": (ADVICE, "Features with no rule", "feature", "features",
                      "A feature with nothing in it: apps may list it, and it does nothing."),
    "fontlab": (ERROR, "What FontLab's compiler said", "message", "messages",
                "Read from FontLab's Output panel after compiling there."),
}
# Kinds whose fixes the Apply safe fixes automatically option applies (each still proven first)
AUTO_KINDS = ("duplicate-rule", "identity", "class-duplicates", "class-repeated", "unused-class", "unused-lookup")


class Stopped(Exception):
    """A check stopped from its progress callback."""


def step(progress, what, done=0, total=1):
    """progress(what, done, total), when given: the window's bar moved (it may raise Stopped)."""
    if progress is not None:
        progress(what, done, total)


def grouped(number):
    """A whole number with its thousands set apart by commas: 13,932 (owner's image 231)."""
    return "{:,}".format(int(number))


def counted(number, one, many=None):
    """"1 rule", "2 rules", "13,932 glyphs": a count (thousands grouped) with its noun in the right number."""
    return "%s %s" % (grouped(number), one if number == 1 else (many or one + "s"))


def has_code(code):
    """Whether a FontCode holds any feature code to compile (a prefix or a feature with text): without
    it, Compile in FontLab has nothing to do."""
    return bool((code.prefix or "").strip() or any((text or "").strip() for _, text in code.features))


def _text(value):
    if value is None:
        return ""
    if sys.version_info[0] == 2 and isinstance(value, str):  # (bytes under 2.7)
        return value.decode("utf-8", "replace")
    return "%s" % value


# ---------------------------------------------------------------------------
# The font's code, in parts (FontLab keeps its classes, the prefix, and each feature apart)
# ---------------------------------------------------------------------------


class FontCode(object):
    """A font's feature code as FontLab keeps it: its OpenType classes (the Classes panel's, which the
    code may use but does not hold), its prefix, and its features in order (each the whole block:
    "feature liga { ... } liga;"). text() puts them together as they are compiled."""

    def __init__(self, prefix="", features=(), classes=()):
        self.prefix = _text(prefix)
        self.features = [(_text(tag), _text(text)) for tag, text in features]
        self.classes = [(_text(name).lstrip("@"), [_text(g) for g in glyphs]) for name, glyphs in classes]

    def copy(self):
        return FontCode(self.prefix, list(self.features), [(n, list(g)) for n, g in self.classes])

    def keys(self):
        return ["classes", "prefix"] + ["feature:%s" % tag for tag, _ in self.features]

    def part(self, key):
        if key == "classes":
            return self.classes_text()
        if key == "prefix":
            return self.prefix
        tag = key.split(":", 1)[1]
        for t, text in self.features:
            if t == tag:
                return text
        return None

    def with_part(self, key, text):
        """A copy with that part's text replaced (None: a feature taken out)."""
        new = self.copy()
        if key == "prefix":
            new.prefix = text or ""
        elif key.startswith("feature:"):
            tag = key.split(":", 1)[1]
            new.features = [(t, text if t == tag else old) for t, old in new.features
                            if not (t == tag and text is None)]
        return new

    def classes_text(self):
        return "".join("@%s = [%s];\n" % (name, " ".join(glyphs)) for name, glyphs in self.classes)

    def pieces(self, skip=()):
        """[(key, text)] in compiling order, each ending with a line break."""
        out = []
        for key in self.keys():
            if key in skip:
                continue
            text = self.part(key) or ""
            if text and not text.endswith("\n"):
                text += "\n"
            out.append((key, text))
        return out

    def text(self, skip=()):
        """(the whole code as compiled, [(key, first line, line count)]), lines counted from 1."""
        pieces = self.pieces(skip)
        spans, line = [], 1
        for key, text in pieces:
            count = text.count("\n")
            spans.append((key, line, count))
            line += count
        return "".join(text for _, text in pieces), spans

    def same(self, other):
        return self.prefix == other.prefix and self.features == other.features and self.classes == other.classes


def locate(spans, line):
    """(part key, line within the part) of a line of the whole code (FontCode.text's spans)."""
    for key, first, count in spans:
        if first <= line < first + max(count, 1):
            return key, line - first + 1
    if spans:
        key, first, count = spans[-1]
        return key, line - first + 1
    return "prefix", line


def part_label(key):
    """"the prefix", "liga", "FontLab's classes"."""
    if key == "prefix":
        return "the prefix"
    if key == "classes":
        return "FontLab's classes"
    return key.split(":", 1)[1] if key.startswith("feature:") else key


# ---------------------------------------------------------------------------
# Findings and fixes
# ---------------------------------------------------------------------------


class Edit(object):
    """A change to one part's text: [start, end) replaced by new (offsets in that part)."""

    def __init__(self, key, start, end, new=""):
        self.key, self.start, self.end, self.new = key, start, end, new


class Fix(object):
    """What a finding's fix does (a sentence) and its edits; safe once proven (prove)."""

    def __init__(self, what, edits, remove_feature=None):
        self.what = what
        self.edits = list(edits)
        self.remove_feature = remove_feature  # a feature taken out of the font altogether (its tag)
        self.safe = None  # True: proven to leave the compiled layout as it was; False: proven not; None: unknown
        self.review = False  # True: a fix that changes what the font does by design (never proven, never automatic)
        self.repair = False  # True (with review): it mends code that does not compile


class Finding(object):
    def __init__(self, kind, message, key="prefix", line=None, subject=None, fix=None, automatic=False):
        self.kind = kind
        self.severity = KINDS[kind][0]
        self.message = message
        self.key = key  # the part it is in
        self.line = line  # its line in that part, from 1
        self.subject = subject  # the glyph, class, lookup, or feature it is about
        self.fix = fix
        self.automatic = automatic  # in FontLab's automatic code (FontLab rewrites it: no fix)

    def where(self):
        label = part_label(self.key)
        return "%s, line %d" % (label, self.line) if self.line else label

    def identity(self):
        """What a finding is, its place left out: the same problem before and after an edit."""
        return (self.kind, self.key, self.subject or self.message)

    def __repr__(self):
        return "<Finding %s %s: %s>" % (self.kind, self.where(), self.message)


def apply_edits(code, edits):
    """A copy of code with edits applied (overlapping ones after the first are skipped)."""
    by_key = {}
    for edit in edits:
        by_key.setdefault(edit.key, []).append(edit)
    new = code
    for key, group in by_key.items():
        text = code.part(key)
        if text is None or key == "classes":
            continue
        group.sort(key=lambda e: (e.start, -e.end))  # (of two from one place, the wider: a removal)
        kept, last = [], -1
        for edit in group:
            if edit.start >= last:
                kept.append(edit)
                last = edit.end
        pieces, at = [], 0  # (put together once: 688 edits each copied a 255 KB prefix; review 11)
        for edit in kept:
            pieces.append(text[at:edit.start])
            pieces.append(edit.new)
            at = edit.end
        pieces.append(text[at:])
        new = new.with_part(key, "".join(pieces))
    return new


def apply_fixes(code, fixes):
    edits = []
    for fix in fixes:
        edits.extend(fix.edits)
    new = apply_edits(code, edits)
    for fix in fixes:
        if fix.remove_feature:
            new = new.with_part("feature:%s" % fix.remove_feature, None)
    return new


# ---------------------------------------------------------------------------
# Tokens and statements (a statement's span in a part's text, for fixes)
# ---------------------------------------------------------------------------


_TEXT_INDEX = {}  # {text: (its tokens, their ends, its line starts)}, the last few texts read


def text_index(text):
    """(tokens, token ends, line starts) of a text, made once a text: a feature with thousands of
    findings had its whole text tokenized again for each (review 9)."""
    text = text or ""
    held = _TEXT_INDEX.get(text)
    if held is None:
        toks = [(m.group(0), m.start(), m.end()) for m in FEA_TOKEN.finditer(text)
                if not m.group(0).startswith(("#", '"'))]
        starts = [0] + [m.end() for m in re.finditer("\n", text)]
        held = (toks, [t[2] for t in toks], starts)
        if len(_TEXT_INDEX) >= 8:
            _TEXT_INDEX.clear()
        _TEXT_INDEX[text] = held
    return held


def tokens(text):
    """[(token, start, end)], comments and strings left out."""
    return text_index(text)[0]


def line_offset(text, line, column=1):
    """The offset of a line (from 1) and column (from 1) in text."""
    starts = text_index(text)[2]
    if line - 1 >= len(starts):
        return len(text)
    return min(starts[max(line, 1) - 1] + max(column, 1) - 1, len(text))


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def statement_span(text, start):
    """(start, end) of the statement beginning at offset start: to its semicolon, or for a block
    ("lookup NAME { ... } NAME;") to the semicolon after its closing brace. None where it cannot be
    told."""
    all_tokens, ends, _ = text_index(text)
    first = bisect.bisect_right(ends, start)
    if first >= len(all_tokens):
        return None
    begin = all_tokens[first][1]
    depth = 0
    for k in range(first, len(all_tokens)):
        tok, s, e = all_tokens[k]
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
            if depth < 0:
                return None
        elif tok == ";" and depth == 0:
            return begin, e
    return None


def whole_lines(text, start, end):
    """(start, end) widened to whole lines where nothing else stands on them (indentation and the line
    break go too); else as given."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    before, after = text[line_start:start], text[end:line_end]
    if before.strip() or (after.strip() and not after.strip().startswith("#")):
        return start, end
    if after.strip():  # (a comment after it on its line stays)
        return start, end
    return line_start, min(line_end + 1, len(text))


def automatic_spans(text):
    """[(start, end)] of FontLab's automatic code in a part: from a "#> feature" comment to the next "#<"."""
    spans, opened = [], None
    for m in FEA_TOKEN.finditer(text or ""):
        token = m.group(0)
        if not token.startswith("#"):
            continue
        token = token.strip()
        if opened is None and token.startswith(FONTLAB_AUTO):
            opened = m.start()
        elif opened is not None and token.startswith("#<"):
            spans.append((opened, m.end()))
            opened = None
    if opened is not None:
        spans.append((opened, len(text)))
    return spans


def block_end(toks, k):
    """The index of the "}" closing the "{" at toks[k], or None."""
    depth = 0
    for j in range(k, len(toks)):
        if toks[j][0] == "{":
            depth += 1
        elif toks[j][0] == "}":
            depth -= 1
            if depth == 0:
                return j
    return None


def aalt_lookups(text):
    """[(start, end, name, body start, body end)] of the lookup blocks written inside a feature aalt block
    (FontLab writes its aalt so: "feature aalt { ... lookup aalt_2 useExtension { ... } aalt_2; }"), which
    neither FontLab's compiler ("'lookup' use not allowed in 'aalt' feature", live) nor fontTools takes."""
    toks = tokens(text)
    out = []
    k = 0
    while k < len(toks) - 1:
        if toks[k][0] == "feature" and toks[k + 1][0] == "aalt":
            opening = k + 2
            while opening < len(toks) and toks[opening][0] not in ("{", ";"):
                opening += 1
            if opening >= len(toks) or toks[opening][0] != "{":
                return out
            closing = block_end(toks, opening)
            if closing is None:
                return out
            j = opening + 1
            while j < closing:
                tok = toks[j][0]
                if tok == "{":
                    j = (block_end(toks, j) or closing) + 1
                    continue
                if tok == "lookup" and j + 2 < closing:
                    brace = j + 2
                    if toks[brace][0] == "useExtension":
                        brace += 1
                    if toks[brace][0] == "{":
                        end = block_end(toks, brace)
                        if end is None or end + 2 > closing or toks[end + 2][0] != ";":
                            return out
                        out.append((toks[j][1], toks[end + 2][2], toks[j + 1][0], toks[brace][2], toks[end][1]))
                        j = end + 3
                        continue
                j += 1
            k = closing + 1
            continue
        k += 1
    return out


AALT_REFUSAL = re.compile(r"Lookup blocks cannot be placed inside 'aalt'|not allowed in 'aalt'", re.I)
AALT_FLAG = re.compile(r"^\s*lookupflag\b[^;]*;[ \t]*\n?", re.M)


def aalt_unwrap_fix(text, key, found):
    """A Fix writing the rules of aalt's lookup blocks straight into aalt, where both compilers take them
    (aalt makes its own lookups of the single and alternate substitutions it holds): each block's body
    kept, its "lookup NAME {", "} NAME;" and lookup flags taken out."""
    edits = []
    for start, end, name, body_start, body_end in found:
        body = AALT_FLAG.sub("", text[body_start:body_end]).strip()
        if body and "#" in body.splitlines()[-1]:
            body += "\n"  # (a comment ending it: what follows on the line stays out of it; review 12)
        edits.append(Edit(key, start, end, body))
    fix = Fix("Write the rules of %s straight into aalt" % ", ".join(f[2] for f in found[:4]) +
              (", ..." if len(found) > 4 else ""), edits)
    fix.review = True
    fix.repair = True
    return fix


def aalt_findings(code):
    """FontLab's aalt with lookup blocks inside it: an error each part that has one, with its repair."""
    out = []
    for key in code.keys():
        text = code.part(key)
        if key == "classes" or not text or "aalt" not in text:
            continue
        found = aalt_lookups(text)
        if found:
            line = line_of(text, found[0][0])
            out.append(Finding("aalt-lookups", "aalt holds %s (%s): neither FontLab's compiler nor fontTools takes "
                               "a lookup there" % (counted(len(found), "lookup block"),
                                                   ", ".join(f[2] for f in found[:4]) + (", ..." if len(found) > 4 else "")),
                               key, line, subject="aalt lookups", fix=aalt_unwrap_fix(text, key, found)))
    return out


NAME_IN_WORD = re.compile(r"@?[A-Za-z_.][\w.\-]*")


def part_words(text):
    """Every name a part's code uses (comments and strings left out): glyph classes as "@name" (also inside
    a compact "@B=[@A]"), lookups and other words bare."""
    out = set()
    for tok in tokens(text):
        out.update(NAME_IN_WORD.findall(tok[0]))
    return out


# ---------------------------------------------------------------------------
# fontTools
# ---------------------------------------------------------------------------


def fealib():
    """fontTools' feaLib pieces, or None without fontTools."""
    try:
        from fontTools.feaLib import ast
        from fontTools.feaLib.builder import Builder
        from fontTools.feaLib.error import FeatureLibError
        from fontTools.feaLib.parser import Parser
        from fontTools.ttLib import TTFont, newTable
    except Exception:
        return None
    return {"ast": ast, "Builder": Builder, "Error": FeatureLibError, "Parser": Parser, "TTFont": TTFont,
            "newTable": newTable}


def error_line(exc):
    """(line, column) of a feaLib error, or (None, None)."""
    location = getattr(exc, "location", None)
    try:
        if location is not None:
            return int(location[1]), int(location[2])
    except Exception:
        pass
    match = re.match(r"^.*?:(\d+):(\d+): ", _text(exc))
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def error_message(exc):
    """A feaLib error's message, its location left out."""
    text = _text(exc)
    match = re.match(r"^.*?:\d+:\d+: (.*)$", text, re.S)
    return (match.group(1) if match else text).strip()


MISSING_AT_PARSE = re.compile(r"glyph names are referenced but are missing from the glyph set:\s*(.*)", re.S)


def parse(lib, text, names):
    """The parsed code (a FeatureFile), or raises feaLib's error. fontTools 4 refuses glyphs the font
    lacks while parsing (3.43 does not): those are added to the names and parsed again, so that both
    read alike and missing_glyphs reports them."""
    names = set(names)
    for _ in range(3):
        parser = lib["Parser"](io.StringIO(text), glyphNames=names, followIncludes=False)
        try:
            return parser.parse()
        except lib["Error"] as exc:
            found = MISSING_AT_PARSE.search(error_message(exc))
            if not found:
                raise
            extra = set(re.findall(r"(?:^|\n)\s*(\S+) \(first found at", found.group(1)))
            if not extra or extra <= names:
                raise
            names |= extra
    return lib["Parser"](io.StringIO(text), glyphNames=names, followIncludes=False).parse()


def stub_font(lib, order):
    font = lib["TTFont"]()
    font.setGlyphOrder(list(order))
    name = lib["newTable"]("name")
    name.names = []
    font["name"] = name
    return font


def build(lib, text, order, doc=None):
    """A stub font with the code's layout tables built, or raises the compiler's error."""
    font = stub_font(lib, order)
    builder = lib["Builder"](font, io.StringIO(text))
    if doc is not None:
        builder.parseTree = doc
    builder.build(tables=BUILT_TABLES)
    return font


# ---------------------------------------------------------------------------
# Reading the parsed code. Statements are gone through one by one, and only the values that can hold
# glyphs or classes are looked into: a walk through every element (anchors and value records included,
# and a named class again under each rule using it) took 11 s of Amiri's 19 (live, 2026-11-17).
# ---------------------------------------------------------------------------


def kind_of(node):
    return type(node).__name__


def location_of(node):
    location = getattr(node, "location", None)
    try:
        return int(location[1]), int(location[2])
    except Exception:
        return None, None


def statements_of(block):
    return list(getattr(block, "statements", None) or [])


RULE_KINDS = ("SingleSubstStatement", "MultipleSubstStatement", "AlternateSubstStatement",
              "LigatureSubstStatement", "ReverseChainSingleSubstStatement", "ChainContextSubstStatement",
              "IgnoreSubstStatement", "SinglePosStatement", "PairPosStatement", "CursivePosStatement",
              "MarkBasePosStatement", "MarkLigPosStatement", "MarkMarkPosStatement",
              "ChainContextPosStatement", "IgnorePosStatement", "LookupReferenceStatement",
              "FeatureReferenceStatement", "SubtableStatement", "SizeParameters", "FeatureNameStatement",
              "CVParametersNameStatement", "CharacterStatement", "NestedBlock")


def has_rules(block):
    for st in statements_of(block):
        name = kind_of(st)
        if name in RULE_KINDS:
            return True
        if name == "LookupBlock" and has_rules(st):
            return True
    return False


def glyph_uses(doc):
    """[(glyph name, statement)] of every glyph named by the code's statements (a class's glyphs once,
    where it is defined), in order."""
    out = []
    strings = (str, type(""))

    def expression(value, statement, depth=0):
        # Only what can hold glyphs is looked into: a glyph, a class written out, and lists of them (a
        # walk through every anchor and value record took Amiri 11 s, live 2026-11-17). A class named
        # (@name) is counted where it is defined.
        name = type(value).__name__
        if name == "GlyphName":
            out.append((_text(value.glyph), statement))
        elif name == "GlyphClass":
            for glyph in value.glyphs:
                if isinstance(glyph, strings):
                    out.append((_text(glyph), statement))
        elif isinstance(value, (list, tuple)) and depth < 4:
            for item in value:
                expression(item, statement, depth + 1)

    def visit(statement):
        name = kind_of(statement)
        for attr, value in statement.__dict__.items():
            if attr in ("lookups", "location", "glyphclass") or isinstance(value, strings):
                continue
            expression(value, statement)
        if name in ("LigatureSubstStatement", "MultipleSubstStatement"):
            # (their output is a plain name, or a list of them, in some fontTools: not a GlyphName)
            replacement = getattr(statement, "replacement", None)
            for glyph in (replacement if isinstance(replacement, (list, tuple)) else [replacement]):
                if isinstance(glyph, strings):
                    out.append((_text(glyph), statement))

    def statements(block):
        for st in statements_of(block):
            if kind_of(st) in ("FeatureBlock", "LookupBlock", "NestedBlock", "TableBlock"):
                statements(st)
            else:
                visit(st)

    statements(doc)
    return out


def class_definitions(doc):
    """[(definition, the block it is in or None)] of the code's named glyph classes."""
    out = []

    def visit(block, owner):
        for st in statements_of(block):
            name = kind_of(st)
            if name == "GlyphClassDefinition":
                out.append((st, owner))
            elif name in ("FeatureBlock", "LookupBlock", "NestedBlock"):
                visit(st, st)

    visit(doc, None)
    return out


BLOCKS = ("FeatureBlock", "LookupBlock", "NestedBlock", "TableBlock")


def all_statements(doc):
    """Every statement of the code, the blocks' own and those inside them, in order."""
    for st in statements_of(doc):
        yield st
        if kind_of(st) in BLOCKS:
            for inner in all_statements(st):
                yield inner


def class_names(value, depth=0):
    """The GlyphClassName elements in a statement's value (lists, classes written out and the classes
    named in them)."""
    name = type(value).__name__
    if name == "GlyphClassName":
        yield value
    elif name == "GlyphClass":
        for item in getattr(value, "original", None) or []:
            for found in class_names(item, depth + 1):
                yield found
    elif isinstance(value, (list, tuple)) and depth < 5:
        for item in value:
            for found in class_names(item, depth + 1):
                yield found


def class_references(doc):
    """{id(definition): count} of named glyph classes used by any statement or other class."""
    used = {}
    for st in all_statements(doc):
        if kind_of(st) in BLOCKS:
            continue
        for attr, value in st.__dict__.items():
            if attr == "location":
                continue
            for node in class_names(value):
                target = getattr(node, "glyphclass", None)
                if target is not None:
                    used[id(target)] = used.get(id(target), 0) + 1
    return used


def lookup_references(doc):
    """{id(lookup block): count} of lookups referred to (a "lookup NAME;" or a contextual rule's)."""
    used = {}
    for node in all_statements(doc):
        name = kind_of(node)
        if name == "LookupReferenceStatement":
            target = getattr(node, "lookup", None)
            if target is not None:
                used[id(target)] = used.get(id(target), 0) + 1
        elif name in ("ChainContextSubstStatement", "ChainContextPosStatement"):
            for item in getattr(node, "lookups", None) or []:
                for target in (item if isinstance(item, (list, tuple)) else [item]):
                    if target is not None:
                        used[id(target)] = used.get(id(target), 0) + 1
    return used


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


class Report(object):
    def __init__(self, code, findings, compiled=None, parsed=False, built=False, unavailable=None, provable=None):
        self.code = code
        self.provable = provable  # the parts of code that compile (fixes are proven on it), or None
        self.order = None  # the glyph order it was built with: the font's, then the glyphs it lacks
        self.findings = findings
        self.compiled = compiled  # the stub font with the layout built (None: it did not build)
        self.parsed, self.built = parsed, built
        self.unavailable = unavailable  # why fontTools' checks could not run, else None

    def errors(self):
        return [f for f in self.findings if f.severity == ERROR]

    def by_kind(self):
        groups = {}
        for f in self.findings:
            groups.setdefault(f.kind, []).append(f)
        return groups


def check(code, glyph_order, progress=None):
    """A Report of the font's code (a FontCode) against its glyphs (in the font's order): every
    finding, with the fixes found (not yet proven: prove_fixes). progress: see step."""
    lib = fealib()
    findings = []
    names = set(glyph_order)
    if lib is None:
        return Report(code, findings, unavailable="fontTools is not installed")
    step(progress, "Reading the code")
    text, spans = code.text()
    doc, parse_error = None, None
    try:
        doc = parse(lib, text, names)
    except Exception as exc:
        parse_error = exc
    good = code
    if parse_error is not None:
        syntax, good = readable_parts(lib, code, names, progress)
        findings.extend(syntax)
        text, spans = good.text()
        try:
            doc = parse(lib, text, names)
        except Exception:
            doc = None
    if doc is None:
        return Report(code, sort_findings(findings), parsed=False)
    step(progress, "Looking through the code")
    # The words of the parts set aside for a syntax error: a class or lookup they name is used, though
    # the parsed code no longer shows it (a CJK font's 688 aalt classes were all "never used", live)
    aside = set()
    for key in code.keys():
        if code.part(key) is not None and good.part(key) != code.part(key):
            aside |= part_words(code.part(key))
    uses = glyph_uses(doc)
    findings.extend(missing_glyphs(uses, spans, names))
    findings.extend(lint(doc, good, spans, names, aside))
    flags = flag_findings(doc, good, spans)
    findings.extend(flags)
    order = list(glyph_order)  # (with the glyphs the font lacks after its own: they hide no other error)
    for glyph, _ in uses:
        if glyph not in names:
            names.add(glyph)
            order.append(glyph)
    # (built with those flags made buildable and the rules written twice blanked, each at the same width:
    # they hide no other error, and the offsets of every fix stay right)
    # The code as it is, where it compiles, is what every fix is proven against; the made-buildable copy
    # only where it does not (a fix proven against a copy that already lacked what it removes proved
    # nothing: review 9)
    # FontLab's aalt, its lookups written inside it: neither compiler takes it (live, 2026-11-17: FontLab's
    # "'lookup' use not allowed in 'aalt' feature"). An error with its repair; fontTools' own words for it
    # are left out of the list
    aalt = aalt_findings(code)
    findings.extend(aalt)
    step(progress, "Compiling")
    buildable = good
    font, built_findings, provable = build_findings(lib, buildable, order, doc)
    neutral = [f.neutral for f in findings if getattr(f, "neutral", None) is not None]
    if neutral and (font is None or built_findings):
        buildable = apply_edits(good, neutral)
        font, built_findings, provable = build_findings(lib, buildable, order, None)
    if aalt:
        built_findings = [f for f in built_findings if not AALT_REFUSAL.search(f.message)]
    findings.extend(built_findings)
    findings = mark_automatic(findings, code)
    report = Report(code, sort_findings(findings), compiled=font, parsed=parse_error is None,
                    built=parse_error is None and font is not None and not built_findings and not flags and not aalt,
                    provable=provable)
    report.order = order
    report.buildable = buildable
    return report


def flag_findings(doc, code, spans):
    """lookupflag statements that set UseMarkFilteringSet (16) or a mark attachment type (the high
    byte) without naming the class it needs, as FontLab writes them on opening some fonts ("lookupflag
    16;", 29 times in Amiri): fontTools refuses them, and the marks are not filtered as meant. Each with
    the same statement made buildable (that bit cleared, the text kept at its width) in .neutral."""
    out = []
    for node in all_statements(doc):
        if kind_of(node) != "LookupFlagStatement":
            continue
        value = getattr(node, "value", 0) or 0
        if not isinstance(value, int):
            continue
        missing = []
        if value & 0x10 and getattr(node, "markFilteringSet", None) is None:
            missing.append(("UseMarkFilteringSet", 0x10))
        if value & 0xFF00 and getattr(node, "markAttachment", None) is None:
            missing.append(("MarkAttachmentType", 0xFF00))
        if not missing:
            continue
        line, _ = location_of(node)
        key, at = locate(spans, line) if line else ("prefix", None)
        message = "lookupflag %d sets %s without naming its class" % (value, " and ".join(m[0] for m in missing))
        f = Finding("flag", message, key, at, subject="lookupflag %d" % value)
        found = node_span(code, spans, node)
        if found is not None:
            part, start, end = found
            statement = code.part(part)[start:end]
            cleared = value
            for _, bits in missing:
                cleared &= ~bits
            new = re.sub(r"\b%d\b" % value, "%d" % cleared, statement, count=1)
            if new != statement:
                f.neutral = Edit(part, start, end, new + " " * (len(statement) - len(new)))
                # The fix a review can take: the bit dropped (its class cannot be told from the code: the
                # font FontLab opened had it in its GDEF); never proven safe, since the lookup then
                # applies to marks it skipped
                f.fix = Fix("Clear %s (every mark then counts)" % " and ".join(m[0] for m in missing),
                            [Edit(part, start, end, new)])
                f.fix.review = True
        out.append(f)
    return out


def sort_findings(findings):
    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.kind, f.key, f.line or 0))


def part_lines(code):
    return dict((key, text) for key, text in code.pieces())


def readable_parts(lib, code, names, progress=None):
    """(one syntax error per part that has one, code without the features that do not read: the prefix
    kept unless it does not read): each part parsed after the parts before it that read well (the
    classes and lookups they define stay known). One pass for both (two parsed a CJK font's 255 KB
    prefix 24 times)."""
    findings, good, context = [], code, ""
    pieces = code.pieces()
    for number, (key, text) in enumerate(pieces):
        step(progress, "Reading the code", number, len(pieces))
        try:
            parse(lib, context + text, names)
            context += text
        except Exception as exc:
            line, _ = error_line(exc)
            first = context.count("\n") + 1
            if line is not None and line < first:
                line = None  # (an error the part's own code does not hold: reported at the part)
            findings.append(Finding("syntax", error_message(exc), key, (line - first + 1) if line else None))
            if key.startswith("feature:"):
                good = good.with_part(key, None)
            elif key == "prefix":
                good = good.with_part(key, "")
    return findings, good


def syntax_findings(lib, code, names):
    return readable_parts(lib, code, names)[0]


def readable_code(lib, code, names):
    return readable_parts(lib, code, names)[1]


def missing_glyphs(uses, spans, names):
    """A finding per glyph name the font lacks (where first named; how many times in the message), from
    glyph_uses."""
    seen = {}
    for glyph, statement in uses:
        if glyph in names:
            continue
        line, _ = location_of(statement)
        if glyph not in seen:
            seen[glyph] = [line, 0]
        seen[glyph][1] += 1
    out = []
    for glyph, (line, count) in seen.items():
        key, at = locate(spans, line) if line else ("prefix", None)
        more = " (named %s)" % counted(count, "time") if count > 1 else ""
        out.append(Finding("missing-glyph", "%s is not in the font%s" % (glyph, more), key, at, subject=glyph))
    return out


def node_span(code, spans, node):
    """(part key, start, end) of a statement in its part's text, or None."""
    line, column = location_of(node)
    if line is None:
        return None
    key, at = locate(spans, line)
    text = code.part(key)
    if text is None or key == "classes":
        return None
    start = line_offset(text, at, column)
    span = statement_span(text, start)
    if span is None:
        return None
    return key, span[0], span[1]


def removal(code, spans, node, what):
    """A Fix removing a statement (or a block), whole lines where it stands alone, or None."""
    found = node_span(code, spans, node)
    if found is None:
        return None
    key, start, end = found
    text = code.part(key)
    start, end = whole_lines(text, start, end)
    return Fix(what, [Edit(key, start, end, "")])


def lint(doc, code, spans, names, aside=frozenset()):
    """aside: the words of the parts set aside for a syntax error (a class or lookup they name is used)."""
    findings = []
    findings.extend(class_findings(doc, code, spans, aside))
    findings.extend(lookup_findings(doc, code, spans, aside))
    findings.extend(feature_findings(doc, code, spans))
    findings.extend(rule_findings(doc, code, spans))
    findings.extend(language_findings(doc, code, spans))
    return findings


def paired_classes(doc):
    """ids of the class definitions whose glyphs pair one by one with another class's: the replacement of
    "sub @a by @b;" (two of @a's glyphs may become one glyph: @b names it twice, and must)."""
    out = set()
    for st in all_statements(doc):
        if kind_of(st) != "SingleSubstStatement":
            continue
        for value in getattr(st, "replacements", None) or []:
            target = getattr(value, "glyphclass", None) if type(value).__name__ == "GlyphClassName" else None
            if target is not None:
                out.add(id(target))
    return out


def class_glyphs(definition):
    glyphs = list(getattr(definition.glyphs, "glyphs", None) or []) if hasattr(definition, "glyphs") else []
    try:
        glyphs = list(definition.glyphSet())
    except Exception:
        pass
    return glyphs


def redefinition_findings(definitions, code, spans):
    """A class defined more than once: with other glyphs (a warning: rules use whichever was read last
    before them), or with the same ones in the code (advice: the later ones removed). FontLab writes each
    of its classes into the prefix too, the same: those are not listed."""
    by_name = {}
    for definition, owner in definitions:
        if owner is None:
            by_name.setdefault(_text(definition.name), []).append(definition)
    out = []
    for name, found in by_name.items():
        if len(found) < 2:
            continue
        places = []
        for definition in found:
            line, _ = location_of(definition)
            key, at = locate(spans, line) if line else ("prefix", None)
            places.append((key, at, class_glyphs(definition), definition))
        first_key, first_at = places[0][0], places[0][1]
        if any(p[2] != places[0][2] for p in places[1:]):
            shown = "; ".join("%s (%s)" % (part_label(k) + (", line %d" % a if a else ""),
                                           counted(len(g), "glyph")) for k, a, g, _ in places[:4])
            last_key, last_at = places[-1][0], places[-1][1]
            fix = None
            panel = [p for p in places if p[0] == "classes"]
            if panel and places[-1][0] != "classes":
                # (FontLab's class is what it keeps: the code's copy made the same again, for review; a CJK
                # font's prefix copy of @aalt2 lost its repeats, and "sub @aalt by @aalt2;" broke, live)
                found = node_span(code, spans, places[-1][3])
                if found is not None:
                    part, start, end = found
                    fix = Fix("Make it FontLab's class again (%s)" % counted(len(panel[-1][2]), "glyph"),
                              [Edit(part, start, end, "@%s = [%s];" % (name, " ".join(panel[-1][2])))])
                    fix.review = True
            out.append(Finding("class-redefined", "@%s is defined %s, differently: %s" % (
                name, "twice" if len(places) == 2 else "%d times" % len(places), shown), last_key, last_at,
                subject="@" + name, fix=fix))
            continue
        later = [p for p in places[1:] if p[0] != "classes"]
        if not later or (len(later) == len(places) - 1 and places[0][0] == "classes" and len(later) == 1):
            continue  # (FontLab's class and its copy in the prefix: FontLab's own)
        for key, at, _, definition in later:
            fix = removal(code, spans, definition, "Remove this definition")
            out.append(Finding("class-repeated", "@%s is defined again, the same (first: %s)" % (
                name, part_label(first_key) + (", line %d" % first_at if first_at else "")), key, at,
                subject="@%s again" % name, fix=fix))
    return out


def class_findings(doc, code, spans, aside=frozenset()):
    out = []
    used = class_references(doc)
    paired = paired_classes(doc)
    definitions = class_definitions(doc)
    out.extend(redefinition_findings(definitions, code, spans))
    counts = {}
    for definition, owner in definitions:
        if owner is None:
            counts[_text(definition.name)] = counts.get(_text(definition.name), 0) + 1
    # (a class defined twice: its earlier definition is "unused" as rules see the later one; listed as
    # defined twice instead, never removed as unused too)
    redefined = set("@" + n for n, c in counts.items() if c > 1)
    for definition, owner in definitions:
        name = _text(definition.name)
        line, _ = location_of(definition)
        key, at = locate(spans, line) if line else ("prefix", None)
        if key == "classes":
            continue  # (FontLab's own classes: kept in its Classes panel, used or not)
        glyphs = class_glyphs(definition)
        if not glyphs:
            out.append(Finding("empty-class", "@%s has no glyph" % name, key, at, subject="@" + name))
        seen_once, twice = set(), set()  # (one pass: a 20,000-glyph class was counted glyph by glyph; review 9)
        for g in glyphs:
            (twice if g in seen_once else seen_once).add(g)
        doubled = sorted(twice)
        if doubled and id(definition) in paired:
            doubled = []  # (its repeats pair with the other class's glyphs: needed)
        if id(definition) not in used and ("@" + name in aside or "@" + name in redefined):
            used[id(definition)] = 1  # (named by a part set aside, or another definition of it is used)
        if doubled:
            # (an unused class is removed whole instead: two fixes of one statement would collide)
            fix = class_dedupe_fix(code, spans, definition) if id(definition) in used else None
            out.append(Finding("class-duplicates", "@%s lists %s twice" % (name, ", ".join(doubled[:8]) +
                                                                         (", ..." if len(doubled) > 8 else "")),
                               key, at, subject="@" + name, fix=fix))
        if id(definition) not in used:
            fix = removal(code, spans, definition, "Remove @%s's definition" % name)
            out.append(Finding("unused-class", "@%s is never used" % name, key, at, subject="@" + name, fix=fix))
    return out


def class_dedupe_fix(code, spans, definition):
    """A Fix rewriting a class definition's own glyph list without its repeats (only a plain list of
    glyph names, ranges and classes inside left alone), or None."""
    found = node_span(code, spans, definition)
    if found is None:
        return None
    key, start, end = found
    text = code.part(key)
    statement = text[start:end]
    match = re.match(r"^(@[\w.\-]+\s*=\s*\[)([^\[\]@]*)(\]\s*;)$", statement, re.S)
    if not match or "-" in match.group(2):
        return None  # (a hyphen may make a range: left alone)
    kept, seen = [], set()
    for word in match.group(2).split():
        if word not in seen:
            seen.add(word)
            kept.append(word)
    new = match.group(1) + " ".join(kept) + match.group(3)
    return Fix("List each glyph once", [Edit(key, start, end, new)])


def lookup_findings(doc, code, spans, aside=frozenset()):
    out = []
    used = lookup_references(doc)
    for st in statements_of(doc):
        if kind_of(st) != "LookupBlock":
            continue
        name = _text(st.name)
        line, _ = location_of(st)
        key, at = locate(spans, line) if line else ("prefix", None)
        if id(st) not in used and name not in aside:
            fix = removal(code, spans, st, "Remove lookup %s" % name)
            out.append(Finding("unused-lookup", "Lookup %s is never used" % name, key, at, subject=name, fix=fix))
        elif not has_rules(st):
            out.append(Finding("empty-lookup", "Lookup %s has no rule" % name, key, at, subject=name))
    for node in all_statements(doc):
        if kind_of(node) == "FeatureBlock":
            for st in statements_of(node):
                if kind_of(st) == "LookupBlock" and not has_rules(st):
                    line, _ = location_of(st)
                    key, at = locate(spans, line) if line else ("prefix", None)
                    out.append(Finding("empty-lookup", "Lookup %s has no rule" % _text(st.name), key, at,
                                       subject=_text(st.name)))
    return out


def feature_findings(doc, code, spans):
    out = []
    tags = []
    for st in statements_of(doc):
        if kind_of(st) != "FeatureBlock":
            continue
        tag = _text(st.name)
        tags.append(tag)
        line, _ = location_of(st)
        key, at = locate(spans, line) if line else ("prefix", None)
        if not has_rules(st):
            text = code.part(key) or ""
            fix = None
            if key == "feature:%s" % tag and not automatic_spans(text):
                fix = Fix("Remove feature %s from the font" % tag, [], remove_feature=tag)
            out.append(Finding("empty-feature", "Feature %s has no rule" % tag, key, at, subject=tag, fix=fix))
    if "aalt" in tags and tags[0] != "aalt":
        out.append(Finding("aalt-order", "aalt comes after %s" % ", ".join(tags[:tags.index("aalt")][:4]),
                           "feature:aalt", None, subject="aalt"))
    return out


def rule_key(statement):
    try:
        return re.sub(r"\s+", " ", _text(statement.asFea())).strip()
    except Exception:
        return None


def rule_findings(doc, code, spans):
    """Rules written twice in one lookup (or one feature's run of rules), and substitutions by the glyph
    itself."""
    out = []

    def visit(block, label):
        seen, current = {}, None
        for st in statements_of(block):
            name = kind_of(st)
            if name in ("LookupBlock", "NestedBlock"):
                visit(st, label)
                seen, current = {}, None  # (the rules after it make a lookup of their own)
                continue
            if name in ("LookupFlagStatement", "ScriptStatement", "LanguageStatement", "SubtableStatement",
                        "LookupReferenceStatement"):
                seen, current = {}, None  # (a new lookup begins)
                continue
            if name not in RULE_KINDS or name == "FeatureReferenceStatement":
                continue
            # A rule of another kind begins a new lookup: "sub a by b; sub c d by e; sub a by b;" is three
            # lookups in fontTools 3.43 (FontLab's), and the second "sub a by b" applies to the e the
            # ligature makes, so it is no duplicate (review 9: it was removed as one, and proven "safe"
            # against code that had it blanked already)
            kind = lookup_kind(st)
            if kind != current:
                seen, current = {}, kind
            text = rule_key(st)
            line, _ = location_of(st)
            key, at = locate(spans, line) if line else ("prefix", None)
            if text and text in seen:
                fix = removal(code, spans, st, "Remove the second one")
                dup = Finding("duplicate-rule", "%s (again)" % text, key, at, subject=text, fix=fix)
                # Built without it (blanked, its lines kept): fontTools 3.43 refuses a single
                # substitution written twice, which set the whole feature aside (live), where Adobe's
                # compiler keeps the first
                found = node_span(code, spans, st)
                if found is not None:
                    part, start, end = found
                    dup.neutral = Edit(part, start, end, re.sub(r"[^\n]", " ", code.part(part)[start:end]))
                out.append(dup)
            elif text:
                seen[text] = st
            if name == "SingleSubstStatement" and not getattr(st, "prefix", None) and not getattr(st, "suffix", None):
                pairs = single_pairs(st)
                if pairs and all(a == b for a, b in pairs):
                    fix = removal(code, spans, st, "Remove it")
                    out.append(Finding("identity", text or "", key, at, subject=text, fix=fix))

    for st in statements_of(doc):
        if kind_of(st) in ("FeatureBlock", "LookupBlock"):
            visit(st, _text(st.name))
    return out


def lookup_kind(statement):
    """The kind of lookup a rule goes in: a contextual rule is a chaining lookup of its own kind."""
    name = kind_of(statement)
    contextual = bool(getattr(statement, "prefix", None) or getattr(statement, "suffix", None) or
                      getattr(statement, "forceChain", False))
    if name in ("SingleSubstStatement", "MultipleSubstStatement", "AlternateSubstStatement",
                "LigatureSubstStatement") and contextual:
        return "chain-sub"
    if name == "SinglePosStatement" and contextual:
        return "chain-pos"
    if name in ("ChainContextSubstStatement", "IgnoreSubstStatement"):
        return "chain-sub"
    if name in ("ChainContextPosStatement", "IgnorePosStatement"):
        return "chain-pos"
    return name


def single_pairs(statement):
    try:
        glyphs = [list(g.glyphSet()) for g in statement.glyphs]
        replace = [list(g.glyphSet()) for g in statement.replacements]
    except Exception:
        return None
    if len(glyphs) != 1 or len(replace) != 1:
        return None
    a, b = glyphs[0], replace[0]
    if len(b) == 1:
        b = b * len(a)
    if len(a) != len(b):
        return None
    return list(zip(a, b))


def language_findings(doc, code, spans):
    """Script and language statements the prefix does not declare, and a missing DFLT dflt."""
    out = []
    systems, first_system = [], None
    for st in statements_of(doc):
        if kind_of(st) == "LanguageSystemStatement":
            pair = (_text(st.script).strip(), _text(st.language).strip())
            systems.append(pair)
            if first_system is None:
                first_system = st
    if not systems:
        return out  # (none declared: compilers take DFLT dflt)
    declared = set(systems)
    scripts = set(s for s, _ in systems)
    if ("DFLT", "dflt") not in declared:
        line, _ = location_of(first_system)
        key, at = locate(spans, line) if line else ("prefix", None)
        out.append(Finding("no-default", "No languagesystem DFLT dflt; the prefix declares %s" % ", ".join(
            "%s %s" % pair for pair in systems[:4]) + (", ..." if len(systems) > 4 else ""), key, at,
            subject="DFLT dflt"))
    reported = set()
    for st in statements_of(doc):
        if kind_of(st) != "FeatureBlock":
            continue
        script = None
        for inner in statements_of(st):
            name = kind_of(inner)
            if name == "ScriptStatement":
                script = _text(inner.script).strip()
                if script not in scripts and (script, "dflt") not in reported:
                    reported.add((script, "dflt"))
                    line, _ = location_of(inner)
                    key, at = locate(spans, line) if line else ("prefix", None)
                    out.append(Finding("language", "script %s is in feature %s but no languagesystem declares it"
                                       % (script, _text(st.name)), key, at, subject="%s dflt" % script))
            elif name == "LanguageStatement":
                language = _text(inner.language).strip()
                pair = (script or "DFLT", language)
                if language != "dflt" and pair not in declared and pair not in reported:
                    reported.add(pair)
                    line, _ = location_of(inner)
                    key, at = locate(spans, line) if line else ("prefix", None)
                    out.append(Finding("language", "language %s (script %s) is in feature %s but no languagesystem "
                                       "declares it" % (language, pair[0], _text(st.name)), key, at,
                                       subject="%s %s" % pair))
    return out


CONFLICT = re.compile(r"Already defined (?:substitution|alternates|rule|different position) for (?:glyph |replacing glyph )?\"?([^\"\s]+)")


def build_findings(lib, code, order, doc):
    """(the stub font built, or None; the compiler's findings; the code that built, or None): each error
    found, its part taken out,
    and the rest built again (BUILD_RETRIES at most). order holds the glyphs the font lacks too, after
    its own, so that they do not hide what else is wrong; doc is code parsed, or None."""
    findings = []
    names = set(order)
    current, current_doc = code, doc
    for _ in range(BUILD_RETRIES):
        text, spans = current.text()
        try:
            font = build(lib, text, order, current_doc)
            try:
                for tag in LAYOUT_TABLES:
                    if tag in font:
                        font[tag].compile(font)
            except Exception as exc:
                overflow = "Overflow" in type(exc).__name__ or "overflow" in error_message(exc).lower()
                findings.append(Finding("overflow" if overflow else "build",
                                        "%s%s" % ("" if overflow else "The tables did not compile: ", error_message(exc)),
                                        "prefix", None, subject="overflow" if overflow else None))
                return None, findings, None
            return (font if current is code else None), findings, current
        except Exception as exc:
            line, _ = error_line(exc)
            key, at = locate(spans, line) if line else ("prefix", None)
            message = error_message(exc)
            conflict = CONFLICT.search(message)
            if conflict:
                findings.append(Finding("conflict", message, key, at, subject=conflict.group(1)))
            elif isinstance(exc, KeyError):
                findings.append(Finding("build", "A glyph or table the compiler could not find: %s" % message, key, at))
            else:
                findings.append(Finding("build", message, key, at))
            if not key.startswith("feature:"):
                return None, findings, None
            current = current.with_part(key, None)
            try:
                current_doc = parse(lib, current.text()[0], names)
            except Exception:
                return None, findings, None
    return None, findings, None


def mark_automatic(findings, code):
    """Findings inside FontLab's automatic code keep no fix: FontLab rewrites that code on compiling."""
    spans_of = {}  # (each part scanned once: once a finding, 10,000 duplicates scanned their feature 10,000 times)
    for f in findings:
        text = code.part(f.key)
        if not text or not f.line:
            continue
        if f.key not in spans_of:
            spans_of[f.key] = automatic_spans(text)
        if not spans_of[f.key]:
            continue
        at = line_offset(text, f.line)
        for start, end in spans_of[f.key]:
            if start <= at < end:
                f.automatic = True
                f.fix = None
    return findings


# ---------------------------------------------------------------------------
# What the compiled layout does (to prove a fix changes nothing)
# ---------------------------------------------------------------------------


class TooLarge(Exception):
    pass


def value_key(value):
    if value is None:
        return None
    out = []
    for name in ("XPlacement", "YPlacement", "XAdvance", "YAdvance", "XPlaDevice", "YPlaDevice", "XAdvDevice",
                 "YAdvDevice"):
        item = getattr(value, name, None)
        if item is not None and item != 0:
            out.append((name, deep_key(item)))
    return tuple(out)


def deep_key(obj, depth=0):
    """A comparable key of an otTables object (its fields, recursively)."""
    if depth > 40:
        raise TooLarge("too deep")
    if obj is None or isinstance(obj, (int, float, bool)) or isinstance(obj, (type(""), type(b""))):
        return obj
    if isinstance(obj, (list, tuple)):
        return tuple(deep_key(x, depth + 1) for x in obj)
    if isinstance(obj, dict):
        return tuple(sorted((deep_key(k, depth + 1), deep_key(v, depth + 1)) for k, v in obj.items()))
    if hasattr(obj, "__dict__"):
        return (type(obj).__name__,) + tuple(sorted((k, deep_key(v, depth + 1)) for k, v in obj.__dict__.items()
                                                    if not k.startswith("_") and k not in ("Format",)))
    return repr(obj)


def coverage(cov):
    return list(getattr(cov, "glyphs", None) or [])


def class_sets(classdef, glyphs, order):
    """{class: frozenset of glyphs} of a ClassDef, class 0 being every glyph of glyphs (or of the font)
    in no class."""
    classes = dict(getattr(classdef, "classDefs", None) or {}) if classdef is not None else {}
    out = {}
    for g, c in classes.items():
        out.setdefault(c, set()).add(g)
    pool = glyphs if glyphs is not None else order
    out[0] = set(g for g in pool if classes.get(g, 0) == 0)
    return dict((c, frozenset(s)) for c, s in out.items())


class Layout(object):
    """What a compiled GSUB or GPOS does, as comparable keys (summary)."""

    def __init__(self, font, tag):
        self.font, self.tag = font, tag
        self.table = font[tag].table if tag in font else None
        self.order = font.getGlyphOrder()
        self.memo = {}
        self.pairs = 0

    def lookup_key(self, index, depth=0):
        if index in self.memo:
            return self.memo[index]
        if depth > 16:
            raise TooLarge("lookups nested too deep")
        lookup = self.table.LookupList.Lookup[index]
        kind = lookup.LookupType
        subtables = list(lookup.SubTable)
        ext = 7 if self.tag == "GSUB" else 9
        if kind == ext:
            subtables = [st.ExtSubTable for st in subtables]
            kind = subtables[0].LookupType if subtables else kind
        flag = (lookup.LookupFlag, getattr(lookup, "MarkFilteringSet", None))
        key = (self.tag, kind, flag, self.subtables_key(kind, subtables, depth))
        self.memo[index] = key
        return key

    def subtables_key(self, kind, subtables, depth):
        sub = self.tag == "GSUB"
        if sub and kind in (1, 2, 3):
            merged = {}
            for st in subtables:
                table = st.mapping if kind == 1 else (st.mapping if kind == 2 else st.alternates)
                for g, out in table.items():
                    if g not in merged:
                        merged[g] = tuple(out) if isinstance(out, (list, tuple)) else out
            if kind == 1:
                merged = dict((g, o) for g, o in merged.items() if g != o)
            return tuple(sorted(merged.items()))
        if sub and kind == 4:
            merged = {}
            for st in subtables:
                for first, ligatures in st.ligatures.items():
                    for lig in ligatures:
                        merged.setdefault(first, []).append((tuple(lig.Component), lig.LigGlyph))
            return tuple(sorted((first, tuple(v)) for first, v in merged.items()))
        if (sub and kind in (5, 6)) or (not sub and kind in (7, 8)):
            rules = []
            for st in subtables:
                rules.extend(self.context_rules(st, depth))
            return tuple(rules)
        if sub and kind == 8:
            return tuple((tuple(frozenset(coverage(c)) for c in st.BacktrackCoverage), tuple(coverage(st.Coverage)),
                          tuple(frozenset(coverage(c)) for c in st.LookAheadCoverage), tuple(st.Substitute))
                         for st in subtables)
        if not sub and kind == 1:
            merged = {}
            for st in subtables:
                glyphs = coverage(st.Coverage)
                if st.Format == 1:
                    values = [st.Value] * len(glyphs)
                else:
                    values = list(st.Value)
                for g, v in zip(glyphs, values):
                    if g not in merged:
                        merged[g] = value_key(v)
            return tuple(sorted(merged.items()))
        if not sub and kind == 2:
            return self.pairs_key(subtables)
        return tuple(deep_key(st) for st in subtables)

    def pairs_key(self, subtables):
        """{(left, right): values} the pair lookup applies, the first subtable covering a pair winning
        (a class subtable covers its left glyphs against every right glyph)."""
        values, blocked = {}, set()
        for st in subtables:
            lefts = coverage(st.Coverage)
            if st.Format == 1:
                for left, pairset in zip(lefts, st.PairSet):
                    if left in blocked:
                        continue
                    for record in pairset.PairValueRecord:
                        pair = (left, record.SecondGlyph)
                        if pair not in values:
                            values[pair] = (value_key(getattr(record, "Value1", None)),
                                            value_key(getattr(record, "Value2", None)))
                            self.count_pair()
            else:
                left_classes = class_sets(st.ClassDef1, lefts, self.order)
                right_classes = class_sets(st.ClassDef2, None, self.order)
                for c1, record in enumerate(st.Class1Record):
                    lefts_here = [g for g in left_classes.get(c1, ()) if g not in blocked]
                    if not lefts_here:
                        continue
                    for c2, record2 in enumerate(record.Class2Record):
                        value = (value_key(getattr(record2, "Value1", None)), value_key(getattr(record2, "Value2", None)))
                        if not any(value):
                            continue
                        for left in lefts_here:
                            for right in right_classes.get(c2, ()):
                                pair = (left, right)
                                if pair not in values:
                                    values[pair] = value
                                    self.count_pair()
                blocked.update(lefts)
        return tuple(sorted((pair, v) for pair, v in values.items() if any(v)))

    def count_pair(self):
        self.pairs += 1
        if self.pairs > PAIRS_PROVEN_MAX:
            raise TooLarge("too many kerning pairs to compare")

    def context_rules(self, st, depth):
        sub = self.tag == "GSUB"
        records_name = "SubstLookupRecord" if sub else "PosLookupRecord"
        chain = hasattr(st, "BacktrackCoverage") or hasattr(st, "ChainSubRuleSet") or hasattr(st, "ChainPosRuleSet") \
            or hasattr(st, "BacktrackClassDef") or type(st).__name__.startswith("Chain")
        fmt = st.Format
        rules = []

        def nested(records):
            return tuple((r.SequenceIndex, self.lookup_key(r.LookupListIndex, depth + 1)) for r in records or [])

        if fmt == 3:
            if chain:
                back = tuple(frozenset(coverage(c)) for c in st.BacktrackCoverage)
                inp = tuple(frozenset(coverage(c)) for c in st.InputCoverage)
                ahead = tuple(frozenset(coverage(c)) for c in st.LookAheadCoverage)
            else:
                back, ahead = (), ()
                inp = tuple(frozenset(coverage(c)) for c in st.Coverage)
            rules.append((back, inp, ahead, nested(getattr(st, records_name, None))))
        elif fmt == 1:
            firsts = coverage(st.Coverage)
            sets_name = ("ChainSubRuleSet" if sub else "ChainPosRuleSet") if chain else ("SubRuleSet" if sub else "PosRuleSet")
            rule_name = ("ChainSubRule" if sub else "ChainPosRule") if chain else ("SubRule" if sub else "PosRule")
            for first, ruleset in zip(firsts, getattr(st, sets_name, None) or []):
                for rule in getattr(ruleset, rule_name, None) or []:
                    back = tuple(frozenset([g]) for g in getattr(rule, "Backtrack", []) or [])
                    inp = (frozenset([first]),) + tuple(frozenset([g]) for g in getattr(rule, "Input", []) or [])
                    ahead = tuple(frozenset([g]) for g in getattr(rule, "LookAhead", []) or [])
                    rules.append((back, inp, ahead, nested(getattr(rule, records_name, None))))
        elif fmt == 2:
            firsts = coverage(st.Coverage)
            if chain:
                back_cls = class_sets(st.BacktrackClassDef, None, self.order)
                inp_cls = class_sets(st.InputClassDef, None, self.order)
                ahead_cls = class_sets(st.LookAheadClassDef, None, self.order)
            else:
                back_cls = ahead_cls = {}
                inp_cls = class_sets(st.ClassDef, None, self.order)
            sets_name = ("ChainSubClassSet" if sub else "ChainPosClassSet") if chain else ("SubClassSet" if sub else "PosClassSet")
            rule_name = ("ChainSubClassRule" if sub else "ChainPosClassRule") if chain else ("SubClassRule" if sub else "PosClassRule")
            for c, classset in enumerate(getattr(st, sets_name, None) or []):
                if classset is None:
                    continue
                first_glyphs = frozenset(g for g in inp_cls.get(c, ()) if g in set(firsts))
                if not first_glyphs:
                    continue
                for rule in getattr(classset, rule_name, None) or []:
                    back = tuple(back_cls.get(k, frozenset()) for k in getattr(rule, "Backtrack", []) or [])
                    inp = (first_glyphs,) + tuple(inp_cls.get(k, frozenset()) for k in
                                                  (getattr(rule, "Input", None) or getattr(rule, "Class", None) or []))
                    ahead = tuple(ahead_cls.get(k, frozenset()) for k in getattr(rule, "LookAhead", []) or [])
                    rules.append((back, inp, ahead, nested(getattr(rule, records_name, None))))
        else:
            rules.append(deep_key(st))
        return rules

    def summary(self):
        """{(script, language): ((lookup key, features), ...) in lookup order}, and the features' params."""
        if self.table is None:
            return {}
        out = {}
        features = self.table.FeatureList.FeatureRecord if self.table.FeatureList else []
        params = []
        for record in features:
            fp = getattr(record.Feature, "FeatureParams", None)
            if fp is not None:
                params.append((record.FeatureTag, deep_key(fp)))
        for script in self.table.ScriptList.ScriptRecord if self.table.ScriptList else []:
            systems = [("dflt", script.Script.DefaultLangSys)] if script.Script.DefaultLangSys else []
            systems += [(ls.LangSysTag, ls.LangSys) for ls in script.Script.LangSysRecord]
            for lang, langsys in systems:
                indices = list(langsys.FeatureIndex)
                required = getattr(langsys, "ReqFeatureIndex", 0xFFFF)
                by_lookup = {}
                # (a required feature is told apart: it applies whatever the user turns off; review 9)
                for fi, mark in [(fi, "") for fi in indices] + ([(required, " (required)")] if required != 0xFFFF else []):
                    record = features[fi]
                    for li in record.Feature.LookupListIndex:
                        by_lookup.setdefault(li, set()).add(record.FeatureTag + mark)
                out[(script.ScriptTag, lang)] = tuple(
                    (self.lookup_key(li), tuple(sorted(tags))) for li, tags in sorted(by_lookup.items()))
        return {"systems": out, "params": tuple(sorted(params))}


def layout_summary(font):
    """What the compiled layout does: GSUB, GPOS, GDEF's classes, and the feature names, as one
    comparable value. Raises TooLarge where a proof would take too long."""
    out = {}
    for tag in LAYOUT_TABLES:
        out[tag] = Layout(font, tag).summary() if tag in font else None
    gdef = font["GDEF"].table if "GDEF" in font else None
    out["GDEF"] = deep_key(gdef) if gdef is not None else None
    names = []
    if "name" in font:
        for record in font["name"].names:
            try:
                names.append((record.nameID, record.platformID, record.langID, record.toUnicode()))
            except Exception:
                pass
    out["names"] = tuple(sorted(names))
    return out


class Compiled(object):
    """A FontCode built once, with its tables' bytes and its layout summary made when first asked."""

    def __init__(self, lib, code, order):
        self.font = build(lib, code.text()[0], order)
        self._bytes, self._summary = None, None

    def table_bytes(self):
        if self._bytes is None:
            self._bytes = dict((tag, self.font[tag].compile(self.font) if tag in self.font else None)
                               for tag in ("GSUB", "GPOS", "GDEF"))
        return self._bytes

    def names(self):
        out = []
        if "name" in self.font:
            for record in self.font["name"].names:
                try:
                    out.append((record.nameID, record.platformID, record.langID, record.toUnicode()))
                except Exception:
                    pass
        return sorted(out)

    def summary(self):
        if self._summary is None:
            self._summary = layout_summary(self.font)
        return self._summary


def compiled(lib, code, order, cache=None):
    """A Compiled of code (from cache, {code text: Compiled}, when given), or None where it does not build."""
    key = code.text()[0]
    if cache is not None and key in cache:
        return cache[key]
    try:
        made = Compiled(lib, code, order)
    except Exception:
        made = None
    if cache is not None:
        cache[key] = made
    return made


def same_layout(lib, before, after, order, cache=None):
    """True when two FontCodes compile to the same layout; False when not; None when it cannot be told
    (one does not compile, or the comparison is too large). The same bytes settle it at once; else
    the layouts are compared by what they do (layout_summary). cache: {code text: Compiled}, so that the
    code every fix is compared with is built once."""
    a = compiled(lib, before, order, cache)
    b = compiled(lib, after, order, cache)
    if a is None or b is None:
        return None
    try:
        if a.table_bytes() == b.table_bytes() and a.names() == b.names():
            return True
    except Exception:
        pass
    try:
        return a.summary() == b.summary()
    except TooLarge:
        return None
    except Exception:
        return None


def set_aside(report, base):
    """The parts of the code that base (the code built) lacks: set aside for an error."""
    return [key for key in report.code.keys() if report.code.part(key) is not None and base.part(key) is None]


# Kinds whose fixes only take out a definition nothing uses (or a second, identical one): taking out any of
# them leaves the others as they were, so a group of them proven together is proven for each. Other fixes
# can depend on each other (two classes' repeats that pair: each removal alone breaks the code, both
# together do not; review 11), and are proven one by one
BATCH_KINDS = ("unused-class", "unused-lookup", "class-repeated")


def disjoint_groups(fixes):
    """fixes split into groups whose edits never overlap (apply_edits keeps the first of two that do: a
    fix left out of its group's code would be proven by nothing). Sorted by where they begin, each goes
    into the first group whose edits so far end before it, per part: no fix is compared with every other."""
    groups = []  # [[fixes], {part key: where its last edit ends}]
    for fix in sorted(fixes, key=lambda f: min([(e.key, e.start) for e in f.edits] or [("", 0)])):
        for group in groups:
            if all(group[1].get(e.key, -1) <= e.start for e in fix.edits):
                break
        else:
            group = [[], {}]
            groups.append(group)
        group[0].append(fix)
        for e in fix.edits:
            group[1][e.key] = max(group[1].get(e.key, -1), e.end)
    return [g[0] for g in groups]


def prove_fixes(report, glyph_order, progress=None):
    """Sets each fix's safe: True where the code with it compiles to the same layout as without it. A fix
    that would make the code fail to compile is withdrawn. Nothing is proven while part of the code is set
    aside for an error: the code built then lacks what a fix may change for it (a CJK font's aalt was set
    aside, and the repeats its "sub @aalt by @aalt2;" needs were taken out as "safe", live, 2026-11-17;
    classes defined inside features and compact definitions defeated a finer guard, review 11). Fixes of
    BATCH_KINDS are proven together, a group that is not the same split in halves (a CJK font's 688 took
    one build each, 15 minutes in FontLab); every other fix alone."""
    lib = fealib()
    fixes = [f.fix for f in report.findings if f.fix is not None]
    if lib is None or not fixes:
        return fixes
    if getattr(report, "proven", False):
        return fixes
    order = list(report.order or glyph_order)
    base = report.provable
    built = getattr(report, "buildable", None) or report.code
    owners = dict((id(f.fix), f) for f in report.findings if f.fix is not None)
    for fix in fixes:
        fix.safe = None
    report.proven = True
    if base is None or set_aside(report, base):
        return fixes
    cache = base_cache(report, base)
    if compiled(lib, base, order, cache) is None:
        return fixes
    base_key = base.text()[0]
    batched, single = {}, []
    for finding in report.findings:
        fix = finding.fix
        if fix is None or fix.review or not fix_applies(base, built, fix):
            continue
        if finding.kind in BATCH_KINDS:
            batched.setdefault(finding.kind, []).append(fix)
        else:
            single.append([fix])
    pending = []
    for kind in sorted(batched):
        pending.extend(disjoint_groups(batched[kind]))
    pending.extend(single)
    total, done = sum(len(g) for g in pending), 0

    def withdraw(fix):
        finding = owners.get(id(fix))
        if finding is not None:
            # A fix that would not compile is no fix (a class's repeats that pair its glyphs with
            # another class's, in order): the finding stays, without one
            finding.fix = None
            finding.message += " (no fix: taking it out would break the code)"

    while pending:
        group = pending.pop(0)
        step(progress, "Proving the fixes", done, total)
        fixed = apply_fixes(base, group)
        builds = compiled(lib, fixed, order, cache) is not None
        result = same_layout(lib, base, fixed, order, cache) if builds else None
        if fixed.text()[0] != base_key:
            cache.pop(fixed.text()[0], None)  # (each variant built once and dropped: the base alone is kept)
        if not builds and len(group) == 1:
            withdraw(group[0])
            done += 1
            continue
        if builds and (result is None or result or len(group) == 1):
            for fix in group:
                fix.safe = result  # (None: too large to compare, and halves would be too)
            done += len(group)
            continue
        half = len(group) // 2
        pending[:0] = [group[:half], group[half:]]
    return [f.fix for f in report.findings if f.fix is not None]


def base_cache(report, base):
    """A cache holding the compiled base alone (each fixed variant is built once and dropped)."""
    held = getattr(report, "base_cache", None)
    if held is None:
        held = report.base_cache = {}
    key = base.text()[0]
    for other in [k for k in held if k != key]:
        del held[other]
    return held


def fix_applies(base, code, fix):
    """Whether every part a fix touches is in base as it is in code (the code built: a part set aside
    for an error has nothing to compare with)."""
    keys = set(edit.key for edit in fix.edits)
    if fix.remove_feature:
        keys.add("feature:%s" % fix.remove_feature)
    return all(base.part(key) is not None and base.part(key) == code.part(key) for key in keys)


def safe_fixes(report, glyph_order, progress=None):
    """The fixes the automatic option applies: of AUTO_KINDS, each proven, then all together proven
    again (dropped one by one from the end until the whole set is)."""
    prove_fixes(report, glyph_order, progress)
    step(progress, "Proving the fixes together")
    chosen = [f.fix for f in report.findings if f.fix is not None and f.fix.safe and f.kind in AUTO_KINDS
              and not f.automatic and not f.fix.review]
    lib = fealib()
    base = report.provable
    while chosen and base is not None:
        if same_layout(lib, base, apply_fixes(base, chosen), list(report.order or glyph_order), base_cache(report, base)):
            return chosen
        chosen = chosen[:-1]
    return []


# ---------------------------------------------------------------------------
# A writer's check of its own code
# ---------------------------------------------------------------------------


_REPORTS = {}  # {(code, glyphs) key: Report}, the last few, so a writer's "before" is not checked twice


def cached_check(code, glyph_order):
    key = (code.text()[0], len(glyph_order), hash(tuple(glyph_order)))
    if key in _REPORTS:
        return _REPORTS[key]
    report = check(code, glyph_order)
    if len(_REPORTS) > 6:
        _REPORTS.clear()
    _REPORTS[key] = report
    return report


def check_change(before, after, glyph_order):
    """(new errors, new warnings) the code after brings that the code before did not have: findings
    compared by what they are, not where (a rule moved is not new). [], [] when fontTools is missing."""
    if fealib() is None:
        return [], []
    old = cached_check(before, glyph_order)
    new = cached_check(after, glyph_order)
    had = set(f.identity() for f in old.findings)
    added = [f for f in new.findings if f.identity() not in had]
    return ([f for f in added if f.severity == ERROR], [f for f in added if f.severity == WARNING])


def font_code(package):
    """A FontCode of a FontLab font (flPackage): its prefix, its features in order, and its feature
    classes (FontLab's Classes panel, kernGroup False)."""
    features = package.fgPackage.features
    try:
        prefix = features.get_prefix() or ""
    except Exception:
        prefix = ""
    parts = [(tag, features.get_feature(tag) or "") for tag in features.keys()]
    classes = []
    try:
        for group in package.getAllGroups():
            kern_group, name, glyphs = group[0], group[1], group[4] if len(group) > 4 else []
            if not kern_group:
                classes.append((name, list(glyphs)))
    except Exception:
        pass
    return FontCode(prefix, parts, classes)


def change_refusal(package, new_texts, new_prefix=None, glyph_order=None):
    """For a writer: the text saying why its code is not written (the new errors it would bring), or None
    (nothing new is wrong, or fontTools is missing). new_texts: {tag: whole feature text} to set;
    new_prefix: the prefix to set, or None for the font's own."""
    try:
        before = font_code(package)
        order = glyph_order if glyph_order is not None else [g.name for g in package.fgPackage.glyphs]
        after = before.copy()
        if new_prefix is not None:
            after.prefix = _text(new_prefix)
        tags = [t for t, _ in after.features]
        after.features = [(t, _text(new_texts[t]) if t in new_texts else text) for t, text in after.features]
        after.features += [(_text(t), _text(text)) for t, text in sorted(new_texts.items()) if t not in tags]
        errors, _ = check_change(before, after, order)
    except Exception:
        return None
    if not errors:
        return None
    shown = "; ".join("%s: %s" % (f.where(), f.message) for f in errors[:3])
    more = " (and %s)" % counted(len(errors) - 3, "more") if len(errors) > 3 else ""
    return "the code would bring %s the font did not have: %s%s" % (
        "an error" if len(errors) == 1 else "%d errors" % len(errors), shown, more)


# ---------------------------------------------------------------------------
# The window (FontLab, Qt)
# ---------------------------------------------------------------------------

FEATURE_CODE_FILE, FEATURE_CODE_MODULE = "freelab_feature_code.py", "freelab_feature_code"
COLUMNS = ("Finding", "Where", "Fix")
SAFE_NOTE = "changes nothing in the compiled font"
UNSAFE_NOTE = "changes the compiled font: review it"
UNPROVEN_NOTE = "not proven: part of the code does not compile; mend the errors first"
REVIEW_NOTE = "changes what the font does: review it"
REPAIR_NOTE = "mends code that does not compile: review it"
# Where each step of a check starts on the bar (the window's top row), and its share of it
STEPS = {"Reading the code": (0.0, 0.3), "Looking through the code": (0.3, 0.05), "Compiling": (0.35, 0.15),
         "Proving the fixes": (0.5, 0.45), "Proving the fixes together": (0.95, 0.05)}
TITLE = "FreeLab Feature Check"
APPLY_TEXT = "Apply ticked fixes"  # (with a count once some are ticked: "Apply 3 ticked fixes")
COMPILE_STEP = "Compiling in FontLab"  # the top row's step while FontLab compiles (owner's image 212)
READ_STEP = "Reading what FontLab's compiler said"
COMPILE_WAIT_MS = 4000  # the bar ends by then whatever happens (ak.compiled_note reads the Output panel for ~3.2 s)

HELP = """<b>FreeLab Feature Check</b><br>
Checks the current font's feature code, whatever made it: what stops it from compiling (syntax errors,
glyphs the font lacks, rules the compiler refuses, tables too large), what probably does not do what was
meant (a language no <code>languagesystem</code> line declares, no default language system, empty
classes, a class defined twice with other glyphs, a glyph given two ways in one lookup), and what does
nothing (rules written twice, a glyph substituted by itself, classes defined twice the same, classes and
lookups never used, empty lookups and features). A fix that changes what the font does (a lookup flag
FontLab wrote without its class, taken out) is offered for review, never applied automatically.<br><br>
Findings are grouped by kind, errors first; select one to see its code under the list, its line
selected. A finding with a fix has a check box: tick the fixes you want, then <i>Apply ticked
fixes</i> (one step of FontLab's History: <i>Edit &gt; Undo</i> takes it back). Each fix is tried first,
and its last column says whether the font's layout, compiled with it, stays the same.<br><br>
<i>Apply safe fixes automatically</i>: at each check, the fixes proven to change nothing in the compiled
font (rules written twice, substitutions by the glyph itself, glyphs listed twice in a class, classes and
lookups never used) are applied at once, and the list shows what is left to review.<br><br>
The checks use fontTools' compiler, which FontLab ships; FontLab compiles with Adobe's, which differs
in places: <i>Compile in FontLab</i> compiles there (the window's top row shows it meanwhile) and adds
what it reports to the log.
FontLab's automatic code (between its <code>#&gt; feature</code> and <code>#&lt;</code> lines) is checked
but never fixed: FontLab writes it again on compiling."""


def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


def load_auto_kerning():
    """Auto Kerning beside this script, as a module (its dialog not opened): the shared window helpers."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "FontKerning") and getattr(held, "_freelab_stamp", None) == stamp:
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


def settings_path(ak):
    return os.path.join(ak.state_dir(), SETTINGS_FILE)


def read_settings(ak):
    import json
    try:
        with io.open(settings_path(ak), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def write_settings(ak, data):
    import json
    try:
        folder = os.path.dirname(settings_path(ak))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(settings_path(ak), "w", encoding="utf-8") as handle:
            handle.write("%s" % json.dumps(data, indent=1, sort_keys=True))
    except (IOError, OSError):
        pass


def fix_note(fix):
    """The Fix column's text: what it does, and whether it was proven."""
    if fix is None:
        return ""
    if getattr(fix, "repair", False):
        return "%s (%s)" % (fix.what, REPAIR_NOTE)
    if getattr(fix, "review", False):
        return "%s (%s)" % (fix.what, REVIEW_NOTE)
    if fix.safe is True:
        return "%s (%s)" % (fix.what, SAFE_NOTE)
    if fix.safe is False:
        return "%s (%s)" % (fix.what, UNSAFE_NOTE)
    return "%s (%s)" % (fix.what, UNPROVEN_NOTE)


def group_title(kind, count):
    severity, title, one, many, _ = KINDS[kind]
    word = {ERROR: "error", WARNING: "warning", ADVICE: "advice"}[severity]
    return "%s (%s, %s)" % (title, counted(count, one, many), word)


def _escaped(text):
    return _text(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def summary_line(report, rich=False):
    """The status line under the font line (owner's images 231 and 237). rich: as rich text, the counts
    and their nouns in bold (the rest escaped)."""
    escape = _escaped if rich else _text
    strong = (lambda text: "<b>%s</b>" % _escaped(text)) if rich else _text
    if report.unavailable:
        return "Nothing was checked: %s." % escape(report.unavailable)
    if not report.findings:
        return "No finding: the code compiles, and nothing in it is unused or written twice."
    groups = report.by_kind()
    totals = dict((severity, sum(len(v) for k, v in groups.items() if KINDS[k][0] == severity))
                  for severity in (ERROR, WARNING, ADVICE))
    parts = []
    for severity, one, many in ((ERROR, "error", "errors"), (WARNING, "warning", "warnings"),
                                (ADVICE, "piece of advice", "pieces of advice")):
        if totals[severity]:
            parts.append(strong(counted(totals[severity], one, many)))
    # (one sentence, so one line: the top line puts each sentence on a line of its own, and "1 error." over
    # "It does not compile." took two, owner's image 343)
    state = "It compiles" if report.built else ("It does not compile" if totals[ERROR] else "")
    return "%s: %s." % (state, ", ".join(parts)) if state else "%s." % ", ".join(parts)


def font_line(ak, name, glyphs):
    """The window's top line: the font's name in bold (its subject is the whole font: no master), and its
    glyphs counted, thousands grouped: "<b>BIZ UDGothic</b> (<b>13,932 glyphs</b>)." (owner's image 231)."""
    named = ak.font_named(name) if hasattr(ak, "font_named") else ak.b(name)
    return "%s (%s)." % (named, ak.b(counted(glyphs, "glyph")))


def written_parts(before, after):
    """(prefix or None, {tag: text} changed, [tags taken out]) from one FontCode to another."""
    prefix = after.prefix if after.prefix != before.prefix else None
    old = dict(before.features)
    new = dict(after.features)
    changed = dict((tag, text) for tag, text in after.features if old.get(tag) != text)
    removed = [tag for tag, _ in before.features if tag not in new]
    return prefix, changed, removed


class FeatureCheckDialog(object):
    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.ak = ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle(TITLE)
        dialog.setWhatsThis(HELP)
        ak.size_dialog(dialog)
        layout = ak.window_layout(dialog)  # (its content scrolls on a small screen)
        # The header, as in every window (owner's images 231 and 237): the font line (the busy bar in its place
        # while a check or a compile runs), the check's result under it, then the header's line
        self.font_label = ak.status_label()
        self.font_label.setWordWrap(True)
        layout.addWidget(self.font_label)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(ak.header_separator())

        row = QtGui.QHBoxLayout()
        self.auto_box = QtGui.QCheckBox("Apply safe fixes automatically.")
        self.auto_box.setWhatsThis("At each check, applies the fixes proven to change nothing in the compiled font "
                                   "(rules written twice, substitutions by the glyph itself, glyphs listed twice in a "
                                   "class, classes and lookups never used), as one step of FontLab's History; the list "
                                   "then shows what is left to review. Off: every finding is listed for you to review.")
        self.settings = read_settings(ak)
        self.auto_box.setChecked(bool(self.settings.get("auto")))
        row.addWidget(self.auto_box)
        self.check_button = QtGui.QPushButton("Check")  # (the run button, at the end of the option it reads)
        self.check_button.setWhatsThis("Checks the font's feature code again as it is now.")
        row.addWidget(self.check_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(COLUMNS))
        self.tree.setHeaderLabels(list(COLUMNS))
        self.tree.setWhatsThis("The findings, errors first, grouped by kind (a group's tooltip says what the kind "
                               "means). A row with a check box has a fix; its last column says what it does and "
                               "whether the compiled font stays the same with it.")
        self.splitter.addWidget(self.tree)
        self.code = QtGui.QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setLineWrapMode(QtGui.QPlainTextEdit.NoWrap)  # (code lines as written)
        self.code.setWhatsThis("The selected finding's code (its feature, the prefix, or FontLab's classes), its line "
                               "selected.")
        self.splitter.addWidget(self.code)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        layout.addWidget(self.splitter, 1)
        self.highlighting = None
        try:  # (Feature Code's colors; without them the code shows plain)
            self.highlighting = ak.load_sibling(FEATURE_CODE_FILE, FEATURE_CODE_MODULE).make_highlighter(self.code)
        except Exception:
            self.highlighting = None
        self.log = ak.Log()
        layout.addWidget(self.log.widget)

        # The bottom row, as in every window (owner's image 255): the list's tick buttons at the left; at the
        # right the compile, then the committing action, then Close
        buttons = QtGui.QHBoxLayout()
        self.check_all = QtGui.QPushButton("Tick all")
        self.check_all.setWhatsThis("Ticks every fix in the list.")
        self.check_none = QtGui.QPushButton("Tick none")
        self.check_none.setWhatsThis("Unticks every fix in the list.")
        self.compile_button = QtGui.QPushButton("Compile in FontLab")
        self.compile_button.setWhatsThis("Compiles the font's features with FontLab's own compiler (Adobe's), as the "
                                         "<i>Features</i> panel's <i>Compile</i> button does, and adds what it reports "
                                         "to the log; the window's top row shows it meanwhile. Grayed while the font has "
                                         "no feature code.")
        self.apply_button = QtGui.QPushButton(APPLY_TEXT)
        self.apply_button.setWhatsThis("Applies the ticked fixes to the font's feature code, as one step of FontLab's "
                                       "History, then checks the code again.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.check_all, self.check_none):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.compile_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.package = None
        self.report = None
        self.items = []
        self.order = []
        self.busy = False
        self.code_there = False  # whether the font has feature code (has_code): Compile in FontLab grays without
        self.compiling = None  # the compile under way (compile_in_fontlab), until FontLab's report is read
        self.seen_history = None
        self.check_button.connect("clicked()", lambda: self.run())
        self.auto_box.connect("toggled(bool)", self.auto_toggled)
        self.compile_button.connect("clicked()", self.compile_in_fontlab)
        self.apply_button.connect("clicked()", self.apply_checked)
        self.check_all.connect("clicked()", lambda: self.check_every(True))
        self.check_none.connect("clicked()", lambda: self.check_every(False))
        self.tree.connect("itemSelectionChanged()", self.show_code)
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons())
        self.close_button.connect("clicked()", ak.close_slot(self))  # (never the window itself: see let_go)
        ak.table_layout(self.tree)
        ak.add_tools_button(dialog, "Feature Check", self.log)  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.read_font()
        self.history_timer = ak.watch_history(self)
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
        self.package = self.current_font()
        if self.package is None:
            self.code_there = False
            self.font_label.setText(self.ak.no_font_line())
            return False
        self.order = [g.name for g in self.package.fgPackage.glyphs]
        self.font_label.setText(font_line(self.ak, self.package.tfn, len(self.order)))
        try:
            self.code_there = has_code(font_code(self.package))
        except Exception:
            self.code_there = True  # (unreadable here: FontLab's compiler may still say what is wrong)
        return True

    def font_changed(self):
        """This window's font was closed, or a font opened for a window without one (fonts_tick)."""
        self.tree.clear()
        self.report, self.items = None, []
        self.code.setPlainText("")
        self.status.setText("")
        if self.read_font():
            self.run()
        self.update_buttons()

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: checked again, nothing applied automatically (an undo
        of the automatic fixes was undone at once by them, live)."""
        self.log.add("The font's History moved (an undo, a redo, or an edit): checked again%s." % (
            "; nothing is applied automatically until you click <i>Check</i>" if self.auto_box.checked else ""))
        self.run(automatic=False)

    # -- checking --------------------------------------------------------------

    def set_busy(self, on, what="", stoppable=True):
        """The check (or a compile in FontLab) under way, or over: its steps in the window's top row
        (ak.busy_start), the buttons grayed; the tools menu, the arrows, and Close stop a check, then do
        what was clicked (a compile, which cannot be stopped halfway, is let finish first)."""
        self.busy = on
        if on:
            if stoppable:
                self.status.setText("")
            self.ak.busy_start(self, what, stoppable=stoppable)
        else:
            self.ak.busy_end(self)
        self.update_buttons()

    def progress(self, what, done=0, total=1):
        """The check at a step (STEPS), done of total within it: the bar in the top row moved, the window
        redrawn. Raises Stopped when the user asked it to stop."""
        first, width = STEPS.get(what, (0.0, 0.0))
        share = float(done) / total if total else 0.0
        self.ak.busy_progress(self, "%s" % what + (" (%d of %d)" % (done, total) if total > 1 else ""),
                              first + width * min(1.0, share))

    def run(self, automatic=True):
        """Checks the font's code; with the automatic option (and automatic), applies the safe fixes and
        checks again."""
        if self.busy:
            return
        current = self.current_font()
        if current is None:
            if self.package is not None:
                self.font_changed()
            else:
                self.font_label.setText(self.ak.no_font_line())
            return
        if self.package is None or self.ak.font_key(current) != self.ak.font_key(self.package):
            self.read_font()
        code = font_code(self.package)
        self.code_there = has_code(code)
        self.set_busy(True, "Checking the feature code")
        try:
            report = check(code, self.order, self.progress)
            prove_fixes(report, self.order, self.progress)
            if automatic and self.auto_box.checked and report.provable is not None:
                chosen = safe_fixes(report, self.order, self.progress)
                if chosen and self.write(report.code, apply_fixes(report.code, chosen), chosen, automatic=True):
                    report = check(font_code(self.package), self.order, self.progress)
                    prove_fixes(report, self.order, self.progress)
        except self.ak.Stopped:
            self.set_busy(False)
            self.status.setText("The check was stopped. Click <i>Check</i> to check again.")
            return
        except Exception as exc:
            self.set_busy(False)
            self.log.add("The check stopped on an error: %s" % self.ak.html("%s" % exc), "error")
            return
        self.set_busy(False)
        self.report = report
        self.seen_history = self.ak.history_mark(self.package)
        self.show_report()

    def show_report(self):
        QtCore, QtGui = _qt()
        report = self.report
        self.tree.blockSignals(True)
        self.tree.clear()
        self.items = []
        groups = report.by_kind()
        kinds = sorted(groups, key=lambda k: (SEVERITY_ORDER[KINDS[k][0]], KINDS[k][1]))
        tristate = getattr(QtCore.Qt, "ItemIsAutoTristate", None) or QtCore.Qt.ItemIsTristate  # (Qt 5.6 and later)
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        for kind in kinds:
            findings = groups[kind]
            group = QtGui.QTreeWidgetItem([group_title(kind, len(findings)), "", ""])
            group.setData(0, QtCore.Qt.UserRole, -1)
            fixable = any(f.fix is not None for f in findings)
            group.setFlags(flags | QtCore.Qt.ItemIsUserCheckable | tristate if fixable else flags)
            group.setFont(0, bold)
            for column in range(len(COLUMNS)):
                group.setToolTip(column, self.ak.html(KINDS[kind][4]))
            self.tree.addTopLevelItem(group)
            for finding in findings:
                index = len(self.items)
                self.items.append(finding)
                message = finding.message + (" (FontLab's automatic code)" if finding.automatic else "")
                item = QtGui.QTreeWidgetItem([message, finding.where(), fix_note(finding.fix)])
                item.setData(0, QtCore.Qt.UserRole, index)
                if finding.fix is not None:
                    item.setFlags(flags | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(0, QtCore.Qt.Unchecked)  # (reviewed by hand: none ticked at first)
                else:
                    item.setFlags(flags)
                item.setToolTip(0, self.ak.html(message))
                group.addChild(item)
            if fixable:
                group.setCheckState(0, QtCore.Qt.Unchecked)
            group.setExpanded(KINDS[kind][0] != ADVICE or len(findings) <= 12)
        self.tree.blockSignals(False)
        try:
            self.ak.fit_rows(self.tree, range(len(COLUMNS) - 1))
        except Exception:
            pass
        self.status.setText(summary_line(report, rich=True))
        self.code.setPlainText("")
        self.update_buttons()

    # -- the list --------------------------------------------------------------

    def rows(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            group = self.tree.topLevelItem(row)
            for child in range(group.childCount()):
                found.append(group.child(child))
        return found

    def finding_of(self, item):
        QtCore, QtGui = _qt()
        try:
            index = int(item.data(0, QtCore.Qt.UserRole))
        except Exception:
            return None
        return self.items[index] if 0 <= index < len(self.items) else None

    def checked_findings(self):
        QtCore, QtGui = _qt()
        out = []
        for item in self.rows():
            finding = self.finding_of(item)
            if finding is not None and finding.fix is not None and item.checkState(0) == QtCore.Qt.Checked:
                out.append(finding)
        return out

    def check_every(self, on):
        rows = [item for item in self.rows() if (self.finding_of(item) or Finding("build", "")).fix is not None]
        self.ak.check_rows(rows, bool(on), self.log, "Tick all" if on else "Tick none", "fix", "fixes",
                           ("in a closed group", "in closed groups"))
        self.update_buttons()

    def update_buttons(self):
        has_font = self.package is not None
        fixes = [f for f in self.items if f.fix is not None]
        checked = len(self.checked_findings()) if fixes else 0
        self.ak.enable(self.check_button, not self.busy and (has_font or self.ak.fonts_open(self.fontlab)))
        # (grayed with nothing to do: no font, or a font without feature code; owner's image 255)
        self.ak.enable(self.compile_button, not self.busy and has_font and self.code_there)
        self.ak.enable(self.apply_button, not self.busy and has_font and checked > 0)
        self.ak.enable(self.check_all, not self.busy and checked < len(fixes))
        self.ak.enable(self.check_none, not self.busy and checked > 0)
        text = "Apply %s" % counted(checked, "ticked fix", "ticked fixes") if checked else APPLY_TEXT
        try:
            if self.apply_button.text != text:
                self.apply_button.setText(text)
        except Exception:
            pass

    def show_code(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        finding = self.finding_of(items[0]) if items else None
        if finding is None or self.report is None:
            return
        self.code.setPlainText(self.report.code.part(finding.key) or "")
        if finding.line:
            # (by paragraph: findBlockByLineNumber counts wrapped lines, and marked the line above, live)
            block = self.code.document().findBlockByNumber(finding.line - 1)
            cursor = QtGui.QTextCursor(block)
            cursor.select(QtGui.QTextCursor.LineUnderCursor)
            try:  # (marked as strongly with the focus on the list as in the box: in light mode the box's unfocused
                # selection was a faint gray, owner's image 367; copied from the palette now, dark or light)
                palette = self.code.palette
                for role in (QtGui.QPalette.Highlight, QtGui.QPalette.HighlightedText):
                    palette.setColor(QtGui.QPalette.Inactive, role, palette.color(QtGui.QPalette.Active, role))
                self.code.setPalette(palette)
            except Exception:
                pass
            self.code.setTextCursor(cursor)
            self.code.centerCursor()

    def auto_toggled(self, on):
        self.settings["auto"] = bool(on)
        write_settings(self.ak, self.settings)
        if on and self.report is not None:
            self.run()

    # -- writing -----------------------------------------------------------

    def apply_checked(self):
        if self.busy or self.report is None or self.package is None:
            return
        chosen = self.checked_findings()
        if not chosen:
            return
        if not font_code(self.package).same(self.report.code):
            self.log.add("The feature code changed since it was checked: checked again, nothing written.", "warning")
            self.run()
            return
        fixes = [f.fix for f in chosen]
        if self.write(self.report.code, apply_fixes(self.report.code, fixes), fixes):
            self.run()

    def write(self, before, after, fixes, automatic=False):
        """Writes the parts of after that differ from before, as one step of FontLab's History; True when
        something was written."""
        prefix, changed, removed = written_parts(before, after)
        if prefix is None and not changed and not removed:
            return False
        if not self.ak.begin_write(self.fontlab, self.package, TITLE, self.log):
            return False
        features = self.package.fgPackage.features
        written, error = [], None
        try:
            if prefix is not None:
                features.set_prefix(prefix)
                written.append("the prefix")
            for tag in [t for t, _ in after.features if t in changed]:
                features.set_feature(tag, changed[tag])
                written.append(tag)
            for tag in removed:
                features.remove(tag)
                written.append("%s (taken out)" % tag)
        except Exception as exc:
            error = exc
        status = self.ak.notify_changed(self.fontlab, self.package, TITLE, added=False)
        if written:
            what = "; ".join(sorted(set(f.what for f in fixes)))
            self.log.add("%s %s (%s) in %s.%s" % (
                "Applied automatically" if automatic else "Applied", self.ak.b(counted(len(fixes), "fix", "fixes")),
                self.ak.html(what), self.ak.b(", ".join(written)),
                status.undo(" <i>Edit &gt; Undo</i> takes %s back." % ("it" if len(fixes) == 1 else "them"))), "done")
        status.report(self.log)
        if error is not None:
            self.log.add("Stopped by an error: %s" % self.ak.html("%s" % error), "error")
        return bool(written)

    def compile_in_fontlab(self):
        """The font's features compiled by FontLab (ak.compiled_note), the window's top row showing it until
        what FontLab's compiler said is in the log (owner's image 212: no feedback before). A compile cannot
        be stopped halfway: the tools menu, the arrows, and Close wait for it."""
        QtCore, QtGui = _qt()
        if self.busy or self.package is None:
            return

        class Box(object):  # (compiled_note's check box, always on here)
            checked = True

        token = object()
        self.compiling = token
        owner = self

        class Told(object):  # the log compiled_note reports to once it has read FontLab's Output panel
            def add(self, *args, **kwargs):
                owner.log.add(*args, **kwargs)
                owner.compiled(token)

        self.set_busy(True, COMPILE_STEP, stoppable=False)
        reads = getattr(self.ak, "_COMPILE_READS", None)
        last = reads[-1] if reads else None
        try:
            note = self.ak.compiled_note(Box(), Told())
        except Exception as exc:
            self.log.add("FontLab did not compile: %s" % self.ak.html("%s" % exc), "error")
            self.compiled(token)
            return
        self.log.add(note.strip())
        # (a read of the Output panel to come: the bar stays until it reports, COMPILE_WAIT_MS at most)
        waiting = bool(reads) and reads[-1] is not last if reads is not None else u"follows in this log" in note
        if not waiting:
            self.compiled(token)
            return
        try:
            self.ak.busy_progress(self, READ_STEP, 0.5, stoppable=False)
        except Exception:
            pass
        self.compile_slot = lambda: self.compiled(token)  # (held: PythonQt drops a slot no Python object holds)
        QtCore.QTimer.singleShot(COMPILE_WAIT_MS, self.compile_slot)

    def compiled(self, token):
        """A compile's report in the log (or its wait over): the top row back as it was. Never raises."""
        try:
            if self.compiling is not token:
                return  # (another compile's, or done already)
            self.compiling = None
            self.set_busy(False)
        except Exception:
            pass

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        if self.package is not None:
            QtCore.QTimer.singleShot(50, self.run)  # checked as it opens


def main():
    """Feature Check on the current font."""
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("Feature Check"):
            return
    except Exception:
        pass
    try:
        dialog = FeatureCheckDialog()
    except Exception as exc:
        print("FreeLab Feature Check: %s" % exc)
        return
    sys._freelab_feature_check = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("Feature Check", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_feature_check":
    main()
