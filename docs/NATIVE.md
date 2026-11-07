# The native engine

Dark mode has two engines, chosen in *Scripts > FreeLab > Dark Mode Settings > Engine*. Both darken Qt's own widgets the same way: a dark palette, Fusion, recolored stylesheets, mapped icons, dark title bars, and editors colored natively ([DARKMODE.md](DARKMODE.md)). They differ in what FontLab paints itself: the glyph canvas, font cells, previews, panel titles, and dock frames.

- **Script:** each of those widgets is drawn offscreen through a graphics effect, and the pixels it drew are mapped.
- **Native:** the colors FontLab hands to Qt are mapped before anything is drawn, and Qt draws dark itself.

If the native engine cannot start (its library is missing, or Qt is another build), the script engine runs and the reason shows in `status()["errors"]`.

## How it is applied to a FontLab install

Nothing in FontLab's own folder changes, on disk or in the registry, beyond what the script engine already does (the workspace color, put back on switching off). *tools/install-fontlab.ps1* does what it did, and one thing more:

1. It copies *freelab_dark_mode.py* and *freelab_dark_mode_settings.py* into FontLab's *Scripts\FreeLab* folder, and adds the FreeLab tools block to FontLab's *startupScript.py*.
2. It builds two libraries into *%LOCALAPPDATA%\FreeLab\bin*: the pixel helper (*freelab_pixels-v103.dll*) and the native engine (*freelab_hooks-v7-103.dll*), from the C sources in *darkmode/native*, with clang or MSVC.

At each FontLab launch, the startup block runs dark mode, which reads *%LOCALAPPDATA%\FreeLab\darkmode.json*. With the native engine chosen, it loads *freelab_hooks* into FontLab's process with `ctypes` and points about two dozen entries of the in-memory import table of *FontLab 7.exe* at the library's wrappers. That change lasts only while FontLab runs: switching dark mode off writes the original addresses back, and quitting FontLab ends it. *-Uninstall* removes both libraries, the scripts, the startup block, and the settings.

## How it works

*darkmode/native/freelab_hooks.c* hooks FontLab's imports from the stock Qt 5.14.2 *Qt5Gui.dll*. All of FontLab's own painting code is in *FontLab 7.exe*, and every Qt function the library uses is looked up by its decorated name first: with any missing, nothing is hooked.

- **Colors at the point of use.** `QPainter::setPen` (a color or a pen), `setBrush`, `fillRect` (a color, a global color, or a brush), `fillPath`, `setBackground`, and `QPixmap::fill` map their color, on a temporary copy of the pen or brush; FontLab's own objects never change. Mapping where colors are made would miss the pens and brushes FontLab made before and keeps, and could change a mark color it saves in a font.
- **Only on screen.** Colors are mapped only on a painter whose device is a widget or a pixmap (`QPaintDevice::devType`, the second entry of its table of virtual functions). Painting into an image stays light: an image FontLab exports is never dark.
- **Images and pixmaps, once.** FontLab draws its glyph cells from images it renders and keeps (premultiplied ARGB32, about 600 per font window). Each is drawn as a mapped copy made once and kept under its `cacheKey`, which Qt changes when its pixels change; smoothing toward transparency survives. Pixmaps FontLab painted before the hooks, or loaded, get the same; those it paints while the hooks are in are dark already (the painters it begins on pixmaps are noted).
- **A light palette for FontLab's code.** Under the dark palette, a color FontLab reads from a palette is already dark, and mapped again it would turn light. Its palette reads (`QPalette::color`, `QPalette::brush`) answer with the light palette's color wherever the palette holds the dark palette's color for that slot.
- **The color rule** is the script's: lightness inverted in OKLab, tints kept (a selected cell's pale blue); clearly colored colors of middle lightness or lighter (selection blues, marks, nodes) kept. White pens stay white: FontLab draws white lines and text only where they stand out, on a color or on dark.
- **Left as FontLab draws them:** color swatches and pickers, ClearType previews (TrueType Hinting's, which keep the script engine's subpixel mapping), and in *Mixed*, the canvases, cells, and previews. Dark mode passes their addresses (from Qt's own description of each widget), and a painter on one of them maps nothing.
- **A guard against a crash at start.** *darkmode.json* holds `native_pending` from just before the hooks go in until the engine has run 15 seconds. Found at the next start, it means FontLab closed while the engine was starting: the script engine runs from then on, and the *Output* panel says why.

The library has no C runtime and no imports; dark mode passes it Qt5Gui's base and `VirtualProtect`. *tests/hooks_selftest.py* calls every wrapper on real Qt objects with FontLab's own *Qt5Gui.dll*, in a separate process, so a fault ends only the test.

## Status (2026-11-07, hooks version 7)

Seen live in FontLab 7.2.0:

- The font window (cells, glyphs, names, the selected cell, the bottom bar), the glyph window (canvas, outline, nodes, rulers, the glyph strip), the panels (Elements, Transform, TrueType Hinting, Kerning, History, Output, Source), and *Mixed* match the script engine's look. A full main-window repaint took 37 to 100 ms, against 270 ms with the script engine.
- Switching on and off twice in a row, and switching between engines, left nothing behind and noted no error.

Not seen yet: dialogs (*Font Info*, *Preferences*, *Export*), the metrics and kerning windows, and working in the glyph window (selections, dragging, previews of tools). In *Mixed*, the font cells' name strips stay dark where the script engine leaves them light.

## The two engines

| | Script engine | Native engine |
|---|---|---|
| **How** | Maps the pixels FontLab's widgets drew, after the fact | Maps the colors FontLab hands to Qt, before drawing |
| **Text** | ClearType text drawn for light, remapped: fringes need rules (defringe, subpixel, syntax) | Qt draws light text on dark itself: smoothing as in any dark application |
| **Speed** | Every effect widget is drawn offscreen and mapped: about 270 ms for a full main window | A color mapped per call, an image once: about 40 to 100 ms |
| **Partial repaints** | A small repaint can map differently from a full one (the reason for several fixes) | Each color is mapped the same way every time |
| **Reach** | Anything drawn, cached images included | Colors FontLab passes to Qt, and the images and pixmaps it draws |
| **Risk** | Python and Qt effects only: a mistake looks wrong | Native code inside FontLab: a mistake in a wrapper can crash FontLab (the start guard then falls back) |
| **Compatibility** | Any FontLab 7 build whose widgets it knows | Qt 5.14.2 (MSVC x64) only; checked at start, script engine otherwise |
| **Maturity** | Tuned on most of FontLab's surfaces | New; the same surfaces seen, dialogs not yet |
