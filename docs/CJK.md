# CJK Spacing

*Scripts > FreeLab > CJK Spacing* writes the OpenType code that lets applications set a Japanese font's full-width kana and punctuation proportionally. Nothing is written until you click *Write the code*.

## What it writes

- **palt** (proportional alternate widths): each full-width kana, CJK punctuation mark, and full-width form is trimmed to its ink and the sidebearings the open-licensed CJK fonts give theirs. Applications turn palt on for proportional Japanese (InDesign's *Proportional Metrics*, CSS `font-feature-settings: "palt"`).
- **halt** (alternate half widths): each punctuation mark set in half the em, as those fonts set it: an opening bracket keeps its right half, a comma or full stop its left.

Each rule is a single adjustment, `pos a-hira <-70 0 -130 0>;`: the ink moves by the first number (x placement) and the width changes by the third (x advance). They sit between FreeLab's marker lines in palt and halt; the rest of each feature is kept, and FontLab's automatic block is handed back (its `#> feature` line becomes `#/> feature`), as Feature Code does. Writing is one step of FontLab's History: *Edit > Undo* takes it back. With *Compile after writing* (on by default) the features are compiled right after, by the *Features* panel's own *Compile* button (FontLab has no call for it; the panel must have been opened once in the session); off, compile them in the *Features* panel to try them.

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

The list groups the glyphs by kind, each with its width, its palt trim, its width after, and its halt setting; checked glyphs are written. Its check boxes are drawn in the window's own colors (a gray frame, or the highlight color with a check mark), so they show in dark mode too, where the list's pictures are left as they are drawn. Under it, a sample is set as it is and with palt, in the font's glyphs, broken into as many lines as the window's width needs (never before a closing mark or a small kana, nor after an opening mark; Korean at its spaces). The samples, each with the full-width punctuation palt trims (「」、。（）, and the full-width comma ， in Chinese):

- **Japanese**: the Iroha (11th century, in the public domain), every kana once.
- **Korean**: a pangram written for FreeLab (GPL-3 with the code, as in Proof), with the 14 basic consonants and the 10 basic vowels: 토요일 아침, 키 큰 여행자가 푸른 바다 앞 야자수 그늘에서 휴식을 즐겼다 (on a Saturday morning, a tall traveler rested in the shade of a palm tree by the blue sea).
- **Chinese**, Simplified and Traditional: a pangram of hanzi cannot be, so the opening lines of the Thousand Character Classic (in the public domain; no character in it twice), in each standard's forms.

The one in the font's own writing is chosen as the font is read, or type text of your own. The font's family name says it first (a word such as JP, KR, SC, TC, or HK), then its OS/2 code page bits where they name one writing only; without either, a font with Hangul syllables gets the Korean sample, one with kana the Japanese, and any other the Chinese sample it covers better. Kana alone does not say Japanese: Chinese fonts carry kana too (GB 2312 and Big5 have it), and IBM Plex Sans JP covers the Traditional Chinese sample as fully as the Iroha. A sample the font covers less than half of is never chosen for its name. The log says what was written; *Restore suggestions* puts the checks back; double-click a glyph to see it in a Glyph window. The list is read again after an undo, a redo, or an edit in FontLab.

## Kana kerning, after palt

palt trims each kana alone; some pairs still sit unevenly (a katakana with an open side beside another, a kana before the ideographic comma or full stop). *Auto Kerning*, with *Script* set to *Kana*, kerns those pairs on top of palt: it reads the font's palt from its feature code (written here or by hand, as single adjustments), measures the kana as palt sets them, and writes pair kerning only for what palt leaves uneven, never undoing a trim. A font whose kana are full width and have no palt is not kerned: write palt here first. See [KERNING.md](KERNING.md#kana).

## Hangul

None of the 16 open-licensed Korean families looked at (Noto Sans and Serif KR, IBM Plex Sans KR, Gothic A1, Gowun Batang and Dodum, Jua, Dongle, Black Han Sans, and others) kerns Hangul or puts it in palt. Half set every syllable at one width (0.77 to 1.0 em; 0.9 em the median); the other half give each syllable its own width, by design. So Korean is made proportional by its widths, and *Hangul:* sets them:

- **One width for all, ink centered**: the font's own width where its syllables share one, else the corpus's 0.9 em.
- **Proportional, by syllable shape**: each syllable keeps its ink and takes the sidebearings the proportional fonts give its shape, measured by *cjk/train/hangul.py* into *cjk/hangul_model.json*: about 0.03 em on the left; on the right, 0.055 em when the vowel stands beside the initial (가, 과) and 0.025 em when it sits under it (고). Noto Sans KR, set this way, would range from 753 to 917 units instead of 920.

The list shows the six shapes, each with its count, its median move, and its median width after; checked shapes are set, in every master (each measured on its own), their outlines and components moved and their widths changed. The sample becomes Korean for a font with more Hangul than kana or hanzi. The font's kerning of Hangul, if it has any, was set for the old widths.

## The rest

- **Vertical text** (vert and vrt2, vpal, and the vertical metrics) is *CJK Vertical*'s: [VERTICAL.md](VERTICAL.md).
- **Kanji** stay full width, as in the corpus.
