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
        if suffix:
            continue  # a form of a ligature (.sc, .ss01, .case) or a localized one (.loclNLD): its own feature's
        key = u"".join(chars.get(part) or u"\0" for part in parts)
        if u"\0" not in key and all(unicodedata.category(c).startswith(u"M") for c in key):
            continue  # marks stacked (tildecomb_acutecomb): ccmp's, not a ligature to set
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
# Forms: case, locl, fractions and figures, small capitals, stylistic sets
# ---------------------------------------------------------------------------

FORMS = "forms"  # FreeLab's block in each form feature
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


def locl_feature(info):
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
    return FormFeature("locl", rules, make_locl,
                       u"Forms of a language, for text tagged with it (on unless turned off); the prefix "
                       u"declares each language")


LOCL_KINDS = ("ligature", "single", "context")  # a lookup each (a lookup holds one kind of rule)


def make_locl(rules, feature):
    groups = {}
    for rule in rules:
        for script in rule.data["scripts"]:
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
                rules.append(FormRule(u"width " + glyph, [glyph], glyph, u"%d units wide" % int(round(widths[glyph])),
                                      u"The %s are tabular, but %s is not %d units wide like the others: review it "
                                      u"(nothing is changed here)" % (what, glyph, common), warning=True))
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
                              if tag.startswith(u"ss") else u"A character's alternate (off unless turned on)",
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
                       u"What InDesign and Illustrator offer as a selected character's alternates (in place and in "
                       u"their <i>Glyphs</i> panel): every one-for-one alternate of the font's features, and the "
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
    """text without FreeLab's block of that name."""
    begin, end = BEGIN % block_name, END % block_name
    kept, inside = [], False
    for line in (text or u"").splitlines():
        stripped = line.strip()
        if stripped == begin:
            inside = True
        elif stripped == end:
            inside = False
        elif not inside:
            kept.append(line)
    return u"\n".join(kept)


def feature_kind(text):
    """How a feature stands in the font's code: "none" (no code), "fontlab" (FontLab's automatic code
    only), "freelab" (FreeLab's forms block, and nothing by hand), or "hand" (code of the designer's:
    outside both, or in a block handed back from FontLab)."""
    if not text or not text.strip():
        return "none"
    fontlab = freelab = hand = False
    automatic = inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == BEGIN % FORMS:
            inside = freelab = True
            continue
        if stripped == END % FORMS:
            inside = False
            continue
        if inside:
            continue
        if stripped.startswith(FONTLAB_AUTO):
            automatic = fontlab = True
            continue
        if stripped.startswith(u"#<"):
            automatic = False
            continue
        if automatic:
            continue
        code = stripped.split(u"#")[0].strip()
        if not code or re.match(r"^feature\s+\S+\s*\{$", code) or re.match(r"^\}\s*\S+\s*;$", code):
            continue
        hand = True
    if hand:
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
    made = [locl_feature(info), case_feature(info)]
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
            feature.kind_note = (u"The font's code has its own %s: left alone unless you check it (FreeLab's block "
                                 u"then goes in beside it, the rest kept)." % tag)
        elif feature.kind == "fontlab" and covered(feature, text):
            feature.on = False
            feature.kind_note = (u"FontLab makes this feature automatically, and its code does the same: left to "
                                 u"it. Checked, FreeLab's code replaces FontLab's (handed back from it).")
        elif feature.kind == "fontlab":
            feature.kind_note = (u"FontLab makes this feature automatically: FreeLab's code replaces its code, "
                                 u"and the feature is handed back from FontLab (no longer rewritten by it).")
        elif feature.kind == "freelab":
            feature.kind_note = u"FreeLab's code is in the font: written again as shown."
        if feature.tag != "locl" and feature.kind == "hand" and re.search(  # (locl's block sets its own)
                r"^\s*(script|language)\s", strip_block(text, FORMS), re.M):
            feature.kind_note += (u" Its code sets languages: FreeLab's block, at its end, would apply to the last "
                                  u"one only.")
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
    kept, inside, automatic = [], False, False
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
        if lines and stripped.startswith(FONTLAB_AUTO):
            kept.append(line.replace(FONTLAB_AUTO, FONTLAB_HANDED, 1))
            automatic = True
            continue
        if automatic:
            if stripped.startswith(u"#<"):
                automatic = False
                kept.append(line)
            continue
        kept.append(line)
    opening = closing = None
    for index, line in enumerate(kept):
        if opening is None and re.match(r"^\s*feature\s+%s\s*\{" % re.escape(tag), line):
            opening = index
        if re.match(r"^\s*}\s*%s\s*;" % re.escape(tag), line):
            closing = index
    if opening is None or closing is None:  # a new feature
        kept = [u"feature %s {" % tag, u"# %s" % FORM_TITLES.get(tag, tag), u"} %s;" % tag]
        opening, closing = 0, 2
    if not lines:
        return u"\n".join(kept) + u"\n"
    block = [begin] + [u"  " + line for line in lines] + [end]
    if lines[0].startswith((u"featureNames", u"cvParameters")):
        at = opening + 1
        while at < closing and kept[at].strip().startswith(u"#") and not kept[at].strip().startswith(
                (u"#>", u"#/>", u"#<", u"# >>>")):
            at += 1
    else:
        at = closing
    return u"\n".join(kept[:at] + block + kept[at:]) + u"\n"


