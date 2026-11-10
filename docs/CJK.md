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

## Kana kerning, after palt

palt trims each kana alone; some pairs still sit unevenly (a katakana with an open side beside another, a kana before the ideographic comma or full stop). *Auto Kerning*, with *Script* set to *Kana*, kerns those pairs on top of palt: it reads the font's palt from its feature code (written here or by hand, as single adjustments), measures the kana as palt sets them, and writes pair kerning only for what palt leaves uneven, never undoing a trim. A font whose kana are full width and have no palt is not kerned: write palt here first. See [KERNING.md](KERNING.md#kana-armenian-and-georgian).

## Hangul

None of the 16 open-licensed Korean families looked at (Noto Sans and Serif KR, IBM Plex Sans KR, Gothic A1, Gowun Batang and Dodum, Jua, Dongle, Black Han Sans, and others) kerns Hangul or puts it in palt. Half set every syllable at one width (0.77 to 1.0 em; 0.9 em the median); the other half give each syllable its own width, by design. So Korean is made proportional by its widths, and *Hangul:* sets them:

- **One width for all, ink centered**: the font's own width where its syllables share one, else the corpus's 0.9 em.
- **Proportional, by syllable shape**: each syllable keeps its ink and takes the sidebearings the proportional fonts give its shape, measured by *cjk/train/hangul.py* into *cjk/hangul_model.json*: about 0.03 em on the left; on the right, 0.055 em when the vowel stands beside the initial (가, 과) and 0.025 em when it sits under it (고). Noto Sans KR, set this way, would range from 753 to 917 units instead of 920.

The list shows the six shapes, each with its count, its median move, and its median width after; checked shapes are set, in every master (each measured on its own), their outlines and components moved and their widths changed. The sample becomes Korean for a font with Hangul and no kana. The font's kerning of Hangul, if it has any, was set for the old widths.

## The rest

- **vpal** (proportional heights, for vertical text) is measured into the model but not written yet: FontLab's vertical metrics have to be read first.
- **Kanji** stay full width, as in the corpus.
