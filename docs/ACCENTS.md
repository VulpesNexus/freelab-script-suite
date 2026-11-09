# Accented glyphs

*Scripts > FreeLab > Accented Glyphs* builds the accented Latin letters a font lacks, as glyphs of components, in every master. Nothing is made until you click *Build checked glyphs*. It needs no groundwork in the font: no anchors, no accented glyphs to learn from, no *.case* marks, not even marks. Where the font has some, it follows them.

## What it builds

- **Which characters**: every character of the chosen blocks (Latin-1 to Latin Extended-B, Latin Extended Additional, or both) that the font lacks and that Unicode's canonical decomposition splits into a letter and marks (*ǎ* is *a* with a caron). A glyph left empty (by FreeLab's first version, which added glyphs without their layers) is listed again and filled under its own name.
- **Which marks**, in this order:
  1. The font's own, by name (*caroncomb*, *caron*) or code point; for capitals, its *.case* form first.
  2. For a mark below, its twin above (a dot below from the dot accent, a macron below from the macron; a comma below from the comma).
  3. A draft made of the font's punctuation: a dot accent of the period, a dieresis of two periods, a macron of the hyphen, a ring of the degree sign, a tilde of `~`, a circumflex of `^`, a caron of an upside-down `^`, a double acute of two acutes. A draft is sized as that mark is in the corpus (a dot accent 0.11 em high, for example) and the list says it is one: a starting point to redraw.

  *i* and *j* take their dotless forms under a mark above. Characters that still cannot be built are listed apart, with what the font lacks (Vietnamese's horn and hook above have nothing to be drafted from).
- **Names**: the letter's name and the marks' (*adotbelow*, *ecircumflexacute*), or *uniXXXX* where that name is taken, with the Unicode value.

## Where the marks go

- **Gaps**: from the font's own composites, per mark and case, where it has two or more (a composite counts where its character decomposes into its components: not a fraction, a guillemet, or *Ŀ*'s middle dot). Otherwise, from the corpus: *diacritics/train/marks.py* measures how the open-licensed fonts installed here (147 families) build their accented letters as composites, into *diacritics/mark_model.json*. A font whose own gaps run larger or smaller than the corpus's has the corpus's gaps scaled by the same amount.
- **Across**: each mark is centered on the center of the letter's top fifth (bottom fifth for marks below; the ogonek hangs from the right end of it), offset by a share of the letter's width. That share is the font's habit on that side and case, all its marks pooled (so a breve and a caron agree on *i*), or the corpus's, plus how far the corpus puts marks on that very letter from its habit: over *b*'s bowl rather than its stem (43% of its width), *K* and *Y* almost centered. A slanted hand's lowercase habit does not carry over to capitals.
- **Stacks**: marks stack the way the corpus stacks each pair. An acute or a hook above sits beside a circumflex, to its right and a little lower than its top, as Vietnamese is set; a tilde over a circumflex, or a macron over a dieresis, sits on it, about 0.05 em apart.

## Room above and below

A glyph must stay clear of the lines around it at a 120% line spacing (applications' automatic leading): its top below where the line above's descenders come down (1.2 em plus the descender), its bottom above where the line below's tallest letters (the ascender or cap height) come up. A glyph that would not fit is made compact: the gaps of its stack closed to 40%, then its marks made smaller, 5% at a time, down to 70%; the list says what it took. One that still does not fit is listed unchecked: it needs a shorter letter or marks drawn for it.

On the owner's test font (no anchors; 106 composites, most of them with marks placed by hand), 269 glyphs can be built, 93 of them with a mark below borrowed from above and 12 with a mark drafted from punctuation, and 59 need a mark the font lacks.

## Limits

- Ligature-like letters (*ǆ*, *ĳ*) and letters with no decomposition (*ŧ*, *ø*) are not built: they are drawn.
- Glyphs whose caron is drawn as an apostrophe (*ď*, *ľ*, *ť*, *Ľ*) are not built from a caron: Unicode decomposes them with one, but fonts draw them otherwise.
- Marks are made smaller, not redrawn: a stack that needs flatter marks (as fonts draw for Vietnamese capitals) is better drawn by hand.
- A mark that always attaches (cedilla, ogonek) attaches as the corpus's do; a drafted cedilla (a comma) is only a placeholder.
- New glyphs are added at the end of the font. Building writes straight into the open font: close it without saving to take the glyphs back.
