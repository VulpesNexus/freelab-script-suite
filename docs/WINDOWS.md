# What every FreeLab window shares

## Long work

A step that takes a while (reading a font, measuring, listing, checking, writing) shows its name and a green bar in the window's top row, between the window's left edge and its **?** button. The window keeps repainting meanwhile, so Windows never marks it *Not Responding*.

While it runs, clicks, keys, and the wheel wait, in the window and in FontLab: nothing may change what the work is reading. A few controls stay usable:

- the tools menu (**≡**) and the **‹ ›** arrows,
- **Close** and the title bar's **✕**,
- **Esc**.

Each one stops the work at its next step: the tool sets aside what it was doing, then does what was clicked (opens the other tool, closes the window) or, for Esc, simply stops. A write to the font is never stopped half way: it ends as one step of FontLab's History, and the click is done after it.

FreeLab's scripts run inside FontLab, in its own thread. If Windows ever offers to end a window that is not responding, it would end FontLab with it: the bar and the stop above exist so that this never has to happen.

## With no font

A window with no font open says so on its first line, *No font is open. This window takes the next font you open.* (the only two sentences FreeLab ever puts on one line). Its controls are grayed until a font comes, all but the tools menu, the arrows, help, Close, and what a tool can do without a font (Font Builder's template, Font Compare's choice of fonts). The lines that set the top text apart from the fields are hidden: there is nothing under them to set apart. An empty status line takes no room.

## Lists

A list's columns share its width; drag a column's edge to give it more, and the last column stays at the frame's edge while you drag. A column cannot be made narrower than 24 pixels, so it never disappears. A list with no rows shows no scroll bars. A dropdown with more choices than fit opens as a scrolled list, with a scroll bar.

## A reinstall in the same session

Installing FreeLab again while FontLab runs replaces its scripts; windows opened before keep working on the copy they were opened with (it is kept for the session) until they are closed.
