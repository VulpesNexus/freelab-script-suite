# What every FreeLab window shares

## Layout

Every window reads the same way, top to bottom:

- **The top line**: the font and its master (`ak.font_named`: *Cardo, master Bold*, with the number of masters only when there are several), then what the tool found, in short; the tools menu, the arrows, and **?** at its right. Text about the results always sits here, under the font line, never under a row of buttons.
- **A line** that sets the top text apart from the rest (`ak.header_separator`), shown in every window, with or without a font.
- **The tabs** (if any), then **the options**, each run button (*Analyze*, *Check*, *Compare*, *Read sheets*, *Save template…*) at the end of the options it reads, never pushed to the window's right edge.
- **The lists and previews**: previews are captioned in a smaller, quieter type, and set apart from each other and from a reference beside them by thin lines; a section heading that follows a list on the same tab has a line above it. A list's dotted handle sits right under its frame.
- **The log**.
- **The bottom row**: at the left, what acts on the list's ticks and rows (*Tick all*, *Tick none*, *Tick high-value glyphs*, *Restore suggestions*, *Show in Glyph window*); at the right, the compile tick if any, the action that writes (*Build ticked glyphs*, *Apply ticked fixes*, *Update the code*), and *Close*. A tabbed window shows the shown tab's buttons there.

Check boxes are *ticked*: "check" is the verb of the tools that check a font (*Check* in Font Check, Kerning Check, and Feature Check). Captions take one of two forms: a noun and a colon (*Script: Latin*), or a sentence the controls finish, ending with its period (*List changes of at least 20 units.*). A caption is grayed with its control, the period too (images 319 to 323), and a right-click on it shows the control's help. A tick's caption that is a sentence ends with a period (*Also list existing glyphs.*, image 324); one that names a thing (a feature, a section: *Vertical forms (vert, vrt2)*) has none. A right-click on a tab shows that tab's help, where the click was: its own, else what the window's help says of it, else its list's (image 329: the whole window's help, in the middle of the window). Dropdowns are as wide as their widest choice. Counts group their thousands (*13,932 glyphs*); headers and tabs give theirs in parentheses (*Glyphs (13,956)*), and a tab that counts differences says *(alike)* where there are none (images 327 and 328). A log names another tool as a link that opens it in the window's place.

## Long work

A step that takes a while (reading a font, measuring, listing, checking, writing) shows its name and a green bar in the window's top row, between the window's left edge and its **?** button. The window keeps repainting meanwhile, so Windows never marks it *Not Responding*.

While it runs, clicks, keys, and the wheel wait, in the window and in FontLab: nothing may change what the work is reading. A few controls stay usable:

- the tools menu (**≡**) and the **‹ ›** arrows,
- **Close** and the title bar's **✕**,
- **Esc**.

Each one stops the work at its next step: the tool sets aside what it was doing, then does what was clicked (opens the other tool, closes the window) or, for Esc, simply stops. A write to the font is never stopped half way: it ends as one step of FontLab's History, and the click is done after it.

FreeLab's scripts run inside FontLab, in its own thread. If Windows ever offers to end a window that is not responding, it would end FontLab with it: the bar and the stop above exist so that this never has to happen.

## With no font

A window with no font open says so on its first line, *No font is open. This window hooks to the next font you open.* (with Proof's and Font Builder's own no-font lines, the only sentences FreeLab puts on one line). Its controls are grayed until a font comes, all but the tools menu, the arrows, help, Close, and what a tool can do without a font (Font Builder's template, Font Compare's choice of fonts, Family Audit's *Add files…*); they are grayed before the window first shows, so nothing flashes usable. The line under the top text stays; the other lines, which set apart parts that are empty, are hidden. An empty status line takes no room. A window with no font opens at the size every tool opens at, and one that opens wider for its content (Font Check) widens once it hooks to a font.

## Lists

A list's columns share its width; drag a column's edge to give it more, and the last column stays at the frame's edge while you drag. A column cannot be made narrower than 24 pixels, so it never disappears, and a column dragged wider stops where the columns after it reach their least (their header's text): it never pushes them past the frame. A list with no rows shows no scroll bars. A dropdown with more choices than fit opens as a scrolled list, with a scroll bar.

## The font info

A write that adds glyphs or code points (Glyph Compose's builds and its *Glyph generation* tab, Font Builder's *Build*, Feature Code's figure forms) updates what the font info says the font covers, where the write changed it. FontLab 7 exports the font info's coverage as it stands, never recalculated (found live), so a font whose glyphs grow would otherwise ship declaring less than it has. The rule (`checks/freelab_font_info.py`):

- **Unicode ranges** (OS/2): a range the write gave the font its first character of is set; one it took the last character of out is cleared.
- **Code pages** (OS/2): the same, for the Windows code pages (1250 to 1258, Thai 874) and the East Asian ones. A code page counts as covered when the font has every letter of its script that it encodes, and A to Z: 1252 needs Š and Ÿ, not ƒ, ª, or µ. The East Asian ones need their standard's first level: JIS X 0208's kana and level 1 kanji (932), GB 2312's level 1 hanzi (936), KS X 1001's 2,350 Hangul syllables (949), Big5's 5,401 frequently used hanzi (950), and every Hangul syllable (Johab, 1361). Macintosh Roman, the MS-DOS code pages, OEM, and Symbol are left as declared: few fonts declare them.
- **Win ascent and descent**: raised to the ink of a glyph the write drew above or below them, never lowered, and left unset where they are not set (0: a value made from a few glyphs would clip the others). Windows clips glyphs outside them, and uses them for line spacing in apps that ignore the typo metrics: a raise can open the lines up there.

Every other bit and value stays as declared, set by hand or not. The log says what changed (*Updated the font info to match: Unicode ranges (added Hangul Syllables); Win ascent (900 to 951).*). Font Builder sets a new font's names and metrics as before, and Font Check, CJK Vertical, and Family Audit write the font info as their own pages say.

*Edit > Undo* takes the Unicode ranges and code pages back with the write's glyphs, and *Redo* sets them again: FontLab keeps them with the font's encoding, which the write's History step records (found live). It does not take back the Win values, nor any other OS/2 metric. FreeLab keeps its Win raises for the session instead: when the History moves while a FreeLab window shows the font (an undo, a redo, or an edit in FontLab that adds or takes out glyphs), it puts each one back in step with the glyphs it was raised for, and says so in the log. A value changed by hand since is left as it is. An undo made with no FreeLab window open is followed at the next write that updates the font info.

The `meta` table's language tags (`dlng`, `slng`) are not written: FontLab 7 keeps no `meta` table for export (one added to the font was dropped from the exported file, live).

## A reinstall in the same session

Installing FreeLab again while FontLab runs replaces its scripts; windows opened before keep working on the copy they were opened with (it is kept for the session) until they are closed.
