# Feature survey

What already exists for the features the owner asked for, surveyed on 2026-11-06 before anything was built, and again for kerning on 2026-11-08. A research agent did the survey; the licenses and activity dates of the repositories below, TypeRig's tags, and the FontLab 7 calls named here were checked again against GitHub and FontLab's FontLab 7 reference. The judgments about how good each tool is come from forum posts and manuals, and are marked where unverified.

## Dark mode

No FontLab 7 build has one. Users asked for it on FontLab's forum in [2020](https://forum.fontlab.com/fontlab-7/dark-mode/) and [2021](https://forum.fontlab.com/fontlab-7/dark-mode-13426/); it arrived in [FontLab 8](https://help.fontlab.com/fontlab/8/tutorials/calfonts/0.%20Installation%20and%20Set%20Up/00c%20FontLab%208%20New%20Dark%20Theme/), which follows the Windows setting. FontLab 7.2 is built on Qt 5.14.2, which predates Qt's own Windows dark-mode switch (5.15), but the Fusion style is compiled into its *Qt5Widgets.dll*, and FontLab runs a user startup script (*%LOCALAPPDATA%\FontLab\FontLab 7\startupScript.py*) at launch. A FreeLab theme can therefore switch the application to Fusion with a dark palette and add a stylesheet, once FontLab 7's Python works ([PYTHON27.md](PYTHON27.md)). Canvas colors that FontLab paints itself are set in its *Preferences* and need a separate look. Built since: [DARKMODE.md](DARKMODE.md) describes what it took.

## Automated kerning

