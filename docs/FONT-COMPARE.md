# Font Compare

*Scripts > FreeLab > Font Compare* compares two open fonts, or two masters of one font, glyph by glyph: the glyphs only in one, names and code points, advance widths and sidebearings, outlines, components, anchors, kerning, and features. It answers a wish of FontLab's forum (*Font Comparison – A Proposal for FontLab 9*): to see at a glance what changed between two versions of a font, or between two weights of a family. It changes nothing in either font; its only action flags a glyph.

The window keeps the conventions of FreeLab's other dialogs and the look of the redesigned Font Check: a top line with the counts in bold, a settings row, a tab per view, chips that filter a list, a list of glyphs the worst first with small pictures, the selected glyph drawn large, grid lines, a log, a right-click to flag a glyph in FontLab (F3 and Shift+F3 go to the next and previous flagged row), a fresh comparison after an undo, a redo, or an edit in either font, and the dialog's ? button to explain any control. At 1000 by 1000 pixels nothing scrolls sideways.

## Choosing what to compare

*Compare* and *with* list every open font, and each master of a font with several (*Sans · Bold*). The current font's current master comes first; the second box starts on the next open font, or on the current font's next master when only one font is open. Choosing the same font and master in both says so. *Compare* runs the comparison (it also runs as the window opens when there are two things to compare).

In sentences and chips, the two sides go by their fonts' names (and their masters' when a font has several), by their masters' names when they are two masters of one font, by their files' names when two fonts share a name, and otherwise as *first* and *second*.

*Ignore differences up to [1] units*: widths, sidebearings, anchor and component positions, node moves, and kerning values that differ by at most this much count as alike. A font with another number of units per em is scaled to the first one's, and the top line says so.

Comparing a font with itself at another point of its History is out of scope: FontLab's API offers no way to read an earlier state.

## Glyphs

Glyphs are paired by name. A glyph left over in each font with a code point in common is paired too (*uni00E9* and *eacute*), when no other leftover glyph shares that code point; the pair then differs in its name. The kinds of difference, gravest first:

