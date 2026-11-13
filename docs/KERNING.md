# Auto kerning

*Scripts > FreeLab > Auto Kerning* suggests kerning for the pairs of the font's current master, one script at a time (Latin, kana, Armenian, or Georgian), by two methods and FontLab's own, shows how far they agree beside the kerning the font has, and writes only the pairs you leave checked.

## Using it

1. Open the font, pick the master to kern, and run the script: it analyzes the master as it opens, and *Analyze* analyzes the font that is current then. *Script* lists the scripts the font has, Latin first (see [Kana, Armenian, and Georgian](#kana-armenian-and-georgian)); choosing another analyzes it. For a font with two scripts or more, its last choice, *All scripts*, analyzes each against its own references and lists their pairs together: a pair's glyphs show its script, and its tooltip names it. Every pair of the script's letters, figures (Latin's), and punctuation the font has is measured by both methods (two marks of punctuation side by side are skipped); about 7,000 pairs take two to five seconds. Each master's results are remembered, each script's apart (in *%LOCALAPPDATA%\FreeLab\kerning-cache*, under a hash of the font's path; uninstalling removes them): the next analysis measures only the pairs whose glyphs changed, and everything again when a reference glyph (l, n, o, H, O, 0, 8) did.
2. The list holds the pairs the font does not kern yet that either method would change by at least the given number of units (20 by default); FontLab's own autokern is asked about them too (a call per pair). *Show* narrows it to letters, letters and punctuation, or figures, and *Common pairs* to the pairs worth kerning even in a font kerned only in part: those common in the text of 24 languages and kerned in fonts ([andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs), MIT; *kerning/common_pairs.txt*), and for the other scripts those common in their text (*kerning/script_pairs.txt*, see below).
3. The columns: each method's value, *Spread* (how far they lie apart), and *Suggested*, from *Suggested values from*: the average of halfkern and contour distance (the default), any one method, or FontLab's. Changing it changes only that column, never the list or its order. The order: largest change, best agreement (the safest pairs to accept together), most common, or alphabetical.
4. Selecting a pair draws it between two dimmed H's (in the other scripts their own straight letter: kana's RO, Armenian's vo, Georgian's in) as it is set now and by each method, a button each (drawn once a pair is selected), with the method's name, value, and key; the one it will take is checked. Clicking another picks it for that pair alone (*Now* keeps the current kerning), and so do double-clicking a value in the list and pressing Ctrl and its number (Ctrl+1 *Now*, Ctrl+2 *Average*, Ctrl+3 halfkern, Ctrl+4 *Contour*, Ctrl+5 *FreeLab*, Ctrl+6 *FontLab*) while the list has the focus (a plain letter or number jumps to the pairs starting with it, as in any list). Clicking one of the H's around the pair, in any button, goes to that H's pair with the glyph beside it (*H* and *T* for *HTo*): it is listed whatever the filters, and measured first when it was not (an accented letter's pair). A pair picked by hand is tinted, its Suggested value bold, and *Only pairs picked by hand* appears to list them; *Reset pair*, Backspace, or double-clicking its Suggested value gives it the suggested value again; *Restore suggestions* puts every check and pick back as the list first came. Space checks or unchecks the selected pair. The line above the buttons says where the pair's value will be written, and the list under it which other glyph pairs that entry kerns (see *Kerning classes*). *Show in Glyph window*, or double-clicking the pair's name, opens the pair between H's, n's, and o's in a Glyph window, to look at it with FontLab's own tools (between the pair's own script's controls where the font has them: Greek's Eta, nu, and omicron, Cyrillic's En, en, and o, kana's RO, NO, and I, Armenian's Vo, vo, and oh, Georgian's In, in, and on, zeros for figures). What a write did goes to the log under the previews; after an undo, a redo, or an edit in FontLab, the current values are read again. The dialog's ? button, then a click on any control, explains it.
5. *Include existing kerned pairs* lists the pairs the font kerns too, those written since included. They are never checked for you: they are the designer's choices, some of which the methods do not model (a j tucked under the letter before it).
6. Uncheck what you disagree with, and click *Write checked pairs*. Each pair is written where its value comes from (see *Kerning classes*); a value of 0 removes the entry unless another entry would then apply to one of the pairs it kerns (then 0 is written). Picks end once written, and the list shows the font's new values. Writing goes straight into the open font: close it without saving to take it all back.

The kerning the font already has acts as a model: with at least three tightenings in it, each method's tightenings are scaled to match how strongly the designer tightens, and the same for loosenings. Without them, halfkern's tightenings are applied at half strength, as halfkern applies them, and contour distance's in full.

### Kerning classes

*Current* is the kerning FontLab applies to the pair, its classes included (`getPlainPairsDict()`): a font kerned by classes (class *T* against class *o*) shows those values, not 0. A pair is written to the entry its value comes from now: its own pair if it has one, or else the pair of its classes, or of its class and the other glyph. With none, it goes to its classes' pair (or its glyphs' where they have no class). A class pair kerns every glyph of both classes (*Tcaron* with *oacute* too); the line above the buttons and the pair's tooltip name it and count its pairs. Checked pairs that share one entry get the value of the most common of them, and the status says how many. FontLab's scripting takes a name that is also a class's as the class, so where an entry names a glyph that shares a class's name (class *l* against glyph *j*, beside a class *j*), the class is renamed for the moment of writing (to a name no class and neither side of the entry bears) and renamed back; renaming a class keeps its pairs.

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
- **Pairs too close with their class's value**: the noted pairs the class tightens now (the member kerns beside the partner exactly as the class's first glyph does, below 0) are listed at the end, each with a value of its own: the class's, loosened by the difference measured, never past 0. *Write checked pairs* writes them as glyph pairs, which the class's value no longer reaches; the class kerns its other glyphs as before. The values are estimates: selecting one draws it under the list, *Now*, *Adjusted* (its own value), and *Base pair* (the class's first glyph beside the same partner), and the *Adjusted* pair's right glyph drags left or right (or Left and Right, Shift for 10 units) to set the value by eye before writing.

On the owner's test font, left out of the counts, 60 of the suggestions were classes the font has already.

## Kerning Check

*Scripts > FreeLab > Kerning Check* (or *Check kerning…* in Auto Kerning) holds three lists for the current master. Nothing changes until a list's button is clicked; writing goes straight into the open font, so closing it without saving takes it back.

- **Collisions**: kerned pairs (tighter than 0) whose ink comes too close at the kerning FontLab applies, classes included, measured on the same renderings as the methods (200 pixels per em, so to about 5 units in a 1,000-unit em). By default a pair is listed when its ink comes within the distance set (2% of the em to start with) *and* that much closer than its base letter beside the same glyph: *Ťj* against *Tj*, *ąj* against *aj*. That is what a class's value does to an accented or barred member it was not set on, and it holds in any font, also one whose letters touch or overlap on purpose (joined crossbars, *TT* kerned to overlap): such pairs are compared with their own base pair, not with a fixed distance. A glyph is a variant of its class's key glyph (the glyph the class is named after, or its first member) when its name starts with the key's and its character is a letter built on the key's letter, or a letter with no decomposition (*Ŧ*, *Ł*); ligatures and other characters (*₩* after *w*) are not. Pairs kerned by an entry of their own are the designer's and are not compared. The list groups the pairs by the glyph that collides (*Ť*: 178 pairs in the owner's test font), closest first; each pair's fix sets it as far apart as its base pair (or, by the absolute measure, at the distance set) and is written as a pair of its own. *Of each other, accented or not* lists every kerned pair within the distance, for fonts whose letters never touch. Both measure the same thing, the narrowest horizontal distance between the two glyphs' ink, row by row, at the pair's kerning; the first (*and that many units closer than without the accent*) also asks that the pair come that much closer than the same pair without its accent or bar. *Common kerned pairs* lists only pairs common in text (the list Auto Kerning's *Common pairs* uses).
- **Cleanup**: entries that change nothing (every pair they cover gets the same value without them), entries overridden for every pair they cover, entries naming a class with no members or a glyph the font lacks (these three checked), and values smaller than the size set (5 units to start with; unchecked, to look at first). *Clean up 3 checked entries* (the count follows the checks) removes the checked ones. Entries are judged most specific first, each as if those found before it were removed: an exception equal to its class's value is listed, and the class entry it falls back on is not. Before removing, the checked entries are judged again on the kerning as it is then: one whose value changed, or that would now change something (an exception whose class pair's value was edited since the check), is left as it is, and the log counts it.
- **Masters**: entries kerned in some masters and not others, entries tightening in one master and loosening in another (an instance between them may collide), and classes whose members differ between masters. A list only: masters differ on purpose as often as by mistake.

