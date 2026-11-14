# CJK Vertical

*Scripts > FreeLab > CJK Vertical* gives a CJK font what vertical text needs of it. Applications lay vertical text out, but they take three things from the font: the forms of the characters that turn or move in vertical text, how tightly its kana and punctuation may be set in proportional vertical text (vpal, and vkrn for pairs), and its vertical metrics. Nothing is written until you click *Write*.

## What it writes

- **Vertical forms** (vert and vrt2): brackets, dashes, the long vowel mark ー, and the wave dash turn a quarter clockwise; the small kana (ぁっゃ), the ideographic comma and full stop (、。), and the full-width comma and full stop (，．) move to the upper right of their square. Each form is a new glyph, the character's glyph name with *.vert*, made of one component of its glyph, turned or moved, so it follows any later change to the glyph. vert and vrt2 get the same substitutions: applications that know vrt2 use it instead of vert, and most of the corpus's fonts (82 percent) have both.
- **Proportional heights** (vpal): each full-width kana and punctuation mark, as vertical text sets it (its vertical form, where it has one), trimmed to its ink and the top and bottom sidebearings the corpus's fonts give theirs, as CJK Spacing's palt does across ([CJK.md](CJK.md)): `pos uni3042 <0 -2 0 -13>;` moves the ink by the second number (y placement) and changes the height by the fourth (y advance). Applications turn vpal on for proportional vertical Japanese.
- **Vertical kerning** (vkrn): the vertical counterpart of kern, for proportional vertical text: the pairs the corpus's fonts kern (mostly kana before the vertical comma and full stop, and kana pairs such as アメ and ティ), by their values (below).
- **Turned proportional glyphs** (vrt2, an option, off unless *Turned proportional glyphs (vrt2)* is checked): turned copies of the font's proportional glyphs (Latin, figures, half-width forms) for vrt2 (below).
- **Vertical metrics**: an advance height for every layer that has none (the em), and the vhea table's ascender, descender, and line gap in the font info, where the font has none (the line gap 0).

The rules sit between FreeLab's marker lines in each feature; the rest of each feature is kept, and FontLab's automatic block is handed back (its `#> feature` line becomes `#/> feature`), as Feature Code and CJK Spacing do. The forms, the code, and the advance heights are one step of FontLab's History: *Edit > Undo* takes them back. The vhea values are not in FontLab's History: *Put back vhea* puts them back as they were (an unset value unset again). With *Compile after writing*, the features are compiled right after, as in CJK Spacing.

## The font's own forms and code

The font's own work comes first, and the list says what it found:

- A character its own vert or vrt2 substitutes (outside FreeLab's block, its classes read too, those FontLab keeps among the font's classes included) is listed under *In the font's own code* and left alone.
- A glyph the font has for the form already, named like the character's with *.vert*, or the character's vertical presentation form (U+FE11 for the ideographic comma, U+FE41 for the left corner bracket, and the rest of U+FE10 to U+FE48), is listed under *Drawn in the font already*: only its rule is written.
- A glyph whose name a form would take is never replaced. A form FreeLab wrote before is listed under *In FreeLab's code already*, checked: writing again keeps its rule and leaves its glyph as it is (delete the glyph to build it again); unchecked, its rule is taken out and the glyph stays.
- The glyphs the font's own vpal positions keep their values: no second value is written for them (it would not compile). The pairs its own vkrn kerns are left alone too.
- A vrt2 FreeLab writes carries every substitution of the font's own vert that the font's own vrt2 lacks: applications that know vrt2 use it alone, and would lose them.
- The font's code is read with its classes and lookups (those its prefix defines and its features name, `sub [a b] by c;`, and a rule on a `lookup X {` line included).

## Which characters, and how far they move

*cjk/train/vertical.py* reads the vert, vrt2, and vpal features and the vertical metrics of the open-licensed fonts at hand (those whose name table declares the SIL Open Font License or the Apache License, and those in *%LOCALAPPDATA%\FreeLab\corpus*): 113 families with vert, among them Noto Sans and Serif CJK, Source Han Sans, IBM Plex Sans JP, the GenEi families, Zen Kaku Gothic, Klee One, and Shippori Mincho. For each character a font gives a vertical form, it compares the form's outline with the glyph's: the same outline turned a quarter clockwise about the em's center (or turned and mirrored, or turned the other way), or moved; a form drawn anew counts as turned when it is as wide as the glyph is tall, as moved when it has the glyph's size. The way most fonts make a character's form, and how far its ink's center sits from where the turn alone puts it (the median, in shares of the em), are *cjk/vertical_model.json*, with each character's Vertical_Orientation from the Unicode Character Database 17.0.0 (UAX #50).

