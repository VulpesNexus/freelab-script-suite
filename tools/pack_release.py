"""Pack a release's ready-made folder into dist/FreeLab-Script-Suite-<version>.zip: the FreeLab folder as
tools/install-fontlab.ps1 lays it out in FontLab's Scripts folder, with the three native libraries built
(bin/: the pixel helper, the native dark mode engine, and the auto kerning core) and the setup script (freelab_setup.py), so that it is unpacked into the Scripts folder and set up
from FontLab's own menu, with no compiler and no installer (docs/INSTALL.md).

The files and their installed names are read from the installer's own list, so the two cannot differ. The
native libraries are built first, into dist/bin (tools/build-native.ps1), unless --bin names a folder
that holds them. The same files give the same bytes (fixed dates and modes, entries in a fixed order).
Prints the archive's size and SHA-256 for the release notes."""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLER = os.path.join(ROOT, "tools", "install-fontlab.ps1")
FOLDER = "FreeLab"  # the folder the archive holds, unpacked into FontLab's Scripts folder
STAMP = (2026, 1, 1, 0, 0, 0)  # (every entry dated alike: the archive depends on the files alone)
NOTES = """FreeLab Script Suite {version}, for FontLab 7 for Windows.

1. Quit FontLab.
2. Copy this FreeLab folder into FontLab's Scripts folder:
   Documents\\FontLab\\FontLab 7\\Scripts
3. Start FontLab and choose Scripts > FreeLab > Set Up FreeLab.
   It adds FreeLab's block to FontLab's startup script, which arranges the menu
   and starts tab docking and dark mode with FontLab.

To remove it: choose Set Up FreeLab again and Remove, restart FontLab, then
delete this folder.

FontLab 7 needs a 64-bit Python 2.7 for its scripts; its installer offers one.

https://github.com/VulpesNexus/freelab-script-suite
"""


def installed_files():
    """[(the file in the repository, its installed name, whether a copy may lack it)], from the installer."""
    text = open(INSTALLER, encoding="utf-8").read()
    table = text[text.index("$files = @("):text.index("# Scripts FreeLab once installed under other names")]
    rows = re.findall(r"@\{ From = '([^']+)'; Name = '([^']+)'(; Optional = \$true)? \}", table)
    if len(rows) != table.count("@{ From"):
        sys.exit("the installer's list of files could not be read whole")
    return [(source.replace("\\", "/"), name, bool(optional)) for source, name, optional in rows]


def version():
    text = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    return re.search(r"\*\*Status: (\d+\.\d+\.\d+)\.\*\*", text).group(1)


def _define(source, define):
    text = open(os.path.join(ROOT, source), encoding="utf-8").read()
    return re.search(r"#define %s (\d+)" % define, text).group(1)


def native_builds():
    """[(the library's file name, build-native.ps1's switches)]: the pixel helper, the native dark mode engine (named
    after both its own version and the pixel helper's, which it includes), and the auto kerning core."""
    pixels = _define("darkmode/native/freelab_pixels.c", "FREELAB_PIXELS_VERSION")
    hooks = _define("darkmode/native/freelab_hooks.c", "FREELAB_HOOKS_VERSION")
    kern = _define("kerning/native/freelab_kern.c", "FREELAB_KERN_VERSION")
    return [("freelab_pixels-v%s.dll" % pixels, []), ("freelab_hooks-v%s-%s.dll" % (hooks, pixels), ["-Hooks"]),
            ("freelab_kern-v%s.dll" % kern, ["-Kern"])]


def native_names():
    return [name for name, _switches in native_builds()]


def build_native(folder):
    """The three libraries built into folder from this copy's sources."""
    os.makedirs(folder, exist_ok=True)
    script = os.path.join(ROOT, "tools", "build-native.ps1")
    for name, extra in native_builds():
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script] + extra +
                       ["-Out", os.path.join(folder, name)], check=True)


def entries(bin_folder):
    """[(the name in the archive, the file's path or its bytes)], in the order written."""
    found = []
    for source, name, optional in installed_files():
        path = os.path.join(ROOT, source)
        if not os.path.isfile(path):
            if optional:
                sys.exit("%s is missing: a release holds all five FreeLang files" % source)
            sys.exit("%s is missing" % source)
        found.append((name, path))
    found.append(("freelab_setup.py", os.path.join(ROOT, "windows", "freelab_setup.py")))
    for name in native_names():
        path = os.path.join(bin_folder, name)
        if not os.path.isfile(path):
            sys.exit("%s is not built in %s" % (name, bin_folder))
        found.append(("bin/" + name, path))
    found.append(("LICENSE", os.path.join(ROOT, "LICENSE")))
    found.append(("README.txt", NOTES.format(version=version()).replace("\n", "\r\n").encode("utf-8")))
    return found


def pack(out, bin_folder):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out + ".part", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in entries(bin_folder):
            entry = zipfile.ZipInfo("%s/%s" % (FOLDER, name), date_time=STAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            if isinstance(source, bytes):
                archive.writestr(entry, source)
            else:
                with open(source, "rb") as handle:
                    archive.writestr(entry, handle.read())
    os.replace(out + ".part", out)
    with open(out, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return os.path.getsize(out), digest


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bin", help="a folder that holds the two native libraries already built")
    parser.add_argument("--out", help="the archive to write")
    args = parser.parse_args()
    bin_folder = args.bin
    if not bin_folder:
        bin_folder = os.path.join(ROOT, "dist", "bin")
        build_native(bin_folder)
    out = args.out or os.path.join(ROOT, "dist", "FreeLab-Script-Suite-%s.zip" % version())
    size, digest = pack(out, bin_folder)
    print("%s: %d bytes, SHA-256 %s" % (os.path.relpath(out, ROOT), size, digest))


if __name__ == "__main__":
    main()