Selecting a row draws its pair under the list, its two glyphs see-through so that overlapping ink shows denser: *Now*, *Adjusted* (with its fix, or without the entry), and *Base pair* (Collisions). A collision's *Adjusted* pair can be set by hand: drag its right glyph left or right (only across: the value is all that changes), or click it and press Left or Right (Shift: 10 units); the fix follows, in the list too, and the row is checked. Up and Down there select the next or previous row. *Show in Glyph window*, or double-clicking a row, opens the selected row's pair (a group's first pair, an entry's first glyph pair) in a new Glyph tab, as FontLab's *Window > New Glyph Tab* does, then sets its text. Each list is checked as its tab is first shown, and again after an undo, a redo, or an edit in FontLab; *Masters* is grayed out for a font with one master. *Check all* and *Check none* check or uncheck a whole list, each grayed out when it would change nothing; *Restore suggestions* puts a list's checks back as it first came.

Another script that changes glyphs opens Kerning Check on them: Auto Spacing's *Check kerning of these glyphs…* after spacing, and Diacritics after building glyphs or moving their marks. The lists then hold only what involves those glyphs: Collisions the pairs with one of them (only those pairs are measured, so it is quick), Cleanup the entries naming one or kerning one through a class, and Masters the entries and classes that do. A line over the lists says so (*Pairs with the 12 glyphs Diacritics built: Ŀ ŀ …*), and *Show all* beside it lists the whole font's. Entries are still judged against the whole kerning: an entry is listed the same, limited or not. A script calls it with `freelab_kerning_check.main(glyphs=[names], reason=u"Diacritics built")`, or Auto Kerning's `open_kerning_check(glyphs, reason)`.

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