- **Only in one font**, or, for two masters, **no layer** in one master.
- **Outlines** (the glyph's own contours; components are compared on their own): the number of contours, the number of nodes, how far the node that moved most moved (when both have the same contour and node counts), and how much the shapes differ. The measure of shape is the area where one outline has ink and the other has not (the symmetric difference of the two filled outlines, overlapping contours counted once and counters left empty, as FontLab fills them), as a share of the larger outline's ink: 0% for the same shape, 100% where one has no ink, and up to 200% for two shapes that do not overlap at all (a mark moved away). A shape counts as changed past 0.2% of its ink, about what a node moved by 10 units on a 700-unit letter changes. When the nodes moved but the shape did not, and the nodes are the same in another order, the sentence says so (*the same nodes in another order (start points or contour order)*).
- **Components**: those only in one font (the second font's component names translated through the glyph pairs above), the same ones in another order, one moved (by its offset), and one scaled or turned.
- **Names and code points**: a glyph paired by its code point, and code points that differ.
- **Metrics**: the advance width, and the left and right sidebearings (the ink measured with components, as FontLab draws the glyph). A glyph with no ink compares its width only.
- **Anchors**: those only in one font, and those moved.

The view has three parts.

- **Chips**, at the top: one per kind with the number of glyphs that have it (*Only in Sans 3*, *Outlines 40*, *Metrics 12*), all shown to start. A chip shows or hides its kind of difference in the list: hidden, that kind leaves every row's short differences and the ranking, and a glyph left with no kind shown leaves the list; the line above the list names the kinds hidden. (Hiding only the glyphs that had nothing else hid nothing for *Metrics*: an outline or component change moves the sidebearings too, so nearly every glyph whose metrics differ differs otherwise as well.) A chip shown is filled in the highlight color, a chip hidden is a gray outline, drawn from the palette in light and dark mode alike.
- **The glyphs that differ**, at the left, the worst first: by the gravest kind each has, then by how much (the share of the shapes, the largest metric change), then by name. Each row has a small picture of the glyph from both fonts, the first in the text color and the second in the highlight color, see-through, its name (both names when they differ), and its differences in short (*outline 4.1% · width +20*). The tooltip has the whole sentence. At most 2,000 glyphs are listed, the worst; two weights of one family differ in nearly every glyph, and the chips narrow the list. A right-click flags the glyph in the first font.

There is no *Show in Glyph window* here (nor a double-click for it): FontLab opens a Glyph window on its current font only (FreeLab opens one through FontLab's *New Glyph Tab* command and `flItems.requestContent`, neither of which takes a font), so a glyph of the other font, or of a font that is not the current one, would show in the wrong font. Open the glyph from its own font's Font window.
- **The comparison**, at the right: the selected glyph at one scale in three panels, the first font's in the text color, both overlaid, and the second font's in the highlight color, with the baseline and each advance width drawn thin and dashed; a font without the glyph shows a dashed empty frame. Under it, its differences in one sentence: *a, Regular and Bold: the shapes differ by 4.1% of the ink; nodes moved up to 12 units (contour 2); width 520 and 540 (+20).*

## Kerning

Each master's kerning is read as FontLab applies it: `getPlainPairsDict()` resolves class kerning to glyph pairs (Auto Kerning's `FontKerning`). Where it is missing, the entries are resolved here the same way: the most specific entry wins, glyph and glyph, then glyph and class, then class and glyph, then class and class. Values are compared as applied, so a pair kerned 0 and a pair not kerned are alike, and a pair kerned by a class in one font and by its own entry in the other is alike when the values are.

Chips: *Only in* one font, the other font, *Other values*, and *Glyphs one font lacks* (pairs of a glyph that one font does not have, hidden to start with: they follow from the glyphs that differ). The list has the pair, its value in each font, and the second's minus the first's, the largest difference first; at most 2,000 pairs are listed. The selected pair is drawn in both fonts, each at its own value, one over the other.

## Features

The features are read from each font's feature code (`fgPackage.features`): the code before the features (*Prefix*), each feature, and the classes of FontLab's *Classes* panel (*Classes*, as code: `@name = [glyphs];`). Line ends, spaces at the ends of lines, and blank lines at the start and end are ignored. The list shows the features only in one font and those whose code differs (*2 lines only in Regular, 1 line only in Bold*); *Show the features that are alike* lists the others too. The selected feature's code is shown with the lines only in the first font on a red tint, after a minus, the lines only in the second on a green tint, after a plus, three unchanged lines around each change, and the rest left out (an ellipsis). FontLab writes the code it generates between `#> feature` and `#< feature`; that code is compared as any other.

Two masters of one font share their features and classes: the tab says so.

## What it does not compare

Font info (names, vertical metrics, and the rest), guides, hints, node smoothness, glyph flags, notes, and tags are not compared. Outlines are compared as drawn, not as they interpolate: Font Check's *Masters* view does that. A TrueType contour's two off-curve points in a row are read as a cubic curve, since FontLab's nodes say only *on* and *off*; both sides are read the same way, so the shape measure still compares like with like (on three corpus fonts read both ways, the same glyphs differed, and a glyph's measure moved by at most 8.4 percentage points).

## How it was checked

The comparisons (pairing glyphs, the shape measure, outlines, metrics, components, anchors, code points, the ranking, kerning resolved and compared, features compared line by line, and the colored code) sit above the Qt line and are unit tested under Python 3 and 2.7 (*tests/compare_tests.py*): areas are exact for straight edges (a corner moved 10 units on a square of 100 gives the 500 units of its triangle), counters and overlaps are filled as FontLab fills them, and a circle of four curves comes within 1% of π·r². The dialog is run on fakes of PythonQt and of FontLab fonts (two fonts with planted differences, and a font of two masters), which exercises its code paths but not Qt's or FontLab's answers.

On corpus fonts read with fontTools (open-licensed, checked as *kerning/train/dataset.py* checks them), with variable fonts instanced at their weight axis's ends:

- **EB Garamond** (3,247 glyphs, 400 and 800): 3,230 glyphs differ (outlines 1,216, components 1,304, metrics 3,200), compared in 2.0 s under Python 3 and 2.0 s under Python 2.7; its 31 features alike.
- **Noto Sans** (4,515 glyphs, 100 and 900): 4,253 differ (outlines 2,418), 2.4 s under Python 3 and 2.2 s under Python 2.7; its 36 features alike.
- **Cairo** (1,956 glyphs, 200 and 1000): 1,954 differ, 0.6 s.
- Each font against itself: no difference.
- Each font against a copy with six changes planted (a node moved by 10 units, an advance width by 12, a glyph removed, a glyph renamed, a contour's start point or the contours' order changed, a component moved by 15 units), two kerning changes, and two feature changes: every change found, and nothing else.

The pictures (the three-panel comparison, the small pictures, the colored code) were drawn offscreen under PySide6 (Qt 6), PythonQt's ways emulated, in light and dark palettes, and looked at; that harness is not in the repository. Reading glyphs through FontLab's objects adds its own time, as in Font Check's *Masters* view.

## FontLab calls not yet proven live

Proven before (see FreeLab MCP's *FONTLAB7-API.md* and Font Check's notes): `flWorkspace.instance().packages()` and `fontlab.flPackage(item)` for the open fonts, the current font, `fgPackage.glyphs` (`name`, `unicode`, `unicodes`), `findName`, `getLayerByName`, a layer's `shapes`, a shape's `contours` and `isComponent`, a contour's `nodes()` (a node's `x`, `y`, and `type`: *on* or *off*), `advanceWidth`, `masters`, `master`, `upm`, `tfn`, `kerning(master)` and `getPlainPairsDict()`, `fgPackage.features` (`keys()`, `get_feature`, `get_prefix`), the History state, and flags. To look at live: a component's `shape.transform` as its offset and scale (Font Check reads a shape's transform for its contours only), `shape.shapeData.componentGlyph` (Font Check uses it), a layer's `anchors` and an anchor's `point` (Diacritics reads them), `package.getAllGroups()` for the Classes panel's classes (documented, its feature classes with `kernGroup` false), and how long FontLab takes to hand over every node of two large fonts. Qt calls no FreeLab dialog used before, each guarded or plain Qt: `QComboBox.setSizeAdjustPolicy(AdjustToMinimumContentsLengthWithIcon)` and `setMinimumContentsLength`, `QSpinBox.setSuffix`, `QTabBar.setTabText`, `QTransform.scale` and `map` on a `QPainterPath`, rich text with a table and `pre` in a `QTextEdit`, and a stylesheet on each chip (`QToolButton` with `:checked` and `:hover`, and `palette(highlight)`, `palette(highlighted-text)`, and `palette(window-text)`).
