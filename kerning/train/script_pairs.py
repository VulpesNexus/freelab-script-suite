"""Count the letter pairs of kana, Armenian, Georgian, Cyrillic, Greek, and Devanagari text into
kerning/script_pairs.txt, the pairs Auto Kerning lists under "Common pairs" for those scripts (Latin's
come from andre-fuchs/kerning-pairs, kerning/common_pairs.txt).

- Kana: public-domain works of Aozora Bunko (https://www.aozora.gr.jp/), those in modern
  orthography (shin-ji shin-kana) whose copyright has expired; their ruby (the readings set over
  kanji), annotations, and the library's notes taken out. Pairs of two kana (small kana and the
  long vowel mark included) or of a kana and a punctuation mark.
- Armenian and Georgian: the introductions of random Wikipedia articles (hy and ka), text under
  the Creative Commons Attribution-ShareAlike 4.0 license. Pairs of two letters, or of a letter and
  a punctuation mark. Capitals: Armenian's as they start words in the text; both scripts' all-capital
  pairs (Armenian capitals, Georgian Mtavruli) from the lowercase pairs, as all-capital text sets them.

- Cyrillic, Greek, and Devanagari: letter pairs from Unilex's word frequencies (Unicode's unilex
  repository, its data/frequency files, counted from web text, case kept: a capitalized word gives
  its capital's pairs), each word's pairs counted as often as the word; punctuation pairs from the
  Universal Declaration of Human Rights in each language (NLTK's udhr2, public domain), whose running
  text has the punctuation word lists lack, weighted by their share of that text's pairs. Each
  language weighs the same: Cyrillic's are Russian, Ukrainian, Belarusian, Bulgarian, Serbian, and
  Macedonian; Greek's modern (monotonic) Greek; Devanagari's Hindi, Marathi, and Nepali (Unilex has
  no Nepali list: its declaration alone). All-capital pairs as for Armenian (Greek capitals without
  their tonos, as all-capital Greek is set).

Each script's pairs are kept, most frequent first, until they cover COVERAGE of the pairs counted
(95% for kana, whose rarer pairs are many: 99% would keep about 6,900; 99% for the others). A script
whose sources are not given keeps its section of the existing file as it is.

    python kerning/train/script_pairs.py [--aozora <folder of Aozora's zipped texts>]
        [--wikipedia hy=<intros.json> --wikipedia ka=<intros.json>]
        [--unilex <unilex archive .tar.gz> --udhr <NLTK udhr2 .zip>] [--out <file>]

Python 3. Only the counts leave the texts.
"""

import argparse
import collections
import glob
import io
import json
import os
import re
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_auto_kerning as ak  # noqa: E402

OUT = os.path.join(HERE, os.pardir, ak.SCRIPT_PAIRS_FILE)
COVERAGE = {"kana": 0.95, "armenian": 0.99, "georgian": 0.99, "cyrillic": 0.99, "greek": 0.99,
            "devanagari": 0.99, "hebrew": 0.99, "thaana": 0.99}  # a script's pairs are kept until they cover this share of its pairs
SECTIONS = ("kana", "armenian", "georgian", "cyrillic", "greek", "devanagari", "hebrew", "thaana")  # the file's order
# The languages counted for each script from Unilex and the declaration: (Unilex's code, udhr2's file).
# Unilex has no Hebrew and no Dhivehi: Hebrew's letter pairs come from An Crúbadán's character
# trigrams (CRUBADAN), Dhivehi's (Thaana) from its declaration alone.
WORD_LANGUAGES = {"cyrillic": (("ru", "rus"), ("uk", "ukr"), ("be", "bel"), ("bg", "bul"), ("sr", "srp_cyrl"), ("mk", "mkd")),
                  "greek": (("el", "ell_monotonic"),),
                  "devanagari": (("hi", "hin"), ("mr", "mar"), (None, "nep")),
                  "hebrew": ((None, "heb"),), "thaana": ((None, "div"),)}
