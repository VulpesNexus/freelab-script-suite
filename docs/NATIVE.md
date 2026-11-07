# Native dark mode (experimental)

A second way to make FontLab 7 dark, to be offered beside the script version: if one misbehaves on someone's machine, they can try the other.

## How it works

The script version maps the pixels widgets have drawn ([DARKMODE.md](DARKMODE.md)). The native version changes the colors before anything is drawn. *darkmode/native/freelab_hooks.c* points the entries of *FontLab 7.exe*'s import table for Qt's color-carrying painting calls at wrappers that map the color, then call Qt, which then draws dark itself, text smoothing included.

- **The surface is small.** All of FontLab's own painting code is in *FontLab 7.exe*; its other modules are PythonQt and QScintilla. It paints through 16 color-carrying entry points of the stock Qt 5.14.2 *Qt5Gui.dll*: `QPainter::fillRect` (with a color, a global color, or a brush), `setPen` (a color or a pen), `setBrush`, `fillPath`, `setBackground`, `QPixmap::fill`, `QImage::fill`, and `QGradient::setColorAt`.
- **Colors are mapped where they are used, never where they are made.** FontLab builds most pens and brushes once and keeps them: mapped at construction, those made before the hooks stayed light, and those made after would be mapped a second time when used. A `QColor` FontLab makes may also be a mark color it saves in a font. A pen or brush is mapped on a temporary copy, and FontLab's own object never changes.
- **Only FontLab's import table changes.** Qt's code is untouched; removing the hooks writes the original addresses back, and a pass-through switch maps nothing while the hooks stay in place.
- **The same color rule as the script:** lightness inverted in OKLab, grays to dark mode's grays, and clearly colored colors of middle lightness or lighter (selection blues, marks, nodes) kept.
- The library has no C runtime and no imports; FontLab's Python passes it the module bases and `VirtualProtect`. It needs Qt 5.14.2's MSVC x64 exports, checked at start: with another Qt build, nothing is hooked.

## Status (2026-11-07)

- *tests/hooks_selftest.py* calls every wrapper on real Qt objects in a separate process with FontLab's own *Qt5Gui.dll*: all 16 map as they should, and the pens and brushes passed in stay untouched.
- Live in FontLab 7.2.0, with the script version off: all 16 imports hooked and removed again without trouble; one full window repaint went through about 3,600 hooked calls, about half of them changing a color. With mapping on, the font window's cell chart draws natively dark (cell backgrounds, glyph names, separators, the selected cell). With mapping off, the window is pixel for pixel FontLab's own.
- Not covered yet: the glyphs in the cells, which FontLab most likely draws from images it rendered and cached before the hooks; anything FontLab paints from cached images; Qt's own widgets, which the native version still darkens the script's way (palette, stylesheets, title bars), only without pixel effects.

## Next

1. Find how cell glyphs, the glyph canvas, and other cached images are drawn, and make FontLab render them anew when the hooks go in (or map those images once).
2. Tell content from interface: the glyph canvas and cells keep their colors under the script version's content rule; the painter's device says which widget is being painted.
3. A loader in the script: palette, stylesheets, title bars, and editors as now, the hooks instead of effects, and a setting to choose between the two versions.
4. Exports and printing: painting into images FontLab saves (font previews, glyph images) and onto printers must not be mapped.

## The two versions

| | Script version | Native version |
|---|---|---|
| **How** | Maps the pixels widgets drew, after the fact | Maps the colors FontLab hands to Qt, before drawing |
| **Text** | ClearType text on light, remapped: fringes need rules (defringe, subpixel, syntax) | Qt draws light text on dark itself: smoothing as in any dark application |
| **Speed** | Every effect widget is drawn offscreen and mapped: tens of milliseconds per large repaint | A color mapped per call: about the cost of drawing |
| **Partial repaints** | A small repaint can map differently from a full one (the reason for several fixes) | Nothing to differ: each color is mapped the same way every time |
| **Reach** | Anything drawn, cached images included | Only colors FontLab passes to Qt; cached images need a fresh render |
| **Risk** | Python and Qt effects only: a mistake looks wrong | Native code inside FontLab: a mistake in a wrapper can crash FontLab |
| **Compatibility** | Any FontLab 7 build whose widgets it knows | Only Qt 5.14.2 (MSVC x64) exports; checked at start, off otherwise |
| **Maturity** | Tuned on most of FontLab's surfaces | Experimental |
