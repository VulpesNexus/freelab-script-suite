"""Count the letter pairs of kana, Armenian, and Georgian text into kerning/script_pairs.txt, the
pairs Auto Kerning lists under "Common pairs" for those scripts (Latin's come from
andre-fuchs/kerning-pairs, kerning/common_pairs.txt).

- Kana: public-domain works of Aozora Bunko (https://www.aozora.gr.jp/), those in modern
  orthography (shin-ji shin-kana) whose copyright has expired; their ruby (the readings set over
  kanji), annotations, and the library's notes taken out. Pairs of two kana (small kana and the
  long vowel mark included) or of a kana and a punctuation mark.
- Armenian and Georgian: the introductions of random Wikipedia articles (hy and ka), text under
  the Creative Commons Attribution-ShareAlike 4.0 license. Pairs of two letters, or of a letter and
  a punctuation mark. Capitals: Armenian's as they start words in the text; both scripts' all-capital
  pairs (Armenian capitals, Georgian Mtavruli) from the lowercase pairs, as all-capital text sets them.

Each script's pairs are kept, most frequent first, until they cover COVERAGE of the pairs counted
(95% for kana, whose rarer pairs are many: 99% would keep about 6,900; 99% for the others).

    python kerning/train/script_pairs.py --aozora <folder of Aozora's zipped texts>
        --wikipedia hy=<intros.json> --wikipedia ka=<intros.json> [--out <file>]

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
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))
os.environ["FREELAB_NO_AUTOSTART"] = "1"
import freelab_auto_kerning as ak  # noqa: E402

OUT = os.path.join(HERE, os.pardir, ak.SCRIPT_PAIRS_FILE)
COVERAGE = {"kana": 0.95, "armenian": 0.99, "georgian": 0.99}  # a script's pairs are kept until they cover this share of its pairs in the text
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--aozora", required=True)
    parser.add_argument("--wikipedia", action="append", default=[], help="lang=file.json (hy, ka)")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args()
    wikipedia = dict(item.split("=", 1) for item in args.wikipedia)
    sections = []
    works = sorted(glob.glob(os.path.join(args.aozora, "*.zip")))
    kana = count_pairs((aozora_text(path) for path in works), ak.KANA_LETTERS, ak.KANA_PUNCTUATION)
    sections.append(("kana", kept(kana, COVERAGE["kana"]), "%d works" % len(works)))
    for lang, script, capital_of in (("hy", "armenian", armenian_capital), ("ka", "georgian", mtavruli)):
        with io.open(wikipedia[lang], encoding="utf-8") as handle:
            texts = list(json.load(handle).values())
        counts = count_pairs(texts, ak.SCRIPT_LETTERS[script], ak.SCRIPT_PUNCTUATION[script])
        sections.append((script, kept(with_capitals(counts, capital_of), COVERAGE[script]), "%d articles" % len(texts)))
    lines = [u"# Letter pairs common in kana, Armenian, and Georgian text, most frequent first, a section per",
             u"# script; made by kerning/train/script_pairs.py, which counts them (only the counts are kept):",
             u"# - kana: public-domain works of Aozora Bunko (https://www.aozora.gr.jp/), modern orthography,",
             u"#   their copyright expired;",
             u"# - Armenian and Georgian: introductions of random articles of the Armenian and Georgian",
             u"#   Wikipedias (https://hy.wikipedia.org, https://ka.wikipedia.org), whose text is licensed",
             u"#   under the Creative Commons Attribution-ShareAlike 4.0 license",
             u"#   (https://creativecommons.org/licenses/by-sa/4.0/), by the Wikipedia contributors. This",
             u"#   list of counts derived from it is shared under the same license, which Creative Commons",
             u"#   declares one-way compatible with the GNU General Public License version 3.",
             u"# All-capital pairs (Armenian capitals, Georgian Mtavruli) are the lowercase pairs set in capitals."]
    for script, pairs, source in sections:
        lines.append(u"# %s: %d pairs, from %s" % (script, len(pairs), source))
        lines.extend(pairs)
        print("%s: %d pairs from %s" % (script, len(pairs), source))
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(u"\n".join(lines) + u"\n")


if __name__ == "__main__":
    main()
