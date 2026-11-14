#FLM: CJK Spacing
# -*- coding: utf-8 -*-
"""FreeLab CJK Spacing, from FontLab's Scripts menu.

Writes the OpenType code that sets a Japanese font's full-width kana and punctuation proportionally:

- palt (proportional alternate widths, which applications turn on for proportional Japanese text):
  each full-width kana, CJK punctuation mark, and full-width form is trimmed to its ink and the
  sidebearings the open-licensed CJK fonts give theirs (cjk/palt_model.json, measured by
  cjk/train/palt.py: about 0.07 em on each side for kana, each punctuation mark its own).
- halt (half widths, for punctuation set in half the em, as in tight headlines): each punctuation
  mark's half-width setting, as those fonts set it (an opening bracket keeps its right half, a comma
  its left).

- Hangul widths: none of the corpus's Korean fonts kerns Hangul or puts it in palt; they set every
  syllable at one width (0.9 em, the median) or give each its own, its sidebearings by its shape
  (cjk/hangul_model.json, measured by cjk/train/hangul.py). On request, the font's syllables are set
  either way: their outlines moved and their widths changed, in every master.

Shows each glyph's trim and the text set both ways before anything is written, and writes only the
glyphs you leave checked, between FreeLab's marker lines in palt and halt (the rest of each feature
kept).

Valid Python 2.7 (FontLab 7) and Python 3. The planning below the Qt line needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import os
import re
import sys

MODEL_FILE = "palt_model.json"
HANGUL_MODEL_FILE = "hangul_model.json"
HANGUL_MODES = (("leave", u"Leave as they are"), ("fixed", u"One width for all, ink centered"),
                ("proportional", u"Proportional, by syllable shape"))
HANGUL_SHAPES = (("vertical", u"Vowel beside (\uac00)"), ("vertical final", u"Vowel beside, final (\uac01)"),
                 ("horizontal", u"Vowel under (\uace0)"), ("horizontal final", u"Vowel under, final (\uace1)"),
                 ("mixed", u"Vowel beside and under (\uacfc)"), ("mixed final", u"Vowel beside and under, final (\uacfd)"))
HANGUL_TOLERANCE = 2  # a syllable moved and widened by less than this is left alone
FULL_WIDTH_SHARE = 0.9  # a glyph narrower than this share of the em is proportional already: left alone
TOLERANCE_UNITS = 4  # a trim smaller than this on both sides is not listed
BEGIN, END = u"# >>> FreeLab %s (made by FreeLab CJK Spacing)", u"# <<< FreeLab %s"
FONTLAB_AUTO, FONTLAB_HANDED = u"#> feature", u"#/> feature"
FEATURE_TITLES = {"palt": "Proportional Alternate Widths", "halt": "Alternate Half Widths"}
KINDS = ("hiragana", "small hiragana", "katakana", "small katakana", "punctuation")
KIND_LABELS = {"hiragana": "Hiragana", "small hiragana": "Small hiragana", "katakana": "Katakana",
               "small katakana": "Small katakana", "punctuation": "Punctuation and full-width forms",
               "hangul": "Hangul"}
# One sample per writing system the trims serve, each set with the full-width punctuation palt trims:
# the Iroha (Japanese, 11th century, public domain: every kana once), a Hangul pangram written for
# FreeLab (GPL-3 with the code: the 14 basic consonants and the 10 basic vowels; Proof has it too), and
# the opening lines of the Thousand Character Classic (public domain, no character twice: a pangram of
# hanzi cannot be) in each Chinese standard's forms. The one the font covers best is shown first; the
# field takes any text of one's own.
SAMPLE = u"「いろはにほへと、ちりぬるを。わかよたれそ、つねならむ。うゐのおくやま、けふこえて。あさきゆめみし、ゑひもせす。」（いろはうた）"
SAMPLES = (("ja", u"Japanese", SAMPLE),
           ("ko", u"Korean", u"「토요일 아침, 키 큰 여행자가 푸른 바다 앞 야자수 그늘에서 휴식을 즐겼다.」"),
           ("zh-hans", u"Chinese (Simplified)", u"「天地玄黄，宇宙洪荒。日月盈昃，辰宿列张。寒来暑往，秋收冬藏。」（千字文）"),
           ("zh-hant", u"Chinese (Traditional)", u"「天地玄黃，宇宙洪荒。日月盈昃，辰宿列張。寒來暑往，秋收冬藏。」（千字文）"))
SAMPLE_SCRIPTS = {"ja": ((0x3041, 0x30FA),), "ko": ((0xAC00, 0xD7A3),),
                  "zh-hans": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF)), "zh-hant": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF))}


def best_sample(codes):
    """The index in SAMPLES of the sample the font covers best (codes: the font's code points; its
    full-width punctuation counted too): the largest share of its characters, then the most glyphs of
    its own script in the font (a Korean or a Chinese font with kana is not shown the Iroha), then the
    first."""
    codes = set(codes)

    def score(index):
        key, _, text = SAMPLES[index]
        chars = [ord(ch) for ch in text if not ch.isspace()]
        share = round(sum(1 for code in chars if code in codes) / float(len(chars) or 1), 3)
        own = sum(1 for code in codes for low, high in SAMPLE_SCRIPTS.get(key, ()) if low <= code <= high)
        return (share, own, -index)
    return max(range(len(SAMPLES)), key=score)


CJK_RANGES = ((0x3000, 0x30FF), (0x3100, 0x31FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7A3),
              (0xF900, 0xFAFF), (0xFF00, 0xFFEF), (0x1100, 0x11FF), (0x3130, 0x318F))


def sample_misses(codes, text):
    """The font's CJK characters (sorted) when the sample text shows none of them, else []: the
    preview would be empty, so the log names them."""
    codes = set(codes)
    if any(ord(ch) in codes for ch in text if not ch.isspace()):
        return []
    return [unichr_(code) for code in sorted(codes) if any(low <= code <= high for low, high in CJK_RANGES)]


def counted_chars(number):
    return u"%d CJK character%s" % (number, u"" if number == 1 else u"s")


# Kinsoku, as Japanese sets lines: never first on a line (closing marks, small kana, the long vowel
# mark), never last (opening marks)
NO_LINE_START = set(u"、。，．・：；？！）」』】〕〉》｝］ー々ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ,.:;?!)]}")
NO_LINE_END = set(u"「『（【〔〈《｛［([{")


def break_lines(chars, widths, room):
    """A sample's lines: [(start, end)] ranges of its characters, each line no wider than room
    (widths: each character's, in the same unit), unless one character alone is. A line breaks after
    a space where it has one (Korean), else between any two characters but not before a closing mark
    or a small kana, nor after an opening mark; the spaces a break leaves at a line's start are dropped."""
    lines, start, count = [], 0, len(chars)
    while start < count:
        while start < count and chars[start] == u" ":
            start += 1
        if start >= count:
            break
        width, end = 0.0, start
        while end < count and (end == start or width + widths[end] <= room):
            width += widths[end]
            end += 1
        if end < count:
            spaces = [k for k in range(end, start, -1) if chars[k - 1] == u" "]
            fits = [k for k in range(end, start, -1)
                    if chars[k] not in NO_LINE_START and chars[k - 1] not in NO_LINE_END]
            end = spaces[0] if spaces else (fits[0] if fits else end)
        stop = end
        while stop > start and chars[stop - 1] == u" ":
            stop -= 1
        lines.append((start, stop))
        start = end
    return lines


SMALL_KANA = set([0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3063, 0x3083, 0x3085, 0x3087, 0x308E, 0x3095, 0x3096,
                  0x30A1, 0x30A3, 0x30A5, 0x30A7, 0x30A9, 0x30C3, 0x30E3, 0x30E5, 0x30E7, 0x30EE, 0x30F5, 0x30F6])


def kind_of(code):
    """The kind of glyph a code point is, as palt groups them, or None."""
    if 0x3041 <= code <= 0x3096:
        return "small hiragana" if code in SMALL_KANA else "hiragana"
    if 0x30A1 <= code <= 0x30FA:
        return "small katakana" if code in SMALL_KANA else "katakana"
    if code in (0x30FC, 0x30FB, 0x309B, 0x309C):
        return "punctuation"
    if 0x3000 < code <= 0x303F or 0xFF01 <= code <= 0xFF60 or code in (0x2018, 0x2019, 0x201C, 0x201D):
        return "punctuation"
    if 0xAC00 <= code <= 0xD7A3:
        return "hangul"
    return None


VERTICAL_VOWELS = (0, 1, 2, 3, 4, 5, 6, 7, 20)  # a, ae, ya, yae, eo, e, yeo, ye, i: beside the initial
HORIZONTAL_VOWELS = (8, 12, 13, 17, 18)  # o, yo, u, yu, eu: under it; the others are both


def hangul_shape(code):
    """A Hangul syllable's shape: its vowel beside its initial ("vertical": 가), under it
    ("horizontal": 고), or both ("mixed": 과), with " final" for a final consonant (각)."""
    index = code - 0xAC00
    vowel, final = (index % 588) // 28, index % 28
    shape = "vertical" if vowel in VERTICAL_VOWELS else "horizontal" if vowel in HORIZONTAL_VOWELS else "mixed"
    return shape + (" final" if final else "")


def unichr_(code):
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def load_model(path=None, name=MODEL_FILE):
    """The CJK fonts' trims (palt_model.json beside this script), or another model there, or {}."""
    import io
    import json
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), name)
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if data.get("format") == 1 else {}
    except (IOError, OSError, ValueError):
        return {}


