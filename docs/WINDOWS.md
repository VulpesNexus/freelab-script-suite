# What every FreeLab window shares

## Layout

Every window reads the same way, top to bottom:

- **The top line**: the font and its master (`ak.font_named`: *Cardo, master Bold*, with the number of masters only when there are several), then what the tool found, in short; the tools menu, the arrows, and **?** at its right. Text about the results always sits here, under the font line, never under a row of buttons, with a blank line between the two in every window, whether they are separate labels (`ak.window_head`) or one (`ak.head_join`; owner's images 346, 355, and 358). The font line stays at the top of the row whether a result line follows it or not.
- **A line** that sets the top text apart from the rest (`ak.header_separator`), shown in every window, with or without a font.
- **The tabs** (if any), then **the options**, each run button (*Analyze*, *Check*, *Compare*, *Read sheets*, *Save template…*) at the end of the options it reads, never pushed to the window's right edge.
- **The lists and previews**: previews are captioned in a smaller, quieter type, and set apart from each other and from a reference beside them by thin lines; a section heading that follows a list on the same tab has a line above it. A preview area shows nothing until it has something to preview: its captions and the lines between its previews come with the first picture and go when it is emptied (`ak.preview_filled`). A list's dotted handle sits right under its frame; the handle between Feature Code's tabs and its code is drawn as nothing while *Stylistic alternates* is shown, where it would meet the line between that tab's two previews (image 11), and is still dragged there: the pointer shows it.
- **The log**. Its bottom edge drags to make it taller or shorter (no handle is drawn: the pointer changes over it), and the window's bottom edge moves with it.
- **The bottom row**: at the left, what acts on the list's ticks and rows (*Tick all*, *Untick all*, *Tick high-value glyphs*, *Restore suggestions*, *Show in Glyph window*); at the right, the compile tick if any, the action that writes (*Build ticked glyphs*, *Apply ticked fixes*, *Update the code*), *Cancel* (in every window whose work can stop: [Long work](#long-work)), and *Close*. A tabbed window shows the shown tab's buttons there.

Check boxes are *ticked*: "check" is the verb of the tools that check a font (*Check* in Font Check, Kerning Check, and Feature Check). Captions take one of two forms: a noun and a colon (*Script: Latin*), or a sentence the controls finish, ending with its period (*List changes of at least 20 units.*). A caption is grayed with its control, the period too (images 319 to 323), and a right-click on it shows the control's help. A tick's caption that is a sentence ends with a period (*Also list existing glyphs.*, image 324); one that names a thing (a feature, a section: *Vertical forms (vert, vrt2)*) has none. A right-click on a tab shows that tab's help, where the click was: its own, else what the window's help says of it, else its list's. Dropdowns are as wide as their widest choice, and so are their open lists, so no choice ends in an ellipsis. Tabs are flat, the chosen one underlined; every tab takes the text's color, the chosen one told by its underline alone, on a light window and on a dark one: a mid gray for the others reads as grayed out. On a light window a grayed field or spin box is filled a shade darker than the window, so an empty one still shows (Windows' own style would fill it with the window's color). Italic words are followed by a hair of room in status lines, logs, and tooltips (`ak.italic_gaps`): FontLab's interface font has no italic of its own, Windows slants the upright one, and each slanted letter reaches one or two pixels past its width, onto the space or the punctuation after it (measured live). A tooltip is as wide as its text, measured as Qt lays it out, with no room after the text. A picture's glyph that leads elsewhere (Auto Kerning's and Auto Spacing's neighbors in their previews, Glyph Compose's) takes a double-click, never a single one (images 333 and 362). Counts group their thousands (*13,932 glyphs*). In the top text and the log, a count is bold with its noun (*1,200 of 13,932 drawn glyphs*), and a number with no noun of its own is bold alone. Headers and tabs give theirs in parentheses (*Glyphs (13,956)*), and a tab that counts differences says *(alike)* where there are none (images 327 and 328). A log names another tool as a link that opens it in the window's place. A glyph a log line names by its name is in italics, a link that opens it in a *Glyph* window of the window's font (*Made dotlessi from i without its dot*), as a glyph drawn in a log line (a character built, a pair kerned) already does; a glyph taken out since is not opened, and the log says so. A glyph of another font (Family Audit's new font) is in italics alone, and a long list names its first glyphs and counts the rest (*and 12 more*). A log line that says a file was saved (Font Builder's template sheets, Proof's PDF) names the folder as a link: a click opens the folder in a new Explorer window with the file selected (*explorer /select*, no console window; on macOS the Finder, *open -R*; elsewhere the folder alone), and the log says so when the file is gone (image 375).

## The menu

*Scripts > FreeLab* lists the font tools in the order a font is usually made (Font Builder, Glyph Compose, Auto Spacing, CJK Spacing, CJK Vertical, Auto Kerning, Kerning Check, Feature Code, Feature Check, Font Compare, Family Audit, Font Check, Proof), then *Quick Overlay* on its own, then dark mode and tab docking with their settings (FontLab's interface helped), then FreeLab MCP's, then *Set Up FreeLab* where a release's folder was dropped in ([INSTALL.md](INSTALL.md#install-from-a-release)), with separators between them; *Dark Mode* and *Tab Docking* are ticked while they are on. FontLab lists a folder's scripts by file name, so FreeLab's startup block arranges the menu each time *Scripts* opens.

## One window per font

Each open font has one FreeLab window, named after it in its title (*FreeLab Font Check (Cardo)*). A tool opened for a font takes the place of the tool that font's window showed, and a window keeps working on its own font while FontLab shows another, so two fonts open side by side each have their own. A window closes with its font, and every FreeLab window closes with FontLab. A window opened with no font open has no name in its title; FontLab's menu, the tools button, and the arrows reuse it, and it takes the next font you open, never a font that has a window of its own (its tools button then opens the tool in that font's window). A tool opened from FontLab's menu opens on the font FontLab shows, whichever FreeLab window was active; one opened from a window's tools button, its arrows, or a button that hands glyphs over opens on that window's font. Each is a window of its own, with a button on the taskbar.

A window opens at 1000 by 1000 pixels (Font Check's 1,400 wide, for its two lists), or at what the screen FontLab is on allows: a window not resized by hand widens, up to that screen, when a list cannot show its columns whole, and on a screen with less than 1000 by 700 free pixels its content scrolls. Once you resize a window by hand, that size is every tool's, for every font, until FontLab quits. A window that takes another size grows or shrinks around its center, kept on screen.

## What the font tools share

- At the top right, a menu button that opens any other font tool, with arrows beside it for the tool before and the tool after.
- A top line with a sentence per line.
- A log under the list: done in green, warnings in amber, errors in red.
- *Restore suggestions*, which puts every tick back as the list first came.
- A right-click on a row flags its glyphs in FontLab, as its *Flag* menu does, to find them again with *Select > Same Flag* or the *Flag* section of the Font window's sidebar. A row is tinted with its glyph's flag color, with a bar of it that shows on a selected row too (a pair's cell split in two, each glyph's flag on its own half). *F3* and *Shift+F3* go to the next and previous flagged row.
- Buttons gray out when they would do nothing; a right-click on a grayed-out one still shows its help.
- Dropdowns open below their box, as a list of 24 rows at most, scrolled.
- Tooltips as wide as their text, at most half the window: one line when they fit, a blank line between paragraphs.
- A number field's tooltip and help (its caption's too) end with what it takes, read from the field's own bounds: *From 0 units to 500 units.*, *From 10% to 200% of the em.*
- A click under a list's last row, or beside the lists, unselects a row.
- Lists that draw each row's glyph from the font, their columns always filling the list ([Lists](#lists)).
- A double-click on a glyph or a pair opens it in a Glyph window; in Auto Spacing, a double-click on a preview's neighboring glyph opens that pair in Auto Kerning.
- A fresh look at the font after an undo, a redo, or an edit in FontLab.

## Writes and Undo

Each write is recorded in FontLab's History, and *Edit > Undo* takes it back, in one step but for a Glyph Compose write that adds glyphs others of it are made of, which takes two ([GLYPH-COMPOSE.md](GLYPH-COMPOSE.md#the-list-the-log-and-the-history)). What the History does not hold has a button of its own: CJK Vertical's *Put back vhea* puts back the vhea values it wrote, and Font Check's *Put back old values* the vertical metrics (for the Win values a write raises, see [The font info](#the-font-info)). *Ctrl+Z*, *Ctrl+Shift+Z*, and *Ctrl+Y* in a tool's window undo and redo in FontLab on the window's own font when the focus is not in a field; in a text field or a number box, they undo and redo your typing there, never FontLab's History. FontLab's own windows are then told to draw the font again. FontLab's Undo acts on the font it shows, so when it shows another, the window's font is brought to the front first; when that cannot be done, the window says so and names the font to click, and when the window's font is no longer open, nothing is undone.

The first write that changes a font's glyphs in a session comes after a step of its own, the font as it was (named after the tool, with *(before)*), which gives Undo something to go back to: when FontLab cannot record that step, nothing is written. When FontLab does not record a write, or does not mark the font as modified, the log says so as an error, and promises no Undo.

## Long work

A step that takes a while (reading a font, measuring, listing, checking, writing) shows its name and a green bar in the window's top row, between the window's left edge and its **?** button. The window keeps repainting meanwhile, so Windows never marks it *Not Responding*.

While it runs, clicks, keys, and the wheel wait, in the window and in FontLab: nothing may change what the work is reading. A few controls stay usable:

- **Cancel**, right before *Close*, in every window whose work can stop,
- the tools menu (**≡**) and the **‹ ›** arrows,
- **Close** and the title bar's **✕**,
- **Esc**.

Each one stops the work at its next step: the tool sets aside what it was doing, then does what was clicked (opens the other tool, closes the window) or, for *Cancel* and *Esc*, simply stops (the same stop, the same lines in the log). *Cancel* is grayed while nothing runs and while the work cannot be stopped, never hidden, so the row never shifts (`ak.cancel_button`; its help adds what a stop leaves behind). A write to the font is never stopped half way: it ends whole in FontLab's History, and the click is done after it. A file saved is never half written either: Font Builder's sheets and Proof's PDF are written beside their files and take their places only once all are whole, so a stopped save leaves nothing behind and replaces nothing ([FONT-BUILDER.md](FONT-BUILDER.md#template), [PROOF.md](PROOF.md#the-window)). A stopped reading, check, or comparison changes nothing in the font, and each window's *Cancel* says what its stop leaves. A window with no work that can stop (Auto Kerning's *Kerning Classes*) has none.

FreeLab's scripts run inside FontLab, in its own thread. If Windows ever offers to end a window that is not responding, it would end FontLab with it: the bar and the stop above exist so that this never has to happen.

## With no font

A window with no font open says so on its first line, *No font is open. This window hooks to the next font you open.* (with Proof's and Font Builder's own no-font lines, the only sentences FreeLab puts on one line). Its controls are grayed until a font comes, all but the tools menu, the arrows, help, Close, and what a tool can do without a font (Font Builder's template, Font Compare's choice of fonts, Family Audit's *Add files…*); they are grayed before the window first shows, so nothing flashes usable. The line under the top text stays; the other lines, which set apart parts that are empty, are hidden. An empty status line takes no room. A window with no font opens at the size every tool opens at, and one that opens wider for its content (Font Check) widens once it hooks to a font.

## Lists

A list's columns share its width; drag a column's edge to give it more, taken from the other columns, those with room to spare first, and the last column stays at the frame's edge while you drag. A column cannot be made narrower than 24 pixels, so it never disappears, and a column dragged wider stops where the columns after it reach their least (their header's text): it never pushes them past the frame. A list with no rows shows no scroll bars. A dropdown with more choices than fit opens as a scrolled list, with a scroll bar.

## The font info

A write that adds glyphs or code points (Glyph Compose's builds and its *Glyph generation* tab, Font Builder's *Build ticked glyphs*, Feature Code's figure forms) updates what the font info says the font covers, where the write changed it. FontLab 7 exports the font info's coverage as it stands, never recalculated (found live), so a font whose glyphs grow would otherwise ship declaring less than it has. The rule (*checks/freelab_font_info.py*):

- **Unicode ranges** (OS/2): a range the write gave the font its first character of is set; one it took the last character of out is cleared.
- **Code pages** (OS/2): the same, for the Windows code pages (1250 to 1258, Thai 874) and the East Asian ones. A code page counts as covered when the font has every letter of its script that it encodes, and A to Z: 1252 needs Š and Ÿ, not ƒ, ª, or µ. The East Asian ones need their standard's first level: JIS X 0208's kana and level 1 kanji (932), GB 2312's level 1 hanzi (936), KS X 1001's 2,350 Hangul syllables (949), Big5's 5,401 frequently used hanzi (950), and every Hangul syllable (Johab, 1361). Macintosh Roman, the MS-DOS code pages, OEM, and Symbol are left as declared: few fonts declare them.
- **Win ascent and descent**: raised to the ink of a glyph the write drew above or below them, never lowered, and left unset where they are not set (0: a value made from a few glyphs would clip the others). Windows clips glyphs outside them, and uses them for line spacing in apps that ignore the typo metrics: a raise can open the lines up there. FontLab exports them from each master's *Safe top* and *Safe bottom* (Font Info's *Font Dimensions*), not from the font info's copy (live 2026-11-27: values set only there were exported as the master's), so each master's own values are read and raised, and the log names the master in a font of several (*Win ascent of Bold (1100 to 1150)*).

Every other bit and value stays as declared, set by hand or not. The log says what changed (*Updated the font info to match: Unicode ranges (added Hangul Syllables); Win ascent (900 to 951).*). Font Builder sets a new font's names and metrics itself, and Font Check, CJK Vertical, and Family Audit write the font info as their own pages say.

*Edit > Undo* takes the Unicode ranges and code pages back with the write's glyphs, and *Redo* sets them again: FontLab keeps them with the font's encoding, which the write's History step records (found live). It does not take back the Win values, nor any other OS/2 metric. FreeLab keeps its Win raises for the session instead: when the History moves while a FreeLab window shows the font (an undo, a redo, or an edit in FontLab that adds or takes out glyphs), it puts each one back in step with the glyphs it was raised for, in its own master, and those a later write drew within it, never under their ink, and says so in the log. A value changed by hand since is left as it is. An undo made with no FreeLab window open is followed at the next write that updates the font info.

The `meta` table's language tags (`dlng`, `slng`) are not written: FontLab 7 keeps no `meta` table for export (one added to the font was dropped from the exported file, live).

## Tab docking

FontLab 7 makes a window of every document tab dropped anywhere, even on the tab bar it came from, and only *Window > Docking > Merge Window* brings it back. FreeLab's tab docking (*windows/freelab_tabs.py*) changes that. It starts at launch, from FreeLab's startup block. *Scripts > FreeLab > Tab Docking Settings* chooses its two options, and *Scripts > FreeLab > Tab Docking* switches it off and on; both are kept in *%LOCALAPPDATA%\FreeLab\tabs.json*.

*Dock tabs released on or near the tab bar.* (ticked at first):

- While a tab is dragged, a marker on the main window's tab bar shows where it will go.
- Released on the bar or within 40 pixels of it, the tab goes into the main window at that place, from the main window or from a window of its own, so tabs reorder by dragging. Released farther away, it becomes a window of its own, as FontLab makes it.
- A window of its own gets a *Dock* button beside its tabs, and a double-click on one of its tabs docks it. Dragged by its title bar, it docks when released with the mouse on the main tab bar or within 12 pixels of it.
- A tab just dragged out of the main window gets no blue drop highlight from FontLab over the area it left, since a release there put the tab back: FreeLab hides it for the first 1.5 seconds of the drag, or until the mouse leaves the document area, and after that the highlight is FontLab's own again, so the tab can be dropped back there (or on the tab bar at any time). A window's highlight is FontLab's own throughout.

*Tabs cannot be undocked.* (unticked at first):

- A press on a main window tab is kept from FontLab's tab bar, so no tab can be dragged out of the main window; FreeLab chooses the tab at the release, as the click would have. FontLab shows no close cross on a tab whose presses it never gets, so FreeLab shows its own at the left end of the tab under the mouse (not on the Sketchboard, which does not close), and a click there closes the tab through FontLab's own slot (which asks about unsaved changes as usual).
- FontLab's *Undock* commands (*Window > Docking*) are hidden.
- With the first option ticked too, a tab still moves along the bar: released on or near it, it goes to the marker's place; released anywhere else, it stays where it is. With the first option unticked, dragging a tab does nothing.

With either option, a main window tab held down without moving is not shown until the mouse is released.

## Driving FreeLab with FreeLab MCP

FreeLab MCP (the separate `freelab-mcp` repository) has window tools that drive any of FontLab's windows as a user would: `list_windows`, `list_window_controls`, `click`, `set_value`, `read_list`, `read_text`, `click_link`, `list_menu`, `run_menu_command`, and `wait_idle`. They know nothing of FreeLab, and FreeLab needs nothing of them; FreeLab follows the optional conventions their [WINDOW-TOOLS.md](https://github.com/VulpesNexus/freelab-mcp/blob/main/docs/WINDOW-TOOLS.md#conventions-a-script-can-follow) describes, so that its windows are driven surely:

- **Its windows are its own.** Every tool window, *FreeLab Kerning Classes*, *FreeLab Dark Mode*, and Font Builder's question before it replaces sheets carry `mcpScriptWindow`: the MCP drives them as a script's, never taking them for a question of FontLab's.
- **Busy, with the step.** While a window works, its `mcpBusy` is the step shown in its top row (*Checking*); once the work is over, `False`. `wait_idle` waits on it.
- **Controls by name.** Each control a tool holds takes the name of the attribute that holds it as its objectName, once, as the window is built (and after each work, for the controls made since): *check_button*, *tree*, *log* (a part's view takes the part's name), *coverage.status* (a part's control: the part's name, then its own). The pages a tab bar switches take their tab's name (*pages.coverage*). The top row's buttons are *freelabTools* (named *Tools*: give `entry`, a tool's name, to open it), *freelabPreviousTool* and *freelabNextTool* (*Previous tool*, *Next tool*), and *freelabHelp* (*Help*). `list_window_controls` gives each control's objectName; a control is found by it whatever its text.
- **Files need risky mode.** The buttons that write files outside FontLab's *History* carry `mcpRisky`, so the MCP clicks them only in its risky mode: Font Builder's *Save template…* and its *Replace*, Proof's *Save PDF…* and its *Replace*, CJK Vertical's *Add vertical metrics to an exported font…*, and Font Check's *Save set* and *Remove set*. A write to the font is an ordinary action: *Edit > Undo* takes it back.

A dropdown in a list's row (Feature Code's ligatures) is addressed through its list, in the rows' order: *ligature_tree > combo#2*. What the MCP cannot do here: Windows' own file dialogs (*Add files…*, Font Builder's sheets, Font Compare's font file, and the files the risky buttons ask for) wait for you; a right-click (the rows' *Flag* menu, a caption's help) and *Ctrl+Z* in a window are not available to it (`run_menu_command` with *Edit > Undo* undoes the font in front).

## A reinstall in the same session

Installing FreeLab again while FontLab runs replaces its scripts; windows opened before keep working on the copy they were opened with (it is kept for the session) until they are closed.
