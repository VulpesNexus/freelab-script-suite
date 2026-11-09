# Accented glyphs

*Scripts > FreeLab > Accented Glyphs* builds the accented Latin letters a font lacks from its letters and marks, as glyphs of components, placing each mark as the font's own accented glyphs place theirs. Nothing is made until you click *Build checked glyphs*.

## What it builds

- **Which characters**: every character of the chosen blocks (Latin-1 to Latin Extended-B, Latin Extended Additional, or both) that the font lacks and that Unicode's canonical decomposition splits into a letter and marks (*ǎ* is *a* with a caron).
- **Which glyphs**: the letter, and each mark by its name (*caroncomb* or *caron*, or found by its code point). Capitals take a mark's *.case* form where the font has one. *i* and *j* take their dotless forms under a mark above. A mark below the font lacks borrows its twin above (a dot below from the dot accent, a macron below from the macron, a comma below from the comma) and the list says so. Characters that cannot be built are listed apart, with what the font lacks (Vietnamese's horn and hook above, for example).
- **Names**: the letter's name and the marks' (*adotbelow*, *ecircumflexacute*), or *uniXXXX* where that name is taken. Each glyph gets its Unicode value.
- **Masters**: each glyph is built in every master, each placed on that master's own outlines.

## Where the marks go

No anchors are needed: the font's own composites show where its marks go. For each composite whose character decomposes into its components (*é* of *e* and *acute*; not a fraction, a guillemet, or *Ŀ*'s middle dot), it measures the mark's gap to the letter's ink and its offset from the center of the letter's top fifth (bottom fifth for marks below; the right end of it for the ogonek). A new glyph's mark takes the median of that mark's placements in the same case, else in the other case, else of all marks on that side, else 4% of the em above the letter and centered. Marks stacked above (Vietnamese *ế*) sit one above the other with the same gap; the horn sits at the letter's top right.

The list draws each glyph as it would be built; selecting one draws it larger between its letter and an accented letter the font has, to compare. Uncheck what looks off, build the rest, and adjust those by hand in FontLab: they are ordinary component glyphs.

On the owner's test font (no anchors, 106 composites), 257 glyphs can be built, 93 of them with a mark borrowed from above, and 71 need a mark the font lacks.

## Limits

- Ligature-like letters (*ǆ*, *ĳ*) and letters with no decomposition (*ŧ*, *ø*) are not built: they are drawn.
- Glyphs whose caron is drawn as an apostrophe (*ď*, *ľ*, *ť*, *Ľ*) are not built from a caron: Unicode decomposes them with one, but fonts draw them otherwise. The owner's test font has them already.
- Vietnamese stacks follow the general rule; designers often offset an acute or grave beside the circumflex, which needs a look.
- New glyphs are added at the end of the font. Building writes straight into the open font: close it without saving to take the glyphs back.