## Kana, Armenian, and Georgian

*Script* offers each of these where the font has its references (below) and at least 20 of its letters. Each is analyzed on its own, its pairs and their kerning listed and written as Latin's are. *All scripts* runs those analyses one after the other (each with its own references, its own cache, and its factors fitted to its own kerning; kana as palt sets them, left out with a warning when palt does not set them proportionally) and lists their pairs together; a pair is previewed between its own script's straight letter. The status line gives each method's factor per script where they differ.

### What the fonts do

Before any method was chosen, the open-licensed fonts were surveyed: 67 of the 68 Japanese families of Google Fonts (M PLUS 1 Code, monospaced, left out), the Armenian and Georgian ones, and the open-licensed fonts installed on the owner's computer, each pair of their kana (or letters) and punctuation shaped by HarfBuzz with and without kern.

- **Kana**: of those 67 families (a font of each), 14 have palt and 8 kern kana: Noto Sans JP (Source Han Sans, 818 pairs), Noto Serif JP (Source Han Serif, 3,936), IBM Plex Sans JP (2,685), Stick (2,026), Klee One (1,136), and Tsukimi Rounded (332), all with palt; Cherry Bomb One (8,431), whose kana are proportional; and LINE Seed JP (6,887), whose kana are full width with no palt (Slackside One kerns a single pair). Of the open-licensed fonts installed, Otomanopee One (24,109, proportional) adds a design; GenEi Gothic and Satsuki Gendai Mincho repeat Source Han's. Every one of them puts its kana pairs in kern, applied the same with palt on or off. What they kern: katakana with open sides (*アノ*, *クム*, *ケイ*), kana before the comma and full stop (*す。*, *ア、*: 305 of Noto Sans JP's 818 pairs), small kana (*っ*, *ゃ*), and the long vowel mark.
- **Armenian**: Google Sans kerns 2,705 pairs (its question mark, set over the vowel, most of all), Noto Sans Armenian 568, Noto Serif Armenian 346; Handjet, a pixel design, none.
- **Georgian**: Google Sans kerns 539 pairs, most of them Mtavruli or punctuation; Noto Sans Georgian kerns 848, and Noto Serif Georgian 1,237.

Kana are kerned by too few designs for the FreeLab method to learn from (it was tried, below), so kana take the measured methods, halfkern and contour distance, with references of their own. Armenian and Georgian take them too, and the FreeLab method as trained on Latin: held out on their families, it came closer than the measured methods, and training it on their pairs as well did not help (see *The FreeLab method in other scripts*).

### Kana

