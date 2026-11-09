# Auto kerning

*Scripts > FreeLab > Auto Kerning* suggests kerning for the Latin pairs of the font's current master by two methods and FontLab's own, shows how far they agree beside the kerning the font has, and writes only the pairs you leave checked.

## Using it

1. Open the font, pick the master to kern, and run the script: it analyzes the master as it opens, and *Analyze* analyzes the font that is current then. Every pair of the Latin letters, figures, and punctuation the font has is measured by both methods (two marks of punctuation side by side are skipped); about 7,000 pairs take two to five seconds. Each master's results are remembered (in *%LOCALAPPDATA%\FreeLab\kerning-cache*, under a hash of the font's path; uninstalling removes them): the next analysis measures only the pairs whose glyphs changed, and everything again when a reference glyph (l, n, o, H, O, 0, 8) did.
2. The list holds the pairs the font does not kern yet that either method would change by at least the given number of units (20 by default); FontLab's own autokern is asked about them too (a call per pair). *Show* narrows it to letters, letters and punctuation, or figures, and *Common pairs* to the pairs worth kerning even in a font kerned only in part: those common in the text of 24 languages and kerned in fonts ([andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs), MIT; *kerning/common_pairs.txt*).
3. The columns: each method's value, *Spread* (how far they lie apart), and *Suggested*, from *Suggested values from*: the average of halfkern and contour distance (the default), any one method, or FontLab's. Changing it changes only that column, never the list or its order. The order: largest change, best agreement (the safest pairs to accept together), most common, or alphabetical.
4. Selecting a pair draws it between two dimmed H's as it is set now and by each method, a button each (drawn once a pair is selected), with the method's name, value, and key; the one it will take is checked. Clicking another picks it for that pair alone (*Now* keeps the current kerning), and so do double-clicking a value in the list and pressing Ctrl and its number (Ctrl+1 *Now*, Ctrl+2 *Average*, Ctrl+3 halfkern, Ctrl+4 *Contour*, Ctrl+5 *FreeLab*, Ctrl+6 *FontLab*) while the list has the focus (a plain letter or number jumps to the pairs starting with it, as in any list). Clicking one of the H's around the pair, in any button, goes to that H's pair with the glyph beside it (*H* and *T* for *HTo*): it is listed whatever the filters, and measured first when it was not (an accented letter's pair). A pair picked by hand is tinted, its Suggested value bold, and *Only pairs picked by hand* appears to list them; *Reset pair*, Backspace, or double-clicking its Suggested value gives it the suggested value again; *Restore suggestions* puts every check and pick back as the list first came. Space checks or unchecks the selected pair. The line above the buttons says where the pair's value will be written, and the list under it which other glyph pairs that entry kerns (see *Kerning classes*). *Show in Glyph window*, or double-clicking the pair's name, opens the pair between H's, n's, and o's in a Glyph window, to look at it with FontLab's own tools (between the pair's own script's controls where the font has them: Greek's Eta, nu, and omicron, Cyrillic's En, en, and o, zeros for figures). What a write did goes to the log under the previews; after an undo, a redo, or an edit in FontLab, the current values are read again. The dialog's ? button, then a click on any control, explains it.
5. *Include existing kerned pairs* lists the pairs the font kerns too, those written since included. They are never checked for you: they are the designer's choices, some of which the methods do not model (a j tucked under the letter before it).
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
- **May need pairs of their own**: members that need kerning looser than the class's first glyph by 3% of the em or more are named at the pair where they differ most, with the difference in units (*éT 52 units looser than eT*: the accent keeps *é* from tucking under *T*'s bar as far as *e* does). The class's value would bring that pair too close, so it may want an exception. Members the methods measure tighter are not named: that is air beside an accent the neighbor does not reach (an accent above *T*'s bar), and the class's value only leaves them a little loose.
- **Scripts**: classes are suggested for Latin letters (to Latin Extended-B), figures, and punctuation, the characters the corpus counts and the methods measure.
- **The font's classes come first**: a suggestion makes a class (named *kern1_* or *kern2_* and its first glyph) only where none of its glyphs has one on that side, or adds glyphs to the one class they share, unless that class kerns both sides. Suggestions that overlap several classes are shown and left as they are, and so are the classes the font has already.
- **Moving pairs**: with *Move each new class's first glyph's pairs into the class* (on by default), a new class takes over its first glyph's own pairs on that side, so every member kerns as that glyph did.
- **Pairs too close with their class's value**: the noted pairs the class tightens now (the member kerns beside the partner exactly as the class's first glyph does, below 0) are listed at the end, each with a value of its own: the class's, loosened by the difference measured, never past 0. *Write checked pairs* writes them as glyph pairs, which the class's value no longer reaches; the class kerns its other glyphs as before. The values are estimates: look at the pairs after writing.

