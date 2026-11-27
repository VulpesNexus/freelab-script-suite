# Install, build, and tests

## Requirements

- FontLab 7 for Windows (developed against 7.2.0), with its Python working. FontLab 7 runs scripts with a **64-bit** Python 2.7 installed on the system (a 32-bit one does not work); the FontLab 7 installer offers one. If *Window > Panels > Scripting* cannot run a one-line `print(1)`, fix that first: [PYTHON27.md](PYTHON27.md).
- Only to install from the source: LLVM (clang) or Visual Studio with the C++ tools, to build FreeLab's native libraries once. A release's folder holds them built.

## Install from a release

A [release](https://github.com/VulpesNexus/freelab-script-suite/releases) holds *FreeLab-Script-Suite-&lt;version&gt;.zip*: the *FreeLab* folder ready to use, with FreeLang's five fonts and the three native libraries built (the pixel helper, the native dark mode engine, and the auto kerning core). Nothing is compiled and no installer runs.

1. Quit FontLab.
2. Unpack the archive into FontLab's *Scripts* folder, *Documents\FontLab\FontLab 7\Scripts* (or the *Scripts* folder in the data folder set in FontLab's preferences), so that it holds a *FreeLab* folder.
3. Start FontLab and choose *Scripts > FreeLab > Set Up FreeLab*.

*Set Up FreeLab* (*windows/freelab_setup.py*) adds FreeLab's block to FontLab's startup script, the one thing a dropped folder cannot do by itself, and starts it at once. The block arranges the *Scripts > FreeLab* menu, starts tab docking, and applies dark mode at launch when it was left on; until it is there, the tools open from the menu but are listed in file order, and neither tab docking nor dark mode starts with FontLab. It is the block the installer writes, to the letter, under the same rules (below), so either way of installing can follow the other.

Dark mode makes FontLab slower, noticeably so even on a fast desktop (tab switches two to three times as long as in light mode with the native engine), and more on a modest computer. It is off until you switch it on, *Mixed* keeps the canvases (its costliest part) as FontLab draws them, and switching it off needs no restart: [DARKMODE.md](DARKMODE.md#cost).

To update, quit FontLab and unpack the newer archive over the folder. To remove FreeLab, switch dark mode off, choose *Set Up FreeLab* again and *Remove*, restart FontLab, and delete the *FreeLab* folder; the installer's `-Uninstall` does the same from a copy of the repository, and also removes dark mode's settings and cache, Auto Kerning's cache, and Proof's and the windows' settings. The other tools' settings (Font Check's saved sets among them) stay in *%LOCALAPPDATA%\FreeLab*: delete that folder to remove them too.

The native libraries are in the folder's *bin*; the tools take the ones the installer built in *%LOCALAPPDATA%\FreeLab\bin* first, where there are any. They are not signed: a virus scanner that objects to them leaves dark mode working with flipped hues in the widgets FontLab paints itself, but Auto Kerning, Auto Spacing, Kerning Check, and Glyph Compose need theirs, and installing from the source builds all three on your own computer.

## Install from the source

Start FontLab once, so that it writes its startup script, then quit it and run *tools/install-fontlab.ps1*. It:

- copies every FreeLab tool and its data into FontLab's user *Scripts* folder (*Documents\FontLab\FontLab 7\Scripts\FreeLab*). Scripts run from that folder, not from this repository: Python 2.7 cannot open files whose path the Windows ANSI code page cannot spell ([PYTHON27.md](PYTHON27.md#paths)).
- adds a marked block to FontLab's startup script that arranges the *Scripts > FreeLab* menu, starts tab docking, and applies dark mode at launch when it was left on. The startup script must be UTF-8 text, and its line endings are kept. The original startup script is kept as *startupScript.py.freelab-backup*, and each change keeps the file it replaced as *startupScript.py.freelab-previous*.
- builds the native libraries into *%LOCALAPPDATA%\FreeLab\bin* (*tools/build-native.ps1*, which can also be run on its own).

When anything required could not be done, the installer lists it and ends with exit status 1, before retiring old files if a script could not be replaced. A FreeLang font FontLab holds open is replaced at the next install. Installing again while FontLab runs is covered in [WINDOWS.md](WINDOWS.md#a-reinstall-in-the-same-session).

`-Uninstall` takes it all out again, leaving FreeLab MCP's files alone, and puts back the workspace color dark mode changed (it asks for dark mode to be switched off first when FontLab is running). Either way, the installer also removes the single startup block that FreeLab wrote when it and FreeLab MCP were one repository, which started the MCP listener too; run FreeLab MCP's installer with `-ListenerAtLaunch` to keep the listener at launch.

## FreeLang

Font Check, Glyph Compose, and Font Builder draw their lists in FreeLang, a font of five files, 31.1 MB together ([FONT-CHECK.md](FONT-CHECK.md#five-files)): *FreeLang Essential* (Latin, Greek, Cyrillic, and the other scripts in common modern use), FreeLang CJK, FreeLang+ General (every other script and symbol block), FreeLang+ Mongolian–Tibetan, and FreeLang+ Duployan. The repository and each release hold all five, in *checks/language_font*. A copy that lacks some of the last four still installs and works: Windows' own fonts then draw those scripts, most in another design and some as boxes.

## macOS

macOS is not supported yet, and nothing has run on a Mac. FontLab 7 for macOS has the same Qt, PythonQt, and Python 2.7 (installed separately on macOS 12.3 and newer), and most of FreeLab is plain Qt and Python that should carry over (a saved file's log link opens the Finder there). What is Windows-only: the installer (PowerShell, Windows paths), the native libraries (built as Windows DLLs), dark mode's title bars and its following of the system theme ([DARKMODE.md](DARKMODE.md#platforms-and-builds)), and Font Compare's list of installed fonts, which reads Windows' font folders only.

## Tests

*python tests/run_tests.py* runs everything under Python 3, including the native helper's tests, then the suites of the scripts FontLab runs (dark mode, the font tools, and tab docking) under Python 2.7, which *tools/get-python27.ps1* fetches (a hash-checked copy of the official package, kept outside the repository: [PYTHON27.md](PYTHON27.md#the-test-interpreter)). The gate fails if the Python 2.7 run is missing or the native helper is not built (*tools/build-native.ps1*).

## The tools folder

*tools/* holds the installer (*install-fontlab.ps1*), the native libraries' build script (*build-native.ps1*), the test gate's Python 2.7 fetcher (*get-python27.ps1*), CJK Vertical's vertical metrics step for an exported font (*add_vertical_metrics.py*, see [VERTICAL.md](VERTICAL.md)), *find_fringes.py*, which counts ClearType's colored edges left in a screenshot of dark mode and writes a sheet of the worst places, and the packer of a release's ready-made folder (*pack_release.py*, which builds the native libraries first and prints the archive's size and SHA-256).
