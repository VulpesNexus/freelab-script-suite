# Quick Overlay

*Scripts > FreeLab > Quick Overlay* opens FontLab's *Overlay Fonts* on a new font that holds only the glyphs to compare, with the family's fonts overlaid on it.

## Why

At each change in *Overlay Fonts* (a color, the opacity, an offset), FontLab works again on every glyph of the font whose window the dialog was opened on, in a time that grows about as the square of its glyph count. The fonts overlaid on it barely count. Measured on 2026-11-25, with dark mode off, one color click took:

| Font the dialog is opened on | Glyphs | Fonts overlaid | One color click |
|---|---|---|---|
| Sarabun Regular | 777 | itself and its bold | 42 ms |
| A copy of FreeLang Essential | 1,374 | itself | 320 ms |
| The same copy | 1,374 | itself and two styles of 11,697 glyphs | 344 ms |
| FreeLang Essential | 11,697 | itself | 14.5 s |

A drag on the color field asks for one change per mouse move, so on a large font FontLab stops answering, and a long drag can crash it (a stack overflow, seen with dark mode on and off).

## Using it

1. Show the font to compare (its Font window or a Glyph window).
2. Choose *Scripts > FreeLab > Quick Overlay* and type the glyphs to compare: characters, or glyph names after a slash (`AaGg /a.alt /Aacute`); `//` stands for the slash itself. *And the glyphs flagged* adds every glyph of one flag color: it lists the colors the font's glyphs are flagged with, each with its count (*Red (12 glyphs)*). Either can be left empty. What was typed and chosen last is offered next time.
3. *Overlay* makes a new font named *Family Quick Overlay* with those glyphs from the current master, and the glyphs their components draw, copied as they are (outlines, components, anchors, advance widths, code points, and the master's line metrics). Its window opens, then *Overlay Fonts* on it, and *Add Family Members* is pressed: every open font of the family is overlaid.

Each change then takes a fraction of a second. The new font is not saved: close it without saving once done. A glyph the font lacks is named in FontLab's *Output* panel, as is anything FontLab refused to copy.

## Limits

- FontLab gives a script no way to read the glyphs selected in a Font window, so the glyphs are typed, or flagged first (selected, then given a color with the flag colors at the top of the Font window) and chosen by their flag.
- The time a change takes grows with the new font's glyphs: a flag on a thousand glyphs makes a slower overlay than a few dozen.
- *Add Family Members* adds every open font of the family, earlier *Quick Overlay* fonts among them: close those first to keep the list short.
- The copy is of the current master only, without kerning or feature code (*Overlay Fonts* shows neither).