class Trim(object):
    """A glyph's palt (and halt) adjustment: x placement and x advance, in font units."""

    def __init__(self, code, name, kind, advance, left, right):
        self.code, self.name, self.kind = code, name, kind
        self.advance, self.left, self.right = advance, left, right  # its ink's left and right edges
        self.palt = None  # (x placement, x advance) or None
        self.halt = None
        self.checked = True

    @property
    def char(self):
        return unichr_(self.code)

    def width_after(self):
        return self.advance + (self.palt[1] if self.palt else 0)


def suggest(trim, model, upm, tolerance=TOLERANCE_UNITS):
    """The trim's palt and halt adjustments, by the model: its ink kept, its sidebearings the corpus's
    (the mark's own where the corpus has it, else its kind's). A glyph that is not full width, or whose
    trim is within the tolerance, gets none."""
    if trim.advance < FULL_WIDTH_SHARE * upm or trim.right <= trim.left:
        return trim
    sides = model.get("palt", {}).get(u"U+%04X" % trim.code) or model.get("palt", {}).get(trim.kind)
    if sides:
        placement = int(round(sides[0] * upm - trim.left))
        advance = int(round((trim.right - trim.left) + (sides[0] + sides[1]) * upm - trim.advance))
        if abs(placement) >= tolerance or abs(advance + placement) >= tolerance:
            trim.palt = (placement, advance)
    half = model.get("halt", {}).get(u"U+%04X" % trim.code)
    if half and trim.kind == "punctuation":
        trim.halt = (int(round(half[0] * upm)), int(round(half[1] * upm)))
    return trim


def plan(glyphs, model, upm):
    """Trims for the font's glyphs: glyphs [(code, name, advance, ink left, ink right)]."""
    trims, seen = [], set()
    for code, name, advance, left, right in sorted(glyphs):
        kind = kind_of(code)
        if kind not in KINDS or name in seen:
            continue
        seen.add(name)
        trim = suggest(Trim(code, name, kind, advance, left, right), model, upm)
        if trim.palt or trim.halt:
            trims.append(trim)
    return trims


class HangulChange(object):
    """A Hangul syllable set anew: its outline moved by shift, its width made advance."""

    def __init__(self, code, name, shape, shift, advance, old_advance):
        self.code, self.name, self.shape = code, name, shape
        self.shift, self.advance, self.old_advance = shift, advance, old_advance


def half_up(value):
    """Rounded half up, as both Pythons do it alike (Python 3's round goes to the even number)."""
    import math
    return int(math.floor(value + 0.5))


