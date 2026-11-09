# Feature code

*Scripts > FreeLab > Feature Code* writes the OpenType code for the font's ligatures, and for alternates that take turns, two things a font's glyph names alone do not settle. The code is shown, and checked by fontTools' feature parser (FontLab 7 ships it), before anything is written.

## Ligatures

The list holds every ligature of the font: the simple rules of its `liga` and `dlig` features (`sub f f t by f_f_t;`, `sub parenleft c parenright by copyright;`), and each glyph whose name joins glyphs of the font with `_` (*l_l*, *f_f_t*) that no rule makes yet. Each is set to:

- **Standard** (`liga`): on unless the user turns it off. In InDesign and Illustrator, the *Ligatures* option; on the web, `font-variant-ligatures: no-common-ligatures`.
- **Discretionary** (`dlig`): off unless the user turns it on (*Discretionary Ligatures*; `font-variant-ligatures: discretionary-ligatures`).
- **Off**: in neither.

So yes, every ligature can be turned off by the user, except in apps that offer no switch; *Off* takes it out of the font's code altogether. A ligature's rule starts in the feature it is in now; a glyph no rule makes starts as Discretionary, or Standard when its name ends in `.liga`.

The rules are written longest first, in a block between FreeLab's marker lines; every other line of the two features stays as it was (in the owner's test font, the hand-written rules that set a standalone *I*). FontLab rewrites the code between its `#> feature` and `#< feature` lines when it updates its automatic features, which it does on compiling and exporting with *Update on Compile* on. A feature written here has that first line turned into `#/> feature`, FontLab's documented way of handing a feature back to you, so FontLab no longer rewrites it; its code stays as it was.

## Alternates that take turns

For a handwriting font: a letter with alternates (named *X.2*, *X.3*; *X.alt*, *X.alt1*; or *X.calt1*) takes its next form when its nearest earlier form, within a few letters (2 by default), is the one before it: *l*, *l.2*, *l*, *l.2*. Doubled and nearby letters vary as handwriting does, and the same text always comes out the same. Only letters stand between: a space or punctuation ends the look back, so each word starts afresh. Stylistic sets (*X.ss01*) are left to FontLab's automatic `ss01` to `ss20`.

The code is a `calt` lookup (contextual alternates, on unless the user turns it off) between FreeLab's marker lines; the rest of `calt` stays. An alternate the font's code already uses for something else is listed but left unchecked, with a note: taking turns would undo its job. In the owner's test font, *I.2* is the standalone *I*, set in `liga`, so *I* stays out, and *N*, *i*, *j*, and *l* take turns. `aalt` and `salt`, which list every alternate as a menu, do not count as a job.

`calt` comes after `liga` in the font, so ligatures form first: where `liga` makes *l_l* of *ll*, the alternates take turns around it.

## Limits

- Only simple ligature rules (glyph names in, one glyph out) are listed; contextual rules and rules with classes stay as they are, where they are.
- The look back counts glyphs of letters (letters, their alternates, ligatures, and accented letters of the font); a mark or a symbol between ends it.
- Writing goes straight into the open font, as one step of FontLab's History: *Edit > Undo* takes it back. Compile the features in FontLab's *Features* panel to try them.
- The code is made again as the choices change. Click a ligature's feature to choose another; the *Cycle* column shows the forms a letter takes in turn. Double-click a ligature or a letter to see it in a Glyph window. *Write the code* becomes *Update the code* once FreeLab's code is in the font, and grays out while the font has the code shown. *Restore suggestions* puts the choices back as they first came; the log says what was written.
