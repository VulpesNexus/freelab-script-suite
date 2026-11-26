# The native engine

The native engine is dark mode's default since 2026-11-26. It was retired on 2026-11-19 as a hybrid that added little to the pixel ("script") engine, then brought back when the glyph canvas proved the pixel engine's limit: FontLab draws dozens of kinds of marks there (anchors' pills, measurement boxes, live values while a tool works, colored lines over translucent template glyphs), each in several states and over each other, and the pixel engine recognizes each kind after the fact, so their combinations kept coming out wrong (the owner's reviews of November 25 and 26). The native engine maps the colors before anything is drawn, so no mark has to be recognized. The pixel engine stays: it runs wherever the hooks do not reach, and in their place when the native engine cannot start.

Dark mode has two engines, chosen in *Scripts > FreeLab > Dark Mode Settings > Engine*. They differ only on the islands: the surfaces FontLab paints itself in fixed light colors (the glyph canvas, font cells, previews, rulers, tab strips, search fields). Everything else is handled the same way by both: a dark palette, Fusion, recolored stylesheets, mapped icons, dark title bars, editors colored natively, and the other effects ([DARKMODE.md](DARKMODE.md)).

- **Script:** each island gets FontLab's light look, is drawn offscreen through a graphics effect, and the pixels it drew are mapped.
- **Native:** the colors FontLab hands to Qt while it paints an island are mapped before anything is drawn, and Qt draws dark itself. Lists whose rows Qt draws get the same, for their dark text.

If the native engine cannot start (its library is missing or another version, FontLab is not 64-bit, Qt is not version 5.14.2, a Qt function or FontLab import it hooks is missing, or an import table entry cannot be written), the script engine runs and the reason shows in `status()["errors"]`.

What the start checks is that list, and no more: Qt's own version (its `qVersion()`), and the MSVC-decorated names the library looks up. A Qt 5.14.2 built otherwise (another compiler, other build options) that still exports those names would pass, and the library's assumptions about Qt's object layout (where a widget's `QPaintDevice` part sits, for one) would then go unchecked. FontLab 7.2's own Qt is the build it was written and tested against.

## How it is applied to a FontLab install

Nothing in FontLab's own folder changes, on disk or in the registry, beyond what the script engine already does (the workspace color, put back on switching off). *tools/install-fontlab.ps1* does what it did, and one thing more:

1. It copies *freelab_dark_mode.py* and *freelab_dark_mode_settings.py* into FontLab's *Scripts\FreeLab* folder, and adds the FreeLab tools block to FontLab's *startupScript.py*.
2. It builds two libraries into *%LOCALAPPDATA%\FreeLab\bin*: the pixel helper (*freelab_pixels-v157.dll*) and the native engine (*freelab_hooks-v25-157.dll*, named after both versions), from the C sources in *darkmode/native*, with clang or MSVC. Superseded builds are removed (one still loaded by a running FontLab stays until FontLab quits).

At each FontLab launch, the startup block runs dark mode, which reads *%LOCALAPPDATA%\FreeLab\darkmode.json*. With the native engine chosen, it loads *freelab_hooks* into FontLab's process with `ctypes` and points entries of the in-memory import tables at the library's wrappers: about thirty in *FontLab 7.exe*, the painting ones in Qt's SVG library (*Qt5Svg.dll*, through which FontLab draws some artwork), and two pen calls in *Qt5Widgets.dll* (for lists' rows). That change lasts only while FontLab runs: switching dark mode off writes the original addresses back, and quitting FontLab ends it. *-Uninstall* removes both libraries, the scripts, the startup block, and the settings.

## How it works

*darkmode/native/freelab_hooks.c* hooks FontLab's imports from the stock Qt 5.14.2 *Qt5Gui.dll* (and `QWidget::palette` from *Qt5Widgets.dll*). Every Qt function the library uses is looked up by its decorated name first: with any missing, nothing is hooked.

