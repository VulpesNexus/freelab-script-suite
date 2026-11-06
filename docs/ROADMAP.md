# Roadmap

## Next

1. Dark mode in the windows not seen yet: the font window, glyph windows, *Preferences*, *Font Info*, and other dialogs. Unknown widgets that paint light are detected, but each window still needs a look.
2. On a disposable test font, prove each read in [FONTLAB7-API.md](FONTLAB7-API.md) and raise its row to **live**.

## Then

- **Writes**, each one verified by a re-read before it is reported as done: width and sidebearings, Unicode values, creating and deleting glyphs, drawing contours. Check the FontLab 8 traps listed in [FONTLAB7-API.md](FONTLAB7-API.md) first.
- **Kerning reads** of explicit pairs, with class resolution done by FontLab.

## Features the owner asked for

In the owner's order of interest:

1. **Dark mode** for FontLab 7's interface (first): running, [DARKMODE.md](DARKMODE.md).
2. Automated kerning.
3. Automated kerning pairs.
4. Automated diacritic variants.
5. Automated discretionary and ligature feature code.

What already exists for each, and what FreeLab would build: [FEATURE-SURVEY.md](FEATURE-SURVEY.md).
