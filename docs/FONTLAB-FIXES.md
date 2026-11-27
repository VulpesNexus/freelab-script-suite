# FontLab fixes

FreeLab mends or works around these defects of FontLab 7.2 itself, each found with dark mode off or in FontLab's light look too. Each line links to the page that has the details.

## Crashes

- **A quick drag on *Overlay Fonts*' color bar crashed FontLab**, on any font: the bar handles each mouse move while letting the event loop run, so moves nested until the stack ran out. FreeLab hands that window one move at a time, the latest, whether dark mode is on or off ([DARKMODE.md](DARKMODE.md)).
- **Opening some fonts crashes FontLab** (a `GPOS` single adjustment with no values: Noto Sans JP's and KR's variable fonts, among others), losing the unsaved work in every open font. Family Audit's *Add files…* and Font Compare's *Open a font…* and installed fonts check each file first and offer a fixed copy. FontLab's own *File > Open Fonts* is not covered ([FAMILY-AUDIT.md](FAMILY-AUDIT.md#fonts-fontlab-72-crashes-on)).

## Speed

- ***Overlay Fonts* on a large font** takes seconds per change (14.5 s on 11,697 glyphs), growing about as the square of the glyph count of the font the dialog is opened on. *Quick Overlay* opens it on a small font holding only the glyphs to compare, with the family's fonts overlaid: a fraction of a second per change ([QUICK-OVERLAY.md](QUICK-OVERLAY.md)).

## Windows and tabs

- **A document tab dropped anywhere becomes a window of its own**, even on the tab bar it came from, and only *Window > Docking > Merge Window* brings it back. Tab docking puts a tab released on or near the bar back in the main window, at the place shown, so tabs also reorder by dragging; it can also keep tabs from being undocked at all ([WINDOWS.md](WINDOWS.md#tab-docking)).

## Display

- **The slant tool's icon jumps up a pixel as the tool is checked**: FontLab's picture for the checked state is drawn a pixel higher than the unchecked one. FreeLab gives the button the same icon with the two pictures lined up, whether dark mode is on or off ([DARKMODE.md](DARKMODE.md)).

## Known, not fixed

- **Glyphs open with a transparent fill in FontLab 7.2.0.7649.** On 11 March 2022 FontLab published build 7649, the last FontLab 7 build, then found that opening some fonts sets the glyphs' fill transparent, and put build 7644 back up for Mac and Windows ([FontLab's news](https://www.fontlab.com/news/)). FontLab does not say which fonts, so FreeLab cannot reproduce it and does not try to mend it. If it happens: *View > True Fill* (Shift+Space) shows the fill fully opaque, and *Preferences > Glyph Window* sets the fill's opacity ([FontLab 7's manual](https://help.fontlab.com/fontlab/7/manual/Outline-Appearance/)); or install 7.2.0.7644 instead, which lacks only one of 7649's fixes (a Font window filtered by code page shows its empty cells). No FontLab 7 build came after 7649: FontLab told users to skip the update notice for 7651.

## Where they live

The *Overlay Fonts* guard and the slant icon are in dark mode's file (*darkmode/freelab_dark_mode.py*), which FreeLab's startup block runs at every launch, so they work with dark mode off; removing dark mode's file removes them. Tab docking is *windows/freelab_tabs.py*, also started at launch. The crash check and *Quick Overlay* act only when their tools are used.
