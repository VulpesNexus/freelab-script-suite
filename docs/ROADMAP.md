# Roadmap

## Next

1. Dark mode's remaining display defects. Every dialog FontLab's menus open has now been looked at (34 on 2026-11-24 with a static and a variable font open, the rest by the owner that day: *Create Instance*, *Place As Glyphs*, and *Compare Fonts* are dark; *Paste Special* and *Zoom* open no window of their own; *Adjust Stem Thickness* is not a FontLab 7 command). What the owner's review of that day found, still to fix, each to be looked at again in a fresh session first (a probe of that afternoon left dark mode unable to examine new widgets for a while, and some of these may be its doing):
   - Dialogs and panels: *Overlay Fonts* (the sample text's edges, the name labels, the opacity dropdown), *Autotrace*'s slider handles, *Replace Element*'s two buttons, *Compare Fonts*' color dropdown, *Add Variation*'s dropdown as it opens, the *Actions* panel (its list's first row, small labels, an underlined unit), *FontAudit*'s captions and *TrueType Hinting*'s size numbers (colored fringes), the *Fonts* panel's style-link letter in its blue circle, panel titles while the mouse is over them, and the view buttons that keep stale painting.
   - The Glyph window: text typed in its small fields, Matchmaker's dotted line, the Sketchboard's and the metrics table's text, and a pasted picture, which the canvas' mapping inverts.
   - Speed: menus are slow to answer while many cells of a Font window are selected.

## Open work the tools' pages record

- The few FontLab calls still not proven live, each listed with how to check it (most were proven on 2026-11-24, Family Audit's *Assemble as masters* run end to end among them): [Family Audit](FAMILY-AUDIT.md#fontlab-calls-proven-live-and-not-yet), [Font Compare](FONT-COMPARE.md#fontlab-calls-not-yet-proven-live), and [Font Check](FONT-CHECK.md#fontlab-calls-not-yet-proven-live).
- Glyph Compose's next scope, built on 2026-11-24 and run live that day for six of its eight kinds (superscript letters, signs made of letters, circled letters, small capitals, letters with bars, on a Latin font, a font of three masters, and a Japanese font): the full-width and half-width forms and the small kana are still to build live, on a font with kana that lacks them, and what the scope leaves is still to do (thicker strokes for its scaled glyphs, *‰*, the kanbun marks, the circled and half-width Hangul) ([GLYPH-COMPOSE.md](GLYPH-COMPOSE.md#next)).
- macOS: nothing has run on a Mac; what is Windows-only is in [INSTALL.md](INSTALL.md#macos).

## Done

The features the owner asked for, in the owner's order of interest:

1. **Dark mode** for FontLab 7's interface: [DARKMODE.md](DARKMODE.md).
2. Automated kerning: Auto Kerning in Latin, Cyrillic, Greek, kana, Armenian, Georgian, Devanagari, Hebrew, and Thaana, suggested kerning classes, and Kerning Check, [KERNING.md](KERNING.md); Auto Spacing, a sister script, [SPACING.md](SPACING.md).
3. Automated kerning pairs: Auto Kerning measures every pair of a script's letters, figures, and punctuation the font has, and *Common pairs* narrows them to the pairs common in text and kerned in fonts ([KERNING.md](KERNING.md#using-it)).
4. Automated diacritic variants: Glyph Compose, [GLYPH-COMPOSE.md](GLYPH-COMPOSE.md).
5. Automated discretionary and ligature feature code: Feature Code, with alternates that take turns and the features of a font's forms, [FEATURE-CODE.md](FEATURE-CODE.md).
6. A font check (language coverage, vertical metrics, masters): Font Check, [FONT-CHECK.md](FONT-CHECK.md).

What already exists for each, and what FreeLab would build: [FEATURE-SURVEY.md](FEATURE-SURVEY.md).

Reads and writes through an AI app belong to FreeLab MCP, the separate `freelab-mcp` repository, and are on its roadmap.
