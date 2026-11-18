# Family Audit

*Scripts > FreeLab > Family Audit* compares the fonts of a family with one another, before they become masters of one font: the glyphs each lacks and the code points that differ, each glyph's structure across them, their font info side by side, their kerning, and their feature code. It changes nothing in any of them. Its one action, *Assemble as masters*, makes a new font with a master per source, and leaves the sources as they were.

It answers the owner's question whether a tool that makes masters out of a set of fonts would be of use or only fancy. A survey of 4,986 fonts (the owner's and the corpus's) found that only about 7% of static Regular and Bold pairs are compatible for interpolation as shipped, that within families of several files the glyph sets differ in 39%, the versions in 13%, and the feature code in 16%, and that the owner's own FontLab projects mostly hold one master each. So the audit comes first: it says what differs and where, which is what tidying a family takes; assembling the masters is a second step, which reports compatibility and never promises interpolation.

## The window

The window keeps every FreeLab window's layout ([WINDOWS.md](WINDOWS.md)). The top line names the window's font and how many sources are ticked, with the reference: *Sans: 3 of 5 sources ticked (reference Regular).* (the counts with their noun in bold); under it, the status line of the tab shown, then the header's line. The options follow, in one row: *Add files…*, *Reference:* [a dropdown], and *Compare* at their end. Under them, the sources' list over the results, in a splitter: the list's frame, the handle right under it, then a line, the tabs, and the tab's list. The log follows, then the bottom row: *Tick all*, *Tick none*, and *Show in Glyph window* at the left, *Assemble as masters* and *Close* at the right.

With no font open, the top line reads *No font is open. This window hooks to the next font you open, or click Add files… to open a family's fonts.*, on one line. Every control is grayed then but *Add files…*, which opens fonts, and the *Reference* dropdown reads a grayed *n/a*.

## Sources

The sources' list holds the fonts open in FontLab, a row for each master of a font of several masters (a variable font, a designspace, a Glyphs file, a FontLab project with masters). Its columns: the source's name in the window, its file, the file's format (*VFC*, *UFO*, *OTF*, *unsaved*…), its font's masters, its glyphs, and its version. A source is named by its style, or by its master in a font of several; two sources of one name take their font's name in parentheses (*Regular (Sans)*), then their file's (*Bold (Sans, old.otf)*), then a number.

To start with, the window's own font is ticked with every open font of its family (the same family name); with no font of its own, the family most open fonts belong to. The list is read again each time the window becomes the active one: the ticks are kept, and a new font of the family is ticked. A font closed leaves the list.

*Add files…* opens font files in FontLab, several at once, in any format FontLab 7 opens: FontLab projects (*.vfc*, *.vfj*, *.vfb*), UFO (*.ufo* is a folder, which a file dialog cannot pick: pick any file inside it, *metainfo.plist* for one) and *.ufoz*, Glyphs, designspace, OpenType and TrueType (*.otf*, *.ttf*, *.otc*, *.ttc*), WOFF and WOFF2, and Type 1 (*.pfb*, *.pfa*). FontLab opens a font in the background: the window looks for each font twice a second, for up to a minute, matches it with its file by path (a font that gives no path is taken for the first file still awaited, once the fonts with paths are matched), ticks it, and says so in the log: *Opened Sans-Bold.otf in FontLab: ticked as Bold.* A font of another family than the window's (its own font's, else the one the ticked sources belong to) is left unticked, and the log says so: tick it to compare it all the same (image 344: a font of another family was ticked with the family). A file open already is ticked at once. A file that never comes in is said, as FontLab may be waiting for an answer in a dialog of its own (*Coordinates Rounding*, for some fonts).

*Reference:* is the source the others are compared with, and whose glyph order, feature code, classes, and font info a new font assembled from them takes. To start with, it is the upright source whose weight is nearest Regular's 400 (a style named Regular, Book, Roman, Normal, or Plain first), of the normal width: its weight class from its font info, else from its style's name (*SemiBold* 600, *Black* 900); a font of several masters goes by its masters' names, since its font info is the font's, not each master's. A choice stays while its source is ticked.

*Compare* reads the ticked sources (at least two) and fills the tabs. It shows its steps in the window's top row and can be stopped there. A tab counts what differs in parentheses: *Compatibility (40)*. Ticking another source or choosing another reference afterward leaves the tabs as they were, says so in the status line, and grays *Assemble as masters* until *Compare* is clicked again. A tab with nothing that differs says *(alike)* rather than *(0)* (images 327 and 328). The audit is kept for the FontLab session: a Family Audit window opened again (after another tool, or closed) shows it again, its sources ticked, as long as every source is still open and none changed since (each font's place in its History), and the log says so; otherwise it shows nothing until *Compare* (image 330).

## Glyph sets

