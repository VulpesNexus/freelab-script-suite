# FreeLab

Tools for FontLab 7 that run inside it: a dark mode for its whole interface, auto kerning, auto spacing, accented glyphs, and feature code.

**Status: 0.3.0.** Dark mode runs in FontLab 7.2.

FreeLab MCP, the separate `freelab-mcp` repository, lets an AI app such as Claude Code read and drive the font open in FontLab. Neither needs the other; installed together, they share FontLab's *Scripts > FreeLab* menu.

## What is here

- *darkmode/*: *Scripts > FreeLab > Toggle Dark Mode* turns FontLab 7 dark (panels, tool bar, rulers, canvas, icons, and title bar) and back, without a restart, and remembers the choice for the next launch. *Scripts > FreeLab > Dark Mode Settings* chooses dark or automatic (following Windows' light or dark mode), mixed (a dark interface with FontLab's light canvases), and the shade of gray, each change shown at once, and the engine: *Script* maps the pixels FontLab drew, *Native* (experimental) the colors FontLab paints with ([docs/NATIVE.md](docs/NATIVE.md)). How it works, and what it costs: [docs/DARKMODE.md](docs/DARKMODE.md).
- *kerning/*: *Scripts > FreeLab > Auto Kerning* suggests kerning for the Latin pairs of the current master by halfkern's method, contour distance, and FontLab's own, shows how far they agree, and writes the pairs you approve; *Kerning Check* lists colliding pairs, entries that do nothing, and differences between masters: [docs/KERNING.md](docs/KERNING.md).
- *spacing/*: *Scripts > FreeLab > Auto Spacing* suggests sidebearings for the drawn Latin letters of the current master, measured against the font's own straight references, shows each glyph as it is and as suggested, and changes the glyphs you approve; glyphs built from components follow: [docs/SPACING.md](docs/SPACING.md).
- *diacritics/*: *Scripts > FreeLab > Accented Glyphs* builds the accented letters the font lacks from its letters and marks, placing each mark as the font's own accented glyphs do, no anchors needed: [docs/ACCENTS.md](docs/ACCENTS.md).
- *features/*: *Scripts > FreeLab > Feature Code* sets each ligature to standard, discretionary, or off, and writes alternates that take turns (for handwriting): [docs/FEATURE-CODE.md](docs/FEATURE-CODE.md).
- *tests/*: the test gate (*run_tests.py*).
- *tools/*: the installer, the native helper's build script, and the test gate's Python 2.7 fetcher.

*Scripts > FreeLab* lists the font tools in the order a font is usually made (Accented Glyphs, Auto Spacing, Auto Kerning, Kerning Check, Feature Code), then dark mode, then FreeLab MCP's, with separators between them: FontLab lists a folder's scripts by file name, so FreeLab's startup block arranges the menu each time *Scripts* opens.

## Requirements

- FontLab 7 for Windows (developed against 7.2.0), with its Python working. FontLab 7 runs scripts with a **64-bit** Python 2.7 installed on the system (a 32-bit one does not work); the FontLab 7 installer offers one. If *Window > Panels > Scripting* cannot run a one-line `print(1)`, fix that first: [docs/PYTHON27.md](docs/PYTHON27.md).
- LLVM (clang) or Visual Studio with the C++ tools, to build dark mode's small native helper once. Without it, dark mode still works, with flipped hues in the widgets FontLab paints itself.

## Install

Start FontLab once, so that it writes its startup script, then quit it and run *tools/install-fontlab.ps1*. It copies the dark-mode scripts into FontLab's user *Scripts* folder (*Documents\FontLab\FontLab 7\Scripts\FreeLab*), adds a marked block to FontLab's startup script that applies dark mode at launch when it was left on, and builds the native helper into *%LOCALAPPDATA%\FreeLab\bin*. The original startup script is kept as *startupScript.py.freelab-backup*, and `-Uninstall` takes it all out again, leaving FreeLab MCP's files alone. Either way it also removes the single block that FreeLab wrote before the MCP and the tools were split, which started the MCP listener too; run FreeLab MCP's installer with `-ListenerAtLaunch` to keep that. The startup script must be UTF-8 text, and its line endings are kept. Scripts run from that folder, not from this repository: Python 2.7 cannot open files whose path the Windows ANSI code page cannot spell.

## Tests

```
python tests/run_tests.py
```

It runs everything under Python 3, including the native helper's tests, then the dark-mode tests under Python 2.7, which *tools/get-python27.ps1* fetches (a hash-checked copy of the official package, kept outside the repository). The gate fails if the Python 2.7 run is missing or the native helper is not built (*tools/build-native.ps1*).

## More

- [docs/DARKMODE.md](docs/DARKMODE.md): how FontLab 7 colors itself, and how dark mode turns each part dark.
- [docs/KERNING.md](docs/KERNING.md): auto kerning, how it measures, and its limits.
- [docs/SPACING.md](docs/SPACING.md): auto spacing, how it measures, and its limits.
- [docs/ACCENTS.md](docs/ACCENTS.md) and [docs/FEATURE-CODE.md](docs/FEATURE-CODE.md): accented glyphs and feature code.
- [docs/NATIVE.md](docs/NATIVE.md): dark mode's native engine (experimental), how it is applied to FontLab, and how it compares with the script engine.
- [docs/ROADMAP.md](docs/ROADMAP.md): what comes next.
- [docs/FEATURE-SURVEY.md](docs/FEATURE-SURVEY.md): what already exists for dark mode, kerning, diacritics, and feature code.

## License

**GPL-3.0-or-later** ([LICENSE](LICENSE)). Copyright © 2026 Vixen420. It comes with no warranty.

Auto kerning ports [halfkern](https://github.com/behdad/halfkern)'s method (Copyright 2022 Google LLC, Apache License 2.0), and *kerning/common_pairs.txt* comes from [andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs) (MIT License, its notice kept in the file). The FreeLab method's model, the kerning class counts, and Accented Glyphs' mark placements were learned from fonts under the SIL Open Font License and the Apache License only; only measurements are kept, no font data.
