# Proof

*Scripts > FreeLab > Proof* makes a PDF proof of the current font, drawn from the font's own outlines in FontLab: nothing is exported or installed, and the font is not changed. FontLab 9 has a *Notepad* panel for specimens and PDF proofs; FontLab 7 has none.

## What a proof holds

The first page says what the proof is: the font, its glyph and master counts, the kerned pairs in each master, and what is applied. The font's info follows on it (on the next page when it does not fit): its family, style, and full names, version, designer, manufacturer, vendor ID, copyright, trademark, license (with its URL), description, the designer's and the manufacturer's URLs, the dates it was created and last modified, its units per em, and its masters, each as FontLab's font info gives it, empty ones left out, and a long one (a license's whole text) cut at 1,200 characters. It comes first, with the about block, because a printed proof is passed around and compared: the reader checks which font and which version they hold before judging a glyph. Then, for the current master or for each master in turn (each starting on a new page, after a page of the masters side by side), the sections you check:

- **Character set**: every glyph in a grid of ten columns, in the font's order, each with its name and code point. A glyph wider than its cell is drawn smaller; a glyph with no layer in the master says so.
- **Waterfall**: a line of sample text at each size typed (8 to 72 points by default), cut at the page's edge.
- **Text**: a few lines of sample text in each script the font covers, at each text size typed (9, 11, and 14 points by default). See [Sample text](#sample-text).
- **Kerning strings**: every kerned pair (or only the pairs common in text), grouped by left glyph, each between control letters: two straight letters of the left glyph's kind before the pair, a straight and a round one of the right glyph's kind twice after it (*HHTAHOHO*, *HHTonono*, *nnr,nono*). Punctuation takes its partner's kind.
- **Spacing strings**: each encoded letter and figure of the Latin, Greek, Cyrillic, Armenian, Georgian, Hebrew, and kana scripts as *HHxHOxOO* or *nnxnoxoo*, with the control letters of its script and case, set without kerning: the sidebearings alone. Modifier letters (superscript and subscript letters) are left out.
- **Diacritics**: the letters with marks, each group after the letter it is built on (*Á* after *A*, *ł* after *l*, by Unicode's decomposition or name), then the combining marks (on the dotted circle when the font has one) and the spacing accents.
- **Figures and punctuation**: the figures, their alternates (*zero.osf*, *one.tf*, and so on, a row per suffix), the figures between *H*s and between *n*s, fractions and superiors, the punctuation alone and between letters, and the symbols.

Each page has a header (the font's name, the master, the date) and a footer (its sections, what is applied, and *Page n of m*).

The control letters are a straight and a round letter per script and case: *H* and *O*, *n* and *o* for Latin; Eta and Omicron, nu and omicron for Greek; En and O for Cyrillic; Ho and Oh, now and oh for Armenian; in and on for Georgian; he and samekh for Hebrew; ro and no for kana; *H* and zero for figures. Where the font lacks a script's controls, Latin's stand in, and where it lacks those too, each letter stands alone.

## What is applied

- **Kerning: yes**, as FontLab applies it, classes resolved (FontLab's own resolution, which Kerning Check reads too). Where FontLab does not resolve the classes, only pairs of glyphs are applied, and the log says so.
- **OpenType features: no.** No ligatures, no contextual or localized forms, no mark positioning, no small caps or figure styles: each character shows its own glyph, as the font maps it. Alternates still show in the character set and among the figures by their names.
- **Scripts that need shaping get no text**: Arabic, the Indic scripts, Thai, and the like need joining, reordering, or mark positioning. The first page, the text section, and the window's top line name the ones left out. Their glyphs still show in the character set.
- **Right to left**: Hebrew text is set right to left, flush right. Kerning strings are set as the pairs are seen, left glyph then right glyph, as FontLab lists them.

## Sample text

The text section reads Font Check's language data (*language_coverage.json*, from [Hyperglot](https://github.com/rosettatype/hyperglot)): a language counts as covered when the font has every one of its base characters. For each covered language with a sample below whose every character the font has, its sample is used, the most spoken six per script first; a script with no sample that fits shows the letters of the language it covers best instead (up to 120 of them; the CJK ideographs once, though Japanese, Chinese, and Korean list them each).

The samples are pangrams written for FreeLab, GPL-3 with the code, for Spanish, Portuguese, German, French, Italian, Turkish, Polish, Dutch, Romanian, Hungarian, Czech, Swedish, Icelandic, Danish, Croatian, Catalan, Lithuanian, Russian, Ukrainian, Greek, Armenian, Hebrew, and Korean, and three texts in the public domain: the English pangram (in print since 1885), the opening line of Nguyễn Du's *Truyện Kiều* (1820) for Vietnamese, and the Iroha (11th century) for Japanese, in hiragana and in katakana. The traditional pangrams of the other languages were replaced because their origins are unclear. Each of FreeLab's pangrams is a sentence a reader of the language finds plausible and holds every base letter Hyperglot lists for its language, accented ones included; letters a language writes only in foreign words come in names and loanwords (*Quentin*, *whisky*, *Wi-Fi*). *tests/proof_tests.py* checks each one and lists any letter missing, with two exceptions: Hyperglot lists the Russian *э* for Ukrainian, which never writes it, and Hebrew's pointed letters (with a dagesh or a shin dot) count by their letter, since the proof does not position marks. Korean's is checked for its 14 basic consonants and 10 basic vowels. Only letters of the language and common punctuation appear, so a font that covers the language and has the punctuation sets it. The waterfall sets the first script's text.

## The window

The top line names the font, the master, the page count and size, the pages per section, the kerned pairs, and what is applied. Under it: *Masters* (the current master, or all of them), *Page* (A4 or US Letter, portrait), *Kerning strings for* (every kerned pair, or the pairs common in text that Auto Kerning's *Common pairs* lists), *Proof* (*Every script*; one script the font has letters of, with the figures, punctuation, and symbols; or, after the line, one language the font covers, with its base and auxiliary letters, whose sample the text section then shows alone), *Colors* (*As the window*: the PDF in the window's text and background colors, light on dark in dark mode; then the other of the two: *Print (black on white)* beside a dark window, *Dark (white on black)* beside a light one), a check box per section, and the waterfall and text sizes (typed in points, separated by spaces or commas). The proof is laid out again as any of them changes, and after an undo, a redo, or an edit in FontLab.

The list on the left shows the pages; the selected page is drawn beside it as the PDF will be, in the colors *Colors* says, the whole page as large as the room allows (drag the line beside the list, or make the window larger) and drawn at the display's own resolution, so it stays sharp on a scaled display. *Show in Glyph window* (or a double-click on a page) opens the page's lines of glyphs in a FontLab Glyph window. *Restore defaults* puts the settings back. *Save PDF…* writes every page to a file you name, in *Documents* at first and then where you saved last, named after the font, the master, and the date; *Open PDF* then opens it in the application Windows opens PDF files with; once the file is moved or deleted, the log says it is not there anymore and the button grays out (looked for again as the window is activated).

## How it works

The proof is laid out in points by pure code (*proof/freelab_proof.py*, above its Qt line, tested by *tests/proof_tests.py* under Python 3 and 2.7): glyph names with their advance widths and kerning, lines broken to the page's width (at spaces, or between any two characters in Japanese and in a script's letters), pages filled in turn, and headers and footers added once the page count is known. Each page is a list of items: lines of glyphs, text, rules, and cell frames. A renderer draws them with a QPainter, each glyph's outline as a vector path (from FontLab's layers, through Auto Kerning's `layer_path`), into a `QPdfWriter` at 600 dots per inch (each page filled with the background color first, unless it is white) or into the preview's pixmap. The renderer takes Qt's modules as arguments, so the same code draws in FontLab (PythonQt) and offline (PySide6, with fontTools pens and HarfBuzz for the kerning), which is how its sample PDFs were checked.

## Limits

- A font with tens of thousands of class-kerned pairs makes a long PDF: each glyph is drawn as its own path. *Common pairs only* keeps it short.
- Line metrics come from the current master's ascender and descender, for every master.
- Combining marks are not positioned (no mark feature): a mark sits where its outline is drawn, after the glyph before it.
- The preview draws one page at a time; the PDF has them all.
- The font info is read by the names FontLab's font info is expected to use (UFO's: *familyName*, *versionMajor*, *openTypeNameDesigner*, and so on), each tried in turn; a field FontLab names otherwise is left out, as an empty one is.
