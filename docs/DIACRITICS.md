# Diacritics

*Scripts > FreeLab > Diacritics* builds the letters with diacritics a font lacks (Latin, Greek, polytonic Greek, and Cyrillic), as glyphs of components, in every master, on its first tab; on its second, *Mark anchors*, it places the anchors and writes the mark features by which scripts that attach their marks (Khmer, Thai, Arabic, Devanagari, and others) set them. Nothing is made until you click *Build checked glyphs*. It needs no groundwork in the font: no anchors, no accented glyphs to learn from, no *.case* marks, not even marks. Where the font has some, it follows them. It was called Accented Glyphs: not every diacritic is an accent (a cedilla, an ogonek, a hook, a breathing).

## What it builds

- **Which characters**: every character of the chosen set (*Character set:* Latin-1 to Latin Extended-B, Latin Extended Additional, Greek, Greek Extended (polytonic), Cyrillic, or *All*) that the font lacks and that Unicode's canonical decomposition splits into a letter and marks (*ǎ* is *a* with a caron, *й* is *и* with a breve). A script the font has no letters of is left out, and the top line says so. A glyph left empty (by FreeLab's first version, which added glyphs without their layers) is listed again and filled under its own name. A glyph that would come out empty (a part with no outline in a master) is not built: the log says which part, the glyph the build added for it is taken out again, and the other checked glyphs are built.
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
- **Polytonic Greek**: a breathing and its accent are one mark, the font's own (*psilioxia*, *dasiavaria*) or its two marks side by side, the breathing first, 0.025 em apart; a perispomeni sits on its breathing (*psiliperispomeni*) or dialytika; the dialytika takes its tonos or varia between its dots. The iota subscript goes under a small letter (*ᾳ*), and after a capital as an adscript (*ᾼ*: the font's *prosgegrammeni*, else its iota), on the baseline, the glyph made wider. A capital's breathings and accents sit at its left, as one.

## Room above and below