- **Only the islands.** Dark mode finds the islands as the script engine does, and passes the native engine those FontLab paints itself (from Qt's own description of each widget). Within them, FontLab's own widget classes are hooked too (the labels over the glyph canvas are drawn by a widget of their own); Qt's widgets inside them (buttons, line edits, scroll bars) are processed as anywhere else. Islands Qt draws are left to the script engine's island: lists (their rows are Qt's) and the zigzag edge where a panel continues (drawn from its stylesheet).
- **Colors at the point of use.** `QPainter::setPen` (a color, a pen, or a style), `setBrush` (a brush or a style), `fillRect` (a color, a global color, or a brush), `fillPath`, and `setBackground` map their color on an island, on a temporary copy of the pen or brush; FontLab's own objects never change, so no mark color it saves in a font is touched. A style alone and an invalid color (`QColor()`, which FontLab passes for the Fonts panel's file names) are mapped as the black Qt paints them. Painting into an image or a pixmap stays light: an image FontLab exports is never dark.
- **What FontLab reads back is its own.** FontLab reads a painter's pen or brush back and makes the next color from it (a label's box from its text color); handed the mapped color, it had it mapped again. Each painter on an island notes what its pen and brush were mapped from, and `QPainter::pen()` and `brush()` hand FontLab a copy in its own color.
- **Images and pixmaps, once.** FontLab draws its glyph cells from images it renders and keeps (premultiplied ARGB32, about 600 per font window). Each image or pixmap it draws on an island is drawn as a mapped copy made once and kept under its `cacheKey`, which Qt changes when its pixels change; smoothing toward transparency survives. White artwork on transparency (all visible pixels near-white) is drawn as is.
- **A light palette while FontLab paints an island.** Under the dark palette, a color FontLab reads from a palette is already dark, and mapped it would turn light. Its palette reads answer with the light palette's color wherever the palette holds the dark palette's for that slot, from an island's own palette at any time (FontLab often reads before it begins painting), and from any palette while one of its painters on an island is active. Elsewhere (its cursors, other widgets, dialogs) it reads the dark palette, as under the script engine: answering light everywhere had given cursors white shadows and dark text in dialogs.
- **The color rule** is the script's: lightness inverted in OKLab, tints kept (a selected cell's pale blue); clearly colored colors of middle lightness or lighter (selection blues, marks, nodes) kept. Pure white pens stay white (FontLab draws white text on a selected cell's blue header); near-white ones and the palette's white are paper-colored lines, mapped. Dark text on a kept fill stays dark: while a painter's brush is light and clearly colored (the Fonts panel's pale blue style dot), a dark pen is left as it is, until the brush changes.
- **Lists, natively.** Qt draws list rows in colors FontLab puts in the list's data (the Metrics panel's widths and sidebearings, in black). On the viewports of lists whose delegates leave the drawing to Qt, dark pens (not the dark palette's own) are mapped light as they are set, in FontLab's code and in *Qt5Widgets*, with no effect. The script engine's ink effect maps those pixels afterward, and rows repainted while scrolling kept dark remnants. Lists whose delegates paint their rows (FontAudit's badges, the Elements tree) keep the ink effect.
- **Color fonts.** While the current font draws in color (shapes with colors of their own, as FontLab imports COLR, or SVG and bitmap pictures), its pictures are what the user gets, so they are drawn as the font has them: *Qt5Svg*'s color-carrying calls go to Qt unmapped (a color glyph's SVG is painted through them on the canvas), and an image that looks like a picture (at least a quarter of its visible pixels, and four or more, clearly colored, or light on transparency) is drawn unmapped. A color glyph is mostly its colors, while a black glyph or a gray icon with a colored accent or white highlights has a few percent of them; at 1%, those were drawn as in light mode, dark on the dark surface. Pixmaps (icons, the interface's artwork) are mapped whatever the font. Dark mode checks the current font when it changes (told apart by FontLab's own number for each open font, so a mono and a color version of one font with as many glyphs are two fonts) and at every full sweep: every glyph's color flag, then the shapes of 48 glyphs spread through the font, the answer kept until the font's glyph count changes. The flag is one for all of FontLab, set from the current font (see [DARKMODE.md](DARKMODE.md#known-limits)).
- **Left as FontLab draws them:** color swatches and pickers, ClearType previews (TrueType Hinting's keep the script engine's subpixel effect), and in *Mixed*, the canvases, cells, and previews.
- **A guard against a crash at start.** *darkmode.json* holds `native_pending` from just before the hooks go in until the engine has run 15 seconds. Found at the next start of FontLab (a mark this session set is its own), it means FontLab closed while the engine was starting: the script engine runs from then on, the *Output* panel says why, and no hooks stay in. Applying dark mode again while the hooks are in only brings the palette table up to date.
- **A diagnostic trace**, off unless asked for (`freelab_hooks_trace_on`, `freelab_hooks_trace`): each color FontLab hands to a painter on a widget, mapped or not, and each palette read. It found the read-back and the near-white lines above.

The library has no C runtime and no imports; dark mode passes it the Qt libraries' bases and `VirtualProtect`. *tests/hooks_selftest.py* calls every wrapper on real Qt objects with FontLab's own Qt libraries, in a separate process, so a fault ends only the test.

## Status (hooks version 20)

Seen live in FontLab 7.2.0 at hooks version 17 (2026-11-08), compared pixel by pixel with the script engine on the same main window (glyph window, font window, panels): the two differ only where the window was in another state (scrolled lists, focus), in a few antialiased pixels, in the glyph window's zoom buttons (lighter, easier to see natively) and two tool icons' tints, and in the Metrics panel, where the native engine leaves no dark remnants. Switching on takes as long with either engine. Version 18 keeps the cached images' and pixmaps' storage 8-byte aligned; version 19 adds the color-font rule above; version 20 hooks all or nothing (a slot that cannot be written puts back the ones written before it, and the script engine runs) and spares pictures only in images, at a quarter of their pixels.

Fixed since the owner's tests of version 10, and waiting for the owner's look: the cursor's shadow and fringe (cursors read the dark palette again; FontLab makes them when it starts or when the tool changes), the dialogs' text (*Export Profiles*, *Preferences*, *Font Info*: dialogs are the script engine's again), FontAudit's badges, the black parts of list icons, the FontLab logo (a label image: white artwork is kept by either engine), the Metrics panel's stale values while scrolling, the glyph canvas's labels (the name, width, and sidebearings), and the white line under some tab strips.

## The two engines

Measured on 2026-11-26 in one FontLab session on the owner's desktop (FontLab 7.2.0.7649, the main window with its tabs and panels as the owner had them, the same fonts open), switching between the engines and light mode with nothing else changed. Times are wall-clock, from inside FontLab; each figure is a range or the median of several runs.

| | Light mode (dark mode off) | Native engine | Pixel ("script") engine |
|---|---|---|---|
| **Switching tabs** (median of 8) | 276 ms | 677 to 832 ms (two runs) | 1,319 ms |
| **Repainting the main window**, maps cleared first | 30 to 118 ms | 135 to 194 ms | 236 to 291 ms |
| **The same, maps kept** | 29 to 112 ms | 83 to 114 ms | 169 to 191 ms |
| **Switching dark mode on** (until every widget is looked at) | | 4.4 s, done after 23 s | 12.8 s, done after 36 s |
| **Memory** (working set, private) | 532 MB, 701 MB | 549 to 585 MB, 728 to 751 MB | 605 MB, 771 MB |

| | Native engine | Pixel engine |
|---|---|---|
| **How** | Maps the colors FontLab hands to Qt while it paints its own surfaces, before anything is drawn | Draws each surface in FontLab's light look and maps the pixels after |
| **Correctness** | Nothing to recognize: every mark FontLab draws (pills, measurement boxes, a tool's live values, lines over template glyphs) comes out dark as drawn, and Qt draws light text on dark itself, with grayscale smoothing (ClearType light on dark had deep colored edges that broke the letters, so the hooked surfaces and native-ink lists ask for grayscale, as dark applications draw their text) | Each kind of mark is recognized after the fact by a rule of its own; their states and overlaps keep producing cases no rule covers (the canvas reviews of November 25 and 26) |
| **Partial repaints** | Each color is mapped the same way every time | A small repaint can map differently from a full one (lists kept dark remnants while scrolling) |
| **Speed** | About 1.7 times the cost of light mode on repaints | About 3 times |
| **Stability** | Native code patches FontLab's import table in memory: a fault in a wrapper ends FontLab, and the start guard then falls back to the pixel engine for later sessions. The self-test calls all 31 wrappers on FontLab's own Qt; no crash in this session | Python and Qt effects only. This month's crashes came from effects and PythonQt (wrappers freed twice, an effect's source asked for outside its drawing, nested drawing while a color was dragged), each fixed |
| **Compatibility** | Qt 5.14.2 (64-bit, FontLab 7.2's) only; checked at start, and the pixel engine runs otherwise | Any FontLab 7 build whose widgets it knows |
| **Screenshots from inside FontLab** | Qt's own grabs (a widget's picture, FreeLab MCP's) render FontLab's surfaces light: the hooks map only painting on screen. The screen itself is dark | As on screen |

### What the native engine leaves to the pixel engine

The native engine covers what FontLab paints itself, 96 surfaces in the session measured (canvases, font cells, rulers, previews, the tool bar, tab strips, the Fonts panel), and the rows of 53 lists whose drawing Qt does from FontLab's colors. These stay the pixel engine's under either engine, so a defect there shows under both (the owner's image 147, *Overlay Fonts*' samples):

- Lists whose rows FontLab's own delegates paint (*Overlay Fonts*' samples, FontAudit's badges, the Elements tree), list headers, the zigzag edge where a panel continues, and the History list.
- Dialogs, and the interface's fields, selectors, and text boxes (some 600 ink and defringe effects in the session measured): the same under both engines.
- TrueType Hinting's preview (ClearType on purpose: the subpixel effect).
- Cursors: FontLab paints them into pictures, which the hooks leave light; dark mode's replacements (made by the pixel engine's rules) serve both.
- A color font's pictures are drawn as they are only while that font is the current one (one flag for all of FontLab).

### When one engine takes the other's place

- The native engine cannot start (its library missing, another Qt): the pixel engine runs, and the reason is in `status()["errors"]`.
- FontLab closed while the native engine was starting: the next launch, and every one after, runs the pixel engine, and the *Output* panel says so, until *Native* is chosen again in *Dark Mode Settings*.
- *Mixed* leaves the canvases, cells, and previews light under either engine.