def hangul_change(code, name, advance, left, right, mode, model, upm, width=None):
    """A syllable's change for a mode ("fixed": one width, its ink centered; "proportional": the
    corpus's sidebearings for its shape), or None when it stays within the tolerance."""
    shape = hangul_shape(code)
    ink = right - left
    if mode == "fixed":
        new_advance = half_up(width if width else (model.get("fixed_width") or 0.9) * upm)
        new_left = (new_advance - ink) / 2.0
    elif mode == "proportional":
        sides = model.get("proportional", {}).get(shape)
        if not sides:
            return None
        new_left = sides[0] * upm
        new_advance = ink + (sides[0] + sides[1]) * upm
    else:
        return None
    shift = half_up(new_left - left)
    new_advance = half_up(new_advance)
    if abs(shift) < HANGUL_TOLERANCE and abs(new_advance - advance) < HANGUL_TOLERANCE:
        return None
    return HangulChange(code, name, shape, shift, new_advance, advance)


def value_rule(name, value):
    return u"pos %s <%d 0 %d 0>;" % (name, value[0], value[1])


def feature_text(tag, old, rules):
    """A feature's code with FreeLab's block of rules in place before its closing line: an older
    FreeLab block taken out, the rest kept, FontLab's automatic block handed back ("#/> feature")."""
    begin, end = BEGIN % tag, END % tag
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
        if stripped.startswith(FONTLAB_AUTO):
            line = line.replace(FONTLAB_AUTO, FONTLAB_HANDED, 1)
        kept.append(line)
    closing = None
    for index in range(len(kept) - 1, -1, -1):
        if re.match(r"^\s*}\s*%s\s*;" % re.escape(tag), kept[index]):
            closing = index
            break
    if closing is None:
        kept = [u"feature %s {" % tag, u"# %s" % FEATURE_TITLES.get(tag, tag), u""]
        closing = len(kept)
        kept.append(u"} %s;" % tag)
    block = [begin] + [u"  %s" % rule for rule in rules] + [end] if rules else []
    return u"\n".join(kept[:closing] + block + kept[closing:]) + u"\n"


def expand_ranges(text):
    """The glyph names of a class's members, a range among them (uni3041-uni3045, or cid00010-cid00012:
    the same name with a number counting up, as the feature syntax allows) spelled out."""
    import re
    names = []
    for token in text.split():
        match = re.match(u"^(uni|u)([0-9A-Fa-f]{4,6})-(uni|u)([0-9A-Fa-f]{4,6})$", token) or             re.match(u"^(.*?)([0-9]+)-(.*?)([0-9]+)$", token)
        if match and match.group(1) == match.group(3) and not token.startswith(u"@"):
            prefix, first, last = match.group(1), match.group(2), match.group(4)
            base = 16 if prefix in (u"uni", u"u") and match.re.pattern.startswith(u"^(uni") else 10
            try:
                start, end = int(first, base), int(last, base)
            except ValueError:
                names.append(token)
                continue
            if 0 <= end - start <= 5000 and len(first) == len(last):
                form = (u"%%0%dX" if base == 16 else u"%%0%dd") % len(first)
                names.extend(prefix + form % number for number in range(start, end + 1))
                continue
        names.append(token)
    return names


def font_positioned(tag, text):
    """The glyphs a feature's own code (outside FreeLab's block) positions one by one (pos a-hira <...>;
    pos [a b] <...>; position, enum pos; a class defined in that code, @KANA = [...];, by its glyphs):
    FreeLab's rules for them would be a second value, which the compiler refuses ("Duplicate single
    positioning glyph with different values"). A class defined elsewhere (the font's classes) is not read."""
    import re
    begin, end = BEGIN % tag, END % tag
    classes = {}
    for match in re.finditer(u"(@[A-Za-z0-9_.\\-]+)\\s*=\\s*\\[([^\\]]*)\\]", re.sub(u"#[^\\n]*", u"", text or u"")):
        classes[match.group(1)] = expand_ranges(match.group(2))

    def members(name, depth=0):
        if not name.startswith(u"@"):
            return [name]
        if depth > 8:
            return []
        return [g for part in classes.get(name, []) for g in members(part, depth + 1)]
    found, inside = set(), False
    for line in (text or u"").splitlines():
        stripped = line.split(u"#")[0].strip() if line.strip() not in (begin, end) else line.strip()
        if line.strip() == begin:
            inside = True
            continue
        if line.strip() == end:
            inside = False
            continue
        if inside:
            continue
        match = re.match(u"(?:enum\\s+)?(?:pos|position)\\s+(\\[[^\\]]*\\]|[^\\s\\[<]+)\\s*(.*)$", stripped)
        if not match or not match.group(2).startswith(u"<"):
            continue  # (a pair or a contextual rule: its glyphs keep their single values)
        target = expand_ranges(match.group(1).strip(u"[]"))
        found.update(glyph for name in target for glyph in members(name))
    return found


def texts_for(trims, old_texts, palt_on=True, halt_on=True, kept=None):
    """{tag: new code} for palt and halt from the checked trims. Glyphs the feature's own code positions
    already keep it (no second value); kept, when given, gets {tag: [their names]}."""
    chosen = [t for t in trims if t.checked]
    new = {}
    for tag, on, value in (("palt", palt_on, lambda t: t.palt), ("halt", halt_on, lambda t: t.halt)):
        own = font_positioned(tag, old_texts.get(tag))
        if kept is not None and on:
            kept[tag] = [t.name for t in chosen if value(t) and t.name in own]
        rules = [value_rule(t.name, value(t)) for t in chosen if value(t) and t.name not in own] if on else []
        old = old_texts.get(tag)
        if rules or (BEGIN % tag) in (old or u""):  # (an empty feature is not made; an old block is taken out)
            new[tag] = feature_text(tag, old, rules)
    return new


def block_of(tag, text):
    """FreeLab's block of a feature, alone in a feature of its own (for the parser's check), or None."""
    begin, end = BEGIN % tag, END % tag
    lines = (text or u"").splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == begin]
    ends = [i for i, line in enumerate(lines) if line.strip() == end]
    if not starts or not ends:
        return None
    return u"\n".join([u"feature %s {" % tag] + lines[starts[0] + 1:ends[0]] + [u"} %s;" % tag]) + u"\n"


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

