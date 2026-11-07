# Auto kerning

*Scripts > FreeLab > Auto Kerning* suggests kerning for the Latin pairs of the font's current master, lists each suggestion beside the kerning the font has, and writes only the pairs you leave checked.

## Using it

1. Open the font, and pick the master to kern.
2. Click *Analyze*. Every pair of the Latin letters, figures, and punctuation the font has is measured (two marks of punctuation side by side are skipped); about 6,600 pairs take three to four seconds.
3. The list shows the pairs whose suggestion differs from the current kerning by at least the given number of units (20 by default), largest first. *Show* narrows it to letters, letters and punctuation, figures, or everything. Selecting a pair draws it between two H's as it is set now and as suggested.
4. Uncheck what you disagree with, and click *Write checked pairs*: each is written to the master as a pair of glyphs (a suggestion of 0 removes the pair).

Kerning the font already has counts as your models: with at least three tightenings in it, suggestions are scaled to match how strongly you tighten (and the same for loosenings). Without them, tightenings are applied at half strength, as halfkern applies them.

## How it measures

The method is [halfkern](https://github.com/behdad/halfkern)'s (Copyright 2022 Google LLC, Apache License 2.0), measured by FreeLab's own native core (*kerning/native/freelab_kern.c*):

- Each glyph is rendered from FontLab's outlines at 200 pixels per em (halfkern renders at 100), and gets an envelope: its ink, over a halo that fades out over about a tenth of the em, at half strength.
- Two glyphs set side by side overlap in their halos. The overlap of a pair, the sum of the squared products of the two envelopes, is held within a band taken from pairs the designer spaced on purpose: halfkern takes it from *ll*, *nn*, and *oo*, and the halo grows until those three agree within a factor of two. A pair is moved a pixel at a time until its overlap enters the band; FreeLab then interpolates where it crosses, for values finer than a pixel.
- FreeLab gives each kind of pair its own band: capitals from *HH*, *HO*, *OH*, and *OO*; lowercase from *ll*, *nn*, and *oo*; figures from *0* and *8*; pairs across cases from the references of both sides; punctuation takes the band of the letter beside it. A single lowercase band, as halfkern has, loosened straight capitals (*HH*, *MN*) that the designer had spaced as wanted.

The core was checked against halfkern itself on the same renderings (Georgia, 19 pairs): the same kerning for every pair, including the two it cannot kern. The envelopes differ by about 1.5 levels in 255, from an exact Euclidean distance transform where halfkern uses fast marching.

## Limits

- Kerning classes are not read or written yet: every suggestion is a pair of glyphs. A font with kerning classes gets glyph pairs, which override its classes.
- Latin only. Japanese kana are spaced with `palt` more than with pairs ([FEATURE-SURVEY.md](FEATURE-SURVEY.md)); they come next.
- The method has blind spots of its own: halfkern loosens *Ty* in Georgia, where the T's bar meets the y's arms, and cannot kern *VA* there. Review before writing.
