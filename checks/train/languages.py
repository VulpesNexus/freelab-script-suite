"""Build Font Check's language data (checks/language_coverage.json) from Hyperglot's database.

Hyperglot (Rosetta Type, https://github.com/rosettatype/hyperglot) documents, for each language, the
characters its orthographies need: base (required in common text), auxiliary (loan words, names,
deprecated letters), and marks (combining marks the orthography needs on their own). Its data is
under the Apache License 2.0, which GPL-3 works may include; checks/language_coverage_LICENSE keeps
its notice.

This reads a release's YAML files, resolves their inheritance (<iso>, <iso auxiliary>, <iso Script>,
<default Script>), and keeps, per orthography, what Font Check compares a font with:

- the language's name, autonym, script, status (living, historical, constructed), validity, and
  number of speakers;
- its base and auxiliary characters, in Unicode's composed form (NFC), each a character or a letter
  with combining marks Unicode has no single character for (n with a dieresis); digraphs (ch, dz) are
  split into their letters, which Hyperglot does not check as units either;
- the marks the orthography needs beyond those its characters decompose into, as Hyperglot's own
  "required marks" (marks listed on their own, and the marks of unencoded letter-and-mark clusters).

Primary orthographies only (and the historical ones of historical languages), as Hyperglot's own
language detection does; secondary orthographies and transliterations are left out.

    python checks/train/languages.py --download <folder> [--out <file.json>]
    python checks/train/languages.py --source <hyperglot folder or .tar.gz> [--out <file.json>]

Python 3 with PyYAML. --download fetches the pinned release (HYPERGLOT_TAG) from GitHub over HTTPS
into the folder given and checks its SHA-256.
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import unicodedata
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(HERE, os.pardir, "language_coverage.json")
HYPERGLOT_TAG = "0.8.2"
HYPERGLOT_URL = "https://codeload.github.com/rosettatype/hyperglot/tar.gz/refs/tags/%s" % HYPERGLOT_TAG
HYPERGLOT_SHA256 = "0e41da89a3cd9edd0e88b6042a886dfba8ea9173ec0d67234c775e4eac774aca"
MARK_BASE = "\N{DOTTED CIRCLE}"
TAG = re.compile(r"<([A-Za-z'\N{MODIFIER LETTER REVERSED COMMA} ]*)>")
ATTRIBUTES = ("base", "auxiliary", "marks")
STATUSES = ("primary", "local", "secondary", "historical", "transliteration")  # Hyperglot's order of preference
KEPT_STATUSES = ("primary", "local")


def download(folder):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "hyperglot-%s.tar.gz" % HYPERGLOT_TAG)
    if not os.path.isfile(path):
        with urllib.request.urlopen(HYPERGLOT_URL, timeout=120) as response, open(path, "wb") as handle:
            handle.write(response.read())
    digest = sha256_of(path)
    if digest != HYPERGLOT_SHA256:
        raise SystemExit("%s: SHA-256 %s, expected %s" % (path, digest, HYPERGLOT_SHA256))
    return path


def sha256_of(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def read_yaml_files(source):
    """{file stem: parsed YAML} of Hyperglot's data folder, and its extra_data/default.yaml, read from
    a release archive or an extracted folder (nothing in it is run)."""
    found, default = {}, None
    if os.path.isfile(source):
        with tarfile.open(source, "r:gz") as archive:
            for member in archive.getmembers():
                parts = member.name.split("/")
                if not member.isfile() or not member.name.endswith(".yaml") or "lib" not in parts:
                    continue
                text = archive.extractfile(member).read().decode("utf-8")
                if parts[-2] == "data":
                    found[parts[-1][:-5]] = yaml.safe_load(io.StringIO(text))
                elif parts[-2:] == ["extra_data", "default.yaml"]:
                    default = yaml.safe_load(io.StringIO(text))
    else:
        root = os.path.join(source, "lib", "hyperglot") if os.path.isdir(os.path.join(source, "lib")) else source
        data = os.path.join(root, "data")
        for name in sorted(os.listdir(data)):
            if name.endswith(".yaml"):
                with open(os.path.join(data, name), encoding="utf-8") as handle:
                    found[name[:-5]] = yaml.safe_load(handle)
        with open(os.path.join(root, "extra_data", "default.yaml"), encoding="utf-8") as handle:
            default = yaml.safe_load(handle)
    if not found or default is None:
        raise SystemExit("%s: no Hyperglot data found" % source)
    found["default"] = default
    return found


def orthography_of(languages, iso, script, status):
    """A language's orthography for a script (or any), the most preferred status first."""
    language = languages.get(iso)
    if not isinstance(language, dict):
        raise KeyError("no language %s" % iso)
    matches = [o for o in language.get("orthographies") or []
               if (script is None or o.get("script") == script) and (status is None or (o.get("status") or "primary") == status)]
    if not matches:
        raise KeyError("no orthography of %s for %s %s" % (iso, script, status))
    return sorted(matches, key=lambda o: STATUSES.index(o.get("status") or "primary"))[0]