AUTO_KERNING_FILE, AUTO_KERNING_MODULE = "freelab_auto_kerning.py", "freelab_auto_kerning"
ICON_SIZE = 32
PREVIEW_EM = 44  # pixels per em, the sample's previews


def load_auto_kerning():
    """Auto Kerning beside this script, as a module: the dialogs' shared helpers."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, AUTO_KERNING_FILE)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(AUTO_KERNING_MODULE)
    if held is not None and hasattr(held, "load_sibling") and getattr(held, "_freelab_stamp", None) == stamp:
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


def hangul_note(count, where, bold=lambda text: text):
    """The status line's sentence about the font's Hangul syllables (count of them; where: the setting
    to look under, as shown; bold: how the count is set off), u"" for a font without any. It follows
    the count: "1 Hangul syllable ... its width", "2 Hangul syllables ... their widths"."""
    if not count:
        return u""
    return (u" Its %s: none of the corpus's Korean fonts kerns or trims Hangul; choose how to set %s under %s." % (
        bold(counted(count, u"Hangul syllable")), u"its width" if count == 1 else u"their widths", where))


HELP = u"""<b>FreeLab CJK Spacing</b><br>
Writes palt (proportional widths) and halt (half widths) for the font's full-width kana and
punctuation, so that applications can set Japanese proportionally. Nothing is written until you
click <i>Write the code</i>.<br><br>
<b>The list</b>: each full-width kana and punctuation mark, grouped, with its trim: how far its ink
moves (x placement) and how much its width changes (x advance), trimmed to its ink and the
sidebearings the open-licensed CJK fonts give theirs (about 0.07 em on each side for kana; each
punctuation mark its own: a comma keeps its left, an opening bracket its right). Checked glyphs are
written.<br>
<b>The previews</b>: the sample text set as it is, and with palt, in the font's glyphs, in as many
lines as the window's width needs: the Iroha (every kana once), a Hangul pangram, or the opening of the
Thousand Character Classic in Simplified or Traditional Chinese, each with full-width punctuation.
Type your own sample.<br>
<b>Hangul</b> stays out of palt, as the corpus's Korean fonts leave it: <i>Hangul:</i> sets the
syllables' widths instead (one width for all, or each by its shape), in every master.<br>
<i>Restore suggestions</i> puts every check back as the list first came.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""