Each character is decided on its own, by its Vertical_Orientation, its block, and its glyph's width, never by the font as a whole: in a font that mixes scripts, Latin and Hangul stay as they are while its CJK punctuation and kana get their forms. A form is built where at least half of the fonts that have the character give it one (three at least), and at least half of those make it the same way: most fonts set a full-width ！ centered and give it no form, so it gets none. Characters Unicode sets upright (Vertical_Orientation U) are not built, nor proportional glyphs (narrower than 90 percent of the em): applications turn those themselves. The forms of the characters Unicode marks as transformed (Tu and Tr), and of CJK punctuation, kana, dashes and ellipses, and full-width and vertical forms, start checked; the others the fonts give a form (full-width Greek and Cyrillic, symbols, box drawing) are listed unchecked under their own heading.

| Character | How (share of the fonts) | Move (median) |
| --- | --- | --- |
| Small kana (ぁっゃァッャ) | Moved (97 to 100 percent) | 0.11 to 0.13 em right, 0.09 to 0.13 em up |
| 、 and 。 | Moved (98 percent) | about 0.6 em right and 0.6 em up |
| ， and ． | Moved (94 percent) | about 0.66 em right and 0.65 em up |
| Brackets 「」（）〈〉【】 | Turned clockwise (93 to 97 percent) | none |
| ー, ―, …, ‥, ＝ | Turned clockwise (82 to 97 percent) | none |
| 〜 and ～ | Turned clockwise, then mirrored (92 to 96 percent) | none |

Built from IBM Plex Sans JP's own glyphs (under other names, then undone), the forms came out where that font's designers put theirs: 「 and 〜 to the unit (turned, and turned then mirrored), ー within 4 units, っ within 29 units, and 、 within 23 units.

A turned form keeps the move after the turn, so it sits where the glyph's own design puts it; a moved form is put where the fonts put the center of its ink in the square, wherever the glyph's own ink sits, in each master.

A form that nearly every font lays out anew rather than turning or moving its glyph (fewer than a fifth of them exactly: the squared words such as ㌔, the reversed double prime quotation mark 〞) is not built: draw it by hand.

## vpal

The sidebearings come from the same fonts' vpal, measured on the glyph vertical text sets (its form where it has one): about 0.07 em above and below each kana, and each punctuation mark its own (the ideographic comma 0.07 em above its ink and 0.17 em below). A glyph narrower than 90 percent of the em, and a trim smaller than 4 units at both ends, are left alone. Hangul is not trimmed (see CJK Spacing).

## vkrn

26 of the 113 families have vkrn; 24 of them kern at least ten of the pairs below and are read (Noto Sans and Serif CJK, Source Han Sans, the GenEi Gothic families, IBM Plex Sans JP, Klee One, Stick, Satsuki Gendai Mincho, Tsukimi Rounded, and Chiron Hei HK and its kin), and 1,718 pairs are kerned by at least five of them: a kana before the vertical comma and full stop (す︑ -0.10 em, か︒ -0.13 em), and kana pairs (アメ -0.04 em, ティ -0.05 em). CJK Vertical kerns those pairs of the font's that are as wide as the em (vertical text turns the others itself), each glyph as vertical text sets it (its vertical form, the font's own or the one to build), each by the median of the fonts' values for it, scaled to the em; a pair under 0.01 em is left alone, and so is a pair the font's own vkrn kerns.

