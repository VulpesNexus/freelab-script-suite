# Install, build, and tests

## Requirements

- FontLab 7 for Windows (developed against 7.2.0), with its Python working. FontLab 7 runs scripts with a **64-bit** Python 2.7 installed on the system (a 32-bit one does not work); the FontLab 7 installer offers one. If *Window > Panels > Scripting* cannot run a one-line `print(1)`, fix that first: [PYTHON27.md](PYTHON27.md).
- LLVM (clang) or Visual Studio with the C++ tools, to build FreeLab's native libraries once: the auto kerning core, which Auto Kerning, Auto Spacing, Kerning Check, and Glyph Compose measure with (required), and dark mode's small helper (without it, dark mode still works, with flipped hues in the widgets FontLab paints itself).

## Install

Start FontLab once, so that it writes its startup script, then quit it and run *tools/install-fontlab.ps1*. It:

- copies every FreeLab tool and its data into FontLab's user *Scripts* folder (*Documents\FontLab\FontLab 7\Scripts\FreeLab*). Scripts run from that folder, not from this repository: Python 2.7 cannot open files whose path the Windows ANSI code page cannot spell ([PYTHON27.md](PYTHON27.md#paths)).
- adds a marked block to FontLab's startup script that arranges the *Scripts > FreeLab* menu, starts tab docking, and applies dark mode at launch when it was left on. The startup script must be UTF-8 text, and its line endings are kept. The original startup script is kept as *startupScript.py.freelab-backup*, and each change keeps the file it replaced as *startupScript.py.freelab-previous*.
- builds the native libraries into *%LOCALAPPDATA%\FreeLab\bin* (*tools/build-native.ps1*, which can also be run on its own).

When anything required could not be done, the installer lists it and ends with exit status 1, before retiring old files if a script could not be replaced. A FreeLang font FontLab holds open is replaced at the next install. Installing again while FontLab runs is covered in [WINDOWS.md](WINDOWS.md#a-reinstall-in-the-same-session).

`-Uninstall` takes it all out again, leaving FreeLab MCP's files alone, and puts back the workspace color dark mode changed (it asks for dark mode to be switched off first when FontLab is running). Either way, the installer also removes the single startup block that FreeLab wrote when it and FreeLab MCP were one repository, which started the MCP listener too; run FreeLab MCP's installer with `-ListenerAtLaunch` to keep the listener at launch.

## FreeLang Extras

Font Check draws its lists in FreeLang, a font of five files ([FONT-CHECK.md](FONT-CHECK.md#five-files)). The repository holds the first, *FreeLang Essential* (Latin, Greek, Cyrillic, and the other scripts in common modern use). The four others come with each [release](https://github.com/VulpesNexus/freelab-script-suite/releases) as *FreeLang-Extras.zip* (15.6 MB, 29.2 MB unpacked), which *tools/freelang_extras.py* packs: FreeLang CJK, FreeLang+ General (every other script and symbol block), FreeLang+ Mongolian–Tibetan, and FreeLang+ Duployan. Unpack it into *checks/language_font* before running the installer. Without them, Font Check still works and takes those scripts from Windows' own fonts, which draw most of them in another design and some as boxes.

## macOS

macOS is not supported yet, and nothing has run on a Mac. FontLab 7 for macOS has the same Qt, PythonQt, and Python 2.7 (installed separately on macOS 12.3 and newer), and most of FreeLab is plain Qt and Python that should carry over (a saved file's log link opens the Finder there). What is Windows-only: the installer (PowerShell, Windows paths), the native libraries (built as Windows DLLs), dark mode's title bars and its following of the system theme ([DARKMODE.md](DARKMODE.md#platforms-and-builds)), and Font Compare's list of installed fonts, which reads Windows' font folders only.

## Tests

*python tests/run_tests.py* runs everything under Python 3, including the native helper's tests, then the suites of the scripts FontLab runs (dark mode, the font tools, and tab docking) under Python 2.7, which *tools/get-python27.ps1* fetches (a hash-checked copy of the official package, kept outside the repository: [PYTHON27.md](PYTHON27.md#the-test-interpreter)). The gate fails if the Python 2.7 run is missing or the native helper is not built (*tools/build-native.ps1*).

## The tools folder

*tools/* holds the installer (*install-fontlab.ps1*), the native libraries' build script (*build-native.ps1*), the test gate's Python 2.7 fetcher (*get-python27.ps1*), CJK Vertical's vertical metrics step for an exported font (*add_vertical_metrics.py*, see [VERTICAL.md](VERTICAL.md)), and the packer of a release's *FreeLang-Extras.zip* (*freelang_extras.py*).