The glyphs each source lacks that another has, a group a source (*Missing from Bold (12 glyphs)*), each row saying which sources have it. A master lacks a glyph that has no layer in it. Then the code points that differ: a glyph name with other code points in another source (*U+0061 in Regular; none in Bold*), and a code point given to glyphs of other names (*U+00E9: eacute in Regular; uni00E9 in Bold*). Glyphs are matched by name across a family, since a family's members should share their names; a renamed glyph shows both as missing and under its code point.

## Compatibility

Each glyph in at least two sources is compared, each source with the reference (or, where the reference lacks the glyph, with the first source that has it), in this order: the number of contours, the components (names, in order), the number of nodes of each contour, the node types of each contour (on-curve, curve, off-curve), the direction of each contour, and the anchors (by name). The first difference found is the glyph's: *contour 2: 12 nodes in Regular, 14 in Bold*, *contour 1 runs the other way in Black*, *components in another order in Bold*. The glyphs are grouped by that first difference, then *Compatible*, closed.

A glyph whose structure matches in every source has what interpolation needs, but no more: start points, contour order (contours of the same structure in another order), and the shapes themselves are not compared, and FontLab may still find two layers incompatible. The status line says how many glyphs match and that it promises nothing more: *312 of 340 glyphs match in structure (contours, nodes, components, and anchors). That is needed for them to interpolate, but does not promise it.* Sources of other outline formats (a TrueType file and a CFF one) differ in nearly every glyph, as they should: their curves are made of other points.

*Show in Glyph window* (or a double-click on a row) opens the selected row's glyphs in a *Glyph* window of the window's font, as every FreeLab list does.

## Metrics and info

The font info a column per source: family and style names, version, units per em, ascender, descender, x-height, cap height, line gap, the OpenType typo, hhea, and win values, italic angle, and weight and width classes. Three groups: *Should match, but differ* (what a family shares: names, version, units per em, the line metrics and the OS/2 and hhea values that set line spacing), *Differ by style* (style name, x-height, cap height, italic angle, weight and width classes, which may differ on purpose), and *Alike*, closed. A field no source gives is left out.

FontLab gives a script the line metrics (ascender, descender, x-height, cap height, line gap) of a font's current master only, and the tool never switches a source's master: another master's are left blank.

## Kerning

