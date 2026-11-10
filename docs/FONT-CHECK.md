# Font Check

*Scripts > FreeLab > Font Check* holds three lists for the current font: the languages its characters cover, its vertical metrics, and what keeps its masters from interpolating. It changes nothing in the font: its only buttons that act open Diacritics (which writes only when its own button is clicked), FontLab's Font Info, or a Glyph window.

The window works as Kerning Check's does: a tab per list, a settings row and a top line with the counts in bold, grid lines between the cells, a log under the list, previews where a picture helps, a right-click on a glyph's row to flag the glyph in FontLab (F3 and Shift+F3 go to the next and previous flagged row), *Show in Glyph window* (or a double-click), each list checked as its tab is first shown and again after an undo, a redo, or an edit in FontLab, and the dialog's ? button to explain any control.

## Coverage

Each language's orthography, from [Hyperglot](https://github.com/rosettatype/hyperglot) (Rosetta Type, Apache License 2.0), names the characters it is written with: its **base** characters (required in common text), its **auxiliary** ones (loan words, names, letters falling out of use), and the **marks** it needs on their own. A language is:

- **covered** when the font has every base and auxiliary character and every mark;
- **nearly covered** when it misses at most the number of base characters set (3 to start with; a missing mark counts as one), or only auxiliary characters: the list names what it misses;
- **missed** otherwise.

The list groups the languages by script. Within a script the nearly covered languages come first, the fewest characters missing first, then the covered ones, then the missed ones, the most spoken first. Scripts the font has (at least five of their letters, or a language covered) come first and open; the others come last, folded.

A character the font lacks as one character still counts when the font can **compose** it: Unicode's decomposition (NFD) gives its letter and combining marks, the font has them, and the letter has an anchor each mark attaches to (*top* on the letter, *_top* on the mark), so the font's mark feature puts them together. The longest part the font has is used, so *ḗ* stands on the font's *ē* with an acute. Such a language is marked *composed* and its row's tooltip lists the letters. A character given decomposed (Hyperglot writes some letters as a base and marks) counts when the font has its composed form (NFC). A letter and a mark the font has but no anchor joins are listed as missing, and the tooltip says the font has their parts; unchecking *Count letters its anchors compose* counts only the font's own characters. Hangul syllables do not compose from jamo here (jamo are letters, not marks), nor modifier letters from their base letters.

Historical languages (no native speakers left: Latin, Ancient Greek) are left out unless *Historical languages* is checked; constructed ones (Esperanto) are in.

Double-clicking a language, or *Show in Glyph window*, opens its missing characters (and the ones it composes) in a new Glyph tab, where the missing ones show as FontLab's placeholders. *Build with Diacritics* is clickable when Diacritics' own planning (its `plan`, asked once per language) can build at least one of the language's missing letters from the font's letters and marks: it opens Diacritics. Diacritics today takes no list of letters: it opens on all its blocks, the missing letters among the ones it lists, checked as it checks every letter it can build. Font Check calls `main(characters=[...])` first and falls back to `main()` when Diacritics does not take them; for Diacritics to list only those letters, its `main` would take `characters=None`, hand it to its dialog, and the dialog would add a first entry to its *Character set* box (*From Font Check*) whose `characters()` are those letters, selected as it opens. Diacritics is not changed by this script.

### The data

*checks/language_coverage.json* is made by *checks/train/languages.py* from Hyperglot 0.8.2 (its release archive, downloaded over HTTPS and checked against its SHA-256): 829 orthographies of 799 languages, 260 KB. For each language it keeps the primary orthographies (and the historical ones of historical languages), as Hyperglot's own language detection does; secondary orthographies and transliterations are left out. Hyperglot's inheritance (`<iso>`, `<iso auxiliary>`, `<iso Script>`, `<default Script>`) is resolved, characters are kept composed (NFC), digraphs are split into their letters (Hyperglot does not check them as units either), and the marks kept are Hyperglot's "required" ones: listed marks no character of the orthography decomposes into, and the marks of letter-and-mark clusters Unicode has no single character for. Lists shared by several orthographies (Chinese's) are stored once. *checks/language_coverage_LICENSE* carries Hyperglot's license and says what was changed.

```
python checks/train/languages.py --download <folder>
```

### How it compares with Hyperglot's own checker

On twelve open-licensed corpus fonts (Noto Sans, EB Garamond, Gentium Plus, Poppins, GFS Didot, Noto Sans Arabic, Devanagari, Thai, Khmer, JP, KR, and Amiri), Font Check's base-level support (no composing) and Hyperglot 0.8.2's checker (`Checker.get_supported_languages`, no shaping, draft validity and up, living and constructed languages) agree on 283 to 624 languages per font, and differ in three ways only, each by design:

