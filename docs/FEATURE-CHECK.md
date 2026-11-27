# Feature check

*Scripts > FreeLab > Feature Check* checks the current font's OpenType feature code, whatever made it (FreeLab, FontLab's automatic features, another app, or a hand), and lists what it finds for review. It reads the code as FontLab compiles it: the feature classes of FontLab's *Classes* panel, then the prefix, then each feature in the *Features* panel's order.

## The window

The top line names the font, in bold, and counts its glyphs, thousands grouped (**BIZ UDGothic** (**13,932 glyphs**)). The check's result goes right under it, above the header's line: its counts of errors, warnings, and pieces of advice in bold, or that it found nothing. Under the line, the *Apply safe fixes automatically* option, then *Check*, which checks again. The bottom row holds *Tick all* and *Untick all* at the left, and *Compile in FontLab*, *Apply ticked fixes*, *Cancel*, and *Close* at the right. *Compile in FontLab* is grayed while the font has no feature code (or the window has no font), and *Apply ticked fixes* while nothing is ticked.

## What it finds

Findings are grouped by kind, errors first. A group's tooltip says what its kind means.

**Errors** (nothing of the font's features compiles until they are mended):

- **Syntax errors**: code the compiler cannot read. Each feature is read after the parts before it that read well, so one feature's error does not hide another's.
- **Glyphs not in the font**: every glyph name the font lacks, once, with how many times the code names it.
- **Rules the compiler refuses**: code that reads well but does not compile (a feature referred to and never defined, a `featureNames` block outside a stylistic set, two rule types in one named lookup). After each, the feature is set aside and the rest compiled again, so the list holds them all, up to 24.
- **Lookups inside aalt**: FontLab writes the lookups of `aalt` inside the feature when it opens some fonts; neither its own compiler nor fontTools takes a lookup there, so no feature compiles. The fix writes their rules straight into `aalt`, which both take.
- **Tables too large**: a layout table whose offsets overflow, even split up.
- **Lookup flags without their class**: a `lookupflag` that sets UseMarkFilteringSet (16) or a mark attachment type without naming the class it needs. FontLab writes these when it opens some fonts (`lookupflag 16;`, 29 times in Amiri); fontTools refuses them, and the lookup's marks are not filtered as meant. Name the class (`lookupflag UseMarkFilteringSet @marks;`) or drop the flag. The rest of the code is compiled as if the flag were not set, so they hide no other error. Each has a fix to review, never applied automatically: the bit taken out (`lookupflag 0;`), after which the lookup applies to every mark. The class the font had cannot be told from the code (it was in the opened font's GDEF): to keep the filtering, write the class by hand instead.

**Warnings** (it compiles, and probably does not do what was meant):

- **Glyphs given two ways in one lookup**: fontTools refuses them, Adobe's compiler keeps the first rule.
- **Languages without a languagesystem line**: a feature names a script or language (`script cyrl;`, `language TRK;`) that no `languagesystem` line declares. The feature's rules then apply to it alone: in text in that language, the font's other features are missing.
- **No default language system**: the prefix declares language systems but not `DFLT dflt`, so text in any script it does not name gets no features.
- **Empty classes**: a rule using one never applies.
- **Classes defined twice, differently**: in FontLab's *Classes* panel and in the code, or twice in the code, with other glyphs. Each rule uses the definition read last before it, which may not be the one meant. FontLab writes each of its classes into the prefix too, the same; those copies are not listed.

**Advice** (it does nothing, or could be better):

- **Rules written twice** in the same lookup: the second does nothing. A rule of another kind between them begins another lookup (`sub a by b; sub c d by a; sub a by b;` is three lookups in FontLab's fontTools, and the second `sub a by b` turns the *a* the ligature makes), as do a lookup flag, a script or language, a subtable break, and a lookup's reference: the same rule after one of those is no duplicate.
- **Substitutions that change nothing**: `sub c by c;`.
- **Glyphs listed twice in a class**. Not a class whose glyphs pair with another's: in `sub @a by @b;`, two glyphs of `@a` may become one glyph, which `@b` names twice, and must.
- **Classes defined twice** in the code, the same: the second definition does nothing (its fix removes it).
- **Classes never used**: defined in the code, used by no rule and no other class. FontLab's own classes (its *Classes* panel's) are never listed: the code may not use them, and they are kept there. A class or lookup named by a feature set aside for a syntax error counts as used.
- **Lookups never used**: a lookup outside every feature that no feature or rule refers to. It is compiled into the font and never applied.
- **Empty lookups** and **features with no rule**: an app may list such a feature (a stylistic set with a name) that does nothing.
- **aalt not first**: the specification asks for it before the other features.

FontLab's automatic code (between its `#> feature` and `#<` comment lines) is checked like the rest, and marked so in the list, but never fixed: FontLab writes it again on compiling.

## Fixes, and when one counts as safe

A finding with a fix has a check box, unticked: by default every finding is for you to review. Its last column says what the fix does and how it was proven:

