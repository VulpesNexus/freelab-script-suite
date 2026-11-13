"""Which script each character belongs to, for the scopes of Feature Code's variant builder (every
Latin glyph, every Cyrillic glyph, and so on: the scripts the open font has).

Feature Code runs in FontLab 7's Python 2.7, whose unicodedata has no script property and knows
Unicode 5.2 only. So that a font's scopes are the same in FontLab and in the tests, a character's
script is not worked out by the running Python (from its name, say) but read from a table made here
once: Unicode's Script property for the Basic Multilingual Plane (FontLab's Python has no character
past it), as ranges of code points per script, in the "scripts" of features/alternates_model.json;
the rest of that file stays as it is. Common, Inherited, and Unknown are left out: figures and most
punctuation marks belong to no script, and a script's scope does not take them.

The property is read from fontTools' copy of Unicode's Scripts.txt (fontTools.unicodedata; its
Unicode version is written beside the table). Run from the repository (Python 3, with fontTools):

    python features/train/scripts.py [--json features/alternates_model.json]
"""
import argparse
import io
import json
import os
import re

from fontTools import unicodedata as scripts_data
from fontTools.unicodedata import Scripts

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "alternates_model.json")
NO_SCRIPT = ("Zyyy", "Zinh", "Zzzz")  # Common, Inherited, Unknown
SOURCE = ("Unicode %s: the Script property of the code points of the Basic Multilingual Plane, as hexadecimal "
          "ranges per script, without Common, Inherited, and Unknown (features/train/scripts.py, from fontTools' "
          "copy of Scripts.txt)")


def unicode_version():
    """The Unicode version of fontTools' Scripts.txt ("Scripts-17.0.0.txt" in its header)."""
    with io.open(Scripts.__file__, encoding="utf-8") as handle:
        match = re.search(r"Scripts-(\d+\.\d+)(?:\.\d+)?\.txt", handle.read(2000))
    return match.group(1) if match else "of fontTools %s" % __import__("fontTools").version


def script_ranges():
    """{script's name: "0041-005A 0061-007A 00AA..."} for the code points to U+FFFF."""
    found, start, last, held = {}, None, None, None
    for code in range(0x10001):
        script = scripts_data.script(chr(code)) if code < 0x10000 else None
        if script in NO_SCRIPT:
            script = None
        if script != held:
            if held is not None:
                found.setdefault(scripts_data.script_name(held).replace("_", " "), []).append(
                    "%04X" % start if start == last else "%04X-%04X" % (start, last))
            held, start = script, code
        last = code
    return dict((name, " ".join(parts)) for name, parts in found.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", default=MODEL)
    args = parser.parse_args()
    with io.open(args.json, encoding="utf-8") as handle:
        model = json.load(handle)
    model["scripts_source"] = SOURCE % unicode_version()
    model["scripts"] = script_ranges()
    with io.open(args.json, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(model, ensure_ascii=False, indent=0))
        handle.write(u"\n")
    print("Unicode %s: %d scripts, %d ranges" % (unicode_version(), len(model["scripts"]), sum(
        len(ranges.split()) for ranges in model["scripts"].values())))


if __name__ == "__main__":
    main()