def resolve(languages, scripts, value, attribute, script, depth=0):
    """value with each <iso ...> tag replaced by what it names (recursively)."""
    if not isinstance(value, str) or depth > 10:
        return value or ""

    def replace(match):
        parts = match.group(1).split()
        if not parts or len(parts[0]) < 3:
            return match.group(0)
        iso, wanted, status, wanted_script = parts[0], attribute, None, None
        for part in parts[1:]:
            if part in ATTRIBUTES or part in ("punctuation", "numerals", "currency"):
                wanted = part
            elif part in STATUSES:
                status = part
            elif part in scripts or part[:1].isupper():
                wanted_script = part
        try:
            source = orthography_of(languages, iso, wanted_script or script, status)
        except KeyError:
            if wanted_script is None and attribute not in ATTRIBUTES:
                source = orthography_of(languages, iso, None, status)
            else:
                raise
        return " %s " % resolve(languages, scripts, source.get(wanted) or "", wanted, wanted_script or script, depth + 1)

    return TAG.sub(replace, value)


def is_mark(ch):
    return unicodedata.category(ch).startswith("M")


def items_of(text):
    """The characters of a Hyperglot list: NFC clusters (a letter and the combining marks Unicode has
    no single character for), digraphs split into letters, the dotted circle taken off marks."""
    found = []
    for raw in text.split():
        raw = unicodedata.normalize("NFC", raw.replace(MARK_BASE, ""))
        if not raw:
            continue
        clusters, current = [], ""
        for ch in raw:
            if current and is_mark(ch):
                current += ch
            else:
                if current:
                    clusters.append(current)
                current = ch
        if current:
            clusters.append(current)
        for cluster in clusters:
            if cluster not in found:
                found.append(cluster)
    return found


def decomposed_marks(items):
    marks = []
    for item in items:
        for ch in unicodedata.normalize("NFD", item):
            if is_mark(ch) and ch not in marks:
                marks.append(ch)
    return marks


def required_marks(marks, base, auxiliary):
    """Hyperglot's required base marks: the listed marks no base or auxiliary character decomposes
    into, and the marks of base clusters Unicode has no single character for."""
    listed = [m for m in items_of(marks) if all(is_mark(ch) for ch in m)]
    listed = [ch for m in listed for ch in m]
    derived = set(decomposed_marks(base)) | set(decomposed_marks(auxiliary))
    found = [m for m in listed if m not in derived]
    for item in base:
        if len(item) > 1:
            found += [ch for ch in item[1:] if is_mark(ch)]
    return "".join(sorted(set(found), key=found.index))


def speakers_of(language):
    try:
        return int(language.get("speakers") or 0)
    except (TypeError, ValueError):
        return 0  # ("unknown")


def build(languages):
    scripts = set()
    for language in languages.values():
        for o in (language or {}).get("orthographies") or []:
            if o.get("script"):
                scripts.add(o["script"])
    rows, skipped, texts = [], 0, []

    def text(items):
        """A list's index in texts: lists several orthographies share (Chinese's) are kept once."""
        joined = " ".join(items)
        if joined not in texts:
            texts.append(joined)
        return texts.index(joined)

    for iso in sorted(languages):
        language = languages[iso]
        if iso == "default" or not isinstance(language, dict):
            continue
        status = language.get("status") or "living"
        for o in language.get("orthographies") or []:
            o_status = o.get("status") or "primary"
            if not (o_status in KEPT_STATUSES or (status == "historical" and o_status == "historical")):
                continue
            script = o.get("script") or ""
            try:
                base = items_of(resolve(languages, scripts, o.get("base"), "base", script))
                auxiliary = items_of(resolve(languages, scripts, o.get("auxiliary"), "auxiliary", script))
                marks = resolve(languages, scripts, o.get("marks"), "marks", script)
            except KeyError as exc:
                skipped += 1
                print("skipped %s %s: %s" % (iso, script, exc), file=sys.stderr)
                continue
            marks = required_marks(marks or "", base, auxiliary)  # (lone marks in base or auxiliary: not required)
            base = [item for item in base if not all(is_mark(ch) for ch in item)]
            auxiliary = [item for item in auxiliary if item not in base and not all(is_mark(ch) for ch in item)]
            if not base:
                continue
            rows.append([iso.rstrip("_"), language.get("preferred_name") or language.get("name") or iso,  # (con_.yaml: con)
                         o.get("autonym") or language.get("autonym") or "", script, status[:1],
                         language.get("validity") or "todo", speakers_of(language),
                         text(base), text(auxiliary), marks])
    return rows, texts, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", help="a Hyperglot release (.tar.gz) or its extracted folder")
    parser.add_argument("--download", help="a folder to download the pinned Hyperglot release into")
    parser.add_argument("--out", default=OUT_FILE)
    args = parser.parse_args()
    if not args.source and not args.download:
        parser.error("give --source or --download")
    source = args.source or download(args.download)
    rows, texts, skipped = build(read_yaml_files(source))
    data = {"source": "Hyperglot %s (https://github.com/rosettatype/hyperglot), Apache License 2.0: see "
                      "language_coverage_LICENSE" % HYPERGLOT_TAG,
            "columns": ["iso", "name", "autonym", "script", "status", "validity", "speakers", "base", "auxiliary",
                        "marks"],
            "status": {"l": "living", "h": "historical", "c": "constructed"},
            "orthographies": rows,
            "texts": texts}  # base and auxiliary: an index in texts, each a list of characters split by spaces
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    print("%d orthographies of %d languages written to %s (%d skipped)" % (
        len(rows), len(set(row[0] for row in rows)), os.path.basename(args.out), skipped))


if __name__ == "__main__":
    main()
