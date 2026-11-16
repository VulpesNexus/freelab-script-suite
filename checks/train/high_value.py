"""Which languages are worth covering first: Font Check's checks/high_value_languages.json, which its
*Display* dropdown's *High-value languages only* keeps.

The rule, from Unicode CLDR 49 alone (Unicode License V3, its notice in checks/language_orthographies_LICENSE),
so that anyone can make the list again and check it: a language is of high value when at least one holds:

1. CLDR targets it at its *modern* coverage level (common/properties/coverageLevels.txt): the languages
   the major platforms (Apple, Google, Microsoft, and the other members whose needs set CLDR's targets)
   ship their interfaces in. It stands for presence on the web and in software, which no openly licensed
   count measures (W3Techs' and Ethnologue's figures are proprietary).
2. It is official, or official in fact, in a country or territory (supplementalData.xml's territoryInfo,
   officialStatus "official" or "de_facto_official"; a regional or minority status does not count):
   a government's documents, signs, and schools are set in it.
3. At least WRITERS_MOST people read and write it: each territory's population, times the share that uses
   the language (first and second language alike), times the share of those who write it (the
   language's writingPercent where CLDR gives one, else the language's own literacyPercent, else the
   territory's literacyPercent), summed over the
   territories. Fonts are read, so the written users count, not the spoken ones.

A language is a CLDR language code; it becomes Font Check's ISO 639-3 codes through CLDR's aliases
(supplementalMetadata.xml): the three-letter form of a two-letter code (fra for fr), and the individual
languages of a macrolanguage (arb, Standard Arabic, for ar; cmn, Mandarin, for zh), which Hyperglot lists.
An orthography of such a language is of high value in the scripts CLDR writes the language in: a script
named in the locale's code (sr_Latn), else the language's primary scripts (languageData, not those marked
secondary), else its likely script (likelySubtags.xml); Japanese's Jpan stands for Han, Hiragana, and
Katakana, Korean's Kore for Hangul and Han, Hans and Hant for Han. A script label of Font Check's data that
names no script of Unicode keeps every orthography of the language.

    python checks/train/high_value.py [--cldr <cldr-common-49.zip>] [--out <file.json>]
"""

import argparse
import collections
import hashlib
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
OUT = os.path.join(CHECKS, "high_value_languages.json")
CORPUS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeLab", "corpus", "orthographies")
CLDR = os.path.join(CORPUS, "cldr-common-49.zip")
CLDR_SHA256 = "78403d8d6fb1fed6e208bf9001bf5be00bb5abfd9f8110dae062bf49309d6a89"  # (as orthographies.py pins it)
ALIASES = os.path.join(CORPUS, "unicode-17.0.0-PropertyValueAliases.txt")
DATA_FILES = (os.path.join(CHECKS, "language_coverage.json"), os.path.join(CHECKS, "language_orthographies.json"))
WRITERS_MOST = 1000000  # people who read and write a language, from which it is of high value on that count alone
OFFICIAL = ("official", "de_facto_official")
# Font Check's script labels (Hyperglot's and its other sources') that are not Unicode's names of a script
LABELS = {u"Chinese": "Hani", u"Kanji": "Hani", u"Hanja": "Hani", u"Burmese": "Mymr", u"Geʽez": "Ethi",
          u"Modern Yi": "Yiii", u"Canadian Syllabics": "Cans", u"Cree": "Cans", u"Inuktitut Syllabics": "Cans",
          u"Ojibwe Syllabics": "Cans", u"N’Ko": "Nkoo", u"Tham": "Lana", u"Pollard Phonetic": "Plrd",
          u"Ancient South Arabian": "Sarb", u"Sumero-Akkadian Cuneiforms": "Xsux"}
COMPOSITE = {"Jpan": ("Hani", "Hira", "Kana"), "Kore": ("Hang", "Hani"), "Hans": ("Hani",), "Hant": ("Hani",),
             "Hanb": ("Hani", "Bopo")}


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def attributes(text):
    return dict(re.findall(r'(\w+)="([^"]*)"', text))