- **On top of palt**: kana are measured as the font's palt sets them, so the kerning adds only what palt leaves uneven and never undoes a trim. palt is read from the font's feature code (single adjustments, `pos a-hira <-70 0 -130 0>;` as CJK Spacing writes them, `[lists]` and `@classes` too). Kana proportional already (most narrower than 90% of the em) are measured as they are. Full-width kana that palt does not narrow are not kerned at all: kerned, they would be kerned in full-width text too. Write palt with CJK Spacing first.
- **Where the kerning goes**: into the font's kerning, FontLab's kern feature, as every font above kerns its kana: their kana pairs apply the same with palt on or off (HarfBuzz applies kern by default), so in full-width text too unless the application turns kerning off there.
- **References**: one kind for all kana, hiragana, katakana, small kana, and the long vowel mark alike: a square, a round, and an open kana, RO, NO, and I (ロ, の, い), set with each other under palt with no kerning. The band they span is wide, so that most pairs palt sets evenly are left alone. The halo is tuned on RO and grows until every pair of references overlaps: under palt, kana sit far apart, and no three kana agreed within a factor of two in every font tried. Small kana, the long vowel mark, and punctuation beside a kana (*す。*, *ア、*, the pairs fonts kern most) are held to the same band.
- **Pairs**: the 2,970 kana pairs common in text are measured (all of them, some 45,000, would each be listed and asked of FontLab), counted in 600 public-domain works of Aozora Bunko in modern orthography, the ruby and the library's notes taken out; together they make up 95% of the pairs of kana and punctuation in those texts.
- **Previews** are drawn as palt sets the kana. FontLab's Glyph window sets them as the glyphs' widths are, full width where palt narrows them: *Show in Glyph window* proofs a pair between RO, NO, and I, without palt.

### Armenian and Georgian

- **Armenian**: capitals against vo and oh (Ո, Օ), lowercase against vo, seh, and oh (ո, ս, օ), the halo tuned on the lowercase three; previews and proofs between vo, the capital too.
- **Georgian**: Mkhedruli against in, on, and san (ი, ო, ს), Mtavruli against their capitals (Ი, Ო), the halo tuned on in, on, and san, or on in and on alone where san is spaced far looser (Noto Serif Georgian); fonts without Mtavruli are kerned in Mkhedruli alone.
- **Pairs**: 1,614 Armenian and 1,113 Georgian pairs, counted in the introductions of 1,200 Armenian and 680 Georgian Wikipedia articles (Creative Commons Attribution-ShareAlike 4.0; see *kerning/script_pairs.txt*), 99% of their letter pairs. All-capital pairs (Armenian capitals, Mtavruli) are the lowercase pairs set in capitals.

### How close they come

