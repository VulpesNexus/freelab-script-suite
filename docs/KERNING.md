# Auto kerning

*Scripts > FreeLab > Auto Kerning* suggests kerning for the Latin pairs of the font's current master by two methods and FontLab's own, shows how far they agree beside the kerning the font has, and writes only the pairs you leave checked.

## Using it

1. Open the font, pick the master to kern, and run the script: it analyzes the master as it opens, and *Analyze* analyzes the font that is current then. Every pair of the Latin letters, figures, and punctuation the font has is measured by both methods (two marks of punctuation side by side are skipped); about 7,000 pairs take two to five seconds. Each master's results are remembered (in *%LOCALAPPDATA%\FreeLab\kerning-cache*, under a hash of the font's path; uninstalling removes them): the next analysis measures only the pairs whose glyphs changed, and everything again when a reference glyph (l, n, o, H, O, 0, 8) did.
2. The list holds the pairs the font does not kern yet that either method would change by at least the given number of units (20 by default); FontLab's own autokern is asked about them too (a call per pair). *Show* narrows it to letters, letters and punctuation, or figures, and *Common pairs* to the pairs worth kerning even in a font kerned only in part: those common in the text of 24 languages and kerned in fonts ([andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs), MIT; *kerning/common_pairs.txt*).
3. The columns: each method's value, *Spread* (how far the three lie apart), and *Write*, from *Write values from*: the average of halfkern and contour distance (the default), either of them, or FontLab's. Changing it changes only that column, never the list or its order. The order: largest change, best agreement (the safest pairs to accept together), most common, or alphabetical.
4. Selecting a pair draws it between two H's as it is set now, by each method, and as it will be written, and *This pair uses* picks another method, or the current kerning, for that pair alone; the Write column names the choice.
5. *Include pairs the font kerns* lists the font's own pairs too. They are never checked for you: they are the designer's choices, some of which the methods do not model (a j tucked under the letter before it).
6. Uncheck what you disagree with, and click *Write checked pairs*: each is written to the master as a pair of glyphs (a value of 0 removes the pair). Writing goes straight into the open font: close it without saving to take it all back.

The kerning the font already has acts as a model: with at least three tightenings in it, each method's tightenings are scaled to match how strongly the designer tightens, and the same for loosenings. Without them, halfkern's tightenings are applied at half strength, as halfkern applies them, and contour distance's in full.

## The methods

Both are measured by FreeLab's native core (*kerning/native/freelab_kern.c*) on glyphs rendered from FontLab's outlines at 200 pixels per em, and both hold each kind of pair to its own references, pairs the designer spaced on purpose and that are set with no kerning: capitals to *HH*, *HO*, *OH*, and *OO*; lowercase to *ll*, *nn*, and *oo*; figures to *0* and *8*; pairs across cases to the references of both sides; punctuation to the kind of the letter beside it. A pair is moved until its measure falls within the band its references span.

- **halfkern** ([behdad/halfkern](https://github.com/behdad/halfkern), Copyright 2022 Google LLC, Apache License 2.0): each glyph gets an envelope, its ink over a halo that fades out over about a tenth of the em at half strength; the measure is the overlap of the two envelopes, the sum of their squared products. The halo grows until *ll*, *nn*, and *oo* agree within a factor of two, as halfkern's does, and FreeLab interpolates between whole pixels where the overlap crosses the band. Checked against halfkern itself on the same renderings (Georgia, 19 pairs): the same kerning for every pair, including the two it cannot kern.
- **Contour distance**, after Matthew Skala's description of Tsukurimashou's kerning ([freetype-devel, June 2012](https://lists.nongnu.org/archive/html/freetype-devel/2012-06/msg00118.html)); written from that description, not from its code. Each glyph's left and right edges are found row by row, and their angle is limited (an edge moves at most 0.6 pixels across a row), so that a shape reaches out into the rows above and below it: a period cannot slide under an apostrophe. The measure is the average over the rows of the inverse cube of the gap between the facing edges, found by bisection. A tightening stops where the two glyphs' ink comes within 2% of the em.
- **FontLab's own** autokern (`flPackage.autoKern`, FontLab 8's "K1"), which returns its value without writing it. It is coarse: on the owner's test font it gave −56 for most pairs it tightened.

The two methods often disagree on pairs with diagonals and overhangs (contour distance tightens *To* and *TA* more), and agree on most others. On a font with kerning, contour distance came closer to the designer's own pairs (*LT*: designer −178, contour −154, halfkern −109).

## Scripts and characters

Auto Kerning lists pairs of these characters only: the letters A to Z and a to z, the figures 0 to 9, and the punctuation `. , : ; ! ? ' " - ( ) [ ] { } / & *`, the curly quotes, guillemets, and the en and em dashes. Any other character, accented Latin letters (é, Å, ł) included, is not measured, not listed, and never written: its pairs keep the kerning the font gives them.

| Method | What it could measure | What it is set for |
|---|---|---|
| halfkern | any glyphs: it measures shapes | the Latin references *l*, *n*, *o*, *H*, *O*, *0*, *8*; another script needs references of its own (*н* and *о* for Cyrillic, for instance) |
| Contour distance | any glyphs | the same Latin references; Tsukurimashou tuned the method for Latin, Japanese, and Korean, with other settings for each |
| FontLab's own | any glyph pair | nothing of FreeLab's: FontLab's own settings |
| Learned | the pairs it was trained on | Latin pairs of open-licensed fonts only: elsewhere its values are guesses |

Accented letters usually take their base letter's kerning through kerning classes, which Auto Kerning does not write yet. Japanese kana are spaced with `palt` more than with pairs ([FEATURE-SURVEY.md](FEATURE-SURVEY.md)).

## Limits

- Kerning classes are not read or written yet: every suggestion is a pair of glyphs. A font with kerning classes gets glyph pairs, which override its classes.
- Latin only (see *Scripts and characters*); contour distance, tuned for Japanese in Tsukurimashou, is the base for kana.
- Each method has blind spots: halfkern loosens *Ty* in Georgia, where the T's bar meets the y's arms, and cannot kern *VA* there. Review before writing.
- Other published methods, and the one not to implement (Apple's, patented until 2033), are in [FEATURE-SURVEY.md](FEATURE-SURVEY.md).
