# Roadmap

## Next

1. Dark mode's remaining display defects. Every dialog FontLab's menus open has been looked at (34 on 2026-11-24 with a static and a variable font open, the rest by the owner that day: *Create Instance*, *Place As Glyphs*, and *Compare Fonts* are dark; *Paste Special* and *Zoom* open no window of their own; *Adjust Stem Thickness* is not a FontLab 7 command). Of what the owner's review of that day found, these were reproduced in a fresh session and fixed ([HISTORY.md](HISTORY.md)): menus slow over a Font window with many cells selected, *Overlay Fonts*' sample text and color button, the *Actions* panel's small labels, the Glyph window's metrics table and the text typed in its fields. A second pass that day fixed *Replace Element*'s two buttons, the Font window's five view buttons, the white frame around the row last clicked in FontLab's lists, and *FontAudit*'s captions on the canvas. Later passes (2026-11-25) fixed pictures in glyphs (shown as they are), the names on anchors' gray pills, panel titles on narrow panels, the light glow of FontLab's cursors, colored lines on the canvas (smooth again), black previews in dark lists (*Generate Instance*'s "Ag"), *Overlay Fonts*' rows and the overlaid glyphs' counters in the Font window, the Fonts panel's letters on their discs, the metrics table's three buttons, and ClearType's colored edges in lists, text views, interface islands, the interface's own text, and FreeLab's windows (counted with *tools/find_fringes.py*: 14,404 pairs of opposite hues on the main window, 1,843 after, nearly all in *TrueType Hinting*'s preview, which shows ClearType's colors on purpose; Font Check's window, 31,385 then 283). Still open:
   - *TrueType Hinting*'s size numbers under its preview (blue on white: readable, but soft). The preview shows ClearType's colors on purpose, and what is on pure white is left as drawn.
   - A name on a pill where a guide crosses the pill: the letters beside the guide stay dark.
   - The Scoreboard's word is drawn for an instant only; not looked at closely.

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
