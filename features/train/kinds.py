"""Which characters are letters, figures, and punctuation marks, for Feature Code's alternates that
take turns: only they take turns, each looking back among its own kind.

Feature Code runs in FontLab 7's Python 2.7, whose unicodedata is Unicode 5.2: there the section
sign and the pilcrow are symbols (punctuation since Unicode 6.1), and letters and marks encoded
since are unassigned. So that a font's list is the same in FontLab and in the tests, the kinds are
not asked of the running Python but read from a table made here once: the general categories L
(letters), N (figures), and P (punctuation marks) of the Basic Multilingual Plane (FontLab's
Python has no character past it), as ranges of code points, in the "kinds" of
features/alternates_model.json; the rest of that file stays as it is. The variant builder's case
scopes (lowercase letters, capitals) are read the same way, from the "cases" beside them: the
categories Ll (lowercase) and Lu and Lt (capitals). Run from the repository (Python 3; its Unicode
version is written beside the tables):

    python features/train/kinds.py [--json features/alternates_model.json]
"""
import argparse
import io
import json
import os
import unicodedata

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "alternates_model.json")
KINDS = (("letters", "L"), ("figures", "N"), ("punctuation", "P"))
SOURCE = ("Unicode %s: the code points of the Basic Multilingual Plane whose general category is L (letters), N "
          "(figures), or P (punctuation), as hexadecimal ranges (features/train/kinds.py)")
CASES = (("lower", ("Ll",)), ("upper", ("Lu", "Lt")))
CASES_SOURCE = ("Unicode %s: the code points of the Basic Multilingual Plane whose general category is Ll (lower) or "
                "Lu or Lt (upper), as hexadecimal ranges (features/train/kinds.py)")


def ranges(categories):
    """"0041-005A 0061-007A 00AA..." of the code points to U+FFFF whose category starts with one of
    categories ("L": every letter; "Ll": the lowercase ones)."""
    found, start, last = [], None, None
    for code in range(0x10000):
        if unicodedata.category(chr(code)).startswith(tuple(categories)):
            if start is None:
                start = code
            last = code
        elif start is not None:
            found.append("%04X" % start if start == last else "%04X-%04X" % (start, last))
            start = None
    if start is not None:
        found.append("%04X" % start if start == last else "%04X-%04X" % (start, last))
    return " ".join(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", default=MODEL)
    args = parser.parse_args()
    with io.open(args.json, encoding="utf-8") as handle:
        model = json.load(handle)
    model["kinds_source"] = SOURCE % unicodedata.unidata_version
    model["kinds"] = dict((kind, ranges((letter,))) for kind, letter in KINDS)
    model["cases_source"] = CASES_SOURCE % unicodedata.unidata_version
    model["cases"] = dict((case, ranges(categories)) for case, categories in CASES)
    with io.open(args.json, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, ensure_ascii=False, indent=0))
        handle.write(u"\n")
    print("Unicode %s: %s" % (unicodedata.unidata_version, ", ".join(
        "%d ranges of %s" % (len(model[table][key].split()), key)
        for table, keys in (("kinds", KINDS), ("cases", CASES)) for key, _ in keys)))


if __name__ == "__main__":
    main()