On the owner's test font, left out of the counts, 60 of the suggestions were classes the font has already.

## Kerning Check

*Scripts > FreeLab > Kerning Check* (or *Check kerning…* in Auto Kerning) holds three lists for the current master. Nothing changes until a list's button is clicked; writing goes straight into the open font, so closing it without saving takes it back.

- **Collisions**: kerned pairs (tighter than 0) whose ink comes too close at the kerning FontLab applies, classes included, measured on the same renderings as the methods (200 pixels per em, so to about 5 units in a 1,000-unit em). By default a pair is listed when its ink comes within the distance set (2% of the em to start with) *and* that much closer than its base letter beside the same glyph: *Ťj* against *Tj*, *ąj* against *aj*. That is what a class's value does to an accented or barred member it was not set on, and it holds in any font, also one whose letters touch or overlap on purpose (joined crossbars, *TT* kerned to overlap): such pairs are compared with their own base pair, not with a fixed distance. A glyph is a variant of its class's key glyph (the glyph the class is named after, or its first member) when its name starts with the key's and its character is a letter built on the key's letter, or a letter with no decomposition (*Ŧ*, *Ł*); ligatures and other characters (*₩* after *w*) are not. Pairs kerned by an entry of their own are the designer's and are not compared. The list groups the pairs by the glyph that collides (*Ť*: 178 pairs in the owner's test font), closest first; each pair's fix sets it as far apart as its base pair (or, by the absolute measure, at the distance set) and is written as a pair of its own. *Of each other, whatever the letters* lists every kerned pair within the distance, for fonts whose letters never touch. Both measure the same thing, the narrowest horizontal distance between the two glyphs' ink, row by row, at the pair's kerning; the first also asks that the pair come that much closer than the same pair with its plain letter.
- **Cleanup**: entries that change nothing (every pair they cover gets the same value without them), entries overridden for every pair they cover, entries naming a class with no members or a glyph the font lacks (these three checked), and values smaller than the size set (5 units to start with; unchecked, to look at first). Entries are judged most specific first, each as if those found before it were removed: an exception equal to its class's value is listed, and the class entry it falls back on is not.
- **Masters**: entries kerned in some masters and not others, entries tightening in one master and loosening in another (an instance between them may collide), and classes whose members differ between masters. A list only: masters differ on purpose as often as by mistake.

Selecting a row draws its pair under the list, its two glyphs see-through so that overlapping ink shows denser: now, with its fix, and its base pair (Collisions), or with and without the entry (Cleanup). *Show in Glyph window*, or double-clicking a row, opens the selected row's pair (a group's first pair, an entry's first glyph pair) in a new Glyph tab, as FontLab's *Window > New Glyph Tab* does, then sets its text. Each list is checked as its tab is first shown, and again after an undo, a redo, or an edit in FontLab; *Masters* is grayed out for a font with one master. *Restore suggestions* puts a list's checks back as it first came.

On the owner's test font (22,665 pairs kerned tighter, most through classes), the collision check takes about 2.5 seconds and lists 2,735 pairs, mostly accented and barred letters under tall marks (*Ť*, *Ŧ*, *ŧ*, *î*, *Ý*, *ĵ*); cleanup lists 34 values under 5 units and nothing else.