Each method on the common pairs of the corpus fonts that kern the script, against the font's own kerning, in units of a 1000-unit em, each method's strength fitted to that kerning as Auto Kerning fits it (the average of halfkern and contour distance, the default suggestion; *corr.* is its correlation with the font's kerning on the pairs the font kerns):

| Font | Script | Kerned pairs | Error on all pairs (none / average) | Error on kerned pairs (none / average) | Corr. |
|---|---|---|---|---|---|
| Noto Sans JP | kana, palt | 196 of 2,970 | 2.3 / 10.3 | 34.4 / 23.6 | 0.45 |
| Noto Serif JP | kana, palt | 246 | 2.8 / 12.4 | 33.7 / 30.5 | 0.62 |
| IBM Plex Sans JP | kana, palt | 382 | 3.8 / 18.7 | 29.9 / 26.9 | 0.53 |
| Klee One | kana, palt | 344 | 5.2 / 13.0 | 45.2 / 43.3 | 0.61 |
| Stick | kana, palt | 270 | 5.1 / 22.2 | 56.2 / 32.1 | 0.59 |
| Cherry Bomb One | kana, proportional | 1,562 | 15.5 / 24.9 | 29.4 / 8.9 | 0.92 |
| Otomanopee One | kana, proportional | 1,861 | 33.7 / 32.3 | 53.8 / 19.9 | 0.85 |
| Google Sans | Armenian | 721 of 1,614 | 9.9 / 10.5 | 22.2 / 15.3 | 0.68 |
| Noto Sans Armenian | Armenian | 134 | 2.6 / 7.2 | 30.8 / 20.7 | 0.65 |
| Noto Serif Armenian | Armenian | 121 | 2.5 / 11.4 | 32.8 / 20.1 | 0.71 |
| Google Sans | Georgian | 105 of 1,113 | 2.2 / 4.7 | 23.1 / 10.1 | 0.88 |
| Noto Sans Georgian | Georgian | 258 | 3.6 / 8.2 | 15.4 / 7.5 | 0.72 |
| Noto Serif Georgian | Georgian | 375 | 6.7 / 11.5 | 19.8 / 15.8 | 0.50 |

As for Latin, leaving every pair alone comes closest over all pairs where a font kerns few of them; the methods come closer on the pairs it does kern, most where it kerns many (Cherry Bomb One and Otomanopee One, whose kana are proportional). Contour distance follows Noto Serif Georgian far more closely than halfkern does (a correlation of 0.59 against 0.35).

### The FreeLab method in other scripts

*kerning/train/train.py* scores each script on its own, the same five folds by family, so that adding a script's pairs can be checked not to make Latin's worse. The corpus's Armenian, Georgian, and kana fonts (above) were measured beside the Latin training set (*dataset.py --scripts*), and the model trained on Latin alone, then on Latin, Armenian, and Georgian, then on all four. Mean error in units of a 1000-unit em, all pairs / pairs the fonts kern, each method at its default strength:

| Script | Pairs (families) | No kerning | Average of halfkern and contour | FreeLab, trained on Latin | FreeLab, trained on Latin, Armenian, and Georgian | FreeLab, trained on all four |
|---|---|---|---|---|---|---|
| Latin | 856,513 (240) | 9.4 / 38.4 | 21.9 / 25.0 | **8.5 / 20.9** | 8.5 / 21.1 | 8.5 / 21.1 |
| Armenian | 4,842 (3) | 5.0 / 34.1 | 10.7 / 24.9 | 7.2 / 22.5 | 7.2 / 22.3 | 7.4 / 22.4 |
| Georgian | 3,339 (3) | 4.1 / 27.2 | 7.9 / 14.6 | **5.9 / 9.2** | 6.1 / 10.5 | 5.8 / 10.4 |
| Kana | 20,787 (7) | 7.9 / 42.3 | 18.6 / 29.6 | 7.9 / 42.3 | 8.1 / 42.3 | 7.6 / 37.8 |

The model trained on Latin alone is kept (its trees are the ones *kerning/learned_model.json* had) and used for Armenian and Georgian; their own pairs, from three families each, made Latin's and Georgian's kerned pairs a little worse. For kana it says 0 almost throughout, and trained on kana too it still misses most of what the fonts kern: kana keep halfkern and contour distance.

## Scripts and characters

Auto Kerning lists pairs of these characters only, a script at a time:

- **Latin**: the letters A to Z and a to z, the figures 0 to 9, and the punctuation `. , : ; ! ? ' " - ( ) [ ] { } / & *`, the curly quotes, guillemets, and the en and em dashes.
- **Kana**: hiragana and katakana (small kana, the iteration marks, and the long vowel mark included), with the ideographic comma and full stop, the corner, angle, and lenticular brackets, the full-width comma, full stop, colon, semicolon, question and exclamation marks, and parentheses, the middle dot, the wave dash, the ellipsis, and the curly quotes.
- **Armenian**: the capitals and small letters (U+0531 to U+0587), with Armenian's apostrophe, emphasis mark, exclamation mark, comma, question mark, full stop, and hyphen, and the Latin comma, full stop, colon, parentheses, guillemets, hyphen, and dashes.
- **Georgian**: Mkhedruli (U+10D0 to U+10FF) and Mtavruli (U+1C90 to U+1CBF), with Latin's punctuation and the low and high double quotes.

Any other character, accented Latin letters (é, Å, ł) and kanji included, is not measured, not listed, and never written: its pairs keep the kerning the font gives them.

| Method | What it could measure | What it is set for |
|---|---|---|
| halfkern | any glyphs: it measures shapes | each script's references: Latin's *l*, *n*, *o*, *H*, *O*, *0*, *8*, and those above; another script needs references of its own (*н* and *о* for Cyrillic, for instance) |
| Contour distance | any glyphs | the same references; Tsukurimashou tuned the method for Latin, Japanese, and Korean, with other settings for each |
| FontLab's own | any glyph pair | nothing of FreeLab's: FontLab's own settings |
| FreeLab | the pairs it was trained on | Latin pairs of open-licensed fonts; used for Armenian and Georgian too, where it was checked on families it never saw; not for kana |

Accented letters take their base letter's kerning where the font's classes hold both: a pair written to a class pair kerns them too.

## Limits

- Classes are used, not made: a font without classes gets glyph pairs, and its accented letters keep their own kerning. Classes are suggested for Latin only.
- Latin, kana, Armenian, and Georgian (see *Scripts and characters*); pairs across scripts (a katakana word before a Latin one) are not measured.
- Kana are kerned only as palt sets them or where they are proportional already; their kerning applies wherever kern does, full-width text included, as in the fonts that kern kana.
- Each method has blind spots: halfkern loosens *Ty* in Georgia, where the T's bar meets the y's arms, and cannot kern *VA* there. Review before writing.
- Other published methods, and the one not to implement (Apple's, patented until 2033), are in [FEATURE-SURVEY.md](FEATURE-SURVEY.md).
