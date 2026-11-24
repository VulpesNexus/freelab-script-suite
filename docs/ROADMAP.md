# Roadmap

## Next

1. Dark mode in *Font > Add Glyphs*: its list of categories keeps a light selected row whose text cannot be read, and the edges of its other rows' text are rough. Its delegate takes the text's color from the application's palette and paints the selection in a fixed light color, so neither of dark mode's two treatments fits it (as ink the text is roughened; mapped whole, the text turns as dark as the list). Of the dialogs FontLab's menus open (file pickers aside, which Windows draws), 31 were opened and looked at on 2026-11-24, with one font open: 30 are dark, *Open Installed Fonts* once its list was mapped whole. Not looked at yet: the dialogs that need a state the survey did not set up (*Create Instance*, *Generate Instance*, *Compare Fonts*, *List Related Glyphs*, *Adjust Stem Thickness*, *Replace Element Reference*, *Zoom*, *Autotrace*), and *New Glyph*, *Paste Special*, and *Place As Glyphs*, which showed no dialog there.

## Open work the tools' pages record

- The few FontLab calls still not proven live, each listed with how to check it (most were proven on 2026-11-24, Family Audit's *Assemble as masters* run end to end among them): [Family Audit](FAMILY-AUDIT.md#fontlab-calls-proven-live-and-not-yet), [Font Compare](FONT-COMPARE.md#fontlab-calls-not-yet-proven-live), and [Font Check](FONT-CHECK.md#fontlab-calls-not-yet-proven-live).
- Glyph Compose's next scope, built on 2026-11-24, with two of its kinds run live that day (*™* as *T* and *M* at 49%, *Ħ* as *H* with a bar drawn across it, on a Latin font): one build of each other kind on a Latin font and on a font with kana, and what it leaves (thicker strokes for its scaled glyphs, *‰*, the kanbun marks, the circled and half-width Hangul) ([GLYPH-COMPOSE.md](GLYPH-COMPOSE.md#next)).
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
