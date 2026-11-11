# Feature code

*Scripts > FreeLab > Feature Code* writes the OpenType code for the font's ligatures, for alternates that take turns, and for the forms its glyph names call for (case-sensitive forms, localized forms, fractions and figures, small capitals, stylistic sets). The code is shown, and checked by fontTools' feature parser (FontLab 7 ships it), before anything is written.

The window has two tabs over its lists, *Ligatures and alternates* and *Forms*, and one code part under both: it shows everything the *Write the code* button would write, whichever tab is open.

## Ligatures

The list holds every ligature of the font: the simple rules of its `liga` and `dlig` features (`sub f f t by f_f_t;`, `sub parenleft c parenright by copyright;`), and each glyph whose name joins glyphs of the font with `_` (*l_l*, *f_f_t*) that no rule makes yet. Each is set to:

- **Standard** (`liga`): on unless the user turns it off. In InDesign and Illustrator, the *Ligatures* option; on the web, `font-variant-ligatures: no-common-ligatures`.
- **Discretionary** (`dlig`): off unless the user turns it on (*Discretionary Ligatures*; `font-variant-ligatures: discretionary-ligatures`).
- **Off**: in neither.

So yes, every ligature can be turned off by the user, except in apps that offer no switch; *Off* takes it out of the font's code altogether. A ligature's rule starts in the feature it is in now; a glyph no rule makes starts as Discretionary, or Standard when its name ends in `.liga`.

The rules are written longest first, in a block between FreeLab's marker lines; every other line of the two features stays as it was (in the owner's test font, the hand-written rules that set a standalone *I*). FontLab rewrites the code between its `#> feature` and `#< feature` lines when it updates its automatic features, which it does on compiling and exporting with *Update on Compile* on. A feature written here has that first line turned into `#/> feature`, FontLab's documented way of handing a feature back to you, so FontLab no longer rewrites it; its code stays as it was.

## Alternates that take turns

For a handwriting font: a letter with alternates (named *X.2*, *X.3*; *X.alt*, *X.alt1*; or *X.calt1*) takes its next form when its nearest earlier form, within a few letters (2 by default), is the one before it: *l*, *l.2*, *l*, *l.2*. Doubled and nearby letters vary as handwriting does, and the same text always comes out the same. Only letters stand between: a space or punctuation ends the look back, so each word starts afresh. Stylistic sets (*X.ss01*) are the *Forms* tab's.

The code is a `calt` lookup (contextual alternates, on unless the user turns it off) between FreeLab's marker lines; the rest of `calt` stays. An alternate the font's code already uses for something else is listed but left unchecked, with a note: taking turns would undo its job. In the owner's test font, *I.2* is the standalone *I*, set in `liga`, so *I* stays out, and *N*, *i*, *j*, and *l* take turns. `aalt` and `salt`, which list every alternate as a menu, do not count as a job.

`calt` comes after `liga` in the font, so ligatures form first: where `liga` makes *l_l* of *ll*, the alternates take turns around it.

## Forms

The *Forms* tab lists one row per feature the font's glyph names call for, with its substitutions under it (click the row's arrow; their pictures are drawn as a feature opens). A checked feature is written with its checked rows. Each feature's code sits in a FreeLab block between marker lines, in named lookups (*FreeLab_case*, *FreeLab_frac_numerators*, and so on). A glyph's form is found by its suffix wherever the suffix stands among its others: *a.sc.ss01* is the small capital of *a.ss01* and the `ss01` form of *a.sc*.

The check boxes of the lists (the alternates, the forms, and the figure forms to build) are drawn in the window's own colors, a gray frame, or the highlight color with a check mark when checked, so they show in dark mode too, which leaves these lists' pictures as they are drawn.

