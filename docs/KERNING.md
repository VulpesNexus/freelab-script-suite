# Auto kerning

*Scripts > FreeLab > Auto Kerning* suggests kerning for the Latin pairs of the font's current master by two methods and FontLab's own, shows how far they agree beside the kerning the font has, and writes only the pairs you leave checked.

## Using it

1. Open the font, pick the master to kern, and run the script: it analyzes the master as it opens, and *Analyze* analyzes the font that is current then. Every pair of the Latin letters, figures, and punctuation the font has is measured by both methods (two marks of punctuation side by side are skipped); about 7,000 pairs take two to five seconds. Each master's results are remembered (in *%LOCALAPPDATA%\FreeLab\kerning-cache*, under a hash of the font's path; uninstalling removes them): the next analysis measures only the pairs whose glyphs changed, and everything again when a reference glyph (l, n, o, H, O, 0, 8) did.
2. The list holds the pairs the font does not kern yet that either method would change by at least the given number of units (20 by default); FontLab's own autokern is asked about them too (a call per pair). *Show* narrows it to letters, letters and punctuation, or figures, and *Common pairs* to the pairs worth kerning even in a font kerned only in part: those common in the text of 24 languages and kerned in fonts ([andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs), MIT; *kerning/common_pairs.txt*).
3. The columns: each method's value, *Spread* (how far they lie apart), and *Suggested*, from *Suggested values from*: the average of halfkern and contour distance (the default), any one method, or FontLab's. Changing it changes only that column, never the list or its order. The order: largest change, best agreement (the safest pairs to accept together), most common, or alphabetical.
4. Selecting a pair draws it between two dimmed H's as it is set now and by each method, a button each, with the method's name, value, and key; the one it will take is checked. Clicking another picks it for that pair alone (*Now* keeps the current kerning), and so do double-clicking a value in the list and pressing its number (1 *Now*, 2 *Average*, 3 halfkern, 4 *Contour*, 5 *FreeLab*, 6 *FontLab*) while the list has the focus. A pair picked by hand is tinted, its Suggested value bold, and *Only pairs picked by hand* appears to list them; *Reset*, Backspace, or double-clicking its Suggested value gives it the suggested value again. Space checks or unchecks the selected pair. The line above the buttons says where the pair's value will be written, and the list under it which other glyph pairs that entry kerns (see *Kerning classes*). The dialog's ? button, then a click on any control, explains it.
5. *Include pairs that are already kerned* lists the pairs the font kerns too, those written since included. They are never checked for you: they are the designer's choices, some of which the methods do not model (a j tucked under the letter before it).
6. Uncheck what you disagree with, and click *Write checked pairs*. Each pair is written where its value comes from (see *Kerning classes*); a value of 0 removes the entry unless a class pair would then apply. Picks end once written, and the list shows the font's new values. Writing goes straight into the open font: close it without saving to take it all back.

The kerning the font already has acts as a model: with at least three tightenings in it, each method's tightenings are scaled to match how strongly the designer tightens, and the same for loosenings. Without them, halfkern's tightenings are applied at half strength, as halfkern applies them, and contour distance's in full.

### Kerning classes

*Current* is the kerning FontLab applies to the pair, its classes included (`getPlainPairsDict()`): a font kerned by classes (class *T* against class *o*) shows those values, not 0. A pair is written to the entry its value comes from now: its own pair if it has one, or else the pair of its classes, or of its class and the other glyph. With none, it goes to its classes' pair (or its glyphs' where they have no class). A class pair kerns every glyph of both classes (*Tcaron* with *oacute* too); the line above the buttons and the pair's tooltip name it and count its pairs. Checked pairs that share one entry get the value of the most common of them, and the status says how many. FontLab's scripting takes a name that is also a class's as the class, so where an entry names a glyph that shares a class's name (class *l* against glyph *j*, beside a class *j*), the class is renamed for the moment of writing and renamed back; renaming a class keeps its pairs.

The classes are the font's own, made in FontLab's Classes panel: Auto Kerning reads and writes through them, and never makes, changes, or removes one.

### Suggested classes