- *changes nothing in the compiled font*: the font's code was compiled with the fix and without it, and the two layouts are the same, compared by what they do, not by their bytes: for each script and language, the lookups that apply, in their order, and which features they come from (a required feature told apart), with what each substitutes or positions (classes expanded to their glyphs, kerning to its pairs, a pair covered by an earlier subtable counted as that subtable's), the features' parameters and names, and GDEF's classes.
- *changes the compiled font: review it*: the layouts differ.
- *not proven: part of the code does not compile; mend the errors first*: while any feature is set aside for an error, no fix is proven, since the code built without it cannot show what a fix does to it (a class or lookup it uses, directly or through others).
- *changes what the font does: review it*: a fix that changes the font by design (a lookup flag taken out), never proven and never applied automatically.
- *mends code that does not compile: review it*: a repair (aalt's lookups written into it, a class made FontLab's again), never applied automatically.

Where the code compiles as it is, every fix is compared with it as it is. Only where it does not (a `lookupflag 16;`, or a single substitution written twice, which FontLab's fontTools refuses) is a copy made to compile, those statements blanked or cleared at the same width so the offsets of every fix stay right.

Removals of classes and lookups nothing uses, and of a class's second identical definition, are proven together, a group that is not the same split in halves: taking out one of them leaves the others as they were. Every other fix is proven alone, since two fixes can work only together (two classes whose repeats pair: each removal alone breaks the rule).

**Lookups inside aalt** (an error): FontLab writes the lookups of aalt inside the feature when it opens some fonts (`feature aalt { ... lookup aalt_2 useExtension { ... } aalt_2; }`), and neither its own compiler ("`lookup` use not allowed in 'aalt' feature") nor fontTools takes a lookup there, so none of the font's features compiles. The repair writes the lookups' rules straight into aalt, which both take. Until it is applied, aalt is set aside and nothing is proven, a fix to a class only aalt uses included. A font whose prefix lost the repeats of a class aalt needs (`@aalt2`, which its `sub @aalt by @aalt2;` needs) shows *@aalt2 is defined twice, differently* (FontLab's class keeps the repeats), with a repair that makes the prefix's copy FontLab's class again.

A fix that would not compile is no fix: the finding stays, without a check box, and says so. Dropping the repeated glyph of `[a b a]` in `sub [a b a] by [x y z];` is one: each glyph takes the glyph in its place, so the class must keep its length.

*Apply ticked fixes* applies the ticked ones as one step of FontLab's History (*Edit > Undo* takes it back), then checks again. The code is read again first: if it changed since the check, nothing is written and the list is made again.

*Apply safe fixes automatically*: at each check, the fixes of the kinds that only ever take out dead code (rules written twice, substitutions that change nothing, glyphs listed twice in a class, a class's second identical definition, classes and lookups never used) are applied once each is proven alone and all together, and the list shows what is left. Empty features are never taken out automatically, since an app's menu may show them; tick them by hand. The option is remembered. It applies when the window opens and when *Check* is clicked, never when FontLab's History moves: after *Edit > Undo* of the automatic fixes, the window checks again and leaves the code as the undo put it back, until you click *Check*.

## FreeLab's writers check their own code

Feature Code, Glyph Compose (its mark features), CJK Spacing, and CJK Vertical check the whole font's code as it would be after their write before they write it: when it would bring an error the font's code does not have now, nothing is written and the log says what and where. Errors the font already had do not stop them, and neither does a rule only moved; glyphs the same write adds (CJK Vertical's built forms) count as in the font. Without Feature Check installed, or without fontTools, they write unchecked. The checks of the code before and after the last write (a compiled copy of the layout of every glyph each) are kept for the next write, and let go as any FreeLab window closes: on BIZ UDPGothic (13,932 glyphs) two of them outlived Feature Code's window (live, 2026-11-19). What a write keeps after that is FontLab's: its History records the whole font at the write's steps, about 0.5 GB on BIZ UDPGothic, which *Edit > Undo* needs.

## The compiler

The checks use fontTools' feature compiler (feaLib), which FontLab 7 ships (3.43); the tests run on it and on fontTools 4. FontLab compiles with Adobe's compiler (hotconv), which differs in places: it keeps the first of two conflicting rules where fontTools refuses them, and it stops on its own limits. *Compile in FontLab* compiles there, as the *Features* panel's *Compile* button does, and adds what FontLab's *Output* panel shows to the log. While FontLab compiles, and until what its compiler said is read (a few seconds at most), the window's top row shows a bar in place of the font line; a compile cannot be stopped halfway, so the tools menu, the arrows, and *Close* wait for it.

A large font's code takes a while, and a bar in the window's top row shows the step (reading the code, compiling it, proving the fixes). Amiri (6,710 glyphs, a 231 KB prefix and 23 features) takes about 5 seconds to check inside FontLab: the code is parsed and built once, and the font without fixes is built once for all the proofs. The fixes that take out an unused class, an unused lookup, or a class's second identical definition are proven together, in one build; only a group that changes the layout or does not compile is split in halves, down to the fix that does. Every other fix is proven alone, since such fixes can depend on each other. A kerning change is compared pair by pair, up to 3 million pairs; past that, it is not proven. A CJK font of 15,444 glyphs and 704 classes checks in about 3 seconds outside FontLab. A writer's own check costs about as much as a check: 5 to 10 seconds on a font of Amiri's size, a fraction of a second on most.
