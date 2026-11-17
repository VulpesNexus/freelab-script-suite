# What every FreeLab window shares

## Layout

Every window reads the same way, top to bottom:

- **The top line**: the font and its master (`ak.font_named`: *Cardo, master Bold*, with the number of masters only when there are several), then what the tool found, in short; the tools menu, the arrows, and **?** at its right. Text about the results always sits here, under the font line, never under a row of buttons.
- **A line** that sets the top text apart from the rest (`ak.header_separator`), shown in every window, with or without a font.
- **The tabs** (if any), then **the options**, each run button (*Analyze*, *Check*, *Compare*, *Read sheets*, *Save template…*) at the end of the options it reads, never pushed to the window's right edge.
- **The lists and previews**: previews are captioned in a smaller, quieter type, and set apart from each other and from a reference beside them by thin lines; a section heading that follows a list on the same tab has a line above it. A list's dotted handle sits right under its frame.
- **The log**.
- **The bottom row**: at the left, what acts on the list's ticks and rows (*Tick all*, *Tick none*, *Tick high-value glyphs*, *Restore suggestions*, *Show in Glyph window*); at the right, the compile tick if any, the action that writes (*Build ticked glyphs*, *Apply ticked fixes*, *Update the code*), and *Close*. A tabbed window shows the shown tab's buttons there.

Check boxes are *ticked*: "check" is the verb of the tools that check a font (*Check* in Font Check, Kerning Check, and Feature Check). Captions take one of two forms: a noun and a colon (*Script: Latin*), or a sentence the controls finish, ending with its period (*List changes of at least 20 units.*). A caption is grayed with its control, and a right-click on it shows the control's help. Dropdowns are as wide as their widest choice. Counts group their thousands (*13,932 glyphs*); headers and tabs give theirs in parentheses (*Glyphs (13,956)*). A log names another tool as a link that opens it in the window's place.

## Long work

A step that takes a while (reading a font, measuring, listing, checking, writing) shows its name and a green bar in the window's top row, between the window's left edge and its **?** button. The window keeps repainting meanwhile, so Windows never marks it *Not Responding*.

While it runs, clicks, keys, and the wheel wait, in the window and in FontLab: nothing may change what the work is reading. A few controls stay usable:

- the tools menu (**≡**) and the **‹ ›** arrows,
- **Close** and the title bar's **✕**,
- **Esc**.

Each one stops the work at its next step: the tool sets aside what it was doing, then does what was clicked (opens the other tool, closes the window) or, for Esc, simply stops. A write to the font is never stopped half way: it ends as one step of FontLab's History, and the click is done after it.

FreeLab's scripts run inside FontLab, in its own thread. If Windows ever offers to end a window that is not responding, it would end FontLab with it: the bar and the stop above exist so that this never has to happen.

## With no font

A window with no font open says so on its first line, *No font is open. This window hooks to the next font you open.* (with Proof's and Font Builder's own no-font lines, the only sentences FreeLab puts on one line). Its controls are grayed until a font comes, all but the tools menu, the arrows, help, Close, and what a tool can do without a font (Font Builder's template, Font Compare's choice of fonts); they are grayed before the window first shows, so nothing flashes usable. The line under the top text stays; the other lines, which set apart parts that are empty, are hidden. An empty status line takes no room. A window with no font opens at the size every tool opens at, and one that opens wider for its content (Font Check) widens once it hooks to a font.

## Lists

A list's columns share its width; drag a column's edge to give it more, and the last column stays at the frame's edge while you drag. A column cannot be made narrower than 24 pixels, so it never disappears, and a column dragged wider stops where the columns after it reach their least (their header's text): it never pushes them past the frame. A list with no rows shows no scroll bars. A dropdown with more choices than fit opens as a scrolled list, with a scroll bar.

## A reinstall in the same session

Installing FreeLab again while FontLab runs replaces its scripts; windows opened before keep working on the copy they were opened with (it is kept for the session) until they are closed.