- **case** (case-sensitive forms, for text in capitals): every *X.case* of a glyph *X*: hyphens and dashes, brackets, guillemets, *at*, and marks (an *acutecomb.case* raised for capitals), whatever the font has.
- **locl** (localized forms, for text tagged with a language): one row per language and substitution.
  - Romanian and Moldavian (`ROM`, `MOL`): *S* and *T* with a cedilla (U+015E, U+015F, U+0162, U+0163) become the comma-below letters (U+0218 to U+021B). The code points decide, not the names: Adobe's *Tcommaaccent* is U+0162, the *T* with a cedilla. Where one glyph holds both code points (an old Romanian encoding), the other direction: the languages that write a cedilla (Turkish, Azerbaijani, Crimean Tatar, Gagauz, Kazakh, Tatar, Turkmen, Kurdish; Gagauz for *T*) take the font's unencoded *Scedilla* (or *uni015E*).
  - Catalan (`CAT`): between two *l*'s, the middle dot becomes *periodcentered.loclCAT* (between two *L*'s its *.case* form, where the font has one); a font without it but with *ldot* (U+0140) and *Ldot* sets *l·l* as *ŀl*.
  - Dutch (`NLD`): after *í*, *j* takes an acute (*jacute*, *uni006A0301*, or *j_acutecomb*), and *J* after *Í*; a ligature named for the language (*iacute_j.loclNLD*) replaces the pair.
  - Turkic languages (`TRK`, `AZE`, `CRT`, `KAZ`, `TAT`, `BSH`, `GAG`): *i* becomes *i.loclTRK* (or *idotaccent*), so it keeps its dot in capitals and small capitals; `smcp` then takes *i.sc.loclTRK* (or *Idotaccent.sc*). The row says when the font has no small capital *İ*.
  - Any other glyph named *X.loclXXX*: the language from the suffix (*loclVIET*, Glyphs' name, is `VIT`; *loclMARNEP* is Marathi and Nepali), the script from *X*'s character (`cyrl` for *uni0434.loclBGR*; `dev2` and `deva` for Devanagari; for a glyph of no script, such as a middle dot, the language's usual one). A ligature named so (*Iacute_J.loclNLD*) replaces its parts. A language tag FreeLab does not know is written as named, with a note to check it. The font's own *X.loclXXX* wins over a convention for the same glyph and language.

  The rows are grouped by script and language (`script latn; language ROM;`), a lookup per kind of rule. Each language needs a `languagesystem` line in the prefix, or the font's other features would be missing for text in it: FreeLab adds the ones the prefix lacks in a block of its own after the prefix's last `languagesystem` line (with `DFLT dflt` first where the prefix has none, since declaring one language would otherwise drop the default), and takes it out again when no locl row needs it.
- **frac**, **numr**, **dnom**: a figure's numerator is its *.numr* form (or *.numerator*), its denominator its *.dnom* form (or *.denominator*); where a figure has a denominator but no numerator, `frac` takes its superior. `frac` is the usual three lookups for the text a user selects as a fraction: the slash becomes the fraction bar (U+2044; without one, the slash divides), every figure a numerator, and each numerator after the bar or a denominator a denominator (*1/2*, *12/25*). A figure's other forms (*one.tf*, *one.osf*) take the same numerator and denominator.
- **sups**, **subs**, **sinf**: *.sups* (or *.superior*); *.subs* (or *.inferior*, *.inf*, *.sinf*); *.sinf* (or *.inferior*, *.inf*, *.subs*). Where a glyph has no such form, the font's Unicode superscript or subscript character of it (*twosuperior*, *uni2082*) does, but not the ordinal indicators.
- **ordn**: after a figure, and after a figure and a period (Spanish *1.º*), *a* and *A* become *ª* (or *a.ordn*), *o* and *O* *º* (or *o.ordn*), and letters with an *.ordn* form take it, one after another (*1er*, *2nd*).
- **smcp**, **c2sc**: from *.sc*, *.smcp*, and *.c2sc*. A lowercase letter takes its own form in `smcp` (*a.sc*, or *a.smcp*), else its capital's (*A.sc*), else the small capital of its capital's lowercase letter (dotless *ı*: *i.sc*); a capital takes its own form in `c2sc` (*A.c2sc*, *A.sc*), else its lowercase letter's (*a.sc*). A glyph of no case (*ampersand.sc*, *one.sc*) is in both.
- **lnum**, **onum**, **pnum**, **tnum**: the suffixes say each set's spacing and style as Glyphs names them (*.tf* tabular lining, *.lf* proportional lining, *.osf* proportional oldstyle, *.tosf* tabular oldstyle), or one of the two (*.tnum*, *.pnum*, *.lnum*, *.onum*: the other is read from the set's own widths and ink, else is the default figures'). The default figures' style is read from their widths (most of them one width: tabular), from their ink (a zero lower than the eight: oldstyle), else from the suffixes (a font with *.tf* and *.osf* has proportional lining defaults); the *Forms* tab and each figure feature say which. Each feature maps every set to its counterpart (`tnum` takes *one* to *one.tf* and *one.osf* to *one.tosf*), so features combine; where the font has oldstyle figures at one spacing only, `onum` takes them anyway (tabular lining defaults with proportional *.onum* figures, as in Crimson). The figures of a tabular set must share one advance width: those that do not are amber warning rows under `tnum`, never checked and never changed.
- **ss01** to **ss20**, **cv01** to **cv99**: one feature per suffix, its name written as `featureNames { name "..."; };` (a character variant's as `cvParameters`), first in the feature. The name is suggested from what the set changes and can be edited in the feature's row: *Single-story a* where the outlines tell (an *a* whose counter reaches near its top is single-story, a *g* of three contours double-story; read from the contours' boxes in the current master), else *Alternate a and g*, *Alternate figures*, *Alternate capitals*, or *Alternate A, E, F, and others*. A name the font's own code gives the set is kept and shown, not edited.
- **aalt** (Access All Alternates): what InDesign and Illustrator offer as a selected character's alternates, in place and in their *Glyphs* panel. It refers to every feature with one-for-one alternates (`feature case;`, `feature ss01;`, and the like: case, small caps, figures, superiors and inferiors, salt, swash, titling, the sets), only while it has code, and offers each ASCII character the font draws a look-alike spacing accent for (~ and ˜, ^ and ˆ, ` and ˋ, " and ˝, ' and ʹ) as the other's alternate: the character typed stays, so a search still finds it. Written, aalt is moved first among the font's features (the compiler takes it only there; a feature FontLab adds goes last).

### Figure forms to build

Under the forms, *Figure forms to build* lists what the font lacks for those features, in sections (click a section's arrow for its glyphs, each drawn beside its figure as it would be built):

- **Numerators** and **denominators**: each figure without a *.numr* (or *.numerator*) or *.dnom* (or *.denominator*) form.
- **Superiors** and **inferiors**: each figure without a *.sups* or *.subs* form and without the Unicode character `sups` or `subs` takes instead.
- **Superscript figures** (U+2070, U+00B9, U+00B2, U+00B3, U+2074 to U+2079) and **subscript figures** (U+2080 to U+2089) the font does not encode.
- **Ordinal indicators**: *ª* and *º*, where the font has *a* or *o* but not them.

Names follow the font's: the suffix most of its figures use for the set (*one.numerator* in the font: *two.numerator*), and its names for the Unicode figures (*onesuperior*: *foursuperior*, and *fourinferior*); else *.numr*, *.dnom*, *.sups*, *.subs*, and *uniXXXX*, and *ordfeminine* and *ordmasculine*. A name a glyph without the code point already has is not built beside it.

Each is made of components:

- **Scaled**: the figure (its lining form where the default figures are oldstyle; *a* or *o* for an ordinal indicator), scaled, raised or lowered to its set's baseline, and centered in a width a little wider than the scaled figure's.
- **Copied**: a Unicode superscript or subscript figure is its set's form of the figure (*uni00B2* is *two.sups*), where the font has it or it is checked to be built too.
- **Moved**: where the font has a whole drawn set (all ten figures), a set it lacks is that set moved, unscaled, to its own baseline: drawn small figures beat scaled ones.

The settings row shows and changes one set's scale (of the figure's height), baseline (where the scaled figure's baseline goes, in font units), and width (of the scaled figure's advance); clicking a row picks its set, and *Suggested* puts the set's settings back. Changing the scale of the numerators or of the ordinal indicators keeps their top where it is. The first settings are the font's own where it has drawn forms of the set (the medians of their scale, baseline, and width); a set it has none of takes the size of its other small figures, else the corpus's; and is placed as the corpus places it: a numerator's top at the figures' top, a denominator on the baseline, a superior's baseline at 0.51 of the cap height, an inferior's at −0.17, an ordinal indicator's top at 1.01 of the cap height (or at the font's other indicator's top). Cap height is the current master's.

*Build checked glyphs* (*Build 12 checked glyphs*: the count of the checked rows that can be built) adds them at the end of the font in every master, as one step of FontLab's History: *Edit > Undo* takes them back. Each glyph's code point is set once its layers are made. Placements come from the current master's measures; widths from each master's own figures. The font is then read again, and the forms above take the new glyphs (a feature that was not there, such as `sups`, now has its row): check it and write the code.

Scaling thins strokes: a figure at 59% has stems 59% as thick as the figure's, where the corpus's drawn small figures have ink about 7% wider than scaling gives. FreeLab does not compensate the weight; a built form is a start to draw over, and the window says so.

The settings come from *features/train/figure_forms.py*, which measures the small figures of the open-licensed fonts in *%LOCALAPPDATA%\FreeLab\corpus* (182 families with lining default figures; 6 with oldstyle defaults left out). Medians, with the quartiles:

| Set | Families | Scale | Baseline (of cap height) | Top (of cap height) | Advance over the scaled figure's |
| --- | --- | --- | --- | --- | --- |
| *.numr* | 49 | 0.57 (0.53–0.61) | 0.45 (0.40–0.48) | 1.01 (1.00–1.02) | 1.12 (1.05–1.19) |
| *.dnom* | 49 | 0.57 (0.53–0.61) | 0.00 (−0.01–0.00) | 0.54 (0.53–0.61) | 1.12 (1.04–1.19) |
| *.sups* | 68 | 0.59 (0.53–0.62) | 0.51 (0.45–0.59) | 1.11 (1.01–1.16) | 1.12 (1.05–1.17) |
| *.subs* | 63 | 0.59 (0.53–0.62) | −0.17 (−0.23–−0.13) | 0.42 (0.36–0.51) | 1.11 (1.04–1.16) |
| *.sinf* | 41 | 0.53 (0.53–0.60) | −0.15 (−0.22–−0.13) | 0.42 (0.33–0.51) | 1.12 (1.09–1.18) |
| Superscript figures | 143 | 0.59 (0.53–0.63) | 0.49 (0.41–0.57) | 1.03 (1.00–1.16) | 1.13 (1.06–1.20) |
| Subscript figures | 77 | 0.60 (0.53–0.61) | −0.17 (−0.24–−0.13) | 0.41 (0.35–0.50) | 1.11 (1.04–1.17) |
| *ª*, *º* (their letter) | 164 | 0.66 of *a*, *o* (0.61–0.70) | 0.54 (0.50–0.57) | 1.01 (1.00–1.03) | 1.07 (1.03–1.13) |

Their advance is 0.63 of the figure's; their ink is 1.07 times as wide as the scaled figure's (1.03 for the ordinal indicators). In 5 of the 49 families the numerators are the superior glyphs.

Taking the small figures out of the 36 corpus families with all ten *.numr* and planning them again from the corpus settings, the planned glyphs land within a median of 0.007 of the cap height of the drawn numerators' tops and 0.003 of the drawn denominators' bottoms (355 glyphs each); their advance within 8% of the drawn one's; their left side bearing 0.02 to 0.03 of the cap height larger (the drawn ones are wider). The few superiors among those families sit higher and smaller than most (0.10 of the cap height above the planned ones): the settings row is there for such a font.

### What starts checked

Every feature starts checked, but:

- one the font's code has by hand (code outside FontLab's automatic block and FreeLab's, or in a block handed back from FontLab) starts unchecked, with a note: checked, FreeLab's block goes in beside it and the rest is kept;
- one whose only code is FontLab's automatic code, when that code already makes every checked substitution and FreeLab's would add nothing else (no context, no name), starts unchecked and is left to FontLab.

When a feature with FontLab's automatic code is written, that code is replaced by FreeLab's block (the `#> feature` line handed back as `#/> feature`, what the block held dropped): two versions of the same feature would otherwise both run. A feature whose FreeLab block is in the font but whose glyphs are gone is listed with no rows; writing takes the block out. An unchecked feature's block is taken out as well.

### The checks on real fonts

*features/train/forms_check.py* makes every form feature of an open-licensed font as Feature Code would (on a font with no features), compiles it into a copy of the font with its own `GSUB` taken out (fontTools' feaLib), and shapes test strings with HarfBuzz. On Montserrat Regular, Big Shoulders Display Black, Crimson Roman, and Alegreya SC Regular, 67 of 67 checks pass: *1/2* and *12/25* under `frac`; *(H)* and *A-B* under `case`, in Romanian text too; *a* and *A* under `smcp` and `c2sc`; Romanian *ş* as *ș* (and not in Turkish), Turkish and Azerbaijani *i*, Turkish *i* in small capitals as *i.sc.loclTRK*, Catalan *l·l* (and not in Spanish), Dutch *íj*, Bulgarian *д* (and not in Russian); `ss01`, `tnum`, `onum`, `onum` with `tnum` (*one.tosf*), `sups`, `sinf`, and `ordn` (*1a*, *1.o*, and a lone *a* left alone). The *a* and *g* stories it reads agree with the outlines (Montserrat's *a* double-story, *a.ss01* single-story; Big Shoulders' *g* double-story, *g.ss01* single-story).

A survey of the glyph names of 400 open-licensed families (*%LOCALAPPDATA%\FreeLab\corpus* and the system's fonts) found the suffixes these features read: *.case* in 98, *.loclTRK* in 90, *.dnom* in 69 and *.numr* in 68, stylistic sets in 59, *.loclCAT* in 55, *.tf* in 31, *.sc* in 28, *.lf* in 28, *.tosf* in 23, *.osf* in 22, *.subs* in 12, *.sinf*, *.sups*, and *.superior* in 11 each, and *.smcp* in 8; among the *.locl* suffixes, `BGR`, `VIET`, `NLD`, `SRB`, `BSH`, `TRK`, `GUA`, `CAT`, `PLK`, `CHU`, `MAR`, `VIT`, `MKD`, and `NEP`, with *MARNEP* for two languages at once. Few sets carry names in those fonts (*Round E*, *Alternate ampersand*, *Single-storey a*): names come from the designer, so FreeLab only suggests one.

## Limits

- Only simple ligature rules (glyph names in, one glyph out) are listed; contextual rules and rules with classes stay as they are, where they are.
- The look back counts glyphs of letters (letters, their alternates, ligatures, and accented letters of the font); a mark or a symbol between ends it.
- Writing goes straight into the open font, as one step of FontLab's History: *Edit > Undo* takes it back. With *Compile after writing* (on by default) the features are compiled right after, by the *Features* panel's own *Compile* button (FontLab has no call for it; the panel must have been opened once in the session); off, compile them in the *Features* panel to try them.
- A ligature that neither the font's code nor its name's suffix (*.liga*, *.dlig*) places starts where most of the open-licensed fonts FreeLab learned from put it: *features/train/ligatures.py* counts, per character sequence, the families that make it in liga or clig and in dlig or hlig, into *features/ligature_model.json* (409 families, 252 with ligatures: *f_i* in liga in 214 of 224, *f_f_i* in 124 of 127, *c_t* and unit squares in dlig). One the corpus does not have starts discretionary, to be safe. The feature's tooltip says why.
- The code is made again as the choices change. Pick a ligature's feature in its box (the list scrolls as usual with the boxes in it); drag between the lists and the code to give one more room; the *Cycle* column shows the forms a letter takes in turn. Double-click a ligature, a letter, or a form to see it in a Glyph window. *Write the code* becomes *Update the code* once FreeLab's code is in the font, and grays out while the font has the code shown. *Restore suggestions* puts the choices, checks, and set names back as they first came; the log says what was written.
- Features run in the order FontLab's *Features* panel lists them. A new feature goes where FontLab puts it (written in the order `locl`, `case`, `frac`, and so on to `ss01`); `locl` should come before `smcp` for the Turkish *i* to find its small capital: move it up in the panel if the font's other features come first.
- FreeLab's block goes at the end of a feature (first, for a set's name). Where the feature's own code sets a language (`language TRK;`) before it, the block would apply to that language only: the row says so.
- `frac` turns every figure of the selected text into a numerator until the bar: in *1 1/2*, select only *1/2*.
- `aalt` is not updated with the new forms.
- Built figure forms are scaled outlines, not drawings: their strokes are thinner than the figures', and nothing compensates the weight. Placements are measured in the current master and used in every master. Superscript and subscript signs (⁺, ₋), letters (ⁿ, ₐ), and the bar under some ordinal indicators are not built.
- Where FontLab cannot write the prefix from a script, `locl` is not written (its languages would lose the font's other features), and the log gives the lines to add to the prefix by hand. Writing the prefix uses `set_prefix`, which mirrors the proven `get_prefix` but has not yet been tried in FontLab.

## Stylistic alternates

The third tab lists the characters fonts vary most in their stylistic sets, counted in the open-licensed fonts of FreeLab's corpus (*features/train/alternates.py*: in how many families an `ssXX`, `cvXX`, or `salt` feature varies each; of 412 families, 128 have alternates, and *a*, *g*, *Q*, *G*, *R*, *A*, *l*, *I*, *J*, *t*, *y* lead), those the font has, with the alternates it has already. A checked one gets a starting copy named for the next free stylistic set (*a.ss01*), its outlines as they are, to redraw; the *Forms* tab writes the set.

*Variants that take turns* makes copies of each letter in scope (lowercase, capitals, or both), changed a little as a whole: a slight rotation, uneven scaling, a slant, and a baseline shift, each drawn within the chosen strength's reach (*Subtle*: 0.8°, 2%, 1°, 0.5% of the em; *Moderate*: 1.5°, 4%, 2°, 1%; *Bold*: 3°, 7%, 4°, 2%) from a seed, so the same seed makes the same variants. They are named *X.alt1*, *X.alt2*…, which *Alternates that take turns* on the first tab cycles. Nodes are never moved one by one: tools that jitter every point break smooth curves and read as noise rather than a hand; whole-glyph changes keep the drawing. A font with several masters or drawn alternates has better material for variety; these variants are for the many fonts that have neither.
