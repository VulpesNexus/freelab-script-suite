# Feature survey

What already exists for the features the owner asked for, surveyed on 2026-11-06 before anything was built. A research agent did the survey; the licenses and activity dates of the repositories below, TypeRig's tags, and the FontLab 7 calls named here were checked again against GitHub and FontLab's FontLab 7 reference. The judgments about how good each tool is come from forum posts and manuals, and are marked where unverified.

## Dark mode

No FontLab 7 build has one. Users asked for it on FontLab's forum in [2020](https://forum.fontlab.com/fontlab-7/dark-mode/) and [2021](https://forum.fontlab.com/fontlab-7/dark-mode-13426/); it arrived in [FontLab 8](https://help.fontlab.com/fontlab/8/tutorials/calfonts/0.%20Installation%20and%20Set%20Up/00c%20FontLab%208%20New%20Dark%20Theme/), which follows the Windows setting. FontLab 7.2 is built on Qt 5.14.2, which predates Qt's own Windows dark-mode switch (5.15), but the Fusion style is compiled into its *Qt5Widgets.dll*, and FontLab runs a user startup script (*%LOCALAPPDATA%\FontLab\FontLab 7\startupScript.py*) at launch. A FreeLab theme can therefore switch the application to Fusion with a dark palette and add a stylesheet, once FontLab 7's Python works ([PYTHON27.md](PYTHON27.md)). Canvas colors that FontLab paints itself are set in its *Preferences* and need a separate look. Built since: [DARKMODE.md](DARKMODE.md) describes what it took.

## Automated kerning

FontLab 7 has a basic built-in autokern for selected pairs. Its managing director called it "basic autokerning for the current pair" in 2019 ([forum](https://forum.fontlab.com/fontlab-7/upgraded-from-studio-5-really-loving-7-question/msg43706/)). It is not reachable from Python, as far as the reference shows.

| Prior art | License | Notes |
|---|---|---|
| [mekkablue/Glyphs-Scripts](https://github.com/mekkablue/Glyphs-Scripts) "Auto Bumper" | Apache-2.0 | minimum-distance kerning for Glyphs; logic portable |
| [Tosche/BubbleKern](https://github.com/Tosche/BubbleKern) | Apache-2.0 | bubble-distance kerning for Glyphs; logic portable |
| [simoncozens/kerndeterminer](https://github.com/simoncozens/kerndeterminer) | MIT and Apache-2.0 | Rust with Python bindings; warns it does not suit Latin |
| [simoncozens/atokern](https://github.com/simoncozens/atokern) | none on GitHub | neural kerner; do not copy |
| [HTLetterspacer](https://github.com/huertatipografica/HTLetterspacer), kernagic, FittingRoom | GPL-3.0 | read only, unless FreeLab becomes GPL |
| Kern On, iKern | commercial | Glyphs-only and a paid service |

A FreeLab kerner would be its own: a minimum-distance or bubble model over outlines, read through the listener and written with FontLab's kerning API.

## Kerning pairs and classes

FontLab 7 loads pair lists in its *Pairs & Phrases* panel and has *Font > Kerning > Generate Kerning Classes*, reported to leave glyphs out ([forum, unverified](https://forum.fontlab.com/fontlab-7/auto-generate-kerning-classes-omits-some-glyphs-it-perhaps-shouldn't/)).

| Prior art | License | Notes |
|---|---|---|
| [andre-fuchs/kerning-pairs](https://github.com/andre-fuchs/kerning-pairs) | MIT | ranked Latin pair lists for 24 languages; shippable as data |
| [kateliev/TypeRig](https://github.com/kateliev/TypeRig) at tag `v1.9.0-Py2.7` (or `v1.5.0-py27`) | MPL-2.0 | FontLab 7 era: pair strings and export, class building from composites and name suffixes; reusable with file-level copyleft |
| mekkablue Kerning scripts | Apache-2.0 | group setting, string mixers, crash finders; logic portable |

FontLab 7's `flPackage.getAllGroups()` and `flPackage.kerning(master)` are the calls to build on.

## Diacritic variants

Built in and scriptable. *Font > Generate Glyphs* builds accented glyphs from recipes and anchors, and FontLab 7's Python has `flPackage.generateGlyph(recipe, layer_name, metrics, rtl)` and `flLayer.setGlyphComponents(...)`, both in its reference. [typemytype/GlyphConstruction](https://github.com/typemytype/GlyphConstruction) (MIT) parses the full recipe syntax and needs only fontTools, which FontLab 7 bundles. The work for FreeLab is anchor auditing and per-master checks around FontLab's builder, not a new builder.

## Ligature and discretionary feature code

FontLab 7's auto features already write `liga` and `dlig` from glyph names (for example `f_f_i`, and names with a `.liga` or `.dlig` suffix) between `#>` and `#<` markers, keeping code outside them; this was reported by the survey from FontLab's manual and not checked on this machine. No Python call to trigger it was found. FontLab 7's `fgFont.features` (`fgOTLayout`) has `keys()`, `get_feature(tag)`, and `set_feature(tag, text)`, so FreeLab can generate the code itself and write it. Prior art: tphinney's `Generate-substitutions.py` (Apache-2.0, FontLab Studio 5) and mekkablue's feature scripts (Apache-2.0).

## Licensing

Reusable: MIT, Apache-2.0, and BSD code, with notices kept. MPL-2.0 (TypeRig): reusable, and modified TypeRig files stay MPL. GPL-3.0: read only. No license: never copied.
