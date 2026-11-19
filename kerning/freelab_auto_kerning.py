#FLM: Auto Kerning
# -*- coding: utf-8 -*-
"""FreeLab auto kerning, from FontLab's Scripts menu.

Suggests kerning for the pairs of the current font's current master, one script at a time (Latin,
Cyrillic, Greek, kana as palt sets them, Armenian, Georgian, Devanagari), by two methods and FontLab's own, shows them beside the
kerning the font has and how far they agree, and writes only the pairs you approve.

- halfkern's method (https://github.com/behdad/halfkern, Copyright 2022 Google LLC, Apache License
  2.0): every glyph gets an envelope, a halo around its ink; a pair moves until the overlap of the
  two envelopes falls within a band taken from pairs the designer spaced (ll, nn, oo, and others).
- Contour distance, after Matthew Skala's description of Tsukurimashou's kerning (freetype-devel,
  June 2012): the average inverse cube of the distances between the two glyphs' facing contours,
  their angles limited, held within a band taken from the same pairs.
- FontLab's own autokern (flPackage.autoKern), asked for the listed pairs only.

Both methods are measured by FreeLab's native core (kerning/native/freelab_kern.c). The font's
existing kerning acts as a model: each method's tightenings and loosenings are scaled to match it.

Valid Python 2.7 (FontLab 7) and Python 3. The core below needs no Qt and no FontLab.
"""

from __future__ import absolute_import, division, print_function

import json
import math
import re
import time
import os
import sys

def hold_module(module):
    """A FreeLab module kept alive once a newer copy replaces it (load_sibling, a reinstall in the same
    FontLab session): Python 2.7 empties a module's globals when the module object is freed, and a window
    of the old copy still open, or closed but not yet deleted, then printed a traceback at each of its
    signals (its slots' globals all None). Every copy is kept for the session: a window may outlive any
    number of reinstalls (a bounded list let go of a copy whose window was still open; review 11), and a
    copy costs a few megabytes, reinstalls being rare."""
    if module is None:
        return
    held = getattr(sys, "_freelab_held_modules", None)
    if held is None:
        held = sys._freelab_held_modules = []
    if any(m is module for m in held):
        return
    held.append(module)


hold_module(sys.modules.get(__name__))  # (this copy: the windows it serves keep working after a reinstall)

VERSION = "0.2.0"
KERN_VERSION = 2  # FREELAB_KERN_VERSION in kerning/native/freelab_kern.c
EM_PIXELS = 200  # rendering size, pixels per em (halfkern renders at 100; finer steps here)
HALO_SHARE = 0.1  # the envelope's halo, as a share of the em (halfkern's starting kernel)
PAD_SHARE = 0.3  # room around each glyph image for the halo and the search, as a share of the em
TUNING = (u"l", u"n", u"o")  # spaced right by the designer: the halo and the lowercase band come from them
# Each kind of pair is held to the spacing the designer gave its own kind: references set with each
# other with no kerning (HH, HO, OH, OO for capitals; Hn or Oo across cases). halfkern takes one band
# from lowercase alone, which loosened straight capitals (HH, MN) the designer had spaced as wanted.
REFERENCES = {"upper": (u"H", u"O"), "lower": TUNING, "figure": (u"0", u"8")}
CONTOUR_SLOPE = 0.6  # a contour moves at most this many pixels across per row (its angle limit)
CONTOUR_FLOOR = 1.0  # gaps narrower than this many pixels count as this narrow
MIN_GAP_SHARE = 0.02  # contour distance never tightens a pair's ink closer than this share of the em
METHODS = (("halfkern", "halfkern"), ("contour", "Contour"), ("learned", "FreeLab"), ("fontlab", "FontLab"))  # "learned": FreeLab's own
MEASURED = ("halfkern", "contour", "learned")  # computed here, cached, and scaled to the font's kerning
DEFAULT_FACTORS = {"halfkern": (0.5, 1.0),  # halfkern applies half of a tightening
                   "contour": (1.0, 1.0),
                   "learned": (1.0, 1.0)}
TIGHTEN, LOOSEN = DEFAULT_FACTORS["halfkern"]
FACTOR_RANGE = (0.1, 1.5)  # a factor fitted to the font's kerning stays within this
MODELS_MIN = 3  # fewer existing pairs than this: the method's default factors
TOLERANCE_UNITS = 20  # a suggestion this close to the current value is not listed (about 2% of the em)
SHOW = (("all", "Everything"), ("letters", "Letters"), ("punctuation", "Letters and punctuation"), ("figures", "Figures"))
PAIRS = (("all", "All pairs"), ("common", "Common pairs"))
SOURCES = (("average", "Average of halfkern and Contour"), ("halfkern", "halfkern"), ("contour", "Contour"),
           ("learned", "FreeLab"), ("fontlab", "FontLab"))
ORDERS = (("change", "Largest change first"), ("agreement", "Best agreement first"), ("common", "Most common first"),
          ("alphabet", "Alphabetical"))
PREVIEW_SIZE = 64  # pixels per em in the dialog's preview
COMMON_PAIRS_FILE = "common_pairs.txt"  # beside this script
SCRIPT_PAIRS_FILE = "script_pairs.txt"  # beside it: the other scripts' pairs (kerning/train/script_pairs.py)
CACHE_VERSION = 1  # raise when the measuring changes in a way the settings below do not show
# The learned method's features: the gap between a pair's facing edges in height bands, from below
# the baseline to above the capitals (shares of the em), besides both methods' readings.
PROFILE_BANDS = 16
BAND_RANGE = (-0.25, 1.0)
GAP_CAP = 0.6  # gaps wider than this share of the em count as this wide
KIND_CODES = {"upper": 0, "lower": 1, "figure": 2, "punctuation": 3, "kana": 4}
SPACING_PAIRS = (u"nn", u"oo", u"HH")  # the font's own spacing, as features
LEARNED_MODEL_FILE = "learned_model.json"  # beside this script: trees trained by kerning/train/train.py
LETTERS = u"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
FIGURES = u"0123456789"
PUNCTUATION = u".,:;!?'\"-()[]{}/&*‘’“”«»–—"


def _characters(*ranges):
    """The characters of code point ranges (first, last), as one string (all in the BMP)."""
    found = []
    for first, last in ranges:
        for code in range(first, last + 1):
            try:
                found.append(unichr(code))  # noqa: F821 (Python 2)
            except NameError:
                found.append(chr(code))
    return u"".join(found)


# The other scripts Auto Kerning measures, one script at a time, each held to references of its own
# as Latin is to H, O, l, n, and o: a straight letter and a round one per case, set with themselves
# with no kerning. Kana are measured as palt sets them (see KANA_SETTINGS); Georgian has Mkhedruli
# (lowercase) and Mtavruli (its capitals, for all-capital text). Ranges are written out: FontLab's
# Python 2.7 knows Unicode 5.2, which has no Mtavruli and calls Mkhedruli uncased letters.
KANA_LETTERS = _characters((0x3041, 0x3096), (0x309D, 0x309E), (0x30A1, 0x30FA), (0x30FC, 0x30FE))
KANA_PUNCTUATION = (_characters((0x3001, 0x3002), (0x3008, 0x3011), (0x3014, 0x3015), (0x301C, 0x301C),
                                (0x30FB, 0x30FB), (0xFF01, 0xFF01), (0xFF08, 0xFF09), (0xFF0C, 0xFF0C),
                                (0xFF0E, 0xFF0E), (0xFF1A, 0xFF1B), (0xFF1F, 0xFF1F), (0x2025, 0x2026))
                    + u"‘’“”")
ARMENIAN_CAPITALS = _characters((0x0531, 0x0556))
ARMENIAN_LETTERS = ARMENIAN_CAPITALS + _characters((0x0561, 0x0587))
ARMENIAN_PUNCTUATION = _characters((0x055A, 0x055E), (0x0589, 0x058A)) + u",.:()«»-–—"
MTAVRULI = _characters((0x1C90, 0x1CBA), (0x1CBD, 0x1CBF))
GEORGIAN_LETTERS = _characters((0x10D0, 0x10FA), (0x10FD, 0x10FF)) + MTAVRULI
GEORGIAN_PUNCTUATION = u".,:;!?'\"-()„“”«»–—"
# Cyrillic: the letters of Russian, Ukrainian, Belarusian, Bulgarian, Serbian, and Macedonian (U+0400
# to U+045F, and Ukrainian's ghe with upturn), less the four with a grave accent (Bulgarian and
# Macedonian stress marks): letters with diacritics of other languages (Kazakh's, Tatar's) are not
# measured, as accented Latin letters are not. Greek: monotonic Greek, the vowels with tonos and
# dialytika included (most words have one). Devanagari (one case, as Mkhedruli): the consonants and the
# independent vowels; vowel signs, conjuncts, and half forms are set by the font's shaping, not by a
# glyph of their own Auto Kerning could pair.
CYRILLIC_CAPITALS = _characters((0x0401, 0x040C), (0x040E, 0x042F), (0x0490, 0x0490))
CYRILLIC_LETTERS = (CYRILLIC_CAPITALS + _characters((0x0430, 0x044F), (0x0451, 0x045C), (0x045E, 0x045F),
                                                    (0x0491, 0x0491)))
CYRILLIC_PUNCTUATION = PUNCTUATION + u"\N{DOUBLE LOW-9 QUOTATION MARK}"
GREEK_CAPITALS = _characters((0x0386, 0x0386), (0x0388, 0x038A), (0x038C, 0x038C), (0x038E, 0x038F), (0x0391, 0x03A1),
                             (0x03A3, 0x03AB))
GREEK_LETTERS = GREEK_CAPITALS + _characters((0x0390, 0x0390), (0x03AC, 0x03CE))
GREEK_PUNCTUATION = PUNCTUATION
DEVANAGARI_LETTERS = _characters((0x0905, 0x0939))  # the independent vowels A to AU, then KA to HA
DEVANAGARI_PUNCTUATION = (_characters((0x0964, 0x0965)) + u".,:;!?'\"-()"  # the danda and double danda, then Latin's
                          + _characters((0x2018, 0x2019), (0x201C, 0x201D), (0x2013, 0x2014)))  # (curly quotes, dashes)
# Right-to-left scripts, unicameral and unjoined: Hebrew (its 27 letters, the five final forms
# included; points and accents are marks, set by the font's mark positioning) and Thaana (its letters;
# its vowel signs, the fili, are marks too, so letters stand side by side as consonants do). A pair of
# them is kept as everywhere else, its left glyph on screen first (see text_order): in text, the right
# one comes first.
HEBREW_LETTERS = _characters((0x05D0, 0x05EA))
HEBREW_PUNCTUATION = (_characters((0x05BE, 0x05BE), (0x05C3, 0x05C3), (0x05F3, 0x05F4))  # maqaf, sof pasuq, geresh, gershayim
                      + u".,:;!?'\"-()[]" + _characters((0x2018, 0x2019), (0x201C, 0x201E), (0x2013, 0x2014)))
THAANA_LETTERS = _characters((0x0780, 0x07A5), (0x07B1, 0x07B1))
THAANA_PUNCTUATION = (_characters((0x060C, 0x060C), (0x061B, 0x061B), (0x061F, 0x061F))  # Arabic comma, semicolon, question mark
                      + u".:!'\"-()" + _characters((0x2018, 0x2019), (0x201C, 0x201D), (0x2013, 0x2014)))
RTL_SCRIPTS = ("hebrew", "thaana")
# Characters a right-to-left run sets with the glyph of their mirror (Unicode's Bidi_Mirrored, as
# HarfBuzz and every text engine apply it): typed "(", an opening parenthesis shows as ")" there.
MIRRORED = dict(zip(u"()[]{}<>\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}",
                    u")(][}{><\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}"))
SCRIPTS = (("latin", "Latin"), ("cyrillic", "Cyrillic"), ("greek", "Greek"), ("kana", "Kana"), ("armenian", "Armenian"),
           ("georgian", "Georgian"), ("devanagari", "Devanagari"), ("hebrew", "Hebrew"), ("thaana", "Thaana"))
SCRIPT_LETTERS = {"latin": LETTERS, "cyrillic": CYRILLIC_LETTERS, "greek": GREEK_LETTERS, "kana": KANA_LETTERS,
                  "armenian": ARMENIAN_LETTERS, "georgian": GEORGIAN_LETTERS, "devanagari": DEVANAGARI_LETTERS,
                  "hebrew": HEBREW_LETTERS, "thaana": THAANA_LETTERS}
SCRIPT_PUNCTUATION = {"latin": PUNCTUATION, "cyrillic": CYRILLIC_PUNCTUATION, "greek": GREEK_PUNCTUATION,
                      "kana": KANA_PUNCTUATION, "armenian": ARMENIAN_PUNCTUATION, "georgian": GEORGIAN_PUNCTUATION,
                      "devanagari": DEVANAGARI_PUNCTUATION, "hebrew": HEBREW_PUNCTUATION, "thaana": THAANA_PUNCTUATION}
# Each script's references by kind of letter (as REFERENCES for Latin), the three letters its halo is
# tuned on (as TUNING), and its controls: a straight lowercase, a round lowercase, and a straight
# capital, as n, o, and H are Latin's (the font's spacing for the learned method). Kana have one
# kind: hiragana, katakana, small kana, and the long vowel mark share one body; their halo is tuned on
# RO alone (the halo grows until RO's envelopes meet across its palt spacing: no three kana agreed
# within a factor of two in every palt font tried), and their references are a square, a round, and
# an open kana (RO, NO, I), the band wide enough that most pairs palt sets evenly are left alone.
SCRIPT_REFERENCES = {"latin": REFERENCES,
                     "kana": {"kana": (u"ロ", u"の", u"い")},
                     "armenian": {"upper": (u"Ո", u"Օ"), "lower": (u"ո", u"ս", u"օ")},
                     "georgian": {"upper": (u"Ი", u"Ო"), "lower": (u"ი", u"ო", u"ს")}}
SCRIPT_TUNING = {"latin": TUNING, "kana": (u"ロ",), "armenian": (u"ո", u"ս", u"օ"),
                 "georgian": (u"ი", u"ო", u"ს")}
SCRIPT_CONTROLS = {"latin": u"noH", "kana": u"いのロ", "armenian": u"ոօՈ", "georgian": u"იოᲘ"}
SCRIPT_SIDE = {"latin": u"H", "kana": u"ロ", "armenian": u"Ո", "georgian": u"ი"}  # a pair is previewed between two of these
SCRIPT_PROOF = {"kana": u"ロのい", "armenian": u"Ոոօ", "georgian": u"Იიო"}  # and proofed in a Glyph window between these
SCRIPT_LINES = {"latin": u"Latin letters, figures, and punctuation", "kana": u"Kana and Japanese punctuation, as palt sets them",
                "armenian": u"Armenian letters and punctuation",
                "georgian": u"Georgian letters (Mkhedruli, and Mtavruli where the font has them) and punctuation"}
# Cyrillic and Greek as Latin: a straight and a round capital (En and O, Eta and Omicron), and a
# straight and a round lowercase with a third tuning letter (en, o, and pe; eta, omicron, and iota,
# whose stem is Greek's nearest to l). Devanagari, unicameral: two letters standing on their stem at
# the right (na, pa) and a round one hanging from the headline (ttha), which is drawn across each
# letter and meets the next: the references are set with it joined, as text sets them.
_CYRILLIC_EN, _CYRILLIC_O = u"\N{CYRILLIC CAPITAL LETTER EN}", u"\N{CYRILLIC CAPITAL LETTER O}"
_CYRILLIC_EN_SMALL, _CYRILLIC_O_SMALL = u"\N{CYRILLIC SMALL LETTER EN}", u"\N{CYRILLIC SMALL LETTER O}"
_GREEK_ETA, _GREEK_OMICRON = u"\N{GREEK CAPITAL LETTER ETA}", u"\N{GREEK CAPITAL LETTER OMICRON}"
_GREEK_ETA_SMALL, _GREEK_OMICRON_SMALL = u"\N{GREEK SMALL LETTER ETA}", u"\N{GREEK SMALL LETTER OMICRON}"
_DEVANAGARI_NA, _DEVANAGARI_PA, _DEVANAGARI_TTHA = (u"\N{DEVANAGARI LETTER NA}", u"\N{DEVANAGARI LETTER PA}",
                                                    u"\N{DEVANAGARI LETTER TTHA}")
SCRIPT_REFERENCES.update({
    "cyrillic": {"upper": (_CYRILLIC_EN, _CYRILLIC_O),
                 "lower": (_CYRILLIC_EN_SMALL, _CYRILLIC_O_SMALL, u"\N{CYRILLIC SMALL LETTER PE}")},
    "greek": {"upper": (_GREEK_ETA, _GREEK_OMICRON),
              "lower": (_GREEK_ETA_SMALL, _GREEK_OMICRON_SMALL, u"\N{GREEK SMALL LETTER IOTA}")},
    "devanagari": {"lower": (_DEVANAGARI_NA, _DEVANAGARI_PA, _DEVANAGARI_TTHA)}})
SCRIPT_TUNING.update({"cyrillic": SCRIPT_REFERENCES["cyrillic"]["lower"], "greek": SCRIPT_REFERENCES["greek"]["lower"],
                      "devanagari": SCRIPT_REFERENCES["devanagari"]["lower"]})
SCRIPT_CONTROLS.update({"cyrillic": _CYRILLIC_EN_SMALL + _CYRILLIC_O_SMALL + _CYRILLIC_EN,
                        "greek": _GREEK_ETA_SMALL + _GREEK_OMICRON_SMALL + _GREEK_ETA,
                        "devanagari": _DEVANAGARI_NA + _DEVANAGARI_TTHA + _DEVANAGARI_PA})
SCRIPT_SIDE.update({"cyrillic": _CYRILLIC_EN, "greek": _GREEK_ETA, "devanagari": _DEVANAGARI_NA})
SCRIPT_PROOF.update({"cyrillic": _CYRILLIC_EN + _CYRILLIC_EN_SMALL + _CYRILLIC_O_SMALL,  # (as PROOF_SCRIPTS proofs them)
                     "greek": _GREEK_ETA + u"\N{GREEK SMALL LETTER NU}" + _GREEK_OMICRON_SMALL,
                     "devanagari": _DEVANAGARI_PA + _DEVANAGARI_NA + _DEVANAGARI_TTHA})
SCRIPT_LINES.update({"cyrillic": u"Cyrillic letters and punctuation", "greek": u"Greek letters and punctuation",
                     "devanagari": u"Devanagari consonants, independent vowels, and punctuation"})
# Hebrew, unicameral: he, final mem, and samekh (ה, ם, ס), an open letter, a closed square one, and a
# round one, as Hebrew designers space them; previews between he, proofs between he, final nun, and
# samekh (as PROOF_SCRIPTS proofed them). Thaana: noonu, raa, and meemu (ނ, ރ, މ), its commonest
# letters, set side by side as text sets them under their fili.
_HEBREW_HE = u"\N{HEBREW LETTER HE}"
_THAANA_NOONU = u"\N{THAANA LETTER NOONU}"
SCRIPT_REFERENCES.update({
    "hebrew": {"lower": (_HEBREW_HE, u"\N{HEBREW LETTER FINAL MEM}", u"\N{HEBREW LETTER SAMEKH}")},
    "thaana": {"lower": (_THAANA_NOONU, u"\N{THAANA LETTER RAA}", u"\N{THAANA LETTER MEEMU}")}})
SCRIPT_TUNING.update({"hebrew": SCRIPT_REFERENCES["hebrew"]["lower"], "thaana": SCRIPT_REFERENCES["thaana"]["lower"]})
SCRIPT_CONTROLS.update({"hebrew": _HEBREW_HE + u"\N{HEBREW LETTER SAMEKH}\N{HEBREW LETTER FINAL MEM}",
                        "thaana": _THAANA_NOONU + u"\N{THAANA LETTER MEEMU}\N{THAANA LETTER RAA}"})
SCRIPT_SIDE.update({"hebrew": _HEBREW_HE, "thaana": _THAANA_NOONU})
SCRIPT_PROOF.update({"hebrew": _HEBREW_HE + u"\N{HEBREW LETTER FINAL NUN}\N{HEBREW LETTER SAMEKH}",
                     "thaana": _THAANA_NOONU + u"\N{THAANA LETTER RAA}\N{THAANA LETTER MEEMU}"})
SCRIPT_LINES.update({"hebrew": u"Hebrew letters and punctuation, right to left",
                     "thaana": u"Thaana letters and punctuation, right to left"})
ALL_SCRIPTS = "all"  # the Script list's last choice, for a font with two scripts or more: each analyzed, one list
ALL_SCRIPTS_LABEL = u"All scripts"
ALL_SCRIPTS_LINE = u"Every script the font has, each against its own references, in one list"
SCRIPT_MIN_LETTERS = 20  # a font has a script when it has its tuning letters and at least this many of its letters
KANA_SETTINGS = (("palt", "as the font's palt sets them"), ("proportional", "proportional already"))
FULL_WIDTH_SHARE = 0.9  # kana wider than this share of the em are full width (as CJK Spacing has it)


def common_pairs(path=None):
    """{pair: rank} from common_pairs.txt (andre-fuchs/kerning-pairs, MIT): Latin pairs common in text
    and kerned in fonts, most relevant first; then script_pairs.txt's pairs of the other scripts,
    common in text (kerning/train/script_pairs.py). Only path's pairs when given. Empty when
    the files are missing."""
    here = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    paths = [path] if path else [os.path.join(here, COMMON_PAIRS_FILE), os.path.join(here, SCRIPT_PAIRS_FILE)]
    ranks = {}
    for one in paths:
        try:
            import io
            with io.open(one, encoding="utf-8") as handle:
                for line in handle:
                    pair = line.rstrip(u"\r\n")
                    if len(pair) == 2 and not pair.startswith(u"#") and pair not in ranks:
                        ranks[pair] = len(ranks)
        except (IOError, OSError):
            pass
    return ranks


def method_fingerprint(model=None, script="latin"):
    """What the measuring depends on: a cache made with other settings (or another learned model)
    is not reused."""
    trained = (model or {}).get("info", {})
    references = sorted(SCRIPT_REFERENCES[script].items())
    if script != "latin":
        references = (script, references, SCRIPT_TUNING[script], SCRIPT_CONTROLS[script])
    return u"%d %d %d %r %r %r %r %r %r %r" % (CACHE_VERSION, KERN_VERSION, EM_PIXELS, HALO_SHARE, PAD_SHARE, CONTOUR_SLOPE,
                                             CONTOUR_FLOOR, MIN_GAP_SHARE, references,
                                             (trained.get("trained"), trained.get("pairs")) if model else None)


def cache_path(font_key, master, script="latin"):
    """The cache file of one font's master (and script, past Latin): named by a hash, so no path or
    name is stored in it."""
    import hashlib
    key = u"%s|%s" % (font_key, master) + (u"" if script == "latin" else u"|%s" % script)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return os.path.join(state_dir(), u"kerning-cache", u"%s.json" % digest)


def load_cache(path):
    import io
    import json
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (IOError, OSError, ValueError):
        return None


def save_cache(path, data):
    import io
    import json
    try:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        text = json.dumps(data, sort_keys=True)
        if not isinstance(text, type(u"")):
            text = text.decode("utf-8")
        with io.open(path + u".new", "w", encoding="utf-8") as handle:
            handle.write(text)
        if os.path.exists(path):
            os.remove(path)
        os.rename(path + u".new", path)
    except (IOError, OSError):
        pass  # no cache: the next run measures everything again


def path_signature(path, advance):
    """A glyph's outline and width, hashed: a pair is measured again when either glyph's changes."""
    import hashlib
    digest = hashlib.sha1((u"%.2f;" % advance).encode("ascii"))
    for index in range(path.elementCount()):
        element = path.elementAt(index)
        digest.update((u"%d %.2f %.2f;" % (element.type, element.x, element.y)).encode("ascii"))
    return digest.hexdigest()[:16]


def state_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser(u"~"), u".local", u"state")
    return os.path.join(base, u"FreeLab")


def kern_library_path():
    return os.environ.get("FREELAB_KERN_DLL") or os.path.join(state_dir(), u"bin", u"freelab_kern-v%d.dll" % KERN_VERSION)


class Core(object):
    """The native measuring core (freelab_kern-v<version>.dll)."""

    def __init__(self, path=None):
        import ctypes
        self.ctypes = ctypes
        path = path or kern_library_path()
        if not os.path.isfile(path):
            raise RuntimeError("the auto kerning library is missing: %s (tools/install-fontlab.ps1 builds it)" % path)
        lib = ctypes.CDLL(path)
        if lib.freelab_kern_version() != KERN_VERSION:
            raise RuntimeError("the auto kerning library is another version")
        p, i, d = ctypes.c_void_p, ctypes.c_int, ctypes.c_double
        lib.freelab_kern_scratch_size.restype = ctypes.c_int64
        lib.freelab_kern_scratch_size.argtypes = [i, i]
        lib.freelab_kern_envelope.argtypes = [p, i, i, i, i, p, p]
        lib.freelab_kern_overlap.restype = d
        lib.freelab_kern_overlap.argtypes = [p, i, p, i, i, i, i]
        lib.freelab_kern_pair.argtypes = [p, i, p, i, i, i, i, d, d, i, ctypes.POINTER(i), ctypes.POINTER(d)]
        lib.freelab_kern_profiles.argtypes = [p, i, i, i, p, p]
        lib.freelab_kern_extend.argtypes = [p, i, d, i]
        lib.freelab_kern_extend.restype = None
        lib.freelab_kern_contour_measure.restype = d
        lib.freelab_kern_contour_measure.argtypes = [p, p, i, d, d]
        lib.freelab_kern_closest.restype = d
        lib.freelab_kern_closest.argtypes = [p, p, i, d]
        lib.freelab_kern_contour_pair.argtypes = [p, p, i, d, d, d, d, d, ctypes.POINTER(d)]
        self.lib = lib
        self._scratch = None

    def envelope(self, glyph, bias):
        ctypes = self.ctypes
        size = self.lib.freelab_kern_scratch_size(glyph.width, glyph.height)
        if self._scratch is None or len(self._scratch) < size:
            self._scratch = (ctypes.c_uint8 * size)()
        out = (ctypes.c_uint8 * (glyph.width * glyph.height))()
        if not self.lib.freelab_kern_envelope(glyph.coverage, glyph.width, glyph.height, glyph.stride, bias, out, self._scratch):
            return None
        return out

    def overlap(self, left, left_env, right, right_env, offset):
        return self.lib.freelab_kern_overlap(left_env, left.width, right_env, right.width, left.height, offset, 0)

    def pair(self, left, left_env, right, right_env, offset, bias, low, high):
        ctypes = self.ctypes
        kern, s = ctypes.c_int(), ctypes.c_double()
        if not self.lib.freelab_kern_pair(left_env, left.width, right_env, right.width, left.height, offset, bias,
                                          low, high, 0, ctypes.byref(kern), ctypes.byref(s)):
            return None
        return kern.value, s.value

    def contours(self, glyph, slope):
        """(raw left, raw right, limited left, limited right) edge profiles, a value per row."""
        ctypes = self.ctypes
        h = glyph.height
        left, right = (ctypes.c_double * h)(), (ctypes.c_double * h)()
        self.lib.freelab_kern_profiles(glyph.coverage, glyph.width, h, glyph.stride, left, right)
        limited_left, limited_right = (ctypes.c_double * h)(*left), (ctypes.c_double * h)(*right)
        self.lib.freelab_kern_extend(limited_left, h, slope, 0)
        self.lib.freelab_kern_extend(limited_right, h, slope, 1)
        return left, right, limited_left, limited_right

    def contour_measure(self, right_of_left, left_of_right, h, offset, floor):
        return self.lib.freelab_kern_contour_measure(right_of_left, left_of_right, h, offset, floor)

    def closest(self, right_of_left, left_of_right, h, offset):
        return self.lib.freelab_kern_closest(right_of_left, left_of_right, h, offset)

    def contour_pair(self, right_of_left, left_of_right, h, offset, reach, floor, low, high):
        kern = self.ctypes.c_double()
        if not self.lib.freelab_kern_contour_pair(right_of_left, left_of_right, h, offset, reach, floor, low, high,
                                                  self.ctypes.byref(kern)):
            return None
        return kern.value


class Glyph(object):
    """One glyph's coverage image: `coverage` holds height rows of `stride` bytes; the glyph's origin
    is at column origin_x, on the same baseline row in every image; advance in whole pixels."""

    def __init__(self, name, coverage, width, height, stride, origin_x, advance, baseline=None):
        self.name, self.coverage = name, coverage
        self.width, self.height, self.stride = width, height, stride
        self.origin_x, self.advance = origin_x, advance
        self.baseline = baseline  # the baseline's row (every image shares it)
        self._envelopes = {}
        self._contours = None

    def envelope(self, core, bias):
        if bias not in self._envelopes:
            self._envelopes[bias] = core.envelope(self, bias)
        return self._envelopes[bias]

    def contours(self, core):
        if self._contours is None:
            self._contours = core.contours(self, CONTOUR_SLOPE)
        return self._contours


def base_offset(left, right):
    """The left image's column in the right one's pixels, the pair set with no kerning."""
    return right.origin_x - left.advance - left.origin_x


class Band(object):
    def __init__(self, bias, low, high):
        self.bias, self.low, self.high = bias, low, high


def first_bias(em):
    width = round_units(2 * HALO_SHARE * em)
    if width % 2 == 0:
        width += 1
    return width // 2


def calibrate(core, tuning, em, max_bias=None):
    """The halo and the overlap band, from the tuning glyphs set with themselves (ll, nn, oo):
    the halo grows until their overlaps are within a factor of two, as halfkern's does."""
    bias = first_bias(em)
    limit = max_bias or em
    while bias <= limit:
        overlaps = []
        for glyph in tuning:
            env = glyph.envelope(core, bias)
            if env is None:
                raise ValueError("%s has no solid ink to measure from" % glyph.name)
            overlaps.append(core.overlap(glyph, env, glyph, env, base_offset(glyph, glyph)))
        low, high = min(overlaps), max(overlaps)
        if low > high / 2:
            return Band(bias, low, high)
        bias += 1
    # (it said "no halo makes ll, nn, oo agree", which meant nothing to the user: owner's image 218)
    names = [g.name for g in tuning]
    raise ValueError(u"the font's %s, each set beside itself (%s), sit too differently apart to measure the other "
                     u"glyphs by: space them by eye first" % (
                         u", ".join(names[:-1]) + (u", and " if len(names) > 2 else u" and ") + names[-1]
                         if len(names) > 1 else u"".join(names), u", ".join(n + n for n in names)))


def category(ch):
    """A character's kind: "upper", "lower", "figure", "kana", or "punctuation" (anything else)."""
    if ch in LETTERS:
        return "upper" if ch.isupper() else "lower"
    if ch in FIGURES:
        return "figure"
    if ch in ARMENIAN_LETTERS:
        return "upper" if ch in ARMENIAN_CAPITALS else "lower"
    if ch in GEORGIAN_LETTERS:
        return "upper" if ch in MTAVRULI else "lower"
    if ch in CYRILLIC_LETTERS:  # (case from the tables, not isupper(): FontLab's Python knows Unicode 5.2 only)
        return "upper" if ch in CYRILLIC_CAPITALS else "lower"
    if ch in GREEK_LETTERS:
        return "upper" if ch in GREEK_CAPITALS else "lower"
    if ch in DEVANAGARI_LETTERS or ch in HEBREW_LETTERS or ch in THAANA_LETTERS:
        return "lower"  # (one case: its pairs are held to the lowercase band, as Mkhedruli's)
    if ch in KANA_LETTERS:
        return "kana"
    return "punctuation"


def script_of(ch):
    """The script of a letter Auto Kerning measures ("latin" for the figures too), or None."""
    if ch in LETTERS or ch in FIGURES:
        return "latin"
    for script, letters in SCRIPT_LETTERS.items():
        if ch in letters:
            return script
    return None


def script_characters(script):
    """The characters a script's analysis measures: its letters (and figures, for Latin) and punctuation."""
    return SCRIPT_LETTERS[script] + (FIGURES if script == "latin" else u"") + SCRIPT_PUNCTUATION[script]


def script_pairs(pairs, script):
    """The pairs (strings of two characters) with a letter of the script and nothing of another."""
    found = set()
    for pair in pairs:
        scripts = set(script_of(ch) for ch in pair)
        if script in scripts and scripts <= set([script, None]):
            found.add(pair)
    return found


# Right-to-left pairs. Auto Kerning measures and draws every pair as it stands on screen, its left
# glyph first (the gap between the left glyph's right side and the right glyph's left side). In text,
# a right-to-left pair's right glyph comes first, and that is the order the font's kerning keeps it
# in: a compiled font kerns it as (right glyph, left glyph), its value on the first glyph's placement
# and advance (<-30 0 -30 0>), and FontLab 7 keeps it so (read live on Noto Sans Hebrew, 2026-11-14:
# typed yod then bet, -64, is FontLab's pair (yod, bet); (bet, yod) is empty). So a right-to-left
# pair is read from and written to the font's kerning in text order (kerning_key), proofed in a Glyph
# window in that order (FontLab 7 sets typed Hebrew left to right, kerning it by that key), and
# counted, looked up, and shown in it (text_order, pair_label).


def kerning_key(left_char, right_char, left, right):
    """The font's kerning key of the glyph pair (left, right) on screen: the same, or (right, left) for
    a right-to-left pair, which the font kerns in text order. Its own inverse: given a key and its
    glyphs' characters in key order, kerning_key(second_char, first_char, second, first) is the
    pair on screen (see screen_of_key)."""
    return (right, left) if is_rtl_pair(left_char, right_char) else (left, right)


def screen_of_key(first_char, second_char, first, second):
    """The glyph pair on screen, (left, right), of a kerning key (first, second) whose glyphs have
    those characters (None for an unencoded glyph, which takes its partner's direction; see
    direction_char): a right-to-left key is in text order. Right to left: a letter of Hebrew or
    Thaana, or any character of the right-to-left blocks (is_rtl_char), so that Kerning Check and
    Font Compare read an Arabic or Syriac key the same way, though Auto Kerning measures neither."""
    if any(is_rtl_char(ch) for ch in (first_char, second_char) if ch):
        return second, first
    return first, second


def is_rtl_pair(left_char, right_char):
    """Whether a pair is of a right-to-left script (a mark of punctuation takes its partner's): its
    letters' script, as Auto Kerning measures it; a pair of no script it measures (Arabic) by the
    right-to-left blocks."""
    script = pair_script(left_char, right_char, None)
    if script is not None:
        return script in RTL_SCRIPTS
    return any(is_rtl_char(ch) for ch in (left_char, right_char) if ch)


# The right-to-left blocks: those Unicode gives a right-to-left bidirectional class (R or AL) by default
# (DerivedBidiClass.txt): Hebrew, Arabic, Syriac, Thaana, N'Ko, Samaritan, Mandaic, their presentation
# forms, and plane 1's right-to-left scripts (Phoenician, Kharoshthi, Old South Arabian, Old Hungarian,
# Hanifi Rohingya, Sogdian, Adlam...), without the numbers in them, which a right-to-left text sets left to
# right (Arabic-Indic digits, the Rumi numerals). A table, not unicodedata: FontLab's Python 2.7 knows
# Unicode 5.2, and its narrow build holds a character past U+FFFF as two code units. Proof keeps the
# same table (proof_tests checks they agree).
RTL_RANGES = ((0x0590, 0x08FF), (0xFB1D, 0xFDFF), (0xFE70, 0xFEFC), (0x10800, 0x10FFF), (0x1E800, 0x1EFFF))
RTL_NUMBER_RANGES = ((0x0600, 0x0605), (0x0660, 0x066C), (0x06DD, 0x06DD), (0x06F0, 0x06F9), (0x0890, 0x0891),
                     (0x08E2, 0x08E2), (0x10D30, 0x10D39), (0x10E60, 0x10E7E))


def code_of_char(ch):
    """The code point of a one-character text, a pair of UTF-16 surrogates read as one (a narrow
    Python 2); None for anything else."""
    if not ch:
        return None
    if len(ch) == 2 and 0xD800 <= ord(ch[0]) < 0xDC00 and 0xDC00 <= ord(ch[1]) < 0xE000:
        return 0x10000 + ((ord(ch[0]) - 0xD800) << 10) + ord(ch[1]) - 0xDC00
    return ord(ch) if len(ch) == 1 else None


def is_rtl_char(ch):
    """Whether a character is of a right-to-left script: a letter Auto Kerning measures right to left,
    or a character of the right-to-left blocks, numbers apart (RTL_RANGES)."""
    if not ch:
        return False
    if script_of(ch) in RTL_SCRIPTS:
        return True
    code = code_of_char(ch)
    if code is None:
        return False
    within = lambda ranges: any(low <= code <= high for low, high in ranges)
    return within(RTL_RANGES) and not within(RTL_NUMBER_RANGES)


def direction_char(package, name):
    """The character a glyph's direction is read from: its own, else its base glyph's, named by its
    name's stem (uni0628.fina, yod.alt, beh_alef by beh): FontLab's kerning of a right-to-left font is
    mostly between unencoded contextual forms. None when neither is encoded. Past U+FFFF, two UTF-16
    code units on a narrow Python 2 (is_rtl_char reads them as one)."""
    stem = name.split(u".")[0].split(u"_")[0]
    for candidate in ((name, stem) if stem and stem != name else (name,)):
        try:
            glyph = package.findName(candidate)
            # (flGlyph has no unicode of its own; main_code: not a Kangxi radical FontLab may give first)
            code = main_code(glyph.fgGlyph) if glyph is not None else None
        except Exception:
            code = None
        if code:
            try:
                return unichr(code)  # noqa: F821 (Python 2)
            except NameError:
                return chr(code)
            except ValueError:
                return (b"\\U%08x" % code).decode("unicode-escape")
    return None


def text_order(left_char, right_char):
    """A pair as typed: its characters in text order. A right-to-left pair's right character comes
    first, and a mirrored character is typed as its mirror (the ")" glyph at the right of a Hebrew
    pair is an opening parenthesis typed "(")."""
    if not is_rtl_pair(left_char, right_char):
        return left_char + right_char
    return MIRRORED.get(right_char, right_char) + MIRRORED.get(left_char, left_char)


def screen_order(text):
    """A pair typed (two characters in text order) as it stands on screen: (left, right)."""
    first, second = text[0], text[1]
    if pair_script(first, second, None) not in RTL_SCRIPTS:
        return first, second
    return MIRRORED.get(second, second), MIRRORED.get(first, first)


def pair_label(left_char, right_char):
    """A pair as the interface shows it, as a reader sees it: a right-to-left pair is typed in text
    order, which Qt sets right to left, its first letter at the right. Two letters need nothing more
    (and a list's type-ahead finds the pair by its first letter in text); with a mark of punctuation,
    which takes the direction around it, the pair goes inside a right-to-left embedding, so that the
    mark stays on its side and a bracket is mirrored, as on screen."""
    if not is_rtl_pair(left_char, right_char):
        return left_char + right_char
    text = text_order(left_char, right_char)
    if script_of(left_char) in RTL_SCRIPTS and script_of(right_char) in RTL_SCRIPTS:
        return text
    return u"\N{RIGHT-TO-LEFT EMBEDDING}%s\N{POP DIRECTIONAL FORMATTING}" % text


def rtl_note(s, sentence=False):
    """For a right-to-left pair (a Suggestion), which of its glyphs comes first in text: a sentence
    before a tooltip's next one, or a clause before the preview line's "writes to"."""
    if not is_rtl_pair(s.left_char, s.right_char):
        return u""
    if sentence:
        return u"Read right to left: %s first, at the right. " % s.right
    return u"read right to left, %s first, at the right; " % s.right


def font_scripts(characters):
    """The scripts a font can be kerned in, from the characters it has: their tuning letters and at
    least SCRIPT_MIN_LETTERS of their letters (Latin first)."""
    have = set(characters)
    found = []
    for script, _ in SCRIPTS:
        letters = sum(1 for ch in SCRIPT_LETTERS[script] if ch in have)
        if all(ch in have for ch in SCRIPT_TUNING[script]) and letters >= SCRIPT_MIN_LETTERS:
            found.append(script)
    return found


# palt's rules as FontLab's feature code (FEA) holds them, CJK Spacing's among them:
# "pos a-hira <-70 0 -130 0>;" (x placement, y placement, x advance, y advance), "pos a-hira -130;"
# (x advance alone), the glyph also as a [list] or an @class.
FEA_COMMENT = re.compile(u"#[^\n]*")
FEA_CLASS = re.compile(u"(@[A-Za-z0-9_.\\-]+)\\s*=\\s*\\[([^\\]]*)\\]\\s*;")
FEA_SINGLE = re.compile(u"\\bpos(?:ition)?\\s+(\\[[^\\]]*\\]|@[A-Za-z0-9_.\\-]+|[A-Za-z0-9_.\\-]+)\\s*"
                        u"(?:<\\s*(-?\\d+)\\s+(-?\\d+)\\s+(-?\\d+)\\s+(-?\\d+)\\s*>|(-?\\d+))\\s*;")


def palt_adjustments(text, prefix=u""):
    """{glyph name: (x placement, x advance)} of the single adjustments in palt's code (classes
    defined in it or in the features' prefix are expanded; a glyph's first rule wins, as palt.py reads
    a font's). Pair rules and anything else are left out."""
    classes = {}
    for source in (prefix or u"", text or u""):
        for name, members in FEA_CLASS.findall(FEA_COMMENT.sub(u"", source)):
            classes[name] = members.split()
    found = {}
    for match in FEA_SINGLE.finditer(FEA_COMMENT.sub(u"", text or u"")):
        target, x, _, advance, _, alone = match.groups()
        if target.startswith(u"["):
            names = []
            for item in target[1:-1].split():
                names.extend(classes.get(item, []) if item.startswith(u"@") else [item])
        elif target.startswith(u"@"):
            names = classes.get(target, [])
        else:
            names = [target]
        value = (0, int(alone)) if alone is not None else (int(x), int(advance))
        for name in names:
            found.setdefault(name, value)
    return found


def kana_setting(advances, upm, adjustments):
    """How the font's kana are set, from their advances {glyph name: width} and palt's adjustments:
    "proportional" when most are narrower than full width already (FULL_WIDTH_SHARE), "palt" when
    palt narrows most of them (by any amount: Source Han's palt leaves many kana above 90% of the
    em), None when they are full width and palt does not narrow them (kerning them would fight the
    full-width setting: CJK Spacing writes palt first)."""
    if not advances:
        return None
    limit = FULL_WIDTH_SHARE * upm
    if sum(1 for width in advances.values() if width < limit) * 2 > len(advances):
        return "proportional"
    narrowed = sum(1 for name in advances if adjustments.get(name, (0, 0))[1] < 0)
    return "palt" if narrowed * 2 > len(advances) else None


def reference_band(core, lefts, rights, bias):
    """The halfkern band of the references set with each other with no kerning, or None without them."""
    overlaps = []
    for left in lefts:
        for right in rights:
            left_env, right_env = left.envelope(core, bias), right.envelope(core, bias)
            if left_env is None or right_env is None:
                continue
            overlaps.append(core.overlap(left, left_env, right, right_env, base_offset(left, right)))
    if not overlaps:
        return None
    return Band(bias, min(overlaps), max(overlaps))


def contour_band(core, lefts, rights):
    """The contour-distance band of the references set with each other with no kerning, or None."""
    measures = []
    for left in lefts:
        for right in rights:
            _, _, _, right_of_left = left.contours(core)
            _, _, left_of_right, _ = right.contours(core)
            measures.append(core.contour_measure(right_of_left, left_of_right, left.height, base_offset(left, right),
                                                 CONTOUR_FLOOR))
    if not measures:
        return None
    return Band(None, min(measures), max(measures))


def pair_kinds(left_char, right_char):
    """The kinds whose band the pair follows: punctuation takes its partner's; None for two marks
    of punctuation (no text sets them side by side often enough to kern)."""
    left, right = category(left_char), category(right_char)
    if left == "punctuation" and right == "punctuation":
        return None
    if left == "punctuation":
        left = right
    if right == "punctuation":
        right = left
    return left, right


def suggest_pixels(core, left, right, band):
    """halfkern: the pair's kerning in pixels (negative is tighter; not yet scaled), refined between
    whole steps where the overlap crosses the band, or None when no step within reach does."""
    left_env, right_env = left.envelope(core, band.bias), right.envelope(core, band.bias)
    if left_env is None or right_env is None:
        return None
    offset = base_offset(left, right)
    found = core.pair(left, left_env, right, right_env, offset, band.bias, band.low, band.high)
    if found is None:
        return None
    kern, s = found
    if kern == 0:
        return 0.0
    before = kern + 1 if kern < 0 else kern - 1  # the step before the band was reached
    s_before = core.overlap(left, left_env, right, right_env, offset - before)
    target = band.low if kern < 0 else band.high
    if s == s_before:
        return float(kern)
    share = (target - s_before) / (s - s_before)  # where the overlap crosses the band, between the steps
    share = min(1.0, max(0.0, share))
    return before + (kern - before) * share


def suggest_contour_pixels(core, left, right, band, reach, min_gap):
    """Contour distance: the pair's kerning in pixels, or None when the band is out of reach. A
    tightening stops where the raw contours come within min_gap pixels (unless the pair is set
    closer than that already)."""
    _, raw_right_of_left, _, right_of_left = left.contours(core)
    raw_left_of_right, _, left_of_right, _ = right.contours(core)
    offset = base_offset(left, right)
    kern = core.contour_pair(right_of_left, left_of_right, left.height, offset, reach, CONTOUR_FLOOR, band.low, band.high)
    if kern is None:
        return None
    if kern < 0:
        closest = core.closest(raw_right_of_left, raw_left_of_right, left.height, offset - kern)
        if closest < min_gap:
            kern = min(0.0, kern + (min_gap - closest))
    return kern


def round_units(value):
    """Halves up, the same in Python 2.7 (which rounds them away from zero) and 3 (to even)."""
    return int(math.floor(value + 0.5))


def round_half_even(value):
    """round() as Python 3 does it (halves to even), under Python 2 too: the band edges of
    gap_profile must fall on the rows the training used."""
    floor = math.floor(value)
    if value - floor > 0.5 or (value - floor == 0.5 and floor % 2 == 1):
        floor += 1
    return int(floor)


def gap_profile(core, left, right, em):
    """The narrowest gap between the pair's facing ink (no kerning) in each height band, as a share
    of the em (at most GAP_CAP), or None in a band where either glyph has no ink."""
    _, raw_right_of_left, _, _ = left.contours(core)
    raw_left_of_right, _, _, _ = right.contours(core)
    offset = base_offset(left, right)
    low, high = BAND_RANGE
    step = (high - low) / PROFILE_BANDS
    gaps = []
    for band in range(PROFILE_BANDS):
        top = left.baseline - round_half_even(((low + (band + 1) * step) * em))
        bottom = left.baseline - round_half_even(((low + band * step) * em))
        narrowest = None
        for row in range(max(0, top), min(left.height, bottom)):
            if raw_right_of_left[row] < -1e8 or raw_left_of_right[row] > 1e8:
                continue
            gap = raw_left_of_right[row] - (raw_right_of_left[row] + offset)
            if narrowest is None or gap < narrowest:
                narrowest = gap
        gaps.append(None if narrowest is None else min(GAP_CAP, narrowest / em))
    return gaps


def closest_gap(core, left, right, em):
    """The narrowest gap between the two glyphs' ink, no kerning, as a share of the em (or None)."""
    _, raw_right_of_left, _, _ = left.contours(core)
    raw_left_of_right, _, _, _ = right.contours(core)
    gap = core.closest(raw_right_of_left, raw_left_of_right, left.height, base_offset(left, right))
    return None if gap > 1e8 else gap / em


def font_spacing(core, glyph_of, em, script="latin"):
    """The font's own spacing: the narrowest gaps of nn, oo, and HH (None for a pair it lacks); in
    another script, of its controls (SCRIPT_CONTROLS) set the same way."""
    spacing = []
    for ch in SCRIPT_CONTROLS[script]:
        left, right = glyph_of(ch), glyph_of(ch)
        spacing.append(closest_gap(core, left, right, em) if left is not None and right is not None else None)
    return spacing


def pair_features(core, left_char, right_char, left, right, em, spacing, halo_pixels, contour_pixels):
    """The learned method's inputs for a pair: both methods' readings, the pair's kinds, the font's
    spacing, the advances, and the gap profile; all in shares of the em, None where unknown."""
    return ([None if halo_pixels is None else halo_pixels / em, None if contour_pixels is None else contour_pixels / em,
             KIND_CODES[category(left_char)], KIND_CODES[category(right_char)]] + list(spacing)
            + [left.advance / em, right.advance / em] + gap_profile(core, left, right, em))


_MODEL = {}


def learned_model(path=None):
    """The learned method's trees (learned_model.json beside this script), or None without them."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), LEARNED_MODEL_FILE)
    if path not in _MODEL:
        import io
        import json
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            features = 4 + len(SPACING_PAIRS) + 2 + PROFILE_BANDS  # pair_features' length
            _MODEL[path] = data if data.get("format") == 2 and len(data.get("features", [])) == features else None
        except (IOError, OSError, ValueError):
            _MODEL[path] = None
    return _MODEL[path]


def tree_sum(stage, features):
    """A stage's baseline plus its trees' leaves. A node is [feature, threshold, missing goes left,
    left, right, is leaf, value]; a feature at most the threshold goes left, as in scikit-learn."""
    total = stage["baseline"]
    for tree in stage["trees"]:
        node = tree[0]
        while not node[5]:
            value = features[node[0]]
            left = node[2] if value is None else value <= node[1]
            node = tree[node[3] if left else node[4]]
        total += node[6]
    return total


def learned_scripts(model):
    """The scripts Auto Kerning uses the learned model for: those its training checked it on (its
    info's "scripts"; Latin alone for a model that does not say)."""
    return (model or {}).get("info", {}).get("scripts") or ["latin"]


def predict(model, features):
    """The learned kerning of a pair, as a share of the em: 0 unless the classifier finds the pair
    kerned (its probability at least the model's cut), else the regressor's amount."""
    raw = tree_sum(model["classifier"], features)
    chance = 1.0 / (1.0 + math.exp(-raw)) if raw > -30 else 0.0
    if chance < model["cut"]:
        return 0.0
    return tree_sum(model["regressor"], features)


def to_units(pixels, em, upm, tighten=TIGHTEN, loosen=LOOSEN):
    value = pixels * upm / em
    value *= tighten if value < 0 else loosen
    return round_units(value)


def fit_factors(samples, defaults=(TIGHTEN, LOOSEN)):
    """The tightening and loosening factors that best turn raw suggestions (units, unscaled) into
    the designer's kerning, from (raw, designer) pairs; the defaults where too few pairs show one."""
    factors = []
    for sign, default in zip((-1, 1), defaults):
        chosen = [(raw, value) for raw, value in samples if raw * sign > 0 and value * sign > 0]
        if len(chosen) < MODELS_MIN:
            factors.append(default)
            continue
        factor = sum(raw * value for raw, value in chosen) / sum(raw * raw for raw, _ in chosen)
        factors.append(min(FACTOR_RANGE[1], max(FACTOR_RANGE[0], factor)))
    return tuple(factors)


def spread(values):
    """How far the methods' values lie apart (0 with one or none)."""
    known = [v for v in values if v is not None]
    return max(known) - min(known) if len(known) > 1 else 0


def average(values):
    known = [v for v in values if v is not None]
    return round_units(sum(known) / len(known)) if known else None


# ---------------------------------------------------------------------------
# FontLab
# ---------------------------------------------------------------------------

def _qt():
    from PythonQt import QtCore, QtGui
    return QtCore, QtGui


KERNING_CHECK_FILE, KERNING_CHECK_MODULE = "freelab_kerning_check.py", "freelab_kerning_check"


HELPER_SUFFIX = ".module"  # a helper module's extension once installed (tools/install-fontlab.ps1)
# FontLab lists every .py file of a Scripts folder in its menu, under its file name when it has no
# title line: a module that is no script of its own (Feature Code's freelab_alternates.py) is installed
# with this extension instead, and so stays out of Scripts > FreeLab.


def sibling_path(file_name, here=None):
    """The path of a FreeLab file beside this one: as named, or a helper module under its installed
    extension when the .py is not there."""
    here = here or os.path.dirname(os.path.abspath(globals().get("__file__") or "."))
    path = os.path.join(here, file_name)
    if not os.path.isfile(path):
        helper = os.path.splitext(path)[0] + HELPER_SUFFIX
        if os.path.isfile(helper):
            return helper
    return path


def load_sibling(file_name, module_name):
    """A FreeLab script beside this one, loaded as a module without starting it (its main() not run);
    loaded again when its file changed (a reinstall)."""
    path = sibling_path(file_name)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    held = sys.modules.get(module_name)
    if held is not None and hasattr(held, "main") and getattr(held, "_freelab_stamp", None) == stamp:
        return held
    hold_module(held)  # (its open windows keep their globals)
    old = os.environ.get("FREELAB_NO_AUTOSTART")
    os.environ["FREELAB_NO_AUTOSTART"] = "1"
    try:
        if sys.version_info[0] == 2:
            import imp
            module = imp.new_module(module_name)
            module.__file__ = path
            sys.modules[module_name] = module
            with open(path, "rb") as handle:  # open() takes a unicode path through the wide Windows API
                source = handle.read()
            exec(compile(source, file_name, "exec", 0, True), module.__dict__)
        else:
            import importlib.machinery
            import importlib.util
            # (the loader named: a helper's installed extension tells importlib nothing)
            spec = importlib.util.spec_from_file_location(
                module_name, path, loader=importlib.machinery.SourceFileLoader(module_name, path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)  # no half-loaded stub left behind
        raise
    finally:
        if old is None:
            os.environ.pop("FREELAB_NO_AUTOSTART", None)
        else:
            os.environ["FREELAB_NO_AUTOSTART"] = old
    module._freelab_stamp = stamp
    return module


def open_sibling_script(file_name, module_name, caller=None):
    """Runs a FreeLab script beside this one (its main()), opened from caller's window (a widget of it:
    opening_from); the error's text, or None."""
    try:
        with opening_from(caller):
            load_sibling(file_name, module_name).main()
        return None
    except Exception as exc:
        return u"%s" % exc


FEATURE_CHECK_FILE, FEATURE_CHECK_MODULE = "freelab_feature_check.py", "freelab_feature_check"


def feature_code_refusal(package, texts, prefix=None, names=None, adding=()):
    """For a script about to write feature code: why it must not (Feature Check's change_refusal: the
    errors the code would bring that the font's code does not have now), or None. None too when Feature
    Check or fontTools is not there: the write then goes ahead unchecked. texts: {tag: the whole
    feature's new text}; prefix: the new prefix, or None to keep the font's; names: the font's glyph
    names (read when None); adding: glyphs the same write adds (they count as in the font)."""
    try:
        checker = load_sibling(FEATURE_CHECK_FILE, FEATURE_CHECK_MODULE)
        refusal = getattr(checker, "change_refusal", None)
    except Exception:
        return None
    if refusal is None:
        return None
    try:
        if names is None or adding:
            names = list(names) if names is not None else [g.name for g in package.fgPackage.glyphs]
            names += [name for name in adding if name not in set(names)]
        return refusal(package, texts, prefix, names)
    except Exception:
        return None


def open_kerning_check(glyphs=None, reason=None, caller=None):
    """Kerning Check on caller's font (a widget of the window it is opened from: opening_from), its lists
    limited to the pairs and entries with these glyphs (names, or glyphs) when given; reason says what the
    caller did to them ("Auto Spacing spaced": the line over the lists reads "Pairs with the 12 glyphs
    Auto Spacing spaced: ..."). The error's text, or None."""
    try:
        with opening_from(caller):
            load_sibling(KERNING_CHECK_FILE, KERNING_CHECK_MODULE).main(glyphs=glyphs, reason=reason)
        return None
    except Exception as exc:
        return u"%s" % exc


def _property(widget, name):
    """A Qt property's value (PythonQt gives properties as attributes, some builds as methods)."""
    value = getattr(widget, name)
    return value() if callable(value) else value


def _keep_room_when_hidden(widget):
    """Hides the widget, keeping its room in the layout; False (and the widget shown, disabled) on a Qt
    without retainSizeWhenHidden."""
    QtCore, QtGui = _qt()
    try:
        policy = _property(widget, "sizePolicy")
        policy.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(policy)
        widget.setVisible(False)
        return True
    except Exception:
        widget.setEnabled(False)
        return False


def latin_characters():
    return LETTERS + FIGURES + PUNCTUATION


def font_glyphs(package, characters):
    """(character, glyph name) for the characters the font has, in that order."""
    found = []
    for ch in characters:
        glyph = package.findUnicode(ord(ch))
        if glyph is not None and not glyph.isNull:
            found.append((ch, glyph.name))
    return found


def layer_path(layer, fallback=True):
    """The layer's outlines as one QPainterPath. A layer drawn as a picture (an SVG or bitmap color
    glyph, which FontLab does not hand to scripts) gives the outlines of the glyph's black-and-white
    layer instead (the font's fallback outlines), if it has one."""
    QtCore, QtGui = _qt()
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)
    for shape in layer.shapes:
        transform = shape.transform
        for contour in shape.contours:
            if contour is None:  # FontLab lists an empty contour as None in some glyphs
                continue
            path.addPath(transform.map(contour.path()))
    if fallback and path.isEmpty():
        outlines = outline_layer(layer)
        if outlines is not None:
            return layer_path(outlines, False)
    return path


PICTURE_SHAPE = "ShapeImage"  # an SVG or bitmap color glyph's element


def is_picture_layer(layer):
    try:
        return any(shape.shapeType == PICTURE_SHAPE for shape in layer.shapes)
    except Exception:
        return False


def outline_layer(layer):
    """For a layer drawn as a picture: the glyph's other layer with outlines (an SVG font's
    black-and-white glyphs, as FontLab imports them), or None."""
    if not is_picture_layer(layer):
        return None
    try:
        glyph = layer.glyph
        for other in glyph.layers:
            if other.name == layer.name or other.isMaskLayer or other.isService:
                continue
            if any(len(shape.contours) for shape in other.shapes):
                return other
    except Exception:
        pass
    return None


BLACK_RGBA = 0xff000000


def layer_parts(layer):
    """[(QPainterPath, QColor)] for a layer whose shapes carry their own colors (a COLR color glyph,
    as FontLab imports it), or None for a glyph drawn in one ink."""
    QtCore, QtGui = _qt()
    parts, colored = [], False
    try:
        for shape in layer.shapes:
            color = shape.brush.color()
            colored = colored or (color.rgba() & 0xffffffff) != BLACK_RGBA
            path = QtGui.QPainterPath()
            path.setFillRule(QtCore.Qt.WindingFill)
            transform = shape.transform
            for contour in shape.contours:
                if contour is not None:
                    path.addPath(transform.map(contour.path()))
            if not path.isEmpty():
                parts.append((path, QtGui.QColor(color)))
    except Exception:
        return None
    return parts if colored and parts else None


def fill_glyph(painter, path, brush, parts=None, transform=None):
    """Fill a glyph: in the brush's ink, or, given layer_parts, each part in its own color (with the
    brush's transparency), as the font draws it. transform maps the parts as the path was mapped."""
    QtGui = _qt()[1]
    if not parts:
        painter.fillPath(path, brush)
        return
    alpha = brush.color().alphaF() if brush is not None else 1.0
    for part, color in parts:
        if transform is not None:
            part = transform.map(part)
        if alpha < 1.0:
            color = QtGui.QColor(color)
            color.setAlphaF(color.alphaF() * alpha)
        painter.fillPath(part, QtGui.QBrush(color))


def color_kind(package, sample=48):
    """How a font draws in color: "layers" (shapes with their own colors: COLR), "pictures" (SVG or
    bitmap glyphs), or None. A few milliseconds: every glyph's color flag, then a sample of glyphs."""
    try:
        glyphs = package.fgPackage.glyphs
        for glyph in glyphs:
            if glyph.hasColors():
                return "layers"
        count = len(glyphs)
        master = package.master
        for i in range(0, count, max(1, count // sample)):
            glyph = package.findName(glyphs[i].name)
            layer = glyph.getLayerByName(master) if glyph is not None else None
            if layer is not None and is_picture_layer(layer):
                return "pictures"
    except Exception:
        return None
    return None


def joined(items, word=u"and"):
    """u"l", u"l and n", u"l, n, and o" (the serial comma)."""
    items = list(items)
    if len(items) < 3:
        return (u" %s " % word).join(items)
    return u"%s, %s %s" % (u", ".join(items[:-1]), word, items[-1])


def missing_references(package, needed, missing, tool, why):
    """The sentence for a tool that cannot start without the font's reference letters (needed, of
    which missing are not in the font): the missing ones named only when some are there; for a color
    font without any, why there is nothing to do."""
    if len(missing) == len(needed):
        if color_kind(package):
            return (u"%s is a color font: emoji are set on one width and are not kerned or spaced against "
                    u"letters, so %s has nothing to work from (it needs %s: %s)." % (
                        package.tfn, tool, joined(needed), why))
        return u"%s needs %s: %s." % (tool, joined(needed), why)
    quoted = [u"\N{LEFT DOUBLE QUOTATION MARK}%s\N{RIGHT DOUBLE QUOTATION MARK}" % ch for ch in missing]
    return u"This font has no %s. %s needs %s: %s." % (joined(quoted, u"or"), tool, joined(needed), why)


def color_note(package):
    """A sentence for a script's log about a color font, or u"" for one drawn in one ink."""
    kind = color_kind(package)
    name = b(package.tfn)
    if kind == "layers":
        return u"%s is a color font: its glyphs are shown in their own colors." % name
    if kind == "pictures":
        return (u"%s draws its glyphs as color pictures (SVG or bitmaps), which FontLab does not hand to "
                u"scripts: their black-and-white outlines are shown instead, where the font has them." % name)
    return u""


class FontLabGlyphs(object):
    """Glyph images of one master, rendered with Qt from FontLab's outlines; adjustments {glyph name:
    (x placement, x advance)} set glyphs as a feature does (kana as palt sets them)."""

    def __init__(self, package, master, em=EM_PIXELS, adjustments=None):
        import ctypes
        self.ctypes = ctypes
        self.package, self.master, self.em = package, master, em
        self.adjustments = adjustments or {}
        self.upm = float(package.upm)
        self.scale = em / self.upm
        self.pad = int(math.ceil(PAD_SHARE * em))
        self.paths, self.advances, self.signatures = {}, {}, {}
        self.top = self.bottom = 0.0
        self.images = {}
        # At most `most` images kept (the oldest let go, drawn again if asked for), but those of `keep`; None:
        # every image kept. Auto Spacing measures each glyph against a few references only, and kept every
        # glyph's image with its envelopes: 5 GB more for Noto Sans JP's 4,954 glyphs (live 2026-11-19).
        self.keep, self.most, self._drawn = set(), None, []

    def add(self, name):
        glyph = self.package.findName(name)
        layer = glyph.getLayerByName(self.master) if glyph is not None else None
        if layer is None:
            return False
        path = layer_path(layer)
        if path.isEmpty():
            return False
        advance = layer.advanceWidth
        if name in self.adjustments:
            QtCore, QtGui = _qt()
            placement, extra = self.adjustments[name]
            shift = QtGui.QTransform()
            shift.translate(placement, 0)
            path = shift.map(path)
            advance += extra
        rect = path.boundingRect()
        self.paths[name], self.advances[name] = path, advance
        self.signatures[name] = path_signature(path, advance)
        self.top = max(self.top, rect.bottom())  # font units grow upward: the rect's bottom is the ink's top
        self.bottom = min(self.bottom, rect.top())
        return True

    def image(self, name):
        """The Glyph for name; every image shares one height and baseline (call after every add)."""
        if name in self.images:
            return self.images[name]
        QtCore, QtGui = _qt()
        ctypes = self.ctypes
        path, scale = self.paths[name], self.scale
        rect = path.boundingRect()
        ascent = int(math.ceil(self.top * scale)) + 1
        descent = int(math.ceil(-self.bottom * scale)) + 1
        origin_x = self.pad + int(math.ceil(max(0.0, -rect.left() * scale))) + 1
        width = origin_x + int(math.ceil(max(0.0, rect.right()) * scale)) + 1 + self.pad
        height = ascent + descent + 2 * self.pad
        baseline = self.pad + ascent
        image = QtGui.QImage(width, height, QtGui.QImage.Format_Alpha8)
        image.fill(0)
        painter = QtGui.QPainter(image)
        try:  # ended before anything else can fail: a painter left open on a freed image aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(origin_x, baseline)
            painter.scale(scale, -scale)
            painter.fillPath(path, QtGui.QBrush(QtGui.QColor(0, 0, 0, 255)))
        finally:
            painter.end()
        stride = image.bytesPerLine()
        address = ctypes.addressof(ctypes.c_char.from_buffer(image.bits()))
        coverage = (ctypes.c_uint8 * (stride * height)).from_buffer_copy(ctypes.string_at(address, stride * height))
        advance = round_units(self.advances[name] * scale)
        return self.remember(name, Glyph(name, coverage, width, height, stride, origin_x, advance, baseline))

    def remember(self, name, glyph):
        """glyph kept as name's image; past `most`, the oldest drawn let go (but those of `keep`). Returns glyph."""
        self.images[name] = glyph
        if self.most is not None and name not in self.keep:
            self._drawn.append(name)
            while len(self._drawn) > self.most:
                self.images.pop(self._drawn.pop(0), None)
        return glyph


def current_kerning(kerning, left, right):
    """A glyph pair's own entry only: kerning classes are not looked at (see FontKerning)."""
    try:
        value = kerning.get((left, right))
    except Exception:
        return 0
    return round_units(value or 0)


CLASS_SIDES = {"left": ("KernLeft", "KernBothSide"), "right": ("KernRight", "KernBothSide")}


def _text(name):
    return name if not isinstance(name, bytes) else name.decode("utf-8", "replace")


class FontKerning(object):
    """A master's kerning as FontLab applies it, classes included, and where a pair's value goes.

    fgKerning.get((left, right)) reads a pair's own entry and misses class kerning. FontLab's
    getPlainPairsDict() resolves the classes. Writing kerning[(a, b)] takes a name that is also a
    class's as the class (a class may share its first glyph's name: class T holds T, Tcaron...), so
    a pair is written to the most specific entry that applies to it, or else to its classes'
    pair, and only where the names say what they mean.
    """

    def __init__(self, kerning):
        self.kerning = kerning
        self.plain = None
        try:
            self.plain = dict(((_text(left), _text(right)), value)
                              for (left, right), value in kerning.getPlainPairsDict().items())
        except Exception:
            pass
        self.classes, self.members, self.class_flags = set(), {}, {}
        self.left_class, self.right_class = {}, {}
        try:
            for name, (members, side) in kerning.groups.items():
                name = _text(name)
                self.classes.add(name)
                self.class_flags[name] = str(side)
                self.members[name] = [_text(m) for m in members]
                for member in self.members[name]:
                    if side in CLASS_SIDES["left"]:
                        self.left_class.setdefault(member, name)
                    if side in CLASS_SIDES["right"]:
                        self.right_class.setdefault(member, name)
        except Exception:
            pass
        self.entries = set()  # ((left, is class), (right, is class)) of every explicit pair
        self.values = {}  # entry: its value
        try:
            for pair, value in kerning.items():
                entry = ((_text(pair.left.id), str(pair.left.mode) == "groupMode"),
                         (_text(pair.right.id), str(pair.right.mode) == "groupMode"))
                self.entries.add(entry)
                self.values[entry] = value
        except Exception:
            pass

    def current(self, left, right):
        if self.plain is None:
            return current_kerning(self.kerning, left, right)
        return round_units(self.plain.get((left, right)) or 0)

    def candidates(self, left, right):
        """The entries that could kern the pair, most specific first: glyphs, then classes."""
        left_class, right_class = self.left_class.get(left), self.right_class.get(right)
        found = [((left, False), (right, False))]
        if right_class:
            found.append(((left, False), (right_class, True)))
        if left_class:
            found.append(((left_class, True), (right, False)))
        if left_class and right_class:
            found.append(((left_class, True), (right_class, True)))
        return found

    def hidden(self, entry):
        """The glyph names of an entry that a class also bears: written as they are, FontLab would read
        them as the class (see write)."""
        return sorted(set(name for name, is_class in entry if not is_class and name in self.classes))

    def target(self, left, right):
        """(entry, remove when 0) for a pair: the entry that sets its value now, or else its classes'
        pair (or its glyphs' when it has none). A 0 removes the entry only when no pair it sets would
        then take another entry's value (glyph A against class R, removed, would hand A/W to class L
        against glyph W): it is written as 0 otherwise."""
        found = self.candidates(left, right)
        for entry in found:
            if entry in self.entries:
                return entry, not self.exposes(entry)
        return found[-1], True

    def exposes(self, entry):
        """True when removing the entry would let another entry set a glyph pair it sets now."""
        for left, right in self.pairs(entry):
            found = self.candidates(left, right)
            if entry not in found:
                continue
            index = found.index(entry)
            if any(other in self.entries for other in found[:index]):
                continue  # a more specific entry sets this pair: removing this one changes nothing
            if any(other in self.entries for other in found[index + 1:]):
                return True
        return False

    def reach(self, entry):
        """How many glyph pairs an entry kerns."""
        return len(self.pairs(entry))

    def pairs(self, entry):
        """The glyph pairs an entry kerns: every member of a class side against every one of the other."""
        side = lambda name, is_class: self.members.get(name, []) if is_class else [name]
        return [(left, right) for left in side(*entry[0]) for right in side(*entry[1])]

    def first_pair(self, entry):
        """The first glyph pair an entry kerns (pairs(entry)[0]), without making every pair of two
        classes; None for an empty class."""
        firsts = []
        for name, is_class in entry:
            members = self.members.get(name, []) if is_class else [name]
            if not members:
                return None
            firsts.append(members[0])
        return tuple(firsts)

    @staticmethod
    def describe(entry):
        name = lambda text, is_class: (u"class %s" % text) if is_class else text
        return u"%s \N{MULTIPLICATION SIGN} %s" % (name(*entry[0]), name(*entry[1]))

    def write(self, entry, value, remove):
        """Set the entry (0 removes it when remove). A glyph that shares a class's name (glyph j and
        class j) is named while that class is renamed out of the way, and the class renamed back:
        renaming a class keeps its pairs (checked in FontLab 7.2: pairs, classes, and the applied
        kerning identical after the round trip)."""
        renamed = []
        # a spare name is no class's, no name of the entry's (a glyph A__freelab would be read as the
        # renamed class), and no other spare's
        taken = set(self.classes) | set(name for name, _ in entry)
        try:
            for name in self.hidden(entry):
                spare = name + u"__freelab"
                while spare in taken:
                    spare += u"_"
                taken.add(spare)
                self.kerning.renameGroup(name, spare)
                renamed.append((name, spare))
            # a side that is the renamed class itself (glyph o against class o) goes by its spare name
            spares = dict(renamed)
            key = tuple(spares.get(name, name) if is_class else name for name, is_class in entry)
            if value or not remove:
                self.kerning[key] = value
                self.entries.add(entry)
            elif entry in self.entries:
                self.kerning.remove(key)  # `del kerning[pair]` removes it but raises in PyCXX
                self.entries.discard(entry)
        finally:
            failed = []
            for name, spare in reversed(renamed):
                try:
                    self.kerning.renameGroup(spare, name)
                except Exception:
                    failed.append(u"%s (now %s)" % (name, spare))
            if failed:
                raise RuntimeError(u"FontLab did not rename these classes back: %s. Rename them in the Classes panel."
                                   % u", ".join(failed))

    def resolving(self, left, right):
        """The entry that sets a glyph pair's value now, or None."""
        for entry in self.candidates(left, right):
            if entry in self.entries:
                return entry
        return None


PROOF_CONTEXTS = (u"H", u"n", u"o")  # each line of a Glyph window proof: the pair between two of these


# The control characters a pair is proofed between, by its script: a straight capital, a straight and
# a round lowercase, as type designers proof (Walter Tracy's method); figures between zeros too.
PROOF_SCRIPTS = (("GREEK", u"\u0397\u03bd\u03bf"), ("CYRILLIC", u"\u041d\u043d\u043e"), ("ARMENIAN", u"\u0540\u0576\u0585"),
                 ("HEBREW", u"\u05d4\u05df\u05e1"), ("ARABIC", u"\u0627\u0646\u0647"), ("DIGIT", u"0Hn"))


def proof_contexts(package, names):
    """The glyph names to proof glyphs between, in the script of the first of them that is encoded
    (H, n, and o for Latin; Greek's Eta, nu, omicron; Cyrillic's En, en, o; zeros for figures): only
    those the font has, else Latin's, else the glyphs themselves. The scripts Auto Kerning measures
    take the controls of SCRIPT_PROOF (Greek's and Cyrillic's the same as PROOF_SCRIPTS')."""
    import unicodedata
    controls = u"Hno"
    for name in names:
        glyph = package.findName(name)
        code = main_code(glyph.fgGlyph) if glyph is not None else 0  # (U+65E5, not the radical U+2F47)
        if code:
            script = script_of(unichr_(code))
            if script in SCRIPT_PROOF:
                controls = SCRIPT_PROOF[script]
                break
            title = unicodedata.name(unichr_(code), u"")
            for word, chars in PROOF_SCRIPTS:
                if word in title.split():
                    controls = chars
                    break
            break
    for chars in (controls, u"Hno"):
        found = []
        for ch in chars:
            glyph = package.findUnicode(ord(ch))
            if glyph is not None and not glyph.isNull and glyph.name not in found:
                found.append(glyph.name)
        if found:
            return found
    return list(names[:1])


def proof_text(left, right, contexts=PROOF_CONTEXTS):
    """FontLab text (glyph names after slashes) for a pair between two of each context glyph, a
    line each: /H/H/T/o/H/H, /n/n/T/o/n/n, ..."""
    lines = [u"/%s/%s/%s/%s/%s/%s" % (c, c, left, right, c, c) for c in contexts]
    return u"/space".join(lines)


GLYPH_TAB_ACTION = "actionOpen_Editor_Window"  # FontLab's Window > New Glyph Tab


def pending_slots():
    """The single-shot timers' slots waiting to run, held in sys until each runs and lets itself go: PythonQt
    drops a slot no Python object holds (QTimer.singleShot keeps none), and sys outlives a reinstall's module."""
    held = getattr(sys, "_freelab_pending_slots", None)
    if held is None:
        held = sys._freelab_pending_slots = set()
    return held


def show_in_glyph_window(fontlab, text, owner=None):
    """Opens a new Glyph tab (FontLab's own New Glyph Tab) and sets its text (FontLab's /glyphname
    syntax), as typing it would; the error's text, or None. requestContent alone sets the text of the
    active Glyph window only, and does nothing without one. Both act on the font FontLab shows: asked
    from a tool's window (owner, else the active window's tool) whose font is another, that font is shown
    first (focus_font), and the command refused, naming the font to click, only when it cannot be."""
    QtCore, QtGui = _qt()
    try:
        if owner is None:
            owner = window_owner(QtGui.QApplication.activeWindow())
    except Exception:
        owner = None
    foreign = own_font_refusal(owner, fontlab)
    if foreign:
        return (u"FontLab opens it on the font it shows, not on this window's (%s), and FreeLab could not "
                u"show that font: click %s's Font window, then try again." % (foreign, foreign))
    if foreign is not None:
        return (u"FontLab opens it on the font it shows, and this window's font is no longer open (or FontLab "
                u"could not say which font it shows)")
    try:
        symbols = fontlab.fgSymbolList(text, True)
    except Exception as exc:
        return u"%s" % exc
    action = None
    main = AutoKerningDialog.main_window()
    if main is not None:
        for candidate in main.findChildren(QtGui.QAction):
            if candidate.objectName == GLYPH_TAB_ACTION:
                action = candidate
                break
    if action is None:
        return u"FontLab's New Glyph Tab command was not found"

    pending = pending_slots()

    def fill():
        try:
            fontlab.flItems.requestContent(symbols, 0)
        except Exception:
            pass
        finally:
            pending.discard(fill)

    try:
        action.trigger()
        pending.add(fill)  # (held until it runs: PythonQt drops a slot no Python object holds)
        QtCore.QTimer.singleShot(150, fill)  # once the new tab is the active Glyph window
        return None
    except Exception as exc:
        return u"%s" % exc


def _history():
    held = getattr(sys, "_freelab_history", None)
    if held is None:
        held = sys._freelab_history = {"whole": set(), "counts": {}}
    return held


def _without_state(obj):
    """Whether FontLab's History holds no state of obj to go back to: it is at its first one (a font
    opened afresh: the font itself has one, its layers and glyphs none). True when it cannot be read."""
    try:
        return obj.currentHistoryState() == obj.initialHistoryState()
    except Exception:
        return True


def _glyph_count(package):
    try:
        return int(package.glyphsCount)
    except Exception:
        return None


class HistoryError(Exception):
    """before_changes could not record the font before a write: the write must not happen, since Undo
    could not take it back. Its text is the log's line (HTML)."""


class WriteStatus(object):
    """What notify_changed managed once a write was made. recorded: FontLab's History holds the step,
    so Undo takes the write back; marked: the font is marked modified, so FontLab asks to save it before
    closing it. A redraw that failed (a glyph's update, the Font window's list of glyphs) is not counted:
    it costs a display, not the write."""

    def __init__(self):
        self.recorded = self.marked = True
        self.reasons = []  # (what failed, the error), for the log
        self.info_changes = []  # the font info FreeLab updated to match (freelab_font_info's Change)
        self.info_error = None  # why it could not, if it failed

    @property
    def ok(self):
        return self.recorded and self.marked

    def info_text(self):
        """The log's line (HTML) for the font info updated to match the write, or u"" when none was."""
        if not self.info_changes:
            return u""
        undo = u""
        if self.recorded:  # (the History takes back the ranges and code pages; FreeLab follows it with the Win values)
            win = any(change.field in ("openTypeOS2WinAscent", "openTypeOS2WinDescent") for change in self.info_changes)
            undo = u" <i>Edit &gt; Undo</i> takes it back with the glyphs%s." % (
                u" (the Win values while this window is open)" if win else u"")
        return u"Updated the font info to match: %s.%s" % (
            html(u"; ".join(change.text() for change in self.info_changes)), undo)

    def info_failure(self):
        """The log's line (HTML) when the font info could not be updated to match, or u""."""
        if self.info_error is None:
            return u""
        return u"The font info's Unicode ranges, code pages, and Win values were not updated to match (%s)." % html(
            self.info_error)

    def report_info(self, log):
        """The font info's line, if any, added to a tool's log."""
        if log is None:
            return
        try:
            if self.info_text():
                log.add(self.info_text(), "done")
            if self.info_failure():
                log.add(self.info_failure(), "warning")
        except Exception:
            pass

    def undo(self, text):
        """The text promising Undo (as given) when the History recorded the write; u"" when it did not."""
        return text if self.recorded else u""

    def message(self):
        """The log's error line (HTML) when something failed; u"" when nothing did."""
        parts = []
        if not self.recorded:
            parts.append(u"The font was changed, but FontLab's History did not record the change (%s): <i>Edit &gt; "
                         u"Undo</i> cannot take it back. To drop the change, close the font without saving it." %
                         html(dict(self.reasons).get("history", u"")))
        if not self.marked:
            parts.append(u"FontLab did not mark the font as modified (%s): save the font before closing it, since "
                         u"FontLab may not ask." % html(dict(self.reasons).get("modified", u"")))
        return u" ".join(parts)

    def report(self, log):
        """The error line added to a tool's log when something failed, and the font info's line when it
        was updated to match. Whether nothing failed."""
        if not self.ok and log is not None:
            try:
                log.add(self.message(), "error")
            except Exception:
                pass
        self.report_info(log)
        return self.ok


def _error_text(exc):
    try:
        return u"%s" % (exc,)
    except Exception:  # (Python 2: an error whose text is bytes that are not ASCII)
        return u"%r" % (exc,)


FONT_INFO_FILE, FONT_INFO_MODULE = "freelab_font_info.py", "freelab_font_info"


def font_info():
    """The helper module that keeps the font info in step with FreeLab's writes (freelab_font_info), or
    None. Where it is not beside this file (the tests), the one already loaded."""
    if not os.path.isfile(sibling_path(FONT_INFO_FILE)):
        return sys.modules.get(FONT_INFO_MODULE)
    try:
        return load_sibling(FONT_INFO_FILE, FONT_INFO_MODULE)
    except Exception:
        return sys.modules.get(FONT_INFO_MODULE)


def master_extents(package, glyphs):
    """[(bottom, top)] of the ink of each glyph's master layers (as Font Check measures it: components
    and color glyphs' fallback outlines included)."""
    try:
        masters = [u"%s" % name for name in package.masters]
    except Exception:
        masters = []
    found = []
    for glyph in glyphs:
        for master in masters:
            try:
                layer = glyph.getLayerByName(master)
                if layer is None:
                    continue
                path = layer_path(layer)
                if path.isEmpty():
                    continue
                rect = path.boundingRect()  # (font units grow upward: the rect's top is the ink's bottom)
                found.append((rect.top(), rect.bottom()))
            except Exception:
                continue
    return found


def _named_extents(package):
    def extents(names):
        glyphs = []
        for name in names:
            try:
                glyph = package.findName(name)
            except Exception:
                glyph = None
            if glyph is not None:
                glyphs.append(glyph)
        return master_extents(package, glyphs)
    return extents


def follow_font_info(package, log=None, when_needed=False):
    """The Win values FreeLab raised this session put back in step with the glyphs they were raised for
    (after an undo, a redo, or an edit in FontLab: the History does not take them back, though it takes
    back the Unicode ranges and code pages), its line added to the log. when_needed: only when the font's
    glyph count or place in the History says the glyphs may have changed. [Change]."""
    module, font = font_info(), _font_id(package)
    if module is None or font is None or not module.recorded(font):
        return []
    count, state = _glyph_count(package), history_state(package)
    if when_needed and not module.needs_follow(font, count, state):
        return []
    changes = []
    try:
        changes = module.follow(package.fgPackage.info, font, _named_extents(package))
    except Exception:
        changes = []
    module.note_mark(font, count, state)
    if changes:
        try:
            package.setFlag(2, True)  # ofChanged (the font info is not in the History: no step for it)
        except Exception:
            pass
        if log is not None:
            try:
                log.add(u"Put the font info back in step with the glyphs: %s." % html(module.changes_text(changes)), "done")
            except Exception:
                pass
    return changes


def _coverage_before(package):
    """The font's code points before a write that asks for the font info to follow it, its Win values first
    put in step with the glyphs (an undo made while no FreeLab window watched); None where they cannot be
    read."""
    module = font_info()
    if module is None:
        return None
    follow_font_info(package)
    try:
        return module.font_codes(package)
    except Exception:
        return None


def _update_font_info(status, package, before, glyphs):
    """After a write that asked for it: the font info's Unicode ranges and code pages the write's code
    points changed, and its Win values raised to the ink it drew (freelab_font_info), noted in status."""
    module, font = font_info(), _font_id(package)
    if module is None or before is None or font is None:
        return
    try:
        info = package.fgPackage.info
        after = module.font_codes(package)
        changes = module.apply_bits(info, font, module.coverage(before), module.coverage(after))
        names = []
        for glyph in glyphs:
            try:
                names.append(u"%s" % glyph.name)
            except Exception:
                pass
        changes += module.apply_win(info, font, master_extents(package, glyphs), names)
        status.info_changes = changes
    except Exception as exc:
        status.info_error = _error_text(exc)


def before_changes(fontlab, package, title, glyphs=(), coverage=False):
    """Called before a script changes a font, so that Undo can put back what it changes. A step of
    FontLab's History records each object as it is after the change, and Undo puts back each object's
    state before it: an object with none stays as written while the History moves back (live, on a font
    opened afresh: History 1 to 0, H's width kept). So the first write to a font in a session records
    the whole font as it is first, as a step of its own (its title followed by "(before)"), and so does
    a write after an undo past that step; later writes need none, since each records the whole font.
    The glyphs given are recorded too when they have no state: the whole font's record holds their
    layers, not the glyphs themselves (their flags). The glyph count is noted for notify_changed. The
    objects recorded, as a list (empty when none had to be). Raises HistoryError, before anything is
    changed, when FontLab could not record them: the caller must then write nothing (begin_write).
    coverage: a write that adds glyphs or code points, whose code points are read now so that
    notify_changed can update the font info to match (_update_font_info)."""
    held = _history()
    font = _font_id(package)
    held["counts"][font] = _glyph_count(package)
    if coverage:
        held.setdefault("coverage", {})[font] = _coverage_before(package)
    objects = []
    if font not in held["whole"] or _without_state(package):
        objects.append(package)
    objects.extend(glyph for glyph in glyphs if _without_state(glyph))
    if objects:
        try:
            fontlab.flItems.notifyChangesApplied(u"%s (before)" % title, objects, True)
        except Exception as exc:
            held["counts"].pop(font, None)
            held.setdefault("coverage", {}).pop(font, None)
            raise HistoryError(u"Nothing was changed: FontLab's History could not record the font before the change "
                               u"(%s), so <i>Edit &gt; Undo</i> could not have taken it back." % html(_error_text(exc)))
        if objects[0] is package:
            held["whole"].add(font)
    return objects


def begin_write(fontlab, package, title, log, glyphs=(), coverage=False):
    """before_changes for a tool: True when the write may go ahead; False, with the reason in its log
    (as an error), when FontLab's History could not record the font first and nothing may be written."""
    try:
        before_changes(fontlab, package, title, glyphs, coverage)
        return True
    except HistoryError as exc:
        if log is not None:
            try:
                log.add(_error_text(exc), "error")
            except Exception:
                pass
        return False


def notify_changed(fontlab, package, title, glyphs=(), added=None, coverage=False):
    """FontLab told of a script's changes, as one step of its History, and its windows redrawn; the
    write began with before_changes, so that Undo has something to go back to.

    The step records the whole font (notifyChangesApplied's third argument: its objects and theirs),
    and the glyphs given (their own state, such as their flag, is not in the font's): a step that
    recorded only the glyphs it changed left the font's list of glyphs out, and undoing a later step
    then put back a list without the glyphs a script had added (and FontLab complained of the
    components it could not find). Recording the whole font costs little (0.26 s more than one glyph
    on 9,505 glyphs, live). notifyPackageContentUpdated takes the font's fontgate id (fgPackage.id):
    given flPackage.id, PyCXX cannot pass it as an int. Without it, the Font window does not show glyphs
    a script added; it is called only when glyphs were added or removed (added; None: the glyph count
    differs from the one before_changes noted, or none was), since each call checks the clipboard
    twice. The font is marked modified: a script's writes leave it unmarked, and FontLab would close it
    without asking to save. A WriteStatus: whether the History recorded the step and the font was
    marked (a caller promises Undo only through status.undo, and status.report logs a failure); the
    redraws (glyph.update, notifyPackageContentUpdated) are not part of it.

    coverage: the write began with before_changes' coverage, and the glyphs given are those it drew: the
    font info is updated to match (_update_font_info: its Unicode ranges and code pages, its Win values),
    in status.info_changes, which status.report logs. FontLab's History does not cover the font info: the
    changes are kept so that follow_font_info puts them back in step after an undo."""
    status = WriteStatus()
    glyphs = list(glyphs)
    for glyph in glyphs:
        try:
            glyph.update()
        except Exception:
            pass  # (a redraw)
    held, font = _history(), _font_id(package)
    if coverage:  # (a step of the write's own before it, such as Glyph Compose's parts, leaves the codes read)
        _update_font_info(status, package, held.setdefault("coverage", {}).pop(font, None), glyphs)
    try:
        fontlab.flItems.notifyChangesApplied(title, [package] + glyphs if glyphs else package, True)
        held["whole"].add(font)
    except Exception as exc:
        status.recorded = False
        status.reasons.append(("history", _error_text(exc)))
        held["whole"].discard(font)  # (the next write records the font first again)
    if coverage:
        module = font_info()
        if module is not None and font is not None:  # (where the font stands once the write is in the History)
            # (a write the font info follows: one that changed it, or any while FreeLab's raises are recorded, as
            # its glyphs may be among those they rely on: freelab_font_info.apply_win)
            module.note_mark(font, _glyph_count(package), history_state(package),
                             wrote=bool(status.info_changes) or module.recorded(font))
    before = held["counts"].pop(font, None)
    if added is None:
        added = before is None or before != _glyph_count(package)
    if added:
        try:
            fontlab.flItems.notifyPackageContentUpdated(package.fgPackage.id)
        except Exception:
            pass  # (a redraw: the Font window's list)
    try:
        package.setFlag(2, True)  # ofChanged
    except Exception as exc:
        status.marked = False
        status.reasons.append(("modified", _error_text(exc)))
    return status


def history_state(package):
    """The font's place in FontLab's History (it changes with each step, undo, and redo), or None."""
    try:
        return package.currentHistoryState()
    except Exception:
        return None


# Scripts > FreeLab, in the order a font is usually made, then dark mode, then FreeLab MCP's: FontLab
# lists a folder's scripts by file name and has no separators of its own.
# The font tools in the order of the work, which the menu, each window's tools button, and its arrows
# follow: the glyphs built (Glyph Compose), spaced, kerned, the features written, then the result
# compared, checked (Font Check), and proofed.
MENU_GROUPS = (("Font Builder", "Glyph Compose", "Auto Spacing", "CJK Spacing", "CJK Vertical", "Auto Kerning", "Kerning Check",
                "Feature Code", "Feature Check", "Font Compare", "Family Audit", "Font Check", "Proof"),
               ("Dark Mode", "Toggle Dark Mode", "Dark Mode Settings", "Tab Docking", "Toggle Tab Docking"),
               ("Start MCP Listener", "Stop MCP Listener", "Start Listener", "Stop Listener"))  # (FreeLab MCP's, old names too)
MENU_TITLE, SCRIPTS_MENU = "FreeLab", "menuScripts"
MENU_ORDER_PROP = "freelab_menu_order"
MENU_HOOK_VERSION = 7  # the Scripts menu's property holds it: an older hook found there is replaced


def menu_order(texts, groups=MENU_GROUPS):
    """The texts in the groups' order, None between groups; any text no group names goes last."""
    order = []
    known = set(text for group in groups for text in group)
    rest = [text for text in texts if text not in known]
    for group in list(groups) + [tuple(rest)]:
        present = [text for text in group if text in texts]
        if present:
            if order:
                order.append(None)
            order.extend(present)
    return order


# The menu's switches, ticked while on: their text, and the state FreeLab keeps for them in sys.
MENU_SWITCHES = {u"Dark Mode": "_freelab_dark_mode", u"Toggle Dark Mode": "_freelab_dark_mode",
                 u"Tab Docking": "_freelab_tabs_state", u"Toggle Tab Docking": "_freelab_tabs_state"}


def tick_switches(menu):
    """Dark mode and tab docking ticked in the menu while they are on."""
    for action in menu.actions():
        holder = MENU_SWITCHES.get(action.text.replace(u"&", u""))
        if holder is None:
            continue
        state = getattr(sys, holder, None) or {}
        action.setCheckable(True)
        action.setChecked(bool(state.get("on")))


def arrange_menu(menu):
    """Puts a FreeLab menu's actions in menu_order, with separators between the groups; nothing
    changes when they are in order already. The switches are ticked while on."""
    try:
        tick_switches(menu)
    except Exception:
        pass
    actions = list(menu.actions())
    current = [None if action.isSeparator() else action.text.replace(u"&", u"") for action in actions]
    by_text = dict((action.text.replace(u"&", u""), action) for action in actions if not action.isSeparator())
    wanted = menu_order([text for text in current if text is not None])
    if current == wanted:
        return False
    for action in actions:
        menu.removeAction(action)
    for text in wanted:
        if text is None:
            menu.addSeparator()
        else:
            menu.addAction(by_text[text])
    return True


def hook_menu_order():
    """Arranges Scripts > FreeLab each time the Scripts menu opens (FontLab builds the submenu anew on
    Refresh Scripts). Called at startup by FreeLab's block of FontLab's startup script, and by each
    FreeLab script as it opens.

    The handler finds arrange_menu in the module loaded last, and holds on to its own: Python 2
    empties a module's globals (to None) once nothing holds the module, and a script loaded again
    (after a reinstall) replaces it in sys.modules. The first hook held nothing, and stopped working
    silently after a reinstall."""
    QtCore, QtGui = _qt()
    main = AutoKerningDialog.main_window()
    if main is None:
        return False
    scripts = None
    for menu in main.findChildren(QtGui.QMenu):
        if menu.objectName == SCRIPTS_MENU:
            scripts = menu
            break
    if scripts is None:
        return False
    try:
        version = int(scripts.property(MENU_ORDER_PROP) or 0)
    except (TypeError, ValueError):
        version = 1  # the first hook set True
    if version >= MENU_HOOK_VERSION:
        return False
    holder = [sys.modules.get(__name__), arrange_menu]

    def arrange_latest(submenu):
        latest = sys.modules.get(__name__)
        (getattr(latest, "arrange_menu", None) or holder[1])(submenu)

    def shown():
        try:
            for action in scripts.actions():
                submenu = action.menu()
                if submenu is not None and action.text.replace(u"&", u"") == MENU_TITLE:
                    arrange_latest(submenu)
                    # FontLab may fill the submenu again after this (Refresh Scripts builds it anew, its
                    # actions added as it opens): arranged again as the submenu itself opens
                    if not submenu.property(MENU_ORDER_PROP):
                        slot = lambda menu=submenu: submenu_shown(menu)
                        holder.append(slot)  # (held: PythonQt drops a slot no Python object holds)
                        submenu.connect("aboutToShow()", slot)
                        submenu.setProperty(MENU_ORDER_PROP, MENU_HOOK_VERSION)
        except Exception:
            pass  # a signal handler must not raise

    def submenu_shown(menu):
        try:
            arrange_latest(menu)
        except Exception:
            pass

    scripts.connect("aboutToShow()", shown)
    scripts.setProperty(MENU_ORDER_PROP, MENU_HOOK_VERSION)
    sys._freelab_menu_order = (shown, holder)  # kept: PythonQt drops a slot no Python object holds
    shown()
    return True


FONT_TOOLS = MENU_GROUPS[0]  # what the tools button of each FreeLab window lists (not dark mode, not FreeLab MCP)
_TOOL_BUTTONS = []  # each tools button with its menu and slots, held


# ---------------------------------------------------------------------------
# One window for each open font
#
# The font tools are the steps of one job on one font, so each open font has one FreeLab window: a tool
# opened for a font takes the place (and the size) of the tool that font's window showed, the way a
# step follows another, and the window's title names its font. A window works on the font it was
# opened for, whichever font FontLab shows since: two fonts open side by side each keep their own, and
# a window closes with its font (fonts_tick). A window opened with no font open waits for one, and
# takes the next font opened.
# sys._freelab_windows holds them: {"fonts": {FontLab's number of the font: the tool's dialog object},
# "next": a counter, "hint": (font number, time, window number) for a tool about to be opened from a
# window, "kept": every tool's dialog object shown, "theme": the colors the windows were last drawn in}.
# ---------------------------------------------------------------------------

WINDOW_PROP = "freelab_window"  # on a tool's window: its number in sys._freelab_windows
HINT_SECONDS = 3.0  # how long a window's "the next tool opens on my font" holds


def _windows():
    held = getattr(sys, "_freelab_windows", None)
    if held is None:
        held = sys._freelab_windows = {"fonts": {}, "next": 0, "hint": None}
    return held


def _font_id(package):
    """FontLab's own number for an open font, the same through every Python wrapper of it (two reads
    of currentPackage give two wrappers); None where it cannot be read."""
    try:
        return package.fgPackage.id
    except Exception:
        return None


def find_font(workspace, font_id):
    """The open font FontLab numbers font_id, or None (closed since, or no number given). The
    workspace lists its fonts as plain objects: each is wrapped to be read."""
    if font_id is None:
        return None
    try:
        import fontlab
        listed = workspace.packages()
    except Exception:
        return None
    for item in listed:
        try:
            package = fontlab.flPackage(item)
            if package.fgPackage.id == font_id:
                return package
        except Exception:
            continue
    return None


def open_font_ids(workspace):
    """FontLab's numbers of the open fonts, in its order ([] when none is open; FontLab still hands a
    placeholder package then, which is no font); None when the workspace cannot be read."""
    try:
        import fontlab
        listed = workspace.packages()
    except Exception:
        return None
    found = []
    for item in listed or []:
        try:
            found.append(fontlab.flPackage(item).fgPackage.id)
        except Exception:
            continue
    return found


def fonts_open(fontlab=None):
    """Whether FontLab has a font open (True when it cannot tell): a tool's button that reads a font is
    clickable only then."""
    try:
        if fontlab is None:
            import fontlab
        found = open_font_ids(fontlab.flWorkspace.instance())
    except Exception:
        return True
    return found is None or bool(found)


def font_gone(owner, open_ids):
    """Whether the font a window was opened for has been closed (open_ids: open_font_ids; None, when
    FontLab cannot tell, is no news). A window opened with no font has none to lose."""
    font_id = getattr(owner, "font_id", None)
    return font_id is not None and open_ids is not None and font_id not in open_ids


def _owners():
    """Every tool's dialog object shown by its window's number: the fonts' windows, and a window that is
    not its font's (a window without a font, while another waits too)."""
    registry = _windows()
    found = {}
    for owner in list(registry.get("kept", [])) + list(registry["fonts"].values()):
        key = getattr(owner, "window_key", None)
        if key is not None:
            found[key] = owner
    return found


def widget_alive(widget):
    """Whether a Qt object is still there: PythonQt raises for a deleted one (never so for a list's items,
    which are no Qt objects: re-enumerate those from a live list)."""
    if widget is None:
        return False
    try:
        widget.metaObject()
        return True
    except Exception:
        return False


def _shown(owner):
    try:
        return bool(owner.dialog.isVisible())
    except Exception:
        return False  # (FontLab deleted it)


def window_owner(widget):
    """The tool (its dialog object) whose window this widget is, or is a dialog of; None for any other."""
    owners = _owners()
    tries = 0
    while widget is not None and tries < 8:
        try:
            key = widget.property(WINDOW_PROP)
            if key is not None and int(key) in owners:
                return owners[int(key)]
            widget = widget.parentWidget()
        except Exception:
            return None
        tries += 1
    return None


def calling_font():
    """The number of the font a tool is being opened for from another tool's window (its tools button,
    its arrows, a button handing glyphs over): that window's font, not the one FontLab shows. None when
    it is opened from FontLab's menu, or from a window without a font.

    Only FreeLab's own controls say so, through the hint (opening_from), never the window that has the
    focus: a tool opened from FontLab's menu while a FreeLab window was still the active one (another
    font's) opened on that window's font, in its place (live 2026-11-16: the font tabs switched by a
    script, FontLab showing Bellefair, Font Check opened on Varela Round and replaced its window)."""
    hint = _live_hint()
    return hint[0] if hint is not None else None


def _live_hint():
    """The hint, while it holds: a scoped one (opening_from) until its block ends, however long the tool
    takes to open (Codex's review: a tool slower than HINT_SECONDS to load lost its caller and opened on the
    font FontLab shows); one noted alone (note_caller) for HINT_SECONDS."""
    hint = _windows().get("hint")
    if hint is None:
        return None
    if len(hint) > 3 and hint[3]:
        return hint
    return hint if time.time() - hint[1] <= HINT_SECONDS else None


def calling_owner():
    """The tool (its dialog object) whose window a tool is being opened from (its tools button, its
    arrows, a button handing glyphs over), or None when it is opened from FontLab's menu: the window
    clicked, which the new tool replaces, whether or not it is its font's window in the registry. Only
    from the hint, as calling_font."""
    hint = _live_hint()
    if hint is not None:
        return _owners().get(hint[2]) if len(hint) > 2 else None
    return None


def note_caller(widget, scoped=False):
    """A FreeLab control about to open another tool (a window's tools button, its arrows, a button that
    hands glyphs over): the tool opens on that window's font, in its place (calling_font, calling_owner).
    The tool (its dialog object) whose window it is, or None (nothing noted: the tool then opens as from
    FontLab's menu)."""
    owner = window_owner(widget) if widget is not None else None
    if owner is not None:
        _windows()["hint"] = (getattr(owner, "font_id", None), time.time(), getattr(owner, "window_key", None),
                              bool(scoped))
    return owner


def forget_caller():
    """The hint let go once the tool it was for has opened (or failed to): a menu click after it is a menu
    click, never a click in that window."""
    _windows()["hint"] = None


class opening_from(object):
    """with opening_from(widget): a tool opened inside the block is opened from widget's window (its font,
    its place: note_caller), as FreeLab's own controls open tools, however long it takes to open; the hint
    is let go when the block ends, an error or not (the one before put back: a block inside another)."""

    def __init__(self, widget):
        self.widget, self.before = widget, None

    def __enter__(self):
        self.before = _windows().get("hint")
        if note_caller(self.widget, scoped=True) is None:
            _windows()["hint"] = None  # (no FreeLab window: a tool opened here opens as from FontLab's menu)
        return self

    def __exit__(self, *exc):
        _windows()["hint"] = self.before if self.before is not None and len(self.before) > 3 and self.before[3] \
            else None
        return False


def _move_window(owner, old_id, new_id):
    """A window that now works on another font (new_id): it is that font's window in the registry,
    unless the font has a window of its own already, shown (one window per font: that one stays the
    font's; this one is still found by its number, and a tool opened from it replaces it)."""
    fonts = _windows()["fonts"]
    if fonts.get(old_id) is owner:
        del fonts[old_id]
    if new_id is None or getattr(owner, "window_key", None) is None:
        return  # (a tool reading its font before its window is taken: take_window registers it)
    held = fonts.get(new_id)
    if held is None or held is owner or not _shown(held):
        fonts[new_id] = owner


def window_font(owner, workspace):
    """The font a tool's window works on: the one it was opened for (first read: the calling window's
    font, else FontLab's current one). The window's title follows, and the registry (a window opened
    with no font open is its font's window once it reads one). FontLab's own package when nothing is
    open (callers test it as before): the window is then one without a font, and takes the next font
    opened. None once its font is closed: the window closes with it (fonts_tick), and meanwhile works
    on no font, never on another (it moved to the font FontLab showed, and could make two windows for
    one font)."""
    font_id = getattr(owner, "font_id", None)
    open_ids = open_font_ids(workspace)
    if font_gone(owner, open_ids):
        return None
    if open_ids == []:
        owner.font_id = None  # (a window opened with no font: it has none to lose)
        title_window(owner, None)
        return workspace.currentPackage
    package = find_font(workspace, font_id)
    if package is None:
        if font_id is not None:
            return None  # (FontLab's fonts could not be read: never another font in its place)
        package = find_font(workspace, calling_font()) or workspace.currentPackage
        found = _font_id(package)
        held = _windows()["fonts"].get(found) if found is not None else None
        if (getattr(owner, "window_key", None) is not None and held is not None and held is not owner
                and _shown(held)):
            # A window without a font, shown (it waits for the next font: fonts_tick), never takes a font that
            # has a window of its own: it would be a second window on it. It works on no font meanwhile.
            title_window(owner, None)
            return None
        if found is not None:
            _move_window(owner, None, found)
        owner.font_id = found
    title_window(owner, package)
    return package


def foreign_font(owner, fontlab=None):
    """The name of the font a tool's window works on when FontLab shows another font, else None (that
    font, no window, or nothing to tell). FontLab's own commands (Undo, Redo, a new Glyph tab) act on
    the font it shows: callers show the window's font first (focus_font), and refuse, naming the font to
    click, only when that fails."""
    try:
        font_id = getattr(owner, "font_id", None)
        if font_id is None:
            return None
        if fontlab is None:
            import fontlab
        workspace = fontlab.flWorkspace.instance()
        current = _font_id(workspace.currentPackage)
        if current is None or current == font_id:
            return None
        package = find_font(workspace, font_id)
        if package is None:
            return None  # its font was closed: the window closes with it (fonts_tick)
        return u"%s" % (package.tfn or u"its font")
    except Exception:
        return None


def font_shown(owner, fontlab=None):
    """Whether FontLab shows the font of a tool's window, as FontLab's current font says positively (True for no
    window, or a window with no font: nothing to tell apart). False when the window's font is another, is closed,
    or when the font FontLab shows cannot be read."""
    try:
        font_id = getattr(owner, "font_id", None)
        if font_id is None:
            return True
        if fontlab is None:
            import fontlab
        current = _font_id(fontlab.flWorkspace.instance().currentPackage)
        return current is not None and current == font_id
    except Exception:
        return False


def own_font_refusal(owner, fontlab=None):
    """None when FontLab shows the font of a tool's window, shown first where it showed another (focus_font):
    FontLab's own commands (Undo, Redo, a new Glyph tab) may then run. Else why they must not, as they act on the
    font FontLab shows: the name of the window's font, which FreeLab could not show, or u"" when that font is
    closed or FontLab's current font cannot be read. A window whose font cannot be found never lets a command
    act on the font in front (adversarial review 4: foreign_font's None for a closed font let Undo do so)."""
    if font_shown(owner, fontlab):
        return None
    foreign = foreign_font(owner, fontlab)
    if foreign is None:
        return u""  # (closed, or not to be told: refused all the same)
    if focus_font(owner, fontlab) and font_shown(owner, fontlab):
        return None
    return foreign


FONT_WINDOW_CLASS = "FontWindow"  # the class of a font's Font window, a tab of FontLab's main window


def _main_tab_widgets(main):
    """The tab widgets of FontLab's main window that hold its Font and Glyph windows (YTabWidget), the
    ones docked in the main window first."""
    QtGui = _qt()[1]
    found = []
    try:
        for widget in main.findChildren(QtGui.QTabWidget):
            if widget.inherits("YTabWidget") or u"%s" % widget.className() == u"YTabWidget":
                found.append(widget)
    except Exception:
        return []
    return found


def focus_font(owner, fontlab=None):
    """Whether FontLab shows the font of a tool's window now: when it shows another, the main window's
    tab of that font's Font window is made the current one (as a click on it would), the tab whose
    title names the font tried first, each checked by FontLab's current font (live, 2026-11-18: the
    current font follows the tab at once). The tab shown before is put back when none is that font's.
    Undo, Redo, and a new Glyph tab then act on the window's font instead of refusing (owner's image
    314: "can't the script suite in general refocus on the right font in such cases?")."""
    try:
        font_id = getattr(owner, "font_id", None)
        if font_id is None:
            return True
        if fontlab is None:
            import fontlab
        workspace = fontlab.flWorkspace.instance()
        if _font_id(workspace.currentPackage) == font_id:
            return True
        package = find_font(workspace, font_id)
        main = AutoKerningDialog.main_window()
        if package is None or main is None:
            return False
        name = (u"%s" % (package.tfn or u"")).strip()
    except Exception:
        return False
    for tabs in _main_tab_widgets(main):
        try:
            before = int(_property(tabs, "currentIndex"))
            fonts = [k for k in range(int(_property(tabs, "count")))
                     if tabs.widget(k) is not None and tabs.widget(k).inherits(FONT_WINDOW_CLASS)]
        except Exception:
            continue
        named = [k for k in fonts if name and name in (u"%s" % tabs.tabText(k))]
        for k in named + [k for k in fonts if k not in named]:
            try:
                tabs.setCurrentIndex(k)
                if _font_id(workspace.currentPackage) == font_id:
                    return True
            except Exception:
                continue
        try:
            if int(_property(tabs, "currentIndex")) != before:
                tabs.setCurrentIndex(before)
        except Exception:
            pass
    return False


def title_window(owner, package):
    """The window's title with its font's name in parentheses: "FreeLab Proof (Cardo)"."""
    try:
        dialog = owner.dialog
        base = getattr(owner, "window_title", None)
        if not base:
            base = u"%s" % (_property(dialog, "windowTitle") or u"")
            if not base:
                return
            owner.window_title = base
        name = None
        if package is not None and not package.isNull and package.glyphsCount:
            name = package.tfn
        title = u"%s (%s)" % (base, name) if name else base
        if _property(dialog, "windowTitle") != title:
            dialog.setWindowTitle(title)
    except Exception:
        pass


def _bring_forward(dialog):
    if _property(dialog, "minimized"):
        dialog.showNormal()
    dialog.raise_()
    dialog.activateWindow()


def raise_open(tool):
    """True when the font a tool is being opened for already shows that tool in its window: brought
    forward as it is (opened anew, it would lose its checks and its log). A tool's main() asks first,
    unless it was handed something to show."""
    try:
        import fontlab
        registry = _windows()
        font_id = calling_font()
        if font_id is None:
            workspace = fontlab.flWorkspace.instance()
            if open_font_ids(workspace):
                font_id = _font_id(workspace.currentPackage)  # (none open: the window without a font)
        owner = registry["fonts"].get(font_id)
        if owner is None or not _shown(owner):
            owner = registry["fonts"].get(None)  # a window without a font takes the next font opened
        if owner is None or getattr(owner, "tool", None) != tool or not owner.dialog.isVisible():
            return False
        registry["hint"] = None
        _bring_forward(owner.dialog)
        return True
    except Exception:
        return False


def _size(dialog):
    return int(_property(dialog, "width")), int(_property(dialog, "height"))


def _xy(point):
    """(x, y) of a QPoint, or of an (x, y) pair."""
    try:
        return int(point.x()), int(point.y())
    except AttributeError:
        return int(point[0]), int(point[1])


def note_size(owner):
    """A window resized by hand: its size is the owner's own for the rest of the session. Every tool's
    window opens at it, for every font. It is not kept for later sessions (the owner could never get
    back to the tools' own sizes): FreeLab no longer writes windows.json, and one written by an
    earlier version is not read. A window left at the size it opened at says nothing: each tool then
    opens at its own (Font Check wider than the others, for its two lists)."""
    try:
        dialog = owner.dialog
        if _property(dialog, "minimized") or _property(dialog, "maximized"):
            return
        size, opened = _size(dialog), getattr(owner, "opened_size", None)
        if opened is not None and (abs(size[0] - opened[0]) > 2 or abs(size[1] - opened[1]) > 2):
            _windows()["size"] = owner.opened_size = size
    except Exception:
        pass


def centered_place(place, size, new_size, area=None, frame=(0, 0)):
    """Where a window of new_size goes to take the place of one of size whose frame stood at place:
    around the same center, so a tool wider than the one before grows by as much on each side (it grew
    from the left edge, all of it to the right). Kept inside area (left, top, right, bottom: the
    screen's free part) when given; frame: what the title bar and borders add to the size."""
    x = place[0] + (size[0] - new_size[0]) // 2
    y = place[1] + (size[1] - new_size[1]) // 2
    if area is not None:
        left, top, right, bottom = area
        x = max(left, min(x, right - new_size[0] - frame[0]))
        y = max(top, min(y, bottom - new_size[1] - frame[1]))
    return x, y


SHARE_PROP = "freelabShare"  # on a splitter's pane: its share of the splitter's height at first (share_splitters)
SHARED_PROP = "freelabShared"  # on a splitter once share_splitters has given its panes their shares


def shares_of(total, shares):
    """The heights of panes sharing total pixels by their shares (None: a pane left as it is, taking none)."""
    whole = float(sum(s for s in shares if s)) or 1.0
    sizes = [int(total * s / whole) if s else 0 for s in shares]
    if sizes:
        last = max(range(len(sizes)), key=lambda k: shares[k] or 0)
        sizes[last] += total - sum(sizes)
    return sizes


def share_splitters(window):
    """Each splitter of a window whose panes carry their shares (SHARE_PROP) given heights in those shares, once,
    as the window first shows: stretch factors only share what is left over the panes' own sizes, so a preview
    of large text took the window and the list above it showed one row (live, 2026-11-18, CJK Spacing and
    Feature Code's third tab). Sized on the next turn of the event loop, once laid out; never raises."""
    QtCore, QtGui = _qt()

    def share():
        try:
            for splitter in window.findChildren(QtGui.QSplitter):
                if splitter.property(SHARED_PROP):
                    continue
                count = splitter.count()
                panes = [splitter.widget(k) for k in range(count)]
                shares = [p.property(SHARE_PROP) if p is not None else None for p in panes]
                if not any(shares):
                    continue
                total = sum(int(size) for size in splitter.sizes())
                if total <= 0:
                    continue
                splitter.setProperty(SHARED_PROP, True)
                splitter.setSizes(shares_of(total, [int(s) if s else 0 for s in shares]))
        except Exception:
            pass

    held = getattr(sys, "_freelab_share_slots", None)
    if held is None:
        held = sys._freelab_share_slots = []
    held.append(share)  # (held: PythonQt drops a slot no Python object holds)
    del held[:-8]
    QtCore.QTimer.singleShot(0, share)


def keep_center(owner):
    """A window that took another's place (register_window: owner.placed_from, the other's place and
    size), centered again on that window's center as it first shows: it was placed at the size asked for,
    and Qt then grew it to its layout's least width, all of it to the right, so going from tool to tool
    with the arrows walked the windows off to the right of the screen (owner's image 311). Once."""
    try:
        place = getattr(owner, "placed_from", None)
        if place is None:
            return
        owner.placed_from = None
        dialog = owner.dialog
        area, frame = _free_area(dialog)
        x, y = centered_place(place[0], place[1], _size(dialog), area, frame)
        if (x, y) != _xy(_property(dialog, "pos")):
            dialog.move(x, y)
    except Exception:
        pass


def _free_area(dialog):
    """The free part of the dialog's screen, (left, top, right, bottom), and what its frame adds to its
    size; (None, (0, 0)) where Qt cannot tell."""
    try:
        rect = _qt()[1].QApplication.desktop().availableGeometry(dialog)
        area = (rect.left(), rect.top(), rect.right() + 1, rect.bottom() + 1)
    except Exception:
        return None, (0, 0)
    try:
        frame = _property(dialog, "frameGeometry")
        extra = (max(0, frame.width() - int(_property(dialog, "width"))),
                 max(0, frame.height() - int(_property(dialog, "height"))))
    except Exception:
        extra = (0, 0)
    return area, extra


OPENED_MS = 250  # after a window is shown, when the size it opened at is read (note_size)
OPENED_TRIES = 8  # (read again this many times while it is not shown yet)


def measure_opened(owner, tries=OPENED_TRIES):
    """The size a window opened at (note_size compares with it), read once it is shown and laid out: Qt
    grows a window to its layout's least size as it shows it, and a size read before that was taken
    for one given by hand."""
    QtCore = _qt()[0]

    def measure():
        try:
            if getattr(owner, "opened_size", None) is not None:
                return
            if _property(owner.dialog, "visible"):
                owner.opened_size = _size(owner.dialog)
            elif tries > 1:
                measure_opened(owner, tries - 1)
        except Exception:
            pass  # (a timer's handler must not raise; FontLab may have deleted the window)

    owner.measure_slot = measure  # (PythonQt drops what no Python object holds)
    QtCore.QTimer.singleShot(OPENED_MS, measure)


def grip_resized(window, before):
    """The log's grip made the window taller or shorter (from its height before): the size it opened at
    moves with it, so that only a size given by hand at the window's edges counts (note_size)."""
    try:
        owner = window_owner(window)
        opened = getattr(owner, "opened_size", None)
        if opened is not None:
            owner.opened_size = (opened[0], opened[1] + int(_property(window, "height")) - int(before))
    except Exception:
        pass


def close_tool_windows(*args):
    """Every FreeLab tool window still shown, closed (as its close button does; nothing deleted)."""
    registry = _windows()
    for owner in list(registry.get("kept", [])) + list(registry["fonts"].values()):
        try:
            if owner.dialog.isVisible():
                owner.dialog.close()
        except Exception:
            pass  # (FontLab deleted it; a slot must not raise)


def hook_quit():
    """Once a session: FreeLab's windows close when FontLab quits, or when its last window that ends the
    session (its main window) is closed. Each is a window of its own (_own_window), which Qt counts as
    keeping the application open: one left open kept FontLab running, the tool alone on screen, after
    FontLab's window was closed. They are marked not to count (WA_QuitOnClose), and closed here."""
    if getattr(sys, "_freelab_quit_hook", None) is not None:
        return
    try:
        app = _qt()[1].QApplication.instance()
        slot = lambda *args: close_tool_windows()
        app.connect("aboutToQuit()", slot)
        app.connect("lastWindowClosed()", slot)
        sys._freelab_quit_hook = slot  # (held: PythonQt drops a slot no Python object holds)
    except Exception:
        pass


FONTS_POLL_MS = 700  # how often FreeLab looks whether a window's font was closed, or a font opened
NO_FONT_LINE = u"No font is open. This window hooks to the next font you open."  # a tool's top line meanwhile
NOT_AVAILABLE = u"n/a"  # what a dropdown or a name that would be empty with no font shows (owner's images 289, 290)


def no_font_line(own=None, workspace=None):
    """A tool's top line while its window has no font: own (the tool's words, else NO_FONT_LINE) while no
    font is open. While fonts are open, the window waits (window_font: it never takes a font that has a
    window of its own), and the line says why, counted: never "No font is open" then."""
    try:
        if workspace is None:
            import fontlab
            workspace = fontlab.flWorkspace.instance()
        open_ids = open_font_ids(workspace)
    except Exception:
        open_ids = None
    if not open_ids:
        return own or NO_FONT_LINE
    fonts = _windows()["fonts"]
    held = [font_id for font_id in open_ids if fonts.get(font_id) is not None and _shown(fonts[font_id])]
    if len(held) == len(open_ids):
        if len(open_ids) == 1:
            return u"This window has no font: the font open has a window of its own. It hooks to the next font you open."
        return (u"This window has no font: the %d fonts open each have a window of their own. It hooks to the next "
                u"font you open." % len(open_ids))
    try:
        name = workspace.currentPackage.tfn
    except Exception:
        name = None
    shown = u"%s, the font FontLab shows," % b(name) if name else u"The font FontLab shows"
    return (u"This window has no font: %s has a window of its own. It hooks to the next font you open, or to a "
            u"font without a window once FontLab shows it." % shown)


def font_switched(owner):
    """A window without a font took one (opened since): the tool shows it through its font_changed().
    A tool without one keeps what it shows until it reads its font again (its title has changed
    already)."""
    changed = getattr(owner, "font_changed", None)
    if changed is not None:
        changed()


def fonts_tick(workspace=None):
    """Each shown FreeLab window, as fonts open and close: one whose font was closed closes with it
    (the owner: "I'd suggest closing the script window along with the font it belongs to"; it moved
    to the font FontLab showed, which could leave two windows on one font), and is let go
    (release_window); a window opened with no font takes the font FontLab shows (the one just opened)
    once one is open, unless that font has a window of its own shown. A busy window is looked at next
    time. Returns the windows that changed (closed, or given a font)."""
    if workspace is None:
        import fontlab
        workspace = fontlab.flWorkspace.instance()
    open_ids = open_font_ids(workspace)
    if open_ids is None:
        return []
    fonts = _windows()["fonts"]
    changed = []
    for _, owner in sorted(_owners().items(), key=lambda pair: pair[0]):
        if not _shown(owner) or getattr(owner, "busy", False):
            continue
        font_id = getattr(owner, "font_id", None)
        if font_gone(owner, open_ids):
            try:
                owner.dialog.close()  # (as its close button does: finished, then let go)
            except Exception:
                pass  # (FontLab deleted it)
            changed.append(owner)
            continue
        elif font_id is None and open_ids:
            current = _font_id(workspace.currentPackage)
            target = current if current in open_ids else open_ids[0]
            held = fonts.get(target)
            if held is not None and held is not owner and _shown(held):
                continue  # (that font has its own window: this one stays without a font)
            _move_window(owner, None, target)
            owner.font_id = target
            title_window(owner, find_font(workspace, target))
        else:
            continue
        changed.append(owner)
        try:
            font_switched(owner)
        except Exception:
            pass  # (one tool's refresh failing leaves the others theirs)
    return changed


def watch_fonts():
    """Once a session: fonts_tick every FONTS_POLL_MS, through the module loaded last (a reinstall
    replaces it in sys.modules, and Python 2 empties a dropped module's globals). FontLab's Scripts
    menu cannot gray out a tool that needs a font, so a window follows the fonts instead."""
    if getattr(sys, "_freelab_font_watch", None) is not None:
        return
    QtCore = _qt()[0]
    modules, name, own = sys.modules, __name__, fonts_tick

    def tick():
        try:
            (getattr(modules.get(name), "fonts_tick", None) or own)()
        except Exception:
            pass  # a timer's handler must not raise
        try:  # (a switch dark mode did not announce: theme_tick)
            module = modules.get(name)
            if module is not None and getattr(module, "theme_tick", None) is not None:
                module.theme_tick()
        except Exception:
            pass

    timer = QtCore.QTimer()
    timer.setInterval(FONTS_POLL_MS)
    timer.connect("timeout()", tick)
    timer.start()
    sys._freelab_font_watch = (timer, tick)  # (held: PythonQt drops what no Python object holds)


# ---------------------------------------------------------------------------
# Following dark mode as it switches
#
# Dark mode changes FontLab's palette and style, then tells FreeLab (sys._freelab_theme_hook, set
# here, called by dark mode once it has switched either way); the windows' own tick notices a switch
# it did not announce (theme_tick). Each shown FreeLab window then follows at once (retheme_window):
# - its widgets polished again: Qt 5 polishes a widget under a stylesheet (on it or on a parent)
#   with the palette of that moment, and dark mode sets the style (which polishes) before the
#   palette, so such widgets kept the theme before the switch: dark cells and pale labels in light
#   mode, light ones in dark mode that dark mode's mapping then garbled (owner's screenshots 76 and
#   77; seen in Qt 5.15 offscreen, any number of switches, both ways);
# - its pictures drawn in one palette color (inked: glyph pictures, pair previews, the tools
#   button's lines) drawn again in that role's new color;
# - its items' text and background colors that are a palette color, or a log color for the other
#   background (LOG_COLORS), given the new one;
# - its logs written again in the new colors (Log.restyle);
# - and the tool's own theme_changed(), for what it draws in several colors.
# ---------------------------------------------------------------------------

THEME_ROLES = ("WindowText", "Text", "ButtonText", "HighlightedText", "Window", "Base", "Button", "Highlight",
               "AlternateBase", "Mid", "Dark", "Light")  # (text roles first: they win where two share a color)
INKED_MAX = 50000  # pictures remembered with their color at most (the oldest forgotten first)
# A one-color picture's cacheKey: (its color, the order it came in). Held in sys: each tool may hold its
# own copy of this module (loaded again after a reinstall), and the one that follows a switch must
# find every tool's pictures
_INKED = getattr(sys, "_freelab_inked", None)
if _INKED is None:
    _INKED = sys._freelab_inked = {}
_INKED_ORDER = [max([0] + [entry[1] for entry in _INKED.values()])]


def _rgb(color):
    """(r, g, b) of a QColor, or of an (r, g, b[, a]) tuple."""
    try:
        return (int(color.red()), int(color.green()), int(color.blue()))
    except AttributeError:
        return tuple(int(c) for c in color[:3])


def inked(picture, color):
    """A picture (QIcon or QPixmap) drawn in one color alone, at any strengths (its alpha), noted so
    that a dark mode switch draws it again in the new color of that color's role (retheme_window);
    returns the picture."""
    try:
        _INKED_ORDER[0] += 1
        _INKED[picture.cacheKey()] = (_rgb(color), _INKED_ORDER[0])
        if len(_INKED) > INKED_MAX:
            oldest = sorted(_INKED.items(), key=lambda pair: pair[1][1])[:INKED_MAX // 5]
            for key, _ in oldest:
                del _INKED[key]
    except Exception:
        pass
    return picture


def icon_of(pixmap):
    """A list row's icon of a picture: noted in the picture's color when the picture was (inked), since
    an icon made from a pixmap is another picture to Qt (its own cacheKey)."""
    icon = _qt()[1].QIcon(pixmap)
    ink = ink_of(pixmap)
    return inked(icon, ink) if ink is not None else icon


def ink_of(picture):
    """The color a picture was drawn in (inked), or None."""
    try:
        if picture is None or picture.isNull():
            return None
        found = _INKED.get(picture.cacheKey())
        return found[0] if found is not None else None
    except Exception:
        return None


def theme_colors(palette):
    """{(group, role): (r, g, b)} of a palette: the roles of THEME_ROLES, active, and the grayed-out
    text roles (lists gray out what cannot be done)."""
    QtGui = _qt()[1]
    found = {}
    groups = (("active", getattr(QtGui.QPalette, "Active", 0)), ("disabled", getattr(QtGui.QPalette, "Disabled", 2)))
    for group_name, group in groups:
        for role_name in THEME_ROLES if group_name == "active" else ("WindowText", "Text", "ButtonText"):
            role = getattr(QtGui.QPalette, role_name, None)
            if role is None:
                continue
            try:
                found[(group_name, role_name)] = _rgb(palette.color(group, role))
            except Exception:
                continue
    return found


def theme_dark(colors):
    """Whether a palette's colors (theme_colors) are dark: its window darker than its text."""
    window, text = colors.get(("active", "Window")), colors.get(("active", "WindowText"))
    if window is None or text is None:
        return False
    return sum(window) < sum(text)


def theme_map(old, new):
    """{old color: new color} from one palette's colors to another's (theme_colors), role by role (a
    color two roles shared goes the way of the first, text roles first), with the logs' colors for a
    light background and for a dark one (LOG_COLORS) swapped as the background changed."""
    mapping = {}
    for group in ("active", "disabled"):
        for role in THEME_ROLES:
            key = (group, role)
            if key in old and key in new and old[key] not in mapping:
                mapping[old[key]] = new[key]
    was_dark, dark = theme_dark(old), theme_dark(new)
    if was_dark != dark:
        for on_dark, on_light in LOG_COLORS.values():
            mapping.setdefault(on_dark if was_dark else on_light, on_light if was_dark else on_dark)
    return dict((before, after) for before, after in mapping.items() if before != after)


def retinted(picture, rgb):
    """A one-color picture (QIcon or QPixmap) drawn again in rgb, its alpha kept (Qt's SourceIn: each
    pixel takes the new color at its own strength), and noted in that color (inked)."""
    QtCore, QtGui = _qt()
    icon = not hasattr(picture, "toImage")
    if icon:
        sizes = list(picture.availableSizes())
        if not sizes:
            return None
        source = picture.pixmap(sizes[-1])
    else:
        source = picture
    pixmap = QtGui.QPixmap(source.size())
    try:
        pixmap.setDevicePixelRatio(source.devicePixelRatio())
    except Exception:
        pass
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    try:  # ended whatever happens: a painter left open on a freed pixmap aborts FontLab
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QtGui.QColor(rgb[0], rgb[1], rgb[2]))
    finally:
        painter.end()
    made = QtGui.QIcon(pixmap) if icon else pixmap
    return inked(made, rgb)


def _items(view):
    """Every item of a tree, list, or table widget, read from the live widget now (never kept)."""
    if view.inherits("QTreeWidget"):
        pending = [view.topLevelItem(i) for i in range(_property(view, "topLevelItemCount"))]
        while pending:
            item = pending.pop()
            if item is None:
                continue
            yield item
            pending.extend(item.child(i) for i in range(item.childCount()))
    elif view.inherits("QListWidget"):
        for row in range(_property(view, "count")):
            yield view.item(row)
    elif view.inherits("QTableWidget"):
        for row in range(_property(view, "rowCount")):
            for column in range(_property(view, "columnCount")):
                item = view.item(row, column)
                if item is not None:
                    yield item


def _recolored_brush(brush, mapping):
    """The brush in its color's new color (its alpha kept), or None when it keeps its color."""
    QtGui = _qt()[1]
    try:
        if int(brush.style()) == 0:  # Qt.NoBrush: the item's own color is the palette's already
            return None
        color = brush.color()
        after = mapping.get(_rgb(color))
        if after is None:
            return None
        made = QtGui.QColor(after[0], after[1], after[2])
        made.setAlpha(color.alpha())
        return QtGui.QBrush(made)
    except Exception:
        return None


def retheme_items(view, mapping):
    """A list's pictures (inked) and item colors in their new colors: how many were redrawn. The list's
    signals are held meanwhile: a changed item is no edit of the user's (Glyph Compose dropped its
    revealed rows, Feature Code wrote its code again row by row, on itemChanged)."""
    count = 0
    single = view.inherits("QListWidget")  # (a list's item has no column)
    columns = 1 if single else max(1, _property(view, "columnCount"))
    try:
        blocked = bool(view.blockSignals(True))  # (what it was: a list held already stays held)
    except Exception:
        blocked = None
    try:
        for item in _items(view):
            for column in range(columns):
                args = () if single else (column,)
                try:
                    icon = item.icon(*args)
                    ink = ink_of(icon)
                    if ink is not None and ink in mapping:
                        made = retinted(icon, mapping[ink])
                        if made is not None:
                            item.setIcon(*(args + (made,)))
                            count += 1
                    for getter, setter in (("foreground", "setForeground"), ("background", "setBackground")):
                        brush = _recolored_brush(getattr(item, getter)(*args), mapping)
                        if brush is not None:
                            getattr(item, setter)(*(args + (brush,)))
                            count += 1
                except Exception:
                    continue
    finally:
        if blocked is not None:
            try:
                view.blockSignals(blocked)
            except Exception:
                pass
    return count


def window_widgets(window):
    """The widgets of a window, itself first, each before its children (a child polished before its
    parent would take the parent's colors of before)."""
    QtGui = _qt()[1]
    try:  # (a dialog the tool opened from its window, Auto Kerning's classes, is a window of its own)
        roots = [window] + list(window.findChildren(QtGui.QDialog))
        found = [w for w in QtGui.QApplication.instance().allWidgets() if any(root.isAncestorOf(w) for root in roots)]
    except Exception:
        return [window]

    def depth(widget):
        steps = 0
        while widget is not None and steps < 64:
            widget = widget.parentWidget()
            steps += 1
        return steps
    return sorted(found, key=depth)


def dark_mode_palette(widget):
    """Whether dark mode set this widget's palette (an island's light palette): polished again, Qt would
    drop it. A palette a stylesheet's own rules set counts not: Qt marks such a widget as having a
    palette of its own too (live: 71 of Font Check's widgets), and it is the one to read again."""
    module = (getattr(sys, "_freelab_dark_mode", None) or {}).get("module")
    owns = getattr(module, "owns_palette", None)
    try:
        return bool(owns(widget)) if owns is not None else False
    except Exception:
        return False


def repolish(widget):
    """The widget in the colors of now (see above), its window's widgets taken parents first: unpolished
    (a stylesheet's palette taken back), its palette taken from its parent again where none is set on
    it, then polished again. A widget styled through a stylesheet (on it, a parent, or the application)
    kept the palette it had, colors set on it or not: an empty palette set on it brings the one of now
    (live, November 14: Feature Code's sections and Font Check's lists kept the theme before; polishing
    alone changed nothing). One whose palette dark mode set (an island) is left as it is; one whose
    palette a stylesheet's own colors set is read again (Font Check's scripts list stayed light)."""
    QtGui = _qt()[1]
    try:
        if dark_mode_palette(widget):
            return False
        style = widget.style()
        style.unpolish(widget)
        try:
            if not widget.palette.resolve():  # (nothing set on it: inherit again)
                widget.setPalette(QtGui.QPalette())
        except Exception:
            pass
        style.polish(widget)
        widget.update()
        return True
    except Exception:
        return False


def _logs_of(owner):
    """The logs (Log) a tool's dialog object holds, and those of the parts it holds (a page's log)."""
    def is_log(value):  # (by what it does: a tool may hold a Log of another copy of this module)
        return (not hasattr(value, "inherits") and callable(getattr(value, "restyle", None))
                and hasattr(value, "entries") and hasattr(value, "view"))

    found = []
    for value in list(getattr(owner, "__dict__", {}).values()):
        if is_log(value):
            if all(value is not log for log in found):
                found.append(value)
        elif hasattr(value, "__dict__") and not hasattr(value, "inherits"):
            for inner in list(value.__dict__.values()):
                if is_log(inner) and all(inner is not log for log in found):
                    found.append(inner)
    return found


def retheme_window(owner, mapping):
    """One shown FreeLab window in the colors of now (see above): what was done, by kind."""
    done = {"polished": 0, "pictures": 0, "logs": 0, "tool": False}
    dialog = owner.dialog
    widgets = window_widgets(dialog)
    for widget in widgets:
        if repolish(widget):
            done["polished"] += 1
    done["tables"] = 0
    for widget in widgets:
        try:
            if is_table(widget):  # (its stylesheet holds the palette's colors: written again in the new ones)
                style_table(widget)
                refit(widget)  # (and its columns fitted as they were, from the same rows and fonts)
                done["tables"] += 1
            if widget.inherits("QTreeWidget") or widget.inherits("QListWidget") or widget.inherits("QTableWidget"):
                done["pictures"] += retheme_items(widget, mapping)
            elif widget.inherits("QLabel"):
                pixmap = _property(widget, "pixmap")
                ink = ink_of(pixmap)
                if ink is not None and ink in mapping:
                    widget.setPixmap(retinted(pixmap, mapping[ink]))
                    done["pictures"] += 1
            elif widget.inherits("QAbstractButton"):
                icon = _property(widget, "icon")
                ink = ink_of(icon)
                if ink is not None and ink in mapping:
                    widget.setIcon(retinted(icon, mapping[ink]))
                    done["pictures"] += 1
        except Exception:
            continue
    for log in _logs_of(owner):
        try:
            log.restyle()
            done["logs"] += 1
        except Exception:
            pass
    changed = getattr(owner, "theme_changed", None)
    if changed is not None:
        try:
            changed()
            done["tool"] = True
        except Exception:
            pass  # (one tool failing leaves the others theirs)
    return done


THEME_ATTR = "drawn_theme"  # on a tool's dialog object: the colors (theme_colors) its window is drawn in


def _theme_now():
    try:
        return theme_colors(_qt()[1].QApplication.instance().palette())
    except Exception:
        return None


def note_theme(owner):
    """A tool's window, as it is built, is drawn in the colors of now."""
    now = _theme_now()
    if now is not None:
        setattr(owner, THEME_ATTR, now)


def theme_switched(dark=None):
    """FontLab's palette changed (dark mode switched, either way): every shown FreeLab window follows
    (retheme_window), from the colors it was drawn in. A busy window (inside its own loop, which lets
    events through: an analysis, a check) is left as it is, and follows on a later tick once its work
    is done. dark: what dark mode says it switched to (unused: the palette tells). The windows that
    followed."""
    registry = _windows()
    now = _theme_now()
    if now is None:
        return []
    seen, registry["theme"] = registry.get("theme"), now
    followed = []
    for _, owner in sorted(_owners().items(), key=lambda pair: pair[0]):
        if getattr(owner, RELEASED, False) or not _shown(owner):
            continue  # (a closed window is let go, not redrawn)
        before = getattr(owner, THEME_ATTR, None) or seen
        if not before or before == now:
            setattr(owner, THEME_ATTR, now)
            continue
        if getattr(owner, "busy", False):
            setattr(owner, THEME_ATTR, before)  # (its colors of before kept: it catches up once its work is done)
            continue
        try:
            retheme_window(owner, theme_map(before, now))
            followed.append(owner)
        except Exception:
            pass
        setattr(owner, THEME_ATTR, now)
    return followed


def theme_tick():
    """The windows' tick: a palette change no one announced (an older dark mode) is followed, and a
    window that was busy at a switch catches up; the colors of the first tick are the ones the windows
    were drawn in."""
    registry = _windows()
    if registry.get("theme") is None:
        now = _theme_now()
        if now is not None:
            registry["theme"] = now
        return []
    return theme_switched()


def hook_theme():
    """Once a session: dark mode's call after it switched (sys._freelab_theme_hook) reaches
    theme_switched through the module loaded last. The colors the windows are drawn in now noted."""
    registry = _windows()
    if registry.get("theme") is None:
        try:
            registry["theme"] = theme_colors(_qt()[1].QApplication.instance().palette())
        except Exception:
            pass
    if getattr(sys, "_freelab_theme_hook", None) is not None:
        return
    modules, name, own = sys.modules, __name__, theme_switched

    def switched(dark=None):
        try:
            return (getattr(modules.get(name), "theme_switched", None) or own)(dark)
        except Exception:
            return []  # (dark mode's switch must never fail on FreeLab's account)

    sys._freelab_theme_hook = switched


def _own_window(dialog):
    """A window of its own, with a button on the taskbar, a minimize and a maximize button. A dialog
    FontLab's main window owns has no taskbar button: minimized, it was a title bar in a corner of the
    screen, hard to find again. It no longer stays above FontLab's window; the taskbar brings it back.
    It does not keep FontLab running once FontLab's own window is closed (hook_quit)."""
    QtCore = _qt()[0]
    flags = (QtCore.Qt.Window | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint
             | QtCore.Qt.WindowMinMaxButtonsHint | QtCore.Qt.WindowCloseButtonHint)
    dialog.setParent(None, flags)
    dialog.setAttribute(QtCore.Qt.WA_QuitOnClose, False)


def _center_on_main(dialog):
    """Over FontLab's main window, as a dialog it owned would open."""
    main = AutoKerningDialog.main_window()
    if main is None:
        return
    frame, size = _property(main, "frameGeometry"), _size(dialog)
    area = _qt()[1].QApplication.desktop().availableGeometry(main)
    x = max(area.left(), min(frame.center().x() - size[0] // 2, area.right() - size[0]))
    y = max(area.top(), min(frame.center().y() - size[1] // 2, area.bottom() - size[1] - 30))
    dialog.move(x, y)


TEXT_INPUTS = ("QLineEdit", "QTextEdit", "QPlainTextEdit", "QAbstractSpinBox")


KEY_Z, KEY_Y = 0x5A, 0x59  # Qt::Key_Z, Qt::Key_Y
CONTROL, SHIFT, ALT, META = 0x04000000, 0x02000000, 0x08000000, 0x10000000  # Qt's keyboard modifiers
KEY_PRESS, SHORTCUT_OVERRIDE = 6, 51  # QEvent::KeyPress, QEvent::ShortcutOverride


def undo_key(event):
    """"actionUndo" for Ctrl+Z, "actionRedo" for Ctrl+Shift+Z or Ctrl+Y (FontLab's actions' names), None
    for any other key event."""
    try:
        key, held = int(event.key()), int(event.modifiers()) & (CONTROL | SHIFT | ALT | META)
    except Exception:
        return None
    if key == KEY_Z and held == CONTROL:
        return "actionUndo"
    if (key == KEY_Z and held == CONTROL | SHIFT) or (key == KEY_Y and held == CONTROL):
        return "actionRedo"
    return None


def own_undo(widget, name):
    """Whether the widget with the focus keeps undo and redo (name: "actionUndo" or "actionRedo") for
    itself: every text field, spin box, or spin box's line edit that can be typed in does, whatever its
    own undo holds, so FontLab's Undo runs only when the focus is elsewhere in the window (a list, a
    button, nothing). A spin box applies its value as it is typed and its line edit then reports nothing
    to undo: Ctrl+Z after typing 9 went to FontLab and undid a glyph build, the field still at 9 (live,
    2026-11-17). Read-only text (the log) keeps nothing."""
    try:
        if widget is None or not any(widget.inherits(kind) for kind in TEXT_INPUTS):
            return False
    except Exception:
        return False  # (no text field)
    try:
        return not _property(widget, "readOnly")
    except Exception:
        return True  # (unsure: the field keeps the key, as it would without FreeLab)


COMMITTED_FIELDS = ("QLineEdit", "QAbstractSpinBox")  # one-line fields whose typing becomes a value


def commit_typing(window, pressed=None):
    """What is typed in the window's field with the focus taken as its value, before a button acts on
    it: a spin box's text interpreted (interpretText: its value set and valueChanged emitted, as Enter
    would), then the field's focus taken away, so it ends its editing as when a click moves the focus
    (a line edit's editingFinished, a spin box's own). The owner typed 100 in Feature Code's Strokes over
    130 and clicked Build without Enter: it built at 130. A button that takes no focus on a click (a tool
    button, a button made NoFocus) left the field focused and its value as it was. pressed: the button
    pressed (a field is never its own button). The field committed, or None."""
    QtGui = _qt()[1]
    try:
        focus = QtGui.QApplication.focusWidget()
    except Exception:
        return None
    if focus is None or focus is pressed:
        return None
    try:
        if not _same(focus.window(), window) or not any(focus.inherits(kind) for kind in COMMITTED_FIELDS):
            return None  # (another window's, or a text editor: nothing to commit, its focus kept)
    except Exception:
        return None
    spin = focus
    try:
        if not spin.inherits("QAbstractSpinBox"):
            parent = spin.parentWidget()  # (a spin box's own line edit has the focus while it is typed in)
            spin = parent if parent is not None and parent.inherits("QAbstractSpinBox") else None
    except Exception:
        spin = None
    try:
        if spin is not None:
            spin.interpretText()
    except Exception:
        pass
    try:
        focus.clearFocus()
    except Exception:
        pass
    return focus


def fontlab_undo(owner, name):
    """FontLab's own Edit > Undo (name "actionUndo") or Redo ("actionRedo") run for a tool's window, on its
    font: the QAction of that name among the main window's, triggered, then FontLab's views redrawn
    (refresh_views). Nothing while the tool is busy (owner.busy: inside its own loop, which lets events
    through), and nothing but a line in the log when FontLab shows another font it cannot be made to show the
    window's instead (its commands act on the font it shows: own_font_refusal), when the window's font is
    closed or FontLab's current font cannot be read, when FontLab has nothing to undo (its command grayed out),
    or when the command cannot be found. True when FontLab's command was run."""
    QtCore, QtGui = _qt()
    done, verb = (u"undone", u"undo") if name == "actionUndo" else (u"redone", u"redo")
    log = getattr(owner, "log", None)
    try:
        if getattr(owner, "busy", False):
            return False  # (the History must not move under the tool's own work)
        foreign = own_font_refusal(owner)  # (its font shown first: owner's image 314)
        if foreign:
            if log is not None:
                log.add(u"Nothing was %s: FontLab's %s works on the font it shows, not on this window's (%s). "
                        u"Click %s's Font window, then %s there." % (done, i(verb.capitalize()), b(foreign),
                                                                     b(foreign), verb), "warning")
            return False
        if foreign is not None:
            if log is not None:
                log.add(u"Nothing was %s: FontLab's %s works on the font it shows, and this window's font is no "
                        u"longer open (or FontLab could not say which font it shows)." % (done, i(verb.capitalize())),
                        "warning")
            return False
        main = AutoKerningDialog.main_window()
        for action in (main.findChildren(QtGui.QAction) if main is not None else []):
            if action.objectName != name:
                continue
            if not action.isEnabled():
                if log is not None:
                    log.add(u"FontLab has nothing to %s (its %s is grayed out)." % (
                        verb, i(u"Edit > %s" % verb.capitalize())))
                return False
            action.trigger()
            # FontLab's Undo moved the font's History, but its own windows (Font, Glyph, Kerning) were
            # not drawn again while a FreeLab window was the active one: they are told, once the command
            # has run (refresh_views)
            refresh = lambda: refresh_views(owner)
            owner.undo_refresh = refresh  # (held until it runs: PythonQt drops what no Python object holds)
            QtCore.QTimer.singleShot(0, refresh)
            return True
        if log is not None:
            log.add(u"Nothing was %s: FontLab's %s was not found." % (done, i(u"Edit > %s" % verb.capitalize())),
                    "warning")
    except Exception:
        pass  # (called from slots and filters, which must not raise)
    return False


def undo_key_event(window, obj, event):
    """The window's filter (filter_event) for Ctrl+Z, Ctrl+Shift+Z, and Ctrl+Y: True when it took the
    event. Taken at Qt's ShortcutOverride, which comes before any shortcut is looked up (and goes up to
    the window from whatever widget has the focus): Qt then sends the key as a plain key press, which
    runs FontLab's command here (fontlab_undo). No shortcut of the window or of FontLab sees the key, so
    none can make it ambiguous, whatever context FontLab gave its own (owner's report: undo pressed with
    a FreeLab window in front never reached FontLab). A field that can be typed in keeps the key
    (own_undo), whatever its own undo holds."""
    name = undo_key(event)
    if name is None:
        return False
    owner = window_owner(window)
    if owner is None:
        return False  # (not a FreeLab tool's window: never FontLab's own keys)
    try:
        focus = _qt()[1].QApplication.focusWidget()
    except Exception:
        focus = None
    if own_undo(focus if focus is not None else obj, name):
        return False
    if event.type() == SHORTCUT_OVERRIDE:
        event.accept()
        return True
    fontlab_undo(owner, name)
    return True


def forward_undo(owner):
    """Undo and redo typed in a tool's window reach FontLab (its own Edit > Undo and Redo commands)
    through the window's filter alone (undo_key_event). No shortcut of the window's own: FontLab's Edit
    > Undo is an application-wide Ctrl+Z, and a window shortcut on the same keys made Qt's ambiguous case,
    in which neither ran and the key press never came (live, 2026-11-17: the History did not move until
    the window's Ctrl+Z shortcut was disabled)."""
    owner.undo_shortcuts = []
    try:
        install_filters(owner.dialog)  # (the filter is on the window from the start)
    except Exception:
        pass


def refresh_views(owner, fontlab=None):
    """FontLab's own windows told that the font of a tool's window changed, without a step of its
    History (notifyChangesApplied would make one): after an undo or a redo started from a FreeLab
    window, FontLab's views kept showing the font as it was. The notifications called, as a list.

    Not notifyPackageContentUpdated: it rebuilds the Font window's list and took 8.8 s on Noto Sans
    (3,700 glyphs, live 2026-11-14), each Ctrl+Z (two checks of a clipboard another program held
    open: the time does not grow with the font). FontLab's Undo restores the glyphs itself (live: H's
    width came back on undo and went again on redo); notify_changed still calls it after a write that
    added glyphs. What the owner saw ("the log says History changed, but it doesn't reach FontLab")
    was the first write of a font opened afresh: with no state of FontLab's History before it, Undo
    moves the History back and puts nothing back (live: width 751 kept, History 1 to 0); before_changes
    records the font first."""
    called = []
    try:
        if fontlab is None:
            import fontlab
        package = getattr(owner, "package", None) or fontlab.flWorkspace.instance().currentPackage
        font = package.fgPackage.id
    except Exception:
        return called
    items = getattr(fontlab, "flItems", None)
    for name, args in (("notifyPackageUpdated", (font,)), ("notifyHistoryChanged", ())):
        try:
            getattr(items, name)(*args)
            called.append(name)
        except Exception:
            pass  # (a FontLab without it: the others still run)
    try:
        main = AutoKerningDialog.main_window()
        if main is not None:
            main.update()
    except Exception:
        pass
    return called


RELEASE_MS = 1000  # how long after it closed a tool's window is let go (release_window)
RELEASED = "released"  # what a tool's dialog object holds once let go (let_go): nothing else


def release_window(owner):
    """A tool's window closed (by hand, giving way to another tool, or with its font) let go
    (let_go), RELEASE_MS later, unless it is shown again by then; a tool still busy (inside its own
    loop, which lets events through) is looked at again as long later. Never during the events that
    closed it (a click in it may have), hence the wait."""
    QtCore = _qt()[0]
    registry = _windows()
    waiting = registry.setdefault("releasing", [])

    def release():
        try:  # (a timer's handler must not raise)
            if release in waiting:
                waiting.remove(release)
            if getattr(owner, RELEASED, False) or _shown(owner):
                return
            if getattr(owner, "busy", False):
                release_window(owner)  # (its loop still works on it: later)
                return
            let_go(owner)
        except Exception:
            pass

    waiting.append(release)  # (held until it runs)
    QtCore.QTimer.singleShot(RELEASE_MS, release)


def _window_of(widget):
    try:
        return widget.window()
    except Exception:
        return None  # (deleted)


def _same(one, other):
    """Whether two wrappers are the same Qt object (PythonQt may hand back another wrapper)."""
    try:
        return one is other or (one is not None and other is not None and one == other)
    except Exception:
        return False


def let_go(owner):
    """A tool's window closed for good, freed by PythonQt itself, which deletes a window made from Python
    once no Python object refers to it (never deleteLater: PythonQt would delete it a second time,
    which crashed FontLab). Hidden windows piled up: closed, they were dropped from the registry, but
    a closure Qt held still reached the window. So: every reference FreeLab keeps is dropped (the
    registry's entries, the window's filter, its states' timer, its tools button's slots, dark mode's
    records of its widgets, the tool's own let_go() for what it connected outside the window), timers
    the tool holds are stopped, and the tool's dialog object is emptied (RELEASED alone left on it):
    the slots Qt holds refer to the tool's object, never to the window, so they no longer reach it.
    Nothing else: if something still holds the window, it stays hidden, as before. Returns what was
    let go, by kind (for tests and probes)."""
    registry = _windows()
    done = []
    dialog = getattr(owner, "dialog", None)
    registry["kept"] = [held for held in registry.get("kept", []) if held is not owner]
    for key, held in list(registry["fonts"].items()):
        if held is owner:
            del registry["fonts"][key]
            done.append("font")
    if dialog is not None:
        try:
            key = dialog.property(WINDOW_FILTER_PROP)
            filters = getattr(sys, "_freelab_window_filters", None) or {}
            watcher = filters.get(int(key)) if key is not None else None
            if watcher is not None:
                # (made from Python with no parent: given the window, so Qt deletes them with it, never
                # PythonQt as the last reference goes, at whatever moment Python's collector picks)
                for made in (watcher, getattr(watcher, "child_watch", None)):
                    _adopt(made, dialog)
                filters.pop(int(key), None)
                done.append("filter")
        except Exception:
            pass
        done.extend(_drop_state_watch(dialog))
        done.extend(_drop_tool_buttons(dialog))
        try:  # dark mode's records hold its widgets (and their effects): undone and dropped
            module = (getattr(sys, "_freelab_dark_mode", None) or {}).get("module")
            forget = getattr(module, "forget", None)
            if forget is not None and forget(dialog):
                done.append("dark mode")
        except Exception:
            pass
    own = getattr(owner, "let_go", None)
    if own is not None:
        try:
            own()  # (what the tool connected outside its window)
            done.append("tool")
        except Exception:
            pass
    for timer in _held_timers(owner):
        try:
            timer.stop()  # (a timer whose slot holds the timer itself would tick on, alone)
        except Exception:
            continue
        if dialog is not None and _adopt(timer, dialog):
            done.append("adopted")
    try:
        if dialog is not None:
            dialog.disconnect("finished(int)", owner.size_slot)
    except Exception:
        pass
    if dialog is not None and hand_to_qt(dialog):
        done.append("deleting")
    if release_caches():
        done.append("caches")
    owner.__dict__.clear()
    setattr(owner, RELEASED, True)
    try:
        # Work still pending through the tool's object (a 0 ms timer, a slot its list's model calls as the
        # list is deleted) now does nothing: never through a deleted window's lists and items
        owner.__class__ = ReleasedTool
    except TypeError:
        pass  # (a class of another kind: its attributes are gone all the same)
    return done


def release_caches():
    """The caches that hold a font's compiled code, emptied as a window closes: Feature Check's checks of a
    writer's code (its _REPORTS: a compiled stub font of every glyph per check, the code before and after the
    last write), which outlived every window (live, 2026-11-19: two TTFonts of BIZ UDPGothic's 13,932 glyphs
    still held once Feature Code had closed). It is a cache only: the next write checks again. Whether
    anything was emptied. Never raises."""
    try:
        cache = getattr(sys.modules.get(FEATURE_CHECK_MODULE), "_REPORTS", None)
        if isinstance(cache, dict) and cache:
            cache.clear()
            return True
    except Exception:
        pass
    return False


def _adopt(made, parent):
    """A QObject made from Python with no parent (a timer, an event filter) given one: Qt then deletes it
    with its parent. Left parentless, PythonQt deletes it when its last Python reference goes, which may
    be at any moment Python's collector picks: three crashes of FontLab (November 14) were PythonQt
    freeing such an object twice, inside an unrelated loop. True when it was given one."""
    try:
        if made is None or made.parent() is not None:
            return False
        made.setParent(parent)
        return True
    except Exception:
        return False


DELETING = "deleting"  # in sys._freelab_windows: the windows handed to Qt, held until deleteLater is asked
DELETE_WAIT_MS = 500  # deleteLater waits this long again while a menu or a modal dialog is open


def _popup_open():
    """Whether a menu (a list's right-click menu, a What's This menu) or a modal dialog runs its own event
    loop now: a window deleted inside one would take the menu, its child, from under it."""
    try:
        app = _qt()[1].QApplication
        return app.activePopupWidget() is not None or app.activeModalWidget() is not None
    except Exception:
        return False


def hand_to_qt(dialog):
    """A closed tool window freed by Qt, once, at a moment FreeLab chooses: given FontLab's main window
    as its parent (a window still, hidden: its flags kept), so PythonQt, which deletes a window made from
    Python once nothing refers to it, leaves it to Qt; then deleteLater from a plain timer's slot (never
    from inside the window's own signals), and only then is it let go. Without FontLab's main window, it
    is kept, hidden: never freed rather than freed by PythonQt at a random moment. True when handed."""
    QtCore = _qt()[0]
    registry = _windows()
    held = registry.setdefault(DELETING, [])
    try:
        main = AutoKerningDialog.main_window()
    except Exception:
        main = None
    try:
        if main is None or not widget_alive(dialog):
            if widget_alive(dialog):
                registry.setdefault("unfreed", []).append(dialog)
            return False
        dialog.setParent(main, dialog.windowFlags())  # (a parent: PythonQt no longer deletes it)
    except Exception:
        registry.setdefault("unfreed", []).append(dialog)
        return False

    def delete():
        try:
            if _popup_open():
                QtCore.QTimer.singleShot(DELETE_WAIT_MS, delete)  # (a menu of its own may be open: later)
                return
            if widget_alive(dialog):
                dialog.deleteLater()  # (Qt deletes it as its event loop comes back: once)
        except Exception:
            pass
        held[:] = [entry for entry in held if entry[0] is not dialog]  # (only now let go)

    held.append((dialog, delete))
    QtCore.QTimer.singleShot(0, delete)
    return True


class _Inert(object):
    """Nothing: called, or asked for an attribute, it gives itself; false, empty, and never Qt."""

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self

    def __setattr__(self, name, value):
        pass  # (written to, it stays nothing: one object stands for every attribute of every tool let go)

    def __delattr__(self, name):
        pass

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass

    def __getitem__(self, key):
        return self

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __bool__(self):
        return False
    __nonzero__ = __bool__


_INERT = _Inert()


class ReleasedTool(object):
    """What a tool's dialog object becomes once let go (let_go): whatever is asked of it (a method, a
    widget, a list) is nothing (_Inert), so a slot or a timer still bound to it (self.update_buttons from
    a 0 ms timer, self.select from the selection a deleted list gives up, Glyph Compose's row drop) ends
    there, never reaching a deleted list or its items."""
    released = True

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _INERT


HELD_DEPTH = 4  # how deep _held_timers looks through what a tool holds
HELD_MOST = 50000  # and how many things at most (a tool's lists of results are long)
_PLAIN = (type(None), bool, int, float, str, type(u""), bytes)


def _held_timers(owner):
    """The QTimers a tool's dialog object holds, wherever it holds them: in its attributes, the lists,
    tuples, sets, and dictionaries it holds, and the parts it holds (Glyph Compose's anchors page, Auto
    Kerning's previews' click regions, its classes dialog's drag, a flag menu, a log), each once, down
    to HELD_DEPTH. Timers tick on their own slots, and event filters are timers here: one held only in a
    dictionary of parts was missed, and became garbage PythonQt deleted at an arbitrary moment. Never a
    module's (the shared module a tool holds serves every window), a class's, or a function's; nor
    inside a Qt object."""
    def is_qt(value):
        return hasattr(value, "inherits") and hasattr(value, "metaObject")

    found, seen, pending = [], set([id(owner)]), [(value, 1) for value in list(getattr(owner, "__dict__", {}).values())]
    while pending and len(seen) < HELD_MOST:
        value, depth = pending.pop()
        if isinstance(value, _PLAIN) or id(value) in seen:
            continue
        seen.add(id(value))
        try:
            if is_qt(value):
                if value.inherits("QTimer"):
                    found.append(value)
                continue  # (what a Qt object holds is Qt's)
            if isinstance(value, (type(sys), type)) or callable(value) or depth >= HELD_DEPTH:
                continue
            if isinstance(value, dict):
                inner = list(value.values())
            elif isinstance(value, (list, tuple, set, frozenset)):
                inner = list(value)
            elif hasattr(value, "__dict__"):
                inner = list(value.__dict__.values())
            else:
                continue
            pending.extend((item, depth + 1) for item in inner)
        except Exception:
            continue
    return found


def close_slot(owner):
    """A tool's Close button's slot: the tool's window closed through its dialog object. Connected to
    the window's own close, Qt held the window through the button (a child of the window), and the
    window was never freed once closed (let_go empties the dialog object instead)."""
    def close(*args):
        try:
            owner.dialog.close()
        except Exception:
            pass  # (let go already, or deleted; a slot must not raise)
    owner.close_slot = close  # (held with the tool)
    return close


def _drop_state_watch(dialog):
    """watch_states' tick for this window, disconnected from its timer and dropped (it held the window)."""
    holder = getattr(sys, "_freelab_state_watchers", None) or []
    dropped = []
    for tick in list(holder):
        try:
            if not _same(getattr(tick, "dialog", None), dialog):
                continue
            timer = tick.timer
            timer.stop()
            timer.disconnect("timeout()", tick)
        except Exception:
            pass
        holder.remove(tick)
        dropped.append("states")
    return dropped


def _drop_tool_buttons(dialog):
    """The tools button's slots of this window, disconnected and dropped (_TOOL_BUTTONS held them)."""
    dropped = []
    for entry in list(_TOOL_BUTTONS):
        button, connections = entry[0], entry[3] if len(entry) > 3 else []
        window = _window_of(button)
        if window is not None and not _same(window, dialog):
            continue  # (another window's; a deleted button's entry goes too)
        for sender, signal, slot in connections:
            try:
                sender.disconnect(signal, slot)
            except Exception:
                pass
        _TOOL_BUTTONS.remove(entry)
        dropped.append("tools button")
    return dropped


# FreeLab MCP's window tools drive any Qt window; a script that follows their optional conventions (FreeLab
# MCP's docs/WINDOW-TOOLS.md) is driven more surely. FreeLab follows them and needs nothing of the MCP: they
# are Qt's own objectName and accessible name, and dynamic properties nothing else reads.
MCP_SCRIPT_WINDOW = "mcpScriptWindow"  # on each window and dialog FreeLab shows: its own, not a question of FontLab's
MCP_BUSY = "mcpBusy"  # on a tool's window: the step's name while it works (busy_start), False once it is over
MCP_RISKY = "mcpRisky"  # on a control that writes files outside FontLab's History: its use needs risky mode
MCP_CONTROL_CLASSES = ("QAbstractButton", "QComboBox", "QAbstractSpinBox", "QLineEdit", "QTextEdit", "QPlainTextEdit",
                       "QTabBar", "QTabWidget", "QAbstractItemView", "QLabel", "QProgressBar", "QAbstractSlider")
MCP_UNNAMED_PREFIXES = ("flag", "qt_")  # names dark mode reads as FontLab's (a flag swatch) or Qt keeps for itself
MCP_NAMES_DONE = "freelabNamed"  # on a widget named here (never named twice, nor renamed)


def mcp_script_window(window):
    """Marks a window or a dialog (a QMessageBox asking something) as FreeLab's own: FreeLab MCP then drives
    it as a script's, never taking it for a question of FontLab's. Returns the window. Never raises."""
    try:
        window.setProperty(MCP_SCRIPT_WINDOW, True)
    except Exception:
        pass
    return window


def mark_risky(widget):
    """Marks a control whose use writes files outside FontLab's History (a template, a PDF, an exported
    font): FreeLab MCP's window tools then click it only in risky mode. Returns the control. Never raises."""
    try:
        widget.setProperty(MCP_RISKY, True)
    except Exception:
        pass
    return widget


def _mcp_busy(owner, what):
    """The window's mcpBusy: the step's name (True when it has none) while it works, False once over."""
    try:
        if what is False:
            owner.dialog.setProperty(MCP_BUSY, False)
        else:
            owner.dialog.setProperty(MCP_BUSY, (u"%s" % what) if what else True)
    except Exception:
        pass


def _is_qt_widget(value):
    try:
        return hasattr(value, "inherits") and hasattr(value, "metaObject") and bool(value.isWidgetType())
    except Exception:
        return False


def _mcp_slug(text):
    """A tab's text as part of a name: lowercase words joined by _ (Vertical metrics: vertical_metrics)."""
    words = re.findall(u"[0-9A-Za-z]+", re.sub(u"\\s*\\(.*$", u"", u"%s" % (text or u"")))
    return u"_".join(word.lower() for word in words)


def name_controls(owner):
    """Gives each control of a tool's window that has no objectName one from the attribute the tool holds it
    in (self.check_button: check_button), so FreeLab MCP addresses it whatever its text or place; a control
    held by a part the tool holds (its log, a tab's parts) takes the part's name and its own (coverage.status;
    a part's view alone, the part's name: log). Pages a tab bar switches (a QStackedWidget held as pages,
    beside a QTabBar held as tabs) take their tab's name (pages.coverage). Only the window's own controls,
    each once: a name given is never changed, and a name kept by FreeLab or dark mode is left alone. Called
    as the window is taken (take_window) and after each work (busy_end), for the controls made since.
    Returns the names given. Never raises."""
    given = []
    try:
        window = owner.dialog
    except Exception:
        return given
    taken = set()

    def is_control(widget):
        return any(widget.inherits(name) for name in MCP_CONTROL_CLASSES)

    def name(widget, wanted, any_kind=False):
        try:
            if not _is_qt_widget(widget) or widget.isWindow() or not _same(widget.window(), window):
                return
            if not wanted or wanted in taken or wanted.lower().startswith(MCP_UNNAMED_PREFIXES):
                return
            if u"%s" % (_property(widget, "objectName") or u"") or widget.property(MCP_NAMES_DONE):
                return
            if not (any_kind or is_control(widget)):
                return
            widget.setObjectName(wanted)
            widget.setProperty(MCP_NAMES_DONE, True)
            taken.add(wanted)
            given.append(wanted)
        except Exception:
            pass  # (a deleted widget, or a fake without these calls)

    try:
        attributes = sorted(getattr(owner, "__dict__", {}).items(), key=lambda item: item[0])
    except Exception:
        return given
    parts = []
    for attribute, value in attributes:
        if attribute.startswith("_") or isinstance(value, _PLAIN):
            continue
        if _is_qt_widget(value):
            name(value, attribute)
        elif (hasattr(value, "__dict__") and not isinstance(value, (type(sys), type)) and not callable(value)
              and not hasattr(value, "inherits") and value is not owner):
            parts.append((attribute, value))
    for attribute, part in parts:
        try:
            inner = sorted(part.__dict__.items(), key=lambda item: item[0])
        except Exception:
            continue
        for sub, value in inner:
            if not sub.startswith("_") and _is_qt_widget(value):
                name(value, attribute if sub == "view" else u"%s.%s" % (attribute, sub))
    # The pages a tab bar switches: each named after its tab (FreeLab MCP walks a QTabWidget's tabs itself)
    for attribute, value in attributes:
        try:
            if not _is_qt_widget(value) or not value.inherits("QStackedWidget") or "pages" not in attribute:
                continue
            bar = getattr(owner, attribute.replace("pages", "tabs"), None)
            texts = []
            if _is_qt_widget(bar) and bar.inherits("QTabBar") and int(_property(bar, "count")) == int(_property(value, "count")):
                texts = [_mcp_slug(bar.tabText(index)) for index in range(int(_property(bar, "count")))]
            for index in range(int(_property(value, "count"))):
                page = value.widget(index)
                slug = texts[index] if index < len(texts) and texts[index] else u"%d" % (index + 1)
                name(page, u"%s.%s" % (attribute, slug), any_kind=True)
        except Exception:
            continue
    return given


def mcp_conventions(owner):
    """FreeLab MCP's conventions on a tool's window (see MCP_SCRIPT_WINDOW): the window FreeLab's own, not busy,
    and its controls named (name_controls). Never raises."""
    try:
        mcp_script_window(owner.dialog)
        if owner.dialog.property(MCP_BUSY) is None:
            _mcp_busy(owner, False)
    except Exception:
        pass
    return name_controls(owner)


def take_window(tool, owner):
    """A tool's main() calls this before it shows its window: the window is tied to its font, made a
    window of its own, and takes the place of the tool that font's window showed, which is closed: the
    window it was opened from, when it was (the one clicked, even if it is not its font's own window).
    Its size is its own (or the one the owner gave a tool's window by hand: note_size)."""
    registry = _windows()
    caller = calling_owner()  # (before the hint is used up)
    try:
        owner.current_font()  # (reads its font, if it has not yet: the calling window's, or FontLab's)
    except Exception:
        pass
    registry["hint"] = None
    font_id = getattr(owner, "font_id", None)
    registry["next"] = key = registry.get("next", 0) + 1
    owner.window_key, owner.tool = key, tool
    try:
        owner.dialog.setProperty(WINDOW_PROP, key)
    except Exception:
        pass
    mcp_conventions(owner)  # (FreeLab MCP's: the window its own, its controls named)
    old = registry["fonts"].get(font_id)
    own = old if old is not None and old is not owner and _shown(old) and font_id is not None else None
    if old is None or not _shown(old):
        # a window opened with no font is the next font's: it gives way, not a second window
        fontless = registry["fonts"].get(None)
        if fontless is not None and fontless is not owner and _shown(fontless):
            old = fontless
            if registry["fonts"].get(None) is fontless and font_id is not None:
                del registry["fonts"][None]
    caller_font = getattr(caller, "font_id", None)
    if (caller is not None and caller is not owner and _shown(caller)
            and (caller_font == font_id or (caller_font is None and own is None))):
        # (the window clicked, its font this one's, or a window still without a font, unless the font this
        # one works on has a window of its own: that window gives way, never a second window on one font,
        # and the one without a font goes on waiting for the next font)
        old = caller
    registry["fonts"][font_id] = owner
    # Kept while it is shown: a window with no owner lives only while Python holds it. Once closed (by
    # hand, or giving way to another tool) it is let go (release_window): kept for the session, as
    # FontLab's main window kept its closed tool windows, they piled up (18 hidden after a session, live).
    registry.setdefault("kept", []).append(owner)
    place = None
    if old is not None and old is not owner:
        try:
            if old.dialog.isVisible():
                note_size(old)
                if not _property(old.dialog, "minimized") and not _property(old.dialog, "maximized"):
                    place = (_xy(_property(old.dialog, "pos")), _size(old.dialog))
                old.dialog.close()
        except Exception:
            pass  # (FontLab deleted it)
        release_window(old)
    try:
        _own_window(owner.dialog)
    except Exception:
        pass
    size = registry.setdefault("size", None)  # (given by hand in this session: note_size)
    try:
        if size is not None:
            width, height = size
            try:
                area = _qt()[1].QApplication.desktop().availableGeometry(owner.dialog)
                width, height = min(width, area.width() - 40), min(height, area.height() - 60)
            except Exception:
                pass
            owner.dialog.resize(width, height)
        if place is not None:
            area, frame = _free_area(owner.dialog)
            x, y = centered_place(place[0], place[1], _size(owner.dialog), area, frame)
            owner.dialog.move(x, y)
            owner.placed_from = place  # (centered again as it shows, at the size its layout gives it: keep_center)
        else:
            _center_on_main(owner.dialog)
    except Exception:
        pass
    owner.opened_size = None  # (read once the window is shown: main() shows it after this)
    try:
        measure_opened(owner)
    except Exception:
        pass
    hook_quit()
    try:
        watch_fonts()
        hook_theme()
        note_theme(owner)  # (built just now: in the colors of now)
    except Exception:
        pass
    try:
        def closed(*args):
            note_size(owner)
            release_window(owner)
        owner.size_slot = closed
        owner.dialog.connect("finished(int)", closed)
    except Exception:
        pass
    try:
        forward_undo(owner)
    except Exception:
        pass


def tool_neighbors(tool, tools=None):
    """(the tool before, the tool after) in the order of the work, None at either end."""
    tools = list(tools or FONT_TOOLS)
    if tool not in tools:
        return None, None
    at = tools.index(tool)
    return (tools[at - 1] if at > 0 else None), (tools[at + 1] if at + 1 < len(tools) else None)


def open_tool(title, dialog=None):
    """Opens a FreeLab tool by its entry in Scripts > FreeLab, as FontLab runs it, on the font of the
    window it is opened from (dialog); False when the entry is not there."""
    QtCore, QtGui = _qt()
    main = AutoKerningDialog.main_window()
    if main is None:
        return False
    for menu in main.findChildren(QtGui.QMenu):
        try:
            if menu.objectName != SCRIPTS_MENU:
                continue
            for action in menu.actions():
                submenu = action.menu()
                if submenu is None or action.text.replace(u"&", u"") != MENU_TITLE:
                    continue
                for entry in submenu.actions():
                    if not entry.isSeparator() and entry.text.replace(u"&", u"") == title:
                        with opening_from(dialog):  # (FontLab runs the entry's script before trigger returns)
                            entry.trigger()
                        return True
        except Exception:
            continue
    return False


def tools_icon(color, size=16):
    """Three short lines (the usual menu sign), in color."""
    QtCore, QtGui = _qt()
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    try:
        for y in (3, 7, 11):
            painter.fillRect(2, y, size - 4, 2, color)
    finally:
        painter.end()
    return pixmap


def content_layout(dialog):
    """The layout holding a window's content: the dialog's own, or, on a small screen, that of the body
    in its scroll area (window_layout). The tools button went into the dialog's own layout there, beside
    the scroll area, and left an empty strip at the window's right (live, 2026-11-17)."""
    layout = dialog.layout()
    try:
        if layout is not None and layout.count() == 1:
            area = layout.itemAt(0).widget()
            if area is not None and area.property(WINDOW_BODY_PROP):
                body = area.widget()
                if body is not None and body.layout() is not None:
                    return body.layout()
    except Exception:
        pass
    return layout


TOOLS_BUTTON_NAME = "freelabTools"  # the top row's buttons' objectNames (FreeLab MCP addresses them by these)
TOOL_STEP_NAMES = {u"Previous": "freelabPreviousTool", u"Next": "freelabNextTool"}
HELP_BUTTON_NAME = "freelabHelp"


def add_tools_button(dialog, current, log=None):
    """A menu button at the right of a FreeLab window's first row, listing the font tools (FONT_TOOLS):
    picking one opens it, as Scripts > FreeLab does; the window's own is grayed out. log: a Log told
    when a tool could not be found."""
    QtCore, QtGui = _qt()
    try:
        layout = content_layout(dialog)
        if layout is None or not layout.count():
            return None
        first_item = layout.itemAt(0)
        first, first_row = first_item.widget(), first_item.layout()
        if first is None and first_row is None:
            return None
        button = QtGui.QToolButton()
        button.setAutoRaise(True)
        # (an icon alone: its name and objectName for FreeLab MCP and screen readers, as the arrows' and ?'s)
        button.setObjectName(TOOLS_BUTTON_NAME)
        button.setAccessibleName(u"Tools")
        button.setToolTip(u"Open another FreeLab tool.")
        button.setWhatsThis(u"Lists FreeLab's font tools in the order of the work. Picking one opens it on this window's "
                            u"font, in this window's place.")
        ink = _property(dialog, "palette").color(QtGui.QPalette.WindowText)
        button.setIcon(inked(QtGui.QIcon(tools_icon(ink)), ink))  # (redrawn in the new text color on a switch)
        button.setProperty(LEAVE_ALONE_PROP, True)  # drawn in the dialog's colors
        menu = QtGui.QMenu(button)
        held, connections = [], []  # (sender, signal, slot): disconnected once the window is let go

        def go(title):
            # (the window found from the button as it is clicked: a slot that held the window kept it
            # alive once it was closed, see let_go)
            if not open_tool(title, _window_of(button)) and log is not None:
                log.add(u"%s is not in <i>Scripts &gt; FreeLab</i>: run <i>Refresh Scripts</i>, or reinstall FreeLab." % b(title),
                        "warning")

        for title in FONT_TOOLS:
            action = menu.addAction(title)
            if title == current:
                action.setEnabled(False)
            else:
                chosen = (lambda title: lambda *args: go(title))(title)
                held.append(chosen)
                action.connect("triggered()", chosen)
                connections.append((action, "triggered()", chosen))
        # The tool before and the tool after, in the order of the work: each opens in this window's place
        arrows = []
        for neighbor, arrow, word in zip(tool_neighbors(current), (QtCore.Qt.LeftArrow, QtCore.Qt.RightArrow),
                                         (u"Previous", u"Next")):
            step = QtGui.QToolButton()
            step.setAutoRaise(True)
            step.setArrowType(arrow)
            step.setObjectName(TOOL_STEP_NAMES[word])
            step.setAccessibleName(u"%s tool" % word)
            step.setEnabled(neighbor is not None)
            step.setToolTip(u"%s tool: %s" % (word, neighbor) if neighbor
                            else u"%s tool: none" % word)
            step.setWhatsThis(u"Opens the tool %s this one in the order of the work, on this window's font, in this "
                              u"window's place." % (u"before" if word == u"Previous" else u"after"))
            if neighbor is not None:
                stepped = (lambda title: lambda *args: go(title))(neighbor)
                held.append(stepped)
                step.connect("clicked()", stepped)
                connections.append((step, "clicked()", stepped))
            arrows.append(step)
        held.append(arrows)
        button.setMenu(menu)
        button.setPopupMode(QtGui.QToolButton.InstantPopup)
        button.setStyleSheet(u"QToolButton::menu-indicator { image: none; width: 0px; }")  # (the lines say "menu")
        # Windows shows no title-bar "?" beside minimize and maximize: the help button is here instead
        help_button = QtGui.QToolButton()
        help_button.setAutoRaise(True)
        help_button.setObjectName(HELP_BUTTON_NAME)
        help_button.setAccessibleName(u"Help")
        help_button.setText(u"?")
        bold = QtGui.QFont(help_button.font)
        bold.setBold(True)
        help_button.setFont(bold)
        help_button.setToolTip(u"What's this? Click it, then a control, to read what the control does.")
        help_button.setWhatsThis(u"Click it, then any control of this window, to read what that control does.")
        whats_this = lambda *args: QtGui.QWhatsThis.enterWhatsThisMode()
        held.append(whats_this)
        help_button.connect("clicked()", whats_this)
        connections.append((help_button, "clicked()", whats_this))
        busy = busy_row(dialog)
        if first is not None:  # a widget: it and the buttons share a row
            layout.removeWidget(first)
            first = window_head(layout, first)
            row = QtGui.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            # (the top line and the bar take the row's width; the spacer only once both are hidden: an
            # empty top line hides itself, and the buttons were spread across the row, live)
            row.addWidget(first, 1000)
            row.addWidget(busy, 1000)
            row.addStretch(1)
            for widget in [help_button] + arrows + [button]:
                row.addWidget(widget, 0, QtCore.Qt.AlignTop)
            layout.insertLayout(0, row)
        else:  # a row already: the buttons at its end
            first_row.addWidget(busy, 1000)
            first_row.addStretch(1)
            for widget in [help_button] + arrows + [button]:
                first_row.addWidget(widget, 0, QtCore.Qt.AlignTop)
        for widget in arrows + [button]:
            widget.setProperty(BUSY_ALLOWED_PROP, True)  # (usable while the window works: busy_progress)
        # (PythonQt drops what no Python object holds; let_go drops them with the window)
        _TOOL_BUTTONS.append((button, menu, held, connections))
        return button
    except Exception:
        return None


# A window's long work, shown in its top row and stoppable (owner's images 174 to 183): the step's name
# and a bar between the window's left edge and its "?", the top line hidden meanwhile. While it runs, the
# events go through (the window repaints, Windows never calls it Not Responding: a window it calls so and
# is told to end takes FontLab with it, the scripts running inside FontLab), but no click, key, or wheel
# reaches this window's controls or FontLab's, so nothing changes what the work reads. The tools menu, the
# arrows, Close, and the title bar's close stay usable: one asks the work to stop (busy_progress raises
# Stopped at its next step), and once the tool has unwound (busy_end), it does what was clicked.
BUSY_NAME = "freelabBusy"  # the top row's busy part (a label and a bar), made by add_tools_button
BUSY_ALLOWED_PROP = "freelabBusyAllowed"  # on the controls a click on which stops the work, then is done
BUSY_LINE_PROP = "freelabBusyLine"  # on a window's top line while its bar takes its place
BUSY_RANGE = 1000
BUSY_PUMP_SECONDS = 0.1  # events let through at most this often during the work
BUSY_GREEN = ((120, 200, 120), (30, 120, 40))  # LOG_COLORS["done"]: the bar's chunk (on dark, on light)
BUSY_SHEET = (u"QProgressBar { border: 1px solid rgba(128, 128, 128, 140); border-radius: 3px; "
              u"background: transparent; min-height: 10px; max-height: 10px; } "
              u"QProgressBar::chunk { background-color: rgb(%d, %d, %d); border-radius: 2px; }")
INPUT_EVENTS = (2, 3, 4, 6, 7, 31, 51, 63, 82, 92, 93, 117)  # presses, releases, double clicks, keys, wheel,
# shortcut overrides, drops, context menus, a tablet's presses and releases, and shortcuts themselves (117:
# Ctrl+Z reached FontLab's Undo during a read, owner's images 373 and 377)
SHORTCUT_EVENT = 117  # QEvent::Shortcut: a key sequence sent to its action (busy guard)
GUARD_IDLE_SECONDS = 10.0  # a guard whose tool is no longer busy and whose work has not moved for this long lets go
GUARD_LOST_SECONDS = 120.0  # and any guard, once no FreeLab work has moved for this long while events run
_LAST_PUMP = [0.0]  # when any window's work last moved (busy_progress)


class Stopped(Exception):
    """The work stopped by the user (busy_progress): the tool unwinds, quietly."""

    def __str__(self):
        return u"stopped"


HEAD_PROP = "freelabWindowHead"  # on the column holding a window's top line and its status lines (window_head)
HEAD_PART_PROP = "freelabHeadPart"  # on a widget of status lines under the top line, not a label itself (Glyph Compose's)


def window_head(layout, first):
    """The window's top line (first, taken out of layout already) and the status lines right under it in
    layout (labels, up to the header's separator) in one column, which shares the top row with the
    buttons: the status lines started under the row, a button's height below the top line (owner's
    image 229 asked for them under the font line; live 2026-11-17 they came a blank line lower).
    Returns the column, or first alone when no label follows it or first is no label."""
    QtGui = _qt()[1]
    try:
        if not first.inherits("QLabel"):
            return first
        lines = []
        while layout.count():
            item = layout.itemAt(0)
            widget = item.widget() if item is not None else None
            if widget is None or not (widget.inherits("QLabel") or widget.property(HEAD_PART_PROP)):
                break
            layout.removeWidget(widget)
            lines.append(widget)
        head = QtGui.QWidget()
        head.setProperty(HEAD_PROP, True)
        column = QtGui.QVBoxLayout(head)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(first)
        # A blank line between the font's line and what the tool found, in every window, as Font Check had it
        # (owner's image 346): the first line under it set that much lower, so the gap goes with it while it is
        # hidden (nothing found yet, no font)
        try:
            if lines:
                lines[0].setContentsMargins(0, head_gap(first), 0, 0)
        except Exception:
            pass
        for widget in lines:
            column.addWidget(widget)
        # The column's spare height below its lines: the font's line stays at the top of the row whether lines
        # follow it or not (owner's images 350, 351: alone, the row's button height centered it lower)
        column.addStretch(1)
        return head
    except Exception:
        return first


def head_gap(label):
    """The blank line under a window's top line (window_head): a line of its text, in pixels."""
    QtGui = _qt()[1]
    try:
        return int(QtGui.QFontMetrics(_property(label, "font")).lineSpacing())
    except Exception:
        return 14


def busy_row(dialog):
    """The top row's busy part: the step's name and the bar, hidden until busy_start."""
    QtCore, QtGui = _qt()
    row = QtGui.QWidget()
    row.setObjectName(BUSY_NAME)
    box = QtGui.QHBoxLayout(row)
    box.setContentsMargins(0, 0, 8, 0)
    label = QtGui.QLabel(u"")
    label.setObjectName(BUSY_NAME + "Step")
    bar = QtGui.QProgressBar()
    bar.setObjectName(BUSY_NAME + "Bar")
    bar.setRange(0, BUSY_RANGE)
    bar.setTextVisible(False)
    bar.setProperty(LEAVE_ALONE_PROP, True)
    tip = (u"How far the work is. The tools menu, the arrows, and Close stop it first (at its next step), "
           u"then do what was clicked; Esc stops it.")
    for widget in (row, label, bar):
        widget.setWhatsThis(tip)
    box.addWidget(label)
    box.addWidget(bar, 1)
    row.setVisible(False)
    return row


def _busy_parts(dialog):
    QtGui = _qt()[1]
    try:
        row = dialog.findChild(QtGui.QWidget, BUSY_NAME)
        if row is None:
            return None, None, None
        return row, row.findChild(QtGui.QLabel, BUSY_NAME + "Step"), row.findChild(QtGui.QProgressBar, BUSY_NAME + "Bar")
    except Exception:
        return None, None, None


def _busy_state(owner):
    state = getattr(owner, "busy_state", None)
    if state is None:
        state = owner.busy_state = {}
    return state


def busy_start(owner, what=u"", stoppable=True):
    """The window's work begins: its top row shows what (a step's name) and the bar at 0, its top line
    hidden meanwhile, the input guard on. owner.busy is the tool's own (it grays what it must)."""
    QtCore, QtGui = _qt()
    dialog = owner.dialog
    state = _busy_state(owner)
    row, label, bar = _busy_parts(dialog)
    state.update({"stop": False, "then": None, "pumped": 0.0, "what": None})
    _mcp_busy(owner, what)  # (FreeLab MCP waits on it: set before the first events go through)
    if row is not None:
        try:
            dark = _property(dialog, "palette").color(QtGui.QPalette.Window).lightness() < 128
            bar.setStyleSheet(BUSY_SHEET % (BUSY_GREEN[0] if dark else BUSY_GREEN[1]))
            bar.setValue(0)
            line = _top_line(dialog, row)
            state["line"] = (line, None if line is None else bool(line.isHidden()))
            if line is not None:
                line.setProperty(BUSY_LINE_PROP, True)
                line.setHidden(True)
            row.setVisible(True)
        except Exception:
            pass
    _guard_on(owner)
    # (never raises: a stop asked while the bar first paints is seen at the work's first step, inside the
    # tool's own try and its busy_end; raised here, it left the tool busy; review 12)
    busy_progress(owner, what, 0.0, force=True, stoppable=False)


def _top_line(dialog, row):
    """The label sharing the top row with the busy part (a window's top line), or None."""
    try:
        layout = content_layout(dialog)
        item = layout.itemAt(0)
        inner = item.layout() if item is not None else None
        if inner is None:
            return None
        for k in range(inner.count()):
            widget = inner.itemAt(k).widget()
            if widget is not None and (widget.inherits("QLabel") or widget.property(HEAD_PROP)):
                return widget  # (a label, or the column of the top line and its status lines: window_head)
    except Exception:
        pass
    return None


def busy_progress(owner, what=None, part=None, force=False, stoppable=True):
    """The work at a step: what (its name, or None to keep it) and part (0 to 1 of the whole, or None).
    The window repaints and its events go through the guard (at most every BUSY_PUMP_SECONDS); raises
    Stopped when the user asked the work to stop, unless stoppable is False (a write, which must end as
    one whole step of FontLab's History: what was clicked is done once it is over)."""
    QtCore, QtGui = _qt()
    state = _busy_state(owner)
    row, label, bar = _busy_parts(owner.dialog)
    moved = what is not None and what != state.get("what")
    try:
        if moved:
            state["what"] = what
            _mcp_busy(owner, what)
            label.setText(u"%s\N{HORIZONTAL ELLIPSIS}" % what if what else u"")
            try:
                row.layout().activate()  # (laid out now: painted at the last text's width, a longer one was cut by the bar, owner's image 312)
            except Exception:
                pass
        if part is not None and bar is not None:
            bar.setValue(int(round(min(max(float(part), 0.0), 1.0) * BUSY_RANGE)))
    except Exception:
        pass
    now = time.time()
    _LAST_PUMP[0] = now
    if force or moved or now - state.get("pumped", 0.0) >= BUSY_PUMP_SECONDS:
        state["pumped"] = now
        try:
            QtGui.QApplication.processEvents()
        except Exception:
            pass
    if state.get("stop") and stoppable:
        raise Stopped()


def quiet_list(view, on):
    """A list filled row by row while its window repaints (busy_progress): its rows hidden meanwhile
    (on), shown again after (off). Turned off with setUpdatesEnabled, it painted as a black box at every
    repaint while it filled (live, 2026-11-17, Font Check's languages); its viewport hidden, the list's
    frame and background show, and its scroll position is kept."""
    try:
        view.viewport().setVisible(not on)
    except Exception:
        try:
            view.setUpdatesEnabled(not on)
        except Exception:
            pass


def busy_stopping(owner):
    """Whether the user asked the work to stop (a tool that cannot raise looks)."""
    return bool(_busy_state(owner).get("stop"))


def busy_end(owner):
    """The work over (done, failed, or stopped): the top row as it was, the guard off, and what the user
    clicked meanwhile (a tool, an arrow, Close) done now. Never raises."""
    QtCore, QtGui = _qt()
    state = _busy_state(owner)
    _guard_off(owner)
    _mcp_busy(owner, False)
    name_controls(owner)  # (the controls the work made, for FreeLab MCP)
    try:
        row, label, bar = _busy_parts(owner.dialog)
        if row is not None:
            row.setVisible(False)
            label.setText(u"")
        line, hidden = state.pop("line", (None, None))
        if line is not None:
            # (shown as its text is now: the work wrote it meanwhile; put back as it was before the work,
            # a line empty then stayed hidden over the status the work wrote, live)
            line.setProperty(BUSY_LINE_PROP, None)
            if line.property(HEAD_PROP):
                line.setHidden(False)  # (its lines show or hide themselves by their text)
            else:
                line.setHidden(not (u"%s" % _property(line, "text")).strip())
    except Exception:
        pass
    then, state["then"], state["stop"] = state.get("then"), None, False
    if then is not None:
        QtCore.QTimer.singleShot(0, then)


def _guard_on(owner):
    """The input guard (see BUSY_NAME): an event filter on the application while the work runs."""
    QtCore, QtGui = _qt()
    state = _busy_state(owner)
    if state.get("guard") is not None:
        return
    dialog = owner.dialog

    def ask(then):
        if not state.get("stop"):
            state["stop"], state["then"] = True, then

    class Guard(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
        def eventFilter(self, obj, event):
            try:
                kind = event.type()
                if kind == 19 and obj is dialog:  # (the title bar's close: stop, then close)
                    event.ignore()
                    ask(dialog.close)
                    return True
                if kind == SHORTCUT_EVENT:
                    return True  # (a shortcut goes to its action, no widget: FontLab's Undo during the work)
                if kind not in INPUT_EVENTS or not obj.isWidgetType():
                    return False
                if kind == 6 and event.key() == QtCore.Qt.Key_Escape and obj.window() == dialog.window():
                    ask(None)
                    return True
                if obj.window() == dialog.window():
                    target = obj
                    for _ in range(4):
                        if target is None:
                            break
                        if target.property(BUSY_ALLOWED_PROP) or (
                                target.inherits("QPushButton") and (u"%s" % target.text).replace(u"&", u"") in ALWAYS_ON_TEXTS):
                            if kind == 3:  # (on release: stop, then click it, or open its menu)
                                menu = target.menu() if target.inherits("QToolButton") else None
                                ask(target.showMenu if menu is not None else target.click)
                            return True
                        target = target.parentWidget()
                return True  # (any other input, here or in FontLab, waits until the work is over)
            except Exception:
                return False  # an event filter must never raise

    guard = Guard(dialog)  # (its parent the window: Qt deletes it with it)
    state["guard"] = guard

    def idle():
        # (a tool that never called busy_end must not leave FontLab deaf: its work over (owner.busy off)
        # and not moved for GUARD_IDLE_SECONDS while the event loop ran. A tool still busy keeps its guard:
        # another window's work pumping events meanwhile is no sign that this one is over (review 12),
        # unless nothing has moved anywhere for GUARD_LOST_SECONDS)
        try:
            quiet = time.time() - state.get("pumped", 0.0)
            anywhere = time.time() - _LAST_PUMP[0]
            if (quiet > GUARD_IDLE_SECONDS and not getattr(owner, "busy", False)) or anywhere > GUARD_LOST_SECONDS:
                _guard_off(owner)
        except Exception:
            pass

    guard.idle = idle  # (held)
    guard.setInterval(1000)
    guard.connect("timeout()", idle)
    guard.start()
    try:
        QtGui.QApplication.instance().installEventFilter(guard)
    except Exception:
        pass


def _guard_off(owner):
    QtGui = _qt()[1]
    state = _busy_state(owner)
    guard = state.pop("guard", None)
    if guard is None:
        return
    try:
        guard.stop()
        QtGui.QApplication.instance().removeEventFilter(guard)
    except Exception:
        pass


MENU_HOOK_RETRY_MS = 500  # how often FreeLab's startup block looks again for the Scripts menu,
MENU_HOOK_TRIES = 240  # and for how long (two minutes): at launch, FontLab runs it before its main window is built


def menu_hooked():
    """Whether the Scripts menu carries the current hook."""
    QtCore, QtGui = _qt()
    main = AutoKerningDialog.main_window()
    if main is None:
        return False
    for menu in main.findChildren(QtGui.QMenu):
        if menu.objectName == SCRIPTS_MENU:
            try:
                return int(menu.property(MENU_ORDER_PROP) or 0) >= MENU_HOOK_VERSION
            except (TypeError, ValueError):
                return False
    return False


def hook_menu_order_soon(tries=MENU_HOOK_TRIES):
    """hook_menu_order, now or as soon as FontLab has built its Scripts menu (FreeLab's startup block
    runs before the main window exists: the menu kept FontLab's alphabetical order until a FreeLab
    script was opened)."""
    QtCore, QtGui = _qt()
    try:
        hook_menu_order()
        if menu_hooked() or tries <= 0:
            return
    except Exception:
        pass
    retry = lambda: hook_menu_order_soon(tries - 1)
    # held, with this module: PythonQt drops a slot no Python object holds, and Python 2 empties a
    # dropped module's globals (a FreeLab script loading auto kerning again replaces it in sys.modules)
    sys._freelab_menu_retry = (retry, sys.modules.get(__name__))
    QtCore.QTimer.singleShot(MENU_HOOK_RETRY_MS, retry)


COMPILE_TIP = u"Compile features ("  # the Features panel's button (its tooltip names its shortcut after this)


def fontlab_widget(key, matches):
    """One of FontLab's own widgets, found by matches(widget): the one found before while it is there and
    still matches (sys._freelab_found), else looked for among every widget, a walk that wraps thousands
    (each wrapper a thing PythonQt frees later): once, not at every compile or every read."""
    QtGui = _qt()[1]
    found = getattr(sys, "_freelab_found", None)
    if found is None:
        found = sys._freelab_found = {}
    held = found.get(key)
    try:
        if held is not None and widget_alive(held) and matches(held):
            return held
    except Exception:
        pass
    found.pop(key, None)
    for widget in QtGui.QApplication.instance().allWidgets():
        try:
            if matches(widget):
                found[key] = widget  # (FontLab's: its wrapper held deletes nothing)
                return widget
        except Exception:
            continue
    return None


def compile_features():
    """Compile the current font's features as the Features panel's button does (FontLab has no call for
    it): True once clicked, False when the panel was never made (open it once: Window > Panels)."""
    button = fontlab_widget("compile", lambda widget: (
        widget.inherits("QAbstractButton") and widget.objectName == "buttonCompile"
        and (u"%s" % widget.toolTip).startswith(COMPILE_TIP)))
    if button is None:
        return False
    button.click()
    return True


def compile_box():
    """The "Compile after writing" check box a dialog that writes feature code shows beside its button."""
    QtGui = _qt()[1]
    box = QtGui.QCheckBox(u"Compile after writing.")
    box.setChecked(True)
    box.setWhatsThis(u"Compiles the font's features right after the code is written, as the <i>Features</i> panel's "
                     u"<i>Compile</i> button does, so the new code can be tried at once. Off: the code is only "
                     u"written (the font's other feature code may not compile yet, or a large font takes a while).")
    return box


COMPILE_READ_MS = 400  # after the click: FontLab's Output panel read for what the compiler said, again while it grows
COMPILE_READS_MAX = 8  # reads at most (a slow compile's output is read once it stops growing)
COMPILE_EMPTY_READS_MAX = 40  # reads at most while the panel stays empty (16 seconds: see read_again)


def read_again(reads, before, last, after):
    """Whether the Output panel is read once more after a compile (reads: done so far; before: its text
    before the click; last: at the read before; after: now). FontLab clears the panel as it compiles and
    prints nothing when the code compiles, so an empty panel is either a clean compile or one still under
    way: it is read for COMPILE_EMPTY_READS_MAX reads before it counts as clean (a font of 42,000 kerned
    pairs was said to compile with no errors while its code named a class it lacks: owner's image 342).
    Text is read until it stops growing, or COMPILE_READS_MAX reads."""
    if not (after or u"").strip():
        return reads < COMPILE_EMPTY_READS_MAX
    return reads < COMPILE_READS_MAX and (after != last or after == before)
COMPILE_ERROR_MARKS = (u"[F]", u"[E]", u"error", u"Error")


def output_view():
    """FontLab's Output panel's text box (where the compiler writes its errors), or None. FontLab has two
    of that name, the first hidden and empty (live: the compiler's [N] and [W] lines were in the other,
    and the log said the panel showed nothing): the one shown, else one that holds text, else either."""
    def output(widget):
        return widget.objectName == "textOutput" and widget.inherits("QTextEdit")
    return (fontlab_widget("output", lambda widget: output(widget) and widget.isVisible())
            or fontlab_widget("output (with text)", lambda widget: output(widget) and bool(u"%s" % widget.toPlainText()))
            or fontlab_widget("output (any)", output))


def output_text(view=None):
    """The Output panel's text (output_view, or the text box given: a compile's before and after are read
    from the same one), or None."""
    view = view if view is not None else output_view()
    try:
        return u"%s" % view.toPlainText() if view is not None else None
    except Exception:
        return None


def compiled_note(box, log=None):
    """After writing: compiled (when the box is checked), and what the log says of it. With log, what the
    compiler printed in FontLab's Output panel is read just after, once it stops changing: an error goes in
    the log, in red, else that FontLab reported none (compile_report)."""
    QtCore = _qt()[0]
    if box is None or not box.checked:
        return u" Compile the features in FontLab's <i>Features</i> panel to try it."
    view = output_view()  # (before and after read from the same text box: FontLab has two of that name)
    before = output_text(view)
    if not compile_features():
        return (u" Not compiled: FontLab's <i>Features</i> panel was never opened in this session (<i>Window &gt; "
                u"Panels &gt; Features</i>); compile there.")
    if log is None or before is None:
        return u" Compiled: see the <i>Features</i> panel for any error."
    state = {"last": None, "reads": 0}

    def read():
        try:
            after = output_text(view) or u""
            state["reads"] += 1
            if read_again(state["reads"], before, state["last"], after):
                state["last"] = after  # the first read, still growing, or not changed yet: read again
                QtCore.QTimer.singleShot(COMPILE_READ_MS, read)
                return
            log.add(*compile_outcome(before, after))
        except Exception:
            pass  # a timer's handler must not raise
    _COMPILE_READS.append(read)
    del _COMPILE_READS[:-8]
    QtCore.QTimer.singleShot(COMPILE_READ_MS, read)
    return u" Compiled: what FontLab's compiler reports follows in this log."


def compiler_said(before, after):
    """What a compile printed in FontLab's Output panel, from its text before the click and after. FontLab
    clears the panel at each compile (the owner, 2026-11-15), so what it holds after is the compile's own,
    an empty panel meaning no message at all (the log said "showed nothing from the compiler: see the
    Features panel for any error" after every clean compile); where the panel kept the old text and added
    to it, what was added."""
    if before and after != before and after.startswith(before):
        return after[len(before):]
    return after


COMPILE_UNCHANGED = (u"FontLab's <i>Output</i> panel still shows what it showed before the compile: see the "
                     u"<i>Features</i> panel for any error.")


def compile_outcome(before, after):
    """(the log's line, its level) once the Output panel has been read for the last time: compile_report of
    what the compile printed; but a panel that holds text and never changed (read to COMPILE_READS_MAX) is
    not taken for this compile's (its old error, or its old silence): it says so (COMPILE_UNCHANGED). An
    empty panel that stayed empty is a compile with no message."""
    if after == before and before.strip():
        return COMPILE_UNCHANGED, "info"
    return compile_report(compiler_said(before, after))


def compile_report(said):
    """(the log's line, its level) for what a compile printed (compiler_said): its errors, in red; else
    that FontLab reported none, with its warnings where it gave some."""
    lines = [line.strip() for line in said.splitlines() if line.strip()]
    errors = [line for line in lines if any(mark in line for mark in COMPILE_ERROR_MARKS)]
    if errors:
        text = u"The features did not compile: %s" % html(u" ".join(errors[:3]))
        hint = compile_hint(u" ".join(errors))
        return (u"%s %s" % (text, hint) if hint else text), "error"
    warnings = [line for line in lines if u"[W]" in line]
    if warnings:
        return (u"Compiled: FontLab reported no errors, and %s: %s" % (
            u"a warning" if len(warnings) == 1 else u"%d warnings" % len(warnings),
            html(u" ".join(warnings[:3]))), "info")
    return u"Compiled: FontLab reported no errors.", "info"


COMPILE_HINTS = (
    # (what FontLab's compiler says, what the log adds: the error is in the font's own code, and where it is fixed)
    (u"use not allowed in 'aalt'", u"That is the font's own <i>aalt</i>, not the code just written: FontLab writes "
                                   u"aalt's lookups inside it when it opens some fonts, and its own compiler refuses "
                                   u"them. %s lists it and fixes it."),
)  # (owner's image 383: CJK Vertical's write was blamed for the font's own aalt)


def compile_hint(said):
    """The log's words after a compile error the font's own code causes, naming where it is fixed (COMPILE_HINTS);
    u"" for any other."""
    for words, hint in COMPILE_HINTS:
        if words in said:
            return hint % tool_link(u"Feature Check")
    return u""


_COMPILE_READS = []  # (held: PythonQt drops a slot no Python object holds)


def plain_buttons(dialog):
    """No default button in a FreeLab dialog: Qt frames the default one in a light color dark mode
    leaves light (and Enter in a field would click it). Called as each dialog is built: its scroll
    bars made flat too (flat_scroll_bars)."""
    QtCore, QtGui = _qt()
    flat_scroll_bars(dialog)
    try:  # minimize and maximize in the title bar too (set before the window shows: setting flags hides it)
        if not _property(dialog, "visible"):
            dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint
                                  | QtCore.Qt.WindowMaximizeButtonHint)
    except Exception:
        pass
    try:
        for button in dialog.findChildren(QtGui.QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
    except Exception:
        pass
    style_combos(dialog)  # (as built: a dropdown opened before the first update_states opens below its box too)
    try:
        install_filters(dialog)  # (as built; then as widgets are added)
    except Exception:
        pass
    watch_states(dialog)


# A dialog's states kept in step with what it shows, every STATES_MS while it is shown: Check all and
# Check none (and the like) grayed out when the list beside them has nothing to check, and a
# dropdown with one choice drawn as its text (no arrow, nothing to open).
STATES_MS = 300
CHECK_BUTTON_TEXTS = (u"Tick all", u"Tick none", u"Tick only", u"Tick high-value", u"Tick often",
                      u"Check all", u"Check none", u"Check only")  # ("Check" was their verb before the owner's image 261)
SINGLE_PROP = "freelab_single_choice"
SINGLE_SHEET = (u"QComboBox { border: none; background: transparent; padding-left: 0px; } "
                u"QComboBox::drop-down { width: 0px; border: none; } QComboBox::down-arrow { image: none; width: 0px; }")


def _ancestors(widget):
    chain = []
    while widget is not None:
        chain.append(widget)
        widget = widget.parentWidget()
    return chain


def _shared_depth(a, b):
    """How deep the nearest widget holding both a and b lies (more: closer together)."""
    up = _ancestors(b)
    for depth, widget in enumerate(_ancestors(a)):
        if widget in up:
            return -depth
    return -1000


def has_checkable_items(view):
    """True when a tree or list widget shows an item with a check box: one given a check state (Qt makes
    every item user-checkable by default, a section's heading row too, but draws a box only once a
    check state is set)."""
    QtCore = _qt()[0]
    checkable, role = QtCore.Qt.ItemIsUserCheckable, QtCore.Qt.CheckStateRole

    def boxed(item, state):
        return bool(int(item.flags()) & int(checkable)) and state is not None

    if view.inherits("QTreeWidget"):
        pending = [view.topLevelItem(i) for i in range(view.topLevelItemCount)]
        while pending:
            item = pending.pop()
            if item is None:
                continue
            if boxed(item, item.data(0, role)):
                return True
            pending.extend(item.child(i) for i in range(item.childCount()))
        return False
    if view.inherits("QListWidget"):  # (a list's item has no column)
        return any(boxed(view.item(i), view.item(i).data(role)) for i in range(view.count))
    return True  # a view of another kind: left to its dialog


def single_choice(combo):
    """A dropdown with one choice (or none) drawn as its text; a real dropdown again once it has more."""
    QtCore = _qt()[0]
    single = combo.count <= 1 and not combo.editable
    if single == bool(combo.property(SINGLE_PROP)):
        return
    if single:
        combo.setProperty(SINGLE_PROP, combo.styleSheet or u" ")  # its own sheet, put back later
        combo.setStyleSheet(SINGLE_SHEET)
        combo.setProperty(LEAVE_ALONE_PROP, True)  # its text in the dialog's colors: nothing for dark mode to map
        combo.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        combo.setFocusPolicy(QtCore.Qt.NoFocus)
    else:
        sheet = (u"%s" % combo.property(SINGLE_PROP)).strip()
        combo.setProperty(SINGLE_PROP, None)
        combo.setStyleSheet(sheet)
        # The flag goes with the sheet it was for: a long list's sheet (put back here) keeps it, or dark
        # mode takes the box for a styled input and garbles it
        combo.setProperty(LEAVE_ALONE_PROP, True if sheet == LONG_SHEET else None)
        combo.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        combo.setFocusPolicy(QtCore.Qt.StrongFocus)


LONG_CHOICES = 24  # a dropdown with more choices than this opens as a list of this many rows, scrolled
LONG_SHEET = u"QComboBox { combobox-popup: 0; }"
# Qt's style opens a dropdown as a menu laid over the box, with the current choice under the pointer:
# with several hundred choices (Proof's languages) it covered the screen from top to bottom, its ends
# cut off, and a short one whose current choice was its last (Glyph Compose's Character set on All) opened
# upward, over the box, with room to spare below. With this one property every FreeLab dropdown opens
# as a list hanging from its box (above it only when the screen has no room below), at most LONG_CHOICES
# rows, scrolled past them. The property needs a stylesheet on the box, which dark mode would take for a
# styled input and map: the box asks to be left as drawn, which is what a plain box gets anyway (dark
# mode's Fusion draws it from the dark palette, the sheet holding no color).


POPUP_GRAY_PROP = "freelab_popup_gray"  # on a dropdown's list an earlier build gave an opacity effect (taken off)


def leave_popup_alone(combo):
    """A dropdown's popup list: marked for dark mode to leave as drawn (LEAVE_ALONE_PROP, on the list
    and on the popup window holding it, QComboBoxPrivateContainer): dark mode recolored it as one of
    FontLab's lists, its light text in colored smears and tinted (owner's image 162). Left alone, it
    shows Windows' ClearType, as every other text of the interface does (live, 2026-11-17: the same
    share of colored edge pixels in the popup, in another tool's popup, and in the window's own labels).
    An opacity effect meant to smooth it in gray changed nothing (the list paints an opaque background,
    so Qt keeps ClearType) and cost an offscreen render at every repaint: a list that still has one from
    a session before is given it back (POPUP_GRAY_PROP). Called for every dropdown of every FreeLab
    window, at each update_states (style_combos, through long_choice)."""
    try:
        view = combo.view()
    except Exception:
        return
    if view is None:
        return
    try:
        for widget in (view, view.parentWidget()):
            if widget is not None and not widget.property(LEAVE_ALONE_PROP):
                widget.setProperty(LEAVE_ALONE_PROP, True)
    except Exception:
        pass
    try:
        if view.property(POPUP_GRAY_PROP):  # (an effect put on by an earlier build of this module)
            view.setGraphicsEffect(None)  # (Qt deletes it)
            view.setProperty(POPUP_GRAY_PROP, False)
    except Exception:
        pass


def long_choice(combo):
    """A dropdown (every one, however many its choices) opens as a list under its box, scrolled past
    LONG_CHOICES rows; the sheet and its flag go on together (a one-choice dropdown's own sheet comes
    first, and gives this one back when it has choices again: single_choice). A sheet of the box's own
    is left as it is. Its popup list is left alone by dark mode (leave_popup_alone), whatever its sheet."""
    leave_popup_alone(combo)
    if combo.property(SINGLE_PROP):
        return
    sheet = combo.styleSheet or u""
    if sheet and sheet != LONG_SHEET:
        popup_scroll_bar(combo)
        return  # a sheet of its own: left as it is
    if not sheet:
        combo.setMaxVisibleItems(LONG_CHOICES)
        combo.setStyleSheet(LONG_SHEET)
    if not combo.property(LEAVE_ALONE_PROP):  # (taken off when a one-choice dropdown got its choices back)
        combo.setProperty(LEAVE_ALONE_PROP, True)
    popup_scroll_bar(combo)


def popup_scroll_bar(combo):
    """A dropdown's list scrolls with a scroll bar, FreeLab's flat one (SCROLL_SHEET), when its choices
    pass LONG_CHOICES. Qt sets the list's bar off for a style that opens dropdowns as menus (Fusion's)
    when the list is first made, and leave_popup_alone makes it before LONG_SHEET is on: the Font
    Builder's 300 sets scrolled with the wheel alone, no bar to show there were more (owner's image
    163)."""
    try:
        QtCore = _qt()[0]
        view = combo.view()
        if view is None:
            return
        # (a property in PythonQt, read as one: called, it raised, and the bar stayed off, live)
        if _property(view, "verticalScrollBarPolicy") != QtCore.Qt.ScrollBarAsNeeded:
            view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        bar = view.verticalScrollBar()
        if bar is not None and (_property(bar, "styleSheet") or u"") != SCROLL_SHEET:
            bar.setStyleSheet(SCROLL_SHEET)
    except Exception:
        pass
    popup_width(combo)


POPUP_WIDTH_PROP = "freelabPopupWidth"  # on a dropdown: the choices its list was last made wide enough for
POPUP_PAD = 36  # pixels a list row takes beside its text (margins, and the scroll bar of a long list)


def popup_width(combo):
    """A dropdown's list as wide as its longest choice, never cut short: Qt makes the list as wide as the box,
    and a longer choice ended in "..." (owner's image 357: "Korean (no... the font)"). Measured again only
    when the choices change. The width is measured with a QFontMetrics of the list's font: PythonQt has no
    widget.fontMetrics(), and the call that used it failed silently, every list as wide as its box (live
    2026-11-19, the owner's image 357 again)."""
    QtCore, QtGui = _qt()
    try:
        view = combo.view()
        if view is None:
            return
        count = int(_property(combo, "count"))
        texts = [u"%s" % combo.itemText(k) for k in range(count)]
        key = u"%d:%s" % (count, u"\n".join(texts))
        if (u"%s" % (combo.property(POPUP_WIDTH_PROP) or u"")) == key:
            return
        metrics = QtGui.QFontMetrics(_property(view, "font"))
        widest = max([metrics.width(text) for text in texts] or [0])
        view.setTextElideMode(QtCore.Qt.ElideNone)
        view.setMinimumWidth(int(widest) + POPUP_PAD)
        combo.setProperty(POPUP_WIDTH_PROP, key)  # (set once measured: a failure is tried again)
    except Exception:
        pass


# What every FreeLab window's widgets share through one event filter (put on by update_states as they
# appear, so a tool's later widgets have it too): a right-click on a grayed-out control shows its help
# (Qt sends no context menu to a disabled widget); a tooltip as wide as its window allows, its paragraphs
# a blank line apart; and a click on a list's empty part, or on the window beside every list, clears the
# lists' selection (a row could not be unselected).
FILTER_PROP = "freelab_filtered"  # on a widget (a list: on the list) once the window's filter is on it
WINDOW_FILTER_PROP = "freelab_window_filter"  # on a window: its filter's number in sys._freelab_window_filters
KEEP_SELECTION_PROP = "freelab_keep_selection"  # on a list whose selection must stay (a navigator, a filter)
OWN_TIPS_PROP = "freelab_own_tips"  # on a widget or list that lays its tooltips out itself
# The lists a tool's code needs a row selected in (its page navigator, its filter by script, the lists
# feeding another), by the tool's attribute, for the tools that do not set KEEP_SELECTION_PROP themselves
KEEP_SELECTION = {"Font Check": ("script_tree", "language_tree", "set_tree", "family_tree"), "Proof": ("page_list",)}
OWN_TIPS = ("Font Check",)  # tools whose lists build their rows' tooltips as they show (left to them)
HELP_KINDS = ("QAbstractButton", "QComboBox", "QAbstractSpinBox", "QLineEdit", "QAbstractSlider", "QLabel",
              "QSplitterHandle", "QGroupBox", "QTabBar")  # (a splitter's handle: Feature Code's tooltip came out four
# words wide; a tab bar: each tab's own help, show_tab_help)
NOT_BLANK = ("QAbstractButton", "QComboBox", "QAbstractSpinBox", "QLineEdit", "QAbstractSlider", "QTabBar",
             "QAbstractScrollArea", "QSplitterHandle", "QMenu")  # a press on these is no click beside the lists
TIP_WIDTH = (360, 900)  # a tooltip is at most half its window's width, within these (pixels)
TIP_MARGIN = 8  # pixels added to a tooltip's longest line, so that it does not wrap
_TAG = re.compile(u"<[^>]+>")
_BREAK = re.compile(u"<br\\s*/?>", re.IGNORECASE)
# a line break after a sentence's end is a new paragraph (a list of names, a line each, is not)
_PARAGRAPH = re.compile(u"([.!?:\N{HORIZONTAL ELLIPSIS}](?:</[biBI]>)?)<br>(?!<br>)")


def tip_width(window_width):
    """The widest a window's tooltips are: half its width, within TIP_WIDTH."""
    return max(TIP_WIDTH[0], min(TIP_WIDTH[1], int(window_width) // 2))


def tip_built(text):
    """Whether a tooltip is laid out already by its tool (a table, a page): left as it is."""
    lowered = text.lower()
    return any(mark in lowered for mark in (u"<table", u"<html", u"<qt", u"<p>", u"<p ", u"<div"))


def _plain(line):
    """A rich line's text, as measured."""
    return (_TAG.sub(u"", line).replace(u"&nbsp;", u" ").replace(u"&lt;", u"<").replace(u"&gt;", u">")
            .replace(u"&amp;", u"&"))


def tip_html(text, width, measure):
    """A tooltip laid out for its window: rich text, a blank line between its paragraphs, as wide as its
    longest line when that fits in width (a short tooltip stays on one line: Qt wrapped short ones into
    a narrow column of a few words), else width. measure(text) gives a line's width in pixels. None for
    one left as it is (empty, or laid out by its tool)."""
    text = u"%s" % (text or u"")
    if not text.strip() or tip_built(text):
        return None
    if not _TAG.search(text):
        text = html(text)
    text = _BREAK.sub(u"<br>", text.replace(u"\r\n", u"\n").replace(u"\n", u"<br>"))
    text = _PARAGRAPH.sub(lambda m: m.group(1) + u"<br><br>", text)
    longest = 0
    for line in text.split(u"<br>"):
        if line:
            longest = max(longest, int(measure(_plain(line)) * (1.1 if u"<b>" in line else 1.0)))
    return (u'<table width="%d" cellspacing="0" cellpadding="0"><tr><td>%s</td></tr></table>'
            % (min(width, longest + TIP_MARGIN), text))


def disabled_help(widget):
    """What a right-click on a grayed-out control shows: its What's This, else its tooltip, else its
    nearest container's What's This (as Qt's own right-click finds one); u"" for none."""
    for name in ("whatsThis", "toolTip"):
        value = _property(widget, name)
        if value:
            return u"%s" % value
    parent = widget.parentWidget()
    while parent is not None:
        value = _property(parent, "whatsThis")
        if value:
            return u"%s" % value
        if parent.isWindow():
            break
        parent = parent.parentWidget()
    return u""


def _inherits_any(widget, kinds):
    return any(widget.inherits(kind) for kind in kinds)


def keeps_selection(view):
    """Whether a list's selection must stay when a click falls beside it (KEEP_SELECTION_PROP, or its
    tool's KEEP_SELECTION), or it selects nothing anyway."""
    try:
        if view.property(KEEP_SELECTION_PROP):
            return True
        if int(_property(view, "selectionMode")) == 0:  # NoSelection
            return True
    except Exception:
        return True
    owner = window_owner(view)
    for name in KEEP_SELECTION.get(getattr(owner, "tool", None), ()):
        held = getattr(owner, name, None)
        if held is not None and (held is view or held == view):
            return True
    return False


def clear_selection(view):
    """A list's selection and its current row cleared (its handlers hear it, as when a row is
    unselected); False when it had none."""
    try:
        model = view.selectionModel()
        if model is None or not _property(model, "hasSelection"):
            return False
        view.clearSelection()
        try:
            model.clearCurrentIndex()
        except Exception:
            pass
        return True
    except Exception:
        return False


def blank_press(window, target):
    """Whether a press on target (the widget under the pointer) is a click beside the lists: on the
    window itself, a label or a frame, never on a control (a grayed-out one included), a list, or a
    picture a tool draws (previews: their pair is dragged or clicked)."""
    widget = target
    while widget is not None and not (widget is window or widget == window):
        if widget.property(WINDOW_BODY_PROP):
            widget = widget.parentWidget()  # (the scroll area a small screen's window holds its content in)
            continue
        if _inherits_any(widget, NOT_BLANK) or widget.property(LEAVE_ALONE_PROP) or _property(widget, "mouseTracking"):
            return False
        widget = widget.parentWidget()
    return True


def clear_selections(window):
    """Every list of the window cleared but those that keep theirs; the lists cleared, as a list."""
    QtGui = _qt()[1]
    cleared = []
    for view in window.findChildren(QtGui.QAbstractItemView):
        try:
            if not (view.window() is window or view.window() == window) or not _property(view, "visible"):
                continue  # (a dropdown's list, another window's)
            if view.inherits("QHeaderView"):
                continue  # (a list's header shares its selection: clearing it cleared Font Check's lists, live)
            if not keeps_selection(view) and clear_selection(view):
                cleared.append(view)
        except Exception:
            continue
    return cleared


def show_disabled_help(widget, where):
    """The What's This menu Qt shows on a right-click, for a grayed-out control: its help once picked."""
    QtGui = _qt()[1]
    text = disabled_help(widget)
    if not text:
        return False
    menu = QtGui.QMenu(widget.window())
    action = menu.addAction(u"What's This?")
    picked = menu.exec_(where)
    if picked is not None and widget_alive(widget) and (picked is action or picked.text == action.text):
        center = _property(widget, "rect").center()
        QtGui.QWhatsThis.showText(widget.mapToGlobal(center), text, widget)
    return True


def _view_of(viewport):
    """The list whose viewport this is, or None."""
    try:
        view = viewport.parentWidget()
        if view is not None and view.inherits("QAbstractItemView"):
            return view
    except Exception:
        pass
    return None


def show_tip(obj, event, view=None):
    """A tooltip laid out for its window (tip_html): True once shown, False to leave it to Qt."""
    QtCore, QtGui = _qt()
    if obj.property(OWN_TIPS_PROP) or (view is not None and view.property(OWN_TIPS_PROP)):
        return False
    rect = None
    if view is not None:
        if getattr(window_owner(view), "tool", None) in OWN_TIPS:
            return False
        index = view.indexAt(event.pos())
        if not index.isValid():
            return False
        text = index.data(QtCore.Qt.ToolTipRole)
        rect = view.visualRect(index)
    else:
        text = _property(obj, "toolTip")
    if not text:
        return False
    metrics = QtGui.QFontMetrics(QtGui.QToolTip.font())
    laid_out = tip_html(text, tip_width(_property(obj.window(), "width")), lambda line: metrics.width(line))
    if laid_out is None:
        return False
    if rect is not None:
        QtGui.QToolTip.showText(event.globalPos(), laid_out, obj, rect)
    else:
        QtGui.QToolTip.showText(event.globalPos(), laid_out, obj)
    return True


def filter_event(window, obj, event, pending):
    """The window's filter: True when the event was handled here. pending holds a grayed-out control
    right-clicked, until its context menu comes (or does not)."""
    QtCore = _qt()[0]
    kind = event.type()
    if kind in (KEY_PRESS, SHORTCUT_OVERRIDE):
        return undo_key_event(window, obj, event)  # (Ctrl+Z and the like run FontLab's own Undo and Redo)
    if kind == 2 and int(event.button()) == int(QtCore.Qt.LeftButton) and obj.inherits("QAbstractButton") \
            and _property(obj, "enabled"):
        commit_typing(window, obj)  # (the value typed in a field taken before the button acts on it)
    if kind == 110:  # ToolTip
        return show_tip(obj, event, _view_of(obj))
    if kind in (CONTEXT_MENU, WHATS_THIS) and obj.inherits("QTabBar") and _property(obj, "enabled"):
        # a tab's own help, where it was clicked (owner's image 329: the window's, in the middle of it)
        return show_tab_help(obj, event, kind == CONTEXT_MENU)
    if kind == SHOW_EVENT and (obj is window or obj == window):
        # The window's states set before it first paints: set on update_states' first tick, its controls
        # showed usable and its separators shown for a moment (owner's images 275, 276, 282)
        try:
            owner = window_owner(window)
            module = sys.modules.get(__name__)
            (getattr(module, "update_states", None) or update_states)(owner.dialog if owner is not None else window,
                                                                         hidden_too=True)
            (getattr(module, "keep_center", None) or keep_center)(owner)
            (getattr(module, "share_splitters", None) or share_splitters)(window)
        except Exception:
            pass
        return False
    if obj is window or obj == window:
        if kind == PALETTE_CHANGE:
            # (dark mode switched on or off: the tab bars take the sheet of the new palette, tab_sheet)
            (getattr(sys.modules.get(__name__), "flat_scroll_bars", None) or flat_scroll_bars)(window)
            return False
        if kind == RESIZE_EVENT:
            owner = window_owner(window)
            log = getattr(owner, "log", None) if owner is not None else None
            if log is not None and hasattr(log, "yield_room"):
                log.yield_room(window)
            return False
        if kind == 2 and int(event.button()) == int(QtCore.Qt.LeftButton):  # a press no widget took
            target = window.childAt(event.pos())
            if blank_press(window, target if target is not None else window):
                clear_selections(window)
        if kind == CONTEXT_MENU and window_owner(window) is not None:  # (never FontLab's own window, docked)
            return show_context_help(window, event)
        return False
    view = _view_of(obj)
    if view is not None:
        if kind == 2 and int(event.button()) == int(QtCore.Qt.LeftButton) and not view.indexAt(event.pos()).isValid():
            if not keeps_selection(view):
                clear_selection(view)  # a click under the last row
        return False
    if _property(obj, "enabled"):
        return False
    if kind == 82:  # ContextMenu, if Qt sends one to the grayed-out control
        pending[:] = []
        return show_disabled_help(obj, event.globalPos())
    if kind == 3 and int(event.button()) == int(QtCore.Qt.RightButton):  # MouseButtonRelease
        pending[:] = [obj, event.globalPos()]

        def later():
            try:
                if pending:
                    widget, where = pending[0], pending[1]
                    pending[:] = []
                    show_disabled_help(widget, where)
            except Exception:
                pass  # a timer's handler must not raise
        pending.append(later)  # (held until it runs)
        QtCore.QTimer.singleShot(0, later)
        return True
    return False


SHOW_EVENT = 17  # QEvent::Show, sent before the window's first paint
CONTEXT_MENU, WHATS_THIS = 82, 111  # QEvent::ContextMenu (a right-click), QEvent::WhatsThis (a click after "?")
RESIZE_EVENT = 14  # QEvent::Resize: the window's log yields room first (Log.yield_room)
PALETTE_CHANGE = 39  # QEvent::PaletteChange: dark mode switched (tab_sheet)
WATCHED_EVENTS = (2, 3, 6, 14, 17, 39, 51, 82, 110, 111)  # MouseButtonPress, MouseButtonRelease, KeyPress, Resize,
# Show, PaletteChange, ShortcutOverride, ContextMenu, ToolTip, WhatsThis


def help_section(text, title):
    """The part of a window's help about one of its tabs ("<i>Kerning</i>: the glyph pairs kerned
    differently..." up to the next line break or the next tab's title), its first letter capitalized; u""
    when the help has none."""
    if not text or not title:
        return u""
    found = re.search(u"<i>%s</i>:\\s*(.*?)(?=<br|\\s<i>[^<]{1,40}</i>:|$)" % re.escape(title), u"%s" % text, re.S)
    if found is None:
        return u""
    part = re.sub(u"\\s+", u" ", found.group(1)).strip()
    return part[:1].upper() + part[1:] if part else u""


def tab_title(text):
    """A tab's title without its count ("Compatibility (52)": "Compatibility") or its shortcut's ampersand."""
    return re.sub(u"\\s*\\([^()]*\\)$", u"", (u"%s" % (text or u"")).replace(u"&", u"")).strip()


def tab_help(bar, index):
    """A tab's help: its own What's This, else its tooltip, else what the bar's help or its window's says
    of it (help_section), else the help of the list on the page it shows (the pages beside the bar); u""
    for none."""
    try:
        for text in (bar.tabWhatsThis(index), bar.tabToolTip(index)):
            if text:
                return u"%s" % text
        owner = window_owner(bar)
        dialog = owner.dialog if owner is not None else bar.window()
        title = tab_title(bar.tabText(index))
        for holder in (bar, dialog):
            found = help_section(_property(holder, "whatsThis"), title)
            if found:
                return found
        parent = bar.parentWidget()
        pages = _next_widget(parent.layout(), bar) if parent is not None else None
        if pages is not None and pages is not _NOT_FOUND and pages.inherits("QStackedWidget"):
            page = pages.widget(index)
            QtGui = _qt()[1]
            for view in ([page] if page.inherits("QAbstractItemView") else []) + list(page.findChildren(QtGui.QAbstractItemView)):
                text = _property(view, "whatsThis")
                if text:
                    return u"%s" % text
    except Exception:
        pass
    return u""


def _whats_this_menu(window, where):
    """Qt's own right-click menu of help ("What's This?"): whether it was picked."""
    QtGui = _qt()[1]
    menu = QtGui.QMenu(window)
    action = menu.addAction(u"What's This?")
    picked = menu.exec_(where)
    return picked is not None and (picked is action or picked.text == action.text)


def show_tab_help(bar, event, menu):
    """A tab's help (tab_help) where the tab was clicked: after the What's This menu of a right-click (menu),
    or at once in What's This mode. False (left to Qt) where no tab is, or it has no help."""
    QtGui = _qt()[1]
    try:
        index = bar.tabAt(event.pos())
    except Exception:
        return False
    if index is None or index < 0:
        return False
    text = tab_help(bar, index)
    if not text:
        return False
    where = event.globalPos()
    if menu and not _whats_this_menu(bar.window(), where):
        return True
    if widget_alive(bar):
        QtGui.QWhatsThis.showText(where, text, bar)
    return True


def show_context_help(window, event):
    """A right-click's help where the click was, for a widget of a FreeLab window that leaves its right-click
    to its window: the help of the widget under it, else of the nearest container with one, the window's
    last (Qt's own showed it at the middle of that container: owner's image 329, the window's help in the
    middle of the window, far from the click). False to leave it to Qt."""
    QtGui = _qt()[1]
    target = window.childAt(event.pos())
    widget, text = target if target is not None else window, u""
    while widget is not None:
        if widget.inherits("QTabBar"):
            try:
                text = tab_help(widget, widget.tabAt(widget.mapFromGlobal(event.globalPos())))
            except Exception:
                text = u""
        text = text or u"%s" % (_property(widget, "whatsThis") or u"")
        if text or widget is window or widget == window or widget.isWindow():
            break
        widget = widget.parentWidget()
    if not text:
        return False
    where = event.globalPos()
    if _whats_this_menu(window, where) and widget_alive(widget):
        QtGui.QWhatsThis.showText(where, text, widget)
    return True


CHILD_ADDED = 68  # QEvent::ChildAdded, sent to a widget given a child
WATCH_PROP = "freelab_child_watch"  # on a widget once the window's child watch is on it


def install_filters(dialog):
    """The window's filter (filter_event) on the window, its controls, and its lists' viewports, each
    once (FILTER_PROP), new widgets as they appear; True when the window was walked. It is walked
    when its filter is made, then only once a widget of it was given a child (a ChildAdded event,
    which a watch on each of its widgets notes): walking it every tick of update_states (nine
    findChildren, then each widget wrapped and read) took 1.3 ms of its 2.3 ms on Feature Code's
    1,447 widgets, live, every 300 ms in every shown window."""
    QtCore, QtGui = _qt()
    window = dialog.window()
    holder = getattr(sys, "_freelab_window_filters", None)
    if holder is None:
        holder = sys._freelab_window_filters = {}
    key = window.property(WINDOW_FILTER_PROP)
    watcher = holder.get(int(key)) if key is not None else None
    if watcher is None:
        modules, name, own, pending, changed = sys.modules, __name__, filter_event, [], [True]

        class WindowFilter(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == CHILD_ADDED:
                        changed[0] = True
                    if kind not in WATCHED_EVENTS:
                        return False
                    handler = getattr(modules.get(name), "filter_event", None) or own  # (the module loaded now)
                    return bool(handler(window, obj, event, pending))
                except Exception:
                    return False  # an event filter must never raise

        class ChildWatch(QtCore.QTimer):  # (on the widgets the filter is not on: it notes new children only)
            def eventFilter(self, obj, event):
                try:
                    if event.type() == CHILD_ADDED:
                        changed[0] = True
                except Exception:
                    pass
                return False

        # (their parent the window: Qt deletes them with it, never PythonQt at whatever moment Python's
        # collector picks, as it does a parentless object made from Python)
        watcher = WindowFilter(window)
        watcher.changed, watcher.child_watch = changed, ChildWatch(window)
        key = max(list(holder) + [0]) + 1  # (never a number given before: windows let go leave gaps)
        holder[key] = watcher
        window.setProperty(WINDOW_FILTER_PROP, key)
        window.installEventFilter(watcher)
        window.setProperty(WATCH_PROP, True)
    changed = getattr(watcher, "changed", None)
    if changed is not None:
        if not changed[0]:
            return False
        changed[0] = False  # (before the walk: a widget added during it is walked next time)
    for kind in HELP_KINDS + ("QAbstractItemView",):
        found = getattr(QtGui, kind, None)
        if found is None:
            continue  # (a PythonQt without the class: the others still get it)
        for widget in window.findChildren(found):
            try:
                if widget.property(FILTER_PROP) or not (widget.window() is window or widget.window() == window):
                    continue
                # a list's events go to its viewport (its rows, the space under them)
                (widget.viewport() if kind == "QAbstractItemView" else widget).installEventFilter(watcher)
                widget.setProperty(FILTER_PROP, True)
            except Exception:
                continue
    try:
        captions = getattr(sys, "_freelab_window_captions", None)
        if captions is None:
            captions = sys._freelab_window_captions = {}
        captions[int(key)] = find_captions(window)
        for gone_key in [k for k in captions if k not in holder]:
            del captions[gone_key]
    except Exception:
        pass
    child_watch = getattr(watcher, "child_watch", None)
    if child_watch is not None:
        for widget in window.findChildren(QtGui.QWidget):
            try:
                if not widget.property(WATCH_PROP) and (widget.window() is window or widget.window() == window):
                    widget.installEventFilter(child_watch)  # (a dialog opened from this one watches its own)
                    widget.setProperty(WATCH_PROP, True)
            except Exception:
                continue
    return True


CAPTIONED_KINDS = ("QComboBox", "QAbstractSpinBox", "QLineEdit", "QAbstractSlider")  # what a label can caption
CAPTION_MOST = 80  # characters: a longer label is a sentence of its own, never a caption
CAPTION_OWN_TIP_PROP = "freelabCaptionOwnTip"  # on a caption that had help of its own (kept as it is)
_NOT_FOUND = object()


def _next_widget(layout, widget):
    """The widget after widget in the row (layout) holding it, searched through nested layouts: None when
    widget ends its row or a layout follows it, _NOT_FOUND when the layout does not hold it."""
    try:
        count = layout.count()
    except Exception:
        return _NOT_FOUND
    for k in range(count):
        item = layout.itemAt(k)
        if item is None:
            continue
        held = item.widget()
        if held is not None and (held is widget or held == widget):
            for j in range(k + 1, count):
                after = layout.itemAt(j)
                if after is None:
                    continue
                if after.widget() is not None:
                    return after.widget()
                if after.layout() is not None:
                    return None
            return None
        inner = item.layout()
        if inner is not None:
            found = _next_widget(inner, widget)
            if found is not _NOT_FOUND:
                return found
    return _NOT_FOUND


def caption(label, control):
    """label made the caption of control (a dropdown, a field, a spin box): a right-click on it shows the
    control's help, not the window's (owner's image 216), and it is grayed with the control (owner's
    image 281). caption_states keeps both in step."""
    try:
        label.setBuddy(control)
        label.setProperty(CAPTION_PROP, True)
        if _property(label, "whatsThis") or _property(label, "toolTip"):
            label.setProperty(CAPTION_OWN_TIP_PROP, True)
    except Exception:
        pass
    return label


def find_captions(window):
    """Each short label of the window that comes just before a dropdown, a field, or a spin box in its
    row made that control's caption (caption): "Sample:" before its dropdown, "List changes of at least"
    before its spin box. A tool's own captions (caption()) are kept. The captions, as a list."""
    QtGui = _qt()[1]
    found = []
    for label in window.findChildren(QtGui.QLabel):
        try:
            if not (label.window() is window or label.window() == window):
                continue
            if label.property(CAPTION_PROP):
                found.append(label)
                group_gap(label)
                continue
            if label.property(PREVIEW_CAPTION_PROP):
                continue
            if label.buddy() is not None:  # (a tool's own buddy: a caption too)
                caption(label, label.buddy())
                found.append(label)
                continue
            if _property(label, "wordWrap"):
                continue
            text = u"%s" % _property(label, "text")
            if not text.strip() or len(text) > CAPTION_MOST or u"<br" in text or u"\n" in text:
                continue
            parent = label.parentWidget()
            layout = parent.layout() if parent is not None else None
            if layout is None:
                continue
            control = _next_widget(layout, label)
            if control is None or control is _NOT_FOUND or not _inherits_any(control, CAPTIONED_KINDS):
                continue
            caption(label, control)
            found.append(label)
            group_gap(label)
        except Exception:
            continue
    return found


GROUP_GAP = 8  # pixels more before a caption that follows another control in its row (a group's start)
GROUP_GAP_PROP = "freelabGroupGap"  # on a caption given its gap (group_gap): once


def group_gap(label):
    """A wider gap before a caption that starts a group of its row ("Show:" after the Script dropdown), the
    caption and its control left at the row's spacing: every gap was the same, so a caption sat as near the
    group before it as its own control and the row read unevenly (owner's images 389 and 390). Once per
    caption; a caption after its control (a sentence's period) or first in its row gets none."""
    QtGui = _qt()[1]
    try:
        if label.property(GROUP_GAP_PROP):
            return
        label.setProperty(GROUP_GAP_PROP, True)
        parent = label.parentWidget()
        found = _box_holding(parent.layout() if parent is not None else None, label)
        if found is None:
            return
        box, index = found
        if not box.inherits("QHBoxLayout") or index == 0:
            return
        before = box.itemAt(index - 1)
        widget = before.widget() if before is not None else None
        buddy = label.buddy()
        if widget is None or (buddy is not None and (widget is buddy or widget == buddy)):
            return  # (a spacing or a stretch before it already, or the caption follows its own control)
        if not _inherits_any(widget, CAPTIONED_KINDS + ("QAbstractButton",)):
            return
        box.insertSpacing(index, GROUP_GAP)
    except Exception:
        pass


def _box_holding(layout, widget):
    """(the layout that holds widget itself, its index there), searched through nested layouts; None."""
    try:
        count = layout.count()
    except Exception:
        return None
    for k in range(count):
        item = layout.itemAt(k)
        if item is None:
            continue
        held = item.widget()
        if held is not None and (held is widget or held == widget):
            return layout, k
        inner = item.layout()
        if inner is not None:
            found = _box_holding(inner, widget)
            if found is not None:
                return found
    return None


def caption_states(labels):
    """Each caption (caption) grayed as its control is, its help the control's (tooltip and What's This)
    unless it has its own. Cheap enough for each update_states: the captions are found once a window's
    widgets change (install_filters)."""
    for label in labels:
        try:
            control = label.buddy()
            if control is None:
                continue
            on = bool(_property(control, "enabled"))
            if bool(_property(label, "enabled")) != on:
                label.setEnabled(on)
            if label.property(CAPTION_OWN_TIP_PROP):
                continue
            tip = u"%s" % (_property(control, "toolTip") or u"")
            what = u"%s" % (_property(control, "whatsThis") or u"") or tip
            if u"%s" % (_property(label, "toolTip") or u"") != tip:
                label.setToolTip(tip)
            if u"%s" % (_property(label, "whatsThis") or u"") != what:
                label.setWhatsThis(what)
        except Exception:
            continue


def _window_captions(window):
    """The captions found last for the window (install_filters keeps them), as a list."""
    holder = getattr(sys, "_freelab_window_captions", None)
    try:
        key = window.property(WINDOW_FILTER_PROP)
        return list(holder.get(int(key), [])) if holder is not None and key is not None else []
    except Exception:
        return []


def style_combos(dialog):
    """Each dropdown of the dialog as single_choice and long_choice have it."""
    QtGui = _qt()[1]
    for combo in dialog.findChildren(QtGui.QComboBox):
        try:
            single_choice(combo)
            long_choice(combo)
        except Exception:
            pass


def update_states(dialog, hidden_too=False):
    QtGui = _qt()[1]
    if not hidden_too and not _property(dialog, "visible"):
        return
    style_combos(dialog)
    light_fields(dialog)  # (fields made since the window was built: a read's, a tab's)
    try:
        install_filters(dialog)
    except Exception:
        pass
    try:
        no_font_states(dialog)
    except Exception:
        pass
    try:
        caption_states(_window_captions(dialog.window()))
    except Exception:
        pass
    window = dialog.window()  # (a dialog opened from this one is a child too: its buttons and lists are its own)
    # (the buttons shown only: Kerning Check's bottom row holds each tab's buttons, those of the tab shown
    # visible; and of the lists equally near a button, a shown one first: a QStackedWidget's hidden pages
    # are as near as its shown one, and the first of them judged Font Check's buttons)
    buttons = [b for b in dialog.findChildren(QtGui.QPushButton)
               if any((u"%s" % b.text).startswith(t) for t in CHECK_BUTTON_TEXTS) and b.window() == window
               and _property(b, "visible")]
    if not buttons:
        return
    views = [v for v in dialog.findChildren(QtGui.QAbstractItemView)
             if (v.inherits("QTreeWidget") or v.inherits("QListWidget")) and v.window() == window]
    shown = dict((id(v), bool(_property(v, "visible"))) for v in views)
    checkable = {}  # (asked only of the nearest lists: a long list without tick boxes is walked whole)

    def boxed(view):
        if id(view) not in checkable:
            checkable[id(view)] = has_checkable_items(view)
        return checkable[id(view)]

    for button in buttons:
        if not button.isEnabled():
            continue
        key = lambda v: (-_shared_depth(button, v), not shown[id(v)])
        mates = sorted(views, key=key)
        if not mates:
            continue
        # (of the lists equally near, a shown one, then any with tick boxes: Feature Code's first tab has
        # its ligatures' list, which has none, as near its tick buttons as the turns' list)
        nearest = [v for v in mates if key(v) == key(mates[0])]
        if not any(boxed(v) for v in nearest):
            button.setEnabled(False)  # nothing listed: the dialog enables it again once something is


def watch_states(dialog):
    """Keep dialog's states in step (update_states) while it lives; the timer is the dialog's child. Once
    the dialog is closed for good (gone), its timer stops, and its tick is let go when the next dialog
    is watched."""
    QtCore = _qt()[0]
    holder = getattr(sys, "_freelab_state_watchers", None)
    if holder is None:
        holder = sys._freelab_state_watchers = []
    timer = QtCore.QTimer(dialog)
    timer.setInterval(STATES_MS)
    modules, name, own = sys.modules, __name__, update_states  # (no globals below: a reload empties them)
    seen = []

    def shown(widget):
        value = widget.visible
        return value() if callable(value) else value

    def gone():
        """Closed for good: shown once and hidden since, with the FreeLab dialog it was opened from (if
        any) hidden too, or deleted (its wrapper raises). A FreeLab dialog is made anew when reopened."""
        try:
            if shown(dialog):
                seen[:] = [True]
                return False
            if not seen:
                return False  # not shown yet: still being built
            owner = dialog.parentWidget()
            return owner is None or not owner.inherits("QDialog") or not shown(owner)
        except Exception:
            return True

    def tick():
        try:  # through the module as loaded now (a reloaded one empties this copy's globals)
            if gone():
                timer.stop()
                return
            module = modules.get(name)
            (getattr(module, "update_states", None) or own)(dialog)
        except Exception:
            pass  # a timer's handler must not raise
    tick.gone = gone
    tick.dialog, tick.timer = dialog, timer  # (let_go disconnects it: it holds the window)

    def dropped(held):
        try:
            check = getattr(held, "gone", None)
            return check is not None and check()
        except Exception:
            return True
    holder[:] = [held for held in holder if not dropped(held)]
    timer.connect("timeout()", tick)
    holder.append(tick)
    del holder[:-256]  # (only ticks of a copy loaded before this one, which cannot tell, can pile up)
    timer.start()


# ---------------------------------------------------------------------------
# What every FreeLab dialog shares: rich status lines, a log, grid lines, button states, the font's
# History watched, and previews whose neighbors can be clicked
# ---------------------------------------------------------------------------

TOOL_LINK = u"freelab-tool:"  # a link's target that opens a FreeLab tool (tool_link, Log.link_clicked)


def tool_link(title):
    """A FreeLab tool's name as an italic link a log opens it by, in the window's place (owner's image
    220: "Write palt with CJK Spacing first")."""
    return u'<a href="%s%s"><i>%s</i></a>' % (TOOL_LINK, html(title).replace(u" ", u"%20"), html(title))


def with_tool_links(text):
    """Rich text (escaped already) with each FreeLab tool it names made a link (tool_link): a name inside
    a tag or a link already is left alone."""
    parts = re.split(u"(<[^>]*>)", u"%s" % text)
    inside_link = False
    for index, part in enumerate(parts):
        if part.startswith(u"<"):
            lowered = part.lower()
            if lowered.startswith(u"<a "):
                inside_link = True
            elif lowered.startswith(u"</a"):
                inside_link = False
            continue
        if inside_link:
            continue
        for title in sorted(FONT_TOOLS, key=len, reverse=True):
            if title in part:
                part = part.replace(title, u"\x00%d\x00" % FONT_TOOLS.index(title))
        parts[index] = re.sub(u"\x00(\\d+)\x00", lambda m: tool_link(FONT_TOOLS[int(m.group(1))]), part)
    return u"".join(parts)


def html(text):
    """Text made safe for a rich-text label."""
    return (u"%s" % text).replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


GLYPH_LINK = u"glyph:"


def glyph_links(chars):
    """Characters as links a dialog's log handler selects (Log.link_handler gets u"glyph:" and the code
    point in hex): u"Ñ Ť" in a line, each clickable."""
    return u" ".join(u'<a href="%s%04X">%s</a>' % (GLYPH_LINK, code_point(ch), html(ch)) for ch in chars if ch)


def code_point(ch):
    """A character's code point: of both halves when FontLab's narrow Python 2 holds it as a surrogate pair."""
    first = ord(ch[0])
    if 0xD800 <= first < 0xDC00 and len(ch) > 1 and 0xDC00 <= ord(ch[1]) < 0xE000:
        return 0x10000 + ((first - 0xD800) << 10) + (ord(ch[1]) - 0xDC00)
    return first


def linked_code(target):
    """The code point a glyph link names, or None."""
    if not target.startswith(GLYPH_LINK):
        return None
    try:
        return int(target[len(GLYPH_LINK):], 16)
    except ValueError:
        return None


def linked_char(target):
    """The character a glyph link names, or None."""
    code = linked_code(target)
    return unichr_(code) if code is not None else None


GLYPH_NAME_LINK = u"glyphname:"


def glyph_name_links(names):
    """Glyphs by name as links (u"glyphname:" and the name), for glyphs without a character, or whose
    character the interface's fonts may not have: a font's private-use glyphs came out as empty boxes
    in a log. A log that follows the font (Log.follow) draws each as the font does."""
    return u" ".join(u'<a href="%s%s">%s</a>' % (GLYPH_NAME_LINK, html(name), html(name)) for name in names if name)


LOG_PAIRS_SHOWN = 12  # a log line names the pairs it wrote when they are this few


def pair_links(pairs):
    """Glyph pairs, (left name, right name), as links a log that follows the font (Log.follow) draws as
    the font does, each glyph opened on a click: u"AV, To"."""
    return u", ".join(glyph_name_links([left]) + glyph_name_links([right]) for left, right in pairs)


def linked_glyph_name(target):
    """The glyph name a link names, or None."""
    if not target.startswith(GLYPH_NAME_LINK):
        return None
    return target[len(GLYPH_NAME_LINK):] or None


def glyph_of_link(package, target):
    """The name of the font's glyph a link names, by name or by character; None when the font has none."""
    try:
        name = linked_glyph_name(target)
        if name:
            glyph = package.findName(name)
        else:
            code = linked_code(target)
            glyph = package.findUnicode(code) if code is not None else None
        return glyph.name if glyph is not None and not glyph.isNull else None
    except Exception:
        return None


# A log's glyph pictures: their em is this share of the text's line spacing (about the text's size),
# with this much of it above the baseline (a capital with its accent) and below it. The picture is
# centered on the line: more room below than a descender needs brings its baseline up to the text's.
GLYPH_PICTURE_SIZE = 0.9
GLYPH_PICTURE_ABOVE, GLYPH_PICTURE_BELOW = 1.08, 0.78
GLYPH_UNDERLINE = 0.14  # of the em under the baseline: where a linked glyph's underline is drawn
_GLYPH_ANCHOR = re.compile(u'<a href="(glyph(?:name)?:[^"]+)">(.*?)</a>')


def glyph_picture(package, master, name, color, line):
    """A glyph as the font draws it, for a line of text line pixels high, in color (r, g, b): (PNG in
    base 64, width, height), or None when it has no outlines to draw (or anything fails: the text stays)."""
    QtCore, QtGui = _qt()
    try:
        glyph = package.findName(name)
        layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
        if layer is None:
            return None
        path = layer_path(layer)
        if path.isEmpty():
            return None
        em = line * GLYPH_PICTURE_SIZE
        height = max(8, int(round(em * (GLYPH_PICTURE_ABOVE + GLYPH_PICTURE_BELOW))))
        scale = em / float(package.upm)
        bounds = path.boundingRect()
        left = min(0.0, bounds.left())  # (a mark drawn left of its origin, a glyph past its width)
        right = max(float(layer.advanceWidth), bounds.right())
        width = max(4, int(math.ceil((right - left) * scale)) + 2)
        image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(image)
        try:  # ended before anything else can fail: a painter left open on a freed image aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.translate(1.0 - left * scale, em * GLYPH_PICTURE_ABOVE)
            painter.scale(scale, -scale)
            fill_glyph(painter, path, QtGui.QBrush(QtGui.QColor(color[0], color[1], color[2])), layer_parts(layer))
            # underlined as a link's text is (a picture inside a link gets no underline of its own, so
            # some glyphs of a line looked clickable and others not)
            painter.resetTransform()
            under = int(round(em * (GLYPH_PICTURE_ABOVE + GLYPH_UNDERLINE)))
            painter.fillRect(0, min(under, height - 1), width, 1, QtGui.QColor(color[0], color[1], color[2]))
        finally:
            painter.end()
        data = QtCore.QByteArray()
        buffer = QtCore.QBuffer(data)
        buffer.open(QtCore.QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return (u"%s" % str(data.toBase64()), width, height)
    except Exception:
        return None


GLYPH_ICON_SIZE = 32  # pixels per em of a list row's picture of its glyphs (Font Check's 32, near Glyph Compose's 40)
GLYPH_ICON_ROWS = 1000  # rows of a list drawn with their glyphs at most (each picture takes about a millisecond)


def glyph_icon_size(glyphs=1, size=GLYPH_ICON_SIZE):
    """The (width, height) a list gives its rows' pictures of one glyph or of a pair (setIconSize)."""
    return int(size * (1.6 if glyphs == 1 else 2.8)), int(size * 1.45)


def glyph_icon(package, master, names, color, value=0, size=GLYPH_ICON_SIZE):
    """A list row's picture of its glyph, or of its pair at a kerning value, drawn from the font on one
    baseline (as Glyph Compose draws its rows), in color, color glyphs in their own colors; None when a
    glyph has nothing to draw. Lists that show one take LEAVE_ALONE_PROP: dark mode leaves the
    pictures as drawn, in the window's own text color."""
    QtCore, QtGui = _qt()
    try:
        layers = []
        for name in names:
            glyph = package.findName(name)
            layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
            if layer is None:
                return None
            layers.append((layer, layer_path(layer)))
        if all(path.isEmpty() for _, path in layers):
            return None
        scale = float(size) / float(package.upm)
        left = min(0.0, layers[0][1].boundingRect().left()) if not layers[0][1].isEmpty() else 0.0
        advance = sum(float(layer.advanceWidth) for layer, _ in layers) + (value if len(layers) > 1 else 0)
        width = max(8, int(math.ceil((advance - left) * scale)) + 8)
        height = int(size * 1.45)
        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pixmap)
        colored = False
        try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            x = 4 - left * scale
            for index, (layer, path) in enumerate(layers):
                painter.save()
                painter.translate(x, size * 1.1)
                painter.scale(scale, -scale)
                parts = layer_parts(layer)
                colored = colored or bool(parts)
                fill_glyph(painter, path, QtGui.QBrush(QtGui.QColor(color)), parts)
                painter.restore()
                x += (float(layer.advanceWidth) + (value if index == 0 else 0)) * scale
        finally:
            painter.end()
        icon = QtGui.QIcon(pixmap)
        return icon if colored else inked(icon, color)  # (in one color: redrawn in the new one on a switch)
    except Exception:
        return None


def unicode_label(code):
    """A code point as lists show it (u"U+00C0"), u"" for none."""
    return u"U+%04X" % code if code else u""


def header_alignment():
    """Every list's headers: centered (owner's report 141), over text and numbers alike."""
    Qt = _qt()[0].Qt
    return int(getattr(Qt, "AlignHCenter", 0x4) | getattr(Qt, "AlignVCenter", 0x80))


def center_headers(view, columns=None):
    """A list's header texts centered, the header's own default too (columns: those set by a tool, all
    by default)."""
    centered = header_alignment()
    header = _header_of(view)
    try:
        header.setDefaultAlignment(centered)
    except Exception:
        pass
    try:
        count = int(_property(view, "columnCount"))
    except Exception:
        count = 0
    try:
        item = view.headerItem()  # (a tree widget's)
        for column in (range(count) if columns is None else columns):
            item.setTextAlignment(column, centered)
    except Exception:
        pass


def fit_columns(tree, numbers=()):
    """A list's columns as wide as their contents (what each wants, see share_columns), the width then
    shared out so the columns fill the list (share_columns), the headers centered (numbers: the columns
    of numbers, whose cells the tool right-aligns; their headers are centered as every other's)."""
    try:
        tree.header().setStretchLastSection(False)
    except Exception:
        pass
    for column in range(_property(tree, "columnCount")):
        tree.resizeColumnToContents(column)
    note_wants(tree)
    center_headers(tree)
    share_columns(tree, after_fit=True)


TEXT_MARGIN = 4  # pixels: Qt's delegate keeps its text this far from the cell's edge, each side (at most)
HEADER_MARGIN = 8  # pixels: a header section's text from its edges, each side (at most)
ICON_GAP = 4  # pixels between a cell's picture or check box and its text
TEXT_COLUMN_MOST = 360  # pixels: a column of long texts (glyph lists) is no wider; its cells elide, whole in tooltips


def _tree_rows(view):
    """(item, depth) for every row of a tree widget, those of closed groups too."""
    pending = [(view.topLevelItem(i), 0) for i in range(_property(view, "topLevelItemCount"))]
    while pending:
        item, depth = pending.pop()
        if item is None:
            continue
        yield item, depth
        pending.extend((item.child(i), depth + 1) for i in range(item.childCount()))


def fit_rows(view, columns=None, most=None, settle=True):
    """The columns (None: all) of a tree widget as wide as every row's content needs, the rows of closed
    groups included (Qt's resizeColumnToContents measures the rows it shows, and only some of a long
    list's: Kerning Check's names were cut once a group was opened, CJK Vertical's metrics' labels at the
    end of a long list), from the fonts' measures and fixed margins alone, so a width is the same in
    either theme and after any switch (Font Check's "+N" column grew 6 pixels over a round trip, live).
    A row spanning its first column (a section's heading) counts for no column. most: a width no column
    passes (a number for all, or one per column, None for none). Each row's font is measured as Qt draws
    it: what it does not set taken from the list's font now (a font copied from the list before the
    window was shown kept the size of then, while Qt drew the list's later one: Font Check's "+N" column
    was 35 pixels wide on opening and 39 after a dark mode round trip, live). The list is fitted again,
    with the same columns and widths, once its window is shown (settle_fit), and after a dark
    mode switch (retheme_window); settle False: not again (a refit). The widths set, by column."""
    QtCore, QtGui = _qt()
    count = int(_property(view, "columnCount"))
    columns = list(range(count)) if columns is None else list(columns)
    widths, measures = {}, {}
    remember_fit(view, columns, most, settle)
    try:
        view_font = _property(view, "font")
    except Exception:
        view_font = None

    def drawn_font(font):
        """The font as Qt draws it: the list's, with the row's weight and slant (all FreeLab sets on a
        row's font). Made by hand: QFont.resolve's overloads (one takes a number) are not called from
        PythonQt."""
        if view_font is None:
            return font
        try:
            made = QtGui.QFont(view_font)
            made.setBold(bool(font.bold()))
            made.setItalic(bool(font.italic()))
            return made
        except Exception:
            return font

    def text_width(font, text):
        try:
            key = (font.key(), text)
        except Exception:
            key = (None, text)
        found = measures.get(key)
        if found is None:
            metrics = measures.get(key[0]) or QtGui.QFontMetrics(font)
            measures[key[0]] = metrics
            found = measures[key] = max([int(metrics.width(line)) for line in (u"%s" % text).split(u"\n")] or [0])
        return found

    try:
        icon_width = int(_property(view, "iconSize").width())
    except Exception:
        icon_width = 16
    try:
        indent = int(_property(view, "indentation"))
        decorated = bool(_property(view, "rootIsDecorated"))
    except Exception:
        indent, decorated = 20, True
    padding = 2 * TABLE_PADDING[1] + 2 * TEXT_MARGIN + 1  # (the layout's padding, the text's margin, a grid line)
    check_role = QtCore.Qt.CheckStateRole
    for item, depth in _tree_rows(view):
        try:
            spanned = bool(item.isFirstColumnSpanned())
        except Exception:
            spanned = False
        if spanned:
            continue
        for column in columns:
            try:
                width = text_width(drawn_font(item.font(column)), item.text(column))
                icon = item.icon(column)
                if icon is not None and not icon.isNull():
                    width += icon_width + ICON_GAP
                if item.data(column, check_role) is not None:
                    width += CHECK_SIZE + 2 + ICON_GAP  # (the box as the layout draws it, in any style: Fusion's is 14)
                if column == 0:
                    width += indent * (depth + (1 if decorated else 0))
                widths[column] = max(widths.get(column, 0), width + padding)
            except Exception:
                continue
    try:
        header, head_font = view.headerItem(), _property(view.header(), "font")
        for column in columns:
            widths[column] = max(widths.get(column, 0), text_width(head_font, header.text(column)) + 2 * HEADER_MARGIN)
    except Exception:
        pass
    wanted = {}
    for column in columns:
        width = widths.get(column)
        if width is None:
            continue
        wanted[column] = width  # (its whole content: what it is given first once there is room, share_columns)
        cap = most[column] if isinstance(most, (list, tuple)) and column < len(most) else most
        if isinstance(cap, (int, float)) and not isinstance(cap, bool):
            width = min(width, int(cap))
        widths[column] = width
        try:
            view.setColumnWidth(column, width)
        except Exception:
            pass
    note_wants(view, wanted, dict((column, widths[column]) for column in wanted))
    center_headers(view)
    share_columns(view, after_fit=True)
    return widths


TABLE_FIT_PROP = "freelabTableFit"  # the last fit_rows of a list: its columns and widths, as JSON


FIT_SETTLE_MS = 300  # a list fitted again this long after its filling, once its window is shown
FIT_SETTLE_TRIES = 20  # and looked at this many times for that (a window built before it is shown)


def remember_fit(view, columns, most, settle=True):
    """The list's fit (fit_rows) kept on it, to fit it again as it was (refit); settle: once more after
    its window is shown (settle_fit)."""
    try:
        view.setProperty(TABLE_FIT_PROP, u"%s" % json.dumps(
            {"columns": [int(c) for c in columns], "most": list(most) if isinstance(most, (list, tuple)) else most}))
    except Exception:
        return
    if settle:
        settle_fit(view)


def refit(view):
    """The list fitted again as it was last (fit_rows), its stretch column given the rest again; False
    when it was never fitted. Called from safe points only: after a filling (settle_fit's timer) and
    from the theme hook (retheme_window), never from an event filter."""
    try:
        kept = view.property(TABLE_FIT_PROP)
        if kept is None:
            return False
        kept = json.loads(u"%s" % kept)
    except Exception:
        return False
    fit_rows(view, kept["columns"], most=kept["most"], settle=False)  # (its columns shared out again too)
    return True


def settle_fit(view):
    """The list fitted again (refit) once its window is shown: Qt gives a list built before its window
    is shown its window's font only then. A plain timer, parented to the list and held in sys, looks
    every FIT_SETTLE_MS (at most FIT_SETTLE_TRIES times) and fits it once it is visible. No event filter:
    Python run inside Qt's polishing of a window being shown is where PythonQt crashes FontLab (Kerning
    Check, 2026-11-16, with a filter on font and style changes)."""
    QtCore = _qt()[0]
    modules, name, own = sys.modules, __name__, refit
    try:
        timer = QtCore.QTimer(view)
        timer.setSingleShot(True)
        timer.setInterval(FIT_SETTLE_MS)
    except Exception:
        return None
    tries = [0]
    held = getattr(sys, "_freelab_table_fills", None)
    if held is None:
        held = sys._freelab_table_fills = []

    def settle():  # (no globals below: a reload empties them)
        try:
            tries[0] += 1
            if _property(view, "visible"):
                (getattr(modules.get(name), "refit", None) or own)(view)
            elif tries[0] < FIT_SETTLE_TRIES:
                timer.start()
                return
        except Exception:
            pass  # a slot must not raise
        try:  # (done: let go, once Qt has finished with it)
            held.remove(timer)
        except Exception:
            pass

    try:
        timer.connect("timeout()", settle)
        timer.start()
    except Exception:
        return None
    held.append(timer)
    del held[:-TABLE_FILLS_KEPT]
    return timer


def align_numbers(view, columns):
    """The columns of numbers right-aligned in every row of a tree widget (Font Compare's kerning values
    sat at the left, unlike every other list's numbers); their headers centered, as every header is."""
    QtCore = _qt()[0]
    right = int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    center_headers(view, columns)
    for item, _ in _tree_rows(view):
        for column in columns:
            try:
                item.setTextAlignment(column, right)
            except Exception:
                pass


def fit_list_width(view, most=TEXT_COLUMN_MOST):
    """A list widget at least as wide as its longest row (with room for its scroll bar), at most most
    pixels: Proof's pages list scrolled sideways for 2 pixels."""
    try:
        frame = int(_property(view, "frameWidth"))
    except Exception:
        frame = 1
    try:
        bar = int(view.verticalScrollBar().sizeHint.width()) if not callable(view.verticalScrollBar().sizeHint) \
            else int(view.verticalScrollBar().sizeHint().width())
    except Exception:
        bar = 12
    try:
        needed = int(view.sizeHintForColumn(0)) + 2 * frame + bar + 2
        view.setMinimumWidth(min(needed, int(most)))
        return min(needed, int(most))
    except Exception:
        return None


def b(value):
    """A value in bold, in a status line."""
    return u"<b>%s</b>" % html(value)


def grouped(number):
    """A whole number with its thousands set apart by commas: 13,932 (owner's image 231)."""
    try:
        return u"{:,}".format(int(number))
    except Exception:
        return u"%s" % number


def counted(number, one, many=None):
    """"1 pair", "2 pairs", "13,932 glyphs": a count (thousands set apart, grouped) with its noun in the
    right number."""
    return u"%s %s" % (grouped(number), one if number == 1 else (many or one + u"s"))


def font_named(name, master=None, masters=1):
    """The start of a window's top line, the same in every tool (owner's images 223 and 238 asked what
    decided "(1 master)"): the font's name in bold, then its master's, then how many masters it has only
    when it has more than one. "<b>Cardo</b>, master <b>Bold</b> (of <b>3 masters</b>)"."""
    text = b(name)
    if master:
        text += u", master %s" % b(master)
    try:
        if int(masters) > 1:
            text += u" (of %s)" % b(counted(int(masters), u"master"))
    except Exception:
        pass
    return text


def counted_suffix(spin, one, many=None):
    """A spin box's word kept in step with its number: u" unit" at 1, u" units" otherwise (many: the
    plural, when it is not one with an s). Set now, and again at every change of the value. Returns
    the slot, which sys holds too: PythonQt drops a slot no Python object holds, and a list of this
    module would go with it at a reinstall, while its windows stay open."""
    texts = (u" %s" % one, u" %s" % (many or one + u"s"))

    def follow(*args):  # (no globals below: a reload empties them)
        try:
            value = spin.value
            if callable(value):
                value = value()
            spin.setSuffix(texts[0] if value == 1 else texts[1])
        except Exception:
            pass  # a signal's handler must not raise

    follow()
    try:
        double = bool(spin.inherits("QDoubleSpinBox"))
    except Exception:
        double = False
    try:
        spin.connect("valueChanged(double)" if double else "valueChanged(int)", follow)
    except Exception:
        pass
    held = getattr(sys, "_freelab_suffix_slots", None)
    if held is None:
        held = sys._freelab_suffix_slots = []
    held.append(follow)
    del held[:-256]  # (the slots of windows long closed)
    return follow


def i(name):
    """A button's or a setting's name in italics, in a status line."""
    return u"<i>%s</i>" % html(name)


def rich(label):
    """The label shows rich text (bold values, italic names)."""
    QtCore, QtGui = _qt()
    try:
        label.setTextFormat(QtCore.Qt.RichText)
    except Exception:
        pass
    return label


SENTENCE_END = re.compile(u"([.!?]|\N{HORIZONTAL ELLIPSIS})((?:</[bi]>)?)\\s+(?=[A-Z<(\u00c0-\u024f])")


ONE_LINE = [NO_FONT_LINE]  # the only sentences kept on one line, across the suite (the owner's images 191, 278, 280)


def one_line(text):
    """text's sentences kept on one line by sentences() and status_label (a tool's own no-font line:
    Proof's, Font Builder's); returns text."""
    text = u"%s" % text
    if text not in ONE_LINE:
        ONE_LINE.append(text)
    return text
_JOINED = u"\N{NO-BREAK SPACE}⁠"  # (stands for the space between them while the others are split)


def _split_sentences(text, breaks):
    text = u"%s" % text
    for line in ONE_LINE:
        text = text.replace(line, line.replace(u". ", u"." + _JOINED))
    text = SENTENCE_END.sub(lambda m: m.group(1) + m.group(2) + breaks, text)
    return text.replace(u"." + _JOINED, u". ")


def sentences(text):
    """Rich text with a line per sentence (a status line's sentences each start a line), but those of
    NO_FONT_LINE and the lines given one_line, which share one."""
    return _split_sentences(text, u"<br>").replace(u"\n", u"<br>")


HEAD_BREAK = u"<br><br>"  # the blank line under the font's sentence in a one-label top line (head_join)


def head_join(font, rest):
    """A one-label top line: the font's sentence (font_named's, with its period), a blank line, then what the
    tool found (rest), as the windows whose top line and status lines are separate labels have it (window_head,
    owner's images 346, 355, 358); the font's alone when rest says nothing."""
    font, rest = (u"%s" % (font or u"")).strip(), (u"%s" % (rest or u"")).strip()
    if not font or not rest:
        return font or rest
    return font + HEAD_BREAK + rest


def status_label(text=u"", plain=False):
    """A dialog's top line: rich text (or plain), wrapped, a line per sentence (its setText splits them).
    Hidden while it says nothing: an empty one still took a line, a gap over the fields (owner's images
    197 to 204)."""
    QtCore, QtGui = _qt()

    class StatusLabel(QtGui.QLabel):
        def setText(self, text):
            QtGui.QLabel.setText(self, _split_sentences(text, u"\n") if plain else sentences(text))
            try:  # (kept hidden while the window's bar takes its place: busy_start)
                self.setHidden(bool(self.property(BUSY_LINE_PROP)) or not (u"%s" % text).strip())
            except Exception:
                pass

    label = StatusLabel()
    if not plain:
        rich(label)
    label.setWordWrap(True)
    label.setText(text)
    return label


DIALOG_SIZE = 1000  # pixels: each FreeLab window opens this wide and tall, or as near as the screen allows


SCROLL_SHEET = (u"QScrollBar:vertical { background: transparent; width: 12px; margin: 0; } "
                u"QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; } "
                u"QScrollBar::handle { background: rgba(128, 128, 128, 110); border-radius: 4px; margin: 2px; } "
                u"QScrollBar::handle:vertical { min-height: 24px; } "
                u"QScrollBar::handle:horizontal { min-width: 24px; } "
                u"QScrollBar::handle:hover { background: rgba(128, 128, 128, 170); } "
                u"QScrollBar::handle:pressed { background: rgba(128, 128, 128, 220); } "
                u"QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; border: none; background: none; } "
                u"QScrollBar::add-page, QScrollBar::sub-page { background: none; }")
# FreeLab's scroll bars: flat, a mid gray at the strength of the lists' lines, over either palette.
# Windows' own style draws its scroll bars light whatever the palette: left alone by dark mode (in
# the lists whose pictures it must not map) its thumb came out hollow, and mapped it flickered as the
# pointer passed over it (a hover repaints the bar alone).


TAB_SHEET = (u"QTabBar::tab { background: transparent; color: rgba(128, 128, 128, 255); border: none; "
             u"border-bottom: 2px solid transparent; padding: 5px 12px 4px 12px; margin-right: 2px; } "
             u"QTabBar::tab:selected { color: palette(window-text); border-bottom: 2px solid palette(highlight); } "
             u"QTabBar::tab:hover:!selected { color: palette(window-text); } "
             u"QTabBar::tab:disabled { color: rgba(128, 128, 128, 110); }")
# FreeLab's tab bars: flat, the chosen tab underlined in the highlight color, the others in a mid gray,
# over either palette, and left alone by dark mode. Windows' own style drew the chosen tab light
# whatever the palette: mapped, its text came out garbled, and the edges changed with the tab chosen.
TAB_SHEET_LIGHT = TAB_SHEET.replace(u"QTabBar::tab { background: transparent; color: rgba(128, 128, 128, 255);",
                                    u"QTabBar::tab { background: transparent; color: palette(window-text);")
# On a light window the mid gray read as grayed out (owner's image 352): every tab there takes the text's
# color, the chosen one told by its underline alone.


def tab_sheet(bar):
    """The tab bar's sheet for its window's palette: TAB_SHEET_LIGHT on a light one, else TAB_SHEET."""
    QtGui = _qt()[1]
    try:
        light = bar.palette.color(QtGui.QPalette.Window).lightness() > 128
    except Exception:
        try:
            light = bar.palette().color(QtGui.QPalette.Window).lightness() > 128
        except Exception:
            light = False
    return TAB_SHEET_LIGHT if light else TAB_SHEET


LIGHT_FIELD_PROP = "freelabLightField"  # on a field whose grayed background light_fields set
LIGHT_FIELD_DARKER = 107  # percent: a grayed field's background on a light window, darker than the window's


def light_field_color(window_color, QtGui):
    """The background of a grayed field on a light window: a shade darker than the window's. Windows' own style
    fills a grayed field with the window's color, its frame a faint line: Feature Code's empty field beside
    Glyphs and its spin boxes vanished in light mode (owner's image 366, live 2026-11-19)."""
    return QtGui.QColor(window_color).darker(LIGHT_FIELD_DARKER)


def light_fields(dialog):
    """Each field and spin box of a light window drawn, grayed, on light_field_color; on a dark window (dark
    mode switched on) the background its palette gives it back, dark mode's as before. Never raises."""
    QtGui = _qt()[1]
    try:
        app = QtGui.QApplication.instance()
        window = _property(dialog, "palette").color(QtGui.QPalette.Window)
        light = window.lightness() > 128
        want = light_field_color(window, QtGui) if light else app.palette().color(QtGui.QPalette.Disabled,
                                                                                   QtGui.QPalette.Base)
        for kind in ("QLineEdit", "QAbstractSpinBox"):
            for field in dialog.findChildren(getattr(QtGui, kind)):
                try:
                    if kind == "QLineEdit" and field.parentWidget() is not None and (
                            field.parentWidget().inherits("QAbstractSpinBox") or field.parentWidget().inherits("QComboBox")):
                        continue  # (drawn by its box)
                    if not light and not field.property(LIGHT_FIELD_PROP):
                        continue  # (never set here: dark mode's own)
                    palette = _property(field, "palette")
                    if palette.color(QtGui.QPalette.Disabled, QtGui.QPalette.Base) != want:
                        palette = QtGui.QPalette(palette)
                        palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Base, want)
                        field.setPalette(palette)
                    field.setProperty(LIGHT_FIELD_PROP, True)  # (kept: in dark, it follows the palette's)
                except Exception:
                    continue
    except Exception:
        pass


def flat_scroll_bars(dialog):
    """SCROLL_SHEET on each scroll bar of a dialog's lists and text views, on the bars themselves: a
    stylesheet on the dialog would reach its combo boxes and fields, which dark mode leaves to the
    palette only when no stylesheet lies on them or around them."""
    QtCore, QtGui = _qt()
    try:
        for view in dialog.findChildren(QtGui.QAbstractScrollArea):
            for bar in (view.verticalScrollBar(), view.horizontalScrollBar()):
                if bar is not None and (_property(bar, "styleSheet") or u"") != SCROLL_SHEET:
                    bar.setStyleSheet(SCROLL_SHEET)
    except Exception:
        pass
    light_fields(dialog)  # (and its grayed fields seen on a light window)
    try:  # and its tab bars (TAB_SHEET)
        for bar in dialog.findChildren(QtGui.QTabBar):
            sheet = tab_sheet(bar)
            if (_property(bar, "styleSheet") or u"") != sheet:
                bar.setStyleSheet(sheet)
                bar.setProperty(LEAVE_ALONE_PROP, True)
                bar.setDrawBase(False)
    except Exception:
        pass


SCREEN_MARGIN = (40, 60)  # pixels kept free across a screen's free area beside a window, and down (its title bar)
SMALL_SCREEN = (1000, 700)  # pixels: on a screen whose free area is narrower or lower, windows scroll (window_layout)
WINDOW_BODY_PROP = "freelabWindowBody"  # on the scroll area holding a window's content, and on that content


def screen_area(widget=None):
    """The free part (left, top, right, bottom) of the screen FontLab's main window is on (FreeLab's
    windows open over it), else of the widget's screen; None where Qt cannot tell."""
    QtGui = _qt()[1]
    for source in (AutoKerningDialog.main_window(), widget):
        if source is None:
            continue
        try:
            rect = QtGui.QApplication.desktop().availableGeometry(source)
            return (int(rect.left()), int(rect.top()), int(rect.right()) + 1, int(rect.bottom()) + 1)
        except Exception:
            continue
    return None


def size_dialog(dialog, width=DIALOG_SIZE, height=DIALOG_SIZE):
    """1000 by 1000 pixels (or the size given), or the most the free area of FontLab's screen allows
    (screen_area). Its lists then widen it to show their columns whole (widen_window)."""
    area = screen_area(dialog)
    if area is not None:
        width = min(width, area[2] - area[0] - SCREEN_MARGIN[0])
        height = min(height, area[3] - area[1] - SCREEN_MARGIN[1])
    dialog.resize(max(1, int(width)), max(1, int(height)))


def small_screen(area):
    """Whether a screen's free area (screen_area) is too small for FreeLab's windows as laid out."""
    return area is not None and (area[2] - area[0] < SMALL_SCREEN[0] or area[3] - area[1] < SMALL_SCREEN[1])


def window_layout(dialog, scroll=None):
    """The layout a tool fills its window with. On a small screen (small_screen: a 480p or a 720p
    display), the window's content sits in a scroll area, which scrolls once the window is smaller than
    its content: else Qt grows a window to its layout's least size as it shows it, past the screen's
    edges, its bottom buttons out of reach, and nothing scrolls. scroll: True or False to choose."""
    QtGui = _qt()[1]
    if scroll is None:
        scroll = small_screen(screen_area(dialog))
    if not scroll:
        return QtGui.QVBoxLayout(dialog)
    outer = QtGui.QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    area = QtGui.QScrollArea(dialog)
    area.setWidgetResizable(True)
    area.setFrameShape(QtGui.QFrame.NoFrame)
    body = QtGui.QWidget(area)  # (parented from the start: PythonQt deletes a parentless one when it likes)
    for widget in (area, body):
        widget.setProperty(WINDOW_BODY_PROP, True)  # (a click on it is a click beside the lists: blank_press)
    layout = QtGui.QVBoxLayout(body)
    area.setWidget(body)
    outer.addWidget(area)
    return layout


def widen_window(view):
    """A tool's window made wider when a list just fitted cannot show its columns at their fitted widths
    (note_wants' fits) without scrolling sideways: by what it lacks, at most to the free area of
    FontLab's screen (screen_area, SCREEN_MARGIN kept), around its center. Never narrower, and never
    once the owner gave a window its size by hand (this window since it opened, or every window this
    session: note_size), nor while it is maximized, minimized, or not shown. The pixels it grew by."""
    try:
        window = view.window()
        if not (_property(window, "visible") and _property(view, "visible")):
            return 0
        if _property(window, "maximized") or _property(window, "minimized"):
            return 0
        owner = window_owner(window)
        if owner is None or not _same(owner.dialog, window) or _windows().get("size") is not None:
            return 0
        size, opened = _size(window), getattr(owner, "opened_size", None)
        if opened is not None and (abs(size[0] - opened[0]) > 2 or abs(size[1] - opened[1]) > 2):
            return 0  # (resized by hand: the owner's size stays)
        count = int(_property(view, "columnCount"))
        fits = _wants_of(view).get("fits") or []
        total = sum(fits[c] if c < len(fits) and fits[c] is not None else int(view.columnWidth(c))
                    for c in range(count) if not view.isColumnHidden(c))
        lack = total - int(_property(view.viewport(), "width"))
        if lack <= 0:
            return 0
        area, frame = screen_area(window), _free_area(window)[1]
        most = area[2] - area[0] - SCREEN_MARGIN[0] - frame[0] if area is not None else size[0] + lack
        width = min(size[0] + lack, most)
        if width <= size[0]:
            return 0
        x, y = centered_place(_xy(_property(window, "pos")), size, (width, size[1]), area, frame)
        window.resize(width, size[1])
        window.move(x, y)
        if opened is not None:
            owner.opened_size = (width, size[1])  # (FreeLab's doing, not a size given by hand)
        return width - size[0]
    except Exception:
        return 0


def room_below(window):
    """Pixels between a window's bottom edge (its frame's) and the bottom of its screen's free area."""
    QtCore, QtGui = _qt()
    try:
        area = QtGui.QApplication.desktop().availableGeometry(window)
        return max(0, area.bottom() - _property(window, "frameGeometry").bottom())
    except Exception:
        return 0


SECTION_LINES = 1.7  # a section heading row's height, in lines


def section_row(item, tree):
    """A list's row heading a section: bold, a little taller, its text level with its arrow and check
    box (set at the bottom of a taller row, it sat below them, on the next row's line)."""
    QtCore, QtGui = _qt()
    try:
        bold = QtGui.QFont(tree.font)
        bold.setBold(True)
        item.setFont(0, bold)
        line = QtGui.QFontMetrics(bold).height()
        item.setSizeHint(0, QtCore.QSize(0, int(line * SECTION_LINES)))
        item.setTextAlignment(0, int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter))
    except Exception:
        pass
    return item


LOG_LINES = 4  # the log's height, in lines
LOG_KEPT = 200  # entries kept
LOG_COLORS = {"warning": ((224, 160, 40), (150, 95, 0)), "error": ((240, 96, 86), (190, 30, 20)),
              "done": ((120, 200, 120), (30, 120, 40))}  # (on a dark background, on a light one)


LOG_HEIGHT = []  # the log's height as last dragged, kept for the next window (pixels)
LOG_LEAST_LINES = 2  # the log's height at least, in lines, however little room the lists have
COMFORT_ROWS = 4  # a list showing less than this many rows takes room from the log first (Log.yield_room)


def list_shortfall(view):
    """The pixels a list lacks to show COMFORT_ROWS rows under its header (0 when it has them, or cannot
    tell)."""
    try:
        row = int(view.sizeHintForRow(0))
        if row <= 0:
            row = int(line_height_of(view)) + 6
        head = 0
        header = view.header() if hasattr(view, "header") else None
        if header is not None and _property(header, "visible"):
            head = int(_property(header, "height"))
        frame = 2 * int(_property(view, "frameWidth") or 0)
        return max(0, head + COMFORT_ROWS * row + frame - int(_property(view, "height")))
    except Exception:
        return 0


def line_height_of(widget):
    """A widget's font's line height in pixels."""
    QtGui = _qt()[1]
    return QtGui.QFontMetrics(_property(widget, "font")).lineSpacing()


def log_height(now, wanted, least, short, grown):
    """The log's height for the room the window gives it (Log.yield_room): now less what the lists lack
    (short), never under least; or, nothing lacking and the window grown taller (grown, pixels), back
    toward wanted by as much; else as it is."""
    if short > 0:
        return max(least, min(now, now - short)) if now > least else now
    if grown > 0 and now < wanted:
        return min(wanted, now + grown)
    return now


class Log(object):
    """A few lines under a dialog's list: what each action did, done in green, warnings in amber,
    errors in red, newest first. The dialog's top line keeps to what the list shows. Its bottom edge
    drags to make it taller (widget: the log and that edge, to put in a layout)."""

    def __init__(self):
        QtCore, QtGui = _qt()
        view = self.view = QtGui.QTextBrowser()  # (a text view whose links can be clicked: glyphs named in a line)
        view.setReadOnly(True)
        view.setOpenLinks(False)
        view.setOpenExternalLinks(False)
        self.link_handler = None
        self.source = None  # set by follow()
        self.link_slot = lambda url: self.link_clicked(url)
        view.connect("anchorClicked(QUrl)", self.link_slot)
        # Left to the palette: dark mode's mapping of text views left its scroll bar light
        view.setProperty(LEAVE_ALONE_PROP, True)
        self.line = QtGui.QFontMetrics(view.font).lineSpacing()
        view.setFixedHeight(LOG_HEIGHT[0] if LOG_HEIGHT else int(self.line * LOG_LINES + 12))
        view.setWhatsThis(u"What this window did, newest first: done in green, warnings in amber, errors in red. "
                          u"Drag its bottom edge to make it taller: the window's bottom edge moves with it.")
        self.entries, self.lines = [], []  # (lines: (time, text, level) as given; entries: as shown)
        self.widget = QtGui.QWidget()
        box = QtGui.QVBoxLayout(self.widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(view)
        grip = self.grip = QtGui.QFrame()
        grip.setFixedHeight(6)
        grip.setCursor(QtCore.Qt.SizeVerCursor)
        grip.setToolTip(u"Drag to make the log and the window taller or shorter.")
        box.addWidget(grip)
        log = self

        class Drag(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == 2:  # MouseButtonPress
                        window = log.view.window()
                        log.start = (event.globalPos().y(), _property(log.view, "height"), window,
                                     _property(window, "height"), room_below(window))
                        return True
                    if kind == 5 and getattr(log, "start", None):  # MouseMove, the button held
                        y, height, window, window_height, room = log.start
                        wanted = max(int(log.line * 2 + 12), min(int(log.line * 40), height + event.globalPos().y() - y))
                        # The window's bottom edge moves with the log's, as far as the screen goes (the
                        # list keeps its height); past it, the log takes the list's room.
                        grown = window_height + min(wanted - height, room)
                        before = _property(window, "height")
                        if wanted < _property(log.view, "height"):
                            log.view.setFixedHeight(wanted)
                            window.resize(_property(window, "width"), grown)
                        else:
                            window.resize(_property(window, "width"), grown)
                            log.view.setFixedHeight(wanted)
                        grip_resized(window, before)  # (the grip's doing, not a size given by hand)
                        del LOG_HEIGHT[:]
                        LOG_HEIGHT.append(wanted)
                        return True
                    if kind == 3:  # MouseButtonRelease
                        log.start = None
                        return True
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.start = None
        self.drag = Drag(grip)  # (its parent the grip: Qt deletes it with the grip, never PythonQt at random)
        grip.installEventFilter(self.drag)

    def wanted_height(self):
        """The log's height when the window has room: as last dragged (LOG_HEIGHT), else LOG_LINES lines."""
        return LOG_HEIGHT[0] if LOG_HEIGHT else int(self.line * LOG_LINES + 12)

    def yield_room(self, window):
        """The log gives up room first (owner's image 340: its dragged height kept while the lists above it
        were squeezed to a row): while a list of the window shows less than COMFORT_ROWS rows' room, the log
        is made shorter by what they lack, down to LOG_LEAST_LINES lines; as the window grows taller, the log
        takes its height back first. Called as the window is resized (filter_event). Never raises."""
        if getattr(self, "start", None):
            return  # (its edge being dragged: the height asked for)
        QtGui = _qt()[1]
        try:
            height = int(_property(window, "height"))
            grown = height - getattr(self, "window_height", height)
            self.window_height = height
            now = int(_property(self.view, "height"))
            short = 0
            for view in window.findChildren(QtGui.QAbstractItemView):
                # (a dropdown's list is a window of its own; a header is its list's)
                if (view.window() is window or view.window() == window) and _property(view, "visible") \
                        and not view.inherits("QHeaderView"):
                    short += list_shortfall(view)
            target = log_height(now, self.wanted_height(), int(self.line * LOG_LEAST_LINES + 12), short, grown)
            if target != now:
                self.view.setFixedHeight(target)
        except Exception:
            pass

    def follow(self, source):
        """source() gives (fontlab, package, master) of the font the dialog looks at now. The glyphs its
        lines link to (glyph_links, glyph_name_links) are then drawn as that font draws them, which the
        interface's fonts cannot do for every character (private-use glyphs came out as empty boxes),
        and a link the dialog's handler does not take opens its glyph in a Glyph window."""
        self.source = source

    def pictured(self, text, color):
        """text with each linked glyph the font has drawn from its outlines, in color (r, g, b)."""
        if self.source is None or u'<a href="glyph' not in text:
            return text
        try:
            package, master = self.source()[1:3]
        except Exception:
            return text
        line = self.line

        def swap(match):
            name = glyph_of_link(package, match.group(1))
            picture = glyph_picture(package, master, name, color, line) if name else None
            if picture is None:
                return match.group(0)
            return (u'<a href="%s"><img src="data:image/png;base64,%s" width="%d" height="%d" '
                    u'style="vertical-align: middle"></a>' % ((match.group(1),) + picture))

        return _GLYPH_ANCHOR.sub(swap, text)

    def add(self, text, level="info"):
        """text is rich text already (html(), b(), and i() make its parts)."""
        try:
            stamp = time.strftime("%H:%M")
            self.lines = getattr(self, "lines", [])
            self.lines.insert(0, (stamp, text, level))  # (as given: written again in new colors, restyle)
            del self.lines[LOG_KEPT:]
            self.entries.insert(0, self.rendered(stamp, text, level))
            del self.entries[LOG_KEPT:]
            self.view.setHtml(u"<br>".join(self.entries))
        except Exception:
            pass

    def rendered(self, stamp, text, level):
        """A line as the log shows it, in the colors of now: its glyphs drawn, its level's color."""
        QtGui = _qt()[1]
        color = LOG_COLORS.get(level)
        if color is None:
            ink = self.view.palette.color(QtGui.QPalette.Text)
            text = self.pictured(text, (ink.red(), ink.green(), ink.blue()))
        else:
            base = self.view.palette.color(QtGui.QPalette.Base)
            rgb = color[0] if base.lightness() < 128 else color[1]
            text = self.pictured(text, rgb)
            # links (glyphs to select) in the line's own color, underlined: not the palette's blue
            text = text.replace(u'<a href=', u'<a style="color:#%02x%02x%02x" href=' % (rgb[0], rgb[1], rgb[2]))
            text = u'<span style="color:#%02x%02x%02x">%s</span>' % (rgb[0], rgb[1], rgb[2], text)
        return u"%s&nbsp; %s" % (stamp, text)

    def restyle(self):
        """Every line written again in the colors of now (dark mode switched: retheme_window); the
        lines were colored, and their glyphs drawn, in the colors of when they came."""
        lines = getattr(self, "lines", [])
        if not lines:
            return
        self.entries = [self.rendered(*line) for line in lines]
        try:
            bar = self.view.verticalScrollBar()
            at = int(_property(bar, "value"))  # (a property under PythonQt: a value, not a call)
        except Exception:
            bar = None
        self.view.setHtml(u"<br>".join(self.entries))
        if bar is not None:
            bar.setValue(at)  # (where the reader was)

    def link_clicked(self, url):
        """A link in a line clicked: a tool's (tool_link) opens it in this window's place; any other is
        handed to the dialog's handler (its text: the link's target)."""
        try:
            target = u"%s" % (url.toString() if hasattr(url, "toString") else url)
            if target.startswith(TOOL_LINK):
                title = target[len(TOOL_LINK):].replace(u"%20", u" ")
                if title in FONT_TOOLS and not open_tool(title, self.view.window()):
                    self.add(u"%s is not in <i>Scripts &gt; FreeLab</i>: run <i>Refresh Scripts</i>, or reinstall "
                             u"FreeLab." % b(title), "warning")
                return
            if self.link_handler is not None and self.link_handler(target) is not False:
                return  # (a handler returns False for a link it leaves to the log)
            self.open_linked(target)
        except Exception:
            pass

    def open_linked(self, target):
        """A glyph link no dialog took: its glyph in a new Glyph tab (a list that no longer shows the
        glyph has no row to select)."""
        if self.source is None:
            return
        fontlab, package = self.source()[:2]
        name = glyph_of_link(package, target)
        if not name:
            if linked_glyph_name(target) or linked_code(target) is not None:
                self.add(u"The font does not have that glyph now.", "warning")
            return
        error = show_in_glyph_window(fontlab, u"/%s" % name)
        if error:
            self.add(u"FontLab did not open the glyph: %s" % html(error), "error")

    def clear(self):
        self.entries, self.lines = [], []
        self.view.clear()


# FreeLab's one table layout (table_layout), for every list of rows in every tool, trees and tables
# alike, in either theme and across a switch: the owner's reference is Glyph Compose's and Feature Code's
# lists (2026-11-15), where a list converted later had a header dark mode had mapped (stray light
# separators), gray ticks, rows close to their text, no grid where the theme changed, or columns that
# left half the window empty.
# - Dark mode leaves the whole list alone (LEAVE_ALONE_PROP): everything in it is drawn from the
#   palette, so there is nothing to map; mapped, its header came out with light separators and its
#   grid light (Font Compare, Kerning Classes). The header is the style's own, as Glyph Compose's is.
# - Grid lines halfway between the list's text and its ground, at half strength (a mid gray at 50 %
#   opacity: faint beside the text, in either theme).
# - Each cell's content TABLE_PADDING from its lines (rows with room above and below their text).
# - Check boxes framed in a mid gray, filled with the selection's color and ticked when checked (the
#   style's own nearly vanish on a dark palette).
# - Selected rows in the palette's selection colors (a stylesheet's item rule takes the items'
#   drawing over: without a selected rule, a selected row showed no highlight).
# - The columns fill the list's width: one column (the stretch column) takes what the others leave,
#   Qt's last one unless the tool names another (that one never narrower than its contents: a narrow
#   window scrolls, and it can be dragged as any column).
# The stylesheet holds colors read from the palette: retheme_window writes it again on each switch.
TABLE_PROP = "freelabTable"  # on a list table_layout laid out: its stretch column (-1: Qt's last one)
TABLE_GRID_PROP = "freelabTableGrid"  # False on a list laid out without grid lines
TABLE_SHEET_MARK = u"/* FreeLab table */"
TABLE_SHEET_END = u"/* FreeLab table end */"  # (rules a tool adds after it, Font Check's branch arrows, stay)
TABLE_PADDING = (4, 6)  # pixels between a cell's content and its lines: above and below, and beside
TABLE_GRID_ALPHA = 128  # of 255: the grid lines' strength
CHECK_FRAME = u"rgb(140, 140, 146)"  # an unchecked box's frame: a mid gray, plain on either background
CHECK_MARK_SCALE = 3  # the check mark is drawn this many times the box's size (sharp on a scaled display)
CHECK_SIZE = 13  # pixels: a check box's side when the style does not say


def _view_kind(view):
    """The stylesheet's name for a list's kind: QTableView, QListView, or QTreeView."""
    for kind in ("QTableView", "QListView"):
        try:
            if view.inherits(kind):
                return kind
        except Exception:
            break
    return "QTreeView"


def check_box_sheet(size, mark=None, fill=u"palette(highlight)", frame=CHECK_FRAME, selected_frame=u"white",
                    kind="QTreeView"):
    """Stylesheet rules for a list's check boxes: unchecked, a box framed in a mid gray on the row's own
    background; checked, a box filled with fill (the list's selection color), with the check mark
    (mark: an image file's path; None: filled only). On a selected row (the same color) each box is
    framed in selected_frame (the selected text's color), so it still stands out. size: the style's
    box, frame included (Qt sizes a column for the style's box: a frame drawn around a box of that
    size made it 2 pixels wider, and the cell's text was cut, "Advance heig...")."""
    image = u' image: url("%s");' % mark.replace(u"\\", u"/") if mark else u""
    inner = max(1, size - 2)
    return (u"%s::indicator { width: %dpx; height: %dpx; border: 1px solid %s; border-radius: 2px; "
            u"background: transparent; } "
            u"%s::indicator:checked { border: 1px solid %s; background: %s;%s } "
            u"%s::indicator:indeterminate { background: %s; } "
            u"%s::indicator:selected { border: 1px solid %s; }" % (kind, inner, inner, frame, kind, fill, fill, image,
                                                                 kind, frame, kind, selected_frame))


def check_mark_file(color, size):
    """A check mark in color (r, g, b) for a box of size pixels, drawn larger and saved as a PNG in
    FreeLab's folder of the temporary files (once per color and size): its path, or None."""
    QtCore, QtGui = _qt()
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


def _css(rgb, alpha=None):
    if alpha is None:
        return u"rgb(%d, %d, %d)" % tuple(rgb[:3])
    return u"rgba(%d, %d, %d, %d)" % (tuple(rgb[:3]) + (alpha,))


def table_colors(palette):
    """{"text", "base", "grid", "highlight", "highlighted"}: (r, g, b) of a list's palette, its Active
    group (Qt's light defaults where it cannot be read). The grid lies halfway between the text and the
    ground. Read as Active whatever the window is: the stylesheet holds them as fixed colors, and a
    window behind another at a switch read its Inactive group, whose selection is light gray in the
    Windows style: gray ticks and a gray selection that stayed so once the window was activated (live,
    2026-11-16)."""
    QtGui = _qt()[1]
    defaults = {"Text": (0, 0, 0), "Base": (255, 255, 255), "Highlight": (0, 120, 215), "HighlightedText": (255, 255, 255)}
    active = getattr(QtGui.QPalette, "Active", 0)
    found = {}
    for role, default in defaults.items():
        try:
            found[role] = _rgb(palette.color(active, getattr(QtGui.QPalette, role)))
        except Exception:
            found[role] = default
    text, base = found["Text"], found["Base"]
    return {"text": text, "base": base, "grid": tuple((t + g) // 2 for t, g in zip(text, base)),
            "highlight": found["Highlight"], "highlighted": found["HighlightedText"]}


def table_sheet(colors, kind="QTreeView", grid=True, check_size=CHECK_SIZE, mark=None):
    """The stylesheet of a FreeLab list (table_layout) in colors (table_colors), between its marks."""
    line = _css(colors["grid"], TABLE_GRID_ALPHA)
    # (no focus rectangle: the style framed the clicked cell of the selected row, a faint box around the
    # current column's cell, which serves nothing in lists selected by the row, owner's report 114)
    rules = [TABLE_SHEET_MARK, u"%s { outline: 0; }" % kind]
    if kind == "QTableView":  # (a table draws its grid itself; its cells take only the padding)
        rules.append(u"QTableView { gridline-color: %s; }" % (line if grid else u"transparent"))
        rules.append(u"QTableView::item { padding: %dpx %dpx; }" % TABLE_PADDING)
    else:
        lines = (u" border-right: 1px solid %s; border-bottom: 1px solid %s;" % (line, line)) if grid else u""
        rules.append(u"%s::item { padding: %dpx %dpx;%s }" % ((kind,) + TABLE_PADDING + (lines,)))
    rules.append(u"%s::item:selected { background: %s; color: %s; }" % (kind, _css(colors["highlight"]),
                                                                         _css(colors["highlighted"])))
    rules.append(check_box_sheet(check_size, mark, _css(colors["highlight"]), CHECK_FRAME,
                                 _css(colors["highlighted"]), kind))
    rules.append(TABLE_SHEET_END)
    return u" ".join(rules)


def _without_table_sheet(sheet):
    """A list's stylesheet without the rules table_layout wrote (and what came before them: the
    grid lines of before), keeping those a tool added after them."""
    sheet = u"%s" % (sheet or u"")
    if TABLE_SHEET_END in sheet:
        return sheet.split(TABLE_SHEET_END, 1)[1].strip()
    if TABLE_SHEET_MARK in sheet:
        return u""
    return sheet.strip()


def style_table(view):
    """A FreeLab list's stylesheet (table_sheet) written in the colors of its palette now, the rules a
    tool added after it kept. Called by table_layout, and again by retheme_window on each switch."""
    QtGui = _qt()[1]
    try:
        colors = table_colors(_property(view, "palette"))
    except Exception:
        colors = table_colors(None)
    try:
        size = int(view.style().pixelMetric(QtGui.QStyle.PM_IndicatorWidth))
    except Exception:
        size = CHECK_SIZE
    size = max(11, min(24, size or CHECK_SIZE))
    try:
        mark = check_mark_file(colors["highlighted"], size)
    except Exception:
        mark = None
    try:
        grid = view.property(TABLE_GRID_PROP) is not False
    except Exception:
        grid = True
    try:
        rest = _without_table_sheet(_property(view, "styleSheet"))
    except Exception:
        rest = u""
    sheet = table_sheet(colors, _view_kind(view), grid, size, mark)
    try:
        view.setStyleSheet(u"")  # (polished again: the palette's colors read anew)
        view.setStyleSheet(sheet + (u" " + rest if rest else u""))
    except Exception:
        pass
    return sheet


def table_stretch(view):
    """The column a FreeLab list stretches (table_layout), or None (Qt's last one, or none)."""
    try:
        stretch = view.property(TABLE_PROP)
        stretch = int(stretch) if stretch is not None else -1
    except Exception:
        return None
    return stretch if stretch >= 0 else None


def _header_of(view):
    try:
        return view.horizontalHeader() if view.inherits("QTableView") else view.header()
    except Exception:
        return None


TABLE_WANTS_PROP = "freelabTableWants"  # what each column wants and was fitted to (note_wants), as JSON
TABLE_SHARING_PROP = "freelabTableSharing"  # True while share_columns sets the widths (the header's signals are its own)
TABLE_FILL_PROP = "freelabTableFill"  # the key of the list's fill watch (sys._freelab_table_fills)
RESIZE_EVENT = 14  # QEvent::Resize
TABLE_FILLS_KEPT = 256  # watches held (those of windows long closed go first)
LEAST_COLUMN = 24  # pixels: no column is narrowed below this (or its header's text) to fit a list's width
INTERACTIVE = 0  # QHeaderView::Interactive: a column the owner can drag (a tool's other modes are its own)


def _wants_of(view):
    try:
        kept = view.property(TABLE_WANTS_PROP)
        found = json.loads(u"%s" % kept) if kept is not None else {}
        return found if isinstance(found, dict) else {}
    except Exception:
        return {}


def note_wants(view, wants=None, fits=None):
    """What a list's columns want (share_columns): wants {column: pixels}, its whole content (a long
    glyph list's whole length too); fits {column: pixels}, the width a fit gave it (capped: what
    widen_window makes room for). None: every column's width now, for both. A column not given keeps
    what it had. Kept on the list as JSON (TABLE_WANTS_PROP)."""
    try:
        count = int(_property(view, "columnCount"))
        if wants is None:
            wants = dict((column, int(view.columnWidth(column))) for column in range(count))
    except Exception:
        return
    fits = wants if fits is None else fits
    kept = _wants_of(view)
    merged = {}
    for key, given in (("wants", wants), ("fits", fits)):
        old = list(kept.get(key) or [])
        merged[key] = [int(given[c]) if c in given and given[c] is not None else (old[c] if c < len(old) else None)
                       for c in range(count)]
    try:
        view.setProperty(TABLE_WANTS_PROP, u"%s" % json.dumps(merged))
    except Exception:
        pass


def _spread(amount, weights):
    """amount in whole pixels, split in proportion to weights (the largest remainders take the odd
    pixels, the first column first on a tie); nothing for no weight."""
    total = sum(weights)
    if amount <= 0 or total <= 0:
        return [0] * len(weights)
    exact = [amount * float(w) / total for w in weights]
    parts = [int(math.floor(e)) for e in exact]
    for index in sorted(range(len(weights)), key=lambda i: (parts[i] - exact[i], i))[:amount - sum(parts)]:
        parts[index] += 1
    return parts


def _level_down(widths, wants, columns, need):
    """need pixels taken from the columns' room above wants (what they want, or their least), the
    roomiest first: brought down to the next roomiest, then both together, and so on. What is still
    needed."""
    while need > 0:
        rooms = sorted(((widths[c] - wants[c], c) for c in columns if widths[c] - wants[c] > 0),
                       key=lambda room: (-room[0], room[1]))
        if not rooms:
            break
        top = rooms[0][0]
        level = [c for room, c in rooms if room == top]
        below = max([room for room, _ in rooms if room < top] or [0])
        take = min(need, (top - below) * len(level))
        for column, part in zip(level, _spread(take, [1] * len(level))):
            widths[column] -= part
        need -= take
    return need


def _fill_up(widths, wants, columns, give):
    """give pixels to the columns cut short of what they want: each that the room left can show whole,
    the one lacking least first (a column nearly whole is never left a few pixels short); then the rest
    to those still cut (a long note, a glyph list), in proportion to what they lack. What is left."""
    for lack, column in sorted((wants[c] - widths[c], c) for c in columns if wants[c] > widths[c]):
        if lack <= give:
            widths[column] += lack
            give -= lack
    still = [c for c in columns if wants[c] > widths[c]]
    if give > 0 and still:
        lacks = [wants[c] - widths[c] for c in still]
        part = min(give, sum(lacks))
        for column, share in zip(still, _spread(part, lacks)):
            widths[column] += share
        give -= part
    return give


def share_widths(widths, wants, leasts, room, held=None, stretch=None):
    """New widths (pixels, None for a hidden column) for a list's columns, so that together they fill
    room exactly: never a gap at the list's right (owner's report 142), and no sideways scrolling as
    long as no column must go below its least (leasts) for it.
    Narrower: each column's spare room first (its width past what it wants, wants), the roomiest first;
    after a column was dragged (held, kept as dragged), then its neighbor (the next column, or the one
    before for the last); then the column with the most above its least, brought down to the next, and
    so on (in proportion, Font Check's short "+N" counts were cut to "+..." beside a long list of
    languages, live 2026-11-17).
    Wider: the columns cut short first (_fill_up: made whole, the one lacking least first, then the rest
    to those still cut, in proportion); once none is cut, the stretch column takes the rest (a tool's
    pair pictures or names), or every column in proportion to its width when none is named."""
    new = list(widths)
    shown = [c for c in range(len(new)) if new[c] is not None]
    others = [c for c in shown if c != held]
    if not others:
        return new
    wants = [new[c] if wants[c] is None else wants[c] for c in range(len(new))]
    delta = int(room) - sum(new[c] for c in shown)
    if delta > 0:
        give = _fill_up(new, wants, others, delta)
        if give > 0:
            if stretch in others:
                new[stretch] += give
            else:
                for column, part in zip(others, _spread(give, [max(1, new[c]) for c in others])):
                    new[column] += part
    elif delta < 0:
        need = _level_down(new, wants, others, -delta)
        if need > 0 and held is not None:
            after = [c for c in others if c > held]
            before = [c for c in others if c < held]
            neighbor = min(after) if after else (max(before) if before else None)
            if neighbor is not None:
                take = min(need, max(0, new[neighbor] - leasts[neighbor]))
                new[neighbor] -= take
                need -= take
        if need > 0:  # (the widest above its least first: a short count or name stays whole the longest)
            _level_down(new, leasts, others, need)
    return new


def _header_text(view, column):
    try:
        return u"%s" % view.headerItem().text(column)  # (a tree widget's)
    except Exception:
        pass
    try:
        QtCore = _qt()[0]
        return u"%s" % (view.model().headerData(column, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole) or u"")
    except Exception:
        return u""


OWN_COLUMNS_PROP = "freelab_own_columns"  # on a list whose tool sizes its columns itself (Font Check's right-hand lists)


def _sharing_left_to_tool(header, count, view=None):
    """Whether a list's columns are left to Qt or its tool: the tool says so (OWN_COLUMNS_PROP), Qt's own
    last-section stretch is asked for again, or a column is in another mode than Interactive (Font
    Check's own Stretch and ResizeToContents)."""
    try:
        if view is not None and view.property(OWN_COLUMNS_PROP):
            return True
    except Exception:
        pass
    try:
        if _property(header, "stretchLastSection"):
            return True
    except Exception:
        pass
    try:
        return any(int(header.sectionResizeMode(column)) != INTERACTIVE for column in range(count))
    except Exception:
        return False


def column_needs(view, widths):
    """(wants, leasts) for a list's columns (share_columns): what each wants (note_wants, else Qt's
    measure of its content, at least its header's text) and the least it may be given (its header's
    text, at least LEAST_COLUMN pixels, at most what it wants); None for a hidden column's want."""
    QtGui = _qt()[1]
    header = _header_of(view)
    kept = _wants_of(view).get("wants") or []
    try:
        metrics = QtGui.QFontMetrics(_property(header, "font"))
    except Exception:
        metrics = None
    wants, leasts = [], []
    for column in range(len(widths)):
        want = kept[column] if column < len(kept) else None
        if want is None and widths[column] is not None:
            try:
                want = int(view.sizeHintForColumn(column)) or widths[column]
            except Exception:
                want = widths[column]
        heading = 0
        if metrics is not None:
            try:
                heading = int(metrics.width(_header_text(view, column))) + 2 * HEADER_MARGIN
            except Exception:
                heading = 0
        want = max(want, heading) if want is not None else None
        wants.append(want)
        leasts.append(min(want or 0, max(LEAST_COLUMN, heading)))
    return wants, leasts


def drag_limit(widths, leasts, column, room):
    """The widest a column being dragged may be made (owner's image 214: a column dragged past the
    list's frame pushed every column after it out of sight): the room the list shows, less the columns
    before it as they are and those after it at their least (share_columns brings them down to it once
    the drag ends). widths: the columns' widths now, None for a hidden one. Never under MIN_SECTION."""
    taken = 0
    for other, width in enumerate(widths):
        if other == column or width is None:
            continue
        taken += width if other < column else max(MIN_SECTION, min(width, leasts[other] if other < len(leasts) else width))
    return max(MIN_SECTION, int(room) - taken)


def drag_limit_of(view, column):
    """drag_limit for a list's column now; None when it cannot be read."""
    try:
        count = int(_property(view, "columnCount"))
        widths = [None if view.isColumnHidden(c) else int(view.columnWidth(c)) for c in range(count)]
        room = int(_property(view.viewport(), "width"))
    except Exception:
        return None
    if room <= 0:
        return None
    return drag_limit(widths, column_needs(view, widths)[1], column, room)


def share_columns(view, held=None, after_fit=False):
    """A FreeLab list's columns sharing its width (share_widths). What each wants is its whole content
    (note_wants, from the last fit; or the width the owner dragged it to); the least each may be given is
    its header's text (at least LEAST_COLUMN pixels), and the stretch column's whole content (its
    pictures are never cut). Called when the list is resized (watch_table, on the next turn of the event
    loop), when a column is dragged (held: that column, kept as dragged), and after each fit of the list
    (after_fit: its window then widens to show it whole, widen_window). The widths set, or None (left to
    Qt or the tool)."""
    QtGui = _qt()[1]
    header = _header_of(view)
    if header is None:
        return None
    try:
        count = int(_property(view, "columnCount"))
        if not count or _sharing_left_to_tool(header, count, view):
            return None
        widths = [None if view.isColumnHidden(c) else int(view.columnWidth(c)) for c in range(count)]
        room = int(_property(view.viewport(), "width"))
    except Exception:
        return None
    if room <= 0:
        return None  # (not laid out yet: its first resize shares it out)
    empty_bars(view)
    if view.property(TABLE_DRAG_PROP):
        return None  # (a column being dragged: Qt keeps the last one at the edge until it is let go)
    wants, leasts = column_needs(view, widths)
    stretch = table_stretch(view)
    if stretch is not None and stretch < count and wants[stretch] is not None:
        leasts[stretch] = wants[stretch]  # (its pair pictures or names never cut: the list scrolls first)
    new = share_widths(widths, wants, leasts, room, held, stretch)
    try:
        view.setProperty(TABLE_SHARING_PROP, True)
        for column in range(count):
            if new[column] is not None and new[column] != widths[column]:
                view.setColumnWidth(column, max(0, int(new[column])))
    except Exception:
        pass
    finally:
        try:
            view.setProperty(TABLE_SHARING_PROP, False)
        except Exception:
            pass
    fitted_bar(view, new, room)
    if after_fit:
        widen_window(view)
    return new


def fitted_bar(view, widths, room):
    """A list whose columns fit its width shows no horizontal scroll bar until they no longer do: the
    columns are shared on the next turn of the event loop after a resize, so between the two the old
    widths passed the new width and the bar flashed on and off as the window was resized (owner's image
    295). Off while the columns fit; as needed once even their least passes the width. Not for an empty
    list (empty_bars keeps its bars off)."""
    try:
        if view_rows(view) == 0:
            return
        QtCore = _qt()[0]
        total = sum(int(w) for w in widths if w is not None)
        policy = QtCore.Qt.ScrollBarAlwaysOff if total <= room + 1 else QtCore.Qt.ScrollBarAsNeeded
        if _property(view, "horizontalScrollBarPolicy") != policy:
            view.setHorizontalScrollBarPolicy(policy)
    except Exception:
        pass


MIN_SECTION = 24  # pixels: a column dragged narrower stops here (at 0 it vanished, with no way to get it back)
TABLE_DRAG_PROP = "freelabTableDrag"  # on a list while the owner drags one of its column edges


def view_rows(view):
    """How many rows a list shows at its top level (a tree's, a table's, a list's), or None."""
    for name in ("topLevelItemCount", "rowCount", "count"):
        try:
            value = getattr(view, name)
            return int(value() if callable(value) else value)
        except Exception:
            continue
    return None


def empty_bars(view):
    """A list with no row shows no scroll bar: while it was resized, its columns (shared on the next turn
    of the event loop) passed its width for a moment, and an empty list flashed its bars (owner's image
    192). Its bars come back as needed once it has rows: the vertical one here, the horizontal one when
    its columns no longer fit (fitted_bar, as they are shared out)."""
    try:
        QtCore = _qt()[0]
        empty = view_rows(view) == 0
        policy = QtCore.Qt.ScrollBarAlwaysOff if empty else QtCore.Qt.ScrollBarAsNeeded
        for name in ("horizontalScrollBarPolicy", "verticalScrollBarPolicy") if empty else ("verticalScrollBarPolicy",):
            if _property(view, name) != policy:
                getattr(view, "set" + name[0].upper() + name[1:])(policy)
    except Exception:
        pass


def stretch_column(view, measure=False):
    """The list's columns shared out again (share_columns; the name tools called before). measure: after
    a fill, what the columns want noted first (their widths now), unless a fit noted it already
    (fit_rows: the widths now are shared out, past what the columns want)."""
    if measure and not _wants_of(view).get("wants"):
        note_wants(view)
    return share_columns(view, after_fit=measure)


def watch_table(view):
    """The list's columns shared out again as the list is resized and as the owner drags a column
    (share_columns), by a watch on its viewport and its header: parented to the list (Qt deletes it with
    it, never PythonQt at whatever moment Python's collector picks) and held in sys (PythonQt drops a
    Python override or a slot no one holds). The filter and the header's signal only start the watch's
    own timer: the widths change on the next turn of the event loop, never synchronously inside Qt's
    resizing (where setting a width re-enters the layout). A column dragged keeps the width given it,
    which is what that column wants from then on, until the list is fitted again."""
    QtCore = _qt()[0]
    modules, name, own, own_note = sys.modules, __name__, share_columns, note_wants
    own_limit, _header_of_now, MIN_SECTION_NOW = drag_limit_of, _header_of, [MIN_SECTION]
    dragged = [None]
    try:
        if view.property(TABLE_FILL_PROP) is not None:
            return None  # (watched already)

        class TableWatch(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == RESIZE_EVENT:
                        self.start()  # (the widths changed on the next turn: never inside Qt's layout)
                    elif kind in (2, 3) and obj is not view.viewport():  # (a press or release on the header)
                        # While a column edge is dragged, Qt keeps the last column at the list's edge; the
                        # columns are shared out once it is let go. Shared at each move, the last column
                        # came off the edge and back (owner's image 173: "jittery")
                        header = _header_of(view)
                        dragging = kind == 2
                        view.setProperty(TABLE_DRAG_PROP, dragging)
                        header.setStretchLastSection(dragging)
                        if not dragging:
                            self.start()
                except Exception:
                    pass  # an event filter must never raise
                return False

        watch = TableWatch(view)

        def share():  # (no globals below: a reload empties them)
            try:
                held, dragged[0] = dragged[0], None
                (getattr(modules.get(name), "share_columns", None) or own)(view, held)
            except Exception:
                pass  # a slot must not raise

        def resized(column, old, new):
            try:
                if view.property(TABLE_SHARING_PROP):
                    return  # (share_columns' own widths)
                if view.property(TABLE_DRAG_PROP):  # (the owner's drag: kept inside the frame, MIN_SECTION at least)
                    module = modules.get(name)
                    limit = (getattr(module, "drag_limit_of", None) or own_limit)(view, int(column))
                    if limit is not None and (int(new) > limit or int(new) < MIN_SECTION_NOW[0]):
                        new = limit if int(new) > limit else MIN_SECTION_NOW[0]
                        view.setProperty(TABLE_SHARING_PROP, True)
                        try:
                            _header_of_now(view).resizeSection(int(column), int(new))
                        finally:
                            view.setProperty(TABLE_SHARING_PROP, False)
                dragged[0] = int(column)
                (getattr(modules.get(name), "note_wants", None) or own_note)(view, {int(column): int(new)})
                watch.start()
            except Exception:
                pass  # a slot must not raise

        watch.setSingleShot(True)
        watch.setInterval(0)
        watch.connect("timeout()", share)
        watch.freelab_slots = (share, resized)  # (held: PythonQt drops a slot no Python object holds)
        view.viewport().installEventFilter(watch)
        try:
            header = _header_of(view)
            header.setMinimumSectionSize(MIN_SECTION)
            header.viewport().installEventFilter(watch)  # (its presses and releases: a drag's start and end)
        except Exception:
            pass
    except Exception:
        return None
    try:
        _header_of(view).connect("sectionResized(int,int,int)", resized)
    except Exception:
        pass  # (no header to drag: the list's resizes are still heard)
    held = getattr(sys, "_freelab_table_fills", None)
    if held is None:
        held = sys._freelab_table_fills = []
    held.append(watch)
    del held[:-TABLE_FILLS_KEPT]
    try:
        view.setProperty(TABLE_FILL_PROP, len(held))
    except Exception:
        pass
    return watch


def watch_stretch(view):
    """watch_table (the name tools called before)."""
    return watch_table(view)


def set_stretch(view, column):
    """A FreeLab list's stretch column named after it was laid out (table_layout's stretch): the column
    that takes the room left once every column shows its content whole, and is never cut (share_columns)."""
    try:
        view.setProperty(TABLE_PROP, int(column))
        _header_of(view).setStretchLastSection(False)
    except Exception:
        return
    watch_table(view)


def table_layout(view, stretch=None, numbers=(), grid=True):
    """FreeLab's one layout of a list of rows (tree, table, or list widget; see TABLE_PROP above):
    left alone by dark mode, grid lines (none: grid False), room around each cell's content, check
    boxes and selected rows in the palette's selection colors, no focus rectangle, headers centered,
    the columns filling the width (share_columns; stretch: the column given what is left once every
    column shows its content, never cut; None: every column in proportion). numbers: the columns of
    numbers (the tool right-aligns their cells; their headers are centered as every other's). Returns
    the view."""
    try:
        view.setProperty(LEAVE_ALONE_PROP, True)  # (the whole list: its header and scroll bars too)
        view.setProperty(TABLE_PROP, -1 if stretch is None else int(stretch))
        view.setProperty(TABLE_GRID_PROP, bool(grid))
    except Exception:
        pass
    style_table(view)
    header = _header_of(view)
    if header is not None:
        try:
            header.setStretchLastSection(False)  # (share_columns fills the width: no gap, nothing squeezed by Qt)
        except Exception:
            pass
        center_headers(view)
        watch_table(view)
    return view


def is_table(view):
    """A list laid out by table_layout."""
    try:
        return view.property(TABLE_PROP) is not None
    except Exception:
        return False


def grid_lines(view):
    """A list in FreeLab's table layout (table_layout), its last column stretched (the name the tools
    used before the layout took over the grid's place)."""
    return table_layout(view)


def flat_combo(box):
    """A combo box inside a list's cell: no frame of its own."""
    try:
        box.setFrame(False)
    except Exception:
        pass
    return box


def enable(button, on):
    """A button clickable only when it would do something."""
    try:
        if on and button.property(NO_FONT_PROP):
            return  # (grayed while its window has no font: no_font_states gives it back with a font)
    except Exception:
        pass
    try:
        # Always asked: a button inside a grayed panel reports itself grayed whatever it was last told, so
        # "gray it out" was skipped while a tool was busy, and the button came back clickable.
        button.setEnabled(bool(on))
    except Exception:
        pass


NO_FONT_PROP = "freelabNoFont"  # on a control no_font_states grayed (its window has no font)
NO_FONT_HIDDEN_PROP = "freelabNoFontHidden"  # on a preview caption no_font_states hid (shown again with a font)
WITHOUT_FONT_PROP = "freelabWithoutFont"  # on a control a tool keeps usable without a font (a font chooser)
SEPARATOR_PROP = "freelabSeparator"  # on separator()'s lines
HEADER_SEPARATOR_PROP = "freelabHeaderSeparator"  # on the line under a window's top text (separator(header=True))
PREVIEW_CAPTION_PROP = "freelabPreviewCaption"  # on a preview's caption (preview_caption): quiet, whatever
CAPTION_PROP = "freelabCaption"  # on a label that captions the control after it (caption_states)
NO_FONT_KINDS = ("QPushButton", "QCheckBox", "QRadioButton", "QComboBox", "QAbstractSpinBox", "QLineEdit",
                 "QAbstractSlider")
ALWAYS_ON_TEXTS = (u"Close",)  # buttons usable whatever the window holds


def window_has_font(owner):
    """Whether a tool's window works on a font now (its own has_font(), else its package); True for a
    tool that works without one (works_without_font: Font Builder)."""
    if owner is None or getattr(owner, "works_without_font", False):
        return True
    own = getattr(owner, "has_font", None)
    if callable(own):
        try:
            return bool(own())
        except Exception:
            return True
    return getattr(owner, "package", None) is not None


def no_font_states(dialog):
    """A window with no font (owner's images 193 to 210): its separators hidden (there is nothing under
    them to set apart), and its controls grayed (nothing they act on), but the tools menu, the arrows,
    help, Close, and what a tool keeps usable without a font (WITHOUT_FONT_PROP). Given back as a font
    comes; meanwhile enable() keeps them grayed whatever the tool asks."""
    QtGui = _qt()[1]
    owner = window_owner(dialog)
    if owner is None:
        return
    has_font = window_has_font(owner)
    window = dialog.window()
    restored = []
    if getattr(owner, "busy", False):
        return  # (a tool at work sets its own states)
    for line in dialog.findChildren(QtGui.QFrame):
        try:
            shown = has_font or heads_section(line)
            if line.property(SEPARATOR_PROP) and bool(_property(line, "visible")) != shown and line.window() == window:
                line.setVisible(shown)
        except Exception:
            continue
    for label in dialog.findChildren(QtGui.QLabel):  # (a preview's caption over nothing: owner's image 283)
        try:
            if not label.property(PREVIEW_CAPTION_PROP) or label.window() != window:
                continue
            if not has_font and bool(_property(label, "visible")):
                label.setProperty(NO_FONT_HIDDEN_PROP, True)
                label.setVisible(False)
            elif has_font and label.property(NO_FONT_HIDDEN_PROP):
                label.setProperty(NO_FONT_HIDDEN_PROP, None)
                label.setVisible(True)
        except Exception:
            continue
    for view in dialog.findChildren(QtGui.QAbstractItemView):
        try:
            if view.property(TABLE_PROP) is not None:
                empty_bars(view)
        except Exception:
            continue
    for kind in NO_FONT_KINDS:
        for widget in dialog.findChildren(getattr(QtGui, kind)):
            try:
                if widget.window() != window or widget.property(WITHOUT_FONT_PROP):
                    continue
                if kind == "QPushButton" and (u"%s" % widget.text).replace(u"&", u"") in ALWAYS_ON_TEXTS:
                    continue
                if kind == "QAbstractSpinBox" and widget.parentWidget() is not None and \
                        widget.parentWidget().inherits("QAbstractSpinBox"):
                    continue
                marked = bool(widget.property(NO_FONT_PROP))
                if not has_font and not marked and widget.isEnabled():
                    widget.setProperty(NO_FONT_PROP, True)
                    widget.setEnabled(False)
                elif has_font and marked:
                    widget.setProperty(NO_FONT_PROP, None)
                    widget.setEnabled(True)
                    restored.append(widget)
            except Exception:
                continue
    refresh = getattr(owner, "update_buttons", None)
    if restored and callable(refresh):  # (the tool's own states over them again: some stay grayed)
        try:
            refresh()
        except Exception:
            pass


def heads_section(line):
    """Whether a separator sets apart a section's heading (the label right after it in its layout): it
    stays with no font, the list's frame above and the heading below being shown then too (owner's image
    318, Feature Code's Figure forms to build: "missing on all windows where it should be present")."""
    try:
        parent = line.parentWidget()
        after = _next_widget(parent.layout(), line) if parent is not None else None
        return (after is not None and after is not _NOT_FOUND and bool(after.inherits("QLabel"))
                and not after.property(PREVIEW_CAPTION_PROP))  # (a line between two previews goes)
    except Exception:
        return False


def checks_of(items, checked):
    """(any checked, any unchecked) over checkable items: whether Check none and Check all would do
    anything."""
    some_on = some_off = False
    for item in items:
        if checked(item):
            some_on = True
        else:
            some_off = True
        if some_on and some_off:
            break
    return some_on, some_off


def row_hidden(item):
    """Whether a list's row is out of sight: hidden itself (filtered out), or inside a group that is
    closed or hidden (scrolled out of view does not count)."""
    try:
        if item.isHidden():
            return True
        parent = item.parent()
        while parent is not None:
            if parent.isHidden() or not parent.isExpanded():
                return True
            parent = parent.parent()
    except Exception:
        pass
    return False


def check_line(command, checked, unchecked, hidden, noun=u"row", many=None, hidden_text=(u"hidden", u"hidden")):
    """The log line of a button that ticks or unticks many rows (check_rows): "*Tick all* ticked 12
    pairs (3 of them hidden)." command: the button's name; checked, unchecked: the rows it changed each
    way; hidden: how many of those were out of sight (row_hidden), said so; hidden_text: how they were
    hidden, for one and for many ("in a closed group", "in closed groups")."""
    if not checked and not unchecked:
        return u"%s changed nothing." % i(command)
    parts = []
    if checked:
        parts.append(u"ticked %s" % b(counted(checked, noun, many)))
    if unchecked:
        parts.append(u"unticked %s" % (b(counted(unchecked, noun, many)) if not checked else b(grouped(unchecked))))
    changed = checked + unchecked
    note = u""
    if hidden:
        if changed == 1:
            note = u" (%s)" % hidden_text[0]
        elif hidden == changed:
            note = u" (all of them %s)" % hidden_text[1]
        else:
            note = u" (%s of them %s)" % (b(grouped(hidden)), hidden_text[0] if hidden == 1 else hidden_text[1])
    return u"%s %s%s." % (i(command), u" and ".join(parts), note)


def check_rows(items, wanted, log=None, command=u"Tick all", noun=u"row", many=None,
               hidden_text=(u"hidden", u"hidden")):
    """What Check all, Check none, and every button that checks or unchecks many rows share: each
    checkable row of items (QTreeWidgetItem or QListWidgetItem, column 0) set to wanted (True, False, or
    a function of the item giving either, or None to leave it), and the log told how many it checked
    and unchecked, and how many of those were out of sight (row_hidden: in a closed group, or filtered
    out), as check_line words it (owner's report 118: these buttons left no line). Returns (checked,
    unchecked, hidden). A tool calls it from its button's slot, then updates its buttons as before."""
    QtCore = _qt()[0]
    on, off = QtCore.Qt.Checked, QtCore.Qt.Unchecked
    checked = unchecked = hidden = 0
    for item in items:
        try:
            want = wanted(item) if callable(wanted) else wanted
            if want is None:
                continue
            try:
                state = item.checkState(0)  # (a tree's row)
                tree_row = True
            except Exception:
                state, tree_row = item.checkState(), False  # (a list widget's)
            if int(state) == int(on if want else off):
                continue
            if tree_row:
                item.setCheckState(0, on if want else off)
            else:
                item.setCheckState(on if want else off)
        except Exception:
            continue
        if want:
            checked += 1
        else:
            unchecked += 1
        if row_hidden(item):
            hidden += 1
    if log is not None:
        log.add(check_line(command, checked, unchecked, hidden, noun, many, hidden_text))
    return checked, unchecked, hidden


HISTORY_POLL_MS = 700  # how often an open dialog looks whether the font's History moved


def history_mark(package):
    return (font_key(package), history_state(package)) if package is not None else None


def watch_history(owner):
    """While owner's dialog is shown, calls owner.history_moved() when the font's place in FontLab's
    History differs from owner.seen_history: an undo, a redo, or an edit made in FontLab meanwhile.
    The owner sets seen_history (history_mark) after its own analysis and writes. Keep the timer."""
    QtCore, QtGui = _qt()
    try:  # (its parent the window: Qt deletes it with the window)
        timer = QtCore.QTimer(owner.dialog)
    except Exception:
        timer = QtCore.QTimer()
    timer.setInterval(HISTORY_POLL_MS)

    def tick():
        try:
            if not _property(owner.dialog, "visible") or getattr(owner, "busy", False):
                return
            package, seen = getattr(owner, "package", None), getattr(owner, "seen_history", None)
            if package is None or seen is None:
                return
            # (at each tick, not only when the place moved since owner's last look: a window that was busy when
            # the History moved notes the new place itself once done, and a redo then went unfollowed, live
            # 2026-11-18; cheap: nothing is read for a font whose info FreeLab never updated)
            follow_font_info(package, getattr(owner, "log", None), when_needed=True)
            now = history_mark(package)
            if now != seen:
                # Read again only once the History has stayed at one place for a tick: Undo pressed several
                # times in a row otherwise landed inside a window's read (its events pumped), on glyphs the
                # next Undo had put back (owner's images 373 and 377)
                if getattr(owner, "history_settling", None) != now:
                    owner.history_settling = now
                    return
                owner.history_settling = None
                owner.seen_history = now
                owner.history_moved()
            else:
                owner.history_settling = None
        except Exception:
            pass  # a timer's handler must not raise

    owner.history_tick = tick  # (held with the tool: PythonQt drops a slot no Python object holds)
    timer.connect("timeout()", tick)
    timer.start()
    return timer


class ClickRegions(object):
    """Spans of a widget's picture (a label's pixmap, or a button's icon, drawn centered) that can be
    double-clicked: each (left, right, key) across the picture, in its pixels. A double-click on one calls
    on_click(key); a single click there does nothing (the widget's own click does not happen either): a
    click meant for the button took it to another pair (owner's image 362, as Glyph Compose's previews,
    image 333). The pointer becomes a hand over one."""

    def __init__(self, widget, on_click, tip=u""):
        QtCore, QtGui = _qt()
        self.widget, self.on_click, self.tip = widget, on_click, tip
        self.regions, self.size = [], (0, 0)
        self.pending = []  # (a double-click's call, held until its timer runs it: see below)
        regions = self

        def later(key):
            """on_click(key) once the event is over, as a slot held here until it runs: PythonQt drops a slot
            no Python object holds (adversarial review 9)."""
            def call():
                try:
                    if call in regions.pending:
                        regions.pending.remove(call)
                    regions.on_click(key)
                except Exception:
                    pass  # (a timer's slot must not raise)
            regions.pending.append(call)
            QtCore.QTimer.singleShot(0, call)

        class Filter(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind in (2, 3, 4):  # MouseButtonPress, -Release, -DblClick
                        key = regions.hit(event)
                        if key is not None:
                            if kind == 4:
                                later(key)
                            return True  # the widget's own click does not happen
                    elif kind == 5:  # MouseMove
                        over = regions.hit(event) is not None
                        obj.setCursor(QtCore.Qt.PointingHandCursor if over else QtCore.Qt.ArrowCursor)
                        obj.setToolTip(regions.tip if over else (obj.property("freelabTip") or u""))
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.filter = Filter(widget)  # (its parent the widget it watches: Qt deletes it with it)
        try:
            widget.setMouseTracking(True)
            widget.setProperty("freelabTip", _property(widget, "toolTip"))
            widget.installEventFilter(self.filter)
        except Exception:
            pass

    def set(self, regions, size):
        self.regions, self.size = list(regions), (size.width(), size.height()) if hasattr(size, "width") else size

    def hit(self, event):
        if not self.regions:
            return None
        try:
            pos = event.pos()
            x, y = pos.x(), pos.y()
            rect = _property(self.widget, "rect")
        except Exception:
            return None
        width, height = self.size
        x -= (rect.width() - width) / 2.0
        y -= (rect.height() - height) / 2.0
        if not 0 <= y <= height:
            return None
        for x0, x1, key in self.regions:
            if x0 <= x < x1:
                return key
        return None


PAIR_PREVIEW_EM = 120  # pixels per em in the pair previews of Kerning Check and Kerning Classes
PAIR_ALPHA = 185  # each glyph of a previewed pair this opaque: where they overlap, the ink is denser
ADJUST_ROOM = 0.5  # of the em: room right of an adjustable preview's pair, for dragging its right glyph apart
ADJUST_SHIFT_STEP = 10  # units per Left or Right press with Shift held (1 without)


def pair_pixmap(package, master, left, right, value, caption, color, font, room=False, width=None):
    """A glyph pair at a kerning value, both glyphs see-through in color (where their ink overlaps it
    is denser), its caption under it in font; an empty pixmap when a glyph is missing. room: space at
    the right to drag the right glyph into; width: the picture's width (kept while one is dragged)."""
    QtCore, QtGui = _qt()
    layers = []
    for name in (left, right):
        glyph = package.findName(name)
        layer = glyph.getLayerByName(master) if glyph is not None and not glyph.isNull else None
        if layer is None:
            return QtGui.QPixmap()
        layers.append((layer, layer_path(layer)))
    em = PAIR_PREVIEW_EM
    scale = float(em) / float(package.upm)
    margin = em // 4
    if width is None:
        width = int((layers[0][0].advanceWidth + max(0, layers[1][0].advanceWidth + value)) * scale) + 2 * margin
        if room:
            width += int(em * ADJUST_ROOM)
    line = QtGui.QFontMetrics(font).height() if caption else 0  # (no caption: no blank band under the pair)
    height = int(em * 1.35) + line
    drawn = width  # (the pair's own width; a caption wider than it widens the picture, the pair centered in it:
    # a long font name was cut at both ends, owner's image 368)
    if caption and not room:
        try:
            width = max(width, int(QtGui.QFontMetrics(font).width(caption)) + 2 * margin)
        except Exception:
            pass
    pixmap = QtGui.QPixmap(max(width, 2 * margin), height)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    ink = QtGui.QColor(color)
    ink.setAlpha(PAIR_ALPHA)
    painter = QtGui.QPainter(pixmap)
    colored = False
    try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setFont(font)
        x = float(margin) + max(0, width - drawn) / 2.0
        for index, (layer, path) in enumerate(layers):
            painter.save()
            painter.translate(x, em * 1.05)
            painter.scale(scale, -scale)
            parts = layer_parts(layer)
            colored = colored or bool(parts)
            fill_glyph(painter, path, QtGui.QBrush(ink), parts)
            painter.restore()
            x += (layer.advanceWidth + (value if index == 0 else 0)) * scale
        if caption:
            painter.setPen(color)
            painter.drawText(QtCore.QRect(0, height - line, pixmap.width(), line), int(QtCore.Qt.AlignCenter), caption)
    finally:
        painter.end()
    return pixmap if colored else inked(pixmap, color)  # (one color, at two strengths: redrawn on a switch)


class PairDrag(object):
    """A pair preview whose right glyph is dragged left or right (only across: kerning) to adjust a
    value, which follows as it moves; clicked, Left and Right nudge it (Shift: ADJUST_SHIFT_STEP
    units), Up and Down step to the list's next or previous row. get() gives the value now (None: the
    preview shows nothing adjustable), put(value) sets it, step(1 or -1) selects another row, and
    scale() gives the preview's pixels per font unit."""

    def __init__(self, label, get, put, step, scale):
        QtCore, QtGui = _qt()
        self.start = None
        drag = self
        label.setMouseTracking(True)
        label.setFocusPolicy(QtCore.Qt.ClickFocus)
        label.setToolTip(u"Drag the right glyph left or right to adjust; or click, then press <i>Left</i> or <i>Right</i> "
                         u"(with <i>Shift</i>: %d units)." % ADJUST_SHIFT_STEP)

        class Filter(QtCore.QTimer):  # PythonQt has no QObject to subclass; a timer will do
            def eventFilter(self, obj, event):
                try:
                    kind = event.type()
                    if kind == 2:  # MouseButtonPress
                        value = get()
                        drag.start = (event.pos().x(), value) if value is not None else None
                        return False  # (the label still takes the focus, for the keys)
                    if kind == 5:  # MouseMove
                        if drag.start is not None:
                            x, value = drag.start
                            put(value + int(round((event.pos().x() - x) / scale())))
                            return True
                        obj.setCursor(QtCore.Qt.SizeHorCursor if get() is not None else QtCore.Qt.ArrowCursor)
                    elif kind == 3:  # MouseButtonRelease
                        drag.start = None
                    elif kind == 6:  # KeyPress
                        key = event.key()
                        if key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                            step(1 if key == QtCore.Qt.Key_Down else -1)
                            return True
                        value = get()
                        if value is not None and key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
                            shift = int(event.modifiers()) & int(QtCore.Qt.ShiftModifier)
                            by = ADJUST_SHIFT_STEP if shift else 1
                            put(value + (by if key == QtCore.Qt.Key_Right else -by))
                            return True
                except Exception:
                    pass  # an event filter must never raise
                return False

        self.filter = Filter(label)  # (its parent the label it watches: Qt deletes it with it)
        label.installEventFilter(self.filter)


def select_next_row(tree, step):
    """The row below (step 1) or above (-1) a tree's current one made current."""
    current = tree.currentItem()
    if current is None:
        return
    other = tree.itemBelow(current) if step > 0 else tree.itemAbove(current)
    if other is not None:
        tree.setCurrentItem(other)


# FontLab's flags (its Flag menu: the glyph's mark, a hue plus one; 0 for none), as the lists offer them
FLAG_COLORS = ((u"Red", 1), (u"Green", 121), (u"Cyan", 181), (u"Blue", 241), (u"Magenta", 301), (u"None", 0))


FLAG_TINT = 80  # the alpha of a flagged row's tint: its flag's color, readable under either palette's text
FLAG_ROLE = 0x0100 + 77  # Qt.UserRole + 77: a cell's flag colors (a list's stylesheet item rule hides BackgroundRole)
FLAG_BAR = 3  # pixels: the opaque bar of a flag's color along a flagged cell's bottom, shown over a selected row too


def flag_colors_text(marks):
    """A cell's flag colors as stored in FLAG_ROLE: one per glyph of the row, "#rrggbb" or "" for none,
    joined by commas (a pair's left and right halves); None when no glyph is flagged."""
    if not any(marks):
        return None
    return u",".join(flag_color(m).name() if m else u"" for m in marks)


def flag_segments(text, left, width):
    """[(x, width, "#rrggbb")] of a cell's flagged parts: the cell split evenly among the row's glyphs."""
    names = (text or u"").split(u",")
    found = []
    for k, name in enumerate(names):
        x0 = left + width * k // len(names)
        x1 = left + width * (k + 1) // len(names)
        if name:
            found.append((x0, x1 - x0, name))
    return found


def separator(header=False, vertical=False):
    """A thin line between parts of a window: a mid gray at half strength, as the lists' cell lines.
    header: the line under a window's top text (its font line and status lines), shown whatever the
    window holds (owner's images 222, 223, 275, 276: every window has one, and it stays with no font:
    the grayed fields are still under it); any other is hidden while the window has no font
    (no_font_states: nothing under it to set apart). vertical: a line between two previews side by side."""
    QtCore, QtGui = _qt()
    line = QtGui.QFrame()
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    line.setStyleSheet(u"QFrame { border: none; background: rgba(128, 128, 128, 128); }")
    line.setProperty(HEADER_SEPARATOR_PROP if header else SEPARATOR_PROP, True)
    return line


def sentence_end(row):
    """The period that ends a sentence the controls of row finish ("List changes of at least [20 units]."),
    against its last control: the row's spacing taken back before it (a spacing of its own, the period
    floated a word's width away, live 2026-11-17). The period is that control's caption (caption): grayed
    with it, as with no font (owner's images 319 to 323: it stayed bright), and its help the control's.
    Returns the label."""
    QtGui = _qt()[1]
    try:
        spacing = int(_property(row, "spacing"))
    except Exception:
        spacing = -1
    last = _last_widget(row)
    row.addSpacing(-(spacing if spacing >= 0 else 6) + 1)  # (live: a negative spacing is taken as it is)
    label = QtGui.QLabel(u".")
    row.addWidget(label)
    if last is not None:
        caption(label, last)
    return label


def _last_widget(layout):
    """The last widget of a row (layout), its nested layouts searched from the end; None if it holds none."""
    try:
        count = layout.count()
    except Exception:
        return None
    for k in range(count - 1, -1, -1):
        item = layout.itemAt(k)
        if item is None:
            continue
        if item.widget() is not None:
            return item.widget()
        if item.layout() is not None:
            found = _last_widget(item.layout())
            if found is not None:
                return found
    return None


def header_separator():
    """separator(header=True): the line under a window's top text, always shown."""
    return separator(header=True)


def show_only(groups, shown):
    """Shows the widgets of groups[shown] and hides every other group's (groups: a dict or a list of
    lists of widgets), the others hidden FIRST: a tab's buttons share the window's bottom row, and a
    switch that showed the new tab's before hiding the old ones held both a moment, so Qt grew the window
    to fit them and never gave the width back (owner's image 284, live 2026-11-18: Glyph Compose went from
    1,084 to 1,568 pixels with no font). Never raises."""
    try:
        keys = list(groups.keys()) if hasattr(groups, "keys") else list(range(len(groups)))
    except Exception:
        return
    for show in (False, True):
        for key in keys:
            if (key == shown) != show:
                continue
            for widget in groups[key] or ():
                try:
                    if bool(_property(widget, "visible")) != show or not show:
                        widget.setVisible(show)
                except Exception:
                    pass


def preview_caption(text=u"", label=None):
    """A preview's caption ("Now", "Suggested", "In the font: a"), as CJK Spacing first drew them
    (owner's image 246): a tenth smaller, in the quiet (grayed) text color. label: an existing label to
    style, else a new one. Marked so that caption_states never gives it the color of a control."""
    QtGui = _qt()[1]
    if label is None:
        label = QtGui.QLabel(text)
    quiet = QtGui.QFont(_property(label, "font"))
    try:
        quiet.setPointSizeF(quiet.pointSizeF() * 0.9)
    except Exception:
        pass
    label.setFont(quiet)
    label.setEnabled(False)  # (drawn in the quiet text color)
    label.setProperty(PREVIEW_CAPTION_PROP, True)
    return label


def flag_color(mark, alpha=255):
    """The color FontLab shows for a flag (glyph.mark: a hue plus one)."""
    QtCore, QtGui = _qt()
    color = QtGui.QColor()
    color.setHsv((int(mark) - 1) % 360, 190, 235, alpha)
    return color


def flag_menu(view, owner, names_of_selection, names_of_row=None, column=0):
    """A list's flags: see FlagMenu. Keep what it returns."""
    return FlagMenu(view, owner, names_of_selection, names_of_row, column)


class FlagMenu(object):
    """A right-click menu on a list: the selected row's glyphs flagged in FontLab, as its Flag menu
    does, to find them again later (the Font window shows the flag; Select > Same Flag gathers them),
    and the next or previous flagged row (F3, Shift+F3). With names_of_row (a tree's item, or a
    table's row number, to its glyphs' names), each row whose glyph has a flag shows its color in
    the given column: a tint, and a bar along the bottom that a selected row shows too; a pair's
    cell split in two, each glyph's flag on its own half. Read again whenever the list is filled or
    its items replaced. names_of_selection() gives the selected row's glyphs; owner has package,
    fontlab, log, dialog, and seen_history."""

    def __init__(self, view, owner, names_of_selection, names_of_row=None, column=0):
        QtCore, QtGui = _qt()
        self.view, self.owner, self.column = view, owner, column
        self.names_of_selection, self.names_of_row = names_of_selection, names_of_row
        self.due = False
        self.refreshing = False
        self.cache = {}  # glyph name: its flag, until the list is filled again or a flag is set here
        self.table = view.inherits("QTableWidget")
        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        view.connect("customContextMenuRequested(QPoint)", self.show)
        self.shortcuts = []
        for keys, step in (("F3", 1), ("Shift+F3", -1)):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(keys), view)
            shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
            shortcut.connect("activated()", (lambda step: lambda: self.go(step))(step))
            self.shortcuts.append(shortcut)
        if names_of_row is not None:
            role, bar, tint, segments = FLAG_ROLE, FLAG_BAR, FLAG_TINT, flag_segments

            class Tint(QtGui.QStyledItemDelegate):  # (what it uses held here: a dropped module's globals turn None)
                def paint(self, painter, option, index):
                    parts = []
                    try:
                        rect = option.rect
                        parts = segments(index.data(role), rect.left(), rect.width())
                        for x, width, name in parts:
                            color = QtGui.QColor(name)
                            color.setAlpha(tint)
                            painter.fillRect(QtCore.QRect(x, rect.top(), width, rect.height()), color)
                    except Exception:
                        parts = []
                    QtGui.QStyledItemDelegate.paint(self, painter, option, index)
                    try:  # over the row as drawn: a selected row's highlight covers the tint, not the bar
                        for x, width, name in parts:
                            painter.fillRect(QtCore.QRect(x, rect.bottom() - bar + 1, width, bar), QtGui.QColor(name))
                    except Exception:
                        pass

            self.delegate = Tint(view)
            view.setItemDelegateForColumn(column, self.delegate)
            model = view.model()
            model.connect("rowsInserted(QModelIndex,int,int)", lambda *args: self.soon(True))
            model.connect("modelReset()", lambda: self.soon(True))
            # (a list filled again with as many rows replaces its items: Auto Kerning's order and filters)
            model.connect("dataChanged(QModelIndex,QModelIndex)", lambda *args: self.soon())

    # -- the rows --------------------------------------------------------------------

    def rows(self):
        """[(a tree's item or a table's row, the glyphs' names)], in the list's order."""
        found = []
        if self.names_of_row is None:
            return found
        if self.table:
            for row in range(_property(self.view, "rowCount")):
                found.append((row, self.names_safely(row)))
            return found
        pending = [self.view.topLevelItem(i) for i in range(_property(self.view, "topLevelItemCount"))][::-1]
        while pending:
            item = pending.pop()
            found.append((item, self.names_safely(item)))
            pending.extend(item.child(i) for i in reversed(range(item.childCount())))
        return found

    def names_safely(self, handle):
        try:
            return [n for n in (self.names_of_row(handle) or []) if n]
        except Exception:
            return []

    def marks(self, names, cache):
        package = self.owner.package
        found = []
        for name in names:
            if name not in cache:
                glyph = package.findName(name) if package is not None else None
                try:
                    cache[name] = int(glyph.mark) if glyph is not None and not glyph.isNull else 0
                except Exception:
                    cache[name] = 0
            found.append(cache[name])
        return found

    def usable(self):
        """Whether the list is still there to work on: its tool not let go (let_go), the list not deleted.
        A list deleted with its window sent its model's signals as it went, and the refresh they asked
        for ran on the deleted list (live: "Trying to call 'signalsBlocked' on a destroyed QTreeWidget")."""
        return not getattr(self.owner, RELEASED, False) and widget_alive(self.view)

    def soon(self, filled=False):
        QtCore, QtGui = _qt()
        if self.refreshing or not self.usable():
            return  # its own tints; or a list going away
        if filled:
            self.cache = {}  # filled again (an undo, another font): flags read anew
        if not self.due:
            self.due = True
            QtCore.QTimer.singleShot(0, self.refresh)

    def refresh(self):
        """Each row's cell tinted with the flag of its first flagged glyph, or plain."""
        QtCore, QtGui = _qt()
        self.due = False
        if self.names_of_row is None or not self.usable():
            return  # (never through a deleted list's items: a write through one corrupts FontLab's heap)
        blocked = self.view.signalsBlocked()
        self.view.blockSignals(True)  # a tint is no edit: the dialog's itemChanged must not hear it
        self.refreshing = True
        try:
            for handle, names in self.rows():
                text = flag_colors_text(self.marks(names, self.cache))
                if self.table:
                    item = self.view.item(handle, self.column)
                    if item is not None and item.data(FLAG_ROLE) != text:
                        item.setData(FLAG_ROLE, text)
                elif handle.data(self.column, FLAG_ROLE) != text:
                    handle.setData(self.column, FLAG_ROLE, text)
        except Exception:
            pass  # a list emptied meanwhile
        finally:
            self.refreshing = False
            self.view.blockSignals(blocked)
        self.view.viewport().update()

    def go(self, step):
        """The next (step 1) or previous (-1) row with a flagged glyph selected, around the list's end."""
        if not self.usable():
            return
        rows = [(handle, any(self.marks(names, self.cache))) for handle, names in self.rows()]
        if not any(flagged for _, flagged in rows):
            try:
                self.owner.log.add(u"No row of this list has a flagged glyph.", "warning")
            except Exception:
                pass
            return
        if self.table:
            current = _property(self.view, "currentRow")
            at = current if current >= 0 else -1
        else:
            item = _property(self.view, "currentItem")
            at = next((i for i, (handle, _) in enumerate(rows) if item is not None and handle is item), -1)
        count = len(rows)
        for k in range(1, count + 1):
            i = (at + step * k) % count
            handle, flagged = rows[i]
            if flagged:
                if self.table:
                    self.view.selectRow(handle)
                    self.view.scrollToItem(self.view.item(handle, 0))
                else:
                    self.view.setCurrentItem(handle)
                    self.view.scrollToItem(handle)
                return

    # -- the menu --------------------------------------------------------------------

    def show(self, pos):
        QtCore, QtGui = _qt()
        try:
            owner = self.owner
            names = [n for n in (self.names_of_selection() or []) if n]
            menu = QtGui.QMenu(owner.dialog)
            actions = []
            if names and owner.package is not None:
                title = menu.addAction(u"Flag %s in FontLab" % u" and ".join(names))
                title.setEnabled(False)
                for label, value in FLAG_COLORS:
                    action = menu.addAction(label)
                    if value:
                        pixmap = QtGui.QPixmap(12, 12)
                        pixmap.fill(flag_color(value))
                        action.setIcon(QtGui.QIcon(pixmap))
                    actions.append((action, label, value))
                menu.addSeparator()
            following = menu.addAction(u"Next flagged row\tF3")
            previous = menu.addAction(u"Previous flagged row\tShift+F3")
            view = self.view
            where = view.viewport().mapToGlobal(pos) if hasattr(view, "viewport") else view.mapToGlobal(pos)
            picked = menu.exec_(where)
            if picked is None or not self.usable():
                return  # (nothing picked; or its window closed meanwhile, let go: nothing to flag in)
            if picked.text == following.text:
                self.go(1)
                return
            if picked.text == previous.text:
                self.go(-1)
                return
            for action, label, value in actions:
                if action.text == picked.text:
                    flag_glyphs(owner, names, label, value)
                    break
        except Exception as exc:
            try:
                self.owner.log.add(u"Flagging did not work: %s" % html(exc), "error")
            except Exception:
                pass


def flag_glyphs(owner, names, label, value):
    """The glyphs flagged (or unflagged) in FontLab, as one step of its History; the owner's lists'
    tints read again. Nothing for a tool let go (its window closed while its menu was open)."""
    if getattr(owner, RELEASED, False):
        return
    package = owner.package
    glyphs = []
    for name in names:
        glyph = package.findName(name)
        if glyph is not None and not glyph.isNull:
            glyphs.append(glyph)
    if not glyphs:
        return
    log = getattr(owner, "log", None)
    if not begin_write(owner.fontlab, package, u"FreeLab flag", log, glyphs):
        return  # (nothing flagged: the reason in the log)
    for glyph in glyphs:
        glyph.mark = value
    notify_changed(owner.fontlab, package, u"FreeLab flag", glyphs, added=False).report(log)
    owner.seen_history = history_mark(package)  # its own step: nothing to read again
    menus = getattr(owner, "flagging", None)
    for menu in (menus if isinstance(menus, list) else [menus]):
        if isinstance(menu, FlagMenu):
            menu.cache = {}
            menu.refresh()
    if value:
        owner.log.add(u"Flagged %s %s in FontLab (<i>Select &gt; Same Flag</i> gathers them again; <i>F3</i> goes to the next "
                      u"flagged row here)." % (b(u", ".join(g.name for g in glyphs)), html(label.lower())), "done")
    else:
        owner.log.add(u"Took the flag off %s." % b(u", ".join(g.name for g in glyphs)), "done")


def open_auto_kerning_at(left, right, caller=None):
    """Auto Kerning, opened (or brought forward) on the pair of the glyphs named left and right, on
    caller's font (a widget of the window it is opened from: opening_from); the error's text, or None."""
    try:
        with opening_from(caller):
            held = _windows()["fonts"].get(calling_font())  # (the calling window's font: its own Auto Kerning, if open)
            if held is None or getattr(held, "tool", None) != "Auto Kerning" or not _property(held.dialog, "visible"):
                main(focus=(left, right))
            else:
                _bring_forward(held.dialog)
                held.focus_pair(left, right)
        return None
    except Exception as exc:
        return u"%s" % exc


def fontlab_autokern(package, master, left, right):
    """FontLab's own autokern for the pair: flPackage.autoKern returns it (as text or a number)
    without writing it. None when it gives nothing."""
    try:
        value = package.autoKern(package.findName(left), package.findName(right), master)
        return round_units(float(value))
    except Exception:
        return None


class Suggestion(object):
    def __init__(self, left_char, right_char, left, right, current):
        self.left_char, self.right_char = left_char, right_char
        self.left, self.right = left, right  # as on screen: measured and drawn so
        self.key = kerning_key(left_char, right_char, left, right)  # as the font's kerning holds it
        self.current = current
        self.raw = {}  # method: units before its factors
        self.values = {}  # method: units to write; "fontlab" once asked
        self.override = None  # a method chosen for this pair alone
        self.checked = None  # the user's check in the list; None until the list shows it

    def value(self, source):
        if source == "average":
            return average([self.values.get("halfkern"), self.values.get("contour")])
        if source == "current":
            return self.current
        return self.values.get(source)

    def to_write(self, source):
        """The value written: the pair's own choice, or the dialog's source."""
        return self.value(self.override or source)

    def spread(self):
        return spread([self.values.get(method) for method, _ in METHODS])


class Analysis(object):
    def __init__(self, suggestions, factors, bands, measured=0, reused=0, cache=None, cache_file=None):
        self.suggestions, self.factors, self.bands = suggestions, factors, bands
        self.measured, self.reused = measured, reused
        self.cache, self.cache_file = cache, cache_file

    def remember_fontlab(self):
        """Keep FontLab's values in the cache too (asked a pair at a time, they are slow)."""
        if self.cache is None or not self.cache_file:
            return
        pairs = self.cache.setdefault("pairs", {})
        for s in self.suggestions:
            if "fontlab" in s.values:
                entry = pairs.get(u"%s %s" % (s.left, s.right))
                if entry is not None:
                    entry[2] = s.values["fontlab"]  # [halfkern, contour, FontLab, learned]
        save_cache(self.cache_file, self.cache)


def script_label(key):
    """A Script list choice's label: the script's name, or All scripts."""
    return ALL_SCRIPTS_LABEL if key == ALL_SCRIPTS else dict(SCRIPTS).get(key, key)


def script_choices(found):
    """The Script list's keys for the scripts a font has: each, then All scripts when there are two or more."""
    keys = list(found) or ["latin"]
    return keys + [ALL_SCRIPTS] if len(keys) > 1 else keys


def pair_script(left_char, right_char, default="latin"):
    """The script of a pair of characters: its letters' (a mark of punctuation takes its partner's)."""
    return script_of(left_char) or script_of(right_char) or default


class MergedAnalysis(Analysis):
    """Several scripts' analyses in one list (All scripts): each pair measured by its own script, with
    that script's references and factors (s.script says which)."""

    def __init__(self, parts):
        suggestions, seen = [], set()
        for script, analysis in parts:
            for s in analysis.suggestions:
                if (s.left, s.right) not in seen:  # (no pair is in two scripts' lists: kept once if one were)
                    seen.add((s.left, s.right))
                    s.script = script
                    suggestions.append(s)
        first = parts[0][1] if parts else None
        Analysis.__init__(self, suggestions, first.factors if first else {}, first.bands if first else (None, None),
                          sum(a.measured for _, a in parts), sum(a.reused for _, a in parts))
        self.parts = parts
        self.script_factors = dict((script, analysis.factors) for script, analysis in parts)

    def remember_fontlab(self):
        for _, analysis in self.parts:
            analysis.remember_fontlab()  # (its suggestions are this list's: FontLab's values are on them)


def factors_of(analysis, script):
    """A script's factors in an analysis (a merged one holds each script's)."""
    return getattr(analysis, "script_factors", {}).get(script) or analysis.factors


def factor_summary(analysis):
    """How each method's tightening was scaled, for the status line: "halfkern tightens at 50%", and
    per script where an analysis of All scripts scaled them differently."""
    parts = getattr(analysis, "parts", None) or [(None, analysis)]
    summary = []
    for method in [m for m in MEASURED if any(m in s.raw for s in analysis.suggestions)]:
        readings = []
        for script, part in parts:
            if method not in part.factors or not any(method in s.raw for s in part.suggestions):
                continue
            tighten, _ = part.factors[method]
            fitted = part.factors[method] != DEFAULT_FACTORS[method]
            readings.append((script, u"%.0f%%%s" % (tighten * 100, u" (from the font's kerning)" if fitted else u"")))
        if not readings:
            continue
        if len(set(text for _, text in readings)) == 1:
            summary.append(u"%s tightens at %s" % (dict(METHODS)[method], readings[0][1]))
        else:
            summary.append(u"%s tightens at %s" % (dict(METHODS)[method], u", ".join(
                u"%s in %s" % (text, script_label(script)) for script, text in readings)))
    return summary


def touching_bias(core, groups, bias, limit):
    """The smallest halo from bias up (to limit) at which every pair of each group of references
    overlaps (a group without glyphs is passed over)."""
    while bias < limit:
        bands = [reference_band(core, refs, refs, bias) for refs in groups if refs]
        if all(band is None or band.low > 0 for band in bands):
            return bias
        bias += 1
    return bias


def make_bands(core, image_of, chars, em, max_bias, script="latin"):
    """Both methods' bands for each kind of pair, from the font's references in the script (Latin's:
    H, O, l, n, o, 0, 8); image_of(ch) gives the Glyph of a character in chars. Shared by Auto
    Kerning, Auto Spacing, and the learned method's training."""
    tuning = [image_of(ch) for ch in SCRIPT_TUNING[script]]
    try:
        band = calibrate(core, tuning, em, max_bias=max_bias)
    except ValueError:
        if script == "latin" or len(tuning) < 3:
            raise
        tuning = tuning[:2]  # (Georgian's san spaced far looser than in and on in some fonts: the halo from those two)
        band = calibrate(core, tuning, em, max_bias=max_bias)
    references = dict((kind, [image_of(ch) for ch in refs if ch in chars]) for kind, refs in SCRIPT_REFERENCES[script].items())
    if script != "latin":
        # The halo also reaches across every reference pair: a band whose loosest pair has no overlap
        # at all could not tighten anything (kana's references sit far apart under palt).
        bias = touching_bias(core, list(references.values()), band.bias, max_bias or em)
        if bias != band.bias:
            band = reference_band(core, tuning, tuning, bias) or Band(bias, band.low, band.high)
    halo_bands, contour_bands = {}, {}
    for left_kind in references:
        for right_kind in references:
            lefts, rights = references[left_kind], references[right_kind]
            halo_bands[(left_kind, right_kind)] = reference_band(core, lefts, rights, band.bias) or band
            contour_bands[(left_kind, right_kind)] = contour_band(core, lefts, rights) or contour_band(core, tuning, tuning)
    return {"core": core, "halo": halo_bands, "contour": contour_bands, "bias": band.bias}


def measure_pair(tools, left_char, right_char, left, right, em, reach):
    """(halfkern, contour distance) raw kerning of a pair in pixels, either None when out of reach."""
    kinds = pair_kinds(left_char, right_char)
    halo = suggest_pixels(tools["core"], left, right, tools["halo"][kinds])
    contour = suggest_contour_pixels(tools["core"], left, right, tools["contour"][kinds], reach, MIN_GAP_SHARE * em)
    return halo, contour


def font_key(package):
    return package.path or u"unsaved:%s" % package.tfn


def analyze(package, master, characters=None, em=EM_PIXELS, progress=None, core=None, cache_file=None, script="latin",
            adjustments=None, pairs=None):
    """Suggestions by both methods for every pair of the characters (the script's by default: Latin's
    letters, figures, and punctuation) the font has, each method's factors fitted to its existing
    kerning; only the pairs in pairs (strings of two characters) when given. adjustments {glyph name:
    (x placement, x advance)} set the glyphs as a feature does (kana as palt sets them). Pairs whose
    glyphs are unchanged since the last analysis (the cache of this font's master and script) are not
    measured again; every pair is when a reference glyph changed. progress(done, total) may return
    False to stop."""
    glyphs = FontLabGlyphs(package, master, em, adjustments)
    chars = [(ch, name) for ch, name in font_glyphs(package, characters or script_characters(script)) if glyphs.add(name)]
    names = dict(chars)
    tuning = SCRIPT_TUNING[script]
    missing = [ch for ch in tuning if ch not in names]
    if missing:
        raise ValueError(missing_references(package, tuning, missing, u"Auto Kerning", u"their spacing sets the kerning"))
    reference_names = sorted(set(names[ch] for chars_ in SCRIPT_REFERENCES[script].values() for ch in chars_ if ch in names))
    references_signature = u" ".join(glyphs.signatures[n] for n in reference_names) + u" upm %s" % glyphs.upm
    cache_file = cache_file if cache_file is not None else cache_path(font_key(package), master, script)
    model = learned_model()
    if script not in learned_scripts(model):
        model = None  # trained on other scripts: its values here would be guesses
    old = load_cache(cache_file) or {}
    valid = old.get("method") == method_fingerprint(model, script) and old.get("references") == references_signature
    old_signatures = old.get("signatures", {}) if valid else {}
    old_pairs = old.get("pairs", {}) if valid else {}
    measuring = {}  # made only when a pair must be measured

    def tools():
        if not measuring:
            measuring.update(make_bands(core or Core(), lambda ch: glyphs.image(names[ch]), names, em, glyphs.pad, script))
            if model is not None:
                measuring["spacing"] = font_spacing(measuring["core"], lambda ch: glyphs.image(names[ch]) if ch in names else None,
                                                    em, script)
        return measuring

    reach = float(glyphs.pad)
    kerning = FontKerning(package.kerning(master))
    suggestions, total, done, measured, reused = [], len(chars) * len(chars), 0, 0, 0
    wanted = set(pairs) if pairs is not None else None
    cached = {}  # (not pairs: that names the pairs asked for)
    for left_char, left in chars:
        for right_char, right in chars:
            done += 1
            if progress is not None and done % 200 == 0 and progress(done, total) is False:
                return None
            kinds = pair_kinds(left_char, right_char)
            if kinds is None or (wanted is not None and left_char + right_char not in wanted):
                continue
            key = u"%s %s" % (left, right)
            entry = old_pairs.get(key)
            fresh = (entry is not None and old_signatures.get(left) == glyphs.signatures[left]
                     and old_signatures.get(right) == glyphs.signatures[right])
            if fresh:
                reused += 1
                entry = list(entry) + [None] * (4 - len(entry))
            else:
                t = tools()
                left_glyph, right_glyph = glyphs.image(left), glyphs.image(right)
                halo, contour = measure_pair(t, left_char, right_char, left_glyph, right_glyph, em, reach)
                learned = None
                if model is not None:
                    features = pair_features(t["core"], left_char, right_char, left_glyph, right_glyph, em, t["spacing"],
                                             halo, contour)
                    learned = predict(model, features) * glyphs.upm
                entry = [None if halo is None else halo * glyphs.upm / em,
                         None if contour is None else contour * glyphs.upm / em, None, learned]
                measured += 1
            cached[key] = entry
            s = Suggestion(left_char, right_char, left, right, 0)
            s.current = kerning.current(*s.key)  # (a right-to-left pair's kerning is kept in text order)
            for method, units in ((MEASURED[0], entry[0]), (MEASURED[1], entry[1]), (MEASURED[2], entry[3])):
                if units is not None:
                    s.raw[method] = units
            if entry[2] is not None:
                s.values["fontlab"] = entry[2]
            if s.raw:
                suggestions.append(s)
    factors = {}
    for method in MEASURED:
        samples = [(s.raw[method], s.current) for s in suggestions if s.current and method in s.raw]
        factors[method] = fit_factors(samples, DEFAULT_FACTORS[method])
        tighten, loosen = factors[method]
        for s in suggestions:
            if method in s.raw:
                units = s.raw[method]
                s.values[method] = round_units(units * (tighten if units < 0 else loosen))
    cache = {"method": method_fingerprint(model, script), "references": references_signature,
             "signatures": dict((name, glyphs.signatures[name]) for _, name in chars), "pairs": cached}
    if cache_file:
        save_cache(cache_file, cache)
    return Analysis(suggestions, factors, (measuring.get("halo"), measuring.get("contour")), measured, reused,
                    cache, cache_file)


# ---------------------------------------------------------------------------
# Suggested kerning classes
# ---------------------------------------------------------------------------

CLASS_MODEL_FILE = "class_model.json"  # beside this script: kerning/train/classes.py counts it from the corpus
MERGE_RATE = 0.5  # two base letters may share a class when at least this share of the corpus's families class them so
CLASS_SIDES_LABELS = {"first": "First in a pair (the glyph's right side)", "second": "Second in a pair (the glyph's left side)"}
CLASS_FLAGS = {"first": "KernLeft", "second": "KernRight"}  # FontLab's flags: KernLeft classes come first in pairs
CLASS_PREFIX = {"first": "kern1_", "second": "kern2_"}
CLASS_COLUMNS = ("Class", "Glyphs", "Outcome", "May need pairs of their own")
CLASS_EXCEPTIONS_LABEL = "Pairs too close with their class's value (each given a value of its own when written)"
EXCEPTION_ROLE_BASE = 100000  # a row's data at or above this: a pair too close (its index above it), not a class

_CLASS_MODEL = {}


def class_model(path=None):
    """{side: {(a, b): share of families classing them together}} from class_model.json, or None."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(globals().get("__file__") or ".")), CLASS_MODEL_FILE)
    if path not in _CLASS_MODEL:
        import io
        import json
        try:
            with io.open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            model = None
            if data.get("format") == 1:
                model = {}
                for side, rows in data["sides"].items():
                    rates = model[side] = {}
                    for pair, together, apart in rows:
                        if together + apart <= 0:
                            continue
                        rates[(pair[0], pair[1])] = rates[(pair[1], pair[0])] = together / float(together + apart)
            _CLASS_MODEL[path] = model
        except (IOError, OSError, ValueError, KeyError, TypeError):
            _CLASS_MODEL[path] = None
    return _CLASS_MODEL[path]


def class_characters():
    """The characters classes are suggested for: Latin letters to Latin Extended-B, figures, punctuation."""
    import unicodedata
    letters = [unichr_(code) for code in range(0x41, 0x250) if unicodedata.category(unichr_(code)).startswith("L")]
    return letters + [ch for ch in FIGURES + PUNCTUATION]


def unichr_(code):
    """A code point's character; the replacement character past U+FFFF on a narrow Python 2 (FontLab
    7's), which has none of them as one character."""
    try:
        return unichr(code)  # noqa: F821 (Python 2)
    except NameError:
        return chr(code)
    except ValueError:
        return u"\N{REPLACEMENT CHARACTER}"


def glyph_codes(fg):
    """A fontgate glyph's code points: its unicodes, else its unicode. A glyph may be encoded at several:
    a CJK font encodes 日 at the Kangxi radical U+2F47 and at U+65E5, and FontLab's unicode gives the
    radical first (IBM Plex Sans JP: 日 月 玄 黄 辰), so a map of characters to glyphs built from unicode
    alone lost the ideographs."""
    try:
        codes = [int(code) for code in (fg.unicodes or []) if code]
    except Exception:
        codes = []
    if not codes:
        try:
            codes = [int(fg.unicode)] if fg.unicode else []
        except Exception:
            codes = []
    return codes


def glyph_code_map(glyphs):
    """{code point: glyph name} of every code point of each glyph (the first glyph at a code point wins, as
    in a cmap)."""
    found = {}
    for fg in glyphs:
        for code in glyph_codes(fg):
            found.setdefault(code, u"%s" % fg.name)
    return found


# Where a CJK font encodes a glyph a second time, as a radical or a compatibility form of the ideograph:
# not the character a glyph stands for when one code point is wanted
DUPLICATE_RANGES = ((0x2E80, 0x2EFF), (0x2F00, 0x2FDF), (0xF900, 0xFAFF), (0x2F800, 0x2FA1F))


def main_code(fg):
    """The one code point a glyph stands for: the first of its code points that is not a radical or a
    compatibility duplicate (DUPLICATE_RANGES), else the first; None for an unencoded glyph."""
    codes = glyph_codes(fg)
    for code in codes:
        if not any(low <= code <= high for low, high in DUPLICATE_RANGES):
            return code
    return codes[0] if codes else None


def base_letter(ch):
    """The letter a character is built on (A for À, L for Ŀ), or the character itself."""
    import unicodedata
    decomposed = unicodedata.normalize("NFKD", ch)
    return decomposed[0] if decomposed and decomposed[0].isalpha() and ch.isalpha() else ch


SIGNATURE_PARTNERS = {"first": u"HOonvTAy.", "second": u"HOonvTLrf"}  # what a side is kerned against, as seen beside it
SIGNATURE_TOLERANCE = 0.02  # two sides kern alike when every partner's kerning differs by at most this share of the em
SIGNATURE_MIN = 3  # partners both sides need, measured, to be compared
DIFFERS_NOTE = 0.03  # a member kerning this much differently from its class's first glyph is named (an exception may be due)


def kind_character(ch):
    """The character whose kind (capital, lowercase, figure) sets a pair's references: its base letter;
    for a letter of another script Auto Kerning measures, its script's straight control of its case
    (RO for kana, Armenian's vo, Georgian's in, Cyrillic's en, Greek's eta, Devanagari's na)."""
    base = base_letter(ch)
    if base in LETTERS + FIGURES:
        return base
    script = script_of(ch)
    if script in SCRIPT_PROOF:
        controls = SCRIPT_CONTROLS[script]
        return controls[2] if category(ch) in ("upper", "kana") else controls[0]
    if ch.isalpha():  # a letter of its own (o with stroke, dotless i): its case's references
        return u"H" if ch.isupper() else u"n"
    return ch


def side_signature(tools, image_of, names, ch, side, em, reach):
    """How a side kerns: for each partner of SIGNATURE_PARTNERS the font has, the average of halfkern's
    and contour distance's raw kerning of the pair (the side facing the partner), as a share of the em;
    None where neither measures it."""
    found = []
    for partner in SIGNATURE_PARTNERS[side]:
        if partner not in names:
            found.append(None)
            continue
        left, right = (ch, partner) if side == "first" else (partner, ch)
        if pair_kinds(kind_character(left), kind_character(right)) is None:
            found.append(None)
            continue
        halo, contour = measure_pair(tools, kind_character(left), kind_character(right), image_of(left), image_of(right),
                                     em, reach)
        values = [v for v in (halo, contour) if v is not None]
        found.append(sum(values) / len(values) / float(em) if values else None)
    return found


def signature_gap(one, other):
    """The largest difference between two signatures' measured partners, or None with too few."""
    both = [abs(a - b) for a, b in zip(one or [], other or []) if a is not None and b is not None]
    return max(both) if len(both) >= SIGNATURE_MIN else None


def loosest_difference(one, other):
    """(other minus one, partner index) where other kerns loosest next to one (its accent or part reaching
    toward that partner), or None with too few partners. Where other measures tighter, the methods read
    air beside an accent the partner does not reach (an accent above T's bar): a class value leaves
    that pair a little loose, never colliding, so it is not counted."""
    both = [(b - a, index) for index, (a, b) in enumerate(zip(one or [], other or [])) if a is not None and b is not None]
    if len(both) < SIGNATURE_MIN:
        return None
    return max(both, key=lambda found: (found[0], -found[1]))


def signatures_match(one, other, tolerance=SIGNATURE_TOLERANCE):
    gap = signature_gap(one, other)
    return gap is not None and gap <= tolerance


def suggest_classes(names, signature_of, model):
    """{side: [[character, ...], ...]} classes for the characters of names ({character: glyph name}).
    An accented letter joins its base where most of the corpus's families class the two together on
    that side (model, from class_model), or, for a pair the corpus has not seen, where the two kern
    alike in this font. Base letters share a class where most families class them so and every two
    of them kern alike here. signature_of(character, side) gives a side_signature, or None."""
    result = {}
    for side in ("first", "second"):
        signatures = {}

        def signature(ch):
            if ch not in signatures:
                signatures[ch] = signature_of(ch, side)
            return signatures[ch]

        rates = (model or {}).get(side, {})
        groups, loners = {}, set()  # base: [members]; letters kept apart from their base
        for ch in sorted(names):
            base = base_letter(ch)
            if base == ch or base not in names:
                groups.setdefault(ch, [ch])
                continue
            rate = rates.get((base, ch))
            joins = rate >= MERGE_RATE if rate is not None else signatures_match(signature(base), signature(ch))
            if joins:
                groups.setdefault(base, [base]).append(ch)
            else:
                groups[ch] = [ch]
                loners.add(ch)
        bases = sorted(b for b in groups if b not in loners)
        candidates = sorted(((rates.get((a, b), 0.0), a, b) for i, a in enumerate(bases) for b in bases[i + 1:]
                             if rates.get((a, b), 0.0) >= MERGE_RATE), reverse=True)
        joined = dict((base, [base]) for base in groups)  # base: the bases of its class (one shared list)
        for rate, a, b in candidates:
            if joined[a] is joined[b]:
                continue
            together = joined[a] + joined[b]
            if all(signatures_match(signature(x), signature(y)) for i, x in enumerate(together) for y in together[i + 1:]):
                for base in together:
                    joined[base] = together
        classes, seen = [], set()
        for base in sorted(groups):
            key = id(joined[base])
            if key in seen:
                continue
            seen.add(key)
            members = []
            for member_base in sorted(joined[base], key=lambda b: (b not in LETTERS, b)):
                members.extend(groups[member_base])
            if len(members) > 1:
                classes.append(members)
        result[side] = classes
    return result


class ClassPlan(object):
    """One suggested class against the font's classes: action "new" (a class to make), "add" (glyphs
    to add to an existing class), "same" (the font has it), or "overlap" (members in several classes,
    or a class that kerns both sides: left as it is)."""

    def __init__(self, side, members, names, kerning, differs=None):
        self.side, self.members = side, members
        self.differs = differs or []  # (character, units, partner): members kerning unlike the first one (units
        # below zero: the member kerns that much tighter than the first one beside the partner)
        self.glyphs = [names[ch] for ch in members]
        lookup = kerning.left_class if side == "first" else kerning.right_class
        found = sorted(set(lookup[g] for g in self.glyphs if g in lookup))
        self.existing, self.adding = None, []
        self.name = None
        if not found:
            self.action = "new"
            self.name = class_name(kerning, CLASS_PREFIX[side] + self.glyphs[0])
            self.adding = list(self.glyphs)
        elif len(found) > 1:
            self.action, self.reason = "overlap", u"its glyphs are in %d classes: %s" % (len(found), u", ".join(found))
            self.existing = found
        else:
            self.existing = found[0]
            self.adding = [g for g in self.glyphs if g not in kerning.members.get(self.existing, [])]
            if not self.adding:
                self.action = "same"
            elif kerning.class_flags.get(self.existing) == "KernBothSide":
                self.action, self.reason = "overlap", u"class %s kerns both sides" % self.existing
            else:
                self.action = "add"

    def describe(self):
        text = self.describe_action()
        if self.differs:
            text += u" (may need pairs of their own: %s)" % self.describe_differs()
        return text

    def pair_text(self, ch, partner):
        """The member and its partner as a pair, shown as a reader sees it: the side says its order in
        the font's kerning, which is text order (a right-to-left pair's right glyph first)."""
        first, second = (ch, partner) if self.side == "first" else (partner, ch)
        return pair_label(*screen_of_key(first, second, first, second))

    def describe_differs(self):
        """Each member kerning unlike the first one, as the pair where it differs most (an e acute beside
        T: "...T 52 units looser than eT")."""
        return u"; ".join(u"%s %s %s than %s" % (self.pair_text(ch, partner), counted(abs(units), u"unit"),
                                                 u"tighter" if units < 0 else u"looser",
                                                 self.pair_text(self.members[0], partner))
                          for ch, units, partner in self.differs)

    def characters(self, glyphs):
        """The characters of some of this plan's glyphs, in its order."""
        return [ch for ch, glyph in zip(self.members, self.glyphs) if glyph in glyphs]

    def columns(self):
        """(class, glyphs, what happens) as the classes dialog lists them: a cell's short note takes no
        period."""
        glyphs = u" ".join(self.members)
        if self.action == "new":
            return self.name, glyphs, u"New class"
        if self.action == "add":
            staying = [ch for ch, glyph in zip(self.members, self.glyphs) if glyph not in self.adding]
            return self.existing, u" ".join(self.characters(self.adding)), (
                u"Added to the class" + (u" (with %s)" % u" ".join(staying) if staying else u""))
        if self.action == "same":
            return self.existing, glyphs, u"Nothing: the font has this class already"
        existing = u", ".join(self.existing) if isinstance(self.existing, list) else (self.existing or u"")
        return existing, glyphs, u"Left as it is: " + self.reason.rstrip(u".")

    def key(self):
        """What this plan does, comparable across two workings-out (lists made tuples: hashable)."""
        existing = tuple(self.existing) if isinstance(self.existing, list) else self.existing
        return (self.side, tuple(self.members), self.action, self.name, existing, tuple(self.adding))

    def describe_action(self):
        glyphs = u" ".join(self.members)
        if self.action == "new":
            return u"New class %s: %s" % (self.name, glyphs)
        if self.action == "add":
            return u"Add %s to class %s" % (u" ".join(self.adding), self.existing)
        if self.action == "same":
            return u"Class %s already: %s" % (self.existing, glyphs)
        return u"%s: left as it is (%s)" % (glyphs, self.reason)


def class_name(kerning, wanted):
    name, number = wanted, 2
    while name in kerning.classes:
        name, number = u"%s%d" % (wanted, number), number + 1
    return name


def plan_classes(suggested, names, kerning, signature_of=None, upm=1000.0):
    """The suggestions against the font's classes; with signature_of, each notes the members that kern
    unlike its first glyph by DIFFERS_NOTE or more (in font units)."""
    plans = []
    for side in ("first", "second"):
        for members in suggested.get(side, []):
            differs = []
            if signature_of is not None:
                first = signature_of(members[0], side)
                for ch in members[1:]:
                    found = loosest_difference(first, signature_of(ch, side))
                    if found is not None and found[0] >= DIFFERS_NOTE:
                        differs.append((ch, int(round(found[0] * upm)), SIGNATURE_PARTNERS[side][found[1]]))
            plans.append(ClassPlan(side, members, names, kerning, differs))
    return plans


class NotedException(object):
    """A glyph pair a class's value brings too close (a noted member beside its partner), and the
    value of its own that loosens it by the measured difference."""

    def __init__(self, plan_index, pair, text, current, value):
        self.plan_index, self.pair, self.text = plan_index, pair, text
        self.current, self.value = current, value

    def entry(self):
        return ((self.pair[0], False), (self.pair[1], False))


def noted_exceptions(kerning, plans, names):
    """The noted pairs (ClassPlan.differs) that take their class's tightening now: the member kerns
    beside the partner exactly as the class's first glyph does, below zero. Each gets that value
    loosened by the measured difference, never past zero (an accent that collides unkerned is a
    matter of spacing). kerning is a FontKerning; names maps characters to glyph names."""
    found = []
    for index, plan in enumerate(plans):
        first = names.get(plan.members[0])
        for ch, units, partner in plan.differs:
            member, other = names.get(ch), names.get(partner)
            if not (first and member and other):
                continue
            pair = (member, other) if plan.side == "first" else (other, member)
            base = (first, other) if plan.side == "first" else (other, first)
            current = kerning.current(*pair)
            if current >= 0 or current != kerning.current(*base):
                continue
            value = min(0, current + units)
            if value != current:
                found.append(NotedException(index, pair, plan.pair_text(ch, partner), current, value))
    return found


def write_exceptions(kerning, exceptions):
    """Each exception as a glyph pair of its own (0 kept as an entry: it overrides the class); the
    number written."""
    written = 0
    for exception in exceptions:
        kerning.write(exception.entry(), exception.value, False)
        written += 1
    return written


def own_values(kerning, plans):
    """{(left, right): value} of the glyph pairs whose value comes from an entry naming a glyph a plan
    puts in a class: a member's own kerning, which the class's pairs must not override."""
    found = {}
    for plan in plans:
        at = 0 if plan.side == "first" else 1
        members = plan.glyphs[1:] if plan.action == "new" else plan.adding
        for member in members:
            for entry in kerning.entries:
                if entry[at] != (member, False):
                    continue
                other_name, other_is_class = entry[1 - at]
                others = kerning.members.get(other_name, []) if other_is_class else [other_name]
                for other in others:
                    pair = (member, other) if at == 0 else (other, member)
                    if kerning.resolving(*pair) == entry:
                        found[pair] = kerning.values.get(entry)
    return found


def apply_class_plans(kerning, plans, move_base_kerning=True):
    """Make the "new" classes and extend the "add" ones (kerning: a FontKerning). With
    move_base_kerning, a new class takes over the explicit pairs of its first glyph on its side (its
    members then share them); they are removed from that glyph. A member whose own entry set a pair
    that a class entry would now override gets that value back as a glyph pair. Returns (classes
    made, extended, pairs moved, own values kept)."""
    made = extended = moved = 0
    own = own_values(kerning, plans)
    groups = kerning.kerning.groups
    for plan in plans:
        if plan.action == "new":
            groups[plan.name] = (list(plan.glyphs), CLASS_FLAGS[plan.side])
            kerning.classes.add(plan.name)
            kerning.members[plan.name] = list(plan.glyphs)
            kerning.class_flags[plan.name] = CLASS_FLAGS[plan.side]
            made += 1
            if move_base_kerning:
                base = (plan.glyphs[0], False)
                at = 0 if plan.side == "first" else 1
                for entry in sorted(e for e in kerning.entries if e[at] == base):
                    value = kerning.values.get(entry)
                    if value is None:
                        continue
                    moved_to = ((plan.name, True), entry[1]) if at == 0 else (entry[0], (plan.name, True))
                    if moved_to in kerning.entries:
                        continue
                    kerning.write(moved_to, value, False)
                    kerning.values[moved_to] = value
                    kerning.write(entry, 0, True)
                    kerning.values.pop(entry, None)
                    moved += 1
        elif plan.action == "add":
            members = kerning.members[plan.existing] + [g for g in plan.adding if g not in kerning.members[plan.existing]]
            groups[plan.existing] = (members, kerning.class_flags[plan.existing])
            kerning.members[plan.existing] = members
            extended += 1
    after = FontKerning(kerning.kerning)
    kept = 0
    for (left, right), value in sorted(own.items()):
        if value is not None and after.current(left, right) != round_units(value):
            after.write(((left, False), (right, False)), value, False)
            kept += 1
    return made, extended, moved, kept


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

# The preview's choices, a button each: clicking one picks it for the selected pair alone. Its
# number picks it from the keyboard while the list has the focus.
CHOICES = (("current", "Now"), ("average", "Average"), ("halfkern", "halfkern"), ("contour", "Contour"),
           ("learned", "FreeLab"), ("fontlab", "FontLab"))
LEAVE_ALONE_PROP = "freelabLeaveAlone"  # dark mode leaves the preview's pictures as they are drawn
# The pair's choice, plain to see: framed in the highlight color, on a light tint of it (a frame alone
# looked much like the dashed frame of a method with no value for the pair: flat, nothing to click)
CHOICE_SHEET = (u"QToolButton:checked { background: rgba(%d, %d, %d, %d); border: 2px solid palette(highlight); "
                u"border-radius: 3px; } "
                u"QToolButton:disabled { background: transparent; border: 1px dashed rgba(128, 128, 128, 90); border-radius: 3px; }")
CHOSEN_ALPHA = 60  # the chosen button's tint: the highlight color this opaque, over a light or a dark window


def choice_sheet(palette):
    """CHOICE_SHEET in this palette's highlight color (a stylesheet's rgba takes no palette role)."""
    QtGui = _qt()[1]
    try:
        color = palette.color(QtGui.QPalette.Highlight)
        rgb = (color.red(), color.green(), color.blue())
    except Exception:
        rgb = (0, 120, 215)  # (Windows' highlight)
    return CHOICE_SHEET % (rgb + (CHOSEN_ALPHA,))
UNAVAILABLE_ALPHA = 90  # the name of a method with no value for the pair, this opaque
PREVIEW_TEXT_WIDTH = 92  # pixels beside a preview's glyphs for its method and value
PICKED_ALPHA = 70  # the tint of a row whose value was picked by hand: the highlight color, this opaque
# A cell of a row picked by hand (Qt.UserRole + 78): its tint is painted by the list's delegate, from the palette
# as it is drawn (the list's stylesheet item rule hides BackgroundRole, and a brush set once kept the old palette)
PICKED_ROLE = 0x0100 + 78
SIDE_ALPHA = 110  # the H's on either side of a preview's pair, dimmed: the pair is what to look at
RELATED_SHOWN = 30  # glyph pairs named under the preview's note; the rest are counted, all in its tooltip
PICKED_ROOM = 8888  # the widest count the "picked by hand" filter keeps room for
PALETTE_EVENTS = (38, 39)  # QEvent ApplicationPaletteChange, PaletteChange: dark mode switched
COLUMN_CHOICES = {1: "current", 2: "halfkern", 3: "contour", 4: "learned", 5: "fontlab"}  # double-clicked cells

HELP = u"""<b>FreeLab Auto Kerning</b><br>
Suggests kerning for the font's pairs, one script at a time (Latin, Cyrillic, Greek, Armenian, Georgian, Devanagari, kana,
Hebrew, and Thaana: the <i>Script</i> list offers those the font has, and <i>All scripts</i>, each against its own references,
in one list), and writes only the pairs you check. Kana are kerned as
the font's palt sets them, on top of it. Hebrew and Thaana pairs are listed as read, right to left, measured and drawn as
they stand on screen, and read and written in text order, the right glyph first, as FontLab 7 keeps them.<br><br>
<b>The list</b>: each method's value beside the font's current one. Check the pairs to write;
pairs the font kerns already start unchecked.<br>
<b>Choosing a value for one pair</b>: click a preview below the list, double-click a value in the
list, or press <i>Ctrl</i> and its number (1 Now, 2 Average, 3 halfkern, 4 Contour, 5 FreeLab, 6 FontLab)
while the list has the focus. A pair picked by hand is tinted; <i>Backspace</i> or <i>Reset pair</i> gives it the
suggested value again. <i>Restore suggestions</i> puts every check and pick back as the list first came.<br>
<b>Keys in the list</b>: arrows move, a letter jumps to the pairs starting with it, <i>Space</i> checks or
unchecks the pair, <i>Ctrl+1</i> to <i>Ctrl+6</i> pick, <i>Backspace</i> resets.<br>
<b>The H's around a pair</b> (the script's own straight letter past Latin): double-click one, in any
preview, to go to its pair with the pair's glyph beside it (H and T for HTo); a single click there does nothing.<br>
<b>The pair's name</b>: double-click it to open the pair in a <i>Glyph</i> window.<br>
<b>Kerning classes</b>: a pair is written where its value comes from: its own pair, or else its
classes' pair, which kerns every glyph of both classes. The line under the list says which.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""


class AutoKerningDialog(object):
    COLUMNS = ("Pair", "Current", "halfkern", "Contour", "FreeLab", "FontLab", "Spread", "Suggested")
    NUMBERS = (1, 2, 3, 4, 5, 6, 7)  # the columns of numbers: right-aligned, their headers too

    def __init__(self):
        QtCore, QtGui = _qt()
        import fontlab
        self.fontlab = fontlab
        self.package = self.current_font()
        self.master = self.package.master if self.package is not None else None
        self.analysis, self.suggestions, self.stop, self.selected = None, [], False, None
        self.font_kerning, self.kerning_read = None, 0.0
        self.busy = self.refilter_again = False
        self.common = common_pairs()
        self.script, self.adjustments, self.side = "latin", {}, u"H"  # the script analyzed, palt's adjustments, the preview's sides
        self.sides = {}  # the preview's sides by script (All scripts: each pair between its own script's)
        # FontLab's main window as its parent: a parentless dialog counts as a main window of its own,
        # and kept FontLab running, the dialog alone on screen, after FontLab's window was closed
        # (take_window then makes it a window of its own that does not: _own_window, hook_quit).
        dialog = self.dialog = QtGui.QDialog(self.main_window()) if self.main_window() is not None else QtGui.QDialog()
        dialog.setWindowTitle("FreeLab Auto Kerning")
        dialog.setWhatsThis(HELP)
        size_dialog(dialog)
        layout = window_layout(dialog)  # (its content scrolls on a small screen)
        self.status = status_label(self.font_line())
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(header_separator())
        self.log = Log()
        # (the pairs a line names drawn as the font draws them; a glyph clicked opens in a Glyph window)
        self.log.follow(lambda: (self.fontlab, self.package, self.master))
        self.seen_history, self.first_pass, self.pinned = None, True, set()
        # Two rows of options (owner's images 222, 262, 271, 272): what Analyze measures, ending with it
        # (a tool's run button follows the options it reads, never pushed to the window's right edge), then
        # how the list shows what was measured. Captions: "Noun: [choice]", or a sentence the controls
        # finish, with its period.
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Script:"))
        self.script_box = QtGui.QComboBox()
        self.script_keys = ["latin"]
        self.script_box.addItem(dict(SCRIPTS)["latin"])
        self.script_box.setWhatsThis(u"The script whose pairs are measured and listed: those the font has (its letters "
                                     u"and the letters its spacing is measured by). Kana are measured as the font's palt "
                                     u"sets them (or as they are, when they are proportional already). <i>All scripts</i> "
                                     u"(for a font with two or more) analyzes each, against its own references, and lists "
                                     u"their pairs together: a pair's glyphs show its script, and its tooltip names it.")
        row.addWidget(self.script_box)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Show:"))
        self.show_kind = self.combo(SHOW)
        self.show_kind.setWhatsThis("Which glyphs' pairs are listed.")
        row.addWidget(self.show_kind)
        self.pairs = self.combo(PAIRS)
        self.pairs.setToolTip("<i>Common pairs</i>: frequent in the text of 24 languages and kerned in fonts "
                              "(andre-fuchs/kerning-pairs), worth kerning even in a font kerned in part.")
        self.pairs.setWhatsThis("All pairs, or only the pairs frequent in text and usually kerned.")
        if not self.common:
            self.pairs.setEnabled(False)
        row.addWidget(self.pairs)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("List changes of at least"))
        self.tolerance = QtGui.QSpinBox()
        self.tolerance.setRange(1, 200)
        self.tolerance.setValue(TOLERANCE_UNITS)
        self.suffix_slot = counted_suffix(self.tolerance, u"unit")  # ("1 unit", "2 units")
        self.tolerance.setWhatsThis("A pair is listed when a method would change its kerning by at least this much.")
        row.addWidget(self.tolerance)
        sentence_end(row)
        row.addSpacing(12)
        self.analyze_button = QtGui.QPushButton("Analyze")
        self.analyze_button.setWhatsThis("Measures the font's current master again. Pairs whose glyphs have not "
                                         "changed since the last analysis are not measured again.")
        row.addWidget(self.analyze_button)
        row.addStretch(1)
        layout.addLayout(row)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel("Suggested values:"))
        self.source = self.combo(SOURCES)
        self.source.setWhatsThis("The method whose values fill the Suggested column and are written, for every "
                                 "pair not picked by hand. Changing it does not change the list.")
        row.addWidget(self.source)
        row.addSpacing(12)
        row.addWidget(QtGui.QLabel("Order:"))
        self.order = self.combo(ORDERS)
        self.order.setWhatsThis("The order of the list.")
        row.addWidget(self.order)
        row.addSpacing(12)
        # Pairs the font kerns already are the designer's choices (a j tucked under the letter before
        # it, which the methods do not model): hidden unless asked for, and never checked for writing.
        self.include_kerned = QtGui.QCheckBox("Include existing kerned pairs.")
        self.include_kerned.setWhatsThis("Also lists the pairs the font kerns already, through its classes too, "
                                          "and the pairs written here since. They start unticked.")
        row.addWidget(self.include_kerned)
        self.only_picked = QtGui.QCheckBox(u"List only pairs picked by hand (%d)." % PICKED_ROOM)
        self.only_picked.setWhatsThis("Lists only the pairs whose value you picked yourself.")
        # Its room is kept from the start, so the window does not grow when the first pair is picked
        self.only_picked.setMinimumWidth(_property(self.only_picked, "sizeHint").width())
        self.picked_room_kept = _keep_room_when_hidden(self.only_picked)
        row.addWidget(self.only_picked)
        row.addStretch(1)
        layout.addLayout(row)
        # The list, laid out as the other tools' lists (a tree of plain rows, the pair drawn from the font at
        # the value it takes beside its characters, the numbers right-aligned): a table's header, its own
        # sections drawn by the style and mapped by dark mode, looked washed out in dark mode
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(self.COLUMNS))
        self.tree.setHeaderLabels(list(self.COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)  # (rows of one height: a long list scrolls without measuring each)
        self.tree.setIconSize(QtCore.QSize(*glyph_icon_size(2)))
        self.tree.setProperty(LEAVE_ALONE_PROP, True)  # its pictures are drawn in the dialog's colors
        self.tree.setWhatsThis(u"The pairs, each drawn at the value it takes, each method's value, and the value to "
                               u"write (Suggested). Double-click a value to use it for that pair, or press <i>Ctrl+1</i> "
                               u"to <i>Ctrl+6</i>; <i>Space</i> ticks the pair; <i>Backspace</i> gives it the suggested "
                               u"value again. Double-click a pair to open it in a <i>Glyph</i> window.")
        table_layout(self.tree, stretch=0)  # (the pairs take the room the numbers leave)
        layout.addWidget(self.tree, 1)
        self.icon_cache = {}  # (left, right, value, color): the pair's picture, drawn once
        note_row = QtGui.QHBoxLayout()
        self.preview_note = QtGui.QLabel("Select a pair to compare the methods; click one to use it for that pair.")
        self.preview_note.setWordWrap(True)
        self.preview_note.setVisible(False)  # (shown once pairs are listed: hint_shown)
        note_row.addWidget(self.preview_note, 1)
        self.reset_button = QtGui.QPushButton("Reset pair")
        self.reset_button.setToolTip("Give this pair the suggested value again.")
        self.reset_button.setWhatsThis("Gives the selected pair the value of the source chosen above, undoing a pick.")
        self.reset_button.setEnabled(False)
        self.glyph_window_button = QtGui.QPushButton(u"Show in Glyph window")
        self.glyph_window_button.setWhatsThis(u"Opens the selected pair in a <i>Glyph</i> window, between H's, n's, and o's, "
                                              u"to look at it (and edit it) with FontLab's own tools.")
        self.glyph_window_button.setEnabled(False)
        layout.addLayout(note_row)  # (the pair's buttons in the bottom row, with the others acting on the list)
        self.related = QtGui.QLabel(u"")
        self.related.setWordWrap(True)
        self.related.setWhatsThis("The glyph pairs the selected pair's entry kerns: writing it changes all of them.")
        self.related.setVisible(False)
        layout.addWidget(self.related)
        grid = QtGui.QGridLayout()
        self.choice_group = QtGui.QButtonGroup(dialog)
        self.choice_buttons = {}
        for number, (key, label) in enumerate(CHOICES):
            button = QtGui.QToolButton()
            button.setCheckable(True)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)  # its method and value are in its picture
            button.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
            button.setProperty(LEAVE_ALONE_PROP, True)
            button.setStyleSheet(choice_sheet(dialog.palette))
            button.setToolTip(u"%s: click to use it for this pair (<i>Ctrl+%d</i> in the list)." % (html(label), number + 1))
            button.setWhatsThis(u"The pair as %s sets it, between two H's. Click to use it for this pair." % label)
            button.setEnabled(False)
            self.choice_group.addButton(button, number)
            self.choice_buttons[key] = button
            grid.addWidget(button, number // 2, number % 2)
            _keep_room_when_hidden(button)  # drawn once a pair is selected
        self.neighbors = dict((key, ClickRegions(button, self.focus_neighbor,
                                                 u"Double-click to go to this H's pair with the glyph beside it."))
                              for key, button in self.choice_buttons.items())
        layout.addLayout(grid)
        layout.addWidget(self.log.widget)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Tick new pairs")
        self.all_button.setWhatsThis("Ticks every listed pair the font does not kern yet.")
        self.none_button = QtGui.QPushButton("Tick none")
        self.restore_button = QtGui.QPushButton("Restore suggestions")
        self.restore_button.setWhatsThis("Puts every tick and every value picked by hand back as the list first "
                                         "came, after the last analysis.")
        self.classes_button = QtGui.QPushButton(u"Suggest classes…")
        self.classes_button.setWhatsThis("Suggests kerning classes for this master, from the open-licensed fonts FreeLab "
                                         "learned from and this font's own outlines, to review before any is made.")
        self.class_dialog = None
        self.check_button = QtGui.QPushButton(u"Check kerning…")
        self.check_button.setWhatsThis(u"Opens <i>Kerning Check</i>: pairs whose kerning makes them collide, entries that "
                                       u"do nothing or name what is gone, and differences between masters.")
        self.apply_button = QtGui.QPushButton("Write ticked pairs")
        self.apply_button.setWhatsThis("Writes the Suggested value of every ticked pair to the current master, "
                                       "where the pair's value comes from: see Kerning classes in the help.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button, self.restore_button, self.reset_button,
                       self.glyph_window_button, self.classes_button, self.check_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.apply_button.setEnabled(False)
        self.analyze_button.connect("clicked()", self.run)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.restore_button.connect("clicked()", self.restore)
        self.buttons_due = False
        self.tree.connect("itemChanged(QTreeWidgetItem*,int)", lambda item, column: self.update_buttons_soon())
        self.apply_button.connect("clicked()", self.write)
        self.classes_button.connect("clicked()", self.suggest_classes)
        self.close_button.connect("clicked()", close_slot(self))  # (never the window itself: see let_go)
        self.reset_button.connect("clicked()", self.reset)
        self.glyph_window_button.connect("clicked()", self.show_in_glyph_window)
        self.check_button.connect("clicked()", self.open_kerning_check)
        self.tree.connect("itemSelectionChanged()", self.select)
        self.tree.connect("itemDoubleClicked(QTreeWidgetItem*,int)", self.item_double_clicked)
        for widget in (self.show_kind, self.pairs, self.order):
            widget.connect("currentIndexChanged(int)", lambda index: self.refilter())
        self.script_box.connect("activated(int)", lambda index: self.run())  # (by the user: refilling it starts nothing)
        self.tolerance.connect("valueChanged(int)", lambda value: self.refilter())
        self.include_kerned.connect("toggled(bool)", lambda on: self.refilter())
        self.only_picked.connect("toggled(bool)", lambda on: self.refilter())
        self.source.connect("currentIndexChanged(int)", lambda index: self.refresh_values())  # the list stays as it is
        self.choice_group.connect("buttonClicked(int)", lambda number: self.choose(CHOICES[number][0]))
        self.keys = self.make_keys()
        # (no palette watcher of its own: FreeLab's shared mechanism calls theme_changed when dark mode switches)
        self.history_timer = watch_history(self)
        self.flagging = flag_menu(self.tree, self, lambda: [self.suggestions[self.selected].left,
                                                             self.suggestions[self.selected].right]
                                  if self.selected is not None else [],
                                  lambda item: self.names_of_row(self.row_of(item)))
        self.tint = self.tint_rows()  # after the flags' delegate, which it takes over (one delegate per cell)
        self.focus = None  # a pair to go to once the analysis is done (opened from another script)
        add_tools_button(dialog, "Auto Kerning", getattr(self, "log", None))  # (the other font tools, a click away)
        plain_buttons(dialog)
        self.update_buttons()

    def suggest_classes(self):
        if self.class_dialog is None:
            self.class_dialog = ClassDialog(self)  # kept: PythonQt deletes a dialog with no Python reference
        self.class_dialog.show()

    def show_in_glyph_window(self):
        if self.selected is None or self.package is None:
            return
        s = self.suggestions[self.selected]
        # (in the font's key order: FontLab 7 sets typed Hebrew left to right and kerns it by that key)
        error = show_in_glyph_window(self.fontlab, proof_text(s.key[0], s.key[1], proof_contexts(self.package, list(s.key))))
        if error:
            self.log.add(u"FontLab did not open the pair: %s" % html(error), "error")

    def open_kerning_check(self):
        """Kerning Check, the script beside this one, on the same font."""
        error = open_sibling_script(KERNING_CHECK_FILE, KERNING_CHECK_MODULE, caller=self.dialog)
        if error:
            self.log.add(u"<i>Kerning Check</i> did not open: %s" % html(error), "error")

    def make_keys(self):
        """The list's keys: Ctrl+1 to Ctrl+6 pick (a plain number or letter jumps to the pairs starting
        with it, as in any list), Backspace resets, Space checks. Only while the list has the focus."""
        QtCore, QtGui = _qt()
        made = []
        try:
            actions = [("Ctrl+%d" % (number + 1), (lambda key=key: self.choose(key))) for number, (key, _) in enumerate(CHOICES)]
            actions += [("Backspace", self.reset), ("Delete", self.reset), ("Space", self.toggle_check)]
            for sequence, action in actions:
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(sequence), self.tree)
                shortcut.setContext(QtCore.Qt.WidgetShortcut)
                shortcut.connect("activated()", action)
                made.append(shortcut)  # kept: PythonQt deletes what Python no longer holds
        except Exception:
            pass  # no shortcuts: the buttons and double-clicks still work
        return made

    # -- the list's rows: read from the list each time (an item kept across events may be deleted) ------

    def row_count(self):
        return _property(self.tree, "topLevelItemCount")

    def row_item(self, row):
        """The list's row number row (its suggestion's index in self.suggestions), or None."""
        if row is None or not 0 <= row < self.row_count():
            return None
        return self.tree.topLevelItem(row)

    @staticmethod
    def row_of(item):
        """The row number an item holds (its suggestion's index), or None."""
        QtCore = _qt()[0]
        try:
            return int(item.data(0, QtCore.Qt.UserRole))
        except Exception:
            return None

    def names_of_row(self, row):
        """A row's glyphs' names, as on screen (the flags' tints)."""
        if row is None or not 0 <= row < len(self.suggestions):
            return []
        return [self.suggestions[row].left, self.suggestions[row].right]

    def clear_list(self):
        self.tree.clear()
        self.hint_shown()

    def hint_shown(self):
        """The preview's hint ("Select a pair...") only while pairs are listed and none is selected: with
        none listed, there is nothing to select (owner's image 187)."""
        try:
            if self.selected_row() is None:
                self.preview_note.setVisible(bool(self.suggestions))
        except Exception:
            pass

    def tint_rows(self):
        """The list's delegate: a row picked by hand tinted (PICKED_ROLE) in the highlight color of the
        palette it is drawn with, so that it follows a dark mode switch, and in the pair's column the
        flags of its glyphs (FLAG_ROLE, see FlagMenu, whose delegate for that column it replaces: a cell
        takes one delegate). The delegate, kept, or None where PythonQt could not make it (no tints)."""
        QtCore, QtGui = _qt()
        picked_role, picked_alpha, highlight = PICKED_ROLE, PICKED_ALPHA, QtGui.QPalette.Highlight
        role, bar, tint, segments = FLAG_ROLE, FLAG_BAR, FLAG_TINT, flag_segments  # (held: a dropped module's globals turn None)

        class Tint(QtGui.QStyledItemDelegate):
            def paint(self, painter, option, index):
                parts = []
                try:
                    rect = option.rect
                    if index.data(picked_role):
                        color = QtGui.QColor(option.palette.color(highlight))
                        color.setAlpha(picked_alpha)
                        painter.fillRect(rect, color)
                    if index.column() == 0:
                        parts = segments(index.data(role), rect.left(), rect.width())
                        for x, width, name in parts:
                            color = QtGui.QColor(name)
                            color.setAlpha(tint)
                            painter.fillRect(QtCore.QRect(x, rect.top(), width, rect.height()), color)
                except Exception:
                    parts = []
                QtGui.QStyledItemDelegate.paint(self, painter, option, index)
                try:  # over the row as drawn: a selected row's highlight covers the tint, not the bar
                    for x, width, name in parts:
                        painter.fillRect(QtCore.QRect(x, rect.bottom() - bar + 1, width, bar), QtGui.QColor(name))
                except Exception:
                    pass

        try:
            delegate = Tint(self.tree)
            self.tree.setItemDelegate(delegate)
            self.tree.setItemDelegateForColumn(0, delegate)
            return delegate
        except Exception:
            return None

    def icon_value(self, s, kern):
        """The distance a pair's picture sets its glyphs at: its kerning, and for kana palt's own
        adjustments (the right glyph's placement, the left one's added width, less the left one's
        placement, which moves it alone)."""
        left, right = self.adjustments.get(s.left), self.adjustments.get(s.right)
        return kern + (left[1] - left[0] if left else 0) + (right[0] if right else 0)

    def pair_icon(self, row, s, source):
        """A row's picture: the pair as on screen, at the value it takes (the one written), drawn from the
        font in the dialog's text color (the first GLYPH_ICON_ROWS rows); None for the others."""
        QtCore, QtGui = _qt()
        if self.package is None or row >= GLYPH_ICON_ROWS:
            return None
        kern = s.to_write(source)
        kern = s.current if kern is None else kern
        color = self.dialog.palette.color(QtGui.QPalette.WindowText)
        key = (s.left, s.right, kern, color.name())
        if key not in self.icon_cache:
            self.icon_cache[key] = glyph_icon(self.package, self.master, [s.left, s.right], color, self.icon_value(s, kern))
        return self.icon_cache[key]

    def theme_changed(self):
        """Dark mode switched, either way (FreeLab's shared mechanism calls this on each shown tool
        window): what was drawn or styled from the palette, again from the new one. The choice buttons'
        tint, the list's pictures, and the previews; the rows' tints are read from the palette as they
        are drawn (tint_rows)."""
        try:
            sheet = choice_sheet(self.dialog.palette)
            for button in self.choice_buttons.values():
                button.setStyleSheet(sheet)
        except Exception:
            pass
        self.icon_cache = {}  # (pictures in the old text color)
        try:
            self.refresh_values()  # the pictures and the previews, in the new colors
        except Exception:
            pass
        try:
            self.tree.viewport().update()
        except Exception:
            pass

    @staticmethod
    def main_window():
        QtCore, QtGui = _qt()
        try:
            for widget in QtGui.QApplication.topLevelWidgets():
                if widget.objectName == "MainWindow":
                    return widget
        except Exception:
            pass
        return None

    def current_font(self):
        """This window's font (window_font), or None when no font is open (FontLab then hands an empty package)."""
        workspace = self.fontlab.flWorkspace.instance()
        try:
            if not workspace.packages():
                return None  # nothing open: FontLab still hands a placeholder package with one glyph
        except Exception:
            pass
        package = window_font(self, workspace)
        if package is None or package.isNull or not package.glyphsCount:
            return None
        return package

    def font_named_now(self):
        """The font and master as every top line names them (font_named: the masters counted when several)."""
        try:
            masters = len(list(self.package.masters))
        except Exception:
            masters = 1
        return font_named(self.package.tfn, self.master, masters)

    def font_line(self):
        if self.package is None:
            return no_font_line()
        return head_join(u"%s." % self.font_named_now(),
                         u"%s." % (ALL_SCRIPTS_LINE if self.script == ALL_SCRIPTS else SCRIPT_LINES[self.script]))

    def no_font_scripts(self):
        """With no font, Script: says "n/a" (grayed with it), not the scripts of a font closed or Latin
        (owner's images 289, 290); fill_scripts lists the next font's, its keys being others."""
        try:
            self.script_box.blockSignals(True)
            self.script_box.clear()
            self.script_box.addItem(NOT_AVAILABLE)
            self.script_keys = []
        except Exception:
            pass
        finally:
            try:
                self.script_box.blockSignals(False)
            except Exception:
                pass

    def fill_scripts(self, package, wanted=None):
        """The script list: the scripts the font has; the script to analyze: wanted (or the last one)
        where the font has it, else its first."""
        found = font_scripts([ch for ch, _ in font_glyphs(package, u"".join(SCRIPT_LETTERS[key] for key, _ in SCRIPTS))])
        first, self.scripts_filled = not getattr(self, "scripts_filled", False), True
        if first and len(found) > 1:
            # first opened: the script the font has most letters of (a kana font with a few Latin letters opens on kana)
            wanted = max(found, key=lambda key: len(font_glyphs(package, SCRIPT_LETTERS[key])))
        keys = script_choices(found)
        chosen = next((key for key in (wanted, self.script) if key in keys), found[0] if found else "latin")
        if keys != self.script_keys:
            self.script_box.blockSignals(True)
            self.script_box.clear()
            for key in keys:
                self.script_box.addItem(script_label(key))
            self.script_box.blockSignals(False)
            self.script_keys = keys
        self.script_box.setCurrentIndex(keys.index(chosen) if chosen in keys else 0)
        self.script_box.setEnabled(len(keys) > 1)
        return chosen

    def script_note(self):
        """The script analyzed, for the status line: kana say how they are set."""
        if self.script == ALL_SCRIPTS:
            parts = getattr(self.analysis, "parts", None) or []
            return u"all scripts (%s)" % u", ".join(script_label(script) for script, _ in parts) if parts else u"all scripts"
        if self.script != "kana":
            return dict(SCRIPTS)[self.script]
        if self.adjustments:
            return u"kana as palt sets them (its common pairs)"
        return u"proportional kana (their common pairs)"

    def chosen_script(self):
        index = self.script_box.currentIndex
        return self.script_keys[index] if 0 <= index < len(self.script_keys) else "latin"

    def kana_adjustments(self, package, master):
        """palt's adjustments of the font's kana, read from its feature code; ValueError when its kana
        are full width and palt does not set them proportionally (kerning them would fight the
        full-width setting)."""
        adjustments = {}
        try:
            features = package.fgPackage.features
            prefix = features.get_prefix() if hasattr(features, "get_prefix") else u""
            if "palt" in list(features.keys()):
                adjustments = palt_adjustments(features.get_feature("palt"), prefix)
        except Exception:
            adjustments = {}
        advances = {}
        for ch, name in font_glyphs(package, KANA_LETTERS):
            layer = package.findName(name).getLayerByName(master)
            if layer is not None:
                advances[name] = layer.advanceWidth
        setting = kana_setting(advances, float(package.upm), adjustments)
        if setting is None:
            raise ValueError(u"this font's kana are full width, and its palt does not set them proportionally: kerned, "
                             u"they would be kerned in full-width text too. Write palt with CJK Spacing first, then analyze "
                             u"the kana again.")
        return adjustments if setting == "palt" else {}

    @staticmethod
    def combo(choices):
        QtCore, QtGui = _qt()
        box = QtGui.QComboBox()
        for _, label in choices:
            box.addItem(label)
        return box

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)  # analyzed as it opens, once it is drawn

    def progress(self, done, total, what="Measuring pairs"):
        """The measuring at done of total, in the window's top row (busy_progress): False once the user
        asked it to stop (the tools menu, an arrow, Close, Esc), which analyze takes as "stop"."""
        try:
            busy_progress(self, u"%s (%d of %d)" % (what, done, total) if total else what,
                          float(done) / total if total else None)
        except Stopped:
            self.stop = True
        return not self.stop

    def run(self):
        """Analyze the font that is current now (another may have been opened since the dialog was)."""
        if self.busy:
            return  # a click while measuring or asking FontLab: the work under way finishes first
        self.busy = True
        self.stop = False
        busy_start(self, u"Measuring pairs")
        try:
            self.run_once()
        finally:
            busy_end(self)
            self.busy = False
            self.analyze_button.setEnabled(True)
            self.update_buttons()  # (no font, or nothing analyzed: the settings grayed out)
            if self.refilter_again:
                self.refilter_again = False
                self.refilter()
            self.seen_history = history_mark(self.package)
            if self.focus is not None and self.analysis is not None:
                focus, self.focus = self.focus, None
                self.focus_pair(*focus)

    def run_once(self):
        package = self.current_font()
        if package is None:
            self.package, self.analysis, self.suggestions = None, None, []
            self.clear_list()
            self.no_font_scripts()
            self.status.setText(self.font_line())
            return
        if self.package is None or font_key(package) != font_key(self.package) or package.master != self.master:
            self.analysis, self.suggestions = None, []
            self.clear_list()
        self.package, self.master = package, package.master
        self.analyze_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        try:
            script = self.fill_scripts(package, self.chosen_script())
            if script != self.script:
                self.analysis, self.suggestions = None, []
                self.clear_list()
            self.script = script
            scripts = [key for key in self.script_keys if key != ALL_SCRIPTS] if script == ALL_SCRIPTS else [script]
            self.sides = {}
            for key in scripts:
                sides = font_glyphs(package, SCRIPT_SIDE[key]) or font_glyphs(package, u"H")
                self.sides[key] = sides[0][1] if sides else u"H"
            self.side = self.sides.get(scripts[0], u"H")
            self.adjustments, parts = {}, []
            for key in scripts:
                try:
                    adjustments = self.kana_adjustments(package, self.master) if key == "kana" else {}
                except ValueError as exc:
                    if len(scripts) == 1:
                        raise
                    self.log.add(u"Kana left out: %s" % with_tool_links(html(u"%s" % exc)), "warning")  # (the other scripts analyzed)
                    continue
                self.adjustments.update(adjustments)
                # kana: the pairs common in text only (all of them, some 45,000, would each be listed and asked of FontLab)
                pairs = script_pairs(self.common, key) if key == "kana" else None
                what = u"Measuring %s pairs" % script_label(key) if len(scripts) > 1 else u"Measuring pairs"
                part = analyze(self.package, self.master, progress=lambda done, total, what=what: self.progress(done, total, what),
                               script=key, adjustments=adjustments, pairs=pairs)
                if part is None:
                    parts = None
                    break
                for s in part.suggestions:
                    s.script = key
                parts.append((key, part))
            result = None if parts is None else (parts[0][1] if script != ALL_SCRIPTS else MergedAnalysis(parts))
        except Exception as exc:
            message = u"%s" % exc
            self.status.setText(self.font_line())
            self.log.add(with_tool_links(html(message[:1].upper() + message[1:])), "error")
            return
        if result is None:
            self.status.setText(self.font_line())
            self.log.add(u"Stopped.", "warning")
            return
        self.harvest_checks()
        self.icon_cache = {}  # (measured again: the outlines may have changed, the pictures with them)
        if self.analysis is not None:  # the same font and master: its picks and checks carry over
            before = dict(((old.left, old.right), old) for old in self.analysis.suggestions)
            for new in result.suggestions:
                old = before.get((new.left, new.right))
                if old is not None:
                    new.override, new.checked = old.override, old.checked
        self.analysis = result
        self.refresh_kerning()
        self.refilter(inside_run=True)

    def source_key(self):
        return SOURCES[self.source.currentIndex][0]

    def shown(self, suggestion):
        kind = SHOW[self.show_kind.currentIndex][0]
        kinds = (category(suggestion.left_char), category(suggestion.right_char))
        if kind == "letters":
            return all(k in ("upper", "lower", "kana") for k in kinds)
        if kind == "punctuation":
            return all(k in ("upper", "lower", "kana", "punctuation") for k in kinds)
        if kind == "figures":
            return "figure" in kinds
        return True

    def rank(self, suggestion):
        return self.common.get(text_order(suggestion.left_char, suggestion.right_char), len(self.common))

    def ask_fontlab(self, suggestions):
        """FontLab's own value for the pairs not asked yet (a call per pair)."""
        missing = [s for s in suggestions if "fontlab" not in s.values]
        if not missing:
            return
        # (its own guarded progress when a filter change asks, outside run's: events pumped with no guard
        # let clicks change the list it was filling; and a stop now stops it; review 12)
        own = _busy_state(self).get("guard") is None
        if own:
            self.stop = False
            busy_start(self, u"Asking FontLab")
        try:
            for index, s in enumerate(missing):
                s.values["fontlab"] = fontlab_autokern(self.package, self.master, s.left, s.right)
                if index % 50 == 0 and not self.progress(index, len(missing), "Asking FontLab"):
                    break  # (the pairs asked so far keep FontLab's value; the others show none)
            self.analysis.remember_fontlab()
        finally:
            if own:
                busy_end(self)

    def picked_count(self):
        return sum(1 for s in self.analysis.suggestions if s.override) if self.analysis is not None else 0

    def update_picked(self):
        """The "picked by hand" filter, shown while a pair is picked (or while it is on)."""
        count = self.picked_count()
        self.only_picked.setText(u"List only pairs picked by hand (%d)." % count)
        wanted = bool(count) or self.only_picked.checked
        if self.picked_room_kept:
            self.only_picked.setVisible(wanted)
        else:  # (a Qt without retainSizeWhenHidden: shown throughout, usable while a pair is picked)
            self.only_picked.setEnabled(wanted)

    def refilter(self, inside_run=False):
        """The list: pairs either method would change by the tolerance or more, whatever source writes
        (choosing another source changes only what is written, not the list or its order)."""
        if self.analysis is None:
            return
        if self.busy and not inside_run:
            self.refilter_again = True  # a setting changed while FontLab was asked: done after
            return
        if not inside_run:
            self.busy = True
            try:
                return self.refilter(inside_run=True)
            finally:
                self.busy = False
                if self.refilter_again:
                    self.refilter_again = False
                    self.refilter()
        self.harvest_checks()
        tolerance = self.tolerance.value
        include = self.include_kerned.checked
        common_only = PAIRS[self.pairs.currentIndex][0] == "common"
        picked_only = self.only_picked.checked

        def differs(s, key):
            value = s.value(key)
            return value is not None and abs(value - s.current) >= tolerance

        if picked_only:
            listed = [s for s in self.analysis.suggestions if s.override]
        else:
            listed = [s for s in self.analysis.suggestions
                      if (s.left, s.right) in self.pinned
                      or (self.shown(s) and (include or not s.current)
                          and (not common_only or text_order(s.left_char, s.right_char) in self.common)
                          and (differs(s, "halfkern") or differs(s, "contour") or differs(s, "average")))]
        self.ask_fontlab(listed)
        order = ORDERS[self.order.currentIndex][0]
        change = lambda s: -abs((s.value("average") or 0) - s.current)
        if order == "agreement":
            listed.sort(key=lambda s: (s.spread(), change(s)))
        elif order == "common":
            listed.sort(key=lambda s: (self.rank(s), change(s)))
        elif order == "alphabet":
            listed.sort(key=lambda s: text_order(s.left_char, s.right_char))  # (as read: a Hebrew pair by its right letter)
        else:
            listed.sort(key=change)
        self.suggestions = listed
        self.hint_shown()
        summary = factor_summary(self.analysis)
        analysis = self.analysis
        work = (u"%s: %s measured, %s unchanged since the last analysis" % (
                    b(counted(len(analysis.suggestions), u"pair")), b(grouped(analysis.measured)), b(grouped(analysis.reused)))
                if analysis.reused else u"%s measured" % b(counted(len(analysis.suggestions), u"pair")))
        what = (u"%s listed, picked by hand" % b(grouped(len(listed))) if picked_only
                else u"%s listed" % b(grouped(len(listed))))
        self.status.setText(head_join(u"%s, %s." % (self.font_named_now(), b(self.script_note())),
                                      u"%s; %s.<br>%s." % (work, what, html("; ".join(summary)))))
        if self.first_pass:
            self.first_pass = False
            self.log.add(u"Analyzed %s, master %s: %s listed." % (b(self.package.tfn), b(self.master),
                                                                   b(counted(len(listed), u"pair"))))
        self.update_picked()
        self.fill_table()

    def fill_table(self):
        """The list filled anew with self.suggestions, in their order: row k is suggestion k (its item's
        UserRole holds k)."""
        QtCore, QtGui = _qt()
        tree = self.tree
        # (the pair selected stays selected where it is still listed, as the table kept its row selected)
        kept = getattr(self, "selected_pair", None)
        self.clear_list()
        source = self.source_key()
        blank = [u""] * (len(self.COLUMNS) - 1)
        for row, s in enumerate(self.suggestions):
            item = QtGui.QTreeWidgetItem([pair_label(s.left_char, s.right_char)] + blank)  # (as a reader sees it, right to left too)
            item.setData(0, QtCore.Qt.UserRole, row)
            item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            checked = s.checked if s.checked is not None else not s.current  # the designer's pairs: opt in
            item.setCheckState(0, QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            for column in self.NUMBERS:
                item.setTextAlignment(column, int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
            tree.addTopLevelItem(item)
            self.fill_row(row, s, source, item)
        fit_columns(tree, self.NUMBERS)
        rows = [row for row, s in enumerate(self.suggestions) if (s.left, s.right) == kept]
        if rows:
            self.select_row(rows[0])  # (its selection change shows its preview)
        self.select()
        self.update_buttons()

    def target_text(self, s):
        """Where the pair's value is written, for its tooltip and the line under the list."""
        if self.font_kerning is None:
            return u""
        entry = self.font_kerning.target(*s.key)[0]
        reach = self.font_kerning.reach(entry)
        if reach > 1:
            return u"Writes to %s, which kerns %s." % (FontKerning.describe(entry), counted(reach, u"glyph pair"))
        return u"Writes to the pair %s alone." % FontKerning.describe(entry)

    def fill_row(self, row, s, source, item=None):
        """A row's numbers, its picture at the value it takes, its tint while picked by hand (the
        delegate draws it in the palette's highlight), and its tooltips. item: the row's item, when the
        caller has just made it (else read from the list)."""
        QtCore, QtGui = _qt()
        item = item if item is not None else self.row_item(row)
        if item is None:
            return
        cells = (s.current, s.values.get("halfkern"), s.values.get("contour"), s.values.get("learned"),
                 s.values.get("fontlab"), s.spread(), s.to_write(source))
        for column, value in enumerate(cells, 1):
            item.setText(column, u"\N{EN DASH}" if value is None else str(value))
        last = len(self.COLUMNS) - 1
        font = QtGui.QFont(self.tree.font)
        font.setBold(bool(s.override))
        item.setFont(last, font)
        item.setToolTip(last, u"Picked by hand: %s. <i>Backspace</i> or <i>Reset pair</i> gives it the suggested value."
                        % html(dict(CHOICES)[s.override]) if s.override else u"")
        for column in range(len(self.COLUMNS)):
            if bool(item.data(column, PICKED_ROLE)) != bool(s.override):
                item.setData(column, PICKED_ROLE, True if s.override else None)
        icon = self.pair_icon(row, s, source)
        item.setIcon(0, icon if icon is not None else QtGui.QIcon())
        script = u" (%s)" % script_label(getattr(s, "script", self.script)) if self.script == ALL_SCRIPTS else u""
        item.setToolTip(0, u"%s %s%s. %s%s" % (s.left, s.right, script, rtl_note(s, True), self.target_text(s)))

    def refresh_values(self):
        """Another source: only the Suggested column and the preview change."""
        source = self.source_key()
        for row, s in enumerate(self.suggestions):
            self.fill_row(row, s, source)
        self.select()

    def harvest_checks(self):
        """The list's checks, kept on its suggestions before the list is filled again (rows read anew)."""
        QtCore, QtGui = _qt()
        for row in range(min(self.row_count(), len(self.suggestions))):
            item = self.row_item(row)
            if item is not None:
                self.suggestions[row].checked = item.checkState(0) == QtCore.Qt.Checked

    def check_all(self, on):
        """Check every new pair, or uncheck everything; pairs the font kerns are checked one by one. The
        log says how many it changed (check_rows)."""
        items = [self.row_item(row) for row in range(min(self.row_count(), len(self.suggestions)))]
        check_rows([item for item in items if item is not None],
                   lambda item: on and not self.suggestions[self.row_of(item)].current, self.log,
                   u"Tick new pairs" if on else u"Tick none", u"pair")
        self.update_buttons()

    def row_checked(self, row):
        QtCore, QtGui = _qt()
        item = self.row_item(row)
        return item is not None and item.checkState(0) == QtCore.Qt.Checked

    def update_buttons_soon(self):
        """Once, after the changes under way (filling the list changes every row)."""
        QtCore, QtGui = _qt()
        if not self.buttons_due:
            self.buttons_due = True
            QtCore.QTimer.singleShot(0, self.update_buttons)

    def update_buttons(self):
        """Each button clickable only when it would do something."""
        self.buttons_due = False
        rows = range(min(self.row_count(), len(self.suggestions)))
        checked = [self.row_checked(row) for row in rows]
        enable(self.all_button, any(not on and not self.suggestions[row].current for row, on in zip(rows, checked)))
        enable(self.none_button, any(checked))
        # (only while a checked pair would get a value it has not: once written, its checks stay and it
        # grays out; clicked again and again, it logged "Wrote 0 entries for 0 pairs", owner's report 151)
        enable(self.apply_button, self.writes_pending([self.suggestions[row] for row, on in zip(rows, checked) if on]))
        enable(self.restore_button, self.edited())
        enable(self.classes_button, self.package is not None)
        enable(self.check_button, self.package is not None)
        # The list's settings act on an analysis only: grayed out until there is one (no font open, or
        # one that could not be analyzed); Analyze while there is a font to read
        analyzed = self.analysis is not None
        for widget in (self.tolerance, self.show_kind, self.source, self.order, self.include_kerned):
            enable(widget, analyzed)
        enable(self.pairs, analyzed and bool(self.common))
        enable(self.analyze_button, not self.busy and (self.package is not None or fonts_open(self.fontlab)))

    def edited(self):
        """Whether a check or a value differs from how the list first came."""
        if self.analysis is None:
            return False
        self.harvest_checks()
        return any(s.override or (s.checked is not None and s.checked != (not s.current))
                   for s in self.analysis.suggestions)

    def restore(self):
        """Every check and pick back as the list first came after the last analysis."""
        if self.analysis is None:
            return
        for s in self.analysis.suggestions:
            s.override, s.checked = None, None
        self.update_picked()
        self.fill_table()
        self.log.add(u"Ticks and values restored as suggested.")

    def focus_neighbor(self, key):
        """An H beside a preview's pair clicked: its pair with the glyph beside it."""
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        side = self.side_of(s)
        if key == "before":
            self.focus_pair(side, s.left)
        else:
            self.focus_pair(s.right, side)

    def side_of(self, s):
        """The glyph a pair is previewed between: its script's straight letter (H for Latin)."""
        return self.sides.get(getattr(s, "script", self.script), self.side)

    def focus_pair(self, left, right):
        """The pair of the glyphs named left and right, selected in the list: listed whatever the
        filters (it stays listed until the next analysis), and measured first when it was not."""
        if self.analysis is None or self.package is None:
            self.focus = (left, right)
            return
        found = [s for s in self.analysis.suggestions if (s.left, s.right) == (left, right)]
        if not found:
            s = self.measure_one(left, right)
            if s is None:
                self.log.add(u"The pair %s %s could not be measured: Auto Kerning measures pairs of encoded "
                             u"glyphs." % (b(left), b(right)), "warning")
                return
            self.analysis.suggestions.append(s)
            found = [s]
        self.pinned.add((left, right))
        self.refilter()
        for row, s in enumerate(self.suggestions):
            if (s.left, s.right) == (left, right):
                self.select_row(row)
                self.tree.setFocus()
                return

    def measure_one(self, left, right):
        """A suggestion for one pair outside the analysis (an accented letter's), its values scaled
        by the analysis's factors."""
        package = self.package
        chars = []
        for name in (left, right):
            glyph = package.findName(name)
            code = main_code(glyph.fgGlyph) if glyph is not None else 0  # (not a radical FontLab gives first)
            if not code:
                return None
            chars.append(unichr_(code))
        script = self.script
        if script == ALL_SCRIPTS:  # the pair's own script, if the font's are analyzed
            script = pair_script(chars[0], chars[1], self.script_keys[0])
            if script not in self.script_keys:
                script = self.script_keys[0]
        wanted = list(SCRIPT_TUNING[script]) + [ch for chars_ in SCRIPT_REFERENCES[script].values() for ch in chars_] + chars
        try:
            result = analyze(package, self.master, characters=u"".join(sorted(set(wanted))), cache_file="", script=script,
                             adjustments=self.adjustments if script == "kana" else {})
        except Exception:
            return None
        for s in result.suggestions if result is not None else []:
            if (s.left, s.right) == (left, right):
                s.script = script
                for method, units in s.raw.items():
                    tighten, loosen = factors_of(self.analysis, script).get(method, DEFAULT_FACTORS[method])
                    s.values[method] = round_units(units * (tighten if units < 0 else loosen))
                return s
        return None

    def history_moved(self):
        """An undo, a redo, or an edit in FontLab: the current values read again."""
        if self.analysis is None or self.package is None:
            return
        self.refresh_kerning()
        changed = 0
        for s in self.analysis.suggestions:
            now = self.font_kerning.current(*s.key)
            if now != s.current:
                s.current = now
                changed += 1
        if changed:
            self.harvest_checks()
            for row, s in enumerate(self.suggestions):
                self.fill_row(row, s, self.source_key())
            self.select()
            self.log.add(u"The font's History moved (an undo, a redo, or an edit): %s read again. Click %s "
                         u"if outlines changed." % (b(counted(changed, u"current value")), i("Analyze")))

    def font_changed(self):
        """This window's font was closed, or a font opened for this window without one (fonts_tick):
        the new font analyzed, or the list emptied and the no-font line shown."""
        self.first_pass = True
        self.run()

    def toggle_check(self):
        QtCore, QtGui = _qt()
        if self.selected is None:
            return
        item = self.row_item(self.selected)
        if item is not None:
            item.setCheckState(0, QtCore.Qt.Unchecked if item.checkState(0) == QtCore.Qt.Checked else QtCore.Qt.Checked)

    def select_row(self, row):
        """Row number row made the current, selected row, scrolled into view."""
        item = self.row_item(row)
        if item is not None:
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    def selected_row(self):
        """The selected row's number, or None."""
        items = self.tree.selectedItems()
        row = self.row_of(items[0]) if items else None
        return row if row is not None and row < len(self.suggestions) else None

    def select(self):
        row = self.selected_row()
        self.selected_pair = (self.suggestions[row].left, self.suggestions[row].right) if row is not None else None
        if row is None:
            self.selected = None
            self.reset_button.setEnabled(False)
            self.glyph_window_button.setEnabled(False)
            self.preview_note.setText("Select a pair to compare the methods; click one to use it for that pair.")
            self.preview_note.setVisible(bool(self.suggestions))  # (nothing listed: nothing to select)
            self.related.setVisible(False)
            for button in self.choice_buttons.values():
                button.setEnabled(False)
                button.setIcon(_qt()[1].QIcon())
                button.setVisible(False)
            return
        for button in self.choice_buttons.values():
            button.setVisible(True)
        self.preview_note.setVisible(True)
        self.selected = row
        if self.package is not None and time.time() - self.kerning_read > 1.0:
            self.refresh_kerning()
        self.show_preview(self.suggestions[self.selected])

    def refresh_kerning(self):
        self.font_kerning, self.kerning_read = FontKerning(self.package.kerning(self.master)), time.time()

    def choose(self, key):
        """The method for the selected pair alone; the dialog's source again clears the choice."""
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        if s.value(key) is None:
            return
        s.override = None if key == self.source_key() else key
        self.fill_row(self.selected, s, self.source_key())
        self.show_preview(s)
        self.update_picked()

    def reset(self):
        if self.selected is None:
            return
        s = self.suggestions[self.selected]
        s.override = None
        self.fill_row(self.selected, s, self.source_key())
        self.show_preview(s)
        self.update_picked()

    def double_clicked(self, row, column):
        """A method's value double-clicked: that value for the pair; the Suggested one: reset; the
        pair's name: the pair in a Glyph window."""
        if row is None or row >= len(self.suggestions):
            return
        self.select_row(row)
        self.selected = row
        if column == 0:
            self.show_in_glyph_window()
        elif column in COLUMN_CHOICES:
            self.choose(COLUMN_CHOICES[column])
        elif column == len(self.COLUMNS) - 1:
            self.reset()

    def item_double_clicked(self, item, column):
        """The list's double-click (a row's item and its column), as double_clicked takes it."""
        try:
            self.double_clicked(self.row_of(item), column)
        except Exception:
            pass  # (a slot must not raise)

    def show_related(self, s):
        """Under the note, the glyph pairs the pair's entry kerns, when there are others."""
        pairs = self.font_kerning.pairs(self.font_kerning.target(*s.key)[0]) if self.font_kerning else []
        if len(pairs) < 2:
            self.related.setVisible(False)
            return
        names = [u"%s %s" % pair for pair in pairs if pair != s.key]  # (in the font's key order)
        shown = u", ".join(names[:RELATED_SHOWN])
        if len(names) > RELATED_SHOWN:
            shown += u", and %s more" % grouped(len(names) - RELATED_SHOWN)
        self.related.setText(u"Also kerns: %s." % shown)
        self.related.setToolTip(u"\n".join(names))
        self.related.setVisible(True)

    def show_preview(self, s):
        """Each choice's button: the pair between two H's as that method sets it, its name and value
        beside it (all in one picture, drawn in the dialog's text color), and the one the pair takes
        checked."""
        QtCore, QtGui = _qt()
        source = self.source_key()
        chosen = s.override or source
        self.reset_button.setEnabled(bool(s.override))
        self.glyph_window_button.setEnabled(True)
        picked = (u"Picked by hand: %s. " % dict(CHOICES)[s.override]) if s.override else u""
        target = self.target_text(s)
        self.preview_note.setText(u"%sThe pair %s: %s%s" % (picked, pair_label(s.left_char, s.right_char), rtl_note(s),
                                                             target[:1].lower() + target[1:]))
        self.show_related(s)
        palette = self.dialog.palette
        text = palette.color(QtGui.QPalette.WindowText)  # (FontLab 7's PythonQt lacks the placeholder text role)
        scale = float(PREVIEW_SIZE) / float(self.package.upm)
        paths = []  # (advance, path, role): the pair between two H's (the script's straight letter), when the font has one
        side = self.side_of(s)
        for name, role in ((side, "side"), (s.left, "left"), (s.right, "right"), (side, "side")):
            glyph = self.package.findName(name)
            layer = glyph.getLayerByName(self.master) if glyph is not None and not glyph.isNull else None
            if layer is not None:
                path, advance = layer_path(layer), layer.advanceWidth
                if name in self.adjustments:  # kana as palt sets them
                    placement, extra = self.adjustments[name]
                    shift = QtGui.QTransform()
                    shift.translate(placement, 0)
                    path, advance = shift.map(path), advance + extra
                paths.append((advance, path, role))
        strip = int(sum(advance for advance, _, _ in paths) * scale) + PREVIEW_SIZE
        font = QtGui.QFont(self.dialog.font)
        for number, (key, label) in enumerate(CHOICES):
            button, kern = self.choice_buttons[key], s.value(key)
            button.setEnabled(kern is not None)
            button.setChecked(key == chosen)
            pixmap = QtGui.QPixmap(strip + PREVIEW_TEXT_WIDTH, int(PREVIEW_SIZE * 1.35))
            pixmap.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter(pixmap)
            spans = []
            try:  # ended before anything else can fail: a painter left open on a freed pixmap aborts FontLab
                if kern is not None:
                    spans = self.paint_pair(painter, paths, scale, kern, text)
                    self.paint_label(painter, font, text, strip, pixmap.height(), label, str(kern), number + 1)
                else:  # nothing to choose: its name dimmed, no value, no key (it looked as clickable as the others)
                    dim = QtGui.QColor(text)
                    dim.setAlpha(UNAVAILABLE_ALPHA)
                    self.paint_label(painter, font, dim, strip, pixmap.height(), label, u"not available", None)
            finally:
                painter.end()
            button.setIcon(QtGui.QIcon(pixmap))
            button.setIconSize(pixmap.size())
            self.neighbors[key].set(spans, pixmap.size())

    @staticmethod
    def paint_pair(painter, paths, scale, kern, color):
        """Draws the pair between its H's; the H's spans across the picture, (left, right, "before" or
        "after"), to be clicked."""
        QtCore, QtGui = _qt()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        x = float(PREVIEW_SIZE) / 2
        spans, seen_pair = [], False
        for width, path, role in paths:
            painter.save()
            painter.translate(x, PREVIEW_SIZE * 1.05)
            painter.scale(scale, -scale)
            ink = QtGui.QColor(color)
            if role == "side":
                ink.setAlpha(SIDE_ALPHA)  # the H's: dimmed
            painter.fillPath(path, QtGui.QBrush(ink))
            painter.restore()
            advance = width * scale + (kern * scale if role == "left" else 0)
            if role == "side":
                spans.append((x, x + width * scale, "after" if seen_pair else "before"))
            else:
                seen_pair = True
            x += advance
        return spans

    @staticmethod
    def paint_label(painter, font, color, left, height, label, value, key):
        """The method's name (bold), its value, and its key, in the picture: a button's own text
        took other colors than the dialog's under some styles."""
        QtCore, QtGui = _qt()
        painter.setPen(color)
        bold = QtGui.QFont(font)
        bold.setBold(True)
        line = QtGui.QFontMetrics(font).height()
        top = (height - 3 * line) // 2
        flags = int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        painter.setFont(bold)
        painter.drawText(QtCore.QRect(left, top, PREVIEW_TEXT_WIDTH, line), flags, label)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(left, top + line, PREVIEW_TEXT_WIDTH, line), flags, value)
        if key is None:
            return
        faint = QtGui.QColor(color)
        faint.setAlpha(120)
        painter.setPen(faint)
        painter.drawText(QtCore.QRect(left, top + 2 * line, PREVIEW_TEXT_WIDTH, line), flags, u"Ctrl+%d" % key)

    def planned_writes(self, kerning, checked):
        """What Write checked pairs would write now for the checked suggestions, on kerning (a
        FontKerning): ([(entry, value, remove, its pairs)] for each entry whose value changes, the
        number of pairs that take a commoner pair's value). Pairs sharing an entry (a class pair) get
        the value of the most common of them, even when that one keeps its current value (the entry is
        then left as it is); ties go to the first in alphabetical order."""
        source = self.source_key()
        plans = {}
        for s in checked:
            value = s.to_write(source)
            if value is None:
                continue
            target = kerning.target(*s.key)
            plans.setdefault(target[0], []).append(((self.rank(s), s.left_char, s.right_char), s, value, target[1]))
        todo, shared = [], 0
        for entry, wanted in sorted(plans.items(), key=lambda plan: plan[0]):
            wanted.sort(key=lambda plan: plan[0])
            _, first, value, remove = wanted[0]
            if len(set(plan[2] for plan in wanted)) > 1:
                shared += len(wanted) - 1
            if value != first.current:  # (else the commonest pair keeps its value: the entry stays as it is)
                todo.append((entry, value, remove, [plan[1] for plan in wanted]))
        return todo, shared

    def writes_pending(self, checked):
        """Whether Write checked pairs would change anything for these checked suggestions (planned_writes,
        on the font's kerning as last read; without it, whether one's value differs from its current)."""
        if not checked or self.busy:
            return False
        if self.font_kerning is not None:
            try:
                return bool(self.planned_writes(self.font_kerning, checked)[0])
            except Exception:
                pass
        source = self.source_key()
        return any(s.to_write(source) is not None and s.to_write(source) != s.current for s in checked)

    def write(self):
        """Each checked pair's value, written where it applies (FontKerning.target), as planned_writes
        plans it. Nothing to write (each entry has its value already): said so, nothing recorded."""
        QtCore, QtGui = _qt()
        if self.busy:
            return
        self.harvest_checks()
        kerning = FontKerning(self.package.kerning(self.master))
        todo, shared = self.planned_writes(kerning, [s for s in self.suggestions if s.checked])
        if not todo:
            self.log.add(u"Nothing was written: every ticked pair has the value it would be given already.")
            self.update_buttons()
            return
        if not self.begin_kerning_write():
            return
        classes = entries = 0
        written, error = [], None
        try:
            for entry, value, remove, pairs in todo:
                kerning.write(entry, value, remove)
                entries += 1
                if kerning.reach(entry) > 1:
                    classes += 1
                written.extend(pairs)
        except Exception as exc:  # what was written stays written, and is reported
            error = exc
        status = self.after_writing(self.package)
        self.refresh_kerning()
        for s in self.analysis.suggestions:
            s.current = self.font_kerning.current(*s.key)
        for s in written:
            s.override = None
        first = u"Wrote %s for %s to master %s%s" % (
            b(counted(entries, u"entry", u"entries")), b(counted(len(written), u"pair")), b(html(self.master)),
            (u" (%s, which kern%s %s classes' other glyphs too)" % (
                u"one of them a kerning class pair" if classes == 1 else u"%s of them kerning class pairs" % b(grouped(classes)),
                u"s" if classes == 1 else u"", u"its" if classes == 1 else u"their")) if classes else u"")
        if 0 < len(written) <= LOG_PAIRS_SHOWN:  # the pairs, drawn from the font, each glyph opened on a click
            first += u": %s" % pair_links([(s.left, s.right) for s in written])
        lines = [u"%s shared an entry with a commoner pair and took its value." % b(counted(shared, u"pair"))] if shared else []
        self.update_picked()
        self.fill_table()
        if entries:  # (none: the error below says why)
            self.log.add(u" ".join([first + u"."] + lines), "done")
        if error is not None:
            self.log.add(u"Stopped by an error: %s" % html(error), "error")
        status.report(self.log)
        self.seen_history = history_mark(self.package)

    def begin_kerning_write(self):
        """before_changes for a kerning write (begin_write: False, said in the log, when nothing may be
        written). The kerning is the font's own state, which FontLab records when it opens a font, but the
        step notify_changed makes records the whole font, its glyphs too, and they have no state of their
        own in a font opened afresh: undoing the step made FontLab print "We have a problem with the
        component 'P' in glyph 'Rho:Regular'" for each glyph built from components (owner's image 336)."""
        return begin_write(self.fontlab, self.package, u"FreeLab Auto Kerning", self.log)

    def after_writing(self, package):
        """FontLab told of the change, and the font marked modified: a script's kerning writes leave it
        unmarked, and FontLab would close it without asking to save (begun by begin_kerning_write).
        notify_changed's WriteStatus."""
        return notify_changed(self.fontlab, package, u"FreeLab Auto Kerning", added=False)


def font_class_suggestions(package, master, core=None, em=EM_PIXELS, model=None):
    """(plans, names): the classes suggested for a master, planned against its own classes."""
    glyphs = FontLabGlyphs(package, master, em)
    found = [(ch, name) for ch, name in font_glyphs(package, class_characters()) if glyphs.add(name)]
    names = dict(found)
    missing = [ch for ch in TUNING if ch not in names]
    if missing:
        raise ValueError(missing_references(package, TUNING, missing, u"Suggesting classes",
                                            u"their spacing is what glyphs are compared by"))
    image_of = lambda ch: glyphs.image(names[ch])
    tools = make_bands(core or Core(), image_of, names, em, glyphs.pad)
    signatures = {}

    def signature_of(ch, side):
        if (ch, side) not in signatures:
            signatures[(ch, side)] = side_signature(tools, image_of, names, ch, side, em, float(glyphs.pad))
        return signatures[(ch, side)]

    suggested = suggest_classes(names, signature_of, model if model is not None else class_model())
    return plan_classes(suggested, names, FontKerning(package.kerning(master)), signature_of, glyphs.upm), names


class ClassDialog(object):
    """Suggested kerning classes for the current master: review, check, and create."""

    def __init__(self, owner):
        QtCore, QtGui = _qt()
        self.owner = owner
        parent = owner.dialog
        dialog = self.dialog = mcp_script_window(QtGui.QDialog(parent))
        dialog.setWindowTitle("FreeLab Kerning Classes")
        dialog.setWhatsThis(CLASS_HELP)
        size_dialog(dialog)
        layout = window_layout(dialog)  # (its content scrolls on a small screen)
        self.status = status_label()  # (names in it made safe by html())
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(separator())
        self.tree = QtGui.QTreeWidget()
        self.tree.setColumnCount(len(CLASS_COLUMNS))
        self.tree.setHeaderLabels(list(CLASS_COLUMNS))
        table_layout(self.tree)
        self.tree.setWhatsThis(u"Each class suggested for this master: ticked ones are made (or extended) when you click "
                               u"<i>Create ticked classes</i>. Gray ones are shown for reference and left as they are. "
                               u"<i>May need pairs of their own</i> names the members that need looser kerning than the "
                               u"class's first glyph (an accent reaching toward the neighbor), at the pair where they "
                               u"differ most: the class's value would bring them too close there, so check those pairs "
                               u"after kerning the class.")
        layout.addWidget(self.tree, 1)
        previews = QtGui.QHBoxLayout()
        self.previews = []
        for _ in range(3):
            label = QtGui.QLabel()
            label.setProperty(LEAVE_ALONE_PROP, True)  # dark mode leaves the drawn pictures alone
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setMinimumHeight(int(PAIR_PREVIEW_EM * 1.7))
            label.setWhatsThis(u"A pair too close with its class's value: as it is now, adjusted (the value of its "
                               u"own it would be written with), and its base pair (the class's first glyph beside "
                               u"the same partner). Drag the adjusted pair's right glyph left or right to change "
                               u"that value.")
            previews.addWidget(label, 1)
            self.previews.append(label)
        layout.addLayout(previews)
        self.adjust_width = None
        self.adjusting = PairDrag(self.previews[1], self.adjusted_value, self.set_exception_value,
                                  lambda step: select_next_row(self.tree, step),
                                  lambda: float(PAIR_PREVIEW_EM) / float(self.package.upm))
        self.tree.connect("itemSelectionChanged()", self.update_previews)
        self.move = QtGui.QCheckBox("Move each new class's first glyph's pairs into the class.")
        self.move.setChecked(True)
        self.move.setWhatsThis(u"A new class made from A, \N{LATIN CAPITAL LETTER A WITH GRAVE}, ... takes over A's own pairs on "
                               u"that side, so every member kerns as A does. Without it, the class starts with no kerning.")
        layout.addWidget(self.move)
        buttons = QtGui.QHBoxLayout()
        self.all_button = QtGui.QPushButton("Tick all")
        self.none_button = QtGui.QPushButton("Tick none")
        self.apply_button = QtGui.QPushButton("Create ticked classes")
        self.exceptions_button = QtGui.QPushButton("Write ticked pairs")
        self.exceptions_button.setWhatsThis(u"Gives each ticked pair of <i>Pairs too close with their class's "
                                            u"value</i> the value shown, as a pair of its own: the class kerns "
                                            u"its other glyphs as before.")
        self.close_button = QtGui.QPushButton("Close")
        for button in (self.all_button, self.none_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.exceptions_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.all_button.connect("clicked()", lambda: self.check_all(True))
        self.none_button.connect("clicked()", lambda: self.check_all(False))
        self.apply_button.connect("clicked()", self.apply)
        self.exceptions_button.connect("clicked()", self.write_exceptions)
        self.close_button.connect("clicked()", dialog.close)
        self.plans, self.names, self.exceptions = [], {}, []
        self.package = self.master = None
        plain_buttons(dialog)
        name_controls(self)  # (FreeLab MCP's addresses: tree, apply_button, ...)

    def show(self):
        QtCore, QtGui = _qt()
        self.dialog.show()
        self.dialog.raise_()
        QtCore.QTimer.singleShot(50, self.run)

    def run(self):
        QtCore, QtGui = _qt()
        package = self.owner.current_font()
        master = package.master if package is not None else None
        self.package, self.master, self.plans, self.exceptions = package, master, [], []
        self.tree.clear()
        self.apply_button.setEnabled(False)
        self.exceptions_button.setEnabled(False)
        self.move.setEnabled(False)  # (back on once classes are listed)
        if package is None:
            self.status.setText(no_font_line(u"No font is open. Open one, then run <i>Auto Kerning</i> again."))
            return
        if class_model() is None:
            self.status.setText(u"The class model (%s) is missing beside the script: reinstall FreeLab." % CLASS_MODEL_FILE)
            return
        self.status.setText(u"Comparing the glyphs' sides\N{HORIZONTAL ELLIPSIS}")
        QtGui.QApplication.processEvents()
        try:
            self.plans, self.names = font_class_suggestions(package, master)
            self.exceptions = noted_exceptions(FontKerning(package.kerning(master)), self.plans, self.names)
        except Exception as exc:
            message = u"%s" % exc
            self.status.setText(html(message[:1].upper() + message[1:]))
            return
        self.move.setEnabled(bool(self.plans))
        self.fill()

    def fill(self):
        QtCore, QtGui = _qt()
        self.tree.clear()  # (items are found again by walking the tree, never kept: PythonQt deletes them here)
        counts = {}
        bold = QtGui.QFont(self.tree.font)
        bold.setBold(True)
        for side in ("first", "second"):
            top = QtGui.QTreeWidgetItem([CLASS_SIDES_LABELS[side]])
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            section_row(top, self.tree)
            order = {"new": 0, "add": 0, "overlap": 1, "same": 2}  # what can be made first, what the font has last
            for index, plan in sorted(enumerate(self.plans), key=lambda pair: (order[pair[1].action], pair[0])):
                if plan.side != side:
                    continue
                counts[plan.action] = counts.get(plan.action, 0) + 1
                item = QtGui.QTreeWidgetItem(list(plan.columns()) + [plan.describe_differs()])
                item.setData(0, QtCore.Qt.UserRole, index)
                if plan.action in ("new", "add"):
                    item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
                    item.setCheckState(0, QtCore.Qt.Checked)
                else:
                    item.setFlags(QtCore.Qt.ItemIsSelectable)  # shown, not made: drawn disabled
                tip = u"%s\nGlyphs: %s" % (plan.describe(), u" ".join(plan.glyphs))  # (plain: members may be < or &)
                for column in range(len(CLASS_COLUMNS)):
                    item.setToolTip(column, tip)
                for column in (0, 1):  # the class and its letters stand out
                    item.setFont(column, bold)
                top.addChild(item)
            top.setExpanded(True)
        if self.exceptions:
            top = QtGui.QTreeWidgetItem([CLASS_EXCEPTIONS_LABEL])
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            section_row(top, self.tree)
            for index, exception in enumerate(self.exceptions):
                plan = self.plans[exception.plan_index]
                class_name = plan.existing if isinstance(plan.existing, (type(u""), str)) else u""
                item = QtGui.QTreeWidgetItem([class_name, exception.text,
                                              u"Its own value: %d \N{RIGHTWARDS ARROW} %d" % (exception.current, exception.value),
                                              u", ".join(d for d in plan.describe_differs().split(u"; ")
                                                         if d.startswith(exception.text + u" "))])
                item.setData(0, QtCore.Qt.UserRole, EXCEPTION_ROLE_BASE + index)
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
                item.setCheckState(0, QtCore.Qt.Checked)
                tip = (u"%s %s now takes %d from its class; written as a pair of its own, it gets %d (an estimate: "
                       u"look at it after writing)." % (exception.pair[0], exception.pair[1], exception.current,
                                                        exception.value))
                for column in range(len(CLASS_COLUMNS)):
                    item.setToolTip(column, tip)
                for column in (0, 1):
                    item.setFont(column, bold)
                top.addChild(item)
            top.setExpanded(True)
        self.exceptions_button.setEnabled(bool(self.exceptions))
        # every row measured, each column at most TEXT_COLUMN_MOST: sized to its longest glyph list, the table
        # ran 1,664 pixels wide in a 964-pixel view (Tinos, live); a row's tooltip holds the whole list
        fit_rows(self.tree, range(len(CLASS_COLUMNS) - 1), most=TEXT_COLUMN_MOST)
        plural = lambda count, one, many: u"%s %s" % (b(count), one if count == 1 else many)
        self.summary = (u"%s, master %s: %s, %s, %s, %s. Nothing is changed until you "
                        u"create them." % (b(self.package.tfn), b(self.master),
                                           plural(counts.get("new", 0), u"new class", u"new classes"),
                                           plural(counts.get("add", 0), u"class to extend", u"classes to extend"),
                                           plural(counts.get("same", 0), u"the font has already", u"the font has already"),
                                           plural(counts.get("overlap", 0), u"left as it is (it overlaps the font's classes)",
                                                  u"left as they are (they overlap the font's classes)")))
        self.status.setText(self.summary)
        self.apply_button.setEnabled(bool(counts.get("new") or counts.get("add")))
        for button in (self.all_button, self.none_button):  # (grayed by update_states while the list was empty)
            button.setEnabled(True)
        self.update_previews()

    # -- the previews of a pair too close -----------------------------------

    def selected_exception(self):
        """The selected row's pair too close with its class's value, or None."""
        QtCore, QtGui = _qt()
        items = self.tree.selectedItems()
        if not items or self.package is None:
            return None
        data = items[0].data(0, QtCore.Qt.UserRole)
        index = int(data) - EXCEPTION_ROLE_BASE if data is not None else -1
        return self.exceptions[index] if 0 <= index < len(self.exceptions) else None

    def adjusted_value(self):
        exception = self.selected_exception()
        return exception.value if exception is not None else None

    def picture(self, pair, value, caption, room=False, width=None):
        QtCore, QtGui = _qt()
        return pair_pixmap(self.package, self.master, pair[0], pair[1], value, caption,
                           self.dialog.palette.color(QtGui.QPalette.WindowText), self.dialog.font, room, width)

    def update_previews(self):
        """The selected pair too close: now, adjusted, and its base pair (the class's first glyph)."""
        shown = []
        exception = self.selected_exception()
        try:
            if exception is not None:
                plan = self.plans[exception.plan_index]
                first = self.names.get(plan.members[0])
                shown = [(exception.pair, exception.current, u"Now: %d" % exception.current, False),
                         (exception.pair, exception.value, u"Adjusted: %d" % exception.value, True)]
                if first:
                    base = (first, exception.pair[1]) if plan.side == "first" else (exception.pair[0], first)
                    shown.append((base, exception.current, u"Base pair: %d" % exception.current, False))
        except Exception:
            shown = []
        self.adjust_width = None
        for index, label in enumerate(self.previews):
            if index < len(shown):
                pair, value, caption, room = shown[index]
                picture = self.picture(pair, value, caption, room)
                if room:
                    self.adjust_width = picture.width()  # kept while dragging: the left glyph stays put
                label.setPixmap(picture)
            else:
                label.clear()

    def set_exception_value(self, value):
        """The selected pair's own value set by hand (never past 0, as suggested): drawn again, its row
        shown and checked."""
        QtCore, QtGui = _qt()
        exception = self.selected_exception()
        if exception is None or value == exception.value:
            return
        exception.value = value
        self.previews[1].setPixmap(self.picture(exception.pair, value, u"Adjusted: %d" % value, width=self.adjust_width))
        for item in self.items(exceptions=True):
            if self.exceptions[int(item.data(0, QtCore.Qt.UserRole)) - EXCEPTION_ROLE_BASE] is exception:
                item.setText(2, u"Its own value: %d \N{RIGHTWARDS ARROW} %d" % (exception.current, value))
                item.setCheckState(0, QtCore.Qt.Checked)
                break

    def items(self, exceptions=False):
        """The rows of suggested classes, or of pairs too close (exceptions True)."""
        QtCore, QtGui = _qt()
        found = []
        for top_index in range(self.tree.topLevelItemCount):
            top = self.tree.topLevelItem(top_index)
            for child in range(top.childCount()):
                item = top.child(child)
                if (int(item.data(0, QtCore.Qt.UserRole)) >= EXCEPTION_ROLE_BASE) == exceptions:
                    found.append(item)
        return found

    def write_exceptions(self):
        """The checked pairs too close, each written as a pair of its own."""
        QtCore, QtGui = _qt()
        chosen = [self.exceptions[int(item.data(0, QtCore.Qt.UserRole)) - EXCEPTION_ROLE_BASE]
                  for item in self.items(exceptions=True) if item.checkState(0) == QtCore.Qt.Checked]
        if not chosen:
            return
        package, master = self.package, self.master
        current = self.owner.current_font()
        if current is None or font_key(current) != font_key(package) or current.master != master:
            self.run()
            self.status.setText(u"The font or master changed since these pairs were measured: here are this one's. "
                                + self.status.text)
            return
        kerning = FontKerning(package.kerning(master))
        stale = [e for e in chosen if kerning.current(*e.pair) != e.current]
        error, written = None, 0
        try:
            written = write_exceptions(kerning, [e for e in chosen if e not in stale])
        except Exception as exc:  # what was written stays written, and is reported
            error = exc
        status = self.owner.after_writing(package)
        self.run()
        notes = [u"Wrote %s of %s own." % (counted(written, u"pair"), u"its" if written == 1 else u"their")]
        if stale:
            notes.append(u"%s changed since %s measured and %s left as %s." % (
                counted(len(stale), u"pair"), u"it was" if len(stale) == 1 else u"they were",
                u"was" if len(stale) == 1 else u"were", u"it is" if len(stale) == 1 else u"they are"))
        if error is not None:
            notes.append(u"Stopped by an error: %s" % html(error))
        if not status.ok:
            notes.append(status.message())
        notes.append(u"Writing goes straight into the open font: close it without saving to take it back.")
        self.status.setText(u" ".join(notes) + u" " + self.status.text)

    def check_all(self, on):
        """Check all or Check none over the rows that can be made, the window's status line saying how many
        it changed (check_rows; this window has no log), the rows of closed sections included."""
        QtCore, QtGui = _qt()
        items = [item for item in self.items() + self.items(exceptions=True)
                 if int(item.flags()) & int(QtCore.Qt.ItemIsUserCheckable)]
        counts = check_rows(items, on, command=u"Tick all" if on else u"Tick none")
        line = check_line(u"Tick all" if on else u"Tick none", counts[0], counts[1], counts[2],
                          hidden_text=(u"in a closed section", u"in closed sections"))
        self.status.setText(line + u" " + (getattr(self, "summary", u"") or u""))

    def apply(self):
        QtCore, QtGui = _qt()
        chosen = []
        for item in self.items():
            if item.flags() & QtCore.Qt.ItemIsUserCheckable and item.checkState(0) == QtCore.Qt.Checked:
                chosen.append(self.plans[int(item.data(0, QtCore.Qt.UserRole))])
        if not chosen:
            return
        package, master = self.package, self.master
        current = self.owner.current_font()
        if current is None or font_key(current) != font_key(package) or current.master != master:
            self.run()
            self.status.setText(u"The font or master changed since these suggestions: here are this one's. Review them "
                                u"before creating any. " + self.status.text)
            return
        fresh, _ = font_class_suggestions(package, master)  # the font as it is now: names free, classes as listed
        wanted = set(plan.key() for plan in chosen)
        chosen = [plan for plan in fresh if plan.key() in wanted]
        if len(chosen) != len(wanted):
            self.plans = fresh
            self.fill()
            self.status.setText(u"The font's classes changed since these suggestions: they are worked out again. Review "
                                u"them before creating any. " + self.status.text)
            return
        error = None
        made = extended = moved = kept = 0
        try:
            made, extended, moved, kept = apply_class_plans(FontKerning(package.kerning(master)), chosen, self.move.checked)
        except Exception as exc:  # what was made stays made, and is reported
            error = exc
        status = self.owner.after_writing(package)
        self.run()
        notes = [u"Made %s and extended %d%s." % (counted(made, u"class", u"classes"), extended,
                                                   u", and moved %s into them" % counted(moved, u"pair") if moved else u"")]
        if kept:
            notes.append(u"%s kept %s own value as an exception." % (counted(kept, u"glyph pair"),
                                                                    u"its" if kept == 1 else u"their"))
        if error is not None:
            notes.append(u"Stopped by an error: %s" % html(error))
        if not status.ok:
            notes.append(status.message())
        notes.append(u"Writing goes straight into the open font: close it without saving to take it back.")
        self.status.setText(u" ".join(notes) + u" " + self.status.text)
        if self.owner.package is not None and font_key(self.owner.package) == font_key(package):
            self.owner.run()  # Auto Kerning reads the classes again


CLASS_HELP = u"""<b>FreeLab Kerning Classes</b><br>
Suggests kerning classes for this master: glyphs that kern alike, on the side that faces the pair.<br><br>
<b>How</b>: an accented letter joins its base letter where most of the open-licensed fonts FreeLab
learned from class the two together on that side. Base letters share a class where most of those
fonts class them so (n with m and h, o with c, e, and q) and every two of them kern alike in this
font.<br>
<b>May need pairs of their own</b>: members that need kerning looser than the class's first glyph by
3% of the em or more, each at the pair where it differs most (an e with an accent beside T: the accent
stops it from tucking under T's bar as far as e does). The class's value will not fit that pair.<br>
<b>Pairs too close with their class's value</b>: the noted pairs the class tightens now, each with a
value of its own: the class's, loosened by the difference measured (never past 0). <i>Write checked
pairs</i> writes them as glyph pairs, which the class's value no longer reaches.<br>
<b>Sides</b>: <i>First in a pair</i> classes group glyphs by their right side (FontLab's left, or 1st,
classes); <i>second in a pair</i> by their left side.<br>
<b>The font's classes come first</b>: a suggestion makes a class only where none of its glyphs has one
on that side, or adds glyphs to the one class they share. Suggestions overlapping several classes,
or a class that kerns both sides, are shown and left as they are.<br><br>
Click this help's <i>?</i> button, then any control, for what it does."""



def main(focus=None):
    """Opens Auto Kerning; focus: a pair of glyph names to select once the font is analyzed."""
    if focus is None and raise_open("Auto Kerning"):
        return
    try:
        dialog = AutoKerningDialog()
    except Exception as exc:
        print("FreeLab Auto Kerning: %s" % exc)
        return
    sys._freelab_auto_kerning = dialog  # kept: PythonQt deletes a dialog with no Python reference
    dialog.focus = focus
    hook_menu_order()
    take_window("Auto Kerning", dialog)  # its font's window: the tool shown there gives way
    dialog.show()


if not os.environ.get("FREELAB_NO_AUTOSTART") and __name__ != "freelab_auto_kerning":
    main()


# ---------------------------------------------------------------------------
# A file saved, shown in its folder: a log line names the folder as a link (reveal_link) whose click shows the
# file selected in a new window of the system's file manager (owner's image 375: Font Builder's templates,
# Proof's PDFs). A dialog's log handler hands the link here (reveal_clicked).
# ---------------------------------------------------------------------------

REVEAL_LINK = u"freelab-reveal:"  # a log link's target: a file shown in its folder (its path's UTF-8 in hexadecimal)
CREATE_NO_WINDOW = 0x08000000  # (a process started on Windows opens no console window)


def reveal_link(path, text=None):
    """A link (rich text) a log shows: text (escaped here), else the folder that holds path; a click shows the
    file selected in its folder (reveal_clicked). The path goes in hexadecimal, which QUrl keeps as it is (it
    rewrites backslashes, spaces, and other characters a path may hold)."""
    import binascii
    path = u"%s" % path
    if text is None:
        text = os.path.normpath(os.path.dirname(path)) or path
    target = binascii.hexlify(path.encode("utf-8")).decode("ascii")
    return u'<a href="%s%s">%s</a>' % (REVEAL_LINK, target, html(text))


def revealed_path(target):
    """The path a reveal link names, or None (another link, or a broken one)."""
    import binascii
    target = u"%s" % target
    if not target.startswith(REVEAL_LINK):
        return None
    try:
        return binascii.unhexlify(target[len(REVEAL_LINK):].encode("ascii")).decode("utf-8") or None
    except (TypeError, ValueError, UnicodeError, binascii.Error):
        return None


def reveal_command(path, platform=None):
    """How the system's file manager is asked to show path selected, in a new window: on Windows the command line
    (Explorer by its full path: explorer /select,"path", its slashes made backslashes), on macOS the program and
    its arguments (open -R path: the Finder), elsewhere None (the folder is opened instead: reveal_file)."""
    import ntpath
    platform = platform or sys.platform
    path = u"%s" % path
    if platform.startswith("win"):
        root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or u"C:\\Windows"
        if not isinstance(root, type(u"")):  # (Python 2's environment is bytes)
            root = root.decode("mbcs" if os.name == "nt" else "utf-8", "replace")
        explorer = root.rstrip(u"\\/") + u"\\explorer.exe"
        return u'"%s" /select,"%s"' % (explorer, ntpath.normpath(path))
    if platform == "darwin":
        return [u"/usr/bin/open", u"-R", path]
    return None


def _shell_execute(program, parameters):
    """ShellExecuteW (Windows), for a command line Python 2's subprocess cannot pass (characters outside the ANSI
    code page): through PyDLL, which keeps the interpreter lock, since the call may send FontLab's windows
    messages (docs/DARKMODE.md: windll crashed FontLab that way). True when Windows took it."""
    import ctypes
    function = ctypes.PyDLL("shell32").ShellExecuteW
    function.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                         ctypes.c_int]
    function.restype = ctypes.c_void_p
    return (function(None, u"open", program, parameters, None, 1) or 0) > 32


def reveal_file(path, platform=None):
    """Shows path selected in a new window of the system's file manager: Explorer on Windows (no shell, no
    console window), the Finder on macOS; elsewhere its folder opened (QDesktopServices). None once asked, else
    why not, for the log. Never raises."""
    import subprocess
    path = u"%s" % path
    platform = platform or sys.platform
    try:
        if not os.path.exists(path):
            return u"it is not there anymore (moved or deleted since)"
        command = reveal_command(path, platform)
        if command is None:
            QtCore, QtGui = _qt()
            folder = os.path.dirname(os.path.abspath(path))
            if not QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder)):
                return u"no application opens folders"
            return None
        if isinstance(command, list):
            if sys.version_info[0] < 3:
                command = [part.encode("utf-8") for part in command]
            subprocess.Popen(command, close_fds=True)
            return None
        line = command
        if sys.version_info[0] < 3:
            # (Python 2 passes a command line through the ANSI code page: a path it cannot spell goes to
            # ShellExecuteW instead, Explorer and its arguments as they are)
            line = command.encode("mbcs", "replace")
            if line.decode("mbcs", "replace") != command:
                explorer, parameters = command[1:].split(u'" ', 1)
                return None if _shell_execute(explorer, parameters) else u"Windows did not start Explorer"
        subprocess.Popen(line, creationflags=CREATE_NO_WINDOW, close_fds=True)
        return None
    except Exception as exc:
        return u"%s" % exc


def reveal_clicked(target, log=None):
    """A dialog's log handler's part for reveal links (Log.link_handler): the file shown in its folder
    (reveal_file), and True; False for any other link (left to the log). Why it could not be is said in the
    log."""
    path = revealed_path(target)
    if path is None:
        return False
    why = reveal_file(path)
    if why and log is not None:
        log.add(u"%s could not be shown in its folder: %s." % (i(os.path.basename(path)), html(why)), "warning")
    return True