- Letter-and-mark clusters with no single character (Hausa's *r̃*, Marshallese's *m̧*): Hyperglot without its shaping checks counts them when the font has the letter and the mark; Font Check asks for an anchor that joins them (about 50 languages in each Latin font with all the combining marks). Counting every mark as attached, and Hyperglot in its decomposed mode, the two agree on Noto Sans and Gentium Plus (673 and 658 languages) but for the next two points.
- Languages whose orthographies Hyperglot asks for together (`preferred_as_group`: Serbian in Cyrillic and Latin, Japanese in kana and kanji, Ainu, Pontic): Font Check lists each orthography under its own script, so a Latin-only font covers Serbian's Latin orthography.
- Hyperglot's decomposed mode also takes a modifier letter from its base letter (*ᶿ* from *θ*, by NFKD); Font Check does not, since a modifier letter needs a glyph of its own.

## Vertical metrics

The values are read from FontLab: the current master's ascender, descender, x-height, cap height, and line gap (`flPackage.ascender_value` and its siblings), and the font's OpenType line metrics from its font info (`fgPackage.info`: `openTypeOS2TypoAscender`, `openTypeOS2TypoDescender`, `openTypeOS2TypoLineGap`, `openTypeHheaAscender`, `openTypeHheaDescender`, `openTypeHheaLineGap`, `openTypeOS2WinAscent`, `openTypeOS2WinDescent`, and bit 7 of `openTypeOS2Selection`, *Use Typo Metrics*). An ascender, descender, or win value of 0 reads as not set. Every glyph's ink is measured in every master (its outline as FontLab draws it, components included).

The checks follow Google Fonts' vertical metrics guidance ([gf-docs, VerticalMetrics](https://github.com/googlefonts/gf-docs/tree/main/VerticalMetrics)). In short:

- Windows cuts off whatever reaches above winAscent or below winDescent, so those two should be the family's highest and lowest points, over every glyph of every master. With Use Typo Metrics on, Windows spaces lines by the typo values instead, so the win values can grow to stop clipping without loosening the lines.
- macOS spaces lines by hhea, Windows (with Use Typo Metrics) by typo: the two sets should be equal.
- Line gaps should be 0: applications add a line gap above the line, browsers split it above and below, and Windows without Use Typo Metrics ignores it, so a gap spaces lines differently everywhere.
- For Latin, Greek, and Cyrillic, the line (ascender plus descender) should be 120% to 130% of the em, the default leading of page layout applications; taller scripts (Devanagari, Arabic, Vietnamese's stacked marks) may need more.
- The line's ascender should clear *À*: some macOS applications place the first line by A grave's top or the ascender, whichever is taller.
- Capitals centered in the line (the room above the cap height equal to the room below the baseline) help web designers center text in buttons.
- A family being updated keeps its line spacing, so documents do not reflow: when Use Typo Metrics was off, the old win values become the typo values, and the win values then grow to the new ink.

The list shows, in groups: the glyphs clipped at the top and at the bottom on Windows, each with its master and how many units it is cut by; the line metrics' problems and advice (Use Typo Metrics off, hhea and typo differing, line gaps, the line's share of the em, A grave, centered capitals, win values far past the ink); the glyphs reaching past the line's ascender or descender (the farthest 40 each way: they may touch the line above or below at the font's own line spacing, which tall marks often do); and the suggested values. *Suggest values for a new font* puts the line at the share set (120% to start with), capitals centered in it, raised to A grave's top and lowered to the deepest descender of a to z (and Greek and Cyrillic), with line gaps of 0, hhea equal to typo, win at the ink's extremes, and Use Typo Metrics on; a font whose letters are mostly of another script (Arabic, Devanagari, Han) has the line shared as its ascender and descender are, then raised and lowered to clear its letters' ink. This reproduces the guidance's worked example exactly (typo 965 and −235, win 1116 and 320). *An update, keeping its line spacing* keeps the typo values if Use Typo Metrics was on, or else takes the old win values as typo values.

The line's share and centered capitals are judged only for a font whose letters are mostly Latin, Greek, or Cyrillic.

Selecting a glyph's row draws it in its master with winAscent and winDescent (red), the line's ascender and descender (blue), and the cap height, x-height, and baseline (gray).

FreeLab does not write these values: FontLab's API for them (`fgFontInfo`'s fields, per font or per master, and what FontLab does with them as it exports) is not proven, and a write there would not be one step of FontLab's History. *Copy suggested values* copies them as text and *Open Font Info* opens FontLab's Font Info (`flItems.requestFontInfoDlg`) to set them; the top line says so.

