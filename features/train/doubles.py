"""How often each letter, figure, and punctuation mark stands doubled in text (ll, ee, ss, 00, ..),
for Feature Code's alternates that take turns: the characters that double most are listed first
there, and start checked where the font has more characters with alternates than rules by character
can serve.

The counts come from andre-fuchs/kerning-pairs (https://github.com/andre-fuchs/kerning-pairs, MIT
License, Copyright 2019 André Fuchs; its notice is kept in kerning/common_pairs.txt), file
count/total/list.json: per pair of characters, its count of 300,000 pairs of text, the highest
among 24 languages (so a pair one language doubles often, Finnish aa, counts as often). Kept: the
pairs of one letter, figure, or punctuation mark twice, counted once or more, rounded, most
frequent first, as the "doubles" of features/alternates_model.json; the rest of that file stays as
it is. Auto Kerning's kerning/common_pairs.txt comes from the same counts, but holds only the pairs
fonts kern (no ll, ss, ee, or oo), so it cannot rank doubles alone.

The text counted is encyclopedia text with its markup: the punctuation mark it doubles most is the
closing brace (85 of 300,000, a template's end), then the period (72) and the hyphen (47); !! and ??
count under 1. No mark reaches the 100 that makes a letter one that doubles often, and the counts
say little of the text a handwriting font sets. So the marks that often stand doubled are taken from
conventions instead, as "doubles_typed": the marks whose double or triple Unicode encodes as a
character of its own (the ellipsis, the double exclamation and question marks, the double prime: a
compatibility decomposition into one punctuation mark repeated), and the two TeX reads doubled as
one (The TeXbook, chapter 2: -- is a dash, '' a double quotation mark).

The file is pinned: the script refuses another (SHA-256). Fetch it, then run from the repository
(Python 3):

    https://raw.githubusercontent.com/andre-fuchs/kerning-pairs/<COMMIT>/count/total/list.json
    python features/train/doubles.py <list.json> [--json features/alternates_model.json]
"""
import argparse
import hashlib
import io
import json
import os
import sys
import unicodedata

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "alternates_model.json")
COMMIT = "b7a0e29ed81a8edee7b4b6cb1935ebf7d29ca611"  # of andre-fuchs/kerning-pairs (2024-05-29; the file is of 2019-11-18)
SHA256 = "2ecb7b9bcdbeff4155a2a28a80b38e2b017903c172e6510bd4709bf51f85cccf"  # of count/total/list.json there
SOURCE = ("andre-fuchs/kerning-pairs, count/total/list.json (MIT License, Copyright 2019 André Fuchs; its notice is "
          "in kerning/common_pairs.txt): each doubled letter, figure, or punctuation mark's count of 300,000 pairs of "
          "text, the highest among 24 languages; commit %s, SHA-256 %s" % (COMMIT, SHA256))
TEX = u"-'"  # The TeXbook, chapter 2: two hyphens are a dash, two apostrophes a double quotation mark
TYPED_SOURCE = ("the punctuation marks doubled by convention: those whose double or triple Unicode %s encodes as one "
                "character (a compatibility decomposition into one punctuation mark repeated: the ellipsis, the double "
                "exclamation and question marks, the double prime), and the hyphen and the apostrophe, which TeX reads "
                "doubled as a dash and as a double quotation mark (The TeXbook, chapter 2)")


def doubles(pairs):
    """[[character, count]] of the pairs of one letter, figure, or punctuation mark twice, counted once or more."""
    found = []
    for pair, count in pairs:
        if len(pair) == 2 and pair[0] == pair[1] and unicodedata.category(pair[0])[0] in "LNP" and round(count) >= 1:
            found.append([pair[0], int(round(count))])
    return sorted(found, key=lambda row: (-row[1], row[0]))


def typed_doubles():
    """The punctuation marks doubled by convention, sorted: one that a character of the Basic Multilingual
    Plane decomposes into, repeated and alone (U+2026 is three periods, U+203C two exclamation marks), and
    TeX's two."""
    found = set(TEX)
    for code in range(0x10000):
        parts = unicodedata.normalize("NFKD", chr(code))
        if len(parts) >= 2 and len(set(parts)) == 1 and unicodedata.category(parts[0])[0] == "P":
            found.add(parts[0])
    return sorted(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("counts", help="count/total/list.json of andre-fuchs/kerning-pairs, at the pinned commit")
    parser.add_argument("--json", default=MODEL)
    args = parser.parse_args()
    with io.open(args.counts, "rb") as handle:
        data = handle.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        sys.exit("%s is not the pinned file (commit %s, SHA-256 %s): nothing written." % (args.counts, COMMIT, SHA256))
    rows = doubles(json.loads(data.decode("utf-8")))
    typed = typed_doubles()
    with io.open(args.json, encoding="utf-8") as handle:
        model = json.load(handle)
    model["doubles_source"], model["doubles"] = SOURCE, rows
    model["doubles_typed_source"], model["doubles_typed"] = TYPED_SOURCE % unicodedata.unidata_version, typed
    with io.open(args.json, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, ensure_ascii=False, indent=0))
        handle.write(u"\n")
    kinds = dict((kind, sum(1 for ch, _ in rows if unicodedata.category(ch)[0] == kind)) for kind in "LNP")
    print("%d doubled characters (%d letters, %d figures, %d punctuation marks); the first: %s" % (
        len(rows), kinds["L"], kinds["N"], kinds["P"], " ".join("U+%04X:%d" % (ord(c), n) for c, n in rows[:12])))
    print("Doubled by convention: %s" % " ".join("U+%04X" % ord(ch) for ch in typed))


if __name__ == "__main__":
    main()
