"""Build Font Check's language families and other names (checks/language_families.json) from Glottolog.

Glottolog (Hammarström, Forkel, Haspelmath, and Bank; Max Planck Institute for Evolutionary
Anthropology; https://glottolog.org) classifies the world's languages into families and their
branches, and keeps the other names each language goes by. Its data is under the Creative Commons
Attribution 4.0 International license (CC BY 4.0), which a GPL-3 work may include;
checks/language_families_LICENSE keeps its notice and says what was changed.

For each language of checks/language_coverage.json (Hyperglot's) and of
checks/language_orthographies.json (the other sources', checks/train/orthographies.py), by its ISO
639-3 code, this keeps:

- its place in Glottolog's classification: the family and branches above it, as a table of nodes
  (name, parent). A code Glottolog gives to a dialect hangs under its language (Croatian under
  Serbian-Croatian-Bosnian). A language Glottolog calls an isolate goes under one node, "Language
  isolates" (FreeLab's own heading, not Glottolog's); a code Glottolog does not have, and PLACED does
  not place, is left out of the table, and Font Check lists it under "Languages Glottolog does not
  classify".
- its other names (names.csv: Glottolog's own and those it compiled from MultiTree, Lexvo, the
  Catalogue of Endangered Languages, WALS, AIATSIS, Moseley & Asher 1994, and Ruhlen 1987), but
  those its orthographies already give it, so a search finds it by any of them.

And, for a search to say why a language is not listed: the languages with an ISO 639-3 code that
Glottolog has and neither file describes, each with its name and other names
(PROVIDERS_UNLISTED_LEFT_OUT: the two largest lists are left out, which mostly repeat the others, to
keep the file small). A language described through its dialects or members (described_through:
Latvian through Standard Latvian) is not among them.

Some of those codes are ISO macrolanguages or codes Glottolog files otherwise: PLACED says
where each goes, a judgment made here and checked against the tables (the languoid must exist).

    python checks/train/families.py --download <folder> [--out <file.json>]

Python 3, no package needed. The four tables come over HTTPS from glottolog/glottolog-cldf at a
pinned commit (its release v5.4) into the folder given (outside the repository), each checked against
its SHA-256; files already there are reused. The same sources give the same bytes.
"""

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import unicodedata
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
LANGUAGES_FILE = os.path.join(CHECKS, "language_coverage.json")
ORTHOGRAPHIES_FILE = os.path.join(CHECKS, "language_orthographies.json")  # (checks/train/orthographies.py's)
OUT_FILE = os.path.join(CHECKS, "language_families.json")
LICENSE_FILE = os.path.join(CHECKS, "language_families_LICENSE")
GLOTTOLOG_VERSION = "5.4"
COMMIT = "84977fcab99ddca540550ba99984a32e908a7fcf"  # glottolog/glottolog-cldf, tag v5.4
RAW_URL = "https://raw.githubusercontent.com/glottolog/glottolog-cldf/%s/%s"
SOURCES = {  # path in the repository: SHA-256
    "cldf/languages.csv": "ecadbfd440f3d0c28182f676b7e49c6e38fd3d40774c7ae3d90bf28ca137fe90",
    "cldf/classification.nex": "0020312ad04bda75feef3cffdb15a02b7940be28576f0c5fe9944478c9d0a0ec",
    "cldf/names.csv": "0b5f8104bcaee6e28edbd92b28c03111229ecb9597f77b87872585da9a461ac3",
    "LICENSE": "945fbcb37deca05bccd7c3ca0e261679f1f5373515504fdbad68f6f3cf6f49b9",
}
CITATION = ("Hammarstr\N{LATIN SMALL LETTER O WITH DIAERESIS}m, Harald & Forkel, Robert & Haspelmath, Martin & Bank, Sebastian. 2026. Glottolog %s. "
            "Leipzig: Max Planck Institute for Evolutionary Anthropology. (Available online at "
            "https://glottolog.org)" % GLOTTOLOG_VERSION)
