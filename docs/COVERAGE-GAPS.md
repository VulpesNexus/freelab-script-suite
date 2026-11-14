# Coverage gaps: what Font Check knows of and does not check

Unicode's own data, compared with what Font Check checks (languages, character sets, scripts, sequences, marks): what was added, and what is acknowledged with the reason it is not checked. *checks/train/coverage_gaps.py* writes this page and *checks/coverage_gaps.json* from the pinned data (Unicode 17.0.0, Unihan, CLDR 49, the Ideographic Variation Database of 2025-07-14); its *--check* fails when they differ from what the data gives, so the counts cannot drift. The sources are registered in [SOURCES.md](SOURCES.md).

## Summary

| What | Decision | Count |
| --- | --- | --- |
| Han repertoires (national standards, lists, and Unihan's other writings) | added: sets | 20 sets |
| Unicode blocks no set or script holds whole | acknowledged | 19 of 346 blocks |
| Unihan sources and fields not made sets | acknowledged | 11 |
| Named sequences | acknowledged | 461 |
| Standardized variation sequences | acknowledged | 1,353 |
| Emoji variation sequences | acknowledged | 742 |
| Emoji sequences (keycaps, flags, tags, modifiers, ZWJ) | acknowledged | 2,553 |
| Ideographic variation sequences | acknowledged | 39,501 |
| Joining and Indic syllable shaping | acknowledged | 780 joining and 4,856 Indic characters |
| CLDR's punctuation and number exemplars, regional locales | acknowledged | 188, 115, and 637 locale files |
| Characters FreeLang draws as Unifont's pixels | added: font source | 133 |

## Han repertoires

Font Check's languages had the ideographs of Hyperglot's Chinese, Japanese, and Korean rows (a few thousand). Each repertoire below is a character set under *Han repertoires*, from Unihan's fields as UAX #38 (revision 39) defines them; FreeLang draws each whole, Jigmo supplying what Noto Sans JP, KR, and SC lack. The Han script itself (103,351 ideographs) cannot be drawn whole: a font holds 65,535 glyphs at most, and FreeLang draws 36,179 of them.

| Set | Ideographs | Drawn by FreeLang |
| --- | --- | --- |
| Unihan Core 2020 (Unihan kUnihanCore2020) | 20,720 | 20,720 |
| GB/T 2312-1980 (Unihan G0) | 6,763 | 6,763 |
| Tōngyòng Guīfàn Hànzìbiǎo, 2013 (Unihan kTGH) | 8,105 | 8,105 |
| Big Five (Unihan kBigFive) | 13,064 | 13,064 |
| HKSCS-2008 and 2016 (Unihan H and HD) | 4,605 | 4,605 |
| Jōyō kanji, 2010 (Unihan kJoyoKanji) | 2,136 | 2,136 |
| Jinmei-yō kanji (Unihan kJinmeiyoKanji) | 863 | 863 |
| JIS X 0208-1990 (Unihan J0) | 6,356 | 6,356 |
| JIS X 0213:2004, levels 3 and 4 (Unihan kJIS0213) | 3,695 | 3,695 |
| Japanese kokuji (Unihan JK) | 782 | 782 |
| KS X 1001:2004 hanja (Unihan K0) | 4,888 | 4,888 |
| Basic education hanja, 2007 (Unihan kKoreanEducationHanja) | 1,800 | 1,800 |
| Personal-name hanja (Unihan kKoreanName) | 6,367 | 6,367 |
| Sawndip (Unihan GZ, GZA, GPGLG, and GLGYJ) | 3,812 | 3,812 |
| TCVN 5773:1993 (Unihan V0) | 2,345 | 2,345 |
| TCVN 6056:1995 (Unihan V1) | 3,309 | 3,309 |
| VHN 01:1998 (Unihan V2) | 3,198 | 3,198 |
| VHN 02:1998 (Unihan V3) | 533 | 533 |
| Hán Nôm Coded Character Repertoire (Unihan V4) | 2,008 | 2,008 |
| Vietnamese extensions (Unihan VN) | 2,883 | 2,883 |

Writings in Han characters, and scripts derived from them:

| Writing | Decision | What and why |
| --- | --- | --- |
| Chu Nom (Vietnamese) | added | six sets, one per Vietnamese source of the IRG (Unihan V0 to V4, VN) |
| Sawndip (Zhuang) | added | one set: Unihan's GZ, GZA, GPGLG, and GLGYJ sources |
| Japanese kokuji | added | one set: Unihan's JK source, the Japanese KOKUJI Collection |
| Cantonese characters | added in part | HKSCS-2008 and 2016 is a set; no source lists Cantonese-specific characters as such |
| Taiwanese Hokkien and Hakka characters | acknowledged | Taiwan's Ministry of Education lists recommended characters, but no pinned source with a license checked here holds them; most are in Big Five |
| Korean gukja | acknowledged | no Unihan field or source marks them |
| Bai characters | acknowledged | no source describes them; most are not encoded |
| Jurchen, Khitan Large Script | acknowledged | not encoded in Unicode (the Script Encoding Initiative lists them) |
| Tangut, Nushu, Khitan Small Script | checked | scripts of their own, checked as sets under Scripts (Unicode) |

Unihan's sources and fields left as they are:

| Unihan | Ideographs | Why not a set |
| --- | --- | --- |
| G sources other than G0 and the Zhuang ones | 69,737 | the dictionaries and lists China gave the IRG: a record of where an ideograph was found, not a repertoire a font is made for |
| J sources other than J0 and JK (JIS X 0212, JIS X 0213's replacements, the vendors' and Moji Joho lists) | 52,649 | JIS X 0213, the current standard, is a set (kJIS0213); the Moji Joho list (38,070) is an administrative register of name variants |
| K sources other than K0 (KS X 1002, KS X 1027, the history database) | 21,629 | supplementary standards of rare and historical hanja |
| KP sources (KPS 9566-97, KPS 10721-2000) | 24,132 | North Korea's standards: no font is known to target them apart from KS X 1001 |
| T sources other than Big Five's planes (CNS 11643 planes 3 to 19) | 60,106 | the rare ideographs of Taiwan's full standard, beyond Big Five |
| M sources (Macao) | 348 | 348 ideographs, most of them HKSCS's too |
| S source (the SAT Taisho Daizokyo) | 3,715 | a Buddhist canon's ideographs |
| UK source | 3,409 | the ideographs the United Kingdom submitted from scholarly texts |
| U source (the UTC) | 1,182 | ideographs the UTC submitted |
| Cantonese readings | 29,936 | a reading for nearly every ideograph: no list of Cantonese-specific characters (HKSCS, a set, holds those Hong Kong encodes) |
| Standard Zhuang readings | 2,472 | readings of the Sawndip ideographs, which are a set |

## Unicode blocks

The blocks whose characters no character set holds whole and no script owns whole (the others are either a set, under its group, or a script's, under *Scripts (Unicode)*). Private-use and surrogate blocks hold no characters.

| Block | Assigned | Held by nothing | Why |
| --- | --- | --- | --- |
| Cyrillic | 256 | 2 | marks no set or script holds |
| Devanagari | 128 | 6 | characters no set or script holds |
| Tibetan | 211 | 4 | characters no set or script holds |
| Georgian | 88 | 1 | characters no set or script holds |
| Runic | 89 | 3 | characters no set or script holds |
| Hanunoo | 23 | 2 | characters no set or script holds |
| Mongolian | 158 | 3 | characters no set or script holds |
| Hiragana | 93 | 4 | characters no set or script holds |
| Katakana | 96 | 3 | characters no set or script holds |
| Latin Extended-D | 204 | 3 | characters no set or script holds |
| Kayah Li | 48 | 1 | characters no set or script holds |
| Javanese | 91 | 1 | characters no set or script holds |
| Latin Extended-E | 60 | 3 | characters no set or script holds |
| Variation Selectors | 16 | 16 | variation selectors: a font maps them in its cmap's format 14, which Font Check does not read |
| Specials | 5 | 1 | characters no set or script holds |
| Grantha | 86 | 1 | marks no set or script holds |
| Shorthand Format Controls | 4 | 0 | control or format characters: no glyph is drawn for them |
| Tags | 97 | 0 | control or format characters: no glyph is drawn for them |
| Variation Selectors Supplement | 240 | 240 | variation selectors: a font maps them in its cmap's format 14, which Font Check does not read |

## Sequences

Font Check reads a font's character map and the anchors that join a letter and its marks. A sequence that a font draws through its layout (a ligature, a contextual form, a variation sequence in its cmap's format 14) is not checked: that would need shaping, which Font Check does not do. An orthography's letter-and-mark clusters are checked, as before.

- **Named sequences** (*NamedSequences.txt*), by script: Tamil 290, Latin 69, Khmer 41, Common 14, Arabic 9, Katakana 9, Devanagari 8, Gurmukhi 6, Hiragana 5, Bengali 4, Sinhala 3, Oriya 2, Georgian 1. The Latin ones are letters with marks, checked where an orthography lists them; the Tamil, Khmer, and other Indic ones are syllables a font forms by shaping.
- **Standardized variation sequences** (*StandardizedVariants.txt*), by script of the base: Han 1002, Egyptian Hieroglyphs 146, Common 107, Mongolian 60, Myanmar 27, Phags Pa 6, Manichaean 5.
- **Emoji**: 742 emoji variation sequences; the sequences Emoji Keycap Sequence 12, RGI Emoji Flag Sequence 259, RGI Emoji Modifier Sequence 665, RGI Emoji Tag Sequence 3, RGI Emoji ZWJ Sequence 1,614. Of the 1,438 characters with the Emoji property, 1,438 are in a character set and FreeLang draws 1,438.
- **Ideographic variation sequences** (the IVD of 2025-07-14), by collection: Adobe-Japan1 14,684, Hanyo-Denshi 13,045, Moji_Joho 11,384, CAAPH 198, MSARG 154, KRName 36.

## Shaping

Font Check checks characters, not how a font shapes them: the 780 characters that join (*ArabicShaping.txt*: Arabic, Syriac, N'Ko, Mandaic, Manichaean, and others) and the 4,856 characters an Indic syllable is built of (*IndicSyllabicCategory.txt*) are checked one by one, and their contextual forms, conjuncts, and reordering are a font's layout, which only shaping can test.

## CLDR

The orthographies take each locale's main and auxiliary exemplars. CLDR 49 also gives punctuation exemplars in 188 locale files and number exemplars in 115, which no language's row asks for (a font for a language would need its quotation marks), and 637 regional or variant locale files are not read. CLDR's keyboards and its seed locales are not in the pinned archive.

## What FreeLang draws as pixels, and what it cannot draw

GNU Unifont draws, as a 16 by 16 grid of pixels, the characters no outline font under a license FreeLang can take has: Unifont, 38 characters (0860-086A 088F 0897 FBC3-FBD2 FD90-FD91 FDC8-FDCE); Unifont Upper, 95 characters (10EC2-10EC7 10ED0-10ED8 10EFA-10EFC 1CCFA-1CCFB 1CEBA-1CEBF 1E6C0-1E6DE 1E6E0-1E6F5 1E6FE-1E6FF 1F6D8 1FA89-1FA8A 1FA8E-1FA8F 1FABE 1FAC6 1FAC8 1FACD 1FADC 1FADF 1FAE9-1FAEA 1FAEF). No source at all has 713 characters: Egyptian Hieroglyphs Extended-A 568, Tangut 8, Tangut Components Supplement 115, Tangut Supplement 22. Egyptian's are the signs NewGardiner leaves out as non-core (unverified, its maker says); Tangut's are the additions of Unicode 16 and 17, which no font under a license FreeLang can take draws.

## Fonts to consider for what FreeLang cannot draw

Fonts a designer working on these characters can install beside FreeLang. They are not part of FreeLang and are not distributed with FreeLab; each license was read from the font's own files.

| Font | Maker | License | Where | What it draws that FreeLang does not | Caution |
| --- | --- | --- | --- | --- | --- |
| Jigmo, Jigmo2, Jigmo3 | Kamichi Koichi (GlyphWiki) | CC0 1.0 | https://kamichikoichi.github.io/jigmo/ | every ideograph of Unicode 17.0 (103,351, and the compatibility ideographs), of which FreeLang holds only the Han repertoires' and the orthographies' | public domain: install it beside FreeLang; too large for one of its files (65,535 glyphs at most) |
| Noto Color Emoji | Google | SIL OFL 1.1 | https://github.com/googlefonts/noto-emoji | all 1,219 characters with the Emoji_Presentation property in color, the 14 newest among them (FreeLang draws those as Unifont's pixels), and 2,564 emoji sequences (ZWJ, flags, keycaps, skin tones) as ligatures | a color font (COLR version 1, SVG): its outlines are color layers, so no plain glyph can be taken from it |

## Fonts looked at again

The fonts the build left out, or that earlier work dismissed, read again on 2026-11-14.

| Font | Now | Why |
| --- | --- | --- |
| GNU Unifont 18.0.01 (Unifoundry) | taken | dual-licensed (GPL 2 or later with the font embedding exception, and the SIL OFL 1.1, since 13.0.04): FreeLang takes it under the OFL, for the characters no outline font under a license FreeLang can take draws; its glyphs are a 16 by 16 grid of pixels |
| Jigmo 2025-09-12 (Kamichi Koichi, GlyphWiki) | taken | CC0 1.0 (its LICENSE.txt): the ideographs of the Han repertoires that Noto Sans JP, KR, and SC lack |
| NewGardiner 3.09 (Mark-Jan Nederhof) | taken | SIL OFL 1.1 (its OFL.txt; its copyright record says so): the core signs of Egyptian Hieroglyphs Extended-A; it leaves out the non-core ones, which its maker calls unverified |
| Plangothic (OFL 1.1) | not needed | a gothic design for Extension B to J, which would match Noto Sans CJK better than Jigmo's Mincho; Jigmo draws every ideograph the data asks for |
| BabelStone Tangut Wenhai 1.002 | not needed | OFL 1.1, of 2016: none of Tangut's Unicode 16 and 17 additions, the only Tangut FreeLang lacks |
| Tangut Yinchuan (as BabelStone's page lists it) | still left out | "Copyright Prof. Jing Yongshi", no license named |
| Noto Serif Tai Yo 1.030 (as Language Tools and Unicodia bundle it) | still left out | no copyright, license, or designer record and no license file; notofonts.github.io issue 81, which offers it to Noto, is still open |
| Catrinity 2.250 | not needed | OFL 1.1; every character it drew that FreeLang lacked now has a source |
| Fairfax HD | not needed | OFL 1.1, a monospaced font drawn on a pixel grid |
| JuliaMono 0.63.2, Charis 7.000 | not needed | OFL 1.1; nothing FreeLang lacks |
| Symbola (later versions), Everson Mono, Code2000 | still left out | not free licenses |
| The font Unicodia bundles for Syriac Supplement | still left out | its license forbids commercial use (as read on 2026-11-13); Unifont draws the eleven characters |
