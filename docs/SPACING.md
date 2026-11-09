# Auto spacing

*Scripts > FreeLab > Auto Spacing* suggests sidebearings for the drawn Latin letters of the font's current master, shows each glyph between its references as it is and as suggested, and changes only the glyphs you leave checked.

## Using it

1. Space the references by eye first: *H* and *n*, then *O* and *o* (Walter Tracy's method), and *l*, *0*, and *8*. They set the spacing everything else is measured against, and the script never changes them.
2. Run the script: it measures the master as it opens (about a second for 150 glyphs). *Letters* covers the Latin letters to Latin Extended-B; *Letters and figures* adds the figures (leave them out while they are tabular, one width for all); the last choice adds punctuation.
3. The list holds the glyphs with a side at least the given number of units (6 by default) from its suggestion: each side's sidebearing now, the change suggested (below 0: closer to its neighbors), and the width after. Selecting a glyph draws it between two of its references on each side, as it is and as suggested.
4. Uncheck what you disagree with, and click *Space checked glyphs*. A glyph's outline moves by its left change and its width changes by both. *Show in Glyph window*, or double-clicking the glyph's name, opens the glyph between its references in a Glyph window, to adjust it by hand. Clicking a reference beside the glyph in a preview opens that pair in Auto Kerning. *Restore suggestions* puts the checks back as the list first came.

The list covers letters, letters and figures, letters, figures, and punctuation, or *Everything*: every glyph with a character, other scripts' letters spaced by their case (beside H or n) and symbols beside n.

A font with nothing done yet has its references unspaced too. When H's or n's sidebearings look unspaced (a side at its ink, or one side three times the other), the references come first in the list, unchecked, spaced as the open-licensed fonts space theirs: *spacing/train/references.py* measures H, O, n, o, and zero in 398 families into *spacing/reference_model.json*, as shares of the cap height or x-height (H about 0.08 of the cap height on each side, n 0.09 of the x-height, o 0.077). For a font not spaced yet, check them, space them, then click *Analyze*: the other glyphs are measured against them. A font tight on purpose looks the same (the owner's test font sets H's left side at -23 units), so they stay unchecked unless you check them.

Changes go straight into the open font, as one step of FontLab's History: *Edit > Undo* takes them back, and the dialog measures the glyphs again after an undo, a redo, or an edit in FontLab. What a write did goes to the log under the previews. The font's kerning was set for the old sidebearings, so run Auto Kerning afterward, with *Include existing kerned pairs*, to see which pairs now want other values.

## How it measures

Each side is measured as a pair with the glyph's straight reference: *H* for capitals, *n* for lowercase and punctuation, *0* for figures, by the kind of the glyph's base letter (*Ø* takes *H*). Auto Kerning's two methods, halfkern's and contour distance, find the kerning that pair would want to sit as the references sit beside each other (*HH*, *HO*, *OO* for capitals; *ll*, *nn*, *oo* for lowercase); that kerning is what the sidebearing lacks. *T*'s right side is the pair *TH*, its left side *HT*. The two methods' values are averaged, halfkern's tightenings at half strength as in Auto Kerning before its factors are fitted. A side within the references' own range is left as it is, so most sides of round and straight letters stay.

Open shapes get the largest suggestions (*L*, *T*, *K*, *F* on the right): spacing them to look right beside *H* tightens them, where some designers keep them looser and kern their pairs instead. Uncheck those to keep them for kerning.

## Glyphs built from components

A glyph made only of components (*é* from *e* and an acute) is not spaced: it follows the letter it is built on. Moving *e*'s outline moves it inside *é* too, since the component draws *e*'s outline (checked in FontLab 7.2: shifting a layer moves its nodes, and component offsets and widths can be set); with *Glyphs built from components follow the letters they are built on* (on by default), the accents of *é* move with it, and *é* takes *e*'s change of width. A composite built on one that follows (an acute over *ê*) follows in turn. One built on two changed letters (a ligature made of *f* and *i*) is left as it is and counted, to look at.

On the owner's test font, 72 of 156 drawn glyphs had a side 6 units or more from its suggestion, mostly capitals on their right side, and 10 composites followed them.

## Limits

- Only the current master changes. Each master is spaced on its own.
- Sidebearings are read from the ink's bounds, so italic angles are not taken into account.
- Metric keys (FontLab's linked metrics, such as `=H`) are not read: a glyph whose sidebearing is linked takes its key's value again when FontLab recomputes it.
- Anchors and guides of a drawn glyph move with its outline only where FontLab's layer transform moves them; the owner's test font has none, so this was not checked.