ISOLATES = "Language isolates"  # FreeLab's heading for the languages Glottolog marks as isolates
BOOKKEEPING = "book1242"  # Glottolog's family of retired and spurious entries: never offered as a language
LEVELS = ("language", "dialect", "family")  # a code on several languoids: the first of these
PROVIDERS_UNLISTED_LEFT_OUT = ("lexvo", "multitree")
# Hyperglot's codes Glottolog has under no languoid (ISO macrolanguages, mostly), or files otherwise:
# code: (glottocode, "is" or "beside"). "is": the code stands for that languoid (a group: the language
# hangs where the group does, and takes its other names); "beside": it hangs where that languoid does,
# and takes no name from it.
PLACED = {
    "bal": ("balo1260", "is"),  # Balochi: Balochic
    "bik": ("biko1240", "is"),  # Bikol
    "kau": ("kanu1281", "is"),  # Kanuri: Kanuric
    "kon": ("kiko1235", "is"),  # Kongo: the Kikongo language cluster
    "mlg": ("mala1537", "is"),  # Malagasy: Malagasic
    "oji": ("ojib1241", "is"),  # Ojibwa
    "ori": ("macr1269", "is"),  # Oriya: Macro-Oriya
    "que": ("quec1387", "is"),  # Quechua: Quechuan (a family of its own: the language hangs under it)
    "srd": ("camp1261", "beside"),  # Sardinian: beside Campidanese Sardinian
    "xha": ("mina1279", "is"),  # Hyperglot's xha is Minaean (ISO 639-3: inm)
    "lab": ("mino1236", "beside"),  # Linear A, the script of Minoan: beside it (unclassifiable)
    # Minang (Hyperglot's "Minang (Mirnong)"): no languoid has xrg, nor a name or a closest code that
    # points to it (Glottolog's "Minang" is a MultiTree name of Minangkabau, and Mirning, mirn1243, is
    # a group of the south coast further east). Hyperglot's own note: "an extinct dialect of ISO
    # 639-3:nys", Nyunga (nyun1247), the Noongar language, under which Glottolog lists six south-western
    # varieties (Bibbulman, Goreng, Kaniyang, Pinjarup, Wajuk, and Wardandi) and no Minang. Beside
    # Nyunga, under South-West Pama-Nyungan, not under it: Nyunga is not described through a row of a to z.
    "xrg": ("nyun1247", "beside"),
    # Codes of language_orthographies.json that Glottolog has under no languoid:
    "nwx": ("newa1246", "beside"),  # Middle Newar: beside Kathmandu Valley Newari
    "xmn": ("pahl1241", "beside"),  # Manichaean Middle Persian: beside Pahlavi
}
TREE = re.compile(r"TREE (\w+) = \[&R\] (.*);")
TOKEN = re.compile(r"\(|\)|[A-Za-z0-9_]+(?=:)")


