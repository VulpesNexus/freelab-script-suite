# CJK Spacing

*Scripts > FreeLab > CJK Spacing* writes the OpenType code that lets applications set a Japanese font's full-width kana and punctuation proportionally. Nothing is written until you click *Write the code*.

## What it writes

- **palt** (proportional alternate widths): each full-width kana, CJK punctuation mark, and full-width form is trimmed to its ink and the sidebearings the open-licensed CJK fonts give theirs. Applications turn palt on for proportional Japanese (InDesign's *Proportional Metrics*, CSS `font-feature-settings: "palt"`).
- **halt** (alternate half widths): each punctuation mark set in half the em, as those fonts set it: an opening bracket keeps its right half, a comma or full stop its left.

Each rule is a single adjustment, `pos a-hira <-70 0 -130 0>;`: the ink moves by the first number (x placement) and the width changes by the third (x advance). They sit between FreeLab's marker lines in palt and halt; the rest of each feature is kept, and FontLab's automatic block is handed back (its `#> feature` line becomes `#/> feature`), as Feature Code does. Writing is one step of FontLab's History: *Edit > Undo* takes it back. Compile the features in FontLab's *Features* panel to try them.

## Where the trims come from

*cjk/train/palt.py* reads the palt, halt, and vpal features of the open-licensed fonts at hand (the installed ones whose name table declares the SIL Open Font License or the Apache License, and those in *%LOCALAPPDATA%\FreeLab\corpus*, where OFL fonts from Google Fonts were put: Noto Sans and Serif JP and KR, IBM Plex Sans JP, Shippori Mincho, and others; 23 families with palt). For each glyph they adjust, it measures the ink's sidebearings after the adjustment, in shares of the em; the medians per kind of glyph, and per punctuation mark, are *cjk/palt_model.json*:

| Kind | Left | Right |
| --- | --- | --- |
| Hiragana | 0.078 em | 0.061 em |
| Katakana | 0.075 em | 0.059 em |
| Small kana | 0.08 em | 0.07 em |
| Punctuation | each mark its own (the ideographic comma 0.05 and 0.19 em) |

A glyph narrower than 90% of the em is proportional already and is left alone, and so is a trim smaller than 4 units on both sides. Tried on three of those fonts, the suggestions came within 6 to 31 units (medians) of the fonts' own palt: designers trim to taste, so the list is a starting point.

## The dialog

The list groups the glyphs by kind, each with its width, its palt trim, its width after, and its halt setting; checked glyphs are written. Under it, a sample (yours to type) is set as it is and with palt, in the font's glyphs. The log says what was written; *Restore suggestions* puts the checks back; double-click a glyph to see it in a Glyph window. The list is read again after an undo, a redo, or an edit in FontLab.

## Korean and the rest

- **Hangul** stays full width. The corpus's Korean fonts (Noto Sans and Serif KR) leave Hangul out of palt: proportional Korean comes from kerning, Hangul syllables kerned by classes of their shapes (a syllable with a vertical vowel on its right, like 가, against one with an open left). Auto Kerning measures Latin pairs for now; Hangul pairs are the next step there.
- **vpal** (proportional heights, for vertical text) is measured into the model but not written yet: FontLab's vertical metrics have to be read first.
- **Kanji** stay full width, as in the corpus.