As Kerning Check's *Masters* tab compares a font's masters: the kerning classes whose members differ between sources (against the reference's: *Bold lacks oacute; Bold adds odieresis*), or that only some sources have; the entries only some sources kern (*not kerned in Black*); and the entries that tighten in one source and loosen in another by more than 10 units, where an instance between them may collide. A source with no kerning at all is said once, rather than against its every entry; a source whose kerning cannot be read is left out, and the status line says so.

## Features

The prefix, each feature, and the Classes panel's classes, as Font Compare splits them, each source's code compared with the reference's line by line: the features some sources lack, then those whose code differs, then those alike, closed. A row under each feature for each source that differs (*3 lines only in Regular, 2 lines only in Bold*); selecting it shows its lines beside the list, those only in the reference on red after a minus, those only in that source on green after a plus, as Font Compare shows them.

## Assemble as masters

After an audit, *Assemble 3 sources as masters* (its count follows the sources) makes a NEW font in FontLab, which opens in its own window, and never changes the sources:

- a master per audited source, named by the source's name in the window, the reference's first (the default master);
- every glyph of every source, in the reference's glyph order, then the glyphs only other sources have, in the order they come; each glyph's layer in a master copied by name from that master's source: its outlines (the contours copied, nothing shared with the source), its components (made once the glyphs they draw are drawn, as FontLab builds a component from its glyph as it is then), its anchors, and its width; a glyph a source lacks has an empty layer in its master, and the log lists those glyphs master by master;
- the code points of the reference's glyphs (else of the first source that has the glyph); where sources give a glyph other code points, the reference's are kept, and the log says which;
- each master's kerning from its source: its classes, then its entries;
- the reference's feature code, its prefix with the Classes panel's feature classes written first as code (FontLab offers a script no way to fill the Classes panel), and its font info (family name, version, the OpenType line values, copyright, designer, manufacturer, license, vendor);
- the reference's Unicode ranges and code pages, updated for what the new font covers as the tools update them after a write ([WINDOWS.md](WINDOWS.md#the-font-info)): a range or code page the other sources' glyphs complete is set, and the reference's own choices stay; and the largest Win ascent and descent of the sources (each source's covers its own glyphs; the font's are one for every master), the log saying so where it is not the reference's;
- each master's line metrics from its source, where they could be read (see *Metrics and info*);
- a *Weight* axis (*wght*) where the sources' weight classes differ, a *Width* axis (*wdth*) where their width classes differ, each master placed at its source's classes; no axis where they are alike. Sources that would share a location (a Regular and an Italic of one weight) are said: an italic needs an axis of its own, which the tool does not set.

The units per em are the reference's; sources with other units per em are copied unscaled, and the log says so. The new font is marked modified and not saved: there is no step to undo in its History, since it did not exist before; close it without saving to take it back. The log says what was made (*Made a new font with 3 masters (Regular, Light, and Bold) and 412 glyphs; 9 layers are left empty where a source lacks their glyphs.*), how many glyphs matched in structure at the audit (that is needed to interpolate, not a promise of it), and, as warnings, whatever could not be carried over: a line a kind, its glyphs listed in short, with FontLab's own error, so that a call FontLab refuses for every glyph is one line, not thousands. When FontLab makes no font, or not its masters, nothing is placed in it: the log says the font was left unfinished, to close without saving.

The sources are read again as *Assemble* starts, as they are then. Making the new font cannot be stopped halfway: its steps show in the top row until it is done.

## FontLab calls not yet proven live

Every FontLab call of the tool is a method of `FontLabCalls`, each with a docstring saying what it assumes. Proven before (FreeLab MCP's *FONTLAB7-API.md*, Font Compare, Feature Code, Glyph Compose): the open fonts and their numbers, `masters`, `master`, `tfn`, `tsn`, `path`, `versionMajor` and `versionMinor`, `fgPackage.glyphs` and their `unicodes`, `findName`, `getLayerByName` (with `True` to make a layer), a layer's shapes, contours, nodes and their types, components and anchors, `kerning(master)` read through FontKerning and written through it, `groups[name] = (members, side)`, `get_feature`, `get_prefix`, `set_feature`, `getAllGroups`, `requestLoadingFont`, `flPackage()` for a new font, `flGlyph()` and `addGlyph`, `flShape()` with `addContours` and `flContour.clone()`, `GlyphComponent` with `setGlyphComponents`, `flPinPoint` with `addAnchor`, `advanceWidth`, `fgGlyph.unicodes`, `flGlyph.update()`, `rebuildMaps()`, `notifyPackageContentUpdated`, and `setFlag(2, True)`. To check live, on a disposable font, before the owner relies on *Assemble as masters*:

- `flPackage.renameMaster(old, new)`: rename the new font's first master; read `masters` back.
- `flPackage.addMaster(name, False, None, "", False, False)` (Font Builder's call, its arguments unchecked): add a master; read `masters` back, and check that every glyph then has a layer of that name.
- `flPackage.master = name`: make a master current; read `master` back, and check that `ascender_value` then reads that master's.
- `flShape.transform = …` on a new shape: copy a shape whose transform is not the identity (a scaled or moved contour shape); compare the copy's drawn box with the source's.
- `setGlyphComponents` on a layer that has contours already, then contours added after it: check that both stay (the tool calls it first, then copies the contours).
- `fgPackage.features.set_prefix(text)`: write a prefix; read it back with `get_prefix()`.
- `flPackage.setUpm(units, False)` on a new font: read `upm` back.
- `setattr(fgPackage.info, name, value)` for `familyName`, `copyright`, `openTypeNameDesigner` and the other text fields, and the OS/2 and hhea values: read each back (only the vhea values are proven settable).
- `flPackage.versionMajor` and `versionMinor` as settable: read them back.
- `ascender_value`, `descender_value`, `xHeight_value`, `capsHeight_value`, `lineGap_value` as settable for the current master (Font Builder's): set them in two masters, then read each master's back.
- `fontlab.flAxis()` with `name`, `tag`, `shortName`, `minimum`, `maximum`, and `default` or `defaultValue`, then `flPackage.addAxis(axis)`: read `axes` back, and look at *Font Info > Axes*.
- `flPackage.setLocation(master, {axis name: value})`: read `location(master)` back, and look at the masters' locations in *Font Info > Masters*.
- `fontlab.flItems.notifyPackageAdded(package)` (Font Builder's): check that the new font's Font window opens.
- `fgPackage.info.italicAngle`, `openTypeOS2WeightClass`, `openTypeOS2WidthClass`, `familyName`, and `styleName` as read: compare with *Font Info* on a static font.
- Opening each format through `requestLoadingFont`, and whether a font opened from a binary file (OpenType, WOFF, Type 1) gives that file as its `path` (else it is matched as the first file awaited).
- How long reading and assembling take on four static fonts of a few thousand glyphs, and on a CJK family.

## Limits

- Glyphs are matched by name only (a family's members should share them); Font Compare pairs two fonts' glyphs by code point too.
- Compatibility compares structure, not shapes: Font Compare and Font Check's *Masters* tab look at the outlines themselves.
- The new font's feature code and font info are the reference's alone: the other sources' code that differs is not merged, and the log says so.
- No italic or optical axis is set, nor instances; a family whose sources share a weight and width (a Regular and an Italic) is said, and left on one location.
- The line metrics of a master of a font of several masters other than its current one are not read.
