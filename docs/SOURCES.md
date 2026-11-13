# Sources: in use, weighed, and to watch

What FreeLab's data and fonts are made from, what was looked at and left out, and what to look at again when the data is updated. The data itself is described in [FONT-CHECK.md](FONT-CHECK.md#the-data); this page is the register of sources, so that the next update starts from what is known rather than from a search. Dates are the days a page was read. A source is shipped only when it can be pinned (a release, a commit, a checksum) and its license, quoted from the source itself, allows redistribution and changes in a GPL-3.0-or-later repository.

## In use

| Source | Gives | License | Pinned by |
| --- | --- | --- | --- |
| [Hyperglot](https://github.com/rosettatype/hyperglot) 0.8.2 | Orthographies of 799 languages (the first choice; a declared source or a layout may add a script it does not give a language in: 66 languages) | Apache License 2.0 | release archive, SHA-256 |
| Google Fonts' language data ([googlefonts/lang](https://github.com/googlefonts/lang)) | Declared orthographies, autonyms, sample texts | Apache License 2.0 | release v0.7.9 |
| [Unicode CLDR](https://cldr.unicode.org) 49 | Declared exemplar characters; scripts per language | Unicode License V3 | *cldr-common-49.zip* |
| SIL's Locale Data Repository ([silnrsi/sldr](https://github.com/silnrsi/sldr)) | Declared and generated exemplars | MIT License | tag 26062.1946 |
| [Unilex](https://github.com/unicode-org/unilex) | Word frequencies, counted | Unicode License V3 | commit b3a9ae27 |
| An Crúbadán (Kevin Scannell) | Word frequencies (7 archives the Wayback Machine kept); character trigrams of 2010 (NLTK's *crubadan* package) | CC BY 4.0 (archives); GPL version 3 or later (trigrams) | each capture; nltk/nltk_data commit fa7aae1c |
| The Universal Declaration of Human Rights (NLTK's *udhr2* package) | Whole texts, counted | public domain, by NLTK's index | nltk/nltk_data commit 5d8fe95a |
| [Language Tools](https://languagetools-153419.appspot.com/) (Craig Cornelius, with Translation Commons); source [sven-oly/LanguageTools](https://github.com/sven-oly/LanguageTools) | Keyboard layouts, a third kind of evidence: 37 orthographies of 37 languages (18 no other source describes, 16 scripts no orthography here was written in when they were added; Manipuri's and Laz's are set aside for a declared source's), 131 layouts read, 10 under the floor, and 1 refused as unfinished (Gondi in Telugu, whose shift layer types Tibetan); Sylheti's two Syloti Nagri layouts are not read (no key for *kho*, *cho*, or the anusvara: its counted row is better) | Apache License 2.0 (the repository's *LICENSE*; 111 of the files read carry its header); its fonts, mostly unlicensed, are not used | commit a9386e0031b086418f402338a7428449b08166a1 of the live branch *p3_version* (read 2026-11-13; *master* stopped on 2023-12-21), each layout file by its SHA-256, fetched alone |
| [Glottolog](https://glottolog.org) 5.4 | Families, other names, the languages no source describes; for the orthographies, a language's English name where no source gives one, its constructed status, which codes name a language, and the languages Hyperglot describes through their dialects or members (Akan) | CC BY 4.0 | glottolog-cldf commit 84977fca |
| Unicode Character Database 17.0 | Scripts, blocks, ages, categories | Unicode License V3 | file SHA-256s |
| Google Fonts' glyph sets 1.1.3; Adobe's Latin, Cyrillic, and Greek character sets | Character sets | Apache License 2.0; MIT License | tag; commits |
| Noto fonts and eight others (FreeLang) | The glyphs Font Check draws | SIL Open Font License 1.1 | listed in *checks/language_font/language_font.json* |

## Weighed and left out

| Source | Why not | What would change it |
| --- | --- | --- |
| Wikipedia text | CC BY-SA: not shippable here; about 30 languages beyond the rest | A need it alone fills |
| The *UDHR in Unicode* project's own site | Ended in January 2024; the United Nations' site has no release to pin | Used through NLTK's copy instead |
| NLTK *panlex_swadesh* (CC0) | Short word lists, many in linguists' transcription rather than an orthography; a median of 12 base characters lacking | A use for transcriptions as such |
| NLTK *swadesh*, *extended_omw*, *universal_treebanks* | GFDL, CC BY-SA, non-commercial | None |
| An Crúbadán's own site (crubadan.org) | No longer answers; the Wayback Machine kept the pages but only 7 of about 2,200 archives | The archives published again |
| GNU Unifont | Bitmap-derived glyphs, unlike the rest of FreeLang | Nothing else having a character (see *checks/language_font/removed_sources.md*) |
| Language Tools' fonts (its repository, 187 MB of them) | Most carry no license; a repository's license covers what its own licensor can license | A license from each font's author |
| Language Tools' layouts that type private-use or unassigned code points (Bete, Kpelle, Loma, Qiang, Kurmali's Chisoi, Lampung, Wolof's Catya, Nsibidi) or a script they are not named for (Tulu's types Malayalam; Wolof's Garay and Zaghawa's Beria Erfe type Latin) | No encoded character of the script to keep | The script encoded, and the layout updated to it |

## To watch: reference points and candidates

Read on 2026-11-13. These are not shipped: some state no license, and the others are pointers to primary sources.

| Source | What it holds | License | Use |
| --- | --- | --- | --- |
| [Script Encoding Initiative](https://sei.berkeley.edu/) (UC Berkeley, Department of Linguistics), [Scripts to encode](https://sei.berkeley.edu/scripts-to-encode/) | 192 scripts and notations not yet encoded, each with its region, languages, status, readiness, latest proposal, and authors; 36 rated nearly ready (among them Kulitan, Lampung, Mwangwego, Jurchen) | None stated | The fuller list of what is not yet encoded; it and Unicode's own list disagree on Chola |
| SEI's [Completed proposals](https://sei.berkeley.edu/completed-proposals/) | Document numbers and authors of encoded scripts (Garay L2/16-069, Sunuwar L2/21-157R, Todhri L2/20-188, Sidetic L2/23-019, Tolong Siki L2/23-024: read through a summarizer, to confirm before quoting) | None stated | Where to read a recent script's proposal |
| SEI's [Helpful sites](https://sei.berkeley.edu/helpful-sites/) | ScriptSource, r12a's script pages, the Atlas of Endangered Alphabets, Anshuman Pandey's work, Translation Commons | n/a | Where a designer can find an orthography |
| [Unicode's chart fonts](https://www.unicode.org/charts/fonts.html) | Who made each script's chart font | Not usable: chart fonts may not be extracted or reused | Who to ask for a font |
| [Unicode's unsupported scripts](https://www.unicode.org/standard/unsupported.html) and [pipeline](https://www.unicode.org/alloc/Pipeline.html) | The twelve scripts Font Check names as not encoded; scripts accepted for coming versions | n/a | Read again at each update |
| Noto's [coverage overview](https://github.com/notofonts/overview) and [issues](https://github.com/notofonts/notofonts.github.io/issues) | Which characters no Noto font has; fonts in progress (Gurung Khema and Ol Onal have sources but no built font) | SIL OFL 1.1 when released | A released Noto font replaces any other source for its characters |

## Open: Tai Yo

FreeLang draws none of Tai Yo's 55 characters. The only font known, "Noto Serif Tai Yo" 1.030 (made with FontCreator on 2023-09-04; distributed by Language Tools since September 2023 and bundled by [Unicodia](https://github.com/Mercury13/unicodia)), carries no copyright, license, or designer record, and no license file accompanies it: a repository's license covers what its own licensor can license, not a third party's font placed in it. It is not a Noto font; [notofonts.github.io issue 81](https://github.com/notofonts/notofonts.github.io/issues/81), which offers a file of that name to Noto, is open and its sources were never supplied. The script's proposal is L2/22-289R, "Final Proposal to encode the Tai Yo Script", by Viet Khoi Nguyen, Cong Danh Sam, and Frank van de Kasteelen (2022-12-16), whose form names Viet Khoi Nguyen as the one who would provide a font and leaves the license line blank. Who to ask for a license: Viet Khoi Nguyen first, then Craig Cornelius (who can say where the file came from), then the proposal's co-authors.

## Not supplied by any font

Besides Tai Yo: Syriac Supplement (U+0860 to U+086A: the one font found forbids commercial use), Bopomofo Extended U+31BC to U+31BF, and 14 pictographs of Unicode 16 and 17. Look again at each update: Noto, then a font designed for the script, then a broad-coverage font, never a bitmap-derived one.