## The methods

Both are measured by FreeLab's native core (*kerning/native/freelab_kern.c*) on glyphs rendered from FontLab's outlines at 200 pixels per em, and both hold each kind of pair to its own references, pairs the designer spaced on purpose and that are set with no kerning: capitals to *HH*, *HO*, *OH*, and *OO*; lowercase to *ll*, *nn*, and *oo*; figures to *0* and *8*; pairs across cases to the references of both sides; punctuation to the kind of the letter beside it. A pair is moved until its measure falls within the band its references span.

- **halfkern** ([behdad/halfkern](https://github.com/behdad/halfkern), Copyright 2022 Google LLC, Apache License 2.0): each glyph gets an envelope, its ink over a halo that fades out over about a tenth of the em at half strength; the measure is the overlap of the two envelopes, the sum of their squared products. The halo grows until *ll*, *nn*, and *oo* agree within a factor of two, as halfkern's does, and FreeLab interpolates between whole pixels where the overlap crosses the band. Checked against halfkern itself on the same renderings (Georgia, 19 pairs): the same kerning for every pair, including the two it cannot kern.
- **Contour distance**, after Matthew Skala's description of Tsukurimashou's kerning ([freetype-devel, June 2012](https://lists.nongnu.org/archive/html/freetype-devel/2012-06/msg00118.html)); written from that description, not from its code. Each glyph's left and right edges are found row by row, and their angle is limited (an edge moves at most 0.6 pixels across a row), so that a shape reaches out into the rows above and below it: a period cannot slide under an apostrophe. The measure is the average over the rows of the inverse cube of the gap between the facing edges, found by bisection. A tightening stops where the two glyphs' ink comes within 2% of the em.
- **FontLab's own** autokern (`flPackage.autoKern`, FontLab 8's "K1"), which returns its value without writing it. It is coarse: on the owner's test font it gave −56 for most pairs it tightened.
- **FreeLab**, FreeLab's own learned method: gradient-boosted trees trained on how fonts are kerned. Its inputs are both methods' readings, the gap between the pair's facing ink in 16 height bands, the two advances, and the font's own spacing (its *nn*, *oo*, and *HH*), all as shares of the em, measured by the same code as the other methods. It has two stages: one decides whether a pair is kerned at all, the other how much (a single one learned to say 0, since most common pairs are not kerned). The model, *kerning/learned_model.json*, is evaluated in plain Python.

### What the FreeLab method learned from, and how it was checked

*kerning/train/dataset.py* reads the fonts installed on the computer it runs on and those in FreeLab's corpus folder (*%LOCALAPPDATA%\FreeLab\corpus*, open-licensed fonts fetched from Google Fonts), and keeps only those whose name table declares the SIL Open Font License or the Apache License, with no proprietary terms beside it (*Segoe UI Historic* names Apache-licensed components in a Microsoft license, and is left out), and that kern: 838 on the owner's computer. Fonts that kern fewer than 5% of the common pairs, the same Latin design under another name, and fonts whose *l*, *n*, and *o* cannot be measured were left out: 856,513 pairs from 615 fonts in 240 families, with the kerning each font applies read through HarfBuzz, ligatures and contextual alternates off (an *fi* ligature is not kerning). The measurements stay on that computer; only the trained model is in the repository. *kerning/train/train.py* trains and checks it.

The families were split into five folds, each held out once (no family in both parts), and the methods' suggestions compared with the held-out fonts' kerning, in units of a 1000-unit em:

| Method | Mean error, all pairs | Mean error, kerned pairs | Within 20 units |
|---|---|---|---|
| No kerning at all | 9.4 | 38.4 | 85% |
| halfkern | 17.3 | 22.5 | 69% |
| Contour distance | 27.2 | 31.7 | 56% |
| Average of the two | 21.9 | 24.9 | 63% |
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