CRUBADAN = {"hebrew": "he"}  # a script's trigram list in NLTK's crubadan package (crubadan/<code>-3grams.txt)
# Scripts whose vowel signs or points are marks over and under the letters: taken out before counting,
# so that the letters they sit on count as side by side, as they are set (not Devanagari's virama,
# which joins its letters into a conjunct).
MARKED_SCRIPTS = ("hebrew", "thaana")
SECTION_LINE = re.compile(u"^# (\\w+): (\\d+) pairs, from (.*)$")
CAPITALS_SHARE = 0.25  # all-capital pairs: this many of the lowercase pairs' counts (headings, signs)
RUBY = re.compile(u"\N{LEFT DOUBLE ANGLE BRACKET}[^\N{RIGHT DOUBLE ANGLE BRACKET}]*\N{RIGHT DOUBLE ANGLE BRACKET}")
NOTE = re.compile(u"\N{FULLWIDTH LEFT SQUARE BRACKET}\N{FULLWIDTH NUMBER SIGN}[^\N{FULLWIDTH RIGHT SQUARE BRACKET}]*"
                  u"\N{FULLWIDTH RIGHT SQUARE BRACKET}")
RUBY_START = u"\N{FULLWIDTH VERTICAL LINE}"
HEADER_RULE = u"-------------------------------------------------------"
FOOTER = u"底本："  # the line naming the printed source the text was taken from


def aozora_text(path):
    """A zipped Aozora Bunko text (Shift_JIS) as running text: its notes, ruby, and colophon out."""
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".txt")]
        if not names:
            return u""
        text = archive.read(names[0]).decode("cp932", errors="replace")
    parts = text.split(HEADER_RULE)
    if len(parts) >= 3:  # the key to the library's marks, between two rules, comes first
        text = HEADER_RULE.join(parts[2:])
    footer = text.find(FOOTER)
    if footer >= 0:
        text = text[:footer]
    return NOTE.sub(u"", RUBY.sub(u"", text)).replace(RUBY_START, u"")


def armenian_capital(ch):
    """An Armenian small letter's capital, or None (the ligature ech yiwn has none of one letter)."""
    if ch in ak.ARMENIAN_LETTERS and ch not in ak.ARMENIAN_CAPITALS:
        capital = ch.upper()
        return capital if len(capital) == 1 else None
    return None


def mtavruli(ch):
    """A Mkhedruli letter's Mtavruli capital (U+10D0 to U+1C90, and on), or None."""
    code = ord(ch)
    if 0x10D0 <= code <= 0x10FA or 0x10FD <= code <= 0x10FF:
        return chr(code - 0x10D0 + 0x1C90)
    return None


def count_pairs(texts, letters, punctuation):
    """Counter of the pairs of two letters, or of a letter and a punctuation mark, in the texts."""
    letters, punctuation = set(letters), set(punctuation)
    known = letters | punctuation
    counts = collections.Counter()
    for text in texts:
        for a, b in zip(text, text[1:]):
            if a in known and b in known and (a in letters or b in letters):
                counts[a + b] += 1
    return counts


def with_capitals(counts, capital_of):
    """The counts with the all-capital pairs of each lowercase pair added, at CAPITALS_SHARE."""
    added = collections.Counter(counts)
    for pair, count in counts.items():
        capitals = [capital_of(ch) if capital_of(ch) else (ch if not ch.isalpha() else None) for ch in pair]
        if all(capitals) and any(capital_of(ch) for ch in pair):
            added[u"".join(capitals)] += count * CAPITALS_SHARE
    return added


def script_capital(ch, script):
    """A lowercase letter's capital in all-capital text, or None: Cyrillic's as it is; Greek's without
    its tonos (all-capital Greek drops it, keeping the dialytika), final sigma's sigma."""
    if ak.category(ch) != "lower" or script not in ("cyrillic", "greek"):
        return None
    if script == "greek":
        ch = unicodedata.normalize("NFC", unicodedata.normalize("NFD", ch).replace(u"\N{COMBINING ACUTE ACCENT}", u""))
    capital = ch.upper()
    return capital if len(capital) == 1 and capital in ak.SCRIPT_LETTERS[script] else None


def word_pair_counts(words, letters):
    """Counter of the letter pairs of a word frequency list {word: count}, each counted as often as the word."""
    letters = set(letters)
    counts = collections.Counter()
    for word, count in words.items():
        for a, b in zip(word, word[1:]):
            if a in letters and b in letters:
                counts[a + b] += count
    return counts