A glyph must stay clear of the lines around it at a 120% line spacing (applications' automatic leading): its top below where the line above's descenders come down (1.2 em plus the descender), its bottom above where the line below's tallest letters (the ascender or cap height) come up. A glyph that would not fit is made compact: the gaps of its stack closed to 40%, then its marks made smaller, 5% at a time, down to 70%; the list says what it took. One that still does not fit is listed unchecked: it needs a shorter letter or marks drawn for it.

## Placing marks by hand

Under the list, the selected glyph is drawn large between its letter and a letter the font has with the same base, with the baseline and, dashed, the room a 120% line leaves.

- Click a mark to select it (it is drawn in the highlight color, in a frame with handles). Drag it, or press the arrow keys (Shift: 10 units), to move it; Shift while dragging keeps it on one axis.
- Drag a corner of the frame to scale the mark both ways (Shift: in proportion), or a side to scale it one way; the opposite corner or side stays put.
- Tab selects the next mark, Backspace puts the selected one back, Escape deselects; *Reset diacritics* (*Reset diacritic* for a glyph with one) puts all of the glyph's marks back.
- The changes stay with the glyph as you go down the list, its row's picture follows, and they are built. A mark moved by hand moves by as much in every master, scaled about its own center.
- Click the letter beside the glyph to open that pair in Auto Kerning, once the glyph is built (Auto Kerning measures the font's glyphs).

*Restore suggestions* puts every check and every mark moved by hand back as the list first came.

## Reference

Left of the editor, the selected character is drawn in another font, to compare. At first that is the installed font, among families known for wide coverage (Noto Sans, Gentium Plus, Charis SIL, DejaVu Sans, Segoe UI, Arial, and others), with the most of the listed characters; pick another in its list, and the choice is remembered (*%LOCALAPPDATA%\FreeLab\diacritics.json*). A font that lacks the character (as QRawFont reads the font itself: Windows would otherwise draw another font's glyph under its name) gives way to the font picked before it, or to the next of those families, and the note says so ("Fette Mikado lacks ĭ: shown in Noto Sans.").

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
- The corpus model is measured on Latin, Greek, and Cyrillic composites (202 families); a Greek capital's left-hand marks are left out of it, as they are not above it.

## Mark anchors

Scripts whose marks are not precomposed (Khmer, Thai, Lao, Myanmar, Arabic, Hebrew, Devanagari, and the combining marks of any script) are set by the font's mark features: each mark's anchor meets its base's. The *Mark anchors* tab places them, for the script you pick among those the font has marks of:

- **Bases** (the script's letters that take marks, and their unencoded forms, *beh-ar.init* or *i.2*, by the name before the period) get *top* and *bottom* anchors. Which letters take marks: in Latin, Greek, and Cyrillic, those Unicode composes letters with marks on (*a*, *w*, *ø*, *ł*, the dotless *ı*), not those it has precomposed already (*ẅ*) nor those it composes nothing on (*ª*, *ƒ*); in every script, those at least half the corpus's fonts having them attach marks to (Thai's 46 consonants, not its vowels). A script the corpus says nothing of (Myanmar) takes every letter. The top line counts the letters left out; **marks** (Unicode's nonspacing marks) get the anchor they attach by (*_top* or *_bottom*, by where their ink sits: above or below half the x-height) and the one the next mark attaches to (*top* or *bottom*), for mark-to-mark. Anchors a glyph has already are kept.
- **Ligatures** (Arabic's *lam with alef* and the like: an encoded presentation form such as U+FEFB, a *uniXXXXYYYY* name, or a name of joined letters, *lam_alef-ar*) get *top_1*, *bottom_1*, *top_2*, *bottom_2* (a pair per letter they join; the first letter, read first, is on the right), and the code attaches marks to each part (`pos ligature`). Two-part ligatures take their parts' anchors where the corpus's fonts set theirs: 72% and 22% across, from 19 fonts' mark-to-ligature anchors; longer ones are split evenly.
- **The reph** (Devanagari's ra over the consonant it comes before: *rephdeva*, *Reph.dv*, *dvReph*, and the like, not Marathi's eyelash ra) gets *_reph*, every base a *reph* anchor where the corpus's fonts land it: 77% across the consonant, level with its top (30 fonts).
- **Where**: a base's anchor where the corpus's fonts land a mark on that very letter, shaped through HarfBuzz with all their means at once (anchors, forms they substitute, contextual positioning), from at least 3 fonts: on Thai's *po pla*, *fo fa*, and *fo fan*, a mark above sits left of the ascender, not over it. A letter the corpus has too little of takes its script's rule: over (under) the center of its ink's top (bottom) fifth. Latin takes the letter's placement across only, and its script's rule for the height, which landed marks closer. A mark's anchor sits under (over) the center of its ink. Both by how the corpus's fonts of that script place theirs: *diacritics/train/anchors.py* reads the *mark*, *abvm*, and *blwm* features of 202 open-licensed fonts (Noto Sans and Serif Khmer, Thai, Arabic, Devanagari, Battambang, Hanuman, Sarabun, Kanit, Amiri, Cairo, Hind, Mukta, Poppins, and others) into *diacritics/anchor_model.json*. Thai and Devanagari set their marks right of center (Thai's top anchor at 43% of the base's width right of center, its marks' at their right edge), Arabic 0.10 em above the ink, Khmer 0.07 em.
- **Reference**: beside it, the selected glyph's letter with the sample marks (a mark with the sample letter) in the reference font picked on the first tab, as that font's own features place them, falling back as the first tab's does, then to fonts of that script (Noto Sans Thai, Leelawadee UI, Nirmala UI, and so on).
- **By hand**: the selected glyph is drawn with a mark attached; drag the mark, or press the arrow keys (Shift: 10 units), to move the glyph's anchor (a base's where the mark should sit, a mark's own so that it sits as shown).
- **The code**: *Add checked anchors* adds them in every master, each measured on its own, and, for a font with one master, writes the *mark* and *mkmk* features between FreeLab's marker lines (`markClass` per mark, `pos base` per base, `pos ligature` per ligature, `pos mark` per mark), and the checked substitutions (*ccmp*, *pres*), checked by fontTools' feature parser first. With several masters, the code is left to FontLab's automatic features, which read each master's anchors.

A script's anchor heights come from at least 3 fonts of it; fewer (Hebrew's, Greek's, and Cyrillic's marks below) give way to Latin's. With one script, the *Script:* choice is a plain name.

Tried on fonts of the corpus, their own anchors taken away, the marks land a median 31 units (Noto Sans Thai) to 47 units (Sarabun) across and 27 to 35 up from where the fonts put them; Arabic is roughest (36 across, 117 up in Amiri, whose marks keep heights of their own). The anchors are a start, to adjust by eye.

Each font of the corpus left out in turn of the per-letter placements, the sample mark lands this far from where that font puts it (median, in units of a 1000-unit em; across, then up): Thai 11 and 15 (21 and 31 by the script's rule alone), Devanagari 17 and 18 (64 and 33), Khmer 4 and 0 (18 and 9), Arabic 44 and 59 (81 and 53; its worst tenth from 708 to 164 across), Latin 52 and 38 (60 and 38).

**Substitutions**: the forms some scripts take beside their marks, written when the font has them (a list section of their own, each checkable):

- *Thai* (`ccmp`), by the convention 25 of the corpus's 27 Thai families follow: a tone mark after a mark above takes its smaller form (*.small*); *yo ying* and *tho than* their forms without the tail a vowel below would meet (*.less*), *do chada*, *to patak*, *ru*, and *lu* their shorter forms (*.short*); *lo chula* its shorter form under a mark above. The forms are found by the letter's name in the font, Glyphs' name for it (*yoYing-thai*), or *uni0E0D*, case and hyphens aside. The narrower marks some fonts keep for *po pla*'s ascender are not needed: the anchors set marks beside it.
- *Devanagari* (`pres`): before each consonant, the i-matra (of the font's *uni093F.01*, *iMatra-deva.a03*, and the like) whose hook reaches into it as far as the corpus's fonts with several i-matras reach into that consonant (57% of *ka*'s advance, 88% of *kha*'s; 30 fonts). Its reach is how far its ink goes past its advance.

Tried offline on corpus fonts (their own mark features left out, FreeLab's compiled in with fontTools and shaped with HarfBuzz), Sarabun's Thai and Noto Sans Devanagari's i-matras come out as the fonts' own do, glyph for glyph in the i-matras' case, and Mukta's and Hind's reph sits where theirs does. *diacritics/train/shaped.py* does the shaping for *anchors.py*; the corpus took 73 more open-licensed Thai, Arabic, and Devanagari families from Google Fonts for it (Kanit, Prompt, Sarabun's kin, Cairo, Tajawal, Vazirmatn, Scheherazade New, Poppins, Mukta, Teko, and others).
