# Dark mode

FontLab 7 has no theme to switch: it colors its interface in several independent ways, and *darkmode/freelab_dark_mode.py* handles each. Everything below was found live in FontLab 7.2.0 (Qt 5.14.2) on 2026-11-06, through the FreeLab listener.

## How FontLab 7 colors itself

- **The application palette and style.** Qt's default Windows style and palette. Dark mode switches to the Fusion style (compiled into *Qt5Widgets.dll*) with a dark palette. FontLab's application stylesheet is empty.
- **Widget stylesheets.** About a thousand of FontLab's 4,700 widgets carry their own stylesheet (490 different ones) with fixed light colors, such as `background:#edeeef` or `color:black`. A widget's own stylesheet beats the palette, so these stay light under a dark palette, and the palettes Qt derives from them are light too.
- **Fixed colors in FontLab's code.** Some widgets paint light colors no setting reaches: the Sketchboard and glyph-window canvases (black outlines and fills on the workspace color), the font window's cells and the *Font Map* (black glyphs on the font-cell color), the rulers, the tool bar, tab strips, search-field frames, the *Preview* panel, list headers, the *History* list's selected row, the feature editor's margin, panel title strips, the background of every panel (`YPanel`, #edeeef, normally hidden under its content), and the 1-px frames the dock draws between panels (`YDock`, #cacbcc).
- **Editors.** The *Source* and *Scripting* editors (QScintilla) paint black text and a white margin on a paper that is already dark.
- **Canvas preferences.** The workspace, font-cell, metrics, and mask colors are FontLab preferences (`fontlab.flPreferences()`, stored under *HKCU\Software\Fontlab\fontlab7*). They set backgrounds, but outlines stay black.
- **The window frame.** The title bar is drawn by Windows.

## What dark mode does

1. **Palette and style:** Fusion and a dark palette. Nothing dark mode draws reaches L = 0.9 (HLS lightness). Fonts are left as they are: asking Qt for grayscale text smoothing made GDI drop smoothing altogether at FontLab's small UI sizes.
2. **The color mapping**, used everywhere below, works in OKLab, where lightness follows what the eye sees and hues stay put: lightness is inverted between #1f1f1f (for white) and #dbdbdb (for black), hue is kept, and chroma is kept up to L 0.65 and muted above it, down to a quarter at white. Colors whose channels spread by 60 or less (out of 255) come out pure gray. So tinted whites and pastels turn gray (FontLab's #fffffa metrics background had turned khaki, and bluish whites navy, when HLS saturation was kept), and so do ClearType's colored text edges, which are drawn dark on light in mapped areas; dark-blue text becomes a readable blue, and red and green marks keep their color.
3. **Stylesheets:** every literal color in a widget's own stylesheet is mapped, according to what it is for: backgrounds and borders only when light, text only when dark. A bar that is dark in light mode stays dark, with its light text. Color swatches are skipped.
4. **Islands**, for widgets that paint fixed light colors with dark text or lines on them: the widget gets FontLab's original light palette, and its own stylesheet is prefixed with its ancestors' original stylesheets (a widget's own stylesheet beats inherited rules whatever their specificity), so everything inside it looks exactly as in light mode. A graphics effect then maps the lightness of every pixel it draws. On the canvas, black outlines turn light, colored nodes and marks keep their hue, and the workspace color preference is set to #f0f0f0 for the duration, which maps to a dark gray.
5. **Selective areas**, for light backgrounds without text: an effect maps only pixels at L ≥ 0.9. Dark mode itself never draws that light, so this is safe on any container, and applying it twice changes nothing.
6. **Editors and lists** (the viewports of QScintilla editors and of FontLab's item lists): only near-white (L ≥ 0.9) and near-black (L ≤ 0.06) pixels are mapped, so an editor's margin and black text change while its dark paper and syntax colors stay, and a list's white count badges turn dark. Mark-color buttons get a selective effect with a lower threshold (0.72) for their light-gray frame.
7. **Keyed frames:** the dock's own light colors are collected from one render of it alone, and an effect maps only pixels of exactly those colors. A lightness threshold would also have caught dark mode's own light text.
8. **Fills:** every tab widget fills itself with the dark palette color, covering the panel's #edeeef background before any content draws over it, under translucent labels too.
9. **Panel titles:** an effect maps the strip between a panel's top and its first child.
10. **Icons and label images** are mapped the same way: icons once per icon (cached), label images once each, and nothing twice. Color swatches (icons mostly made of clearly colored pixels, such as mark colors) and pictures larger than 64 px (such as the *About* artwork) are left as they are. A button inside an island that follows a menu action shows the action's original icon, since the island maps it.
11. **Title bars:** `DwmSetWindowAttribute` with `DWMWA_USE_IMMERSIVE_DARK_MODE`, once per window: each call makes Windows recompute the frame, and repeating it on a dialog still opening kept it relaying itself out until FontLab stopped responding.
12. **Restyles:** FontLab restyles some widgets while it works (fields while a glyph is edited, a button that turns green). Each sweep compares visible widgets' stylesheets with what dark mode set or noted, a first stylesheet included; a widget caught once is watched from then on (an event filter on `QEvent::StyleChange`) and darkened before it paints.

Known island classes are listed in the script. Any other visible widget is rendered once without its children: if a quarter of it is near-white, it becomes an island when it paints mostly itself (its visible children cover less than half of it, as a canvas with rulers does) with dark marks on it, else a selective area; a self-painted widget with a smaller light part (3% or more, such as a white margin) is a selective area too. A widget's unprocessed ancestors are always processed first, since a child of a still-light parent looks light itself, and a widget is looked at again whenever its size changes, since a panel may first be seen at a placeholder size while it opens.

## The native helper

Mapping pixels in Python 2.7 would take seconds per frame. *darkmode/native/freelab_pixels.c* does it in C: the full, selective, and editor mappings, the keyed mapping, the pixel counts for detection, and the color collection for keyed frames. It uses no C runtime and imports nothing, and FontLab's Python calls it through `ctypes` on `QImage.bits()`. *tools/build-native.ps1* builds it with clang or MSVC into *%LOCALAPPDATA%\FreeLab\bin\freelab_pixels-v<version>.dll*. The name carries the version because FontLab keeps a loaded DLL locked. Without it, islands fall back to plain color inversion, which flips hues, and the selective and keyed effects do nothing.

## Cost

- Switching on blocks FontLab for about 1.5 to 3 seconds: the style change alone repolishes every widget. The widgets are then processed in 20 ms slices, about 2.5 seconds in all.
- New windows: when keyboard focus moves (Qt's `focusChanged`, which fires as a window or tab opens), dark mode processes the visible new widgets at once, for up to 80 ms, so they barely show light. A sweep every 0.75 seconds catches the rest, and every 30 seconds it revisits every widget, catching stylesheets FontLab replaced.
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
- Python identity does not tell Qt objects apart: `graphicsEffect()` may return another wrapper for the same effect. FreeLab tags its effects with a Qt property instead; taking its own effect for a foreign one once dropped the last Python reference to an installed effect, and FontLab crashed in *PythonQt.dll* on the next repaint.
- A Python 2 module that is no longer referenced has its globals set to None, and FontLab may drop modules from `sys.modules`, as a reload does. Anything Qt still calls into (timers, event filters, effects) then fails with `'NoneType' object is not callable`. Dark mode keeps every version of itself it loaded referenced, and the listener keeps its module.
- `QObject` cannot be subclassed from Python here; an event filter subclasses `QTimer` instead.
- `flWorkspace.changed()` is not a getter: calling it marks the workspace as changed.