def unilex_words(archive, language):
    """{word form: count} of a language's Unilex frequency list (data/frequency/<language>.txt)."""
    import tarfile
    with tarfile.open(archive) as tar:
        member = next((m for m in tar.getmembers() if m.name.endswith("/data/frequency/%s.txt" % language)), None)
        if member is None:
            return {}
        text = tar.extractfile(member).read().decode("utf-8")
    words = {}
    for line in text.splitlines():
        parts = line.split(u"\t")
        if len(parts) == 2 and not line.startswith(u"#") and parts[1].isdigit():
            words[parts[0]] = words.get(parts[0], 0) + int(parts[1])
    return words


def udhr_text(archive, name):
    """The declaration's text in one language, from NLTK's udhr2 package (udhr2/<name>.txt)."""
    with zipfile.ZipFile(archive) as package:
        return package.read("udhr2/%s.txt" % name).decode("utf-8")


def without_marks(text):
    """The text without its nonspacing marks (Hebrew's points, Thaana's fili)."""
    return u"".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def trigram_pair_counts(archive, code, letters):
    """Counter of the letter pairs inside An Crúbadán's character trigrams of a language (each pair
    counted as often as each trigram it is in: about twice its own count, alike for every pair)."""
    with zipfile.ZipFile(archive) as package:
        text = package.read("crubadan/%s-3grams.txt" % code).decode("utf-8")
    letters = set(letters)
    counts = collections.Counter()
    for line in text.splitlines():
        parts = line.strip().split(u" ", 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        trigram = without_marks(parts[1])
        for a, b in zip(trigram, trigram[1:]):
            if a in letters and b in letters:
                counts[a + b] += int(parts[0])
    return counts


def word_and_text_counts(script, unilex, udhr, crubadan=None):
    """A script's pairs: each language's letter pairs (Unilex, or An Crúbadán's trigrams) and
    punctuation pairs (its declaration), the punctuation weighed by its share of the declaration's
    pairs, every language weighing 1. Pairs are in text order (a right-to-left pair's right letter first)."""
    letters, punctuation = ak.SCRIPT_LETTERS[script], ak.SCRIPT_PUNCTUATION[script]
    total = collections.Counter()
    for unilex_code, udhr_name in WORD_LANGUAGES[script]:
        text = udhr_text(udhr, udhr_name)
        if script in MARKED_SCRIPTS:
            text = without_marks(text)
        running = count_pairs([text], letters, punctuation)
        all_pairs = float(sum(running.values())) or 1.0
        marks = dict((pair, count) for pair, count in running.items() if any(ch in punctuation for ch in pair))
        words = word_pair_counts(unilex_words(unilex, unilex_code), letters) if unilex_code else collections.Counter()
        if not words and crubadan and script in CRUBADAN:
            words = trigram_pair_counts(crubadan, CRUBADAN[script], letters)
        if not words:  # (no word list: the declaration's own letter pairs)
            words = collections.Counter(dict((pair, count) for pair, count in running.items() if pair not in marks))
        word_total = float(sum(words.values())) or 1.0
        share = sum(marks.values()) / all_pairs
        for pair, count in words.items():
            total[pair] += (1.0 - share) * count / word_total
        for pair, count in marks.items():
            total[pair] += count / all_pairs
    return total


def kept(counts, coverage):
    """The most frequent pairs, until they cover the share of all pairs counted."""
    total = float(sum(counts.values()))
    found, covered = [], 0.0
    for pair, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if covered >= coverage * total:
            break
        found.append(pair)
        covered += count
    return found


def existing_sections(path):
    """{script: (pairs, source)} of the sections of an existing script_pairs.txt (none when missing)."""
    sections, current = {}, None
    try:
        with io.open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip(u"\r\n")
                match = SECTION_LINE.match(line)
                if match and match.group(1) in COVERAGE:
                    current = sections[match.group(1)] = ([], match.group(3))
                elif current is not None and len(line) == 2 and not line.startswith(u"#"):
                    current[0].append(line)
    except (IOError, OSError):
        pass
    return sections


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--aozora", help="a folder of Aozora Bunko's zipped texts (kana)")
    parser.add_argument("--wikipedia", action="append", default=[], help="lang=file.json (hy, ka)")
    parser.add_argument("--unilex", help="Unilex's archive (Cyrillic, Greek, and Devanagari, with --udhr)")
    parser.add_argument("--udhr", help="NLTK's udhr2 package (zip)")
    parser.add_argument("--crubadan", help="NLTK's crubadan package (zip): Hebrew and Thaana, with --udhr")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args()
    wikipedia = dict(item.split("=", 1) for item in args.wikipedia)
    found = {}  # script: (pairs, source)
    if args.aozora:
        works = sorted(glob.glob(os.path.join(args.aozora, "*.zip")))
        kana = count_pairs((aozora_text(path) for path in works), ak.KANA_LETTERS, ak.KANA_PUNCTUATION)
        found["kana"] = (kept(kana, COVERAGE["kana"]), "%d works" % len(works))
    for lang, script, capital_of in (("hy", "armenian", armenian_capital), ("ka", "georgian", mtavruli)):
        if lang in wikipedia:
            with io.open(wikipedia[lang], encoding="utf-8") as handle:
                texts = list(json.load(handle).values())
            counts = count_pairs(texts, ak.SCRIPT_LETTERS[script], ak.SCRIPT_PUNCTUATION[script])
            found[script] = (kept(with_capitals(counts, capital_of), COVERAGE[script]), "%d articles" % len(texts))
    if args.unilex and args.udhr:
        for script in ("cyrillic", "greek", "devanagari"):
            counts = with_capitals(word_and_text_counts(script, args.unilex, args.udhr), lambda ch: script_capital(ch, script))
            languages = WORD_LANGUAGES[script]
            found[script] = (kept(counts, COVERAGE[script]), "Unilex and the declaration in %d %s" % (
                len(languages), "language" if len(languages) == 1 else "languages"))
    if args.udhr and args.crubadan:
        found["hebrew"] = (kept(word_and_text_counts("hebrew", None, args.udhr, args.crubadan), COVERAGE["hebrew"]),
                           "An Crubadan's Hebrew trigrams and the declaration in Hebrew")
        found["thaana"] = (kept(word_and_text_counts("thaana", None, args.udhr), COVERAGE["thaana"]),
                           "the declaration in Dhivehi")
    found = dict(existing_sections(args.out), **found)
    sections = [(script,) + found[script] for script in SECTIONS if script in found]
    lines = [u"# Letter pairs common in kana, Armenian, Georgian, Cyrillic, Greek, Devanagari, Hebrew, and Thaana",
             u"# text, most frequent first, a section per script; made by kerning/train/script_pairs.py, which",
             u"# counts them (only the counts are kept):",
             u"# - kana: public-domain works of Aozora Bunko (https://www.aozora.gr.jp/), modern orthography,",
             u"#   their copyright expired;",
             u"# - Armenian and Georgian: introductions of random articles of the Armenian and Georgian",
             u"#   Wikipedias (https://hy.wikipedia.org, https://ka.wikipedia.org), whose text is licensed",
             u"#   under the Creative Commons Attribution-ShareAlike 4.0 license",
             u"#   (https://creativecommons.org/licenses/by-sa/4.0/), by the Wikipedia contributors. This",
             u"#   list of counts derived from it is shared under the same license, which Creative Commons",
             u"#   declares one-way compatible with the GNU General Public License version 3.",
             u"# - Cyrillic, Greek, and Devanagari: letter pairs from the word frequencies of Unilex",
             u"#   (https://github.com/unicode-org/unilex, commit b3a9ae27, Unicode License), punctuation",
             u"#   pairs from the Universal Declaration of Human Rights (NLTK's udhr2, public domain).",
             u"# - Hebrew: letter pairs from An Crubadan's character trigrams of 2010 (Kevin Scannell; NLTK's",
             u"#   crubadan package, GNU General Public License version 3 or later), punctuation pairs from",
             u"#   the declaration; Thaana: the declaration in Dhivehi alone. Points and vowel signs (marks)",
             u"#   taken out first. Right-to-left pairs are in text order: the right letter first.",
             u"# All-capital pairs (Armenian and Cyrillic capitals, Georgian Mtavruli, Greek capitals) are the",
             u"# lowercase pairs set in capitals."]
    for script, pairs, source in sections:
        lines.append(u"# %s: %d pairs, from %s" % (script, len(pairs), source))
        lines.extend(pairs)
        print("%s: %d pairs from %s" % (script, len(pairs), source))
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(u"\n".join(lines) + u"\n")


if __name__ == "__main__":
    main()
