# Diacritics

*Scripts > FreeLab > Diacritics* builds the letters with diacritics a font lacks (Latin, Greek, and Cyrillic), as glyphs of components, in every master. Nothing is made until you click *Build checked glyphs*. It needs no groundwork in the font: no anchors, no accented glyphs to learn from, no *.case* marks, not even marks. Where the font has some, it follows them. It was called Accented Glyphs: not every diacritic is an accent (a cedilla, an ogonek, a hook, a breathing).

## What it builds

- **Which characters**: every character of the chosen set (*Character set:* Latin-1 to Latin Extended-B, Latin Extended Additional, Greek, Cyrillic, or *All*) that the font lacks and that Unicode's canonical decomposition splits into a letter and marks (*ǎ* is *a* with a caron, *й* is *и* with a breve). A script the font has no letters of is left out, and the top line says so. A glyph left empty (by FreeLab's first version, which added glyphs without their layers) is listed again and filled under its own name.
- **Which marks**, in this order:
  1. The font's own, by name (*caroncomb*, *caron*) or code point; for capitals, its *.case* form first; the script's own form before all (Greek's *tonos* for an acute, Cyrillic's *brevecomb-cy* for the short i's breve).
  2. For a mark below, its twin above (a dot below from the dot accent, a macron below from the macron; a comma below from the comma).
  3. A draft made of the font's punctuation: a dot accent of the period, a dieresis of two periods, a macron of the hyphen, a ring of the degree sign, a tilde of `~`, a circumflex of `^`, a caron of an upside-down `^`, a double acute of two acutes. A draft is sized as that mark is in the corpus (a dot accent 0.11 em high, for example) and the list says it is one: a starting point to redraw.

  *i* and *j* (and Cyrillic *і* and *ј*) take their dotless forms under a mark above. Greek's dialytika with tonos (*ΐ*) takes the font's *dieresistonos*, or its dieresis and tonos set over each other, the tonos between the dots. Characters that still cannot be built are listed apart, with what the font lacks (Vietnamese's horn and hook above have nothing to be drafted from).
- **Names**: Glyphs' names for the characters (*iishort-cy*, *Alphatonos*, *adotbelow*), from glyphsLib's *GlyphData.xml* (MIT License, its notice in *diacritics/GlyphData_LICENSE*), kept in *diacritics/glyph_names.json*; else the letter's name and the marks'; *uniXXXX* where those are taken. Each glyph gets its Unicode value.

## Where the marks go

- **Gaps**: from the font's own composites, per mark and case, where it has two or more (a composite counts where its character decomposes into its components: not a fraction, a guillemet, or *Ŀ*'s middle dot). Otherwise, from the corpus: *diacritics/train/marks.py* measures how the open-licensed fonts installed here (147 families) build their accented letters as composites, into *diacritics/mark_model.json*. A font whose own gaps run larger or smaller than the corpus's has the corpus's gaps scaled by the same amount.
- **Across**: each mark is centered on the center of the letter's top fifth (bottom fifth for marks below; the ogonek hangs from the right end of it), offset by a share of the letter's width. That share is the font's habit on that side and case, all its marks pooled (so a breve and a caron agree on *i*), or the corpus's, plus how far the corpus puts marks on that very letter from its habit: over *b*'s bowl rather than its stem (43% of its width), *K* and *Y* almost centered. A slanted hand's lowercase habit does not carry over to capitals.
- **Stacks**: marks stack the way the corpus stacks each pair. An acute or a hook above sits beside a circumflex, to its right and a little lower than its top, as Vietnamese is set; a tilde over a circumflex, or a macron over a dieresis, sits on it, about 0.05 em apart.
- **Greek capitals** carry their tonos (and breathings) at their left, the mark's top level with the capital's, 0.03 em away; the glyph is made wider by as much, so the mark keeps the letter's left sidebearing.

## Room above and below

A glyph must stay clear of the lines around it at a 120% line spacing (applications' automatic leading): its top below where the line above's descenders come down (1.2 em plus the descender), its bottom above where the line below's tallest letters (the ascender or cap height) come up. A glyph that would not fit is made compact: the gaps of its stack closed to 40%, then its marks made smaller, 5% at a time, down to 70%; the list says what it took. One that still does not fit is listed unchecked: it needs a shorter letter or marks drawn for it.

## Placing marks by hand

Under the list, the selected glyph is drawn large between its letter and a letter the font has with the same base, with the baseline and, dashed, the room a 120% line leaves.

- Click a mark to select it (it is drawn in the highlight color, in a frame with handles). Drag it, or press the arrow keys (Shift: 10 units), to move it; Shift while dragging keeps it on one axis.
- Drag a corner of the frame to scale the mark both ways (Shift: in proportion), or a side to scale it one way; the opposite corner or side stays put.
- Tab selects the next mark, Backspace puts the selected one back, Escape deselects; *Reset marks* puts all of the glyph's marks back.
- The changes stay with the glyph as you go down the list, its row's picture follows, and they are built. A mark moved by hand moves by as much in every master, scaled about its own center.
- Click the letter beside the glyph to open that pair in Auto Kerning, once the glyph is built (Auto Kerning measures the font's glyphs).

*Restore suggestions* puts every check and every mark moved by hand back as the list first came.

## Reference

Left of the editor, the selected character is drawn in another font, to compare. At first that is the installed font, among families known for wide coverage (Noto Sans, Gentium Plus, Charis SIL, DejaVu Sans, Segoe UI, Arial, and others), with the most of the listed characters; pick another in its list, and the choice is remembered (*%LOCALAPPDATA%\FreeLab\diacritics.json*). A font that lacks the character says so rather than drawing another's.

## The list, the log, and the History

- Double-click a glyph the font has (or select it and click *Show in Glyph window*) to open it between H's, n's, and o's in a Glyph window.
- The log under the editor says what each build did: done in green, warnings in amber, errors in red.
- Building is one step of FontLab's History, the font's list of glyphs included: *Edit > Undo* takes the new glyphs back. The dialog reads the font again after an undo, a redo, or an edit made in FontLab, keeping its checks and the marks moved by hand.
- New glyphs are added at the end of the font, and FontLab's Font window shows them at once.

On the owner's test font (no anchors; 106 composites, most of them with marks placed by hand), 269 glyphs can be built, 93 of them with a mark below borrowed from above and 12 with a mark drafted from punctuation, and 59 need a mark the font lacks.

## Limits

- Ligature-like letters (*ǆ*, *ĳ*) and letters with no decomposition (*ŧ*, *ø*) are not built: they are drawn.
- Glyphs whose caron is drawn as an apostrophe (*ď*, *ľ*, *ť*, *Ľ*) are not built from a caron: Unicode decomposes them with one, but fonts draw them otherwise.
- Marks are made smaller, not redrawn: a stack that needs flatter marks (as fonts draw for Vietnamese capitals) is better drawn by hand.
- A mark that always attaches (cedilla, ogonek) attaches as the corpus's do; a drafted cedilla (a comma) is only a placeholder.
- Greek's polytonic letters (Greek Extended) and scripts whose marks are positioned by the font's mark features rather than built as glyphs (Khmer, Thai, Arabic, Devanagari) are not built yet: for those, what Diacritics would place is anchors, for FontLab's automatic *mark* and *mkmk* features.
- The corpus model was measured on Latin letters; Greek and Cyrillic marks are placed by the font's own habit and the Latin marks' gaps.
