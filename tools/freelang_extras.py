"""Pack FreeLang's four optional fonts and their license into dist/FreeLang-Extras.zip, the file each
release publishes beside the repository (which keeps FreeLang-Essential.ttf alone). Run it after
checks/train/language_font.py has built the fonts; the same fonts give the same bytes (fixed dates and
modes, entries in a fixed order). Prints the archive's size and SHA-256 for the release notes."""

import hashlib
import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "checks", "language_font")
NAMES = ("FreeLang-CJK.ttf", "FreeLang-Extended-General.ttf", "FreeLang-Extended-Mongolian-Tibetan.ttf",
         "FreeLang-Extended-Duployan.ttf", "FreeLang_LICENSE")
OUT = os.path.join(ROOT, "dist", "FreeLang-Extras.zip")
STAMP = (2026, 1, 1, 0, 0, 0)  # (every entry dated alike: the archive depends on the files alone)


def main():
    missing = [name for name in NAMES if not os.path.isfile(os.path.join(FOLDER, name))]
    if missing:
        sys.exit("not built yet: %s (run checks/train/language_font.py)" % ", ".join(missing))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT + ".part", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in NAMES:
            entry = zipfile.ZipInfo(name, date_time=STAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            with open(os.path.join(FOLDER, name), "rb") as handle:
                archive.writestr(entry, handle.read())
    for attempt in range(10):  # (a virus scanner may hold the new file a moment: refused, then allowed)
        try:
            os.replace(OUT + ".part", OUT)
            break
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.5)
    with open(OUT, "rb") as handle:
        data = handle.read()
    print("%s: %d bytes, SHA-256 %s" % (os.path.relpath(OUT, ROOT), len(data), hashlib.sha256(data).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
