# FontLab fixes

FreeLab mends or works around these defects of FontLab 7.2 itself, each found with dark mode off or in FontLab's light look too. Each line links to the page that has the details.

## Crashes

- **A quick drag on *Overlay Fonts*' color bar crashed FontLab**, on any font: the bar handles each mouse move while letting the event loop run, so moves nested until the stack ran out. FreeLab hands that window one move at a time, the latest, whether dark mode is on or off ([DARKMODE.md](DARKMODE.md)).
- **Opening some fonts crashes FontLab** (a `GPOS` single adjustment of format 2 with no values: Noto Sans JP's and KR's variable fonts, among others), losing the unsaved work in every open font. Family Audit's *Add files…* and Font Compare's *Open a font…* and installed fonts check each file first and offer a fixed copy. FontLab's own *File > Open Fonts* is not covered ([FAMILY-AUDIT.md](FAMILY-AUDIT.md#fonts-fontlab-72-crashes-on)).

## Speed

- ***Overlay Fonts* on a large font** takes seconds per change (14.5 s on 11,697 glyphs), growing about as the square of the glyph count of the font the dialog is opened on. *Quick Overlay* opens it on a small font holding only the glyphs to compare, with the family's fonts overlaid: a fraction of a second per change ([QUICK-OVERLAY.md](QUICK-OVERLAY.md)).

## Windows and tabs

- **A document tab dropped anywhere becomes a window of its own**, even on the tab bar it came from, and only *Window > Docking > Merge Window* brings it back. Tab docking puts a tab released on or near the bar back in the main window, at the place shown, so tabs also reorder by dragging; it can also keep tabs from being undocked at all ([WINDOWS.md](WINDOWS.md#tab-docking)).

## Display

- **The slant tool's icon jumps up a pixel as the tool is checked**: FontLab's picture for the checked state is drawn a pixel higher than the unchecked one. FreeLab gives the button the same icon with the two pictures lined up, whether dark mode is on or off ([DARKMODE.md](DARKMODE.md)).

## Where they live

The *Overlay Fonts* guard and the slant icon are in dark mode's file (*darkmode/freelab_dark_mode.py*), which FreeLab's startup block runs at every launch, so they work with dark mode off; removing dark mode's file removes them. Tab docking is *windows/freelab_tabs.py*, also started at launch. The crash check and *Quick Overlay* act only when their tools are used.
