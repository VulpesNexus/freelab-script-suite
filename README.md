# FreeLab

Tools for FontLab 7 that run inside it: a dark mode for its whole interface, auto kerning, auto spacing, CJK spacing, diacritics, feature code, a font check, a font comparison, and PDF proofs.

**Status: 0.3.0.** Dark mode runs in FontLab 7.2.

FreeLab MCP, the separate `freelab-mcp` repository, lets an AI app such as Claude Code read and drive the font open in FontLab. Neither needs the other; installed together, they share FontLab's *Scripts > FreeLab* menu.

## What is here

- *darkmode/*: *Scripts > FreeLab > Dark Mode* turns FontLab 7 dark (panels, tool bar, rulers, canvas, icons, and title bar) and back, without a restart, and remembers the choice for the next launch. *Scripts > FreeLab > Dark Mode Settings* chooses dark or automatic (following Windows' light or dark mode), mixed (a dark interface with FontLab's light canvases), and the shade of gray, each change shown at once, and the engine: *Script* maps the pixels FontLab drew, *Native* (experimental) the colors FontLab paints with ([docs/NATIVE.md](docs/NATIVE.md)). How it works, and what it costs: [docs/DARKMODE.md](docs/DARKMODE.md).
- *kerning/*: *Scripts > FreeLab > Auto Kerning* suggests kerning for the Latin, Armenian, Georgian, and kana pairs of the current master by halfkern's method, contour distance, and FontLab's own, shows how far they agree, and writes the pairs you approve; *Kerning Check* lists colliding pairs, entries that do nothing, and differences between masters: [docs/KERNING.md](docs/KERNING.md).
- *spacing/*: *Scripts > FreeLab > Auto Spacing* suggests sidebearings for the drawn Latin, Armenian, Georgian, and proportional kana letters of the current master, measured against the font's own straight references, shows each glyph as it is and as suggested, and changes the glyphs you approve; glyphs built from components follow: [docs/SPACING.md](docs/SPACING.md).
- *diacritics/*: *Scripts > FreeLab > Diacritics* builds the Latin, Greek (polytonic too), and Cyrillic letters with diacritics the font lacks from its letters and marks, placing each mark as the font's own accented glyphs do, no anchors needed, with an editor to move and scale each mark by hand; and places the anchors and mark features of scripts that attach their marks (Hebrew, Arabic, Devanagari, Bengali, Gujarati, Tamil, Thai, Khmer): [docs/DIACRITICS.md](docs/DIACRITICS.md).
- *cjk/*: *Scripts > FreeLab > CJK Spacing* writes palt and halt for a Japanese font's full-width kana and punctuation, trimmed as the open-licensed CJK fonts trim theirs, and sets Hangul at one width or proportionally, as Korean fonts do: [docs/CJK.md](docs/CJK.md).
- *features/*: *Scripts > FreeLab > Feature Code* sets each ligature to standard, discretionary, or off, writes alternates that take turns (for handwriting), and writes the features of the font's forms (case, locl, fractions, superiors and inferiors, ordinals, small caps, figure styles, and named stylistic sets): [docs/FEATURE-CODE.md](docs/FEATURE-CODE.md).
- *compare/*: *Scripts > FreeLab > Font Compare* compares two open fonts, or two masters of one font: the glyphs only in one, code points, metrics, outlines (how much their shapes differ), components, and anchors, drawn overlaid; the kerning, class kerning resolved; and the feature code, line by line. It changes nothing: [docs/FONT-COMPARE.md](docs/FONT-COMPARE.md).
- *proof/*: *Scripts > FreeLab > Proof* makes a PDF proof of the current font from its own outlines (character set, waterfalls, text in each script it covers, kerning and spacing strings, diacritics, and figures and punctuation) for the current master or each one, kerning applied, OpenType features not: [docs/PROOF.md](docs/PROOF.md).
- *checks/*: *Scripts > FreeLab > Font Check* ranks the characters to add by the languages they would complete, by script (and hands them to Diacritics), draws the font's vertical metrics over its tallest and deepest glyphs with suggested values, and compares the masters' outlines side by side where they do not interpolate: [docs/FONT-CHECK.md](docs/FONT-CHECK.md).
- *windows/*: tab docking, on at launch: a document tab dropped on or near the main window's tab bar goes back in at that place (FontLab otherwise makes a window of every dropped tab), so tabs reorder by dragging; one pulled farther away becomes a window, which gets a *Dock* button, and a double-click on its tab docks it too. *Scripts > FreeLab > Tab Docking* switches it off and on.
- *tests/*: the test gate (*run_tests.py*).
- *tools/*: the installer, the native helper's build script, and the test gate's Python 2.7 fetcher.

*Scripts > FreeLab* lists the font tools in the order a font is usually made (Diacritics, Auto Spacing, CJK Spacing, Auto Kerning, Kerning Check, Font Check, Font Compare, Feature Code, Proof), then dark mode, then FreeLab MCP's, with separators between them: FontLab lists a folder's scripts by file name, so FreeLab's startup block arranges the menu each time *Scripts* opens.

The font tools share their ways: a window of 1000 by 1000 pixels (or what the screen allows), a menu button at its top right that opens any other font tool, a top line with a sentence per line, a log under the list (done in green, warnings in amber, errors in red; drag its bottom edge to make it taller, and the window's bottom edge moves with it), *Restore suggestions* to put every check back as the list first came, a right-click on a row to flag its glyphs in FontLab (as its *Flag* menu does, to find them again with *Select > Same Flag* or the *Flag* section of the Font window's sidebar), a row tinted with its glyph's flag color, with a bar of it that shows on a selected row too (a pair's cell split in two, each glyph's flag on its own half), F3 and Shift+F3 to go to the next and previous flagged row, buttons that gray out when they would do nothing, a double-click on a glyph or pair to open it in a Glyph window, a click on a preview's neighboring letter to open that pair in Auto Kerning, and a fresh look at the font after an undo, a redo, or an edit in FontLab. Each write is one step of FontLab's History: *Edit > Undo* takes it back.

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
- [docs/DIACRITICS.md](docs/DIACRITICS.md), [docs/CJK.md](docs/CJK.md), [docs/FEATURE-CODE.md](docs/FEATURE-CODE.md), [docs/FONT-CHECK.md](docs/FONT-CHECK.md), [docs/FONT-COMPARE.md](docs/FONT-COMPARE.md), and [docs/PROOF.md](docs/PROOF.md): diacritics, CJK spacing, feature code, the font check, the font comparison, and proofs.
- [docs/NATIVE.md](docs/NATIVE.md): dark mode's native engine (experimental), how it is applied to FontLab, and how it compares with the script engine.
- [docs/ROADMAP.md](docs/ROADMAP.md): what comes next.
- [docs/FEATURE-SURVEY.md](docs/FEATURE-SURVEY.md): what already exists for dark mode, kerning, diacritics, and feature code.

## License

**GPL-3.0-or-later** ([LICENSE](LICENSE)). Copyright © 2026 Vixen420. It comes with no warranty.

Auto kerning ports [halfkern](https://github.com/behdad/halfkern)'s method (Copyright 2022 Google LLC, Apache License 2.0), and *kerning/common_pairs.txt* comes from [andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs) (MIT License, its notice kept in the file). *kerning/script_pairs.txt* counts pairs in public-domain Aozora Bunko works (kana) and Wikipedia text (Armenian and Georgian, CC BY-SA 4.0), as its header says. Font Check's *checks/language_coverage.json* is derived from [Hyperglot](https://github.com/rosettatype/hyperglot) (Apache License 2.0, its notice in *checks/language_coverage_LICENSE*). Diacritics names glyphs as glyphsLib's *GlyphData.xml* does (MIT License, Copyright (c) 2016 Georg Seifert, its notice in *diacritics/GlyphData_LICENSE*). The FreeLab method's model, the kerning class counts, Diacritics' mark placements, and CJK Spacing's trims were learned from fonts under the SIL Open Font License and the Apache License only; only measurements are kept, no font data. The one exception: Font Check bundles *checks/language_font/FreeLabLanguages.ttf*, a subset of 46 Noto fonts (SIL Open Font License 1.1, their notices in *checks/language_font/FreeLabLanguages_LICENSE*) holding the characters its list of languages shows, so every name and autonym is drawn in one font.