*Suggest classes…* proposes kerning classes for the master, to review before any is made. Each side is its own set of classes: *first in a pair* groups glyphs by their right side (FontLab's left, or 1st, classes), *second in a pair* by their left side.

- **From the corpus**: *kerning/train/classes.py* reads the kerning classes of the same open-licensed fonts the FreeLab method learned from (155 families, once the same classes under another family name count once, class their kerning; where a font splits its kerning over subtables, a pair counts as classed together where most of them do) and counts, for each pair of characters and each side, how many families put them in one class. The counts are *kerning/class_model.json*.
- **An accented letter** joins its base letter where most families class the two together on that side (*À* with *A* almost always; *Ŀ* with *L* only on one side). For a pair the corpus has not seen, it joins where the two kern alike in this font.
- **Base letters** share a class where most families class them so (*n* with *m* and *h*, *o* with *c*, *e*, and *q*, the straight-stemmed capitals on their left) and every two of them kern alike in this font: within 2% of the em against each of a few partners (*H*, *O*, *o*, *n*, *v*, *T*, and others), measured by halfkern and contour distance.
- **Members that kern unlike** the class's first glyph by 3% of the em or more are named with the difference, in units: where an accent reaches toward a neighbor (*ì* beside *f*), the class may want an exception.
- **The font's classes come first**: a suggestion makes a class (named *kern1_* or *kern2_* and its first glyph) only where none of its glyphs has one on that side, or adds glyphs to the one class they share, unless that class kerns both sides. Suggestions that overlap several classes are shown and left as they are, and so are the classes the font has already.
- **Moving pairs**: with *Move each new class's first glyph's pairs into the class* (on by default), a new class takes over its first glyph's own pairs on that side, so every member kerns as that glyph did.

On the owner's test font, left out of the counts, 60 of the suggestions were classes the font has already.

## The methods

Both are measured by FreeLab's native core (*kerning/native/freelab_kern.c*) on glyphs rendered from FontLab's outlines at 200 pixels per em, and both hold each kind of pair to its own references, pairs the designer spaced on purpose and that are set with no kerning: capitals to *HH*, *HO*, *OH*, and *OO*; lowercase to *ll*, *nn*, and *oo*; figures to *0* and *8*; pairs across cases to the references of both sides; punctuation to the kind of the letter beside it. A pair is moved until its measure falls within the band its references span.

- **halfkern** ([behdad/halfkern](https://github.com/behdad/halfkern), Copyright 2022 Google LLC, Apache License 2.0): each glyph gets an envelope, its ink over a halo that fades out over about a tenth of the em at half strength; the measure is the overlap of the two envelopes, the sum of their squared products. The halo grows until *ll*, *nn*, and *oo* agree within a factor of two, as halfkern's does, and FreeLab interpolates between whole pixels where the overlap crosses the band. Checked against halfkern itself on the same renderings (Georgia, 19 pairs): the same kerning for every pair, including the two it cannot kern.
- **Contour distance**, after Matthew Skala's description of Tsukurimashou's kerning ([freetype-devel, June 2012](https://lists.nongnu.org/archive/html/freetype-devel/2012-06/msg00118.html)); written from that description, not from its code. Each glyph's left and right edges are found row by row, and their angle is limited (an edge moves at most 0.6 pixels across a row), so that a shape reaches out into the rows above and below it: a period cannot slide under an apostrophe. The measure is the average over the rows of the inverse cube of the gap between the facing edges, found by bisection. A tightening stops where the two glyphs' ink comes within 2% of the em.
- **FontLab's own** autokern (`flPackage.autoKern`, FontLab 8's "K1"), which returns its value without writing it. It is coarse: on the owner's test font it gave −56 for most pairs it tightened.
- **FreeLab**, FreeLab's own learned method: gradient-boosted trees trained on how fonts are kerned. Its inputs are both methods' readings, the gap between the pair's facing ink in 16 height bands, the two advances, and the font's own spacing (its *nn*, *oo*, and *HH*), all as shares of the em, measured by the same code as the other methods. It has two stages: one decides whether a pair is kerned at all, the other how much (a single one learned to say 0, since most common pairs are not kerned). The model, *kerning/learned_model.json*, is evaluated in plain Python.

### What the FreeLab method learned from, and how it was checked

*kerning/train/dataset.py* reads the fonts installed on the computer it runs on, and keeps only those whose name table declares the SIL Open Font License or the Apache License, and that kern: of the 4,074 fonts installed on the owner's computer, 747. Fonts that kern fewer than 5% of the common pairs, the same Latin design under another name, and fonts whose *l*, *n*, and *o* cannot be measured were left out: 777,113 pairs from 558 fonts in 186 families, with the kerning each font applies read through HarfBuzz, ligatures and contextual alternates off (an *fi* ligature is not kerning). The measurements stay on that computer; only the trained model is in the repository. *kerning/train/train.py* trains and checks it.

The families were split into five folds, each held out once (no family in both parts), and the methods' suggestions compared with the held-out fonts' kerning, in units of a 1000-unit em:

| Method | Mean error, all pairs | Mean error, kerned pairs | Within 20 units |
|---|---|---|---|
| No kerning at all | 9.3 | 38.2 | 85% |
| halfkern | 17.1 | 22.4 | 69% |
| Contour distance | 26.9 | 32.0 | 57% |
| Average of the two | 21.7 | 25.1 | 63% |
| **FreeLab** | **8.6** | **21.1** | **85%** |

halfkern and contour distance are scored here with their default strengths; in Auto Kerning, the font's own kerning tunes them, which narrows the gap. The FreeLab method is the only one that beats leaving most pairs alone while also coming closest on the pairs the fonts do kern.

These are averages over many fonts; one font can go the other way. The owner's test font, left out of training (`train.py --exclude`), on its 1,395 common pairs with its kerning as HarfBuzz applies it, classes included (817 kerned), each method's strength fitted to that kerning as Auto Kerning fits it:

| Method | Mean error, all pairs | Kerned pairs | Unkerned pairs | Within 20 units |
|---|---|---|---|---|
| No kerning at all | 32.8 | 55.3 | 1.1 | 55% |
| halfkern | 29.9 | 34.0 | 24.1 | 47% |
| Contour distance | **22.7** | **29.7** | 12.7 | **63%** |
| FreeLab | 23.8 | 36.8 | **5.5** | 61% |

FreeLab leaves alone what the font leaves alone, but on that font's kerned pairs contour distance came closer: FreeLab leaves some at 0 that the font kerns. That is why the suggestions default to the average of halfkern and contour distance, with FreeLab one click away, and why each pair's methods are shown side by side. (An earlier version of this check read only the font's glyph pairs, missing its class kerning, and favored FreeLab wrongly.)

The two methods often disagree on pairs with diagonals and overhangs (contour distance tightens *To* and *TA* more), and agree on most others. On a font with kerning, contour distance came closer to the designer's own pairs (*LT*: designer −178, contour −154, halfkern −109).

## Scripts and characters

Auto Kerning lists pairs of these characters only: the letters A to Z and a to z, the figures 0 to 9, and the punctuation `. , : ; ! ? ' " - ( ) [ ] { } / & *`, the curly quotes, guillemets, and the en and em dashes. Any other character, accented Latin letters (é, Å, ł) included, is not measured, not listed, and never written: its pairs keep the kerning the font gives them.

| Method | What it could measure | What it is set for |
|---|---|---|
| halfkern | any glyphs: it measures shapes | the Latin references *l*, *n*, *o*, *H*, *O*, *0*, *8*; another script needs references of its own (*н* and *о* for Cyrillic, for instance) |
| Contour distance | any glyphs | the same Latin references; Tsukurimashou tuned the method for Latin, Japanese, and Korean, with other settings for each |
| FontLab's own | any glyph pair | nothing of FreeLab's: FontLab's own settings |
| FreeLab | the pairs it was trained on | Latin pairs of open-licensed fonts only: elsewhere its values are guesses |

Accented letters take their base letter's kerning where the font's classes hold both: a pair written to a class pair kerns them too. Japanese kana are spaced with `palt` more than with pairs ([FEATURE-SURVEY.md](FEATURE-SURVEY.md)).

## Limits

- Classes are used, not made: a font without classes gets glyph pairs, and its accented letters keep their own kerning.
- Latin only (see *Scripts and characters*); contour distance, tuned for Japanese in Tsukurimashou, is the base for kana.
- Each method has blind spots: halfkern loosens *Ty* in Georgia, where the T's bar meets the y's arms, and cannot kern *VA* there. Review before writing.
- Other published methods, and the one not to implement (Apple's, patented until 2033), are in [FEATURE-SURVEY.md](FEATURE-SURVEY.md).