class CJKSpacingDialog(object):
    COLUMNS = ("Glyph", "Name", "Width", "palt", "Width after", "halt")

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        ak = self.ak = load_auto_kerning()
        main = ak.AutoKerningDialog.main_window()
        dialog = self.dialog = QtGui.QDialog(main) if main is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab CJK Spacing")
        dialog.setWhatsThis(HELP)
        self.ak.size_dialog(dialog)
        layout = QtGui.QVBoxLayout(dialog)
        self.status = ak.status_label()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(ak.separator())
        self.log = ak.Log()
        row = QtGui.QHBoxLayout()
        self.palt_box = QtGui.QCheckBox("Proportional widths (palt)")
        self.palt_box.setChecked(True)
        self.palt_box.setWhatsThis(u"Writes palt: kana and punctuation trimmed to their ink and the corpus's sidebearings.")
        self.halt_box = QtGui.QCheckBox("Half-width punctuation (halt)")
        self.halt_box.setChecked(True)
        self.halt_box.setWhatsThis(u"Writes halt: each punctuation mark set in half the em, as the corpus's fonts set it.")
        row.addWidget(self.palt_box)
        row.addWidget(self.halt_box)
        row.addWidget(QtGui.QLabel(u"Hangul:"))
        self.hangul_box = QtGui.QComboBox()
        for _, label in HANGUL_MODES:
            self.hangul_box.addItem(label)
        self.hangul_box.setWhatsThis(u"How the font's Hangul syllables are set: as they are; all at one width (the font's "
                                     u"own where its syllables share one, else the corpus's 0.9 em), each one's ink "
                                     u"centered; or proportionally, each with the sidebearings the corpus's proportional "
                                     u"Korean fonts give its shape. Their outlines move and their widths change, in every "
                                     u"master.")
        row.addWidget(self.hangul_box)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
        self.tree.setProperty(ak.LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        ak.grid_lines(self.tree)
        self.tree.setWhatsThis(u"Each full-width kana and punctuation mark with its trims: palt's x placement and x "
                               u"advance, the width after, and halt's. Checked glyphs are written. Double-click one "
                               u"to see it in a <i>Glyph</i> window.")
        layout.addWidget(self.tree, 1)
        sample_row = QtGui.QHBoxLayout()
        self.sample_label = QtGui.QLabel(u"Sample:")
        sample_row.addWidget(self.sample_label)
        self.sample_box = QtGui.QComboBox()
        for _, label, _ in SAMPLES:
            self.sample_box.addItem(label)
        self.sample_box.setWhatsThis(u"A sample per writing system (the one the font covers best is chosen as it is "
                                     u"read); the field beside it takes text of your own.")
        sample_row.addWidget(self.sample_box)
        self.sample = QtGui.QLineEdit(SAMPLE)
        self.sample.setWhatsThis(u"The text the previews set, as it is and with palt, in as many lines as the window's "
                                 u"width needs: the Iroha (every kana once), a Hangul pangram, or the opening of the "
                                 u"Thousand Character Classic, each with full-width punctuation; or text of your own.")
        sample_row.addWidget(self.sample, 1)
        layout.addLayout(sample_row)
        self.previews, self.preview_captions = [], []
        for number, caption in enumerate((u"Now", u"With palt")):
            if number:
                layout.addWidget(ak.separator())
            title = QtGui.QLabel(caption)
            quiet = QtGui.QFont(title.font)
            quiet.setPointSizeF(quiet.pointSizeF() * 0.9)
            title.setFont(quiet)
            title.setEnabled(False)  # (drawn in the quiet text color)
            layout.addWidget(title)
            self.preview_captions.append(title)
            label = QtGui.QLabel()
            label.setProperty(ak.LEAVE_ALONE_PROP, True)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumHeight(int(PREVIEW_EM * 1.9))
            try:  # its picture never holds the window wider: the sample is broken into lines to fit it
                label.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Preferred)
            except Exception:
                pass
            label.setToolTip(caption)
            layout.addWidget(label)
            self.previews.append((label, caption))
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Check all")
        self.none_button = QtGui.QPushButton("Check none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis(u"Puts every check back as the list first came.")
        self.write_button = QtGui.QPushButton("Write the code")
        self.write_button.setWhatsThis(u"Writes palt and halt for the checked glyphs, between FreeLab's marker lines; the "
                                       u"rest of each feature is kept. <i>Edit &gt; Undo</i> takes it back.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.compile_box = ak.compile_box()
        buttons.addWidget(self.compile_box)
        buttons.addWidget(self.write_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.write_button.connect("clicked()", self.write)
        self.close_button.connect("clicked()", dialog.close)
        self.palt_box.connect("toggled(bool)", lambda on: self.toggled())
        self.halt_box.connect("toggled(bool)", lambda on: self.toggled())
        self.sample.connect("textChanged(QString)", lambda text: self.draw_previews())
        self.sample_box.connect("activated(int)", lambda index: self.sample.setText(SAMPLES[index][2]))
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.changed())
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", lambda item, column: self.show_in_glyph_window(item))
        self.package = None
        self.trims, self.first_checks, self.texts, self.names = [], [], {}, []
        self.seen_history, self.busy, self.buttons_due = None, False, False
        self.model = load_model()
        self.hangul_model = load_model(name=HANGUL_MODEL_FILE)
        self.hangul_glyphs, self.hangul, self.hangul_checks, self.hangul_width = [], [], {}, None
        self.hangul_box.connect("currentIndexChanged(int)", lambda index: self.plan_hangul())
        ak.add_tools_button(dialog, "CJK Spacing", getattr(self, "log", None))  # (the other font tools, a click away)
        ak.plain_buttons(dialog)
        self.history_timer = ak.watch_history(self)
        self.flagging = ak.flag_menu(self.tree, self, self.flag_names, self.row_names)
        self.preview_width, self.watchers = None, []
        self.watch_previews()
        try:  # the check boxes drawn plain to see in either palette (the list's pictures stay unmapped)
            fc = ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
            self.watchers.append(fc.watch_check_boxes(self.dialog, [self.tree]))
        except Exception:
            pass

    def watch_previews(self):
        """The previews set again when their width changes (their lines break to fit it)."""
        QtCore, QtGui = _qt()
        owner = self

        class Watcher(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    if event.type() == 14:  # Resize
                        owner.redraw_timer.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        try:
            self.redraw_timer = QtCore.QTimer()
            self.redraw_timer.setSingleShot(True)
            self.redraw_timer.setInterval(80)
            self.redraw_timer.connect("timeout()", self.previews_resized)
            watcher = Watcher()
            self.previews[0][0].installEventFilter(watcher)
            self.watchers.append(watcher)
        except Exception:
            pass

    def previews_resized(self):
        if self.preview_room() != self.preview_width:
            self.draw_previews()

    def flag_names(self):
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items:
            return []
        return self.row_names(items[0])

    def row_names(self, item):
        QtCore, QtGui = _qt()
        data = item.data(0, QtCore.Qt.UserRole)
        index = int(data) if data is not None else -1
        return [self.trims[index].name] if 0 <= index < len(self.trims) else []

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

    def run(self):
        QtCore, QtGui = _qt()
        ak = self.ak
        kept = dict((t.name, t.checked) for t in self.trims)
        self.tree.blockSignals(True)
        self.tree.clear()
        self.tree.blockSignals(False)
        self.trims = []
        package = self.package = self.current_font()
        self.show_font_parts(package is not None)
        if package is None:
            self.status.setText(ak.NO_FONT_LINE)
            self.update_buttons()
            return
        if not self.model:
            self.status.setText(u"")
            self.log.add(u"The corpus's trims (palt_model.json) are missing beside this script: reinstall FreeLab.", "error")
            return
        master = package.master
        glyphs, hangul = [], 0
        self.hangul_glyphs = []
        for fg in package.fgPackage.glyphs:
            code = fg.unicode
            kind = kind_of(code) if code else None
            if kind == "hangul":
                hangul += 1
                self.hangul_glyphs.append((code, fg.name))
            if kind not in KINDS:
                continue
            glyph = package.findName(fg.name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() <= 0:
                continue
            glyphs.append((code, fg.name, layer.advanceWidth, box.left(), box.right()))
        self.names = [g.name for g in package.fgPackage.glyphs]
        features = package.fgPackage.features
        self.texts = dict((tag, features.get_feature(tag)) for tag in features.keys())
        self.trims = plan(glyphs, self.model, float(package.upm))
        for t in self.trims:
            t.checked = kept.get(t.name, t.checked)
        if u"%s" % self.sample.text in [text for _, _, text in SAMPLES]:  # (text of one's own is kept)
            index = best_sample(set(fg.unicode for fg in package.fgPackage.glyphs if fg.unicode))
            self.sample_box.setCurrentIndex(index)
            self.sample.setText(SAMPLES[index][2])
        self.note_font(package)
        self.hangul_box.setEnabled(bool(hangul))
        self.hangul = []
        if hangul and HANGUL_MODES[self.hangul_box.currentIndex][0] != "leave":
            self.measure_hangul()
        self.fill()
        self.first_checks = [True for _ in self.trims]
        self.update_buttons()  # (fill compared the checks with the last font's)
        b = ak.b
        full = sum(1 for g in glyphs if g[2] >= FULL_WIDTH_SHARE * package.upm)
        korean = hangul_note(hangul, ak.i(u"Hangul:"), b)
        if not full:
            self.status.setText(u"%s, master %s, has no full-width kana or CJK punctuation: nothing to trim.%s" % (
                b(package.tfn), b(master), korean))
        else:
            self.status.setText(u"%s, master %s: %s of the %s full-width kana and punctuation %s a trim (palt: %s, halt: "
                                u"%s). Nothing is written until you click %s.%s" % (
                                    b(package.tfn), b(master), b(len(self.trims)), b(full),
                                    u"gets" if len(self.trims) == 1 else u"get",
                                    b(sum(1 for t in self.trims if t.palt)), b(sum(1 for t in self.trims if t.halt)),
                                    ak.i(self.write_button.text), korean))
        self.seen_history = ak.history_mark(package)
        self.draw_previews()

    # -- Hangul -----------------------------------------------------------------------

    def hangul_mode(self):
        return HANGUL_MODES[self.hangul_box.currentIndex][0]

    def measure_hangul(self, master=None):
        """The changes the chosen Hangul mode makes to the master's syllables (and the width it sets)."""
        QtCore, QtGui = _qt()
        package = self.package
        master = master or package.master
        mode = self.hangul_mode()
        upm = float(package.upm)
        measured = []
        for count, (code, name) in enumerate(self.hangul_glyphs):
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is None:
                continue
            box = layer.boundingBox
            if box.width() > 0:
                measured.append((code, name, layer.advanceWidth, box.left(), box.right()))
            if count % 1000 == 999:
                self.status.setText(u"Measuring Hangul: %s of %s\N{HORIZONTAL ELLIPSIS}" % (
                    self.ak.b(count + 1), self.ak.b(len(self.hangul_glyphs))))
                QtGui.QApplication.processEvents()
        widths = sorted(set(int(round(m[2])) for m in measured))
        width = None
        if mode == "fixed":
            width = widths[len(widths) // 2] if 0 < len(widths) <= 3 else (self.hangul_model.get("fixed_width") or 0.9) * upm
        self.hangul_width = width
        changes = [hangul_change(code, name, advance, left, right, mode, self.hangul_model, upm, width)
                   for code, name, advance, left, right in measured]
        changes = [c for c in changes if c is not None]
        if master == package.master:
            self.hangul = changes
        return changes

    def plan_hangul(self):
        if self.package is None:
            return
        self.hangul = []
        if self.hangul_glyphs and self.hangul_mode() != "leave":
            self.measure_hangul()
            self.log.add(u"Hangul, %s: %s would change%s." % (
                self.ak.html(HANGUL_MODES[self.hangul_box.currentIndex][1].lower()),
                self.ak.b(counted(len(self.hangul), u"syllable")),
                u" (one width: %s)" % counted(self.hangul_width, u"unit") if self.hangul_width else u""))
        self.fill()
        self.draw_previews()

    def toggled(self):
        """palt or halt switched: the list shows what is written now (counts, columns), the previews too."""
        try:
            self.harvest()
            self.fill()
            self.draw_previews()
        except Exception as exc:
            self.log.add(u"Could not show the change: %s" % self.ak.html(exc), "error")
        self.update_buttons()

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        self.tree.clear()
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        palt_on, halt_on = self.palt_box.checked, self.halt_box.checked
        try:
            dimmed = QtGui.QBrush(self.dialog.palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text))
        except Exception:
            dimmed = None
        for kind in KINDS:
            members = [(index, t) for index, t in enumerate(self.trims) if t.kind == kind]
            if not members:
                continue
            written = sum(1 for _, t in members if (t.palt and palt_on) or (t.halt and halt_on))
            off = [tag for tag, on in ((u"palt", palt_on), (u"halt", halt_on)) if not on]
            heading = u"%s (%d)" % (KIND_LABELS[kind], len(members)) if not off else u"%s (%d of %d trimmed: %s off)" % (
                KIND_LABELS[kind], written, len(members), u" and ".join(off))
            top = QtGui.QTreeWidgetItem([heading])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for index, t in members:
                item = QtGui.QTreeWidgetItem([t.char, t.name, u"%d" % t.advance,
                                              u"%+d, %+d" % t.palt if t.palt else u"\N{EN DASH}",
                                              u"%d" % t.width_after(),
                                              u"%+d, %+d" % t.halt if t.halt else u"\N{EN DASH}"])
                item.setData(0, QtCore.Qt.UserRole, index)
                item.setFont(0, bold)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if t.checked else QtCore.Qt.Unchecked)
                item.setToolTip(3, u"x placement, x advance: the ink moves by the first, the width changes by the second.")
                for column in range(2, len(self.COLUMNS)):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                if dimmed is not None:  # what is not written, as off
                    for column in ((3, 4) if not palt_on else ()) + ((5,) if not halt_on else ()):
                        item.setForeground(column, dimmed)
                icon = self.picture([(t.name, 0, 0)], ICON_SIZE)
                if icon is not None:
                    item.setIcon(0, QtGui.QIcon(icon))
                top.addChild(item)
            top.setExpanded(True)
        if self.hangul:
            top = QtGui.QTreeWidgetItem([u"Hangul (%s)" % counted(len(self.hangul), u"syllable")])
            top.setData(0, QtCore.Qt.UserRole, -1)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            self.ak.section_row(top, self.tree)
            for number, (shape, label) in enumerate(HANGUL_SHAPES):
                members = [c for c in self.hangul if c.shape == shape]
                if not members:
                    continue
                middle = lambda values: sorted(values)[len(values) // 2]
                item = QtGui.QTreeWidgetItem([label, counted(len(members), u"syllable"),
                                              u"%d" % middle([c.old_advance for c in members]),
                                              u"moved %+d" % middle([c.shift for c in members]),
                                              u"%d" % middle([c.advance for c in members]), u""])
                item.setData(0, QtCore.Qt.UserRole, -10 - number)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.Checked if self.hangul_checks.get(shape, True) else QtCore.Qt.Unchecked)
                item.setToolTip(3, u"The median move of their outlines, and (next) their median width after.")
                for column in range(2, len(self.COLUMNS)):
                    item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                top.addChild(item)
            top.setExpanded(True)
        for column in range(len(self.COLUMNS)):
            self.tree.resizeColumnToContents(column)
        self.tree.blockSignals(False)
        self.update_buttons()

    def items(self):
        found = []
        for row in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(row)
            for child in range(top.childCount()):
                found.append(top.child(child))
        return found

    def harvest(self):
        QtCore, QtGui = _qt()
        for item in self.items():
            index = int(item.data(0, QtCore.Qt.UserRole))
            if 0 <= index < len(self.trims):
                self.trims[index].checked = item.checkState(0) == QtCore.Qt.Checked
            elif index <= -10:
                self.hangul_checks[HANGUL_SHAPES[-10 - index][0]] = item.checkState(0) == QtCore.Qt.Checked

    def hangul_chosen(self):
        return [c for c in self.hangul if self.hangul_checks.get(c.shape, True)]

    def check_all(self, on):
        QtCore, QtGui = _qt()
        self.tree.blockSignals(True)
        for item in self.items():
            item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        self.tree.blockSignals(False)
        self.changed()

    def changed(self):
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        QtCore, QtGui = _qt()
        self.buttons_due = False
        ak = self.ak
        self.harvest()
        checks = [t.checked for t in self.trims]
        ak.enable(self.all_button, not all(checks) if checks else False)
        ak.enable(self.none_button, any(checks))
        ak.enable(self.restore_button, checks != self.first_checks)
        new = texts_for(self.trims, self.texts, self.palt_box.checked, self.halt_box.checked) if self.package else {}
        present = any((BEGIN % tag) in (self.texts.get(tag) or u"") for tag in ("palt", "halt"))
        changes = any(new[tag] != self.texts.get(tag) for tag in new)
        widths = bool(self.hangul_chosen())
        what = (u"Update the code" if present else u"Write the code") if changes else u""
        self.write_button.setText(u"%s and Hangul widths" % what if what and widths else what or
                                  (u"Set Hangul widths" if widths else u"Write the code"))
        ak.enable(self.write_button, changes or widths)
        self.draw_previews()

    def restore(self):
        for t, on in zip(self.trims, self.first_checks):
            t.checked = on
        self.fill()
        self.log.add(u"Checks restored as suggested.")

    def history_moved(self):
        self.log.add(u"The font's History moved (an undo, a redo, or an edit): read again.")
        self.run()

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick):
        read anew, or the list emptied and the no-font line shown."""
        self.run()

    def show_font_parts(self, on):
        """With no font open, what has nothing to act on is hidden (the sample and its previews) or
        grayed out (the features to write, the Hangul setting, compiling)."""
        for widget in [self.sample_label, self.sample_box, self.sample] + list(self.preview_captions):
            widget.setVisible(on)
        for label, _ in self.previews:
            label.setVisible(on)
        for widget in (self.palt_box, self.halt_box, self.compile_box):
            self.ak.enable(widget, on)
        if not on:
            self.ak.enable(self.hangul_box, False)  # (a font's Hangul sets it again as it is read)

    # -- pictures ------------------------------------------------------------------

    def layer_of(self, name):
        glyph = self.package.findName(name)
        return glyph.getLayerByName(self.package.master) if glyph is not None and not glyph.isNull else None

    def picture(self, placed, size, rows=None):
        """Glyphs [(name, x placement, x advance change)] set in a row (or rows: lists of them, one line
        each, under one another), in the dialog's text color."""
        QtCore, QtGui = _qt()
        lines = []
        for row in (rows if rows is not None else [placed]):
            layers = []
            for item in row:
                layer = self.layer_of(item[0])
                if layer is not None:
                    layers.append((layer, item[1], item[2]))
            lines.append(layers)
        if not any(lines):
            return None
        upm = float(self.package.upm)
        scale = size / upm
        total = max(sum(layer.advanceWidth + advance for layer, _, advance in layers) for layers in lines)
        step = size * 1.25
        pixmap = QtGui.QPixmap(max(int(total * scale) + 8, 4), int(step * len(lines)))
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        painter = QtGui.QPainter(pixmap)
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            for number, layers in enumerate(lines):
                x = 4.0
                for layer, placement, advance in layers:
                    painter.save()
                    painter.translate(x + placement * scale, size * 1.0 + step * number)
                    painter.scale(scale, -scale)
                    self.ak.fill_glyph(painter, self.ak.layer_path(layer), QtGui.QBrush(color), self.ak.layer_parts(layer))
                    painter.restore()
                    x += (layer.advanceWidth + advance) * scale
        finally:
            painter.end()
        return pixmap

    def note_font(self, package):
        """Said once per font and sample: a color font's glyphs, and a sample that shows none of the
        font's CJK characters (its preview stays empty)."""
        key = (self.ak.font_key(package), u"%s" % self.sample.text)
        if key == getattr(self, "noted_font", None):
            return
        first = getattr(self, "noted_font", (None,))[0] != key[0]
        self.noted_font = key
        note = self.ak.color_note(package) if first else u""
        if note:
            self.log.add(note)
        codes = set(fg.unicode for fg in package.fgPackage.glyphs if fg.unicode)
        missed = sample_misses(codes, u"%s" % self.sample.text)
        if missed:
            shown = u" ".join(missed[:12]) + (u" …" if len(missed) > 12 else u"")
            self.log.add(u"The sample shows none of the font's %s (%s): type text of your own with them in the "
                         u"%s field to see them set." % (
                             self.ak.b(counted_chars(len(missed))), self.ak.html(shown), self.ak.i(u"Sample")),
                         "warning")

    def preview_room(self):
        """The previews' width in pixels, for their lines (None where Qt does not say)."""
        try:
            width = int(self.ak._property(self.previews[0][0], "width"))
            return width - 12 if width > 2 * PREVIEW_EM else None
        except Exception:
            return None

    def draw_previews(self):
        if self.package is None:
            return
        by_code = dict((t.code, t) for t in self.trims if t.checked and t.palt)
        by_code.update((c.code, c) for c in self.hangul_chosen())
        names = dict((g.unicode, g.name) for g in self.package.fgPackage.glyphs if g.unicode)
        text = u"%s" % self.sample.text
        room = self.preview_width = self.preview_room()
        upm = float(self.package.upm) or 1000.0
        advances = {}
        palt_on = self.palt_box.checked
        try:
            self.preview_captions[1].setText(u"With palt" if palt_on else u"With palt (off: palt is not written)")
        except Exception:
            pass
        for index, (label, caption) in enumerate(self.previews):
            placed, chars, widths = [], [], []
            for ch in text:
                name = names.get(ord(ch))
                if name is None:
                    continue
                trim = by_code.get(ord(ch)) if index == 1 else None
                if trim is not None and not palt_on and not isinstance(trim, HangulChange):
                    trim = None  # (palt not written; Hangul widths are)
                if isinstance(trim, HangulChange):
                    placed.append((name, trim.shift, trim.advance - trim.old_advance))
                else:
                    placed.append((name, trim.palt[0], trim.palt[1]) if trim else (name, 0, 0))
                if name not in advances:
                    layer = self.layer_of(name)
                    advances[name] = layer.advanceWidth if layer is not None else 0
                chars.append(ch)
                widths.append((advances[name] + placed[-1][2]) * PREVIEW_EM / upm)
            rows = [placed[start:end] for start, end in break_lines(chars, widths, room)] if room else None
            pixmap = self.picture(placed, PREVIEW_EM, rows) if placed else None
            if pixmap is None:
                label.clear()
            else:
                label.setPixmap(pixmap)
                try:  # as tall as its lines
                    label.setMinimumHeight(max(int(PREVIEW_EM * 1.9), int(pixmap.height()) + 8))
                except Exception:
                    pass

    def show_in_glyph_window(self, item):
        QtCore, QtGui = _qt()
        index = int(item.data(0, QtCore.Qt.UserRole))
        if not 0 <= index < len(self.trims):
            return
        name = self.trims[index].name
        error = self.ak.show_in_glyph_window(self.fontlab, u"/%s/%s/%s" % (name, name, name))
        if error:
            self.log.add(u"FontLab did not open the glyph: %s" % self.ak.html(error), "error")

    # -- writing --------------------------------------------------------------------

    def write(self):
        if self.package is None:
            return
        self.harvest()
        package = self.package
        current = self.current_font()
        if current is None or self.ak.font_key(current) != self.ak.font_key(package):
            self.run()
            self.log.add(u"The font changed: here is this one's list. Nothing was written.", "warning")
            return
        features = package.fgPackage.features
        kept = {}
        new = texts_for(self.trims, self.texts, self.palt_box.checked, self.halt_box.checked, kept)
        for tag, names in sorted(kept.items()):
            if names:
                self.log.add(u"%s %s positioned by the font's own %s code already: %s %s it, not FreeLab's trim "
                             u"(two values for one glyph do not compile): %s." % (
                                 self.ak.b(counted(len(names), u"glyph")), u"is" if len(names) == 1 else u"are", tag,
                                 u"it keeps" if len(names) == 1 else u"they keep", tag,
                                 self.ak.html(u" ".join(names[:30]) + (u" \N{HORIZONTAL ELLIPSIS}" if len(names) > 30 else u""))),
                             "warning")
        fc = None
        try:
            fc = self.ak.load_sibling("freelab_feature_code.py", "freelab_feature_code")
        except Exception:
            pass
        problems = []
        for tag, text in new.items():
            block = block_of(tag, text)
            problem = fc.check_code(block, self.names) if (fc is not None and block) else None
            if problem:
                problems.append(u"%s: %s" % (tag, problem))
        if problems:
            self.log.add(u"The code has problems, so nothing was written: %s" % self.ak.html(u"; ".join(problems)), "error")
            return
        written, error, syllables = [], None, 0
        shapes = set(c.shape for c in self.hangul_chosen())
        self.ak.before_changes(self.fontlab, package, u"FreeLab CJK Spacing")
        try:
            for tag in ("palt", "halt"):
                if tag in new and new[tag] != self.texts.get(tag):
                    features.set_feature(tag, new[tag])
                    written.append(tag)
            if shapes:
                syllables = self.write_hangul(package, shapes)
        except Exception as exc:
            error = exc
        self.ak.notify_changed(self.fontlab, package, u"FreeLab CJK Spacing")
        self.run()
        if written:
            them = u"it" if len(written) == 1 else u"them"
            self.log.add(u"Wrote %s; <i>Edit &gt; Undo</i> takes %s back.%s" % (
                self.ak.b(u" and ".join(written)), them, self.ak.compiled_note(self.compile_box, self.log)), "done")
        if syllables:
            self.log.add(u"Set %s in every master; the font's kerning of Hangul, if any, was set for the old widths. "
                         u"<i>Edit &gt; Undo</i> takes it back." % self.ak.b(counted(syllables, u"syllable width", u"syllable widths")),
                         "done")
        if not written and not syllables:
            self.log.add(u"Wrote nothing.")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % self.ak.html(error), "error")

    def write_hangul(self, package, shapes):
        """Each chosen syllable set anew in every master (each measured on its own): its shapes moved
        (components and outlines alike, by their transforms) and its width changed. How many changed."""
        QtCore, QtGui = _qt()
        done = 0
        for master in list(package.masters) or [package.master]:
            for change in self.measure_hangul(master):
                if change.shape not in shapes:
                    continue
                glyph = package.findName(change.name)
                layer = glyph.getLayerByName(master) if glyph is not None else None
                if layer is None:
                    continue
                for shape in layer.shapes:
                    t = shape.transform
                    shape.transform = QtGui.QTransform(t.m11(), t.m12(), t.m21(), t.m22(), t.dx() + change.shift, t.dy())
                layer.advanceWidth = change.advance
                try:
                    glyph.update()
                except Exception:
                    pass
                done += 1
        return done

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)


def main():
    try:  # this font's window shows it already: brought forward as it is
        if load_auto_kerning().raise_open("CJK Spacing"):
            return
    except Exception:
        pass
    try:
        dialog = CJKSpacingDialog()
    except Exception as exc:
        print("FreeLab CJK Spacing: %s" % exc)
        return
    sys._freelab_cjk_spacing = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.ak.hook_menu_order()
    try:
        dialog.ak.take_window("CJK Spacing", dialog)  # its font's window: the tool shown there gives way
    except Exception:
        pass
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_cjk_spacing":
    main()