def forms_texts(features, texts):
    """{tag: new code} for each form feature checked, and each unchecked one whose FreeLab block is in
    the font (taken out); only where the code changes."""
    new = {}
    for feature in features:
        old = texts.get(feature.tag)
        if feature.on:
            text = forms_feature_text(feature.tag, old, feature.lines())
        elif (BEGIN % FORMS) in (old or u""):
            text = forms_feature_text(feature.tag, old, [])
        else:
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
    return u"on the baseline" if not dy else (u"raised %d units" % dy if dy > 0 else u"lowered %d units" % -dy)


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


def build_label(count):
    """The build button's words for this many checked glyphs."""
    return u"Build %s" % counted(count, u"checked glyph") if count else u"Build checked glyphs"


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
    return u"%d %s" % (number, one if number == 1 else (many or one + u"s"))


HELP = u"""<b>FreeLab Feature Code</b><br>
Writes the OpenType code for the font's ligatures, for alternates that take turns, and for the forms
its glyph names call for. The code is shown, and checked, before anything is written.<br><br>
<b>Ligatures and alternates</b> (the first tab):<br>
<b>Ligatures</b>: each ligature with what it replaces, set to <i>Standard</i> (liga, on unless a user turns
it off), <i>Discretionary</i> (dlig, off unless a user turns it on), or <i>Off</i>. A ligature the font's code and
name do not place starts where most of the open-licensed fonts FreeLab learned from put it (f_i in
liga, c_t in dlig); its feature's tooltip says why. Applications let users switch
both: in InDesign and Illustrator, the <i>Ligatures</i> and <i>Discretionary Ligatures</i> options; on the web,
font-variant-ligatures. A feature written here is handed back from FontLab's automatic features (its
"#&gt; feature" line becomes "#/&gt; feature"), so FontLab no longer rewrites it; the rest of its
code is kept.<br>
<b>Alternates that take turns</b> (calt, on unless turned off): a letter repeated within the letters
set takes its next alternate (X.2, X.3, or X.alt1...), so repeated letters vary as handwriting does.
The nearest earlier form decides; a space or punctuation ends the look back. Ligatures come first:
where liga makes l_l of <i>ll</i>, the alternates take turns around it.<br><br>
<b>Forms</b> (the second tab): one row per feature, its substitutions under it (click its arrow):
case (.case), locl (Romanian and Moldavian <i>S</i> and <i>T</i> with a comma below, Catalan
<i>l\N{MIDDLE DOT}l</i>, Dutch <i>\N{LATIN SMALL LETTER I WITH ACUTE}j</i>, the Turkic dotted <i>i</i>, and any
.loclXXX glyph), frac, numr, and dnom
(.numr, .dnom), sups, subs, and sinf, ordn, smcp and c2sc (.sc, .smcp, .c2sc), lnum, onum, pnum, and
tnum (.tf, .lf, .osf, .tosf...), and the stylistic sets (.ss01 to .ss20, each with a name you can edit)
and character variants (.cv01...). Check a feature to write it, and its rows to keep them in it. A
feature the font's code has by hand starts unchecked, as does one FontLab's automatic code already
makes the same way; a warning row (figures of a tabular set that do not share one width) is for you
to review, and changes nothing.<br>
<b>Figure forms to build</b> (under the forms): the numerators, denominators, superiors, inferiors,
Unicode superscript and subscript figures, and ordinal indicators the font lacks, each made of its
figure (or <i>a</i> or <i>o</i>) as a component, scaled and raised or lowered as most open-licensed fonts place
them (or as the font's own small figures, where it has some). Pick a set in the settings row to change
its scale, baseline, and width. Scaling thins the strokes: a built form is a start to draw over.
<i>Build checked glyphs</i> adds them in one step of FontLab's History; the font is read again, and
the forms above take them.<br><br>
The code is made again as you change the choices. Pick a ligature's feature in its box; drag between the parts to give one more room;
double-click a ligature, a letter, or a form to see it in a <i>Glyph</i> window. <i>Restore suggestions</i> puts the
choices back as they first came.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""

TABS = (u"Ligatures and alternates", u"Forms")
FORM_ICON_WIDTH = 3  # a form row's picture: this many icons wide

# The check boxes of a list whose pictures dark mode leaves alone (LEAVE_ALONE_PROP): the style drew
# them nearly invisible on a dark palette, so a stylesheet draws them from the palette instead
CHECK_FRAME = u"rgb(140, 140, 146)"  # an unchecked box's frame: a mid gray, plain on either background
CHECK_MARK_SCALE = 3  # the check mark is drawn this many times the box's size (sharp on a scaled display)
CHECK_SHEET_MARK = u"/* FreeLab check boxes */"


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
    """The list's check boxes drawn in its palette's colors (base: its own stylesheet, kept before them)."""
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


def watch_check_boxes(dialog, trees):
    """The trees' check boxes drawn plain to see in either palette, and drawn again when dark mode
    switches; the watcher to keep a reference to (None where it could not be made)."""
    QtCore, QtGui = _qt()
    bases = []
    for tree in trees:
        sheet = tree.styleSheet() if callable(tree.styleSheet) else tree.styleSheet
        sheet = u"%s" % (sheet or u"")
        bases.append(sheet.split(CHECK_SHEET_MARK)[0].strip())

    def restyle():
        for tree, base in zip(trees, bases):
            try:
                style_check_boxes(QtCore, QtGui, tree, base)
            except Exception:
                pass

    restyle()

    class CheckWatcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
        def eventFilter(self, obj, event):
            try:
                if event.type() in (38, 39):  # the palette changed: dark mode switched
                    self.start()
            except Exception:
                pass  # an event filter must never raise
            return False

    try:
        watcher = CheckWatcher()
        watcher.setSingleShot(True)
        watcher.setInterval(0)
        watcher.connect("timeout()", restyle)
        dialog.installEventFilter(watcher)
        return watcher
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
        self.status = self.ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.ak.separator())
        self.log = self.ak.Log()
        self.seen_history, self.first_choices, self.first_checks = None, [], []

        # The lists (on two tabs) and the code share the height in a splitter: drag between them to see
        # more of one
        self.splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setWhatsThis(u"Drag the space between two parts up or down to give one more room.")
        layout.addWidget(self.splitter, 1)
        top = self.part(QtGui, 3)
        # A tab bar over plain pages: a QTabWidget's themed page drew its buttons with light frames in dark mode
        self.tabs = QtGui.QTabBar()
        self.tabs.setExpanding(False)
        for label in TABS:
            self.tabs.addTab(label)
        self.tabs.setTabToolTip(0, u"Ligatures (liga, dlig) and alternates that take turns (calt)")
        self.tabs.setTabToolTip(1, u"Forms: case, locl, fractions and figures, small capitals, stylistic sets")
        top.addWidget(self.tabs)
        self.pages = QtGui.QStackedWidget()
        top.addWidget(self.pages, 1)

        self.lists = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.lists.setChildrenCollapsible(False)
        self.lists.setWhatsThis(u"Drag the space between two parts up or down to give one more room.")
        self.pages.addWidget(self.lists)
        part = self.part(QtGui, 2, self.lists)
        part.addWidget(self.heading(QtGui, u"Ligatures"))
        self.ligature_tree = QtGui.QTreeWidget()
        self.ligature_tree.setColumnCount(3)
        self.ligature_tree.setHeaderLabels(["Ligature", "Replaces", "Feature"])
        self.ligature_tree.setRootIsDecorated(False)
        self.ligature_tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.ligature_tree.setWhatsThis(u"Each ligature, what it replaces, and the feature it goes in (pick it to "
                                        u"change it). Standard ligatures are on unless a user turns them off; "
                                        u"discretionary ones off unless turned on.")
        self.ligature_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        self.ak.grid_lines(self.ligature_tree)
        part.addWidget(self.ligature_tree, 1)

        part = self.part(QtGui, 1, self.lists)
        part.addWidget(self.heading(QtGui, u"Alternates that take turns"))
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
        part.addLayout(row)
        self.alternate_tree = QtGui.QTreeWidget()
        self.alternate_tree.setColumnCount(3)
        self.alternate_tree.setHeaderLabels(["Letter", "Cycle", "Note"])
        self.alternate_tree.setRootIsDecorated(False)
        self.alternate_tree.setIconSize(QtCore.QSize(ICON_SIZE * 3, ICON_SIZE))
        self.alternate_tree.setWhatsThis(u"The letters with alternates (named X.2, X.alt1, or X.calt1), and their "
                                         u"cycle: the forms they take in turn. Checked letters take turns.")
        self.alternate_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.grid_lines(self.alternate_tree)
        part.addWidget(self.alternate_tree, 1)

        forms_page = QtGui.QWidget()
        box = QtGui.QVBoxLayout(forms_page)
        box.setContentsMargins(0, 0, 0, 0)
        self.forms_label = QtGui.QLabel(u"")
        self.forms_label.setWordWrap(True)
        box.addWidget(self.forms_label)
        self.forms_parts = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.forms_parts.setChildrenCollapsible(False)
        self.forms_parts.setWhatsThis(u"Drag the space between two parts up or down to give one more room.")
        box.addWidget(self.forms_parts, 1)
        forms_box = self.part(QtGui, 3, self.forms_parts)
        self.forms_tree = QtGui.QTreeWidget()
        self.forms_tree.setColumnCount(3)
        self.forms_tree.setHeaderLabels(["Feature", "Becomes", "Note"])
        self.forms_tree.setRootIsDecorated(True)
        self.forms_tree.setIconSize(QtCore.QSize(ICON_SIZE * FORM_ICON_WIDTH, ICON_SIZE))
        self.forms_tree.setWhatsThis(u"The form features the font's glyph names call for, each with its substitutions "
                                     u"under it (click its arrow). A checked feature is written, with its checked "
                                     u"rows; a set's name (the Becomes column of its row) is what applications show, "
                                     u"and you can edit it. Amber rows are warnings to review: they change nothing.")
        self.forms_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.grid_lines(self.forms_tree)
        forms_box.addWidget(self.forms_tree, 1)
        self.small_forms, self.small_plans, self.small_info = [], {}, None
        self.small_setup, self.small_first, self.small_set_index = {}, {}, 0
        self.build_part(QtCore, QtGui, self.part(QtGui, 2, self.forms_parts))
        self.pages.addWidget(forms_page)

        part = self.part(QtGui, 2)
        part.addWidget(self.heading(QtGui, u"The code"))
        self.code = QtGui.QPlainTextEdit()
        self.code.setReadOnly(True)
        self.code.setWhatsThis(u"The code to be written, feature by feature: FreeLab's blocks between their "
                               u"marker lines, the rest of each feature as it is; the prefix's language systems "
                               u"first where locl needs some.")
        part.addWidget(self.code, 1)

        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every ligature's feature, every letter's, form's, and figure form's "
                                         u"check, every set's name, and the build settings back as they first came.")
        self.write_button = QtGui.QPushButton("Write the code")
        self.write_button.setWhatsThis(u"Writes the features as shown (liga, dlig, calt, and the checked forms) to the "
                                       u"font, and the language systems locl needs to its prefix (<i>Update the code</i>: "
                                       u"FreeLab's code is in them already, and changes).")
        self.close_button = QtGui.QPushButton("Close")
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        self.compile_box = self.ak.compile_box()
        buttons.addWidget(self.compile_box)
        buttons.addWidget(self.write_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.restore_button.connect("clicked()", self.restore)
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", dialog.close)
        self.tabs.connect("currentChanged(int)", self.switch_page)
        self.look_back.connect("valueChanged(int)", lambda value: self.make_code())
        self.ligature_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.alternate_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.alternate_tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.make_code())
        self.forms_tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.double_clicked)
        self.forms_tree.connect("itemChanged(QTreeWidgetItem*,int)", self.form_checked)
        self.forms_tree.connect("itemExpanded(QTreeWidgetItem*)", self.form_expanded)
        self.package = None
        self.combos = []  # each ligature's feature box, by its index in found (held: PythonQt deletes what Python does not)
        self.name_edits = {}  # each set's name box, by its tag (held likewise)
        self.names, self.letters, self.found, self.sets = [], [], [], {}
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
            self.check_watcher = watch_check_boxes(dialog, [self.alternate_tree, self.forms_tree, self.small_tree])
        except Exception:
            self.check_watcher = None

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)

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
        package = workspace.currentPackage
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def run(self):
        QtCore, QtGui = _qt()
        kept = self.small_state()  # (the builds' checks and settings, kept for the same font)
        package = self.package = self.current_font()
        if kept is not None and (package is None or self.ak.font_key(package) != kept[0]):
            kept = None
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
            self.status.setText(u"No font is open. Open one, then run <i>Feature Code</i> again.")
            self.forms_label.setText(u"")
            self.small_forms, self.small_plans, self.small_info = [], {}, None
            self.show_small_forms()
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
            item.setToolTip(2, u"Its feature. First set by %s." % (lig.why or u"default"))
            self.ligature_tree.addTopLevelItem(item)
            combo = self.ak.flat_combo(QtGui.QComboBox())
            for _, label in CHOICES:
                combo.addItem(label)
            combo.setToolTip(u"Its feature. First set by %s." % (lig.why or u"default"))
            combo.connect("currentIndexChanged(int)", lambda choice, lig=lig: self.choose(lig, choice))
            self.ligature_tree.setItemWidget(item, 2, combo)
            self.combos.append(combo)
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
        self.checked_code = {}
        self.read_forms(glyphs)
        self.make_code()
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
            item = QtGui.QTreeWidgetItem([feature.tag, u"", u" ".join(t for t in (feature.kind_note, feature.note) if t)])
            self.ak.section_row(item, tree)
            item.setData(0, QtCore.Qt.UserRole, feature.tag)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(0, QtCore.Qt.Checked if feature.on else QtCore.Qt.Unchecked)
            item.setToolTip(0, u"%s (%s): %s." % (feature.title(), feature.tag, counted(len(feature.rules), u"row")))
            item.setToolTip(2, item.text(2))
            if feature.tag not in SET_TAGS:
                item.setText(1, u"%s (%d)" % (feature.title(), len(feature.rules)))
            tree.addTopLevelItem(item)
            for rule in feature.rules:
                child = QtGui.QTreeWidgetItem([rule.source, rule.target, rule.note])
                child.setData(0, QtCore.Qt.UserRole, u"%s\t%s" % (feature.tag, rule.key))
                child.setToolTip(2, rule.note)
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
                    edit.setToolTip(u"The name the font's own code gives this set: edit it there.")
                else:
                    edit.setToolTip(u"The set's name, as applications show it (suggested from what it changes): "
                                    u"edit it as you like.")
                edit.connect("textEdited(QString)", lambda text, feature=feature: self.rename(feature, text))
                tree.setItemWidget(item, 1, edit)
                self.name_edits[feature.tag] = edit
        tree.blockSignals(False)
        tree.resizeColumnToContents(0)
        tree.setColumnWidth(1, max(tree.columnWidth(1), ICON_SIZE * FORM_ICON_WIDTH + 160))
        if self.figures:
            self.forms_label.setText(u"The default figures are %s (by %s). %s" % (
                self.ak.b(describe_style(*self.figures[:2])), self.ak.html(self.figures[2]),
                u"Click a feature's arrow for its rows." if self.forms else u""))
        if not self.forms:
            self.forms_label.setText(u"No glyph is named for a form feature (.case, .sc, .numr, .ss01...): "
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
                    child.setIcon(1, QtGui.QIcon(icon))
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
        part.addWidget(self.heading(QtGui, u"Figure forms to build"))
        self.small_label = QtGui.QLabel(u"")
        self.small_label.setWordWrap(True)
        part.addWidget(self.small_label)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(u"Settings of"))
        self.small_set = QtGui.QComboBox()
        for key in SMALL_SETS:
            self.small_set.addItem(SMALL_SET_TITLES[key])
        self.small_set.setWhatsThis(u"The set whose settings the boxes beside show and change (clicking a row "
                                    u"picks its set).")
        row.addWidget(self.small_set)
        row.addWidget(QtGui.QLabel(u"Scale"))
        self.small_scale = QtGui.QSpinBox()
        self.small_scale.setRange(20, 95)
        self.small_scale.setSuffix(u"%")
        self.small_scale.setWhatsThis(u"The size of the set's glyphs, of their figure's (or letter's). Numerators and "
                                      u"ordinal indicators keep their top where it is; the others their baseline.")
        row.addWidget(self.small_scale)
        row.addWidget(QtGui.QLabel(u"Baseline at"))
        self.small_baseline = QtGui.QSpinBox()
        self.small_baseline.setRange(-3000, 3000)
        self.small_baseline.setSuffix(u" units")
        self.small_baseline.setWhatsThis(u"Where the scaled figure's baseline goes, in font units above the font's "
                                         u"baseline (below it, negative).")
        row.addWidget(self.small_baseline)
        row.addWidget(QtGui.QLabel(u"Width"))
        self.small_width = QtGui.QSpinBox()
        self.small_width.setRange(50, 200)
        self.small_width.setSuffix(u"%")
        self.small_width.setWhatsThis(u"The advance width, of the scaled figure's: above 100%, a little more room "
                                      u"around the small figure (most open-licensed fonts give them 112%).")
        row.addWidget(self.small_width)
        self.small_reset = QtGui.QPushButton(u"Suggested")
        self.small_reset.setWhatsThis(u"Puts the set's scale, baseline, and width back as first suggested.")
        row.addWidget(self.small_reset)
        self.small_why = QtGui.QLabel(u"")
        row.addWidget(self.small_why, 1)
        part.addLayout(row)
        self.small_tree = QtGui.QTreeWidget()
        self.small_tree.setColumnCount(3)
        self.small_tree.setHeaderLabels(["Glyph", "Made of", "Note"])
        self.small_tree.setRootIsDecorated(True)
        self.small_tree.setIconSize(QtCore.QSize(ICON_SIZE * 2, ICON_SIZE))
        self.small_tree.setWhatsThis(u"The figure forms the font lacks, by set (click a set's arrow): each glyph, what "
                                     u"it would be made of, drawn beside its figure, and its code point. Checked "
                                     u"glyphs are built.")
        self.small_tree.setProperty(self.ak.LEAVE_ALONE_PROP, True)
        self.ak.grid_lines(self.small_tree)
        part.addWidget(self.small_tree, 1)
        row = QtGui.QHBoxLayout()
        row.addStretch(1)
        self.build_button = QtGui.QPushButton(build_label(0))
        self.build_button.setWhatsThis(u"Adds the checked glyphs to the font, made of components as shown, in one "
                                       u"step of FontLab's History. The font is read again: the forms above take "
                                       u"them.")
        self.build_button.setEnabled(False)
        row.addWidget(self.build_button)
        part.addLayout(row)
        self.small_set.connect("currentIndexChanged(int)", self.small_set_picked)
        self.small_scale.connect("valueChanged(int)", lambda value: self.small_setting("scale", value))
        self.small_baseline.connect("valueChanged(int)", lambda value: self.small_setting("baseline", value))
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
                item.setFirstColumnSpanned(True)  # (its check box and count whole, not cut by the first column)
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
            self.small_label.setText(u"")
        elif self.small_forms:
            self.small_label.setText(
                u"The font lacks %s. Each is made of its figure (or <i>a</i> or <i>o</i>) as a component, scaled and "
                u"moved, or of a "
                u"drawn small figure where the font has a whole set of them: a start, not a drawing. Scaling thins "
                u"the strokes (a figure at 60%% has stems 60%% as thick; most fonts' drawn small figures have "
                u"ink about 7%% wider than scaling gives): draw over them, or draw your own. Built, the features above "
                u"take them." % (
                    self.ak.b(counted(len(self.small_forms), u"figure form"))))
        elif self.small_info is not None and not any(self.small_info.figures()):
            self.small_label.setText(u"The font has no figures 0 to 9 to build small forms of.")
        else:
            self.small_label.setText(u"The font has every figure form FreeLab builds: numerators, denominators, "
                                     u"superiors, inferiors, their Unicode characters, and the ordinal indicators.")
        self.small_set_picked(self.small_set_index)
        self.replan()

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
                item.setText(1, u"%d of %s checked" % (on, counted(total, u"glyph")))
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
                            SMALL_NOTES.get(plan.how if plan is not None else None, u"")) if text)
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
                child.setIcon(1, QtGui.QIcon(icon))

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
                painter.fillPath(QtGui.QTransform(sx, 0.0, 0.0, sy, float(dx), float(dy)).map(path), QtGui.QBrush(color))
            painter.restore()
        finally:
            painter.end()
        return pixmap

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
                self.small_why.setText(u"Suggested: %s" % self.ak.html(setting.get("why") or u""))
            else:
                self.small_why.setText(u"")
        finally:
            for box in boxes:
                box.blockSignals(False)

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
        elif key == "baseline":
            setting["baseline"] = int(value)
        else:
            setting["width"] = value / 100.0
        self.replan()

    def small_suggested(self):
        """The picked set's settings back as first suggested."""
        set_key = SMALL_SETS[self.small_set_index]
        if set_key in self.small_first:
            self.small_setup[set_key] = dict(self.small_first[set_key])
            self.small_set_picked(self.small_set_index)
            self.replan()

    def small_changed(self):
        return any(form.on != form.first_on for form in self.small_forms) or any(
            self.small_setup.get(key, {}).get(k) != setting.get(k) for key, setting in self.small_first.items()
            for k in ("scale", "baseline", "width"))

    def update_small_buttons(self):
        count = sum(1 for form in self.small_forms if form.on and self.small_plans.get(form.name) is not None)
        self.build_button.setText(build_label(count))
        self.ak.enable(self.build_button, count > 0)
        self.ak.enable(self.restore_button, self.restorable())

    def restorable(self):
        return [lig.choice for lig in self.found] != self.first_choices or self.alternate_checks() != self.first_checks \
            or self.forms_changed() or self.small_changed()

    def has_code(self, package, code):
        try:
            return package.findUnicode(code) is not None
        except Exception:
            return False

    def build_small_forms(self):
        """The checked figure forms added to the font, made of components as planned, in every master
        (placed by the current master's measures; widths from each master's own glyphs), as one step of
        FontLab's History; a code point set once its glyph's layers are made."""
        QtCore, QtGui = _qt()
        if self.package is None or self.small_info is None:
            return
        chosen = [form for form in self.small_forms if form.on]
        if not chosen:
            return
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed since the list was made: here is this one's. Nothing was built.", "warning")
            return
        fontlab = self.fontlab
        try:
            masters = list(package.masters)
        except Exception:
            masters = []
        masters = masters or [package.master]
        plans = {}

        def plans_of(master):
            if master not in plans:
                def advance(name):
                    glyph = package.findName(name)
                    layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
                    return layer.advanceWidth if layer is not None else None
                plans[master] = plan_small_forms(self.small_info, self.small_forms, self.small_setup, advance)
            return plans[master]

        made, skipped, failed, error, touched = [], [], [], None, []
        try:
            for master in masters:
                plans_of(master)  # (each master planned before anything is added)
            for form in sorted(chosen, key=lambda f: f.group in ("superscript", "subscript")):
                if package.findName(form.name) is not None or (form.code and self.has_code(package, form.code)):
                    skipped.append(form.name)  # made meanwhile
                    continue
                new = fontlab.flGlyph()
                new.name = form.name
                # (its code point set once its layers are made: given before, FontLab kept none of them)
                package.addGlyph(new)  # (FontLab adds a copy, without layers: they are made on the font's glyph)
                glyph = package.findName(form.name)
                if glyph is None:
                    raise RuntimeError(u"FontLab did not add %s" % form.name)
                placed = False
                for master in masters:
                    plan = plans_of(master).get(form.name)
                    if plan is None or any(package.findName(part[0]) is None for part in plan.parts):
                        continue  # its figure not drawn in this master, or the glyph it copies not built
                    components = []
                    for part in plan.parts:
                        name, sx, sy, dx, dy = unwrapped(package, master, *part)
                        component = fontlab.GlyphComponent(name)
                        component.transform = QtGui.QTransform(sx, 0.0, 0.0, sy, float(round(dx)), float(round(dy)))
                        components.append(component)
                    layer = glyph.getLayerByName(master, True)
                    layer.setGlyphComponents(components, float(plan.width), package, False)
                    placed = True
                if not placed or is_empty(package.findName(form.name)):
                    failed.append((form.name, u"FontLab did not keep its components" if placed else
                                   u"its figure has no width in any master"))
                    package.deleteGlyph(package.findName(form.name))
                    continue
                if form.code:
                    package.findName(form.name).fgGlyph.unicode = form.code
                touched.append(glyph)
                made.append(form.name)
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
        self.ak.notify_changed(fontlab, package, u"FreeLab Feature Code", touched)
        b = self.ak.b
        if made:
            one = len(made) == 1
            self.log.add(u"Built %s: %s. %s at the end of the font; <i>Edit &gt; Undo</i> takes %s back. Scaling thins "
                         u"strokes: draw over what was scaled. The forms above take %s now: check their features "
                         u"and write the code." % (
                             b(counted(len(made), u"glyph")), self.ak.html(u", ".join(made)),
                             u"It is" if one else u"They are", u"it" if one else u"them", u"it" if one else u"them"),
                         "done")
        else:
            self.log.add(u"Built none.")
        if skipped:
            self.log.add(u"%s had been made meanwhile and %s left as %s." % (
                b(u", ".join(skipped)), u"was" if len(skipped) == 1 else u"were",
                u"it was" if len(skipped) == 1 else u"they were"), "warning")
        for name, why in failed:
            self.log.add(u"%s was not built: %s." % (b(name), self.ak.html(why)), "warning")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")
        forms = self.form_state()
        self.run()
        self.apply_form_state(forms)
        self.make_code()

    # -- the rest -----------------------------------------------------------------------

    def part(self, QtGui, stretch, splitter=None):
        """A part of a splitter (the dialog's, unless another is given): its layout, to fill (stretch:
        its share of the height at first)."""
        splitter = splitter if splitter is not None else self.splitter
        widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(widget)
        splitter.setStretchFactor(splitter.indexOf(widget), stretch)
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
        self.small_setup = dict((key, dict(setting)) for key, setting in self.small_first.items())
        self.show_small_checks()
        self.small_set_picked(self.small_set_index)
        self.replan()
        self.make_code()
        self.log.add(u"Choices restored as suggested.")

    def double_clicked(self, item, column):
        """A ligature's glyphs, a letter's forms, or a form's glyphs in a Glyph window."""
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

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the font read again, the choices kept where they still apply."""
        choices = dict((lig.glyph, lig.choice) for lig in self.found)
        forms = self.form_state()
        self.run()
        for row, lig in enumerate(self.found):
            if lig.glyph in choices and choices[lig.glyph] != lig.choice:
                lig.choice = choices[lig.glyph]
                self.show_choice(self.ligature_tree.topLevelItem(row), lig)
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
        with rules FreeLab takes over), and for the form features that change."""
        texts = ligature_texts(self.found, self.texts)
        cycling = self.cycling()
        if cycling or (BEGIN % "alternates") in (self.texts.get("calt") or u""):
            texts["calt"] = calt_text(self.texts.get("calt"),
                                      cycle_code(cycling, self.letters, self.look_back.value) if cycling else [])
        texts.update(forms_texts(self.forms, self.texts))
        return texts

    def tags_shown(self, texts):
        return [tag for tag in ("liga", "dlig", "calt") if tag in texts] + \
            [feature.tag for feature in self.forms if feature.tag in texts]

    def make_code(self):
        if self.package is None:
            return
        texts = self.new_texts()
        prefix = self.new_prefix()
        shown, problems = [], []
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
        self.code.setPlainText(u"\n".join(shown))
        present = any((BEGIN % kind) in (self.texts.get(tag) or u"")
                      for tag, kind in (("liga", "ligatures"), ("dlig", "ligatures"), ("calt", "alternates"))) or \
            any((BEGIN % FORMS) in (text or u"") for text in self.texts.values())
        changes = bool(texts and any(texts[tag] != self.texts.get(tag) for tag in texts)) or prefix is not None
        self.write_button.setText(u"Update the code" if present else u"Write the code")
        self.ak.enable(self.write_button, changes and not problems)
        self.ak.enable(self.restore_button, self.restorable())
        counts = dict((key, sum(1 for lig in self.found if lig.choice == key)) for key, _ in CHOICES)
        b = self.ak.b
        checked = [feature.tag for feature in self.forms if feature.on and feature.checked()]
        self.status.setText(u"%s: %s (%s standard, %s discretionary, %s off); %s with alternates taking turns.\n"
                            u"Forms: %s checked of %s%s.%s%s" % (
                                b(self.package.tfn), b(counted(len(self.found), u"ligature")), b(counts["liga"]),
                                b(counts["dlig"]), b(counts["off"]), b(counted(len(self.cycling()), u"letter")),
                                b(len(checked)), b(counted(len(self.forms), u"form feature")),
                                (u" (%s)" % self.ak.html(u", ".join(checked))) if checked else u"",
                                u" The font has this code already." if not changes and (texts or self.forms) else u"",
                                (u" The code has problems, so nothing can be written: " +
                                 self.ak.html(u"; ".join(problems))) if problems else u""))

    def write(self):
        if self.package is None:
            return
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(self.package):
            self.run()
            self.log.add(u"The font changed: here is this one's code. Nothing was written.", "warning")
            return
        features = self.package.fgPackage.features
        texts = self.new_texts()
        prefix = self.new_prefix()
        try:
            prefix_now = features.get_prefix() or u""
        except Exception:
            prefix_now = self.prefix
        tags = set(("liga", "dlig", "calt")) | set(texts)
        if any((features.get_feature(tag) if tag in features.keys() else None) != self.texts.get(tag) for tag in tags) \
                or prefix_now != self.prefix:
            self.run()
            self.log.add(u"The features changed since they were read: here they are again. Nothing was written.",
                         "warning")
            return
        written, error, skipped = [], None, None
        try:
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
                features.set_feature(tag, texts[tag])
                written.append(tag)
            if u"aalt" in written and aalt_first(features):
                written[written.index(u"aalt")] = u"aalt (first among the features)"
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.fontlab, self.package, u"FreeLab Feature Code")
        forms = self.form_state()
        self.run()
        self.apply_form_state(forms)
        self.make_code()
        them = u"it" if len(written) == 1 else u"them"
        self.log.add(u"Wrote %s; <i>Edit &gt; Undo</i> takes %s back.%s" % (
            self.ak.b(u", ".join(written)), them, self.ak.compiled_note(self.compile_box, self.log)) if written else u"Wrote nothing.",
            "done" if written else "info")
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