## Masters

Masters interpolate only where every glyph has the same structure in each. Each master is compared with the one chosen in *Compare every master with* (the font's default master to start with), glyph by glyph, and each difference is a row naming the glyph, the master, the contour (numbered from 1, in FontLab's order), and what differs:

- a glyph the master lacks;
- the number of contours, and contours in another order (the same node counts, shuffled);
- a contour open in one master and closed in the other;
- the number of nodes in a contour, and the first node whose type differs (on-curve, off-curve);
- a contour's direction (the sign of its area), also when the reversal shows first as node types in another order; a contour whose area is under 5% of its box's (a figure eight, whose halves cancel out) is not judged;
- a contour's start point: with the same nodes and types, the contour's points (centered and scaled to its size) are compared with the reference's at every start the node types allow; when another start fits at least four times as well as the one in place, and the one in place fits poorly, the row says how many nodes on or back the start sits. This is a judgment from the shapes: a contour whose shape changes a lot between masters (a dot drawn as a square in one weight and as a diamond in another) can look moved when it is not;
- components, by glyph name, and their order;
- anchors, by name.

A font with one master says there is nothing to compare. Selecting a row draws the glyph in both masters, the row's contour in orange and its start point dotted. The outlines are read through FontLab's own objects (`layer.shapes`; a shape's `isComponent` and `shapeData.componentGlyph`; its `transform` and `contours`; a contour's `nodes()` and `closed`; a node's `x`, `y`, and `type`; `layer.anchors`), the shape's transform applied, as Auto Kerning's `layer_path` draws them. Components' positions and scales, node smoothness, and guides are not compared: they interpolate whatever their values.

## How it was checked

FontLab was not run for this script. The checks above the Qt line are unit tested under Python 3 and 2.7 (*tests/fontcheck_tests.py*), and the dialog is run on fakes of PythonQt and of a two-master FontLab font (every Qt call accepted and ignored), which exercises its code paths but not Qt's or FontLab's answers.

- **Coverage**: compared with Hyperglot's own checker on twelve corpus fonts, as above.
- **Vertical metrics**: run on 169 open-licensed corpus fonts (variable fonts at their default and at each axis's ends, standing in for masters), and compared with what fontbakery's checks say of the same fonts (*win_ascent_and_descent*, *os2_metrics_match_hhea*, *linegaps*, *use_typo_metrics*): the same verdict for every font and check but two, Jua and Playpen Sans Hebrew, whose *head* table's box (control points) reaches past winDescent while their ink does not; Font Check measures the ink. In 22 variable fonts only a master other than the default clips, which a check of the *head* table cannot see.
- **Masters**: six variable corpus fonts (Noto Sans, EB Garamond, Cairo, Vazirmatn, Noto Sans Devanagari, Markazi Text; 13,407 glyphs), instanced at each axis's ends (compatible by construction, so anything found is a false alarm), then glyphs with one fault planted each (a start point moved, a contour reversed, a node dropped, components swapped, contours reordered, a glyph removed). 1,194 of the 1,200 planted faults were found (the six missed swap two components of the same name, or reorder contours of the same size: no change at all). False alarms came in 21 glyphs, all in Cairo's and Vazirmatn's Arabic dots and signs, whose shapes change between weights and slants: start points (66 contours) and two contours whose direction does flip in Vazirmatn's extremes. A plain comparison of the normalized points found 1,095 of 1,100 moved start points; fitting each start to the reference by a stretch and a slant first found 806, at as many false alarms, so the plain one is kept.

## FontLab calls not yet proven live

Proven before (see FreeLab MCP's *FONTLAB7-API.md*): the workspace and current font, `fgPackage.glyphs`, `findName`, `getLayerByName`, a layer's shapes, contours, and `path()`, `masters`, `master`, `upm`, the History state, the Glyph window, and flags. Used by Diacritics already: `ascender_value`, `descender_value`, `capsHeight_value`, `xHeight_value`, `layer.anchors`, `shape.isComponent`, `shape.shapeData.componentGlyph`. Documented in FontLab 7's reference and not yet run here: `lineGap_value`, `defaultMaster`, `fgPackage.info` and its `openType…` fields, `flContour.nodes()` and `closed`, `flNode.x`, `y`, and `type`, and `flItems.requestFontInfoDlg()`. To look at live: whether the `…_value` metrics are the current master's; how an unset typo, hhea, or win value reads (0, None, or FontLab's computed value) and whether FontLab exports what `fgFontInfo` holds; the strings `flNode.type` gives; and whether `flContour.nodes()` lists a closed contour's first node again at its end (the start-point and node-count checks would need it dropped).