Measuring the font's own glyphs was tried first and is not used. A pair's white, read as proportional vertical text sets it (in 16 bands across the column, its vpal applied, each band's white counted to 0.4 em at most), against the font's usual white, predicted the fonts' values weakly: a correlation of 0.26 over the 24 fonts' 40,812 pairs (0.36 to 0.54 on the designs of their own), a median error of 0.045 em; and live, on Zen Kaku Gothic New and IBM Plex Sans KR, its values stayed under 0.03 em, so no pair was written. The corpus's values are dominated by the Source Han Sans family and its copies (Noto Sans CJK, the GenEi Gothic families, Chiron Hei HK): on a design of its own, they are a starting point to look at in the preview, and to uncheck where the design does not want them.

## Turned proportional glyphs in vrt2

37 of the 113 families (a third) put turned copies of their proportional glyphs in vrt2, 325 characters in at least five of them (ASCII, Latin-1, half-width forms); the others leave proportional glyphs to applications, which turn them in vertical text themselves. With *Turned proportional glyphs (vrt2)* checked, CJK Vertical builds, for each proportional glyph (narrower than 90 percent of the em) whose character at least half of those fonts turn, a copy named with *.vrt2*: a component turned a quarter clockwise about the em's square (98 percent of their turned glyphs are turned so; its baseline goes to the descender's depth from the square's left), the em wide and as tall as the glyph is wide, as those fonts make them. It goes in vrt2 only. A glyph the font's own vrt2 turns is left alone; a *.vrt2* glyph the font has is used as it is. A glyph that has a vertical form (the font's own, its vertical presentation form, or one listed here) takes that form in vrt2, and no turned copy is built for it: vrt2 gets one rule per glyph (live, IBM Plex Sans KR's en dash had both its presentation form and a turned copy, and the copy was built for nothing).

## Vertical metrics in FontLab 7

What FontLab 7.2 lets a script read and write, found live on IBM Plex Sans JP (whose file has vhea and vmtx):

- FontLab keeps no vertical metrics from a font file it opens: every layer's advance height reads 0 and *has no advance height*, and vhea's values in the font info are unset.
- A layer's advance height (`flLayer.advanceHeight`) can be set, and *Edit > Undo* takes it back. CJK Vertical sets the em on every layer without one, and tells each glyph it changed (its `update()`): on a font opened afresh, the heights were otherwise gone once the write was over in all but a few glyphs (Zen Old Mincho kept 256 of 7,866; with `update()`, Zen Kaku Gothic New kept all 7,792). A glyph's own value is kept.
- vhea's ascender, descender, and line gap (`openTypeVheaVertTypo*` in the font info) can be set and unset; they are outside FontLab's History. CJK Vertical suggests 0.5 em and -0.5 em (the corpus's medians: the em's square centered on its middle), and a line gap of 0 (the owner's choice; the corpus's median is 0.15 em, while IBM Plex Sans JP and Source Han Sans have none).
- No vertical origin is exposed (no VORG, no top sidebearing per glyph): CJK Vertical takes the origin at the typographic ascender, as the corpus's fonts have it (their median sits on it), and turns each form about the center of the square under it.

**FontLab 7 does not export vertical metrics.** Tried live (IBM Plex Sans KR, *File > Export* through `flWorkspace.exportFont`): as OpenType TT and as OpenType PS, with every layer's advance height and vhea's values in the font info set, the exported font had no vhea, vmtx, or VORG table; with an AFDKO `table vhea { … } vhea;` block in the feature prefix, the features compiled and the table was still left out; a `table vmtx { VertOriginY … } vmtx;` block stopped the features compiling (*VertOriginY redefined for glyph uniAC00*), and the font was exported without GSUB and GPOS. The values CJK Vertical sets stay in the font (its *.vfc*), and the log says so after a write: a font exported from FontLab gets its vhea and vmtx (and VORG, for CFF) afterward, from the step below.

## Vertical metrics for an exported font

*Add vertical metrics to an exported font…* (under the list) asks for the font FontLab exported (*.otf* or *.ttf*) and writes a copy of it beside it, *&lt;name&gt;.vert.otf* (or *.vert-2.otf* and on, never over a file), with:

- vmtx: each glyph's advance height as the current master has it (the em where it has none), and its top sidebearing, the vertical origin less the top of its ink (0 for a glyph without ink). A glyph the export renamed is found by its code points.
- vhea: the ascender, descender, and line gap of the font info (the suggested ones where it has none), and the extents from vmtx.
- VORG, for a CFF font (*.otf*): the vertical origin, the typographic ascender, as the default for every glyph.

The exported font is not changed. The step runs inside FontLab, with the fontTools FontLab 7 ships for its Python (3.43), and reads the tables back; the log gives what it wrote. It writes the values beside the exported font too, as *&lt;font file&gt;.vertical.json*, so that a font exported again needs no FontLab to get them: the step is *tools/add_vertical_metrics.py* (installed as *add_vertical_metrics.module*, beside CJK Vertical), which runs on its own with Python 3 and fontTools:

    python add_vertical_metrics.py <exported font> [--values <json>] [--out <file>] [--force]

It refuses to write over the exported font, writes over an earlier output only with `--force`, and refuses values made for another em. With uharfbuzz installed, it also says what advances HarfBuzz gives a sample set vertically in the font it wrote.

## The dialog

The list groups the forms (turned, moved, written by FreeLab before, drawn already, others, the font's own), each with its picture as it will be, then the turned proportional glyphs (while their option is on), the vpal trims (each with its top and bottom sidebearings now, and its y placement and y advance), the vkrn pairs (each with the number of fonts that kern it, and its kerning), then the vertical metrics (each with its value now and the one written). The check boxes over it switch each part on and off. Under it, a sample is set in vertical columns, right to left, as the font's own code sets it and with what is checked (vpal and vkrn included): a Japanese sentence written for FreeLab with brackets, small kana, the long vowel mark, a dash, and the comma and full stop (in place of CJK Spacing's Iroha, which has neither small kana nor the long vowel mark), CJK Spacing's Korean and Chinese samples, or text of your own. Every sample is set vertically: vertical forms do nothing across, and CJK Spacing shows the text across. The columns shrink to fit their pane, and a character the font lacks is drawn as an empty box. *Restore suggestions* puts the checks back; double-click a glyph to see it in a Glyph window. The list is read again after an undo, a redo, or an edit in FontLab.

## Limits

- FontLab 7's export writes no vertical tables (above): the features are exported (vert, vrt2, and vpal were, live), the vertical metrics are added to the exported font afterward, as one origin for every glyph (VORG's default; no glyph of its own origin).
- vkrn is a starting point (above): its pairs and values are the corpus's, not measured on the font's glyphs.
- A form is a component turned or moved: a design that wants its vertical form redrawn (a brush stroke's direction, a wave dash's curve) can be drawn over afterward, and is then the font's.
