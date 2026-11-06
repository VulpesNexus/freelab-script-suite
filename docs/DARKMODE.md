# Dark mode

FontLab 7 has no theme to switch: it colors its interface in several independent ways, and *darkmode/freelab_dark_mode.py* handles each. Everything below was found live in FontLab 7.2.0 (Qt 5.14.2) on 2026-11-06, through the FreeLab listener.

## How FontLab 7 colors itself

- **The application palette and style.** Qt's default Windows style and palette. Dark mode switches to the Fusion style (compiled into *Qt5Widgets.dll*) with a dark palette. FontLab's application stylesheet is empty.
- **Widget stylesheets.** About a thousand of FontLab's 4,700 widgets carry their own stylesheet (490 different ones) with fixed light colors, such as `background:#edeeef` or `color:black`. A widget's own stylesheet beats the palette, so these stay light under a dark palette, and the palettes Qt derives from them are light too.
- **Fixed colors in FontLab's code.** Some widgets paint light colors no setting reaches: the Sketchboard and glyph-window canvases (black outlines and fills on the workspace color), the font window's cells and the *Font Map* (black glyphs on the font-cell color), the rulers, the tool bar, tab strips, search-field frames, the *Preview* panel, list headers, the *History* list's selected row, the feature editor's margin, panel title strips, the background of every panel (`YPanel`, #edeeef, normally hidden under its content), and the 1-px frames the dock draws between panels (`YDock`, #cacbcc).
- **Canvas preferences.** The workspace, font-cell, metrics, and mask colors are FontLab preferences (`fontlab.flPreferences()`, stored under *HKCU\Software\Fontlab\fontlab7*). They set backgrounds, but outlines stay black.
- **The window frame.** The title bar is drawn by Windows.

## What dark mode does

1. **Palette and style:** Fusion and a dark palette. Nothing dark mode draws reaches L = 0.9 (HLS lightness): mapped colors stop at 0.86, the palette at 0.88.
2. **Stylesheets:** every literal color in a widget's own stylesheet is mapped: its lightness L becomes 0.12 + (1 − L) × 0.74, with hue, saturation, and alpha kept. White becomes #1f1f1f, black #dbdbdb, and a red mark stays red. Color swatches are skipped.
3. **Islands**, for widgets that paint fixed light colors with dark text or lines on them: the widget gets FontLab's original light palette, and its own stylesheet is prefixed with its ancestors' original stylesheets (a widget's own stylesheet beats inherited rules whatever their specificity), so everything inside it looks exactly as in light mode. A graphics effect then maps the lightness of every pixel it draws. On the canvas, black outlines turn light, colored nodes and marks keep their hue, and the workspace color preference is set to #f0f0f0 for the duration, which maps to a dark gray.
4. **Selective areas**, for light backgrounds without text: an effect maps only pixels at L ≥ 0.9. Dark mode itself never draws that light, so this is safe on any container, and applying it twice changes nothing.
5. **Keyed frames:** the dock's own light colors are collected from one render of it alone, and an effect maps only pixels of exactly those colors. A lightness threshold would also have caught dark mode's own light text.
6. **Fills:** a panel's tab widget fills itself with the dark palette color, covering the panel's #edeeef background before any content draws over it, under translucent labels too.
7. **Panel titles:** an effect maps the strip between a panel's top and its first child.
8. **Icons and label images** are mapped the same way: icons once per icon (cached), label images once each, and nothing twice. A button inside an island that follows a menu action shows the action's original icon, since the island maps it.
9. **Title bars:** `DwmSetWindowAttribute` with `DWMWA_USE_IMMERSIVE_DARK_MODE` on each of FontLab's windows.

Known island classes are listed in the script. Any other visible widget is rendered once without its children: if a quarter of it is near-white, it becomes an island when it paints mostly itself (its visible children cover less than half of it, as a canvas with rulers does) with dark marks on it, else a selective area. A widget's unprocessed ancestors are always processed first, since a child of a still-light parent looks light itself.

## The native helper

Mapping pixels in Python 2.7 would take seconds per frame. *darkmode/native/freelab_pixels.c* does it in C: the full and selective mapping, the keyed mapping, the pixel counts for detection, and the color collection for keyed frames. It uses no C runtime and imports nothing, and FontLab's Python calls it through `ctypes` on `QImage.bits()`. *tools/build-native.ps1* builds it with clang or MSVC into *%LOCALAPPDATA%\FreeLab\bin\freelab_pixels-v<version>.dll*. The name carries the version because FontLab keeps a loaded DLL locked. Without it, islands fall back to plain color inversion, which flips hues, and the selective and keyed effects do nothing.

## Cost

- Switching on blocks FontLab for about 1.5 to 3 seconds: the style change alone repolishes every widget. The widgets are then processed in 20 ms slices, about 2.5 seconds in all.
- New windows: when keyboard focus moves (Qt's `focusChanged`, which fires as a window or tab opens), dark mode processes the visible new widgets at once, for up to 150 ms, so they barely show light. A sweep every 0.75 seconds catches the rest, and every 30 seconds it revisits every widget, catching stylesheets FontLab replaced.
- Any widget with an effect is drawn offscreen first. A full canvas render took 40 ms without dark mode and 55 to 100 ms with it (the mapping itself 8 to 16 ms). If the canvas feels slow, set `"canvas": false` in *%LOCALAPPDATA%\FreeLab\darkmode.json* and switch dark mode off and on again: the canvas then keeps FontLab's own colors, and only its rulers are mapped.

## Switching off

Everything is recorded before it changes, and switching off puts it back without a restart: style, palette, stylesheets (unless FontLab replaced one meanwhile), palettes, icons, effects, fills, title bars, and the workspace color (unless it was changed meanwhile). The saved workspace color is kept in *darkmode.json* until then. Graphics effects FontLab sets itself are never replaced. `tools/install-fontlab.ps1 -Uninstall` also puts the workspace color back, and asks for dark mode to be switched off first when FontLab is running.

## PythonQt traps met on the way

- Qt properties read as values: `widget.styleSheet`, `app.style().objectName`, and `widget.palette` are not callable.
- `QPalette` has no `PlaceholderText` name (the wrappers predate Qt 5.12), but the role works by number (20).
- `QWidget.winId()` returns nothing usable; window handles come from `EnumWindows` instead.
- `findChildren(QWidget)` returns an empty list.
- A Python subclass of a Qt class, such as a `QGraphicsEffect`, is deleted as soon as Python holds no reference to it, even after `setGraphicsEffect` gave it to a widget.
- `QGraphicsEffect.sourcePixmap` takes a `QPoint` to fill with the drawing offset, which is not zero for a widget inside another effect's widget.
- Under any widget stylesheet, `app.style()` is Qt's stylesheet wrapper, whose name is empty. Switching off therefore restores the `windowsvista` style by name.
- Paint events are not delivered while a listener request runs, so `widget.grab()` is the way to see the current look.
