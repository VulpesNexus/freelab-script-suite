# Roadmap

Nothing is outstanding, and nothing else is planned. Every feature the owner asked for is done (below), and every item this page carried was closed on 2026-11-27, either done or recorded as a known limit with its reason. How each tool came to work as it does is in [HISTORY.md](HISTORY.md).

## Done

The features the owner asked for, in the owner's order of interest:

1. **Dark mode** for FontLab 7's interface: [DARKMODE.md](DARKMODE.md).
2. Automated kerning: Auto Kerning in Latin, Cyrillic, Greek, kana, Armenian, Georgian, Devanagari, Hebrew, and Thaana, suggested kerning classes, and Kerning Check, [KERNING.md](KERNING.md); Auto Spacing, a sister script, [SPACING.md](SPACING.md).
3. Automated kerning pairs: Auto Kerning measures every pair of a script's letters, figures, and punctuation the font has, and *Common pairs* narrows them to the pairs common in text and kerned in fonts ([KERNING.md](KERNING.md#using-it)).
4. Automated diacritic variants: Glyph Compose, [GLYPH-COMPOSE.md](GLYPH-COMPOSE.md).
5. Automated discretionary and ligature feature code: Feature Code, with alternates that take turns and the features of a font's forms, [FEATURE-CODE.md](FEATURE-CODE.md).
6. A font check (language coverage, vertical metrics, masters): Font Check, [FONT-CHECK.md](FONT-CHECK.md).

Around them: Font Builder, Feature Check, Font Compare, Family Audit, Proof, Quick Overlay, CJK Spacing, CJK Vertical, and tab docking ([README](../README.md)). What already existed for each feature, and what FreeLab would build: [FEATURE-SURVEY.md](FEATURE-SURVEY.md).

## Closed on 2026-11-27

- Dark mode's display defects: every dialog FontLab's menus open was looked at, and every defect the owner's reviews found is fixed and was seen live ([HISTORY.md](HISTORY.md)), but the few recorded below. The tab titles keep ClearType, the owner's choice (image 182).
- Every FontLab call of Family Audit and Font Compare is proven live; Font Check's vertical metrics reach an exported font; Glyph Compose's whole next scope is built.
- Codex's review of everything changed since 2026-11-19 (24 findings), and the documentation checked against the code and data.

## Known limits

Recorded where they belong, not planned:

- Dark mode's remaining cost, *Overlay Fonts*' own slowness on a large font, and Matchmaker's dotted line not seen again: [DARKMODE.md](DARKMODE.md#known-limits).
- macOS: FreeLab is for Windows ([INSTALL.md](INSTALL.md#macos)).
- Glyph Compose leaves the strokes of scaled superscripts, subscripts, and other scaled glyphs as scaled, since no one rule fits the corpus ([GLYPH-COMPOSE.md](GLYPH-COMPOSE.md#what-it-leaves-and-why)).

Reads and writes through an AI app belong to FreeLab MCP, the separate `freelab-mcp` repository.
