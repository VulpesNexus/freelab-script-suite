"""Which languages typeset with the no-break space (U+00A0) or the narrow no-break space (U+202F): Font Check's
checks/space_conventions.json.

From Unicode CLDR 49 (Unicode License V3, its notice in checks/language_orthographies_LICENSE): each base
locale's grouping separator for its Latin-digit numbers (common/main/<locale>.xml, <symbols
numberSystem="latn"><group>). A language whose numbers group thousands with one of these spaces sets it
in every long number ("12 345"), so a font for it needs that glyph: French groups with U+202F (and puts it
before ; ! ? and inside guillemets), Russian, Polish, Czech, Swedish, and many more with U+00A0. Locale
codes become ISO 639-3 codes through CLDR's own language aliases (supplementalMetadata.xml: fra for fr), a
macrolanguage's members taking its row (Norwegian's nob and nno). Only the codes are kept.

    python checks/train/spaces.py [--cldr <cldr-common-49.zip>] [--out <file.json>]
"""

import argparse
import io
import json
import os
import re
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "space_conventions.json")
CLDR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus", "orthographies", "cldr-common-49.zip")
SPACES = {u" ": "00A0", u" ": "202F"}
MEMBERS = {"nor": ("nob", "nno")}  # (CLDR's no: Norwegian, whose written languages Font Check lists apart)


def conventions(path):
    archive = zipfile.ZipFile(path)
    aliases = archive.read("common/supplemental/supplementalMetadata.xml").decode("utf-8")
    long_of = {}
    for long_code, short in re.findall(r'<languageAlias type="([a-z]{3})" replacement="([a-z]{2,3})" reason="overlong"', aliases):
        long_of.setdefault(short, long_code)
    found = dict((code, set()) for code in SPACES.values())
    for name in archive.namelist():
        if not (name.startswith("common/main/") and name.endswith(".xml")):
            continue
        locale = os.path.basename(name)[:-4]
        if "_" in locale or locale == "root":
            continue
        text = archive.read(name).decode("utf-8")
        match = re.search(r'<symbols numberSystem="latn">.*?<group>(.*?)</group>', text, re.S)
        if not match or match.group(1) not in SPACES:
            continue
        code = long_of.get(locale, locale if len(locale) == 3 else None)
        if code is None:
            continue
        found[SPACES[match.group(1)]].update((code,) + MEMBERS.get(code, ()))
    return dict((space, sorted(codes)) for space, codes in found.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cldr", default=CLDR)
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args()
    table = {"about": u"Languages whose numbers group thousands with a no-break space (U+00A0) or a narrow "
                      u"no-break space (U+202F), by ISO 639-3 code: Unicode CLDR 49's grouping separators (Unicode "
                      u"License V3; notice in language_orthographies_LICENSE), made by checks/train/spaces.py.",
             "spaces": conventions(args.cldr)}
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(table, ensure_ascii=True, indent=1, sort_keys=True) + u"\n")
    print(dict((space, len(codes)) for space, codes in table["spaces"].items()))


if __name__ == "__main__":
    main()