def territory_figures(supplemental):
    """{CLDR code (with its script, if any): [writers, set of (territory, status)]}."""
    found = collections.defaultdict(lambda: [0.0, set()])
    info = supplemental[supplemental.find("<territoryInfo>"):supplemental.find("</territoryInfo>")]
    for match in re.finditer(r'<territory ([^>]*)>(.*?)</territory>', info, re.S):
        territory = attributes(match.group(1))
        population = float(territory.get("population", 0))
        literacy = float(territory.get("literacyPercent", 100))
        for one in re.finditer(r'<languagePopulation ([^>]*)/>', match.group(2)):
            language = attributes(one.group(1))
            share = float(language["populationPercent"]) / 100.0
            # (CLDR's order: the language's writingPercent, else its own literacyPercent, else the territory's)
            writing = float(language.get("writingPercent", language.get("literacyPercent", literacy))) / 100.0
            entry = found[language["type"]]
            entry[0] += population * share * writing
            if language.get("officialStatus") in OFFICIAL:
                entry[1].add((territory["type"], language["officialStatus"]))
    return found


def primary_scripts(supplemental):
    """{CLDR language: its primary scripts (languageData, the secondary ones left out)}."""
    found = {}
    for match in re.finditer(r'<language ([^>]*)/>', supplemental):
        one = attributes(match.group(1))
        if one.get("alt") == "secondary" or "scripts" not in one:
            continue
        found.setdefault(one["type"], []).extend(one["scripts"].split())
    return found


def likely_scripts(text):
    """{CLDR language: its likely script} (likelySubtags.xml: und_ and region-only rows left out)."""
    found = {}
    for source, target in re.findall(r'<likelySubtag from="([a-z]{2,3})" to="([^"]+)"', text):
        parts = target.split("_")
        if len(parts) > 1 and len(parts[1]) == 4:
            found[source] = parts[1]
    return found


def iso_codes(metadata):
    """{CLDR language: the ISO 639-3 codes it stands for}: its three-letter form, and the individual
    languages CLDR folds into it (macrolanguage aliases)."""
    found = collections.defaultdict(set)
    for code, target, reason in re.findall(r'<languageAlias type="([a-z]{3})" replacement="([a-z]{2,3})" reason="(\w+)"',
                                           metadata):
        if reason in ("overlong", "macrolanguage"):
            found[target].add(code)
    return found


def script_codes(path):
    """{a script's name, as Unicode writes it with spaces: its ISO 15924 code}."""
    found = {}
    with io.open(path, encoding="utf-8") as handle:
        for line in handle:
            parts = [part.strip() for part in line.split("#")[0].split(";")]
            if len(parts) >= 3 and parts[0] == "sc":
                for name in parts[2:]:
                    found[name.replace("_", " ")] = parts[1]
    return found


def label_code(label, codes):
    return LABELS.get(label) or codes.get(label)