def sha256_of(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def download(folder):
    """{path in the repository: local path} of the pinned tables, fetched when not there yet, each checked."""
    os.makedirs(folder, exist_ok=True)
    found = {}
    for relative, digest in sorted(SOURCES.items()):
        path = os.path.join(folder, "glottolog-cldf-%s-%s" % (COMMIT[:12], relative.replace("/", "_")))
        if not os.path.isfile(path):
            with urllib.request.urlopen(RAW_URL % (COMMIT, relative), timeout=300) as response:
                data = response.read()
            with open(path + ".part", "wb") as handle:
                handle.write(data)
            os.replace(path + ".part", path)
        if sha256_of(path) != digest:
            raise SystemExit("%s: SHA-256 %s, expected %s" % (path, sha256_of(path), digest))
        found[relative] = path
    return found


def table(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parents_of(path):
    """{glottocode: its parent's} from classification.nex: a Newick tree per family, each group's
    label after its children."""
    parent = {}
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    for match in TREE.finditer(text):
        stack, current = [], []
        for token in TOKEN.findall(match.group(2)):
            if token == "(":
                stack.append(current)
                current = []
            elif token == ")":
                children, current = current, stack.pop()
                current.append(children)
            else:
                if current and isinstance(current[-1], list):  # the label of the group just closed
                    for child in current.pop():
                        parent[child] = token
                current.append(token)
    return parent


def described_through(languoids, parent, described):
    """The ISO 639-3 codes of the languoids that have, below them, one with a code of described: a
    language whose dialect has it (Akan, aka, whose dialects Twi and Fante Hyperglot describes), or a
    family that stands for a macrolanguage whose member has it (Uzbek, uzb, and Northern Uzbek). Below
    is classification.nex's tree (parent), and, for a dialect it leaves out, its Language_ID."""
    up = dict(parent)
    for row in languoids:
        if row["Language_ID"] and row["ID"] not in up:
            up[row["ID"]] = row["Language_ID"]
    code_of = dict((row["ID"], row["ISO639P3code"]) for row in languoids
                   if row["ISO639P3code"] and row["Family_ID"] != BOOKKEEPING)
    found = set()
    for row in languoids:
        if row["ISO639P3code"] in described and row["Family_ID"] != BOOKKEEPING:
            at = up.get(row["ID"])
            while at is not None:
                if code_of.get(at) and code_of[at] not in described:
                    found.add(code_of[at])
                at = up.get(at)
    return found


def fold(text):
    """A name to compare: any case, its diacritics set aside."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.category(c).startswith("M"))


def clean(name):
    """A name as the tables give it, the double quotes some lists put around a name taken off."""
    return " ".join(name.split()).strip('"').strip()  # (split: at any white space, a no-break space too)


def build(paths):
    known = collections.OrderedDict()  # ISO code: the names its orthographies give it, folded
    for path in (LANGUAGES_FILE, ORTHOGRAPHIES_FILE):  # (the second: the languages Hyperglot does not describe)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            coverage = json.load(handle)
        for row in coverage["orthographies"]:
            known.setdefault(row[0], set()).update(fold(text) for text in (row[1], row[2]) if text)
    languoids = table(paths["cldf/languages.csv"])
    by_id = dict((row["ID"], row) for row in languoids)
    parent = parents_of(paths["cldf/classification.nex"])
    by_iso = {}
    for row in sorted(languoids, key=lambda row: (LEVELS.index(row["Level"]), row["ID"])):
        if row["ISO639P3code"]:
            by_iso.setdefault(row["ISO639P3code"], row)

    def ancestors(code):
        found = []
        while code in parent:
            code = parent[code]
            found.append(code)
        return found[::-1]

    def place(iso):
        """(the languoid whose names the code takes or None, the glottocodes above it root first, isolate)."""
        row, how = by_iso.get(iso), "is"
        if row is None and iso in PLACED:
            code, how = PLACED[iso]
            row = by_id[code]  # (a KeyError here: PLACED names a languoid Glottolog does not have)
        if row is None:
            return None, None, False
        if row["Level"] == "dialect":
            above = ancestors(row["Language_ID"]) + [row["Language_ID"]]
        else:
            above = ancestors(row["ID"])
            if not above and row["Level"] == "family":
                above = [row["ID"]]  # (a family of its own stands for a macrolanguage: under itself)
        return (row if how == "is" else None), above, row["Is_Isolate"] == "true" and not above

    nodes, index_of, languages, named, unplaced = [], {}, {}, {}, []

    def node(codes):
        """The index of the node at the end of a path of glottocodes, made with those above it."""
        key = tuple(codes)
        if key not in index_of:
            above = node(codes[:-1]) if len(codes) > 1 else -1
            index_of[key] = len(nodes)
            nodes.append([by_id[codes[-1]]["Name"], above])
        return index_of[key]

    isolates = []
    for iso in known:
        row, above, isolate = place(iso)
        if above is None:
            unplaced.append(iso)
            continue
        if row is not None:
            named[iso] = row
        if above:
            languages[iso] = node(above)
        elif isolate:
            isolates.append(iso)
        else:
            unplaced.append(iso)
    if isolates:
        nodes.append([ISOLATES, -1])
        for iso in isolates:
            languages[iso] = len(nodes) - 1

    names = collections.defaultdict(list)  # glottocode: [(provider, name)]
    for row in table(paths["cldf/names.csv"]):
        names[row["Language_ID"]].append((row["Provider"], clean(row["Name"])))

    def others(row, taken, left_out=()):
        """A languoid's names beyond those taken (folded), each once whatever its case and diacritics."""
        found = {}
        candidates = [clean(row["Name"])] + [name for provider, name in names.get(row["ID"], ())
                                             if provider not in left_out]
        for name in sorted(candidates):
            key = fold(name)
            if name and key not in taken and key not in found:
                found[key] = name
        return [found[key] for key in sorted(found)]

    aliases = dict((iso, others(row, known[iso])) for iso, row in named.items())
    aliases = dict((iso, found) for iso, found in aliases.items() if found)
    # The languages known and not described, each with the family it belongs to (its top node: the
    # branches are not kept for them), so Font Check can count, family by family, what it cannot check
    # yet. A family none of whose languages is described gets a node all the same; an isolate goes
    # under the isolates' node, and a language Glottolog does not classify under none (-1).
    # A language described through its dialects is not counted as not described: Latvian (lav) through
    # Standard Latvian (lvs), Akan through Twi and Fante (described_through).
    through = described_through(languoids, parent, set(known))
    unlisted, family_nodes = [], {}
    for row in sorted(languoids, key=lambda row: (row["ISO639P3code"], row["ID"])):
        iso = row["ISO639P3code"]
        if (row["Level"] != "language" or not iso or iso in known or iso in through
                or row["Family_ID"] == BOOKKEEPING):
            continue
        name = clean(row["Name"])
        above = ancestors(row["ID"])
        if above:
            at = node(above[:1])
        elif row["Is_Isolate"] == "true":
            if ISOLATES not in family_nodes:
                family_nodes[ISOLATES] = next((index for index, (title, parent_) in enumerate(nodes)
                                               if title == ISOLATES and parent_ == -1), None)
                if family_nodes[ISOLATES] is None:
                    nodes.append([ISOLATES, -1])
                    family_nodes[ISOLATES] = len(nodes) - 1
            at = family_nodes[ISOLATES]
        else:
            at = -1
        unlisted.append([iso, name, others(row, set([fold(name)]), PROVIDERS_UNLISTED_LEFT_OUT), at])
    with_code = sum(1 for row in languoids if row["Level"] == "language" and row["ISO639P3code"])

    def top_of(at):
        while nodes[at][1] != -1:
            at = nodes[at][1]
        return at

    data = collections.OrderedDict((
        ("source", "Glottolog %s (https://glottolog.org; glottolog/glottolog-cldf at %s), CC BY 4.0: see "
                   "language_families_LICENSE" % (GLOTTOLOG_VERSION, COMMIT)),
        ("citation", CITATION),
        ("counts", collections.OrderedDict((("glottolog_languages", sum(1 for row in languoids if row["Level"] == "language")),
                                            ("glottolog_languages_with_iso", with_code),
                                            ("classified", len(languages)), ("not_classified", sorted(unplaced)),
                                            # what Font Check can and cannot check, of the languages with a code
                                            ("described", len(known)), ("not_described", len(unlisted)),
                                            ("families", sum(1 for _, above in nodes if above == -1)),
                                            ("families_without_a_described_language", len(set(
                                                row[3] for row in unlisted if row[3] >= 0) - set(
                                                top_of(at) for at in languages.values())))))),
        ("isolates", ISOLATES),
        ("nodes", nodes),  # [name, the index of the node above it or -1]
        ("languages", collections.OrderedDict(sorted(languages.items()))),  # ISO code: the node it hangs under
        ("aliases", collections.OrderedDict(sorted(aliases.items()))),  # ISO code: its other names
        # [ISO code, name, other names, its family's node or -1]: languages no orthography file describes
        ("unlisted", unlisted),
    ))
    return data


def license_notice(license_path):
    with open(license_path, encoding="utf-8") as handle:
        text = handle.read().replace("\r\n", "\n").strip() + "\n"
    lines = [
        "language_families.json is derived from Glottolog %s (https://glottolog.org), by Harald" % GLOTTOLOG_VERSION,
        "Hammarstr\N{LATIN SMALL LETTER O WITH DIAERESIS}m, Robert Forkel, Martin Haspelmath, and Sebastian Bank (Leipzig: Max Planck",
        "Institute for Evolutionary Anthropology, 2026), as published in CLDF by",
        "https://github.com/glottolog/glottolog-cldf (release v%s, commit" % GLOTTOLOG_VERSION,
        "%s)," % COMMIT,
        "licensed under the Creative Commons Attribution 4.0 International license (CC BY 4.0).",
        "",
        "Changes made: checks/train/families.py keeps, for the languages of language_coverage.json",
        "and language_orthographies.json (by ISO 639-3 code), the names of the families and branches",
        "above each one in Glottolog's",
        "classification (languages.csv, classification.nex) and its other names (names.csv, which",
        "Glottolog compiled from its own records, MultiTree, Lexvo, the Catalogue of Endangered",
        "Languages, WALS, AIATSIS, Moseley & Asher 1994, and Ruhlen 1987), and, for the other",
        "languages that have an ISO 639-3 code, their name and part of their other names. A few",
        "codes Glottolog files otherwise are placed by hand (the script's PLACED table), and the",
        "isolates are grouped under a heading of FreeLab's own, \"%s\". No other part of" % ISOLATES,
        "Glottolog is included, and Glottolog does not endorse this file or FreeLab.",
        "",
        "The Creative Commons Attribution 4.0 International license, as Glottolog's repository ships",
        "it, follows.",
        "",
        "-" * 80,
        "",
    ]
    return "\n".join(lines) + text


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", required=True, help="a folder to download the pinned Glottolog tables into")
    parser.add_argument("--out", default=OUT_FILE)
    parser.add_argument("--license-out", default=LICENSE_FILE)
    args = parser.parse_args()
    paths = download(args.download)
    data = build(paths)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    with open(args.license_out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(license_notice(paths["LICENSE"]))
    print("%d languages under %d nodes, %d not classified (%s); %d with other names (%d names); %d unlisted; %d bytes" % (
        len(data["languages"]), len(data["nodes"]), len(data["counts"]["not_classified"]),
        " ".join(data["counts"]["not_classified"]), len(data["aliases"]),
        sum(len(found) for found in data["aliases"].values()), len(data["unlisted"]), os.path.getsize(args.out)))


if __name__ == "__main__":
    main()