FontLab 7 has a basic built-in autokern for selected pairs. Its managing director called it "basic autokerning for the current pair" in 2019 ([forum](https://forum.fontlab.com/fontlab-7/upgraded-from-studio-5-really-loving-7-question/msg43706/)). Python reaches it as `flPackage.autoKern(left, right, master)`, which returns its suggestion without writing it (below).

| Prior art | License | Notes |
|---|---|---|
| [behdad/halfkern](https://github.com/behdad/halfkern) | Apache-2.0 (Google, 2022) | "essentially a font auto-kerning tool masqueraded as a kerning audit tool": blurs the two glyphs' renderings (a signed distance field by default) and spaces them until the blurs overlap by an amount calibrated on *ll*, *nn*, and *oo*; prints suggested values and does not write them into the font. Python 3 with numpy, scipy, cairo, FreeType, and HarfBuzz; last commit June 2024 |
| [mekkablue/Glyphs-Scripts](https://github.com/mekkablue/Glyphs-Scripts) "Auto Bumper" | Apache-2.0 | minimum-distance kerning for Glyphs; logic portable |
| [Tosche/BubbleKern](https://github.com/Tosche/BubbleKern) | Apache-2.0 | bubble-distance kerning for Glyphs; logic portable |
| [simoncozens/kerndeterminer](https://github.com/simoncozens/kerndeterminer) | MIT and Apache-2.0 | Rust with Python bindings; warns it does not suit Latin |
| [simoncozens/atokern](https://github.com/simoncozens/atokern) | none on GitHub | neural kerner; do not copy |
| "Learning to Kern" ([arXiv 2402.14313](https://arxiv.org/abs/2402.14313), Kyushu University, 2024) | paper; no code found | pairwise and set-wise (transformer) models over letter images, about 5.3 px average error on about 2,500 Google Fonts; compared against FontForge's autokern |
| [HTLetterspacer](https://github.com/huertatipografica/HTLetterspacer), kernagic, FittingRoom | GPL-3.0 | usable: FreeLab is GPL-3.0-or-later |
| Kern On, iKern | commercial | Glyphs-only and a paid service. Kern On works from a few "model" pairs the designer kerns, and compares glyphs and pairs to kern the rest ([manual](https://kern-on.com/manual)) |
| FontLab 8 | commercial | a newer autokern algorithm (K2, beside the old K1), *Kern to Distance* (the pair's closest contours at a given distance), and automatic kerning classes ([FontLab 8 help](https://help.fontlab.com/fontlab/8/whats-new/whats-new-06-metrics-kerning/)); no internals published |

A FreeLab kerner would be its own: a minimum-distance or bubble model over outlines, run inside FontLab, reading outlines and writing kerning through FontLab's own API. halfkern's approach (blurred shapes, overlap calibrated on the font's own *ll*, *nn*, and *oo*) is the most promising open method, and its Apache license allows porting it; FontLab 7's Python has no numpy, so its heavy part would go into FreeLab's native helper (C), as dark mode's pixel work does.

**Optical kerning (2026-11-08).** Adobe's *Optical* kerning (InDesign, Illustrator) is not described anywhere public; forum claims that it descends from URW's or iKern's work are unverified. Methods that are public, and their standing:

| Method | Standing | How it measures |
|---|---|---|
| FontLab 7's own autokern (`flPackage.autoKern(left, right, master)`) | built in | returns its suggestion as text (−29 for *To* on the owner's test font) without writing it; the "K1" of FontLab 8 |
| Neville and Fox, [US 5,803,629](https://patents.google.com/patent/US5803629) (1997) | patent expired 2017: free to implement | each outline sampled at 100 heights; the gaps between the facing intercepts, filtered to the nearer ones (a 33% or 78% cut), set the spacing from their mean less their standard deviation |
| Karow and MacMillan (Adobe), [US 6,624,814](https://patents.google.com/patent/US6624814) | expired 2016 | optical margins and size-dependent metrics; its kerning values come from Karow's automatic method, EP 0 465 704 (URW, 1991, expired) |
| Refstrup and others (Apple), [US 9,208,589](https://patents.google.com/patent/US9208589) | **active until 2033: not to be implemented** | the closest distance between the facing edges, kept above a threshold |
| Tsukurimashou (Matthew Skala), [described on freetype-devel, 2012](https://lists.nongnu.org/archive/html/freetype-devel/2012-06/msg00118.html) | method public (the code is GPL: implemented from the description only) | the average inverse cube of the distances between the two glyphs' facing contours, whose angles are limited (a period cannot slide under an apostrophe), kerned to a constant; tuned separately for Latin, Japanese, and Korean |
| FontForge's optical separation ([old manual](https://fontforge.org/archive/autowidth.html)) | method public (code GPL) | gaps at heights a hundredth of the em apart where both glyphs have ink, averaged with weights 1 / (gap + em/50)²; "handwaving", by its own account |
| [Coupler](https://jrgdrs.github.io/Coupler) | no license: ideas only | 16 horizontal zones, facing margins averaged per pair against the *oo* (or *OO*) baseline, smoothed; a minimum ink gap |
| iKern (Igino Marini) | commercial; theory described, algorithms unpublished | a model of the interaction between shapes |

**Japanese.** Kana and punctuation in Japanese fonts are spaced with `palt` (proportional widths, a GPOS single adjustment) more than with pairs; layout engines apply `palt` first and kerning on top of it ([W3C discussion, 2023](https://lists.w3.org/Archives/Public/public-i18n-japanese/2023AprJun/0048.html)). No open tool that generates `palt` values automatically was found; [Gen Interface JP](https://github.com/yamatoiizuka/gen-interface-jp) sets them by hand for 48 punctuation glyphs.

## Kerning pairs and classes

FontLab 7 loads pair lists in its *Pairs & Phrases* panel and has *Font > Kerning > Generate Kerning Classes*, reported to leave glyphs out ([forum, unverified](https://forum.fontlab.com/fontlab-7/auto-generate-kerning-classes-omits-some-glyphs-it-perhaps-shouldn't/)).

| Prior art | License | Notes |
|---|---|---|
| [andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs) | MIT | ranked Latin pair lists for 24 languages; shippable as data |
| [kateliev/TypeRig](https://github.com/kateliev/TypeRig) at tag `v1.9.0-Py2.7` (or `v1.5.0-py27`) | MPL-2.0 for those tags; AGPL-3.0 since 5 November 2026 | FontLab 7 era: pair strings and export, class building from composites and name suffixes. Its NOTICE now reserves text and data mining, AI training included: not to be fed to AI tools, so not used here |
| mekkablue Kerning scripts | Apache-2.0 | group setting, string mixers, crash finders; logic portable |

FontLab 7's `flPackage.getAllGroups()` and `flPackage.kerning(master)` are the calls to build on.

## Diacritic variants

Built in and scriptable. *Font > Generate Glyphs* builds accented glyphs from recipes and anchors, and FontLab 7's Python has `flPackage.generateGlyph(recipe, layer_name, metrics, rtl)` and `flLayer.setGlyphComponents(...)`, both in its reference. [typemytype/GlyphConstruction](https://github.com/typemytype/GlyphConstruction) (MIT) parses the full recipe syntax and needs only fontTools, which FontLab 7 bundles. The work for FreeLab is anchor auditing and per-master checks around FontLab's builder, not a new builder.

## Ligature and discretionary feature code

FontLab 7's auto features already write `liga` and `dlig` from glyph names (for example `f_f_i`, and names with a `.liga` or `.dlig` suffix) between `#>` and `#<` markers, keeping code outside them; this was reported by the survey from FontLab's manual and not checked on this machine. No Python call to trigger it was found. FontLab 7's `fgFont.features` (`fgOTLayout`) has `keys()`, `get_feature(tag)`, and `set_feature(tag, text)`, so FreeLab can generate the code itself and write it. Prior art: tphinney's *Generate-substitutions.py* (Apache-2.0, FontLab Studio 5) and mekkablue's feature scripts (Apache-2.0).

Contextual alternates for handwriting (surveyed 2026-11-09): FontLab 7's auto features write no `calt` (its [release notes](https://help.fontlab.com/fontlab/7/manual/Release-Notes-7264-4/) list the suffix rules: `.alt1` lands in `ss01`), so cycling alternates is hand-written code. Known techniques: Tal Leming's [OpenType Cookbook](https://opentypecookbook.com/common-techniques/) (endless cycle, duplicate eliminator, quantum; no license stated, ideas only), Glyphs' [DEFAULT, ALT1, ALT2 classes](https://glyphsapp.com/learn/features-part-3-advanced-contextual-alternates), Underware's [Liza Pro](https://underware.nl/case-studies/random-vs-clever) (a rotator and a swapper looking back along the line), and mekkablue's *Create Pseudorandom calt Feature* (Apache-2.0). Large `calt` code can overflow a lookup's 16-bit offsets ([Simon Cozens](https://simoncozens.github.io/gsub-overflow)).

## Quality checks

Surveyed on 2026-11-09 by a research agent; the claims below are from FontLab's manual and forum, linked.

FontLab 7's FontAudit ([manual](https://help.fontlab.com/fontlab/7/manual/FontAudit/), [panel](https://help.fontlab.com/fontlab/7/manual/FontAudit-panel/)) checks outlines only: missing extremes, flat curves, collinear handles, inflections, semi-horizontal and semi-vertical vectors, short segments, and the like. It flags them on the contour in the Glyph window and lists them in a panel with Fix buttons, for the current glyph. Across the font, *Check Glyphs* marks each problem glyph's cell with a small red triangle; there is no font-wide list with pictures, and selecting the flagged glyphs was still a user request in [2022](https://forum.fontlab.com/fontlab-8/selecting-the-font-audit-marked-glyphs/) and [2024](https://forum.fontlab.com/fontlab-8/feature-suggestion-select-glyphs-with-fontaudit-problems/). It does not check vertical metrics, language coverage, accented glyphs against their base's sidebearings, figure widths, or kerning collisions (FontLab 8's *Audit Exceptions* does the last).

| Prior art | License | What to learn from it |
|---|---|---|
| [jenskutilek/RedArrow-Glyphs](https://github.com/jenskutilek/RedArrow-Glyphs) | none shown | arrows on the outline, and *Select Glyphs With Outline Errors* to open them in a tab |
| [typesupply/glyph-nanny](https://github.com/typesupply/glyph-nanny) | MIT | a live report while drawing; stray points, crossed handles, stems against stem snaps |
| [mekkablue/Glyphs-Scripts](https://github.com/mekkablue/Glyphs-Scripts) finders | Apache-2.0 | each check opens its glyphs in a tab: path, component, spacing, tabular, composite consistency |
| [fonttools/fontbakery](https://github.com/fonttools/fontbakery) | Apache-2.0 | an HTML report on the compiled font, each check with its rationale |

## Proofing

| Prior art | License | What it shows |
|---|---|---|
| [adobe-type-tools/drawBotProofing](https://github.com/adobe-type-tools/drawBotProofing) | MIT | one PDF proof per question: glyph grids, figure spacing, vertical metrics, accents in words, spacing strings, waterfalls, overlays of fonts |
| [silnrsi/fontproof](https://github.com/silnrsi/fontproof) | MIT | PDF waterfalls, Unicode charts, feature on/off comparisons, preset spacing and kerning texts |
| [impallari/Font-Testing-Page](https://github.com/impallari/Font-Testing-Page) | MIT (texts CC BY-SA 3.0) | an HTML page to drop a font on: sizes, Adhesion text, kerning, diacritics of 103 languages |
| Adhesion Text ([Typographica](https://typographica.org/?p=3760)) | idea | real words made only of the letters drawn so far |
| [hoeflerco/proofs](https://github.com/hoeflerco/proofs) | CC BY-NC-SA 4.0 | texts that isolate each letter's shape and fit; non-commercial, so not shipped with FreeLab |
| [googlefonts/diffenator2](https://github.com/googlefonts/diffenator2) | Apache-2.0 | HTML proofs, and words set in two versions of a font with their differences |

## Licensing

Reusable: MIT, Apache-2.0, BSD, and GPL-3.0 code (FreeLab is GPL-3.0-or-later), with notices kept. AGPL-3.0: read only. No license: never copied. A work whose rightholders reserve text and data mining (TypeRig's NOTICE): not processed with AI tools at all.