def high_value(archive, codes, data_files=DATA_FILES, writers_most=WRITERS_MOST):
    """[[ISO 639-3 code, script label, reasons]], one per orthography of Font Check's data of high value,
    by code and label; reasons: "modern", "official" (with the territories), and the writers counted."""
    supplemental = archive.read("common/supplemental/supplementalData.xml").decode("utf-8")
    metadata = archive.read("common/supplemental/supplementalMetadata.xml").decode("utf-8")
    likely = likely_scripts(archive.read("common/supplemental/likelySubtags.xml").decode("utf-8"))
    coverage = {}
    for line in archive.read("common/properties/coverageLevels.txt").decode("utf-8").splitlines():
        parts = [part.strip() for part in line.split(";")]
        if len(parts) >= 2 and not line.startswith("#"):
            coverage[parts[0]] = parts[1]
    figures, primary, isos = territory_figures(supplemental), primary_scripts(supplemental), iso_codes(metadata)
    # Each CLDR language: its writers, its official places, modern or not, and the scripts of each
    languages = collections.defaultdict(lambda: {"writers": 0.0, "official": set(), "modern": False, "scripts": set()})

    def scripts_of(code):
        language, _, script = code.partition("_")
        if script and len(script) == 4:
            named = [script]
        else:
            named = primary.get(language) or ([likely[language]] if language in likely else [])
        return set(part for one in named for part in COMPOSITE.get(one, (one,)))

    for code, (writers, official) in figures.items():
        entry = languages[code.split("_")[0]]
        entry["writers"] += writers
        entry["official"] |= set(territory for territory, _ in official)
        if writers >= writers_most or official:
            entry["scripts"] |= scripts_of(code)
    for code, level in coverage.items():
        if level == "modern":
            entry = languages[code.split("_")[0]]
            entry["modern"] = True
            entry["scripts"] |= scripts_of(code)
    by_iso = {}
    for code, entry in languages.items():
        reasons = []
        if entry["modern"]:
            reasons.append("modern")
        if entry["official"]:
            reasons.append("official " + " ".join(sorted(entry["official"])))
        if entry["writers"] >= writers_most or reasons:
            reasons.append("writers %d" % int(round(entry["writers"])))
        if entry["modern"] or entry["official"] or entry["writers"] >= writers_most:
            for iso in set([code] if len(code) == 3 else []) | isos.get(code, set()):
                held = by_iso.get(iso)
                if held is None or held[1]["writers"] < entry["writers"]:  # (a code two languages claim: the larger)
                    by_iso[iso] = (code, entry, reasons)
    found, seen, unmapped = [], set(), set()
    for path in data_files:
        with io.open(path, encoding="utf-8") as handle:
            rows = json.load(handle)["orthographies"]
        for row in rows:
            iso, label = row[0], row[3]
            if (iso, label) in seen or iso not in by_iso:
                continue
            seen.add((iso, label))
            _, entry, reasons = by_iso[iso]
            script = label_code(label, codes)
            if script is None:
                unmapped.add(label)
            elif entry["scripts"] and script not in entry["scripts"]:
                continue
            found.append([iso, label, reasons])
    found.sort()
    return found, sorted(unmapped)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cldr", default=CLDR)
    parser.add_argument("--aliases", default=ALIASES, help="Unicode 17's PropertyValueAliases.txt")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args()
    if sha256_of(args.cldr) != CLDR_SHA256:
        raise SystemExit("%s is not CLDR 49's cldr-common-49.zip (SHA-256 differs)" % os.path.basename(args.cldr))
    found, unmapped = high_value(zipfile.ZipFile(args.cldr), script_codes(args.aliases))
    table = {"about": u"The orthographies of Font Check's languages that are of high value (its Display dropdown's "
                      u"High-value languages only), as [ISO 639-3 code, script label, reasons], made by "
                      u"checks/train/high_value.py from Unicode CLDR 49 (Unicode License V3; notice in "
                      u"language_orthographies_LICENSE). A language is of high value when CLDR targets it at its "
                      u"modern coverage level, when it is official (or official in fact) in a country or territory, "
                      u"or when at least %s people read and write it (CLDR's populations, times the share using "
                      u"the language, times its writing or literacy share). Reasons: modern; official and the "
                      u"territories; writers and their number." % format(WRITERS_MOST, ","),
             "writers_most": WRITERS_MOST}
    head = json.dumps(table, ensure_ascii=True, indent=1, sort_keys=True)[:-2]  # (one orthography a line)
    rows = u",\n  ".join(json.dumps(row, ensure_ascii=True) for row in found)
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(u"%s,\n \"orthographies\": [\n  %s\n ]\n}\n" % (head, rows))
    print("%d orthographies of %d languages; labels naming no script of Unicode: %s"
          % (len(found), len(set(row[0] for row in found)), ", ".join(unmapped) or "none"))


if __name__ == "__main__":
    sys.exit(main())
